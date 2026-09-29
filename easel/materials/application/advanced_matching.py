"""Explainable Library matching using semantic, director, and continuity evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from easel.materials.application.matching import MaterialMatcher
from easel.materials.application.library_reuse import LibraryReuseCandidate
from easel.materials.domain import IntelligenceStatus, MaterialNeed, SemanticField
from easel.materials.library import LibraryScope
from easel.materials.semantic_index import (
    EmbeddingProvider,
    MaterialSemanticIndex,
    SearchMode,
)


class DirectorPreference(BaseModel):
    """Soft preference supplied by the caller; it never edits Need or intent."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    field: SemanticField
    preferred_values: tuple[str, ...] = Field(min_length=1)
    weight: float = Field(default=1.0, ge=0, le=1)

    @field_validator("preferred_values")
    @classmethod
    def nonblank_preferences(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not value.strip() for value in values):
            raise ValueError("director preference values must not be blank")
        return tuple(value.strip() for value in values)


class EvidenceKind(str, Enum):
    SOURCE_FACT = "SOURCE_FACT"
    AI_INFERENCE = "AI_INFERENCE"
    LINEAGE = "LINEAGE"
    USAGE_HISTORY = "USAGE_HISTORY"
    SEMANTIC_INDEX = "SEMANTIC_INDEX"


@dataclass(frozen=True)
class MatchEvidence:
    kind: EvidenceKind
    reference: str
    detail: str


@dataclass(frozen=True)
class AdvancedMatchEvidence:
    semantic_score: float | None
    semantic_mode: SearchMode
    director_score: float | None
    continuity_score: float | None
    usage_penalty: float
    recent_usage_count: int
    facts: tuple[MatchEvidence, ...]
    inferences: tuple[MatchEvidence, ...]
    usage_history: tuple[MatchEvidence, ...]
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class AdvancedMaterialMatch:
    need_id: str
    library_asset_id: str
    asset_id: str
    rank: int
    score: float
    evidence: AdvancedMatchEvidence
    selected_for_production: bool = False


@dataclass(frozen=True)
class AdvancedMatchRejection:
    library_asset_id: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class AdvancedMatchingResult:
    need_id: str
    matches: tuple[AdvancedMaterialMatch, ...]
    rejected: tuple[AdvancedMatchRejection, ...]
    stale_index_asset_ids: tuple[str, ...]


class AdvancedMaterialMatcher:
    """Rank eligible Library candidates without gaining Production selection authority."""

    _RECENT_WINDOW = timedelta(days=30)
    _MAX_USAGE_PENALTY = 0.20

    def __init__(
        self,
        semantic_index: MaterialSemanticIndex,
        *,
        baseline_matcher: MaterialMatcher | None = None,
    ):
        self.semantic_index = semantic_index
        self.baseline_matcher = baseline_matcher or MaterialMatcher()

    def match(
        self,
        need: MaterialNeed,
        candidates: tuple[LibraryReuseCandidate, ...] | list[LibraryReuseCandidate],
        *,
        scope: LibraryScope,
        embedding_provider: EmbeddingProvider | None = None,
        director_preferences: tuple[DirectorPreference, ...] = (),
        as_of: datetime | None = None,
    ) -> AdvancedMatchingResult:
        now = as_of or datetime.now(timezone.utc)
        if now.utcoffset() is None:
            raise ValueError("as_of must include a timezone")

        # Reuse discovery supplies current scope/rights/technical eligibility;
        # rerun MaterialMatcher so this layer cannot weaken P0 hard constraints.
        assets = tuple(candidate.asset for candidate in candidates)
        baseline = self.baseline_matcher.match(need, assets)
        baseline_by_asset_id = {item.asset_id: item for item in baseline.matches}
        rejected = tuple(
            AdvancedMatchRejection(
                library_asset_id=next(
                    (candidate.library_asset_id for candidate in candidates if candidate.asset.asset_id == item.asset_id),
                    item.asset_id,
                ),
                reasons=item.reasons,
            )
            for item in baseline.rejected
        )
        query = " ".join(
            [need.intent.description]
            + [f"{ref.kind} {ref.ref}" for ref in need.continuity_refs]
            + [value for preference in director_preferences for value in preference.preferred_values]
        )
        indexed = self.semantic_index.search(query, scope=scope, provider=embedding_provider, limit=1000)
        semantic_by_id = {
            hit.record.library_asset_id: max(0.0, min(1.0, (hit.score + 1.0) / 2.0))
            if indexed.mode is SearchMode.VECTOR else max(0.0, min(1.0, hit.score))
            for hit in indexed.hits
        }

        ranked: list[tuple[LibraryReuseCandidate, float, AdvancedMatchEvidence]] = []
        for candidate in candidates:
            base = baseline_by_asset_id.get(candidate.asset.asset_id)
            if base is None:
                continue
            semantic_score = semantic_by_id.get(candidate.library_asset_id)
            if semantic_score is None:
                semantic_score = base.scores.semantic
            director_score, facts, inferences = self._director_score(candidate, director_preferences)
            continuity_score, continuity_evidence = self._continuity_score(candidate, need)
            facts += continuity_evidence
            recent_uses = sum(
                1 for usage in candidate.usage_history
                if now - self._utc(usage.used_at) <= self._RECENT_WINDOW
                and self._utc(usage.used_at) <= now
            )
            recent_usage_evidence = tuple(
                MatchEvidence(
                    EvidenceKind.USAGE_HISTORY,
                    usage.usage_id,
                    f"{usage.usage_kind}:{self._utc(usage.used_at).isoformat()}",
                )
                for usage in candidate.usage_history
                if now - self._utc(usage.used_at) <= self._RECENT_WINDOW
                and self._utc(usage.used_at) <= now
            )
            usage_penalty = min(self._MAX_USAGE_PENALTY, recent_uses * 0.05)
            components = (
                (semantic_score, 0.45),
                (director_score, 0.25),
                (continuity_score, 0.20),
                (base.scores.quality, 0.10),
            )
            present = [(score, weight) for score, weight in components if score is not None]
            raw = sum(score * weight for score, weight in present) / sum(weight for _, weight in present) if present else 0.0
            score = round(max(0.0, min(1.0, raw - usage_penalty)), 6)
            reasons = ["hard_filter=passed", f"semantic_mode={indexed.mode.value}"]
            if semantic_score is not None:
                reasons.append(f"semantic_score={semantic_score:.3f}")
            if director_score is not None:
                reasons.append(f"director_preference_score={director_score:.3f}")
            if continuity_score is not None:
                reasons.append(f"continuity_score={continuity_score:.3f}")
            reasons.append(f"recent_usage_penalty={usage_penalty:.3f}")
            evidence = AdvancedMatchEvidence(
                semantic_score=semantic_score,
                semantic_mode=indexed.mode,
                director_score=director_score,
                continuity_score=continuity_score,
                usage_penalty=usage_penalty,
                recent_usage_count=recent_uses,
                facts=tuple(sorted(set(facts), key=lambda item: (item.reference, item.detail))),
                inferences=tuple(sorted(set(inferences), key=lambda item: (item.reference, item.detail))),
                usage_history=recent_usage_evidence,
                reasons=tuple(reasons),
            )
            ranked.append((candidate, score, evidence))

        ranked.sort(key=lambda item: (-item[1], item[0].library_asset_id))
        matches = tuple(
            AdvancedMaterialMatch(
                need_id=need.need_id,
                library_asset_id=candidate.library_asset_id,
                asset_id=candidate.asset.asset_id,
                rank=rank,
                score=score,
                evidence=evidence,
            )
            for rank, (candidate, score, evidence) in enumerate(ranked, start=1)
        )
        return AdvancedMatchingResult(
            need_id=need.need_id,
            matches=matches,
            rejected=rejected,
            stale_index_asset_ids=indexed.stale_asset_ids,
        )

    @classmethod
    def _director_score(
        cls,
        candidate: LibraryReuseCandidate,
        preferences: tuple[DirectorPreference, ...],
    ) -> tuple[float | None, tuple[MatchEvidence, ...], tuple[MatchEvidence, ...]]:
        if not preferences:
            return None, (), ()
        fact_values: dict[SemanticField, list[tuple[str, str]]] = {}
        semantic = candidate.asset.semantic
        if semantic.caption:
            fact_values.setdefault(SemanticField.CAPTION, []).append((semantic.caption, "caption"))
        if semantic.tags:
            fact_values.setdefault(SemanticField.TAGS, []).extend((value, "tags") for value in semantic.tags)
        field_keys = {
            SemanticField.OBJECTS: "objects", SemanticField.ENVIRONMENT: "environment",
            SemanticField.ACTION: "action", SemanticField.SHOT_TYPE: "shot_type",
            SemanticField.CAMERA_MOTION: "camera_motion", SemanticField.VISIBLE_TEXT: "visible_text",
            SemanticField.LOGO: "logo", SemanticField.STYLE: "style", SemanticField.COLOR: "color",
            SemanticField.LIGHTING: "lighting",
        }
        for field, key in field_keys.items():
            value = semantic.attributes.get(key)
            if isinstance(value, str):
                fact_values.setdefault(field, []).append((value, f"attributes.{key}"))
            elif isinstance(value, (tuple, list)):
                fact_values.setdefault(field, []).extend(
                    (item, f"attributes.{key}") for item in value if isinstance(item, str)
                )

        scores: list[tuple[float, float]] = []
        facts: list[MatchEvidence] = []
        inferences: list[MatchEvidence] = []
        for preference in preferences:
            values = fact_values.get(preference.field, [])
            fact_ratio = cls._support(preference.preferred_values, [value for value, _ in values])
            inference_values: list[tuple[str, str]] = []
            for inference in semantic.inferences:
                if inference.status not in {IntelligenceStatus.COMPLETE, IntelligenceStatus.PARTIAL}:
                    continue
                for annotation in inference.annotations:
                    if annotation.field is preference.field:
                        rendered = cls._render(annotation.value)
                        ref = f"{inference.analyzer_id}@{inference.model_version or 'unspecified'}"
                        inference_values.extend((item, ref) for item in rendered)
            inference_ratio = cls._support(
                preference.preferred_values, [value for value, _ in inference_values]
            )
            score = max(fact_ratio, inference_ratio)
            scores.append((score, preference.weight))
            if fact_ratio:
                facts.extend(
                    MatchEvidence(EvidenceKind.SOURCE_FACT, source, f"{preference.field.value}:{value}")
                    for value, source in values if cls._supports_any(preference.preferred_values, value)
                )
            if inference_ratio:
                inferences.extend(
                    MatchEvidence(EvidenceKind.AI_INFERENCE, source, f"{preference.field.value}:{value}")
                    for value, source in inference_values
                    if cls._supports_any(preference.preferred_values, value)
                )
        total_weight = sum(weight for _, weight in scores)
        return (sum(score * weight for score, weight in scores) / total_weight if total_weight else 0.0), tuple(facts), tuple(inferences)

    @classmethod
    def _continuity_score(
        cls,
        candidate: LibraryReuseCandidate,
        need: MaterialNeed,
    ) -> tuple[float | None, tuple[MatchEvidence, ...]]:
        if not need.continuity_refs:
            return None, ()
        references = set(candidate.asset.lineage.references)
        evidence: list[MatchEvidence] = []
        hits = 0
        for ref in need.continuity_refs:
            key = f"{ref.kind}:{ref.ref}"
            if key in references:
                hits += 1
                evidence.append(MatchEvidence(EvidenceKind.LINEAGE, key, "exact continuity identity"))
                continue
            # Attribute-backed identity is a factual, structured fallback.
            continuity_values = candidate.asset.semantic.attributes.get("continuity_refs", ())
            if isinstance(continuity_values, str):
                continuity_values = (continuity_values,)
            if isinstance(continuity_values, (tuple, list)) and key in continuity_values:
                hits += 1
                evidence.append(MatchEvidence(EvidenceKind.SOURCE_FACT, "attributes.continuity_refs", key))
        return hits / len(need.continuity_refs), tuple(evidence)

    @staticmethod
    def _support(preferred: tuple[str, ...], observed: list[str]) -> float:
        return sum(1 for item in preferred if AdvancedMaterialMatcher._supports_any((item,), " ".join(observed))) / len(preferred)

    @staticmethod
    def _supports_any(preferred: tuple[str, ...], observed: str) -> bool:
        haystack = observed.casefold()
        return any(value.casefold() in haystack for value in preferred)

    @staticmethod
    def _render(value: object) -> tuple[str, ...]:
        if isinstance(value, str):
            return (value,)
        if isinstance(value, (tuple, list)):
            return tuple(str(item) for item in value)
        return (str(value),)

    @staticmethod
    def _utc(value: datetime) -> datetime:
        return value.astimezone(timezone.utc) if value.utcoffset() is not None else value.replace(tzinfo=timezone.utc)


__all__ = [
    "AdvancedMaterialMatcher", "AdvancedMaterialMatch", "AdvancedMatchEvidence",
    "AdvancedMatchRejection", "AdvancedMatchingResult", "DirectorPreference",
    "EvidenceKind", "MatchEvidence",
]
