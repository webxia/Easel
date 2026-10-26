"""CTX-01: synthetic session contracts only. No installed Gateway or model."""
import asyncio
import copy
import json
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from tests.production.test_conversation import env, entry, turn, tool
from easel.conversation_bridge import PersistentWorkToolBridge
from easel.conversation_compaction import ContextPreparation, ContextPreparationError, SessionRPC, pressure
from easel.gateway_questions import GatewayClient, GatewayRPCError, GatewayUnsupportedError
from easel.work_bridge import Identity, Claim


class NoPressureRPC:
    def __init__(self,*args):pass
    def describe(self,key):return {'sessionId':'native-'+key.rsplit(':',1)[-1]}
    def compact(self,key):raise AssertionError('no compression expected')
    def close(self):pass


class FakeRPC:
    def __init__(self, session, outcome=None):
        self.session = session
        self.calls = []
        self.outcome = outcome if outcome is not None else {'ok':True,'compacted':True,'result':{'tokensBefore':281483,'tokensAfter':20000}}
    def describe(self,key):
        self.calls.append(('describe',key))
        return copy.deepcopy(self.session)
    def complete(self):
        self.session.pop('contextBudgetStatus',None)
        self.session['compactionCheckpointCount'] += 1
    def compact(self,key):
        self.calls.append(('compact',key))
        if isinstance(self.outcome,Exception):raise self.outcome
        if self.outcome.get('ok') and self.outcome.get('compacted'):self.complete()
        return self.outcome
    def close(self):pass


def reserve(env):
    service,c=env;seg=entry(c)
    bridge,identity,_=turn(service,c,seg,'HISTORY_SENTINEL',id='history')
    bridge.end(Identity(**identity))
    request=bridge.reserve(ui_session='ui',turn_id='next',segment_id=seg,message='CURRENT_SENTINEL',attachments=[])
    session={'sessionId':identity['session_id'],'model':'fixture','modelProvider':'fake','contextTokens':256000,
             'compactionCheckpointCount':0,
             'contextBudgetStatus':{'source':'pre-prompt-estimate','sessionId':identity['session_id'],
                 'provider':'fake','model':'fixture','contextTokenBudget':256000,'updatedAt':123,
                 'shouldCompact':True,'route':'compact_only','estimatedPromptTokens':281483,'promptBudgetBeforeReserve':236000}}
    return bridge,request,session


def stored(bridge):
    with bridge.store.connection() as conn:
        record=dict(conn.execute("SELECT * FROM conversation_turns WHERE id='next'").fetchone())
    return record,json.loads(record['payload_json'])


def expire(bridge):
    with bridge.store.transaction() as conn:
        record,payload=stored(bridge)
        payload['delivery_lease_until']=0
        bridge._save(conn,'next',payload,record['state'])


def preparation(bridge,rpc):return ContextPreparation(bridge,'http://offline.invalid','test',rpc_factory=lambda *a:rpc)


def test_sources_are_references_and_user_quote_once_with_full_tool_access(env):
    bridge,request,session=reserve(env)
    assert 'HISTORY_SENTINEL' not in request['prompt']
    assert request['prompt'].count('CURRENT_SENTINEL')==1
    ident=dict(agent_id='main',session_key=request['payload']['session_key'],session_id=session['sessionId'],run_id='native-next')
    bridge.claim(Claim(**ident,prompt=request['prompt']))
    context=tool(bridge,ident,'easel_work_context',{})
    assert any(s['text']=='HISTORY_SENTINEL' for s in context['sources'])
    assert any(s['text']=='CURRENT_SENTINEL' for s in context['sources'])


def test_pressure_compacts_before_admission_and_cannot_replay_chat(env):
    bridge,request,session=reserve(env);rpc=FakeRPC(session);prep=preparation(bridge,rpc)
    result=prep.prepare('next')
    assert [c[0] for c in rpc.calls]==['describe','compact','describe']
    assert result['payload']['run_id'] is None
    assert 'HISTORY_SENTINEL' not in result['prompt']
    assert result['prompt'].count('CURRENT_SENTINEL')==1
    with pytest.raises(Exception):
        bridge.claim(Claim(agent_id='main',session_key=request['payload']['session_key'],session_id=session['sessionId'],run_id='bad',prompt=result['prompt']))
    prep.submitted('next',result['preparation_owner'])
    with pytest.raises(ContextPreparationError):prep.submitted('next',result['preparation_owner'])
    assert ContextPreparation.recoverable(bridge) is None
    with pytest.raises(ContextPreparationError):prep.prepare('next')


@pytest.mark.parametrize('change',[{'shouldCompact':False},{'source':'unknown'},{'model':'other'},{'sessionId':'other'},{'contextTokenBudget':999}])
def test_absent_or_stale_pressure_does_not_add_compression(env,change):
    bridge,_,session=reserve(env);session['contextBudgetStatus'].update(change)
    rpc=FakeRPC(session);preparation(bridge,rpc).prepare('next')
    assert [c[0] for c in rpc.calls]==['describe']


def test_no_history_no_compression(env):
    service,c=env;seg=entry(c);bridge=PersistentWorkToolBridge(service)
    bridge.reserve(ui_session='ui',turn_id='next',segment_id=seg,message='new',attachments=[])
    rpc=FakeRPC(None);preparation(bridge,rpc).prepare('next')
    assert [c[0] for c in rpc.calls]==['describe']


@pytest.mark.parametrize('outcome,code',[
    ({'ok':True,'compacted':False,'reason':'no transcript'},'compaction_not_completed'),
    ({'ok':False,'compacted':False},'compaction_not_completed'),
    ({'ok':True,'compacted':True,'result':{'tokensBefore':100,'tokensAfter':100}},'compaction_no_progress'),
    (GatewayRPCError('INVALID_REQUEST'),'compaction_rejected'),
])
def test_failed_compaction_is_unsent_not_unknown_native_and_not_repeated(env,outcome,code):
    bridge,_,session=reserve(env);rpc=FakeRPC(session,outcome);prep=preparation(bridge,rpc)
    with pytest.raises(ContextPreparationError,match=code):prep.prepare('next')
    record,payload=stored(bridge)
    assert record['state']=='reserved' and payload['run_id'] is None
    assert not payload['context_preparation'].get('chat_submitted')
    expire(bridge)
    with pytest.raises(ContextPreparationError):prep.prepare('next')
    assert len([c for c in rpc.calls if c[0]=='compact'])==1
    assert prep.cancel('next')
    assert stored(bridge)[0]['state']=='ended'


@pytest.mark.parametrize('outcome',[TimeoutError(),{'ok':True,'compacted':False,'result':{'details':{'pending':True}}}])
def test_uncertain_compact_reads_back_after_restart_without_second_paid_call(env,outcome):
    bridge,_,session=reserve(env);rpc=FakeRPC(session,outcome);prep=preparation(bridge,rpc)
    with pytest.raises(ContextPreparationError):prep.prepare('next')
    expire(bridge)
    assert ContextPreparation.recoverable(bridge)['turn_id']=='next'
    with pytest.raises(ContextPreparationError):preparation(bridge,rpc).prepare('next')
    rpc.complete();expire(bridge)
    recovered=preparation(bridge,rpc).prepare('next')
    assert recovered['payload']['context_preparation']['state']=='ready'
    assert len([c for c in rpc.calls if c[0]=='compact'])==1


def test_cancellation_during_compact_never_admits_chat(env):
    bridge,_,session=reserve(env);rpc=FakeRPC(session);prep=preparation(bridge,rpc)
    original=rpc.compact
    def compact(key):
        prep.cancel('next')
        return original(key)
    rpc.compact=compact
    with pytest.raises(ContextPreparationError):prep.prepare('next')
    record,payload=stored(bridge)
    assert record['state']=='ended'
    assert payload['context_preparation']['state']=='cancelled'
    assert not payload['context_preparation'].get('chat_submitted')


def test_unknown_cancel_waits_for_readback_and_then_releases_without_sending(env):
    bridge,_,session=reserve(env);rpc=FakeRPC(session,TimeoutError());prep=preparation(bridge,rpc)
    with pytest.raises(ContextPreparationError):prep.prepare('next')
    prep.cancel('next');rpc.complete();expire(bridge)
    with pytest.raises(ContextPreparationError):prep.prepare('next')
    assert stored(bridge)[0]['state']=='ended'
    assert len([c for c in rpc.calls if c[0]=='compact'])==1


def test_identity_change_blocks_without_compressing_foreign_session(env):
    bridge,_,session=reserve(env);session['sessionId']='other'
    rpc=FakeRPC(session)
    with pytest.raises(ContextPreparationError,match='session_changed'):preparation(bridge,rpc).prepare('next')
    assert [c[0] for c in rpc.calls]==['describe']


def test_duplicate_workers_cannot_both_prepare_or_submit(env):
    bridge,_,session=reserve(env);rpc=FakeRPC(session);prep=preparation(bridge,rpc)
    def run(_):
        try:return prep.prepare('next')
        except ContextPreparationError:return None
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(run,range(2)))
    assert sum(r is not None for r in results)==1
    assert len([c for c in rpc.calls if c[0]=='compact'])==1


def test_session_rpc_targets_exact_gateway_and_omits_truncation(monkeypatch):
    calls=[]
    class Client:
        def __init__(self,**kw):calls.append(kw)
        def rpc(self,*a,**kw):calls.append((a,kw));return {'session':None}
        def close(self):pass
    monkeypatch.setattr('easel.conversation_compaction.GatewayClient',Client)
    rpc=SessionRPC('https://127.0.0.1:23456','fixture-token')
    rpc.describe('owned');rpc.compact('owned')
    assert calls[0]=={'url':'wss://127.0.0.1:23456','token':'fixture-token'}
    assert calls[2][0]==('sessions.compact',{'key':'owned','agentId':'main'})


@pytest.mark.parametrize('message,kind',[('has an active run',GatewayRPCError),('unknown method: sessions.compact',GatewayUnsupportedError)])
def test_ws_rpc_error_and_timeout_contract(message,kind):
    class Socket:
        def __init__(self):self.sent=[];self.timeouts=[]
        def send(self,value):self.sent.append(json.loads(value))
        def settimeout(self,value):self.timeouts.append(value)
        def recv(self):return json.dumps({'id':str(client._seq),'ok':False,'error':{'code':'INVALID_REQUEST','message':message}})
    client=GatewayClient();client.ws=Socket()
    with pytest.raises(kind):client.rpc('sessions.compact',{'key':'owned'},timeout=60)
    assert client.ws.timeouts[0]>12 and client.ws.timeouts[-1]==12


def test_checkpoint_alone_does_not_clear_official_pressure(env):
    bridge,_,session=reserve(env)
    session['latestCompactionCheckpoint']={'checkpointId':'already-compacted','createdAt':124}
    rpc=FakeRPC(session);preparation(bridge,rpc).prepare('next')
    assert any(c[0]=='compact' for c in rpc.calls)


def test_unknown_compaction_checkpoint_without_cleared_pressure_is_not_success(env):
    bridge,_,session=reserve(env);rpc=FakeRPC(session,TimeoutError());prep=preparation(bridge,rpc)
    with pytest.raises(ContextPreparationError):prep.prepare('next')
    rpc.session['compactionCheckpointCount'] += 1
    rpc.session['latestCompactionCheckpoint']={'checkpointId':'snapshot-only','createdAt':124}
    expire(bridge)
    with pytest.raises(ContextPreparationError,match='compaction_unresolved'):prep.prepare('next')
    assert len([c for c in rpc.calls if c[0]=='compact'])==1


@pytest.mark.parametrize('mutate',[lambda s:s.update(model='changed'),lambda s:s.update(hasActiveRun=True)])
def test_readback_does_not_infer_success_from_changed_model_or_active_run(env,mutate):
    bridge,_,session=reserve(env);rpc=FakeRPC(session,TimeoutError());prep=preparation(bridge,rpc)
    with pytest.raises(ContextPreparationError):prep.prepare('next')
    rpc.complete();mutate(rpc.session);expire(bridge)
    with pytest.raises(ContextPreparationError):prep.prepare('next')
    assert len([c for c in rpc.calls if c[0]=='compact'])==1


def test_revoke_during_compaction_cannot_dispatch(env):
    bridge,_,session=reserve(env);rpc=FakeRPC(session);original=rpc.compact
    def compact(key):
        bridge.conversations.revoke('ui')
        return original(key)
    rpc.compact=compact
    with pytest.raises(ContextPreparationError):preparation(bridge,rpc).prepare('next')
    assert not stored(bridge)[1]['context_preparation'].get('chat_submitted')
    assert 'message' not in stored(bridge)[1]


def test_gateway_handshake_uses_same_url_and_token(monkeypatch):
    import easel.gateway_questions as module
    recorded=[];signed=[]
    device={'device_id':'test-device','token':'old-device-token','public_key':'public-placeholder'}
    monkeypatch.setattr(module,'_load_device',lambda:device)
    monkeypatch.setattr(module,'_sign',lambda s:signed.append(s) or 'test-signature')
    class Socket:
        def __init__(self):self.responses=iter([{'event':'connect.challenge','payload':{'nonce':'nonce','ts':123}},{'id':'1','ok':True}])
        def recv(self):return json.dumps(next(self.responses))
        def send(self,s):recorded.append(json.loads(s))
        def settimeout(self,s):pass
        def close(self):pass
    socket=Socket();endpoints=[]
    monkeypatch.setattr('websocket.create_connection',lambda url,**kwargs:endpoints.append(url) or socket)
    client=GatewayClient(url='ws://127.0.0.1:12345',token='gateway-token')
    client.connect();client.close()
    assert endpoints==['ws://127.0.0.1:12345']
    assert recorded[0]['params']['auth']=={'token':'gateway-token'}
    assert '|gateway-token|nonce' in signed[0] and 'old-device-token' not in signed[0]


def test_web_pressure_order_replay_and_identity(env,tmp_path,monkeypatch):
    import web.conversation_api as api
    bridge,request,session=reserve(env);rpc=FakeRPC(session);events=[];sent=[]
    class Response:
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        def raise_for_status(self):pass
        async def aiter_lines(self):
            identity={'agent_id':'main','session_key':request['payload']['session_key'],'session_id':session['sessionId'],'run_id':'new-run'}
            bridge.claim(Claim(**identity,prompt=sent[0]['messages'][0]['content']))
            bridge.end(Identity(**identity))
            yield 'data: '+json.dumps({'choices':[{'delta':{'content':'完成讨论'},'finish_reason':'stop'}]})
            yield 'data: [DONE]'
    class HTTP:
        def __init__(self,*a,**kw):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*a):pass
        def stream(self,*a,**kw):
            assert [c[0] for c in rpc.calls]==['describe','compact','describe']
            sent.append(kw['json']);return Response()
    monkeypatch.setattr(api.httpx,'AsyncClient',HTTP)
    chat=api.VideoChat(lambda:bridge.service,lambda _:tmp_path/'events',lambda *a:None,
        gateway_url='http://fake',gateway_token='fake',context_preparer=lambda *a:preparation(bridge,rpc))
    async def run():
        await chat._deliver('ui','next',request,tmp_path/'events',event_sink=lambda k,v:events.append((k,v)))
        await chat._deliver('ui','next',request,tmp_path/'events',event_sink=lambda k,v:events.append((k,v)))
    asyncio.run(run())
    assert len(sent)==1
    assert stored(bridge)[0]['state']=='ended'
    assert sum(k=='done' for k,v in events)==1
    assert bridge.service.list_works()['items']==[]


def test_automatic_relay_recovers_preparation_without_retrying_compaction(env,tmp_path,monkeypatch):
    import web.conversation_api as api
    bridge,request,session=reserve(env);rpc=FakeRPC(session,TimeoutError());prep=preparation(bridge,rpc)
    with pytest.raises(ContextPreparationError):prep.prepare('next')
    rpc.complete();expire(bridge)
    sends=[]
    class HTTP:
        def __init__(self,*a,**kw):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*a):pass
        def stream(self,*a,**kw):sends.append(kw);raise OSError('synthetic network uncertainty')
    monkeypatch.setattr(api.httpx,'AsyncClient',HTTP)
    chat=api.VideoChat(lambda:bridge.service,lambda _:tmp_path/'events',lambda *a:None,
        gateway_url='http://fake',gateway_token='fake',context_preparer=lambda *a:preparation(bridge,rpc))
    async def run():
        assert await chat.process_results_once()
        await chat.tasks['ui']
        assert not await chat.process_results_once()
    asyncio.run(run())
    assert len(sends)==1
    assert len([c for c in rpc.calls if c[0]=='compact'])==1
    assert stored(bridge)[0]['state']=='unknown'


@pytest.mark.parametrize('origin',['handoff','task_result'])
def test_host_origin_survives_compression_and_rebuild(env,origin):
    bridge,_,session=reserve(env)
    with bridge.store.transaction() as conn:
        record,payload=stored(bridge)
        payload['origin']=origin
        if origin=='task_result':payload['result_event']={'script':'RESULT_SCRIPT_SENTINEL','state':'succeeded'}
        bridge._save(conn,'next',payload,record['state'])
    rpc=FakeRPC(session);result=preparation(bridge,rpc).prepare('next')
    assert [c[0] for c in rpc.calls]==['describe','compact','describe']
    assert 'HISTORY_SENTINEL' not in result['prompt']
    if origin=='handoff':
        assert result['prompt'].startswith('【宿主管线交接；不是新的用户回答或授权】')
        assert result['payload']['visible_proposals']==[]
        assert result['prompt'].count('CURRENT_SENTINEL')==1
    else:
        assert result['prompt'].startswith('【宿主任务结果事件，不是用户新指令或授权】')
        assert result['prompt'].count('RESULT_SCRIPT_SENTINEL')==1
        assert result['payload']['result_prompt']==result['prompt']


def test_web_stop_while_rpc_thread_finishes_never_posts(env,tmp_path,monkeypatch):
    import threading
    import web.conversation_api as api
    bridge,request,session=reserve(env);rpc=FakeRPC(session)
    entered=threading.Event();release=threading.Event();finished=threading.Event()
    original=rpc.compact
    def compact(key):
        entered.set()
        assert release.wait(5)
        return original(key)
    rpc.compact=compact
    prep=preparation(bridge,rpc);prepare=prep.prepare
    def waiting(turn_id):
        try:return prepare(turn_id)
        finally:finished.set()
    prep.prepare=waiting
    def forbidden(*args,**kwargs):raise AssertionError('cancelled preparation must not POST')
    monkeypatch.setattr(api.httpx,'AsyncClient',forbidden)
    chat=api.VideoChat(lambda:bridge.service,lambda _:tmp_path/'events',lambda *a:None,
        gateway_url='http://fake',gateway_token='fake',context_preparer=lambda *a:prep)
    async def run():
        task=asyncio.create_task(chat._deliver('ui','next',request,tmp_path/'events'))
        chat.tasks['ui']=task
        assert await asyncio.to_thread(entered.wait,5)
        assert chat.stop('ui')['stopped']
        await task
        release.set()
        assert await asyncio.to_thread(finished.wait,5)
    asyncio.run(run())
    record,payload=stored(bridge)
    assert record['state']=='ended'
    assert payload['context_preparation']['cancel_requested']
    assert not payload['context_preparation'].get('chat_submitted')
    assert bridge.service.list_works()['items']==[]


def empty_length(env):
    bridge,request,session=reserve(env)
    session.pop('contextBudgetStatus')
    with bridge.store.transaction() as conn:
        record=dict(conn.execute("SELECT * FROM conversation_turns WHERE id='history'").fetchone())
        payload=json.loads(record['payload_json'])
        payload.update(delivery_state='interrupted',answer='',
            context_preparation={'state':'ready','chat_submitted':True},
            model_diagnostic={'stop_reason':'length','text_chars':0,'tool_calls':0,
                'provider':session['modelProvider'],'model':session['model']})
        bridge._save(conn,'history',payload,'ended')
        before=dict(conn.execute("SELECT * FROM conversation_turns WHERE id='history'").fetchone())
    return bridge,request,session,before


def test_known_empty_length_compacts_before_new_turn_without_replaying_old_one(env):
    bridge,request,session,before=empty_length(env)
    rpc=FakeRPC(session);result=preparation(bridge,rpc).prepare('next')
    assert [c[0] for c in rpc.calls]==['describe','compact','describe']
    assert result['payload']['message']=='CURRENT_SENTINEL'
    assert result['payload']['context_preparation']['evidence']['source']=='known-empty-length'
    with bridge.store.connection() as conn:
        assert dict(conn.execute("SELECT * FROM conversation_turns WHERE id='history'").fetchone())==before
    assert stored(bridge)[0]['state']=='reserved'
    assert not result['payload']['context_preparation'].get('chat_submitted')


@pytest.mark.parametrize('change',['partial_text','tool_call','unknown','not_submitted','changed_model','already_compacted','failed_after_compact'])
def test_empty_length_does_not_guess_pressure_or_repeat_compression(env,change):
    bridge,_,session,_=empty_length(env)
    with bridge.store.transaction() as conn:
        row=conn.execute("SELECT * FROM conversation_turns WHERE id='history'").fetchone()
        payload=json.loads(row['payload_json']);state=row['state']
        if change=='partial_text':payload['model_diagnostic']['text_chars']=1
        if change=='tool_call':payload['model_diagnostic']['tool_calls']=1
        if change=='unknown':state='unknown'
        if change=='not_submitted':payload['context_preparation']['chat_submitted']=False
        if change=='changed_model':session['model']='other'
        if change=='already_compacted':session['latestCompactionCheckpoint']={'createdAt':time.time()*1000+1000}
        if change=='failed_after_compact':payload['context_preparation']['evidence']={'source':'known-empty-length'}
        bridge._save(conn,'history',payload,state)
        segment=dict(conn.execute('SELECT * FROM conversation_segments WHERE id=?',(row['segment_id'],)).fetchone())
    assert preparation(bridge,FakeRPC(session))._empty_length_evidence('next',segment,session) is None


def test_empty_length_uncertain_compaction_is_not_reissued(env):
    bridge,_,session,_=empty_length(env)
    rpc=FakeRPC(session,outcome={'ok':True,'compacted':False,'result':{'details':{'pending':True}}})
    with pytest.raises(ContextPreparationError):preparation(bridge,rpc).prepare('next')
    expire(bridge)
    with pytest.raises(ContextPreparationError,match='compaction_unresolved'):
        preparation(bridge,rpc).prepare('next')
    assert len([c for c in rpc.calls if c[0]=='compact'])==1
