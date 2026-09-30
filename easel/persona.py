"""Easel 画像（Profile）共享助手 —— CLI / Web / skill 三入口的单一真相源。

历史上三处各写一份画像逻辑，且 CLI 还残留全局 USER.md（并发竞态）。
统一到这里后：画像一律**作为消息内联**注入（`我当前使用的画像是「X」。`），
由 OpenClaw 按 AGENTS.md 自行读取 `profiles/<X>/` 并凝练，每个请求自包含，无全局文件污染。
参见 docs/prompt-stack.md。
"""

from __future__ import annotations

from pathlib import Path
import json
import os
import tempfile

from easel.creative_mode import creative_mode_prefix, load_creative_mode

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROFILES_DIR = PROJECT_ROOT / "profiles"

# 六维画像文件的固定顺序（identity/style/... 先，其余 .md 追加在后）
_FILE_ORDER = [
    "identity.md", "style.md", "audience.md",
    "platforms.md", "preferences.md", "memory.md",
]
PROFILE_SETTINGS_FILENAME = ".easel-profile.json"


def list_personas() -> list[str]:
    """列出所有可用画像目录名（排除下划线开头的内部目录）。"""
    if not PROFILES_DIR.is_dir():
        return []
    return sorted(
        d.name for d in PROFILES_DIR.iterdir()
        if d.is_dir() and not d.name.startswith("_")
    )


def profile_exists(name: str) -> bool:
    """检查画像目录是否存在。"""
    return bool(name) and (PROFILES_DIR / name).is_dir()


def _profile_settings_path(name: str, profiles_dir: Path | None = None) -> Path | None:
    root = profiles_dir or PROFILES_DIR
    if not name or "/" in name or "\\" in name:
        return None
    profile_dir = (root / name).resolve()
    if not profile_dir.is_dir() or root.resolve() not in profile_dir.parents:
        return None
    return profile_dir / PROFILE_SETTINGS_FILENAME


def load_profile_settings(name: str, profiles_dir: Path | None = None) -> dict:
    """Read non-editorial Profile metadata without mixing it into Profile text."""
    path = _profile_settings_path(name, profiles_dir)
    if path is None or not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def profile_default_creative_mode(name: str, profiles_dir: Path | None = None) -> str | None:
    value = load_profile_settings(name, profiles_dir).get("default_creative_mode")
    return value if isinstance(value, str) and value else None


def set_profile_default_creative_mode(name: str, mode_id: str | None,
                                      profiles_dir: Path | None = None) -> str | None:
    """Persist only a Mode reference; providers and production settings stay out."""
    path = _profile_settings_path(name, profiles_dir)
    if path is None:
        raise ValueError("画像不存在")
    data = load_profile_settings(name, profiles_dir)
    if mode_id:
        data["default_creative_mode"] = mode_id
    else:
        data.pop("default_creative_mode", None)
    if not data:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        return None
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
    return profile_default_creative_mode(name, profiles_dir)


def load_profile_text(name: str) -> str:
    """读取画像文件夹，按固定顺序拼接所有非空 .md。画像不存在返回空串。"""
    profile_dir = PROFILES_DIR / name
    if not profile_dir.is_dir():
        return ""
    parts: list[str] = []
    for filename in _FILE_ORDER:
        filepath = profile_dir / filename
        if filepath.is_file():
            text = filepath.read_text(encoding="utf-8").strip()
            if text:
                parts.append(text)
    for filepath in sorted(profile_dir.glob("*.md")):
        if filepath.name not in _FILE_ORDER:
            text = filepath.read_text(encoding="utf-8").strip()
            if text:
                parts.append(text)
    return "\n\n---\n\n".join(parts)


def persona_prefix(name: str | None) -> str:
    """把画像作为消息前缀内联。无画像或画像不存在时返回空串。

    明确账号记忆作用域，避免 OpenClaw 的全局 MEMORY.md 污染并行画像会话。
    """
    if name and profile_exists(name):
        return (
            f"我当前使用的画像是「{name}」。"
            f"本会话的账号长期记忆仅使用 profiles/{name}/memory.md，"
            "不要使用工作区全局 MEMORY.md 作为账号记忆。"
        )
    return ""


# --- 每轮行为提醒（抗长对话指令衰减）----------------------------------------
# AGENTS.md / SOUL.md 是系统提示，只在会话开头最「新鲜」；长对话里后续追问，
# 模型对系统提示的注意力会衰减 → 常见现象「开头会查 SKILL、后面就凭记忆裸做」。
# 把最关键的反射每轮在消息末尾重申一次（放末尾借近因效应），成本极低，
# 显著提升后续轮次的 SKILL 命中率。仅用于对话入口；单跑某个 SKILL 不必加。
TURN_REMINDER = (
    "〔内部提醒·非用户所说，勿复述、勿回显〕本轮动手前先查技能库："
    "有对应或相邻的 SKILL 就读进来、按它的流程/数据源/工具做，别凭记忆或通用知识裸做；"
    "五层（含制作层：图文/图/视频/成片/长稿等）都由你自己按对应 SKILL 产出成品文件到 outputs/；"
    "问「我的账号/帖子/粉丝/最近发了啥」先查已登录账号、别回问用户要账号名；"
    "要发到公开平台的文案/评论绝不写入密钥/内部地址/代理/路径/env 名等敏感信息，也别随手自曝「由 AI 生成/某工具做的」。"
)


def turn_reminder() -> str:
    """返回每轮行为提醒文案。"""
    return TURN_REMINDER


def chat_turn_message(user_message: str, name: str | None,
                      creative_mode: str | None = None, *, proposal: bool = False) -> str:
    """Build one Agent turn from the selected Profile and Creative Mode.

    The Profile defines the creator. The optional Mode defines the expression
    contract for applicable work. Both are invisible to the chat transcript.
    """
    if proposal and creative_mode:
        mode = load_creative_mode(creative_mode)
        mode_prefix = (f"〔当前作品风格：{mode['name']} / {mode['id']} v{mode['version']}〕"
                       if mode else "")
    else:
        mode_prefix = creative_mode_prefix(creative_mode)
    prefixes = [p for p in (persona_prefix(name), mode_prefix) if p]
    head = "\n\n".join(prefixes)
    head = f"{head}\n\n" if head else ""
    return f"{head}{user_message}" + ("" if proposal else f"\n\n{turn_reminder()}")
