import io
import json
import math
from pathlib import Path
import shutil
import struct
import wave

import httpx
from PIL import Image, ImageChops
import pytest

from easel.production.contracts import SubtitleSettings, VoiceIdentity
from easel.production.editors.base import AssetManifest, EditError, MediaAsset
from easel.production.errors import Conflict, ProductionError
from easel.production.media import caption_image, file_sha256
from easel.production.operations import OperationService
from easel.production.settings import resolve_settings, settings_save_request
from easel.production.store import Store
from easel.production.subtitles import SubtitleService, caption_from_settings
from easel.production.voice import SpeechConfig, VoiceBinding, VoiceHTTPAdapter, VoiceOption, VoiceService, sentence_segments
from .test_operations import owned_request


def wav_bytes():
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as stream:
        stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(24000)
        stream.writeframes(b"".join(struct.pack("<h", int(4000 * math.sin(i * 440 * 2 * math.pi / 24000))) for i in range(4800)))
    return buffer.getvalue()


@pytest.fixture
def speech(tmp_path):
    if not shutil.which("ffprobe"):
        pytest.skip("NOT_TESTED: local ffprobe unavailable")
    store = Store(tmp_path / "production.sqlite3"); store.initialize()
    ops = OperationService(store, clock=lambda: 1000)
    spec = owned_request(store, kind="VOICE", limit=0)
    binding = VoiceBinding(**{key: spec[key] for key in VoiceBinding.__dataclass_fields__})
    voice = VoiceIdentity(provider="fixture", model="voice", voice_id="fixed-a", engine="speech-http-v1")
    calls = []
    def transport(request):
        calls.append(request)
        return httpx.Response(200, content=wav_bytes(), headers={"Content-Type": "audio/wav"})
    config = SpeechConfig(provider="fixture", model="voice", engine="speech-http-v1", base_url="https://speech.invalid/v1",
        config_version="fixture-1", voices=(VoiceOption(voice, "固定音色", tags=("金融",), speed_range=(.5, 2)),),
        mode="normal", api_key="test-secret-never-persist")
    adapter = VoiceHTTPAdapter(config, tmp_path / "voice", transport=httpx.MockTransport(transport))
    service = VoiceService(ops, tmp_path / "cache", [adapter])
    return store, ops, binding, voice, calls, adapter, service


def test_voice_protocol_and_same_text_reuse_do_not_consume_image_video_quota(speech):
    store, ops, binding, voice, calls, adapter, service = speech
    result = service.synthesize(binding, identity=voice, text="同一段试听。", segment_id="preview")
    assert result["state"] == "succeeded" and result["asset"]["duration"] == .2
    other = VoiceBinding(**{**binding.__dict__, "operation_id": "next-scene"})
    cached = service.synthesize(other, identity=voice, text="同一段试听。", segment_id="scene-a")
    assert cached["reused"] and cached["asset"] == result["asset"]
    assert len(calls) == 1 and calls[0].url == "https://speech.invalid/v1/audio/speech"
    assert json.loads(calls[0].content) == {"model": "voice", "voice": "fixed-a", "input": "同一段试听。", "response_format": "wav"}
    assert calls[0].headers["Authorization"] == "Bearer test-secret-never-persist"
    assert all(value["used"] == 0 for value in ops.quota(binding.work_id).values())
    for file in adapter.root.rglob("*.json"):
        assert "test-secret-never-persist" not in file.read_text()
    assert "test-secret-never-persist" not in repr(adapter.config)
    assert service.catalog(reference_text="金融频道")[0]["identity"] == voice.model_dump()


def test_unknown_voice_is_not_resent_or_switched(speech):
    _, _, binding, voice, calls, adapter, service = speech
    def timeout(request):
        calls.append(request)
        raise httpx.ReadTimeout("redacted transport body")
    adapter.transport = httpx.MockTransport(timeout)
    result = service.synthesize(binding, identity=voice, text="结果不明。", segment_id="one")
    assert result["state"] == "unknown"
    again = service.synthesize(VoiceBinding(**{**binding.__dict__, "operation_id": "new-command"}), identity=voice, text="结果不明。", segment_id="one")
    assert again["state"] == "unknown" and len(calls) == 1
    assert again["voice"] == voice.model_dump() and "redacted" not in json.dumps(again)


def test_voice_identity_and_operation_intent_cannot_change(speech):
    _, _, binding, voice, calls, _, service = speech
    service.synthesize(binding, identity=voice, text="原句。", segment_id="one")
    with pytest.raises(Conflict):
        service.synthesize(binding, identity=voice, text="改写。", segment_id="one")
    with pytest.raises(ProductionError, match="固定声音"):
        service.synthesize(binding, identity=voice.model_copy(update={"engine": "other-engine"}), text="原句。", segment_id="one")
    with pytest.raises(ProductionError, match="不支持"):
        service.synthesize(binding, identity=voice.model_copy(update={"parameters": {"emotion": "happy"}}), text="原句。", segment_id="one")
    assert len(calls) == 1


def test_explicit_regeneration_new_call_and_sentence_edit_reuses_unchanged_audio(speech):
    _, _, binding, voice, calls, _, service = speech
    old = sentence_segments("第一句。第二句。")
    changed = sentence_segments("第一句。新第二句。")
    assert old[0] == changed[0] and old[1]["segment_id"] != changed[1]["segment_id"]
    precise = sentence_segments("收益是 3.14%。Dr. Smith agreed. 第二句。")
    assert [item["text"] for item in precise] == ["收益是 3.14%。", "Dr. Smith agreed.", "第二句。"]
    for index, segment in enumerate(old + changed):
        service.synthesize(VoiceBinding(**{**binding.__dict__, "operation_id": f"sentence-{index}"}),
                           identity=voice, text=segment["text"], segment_id=segment["segment_id"])
    assert len(calls) == 3
    service.synthesize(VoiceBinding(**{**binding.__dict__, "operation_id": "creator-regenerate"}), identity=voice,
                       text=old[0]["text"], segment_id=old[0]["segment_id"], regenerate=True)
    assert len(calls) == 4


def test_removed_audio_does_not_silently_generate_again(speech):
    _, _, binding, voice, calls, _, service = speech
    result = service.synthesize(binding, identity=voice, text="原句。", segment_id="one")
    Path(result["asset"]["path"]).unlink()
    with pytest.raises(ProductionError) as error:
        service.synthesize(binding, identity=voice, text="原句。", segment_id="one")
    assert error.value.code == "voice_asset_missing" and len(calls) == 1


def test_preview_authorization_is_scoped_to_named_task(speech):
    store, _, binding, voice, calls, _, service = speech
    with store.transaction() as conn:
        conn.execute("UPDATE authorization_grants SET purpose='preview',target_ref='different',allow_ai=0 WHERE id=?", (binding.grant_id,))
        conn.execute("UPDATE tasks SET kind='voice_preview' WHERE id=?", (binding.task_id,))
    with pytest.raises(ProductionError, match="试听授权"):
        service.synthesize(binding, identity=voice, text="试听。", segment_id="preview")
    assert not calls
    with store.transaction() as conn:
        conn.execute("UPDATE authorization_grants SET target_ref=? WHERE id=?", (binding.task_id, binding.grant_id))
    assert service.synthesize(binding, identity=voice, text="试听。", segment_id="preview")["state"] == "succeeded"


def test_settings_scope_precedence_snapshot_and_voice_identity():
    a = {"provider": "a", "model": "a", "voice_id": "one", "engine": "a"}
    b = {"provider": "b", "model": "b", "voice_id": "two", "engine": "b"}
    profile = {"voice": a, "subtitles": {"size": 40, "color": "#FFFFFF"}}
    channel = {"voice": b, "subtitles": {"size": 60}}
    work = {"subtitles": {"position": "top"}}
    resolved = resolve_settings(work=work, channel=channel, profile=profile)
    assert resolved["settings"]["voice"]["provider"] == "b"
    assert resolved["settings"]["subtitles"] == {"size": 60, "color": "#FFFFFF", "position": "top"}
    channel["subtitles"]["size"] = 80
    assert resolved["settings"]["subtitles"]["size"] == 60
    assert resolve_settings(work={"voice": None}, profile=profile)["settings"]["voice"] is None
    with pytest.raises(ProductionError):
        settings_save_request(scope="channel", settings=work)
    assert settings_save_request(scope="profile", settings=work, profile_ref="me")["target_ref"] == "me"


def test_subtitle_preview_and_export_use_identical_layer_and_never_change_text(tmp_path):
    if not shutil.which("ffprobe"):
        pytest.skip("NOT_TESTED: ffprobe unavailable")
    font = next((Path(path) for path in ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf") if Path(path).is_file()), None)
    if font is None:
        pytest.skip("NOT_TESTED: no configured local test font")
    assets = tmp_path / "assets"; assets.mkdir()
    shutil.copyfile(font, assets / "fixture.ttf")
    Image.new("RGB", (1080, 1920), "#315579").save(assets / "frame.png")
    manifest = AssetManifest(root=assets, assets={name: MediaAsset(locator=filename, sha256=file_sha256(assets / filename), kind=kind)
        for name, filename, kind in (("frame", "frame.png", "image"), ("font", "fixture.ttf", "font"))})
    settings = SubtitleSettings(font="Fixture", size=76, background="#000000")
    text = "真实画面 / Literal {text}"
    service = SubtitleService(tmp_path / "preview")
    result = service.preview(manifest=manifest, frame_asset_id="frame", at=0, settings=settings, text=text, fonts={"Fixture": "font"})
    caption = caption_from_settings(settings, caption_id="real", text=text, start=0, end=1, fonts={"Fixture": "font"})
    layer = caption_image(caption, assets / "fixture.ttf", width=1080, height=1920, destination=tmp_path / "export-layer.png")
    with Image.open(assets / "frame.png") as source, Image.open(layer) as overlay, Image.open(result["path"]) as preview:
        expected = source.convert("RGBA"); expected.alpha_composite(overlay)
        assert ImageChops.difference(expected, preview).getbbox() is None
    assert caption.text == text
    assert service.preview(manifest=manifest, frame_asset_id="frame", at=0, settings=settings, text=text, fonts={"Fixture": "font"})["reused"]
    with pytest.raises(EditError, match="not configured"):
        service.preview(manifest=manifest, frame_asset_id="frame", at=0, settings=settings, text=text, fonts={})
    disabled = service.preview(manifest=manifest, frame_asset_id="frame", at=0,
        settings=settings.model_copy(update={"enabled": False}), text=text, fonts={})
    with Image.open(disabled["path"]) as image, Image.open(assets / "frame.png") as original:
        assert ImageChops.difference(image.convert("RGB"), original).getbbox() is None

    single = settings.model_copy(update={'single_line': True, 'size': 40, 'background': 'transparent'})
    long_text = '按真实字体宽度分段显示，口播字幕每次只出现一行。' * 8
    result = service.preview(manifest=manifest, frame_asset_id='frame', at=0,
        settings=single, text=long_text, fonts={'Fixture': 'font'})
    assert result['cue_count'] > 1 and '\n' not in result['preview_text']
    first = caption_from_settings(single, caption_id='preview', text=result['preview_text'], start=0, end=1, fonts={'Fixture':'font'})
    layer = caption_image(first, assets/'fixture.ttf', width=1080, height=1920, destination=tmp_path/'single.png')
    with Image.open(assets/'frame.png') as source, Image.open(layer) as overlay, Image.open(result['path']) as preview:
        expected=source.convert('RGBA'); expected.alpha_composite(overlay)
        assert ImageChops.difference(expected,preview).getbbox() is None
    cached=service.preview(manifest=manifest, frame_asset_id='frame', at=0,
        settings=single,text=long_text,fonts={'Fixture':'font'})
    assert cached['reused'] and cached['preview_text']==result['preview_text']


def test_compiled_request_changes_audio_cache_identity(speech,monkeypatch):
    _,_,binding,voice,calls,adapter,service=speech
    original=adapter.request
    def request(**kwargs):return {**original(**kwargs),'compiler_version':'new'}
    first=service.synthesize(binding,identity=voice,text='同稿。',segment_id='one')
    monkeypatch.setattr(adapter,'request',request)
    other=VoiceBinding(**{**binding.__dict__,'operation_id':'compiled-new'})
    changed=service.synthesize(other,identity=voice,text='同稿。',segment_id='one')
    assert not changed['reused'] and len(calls)==2
    again=service.synthesize(other,identity=voice,text='同稿。',segment_id='one')
    assert again['reused'] and len(calls)==2
    monkeypatch.setattr(adapter,'request',original)
    restored=service.synthesize(VoiceBinding(**{**binding.__dict__,'operation_id':'restored'}),identity=voice,text='同稿。',segment_id='another')
    assert restored['asset']==first['asset'] and len(calls)==2
