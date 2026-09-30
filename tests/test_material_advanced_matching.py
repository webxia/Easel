from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

from easel.materials.application import (
    AdvancedMaterialMatcher,
    DirectorPreference,
    EvidenceKind,
    LibraryReuseService,
)
from easel.materials.application.intelligence import SemanticAnalysisOutput
from easel.materials.application.vlm_enrichment import LibraryVLMEnricher
from easel.materials.domain import (
    CandidateSource,
    ContinuityRef,
    FileInfo,
    IntelligenceStatus,
    MaterialNeed,
    MediaType,
    NeedImportance,
    NeedIntent,
    NeedScope,
    NeedScopeType,
    RightsEvidence,
    RightsInfo,
    RightsStatus,
    SemanticAnnotation,
    SemanticField,
    SemanticInfo,
    SemanticInference,
    TechnicalInfo,
    TechnicalStatus,
)
from easel.materials.library import (
    LibraryScope,
    MaterialLibraryCatalog,
    PromotionConsent,
)
from easel.materials.semantic_index import MaterialSemanticIndex, SearchMode
from easel.materials.store import AttemptMaterialStore


class FakeEmbedding:
    provider_id = "test-local"
    model_version = "v1"
    dimensions = 5
    tokens = {"portrait": 0, "city": 1, "ocean": 2, "night": 3, "music": 4}

    def embed(self, text: str) -> tuple[float, ...]:
        vector = [0.0] * self.dimensions
        for token in text.casefold().replace(":", " ").split():
            if token in self.tokens:
                vector[self.tokens[token]] += 1.0
        if not any(vector):
            vector[0] = 1.0
        return tuple(vector)


class FakeVLM:
    analyzer_id = "fixture-vlm"
    model_version = "fixture-7"

    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.calls = 0

    def analyze(self, path: Path, media_type: MediaType) -> SemanticAnalysisOutput:
        self.calls += 1
        assert path.is_file()
        if self.fail:
            raise RuntimeError("offline fixture failure")
        return SemanticAnalysisOutput(
            annotations=(
                SemanticAnnotation(field=SemanticField.ENVIRONMENT, value="rainy city street", confidence=0.93,
                                   evidence="fixture visual observation"),
                SemanticAnnotation(field=SemanticField.OBJECTS, value=("umbrella", "taxi"), confidence=0.88,
                                   evidence="fixture visual observation"),
            )
        )


def _need(*, continuity: tuple[ContinuityRef, ...] = ()) -> MaterialNeed:
    return MaterialNeed(
        need_id="need-city",
        scope=NeedScope(type=NeedScopeType.SCENE, ref="scene-1"),
        media_type=MediaType.IMAGE,
        role="visual",
        intent=NeedIntent(description="portrait city at night"),
        constraints={},
        continuity_refs=continuity,
        importance=NeedImportance.REQUIRED,
    )


def _register(
    tmp_path: Path,
    catalog: MaterialLibraryCatalog,
    *,
    asset_id: str,
    body: bytes,
    caption: str,
    tags: tuple[str, ...],
    references: tuple[str, ...] = (),
    attributes: dict[str, object] | None = None,
    observed: bool = True,
):
    attempt_root = tmp_path / f"attempt-{asset_id}"
    attempt_root.mkdir()
    store = AttemptMaterialStore(attempt_root)
    locator = store.write_asset_bytes(asset_id, "original.jpg", body)
    asset = {
        "asset_id": asset_id,
        "media_type": MediaType.IMAGE,
        "file": FileInfo(path=locator, sha256=hashlib.sha256(body).hexdigest(), size=len(body), mime="image/jpeg"),
        "source": CandidateSource(kind="fixture", provider="fixture", provider_asset_id=asset_id),
        "rights": RightsInfo(
            status=RightsStatus.KNOWN,
            license_name="fixture license",
            evidence=(RightsEvidence(kind="asset_license", reference=f"fixture:{asset_id}"),),
        ),
        "technical": TechnicalInfo(status=TechnicalStatus.PASSED, width=1080, height=1920, mime="image/jpeg"),
        "semantic": SemanticInfo(caption=caption, tags=tags, attributes=attributes or {},
            inferences=((SemanticInference(analyzer_id="fixture-observation", status=IntelligenceStatus.COMPLETE,
                annotations=(SemanticAnnotation(field=SemanticField.CAPTION, value=caption,
                                                confidence=0.95, evidence="fixture visual observation"),)),)
                if observed else ())),
        "lineage": {"references": references},
    }
    from easel.materials.domain import MaterialAsset

    material_asset = MaterialAsset(**asset)
    store.write_asset(material_asset)
    scope = LibraryScope(tenant_id="tenant-a", creator_id="creator-a")
    record = catalog.promote_attempt_asset(
        material_asset,
        store,
        scope=scope,
        source_attempt_id=f"source-{asset_id}",
        consent=PromotionConsent(
            authorized=True,
            actor_id="creator-a",
            purpose="fixture test",
            consented_at=datetime.now(timezone.utc),
        ),
    )
    return scope, record


def test_vlm_enrichment_is_optional_and_preserves_source_facts(tmp_path: Path) -> None:
    catalog = MaterialLibraryCatalog(tmp_path / "library")
    scope, record = _register(
        tmp_path, catalog, asset_id="city", body=b"city", caption="provider caption", tags=("source-tag",),
        observed=False,
    )
    disabled_analyzer = FakeVLM()
    disabled = LibraryVLMEnricher(catalog, disabled_analyzer).enrich(record, scope=scope)
    assert disabled.status is IntelligenceStatus.DISABLED
    assert disabled_analyzer.calls == 0

    analyzer = FakeVLM()
    enriched = LibraryVLMEnricher(catalog, analyzer, enabled=True).enrich(record, scope=scope)
    assert enriched.status is IntelligenceStatus.COMPLETE
    assert enriched.record.asset.semantic.caption == "provider caption"
    assert enriched.record.asset.semantic.tags == ("source-tag",)
    inference = enriched.record.asset.semantic.inferences[0]
    assert inference.analyzer_id == "fixture-vlm"
    assert inference.model_version == "fixture-7"
    assert inference.annotations[0].field is SemanticField.ENVIRONMENT
    candidates = LibraryReuseService(catalog).find_candidates(
        _need(), scope=scope, creation_id="creation-match", attempt_id="attempt-match"
    ).candidates
    matcher = AdvancedMaterialMatcher(MaterialSemanticIndex(catalog))
    matched = matcher.match(
        _need(), candidates, scope=scope,
        director_preferences=(DirectorPreference(
            field=SemanticField.ENVIRONMENT, preferred_values=("rainy city",)
        ),),
    ).matches[0]
    assert any(item.kind is EvidenceKind.AI_INFERENCE for item in matched.evidence.inferences)
    assert all(item.kind is EvidenceKind.SOURCE_FACT for item in matched.evidence.facts)
    failed = LibraryVLMEnricher(catalog, FakeVLM(fail=True), enabled=True).enrich(enriched.record, scope=scope)
    assert failed.status is IntelligenceStatus.FAILED
    assert failed.record == enriched.record


def test_semantic_director_and_multifamily_continuity_are_explainable(tmp_path: Path) -> None:
    catalog = MaterialLibraryCatalog(tmp_path / "library")
    scope, record = _register(
        tmp_path,
        catalog,
        asset_id="city",
        body=b"city",
        caption="portrait city at night",
        tags=("urban portrait",),
        references=("character:creator-avatar", "location:studio-a", "object:red-camera", "world:neo-noir", "music-family:pulse"),
        attributes={"style": "neo noir", "continuity_refs": ["character:creator-avatar"]},
    )
    catalog.record_usage(
        record.library_asset_id,
        scope=scope,
        creation_id="creation-old",
        attempt_id="attempt-old",
        need_ids=("old-need",),
        used_at=datetime.now(timezone.utc) + timedelta(seconds=1),
    )
    reuse = LibraryReuseService(catalog).find_candidates(
        _need(), scope=scope, creation_id="creation-new", attempt_id="attempt-new"
    )
    index = MaterialSemanticIndex(catalog)
    embedding = FakeEmbedding()
    record = catalog.get(record.library_asset_id, scope=scope)
    index.index_record(record, embedding)
    need = _need(continuity=(
        ContinuityRef(kind="character", ref="creator-avatar"),
        ContinuityRef(kind="location", ref="studio-a"),
        ContinuityRef(kind="object", ref="red-camera"),
        ContinuityRef(kind="world", ref="neo-noir"),
        ContinuityRef(kind="music-family", ref="pulse"),
    ))
    preferences = (DirectorPreference(field=SemanticField.STYLE, preferred_values=("neo noir",)),)
    matcher = AdvancedMaterialMatcher(index)
    result = matcher.match(
        need, reuse.candidates, scope=scope, embedding_provider=embedding,
        director_preferences=preferences, as_of=datetime.now(timezone.utc) + timedelta(days=32),
    )
    match = result.matches[0]
    assert match.library_asset_id == record.library_asset_id
    assert match.evidence.semantic_mode is SearchMode.VECTOR
    assert match.evidence.continuity_score == 1.0
    assert match.evidence.director_score == 1.0
    assert match.evidence.recent_usage_count == 0
    assert any(e.kind is EvidenceKind.LINEAGE for e in match.evidence.facts)
    assert match.selected_for_production is False
    assert result == matcher.match(
        need, reuse.candidates, scope=scope, embedding_provider=embedding,
        director_preferences=preferences, as_of=datetime.now(timezone.utc) + timedelta(days=32),
    )


def test_fallback_usage_penalty_and_hard_constraints_remain_distinct(tmp_path: Path) -> None:
    catalog = MaterialLibraryCatalog(tmp_path / "library")
    scope, first = _register(
        tmp_path, catalog, asset_id="a-city", body=b"a", caption="portrait city night", tags=("portrait",)
    )
    _, second = _register(
        tmp_path, catalog, asset_id="b-city", body=b"b", caption="portrait city night", tags=("portrait",)
    )
    selected_at = datetime.now(timezone.utc) + timedelta(seconds=1)
    catalog.record_usage(
        first.library_asset_id,
        scope=scope,
        creation_id="creation-old",
        attempt_id="attempt-old",
        need_ids=("need-city",),
        used_at=selected_at,
    )
    service = LibraryReuseService(catalog)
    candidates = service.find_candidates(
        _need(), scope=scope, creation_id="creation-new", attempt_id="attempt-new"
    ).candidates
    matcher = AdvancedMaterialMatcher(MaterialSemanticIndex(catalog))
    result = matcher.match(
        _need(), candidates, scope=scope, embedding_provider=None,
        as_of=selected_at + timedelta(seconds=1),
    )
    assert result.matches[0].library_asset_id == second.library_asset_id
    assert result.matches[0].evidence.semantic_mode is SearchMode.METADATA_FALLBACK
    reused_match = next(item for item in result.matches if item.library_asset_id == first.library_asset_id)
    assert reused_match.evidence.usage_penalty == 0.05
    assert reused_match.evidence.usage_history[0].kind is EvidenceKind.USAGE_HISTORY

    invalid_asset = candidates[0].asset.model_copy(update={
        "rights": RightsInfo(status=RightsStatus.UNKNOWN),
    })
    invalid_candidate = candidates[0].__class__(
        **{**candidates[0].__dict__, "asset": invalid_asset}
    )
    hard_result = matcher.match(
        _need(), (invalid_candidate,), scope=scope, embedding_provider=None,
    )
    assert hard_result.matches == ()
    assert any(reason.startswith("rights_blocked") for reason in hard_result.rejected[0].reasons)
