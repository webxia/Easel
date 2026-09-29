"""Cheap, provider-aware candidate eligibility and pre-ranking."""

from __future__ import annotations

import re
from dataclasses import dataclass

from easel.materials.domain import Availability, MediaType, RetrievalIntent, RightsStatus, SupplyCandidate


@dataclass(frozen=True)
class RankedCandidate:
    candidate: SupplyCandidate
    score: float
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class CandidatePreRankResult:
    selected: tuple[RankedCandidate, ...]
    rejected: tuple[tuple[str, str], ...]


class CandidatePreRanker:
    """Apply only evidence-backed hard filters, then select a bounded Top-N.

    Missing metadata and UNKNOWN rights remain unknown. This stage does not
    admit rights, inspect media bytes, perform semantic matching, or acquire.
    """

    _TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
    _QUERY_FIELDS = {
        "pexels": ("description",),
        "pixabay": ("tags",),
        "local": ("filename",),
    }
    _DOWNLOADABLE = frozenset({Availability.DIRECT_DOWNLOADABLE, Availability.RESOLVABLE})

    def select(
        self,
        candidates: tuple[SupplyCandidate, ...] | list[SupplyCandidate],
        intent: RetrievalIntent,
        *,
        top_n: int,
    ) -> CandidatePreRankResult:
        if not isinstance(top_n, int) or isinstance(top_n, bool) or top_n < 1:
            raise ValueError("top_n must be a positive integer")

        eligible: list[tuple[int, SupplyCandidate]] = []
        rejected: list[tuple[str, str]] = []
        seen_ids: set[str] = set()
        provider_positions: dict[str, int] = {}
        provider_rank: dict[str, tuple[int, int]] = {}

        for input_index, candidate in enumerate(candidates):
            provider = candidate.source.provider or ""
            reason = self._ineligible_reason(candidate, intent)
            if reason:
                rejected.append((candidate.candidate_id, reason))
                continue
            # Stable source identity only. Cross-provider/file-content
            # deduplication belongs to P0-14 and needs stronger evidence.
            if candidate.candidate_id in seen_ids:
                rejected.append((candidate.candidate_id, "duplicate_candidate_id"))
                continue
            seen_ids.add(candidate.candidate_id)
            position = provider_positions.get(provider, 0)
            provider_positions[provider] = position + 1
            provider_rank[candidate.candidate_id] = (position, 1)
            eligible.append((input_index, candidate))

        provider_counts: dict[str, int] = {}
        for _, candidate in eligible:
            provider = candidate.source.provider or ""
            provider_counts[provider] = provider_counts.get(provider, 0) + 1

        ranked: list[tuple[int, RankedCandidate]] = []
        query_terms = self._query_terms(intent)
        preferred_provider = intent.ranking_hints.get("preferred_provider")
        for input_index, candidate in eligible:
            provider = candidate.source.provider or ""
            fields = self._QUERY_FIELDS.get(provider, ())
            evidence = " ".join(
                value
                for field in fields
                if isinstance((value := candidate.metadata.get(field)), str)
            )
            evidence_terms = set(self._tokens(evidence))
            overlap = (len(query_terms & evidence_terms) / len(query_terms)) if query_terms else 0.0
            score = overlap * 100.0
            reasons: list[str] = []
            if evidence_terms and query_terms:
                reasons.append(f"provider_metadata_query_overlap={overlap:.3f}")
            else:
                reasons.append("provider_relevance_metadata=unknown")

            if provider in {"pexels", "pixabay"} and provider_counts.get(provider, 0) > 1:
                ordinal = provider_rank[candidate.candidate_id][0]
                order_score = max(0.0, 1.0 - ordinal / provider_counts[provider])
                score += order_score * 10.0
                reasons.append(f"provider_return_order={ordinal + 1}")

            if isinstance(preferred_provider, str) and provider == preferred_provider:
                score += 20.0
                reasons.append("preferred_provider")

            self._add_dimension_reasons(candidate, intent, reasons)
            if candidate.rights_hint.status is RightsStatus.UNKNOWN:
                reasons.append("rights_hint=UNKNOWN; admission_not_decided")
            elif candidate.rights_hint.status is RightsStatus.RESTRICTED:
                # Normally filtered earlier; keep this defensive explanation.
                reasons.append("rights_hint=RESTRICTED")

            ranked.append((input_index, RankedCandidate(candidate, round(score, 6), tuple(reasons))))

        ranked.sort(key=lambda item: (-item[1].score, item[0], item[1].candidate.candidate_id))
        selected = tuple(item for _, item in ranked[:top_n])
        return CandidatePreRankResult(selected=selected, rejected=tuple(rejected))

    @classmethod
    def _ineligible_reason(cls, candidate: SupplyCandidate, intent: RetrievalIntent) -> str | None:
        expected_type = intent.filters.get("media_type")
        if expected_type and candidate.media_type.value != expected_type:
            return "media_type_mismatch"
        if candidate.need_id is not None and candidate.need_id != intent.need_id:
            return "need_id_mismatch"
        if candidate.availability not in cls._DOWNLOADABLE:
            return "not_acquirable_in_p0"
        if candidate.rights_hint.status is RightsStatus.RESTRICTED:
            return "rights_hint_restricted"

        width = cls._number(candidate.metadata.get("width"))
        height = cls._number(candidate.metadata.get("height"))
        duration = cls._number(candidate.metadata.get("duration_seconds"))
        min_width = cls._number(intent.filters.get("min_width"))
        min_height = cls._number(intent.filters.get("min_height"))
        min_duration = cls._number(intent.filters.get("min_duration"))
        max_duration = cls._number(intent.filters.get("max_duration"))
        if width is not None and min_width is not None and width < min_width:
            return "below_min_width"
        if height is not None and min_height is not None and height < min_height:
            return "below_min_height"
        if duration is not None and min_duration is not None and duration < min_duration:
            return "below_min_duration"
        if duration is not None and max_duration is not None and duration > max_duration:
            return "above_max_duration"

        orientation = intent.filters.get("orientation")
        if width is not None and height is not None:
            if orientation == "landscape" and width <= height:
                return "orientation_mismatch"
            if orientation == "portrait" and height <= width:
                return "orientation_mismatch"
            if orientation == "square" and width != height:
                return "orientation_mismatch"
        return None

    @classmethod
    def _add_dimension_reasons(
        cls, candidate: SupplyCandidate, intent: RetrievalIntent, reasons: list[str]
    ) -> None:
        width = cls._number(candidate.metadata.get("width"))
        height = cls._number(candidate.metadata.get("height"))
        orientation = intent.filters.get("orientation")
        if width is not None and height is not None:
            if orientation and ((orientation == "landscape" and width > height)
                                or (orientation == "portrait" and height > width)
                                or (orientation == "square" and width == height)):
                reasons.append(f"orientation_match={orientation}")
            min_width = cls._number(intent.filters.get("min_width"))
            min_height = cls._number(intent.filters.get("min_height"))
            if min_width is not None or min_height is not None:
                reasons.append(f"dimensions={int(width)}x{int(height)}")
        duration = cls._number(candidate.metadata.get("duration_seconds"))
        if duration is not None and ("min_duration" in intent.filters or "max_duration" in intent.filters):
            reasons.append(f"duration_seconds={duration:g}")

    @classmethod
    def _query_terms(cls, intent: RetrievalIntent) -> set[str]:
        terms: set[str] = set()
        for query in intent.semantic_queries:
            terms.update(cls._tokens(query))
        terms.difference_update({"a", "an", "and", "for", "in", "of", "the", "to", "with"})
        return terms

    @classmethod
    def _tokens(cls, value: str) -> tuple[str, ...]:
        return tuple(token.casefold() for token in cls._TOKEN_RE.findall(value))

    @staticmethod
    def _number(value: object) -> float | None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        return float(value)
