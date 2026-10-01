"""Thin, provider-neutral orchestration for P0 standalone acceptance."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timezone

from easel.materials.application.acquisition import AcquisitionError, MaterialAcquirer
from easel.materials.application.assembly import MaterialBundleAssembler
from easel.materials.application.compiler import NeedCompiler
from easel.materials.application.dedup import MaterialDeduplicator
from easel.materials.application.inspector import TechnicalInspector
from easel.materials.application.intelligence import BasicMaterialIntelligence
from easel.materials.application.matching import MaterialMatcher
from easel.materials.application.prerank import CandidatePreRanker
from easel.materials.application.readiness import MaterialReadinessCalculator
from easel.materials.application.rights import RightsService
from easel.materials.domain import (
    MaterialAsset,
    MaterialBundle,
    MaterialGap,
    MaterialMatch,
    MaterialPlan,
    MaterialReadiness,
    RightsInfo,
    SupplyRun,
    SupplySourceResult,
)
from easel.materials.providers import ProviderRegistry, ProviderSearchResult
from easel.materials.providers.models import ProviderContinuation
from easel.materials.store import AttemptMaterialStore


@dataclass(frozen=True)
class StandaloneFlowResult:
    """Auditable output of one bounded standalone supply attempt."""

    plan: MaterialPlan
    supply_run: SupplyRun
    assets: tuple[MaterialAsset, ...]
    matches: tuple[MaterialMatch, ...]
    bundle: MaterialBundle
    readiness: MaterialReadiness
    gaps: tuple[MaterialGap, ...]
    provider_results: tuple[ProviderSearchResult, ...]


class StandaloneMaterialFlow:
    """Compose P0 services without adding a production or product-mainline path.

    The optional ``rights_facts`` callback is deliberately explicit: Provider
    identity never upgrades Rights. If it is omitted, acquired assets retain
    their candidate rights status and required Needs can remain blocked.
    """

    def __init__(
        self,
        registry: ProviderRegistry,
        store: AttemptMaterialStore,
        *,
        acquirer: MaterialAcquirer | None = None,
        compiler: NeedCompiler | None = None,
        preranker: CandidatePreRanker | None = None,
        inspector: TechnicalInspector | None = None,
        rights: RightsService | None = None,
        intelligence: BasicMaterialIntelligence | None = None,
        matcher: MaterialMatcher | None = None,
        deduplicator: MaterialDeduplicator | None = None,
        assembler: MaterialBundleAssembler | None = None,
        readiness: MaterialReadinessCalculator | None = None,
        rights_facts: Callable[[object, MaterialAsset], RightsInfo | None] | None = None,
    ):
        self.registry = registry
        self.store = store
        self.acquirer = acquirer or MaterialAcquirer(store)
        self.compiler = compiler or NeedCompiler()
        self.preranker = preranker or CandidatePreRanker()
        self.inspector = inspector or TechnicalInspector(store)
        self.rights = rights or RightsService(store)
        self.intelligence = intelligence or BasicMaterialIntelligence(store)
        self.matcher = matcher or MaterialMatcher()
        self.deduplicator = deduplicator or MaterialDeduplicator(store)
        self.assembler = assembler or MaterialBundleAssembler()
        self.readiness = readiness or MaterialReadinessCalculator(store=store)
        self.rights_facts = rights_facts

    def run(
        self,
        plan: MaterialPlan,
        *,
        supply_run_id: str,
        bundle_id: str,
        top_n: int = 3,
        creator_context_terms: Iterable[str] = (),
        creative_mode_terms: Iterable[str] = (),
        continuations: dict[str, ProviderContinuation] | None = None,
        persist_bundle: bool = True,
        excluded_sources: frozenset[tuple[str, str, str]] = frozenset(),
    ) -> StandaloneFlowResult:
        started_at = datetime.now(timezone.utc)
        selected_candidates: list[object] = []
        provider_results: list[ProviderSearchResult] = []
        stats: dict[str, dict[str, object]] = defaultdict(
            lambda: {"candidates": 0, "acquired": 0, "failed": []}
        )
        def candidate_identity(candidate):
            reference = candidate.source.provider_asset_id or candidate.source.source_page
            return (candidate.media_type.value, candidate.source.provider or 'unknown', reference) if reference else None

        for need in plan.needs:
            intent = self.compiler.compile(
                need,
                creator_context_terms=creator_context_terms,
                creative_mode_terms=creative_mode_terms,
            )
            results = self.registry.search_all(intent, continuations=continuations)
            provider_results.extend(results)
            for result in results:
                state = stats[result.provider_id]
                if result.failure is not None:
                    state["failed"].append(result.failure.category.value)
                    continue
                assert result.page is not None
                state["candidates"] = int(state["candidates"]) + len(result.page.candidates)
                fresh = tuple(c for c in result.page.candidates if candidate_identity(c) not in excluded_sources)
                ranked = self.preranker.select(fresh, intent, top_n=top_n)
                selected_candidates.extend(item.candidate for item in ranked.selected)

        assets: list[MaterialAsset] = []
        seen_sources = set(excluded_sources)
        for candidate in selected_candidates:
            provider = candidate.source.provider or "unknown"
            source_key = candidate_identity(candidate)
            if source_key is not None and source_key in seen_sources:
                continue
            if source_key is not None:
                seen_sources.add(source_key)
            try:
                acquired = self.acquirer.acquire(candidate)
                inspected = self.inspector.inspect_and_persist(acquired)
                if self.rights_facts is not None:
                    facts = self.rights_facts(candidate, inspected)
                    if facts is not None:
                        inspected = self.rights.record(inspected, facts)
                enriched = self.intelligence.enrich(inspected)
                assets.append(enriched)
                stats[provider]["acquired"] = int(stats[provider]["acquired"]) + 1
            except (AcquisitionError, OSError, ValueError) as exc:
                stats[provider]["failed"].append(type(exc).__name__)

        assets_tuple = tuple(assets)
        matches: list[MaterialMatch] = []
        for need in plan.needs:
            matching = self.matcher.match(need, assets_tuple)
            diversity = self.deduplicator.deduplicate_and_diversify(
                matching.matches,
                assets_tuple,
                top_k=top_n,
            )
            matches.extend(diversity.shortlist)

        now = datetime.now(timezone.utc)
        supply_results = tuple(
            SupplySourceResult(
                source_id=provider_id,
                status="FAILED" if state["failed"] and not state["acquired"] else "PARTIAL" if state["failed"] else "COMPLETE",
                candidates_found=int(state["candidates"]),
                acquired_assets=int(state["acquired"]),
                failure_summary=";".join(str(item) for item in state["failed"]) or None,
            )
            for provider_id, state in sorted(stats.items())
        )
        run = SupplyRun(
            supply_run_id=supply_run_id,
            plan_id=plan.plan_id,
            started_at=started_at,
            finished_at=now,
            provider_results=supply_results,
            failures=tuple(
                f"{provider_id}:{failure}"
                for provider_id, state in sorted(stats.items())
                for failure in state["failed"]
            ),
            result_bundle_id=bundle_id,
        )
        bundle = self.assembler.assemble(plan, run, assets_tuple, tuple(matches), bundle_id=bundle_id)
        self.store.write_supply_run(run)
        if persist_bundle:
            self.store.write_bundle(bundle)
        readiness, gaps = self.readiness.calculate(plan, bundle)
        return StandaloneFlowResult(
            plan=plan,
            supply_run=run,
            assets=assets_tuple,
            matches=tuple(matches),
            bundle=bundle,
            readiness=readiness,
            gaps=gaps,
            provider_results=tuple(provider_results),
        )
