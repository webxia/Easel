from __future__ import annotations

import hashlib
import io
import json
import subprocess
from PIL import Image

from easel.materials.application.inspector import TechnicalInspector
from easel.materials.domain import (
    CandidateSource,
    FileInfo,
    MaterialAsset,
    MediaType,
    RightsInfo,
    RightsStatus,
    TechnicalStatus,
)
from easel.materials.store import AttemptMaterialStore


def image_bytes() -> bytes:
    stream = io.BytesIO()
    Image.new("RGBA", (16, 9), (255, 0, 0, 128)).save(stream, format="PNG")
    return stream.getvalue()


def stored_asset(store: AttemptMaterialStore, *, media_type: MediaType, data: bytes, filename: str, mime: str):
    asset_id = "asset-inspector-test"
    locator = store.write_asset_bytes(asset_id, filename, data)
    asset = MaterialAsset(
        asset_id=asset_id,
        media_type=media_type,
        file=FileInfo(path=locator, sha256=hashlib.sha256(data).hexdigest(), size=len(data), mime=mime),
        source=CandidateSource(kind="local", provider="local", provider_asset_id="fixture"),
        rights=RightsInfo(status=RightsStatus.UNKNOWN),
    )
    store.write_asset(asset)
    return asset


def test_inspects_generated_image_facts_and_persists_analysis(tmp_path) -> None:
    store = AttemptMaterialStore(tmp_path)
    asset = stored_asset(store, media_type=MediaType.IMAGE, data=image_bytes(), filename="image.png", mime="image/png")
    original_hash = asset.file.sha256

    result = TechnicalInspector(store).inspect_and_persist(asset)

    assert result.technical.status is TechnicalStatus.PASSED
    assert result.technical.width == 16
    assert result.technical.height == 9
    assert result.technical.mime == "image/png"
    assert result.technical.facts["alpha"] is True
    assert result.technical.facts["size_bytes"] == len(image_bytes())
    assert result.technical.facts["sha256"] == original_hash
    assert store.read_asset(asset.asset_id).technical == result.technical
    assert store.resolve_asset_locator(asset.file.path).read_bytes() == image_bytes()
    assert json.loads((tmp_path / "materials" / "assets" / asset.asset_id / "analysis.json").read_text())["technical"]["status"] == "PASSED"


def test_inspects_video_probe_facts_without_normalizing_or_transcoding(tmp_path, monkeypatch) -> None:
    store = AttemptMaterialStore(tmp_path)
    payload = b"fixture video bytes"
    asset = stored_asset(store, media_type=MediaType.VIDEO, data=payload, filename="video.mp4", mime="video/mp4")
    before = store.resolve_asset_locator(asset.file.path).read_bytes()
    observed = {}

    def fake_run(command, **kwargs):
        observed["command"] = command
        observed["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps({
            "format": {"duration": "12.5", "format_name": "mov,mp4,m4a,3gp,3g2,mj2"},
            "streams": [
                {"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080,
                 "avg_frame_rate": "30000/1001", "disposition": {"attached_pic": 0}},
                {"codec_type": "audio", "codec_name": "aac"},
            ],
        }), stderr="")

    monkeypatch.setattr("easel.materials.application.inspector.subprocess.run", fake_run)
    result = TechnicalInspector(store, ffprobe="ffprobe-fixture").inspect(asset)

    assert result.technical.status is TechnicalStatus.PASSED
    assert result.technical.duration_seconds == 12.5
    assert (result.technical.width, result.technical.height) == (1920, 1080)
    assert result.technical.facts["fps"] == 30000 / 1001
    assert result.technical.facts["codec"] == "h264"
    assert result.technical.facts["audio_codec"] == "aac"
    assert result.technical.has_audio is True
    assert result.technical.mime == "video/mp4"
    assert "ffmpeg" not in observed["command"][0]
    assert observed["kwargs"]["timeout"] == 30.0
    assert store.resolve_asset_locator(asset.file.path).read_bytes() == before


def test_inspects_audio_stream_facts(tmp_path, monkeypatch) -> None:
    store = AttemptMaterialStore(tmp_path)
    asset = stored_asset(store, media_type=MediaType.AUDIO, data=b"audio", filename="audio.wav", mime="audio/wav")
    monkeypatch.setattr(
        "easel.materials.application.inspector.subprocess.run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 0, stdout=json.dumps({
            "format": {"duration": "2.75", "format_name": "wav"},
            "streams": [{"codec_type": "audio", "codec_name": "pcm_s16le"}],
        }), stderr=""),
    )

    result = TechnicalInspector(store, ffprobe="ffprobe-fixture").inspect(asset)
    assert result.technical.status is TechnicalStatus.PASSED
    assert result.technical.duration_seconds == 2.75
    assert result.technical.has_audio is True
    assert result.technical.facts["codec"] == "pcm_s16le"
    assert result.technical.mime == "audio/wav"


def test_corrupt_image_is_an_explicit_failed_inspection(tmp_path) -> None:
    store = AttemptMaterialStore(tmp_path)
    asset = stored_asset(store, media_type=MediaType.IMAGE, data=b"not an image", filename="bad.png", mime="image/png")
    result = TechnicalInspector(store).inspect(asset)
    assert result.technical.status is TechnicalStatus.FAILED
    assert result.technical.facts["inspection_error"] == "corrupt_or_unsupported_image"


def test_probe_failure_timeout_invalid_json_and_missing_stream_are_explicit(tmp_path, monkeypatch) -> None:
    store = AttemptMaterialStore(tmp_path)
    asset = stored_asset(store, media_type=MediaType.VIDEO, data=b"video", filename="bad.mp4", mime="video/mp4")

    monkeypatch.setattr(
        "easel.materials.application.inspector.subprocess.run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 1, stdout="", stderr="path must not leak"),
    )
    assert TechnicalInspector(store, ffprobe="ffprobe-fixture").inspect(asset).technical.facts["inspection_error"] == "ffprobe_rejected_media"

    def timeout(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])
    monkeypatch.setattr("easel.materials.application.inspector.subprocess.run", timeout)
    assert TechnicalInspector(store, ffprobe="ffprobe-fixture").inspect(asset).technical.facts["inspection_error"] == "ffprobe_timeout"

    monkeypatch.setattr(
        "easel.materials.application.inspector.subprocess.run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 0, stdout="not json", stderr=""),
    )
    assert TechnicalInspector(store, ffprobe="ffprobe-fixture").inspect(asset).technical.facts["inspection_error"] == "ffprobe_invalid_json"

    monkeypatch.setattr(
        "easel.materials.application.inspector.subprocess.run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 0, stdout='{"streams":[]}', stderr=""),
    )
    assert TechnicalInspector(store, ffprobe="ffprobe-fixture").inspect(asset).technical.facts["inspection_error"] == "video_stream_missing"


def test_missing_probe_and_hash_mismatch_fail_closed(tmp_path, monkeypatch) -> None:
    store = AttemptMaterialStore(tmp_path)
    asset = stored_asset(store, media_type=MediaType.VIDEO, data=b"video", filename="video.mp4", mime="video/mp4")
    no_probe = TechnicalInspector(store, ffprobe="")
    assert no_probe.inspect(asset).technical.facts["inspection_error"] == "ffprobe_unavailable"
    monkeypatch.setattr("easel.materials.application.inspector.subprocess.run", lambda *args, **kwargs: None)
    changed = asset.model_copy(update={"file": asset.file.model_copy(update={"sha256": "0" * 64})})
    result = TechnicalInspector(store, ffprobe="ffprobe-fixture").inspect(changed)
    assert result.technical.status is TechnicalStatus.FAILED
    assert result.technical.facts["inspection_error"] == "content_hash_mismatch"
