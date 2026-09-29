from __future__ import annotations

import pytest

from easel.materials.application.prerank import CandidatePreRanker
from easel.materials.domain import (
    Availability,
    CandidateSource,
    MediaType,
    RetrievalIntent,
    RightsStatus,
    SupplyCandidate,
)
from easel.materials.domain.models import PreviewInfo, RightsHint


def intent(**filters: str | int | float | bool) -> RetrievalIntent:
    return RetrievalIntent(
        need_id="need-1",
        semantic_queries=("night city street",),
        filters={"media_type": "video", **filters},
    )


def candidate(
    candidate_id: str,
    *,
    provider: str = "pixabay",
    media_type: MediaType = MediaType.VIDEO,
    availability: Availability = Availability.DIRECT_DOWNLOADABLE,
    metadata: dict | None = None,
    rights: RightsStatus = RightsStatus.UNKNOWN,
    need_id: str | None = "need-1",
) -> SupplyCandidate:
    return SupplyCandidate(
        candidate_id=candidate_id,
        need_id=need_id,
        media_type=media_type,
        source=CandidateSource(kind="stock", provider=provider, provider_asset_id=candidate_id),
        preview=PreviewInfo(url="https://example.test/preview"),
        availability=availability,
        rights_hint=RightsHint(status=rights),
        metadata=metadata or {},
    )


def test_provider_aware_metadata_and_search_order_explain_ranking() -> None:
    first = candidate("p-1", metadata={"tags": "other"})
    second = candidate("p-2", metadata={"tags": "night city street"})

    result = CandidatePreRanker().select([first, second], intent(), top_n=2)

    assert [item.candidate.candidate_id for item in result.selected] == ["p-2", "p-1"]
    assert any("provider_metadata_query_overlap=1.000" in reason for reason in result.selected[0].reasons)
    assert any(reason == "provider_return_order=2" for reason in result.selected[0].reasons)
    assert "rights_hint=UNKNOWN; admission_not_decided" in result.selected[0].reasons
    assert result.rejected == ()


def test_provider_specific_fields_are_used_without_fabricating_missing_metadata() -> None:
    pexels = candidate("pexels:1", provider="pexels", metadata={"description": "night city"})
    pixabay = candidate("pixabay:1", provider="pixabay", metadata={"tags": "street"})
    empty = candidate("pexels:2", provider="pexels", metadata={})

    result = CandidatePreRanker().select([empty, pixabay, pexels], intent(), top_n=3)

    by_id = {item.candidate.candidate_id: item for item in result.selected}
    assert by_id["pexels:1"].score > by_id["pixabay:1"].score > by_id["pexels:2"].score
    assert "provider_relevance_metadata=unknown" in by_id["pexels:2"].reasons


@pytest.mark.parametrize(
    ("filters", "metadata", "expected"),
    [
        ({"orientation": "portrait"}, {"width": 1920, "height": 1080}, "orientation_mismatch"),
        ({"min_width": 1000}, {"width": 640, "height": 480}, "below_min_width"),
        ({"min_height": 700}, {"width": 1280, "height": 600}, "below_min_height"),
        ({"min_duration": 5}, {"duration_seconds": 4}, "below_min_duration"),
        ({"max_duration": 5}, {"duration_seconds": 8}, "above_max_duration"),
    ],
)
def test_confirmed_metadata_constraint_violation_is_filtered(filters, metadata, expected) -> None:
    result = CandidatePreRanker().select(
        [candidate("bad", metadata=metadata)], intent(**filters), top_n=2
    )
    assert result.selected == ()
    assert result.rejected == (("bad", expected),)


def test_missing_metadata_is_not_fabricated_or_used_to_reject_candidate() -> None:
    result = CandidatePreRanker().select(
        [candidate("unknown-facts")], intent(orientation="portrait", min_duration=3), top_n=1
    )
    assert len(result.selected) == 1
    assert result.rejected == ()


def test_ineligible_and_restricted_candidates_never_enter_top_n() -> None:
    candidates = [
        candidate("preview", availability=Availability.PREVIEWABLE),
        candidate("wrong-type", media_type=MediaType.IMAGE),
        candidate("wrong-need", need_id="other-need"),
        candidate("restricted", rights=RightsStatus.RESTRICTED),
        candidate("eligible"),
    ]
    result = CandidatePreRanker().select(candidates, intent(), top_n=10)
    assert [item.candidate.candidate_id for item in result.selected] == ["eligible"]
    assert {reason for _, reason in result.rejected} == {
        "not_acquirable_in_p0", "media_type_mismatch", "need_id_mismatch", "rights_hint_restricted"
    }


def test_top_n_is_bounded_and_duplicate_identity_is_only_duplicate_filter() -> None:
    candidates = [candidate("same"), candidate("same"), candidate("other")]
    result = CandidatePreRanker().select(candidates, intent(), top_n=1)
    assert len(result.selected) == 1
    assert result.rejected == (("same", "duplicate_candidate_id"),)
    with pytest.raises(ValueError, match="top_n"):
        CandidatePreRanker().select(candidates, intent(), top_n=0)
