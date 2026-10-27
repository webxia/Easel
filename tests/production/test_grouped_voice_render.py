"""Measured group scheduling through real FFmpeg; not CreationTasks/model or listening QA."""
import array
import json
import math
import subprocess

import pytest

from easel.production.editors import AssetManifest, AudioClip, Caption, EditProject, FFmpegEditor, MediaAsset, Scene
from easel.production.media import file_sha256, probe_media
from easel.production.narration import aligned_captions, check_voice_schedule, measured_execution_plan, narration_segments
from .test_narration_groups import plan
from .test_render_local import FFMPEG, FFPROBE, run, sources, wait  # reuse local synthetic fixture

pytestmark = pytest.mark.skipif(not (FFMPEG and FFPROBE), reason='real FFmpeg unavailable')


def test_group_retiming_reaches_encoded_audio_and_caption_frames(tmp_path, sources):
    if 'font' not in sources.assets:
        pytest.skip('known font unavailable')
    from PIL import Image
    import shutil
    for asset in sources.assets.values():
        shutil.copyfile(sources.root / asset.locator, tmp_path / asset.locator)
    assets = dict(sources.assets)
    # Unique tones allow the actual decoded mix to identify each layer.
    for name, hz, duration in [('first', 440, 1), ('longer', 440, 1.6),
                               ('second', 880, 1), ('bgm', 160, 5), ('effect', 1760, .2)]:
        run(['-f', 'lavfi', '-i', f'sine=frequency={hz}:sample_rate=48000:duration={duration}', str(tmp_path / f'{name}.wav')])
        assets[name] = MediaAsset(locator=f'{name}.wav', sha256=file_sha256(tmp_path / f'{name}.wav'), kind='audio')
    manifest = AssetManifest(root=tmp_path, assets=assets)
    editor = FFmpegEditor(tmp_path / 'jobs')
    frozen = plan()
    segments = narration_segments(frozen)
    outputs = []
    for revision, first in enumerate(('first', 'longer'), 1):
        records = []
        for segment, asset_id in zip(segments, (first, 'second')):
            duration = probe_media(tmp_path / assets[asset_id].locator)['duration']
            records.append({'id': asset_id, 'metadata_json': json.dumps({'role': 'voice',
                'segment_id': segment['segment_id'], 'duration': duration, 'narration_text': segment['text'],
                'timing': {'provider_alignment': {'status': 'received', 'segments': [
                    {'text': segment['text'], 'start': 0, 'end': duration}]}}})})
        _, timing = measured_execution_plan(frozen, records)
        slots = timing['voice_schedule']
        voices = tuple(AudioClip(clip_id=f'v{i}', asset_id=asset, role='voice', at=slot['at'], duration=slot['duration'])
                       for i, (asset, slot) in enumerate(zip((first, 'second'), slots)))
        check_voice_schedule(voices, records, timing)
        anchors = aligned_captions(voices, records)
        captions = tuple(Caption(caption_id=f'c{i}', font_asset_id='font', size=40, **anchor) for i, anchor in enumerate(anchors))
        p = EditProject(work_id='synthetic', plan_revision=revision, revision=revision,
            width=1920, height=1080, duration=timing['duration'], audio_mode='mixed',
            scenes=(Scene(scene_id='still', asset_id='still', duration=timing['duration']),),
            audio=voices + (AudioClip(clip_id='bgm', asset_id='bgm', role='music', at=0, duration=timing['duration'], gain=.25),
                AudioClip(clip_id='effect', asset_id='effect', role='sfx', at=slots[1]['at']+.35, duration=.2, gain=.5)),
            captions=captions)
        # Scheduling is deterministic here, not a claim that CreationTasks made these choices.
        job = f'group-{revision}'
        editor.build(p, manifest, job_id=job)
        assert wait(editor, job).status == 'completed'
        rendered = editor.collect(job)
        raw = subprocess.run([FFMPEG, '-v', 'error', '-i', str(rendered.video_path), '-vn', '-ac', '1',
                              '-ar', '48000', '-f', 'f32le', 'pipe:1'], capture_output=True, check=True).stdout
        samples = array.array('f'); samples.frombytes(raw)
        def amplitude(hz, at):
            window = samples[round(at*48000):round((at+.1)*48000)]
            assert len(window) == 4800
            real = sum(x*math.cos(2*math.pi*hz*i/48000) for i,x in enumerate(window))
            imag = sum(x*math.sin(2*math.pi*hz*i/48000) for i,x in enumerate(window))
            return 2*math.hypot(real, imag)/len(window)
        second_at = slots[1]['at']
        assert amplitude(440, .4) > .08
        assert amplitude(880, second_at+.1) > .08
        assert amplitude(880, second_at+.8) > .08  # complete ending, no truncation
        assert amplitude(880, second_at-.15) < .005
        if outputs:
            assert amplitude(880, outputs[0][1][1]['at']+.1) < .005  # no stale old placement
        assert amplitude(880, second_at+1.15) < .005  # no repeat/overrun
        assert amplitude(160, .05) > .02 and amplitude(160, second_at+1.2) > .02
        assert amplitude(1760, second_at+.4) > .04
        assert amplitude(1760, second_at+.7) < .005
        # Verify caption pixels exist during the measured second group and vanish after it.
        def frame(at):
            data = subprocess.run([FFMPEG, '-v', 'error', '-ss', str(at), '-i', str(rendered.video_path),
                '-frames:v', '1', '-vf', 'scale=640:360', '-f', 'rawvideo', '-pix_fmt', 'rgb24', 'pipe:1'], capture_output=True, check=True).stdout
            return Image.frombytes('RGB', (640, 360), data)
        def white(image):
            pixels = image.crop((0, 240, 640, 360)).tobytes()
            return sum(min(pixels[i:i+3]) > 210 for i in range(0, len(pixels), 3))
        assert white(frame(second_at+.2)) > 50
        assert white(frame(second_at+1.2)) == 0
        outputs.append((p, slots))
    assert outputs[1][1][1]['at'] - outputs[0][1][1]['at'] == pytest.approx(.6)
    assert outputs[1][0].captions[1].start - outputs[0][0].captions[1].start == pytest.approx(.6)
