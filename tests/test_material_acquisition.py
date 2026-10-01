from __future__ import annotations

import hashlib
import json
import pytest

from easel.materials.application.acquisition import (
    AcquisitionError,
    DownloadResponse,
    MaterialAcquirer,
    RemoteURLPolicy,
)
from easel.materials.domain import (
    Availability,
    CandidateSource,
    MediaType,
    RightsStatus,
    SupplyCandidate,
)
from easel.materials.domain.models import AcquisitionInfo, RightsHint
from easel.materials.store import AttemptMaterialStore


class FakeTransport:
    def __init__(self, *responses: DownloadResponse):
        self.responses = list(responses)
        self.calls: list[tuple[str, dict[str, str], tuple[str, ...]]] = []

    def get(self, url, *, headers, timeout, max_bytes, addresses):
        self.calls.append((url, dict(headers), addresses))
        return self.responses.pop(0)


def candidate(
    url: str = "https://videos.pexels.com/video-files/4/video.mp4?signature=secret-token",
    *,
    provider: str = "pexels",
    source_page: str = "https://www.pexels.com/video/4/?access_token=page-secret",
    media_type: MediaType = MediaType.VIDEO,
) -> SupplyCandidate:
    return SupplyCandidate(
        candidate_id=f"{provider}:4",
        need_id="need-4",
        media_type=media_type,
        source=CandidateSource(
            kind="stock",
            provider=provider,
            provider_asset_id="4",
            source_page=source_page,
            creator="Creator",
        ),
        availability=Availability.DIRECT_DOWNLOADABLE,
        rights_hint=RightsHint(status=RightsStatus.UNKNOWN),
        acquisition=AcquisitionInfo(mode="provider_direct_url", locator=url, media_format="video/mp4"),
    )


def policy_with(address: str = "93.184.216.34") -> RemoteURLPolicy:
    return RemoteURLPolicy(resolver=lambda host, port: (address,))


def test_remote_acquisition_stages_hashed_asset_and_redacted_sidecar(tmp_path) -> None:
    store = AttemptMaterialStore(tmp_path)
    transport = FakeTransport(
        DownloadResponse(200, {"content-type": "video/mp4", "content-length": "4"}, b"data")
    )
    acquirer = MaterialAcquirer(store, transport=transport, url_policy=policy_with())

    asset = acquirer.acquire(candidate())

    path = store.resolve_asset_locator(asset.file.path)
    assert path.read_bytes() == b"data"
    assert asset.file.sha256 == hashlib.sha256(b"data").hexdigest()
    assert asset.file.mime == "video/mp4"
    assert asset.technical.status.value == "PENDING"
    assert asset.rights.status is RightsStatus.UNKNOWN
    assert len(transport.calls) == 1
    assert transport.calls[0][2] == ("93.184.216.34",)
    sidecar_path = tmp_path / "materials" / "assets" / asset.asset_id / "acquisition.json"
    sidecar = sidecar_path.read_text()
    assert "secret-token" not in sidecar
    assert "page-secret" not in sidecar
    evidence = json.loads(sidecar)
    assert evidence["source_page"] == "https://www.pexels.com/video/4/?[REDACTED]"
    assert evidence["requested_url"].endswith("?[REDACTED]")
    assert evidence["final_url"] == evidence["requested_url"]
    assert evidence["rights_status_at_acquisition"] == "UNKNOWN"


def test_known_provider_license_is_carried_with_asset_specific_evidence(tmp_path) -> None:
    store = AttemptMaterialStore(tmp_path)
    source = candidate().model_copy(update={"rights_hint": RightsHint(
        status=RightsStatus.KNOWN,
        license_name="Pexels License",
        license_url="https://www.pexels.com/license/",
        attribution_required=False,
        usage_constraints=("no_redistribution_as_stock", "no_trademark_use"),
    )})
    asset = MaterialAcquirer(
        store,
        transport=FakeTransport(DownloadResponse(200, {"content-type": "video/mp4"}, b"data")),
        url_policy=policy_with(),
    ).acquire(source)

    assert asset.rights.status is RightsStatus.KNOWN
    assert asset.rights.license_name == "Pexels License"
    assert asset.rights.usage_constraints == ("no_redistribution_as_stock", "no_trademark_use")
    assert {item.kind for item in asset.rights.evidence} == {
        "asset_provider_listing", "asset_provider_license_terms",
    }
    assert any(item.reference == "https://www.pexels.com/video/4/?[REDACTED]" for item in asset.rights.evidence)
    assert any(item.reference == "https://www.pexels.com/license/" for item in asset.rights.evidence)


@pytest.mark.parametrize('provider,origin,target', [('pixabay', 'pixabay.com', 'cdn.pixabay.com'),
    ('minimax', 'video-product.cdn.minimax.io', 'cdn.hailuoai.com')])
def test_redirect_is_revalidated_before_following_and_records_final_url(tmp_path, provider, origin, target) -> None:
    transport = FakeTransport(
        DownloadResponse(302, {"Location": f"https://{target}/get/asset.mp4?token=private"}),
        DownloadResponse(200, {"Content-Type": "video/mp4"}, b"video"),
    )
    candidate_value = candidate(
        f"https://{origin}/get/asset.mp4?key=api-secret",
        provider=provider,
        source_page=f"https://{origin}/videos/4/",
    )
    resolver_calls = []

    def resolve(host, port):
        resolver_calls.append(host)
        return ("93.184.216.34",)

    asset = MaterialAcquirer(
        AttemptMaterialStore(tmp_path), transport=transport, url_policy=RemoteURLPolicy(resolve)
    ).acquire(candidate_value)

    assert resolver_calls == [origin, target]
    assert len(transport.calls) == 2
    evidence = json.loads((tmp_path / "materials" / "assets" / asset.asset_id / "acquisition.json").read_text())
    assert evidence["redirect_count"] == 1
    assert evidence["final_url"] == f"https://{target}/get/asset.mp4?[REDACTED]"
    assert "api-secret" not in json.dumps(evidence)
    assert "private" not in json.dumps(evidence)


@pytest.mark.parametrize(
    "url",
    [
        "http://videos.pexels.com/file.mp4",
        "https://user:password@videos.pexels.com/file.mp4",
        "https://videos.pexels.com:8443/file.mp4",
        "https://localhost/file.mp4",
        "https://videos.pexels.com.local/file.mp4",
        "https://example.com/file.mp4",
    ],
)
def test_remote_url_policy_rejects_unsafe_url_shapes(url) -> None:
    with pytest.raises(AcquisitionError):
        policy_with().validate(url, "pexels")


@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.4", "169.254.169.254", "::1", "fc00::1"])
def test_remote_url_policy_rejects_private_or_local_dns_addresses(address) -> None:
    with pytest.raises(AcquisitionError, match="non-public"):
        policy_with(address).validate("https://videos.pexels.com/file.mp4", "pexels")


def test_remote_url_policy_rejects_mixed_public_and_private_dns_answers() -> None:
    policy = RemoteURLPolicy(resolver=lambda host, port: ("93.184.216.34", "192.168.0.1"))
    with pytest.raises(AcquisitionError, match="non-public"):
        policy.validate("https://videos.pexels.com/file.mp4", "pexels")


def test_vpn_synthetic_dns_requires_public_https_dns_answer(monkeypatch) -> None:
    from easel.materials.application import acquisition

    monkeypatch.setattr(acquisition.socket, "getaddrinfo", lambda *args, **kwargs: [
        (None, None, None, None, ("198.18.0.14", 443)),
    ])

    class DnsResponse:
        def __init__(self, address):
            self.address = address

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self, *args):
            return json.dumps({"Answer": [{"type": 1, "data": self.address}]}).encode()

    monkeypatch.setattr(acquisition, "urlopen", lambda *args, **kwargs: DnsResponse("104.18.66.220"))
    assert RemoteURLPolicy().validate("https://videos.pexels.com/file.mp4", "pexels") == ("104.18.66.220",)

    monkeypatch.setattr(acquisition, "urlopen", lambda *args, **kwargs: DnsResponse("127.0.0.1"))
    with pytest.raises(AcquisitionError, match="non-public"):
        RemoteURLPolicy().validate("https://videos.pexels.com/file.mp4", "pexels")


def test_redirect_to_private_or_other_provider_host_is_rejected_before_request(tmp_path) -> None:
    transport = FakeTransport(
        DownloadResponse(302, {"location": "https://127.0.0.1/internal"})
    )
    with pytest.raises(AcquisitionError):
        MaterialAcquirer(
            AttemptMaterialStore(tmp_path), transport=transport, url_policy=policy_with()
        ).acquire(candidate())
    assert len(transport.calls) == 1


@pytest.mark.parametrize(
    ("response", "max_bytes", "message"),
    [
        (DownloadResponse(404, {}, b"not found"), 100, "HTTP 404"),
        (DownloadResponse(200, {"content-type": "image/jpeg"}, b"not-video"), 100, "does not match"),
        (DownloadResponse(200, {"content-type": "video/mp4"}, b""), 100, "empty"),
        (DownloadResponse(200, {"content-type": "video/mp4", "content-length": "101"}, b"small"), 100, "size limit"),
    ],
)
def test_bad_or_oversized_response_is_rejected_and_staging_cleaned(tmp_path, response, max_bytes, message) -> None:
    with pytest.raises(AcquisitionError, match=message):
        MaterialAcquirer(
            AttemptMaterialStore(tmp_path),
            transport=FakeTransport(response),
            url_policy=policy_with(),
            max_bytes=max_bytes,
        ).acquire(candidate())
    assets_dir = tmp_path / "materials" / "assets"
    assert not list(assets_dir.glob("asset-*"))


def test_local_candidate_is_staged_only_from_explicit_root(tmp_path) -> None:
    root = tmp_path / "permitted"
    root.mkdir()
    source = root / "sample.jpg"
    source.write_bytes(b"image bytes")
    local = SupplyCandidate(
        candidate_id="local:sample",
        need_id="need-4",
        media_type=MediaType.IMAGE,
        source=CandidateSource(kind="local", provider="local", provider_asset_id="sample"),
        availability=Availability.RESOLVABLE,
        acquisition=AcquisitionInfo(mode="local_file", locator=str(source), media_format="image/jpeg"),
    )
    attempt_root = tmp_path / "attempt"
    attempt_root.mkdir()
    store = AttemptMaterialStore(attempt_root)
    asset = MaterialAcquirer(store, local_roots=[root]).acquire(local)
    assert store.resolve_asset_locator(asset.file.path).read_bytes() == b"image bytes"
    sidecar = json.loads((store.attempt_root / asset.file.path).parent.joinpath("acquisition.json").read_text())
    assert sidecar["local_origin"] == "sample.jpg"


def test_local_candidate_outside_root_and_symlink_are_rejected(tmp_path) -> None:
    root = tmp_path / "permitted"
    root.mkdir()
    outside = tmp_path / "outside.jpg"
    outside.write_bytes(b"bytes")
    link = root / "linked.jpg"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks unavailable")
    candidate_value = candidate(str(outside), provider="local", media_type=MediaType.IMAGE)
    candidate_value = candidate_value.model_copy(update={
        "availability": Availability.RESOLVABLE,
        "acquisition": AcquisitionInfo(mode="local_file", locator=str(outside), media_format="image/jpeg"),
    })
    attempt_one = tmp_path / "attempt-1"
    attempt_one.mkdir()
    with pytest.raises(AcquisitionError, match="outside"):
        MaterialAcquirer(AttemptMaterialStore(attempt_one), local_roots=[root]).acquire(candidate_value)
    candidate_value = candidate_value.model_copy(update={
        "acquisition": AcquisitionInfo(mode="local_file", locator=str(link), media_format="image/jpeg"),
    })
    attempt_two = tmp_path / "attempt-2"
    attempt_two.mkdir()
    with pytest.raises(AcquisitionError, match="symlink"):
        MaterialAcquirer(AttemptMaterialStore(attempt_two), local_roots=[root]).acquire(candidate_value)
