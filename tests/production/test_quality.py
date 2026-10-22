"""Synthetic local videos + scripted model: coverage evidence, NOT real AI quality."""
import asyncio
import base64
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from easel.production.context import TaskContext
from easel.production.expression_policy import snapshot
from easel.production.creation import SemanticReview
from easel.production.inspection import observe_media, prepare_video_chunks
from easel.production.media import probe_media
from easel.production.model_tasks import ModelTaskError, ModelTaskRunner
from easel.production.quality import review_full_video


pytestmark = pytest.mark.skipif(not shutil.which('ffmpeg'), reason='NOT_TESTED: local FFmpeg unavailable')


def video(path, *, seconds=7, audio=False, tail_red=False, fps=24):
    command = [shutil.which('ffmpeg'), '-hide_banner', '-loglevel', 'error', '-f', 'lavfi',
               '-i', f'color=c=blue:s=192x108:r={fps}:d={seconds}']
    if audio:
        command += ['-f','lavfi','-i',f'sine=frequency=440:duration={seconds}']
    if tail_red:
        command += ['-vf',f"drawbox=x=0:y=0:w=iw:h=ih:color=red:t=fill:enable='gte(t,{seconds-.75})'"]
    command += ['-c:v','libx264','-pix_fmt','yuv420p']
    if audio:command += ['-c:a','aac']
    command += ['-y',str(path)]
    subprocess.run(command,check=True,capture_output=True,timeout=30)
    return path


def response(*, verdict='pass', findings=None, limitations=None):
    return {'content':json.dumps({'verdict':verdict, 'factual_fidelity':'synthetic blue/red fixture only',
        'style_consistency':'synthetic fixture', 'narrative_coherence':'synthetic fixture',
        'audiovisual_alignment':'synthetic fixture', 'findings':findings or [],'limitations':limitations or []})}


class Model:
    capabilities=frozenset({'text','structured','image','video','audio'})
    video_dialect='qwen-omni-video-url'
    quality_chunk_seconds=3

    def __init__(self, folder, *, tail=False, global_fail=False, interrupt_at=None, partial=False):
        self.folder=folder;self.calls=[];self.files=[];self.tail=tail;self.global_fail=global_fail
        self.interrupt_at=interrupt_at;self.partial=partial

    async def complete(self,messages,tools,schema):
        self.calls.append(messages)
        assert snapshot()["rules"]["review"] in messages[0]["content"]
        if len(self.calls)==self.interrupt_at:
            raise ModelTaskError('result_unknown','fixture interrupted')
        native=next((b for b in messages[1]['content'] if b.get('type')=='video_url'),None)
        if native:
            data=base64.b64decode(native['video_url']['url'].split(',',1)[1])
            path=self.folder/f'submitted-{len(self.files)}.mp4';path.write_bytes(data);self.files.append(path)
            info=probe_media(path)
            assert info['video'] and info['width']==192 and info['height']==108
            # Inspect the bytes that were actually passed to the model boundary.
            raw=subprocess.run([shutil.which('ffmpeg'),'-hide_banner','-loglevel','error',
                '-ss',str(max(0,info['duration']-.1)),'-i',str(path),'-frames:v','1','-vf','scale=1:1',
                '-pix_fmt','rgb24','-f','rawvideo','pipe:1'],capture_output=True,check=True,timeout=30).stdout
            if self.tail and raw[0]>raw[2]:
                return response(verdict='fail',findings=['全片末尾红色缺陷（真实提交视频测试）'])
            if self.partial:return response(verdict='partial',limitations=['fixture provider cannot inspect a brief action'])
        if not native and self.global_fail:
            return response(verdict='fail',findings=['跨段叙事冲突（fixture）'])
        return response()


def run_review(path, model, cache, progress=None):
    async def authorize(context):pass
    return asyncio.run(review_full_video(path,cache_root=cache,info=probe_media(path),transport=model,
        runner=ModelTaskRunner(model,authorize),context=TaskContext('work','run','task',expression_policy=snapshot()),
        review_type=SemanticReview,on_segment=progress))


def test_short_video_sample_reaches_tail_instead_of_first_quarter(tmp_path):
    path=video(tmp_path/'short.mp4',seconds=2)
    _,_,evidence=observe_media(path,max_frames=12)
    assert len(evidence['frame_times'])==3
    assert evidence['frame_times'][0]==0
    assert evidence['frame_times'][-1]>=1.9
    assert evidence['sampling']=='bounded_frames_full_audio'  # Never full-video QC.


@pytest.mark.parametrize('fps',[1,10])
def test_low_fps_tail_sample_uses_last_available_frame(tmp_path,fps):
    path=video(tmp_path/'slow.mp4',seconds=2,fps=fps)
    blocks,_,evidence=observe_media(path,max_frames=12)
    assert evidence['frame_times'][-1]==pytest.approx(2-1/fps,abs=.00001)
    assert any(block['type']=='image_url' for block in blocks)


@pytest.mark.parametrize('dialect,capabilities,code',[
    ('qwen-vl-video-url',{'text','structured','image'},'capability_unavailable'),
    ('',{'text','structured','video','audio'},'video_protocol_unavailable'),
    ('pretend-video',{'text','structured','video','audio'},'video_protocol_unavailable'),
    ('qwen-omni-video-url',{'text','structured','video'},'capability_unavailable'),
    ('qwen-vl-video-url',{'text','structured','video','audio'},'audio_video_protocol_unavailable'),
])
def test_unknown_protocol_image_only_or_missing_audio_never_full_pass(tmp_path,dialect,capabilities,code):
    path=video(tmp_path/'sound.mp4',seconds=1,audio=True)
    model=Model(tmp_path);model.video_dialect=dialect;model.capabilities=frozenset(capabilities)
    with pytest.raises(ModelTaskError) as caught:run_review(path,model,tmp_path/'cache')
    assert caught.value.code==code and model.calls==[]


def test_complete_real_video_and_sound_ranges_plus_global_synthesis(tmp_path):
    path=video(tmp_path/'complete.mp4',audio=True)
    model=Model(tmp_path);progress=[]
    answer=run_review(path,model,tmp_path/'cache',lambda *entry:progress.append(entry))
    evidence=answer.evidence
    assert answer.verdict=='pass' and evidence['global_review_complete']
    assert evidence['sampling']=='native_video_full_timeline' and evidence['coverage_complete']
    assert evidence['provider_frame_sampling']=='provider_internal_not_verified'
    assert len(model.files)==3 and len(model.calls)==4 and len(progress)==3
    assert all(probe_media(path)['audio'] for path in model.files)
    chunks=evidence['reviewed_chunks']
    assert chunks[0]['start']==0 and chunks[-1]['end']==pytest.approx(7)
    assert all(right['start']<left['end'] for left,right in zip(chunks,chunks[1:]))
    assert not any(b.get('type')=='image_url' for call in model.calls for b in call[1]['content'])
    global_input=json.loads(model.calls[-1][1]['content'][-1]['text'])
    assert len(global_input['actual_video_segment_reviews'])==3
    # Cache reuse retains exact media bytes even if the FFmpeg encoder version changes.
    first=[p.read_bytes() for p in model.files]
    again=Model(tmp_path)
    run_review(path,again,tmp_path/'cache')
    assert first==[p.read_bytes() for p in again.files]


def test_tail_defect_cannot_be_erased_by_passing_global_summary(tmp_path):
    path=video(tmp_path/'tail.mp4',tail_red=True)
    model=Model(tmp_path,tail=True)
    answer=run_review(path,model,tmp_path/'cache')
    assert answer.verdict=='fail' and '末尾' in answer.findings[0]
    assert answer.review['segments'][-1]['review']['verdict']=='fail'
    assert answer.review['global']['verdict']=='pass'  # Program does not trust this override.


def test_local_passes_still_require_global_coherence_and_no_limitations(tmp_path):
    path=video(tmp_path/'complete.mp4')
    answer=run_review(path,Model(tmp_path,global_fail=True),tmp_path/'cache')
    assert answer.verdict=='fail' and all(r['review']['verdict']=='pass' for r in answer.review['segments'])
    answer=run_review(path,Model(tmp_path,partial=True),tmp_path/'cache')
    assert answer.verdict=='partial' and answer.limitations


def test_interrupted_late_review_retains_exact_completed_coverage(tmp_path):
    path=video(tmp_path/'complete.mp4')
    with pytest.raises(ModelTaskError) as caught:
        run_review(path,Model(tmp_path,interrupt_at=3),tmp_path/'cache')
    evidence=caught.value.diagnostic['evidence']
    assert caught.value.code=='result_unknown'
    assert len(evidence['reviewed_chunks'])==2 and not evidence['global_review_complete']


def test_changed_cached_segment_is_not_regenerated_for_old_receipts(tmp_path):
    path=video(tmp_path/'short.mp4',seconds=1)
    chunks,_=prepare_video_chunks(path,cache_root=tmp_path/'cache')
    chunks[0].path.write_bytes(b'changed')
    with pytest.raises(ModelTaskError) as caught:prepare_video_chunks(path,cache_root=tmp_path/'cache')
    assert caught.value.code=='inspection_changed'
