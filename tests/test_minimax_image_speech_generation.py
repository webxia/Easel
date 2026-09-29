from __future__ import annotations

import hashlib
import base64
import json
from io import BytesIO

import pytest
from PIL import Image

from easel.materials.application import generation_modalities as generation_module
from easel.materials.application.generation import GenerationApprovalRequired
from easel.materials.application.generation_modalities import MiniMaxImageSpeechGeneration
from easel.materials.domain import (
    ImageNeedSpec,
    MaterialNeed,
    MaterialPlan,
    MediaType,
    NeedImportance,
    NeedIntent,
    NeedScope,
    NeedScopeType,
    RightsStatus,
    TechnicalInfo,
    TechnicalStatus,
    VoiceIdentityRef,
    VoiceIdentitySource,
    VoiceNeedSpec,
)
from easel.materials.providers.http_support import HttpResponse
from easel.materials.providers.minimax_image import MiniMaxImageAdapter
from easel.materials.providers.minimax_speech import MiniMaxSpeechAdapter, MiniMaxSpeechResult
from easel.materials.store import AttemptMaterialStore


class FakeTransport:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def post(self, url, *, headers, body, timeout):
        self.calls.append((url, dict(headers), json.loads(body.decode("utf-8")), timeout))
        return HttpResponse(200, {}, json.dumps(self.payload).encode("utf-8"))

    def get(self, url, *, headers, timeout):
        raise AssertionError("unexpected GET")


def test_minimax_image_adapter_decodes_official_single_image_base64_array():
    transport = FakeTransport({
        "base_resp": {"status_code": 0},
        "data": {"image_base64": [base64.b64encode(b"fixture-image").decode("ascii")]},
    })
    adapter = MiniMaxImageAdapter("fixture-secret", transport=transport)

    result = adapter.generate("晨光中的工作室", aspect_ratio="9:16")

    assert result.image_bytes == b"fixture-image"
    url, headers, body, _ = transport.calls[0]
    assert url == "https://api.minimax.cn/v1/image_generation"
    assert headers["Authorization"] == "Bearer fixture-secret"
    assert body == {
        "model": "image-01", "prompt": "晨光中的工作室", "aspect_ratio": "9:16",
        "response_format": "base64", "n": 1, "prompt_optimizer": True,
    }


def test_minimax_image_adapter_rejects_unexpected_image_count():
    transport = FakeTransport({
        "base_resp": {"status_code": 0},
        "data": {"image_base64": ["aW1hZ2UtMQ==", "aW1hZ2UtMg=="]},
    })
    adapter = MiniMaxImageAdapter("fixture-secret", transport=transport)

    with pytest.raises(ValueError, match="exactly one image"):
        adapter.generate("晨光中的工作室")

    assert len(transport.calls) == 1


def test_minimax_speech_adapter_returns_preset_voice_mp3_bytes():
    transport = FakeTransport({
        "base_resp": {"status_code": 0}, "data": {"audio": b"fixture-mp3".hex()},
    })
    adapter = MiniMaxSpeechAdapter("fixture-secret", transport=transport)

    result = adapter.generate("这是冻结脚本中的旁白。")

    assert result.audio_bytes == b"fixture-mp3"
    url, headers, body, _ = transport.calls[0]
    assert url == "https://api.minimax.cn/v1/t2a_v2"
    assert headers["Authorization"] == "Bearer fixture-secret"
    assert body["model"] == "speech-2.8-hd"
    assert body["text"] == "这是冻结脚本中的旁白。"
    assert body["voice_setting"]["voice_id"] == "male-qn-qingse"
    assert body["audio_setting"]["format"] == "mp3"
    assert body["output_format"] == "hex"


class FakeInspector:
    def __init__(self, store):
        self.store = store

    def inspect_and_persist(self, asset):
        checked = asset.model_copy(update={
            "technical": TechnicalInfo(status=TechnicalStatus.PASSED, mime=asset.file.mime),
        })
        self.store.write_asset(checked)
        return checked


def _need(media_type, spec, need_id):
    return MaterialNeed(
        need_id=need_id, scope=NeedScope(type=NeedScopeType.SCENE, ref="scene-1"),
        media_type=media_type, role="narrative", intent=NeedIntent(description="素材需求描述"),
        constraints={"allow_generation": True}, importance=NeedImportance.REQUIRED,
        modality_spec=spec,
    )


def test_image_generation_requires_explicit_paid_approval_and_is_idempotent(tmp_path, monkeypatch):
    image = BytesIO()
    Image.new("RGB", (2, 2), "white").save(image, format="PNG")
    body = image.getvalue()
    need = _need(MediaType.IMAGE, ImageNeedSpec(aspect_ratio="9:16", visual_style="暖色纪实"), "need-image")
    plan = MaterialPlan(plan_id="plan-1", creation_id="creation-1", attempt_id="attempt-1", needs=(need,))
    store = AttemptMaterialStore(tmp_path)
    inspector = FakeInspector

    class FakeImage:
        model = "image-01"
        def generate(self, prompt, *, aspect_ratio):
            assert "Visual style: 暖色纪实" in prompt
            assert aspect_ratio == "9:16"
            return type("Result", (), {"image_bytes": body})()

    monkeypatch.setattr(generation_module, "TechnicalInspector", inspector)
    service = MiniMaxImageSpeechGeneration(image_adapter=FakeImage())
    with pytest.raises(GenerationApprovalRequired):
        service.generate(plan, need, store, request_id="image-1", confirmed_paid=False)
    result = service.generate(plan, need, store, request_id="image-1", confirmed_paid=True)
    repeated = service.generate(plan, need, store, request_id="image-1", confirmed_paid=True)

    assert result.asset.asset_id == repeated.asset.asset_id
    assert result.asset.rights.status is RightsStatus.UNKNOWN
    assert result.asset.technical.status is TechnicalStatus.PASSED
    assert result.record["input_sha256"] == hashlib.sha256(
        "素材需求描述\nVisual style: 暖色纪实".encode()
    ).hexdigest()


def test_voice_generation_is_bound_to_frozen_script_digest(tmp_path, monkeypatch):
    script = "这是经 truth review 的冻结旁白内容。"
    spec = VoiceNeedSpec(
        identity=VoiceIdentityRef(source=VoiceIdentitySource.EXPLICIT_USER, reference="普通预置音色"),
        text_ref="planning/SCRIPT.md", text_sha256=hashlib.sha256(script.encode()).hexdigest(),
    )
    need = _need(MediaType.AUDIO, spec, "need-voice").model_copy(update={
        "scope": NeedScope(type=NeedScopeType.GLOBAL, ref="program"),
    })
    plan = MaterialPlan(plan_id="plan-1", creation_id="creation-1", attempt_id="attempt-1", needs=(need,))
    store = AttemptMaterialStore(tmp_path)

    class FakeSpeech:
        model = "speech-2.8-hd"
        def generate(self, text):
            assert text == script
            return MiniMaxSpeechResult(self.model, "male-qn-qingse", b"fixture-audio", "mp3")

    monkeypatch.setattr(generation_module, "TechnicalInspector", FakeInspector)
    service = MiniMaxImageSpeechGeneration(speech_adapter=FakeSpeech())
    with pytest.raises(ValueError, match="hash-bound"):
        service.generate(plan, need, store, request_id="voice-bad", confirmed_paid=True, speech_text="改过的脚本")
    scene_need = need.model_copy(update={"scope": NeedScope(type=NeedScopeType.SCENE, ref="scene-1")})
    with pytest.raises(ValueError, match="global Need"):
        service.generate(
            plan.model_copy(update={"needs": (scene_need,)}), scene_need,
            store, request_id="voice-scene", confirmed_paid=True, speech_text=script,
        )

    result = service.generate(plan, need, store, request_id="voice-1", confirmed_paid=True, speech_text=script)
    assert result.asset.media_type is MediaType.AUDIO
    assert result.asset.file.mime == "audio/mpeg"
    assert result.asset.rights.status is RightsStatus.UNKNOWN
    assert result.record["input_sha256"] == spec.text_sha256
