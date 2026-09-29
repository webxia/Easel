"""Deterministic, inspectable routing across Library, Local, and Providers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from easel.materials.domain import MaterialNeed, MediaType, NeedScopeType
from easel.materials.providers.models import (
    AccessMode,
    ProviderCapability,
    ProviderHealth,
    ProviderHealthStatus,
    ProviderInfo,
)
from easel.materials.providers.models import ProviderContinuation
from easel.materials.domain.models import RetrievalIntent
from easel.materials.providers.registry import ProviderRegistry, ProviderSearchResult, RetryPolicy


class SourceKind(str, Enum):
    LIBRARY = "LIBRARY"
    LOCAL = "LOCAL"
    EXTERNAL = "EXTERNAL"
    GENERATIVE = "GENERATIVE"


class ProviderPerformance(BaseModel):
    """Caller-supplied outcome summary from prior bounded search attempts."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    provider_id: str = Field(min_length=1)
    success_count: int = Field(default=0, ge=0)
    failure_count: int = Field(default=0, ge=0)
    average_latency_ms: float | None = Field(default=None, ge=0)

    @property
    def sample_count(self) -> int:
        return self.success_count + self.failure_count

    @property
    def success_rate(self) -> float:
        return self.success_count / self.sample_count if self.sample_count else 0.5


class ProviderRoutingPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    include_local: bool = True
    include_external: bool = True
    include_generation: bool = True
    disabled_provider_ids: tuple[str, ...] = ()
    preferred_provider_order: tuple[str, ...] = ()
    max_external_providers: int | None = Field(default=None, ge=1)

    @field_validator("disabled_provider_ids", "preferred_provider_order")
    @classmethod
    def unique_provider_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not value.strip() for value in values) or len(values) != len(set(values)):
            raise ValueError("provider id lists must contain unique non-blank values")
        return values


class SourceRoute(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    source_id: str = Field(min_length=1)
    kind: SourceKind
    order: int = Field(ge=1)
    candidate_count: int = Field(default=0, ge=0)
    health: ProviderHealthStatus | None = None
    success_rate: float | None = Field(default=None, ge=0, le=1)
    average_latency_ms: float | None = Field(default=None, ge=0)
    reasons: tuple[str, ...] = ()


class RouteSkip(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    source_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class RoutingDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    media_type: MediaType
    required_capability: ProviderCapability
    routes: tuple[SourceRoute, ...]
    skipped: tuple[RouteSkip, ...] = ()
    rights_policy: str = "candidate discovery never bypasses downstream Rights Admission"


@dataclass(frozen=True)
class RoutedSearchResult:
    decision: RoutingDecision
    provider_results: tuple[ProviderSearchResult, ...]


class MaterialSourceRouter:
    """Order sources deterministically without making Rights or selection decisions."""

    def plan(
        self,
        media_type: MediaType,
        provider_infos: tuple[ProviderInfo, ...] | list[ProviderInfo],
        *,
        library_candidate_count: int = 0,
        provider_health: dict[str, ProviderHealth] | None = None,
        performance: dict[str, ProviderPerformance] | None = None,
        policy: ProviderRoutingPolicy | None = None,
        required_capability: ProviderCapability = ProviderCapability.SEARCH,
        need: MaterialNeed | None = None,
    ) -> RoutingDecision:
        if library_candidate_count < 0:
            raise ValueError("library_candidate_count must be non-negative")
        active_policy = policy or ProviderRoutingPolicy()
        health_by_id = provider_health or {}
        performance_by_id = performance or {}
        routes: list[SourceRoute] = []
        skipped: list[RouteSkip] = []
        if library_candidate_count:
            routes.append(SourceRoute(
                source_id="material-library",
                kind=SourceKind.LIBRARY,
                order=1,
                candidate_count=library_candidate_count,
                reasons=(
                    "scope-filtered Library candidates already satisfy current reuse eligibility",
                    "Library is preferred before external supply",
                    "Production Authoring retains final material selection",
                ),
            ))

        eligible: list[tuple[ProviderInfo, ProviderHealthStatus, ProviderPerformance | None]] = []
        seen: set[str] = set()
        for info in provider_infos:
            if info.provider_id in seen:
                skipped.append(RouteSkip(source_id=info.provider_id, reason="duplicate_provider_info"))
                continue
            seen.add(info.provider_id)
            if info.provider_id in active_policy.disabled_provider_ids:
                skipped.append(RouteSkip(source_id=info.provider_id, reason="disabled_by_policy"))
                continue
            if not info.supports(media_type, required_capability):
                skipped.append(RouteSkip(source_id=info.provider_id, reason="required_capability_or_media_type_unsupported"))
                continue
            kind = SourceKind.LOCAL if info.access_mode is AccessMode.LOCAL else SourceKind.EXTERNAL
            if kind is SourceKind.LOCAL and not active_policy.include_local:
                skipped.append(RouteSkip(source_id=info.provider_id, reason="local_sources_disabled"))
                continue
            if kind is SourceKind.EXTERNAL and not active_policy.include_external:
                skipped.append(RouteSkip(source_id=info.provider_id, reason="external_sources_disabled"))
                continue
            health_record = health_by_id.get(info.provider_id)
            status = health_record.status if health_record else ProviderHealthStatus.UNKNOWN
            if status is ProviderHealthStatus.UNAVAILABLE:
                skipped.append(RouteSkip(source_id=info.provider_id, reason="provider_unavailable"))
                continue
            eligible.append((info, status, performance_by_id.get(info.provider_id)))

        preferred_index = {provider_id: index for index, provider_id in enumerate(active_policy.preferred_provider_order)}
        status_order = {
            ProviderHealthStatus.HEALTHY: 0,
            ProviderHealthStatus.DEGRADED: 1,
            ProviderHealthStatus.UNKNOWN: 2,
            ProviderHealthStatus.UNAVAILABLE: 3,
        }
        eligible.sort(key=lambda item: (
            preferred_index.get(item[0].provider_id, len(preferred_index) + (0 if item[0].access_mode is AccessMode.LOCAL else 1)),
            status_order[item[1]],
            -(item[2].success_rate if item[2] else 0.5),
            item[2].failure_count if item[2] else 0,
            item[2].average_latency_ms if item[2] and item[2].average_latency_ms is not None else float("inf"),
            item[0].provider_id,
        ))
        external_count = 0
        for info, status, history in eligible:
            kind = SourceKind.LOCAL if info.access_mode is AccessMode.LOCAL else SourceKind.EXTERNAL
            if kind is SourceKind.EXTERNAL and active_policy.max_external_providers is not None:
                if external_count >= active_policy.max_external_providers:
                    skipped.append(RouteSkip(source_id=info.provider_id, reason="external_provider_limit_reached"))
                    continue
                external_count += 1
            reasons = [f"supports={required_capability.value}:{media_type.value}", f"availability={status.value}"]
            if history is None or history.sample_count == 0:
                reasons.append("historical_behavior=unobserved")
            else:
                reasons.append(
                    f"historical_behavior=success:{history.success_count},failure:{history.failure_count},"
                    f"success_rate:{history.success_rate:.3f}"
                )
                if history.average_latency_ms is not None:
                    reasons.append(f"average_latency_ms={history.average_latency_ms:.3f}")
            if status is ProviderHealthStatus.DEGRADED:
                reasons.append("degraded_provider_routed_after_healthy_candidates")
            reasons.append("rights_admission_required_after_candidate_acquisition")
            routes.append(SourceRoute(
                source_id=info.provider_id,
                kind=kind,
                order=len(routes) + 1,
                health=status,
                success_rate=history.success_rate if history and history.sample_count else None,
                average_latency_ms=history.average_latency_ms if history else None,
                reasons=tuple(reasons),
            ))
        if need is not None and active_policy.include_generation and self._generation_eligible(need):
            routes.append(SourceRoute(
                source_id="material-ai-generation",
                kind=SourceKind.GENERATIVE,
                order=len(routes) + 1,
                reasons=(
                    "Material AI generation is eligible for this Need under explicit source policy or continuity identity",
                    "runs only after qualified Library and eligible acquisition routes remain insufficient",
                    "generation requires a configured material provider and explicit execution gate",
                ),
            ))
        # Reassign orders after any filtering so the sequence is contiguous.
        routes = [route.model_copy(update={"order": position}) for position, route in enumerate(routes, start=1)]
        return RoutingDecision(
            media_type=media_type,
            required_capability=required_capability,
            routes=tuple(routes),
            skipped=tuple(skipped),
        )

    @staticmethod
    def _generation_eligible(need: MaterialNeed) -> bool:
        """Use Need policy/identity, not shortage alone, to expose generation."""
        is_voice = (
            need.media_type is MediaType.AUDIO
            and getattr(need.modality_spec, "kind", None) == "voice"
            and need.scope.type is NeedScopeType.GLOBAL
        )
        if need.media_type not in {MediaType.IMAGE, MediaType.VIDEO} and not is_voice:
            return False
        if need.constraints.get("allow_generation") is True:
            return True
        continuity_kinds = {ref.kind.casefold() for ref in need.continuity_refs}
        if need.media_type in {MediaType.IMAGE, MediaType.VIDEO} and continuity_kinds.intersection(
            {"character", "location", "world", "object"}
        ):
            return True
        identity = getattr(need.modality_spec, "identity", None)
        return is_voice and identity is not None

    def search_routed(
        self,
        registry: ProviderRegistry,
        intent: RetrievalIntent,
        decision: RoutingDecision,
        *,
        continuations: dict[str, ProviderContinuation] | None = None,
        retry_policy: RetryPolicy = RetryPolicy(),
        sleep: Callable[[float], None] | None = None,
    ) -> RoutedSearchResult:
        """Search only planned providers, one isolated registry boundary at a time."""
        expected_type = intent.filters.get("media_type")
        if expected_type != decision.media_type.value:
            raise ValueError("routing decision media_type does not match RetrievalIntent")
        results: list[ProviderSearchResult] = []
        for route in decision.routes:
            if route.kind is SourceKind.LIBRARY:
                continue
            isolated_registry = ProviderRegistry()
            isolated_registry.register(registry.get(route.source_id))
            arguments = {
                "continuations": ({route.source_id: continuations[route.source_id]} if continuations and route.source_id in continuations else None),
                "retry_policy": retry_policy,
            }
            if sleep is not None:
                arguments["sleep"] = sleep
            results.extend(isolated_registry.search_all(intent, **arguments))
        return RoutedSearchResult(decision=decision, provider_results=tuple(results))


__all__ = [
    "MaterialSourceRouter", "ProviderPerformance", "ProviderRoutingPolicy",
    "RouteSkip", "RoutedSearchResult", "RoutingDecision", "SourceKind", "SourceRoute",
]
