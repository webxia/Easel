"""Deterministic Need-to-Asset matching with hard eligibility before soft rank."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

from easel.materials.application.intelligence import IntelligenceStatus
from easel.materials.application.rights import RightsAdmissionStatus, RightsService
from easel.materials.domain import (
    MaterialAsset,
    MaterialMatch,
    MaterialNeed,
    SemanticField,
    TechnicalStatus,
)
from easel.materials.domain.models import MatchScores


@dataclass(frozen=True)
class MatchRejection:
    need_id: str
    asset_id: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class MaterialMatchingResult:
    need_id: str
    matches: tuple[MaterialMatch, ...]
    rejected: tuple[MatchRejection, ...]


class MaterialMatcher:
    """Keep eligibility decisions independent from explainable soft scores.

    Supported hard-constraint keys are `orientation`, `min/max_duration` (or
    their `_seconds` forms), `min_width`, `min_height`, `min_pixels`,
    `text_in_frame`, `logo`, `required_source_kind`, `forbidden_source_kind`, and
    `required_identity_refs`. Identity refs are
    exact `kind:ref` values stored in MaterialAsset.lineage.references.
    """

    _TOKEN_RE = re.compile(r"[a-z0-9]+|[\u3400-\u9fff]", re.IGNORECASE)
    _STOP_WORDS = frozenset({"a", "an", "and", "the", "with", "of", "in", "on", "at", "to", "for"})
    _SOFT_FIELDS = frozenset({
        SemanticField.CAPTION, SemanticField.TAGS, SemanticField.OBJECTS,
        SemanticField.ENVIRONMENT, SemanticField.ACTION, SemanticField.SHOT_TYPE,
        SemanticField.CAMERA_MOTION, SemanticField.STYLE, SemanticField.COLOR,
        SemanticField.LIGHTING,
    })

    def __init__(self, rights_service: RightsService | None = None):
        self._rights = rights_service or RightsService()

    def match(self, need: MaterialNeed, assets: tuple[MaterialAsset, ...] | list[MaterialAsset]) -> MaterialMatchingResult:
        eligible: list[tuple[MaterialAsset, MatchScores, float, tuple[str, ...]]] = []
        rejected: list[MatchRejection] = []
        for asset in assets:
            hard_reasons = self._hard_filter(need, asset)
            if hard_reasons:
                rejected.append(MatchRejection(need.need_id, asset.asset_id, hard_reasons))
                continue
            scores, total, soft_reasons = self._soft_scores(need, asset)
            eligible.append((asset, scores, total, ("hard_filter=passed",) + soft_reasons))

        eligible.sort(key=lambda item: (-item[2], item[0].asset_id))
        matches = tuple(
            MaterialMatch(
                need_id=need.need_id,
                asset_id=asset.asset_id,
                rank=index,
                score=score,
                scores=scores,
                reasons=reasons,
                qualified=True,
            )
            for index, (asset, scores, score, reasons) in enumerate(eligible, start=1)
        )
        return MaterialMatchingResult(need_id=need.need_id, matches=matches, rejected=tuple(rejected))

    def match_many(
        self,
        needs: tuple[MaterialNeed, ...] | list[MaterialNeed],
        assets: tuple[MaterialAsset, ...] | list[MaterialAsset],
    ) -> tuple[MaterialMatchingResult, ...]:
        return tuple(self.match(need, assets) for need in needs)

    def _hard_filter(self, need: MaterialNeed, asset: MaterialAsset) -> tuple[str, ...]:
        failures: list[str] = []
        if need.media_type is not asset.media_type:
            failures.append("media_type_mismatch")
        if asset.technical.status is not TechnicalStatus.PASSED:
            failures.append("technical_inspection_not_passed")
        rights = self._rights.evaluate(
            asset, need, attribution=self._rights.attribution_condition_for(asset),
        )
        if rights.status not in {RightsAdmissionStatus.ADMITTED, RightsAdmissionStatus.CONDITIONAL}:
            failures.append(f"rights_{rights.status.value.lower()}:{rights.reason}")

        constraints = need.constraints
        if constraints.get("allow_generation") is False and asset.source.kind == "generative":
            failures.append("generation_not_allowed")
        required_source_kind = constraints.get("required_source_kind")
        if required_source_kind is not None:
            if not isinstance(required_source_kind, str) or not required_source_kind.strip():
                failures.append("required_source_kind_invalid")
            elif asset.source.kind != required_source_kind:
                failures.append("required_source_kind_mismatch")
        forbidden_source_kind = constraints.get("forbidden_source_kind")
        if forbidden_source_kind is not None:
            if not isinstance(forbidden_source_kind, str) or not forbidden_source_kind.strip():
                failures.append("forbidden_source_kind_invalid")
            elif asset.source.kind == forbidden_source_kind:
                failures.append("forbidden_source_kind_match")
        orientation = constraints.get("orientation")
        if orientation not in (None, "all"):
            if not isinstance(orientation, str) or orientation not in {"portrait", "landscape", "square"}:
                failures.append("orientation_constraint_invalid")
            elif asset.technical.width is None or asset.technical.height is None:
                failures.append("orientation_unknown")
            elif not self._orientation_matches(orientation, asset.technical.width, asset.technical.height):
                failures.append("orientation_mismatch")

        width, height = asset.technical.width, asset.technical.height
        for key, actual in (("min_width", width), ("min_height", height)):
            minimum = self._number(constraints.get(key))
            if key in constraints and minimum is None:
                failures.append(f"{key}_constraint_invalid")
            elif minimum is not None and (actual is None or actual < minimum):
                failures.append(f"{key}_not_met")
        min_pixels = self._number(constraints.get("min_pixels"))
        if "min_pixels" in constraints and min_pixels is None:
            failures.append("min_pixels_constraint_invalid")
        elif min_pixels is not None and (width is None or height is None or width * height < min_pixels):
            failures.append("min_pixels_not_met")

        duration = asset.technical.duration_seconds
        for lower_key in ("min_duration_seconds", "min_duration"):
            lower = self._number(constraints.get(lower_key))
            if lower_key in constraints and lower is None:
                failures.append("min_duration_constraint_invalid")
            elif lower is not None and (duration is None or duration < lower):
                failures.append("min_duration_not_met")
        for upper_key in ("max_duration_seconds", "max_duration"):
            upper = self._number(constraints.get(upper_key))
            if upper_key in constraints and upper is None:
                failures.append("max_duration_constraint_invalid")
            elif upper is not None and (duration is None or duration > upper):
                failures.append("max_duration_not_met")

        if constraints.get("logo") is False:
            logo = self._annotation(asset, SemanticField.LOGO)
            if logo is None:
                failures.append("logo_presence_unknown")
            elif self._is_present(logo.value):
                failures.append("logo_forbidden")
        if constraints.get("text_in_frame") is False:
            text = self._annotation(asset, SemanticField.VISIBLE_TEXT)
            if text is None:
                failures.append("visible_text_unknown")
            elif self._is_present(text.value):
                failures.append("visible_text_forbidden")

        required_ids = constraints.get("required_identity_refs", ())
        if not isinstance(required_ids, (tuple, list)) or any(not isinstance(item, str) or not item for item in required_ids):
            if "required_identity_refs" in constraints:
                failures.append("required_identity_refs_invalid")
        else:
            available_ids = set(asset.lineage.references)
            missing = sorted(set(required_ids) - available_ids)
            if missing:
                failures.extend(f"required_identity_missing:{item}" for item in missing)
        return tuple(failures)

    def _soft_scores(self, need: MaterialNeed, asset: MaterialAsset) -> tuple[MatchScores, float, tuple[str, ...]]:
        corpus_by_field: dict[SemanticField, list[str]] = {field: [] for field in self._SOFT_FIELDS}
        if asset.semantic.caption:
            corpus_by_field[SemanticField.CAPTION].append(asset.semantic.caption)
        corpus_by_field[SemanticField.TAGS].extend(asset.semantic.tags)
        for key in ("objects", "environment", "action", "shot_type", "camera_motion", "style", "color", "lighting"):
            value = asset.semantic.attributes.get(key)
            if isinstance(value, str):
                try:
                    corpus_by_field[SemanticField(key)].append(value)
                except ValueError:
                    pass
            elif isinstance(value, (tuple, list)):
                corpus_by_field[SemanticField(key)].extend(item for item in value if isinstance(item, str))
        for inference in asset.semantic.inferences:
            if inference.status not in {IntelligenceStatus.COMPLETE, IntelligenceStatus.PARTIAL}:
                continue
            for annotation in inference.annotations:
                if annotation.field not in self._SOFT_FIELDS:
                    continue
                corpus_by_field[annotation.field].extend(self._as_text(annotation.value))

        query = self._tokens(need.intent.description)
        semantic_corpus = self._tokens(" ".join(value for values in corpus_by_field.values() for value in values))
        semantic = self._jaccard(query, semantic_corpus) if semantic_corpus else None

        preferred_style = need.constraints.get("preferred_style")
        if isinstance(preferred_style, str) and preferred_style.strip():
            style_corpus = self._tokens(" ".join(corpus_by_field[SemanticField.STYLE]))
            director = self._jaccard(self._tokens(preferred_style), style_corpus) if style_corpus else 0.0
        else:
            director = None

        continuity = None
        if need.continuity_refs:
            semantic_text = " ".join(value for values in corpus_by_field.values() for value in values)
            hits = 0
            for ref in need.continuity_refs:
                exact = f"{ref.kind}:{ref.ref}" in asset.lineage.references
                lexical = bool(self._tokens(ref.ref) & self._tokens(semantic_text))
                hits += int(exact or lexical)
            continuity = hits / len(need.continuity_refs)

        quality = self._quality_score(need, asset)
        scores = MatchScores(semantic=semantic, director=director, continuity=continuity, quality=quality)
        weighted = ((semantic, 0.50), (director, 0.15), (continuity, 0.20), (quality, 0.15))
        present = [(score, weight) for score, weight in weighted if score is not None]
        total = sum(score * weight for score, weight in present) / sum(weight for _, weight in present) if present else 0.0
        reasons = tuple(
            [f"semantic_overlap={semantic:.3f}" if semantic is not None else "semantic_evidence=absent"]
            + ([f"director_style_overlap={director:.3f}"] if director is not None else [])
            + ([f"continuity_overlap={continuity:.3f}"] if continuity is not None else [])
            + ([f"technical_quality={quality:.3f}"] if quality is not None else [])
        )
        return scores, round(total, 6), reasons

    @staticmethod
    def _quality_score(need: MaterialNeed, asset: MaterialAsset) -> float | None:
        technical = asset.technical
        signals: list[float] = []
        if technical.width is not None and technical.height is not None:
            pixels = technical.width * technical.height
            signals.append(min(1.0, math.sqrt(pixels / (1080 * 1920))))
        target = need.duration_hint.target_seconds if need.duration_hint else None
        if target and technical.duration_seconds:
            ratio = technical.duration_seconds / target
            signals.append(1.0 / (1.0 + abs(math.log(ratio))))
        return sum(signals) / len(signals) if signals else None

    @staticmethod
    def _annotation(asset: MaterialAsset, field: SemanticField):
        for inference in reversed(asset.semantic.inferences):
            if inference.status in {IntelligenceStatus.COMPLETE, IntelligenceStatus.PARTIAL}:
                for annotation in inference.annotations:
                    if annotation.field is field:
                        return annotation
        return None

    @staticmethod
    def _is_present(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (tuple, list, str)):
            return bool(value)
        return bool(value)

    @classmethod
    def _tokens(cls, value: str) -> set[str]:
        return {token for token in (item.casefold() for item in cls._TOKEN_RE.findall(value))
                if token not in cls._STOP_WORDS}

    @staticmethod
    def _jaccard(left: set[str], right: set[str]) -> float:
        union = left | right
        return len(left & right) / len(union) if union else 0.0

    @staticmethod
    def _as_text(value: object) -> list[str]:
        if isinstance(value, str):
            return [value]
        if isinstance(value, (tuple, list)):
            return [item for item in value if isinstance(item, str)]
        if isinstance(value, bool):
            return ["true" if value else "false"]
        return []

    @staticmethod
    def _number(value: object) -> float | None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        number = float(value)
        return number if math.isfinite(number) and number >= 0 else None

    @staticmethod
    def _orientation_matches(expected: str, width: int, height: int) -> bool:
        if expected == "portrait":
            return height > width
        if expected == "landscape":
            return width > height
        return width == height
