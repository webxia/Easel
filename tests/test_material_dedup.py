from __future__ import annotations

from datetime import datetime, timezone

import pytest

from easel.materials.application.dedup import MaterialDeduplicator
from easel.materials.domain import (
    CandidateSource,
    FileInfo,
    MaterialAsset,
    MaterialMatch,
    MediaType,
    RightsEvidence,
    RightsInfo,
    RightsStatus,
    SemanticInfo,
    TechnicalInfo,
    TechnicalStatus,
)
from easel.materials.store import AttemptMaterialStore


def _asset(
    asset_id: str,
    *,
    provider: str = "pexels",
    native_id: str | None = None,
    source_page: str | None = None,
    sha: str | None = None,
    caption: str = "A person walking through an office at night",
    creator: str | None = "Creator",
    duration: float | None = 5.0,
    width: int | None = 1080,
    height: int | None = 1920,
    media_type: MediaType = MediaType.VIDEO,
    metadata_id: str | None = None,
) -> MaterialAsset:
    attrs = {"canonical_media_id": metadata_id} if metadata_id else {}
    evidence = RightsEvidence(
        kind="asset_license", reference=f"https://example.test/rights/{asset_id}",
        observed_at=datetime(2026, 9, 23, tzinfo=timezone.utc),
    )
    return MaterialAsset(
        asset_id=asset_id,
        media_type=media_type,
        file=FileInfo(
            path=f"materials/assets/{asset_id}/original.mp4",
            sha256=sha or ("a" if asset_id.endswith("1") else "b") * 64,
            size=1024,
            mime="video/mp4",
        ),
        source=CandidateSource(
            kind="stock", provider=provider, provider_asset_id=native_id or asset_id,
            source_page=source_page or f"https://example.test/{provider}/{asset_id}", creator=creator,
        ),
        rights=RightsInfo(status=RightsStatus.KNOWN, license_name="Fixture", evidence=(evidence,)),
        technical=TechnicalInfo(
            status=TechnicalStatus.PASSED, duration_seconds=duration, width=width, height=height,
        ),
        semantic=SemanticInfo(caption=caption, attributes=attrs),
    )


def _match(asset_id: str, rank: int, score: float, *, qualified: bool = True) -> MaterialMatch:
    return MaterialMatch(
        need_id="need-1", asset_id=asset_id, rank=rank, score=score,
        reasons=("hard_filter=passed", f"semantic_overlap={score:.3f}"), qualified=qualified,
    )


def test_provider_native_id_collapses_repeated_native_result_stably() -> None:
    first = _asset("asset-1", native_id="native-7", sha="1" * 64)
    second = _asset("asset-2", native_id="native-7", sha="2" * 64)

    result = MaterialDeduplicator().deduplicate_and_diversify(
        [_match("asset-2", 2, 0.7), _match("asset-1", 1, 0.9)], [first, second], top_k=5
    )

    assert [item.asset_id for item in result.unique_matches] == ["asset-1"]
    assert result.suppressed[0].representative_asset_id == "asset-1"
    assert result.suppressed[0].kind == "exact"
    assert "native" in result.suppressed[0].evidence


def test_canonical_url_removes_tracking_but_preserves_content_selectors() -> None:
    first = _asset("asset-1", source_page="https://EXAMPLE.test/video/7?utm_source=feed&edition=a", sha="1" * 64)
    tracked = _asset("asset-2", provider="pixabay", source_page="https://example.test/video/7?edition=a&utm_campaign=mail#preview", sha="2" * 64)
    selector = _asset(
        "asset-3", provider="local", source_page="https://example.test/video/7?edition=b",
        sha="3" * 64, caption="A lighthouse beside the sea", creator="Different Creator",
    )

    result = MaterialDeduplicator().deduplicate_and_diversify(
        [_match("asset-1", 1, 0.9), _match("asset-2", 2, 0.8), _match("asset-3", 3, 0.7)],
        [first, tracked, selector], top_k=5,
    )

    assert [item.asset_id for item in result.unique_matches] == ["asset-1", "asset-3"]
    assert "url" in result.suppressed[0].evidence


def test_sha256_collapses_cross_provider_copies_but_media_type_scopes_native_and_url() -> None:
    first = _asset("asset-1", provider="pexels", sha="c" * 64)
    second = _asset("asset-2", provider="pixabay", sha="c" * 64)
    image = _asset("asset-3", provider="local", sha="d" * 64, source_page=first.source.source_page, media_type=MediaType.IMAGE)

    result = MaterialDeduplicator().deduplicate_and_diversify(
        [_match("asset-1", 1, 0.9), _match("asset-2", 2, 0.8), _match("asset-3", 3, 0.7)],
        [first, second, image], top_k=5,
    )

    assert [item.asset_id for item in result.unique_matches] == ["asset-1", "asset-3"]
    assert "sha256" in result.suppressed[0].evidence


def test_redacted_acquisition_download_urls_are_exact_dedup_evidence(tmp_path) -> None:
    store = AttemptMaterialStore(tmp_path)
    first = _asset("asset-1", sha="1" * 64, caption="office coding scene", creator="Creator A")
    second = _asset("asset-2", provider="pixabay", sha="2" * 64, caption="mountain sunrise", creator="Creator B")
    store.write_acquisition_evidence("asset-1", {"final_url": "https://cdn.example/media/77?sig=[REDACTED]"})
    store.write_acquisition_evidence("asset-2", {"requested_url": "https://elsewhere.example/temp", "final_url": "https://cdn.example/media/77?sig=[REDACTED]"})

    result = MaterialDeduplicator(store).deduplicate_and_diversify(
        [_match("asset-1", 1, 0.9), _match("asset-2", 2, 0.8)], [first, second], top_k=5
    )

    assert [item.asset_id for item in result.unique_matches] == ["asset-1"]
    assert "url" in result.suppressed[0].evidence


def test_explicit_canonical_metadata_id_is_an_exact_dedup_key() -> None:
    first = _asset("asset-1", sha="1" * 64, metadata_id=" media-abc ")
    second = _asset("asset-2", provider="pixabay", sha="2" * 64, metadata_id="MEDIA-ABC")

    result = MaterialDeduplicator().deduplicate_and_diversify(
        [_match("asset-1", 1, 0.8), _match("asset-2", 2, 0.8)], [first, second], top_k=3
    )

    assert len(result.unique_matches) == 1
    assert result.suppressed[0].evidence == ("metadata_id",)


def test_near_duplicate_metadata_requires_duration_and_corroboration() -> None:
    first = _asset("asset-1", sha="1" * 64)
    similar = _asset(
        "asset-2", provider="pixabay", sha="2" * 64,
        caption="A person walking through an office late at night",
    )
    too_long = _asset("asset-3", provider="local", sha="3" * 64, duration=45.0)

    result = MaterialDeduplicator().deduplicate_and_diversify(
        [_match("asset-1", 1, 0.9), _match("asset-2", 2, 0.8), _match("asset-3", 3, 0.7)],
        [first, similar, too_long], top_k=5,
    )

    assert [item.asset_id for item in result.unique_matches] == ["asset-1", "asset-3"]
    assert result.suppressed[0].kind == "metadata"
    assert any(item.startswith("metadata_similarity=") for item in result.suppressed[0].evidence)


def test_diversity_adjusts_top_k_without_rewriting_match_evidence() -> None:
    first = _asset("asset-1", sha="1" * 64, caption="person walking office night corridor")
    similar = _asset("asset-2", provider="pixabay", sha="2" * 64, caption="person walking office night hallway")
    distinct = _asset("asset-3", provider="local", sha="3" * 64, caption="mountain sunrise snow forest")
    matches = [_match("asset-1", 1, 0.95), _match("asset-2", 2, 0.91), _match("asset-3", 3, 0.84)]

    result = MaterialDeduplicator().deduplicate_and_diversify(matches, [first, similar, distinct], top_k=3)

    assert len(result.unique_matches) == 3
    assert [item.asset_id for item in result.shortlist] == ["asset-1", "asset-3", "asset-2"]
    assert result.shortlist[0] == matches[0]
    assert result.shortlist[0].qualified is True
    assert "semantic_overlap=0.950" in result.shortlist[0].reasons


def test_unqualified_matches_are_rejected_and_duplicate_input_is_deterministic() -> None:
    asset = _asset("asset-1", sha="1" * 64)
    first = _match("asset-1", 1, 0.8)
    duplicate_record = _match("asset-1", 2, 0.9)
    unqualified = _match("asset-2", 3, 0.7, qualified=False)
    other = _asset("asset-2", sha="2" * 64)

    result = MaterialDeduplicator().deduplicate_and_diversify(
        [first, duplicate_record, unqualified], [asset, other], top_k=1
    )

    assert result.shortlist == (duplicate_record,)
    assert result.rejected == (("asset-2", "match_not_qualified"),)


@pytest.mark.parametrize("top_k", [0, -1, True])
def test_top_k_must_be_a_positive_integer(top_k: int) -> None:
    with pytest.raises(ValueError):
        MaterialDeduplicator().deduplicate_and_diversify([], [], top_k=top_k)
