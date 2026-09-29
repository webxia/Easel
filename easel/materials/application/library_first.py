"""Library-first candidate sourcing with explicit, bounded fallback operations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from easel.materials.application.advanced_matching import (
    AdvancedMaterialMatch,
    AdvancedMaterialMatcher,
    DirectorPreference,
)
from easel.materials.application.library_reuse import LibraryReuseCandidate, LibraryReuseService
from easel.materials.application.matching import MaterialMatcher
from easel.materials.application.routing import (
    MaterialSourceRouter,
    ProviderPerformance,
    ProviderRoutingPolicy,
    RoutingDecision,
    SourceKind,
    SourceRoute,
)
from easel.materials.application.supplemental import (
    SupplementalMergeResult,
    SupplementalSupplyFoundation,
    SupplySubset,
)
from easel.materials.domain import MaterialAsset, MaterialMatch, MaterialNeed
from easel.materials.library import LibraryScope
from easel.materials.providers.models import ProviderCapability, ProviderHealth, ProviderInfo


@dataclass(frozen=True)
class ExternalSupplyFailure:
    source_id: str
    error: str


@dataclass(frozen=True)
class LibraryFirstNeedResult:
    reuse_candidates: tuple[LibraryReuseCandidate, ...]
    library_matches: tuple[AdvancedMaterialMatch, ...]
    external_assets: tuple[MaterialAsset, ...]
    external_matches: tuple[MaterialMatch, ...]
    routing: RoutingDecision
    attempted_sources: tuple[str, ...]
    failures: tuple[ExternalSupplyFailure, ...]
    requested_options: int
    generation_route: SourceRoute | None = None
    selection_authority: bool = False

    @property
    def qualified_option_count(self) -> int:
        return len(self.library_matches) + len(self.external_matches)


@dataclass
class SupplementalAttemptBudget:
    """Mutable per-attempt counter; callers persist its count with supply evidence."""

    max_attempts: int = 1
    attempts: int = 0

    def __post_init__(self) -> None:
        if self.max_attempts < 0 or self.attempts < 0 or self.attempts > self.max_attempts:
            raise ValueError("supplemental attempt budget is invalid")

    def consume(self) -> int:
        if self.attempts >= self.max_attempts:
            raise RuntimeError("supplemental supply attempt ceiling reached")
        self.attempts += 1
        return self.attempts


@dataclass
class LibraryFirstSupplyService:
    """Orchestrate candidate options while leaving final choice to Production."""

    reuse: LibraryReuseService
    advanced_matcher: AdvancedMaterialMatcher
    router: MaterialSourceRouter = field(default_factory=MaterialSourceRouter)
    matcher: MaterialMatcher = field(default_factory=MaterialMatcher)
    supplemental: SupplementalSupplyFoundation = field(default_factory=SupplementalSupplyFoundation)

    def supply_need(
        self,
        need: MaterialNeed,
        *,
        scope: LibraryScope,
        creation_id: str,
        attempt_id: str,
        provider_infos: tuple[ProviderInfo, ...] | list[ProviderInfo],
        external_supply: Callable[[str, MaterialNeed], tuple[MaterialAsset, ...] | list[MaterialAsset]],
        provider_health: dict[str, ProviderHealth] | None = None,
        performance: dict[str, ProviderPerformance] | None = None,
        policy: ProviderRoutingPolicy | None = None,
        director_preferences: tuple[DirectorPreference, ...] = (),
    ) -> LibraryFirstNeedResult:
        """Search Library first; invoke bounded local/external routes only if short."""
        library = self.reuse.find_candidates(
            need, scope=scope, creation_id=creation_id, attempt_id=attempt_id,
        )
        ranked_library = self.advanced_matcher.match(
            need, library.candidates, scope=scope, director_preferences=director_preferences,
        )
        matched_library = tuple(ranked_library.matches)
        routes = self.router.plan(
            need.media_type,
            provider_infos,
            library_candidate_count=len(matched_library),
            provider_health=provider_health,
            performance=performance,
            policy=policy,
            required_capability=ProviderCapability.DIRECT_DOWNLOAD,
            need=need,
        )
        assets: list[MaterialAsset] = []
        matches: list[MaterialMatch] = []
        attempted: list[str] = []
        failures: list[ExternalSupplyFailure] = []
        generation_route = next(
            (route for route in routes.routes if route.kind is SourceKind.GENERATIVE), None,
        )
        # Each source call is isolated. Stop once the requested candidate pool is
        # filled; this is fallback, not a recursive retry loop.
        for route in routes.routes:
            if len(matched_library) + len(matches) >= need.desired_options:
                break
            if route.kind is SourceKind.LIBRARY:
                continue
            if route.kind is SourceKind.GENERATIVE:
                # Generation is dispatched only after the first material pass
                # has persisted its Bundle/Gap. Material AI generation then
                # addresses the exact blocking Need through its own provider.
                continue
            attempted.append(route.source_id)
            try:
                supplied = tuple(external_supply(route.source_id, need))
                existing_ids = {candidate.asset.asset_id for candidate in library.candidates}
                existing_ids.update(asset.asset_id for asset in assets)
                unique_items: list[MaterialAsset] = []
                for asset in supplied:
                    if asset.asset_id in existing_ids:
                        continue
                    existing_ids.add(asset.asset_id)
                    unique_items.append(asset)
                unique = tuple(unique_items)
                candidate_result = self.matcher.match(need, unique)
                assets.extend(unique)
                matches.extend(candidate_result.matches)
            except Exception as exc:  # provider isolation boundary
                failures.append(ExternalSupplyFailure(route.source_id, f"{type(exc).__name__}: {exc}"))
        return LibraryFirstNeedResult(
            reuse_candidates=tuple(library.candidates),
            library_matches=matched_library,
            external_assets=tuple(assets),
            external_matches=tuple(matches),
            routing=routes,
            attempted_sources=tuple(attempted),
            failures=tuple(failures),
            requested_options=need.desired_options,
            generation_route=generation_route,
        )

    def supplemental_subset(self, plan, gaps) -> SupplySubset:
        """Request one explicit blocking subset; no implicit recursive supply."""
        return self.supplemental.supply_subset(plan, gaps)

    def merge_supplemental(self, *args, budget: SupplementalAttemptBudget, **kwargs) -> SupplementalMergeResult:
        """Merge one explicitly supplied result under the caller's attempt ceiling."""
        budget.consume()
        return self.supplemental.merge(*args, **kwargs)


__all__ = [
    "ExternalSupplyFailure",
    "LibraryFirstNeedResult",
    "LibraryFirstSupplyService",
    "SupplementalAttemptBudget",
]
