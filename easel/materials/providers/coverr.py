"""Coverr API discovery adapter; search results are not acquisition approval."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.parse import urlencode

from easel.materials.domain import Availability, CandidateSource, MediaType, RetrievalIntent, RightsStatus, SupplyCandidate
from easel.materials.domain.models import PreviewInfo, RightsHint
from easel.materials.providers.base import ProviderPage
from easel.materials.providers.errors import (
    ProviderAuthError,
    classify_http_error,
    ProviderInvalidResponseError,
    ProviderNetworkError,
    ProviderUnsupportedError,
)
from easel.materials.providers.http_support import (
    HttpResponse,
    HttpTransport,
    UrllibTransport,
    continuation_token,
    decode_json,
    normalized_headers,
    parse_continuation_token,
    safe_https_url,
)
from easel.materials.providers.models import (
    AccessMode,
    PaginationMode,
    ProviderCapability,
    ProviderContinuation,
    ProviderHealth,
    ProviderHealthStatus,
    ProviderInfo,
)


_API_ROOT = "https://api.coverr.co"
_PAGE_SIZE = 20


class CoverrProvider:
    """Search the official Coverr API without exposing signed media URLs."""

    provider_id = "coverr"

    def __init__(self, api_key: str = "", *, transport: HttpTransport | None = None, timeout: float = 20.0):
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self._api_key = api_key.strip()
        self._transport = transport or UrllibTransport()
        self._timeout = timeout
        self._last_success_at: datetime | None = None
        self._quota_remaining: int | None = None
        self._last_error: tuple[str, str, bool, float | None] | None = None

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            provider_id=self.provider_id,
            display_name="Coverr",
            media_types=(MediaType.VIDEO,),
            access_mode=AccessMode.DISCOVERY_ONLY,
            capabilities=(
                ProviderCapability.SEARCH,
                ProviderCapability.PREVIEW,
                ProviderCapability.PAGINATION,
                ProviderCapability.HEALTH_CHECK,
            ),
            pagination_mode=PaginationMode.PAGE,
            auth_mode="Coverr API key in Authorization: Bearer header; key is injected by caller",
            quota_policy="Official API docs list 50 requests/hour for Demo and 2,000/hour for Production (requires active Pro or Ultimate); observe configured tier.",
            cache_policy="No client-side response cache configured; no mandatory API cache duration found in the reviewed docs.",
            attribution_policy="Coverr API integrations must display a clickable Coverr logo. Asset creator credit is not required by the current free-download license but is appreciated.",
            acquisition_policy="Discovery only. Coverr API introduction restricts API use from commercial use; download selection also requires PATCH /videos/{id}/stats/downloads. Neither commercial eligibility nor that selection callback is represented by this adapter.",
        )

    def search(self, intent: RetrievalIntent, continuation: ProviderContinuation | None = None) -> ProviderPage:
        if not self._api_key:
            raise ProviderAuthError(self.provider_id, "Coverr API key is not configured")
        if intent.filters.get("media_type") != MediaType.VIDEO.value:
            raise ProviderUnsupportedError(self.provider_id, "Coverr supports video discovery only")
        query_index, page_token = self._continuation(intent, continuation)
        params = {
            "query": intent.semantic_queries[query_index],
            "page": page_token - 1,
            "page_size": _PAGE_SIZE,
            "sort": "popular",
        }
        response = self._get(f"{_API_ROOT}/videos?{urlencode(params)}")
        payload = self._object(response)
        hits = payload.get("hits")
        if not isinstance(hits, list):
            raise ProviderInvalidResponseError(self.provider_id, "Coverr response is missing hits")
        candidates = tuple(self._candidate(item, intent.need_id) for item in hits)
        current_page = self._positive_or_zero(payload.get("page"), "page")
        pages = self._positive_or_zero(payload.get("pages"), "pages")
        next_state = None
        if current_page + 1 < pages:
            next_state = (query_index, current_page + 2)
        elif query_index + 1 < len(intent.semantic_queries):
            next_state = (query_index + 1, 1)
        continuation_out = (
            ProviderContinuation(
                provider_id=self.provider_id,
                mode=PaginationMode.PAGE,
                token=continuation_token(intent, *next_state),
            )
            if next_state else None
        )
        self._record_success(response)
        return ProviderPage(candidates=candidates, continuation=continuation_out)

    def health(self) -> ProviderHealth:
        if self._last_error:
            from easel.materials.providers.models import ProviderFailureRecord

            category, message, retryable, retry_after = self._last_error
            return ProviderHealth(
                provider_id=self.provider_id,
                status=ProviderHealthStatus.DEGRADED,
                last_success_at=self._last_success_at,
                quota_remaining=self._quota_remaining,
                retry_after_seconds=retry_after,
                degraded_reason=message,
                last_error=ProviderFailureRecord(
                    provider_id=self.provider_id, category=category, message=message,
                    retryable=retryable, retry_after_seconds=retry_after,
                ),
            )
        return ProviderHealth(
            provider_id=self.provider_id,
            status=ProviderHealthStatus.HEALTHY if self._last_success_at else ProviderHealthStatus.UNKNOWN,
            last_success_at=self._last_success_at,
            quota_remaining=self._quota_remaining,
        )

    def _get(self, url: str) -> HttpResponse:
        try:
            response = self._transport.get(
                url, headers={"Authorization": f"Bearer {self._api_key}", "Accept": "application/json"},
                timeout=self._timeout,
            )
        except Exception as exc:
            raise self._fail(ProviderNetworkError(self.provider_id, "Coverr API request failed")) from exc
        headers = normalized_headers(response.headers)
        if response.status_code == 200:
            return response
        error = classify_http_error(
            self.provider_id, response.status_code, response.headers, response.body,
            retry_after_seconds=self._retry_after(headers),
        )
        raise self._fail(error)

    def _fail(self, error):
        self._last_error = (error.category.value, error.message, error.retryable, error.retry_after_seconds)
        return error

    def _record_success(self, response: HttpResponse) -> None:
        # The reviewed Coverr API docs publish account-tier limits but do not
        # document a response quota header, so remaining quota is not inferred.
        self._quota_remaining = None
        self._last_success_at = datetime.now(timezone.utc)
        self._last_error = None

    def _object(self, response: HttpResponse) -> dict:
        try:
            payload = decode_json(response)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderInvalidResponseError(self.provider_id, "Coverr API returned malformed JSON") from exc
        if not isinstance(payload, dict):
            raise ProviderInvalidResponseError(self.provider_id, "Coverr API returned a non-object response")
        return payload

    def _candidate(self, item: object, need_id: str) -> SupplyCandidate:
        if not isinstance(item, dict):
            raise ProviderInvalidResponseError(self.provider_id, "Coverr video record is malformed")
        native_id = item.get("id")
        if not isinstance(native_id, (str, int)) or not str(native_id).strip():
            raise ProviderInvalidResponseError(self.provider_id, "Coverr video record is missing identity")
        preview_url = safe_https_url(item.get("poster")) or safe_https_url(item.get("thumbnail"))
        tags = item.get("tags")
        if tags is not None and (not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags)):
            raise ProviderInvalidResponseError(self.provider_id, "Coverr video tags are malformed")
        metadata: dict[str, object] = {
            "api_attribution_required": "clickable_coverr_logo",
            "api_usage_restriction": "commercial_use_not_confirmed",
            "license_evidence_url": "https://coverr.co/license",
        }
        for source_key, normalized_key in (
            ("title", "title"), ("description", "description"),
            ("duration", "duration_seconds"), ("max_width", "width"), ("max_height", "height"),
        ):
            value = item.get(source_key)
            if isinstance(value, (str, int, float)) and not isinstance(value, bool):
                metadata[normalized_key] = value
        if tags:
            metadata["tags"] = tuple(tag.strip() for tag in tags if tag.strip())
        return SupplyCandidate(
            candidate_id=f"coverr:{native_id}",
            need_id=need_id,
            media_type=MediaType.VIDEO,
            source=CandidateSource(kind="stock", provider=self.provider_id, provider_asset_id=str(native_id)),
            preview=PreviewInfo(url=preview_url) if preview_url else None,
            availability=Availability.PREVIEWABLE if preview_url else Availability.DISCOVERED,
            rights_hint=RightsHint(status=RightsStatus.UNKNOWN),
            metadata=metadata,
        )

    def _continuation(self, intent: RetrievalIntent, continuation: ProviderContinuation | None) -> tuple[int, int]:
        if continuation is None:
            return 0, 1
        if continuation.provider_id != self.provider_id or continuation.mode is not PaginationMode.PAGE:
            raise ProviderUnsupportedError(self.provider_id, "Continuation does not belong to CoverrProvider")
        state = parse_continuation_token(continuation.token, intent)
        if state is None:
            raise ProviderUnsupportedError(self.provider_id, "Coverr continuation is invalid for this search")
        return state

    def _positive_or_zero(self, value: object, field: str) -> int:
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ProviderInvalidResponseError(self.provider_id, f"Coverr {field} value is invalid")
        return value

    @staticmethod
    def _retry_after(headers: dict[str, str]) -> float | None:
        try:
            return max(0.0, float(headers["retry-after"]))
        except (KeyError, ValueError):
            return None


__all__ = ["CoverrProvider"]
