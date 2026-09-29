from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

import pytest

from easel.materials.domain import Availability, MediaType, RetrievalIntent, RightsStatus
from easel.materials.providers import (
    PaginationMode,
    ProviderAuthError,
    ProviderEdgeBlockedError,
    ProviderInvalidResponseError,
    ProviderRateLimitError,
    ProviderUnsupportedError,
)
from easel.materials.providers.http_support import HttpResponse
from easel.materials.providers.pexels import PexelsProvider


class FakeTransport:
    def __init__(self, *responses: HttpResponse):
        self.responses = list(responses)
        self.requests: list[tuple[str, dict[str, str], float]] = []

    def get(self, url: str, *, headers, timeout: float) -> HttpResponse:
        self.requests.append((url, dict(headers), timeout))
        return self.responses.pop(0)


def response(payload: object, *, headers: dict[str, str] | None = None, status: int = 200) -> HttpResponse:
    return HttpResponse(status, headers or {}, json.dumps(payload).encode())


def intent(media_type: MediaType, *queries: str, **filters: str | int | bool) -> RetrievalIntent:
    return RetrievalIntent(
        need_id="need-pexels",
        semantic_queries=tuple(queries or ("city walk",)),
        filters={"media_type": media_type.value, **filters},
    )


def test_pexels_maps_video_search_metadata_and_rights_as_unknown() -> None:
    transport = FakeTransport(
        response(
            {
                "page": 1,
                "videos": [
                    {
                        "id": 41,
                        "url": "https://www.pexels.com/video/41/",
                        "image": "https://images.pexels.com/videos/41/poster.jpg",
                        "duration": 8,
                        "width": 1080,
                        "height": 1920,
                        "user": {"name": "Creator", "url": "https://www.pexels.com/@creator"},
                        "video_files": [
                            {"link": "https://cdn.example.test/41.mp4", "file_type": "video/mp4", "width": 1080, "height": 1920}
                        ],
                        "video_pictures": [{"picture": "https://not-copied.example.test/ignored.jpg"}],
                    }
                ],
                "next_page": "https://api.pexels.com/v1/videos/search?page=2",
            },
            headers={"X-Ratelimit-Remaining": "199"},
        )
    )
    provider = PexelsProvider("fixture-secret", transport=transport)
    retrieval = intent(MediaType.VIDEO, "city walk", "walking downtown", orientation="portrait", min_height=1080)

    page = provider.search(retrieval)
    candidate = page.candidates[0]

    assert candidate.candidate_id == "pexels:41"
    assert candidate.need_id == retrieval.need_id
    assert candidate.source.creator == "Creator"
    assert candidate.source.source_page == "https://www.pexels.com/video/41/"
    assert candidate.preview.url.endswith("poster.jpg")
    assert candidate.availability is Availability.DIRECT_DOWNLOADABLE
    assert candidate.acquisition.locator == "https://cdn.example.test/41.mp4"
    assert candidate.metadata == {
        "duration_seconds": 8,
        "width": 1080,
        "height": 1920,
        "creator_profile": "https://www.pexels.com/@creator",
    }
    assert candidate.rights_hint.status is RightsStatus.KNOWN
    assert candidate.rights_hint.license_name == "Pexels License"
    assert candidate.rights_hint.license_url == "https://www.pexels.com/license/"
    assert "no_redistribution_as_stock" in candidate.rights_hint.usage_constraints
    assert page.continuation.mode is PaginationMode.PAGE
    assert "fixture-secret" not in candidate.to_json()
    url, headers, _ = transport.requests[0]
    assert url.startswith("https://api.pexels.com/v1/videos/search?")
    assert parse_qs(urlparse(url).query)["query"] == ["city walk"]
    assert parse_qs(urlparse(url).query)["orientation"] == ["portrait"]
    assert parse_qs(urlparse(url).query)["size"] == ["medium"]
    assert headers["Authorization"] == "fixture-secret"
    assert provider.health().quota_remaining == 199


def test_pexels_maps_photo_and_advances_semantic_query_after_last_page() -> None:
    transport = FakeTransport(
        response(
            {
                "photos": [
                    {
                        "id": 9,
                        "url": "https://www.pexels.com/photo/9/",
                        "width": 1600,
                        "height": 900,
                        "photographer": "Photographer",
                        "photographer_url": "https://www.pexels.com/@photo",
                        "alt": "street at dusk",
                        "src": {
                            "small": "https://images.pexels.com/small.jpg",
                            "medium": "https://images.pexels.com/medium.jpg",
                            "original": "https://images.pexels.com/original.jpg",
                        },
                    }
                ],
                "next_page": None,
            }
        ),
        response({"photos": [], "next_page": None}),
    )
    provider = PexelsProvider("key", transport=transport)
    retrieval = intent(MediaType.IMAGE, "street at dusk", "night street")

    first = provider.search(retrieval)
    candidate = first.candidates[0]
    second = provider.search(retrieval, first.continuation)

    assert candidate.media_type is MediaType.IMAGE
    assert candidate.preview.url.endswith("medium.jpg")
    assert candidate.acquisition.locator.endswith("original.jpg")
    assert candidate.source.creator == "Photographer"
    assert candidate.metadata["description"] == "street at dusk"
    assert candidate.rights_hint.status is RightsStatus.KNOWN
    assert candidate.rights_hint.license_name == "Pexels License"
    assert first.continuation is not None
    assert second.continuation is None
    assert parse_qs(urlparse(transport.requests[1][0]).query)["query"] == ["night street"]


def test_pexels_rejects_malformed_payload_and_search_bound_continuation() -> None:
    provider = PexelsProvider("key", transport=FakeTransport(response({"not_photos": []})))
    with pytest.raises(ProviderInvalidResponseError):
        provider.search(intent(MediaType.IMAGE))

    provider = PexelsProvider("key", transport=FakeTransport(response({"photos": []})))
    page = provider.search(intent(MediaType.IMAGE, "one", "two"))
    with pytest.raises(ProviderUnsupportedError, match="invalid for this search"):
        provider.search(intent(MediaType.IMAGE, "different", "query"), page.continuation)


@pytest.mark.parametrize(
    ("status", "headers", "expected"),
    [
        (401, {}, ProviderAuthError),
        (429, {"Retry-After": "5"}, ProviderRateLimitError),
    ],
)
def test_pexels_http_failures_are_typed_and_do_not_leak_credentials(status, headers, expected) -> None:
    provider = PexelsProvider("private-api-key", transport=FakeTransport(response({}, status=status, headers=headers)))

    with pytest.raises(expected) as error:
        provider.search(intent(MediaType.VIDEO))

    assert "private-api-key" not in str(error.value)
    if isinstance(error.value, ProviderRateLimitError):
        assert error.value.retry_after_seconds == 5


def test_pexels_browser_signature_403_is_edge_block_not_bad_credential() -> None:
    body = b"The site owner has blocked access based on your browser's signature."
    provider = PexelsProvider(
        "private-api-key",
        transport=FakeTransport(HttpResponse(403, {"Content-Type": "text/html"}, body)),
    )

    with pytest.raises(ProviderEdgeBlockedError) as error:
        provider.search(intent(MediaType.IMAGE))

    assert not isinstance(error.value, ProviderAuthError)
    assert "private-api-key" not in str(error.value)
    assert "browser's signature" not in str(error.value)


def test_pexels_rejects_audio_before_network() -> None:
    transport = FakeTransport()
    provider = PexelsProvider("key", transport=transport)

    with pytest.raises(ProviderUnsupportedError):
        provider.search(intent(MediaType.AUDIO))

    assert transport.requests == []
