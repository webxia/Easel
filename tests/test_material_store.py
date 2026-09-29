from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from easel.materials.domain import (
    CandidateSource,
    FileInfo,
    MaterialAsset,
    MaterialBundle,
    MaterialNeed,
    MaterialPlan,
    MediaType,
    NeedImportance,
    NeedIntent,
    NeedScope,
    NeedScopeType,
    RightsInfo,
    RightsStatus,
    SupplyRun,
    SupplySourceResult,
)
from easel.materials.store import AttemptMaterialStore, AttemptMaterialStoreError


def sample_plan() -> MaterialPlan:
    return MaterialPlan(
        plan_id="plan-1",
        creation_id="creation-1",
        attempt_id="attempt-1",
        needs=(
            MaterialNeed(
                need_id="need-1",
                scope=NeedScope(type=NeedScopeType.SCENE, ref="scene-1"),
                media_type=MediaType.VIDEO,
                role="primary_visual",
                intent=NeedIntent(description="A person walking in a city"),
                importance=NeedImportance.REQUIRED,
            ),
        ),
    )


def sample_asset() -> MaterialAsset:
    return MaterialAsset(
        asset_id="asset-1",
        media_type=MediaType.VIDEO,
        file=FileInfo(
            path="materials/assets/asset-1/original.mp4",
            sha256="b" * 64,
            size=12,
            mime="video/mp4",
        ),
        source=CandidateSource(kind="local", creator="user"),
        rights=RightsInfo(status=RightsStatus.UNKNOWN),
    )


def test_round_trip_plan_bundle_asset_and_supply_run(tmp_path: Path) -> None:
    attempt_root = tmp_path / "attempt"
    attempt_root.mkdir()
    store = AttemptMaterialStore(attempt_root)
    plan = sample_plan()
    asset = sample_asset()
    bundle = MaterialBundle(bundle_id="bundle-1", plan_id=plan.plan_id, supply_run_id="run-1", assets=(asset,))
    run = SupplyRun(
        supply_run_id="run-1",
        plan_id=plan.plan_id,
        started_at=datetime(2026, 9, 22, tzinfo=timezone.utc),
        provider_results=(SupplySourceResult(source_id="local", status="complete", acquired_assets=1),),
        result_bundle_id=bundle.bundle_id,
    )

    assert store.write_plan(plan) == "materials/plan.json"
    assert store.read_plan() == plan
    assert store.write_asset(asset) == asset.file.path
    assert store.read_asset(asset.asset_id) == asset
    assert store.write_bundle(bundle) == "materials/bundle.json"
    assert store.read_bundle() == bundle
    assert store.write_supply_run(run) == "materials/supply-runs/run-1/result.json"
    assert store.read_supply_run(run.supply_run_id) == run
    assert (tmp_path / "attempt/materials/assets/asset-1/source.json").is_file()
    assert (tmp_path / "attempt/materials/assets/asset-1/analysis.json").is_file()
    source_sidecar = json.loads((tmp_path / "attempt/materials/assets/asset-1/source.json").read_text())
    assert source_sidecar["rights"]["status"] == RightsStatus.UNKNOWN.value


@pytest.mark.parametrize(
    "locator",
    ["/etc/passwd", "../escape", "materials/../escape", "materials\\assets\\asset.mp4", "materials//plan.json", "~/x"],
)
def test_rejects_noncanonical_and_outside_locators(tmp_path: Path, locator: str) -> None:
    root = tmp_path / "attempt"
    root.mkdir()
    store = AttemptMaterialStore(root)
    with pytest.raises(AttemptMaterialStoreError):
        store.resolve_asset_locator(locator)


def test_store_rejects_symlink_materials_root_and_nested_escape(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "attempt"
    root.mkdir()
    (root / "materials").symlink_to(outside, target_is_directory=True)
    with pytest.raises(AttemptMaterialStoreError, match="Symlinks"):
        AttemptMaterialStore(root)

    root2 = tmp_path / "attempt-2"
    root2.mkdir()
    store = AttemptMaterialStore(root2)
    (root2 / "materials/assets/asset-1").symlink_to(outside, target_is_directory=True)
    with pytest.raises(AttemptMaterialStoreError, match="Symlinks"):
        store.resolve_asset_locator("materials/assets/asset-1/original.mp4")


def test_store_resolves_workspace_asset_to_relative_hypit_source_path(tmp_path: Path) -> None:
    root = tmp_path / "attempt"
    (root / "productions/easel-authoring").mkdir(parents=True)
    authoring = root / "productions/easel-authoring/main.svml"
    authoring.write_text("<!-- fixture -->\n", encoding="utf-8")
    store = AttemptMaterialStore(root)
    asset = sample_asset()
    asset_path = root / asset.file.path
    asset_path.parent.mkdir(parents=True)
    asset_path.write_bytes(b"fixture")

    resolved = store.resolve_asset_locator(asset.file.path)
    hypit_src = store.hypit_source_path(asset, "productions/easel-authoring/main.svml")
    assert resolved == asset_path
    assert not Path(hypit_src).is_absolute()
    assert (authoring.parent / hypit_src).resolve() == asset_path.resolve()
    assert hypit_src.endswith("materials/assets/asset-1/original.mp4")


def test_attempt_stores_are_isolated(tmp_path: Path) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first_root.mkdir()
    second_root.mkdir()
    first = AttemptMaterialStore(first_root)
    second = AttemptMaterialStore(second_root)
    first.write_plan(sample_plan())

    assert first.read_plan() == sample_plan()
    with pytest.raises(AttemptMaterialStoreError, match="not found"):
        second.read_plan()


def test_asset_record_must_keep_its_locator_under_its_own_asset_directory(tmp_path: Path) -> None:
    root = tmp_path / "attempt"
    root.mkdir()
    store = AttemptMaterialStore(root)
    asset = sample_asset().model_copy(update={"file": FileInfo(
        path="materials/assets/asset-2/original.mp4",
        sha256="b" * 64,
        size=12,
        mime="video/mp4",
    )})
    with pytest.raises(AttemptMaterialStoreError, match="asset directory"):
        store.write_asset(asset)


def test_hypit_source_path_rejects_media_extensions_outside_v027_contract(tmp_path: Path) -> None:
    root = tmp_path / "attempt"
    root.mkdir()
    store = AttemptMaterialStore(root)
    unsupported = sample_asset().model_copy(update={"file": FileInfo(
        path="materials/assets/asset-1/original.mkv",
        sha256="b" * 64,
        size=12,
        mime="video/x-matroska",
    )})
    file_path = root / unsupported.file.path
    file_path.parent.mkdir(parents=True)
    file_path.write_bytes(b"fixture")

    with pytest.raises(AttemptMaterialStoreError, match="not supported by Hypit media:video"):
        store.hypit_source_path(unsupported, "productions/easel-authoring/main.svml")
