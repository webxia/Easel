"""Deterministic Need-to-Asset matching with hard eligibility before soft rank."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

from easel.materials.application.intelligence import IntelligenceStatus
from easel.materials.application.rights import RightsAdmissionStatus, RightsService
from easel.materials.application.visual_observation import PREFIX, observed_interval, observed_match, scoped_inference, need_identity
from easel.materials.application.voice_delivery import VOICE_CONTENT_PREFIX, voice_content_observed
from easel.materials.application.music_observation import PREFIX as MUSIC_PREFIX, binding as music_binding, music_observed
from easel.materials.domain import (
    BgmNeedSpec,
    MaterialAsset,
    MaterialMatch,
    MaterialNeed,
    MediaType,
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
            visual_evidence = (asset.media_type not in {MediaType.IMAGE, MediaType.VIDEO}
                               or self._observed_semantic_overlap(need, asset))
            if scores.semantic is None or scores.semantic <= 0 or not visual_evidence:
                rejected.append(MatchRejection(need.need_id, asset.asset_id,
                                               ("semantic_evidence_missing_or_unrelated",)))
                continue
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
        if (getattr(need.modality_spec, 'kind', None) == 'bgm'
                and not self._creator_match_review(need, asset) and music_observed(need, asset) is not True):
            failures.append('music_observation_missing_or_unsuitable')
        if (getattr(need.modality_spec, 'kind', None) == 'voice' and need.modality_spec.text_sha256
                and not self._creator_match_review(need, asset) and not voice_content_observed(need, asset)):
            failures.append('voice_content_observation_missing')
        if need.constraints.get('requires_dynamic_action') is True and asset.media_type is MediaType.IMAGE:
            failures.append('required_dynamic_action_cannot_be_a_still_image')
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
        interval = observed_interval(need, asset) if asset.media_type is MediaType.VIDEO else None
        if interval is not None:
            duration = interval[1] - interval[0]
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
            logos = self._annotations(asset, SemanticField.LOGO, need)
            if not logos:
                failures.append("logo_presence_unknown")
            elif any(self._is_present(item.value) for item in logos):
                failures.append("logo_forbidden")
        if constraints.get("text_in_frame") is False:
            texts = self._annotations(asset, SemanticField.VISIBLE_TEXT, need)
            if not texts:
                failures.append("visible_text_unknown")
            elif any(self._is_present(item.value) for item in texts):
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
            if inference.analyzer_id.startswith('creator-match:') and (
                    inference.analyzer_id != 'creator-match:' + need.need_id
                    or not self._creator_match_review(need, asset)):
                continue
            if inference.analyzer_id.startswith(MUSIC_PREFIX) and not all(
                    a.evidence and a.evidence.startswith(music_binding(need, asset)) for a in inference.annotations):
                continue
            if inference.analyzer_id.startswith(VOICE_CONTENT_PREFIX):
                continue  # Voice evidence is scoped below, never generic tag overlap.
            if inference.analyzer_id.startswith(PREFIX) and not scoped_inference(need, asset, inference):
                continue
            if inference.status not in {IntelligenceStatus.COMPLETE, IntelligenceStatus.PARTIAL}:
                continue
            for annotation in inference.annotations:
                if annotation.field not in self._SOFT_FIELDS:
                    continue
                corpus_by_field[annotation.field].extend(self._as_text(annotation.value))

        query = self._tokens(need.intent.description)
        semantic_corpus = self._tokens(" ".join(value for values in corpus_by_field.values() for value in values))
        semantic = self._jaccard(query, semantic_corpus) if semantic_corpus else None
        system_observed = observed_match(need, asset) is True
        voice_observed = voice_content_observed(need, asset)
        bgm_observed = music_observed(need, asset) is True
        if self._creator_match_review(need, asset) or system_observed or voice_observed or bgm_observed:
            semantic = 1.0

        preferred_style = need.constraints.get("preferred_style")
        if isinstance(preferred_style, str) and preferred_style.strip():
            style_corpus = self._tokens(" ".join(corpus_by_field[SemanticField.STYLE]))
            director = self._jaccard(self._tokens(preferred_style), style_corpus) if style_corpus else 0.0
        else:
            director = None
        style_overlap = director
        bgm_preference = self._bgm_preference_score(need, asset, semantic_corpus)
        if bgm_preference is not None:
            director = (director + bgm_preference) / 2 if director is not None else bgm_preference

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
            ["system_visual_match=suitable" if system_observed else
             "system_voice_content=complete" if voice_observed else
             "system_music=acoustically_observed" if bgm_observed else
             f"semantic_overlap={semantic:.3f}" if semantic is not None else "semantic_evidence=absent"]
            + ([f"director_style_overlap={style_overlap:.3f}"] if style_overlap is not None else [])
            + ([f"bgm_preference_{'acoustic_and_metadata' if bgm_observed else 'metadata'}_overlap={bgm_preference:.3f}"] if bgm_preference is not None else [])
            + ([f"continuity_overlap={continuity:.3f}"] if continuity is not None else [])
            + ([f"technical_quality={quality:.3f}"] if quality is not None else [])
        )
        return scores, round(total, 6), reasons

    def _bgm_preference_score(self, need: MaterialNeed, asset: MaterialAsset,
                              semantic_corpus: set[str]) -> float | None:
        """Prefer observed instrument/genre tags; keep other preferences soft.

        Metadata may guide selection; it cannot establish absence of vocals,
        technical readiness or Rights. Missing preferences remain soft zeros.
        """
        spec = need.modality_spec
        if not isinstance(spec, BgmNeedSpec):
            return None
        acoustic = [a for i in asset.semantic.inferences if i.analyzer_id == MUSIC_PREFIX + need.need_id
                    for a in i.annotations if a.field is SemanticField.TAGS
                    and a.evidence and a.evidence.startswith(music_binding(need, asset))]
        acoustic_corpus = self._tokens(' '.join(text for a in acoustic for text in self._as_text(a.value)))
        scores = []
        for field, requested in (('mood', (spec.mood,)), ('genre', (spec.genre,)),
                                 ('instruments', spec.instruments), ('energy', (spec.energy,))):
            terms = [self._tokens(value) for value in requested if value and value.strip()]
            terms = [tokens for tokens in terms if tokens]
            if not terms:
                continue
            value = asset.semantic.attributes.get(field)
            corpus = (self._tokens(' '.join(self._as_text(value)))
                      if value is not None else semantic_corpus)
            if acoustic and field in {'instruments', 'genre'}:
                corpus = acoustic_corpus  # Provider titles cannot override actual sound evidence.
            scores.append(sum(len(tokens & corpus) / len(tokens) for tokens in terms) / len(terms))
        if spec.tempo_bpm is not None:
            tempo = self._number(asset.semantic.attributes.get('tempo_bpm'))
            scores.append(float(tempo is not None and spec.tempo_bpm[0] <= tempo <= spec.tempo_bpm[1]))
        return sum(scores) / len(scores) if scores else None

    def _observed_semantic_overlap(self, need: MaterialNeed, asset: MaterialAsset) -> bool:
        if self._creator_match_review(need, asset):
            return True
        observed = observed_match(need, asset)
        if observed is not None:
            return observed
        query = self._tokens(need.intent.description)
        if not query:
            return False
        for inference in asset.semantic.inferences:
            if inference.analyzer_id.startswith("creator-match:"):
                continue
            if inference.status not in {IntelligenceStatus.COMPLETE, IntelligenceStatus.PARTIAL}:
                continue
            for annotation in inference.annotations:
                if (annotation.field in self._SOFT_FIELDS and annotation.evidence
                        and (annotation.confidence is None or annotation.confidence >= 0.5)
                        and query & self._tokens(" ".join(self._as_text(annotation.value)))):
                    return True
        return False

    @staticmethod
    def _creator_match_review(need: MaterialNeed, asset: MaterialAsset) -> bool:
        expected = f"creator-confirmed:{need.need_id}:{asset.file.sha256}"
        return any(
            inference.analyzer_id == f"creator-match:{need.need_id}"
            and inference.status is IntelligenceStatus.COMPLETE
            and any(annotation.field is SemanticField.CAPTION
                    and isinstance(annotation.value, str) and annotation.value.strip()
                    and annotation.evidence in {expected, expected + ':need=' + need_identity(need)}
                    for annotation in inference.annotations)
            for inference in asset.semantic.inferences
        )

    @staticmethod
    def _quality_score(need: MaterialNeed, asset: MaterialAsset) -> float | None:
        technical = asset.technical
        signals: list[float] = []
        if technical.width is not None and technical.height is not None:
            pixels = technical.width * technical.height
            signals.append(min(1.0, math.sqrt(pixels / (1080 * 1920))))
        target = need.duration_hint.target_seconds if need.duration_hint else None
        interval = observed_interval(need, asset) if asset.media_type is MediaType.VIDEO else None
        duration = interval[1] - interval[0] if interval else technical.duration_seconds
        if target and duration:
            ratio = duration / target
            signals.append(1.0 / (1.0 + abs(math.log(ratio))))
        return sum(signals) / len(signals) if signals else None

    @staticmethod
    def _annotations(asset: MaterialAsset, field: SemanticField, need: MaterialNeed):
        results = []
        for inference in asset.semantic.inferences:
            if inference.analyzer_id.startswith(PREFIX) and not scoped_inference(need, asset, inference):
                continue
            if inference.analyzer_id.startswith('creator-match:') and any(
                    ':need=' in (a.evidence or '') and not a.evidence.endswith(':need=' + need_identity(need))
                    for a in inference.annotations):
                continue
            if inference.status in {IntelligenceStatus.COMPLETE, IntelligenceStatus.PARTIAL}:
                results.extend(annotation for annotation in inference.annotations
                               if annotation.field is field and annotation.evidence
                               and annotation.confidence is not None
                               and annotation.confidence >= 0.5)
        return tuple(results)

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
