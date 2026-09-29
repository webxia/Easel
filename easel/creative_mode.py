"""Creative Mode packages shared by the Director, production, and review stages.

A profile answers who is speaking. A creative mode answers how a particular
work should feel without prescribing its topic or narrative template.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CREATIVE_MODES_DIR = PROJECT_ROOT / "creative_modes"
_MODE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_BIBLE_FILES = (
    "director-treatment.md",
    "visual-bible.md",
    "audio-bible.md",
    "editing-bible.md",
    "qc-rubric.md",
)

# A Mode is introduced after the Director has settled the Content Core.  Each
# production concern reads only the part of the contract it can actually use.
# This keeps a visual choice from quietly turning into a narrative template.
_STAGE_BIBLES: dict[str, tuple[str, ...]] = {
    "director_plan": ("director-treatment.md",),
    "storyboard": ("visual-bible.md", "audio-bible.md", "editing-bible.md"),
    "image": ("visual-bible.md",),
    "video": ("visual-bible.md", "editing-bible.md"),
    "tts": ("audio-bible.md",),
    "audio": ("audio-bible.md",),
    "assemble": ("audio-bible.md", "editing-bible.md"),
    "qc": ("qc-rubric.md",),
}


def _mode_dir(mode_id: str) -> Path | None:
    if not isinstance(mode_id, str) or not _MODE_ID_RE.fullmatch(mode_id):
        return None
    candidate = (CREATIVE_MODES_DIR / mode_id).resolve()
    root = CREATIVE_MODES_DIR.resolve()
    if root not in candidate.parents:
        return None
    return candidate


def load_creative_mode(mode_id: str) -> dict[str, Any] | None:
    """Load a machine-readable mode contract, or return ``None`` if invalid."""
    directory = _mode_dir(mode_id)
    if directory is None:
        return None
    manifest = directory / "mode.json"
    if not manifest.is_file():
        return None
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or data.get("id") != mode_id:
        return None
    if not isinstance(data.get("name"), str) or not isinstance(data.get("version"), str):
        return None
    data["_directory"] = directory
    return data


def list_creative_modes() -> list[dict[str, Any]]:
    """Return safe UI metadata for every valid, active mode package."""
    if not CREATIVE_MODES_DIR.is_dir():
        return []
    items: list[dict[str, Any]] = []
    for directory in sorted(CREATIVE_MODES_DIR.iterdir()):
        if not directory.is_dir() or directory.name.startswith("_"):
            continue
        mode = load_creative_mode(directory.name)
        if mode is None:
            continue
        items.append({
            "id": mode["id"],
            "name": mode["name"],
            "version": mode["version"],
            "summary": str(mode.get("summary") or ""),
            # Kept as an empty compatibility field; backend routing belongs to
            # the request Capability, never to a Creative Mode.
            "routes": [],
            "status": str(mode.get("status") or "active"),
        })
    return items


def creative_mode_exists(mode_id: str | None) -> bool:
    return bool(mode_id and load_creative_mode(mode_id))


def creative_mode_stage_names() -> tuple[str, ...]:
    """Return the production concerns that can consume a Mode contract."""
    return tuple(_STAGE_BIBLES)


def creative_mode_stage_context(mode_id: str | None, stage: str) -> str:
    """Return the narrow Mode context for one post-Core production concern.

    ``stage`` deliberately names a production concern instead of a story
    shape.  The Director remains free to create the Content Core and choose
    the narrative before this context is used.
    """
    if not mode_id:
        return ""
    mode = load_creative_mode(mode_id)
    if mode is None:
        return ""
    filenames = _STAGE_BIBLES.get(stage)
    if filenames is None:
        allowed = ", ".join(creative_mode_stage_names())
        raise ValueError(f"未知的 Creative Mode 阶段 {stage!r}；可用：{allowed}")

    directory = mode.pop("_directory")
    sections: list[str] = []
    for filename in filenames:
        path = directory / filename
        if path.is_file():
            text = path.read_text(encoding="utf-8").strip()
            if text:
                sections.append(f"### {filename}\n{text}")

    if not sections:
        return ""
    return (
        f"〔Creative Mode 阶段合同：{mode['name']} / {mode['id']} "
        f"v{mode['version']} · {stage}〕\n"
        "Content Core、事实边界和 Director 的叙事决定已经在上游完成。"
        "本合同只约束当前生产环节的作品表达；不得改写主题、补造事实，"
        "也不得把任一视觉或声音规则升级为固定脚本。\n\n"
        + "\n\n".join(sections)
    )


def creative_mode_prefix(mode_id: str | None) -> str:
    """Build the Director-level Mode identity injected into an Agent turn."""
    if not mode_id:
        return ""
    mode = load_creative_mode(mode_id)
    if mode is None:
        return ""

    mode.pop("_directory")
    mode.pop("routes", None)  # Ignore legacy route hints in Mode packages.
    contract = json.dumps(mode, ensure_ascii=False, indent=2)
    return (
        f"〔Creative Mode：{mode['name']} / {mode['id']} v{mode['version']}〕\n"
        "这是作品表达合同，不是固定脚本模板，也不替代你作为 Easel Director 的内容判断。"
        "先根据用户输入与画像建立事实底稿和 Content Core，再决定叙事、脚本与分镜；"
        "仅在本轮确定要制作作品时，才在 Content Core 之后读取对应生产阶段的 Mode 合同。"
        "不要把它用于普通问答、调试或与该作品无关的任务。\n\n"
        "机器合同：\n```json\n"
        f"{contract}\n"
        "```\n\n"
        "执行纪律：内容主题、观点结构和故事类型保持开放；不得为了 Mode 编造第一人称经历、"
        "真实截图、工作细节或情绪。制作项目时把 mode id 与 version 写入 .easel.json 的展示头，"
        "并在交付前同时完成技术 QC 和本 Mode 的导演审片。"
        "阶段合同由 `python3 -m easel.creation context --id <作品ID> --stage <阶段>` 提供。"
    )
