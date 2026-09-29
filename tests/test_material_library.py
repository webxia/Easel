from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path

import pytest

from easel.materials.domain import (
    CandidateSource,
    FileInfo,
    IntelligenceStatus,
    MaterialAsset,
    MediaType,
    RightsEvidence,
    RightsInfo,
    RightsStatus,
    SemanticInfo,
    TechnicalInfo,
    TechnicalStatus,
)
from easel.materials.library import (
    LibraryScope,
    MaterialLibraryCatalog,
    MaterialLibraryError,
    PromotionRejected,
    PromotionConsent,
)
from easel.materials.store import AttemptMaterialStore


def _attempt_asset(tmp_path: Path, *, asset_id: str = "asset-1") -> tuple[AttemptMaterialStore, MaterialAsset, bytes]:
    attempt_root = tmp_path / "attempt"
    attempt_root.mkdir()
    store = AttemptMaterialStore(attempt_root)
    body = b"fixture-material-bytes"
    digest = hashlib.sha256(body).hexdigest()
    locator = store.write_asset_bytes(asset_id, "original.jpg", body)
    asset = MaterialAsset(
        asset_id=asset_id,
        media_type=MediaType.IMAGE,
        file=FileInfo(path=locator, sha256=digest, size=len(body), mime="image/jpeg"),
        source=CandidateSource(
            kind="stock",
            provider="fixture-provider",
            provider_asset_id="provider-42",
            source_page="https://example.test/media/42",
            creator="Fixture Artist",
        ),
        rights=RightsInfo(
            status=RightsStatus.KNOWN,
            license_name="Fixture License",
            license_url="https://example.test/license",
            evidence=(RightsEvidence(kind="asset_license", reference="fixture-asset-terms"),),
        ),
        technical=TechnicalInfo(
            status=TechnicalStatus.PASSED,
            width=720,
            height=1280,
            mime="image/jpeg",
            facts={"sha256_verified": True},
        ),
        semantic=SemanticInfo(
            caption="A fixture portrait",
            tags=("fixture", "portrait"),
            intelligence_status=IntelligenceStatus.COMPLETE,
        ),
    )
    store.write_asset(asset)
    return store, asset, body


def _consent() -> PromotionConsent:
    return PromotionConsent(
        authorized=True,
        actor_id="creator-a",
        purpose="retain for future library search",
        consented_at=datetime(2026, 9, 23, tzinfo=timezone.utc),
    )


def test_promote_persists_content_addressed_object_and_all_material_facts(tmp_path: Path) -> None:
    store, asset, body = _attempt_asset(tmp_path)
    store.write_acquisition_evidence(asset.asset_id, {
        "method": "provider_direct_url", "provider": "fixture-provider",
        "sha256": asset.file.sha256,
    })
    store.write_generation_record("gen-fixture", {
        "generation_id": "gen-fixture", "asset_id": asset.asset_id,
        "provider": "fixture-provider", "status": "COMPLETE",
    })
    catalog = MaterialLibraryCatalog(tmp_path / "material-library")
    scope = LibraryScope(tenant_id="workspace-a", creator_id="creator-a")

    record = catalog.promote_attempt_asset(
        asset, store, scope=scope, source_attempt_id="attempt-1",
        source_creation_id="creation-1", consent=_consent(),
    )

    assert record.library_asset_id == f"lib-{asset.file.sha256}"
    assert record.physical_locator == f"objects/{asset.file.sha256}.jpg"
    assert record.asset == asset
    assert record.source_attempt_id == "attempt-1"
    assert record.source_creation_id == "creation-1"
    assert record.provenance["acquisition"]["method"] == "provider_direct_url"
    assert record.provenance["generation_lineage"][0]["generation_id"] == "gen-fixture"
    assert catalog.resolve_physical_locator(record).read_bytes() == body
    assert catalog.get(record.library_asset_id, scope=scope) == record
    assert catalog.find_by_content(asset.file.sha256, scope=scope) == record

    assert catalog.database_path.name == "catalog.db"


def test_catalog_scope_isolation_and_exact_metadata_lookup(tmp_path: Path) -> None:
    store, asset, _ = _attempt_asset(tmp_path)
    catalog = MaterialLibraryCatalog(tmp_path / "library")
    first = LibraryScope(tenant_id="tenant-a", creator_id="creator-a")
    other_creator = LibraryScope(tenant_id="tenant-a", creator_id="creator-b")
    other_tenant = LibraryScope(tenant_id="tenant-b", creator_id="creator-a")

    record = catalog.promote_attempt_asset(asset, store, scope=first, source_attempt_id="attempt-1", consent=_consent())
    assert catalog.list_scope(scope=first, media_type=MediaType.IMAGE, rights_status=RightsStatus.KNOWN) == (record,)
    assert catalog.list_scope(scope=other_creator) == ()
    assert catalog.list_scope(scope=other_tenant) == ()
    assert catalog.get(record.library_asset_id, scope=other_creator, missing_ok=True) is None
    assert catalog.find_by_content(asset.file.sha256, scope=other_tenant, missing_ok=True) is None


def test_repeated_promotion_is_stable_and_does_not_globalize_attempt_data(tmp_path: Path) -> None:
    store, asset, _ = _attempt_asset(tmp_path)
    catalog = MaterialLibraryCatalog(tmp_path / "library")
    scope = LibraryScope(tenant_id="tenant-a", creator_id="creator-a")

    first = catalog.promote_attempt_asset(asset, store, scope=scope, source_attempt_id="attempt-1", consent=_consent())
    second = catalog.promote_attempt_asset(asset, store, scope=scope, source_attempt_id="attempt-2", consent=_consent())

    assert second == first
    assert second.source_attempt_id == "attempt-1"
    assert len(catalog.list_scope(scope=scope)) == 1


def test_promotion_rejects_tampered_attempt_bytes(tmp_path: Path) -> None:
    store, asset, _ = _attempt_asset(tmp_path)
    path = store.resolve_asset_locator(asset.file.path)
    path.write_bytes(b"tampered")
    catalog = MaterialLibraryCatalog(tmp_path / "library")

    with pytest.raises(MaterialLibraryError, match="content identity"):
        catalog.promote_attempt_asset(
            asset,
            store,
            scope=LibraryScope(tenant_id="tenant-a", creator_id="creator-a"),
            source_attempt_id="attempt-1",
            consent=_consent(),
        )


@pytest.mark.parametrize("status", [RightsStatus.UNKNOWN, RightsStatus.RESTRICTED])
def test_promotion_never_bypasses_unknown_or_restricted_rights(tmp_path: Path, status: RightsStatus) -> None:
    store, asset, _ = _attempt_asset(tmp_path)
    asset = asset.model_copy(update={"rights": asset.rights.model_copy(update={"status": status})})
    catalog = MaterialLibraryCatalog(tmp_path / "library")
    with pytest.raises(PromotionRejected, match="UNKNOWN or RESTRICTED"):
        catalog.promote_attempt_asset(
            asset, store, scope=LibraryScope(tenant_id="tenant-a", creator_id="creator-a"),
            source_attempt_id="attempt-1", source_creation_id="creation-1", consent=_consent(),
        )


def test_catalog_persists_across_instances_and_keeps_timezone_timestamps(tmp_path: Path) -> None:
    store, asset, _ = _attempt_asset(tmp_path)
    root = tmp_path / "library"
    scope = LibraryScope(tenant_id="tenant-a", creator_id="creator-a")
    first = MaterialLibraryCatalog(root).promote_attempt_asset(asset, store, scope=scope, source_attempt_id="attempt-1", consent=_consent())

    reopened = MaterialLibraryCatalog(root)
    loaded = reopened.get(first.library_asset_id, scope=scope)
    assert loaded is not None
    assert loaded.created_at.tzinfo is not None
    assert loaded.updated_at.tzinfo is not None
    assert loaded.asset.rights.evidence[0].kind == "asset_license"
    assert loaded.asset.technical.status is TechnicalStatus.PASSED
    assert loaded.asset.semantic.tags == ("fixture", "portrait")
