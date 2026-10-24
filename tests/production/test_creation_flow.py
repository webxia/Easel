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
    overlay_repair=False
    async def complete(self,messages,tools,schema):
        self.calls.append(messages)
        from easel.production.expression_policy import RULES
        role="visual" if schema["title"]=="CreativeEdit" else "review"
        assert RULES[role] in messages[0]["content"]
        if schema['title']=='CreativeEdit':
            data=json.loads(messages[1]['content'][0]['text'])
            captions=[]
            if self.overlay_repair:
                font=next(a['asset_id'] for a in data['artifacts'] if a['kind']=='font')
                captions=[{'caption_id':'source-note','role':'overlay','text':'A source note with enough text to extend beyond the left edge',
                    'font_asset_id':font,'start':0,'end':1,'size':32,'x':.06 if len(self.calls)==1 else .5,'y':.13}]
            return {'content':json.dumps({'scenes':[{'scene_id':'s1','asset_id':data['artifacts'][0]['asset_id'],'duration':1}], 'audio':[],'captions':captions})}
        return {'content':json.dumps({'verdict':'pass','factual_fidelity':'fixture only','style_consistency':'fixture only','narrative_coherence':'fixture only','audiovisual_alignment':'silent fixture','findings':[],'limitations':[]})}


@pytest.mark.skipif(not shutil.which('ffmpeg'),reason='FFmpeg unavailable')
@pytest.mark.parametrize('full_video,recover_render,overlay_repair',[(True,False,False),(False,False,False),(True,True,False),(False,False,True),(False,True,True)])
def test_confirm_to_real_render_to_reviewable_without_creator_acceptance(tmp_path,full_video,recover_render,overlay_repair,monkeypatch):
    store=Store(tmp_path/'outputs/_production/production.sqlite3');store.initialize()
    service=WorkService(store,outputs=tmp_path/'outputs',profiles=tmp_path/'profiles')
    model=ScriptedModel();model.calls=[];model.overlay_repair=overlay_repair
    if not full_video:model.capabilities=frozenset({'text','structured','image','tools'})
    identity={'provider':'direct-api','model':'offline-scripted','mode':'structured'}
    planning=PlanningTasks(service,OperationService(store),model,identity,'offline')
    creation=CreationTasks(service,planning)
    late_caption=recover_render and overlay_repair
    if late_caption:
        import easel.production.creation as creation_module
        original_check=creation_module.check_caption_layout
        monkeypatch.setattr(creation_module,"check_caption_layout",lambda *a,**kw:None)
    if recover_render and not late_caption:
        from easel.production.editors import RenderJob
        from easel.production.service import now
        class FailFirstRender:
            def __init__(self,delegate):self.delegate=delegate;self.failed=None
            def __getattr__(self,name):return getattr(self.delegate,name)
            def build(self,project,manifest,*,job_id):
                if self.failed is None:
                    self.failed=RenderJob(job_id=job_id,project_hash='a'*64,status='failed',
                        updated_at=now(),error='synthetic local renderer failure')
                if job_id==self.failed.job_id:return self.failed
                return self.delegate.build(project,manifest,job_id=job_id)
            def observe(self,job_id):
                return self.failed if self.failed and job_id==self.failed.job_id else self.delegate.observe(job_id)
        creation.editor=FailFirstRender(creation.editor)
    image=tmp_path/'input.png';Image.new('RGB',(400,300),'blue').save(image)
    async def supply(ctx):
        artifact=register_file(service,ctx,image,kind='image',media_type='image/png',metadata={'source':'synthetic test'})
        ids=[artifact['id']]
        if overlay_repair:
            from pathlib import Path
            font=next((Path(p) for p in ['/System/Library/Fonts/Supplemental/Arial Unicode.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'] if Path(p).is_file()),None)
            if font is None:pytest.skip('font unavailable')
            ids.append(register_file(service,ctx,font,kind='font',media_type='font/ttf',metadata={'font_name':'sans-serif'})['id'])
        return TaskResult(next_kind='edit',next_payload={'asset_ids':ids})
    worker=Worker(store,{'supply':supply,'edit':creation.edit,'render':creation.render,'quality':creation.quality},poll_interval=.01)
    id=service.command('create',{'title':'offline local test'},command_id='create')['work_id']
    plan={'title':'one second','summary':'local media test','script':'fixture','scenes':[{'id':'s1','purpose':'test','visual':'blue','narration':''}], 'settings':{'duration_seconds':1,'aspect_ratio':'16:9','audio_mode':'silent'}}
    if overlay_repair:
        plan['narration_policy']={'continuous':True,'duration_mode':'fixed'}
    result=service.command('plan',{'generate':False,'plan':plan},command_id='plan',work_id=id,expected_revision=1)
    service.command('confirm',{'plan_revision':1,'plan_hash':result['plan_hash'],'services':[identity]},command_id='confirm',work_id=id,expected_revision=2)
    resumed=False
    deadline=time.monotonic()+35
    while time.monotonic()<deadline:
        asyncio.run(worker.run_once())
        snap=service.snapshot(id)
        if recover_render and not resumed and snap['state']=='needs_decision':
            failed=next(t for t in snap['tasks'] if t['kind']=='render')
            assert json.loads(failed['error_json'])['code']=='render_failed'
            calls_before=len(model.calls)
            if late_caption:
                monkeypatch.setattr(creation_module,"check_caption_layout",original_check)
                class ForbiddenVoice:
                    async def prepare_assets(self,*a,**kw):raise AssertionError('must reuse voice')
                creation.voice_tasks=ForbiddenVoice()
            service.command('resume',{'decision_id':failed['id']},command_id='retry-local-render',
                work_id=id,expected_revision=snap['revision'])
            # Idempotent command replay must not create a second local attempt.
            service.command('resume',{'decision_id':failed['id']},command_id='retry-local-render',
                work_id=id,expected_revision=snap['revision'])
            resumed=True
            continue
        if snap['runs'][-1]['state'] in {'succeeded','failed','needs_decision'}:break
        time.sleep(.1)
    assert snap['state']==('reviewable' if full_video else 'needs_decision'),[(t['kind'],t['state'],t['error_json']) for t in snap['tasks']]
    assert snap['accepted_output_id'] is None
    if late_caption:
        assert resumed and calls_before==1
        assert sum(t['kind']=='supply' for t in snap['tasks'])==1
        assert sum(t['kind']=='render' and t['state']=='cancelled' for t in snap['tasks'])==1
        edit=next(t for t in snap['tasks'] if t['kind']=='edit')
        assert json.loads(edit['payload_json'])['reuse_existing_media_only']
        assert all(json.loads(t['payload_json']).get('reuse_existing_media_only') for t in snap['tasks'] if t['kind'] in {'render','quality'} and t['state']!='cancelled')
    if recover_render and not late_caption:
        assert resumed and calls_before==1
        render=next(t for t in snap['tasks'] if t['kind']=='render')
        assert json.loads(render['payload_json'])['render_attempt']==1
        assert creation.editor.observe(creation.editor.failed.job_id).status=='failed'
        assert creation.editor.observe(creation.editor.failed.job_id+'_retry1').status=='completed'
    outputs=[a for a in snap['artifacts'] if a['kind']=='output']
    assert len(outputs)==1 and outputs[0]['quality_state']==('passed' if full_video else 'needs_fix')
    path,_=service.artifact_path(outputs[0]['id']);assert path.stat().st_size>1000
    if not full_video:
        assert len(model.calls)==(2 if overlay_repair else 1)  # Edit only; sampled images never grant complete QC.
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
