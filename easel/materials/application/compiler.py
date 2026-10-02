"""Deterministic compiler from MaterialNeed to retrieval hints."""

from __future__ import annotations

import re
from collections.abc import Iterable

from easel.materials.domain import BgmNeedSpec, MaterialNeed, RetrievalIntent, VoiceNeedSpec
from easel.materials.application.voice_delivery import validate_voice_delivery


class NeedCompilationError(ValueError):
    """Raised when an intent cannot be represented without losing constraints."""


class NeedCompiler:
    """Compile one Need without mutating its Director-owned meaning.

    Context inputs are deliberately limited to caller-selected search terms;
    this class does not read or rewrite Creator/Creative Mode snapshots.
    """

    _FILTER_VALUE_TYPES = (str, int, float, bool)

    def __init__(self, *, search_terms: dict[str, tuple[str, ...]] | None = None):
        self.search_terms = search_terms or {}

    def compile(
        self,
        need: MaterialNeed,
        *,
        creator_context_terms: Iterable[str] = (),
        creative_mode_terms: Iterable[str] = (),
    ) -> RetrievalIntent:
        description = self._normalize(need.intent.description)
        if not description:
            raise NeedCompilationError(f"Need {need.need_id!r} has an empty intent description")
        creator_terms = self._normalize_terms(creator_context_terms, "creator_context_terms")
        mode_terms = self._normalize_terms(creative_mode_terms, "creative_mode_terms")

        filters: dict[str, str | int | float | bool] = {"media_type": need.media_type.value}
        if need.duration_hint is not None:
            filters["min_duration"] = need.duration_hint.target_seconds
        for key, value in need.constraints.items():
            if not isinstance(key, str) or not key.strip():
                raise NeedCompilationError("Need constraint keys must be non-empty strings")
            if key == "preferred_visual_details":
                if need.media_type.value not in {"image", "video"} or not isinstance(value, str) or not value.strip():
                    raise NeedCompilationError("preferred_visual_details 须为视觉 Need 的非空偏好说明")
                # Director discretion is not a stock Provider hard filter.
                continue
            if key == "voice_delivery" and isinstance(need.modality_spec, VoiceNeedSpec):
                # TTS execution controls stay on the original Need, consumed by
                # generation. They cannot be represented as stock-search filters.
                # Validate the known contract rather than discarding arbitrary
                # structured constraints (which must still fail below).
                try:
                    validate_voice_delivery(value)
                except ValueError as exc:
                    raise NeedCompilationError(str(exc)) from exc
                continue
            if not isinstance(value, self._FILTER_VALUE_TYPES):
                raise NeedCompilationError(
                    f"Constraint {key!r} is not representable as a scalar retrieval filter"
                )
            if key in filters and filters[key] != value:
                raise NeedCompilationError(f"Constraint {key!r} conflicts with a canonical Need filter")
            filters[key] = value

        role = need.role.replace("_", " ").strip()
        query_candidates = [description, f"{role} {description}".strip()]
        if need.need_id in self.search_terms:
            terms = self._normalize_terms(self.search_terms[need.need_id], "search_terms")
            if not terms or len(terms) > 4 or any(len(term) > 120 for term in terms):
                raise NeedCompilationError("检索提示须为 1～4 条不超过 120 字符的短语")
            query_candidates = [*terms, *query_candidates]
        if isinstance(need.modality_spec, BgmNeedSpec):
            spec = need.modality_spec
            sound = list(self._normalize_terms(
                (spec.mood or '', spec.genre or '', *spec.instruments, spec.energy or ''), 'bgm preferences'))
            # Reserve one actual Provider query, including when Planning fills
            # all four search hints. These are discovery hints, not evidence
            # that the retrieved audio has been heard or contains no vocals.
            if not spec.vocals_allowed:
                sound.append('instrumental')
            if spec.tempo_bpm:
                sound.append(f'{spec.tempo_bpm[0]}-{spec.tempo_bpm[1]} bpm')
            if sound:
                query_candidates.insert(0, ' '.join((*sound, 'background music')))
            if spec.instruments and need.need_id not in self.search_terms:
                instrument = self._normalize(spec.instruments[0])
                if instrument:
                    # Keep broad fallbacks: requiring every preferred sound
                    # in every search would turn soft direction into no supply.
                    query_candidates[1:1] = [f'{instrument} instrumental' if not spec.vocals_allowed
                                             else f'{instrument} music', instrument]
        if creator_terms:
            query_candidates.append(f"{description} {' '.join(creator_terms)}")
        if mode_terms:
            # Reserve a real query for style. Appending after four explicit
            # search hints silently dropped Mode at the Provider boundary.
            query_candidates.insert(0, f"{query_candidates[0]} {' '.join(mode_terms)}")
        if need.intent.function:
            query_candidates.append(f"{description} {need.intent.function}")
        queries: list[str] = []
        seen: set[str] = set()
        for query in query_candidates:
            normalized = self._normalize(query)
            key = normalized.casefold()
            if normalized and key not in seen:
                queries.append(normalized)
                seen.add(key)
            if len(queries) == 4:
                break
        if len(queries) < 2:
            fallback = self._normalize(f"{description} {need.media_type.value}")
            if fallback.casefold() not in seen:
                queries.append(fallback)
        if not queries:
            raise NeedCompilationError(f"Need {need.need_id!r} produced no search queries")

        negative_terms = tuple(
            key.replace("_", " ").strip()
            for key, value in need.constraints.items()
            if value is False and key.strip()
        )
        if isinstance(need.modality_spec, BgmNeedSpec) and not need.modality_spec.vocals_allowed:
            negative_terms = tuple(dict.fromkeys((*negative_terms, 'vocals')))
        ranking_hints: dict[str, str | int | float | bool] = {"role": role}
        if "preferred_visual_details" in need.constraints:
            ranking_hints["preferred_visual_details"] = need.constraints["preferred_visual_details"]
        if need.intent.function:
            ranking_hints["intent_function"] = need.intent.function
        query_context = {
            "scope_type": need.scope.type.value,
            "scope_ref": need.scope.ref,
            **({"creator_context_terms": " | ".join(creator_terms)} if creator_terms else {}),
            **({"creative_mode_terms": " | ".join(mode_terms)} if mode_terms else {}),
        }
        return RetrievalIntent(
            need_id=need.need_id,
            semantic_queries=tuple(queries),
            filters=filters,
            negative_terms=negative_terms,
            ranking_hints=ranking_hints,
            query_context=query_context,
        )

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    @classmethod
    def _normalize_terms(cls, values: Iterable[str], field: str) -> tuple[str, ...]:
        try:
            raw_values = tuple(values)
        except TypeError as exc:
            raise NeedCompilationError(f"{field} must be an iterable of strings") from exc
        if any(not isinstance(value, str) for value in raw_values):
            raise NeedCompilationError(f"{field} must contain only strings")
        terms = tuple(cls._normalize(value) for value in raw_values)
        unique: list[str] = []
        seen: set[str] = set()
        for term in terms:
            if not term:
                continue
            if term.casefold() not in seen:
                unique.append(term)
                seen.add(term.casefold())
        return tuple(unique)
