"""Real regressions with temporary stores and fake transports; no paid requests."""
import asyncio
from copy import deepcopy
import json
from types import SimpleNamespace
import pytest
from pydantic import BaseModel, ValidationError

from .test_conversation import env, entry, turn, tool, raises
from .test_conversation_pipeline import seed, pipe
from easel.work_bridge import Identity
from easel.native_diagnostics import NativeEnd
from easel.production.service import row
from easel.production.context import TaskContext
from easel.production.model_tasks import ModelTaskRunner
from easel.production.tools import ScopedTool
from easel.production.contracts import Contract
from easel.production.creation import CreativeEdit
from easel.production.edit_observation import check_visual_evidence, edit_observation_tools
from easel.production.narration import measured_execution_plan, narration_segments
from web.conversation_api import VideoChat


def test_fixed_duration_survives_confirmed_dialogue_into_planning_basis(env):
    channel=seed(env);s,c=env
    seg=entry(c,profile_ref='one',channel_id=channel,director_revision='v4',director_trial=True)
    b,i,_=turn(s,c,seg,'做一个固定30秒的视频')
    w=pipe(b,i,'draft',user_quote='做一个固定30秒的视频',values={'title':'fixture','input_text':'固定30秒'})['work_id']
    p=pipe(b,i,'offer',action='plan',values={'request':'固定30秒','duration_seconds':30},summary='整理固定30秒方案')
    assert 'duration_seconds' not in s.snapshot(w)['settings']
    b.end(Identity(**i));b,i,_=turn(s,c,seg,'同意整理30秒方案',id='yes')
    result=pipe(b,i,'answer',proposal_id=p['proposal_id'],hash=p['hash'],user_quote='同意整理30秒方案')
    assert s.snapshot(w)['settings']['duration_seconds']==30
    task=s.snapshot(w)['tasks'][0]
    assert json.loads(task['payload_json'])['creation_basis']['settings']['duration_seconds']==30
    assert pipe(b,i,'answer',proposal_id=p['proposal_id'],hash=p['hash'],user_quote='同意整理30秒方案')==result
    assert len(s.snapshot(w)['runs'])==1
    with s.store.connection() as conn:assert conn.execute('select count(*) from operations').fetchone()[0]==0


def test_native_length_record_is_bound_redacted_and_does_not_retry(env):
    s,c=env;seg=entry(c,profile_ref='one');b,i,_=turn(s,c,seg,'继续讨论')
    d={'stop_reason':'length','text_chars':0,'tool_calls':0,'usage_status':'missing_or_zero',
       'parameter_source':'configured_not_wire','max_tokens':8192,'reasoning_effort':'medium'}
    assert NativeEnd(**i,diagnostic={**d,'prompt':'SECRET'}).diagnostic is None
    with pytest.raises(Exception):b.end(NativeEnd(**{**i,'run_id':'wrong'},diagnostic=d))
    b.end(NativeEnd(**i,diagnostic=d))
    view,message=VideoChat.interrupted_result(s,'ui','turn')
    assert '长度上限' in message and '不会自动重发' in message
    assert s.list_works()['items']==[]
    with s.store.connection() as conn:
        payload=json.loads(conn.execute('select payload_json from conversation_turns').fetchone()[0])
        assert payload['model_diagnostic']['usage_status']=='missing_or_zero'
    # Ending this reply doesn't block a fresh human conversation or start production.
    b,i,_=turn(s,c,seg,'先解释原因',id='next')
    b.end(NativeEnd(**i,diagnostic={'prompt':'SECRET'}))
    assert c.view('ui')['turns'][-1]['state']=='ended'


def test_tool_exchange_preserves_provider_reasoning_only_in_model_history():
    class Result(BaseModel):answer:str
    class Args(Contract):pass
    async def inspect(args,ctx):return {'observed':True}
    class Transport:
        capabilities=frozenset({'text','structured','tools'})
        def __init__(self):self.calls=[]
        async def complete(self,messages,*_):
            self.calls.append(deepcopy(messages))
            if len(self.calls)==1:
                return {'content':None,'reasoning_content':'private provider reasoning',
                    'tool_calls':[{'id':'a','function':{'name':'inspect_media','arguments':'{}'}}]}
            return {'content':'{"answer":"ok"}'}
    async def authorize(_):pass
    t=Transport()
    result=asyncio.run(ModelTaskRunner(t,authorize).run(TaskContext('w','r','t'),'inspect',Result,
        tools=(ScopedTool('inspect_media','observe',Args,inspect,()),)))
    assistant=next(m for m in t.calls[1] if m['role']=='assistant')
    assert assistant['reasoning_content']=='private provider reasoning'
    assert result.model_dump()=={'answer':'ok'} and len(t.calls)==2


def test_visual_evidence_checks_only_real_references_not_artistic_thresholds():
    data={'scenes':[{'scene_id':'s1','asset_id':'a','source_start':5,'duration':4}],
        'visual_evidence':[{'scene_id':'s1','asset_id':'a','observed_times':[6],
            'observation':'翻页','uncertainty':'无法证明动作完成；仅作氛围'}]}
    edit=CreativeEdit.model_validate(data)
    check_visual_evidence(edit,{'a':[0,6,14]})  # uncertainty doesn't add a veto
    check_visual_evidence(CreativeEdit.model_validate({'scenes':data['scenes']}),{})  # legacy receipt
    for fields in ({'asset_id':'other'},{'observed_times':[7]},{'observed_times':[14]}):
        bad=deepcopy(data);bad['visual_evidence'][0].update(fields)
        with pytest.raises(ValueError):check_visual_evidence(CreativeEdit.model_validate(bad),{'a':[0,6,14]})


def test_tool_observation_tracks_only_actual_not_requested_timestamps(monkeypatch):
    import easel.production.edit_observation as module
    monkeypatch.setattr(module,'observe_media',lambda *a,**k:((),frozenset(),{'frame_times':[None,6]}))
    observed={};t=edit_observation_tools({'a':'fake'},observed)[0]
    asyncio.run(t.invoke({'asset_id':'a','frame_times':[5,6]},TaskContext('w','r','t',allowed_handles=frozenset({'a'}))))
    assert observed=={'a':[None,6]}


@pytest.mark.parametrize('explicit,mode',[(True,'voice_driven'),(False,'fixed'),(False,'voice_driven'),(False,None)])
def test_new_plan_fixed_and_voice_driven_remain_separate(tmp_path,explicit,mode):
    from easel.production.store import Store
    from easel.production.service import WorkService
    from easel.production.operations import OperationService
    from easel.production.planning import PlanningTasks
    from easel.production.worker import Worker
    store=Store(tmp_path/'db');store.initialize();s=WorkService(store,outputs=tmp_path/'outputs',profiles=tmp_path/'profiles')
    settings={'audio_mode':'voice','voice':{'provider':'fake','model':'fake','voice_id':'fixed'}}
    if explicit:settings['duration_seconds']=30
    w=s.command('create',{'title':'fixture','settings':settings},command_id='create')['work_id']
    identity={'provider':'fake','model':'fake','mode':'structured'}
    s.command('plan',{'services':[identity]},command_id='plan',work_id=w,expected_revision=1)
    class Transport:
        capabilities=frozenset({'text','structured'})
        async def complete(self,messages,tools,schema):
            value={'verdict':'pass','findings':[]} if schema['title']=='DraftReview' else {
                'title':'fixture','summary':'fixture','script':'fixture','settings':{**settings,'duration_seconds':30},
                'scenes':[{'id':'s1','purpose':'think','visual':'desk','narration':'先做一件小事。','duration_seconds':30}],
                'narration_policy':{'continuous':True,'duration_mode':mode} if mode else None}
            return {'content':json.dumps(value)}
    p=PlanningTasks(s,OperationService(store),Transport(),identity,'fixture')
    asyncio.run(Worker(store,{'plan':p.plan}).run_once())
    snap=s.snapshot(w);assert snap['state']=='awaiting_confirmation'
    plan=snap['plans'][0]['plan'];expected='fixed' if explicit or mode is None else mode
    assert plan['narration_policy']=={'continuous':True,'duration_mode':expected}
    seg=narration_segments(plan)[0]
    out,timing=measured_execution_plan(plan,[{'metadata_json':json.dumps({'role':'voice','segment_id':seg['segment_id'],'duration':18.936})}])
    assert out['settings']['duration_seconds']==pytest.approx(30 if expected=='fixed' else 19.9666667)
    if explicit:
        bad=deepcopy(plan);bad['narration_policy']['duration_mode']='voice_driven'
        with s.store.connection() as conn:
            raises('plan_constraint_changed',lambda:s.validate_plan(conn,row(conn,'works',w),bad))


@pytest.mark.parametrize('content,finish', [('partial answer','length'), ('','stop')])
def test_sse_incomplete_answer_is_not_success_or_replayed(env,tmp_path,monkeypatch,content,finish):
    import web.conversation_api as api
    s,c=env;seg=entry(c,profile_ref='one');b,i,result=turn(s,c,seg,'讨论')
    calls=[];saved=[]
    class Response:
        async def __aenter__(self):return self
        async def __aexit__(self,*a):pass
        def raise_for_status(self):pass
        async def aiter_lines(self):
            yield 'data: '+json.dumps({'choices':[{'delta':{'content':content},'finish_reason':None}]})
            b.end(NativeEnd(**i,diagnostic={'stop_reason':finish}))
            yield 'data: '+json.dumps({'choices':[{'delta':{},'finish_reason':finish}]})
            yield 'data: [DONE]'
    class Client:
        def __init__(self,*a,**kw):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*a):pass
        def stream(self,*a,**kw):calls.append(kw['json']);return Response()
    monkeypatch.setattr(api.httpx,'AsyncClient',Client)
    path=tmp_path/'events.jsonl'
    chat=VideoChat(lambda:s,lambda _:path,lambda *a:saved.append(a),gateway_url='http://fixture',gateway_token='fake')
    asyncio.run(chat._deliver('ui','turn',result,path))
    events=[json.loads(x) for x in path.read_text().splitlines()]
    assert events[-1]['event']=='error' and all(e['event']!='done' for e in events)
    assert len(calls)==1 and s.list_works()['items']==[]
    if finish=='length':assert '长度上限' in events[-1]['data']
    assert saved[0][-1]['clean_end'] is False
