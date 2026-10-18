"""Real local version revision/export lifecycle; model decisions remain scripted."""
import asyncio
import json
import shutil
import time
import pytest
from tests.production.test_creation_flow import test_confirm_to_real_render_to_reviewable_without_creator_acceptance as _first_cut, ScriptedModel
from easel.production.store import Store
from easel.production.service import WorkService
from easel.production.worker import Worker
from easel.production.operations import OperationService
from easel.production.planning import PlanningTasks
from easel.production.creation import CreationTasks
from easel.production.revisions import RevisionTasks


class RevisionModel(ScriptedModel):
    async def complete(self,messages,tools,schema):
        if schema['title']=='RevisionProposal':
            self.calls.append(messages)
            context=json.loads(messages[1]['content'][0]['text'])
            base=context['artifacts'][0]['base_edit']
            edit={key:base[key] for key in ('scenes','audio','captions','required_features')}
            edit['scenes'][0]['motion']='push_in'
            return {'content':json.dumps({'summary':'只增加缓慢推近','affected':['visual'],'expands_scope':False,
                'requires_new_generation':False,'reason':'现有画面内调整','edit':edit})}
        return await super().complete(messages,tools,schema)


@pytest.mark.skipif(not shutil.which('ffmpeg'),reason='FFmpeg unavailable')
def test_local_revision_keeps_accepted_version_then_explicitly_switches(tmp_path):
    _first_cut(tmp_path,True)
    store=Store(tmp_path/'outputs/_production/production.sqlite3')
    service=WorkService(store,outputs=tmp_path/'outputs',profiles=tmp_path/'profiles')
    work=service.list_works()['items'][0]['id'];snap=service.snapshot(work)
    first=next(a for a in snap['artifacts'] if a['kind']=='output')
    first_path,_=service.artifact_path(first['id']);first_bytes=first_path.read_bytes()
    service.command('accept',{'output_id':first['id']},command_id='accept-old',work_id=work,expected_revision=snap['revision'])
    snap=service.snapshot(work)
    service.command('revise',{'output_id':first['id'],'feedback':'只增加缓慢推近，其他不变'},command_id='revision',work_id=work,expected_revision=snap['revision'])
    model=RevisionModel();model.calls=[]
    planning=PlanningTasks(service,OperationService(store),model,{'provider':'direct-api','model':'offline-scripted','mode':'structured'},'offline')
    creation=CreationTasks(service,planning)
    worker=Worker(store,{'revise':RevisionTasks(service,planning,creation).revise,'render':creation.render,'quality':creation.quality},poll_interval=.01)
    deadline=time.monotonic()+35
    while time.monotonic()<deadline:
        asyncio.run(worker.run_once());snap=service.snapshot(work)
        active=next((r for r in snap['runs'] if r['id']==snap['active_run_id']),None)
        if active is None or active['state'] in {'succeeded','failed','needs_decision'}:break
        time.sleep(.1)
    assert snap['state']=='reviewable',[(t['kind'],t['error_json']) for t in snap['tasks']]
    outputs=[a for a in snap['artifacts'] if a['kind']=='output']
    assert len(outputs)==2 and snap['accepted_output_id']==first['id']
    assert first_path.read_bytes()==first_bytes
    assert any(block.get('type')=='image_url' for block in model.calls[0][1]['content'])
    second=next(a for a in outputs if a['id']!=first['id'])
    service.command('accept',{'output_id':second['id']},command_id='accept-new',work_id=work,expected_revision=snap['revision'])
    assert service.snapshot(work)['accepted_output_id']==second['id']


@pytest.mark.skipif(not shutil.which('ffmpeg'),reason='FFmpeg unavailable')
@pytest.mark.parametrize('change_protected_audio',[False,True])
def test_image_only_revision_reuses_unselected_candidate_and_protects_audio_bytes(tmp_path,change_protected_audio):
    import hashlib
    import subprocess
    import wave
    from PIL import Image
    from easel.production.artifacts import register_file
    from easel.production.worker import TaskResult
    from easel.production.service import row
    store=Store(tmp_path/'outputs/_production/production.sqlite3');store.initialize()
    service=WorkService(store,outputs=tmp_path/'outputs',profiles=tmp_path/'profiles')
    for color in ('blue','red'):Image.new('RGB',(400,300),color).save(tmp_path/(color+'.png'))
    with wave.open(str(tmp_path/'tone.wav'),'wb') as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000)
        f.writeframes(b'\x00\x00\x10\x00'*8000)
    class Model:
        capabilities=frozenset({'text','image','structured'})
        requests=[]
        async def complete(self,messages,tools,schema):
            self.requests.append(messages)
            data=json.loads(messages[1]['content'][0]['text'])
            if schema['title']=='CreativeEdit':
                return {'content':json.dumps({'scenes':[{'scene_id':'s1','asset_id':data['artifacts'][0]['asset_id'],'duration':1}],
                    'audio':[{'clip_id':'voice','asset_id':data['artifacts'][1]['asset_id'],'role':'voice','at':0,'duration':1}],'captions':[]})}
            base=data['artifacts'][0]['base_edit'];edit={k:base[k] for k in ('scenes','audio','captions','required_features')}
            alternate=next(a['asset_id'] for a in data['artifacts'][1:] if a['asset_id']==self.alternate)
            edit['scenes'][0]['asset_id']=alternate
            if change_protected_audio:edit['audio'][0]['gain']=.5
            return {'content':json.dumps({'summary':'仅替换为同批现有红画面','affected':['visual','audio'] if change_protected_audio else ['visual'],
                'expands_scope':False,'requires_new_generation':False,'reason':'保留原声音','edit':edit})}
    model=Model();identity={'provider':'direct-api','model':'offline-model','mode':'structured'}
    planning=PlanningTasks(service,OperationService(store),model,identity,'offline')
    creation=CreationTasks(service,planning,manual_review_only=True)
    async def supply(ctx):
        visual=register_file(service,ctx,tmp_path/'blue.png',kind='image',media_type='image/png',metadata={})
        voice=register_file(service,ctx,tmp_path/'tone.wav',kind='audio',media_type='audio/wav',metadata={})
        model.alternate=register_file(service,ctx,tmp_path/'red.png',kind='image',media_type='image/png',metadata={})['id']
        return TaskResult(next_kind='edit',next_payload={'asset_ids':[visual['id'],voice['id']]})
    worker=Worker(store,{'supply':supply,'edit':creation.edit,'revise':RevisionTasks(service,planning,creation).revise,
        'render':creation.render,'quality':creation.quality},poll_interval=.01)
    work=service.command('create',{'title':'preserved sound'},command_id='new')['work_id']
    plan={'title':'one','summary':'fixture','script':'fixture','scenes':[{'id':'s1','purpose':'test','visual':'blue','narration':''}],
        'settings':{'duration_seconds':1,'aspect_ratio':'16:9','audio_mode':'voice'}}
    p=service.command('plan',{'generate':False,'plan':plan},command_id='plan',work_id=work,expected_revision=1)
    service.command('confirm',{'plan_revision':1,'plan_hash':p['plan_hash'],'services':[identity]},command_id='confirm',work_id=work,expected_revision=2)
    def finish():
        deadline=time.monotonic()+25
        while time.monotonic()<deadline:
            asyncio.run(worker.run_once());s=service.snapshot(work)
            if next(r for r in s['runs'] if r['id']==s['active_run_id'])['state'] in {'succeeded','needs_decision','failed'}:return s
            time.sleep(.05)
        pytest.fail('local rendering timed out')
    first=finish();assert first['state']=='reviewable'
    a=next(v for v in first['artifacts'] if v['kind']=='output');path_a,_=service.artifact_path(a['id']);original=path_a.read_bytes()
    service.command('revise',{'output_id':a['id'],'feedback':'只替换画面，声音不变','preserve_audio':True},
        command_id='revise',work_id=work,expected_revision=first['revision'])
    last=finish();outputs=[v for v in last['artifacts'] if v['kind']=='output']
    assert path_a.read_bytes()==original and len(last['plans'])==1
    assert not any(b.get('type')=='input_audio' for b in model.requests[-1][1]['content'])
    if change_protected_audio:
        assert len(outputs)==1 and last['state']=='needs_decision'
        assert '保留声音' in next(t for t in last['tasks'] if t['kind']=='revise')['error_json']
    else:
        assert len(outputs)==2 and last['state']=='reviewable'
        b=next(v for v in outputs if v['id']!=a['id']);path_b,_=service.artifact_path(b['id'])
        pcm=lambda p:subprocess.check_output(['ffmpeg','-v','error','-i',str(p),'-map','0:a:0','-f','s16le','-'])
        assert hashlib.sha256(pcm(path_a)).digest()==hashlib.sha256(pcm(path_b)).digest()
        with store.connection() as conn:
            project=row(conn,'artifacts',json.loads(row(conn,'artifacts',b['id'])['metadata_json'])['project_id'])
            assert json.loads((service.outputs/project['storage_ref']).read_text())['scenes'][0]['asset_id']==model.alternate
            assert conn.execute("SELECT COUNT(*) FROM operations WHERE kind='VOICE'").fetchone()[0]==0


@pytest.mark.skipif(not shutil.which('ffmpeg'),reason='FFmpeg unavailable')
def test_render_only_reuses_exact_project_without_model_or_voice_and_rejects_known_gaps(tmp_path):
    from easel.production.errors import ProductionError
    from easel.production.service import row,encode,new_id,now
    from easel.production.media import file_sha256
    _first_cut(tmp_path,True)
    store=Store(tmp_path/'outputs/_production/production.sqlite3')
    service=WorkService(store,outputs=tmp_path/'outputs',profiles=tmp_path/'profiles')
    work=service.list_works()['items'][0]['id'];first=service.snapshot(work)
    source=next(a for a in first['artifacts'] if a['kind']=='output')
    path,_=service.artifact_path(source['id']);old_digest=file_sha256(path)
    with store.connection() as conn:
        operations=[tuple(r) for r in conn.execute('SELECT * FROM operations ORDER BY id')]
        project=row(conn,'artifacts',json.loads(row(conn,'artifacts',source['id'])['metadata_json'])['project_id'])
        metadata=project['metadata_json']
    def submit(command_id,**extra):
        return service.command('revise',{'output_id':source['id'],'feedback':'仅重新导出','preserve_audio':True,'render_only':True,**extra},
            command_id=command_id,work_id=work,expected_revision=service.snapshot(work)['revision'])
    with pytest.raises(ProductionError):submit('wrong-flag',render_only='true')
    with store.transaction() as conn:
        conn.execute('UPDATE artifacts SET metadata_json=? WHERE id=?',
            (encode({**json.loads(metadata),'unverified_editor_notes':['PENDING_VISUAL_MATCH s1']}),project['id']))
    with pytest.raises(ProductionError,match='画面缺口'):submit('known-gap')
    with store.transaction() as conn:
        conn.execute('UPDATE artifacts SET metadata_json=? WHERE id=?',(metadata,project['id']))
        check_id=new_id()
        conn.execute("INSERT INTO quality_checks VALUES (?,?,?,'semantic','fixture','partial',?,?)",
            (check_id,source['id'],source['digest'],encode({'schema_version':1}),now()))
    with pytest.raises(ProductionError,match='画面缺口'):submit('known-failed-qc')
    with store.transaction() as conn:conn.execute('DELETE FROM quality_checks WHERE id=?',(check_id,))
    result=submit('export')
    # There is intentionally no plan, revise, supply, or voice handler.
    planning=PlanningTasks(service,OperationService(store),None,{},'offline')
    creation=CreationTasks(service,planning,manual_review_only=True)
    worker=Worker(store,{'render':creation.render,'quality':creation.quality},poll_interval=.01)
    deadline=time.monotonic()+30
    while time.monotonic()<deadline:
        asyncio.run(worker.run_once());snap=service.snapshot(work)
        active=next(r for r in snap['runs'] if r['id']==result['run_id'])
        if active['state'] in {'succeeded','failed','needs_decision'}:break
        time.sleep(.05)
    assert active['state']=='succeeded'
    assert [t['kind'] for t in snap['tasks'] if t['run_id']==result['run_id']]==['render','quality']
    assert len([a for a in snap['artifacts'] if a['kind']=='output'])==2
    assert len(snap['plans'])==len(first['plans']) and snap['accepted_output_id']==first['accepted_output_id']
    assert file_sha256(path)==old_digest
    with store.connection() as conn:
        assert [tuple(r) for r in conn.execute('SELECT * FROM operations ORDER BY id')]==operations
        assert conn.execute("SELECT COUNT(*) FROM artifacts WHERE kind='edit_project'").fetchone()[0]==1
