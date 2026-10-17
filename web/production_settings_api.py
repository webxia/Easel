"""Voice preview, subtitle preview and explicit default scopes for production."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from fastapi import APIRouter
from pydantic import ValidationError

from easel.direct_api import read_settings
from easel.production.contracts import SubtitleSettings, VoiceIdentity, canonical_json, fingerprint
from easel.production.editors.base import AssetManifest, EditError, MediaAsset
from easel.production.errors import Conflict, ProductionError
from easel.production.media import file_sha256, local_path, stage_work_media
from easel.production.operations import OperationService
from easel.production.service import WorkService, row
from easel.production.settings import resolve_settings, settings_save_request, validate_settings_patch
from easel.production.store import utc_now
from easel.production.subtitles import SubtitleService, configured_fonts, stage_fonts
from easel.production.voice import configured_voice_service
from web.production_api import Command


def voice_service_for(service: WorkService):
    settings = read_settings(service.outputs.parent / ".env")
    return configured_voice_service(OperationService(service.store), root=service.outputs / "_production" / "voice", settings=settings)


def _settings(value: str) -> dict:
    return {key: value for key, value in json.loads(value).items()
            if key in {"duration_seconds", "aspect_ratio", "audio_mode", "voice", "subtitles"}}


def _replay(service, request, *, action, work_id):
    """Cheap idempotent read before local preparation/configuration can change."""
    payload = {"action": action, "work_id": work_id, "expected_revision": request.expected_revision, "payload": request.payload}
    digest = fingerprint({"work_id": work_id, "expected_revision": request.expected_revision, "request": payload})
    with service.store.connection() as reader:
        previous = reader.execute("SELECT * FROM command_receipts WHERE command_id=?", (request.command_id,)).fetchone()
    if previous:
        if previous["request_hash"] != digest:
            raise Conflict("同一命令标识不能用于不同请求")
        return json.loads(previous["response_json"])
    return None


def create_settings_router(service_provider: Callable[[], WorkService], *, voice_provider=None,
                           settings_provider=None) -> APIRouter:
    router = APIRouter(prefix="/api/production")
    def voice(service):
        return voice_provider() if voice_provider else voice_service_for(service)
    def settings(service):
        return settings_provider() if settings_provider else read_settings(service.outputs.parent / ".env")
    def patch(payload):
        try:
            return validate_settings_patch(payload)
        except (ValidationError, ValueError):
            raise ProductionError("invalid_settings", "声音或字幕设置格式无效") from None

    @router.get("/voice-options")
    def voices(work_id: str | None = None):
        service = service_provider()
        reference = ""
        if work_id:
            with service.store.connection() as reader:
                work = row(reader, "works", work_id)
                reference = work["title"] + " " + work["input_text"]
                if work["channel_id"]:
                    reference += " " + row(reader, "channels", work["channel_id"])["name"]
                if work["profile_ref"]:
                    reference += " " + canonical_json(service.profile_snapshot(reader, work["profile_ref"]))
        return {"voices": voice(service).catalog(reference_text=reference)}

    @router.get("/subtitle-fonts")
    def fonts():
        paths = configured_fonts(settings(service_provider()))
        return {"fonts": [{"id": name, "label": f"{name} · {path.stem}"} for name, path in paths.items()]}

    @router.get("/works/{work_id}/settings")
    def get_settings(work_id: str):
        service = service_provider()
        with service.store.connection() as reader:
            work = row(reader, "works", work_id)
            channel = row(reader, "channels", work["channel_id"]) if work["channel_id"] else None
            profile = row(reader, "profile_refs", work["profile_ref"]) if work["profile_ref"] else None
            scopes = {"work": _settings(work["settings_json"]), "channel": _settings(channel["settings_json"]) if channel else {},
                      "profile": _settings(profile["settings_json"]) if profile else {}}
            return {"revision": work["revision"], "scopes": scopes, "hashes": {scope: fingerprint(value) for scope, value in scopes.items()},
                    **resolve_settings(**scopes)}

    @router.post("/works/{work_id}/settings")
    def save_settings(work_id: str, request: Command):
        service = service_provider()
        values = patch(request.payload.get("settings", {}))
        if request.expected_revision is None:
            raise ProductionError("stale_revision", "保存设置须提供当前作品版本", status_code=409)
        def save(writer):
            work = row(writer, "works", work_id)
            selected = settings_save_request(scope=request.payload.get("scope"), settings=values,
                                             channel_id=work["channel_id"], profile_ref=work["profile_ref"])
            service._ensure_idle(writer, work)
            scope = selected["scope"]
            if scope == "work":
                current = json.loads(work["settings_json"])
                if "subtitles" in values:
                    current["subtitles"] = {**current.get("subtitles", {}), **values["subtitles"]}
                subtitles = current.get("subtitles")
                current.update(values)
                if subtitles is not None:
                    current["subtitles"] = subtitles
                updated = service.store.bump_work(writer, work_id, work["revision"], settings_json=current)
            else:
                table = "channels" if scope == "channel" else "profile_refs"
                target = row(writer, table, selected["target_ref"])
                if request.payload.get("expected_settings_hash") != fingerprint(_settings(target["settings_json"])):
                    raise ProductionError("stale_revision", "频道或画像默认设置已变化，请刷新后保存", status_code=409)
                if target["archived"]:
                    raise ProductionError("invalid_settings_scope", "所选频道或画像已归档")
                old = json.loads(target["settings_json"])
                merged = {**old, **values, "schema_version": 1}
                if "subtitles" in values:
                    merged["subtitles"] = {**old.get("subtitles", {}), **values["subtitles"]}
                if scope == "channel":
                    writer.execute("UPDATE channels SET settings_json=?,revision=revision+1,updated_at=? WHERE id=?",
                                   (canonical_json(merged), utc_now(), target["id"]))
                else:
                    writer.execute("UPDATE profile_refs SET settings_json=? WHERE id=?", (canonical_json(merged), target["id"]))
                updated = service.store.bump_work(writer, work_id, work["revision"])
            service.store.append_event(writer, work_id, "settings_saved", {"scope": scope, "target_ref": selected["target_ref"]})
            return {"work_id": work_id, "revision": updated["revision"], "scope": scope, "settings": values}
        return service.store.execute_command(request.command_id,
            {"action": "settings_save", "work_id": work_id, "expected_revision": request.expected_revision, "payload": request.payload},
            save, work_id=work_id, expected_revision=request.expected_revision)

    @router.post("/works/{work_id}/voice-previews", status_code=202)
    def preview_voice(work_id: str, request: Command):
        service = service_provider()
        previous = _replay(service, request, action="voice_preview", work_id=work_id)
        if previous is not None:
            return previous
        if request.expected_revision is None:
            raise ProductionError("stale_revision", "试听须提供当前作品版本", status_code=409)
        try:
            identity = VoiceIdentity.model_validate(request.payload.get("voice"))
            selected = voice(service)._adapter(identity)
            selected.request(identity=identity, text=request.payload.get("text", ""), segment_id="preview")
        except (ValueError, TypeError, ValidationError):
            raise ProductionError("voice_text_invalid", "请提供有效的固定声音与试听文字") from None
        expected_service = {"provider": selected.provider_id, "model": selected.model, "mode": selected.mode}
        if not isinstance(request.payload.get("regenerate", False), bool):
            raise ProductionError("invalid_input", "重新试听选项无效")
        if expected_service not in request.payload.get("services", []):
            raise ProductionError("permission_missing", "新增试听前请允许本次声音服务；可能产生费用", requires_decision=True)
        def create(writer):
            work = row(writer, "works", work_id)
            service._ensure_idle(writer, work)
            grant_id = service._insert_grant(writer, work, "preview", {"services": [expected_service], "target_ref": request.command_id})
            run_id = service._run(writer, work, "planning", target=request.command_id,
                payload={"voice": identity.model_dump(mode="json"), "text": request.payload["text"],
                         "grant_id": grant_id, "previous_work_state": work["state"], "regenerate": request.payload.get("regenerate", False)})
            writer.execute("UPDATE tasks SET kind='voice_preview' WHERE run_id=?", (run_id,))
            writer.execute("UPDATE works SET state=? WHERE id=?", (work["state"], work_id))
            task = writer.execute("SELECT id FROM tasks WHERE run_id=?", (run_id,)).fetchone()
            return {"work_id": work_id, "run_id": run_id, "task_id": task[0], "revision": row(writer, "works", work_id)["revision"]}
        return service.store.execute_command(request.command_id,
            {"action": "voice_preview", "work_id": work_id, "expected_revision": request.expected_revision, "payload": request.payload},
            create, work_id=work_id, expected_revision=request.expected_revision)

    @router.post("/works/{work_id}/subtitle-previews")
    def preview_subtitles(work_id: str, request: Command):
        service = service_provider()
        previous = _replay(service, request, action="subtitle_preview", work_id=work_id)
        if previous is not None:
            return previous
        if request.expected_revision is None:
            raise ProductionError("stale_revision", "预览须提供当前作品版本", status_code=409)
        try:
            style = SubtitleSettings.model_validate(request.payload.get("settings", {}))
            text = request.payload.get("text", "")
            if not isinstance(text, str) or not text.strip() or len(text) > 12000:
                raise ValueError
        except (ValidationError, ValueError):
            raise ProductionError("invalid_settings", "字幕预览的文字或设置无效") from None
        with service.store.connection() as reader:
            work = row(reader, "works", work_id)
            if work["revision"] != request.expected_revision:
                raise ProductionError("stale_revision", "作品已更新，请刷新后预览", status_code=409)
            if request.payload.get("frame_artifact_id"):
                frame = row(reader, "artifacts", request.payload["frame_artifact_id"])
                if frame["work_id"] != work_id or not frame["media_type"].startswith(("video/", "image/")):
                    raise ProductionError("permission_missing", "画面不属于本作品", status_code=403)
                source, digest = frame["storage_ref"], frame["digest"]
                kind = "video" if frame["media_type"].startswith("video/") else "image"
                frame_id = frame["id"]
                if frame["kind"] == "output":
                    # A burned output cannot be used as the canvas for a new
                    # subtitle style: that would retain the old subtitles too.
                    from easel.production.editors import FFmpegEditor
                    render_id = json.loads(frame["metadata_json"]).get("render_job_id")
                    if not render_id:
                        raise ProductionError("preview_frame_required", "此历史版本缺少无字幕画面，请选择原始画面素材预览")
                    try:
                        base, digest = FFmpegEditor(service.outputs / "_production" / "renders").caption_base(render_id, work_id=work_id)
                    except EditError:
                        raise ProductionError("preview_frame_required", "该版本的无字幕画面不可用，未叠加到旧字幕上") from None
                    source = base.relative_to(service.outputs).as_posix()
            elif request.payload.get("frame_input_id"):
                frame = row(reader, "work_inputs", request.payload["frame_input_id"])
                if frame["work_id"] != work_id or frame["kind"] not in {"video", "image"}:
                    raise ProductionError("permission_missing", "画面不属于本作品", status_code=403)
                source, digest, kind, frame_id = frame["source_ref"], frame["digest"], frame["kind"], frame["id"]
            else:
                raise ProductionError("preview_frame_required", "请先选择本片的实际视频或画面素材")
        # Local rendering occurs outside the write transaction; final registration
        # rechecks the user's expected revision and command identity atomically.
        try:
            local_path(service.outputs, source)
            font_map, assets = stage_fonts(configured_fonts(settings(service)), outputs=service.outputs)
            assets[frame_id] = MediaAsset(locator=source, sha256=digest, kind=kind)
            result = SubtitleService(service.outputs / "_production" / "subtitle_previews").preview(
                manifest=AssetManifest(root=service.outputs, assets=assets), frame_asset_id=frame_id,
                at=float(request.payload.get("at", 0)), settings=style, text=text, fonts=font_map)
        except (EditError, ValueError, OSError):
            raise ProductionError("subtitle_preview_failed", "当前画面或所选字体无法预览，请检查字号、位置和媒体引用") from None
        output = stage_work_media(service.outputs, work_id, Path(result["path"]))
        identifier = "subtitle_" + fingerprint([work_id, result["sha256"]])[:32]
        def register(writer):
            writer.execute("""INSERT OR IGNORE INTO artifacts(id,work_id,kind,storage_ref,digest,size_bytes,media_type,
                displayable,metadata_json,created_at) VALUES(?,?,'subtitle_preview',?,?,?,'image/png',1,?,?)""",
                (identifier, work_id, output.relative_to(service.outputs).as_posix(), file_sha256(output), output.stat().st_size,
                 canonical_json({"schema_version": 1, "settings": style.model_dump(), "frame_id": frame_id,
                                 "width": result["width"], "height": result["height"], "at": result["at"]}), utc_now()))
            service.store.append_event(writer, work_id, "artifact_registered", {"artifact_id": identifier, "kind": "subtitle_preview"})
            return {"artifact_id": identifier, "reused": result["reused"], "width": result["width"], "height": result["height"],
                    "message": "使用所选实际画面预览；构图尺寸以该画面为准。", "revision": request.expected_revision}
        return service.store.execute_command(request.command_id,
            {"action": "subtitle_preview", "work_id": work_id, "expected_revision": request.expected_revision, "payload": request.payload},
            register, work_id=work_id, expected_revision=request.expected_revision)

    return router
