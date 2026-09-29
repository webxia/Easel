"""Unsplash API search adapter preserving hotlink and selection-tracking rules."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl

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


_API_ROOT = "https://api.unsplash.com"
_PAGE_SIZE = 20  # Unsplash documents a maximum per_page of 30.
_APP_NAME = "easel"


class UnsplashProvider:
    """Search Unsplash without copying media; record selection events explicitly."""

    provider_id = "unsplash"

    def __init__(self, access_key: str = "", *, transport: HttpTransport | None = None, timeout: float = 20.0):
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self._access_key = access_key.strip()
        self._transport = transport or UrllibTransport()
        self._timeout = timeout
        self._last_success_at: datetime | None = None
        self._quota_remaining: int | None = None
        self._last_error: tuple[str, str, bool, float | None] | None = None

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            provider_id=self.provider_id,
            display_name="Unsplash",
            media_types=(MediaType.IMAGE,),
            access_mode=AccessMode.DISCOVERY_ONLY,
            capabilities=(
                ProviderCapability.SEARCH,
                ProviderCapability.PREVIEW,
                ProviderCapability.ATTRIBUTION_METADATA,
                ProviderCapability.DOWNLOAD_TRACKING,
                ProviderCapability.PAGINATION,
                ProviderCapability.HEALTH_CHECK,
            ),
            pagination_mode=PaginationMode.PAGE,
            auth_mode="Unsplash Access Key in Authorization: Client-ID header; key is injected by caller",
            quota_policy="Observe X-Ratelimit-Limit and X-Ratelimit-Remaining; application tier limits are not assumed by the adapter.",
            cache_policy="No client-side response or image cache configured; official guidelines require hotlinked photo.urls for all image use.",
            attribution_policy="Display Unsplash and photographer credit with referral links including utm_source=easel&utm_medium=referral.",
            acquisition_policy="Discovery only. On user selection call photo.links.download_location; direct media acquisition is not claimed because current Easel has no selection/hotlink presentation adapter.",
        )

    def search(self, intent: RetrievalIntent, continuation: ProviderContinuation | None = None) -> ProviderPage:
        if not self._access_key:
            raise ProviderAuthError(self.provider_id, "Unsplash Access Key is not configured")
        if intent.filters.get("media_type") != MediaType.IMAGE.value:
            raise ProviderUnsupportedError(self.provider_id, "Unsplash supports image discovery only")
        query_index, page = self._continuation(intent, continuation)
        params: dict[str, str | int] = {
            "query": intent.semantic_queries[query_index],
            "page": page,
            "per_page": _PAGE_SIZE,
        }
        orientation = intent.filters.get("orientation")
        if isinstance(orientation, str) and orientation in {"landscape", "portrait", "squarish"}:
            params["orientation"] = orientation
        response = self._get(f"{_API_ROOT}/search/photos?{urlencode(params)}")
        payload = self._object(response)
        results = payload.get("results")
        if not isinstance(results, list):
            raise ProviderInvalidResponseError(self.provider_id, "Unsplash response is missing results")
        candidates = tuple(self._candidate(item, intent.need_id) for item in results)
        total_pages = payload.get("total_pages")
        if not isinstance(total_pages, int) or isinstance(total_pages, bool) or total_pages < 0:
            raise ProviderInvalidResponseError(self.provider_id, "Unsplash total_pages is invalid")
        next_state = (query_index, page + 1) if page < total_pages else (
            (query_index + 1, 1) if query_index + 1 < len(intent.semantic_queries) else None
        )
        next_continuation = (
            ProviderContinuation(
                provider_id=self.provider_id, mode=PaginationMode.PAGE,
                token=continuation_token(intent, *next_state),
            ) if next_state else None
        )
        self._record_success(response)
        return ProviderPage(candidates=candidates, continuation=next_continuation)

    def record_selection(self, candidate: SupplyCandidate) -> None:
        """Call Unsplash's required download endpoint after a user selects a photo."""
        if candidate.source.provider != self.provider_id or candidate.media_type is not MediaType.IMAGE:
            raise ProviderUnsupportedError(self.provider_id, "Selection candidate is not from Unsplash")
        tracking_url = candidate.metadata.get("download_tracking_url")
        if not self._access_key:
            raise ProviderAuthError(self.provider_id, "Unsplash Access Key is not configured")
        expected_path = f"/photos/{candidate.source.provider_asset_id}/download"
        if not self._valid_download_location(tracking_url) or urlsplit(tracking_url).path != expected_path:
            raise ProviderUnsupportedError(self.provider_id, "Unsplash download tracking URL is invalid")
        self._get(tracking_url)

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
                url,
                headers={
                    "Authorization": f"Client-ID {self._access_key}",
                    "Accept-Version": "v1",
                    "Accept": "application/json",
                },
                timeout=self._timeout,
            )
        except Exception as exc:
            raise self._fail(ProviderNetworkError(self.provider_id, "Unsplash API request failed")) from exc
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
        headers = normalized_headers(response.headers)
        try:
            self._quota_remaining = int(headers["x-ratelimit-remaining"])
        except (KeyError, ValueError):
            self._quota_remaining = None
        self._last_success_at = datetime.now(timezone.utc)
        self._last_error = None

    def _object(self, response: HttpResponse) -> dict:
        try:
            payload = decode_json(response)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderInvalidResponseError(self.provider_id, "Unsplash API returned malformed JSON") from exc
        if not isinstance(payload, dict):
            raise ProviderInvalidResponseError(self.provider_id, "Unsplash API returned a non-object response")
        return payload

    def _candidate(self, item: object, need_id: str) -> SupplyCandidate:
        if not isinstance(item, dict):
            raise ProviderInvalidResponseError(self.provider_id, "Unsplash photo record is malformed")
        photo_id = item.get("id")
        urls, links, user = item.get("urls"), item.get("links"), item.get("user")
        if not isinstance(photo_id, str) or not photo_id or not all(isinstance(v, dict) for v in (urls, links, user)):
            raise ProviderInvalidResponseError(self.provider_id, "Unsplash photo record is missing identity or links")
        image_url = safe_https_url(urls.get("small")) or safe_https_url(urls.get("thumb"))
        download_location = links.get("download_location")
        if not self._valid_download_location(download_location):
            raise ProviderInvalidResponseError(self.provider_id, "Unsplash download_location is invalid")
        profile = self._with_referral(safe_https_url(user.get("links", {}).get("html")) if isinstance(user.get("links"), dict) else None)
        photo_page = self._with_referral(safe_https_url(links.get("html")))
        creator = user.get("name")
        metadata: dict[str, object] = {
            "attribution_required": True,
            "attribution_provider": "Unsplash",
            "attribution_provider_url": self._with_referral("https://unsplash.com"),
            "download_tracking_url": download_location,
        }
        if isinstance(creator, str) and creator.strip():
            metadata["creator_name"] = creator.strip()
        if profile:
            metadata["creator_profile_url"] = profile
        description = item.get("alt_description") or item.get("description")
        if isinstance(description, str) and description.strip():
            metadata["description"] = description.strip()
        width, height = item.get("width"), item.get("height")
        if isinstance(width, int) and not isinstance(width, bool) and width > 0:
            metadata["width"] = width
        if isinstance(height, int) and not isinstance(height, bool) and height > 0:
            metadata["height"] = height
        return SupplyCandidate(
            candidate_id=f"unsplash:{photo_id}",
            need_id=need_id,
            media_type=MediaType.IMAGE,
            source=CandidateSource(
                kind="stock", provider=self.provider_id, provider_asset_id=photo_id,
                source_page=photo_page, creator=creator.strip() if isinstance(creator, str) and creator.strip() else None,
            ),
            preview=PreviewInfo(url=image_url) if image_url else None,
            availability=Availability.PREVIEWABLE if image_url else Availability.DISCOVERED,
            rights_hint=RightsHint(status=RightsStatus.UNKNOWN),
            metadata=metadata,
        )

    def _continuation(self, intent: RetrievalIntent, continuation: ProviderContinuation | None) -> tuple[int, int]:
        if continuation is None:
            return 0, 1
        if continuation.provider_id != self.provider_id or continuation.mode is not PaginationMode.PAGE:
            raise ProviderUnsupportedError(self.provider_id, "Continuation does not belong to UnsplashProvider")
        state = parse_continuation_token(continuation.token, intent)
        if state is None:
            raise ProviderUnsupportedError(self.provider_id, "Unsplash continuation is invalid for this search")
        return state

    @staticmethod
    def _with_referral(url: str | None) -> str | None:
        if not url:
            return None
        parts = urlsplit(url)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query.update({"utm_source": _APP_NAME, "utm_medium": "referral"})
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))

    @staticmethod
    def _valid_download_location(value: object) -> bool:
        if not isinstance(value, str) or not safe_https_url(value):
            return False
        parts = urlsplit(value)
        return parts.hostname == "api.unsplash.com" and parts.path.startswith("/photos/") and parts.path.endswith("/download")

    @staticmethod
    def _retry_after(headers: dict[str, str]) -> float | None:
        try:
            return max(0.0, float(headers["retry-after"]))
        except (KeyError, ValueError):
            return None


__all__ = ["UnsplashProvider"]
