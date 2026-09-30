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
from typing import Any, Awaitable, Callable

from easel import creation
from easel.integrations.hypit.secrets import SecretRedactor
from easel.integrations.hypit.service import pricing_has_no_provider_charge

SCHEMA = "easel-creation-delivery@1"
MAX_FAILURES = 3
MAX_BUILD_RECOVERIES = 2
active_delivery: ContextVar[str | None] = ContextVar("active_creation_delivery", default=None)


class DeliveryExecutionUncertain(RuntimeError):
    """Caller lost execution observation; this does not prove remote work ended."""


def is_managed(work: dict[str, Any]) -> bool:
    return (work.get("delivery") or {}).get("schema") == SCHEMA


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
    workflow = work.get("chat_workflow") or {}
    proposal = delivery.get("proposal")
    if (workflow.get("proposal_status") != "CONFIRMED" or not isinstance(proposal, str)
            or hashlib.sha256(proposal.encode()).hexdigest() != workflow.get("proposal_sha256")
            or delivery.get("proposal_sha256") != workflow.get("proposal_sha256")):
        return None, "commission_invalid"
    if delivery.get("stopped"):
        return None, "stopped"
    if work.get("selected_output_name"):
        return None, "accepted"
    if any(call.get("status") in {"pending", "submitting"}
           for call in delivery.get("agent_calls", {}).values()):
        return "observe_agent", "observing_execution"
    if delivery.get("recovering_build_from"):
        return "retry_build", "recovering_production"
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
        return (None, "awaiting_quality") if attempt.get("outputs") else ("export", "exporting")
    if execution == "BUILD_FAILED":
        if len(delivery.get("build_recoveries", [])) < MAX_BUILD_RECOVERIES:
            return "retry_build", "recovering_production"
        return None, "production_failed"
    if execution == "CANCELLED":
        return None, "stopped"
    gate = attempt.get("material_gate") or {}
    if gate.get("bundle_revision") and gate.get("status") in {"MATERIAL_READY", "MATERIAL_NOT_READY"}:
        observed = attempt.get("material_observation") or {}
        if (observed.get("status") != "COMPLETE"
                or observed.get("bundle_revision") != gate.get("bundle_revision")
                or observed.get("plan_revision") != gate.get("plan_revision")):
            return "observe_material", "observing_material"
    if gate.get("status") != "MATERIAL_READY":
        prep_status = (work.get("preparation") or {}).get("status")
        if (prep_status == "SCRIPT_TRUTH_REVIEW_REQUIRED"
                and attempt.get("material_planning", {}).get("truth_review_status") == "PASSED"):
            return "prepare", "preparing"
        if prep_status in {"SCRIPT_TRUTH_REVIEW_REQUIRED", "MATERIAL_NOT_READY"}:
            return None, "needs_evidence"
        return "prepare", "preparing"
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
                      ) or _attempt(work).get("attempt_id", "preparation")
        key = f"{attempt_id}:{operation}"
        failures = work["delivery"].get("failures", {})
        observation = operation in {"refresh", "reconcile", "observe_agent"}
        if operation and not observation and failures.get(key, 0) >= MAX_FAILURES:
            operation, status = None, "failed"
        record = work["delivery"]
        if observation and record.get("status") == "observation_failed":
            status = "observation_failed"
        stored_operation = previous_operation if status == "execution_uncertain" else operation
        if (record.get("status"), record.get("operation")) != (status, stored_operation):
            with creation.edit_creation(creation_id) as current:
                record = current["delivery"]
                record.update(status=status, operation=stored_operation, updated_at=creation._now())
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

        # Cancellation must not release the OS lock while a to_thread executor
        # or CLI child still runs. Shutdown drains that call before unlocking.
        async def invoke():
            token = active_delivery.set(creation_id)
            try:
                await execute(operation, work)
            finally:
                active_delivery.reset(token)

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
                if operation in {"prepare", "author", "observe_material"} and isinstance(exc, (DeliveryExecutionUncertain, subprocess.TimeoutExpired)):
                    record.update(status="execution_uncertain", last_error=None,
                                  updated_at=creation._now())
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
            record.setdefault("failures", {}).pop(key, None)
            record.update(status=next_operation(current)[1], operation=None, last_error=None, updated_at=creation._now())
        return True


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
                running[creation_id] = asyncio.create_task(advance_creation(creation_id, execute))
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass
    finally:
        await asyncio.gather(*running.values(), return_exceptions=True)
