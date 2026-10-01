"""Attempt-bound MiniMax image and speech generation intake."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from io import BytesIO

from easel.materials.application.generation import (
    GenerationApprovalRequired,
    GenerationRequestConflict,
    GeneratedMaterialResult,
)
from easel.materials.application.inspector import TechnicalInspector
from PIL import Image
from easel.materials.domain import (
    CandidateSource,
    FileInfo,
    ImageNeedSpec,
    MaterialAsset,
    MaterialNeed,
    MaterialPlan,
    MediaType,
    NeedScopeType,
    RightsInfo,
    RightsStatus,
    TechnicalInfo,
    TechnicalStatus,
    VoiceNeedSpec,
)
from easel.materials.providers import MiniMaxImageAdapter, MiniMaxSpeechAdapter
from easel.materials.store import AttemptMaterialStore, GenerationRecordNotFound
from easel.materials.application.voice_delivery import DEFAULT_DELIVERY, validate_voice_delivery, bind_voice_timing


def recoverable_generation_records(plan, bundle, store, *, gate_revision=None) -> list[dict]:
    """Only current known results, never uncertain submissions or another draft."""
    revision = hashlib.sha256(plan.to_json().encode()).hexdigest()
    needs = {n.need_id: hashlib.sha256(n.to_json().encode()).hexdigest() for n in plan.needs}
    assets = {a.asset_id for a in bundle.assets}
    return [r for r in store.list_generation_records()
            if r.get('schema') == 'easel-material-generation@1' and r.get('provider') == 'minimax'
            and r.get('modality') in {'image', 'voice'}
            and r.get('attempt_id') == plan.attempt_id and r.get('plan_id') == plan.plan_id
            and r.get('plan_revision') == revision and r.get('need_id') in needs
            and r.get('need_sha256') == needs[r['need_id']]
            and ((r.get('status') in {'RESULT_RECEIVED', 'RESULT_INTAKE_FAILED'} and r.get('received_asset'))
                 or (r.get('status') == 'COMPLETE' and (r.get('asset_id') not in assets
                     or (gate_revision is not None and gate_revision != bundle.revision
                         and r.get('bundle_intake', {}).get('after_revision') == bundle.revision))))]


class MiniMaxImageSpeechGeneration:
    """Generate an Image or script-bound Voice Asset and use ordinary Material intake."""

    def __init__(
        self,
        *,
        image_adapter: MiniMaxImageAdapter | None = None,
        speech_adapter: MiniMaxSpeechAdapter | None = None,
    ) -> None:
        self._image = image_adapter
        self._speech = speech_adapter

    def generate(
        self,
        plan: MaterialPlan,
        need: MaterialNeed,
        store: AttemptMaterialStore,
        *,
        request_id: str,
        confirmed_paid: bool,
        speech_text: str | None = None,
    ) -> GeneratedMaterialResult:
        with store.generation_lock(f"gen-{request_id}"):
            return self._generate(plan, need, store, request_id=request_id,
                                  confirmed_paid=confirmed_paid, speech_text=speech_text)

    def _generate(
        self, plan: MaterialPlan, need: MaterialNeed, store: AttemptMaterialStore, *,
        request_id: str, confirmed_paid: bool, speech_text: str | None,
    ) -> GeneratedMaterialResult:
        if not confirmed_paid:
            raise GenerationApprovalRequired("Explicit approval for possible MiniMax charges is required")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}", request_id):
            raise ValueError("Generation request id is invalid")
        if need not in plan.needs or need.media_type not in {MediaType.IMAGE, MediaType.AUDIO}:
            raise ValueError("MiniMax image/speech generation requires a matching Need in the supplied plan")

        is_voice = need.media_type is MediaType.AUDIO
        spec = need.modality_spec
        if is_voice and (not isinstance(spec, VoiceNeedSpec) or spec.identity is None):
            raise ValueError("MiniMax TTS requires an explicit provider-neutral Voice identity")
        if is_voice and need.scope.type is not NeedScopeType.GLOBAL:
            raise ValueError("MiniMax TTS currently requires a global Need bound to the complete frozen Script")
        if not is_voice and spec is not None and not isinstance(spec, ImageNeedSpec):
            raise ValueError("MiniMax image generation cannot serve this Need modality")
        if isinstance(spec, ImageNeedSpec) and spec.reference_asset_ids:
            raise ValueError("MiniMax image-01 adapter does not support Material reference-image inputs")
        if is_voice:
            if self._speech is None:
                raise ValueError("MiniMax speech adapter is not configured")
            if speech_text is None or not speech_text.strip() or len(speech_text) > 10_000:
                raise ValueError("A frozen Script of 1–10000 characters is required for MiniMax TTS")
            input_digest = hashlib.sha256(speech_text.encode("utf-8")).hexdigest()
            if spec.text_ref != "planning/SCRIPT.md" or spec.text_sha256 != input_digest:
                raise ValueError("Voice Need must match the hash-bound frozen planning Script")
            intent = need.intent.description.strip()
            model = self._speech.model
            speech_settings = validate_voice_delivery(need.constraints.get("voice_delivery", {}))
        else:
            if self._image is None:
                raise ValueError("MiniMax image adapter is not configured")
            intent = need.intent.description.strip()
            if isinstance(spec, ImageNeedSpec) and spec.visual_style:
                intent = f"{intent}\nVisual style: {spec.visual_style}"
            if not intent or len(intent) > 1500:
                raise ValueError("Image Need prompt must contain 1–1500 characters")
            input_digest = hashlib.sha256(intent.encode("utf-8")).hexdigest()
            model = self._image.model

        generation_id = f"gen-{request_id}"
        plan_revision = hashlib.sha256(plan.to_json().encode("utf-8")).hexdigest()
        record: dict[str, object] = {
            "schema": "easel-material-generation@1",
            "generation_id": generation_id,
            "attempt_id": plan.attempt_id,
            "plan_id": plan.plan_id,
            "plan_revision": plan_revision,
            "need_id": need.need_id,
            "need_sha256": hashlib.sha256(need.to_json().encode()).hexdigest(),
            "provider": "minimax",
            "model": model,
            "modality": "voice" if is_voice else "image",
            "input_sha256": input_digest,
            "operator_confirmed_paid": True,
            "operator_confirmed_at": datetime.now(timezone.utc).isoformat(),
            "status": "GENERATING",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "billing": {
                "status": "UNKNOWN",
                "may_be_billable": True,
                "pricing_reference": "https://platform.minimaxi.com/docs/guides/pricing-paygo",
            },
        }
        if is_voice:
            record.update(voice_id=self._speech.voice_id, speech_settings=speech_settings)
        try:
            previous = store.read_generation_record(generation_id)
        except GenerationRecordNotFound:
            previous = None
        if previous is not None:
            fields = ("attempt_id", "plan_id", "plan_revision", "need_id", "need_sha256", "model", "input_sha256", "modality")
            if any(previous.get(field) != record.get(field) for field in fields):
                raise GenerationRequestConflict("Generation request id is already bound to different input")
            if is_voice and (previous.get("voice_id") != record["voice_id"]
                    or previous.get("speech_settings", DEFAULT_DELIVERY) != speech_settings):
                raise GenerationRequestConflict("Generation request is bound to another voice or delivery setting")
            return self._resume_received(store, previous, speech_text=speech_text)
        if is_voice and spec.delivery_description and "voice_delivery" not in need.constraints:
            raise ValueError("旁白朗读描述尚未转成执行参数，需先补齐规划；未请求 TTS")
        store.write_generation_record(generation_id, record)

        try:
            if is_voice:
                assert self._speech is not None
                output = self._speech.generate(speech_text or "", **speech_settings)
                asset_id = "asset-" + hashlib.sha256(request_id.encode()).hexdigest()[:32]
                relative_path = store.write_asset_bytes(asset_id, "original.mp3", output.audio_bytes)
                digest = hashlib.sha256(output.audio_bytes).hexdigest()
                file = FileInfo(path=relative_path, sha256=digest, size=len(output.audio_bytes), mime="audio/mpeg")
                asset = MaterialAsset(
                    asset_id=asset_id,
                    media_type=MediaType.AUDIO,
                    file=file,
                    source=CandidateSource(kind="generative", provider="minimax", provider_asset_id=generation_id),
                    rights=RightsInfo(status=RightsStatus.UNKNOWN),
                    technical=TechnicalInfo(status=TechnicalStatus.PENDING),
                )
                record.update({"voice_id": output.voice_id, "audio_format": output.audio_format,
                               "received_timings": list(output.timings), "received_timing_error": output.timing_error})
            else:
                assert self._image is not None
                aspect_ratio = spec.aspect_ratio if isinstance(spec, ImageNeedSpec) and spec.aspect_ratio else "16:9"
                generated = self._image.generate(intent, aspect_ratio=aspect_ratio)
                with Image.open(BytesIO(generated.image_bytes)) as decoded:
                    image_format = (decoded.format or "").upper()
                mime = Image.MIME.get(image_format)
                extension = image_format.lower()
                if not mime or not mime.startswith("image/") or len(extension) > 8:
                    raise ValueError("MiniMax returned an unsupported image format")
                asset_id = "asset-" + hashlib.sha256(request_id.encode()).hexdigest()[:32]
                relative_path = store.write_asset_bytes(asset_id, f"original.{extension}", generated.image_bytes)
                digest = hashlib.sha256(generated.image_bytes).hexdigest()
                asset = MaterialAsset(
                    asset_id=asset_id,
                    media_type=MediaType.IMAGE,
                    file=FileInfo(path=relative_path, sha256=digest, size=len(generated.image_bytes), mime=mime),
                    source=CandidateSource(
                        kind="generative", provider="minimax", provider_asset_id=generation_id,
                        source_page="https://platform.minimaxi.com/docs/guides/image-generation",
                    ),
                    rights=RightsInfo(status=RightsStatus.UNKNOWN),
                    technical=TechnicalInfo(status=TechnicalStatus.PENDING),
                )

            # Receipt is durable before technical inspection or Asset registration.
            # This is the only evidence that permits local recovery without buying again.
            record.update(status="RESULT_RECEIVED", received_asset=asset.model_dump(mode="json"),
                          received_at=datetime.now(timezone.utc).isoformat())
            store.write_generation_record(generation_id, record)
            return self._resume_received(store, record, speech_text=speech_text)
        except Exception:
            record["status"] = "RESULT_INTAKE_FAILED" if record.get("received_asset") else "SUBMISSION_UNCERTAIN"
            record["failed_at"] = datetime.now(timezone.utc).isoformat()
            store.write_generation_record(generation_id, record)
            raise

    def resume_received(self, store: AttemptMaterialStore, generation_id: str, *,
                        speech_text: str | None = None) -> GeneratedMaterialResult:
        """Finish only a durable known result. Never load credentials or call a Provider."""
        with store.generation_lock(generation_id):
            record = store.read_generation_record(generation_id)
            if record.get('generation_id') != generation_id:
                raise GenerationRequestConflict('生成记录身份不一致，不能认领另一请求')
            return self._resume_received(store, record, speech_text=speech_text)

    def _resume_received(self, store, record, *, speech_text=None):
        generation_id = record["generation_id"]
        is_voice = record.get("modality") == "voice"
        if is_voice and (not isinstance(speech_text, str)
                or hashlib.sha256(speech_text.encode()).hexdigest() != record.get("input_sha256")):
            raise GenerationRequestConflict("本地旁白恢复必须使用原冻结脚本")
        if record.get("status") == "COMPLETE" and isinstance(record.get("asset_id"), str):
            asset = store.read_asset(record["asset_id"])
            expected = (record.get("asset_path"), record.get("asset_sha256"), record.get("asset_bytes"))
        elif record.get("status") in {"RESULT_RECEIVED", "RESULT_INTAKE_FAILED"} and isinstance(record.get("received_asset"), dict):
            asset = MaterialAsset.model_validate_json(json.dumps(record["received_asset"]))
            expected = (asset.file.path, asset.file.sha256, asset.file.size)
        else:
            raise GenerationRequestConflict(
                f"Generation request already has state ({record.get('status', 'unknown')}); inspect it before another paid request"
            )
        path = store.resolve_asset_locator(asset.file.path)
        expected_asset = 'asset-' + hashlib.sha256(generation_id.removeprefix('gen-').encode()).hexdigest()[:32]
        if (asset.asset_id != expected_asset or asset.source.provider_asset_id != generation_id
                or (asset.file.path, asset.file.sha256, asset.file.size) != expected
                or path.stat().st_size != asset.file.size
                or hashlib.sha256(path.read_bytes()).hexdigest() != asset.file.sha256):
            raise GenerationRequestConflict("Persisted generated Asset bytes are stale")
        if record.get("status") == "COMPLETE":
            return GeneratedMaterialResult(generation_id, generation_id, asset, record)
        try:
            # Asset metadata may have committed before a sidecar/receipt write
            # failed. Keep its accepted evidence instead of restoring PENDING.
            if path.with_name('asset.json').exists():
                saved = store.read_asset(asset.asset_id)
                if saved.file != asset.file or saved.source.provider_asset_id != generation_id:
                    raise GenerationRequestConflict('已登记素材与生成回执身份不一致')
                asset = saved
            if asset.technical.status is TechnicalStatus.PASSED:
                store.write_asset(asset)
            else:
                asset = TechnicalInspector(store).inspect_and_persist(asset)
            if asset.technical.status is not TechnicalStatus.PASSED:
                raise ValueError("已保存生成结果，本地技术检查尚未通过；只重试检查，不重新生成")
            if is_voice:
                record["voice_timing"] = bind_voice_timing(
                    speech_text, asset, tuple(record.get("received_timings", [])), record.get("received_timing_error"),
                )
            record.update({
                "status": "COMPLETE", "asset_id": asset.asset_id,
                "asset_path": asset.file.path, "asset_sha256": asset.file.sha256,
                "asset_bytes": asset.file.size, "asset_mime": asset.file.mime,
                "technical_status": asset.technical.status.value, "rights_status": asset.rights.status.value,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            })
            record.pop("failed_at", None)
            store.write_generation_record(generation_id, record)
            return GeneratedMaterialResult(generation_id, generation_id, asset, record)
        except Exception:
            record.update(status="RESULT_INTAKE_FAILED", failed_at=datetime.now(timezone.utc).isoformat())
            store.write_generation_record(generation_id, record)
            raise
