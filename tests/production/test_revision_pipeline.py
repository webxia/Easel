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
            from easel.production.expression_policy import RULES
            assert RULES['visual'] in messages[0]['content']
            self.calls.append(messages)
            context=json.loads(messages[1]['content'][0]['text'])
            assert context['task_view']['version'] == 'editor-context-2'
            image = next(a for a in context['artifacts'][1:] if a['kind'] == 'image')
            assert image['metadata']['semantic']['observation_scope'] == 'fixture'
            assert image['metadata']['candidate_only'] is False
            base=context['artifacts'][0]['base_edit']
            edit={key:base[key] for key in ('scenes','audio','captions','required_features')}
            edit['scenes'][0]['motion']='push_in'
            return {'content':json.dumps({'summary':'只增加缓慢推近','affected':['visual'],'expands_scope':False,
                'requires_new_generation':False,'reason':'现有画面内调整',
                **({'edit':edit} if 'edit' in schema['properties'] else {'changes':{'scenes':[{'scene_id':edit['scenes'][0]['scene_id'],'scenes':[edit['scenes'][0]]}]}})})}
        return await super().complete(messages,tools,schema)


@pytest.mark.skipif(not shutil.which('ffmpeg'),reason='FFmpeg unavailable')
def test_local_revision_keeps_accepted_version_then_explicitly_switches(tmp_path,monkeypatch):
    _first_cut(tmp_path,True,False,False,monkeypatch)
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
@pytest.mark.parametrize('change_protected_audio,recut,partial',[(False,False,False),(True,False,False),(False,True,False),(False,True,True)])
def test_image_only_revision_reuses_unselected_candidate_and_protects_audio_bytes(tmp_path,change_protected_audio,recut,partial):
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
            if recut:
                edit['scenes']=[{**edit['scenes'][0],'scene_id':'s1-cut1','duration':.5},
                                {**edit['scenes'][0],'scene_id':'s1-cut2','duration':.5}]
            if change_protected_audio:edit['audio'][0]['gain']=.5
            return {'content':json.dumps({'summary':'仅替换为同批现有红画面','affected':['visual','audio'] if change_protected_audio else ['visual'],
                'expands_scope':False,'requires_new_generation':False,'reason':'保留原声音',
                **({'changes':{'scenes':[{'scene_id':'s1','scenes':edit['scenes']}]}} if partial or not change_protected_audio else {'edit':edit})})}
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
    if recut:plan['narration_policy']={'continuous':False,'duration_mode':'fixed'}
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
    if recut:
        with store.transaction() as conn:
            task=conn.execute("SELECT id,payload_json FROM tasks WHERE kind='revise'").fetchone()
            payload=json.loads(task['payload_json']);payload['creative_visual_repair']=True
            conn.execute('UPDATE tasks SET payload_json=? WHERE id=?',(json.dumps(payload),task['id']))
    last=finish();outputs=[v for v in last['artifacts'] if v['kind']=='output']
    assert path_a.read_bytes()==original and len(last['plans'])==1
    assert not any(b.get('type')=='input_audio' for b in model.requests[-1][1]['content'])
    if change_protected_audio:
        assert len(outputs)==1 and last['state']=='needs_decision'
        pending=next(t for t in last['tasks'] if t['kind']=='revise')
        assert 'invalid_model_output' in pending['error_json']
        # The same task resumes from its latest known receipt, never a new run.
        service.command('resume',{'decision_id':pending['id']},command_id='resume-known-proposal',work_id=work,expected_revision=last['revision'])
        retry=finish()
        again=next(t for t in retry['tasks'] if t['id']==pending['id'])
        assert retry['state']=='needs_decision'
        assert json.loads(again['payload_json'])['revision_recovery_source']
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
def test_render_only_reuses_exact_project_without_model_or_voice_and_rejects_known_gaps(tmp_path,monkeypatch):
    from easel.production.errors import ProductionError
    from easel.production.service import row,encode,new_id,now
    from easel.production.media import file_sha256
    _first_cut(tmp_path,True,False,False,monkeypatch)
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


@pytest.mark.skipif(not shutil.which('ffmpeg'),reason='FFmpeg unavailable')
@pytest.mark.parametrize('scenario',['current_output','foreign_output','recover_known_tool_call'])
def test_revision_inspects_only_selected_output_and_recovers_known_read_request(tmp_path,monkeypatch,scenario):
    from easel.production import edit_observation
    _first_cut(tmp_path,True,False,False,monkeypatch)
    store=Store(tmp_path/'outputs/_production/production.sqlite3')
    service=WorkService(store,outputs=tmp_path/'outputs',profiles=tmp_path/'profiles')
    work=service.list_works()['items'][0]['id'];before=service.snapshot(work)
    output=next(a for a in before['artifacts'] if a['kind']=='output')
    path,_=service.artifact_path(output['id']);original=path.read_bytes()
    if scenario=='foreign_output':
        from tests.production.test_store import insert_artifact
        foreign=service.command('create',{'title':'other work'},command_id='other-work')['work_id']
        with store.transaction() as conn:
            fields=dict(conn.execute('SELECT storage_ref,digest,size_bytes FROM artifacts WHERE id=?',(output['id'],)).fetchone())
            insert_artifact(conn,foreign,'other-work-output',kind='output',media_type='video/mp4',**fields)
    class InspectingModel(RevisionModel):
        inspected=False
        author_calls=0
        async def complete(self,messages,tools,schema):
            if schema['title']=='RevisionProposal' and not self.inspected:
                self.inspected=True;self.author_calls+=1
                data=json.loads(messages[1]['content'][0]['text'])
                assert data['artifacts'][0]['review_output']['asset_id']==output['id']
                assert output['id'] not in [a.get('asset_id') for a in data['artifacts'][1:]]
                self.calls.append(messages)
                return {'tool_calls':[{'id':'inspect-output','type':'function','function':{'name':'inspect_media',
                    'arguments':json.dumps({'asset_id':'other-work-output' if scenario=='foreign_output' else output['id'],'frame_times':[.4]})}}]}
            if schema['title']=='RevisionProposal':
                replies=[json.loads(m['content']) for m in messages if m.get('role')=='tool']
                assert any(r.get('asset_id')==output['id'] and .4 in r.get('frame_times',[]) for r in replies)
                assert any(m.get('role')=='user' and isinstance(m.get('content'),list) and
                    any(b.get('type')=='image_url' for b in m['content']) for m in messages[2:])
            return await super().complete(messages,tools,schema)
    model=InspectingModel();model.calls=[]
    planning=PlanningTasks(service,OperationService(store),model,{'provider':'direct-api','model':'offline-scripted','mode':'structured'},'offline')
    creation=CreationTasks(service,planning)
    revision=RevisionTasks(service,planning,creation)
    service.command('revise',{'output_id':output['id'],'feedback':'查看本版0.4秒并增加推近，保留声音','preserve_audio':True},
        command_id='inspect-revision',work_id=work,expected_revision=before['revision'])
    from easel.production.worker import TaskResult
    async def await_render(ctx):return TaskResult(state='waiting_external',result={'fixture':'render pending'})
    worker=Worker(store,{'revise':revision.revise,'render':await_render})
    original_tools=edit_observation.edit_observation_tools
    if scenario=='recover_known_tool_call':
        # Reproduce the old registry omission while retaining the real request/receipt.
        monkeypatch.setattr(edit_observation,'edit_observation_tools',lambda paths,*a,**kw:
            original_tools({k:v for k,v in paths.items() if k!=output['id']},*a,**kw))
    asyncio.run(worker.run_once());snap=service.snapshot(work)
    task=next(t for t in snap['tasks'] if t['kind']=='revise')
    if scenario=='foreign_output':
        assert task['state']=='needs_decision' and 'invalid_model_output' in task['error_json']
        assert len(model.calls)==1 and snap['artifacts']==before['artifacts']
        return
    if scenario=='recover_known_tool_call':
        assert task['state']=='needs_decision' and len(model.calls)==1
        monkeypatch.setattr(edit_observation,'edit_observation_tools',original_tools)
        with store.connection() as conn:old_ops=[tuple(r) for r in conn.execute('SELECT id,state,receipt_json FROM operations WHERE task_id=?',(task['id'],))]
        service.command('resume',{'decision_id':task['id']},command_id='resume-read',work_id=work,expected_revision=snap['revision'])
        asyncio.run(worker.run_once());snap=service.snapshot(work)
        assert model.author_calls==1
        with store.connection() as conn:
            for old in old_ops:
                assert tuple(conn.execute('SELECT id,state,receipt_json FROM operations WHERE id=?',(old[0],)).fetchone())==old
    task=next(t for t in snap['tasks'] if t['kind']=='revise')
    assert task['state']=='succeeded',task['error_json']
    assert len(model.calls)==2
    assert path.read_bytes()==original
    assert [a for a in snap['artifacts'] if a['kind'] in {'image','video','audio'}]==[a for a in before['artifacts'] if a['kind'] in {'image','video','audio'}]
    assert next(t for t in snap['tasks'] if t['kind']=='render' and t['state']=='waiting_external')


@pytest.mark.skipif(not shutil.which('ffmpeg'),reason='FFmpeg unavailable')
def test_duplicate_scene_search_is_corrected_before_any_stock_acquisition(tmp_path,monkeypatch):
    _first_cut(tmp_path,True,False,False,monkeypatch)
    store=Store(tmp_path/'outputs/_production/production.sqlite3')
    service=WorkService(store,outputs=tmp_path/'outputs',profiles=tmp_path/'profiles')
    work=service.list_works()['items'][0]['id'];before=service.snapshot(work)
    output=next(a for a in before['artifacts'] if a['kind']=='output')
    class SearchModel(RevisionModel):
        async def complete(self,messages,tools,schema):
            result=await super().complete(messages,tools,schema)
            if schema['title']=='RevisionProposal':
                value=json.loads(result['content']);count=len(self.calls)
                if count==2:
                    assert any('同一原场景只能保留一条' in m.get('content','') for m in messages if isinstance(m.get('content'),str))
                value['material_searches']=([{'scene_id':'s1','query':query,'media_types':['image'],'options':1}
                    for query in (['blue image','blue desk'] if count==1 else ['blue image'])] if count<3 else [])
                result={'content':json.dumps(value)}
            return result
    model=SearchModel();model.calls=[]
    planning=PlanningTasks(service,OperationService(store),model,{'provider':'direct-api','model':'offline-scripted','mode':'structured'},'offline')
    creation=CreationTasks(service,planning)
    class Supply:
        calls=[]
        def revision_visuals(self,ctx,searches):
            self.calls.append(searches)
            assert len(searches)==1 and len(model.calls)==2
            return []
    supply=Supply();supply.calls=[]
    revision=RevisionTasks(service,planning,creation,supply=supply)
    service.command('revise',{'output_id':output['id'],'feedback':'局部补一张蓝色示意图','preserve_audio':True},
        command_id='search-revision',work_id=work,expected_revision=before['revision'])
    from easel.production.worker import TaskResult
    async def await_render(ctx):return TaskResult(state='waiting_external')
    asyncio.run(Worker(store,{'revise':revision.revise,'render':await_render}).run_once())
    snapshot=service.snapshot(work);task=next(t for t in snapshot['tasks'] if t['kind']=='revise')
    assert task['state']=='succeeded',task['error_json']
    assert len(supply.calls)==1 and len(model.calls)==3
