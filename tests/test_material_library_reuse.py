from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from easel.materials.application.library_reuse import LibraryReuseService
from easel.materials.domain import (
    CandidateSource,
    FileInfo,
    MaterialNeed,
    MaterialAsset,
    MediaType,
    NeedImportance,
    NeedIntent,
    NeedScope,
    NeedScopeType,
    RightsEvidence,
    RightsInfo,
    RightsStatus,
    TechnicalInfo,
    TechnicalStatus,
)
from easel.materials.library import LibraryScope, MaterialLibraryCatalog, PromotionConsent
from easel.materials.store import AttemptMaterialStore


def _scope() -> LibraryScope:
    return LibraryScope(tenant_id="tenant-1", creator_id="creator-1")


def _consent() -> PromotionConsent:
    return PromotionConsent(
        authorized=True,
        actor_id="creator-1",
        purpose="cross-attempt library storage",
        consented_at=datetime(2026, 9, 23, tzinfo=timezone.utc),
    )


def _need(*, media_type: MediaType = MediaType.IMAGE, constraints: dict | None = None) -> MaterialNeed:
    return MaterialNeed(
        need_id="need-current",
        scope=NeedScope(type=NeedScopeType.SCENE, ref="scene-1"),
        media_type=media_type,
        role="visual",
        intent=NeedIntent(description="city portrait"),
        importance=NeedImportance.REQUIRED,
        constraints=constraints or {},
    )


def _promote(
    tmp_path: Path,
    catalog: MaterialLibraryCatalog,
    *,
    asset_id: str,
    source_attempt_id: str,
    rights_status: RightsStatus = RightsStatus.KNOWN,
    technical_status: TechnicalStatus = TechnicalStatus.PASSED,
    media_type: MediaType = MediaType.IMAGE,
    body: bytes | None = None,
):
    body = body or asset_id.encode("utf-8")
    attempt_root = tmp_path / f"workspace-{source_attempt_id}-{asset_id}"
    attempt_root.mkdir()
    store = AttemptMaterialStore(attempt_root)
    suffix = ".jpg" if media_type is MediaType.IMAGE else ".mp4"
    mime = "image/jpeg" if media_type is MediaType.IMAGE else "video/mp4"
    locator = store.write_asset_bytes(asset_id, f"original{suffix}", body)
    asset = MaterialAsset(
        asset_id=asset_id,
        media_type=media_type,
        file=FileInfo(path=locator, sha256=hashlib.sha256(body).hexdigest(), size=len(body), mime=mime),
        source=CandidateSource(kind="stock", provider="fixture", provider_asset_id=asset_id, creator="artist"),
        rights=RightsInfo(
            status=rights_status,
            license_name="fixture license" if rights_status is RightsStatus.KNOWN else None,
            evidence=(RightsEvidence(kind="asset_license", reference=f"license:{asset_id}"),)
            if rights_status is not RightsStatus.UNKNOWN else (),
        ),
        technical=TechnicalInfo(status=technical_status, width=720, height=1280, mime=mime),
    )
    store.write_asset(asset)
    record = None
    if technical_status is TechnicalStatus.PASSED and rights_status is not RightsStatus.RESTRICTED:
        record = catalog.promote_attempt_asset(
            asset,
            store,
            scope=_scope(),
            source_attempt_id=source_attempt_id,
            consent=_consent(),
        )
    return store, asset, record


def test_usage_history_is_scoped_to_asset_creation_and_attempt_and_idempotent(tmp_path: Path) -> None:
    catalog = MaterialLibraryCatalog(tmp_path / "library")
    _, _, record = _promote(tmp_path, catalog, asset_id="asset-1", source_attempt_id="attempt-source")
    assert record is not None
    fixed_time = datetime.now(timezone.utc)

    first = catalog.record_usage(
        record.library_asset_id,
        scope=_scope(),
        creation_id="creation-1",
        attempt_id="attempt-2",
        need_ids=("need-b",),
        evidence_ref="selection/need-b.json",
        used_at=fixed_time,
    )
    merged = catalog.record_usage(
        record.library_asset_id,
        scope=_scope(),
        creation_id="creation-1",
        attempt_id="attempt-2",
        need_ids=("need-a", "need-b"),
        evidence_ref="selection/need-a.json",
        used_at=fixed_time,
    )

    assert first.usage_id == merged.usage_id
    assert merged.need_ids == ("need-a", "need-b")
    assert len(catalog.usage_for_asset(record.library_asset_id, scope=_scope())) == 1
    assert catalog.usage_for_attempt("creation-1", "attempt-2", scope=_scope()) == (merged,)
    assert catalog.get(record.library_asset_id, scope=_scope()).last_used_at == fixed_time
    assert catalog.usage_for_attempt("creation-1", "attempt-2", scope=LibraryScope(tenant_id="tenant-2", creator_id="creator-1")) == ()


def test_reuse_candidates_revalidate_scope_rights_and_technical_and_do_not_select(tmp_path: Path) -> None:
    catalog = MaterialLibraryCatalog(tmp_path / "library")
    _, _, eligible = _promote(tmp_path, catalog, asset_id="eligible", source_attempt_id="attempt-1")
    _, _, unknown_rights_record = _promote(
        tmp_path, catalog, asset_id="unknown", source_attempt_id="attempt-1"
    )
    assert unknown_rights_record is not None
    # A pre-gate catalog row may exist from an earlier release. Reuse must
    # still recheck its current Rights facts and refuse to admit UNKNOWN.
    payload = json.loads(json.dumps(unknown_rights_record.asset.model_dump(mode="json")))
    payload["rights"]["status"] = RightsStatus.UNKNOWN.value
    with catalog._connect() as connection:
        connection.execute(
            "UPDATE library_assets SET asset_json=? WHERE tenant_id=? AND creator_id=? AND library_asset_id=?",
            (json.dumps(payload), _scope().tenant_id, _scope().creator_id,
             unknown_rights_record.library_asset_id),
        )
    unknown_rights = catalog.get(unknown_rights_record.library_asset_id, scope=_scope())
    _, _, wrong_media = _promote(
        tmp_path, catalog, asset_id="video", source_attempt_id="attempt-1", media_type=MediaType.VIDEO
    )
    assert eligible is not None and wrong_media is not None
    service = LibraryReuseService(catalog)

    result = service.find_candidates(
        _need(), scope=_scope(), creation_id="creation-2", attempt_id="attempt-2"
    )

    assert [candidate.library_asset_id for candidate in result.candidates] == [eligible.library_asset_id]
    assert result.candidates[0].asset == eligible.asset
    assert result.candidates[0].selected_for_production is False
    assert result.candidates[0].rights_admission.admitted
    assert any(item.reason.startswith("rights_blocked:") for item in result.rejected)
    assert all(item.library_asset_id != wrong_media.library_asset_id for item in result.candidates)
    assert unknown_rights is not None


def test_current_attempt_is_excluded_and_usage_does_not_itself_grant_permission(tmp_path: Path) -> None:
    catalog = MaterialLibraryCatalog(tmp_path / "library")
    _, _, record = _promote(tmp_path, catalog, asset_id="asset-1", source_attempt_id="attempt-1")
    assert record is not None
    service = LibraryReuseService(catalog)

    same_attempt = service.find_candidates(
        _need(), scope=_scope(), creation_id="creation-1", attempt_id="attempt-1"
    )
    assert same_attempt.candidates == ()
    assert same_attempt.rejected[0].reason == "same_attempt_source"

    catalog.record_usage(
        record.library_asset_id,
        scope=_scope(),
        creation_id="creation-2",
        attempt_id="attempt-2",
        need_ids=("need-current",),
    )
    already_used = service.find_candidates(
        _need(), scope=_scope(), creation_id="creation-2", attempt_id="attempt-2"
    )
    assert already_used.candidates == ()
    assert already_used.rejected[0].reason == "already_used_in_attempt"
