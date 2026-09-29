"""Deterministic MaterialBundle and SupplyRun assembly."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from easel.materials.domain import (
    Coverage,
    CoverageStatus,
    MaterialAsset,
    MaterialBundle,
    MaterialMatch,
    MaterialPlan,
    SupplyRun,
)


@dataclass(frozen=True)
class MaterialBundleAssembler:
    """Assemble supply facts without making an editorial or production choice."""

    def assemble(
        self,
        plan: MaterialPlan,
        supply_run: SupplyRun,
        assets: tuple[MaterialAsset, ...] | list[MaterialAsset],
        matches: tuple[MaterialMatch, ...] | list[MaterialMatch],
        *,
        bundle_id: str,
    ) -> MaterialBundle:
        if not bundle_id or not bundle_id.strip():
            raise ValueError("bundle_id must be non-empty")
        if supply_run.plan_id != plan.plan_id:
            raise ValueError("SupplyRun.plan_id must match MaterialPlan.plan_id")
        asset_ids = {asset.asset_id for asset in assets}
        if len(asset_ids) != len(assets):
            raise ValueError("assets must have unique asset_id values")
        plan_need_ids = {need.need_id for need in plan.needs}
        for match in matches:
            if match.need_id not in plan_need_ids:
                raise ValueError(f"MaterialMatch references Need outside plan: {match.need_id}")
            if match.asset_id not in asset_ids:
                raise ValueError(f"MaterialMatch references asset outside supply: {match.asset_id}")

        coverage = self._coverage(plan, matches)
        provisional = MaterialBundle(
            bundle_id=bundle_id,
            plan_id=plan.plan_id,
            supply_run_id=supply_run.supply_run_id,
            assets=tuple(sorted(assets, key=lambda item: item.asset_id)),
            matches=tuple(sorted(matches, key=lambda item: (item.need_id, item.rank, item.asset_id))),
            coverage=coverage,
        )
        revision = self.revision(provisional)
        return provisional.model_copy(update={"revision": revision})

    @staticmethod
    def _coverage(
        plan: MaterialPlan,
        matches: tuple[MaterialMatch, ...] | list[MaterialMatch],
    ) -> tuple[Coverage, ...]:
        qualified: dict[str, int] = {}
        for match in matches:
            if match.qualified:
                qualified[match.need_id] = qualified.get(match.need_id, 0) + 1
        result: list[Coverage] = []
        for need in plan.needs:
            count = qualified.get(need.need_id, 0)
            if count == 0:
                status = CoverageStatus.UNCOVERED
            elif count < need.desired_options:
                status = CoverageStatus.PARTIAL
            else:
                status = CoverageStatus.COVERED
            result.append(Coverage(need_id=need.need_id, status=status, qualified_assets=count))
        return tuple(result)

    @staticmethod
    def revision(bundle: MaterialBundle) -> str:
        """Hash supply facts without making revision self-referential."""
        payload = bundle.model_copy(update={"revision": None}).to_json().encode("utf-8")
        return hashlib.sha256(payload).hexdigest()
