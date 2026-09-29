"""Official Pixabay image and video discovery adapter."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.parse import urlencode

from easel.materials.domain import Availability, CandidateSource, MediaType, RetrievalIntent, SupplyCandidate
from easel.materials.domain.models import AcquisitionInfo, PreviewInfo, RightsHint, RightsStatus
from easel.materials.providers.base import ProviderPage
from easel.materials.providers.errors import (
    ProviderAuthError,
    ProviderError,
    classify_http_error,
    ProviderInvalidResponseError,
    ProviderNetworkError,
    ProviderRateLimitError,
    ProviderTemporaryError,
    ProviderUnsupportedError,
)
from easel.materials.providers.http_support import (
    HttpResponse,
    HttpTransport,
    FileTTLResponseCache,
    ResponseCache,
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
)
from easel.materials.providers.models import ProviderInfo


_API_ROOT = "https://pixabay.com/api"
_PAGE_SIZE = 20  # Official range is 3-200; the API exposes at most 500 hits/query.
_MAX_QUERY_HITS = 500
_DEFAULT_CACHE = FileTTLResponseCache(ttl_seconds=86_400)


class PixabayProvider:
    """Search Pixabay API; cache successful response pages and do not acquire media."""

    provider_id = "pixabay"

    def __init__(
        self,
        api_key: str = "",
        *,
        transport: HttpTransport | None = None,
        response_cache: ResponseCache | None = None,
        timeout: float = 20.0,
    ):
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self._api_key = api_key.strip()
        self._transport = transport or UrllibTransport()
        self._cache = response_cache or _DEFAULT_CACHE
        self._timeout = timeout
        self._quota_remaining: int | None = None
        self._retry_after: float | None = None
        self._last_success_at: datetime | None = None
        self._last_error: tuple[str, str, bool, float | None] | None = None

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            provider_id=self.provider_id,
            display_name="Pixabay",
            media_types=(MediaType.IMAGE, MediaType.VIDEO),
            access_mode=AccessMode.OFFICIAL_API,
            capabilities=(
                ProviderCapability.SEARCH,
                ProviderCapability.PREVIEW,
                ProviderCapability.ATTRIBUTION_METADATA,
                ProviderCapability.DIRECT_DOWNLOAD,
                ProviderCapability.PAGINATION,
                ProviderCapability.HEALTH_CHECK,
            ),
            pagination_mode=PaginationMode.PAGE,
            auth_mode="Pixabay API key query parameter; never included in candidate metadata or errors",
            quota_policy="Default quota: 100 requests per 60 seconds; observe X-RateLimit headers and Retry-After.",
            cache_policy="Successful search response pages are cached on local disk for 24 hours as required by Pixabay API terms.",
            attribution_policy="Show a clear Pixabay source link whenever API results are displayed; creator credit is appreciated, not required.",
            acquisition_policy="Image URLs are temporary preview/API URLs and must not be permanently hotlinked; store used media locally. No acquisition is performed here.",
        )

    def search(
        self,
        intent: RetrievalIntent,
        continuation: ProviderContinuation | None = None,
    ) -> ProviderPage:
        if not self._api_key:
            raise ProviderAuthError(self.provider_id, "Pixabay API key is not configured")
        media_type = self._media_type(intent)
        query_index, page = self._continuation_state(intent, continuation)
        query = intent.semantic_queries[query_index]
        if len(query) > 100:
            raise ProviderUnsupportedError(self.provider_id, "Pixabay query must not exceed 100 characters")
        endpoint = "/videos/" if media_type is MediaType.VIDEO else "/"
        params: dict[str, str | int | bool] = {
            "key": self._api_key,
            "q": query,
            "page": page,
            "per_page": _PAGE_SIZE,
            "safesearch": "true",
        }
        self._map_filters(intent, params)
        url = f"{_API_ROOT}{endpoint}?{urlencode(params)}"
        try:
            response = self._cache.get_or_fetch(url, lambda: self._get(url))
        except ProviderError:
            raise
        except Exception as exc:
            self._raise_recorded(ProviderTemporaryError(self.provider_id, "Pixabay response cache is unavailable"))
            raise AssertionError("unreachable") from exc
        payload = self._json_object(response)
        hits = payload.get("hits")
        if not isinstance(hits, list):
            raise ProviderInvalidResponseError(self.provider_id, "Pixabay API response is missing hits")
        candidates = (
            self._video_candidates(hits, intent.need_id)
            if media_type is MediaType.VIDEO
            else self._image_candidates(hits, intent.need_id)
        )
        total_hits = self._total_hits(payload)
        self._record_success(response)
        has_more = page * _PAGE_SIZE < min(total_hits, _MAX_QUERY_HITS) and bool(hits)

        next_state: tuple[int, int] | None = None
        if has_more:
            next_state = (query_index, page + 1)
        elif query_index + 1 < len(intent.semantic_queries):
            next_state = (query_index + 1, 1)
        next_continuation = (
            ProviderContinuation(
                provider_id=self.provider_id,
                mode=PaginationMode.PAGE,
                token=continuation_token(intent, *next_state),
            )
            if next_state is not None
            else None
        )
        return ProviderPage(candidates=tuple(candidates), continuation=next_continuation)

    def health(self) -> ProviderHealth:
        if self._last_error is not None:
            from easel.materials.providers.models import ProviderFailureRecord

            category, message, retryable, retry_after = self._last_error
            return ProviderHealth(
                provider_id=self.provider_id,
                status=ProviderHealthStatus.DEGRADED,
                last_success_at=self._last_success_at,
                last_error=ProviderFailureRecord(
                    provider_id=self.provider_id,
                    category=category,
                    message=message,
                    retryable=retryable,
                    retry_after_seconds=retry_after,
                ),
                quota_remaining=self._quota_remaining,
                retry_after_seconds=self._retry_after,
                degraded_reason=message,
            )
        status = ProviderHealthStatus.HEALTHY if self._last_success_at else ProviderHealthStatus.UNKNOWN
        return ProviderHealth(
            provider_id=self.provider_id,
            status=status,
            last_success_at=self._last_success_at,
            quota_remaining=self._quota_remaining,
            retry_after_seconds=self._retry_after,
        )

    @staticmethod
    def _media_type(intent: RetrievalIntent) -> MediaType:
        try:
            media_type = MediaType(intent.filters["media_type"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderUnsupportedError("pixabay", "Search requires a supported media_type") from exc
        if media_type not in (MediaType.IMAGE, MediaType.VIDEO):
            raise ProviderUnsupportedError("pixabay", f"Pixabay does not support media_type={media_type.value}")
        return media_type

    def _continuation_state(
        self, intent: RetrievalIntent, continuation: ProviderContinuation | None
    ) -> tuple[int, int]:
        if continuation is None:
            return 0, 1
        if continuation.provider_id != self.provider_id or continuation.mode is not PaginationMode.PAGE:
            raise ProviderUnsupportedError(self.provider_id, "Continuation does not belong to PixabayProvider")
        state = parse_continuation_token(continuation.token, intent)
        if state is None:
            raise ProviderUnsupportedError(self.provider_id, "Pixabay continuation is invalid for this search")
        return state

    @staticmethod
    def _map_filters(intent: RetrievalIntent, params: dict[str, str | int | bool]) -> None:
        orientation = intent.filters.get("orientation")
        if orientation == "landscape":
            params["orientation"] = "horizontal"
        elif orientation == "portrait":
            params["orientation"] = "vertical"
        min_width = intent.filters.get("min_width")
        min_height = intent.filters.get("min_height")
        if isinstance(min_width, int) and not isinstance(min_width, bool) and min_width >= 0:
            params["min_width"] = min_width
        if isinstance(min_height, int) and not isinstance(min_height, bool) and min_height >= 0:
            params["min_height"] = min_height
        order = intent.filters.get("order")
        if order in ("popular", "latest"):
            params["order"] = str(order)
        category = intent.filters.get("category")
        if isinstance(category, str) and category.strip():
            params["category"] = category.strip()

    def _get(self, url: str) -> HttpResponse:
        try:
            response = self._transport.get(
                url,
                headers={"Accept": "application/json"},
                timeout=self._timeout,
            )
        except Exception as exc:
            self._raise_recorded(ProviderNetworkError(self.provider_id, "Pixabay API request failed"))
            raise AssertionError("unreachable") from exc
        headers = normalized_headers(response.headers)
        if response.status_code == 200:
            return response
        error = classify_http_error(
            self.provider_id, response.status_code, response.headers, response.body,
            retry_after_seconds=self._retry_after_from_headers(headers),
        )
        self._raise_recorded(error)
        raise AssertionError("unreachable")

    def _raise_recorded(self, error) -> None:
        self._last_error = (
            error.category.value,
            error.message,
            error.retryable,
            error.retry_after_seconds,
        )
        self._retry_after = error.retry_after_seconds
        raise error

    def _record_success(self, response: HttpResponse) -> None:
        # Cached quota headers describe the past API window and must not be
        # presented as current Provider health information.
        if response.from_cache:
            return
        headers = normalized_headers(response.headers)
        try:
            self._quota_remaining = int(headers["x-ratelimit-remaining"])
        except (KeyError, ValueError):
            self._quota_remaining = None
        try:
            self._retry_after = max(0.0, float(headers["x-ratelimit-reset"]))
        except (KeyError, ValueError):
            self._retry_after = None
        self._last_success_at = datetime.now(timezone.utc)
        self._last_error = None

    @staticmethod
    def _retry_after_from_headers(headers: dict[str, str]) -> float | None:
        try:
            return max(0.0, float(headers["retry-after"]))
        except (KeyError, ValueError):
            return None

    def _json_object(self, response: HttpResponse) -> dict:
        try:
            payload = decode_json(response)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderInvalidResponseError(self.provider_id, "Pixabay API returned malformed JSON") from exc
        if not isinstance(payload, dict):
            raise ProviderInvalidResponseError(self.provider_id, "Pixabay API returned a non-object response")
        return payload

    @staticmethod
    def _total_hits(payload: dict) -> int:
        total_hits = payload.get("totalHits", payload.get("total"))
        if not isinstance(total_hits, int) or isinstance(total_hits, bool) or total_hits < 0:
            raise ProviderInvalidResponseError("pixabay", "Pixabay API returned an invalid result count")
        return min(total_hits, _MAX_QUERY_HITS)

    def _image_candidates(self, hits: list, need_id: str) -> list[SupplyCandidate]:
        candidates: list[SupplyCandidate] = []
        for item in hits:
            if not isinstance(item, dict):
                raise ProviderInvalidResponseError(self.provider_id, "Pixabay image record is malformed")
            asset_id = item.get("id")
            source_page = safe_https_url(item.get("pageURL"))
            if not isinstance(asset_id, (str, int)) or not source_page:
                raise ProviderInvalidResponseError(self.provider_id, "Pixabay image record is missing identity or source")
            preview_url = safe_https_url(item.get("previewURL")) or safe_https_url(item.get("webformatURL"))
            direct_url = (
                safe_https_url(item.get("imageURL"))
                or safe_https_url(item.get("fullHDURL"))
                or safe_https_url(item.get("largeImageURL"))
                or safe_https_url(item.get("webformatURL"))
            )
            creator = item.get("user")
            tags = item.get("tags")
            width = self._optional_positive_int(item.get("imageWidth"))
            height = self._optional_positive_int(item.get("imageHeight"))
            candidates.append(
                SupplyCandidate(
                    candidate_id=f"pixabay:{asset_id}",
                    need_id=need_id,
                    media_type=MediaType.IMAGE,
                    source=CandidateSource(
                        kind="stock",
                        provider=self.provider_id,
                        provider_asset_id=str(asset_id),
                        source_page=source_page,
                        creator=creator.strip() if isinstance(creator, str) and creator.strip() else None,
                    ),
                    preview=PreviewInfo(url=preview_url) if preview_url else None,
                    availability=Availability.DIRECT_DOWNLOADABLE if direct_url else Availability.PREVIEWABLE if preview_url else Availability.DISCOVERED,
                    rights_hint=RightsHint(
                        status=RightsStatus.KNOWN,
                        license_name="Pixabay Content License",
                        license_url="https://pixabay.com/service/terms/",
                        attribution_required=False,
                        usage_constraints=("no_standalone_distribution", "recognizable_trademark_noncommercial_restriction",
                                           "no_misleading_use", "no_immoral_or_illegal_use", "no_trademark_use",
                                           "third_party_rights_may_apply"),
                    ),
                    metadata={
                        **({"tags": tags.strip()} if isinstance(tags, str) and tags.strip() else {}),
                        **({"width": width} if width else {}),
                        **({"height": height} if height else {}),
                    },
                    acquisition=AcquisitionInfo(mode="provider_direct_url", locator=direct_url, media_format="image") if direct_url else None,
                )
            )
        return candidates

    def _video_candidates(self, hits: list, need_id: str) -> list[SupplyCandidate]:
        candidates: list[SupplyCandidate] = []
        for item in hits:
            if not isinstance(item, dict):
                raise ProviderInvalidResponseError(self.provider_id, "Pixabay video record is malformed")
            asset_id = item.get("id")
            source_page = safe_https_url(item.get("pageURL"))
            renditions = item.get("videos")
            if not isinstance(asset_id, (str, int)) or not source_page or not isinstance(renditions, dict):
                raise ProviderInvalidResponseError(self.provider_id, "Pixabay video record is missing identity or renditions")
            # The official API documents medium as available for all video hits.
            # Preserve its rendition as a descriptor; do not download or transcode it.
            selected = renditions.get("medium")
            if not isinstance(selected, dict) or not safe_https_url(selected.get("url")):
                selected = next(
                    (
                        renditions.get(key)
                        for key in ("small", "tiny", "large")
                        if isinstance(renditions.get(key), dict) and safe_https_url(renditions[key].get("url"))
                    ),
                    None,
                )
            direct_url = safe_https_url(selected.get("url")) if isinstance(selected, dict) else None
            preview_url = safe_https_url(selected.get("thumbnail")) if isinstance(selected, dict) else None
            duration = self._optional_positive_int(item.get("duration"))
            width = self._optional_positive_int(selected.get("width")) if isinstance(selected, dict) else None
            height = self._optional_positive_int(selected.get("height")) if isinstance(selected, dict) else None
            creator = item.get("user")
            tags = item.get("tags")
            candidates.append(
                SupplyCandidate(
                    candidate_id=f"pixabay:{asset_id}",
                    need_id=need_id,
                    media_type=MediaType.VIDEO,
                    source=CandidateSource(
                        kind="stock",
                        provider=self.provider_id,
                        provider_asset_id=str(asset_id),
                        source_page=source_page,
                        creator=creator.strip() if isinstance(creator, str) and creator.strip() else None,
                    ),
                    preview=PreviewInfo(url=preview_url) if preview_url else None,
                    availability=Availability.DIRECT_DOWNLOADABLE if direct_url else Availability.DISCOVERED,
                    rights_hint=RightsHint(
                        status=RightsStatus.KNOWN,
                        license_name="Pixabay Content License",
                        license_url="https://pixabay.com/service/terms/",
                        attribution_required=False,
                        usage_constraints=("no_standalone_distribution", "recognizable_trademark_noncommercial_restriction",
                                           "no_misleading_use", "no_immoral_or_illegal_use", "no_trademark_use",
                                           "third_party_rights_may_apply"),
                    ),
                    metadata={
                        **({"tags": tags.strip()} if isinstance(tags, str) and tags.strip() else {}),
                        **({"duration_seconds": duration} if duration else {}),
                        **({"width": width} if width else {}),
                        **({"height": height} if height else {}),
                    },
                    acquisition=AcquisitionInfo(mode="provider_direct_url", locator=direct_url, media_format="video/mp4") if direct_url else None,
                )
            )
        return candidates

    @staticmethod
    def _optional_positive_int(value: object) -> int | None:
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return value
        return None
