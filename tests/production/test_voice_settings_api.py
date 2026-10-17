"""Offline speech protocol plus real local preview and existing HTTP/worker path."""
import asyncio
import json
from pathlib import Path
import shutil
import time

from fastapi import FastAPI
from fastapi.testclient import TestClient
import httpx
from PIL import Image
import pytest

from easel.production.contracts import VoiceIdentity
from easel.production.media import file_sha256
from easel.production.operations import OperationService
from easel.production.service import WorkService
from easel.production.store import Store, utc_now
from easel.production.voice import configured_voice_service, voice_preview_handler
from easel.production.voice_tasks import VoiceTasks
from easel.production.worker import Worker
from web.production_api import create_router, production_error_handler
from web.production_settings_api import create_settings_router
from easel.production.errors import ProductionError
from .test_voice_subtitles import wav_bytes


@pytest.fixture
def environment(tmp_path):
    outputs = tmp_path / "outputs"; outputs.mkdir()
    profiles = tmp_path / "profiles"; profiles.mkdir(); (profiles / "本人").mkdir()
    (profiles / "本人" / "identity.md").write_text("本人经历", encoding="utf8")
    store = Store(outputs / "_production" / "production.sqlite3"); store.initialize()
    service = WorkService(store, outputs=outputs, profiles=profiles)
    config = {"EASEL_VOICE_SERVICES_JSON": json.dumps([{"provider": "fixture", "model": "speech", "engine": "speech-http-v1",
        "base_url": "https://speech.invalid/v1", "api_key_env": "FIXTURE_KEY",
        "voices": [{"voice_id": "fixed", "label": "测试声音", "tags": ["金融"]}]}]), "FIXTURE_KEY": "fixture-only"}
    calls = []
    def transport(request):
        calls.append(request); return httpx.Response(200, content=wav_bytes())
    voice = configured_voice_service(OperationService(store), root=outputs / "_production" / "voice", settings=config,
                                     transport=httpx.MockTransport(transport))
    app = FastAPI(); app.add_exception_handler(ProductionError, production_error_handler)
    app.include_router(create_router(lambda: service))
    app.include_router(create_settings_router(lambda: service, voice_provider=lambda: voice, settings_provider=lambda: config))
    client = TestClient(app)
    work = service.command("create", {"title": "金融学习", "profile_ref": "本人"}, command_id="create")
    return service, voice, calls, client, work["work_id"], config


def command(identifier, revision, payload):
    return {"command_id": identifier, "expected_revision": revision, "payload": payload}


@pytest.mark.skipif(not shutil.which("ffprobe"), reason="NOT_TESTED: ffprobe unavailable")
def test_preview_authorization_worker_audio_serving_and_restart_reuse(environment):
    service, voice, calls, client, work_id, config = environment
    option = client.get("/api/production/voice-options", params={"work_id": work_id}).json()["voices"][0]
    payload = {"voice": option["identity"], "text": "固定声音试听。", "services": [option["service"]]}
    denied = client.post(f"/api/production/works/{work_id}/voice-previews", json=command("denied", 1, {**payload, "services": []}))
    assert denied.status_code == 422 and not calls
    queued = client.post(f"/api/production/works/{work_id}/voice-previews", json=command("preview", 1, payload))
    assert queued.status_code == 202 and not calls
    worker = Worker(service.store, {"voice_preview": voice_preview_handler(lambda: voice, outputs=service.outputs)})
    asyncio.run(worker.run_once())
    snapshot = service.snapshot(work_id)
    task = snapshot["tasks"][0]
    assert task["state"] == "succeeded", task
    result = json.loads(task["result_json"])
    audio = client.get(f"/api/production/artifacts/{result['artifact_id']}/content")
    assert audio.status_code == 200 and audio.content[:4] == b"RIFF" and len(calls) == 1
    assert not snapshot["quota"]["IMAGE"]["used"] and not snapshot["quota"]["VIDEO"]["used"]
    replay = client.post(f"/api/production/works/{work_id}/voice-previews", json=command("preview", 1, payload))
    assert replay.json() == queued.json()
    again = client.post(f"/api/production/works/{work_id}/voice-previews", json=command("next-preview", snapshot["revision"], payload))
    assert again.status_code == 202
    asyncio.run(worker.run_once())
    assert len(calls) == 1
    latest = service.snapshot(work_id)
    assert all(t["state"] == "succeeded" for t in latest["tasks"])


def test_default_save_is_explicit_scoped_and_compare_and_swap(environment):
    service, _, _, client, work_id, _ = environment
    snapshot = client.get(f"/api/production/works/{work_id}/settings").json()
    profile_hash = snapshot["hashes"]["profile"]
    data = command("profile-default", 1, {"scope": "profile", "settings": {"subtitles": {"size": 72}}, "expected_settings_hash": profile_hash})
    saved = client.post(f"/api/production/works/{work_id}/settings", json=data)
    assert saved.status_code == 200 and saved.json()["scope"] == "profile"
    changed = client.get(f"/api/production/works/{work_id}/settings").json()
    assert changed["scopes"]["profile"]["subtitles"]["size"] == 72
    assert changed["scopes"]["work"] == {}  # Existing work snapshot is not silently rewritten.
    stale = client.post(f"/api/production/works/{work_id}/settings", json=command("stale", 2,
        {"scope": "profile", "settings": {"subtitles": {"size": 90}}, "expected_settings_hash": profile_hash}))
    assert stale.status_code == 409
    assert client.post(f"/api/production/works/{work_id}/settings", json=data).json() == saved.json()
    no_channel = client.post(f"/api/production/works/{work_id}/settings", json=command("no-channel", 2,
        {"scope": "channel", "settings": {"subtitles": {"size": 90}}}))
    assert no_channel.status_code == 422


@pytest.mark.skipif(not shutil.which("ffprobe"), reason="NOT_TESTED: ffprobe unavailable")
def test_real_subtitle_preview_serves_work_file_and_rejects_cross_work(environment):
    service, _, calls, client, work_id, config = environment
    font = next((Path(path) for path in ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf") if Path(path).is_file()), None)
    if font is None:
        pytest.skip("NOT_TESTED: no local fixture font")
    config["EASEL_SUBTITLE_FONTS_JSON"] = json.dumps({"Fixture": str(font)})
    source = service.outputs / "frame.png"; Image.new("RGB", (1080, 1920), "#334455").save(source)
    with service.store.transaction() as writer:
        writer.execute("INSERT INTO work_inputs(id,work_id,kind,usage,source_ref,digest,created_at) VALUES(?,?,'image','reference',?,?,?)",
                       ("frame", work_id, "frame.png", file_sha256(source), utc_now()))
    request = command("subtitle", 1, {"settings": {"font": "Fixture", "size": 80}, "text": "真实字幕", "frame_input_id": "frame"})
    preview = client.post(f"/api/production/works/{work_id}/subtitle-previews", json=request)
    assert preview.status_code == 200, preview.text
    data = preview.json()
    assert data["width"] == 1080 and data["height"] == 1920 and not calls
    image = client.get(f"/api/production/artifacts/{data['artifact_id']}/content")
    assert image.status_code == 200 and image.content.startswith(b"\x89PNG")
    other = service.command("create", {"title": "其他作品"}, command_id="other")["work_id"]
    denied = client.post(f"/api/production/works/{other}/subtitle-previews", json=command("cross-work", 1, request["payload"]))
    assert denied.status_code == 403
    client.post(f"/api/production/works/{work_id}/settings", json=command("change", 1, {"scope": "work", "settings": {"subtitles": {"size": 60}}}))
    assert client.post(f"/api/production/works/{work_id}/subtitle-previews", json=request).json() == data


def test_fixed_config_missing_secret_retains_identity_but_disables_voice(tmp_path):
    store = Store(tmp_path / "db.sqlite3"); store.initialize()
    config = {"EASEL_VOICE_SERVICES_JSON": json.dumps([{"provider": "provider", "model": "model", "engine": "engine",
        "base_url": "https://speech.invalid/v1", "api_key_env": "MISSING_KEY", "voices": [{"voice_id": "fixed", "label": "原声音"}]}])}
    service = configured_voice_service(OperationService(store), root=tmp_path / "voice", settings=config)
    option = service.catalog()[0]
    assert option["identity"]["voice_id"] == "fixed" and not option["available"]
    with pytest.raises(ProductionError):
        service._adapter(VoiceIdentity.model_validate(option["identity"]))


@pytest.mark.skipif(not shutil.which("ffprobe"), reason="NOT_TESTED: ffprobe unavailable")
def test_production_voice_preparation_preserves_original_and_reuses_sentences(environment):
    service, voice, calls, _, work_id, config = environment
    selected = voice.catalog()[0]
    plan = {"title": "测试", "summary": "固定文本", "script": "第一句。第二句。", "scenes": [
        {"id": "s1", "purpose": "说明", "visual": "素材", "narration": "第一句。第二句。", "duration_seconds": 1}],
        "settings": {"duration_seconds": 1, "audio_mode": "voice", "voice": selected["identity"], "subtitles": {"enabled": False}}}
    saved = service.command("plan", {"generate": False, "plan": plan}, command_id="plan", work_id=work_id, expected_revision=1)
    confirmed = service.command("confirm", {"plan_revision": 1, "plan_hash": saved["plan_hash"], "services": [selected["service"]]},
                                 command_id="confirm", work_id=work_id, expected_revision=2)
    worker = Worker(service.store, {})
    lease = worker.claim_next()
    with service.store.connection() as reader:
        task = reader.execute("SELECT id,kind FROM tasks WHERE run_id=?", (confirmed["run_id"],)).fetchone()
    context = worker._start(lease, task["id"], task["kind"])
    helper = VoiceTasks(service, lambda: voice, settings_provider=lambda: config)
    ids, outcome = asyncio.run(helper.prepare_assets(context, plan, []))
    assert outcome is None and len(ids) == 2 and len(calls) == 2
    reused, outcome = asyncio.run(helper.prepare_assets(context, plan, []))
    assert reused == ids and outcome is None and len(calls) == 2
    with service.store.transaction() as writer:
        writer.execute("INSERT INTO work_inputs(id,work_id,kind,usage,source_ref,digest,metadata_json,created_at) VALUES(?,?,'video','must_use','source.mp4',?,?,?)",
            ("original", work_id, "0" * 64, json.dumps({"schema_version": 1, "original_audio": True}), utc_now()))
    protected = {**plan, "scenes": [{**plan["scenes"][0], "required_input_ids": ["original"]}]}
    ids, outcome = asyncio.run(helper.prepare_assets(context, protected, []))
    assert ids == [] and outcome is None and len(calls) == 2
    too_short = {**plan, "scenes": [{**plan["scenes"][0], "duration_seconds": .1}]}
    ids, outcome = asyncio.run(helper.prepare_assets(context, too_short, []))
    assert len(ids) == 2 and outcome.error.code == "voice_timing_exceeds_plan" and len(calls) == 2
    repeated = {**plan, "scenes": [{**plan["scenes"][0], "narration": "第一句。第一句。"}]}
    repeated_ids, outcome = asyncio.run(helper.prepare_assets(context, repeated, []))
    assert len(repeated_ids) == 2 and len(set(repeated_ids)) == 2 and outcome is None and len(calls) == 2
    missing_font = {**plan, "settings": {**plan["settings"], "subtitles": {"enabled": True, "font": "unconfigured"}}}
    _, outcome = asyncio.run(helper.prepare_assets(context, missing_font, []))
    assert outcome.error.code == "font_unavailable" and len(calls) == 2


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="NOT_TESTED: ffmpeg unavailable")
def test_fixed_voice_and_caption_settings_reach_actual_renderer(environment):
    """Real render and speech protocol; scripted model is NOT semantic acceptance."""
    from easel.production.artifacts import register_file
    from easel.production.creation import CreationTasks
    from easel.production.editors import EditProject
    from easel.production.media import probe_media
    from easel.production.planning import PlanningTasks
    from easel.production.worker import TaskResult
    service, voice, calls, _, work_id, config = environment
    font = next((Path(path) for path in ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf") if Path(path).is_file()), None)
    if font is None:
        pytest.skip("NOT_TESTED: no local fixture font")
    config["EASEL_SUBTITLE_FONTS_JSON"] = json.dumps({"Fixture": str(font)})
    image = service.outputs / "fixture.png"; Image.new("RGB", (640, 360), "#336699").save(image)
    class Model:
        capabilities = frozenset({"text", "structured", "image", "audio", "tools", "video"})
        video_dialect = "qwen-omni-video-url"
        quality_chunk_seconds = 30
        async def complete(self, messages, tools, schema):
            if schema["title"] == "CreativeEdit":
                data = json.loads(messages[1]["content"][0]["text"])
                picture = next(item for item in data["artifacts"] if item["kind"] == "image")
                font_item = next(item for item in data["artifacts"] if item["kind"] == "font")
                sounds = [item for item in data["artifacts"] if item["metadata"].get("role") == "voice"]
                at = 0; clips = []; captions = []
                for index, sound in enumerate(sounds):
                    duration = sound["metadata"]["duration"]
                    clips.append({"clip_id": f"voice-{index}", "asset_id": sound["asset_id"], "role": "voice", "at": at, "duration": duration})
                    captions.append({"caption_id": f"cap-{index}", "text": sound["metadata"]["narration_text"],
                        "start": at, "end": at+duration, "font_asset_id": font_item["asset_id"], "size": 12, "color": "#FF0000"})
                    at += duration
                return {"content": json.dumps({"scenes": [{"scene_id": "s1", "asset_id": picture["asset_id"], "duration": 1}], "audio": clips, "captions": captions})}
            return {"content": json.dumps({"verdict": "pass", "factual_fidelity": "scripted test only", "style_consistency": "scripted",
                "narrative_coherence": "scripted", "audiovisual_alignment": "scripted", "findings": [], "limitations": []})}
    model_identity = {"provider": "direct-api", "model": "scripted", "mode": "structured"}
    planning = PlanningTasks(service, OperationService(service.store), Model(), model_identity, "fixture-1")
    creation = CreationTasks(service, planning, voice_tasks=VoiceTasks(service, lambda: voice, settings_provider=lambda: config))
    async def supply(context):
        artifact = register_file(service, context, image, kind="image", media_type="image/png", metadata={"source": "synthetic fixture"})
        return TaskResult(next_kind="edit", next_payload={"asset_ids": [artifact["id"]]})
    selected = voice.catalog()[0]
    plan = {"title": "一秒声音测试", "summary": "真实编码软件检查", "script": "第一句。第二句。",
        "scenes": [{"id": "s1", "purpose": "测试", "visual": "明确静态图片", "narration": "第一句。第二句。", "duration_seconds": 1}],
        "settings": {"duration_seconds": 1, "aspect_ratio": "9:16", "audio_mode": "voice", "voice": selected["identity"],
                     "subtitles": {"font": "Fixture", "size": 72, "color": "#FFFFFF", "background": "#000000"}}}
    saved = service.command("plan", {"generate": False, "plan": plan}, command_id="plan", work_id=work_id, expected_revision=1)
    service.command("confirm", {"plan_revision": 1, "plan_hash": saved["plan_hash"], "services": [selected["service"], model_identity]},
                    command_id="confirm", work_id=work_id, expected_revision=2)
    worker = Worker(service.store, {"supply": supply, "edit": creation.edit, "render": creation.render, "quality": creation.quality}, poll_interval=.01)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        asyncio.run(worker.run_once())
        snapshot = service.snapshot(work_id)
        if snapshot["state"] in {"reviewable", "needs_decision", "preview_needs_fix"}:
            break
        time.sleep(.05)
    output = next((item for item in snapshot["artifacts"] if item["kind"] == "output"), None)
    assert output, [(item["kind"], item["state"], item["error_json"]) for item in snapshot["tasks"]]
    path, _ = service.artifact_path(output["id"])
    assert probe_media(path)["audio"] and len(calls) == 2
    project = next(item for item in snapshot["artifacts"] if item["kind"] == "edit_project")
    project_path, _ = service.artifact_path(project["id"])
    parsed = EditProject.model_validate_json(project_path.read_text())
    assert len(parsed.audio) == 2 and all(caption.size == 72 and caption.color == "#FFFFFF" for caption in parsed.captions)
    assert all(caption.background == "#000000CC" for caption in parsed.captions)
    assert snapshot["accepted_output_id"] is None
