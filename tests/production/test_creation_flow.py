"""Real local rendering with a scripted model; software evidence, NOT real AI production."""
import asyncio
import json
import shutil
import time
import pytest
from PIL import Image
from easel.production.store import Store
from easel.production.service import WorkService
from easel.production.worker import Worker,TaskResult
from easel.production.operations import OperationService
from easel.production.planning import PlanningTasks
from easel.production.creation import CreationTasks
from easel.production.artifacts import register_file


class ScriptedModel:
    capabilities=frozenset({'text','structured','image','tools','video'})
    video_dialect='qwen-vl-video-url'
    quality_chunk_seconds=30
    calls=[]
    async def complete(self,messages,tools,schema):
        self.calls.append(messages)
        if schema['title']=='CreativeEdit':
            data=json.loads(messages[1]['content'][0]['text'])
            return {'content':json.dumps({'scenes':[{'scene_id':'s1','asset_id':data['artifacts'][0]['asset_id'],'duration':1}], 'audio':[],'captions':[]})}
        return {'content':json.dumps({'verdict':'pass','factual_fidelity':'fixture only','style_consistency':'fixture only','narrative_coherence':'fixture only','audiovisual_alignment':'silent fixture','findings':[],'limitations':[]})}


@pytest.mark.skipif(not shutil.which('ffmpeg'),reason='FFmpeg unavailable')
@pytest.mark.parametrize('full_video',[True,False])
def test_confirm_to_real_render_to_reviewable_without_creator_acceptance(tmp_path,full_video):
    store=Store(tmp_path/'outputs/_production/production.sqlite3');store.initialize()
    service=WorkService(store,outputs=tmp_path/'outputs',profiles=tmp_path/'profiles')
    model=ScriptedModel();model.calls=[]
    if not full_video:model.capabilities=frozenset({'text','structured','image','tools'})
    identity={'provider':'direct-api','model':'offline-scripted','mode':'structured'}
    planning=PlanningTasks(service,OperationService(store),model,identity,'offline')
    creation=CreationTasks(service,planning)
    image=tmp_path/'input.png';Image.new('RGB',(400,300),'blue').save(image)
    async def supply(ctx):
        artifact=register_file(service,ctx,image,kind='image',media_type='image/png',metadata={'source':'synthetic test'})
        return TaskResult(next_kind='edit',next_payload={'asset_ids':[artifact['id']]})
    worker=Worker(store,{'supply':supply,'edit':creation.edit,'render':creation.render,'quality':creation.quality},poll_interval=.01)
    id=service.command('create',{'title':'offline local test'},command_id='create')['work_id']
    plan={'title':'one second','summary':'local media test','script':'fixture','scenes':[{'id':'s1','purpose':'test','visual':'blue','narration':''}], 'settings':{'duration_seconds':1,'aspect_ratio':'16:9','audio_mode':'silent'}}
    result=service.command('plan',{'generate':False,'plan':plan},command_id='plan',work_id=id,expected_revision=1)
    service.command('confirm',{'plan_revision':1,'plan_hash':result['plan_hash'],'services':[identity]},command_id='confirm',work_id=id,expected_revision=2)
    deadline=time.monotonic()+35
    while time.monotonic()<deadline:
        asyncio.run(worker.run_once())
        snap=service.snapshot(id)
        if snap['runs'][-1]['state'] in {'succeeded','failed','needs_decision'}:break
        time.sleep(.1)
    assert snap['state']==('reviewable' if full_video else 'needs_decision'),[(t['kind'],t['state'],t['error_json']) for t in snap['tasks']]
    assert snap['accepted_output_id'] is None
    outputs=[a for a in snap['artifacts'] if a['kind']=='output']
    assert len(outputs)==1 and outputs[0]['quality_state']==('passed' if full_video else 'needs_fix')
    path,_=service.artifact_path(outputs[0]['id']);assert path.stat().st_size>1000
    if not full_video:
        assert len(model.calls)==1  # Edit only; sampled images never grant complete QC.
        quality=next(t for t in snap['tasks'] if t['kind']=='quality')
        assert quality['state']=='needs_decision' and 'capability_unavailable' in quality['error_json']
        with store.connection() as conn:
            assert conn.execute("SELECT status FROM quality_checks WHERE check_kind='semantic'").fetchone()[0]=='not_tested'
        return
    assert len(model.calls)==3
    assert any(b.get('type')=='video_url' for b in model.calls[-2][1]['content'])
    assert '全片综合审片' in model.calls[-1][0]['content']
    with store.connection() as conn:
        checks=[dict(r) for r in conn.execute('SELECT * FROM quality_checks')]
    assert {c['check_kind'] for c in checks}=={'technical','semantic'}
    assert all(c['artifact_digest']==outputs[0]['digest'] for c in checks)
    semantic=json.loads(next(c['findings_json'] for c in checks if c['check_kind']=='semantic'))
    assert semantic['evidence']['coverage_complete'] and semantic['evidence']['global_review_complete']
    with store.connection() as conn:
        task=conn.execute("SELECT id FROM tasks WHERE kind='quality'").fetchone()
        assert conn.execute('SELECT COUNT(*) FROM operations WHERE task_id=?',(task['id'],)).fetchone()[0]==2
