"""Recovery of an invalid review label does not erase real defects or rerender."""
import json
import pytest
from tests.production.test_conversation import env,draft,output_fixture,encode,now,turn
from tests.production.test_conversation_pipeline import pipe
from easel.production.errors import ProductionError
from easel.production.quality import effective_quality_checks


def setup(env,verdict='pass'):
    service,c,seg,work=draft(env);path=output_fixture(service,work,style=False)
    with service.store.transaction() as conn:
        run=conn.execute('SELECT active_run_id FROM works WHERE id=?',(work,)).fetchone()[0]
        task=conn.execute('SELECT id FROM tasks WHERE run_id=?',(run,)).fetchone()[0]
        conn.execute("UPDATE works SET state='preview_needs_fix' WHERE id=?",(work,))
        conn.execute("UPDATE tasks SET kind='quality',payload_json=? WHERE id=?",(encode({'schema_version':1,'output_id':'out','project_id':'project','repair_round':1}),task))
        checksum=conn.execute("SELECT digest FROM artifacts WHERE id='out'").fetchone()[0]
        conn.execute('INSERT INTO quality_checks VALUES (?,?,?,?,?,?,?,?)',('invalid','out',checksum,'semantic','visual-preview-1','fail',encode({'scope':'sampled_visual_only','visual_status':'fail','review':{'verdict':verdict,'findings':['评审正文'],'observations':['frame']}}),now()))
    return service,c,seg,work,path,task


def test_recheck_uses_existing_resume_and_preserves_successful_media_history(env):
    s,c,seg,w,path,task=setup(env)
    before=path.read_bytes();snap=s.snapshot(w)
    b,i,_=turn(s,c,seg,'仅重新复核当前视频，不重做',id='recheck')
    choice=next(x for x in pipe(b,i,'pending')['blockers'] if x['code']=='visual_review_inconsistent')['choices'][0]
    assert choice['action']=='resume' and choice['values']=={'decision_id':task}
    result=s.command('resume',choice['values'],command_id='explicit-recheck',work_id=w,expected_revision=snap['revision'])
    assert result['run_id']==snap['active_run_id']
    after=s.snapshot(w);assert len(after['tasks'])==len(snap['tasks'])
    changed=next(t for t in after['tasks'] if t['id']==task)
    assert changed['state']=='pending' and json.loads(changed['payload_json'])['visual_recheck_source']=='invalid'
    assert path.read_bytes()==before and after['accepted_output_id'] is None
    with s.store.connection() as conn:
        assert conn.execute("SELECT status FROM quality_checks WHERE id='invalid'").fetchone()[0]=='fail'
        assert conn.execute('SELECT count(*) FROM operations').fetchone()[0]==0


def test_real_failed_review_has_no_automatic_recheck_escape(env):
    s,c,seg,w,path,task=setup(env,verdict='fail')
    snap=s.snapshot(w)
    with s.store.connection() as conn:assert s.visual_review_recheck(conn,dict(conn.execute('SELECT * FROM works WHERE id=?',(w,)).fetchone())) is None
    with pytest.raises(ProductionError):s.command('resume',{'decision_id':task},command_id='not-a-review-conflict',work_id=w,expected_revision=snap['revision'])


def test_only_explicit_consistent_same_bytes_recheck_resolves_invalid_label():
    old={'id':'old','artifact_id':'a','artifact_digest':'bytes','rule_version':'visual-preview-1','status':'fail','findings_json':json.dumps({'scope':'sampled_visual_only','review':{'verdict':'pass','findings':['ambiguous']}})}
    raw={'scope':'sampled_visual_only','visual_status':'pass','rechecks_invalid_review':'old','review':{'verdict':'pass','observations':['frame'],'findings':[],'limitations':['未听声音']}}
    new={**old,'id':'new','rule_version':'visual-preview-2','status':'not_tested','findings_json':json.dumps(raw)}
    assert len(effective_quality_checks([old]))==1
    assert [x['id'] for x in effective_quality_checks([old,new])]==['new']
    assert len(effective_quality_checks([old,{**new,'artifact_digest':'other-bytes'}]))==2
    actual={**old,'findings_json':json.dumps({'scope':'sampled_visual_only','review':{'verdict':'fail','findings':['实际错误']}})}
    assert len(effective_quality_checks([actual,new]))==2
    raw['review']['findings']=['contradiction']
    assert len(effective_quality_checks([old,{**new,'findings_json':json.dumps(raw)}]))==2


@pytest.mark.parametrize('state',['sending','unknown'])
def test_recheck_never_repeats_an_in_flight_or_unknown_operation(env,state):
    s,c,seg,w,path,task=setup(env)
    snap=s.snapshot(w)
    with s.store.transaction() as conn:
        grant=conn.execute('SELECT id FROM authorization_grants WHERE work_id=? LIMIT 1',(w,)).fetchone()[0]
        conn.execute('INSERT INTO operations(id,work_id,run_id,task_id,grant_id,kind,state,provider,model,mode,config_version,request_key,input_hash,request_json,owner_epoch,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',('uncertain',w,snap['active_run_id'],task,grant,'MODEL',state,'fixture','fixture','structured','v1','key','0'*64,'{}',0,now(),now()))
    with pytest.raises(ProductionError):s.command('resume',{'decision_id':task},command_id='unsafe-recheck',work_id=w,expected_revision=snap['revision'])
    with s.store.connection() as conn:assert conn.execute("SELECT state FROM operations WHERE id='uncertain'").fetchone()[0]==state
