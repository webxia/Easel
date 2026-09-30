"""Controlled chat capabilities and durable chat-to-Creation binding."""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

if os.name == "nt":
    import msvcrt
else:
    import fcntl

from easel import creation

CAPABILITIES: dict[str, dict[str, str]] = {
    "ai-film": {
        "artifact_type": "video",
        "route": "hypit_video",
        "label": "整片视频创作",
    },
}

_BINDINGS_NAME = "_chat_bindings.json"
_local_lock = threading.RLock()


class ChatCapabilityError(ValueError):
    """Raised when a chat capability is unsupported or cannot be bound."""


def is_film_creation_request(message: str) -> bool:
    """Route explicit film commissions into Proposal, never into execution.

    Script-only, editing and advice requests remain ordinary chat. Ambiguous
    requests can still select the existing capability menu explicitly.
    """
    text = message.strip()
    if re.search(r"(?:不要|不需要|不想)(?:做|制作|生成|创作)?(?:完整)?(?:短)?视频", text):
        return False
    if re.search(r"视频(?:脚本|怎么做|如何|选型)|(?:剪辑|裁剪|压缩|转码|翻译|提取|分析|总结)(?:.{0,8})视频|口播脚本", text):
        return False
    return bool(re.search(
        r"(?:我想|我要|帮我|请|希望)(?:.{0,12})(?:做|制作|创作|生成)(?:.{0,40})(?:短视频|完整视频|整片视频|一支视频|一条视频|一部视频)",
        text,
    ))


def resolve_chat_capability(value: str | None) -> dict[str, str] | None:
    if value is None:
        return None
    if not isinstance(value, str) or value not in CAPABILITIES:
        raise ChatCapabilityError("不支持的创作能力")
    return {"id": value, **CAPABILITIES[value]}


def _session_hash(session_id: str) -> str:
    if not isinstance(session_id, str) or not session_id.strip() or len(session_id) > 256:
        raise ChatCapabilityError("视频创作需要有效的聊天会话")
    return hashlib.sha256(session_id.encode("utf-8")).hexdigest()


def _read_bindings(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema": "easel-chat-bindings@1", "sessions": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ChatCapabilityError("聊天作品绑定记录损坏，已停止创建以避免重复作品") from exc
    if (not isinstance(data, dict)
            or data.get("schema") != "easel-chat-bindings@1"
            or not isinstance(data.get("sessions"), dict)):
        raise ChatCapabilityError("聊天作品绑定记录格式无效")
    return data


@contextmanager
def _bindings_lock(lock_path: Path) -> Iterator[None]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with _local_lock, lock_path.open("a+b") as lock_file:
        if os.name == "nt":
            lock_file.seek(0, os.SEEK_END)
            if lock_file.tell() == 0:
                lock_file.write(b"0")
                lock_file.flush()
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
        else:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _find_unindexed_creation(session_hash: str) -> dict[str, Any] | None:
    matches: list[dict[str, Any]] = []
    root = creation.CREATIONS_DIR
    if root.is_dir():
        for path in root.glob("cr_*/creation.json"):
            try:
                item = creation._load(path.parent.name)
            except creation.CreationError:
                continue
            origin = item.get("origin", {})
            if origin.get("type") == "chat" and origin.get("session_hash") == session_hash:
                matches.append(item)
    if len(matches) > 1:
        raise ChatCapabilityError("当前会话存在多个未绑定作品，请新建聊天后继续")
    return matches[0] if matches else None


def bind_chat_creation(
    session_id: str,
    turn_id: str | None,
    idea: str,
    *,
    profile: str | None,
    creative_mode: str | None,
    capability: str,
) -> dict[str, Any]:
    """Create once per chat session, recovering the binding after a process crash."""
    resolved = resolve_chat_capability(capability)
    if resolved is None:
        raise ChatCapabilityError("缺少受支持的创作能力")
    session_hash = _session_hash(session_id)
    if turn_id is not None and (not isinstance(turn_id, str) or len(turn_id) > 256):
        raise ChatCapabilityError("无效的聊天轮次标识")
    idea = idea.strip()
    if not idea:
        raise ChatCapabilityError("请先输入这条作品的主题")
    turn_hash = hashlib.sha256(turn_id.encode("utf-8")).hexdigest() if turn_id else ""

    root = creation.CREATIONS_DIR
    index_path = root / _BINDINGS_NAME
    with _bindings_lock(index_path.with_suffix(".lock")):
        index = _read_bindings(index_path)
        creation_id = index["sessions"].get(session_hash)
        work: dict[str, Any] | None = None
        if isinstance(creation_id, str):
            try:
                work = creation.get_creation(creation_id)
            except creation.CreationError:
                work = None
        if work is not None:
            origin = work.get("origin", {})
            if origin.get("type") != "chat" or origin.get("session_hash") != session_hash:
                raise ChatCapabilityError("聊天作品绑定与作品记录不一致，已停止继续创作")
        if work is None:
            work = _find_unindexed_creation(session_hash)
        if work is None:
            work = creation.create_creation(
                idea,
                profile=profile,
                creative_mode=creative_mode,
                route=resolved["route"],
                origin={
                    "type": "chat",
                    "session_hash": session_hash,
                    "initial_turn_hash": turn_hash,
                },
            )
        if work.get("route") != resolved["route"]:
            raise ChatCapabilityError("当前会话已绑定其他作品路由，请新建聊天后继续")
        try:
            work = creation.ensure_chat_proposal_state(work["id"])
        except creation.CreationError as exc:
            raise ChatCapabilityError(str(exc)) from exc
        index["sessions"][session_hash] = work["id"]
        creation._atomic_write(index_path, index)
        return work


def get_chat_creation(session_id: str) -> dict[str, Any] | None:
    """Resolve the existing Creation bound to a chat without creating a new one."""
    session_hash = _session_hash(session_id)
    index_path = creation.CREATIONS_DIR / _BINDINGS_NAME
    with _bindings_lock(index_path.with_suffix(".lock")):
        index = _read_bindings(index_path)
        creation_id = index["sessions"].get(session_hash)
        work = None
        if isinstance(creation_id, str):
            try:
                work = creation.get_creation(creation_id)
            except creation.CreationError:
                work = None
        if work is None:
            work = _find_unindexed_creation(session_hash)
        if work is None:
            return None
        origin = work.get("origin", {})
        if origin.get("type") != "chat" or origin.get("session_hash") != session_hash:
            raise ChatCapabilityError("聊天作品绑定与作品记录不一致，已停止继续创作")
        return work


def creation_context(work: dict[str, Any]) -> str:
    """Build the hidden Agent context for the already-bound work."""
    mode = work.get("creative_mode") or "自由表达"
    profile = work.get("profile") or "通用画像"
    return (
        "〔当前作品上下文，仅供 Easel 内部协作，不要向用户复述内部 ID〕\n"
        f"作品 ID：{work['id']}\n"
        f"初始主题：{work['idea']}\n"
        f"创作链路：{work.get('route') or 'standard'}\n"
        f"绑定创作者画像：{profile}\n"
        f"绑定作品风格：{mode}\n"
        f"当前准备状态：{(work.get('preparation') or {}).get('status', 'CREATED')}\n"
        "本轮属于该聊天会话关联作品的首次创作或后续修订；必须复用此作品 ID，"
        "不得另建 Creation。Profile、作品风格和初始主题以该作品记录为准。"
    )
