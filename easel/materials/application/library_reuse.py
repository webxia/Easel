"""Candidate discovery adapted from V1 library_reuse.py (57c8e2ad).

Apache-2.0. Re-evaluate current purpose and bytes; do not exclude assets merely
because they were used in the same work. Search never selects production media.
"""
from __future__ import annotations

from dataclasses import dataclass

from easel.materials.application.rights import RightsAdmission, RightsAdmissionStatus, RightsService
from easel.materials.domain import MaterialNeed, TechnicalStatus
from easel.materials.library import LibraryVisibility, MaterialLibraryCatalog, MaterialLibraryRecord, UseContext
from easel.materials.store import MaterialStoreError


@dataclass(frozen=True)
class LibraryReuseCandidate:
    record: MaterialLibraryRecord
    rights_admission: RightsAdmission
    selected_for_production: bool = False

    @property
    def library_asset_id(self):
        return self.record.library_asset_id

    @property
    def asset(self):
        return self.record.asset


@dataclass(frozen=True)
class LibraryReuseRejection:
    library_asset_id: str
    reason: str


@dataclass(frozen=True)
class LibraryReuseSearchResult:
    candidates: tuple[LibraryReuseCandidate, ...]
    rejected: tuple[LibraryReuseRejection, ...]
    search_mode: str = "METADATA_FALLBACK"
    fallback_reason: str | None = "embedding_provider_disabled"


class LibraryReuseService:
    def __init__(self, catalog: MaterialLibraryCatalog, rights: RightsService | None = None):
        self.catalog = catalog
        self.rights = rights or RightsService()

    def evaluate(self, record: MaterialLibraryRecord, need: MaterialNeed, context: UseContext) -> RightsAdmission:
        # Confirmed work constraints override model-supplied candidate constraints.
        current = need.model_copy(update={"constraints": {**need.constraints, **context.constraints}})
        return self.rights.evaluate(record.asset, current,
                                   attribution=self.rights.attribution_condition_for(record.asset))

    def find_candidates(self, need: MaterialNeed, *, scope: LibraryVisibility,
                        context: UseContext, limit: int = 100,
                        records: tuple[MaterialLibraryRecord, ...] | None = None) -> LibraryReuseSearchResult:
        if records is None:
            records = self.catalog.metadata_search(scope=scope, context=context,
                       media_type=need.media_type, limit=limit)
        candidates = []
        rejected = []
        for candidate in records:
            # Re-read even caller-provided search hits; an index is not authority.
            record = self.catalog.get(candidate.library_asset_id, scope=scope, context=context, missing_ok=True)
            if record is None:
                continue
            reason = None
            if record.asset.media_type is not need.media_type:
                reason = "media_type_mismatch"
            elif context.purpose == "production" and record.input_purpose == "reference":
                reason = "reference_only"
            elif record.asset.technical.status is not TechnicalStatus.PASSED:
                reason = "technical_inspection_not_passed"
            try:
                self.catalog.resolve_physical_locator(record)
            except (MaterialStoreError, OSError):
                reason = "library_object_unavailable"
            admission = self.evaluate(record, need, context)
            if context.purpose == "production" and admission.status not in {RightsAdmissionStatus.ADMITTED, RightsAdmissionStatus.CONDITIONAL}:
                reason = admission.reason
            if reason:
                rejected.append(LibraryReuseRejection(record.library_asset_id, reason))
                continue
            candidates.append(LibraryReuseCandidate(record, admission))
        return LibraryReuseSearchResult(tuple(candidates), tuple(rejected))
