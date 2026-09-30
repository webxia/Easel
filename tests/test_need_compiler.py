from __future__ import annotations

import pytest

from easel.materials.application.compiler import NeedCompilationError, NeedCompiler
from easel.materials.domain import (
    BgmNeedSpec,
    DurationHint,
    MaterialNeed,
    MediaType,
    NeedImportance,
    NeedIntent,
    NeedScope,
    NeedScopeType,
)


def make_need(**changes) -> MaterialNeed:
    fields = {
        "need_id": "scene03-visual-main",
        "scope": NeedScope(type=NeedScopeType.SCENE, ref="scene-03"),
        "media_type": MediaType.VIDEO,
        "role": "primary_visual",
        "intent": NeedIntent(
            description="  developer coding alone in a dark office  ",
            function="establish_environment",
        ),
        "duration_hint": DurationHint(target_seconds=4.0),
        "constraints": {"orientation": "portrait", "logo": False},
        "importance": NeedImportance.REQUIRED,
        "desired_options": 3,
    }
    fields.update(changes)
    return MaterialNeed(**fields)


def test_compiler_produces_deterministic_need_scoped_retrieval_intent() -> None:
    source = make_need()
    original = source.to_json()
    compiler = NeedCompiler()
    first = compiler.compile(
        source,
        creator_context_terms=("young adult", "independent creator"),
        creative_mode_terms=("cinematic low-key lighting",),
    )
    second = compiler.compile(
        source,
        creator_context_terms=("young adult", "independent creator"),
        creative_mode_terms=("cinematic low-key lighting",),
    )

    assert first == second
    assert first.need_id == source.need_id
    assert 2 <= len(first.semantic_queries) <= 4
    assert first.semantic_queries[0] == "developer coding alone in a dark office cinematic low-key lighting"
    assert "developer coding alone in a dark office" in first.semantic_queries
    assert first.filters == {
        "media_type": "video",
        "min_duration": 4.0,
        "orientation": "portrait",
        "logo": False,
    }
    assert first.negative_terms == ("logo",)
    assert first.query_context["scope_ref"] == "scene-03"
    assert source.to_json() == original


def test_compiler_includes_curated_creator_and_mode_terms_without_changing_need() -> None:
    intent = NeedCompiler().compile(
        make_need(),
        creator_context_terms=("  science educator ", "Science educator"),
        creative_mode_terms=("documentary visual",),
    )

    assert len(intent.semantic_queries) == 4
    assert "developer coding alone in a dark office science educator" in intent.semantic_queries
    assert intent.semantic_queries[0] == "developer coding alone in a dark office documentary visual"
    assert intent.query_context["creator_context_terms"] == "science educator"


def test_compiler_rejects_blank_intent_and_unrepresentable_constraints() -> None:
    with pytest.raises(NeedCompilationError, match="empty intent"):
        NeedCompiler().compile(make_need(intent=NeedIntent(description="   ")))
    with pytest.raises(NeedCompilationError, match="scalar retrieval filter"):
        NeedCompiler().compile(make_need(constraints={"orientation": ["portrait", "landscape"]}))


def test_compiler_rejects_conflicting_canonical_filters_and_invalid_context() -> None:
    with pytest.raises(NeedCompilationError, match="conflicts"):
        NeedCompiler().compile(make_need(constraints={"media_type": "image"}))
    with pytest.raises(NeedCompilationError, match="only strings"):
        NeedCompiler().compile(make_need(), creator_context_terms=("okay", 7))  # type: ignore[arg-type]


def test_music_discovery_uses_sound_terms_preserving_director_and_gate_constraints() -> None:
    source = make_need(media_type=MediaType.AUDIO, role="bgm",
        intent=NeedIntent(description="Gentle piano and soft synth pad instrumental, calm reflective mood, no vocals, suitable underneath narration at low volume for 36 seconds."),
        duration_hint=DurationHint(target_seconds=36),
        modality_spec=BgmNeedSpec(kind="bgm", instruments=("piano", "soft synth pad"), vocals_allowed=False),
        constraints={"required_source_kind": "stock", "allow_generation": False})
    before = source.to_json()
    result = NeedCompiler().compile(source)
    assert result.semantic_queries[:2] == ("piano instrumental", "piano")
    assert source.intent.description in result.semantic_queries
    assert result.filters == {"media_type": "audio", "min_duration": 36.0,
                              "required_source_kind": "stock", "allow_generation": False}
    assert source.to_json() == before


def test_creator_search_hints_preserve_need_filters_and_full_intent() -> None:
    source = make_need()
    hinted = NeedCompiler(search_terms={source.need_id: ("empty desk",)}).compile(source)
    assert hinted.semantic_queries[0] == "empty desk"
    assert source.intent.description.strip() in hinted.semantic_queries
    assert hinted.filters == NeedCompiler().compile(source).filters
    with pytest.raises(NeedCompilationError):
        NeedCompiler(search_terms={source.need_id: ("x" * 121,)}).compile(source)
