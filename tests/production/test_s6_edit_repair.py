"""S6 regressions with synthetic inputs only; no production or E2E calls."""
import asyncio
from copy import deepcopy
import json
from types import SimpleNamespace

import httpx
import pytest

from easel.production.narration import measured_execution_plan, check_voice_schedule
from .test_continuous_narration import sample, record, clip


def test_fixed_duration_exposes_real_speech_without_imposing_silence_gate():
    plan = sample()
    plan['settings']['duration_seconds'] = 45
    plan['narration_policy']['duration_mode'] = 'fixed'
    before = deepcopy(plan)
    measured, timing = measured_execution_plan(plan, [record(plan, duration=31)])
    assert measured == before == plan
    assert timing['mode'] == 'fixed' and timing['duration'] == 45
    assert timing['voice_schedule'][0]['duration'] == 31
    assert timing['placement'] == 'advisory'
    assert timing['aligned_captions'] is None
    # Deliberate opening/closing silence is not an automatic failure.
    check_voice_schedule([clip(at=2, duration=31)], [record(plan, duration=31)], timing)


def test_fixed_alignment_is_literal_not_proportional_scene_timing():
    plan = sample(); plan['narration_policy']['duration_mode'] = 'fixed'
    alignment = {'status':'received', 'segments':[
        {'text':plan['scenes'][0]['narration'], 'start':0, 'end':3},
        {'text':plan['scenes'][1]['narration'], 'start':4, 'end':6}]}
    _, timing = measured_execution_plan(plan, [record(plan, duration=7, alignment=alignment)])
    assert timing['scene_anchors'][0]['scene_id'] == 's1'
    assert timing['scene_anchors'][1]['start'] == pytest.approx(4.2)
    alignment['segments'][1]['text'] = 'invented'
    _, bad = measured_execution_plan(plan, [record(plan, duration=7, alignment=alignment)])
    assert bad['aligned_captions'] is None and bad['scene_anchors'] == []


def test_observation_budget_reuses_frames_and_stops_growth(monkeypatch):
    from easel.production.edit_observation import ObservationBudget, edit_observation_tools
    from easel.production.context import TaskContext
    calls = []
    def observe(path, **kw):
        times = list(kw.get('frame_times') or [0, 1])[:kw.get('max_frames', 8)]
        calls.append(times)
        return tuple({'type':'image_url','image_url':{'url':str(t)}} for t in times), frozenset({'image'}), {'frame_times':times}
    monkeypatch.setattr('easel.production.edit_observation.observe_media', observe)
    budget = ObservationBudget(limit=3)
    observed = {}
    tools = edit_observation_tools({'a':'a.mp4'}, observed, budget=budget)
    ctx = TaskContext('w','r','t',allowed_handles=frozenset({'a'}))
    async def run():
        a = await tools[0].invoke({'asset_id':'a','frame_times':[0,1]},ctx)
        b = await tools[0].invoke({'asset_id':'a','frame_times':[1,2]},ctx)
        c = await tools[0].invoke({'asset_id':'a','frame_times':[2,3]},ctx)
        return a,b,c
    a,b,c = asyncio.run(run())
    assert calls == [[0,1],[2]]
    assert len(a.media) > len(b.media) and isinstance(c, dict)
    assert c['unobserved_times'] == [3]
    assert c['budget_exhausted'] is True
    assert observed['a'] == [0,1,2]
    assert sum(b['type']=='image_url' for b in budget.media) == 3


@pytest.mark.parametrize('body', [b'<html>private service failure</html>',
    b'{"error":{"code":"internal_error","message":"private prompt secret-fixture-key"}}',
    b'{"error":{"code":"private-user-text","message":"secret"}}'])
def test_http_error_safe_diagnostics(body):
    from easel.production.model_tasks import HTTPModelTransport, ModelTaskError
    from .test_model_call_diagnostics import SETTINGS
    calls=[]
    def handler(req):
        calls.append(req)
        return httpx.Response(500,content=body,headers={'x-request-id':'req-500'})
    t=HTTPModelTransport(SETTINGS,transport=httpx.MockTransport(handler))
    with pytest.raises(ModelTaskError) as caught:
        asyncio.run(t.complete([],[],{}))
    diagnostic=caught.value.diagnostic
    assert diagnostic['error_body_bytes']==len(body)
    assert diagnostic['error_body_format'] in {'json','html'}
    assert diagnostic['request_id']=='req-500' and len(calls)==1
    assert all(word not in json.dumps(diagnostic) for word in ['private','secret-fixture-key'])
    assert '请求格式' not in str(caught.value)


@pytest.mark.parametrize('scope', ['visual', 'protected_timing_or_content'])
def test_quality_component_routes_scope_without_render_or_model(monkeypatch, tmp_path, scope):
    from contextlib import nullcontext
    import sqlite3
    from easel.production.creation import CreationTasks
    from easel.production.context import TaskContext
    from easel.production.editors import EditProject
    from easel.production.quality import VisualPreviewReview
    db=sqlite3.connect(':memory:')
    db.execute('CREATE TABLE reviews(id,work_id,output_id,feedback,created_at)')
    db.execute('CREATE TABLE tasks(id,payload_json)')
    db.execute("INSERT INTO tasks VALUES ('t','{}')")
    project=EditProject(work_id='w',plan_revision=1,revision=1,width=1920,height=1080,duration=45,
        audio_mode='voice', scenes=[{'scene_id':'s1','asset_id':'image','duration':45}],
        audio=[{'clip_id':'v','asset_id':'voice','at':2,'duration':31.176,'role':'voice'}],captions=[])
    path=tmp_path/'project.json';path.write_text(project.model_dump_json())
    records={'out':{'id':'out','work_id':'w'},'project':{'id':'project','work_id':'w','metadata_json':'{}'},
             't':{'payload_json':'{}'}}
    monkeypatch.setattr('easel.production.creation.row',lambda conn,table,key:records[key])
    monkeypatch.setattr('easel.production.creation.artifact_file',lambda service,record:path)
    monkeypatch.setattr('easel.production.media.probe_media',lambda path:{'video':True,'duration':45,
        'width':1920,'height':1080,'audio':True})
    monkeypatch.setattr('easel.production.inspection.observe_media',lambda *a,**k:((),frozenset(),{}))
    class Runner:
        async def run(self,context,instruction,result_type,**kw):
            assert 'unvoiced_tail_seconds' in context.brief and '33.176' in context.brief
            assert '不因没有具体软件界面或品牌判失败' in instruction
            return VisualPreviewReview(verdict='fail',observations=['sample'],findings=['specific defect'],
                limitations=['not heard'],repair_scope=scope,affected_scene_ids=['s1','unknown'])
    context=TaskContext('w','r','t',plan={'narration_policy':{'continuous':True,'duration_mode':'fixed'}})
    service=SimpleNamespace(store=SimpleNamespace(connection=lambda:nullcontext(db)),_event=lambda *a,**kw:None)
    planning=SimpleNamespace(context=lambda _:context,runner=lambda *a,**kw:Runner())
    creation=CreationTasks(service,planning,editor=object(),manual_review_only=True,visual_review=True)
    checks=[];states=[]
    creation._check=lambda *a,**kw:checks.append((a,kw))
    creation._quality_state=lambda *a:states.append(a[-1])
    ctx=SimpleNamespace(work_id='w',run_id='r',task_id='t',payload={'output_id':'out','project_id':'project'},
                        transaction=lambda:nullcontext(db))
    result=asyncio.run(creation.quality(ctx))
    assert states==['needs_fix']
    assert checks[-1][0][3]=='fail'
    assert result.next_kind=='revise' and result.next_payload['preserve_audio'] is True
    assert result.next_payload['repair_scope']==scope
    assert result.next_payload['affected_scene_ids']==['s1']
    assert db.execute('SELECT count(*) FROM reviews').fetchone()[0]==1
    db.close()


@pytest.mark.parametrize('legacy', [False, True])
def test_revision_component_scopes_observation_and_keeps_old_policy(monkeypatch,tmp_path,legacy):
    from contextlib import nullcontext
    import sqlite3
    from pathlib import Path
    from easel.production.revisions import RevisionTasks
    from easel.production.editors import EditProject
    from easel.production.context import TaskContext
    from easel.production.model_tasks import ModelTaskError
    db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row
    db.executescript('CREATE TABLE tasks(id,payload_json); CREATE TABLE artifacts(id,work_id,run_id,deleted_at,kind,created_at); CREATE TABLE runs(id,plan_revision); CREATE TABLE artifact_edges(artifact_id,dependency_id);')
    db.execute("INSERT INTO runs VALUES ('r',1)")
    records=[{'id':id,'kind':'video','metadata_json':'{}'} for id in ['selected','unaffected','alternative']]
    for r in records:db.execute('INSERT INTO artifacts VALUES (?,?,?,?,?,?)',(r['id'],'w','r',None,'video','0'))
    for id in ['selected','unaffected']:db.execute("INSERT INTO artifact_edges VALUES ('project',?)",(id,))
    payload={'creative_visual_repair':True,'preserve_audio':True,'affected_scene_ids':['s1']}
    if legacy:payload['revision_asset_ids']=[r['id'] for r in records]
    db.execute('INSERT INTO tasks VALUES (?,?)',('t',json.dumps(payload)))
    base=EditProject(work_id='w',plan_revision=1,revision=1,width=1920,height=1080,duration=10,
        audio_mode='silent',scenes=[{'scene_id':'s1','asset_id':'selected','source_start':3,'duration':5},
                                  {'scene_id':'s2','asset_id':'unaffected','duration':5}],audio=[],captions=[])
    path=tmp_path/'project.json';path.write_text(base.model_dump_json())
    rows={'review':{'id':'review','work_id':'w','feedback':'repair s1'},
          'out':{'id':'out','work_id':'w','metadata_json':'{"project_id":"project"}'},
          'project':{'id':'project','metadata_json':'{}'}}
    def row(conn,table,key):
        return dict(db.execute('SELECT * FROM tasks WHERE id=?',(key,)).fetchone()) if table=='tasks' else rows[key]
    monkeypatch.setattr('easel.production.revisions.row',row)
    monkeypatch.setattr('easel.production.revisions.artifact_file',lambda service,r:path if r['id']=='project' else Path(r['id']))
    monkeypatch.setattr('easel.production.revisions.recorded_proposal',lambda *a:None)
    observed=[]
    def observe(path,**kw):
        observed.append((str(path),kw))
        times=list(kw.get('frame_times') or [0])
        return tuple({'type':'image_url','image_url':{'url':'fixture'}} for t in times),frozenset({'image'}),{'frame_times':times}
    monkeypatch.setattr('easel.production.inspection.observe_media',observe)
    monkeypatch.setattr('easel.production.edit_observation.observe_media',observe)
    class Runner:
        async def run(self,context,instruction,result_type,**kw):
            assert len([a for a in context.artifacts if 'asset_id' in a])==3
            if not legacy:
                assert '优先复核失败场景' in instruction
                assert '先实际复查全部候选' not in instruction
            raise ModelTaskError('fixture_stop','component stopped before model')
    context=TaskContext('w','r','t',plan={'narration_policy':{'duration_mode':'fixed','continuous':True}})
    planning=SimpleNamespace(context=lambda _:context,runner=lambda *a,**k:Runner(),
        transport=SimpleNamespace(capabilities=frozenset({'tools'})))
    service=SimpleNamespace(store=SimpleNamespace(connection=lambda:nullcontext(db)))
    creation=SimpleNamespace(assets=lambda *a:(records,None))
    task=SimpleNamespace(work_id='w',run_id='r',task_id='t',plan_revision=1,
        payload={'review_id':'review','output_id':'out'},transaction=lambda:nullcontext(db))
    result=asyncio.run(RevisionTasks(service,planning,creation).revise(task))
    assert result.error.code=='fixture_stop'
    saved=json.loads(db.execute('SELECT payload_json FROM tasks').fetchone()[0])
    if legacy:
        assert 'observation_policy' not in saved
        assert {p for p,_ in observed}=={'out','selected','unaffected','alternative'}
    else:
        assert saved['observation_policy']=='targeted-v1'
        assert {p for p,_ in observed}=={'out','selected'}
        assert next(k for p,k in observed if p=='selected')['frame_times']==(5.5,)
    db.close()


def test_protected_scope_uses_existing_confirmation_without_model(tmp_path):
    from easel.production.store import Store
    from easel.production.service import WorkService, digest
    from easel.production.revisions import RevisionTasks
    from easel.production.artifacts import register_file, artifact_file
    from easel.production.editors import EditProject
    from easel.production.errors import ProductionError
    store=Store(tmp_path/'test.sqlite3');store.initialize()
    service=WorkService(store,outputs=tmp_path/'outputs',profiles=tmp_path/'profiles')
    work=service.command('create',{'title':'scope fixture'},command_id='create')['work_id']
    plan={'title':'fixture','summary':'fixture','script':'fixture',
          'scenes':[{'id':'s1','purpose':'test','visual':'generic scene'}],
          'settings':{'duration_seconds':45,'aspect_ratio':'16:9','audio_mode':'silent'}}
    saved=service.command('plan',{'generate':False,'plan':plan},command_id='plan',work_id=work,expected_revision=1)
    service.command('confirm',{'plan_revision':1,'plan_hash':saved['plan_hash'],'services':[]},
        command_id='confirm',work_id=work,expected_revision=2)
    with store.connection() as conn:
        task=dict(conn.execute('SELECT * FROM tasks').fetchone())
    ctx=SimpleNamespace(work_id=work,run_id=task['run_id'],task_id=task['id'],plan_revision=1,
        transaction=store.transaction,payload={})
    base=EditProject(work_id=work,plan_revision=1,revision=1,width=1920,height=1080,duration=45,
        audio_mode='silent',scenes=[{'scene_id':'s1','asset_id':'fixture','duration':45}],audio=[],captions=[])
    file=tmp_path/'project.json';file.write_text(base.model_dump_json())
    project=register_file(service,ctx,file,kind='edit_project',media_type='application/json',metadata={})
    output=register_file(service,ctx,file,kind='output',media_type='application/json',
        metadata={'project_id':project['id']},output=True)
    ctx.payload={'schema_version':1,'review_id':'review','output_id':output['id'],'repair_scope':'protected_timing_or_content'}
    with store.transaction() as conn:
        conn.execute('INSERT INTO reviews(id,work_id,output_id,feedback,created_at) VALUES (?,?,?,?,?)',
            ('review',work,output['id'],'已证实需要调整内容范围','fixture'))
        conn.execute("UPDATE tasks SET kind='revise',payload_json=? WHERE id=?",(json.dumps(ctx.payload),ctx.task_id))
    result=asyncio.run(RevisionTasks(service,None,None).revise(ctx))
    assert result.state=='needs_decision' and result.error.code=='revision_scope_confirmation'
    with store.transaction() as conn:
        conn.execute("UPDATE tasks SET state='needs_decision'")
        conn.execute("UPDATE runs SET state='needs_decision'")
        conn.execute("UPDATE works SET state='needs_decision'")
        changes=json.loads(conn.execute('SELECT changes_json FROM reviews').fetchone()[0])
        assert changes['source']=='quality_scope'
        assert conn.execute('SELECT count(*) FROM operations').fetchone()[0]==0
    revision=service.snapshot(work)['revision']
    with pytest.raises(ProductionError):
        service.command('confirm_revision',{'review_id':'review','change_hash':'wrong'},
            command_id='bad',work_id=work,expected_revision=revision)
    confirmed=service.command('confirm_revision',{'review_id':'review','change_hash':digest(changes)},
        command_id='scope-confirm',work_id=work,expected_revision=revision)
    with store.connection() as conn:
        assert conn.execute('SELECT kind FROM runs WHERE id=?',(confirmed['run_id'],)).fetchone()[0]=='planning'
        assert conn.execute('SELECT count(*) FROM operations').fetchone()[0]==0
    assert artifact_file(service,output).read_bytes()==file.read_bytes()


def test_edit_component_receives_fixed_timing_without_changing_plan(monkeypatch):
    from pathlib import Path
    from easel.production.creation import CreationTasks
    from easel.production.context import TaskContext
    from easel.production.model_tasks import ModelTaskError
    plan=sample();plan['narration_policy']['duration_mode']='fixed'
    plan['settings'].update(duration_seconds=45,aspect_ratio='16:9')
    before=deepcopy(plan)
    voice={**record(plan,duration=31),'kind':'audio'}
    monkeypatch.setattr('easel.production.creation.artifact_file',lambda *a:Path('fixture'))
    monkeypatch.setattr('easel.production.creation.observe_media',lambda *a,**kw:((),frozenset(),{}))
    monkeypatch.setattr('easel.production.inspection.observe_audio_technical',lambda *a:{})
    class Runner:
        async def run(self,context,instruction,result_type,**kw):
            assert context.plan==before
            timing=json.loads(context.brief.split('：')[-1])
            assert timing['mode']=='fixed' and timing['voice_schedule'][0]['duration']==31
            assert timing['aligned_captions'] is None
            raise ModelTaskError('fixture_stop','before any model or editor')
    context=TaskContext('w','r','t',plan=plan)
    planning=SimpleNamespace(context=lambda _:context,runner=lambda *a,**kw:Runner(),transport=None)
    creation=CreationTasks(SimpleNamespace(),planning,editor=object())
    creation.assets=lambda *a:([voice],SimpleNamespace(assets={'voice-a':{}}))
    result=asyncio.run(creation.edit(SimpleNamespace(payload={})))
    assert result.error.code=='fixture_stop' and plan==before


def test_bounded_tools_preserve_reasoning_and_finish_with_existing_evidence(monkeypatch):
    from pydantic import BaseModel
    from easel.production.model_tasks import ModelTaskRunner
    from easel.production.context import TaskContext
    from easel.production.edit_observation import ObservationBudget, edit_observation_tools
    class Answer(BaseModel):
        summary:str
    def observe(path,**kw):
        times=kw['frame_times']
        return tuple({'type':'image_url','image_url':{'url':str(t)}} for t in times),frozenset({'image'}),{'frame_times':list(times)}
    monkeypatch.setattr('easel.production.edit_observation.observe_media',observe)
    class Transport:
        capabilities=frozenset({'text','structured','image','tools'})
        calls=0
        async def complete(self,messages,tools,schema):
            self.calls+=1
            if self.calls<4:
                return {'reasoning_content':'retained-'+str(self.calls),'tool_calls':[{
                    'id':'call-'+str(self.calls),'function':{'name':'inspect_media','arguments':json.dumps({
                        'asset_id':'a','frame_times':[self.calls-1,self.calls]})}}]}
            images=[block for m in messages if isinstance(m.get('content'),list) for block in m['content'] if block['type']=='image_url']
            assert len(images)==3
            assert [m['reasoning_content'] for m in messages if 'reasoning_content' in m]==['retained-1','retained-2','retained-3']
            assert json.loads(messages[-1]['content'])['unobserved_times']==[3]
            return {'content':'{"summary":"observed limits, not claimed missing frames"}'}
    transport=Transport()
    async def authorize(_):pass
    tools=edit_observation_tools({'a':'fixture'},budget=ObservationBudget(limit=3))
    context=TaskContext('w','r','t',allowed_handles=frozenset({'a'}))
    result=asyncio.run(ModelTaskRunner(transport,authorize).run(context,'fixture',Answer,tools=tools))
    assert result.summary and transport.calls==4
