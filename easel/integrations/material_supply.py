"""Compose existing P0 and P1 supply services for one product Attempt."""

from __future__ import annotations

from easel.integrations.hypit.secrets import SecretRedactor

import hashlib
import json
import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
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
from easel.materials.application.acquisition import MaterialAcquirer, RemoteURLPolicy
from easel.materials.domain import (
    MaterialAsset, MaterialBundle, MaterialGap, MaterialPlan, MaterialReadiness, MediaType,
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
        additional_visual_need_ids: tuple[str, ...] = (),
    ) -> ProductSupplyResult:
        started_at = datetime.now(timezone.utc)
        started = monotonic()
        if set(additional_visual_need_ids) - {n.need_id for n in plan.needs if n.media_type in {MediaType.IMAGE, MediaType.VIDEO}}:
            raise ValueError('额外视觉补料只能使用现有图像或视频 Need')
        store = AttemptMaterialStore(attempt["workspace"]["path"])
        from easel.creation_delivery import is_managed
        retain_sources = is_managed(creation.get_creation(attempt['creation_id'])) or supply_run_id.startswith('supplement-')
        from easel.creation_delivery import active_delivery
        if active_delivery.get() == attempt['creation_id']:
            with creation.edit_creation(attempt['creation_id']) as work:
                work['delivery'].setdefault('material_started_at', creation._now())
        catalog = MaterialLibraryCatalog(self.library_root)
        scope = self.scope_for_attempt(attempt)
        registry, missing_keys = (
            (self.registry, ()) if self.registry is not None
            else product_provider_registry(local_roots)
        )
        assert registry is not None
        infos = registry.infos()
        from easel.materials.application.routing import ProviderRoutingPolicy
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
        retained_ids = set(assets)
        retained_hashes = frozenset(a.file.sha256 for a in assets.values())

        for need in plan.needs:
            style = need.constraints.get("preferred_style")
            style_terms = (style,) if isinstance(style, str) and style.strip() else ()
            director_preferences = (DirectorPreference(
                field=SemanticField.STYLE, preferred_values=style_terms,
            ),) if style_terms else ()
            additional = need.need_id in additional_visual_need_ids
            reusable = tuple(a for a in assets.values() if not additional or a.asset_id not in retained_ids)
            if need.need_id in skip_need_ids or matcher.match(need, reusable).matches:
                trace.append({"need_id": need.need_id, "checkpoint_reused": True,
                              "attempted_sources": [], "failures": [],
                              "selection_authority": False})
                continue
            # A rejected batch can continue at an untried capable source. Keep
            # one external source per pass, rather than fan-out on every retry.
            from easel.materials.application.visual_observation import scoped_inference
            current_intent = hashlib.sha256(NeedCompiler.for_plan(plan, search_terms=search_terms).compile(need, creative_mode_terms=style_terms).to_json().encode()).hexdigest()
            current_links = (store.read_recovery_record('candidate-links') or {}).get('assets', {})
            rejected_sources = {a.source.provider for a in assets.values()
                if any(r.get('need_id') == need.need_id and r.get('compiled_intent_sha256') == current_intent
                       for r in current_links.get(a.asset_id, []))
                if a.media_type is need.media_type and any(
                    scoped_inference(need, a, i) and any((ann.evidence or '').endswith(':unsuitable')
                        for ann in i.annotations) for i in a.semantic.inferences)
                and not matcher.match(need, (a,)).matches}
            preferred = tuple(i.provider_id for i in infos if i.provider_id not in rejected_sources)
            policy = ProviderRoutingPolicy(preferred_provider_order=preferred, max_external_providers=1)
            reused_queries, reused_assets, duplicate_bytes = [], [], []
            search_clock = []
            wire_queries = []
            def source_supply(source_id: str, requested_need=need) -> tuple[MaterialAsset, ...]:
                wire_queries.clear()
                def before_search(provider_id, intent, retry):
                    from easel.creation_delivery import active_delivery, reserve_delivery_call, DeliveryExecutionUncertain
                    cid = active_delivery.get()
                    if cid != attempt['creation_id']:
                        return
                    search_clock[:] = [monotonic()]
                    with creation.edit_creation(cid) as work:
                        if any(c.get('status') in {'pending', 'submitting'} for c in work['delivery'].get('agent_calls', {}).values()):
                            raise DeliveryExecutionUncertain('素材检索前已有未知提交，先核对原执行')
                        stage, ordinal = reserve_delivery_call(work, category='provider_search', stage_override='material',
                            need_count=len(plan.needs), source_count=len(infos))
                        work['delivery'].setdefault('provider_calls', []).append({
                            'stage': stage, 'stage_ordinal': ordinal, 'provider_id': provider_id,
                            'need_id': intent.need_id, 'retry': retry, 'supply_run_id': supply_run_id,
                            'intent_sha256': hashlib.sha256(intent.to_json().encode()).hexdigest(),
                            'query_hints': SecretRedactor.redact(list(intent.semantic_queries)), 'created_at': creation._now()})
                def after_search(provider_id, intent, query, failure_type):
                    wire_queries.append(SecretRedactor.redact(query))
                    from easel.creation_delivery import active_delivery
                    cid = active_delivery.get()
                    if cid != attempt['creation_id']:
                        return
                    with creation.edit_creation(cid) as work:
                        record = work['delivery']['provider_calls'][-1]
                        if record['provider_id'] == provider_id and record['need_id'] == intent.need_id:
                            record.update(actual_query=SecretRedactor.redact(query), failure_type=failure_type,
                                finished_at=creation._now(), elapsed_seconds=round(monotonic() - search_clock[0], 6))
                source_registry = ProviderRegistry(before_search=before_search, after_search=after_search)
                source_registry.register(registry.get(source_id))
                subset = plan.model_copy(update={"needs": (requested_need,)})
                key = hashlib.sha256(f"{supply_run_id}\0{source_id}\0{requested_need.need_id}".encode()).hexdigest()[:20]
                provider = registry.get(source_id)
                local_revision = []
                if isinstance(provider, LocalProvider):
                    # Local media and byte-bound Rights sidecars are mutable
                    # inputs. Cache reuse must notice additions/changed evidence.
                    for media_path in provider._supported_files(requested_need.media_type):
                        for path in (media_path, Path(str(media_path) + '.rights.json')):
                            if path.exists() and not path.is_symlink():
                                stat = path.stat()
                                local_revision.append((str(path), stat.st_size, stat.st_mtime_ns))
                input_sha256 = hashlib.sha256(json.dumps({
                    'plan': subset.model_dump(mode='json'), 'style': style_terms,
                    'search_terms': (search_terms or {}).get(requested_need.need_id), 'top_n': top_n,
                    'compiled_intent': NeedCompiler.for_plan(plan, search_terms=search_terms).compile(requested_need,
                        creative_mode_terms=style_terms).model_dump(mode='json'),
                    'provider_contract': provider.info().model_dump(mode='json'),
                    'local_roots': [str(Path(p).resolve()) for p in local_roots], 'local_revision': local_revision,
                }, sort_keys=True).encode()).hexdigest()
                # Query/input identity, independent of the surrounding recovery
                # run. A completed empty query is reusable too.
                key = hashlib.sha256((source_id + input_sha256).encode()).hexdigest()[:20]
                receipt = store.read_recovery_record(f'source-{key}') if retain_sources else None
                if receipt is not None:
                    wire_queries[:] = receipt.get('actual_queries', [])
                    reused_queries.append(source_id)
                    if receipt.get('input_sha256') != input_sha256:
                        raise ValueError('同一素材供应请求不能改变检索依据')
                    restored = tuple(MaterialAsset.model_validate_json(json.dumps(item)) for item in receipt['assets'])
                    for asset in restored:
                        path = store.resolve_asset_locator(asset.file.path)
                        current = store.read_asset(asset.asset_id)
                        if (current.file != asset.file or current.source != asset.source
                                or current.technical != asset.technical or path.stat().st_size != asset.file.size
                                or hashlib.sha256(path.read_bytes()).hexdigest() != asset.file.sha256):
                            raise ValueError('已完成素材供应的结果已变化，不能重复请求或覆盖')
                    restored = tuple(store.read_asset(a.asset_id) for a in restored)
                    reused_assets.extend(a.asset_id for a in restored)
                    results = tuple(SupplySourceResult.model_validate_json(json.dumps(item)) for item in receipt['provider_results'])
                else:
                    restored = None
                flow = StandaloneMaterialFlow(
                    source_registry,
                    store,
                    acquirer=MaterialAcquirer(store, local_roots=local_roots),
                    rights_facts=self.rights_facts,
                    compiler=NeedCompiler.for_plan(plan, search_terms=search_terms),
                )
                if restored is None:
                    result = flow.run(
                        subset, supply_run_id=f"source-{key}", bundle_id=f"source-bundle-{key}", top_n=top_n,
                        persist_bundle=False, creative_mode_terms=style_terms,
                        excluded_sources=frozenset((a.media_type.value, a.source.provider or 'unknown',
                                                   a.source.provider_asset_id or a.source.source_page)
                                                  for a in assets.values()
                                                  if a.source.provider_asset_id or a.source.source_page) if retain_sources else frozenset(),
                    )
                    restored, results = result.assets, result.supply_run.provider_results
                    if retain_sources and all(r.status != 'FAILED' for r in results):
                        store.write_recovery_record(f'source-{key}', {
                            'input_sha256': input_sha256, 'assets': [a.model_dump(mode='json') for a in restored],
                            'provider_results': [r.model_dump(mode='json') for r in results],
                            'actual_queries': list(wire_queries),
                            'candidate_origins': [{
                                'provider': c.source.provider, 'provider_asset_id': c.source.provider_asset_id,
                                'source_page': RemoteURLPolicy.redact(c.source.source_page), 'media_type': c.media_type.value, 'rank': rank}
                                for r in result.provider_results if r.page is not None
                                for rank, c in enumerate(r.page.candidates)],
                        })
                for item in results:
                    totals = source_totals[item.source_id]
                    totals["candidates"] = int(totals["candidates"]) + item.candidates_found
                    totals["acquired"] = int(totals["acquired"]) + (item.acquired_assets if receipt is None else 0)
                    if item.failure_summary:
                        totals["failures"].append(item.failure_summary)
                links = store.read_recovery_record('candidate-links') or {'assets': {}}
                origins = receipt.get('candidate_origins', []) if receipt is not None else [
                    {'provider': c.source.provider, 'provider_asset_id': c.source.provider_asset_id,
                     'source_page': RemoteURLPolicy.redact(c.source.source_page), 'media_type': c.media_type.value, 'rank': rank}
                    for r in result.provider_results if r.page is not None for rank, c in enumerate(r.page.candidates)]
                ranked_assets = [(rank, asset) for rank, asset in enumerate(restored)]
                for origin in origins:
                    for asset in assets.values():
                        if (asset.media_type.value == origin['media_type'] and asset.source.provider == origin['provider']
                                and (origin['provider_asset_id'] and asset.source.provider_asset_id == origin['provider_asset_id']
                                     or origin['source_page'] and asset.source.source_page == origin['source_page'])):
                            ranked_assets.append((origin['rank'], asset))
                for rank, asset in ranked_assets:
                    row = {'need_id': requested_need.need_id,
                           'need_sha256': hashlib.sha256(requested_need.to_json().encode()).hexdigest(),
                           'asset_sha256': asset.file.sha256, 'source_id': source_id, 'rank': rank,
                           'queries': wire_queries, 'input_sha256': input_sha256,
                           'compiled_intent_sha256': hashlib.sha256(NeedCompiler.for_plan(plan, search_terms=search_terms).compile(requested_need,
                               creative_mode_terms=style_terms).to_json().encode()).hexdigest()}
                    entries = links['assets'].setdefault(asset.asset_id, [])
                    if row not in entries:
                        entries.append(row)
                store.write_recovery_record('candidate-links', links)
                return tuple(a for a in restored if a.asset_id not in assets)

            result = library_first.supply_need(
                need, scope=scope, creation_id=attempt["creation_id"],
                attempt_id=attempt["attempt_id"], provider_infos=() if getattr(need.modality_spec, 'kind', None) == 'voice' else infos,
                external_supply=source_supply, director_preferences=director_preferences,
                excluded_sha256=retained_hashes if additional else frozenset(),
                policy=policy,
            )
            library_by_id = {item.library_asset_id: item for item in result.reuse_candidates}
            for matched in result.library_matches:
                candidate = library_by_id[matched.library_asset_id]
                imported = self._import_library(candidate.record, catalog, store, scope)
                assets[imported.asset_id] = imported
            for asset in result.external_assets:
                duplicate = next((a for a in assets.values() if a.media_type is asset.media_type
                    and a.file.sha256 == asset.file.sha256 and (a.rights == asset.rights
                    or a.rights.status.value == 'KNOWN' and asset.rights.status.value == 'UNKNOWN')), None)
                if duplicate is not None:
                    links = store.read_recovery_record('candidate-links') or {'assets': {}}
                    merged = links['assets'].setdefault(duplicate.asset_id, [])
                    for row in links['assets'].get(asset.asset_id, []):
                        if row not in merged:
                            merged.append(row)
                    store.write_recovery_record('candidate-links', links)
                    duplicate_bytes.append(asset.asset_id)
                    continue
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
                "reused_queries": reused_queries, "reused_asset_ids": reused_assets,
                "duplicate_byte_asset_ids": duplicate_bytes,
                "source_switch_reason": 'prior_batch_rejected' if rejected_sources else 'library_first_gap',
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
        readiness, gaps = MaterialReadinessCalculator(store=store).calculate(plan, bundle)
        previous_ids = {a.asset_id for a in checkpoint.assets} if checkpoint is not None and gate else set()
        if (retain_sources and (readiness.status.value == 'NOT_READY' or additional_visual_need_ids)
                and not any(a.asset_id not in previous_ids for a in all_assets)
                and (any(r.status == 'FAILED' for r in provider_results) or any(row['failures'] for row in trace))):
            raise RuntimeError('素材来源请求未完成；已保存的成功来源与素材会复用，重试仅继续未完成来源')
        if checkpoint is not None and gate:
            if store.read_bundle() != checkpoint or any(
                    store.read_asset(asset.asset_id) != asset for asset in checkpoint.assets):
                raise ValueError("素材 checkpoint 在检索期间变化，拒绝覆盖，请先刷新核对")
        store.write_supply_run(run)
        store.write_bundle(bundle)
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
            "plan_revision": MaterialReadinessCalculator.plan_revision(plan),
            "bundle_revision": bundle.revision,
            "elapsed_seconds": round(monotonic() - started, 6),
            "required_covered": len([n for n in plan.needs if n.importance.value == 'required'
                                      and n.need_id not in readiness.blocking_needs]),
            "blocking_needs": list(readiness.blocking_needs),
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
