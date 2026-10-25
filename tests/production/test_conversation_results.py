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
    result=pipe(b,i,'answer',dismiss=False,proposal_id=p['proposal_id'],hash=p['hash'],user_quote='同意整理方案')
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
    identity={'agent_id':'main','session_key':result['payload']['session_key'],'session_id':'native-'+result['payload']['session_key'].split(':')[-1], 'run_id':'native-'+result['turn_id']}
    b.claim(Claim(**identity,prompt=result['prompt']))
    return b,identity


def finish_result(s,result,text='助手实际生成的方案解释与下一步问题。'):
    if result.get('local_delivery'):
        assert result['answer'] and result['payload']['delivery_state']=='delivered'
        return
    b,i=claim_result(s,result)
    b.record_result_text(result['turn_id'],text)
    b.end(Identity(**i));b.delivery(result['turn_id'],'unknown',text)


def test_plan_result_reenters_same_assistant_once_with_complete_script(env):
    s,c,seg,work,request,worker=planning(env)
    relay=ConversationResults(PersistentWorkToolBridge(s))
    assert relay.reserve_next() is None
    asyncio.run(worker.run_once())
    result=relay.reserve_next()
    assert result and result['payload']['session_key']=='agent:main:easel-pipeline:'+seg
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
    before=s.snapshot(work)
    assert result['local_delivery'] and '不能自动重发' in result['answer']
    b=PersistentWorkToolBridge(s)
    identity={'agent_id':'main','session_key':result['payload']['session_key'],
              'session_id':result['payload']['native_session_id'],'run_id':'unauthorized-native-retry'}
    raises('binding_mismatch',lambda:b.claim(Claim(**identity,prompt='')))
    assert relay.reserve_next() is None
    assert s.snapshot(work)==before
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
    raises('result_event_read_only',lambda:pipe(b,i,'answer',dismiss=False,proposal_id=p['proposal_id'],hash=p['hash'],user_quote='同意'))
    b.end(Identity(**i));b.delivery(result['turn_id'],'unknown','完整方案和所需服务已展示。是否确认制作？')
    b,i,_=turn(s,c,seg,'同意制作这个方案',id='make-yes')
    r=pipe(b,i,'answer',dismiss=False,proposal_id=p['proposal_id'],hash=p['hash'],user_quote='同意制作这个方案')
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
    from tests.production.test_context_preparation import NoPressureRPC
    monkeypatch.setattr('easel.conversation_compaction.SessionRPC',NoPressureRPC)
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
    pipe(b,i,'answer',dismiss=False,proposal_id=p['proposal_id'],hash=p['hash'],user_quote='同意继续');b.end(Identity(**i))
    assert relay.reserve_next() is None
    asyncio.run(planning_worker.run_once())
    second=relay.reserve_next();assert second['turn_id']!=first['turn_id']
    finish_result(s,second,'原任务已完成，完整方案如下。')
    assert relay.reserve_next() is None
    assert len(c.view('ui')['result_messages'])==2
    assert len(s.snapshot(work)['runs'])==1


def test_result_reports_all_known_material_gaps_and_unreviewed_candidates(env):
    from tests.production.test_preoutput_replan import stopped
    from easel.production.service import row
    s,w,r=stopped(env)
    with s.store.transaction() as conn:
        for payload in [{'scene_id':'s1','kind':'video','candidate_count':0,'failures':[{'source':'pexels','code':'network_timeout'}]},
                        {'scene_id':'s2','kind':'image','candidate_count':0,'failures':[{'source':'pixabay','code':'no_results'}]},
                        {'kind':'audio','role':'music','candidate_count':0,'failures':[{'source':'wikimedia_bgm','code':'http_rate_limited'}]}]:
            s._event(conn,w,'material_search_completed',payload,run_id=r)
        insert_artifact(conn,w,kind='video',run_id=r)
    with s.store.connection() as conn:
        result=ConversationResults.event_result(conn,s.snapshot(w),row(conn,'runs',r),{'seq':1})
    summary=result['material_summary']
    assert len(summary['known_gaps'])==3
    assert summary['candidate_is_approved'] is False
    assert summary['retained_candidates']==[{'kind':'video','quality_state':'unchecked'}]
    assert result['current_plan']['confirmed_at']


def test_existing_activity_distinguishes_execution_and_delivery(env):
    s,c,_,w,result,_=planning(env)
    relay=ConversationResults(PersistentWorkToolBridge(s))
    assert relay.activity('plan-yes')=='正在整理完整方案'
    with s.store.transaction() as conn:conn.execute("UPDATE runs SET state='needs_decision' WHERE id=?",(result['run_id'],))
    assert relay.activity('plan-yes')=='执行已停止，正在整理结果'


def test_failed_render_is_returned_without_model_and_status_survives_reply_loss(env,tmp_path,monkeypatch):
    import web.conversation_api as api
    s,c,work=confirm_production(env)
    async def supply(ctx):return TaskResult(next_kind='render')
    async def render(ctx):return TaskResult(state='needs_decision',error=ProductionError(
        'render_failed','caption exceeds the frame; adjust its explicit size or position',requires_decision=True))
    asyncio.run(Worker(s.store,{'supply':supply,'render':render}).run_once())
    before=s.snapshot(work)
    def forbidden(*a,**kw):raise AssertionError('failure notification must not call a model/gateway')
    monkeypatch.setattr(api.httpx,'AsyncClient',forbidden)
    saved=[]
    chat=api.VideoChat(lambda:s,lambda t:tmp_path/(t+'.jsonl'),lambda *a:saved.append(a),
                       gateway_url='http://fake',gateway_token='fake',preflight=forbidden)
    assert asyncio.run(chat.process_results_once())
    assert not asyncio.run(chat.process_results_once())
    assert len(saved)==1 and not chat.tasks
    view=c.view('ui')
    assert '文字超出边界' in view['production_status']['message']
    assert '素材准备' in view['production_status']['message']
    assert view['production_status']['title']=='制作已暂停'
    assert '素材准备' in view['production_status']['completed_steps']
    assert view['production_status']['issues'][0]['stage']=='渲染'
    reply=view['result_messages'][-1]
    assert reply['resultState']=='ended' and '制作已暂停' in reply['content']
    # Mimic a previously interrupted explanation: authoritative status still renders.
    with s.store.transaction() as conn:
        row=conn.execute('SELECT payload_json FROM conversation_turns WHERE id=?',(reply['serverTurnId'],)).fetchone()
        payload=json.loads(row[0]);payload.update(answer='',delivery_error='interrupted')
        conn.execute('UPDATE conversation_turns SET payload_json=? WHERE id=?',(encode(payload),reply['serverTurnId']))
    assert c.view('ui')['production_status']==view['production_status']
    # Older persisted notifications are re-projected from their own event, not
    # copied verbatim or rebuilt from a later production run.
    with s.store.transaction() as conn:
        payload['answer']='旧提示：成片检查已通过，revise失败'
        conn.execute('UPDATE conversation_turns SET payload_json=? WHERE id=?',(encode(payload),reply['serverTurnId']))
    refreshed=c.view('ui')['result_messages'][-1]
    assert '文字超出边界' in refreshed['content'] and '检查已通过' not in refreshed['content']
    assert refreshed['serverTurnId']==reply['serverTurnId']
    assert s.snapshot(work)==before


def test_explicit_resume_uses_existing_run_without_another_confirmation(env):
    s,c,work=confirm_production(env)
    async def supply(ctx):return TaskResult(next_kind='render')
    async def render(ctx):return TaskResult(state='needs_decision',error=ProductionError(
        'render_failed','local renderer unavailable',requires_decision=True))
    asyncio.run(Worker(s.store,{'supply':supply,'render':render}).run_once())
    snap=s.snapshot(work);seg=c.view('ui')['segment_id']
    task=next(t for t in snap['tasks'] if t['kind']=='render')
    b,i,_=turn(s,c,seg,'继续制作，保留已有素材和配音',id='resume-human')
    pending=pipe(b,i,'pending')
    assert any(choice['action']=='resume' for item in pending['blockers'] for choice in item['choices'])
    raises('resume_required',lambda:pipe(b,i,'offer',action='plan',values={'request':'继续制作'}))
    raises('invalid_source',lambda:pipe(b,i,'offer',action='resume',values={'decision_id':task['id']},user_quote='伪造同意'))
    args={'action':'resume','values':{'decision_id':task['id']},'user_quote':'继续制作，保留已有素材和配音'}
    result=pipe(b,i,'offer',**args)
    assert result['resumed'] and not result['requires_user_confirmation']
    assert pipe(b,i,'offer',**args)==result
    after=s.snapshot(work)
    assert after['active_run_id']==snap['active_run_id']
    assert len(after['runs'])==len(snap['runs'])
    assert after['artifacts']==snap['artifacts']
    assert next(t for t in after['tasks'] if t['id']==task['id'])['state']=='pending'
    assert not [p for p in c.view('ui')['proposals'] if p['state']=='proposed']


def test_interrupted_failure_restores_original_message_before_next_user(env):
    s,c,work=confirm_production(env)
    async def supply(ctx):return TaskResult(state='needs_decision',error=ProductionError(
        'material_gap','已有素材不足',requires_decision=True))
    asyncio.run(Worker(s.store,{'supply':supply}).run_once())
    result=ConversationResults(PersistentWorkToolBridge(s)).reserve_next()
    with s.store.transaction() as conn:
        r=conn.execute('SELECT payload_json FROM conversation_turns WHERE id=?',(result['turn_id'],)).fetchone()
        p=json.loads(r[0]);p.update(answer='',delivery_error='interrupted')
        conn.execute('UPDATE conversation_turns SET payload_json=? WHERE id=?',(encode(p),result['turn_id']))
    seg=c.view('ui')['segment_id']
    b,i,_=turn(s,c,seg,'继续制作',id='after-failure')
    reply=c.view('ui')['result_messages'][-1]
    assert reply['serverTurnId']==result['turn_id']
    assert reply['beforeUserTurnId']=='after-failure'
    assert reply['beforeUserMessage']=='继续制作'
    assert '已有素材不足' in reply['content'] and reply['deliveryError'] is None
    b.end(Identity(**i))


def test_explicit_resume_does_not_replay_unknown(env):
    s,c,seg,work,_,worker=planning(env,fail=True)
    asyncio.run(worker.run_once())
    before=s.snapshot(work)
    task=next(t for t in before['tasks'] if t['state']=='needs_decision')
    b,i,_=turn(s,c,seg,'继续制作',id='unknown-resume')
    raises('result_unknown',lambda:pipe(b,i,'offer',action='resume',
        values={'decision_id':task['id']},user_quote='继续制作'))
    assert s.snapshot(work)==before


@pytest.mark.parametrize('authorized',[True,False])
def test_explicit_replan_preserves_media_and_only_starts_planning(env,authorized):
    s,c,work=confirm_production(env)
    async def supply(ctx):
        with ctx.transaction() as conn:insert_artifact(conn,work,'retained-voice',kind='audio',run_id=ctx.run_id)
        return TaskResult(state='needs_decision',error=ProductionError('material_gap','fixture gap',requires_decision=True))
    asyncio.run(Worker(s.store,{'supply':supply}).run_once())
    if not authorized:
        with s.store.transaction() as conn:conn.execute("UPDATE authorization_grants SET revoked_at='fixture' WHERE work_id=? AND purpose='planning'",(work,))
    before=s.snapshot(work);seg=c.view('ui')['segment_id']
    # No keyword recognizer: the semantic action and genuine human source select the route.
    message='保留旧版，我想换一种结构来讲：从当代问题切入，历史放在后面，请整理新的完整方案。'
    b,i,_=turn(s,c,seg,message,id='explicit-replan')
    args={'action':'plan','values':{'intent':'replan','request':'当代问题开头，历史随后'},'user_quote':message}
    result=pipe(b,i,'offer',**args)
    if not authorized:
        assert result['requires_user_confirmation'] and result['state']=='proposed'
        assert s.snapshot(work)==before
        b.end(Identity(**i))
        b,i,_=turn(s,c,seg,'同意本次规划服务',id='replan-grant')
        result=pipe(b,i,'answer',dismiss=False,proposal_id=result['proposal_id'],hash=result['hash'],user_quote='同意本次规划服务')
    else:
        assert result['replanned'] and result['requires_user_confirmation'] is False
        assert pipe(b,i,'offer',**args)==result
    after=s.snapshot(work)
    assert after['artifacts']==before['artifacts']
    assert after['plans']==before['plans']
    assert after['current_plan_revision'] is None
    old=next(r for r in after['runs'] if r['id']==before['active_run_id'])
    new=next(r for r in after['runs'] if r['id']==result['run_id'])
    assert old['state']=='superseded' and new['kind']=='planning'
    assert len(after['runs'])==len(before['runs'])+1
    assert [t['kind'] for t in after['tasks'] if t['run_id']==new['id']]==['plan']
    b.end(Identity(**i))
    answer={'title':'新结构','summary':'新方案','script':'新的讲述。','scenes':[{'id':'s1','purpose':'解释','visual':'科技画面','narration':'新的讲述。','duration_seconds':3,'required_input_ids':[]}],'settings':{'duration_seconds':3,'aspect_ratio':'16:9','audio_mode':'silent'}}
    handler=PlanningTasks(s,OperationService(s.store),Transport(answer),{'provider':'direct-api','model':'fixture-model','mode':'structured'},'fixture')
    asyncio.run(Worker(s.store,{'plan':handler.plan}).run_once())
    final=s.snapshot(work)
    assert len(final['plans'])==len(before['plans'])+1
    assert next(p for p in final['plans'] if p['revision']==final['current_plan_revision'])['confirmed_at'] is None
    assert final['state']=='awaiting_confirmation'
    assert len(final['runs'])==len(after['runs'])  # New plan never auto-starts production.
    assert final['artifacts']==before['artifacts']


def test_explicit_replan_cannot_replace_running_production(env):
    s,c,work=confirm_production(env)
    before=s.snapshot(work);seg=c.view('ui')['segment_id']
    b,i,_=turn(s,c,seg,'重新设计方案',id='replan-active')
    raises('active_run',lambda:pipe(b,i,'offer',action='plan',
        values={'intent':'replan','request':'改变结构'},user_quote='重新设计方案'))
    assert s.snapshot(work)==before


def test_explicit_replan_preserves_unknown_receipts(env):
    s,c,work=confirm_production(env)
    async def supply(ctx):return TaskResult(state='needs_decision',error=ProductionError('material_gap','fixture',requires_decision=True))
    asyncio.run(Worker(s.store,{'supply':supply}).run_once())
    with s.store.transaction() as conn:
        conn.execute("UPDATE operations SET state='unknown' WHERE work_id=?",(work,))
    before=s.snapshot(work);seg=c.view('ui')['segment_id']
    b,i,_=turn(s,c,seg,'重新规划',id='replan-unknown')
    raises('result_unknown',lambda:pipe(b,i,'offer',action='plan',
        values={'intent':'replan','request':'改变结构'},user_quote='重新规划'))
    assert s.snapshot(work)==before


def test_explicit_replan_can_replace_unconfirmed_plan(env):
    s,c,seg,work,_,worker=planning(env)
    asyncio.run(worker.run_once())
    before=s.snapshot(work)
    assert before['state']=='awaiting_confirmation'
    b,i,_=turn(s,c,seg,'我想换个结构，请再出一版方案',id='replan-draft')
    result=pipe(b,i,'offer',action='plan',values={'intent':'replan','request':'换一个叙事结构'},
        user_quote='我想换个结构，请再出一版方案')
    after=s.snapshot(work)
    assert result['replanned'] and after['plans']==before['plans']
    assert len(after['runs'])==len(before['runs'])+1
    assert all(r['kind']=='planning' for r in after['runs'])


def test_failure_message_uses_current_attempt_and_separates_check_results():
    from easel.conversation_results import failure_text, failure_details
    tasks=[{'kind':'supply','state':'succeeded'}, {'kind':'edit','state':'succeeded'},
        {'kind':'render','state':'cancelled','error_json':encode({'user_message':'caption exceeds the frame'})},
        {'kind':'render','state':'succeeded'},
        {'kind':'quality','state':'succeeded','result_json':encode({'visual':'fail'})},
        {'kind':'revise','state':'needs_decision','error_json':encode({'code':'invalid_model_output','user_message':'工具请求无效、越界或没有新证据'})}]
    details=failure_details(tasks,'needs_decision');text=failure_text(tasks,'needs_decision')
    assert details['completed_steps']==['素材准备','剪辑','渲染']
    assert details['check_results']==['画面抽样检查发现问题']
    assert len(details['issues'])==1 and details['issues'][0]['stage']=='局部修订'
    assert '文字超出边界' not in text and 'revise' not in text
    assert '尚未恢复' not in text and '局部修订尚未完成' in text
    tasks += [{'kind':'quality','state':'succeeded','result_json':encode({'technical':'pass','semantic':'not_tested'})}]
    text=failure_text(tasks,'needs_decision')
    assert '技术检查通过' in text and '完整语义与声音检查未验证' in text
    assert '画面抽样检查发现问题' not in text


def test_ended_check_without_verdict_never_claims_pass():
    from easel.conversation_results import failure_text
    text=failure_text([{'kind':'quality','state':'succeeded'}],'needs_decision')
    assert '结果待核实' in text and '通过' not in text and '已完成：成片检查' not in text


def test_failure_continuation_hint_reuses_existing_route_without_auto_resume():
    from easel.conversation_results import failure_details, failure_text
    task={'kind':'revise','state':'needs_decision','error_json':encode({'code':'invalid_model_output','user_message':'工具请求无效、越界或没有新证据'})}
    text=failure_text([task],'needs_decision')
    assert '本对话回复「继续制作」' in text and '保留已有素材和配音' in text
    assert failure_details([task],'needs_decision',unknown=True)['next_step'] is None
    assert failure_details([task],'cancelled')['next_step'] is None
    assert failure_details([{**task,'state':'cancelled'}],'needs_decision')['next_step'] is None
    unsupported={**task,'error_json':encode({'code':'capability_unavailable','user_message':'尚无能力'})}
    assert failure_details([unsupported],'needs_decision')['next_step'] is None


def test_recovered_second_output_delivered_locally_once_without_media_work(env):
    from tests.production.test_worker import retired_render
    s,c,work=confirm_production(env)
    async def supply(ctx):return TaskResult(next_kind='edit')
    async def edit(ctx):
        retired_render(s.store,work,ctx.run_id,ctx.task_id)
        return TaskResult(next_kind='render')
    async def render(ctx):
        with ctx.transaction() as conn:
            for revision in (1,2):
                insert_artifact(conn,work,f'output-{revision}',run_id=ctx.run_id,kind='output',media_type='video/mp4',output_revision=revision,quality_state='needs_fix',displayable=1)
        return TaskResult(result={'output_id':'output-2'},next_kind='quality')
    async def quality(ctx):
        from easel.production.store import utc_now
        with ctx.transaction() as conn:
            for kind,status,findings in [('technical','pass',{}),('semantic','not_tested',{'scope':'sampled_visual_only','visual_status':'pass'}),('semantic','not_tested',{'mode':'manual_review_only'})]:
                conn.execute('INSERT INTO quality_checks VALUES (?,?,?,?,?,?,?,?)',
                    ('check-'+str(len(findings))+kind,'output-2','a'*64,kind,'fixture',status,encode(findings),utc_now()))
        return TaskResult(result={'output_id':'output-2','technical':'pass','semantic':'not_tested'},work_state='reviewable')
    asyncio.run(Worker(s.store,{'supply':supply,'edit':edit,'render':render,'quality':quality}).run_once())
    snap=s.snapshot(work);run=snap['active_run_id']
    # Reproduce the already-deployed false stop and its original text delivery.
    with s.store.transaction() as conn:
        conn.execute("UPDATE runs SET state='needs_decision' WHERE id=?",(run,))
        s.store.append_event(conn,work,'decision_required',{'code':'dependency_blocked'},run_id=run)
    relay=ConversationResults(PersistentWorkToolBridge(s))
    old=relay.reserve_next();assert old['local_delivery'] and '制作已暂停' in old['answer']
    before=s.snapshot(work)
    assert Worker(s.store,{}).reconcile_completed_run(run)
    result=relay.reserve_next()
    assert result['local_delivery']
    assert '第 2 版' in result['answer']
    assert '<video controls src="/api/production/artifacts/output-2/content"></video>' in result['answer']
    assert 'output-1/content' not in result['answer']
    assert '完整语义与声音检查未验证' in result['answer']
    assert '技术检查通过' in result['answer'] and '画面抽样检查通过（仅抽样）' in result['answer']
    assert result['payload']['delivery_state']=='delivered'
    assert relay.reserve_next() is None
    after=s.snapshot(work)
    assert before['tasks']==after['tasks']
    # Completion changes derived acceptance guidance, never the stored media/QC.
    stored=lambda artifacts:[{k:v for k,v in a.items() if k not in {'manual_review_required','delivery'}} for a in artifacts]
    assert stored(before['artifacts'])==stored(after['artifacts'])
    view=c.view('ui')
    assert view['result_messages'][-1]['content']==result['answer']
    assert view['result_messages'][-1]['resultState']=='ended'
    assert '制作已暂停' in view['result_messages'][-2]['content']  # preserve historical evidence


def test_unconfirmed_narration_change_reuses_plan_without_revision_confirmation(env):
    s,c,seg,work,_,worker=planning(env)
    asyncio.run(worker.run_once())
    before=s.snapshot(work)
    message='口播我不是很满意，句子短一点，按原观点改稿'
    b,i,_=turn(s,c,seg,message,id='narration-edit')
    with s.store.connection() as conn:
        count=conn.execute('SELECT count(*) FROM conversation_proposals').fetchone()[0]
    for action,values in [('revise',{'feedback':message,'scope':'narration','preserve_audio':False}),
                          ('confirm_revision',{'review_id':'conversation-proposal-id','change_hash':'fake','services':[]})]:
        with pytest.raises(ProductionError) as exc:
            pipe(b,i,'offer',action=action,values=values)
        assert exc.value.code in {'plan_revision_required','revision_review_missing'}
    with pytest.raises(ProductionError,match='未确认方案'):
        tool(b,i,'easel_work_request_revision',{'feedback':message})
    with s.store.connection() as conn:
        assert conn.execute('SELECT count(*) FROM conversation_proposals').fetchone()[0]==count
    result=pipe(b,i,'offer',action='plan',values={'intent':'replan','request':message},user_quote=message)
    assert result['replanned'] and not result['requires_user_confirmation']
    assert pipe(b,i,'offer',action='plan',values={'intent':'replan','request':message},user_quote=message)==result
    after=s.snapshot(work)
    assert len(after['runs'])==len(before['runs'])+1
    assert all(r['kind']=='planning' for r in after['runs'])
    assert after['artifacts']==before['artifacts']==[]
    assert after['plans']==before['plans']
    with s.store.connection() as conn:
        assert conn.execute('SELECT count(*) FROM reviews').fetchone()[0]==0
        assert conn.execute("SELECT count(*) FROM authorization_grants WHERE purpose='production'").fetchone()[0]==0


def test_historical_invalid_revision_proposal_is_readable_but_not_answerable(env):
    s,c,seg,work,_,worker=planning(env);asyncio.run(worker.run_once())
    b,i,_=turn(s,c,seg,'修改口播',id='old-bad-revision')
    # Reproduce a proposal persisted by the old entry, without calling new validation.
    with s.store.transaction() as conn:
        from easel.production.service import row
        p=c.proposal(conn,row(conn,'conversation_segments',seg),'pipeline',
                     {'action':'revise','payload':{'feedback':'修改口播'},'catalog_target':{},'summary':'旧提案'},['old-bad-revision'])
    pending=pipe(b,i,'pending')
    old=next(v for v in pending['pending'] if v['id']==p['proposal_id'])
    assert old['can_answer'] is False and old['validation_code']=='plan_revision_required'
    assert '重新规划' in pending['replanning']['instruction']
    assert not any(r['kind']=='revision' for r in s.snapshot(work)['runs'])


def test_current_audio_failure_keeps_resume_without_old_model_error():
    from easel.conversation_results import failure_details, failure_text
    tasks=[{'kind':'supply','state':'succeeded'},
        {'kind':'edit','state':'cancelled','error_json':encode({'code':'invalid_model_output','user_message':'历史模型错误'})},
        {'kind':'edit','state':'needs_decision','error_json':encode({'code':'sfx_binding_missing','user_message':'当前音效窗口不符'})}]
    details=failure_details(tasks,'needs_decision')
    text=failure_text(tasks,'needs_decision')
    assert '当前音效窗口不符' in text and '历史模型错误' not in text
    assert '继续制作' in text and '纯旁白' not in text
    assert len(details['issues'])==1
    assert failure_details(tasks,'needs_decision',unknown=True)['next_step'] is None


@pytest.mark.parametrize('state,title', [('needs_decision','方案整理已暂停'),
    ('failed','方案整理失败'), ('cancelled','方案整理已取消')])
def test_planning_failure_does_not_claim_media_production(state,title):
    from easel.conversation_results import failure_text
    task={'kind':'plan','state':state,'error_json':encode({
        'code':'draft_review_failed','user_message':'原生草稿经过两轮修正仍有明确问题，未冻结、未配音'})}
    text=failure_text([task],state)
    assert text.startswith(title)
    assert '本轮尚未进入配音、素材下载或成片制作' in text
    assert '已有方案、素材、配音' not in text
    assert '继续制作' not in text
    # Real production failures keep their existing media-retention scope.
    text=failure_text([{'kind':'supply','state':'succeeded'},
        {'kind':'edit','state':state}],state)
    assert '已有方案、素材、配音' in text


@pytest.mark.parametrize('visual', ['pass','fail','partial',None])
def test_preview_preserves_visual_verdict_without_promoting_full_semantics(visual):
    from easel.conversation_pipeline import output_summary
    from easel.conversation_results import preview_text
    findings={'scope':'sampled_visual_only','review':{'findings':[]}}
    if visual:findings['visual_status']=visual
    output={'output_revision':1,'playback_url':'/actual-output','checks':[
        {'kind':'technical','status':'pass','findings':{}},
        {'kind':'semantic','status':'not_tested','findings':findings},
        {'kind':'semantic','status':'not_tested','findings':{'mode':'manual_review_only'}}]}
    checks=output_summary(output)['checks']
    assert checks[1]['status']=='not_tested'
    assert checks[1].get('visual_status')==visual
    assert checks[2]['status']=='not_tested' and 'visual_status' not in checks[2]
    text=preview_text(output)
    verdict={'pass':'通过','fail':'发现问题','partial':'部分完成',None:'未完整验证'}[visual]
    assert '本版画面抽样检查：'+verdict+'（仅抽样）' in text
    assert '本版内容检查：未完整验证' in text
