"""MaterialReadiness gate and blocking MaterialGap calculation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Callable

from easel.materials.application.assembly import MaterialBundleAssembler
from easel.materials.application.matching import MaterialMatcher
from easel.materials.application.rights import RightsAdmissionStatus, RightsService
from easel.materials.domain import (
    MaterialAsset,
    MaterialBundle,
    MaterialGap,
    MaterialMatch,
    MaterialNeed,
    MaterialPlan,
    MaterialReadiness,
    ReadinessStatus,
    TechnicalStatus,
)
from easel.materials.store import AttemptMaterialStore, AttemptMaterialStoreError


@dataclass(frozen=True)
class MaterialReadinessCalculator:
    """Recompute readiness from the current Plan and Bundle every time."""

    store: AttemptMaterialStore | None = None
    rights: RightsService | None = None
    evidence_view: Callable[[MaterialNeed, MaterialAsset], MaterialAsset] | None = None

    def calculate(self, plan: MaterialPlan, bundle: MaterialBundle) -> tuple[MaterialReadiness, tuple[MaterialGap, ...]]:
        if bundle.plan_id != plan.plan_id:
            raise ValueError("MaterialBundle.plan_id must match MaterialPlan.plan_id")
        if bundle.revision != MaterialBundleAssembler.revision(bundle):
            raise ValueError("MaterialBundle revision is stale or missing")
        assets = {asset.asset_id: asset for asset in bundle.assets}
        matches_by_need: dict[str, list[MaterialMatch]] = {}
        for match in bundle.matches:
            matches_by_need.setdefault(match.need_id, []).append(match)

        required_ids = tuple(need.need_id for need in plan.needs if need.importance.value == "required")
        covered: list[str] = []
        gaps: list[MaterialGap] = []
        gap_reasons: dict[str, set[str]] = {}
        for need in plan.needs:
            if need.importance.value != "required":
                continue
            reasons: list[str] = []
            qualified = False
            for match in sorted(matches_by_need.get(need.need_id, []), key=lambda item: (item.rank, item.asset_id)):
                if not match.qualified:
                    reasons.append(f"{match.asset_id}:match_not_qualified")
                    continue
                asset = assets.get(match.asset_id)
                if asset is None:
                    reasons.append(f"{match.asset_id}:asset_missing")
                    continue
                if not self._accessible(asset):
                    reasons.append(f"{asset.asset_id}:asset_inaccessible")
                    continue
                if asset.technical.status is not TechnicalStatus.PASSED:
                    reasons.append(f"{asset.asset_id}:technical_inspection_not_passed")
                    continue
                if "hard_filter=passed" not in match.reasons:
                    reasons.append(f"{asset.asset_id}:hard_filter_not_confirmed")
                    continue
                rights_service = self.rights or RightsService()
                attribution = rights_service.attribution_condition_for(asset)
                admission = rights_service.evaluate(asset, need, attribution=attribution)
                if admission.status not in {
                    RightsAdmissionStatus.ADMITTED,
                    RightsAdmissionStatus.CONDITIONAL,
                }:
                    reasons.append(f"{asset.asset_id}:rights_{admission.status.value.lower()}:{admission.reason}")
                    continue
                # A persisted qualified flag is only a claim. Recheck the
                # current Need and Asset, including per-Need semantic evidence.
                evidence_asset = self.evidence_view(need, asset) if self.evidence_view is not None else asset
                verified = MaterialMatcher(self.rights).match(need, [evidence_asset])
                if not verified.matches:
                    reasons.append(f"{asset.asset_id}:match_evidence_invalid")
                    continue
                qualified = True
                break
            if qualified:
                covered.append(need.need_id)
            else:
                if not reasons:
                    reasons.append("no_qualified_match")
                gap_reasons[need.need_id] = {reason.split(":", 1)[-1] for reason in reasons}
                gaps.append(MaterialGap(
                    need_id=need.need_id,
                    reason="required_need_not_covered",
                    request=need.intent.description,
                    blocking=True,
                ))

        blocking_ids = tuple(gap.need_id for gap in gaps)
        status = ReadinessStatus.READY if not gaps else ReadinessStatus.NOT_READY
        reasons = tuple(sorted({reason for gap_id in blocking_ids for reason in gap_reasons.get(gap_id, {"required_need_not_covered"})}))
        readiness = MaterialReadiness(
            plan_id=plan.plan_id,
            bundle_id=bundle.bundle_id,
            status=status,
            required_needs=required_ids,
            covered_required_needs=tuple(covered),
            blocking_needs=blocking_ids,
            blocking_reasons=reasons,
            plan_revision=self.plan_revision(plan),
            bundle_revision=bundle.revision,
        )
        return readiness, tuple(gaps)

    def is_current(self, plan: MaterialPlan, bundle: MaterialBundle, readiness: MaterialReadiness) -> bool:
        return (
            readiness.plan_id == plan.plan_id
            and readiness.bundle_id == bundle.bundle_id
            and readiness.plan_revision == self.plan_revision(plan)
            and readiness.bundle_revision == bundle.revision
        )

    def _accessible(self, asset: MaterialAsset) -> bool:
        if self.store is None:
            return bool(asset.file.path)
        try:
            path = self.store.resolve_asset_locator(asset.file.path)
            digest = hashlib.sha256()
            size = 0
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
                    size += len(chunk)
            return digest.hexdigest() == asset.file.sha256 and size == asset.file.size
        except (AttemptMaterialStoreError, OSError):
            return False

    @staticmethod
    def plan_revision(plan: MaterialPlan) -> str:
        return hashlib.sha256(plan.to_json().encode("utf-8")).hexdigest()
