"""Actual local media tests. All picture/audio sources are synthetic test fixtures."""
import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

from easel.production.editors import (AssetManifest, AudioClip, Caption, Crop, EditError,
                                     EditProject, FFmpegEditor, MediaAsset, Scene, assert_local_revision)
from easel.production.media import file_sha256, probe_media


FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")
pytestmark = pytest.mark.skipif(not (FFMPEG and FFPROBE), reason="real FFmpeg/ffprobe unavailable; media support is NOT_TESTED")


def run(args):
    subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", *args],
                   check=True, capture_output=True, timeout=120)


@pytest.fixture(scope="module")
def sources(tmp_path_factory):
    root = tmp_path_factory.mktemp("render-media")
    run(["-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30:duration=4",
         "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=4",
         "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(root / "clip.mp4")])
    run(["-f", "lavfi", "-i", "sine=frequency=880:sample_rate=48000:duration=4", str(root / "music.wav")])
    from PIL import Image
    Image.new("RGB", (640, 360), "#2255AA").save(root / "still.png")
    font = next((p for p in [Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
                             Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
                             Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/arial.ttf"] if p.is_file()), None)
    if font:
        shutil.copyfile(font, root / "font.ttf")
    assets = {"clip": MediaAsset(locator="clip.mp4", sha256=file_sha256(root / "clip.mp4"), kind="video"),
              "music": MediaAsset(locator="music.wav", sha256=file_sha256(root / "music.wav"), kind="audio"),
              "still": MediaAsset(locator="still.png", sha256=file_sha256(root / "still.png"), kind="image")}
    if font:
        assets["font"] = MediaAsset(locator="font.ttf", sha256=file_sha256(root / "font.ttf"), kind="font")
    return AssetManifest(root=root, assets=assets)


def wait(editor, job_id, timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = editor.observe(job_id)
        if job.status in {"completed", "failed", "cancelled", "interrupted"}:
            if job.status == "failed":
                log = (editor.root / job_id / "ffmpeg.log").read_text(errors="replace")
                pytest.fail(f"{job.error}\n{log[-4000:]}")
            return job
        time.sleep(0.1)
    pytest.fail("real local render did not finish within test bound")


def project(**changes):
    data = dict(work_id="w", plan_revision=1, revision=1, duration=1,
                scenes=(Scene(scene_id="s", asset_id="clip", duration=1),))
    data.update(changes)
    return EditProject(**data)


def encoded_audio(path):
    return subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-i", str(path),
                           "-map", "0:a", "-c:a", "copy", "-f", "adts", "pipe:1"],
                          capture_output=True, check=True).stdout


def test_four_sound_modes_and_both_full_hd_aspects(tmp_path, sources):
    editor = FFmpegEditor(tmp_path / "jobs")
    for index, mode in enumerate(("silent", "music", "voice", "mixed")):
        audio = ((AudioClip(clip_id="m", asset_id="music", role="music", at=0, duration=1, gain=0.2),)
                 if mode in {"music", "mixed"} else ())
        p = project(width=1920 if index % 2 else 1080, height=1080 if index % 2 else 1920,
                    audio_mode=mode, audio=audio,
                    scenes=(Scene(scene_id="s", asset_id="clip", duration=1, source_start=1,
                                  source_audio=mode in {"voice", "mixed"}),))
        assert editor.check(p, sources).valid
        editor.build(p, sources, job_id=mode)
        assert wait(editor, mode).status == "completed"
        output = FFmpegEditor(editor.root).collect(mode)
        assert output.audio_present == (mode != "silent")
        assert (output.width, output.height) == (p.width, p.height)
        assert abs(output.duration - 1) < 0.1
        assert output.project_path.is_file()


def test_caption_and_crop_revision_reuse_exact_encoded_audio(tmp_path, sources):
    if "font" not in sources.assets:
        pytest.skip("test host has no known font; caption rendering NOT_TESTED")
    editor = FFmpegEditor(tmp_path / "jobs")
    original = project(audio_mode="voice", scenes=(Scene(scene_id="s", asset_id="clip", duration=1, source_audio=True),),
                       captions=(Caption(caption_id="c", text="原声保持 Keep my words", font_asset_id="font", start=0, end=1, size=48),))
    editor.build(original, sources, job_id="base")
    assert wait(editor, "base").status == "completed"
    edited = original.model_copy(update={"revision": 2,
        "scenes": (original.scenes[0].model_copy(update={"crop": Crop(x=0.1, width=0.8)}),),
        "captions": (original.captions[0].model_copy(update={"size": 64, "background": "#00000080"}),)})
    assert_local_revision(original, edited, allowed={"visual", "captions"})
    editor.build(edited, sources, job_id="revision")
    assert wait(editor, "revision").status == "completed"
    first, second = editor.collect("base"), editor.collect("revision")
    assert first.sha256 != second.sha256
    assert encoded_audio(first.video_path) == encoded_audio(second.video_path)
    assert len(list((editor.root / "cache").glob("audio-*.m4a"))) == 1
    assert first.video_path.is_file()
    clean, checksum = editor.caption_base("base", work_id=original.work_id)
    assert clean != first.video_path and file_sha256(clean) == checksum
    with pytest.raises(EditError, match="unavailable"):
        editor.caption_base("base", work_id="different-work")


def test_real_video_dissolve_and_declared_still_motion(tmp_path, sources):
    editor = FFmpegEditor(tmp_path / "jobs")
    p = project(duration=2, scenes=(Scene(scene_id="opening", asset_id="clip", duration=1.5, fade_in=0.1),
                                   Scene(scene_id="ending", asset_id="still", duration=1,
                                         transition="dissolve", transition_seconds=0.5, motion="push_in")))
    editor.build(p, sources, job_id="dissolve")
    assert wait(editor, "dissolve").status == "completed"
    assert abs(editor.collect("dissolve").duration - 2) < 0.1


def test_inputs_idempotency_tampering_and_missing_source_sound(tmp_path, sources):
    editor = FFmpegEditor(tmp_path / "jobs")
    p = project()
    editor.build(p, sources, job_id="stable")
    assert wait(editor, "stable").status == "completed"
    old = editor.collect("stable")
    assert editor.build(p, sources, job_id="stable").status == "completed"
    assert editor.collect("stable").sha256 == old.sha256
    with pytest.raises(EditError, match="different inputs"):
        editor.build(p.model_copy(update={"revision": 2}), sources, job_id="stable")
    bad = sources.model_copy(update={"assets": {**sources.assets, "clip": sources.assets["clip"].model_copy(update={"sha256": "0" * 64})}})
    assert not editor.check(p, bad).valid
    assert not editor.check(project(scenes=(Scene(scene_id="s", asset_id="clip", duration=1, source_start=10),)), sources).valid
    with old.video_path.open("ab") as stream:
        stream.write(b"tamper")
    with pytest.raises(EditError, match="identity changed"):
        editor.collect("stable")


def test_explicit_zero_music_gain_stays_zero(tmp_path, sources):
    editor = FFmpegEditor(tmp_path / "jobs")
    p = project(audio_mode="music", audio=(AudioClip(clip_id="m", asset_id="music", role="music",
                                                   at=0, duration=1, gain=0),))
    editor.build(p, sources, job_id="zero")
    assert wait(editor, "zero").status == "completed"
    pcm = subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-i", str(editor.collect("zero").video_path),
                          "-map", "0:a", "-f", "s16le", "pipe:1"], capture_output=True, check=True).stdout
    assert pcm and set(pcm) == {0}


def test_disguised_playlist_cannot_read_other_local_files(tmp_path, sources):
    bad = tmp_path / "looks-like-video.mp4"
    bad.write_text("ffconcat version 1.0\nfile '" + str(sources.root / "clip.mp4") + "'\n")
    manifest = AssetManifest(root=tmp_path, assets={
        "clip": MediaAsset(locator=bad.name, sha256=file_sha256(bad), kind="video")})
    assert not FFmpegEditor(tmp_path / "jobs").check(project(), manifest).valid


def test_cancel_is_observed_and_restart_recovers_interrupted_local_job(tmp_path, sources):
    editor = FFmpegEditor(tmp_path / "jobs")
    p = project(duration=30, scenes=(Scene(scene_id="long", asset_id="still", duration=30),))
    editor.build(p, sources, job_id="cancel")
    editor.cancel("cancel")
    assert wait(editor, "cancel").status == "cancelled"
    with pytest.raises(EditError, match="not complete"):
        editor.collect("cancel")
    # Simulate a dead local renderer after it persisted ownership; a held OS lock
    # would prevent this reconciliation. No external generation is repeated.
    p = project()
    editor.build(p, sources, job_id="recover")
    assert wait(editor, "recover").status == "completed"
    record = editor.root / "recover/job.json"
    payload = json.loads(record.read_text())
    payload["status"] = "running"
    record.write_text(json.dumps(payload))
    rebuilt = FFmpegEditor(editor.root)
    assert rebuilt.observe("recover").status == "interrupted"
    rebuilt.build(p, sources, job_id="recover")
    assert wait(rebuilt, "recover").status == "completed"


@pytest.mark.skipif(os.environ.get("EASEL_RUN_LONG_MEDIA") != "1", reason="900 second real encode is opt-in; long-media evidence tracked separately")
def test_900_second_boundary_real_encode(tmp_path, sources):
    editor = FFmpegEditor(tmp_path / "jobs")
    p = project(duration=900, fps=24, width=1920, height=1080,
                scenes=(Scene(scene_id="long", asset_id="still", duration=900),))
    editor.build(p, sources, job_id="boundary900")
    assert wait(editor, "boundary900", timeout=900).status == "completed"
    output = editor.collect("boundary900")
    assert abs(output.duration - 900) < 0.1 and not output.audio_present


@pytest.mark.parametrize('with_audio',[False,True])
def test_captions_survive_color_metadata_changes_across_cuts(tmp_path,sources,with_audio):
    if 'font' not in sources.assets:pytest.skip('test host has no known font')
    assets=dict(sources.assets)
    for asset in assets.values():shutil.copyfile(sources.root/asset.locator,tmp_path/asset.locator)
    for index,color_space in enumerate(('bt709','smpte170m','bt470bg')):
        path=tmp_path/f'color-{index}.mp4'
        run(['-f','lavfi','-i','color=blue:size=640x360:rate=30:duration=1',
             '-c:v','libx264','-preset','ultrafast','-colorspace',color_space,
             '-color_range','pc' if index==2 else 'tv',str(path)])
        assets[f'color-{index}']=MediaAsset(locator=path.name,sha256=file_sha256(path),kind='video')
    manifest=AssetManifest(root=tmp_path,assets=assets)
    p=project(duration=3,audio_mode='music' if with_audio else 'silent',
        scenes=tuple(Scene(scene_id=f's{i}',asset_id=f'color-{i}',duration=1) for i in range(3)),
        audio=(AudioClip(clip_id='m',asset_id='music',role='music',at=0,duration=3),) if with_audio else (),
        captions=tuple(Caption(caption_id=f'c{i}',text=f'VISIBLE CAPTION {i+1}',font_asset_id='font',
            start=.1+i*.5,end=.4+i*.5,size=64,background='#000000C0') for i in range(5)))
    editor=FFmpegEditor(tmp_path/'jobs');editor.build(p,manifest,job_id='color-cuts')
    assert wait(editor,'color-cuts').status=='completed'
    output=editor.collect('color-cuts')
    from PIL import Image
    from io import BytesIO
    for at in (.2,.7,1.2,1.7,2.2,2.8):
        decoded=subprocess.check_output([FFMPEG,'-v','error','-ss',str(at),'-i',str(output.video_path),
            '-frames:v','1','-f','image2pipe','-vcodec','png','-'])
        frame=Image.open(BytesIO(decoded)).convert('RGB')
        white=sum(min(pixel)>200 for pixel in frame.crop((0,int(p.height*.65),p.width,p.height)).getdata())
        assert (white>500)==(at<2.8),(at,white)


@pytest.mark.parametrize("motion", ["none", "push_in", "pull_out"])
def test_complete_graph_in_frame_leaves_subtitle_region(tmp_path, sources, motion):
    """Destination layout must not crop the source or zoom into the subtitle strip."""
    from PIL import Image, ImageDraw
    import io
    graph = Image.new('RGB', (640, 360), 'white')
    draw = ImageDraw.Draw(graph)
    for box, color in [((0, 0, 63, 35), 'red'), ((576, 0, 639, 35), 'green'),
                       ((0, 324, 63, 359), 'blue'), ((576, 324, 639, 359), 'yellow')]:
        draw.rectangle(box, fill=color)
    path = tmp_path / 'graph.png'; graph.save(path)
    manifest = AssetManifest(root=tmp_path, assets={
        'graph': MediaAsset(locator='graph.png', sha256=file_sha256(path), kind='image')})
    scene = Scene(scene_id='graph', asset_id='graph', duration=1, fit='contain', motion=motion,
                  frame={'x': 0.1, 'y': 0, 'width': 0.8, 'height': 0.8})
    p = project(width=1920, height=1080, scenes=(scene,))
    editor = FFmpegEditor(tmp_path / 'jobs')
    editor.build(p, manifest, job_id='graph')
    assert wait(editor, 'graph').status == 'completed'
    output = editor.collect('graph')
    data = subprocess.run([FFMPEG, '-v', 'error', '-ss', '0.5', '-i', str(output.video_path),
                           '-frames:v', '1', '-f', 'image2pipe', '-vcodec', 'png', '-'],
                          capture_output=True, check=True).stdout
    frame = Image.open(io.BytesIO(data)).convert('RGB')
    assert max(frame.crop((0, 870, 1920, 1080)).getextrema()[0]) <= 4
    assert max(frame.crop((0, 0, 180, 1080)).getextrema()[0]) <= 4
    if motion == 'none':
        for point, dominant in [((220, 25), 0), ((1695, 25), 1), ((220, 840), 2)]:
            pixel = frame.getpixel(point)
            assert pixel[dominant] > 100 and pixel[dominant] > min(pixel) + 80
        assert min(frame.getpixel((1695, 840))[:2]) > 200


def test_narration_music_balance_is_attenuation_only_and_scoped(tmp_path,sources):
    from easel.production.editors.ffmpeg import LocalRender
    # Exercise policy without rendering: actual timeline scope is deterministic.
    render=object.__new__(LocalRender);render.path=tmp_path
    render._mean_level=lambda c: {'voice':-24,'music':-12}[c['asset_id']]
    voice={'clip_id':'v','asset_id':'voice','role':'voice','at':2,'duration':2,'source_start':0,'gain':1}
    music={'clip_id':'m','asset_id':'music','role':'music','at':0,'duration':4,'source_start':0,'gain':.5}
    levels=render._music_levels([voice,music])
    start,end,gain=levels['m'][0]
    assert (start,end)==(2,4) and gain==pytest.approx(10**(-24/20))
    assert voice['gain']==1 and music['gain']==.5
    assert render._music_levels([{**music,'gain':0},voice])=={}
    assert render._music_levels([music])=={}
    quiet={**music,'gain':.01}
    assert render._music_levels([voice,quiet])['m'][0][2]==.01
    assert render._music_levels([voice,{**music,'at':5}])=={}


def test_measured_narration_mix_writes_effective_gain(tmp_path,sources):
    editor=FFmpegEditor(tmp_path/'jobs')
    p=project(audio_mode='mixed',audio=(
        AudioClip(clip_id='v',asset_id='music',role='voice',at=0,duration=1,gain=.1),
        AudioClip(clip_id='m',asset_id='music',role='music',at=0,duration=1,gain=.5)))
    editor.build(p,sources,job_id='balanced')
    assert wait(editor,'balanced').status=='completed'
    import json
    evidence=json.loads((editor.root/'balanced/audio-balance.json').read_text())
    span=evidence['spans'][0]
    assert span['narration_gain']==pytest.approx(.1*10**(-12/20),rel=.01)
    assert evidence['listening_verified'] is False
    graph=(editor.root/'balanced/audio.filter').read_text()
    assert 'max(0,(t-0.0+.1)/.1)' in graph and 'eval=frame' in graph
    # Independently measure encoded PCM, rather than trusting the recipe JSON.
    import array, math
    def rms(path):
        pcm=subprocess.run([FFMPEG,'-v','error','-ss','0.25','-i',str(path),'-t','0.5',
            '-map','0:a:0','-af','aformat=sample_fmts=fltp:channel_layouts=stereo',
            '-ac','1','-ar','48000','-f','s16le','pipe:1'],
            capture_output=True,check=True).stdout
        samples=array.array('h');samples.frombytes(pcm)
        return math.sqrt(sum(x*x for x in samples)/len(samples))
    actual=rms(editor.collect('balanced').video_path)/rms(sources.root/'music.wav')
    assert actual==pytest.approx(.1+.1*10**(-12/20),abs=.01)
    editor.build(p,sources,job_id='balanced-reuse')
    assert wait(editor,'balanced-reuse').status=='completed'
    assert json.loads((editor.root/'balanced-reuse/audio-balance.json').read_text())==evidence
