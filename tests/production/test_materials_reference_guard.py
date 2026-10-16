"""Retained input/output references protect library objects across works."""
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

from PIL import Image
import pytest

from easel.materials.domain import CandidateSource, MediaType, RightsInfo, RightsStatus, RightsEvidence
from easel.materials.library import LibraryVisibility, UseContext, PromotionConsent, ReferenceProtected
from easel.production.materials import MaterialService


@pytest.fixture
def material(tmp_path):
    root = tmp_path.resolve()
    inputs = root / "inputs"
    inputs.mkdir()
    Image.new("RGB", (10, 10), "red").save(inputs / "a.png")
    service = MaterialService(root / "library")
    visibility, context = LibraryVisibility(profile_ref="profile-a"), UseContext(work_id="work-1")
    kwargs = dict(source_root=inputs, relative_path="a.png", visibility=visibility, context=context,
        media_type=MediaType.IMAGE, source=CandidateSource(kind="user_upload", provider_asset_id="input-1"),
        rights=RightsInfo(status=RightsStatus.KNOWN, license_name="owned", evidence=(RightsEvidence(kind="asset_user_permission", reference="input-1"),)))
    handle = service.ingest_input(**kwargs)
    return service, visibility, context, handle, kwargs


def test_shared_reference_blocks_deletion_until_each_version_releases(material):
    service, visibility, context, handle, _ = material
    service.promote(handle.asset_ref, visibility=visibility, context=context, consent=PromotionConsent(
        authorized=True, actor_id="user", purpose="reuse", consented_at=datetime.now(timezone.utc)))
    other = UseContext(work_id="work-2")
    service.catalog.record_usage(handle.asset_ref, scope=visibility, context=context, reference_id="accepted-output-1")
    service.catalog.record_usage(handle.asset_ref, scope=visibility, context=other, reference_id="accepted-output-2")
    with pytest.raises(ReferenceProtected):
        service.delete(handle.asset_ref, visibility=visibility, context=context)
    service.release_reference(handle.asset_ref, "input:" + handle.asset_ref, visibility=visibility, context=context)
    service.release_reference(handle.asset_ref, "accepted-output-1", visibility=visibility, context=context)
    # Releasing another work's reference from this context is a no-op.
    service.release_reference(handle.asset_ref, "accepted-output-2", visibility=visibility, context=context)
    with pytest.raises(ReferenceProtected):
        service.delete(handle.asset_ref, visibility=visibility, context=context)
    service.release_reference(handle.asset_ref, "accepted-output-2", visibility=visibility, context=other)
    service.delete(handle.asset_ref, visibility=visibility, context=context)
    assert handle.local_path.exists()  # Private blob reconciliation owns eventual cleanup.
    assert service.catalog.collect_deleted()
    assert not handle.local_path.exists()


def test_delete_never_unlinks_original_or_shared_bytes(material):
    service, visibility, context, handle, kwargs = material
    second = service.ingest_input(**{**kwargs, "context": UseContext(work_id="work-2")})
    assert second.local_path == handle.local_path
    service.release_reference(handle.asset_ref, "input:" + handle.asset_ref, visibility=visibility, context=context)
    service.delete(handle.asset_ref, visibility=visibility, context=context)
    assert service.catalog.collect_deleted() == ()
    assert (kwargs["source_root"] / kwargs["relative_path"]).is_file()
    assert service.resolve(second.asset_ref, visibility=visibility, context=UseContext(work_id="work-2")).local_path.is_file()


def test_concurrent_duplicate_ingest_has_one_record_and_input_reference(material):
    service, visibility, context, handle, kwargs = material
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: service.ingest_input(**kwargs), range(8)))
    assert {r.asset_ref for r in results} == {handle.asset_ref}
    assert len(service.catalog.metadata_search(scope=visibility, context=context)) == 1
    assert len(service.catalog.usage_for_asset(handle.asset_ref, scope=visibility, context=context)) == 1
