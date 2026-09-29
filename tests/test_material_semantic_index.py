from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path

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
from easel.materials.library import LibraryScope, MaterialLibraryCatalog, PromotionConsent
from easel.materials.semantic_index import MaterialSemanticIndex, SearchMode, SemanticIndexError
from easel.materials.store import AttemptMaterialStore


class LocalFakeEmbedding:
    provider_id = "fixture-local"
    model_version = "fixture-1"
    dimensions = 4
    vocabulary = {"portrait": 0, "city": 1, "ocean": 2, "night": 3}

    def embed(self, text: str) -> tuple[float, ...]:
        vector = [0.0] * self.dimensions
        for token in text.casefold().replace(":", " ").replace(",", " ").split():
            if token in self.vocabulary:
                vector[self.vocabulary[token]] += 1.0
        return tuple(vector)


class BrokenEmbedding(LocalFakeEmbedding):
    def embed(self, text: str) -> tuple[float, ...]:
        raise RuntimeError("fixture failure")


def _register(tmp_path: Path, catalog: MaterialLibraryCatalog, *, asset_id: str, caption: str, tags: tuple[str, ...], body: bytes):
    root = tmp_path / f"attempt-{asset_id}"
    root.mkdir()
    store = AttemptMaterialStore(root)
    locator = store.write_asset_bytes(asset_id, "original.jpg", body)
    asset = MaterialAsset(
        asset_id=asset_id,
        media_type=MediaType.IMAGE,
        file=FileInfo(path=locator, sha256=hashlib.sha256(body).hexdigest(), size=len(body), mime="image/jpeg"),
        source=CandidateSource(kind="local", provider="fixture", provider_asset_id=asset_id, creator="local maker"),
        rights=RightsInfo(
            status=RightsStatus.KNOWN,
            license_name="fixture terms",
            evidence=(RightsEvidence(kind="asset_license", reference=f"asset:{asset_id}"),),
        ),
        technical=TechnicalInfo(status=TechnicalStatus.PASSED, width=640, height=960, mime="image/jpeg"),
        semantic=SemanticInfo(caption=caption, tags=tags),
    )
    store.write_asset(asset)
    scope = LibraryScope(tenant_id="tenant-a", creator_id="creator-a")
    consent = PromotionConsent(
        authorized=True,
        actor_id="creator-a",
        purpose="test fixture",
        consented_at=datetime(2026, 9, 23, tzinfo=timezone.utc),
    )
    record = catalog.promote_attempt_asset(
        asset,
        store,
        scope=scope,
        source_attempt_id=f"attempt-{asset_id}",
        consent=consent,
    )
    return scope, record


def test_fake_embedding_ranks_and_persists_scoped_semantic_vectors(tmp_path: Path) -> None:
    catalog = MaterialLibraryCatalog(tmp_path / "library")
    scope, portrait = _register(
        tmp_path, catalog, asset_id="portrait-1", caption="portrait city night", tags=("portrait", "city"), body=b"portrait"
    )
    _, ocean = _register(
        tmp_path, catalog, asset_id="ocean-1", caption="ocean night", tags=("ocean", "night"), body=b"ocean"
    )
    provider = LocalFakeEmbedding()
    index = MaterialSemanticIndex(catalog)

    assert index.index_record(portrait, provider).dimensions == provider.dimensions
    index.index_record(ocean, provider)
    result = MaterialSemanticIndex(catalog).search("portrait city", scope=scope, provider=provider)

    assert result.mode == SearchMode.VECTOR
    assert [hit.record.library_asset_id for hit in result.hits] == [portrait.library_asset_id, ocean.library_asset_id]
    assert result.hits[0].score > result.hits[1].score
    assert result.stale_asset_ids == ()
    assert result == MaterialSemanticIndex(catalog).search("portrait city", scope=scope, provider=provider)
    assert MaterialSemanticIndex(catalog).invalidate_record(portrait.library_asset_id, scope=scope)
    after_invalidation = MaterialSemanticIndex(catalog).search("portrait city", scope=scope, provider=provider)
    assert portrait.library_asset_id in after_invalidation.stale_asset_ids


def test_model_version_and_source_text_changes_are_detected_as_stale(tmp_path: Path) -> None:
    catalog = MaterialLibraryCatalog(tmp_path / "library")
    scope, record = _register(
        tmp_path, catalog, asset_id="portrait-1", caption="portrait city", tags=("portrait",), body=b"portrait"
    )
    index = MaterialSemanticIndex(catalog)
    old_model = LocalFakeEmbedding()
    index.index_record(record, old_model)
    new_model = LocalFakeEmbedding()
    new_model.model_version = "fixture-2"

    assert index.is_stale(record, new_model)
    result = index.search("portrait", scope=scope, provider=new_model)
    assert result.hits == ()
    assert result.stale_asset_ids == (record.library_asset_id,)

    changed_asset = record.asset.model_copy(update={"semantic": SemanticInfo(caption="ocean", tags=("ocean",))})
    changed_record = record.model_copy(update={"asset": changed_asset})
    assert index.is_stale(changed_record, old_model)


def test_disabled_or_failed_embedding_uses_deterministic_metadata_fallback(tmp_path: Path) -> None:
    catalog = MaterialLibraryCatalog(tmp_path / "library")
    scope, record = _register(
        tmp_path, catalog, asset_id="portrait-1", caption="portrait city at night", tags=("portrait", "city"), body=b"portrait"
    )
    index = MaterialSemanticIndex(catalog)

    disabled = index.search("portrait city", scope=scope, provider=None)
    failed = index.search("portrait city", scope=scope, provider=BrokenEmbedding())
    assert disabled.mode == SearchMode.METADATA_FALLBACK
    assert disabled.fallback_reason == "embedding_provider_disabled"
    assert failed.mode == SearchMode.METADATA_FALLBACK
    assert failed.fallback_reason == "embedding_provider_failed"
    assert disabled.hits[0].record.library_asset_id == record.library_asset_id
    assert failed.hits == disabled.hits


def test_bad_embedding_dimensions_are_rejected_when_indexing(tmp_path: Path) -> None:
    class BadEmbedding(LocalFakeEmbedding):
        def embed(self, text: str) -> tuple[float, ...]:
            return (1.0,)

    catalog = MaterialLibraryCatalog(tmp_path / "library")
    _, record = _register(
        tmp_path, catalog, asset_id="portrait-1", caption="portrait city", tags=("portrait",), body=b"portrait"
    )
    try:
        MaterialSemanticIndex(catalog).index_record(record, BadEmbedding())
    except SemanticIndexError as exc:
        assert "dimensions" in str(exc)
    else:
        raise AssertionError("invalid embedding dimensions should fail contract validation")
