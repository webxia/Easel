"""Committed execution receipts, original-turn delivery and recovery ownership."""
import asyncio
import json
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from tests.production.test_conversation import env, entry, turn, raises, tool
from tests.production.test_conversation_pipeline import seed, pipe
from tests.production.test_planning_runtime import Transport
from easel.conversation_bridge import PersistentCall, PersistentDispatch, ExecutionPoll
from easel.conversation_results import ConversationResults
from easel.production.planning import PlanningTasks
from easel.production.operations import OperationService
from easel.production.worker import Worker, TaskResult
from easel.production.service import encode
from easel.work_bridge import Identity


def start(env,legacy=False):
    s,c=env;channel=seed(env)
    seg=entry(c,profile_ref='one',channel_id=channel,director_revision='v4',director_trial=True)
    b,i,_=turn(s,c,seg,'制作视频')
    work=pipe(b,i,'draft',user_quote='制作视频',values={'title':'等待','input_text':'技术服务人'})['work_id']
    p=tool(b,i,'easel_work_request_plan',{'request':'完整方案'}) if legacy else pipe(b,i,'offer',action='plan',values={'request':'完整方案'})
    b.end(Identity(**i));b,i,_=turn(s,c,seg,'确认规划',id='execute')
    with s.store.transaction() as conn:
        conn.execute("UPDATE conversation_turns SET payload_json=json_set(payload_json,'$.delivery_state','streaming','$.delivery_lease_until',?) WHERE id='execute'",(time.time()+30,))
    args=dict(mode='answer',proposal_id=p['proposal_id'],hash=p['hash'],user_quote='确认规划')
    call=PersistentCall(**i,tool_call_id='execute-call',tool='easel_pipeline',params=args)
    req=PersistentDispatch(**call.model_dump(),ticket=b.prepare(call)['ticket'])
    receipt=b.dispatch(req)
    return s,c,b,i,ExecutionPoll(**req.model_dump()),receipt


def worker(s):
    answer={'title':'等待','summary':'摘要','script':'技术服务人。','scenes':[{'id':'s1','purpose':'解释','visual':'科技画面','narration':'技术服务人。','duration_seconds':3,'required_input_ids':[]}],'settings':{'duration_seconds':3,'aspect_ratio':'16:9','audio_mode':'silent'}}
    handler=PlanningTasks(s,OperationService(s.store),Transport(answer),{'provider':'direct-api','model':'fixture-model','mode':'structured'},'fixture')
    return Worker(s.store,{'plan':handler.plan})


@pytest.mark.parametrize('legacy',[False,True])
def test_wait_receipt_is_committed_worker_writes_then_same_turn_acknowledges(env,legacy):
    s,c,b,i,req,receipt=start(env,legacy=legacy);results=ConversationResults(b)
    assert results.poll(req)['waiting']
    raises('execution_delivery_incomplete',lambda:b.complete_delivery('execute','已提交'))
    # A different thread can write while the native tool is polling.
    with ThreadPoolExecutor() as pool:pool.submit(lambda:asyncio.run(worker(s).run_once())).result(timeout=10)
    ready=results.poll(req)
    assert not ready['waiting']
    assert ready['result']['execution_result']['run_state']=='succeeded'
    assert '技术服务人。' in encode(ready)
    assert results.reserve_next() is None
    b.end(Identity(**i))
    assert results.reserve_next() is None  # end hook can precede the last Web token.
    raises('invocation_pending',lambda:b.reserve(ui_session='ui',turn_id='too-early',segment_id=c.view('ui')['segment_id'],message='新问题',attachments=[]))
    b.complete_delivery('execute','完整方案及逐字稿已交付，请确认后制作。')
    assert results.reserve_next() is None
    assert len(s.snapshot(receipt['work_id'])['runs'])==1


@pytest.mark.parametrize('after_result',[False,True])
def test_interruption_does_not_cancel_and_fallback_only_after_native_end(env,after_result):
    s,c,b,i,req,receipt=start(env);results=ConversationResults(b)
    asyncio.run(worker(s).run_once())
    if after_result:assert not results.poll(req)['waiting']
    b.delivery('execute','unknown','')
    assert results.reserve_next() is None
    b.end(Identity(**i))
    with ThreadPoolExecutor() as pool:claims=list(pool.map(lambda _:results.reserve_next(),range(4)))
    assert sum(x is not None for x in claims)==1
    assert s.snapshot(receipt['work_id'])['runs'][0]['state']=='succeeded'


def test_expired_web_delivery_lease_recovers_only_verified_ended_native(env):
    s,c,b,i,req,_=start(env);results=ConversationResults(b)
    asyncio.run(worker(s).run_once());results.poll(req);b.end(Identity(**i))
    assert results.reserve_next() is None
    with s.store.transaction() as conn:
        conn.execute("UPDATE conversation_turns SET payload_json=json_set(payload_json,'$.delivery_lease_until',?) WHERE id='execute'",(time.time()-1,))
    assert results.reserve_next()


def test_wrong_native_identity_or_uncommitted_ticket_cannot_follow_other_run(env):
    s,c,b,i,req,_=start(env);results=ConversationResults(b)
    raises('binding_mismatch',lambda:results.poll(req.model_copy(update={'run_id':'other'})))
    raises('ticket_mismatch',lambda:results.poll(req.model_copy(update={'ticket':'x'*32})))
    before=s.snapshot(c.view('ui')['work_id'])
    stopped=results.poll(req.model_copy(update={'interrupted':True}))
    assert stopped['result']['wait_interrupted']
    assert s.snapshot(before['id'])==before


def test_no_wait_for_read_or_proposal(env):
    s,c,b,i,req,_=start(env)
    call=PersistentCall(**i,tool_call_id='read',tool='easel_pipeline',params={'mode':'pending'})
    request=PersistentDispatch(**call.model_dump(),ticket=b.prepare(call)['ticket'])
    value=b.dispatch(request)
    assert ConversationResults(b).poll(ExecutionPoll(**request.model_dump()))=={'waiting':False,'result':value}


def answer(b,i,p,quote):
    call=PersistentCall(**i,tool_call_id='answer-'+i['run_id'],tool='easel_pipeline',params={'mode':'answer','proposal_id':p['proposal_id'],'hash':p['hash'],'user_quote':quote})
    req=PersistentDispatch(**call.model_dump(),ticket=b.prepare(call)['ticket'])
    receipt=b.dispatch(req)
    return ExecutionPoll(**req.model_dump()),receipt


def end_and_turn(s,c,b,i,quote,id):
    b.end(Identity(**i))
    b.complete_delivery(i['run_id'].removeprefix('run-'),'实际结果与待确认方案。')
    return turn(s,c,c.view('ui')['segment_id'],quote,id=id)[:2]


def complete_plan(env):
    s,c,b,i,req,receipt=start(env)
    asyncio.run(worker(s).run_once());ConversationResults(b).poll(req)
    return s,c,b,i,receipt


def production(env):
    s,c,b,i,receipt=complete_plan(env);snap=s.snapshot(receipt['work_id']);plan=snap['plans'][0]
    p=pipe(b,i,'offer',action='confirm',values={'plan_revision':1,'plan_hash':plan['plan_hash'],'services':[]})
    b,i=end_and_turn(s,c,b,i,'确认制作','produce')
    req,r=answer(b,i,p,'确认制作')
    return s,c,b,i,req,r


def test_production_waits_for_all_tasks_including_existing_repair_and_final_quality(env):
    s,c,b,i,req,r=production(env);results=ConversationResults(b);stages=[]
    async def stage(ctx):
        kind=next(t['kind'] for t in s.snapshot(r['work_id'])['tasks'] if t['id']==ctx.task_id)
        stages.append(kind)
        assert results.poll(req)['waiting']
        if kind=='quality' and stages.count('quality')==2:return TaskResult(work_state='reviewable')
        return TaskResult(next_kind={'supply':'edit','edit':'render','render':'quality','quality':'revise','revise':'render'}[kind])
    asyncio.run(Worker(s.store,{k:stage for k in ['supply','edit','render','quality','revise']}).run_once())
    assert stages==['supply','edit','render','quality','revise','render','quality']
    assert results.poll(req)['result']['execution_result']['run_state']=='succeeded'
    assert len(s.snapshot(r['work_id'])['runs'])==2


@pytest.mark.parametrize('action',['resume','grant'])
def test_existing_resume_and_grant_resume_wait_on_same_run(env,action):
    from easel.production.errors import ProductionError
    s,c,b,i,req,r=start(env);results=ConversationResults(b)
    async def needs_grant(ctx):return TaskResult(state='needs_decision',error=ProductionError('permission_missing','缺少授权',requires_decision=True))
    asyncio.run(Worker(s.store,{'plan':needs_grant}).run_once())
    result=results.poll(req)['result'];assert result['execution_result']['run_state']=='needs_decision'
    task=s.snapshot(r['work_id'])['tasks'][0]
    values={'decision_id':task['id']} if action=='resume' else {'purpose':'planning'}
    p=pipe(b,i,'offer',action=action,values=values)
    b,i=end_and_turn(s,c,b,i,'同意继续原任务','resume')
    req,continued=answer(b,i,p,'同意继续原任务')
    assert continued['run_id']==r['run_id']
    assert results.poll(req)['waiting']
    asyncio.run(worker(s).run_once())
    assert results.poll(req)['result']['execution_result']['run_state']=='succeeded'
    b.complete_delivery('resume','已收到完整方案');b.end(Identity(**i))
    assert results.reserve_next() is None  # consume BOTH subscriptions of resumed run.


def test_revision_and_expanded_scope_confirmation_wait_but_stop_at_new_plan(env):
    from tests.production.test_store import insert_artifact
    from easel.production.service import digest
    from easel.production.errors import ProductionError
    s,c,b,i,req,r=production(env);results=ConversationResults(b)
    async def ready(ctx):return TaskResult(work_state='reviewable')
    asyncio.run(Worker(s.store,{'supply':ready}).run_once());results.poll(req)
    with s.store.transaction() as conn:
        insert_artifact(conn,r['work_id'],'selected-output',kind='output',run_id=r['run_id'],output_revision=1,displayable=1)
    p=pipe(b,i,'offer',action='revise',values={'output_id':'selected-output','feedback':'改画面'})
    b,i=end_and_turn(s,c,b,i,'确认局部修订','revision')
    req,revision=answer(b,i,p,'确认局部修订');assert results.poll(req)['waiting']
    changes={'schema_version':1,'summary':'修改影响内容，需要新方案'}
    async def expanded(ctx):
        with ctx.transaction() as conn:conn.execute('UPDATE reviews SET changes_json=? WHERE id=?',(encode(changes),revision['review_id']))
        return TaskResult(state='needs_decision',error=ProductionError('revision_scope_changed','需确认影响',requires_decision=True))
    asyncio.run(Worker(s.store,{'revise':expanded}).run_once())
    assert results.poll(req)['result']['execution_result']['run_state']=='needs_decision',[(t['kind'],t['error_json']) for t in s.snapshot(r['work_id'])['tasks']]
    p=pipe(b,i,'offer',action='confirm_revision',values={'review_id':revision['review_id'],'change_hash':digest(changes),'services':[]})
    b,i=end_and_turn(s,c,b,i,'确认影响范围','scope')
    req,newplan=answer(b,i,p,'确认影响范围')
    assert newplan['run_id']!=revision['run_id'] and results.poll(req)['waiting']
    asyncio.run(worker(s).run_once())
    result=results.poll(req)['result']['execution_result']
    assert result['plan_ready'] and result['run_state']=='succeeded'
    assert next(x for x in s.snapshot(r['work_id'])['runs'] if x['id']==newplan['run_id'])['kind']=='planning'
    snapshot=s.snapshot(r['work_id'])
    assert next(p for p in snapshot['plans'] if p['revision']==snapshot['current_plan_revision'])['confirmed_at'] is None


def test_reference_analysis_uses_same_receipt_wait_without_confirming_director(env):
    from tests.production.test_conversation import attachment, proposal
    s,c=env;seg=entry(c,profile_ref='one',kind='director_formation')
    b,i,_=turn(s,c,seg,'建立参考作品')
    work=pipe(b,i,'draft',user_quote='建立参考作品',values={'title':'参考','input_text':'分析参考'})['work_id']
    a=attachment(s)
    input=s.command('input',{'session_id':'ui','attachment':a},command_id='input',work_id=work,expected_revision=s.snapshot(work)['revision'])
    b,i=end_and_turn(s,c,b,i,'请分析这条参考','ref-proposal')
    p=proposal(s,c,seg,'director_formation',{'name':'参考导演','reference_input_ids':[input['input_id']]},'ref-proposal')
    b,i=end_and_turn(s,c,b,i,'确认分析参考','reference')
    req,receipt=answer(b,i,p,'确认分析参考');results=ConversationResults(b)
    assert results.poll(req)['waiting']
    async def analyzed(ctx):return TaskResult(result={'analysis':'本地假参考分析'},work_state='discussing')
    asyncio.run(Worker(s.store,{'analyze_director':analyzed}).run_once())
    ready=results.poll(req)['result']['execution_result']
    assert ready['run_state']=='succeeded' and ready['tasks'][0]['kind']=='analyze_director'
    with s.store.connection() as conn:assert conn.execute('SELECT count(*) FROM director_revisions').fetchone()[0]==0


def test_provider_timeout_unknown_is_delivered_without_replay(env):
    from easel.production.model_tasks import ModelTaskError
    s,c,b,i,req,r=start(env);w=worker(s)
    async def timeout(*args):raise ModelTaskError('provider_timeout','提交结果未知，不重发')
    w.handlers['plan'].__self__.transport.complete=timeout
    asyncio.run(w.run_once());result=ConversationResults(b).poll(req)['result']['execution_result']
    assert result['run_state']=='needs_decision' and result['unknown_operations']
    assert not result['model_result_query_available']
    before=s.snapshot(r['work_id']);ConversationResults(b).poll(req)
    assert s.snapshot(r['work_id'])==before


def test_result_endpoint_retains_loopback_credential_and_native_ticket_checks(env,monkeypatch):
    import web.app as web
    from fastapi.testclient import TestClient
    s,c,b,i,req,_=start(env)
    token='isolated-result-token-long-enough'
    monkeypatch.setattr(web.app.state,'production_service',s,raising=False)
    monkeypatch.setenv('EASEL_WORK_BRIDGE_TOKEN',token)
    headers={'Authorization':'Bearer '+token}
    local=TestClient(web.app,base_url='http://127.0.0.1:7860',client=('127.0.0.1',12345))
    assert local.post('/api/chat/work-tools/result',json=req.model_dump()).status_code==401
    response=local.post('/api/chat/work-tools/result',headers=headers,json=req.model_dump())
    assert response.status_code==200 and response.json()['waiting']
    assert local.post('/api/chat/work-tools/result',headers=headers,json={**req.model_dump(),'run_id':'foreign'}).status_code==403
    remote=TestClient(web.app,base_url='http://127.0.0.1:7860',client=('192.0.2.5',12345))
    assert remote.post('/api/chat/work-tools/result',headers=headers,json=req.model_dump()).status_code==403


def test_completion_and_recovery_race_has_exactly_one_delivery_owner(env):
    s,c,b,i,req,_=start(env);results=ConversationResults(b)
    asyncio.run(worker(s).run_once());results.poll(req);b.end(Identity(**i))
    with ThreadPoolExecutor() as pool:
        future=pool.submit(results.reserve_next)
        b.complete_delivery('execute','完整方案已交付。')
        assert future.result() is None
    assert results.reserve_next() is None
    # The live delivery lease also prevents a new user turn stealing the latest
    # native binding between agent_end and the last streamed token (covered above).


def test_expired_owner_cannot_late_acknowledge_recovery_claim(env):
    s,c,b,i,req,_=start(env);results=ConversationResults(b)
    asyncio.run(worker(s).run_once());results.poll(req);b.end(Identity(**i))
    with s.store.transaction() as conn:
        conn.execute("UPDATE conversation_turns SET payload_json=json_set(payload_json,'$.delivery_lease_until',0) WHERE id='execute'")
    assert results.reserve_next()
    raises('result_delivery_claimed',lambda:b.complete_delivery('execute','迟到的旧回复'))


def test_retired_agent_result_is_not_automatically_replayed(env):
    s,c,b,i,req,_=start(env);results=ConversationResults(b)
    asyncio.run(worker(s).run_once());results.poll(req);b.end(Identity(**i))
    with s.store.transaction() as conn:
        conn.execute("UPDATE conversation_turns SET payload_json=json_set(payload_json,'$.session_key','agent:easel-video:legacy','$.delivery_lease_until',0) WHERE id='execute'")
    before=s.snapshot(c.view('ui')['work_id'])
    assert results.reserve_next() is None
    assert s.snapshot(c.view('ui')['work_id'])==before


def test_failed_draft_is_not_delivered_as_confirmable_plan(env):
    from easel.production.errors import ProductionError
    s,c,b,i,req,r=start(env)
    async def rejected(ctx):
        with ctx.transaction() as conn:
            t=conn.execute('SELECT payload_json FROM tasks WHERE id=?',(ctx.task_id,)).fetchone()
            payload=json.loads(t[0]);payload['native_draft_checkpoint']={'draft':{'script':'UNAPPROVED_PRIVATE_DRAFT'},'review':{'verdict':'fail','findings':['加入了用户未要求的品牌限制']}}
            conn.execute('UPDATE tasks SET payload_json=? WHERE id=?',(encode(payload),ctx.task_id))
        return TaskResult(state='needs_decision',error=ProductionError('draft_review_failed','草稿未通过，未冻结',requires_decision=True))
    asyncio.run(Worker(s.store,{'plan':rejected}).run_once())
    result=ConversationResults(b).poll(req)['result']
    assert result['execution_result']['current_plan'] is None
    assert result['execution_result']['plan_ready'] is False
    assert result['execution_result']['outcome']=='blocked'
    assert 'UNAPPROVED_PRIVATE_DRAFT' not in encode(result)
    assert '加入了用户未要求的品牌限制' in encode(result)
    assert '不能声称方案成功' in result['delivery_instruction']
    assert 'UNAPPROVED_PRIVATE_DRAFT' in encode(s.snapshot(r['work_id']))
    assert 'UNAPPROVED_PRIVATE_DRAFT' not in encode(pipe(b,i,'pending'))


@pytest.mark.parametrize("kind,code", [("edit","invalid_edit_project"),("revise","invalid_revision_search")])
def test_known_edit_failure_exposes_existing_resume_without_resubmission(env,kind,code):
    from easel.production.errors import ProductionError
    s,c,b,i,req,r=start(env)
    with s.store.transaction() as conn:
        conn.execute("UPDATE tasks SET kind=? WHERE run_id=?",(kind,r['run_id']))
    async def fail_edit(ctx):
        return TaskResult(state='needs_decision',error=ProductionError(code,'known boundary failure',requires_decision=True))
    asyncio.run(Worker(s.store,{kind:fail_edit}).run_once())
    pending=pipe(b,i,'pending');choice=pending['blockers'][0]['choices'][0]
    assert choice['action']=='resume' and choice['values']['decision_id']
    assert '阻断已解决' in choice['requires']
    proposal=pipe(b,i,'offer',action=choice['action'],values=choice['values'])
    assert s.snapshot(r['work_id'])['runs'][0]['state']=='needs_decision'
    ConversationResults(b).poll(req)
    b.end(Identity(**i));b.complete_delivery('execute','说明失败与恢复范围')
    b,i,_=turn(s,c,c.view('ui')['segment_id'],'确认修复后继续',id='resume-edit')
    reply=pipe(b,i,'answer',proposal_id=proposal['proposal_id'],hash=proposal['hash'],user_quote='确认修复后继续')
    assert reply['run_id']==r['run_id']
    assert s.snapshot(r['work_id'])['tasks'][0]['state']=='pending'


def test_same_stage_real_events_refresh_native_progress_without_fake_ticks(env):
    s,c,b,i,req,receipt=start(env);results=ConversationResults(b)
    before=results.poll(req)
    assert results.poll(req)==before
    with s.store.transaction() as conn:
        s.store.append_event(conn,receipt['work_id'],'material_search_completed',{},run_id=receipt['run_id'])
    after=results.poll(req)
    assert after['waiting'] and after['task']==before['task']
    assert after['progress_seq']>before['progress_seq']
    assert results.poll(req)==after
