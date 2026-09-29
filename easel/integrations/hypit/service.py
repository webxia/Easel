"""Persist Hypit Build attempts under Easel Creations."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from easel import creation
from easel.integrations.hypit.cli import HypitCLI
from easel.integrations.hypit.errors import HypitCLIError, HypitIntegrationError
from easel.integrations.hypit.handoff import (
    create_handoff,
    resolve_handoff,
    verify_handoff_directory,
)
from easel.integrations.hypit.secrets import SecretRedactor
from easel.integrations.hypit.workspace import (
    attempt_workspace, create_workspace, refresh_authoring_task, workspace_root,
)

_REVIEW_STATES = {"pending", "pass", "modify", "fail"}
_ATTEMPT_ID_RE = re.compile(r"^fa_[0-9a-f]{32}$")
_BUILD_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$")
_OUTPUT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$")
_FINGERPRINT_EXCLUDED_DIRS = {".easel", ".hypit", ".git"}
_AUTHORING_RUN_PATH = "productions/easel-authoring/runs/main.svrun"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _contract_sha256(value: Any) -> str:
    """Hash a JSON contract payload without interpreting provider pricing fields."""
    try:
        encoded = json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise HypitIntegrationError("Hypit contract response is not stable JSON") from exc
    return hashlib.sha256(encoded).hexdigest()


def _attempt_in_creation(work: dict[str, Any], attempt_id: str) -> dict[str, Any] | None:
    return next((item for item in work.get("hypit_attempts", [])
                 if item.get("attempt_id") == attempt_id), None)


def _find_attempt(attempt_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if not _ATTEMPT_ID_RE.fullmatch(attempt_id):
        raise HypitIntegrationError("FilmBuildAttempt ID 非法")
    root = creation.CREATIONS_DIR
    if root.is_dir():
        for directory in root.glob("cr_*"):
            try:
                work = creation._load(directory.name)
            except creation.CreationError:
                continue
            attempt = _attempt_in_creation(work, attempt_id)
            if attempt is not None:
                return work, attempt
    raise HypitIntegrationError("FilmBuildAttempt 不存在")


def _save_attempt(attempt_id: str, mutate) -> dict[str, Any]:
    work, _ = _find_attempt(attempt_id)
    result: dict[str, Any] = {}
    with creation.edit_creation(work["id"]) as current:
        attempt = _attempt_in_creation(current, attempt_id)
        if attempt is None:
            raise HypitIntegrationError("FilmBuildAttempt 不存在")
        updated = mutate(attempt)
        _set_summary(updated)
        current["hypit_attempts"] = [
            updated if item.get("attempt_id") == attempt_id else item
            for item in current.get("hypit_attempts", [])
        ]
        result.update(updated)
    return {"creation_id": work["id"], **result}


def _event(attempt: dict[str, Any], event: str, **fields: Any) -> dict[str, Any]:
    changed = dict(attempt)
    changed["updated_at"] = _now()
    changed.setdefault("history", []).append({"at": changed["updated_at"], "event": event, **fields})
    return changed


def _summary_status(attempt: dict[str, Any]) -> str:
    material_gate = attempt.get("material_gate", {}).get("status")
    if material_gate == "MATERIAL_NOT_READY":
        return "MATERIAL_NOT_READY"
    execution = attempt.get("execution_status", "NOT_SUBMITTED")
    if attempt.get("review_status") == "APPROVED":
        return "REVIEW_APPROVED"
    if attempt.get("export_status") == "EXPORTED":
        return "EXPORTED"
    if execution in {"SUBMITTING", "SUBMISSION_UNCERTAIN", "SUBMITTED", "RUNNING",
                     "BUILD_FAILED", "CANCEL_REQUESTED", "CANCELLED", "BUILD_COMPLETE"}:
        return execution
    if attempt.get("cost", {}).get("approved"):
        return "AWAITING_APPROVAL"
    if attempt.get("cost", {}).get("status") == "pricing_read":
        return "AWAITING_APPROVAL"
    if attempt.get("plan", {}).get("status") == "ready":
        return "PLANNED"
    authoring = attempt.get("authoring_status", "PENDING")
    if authoring in {"READY_FOR_EXTERNAL_AUTHORING", "AUTHORING_RUNNING", "AUTHORING_READY"}:
        return authoring
    preparation = attempt.get("preparation_status")
    if authoring in {"PENDING", "AUTHORING_PENDING"} and preparation in {
        "READY_FOR_EXTERNAL_AUTHORING", "BLOCKED_RUNTIME_NOT_CONFIGURED", "BLOCKED_RUNTIME_INVALID",
    }:
        return preparation
    return {
        "PENDING": "HANDOFF_READY",
        "VALIDATING": "VALIDATING",
        "AUTHORING_FAILED": "AUTHORING_FAILED",
        "PLAN_FAILED": "PLAN_FAILED",
    }.get(authoring, authoring)


def _set_summary(attempt: dict[str, Any]) -> None:
    attempt["status"] = _summary_status(attempt)


def update_film_attempt(attempt_id: str, *, event: str, **fields: Any) -> dict[str, Any]:
    """Persist integration-owned Attempt fields through the shared projection path."""
    if not isinstance(event, str) or not re.fullmatch(r"[a-z][a-z0-9_]{2,80}", event):
        raise HypitIntegrationError("Attempt event name is invalid")

    def update(item: dict[str, Any]) -> dict[str, Any]:
        changed = dict(item)
        changed.update(fields)
        return _event(changed, event, fields=sorted(fields))

    return _save_attempt(attempt_id, update)


def _hypit_outcome(build: dict[str, Any]) -> str | None:
    work = build.get("work")
    result = build.get("result")
    return ((work.get("outcome") if isinstance(work, dict) else None)
            or (result.get("state") if isinstance(result, dict) else None))


def _advance_execution(current: str, incoming: str) -> str:
    terminal = {"BUILD_COMPLETE", "BUILD_FAILED", "CANCELLED"}
    if current in terminal:
        return current
    if current == "RUNNING" and incoming == "SUBMITTED":
        return current
    if current == "CANCEL_REQUESTED" and incoming in {"SUBMITTED", "RUNNING"}:
        return current
    return incoming


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _output_file(creation_id: str, attempt_id: str, output_name: str, *, primary: bool) -> Path:
    if not _OUTPUT_NAME_RE.fullmatch(output_name) or output_name in {".", ".."}:
        raise HypitIntegrationError("Hypit output name 格式非法")
    directory = (creation.OUTPUTS_DIR / "_creations" / creation_id / "attempts" / attempt_id).resolve()
    root = creation.OUTPUTS_DIR.resolve()
    if root not in directory.parents:
        raise HypitIntegrationError("导出目录越过 outputs")
    suffix = "" if primary else "-" + hashlib.sha256(output_name.encode("utf-8")).hexdigest()[:12]
    return directory / f"final{suffix}.mp4"


def _output_path(attempt: dict[str, Any], output: dict[str, Any]) -> Path:
    value = output.get("path")
    if not isinstance(value, str):
        raise HypitIntegrationError("已导出产物缺少安全路径")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise HypitIntegrationError("已导出产物路径非法")
    path = (creation.OUTPUTS_DIR / relative).resolve()
    if creation.OUTPUTS_DIR.resolve() not in path.parents or not path.is_file():
        raise HypitIntegrationError("已导出产物不存在或越过 outputs")
    expected = (creation.OUTPUTS_DIR / "_creations" / attempt["creation_id"]
                / "attempts" / attempt["attempt_id"]).resolve()
    if expected not in path.parents:
        raise HypitIntegrationError("产物不属于当前 Attempt")
    return path


def _runtime_identity(value: str) -> dict[str, str]:
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise HypitIntegrationError("Hypit Runtime Profile 必须是有效的绝对文件路径")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise HypitIntegrationError("Hypit Runtime Profile 文件不存在") from exc
    if not resolved.is_file():
        raise HypitIntegrationError("Hypit Runtime Profile 必须指向文件")
    try:
        document = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HypitIntegrationError("Hypit Runtime Profile 不是有效 JSON") from exc
    if not isinstance(document, dict) or document.get("format") != "hypit.runtime-local@1":
        raise HypitIntegrationError("Hypit Runtime Profile 格式必须是 hypit.runtime-local@1")
    allowed = {"format", "dataRoot", "worker", "credentials", "endpoints", "bindings"}
    if set(document) - allowed:
        raise HypitIntegrationError("Hypit Runtime Profile 含当前 Hypit 不认识的字段")
    if not isinstance(document.get("dataRoot"), str) or not document["dataRoot"].strip():
        raise HypitIntegrationError("Hypit Runtime Profile 缺少 dataRoot")
    for field in ("credentials", "endpoints", "bindings"):
        if field in document and not isinstance(document[field], dict):
            raise HypitIntegrationError(f"Hypit Runtime Profile {field} 必须是对象")
    instances: set[str] = set()
    for group in ("credentials", "endpoints"):
        entries = document.get(group, {})
        for instance, entry in entries.items():
            if (not isinstance(instance, str) or not instance.strip() or not isinstance(entry, dict)
                    or not isinstance(entry.get("use"), str) or not entry["use"].strip()):
                raise HypitIntegrationError(f"Hypit Runtime Profile {group} 条目无效")
            entry_fields = {"use", "config"} | ({"pool"} if group == "endpoints" else set())
            if set(entry) - entry_fields:
                raise HypitIntegrationError(f"Hypit Runtime Profile {group} 条目包含无效字段")
            if "pool" in entry and (not isinstance(entry["pool"], str) or not entry["pool"].strip()):
                raise HypitIntegrationError("Hypit Runtime Profile Endpoint pool 无效")
            if instance in instances:
                raise HypitIntegrationError("Hypit Runtime Profile instance ID 重复")
            instances.add(instance)
    bindings = document.get("bindings", {})
    if (not isinstance(bindings, dict)
            or any(not isinstance(key, str) or not key.strip() or not isinstance(target, str)
                   or target not in document.get("endpoints", {})
                   for key, target in bindings.items())):
        raise HypitIntegrationError("Hypit Runtime Profile bindings 必须指向已声明的 Endpoint")
    worker = document.get("worker")
    if worker is not None and (not isinstance(worker, dict)
                               or set(worker) != {"executionMemoryMb"}
                               or type(worker.get("executionMemoryMb")) is not int
                               or worker["executionMemoryMb"] <= 0):
        raise HypitIntegrationError("Hypit Runtime Profile worker 配置无效")
    return {"path": str(resolved), "sha256": _file_sha256(resolved),
            "format": "hypit.runtime-local@1"}


def _authoring_file_hash(
    workspace: Path, run_source: Path,
) -> tuple[str, str, str, list[dict[str, str]]]:
    entries: list[dict[str, str]] = []
    for path in sorted(workspace.rglob("*")):
        relative = path.relative_to(workspace)
        if any(part in _FINGERPRINT_EXCLUDED_DIRS for part in relative.parts):
            continue
        if path.is_symlink():
            raise HypitIntegrationError(f"Authoring workspace 不允许 symlink：{relative.as_posix()}")
        if path.is_file():
            entries.append({"path": relative.as_posix(), "sha256": _file_sha256(path)})
    run_relative = run_source.relative_to(workspace).as_posix()
    run_entry = next((item for item in entries if item["path"] == run_relative), None)
    if run_entry is None:
        raise HypitIntegrationError("Hypit Run 未纳入 authoring fingerprint")
    payload = json.dumps(entries, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    dependencies = [item for item in entries if item["path"] != run_relative]
    dependency_bytes = json.dumps(dependencies, ensure_ascii=False, sort_keys=True,
                                  separators=(",", ":")).encode("utf-8")
    return (
        "sha256:" + hashlib.sha256(payload).hexdigest(),
        run_entry["sha256"],
        "sha256:" + hashlib.sha256(dependency_bytes).hexdigest(),
        entries,
    )


def _execution_fingerprint(attempt: dict[str, Any], run_path: str | None = None) -> dict[str, Any]:
    workspace = _workspace(attempt)
    handoff_id = attempt.get("handoff", {}).get("handoff_id")
    package, manifest, handoff_hash = resolve_handoff(attempt["creation_id"], handoff_id)
    if handoff_hash != attempt.get("handoff", {}).get("hash"):
        raise HypitIntegrationError("Attempt Handoff hash 与 Creation 登记不一致")
    copied_manifest, copied_hash = verify_handoff_directory(workspace / "handoff", handoff_hash)
    if copied_hash != handoff_hash or copied_manifest.get("handoff_id") != handoff_id:
        raise HypitIntegrationError("Hypit workspace Handoff snapshot 与 Attempt 不一致")
    run_source = _run_source(attempt, run_path)
    authoring_hash, run_hash, dependencies_hash, files = _authoring_file_hash(workspace, run_source)
    runtime_profile = attempt.get("runtime_profile")
    if not isinstance(runtime_profile, dict) or not isinstance(runtime_profile.get("path"), str):
        raise HypitIntegrationError("当前 Attempt 被 Runtime Profile 缺失状态阻塞")
    runtime = _runtime_identity(runtime_profile["path"])
    components = {
        "handoff_sha256": handoff_hash,
        "authoring_sha256": authoring_hash,
        "run_sha256": run_hash,
        "authoring_dependencies_sha256": dependencies_hash,
        "authoring_files": files,
        "mode_snapshot_sha256": manifest["creative_mode"]["hash"],
        "runtime_profile_path": runtime["path"],
        "runtime_profile_sha256": runtime["sha256"],
        "run_path": run_source.relative_to(workspace).as_posix(),
    }
    encoded = json.dumps(components, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**components, "sha256": "sha256:" + hashlib.sha256(encoded).hexdigest()}


def _invalidate_cost(item: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    item["plan"] = {**item.get("plan", {}), "status": "stale", "execution_fingerprint": None}
    item["cost"] = {
        **item.get("cost", {}), "status": "stale", "pricing": None,
        "estimated_usd": None, "approved": False, "approved_fingerprint": None,
        "pricing_sha256": None, "approved_pricing_sha256": None,
        "approved_plan_sha256": None,
        "invalidated_at": _now(), "current_fingerprint": current["sha256"],
    }
    _set_summary(item)
    return item


def _invalidate_unverifiable_cost(item: dict[str, Any]) -> dict[str, Any]:
    item["plan"] = {**item.get("plan", {}), "status": "stale", "execution_fingerprint": None}
    item["cost"] = {
        **item.get("cost", {}), "status": "stale", "pricing": None,
        "estimated_usd": None, "approved": False, "approved_fingerprint": None,
        "pricing_sha256": None, "approved_pricing_sha256": None,
        "approved_plan_sha256": None,
        "invalidated_at": _now(), "invalidation_reason": "execution_fingerprint_unavailable",
    }
    _set_summary(item)
    return item


def _invalidate_if_unsubmitted(item: dict[str, Any]) -> dict[str, Any]:
    if item.get("execution_status", "NOT_SUBMITTED") != "NOT_SUBMITTED":
        return item
    return _invalidate_unverifiable_cost(item)


def _record_operation_error(
    attempt_id: str,
    operation: str,
    error: Exception,
    *,
    status: str | None = None,
) -> None:
    message = SecretRedactor.redact_text(str(error).strip())[:2000] or type(error).__name__

    def update(item):
        changed = dict(item)
        if status:
            if status == "SUBMISSION_UNCERTAIN":
                changed["execution_status"] = status
            elif status in {"AUTHORING_FAILED", "PLAN_FAILED"}:
                changed["authoring_status"] = status
                if status == "AUTHORING_FAILED":
                    changed["authoring"] = {
                        **changed.get("authoring", {}),
                        "status": "failed",
                        "failed_at": _now(),
                    }
        changed["last_error"] = {"operation": operation, "message": message, "at": _now()}
        _set_summary(changed)
        return _event(changed, "operation_failed", operation=operation, error=message)

    try:
        _save_attempt(attempt_id, update)
    except Exception:
        pass


def _workspace(attempt: dict[str, Any]) -> Path:
    root = Path(attempt["workspace"].get("root", "")).expanduser()
    if not root.is_absolute():
        raise HypitIntegrationError("Attempt 缺少有效的持久化 Hypit workspace root")
    expected = attempt_workspace(attempt["creation_id"], attempt["attempt_id"], root=root)
    value = Path(attempt["workspace"]["path"]).expanduser().resolve()
    if value != expected:
        raise HypitIntegrationError("Hypit workspace 路径与 Attempt 身份不一致")
    if not value.is_dir():
        raise HypitIntegrationError("Hypit workspace 已不存在")
    return value


def _run_source(attempt: dict[str, Any], run_path: str | None = None) -> Path:
    workspace = _workspace(attempt)
    value = run_path or attempt.get("authoring", {}).get("run_path")
    if not isinstance(value, str) or not value:
        raise HypitIntegrationError("请先提供 Hypit Run 文件路径")
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise HypitIntegrationError("Hypit Run 必须位于 workspace 内")
    source = (workspace / candidate).resolve()
    if workspace not in source.parents or not source.is_file():
        raise HypitIntegrationError("Hypit Run 文件不存在或越过 workspace")
    return source


def _cli(cli: HypitCLI | None) -> HypitCLI:
    return cli or HypitCLI()


def create_creation_handoff(creation_id: str, **kwargs: Any) -> dict[str, Any]:
    return create_handoff(creation_id, **kwargs)


def create_film_attempt(
    creation_id: str,
    handoff_id: str,
    *,
    runtime_profile: str | None = None,
    preparation_key: str | None = None,
    runtime_status: str | None = None,
) -> dict[str, Any]:
    if preparation_key is not None and not re.fullmatch(r"[0-9a-f]{64}", preparation_key):
        raise HypitIntegrationError("Preparation operation key 格式无效")
    if not runtime_profile and not preparation_key:
        raise HypitIntegrationError("创建 Hypit Attempt 时必须指定 Hypit Runtime Profile 绝对路径")
    runtime = _runtime_identity(runtime_profile) if runtime_profile else None
    effective_runtime_status = runtime_status or ("CONFIGURED" if runtime else "NOT_CONFIGURED")
    if effective_runtime_status not in {"CONFIGURED", "NOT_CONFIGURED", "INVALID"}:
        raise HypitIntegrationError("Attempt Runtime status 无效")
    if (runtime is None) == (effective_runtime_status == "CONFIGURED"):
        raise HypitIntegrationError("Attempt Runtime 状态与 Runtime Profile 不一致")
    execution_status = "NOT_SUBMITTED" if runtime else "BLOCKED"
    work = creation.get_creation(creation_id)
    try:
        creation.require_chat_proposal_confirmed(work)
    except creation.CreationError as exc:
        raise HypitIntegrationError(str(exc)) from exc
    package, manifest, handoff_hash = resolve_handoff(creation_id, handoff_id)
    if manifest.get("production_request", {}).get("media_type") != "video":
        raise HypitIntegrationError("Hypit V1 当前只接收 video Handoff")
    attempt_id = (
        "fa_" + hashlib.sha256(f"{creation_id}:{preparation_key}".encode("utf-8")).hexdigest()[:32]
        if preparation_key else f"fa_{uuid.uuid4().hex}"
    )
    root = workspace_root()
    now = _now()
    with creation.edit_creation(creation_id) as current:
        if preparation_key:
            existing = next((item for item in current.get("hypit_attempts", [])
                             if item.get("preparation_key") == preparation_key), None)
            if existing:
                if runtime and existing.get("runtime_status") != "CONFIGURED":
                    if (existing.get("execution_status") not in {"BLOCKED", "NOT_SUBMITTED"}
                            or existing.get("build", {}).get("operation")
                            or existing.get("build", {}).get("build_id")):
                        raise HypitIntegrationError("Attempt 已进入执行流程，不能替换 Runtime Profile")
                    existing = {
                        **existing,
                        "runtime_profile": runtime,
                        "runtime_status": "CONFIGURED",
                        "execution_status": "NOT_SUBMITTED",
                        "execution_block_reason": None,
                        "status": "READY_FOR_EXTERNAL_AUTHORING",
                        "preparation_status": "READY_FOR_EXTERNAL_AUTHORING",
                        "updated_at": now,
                        "history": [*existing.get("history", []), {
                            "at": now, "event": "runtime_profile_resolved",
                        }],
                    }
                    current["hypit_attempts"] = [
                        existing if item.get("attempt_id") == existing["attempt_id"] else item
                        for item in current.get("hypit_attempts", [])
                    ]
                return existing
        attempt_number = max((int(item.get("attempt_number", 0))
                              for item in current.get("hypit_attempts", [])), default=0) + 1
        target = create_workspace(
            creation_id, attempt_id, package,
            handoff_id=handoff_id, handoff_hash=handoff_hash,
            root=root,
        )
        attempt = {
            "schema": "easel-film-build-attempt@1",
            "attempt_id": attempt_id,
            "creation_id": creation_id,
            "attempt_number": attempt_number,
            "backend": "hypit",
            "status": "READY_FOR_EXTERNAL_AUTHORING",
            "authoring_status": "READY_FOR_EXTERNAL_AUTHORING",
            "preparation_status": "READY_FOR_EXTERNAL_AUTHORING",
            "runtime_status": effective_runtime_status,
            "execution_status": execution_status,
            "execution_block_reason": (None if runtime else f"RUNTIME_{effective_runtime_status}"),
            "export_status": "NOT_EXPORTED",
            "review_status": "PENDING",
            "handoff": {"handoff_id": handoff_id, "hash": handoff_hash},
            "production_request": manifest.get("production_request", {}),
            "workspace": {"path": str(target), "root": str(root)},
            "runtime_profile": runtime,
            **({"preparation_key": preparation_key} if preparation_key else {}),
            "authoring": {"status": "pending", "task_path": "AUTHORING_TASK.md"},
            "plan": {"status": "pending", "execution_fingerprint": None},
            "cost": {
                "status": "not_estimated",
                "approval_required": bool(manifest.get("cost_policy", {}).get("approval_required", True)),
                "max_budget_usd": manifest.get("cost_policy", {}).get("max_budget_usd"),
                "approved": False,
                "approved_fingerprint": None,
                "approved_budget_is_hard_spend_cap": False,
                "total": {"status": "unknown", "currency": "USD", "reason": "Hypit pricing 未提供可验证的聚合总价"},
                "budget_notice": "approved_budget_usd 仅为用户批准金额，不是 Hypit 或 Provider 的硬消费上限",
            },
            "build": {"build_id": None, "status": "not_submitted", "operation": None},
            "outputs": {},
            "review": {
                "technical": {"status": "pending", "notes": []},
                "truth": {"status": "pending", "notes": []},
                "style": {"status": "pending", "notes": []},
                "human": {"status": "pending"},
                "feedback": [],
            },
            "selected": False,
            "created_at": now,
            "updated_at": now,
            "history": [{"at": now, "event": "workspace_created"}],
        }
        current.setdefault("hypit_attempts", []).append(attempt)
        current.setdefault("history", []).append({
            "at": now, "event": "hypit_attempt_created", "attempt_id": attempt_id,
            "attempt_number": attempt_number,
        })
    return attempt


def authoring_agent_task(attempt_id: str) -> dict[str, str]:
    """Return the fixed, workspace-scoped task for the existing Easel Director.

    This intentionally does not invoke Hypit.  The Web layer dispatches the
    same OpenClaw main Agent that handled Preparation; this helper keeps the
    task path and allowed output surface deterministic.
    """
    attempt = get_film_attempt(attempt_id)
    workspace = _workspace(attempt)
    handoff_id = attempt.get("handoff", {}).get("handoff_id")
    handoff_hash = attempt.get("handoff", {}).get("hash")
    if not isinstance(handoff_id, str) or not isinstance(handoff_hash, str):
        raise HypitIntegrationError("Attempt 缺少冻结的 Handoff 身份")
    verify_handoff_directory(workspace / "handoff", handoff_hash)
    if attempt.get("authoring_status") == "AUTHORING_FAILED":
        refresh_authoring_task(
            workspace, handoff_id=handoff_id, handoff_hash=handoff_hash,
        )
    return {
        "workspace": str(workspace),
        "task_path": str(workspace / "AUTHORING_TASK.md"),
        "run_path": _AUTHORING_RUN_PATH,
    }


def begin_film_authoring(attempt_id: str) -> dict[str, Any]:
    """Claim one no-media authoring operation for an Attempt.

    The authoring lock is persisted before an Agent is dispatched, so a retry
    or duplicate UI click cannot create concurrent writers in one workspace.
    """
    attempt = get_film_attempt(attempt_id)
    # Material-integrated attempts must pass the current MaterialReadiness
    # evidence and explicit Production Authoring selection before dispatch.
    # Legacy/unintegrated attempts retain the existing authoring contract.
    if "material_planning" in attempt or "material_gate" in attempt:
        from easel.integrations.material_layer import MaterialGateIntegration

        MaterialGateIntegration().assert_ready(attempt)
        if attempt.get("production_authoring", {}).get("status") not in {
            "PENDING_SELECTION", "SELECTION_RECORDED", "READY",
        }:
            raise HypitIntegrationError("Production Authoring 尚未完成素材选择")
    task = authoring_agent_task(attempt_id)
    try:
        creation.require_chat_proposal_confirmed(creation.get_creation(attempt["creation_id"]))
    except creation.CreationError as exc:
        raise HypitIntegrationError(str(exc)) from exc

    def begin(item: dict[str, Any]) -> dict[str, Any]:
        if item.get("execution_status") not in {"BLOCKED", "NOT_SUBMITTED"}:
            raise HypitIntegrationError("Attempt 已进入执行阶段，不能重新开始 Authoring")
        current = item.get("authoring_status", "PENDING")
        if current == "AUTHORING_RUNNING":
            return item
        if current == "AUTHORING_READY":
            return item
        if current not in {"READY_FOR_EXTERNAL_AUTHORING", "AUTHORING_FAILED"}:
            raise HypitIntegrationError(f"Attempt 当前不能开始 Authoring：{current}")
        changed = {
            **item,
            "authoring_status": "AUTHORING_RUNNING",
            "authoring": {
                **item.get("authoring", {}),
                "status": "running",
                "task_path": "AUTHORING_TASK.md",
                "run_path": _AUTHORING_RUN_PATH,
                "started_at": _now(),
            },
            "last_error": None,
        }
        _set_summary(changed)
        return _event(changed, "authoring_started", run_path=_AUTHORING_RUN_PATH)

    result = _save_attempt(attempt_id, begin)
    return {**result, "authoring_task": task}


def _normalize_single_timeline_clock_reference(source: Path) -> bool:
    """Normalize Hypit's single-clock shorthand only when its target is unambiguous.

    Some Authoring agents serialize a typed Hypit reference as a quoted string.
    The installed timeline-author surface requires ``clock={clock}``. When a
    source has exactly one Clock declaration and every string-valued Timeline
    clock points to that declaration, rewrite only that declaration/reference;
    otherwise leave the source untouched for Hypit's normal diagnostic path.
    """
    if not source.is_file():
        return False
    text = source.read_text(encoding="utf-8")
    clocks = list(re.finditer(r'<time:Clock\b[^>]*\bid="([A-Za-z_][A-Za-z0-9_-]*)"[^>]*/>', text))
    if len(clocks) != 1:
        return False
    clock_match = clocks[0]
    old_id = clock_match.group(1)
    timelines = list(re.finditer(
        r'(<time:Timeline\b[^>]*?\bclock=)"([A-Za-z_][A-Za-z0-9_-]*)"', text,
    ))
    timeline_count = len(re.findall(r'<time:Timeline\b', text))
    if (not timelines or timeline_count != len(timelines)
            or any(match.group(2) != old_id for match in timelines)):
        return False
    if old_id != "clock" and re.search(r'\bid="clock"', text):
        return False

    text = text[:clock_match.start(1)] + "clock" + text[clock_match.end(1):]
    text = re.sub(
        r'(<time:Timeline\b[^>]*?\bclock=)"' + re.escape(old_id) + r'"',
        r"\1{clock}", text,
    )
    source.write_text(text, encoding="utf-8")
    return True


def complete_film_authoring(
    attempt_id: str,
    *,
    cli: HypitCLI | None = None,
) -> dict[str, Any]:
    """Run Hypit's local syntax check and freeze a valid Authoring result.

    `hypit check` validates authored sources only.  Runtime resolution, plan,
    pricing and Build remain separate execution-stage operations.
    """
    attempt = get_film_attempt(attempt_id)
    if "material_planning" in attempt or "material_gate" in attempt:
        from easel.integrations.material_layer import MaterialGateIntegration

        MaterialGateIntegration().assert_ready(attempt)
    if attempt.get("authoring_status") == "AUTHORING_READY":
        return attempt
    if attempt.get("authoring_status") != "AUTHORING_RUNNING":
        raise HypitIntegrationError("Attempt 未处于 Authoring 运行状态")
    workspace = _workspace(attempt)
    handoff_hash = attempt.get("handoff", {}).get("hash")
    if not isinstance(handoff_hash, str):
        raise HypitIntegrationError("Attempt 缺少 Handoff hash")
    verify_handoff_directory(workspace / "handoff", handoff_hash)
    source = _run_source(attempt, _AUTHORING_RUN_PATH)
    if "material_planning" in attempt or "material_gate" in attempt:
        from easel.integrations.material_layer import ProductionAuthoringIntegration

        attempt = ProductionAuthoringIntegration().validate_authored_selection(
            attempt, _AUTHORING_RUN_PATH,
        )["attempt"]
    authored_source = workspace / "productions/easel-authoring/authors/main.svml"
    normalized_clock_reference = _normalize_single_timeline_clock_reference(authored_source)
    try:
        check = _cli(cli).check(workspace, source)
        if normalized_clock_reference:
            check = {**check, "easel_normalizations": ["single_timeline_clock_reference"]}
    except HypitIntegrationError as exc:
        _record_operation_error(attempt_id, "authoring_check", exc, status="AUTHORING_FAILED")
        raise
    if check.get("ok") is not True:
        error = HypitIntegrationError("Hypit Authoring 静态校验未通过")
        _record_operation_error(attempt_id, "authoring_check", error, status="AUTHORING_FAILED")
        raise error
    authoring_hash, run_hash, dependencies_hash, files = _authoring_file_hash(workspace, source)

    def finish(item: dict[str, Any]) -> dict[str, Any]:
        if item.get("authoring_status") != "AUTHORING_RUNNING":
            raise HypitIntegrationError("Authoring 状态已变化，拒绝覆盖")
        changed = {
            **item,
            "authoring_status": "AUTHORING_READY",
            "authoring": {
                **item.get("authoring", {}),
                "status": "ready",
                "run_path": _AUTHORING_RUN_PATH,
                "check": SecretRedactor.redact(check),
                "authoring_sha256": authoring_hash,
                "run_sha256": run_hash,
                "dependencies_sha256": dependencies_hash,
                "files": files,
                "completed_at": _now(),
            },
        }
        _set_summary(changed)
        return _event(changed, "authoring_ready", run_path=_AUTHORING_RUN_PATH,
                      authoring_sha256=authoring_hash)

    return _save_attempt(attempt_id, finish)


def resolve_film_attempt_runtime(attempt_id: str, runtime_profile: str) -> dict[str, Any]:
    """Attach the server-selected Runtime after authoring, without creating an Attempt."""
    runtime = _runtime_identity(runtime_profile)

    def resolve(item):
        if item.get("runtime_status") == "CONFIGURED":
            if item.get("runtime_profile") == runtime:
                return item
            raise HypitIntegrationError("Attempt Runtime 已绑定；更换 Runtime 需要重新校验输入")
        if item.get("execution_status") != "BLOCKED" or item.get("build", {}).get("build_id"):
            raise HypitIntegrationError("只有尚未进入执行的 Attempt 才能解析 Runtime")
        changed = {
            **item,
            "runtime_profile": runtime,
            "runtime_status": "CONFIGURED",
            "execution_status": "NOT_SUBMITTED",
            "execution_block_reason": None,
            "updated_at": _now(),
        }
        _set_summary(changed)
        return _event(changed, "runtime_profile_resolved", runtime_profile_sha256=runtime["sha256"])

    return _save_attempt(attempt_id, resolve)


def list_film_attempts(creation_id: str) -> list[dict[str, Any]]:
    work = creation.get_creation(creation_id)
    return list(reversed(work.get("hypit_attempts", [])))


def get_film_attempt(attempt_id: str) -> dict[str, Any]:
    work, attempt = _find_attempt(attempt_id)
    return {"creation_id": work["id"], **attempt}


def validate_film_attempt(
    attempt_id: str,
    run_path: str,
    *,
    cli: HypitCLI | None = None,
) -> dict[str, Any]:
    attempt = get_film_attempt(attempt_id)
    if "material_planning" in attempt or "material_gate" in attempt:
        from easel.integrations.material_layer import ProductionAuthoringIntegration

        attempt = ProductionAuthoringIntegration().assert_selection_current(attempt, run_path)
    if not isinstance(attempt.get("runtime_profile"), dict):
        raise HypitIntegrationError("Film Authoring 可以继续；validate 前必须先完成 Runtime Resolution")
    def begin_validation(item):
        if item.get("execution_status", "NOT_SUBMITTED") != "NOT_SUBMITTED":
            raise HypitIntegrationError("已提交的 Attempt 不可重新 validate；请创建新的 Attempt")
        if item.get("authoring_status") == "VALIDATING":
            raise HypitIntegrationError("该 Attempt 正在 validate")
        changed = {**item, "authoring_status": "VALIDATING", "status": "VALIDATING"}
        return _event(changed, "validation_started")

    attempt = _save_attempt(attempt_id, begin_validation)
    workspace = _workspace(attempt)
    source = _run_source(attempt, run_path)
    client = _cli(cli)
    try:
        check = client.check(workspace, source)
    except HypitIntegrationError as exc:
        _record_operation_error(attempt_id, "check", exc, status="AUTHORING_FAILED")
        raise
    if check.get("ok") is not True:
        def fail_check(item):
            item["authoring_status"] = "AUTHORING_FAILED"
            item["authoring"] = {"status": "failed", "run_path": run_path, "check": check}
            _set_summary(item)
            return _event(item, "authoring_check_failed")
        return _save_attempt(attempt_id, fail_check)

    fingerprint_before = _execution_fingerprint(attempt, run_path)
    runtime_profile = attempt["runtime_profile"]["path"]
    try:
        plan = client.plan(workspace, source, runtime_profile=runtime_profile)
    except HypitIntegrationError as exc:
        _record_operation_error(attempt_id, "plan", exc, status="PLAN_FAILED")
        raise
    okay = plan.get("ok") is True
    fingerprint_after = _execution_fingerprint(get_film_attempt(attempt_id), run_path)
    if okay and fingerprint_before["sha256"] != fingerprint_after["sha256"]:
        def stale_plan(item):
            item["authoring_status"] = "PLAN_FAILED"
            item["plan"] = {**item.get("plan", {}), "status": "stale", "execution_fingerprint": None}
            _set_summary(item)
            return _event(item, "input_changed_during_plan")
        _save_attempt(attempt_id, stale_plan)
        raise HypitIntegrationError("Plan 期间 Run/依赖发生变化；请重新 validate")
    def finish_plan(item):
        item["authoring_status"] = "PLANNED" if okay else "PLAN_FAILED"
        item["authoring"] = {"status": "ready" if okay else "failed",
                              "run_path": run_path, "check": SecretRedactor.redact(check)}
        safe_plan = SecretRedactor.redact(plan)
        item["plan"] = {"status": "ready" if okay else "failed",
                        "result": safe_plan,
                        "contract_sha256": _contract_sha256(safe_plan) if okay else None,
                        "execution_fingerprint": fingerprint_after if okay else None}
        _set_summary(item)
        return _event(item, "plan_completed" if okay else "plan_failed")
    return _save_attempt(attempt_id, finish_plan)


def estimate_film_attempt(attempt_id: str, *, cli: HypitCLI | None = None) -> dict[str, Any]:
    attempt = get_film_attempt(attempt_id)
    if attempt.get("execution_status") == "BLOCKED":
        raise HypitIntegrationError("Execution 被 Runtime 配置阻塞；先完成 Runtime Resolution")
    if attempt.get("execution_status", "NOT_SUBMITTED") != "NOT_SUBMITTED":
        raise HypitIntegrationError("Build 已提交后不能重新 pricing")
    if attempt.get("authoring_status") not in ("PLANNED", "AUTHORING_READY") or attempt.get("plan", {}).get("status") != "ready":
        raise HypitIntegrationError("必须先通过 check 和 plan")
    try:
        fingerprint = _execution_fingerprint(attempt)
    except HypitIntegrationError:
        _save_attempt(attempt_id, lambda item: _event(
            _invalidate_if_unsubmitted(item), "approval_invalidated_fingerprint_unavailable"))
        raise
    planned_fingerprint = attempt.get("plan", {}).get("execution_fingerprint", {}).get("sha256")
    if fingerprint["sha256"] != planned_fingerprint:
        _save_attempt(attempt_id, lambda item: _event(
            _invalidate_cost(item, fingerprint), "approval_invalidated_input_changed"))
        raise HypitIntegrationError("Plan 输入已变化；必须重新 validate、pricing 并批准")
    try:
        plan_sha256 = _contract_sha256(attempt.get("plan", {}).get("result"))
    except HypitIntegrationError:
        _save_attempt(attempt_id, lambda item: _invalidate_cost(item, fingerprint))
        raise
    if plan_sha256 != attempt.get("plan", {}).get("contract_sha256"):
        _save_attempt(attempt_id, lambda item: _invalidate_cost(item, fingerprint))
        raise HypitIntegrationError("Plan contract changed; revalidate before pricing")
    workspace = _workspace(attempt)
    source = _run_source(attempt)
    try:
        pricing = _cli(cli).pricing(
            workspace, source, runtime_profile=attempt["runtime_profile"]["path"])
    except HypitIntegrationError as exc:
        _record_operation_error(attempt_id, "pricing", exc, status="PRICING_FAILED")
        raise
    after = _execution_fingerprint(get_film_attempt(attempt_id))
    if after["sha256"] != fingerprint["sha256"]:
        _save_attempt(attempt_id, lambda item: _event(
            _invalidate_cost(item, after), "approval_invalidated_pricing_input_changed"))
        raise HypitIntegrationError("Pricing 期间 Run/依赖发生变化；必须重新 validate、pricing 并批准")
    # Hypit reports provider pricing material but does not calculate a single total.
    safe_pricing = SecretRedactor.redact(pricing)
    pricing_sha256 = _contract_sha256(safe_pricing)
    return _save_attempt(attempt_id, lambda item: _event(
        {**item,
         "cost": {**item["cost"], "status": "pricing_read", "estimated_usd": None,
                  "pricing": safe_pricing, "pricing_sha256": pricing_sha256,
                  "approved_pricing_sha256": None, "approved_plan_sha256": None, "approved": False,
                  "approved_fingerprint": None, "execution_fingerprint": after,
                  "plan_sha256": plan_sha256,
                  "total": {"status": "unknown", "currency": "USD",
                            "reason": "Hypit pricing 提供各 Provider 价格材料，不提供可验证的聚合总价"},
                  "approved_budget_is_hard_spend_cap": False,
                  "limit_enforced_by_hypit": False,
                  "budget_notice": "批准金额表示操作员同意继续执行，不是 Hypit 或 Provider 强制执行的消费上限",
                  }},
        "pricing_read"))


def approve_film_cost(attempt_id: str, max_budget_usd: float) -> dict[str, Any]:
    if not math.isfinite(max_budget_usd) or max_budget_usd <= 0:
        raise HypitIntegrationError("必须明确批准一个大于 0 的美元预算")
    attempt = get_film_attempt(attempt_id)
    if attempt.get("execution_status") == "BLOCKED":
        raise HypitIntegrationError("Execution 被 Runtime 配置阻塞；先完成 Runtime Resolution")
    if attempt.get("execution_status", "NOT_SUBMITTED") != "NOT_SUBMITTED":
        raise HypitIntegrationError("已提交的 Attempt 不能重新批准 Build")
    if attempt.get("cost", {}).get("status") != "pricing_read" or attempt.get("cost", {}).get("pricing") is None:
        raise HypitIntegrationError("请先完成 Hypit pricing 读取")
    cost = attempt.get("cost", {})
    plan = attempt.get("plan", {})
    try:
        plan_sha256 = _contract_sha256(plan.get("result"))
        pricing_sha256 = _contract_sha256(cost.get("pricing"))
    except HypitIntegrationError:
        raise
    if (plan_sha256 != plan.get("contract_sha256")
            or plan_sha256 != cost.get("plan_sha256")
            or pricing_sha256 != cost.get("pricing_sha256")):
        current = cost.get("execution_fingerprint") or {"sha256": "unavailable"}
        _save_attempt(attempt_id, lambda item: _invalidate_cost(item, current))
        raise HypitIntegrationError("Plan/Pricing contract changed; approval is blocked")
    declared_cap = attempt["cost"].get("max_budget_usd")
    if declared_cap is not None and max_budget_usd > float(declared_cap):
        raise HypitIntegrationError("批准金额不能高于 Handoff 声明的预算上限")
    outcome: dict[str, Any] = {}

    def approve(item):
        if item.get("execution_status", "NOT_SUBMITTED") != "NOT_SUBMITTED":
            raise HypitIntegrationError("已提交的 Attempt 不能重新批准 Build")
        if item.get("cost", {}).get("status") != "pricing_read" or item.get("cost", {}).get("pricing") is None:
            raise HypitIntegrationError("请先完成 Hypit pricing 读取")
        try:
            current = _execution_fingerprint(item)
        except HypitIntegrationError:
            _invalidate_unverifiable_cost(item)
            outcome["unverifiable"] = True
            return _event(item, "approval_invalidated_fingerprint_unavailable")
        expected = item.get("cost", {}).get("execution_fingerprint", {}).get("sha256")
        planned = item.get("plan", {}).get("execution_fingerprint", {}).get("sha256")
        current_plan = item.get("plan", {})
        current_cost = item.get("cost", {})
        try:
            plan_sha256 = _contract_sha256(current_plan.get("result"))
            pricing_sha256 = _contract_sha256(current_cost.get("pricing"))
        except HypitIntegrationError:
            _invalidate_unverifiable_cost(item)
            outcome["unverifiable"] = True
            return _event(item, "approval_invalidated_contract_unavailable")
        if (current["sha256"] != expected or current["sha256"] != planned
                or plan_sha256 != current_plan.get("contract_sha256")
                or plan_sha256 != current_cost.get("plan_sha256")
                or pricing_sha256 != current_cost.get("pricing_sha256")):
            _invalidate_cost(item, current)
            outcome["stale"] = True
            return _event(item, "approval_invalidated_before_approval")
        item["cost"] = {**item["cost"], "approved": True,
                         "approved_budget_usd": float(max_budget_usd),
                         "approved_at": _now(), "approved_fingerprint": current,
                         "approved_plan_sha256": plan_sha256,
                         "approved_pricing_sha256": pricing_sha256,
                         "approved_budget_is_hard_spend_cap": False,
                         "approval_kind": "explicit_operator_approval",
                         "limit_enforced_by_hypit": False}
        return _event(item, "cost_approved", approved_budget_usd=float(max_budget_usd))

    saved = _save_attempt(attempt_id, approve)
    if outcome.get("unverifiable"):
        raise HypitIntegrationError("当前输入 fingerprint 无法验证；批准已失效")
    if outcome.get("stale"):
        raise HypitIntegrationError("Pricing/Plan 输入已变化；批准已失效，请重新 validate、pricing 后再批准")
    return saved


def submit_film_build(
    attempt_id: str,
    *,
    title: str,
    cli: HypitCLI | None = None,
) -> dict[str, Any]:
    if not isinstance(title, str) or not title.strip():
        raise HypitIntegrationError("Hypit Build 需要非空标题")
    if SecretRedactor.redact_text(title) != title:
        raise HypitIntegrationError("Hypit Build 标题中包含疑似凭证内容")
    attempt = get_film_attempt(attempt_id)
    existing_execution = attempt.get("execution_status", "NOT_SUBMITTED")
    if existing_execution == "BLOCKED":
        raise HypitIntegrationError("Execution 被 Runtime 配置阻塞；先完成 Runtime Resolution")
    if existing_execution != "NOT_SUBMITTED":
        if attempt.get("build", {}).get("operation"):
            return {**attempt, "creation_id": attempt["creation_id"], "idempotent_replay": True}
        raise HypitIntegrationError("该 Attempt 已离开可提交状态；请创建新的 Attempt")
    if "material_planning" in attempt or "material_gate" in attempt:
        from easel.integrations.material_layer import ProductionAuthoringIntegration

        validated_run = attempt.get("plan", {}).get("run_path") or attempt.get("authoring", {}).get("run_path")
        if not isinstance(validated_run, str):
            raise HypitIntegrationError("Material-integrated Attempt has no validated Production Run")
        attempt = ProductionAuthoringIntegration().assert_selection_current(attempt, validated_run)
    workspace = _workspace(attempt)
    source = _run_source(attempt)
    try:
        _execution_fingerprint(attempt)
    except HypitIntegrationError:
        _save_attempt(attempt_id, lambda item: _event(
            _invalidate_if_unsubmitted(item), "approval_invalidated_fingerprint_unavailable"))
        raise
    operation_id = f"op_{uuid.uuid4().hex}"
    submitted_at = _now()
    hypit_title = f"{title} [EaselOp:{operation_id}]"
    outcome: dict[str, Any] = {}

    def begin(item):
        if item.get("execution_status", "NOT_SUBMITTED") != "NOT_SUBMITTED":
            outcome["attempt"] = dict(item)
            outcome["replay"] = True
            return item
        if not item.get("cost", {}).get("approved"):
            raise HypitIntegrationError("Hypit Build 需要有效的显式成本批准")
        if item.get("plan", {}).get("status") != "ready":
            raise HypitIntegrationError("Hypit Run 尚未通过 plan")
        try:
            locked_fingerprint = _execution_fingerprint(item)
        except HypitIntegrationError:
            _invalidate_unverifiable_cost(item)
            outcome["unverifiable"] = True
            return _event(item, "approval_invalidated_fingerprint_unavailable")
        approved = item.get("cost", {}).get("approved_fingerprint", {}).get("sha256")
        planned = item.get("plan", {}).get("execution_fingerprint", {}).get("sha256")
        priced = item.get("cost", {}).get("execution_fingerprint", {}).get("sha256")
        plan_contract = item.get("plan", {})
        cost_contract = item.get("cost", {})
        try:
            plan_sha256 = _contract_sha256(plan_contract.get("result"))
            pricing_sha256 = _contract_sha256(cost_contract.get("pricing"))
        except HypitIntegrationError:
            _invalidate_unverifiable_cost(item)
            outcome["unverifiable"] = True
            return _event(item, "approval_invalidated_contract_unavailable")
        if (locked_fingerprint["sha256"] != approved or locked_fingerprint["sha256"] != planned
                or locked_fingerprint["sha256"] != priced
                or plan_sha256 != plan_contract.get("contract_sha256")
                or plan_sha256 != cost_contract.get("plan_sha256")
                or pricing_sha256 != cost_contract.get("pricing_sha256")
                or plan_sha256 != cost_contract.get("approved_plan_sha256")
                or pricing_sha256 != cost_contract.get("approved_pricing_sha256")):
            _invalidate_cost(item, locked_fingerprint)
            outcome["stale"] = True
            return _event(item, "approval_invalidated_before_build")
        operation = {
            "operation_id": operation_id,
            "execution_fingerprint": locked_fingerprint,
            "submitted_at": submitted_at,
            "run_path": source.relative_to(workspace).as_posix(),
            "display_title": title,
            "hypit_title": hypit_title,
        }
        item["execution_status"] = "SUBMITTING"
        item["build"] = {**item.get("build", {}), "operation": operation, "status": "submitting"}
        _set_summary(item)
        outcome["attempt"] = _event(item, "build_submission_started", operation_id=operation_id,
                                     execution_fingerprint=locked_fingerprint["sha256"])
        return outcome["attempt"]

    started = _save_attempt(attempt_id, begin)
    if outcome.get("replay"):
        return {**started, "idempotent_replay": True}
    if outcome.get("unverifiable"):
        raise HypitIntegrationError("Build fingerprint 无法验证；批准已失效，请修复输入后重新 validate、pricing、approve")
    if outcome.get("stale"):
        raise HypitIntegrationError("Build 输入与已批准 fingerprint 不一致；批准已失效，请重新 validate、pricing、approve")

    try:
        result = _cli(cli).build(
            workspace, source, title=hypit_title,
            runtime_profile=attempt["runtime_profile"]["path"])
    except HypitCLIError as exc:
        payload = exc.payload
        build_view = payload.get("build") if isinstance(payload, dict) else None
        build_id = build_view.get("id") if isinstance(build_view, dict) else None
        if (isinstance(payload, dict) and payload.get("format") == "hypit.cli-build@1"
                and isinstance(build_id, str) and _BUILD_ID_RE.fullmatch(build_id)):
            return _complete_build_submission(attempt_id, operation_id, payload)
        _record_operation_error(attempt_id, "build_submission", exc, status="SUBMISSION_UNCERTAIN")
        raise
    except HypitIntegrationError as exc:
        _record_operation_error(attempt_id, "build_submission", exc, status="SUBMISSION_UNCERTAIN")
        raise
    build_view = result.get("build")
    build_id = build_view.get("id") if isinstance(build_view, dict) else None
    if not isinstance(build_id, str) or not _BUILD_ID_RE.fullmatch(build_id):
        error = HypitIntegrationError("Hypit 没有返回可持久化的 Build ID")
        _record_operation_error(attempt_id, "build_submission", error, status="SUBMISSION_UNCERTAIN")
        raise error
    return _complete_build_submission(attempt_id, operation_id, result)


def _complete_build_submission(attempt_id: str, operation_id: str, result: dict[str, Any]) -> dict[str, Any]:
    result = SecretRedactor.redact(result)
    if result.get("format") != "hypit.cli-build@1":
        _record_operation_error(attempt_id, "build_submission",
                                HypitIntegrationError("Hypit Build 返回了无效响应格式"),
                                status="SUBMISSION_UNCERTAIN")
        raise HypitIntegrationError("Hypit Build 返回了无效响应格式")
    build_view = result.get("build")
    build_id = build_view.get("id") if isinstance(build_view, dict) else None
    if not isinstance(build_id, str) or not _BUILD_ID_RE.fullmatch(build_id):
        _record_operation_error(attempt_id, "build_submission", HypitIntegrationError("Hypit Build ID 无效"),
                                status="SUBMISSION_UNCERTAIN")
        raise HypitIntegrationError("Hypit Build ID 无效")
    work_state = _hypit_outcome(build_view)
    execution_status = "BUILD_FAILED" if work_state == "failed" else "BUILD_COMPLETE" if work_state == "complete" else "SUBMITTED"

    def update(item):
        operation = item.get("build", {}).get("operation", {})
        if operation.get("operation_id") != operation_id:
            raise HypitIntegrationError("Build operation 与当前 Attempt 不匹配")
        existing_build_id = item.get("build", {}).get("build_id")
        if existing_build_id and existing_build_id != build_id:
            raise HypitIntegrationError("该 Attempt 已关联其他 Hypit Build；拒绝覆盖")
        execution_status_effective = _advance_execution(
            item.get("execution_status", "SUBMITTING"), execution_status)
        item["execution_status"] = execution_status_effective
        item["build"] = {**item["build"], "build_id": build_id,
                          "status": "failed" if execution_status_effective == "BUILD_FAILED" else "complete" if execution_status_effective == "BUILD_COMPLETE" else "open",
                          "submitted": result}
        _set_summary(item)
        return _event(item, "build_submitted", build_id=build_id,
                      execution_status=execution_status_effective)

    return _save_attempt(attempt_id, update)


def _build_candidates(
    attempt: dict[str, Any],
    builds_payload: dict[str, Any],
    history_payload: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    operation = attempt.get("build", {}).get("operation") or {}
    marker = f"[EaselOp:{operation.get('operation_id')}]"
    workspace = _workspace(attempt)
    expected_run = (workspace / operation.get("run_path", "")).resolve()
    submitted = datetime.fromisoformat(operation["submitted_at"])
    raw: dict[str, dict[str, Any]] = {}
    for item in builds_payload.get("builds", []):
        if (isinstance(item, dict) and isinstance(item.get("id"), str)
                and _BUILD_ID_RE.fullmatch(item["id"])):
            raw[item["id"]] = {**item, "_source": "builds"}
    if history_payload:
        for item in history_payload.get("entries", []):
            if not isinstance(item, dict) or not isinstance(item.get("build"), str):
                continue
            current = raw.setdefault(item["build"], {**item, "id": item["build"], "_source": "history"})
            current.setdefault("history_output", item.get("output"))

    candidates = []
    for item in raw.values():
        title = str(item.get("title") or "")
        operation_marker_found = marker in title
        source = item.get("run") or item.get("source")
        if source:
            run = Path(str(source))
            actual_run = (run if run.is_absolute() else workspace / run).resolve()
            if actual_run != expected_run:
                continue
        elif not operation_marker_found:
            continue
        created = item.get("createdAt") or item.get("created_at")
        if not isinstance(created, str):
            continue
        try:
            created_at = datetime.fromisoformat(created.replace("Z", "+00:00"))
            submit_at = submitted if submitted.tzinfo else submitted.replace(tzinfo=timezone.utc)
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        delta = (created_at - submit_at).total_seconds()
        if delta < -120 or delta > 900:
            continue
        if not operation_marker_found and not source:
            continue
        evidence = ["workspace_scoped_build_list", "submit_time_window"]
        if source:
            evidence.append("run_path")
        if operation_marker_found:
            evidence.append("operation_id_in_title")
        candidates.append({
            "build_id": item["id"],
            "title": title,
            "run": str(source or expected_run),
            "created_at": created,
            "outcome": item.get("outcome"),
            "evidence": evidence,
        })
    return candidates


def reconcile_film_submission(
    attempt_id: str,
    *,
    build_id: str | None = None,
    output_name: str | None = None,
    cli: HypitCLI | None = None,
) -> dict[str, Any]:
    attempt = get_film_attempt(attempt_id)
    execution = attempt.get("execution_status", "NOT_SUBMITTED")
    if execution not in {"SUBMITTING", "SUBMISSION_UNCERTAIN"}:
        if attempt.get("build", {}).get("build_id"):
            return {"status": "already_reconciled", "attempt": attempt}
        raise HypitIntegrationError("只有 SUBMITTING/SUBMISSION_UNCERTAIN Attempt 可执行对账")
    operation = attempt.get("build", {}).get("operation")
    if not isinstance(operation, dict) or not operation.get("operation_id"):
        raise HypitIntegrationError("Attempt 缺少持久化 Build operation 证据")
    workspace = _workspace(attempt)
    client = _cli(cli)
    try:
        builds_payload = client.builds(workspace, limit=100)
        history_payload = None
        if output_name:
            run_source = _run_source(attempt)
            history_payload = client.history(workspace, output_name, source=run_source, limit=100)
    except HypitIntegrationError as exc:
        _record_operation_error(attempt_id, "reconcile", exc)
        raise
    candidates = _build_candidates(attempt, builds_payload, history_payload)
    if build_id:
        chosen = next((item for item in candidates if item["build_id"] == build_id), None)
        if chosen is None:
            raise HypitIntegrationError("指定 Build ID 不满足 workspace、Run、operation 标题和时间证据，不能认领")
    elif len(candidates) == 1:
        chosen = candidates[0]
    elif len(candidates) > 1:
        return {"status": "ambiguous", "operation_id": operation["operation_id"],
                "candidates": candidates, "claim_required": True}
    else:
        return {"status": "unresolved", "operation_id": operation["operation_id"],
                "candidates": [], "retry_allowed": False,
                "message": "未找到足够证据；禁止重新 Build，请确认 Hypit workspace 的 active/history 后再对账"}

    outcome = chosen.get("outcome")
    execution_status = ("BUILD_COMPLETE" if outcome == "complete" else
                        "BUILD_FAILED" if outcome == "failed" else
                        "CANCELLED" if outcome == "cancelled" else "SUBMITTED")

    def bind(item):
        current_operation = item.get("build", {}).get("operation") or {}
        if current_operation.get("operation_id") != operation["operation_id"]:
            raise HypitIntegrationError("Attempt operation 在对账期间发生变化")
        item["execution_status"] = execution_status
        item["build"] = {**item["build"], "build_id": chosen["build_id"],
                          "status": str(outcome or "open"), "reconciled": chosen}
        _set_summary(item)
        return _event(item, "build_reconciled", build_id=chosen["build_id"], evidence=chosen["evidence"])

    linked = _save_attempt(attempt_id, bind)
    return {"status": "reconciled", "attempt": linked, "candidate": chosen}


def refresh_film_build(attempt_id: str, *, cli: HypitCLI | None = None) -> dict[str, Any]:
    attempt = get_film_attempt(attempt_id)
    build_id = attempt.get("build", {}).get("build_id")
    if not build_id:
        raise HypitIntegrationError("Attempt 尚无 Hypit Build ID")
    try:
        status_result = _cli(cli).status(
            _workspace(attempt), build_id, runtime_profile=attempt["runtime_profile"]["path"])
    except HypitIntegrationError as exc:
        _record_operation_error(attempt_id, "status", exc)
        raise
    view = status_result.get("build")
    if not isinstance(view, dict):
        raise HypitIntegrationError("Hypit 未找到该 Build；保留当前状态以便恢复排查")
    outcome = _hypit_outcome(view)
    if outcome == "complete":
        status, build_status = "BUILD_COMPLETE", "complete"
    elif outcome == "failed":
        status, build_status = "BUILD_FAILED", "failed"
    elif outcome == "cancelled":
        status, build_status = "CANCELLED", "cancelled"
    elif isinstance(view.get("work"), dict) and view["work"].get("state") in ("working", "submitting"):
        status, build_status = "RUNNING", "open"
    else:
        status, build_status = "SUBMITTED", "open"
    def update(item):
        effective = _advance_execution(item.get("execution_status", "SUBMITTED"), status)
        item["execution_status"] = effective
        stable_build_status = {
            "BUILD_COMPLETE": "complete", "BUILD_FAILED": "failed",
            "CANCELLED": "cancelled", "CANCEL_REQUESTED": "cancel_requested",
            "RUNNING": "open", "SUBMITTED": "open",
        }.get(effective, build_status)
        item["build"] = {**item["build"], "status": stable_build_status,
                          "last_status": SecretRedactor.redact(status_result)}
        _set_summary(item)
        return _event(item, "build_status_refreshed", execution_status=effective,
                      observed_execution_status=status)
    return _save_attempt(attempt_id, update)


def inspect_film_build(attempt_id: str, *, cli: HypitCLI | None = None) -> dict[str, Any]:
    attempt = get_film_attempt(attempt_id)
    build_id = attempt.get("build", {}).get("build_id")
    if not build_id:
        raise HypitIntegrationError("Attempt 尚无 Hypit Build ID")
    try:
        return SecretRedactor.redact(_cli(cli).inspect(_workspace(attempt), build_id))
    except HypitIntegrationError as exc:
        _record_operation_error(attempt_id, "inspect", exc)
        raise


def cancel_film_build(attempt_id: str, *, cli: HypitCLI | None = None) -> dict[str, Any]:
    attempt = get_film_attempt(attempt_id)
    if attempt.get("execution_status") in {"BUILD_COMPLETE", "BUILD_FAILED", "CANCELLED"}:
        raise HypitIntegrationError("终态 Hypit Build 不能再请求取消")
    build_id = attempt.get("build", {}).get("build_id")
    if not build_id:
        raise HypitIntegrationError("Attempt 尚无 Hypit Build ID")
    try:
        result = _cli(cli).cancel(_workspace(attempt), build_id)
    except HypitIntegrationError as exc:
        _record_operation_error(attempt_id, "cancel", exc)
        raise
    requested = result.get("requested") is True

    def update(item):
        if requested:
            item["execution_status"] = "CANCEL_REQUESTED"
        item["build"] = {**item["build"],
                         "status": "cancel_requested" if requested else item["build"].get("status"),
                         "cancel": SecretRedactor.redact(result)}
        _set_summary(item)
        return _event(item, "build_cancel_requested", requested=requested)

    return _save_attempt(attempt_id, update)


def _validate_video(path: Path, *, require_audio: bool) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size <= 0:
        raise HypitIntegrationError("Hypit 导出文件为空或不存在")
    probe = shutil.which("ffprobe")
    if not probe:
        raise HypitIntegrationError("无法验收成片：系统未安装 ffprobe")
    result = subprocess.run(
        [probe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture_output=True, text=True, timeout=30, check=False,
    )
    if result.returncode:
        raise HypitIntegrationError(f"ffprobe 无法读取导出视频：{result.stderr.strip()[-800:]}")
    try:
        metadata = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise HypitIntegrationError("ffprobe 返回无效 JSON") from exc
    streams = metadata.get("streams", [])
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    duration = float(metadata.get("format", {}).get("duration") or 0)
    if video is None or int(video.get("width") or 0) <= 0 or int(video.get("height") or 0) <= 0:
        raise HypitIntegrationError("导出文件没有有效视频轨")
    if duration <= 0:
        raise HypitIntegrationError("导出文件没有有效时长")
    if require_audio and audio is None:
        raise HypitIntegrationError("Handoff 要求音轨，但导出文件没有音频轨")
    decoder = shutil.which("ffmpeg")
    if not decoder:
        raise HypitIntegrationError("无法完成成片解码校验：系统未安装 ffmpeg")
    decoded = subprocess.run(
        [decoder, "-v", "error", "-i", str(path), "-f", "null", "-"],
        capture_output=True, text=True, timeout=120, check=False,
    )
    if decoded.returncode:
        raise HypitIntegrationError(f"导出视频无法完整解码：{decoded.stderr.strip()[-800:]}")
    return {
        "duration_seconds": duration,
        "width": int(video["width"]),
        "height": int(video["height"]),
        "audio_present": audio is not None,
        "size_bytes": path.stat().st_size,
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def export_film_output(
    attempt_id: str,
    output_name: str,
    *,
    cli: HypitCLI | None = None,
) -> dict[str, Any]:
    attempt = get_film_attempt(attempt_id)
    if attempt.get("execution_status") != "BUILD_COMPLETE":
        raise HypitIntegrationError("只有 Hypit Build complete 后才能导出")
    if output_name in attempt.get("outputs", {}):
        raise HypitIntegrationError("该 Hypit output 已导出；为保留审片绑定，不覆盖已有产物")
    attribution = _validated_attribution_metadata(attempt)
    build_id = attempt["build"]["build_id"]
    creation_id = attempt["creation_id"]
    final_path = _output_file(creation_id, attempt_id, output_name,
                              primary=not bool(attempt.get("outputs")))
    output_dir = final_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    if final_path.exists():
        raise HypitIntegrationError("该 Attempt 已有 final.mp4；为保留历史，不覆盖已有产物")
    staged = output_dir / f".final-{uuid.uuid4().hex}.part.mp4"
    committed = False
    try:
        response = _cli(cli).get(_workspace(attempt), build_id, output_name, staged)
        metadata = _validate_video(
            staged, require_audio=bool(
                attempt.get("production_request", {}).get("audio_required", False)
                or attempt.get("material_audio_policy", {}).get("requires_audio", False)
            ))
        request = attempt.get("production_request", {})
        bounds = request.get("preferred_duration_seconds", {})
        duration = metadata["duration_seconds"]
        if isinstance(bounds, dict):
            minimum, maximum = bounds.get("min"), bounds.get("max")
            if minimum is not None and duration < float(minimum) - 0.5:
                raise HypitIntegrationError("导出视频短于 Handoff 要求的最短时长")
            if maximum is not None and duration > float(maximum) + 0.5:
                raise HypitIntegrationError("导出视频长于 Handoff 要求的最长时长")
        orientation = request.get("orientation")
        if orientation == "9:16" and abs(metadata["width"] / metadata["height"] - 9 / 16) > 0.035:
            raise HypitIntegrationError("导出视频画幅不是要求的 9:16")
        digest = _sha256_file(staged)
        try:
            os.link(staged, final_path)
        except FileExistsError as exc:
            raise HypitIntegrationError("该 Attempt 已有 final.mp4；为保留历史，不覆盖已有产物") from exc
        committed = True
        staged.unlink()
    except BaseException as exc:
        staged.unlink(missing_ok=True)
        if committed:
            final_path.unlink(missing_ok=True)
        if isinstance(exc, Exception):
            _record_operation_error(attempt_id, "export", exc)
        raise

    relative = final_path.relative_to(creation.OUTPUTS_DIR).as_posix()
    exported = {
        "result_output": output_name,
        "path": relative,
        "sha256": "sha256:" + digest,
        "metadata": metadata,
        "attribution": attribution,
        "hypit_get": response,
        "exported_at": _now(),
    }
    exported["technical_qc"] = {
        "status": "pass", "notes": [], "artifact": relative,
        "output_name": output_name, "sha256": exported["sha256"],
    }
    try:
        def register(item):
            if item.get("execution_status") != "BUILD_COMPLETE":
                raise HypitIntegrationError("Build 状态已变化，不能登记导出产物")
            if output_name in item.get("outputs", {}):
                raise HypitIntegrationError("Hypit output 已被并发导出；保留已有记录")
            item["outputs"] = {**item.get("outputs", {}), output_name: exported}
            item["export_status"] = "EXPORTED"
            item["review"] = {**item["review"], "technical": exported["technical_qc"]}
            _set_summary(item)
            return _event(item, "output_exported", output=output_name, path=relative)

        return _save_attempt(attempt_id, register)
    except Exception:
        final_path.unlink(missing_ok=True)
        raise


def record_film_review(attempt_id: str, review: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(review, dict):
        raise HypitIntegrationError("Review 必须是 JSON 对象")
    for key in ("truth", "style"):
        section = review.get(key)
        if not isinstance(section, dict) or section.get("status") not in _REVIEW_STATES:
            raise HypitIntegrationError(f"Review {key}.status 无效")
    human = review.get("human")
    if not isinstance(human, dict) or human.get("status") not in {"pending", "approved", "rejected"}:
        raise HypitIntegrationError("Review human.status 无效")
    attempt = get_film_attempt(attempt_id)
    output_name = review.get("output_name") or review.get("outputName")
    output_hash = review.get("sha256")
    output = attempt.get("outputs", {}).get(output_name) if isinstance(output_name, str) else None
    if not isinstance(output, dict):
        raise HypitIntegrationError("Review 必须绑定一个已导出的 output_name")
    if output_hash != output.get("sha256"):
        raise HypitIntegrationError("Review sha256 与指定 output 不匹配")
    media_path = _output_path(attempt, output)
    if _file_sha256(media_path) != output_hash:
        raise HypitIntegrationError("Review 绑定的成片内容已变化")
    technical = output.get("technical_qc", {})
    if (technical.get("status") != "pass" or technical.get("output_name") != output_name
            or technical.get("sha256") != output_hash):
        raise HypitIntegrationError("该 output 缺少与自身名称和 sha256 绑定的 Technical QC")
    normalized = {
        "technical": technical,
        "truth": review["truth"],
        "style": review["style"],
        "human": human,
        "feedback": list(review.get("feedback", [])),
        "binding": {"output_name": output_name, "sha256": output_hash},
        "attribution": output.get("attribution", []),
    }
    ready = all(normalized[name]["status"] == "pass" for name in ("technical", "truth", "style")) \
        and human["status"] == "approved"
    def update(work):
        item = _attempt_in_creation(work, attempt_id)
        if item is None:
            raise HypitIntegrationError("FilmBuildAttempt 不存在")
        current_output = item.get("outputs", {}).get(output_name)
        if (not isinstance(current_output, dict) or current_output.get("sha256") != output_hash
                or current_output.get("technical_qc") != technical):
            raise HypitIntegrationError("Review 对应产物在审片期间发生变化")
        previous_binding = item.get("review", {}).get("binding")
        binding_changed = previous_binding != normalized["binding"]
        item["review"] = normalized
        item["review_status"] = "APPROVED" if ready else "PENDING"
        item["status"] = "REVIEW_APPROVED" if ready else "REVIEW_PENDING"
        item.setdefault("history", []).append({
            "at": _now(), "event": "review_recorded", "ready": ready,
            "output_name": output_name, "sha256": output_hash,
        })
        item["updated_at"] = _now()
        if (not ready or binding_changed) and work.get("selected_attempt_id") == attempt_id:
            work.pop("selected_attempt_id", None)
            work.pop("selected_output_name", None)
            work["publication"] = {
                "status": "REVIEW_REQUIRED", "publish_automatically": False,
                "invalidated_at": _now(),
            }
            item["selected"] = False
        return {"creation_id": work["id"], **item}

    with creation.edit_creation(attempt["creation_id"]) as work:
        saved = update(work)
    return saved


def select_film_attempt(creation_id: str, attempt_id: str, output_name: str) -> dict[str, Any]:
    with creation.edit_creation(creation_id) as work:
        attempt = _attempt_in_creation(work, attempt_id)
        if attempt is None:
            raise HypitIntegrationError("该 Attempt 不属于此 Creation")
        selected_output = attempt.get("outputs", {}).get(output_name)
        binding = attempt.get("review", {}).get("binding", {})
        review = attempt.get("review", {})
        technical = review.get("technical", {})
        if (attempt.get("review_status") != "APPROVED"
                or not isinstance(selected_output, dict)
                or binding.get("output_name") != output_name
                or binding.get("sha256") != selected_output.get("sha256")
                or technical.get("status") != "pass"
                or technical.get("output_name") != output_name
                or technical.get("sha256") != selected_output.get("sha256")
                or review.get("truth", {}).get("status") != "pass"
                or review.get("style", {}).get("status") != "pass"
                or review.get("human", {}).get("status") != "approved"
                or review.get("attribution", []) != selected_output.get("attribution", [])):
            raise HypitIntegrationError("所选 output 未通过与其名称和 sha256 绑定的完整审片")
        media_path = _output_path(attempt, selected_output)
        if _file_sha256(media_path) != binding["sha256"]:
            raise HypitIntegrationError("所选成片与已批准 Review 的 sha256 不一致")
        for item in work.get("hypit_attempts", []):
            item["selected"] = item.get("attempt_id") == attempt_id
        work["selected_attempt_id"] = attempt_id
        work["selected_output_name"] = output_name
        work["publication"] = {
            "status": "READY_FOR_MANUAL_PUBLISH",
            "media": selected_output.get("path"),
            "output_name": output_name,
            "sha256": selected_output.get("sha256"),
            "attribution": selected_output.get("attribution", []),
            "attribution_status": (
                "PUBLISH_METADATA_READY" if selected_output.get("attribution") else "NOT_REQUIRED"
            ),
            "selected_at": _now(),
            "publish_automatically": False,
        }
        # Formal Selection is the registration event for the Content Library.
        # The Attempt output stays in place for execution and audit history.
        from easel.content_assets import register_selected_output
        work["content_asset"] = register_selected_output(work, attempt_id, output_name)
        work.setdefault("history", []).append({
            "at": _now(), "event": "hypit_attempt_selected", "attempt_id": attempt_id,
            "output_name": output_name, "sha256": binding["sha256"],
        })
    return creation.get_creation(creation_id)


def _validated_attribution_metadata(attempt: dict[str, Any]) -> list[dict[str, Any]]:
    """Return only attribution facts produced by the current material selection check."""
    validation = attempt.get("production_authoring", {}).get("selection_validation", {})
    selected = validation.get("assets", []) if isinstance(validation, dict) else []
    if not isinstance(selected, list) or any(not isinstance(item, dict) for item in selected):
        raise HypitIntegrationError("当前 Production selected Asset evidence 无效")
    selected_ids = {item.get("asset_id") for item in selected if isinstance(item, dict)}
    entries = validation.get("attributions", []) if isinstance(validation, dict) else []
    if not isinstance(entries, list) or any(not isinstance(item, dict) for item in entries):
        raise HypitIntegrationError("当前 Production selection 的 attribution metadata 无效")
    if attempt.get("material_planning", {}).get("status") != "PLANNING_READY":
        # Preserve legacy Hypit-only attempts; formal Material Attempts are
        # checked against their persisted Bundle below.
        return []
    from easel.materials.application.rights import RightsService
    from easel.materials.store import AttemptMaterialStore

    try:
        bundle = AttemptMaterialStore(_workspace(attempt)).read_bundle()
    except Exception as exc:
        raise HypitIntegrationError("Material Bundle attribution facts are unavailable") from exc
    bundle_assets = {asset.asset_id: asset for asset in bundle.assets}
    by_id: dict[str, dict[str, Any]] = {}
    for item in entries:
        if isinstance(item, dict) and isinstance(item.get("asset_id"), str):
            if item["asset_id"] in by_id:
                raise HypitIntegrationError("attribution Asset identity is duplicated")
            by_id[item["asset_id"]] = item
    clean: list[dict[str, Any]] = []
    seen: set[str] = set()
    for asset_id in sorted(selected_ids):
        asset = bundle_assets.get(asset_id)
        if asset is None:
            raise HypitIntegrationError("selected Asset is absent from the current Material Bundle")
        required = (
            asset.rights.attribution_required
            or asset.rights.status.value == "ATTRIBUTION_REQUIRED"
            or "attribution_required" in asset.rights.usage_constraints
        )
        if not required:
            continue
        condition = RightsService.attribution_condition_for(asset)
        if condition is None:
            raise HypitIntegrationError("required Asset attribution facts are missing at Export")
        item = by_id.get(asset_id)
        expected = {
            "asset_id": asset_id, "creator": asset.source.creator,
            "credit_text": condition.credit_text, "source_page": condition.source_page,
            "destination": condition.destination, "rights_status": asset.rights.status.value,
            "evidence_references": [evidence.reference for evidence in asset.rights.evidence],
        }
        if item != expected:
            raise HypitIntegrationError("Export attribution no longer matches selected MaterialAsset Rights facts")
        if asset_id in seen:
            raise HypitIntegrationError("selected attribution Asset identity is duplicated")
        seen.add(asset_id)
        clean.append(expected)
    if set(by_id) != seen:
        raise HypitIntegrationError("attribution metadata contains an unselected or no-longer-required Asset")
    return clean
