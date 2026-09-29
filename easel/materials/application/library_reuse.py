"""Explicit cross-Attempt Material Library reuse candidate discovery."""

from __future__ import annotations

from dataclasses import dataclass

from easel.materials.application.rights import RightsAdmission, RightsAdmissionStatus, RightsService
from easel.materials.domain import MaterialAsset, MaterialNeed, TechnicalStatus
from easel.materials.library import (
    LibraryScope,
    MaterialLibraryCatalog,
    MaterialLibraryError,
    MaterialLibraryRecord,
    MaterialLibraryUsage,
)


@dataclass(frozen=True)
class LibraryReuseCandidate:
    """Eligible catalog supply option, with no Production selection authority."""

    library_asset_id: str
    asset: MaterialAsset
    record: MaterialLibraryRecord
    usage_history: tuple[MaterialLibraryUsage, ...]
    rights_admission: RightsAdmission
    selected_for_production: bool = False


@dataclass(frozen=True)
class LibraryReuseRejection:
    library_asset_id: str
    reason: str


@dataclass(frozen=True)
class LibraryReuseSearchResult:
    candidates: tuple[LibraryReuseCandidate, ...]
    rejected: tuple[LibraryReuseRejection, ...]


class LibraryReuseService:
    """Discover candidates and revalidate them against a current Need.

    This service does not copy objects into an Attempt, bind assets to a Need,
    or choose Production material. The caller must perform those workflow
    decisions independently after inspecting returned candidates.
    """

    def __init__(self, catalog: MaterialLibraryCatalog, rights: RightsService | None = None):
        self.catalog = catalog
        self.rights = rights or RightsService()

    def find_candidates(
        self,
        need: MaterialNeed,
        *,
        scope: LibraryScope,
        creation_id: str,
        attempt_id: str,
        limit: int = 100,
    ) -> LibraryReuseSearchResult:
        records = self.catalog.metadata_search(
            scope=scope,
            media_type=need.media_type,
            technical_status=TechnicalStatus.PASSED,
            limit=limit,
        )
        candidates: list[LibraryReuseCandidate] = []
        rejected: list[LibraryReuseRejection] = []
        for record in records:
            if record.source_attempt_id == attempt_id:
                rejected.append(LibraryReuseRejection(record.library_asset_id, "same_attempt_source"))
                continue
            prior_attempt_usage = tuple(
                usage for usage in self.catalog.usage_for_asset(record.library_asset_id, scope=scope)
                if usage.creation_id == creation_id and usage.attempt_id == attempt_id
            )
            if prior_attempt_usage:
                rejected.append(LibraryReuseRejection(record.library_asset_id, "already_used_in_attempt"))
                continue
            try:
                self.catalog.resolve_physical_locator(record)
            except MaterialLibraryError:
                rejected.append(LibraryReuseRejection(record.library_asset_id, "library_object_unavailable"))
                continue
            admission = self.rights.evaluate(record.asset, need)
            if admission.status is not RightsAdmissionStatus.ADMITTED:
                rejected.append(LibraryReuseRejection(
                    record.library_asset_id,
                    f"rights_{admission.status.value.lower()}:{admission.reason}",
                ))
                continue
            candidates.append(LibraryReuseCandidate(
                library_asset_id=record.library_asset_id,
                asset=record.asset,
                record=record,
                usage_history=self.catalog.usage_for_asset(record.library_asset_id, scope=scope),
                rights_admission=admission,
                selected_for_production=False,
            ))
        return LibraryReuseSearchResult(tuple(candidates), tuple(rejected))


__all__ = [
    "LibraryReuseCandidate",
    "LibraryReuseRejection",
    "LibraryReuseSearchResult",
    "LibraryReuseService",
]
