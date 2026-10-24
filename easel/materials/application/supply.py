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
    search_diagnostics: tuple[SupplyFailure, ...] = ()


class MaterialSupply:
    def __init__(self, materials, *, providers=(), downloaders=None,
                 max_sources: int = 3, max_candidates: int = 8, sfx_embedding_provider=None):
        if not 1 <= max_sources <= 10 or not 1 <= max_candidates <= 80:
            raise ValueError("Invalid bounded supply limits")
        self.materials, self.providers = materials, tuple(providers)
        self.downloaders = downloaders or {}
        self.max_sources, self.max_candidates = max_sources, max_candidates
        self.sfx_embedding_provider = sfx_embedding_provider

    def supply(self, need: MaterialNeed, *, visibility: LibraryVisibility, context: UseContext,
               required_asset_refs: tuple[str, ...] = (), allowed_providers: tuple[str, ...] = (),
               allow_generation: bool = False, excluded_asset_refs: tuple[str, ...] = (),
               check_current=None, check_provider=None) -> MaterialSupplyResult:
        selected, failures, attempted, diagnostics = [], [], [], []
        # Required input cannot be silently replaced by a stock or generated hit.
        for asset_ref in required_asset_refs:
            record = self.materials.catalog.get(asset_ref, scope=visibility, context=context, missing_ok=True)
            result = self.materials.reuse.find_candidates(need, scope=visibility, context=context,
                                                          records=(record,) if record else ())
            if not result.candidates:
                return MaterialSupplyResult((), required_asset_refs, (), (), gap="required_material_unavailable")
            selected.append(result.candidates[0])
        # An explicit source page identifies a particular item, not semantic
        # search terms. Reuse by provider identity below after exact lookup.
        exact_source = need.intent.description.strip().lower().startswith(('http://', 'https://'))
        prior = None if exact_source else self.materials.candidates(need, visibility=visibility, context=context,
                                          query=need.intent.description, limit=self.max_candidates)
        seen = {c.library_asset_id for c in selected}
        digests = {c.asset.file.sha256 for c in selected}
        for candidate in prior.candidates if prior else ():
            if candidate.library_asset_id in seen or candidate.library_asset_id in excluded_asset_refs or candidate.asset.file.sha256 in digests:
                continue
            selected.append(candidate)
            seen.add(candidate.library_asset_id)
            digests.add(candidate.asset.file.sha256)
        if len(selected) >= need.desired_options:
            return MaterialSupplyResult(tuple(selected), required_asset_refs, (), ())
        if (not exact_source and need.media_type.value == 'audio' and need.role == 'sfx'
                and self.sfx_embedding_provider is not None and len(selected) < self.max_candidates):
            if check_current is not None:
                check_current()
            supplement = self.materials.candidates(need, visibility=visibility, context=context,
                query=need.intent.description, limit=self.max_candidates,
                embedding_provider=self.sfx_embedding_provider, semantic_supplement=True)
            if supplement.fallback_reason:
                diagnostics.append(SupplyFailure('local_sfx_semantic', supplement.fallback_reason))
            for candidate in supplement.candidates:
                if (candidate.library_asset_id in seen or candidate.library_asset_id in excluded_asset_refs
                        or candidate.asset.file.sha256 in digests):
                    continue
                selected.append(candidate)
                seen.add(candidate.library_asset_id)
                digests.add(candidate.asset.file.sha256)
                if len(selected) >= self.max_candidates:
                    break
            if check_current is not None:
                check_current()
            if len(selected) >= need.desired_options:
                return MaterialSupplyResult(tuple(selected), required_asset_refs, (), tuple(failures),
                    search_diagnostics=tuple(diagnostics))
        for provider in self.providers:
            if check_current is not None:
                check_current()
            if provider.provider_id not in allowed_providers or len(attempted) >= self.max_sources:
                continue
            if len(selected) >= need.desired_options:
                break
            # Audio source identities can be role-specific even though their
            # physical MediaType is always AUDIO. Never search the SFX source
            # to fill a music need or reverse the roles.
            source_roles = getattr(provider, 'audio_roles', None)
            if need.media_type.value == 'audio' and source_roles and need.role not in source_roles:
                continue
            if check_provider is not None:
                check_provider(provider.provider_id)
            attempted.append(provider.provider_id)
            try:
                candidates = provider.search(need.intent.description, media_type=need.media_type, limit=self.max_candidates)
            except Exception as exc:
                code = getattr(exc, "code", None)
                failures.append(SupplyFailure(provider.provider_id, code if code in {
                    "capability_unavailable","source_unavailable","network_timeout",
                    "network_connection","http_permission","http_rate_limited",
                    "http_unavailable","invalid_response"} else "invalid_response"))
                continue
            if not candidates:
                failures.append(SupplyFailure(provider.provider_id,"no_results"))
            downloader = self.downloaders.get(provider.provider_id) or MediaDownloader(
                RemoteURLPolicy(provider.allowed_hosts),
                user_agent=getattr(provider,'download_user_agent','Easel/2 material acquisition'))
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
                # An explicitly classified public-audio item cannot be used
                # as a different role. Selection still requires listening.
                audio_roles = candidate.semantic.attributes.get('audio_roles')
                if (need.media_type.value == 'audio' and audio_roles
                        and need.role not in audio_roles):
                    failures.append(SupplyFailure(provider.provider_id, 'audio_role_incompatible'))
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
                        # Providers with a source-side file digest must verify
                        # downloaded bytes against that reviewed revision.
                        verify = getattr(provider, 'verify_download', None)
                        if verify is not None:
                            verify(candidate, downloaded)
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
                    from .acquisition import AcquisitionError
                    failures.append(SupplyFailure(provider.provider_id,
                        "download_failed" if isinstance(exc,AcquisitionError) else "material_ineligible"))
        gap = "insufficient_eligible_materials" if len(selected) < need.desired_options else None
        route = {"kind": need.media_type.value.upper(), "need_id": need.need_id,
                 "requires_director_selection": True} if gap and allow_generation and need.media_type.value in {"image", "video"} else None
        return MaterialSupplyResult(tuple(selected), required_asset_refs, tuple(attempted), tuple(failures), gap, route,
                                   search_diagnostics=tuple(diagnostics))
