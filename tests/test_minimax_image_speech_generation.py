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
        return HttpResponse(200, {}, self.payload if isinstance(self.payload, bytes) else json.dumps(self.payload).encode("utf-8"))

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
    subtitle = {"text": "这是冻结脚本中的旁白。", "text_begin": 0, "text_end": 11,
                "time_begin": 250, "time_end": 2500}
    packets = [{"data": {"audio": b"partial-must-not-be-appended".hex(), "status": 1, "subtitle": subtitle}},
               {"base_resp": {"status_code": 0}, "data": {"audio": b"fixture-mp3".hex(), "status": 2,
                                                        "subtitles": [subtitle]}}]
    transport = FakeTransport("\n\n".join('data: ' + json.dumps(p) for p in packets).encode())
    adapter = MiniMaxSpeechAdapter("fixture-secret", transport=transport)

    result = adapter.generate("这是冻结脚本中的旁白。", pace_ratio=0.95, pitch_semitones=1, tone="neutral")

    assert result.audio_bytes == b"fixture-mp3"
    assert result.timings[0]['start_seconds'] == .25 and result.timings[0]['end_seconds'] == 2.5
    url, headers, body, _ = transport.calls[0]
    assert url == "https://api.minimax.cn/v1/t2a_v2"
    assert headers["Authorization"] == "Bearer fixture-secret"
    assert body["model"] == "speech-2.8-hd"
    assert body["text"] == "这是冻结脚本中的旁白。"
    assert body["voice_setting"] == {"voice_id": "male-qn-qingse", "speed": .95, "pitch": 1, "vol": 1, "emotion": "calm"}
    assert body["stream"] is True and body["subtitle_enable"] is True
    assert body["stream_options"]["exclude_aggregated_audio"] is False
    assert body["audio_setting"]["format"] == "mp3"
    assert body["output_format"] == "hex"


class FakeInspector:
    def __init__(self, store):
        self.store = store

    def inspect_and_persist(self, asset):
        checked = asset.model_copy(update={
            "technical": TechnicalInfo(status=TechnicalStatus.PASSED, mime=asset.file.mime,
                                       duration_seconds=3.0 if asset.media_type is MediaType.AUDIO else None),
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

    class FakeImage:
        model = "image-01"
        calls = 0
        def generate(self, prompt, *, aspect_ratio):
            self.calls += 1
            with pytest.raises(ValueError, match='仍在执行'):
                service.generate(plan, need, store, request_id='image-1', confirmed_paid=True)
            assert "Visual style: 暖色纪实" in prompt
            assert aspect_ratio == "9:16"
            return type("Result", (), {"image_bytes": body})()

    class InterruptedInspector(FakeInspector):
        def inspect_and_persist(self, asset):
            super().inspect_and_persist(asset)
            raise OSError('fixture local intake interruption')

    monkeypatch.setattr(generation_module, "TechnicalInspector", InterruptedInspector)
    adapter = FakeImage()
    service = MiniMaxImageSpeechGeneration(image_adapter=adapter)
    with pytest.raises(GenerationApprovalRequired):
        service.generate(plan, need, store, request_id="image-1", confirmed_paid=False)
    with pytest.raises(OSError, match='local intake'):
        service.generate(plan, need, store, request_id="image-1", confirmed_paid=True)
    assert store.read_generation_record('gen-image-1')['status'] == 'RESULT_INTAKE_FAILED'
    def no_repeat_inspection(*args):
        raise AssertionError('Accepted inspection must survive a receipt write interruption')
    monkeypatch.setattr(generation_module, 'TechnicalInspector', no_repeat_inspection)
    result = MiniMaxImageSpeechGeneration().resume_received(store, 'gen-image-1')
    repeated = service.generate(plan, need, store, request_id="image-1", confirmed_paid=True)

    assert result.asset.asset_id == repeated.asset.asset_id
    assert adapter.calls == 1
    assert result.asset.rights.status is RightsStatus.UNKNOWN
    assert result.asset.technical.status is TechnicalStatus.PASSED
    assert result.record["input_sha256"] == hashlib.sha256(
        "素材需求描述\nVisual style: 暖色纪实".encode()
    ).hexdigest()


@pytest.mark.parametrize('timing_error', [None, 'provider_timing_missing_or_invalid'])
def test_voice_generation_is_bound_to_frozen_script_digest(tmp_path, monkeypatch, timing_error):
    script = "这是经 truth review 的冻结旁白内容。"
    spec = VoiceNeedSpec(
        identity=VoiceIdentityRef(source=VoiceIdentitySource.EXPLICIT_USER, reference="普通预置音色"),
        text_ref="planning/SCRIPT.md", text_sha256=hashlib.sha256(script.encode()).hexdigest(),
    )
    need = _need(MediaType.AUDIO, spec, "need-voice").model_copy(update={
        "scope": NeedScope(type=NeedScopeType.GLOBAL, ref="program"),
        "constraints": {"allow_generation": True, "voice_delivery": {"pace_ratio": 0.95, "pitch_semitones": 0, "tone": "neutral"}},
    })
    plan = MaterialPlan(plan_id="plan-1", creation_id="creation-1", attempt_id="attempt-1", needs=(need,))
    store = AttemptMaterialStore(tmp_path)

    class FakeSpeech:
        model = "speech-2.8-hd"
        voice_id = "male-qn-qingse"
        calls = 0
        def generate(self, text, **settings):
            self.calls += 1
            assert text == script
            assert settings == need.constraints['voice_delivery']
            return MiniMaxSpeechResult(self.model, self.voice_id, b"fixture-audio", "mp3", (
                {"text": script, "start_seconds": .1, "end_seconds": 2.8,
                 "start_character": 0, "end_character": len(script)},), timing_error)

    monkeypatch.setattr(generation_module, "TechnicalInspector", FakeInspector)
    speech = FakeSpeech()
    service = MiniMaxImageSpeechGeneration(speech_adapter=speech)
    with pytest.raises(ValueError, match="hash-bound"):
        service.generate(plan, need, store, request_id="voice-bad", confirmed_paid=True, speech_text="改过的脚本")
    scene_need = need.model_copy(update={"scope": NeedScope(type=NeedScopeType.SCENE, ref="scene-1")})
    with pytest.raises(ValueError, match="global Need"):
        service.generate(
            plan.model_copy(update={"needs": (scene_need,)}), scene_need,
            store, request_id="voice-scene", confirmed_paid=True, speech_text=script,
        )

    class FailedInspection(FakeInspector):
        def inspect_and_persist(self, asset):
            failed = asset.model_copy(update={'technical': TechnicalInfo(status=TechnicalStatus.FAILED)})
            self.store.write_asset(failed)
            return failed
    monkeypatch.setattr(generation_module, 'TechnicalInspector', FailedInspection)
    with pytest.raises(ValueError, match='只重试检查'):
        service.generate(plan, need, store, request_id='voice-1', confirmed_paid=True, speech_text=script)
    with pytest.raises(ValueError, match='原冻结脚本'):
        MiniMaxImageSpeechGeneration().resume_received(store, 'gen-voice-1', speech_text='另一稿')
    monkeypatch.setattr(generation_module, 'TechnicalInspector', FakeInspector)
    result = MiniMaxImageSpeechGeneration().resume_received(store, 'gen-voice-1', speech_text=script)
    assert result.asset.media_type is MediaType.AUDIO
    assert result.asset.file.mime == "audio/mpeg"
    assert result.asset.rights.status is RightsStatus.UNKNOWN
    assert result.record["input_sha256"] == spec.text_sha256
    assert result.record['speech_settings'] == need.constraints['voice_delivery']
    assert result.record['voice_timing']['status'] == ('READY' if timing_error is None else 'UNAVAILABLE')
    assert result.record['voice_timing']['audio_sha256'] == result.asset.file.sha256
    assert result.record['voice_timing']['script_sha256'] == spec.text_sha256
    assert service.generate(plan, need, store, request_id='voice-1', confirmed_paid=True, speech_text=script).asset == result.asset
    speech.voice_id = 'another-preset'
    with pytest.raises(ValueError, match='another voice'):
        service.generate(plan, need, store, request_id='voice-1', confirmed_paid=True, speech_text=script)
    assert speech.calls == 1
    speech.voice_id = 'male-qn-qingse'
    replaced = b'replaced audio and metadata'
    store.resolve_asset_locator(result.asset.file.path).write_bytes(replaced)
    store.write_asset(result.asset.model_copy(update={'file': result.asset.file.model_copy(update={
        'sha256': hashlib.sha256(replaced).hexdigest(), 'size': len(replaced)})}))
    with pytest.raises(ValueError, match='Persisted generated Asset bytes are stale'):
        service.generate(plan, need, store, request_id='voice-1', confirmed_paid=True, speech_text=script)
    assert speech.calls == 1


@pytest.mark.parametrize('bad_subtitles', [None, [], [{'text': '一句', 'time_begin': float('nan')} ]])
def test_missing_provider_timing_preserves_successful_audio(bad_subtitles):
    transport = FakeTransport(('data: ' + json.dumps({'data': {
        'status': 2, 'audio': b'already-paid-audio'.hex(), 'subtitles': bad_subtitles}})).encode())
    result = MiniMaxSpeechAdapter('fixture-secret', transport=transport).generate('一句')
    assert result.audio_bytes == b'already-paid-audio'
    assert result.timings == () and result.timing_error == 'provider_timing_missing_or_invalid'
    assert len(transport.calls) == 1


def test_voice_alignment_rejects_truncation_overlap_and_stale_output(tmp_path):
    from easel.materials.application.voice_delivery import bind_voice_timing, authoring_voice_timings
    from easel.materials.domain import MaterialAsset, CandidateSource, FileInfo, RightsInfo, MaterialMatch
    from types import SimpleNamespace
    script = '第一句。第二句。'
    data = b'fixture audio'
    need = _need(MediaType.AUDIO, VoiceNeedSpec(), 'voice')
    plan = MaterialPlan(plan_id='p', creation_id='c', attempt_id='a', needs=(need,))
    asset = MaterialAsset(asset_id='voice', media_type=MediaType.AUDIO,
        file=FileInfo(path='materials/assets/voice/original.mp3', sha256=hashlib.sha256(data).hexdigest(), size=len(data), mime='audio/mpeg'),
        source=CandidateSource(kind='generative', provider='fixture', provider_asset_id='voice'),
        rights=RightsInfo(status=RightsStatus.UNKNOWN),
        technical=TechnicalInfo(status=TechnicalStatus.PASSED, duration_seconds=3))
    cues = ({'text': '第一句', 'start_character': 0, 'end_character': 3, 'start_seconds': 0., 'end_seconds': 1.2},
            {'text': '第二句', 'start_character': 4, 'end_character': 7, 'start_seconds': 1.3, 'end_seconds': 2.8})
    ready = bind_voice_timing(script, asset, cues)
    assert ready['status'] == 'READY'
    for bad in (cues[:1], (cues[0], {**cues[1], 'start_seconds': 1.1}),
                (cues[0], {**cues[1], 'end_seconds': 4.}), (cues[0], {**cues[1], 'text': '另一句。'})):
        assert bind_voice_timing(script, asset, bad)['status'] == 'INVALID'
    store = AttemptMaterialStore(tmp_path)
    store.write_generation_record('gen-voice', {'schema': 'easel-material-generation@1', 'status': 'COMPLETE',
        'asset_id': asset.asset_id, 'asset_sha256': asset.file.sha256,
        'need_sha256': hashlib.sha256(need.to_json().encode()).hexdigest(), 'voice_timing': ready})
    bundle = SimpleNamespace(assets=(asset,), matches=(MaterialMatch(need_id='voice', asset_id='voice', rank=1, score=1, qualified=True),))
    projection = authoring_voice_timings(plan, bundle, store, script)
    assert len(projection['assets']) == 1 and projection['unavailable_need_ids'] == []
    assert ''.join(cue['display_text'] for cue in projection['assets'][0]['cues']) == script
    assert authoring_voice_timings(plan, bundle, store, '改过的脚本')['unavailable_need_ids'] == ['voice']
    changed = asset.model_copy(update={'file': asset.file.model_copy(update={'sha256': '0' * 64})})
    bundle.assets = (changed,)
    assert authoring_voice_timings(plan, bundle, store, script)['unavailable_need_ids'] == ['voice']


def test_speech_stream_uncertain_result_and_unsupported_delivery_never_retries(tmp_path):
    transport = FakeTransport(b'data: {"data":{"status":1,"audio":"61"}}\n\n')
    adapter = MiniMaxSpeechAdapter('fixture-secret', transport=transport)
    with pytest.raises(ValueError, match='不支持'):
        adapter.generate('旁白', tone='whisper')
    assert not transport.calls
    with pytest.raises(ValueError, match='without a complete result'):
        adapter.generate('旁白')
    assert len(transport.calls) == 1
    script = '旁白'
    need = _need(MediaType.AUDIO, VoiceNeedSpec(
        identity=VoiceIdentityRef(source=VoiceIdentitySource.EXPLICIT_USER, reference='预置音色'),
        text_ref='planning/SCRIPT.md', text_sha256=hashlib.sha256(script.encode()).hexdigest()), 'voice')
    need = need.model_copy(update={'scope': NeedScope(type=NeedScopeType.GLOBAL, ref='program')})
    plan = MaterialPlan(plan_id='p', creation_id='c', attempt_id='a', needs=(need,))
    store = AttemptMaterialStore(tmp_path)
    service = MiniMaxImageSpeechGeneration(speech_adapter=adapter)
    with pytest.raises(ValueError, match='without a complete result'):
        service.generate(plan, need, store, request_id='uncertain', confirmed_paid=True, speech_text=script)
    assert store.read_generation_record('gen-uncertain')['status'] == 'SUBMISSION_UNCERTAIN'
    with pytest.raises(ValueError, match='already has state'):
        service.generate(plan, need, store, request_id='uncertain', confirmed_paid=True, speech_text=script)
    with pytest.raises(ValueError, match='already has state'):
        MiniMaxImageSpeechGeneration().resume_received(store, 'gen-uncertain', speech_text=script)
    assert len(transport.calls) == 2  # one adapter probe + one generation; no retry


@pytest.mark.parametrize('modality,expected', [('voice', '0.001400'), ('image', '0.025000'), ('video', '1.980000')])
def test_domestic_generation_quote_uses_current_contract_and_system_voice(modality, expected):
    from types import SimpleNamespace
    from easel.materials.providers.minimax_pricing import quote_generation, PRICE_URL
    settings = SimpleNamespace(base_url='https://api.minimax.cn', speech_model='speech-2.8-hd',
        speech_voice_id='male-qn-qingse', image_model='image-01', video_model='MiniMax-H3-Max')
    contract = """
## 语音
单价：元/万字符
| 同步 T2A | speech-2.8-hd | 说明 | 3.50 |
1 个汉字算 2 个字符
## 视频
**视频生成-输出价格**
| <div>MiniMax-H3-Max</div> | 480P | 按秒计费 | 0.33 元/秒 |
## 图像
单价：元/张
| image-01<br />image-01-live | 描述 | 0.025 |
"""
    def read(url):
        return contract if url == PRICE_URL else '| 1 | 中文 | `male-qn-qingse` | 青年 |'
    quote = quote_generation(settings, modality=modality, text='中文', seconds=6, resolution='480P', read=read)
    assert quote['currency'] == 'CNY' and quote['upper_estimate'] == expected
    assert all(len(item['sha256']) == 64 for item in quote['evidence'])
    if modality == 'voice':
        settings.speech_voice_id = 'unverified-custom-voice'
        with pytest.raises(ValueError, match='首次使用费用'):
            quote_generation(settings, modality=modality, text='中文', read=read)
    settings.base_url = 'https://api.minimax.io'
    with pytest.raises(ValueError, match='不能自动换算'):
        quote_generation(settings, modality=modality, read=read)


def test_voice_recognition_is_offline_unprompted_and_uses_measured_word_times(tmp_path, monkeypatch):
    import sys
    from types import SimpleNamespace
    from easel.materials.application import voice_delivery
    from easel.runtime_config import EaselRuntimeConfig
    calls = []
    class Recognizer:
        def __init__(self, path, **kwargs):
            assert kwargs == {'device': 'cpu', 'compute_type': 'int8', 'local_files_only': True}
            calls.append(path)
        def transcribe(self, path, **kwargs):
            assert kwargs == {'language': None, 'beam_size': 5, 'word_timestamps': True,
                              'vad_filter': True, 'condition_on_previous_text': False}
            return [SimpleNamespace(words=[SimpleNamespace(word='一句。', start=.23, end=1.71, probability=.93)])], SimpleNamespace(language='zh')
    monkeypatch.setitem(sys.modules, 'faster_whisper', SimpleNamespace(WhisperModel=Recognizer))
    # The adapter passes the actual file and no target script to the recognizer.
    report = voice_delivery.transcribe_local_voice(tmp_path / 'saved.mp3', tmp_path / 'local-model', None)
    assert report['words'][0] == {'text': '一句。', 'start_seconds': .23, 'end_seconds': 1.71, 'probability': .93}
    assert calls == [str(tmp_path / 'local-model')]
    monkeypatch.setattr(EaselRuntimeConfig, 'load', lambda: SimpleNamespace(get=lambda *a: str(tmp_path / 'absent-model')))
    import subprocess
    monkeypatch.setattr(subprocess, 'run', lambda *a, **kw: pytest.fail('missing model must not download or start recognition'))
    with pytest.raises(ValueError, match='本地语音识别模型未就绪'):
        voice_delivery.read_local_voice(tmp_path / 'saved.mp3', None)
