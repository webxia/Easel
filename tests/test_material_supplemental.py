from __future__ import annotations

from datetime import datetime, timezone
import hashlib

import pytest

from easel.materials.application.assembly import MaterialBundleAssembler
from easel.materials.application.supplemental import SupplementalSupplyFoundation
from easel.materials.domain import (
    CandidateSource,
    FileInfo,
    MaterialAsset,
    MaterialGap,
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
    SupplySourceResult,
    TechnicalInfo,
    TechnicalStatus,
)


def need(need_id: str, importance: NeedImportance = NeedImportance.REQUIRED) -> MaterialNeed:
    return MaterialNeed(
        need_id=need_id,
        scope=NeedScope(type=NeedScopeType.SCENE, ref=f"scene-{need_id}"),
        media_type=MediaType.VIDEO,
        role="broll",
        intent=NeedIntent(description=f"visual for {need_id}"),
        importance=importance,
    )


def plan() -> MaterialPlan:
    return MaterialPlan(
        plan_id="plan-supplemental", creation_id="c", attempt_id="a",
        needs=(need("first"), need("second"), need("optional", NeedImportance.OPTIONAL)),
    )


def asset(asset_id: str) -> MaterialAsset:
    return MaterialAsset(
        asset_id=asset_id,
        media_type=MediaType.VIDEO,
        file=FileInfo(path=f"materials/assets/{asset_id}/original.mp4", sha256=hashlib.sha256(asset_id.encode()).hexdigest(), size=1, mime="video/mp4"),
        source=CandidateSource(kind="fixture", provider="fixture", provider_asset_id=asset_id),
        rights=RightsInfo(status=RightsStatus.KNOWN, license_name="Fixture", evidence=(RightsEvidence(kind="asset_license", reference=f"fixture:{asset_id}"),)),
        technical=TechnicalInfo(status=TechnicalStatus.PASSED, duration_seconds=2, width=1920, height=1080),
    )


def run(run_id: str, bundle_id: str | None = None, source: str = "fixture") -> SupplyRun:
    now = datetime(2026, 9, 23, tzinfo=timezone.utc)
    return SupplyRun(
        supply_run_id=run_id,
        plan_id="plan-supplemental",
        started_at=now,
        finished_at=now,
        provider_results=(SupplySourceResult(source_id=source, status="COMPLETE", candidates_found=1),),
        result_bundle_id=bundle_id,
    )


def bundle(p: MaterialPlan, supply_run: SupplyRun, bundle_id: str, assets: tuple[MaterialAsset, ...], matches: tuple[MaterialMatch, ...]):
    return MaterialBundleAssembler().assemble(p, supply_run, assets, matches, bundle_id=bundle_id)


def test_subset_is_explicit_blocking_only_and_plan_ordered() -> None:
    p = plan()
    gaps = (
        MaterialGap(need_id="second", reason="required_need_not_covered", blocking=True),
        MaterialGap(need_id="optional", reason="editorial_preference", blocking=False),
        MaterialGap(need_id="first", reason="required_need_not_covered", blocking=True),
        MaterialGap(need_id="first", reason="duplicate", blocking=True),
    )
    subset = SupplementalSupplyFoundation().supply_subset(p, gaps)
    assert subset.need_ids == ("first", "second")
    assert tuple(gap.need_id for gap in subset.gaps) == subset.need_ids


def test_merge_preserves_base_material_and_adds_only_requested_supplemental_results() -> None:
    p = plan()
    base_run = run("run-base", "bundle-base")
    base = bundle(p, base_run, "bundle-base", (asset("asset-base"),), (
        MaterialMatch(need_id="first", asset_id="asset-base", rank=1, qualified=True, reasons=("hard_filter=passed",)),
    ))
    supplemental_run = run("run-supplemental", "bundle-supplemental", source="second-source")
    supplemental = bundle(p, supplemental_run, "bundle-supplemental", (asset("asset-new"),), (
        MaterialMatch(need_id="second", asset_id="asset-new", rank=1, qualified=True, reasons=("hard_filter=passed",)),
    ))
    subset = SupplementalSupplyFoundation().supply_subset(p, (MaterialGap(need_id="second", reason="required_need_not_covered"),))

    result = SupplementalSupplyFoundation().merge(
        p, base, base_run, supplemental, supplemental_run, subset,
        merged_supply_run_id="run-merged", merged_bundle_id="bundle-merged",
    )
    assert [item.asset_id for item in result.bundle.assets] == ["asset-base", "asset-new"]
    assert {(item.need_id, item.asset_id) for item in result.bundle.matches} == {("first", "asset-base"), ("second", "asset-new")}
    assert result.bundle.supply_run_id == "run-merged"
    assert result.supply_run.result_bundle_id == "bundle-merged"
    assert result.supply_run.parent_run_id == "run-base"
    assert {item.source_id for item in result.supply_run.provider_results} == {"fixture", "second-source"}


def test_merge_rejects_out_of_subset_matches_and_conflicting_asset_identity() -> None:
    p = plan()
    base_run = run("run-base", "bundle-base")
    base = bundle(p, base_run, "bundle-base", (asset("asset-base"),), ())
    supplemental_run = run("run-supplemental", "bundle-supplemental", source="second-source")
    supplemental = bundle(p, supplemental_run, "bundle-supplemental", (asset("asset-new"),), (
        MaterialMatch(need_id="first", asset_id="asset-new", rank=1),
    ))
    subset = SupplementalSupplyFoundation().supply_subset(p, (MaterialGap(need_id="second", reason="required_need_not_covered"),))
    with pytest.raises(ValueError, match="requested blocking"):
        SupplementalSupplyFoundation().merge(p, base, base_run, supplemental, supplemental_run, subset, merged_supply_run_id="r", merged_bundle_id="b")

    conflicting = bundle(p, supplemental_run, "bundle-supplemental", (asset("asset-base").model_copy(update={"file": asset("asset-new").file}),), ())
    empty_subset = SupplementalSupplyFoundation().supply_subset(p, (MaterialGap(need_id="second", reason="required_need_not_covered"),))
    with pytest.raises(ValueError, match="conflicts"):
        SupplementalSupplyFoundation().merge(p, base, base_run, conflicting, supplemental_run, empty_subset, merged_supply_run_id="r", merged_bundle_id="b")


def test_merge_keeps_unfinished_run_unfinished_instead_of_using_wall_clock() -> None:
    p = plan()
    started = datetime(2026, 9, 23, tzinfo=timezone.utc)
    base_run = SupplyRun(supply_run_id="run-base", plan_id=p.plan_id, started_at=started)
    supplemental_run = SupplyRun(supply_run_id="run-supplemental", plan_id=p.plan_id, started_at=started)
    base = bundle(p, base_run, "bundle-base", (), ())
    supplemental = bundle(p, supplemental_run, "bundle-supplemental", (), ())
    subset = SupplementalSupplyFoundation().supply_subset(p, ())
    result = SupplementalSupplyFoundation().merge(
        p, base, base_run, supplemental, supplemental_run, subset,
        merged_supply_run_id="run-merged", merged_bundle_id="bundle-merged",
    )
    assert result.supply_run.finished_at is None


def test_merge_deduplicates_supplemental_asset_by_content_identity() -> None:
    p = plan()
    base_run = run("run-base", "bundle-base")
    base_asset = asset("asset-base")
    base = bundle(p, base_run, "bundle-base", (base_asset,), (
        MaterialMatch(need_id="first", asset_id="asset-base", rank=1, qualified=True),
    ))
    supplemental_run = run("run-supplemental", "bundle-supplemental", source="second-source")
    duplicate = asset("asset-duplicate").model_copy(update={"file": base_asset.file.model_copy(update={"path": "materials/assets/asset-duplicate/original.mp4"})})
    supplemental = bundle(p, supplemental_run, "bundle-supplemental", (duplicate,), (
        MaterialMatch(need_id="second", asset_id="asset-duplicate", rank=1, qualified=True),
    ))
    subset = SupplementalSupplyFoundation().supply_subset(p, (MaterialGap(need_id="second", reason="required_need_not_covered"),))
    result = SupplementalSupplyFoundation().merge(
        p, base, base_run, supplemental, supplemental_run, subset,
        merged_supply_run_id="run-merged", merged_bundle_id="bundle-merged",
    )
    assert [item.asset_id for item in result.bundle.assets] == ["asset-base"]
    assert {(item.need_id, item.asset_id) for item in result.bundle.matches} == {("first", "asset-base"), ("second", "asset-base")}
