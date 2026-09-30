"""Compose existing P0 and P1 supply services for one product Attempt."""

from __future__ import annotations

import hashlib
import json
import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from easel import creation
from easel.materials.application.advanced_matching import AdvancedMaterialMatcher, DirectorPreference
from easel.materials.application.assembly import MaterialBundleAssembler
from easel.materials.application.dedup import MaterialDeduplicator
from easel.materials.application.compiler import NeedCompiler
from easel.materials.application.library_first import LibraryFirstSupplyService
from easel.materials.application.library_reuse import LibraryReuseService
from easel.materials.application.matching import MaterialMatcher
from easel.materials.application.readiness import MaterialReadinessCalculator
from easel.materials.application.standalone import StandaloneMaterialFlow
from easel.materials.application.acquisition import MaterialAcquirer
from easel.materials.domain import (
    MaterialAsset, MaterialBundle, MaterialGap, MaterialPlan, MaterialReadiness,
    RightsInfo, SupplyRun, SupplySourceResult, TechnicalStatus, SemanticField,
)
from easel.materials.library import LibraryScope, MaterialLibraryCatalog
from easel.materials.providers import (
    CoverrProvider, LocalProvider, OpenverseAudioProvider, OpenverseProvider, PexelsProvider,
    PixabayProvider, ProviderRegistry, UnsplashProvider,
)
from easel.materials.semantic_index import MaterialSemanticIndex
from easel.materials.store import AttemptMaterialStore, AttemptMaterialStoreError


@dataclass(frozen=True)
class ProductSupplyResult:
    """One auditable supply result; no Production selection authority."""

    plan: MaterialPlan
    bundle: MaterialBundle
    supply_run: SupplyRun
    readiness: MaterialReadiness
    gaps: tuple[MaterialGap, ...]
    routing_trace: tuple[dict, ...]
    generation_preparation: dict[str, object] | None = None


def product_provider_registry(local_roots: tuple[str | Path, ...]) -> tuple[ProviderRegistry, tuple[str, ...]]:
    """Enable only configured acquisition routes; keep discovery-only routes visible."""
    from easel.runtime_config import EaselRuntimeConfig
    runtime_config = EaselRuntimeConfig.load()
    registry = ProviderRegistry()
    if local_roots:
        registry.register(LocalProvider(tuple(local_roots)))
    missing: list[str] = []
    configured = (
        ("pexels", "PEXELS_API_KEY", PexelsProvider),
        ("pixabay", "PIXABAY_API_KEY", PixabayProvider),
        ("coverr", "COVERR_API_KEY", CoverrProvider),
        ("unsplash", "UNSPLASH_ACCESS_KEY", UnsplashProvider),
    )
    for source_id, key, provider_type in configured:
        value = runtime_config.get(key).strip()
        if runtime_config.providers.credential_presence[source_id]:
            registry.register(provider_type(value))
        else:
            missing.append(source_id)
    # Openverse OAuth credentials are owned by the provider adapter. Search is
    # discovery-only and has no Easel Acquirer route.
    token = runtime_config.get("OPENVERSE_ACCESS_TOKEN", "")
    registry.register(OpenverseProvider(
        token,
        client_id=runtime_config.get("OPENVERSE_CLIENT_ID", ""),
        client_secret=runtime_config.get("OPENVERSE_CLIENT_SECRET", ""),
    ))
    registry.register(OpenverseAudioProvider(
        token,
        client_id=runtime_config.get("OPENVERSE_CLIENT_ID", ""),
        client_secret=runtime_config.get("OPENVERSE_CLIENT_SECRET", ""),
    ))
    return registry, tuple(missing)


class ProductMaterialSupply:
    """Run Library-first policy and P0 acquisition without creating a new supply engine."""

    def __init__(
        self,
        *,
        library_root: str | Path | None = None,
        registry: ProviderRegistry | None = None,
        rights_facts: Callable[[object, MaterialAsset], RightsInfo | None] | None = None,
    ) -> None:
        from easel.runtime_config import EaselRuntimeConfig
        self.library_root = Path(library_root or EaselRuntimeConfig.load().material.library_root).expanduser()
        self.registry = registry
        self.rights_facts = rights_facts

    @staticmethod
    def scope_for_attempt(attempt: dict) -> LibraryScope:
        work = creation.get_creation(attempt["creation_id"])
        profile = work.get("profile")
        if not isinstance(profile, str) or not profile.strip():
            # General mode has no Creator profile. Keep its catalog isolated
            # to this persisted work rather than sharing another profile's assets.
            return LibraryScope(tenant_id="local", creator_id="creation-" + work["id"])
        return LibraryScope(
            tenant_id="local",
            creator_id="profile-" + hashlib.sha256(profile.encode("utf-8")).hexdigest()[:24],
        )

    def run(
        self,
        plan: MaterialPlan,
        attempt: dict,
        *,
        local_roots: tuple[str | Path, ...],
        supply_run_id: str,
        bundle_id: str,
        top_n: int = 3,
        generated_assets: tuple[MaterialAsset, ...] = (),
        search_terms: dict[str, tuple[str, ...]] | None = None,
        skip_need_ids: tuple[str, ...] = (),
    ) -> ProductSupplyResult:
        started_at = datetime.now(timezone.utc)
        store = AttemptMaterialStore(attempt["workspace"]["path"])
        catalog = MaterialLibraryCatalog(self.library_root)
        scope = self.scope_for_attempt(attempt)
        registry, missing_keys = (
            (self.registry, ()) if self.registry is not None
            else product_provider_registry(local_roots)
        )
        assert registry is not None
        infos = registry.infos()
        library_first = LibraryFirstSupplyService(
            LibraryReuseService(catalog),
            AdvancedMaterialMatcher(MaterialSemanticIndex(catalog)),
        )
        matcher = MaterialMatcher()
        assets: dict[str, MaterialAsset] = {}
        try:
            checkpoint = store.read_bundle()
        except AttemptMaterialStoreError:
            checkpoint = None
        gate = attempt.get("material_gate", {})
        if checkpoint is not None and gate:
            if (checkpoint.plan_id != plan.plan_id
                    or gate.get("plan_revision") != MaterialReadinessCalculator.plan_revision(plan)
                    or gate.get("bundle_id") != checkpoint.bundle_id
                    or gate.get("bundle_revision") != checkpoint.revision):
                raise ValueError("现有素材 checkpoint 已变化，不能覆盖或重新供应")
            for asset in checkpoint.assets:
                persisted = store.read_asset(asset.asset_id)
                path = store.resolve_asset_locator(asset.file.path)
                if (persisted != asset or path.stat().st_size != asset.file.size
                        or hashlib.sha256(path.read_bytes()).hexdigest() != asset.file.sha256):
                    raise ValueError("现有素材 checkpoint 字节或证据已变化")
                assets[asset.asset_id] = asset
        trace: list[dict] = []
        source_totals: dict[str, dict[str, object]] = defaultdict(
            lambda: {"candidates": 0, "acquired": 0, "failures": []}
        )
        for generated in generated_assets:
            persisted = store.read_asset(generated.asset_id)
            if persisted != generated:
                raise ValueError("Generation Asset differs from its Attempt record")
            assets[generated.asset_id] = generated
        assets.update(self._current_generated_assets(store, plan))

        for need in plan.needs:
            style = need.constraints.get("preferred_style")
            style_terms = (style,) if isinstance(style, str) and style.strip() else ()
            director_preferences = (DirectorPreference(
                field=SemanticField.STYLE, preferred_values=style_terms,
            ),) if style_terms else ()
            if need.need_id in skip_need_ids or matcher.match(need, tuple(assets.values())).matches:
                trace.append({"need_id": need.need_id, "checkpoint_reused": True,
                              "attempted_sources": [], "failures": [],
                              "selection_authority": False})
                continue
            def source_supply(source_id: str, requested_need=need) -> tuple[MaterialAsset, ...]:
                source_registry = ProviderRegistry()
                source_registry.register(registry.get(source_id))
                subset = plan.model_copy(update={"needs": (requested_need,)})
                key = hashlib.sha256(f"{supply_run_id}\0{source_id}\0{requested_need.need_id}".encode()).hexdigest()[:20]
                flow = StandaloneMaterialFlow(
                    source_registry,
                    store,
                    acquirer=MaterialAcquirer(store, local_roots=local_roots),
                    rights_facts=self.rights_facts,
                    compiler=NeedCompiler(search_terms=search_terms),
                )
                result = flow.run(
                    subset, supply_run_id=f"source-{key}", bundle_id=f"source-bundle-{key}", top_n=top_n,
                    persist_bundle=False, creative_mode_terms=style_terms,
                )
                for item in result.supply_run.provider_results:
                    totals = source_totals[item.source_id]
                    totals["candidates"] = int(totals["candidates"]) + item.candidates_found
                    totals["acquired"] = int(totals["acquired"]) + item.acquired_assets
                    if item.failure_summary:
                        totals["failures"].append(item.failure_summary)
                return result.assets

            result = library_first.supply_need(
                need, scope=scope, creation_id=attempt["creation_id"],
                attempt_id=attempt["attempt_id"], provider_infos=infos,
                external_supply=source_supply, director_preferences=director_preferences,
            )
            library_by_id = {item.library_asset_id: item for item in result.reuse_candidates}
            for matched in result.library_matches:
                candidate = library_by_id[matched.library_asset_id]
                imported = self._import_library(candidate.record, catalog, store, scope)
                assets[imported.asset_id] = imported
            for asset in result.external_assets:
                assets[asset.asset_id] = asset
            trace.append({
                "need_id": need.need_id,
                "library_search_called": True,
                "structured_search_called": True,
                "semantic_search_called": True,
                "reuse_candidates": len(result.reuse_candidates),
                "advanced_matches": len(result.library_matches),
                "library_asset_ids": [match.library_asset_id for match in result.library_matches],
                "routes": [{"source_id": route.source_id, "kind": route.kind.value,
                            "order": route.order} for route in result.routing.routes],
                "skipped": [{"source_id": item.source_id, "reason": item.reason}
                            for item in result.routing.skipped],
                "unconfigured": list(missing_keys),
                "attempted_sources": list(result.attempted_sources),
                "failures": [{"source_id": item.source_id, "error": item.error}
                             for item in result.failures],
                "generation_route_eligible": result.generation_route is not None,
                "selection_authority": False,
            })

        all_assets = tuple(assets.values())
        matches = []
        deduplicator = MaterialDeduplicator(store)
        for need in plan.needs:
            ranked = matcher.match(need, all_assets)
            shortlist = deduplicator.deduplicate_and_diversify(
                ranked.matches, all_assets, top_k=top_n,
            ).shortlist
            matches.extend(shortlist)
        finished_at = datetime.now(timezone.utc)
        provider_results = tuple(
            SupplySourceResult(
                source_id=source_id,
                status="FAILED" if values["failures"] and not values["acquired"] else
                "PARTIAL" if values["failures"] else "COMPLETE",
                candidates_found=int(values["candidates"]),
                acquired_assets=int(values["acquired"]),
                failure_summary=";".join(str(item) for item in values["failures"]) or None,
            )
            for source_id, values in sorted(source_totals.items())
        )
        run = SupplyRun(
            supply_run_id=supply_run_id, plan_id=plan.plan_id,
            parent_run_id=checkpoint.supply_run_id if checkpoint is not None and gate else None,
            started_at=started_at, finished_at=finished_at,
            provider_results=provider_results,
            failures=tuple(
                f"{item['source_id']}:{item['error']}"
                for row in trace for item in row["failures"]
            ),
            result_bundle_id=bundle_id,
        )
        bundle = MaterialBundleAssembler().assemble(plan, run, all_assets, tuple(matches), bundle_id=bundle_id)
        if checkpoint is not None and gate:
            if store.read_bundle() != checkpoint or any(
                    store.read_asset(asset.asset_id) != asset for asset in checkpoint.assets):
                raise ValueError("素材 checkpoint 在检索期间变化，拒绝覆盖，请先刷新核对")
        store.write_supply_run(run)
        store.write_bundle(bundle)
        readiness, gaps = MaterialReadinessCalculator(store=store).calculate(plan, bundle)
        generation_preparation: dict[str, object] | None = None
        if readiness.status.value == "NOT_READY":
            blocking_need_ids = {gap.need_id for gap in gaps}
            trace_by_need = {row["need_id"]: row for row in trace}
            eligible_need = next((need for need in plan.needs
                                  if need.need_id in blocking_need_ids
                                  and trace_by_need.get(need.need_id, {}).get("generation_route_eligible") is True), None)
            if eligible_need is not None:
                generation_preparation = {
                    "status": "MATERIAL_GENERATION_AVAILABLE",
                    "need_id": eligible_need.need_id,
                }
                for row in trace:
                    if row["need_id"] == eligible_need.need_id:
                        row["generation_preparation"] = generation_preparation
                        break
        evidence_path = store.materials_root / "product-supply.json"
        if evidence_path.is_symlink():
            raise AttemptMaterialStoreError("Product supply evidence path must not be a symlink")
        evidence_path.write_text(json.dumps({
            "schema": "easel-product-supply@1", "plan_id": plan.plan_id,
            "attempt_id": attempt["attempt_id"], "library_scope": scope.key,
            "library_root": str(catalog.root), "routing": trace,
            "generation_preparation": generation_preparation,
        }, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return ProductSupplyResult(
            plan, bundle, run, readiness, gaps, tuple(trace), generation_preparation,
        )

    @staticmethod
    def _current_generated_assets(store: AttemptMaterialStore, plan: MaterialPlan) -> dict[str, MaterialAsset]:
        """Rehydrate only completed generated Assets bound to this exact Plan revision."""
        plan_revision = MaterialReadinessCalculator.plan_revision(plan)
        needs = {need.need_id: need for need in plan.needs}
        restored: dict[str, MaterialAsset] = {}
        for record in store.list_generation_records():
            if (record.get("schema") != "easel-material-generation@1"
                    or record.get("status") != "COMPLETE"
                    or record.get("attempt_id") != plan.attempt_id
                    or record.get("plan_id") != plan.plan_id
                    or record.get("plan_revision") != plan_revision):
                continue
            need = needs.get(record.get("need_id"))
            asset_id = record.get("asset_id")
            if need is None or not isinstance(asset_id, str):
                continue
            try:
                asset = store.read_asset(asset_id)
                path = store.resolve_asset_locator(asset.file.path)
            except (AttemptMaterialStoreError, OSError):
                continue
            if (asset.source.kind != "generative"
                    or asset.media_type is not need.media_type
                    or asset.technical.status is not TechnicalStatus.PASSED
                    or record.get("asset_path") != asset.file.path
                    or record.get("asset_sha256") != asset.file.sha256
                    or record.get("asset_bytes") != asset.file.size):
                continue
            digest = hashlib.sha256()
            size = 0
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
                    size += len(chunk)
            if digest.hexdigest() != asset.file.sha256 or size != asset.file.size:
                continue
            restored[asset.asset_id] = asset
        return restored

    @staticmethod
    def _import_library(record, catalog: MaterialLibraryCatalog,
                        store: AttemptMaterialStore, scope: LibraryScope) -> MaterialAsset:
        if record.scope != scope:
            raise ValueError("Library record belongs to another Creator scope")
        source = catalog.resolve_physical_locator(record)
        asset_id = "reuse-" + record.asset.file.sha256[:24]
        try:
            existing = store.read_asset(asset_id)
            path = store.resolve_asset_locator(existing.file.path)
            if existing.file.sha256 != record.asset.file.sha256 or hashlib.sha256(path.read_bytes()).hexdigest() != existing.file.sha256:
                raise ValueError("Existing Library reuse bytes are stale")
            return existing
        except AttemptMaterialStoreError:
            pass
        content = source.read_bytes()
        if hashlib.sha256(content).hexdigest() != record.asset.file.sha256:
            raise ValueError("Library object changed during Attempt import")
        filename = "original" + source.suffix.lower()
        locator = store.write_asset_bytes(asset_id, filename, content)
        file = record.asset.file.model_copy(update={"path": locator})
        asset = record.asset.model_copy(update={
            "asset_id": asset_id, "file": file,
            "lineage": record.asset.lineage.model_copy(update={
                "references": tuple(dict.fromkeys((*record.asset.lineage.references,
                    f"material-library:{record.library_asset_id}"))),
            }),
        })
        store.write_asset(asset)
        store.write_acquisition_evidence(asset_id, {
            "method": "material_library", "library_asset_id": record.library_asset_id,
            "library_scope": scope.key, "source_attempt_id": record.source_attempt_id,
            "sha256": record.asset.file.sha256,
        })
        return asset
