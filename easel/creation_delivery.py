"""Durable execution ownership for the existing Creation production chain.

This is a dispatcher, not another workflow: the next operation is derived from
Preparation/Attempt checkpoints. Only explicitly enrolled commissions run.
"""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import logging
import os
import subprocess
from datetime import datetime
from time import monotonic
from typing import Any, Awaitable, Callable

from easel import creation
from easel.integrations.hypit.secrets import SecretRedactor
from easel.integrations.hypit.service import pricing_has_no_provider_charge

SCHEMA = "easel-creation-delivery@1"
MAX_FAILURES = 3
MAX_BUILD_RECOVERIES = 2
MAX_QUALITY_REPAIRS = 2
active_operation: ContextVar[str | None] = ContextVar("active_delivery_operation", default=None)
active_delivery: ContextVar[str | None] = ContextVar("active_creation_delivery", default=None)


class DeliveryExecutionUncertain(RuntimeError):
    """Caller lost execution observation; this does not prove remote work ended."""


class DeliveryBudgetExhausted(RuntimeError):
    """No new work; durable results and uncertain-run reconciliation remain valid."""


class DeliveryReportError(ValueError):
    """A known terminal report fault, distinct from unknown remote execution."""

    def __init__(self, message: str, *, failure_kind: str):
        super().__init__(message)
        self.failure_kind = failure_kind


def delivery_call_stage(operation: str | None) -> str:
    if operation in {"observe_material", "recover_material", "generate_material", "review_material"}:
        return "material"
    if operation in {"author"}:
        return "author"
    if operation in {"quality"}:
        return "quality"
    return "prepare"


def reserve_delivery_call(work: dict, *, category: str, frame_count: int = 1,
                          stage_override: str | None = None, need_count: int | None = None, source_count: int = 1) -> tuple[str, int]:
    """Use the existing commission record, shared by all nested calls/forks.

    Called inside edit_creation before dispatch. Attempts and explicit Retry do
    not reset this ledger. Polling/reusing a persisted call never reaches it.
    """
    stage = stage_override or delivery_call_stage(active_operation.get() or work["delivery"].get("operation"))
    record = work["delivery"]
    attempt = _attempt(work)
    needs = max(1, len(attempt.get("material_gate", {}).get("required_need_ids", [])))
    if stage == "material" and attempt.get("workspace", {}).get("path"):
        from pathlib import Path
        import json
        plan_path = Path(attempt["workspace"]["path"]) / "materials/plan.json"
        if plan_path.is_file():
            needs = max(1, len(json.loads(plan_path.read_text())["needs"]))
    needs = max(needs, need_count or 1)
    limits = {"prepare": MAX_FAILURES * 8,
              "material": needs * (MAX_FAILURES * 9 * 2 * 3 + max(1, source_count) * 2 * 3) + 4,
              "author": MAX_FAILURES * 4 * (1 + MAX_QUALITY_REPAIRS),
              "quality": 2 * 3 * max(1, frame_count) * (1 + MAX_QUALITY_REPAIRS)}
    budgets = record.setdefault("call_budgets", {})
    budget = budgets.setdefault(stage, {"used": 0, "limit": limits[stage], "categories": {}})
    if budget["used"] >= budget["limit"]:
        raise DeliveryBudgetExhausted(f"{stage} 阶段累计调用额度已耗尽；保留成果，停止派发新工作")
    budget["used"] += 1
    budget["categories"][category] = budget["categories"].get(category, 0) + 1
    return stage, budget["used"]


class DeliveryObservationPending(RuntimeError):
    """Continue observing a known remote operation without consuming retries."""

    def __init__(self, message: str, *, disconnected: bool):
        super().__init__(message)
        self.disconnected = disconnected


def is_managed(work: dict[str, Any]) -> bool:
    return (work.get("delivery") or {}).get("schema") == SCHEMA


def set_material_endpoint(creation_id: str) -> dict:
    """Persist a narrow owner endpoint before resuming the formal material path."""
    with execution_lock(creation_id) as acquired:
        if not acquired:
            raise creation.CreationError('当前步骤仍在执行，不能更换验收终点')
        with creation.edit_creation(creation_id) as work:
            attempt = _attempt(work)
            if (not is_managed(work) and work.get('route') == 'hypit_video'
                    and work.get('origin', {}).get('type') == 'chat'
                    and not work.get('chat_workflow', {}).get('confirmed_at')
                    and not work.get('hypit_attempts')):
                work.setdefault('chat_workflow', {})['delivery_endpoint'] = 'MATERIAL_READY'
                work['chat_workflow']['endpoint_set_at'] = creation._now()
                return work
            if (not is_managed(work) or work.get('selected_output_name')
                    or attempt.get('execution_status') not in {None, 'NOT_SUBMITTED', 'BLOCKED'}
                    or attempt.get('authoring_status') not in {None, 'PENDING', 'READY_FOR_EXTERNAL_AUTHORING'}
                    or attempt.get('production_authoring', {}).get('selected_asset_ids')
                    or attempt.get('cost', {}).get('approved')
                    or work['delivery'].get('recovering_quality_from')
                    or any(c.get('status') in {'pending', 'submitting'} for c in work['delivery'].get('agent_calls', {}).values())):
                raise creation.CreationError('素材验收终点必须在制作或未知执行开始前设定')
            work['delivery']['endpoint'] = 'MATERIAL_READY'
            work['delivery']['endpoint_set_at'] = creation._now()
    return creation.get_creation(creation_id)


def _save_material_endpoint(work):
    record = work['delivery']
    gate = _attempt(work)['material_gate']
    prior = record.get('material_endpoint_result', {})
    if prior.get('gate') == gate:
        return
    finished = creation._now()
    started = record.get('material_started_at')
    record['material_endpoint_result'] = {
        'attempt_id': _attempt(work)['attempt_id'], 'gate': dict(gate),
        'completed_at': finished, 'film_delivery_complete': False,
        'elapsed_wall_seconds': (datetime.fromisoformat(finished) - datetime.fromisoformat(started)).total_seconds() if started else None,
        'actual_provider_charge': 'unknown',
    }


@contextmanager
def measure_delivery_phase(phase: str, attempt_id: str = "preparation"):
    """Time only a few internal calls hidden inside the prepare operation.

    Counts invocations (including durable checkpoint reads), not model submits.
    These intervals nest inside operation_timings; never sum both as wall time.
    """
    creation_id = active_delivery.get()
    if not creation_id or not is_managed(creation.get_creation(creation_id)):
        yield
        return
    if phase not in {"preparation", "planning", "structure_repair", "truth", "truth_repair"}:
        raise ValueError("未知制作计时阶段")
    key = f"{attempt_id}:{phase}"
    started_at, started = creation._now(), monotonic()
    with creation.edit_creation(creation_id) as current:
        timing = current["delivery"].setdefault("phase_timings", {}).setdefault(key, {
            "calls": 0, "elapsed_seconds": 0.0, "first_started_at": started_at,
        })
        timing.update(calls=timing["calls"] + 1, last_started_at=started_at, last_outcome="running")
    outcome = "completed"
    try:
        yield
    except DeliveryObservationPending:
        outcome = "pending"
        raise
    except (DeliveryExecutionUncertain, subprocess.TimeoutExpired):
        outcome = "uncertain"
        raise
    except asyncio.CancelledError:
        outcome = "cancelled"
        raise
    except Exception:
        outcome = "failed"
        raise
    finally:
        elapsed = max(0.0, monotonic() - started)
        with creation.edit_creation(creation_id) as current:
            timing = current["delivery"]["phase_timings"][key]
            timing.update(elapsed_seconds=round(timing["elapsed_seconds"] + elapsed, 6),
                          last_elapsed_seconds=round(elapsed, 6), last_outcome=outcome,
                          last_finished_at=creation._now())


def enrolled_creation_ids() -> list[str]:
    # Do not use the UI's capped newest-200 listing: older pending commissions
    # must survive arbitrarily many later proposals. Reads do not enroll work.
    result = []
    if creation.CREATIONS_DIR.is_dir():
        for path in creation.CREATIONS_DIR.glob("cr_*/creation.json"):
            try:
                if is_managed(creation.get_creation(path.parent.name)):
                    result.append(path.parent.name)
            except (creation.CreationError, OSError):
                continue
    return result


@contextmanager
def execution_lock(creation_id: str):
    """Nonblocking OS lock; never steal a live owner because of a timeout/PID."""
    path = creation._creation_dir(creation_id) / "delivery.lock"
    with path.open("a+b") as lock:
        acquired = False
        try:
            if os.name == "nt":
                import msvcrt
                if lock.tell() == 0:
                    lock.write(b"0")
                    lock.flush()
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except (BlockingIOError, OSError):
            pass
        try:
            yield acquired
        finally:
            if acquired:
                if os.name == "nt":
                    lock.seek(0)
                    msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _attempt(work: dict[str, Any]) -> dict[str, Any]:
    attempts = work.get("hypit_attempts") or []
    return attempts[-1] if attempts else {}


def next_operation(work: dict[str, Any]) -> tuple[str | None, str]:
    """Return an existing operation or an evidenced waiting condition."""
    if not is_managed(work):
        return None, "unmanaged"
    delivery = work["delivery"]
    # Observe an existing executor and retire its runtime independently of
    # commission validity/stopping. Stopping new work cannot strand a live or
    # uncertain run, nor authorize abort before its terminal state is known.
    if any(call.get("status") in {"pending", "submitting"}
           or call.get("runtime_release") == "pending"
           for call in delivery.get("agent_calls", {}).values()):
        return "observe_agent", "observing_execution"
    workflow = work.get("chat_workflow") or {}
    if workflow.get("editing_proposal"):
        return None, "revising_proposal"
    proposal = delivery.get("proposal")
    if (workflow.get("proposal_status") != "CONFIRMED" or not isinstance(proposal, str)
            or hashlib.sha256(proposal.encode()).hexdigest() != workflow.get("proposal_sha256")
            or delivery.get("proposal_sha256") != workflow.get("proposal_sha256")):
        return None, "commission_invalid"
    if delivery.get("stopped"):
        return None, "stopped"
    if work.get("selected_output_name"):
        return None, "accepted"
    if delivery.get("recovering_build_from"):
        return "retry_build", "recovering_production"
    if delivery.get("recovering_quality_from"):
        return "repair_quality", "repairing_quality"
    attempt = _attempt(work)
    if not attempt:
        return "prepare", "preparing"
    execution = attempt.get("execution_status")
    # A persisted intent to submit is never a license to submit again.
    if execution in {"SUBMITTING", "SUBMISSION_UNCERTAIN"}:
        return "reconcile", "reconciling"
    if execution in {"SUBMITTED", "RUNNING", "CANCEL_REQUESTED"}:
        return "refresh", "producing"
    if execution == "BUILD_COMPLETE":
        from easel.integrations.hypit.quality import SCHEMA as QUALITY_SCHEMA, needs_reobservation
        if not attempt.get("outputs"):
            return "export", "exporting"
        system = attempt.get("review", {}).get("system", {})
        binding = system.get("binding", {})
        output = attempt["outputs"].get(binding.get("output_name"), {})
        if (system.get("schema") == QUALITY_SCHEMA and output
                and output.get("sha256") == binding.get("sha256")):
            if system.get("status") == "READY":
                return None, "first_cut_ready"
            if needs_reobservation(system):
                return 'quality', 'checking_quality'
            if system.get("status") == "REPAIR_REQUIRED":
                from easel.integrations.hypit.quality import repair_request
                if (len(delivery.get('quality_repairs', [])) < MAX_QUALITY_REPAIRS
                        and repair_request(attempt) is not None):
                    return 'repair_quality', 'repairing_quality'
                return None, "quality_repair_required"
            if system.get("status") == "INCOMPLETE":
                return None, "quality_incomplete"
        return "quality", "checking_quality"
    if execution == "BUILD_FAILED":
        if len(delivery.get("build_recoveries", [])) < MAX_BUILD_RECOVERIES:
            return "retry_build", "recovering_production"
        return None, "production_failed"
    if execution == "CANCELLED":
        return None, "stopped"
    from easel.integrations.material_layer import MaterialProductOrchestrator
    if MaterialProductOrchestrator.pending_combination_request(attempt):
        return 'finish_material_review', 'reviewing_material'
    planning_repair = attempt.get('planning_repair', {})
    if planning_repair and planning_repair.get('status') != 'COMPLETE':
        if (planning_repair.get('status') == 'TRUTH_REQUIRED'
                and attempt.get('material_planning', {}).get('truth_review_status') != 'PASSED'):
            return None, 'needs_evidence'
        return 'repair_planning', 'repairing_quality'
    gate = attempt.get("material_gate") or {}
    if (gate.get('status') == 'MATERIAL_NOT_READY' and gate.get('bundle_revision')
            and attempt.get('workspace', {}).get('path')):
        from easel.materials.store import AttemptMaterialStore
        from easel.materials.application.generation_modalities import recoverable_generation_records
        try:
            store = AttemptMaterialStore(attempt['workspace']['path'])
            pending = recoverable_generation_records(store.read_plan(), store.read_bundle(), store,
                                                     gate_revision=gate.get('bundle_revision'))
        except (ValueError, OSError):
            # Execute under the normal bounded retry/error reporting path.
            # A projection read error must not silently kill the dispatcher.
            pending = True
        if pending:
            return 'finish_material_generation', 'recovering_material'
    if gate.get('bundle_revision') and attempt.get('workspace', {}).get('path'):
        from easel.materials.application.voice_delivery import pending_voice_timing_recovery
        from easel.integrations.material_layer import PlanningIntegration
        from easel.materials.store import AttemptMaterialStore
        try:
            store = AttemptMaterialStore(attempt['workspace']['path'])
            pending = False
            if any(r.get('modality') == 'voice' and r.get('status') == 'COMPLETE'
                   for r in store.list_generation_records()):
                planning = PlanningIntegration().load(attempt)
                pending = pending_voice_timing_recovery(planning['plan'], store.read_bundle(), store, planning['script'],
                                                        require_content=True)
        except (ValueError, OSError):
            pending = True
        if pending:
            from easel.materials.application.voice_delivery import voice_verification_identity, voice_recovery_identity
            try:
                need = next(n for n in planning['plan'].needs if n.need_id == pending[0]['need_id'])
                record = pending[0]
                binding = {'audio_sha256': record['asset_sha256'],
                           'script_sha256': hashlib.sha256(planning['script'].encode()).hexdigest(),
                           'need_sha256': hashlib.sha256(need.to_json().encode()).hexdigest()}
                failure_key = 'voice-failure-' + voice_recovery_identity(binding, voice_verification_identity(None))
                if store.read_recovery_record(failure_key):
                    return None, 'needs_audio_verification'
            except (ValueError, OSError, TypeError):
                pass  # Diagnose an invalid projection through the existing Owner.
            return 'recover_voice_timing', 'recovering_material'
    accepted = attempt.get('material_combination_review', {})
    if accepted.get('status') == 'COMPLETE':
        from easel.integrations.material_layer import ProductionAuthoringIntegration
        from easel.materials.store import AttemptMaterialStore
        try:
            store = AttemptMaterialStore(attempt['workspace']['path'])
            ProductionAuthoringIntegration.accepted_combination(attempt, store.read_plan(), store.read_bundle(), store)
        except (ValueError, OSError):
            return None, 'needs_evidence'
        # The accepted combination is a human creative choice. Preserve it;
        # admission and narration timing are still independently checked.
    if accepted.get('status') != 'COMPLETE' and attempt.get('autonomous_material_recovery', {}).get('status') in {'PLANNING', 'SUPPLYING'}:
        return 'recover_material', 'recovering_material'
    if gate.get("bundle_revision") and gate.get("status") in {"MATERIAL_READY", "MATERIAL_NOT_READY"}:
        observed = attempt.get("material_observation") or {}
        if observed.get('status') == 'COMPLETE' and accepted.get('status') != 'COMPLETE':
            from easel.materials.application.visual_observation import pending_visual_reassessment, pending_generated_visual_intake
            try:
                reassessment = pending_visual_reassessment(attempt)
                if (not reassessment and gate.get('status') == 'MATERIAL_NOT_READY'
                        and any(r.get('status') == 'complete' and r.get('need_id') in gate.get('blocking_needs', [])
                                for r in delivery.get('material_generations', {}).values())):
                    reassessment = pending_generated_visual_intake(attempt)
            except (ValueError, OSError):
                reassessment = True
            audio_recovery = attempt.get('autonomous_material_recovery', {}).get('compiled_audio_fallback_need_ids', [])
            if (not reassessment and gate.get('status') == 'MATERIAL_NOT_READY'
                    and set(audio_recovery) & set(gate.get('blocking_needs', []))):
                from easel.integrations.material_layer import MaterialProductOrchestrator
                reassessment = bool(MaterialProductOrchestrator.pending_openverse_rights_refresh(attempt))
            if reassessment:
                return 'observe_material', 'observing_material'
        revision = attempt.get('revision_feedback', {})
        visual_repair = (revision.get('origin') == 'system_quality'
                         and 'visual_material' in revision.get('allowed_changes', []))
        if (accepted.get('status') != 'COMPLETE' or visual_repair) and (observed.get("status") != "COMPLETE"
                or observed.get("bundle_revision") != gate.get("bundle_revision")
                or observed.get("plan_revision") != gate.get("plan_revision")
                or (visual_repair and observed.get('quality_report_sha256') != revision.get('quality_report_sha256'))):
            return "observe_material", "observing_material"
        if any(progress.get('stop_reason') == 'batch_complete' and progress.get('next_candidates')
               for progress in observed.get('candidate_progress', {}).values()):
            return 'observe_material', 'observing_material'
        if visual_repair and not attempt.get('autonomous_material_recovery'):
            from easel.integrations.hypit.service import quality_visual_replacement_gaps
            try:
                missing = quality_visual_replacement_gaps(attempt)
            except (ValueError, OSError):
                missing = True  # Diagnose under the ordinary bounded operation retry.
            if missing:
                return 'recover_material', 'recovering_material'
    if gate.get("status") != "MATERIAL_READY":
        prep_status = (work.get("preparation") or {}).get("status")
        if (prep_status == "SCRIPT_TRUTH_REVIEW_REQUIRED"
                and attempt.get("material_planning", {}).get("truth_review_status") == "PASSED"):
            return "prepare", "preparing"
        if (gate.get('status') == 'MATERIAL_NOT_READY' and gate.get('plan_revision') and gate.get('bundle_revision')
                and attempt.get('material_planning', {}).get('truth_review_status') == 'PASSED'
                and not attempt.get('autonomous_material_recovery')):
            if delivery.get('authorization', {}).get('material_generation'):
                from easel.integrations.material_generation import pending_generated_need
                from easel.materials.store import AttemptMaterialStore
                try:
                    plan = AttemptMaterialStore(attempt['workspace']['path']).read_plan()
                    choice = pending_generated_need(work, attempt, plan)
                    if not choice:
                        from easel.integrations.material_generation import image_fallback_decision
                        if any((decision := image_fallback_decision(work, attempt, plan, n)).get('reserved_calls') and not decision['eligible']
                               for n in plan.needs if n.media_type.value == 'image' and n.need_id in gate.get('blocking_needs', [])):
                            return None, 'material_supply_exhausted'
                except (ValueError, OSError):
                    choice = None
                if choice and choice[0].media_type.value == 'image':
                    return 'generate_material', 'generating_material'
            return 'recover_material', 'recovering_material'
        if (gate.get('status') == 'MATERIAL_NOT_READY' and attempt.get('workspace', {}).get('path')
                and attempt.get('material_planning', {}).get('truth_review_status') == 'PASSED'
                and delivery.get('authorization', {}).get('material_generation')):
            from easel.integrations.material_generation import pending_generated_need
            from easel.materials.store import AttemptMaterialStore
            try:
                plan = AttemptMaterialStore(attempt['workspace']['path']).read_plan()
                pending = pending_generated_need(work, attempt, plan)
            except (ValueError, OSError):
                # Resolve/read failures belong to the owner's bounded operation
                # retry, not an uncaught projection failure in the dispatcher.
                pending = True
            if pending:
                return 'generate_material', 'generating_material'
            statuses = {r.get('status') for r in delivery.get('material_generations', {}).values()
                        if r.get('attempt_id') == attempt.get('attempt_id')}
            if 'uncertain' in statuses:
                return None, 'material_submission_uncertain'
            if statuses & {'quote_unavailable', 'budget_exceeded'}:
                return None, 'needs_generation_approval'
        if gate.get('status') == 'MATERIAL_NOT_READY' and attempt.get('autonomous_material_recovery'):
            from easel.integrations.material_recovery import visual_supply_recovery_state
            try:
                recovery_state = visual_supply_recovery_state(attempt)
            except (ValueError, OSError):
                return 'recover_material', 'recovering_material'
            if recovery_state == 'available':
                return 'recover_material', 'recovering_material'
            if recovery_state == 'exhausted':
                return None, 'material_supply_exhausted'
        if (gate.get('status') == 'MATERIAL_NOT_READY'
                or prep_status in {"SCRIPT_TRUTH_REVIEW_REQUIRED", "MATERIAL_NOT_READY"}):
            return None, "needs_evidence"
        return "prepare", "preparing"
    if delivery.get('endpoint') == 'MATERIAL_READY' and attempt.get('material_gate', {}).get('status') == 'MATERIAL_READY':
        from easel.integrations.material_layer import MaterialGateIntegration
        try:
            MaterialGateIntegration().assert_ready(attempt)
        except (ValueError, OSError):
            return None, 'needs_evidence'
        return None, 'material_ready'
    authoring = attempt.get("authoring_status")
    if authoring in {"PENDING", "READY_FOR_EXTERNAL_AUTHORING", "AUTHORING_RUNNING", "AUTHORING_FAILED"}:
        return "author", "authoring"
    if any(stage.get("attempt_id") == attempt.get("attempt_id")
           for stage in delivery.get("authoring_stages", {}).values()):
        return "release_authoring", "preparing_production"
    if attempt.get("runtime_status") != "CONFIGURED":
        return "runtime", "preparing_production"
    if (attempt.get("plan") or {}).get("status") != "ready":
        return "validate", "preparing_production"
    cost = attempt.get("cost") or {}
    if cost.get("status") != "pricing_read":
        return "price", "checking_cost"
    if cost.get("approved"):
        return "submit", "submitting"
    if (delivery.get("authorization", {}).get("no_provider_charge_build") is True
            and pricing_has_no_provider_charge(cost.get("pricing"))):
        return "approve_free", "checking_cost"
    return None, "needs_cost_approval"


def retry_delivery(creation_id: str) -> dict[str, Any]:
    """Retry only the exhausted operation; approvals/checkpoints stay untouched."""
    with creation.edit_creation(creation_id) as work:
        if not is_managed(work):
            raise creation.CreationError("该作品未委托后端持续交付")
        record = work["delivery"]
        failure_key = record.get("exhausted_operation")
        if record.get("status") == "execution_uncertain":
            raise creation.CreationError("上一次执行结果尚未核实，不能重复派发")
        if failure_key:
            record.setdefault("failures", {}).pop(failure_key, None)
            attempt_id = _attempt(work).get("attempt_id")
            if (failure_key == f"{attempt_id}:prepare"
                    and record.get("script_repairs", {}).pop(attempt_id, None)):
                rounds = record.setdefault("script_repair_rounds", {})
                rounds[attempt_id] = rounds.get(attempt_id, 0) + 1
            record.update(status="pending", operation=None, exhausted_operation=None, last_error=None)
    return creation.get_creation(creation_id)


async def advance_creation(
    creation_id: str,
    execute: Callable[[str, dict[str, Any]], Awaitable[None]],
) -> bool:
    """Run one checkpoint transition, holding ownership until execution ends."""
    work = creation.get_creation(creation_id)
    if not is_managed(work):
        return False
    with execution_lock(creation_id) as acquired:
        if not acquired:
            return False
        work = creation.get_creation(creation_id)
        operation, status = next_operation(work)
        # The OS lock proves only that the previous backend owner is gone.
        # OpenClaw can run through a separate gateway after the caller dies.
        # Until its operation can be reconciled, absence of our process is NOT
        # evidence that another model/supply request is safe. Completed domain
        # checkpoints can still advance to a different operation.
        previous_operation = work["delivery"].get("operation")
        if (operation in {"prepare", "author"} and previous_operation == operation
                and not work["delivery"].get("last_error")
                and not work["delivery"].get("agent_calls")):
            operation, status = None, "execution_uncertain"
        attempt_id = (work["delivery"].get("recovering_build_from") if operation == "retry_build" else None
                      ) or (work['delivery'].get('recovering_quality_from') if operation == 'repair_quality' else None
                      ) or _attempt(work).get("attempt_id", "preparation")
        key = f"{attempt_id}:{operation}"
        failures = work["delivery"].get("failures", {})
        observation = operation in {"refresh", "reconcile", "observe_agent"}
        if operation and not observation and (failures.get(key, 0) >= MAX_FAILURES
                                             or work['delivery'].get('exhausted_operation') == key):
            operation, status = None, "failed"
        record = work["delivery"]
        if (observation or previous_operation == operation) and record.get("status") == "observation_failed":
            status = "observation_failed"
        stored_operation = previous_operation if status == "execution_uncertain" else operation
        if ((record.get("status"), record.get("operation")) != (status, stored_operation)
                or status == 'material_ready' and not record.get('material_endpoint_result')):
            with creation.edit_creation(creation_id) as current:
                record = current["delivery"]
                record.update(status=status, operation=stored_operation, updated_at=creation._now())
                if status == 'material_ready':
                    _save_material_endpoint(current)
                if status == "failed":
                    record["exhausted_operation"] = key
        if not operation:
            return False
        if operation == "retry_build" and not record.get("recovering_build_from"):
            # Persist the source BEFORE the existing fork service creates a
            # sibling. A partial copy must resume from this source, not send
            # the half-built latest Attempt into ordinary Preparation.
            with creation.edit_creation(creation_id) as current:
                record = current["delivery"]
                record["recovering_build_from"] = attempt_id
                record.setdefault("build_recoveries", []).append(attempt_id)
            work = creation.get_creation(creation_id)
        if operation == 'repair_quality' and not record.get('recovering_quality_from'):
            with creation.edit_creation(creation_id) as current:
                record = current['delivery']
                record['recovering_quality_from'] = attempt_id
                record.setdefault('quality_repairs', []).append(attempt_id)
            work = creation.get_creation(creation_id)

        # Cancellation must not release the OS lock while a to_thread executor
        # or CLI child still runs. Shutdown drains that call before unlocking.
        async def invoke():
            token = active_delivery.set(creation_id)
            operation_token = active_operation.set(operation)
            started_at, started = creation._now(), monotonic()
            outcome = "completed"
            try:
                await execute(operation, work)
            except DeliveryObservationPending:
                outcome = "pending"
                raise
            except (DeliveryExecutionUncertain, subprocess.TimeoutExpired):
                outcome = "uncertain"
                raise
            except asyncio.CancelledError:
                outcome = "cancelled"
                raise
            except Exception:
                outcome = "failed"
                raise
            finally:
                active_operation.reset(operation_token)
                active_delivery.reset(token)
                elapsed = max(0.0, monotonic() - started)
                with creation.edit_creation(creation_id) as current:
                    timing = current["delivery"].setdefault("operation_timings", {}).setdefault(key, {
                        "calls": 0, "elapsed_seconds": 0.0, "first_started_at": started_at,
                    })
                    timing.update(calls=timing["calls"] + 1,
                                  elapsed_seconds=round(timing["elapsed_seconds"] + elapsed, 6),
                                  last_elapsed_seconds=round(elapsed, 6), last_outcome=outcome,
                                  last_started_at=started_at, last_finished_at=creation._now())

        task = asyncio.create_task(invoke())
        try:
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                try:
                    await task
                finally:
                    raise
        except Exception as exc:
            with creation.edit_creation(creation_id) as current:
                record = current["delivery"]
                if isinstance(exc, DeliveryObservationPending):
                    record.update(status="observation_failed" if exc.disconnected else next_operation(current)[1],
                                  last_error=SecretRedactor.redact_text(str(exc))[:1000] if exc.disconnected else None,
                                  updated_at=creation._now())
                    return False
                if operation in {"prepare", "author", "observe_material", "recover_material", "quality", "repair_planning"} and isinstance(exc, (DeliveryExecutionUncertain, subprocess.TimeoutExpired)):
                    record.update(status="execution_uncertain", last_error=None,
                                  updated_at=creation._now())
                    return False
                if isinstance(exc, DeliveryBudgetExhausted):
                    record.update(status="failed", exhausted_operation=key,
                                  last_error=str(exc), updated_at=creation._now())
                    record.setdefault("failures", {})[key] = MAX_FAILURES
                    return False
                if isinstance(exc, DeliveryReportError):
                    record.update(status="observation_failed" if observation else "failed",
                                  exhausted_operation=key, last_failure_kind=exc.failure_kind,
                                  last_error=str(exc), updated_at=creation._now())
                    return False
                count = record.setdefault("failures", {}).get(key, 0) + 1
                record["failures"][key] = count
                record.update(status="observation_failed" if observation else "failed" if count >= MAX_FAILURES else "retrying",
                              last_error=SecretRedactor.redact_text(str(exc))[:1000],
                              exhausted_operation=key if not observation and count >= MAX_FAILURES else None,
                              updated_at=creation._now())
            return False
        with creation.edit_creation(creation_id) as current:
            record = current["delivery"]
            if operation == "retry_build":
                record.pop("recovering_build_from", None)
            if operation == 'repair_quality':
                record.pop('recovering_quality_from', None)
            record.setdefault("failures", {}).pop(key, None)
            record.update(status=next_operation(current)[1], operation=None, last_error=None, updated_at=creation._now())
            if record['status'] == 'material_ready':
                _save_material_endpoint(current)
        return True


async def _advance_ready_creation(creation_id: str, stop: asyncio.Event, execute: Callable) -> None:
    """Drain ready transitions; unchanged operations still use the polling clock."""
    # Bound a burst even if a broken executor cycles through different states.
    for _ in range(32):
        if stop.is_set():
            return
        before = creation.get_creation(creation_id)
        previous = (_attempt(before).get("attempt_id"), next_operation(before)[0])
        if not await advance_creation(creation_id, execute):
            return
        after = creation.get_creation(creation_id)
        following = (_attempt(after).get("attempt_id"), next_operation(after)[0])
        if following[1] is None or following == previous:
            return


async def serve_delivery(stop: asyncio.Event, execute: Callable, *, interval: float = 3.0) -> None:
    """One backend owner per Creation, resumed from disk on application startup."""
    running: dict[str, asyncio.Task] = {}
    try:
        while not stop.is_set():
            for creation_id in enrolled_creation_ids():
                prior = running.get(creation_id)
                if prior is not None and not prior.done():
                    continue
                if prior is not None:
                    # Observe exceptions (e.g. unavailable disk), without
                    # stopping delivery for unrelated works or claiming failure.
                    try:
                        prior.result()
                    except Exception as exc:
                        logging.getLogger(__name__).warning("作品交付状态读写失败：%s", type(exc).__name__)
                running[creation_id] = asyncio.create_task(_advance_ready_creation(creation_id, stop, execute))
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass
    finally:
        await asyncio.gather(*running.values(), return_exceptions=True)
