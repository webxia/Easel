from __future__ import annotations

from datetime import datetime, timezone

import pytest

from easel.materials.application.assembly import MaterialBundleAssembler
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
    SupplySourceResult,
    TechnicalInfo,
    TechnicalStatus,
    CoverageStatus,
)


def need(need_id: str, *, importance: NeedImportance, desired_options: int = 1) -> MaterialNeed:
    return MaterialNeed(
        need_id=need_id,
        scope=NeedScope(type=NeedScopeType.SCENE, ref=f"scene-{need_id}"),
        media_type=MediaType.VIDEO,
        role="broll",
        intent=NeedIntent(description=f"visual for {need_id}"),
        importance=importance,
        desired_options=desired_options,
    )


def plan() -> MaterialPlan:
    return MaterialPlan(
        plan_id="plan-assembly",
        creation_id="creation-1",
        attempt_id="attempt-1",
        needs=(
            need("required-covered", importance=NeedImportance.REQUIRED, desired_options=2),
            need("optional-missing", importance=NeedImportance.OPTIONAL),
            need("required-uncovered", importance=NeedImportance.REQUIRED),
        ),
    )


def asset(asset_id: str) -> MaterialAsset:
    return MaterialAsset(
        asset_id=asset_id,
        media_type=MediaType.VIDEO,
        file=FileInfo(
            path=f"materials/assets/{asset_id}/original.mp4",
            sha256=(asset_id[0] * 64),
            size=10,
            mime="video/mp4",
        ),
        source=CandidateSource(kind="fixture", provider="fixture", provider_asset_id=asset_id),
        rights=RightsInfo(
            status=RightsStatus.KNOWN,
            license_name="Fixture License",
            evidence=(RightsEvidence(kind="asset_license", reference=f"fixture:{asset_id}"),),
        ),
        technical=TechnicalInfo(status=TechnicalStatus.PASSED, duration_seconds=2, width=1920, height=1080),
    )


def run() -> SupplyRun:
    now = datetime(2026, 9, 23, tzinfo=timezone.utc)
    return SupplyRun(
        supply_run_id="run-assembly",
        plan_id="plan-assembly",
        started_at=now,
        finished_at=now,
        provider_results=(SupplySourceResult(source_id="fixture", status="COMPLETE", candidates_found=2),),
    )


def test_assembly_preserves_supply_facts_and_derives_coverage_without_editorial_fields() -> None:
    p = plan()
    bundle = MaterialBundleAssembler().assemble(
        p,
        run(),
        (asset("asset-a"),),
        (
            MaterialMatch(need_id="required-covered", asset_id="asset-a", rank=1, qualified=True),
            MaterialMatch(need_id="required-uncovered", asset_id="asset-a", rank=1, qualified=False),
        ),
        bundle_id="bundle-assembly",
    )

    assert bundle.revision == MaterialBundleAssembler.revision(bundle)
    assert [(item.need_id, item.status, item.qualified_assets) for item in bundle.coverage] == [
        ("required-covered", CoverageStatus.PARTIAL, 1),
        ("optional-missing", CoverageStatus.UNCOVERED, 0),
        ("required-uncovered", CoverageStatus.UNCOVERED, 0),
    ]
    roundtrip = type(bundle).from_json(bundle.to_json())
    assert roundtrip == bundle
    assert not hasattr(bundle, "timeline")
    assert not hasattr(bundle, "track")
    assert not hasattr(bundle, "build")


def test_assembly_rejects_matches_outside_plan_or_supply() -> None:
    p = plan()
    assembler = MaterialBundleAssembler()
    with pytest.raises(ValueError, match="outside plan"):
        assembler.assemble(
            p,
            run(),
            (asset("asset-a"),),
            (MaterialMatch(need_id="unknown", asset_id="asset-a", rank=1),),
            bundle_id="bundle-assembly",
        )
    with pytest.raises(ValueError, match="outside supply"):
        assembler.assemble(
            p,
            run(),
            (asset("asset-a"),),
            (MaterialMatch(need_id="required-covered", asset_id="asset-b", rank=1),),
            bundle_id="bundle-assembly",
        )
