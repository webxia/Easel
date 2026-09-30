from __future__ import annotations

from datetime import datetime, timezone

import pytest

from easel.materials.application.intelligence import IntelligenceStatus
from easel.materials.application.matching import MaterialMatcher
from easel.materials.domain import (
    CandidateSource,
    ContinuityRef,
    FileInfo,
    MaterialAsset,
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
    SemanticInference,
    SemanticInfo,
    TechnicalInfo,
    TechnicalStatus,
)


def _need(**constraints: object) -> MaterialNeed:
    return MaterialNeed(
        need_id="need-1",
        scope=NeedScope(type=NeedScopeType.SCENE, ref="scene-1"),
        media_type=MediaType.VIDEO,
        role="primary_visual",
        intent=NeedIntent(description="a person working in an office at night", function="establish environment"),
        duration_hint={"target_seconds": 4.0},
        constraints=dict(constraints),
        continuity_refs=(ContinuityRef(kind="location", ref="office-a"),),
        importance=NeedImportance.REQUIRED,
        desired_options=3,
    )


def _asset(
    asset_id: str,
    *,
    caption: str = "A person working in an office at night",
    rights_status: RightsStatus = RightsStatus.KNOWN,
    technical_status: TechnicalStatus = TechnicalStatus.PASSED,
    media_type: MediaType = MediaType.VIDEO,
    width: int | None = 1080,
    height: int | None = 1920,
    duration: float | None = 4.0,
    logo: bool | None = False,
    visible_text: tuple[str, ...] | None = (),
    identity_refs: tuple[str, ...] = ("location:office-a",),
    style: str | None = None,
    source_kind: str = "fixture",
) -> MaterialAsset:
    annotations = [SemanticAnnotation(field=SemanticField.CAPTION, value=caption, confidence=0.9,
                                      evidence="fixture visual observation")]
    if logo is not None:
        annotations.append(SemanticAnnotation(field=SemanticField.LOGO, value=logo, confidence=0.8,
                                              evidence="fixture visual inspection"))
    if visible_text is not None:
        annotations.append(SemanticAnnotation(field=SemanticField.VISIBLE_TEXT, value=visible_text, confidence=0.8,
                                              evidence="fixture visual inspection"))
    if style:
        annotations.append(SemanticAnnotation(field=SemanticField.STYLE, value=style, confidence=0.8))
    evidence = () if rights_status is RightsStatus.UNKNOWN else (
        RightsEvidence(kind="asset_license", reference=f"https://example.test/license/{asset_id}", observed_at=datetime(2026, 9, 23, tzinfo=timezone.utc)),
    )
    return MaterialAsset(
        asset_id=asset_id,
        media_type=media_type,
        file=FileInfo(path=f"materials/assets/{asset_id}/original.mp4", sha256="a" * 64, size=1024, mime="video/mp4"),
        source=CandidateSource(kind=source_kind, provider="fixture", provider_asset_id=asset_id, source_page="https://example.test/source", creator="Fixture Author"),
        rights=RightsInfo(status=rights_status, license_name="Fixture License" if rights_status is RightsStatus.KNOWN else None, evidence=evidence),
        technical=TechnicalInfo(status=technical_status, duration_seconds=duration, width=width, height=height, facts={"fps": 30.0}),
        semantic=SemanticInfo(inferences=(SemanticInference(analyzer_id="fixture", status=IntelligenceStatus.COMPLETE, annotations=tuple(annotations)),)),
        lineage={"references": identity_refs},
    )


@pytest.mark.parametrize(
    ("need", "asset", "reason"),
    [
        (_need(), _asset("wrong-type", media_type=MediaType.IMAGE), "media_type_mismatch"),
        (_need(), _asset("not-inspected", technical_status=TechnicalStatus.PENDING), "technical_inspection_not_passed"),
        (_need(), _asset("unknown-rights", rights_status=RightsStatus.UNKNOWN), "rights_blocked"),
        (_need(orientation="landscape"), _asset("wrong-orientation"), "orientation_mismatch"),
        (_need(min_width=1200), _asset("small-width"), "min_width_not_met"),
        (_need(min_duration_seconds=5), _asset("short"), "min_duration_not_met"),
        (_need(logo=False), _asset("logo-present", logo=True), "logo_forbidden"),
        (_need(text_in_frame=False), _asset("text-present", visible_text=("SALE",)), "visible_text_forbidden"),
        (_need(text_in_frame=False), _asset("text-unknown", visible_text=None), "visible_text_unknown"),
        (_need(required_identity_refs=("character:creator-avatar",)), _asset("identity-missing"), "required_identity_missing:character:creator-avatar"),
        (_need(required_source_kind="generative"), _asset("local-substitute", source_kind="local"), "required_source_kind_mismatch"),
        (_need(forbidden_source_kind="local"), _asset("local-music", source_kind="local"), "forbidden_source_kind_match"),
        (_need(allow_generation=False), _asset("generated-audio", source_kind="generative"), "generation_not_allowed"),
    ],
)
def test_any_hard_failure_excludes_asset_even_when_semantics_match(
    need: MaterialNeed, asset: MaterialAsset, reason: str
) -> None:
    result = MaterialMatcher().match(need, [asset])

    assert result.matches == ()
    assert result.rejected[0].asset_id == asset.asset_id
    assert any(item == reason or item.startswith(reason + ":") for item in result.rejected[0].reasons)


def test_matching_returns_decomposed_scores_reasons_and_multiple_ranked_alternatives() -> None:
    need = _need(preferred_style="documentary")
    exact = _asset("asset-a", style="documentary, natural")
    weak = _asset("asset-b", caption="A mountain in daylight", style="animation")

    result = MaterialMatcher().match(need, [weak, exact])

    assert [match.asset_id for match in result.matches] == ["asset-a"]
    assert result.rejected[0].asset_id == "asset-b"
    assert result.matches[0].scores.semantic is not None
    assert result.matches[0].scores.director is not None
    assert result.matches[0].scores.continuity == 1
    assert result.matches[0].scores.quality is not None
    assert "hard_filter=passed" in result.matches[0].reasons
    assert any(reason.startswith("semantic_overlap=") for reason in result.matches[0].reasons)
    assert all(match.qualified for match in result.matches)


def test_ranking_is_deterministic_and_does_not_mutate_need_or_choose_production_placement() -> None:
    need = _need()
    first = _asset("asset-a")
    second = _asset("asset-b")
    matcher = MaterialMatcher()

    one = matcher.match(need, [second, first])
    two = matcher.match(need, [first, second])

    assert [(m.asset_id, m.score, m.rank, m.reasons) for m in one.matches] == [
        (m.asset_id, m.score, m.rank, m.reasons) for m in two.matches
    ]
    assert need.need_id == "need-1"
    assert not hasattr(one.matches[0], "track")
    assert not hasattr(one.matches[0], "timeline")


def test_match_many_returns_a_separate_alternative_list_for_each_need() -> None:
    first = _need()
    second = first.model_copy(update={"need_id": "need-2", "intent": NeedIntent(description="mountain landscape")})

    results = MaterialMatcher().match_many([first, second], [_asset("office"), _asset("mountain", caption="A mountain landscape")])

    assert [result.need_id for result in results] == ["need-1", "need-2"]
    assert all(len(result.matches) == 1 for result in results)
    assert results[0].matches[0].asset_id == "office"
    assert results[1].matches[0].asset_id == "mountain"


def test_reused_visual_asset_needs_independent_observed_match_and_logo_clearance() -> None:
    office = _need(logo=False)
    mountain = office.model_copy(update={
        "need_id": "need-mountain", "intent": NeedIntent(description="mountain landscape"),
    })
    asset = _asset("office-image", caption="Person working in an office at night")
    results = MaterialMatcher().match_many([office, mountain], [asset])
    assert [match.asset_id for match in results[0].matches] == [asset.asset_id]
    assert results[1].matches == ()
    assert results[1].rejected[0].reasons == ("semantic_evidence_missing_or_unrelated",)

    logo_conflict = _asset("logo-image", logo=True)
    result = MaterialMatcher().match(office, [logo_conflict])
    assert result.matches == ()
    assert "logo_forbidden" in result.rejected[0].reasons


def test_verified_attribution_asset_remains_matchable() -> None:
    asset = _asset("credited")
    source_page = "https://example.test/source"
    asset = asset.model_copy(update={"rights": RightsInfo(
        status=RightsStatus.ATTRIBUTION_REQUIRED,
        license_name="CC BY 4.0",
        attribution_required=True,
        attribution_text=f"Fixture Author, {source_page}",
        evidence=(RightsEvidence(kind="asset_license", reference=source_page),),
    )})

    result = MaterialMatcher().match(_need(), [asset])

    assert [match.asset_id for match in result.matches] == ["credited"]
