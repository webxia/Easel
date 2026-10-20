"""First-plan recovery, isolated database only; never calls a provider."""
import pytest
from tests.production.test_conversation import env, raises
from easel.production.service import row


def stopped(env):
    s,_=env
    w=s.command('create',{'title':'fixture','settings':{'duration_seconds':45}},command_id='create')['work_id']
    r=s.command('plan',{'services':[{'provider':'direct-api','model':'fixture-model','mode':'structured'}]},work_id=w,expected_revision=1,command_id='plan')['run_id']
    with s.store.transaction() as c:
        c.execute("UPDATE runs SET state='needs_decision' WHERE id=?",(r,))
        c.execute("UPDATE tasks SET state='needs_decision',error_json=? WHERE run_id=?",('{"code":"plan_constraint_changed"}',r))
        c.execute("UPDATE works SET state='needs_decision' WHERE id=?",(w,))
        t=c.execute('SELECT id FROM tasks WHERE run_id=?',(r,)).fetchone()[0]
    return s,w,r,t


def test_recovery_preserves_work_and_history_and_is_idempotent(env):
    s,w,r,t=stopped(env)
    with s.store.connection() as c:target=s.failed_planning_target(c,row(c,'works',w),t)
    before=s.snapshot(w)
    data={'decision_id':t,'failed_planning_target':target}
    result=s.command('plan',data,work_id=w,expected_revision=before['revision'],command_id='recover')
    after=s.snapshot(w)
    assert result['work_id']==w and result['run_id']!=r
    assert next(x for x in after['runs'] if x['id']==r)['state']=='superseded'
    assert after['settings']==before['settings']
    assert s.command('plan',data,work_id=w,expected_revision=before['revision'],command_id='recover')==result
    assert after['plans']==[]


@pytest.mark.parametrize('mutation',['owner','running','cancelled','uncertain_error','stale'])
def test_unsafe_recovery_rejected(env,mutation):
    s,w,r,t=stopped(env)
    with s.store.transaction() as c:
        if mutation=='owner':c.execute("UPDATE runs SET owner_id='worker' WHERE id=?",(r,))
        if mutation=='running':c.execute("UPDATE runs SET state='running' WHERE id=?",(r,))
        if mutation=='cancelled':c.execute("UPDATE works SET state='cancelled' WHERE id=?",(w,))
        if mutation=='uncertain_error':
            c.execute('UPDATE tasks SET error_json=? WHERE id=?',('{"code":"provider_timeout"}',t))
        if mutation=='stale':t='missing'
        from easel.production.errors import ProductionError
        with pytest.raises(ProductionError):s.failed_planning_target(c,row(c,'works',w),t)


def test_schedule_failure_rolls_back(env,monkeypatch):
    s,w,r,t=stopped(env)
    with s.store.connection() as c:target=s.failed_planning_target(c,row(c,'works',w),t)
    before=s.snapshot(w)
    def fail(*a,**k):raise RuntimeError('injected')
    monkeypatch.setattr(s,'_run',fail)
    with pytest.raises(RuntimeError):s.command('plan',{'decision_id':t,'failed_planning_target':target},work_id=w,expected_revision=before['revision'],command_id='recover')
    assert s.snapshot(w)==before


@pytest.mark.parametrize('state',['reserved','sending','submitted','unknown'])
def test_work_wide_operation_guard(env,state):
    from easel.production.service import now
    s,w,r,t=stopped(env)
    with s.store.transaction() as c:
        g=c.execute('SELECT id FROM authorization_grants WHERE work_id=?',(w,)).fetchone()[0]
        c.execute('INSERT INTO operations(id,work_id,run_id,task_id,grant_id,kind,state,provider,model,mode,config_version,request_key,input_hash,request_json,owner_epoch,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',('op',w,r,t,g,'MODEL',state,'fixture','fixture','structured','v1','key','hash','{}',0,now(),now()))
        raises('result_unknown',lambda:s.failed_planning_target(c,row(c,'works',w),t))


def test_stale_recovery_target_is_rejected(env):
    s,w,r,t=stopped(env)
    with s.store.connection() as c:target=s.failed_planning_target(c,row(c,'works',w),t)
    with s.store.transaction() as c:c.execute('UPDATE runs SET revision=revision+1 WHERE id=?',(r,))
    raises('stale_revision',lambda:s.command('plan',{'decision_id':t,'failed_planning_target':target},work_id=w,expected_revision=s.snapshot(w)['revision'],command_id='recover'))


def test_conversation_recovery_requires_new_human_confirmation(env):
    from tests.production.test_conversation import entry,turn
    from tests.production.test_conversation_pipeline import seed,pipe
    from easel.work_bridge import Identity
    s,c=env;channel=seed(env)
    seg=entry(c,profile_ref='one',channel_id=channel,director_revision='v4',director_trial=True)
    b,i,_=turn(s,c,seg,'创建作品')
    w=pipe(b,i,'draft',user_quote='创建作品',values={'title':'测试','input_text':'原文'})['work_id']
    b.end(Identity(**i))
    r=s.command('plan',{},work_id=w,expected_revision=s.snapshot(w)['revision'],command_id='plan')['run_id']
    with s.store.transaction() as conn:
        conn.execute("UPDATE runs SET state='needs_decision' WHERE id=?",(r,))
        conn.execute("UPDATE tasks SET state='needs_decision',error_json=? WHERE run_id=?",('{"code":"plan_constraint_changed"}',r))
        conn.execute("UPDATE works SET state='needs_decision' WHERE id=?",(w,))
    b,i,_=turn(s,c,seg,'继续整理方案',id='offer')
    option=pipe(b,i,'pending')['failed_planning_replan']
    assert option['can_offer']
    proposed=pipe(b,i,'offer',action='plan',values=option['values'])
    assert '不取消整部作品' in proposed['values']['summary']
    assert '费用' in proposed['values']['summary']
    assert len(s.snapshot(w)['runs'])==1
    raises('confirmation_required',lambda:pipe(b,i,'answer',proposal_id=proposed['proposal_id'],hash=proposed['hash'],user_quote='继续整理方案'))
    b.end(Identity(**i))
    b,i,_=turn(s,c,seg,'确认重新规划的费用和范围',id='answer')
    pipe(b,i,'answer',proposal_id=proposed['proposal_id'],hash=proposed['hash'],user_quote='确认重新规划的费用和范围')
    snap=s.snapshot(w)
    assert len(snap['runs'])==2 and snap['state']=='discussing'
    assert not snap['plans']
