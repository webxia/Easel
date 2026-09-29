from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path

import pytest

from easel.materials.domain import (
    CandidateSource,
    FileInfo,
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
    PromotionConsent,
    PromotionRejected,
)
from easel.materials.store import AttemptMaterialStore


def _source(tmp_path: Path, *, asset_id: str = "asset-1", body: bytes = b"fixture"):
    root = tmp_path / asset_id
    root.mkdir()
    store = AttemptMaterialStore(root)
    locator = store.write_asset_bytes(asset_id, "original.jpg", body)
    asset = MaterialAsset(
        asset_id=asset_id,
        media_type=MediaType.IMAGE,
        file=FileInfo(path=locator, sha256=hashlib.sha256(body).hexdigest(), size=len(body), mime="image/jpeg"),
        source=CandidateSource(kind="stock", provider="fixture", provider_asset_id=asset_id, creator="artist"),
        rights=RightsInfo(
            status=RightsStatus.KNOWN,
            license_name="fixture terms",
            evidence=(RightsEvidence(kind="asset_license", reference=f"license:{asset_id}"),),
        ),
        technical=TechnicalInfo(status=TechnicalStatus.PASSED, width=600, height=900, mime="image/jpeg"),
        semantic=SemanticInfo(caption="City portrait at dusk", tags=("portrait", "city", asset_id)),
    )
    store.write_asset(asset)
    return store, asset


def _consent(authorized: bool = True) -> PromotionConsent:
    return PromotionConsent(
        authorized=authorized,
        actor_id="creator-1",
        purpose="library catalog search",
        consented_at=datetime(2026, 9, 23, tzinfo=timezone.utc),
    )


def test_promotion_requires_explicit_consent_and_passing_technical_inspection(tmp_path: Path) -> None:
    store, asset = _source(tmp_path)
    catalog = MaterialLibraryCatalog(tmp_path / "library")
    scope = LibraryScope(tenant_id="tenant-1", creator_id="creator-1")

    with pytest.raises(PromotionRejected, match="consent"):
        catalog.promote_attempt_asset(
            asset, store, scope=scope, source_attempt_id="attempt-1", consent=_consent(False)
        )

    pending = asset.model_copy(update={"technical": TechnicalInfo(status=TechnicalStatus.PENDING)})
    store.write_asset(pending)
    with pytest.raises(PromotionRejected, match="inspection"):
        catalog.promote_attempt_asset(
            pending, store, scope=scope, source_attempt_id="attempt-1", consent=_consent()
        )
    assert catalog.list_scope(scope=scope) == ()


def test_restricted_asset_stays_attempt_local_and_promotion_records_consent(tmp_path: Path) -> None:
    store, asset = _source(tmp_path)
    catalog = MaterialLibraryCatalog(tmp_path / "library")
    scope = LibraryScope(tenant_id="tenant-1", creator_id="creator-1")
    restricted = asset.model_copy(update={"rights": RightsInfo(status=RightsStatus.RESTRICTED)})
    store.write_asset(restricted)
    with pytest.raises(PromotionRejected, match="Restricted"):
        catalog.promote_attempt_asset(
            restricted, store, scope=scope, source_attempt_id="attempt-1", consent=_consent()
        )

    store.write_asset(asset)
    promoted = catalog.promote_attempt_asset(
        asset, store, scope=scope, source_attempt_id="attempt-1", consent=_consent()
    )
    assert promoted.promotion_consent == _consent()
    assert promoted.asset.rights.evidence[0].reference == "license:asset-1"
    assert catalog.resolve_physical_locator(promoted).is_file()


def test_metadata_search_supports_exact_structured_filters_and_scope(tmp_path: Path) -> None:
    catalog = MaterialLibraryCatalog(tmp_path / "library")
    scope = LibraryScope(tenant_id="tenant-1", creator_id="creator-1")
    other_scope = LibraryScope(tenant_id="tenant-1", creator_id="creator-2")
    first_store, first_asset = _source(tmp_path, asset_id="asset-1", body=b"first")
    second_store, second_asset = _source(tmp_path, asset_id="asset-2", body=b"second")
    first = catalog.promote_attempt_asset(first_asset, first_store, scope=scope, source_attempt_id="attempt-a", consent=_consent())
    catalog.promote_attempt_asset(second_asset, second_store, scope=scope, source_attempt_id="attempt-b", consent=_consent())

    result = catalog.metadata_search(
        scope=scope,
        media_type=MediaType.IMAGE,
        rights_status=RightsStatus.KNOWN,
        technical_status=TechnicalStatus.PASSED,
        provider="fixture",
        creator="artist",
        tags_all=("portrait",),
        tags_any=("asset-1",),
        caption="CITY PORTRAIT AT DUSK",
    )
    assert result == (first,)
    assert catalog.metadata_search(scope=other_scope) == ()
    assert catalog.metadata_search(scope=scope, sha256=first.asset.file.sha256) == (first,)
    first_order = tuple(item.library_asset_id for item in catalog.metadata_search(scope=scope))
    assert tuple(item.library_asset_id for item in catalog.metadata_search(scope=scope)) == first_order
    assert catalog.metadata_search(scope=scope, tags_any=("asset-2",), limit=1)[0].asset.asset_id == "asset-2"
