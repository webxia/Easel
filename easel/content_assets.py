"""Registration of formally selected Creation outputs in the Content Library."""

from __future__ import annotations

import hashlib
import json
import os
import re
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from easel import creation


class ContentAssetRegistrationError(ValueError):
    """Raised when a selected output cannot be safely registered."""


def publication_requires_rights_review(material_usage: list[dict]) -> bool:
    """Production permission is distinct from permission to distribute."""
    if (not isinstance(material_usage, list)
            or any(not isinstance(item, dict) or not isinstance(item.get('constraints'), list)
                   or any(not isinstance(value, str) for value in item['constraints'])
                   for item in material_usage)):
        raise ContentAssetRegistrationError('成片素材使用范围记录无效')
    return any('internal_production_only' in item['constraints'] for item in material_usage)


def assert_media_publication_allowed(path: Path) -> None:
    """Enforce retained output limits for original and Content Library copies."""
    try:
        relative = path.resolve().relative_to(creation.OUTPUTS_DIR.resolve())
    except ValueError as exc:
        raise ContentAssetRegistrationError('发布文件不属于内容库') from exc
    parts = relative.parts
    manifest_source = None
    if len(parts) == 5 and parts[0] == '_creations' and parts[2] == 'attempts':
        creation_id, attempt_id = parts[1], parts[3]
        original_path = relative.as_posix()
    elif len(parts) == 2 and re.fullmatch(r'creation-cr_[0-9a-f]{32}-[0-9a-f]{12}', parts[0]):
        try:
            manifest_path = path.parent / '.easel.json'
            if manifest_path.is_symlink():
                raise ValueError
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            if manifest.get('schema') != 'easel-content-asset@1' or path.name not in manifest.get('deliverables', []):
                raise ValueError
            manifest_source = manifest['source']
            creation_id, attempt_id = manifest_source['creation_id'], manifest_source['attempt_id']
            original_path = manifest_source['original_path']
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise ContentAssetRegistrationError('无法核实成片素材使用范围') from exc
    else:
        return  # Existing unrelated publication projects retain their behavior.
    try:
        work = creation.get_creation(creation_id)
        attempt = next(item for item in work.get('hypit_attempts', []) if item.get('attempt_id') == attempt_id)
        output_name, output = next((name, item) for name, item in attempt.get('outputs', {}).items()
                                   if item.get('path') == original_path)
        usage = output.get('material_usage', [])
        digest = _digest(path)
        if output.get('sha256') != 'sha256:' + digest:
            raise ValueError
        if manifest_source is not None and (manifest_source.get('sha256') != digest
                or manifest_source.get('material_usage', []) != usage):
            raise ValueError
    except (OSError, ValueError, TypeError, KeyError, StopIteration) as exc:
        raise ContentAssetRegistrationError('成片身份或素材使用范围与原记录不一致') from exc
    review = attempt.get('review', {})
    if (attempt.get('review_status') != 'APPROVED'
            or review.get('binding') != {'output_name': output_name, 'sha256': output['sha256']}
            or review.get('human', {}).get('status') != 'approved'
            or any(review.get(key, {}).get('status') != 'pass' for key in ('technical', 'truth', 'style'))
            or review.get('material_usage', []) != usage):
        raise ContentAssetRegistrationError('当前成片尚未通过绑定此文件的最终审片，不能发布')
    if publication_requires_rights_review(usage):
        raise ContentAssetRegistrationError('本片素材使用范围仅限内部制作；入库未增加发布权限')


def _digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def _metadata(path: Path, output: dict[str, Any]) -> dict[str, Any]:
    facts = dict(output.get("metadata") or {})
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration:stream=codec_name,width,height,codec_type",
             "-of", "json", str(path)], capture_output=True, text=True,
            timeout=15, check=True,
        )
        data = json.loads(probe.stdout)
        streams = data.get("streams", [])
        video = next((item for item in streams if item.get("codec_type") == "video"), {})
        if video.get("codec_name"):
            facts["video_codec"] = video["codec_name"]
        audio = next((item for item in streams if item.get("codec_type") == "audio"), {})
        if audio.get("codec_name"):
            facts["audio_codec"] = audio["codec_name"]
        if video.get("width"):
            facts["width"] = video["width"]
        if video.get("height"):
            facts["height"] = video["height"]
        if data.get("format", {}).get("duration"):
            facts["duration_seconds"] = float(data["format"]["duration"])
    except (OSError, subprocess.SubprocessError, ValueError, json.JSONDecodeError):
        pass
    facts["size_bytes"] = path.stat().st_size
    return facts


def _safe_title(value: Any) -> str:
    title = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", " ", str(value or "Easel 创作")).strip()
    title = re.sub(r"\s+", " ", title)
    return title[:80] or "Easel 创作"


def _creation_theme(work: dict[str, Any], attempt: dict[str, Any]) -> str | None:
    idea = str(work.get("idea") or "")
    match = re.search(r"主题(?:是|为)?\s*[“「\"]([^”」\"]{2,80})[”」\"]", idea)
    if match:
        return match.group(1).strip()
    core: dict[str, Any] = {}
    handoff_id = attempt.get("handoff", {}).get("handoff_id")
    if isinstance(handoff_id, str) and re.fullmatch(r"ho_[0-9a-f]{32}", handoff_id):
        creation_root = creation.OUTPUTS_DIR / "_creations" / str(work.get("id"))
        core_path = creation_root / "handoffs" / handoff_id / "content-core.json"
        try:
            resolved = core_path.resolve(strict=True)
            if (creation_root.resolve() in resolved.parents and not core_path.is_symlink()
                    and resolved.is_file()):
                core = json.loads(resolved.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    core_idea = core.get("core_idea")
    if isinstance(core_idea, str) and core_idea.strip():
        quoted = re.search(r"[「“\"]([^」”\"]{2,80})[」”\"]", core_idea)
        return (quoted.group(1) if quoted else core_idea).strip()
    return None


def _selected_copy(attempt: dict[str, Any]) -> dict[str, list[str]]:
    brief = attempt.get("production_request", {}).get("production_brief", {})
    overlays = brief.get("text_overlays") if isinstance(brief, dict) else None
    on_screen = [str(value).strip()[:240] for value in overlays
                 if isinstance(value, str) and value.strip()][:12] if isinstance(overlays, list) else []
    voiceover: list[str] = []
    try:
        from easel.integrations.hypit.service import _workspace
        workspace = _workspace(attempt)
        script = next((workspace / candidate for candidate in (
            "productions/easel-authoring/SCRIPT.md", "planning/SCRIPT.md",
        ) if (workspace / candidate).is_file() and not (workspace / candidate).is_symlink()
            and workspace.resolve() in (workspace / candidate).resolve().parents), None)
        if script is not None:
            text = script.read_text(encoding="utf-8").strip()
            section = re.search(
                r"^##\s*(?:字幕文本|画面文案|文案)[^\n]*\n([\s\S]*?)(?=^##\s|\Z)",
                text, re.MULTILINE,
            )
            if section:
                block = re.search(r"```[^\n]*\n([\s\S]*?)```", section.group(1))
                values = block.group(1) if block else section.group(1)
                on_screen = [line.strip(" `「」\"'：:|-　")[:240]
                             for line in values.splitlines()
                             if line.strip(" `「」\"'：:|-　")][:12] or on_screen
            elif not re.search(r"^\s{0,3}(?:#|>|\||[-*])", text, re.MULTILINE) and len(text) <= 1200:
                voiceover = [text[:1200]]
    except (OSError, ValueError, KeyError):
        pass
    return {"on_screen": on_screen, "voiceover": voiceover}


def _selected_record(work: dict[str, Any], attempt_id: str, output_name: str) -> tuple[dict, dict, Path]:
    attempt = next((item for item in work.get("hypit_attempts", [])
                    if item.get("attempt_id") == attempt_id), None)
    if (attempt is None or work.get("selected_attempt_id") != attempt_id
            or work.get("selected_output_name") != output_name
            or attempt.get("selected") is not True
            or attempt.get("review_status") != "APPROVED"):
        raise ContentAssetRegistrationError("只有当前已批准的 Selected Output 可以登记到内容库")
    output = attempt.get("outputs", {}).get(output_name)
    review = attempt.get("review", {})
    sha = (output or {}).get("sha256")
    if (not isinstance(output, dict) or not re.fullmatch(r"sha256:[0-9a-f]{64}", str(sha))
            or review.get("binding", {}).get("output_name") != output_name
            or review.get("binding", {}).get("sha256") != sha
            or review.get("human", {}).get("status") != "approved"
            or review.get('material_usage', []) != output.get('material_usage', [])
            or review.get("truth", {}).get("status") != "pass"
            or review.get("style", {}).get("status") != "pass"
            or review.get("technical", {}).get("status") != "pass"):
        raise ContentAssetRegistrationError("Selected Output 缺少与文件绑定的有效 Review 证据")
    relative = output.get("path")
    if not isinstance(relative, str) or Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ContentAssetRegistrationError("Selected Output 路径无效")
    source = (creation.OUTPUTS_DIR / relative).resolve()
    root = creation.OUTPUTS_DIR.resolve()
    if root not in source.parents or not source.is_file() or _digest(source) != sha.removeprefix("sha256:"):
        raise ContentAssetRegistrationError("Selected Output 文件缺失或 SHA 与 Review 不一致")
    return attempt, output, source


def register_selected_output(work: dict[str, Any], attempt_id: str, output_name: str) -> dict[str, Any]:
    """Copy one currently approved Selected Output into a visible library project.

    Stable Creation/output identity makes retries idempotent. The original
    Attempt output remains intact as execution and audit evidence.
    """
    attempt, output, source = _selected_record(work, attempt_id, output_name)
    sha = output["sha256"].removeprefix("sha256:")
    project_name = f"creation-{work['id']}-{sha[:12]}"
    project = creation.OUTPUTS_DIR / project_name
    target = project / "final.mp4"
    manifest_path = project / ".easel.json"
    metadata = _metadata(source, output)
    theme = _creation_theme(work, attempt)
    copy = _selected_copy(attempt)
    record = {
        "schema": "easel-content-asset@1",
        "asset_id": f"content-{work['id']}-{sha[:12]}",
        "title": _safe_title(attempt.get("build", {}).get("operation", {}).get("display_title")
                              or attempt.get("production_request", {}).get("display_title")
                              or attempt.get("production_request", {}).get("title")
                              or work.get("idea")),
        "summary": theme or "",
        "theme": theme,
        "copy": copy,
        "kind": "video",
        "status": "ready",
        "deliverables": ["final.mp4"],
        "source": {
            "creation_id": work["id"], "attempt_id": attempt_id,
            "build_id": (attempt.get("build", {}).get("build_id")
                         or attempt.get("submitted", {}).get("build", {}).get("id")
                         or attempt.get("submitted", {}).get("build_id")),
            "selected_output_name": output_name,
            "selected_at": work.get("publication", {}).get("selected_at"),
            "original_path": output["path"], "sha256": sha,
            "attribution": output.get("attribution", []),
            "material_usage": output.get("material_usage", []),
        },
        "media_metadata": metadata,
        "creative_mode": work.get("creative_mode"),
        "creative_mode_version": work.get("creative_mode_version"),
    }
    project.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.is_symlink() or _digest(target) != sha:
            raise ContentAssetRegistrationError("内容库目标已存在且内容不匹配")
    else:
        fd, temporary_name = tempfile.mkstemp(prefix=".final-", suffix=".mp4", dir=project)
        os.close(fd)
        try:
            shutil.copyfile(source, temporary_name)
            if _digest(Path(temporary_name)) != sha:
                raise ContentAssetRegistrationError("复制后的内容 SHA 校验失败")
            Path(temporary_name).replace(target)
        finally:
            Path(temporary_name).unlink(missing_ok=True)
    existing: dict[str, Any] = {}
    if manifest_path.is_file():
        try:
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raise ContentAssetRegistrationError("内容库资产登记文件损坏")
        if existing.get("asset_id") != record["asset_id"] or existing.get("source", {}).get("sha256") != sha:
            raise ContentAssetRegistrationError("内容库资产身份与本次 Selected Output 冲突")
    if existing != record:
        temporary_manifest = manifest_path.with_suffix(".tmp")
        temporary_manifest.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary_manifest.replace(manifest_path)
    return {
        "asset_id": record["asset_id"], "path": f"{project_name}/final.mp4",
        "manifest": f"{project_name}/.easel.json", "sha256": sha,
        "metadata": metadata, "source": record["source"],
        "theme": theme, "copy": copy,
    }


def reconcile_selected_outputs() -> dict[str, Any]:
    """Idempotently register only records with formal approved Selection evidence."""
    from easel.creation import edit_creation, list_creations

    registered: list[dict[str, Any]] = []
    skipped = 0
    for listed in list_creations(limit=200):
        creation_id = listed.get("id")
        if not isinstance(creation_id, str):
            continue
        attempt_id = listed.get("selected_attempt_id")
        output_name = listed.get("selected_output_name")
        if not attempt_id or not output_name:
            continue
        try:
            with edit_creation(creation_id) as work:
                registration = register_selected_output(work, attempt_id, output_name)
                if work.get("content_asset") != registration:
                    work["content_asset"] = registration
                    work.setdefault("history", []).append({
                        "at": work.get("updated_at"),
                        "event": "selected_output_registered_in_content_library",
                        "asset_id": registration["asset_id"],
                        "sha256": registration["sha256"],
                    })
        except ContentAssetRegistrationError:
            skipped += 1
            continue
        registered.append({"creation_id": creation_id, **registration})
    return {"registered": registered, "registered_count": len(registered), "skipped_invalid": skipped}
