"""Explicit voice identities, durable speech dispatch and reusable sentence assets.

The HTTP contract is the repository's existing /audio/speech binary response
contract. It is opt-in configuration, not provider discovery or engine fallback.
"""
from __future__ import annotations

import asyncio
import json
import math
import re
import shutil
import tempfile
import mimetypes
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from .contracts import VoiceIdentity, fingerprint
from .editors.ffmpeg import _lock
from .errors import ProductionError
from .media import atomic_json, file_sha256, probe_media, stage_work_media
from .operations import OperationService
from .providers.base import ProviderCapabilities, ProviderResult, SubmissionNotSent


@dataclass(frozen=True)
class VoiceOption:
    identity: VoiceIdentity
    label: str
    tags: tuple[str, ...] = ()
    languages: tuple[str, ...] = ()
    speed_range: tuple[float, float] | None = None
    instructions_supported: bool = False
    available: bool = True
    unavailable_reason: str = ""
    fee_notice: str = "新增试听或配音可能产生服务费用；已生成音频可直接复用。"

    def public(self) -> dict:
        return {"identity": self.identity.model_dump(mode="json"), "label": self.label,
                "tags": list(self.tags), "languages": list(self.languages),
                "speed_range": list(self.speed_range) if self.speed_range else None,
                "instructions_supported": self.instructions_supported, "available": self.available,
                "unavailable_reason": self.unavailable_reason, "fee_notice": self.fee_notice}


@dataclass(frozen=True)
class SpeechConfig:
    provider: str
    model: str
    engine: str
    base_url: str
    config_version: str
    voices: tuple[VoiceOption, ...]
    api_key: str = field(default="", repr=False)
    response_format: str = "wav"
    mode: str = "speech"
    timeout_seconds: float = 120

    def __post_init__(self):
        url = urlsplit(self.base_url)
        if (url.scheme not in {"https", "http"} or not url.hostname or url.username or url.password
                or url.query or url.fragment or not all((self.provider, self.model, self.engine, self.config_version))):
            raise ValueError("speech service requires an explicit trusted URL and complete identity")
        if self.engine.casefold() == "auto":
            raise ValueError("automatic speech engine selection is unsupported")
        if self.response_format not in {"wav", "mp3", "flac", "aac", "ogg"}:
            raise ValueError("unsupported speech response format")
        if not 0 < self.timeout_seconds <= 600:
            raise ValueError("invalid speech timeout")
        seen = set()
        for voice in self.voices:
            identity = voice.identity
            if (identity.provider, identity.model, identity.engine) != (self.provider, self.model, self.engine):
                raise ValueError("configured voice belongs to a different speech service")
            if identity.voice_id in seen:
                raise ValueError("duplicate voice identity")
            seen.add(identity.voice_id)


class VoiceHTTPAdapter:
    """No remote query claim: observation only recovers a locally persisted receipt."""
    capabilities = ProviderCapabilities(query_by_request_key=True)

    def __init__(self, config: SpeechConfig, root: Path, *, transport: httpx.BaseTransport | None = None,
                 ffprobe: str = "ffprobe"):
        self.config, self.root, self.transport, self.ffprobe = config, Path(root), transport, ffprobe
        self.provider_id, self.model, self.mode = config.provider, config.model, config.mode
        self.root.mkdir(parents=True, exist_ok=True)

    def option(self, identity: VoiceIdentity, *, require_available: bool = True) -> VoiceOption:
        if (identity.provider, identity.model, identity.engine) != (
                self.config.provider, self.config.model, self.config.engine):
            raise ProductionError("voice_identity_mismatch", "所选声音与固定的服务、模型或引擎不一致", requires_decision=True)
        option = next((item for item in self.config.voices if item.identity.voice_id == identity.voice_id), None)
        if not option or (require_available and not option.available):
            raise ProductionError("voice_unavailable", "固定声音目前不可用，请保留原设置并明确选择替代试听", requires_decision=True)
        parameters = identity.parameters
        allowed = ({"speed"} if option.speed_range else set()) | ({"instructions"} if option.instructions_supported else set())
        if set(parameters) - allowed:
            raise ProductionError("voice_parameter_unsupported", "该声音不支持所选参数")
        if "speed" in parameters:
            speed = parameters["speed"]
            if (isinstance(speed, bool) or not isinstance(speed, (float, int)) or not math.isfinite(speed)
                    or not option.speed_range[0] <= speed <= option.speed_range[1]):
                raise ProductionError("voice_parameter_unsupported", "语速超出所选声音支持的范围")
        if "instructions" in parameters and (not isinstance(parameters["instructions"], str)
                                              or len(parameters["instructions"]) > 1000):
            raise ProductionError("voice_parameter_unsupported", "声音表达要求格式不正确")
        return option

    def request(self, *, identity: VoiceIdentity, text: str, segment_id: str, require_available: bool = True) -> dict:
        self.option(identity, require_available=require_available)
        if not text.strip() or len(text) > 12000 or not segment_id:
            raise ProductionError("voice_text_invalid", "配音片段需要非空文本，单段不能超过 12000 字符")
        return {"text": text, "text_hash": fingerprint(text), "segment_id": segment_id,
                "voice": identity.model_dump(mode="json"), "config_version": self.config.config_version,
                "response_format": self.config.response_format}

    def _directory(self, request_key: str) -> Path:
        return self.root / fingerprint(request_key)

    def submit(self, request: dict, *, request_key: str) -> ProviderResult:
        # Validate the complete persisted request before entering the transport.
        try:
            if not shutil.which(self.ffprobe):
                raise ValueError("audio verification executable is unavailable")
            identity = VoiceIdentity.model_validate(request["voice"])
            expected = self.request(identity=identity, text=request["text"], segment_id=request["segment_id"])
            if request != expected:
                raise ValueError("speech intent changed")
        except (KeyError, ValueError, ProductionError) as error:
            raise SubmissionNotSent("invalid speech request") from error
        folder = self._directory(request_key)
        folder.mkdir(parents=True, exist_ok=True)
        with _lock(folder / "dispatch.lock"):
            if (folder / "receipt.json").exists():
                return self.observe(task_id=None, request_key=request_key)
            # A durable local intent prevents direct adapter callers from blindly
            # resending after timeout/crash; only OperationService may open sends.
            intent = folder / "intent.json"
            if intent.exists():
                previous = json.loads(intent.read_text())
                if previous["request_hash"] != fingerprint(request):
                    raise SubmissionNotSent("speech key conflict")
                return ProviderResult("unknown")
            atomic_json(intent, {"request_hash": fingerprint(request)})
            payload = {"model": identity.model, "voice": identity.voice_id, "input": request["text"],
                       "response_format": self.config.response_format, **identity.parameters}
            headers = {"Content-Type": "application/json", "Idempotency-Key": request_key}
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"
            with httpx.Client(transport=self.transport, timeout=self.config.timeout_seconds,
                              trust_env=False, follow_redirects=False) as client:
                with client.stream("POST", self.config.base_url.rstrip("/") + "/audio/speech",
                                   json=payload, headers=headers) as response:
                    if response.status_code != 200:
                        # A rejected request still reached the service. Never
                        # infer fee refund/non-submission from a generic status.
                        receipt = ProviderResult("failed", result={"error_code": "voice_service_rejected",
                                                                   "http_status": response.status_code})
                        atomic_json(folder / "receipt.json", {"state": receipt.state, "result": receipt.result})
                        return receipt
                    total = 0
                    with tempfile.NamedTemporaryFile(prefix="speech-", dir=folder, delete=False) as stream:
                        temporary = Path(stream.name)
                        try:
                            for chunk in response.iter_bytes():
                                total += len(chunk)
                                if total > 64 * 1024 * 1024:
                                    raise ValueError("speech response exceeds local limit")
                                stream.write(chunk)
                        except BaseException:
                            temporary.unlink(missing_ok=True)
                            raise
            output = folder / f"audio.{self.config.response_format}"
            temporary.replace(output)
            try:
                metadata = probe_media(output, ffprobe=self.ffprobe)
                if not metadata["audio"] or metadata["video"] or metadata["duration"] <= 0:
                    raise ValueError("not an audio asset")
            except Exception:
                receipt = ProviderResult("failed", result={"error_code": "voice_invalid_audio"})
                atomic_json(folder / "receipt.json", {"state": receipt.state, "result": receipt.result})
                return receipt
            result = {"path": str(output), "sha256": file_sha256(output), "duration": metadata["duration"],
                      "voice": identity.model_dump(mode="json"), "text_hash": request["text_hash"],
                      "segment_id": request["segment_id"], "config_version": self.config.config_version}
            atomic_json(folder / "receipt.json", {"state": "succeeded", "result": result})
            return ProviderResult("succeeded", result=result)

    def observe(self, *, task_id: str | None, request_key: str) -> ProviderResult:
        receipt = self._directory(request_key) / "receipt.json"
        if not receipt.is_file():
            return ProviderResult("unknown")
        saved = json.loads(receipt.read_text())
        if saved["state"] == "succeeded":
            result = saved["result"]
            path = self._directory(request_key) / f"audio.{self.config.response_format}"
            if (str(path) != result["path"] or path.is_symlink() or not path.is_file()
                    or file_sha256(path) != result["sha256"]):
                return ProviderResult("unknown", result={"error_code": "voice_asset_missing"})
        return ProviderResult(saved["state"], result=saved["result"])


@dataclass(frozen=True)
class VoiceBinding:
    operation_id: str
    work_id: str
    run_id: str
    task_id: str
    grant_id: str
    owner_epoch: int


class VoiceService:
    def __init__(self, operations: OperationService, root: Path, adapters: list[VoiceHTTPAdapter]):
        self.operations, self.root, self.adapters = operations, Path(root), tuple(adapters)
        self.root.mkdir(parents=True, exist_ok=True)

    def catalog(self, *, reference_text: str = "", limit: int | None = None) -> list[dict]:
        """Rank explicit options as suggestions; never change the selected voice."""
        options = [(option, adapter) for adapter in self.adapters for option in adapter.config.voices]
        context = reference_text.casefold()
        options.sort(key=lambda item: (not item[0].available, -sum(tag.casefold() in context for tag in item[0].tags), item[0].label))
        return [{**option.public(), "service": {"provider": adapter.provider_id, "model": adapter.model, "mode": adapter.mode}}
                for option, adapter in (options if limit is None else options[:max(0, limit)])]

    def _adapter(self, identity: VoiceIdentity, *, require_available: bool = True) -> VoiceHTTPAdapter:
        candidates = [adapter for adapter in self.adapters if (adapter.config.provider, adapter.config.model, adapter.config.engine)
                      == (identity.provider, identity.model, identity.engine)]
        if len(candidates) != 1:
            raise ProductionError("voice_unavailable", "固定声音的服务不可用；请选择并确认替代声音", requires_decision=True)
        candidates[0].option(identity, require_available=require_available)
        return candidates[0]

    def synthesize(self, binding: VoiceBinding, *, identity: VoiceIdentity, text: str,
                   segment_id: str, regenerate: bool = False) -> dict:
        adapter = self._adapter(identity, require_available=False)
        request = adapter.request(identity=identity, text=text, segment_id=segment_id, require_available=False)
        # Segment location is not acoustic identity: equal text in a different
        # scene or the preview can reuse an already paid audio asset in this work.
        key = fingerprint({"work_id": binding.work_id, "text": text, "voice": identity.model_dump(mode="json"),
                           "config": adapter.config.config_version, "format": adapter.config.response_format,
                           **({"explicit_regeneration": binding.operation_id} if regenerate else {})})
        pointer = self.root / f"{key}.json"
        with _lock(self.root / f"{key}.lock"):
            reused = pointer.is_file()
            if reused:
                operation_id = json.loads(pointer.read_text())["operation_id"]
                current = self.operations.get(operation_id)
                if current["work_id"] != binding.work_id:
                    raise ProductionError("voice_cache_conflict", "配音缓存不属于当前作品")
                if operation_id == binding.operation_id:
                    # A repeated intent cannot silently change text, voice or
                    # grant even if its previous result is already available.
                    self._reserve(binding, adapter, request)
                if current["state"] in {"sending", "submitted", "unknown"}:
                    current = self.operations.observe(operation_id, adapter)
                elif current["state"] == "reserved":
                    adapter.option(identity)
                    current = self.operations.submit(operation_id, adapter, owner_epoch=binding.owner_epoch)
            else:
                adapter.option(identity)
                current = self._reserve(binding, adapter, request)
                atomic_json(pointer, {"operation_id": binding.operation_id})
                current = self.operations.submit(binding.operation_id, adapter, owner_epoch=binding.owner_epoch)
            result = {"state": current["state"], "operation_id": current["id"], "segment_id": segment_id,
                      "reused": reused, "voice": identity.model_dump(mode="json"), "text_hash": fingerprint(text), "text": text}
            if current["state"] == "succeeded":
                receipt = adapter.observe(task_id=current["provider_task_id"], request_key=current["request_key"])
                if receipt.state != "succeeded":
                    raise ProductionError("voice_asset_missing", "已生成音频当前不可读取，未自动重做", requires_decision=True)
                result["asset"] = receipt.result
            elif current["state"] in {"unknown", "sending", "submitted"}:
                result["message"] = "声音服务结果待核实，保留原音色，不重复发送。"
            else:
                result["message"] = "本次声音生成未完成，保留原音色，请明确选择重试或替代声音。"
            return result

    def _reserve(self, binding: VoiceBinding, adapter: VoiceHTTPAdapter, request: dict) -> dict:
        return self.operations.reserve(operation_id=binding.operation_id, work_id=binding.work_id,
            run_id=binding.run_id, task_id=binding.task_id, grant_id=binding.grant_id, owner_epoch=binding.owner_epoch,
            kind="VOICE", provider=adapter.provider_id, model=adapter.model, mode=adapter.mode,
            config_version=adapter.config.config_version, request=request)


def sentence_segments(text: str) -> list[dict]:
    """Stable sentence identities survive an edit to a different sentence."""
    # Do not split decimal amounts, initials or common abbreviations into new
    # speech calls: that can change their pronunciation and meaning.
    parts, current = [], ""
    abbreviations = {"mr.", "mrs.", "ms.", "dr.", "prof.", "sr.", "jr.", "e.g.", "i.e.", "vs.", "etc."}
    index = 0
    while index < len(text):
        char = text[index]; current += char
        following = text[index + 1] if index + 1 < len(text) else ""
        boundary = char in "。！？!?\n"
        if char == "." and (not following or following.isspace()):
            last_word = current.split()[-1] if current.split() else ""
            boundary = last_word.casefold() not in abbreviations and not re.fullmatch(r"[A-Z]\.", last_word)
        if boundary:
            while index + 1 < len(text) and text[index + 1] in "。！？!?\"'”’」』）)]":
                index += 1; current += text[index]
            if current.strip():
                parts.append(current.strip())
            current = ""
        index += 1
    if current.strip():
        parts.append(current.strip())
    occurrences: dict[str, int] = {}
    result = []
    for part in parts:
        digest = fingerprint(part)
        occurrences[digest] = occurrences.get(digest, 0) + 1
        result.append({"segment_id": f"sentence-{digest[:20]}-{occurrences[digest]}", "text": part, "text_hash": digest})
    return result


def configured_voice_service(operations: OperationService, *, root: Path, settings: dict[str, str],
                             transport: httpx.BaseTransport | None = None) -> VoiceService:
    """Read opt-in JSON config; no inference from a generic TTS key or auto mode.

    EASEL_VOICE_SERVICES_JSON is an array of provider/model/engine/base_url,
    api_key_env (a key NAME in settings), mode and voices. A voice has voice_id,
    label and optional tags/languages/speed_range/instructions_supported. Secrets
    are never accepted inline or included in catalog/config_version receipts.
    """
    try:
        values = json.loads(settings.get("EASEL_VOICE_SERVICES_JSON", "[]") or "[]")
        if not isinstance(values, list) or len(values) > 30:
            raise ValueError("invalid service list")
        adapters = []
        for value in values:
            if set(value) - {"provider", "model", "engine", "base_url", "api_key_env", "mode", "voices", "response_format", "timeout_seconds"}:
                raise ValueError("unsupported service configuration")
            voices = []
            for item in value["voices"]:
                identity = VoiceIdentity(provider=value["provider"], model=value["model"], engine=value["engine"],
                                         voice_id=item["voice_id"], parameters=item.get("parameters", {}))
                speed_range = tuple(item["speed_range"]) if item.get("speed_range") else None
                if speed_range and (len(speed_range) != 2 or not 0 < speed_range[0] <= speed_range[1] <= 4):
                    raise ValueError("invalid speech parameter range")
                voices.append(VoiceOption(identity, item["label"], tuple(item.get("tags", [])), tuple(item.get("languages", [])),
                    speed_range, item.get("instructions_supported", False), item.get("available", True),
                    item.get("unavailable_reason", ""), item.get("fee_notice", VoiceOption.__dataclass_fields__["fee_notice"].default)))
            key_name = value.get("api_key_env", "")
            if key_name and (not re.fullmatch(r"[A-Z][A-Z0-9_]*", key_name) or not settings.get(key_name)):
                # Preserve configured options and their fixed identity, marked
                # unavailable, so the UI can explain without choosing another.
                voices = [VoiceOption(v.identity, v.label, v.tags, v.languages, v.speed_range, v.instructions_supported,
                                      False, "服务凭证尚未配置", v.fee_notice) for v in voices]
            config = SpeechConfig(provider=value["provider"], model=value["model"], engine=value["engine"],
                base_url=value["base_url"], config_version=fingerprint(value), voices=tuple(voices),
                api_key=settings.get(key_name, "") if key_name else "", mode=value.get("mode", "speech"),
                response_format=value.get("response_format", "wav"), timeout_seconds=value.get("timeout_seconds", 120))
            adapters.append(VoiceHTTPAdapter(config, root / "receipts" / fingerprint([config.provider, config.model, config.engine]), transport=transport))
        return VoiceService(operations, root / "cache", adapters)
    except (ValueError, TypeError, KeyError):
        raise ProductionError("voice_configuration_invalid", "声音服务配置格式无效，请检查具名服务配置") from None


def register_voice_asset(context, *, outputs: Path, result: dict) -> str:
    """Register a verified voice receipt under the task lease, with no new call."""
    from .contracts import canonical_json
    from .store import utc_now
    asset = result["asset"]
    path = Path(asset["path"])
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(outputs.resolve()) or file_sha256(path) != asset["sha256"]:
        raise ProductionError("voice_asset_missing", "声音资产不在当前受管输出中")
    path = stage_work_media(outputs, context.work_id, path)
    # Repeated equal sentences share paid bytes, but distinct editorial handles
    # preserve each intended occurrence instead of collapsing the narration.
    identifier = "voice_" + fingerprint([context.work_id, context.task_id, result["segment_id"],
                                        result["operation_id"], asset["sha256"]])[:32]
    metadata = {"schema_version": 1, "role": "voice", "voice": asset["voice"], "text_hash": asset["text_hash"],
                "segment_id": result["segment_id"], "narration_text": result["text"],
                "duration": asset["duration"], "config_version": asset["config_version"],
                "timing": {"duration_seconds": asset["duration"], "alignment": "sentence", "word_timestamps": None}}
    with context.transaction() as writer:
        previous = writer.execute("SELECT digest,work_id FROM artifacts WHERE id=?", (identifier,)).fetchone()
        if previous is not None:
            if previous["digest"] != asset["sha256"] or previous["work_id"] != context.work_id:
                raise ProductionError("voice_cache_conflict", "声音资产标识冲突")
            return identifier
        writer.execute("""INSERT INTO artifacts(id,work_id,run_id,operation_id,kind,storage_ref,digest,size_bytes,
            media_type,displayable,metadata_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,1,?,?)""",
            (identifier, context.work_id, context.run_id, result["operation_id"], "audio", str(path.resolve().relative_to(outputs.resolve())),
             asset["sha256"], path.stat().st_size, mimetypes.guess_type(path.name)[0] or "audio/wav", canonical_json(metadata), utc_now()))
        context.store.append_event(writer, context.work_id, "artifact_registered", {"artifact_id": identifier, "kind": "voice"}, run_id=context.run_id)
    return identifier


async def prepare_voice_segments(context, *, service: VoiceService, outputs: Path, identity: VoiceIdentity,
                                 grant_id: str, segments: list[dict], regenerate: bool = False) -> dict:
    """Prepare only supplied narration; each sentence remains a reusable asset.

    Input segment_id/text plus optional available_seconds. No timing stretch,
    source-audio replacement, or text rewrite is permitted here. The editor uses
    returned durations and planned scene slots; quality checks inspect the joins.
    """
    prepared = []
    for segment in segments:
        context.assert_current()
        binding = VoiceBinding("voice_" + fingerprint([context.task_id, segment["segment_id"], segment["text"], identity.model_dump()])[:32],
                               context.work_id, context.run_id, context.task_id, grant_id, context.owner_epoch)
        result = await asyncio.to_thread(service.synthesize, binding, identity=identity, text=segment["text"],
                                         segment_id=segment["segment_id"], regenerate=regenerate)
        if result["state"] != "succeeded":
            return {"state": result["state"], "segments": prepared, "pending": result}
        artifact_id = register_voice_asset(context, outputs=outputs, result=result)
        entry = {"segment_id": segment["segment_id"], "text": segment["text"], "artifact_id": artifact_id,
                 "duration": result["asset"]["duration"], "asset": result["asset"], "reused": result["reused"]}
        prepared.append(entry)
        if segment.get("available_seconds") is not None and entry["duration"] > segment["available_seconds"] + .02:
            return {"state": "needs_decision", "segments": prepared, "error_code": "voice_timing_exceeds_plan",
                    "message": "配音长于已确认时段，已保留音频，需明确调整时长或表达，未截断或加速。"}
    return {"state": "succeeded", "segments": prepared}


def voice_preview_handler(service_provider, *, outputs: Path):
    """Factory for Worker.handlers['voice_preview']; service may reload config."""
    from .worker import TaskResult
    async def handle(context):
        payload = context.payload
        voice = VoiceIdentity.model_validate(payload["voice"])
        result = await prepare_voice_segments(context, service=service_provider(), outputs=outputs, identity=voice,
            grant_id=payload["grant_id"], segments=[{"segment_id": "preview", "text": payload["text"]}],
            regenerate=payload.get("regenerate", False))
        if result["state"] == "succeeded":
            return TaskResult(result={"artifact_id": result["segments"][0]["artifact_id"],
                                      "reused": result["segments"][0]["reused"]}, work_state=payload.get("previous_work_state"))
        if result["state"] in {"sending", "unknown", "submitted"}:
            return TaskResult(state="waiting_external", result={"operation_id": result["pending"]["operation_id"]})
        return TaskResult(state="needs_decision", result=result, error=ProductionError("voice_not_completed",
            "固定音色试听未完成，保留当前设置，请确认重试或选择其他声音", requires_decision=True))
    return handle
