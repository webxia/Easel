"""Real worker/ledger and native-turn lifecycle with fake model transport only."""
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from tests.production.test_conversation import env, entry, turn, tool, raises
from tests.production.test_conversation_pipeline import seed, pipe
from tests.production.test_planning_runtime import Transport
from tests.production.test_store import insert_artifact
from easel.conversation_bridge import PersistentWorkToolBridge
from easel.conversation_results import ConversationResults
from easel.production.operations import OperationService
from easel.production.planning import PlanningTasks
from easel.production.worker import Worker, TaskResult
from easel.production.errors import ProductionError
from easel.production.service import encode
from easel.work_bridge import Claim, Identity


def planning(env, *, fail=False):
    s,c=env;channel=seed(env)
    seg=entry(c,profile_ref='one',channel_id=channel,director_revision='v4',director_trial=True)
    b,i,_=turn(s,c,seg,'请制作一个视频')
    work=pipe(b,i,'draft',user_quote='请制作一个视频',values={'title':'任务结果','input_text':'技术服务人'})['work_id']
    p=pipe(b,i,'offer',action='plan',values={'request':'完整方案'})
    b.end(Identity(**i))
    b,i,_=turn(s,c,seg,'同意整理方案',id='plan-yes')
    result=pipe(b,i,'answer',proposal_id=p['proposal_id'],hash=p['hash'],user_quote='同意整理方案')
    b.end(Identity(**i))
    answer={'title':'任务结果','summary':'方案摘要','script':'技术服务人。','scenes':[{'id':'s1','purpose':'解释','visual':'科技画面','narration':'技术服务人。','duration_seconds':3,'required_input_ids':[]}],'settings':{'duration_seconds':3,'aspect_ratio':'16:9','audio_mode':'silent'}}
    transport=Transport(answer)
    if fail:
        from easel.production.model_tasks import ModelTaskError
        async def timeout(*args):
            raise ModelTaskError('provider_timeout','模型请求超时；提交结果尚未确定，禁止自动重发')
        transport.complete=timeout
    handler=PlanningTasks(s,OperationService(s.store),transport,{'provider':'direct-api','model':'fixture-model','mode':'structured'},'fixture')
    worker=Worker(s.store,{'plan':handler.plan})
    return s,c,seg,work,result,worker


def claim_result(s,result):
    b=PersistentWorkToolBridge(s)
    identity={'agent_id':'easel-video','session_key':result['payload']['session_key'],'session_id':'native-'+result['payload']['session_key'].split(':')[-1], 'run_id':'native-'+result['turn_id']}
    b.claim(Claim(**identity,prompt=result['prompt']))
    return b,identity


def finish_result(s,result,text='助手实际生成的方案解释与下一步问题。'):
    b,i=claim_result(s,result)
    b.record_result_text(result['turn_id'],text)
    b.end(Identity(**i));b.delivery(result['turn_id'],'unknown',text)


def test_plan_result_reenters_same_assistant_once_with_complete_script(env):
    s,c,seg,work,request,worker=planning(env)
    relay=ConversationResults(PersistentWorkToolBridge(s))
    assert relay.reserve_next() is None
    asyncio.run(worker.run_once())
    result=relay.reserve_next()
    assert result and result['payload']['session_key']=='agent:easel-video:'+seg
    assert result['payload']['message'] is None
    assert '技术服务人。' in result['prompt'] and '科技画面' in result['prompt']
    assert result['payload']['result_event']['run_state']=='succeeded'
    assert relay.reserve_next() is None  # dispatch claim is durable before network
    finish_result(s,result)
    assert ConversationResults(PersistentWorkToolBridge(s)).reserve_next() is None
    view=c.view('ui');assert len(view['result_messages'])==1
    assert view['result_messages'][0]['content'].startswith('助手实际生成')
    assert view['result_messages'][0]['resultState']=='ended'
    assert all(m['role']=='assistant' for m in view['result_messages'])
    with s.store.connection() as conn:
        assert result['turn_id'] not in [x['ref'] for x in c.context(conn,c.segment(conn,'ui'))['sources']]
        raises('invalid_source',lambda:c.source_refs(conn,c.segment(conn,'ui'),[result['turn_id']]))
    assert len(s.snapshot(work)['runs'])==1


def test_timeout_event_explains_failure_and_cannot_be_authorization_or_retry(env):
    s,c,seg,work,_,worker=planning(env,fail=True)
    asyncio.run(worker.run_once())
    relay=ConversationResults(PersistentWorkToolBridge(s));result=relay.reserve_next()
    assert result['payload']['result_event']['unknown_operations']
    b,i=claim_result(s,result)
    before=s.snapshot(work)
    for args in [dict(mode='answer',user_quote='同意',proposal_id='fake',hash='fake'),dict(mode='draft',user_quote='同意',values={}),dict(mode='offer',action='resume',values={}),dict(mode='offer',action='replan_after_unknown',values={}),dict(mode='offer',action='grant',values={'purpose':'planning'})]:
        raises('result_event_read_only',lambda:pipe(b,i,**args))
    raises('result_event_read_only',lambda:tool(b,i,'easel_work_update_brief',{'entries':[{'kind':'suggestion','text':'x','source_refs':['turn']}]}))
    assert s.snapshot(work)==before
    b.end(Identity(**i));b.delivery(result['turn_id'],'unknown','本次整理方案未取得结果。当前模型接口没有查询能力，不能自动重发。需要先核对服务再由你决定。')
    # A real subsequent user turn can read the failed task and continue talking.
    b,i,_=turn(s,c,seg,'为什么超时，先解释不要重做',id='follow-up')
    pending=pipe(b,i,'pending')
    assert any(t['state']=='needs_decision' for t in pending['work']['tasks'])
    assert len(pending['work']['runs'])==1


def confirm_production(env):
    s,c,seg,work,_,worker=planning(env);asyncio.run(worker.run_once())
    result=ConversationResults(PersistentWorkToolBridge(s)).reserve_next();b,i=claim_result(s,result)
    plan=s.snapshot(work)['plans'][0]
    p=pipe(b,i,'offer',action='confirm',values={'plan_revision':plan['revision'],'plan_hash':plan['plan_hash'],'services':[],'allow_ai':False,'image_limit':0,'video_limit':0},summary='已展示完整方案，确认后制作')
    raises('result_event_read_only',lambda:pipe(b,i,'answer',proposal_id=p['proposal_id'],hash=p['hash'],user_quote='同意'))
    b.end(Identity(**i));b.delivery(result['turn_id'],'unknown','完整方案和所需服务已展示。是否确认制作？')
    b,i,_=turn(s,c,seg,'同意制作这个方案',id='make-yes')
    r=pipe(b,i,'answer',proposal_id=p['proposal_id'],hash=p['hash'],user_quote='同意制作这个方案')
    assert r['run_id']!=result['payload']['result_event']['run_id']
    assert len(s.snapshot(work)['runs'])==2
    b.end(Identity(**i))
    return s,c,work


def test_result_turn_can_only_offer_confirmation_then_real_user_confirms(env):
    confirm_production(env)


@pytest.mark.parametrize('failure',[False,True])
def test_edit_render_quality_terminal_result_and_edit_failure(env,failure):
    s,c,work=confirm_production(env)
    async def supply(ctx):return TaskResult(next_kind='edit')
    async def edit(ctx):
        if failure:raise ProductionError('edit_fixture_failed','本次剪辑无法取得可用素材',requires_decision=True)
        return TaskResult(next_kind='render')
    async def render(ctx):return TaskResult(next_kind='quality')
    async def quality(ctx):
        with ctx.transaction() as conn:
            insert_artifact(conn,work,'fixture-output',run_id=ctx.run_id,kind='output',media_type='video/mp4',output_revision=1,quality_state='passed',displayable=1)
        return TaskResult(work_state='reviewable')
    worker=Worker(s.store,{'supply':supply,'edit':edit,'render':render,'quality':quality})
    asyncio.run(worker.run_once())
    result=ConversationResults(PersistentWorkToolBridge(s)).reserve_next()
    event=result['payload']['result_event']
    if failure:
        assert event['run_state']=='needs_decision'
        assert any('edit_fixture_failed' in (t['error_json'] or '') for t in event['tasks'])
        assert event['outputs']==[]
    else:
        assert event['run_state']=='succeeded'
        assert [t['kind'] for t in event['tasks']]==['supply','edit','render','quality']
        assert event['outputs'][0]['playback_url']=='/api/production/artifacts/fixture-output/content'
    finish_result(s,result,'剪辑结果由助手解释；请告诉我审阅意见。')
    assert len(c.view('ui')['result_messages'])==2


def test_user_turn_blocks_result_delivery_and_concurrent_claim_is_once(env):
    s,c,seg,work,_,worker=planning(env);asyncio.run(worker.run_once())
    b,i,_=turn(s,c,seg,'我有个问题',id='question')
    assert ConversationResults(PersistentWorkToolBridge(s)).reserve_next() is None
    b.end(Identity(**i))
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda _:ConversationResults(PersistentWorkToolBridge(s)).reserve_next(),range(4)))
    assert sum(r is not None for r in results)==1


def test_no_retroactive_paid_reply_for_legacy_receipt_or_revoked_segment(env):
    s,c,seg,work,_,worker=planning(env);asyncio.run(worker.run_once())
    with s.store.transaction() as conn:
        for p in conn.execute("SELECT id,receipt_json FROM conversation_proposals WHERE state='applied'").fetchall():
            receipt=json.loads(p['receipt_json']);receipt.pop('_result_delivery',None)
            conn.execute('UPDATE conversation_proposals SET receipt_json=? WHERE id=?',(encode(receipt),p['id']))
    assert ConversationResults(PersistentWorkToolBridge(s)).reserve_next() is None
    c.revoke('ui')
    assert ConversationResults(PersistentWorkToolBridge(s)).reserve_next() is None


def test_delivery_failure_never_redispatches_assistant_or_production(env,tmp_path,monkeypatch):
    import web.conversation_api as api
    s,c,seg,work,_,worker=planning(env);asyncio.run(worker.run_once())
    calls=[]
    class Client:
        def __init__(self,*a,**kw):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*a):pass
        def stream(self,*a,**kw):calls.append(1);raise RuntimeError('fake disconnected')
    monkeypatch.setattr(api.httpx,'AsyncClient',Client)
    chat=api.VideoChat(lambda:s,lambda t:tmp_path/(t+'.jsonl'),lambda *a:None,gateway_url='http://fake',gateway_token='fake',preflight=lambda *a:None)
    async def run():
        assert await chat.process_results_once()
        await chat.tasks['ui']
        assert not await chat.process_results_once()
    asyncio.run(run())
    assert len(calls)==1
    assert c.view('ui')['result_messages'][0]['deliveryError']
    assert len(s.snapshot(work)['runs'])==1


def test_deleting_chat_scrubs_result_prompt_and_late_text(env):
    s,c,seg,work,_,worker=planning(env);asyncio.run(worker.run_once())
    result=ConversationResults(PersistentWorkToolBridge(s)).reserve_next()
    b,i=claim_result(s,result)
    c.revoke('ui');b.record_result_text(result['turn_id'],'不应写回的晚到正文')
    b.end(Identity(**i))
    with s.store.connection() as conn:
        payload=json.loads(conn.execute('SELECT payload_json FROM conversation_turns WHERE id=?',(result['turn_id'],)).fetchone()[0])
        assert 'result_prompt' not in payload and 'answer' not in payload
        assert 'tasks' not in payload['result_event'] and 'outputs' not in payload['result_event']


def test_explicit_resume_same_run_delivers_new_outcome_once(env):
    s,c,seg,work,_,planning_worker=planning(env)
    async def pause(ctx):
        return TaskResult(state='needs_decision',error=ProductionError('fixture_pause','请决定是否继续原任务',requires_decision=True))
    asyncio.run(Worker(s.store,{'plan':pause}).run_once())
    relay=ConversationResults(PersistentWorkToolBridge(s));first=relay.reserve_next();finish_result(s,first,'本次已暂停，是否继续？')
    task=s.snapshot(work)['tasks'][0]
    b,i,_=turn(s,c,seg,'继续原任务',id='resume-offer')
    p=pipe(b,i,'offer',action='resume',values={'decision_id':task['id']},summary='继续原任务，不新建运行')
    b.end(Identity(**i))
    b,i,_=turn(s,c,seg,'同意继续',id='resume-answer')
    pipe(b,i,'answer',proposal_id=p['proposal_id'],hash=p['hash'],user_quote='同意继续');b.end(Identity(**i))
    assert relay.reserve_next() is None
    asyncio.run(planning_worker.run_once())
    second=relay.reserve_next();assert second['turn_id']!=first['turn_id']
    finish_result(s,second,'原任务已完成，完整方案如下。')
    assert relay.reserve_next() is None
    assert len(c.view('ui')['result_messages'])==2
    assert len(s.snapshot(work)['runs'])==1
