"""Host continuation component tests: no Gateway, model or production calls."""
import json
import pytest
from tests.production.test_conversation import env, entry, turn, tool, raises
from tests.production.test_conversation_pipeline import seed, pipe
from easel.work_bridge import Identity, Claim
from easel.conversation_bridge import PersistentWorkToolBridge


@pytest.mark.parametrize('quote',['','画像说明的一部分。仅讨论','模型改写的文字'])
def test_entry_uses_host_input_not_model_repetition(env,quote):
    from web.conversation_api import NaturalEntry,EntryCall
    s,c=env;gate=NaturalEntry()
    gate.reserve('ui','unused','web-turn','host-prompt','仅讨论，不创建作品','one')
    identity=dict(agent_id='main',session_key='agent:main:ui',session_id='native',run_id='run')
    gate.call(s,EntryCall(**identity,mode='claim',prompt='host-prompt'))
    result=gate.call(s,EntryCall(**identity,mode='enter',prompt='',kind='new_work',user_quote=quote,tool_call_id='call'))
    assert result['pending']['context']['sources'][0]['text']=='仅讨论，不创建作品'
    assert not s.list_works()['items']


def test_binding_continuation_is_once_and_cannot_authorize(env):
    s,c=env; channel=seed(env);seg=entry(c,profile_ref='one')
    b,i,_=turn(s,c,seg,'用频道甲和导演甲，讨论学习这个题目')
    pipe(b,i,'bind',user_quote='用频道甲和导演甲',values={'channel_id':channel,'director_revision':'v4','director_trial':True})
    assert b.continue_handoff('ui','turn') is None
    b.end(Identity(**i))
    r=b.continue_handoff('ui','turn')
    assert r['payload']['origin']=='handoff'
    assert r['payload']['message']=='用频道甲和导演甲，讨论学习这个题目'
    assert b.continue_handoff('ui','turn') is None
    ident=dict(agent_id='main',session_key=r['payload']['session_key'],session_id='native-next',run_id='run-next')
    b.claim(Claim(**ident,prompt=r['prompt']))
    raises('handoff_confirmation_required',lambda:pipe(b,ident,'answer',dismiss=False,proposal_id='a'*32,hash='b'*64,user_quote='用频道甲和导演甲'))
    assert not s.list_works()['items']


def test_no_handoff_for_plain_or_unknown_turn(env):
    s,c=env;seg=entry(c,profile_ref='one');b,i,_=turn(s,c,seg,'先讨论')
    assert b.continue_handoff('ui','turn') is None
    b.delivery('turn','unknown')
    assert b.continue_handoff('ui','turn') is None


def test_material_summary_does_not_call_network_failure_no_results():
    from easel.conversation_results import material_search_summary
    value=material_search_summary([
        {'scene_id':'s1','candidate_count':0,'sources':['stock'],'failures':[{'source':'stock','code':'network_timeout'}]},
        {'scene_id':'s2','candidate_count':0,'sources':['stock'],'failures':[{'source':'stock','code':'no_results'}]},
        {'role':'music','candidate_count':0,'failures':[{'code':'download_failed'}]},
    ])
    assert value[0]['findings']==['search_incomplete']
    assert value[1]['findings']==['no_results']
    assert value[2]['findings']==['download_failed']


def test_natural_entry_requires_authenticated_end(env):
    from web.conversation_api import NaturalEntry,EntryCall
    s,c=env;gate=NaturalEntry();b=PersistentWorkToolBridge(s)
    gate.reserve('ui','unused','web-turn','prompt','讨论视频','one')
    identity=dict(agent_id='main',session_key='agent:main:ui',session_id='native',run_id='run')
    gate.call(s,EntryCall(**identity,mode='claim',prompt='prompt'))
    result=gate.call(s,EntryCall(**identity,mode='enter',prompt='',kind='new_work',user_quote='讨论视频',tool_call_id='call'))
    source=result['source_turn_id']
    assert b.continue_handoff('ui',source) is None
    gate.call(s,EntryCall(**identity,mode='end',prompt=''))
    child=b.continue_handoff('ui',source)
    assert child and child['payload']['origin']=='handoff'
    assert b.continue_handoff('ui',source) is None
    assert s.list_works()['items']==[]


def test_web_binding_continues_before_single_done(env,tmp_path,monkeypatch):
    import asyncio
    import web.conversation_api as api
    from tests.production.test_context_preparation import NoPressureRPC
    monkeypatch.setattr('easel.conversation_compaction.SessionRPC',NoPressureRPC)
    s,c=env;channel=seed(env);seg=entry(c,profile_ref='one')
    b=PersistentWorkToolBridge(s)
    initial=b.reserve(ui_session='ui',turn_id='first',segment_id=seg,message='用频道甲和导演甲讨论视频',attachments=[])
    calls=[];events=[];saved=[]
    class Response:
        def __init__(self,body):self.body=body
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        def raise_for_status(self):pass
        async def aiter_lines(self):
            n=len(calls);view=c.view('ui')
            ident=dict(agent_id='main',session_key='agent:main:easel-pipeline:'+view['segment_id'],session_id='native-'+view['segment_id'],run_id='native-run-'+str(n))
            b.claim(Claim(**ident,prompt=self.body['messages'][0]['content']))
            if n==1:
                yield 'data: '+json.dumps({'choices':[{'delta':{'content':'切换前的重复讨论'}}]})
                pipe(b,ident,'bind',user_quote='用频道甲和导演甲',values={'channel_id':channel,'director_revision':'v4','director_trial':True})
            else:
                assert not any(k=='done' for k,_ in events)
                assert pipe(b,ident,'pending')['missing_choices']==[]
            b.end(Identity(**ident))
            yield 'data: '+json.dumps({'choices':[{'delta':{'content':'开始讨论选题' if n==2 else '正在衔接'}}]})
            yield 'data: [DONE]'
    class Client:
        def __init__(self,*a,**k):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*a):pass
        def stream(self,*a,**k):calls.append(k['json']);return Response(k['json'])
    monkeypatch.setattr(api.httpx,'AsyncClient',Client)
    chat=api.VideoChat(lambda:s,lambda _:tmp_path/'events',lambda *a:saved.append(a),gateway_url='http://fixture',gateway_token='fixture')
    asyncio.run(chat._deliver('ui','first',initial,tmp_path/'events',event_sink=lambda k,v:events.append((k,v))))
    assert ''.join(v for k,v in events if k=='token')=='开始讨论选题'
    assert len(calls)==2
    assert [k for k,_ in events].count('done')==1
    assert events[-1][0]=='done'
    assert saved[-1][2]=='开始讨论选题' and saved[-1][3]['turn_id']=='first'
    assert not s.list_works()['items']


def test_concurrent_handoff_consumption_is_once(env):
    from concurrent.futures import ThreadPoolExecutor
    s,c=env;channel=seed(env);seg=entry(c,profile_ref='one')
    b,i,_=turn(s,c,seg,'用频道甲和导演甲')
    pipe(b,i,'bind',user_quote='用频道甲和导演甲',values={'channel_id':channel,'director_revision':'v4','director_trial':True})
    b.end(Identity(**i))
    with ThreadPoolExecutor(2) as pool:
        results=list(pool.map(lambda _:b.continue_handoff('ui','turn'),range(2)))
    assert sum(r is not None for r in results)==1


@pytest.mark.parametrize('stream_error',[False,True])
@pytest.mark.parametrize('native_end',[False,True])
def test_committed_binding_interrupts_obsolete_run_without_prose(env,tmp_path,monkeypatch,stream_error,native_end):
    """An agent that keeps probing old tools cannot hold handoff forever."""
    import asyncio
    import threading
    import web.conversation_api as api
    from tests.production.test_context_preparation import NoPressureRPC
    monkeypatch.setattr('easel.conversation_compaction.SessionRPC',NoPressureRPC)
    s,c=env;channel=seed(env);seg=entry(c,profile_ref='one')
    b=PersistentWorkToolBridge(s)
    initial=b.reserve(ui_session='ui',turn_id='first',segment_id=seg,
        message='用频道甲和导演甲讨论视频',attachments=[])
    calls=[];events=[];saved=[];interruptions=[];stopped=threading.Event()
    identity={}
    def interrupt(url,token,payload):
        assert payload['run_id']==identity['run_id']
        assert payload['native_session_id']==identity['session_id']
        assert payload['pipeline_entry']['channel_id']==channel
        # RPC success itself is not an ended receipt.
        assert b.continue_handoff('ui','first') is None
        interruptions.append(payload['run_id'])
        if native_end:b.end(Identity(**identity))  # Simulated authenticated native end hook.
        stopped.set()
    class Response:
        def __init__(self,body):self.body=body
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        def raise_for_status(self):pass
        async def aiter_lines(self):
            n=len(calls);view=c.view('ui')
            ident=dict(agent_id='main',session_key='agent:main:easel-pipeline:'+view['segment_id'],
                session_id='native-'+view['segment_id'],run_id='native-run-'+str(n))
            b.claim(Claim(**ident,prompt=self.body['messages'][0]['content']))
            if n==1:
                identity.update(ident)
                pipe(b,ident,'bind',user_quote='用频道甲和导演甲',values={
                    'channel_id':channel,'director_revision':'v4','director_trial':True})
                # No assistant prose or voluntary end. Wait for host control.
                await asyncio.wait_for(asyncio.to_thread(stopped.wait),2)
                if stream_error:
                    yield 'data: '+json.dumps({'error':{'type':'aborted'}})
                else:yield 'data: [DONE]'
            else:
                assert pipe(b,ident,'pending')['missing_choices']==[]
                b.end(Identity(**ident))
                yield 'data: '+json.dumps({'choices':[{'delta':{'content':'第五条规划可以继续'}}]})
                yield 'data: [DONE]'
    class Client:
        def __init__(self,*a,**k):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*a):pass
        def stream(self,*a,**k):calls.append(k['json']);return Response(k['json'])
    monkeypatch.setattr(api.httpx,'AsyncClient',Client)
    chat=api.VideoChat(lambda:s,lambda _:tmp_path/'events',lambda *a:saved.append(a),
        gateway_url='http://fixture',gateway_token='fixture',handoff_interrupter=interrupt)
    asyncio.run(chat._deliver('ui','first',initial,tmp_path/'events',event_sink=lambda k,v:events.append((k,v))))
    if not native_end:
        assert len(calls)==1 and interruptions==['native-run-1']
        assert b.continue_handoff('ui','first') is None
        assert not any(k=='done' for k,_ in events)
        assert any(k=='error' for k,_ in events)
        with b.store.connection() as conn:
            assert conn.execute("SELECT state FROM conversation_turns WHERE id='first'").fetchone()[0]=='unknown'
        assert not s.list_works()['items']
        return
    assert len(calls)==2 and interruptions==['native-run-1']
    assert ''.join(v for k,v in events if k=='token')=='第五条规划可以继续'
    assert [k for k,_ in events].count('done')==1
    assert not any(k=='error' for k,_ in events)
    assert saved[-1][3]['turn_id']=='first'
    assert not s.list_works()['items']


def test_handoff_abort_pins_native_session_and_run(monkeypatch):
    import web.conversation_api as api
    calls=[]
    class RPC:
        def __init__(self,*args):self.client=self
        def describe(self,key):return {'sessionId':'native'}
        def rpc(self,method,args):calls.append((method,args));return {'ok':True}
        def close(self):calls.append('closed')
    monkeypatch.setattr(api,'SessionRPC',RPC)
    payload={'session_key':'agent:main:easel-pipeline:one','native_session_id':'native','run_id':'run'}
    api.interrupt_committed_handoff('fixture','secret',payload)
    assert calls[0]==('chat.abort',{'sessionKey':payload['session_key'],'runId':'run','agentId':'main','preserveSideRuns':True})
    assert calls[-1]=='closed'
    calls.clear()
    with pytest.raises(ValueError,match='session_changed'):
        api.interrupt_committed_handoff('fixture','secret',{**payload,'native_session_id':'wrong'})
    assert calls==['closed']
