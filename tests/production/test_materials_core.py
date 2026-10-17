"""V1 library/reuse/index regression intents with entirely new V2 fixtures."""
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from PIL import Image
import pytest

from easel.materials.domain import (
    CandidateSource, MaterialNeed, MediaType, NeedImportance, NeedIntent,
    NeedScope, NeedScopeType, RightsEvidence, RightsInfo, RightsStatus, SemanticInfo,
    TechnicalStatus,
)
from easel.materials.library import LibraryVisibility, MaterialLibraryError, PromotionConsent, PromotionRejected, UseContext
from easel.materials.semantic_index import SemanticIndexError
from easel.materials.store import MaterialStoreError
from easel.production.materials import MaterialService


@pytest.fixture
def env(tmp_path):
    root = tmp_path.resolve()
    source = root / "inputs"
    source.mkdir()
    Image.new("RGB", (32, 24), (12, 80, 160)).save(source / "scene.png")
    return MaterialService(root / "library"), source, LibraryVisibility(profile_ref="profile-a"), UseContext(work_id="work-1")


def rights(**changes):
    return RightsInfo(status=RightsStatus.KNOWN, license_name="User-owned fixture",
        evidence=(RightsEvidence(kind="asset_user_permission", reference="input:fixture",
                                 observed_at=datetime(2026, 10, 17, tzinfo=timezone.utc)),), **changes)


def ingest(env, **changes):
    service, root, scope, context = env
    args = dict(source_root=root, relative_path="scene.png", visibility=scope, context=context,
        media_type=MediaType.IMAGE, source=CandidateSource(kind="user_upload", provider_asset_id="upload-1", creator="Fixture author"),
        rights=rights(), semantic=SemanticInfo(caption="A city at night", tags=("city", "night")))
    args.update(changes)
    return service.ingest_input(**args)


def need(**constraints):
    return MaterialNeed(need_id="scene-1-image", scope=NeedScope(type=NeedScopeType.SCENE, ref="scene-1"),
        media_type=MediaType.IMAGE, role="broll", intent=NeedIntent(description="city"),
        importance=NeedImportance.REQUIRED, constraints=constraints)


def consent(authorized=True):
    return PromotionConsent(authorized=authorized, actor_id="local-user", purpose="Reuse in this profile",
                            consented_at=datetime.now(timezone.utc))


def test_ingest_copies_verifies_and_persists_stable_identity(env):
    service, source, scope, context = env
    first = ingest(env)
    second = ingest(env)
    assert first.asset_ref == second.asset_ref
    assert first.local_path != source / "scene.png"
    assert first.local_path.read_bytes() == (source / "scene.png").read_bytes()
    assert first.asset.technical.status is TechnicalStatus.PASSED
    assert first.asset.technical.width == 32
    reopened = MaterialService(service.catalog.root)
    assert reopened.resolve(first.asset_ref, visibility=scope, context=context) == first
    assert len(service.catalog.usage_for_asset(first.asset_ref, scope=scope, context=context)) == 1


def test_scope_and_metadata_are_mandatory_and_exact(env):
    service, _, scope, context = env
    h = ingest(env)
    assert service.catalog.metadata_search(scope=scope, context=context, caption="a CITY at night", tags_all=("CITY",))[0].asset_ref == h.asset_ref
    for other in (LibraryVisibility(profile_ref="profile-b"), LibraryVisibility(owner_id="other", profile_ref="profile-a"), LibraryVisibility()):
        assert service.candidates(need(), visibility=other, context=context).candidates == ()
        with pytest.raises(MaterialLibraryError):
            service.resolve(h.asset_ref, visibility=other, context=context)


def test_explicit_promotion_permits_profile_reuse_without_auto_selection(env):
    service, _, scope, context = env
    h = ingest(env)
    other = UseContext(work_id="work-2")
    assert not service.candidates(need(), visibility=scope, context=other).candidates
    with pytest.raises(PromotionRejected):
        service.promote(h.asset_ref, visibility=scope, context=context, consent=consent(False))
    service.promote(h.asset_ref, visibility=scope, context=context, consent=consent())
    candidates = service.candidates(need(), visibility=scope, context=other)
    assert candidates.candidates[0].library_asset_id == h.asset_ref
    assert not candidates.candidates[0].selected_for_production
    assert len(service.catalog.usage_for_asset(h.asset_ref, scope=scope, context=context)) == 1
    service.select(h.asset_ref, need(), visibility=scope, context=other, reference_id="output-2")
    assert len(service.catalog.usage_for_asset(h.asset_ref, scope=scope, context=context)) == 2


def test_same_work_recovery_and_revision_can_reuse_selected_material(env):
    service, _, scope, context = env
    h = ingest(env)
    service.select(h.asset_ref, need(), visibility=scope, context=context, reference_id="output-1")
    service.select(h.asset_ref, need(), visibility=scope, context=context, reference_id="output-1")
    assert len(service.catalog.usage_for_asset(h.asset_ref, scope=scope, context=context)) == 2
    assert service.candidates(need(), visibility=scope, context=context).candidates
    service.select(h.asset_ref, need(), visibility=scope, context=context, reference_id="output-2")
    assert len(service.catalog.usage_for_asset(h.asset_ref, scope=scope, context=context)) == 3


def test_current_creation_only_survives_explicit_promotion(env):
    service, _, scope, context = env
    h = ingest(env, rights=rights(usage_constraints=("current_creation_only",)))
    service.promote(h.asset_ref, visibility=scope, context=context, consent=consent())
    assert service.candidates(need(), visibility=scope, context=context).candidates
    assert not service.candidates(need(), visibility=scope, context=UseContext(work_id="work-2")).candidates


def test_no_profile_is_work_only_and_later_classification_does_not_expand_rights(env):
    service, _, _, context = env
    anonymous = LibraryVisibility()
    h = ingest(env, visibility=anonymous)
    with pytest.raises(PromotionRejected):
        service.promote(h.asset_ref, visibility=anonymous, context=context, consent=consent())
    assert not service.candidates(need(), visibility=anonymous, context=UseContext(work_id="work-2")).candidates
    with pytest.raises(MaterialLibraryError):
        service.resolve(h.asset_ref, visibility=LibraryVisibility(profile_ref="new-profile"), context=context)
    assert service.resolve(h.asset_ref, visibility=anonymous, context=context)


def test_reference_only_does_not_become_renderable_on_promotion(env):
    service, _, scope, context = env
    reference = UseContext(work_id=context.work_id, purpose="reference")
    h = ingest(env, context=reference)
    service.promote(h.asset_ref, visibility=scope, context=reference, consent=consent())
    assert service.candidates(need(), visibility=scope, context=reference).candidates
    with pytest.raises(MaterialLibraryError, match="reference_only"):
        service.select(h.asset_ref, need(), visibility=scope, context=context, reference_id="output-1")


@pytest.mark.parametrize("status", [RightsStatus.UNKNOWN, RightsStatus.RESTRICTED])
def test_unknown_or_restricted_are_preserved_but_never_promoted_or_selected(env, status):
    service, _, scope, context = env
    h = ingest(env, rights=RightsInfo(status=status))
    assert h.asset.rights.status is status
    with pytest.raises(PromotionRejected):
        service.promote(h.asset_ref, visibility=scope, context=context, consent=consent())
    with pytest.raises(MaterialLibraryError):
        service.select(h.asset_ref, need(), visibility=scope, context=context, reference_id="output-1")


def test_same_bytes_different_rights_do_not_merge_permissions(env):
    allowed = ingest(env)
    unknown = ingest(env, rights=RightsInfo(status=RightsStatus.UNKNOWN))
    assert allowed.digest == unknown.digest
    assert allowed.asset_ref != unknown.asset_ref
    assert allowed.local_path == unknown.local_path


def test_new_purpose_rechecks_rights_and_work_constraints_override_need(env):
    service, _, scope, context = env
    h = ingest(env, rights=rights(usage_constraints=("editorial_only",)))
    service.promote(h.asset_ref, visibility=scope, context=context, consent=consent())
    assert service.candidates(need(), visibility=scope, context=UseContext(work_id="work-2")).candidates
    commercial = UseContext(work_id="work-2", constraints={"commercial_use": True})
    with pytest.raises(MaterialLibraryError, match="commercial"):
        service.select(h.asset_ref, need(commercial_use=False), visibility=scope, context=commercial, reference_id="output-2")


def test_attribution_is_a_required_export_dependency(env):
    service, _, scope, context = env
    source = CandidateSource(kind="stock", creator="Artist", source_page="https://example.test/media/1")
    credit = "Artist https://example.test/media/1"
    license_info = RightsInfo(status=RightsStatus.ATTRIBUTION_REQUIRED, license_name="CC-BY",
        attribution_required=True, attribution_text=credit, evidence=rights().evidence)
    h = ingest(env, source=source, rights=license_info)
    assert service.candidates(need(), visibility=scope, context=context).candidates
    with pytest.raises(MaterialLibraryError, match="attribution"):
        service.select(h.asset_ref, need(), visibility=scope, context=context, reference_id="output-1")
    selected = service.select(h.asset_ref, need(), visibility=scope, context=context, reference_id="output-1", enforce_attribution=True)
    assert selected.artifact_metadata()["attribution"]["credit_text"] == credit
    usage = service.catalog.usage_for_asset(h.asset_ref, scope=scope, context=context)
    assert any(item.attribution and item.attribution["credit_text"] == credit for item in usage)


def test_tampering_source_or_catalog_bytes_is_rejected(env):
    service, source, scope, context = env
    with pytest.raises(MaterialLibraryError, match="digest"):
        ingest(env, expected_sha256="a" * 64)
    h = ingest(env)
    h.local_path.write_bytes(b"tampered")
    with pytest.raises(MaterialLibraryError):
        service.resolve(h.asset_ref, visibility=scope, context=context)
    assert not service.candidates(need(), visibility=scope, context=context).candidates
    assert (source / "scene.png").exists()


@pytest.mark.parametrize("locator", ["../scene.png", "/scene.png", "C:\\scene.png", "x/../scene.png", "x//scene.png"])
def test_ingest_rejects_path_escape(env, locator):
    with pytest.raises(MaterialStoreError):
        ingest(env, relative_path=locator)


def test_symlink_input_and_catalog_component_are_rejected(env):
    service, source, scope, context = env
    (source / "alias.png").symlink_to(source / "scene.png")
    with pytest.raises(MaterialStoreError):
        ingest(env, relative_path="alias.png")
    h = ingest(env)
    h.local_path.unlink()
    h.local_path.symlink_to(source / "scene.png")
    with pytest.raises(MaterialStoreError):
        service.resolve(h.asset_ref, visibility=scope, context=context)


def test_corrupt_media_is_stored_as_failed_not_selected(env):
    service, source, scope, context = env
    (source / "broken.png").write_bytes(b"not an image")
    h = ingest(env, relative_path="broken.png")
    assert h.asset.technical.status is TechnicalStatus.FAILED
    with pytest.raises(MaterialLibraryError, match="technical"):
        service.select(h.asset_ref, need(), visibility=scope, context=context, reference_id="output-1")


class FixtureEmbedding:
    provider_id = "offline-test"
    model_version = "v1"
    dimensions = 2

    def embed(self, text):
        return (1.0, 0.2) if "city" in text.lower() else (0.2, 1.0)


def test_semantic_index_is_scoped_persisted_and_reports_stale_fallback(env):
    service, _, scope, context = env
    h = ingest(env)
    no_index = service.candidates(need(), visibility=scope, context=context, query="city", embedding_provider=FixtureEmbedding())
    assert no_index.search_mode == "METADATA_FALLBACK"
    assert no_index.fallback_reason == "embedding_index_incomplete"
    record = service.catalog.get(h.asset_ref, scope=scope, context=context)
    service.index.index_record(record, FixtureEmbedding())
    loaded = MaterialService(service.catalog.root)
    result = loaded.candidates(need(), visibility=scope, context=context, query="city", embedding_provider=FixtureEmbedding())
    assert result.search_mode == "VECTOR"
    assert result.candidates[0].library_asset_id == h.asset_ref
    assert not loaded.candidates(need(), visibility=LibraryVisibility(profile_ref="other"), context=context, query="city").candidates
    changed = FixtureEmbedding()
    changed.model_version = "v2"
    assert loaded.candidates(need(), visibility=scope, context=context, query="city", embedding_provider=changed).search_mode == "METADATA_FALLBACK"


def test_missing_or_failed_embedding_is_explicit_metadata_search(env):
    service, _, scope, context = env
    ingest(env)
    result = service.candidates(need(), visibility=scope, context=context, query="city")
    assert result.search_mode == "METADATA_FALLBACK" and result.fallback_reason == "embedding_provider_disabled"
    class Broken(FixtureEmbedding):
        def embed(self, text):
            raise RuntimeError("offline")
    result = service.candidates(need(), visibility=scope, context=context, query="city", embedding_provider=Broken())
    assert result.candidates and result.fallback_reason == "embedding_provider_failed"
    class Wrong(FixtureEmbedding):
        def embed(self, text):
            return (1.0,)
    record = service.catalog.metadata_search(scope=scope, context=context)[0]
    with pytest.raises(SemanticIndexError):
        service.index.index_record(record, Wrong())


def test_input_source_and_rights_urls_are_redacted_without_upgrading_rights(env):
    source = CandidateSource(kind="public", provider="fixture", source_page="https://user:secret@example.test/a?token=SECRET")
    info = RightsInfo(status=RightsStatus.UNKNOWN,
        evidence=(RightsEvidence(kind="public_page", reference="https://example.test/a?key=SECRET", summary="token=SECRET"),))
    h = ingest(env, source=source, rights=info)
    text = h.asset.model_dump_json()
    assert "SECRET" not in text and "user:secret" not in text
    assert h.asset.rights.status is RightsStatus.UNKNOWN


def test_v1_catalog_is_not_silently_imported(tmp_path):
    root = tmp_path.resolve()
    with sqlite3.connect(root / "catalog.db") as db:
        db.execute("CREATE TABLE library_assets(tenant_id TEXT, creator_id TEXT)")
    with pytest.raises(MaterialLibraryError, match="migration"):
        MaterialService(root)
