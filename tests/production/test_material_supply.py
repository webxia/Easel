"""V1 supply/download negative cases adapted to work-scoped V2 fixtures."""
from datetime import datetime, timezone
from io import BytesIO

import httpx
from PIL import Image
import pytest

from easel.materials.application.acquisition import AcquisitionError, DownloadResponse, MediaDownloader, RemoteURLPolicy
from easel.materials.application.supply import MaterialSupply
from easel.materials.domain import CandidateSource, MaterialNeed, MediaType, NeedImportance, NeedIntent, NeedScope, NeedScopeType, RightsEvidence, RightsInfo, RightsStatus, SemanticInfo
from easel.materials.library import LibraryVisibility, UseContext
from easel.production.materials import MaterialService
from easel.production.providers.stock import ExternalCandidate, PexelsStockProvider, StockUnavailable


def png():
    output = BytesIO()
    Image.new("RGB", (30, 20), "blue").save(output, format="PNG")
    return output.getvalue()


def need(options=1):
    return MaterialNeed(need_id="scene-image", scope=NeedScope(type=NeedScopeType.SCENE, ref="scene-1"),
        media_type=MediaType.IMAGE, role="broll", intent=NeedIntent(description="city"),
        importance=NeedImportance.REQUIRED, desired_options=options)


def evidence():
    return RightsInfo(status=RightsStatus.KNOWN, license_name="Fixture", evidence=(RightsEvidence(
        kind="asset_license_statement", reference="https://media.example/license", observed_at=datetime.now(timezone.utc)),))


class Provider:
    provider_id = "fixture_stock"
    allowed_hosts = ("media.example",)

    def __init__(self, rights=None, fail=False):
        self.calls = 0
        self.rights, self.fail = rights or evidence(), fail

    def search(self, query, *, media_type, limit):
        self.calls += 1
        if self.fail:
            raise RuntimeError("token=PRIVATE must not enter public failure messages")
        return (ExternalCandidate("fixture-1", MediaType.IMAGE, "https://media.example/a.png",
                CandidateSource(kind="stock", provider=self.provider_id, source_page="https://media.example/a", creator="Artist"),
                self.rights, SemanticInfo(caption="city")),)


class Transport:
    def __init__(self, responses=None):
        self.calls = []
        self.responses = list(responses or [DownloadResponse(200, {"content-type": "image/png"}, png())])

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


def downloader(transport, resolver=None, **kwargs):
    return MediaDownloader(RemoteURLPolicy(("media.example",), resolver=resolver or (lambda *_: ("8.8.8.8",))), transport=transport, **kwargs)


@pytest.fixture
def env(tmp_path):
    return MaterialService(tmp_path.resolve() / "library"), LibraryVisibility(profile_ref="profile"), UseContext(work_id="work-1")


def test_external_media_is_inspected_before_it_becomes_a_candidate_and_next_supply_reuses(env):
    service, scope, context = env
    provider, transport = Provider(), Transport()
    supply = MaterialSupply(service, providers=(provider,), downloaders={provider.provider_id: downloader(transport)})
    first = supply.supply(need(), visibility=scope, context=context, allowed_providers=(provider.provider_id,), allow_generation=True)
    assert len(first.candidates) == 1 and first.gap is None and first.generation_route is None
    assert first.candidates[0].asset.technical.width == 30
    assert not first.candidates[0].selected_for_production
    second = supply.supply(need(), visibility=scope, context=context, allowed_providers=(provider.provider_id,))
    assert second.candidates[0].library_asset_id == first.candidates[0].library_asset_id
    assert provider.calls == len(transport.calls) == 1


def test_required_material_is_never_replaced_by_external_or_generation(env):
    service, scope, context = env
    provider = Provider()
    result = MaterialSupply(service, providers=(provider,)).supply(need(), visibility=scope, context=context,
        required_asset_refs=("missing-required",), allowed_providers=(provider.provider_id,), allow_generation=True)
    assert result.gap == "required_material_unavailable" and result.generation_route is None
    assert provider.calls == 0


def test_public_url_does_not_imply_rights_and_generation_is_only_a_route(env):
    service, scope, context = env
    provider, transport = Provider(rights=RightsInfo(status=RightsStatus.UNKNOWN)), Transport()
    result = MaterialSupply(service, providers=(provider,), downloaders={provider.provider_id: downloader(transport)}).supply(
        need(), visibility=scope, context=context, allowed_providers=(provider.provider_id,), allow_generation=True)
    assert not result.candidates and result.gap
    assert result.generation_route == {"kind": "IMAGE", "need_id": "scene-image", "requires_director_selection": True}
    assert result.failures[0].reason == "required_need_rights_unknown"


def test_corrupt_external_media_stops_as_gap(env):
    service, scope, context = env
    provider = Provider()
    transport = Transport([DownloadResponse(200, {"content-type": "image/png"}, b"not an image")])
    result = MaterialSupply(service, providers=(provider,), downloaders={provider.provider_id: downloader(transport)}).supply(
        need(), visibility=scope, context=context, allowed_providers=(provider.provider_id,))
    assert not result.candidates and result.gap
    assert result.failures[0].reason == "technical_inspection_not_passed"


def test_source_failures_are_bounded_and_sanitized(env):
    service, scope, context = env
    providers = tuple(Provider(fail=True) for _ in range(5))
    result = MaterialSupply(service, providers=providers, max_sources=2).supply(need(), visibility=scope, context=context,
        allowed_providers=("fixture_stock",))
    assert sum(p.calls for p in providers) == 2
    assert len(result.failures) == 2 and "PRIVATE" not in repr(result)
    assert result.generation_route is None


@pytest.mark.parametrize("address", ["127.0.0.1", "10.1.2.3", "169.254.169.254", "::1", "fc00::1", "224.0.0.1"])
def test_private_and_nonunicast_dns_is_rejected_before_download(address):
    transport = Transport()
    client = downloader(transport, resolver=lambda *_: (address,))
    with pytest.raises(AcquisitionError):
        client.download("https://media.example/a.png", media_type="image")
    assert not transport.calls


def test_each_redirect_is_revalidated_and_dns_is_pinned():
    transport = Transport([DownloadResponse(302, {"location": "https://media.example/private"})])
    addresses = iter([("8.8.8.8",), ("127.0.0.1",)])
    client = downloader(transport, resolver=lambda *_: next(addresses))
    with pytest.raises(AcquisitionError):
        client.download("https://media.example/a.png", media_type="image")
    assert len(transport.calls) == 1 and transport.calls[0][1]["addresses"] == ("8.8.8.8",)


@pytest.mark.parametrize("location", ["http://media.example/a", "https://127.0.0.1/a", "https://other.example/a", "https://user:pass@media.example/a"])
def test_disallowed_redirect_destinations_never_receive_a_request(location):
    transport = Transport([DownloadResponse(302, {"location": location})])
    with pytest.raises(AcquisitionError):
        downloader(transport).download("https://media.example/a", media_type="image")
    assert len(transport.calls) == 1


@pytest.mark.parametrize("response", [
    DownloadResponse(200, {"content-type": "image/png", "content-length": "999"}, b"x"),
    DownloadResponse(200, {"content-type": "image/png", "content-length": "-1"}, b"x"),
    DownloadResponse(200, {"content-type": "image/png"}, b"x" * 11),
    DownloadResponse(200, {"content-type": "text/html"}, b"x"),
    DownloadResponse(200, {"content-type": "image/png"}, b""),
])
def test_invalid_size_and_type_are_rejected(response):
    with pytest.raises(AcquisitionError):
        downloader(Transport([response]), max_bytes=10).download("https://media.example/a", media_type="image")


def test_pexels_http_mapping_keeps_source_terms_and_supports_image_and_video():
    calls = []
    def handler(request):
        calls.append(request)
        assert request.headers["Authorization"] == "fixture-key"
        if request.url.path == "/v1/search":
            return httpx.Response(200, json={"photos": [{"id": 1, "url": "https://www.pexels.com/photo/1/",
                "photographer": "Artist", "alt": "city", "src": {"original": "https://images.pexels.com/a.png"}}]})
        return httpx.Response(200, json={"videos": [{"id": 2, "url": "https://www.pexels.com/video/2/", "user": {"name": "Artist"},
            "video_files": [{"file_type": "video/mp4", "link": "https://videos.pexels.com/a.mp4"}]}]})
    provider = PexelsStockProvider("fixture-key", transport=httpx.MockTransport(handler))
    for kind in (MediaType.IMAGE, MediaType.VIDEO):
        candidate = provider.search("city", media_type=kind, limit=2)[0]
        assert candidate.media_type is kind and candidate.rights.status is RightsStatus.KNOWN
        assert candidate.rights.evidence[0].kind == "asset_provider_listing"
        assert "no_endorsement" in candidate.rights.usage_constraints
    assert len(calls) == 2


def test_pexels_missing_configuration_never_calls_network():
    with pytest.raises(StockUnavailable, match="capability_unavailable"):
        PexelsStockProvider("").search("city", media_type=MediaType.IMAGE, limit=2)
