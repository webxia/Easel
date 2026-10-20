"""New planning only after a separate human answer; old UNKNOWN stays immutable."""
import asyncio
import json
import httpx
import pytest
from tests.production.test_conversation import env, entry, turn, raises
from tests.production.test_conversation_pipeline import seed, pipe
from easel.work_bridge import Identity
from easel.production.configuration import model_configuration
from easel.production.model_tasks import HTTPModelTransport
from easel.production.operations import OperationService
from easel.production.planning import PlanningTasks
from easel.production.worker import Worker


def paused(env):
    s,c=env;channel=seed(env)
    seg=entry(c,profile_ref='one',channel_id=channel,director_revision='v4',director_trial=True)
    b,i,_=turn(s,c,seg,'整理想法')
    work=pipe(b,i,'draft',user_quote='整理想法',values={'title':'例子','input_text':'分析小事'})['work_id']
    b.end(Identity(**i))
    s.command('basis',{'settings':{'audio_mode':'silent','duration_seconds':3}},work_id=work,expected_revision=s.snapshot(work)['revision'],command_id='silent-fixture')
    settings,model,version=model_configuration(s.outputs.parent)
    s.command('plan',{'request':'保留原要求','services':[model]},work_id=work,expected_revision=s.snapshot(work)['revision'],command_id='original-plan')
    calls=[]
    def timeout(req):calls.append(req);raise httpx.ReadTimeout('fixture-private')
    transport=HTTPModelTransport(settings,transport=httpx.MockTransport(timeout))
    planning=PlanningTasks(s,OperationService(s.store),transport,model,version)
    asyncio.run(Worker(s.store,{'plan':planning.plan}).run_once())
    snap=s.snapshot(work)
    assert json.loads(snap['tasks'][0]['error_json'])['code']=='provider_timeout'
    assert len(calls)==1
    with s.store.connection() as conn:
        old=dict(conn.execute('SELECT * FROM operations WHERE work_id=?',(work,)).fetchone())
    return s,c,seg,work,old,calls


def test_web_dialogue_unknown_requires_new_answer_is_idempotent_and_preserves_evidence(env):
    s,c,seg,work,old,calls=paused(env)
    before=s.snapshot(work)
    b,i,_=turn(s,c,seg,'怎么继续',id='explain')
    status=pipe(b,i,'pending')['model_calls']
    assert status['diagnostics'][0]['timeout_type']=='read'
    assert status['diagnostics'][0]['operation_id']==old['id']
    assert json.loads(before['tasks'][0]['error_json'])['operation_id']==old['id']
    assert status['recovery']['can_offer']
    p=pipe(b,i,**status['recovery']['next_action'])
    summary=p['values']['summary']
    assert all(text in summary for text in ('可能重复计费','保留旧UNKNOWN','不制作视频','一次规划任务不代表只有一次模型调用'))
    raises('confirmation_required',lambda:pipe(b,i,'answer',proposal_id=p['proposal_id'],hash=p['hash'],user_quote='怎么继续'))
    assert s.snapshot(work)['runs']==before['runs']
    b.end(Identity(**i))
    b,i,_=turn(s,c,seg,'同意以上范围，另行规划',id='explicit-answer')
    result=pipe(b,i,'answer',proposal_id=p['proposal_id'],hash=p['hash'],user_quote='同意以上范围，另行规划')
    assert pipe(b,i,'answer',proposal_id=p['proposal_id'],hash=p['hash'],user_quote='同意以上范围，另行规划')==result
    assert result['run_id']!=old['run_id'] and result['previous_result']=='UNKNOWN'
    with s.store.connection() as conn:
        assert dict(conn.execute('SELECT * FROM operations WHERE id=?',(old['id'],)).fetchone())==old
        assert conn.execute('SELECT count(*) FROM operations').fetchone()[0]==1
        tasks=conn.execute('SELECT * FROM tasks ORDER BY created_at').fetchall()
        assert len(tasks)==2 and tasks[0]['state']=='cancelled' and tasks[1]['state']=='pending'
        assert json.loads(tasks[1]['payload_json'])['request']=='保留原要求'
        grants=conn.execute('SELECT * FROM authorization_grants WHERE revoked_at IS NULL').fetchall()
        assert len(grants)==1 and grants[0]['purpose']=='planning' and not grants[0]['allow_ai']
    assert len(calls)==1  # no worker was started for the new task


@pytest.mark.parametrize('changed',['receipt','model','basis','run','foreign_task','inflight'])
def test_changed_recovery_conditions_never_cancel_or_enqueue(env,changed):
    s,c,seg,work,old,calls=paused(env)
    b,i,_=turn(s,c,seg,'如何继续',id='offer')
    status=pipe(b,i,'pending')['model_calls'];action=status['recovery']['next_action']
    if changed=='foreign_task':
        raises('stale_revision',lambda:pipe(b,i,'offer',action='replan_after_unknown',values={'decision_id':'other'}));return
    p=pipe(b,i,**action);b.end(Identity(**i))
    with s.store.transaction() as conn:
        if changed=='receipt':conn.execute("UPDATE operations SET state='succeeded',revision=revision+1 WHERE id=?",(old['id'],))
        elif changed=='run':conn.execute("UPDATE runs SET state='running',owner_id='worker' WHERE id=?",(old['run_id'],))
        elif changed=='inflight':conn.execute("UPDATE operations SET state='sending' WHERE id=?",(old['id'],))
        elif changed=='basis':conn.execute("UPDATE works SET settings_json=json_set(settings_json,'$.duration_seconds',5) WHERE id=?",(work,))
    if changed=='model':(s.outputs.parent/'.env').write_text('EASEL_DIRECT_API_BASE_URL=http://127.0.0.1:1/v1\nEASEL_DIRECT_API_MODEL=changed\n')
    b,i,_=turn(s,c,seg,'确认另行规划',id='answer')
    raises('result_unknown' if changed in {'receipt','inflight'} else 'stale_revision',lambda:pipe(b,i,'answer',proposal_id=p['proposal_id'],hash=p['hash'],user_quote='确认另行规划'))
    with s.store.connection() as conn:
        assert conn.execute('SELECT count(*) FROM runs').fetchone()[0]==1
        assert conn.execute("SELECT count(*) FROM runs WHERE state='cancelled'").fetchone()[0]==0
        assert conn.execute('SELECT count(*) FROM authorization_grants WHERE revoked_at IS NOT NULL').fetchone()[0]==0
    assert len(calls)==1


def test_legacy_unknown_without_diagnostics_is_not_backfilled(env):
    s,c,seg,work,old,calls=paused(env)
    with s.store.transaction() as conn:conn.execute("DELETE FROM events WHERE kind='model_call_diagnostic'")
    b,i,_=turn(s,c,seg,'看看现在的状态',id='read-only')
    status=pipe(b,i,'pending')['model_calls']
    assert status['diagnostics']==[] and status['recovery']['can_offer']
    assert '不能补推' in status['recovery']['note']
    assert s.snapshot(work)['tasks'][0]['state']=='needs_decision' and len(calls)==1


def test_new_plan_failure_rolls_back_local_stop_and_grant_revocation(env,monkeypatch):
    from easel.production.errors import ProductionError
    s,c,seg,work,old,calls=paused(env)
    b,i,_=turn(s,c,seg,'怎么继续',id='offer')
    p=pipe(b,i,**pipe(b,i,'pending')['model_calls']['recovery']['next_action'])
    b.end(Identity(**i))
    before=s.snapshot(work)
    def fail_plan(*args):raise ProductionError('fixture_failure','模拟新规划入队失败')
    monkeypatch.setattr(s,'_plan',fail_plan)
    b,i,_=turn(s,c,seg,'同意另行规划',id='answer')
    raises('fixture_failure',lambda:pipe(b,i,'answer',proposal_id=p['proposal_id'],hash=p['hash'],user_quote='同意另行规划'))
    assert s.snapshot(work)==before
    with s.store.connection() as conn:
        assert dict(conn.execute('SELECT * FROM operations WHERE id=?',(old['id'],)).fetchone())==old
        assert conn.execute('SELECT count(*) FROM authorization_grants WHERE revoked_at IS NOT NULL').fetchone()[0]==0
