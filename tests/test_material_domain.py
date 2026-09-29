from __future__ import annotations

import subprocess
import sys

import pytest
from pydantic import ValidationError

from easel.materials.domain import (
    Availability,
    CandidateSource,
    ContinuityRef,
    Coverage,
    CoverageStatus,
    DurationHint,
    FileInfo,
    MaterialAsset,
    MaterialBundle,
    MaterialGap,
    MaterialMatch,
    MaterialNeed,
    MaterialPlan,
    MaterialReadiness,
    MediaType,
    NeedImportance,
    NeedIntent,
    NeedScope,
    NeedScopeType,
    ReadinessStatus,
    RetrievalIntent,
    RightsInfo,
    RightsStatus,
    SupplyCandidate,
    TechnicalInfo,
    TechnicalStatus,
)


def need(*, need_id: str = "need-1", importance: NeedImportance = NeedImportance.REQUIRED) -> MaterialNeed:
    return MaterialNeed(
        need_id=need_id,
        scope=NeedScope(type=NeedScopeType.SCENE, ref="scene-1"),
        media_type=MediaType.VIDEO,
        role="primary_visual",
        intent=NeedIntent(description="A person working in an office", function="establish_environment"),
        duration_hint=DurationHint(target_seconds=4.0),
        constraints={"orientation": "portrait", "logo": False},
        continuity_refs=(ContinuityRef(kind="location", ref="office-a"),),
        importance=importance,
        desired_options=2,
    )


def asset(*, asset_id: str = "asset-1") -> MaterialAsset:
    return MaterialAsset(
        asset_id=asset_id,
        media_type=MediaType.VIDEO,
        file=FileInfo(
            path=f"materials/assets/{asset_id}/original.mp4",
            sha256="a" * 64,
            size=1024,
            mime="video/mp4",
        ),
        source=CandidateSource(kind="stock", provider="pexels", provider_asset_id="123"),
        rights=RightsInfo(
            status=RightsStatus.KNOWN,
            license_name="Provider terms",
            evidence=(),
        ),
        technical=TechnicalInfo(status=TechnicalStatus.PASSED, duration_seconds=8.0, width=1080, height=1920),
    )


def test_plan_rejects_invalid_enum_missing_identity_and_duplicate_need_ids() -> None:
    with pytest.raises(ValidationError):
        MaterialNeed(
            need_id="n",
            scope=NeedScope(type="scene", ref="s"),  # type: ignore[arg-type]
            media_type="animation",  # type: ignore[arg-type]
            role="visual",
            intent=NeedIntent(description="A scene"),
            importance="required",  # type: ignore[arg-type]
        )

    with pytest.raises(ValidationError):
        MaterialPlan(plan_id="", creation_id="c", attempt_id="a")

    with pytest.raises(ValidationError, match="unique"):
        MaterialPlan(
            plan_id="p",
            creation_id="c",
            attempt_id="a",
            needs=(need(), need()),
        )


@pytest.mark.parametrize("path", ["/tmp/asset.mp4", "../asset.mp4", "materials/../asset.mp4", "C:/asset.mp4"])
def test_asset_rejects_non_workspace_relative_paths(path: str) -> None:
    with pytest.raises(ValidationError):
        FileInfo(path=path, sha256="a" * 64, size=1, mime="video/mp4")


def test_malformed_bundle_references_and_duplicate_ids_fail() -> None:
    with pytest.raises(ValidationError, match="unknown asset_id"):
        MaterialBundle(
            bundle_id="b",
            plan_id="p",
            supply_run_id="r",
            coverage=(Coverage(need_id="n", status=CoverageStatus.UNCOVERED, qualified_assets=0),),
            matches=(MaterialMatch(need_id="n", asset_id="missing", rank=1),),
        )

    with pytest.raises(ValidationError, match="unique"):
        MaterialBundle(bundle_id="b", plan_id="p", supply_run_id="r", assets=(asset(), asset()))


def test_coverage_and_readiness_preserve_partial_optional_and_required_semantics() -> None:
    bundle = MaterialBundle(
        bundle_id="b",
        plan_id="p",
        supply_run_id="r",
        assets=(asset(),),
        matches=(MaterialMatch(need_id="required", asset_id="asset-1", rank=1, qualified=True),),
        coverage=(
            Coverage(need_id="required", status=CoverageStatus.COVERED, qualified_assets=1),
            Coverage(need_id="optional", status=CoverageStatus.UNCOVERED, qualified_assets=0),
        ),
    )
    assert bundle.coverage[1].status is CoverageStatus.UNCOVERED
    ready = MaterialReadiness(
        plan_id="p",
        bundle_id="b",
        status=ReadinessStatus.READY,
        required_needs=("required",),
        covered_required_needs=("required",),
    )
    assert ready.status is ReadinessStatus.READY
    assert MaterialGap(need_id="optional", reason="uncovered", blocking=False).blocking is False

    with pytest.raises(ValidationError, match="blocking Need"):
        MaterialReadiness(
            plan_id="p",
            bundle_id="b",
            status=ReadinessStatus.NOT_READY,
            required_needs=("required",),
        )


def test_provider_specific_fields_are_rejected_by_domain_contracts() -> None:
    with pytest.raises(ValidationError, match="extra"):
        SupplyCandidate(
            candidate_id="c",
            media_type=MediaType.IMAGE,
            source=CandidateSource(kind="stock"),
            availability=Availability.DISCOVERED,
            photographer_id=17,
            src={"original": "https://provider.invalid/file.jpg"},
        )


def test_importing_material_domain_does_not_load_hypit() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import easel.materials.domain; "
            "assert not any(name == 'hypit' or name.startswith('hypit.') for name in sys.modules)",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
