"""Persistent work lifecycle for a Director-led Easel creation.

This module does not generate media or make editorial decisions.  It records
one work's state and exposes the narrow Creative Mode contract required by
each production concern, so the existing Director and Skills can collaborate
without turning a chat session into the source of truth.
"""

from __future__ import annotations

import argparse
import hashlib
from contextlib import contextmanager
import json
import os
import re
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if os.name == "nt":
    import msvcrt
else:
    import fcntl

from easel.creative_mode import (
    creative_mode_stage_context,
    creative_mode_stage_names,
    load_creative_mode,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
CREATIONS_DIR = OUTPUTS_DIR / "_creations"

STAGES = ("content_core", "director_plan", "storyboard", "assets", "assemble", "qc")
STAGE_STATUSES = ("pending", "in_progress", "completed", "failed", "blocked", "skipped")
CREATION_STATUSES = ("draft", "planning", "producing", "ready", "not_ready", "failed", "paused")
_CONTEXT_PREREQUISITES = {
    "director_plan": "content_core",
    "storyboard": "director_plan",
    "image": "storyboard",
    "video": "storyboard",
    "tts": "storyboard",
    "audio": "storyboard",
    "assemble": "assets",
    "qc": "assemble",
}


class CreationError(ValueError):
    """Raised when lifecycle input cannot describe a valid work state."""


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _creation_dir(creation_id: str) -> Path:
    if not creation_id.startswith("cr_") or len(creation_id) != 35:
        raise CreationError("作品 ID 非法")
    try:
        uuid.UUID(hex=creation_id[3:])
    except ValueError as exc:
        raise CreationError("作品 ID 非法") from exc
    return CREATIONS_DIR / creation_id


def _creation_path(creation_id: str) -> Path:
    return _creation_dir(creation_id) / "creation.json"


def _atomic_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _load(creation_id: str) -> dict[str, Any]:
    path = _creation_path(creation_id)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CreationError("作品不存在") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise CreationError("作品状态文件损坏") from exc
    if data.get("id") != creation_id or not isinstance(data.get("stages"), dict):
        raise CreationError("作品状态文件无效")
    return data


def _save(data: dict[str, Any]) -> dict[str, Any]:
    if data.get("route") == "hypit_video":
        previous_status = data.get("status")
        data["status"] = _derive_status(data)
        if previous_status != data["status"]:
            data.setdefault("history", []).append({
                "at": _now(),
                "event": "video_lifecycle_status_projected",
                "from": previous_status,
                "to": data["status"],
            })
    data["updated_at"] = _now()
    _atomic_write(_creation_path(str(data["id"])), data)
    return data


@contextmanager
def edit_creation(creation_id: str):
    """Serialize one Creation read-modify-write across threads and processes."""
    path = _creation_path(creation_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(".lock")
    with lock_path.open("a+b") as lock:
        if os.name == "nt":
            lock.seek(0, os.SEEK_END)
            if lock.tell() == 0:
                lock.write(b"0")
                lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
        else:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            data = _load(creation_id)
            yield data
            _save(data)
        finally:
            if os.name == "nt":
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _safe_artifact_path(value: str) -> str:
    candidate = Path(value)
    if not value or candidate.is_absolute() or ".." in candidate.parts:
        raise CreationError("产物路径必须是 outputs/ 下的相对路径")
    full = (OUTPUTS_DIR / candidate).resolve()
    root = OUTPUTS_DIR.resolve()
    if root not in full.parents or not full.is_file():
        raise CreationError(f"产物不存在或不在 outputs/ 下：{value}")
    return candidate.as_posix()


def _derive_status(data: dict[str, Any]) -> str:
    if data.get("route") == "hypit_video":
        return _derive_hypit_video_status(data)
    stages = data["stages"]
    if any(item.get("status") == "failed" for item in stages.values()):
        return "failed"
    if any(item.get("status") == "blocked" for item in stages.values()):
        return "paused"
    qc = stages["qc"]
    if qc.get("status") == "completed":
        if qc.get("decision") == "not_ready":
            return "not_ready"
        required = ("content_core", "director_plan", "storyboard", "assets", "assemble")
        if all(stages[name].get("status") == "completed" for name in required):
            return "ready"
    if any(stages[name].get("status") in ("in_progress", "completed")
           for name in ("assets", "assemble")):
        return "producing"
    if any(item.get("status") in ("in_progress", "completed") for item in stages.values()):
        return "planning"
    return "draft"


def _derive_hypit_video_status(data: dict[str, Any]) -> str:
    """Project the official video lifecycle onto the Creation summary.

    Detailed execution state remains on each Hypit Attempt.  Creation.status
    is only the coarse product summary and becomes ready only after an
    approved Attempt output is selected.
    """
    preparation = data.get("preparation") or {}
    preparation_status = preparation.get("status")
    attempts = data.get("hypit_attempts") or []
    selected_id = data.get("selected_attempt_id")
    selected = next((item for item in attempts if item.get("attempt_id") == selected_id), None)
    if (selected is not None
            and selected.get("selected") is True
            and selected.get("review_status") == "APPROVED"
            and data.get("publication", {}).get("status") == "READY_FOR_MANUAL_PUBLISH"):
        return "ready"

    current = next((item for item in attempts if item.get("selected") is True), None)
    if current is None and attempts:
        current = max(attempts, key=lambda item: int(item.get("attempt_number", 0)))
    if current is not None:
        execution = current.get("execution_status")
        authoring = current.get("authoring_status")
        if execution == "BUILD_FAILED" or authoring in {"AUTHORING_FAILED", "PLAN_FAILED"}:
            return "failed"
        if current.get("material_gate", {}).get("status") == "MATERIAL_NOT_READY":
            return "not_ready"
        if execution == "BLOCKED" or current.get("runtime_status") in {"NOT_CONFIGURED", "INVALID"}:
            return "paused"
        if (execution in {"SUBMITTING", "SUBMISSION_UNCERTAIN", "SUBMITTED", "RUNNING",
                          "BUILD_COMPLETE", "CANCEL_REQUESTED", "CANCELLED"}
                or current.get("material_gate", {}).get("status") == "MATERIAL_READY"):
            return "producing"

    # Preparation is a snapshot of an earlier stage. A resumed Attempt may
    # progress past it without rewriting that historical summary.
    if preparation_status in {"FAILED", "MATERIAL_FAILED"}:
        return "failed"
    if preparation_status == "MATERIAL_NOT_READY":
        return "not_ready"
    if preparation_status in {"BLOCKED_RUNTIME_NOT_CONFIGURED", "BLOCKED_RUNTIME_INVALID"}:
        return "paused"

    if preparation_status in {
        "PREPARING", "CONTENT_READY", "HANDOFF_READY", "PRODUCTION_PREPARED",
        "READY_FOR_EXTERNAL_AUTHORING", "MATERIAL_READY",
    }:
        return "producing" if preparation_status in {
            "READY_FOR_EXTERNAL_AUTHORING", "MATERIAL_READY",
        } else "planning"
    if data.get("chat_workflow", {}).get("proposal_status") == "CONFIRMED":
        return "planning"
    return "draft"


def create_creation(idea: str, *, profile: str | None = None,
                    creative_mode: str | None = None,
                    route: str | None = None,
                    origin: dict[str, str] | None = None) -> dict[str, Any]:
    """Create a persistent work record without invoking the Director or media."""
    idea = idea.strip()
    if not idea:
        raise CreationError("作品需要一个想法或主题")
    if len(idea) > 4000:
        raise CreationError("想法不能超过 4000 字")

    mode_version: str | None = None
    if creative_mode:
        mode = load_creative_mode(creative_mode)
        if mode is None:
            raise CreationError("Creative Mode 不存在或不可用")
        mode_version = str(mode["version"])

    if origin is not None:
        if (origin.get("type") != "chat"
                or not re.fullmatch(r"[0-9a-f]{64}", origin.get("session_hash", ""))
                or (origin.get("initial_turn_hash")
                    and not re.fullmatch(r"[0-9a-f]{64}", origin["initial_turn_hash"]))):
            raise CreationError("作品来源信息无效")

    creation_id = f"cr_{uuid.uuid4().hex}"
    workspace = f"_creations/{creation_id}"
    now = _now()
    data: dict[str, Any] = {
        "schema_version": 1,
        "id": creation_id,
        "idea": idea,
        "profile": profile or None,
        "creative_mode": creative_mode or None,
        "creative_mode_version": mode_version,
        "route": route or None,
        **({"origin": dict(origin)} if origin else {}),
        **({"preparation": {"status": "CREATED"}} if route == "hypit_video" else {}),
        **({"chat_workflow": {
            "phase": "PROPOSAL",
            "proposal_status": "DISCUSSING",
            "confirmed_at": None,
            "confirmed_by_turn": None,
        }} if route == "hypit_video" and origin and origin.get("type") == "chat" else {}),
        "workspace": workspace,
        "status": "draft",
        "created_at": now,
        "updated_at": now,
        "stages": {name: {"status": "pending", "artifacts": []} for name in STAGES},
        "history": [{"at": now, "event": "created", "summary": "作品已创建"}],
    }
    _atomic_write(_creation_path(creation_id), data)
    return data


def ensure_chat_proposal_state(creation_id: str) -> dict[str, Any]:
    """Initialize the explicit proposal gate for an existing chat-bound film work."""
    with edit_creation(creation_id) as data:
        if data.get("route") != "hypit_video" or data.get("origin", {}).get("type") != "chat":
            raise CreationError("当前作品不是聊天创建的视频作品")
        data.setdefault("chat_workflow", {
            "phase": "PROPOSAL",
            "proposal_status": "DISCUSSING",
            "confirmed_at": None,
            "confirmed_by_turn": None,
        })
    return get_creation(creation_id)


def mark_chat_proposal_ready(creation_id: str) -> dict[str, Any]:
    """Make the explicit confirmation action available after a completed chat turn."""
    with edit_creation(creation_id) as data:
        if data.get("route") != "hypit_video" or data.get("origin", {}).get("type") != "chat":
            raise CreationError("当前作品不是聊天创建的视频作品")
        workflow = dict(data.get("chat_workflow") or {})
        if not workflow.get("confirmed_at"):
            workflow.update({"phase": "PROPOSAL", "proposal_status": "READY_FOR_CONFIRMATION"})
            data["chat_workflow"] = workflow
    return get_creation(creation_id)


def confirm_chat_proposal(
    creation_id: str,
    turn_id: str | None,
    *,
    proposal_sha256: str | None = None,
    production_specs: dict[str, Any] | None = None,
    delivery_proposal: str | None = None,
) -> dict[str, Any]:
    """Persist a user-issued production confirmation; natural-language text cannot call this implicitly."""
    with edit_creation(creation_id) as data:
        if data.get("route") != "hypit_video" or data.get("origin", {}).get("type") != "chat":
            raise CreationError("当前作品不是聊天创建的视频作品")
        workflow = dict(data.get("chat_workflow") or {})
        if not workflow.get("confirmed_at"):
            if workflow.get("proposal_status") != "READY_FOR_CONFIRMATION":
                raise CreationError("Easel 尚未完成创作方案回复，不能开始制作")
            if proposal_sha256 is not None and not re.fullmatch(r"[0-9a-f]{64}", proposal_sha256):
                raise CreationError("确认方案摘要无效")
            workflow.update({
                "phase": "PRODUCTION_CONFIRMED",
                "proposal_status": "CONFIRMED",
                "confirmed_at": _now(),
                "confirmed_by_turn": turn_id or "explicit-action",
                **({"proposal_sha256": proposal_sha256} if proposal_sha256 else {}),
                **({"production_specs": production_specs} if production_specs is not None else {}),
            })
            data["chat_workflow"] = workflow
            if delivery_proposal is not None:
                from easel.integrations.hypit.secrets import SecretRedactor

                if (not proposal_sha256 or len(delivery_proposal) > 32_000
                        or hashlib.sha256(delivery_proposal.encode("utf-8")).hexdigest() != proposal_sha256
                        or SecretRedactor.contains_secret(delivery_proposal)):
                    raise CreationError("自主委托与确认方案不一致或含疑似 Secret")
                # Enrollment and confirmation are one write. Old confirmations
                # never acquire a delivery record through a replay or restart.
                data["delivery"] = {
                    "schema": "easel-creation-delivery@1",
                    "proposal": delivery_proposal,
                    "proposal_sha256": proposal_sha256,
                    "confirmed_at": workflow["confirmed_at"],
                    "confirmed_by_turn": workflow["confirmed_by_turn"],
                    "authorization": {"no_provider_charge_build": True,
                                      "paid_operations": "explicit_approval_required"},
                    "status": "pending", "failures": {},
                }
        elif (proposal_sha256 is not None
              and workflow.get("proposal_sha256") != proposal_sha256):
            raise CreationError("本 Creation 已绑定另一份确认方案；不能静默替换冻结输入")
    return get_creation(creation_id)


def require_chat_proposal_confirmed(work: dict[str, Any]) -> None:
    """Hard gate for chat-created Hypit work before any production artifacts are created."""
    if work.get("route") == "hypit_video" and work.get("origin", {}).get("type") == "chat":
        workflow = work.get("chat_workflow") or {}
        if (workflow.get("proposal_status") != "CONFIRMED"
                or not workflow.get("confirmed_at")):
            raise CreationError("用户尚未明确确认创作方案；禁止进入 Hypit 制作")


def get_creation(creation_id: str) -> dict[str, Any]:
    """Load one work record."""
    data = _load(creation_id)
    if data.get("route") == "hypit_video":
        data = {**data, "status": _derive_status(data)}
    return data


def list_creations(limit: int = 50) -> list[dict[str, Any]]:
    """List newest creation records without walking media project directories."""
    if not CREATIONS_DIR.is_dir():
        return []
    records: list[dict[str, Any]] = []
    for directory in CREATIONS_DIR.iterdir():
        if not directory.is_dir():
            continue
        try:
            data = _load(directory.name)
            if data.get("route") == "hypit_video":
                data = {**data, "status": _derive_status(data)}
            records.append(data)
        except CreationError:
            continue
    records.sort(key=lambda item: str(item.get("updated_at", "")), reverse=True)
    return records[:max(1, min(limit, 200))]


def record_stage(creation_id: str, stage: str, status: str, *,
                 artifacts: list[str] | None = None, summary: str = "",
                 error: str = "", decision: str | None = None) -> dict[str, Any]:
    """Persist one stage result and verify completed artifacts really exist."""
    if stage not in STAGES:
        raise CreationError(f"未知作品阶段：{stage}")
    if status not in STAGE_STATUSES:
        raise CreationError(f"未知阶段状态：{status}")
    if decision not in (None, "ready", "not_ready"):
        raise CreationError("QC 决策只能是 ready 或 not_ready")
    if decision is not None and stage != "qc":
        raise CreationError("只有 qc 阶段可以写入最终决策")

    clean_artifacts = [_safe_artifact_path(item) for item in (artifacts or [])]
    with edit_creation(creation_id) as data:
        if status == "completed" and stage in ("content_core", "director_plan", "storyboard", "assets", "assemble") and not clean_artifacts:
            raise CreationError(f"{stage} 完成时必须登记至少一个真实产物")
        if stage == "qc" and status == "completed" and decision is None:
            raise CreationError("qc 完成时必须明确决定 ready 或 not_ready")
        if stage == "qc" and status == "completed" and decision == "ready":
            if data["stages"]["assemble"].get("status") != "completed":
                raise CreationError("READY 前必须完成 assemble 并登记最终成片")

        now = _now()
        previous = data["stages"][stage]
        current = {
            "status": status,
            "artifacts": clean_artifacts,
            "summary": summary.strip(),
            "error": error.strip(),
            "updated_at": now,
        }
        if status == "in_progress":
            current["started_at"] = previous.get("started_at") or now
        if status in ("completed", "failed", "blocked", "skipped"):
            current["finished_at"] = now
        if decision is not None:
            current["decision"] = decision
        data["stages"][stage] = current
        data["status"] = _derive_status(data)
        data["history"].append({
            "at": now,
            "event": "stage_recorded",
            "stage": stage,
            "status": status,
            "summary": summary.strip() or error.strip(),
        })
    return data


def stage_context(creation_id: str, target: str) -> str:
    """Return a stage-specific Mode context after enforcing upstream state."""
    data = _load(creation_id)
    if target not in creative_mode_stage_names():
        allowed = ", ".join(creative_mode_stage_names())
        raise CreationError(f"未知 Mode 生产阶段 {target!r}；可用：{allowed}")
    required = _CONTEXT_PREREQUISITES.get(target)
    if required and data["stages"][required].get("status") != "completed":
        raise CreationError(f"{target} 前需要先完成 {required}")
    mode_id = data.get("creative_mode")
    if not mode_id:
        raise CreationError("本作品没有绑定 Creative Mode")
    context = creative_mode_stage_context(mode_id, target)
    if not context:
        raise CreationError("无法读取 Creative Mode 阶段合同")
    return (
        f"〔作品状态：{creation_id} · {target}〕\n"
        f"工作区：outputs/{data['workspace']}/\n\n{context}"
    )


def _print(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Easel 作品生命周期状态")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="创建作品状态，不调用模型或媒体")
    create.add_argument("--idea", required=True)
    create.add_argument("--profile")
    create.add_argument("--creative-mode")
    create.add_argument("--route")

    show = sub.add_parser("show", help="读取一个作品状态")
    show.add_argument("--id", required=True)
    listing = sub.add_parser("list", help="列出最近作品")
    listing.add_argument("--limit", type=int, default=50)

    record = sub.add_parser("record", help="登记一个阶段及其真实产物")
    record.add_argument("--id", required=True)
    record.add_argument("--stage", required=True, choices=STAGES)
    record.add_argument("--status", required=True, choices=STAGE_STATUSES)
    record.add_argument("--artifact", action="append", default=[])
    record.add_argument("--summary", default="")
    record.add_argument("--error", default="")
    record.add_argument("--decision", choices=("ready", "not_ready"))

    context = sub.add_parser("context", help="读取一个生产环节的 Mode 合同")
    context.add_argument("--id", required=True)
    context.add_argument("--stage", required=True, choices=creative_mode_stage_names())

    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            _print(create_creation(args.idea, profile=args.profile,
                                   creative_mode=args.creative_mode, route=args.route))
        elif args.command == "show":
            _print(get_creation(args.id))
        elif args.command == "list":
            _print(list_creations(args.limit))
        elif args.command == "record":
            _print(record_stage(args.id, args.stage, args.status,
                                artifacts=args.artifact, summary=args.summary,
                                error=args.error, decision=args.decision))
        else:
            print(stage_context(args.id, args.stage))
    except CreationError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
