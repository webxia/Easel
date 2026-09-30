"""Immutable Easel-to-Hypit handoff packages."""

from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import uuid

from easel import creation
from easel.creative_mode import load_creative_mode
from easel.integrations.hypit.errors import HypitIntegrationError
from easel.integrations.hypit.secrets import SecretRedactor

_MODE_FILES = (
    "mode.json",
    "director-treatment.md",
    "visual-bible.md",
    "audio-bible.md",
    "editing-bible.md",
    "qc-rubric.md",
)
_ID_RE = re.compile(r"^cr_[0-9a-f]{32}$")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _write_json(path: Path, value: Any) -> str:
    payload = _json_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(payload)
    return _sha256(payload)


def _reject_secret_fields(value: Any, path: str = "root") -> None:
    if SecretRedactor.contains_secret(value):
        raise HypitIntegrationError(f"Handoff 检测到疑似凭证或凭证字段：{path}")


def _set_readonly_tree(root: Path) -> None:
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        path.chmod(0o555 if path.is_dir() else 0o444)
    root.chmod(0o555)


def load_frozen_creative_mode(attempt: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Read execution preferences from this Attempt's verified snapshot only."""
    package = Path(attempt["workspace"]["path"]) / "handoff"
    manifest, _ = verify_handoff_directory(package, attempt["handoff"]["hash"])
    if (manifest.get("creation_id") != attempt["creation_id"]
            or manifest.get("handoff_id") != attempt["handoff"]["handoff_id"]):
        raise HypitIntegrationError("Creative Mode 快照不属于当前作品")
    ref = manifest["creative_mode"]
    mode = json.loads((package / ref["path"] / "mode.json").read_text(encoding="utf-8"))
    style = mode.get("visual_material_style")
    if style is not None and (not isinstance(style, str) or not style.strip() or len(style) > 200):
        raise HypitIntegrationError("Creative Mode 视觉素材偏好必须为非空短语")
    return mode, ref["hash"]


def verify_handoff_directory(package: Path, expected_hash: str) -> tuple[dict[str, Any], str]:
    """Verify an Easel handoff directory without trusting manifest paths."""
    package = package.resolve()
    manifest_path = package / "handoff.json"
    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes)
    except (OSError, json.JSONDecodeError) as exc:
        raise HypitIntegrationError("Handoff 文件缺失或损坏") from exc
    actual_handoff_hash = _sha256(manifest_bytes)
    if actual_handoff_hash != expected_hash:
        raise HypitIntegrationError("Handoff manifest hash 不匹配")

    expected_files = {"handoff.json"}
    refs = [
        manifest.get("creator_context", {}),
        *manifest.get("content", {}).values(),
        manifest.get("references", {}),
    ]
    for item in refs:
        if not isinstance(item, dict):
            raise HypitIntegrationError("Handoff 文件索引格式无效")
        relative = Path(item.get("path", ""))
        if not relative.parts or relative.is_absolute() or ".." in relative.parts:
            raise HypitIntegrationError("Handoff 中包含非法文件路径")
        source = (package / relative).resolve()
        if package not in source.parents or not source.is_file():
            raise HypitIntegrationError(f"Handoff 文件缺失或越界：{relative}")
        if _sha256(source.read_bytes()) != item.get("hash"):
            raise HypitIntegrationError(f"Handoff 文件 hash 不匹配：{relative}")
        expected_files.add(relative.as_posix())

    mode = manifest.get("creative_mode", {})
    mode_dir_relative = Path(mode.get("path", ""))
    if not mode_dir_relative.parts or mode_dir_relative.is_absolute() or ".." in mode_dir_relative.parts:
        raise HypitIntegrationError("Creative Mode snapshot 路径非法")
    mode_dir = (package / mode_dir_relative).resolve()
    if package not in mode_dir.parents or not mode_dir.is_dir():
        raise HypitIntegrationError("Creative Mode snapshot 目录不存在或越界")
    mode_entries = mode.get("files", [])
    for item in mode_entries:
        if not isinstance(item, dict):
            raise HypitIntegrationError("Creative Mode 文件索引格式无效")
        relative = Path(item.get("path", ""))
        if not relative.parts or relative.is_absolute() or ".." in relative.parts:
            raise HypitIntegrationError("Creative Mode snapshot 文件路径非法")
        source = (mode_dir / relative).resolve()
        if mode_dir not in source.parents or not source.is_file():
            raise HypitIntegrationError(f"Creative Mode snapshot 文件缺失或越界：{relative}")
        if _sha256(source.read_bytes()) != item.get("hash"):
            raise HypitIntegrationError(f"Creative Mode snapshot hash 不匹配：{relative}")
        expected_files.add((mode_dir_relative / relative).as_posix())
    mode_hash = _sha256(_json_bytes(mode_entries))
    if mode_hash != mode.get("hash"):
        raise HypitIntegrationError("Creative Mode snapshot 总 hash 不匹配")
    for candidate in package.rglob("*"):
        if candidate.is_symlink():
            raise HypitIntegrationError("Handoff 不允许 symlink")
        if candidate.is_file() and candidate.relative_to(package).as_posix() not in expected_files:
            raise HypitIntegrationError("Handoff 包含未纳入 hash 的额外文件")
    return manifest, actual_handoff_hash


def _validate_creator_context(value: dict[str, Any]) -> dict[str, Any]:
    _reject_secret_fields(value)
    allowed = {"schema", "identity", "audience", "voice", "relevant_context", "privacy_policy"}
    unknown = set(value) - allowed
    if unknown:
        raise HypitIntegrationError(f"Creator Context 包含未允许字段：{', '.join(sorted(unknown))}")
    if value.get("schema") != "easel-creator-context@1":
        raise HypitIntegrationError("Creator Context schema 必须是 easel-creator-context@1")
    identity = value.get("identity")
    if not isinstance(identity, dict) or not isinstance(identity.get("public_description"), str):
        raise HypitIntegrationError("Creator Context 缺少 identity.public_description")
    if not isinstance(value.get("audience"), str):
        raise HypitIntegrationError("Creator Context 缺少 audience")
    voice = value.get("voice", {})
    if not isinstance(voice, dict) or not isinstance(voice.get("avoid", []), list):
        raise HypitIntegrationError("Creator Context voice 格式无效")
    context = value.get("relevant_context", [])
    if not isinstance(context, list):
        raise HypitIntegrationError("Creator Context relevant_context 必须是数组")
    privacy = value.get("privacy_policy", {})
    if not isinstance(privacy, dict) or privacy.get("do_not_infer_private_facts") is not True:
        raise HypitIntegrationError("Creator Context 必须禁止推断私人事实")
    return value


def _validate_truth_packet(value: dict[str, Any]) -> dict[str, Any]:
    if value.get("schema") not in {"easel-truth-packet@1", "easel-truth-packet@2"}:
        raise HypitIntegrationError("Truth Packet schema 必须是 easel-truth-packet@1 或 @2")
    if not isinstance(value.get("claims"), list) or not isinstance(value.get("personal_facts"), list):
        raise HypitIntegrationError("Truth Packet 必须包含 claims 和 personal_facts 数组")
    if not isinstance(value.get("forbidden_inventions"), list):
        raise HypitIntegrationError("Truth Packet 必须包含 forbidden_inventions 数组")
    if not isinstance(value.get("uncertainty_policy"), dict):
        raise HypitIntegrationError("Truth Packet 缺少 uncertainty_policy")
    _reject_secret_fields(value)
    return value


def create_handoff(
    creation_id: str,
    *,
    content_core: dict[str, Any],
    truth_packet: dict[str, Any],
    creator_context: dict[str, Any],
    references: list[dict[str, Any]] | None = None,
    production_request: dict[str, Any] | None = None,
    approval_required: bool = True,
    max_budget_usd: float | None = None,
    preparation_key: str | None = None,
    profile_source_sha256: str | None = None,
) -> dict[str, Any]:
    if not _ID_RE.fullmatch(creation_id):
        raise HypitIntegrationError("作品 ID 非法")
    work = creation.get_creation(creation_id)
    try:
        creation.require_chat_proposal_confirmed(work)
    except creation.CreationError as exc:
        raise HypitIntegrationError(str(exc)) from exc
    if not isinstance(content_core, dict) or not content_core:
        raise HypitIntegrationError("Content Core 必须是非空 JSON 对象")
    _reject_secret_fields(content_core)
    _validate_truth_packet(truth_packet)
    _validate_creator_context(creator_context)
    references = references or []
    production_request = production_request or {
        "media_type": "video",
        "orientation": "9:16",
        "language": "zh-CN",
        "preferred_duration_seconds": {"min": 30, "max": 45},
    }
    if not isinstance(references, list) or not isinstance(production_request, dict):
        raise HypitIntegrationError("references 或 production_request 格式无效")
    _reject_secret_fields(references)
    _reject_secret_fields(production_request)
    if max_budget_usd is not None and (not math.isfinite(max_budget_usd) or max_budget_usd < 0):
        raise HypitIntegrationError("max_budget_usd 必须是有限的非负金额")
    if preparation_key is not None and not re.fullmatch(r"[0-9a-f]{64}", preparation_key):
        raise HypitIntegrationError("Preparation operation key 格式无效")
    if profile_source_sha256 is not None and not re.fullmatch(r"sha256:[0-9a-f]{64}", profile_source_sha256):
        raise HypitIntegrationError("Creator Profile source hash 格式无效")

    mode_id = work.get("creative_mode")
    mode = load_creative_mode(mode_id) if mode_id else None
    if mode is None:
        raise HypitIntegrationError("Creation 必须绑定有效的 Creative Mode")
    _reject_secret_fields(mode)
    if work.get("creative_mode_version") and work["creative_mode_version"] != mode["version"]:
        raise HypitIntegrationError("Creation 创建后 Creative Mode 版本已变化；请创建新作品以保持可复现")

    creation_dir = creation._creation_dir(creation_id)
    handoff_id = (
        "ho_" + hashlib.sha256(f"{creation_id}:{preparation_key}".encode("utf-8")).hexdigest()[:32]
        if preparation_key else f"ho_{uuid.uuid4().hex}"
    )
    package = creation_dir / "handoffs" / handoff_id
    if preparation_key:
        existing = next((item for item in work.get("hypit_handoffs", [])
                         if item.get("preparation_key") == preparation_key), None)
        if existing:
            resolved_package, manifest, digest = resolve_handoff(creation_id, existing["handoff_id"])
            return {**existing, "manifest": manifest, "path": existing["path"], "hash": digest}
        if package.exists():
            try:
                manifest_bytes = (package / "handoff.json").read_bytes()
                recovered_hash = _sha256(manifest_bytes)
                manifest, recovered_hash = verify_handoff_directory(package, recovered_hash)
            except (OSError, HypitIntegrationError) as exc:
                raise HypitIntegrationError("检测到未完成的同一 operation Handoff；为避免重复创建已停止") from exc
            if (manifest.get("creation_id") != creation_id
                    or manifest.get("handoff_id") != handoff_id
                    or manifest.get("preparation_key") != preparation_key):
                raise HypitIntegrationError("同一 operation 的 Handoff 身份不匹配；拒绝覆盖")
            record = {
                "handoff_id": handoff_id,
                "path": f"_creations/{creation_id}/handoffs/{handoff_id}",
                "hash": recovered_hash,
                "creative_mode_id": mode_id,
                "creative_mode_version": mode["version"],
                "preparation_key": preparation_key,
                "created_at": manifest.get("created_at", _now()),
            }
            with creation.edit_creation(creation_id) as current:
                if not any(item.get("handoff_id") == handoff_id for item in current.get("hypit_handoffs", [])):
                    current.setdefault("hypit_handoffs", []).append(record)
            _set_readonly_tree(package)
            return {**record, "manifest": manifest}
    package.mkdir(parents=True, exist_ok=False)
    mode_dir = Path(mode["_directory"])
    try:
        files = {
            "content-core.json": content_core,
            "truth-packet.json": truth_packet,
            "creator-context.json": creator_context,
            "references.json": references,
        }
        hashes = {name: _write_json(package / name, value) for name, value in files.items()}

        mode_snapshot = package / "creative-mode"
        mode_snapshot.mkdir()
        mode_entries: list[dict[str, str]] = []
        for filename in _MODE_FILES:
            source = mode_dir / filename
            if not source.is_file():
                continue
            if mode_dir.resolve() not in source.resolve().parents:
                raise HypitIntegrationError(f"Creative Mode 文件越过 Mode 目录：{filename}")
            payload = source.read_bytes()
            (mode_snapshot / filename).write_bytes(payload)
            mode_entries.append({"path": filename, "hash": _sha256(payload)})
        mode_hash = _sha256(_json_bytes(mode_entries))

        handoff = {
            "schema": "easel-hypit-handoff@1",
            "creation_id": creation_id,
            "handoff_id": handoff_id,
            "created_at": _now(),
            "creator_context": {
                "path": "creator-context.json",
                "hash": hashes["creator-context.json"],
                "profile_id": work.get("profile"),
                "profile_name": work.get("profile"),
                "profile_source_sha256": profile_source_sha256,
            },
            "content": {
                "content_core": {"path": "content-core.json", "hash": hashes["content-core.json"]},
                "truth_packet": {"path": "truth-packet.json", "hash": hashes["truth-packet.json"]},
            },
            "creative_mode": {
                "mode_id": mode_id,
                "version": mode["version"],
                "path": "creative-mode",
                "hash": mode_hash,
                "files": mode_entries,
            },
            "production_request": production_request,
            "cost_policy": {
                "approval_required": bool(approval_required),
                "max_budget_usd": max_budget_usd,
            },
            "references": {"path": "references.json", "hash": hashes["references.json"]},
            **({"preparation_key": preparation_key} if preparation_key else {}),
        }
        handoff_hash = _write_json(package / "handoff.json", handoff)
    except BaseException:
        shutil.rmtree(package, ignore_errors=True)
        raise

    creation.get_creation(creation_id)
    record = {
        "handoff_id": handoff_id,
        "path": f"_creations/{creation_id}/handoffs/{handoff_id}",
        "hash": handoff_hash,
        "creative_mode_id": mode_id,
        "creative_mode_version": mode["version"],
        **({"preparation_key": preparation_key} if preparation_key else {}),
        "created_at": handoff["created_at"],
    }
    with creation.edit_creation(creation_id) as current:
        current.setdefault("hypit_handoffs", []).append(record)
    creation.record_stage(
        creation_id,
        "content_core",
        "completed",
        artifacts=[
            f"_creations/{creation_id}/handoffs/{handoff_id}/content-core.json",
            f"_creations/{creation_id}/handoffs/{handoff_id}/truth-packet.json",
        ],
        summary="Content Core 与 Truth Packet 已冻结到 Handoff",
    )
    _set_readonly_tree(package)
    return {**record, "manifest": handoff}


def resolve_handoff(creation_id: str, handoff_id: str) -> tuple[Path, dict[str, Any], str]:
    work = creation.get_creation(creation_id)
    record = next((item for item in work.get("hypit_handoffs", [])
                   if item.get("handoff_id") == handoff_id), None)
    if record is None:
        raise HypitIntegrationError("Handoff 不存在")
    if not re.fullmatch(r"ho_[0-9a-f]{32}", handoff_id):
        raise HypitIntegrationError("Handoff ID 非法")
    package = creation._creation_dir(creation_id) / "handoffs" / handoff_id
    manifest, handoff_hash = verify_handoff_directory(package, record.get("hash", ""))
    if handoff_hash != record.get("hash"):
        raise HypitIntegrationError("Handoff 与已登记 hash 不一致")
    return package, manifest, handoff_hash
