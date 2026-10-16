from pathlib import Path

import pytest
from pydantic import ValidationError

from easel.production.editors import (AssetManifest, AudioClip, Caption, Crop, EditError,
                                     EditProject, FFmpegEditor, MediaAsset, Scene, assert_local_revision)
from easel.production.media import local_path, process_environment


def project(**changes):
    values = dict(work_id="work-1", plan_revision=1, revision=1, duration=2,
                  scenes=(Scene(scene_id="s1", asset_id="clip", duration=2),))
    values.update(changes)
    return EditProject(**values)


def test_exact_timeline_and_four_audio_modes():
    with pytest.raises(ValidationError):
        project(duration=3)
    with pytest.raises(ValidationError):
        project(width=1080, height=1080)
    with pytest.raises(ValidationError):
        project(duration=901)
    with pytest.raises(ValidationError):
        project(audio_mode="voice")
    music = AudioClip(clip_id="bgm", asset_id="m", role="music", at=0, duration=2, gain=0)
    voice = AudioClip(clip_id="voice", asset_id="v", role="voice", at=0, duration=2)
    assert project(audio_mode="music", audio=(music,)).audio[0].gain == 0
    assert project(audio_mode="voice", audio=(voice,)).audio_mode == "voice"
    assert project(audio_mode="mixed", audio=(voice, music)).audio_mode == "mixed"
    with pytest.raises(ValidationError):
        project(audio=(music,))
    with pytest.raises(ValidationError):
        AudioClip(clip_id="v", asset_id="v", role="voice", at=0, duration=1, loop=True)


def test_visual_revision_preserves_native_audio_timing_text_and_media():
    base = project(audio_mode="voice", scenes=(Scene(scene_id="s1", asset_id="clip", duration=2, source_audio=True),),
                   captions=(Caption(caption_id="c1", text="Keep my words", start=0, end=2, font_asset_id="font"),))
    revised = base.model_copy(update={"revision": 2, "scenes": (
        base.scenes[0].model_copy(update={"crop": Crop(x=0.1, width=0.8)}),)})
    assert_local_revision(base, revised, allowed={"visual"})
    bad = revised.model_copy(update={"scenes": (revised.scenes[0].model_copy(update={"source_audio": False}),)})
    with pytest.raises(EditError, match="protected"):
        assert_local_revision(base, bad, allowed={"visual"})
    bad = revised.model_copy(update={"captions": (base.captions[0].model_copy(update={"text": "Changed"}),)})
    with pytest.raises(EditError, match="protected"):
        assert_local_revision(base, bad, allowed={"visual", "captions"})
    with pytest.raises(EditError):
        assert_local_revision(base, base, allowed={"everything"})


def test_dissolve_uses_explicit_overlap():
    p = project(duration=3.5, scenes=(Scene(scene_id="s1", asset_id="a", duration=2),
                                    Scene(scene_id="s2", asset_id="b", duration=2,
                                          transition="dissolve", transition_seconds=0.5)))
    assert p.scene_starts() == (0, 1.5)
    with pytest.raises(ValidationError):
        Scene(scene_id="s1", asset_id="a", duration=1, transition="dissolve")


@pytest.mark.parametrize("locator", ["../secret.mp4", "/etc/passwd", "https://x/a.mp4", "file:a.mp4",
                                     "a/../b.mp4", "a//b.mp4", "a\\b.mp4"])
def test_manifest_rejects_unsafe_locators(tmp_path, locator):
    with pytest.raises(EditError):
        local_path(tmp_path, locator)


def test_symlink_alias_and_secret_environment_are_rejected(tmp_path, monkeypatch):
    actual = tmp_path / "source.mp4"
    actual.write_bytes(b"media")
    alias = tmp_path / "alias.mp4"
    try:
        alias.symlink_to(actual)
    except OSError:
        pytest.skip("host does not allow creating test symlinks")
    with pytest.raises(EditError):
        local_path(tmp_path, "alias.mp4")
    monkeypatch.setenv("MINIMAX_API_KEY", "not-a-real-secret")
    monkeypatch.setenv("HTTPS_PROXY", "https://example.invalid")
    env = process_environment(tmp_path / "home")
    assert "MINIMAX_API_KEY" not in env and "HTTPS_PROXY" not in env
    assert env["HOME"] == str(tmp_path / "home")


def test_missing_backend_and_unrequested_features_are_explicit(tmp_path):
    editor = FFmpegEditor(tmp_path / "jobs", ffmpeg="easel-nonexistent-ffmpeg")
    assert editor.capabilities()["available"] is False
    result = editor.check(project(), AssetManifest(root=tmp_path, assets={}))
    assert not result.valid
    with pytest.raises(EditError):
        editor.build(project(), AssetManifest(root=tmp_path, assets={}), job_id="../../bad")
