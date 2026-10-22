"""Safe legacy-local import and configured stock adapters: no external requests."""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
import json
import os
from pathlib import Path
import shutil
import struct
from types import SimpleNamespace
import wave

import httpx
from PIL import Image
import pytest

from easel.materials.domain import CandidateSource, MediaType, RightsEvidence, RightsInfo, RightsStatus, SemanticInfo, TechnicalStatus
from easel.materials.library import LibraryVisibility, PromotionConsent, PromotionRejected, UseContext
from easel.production.configuration import capabilities
from easel.production.materials import MaterialService
from easel.production.providers.pixabay import PixabayStockProvider
from easel.production.providers.stock import StockUnavailable
from easel.production.supply_tasks import configured_supply
from scripts.import_local_materials import migrate


def _fixture_response(request):
    assert request.url.host == "pixabay.com"
    assert request.url.params["key"] == "private-test-key"
    if request.url.path == "/api/":
        return httpx.Response(200, json={"hits": [
            {"id": 25, "pageURL": "https://pixabay.com/photos/25/",
             "largeImageURL": "https://cdn.pixabay.com/photo/25.jpg", "tags": "city, night",
             "user": "Contributor"},
            {"id": 26, "pageURL": "https://pixabay.com/photos/26/",
             "largeImageURL": "http://127.0.0.1/private.png", "tags": "private"}]})
    assert request.url.path == "/api/videos/"
    return httpx.Response(200, json={"hits": [
        {"id": 99, "pageURL": "https://pixabay.com/videos/99/", "user": "Contributor",
         "videos": {"medium": {"url": "https://cdn.pixabay.com/video/99.mp4"}},
         "tags": "city, river"}]})


def test_pixabay_image_video_maps_rights_and_sanitizes_nonpublic_candidate(tmp_path):
    calls = []
    def handler(request):
        calls.append(request)
        return _fixture_response(request)
    provider = PixabayStockProvider("private-test-key", transport=httpx.MockTransport(handler),
                                   cache_root=tmp_path / "pixabay")
    images = provider.search("night city", media_type=MediaType.IMAGE)
    videos = provider.search("city river", media_type=MediaType.VIDEO)
    assert len(images) == len(videos) == 1
    assert images[0].source.provider == "pixabay"
    assert images[0].source.provider_asset_id == "25"
    assert images[0].rights.status is RightsStatus.KNOWN
    assert 'no_redistribution_as_stock' in images[0].rights.usage_constraints
    assert any(e.kind == "asset_provider_listing" for e in images[0].rights.evidence)
    assert images[0].semantic.tags == ("city", "night")
    assert videos[0].download_url == "https://cdn.pixabay.com/video/99.mp4"
    assert len(calls) == 2
    caches = list((tmp_path / "pixabay").glob("*.json"))
    assert len(caches) == 2
    assert all("private-test-key" not in cache.read_text() for cache in caches)
    # Windows stat mode does not represent POSIX owner-only permissions.
    if os.name != 'nt':
        assert all(cache.stat().st_mode & 0o077 == 0 for cache in caches)


def test_pixabay_cache_reused_across_instance_and_expires_after_24h(tmp_path):
    time_now = [1000.0]
    calls = []
    def handler(request):
        calls.append(request)
        return _fixture_response(request)
    provider = PixabayStockProvider("private-test-key", transport=httpx.MockTransport(handler),
        cache_root=tmp_path / "cache", clock=lambda: time_now[0])
    first = provider.search("city", media_type=MediaType.IMAGE)
    def must_not_call(request):
        pytest.fail("valid cached search must not consume API quota")
    restarted = PixabayStockProvider("private-test-key", transport=httpx.MockTransport(must_not_call),
        cache_root=tmp_path / "cache", clock=lambda: time_now[0] + 10)
    assert restarted.search("city", media_type=MediaType.IMAGE) == first
    time_now[0] += 86401
    renewed = PixabayStockProvider("private-test-key", transport=httpx.MockTransport(handler),
        cache_root=tmp_path / "cache", clock=lambda: time_now[0])
    assert renewed.search("city", media_type=MediaType.IMAGE) == first or len(renewed.search("city", media_type=MediaType.IMAGE)) == 1
    assert len(calls) == 2


def test_pixabay_missing_key_errors_and_bad_cache_does_not_fallback_to_network(tmp_path):
    with pytest.raises(StockUnavailable, match="capability_unavailable"):
        PixabayStockProvider("").search("city", media_type=MediaType.IMAGE)
    calls = []
    def handler(request):
        calls.append(request)
        return _fixture_response(request)
    provider = PixabayStockProvider("private-test-key", transport=httpx.MockTransport(handler),
        cache_root=tmp_path / "cache")
    assert provider.search("city", media_type=MediaType.IMAGE)
    path = next((tmp_path / "cache").glob("*.json"))
    path.write_text('{"candidates":"corrupt","saved_at":99999999999}')
    # Future timestamp makes cache stale; damaged candidate data must fail closed if fresh.
    path.write_text('{"candidates":"corrupt","saved_at":' + str(provider._clock()) + '}')
    restarted = PixabayStockProvider("private-test-key", transport=httpx.MockTransport(handler),
        cache_root=tmp_path / "cache")
    with pytest.raises(StockUnavailable, match="cache"):
        restarted.search("city", media_type=MediaType.IMAGE)
    assert len(calls) == 1


def test_stock_provider_http_failures_are_bounded_and_not_retried(tmp_path):
    calls = []
    def rate_limited(request):
        calls.append(request.url.path)
        return httpx.Response(429, json={'private': 'remote-secret'})
    with pytest.raises(StockUnavailable) as pixabay:
        PixabayStockProvider('private-test-key', transport=httpx.MockTransport(rate_limited),
            cache_root=tmp_path / 'cache').search('city', media_type=MediaType.IMAGE)
    assert pixabay.value.code == 'http_rate_limited'
    from easel.production.providers.unsplash import UnsplashDiscoveryProvider
    with pytest.raises(StockUnavailable, match='HTTP 429') as unsplash:
        UnsplashDiscoveryProvider('private-test-key', transport=httpx.MockTransport(rate_limited)).search('city')
    assert calls == ['/api/', '/search/photos']
    assert 'private-test-key' not in str(pixabay.value) + str(unsplash.value)
    assert 'remote-secret' not in str(pixabay.value) + str(unsplash.value)


def test_runtime_wires_pixabay_and_marks_unsplash_discovery_only(tmp_path):
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    service = SimpleNamespace(outputs=outputs)
    settings = {"PEXELS_API_KEY": "pexels-private", "PIXABAY_API_KEY": "pixabay-private",
                "UNSPLASH_ACCESS_KEY": "unsplash-private", "MINIMAX_API_KEY": "minimax-private"}
    task = configured_supply(service, None, None, settings)
    assert [p.provider_id for p in task.external_providers] == ["pexels", "pixabay"]
    assert task.generation_providers.get("IMAGE") is not None
    # No fabricated generation license or hidden video model.
    assert "VIDEO" not in task.generation_providers
    from easel.production.supply_tasks import supply_capabilities
    assert all(not x["available"] for x in supply_capabilities(settings))
    from easel.production.configuration import capabilities as real_capabilities
    from easel.direct_api import read_settings
    # Test static configuration schema without modifying actual environment.
    stock = (("pexels", "PEXELS_API_KEY"), ("pixabay", "PIXABAY_API_KEY"), ("unsplash", "UNSPLASH_ACCESS_KEY"))
    assert all(settings[key] for _, key in stock)


def _image(tmp_path):
    image = tmp_path / "local.png"
    Image.new("RGB", (48, 32), "blue").save(image)
    return image


def _rights():
    return RightsInfo(status=RightsStatus.KNOWN, license_name="Allowed local reuse",
        evidence=(RightsEvidence(kind="asset_owner_declaration", reference="local-owner:explicit"),))


def test_owner_shared_promotion_is_only_for_verified_local_import_and_is_scoped_by_owner(tmp_path):
    image = _image(tmp_path)
    service = MaterialService(tmp_path / "library")
    local = LibraryVisibility(owner_id="local")
    importing = UseContext(work_id="local-import-fixed")
    asset = service.ingest_input(source_root=tmp_path, relative_path=image.name,
        visibility=local, context=importing, media_type=MediaType.IMAGE,
        source=CandidateSource(kind="local_import", provider="legacy_local", provider_asset_id="25"),
        rights=_rights(), semantic=SemanticInfo(caption="city"))
    assert asset.asset.technical.status is TechnicalStatus.PASSED
    other = UseContext(work_id="second-work")
    assert service.catalog.get(asset.asset_ref, scope=local, context=other, missing_ok=True) is None
    with pytest.raises(PromotionRejected):
        service.catalog.promote(asset.asset_ref, scope=local, context=importing,
            consent=PromotionConsent(authorized=True, actor_id="local-owner",
                purpose="ordinary", consented_at=datetime.now(timezone.utc)))
    consent = PromotionConsent(authorized=True, actor_id="local-owner",
        purpose="owner_shared_import", consented_at=datetime.now(timezone.utc))
    record = service.catalog.promote(asset.asset_ref, scope=local, context=importing,
                                     consent=consent, owner_shared=True)
    assert record.owner_shared and record.reusable
    for scope in (local, LibraryVisibility(owner_id="local", profile_ref="six-dimension-profile")):
        assert service.catalog.get(asset.asset_ref, scope=scope, context=other).owner_shared
        assert service.catalog.list_scope(scope=scope, context=other, media_type=MediaType.IMAGE)[0].asset_ref == asset.asset_ref
    assert service.catalog.get(asset.asset_ref, scope=LibraryVisibility(owner_id="different"), context=other, missing_ok=True) is None


def test_unprofiled_upload_cannot_be_promoted_owner_wide(tmp_path):
    media = _image(tmp_path)
    service = MaterialService(tmp_path / "library")
    scope = LibraryVisibility()
    ctx = UseContext(work_id="work-1")
    handle = service.ingest_input(source_root=tmp_path, relative_path=media.name,
        visibility=scope, context=ctx, media_type=MediaType.IMAGE,
        source=CandidateSource(kind="user_upload", provider_asset_id="upload"),
        rights=_rights())
    with pytest.raises(PromotionRejected):
        service.catalog.promote(handle.asset_ref, scope=scope, context=ctx,
            consent=PromotionConsent(authorized=True, actor_id="local-owner",
                purpose="owner_shared_import", consented_at=datetime.now(timezone.utc)),
            owner_shared=True)
    assert service.catalog.get(handle.asset_ref, scope=scope, context=UseContext(work_id="second"), missing_ok=True) is None


@pytest.mark.skipif(shutil.which('ffprobe') is None, reason='Real local FFprobe unavailable; audio migration NOT_TESTED')
def test_local_import_from_verifiable_sidecars_is_idempotent_and_preserves_originals(tmp_path):
    root = tmp_path / "legacy" / "media"
    root.mkdir(parents=True)
    audio = root / "track.wav"
    with wave.open(str(audio), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(struct.pack("<" + "h" * 3200, *([0] * 3200)))
    from easel.materials.store import digest_file
    digest = digest_file(audio)
    (root / "track.json").write_text(json.dumps({
        "id": "fixture-track", "file": "track.wav", "source_url": "https://example.org/track",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "creator": "Fixture", "title": "Test audio", "mood": ["calm"]}), encoding="utf-8")
    (root / "rights.json").write_text(json.dumps({"asset_sha256": digest, "rights": {
        "status": "ATTRIBUTION_REQUIRED", "license_name": "CC BY 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "attribution_required": True, "attribution_text": "Fixture — source: example.org",
        "evidence": [{"kind": "asset_license_statement", "reference": "https://example.org/track"}]}}), encoding="utf-8")
    env = tmp_path / "legacy" / ".env"
    env.write_text(f"EASEL_MATERIAL_LOCAL_ROOTS={root}\n")
    target = tmp_path / "v2" / "materials"
    assert migrate(env, target, execute=False) == {"seen": 1, "rights_verified": 1}
    assert not target.exists()
    before = audio.read_bytes()
    result = migrate(env, target, execute=True)
    assert result["imported_or_already_present"] == 1
    again = migrate(env, target, execute=True)
    assert again["imported_or_already_present"] == 1
    assert audio.read_bytes() == before
    materials = MaterialService(target)
    records = materials.catalog.list_scope(scope=LibraryVisibility(), context=UseContext(work_id="another-work"))
    assert len(records) == 1 and records[0].owner_shared
    assert records[0].asset.rights.attribution_required
    from easel.materials.domain import MaterialNeed, NeedScope, NeedScopeType, NeedIntent, NeedImportance
    need = MaterialNeed(need_id='background-music', media_type=MediaType.AUDIO, role='music',
        scope=NeedScope(type=NeedScopeType.GLOBAL, ref='another-work'),
        importance=NeedImportance.REQUIRED, intent=NeedIntent(description='calm music'))
    result = materials.candidates(need, visibility=LibraryVisibility(), context=UseContext(work_id='another-work'))
    assert len(result.candidates) == 1
    assert 'https://example.org/track' in records[0].asset.rights.attribution_text
    assert len(list((target / "objects").iterdir())) == 1


def test_unsplash_discovery_only_hotlinks_with_exact_credit_and_no_download():
    from easel.production.providers.unsplash import UnsplashDiscoveryProvider
    requests = []
    def respond(request):
        requests.append(request)
        assert request.method == "GET"
        assert request.url.host == "api.unsplash.com"
        assert request.url.path == "/search/photos"
        assert request.headers["Authorization"] == "Client-ID private-test-key"
        return httpx.Response(200, json={"results": [
            {"id": "image-1", "urls": {"small": "https://images.unsplash.com/photo-1?ixid=public"},
             "links": {"html": "https://unsplash.com/photos/photo-1"},
             "user": {"name": "Photographer", "links": {"html": "https://unsplash.com/@artist"}}},
            {"id": "image-2", "urls": {"small": "http://127.0.0.1/trick.jpg"},
             "links": {"html": "https://unsplash.com/photos/photo-2"},
             "user": {"name": "Bad", "links": {"html": "https://unsplash.com/@bad"}}}]})
    provider = UnsplashDiscoveryProvider("private-test-key", transport=httpx.MockTransport(respond))
    results = provider.search("architecture")
    assert len(results) == len(requests) == 1
    result = results[0]
    assert result["production_ready"] is False and result["selection_required"] is True
    assert result["creator"] == "Photographer"
    assert result["preview_url"].startswith("https://images.unsplash.com/")
    assert "utm_source=easel" in result["creator_page"] and "utm_medium=referral" in result["source_page"]
    assert "private-test-key" not in json.dumps(result)


def test_unsplash_preview_route_requires_explicit_post_not_automatic_supply(monkeypatch,tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from web.production_api import create_router
    from easel.production.providers.unsplash import UnsplashDiscoveryProvider
    import easel.direct_api
    monkeypatch.setattr(easel.direct_api, "read_settings", lambda *_: {"UNSPLASH_ACCESS_KEY": "private-test-key"})
    calls = []
    def fake_search(self, query, *, limit=10):
        assert self.available and query == "city" and limit == 2
        calls.append(1)
        return ({"provider": "unsplash", "production_ready": False, "preview_url": "https://images.unsplash.com/a"},)
    monkeypatch.setattr(UnsplashDiscoveryProvider, "search", fake_search)
    app = FastAPI()
    app.include_router(create_router(lambda: SimpleNamespace(outputs=tmp_path / "outputs")))
    client = TestClient(app)
    path = "/api/production/material-sources/unsplash/preview-search"
    assert client.get(path).status_code == 405
    assert client.post(path, json={"query": "", "limit": 2}).status_code == 422
    result = client.post(path, json={"query": "city", "limit": 2})
    assert result.status_code == 200 and result.json()["production_ready"] is False
    assert calls == [1]
