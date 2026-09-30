"""Bounded Creator-authorized source revision and supplemental supply."""

from __future__ import annotations

import fcntl
import hashlib
import json
from datetime import datetime, timezone

from easel.integrations.hypit.service import get_film_attempt, update_film_attempt
from easel.integrations.material_layer import (
    MaterialGateIntegration, MaterialIntegrationError, MaterialProductOrchestrator,
    PlanningIntegration, ProductionAuthoringIntegration,
)
from easel.integrations.material_supply import ProductMaterialSupply
from easel.materials.application.assembly import MaterialBundleAssembler
from easel.materials.application.compiler import NeedCompiler
from easel.materials.application.dedup import MaterialDeduplicator
from easel.materials.application.matching import MaterialMatcher
from easel.materials.application.readiness import MaterialReadinessCalculator
from easel.materials.domain import MaterialBundle, MaterialPlan, ReadinessStatus, SupplyRun
from easel.materials.store import AttemptMaterialStore
from easel.runtime_config import EaselRuntimeConfig


def recover_materials(attempt_id: str, *, request_id: str, expected_plan_revision: str,
                      expected_bundle_revision: str, allow_licensed_bgm: bool,
                      search_terms: dict[str, tuple[str, ...]]) -> dict:
    """Preserve content and acquired facts; never generate or submit production."""
    attempt = get_film_attempt(attempt_id)
    store = AttemptMaterialStore(attempt["workspace"]["path"])
    # The store validates the request locator before using it for a lock.
    store.read_recovery_record(request_id)
    lock_path = store.materials_root / "recovery.lock"
    if lock_path.is_symlink():
        raise MaterialIntegrationError("素材恢复锁路径无效")
    with lock_path.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        return _recover_locked(attempt_id, store, request_id, expected_plan_revision,
                               expected_bundle_revision, allow_licensed_bgm, search_terms)


def _recover_locked(attempt_id, store, request_id, expected_plan_revision,
                    expected_bundle_revision, allow_licensed_bgm, search_terms):
    attempt = get_film_attempt(attempt_id)
    fingerprint = hashlib.sha256(json.dumps({
        "attempt_id": attempt_id, "plan_revision": expected_plan_revision,
        "bundle_revision": expected_bundle_revision, "allow_licensed_bgm": allow_licensed_bgm,
        "search_terms": search_terms,
    }, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    record = store.read_recovery_record(request_id)
    planning = PlanningIntegration().load(attempt)
    if record:
        if record.get("fingerprint") != fingerprint:
            raise MaterialIntegrationError("相同素材恢复请求不能改变输入")
        if MaterialReadinessCalculator.plan_revision(planning["plan"]) not in {
                expected_plan_revision, record["target_plan_revision"]}:
            raise MaterialIntegrationError("素材方案已变化，请刷新后重新处理")
        if record["status"] == "COMPLETE":
            return {"attempt": attempt, "material_status": attempt["material_gate"]["status"],
                    "recovery": {"status": "COMPLETE", "reused": True}}
        if (attempt.get("execution_status") != "NOT_SUBMITTED"
                or attempt.get("cost", {}).get("approved")
                or attempt.get("production_authoring") or attempt.get("outputs")
                or attempt.get("authoring_status") in {"AUTHORING_RUNNING", "AUTHORING_READY", "PLAN_READY"}):
            raise MaterialIntegrationError("视频制作已开始，不能覆盖素材规划；请使用当前阶段恢复或成片修改")
        source_plan = MaterialPlan.model_validate_json(json.dumps(record["source_plan"]))
        source_bundle = MaterialBundle.model_validate_json(json.dumps(record["source_bundle"]))
    else:
        if (attempt.get("execution_status") != "NOT_SUBMITTED"
                or attempt.get("cost", {}).get("approved")
                or attempt.get("production_authoring") or attempt.get("outputs")
                or attempt.get("authoring_status") in {"AUTHORING_RUNNING", "AUTHORING_READY", "PLAN_READY"}):
            raise MaterialIntegrationError("视频制作已开始，不能覆盖素材规划；请使用当前阶段恢复或成片修改")
        source_plan = planning["plan"]
        source_bundle = store.read_bundle()
        gate = attempt.get("material_gate", {})
        if (gate.get("status") != "MATERIAL_NOT_READY"
                or MaterialReadinessCalculator.plan_revision(source_plan) != expected_plan_revision
                or source_bundle.revision != expected_bundle_revision
                or gate.get("plan_revision") != expected_plan_revision
                or gate.get("bundle_revision") != expected_bundle_revision
                or gate.get("bundle_id") != source_bundle.bundle_id):
            raise MaterialIntegrationError("素材状态已变化，请刷新；不会重新检索或改写旧状态")
        allowed = set(gate.get("blocking_needs", []))
        if set(search_terms) - allowed:
            raise MaterialIntegrationError("只能为当前未覆盖的素材需求补充检索提示")
        record = {"schema": "easel-material-recovery@1", "status": "PREPARED",
                  "fingerprint": fingerprint, "attempt_id": attempt_id,
                  "created_at": datetime.now(timezone.utc).isoformat(),
                  "source_plan": source_plan.model_dump(mode="json"),
                  "source_bundle": source_bundle.model_dump(mode="json"),
                  "script_sha256": planning["truth_ledger"]["script_sha256"],
                  "allow_licensed_bgm": allow_licensed_bgm, "search_terms": search_terms}
    if planning["truth_ledger"]["script_sha256"] != record["script_sha256"]:
        raise MaterialIntegrationError("脚本已变化，不能复用本次旁白与内容审阅")
    needs = []
    for need in source_plan.needs:
        if need.need_id in search_terms and getattr(need.modality_spec, "kind", None) == "voice":
            raise MaterialIntegrationError("素材恢复不会检索或重新生成已冻结的旁白")
        if (allow_licensed_bgm and getattr(need.modality_spec, "kind", None) == "bgm"
                and need.constraints.get("required_source_kind") == "stock"):
            constraints = dict(need.constraints)
            del constraints["required_source_kind"]
            constraints["allow_generation"] = False
            need = need.model_copy(update={"constraints": constraints})
        NeedCompiler(search_terms=search_terms).compile(need)
        needs.append(need)
    target_plan = source_plan.model_copy(update={"needs": tuple(needs)})
    record["target_plan_revision"] = MaterialReadinessCalculator.plan_revision(target_plan)
    for asset in source_bundle.assets:
        persisted = store.read_asset(asset.asset_id)
        path = store.resolve_asset_locator(asset.file.path)
        if (persisted != asset or path.stat().st_size != asset.file.size
                or hashlib.sha256(path.read_bytes()).hexdigest() != asset.file.sha256):
            raise MaterialIntegrationError("已保留素材的字节或证据变化，拒绝覆盖")
    store.write_recovery_record(request_id, record)
    if record["status"] == "PREPARED":
        planning = PlanningIntegration().persist(
            attempt, target_plan, treatment=planning["treatment"],
            script=planning["script"], scenes=planning["scenes"],
        )
        attempt = planning["attempt"]
        now = datetime.now(timezone.utc)
        run = SupplyRun(supply_run_id=f"recover-{request_id}", plan_id=target_plan.plan_id,
                        parent_run_id=source_bundle.supply_run_id, started_at=now, finished_at=now,
                        result_bundle_id=source_bundle.bundle_id)
        matches = []
        for need in target_plan.needs:
            ranked = MaterialMatcher().match(need, source_bundle.assets)
            matches.extend(MaterialDeduplicator(store).deduplicate_and_diversify(
                ranked.matches, source_bundle.assets, top_k=3).shortlist)
        bundle = MaterialBundleAssembler().assemble(
            target_plan, run, source_bundle.assets, tuple(matches), bundle_id=source_bundle.bundle_id)
        readiness, gaps = MaterialReadinessCalculator(store=store).calculate(target_plan, bundle)
        attempt = MaterialGateIntegration().record(attempt, target_plan, bundle, run, readiness, gaps)["attempt"]
        record["status"] = "CHECKPOINT_READY"
        store.write_recovery_record(request_id, record)
    # A valid old generation is retained only for an exactly unchanged Need.
    retained = {asset.asset_id: asset for asset in source_bundle.assets}
    skip_voice = tuple(need.need_id for need in source_plan.needs
        if getattr(need.modality_spec, "kind", None) == "voice"
        and any(item.get("status") == "COMPLETE" and item.get("asset_id") in retained
                and item.get("schema") == "easel-material-generation@1"
                and item.get("attempt_id") == attempt_id
                and item.get("plan_id") == source_plan.plan_id
                and item.get("asset_sha256") == retained[item["asset_id"]].file.sha256
                and item.get("asset_path") == retained[item["asset_id"]].file.path
                and item.get("asset_bytes") == retained[item["asset_id"]].file.size
                and item.get("need_id") == need.need_id
                and item.get("plan_revision") == expected_plan_revision
                and item.get("input_sha256") == getattr(need.modality_spec, "text_sha256", None)
                for item in store.list_generation_records()))
    # Reconcile a completed Supply checkpoint before contacting Providers again.
    final_bundle = store.read_bundle()
    final_run_id = f"supplement-{request_id}"
    if final_bundle.supply_run_id == final_run_id:
        final_run = store.read_supply_run(final_run_id)
        if (final_run.plan_id != target_plan.plan_id or not final_run.finished_at
                or final_run.result_bundle_id != final_bundle.bundle_id):
            raise MaterialIntegrationError("素材补充提交结果不一致，不能重复检索")
        for asset in final_bundle.assets:
            path = store.resolve_asset_locator(asset.file.path)
            if (store.read_asset(asset.asset_id) != asset or path.stat().st_size != asset.file.size
                    or hashlib.sha256(path.read_bytes()).hexdigest() != asset.file.sha256):
                raise MaterialIntegrationError("素材补充结果证据变化，请刷新核对")
        readiness, gaps = MaterialReadinessCalculator(store=store).calculate(target_plan, final_bundle)
    else:
        roots = EaselRuntimeConfig.load().material_roots()
        supplied = ProductMaterialSupply(rights_facts=lambda candidate, asset:
            MaterialProductOrchestrator._local_rights_facts(candidate, asset, roots)).run(
                target_plan, attempt, local_roots=roots, supply_run_id=final_run_id,
                bundle_id=source_bundle.bundle_id, search_terms=search_terms, skip_need_ids=skip_voice)
        final_bundle, final_run, readiness, gaps = (
            supplied.bundle, supplied.supply_run, supplied.readiness, supplied.gaps)
    gate = MaterialGateIntegration().record(attempt, target_plan, final_bundle, final_run, readiness, gaps)
    attempt = gate["attempt"]
    record["status"] = "COMPLETE"
    record["result_bundle_revision"] = final_bundle.revision
    store.write_recovery_record(request_id, record)
    attempt = update_film_attempt(attempt_id, event="material_recovery_completed",
        material_recovery={"request_id": request_id, "status": "COMPLETE",
                           "source_plan_revision": expected_plan_revision,
                           "plan_revision": record["target_plan_revision"]})
    if readiness.status is ReadinessStatus.READY:
        attempt = ProductionAuthoringIntegration().prepare(attempt, selected_asset_ids=())["attempt"]
    return {"attempt": attempt, "material_status": gate["status"],
            "recovery": {"status": "COMPLETE", "reused": False}}
