"""V2 work adapter for the migrated material catalog.

All paths and scope objects originate at the trusted input/work boundary.
This service does not call a provider, select a replacement for required input,
write plans/acceptances, or grant generation/reuse permission.
"""
from __future__ import annotations

import hashlib
import json
import mimetypes
import math
import tempfile
from dataclasses import dataclass
from pathlib import Path

from easel.materials.application.inspector import TechnicalInspector
from easel.materials.application.library_reuse import LibraryReuseSearchResult, LibraryReuseService
from easel.materials.application.rights import AttributionCondition, RightsAdmissionStatus, RightsService
from easel.materials.domain import CandidateSource, FileInfo, MaterialAsset, MaterialNeed, MediaType, RightsInfo, SemanticInfo, TechnicalStatus
from easel.materials.library import LibraryVisibility, MaterialLibraryCatalog, MaterialLibraryError, PromotionConsent, UseContext
from easel.materials.semantic_index import EmbeddingProvider, MaterialSemanticIndex
from easel.materials.store import MaterialFileStore, RemoteURLPolicy, digest_file


@dataclass(frozen=True)
class MaterialHandle:
    asset_ref: str
    digest: str
    local_path: Path
    asset: MaterialAsset
    attribution: AttributionCondition | None = None

    def artifact_metadata(self) -> dict:
        return {"asset_ref": self.asset_ref, "sha256": self.digest,
                "source": self.asset.source.model_dump(mode="json"),
                "rights": self.asset.rights.model_dump(mode="json"),
                "technical": self.asset.technical.model_dump(mode="json"),
                "semantic": self.asset.semantic.model_dump(mode="json"),
                "attribution": self.attribution.__dict__ if self.attribution else None}


class MaterialService:
    def __init__(self, root: str | Path, *, ffprobe: str | None = None):
        self.catalog = MaterialLibraryCatalog(root)
        self.index = MaterialSemanticIndex(self.catalog)
        self.reuse = LibraryReuseService(self.catalog)
        self.ffprobe = ffprobe

    def ingest_downloaded(self, downloaded, *, visibility: LibraryVisibility, context: UseContext,
                          media_type: MediaType, source: CandidateSource, rights: RightsInfo,
                          semantic: SemanticInfo | None = None) -> MaterialHandle:
        """Inspect and ingest bounded received bytes without granting new rights."""
        suffix = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp",
                  "video/mp4": ".mp4", "audio/mpeg": ".mp3", "audio/wav": ".wav",
                  "audio/x-wav": ".wav", "audio/ogg": ".ogg", "application/ogg": ".ogg",
                  "audio/flac": ".flac"}.get(downloaded.mime, ".media")
        with tempfile.TemporaryDirectory(prefix=".receive-", dir=self.catalog.root) as directory:
            source_root = Path(directory)
            path = source_root / ("received" + suffix)
            path.write_bytes(downloaded.body)
            return self.ingest_input(source_root=source_root, relative_path=path.name,
                visibility=visibility, context=context, media_type=media_type, source=source,
                rights=rights, semantic=semantic)

    def ingest_input(self, *, source_root: str | Path, relative_path: str,
                     visibility: LibraryVisibility, context: UseContext,
                     media_type: MediaType, source: CandidateSource, rights: RightsInfo,
                     semantic: SemanticInfo | None = None, expected_sha256: str | None = None,
                     max_bytes: int = 4 * 1024 ** 3) -> MaterialHandle:
        files = MaterialFileStore(source_root)
        path = files.resolve_asset_locator(relative_path)
        size = path.stat().st_size
        if size <= 0 or size > max_bytes:
            raise MaterialLibraryError("Input is empty or exceeds the configured size limit")
        digest = digest_file(path)
        if expected_sha256 is not None and expected_sha256 != digest:
            raise MaterialLibraryError("Input content does not match the registered digest")
        policy = RightsService()
        # Evidence may contain signed download URLs. Persist source facts without
        # credentials/query strings; a sanitized string is not a license proof.
        clean_source = source.model_copy(update={"source_page": RemoteURLPolicy.redact(source.source_page),
            "creator": policy._sanitize_text(source.creator)})
        clean_rights = rights.model_copy(update={"license_url": RemoteURLPolicy.redact(rights.license_url),
            "attribution_text": policy._sanitize_text(rights.attribution_text),
            "evidence": tuple(e.model_copy(update={"reference": policy._sanitize_text(e.reference),
                                                    "summary": policy._sanitize_text(e.summary)}) for e in rights.evidence)})
        identity = json.dumps([context.work_id, relative_path, digest, clean_source.model_dump(mode="json")], sort_keys=True)
        asset = MaterialAsset(asset_id="input-" + hashlib.sha256(identity.encode()).hexdigest()[:32],
            media_type=media_type, file=FileInfo(path=relative_path, sha256=digest, size=size,
            mime=mimetypes.guess_type(path.name)[0] or "application/octet-stream"),
            source=clean_source, rights=clean_rights, semantic=semantic or SemanticInfo())
        inspected = TechnicalInspector(files, ffprobe=self.ffprobe).inspect(asset)
        if inspected.technical.status is TechnicalStatus.PASSED and inspected.technical.mime:
            inspected = inspected.model_copy(update={"file": inspected.file.model_copy(update={"mime": inspected.technical.mime})})
        record = self.catalog.register(inspected, files, scope=visibility, context=context)
        # Keep the original input retained independently of any output selection.
        self.catalog.record_usage(record.asset_ref, scope=visibility, context=context,
                                  reference_id=f"input:{record.asset_ref}")
        return self.resolve(record.asset_ref, visibility=visibility, context=context)

    def resolve(self, asset_ref: str, *, visibility: LibraryVisibility, context: UseContext) -> MaterialHandle:
        record = self.catalog.get(asset_ref, scope=visibility, context=context)
        return MaterialHandle(record.asset_ref, record.asset.file.sha256,
                              self.catalog.resolve_physical_locator(record), record.asset,
                              RightsService.attribution_condition_for(record.asset))

    def promote(self, asset_ref: str, *, visibility: LibraryVisibility, context: UseContext,
                consent: PromotionConsent):
        return self.catalog.promote(asset_ref, scope=visibility, context=context, consent=consent)

    def candidates(self, need: MaterialNeed, *, visibility: LibraryVisibility, context: UseContext,
                   query: str = "", limit: int = 100,
                   embedding_provider: EmbeddingProvider | None = None,
                   semantic_supplement: bool = False) -> LibraryReuseSearchResult:
        if not 1 <= limit <= 1000:
            raise MaterialLibraryError("Candidate limit must be between 1 and 1000")
        if semantic_supplement:
            minimum = getattr(embedding_provider, 'minimum_score', None)
            if (need.media_type is not MediaType.AUDIO or need.role != 'sfx' or not query.strip()
                    or embedding_provider is None or not isinstance(minimum, (int, float))
                    or not math.isfinite(minimum) or not -1 <= minimum <= 1):
                return LibraryReuseSearchResult((), (), fallback_reason='semantic_supplement_unavailable')
        # Rank a bounded pool first, but apply the requested top-k only after
        # eligibility. An old invalid Rights record must not hide a valid one.
        if not query.strip():
            checked = self.reuse.find_candidates(need, scope=visibility, context=context, limit=1000)
            mode, reason = checked.search_mode, checked.fallback_reason
        else:
            options = ({'allow_partial': True, 'audio_role': 'sfx', 'min_score': minimum}
                       if semantic_supplement else {})
            search = self.index.search(query, scope=visibility, context=context, provider=embedding_provider,
                                       limit=1000, metadata_filters={"media_type": need.media_type, "limit": 1000}, **options)
            records = tuple(hit.record for hit in search.hits)
            if semantic_supplement:
                from easel.materials.audio_search import audio_action_conflict
                records = tuple(r for r in records if not audio_action_conflict(query, r.asset.semantic.caption or ''))
            checked = self.reuse.find_candidates(need, scope=visibility, context=context,
                records=records, limit=1000)
            mode, reason = search.mode.value, search.fallback_reason
        candidates, seen = [], set()
        for candidate in checked.candidates:
            if candidate.asset.file.sha256 not in seen:
                candidates.append(candidate)
                seen.add(candidate.asset.file.sha256)
            if len(candidates) == limit:
                break
        return LibraryReuseSearchResult(tuple(candidates), checked.rejected, mode, reason)

    def preflight_external(self, candidate, need: MaterialNeed, context: UseContext):
        """Check source Rights before downloading; this is not media inspection."""
        pending = MaterialAsset(asset_id=candidate.candidate_id, media_type=candidate.media_type,
            file=FileInfo(path="pending.media", sha256="0" * 64, size=0, mime="application/octet-stream"),
            source=candidate.source, rights=candidate.rights, semantic=candidate.semantic)
        current = need.model_copy(update={"constraints": {**need.constraints, **context.constraints}})
        policy = RightsService()
        return policy.evaluate(pending, current, attribution=policy.attribution_condition_for(pending))

    @staticmethod
    def _rights_identity(rights: RightsInfo) -> str:
        # Observation time is not a new license. All substantive evidence,
        # restrictions, credit text and policy versions still participate.
        data = rights.model_dump(mode="json")
        data.pop("reviewed_at", None)
        for evidence in data.get("evidence", []):
            evidence.pop("observed_at", None)
        return json.dumps(data, sort_keys=True, ensure_ascii=False)

    def reuse_external(self, candidate, need: MaterialNeed, *, visibility: LibraryVisibility,
                       context: UseContext) -> MaterialHandle | None:
        source = candidate.source
        if not source.provider or not source.provider_asset_id:
            return None
        records = self.catalog.list_scope(scope=visibility, context=context,
            media_type=need.media_type, provider=source.provider, limit=1000)
        for record in records:
            if (record.asset.source != source or
                    self._rights_identity(record.asset.rights) != self._rights_identity(candidate.rights)):
                continue
            checked = self.reuse.find_candidates(need, scope=visibility, context=context, records=(record,))
            if checked.candidates:
                return self.resolve(record.asset_ref, visibility=visibility, context=context)
        return None

    def select(self, asset_ref: str, need: MaterialNeed, *, visibility: LibraryVisibility,
               context: UseContext, reference_id: str, enforce_attribution: bool = False) -> MaterialHandle:
        """Bind an explicitly chosen eligible candidate; never choose by rank.

        enforce_attribution asserts that the caller carries returned exact
        credits into the output dependency/export contract, not user consent.
        """
        if context.purpose != "production":
            raise MaterialLibraryError("Production selection needs a production use context")
        record = self.catalog.get(asset_ref, scope=visibility, context=context)
        result = self.reuse.find_candidates(need, scope=visibility, context=context, records=(record,))
        if not result.candidates:
            raise MaterialLibraryError(result.rejected[0].reason if result.rejected else "Material is unavailable")
        admission = result.candidates[0].rights_admission
        attribution = RightsService.attribution_condition_for(record.asset)
        if admission.status is RightsAdmissionStatus.CONDITIONAL and not enforce_attribution:
            raise MaterialLibraryError("Exact attribution must be retained by the output/export contract")
        self.catalog.record_usage(asset_ref, scope=visibility, context=context, reference_id=reference_id,
                    need_ids=(need.need_id,), attribution=attribution.__dict__ if attribution else None)
        return self.resolve(asset_ref, visibility=visibility, context=context)

    def release_reference(self, asset_ref: str, reference_id: str, *, visibility: LibraryVisibility,
                          context: UseContext) -> None:
        self.catalog.release_reference(asset_ref, reference_id, scope=visibility, context=context)

    def delete(self, asset_ref: str, *, visibility: LibraryVisibility, context: UseContext) -> None:
        self.catalog.delete(asset_ref, scope=visibility, context=context)
