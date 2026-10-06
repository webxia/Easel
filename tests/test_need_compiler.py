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
    VoiceNeedSpec,
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
    assert "developer coding alone in a dark office cinematic low-key lighting" in first.semantic_queries
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
    assert intent.semantic_queries[0] == "developer coding alone in a dark office"
    assert "developer coding alone in a dark office documentary visual" in intent.semantic_queries
    assert intent.query_context["creator_context_terms"] == "science educator"


def test_compiler_rejects_blank_intent_and_unrepresentable_constraints() -> None:
    with pytest.raises(NeedCompilationError, match="empty intent"):
        NeedCompiler().compile(make_need(intent=NeedIntent(description="   ")))
    with pytest.raises(NeedCompilationError, match="scalar retrieval filter"):
        NeedCompiler().compile(make_need(constraints={"orientation": ["portrait", "landscape"]}))
    with pytest.raises(NeedCompilationError, match="constraints.voice_delivery.*audio/voice"):
        NeedCompiler().compile(make_need(constraints={"voice_delivery": {"pace_ratio": 1}}))
    with pytest.raises(NeedCompilationError, match="语速倍率"):
        NeedCompiler().compile(make_need(media_type=MediaType.AUDIO,
            modality_spec=VoiceNeedSpec(), constraints={"voice_delivery": {"pace_ratio": 10}}))


def test_compiler_rejects_conflicting_canonical_filters_and_invalid_context() -> None:
    with pytest.raises(NeedCompilationError, match="conflicts"):
        NeedCompiler().compile(make_need(constraints={"media_type": "image"}))
    with pytest.raises(NeedCompilationError, match="only strings"):
        NeedCompiler().compile(make_need(), creator_context_terms=("okay", 7))  # type: ignore[arg-type]


@pytest.mark.parametrize("search_hints", [None, ("piano", "calm piano"),
    ("piano", "calm piano", "soft piano", "quiet piano")])
def test_music_discovery_uses_sound_terms_preserving_director_and_gate_constraints(search_hints) -> None:
    source = make_need(media_type=MediaType.AUDIO, role="bgm",
        intent=NeedIntent(description="Gentle piano and soft synth pad instrumental, calm reflective mood, no vocals, suitable underneath narration at low volume for 36 seconds."),
        duration_hint=DurationHint(target_seconds=36),
        modality_spec=BgmNeedSpec(kind="bgm", instruments=("piano", "soft synth pad"), vocals_allowed=False),
        constraints={"required_source_kind": "stock", "allow_generation": False})
    before = source.to_json()
    compiler = NeedCompiler(search_terms={source.need_id: search_hints} if search_hints else None)
    result = compiler.compile(source)
    if search_hints:
        # Query recovery must change the query actually sent on the first page;
        # all sound preferences remain present without overwriting that choice.
        assert result.semantic_queries[0] == "piano"
        assert result.semantic_queries[1] == "piano soft synth pad instrumental background music"
        assert len(result.semantic_queries) <= 4
    else:
        assert result.semantic_queries[:3] == (
            "piano soft synth pad instrumental background music", "piano instrumental", "piano")
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


def test_english_query_keeps_chinese_intent_and_changes_only_discovery():
    need = make_need().model_copy(update={'intent': NeedIntent(description='桌面上的纸笔，不得出现标志'),
        'constraints': {'logo': False, 'search_query_en': 'notebook pen desk'}})
    before = need.to_json()
    intent = NeedCompiler().compile(need)
    assert intent.semantic_queries[0] == 'notebook pen desk'
    assert '桌面上的纸笔，不得出现标志' in intent.semantic_queries
    assert intent.filters == {'media_type': need.media_type.value, 'min_duration': need.duration_hint.target_seconds, 'logo': False}
    assert need.to_json() == before
    recovered = NeedCompiler(search_terms={need.need_id: ('pen notebook overhead',)}).compile(need)
    assert recovered.semantic_queries[0] == 'pen notebook overhead'
    with pytest.raises(NeedCompilationError):
        NeedCompiler().compile(need.model_copy(update={'constraints': {'search_query_en': '桌面'}}))


def test_stock_recovery_uses_complete_subject_hint_and_keeps_long_intent():
    description = '纸笔桌面。' + '保持同一必要表达和画面用途。' * 12
    need = make_need(intent=NeedIntent(description=description))
    intent = NeedCompiler().compile(need, creative_mode_terms=('muted documentary ' * 10,))
    assert intent.semantic_queries[0] == '纸笔桌面'
    assert intent.ranking_hints['intent_description'] == description
    assert need.intent.description == description
    recovered = NeedCompiler(search_terms={need.need_id: ('notebook desk',)}).compile(
        need, creative_mode_terms=('muted documentary',))
    assert recovered.semantic_queries[0] == 'notebook desk'
    assert recovered.filters == intent.filters
