from __future__ import annotations

from datetime import datetime, timezone
import hashlib

from easel.materials.application.advanced_matching import AdvancedMaterialMatcher
from easel.materials.application.assembly import MaterialBundleAssembler
from easel.materials.application.library_first import (
    LibraryFirstSupplyService,
    SupplementalAttemptBudget,
)
from easel.materials.application.library_reuse import LibraryReuseService
from easel.materials.application.matching import MaterialMatcher
from easel.materials.application.supplemental import SupplementalSupplyFoundation
from easel.materials.domain import (
    CandidateSource, FileInfo, MaterialAsset, MaterialGap, MaterialMatch,
    MaterialNeed, MaterialPlan, MediaType, NeedImportance, NeedIntent,
    NeedScope, NeedScopeType, RightsEvidence, RightsInfo, RightsStatus,
    SupplyRun, SupplySourceResult, TechnicalInfo, TechnicalStatus,
)
from easel.materials.library import (
    LibraryScope, MaterialLibraryCatalog, PromotionConsent,
)
from easel.materials.semantic_index import MaterialSemanticIndex, SearchMode
from easel.materials.store import AttemptMaterialStore
from easel.materials.providers.models import (
    AccessMode, ProviderCapability, ProviderInfo,
)


def _need(need_id: str, description: str, *, desired_options: int = 1) -> MaterialNeed:
    return MaterialNeed(
        need_id=need_id,
        scope=NeedScope(type=NeedScopeType.SCENE, ref=f"scene-{need_id}"),
        media_type=MediaType.IMAGE, role="visual",
        intent=NeedIntent(description=description),
        importance=NeedImportance.REQUIRED,
        desired_options=desired_options,
    )


def _asset(asset_id: str, text: str, *, provider: str = "local-fixture") -> MaterialAsset:
    body = f"fixture:{asset_id}".encode()
    return MaterialAsset(
        asset_id=asset_id, media_type=MediaType.IMAGE,
        file=FileInfo(
            path=f"materials/assets/{asset_id}/original.jpg",
            sha256=hashlib.sha256(body).hexdigest(), size=len(body), mime="image/jpeg",
        ),
        source=CandidateSource(kind="fixture", provider=provider, provider_asset_id=asset_id),
        rights=RightsInfo(
            status=RightsStatus.KNOWN, license_name="Fixture License",
            evidence=(RightsEvidence(kind="asset_license", reference=f"fixture:{asset_id}"),),
        ),
        technical=TechnicalInfo(status=TechnicalStatus.PASSED, width=1080, height=1920, mime="image/jpeg"),
        semantic={"caption": text, "tags": ("portrait", "city")},
    )


def _promote_attempt_asset(tmp_path, catalog, scope):
    attempt_root = tmp_path / "attempt-source"
    attempt_root.mkdir()
    store = AttemptMaterialStore(attempt_root)
    asset = _asset("library-city", "portrait city at night")
    locator = store.write_asset_bytes("library-city", "original.jpg", b"fixture:library-city")
    asset = asset.model_copy(update={"file": asset.file.model_copy(update={"path": locator})})
    store.write_asset(asset)
    record = catalog.promote_attempt_asset(
        asset, store, scope=scope, source_attempt_id="attempt-source",
        consent=PromotionConsent(
            authorized=True, actor_id=scope.creator_id, purpose="P1 regression fixture",
            consented_at=datetime(2026, 9, 23, tzinfo=timezone.utc),
        ),
    )
    catalog.record_usage(
        record.library_asset_id, scope=scope, creation_id="creation-history",
        attempt_id="attempt-history", need_ids=("prior-need",),
        used_at=max(datetime.now(timezone.utc), record.created_at),
    )
    return asset, record


def test_p1_full_library_first_routing_and_supplemental_regression(tmp_path) -> None:
    scope = LibraryScope(tenant_id="tenant-regression", creator_id="creator-regression")
    catalog = MaterialLibraryCatalog(tmp_path / "library")
    library_asset, promoted = _promote_attempt_asset(tmp_path, catalog, scope)

    # Attempt Asset -> promotion -> scoped Library -> metadata/semantic search.
    assert catalog.get(promoted.library_asset_id, scope=scope).asset == library_asset
    index = MaterialSemanticIndex(catalog)
    search = index.search("portrait city at night", scope=scope, provider=None, limit=10)
    assert search.hits and search.mode is SearchMode.METADATA_FALLBACK
    reuse = LibraryReuseService(catalog)
    candidates = reuse.find_candidates(
        _need("need-city", "portrait city at night", desired_options=2),
        scope=scope, creation_id="creation-current", attempt_id="attempt-current",
    ).candidates
    assert len(candidates) == 1
    assert len(candidates[0].usage_history) == 1

    # Cross-Attempt reuse -> advanced semantic matching -> Library-first route.
    advanced = AdvancedMaterialMatcher(index)
    advanced_result = advanced.match(
        _need("need-city", "portrait city at night", desired_options=2),
        candidates, scope=scope,
    )
    assert advanced_result.matches[0].library_asset_id == promoted.library_asset_id
    external = ProviderInfo(
        provider_id="openverse-fixture", display_name="Openverse fixture",
        media_types=(MediaType.IMAGE,), access_mode=AccessMode.PUBLIC_API,
        capabilities=(ProviderCapability.SEARCH, ProviderCapability.DIRECT_DOWNLOAD),
    )
    service = LibraryFirstSupplyService(reuse, advanced, matcher=MaterialMatcher())
    external_calls = []

    def fallback(provider_id, need):
        external_calls.append(provider_id)
        return (_asset("external-city", "portrait city at dusk", provider=provider_id),)

    need_city = _need("need-city", "portrait city at night", desired_options=2)
    supplied = service.supply_need(
        need_city, scope=scope, creation_id="creation-current", attempt_id="attempt-current",
        provider_infos=(external,), external_supply=fallback,
    )
    assert supplied.routing.routes[0].source_id == "material-library"
    assert external_calls == ["openverse-fixture"]
    assert len(supplied.library_matches) == 1 and len(supplied.external_matches) == 1
    assert supplied.selection_authority is False

    # The returned options can be assembled as supply facts; Production still
    # chooses later. A second uncovered Need drives one explicit supplement.
    need_missing = _need("need-missing", "mountain landscape")
    plan = MaterialPlan(
        plan_id="plan-p1-regression", creation_id="creation-current", attempt_id="attempt-current",
        needs=(need_city, need_missing),
    )
    base_run = SupplyRun(
        supply_run_id="run-base", plan_id=plan.plan_id,
        started_at=datetime(2026, 9, 23, tzinfo=timezone.utc),
        finished_at=datetime(2026, 9, 23, tzinfo=timezone.utc),
        provider_results=(SupplySourceResult(source_id="openverse-fixture", status="COMPLETE", candidates_found=1, acquired_assets=1),),
        result_bundle_id="bundle-base",
    )
    base_assets = (library_asset, *supplied.external_assets)
    base_matches = (
        MaterialMatch(need_id="need-city", asset_id=library_asset.asset_id, rank=1, score=advanced_result.matches[0].score, qualified=True, reasons=("hard_filter=passed", "source=library")),
        MaterialMatch(need_id="need-city", asset_id="external-city", rank=2, score=supplied.external_matches[0].score, qualified=True, reasons=("hard_filter=passed", "source=external")),
    )
    base_bundle = MaterialBundleAssembler().assemble(plan, base_run, base_assets, base_matches, bundle_id="bundle-base")
    gap = MaterialGap(need_id="need-missing", reason="required_need_not_covered", request="mountain landscape")
    subset = service.supplemental_subset(plan, (gap,))
    assert subset.need_ids == ("need-missing",)
    supplemental_run = SupplyRun(
        supply_run_id="run-supplemental", plan_id=plan.plan_id,
        started_at=datetime(2026, 9, 23, tzinfo=timezone.utc),
        finished_at=datetime(2026, 9, 23, tzinfo=timezone.utc),
        provider_results=(SupplySourceResult(source_id="local-supplement", status="COMPLETE", candidates_found=1, acquired_assets=1),),
        result_bundle_id="bundle-supplemental",
    )
    supplemental_asset = _asset("supplemental-mountain", "mountain landscape")
    supplemental_bundle = MaterialBundleAssembler().assemble(
        plan, supplemental_run, (supplemental_asset,),
        (MaterialMatch(need_id="need-missing", asset_id=supplemental_asset.asset_id, rank=1, qualified=True, reasons=("hard_filter=passed",)),),
        bundle_id="bundle-supplemental",
    )
    budget = SupplementalAttemptBudget(max_attempts=1)
    merged = service.merge_supplemental(
        plan, base_bundle, base_run, supplemental_bundle, supplemental_run, subset,
        merged_supply_run_id="run-merged", merged_bundle_id="bundle-merged", budget=budget,
    )
    assert budget.attempts == 1
    assert {item.asset_id for item in merged.bundle.assets} == {"library-city", "external-city", "supplemental-mountain"}
    assert {item.source_id for item in merged.supply_run.provider_results} == {"openverse-fixture", "local-supplement"}
