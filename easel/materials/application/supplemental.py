"""Explicit, bounded supplemental supply subset and merge operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from easel.materials.application.assembly import MaterialBundleAssembler
from easel.materials.domain import (
    MaterialAsset,
    MaterialBundle,
    MaterialGap,
    MaterialMatch,
    MaterialPlan,
    SupplyRun,
)


@dataclass(frozen=True)
class SupplySubset:
    plan_id: str
    need_ids: tuple[str, ...]
    gaps: tuple[MaterialGap, ...]


@dataclass(frozen=True)
class SupplementalMergeResult:
    bundle: MaterialBundle
    supply_run: SupplyRun


class SupplementalSupplyFoundation:
    """Prepare only an explicit blocking subset and merge one supplied result.

    This class deliberately has no Provider callback, retry loop, or recursive
    invocation. The caller executes a bounded supply operation separately and
    hands its result to :meth:`merge`.
    """

    def supply_subset(
        self,
        plan: MaterialPlan,
        gaps: tuple[MaterialGap, ...] | list[MaterialGap],
    ) -> SupplySubset:
        plan_ids = {need.need_id for need in plan.needs}
        selected: dict[str, MaterialGap] = {}
        for gap in gaps:
            if not gap.blocking:
                continue
            if gap.need_id not in plan_ids:
                raise ValueError(f"MaterialGap references Need outside plan: {gap.need_id}")
            selected.setdefault(gap.need_id, gap)
        ordered = tuple(selected[need.need_id] for need in plan.needs if need.need_id in selected)
        return SupplySubset(plan_id=plan.plan_id, need_ids=tuple(gap.need_id for gap in ordered), gaps=ordered)

    def merge(
        self,
        plan: MaterialPlan,
        base_bundle: MaterialBundle,
        base_run: SupplyRun,
        supplemental_bundle: MaterialBundle,
        supplemental_run: SupplyRun,
        subset: SupplySubset,
        *,
        merged_supply_run_id: str,
        merged_bundle_id: str,
    ) -> SupplementalMergeResult:
        if base_bundle.plan_id != plan.plan_id or supplemental_bundle.plan_id != plan.plan_id:
            raise ValueError("Both bundles must belong to the Plan")
        if base_run.plan_id != plan.plan_id or supplemental_run.plan_id != plan.plan_id:
            raise ValueError("Both SupplyRuns must belong to the Plan")
        if subset.plan_id != plan.plan_id:
            raise ValueError("SupplySubset must belong to the Plan")
        if base_bundle.supply_run_id != base_run.supply_run_id:
            raise ValueError("base Bundle and SupplyRun identity mismatch")
        if supplemental_bundle.supply_run_id != supplemental_run.supply_run_id:
            raise ValueError("supplemental Bundle and SupplyRun identity mismatch")
        subset_ids = set(subset.need_ids)
        if any(match.need_id not in subset_ids for match in supplemental_bundle.matches):
            raise ValueError("Supplemental results may target only the requested blocking Need subset")

        assets_by_id = {asset.asset_id: asset for asset in base_bundle.assets}
        content_identity = {
            (asset.media_type, asset.file.sha256): asset.asset_id
            for asset in base_bundle.assets
        }
        asset_aliases: dict[str, str] = {}
        for asset in supplemental_bundle.assets:
            existing = assets_by_id.get(asset.asset_id)
            if existing is not None and existing != asset:
                raise ValueError(f"Supplemental result conflicts with existing asset: {asset.asset_id}")
            identity = (asset.media_type, asset.file.sha256)
            canonical_id = content_identity.get(identity)
            if canonical_id is not None and canonical_id != asset.asset_id:
                asset_aliases[asset.asset_id] = canonical_id
                continue
            assets_by_id.setdefault(asset.asset_id, asset)
            content_identity.setdefault(identity, asset.asset_id)

        match_by_pair = {(match.need_id, match.asset_id): match for match in base_bundle.matches}
        for match in supplemental_bundle.matches:
            canonical_asset_id = asset_aliases.get(match.asset_id, match.asset_id)
            if canonical_asset_id != match.asset_id:
                match = match.model_copy(update={"asset_id": canonical_asset_id})
            # Existing match evidence and rank remain authoritative; supplemental
            # supply only adds a missing pair and cannot silently replace it.
            match_by_pair.setdefault((match.need_id, match.asset_id), match)

        run = self._merge_runs(base_run, supplemental_run, merged_supply_run_id, merged_bundle_id)
        bundle = MaterialBundleAssembler().assemble(
            plan,
            run,
            tuple(assets_by_id.values()),
            tuple(match_by_pair.values()),
            bundle_id=merged_bundle_id,
        )
        return SupplementalMergeResult(bundle=bundle, supply_run=run)

    @staticmethod
    def _merge_runs(
        base: SupplyRun,
        supplemental: SupplyRun,
        run_id: str,
        bundle_id: str,
    ) -> SupplyRun:
        if not run_id or not bundle_id:
            raise ValueError("merged IDs must be non-empty")
        results: dict[str, object] = {}
        for result in (*base.provider_results, *supplemental.provider_results):
            existing = results.get(result.source_id)
            if existing is None:
                results[result.source_id] = result
            elif existing != result:
                statuses = {existing.status, result.status}
                status = existing.status if len(statuses) == 1 else "PARTIAL"
                summaries = tuple(dict.fromkeys(
                    value for value in (existing.failure_summary, result.failure_summary) if value
                ))
                results[result.source_id] = existing.model_copy(update={
                    "status": status,
                    "candidates_found": existing.candidates_found + result.candidates_found,
                    "acquired_assets": existing.acquired_assets + result.acquired_assets,
                    "failure_summary": ";".join(summaries) or None,
                })
        started = min(base.started_at, supplemental.started_at)
        finished_values = [value for value in (base.finished_at, supplemental.finished_at) if value is not None]
        # Preserve an unfinished run as unfinished; injecting wall-clock time
        # here would make the merged evidence non-deterministic.
        finished = max(finished_values) if finished_values else None
        failures = tuple(dict.fromkeys((*base.failures, *supplemental.failures)))
        return SupplyRun(
            supply_run_id=run_id,
            plan_id=base.plan_id,
            started_at=started,
            finished_at=finished,
            provider_results=tuple(results[key] for key in sorted(results)),
            failures=failures,
            parent_run_id=base.supply_run_id,
            result_bundle_id=bundle_id,
        )
