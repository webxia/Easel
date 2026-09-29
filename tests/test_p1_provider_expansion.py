from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

import pytest

from easel.materials.domain import Availability, MediaType, RetrievalIntent, RightsStatus
from easel.materials.providers import (
    AccessMode,
    CoverrProvider,
    OpenverseAudioProvider,
    OpenverseProvider,
    PaginationMode,
    ProviderCapability,
    ProviderAccessDeniedError,
    ProviderAuthError,
    ProviderEdgeBlockedError,
    ProviderRateLimitError,
    ProviderUnsupportedError,
    ProviderInvalidResponseError,
    UnsplashProvider,
)
from easel.materials.providers.http_support import HttpResponse


class FakeTransport:
    def __init__(self, *responses: HttpResponse):
        self.responses = list(responses)
        self.requests: list[tuple[str, dict[str, str], float]] = []
        self.post_requests: list[tuple[str, dict[str, str], bytes, float]] = []

    def get(self, url: str, *, headers, timeout: float) -> HttpResponse:
        self.requests.append((url, dict(headers), timeout))
        return self.responses.pop(0)

    def post(self, url: str, *, headers, body: bytes, timeout: float) -> HttpResponse:
        self.post_requests.append((url, dict(headers), body, timeout))
        return self.responses.pop(0)


def response(payload: object, *, status: int = 200, headers: dict[str, str] | None = None) -> HttpResponse:
    return HttpResponse(status, headers or {}, json.dumps(payload).encode())


def intent(media_type: MediaType, *queries: str, **filters: str | int | bool) -> RetrievalIntent:
    return RetrievalIntent(
        need_id="need-p1",
        semantic_queries=tuple(queries or ("night city",)),
        filters={"media_type": media_type.value, **filters},
    )


def test_coverr_discovery_only_search_pagination_and_policy_metadata() -> None:
    transport = FakeTransport(
        response({
            "page": 0,
            "pages": 2,
            "hits": [{
                "id": "coverr-1", "title": "City at night", "description": "A night street",
                "poster": "https://storage.coverr.co/p/coverr-1", "thumbnail": "https://storage.coverr.co/t/coverr-1",
                "duration": 9.5, "max_width": 1920, "max_height": 1080, "tags": ["city", "night"],
                "urls": {"mp4_download": "https://storage.coverr.co/download?token=secret"},
            }],
        }, headers={"X-RateLimit-Remaining": "17"}),
        response({"page": 1, "pages": 2, "hits": []}),
    )
    provider = CoverrProvider("coverr-secret", transport=transport)
    query = intent(MediaType.VIDEO, "night city", "urban skyline")
    first = provider.search(query)
    candidate = first.candidates[0]
    second = provider.search(query, first.continuation)

    assert provider.info().access_mode is AccessMode.DISCOVERY_ONLY
    assert "DIRECT_DOWNLOAD" not in {cap.value for cap in provider.info().capabilities}
    assert candidate.availability is Availability.PREVIEWABLE
    assert candidate.rights_hint.status is RightsStatus.UNKNOWN
    assert candidate.acquisition is None
    assert candidate.preview.url.endswith("coverr-1")
    assert candidate.metadata["api_attribution_required"] == "clickable_coverr_logo"
    assert "secret" not in candidate.to_json()
    assert second.continuation is not None
    assert parse_qs(urlparse(transport.requests[1][0]).query)["page"] == ["1"]
    assert transport.requests[0][1]["Authorization"] == "Bearer coverr-secret"
    assert provider.health().quota_remaining is None


def test_coverr_requires_key_and_isolates_rate_limit() -> None:
    with pytest.raises(ProviderAuthError):
        CoverrProvider().search(intent(MediaType.VIDEO))
    provider = CoverrProvider("key", transport=FakeTransport(response({}, status=429, headers={"Retry-After": "3"})))
    with pytest.raises(ProviderRateLimitError) as error:
        provider.search(intent(MediaType.VIDEO))
    assert error.value.retry_after_seconds == 3
    assert "key" not in str(error.value)


def test_coverr_browser_signature_403_is_edge_block() -> None:
    response_edge = HttpResponse(
        403,
        {"Content-Type": "text/html"},
        b"The site owner has blocked access based on your browser's signature.",
    )
    provider = CoverrProvider("coverr-secret", transport=FakeTransport(response_edge))

    with pytest.raises(ProviderEdgeBlockedError) as error:
        provider.search(intent(MediaType.VIDEO))

    assert "coverr-secret" not in str(error.value)


def _unsplash_photo(photo_id: str = "photo-1") -> dict[str, object]:
    return {
        "id": photo_id,
        "alt_description": "night city portrait",
        "width": 900,
        "height": 1200,
        "urls": {
            "small": f"https://images.unsplash.com/{photo_id}?w=400",
            "thumb": f"https://images.unsplash.com/{photo_id}?w=100",
        },
        "links": {
            "html": f"https://unsplash.com/photos/{photo_id}",
            "download_location": f"https://api.unsplash.com/photos/{photo_id}/download",
        },
        "user": {"name": "Photographer", "links": {"html": "https://unsplash.com/@photo"}},
    }


def test_unsplash_hotlink_attribution_download_tracking_and_pagination() -> None:
    transport = FakeTransport(
        response({"results": [_unsplash_photo()], "total_pages": 2}, headers={"X-Ratelimit-Remaining": "45"}),
        response({"results": [], "total_pages": 2}, headers={"X-Ratelimit-Remaining": "45"}),
        response({"url": "https://images.unsplash.com/photo-1"}, headers={"X-Ratelimit-Remaining": "45"}),
    )
    provider = UnsplashProvider("fixture-access-key", transport=transport)
    query = intent(MediaType.IMAGE, "night city", "portrait skyline")
    first = provider.search(query)
    candidate = first.candidates[0]
    provider.search(query, first.continuation)
    provider.record_selection(candidate)

    assert provider.info().access_mode is AccessMode.DISCOVERY_ONLY
    assert candidate.availability is Availability.PREVIEWABLE
    assert candidate.acquisition is None
    assert candidate.rights_hint.status is RightsStatus.UNKNOWN
    assert candidate.preview.url.startswith("https://images.unsplash.com/")
    assert "utm_source=easel" in candidate.source.source_page
    assert "utm_medium=referral" in candidate.metadata["creator_profile_url"]
    assert candidate.metadata["attribution_required"] is True
    assert parse_qs(urlparse(transport.requests[1][0]).query)["page"] == ["2"]
    assert urlparse(transport.requests[2][0]).path.endswith("/photos/photo-1/download")
    assert transport.requests[2][1]["Authorization"] == "Client-ID fixture-access-key"
    assert provider.health().quota_remaining == 45


def test_unsplash_rejects_untrusted_tracking_location_and_missing_auth() -> None:
    provider = UnsplashProvider("key", transport=FakeTransport())
    candidate = provider._candidate(_unsplash_photo(), "need-p1")
    malicious = candidate.model_copy(update={
        "metadata": {**candidate.metadata, "download_tracking_url": "https://attacker.example/photos/photo-1/download"}
    })
    with pytest.raises(ProviderUnsupportedError):
        provider.record_selection(malicious)
    wrong_photo = candidate.model_copy(update={
        "metadata": {**candidate.metadata, "download_tracking_url": "https://api.unsplash.com/photos/other-photo/download"}
    })
    with pytest.raises(ProviderUnsupportedError):
        provider.record_selection(wrong_photo)
    with pytest.raises(ProviderAuthError):
        UnsplashProvider().search(intent(MediaType.IMAGE))


def _openverse_result(*, license_id: str = "by", item_id: str = "item-1") -> dict[str, object]:
    return {
        "id": item_id,
        "title": "Night city",
        "foreign_landing_url": "https://commons.example/item-1",
        "url": "https://media.example/item-1.jpg",
        "thumbnail": "https://media.example/item-1-thumb.jpg",
        "creator": "Creator",
        "creator_url": "https://commons.example/creator",
        "license": license_id,
        "license_version": "4.0",
        "license_url": f"https://creativecommons.org/licenses/{license_id}/4.0/",
        "provider": "flickr",
        "source": "flickr",
        "attribution": "Creator, CC BY",
        "width": 1200,
        "height": 800,
        "filesize": 2048,
        "filetype": "image/jpeg",
        "tags": [{"name": "city"}, {"name": "night"}],
    }


def test_openverse_maps_item_rights_filters_safe_acquisition_and_page_state() -> None:
    transport = FakeTransport(
        response({"results": [_openverse_result(), _openverse_result(license_id="by-nc", item_id="item-2")], "page": 1, "page_count": 2}),
        response({"results": [], "page": 2, "page_count": 2}),
    )
    provider = OpenverseProvider("fixture-oauth-token", transport=transport)
    query = intent(MediaType.IMAGE, "night city", license="by,cc0")
    first = provider.search(query)
    by, nc = first.candidates
    second = provider.search(query, first.continuation)

    assert provider.info().access_mode.value == "DISCOVERY_ONLY"
    assert "DIRECT_DOWNLOAD" not in {cap.value for cap in provider.info().capabilities}
    assert by.availability is Availability.PREVIEWABLE
    assert by.rights_hint.status is RightsStatus.ATTRIBUTION_REQUIRED
    assert by.rights_hint.attribution_required is True
    assert by.metadata["license_version"] == "4.0"
    assert by.metadata["attribution"] == "Creator, CC BY"
    assert by.acquisition is None
    assert nc.rights_hint.status is RightsStatus.UNKNOWN
    assert nc.metadata["license_id"] == "by-nc"
    assert second.continuation is None
    assert parse_qs(urlparse(transport.requests[0][0]).query)["license"] == ["by,cc0"]
    assert transport.requests[0][1]["Authorization"] == "Bearer fixture-oauth-token"
    assert "fixture-oauth-token" not in by.to_json()


def test_openverse_unknown_rights_and_audio_are_normalized_without_provider_payload() -> None:
    audio_item = {
        "id": "audio-1", "title": "City ambience", "foreign_landing_url": "https://sound.example/audio-1",
        "url": "http://insecure.example/audio.wav", "thumbnail": "https://sound.example/cover.jpg",
        "creator": "Sound Author", "license": "unverified", "license_url": "https://license.example/custom",
        "license_version": "", "filetype": "audio/wav", "filesize": 123, "duration": 5.0,
        "tags": [], "attribution": "Sound Author",
    }
    transport = FakeTransport(response({"results": [audio_item], "page": 1, "page_count": 1}))
    provider = OpenverseProvider(transport=transport)
    candidate = provider.search(intent(MediaType.AUDIO)).candidates[0]
    assert candidate.media_type is MediaType.AUDIO
    assert candidate.rights_hint.status is RightsStatus.UNKNOWN
    assert candidate.availability is Availability.PREVIEWABLE
    assert candidate.acquisition is None
    assert "license_id" in candidate.metadata
    assert "provider_payload" not in candidate.metadata
    assert "Authorization" not in transport.requests[0][1]


def test_openverse_audio_acquisition_requires_safe_cdn_and_supported_item_license() -> None:
    safe = {**_openverse_result(), "url": "https://cdn.freesound.org/previews/1/1-hq.mp3",
            "foreign_landing_url": "https://freesound.org/people/Creator/sounds/1", "source": "freesound"}
    unsafe = {**safe, "id": "unsafe", "url": "https://unrelated.example/audio.mp3"}
    restricted = {**safe, "id": "restricted", "license": "by-nc"}
    transport = FakeTransport(response({"results": [safe, unsafe, restricted], "page": 1, "page_count": 1}))
    provider = OpenverseAudioProvider(transport=transport)

    page = provider.search(intent(MediaType.AUDIO, "gentle piano"))

    assert provider.info().supports(MediaType.AUDIO, ProviderCapability.DIRECT_DOWNLOAD)
    assert not provider.info().supports(MediaType.IMAGE, ProviderCapability.DIRECT_DOWNLOAD)
    assert page.candidates[0].availability is Availability.DIRECT_DOWNLOADABLE
    assert page.candidates[0].acquisition.locator == safe["url"]
    assert all(item.acquisition is None for item in page.candidates[1:])
    assert parse_qs(urlparse(transport.requests[0][0]).query)["license"] == ["cc0,by"]


def _openverse_empty_page() -> HttpResponse:
    return response({"results": [], "page": 1, "page_count": 1})


def _oauth_token(value: str, *, expires_in: int = 3600) -> HttpResponse:
    return response({"access_token": value, "token_type": "Bearer", "expires_in": expires_in})


def test_openverse_oauth_client_credentials_are_cached_in_memory() -> None:
    transport = FakeTransport(_oauth_token("short-lived-token"), _openverse_empty_page(), _openverse_empty_page())
    provider = OpenverseProvider(client_id="client-id", client_secret="client-secret", transport=transport)

    provider.search(intent(MediaType.IMAGE))
    provider.search(intent(MediaType.IMAGE))

    assert len(transport.post_requests) == 1
    token_url, headers, body, _ = transport.post_requests[0]
    assert token_url.endswith("/v1/auth_tokens/token/")
    assert headers["Content-Type"] == "application/x-www-form-urlencoded"
    assert parse_qs(body.decode()) == {
        "grant_type": ["client_credentials"],
        "client_id": ["client-id"],
        "client_secret": ["client-secret"],
    }
    assert all(request[1]["Authorization"] == "Bearer short-lived-token" for request in transport.requests)
    assert "client-secret" not in repr(provider)


def test_openverse_oauth_pair_takes_precedence_over_static_token() -> None:
    transport = FakeTransport(_oauth_token("managed-token"), _openverse_empty_page())
    provider = OpenverseProvider(
        "static-fallback-token",
        client_id="client-id",
        client_secret="client-secret",
        transport=transport,
    )

    provider.search(intent(MediaType.IMAGE))

    assert transport.requests[0][1]["Authorization"] == "Bearer managed-token"
    assert "static-fallback-token" not in repr(transport.requests)


def test_openverse_static_token_is_used_when_oauth_pair_is_absent() -> None:
    transport = FakeTransport(_openverse_empty_page())
    provider = OpenverseProvider("static-fallback-token", transport=transport)

    provider.search(intent(MediaType.IMAGE))

    assert transport.requests[0][1]["Authorization"] == "Bearer static-fallback-token"
    assert transport.post_requests == []


def test_openverse_oauth_refreshes_before_expiry() -> None:
    now = [100.0]
    transport = FakeTransport(
        _oauth_token("token-one", expires_in=100), _openverse_empty_page(),
        _oauth_token("token-two", expires_in=100), _openverse_empty_page(),
    )
    provider = OpenverseProvider(
        client_id="client-id", client_secret="client-secret", transport=transport,
        clock=lambda: now[0],
    )

    provider.search(intent(MediaType.IMAGE))
    now[0] = 191.0  # expires_in=100; refresh point is 90 seconds after issue.
    provider.search(intent(MediaType.IMAGE))

    assert len(transport.post_requests) == 2
    assert [request[1]["Authorization"] for request in transport.requests] == [
        "Bearer token-one", "Bearer token-two",
    ]


def test_openverse_retries_one_rejected_bearer_with_refreshed_token() -> None:
    transport = FakeTransport(
        _oauth_token("expired-token"), response({}, status=401),
        _oauth_token("fresh-token"), _openverse_empty_page(),
    )
    provider = OpenverseProvider(client_id="client-id", client_secret="client-secret", transport=transport)

    page = provider.search(intent(MediaType.IMAGE))

    assert page.candidates == ()
    assert len(transport.post_requests) == 2
    assert [request[1]["Authorization"] for request in transport.requests] == [
        "Bearer expired-token", "Bearer fresh-token",
    ]


def test_openverse_edge_403_is_not_misclassified_or_retried_as_bad_token() -> None:
    edge_response = HttpResponse(
        403,
        {"Content-Type": "text/html"},
        b"The site owner has blocked access based on your browser's signature.",
    )
    transport = FakeTransport(_oauth_token("managed-token"), edge_response)
    provider = OpenverseProvider(client_id="client-id", client_secret="client-secret", transport=transport)

    with pytest.raises(ProviderEdgeBlockedError) as error:
        provider.search(intent(MediaType.IMAGE))

    assert len(transport.post_requests) == 1
    assert len(transport.requests) == 1
    assert "browser's signature" not in str(error.value)


def test_openverse_generic_403_is_access_denied_not_authentication_failure() -> None:
    transport = FakeTransport(response({"detail": "permission denied"}, status=403))
    provider = OpenverseProvider("valid-looking-token", transport=transport)

    with pytest.raises(ProviderAccessDeniedError) as error:
        provider.search(intent(MediaType.IMAGE))

    assert not isinstance(error.value, ProviderAuthError)


def test_openverse_oauth_partial_credentials_and_bad_token_response_are_typed() -> None:
    with pytest.raises(ProviderAuthError, match="must be configured together"):
        OpenverseProvider(client_id="client-id").search(intent(MediaType.IMAGE))

    provider = OpenverseProvider(
        client_id="client-id", client_secret="client-secret",
        transport=FakeTransport(response({"access_token": "no-expiry", "token_type": "Bearer"})),
    )
    with pytest.raises(ProviderInvalidResponseError, match="token response") as error:
        provider.search(intent(MediaType.IMAGE))
    assert "client-secret" not in str(error.value)
