from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

import pytest

from easel.materials.domain import Availability, MediaType, RetrievalIntent, RightsStatus
from easel.materials.providers import (
    ProviderAccessDeniedError,
    ProviderAuthError,
    ProviderInvalidResponseError,
    ProviderRateLimitError,
    ProviderUnsupportedError,
)
from easel.materials.providers.http_support import (
    FileTTLResponseCache,
    HttpResponse,
    MemoryTTLResponseCache,
)
from easel.materials.providers.pixabay import PixabayProvider


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
        need_id="need-pixabay",
        semantic_queries=tuple(queries or ("city walk",)),
        filters={"media_type": media_type.value, **filters},
    )


def test_pixabay_maps_image_metadata_unknown_rights_and_search_filters() -> None:
    transport = FakeTransport(
        response(
            {
                "total": 1,
                "totalHits": 1,
                "hits": [
                    {
                        "id": 18,
                        "pageURL": "https://pixabay.com/photos/city-street-18/",
                        "type": "photo",
                        "tags": "city, street",
                        "previewURL": "https://cdn.pixabay.com/preview.jpg",
                        "webformatURL": "https://pixabay.com/get/18_640.jpg",
                        "imageWidth": 1920,
                        "imageHeight": 1080,
                        "user": "artist",
                        "user_id": 3,
                        "source_data": {"ignored": "provider payload"},
                    }
                ],
            },
            headers={"X-RateLimit-Remaining": "87", "X-RateLimit-Reset": "21"},
        )
    )
    provider = PixabayProvider("api-secret", transport=transport, response_cache=MemoryTTLResponseCache())
    retrieval = intent(
        MediaType.IMAGE,
        "city street",
        orientation="landscape",
        min_width=1280,
        min_height=720,
        order="latest",
    )

    page = provider.search(retrieval)
    candidate = page.candidates[0]

    assert candidate.candidate_id == "pixabay:18"
    assert candidate.source.provider_asset_id == "18"
    assert candidate.source.creator == "artist"
    assert candidate.source.source_page == "https://pixabay.com/photos/city-street-18/"
    assert candidate.preview.url.endswith("preview.jpg")
    assert candidate.availability is Availability.DIRECT_DOWNLOADABLE
    assert candidate.acquisition.locator.endswith("18_640.jpg")
    assert candidate.metadata == {"tags": "city, street", "width": 1920, "height": 1080}
    assert candidate.rights_hint.status is RightsStatus.KNOWN
    assert candidate.rights_hint.license_name == "Pixabay Content License"
    assert candidate.rights_hint.license_url == "https://pixabay.com/service/terms/"
    assert "third_party_rights_may_apply" in candidate.rights_hint.usage_constraints
    assert "source_data" not in candidate.metadata
    assert "license" not in candidate.metadata

    url, headers, _ = transport.requests[0]
    params = parse_qs(urlparse(url).query)
    assert url.startswith("https://pixabay.com/api/?")
    assert params["key"] == ["api-secret"]
    assert params["q"] == ["city street"]
    assert params["orientation"] == ["horizontal"]
    assert params["min_width"] == ["1280"]
    assert params["min_height"] == ["720"]
    assert params["order"] == ["latest"]
    assert params["safesearch"] == ["true"]
    assert "api-secret" not in candidate.to_json()
    assert provider.health().quota_remaining == 87


def test_pixabay_maps_video_rendition_and_paginates() -> None:
    transport = FakeTransport(
        response(
            {
                "total": 850,
                "totalHits": 500,
                "hits": [
                    {
                        "id": 51,
                        "pageURL": "https://pixabay.com/videos/id-51/",
                        "tags": "city, walking",
                        "duration": 12,
                        "user": "videographer",
                        "videos": {
                            "large": {"url": "https://cdn.pixabay.com/large.mp4", "width": 3840, "height": 2160, "thumbnail": "https://cdn.pixabay.com/large.jpg"},
                            "medium": {"url": "https://cdn.pixabay.com/medium.mp4", "width": 1920, "height": 1080, "thumbnail": "https://cdn.pixabay.com/medium.jpg"},
                            "small": {"url": "https://cdn.pixabay.com/small.mp4", "width": 1280, "height": 720, "thumbnail": "https://cdn.pixabay.com/small.jpg"},
                        },
                    }
                ],
            }
        ),
        response({"total": 500, "totalHits": 500, "hits": []}),
    )
    provider = PixabayProvider("key", transport=transport, response_cache=MemoryTTLResponseCache())
    retrieval = intent(MediaType.VIDEO, "city walking", "urban pedestrian")

    first = provider.search(retrieval)
    candidate = first.candidates[0]
    second = provider.search(retrieval, first.continuation)

    assert candidate.media_type is MediaType.VIDEO
    assert candidate.preview.url.endswith("medium.jpg")
    assert candidate.acquisition.locator.endswith("medium.mp4")
    assert candidate.metadata == {
        "tags": "city, walking",
        "duration_seconds": 12,
        "width": 1920,
        "height": 1080,
    }
    assert candidate.rights_hint.status is RightsStatus.KNOWN
    assert candidate.rights_hint.license_name == "Pixabay Content License"
    assert first.continuation is not None
    assert second.continuation is not None  # starts the second semantic query after page one is empty
    assert parse_qs(urlparse(transport.requests[1][0]).query)["page"] == ["2"]
    assert parse_qs(urlparse(transport.requests[1][0]).query)["q"] == ["city walking"]


def test_pixabay_success_response_is_cached_on_disk_for_24_hours(tmp_path) -> None:
    now = [100.0]
    cache_dir = tmp_path / "pixabay-cache"
    cache = FileTTLResponseCache(cache_dir, clock=lambda: now[0])
    transport = FakeTransport(
        response(
            {"total": 0, "totalHits": 0, "hits": []},
            headers={"X-RateLimit-Remaining": "51"},
        ),
        response({"total": 0, "totalHits": 0, "hits": []}),
    )
    provider = PixabayProvider("cache-key", transport=transport, response_cache=cache)
    retrieval = intent(MediaType.IMAGE, "cache fixture")

    provider.search(retrieval)
    assert provider.health().quota_remaining == 51
    cache_text = "".join(path.read_text(encoding="utf-8") for path in cache_dir.glob("*.json"))
    assert "cache-key" not in cache_text
    now[0] += 86_399
    restarted_provider = PixabayProvider(
        "cache-key",
        transport=transport,
        response_cache=FileTTLResponseCache(cache_dir, clock=lambda: now[0]),
    )
    restarted_provider.search(retrieval)
    assert restarted_provider.health().quota_remaining is None
    assert len(transport.requests) == 1

    now[0] += 2
    restarted_provider.search(retrieval)
    assert len(transport.requests) == 2


def test_pixabay_maps_api_failures_to_typed_errors_without_key_leak() -> None:
    for status, headers, expected in (
        (403, {}, ProviderAccessDeniedError),
        (429, {"Retry-After": "9"}, ProviderRateLimitError),
    ):
        provider = PixabayProvider(
            "sensitive-key",
            transport=FakeTransport(response("rate/error text", status=status, headers=headers)),
            response_cache=MemoryTTLResponseCache(),
        )
        with pytest.raises(expected) as error:
            provider.search(intent(MediaType.VIDEO))
        assert "sensitive-key" not in str(error.value)
        if isinstance(error.value, ProviderRateLimitError):
            assert error.value.retry_after_seconds == 9


def test_pixabay_rejects_bad_payload_long_query_and_audio_without_provider_call() -> None:
    transport = FakeTransport(response({"wrong": []}))
    provider = PixabayProvider("key", transport=transport, response_cache=MemoryTTLResponseCache())
    with pytest.raises(ProviderInvalidResponseError):
        provider.search(intent(MediaType.IMAGE))

    with pytest.raises(ProviderUnsupportedError, match="100 characters"):
        provider.search(intent(MediaType.IMAGE, "x" * 101))

    with pytest.raises(ProviderUnsupportedError):
        provider.search(intent(MediaType.AUDIO))
    assert len(transport.requests) == 1


def test_pixabay_rejects_continuation_bound_to_another_search() -> None:
    provider = PixabayProvider(
        "key",
        transport=FakeTransport(response({"total": 100, "totalHits": 100, "hits": [{
            "id": 1,
            "pageURL": "https://pixabay.com/videos/id-1/",
            "videos": {"medium": {"url": "https://cdn.pixabay.com/1.mp4", "width": 1280, "height": 720, "thumbnail": "https://cdn.pixabay.com/1.jpg"}},
        }]})),
        response_cache=MemoryTTLResponseCache(),
    )
    page = provider.search(intent(MediaType.VIDEO, "first query"))
    with pytest.raises(ProviderUnsupportedError, match="invalid for this search"):
        provider.search(intent(MediaType.VIDEO, "other query"), page.continuation)


def test_pixabay_skips_overlong_hint_without_truncating_subject_or_losing_filters():
    transport = FakeTransport(response({'totalHits': 0, 'hits': []}))
    provider = PixabayProvider('fixture-key', transport=transport, response_cache=MemoryTTLResponseCache())
    retrieval = intent(MediaType.VIDEO, 'a' * 101, 'notebook desk', orientation='portrait')
    provider.search(retrieval)
    params = parse_qs(urlparse(transport.requests[0][0]).query)
    assert params['q'] == ['notebook desk']
    assert params['orientation'] == ['vertical']
    assert retrieval.semantic_queries[0] == 'a' * 101
