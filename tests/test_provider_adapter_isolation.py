from __future__ import annotations

import json

import pytest

from easel.materials.domain import MediaType, RetrievalIntent
from easel.materials.providers import ProviderErrorCategory, ProviderRegistry
from easel.materials.providers.http_support import HttpResponse, MemoryTTLResponseCache
from easel.materials.providers.local import LocalProvider
from easel.materials.providers.pexels import PexelsProvider
from easel.materials.providers.pixabay import PixabayProvider


class FakeTransport:
    def __init__(self, response: HttpResponse):
        self.response = response

    def get(self, url: str, *, headers, timeout: float) -> HttpResponse:
        return self.response


def http_response(status: int, payload: object) -> HttpResponse:
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    return HttpResponse(status, {}, body)


@pytest.mark.parametrize("failed_provider", ("pexels", "pixabay"))
def test_one_remote_provider_failure_does_not_hide_other_provider_results(tmp_path, failed_provider) -> None:
    root = tmp_path / "local"
    root.mkdir()
    (root / "local.mp4").write_bytes(b"local fixture")

    pexels_payload = {
        "videos": [{
            "id": 7,
            "url": "https://www.pexels.com/video/7/",
            "image": "https://images.pexels.com/video-7.jpg",
            "duration": 3,
            "user": {"name": "Creator", "url": "https://www.pexels.com/@creator"},
            "video_files": [{"link": "https://cdn.example.test/pexels-7.mp4", "file_type": "video/mp4"}],
        }],
        "next_page": None,
    }
    pixabay_payload = {
        "total": 1,
        "totalHits": 1,
        "hits": [{
            "id": 8,
            "pageURL": "https://pixabay.com/videos/id-8/",
            "videos": {"medium": {
                "url": "https://cdn.pixabay.com/video-8.mp4",
                "thumbnail": "https://cdn.pixabay.com/video-8.jpg",
                "width": 1280,
                "height": 720,
            }},
        }],
    }
    pexels_status = 401 if failed_provider == "pexels" else 200
    pixabay_status = 401 if failed_provider == "pixabay" else 200
    registry = ProviderRegistry()
    registry.register(PexelsProvider("key", transport=FakeTransport(http_response(pexels_status, pexels_payload))))
    registry.register(
        PixabayProvider(
            "key",
            transport=FakeTransport(http_response(pixabay_status, pixabay_payload)),
            response_cache=MemoryTTLResponseCache(),
        )
    )
    registry.register(LocalProvider([root]))

    results = registry.search_all(
        RetrievalIntent(
            need_id="need-isolation",
            semantic_queries=("fixture footage",),
            filters={"media_type": MediaType.VIDEO.value},
        )
    )
    by_provider = {result.provider_id: result for result in results}

    assert by_provider[failed_provider].failure.category is ProviderErrorCategory.AUTH
    assert by_provider["pexels" if failed_provider == "pixabay" else "pixabay"].page.candidates
    assert by_provider["local"].page.candidates[0].metadata["filename"] == "local.mp4"
