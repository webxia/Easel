"""Exact and bounded metadata deduplication plus per-Need shortlist diversity."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from easel.materials.domain import MaterialAsset, MaterialMatch
from easel.materials.store import AttemptMaterialStore, AttemptMaterialStoreError


@dataclass(frozen=True)
class SuppressedMatch:
    match: MaterialMatch
    representative_asset_id: str
    kind: str
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class MaterialDiversityResult:
    unique_matches: tuple[MaterialMatch, ...]
    shortlist: tuple[MaterialMatch, ...]
    suppressed: tuple[SuppressedMatch, ...]
    rejected: tuple[tuple[str, str], ...]


class MaterialDeduplicator:
    """Collapse well-supported duplicates and return a diverse ranked Top-K.

    Exact keys are scoped provider-native IDs, conservatively normalized source
    and acquisition URLs, bytes SHA-256, and an explicit `canonical_media_id` fact.
    Near-duplicate text comparison requires compatible duration and strong
    caption overlap plus corroborating creator or matching frame dimensions.
    """

    _TOKEN_RE = re.compile(r"[a-z0-9]+|[\u3400-\u9fff]", re.IGNORECASE)
    _STOP_WORDS = frozenset({"a", "an", "and", "the", "of", "in", "on", "for", "video", "clip", "footage", "stock"})
    _TRACKING_KEYS = frozenset({"fbclid", "gclid", "mc_cid", "mc_eid", "ref_src"})
    _DIVERSITY_PENALTY = 0.30

    def __init__(self, store: AttemptMaterialStore | None = None):
        self._store = store

    def deduplicate_and_diversify(
        self,
        matches: tuple[MaterialMatch, ...] | list[MaterialMatch],
        assets: tuple[MaterialAsset, ...] | list[MaterialAsset],
        *,
        top_k: int,
    ) -> MaterialDiversityResult:
        if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 1:
            raise ValueError("top_k must be a positive integer")
        assets_by_id = {asset.asset_id: asset for asset in assets}
        if len(assets_by_id) != len(assets):
            raise ValueError("asset IDs must be unique")
        rejected: list[tuple[str, str]] = []
        by_asset: dict[str, MaterialMatch] = {}
        for match in matches:
            if match.asset_id not in assets_by_id:
                raise ValueError(f"match references unknown asset: {match.asset_id}")
            if not match.qualified:
                rejected.append((match.asset_id, "match_not_qualified"))
                continue
            existing = by_asset.get(match.asset_id)
            if existing is None or self._match_order(match) < self._match_order(existing):
                by_asset[match.asset_id] = match

        ordered = sorted(by_asset.values(), key=self._match_order)
        acquisition_urls = {
            asset_id: self._acquisition_urls(asset)
            for asset_id, asset in assets_by_id.items()
        }
        parent = {match.asset_id: match.asset_id for match in ordered}

        def root(asset_id: str) -> str:
            while parent[asset_id] != asset_id:
                parent[asset_id] = parent[parent[asset_id]]
                asset_id = parent[asset_id]
            return asset_id

        exact_index: dict[str, str] = {}
        key_members: dict[str, set[str]] = {}
        for match in ordered:
            for key in self._exact_keys(assets_by_id[match.asset_id], acquisition_urls[match.asset_id]):
                key_members.setdefault(key, set()).add(match.asset_id)
                other = exact_index.setdefault(key, match.asset_id)
                left, right = root(match.asset_id), root(other)
                if left != right:
                    # Input order is already deterministic by match score/rank/ID.
                    parent[right] = left

        exact_groups: dict[str, list[MaterialMatch]] = {}
        for match in ordered:
            exact_groups.setdefault(root(match.asset_id), []).append(match)
        exact_representative: dict[str, MaterialMatch] = {}
        exact_evidence: dict[str, tuple[str, ...]] = {}
        for group in exact_groups.values():
            representative = min(group, key=self._match_order)
            group_ids = {item.asset_id for item in group}
            labels = {
                key.split(":", 1)[0]
                for key, members in key_members.items()
                if len(members & group_ids) > 1
            }
            for item in group:
                exact_representative[item.asset_id] = representative
                exact_evidence[item.asset_id] = tuple(sorted(labels))

        unique: list[MaterialMatch] = []
        suppressed: list[SuppressedMatch] = []
        near_representatives: list[MaterialMatch] = []
        for match in ordered:
            representative = exact_representative[match.asset_id]
            if representative.asset_id != match.asset_id:
                suppressed.append(SuppressedMatch(
                    match, representative.asset_id, "exact", exact_evidence[match.asset_id]
                ))
                continue
            asset = assets_by_id[match.asset_id]
            near_match: MaterialMatch | None = None
            near_evidence: tuple[str, ...] = ()
            for candidate in near_representatives:
                evidence = self._metadata_duplicate_evidence(asset, assets_by_id[candidate.asset_id])
                if evidence:
                    near_match, near_evidence = candidate, evidence
                    break
            if near_match is not None:
                suppressed.append(SuppressedMatch(match, near_match.asset_id, "metadata", near_evidence))
                continue
            unique.append(match)
            near_representatives.append(match)

        shortlist = self._diverse_top_k(unique, assets_by_id, top_k)
        return MaterialDiversityResult(
            unique_matches=tuple(unique),
            shortlist=shortlist,
            suppressed=tuple(suppressed),
            rejected=tuple(rejected),
        )

    @classmethod
    def _exact_keys(cls, asset: MaterialAsset, acquisition_urls: tuple[str, ...] = ()) -> tuple[str, ...]:
        keys: list[str] = []
        provider = asset.source.provider
        native_id = asset.source.provider_asset_id
        if provider and native_id:
            keys.append(f"native:{asset.media_type.value}:{provider.casefold()}:{native_id.strip()}")
        for raw_url in (asset.source.source_page, *acquisition_urls):
            normalized = cls._canonical_url(raw_url)
            if normalized:
                keys.append(f"url:{asset.media_type.value}:{normalized}")
        if asset.file.sha256:
            keys.append(f"sha256:{asset.file.sha256.lower()}")
        metadata_id = asset.semantic.attributes.get("canonical_media_id")
        if isinstance(metadata_id, str) and metadata_id.strip():
            keys.append(f"metadata_id:{asset.media_type.value}:{metadata_id.strip().casefold()}")
        return tuple(keys)

    def _acquisition_urls(self, asset: MaterialAsset) -> tuple[str, ...]:
        if self._store is None:
            return ()
        try:
            evidence = self._store.read_acquisition_evidence(asset.asset_id)
        except AttemptMaterialStoreError:
            return ()
        return tuple(
            value for key in ("requested_url", "final_url")
            if isinstance((value := evidence.get(key)), str) and value.strip()
        )

    @classmethod
    def _canonical_url(cls, value: str | None) -> str | None:
        if not value:
            return None
        try:
            parsed = urlsplit(value.strip())
            if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
                return None
            if parsed.username or parsed.password:
                return None
            host = parsed.hostname.encode("idna").decode("ascii").casefold()
            port = parsed.port
            netloc = host if port is None or (parsed.scheme.casefold(), port) in {("http", 80), ("https", 443)} else f"{host}:{port}"
            query = [
                (key, item)
                for key, item in parse_qsl(parsed.query, keep_blank_values=True)
                if not key.casefold().startswith("utm_") and key.casefold() not in cls._TRACKING_KEYS
            ]
            query.sort()
            path = parsed.path or "/"
            return urlunsplit((parsed.scheme.casefold(), netloc, path, urlencode(query, doseq=True), ""))
        except (UnicodeError, ValueError):
            return None

    @classmethod
    def _metadata_duplicate_evidence(cls, first: MaterialAsset, second: MaterialAsset) -> tuple[str, ...]:
        if first.media_type is not second.media_type:
            return ()
        first_duration, second_duration = first.technical.duration_seconds, second.technical.duration_seconds
        if first_duration is None or second_duration is None or not cls._duration_compatible(first_duration, second_duration):
            return ()
        first_creator = (first.source.creator or "").strip().casefold()
        second_creator = (second.source.creator or "").strip().casefold()
        if first_creator and second_creator and first_creator != second_creator:
            return ()
        left = cls._caption_tokens(first)
        right = cls._caption_tokens(second)
        similarity = cls._jaccard(left, right)
        same_creator = bool(first_creator and first_creator == second_creator)
        same_dimensions = (
            first.technical.width is not None and first.technical.height is not None
            and first.technical.width == second.technical.width
            and first.technical.height == second.technical.height
        )
        corroborated = same_creator or same_dimensions
        if similarity >= 0.82 and corroborated:
            return (f"metadata_similarity={similarity:.3f}", "duration_compatible", "metadata_corroborated")
        return ()

    @classmethod
    def _diverse_top_k(
        cls,
        matches: list[MaterialMatch],
        assets: dict[str, MaterialAsset],
        top_k: int,
    ) -> tuple[MaterialMatch, ...]:
        remaining = list(matches)
        chosen: list[MaterialMatch] = []
        while remaining and len(chosen) < top_k:
            ranked: list[tuple[float, float, int, str, MaterialMatch]] = []
            for match in remaining:
                asset = assets[match.asset_id]
                max_similarity = max(
                    (cls._jaccard(cls._caption_tokens(asset), cls._caption_tokens(assets[other.asset_id])) for other in chosen),
                    default=0.0,
                )
                score = match.score if match.score is not None else 0.0
                adjusted = score - cls._DIVERSITY_PENALTY * max_similarity
                ranked.append((adjusted, score, -match.rank, match.asset_id, match))
            best = min(ranked, key=lambda item: (-item[0], -item[1], -item[2], item[3]))[-1]
            chosen.append(best)
            remaining.remove(best)
        return tuple(chosen)

    @classmethod
    def _caption_tokens(cls, asset: MaterialAsset) -> set[str]:
        values: list[str] = []
        if asset.semantic.caption:
            values.append(asset.semantic.caption)
        values.extend(asset.semantic.tags)
        for inference in asset.semantic.inferences:
            for annotation in inference.annotations:
                if annotation.field.value in {"caption", "tags", "objects", "environment", "action", "shot_type"}:
                    if isinstance(annotation.value, str):
                        values.append(annotation.value)
                    elif isinstance(annotation.value, (tuple, list)):
                        values.extend(value for value in annotation.value if isinstance(value, str))
        normalized = " ".join(values).casefold()
        return {token for token in cls._TOKEN_RE.findall(normalized) if token not in cls._STOP_WORDS}

    @classmethod
    def _duration_compatible(cls, left: float, right: float) -> bool:
        return math.isfinite(left) and math.isfinite(right) and abs(left - right) <= max(1.5, min(left, right) * 0.04)

    @staticmethod
    def _jaccard(left: set[str], right: set[str]) -> float:
        union = left | right
        return len(left & right) / len(union) if union else 0.0

    @staticmethod
    def _match_order(match: MaterialMatch) -> tuple[float, int, str]:
        return (-(match.score if match.score is not None else 0.0), match.rank, match.asset_id)
