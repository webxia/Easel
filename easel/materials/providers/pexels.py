"""Official Pexels photo and video discovery adapter."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.parse import urlencode

from easel.materials.domain import Availability, CandidateSource, MediaType, RetrievalIntent, SupplyCandidate
from easel.materials.domain.models import AcquisitionInfo, PreviewInfo, RightsHint, RightsStatus
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


_API_ROOT = "https://api.pexels.com/v1"
_PAGE_SIZE = 20  # Official API maximum is 80.


class PexelsProvider:
    """Search Pexels API v1; does not acquire media or certify rights."""

    provider_id = "pexels"

    def __init__(self, api_key: str = "", *, transport: HttpTransport | None = None, timeout: float = 20.0):
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self._api_key = api_key.strip()
        self._transport = transport or UrllibTransport()
        self._timeout = timeout
        self._quota_remaining: int | None = None
        self._last_success_at: datetime | None = None
        self._last_error: tuple[str, str, bool, float | None] | None = None

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            provider_id=self.provider_id,
            display_name="Pexels",
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
            auth_mode="Pexels API key in Authorization header",
            quota_policy="Default quota: 200 requests/hour and 20,000/month; successful responses expose X-Ratelimit headers.",
            cache_policy="No mandatory minimum response-cache duration identified in current API documentation.",
            attribution_policy="Prominently link to Pexels for API usage/results; credit the creator when possible.",
            acquisition_policy="Discovery only; any returned media URL is a descriptor, not an acquisition or rights decision.",
        )

    def search(
        self,
        intent: RetrievalIntent,
        continuation: ProviderContinuation | None = None,
    ) -> ProviderPage:
        if not self._api_key:
            raise ProviderAuthError(self.provider_id, "Pexels API key is not configured")
        media_type = self._media_type(intent)
        query_index, page = self._continuation_state(intent, continuation)
        query = intent.semantic_queries[query_index]
        endpoint = "/videos/search" if media_type is MediaType.VIDEO else "/search"
        params: dict[str, str | int] = {"query": query, "page": page, "per_page": _PAGE_SIZE}
        self._map_filters(intent, media_type, params)
        url = f"{_API_ROOT}{endpoint}?{urlencode(params)}"
        response = self._get(url)
        payload = self._json_object(response)
        candidates = (
            self._video_candidates(payload, intent.need_id)
            if media_type is MediaType.VIDEO
            else self._image_candidates(payload, intent.need_id)
        )
        self._record_success(response)

        next_state: tuple[int, int] | None = None
        next_key = "next_page"
        next_page = payload.get(next_key)
        if next_page is not None:
            if not isinstance(next_page, str) or not safe_https_url(next_page):
                raise ProviderInvalidResponseError(self.provider_id, "Pexels pagination link is malformed")
            next_state = (query_index, page + 1)
        elif query_index + 1 < len(intent.semantic_queries):
            next_state = (query_index + 1, 1)

        next_continuation = None
        if next_state is not None:
            next_continuation = ProviderContinuation(
                provider_id=self.provider_id,
                mode=PaginationMode.PAGE,
                token=continuation_token(intent, *next_state),
            )
        return ProviderPage(candidates=tuple(candidates), continuation=next_continuation)

    def health(self) -> ProviderHealth:
        if self._last_error is not None:
            category, message, retryable, retry_after = self._last_error
            from easel.materials.providers.errors import ProviderErrorCategory, ProviderFailure

            last_error = ProviderFailure(
                provider_id=self.provider_id,
                category=ProviderErrorCategory(category),
                message=message,
                retryable=retryable,
                retry_after_seconds=retry_after,
            )
            from easel.materials.providers.models import ProviderFailureRecord

            return ProviderHealth(
                provider_id=self.provider_id,
                status=ProviderHealthStatus.DEGRADED,
                last_success_at=self._last_success_at,
                last_error=ProviderFailureRecord(
                    provider_id=last_error.provider_id,
                    category=last_error.category.value,
                    message=last_error.message,
                    retryable=last_error.retryable,
                    retry_after_seconds=last_error.retry_after_seconds,
                ),
                quota_remaining=self._quota_remaining,
                retry_after_seconds=retry_after,
                degraded_reason=message,
            )
        status = ProviderHealthStatus.HEALTHY if self._last_success_at else ProviderHealthStatus.UNKNOWN
        return ProviderHealth(
            provider_id=self.provider_id,
            status=status,
            last_success_at=self._last_success_at,
            quota_remaining=self._quota_remaining,
        )

    @staticmethod
    def _media_type(intent: RetrievalIntent) -> MediaType:
        try:
            media_type = MediaType(intent.filters["media_type"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderUnsupportedError("pexels", "Search requires a supported media_type") from exc
        if media_type not in (MediaType.IMAGE, MediaType.VIDEO):
            raise ProviderUnsupportedError("pexels", f"Pexels does not support media_type={media_type.value}")
        return media_type

    def _continuation_state(
        self, intent: RetrievalIntent, continuation: ProviderContinuation | None
    ) -> tuple[int, int]:
        if continuation is None:
            return 0, 1
        if continuation.provider_id != self.provider_id or continuation.mode is not PaginationMode.PAGE:
            raise ProviderUnsupportedError(self.provider_id, "Continuation does not belong to PexelsProvider")
        state = parse_continuation_token(continuation.token, intent)
        if state is None:
            raise ProviderUnsupportedError(self.provider_id, "Pexels continuation is invalid for this search")
        return state

    @staticmethod
    def _map_filters(
        intent: RetrievalIntent, media_type: MediaType, params: dict[str, str | int]
    ) -> None:
        orientation = intent.filters.get("orientation")
        if isinstance(orientation, str) and orientation in {"landscape", "portrait", "square"}:
            params["orientation"] = orientation
        locale = intent.filters.get("locale")
        if isinstance(locale, str) and locale:
            params["locale"] = locale
        size = intent.filters.get("size")
        if isinstance(size, str) and size in {"large", "medium", "small"}:
            params["size"] = size
        elif media_type is MediaType.VIDEO:
            minimum_height = intent.filters.get("min_height")
            if isinstance(minimum_height, (int, float)) and not isinstance(minimum_height, bool) and minimum_height > 0:
                params["size"] = "large" if minimum_height >= 2160 else "medium" if minimum_height >= 1080 else "small"

    def _get(self, url: str) -> HttpResponse:
        try:
            response = self._transport.get(
                url,
                headers={"Authorization": self._api_key, "Accept": "application/json"},
                timeout=self._timeout,
            )
        except Exception as exc:
            self._raise_recorded(ProviderNetworkError(self.provider_id, "Pexels API request failed"))
            raise AssertionError("unreachable") from exc
        headers = normalized_headers(response.headers)
        if response.status_code == 200:
            return response
        error = classify_http_error(
            self.provider_id, response.status_code, response.headers, response.body,
            retry_after_seconds=self._retry_after(headers),
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
        raise error

    def _record_success(self, response: HttpResponse) -> None:
        headers = normalized_headers(response.headers)
        try:
            self._quota_remaining = int(headers["x-ratelimit-remaining"])
        except (KeyError, ValueError):
            self._quota_remaining = None
        self._last_success_at = datetime.now(timezone.utc)
        self._last_error = None

    @staticmethod
    def _retry_after(headers: dict[str, str]) -> float | None:
        try:
            return max(0.0, float(headers["retry-after"]))
        except (KeyError, ValueError):
            return None

    def _json_object(self, response: HttpResponse) -> dict:
        try:
            payload = decode_json(response)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderInvalidResponseError(self.provider_id, "Pexels API returned malformed JSON") from exc
        if not isinstance(payload, dict):
            raise ProviderInvalidResponseError(self.provider_id, "Pexels API returned a non-object response")
        return payload

    def _image_candidates(self, payload: dict, need_id: str) -> list[SupplyCandidate]:
        photos = payload.get("photos")
        if not isinstance(photos, list):
            raise ProviderInvalidResponseError(self.provider_id, "Pexels photo response is missing photos")
        candidates: list[SupplyCandidate] = []
        for item in photos:
            if not isinstance(item, dict):
                raise ProviderInvalidResponseError(self.provider_id, "Pexels photo record is malformed")
            asset_id = item.get("id")
            source_page = safe_https_url(item.get("url"))
            src = item.get("src")
            if not isinstance(asset_id, (str, int)) or not source_page or not isinstance(src, dict):
                raise ProviderInvalidResponseError(self.provider_id, "Pexels photo record is missing identity or source")
            preview_url = safe_https_url(src.get("medium")) or safe_https_url(src.get("small"))
            direct_url = safe_https_url(src.get("original"))
            photographer = item.get("photographer")
            alt = item.get("alt")
            width = self._optional_positive_int(item.get("width"))
            height = self._optional_positive_int(item.get("height"))
            candidates.append(
                SupplyCandidate(
                    candidate_id=f"pexels:{asset_id}",
                    need_id=need_id,
                    media_type=MediaType.IMAGE,
                    source=CandidateSource(
                        kind="stock",
                        provider=self.provider_id,
                        provider_asset_id=str(asset_id),
                        source_page=source_page,
                        creator=photographer.strip() if isinstance(photographer, str) and photographer.strip() else None,
                    ),
                    preview=PreviewInfo(url=preview_url) if preview_url else None,
                    availability=Availability.DIRECT_DOWNLOADABLE if direct_url else Availability.PREVIEWABLE if preview_url else Availability.DISCOVERED,
                    rights_hint=RightsHint(
                        status=RightsStatus.KNOWN,
                        license_name="Pexels License",
                        license_url="https://www.pexels.com/license/",
                        attribution_required=False,
                        usage_constraints=("no_redistribution_as_stock", "no_endorsement", "no_trademark_use",
                                           "identifiable_person_restriction", "no_unaltered_resale"),
                    ),
                    metadata={
                        **({"description": alt.strip()} if isinstance(alt, str) and alt.strip() else {}),
                        **({"width": width} if width else {}),
                        **({"height": height} if height else {}),
                        **({"creator_profile": safe_https_url(item.get("photographer_url"))} if safe_https_url(item.get("photographer_url")) else {}),
                    },
                    acquisition=AcquisitionInfo(mode="provider_direct_url", locator=direct_url, media_format="image") if direct_url else None,
                )
            )
        return candidates

    def _video_candidates(self, payload: dict, need_id: str) -> list[SupplyCandidate]:
        videos = payload.get("videos")
        if not isinstance(videos, list):
            raise ProviderInvalidResponseError(self.provider_id, "Pexels video response is missing videos")
        candidates: list[SupplyCandidate] = []
        for item in videos:
            if not isinstance(item, dict):
                raise ProviderInvalidResponseError(self.provider_id, "Pexels video record is malformed")
            asset_id = item.get("id")
            source_page = safe_https_url(item.get("url"))
            video_files = item.get("video_files")
            if not isinstance(asset_id, (str, int)) or not source_page or not isinstance(video_files, list):
                raise ProviderInvalidResponseError(self.provider_id, "Pexels video record is missing identity or source")
            direct_url = None
            media_format = None
            for video_file in video_files:
                if not isinstance(video_file, dict):
                    continue
                link = safe_https_url(video_file.get("link"))
                file_type = video_file.get("file_type")
                if link and isinstance(file_type, str) and file_type.lower().startswith("video/"):
                    direct_url, media_format = link, file_type.lower()
                    break
            preview_url = safe_https_url(item.get("image"))
            user = item.get("user")
            creator = user.get("name") if isinstance(user, dict) else None
            duration = self._optional_positive_int(item.get("duration"))
            width = self._optional_positive_int(item.get("width"))
            height = self._optional_positive_int(item.get("height"))
            creator_url = safe_https_url(user.get("url")) if isinstance(user, dict) else None
            candidates.append(
                SupplyCandidate(
                    candidate_id=f"pexels:{asset_id}",
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
                    availability=Availability.DIRECT_DOWNLOADABLE if direct_url else Availability.PREVIEWABLE if preview_url else Availability.DISCOVERED,
                    rights_hint=RightsHint(
                        status=RightsStatus.KNOWN,
                        license_name="Pexels License",
                        license_url="https://www.pexels.com/license/",
                        attribution_required=False,
                        usage_constraints=("no_redistribution_as_stock", "no_endorsement", "no_trademark_use",
                                           "identifiable_person_restriction", "no_unaltered_resale"),
                    ),
                    metadata={
                        **({"duration_seconds": duration} if duration else {}),
                        **({"width": width} if width else {}),
                        **({"height": height} if height else {}),
                        **({"creator_profile": creator_url} if creator_url else {}),
                    },
                    acquisition=AcquisitionInfo(mode="provider_direct_url", locator=direct_url, media_format=media_format) if direct_url else None,
                )
            )
        return candidates

    @staticmethod
    def _optional_positive_int(value: object) -> int | None:
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return value
        return None
