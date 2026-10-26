"""Pre-output plan replacement uses isolated state and no provider calls."""
import json
import pytest
from tests.production.test_conversation import env, raises
from easel.production.service import row, encode
from easel.production.errors import ProductionError


def stopped(env):
    s,_=env
    work=s.command('create',{'title':'测试','input_text':'不可改原话','settings':{'audio_mode':'mixed'}},command_id='create')['work_id']
    plan={'title':'测试','summary':'原观点','script':'逐字稿','core_views':['观点'],
          'scenes':[{'id':'s1','purpose':'说明','visual':'桌面','narration':'逐字稿'}],
          'settings':{'duration_seconds':10,'audio_mode':'mixed'}}
    p=s.command('plan',{'generate':False,'plan':plan},command_id='plan',work_id=work,expected_revision=s.snapshot(work)['revision'])
    r=s.command('confirm',p,command_id='confirm',work_id=work,expected_revision=s.snapshot(work)['revision'])
    with s.store.transaction() as conn:
        conn.execute("UPDATE runs SET state='needs_decision' WHERE id=?",(r['run_id'],))
        conn.execute("UPDATE tasks SET state='needs_decision' WHERE run_id=?",(r['run_id'],))
    return s,work,r['run_id']


def test_replan_keeps_history_and_retires_waiting_run(env):
    s,w,r=stopped(env);before=s.snapshot(w)
    with s.store.connection() as conn:target=s.preoutput_target(conn,row(conn,'works',w),{'settings':{'audio_mode':'voice'}})
    data={'settings':{'audio_mode':'voice'},'recovery_target':target,'services':[{'provider':'direct-api','model':'fixture-model','mode':'structured'}]}
    result=s.command('plan',data,command_id='recover',work_id=w,expected_revision=before['revision'])
    after=s.snapshot(w)
    assert after['plans']==before['plans']
    assert next(x for x in after['runs'] if x['id']==r)['state']=='superseded'
    assert after['input_text']=='不可改原话'
    with s.store.connection() as conn:
        task=dict(conn.execute('SELECT * FROM tasks WHERE run_id=?',(result['run_id'],)).fetchone())
        payload=json.loads(task['payload_json'])
        assert payload['protected_plan']==before['plans'][0]['plan']
        assert conn.execute("SELECT count(*) FROM authorization_grants WHERE purpose='production' AND revoked_at IS NULL").fetchone()[0]==0
    assert s.command('plan',data,command_id='recover',work_id=w,expected_revision=before['revision'])==result


@pytest.mark.parametrize('mutation', ['owner','running','cancelled','changed'])
def test_unsafe_replan_rejected(env,mutation):
    s,w,r=stopped(env)
    with s.store.transaction() as conn:
        if mutation=='owner':conn.execute("UPDATE runs SET owner_id='worker' WHERE id=?",(r,))
        if mutation=='running':conn.execute("UPDATE runs SET state='running' WHERE id=?",(r,))
        if mutation=='cancelled':conn.execute("UPDATE works SET state='cancelled' WHERE id=?",(w,))
        data={'settings':{'audio_mode':'voice'}}
        if mutation=='changed':data['settings']['duration_seconds']=20
        with pytest.raises(ProductionError):s.preoutput_target(conn,row(conn,'works',w),data)


def test_replan_rolls_back_retirement_when_new_schedule_fails(env,monkeypatch):
    s,w,r=stopped(env);before=s.snapshot(w)
    with s.store.connection() as conn:target=s.preoutput_target(conn,row(conn,'works',w),{'settings':{'audio_mode':'voice'}})
    def fail_run(*args,**kwargs):raise RuntimeError('injected transaction failure')
    monkeypatch.setattr(s,'_run',fail_run)
    with pytest.raises(RuntimeError):s.command('plan',{'settings':{'audio_mode':'voice'},'recovery_target':target},command_id='recover',work_id=w,expected_revision=before['revision'])
    assert s.snapshot(w)==before


def test_replan_rejects_stale_target_and_existing_output(env):
    from tests.production.test_store import insert_artifact
    s,w,r=stopped(env)
    with s.store.connection() as conn:target=s.preoutput_target(conn,row(conn,'works',w),{'settings':{'audio_mode':'voice'}})
    with s.store.transaction() as conn:conn.execute('UPDATE runs SET revision=revision+1 WHERE id=?',(r,))
    raises('stale_revision',lambda:s.command('plan',{'settings':{'audio_mode':'voice'},'recovery_target':target},command_id='recover',work_id=w,expected_revision=s.snapshot(w)['revision']))
    with s.store.transaction() as conn:
        insert_artifact(conn,w,kind='output')
        raises('revision_required',lambda:s.preoutput_target(conn,row(conn,'works',w),{'settings':{'audio_mode':'voice'}}))


@pytest.mark.parametrize('state',['reserved','sending','submitted','unknown'])
def test_inflight_and_unknown_are_never_reopened(env,state):
    from easel.production.service import now
    s,w,r=stopped(env)
    with s.store.transaction() as conn:
        task=conn.execute('SELECT id FROM tasks WHERE run_id=?',(r,)).fetchone()[0]
        grant=conn.execute('SELECT id FROM authorization_grants WHERE work_id=?',(w,)).fetchone()[0]
        conn.execute("INSERT INTO operations(id,work_id,run_id,task_id,grant_id,kind,state,provider,model,mode,config_version,request_key,input_hash,request_json,owner_epoch,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",('op',w,r,task,grant,'MODEL',state,'fixture','fixture','structured','v1','key','fingerprint','{}',0,now(),now()))
        raises('result_unknown',lambda:s.preoutput_target(conn,row(conn,'works',w),{'settings':{'audio_mode':'voice'}}))


def test_fake_planning_produces_v2_and_preserves_v1(env):
    import asyncio
    from tests.production.test_planning_runtime import Transport
    from easel.production.planning import PlanningTasks, CreativePlan
    from easel.production.operations import OperationService
    from easel.production.worker import Worker
    s,w,r=stopped(env);old=s.snapshot(w)['plans'][0]
    with s.store.connection() as conn:target=s.preoutput_target(conn,row(conn,'works',w),{'settings':{'audio_mode':'voice'}})
    identity={'provider':'direct-api','model':'fixture-model','mode':'structured'}
    s.command('plan',{'settings':{'audio_mode':'voice'},'recovery_target':target,'services':[identity]},command_id='recover',work_id=w,expected_revision=s.snapshot(w)['revision'])
    answer={k:v for k,v in old['plan'].items() if k in CreativePlan.model_fields}
    answer['settings']={**answer['settings'],'audio_mode':'voice'}
    transport=Transport(answer)
    handler=PlanningTasks(s,OperationService(s.store),transport,identity,'fixture')
    assert asyncio.run(Worker(s.store,{'plan':handler.plan}).run_once())
    snap=s.snapshot(w)
    assert snap['plans'][-1]==old
    assert snap['plans'][0]['revision']==2, snap['tasks']
    assert snap['plans'][0]['confirmed_at'] is None
    assert snap['plans'][0]['plan']['script']==old['plan']['script']
    assert '本片不使用背景音乐或可选音效' in snap['plans'][0]['plan']['constraints']
    assert transport.calls==1


@pytest.mark.parametrize('field',['script','core_views','scenes','settings'])
def test_audio_replan_rejects_expanded_content(env,field):
    from easel.production.planning import validate_audio_replan, CreativePlan
    s,w,_=stopped(env);old=s.snapshot(w)['plans'][0]['plan']
    changed={k:v for k,v in old.items() if k in CreativePlan.model_fields}
    changed['settings']={**old['settings'],'audio_mode':'voice'}
    if field=='settings':changed[field]['duration_seconds']=15
    elif field=='scenes':changed[field]=[{**old['scenes'][0],'id':'another'}]
    elif field=='core_views':changed[field]=['不同观点']
    else:changed[field]='改了旁白'
    with pytest.raises(ValueError):validate_audio_replan(changed,old)


def test_cancelled_work_recovery_requires_later_human_answer(env):
    from tests.production.test_conversation import entry,turn
    from tests.production.test_conversation_pipeline import seed,pipe
    from easel.work_bridge import Identity
    s,c=env;channel=seed(env)
    seg=entry(c,profile_ref='one',channel_id=channel,director_revision='v4',director_trial=True)
    b,i,_=turn(s,c,seg,'创建作品')
    w=pipe(b,i,'draft',user_quote='创建作品',values={'title':'测试','input_text':'原文'})['work_id']
    b.end(Identity(**i))
    p=s.command('plan',{'generate':False,'plan':{'title':'测试','summary':'观点','script':'原稿','scenes':[{'id':'s1','purpose':'说明','visual':'桌面'}],'settings':{'duration_seconds':10,'audio_mode':'mixed'}}},command_id='plan',work_id=w,expected_revision=s.snapshot(w)['revision'])
    s.command('confirm',p,command_id='confirm',work_id=w,expected_revision=s.snapshot(w)['revision'])
    s.command('cancel',{},command_id='cancel',work_id=w,expected_revision=s.snapshot(w)['revision'])
    b,i,_=turn(s,c,seg,'恢复本作品改纯旁白，不要背景音乐音效',id='restore')
    raises('confirmation_required',lambda:pipe(b,i,'offer',action='plan',values={'settings':{'audio_mode':'voice'}}))
    proposal=pipe(b,i,'offer',action='plan',values={'settings':{'audio_mode':'voice'},'restore_cancelled':True})
    assert proposal['values']['payload']['services']
    raises('confirmation_required',lambda:pipe(b,i,'answer',dismiss=False,proposal_id=proposal['proposal_id'],hash=proposal['hash'],user_quote='恢复本作品'))
    b.end(Identity(**i));b,i,_=turn(s,c,seg,'确认恢复并重新规划',id='yes')
    result=pipe(b,i,'answer',dismiss=False,proposal_id=proposal['proposal_id'],hash=proposal['hash'],user_quote='确认恢复并重新规划')
    assert result['run_id']
    assert s.snapshot(w)['plans'][0]['confirmed_at']
    assert s.snapshot(w)['input_text']=='原文'


def test_model_scope_expansion_stops_after_existing_bounded_correction(env):
    import asyncio
    from tests.production.test_planning_runtime import Transport
    from easel.production.planning import PlanningTasks,CreativePlan
    from easel.production.operations import OperationService
    from easel.production.worker import Worker
    s,w,_=stopped(env);old=s.snapshot(w)['plans']
    with s.store.connection() as conn:target=s.preoutput_target(conn,row(conn,'works',w),{'settings':{'audio_mode':'voice'}})
    identity={'provider':'direct-api','model':'fixture-model','mode':'structured'}
    s.command('plan',{'settings':{'audio_mode':'voice'},'recovery_target':target,'services':[identity]},command_id='recover',work_id=w,expected_revision=s.snapshot(w)['revision'])
    answer={k:v for k,v in old[0]['plan'].items() if k in CreativePlan.model_fields}
    answer['settings']={**answer['settings'],'audio_mode':'voice'};answer['script']='擅自改写'
    transport=Transport(answer);handler=PlanningTasks(s,OperationService(s.store),transport,identity,'fixture')
    worker=Worker(s.store,{'plan':handler.plan})
    asyncio.run(worker.run_once())
    assert s.snapshot(w)['plans']==old
    assert s.snapshot(w)['state']=='needs_decision'
    assert transport.calls==3
    assert not asyncio.run(worker.run_once())
