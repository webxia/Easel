"""Bounded library-first supply adapted from V1 library_first.py (57c8e2ad).

V2 keeps source isolation and finite fallback, but removes the old Attempt
budget, ranking authority and generation dispatch. The director selects media.
"""
from __future__ import annotations

from dataclasses import dataclass

from easel.materials.domain import MaterialNeed
from easel.materials.library import LibraryVisibility, UseContext
from easel.materials.application.acquisition import MediaDownloader, RemoteURLPolicy
from easel.materials.application.library_reuse import LibraryReuseCandidate
from easel.materials.application.rights import RightsAdmissionStatus


@dataclass(frozen=True)
class SupplyFailure:
    source: str
    reason: str


@dataclass(frozen=True)
class MaterialSupplyResult:
    candidates: tuple[LibraryReuseCandidate, ...]
    required_asset_refs: tuple[str, ...]
    attempted_sources: tuple[str, ...]
    failures: tuple[SupplyFailure, ...]
    gap: str | None = None
    generation_route: dict | None = None


class MaterialSupply:
    def __init__(self, materials, *, providers=(), downloaders=None,
                 max_sources: int = 3, max_candidates: int = 8):
        if not 1 <= max_sources <= 10 or not 1 <= max_candidates <= 80:
            raise ValueError("Invalid bounded supply limits")
        self.materials, self.providers = materials, tuple(providers)
        self.downloaders = downloaders or {}
        self.max_sources, self.max_candidates = max_sources, max_candidates

    def supply(self, need: MaterialNeed, *, visibility: LibraryVisibility, context: UseContext,
               required_asset_refs: tuple[str, ...] = (), allowed_providers: tuple[str, ...] = (),
               allow_generation: bool = False, excluded_asset_refs: tuple[str, ...] = (),
               check_current=None, check_provider=None) -> MaterialSupplyResult:
        selected, failures, attempted = [], [], []
        # Required input cannot be silently replaced by a stock or generated hit.
        for asset_ref in required_asset_refs:
            record = self.materials.catalog.get(asset_ref, scope=visibility, context=context, missing_ok=True)
            result = self.materials.reuse.find_candidates(need, scope=visibility, context=context,
                                                          records=(record,) if record else ())
            if not result.candidates:
                return MaterialSupplyResult((), required_asset_refs, (), (), gap="required_material_unavailable")
            selected.append(result.candidates[0])
        prior = self.materials.candidates(need, visibility=visibility, context=context,
                                          query=need.intent.description, limit=self.max_candidates)
        seen = {c.library_asset_id for c in selected}
        digests = {c.asset.file.sha256 for c in selected}
        for candidate in prior.candidates:
            if candidate.library_asset_id in seen or candidate.library_asset_id in excluded_asset_refs or candidate.asset.file.sha256 in digests:
                continue
            selected.append(candidate)
            seen.add(candidate.library_asset_id)
            digests.add(candidate.asset.file.sha256)
        if len(selected) >= need.desired_options:
            return MaterialSupplyResult(tuple(selected), required_asset_refs, (), ())
        for provider in self.providers:
            if check_current is not None:
                check_current()
            if provider.provider_id not in allowed_providers or len(attempted) >= self.max_sources:
                continue
            if len(selected) >= need.desired_options:
                break
            if check_provider is not None:
                check_provider(provider.provider_id)
            attempted.append(provider.provider_id)
            try:
                candidates = provider.search(need.intent.description, media_type=need.media_type, limit=self.max_candidates)
            except Exception as exc:
                code = getattr(exc, "code", None)
                failures.append(SupplyFailure(provider.provider_id, code if code in {"capability_unavailable", "source_unavailable"} else type(exc).__name__))
                continue
            downloader = self.downloaders.get(provider.provider_id) or MediaDownloader(RemoteURLPolicy(provider.allowed_hosts))
            for candidate in tuple(candidates)[:self.max_candidates]:
                if check_current is not None:
                    check_current()
                if len(selected) >= need.desired_options:
                    break
                if check_provider is not None:
                    check_provider(provider.provider_id)
                if candidate.media_type is not need.media_type:
                    failures.append(SupplyFailure(provider.provider_id, "media_type_mismatch"))
                    continue
                try:
                    admission = self.materials.preflight_external(candidate, need, context)
                    if admission.status not in {RightsAdmissionStatus.ADMITTED, RightsAdmissionStatus.CONDITIONAL}:
                        failures.append(SupplyFailure(provider.provider_id, admission.reason))
                        continue
                    handle = self.materials.reuse_external(candidate, need, visibility=visibility, context=context)
                    if handle is None:
                        downloaded = downloader.download(candidate.download_url, media_type=need.media_type.value)
                        if check_current is not None:
                            check_current()
                        handle = self.materials.ingest_downloaded(downloaded, visibility=visibility, context=context,
                            media_type=need.media_type, source=candidate.source, rights=candidate.rights, semantic=candidate.semantic)
                    record = self.materials.catalog.get(handle.asset_ref, scope=visibility, context=context)
                    checked = self.materials.reuse.find_candidates(need, scope=visibility, context=context, records=(record,))
                    if not checked.candidates:
                        failures.append(SupplyFailure(provider.provider_id, checked.rejected[0].reason if checked.rejected else "material_unavailable"))
                        continue
                    if handle.digest in digests or handle.asset_ref in excluded_asset_refs:
                        continue
                    selected.extend(checked.candidates)
                    digests.add(handle.digest)
                except Exception as exc:
                    failures.append(SupplyFailure(provider.provider_id, type(exc).__name__))
        gap = "insufficient_eligible_materials" if len(selected) < need.desired_options else None
        route = {"kind": need.media_type.value.upper(), "need_id": need.need_id,
                 "requires_director_selection": True} if gap and allow_generation and need.media_type.value in {"image", "video"} else None
        return MaterialSupplyResult(tuple(selected), required_asset_refs, tuple(attempted), tuple(failures), gap, route)
