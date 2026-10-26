"""Prepare fixed narration and font assets before the creative editor plans cuts."""
from __future__ import annotations

import json
from pathlib import Path

from .artifacts import register_file
from .contracts import SubtitleSettings, VoiceIdentity
from .editors.base import EditError
from .errors import ProductionError
from .subtitles import configured_fonts, stage_fonts
from .voice import prepare_voice_segments
from .model_tasks import ModelTaskError
from .worker import TaskResult


class VoiceTasks:
    def __init__(self, service, voice_service_provider, *, settings_provider):
        self.service, self.voice_service_provider, self.settings_provider = service, voice_service_provider, settings_provider

    async def prepare_assets(self, context, plan: dict, asset_ids: list[str]) -> tuple[list[str], TaskResult | None]:
        """Return asset handles and optionally a durable pending/decision outcome.

        Only confirmed scene.narration becomes TTS. A scene that explicitly uses
        protected original audio keeps that original track instead. Returned
        audio metadata has literal sentence text, identity and real duration;
        the editing model assigns placement without changing those identities.
        """
        identifiers = list(asset_ids)
        settings = plan["settings"]
        try:
            style = SubtitleSettings.model_validate(settings.get("subtitles", {}))
            if style.enabled:
                configured = configured_fonts(self.settings_provider())
                if style.font not in configured:
                    raise ProductionError("font_unavailable", "所选字幕字体尚未配置，请明确选择可用字体；未替换为系统字体", requires_decision=True)
                font_map, fonts = stage_fonts({style.font: configured[style.font]}, outputs=self.service.outputs)
                asset = fonts[font_map[style.font]]
                saved = register_file(self.service, context, self.service.outputs / asset.locator, kind="font",
                    media_type="font/ttf" if Path(asset.locator).suffix == ".ttf" else "font/otf",
                    metadata={"font_name": style.font, "font_sha256": asset.sha256, "subtitle_settings": style.model_dump()})
                if saved["id"] not in identifiers:
                    identifiers.append(saved["id"])
            if settings["audio_mode"] in {"silent", "music"}:
                return identifiers, None
            with self.service.store.connection() as reader:
                protected = {item["id"] for item in reader.execute("SELECT * FROM work_inputs WHERE work_id=?", (context.work_id,))
                             if json.loads(item["metadata_json"]).get("original_audio")}
            scenes = plan["scenes"]
            from .narration import validate_narration_execution
            segments = validate_narration_execution(plan, protected)
            if not segments:
                if protected:
                    return identifiers, None
                raise ProductionError("narration_required", "当前声音模式需要已确认的旁白文本或保留原声，未擅自朗读脚本中的画面说明", requires_decision=True)
            if not settings.get("voice"):
                raise ProductionError("voice_required", "请先为本次旁白明确选择并固定声音", requires_decision=True)
            identity = VoiceIdentity.model_validate(settings["voice"])
            voice = self.voice_service_provider()
            adapter = voice._adapter(identity)
            # Validate the complete frozen grouping before dispatching its first
            # paid segment. Do not partially synthesize an invalid later group.
            from .voice import effective_segment_voice
            from .prosody import compile_pauses
            for segment in segments:
                effective = effective_segment_voice(identity, segment)
                spoken = compile_pauses(segment['text'], segment.get('pauses', []), effective)
                adapter.request(identity=effective, text=spoken, segment_id=segment['segment_id'])
            required = {"provider": adapter.provider_id, "model": adapter.model, "mode": adapter.mode}
            with self.service.store.connection() as reader:
                grants = [dict(item) for item in reader.execute("""SELECT * FROM authorization_grants WHERE work_id=?
                    AND purpose='production' AND plan_revision=? AND revoked_at IS NULL ORDER BY created_at DESC,id DESC""",
                    (context.work_id, context.plan_revision))]
            grant = next((item for item in grants if required in json.loads(item["services_json"])), None)
            if grant is None:
                raise ProductionError("permission_missing", "当前方案尚未允许所选声音服务；配音不占生图或生视频次数", requires_decision=True)
            result = await prepare_voice_segments(context, service=voice, outputs=self.service.outputs,
                identity=identity, grant_id=grant["id"], segments=segments)
            for segment in result["segments"]:
                if segment["artifact_id"] not in identifiers:
                    identifiers.append(segment["artifact_id"])
            if result["state"] != "succeeded":
                if result["state"] in {"sending", "unknown", "submitted"}:
                    return identifiers, TaskResult(state="waiting_external", result={"asset_ids": identifiers,
                        "operation_id": result["pending"]["operation_id"]})
                raise ProductionError("voice_not_completed", "固定音色配音未完成，已保留已有片段，请明确选择重试或替代声音", requires_decision=True)
            # Real spoken duration must fit each approved scene slot. No truncate,
            # acceleration, repeated narration or extension is implied by success.
            by_id = {segment["segment_id"]: segment for segment in segments}
            totals: dict[str, float] = {}
            for segment in result["segments"]:
                scene_id = by_id[segment["segment_id"]]["scene_id"]
                totals[scene_id] = totals.get(scene_id, 0) + segment["duration"]
            for scene in scenes:
                available = scene.get("duration_seconds")
                if (not (plan.get('narration_policy') or {}).get('continuous')
                        and available is not None and totals.get(scene["id"], 0) > available + .02):
                    raise ProductionError("voice_timing_exceeds_plan", "实际旁白长于已确认场景时段，已保留配音，需要明确调整时长或表达", requires_decision=True)
            if ((plan.get('narration_policy') or {}).get('duration_mode') != 'voice_driven'
                    and sum(totals.values()) > settings["duration_seconds"] + .02):
                raise ProductionError("voice_timing_exceeds_plan", "实际旁白长于已确认作品时长，未截断或加速", requires_decision=True)
            return identifiers, None
        except (ProductionError, EditError, ModelTaskError) as error:
            public = error if isinstance(error, ProductionError) else ProductionError(error.code, str(error), requires_decision=True)
            return identifiers, TaskResult(state="needs_decision", result={"asset_ids": identifiers}, error=public)


def configured_voice_tasks(service, *, settings_provider, voice_service_provider):
    return VoiceTasks(service, voice_service_provider, settings_provider=settings_provider)
