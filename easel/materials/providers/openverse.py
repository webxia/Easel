"""Openverse API adapter with per-item license facts and safe media admission."""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from threading import Lock
from urllib.parse import urlencode, urlsplit

from easel.materials.domain import (
    Availability,
    AcquisitionInfo,
    CandidateSource,
    MediaType,
    RetrievalIntent,
    RightsStatus,
    SupplyCandidate,
)
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


_API_ROOT = "https://api.openverse.org/v1"
_TOKEN_URL = f"{_API_ROOT}/auth_tokens/token/"
_PAGE_SIZE = 20  # Openverse API default; stays within every documented tier.
_LICENSE_ID_RE = re.compile(r"^[a-z0-9,-]{1,120}$")
_PUBLIC_DOMAIN_LICENSES = {"cc0", "pdm"}
_SIMPLE_ATTRIBUTION_LICENSES = {"by"}


class OpenverseProvider:
    """Search Openverse images/audio; discovery does not authorize Easel acquisition."""

    provider_id = "openverse"

    def __init__(
        self,
        access_token: str = "",
        *,
        client_id: str = "",
        client_secret: str = "",
        transport: HttpTransport | None = None,
        timeout: float = 20.0,
        clock=time.monotonic,
    ):
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self._access_token = access_token.strip()
        self._client_id = client_id.strip()
        self._client_secret = client_secret.strip()
        self._transport = transport or UrllibTransport()
        self._timeout = timeout
        self._clock = clock
        self._token_refresh_at = 0.0
        self._token_lock = Lock()
        self._last_success_at: datetime | None = None
        self._quota_remaining: int | None = None
        self._last_error: tuple[str, str, bool, float | None] | None = None

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            provider_id=self.provider_id,
            display_name="Openverse",
            media_types=(MediaType.IMAGE, MediaType.AUDIO),
            access_mode=AccessMode.DISCOVERY_ONLY,
            capabilities=(
                ProviderCapability.SEARCH,
                ProviderCapability.PREVIEW,
                ProviderCapability.DETAIL,
                ProviderCapability.RIGHTS_METADATA,
                ProviderCapability.ATTRIBUTION_METADATA,
                ProviderCapability.PAGINATION,
                ProviderCapability.HEALTH_CHECK,
            ),
            pagination_mode=PaginationMode.PAGE,
            auth_mode="OAuth2 client credentials with in-memory Bearer refresh; static bearer token remains supported",
            quota_policy="Tier and page-size limits depend on authentication; honor current API response rate-limit and Retry-After headers.",
            cache_policy="No client-side response cache configured; re-query rather than persisting expiring or stale media URLs.",
            attribution_policy="Normalize the item license, license URL, creator, source landing page, and attribution text separately for every result.",
            acquisition_policy="DISCOVERY_ONLY: preserve Openverse item URLs and license facts for review; the Easel Acquirer does not fetch Openverse media.",
        )

    def search(self, intent: RetrievalIntent, continuation: ProviderContinuation | None = None) -> ProviderPage:
        try:
            media_type = MediaType(intent.filters["media_type"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderUnsupportedError(self.provider_id, "Openverse search requires a supported media_type") from exc
        if media_type not in {MediaType.IMAGE, MediaType.AUDIO}:
            raise ProviderUnsupportedError(self.provider_id, "Openverse supports image and audio search only")
        query_index, page = self._continuation(intent, continuation)
        query = intent.semantic_queries[query_index]
        if len(query) > 200:
            raise ProviderUnsupportedError(self.provider_id, "Openverse query must not exceed 200 characters")
        params: dict[str, str | int] = {"q": query, "page": page, "page_size": _PAGE_SIZE}
        license_filter = intent.filters.get("license")
        if isinstance(license_filter, str) and _LICENSE_ID_RE.fullmatch(license_filter):
            params["license"] = license_filter
        path = "images" if media_type is MediaType.IMAGE else "audio"
        response = self._get(f"{_API_ROOT}/{path}/?{urlencode(params)}")
        payload = self._object(response)
        results = payload.get("results")
        if not isinstance(results, list):
            raise ProviderInvalidResponseError(self.provider_id, "Openverse response is missing results")
        candidates = tuple(self._candidate(item, intent.need_id, media_type) for item in results)
        page_count = payload.get("page_count")
        if not isinstance(page_count, int) or isinstance(page_count, bool) or page_count < 0:
            raise ProviderInvalidResponseError(self.provider_id, "Openverse page_count is invalid")
        next_state = (query_index, page + 1) if page < page_count else (
            (query_index + 1, 1) if query_index + 1 < len(intent.semantic_queries) else None
        )
        continuation_out = (
            ProviderContinuation(
                provider_id=self.provider_id, mode=PaginationMode.PAGE,
                token=continuation_token(intent, *next_state),
            ) if next_state else None
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
        token = self._get_access_token()
        for attempt in range(2):
            headers = {"Accept": "application/json"}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            try:
                response = self._transport.get(url, headers=headers, timeout=self._timeout)
            except Exception as exc:
                raise self._fail(ProviderNetworkError(self.provider_id, "Openverse API request failed")) from exc
            normalized = normalized_headers(response.headers)
            if response.status_code == 200:
                return response
            error = classify_http_error(
                self.provider_id, response.status_code, response.headers, response.body,
                retry_after_seconds=self._retry_after(normalized),
            )
            if isinstance(error, ProviderAuthError) and self._has_oauth_pair and attempt == 0:
                token = self._refresh_rejected_token(token)
                continue
            raise self._fail(error)
        raise self._fail(ProviderAuthError(self.provider_id, "Openverse API rejected refreshed credentials"))

    @property
    def _has_oauth_pair(self) -> bool:
        return bool(self._client_id and self._client_secret)

    def _get_access_token(self) -> str:
        if bool(self._client_id) != bool(self._client_secret):
            raise self._fail(ProviderAuthError(self.provider_id, "Openverse OAuth client ID and secret must be configured together"))
        if not self._has_oauth_pair:
            return self._access_token
        with self._token_lock:
            if self._access_token and self._clock() < self._token_refresh_at:
                return self._access_token
            self._fetch_access_token_locked()
            return self._access_token

    def _refresh_rejected_token(self, rejected_token: str) -> str:
        with self._token_lock:
            if self._access_token == rejected_token:
                self._token_refresh_at = 0.0
            if not self._access_token or self._clock() >= self._token_refresh_at:
                self._fetch_access_token_locked()
            return self._access_token

    def _fetch_access_token_locked(self) -> None:
        post = getattr(self._transport, "post", None)
        if not callable(post):
            raise self._fail(ProviderNetworkError(self.provider_id, "Openverse OAuth transport does not support token requests"))
        body = urlencode({
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }).encode("utf-8")
        try:
            response = post(
                _TOKEN_URL,
                headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
                body=body,
                timeout=self._timeout,
            )
        except Exception as exc:
            raise self._fail(ProviderNetworkError(self.provider_id, "Openverse OAuth token request failed")) from exc
        headers = normalized_headers(response.headers)
        if response.status_code != 200:
            raise self._fail(classify_http_error(
                self.provider_id, response.status_code, response.headers, response.body,
                retry_after_seconds=self._retry_after(headers),
            ))
        try:
            payload = decode_json(response)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise self._fail(ProviderInvalidResponseError(self.provider_id, "Openverse OAuth token response was malformed")) from exc
        if not isinstance(payload, dict):
            raise self._fail(ProviderInvalidResponseError(self.provider_id, "Openverse OAuth token response was not an object"))
        token = payload.get("access_token")
        token_type = payload.get("token_type")
        expires_in = payload.get("expires_in")
        if (not isinstance(token, str) or not token.strip()
                or not isinstance(token_type, str) or token_type.casefold() != "bearer"
                or not isinstance(expires_in, (int, float)) or isinstance(expires_in, bool) or expires_in <= 0):
            raise self._fail(ProviderInvalidResponseError(self.provider_id, "Openverse OAuth token response is missing valid Bearer token expiry fields"))
        self._access_token = token.strip()
        # Refresh at least 10% or 60 seconds before provider expiry, whichever is smaller.
        refresh_lead = min(60.0, float(expires_in) * 0.1)
        self._token_refresh_at = self._clock() + max(0.0, float(expires_in) - refresh_lead)

    def _fail(self, error):
        self._last_error = (error.category.value, error.message, error.retryable, error.retry_after_seconds)
        return error

    def _record_success(self, response: HttpResponse) -> None:
        headers = normalized_headers(response.headers)
        for name in ("x-ratelimit-remaining", "ratelimit-remaining"):
            try:
                self._quota_remaining = int(headers[name])
                break
            except (KeyError, ValueError):
                self._quota_remaining = None
        self._last_success_at = datetime.now(timezone.utc)
        self._last_error = None

    def _object(self, response: HttpResponse) -> dict:
        try:
            payload = decode_json(response)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderInvalidResponseError(self.provider_id, "Openverse API returned malformed JSON") from exc
        if not isinstance(payload, dict):
            raise ProviderInvalidResponseError(self.provider_id, "Openverse API returned a non-object response")
        return payload

    def _candidate(self, item: object, need_id: str, media_type: MediaType) -> SupplyCandidate:
        if not isinstance(item, dict):
            raise ProviderInvalidResponseError(self.provider_id, "Openverse media record is malformed")
        native_id = item.get("id")
        if not isinstance(native_id, str) or not native_id.strip():
            raise ProviderInvalidResponseError(self.provider_id, "Openverse media record is missing identity")
        media_url = safe_https_url(item.get("url"))
        thumbnail = safe_https_url(item.get("thumbnail"))
        landing_url = safe_https_url(item.get("foreign_landing_url")) or safe_https_url(item.get("detail_url"))
        creator = item.get("creator")
        license_id = item.get("license")
        license_version = item.get("license_version")
        license_url = safe_https_url(item.get("license_url"))
        attribution = item.get("attribution")
        if license_id is not None and not isinstance(license_id, str):
            raise ProviderInvalidResponseError(self.provider_id, "Openverse item license value is malformed")
        status, attribution_required = self._rights_hint(license_id)
        tags = item.get("tags")
        if tags is not None and (not isinstance(tags, list) or any(not isinstance(tag, dict) for tag in tags)):
            raise ProviderInvalidResponseError(self.provider_id, "Openverse item tags are malformed")
        metadata: dict[str, object] = {
            "rights_fact_source": "openverse_item_license",
            "license_id": license_id or "",
            "license_version": license_version if isinstance(license_version, str) else "",
            "license_url": license_url or "",
            "attribution": attribution.strip() if isinstance(attribution, str) else "",
            "provider_source": item.get("source", "") if isinstance(item.get("source"), str) else "",
            "provider_name": item.get("provider", "") if isinstance(item.get("provider"), str) else "",
        }
        title = item.get("title")
        if isinstance(title, str) and title.strip():
            metadata["title"] = title.strip()
        if isinstance(creator, str) and creator.strip():
            metadata["creator_name"] = creator.strip()
        creator_url = safe_https_url(item.get("creator_url"))
        if creator_url:
            metadata["creator_url"] = creator_url
        if tags:
            metadata["tags"] = tuple(
                tag["name"].strip() for tag in tags if isinstance(tag.get("name"), str) and tag["name"].strip()
            )
        filetype = item.get("filetype")
        if isinstance(filetype, str) and filetype.strip():
            metadata["file_type"] = filetype.strip()
        filesize = item.get("filesize")
        if isinstance(filesize, int) and not isinstance(filesize, bool) and filesize >= 0:
            metadata["file_size"] = filesize
        for key in ("width", "height", "duration"):
            value = item.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
                metadata["duration_seconds" if key == "duration" else key] = value
        acquisition = self._audio_acquisition(media_type, media_url, landing_url, license_id)
        return SupplyCandidate(
            candidate_id=f"openverse:{media_type.value}:{native_id}",
            need_id=need_id,
            media_type=media_type,
            source=CandidateSource(
                kind="open_license_index", provider=self.provider_id, provider_asset_id=native_id,
                source_page=landing_url, creator=creator.strip() if isinstance(creator, str) and creator.strip() else None,
            ),
            preview=PreviewInfo(url=thumbnail) if thumbnail else None,
            availability=Availability.DIRECT_DOWNLOADABLE if acquisition else (
                Availability.PREVIEWABLE if thumbnail else Availability.DISCOVERED),
            rights_hint=RightsHint(
                status=status,
                license_name=f"{license_id} {license_version}".strip() if license_id else None,
                license_url=license_url,
                attribution_required=attribution_required,
            ),
            metadata=metadata,
            acquisition=acquisition,
        )

    def _audio_acquisition(
        self, media_type: MediaType, media_url: str | None,
        landing_url: str | None, license_id: str | None,
    ) -> AcquisitionInfo | None:
        # The base Openverse adapter remains discovery-only. A separate audio
        # route opts into acquisition for the two reviewed source CDNs.
        if not getattr(self, "_acquirable_audio", False) or media_type is not MediaType.AUDIO:
            return None
        if not media_url or not landing_url or (license_id or "").casefold() not in {"cc0", "by"}:
            return None
        if (urlsplit(media_url).hostname or "").lower() not in {
            "cdn.freesound.org", "upload.wikimedia.org",
        }:
            return None
        return AcquisitionInfo(mode="provider_direct_url", locator=media_url)

    @staticmethod
    def _rights_hint(license_id: str | None) -> tuple[RightsStatus, bool | None]:
        if not license_id:
            return RightsStatus.UNKNOWN, None
        normalized = license_id.casefold().strip()
        if normalized in _PUBLIC_DOMAIN_LICENSES:
            return RightsStatus.PUBLIC_DOMAIN, False
        if normalized in _SIMPLE_ATTRIBUTION_LICENSES:
            return RightsStatus.ATTRIBUTION_REQUIRED, True
        # The current RightsInfo contract cannot encode NC/ND/SA obligations
        # safely. Preserve the exact item license facts, but require review.
        if normalized in {"by-nc", "by-nc-sa", "by-nc-nd", "by-nd", "by-sa", "sampling+", "other"}:
            return RightsStatus.UNKNOWN, None
        return RightsStatus.UNKNOWN, None

    def _continuation(self, intent: RetrievalIntent, continuation: ProviderContinuation | None) -> tuple[int, int]:
        if continuation is None:
            return 0, 1
        if continuation.provider_id != self.provider_id or continuation.mode is not PaginationMode.PAGE:
            raise ProviderUnsupportedError(self.provider_id, "Continuation does not belong to OpenverseProvider")
        state = parse_continuation_token(continuation.token, intent)
        if state is None:
            raise ProviderUnsupportedError(self.provider_id, "Openverse continuation is invalid for this search")
        return state

    @staticmethod
    def _retry_after(headers: dict[str, str]) -> float | None:
        try:
            return max(0.0, float(headers["retry-after"]))
        except (KeyError, ValueError):
            return None


class OpenverseAudioProvider(OpenverseProvider):
    """Bounded Openverse audio acquisition; image discovery remains unchanged."""

    provider_id = "openverse_audio"
    _acquirable_audio = True

    def search(self, intent: RetrievalIntent, continuation: ProviderContinuation | None = None) -> ProviderPage:
        # This route has acquisition support only for licenses the current
        # Rights contract can represent; keep other licenses on the base
        # discovery-only adapter.
        filters = {**intent.filters, "license": "cc0,by"}
        return super().search(intent.model_copy(update={"filters": filters}), continuation)

    def info(self) -> ProviderInfo:
        base = super().info()
        return base.model_copy(update={
            "provider_id": self.provider_id,
            "display_name": "Openverse Audio",
            "media_types": (MediaType.AUDIO,),
            "access_mode": AccessMode.PUBLIC_API,
            "capabilities": (*base.capabilities, ProviderCapability.DIRECT_DOWNLOAD),
            "acquisition_policy": "Only CC0/CC-BY audio on cdn.freesound.org or upload.wikimedia.org; source-page Rights review remains required.",
        })


__all__ = ["OpenverseProvider", "OpenverseAudioProvider"]
