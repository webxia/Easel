from __future__ import annotations

import pytest

from easel.materials.application.compiler import NeedCompilationError, NeedCompiler
from easel.materials.domain import (
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
    assert first.semantic_queries[0] == "developer coding alone in a dark office"
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
    assert intent.semantic_queries[2] == "developer coding alone in a dark office science educator"
    assert intent.semantic_queries[3] == "developer coding alone in a dark office documentary visual"
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
