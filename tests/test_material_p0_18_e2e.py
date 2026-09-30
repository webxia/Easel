from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image

from easel.materials.application.intelligence import BasicMaterialIntelligence
from easel.materials.application.rights import RightsService
from easel.materials.application.standalone import StandaloneMaterialFlow
from easel.materials.application.supplemental import SupplementalSupplyFoundation
from easel.materials.domain import (
    MaterialGap,
    MaterialNeed,
    MaterialPlan,
    MediaType,
    NeedImportance,
    NeedIntent,
    NeedScope,
    NeedScopeType,
    RightsEvidence,
    RightsInfo,
    RightsStatus,
    ReadinessStatus,
)
from easel.materials.providers import LocalProvider, ProviderRegistry
from easel.materials.providers.http_support import HttpResponse, MemoryTTLResponseCache
from easel.materials.providers.pexels import PexelsProvider
from easel.materials.providers.pixabay import PixabayProvider
from easel.materials.store import AttemptMaterialStore


class JsonTransport:
    def __init__(self, payload: object):
        self.payload = payload
        self.requests: list[str] = []

    def get(self, url: str, *, headers: dict[str, str], timeout: float) -> HttpResponse:
        self.requests.append(url)
        return HttpResponse(200, {}, json.dumps(self.payload).encode())


class FixtureAnalyzer:
    analyzer_id = "fixture-analyzer"

    def analyze(self, path: Path, media_type: MediaType) -> dict[str, object]:
        assert path.is_file()
        return {
            "annotations": [
                {"field": "caption", "value": "city street", "confidence": 0.99,
                 "evidence": "fixture visual observation"},
                {"field": "environment", "value": "urban", "confidence": 0.8,
                 "evidence": "fixture visual observation"},
            ]
        }


def plan(*, optional_audio: bool = True) -> MaterialPlan:
    needs = [
        MaterialNeed(
            need_id="visual-main",
            scope=NeedScope(type=NeedScopeType.SCENE, ref="scene-1"),
            media_type=MediaType.IMAGE,
            role="primary_visual",
            intent=NeedIntent(description="city street"),
            importance=NeedImportance.REQUIRED,
            desired_options=2,
        )
    ]
    if optional_audio:
        needs.append(
            MaterialNeed(
                need_id="optional-ambience",
                scope=NeedScope(type=NeedScopeType.SCENE, ref="scene-1"),
                media_type=MediaType.AUDIO,
                role="ambience",
                intent=NeedIntent(description="quiet ambience"),
                importance=NeedImportance.OPTIONAL,
            )
        )
    return MaterialPlan(plan_id="plan-e2e", creation_id="creation-e2e", attempt_id="attempt-e2e", needs=tuple(needs))


def rights_fixture(candidate: object, asset: object) -> RightsInfo:
    candidate_id = getattr(candidate, "candidate_id")
    return RightsInfo(
        status=RightsStatus.KNOWN,
        license_name="Fixture License",
        evidence=(RightsEvidence(kind="asset_license", reference=f"fixture:{candidate_id}"),),
    )


def providers(root: Path, *, pixabay_key: str = "fixture-key") -> ProviderRegistry:
    pexels_payload = {
        "photos": [
            {
                "id": 11,
                "url": "https://www.pexels.com/photo/mountain-11/",
                "width": 1600,
                "height": 900,
                "photographer": "Remote Creator",
                "alt": "mountain landscape",
                "src": {"medium": "https://images.pexels.com/mountain.jpg", "original": "https://images.pexels.com/mountain-original.jpg"},
            }
        ],
        "next_page": None,
    }
    pixabay_payload = {
        "total": 1,
        "totalHits": 1,
        "hits": [
            {
                "id": 22,
                "pageURL": "https://pixabay.com/photos/forest-22/",
                "tags": "forest, trees",
                "previewURL": "https://cdn.pixabay.com/forest-preview.jpg",
                "webformatURL": "https://cdn.pixabay.com/forest.jpg",
                "imageWidth": 1600,
                "imageHeight": 900,
                "user": "Remote Artist",
            }
        ],
    }
    registry = ProviderRegistry()
    registry.register(LocalProvider([root]))
    registry.register(PexelsProvider("fixture-key", transport=JsonTransport(pexels_payload)))
    registry.register(
        PixabayProvider(
            pixabay_key,
            transport=JsonTransport(pixabay_payload),
            response_cache=MemoryTTLResponseCache(),
        )
    )
    return registry


def flow(root: Path, store: AttemptMaterialStore, *, rights: bool, pixabay_key: str = "fixture-key") -> StandaloneMaterialFlow:
    from easel.materials.application.acquisition import MaterialAcquirer
    from easel.materials.application.inspector import TechnicalInspector

    facts = rights_fixture if rights else None
    return StandaloneMaterialFlow(
        providers(root, pixabay_key=pixabay_key),
        store,
        acquirer=MaterialAcquirer(store, local_roots=(root,)),
        inspector=TechnicalInspector(store, ffprobe="definitely-not-installed-for-image-fixture"),
        rights=RightsService(store),
        intelligence=BasicMaterialIntelligence(store, FixtureAnalyzer(), enabled=True),
        rights_facts=facts,
    )


def write_fixture(root: Path, name: str = "city-street.png") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / name
    Image.new("RGB", (160, 90), (20, 80, 120)).save(path, format="PNG")
    Image.new("RGB", (160, 90), (80, 30, 120)).save(root / "city-street-alt.png", format="PNG")
    return path


def test_local_success_e2e_tracks_workspace_bundle_run_and_mock_stock_providers(tmp_path: Path) -> None:
    root = tmp_path / "source-library"
    write_fixture(root)
    attempt = tmp_path / "attempt"
    attempt.mkdir()
    store = AttemptMaterialStore(attempt)
    result = flow(root, store, rights=True).run(plan(), supply_run_id="run-e2e", bundle_id="bundle-e2e", top_n=2)

    assert result.readiness.status is ReadinessStatus.READY
    assert result.gaps == ()
    assert {item.provider_id for item in result.provider_results} == {"local", "pexels", "pixabay"}
    assert result.supply_run.provider_results[0].candidates_found >= 1
    assert len(result.assets) == 2
    assert len(result.matches) == 2
    assert [match.rank for match in result.matches] == [1, 2]
    asset = result.assets[0]
    assert asset.semantic.intelligence_status.value == "COMPLETE"
    assert store.read_asset(asset.asset_id) == asset
    evidence = store.read_acquisition_evidence(asset.asset_id)
    assert evidence["method"] == "local_file"
    assert evidence["sha256"] in {
        hashlib.sha256((root / "city-street.png").read_bytes()).hexdigest(),
        hashlib.sha256((root / "city-street-alt.png").read_bytes()).hexdigest(),
    }
    assert store.read_bundle().bundle_id == "bundle-e2e"
    assert store.read_supply_run("run-e2e").result_bundle_id == "bundle-e2e"
    assert not hasattr(result.bundle, "timeline")
    assert not hasattr(result.bundle, "track")


def test_mock_provider_failure_isolated_and_rights_blocked_required_need_is_not_ready(tmp_path: Path) -> None:
    root = tmp_path / "source-library"
    write_fixture(root)
    attempt = tmp_path / "attempt"
    attempt.mkdir()
    store = AttemptMaterialStore(attempt)
    result = flow(root, store, rights=False, pixabay_key="").run(
        plan(optional_audio=False), supply_run_id="run-blocked", bundle_id="bundle-blocked", top_n=1
    )

    assert result.readiness.status is ReadinessStatus.NOT_READY
    assert result.gaps[0].need_id == "visual-main"
    assert any(item.provider_id == "pixabay" and item.failure is not None for item in result.provider_results)
    assert any(item.provider_id == "local" and item.page is not None for item in result.provider_results)
    assert any(item.provider_id == "pexels" and item.page is not None for item in result.provider_results)
    assert result.matches == ()
    assert result.readiness.blocking_reasons == ("no_qualified_match",)


def test_missing_required_need_then_explicit_supplemental_supply_reaches_ready(tmp_path: Path) -> None:
    root = tmp_path / "source-library"
    root.mkdir()
    attempt = tmp_path / "attempt"
    attempt.mkdir()
    store = AttemptMaterialStore(attempt)
    p = plan(optional_audio=True)
    initial = flow(root, store, rights=True).run(p, supply_run_id="run-initial", bundle_id="bundle-initial", top_n=1)

    assert initial.readiness.status is ReadinessStatus.NOT_READY
    assert initial.gaps == (MaterialGap(need_id="visual-main", reason="required_need_not_covered", request="city street", blocking=True),)
    subset = SupplementalSupplyFoundation().supply_subset(p, initial.gaps)
    assert subset.need_ids == ("visual-main",)

    write_fixture(root)
    supplemental = flow(root, store, rights=True).run(p, supply_run_id="run-supplemental", bundle_id="bundle-supplemental", top_n=1)
    merged = SupplementalSupplyFoundation().merge(
        p,
        initial.bundle,
        initial.supply_run,
        supplemental.bundle,
        supplemental.supply_run,
        subset,
        merged_supply_run_id="run-merged",
        merged_bundle_id="bundle-merged",
    )
    readiness, gaps = flow(root, store, rights=True).readiness.calculate(p, merged.bundle)
    assert readiness.status is ReadinessStatus.READY
    assert gaps == ()
    assert merged.supply_run.parent_run_id == "run-initial"
    assert merged.bundle.supply_run_id == "run-merged"
