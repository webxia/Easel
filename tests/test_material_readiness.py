from __future__ import annotations

from datetime import datetime, timezone

from easel.materials.application.assembly import MaterialBundleAssembler
from easel.materials.application.readiness import MaterialReadinessCalculator
from easel.materials.domain import (
    CandidateSource,
    FileInfo,
    MaterialAsset,
    MaterialMatch,
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
    SupplyRun,
    TechnicalInfo,
    TechnicalStatus,
    ReadinessStatus,
)
from easel.materials.store import AttemptMaterialStore


def need(need_id: str, importance: NeedImportance, desired_options: int = 1) -> MaterialNeed:
    return MaterialNeed(
        need_id=need_id,
        scope=NeedScope(type=NeedScopeType.SCENE, ref=f"scene-{need_id}"),
        media_type=MediaType.VIDEO,
        role="broll",
        intent=NeedIntent(description=f"visual for {need_id}"),
        importance=importance,
        desired_options=desired_options,
    )


def asset(asset_id: str, *, rights: RightsStatus = RightsStatus.KNOWN, technical: TechnicalStatus = TechnicalStatus.PASSED, path: str | None = None) -> MaterialAsset:
    evidence = () if rights is RightsStatus.UNKNOWN else (
        RightsEvidence(kind="asset_license", reference=f"fixture:{asset_id}"),
    )
    return MaterialAsset(
        asset_id=asset_id,
        media_type=MediaType.VIDEO,
        file=FileInfo(path=path or f"materials/assets/{asset_id}/original.mp4", sha256=asset_id[0] * 64, size=1, mime="video/mp4"),
        source=CandidateSource(kind="fixture", provider="fixture", provider_asset_id=asset_id),
        rights=RightsInfo(status=rights, license_name="Fixture License" if rights is RightsStatus.KNOWN else None, evidence=evidence),
        technical=TechnicalInfo(status=technical, duration_seconds=2, width=1920, height=1080),
    )


def run(plan_id: str = "plan-ready") -> SupplyRun:
    now = datetime(2026, 9, 23, tzinfo=timezone.utc)
    return SupplyRun(supply_run_id="run-ready", plan_id=plan_id, started_at=now, finished_at=now)


def make_bundle(plan: MaterialPlan, assets: tuple[MaterialAsset, ...], matches: tuple[MaterialMatch, ...]):
    return MaterialBundleAssembler().assemble(plan, run(plan.plan_id), assets, matches, bundle_id="bundle-ready")


def test_required_need_is_ready_with_one_qualified_asset_even_when_more_options_are_desired() -> None:
    p = MaterialPlan(
        plan_id="plan-ready", creation_id="c", attempt_id="a",
        needs=(need("required", NeedImportance.REQUIRED, desired_options=3), need("optional", NeedImportance.OPTIONAL)),
    )
    bundle = make_bundle(p, (asset("asset-good"),), (
        MaterialMatch(need_id="required", asset_id="asset-good", rank=1, qualified=True, reasons=("hard_filter=passed",)),
    ))

    readiness, gaps = MaterialReadinessCalculator().calculate(p, bundle)
    assert readiness.status is ReadinessStatus.READY
    assert readiness.covered_required_needs == ("required",)
    assert readiness.blocking_needs == ()
    assert gaps == ()
    assert readiness.plan_revision == MaterialReadinessCalculator.plan_revision(p)
    assert readiness.bundle_revision == bundle.revision
    assert MaterialReadinessCalculator().is_current(p, bundle, readiness)


def test_unknown_rights_and_missing_hard_filter_block_required_but_optional_absence_does_not() -> None:
    p = MaterialPlan(
        plan_id="plan-ready", creation_id="c", attempt_id="a",
        needs=(need("required", NeedImportance.REQUIRED), need("optional", NeedImportance.OPTIONAL)),
    )
    bundle = make_bundle(p, (asset("asset-unknown", rights=RightsStatus.UNKNOWN),), (
        MaterialMatch(need_id="required", asset_id="asset-unknown", rank=1, qualified=True, reasons=("hard_filter=passed",)),
    ))

    readiness, gaps = MaterialReadinessCalculator().calculate(p, bundle)
    assert readiness.status is ReadinessStatus.NOT_READY
    assert readiness.blocking_needs == ("required",)
    assert gaps[0].blocking is True
    assert "rights_unknown" in readiness.blocking_reasons[0]


def test_store_backed_access_and_technical_failure_are_readiness_facts(tmp_path) -> None:
    p = MaterialPlan(
        plan_id="plan-ready", creation_id="c", attempt_id="a",
        needs=(need("required", NeedImportance.REQUIRED),),
    )
    store = AttemptMaterialStore(tmp_path)
    locator = store.write_asset_bytes("asset-missing", "original.mp4", b"x")
    inaccessible = asset("asset-missing", path="materials/assets/asset-missing/not-present.mp4")
    bundle = make_bundle(p, (inaccessible,), (
        MaterialMatch(need_id="required", asset_id="asset-missing", rank=1, qualified=True, reasons=("hard_filter=passed",)),
    ))
    readiness, gaps = MaterialReadinessCalculator(store=store).calculate(p, bundle)
    assert locator.endswith("original.mp4")
    assert readiness.status is ReadinessStatus.NOT_READY
    assert "asset_inaccessible" in readiness.blocking_reasons[0]

    failed = asset("asset-failed", technical=TechnicalStatus.FAILED)
    failed_bundle = make_bundle(p, (failed,), (
        MaterialMatch(need_id="required", asset_id="asset-failed", rank=1, qualified=True, reasons=("hard_filter=passed",)),
    ))
    failed_readiness, _ = MaterialReadinessCalculator().calculate(p, failed_bundle)
    assert "technical_inspection_not_passed" in failed_readiness.blocking_reasons[0]


def test_attribution_required_asset_passes_gate_only_with_asset_bound_export_credit_facts():
    p = MaterialPlan(
        plan_id="plan-ready", creation_id="c", attempt_id="a",
        needs=(need("required", NeedImportance.REQUIRED),),
    )
    source_page = "https://example.org/photo/1"
    attributed = asset("asset-credit", rights=RightsStatus.ATTRIBUTION_REQUIRED).model_copy(update={
        "source": CandidateSource(
            kind="fixture", provider="fixture", creator="Ada",
            source_page=source_page, provider_asset_id="credit-1",
        ),
        "rights": RightsInfo(
            status=RightsStatus.ATTRIBUTION_REQUIRED, attribution_required=True,
            attribution_text=f"Photo by Ada — {source_page}",
            evidence=(RightsEvidence(kind="asset_license", reference="fixture:credit-license"),),
        ),
    })
    bundle = make_bundle(p, (attributed,), (
        MaterialMatch(need_id="required", asset_id="asset-credit", rank=1,
                      qualified=True, reasons=("hard_filter=passed",)),
    ))
    readiness, gaps = MaterialReadinessCalculator().calculate(p, bundle)
    assert readiness.status is ReadinessStatus.READY
    assert gaps == ()


def test_attribution_required_asset_without_exact_credit_facts_stays_blocked():
    p = MaterialPlan(
        plan_id="plan-ready", creation_id="c", attempt_id="a",
        needs=(need("required", NeedImportance.REQUIRED),),
    )
    attributed = asset("asset-no-credit", rights=RightsStatus.ATTRIBUTION_REQUIRED).model_copy(update={
        "rights": RightsInfo(
            status=RightsStatus.ATTRIBUTION_REQUIRED, attribution_required=True,
            attribution_text="A vague credit line",
            evidence=(RightsEvidence(kind="asset_license", reference="fixture:credit-license"),),
        ),
    })
    bundle = make_bundle(p, (attributed,), (
        MaterialMatch(need_id="required", asset_id="asset-no-credit", rank=1,
                      qualified=True, reasons=("hard_filter=passed",)),
    ))
    readiness, _ = MaterialReadinessCalculator().calculate(p, bundle)
    assert readiness.status is ReadinessStatus.NOT_READY
    assert "rights_blocked" in readiness.blocking_reasons[0]
