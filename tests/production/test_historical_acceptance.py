"""Manual acceptance follows the selected completed output, not a later plan."""
import pytest
from easel.conversation import ConversationService
from easel.production.errors import ProductionError
from easel.production.store import Store
from easel.production.publication import Publications
from easel.publication_bilibili import BilibiliAdapter
from tests.production.test_conversation import env, draft, output_fixture, now, encode, turn
from tests.production.test_conversation_pipeline import pipe


def historical(env, *, proof=True, reversed_events=False):
    s,c,seg,w=draft(env)
    output_fixture(s,w,style=False)
    with s.store.transaction() as conn:
        run=conn.execute("SELECT run_id FROM artifacts WHERE id='out'").fetchone()[0]
        events=['run_completed','run_superseded']
        if reversed_events:events.reverse()
        for kind in events:
            if proof or kind!='run_completed':s.store.append_event(conn,w,kind,{},run_id=run)
        conn.execute("UPDATE runs SET state='superseded' WHERE id=?",(run,))
        conn.execute("UPDATE works SET state='needs_decision',current_plan_revision=NULL WHERE id=?",(w,))
    return s,c,seg,w,run


def test_web_bridge_accepts_proven_completed_version_and_prepares_original_draft(env):
    s,c,seg,w,run=historical(env)
    before=s.snapshot(w)
    b,i,_=turn(s,c,seg,'我已完整审阅并接受此版，继续发布',id='accept-historical')
    pipe(b,i,'offer',action='accept',values={'output_id':'out','manual_review_confirmed':True},user_quote='我已完整审阅并接受此版，继续发布')
    result=pipe(b,i,'offer',action='publication_prepare',values={'output_id':'out'},user_quote='我已完整审阅并接受此版，继续发布')
    assert result['publication']['output_id']=='out'
    after=s.snapshot(w)
    assert after['runs']==before['runs'] and after['tasks']==before['tasks']
    assert after['state']=='needs_decision' and after['current_plan_revision'] is None
    assert after['accepted_output_id']=='out'
    assert next(a for a in after['artifacts'] if a['id']=='out')['quality_state']=='needs_fix'


@pytest.mark.parametrize('proof,reversed_events',[(False,False),(True,True)])
def test_incomplete_superseded_run_never_qualifies(env,proof,reversed_events):
    s,c,seg,w,run=historical(env,proof=proof,reversed_events=reversed_events)
    with pytest.raises(ProductionError,match='制作尚未成功完成'):
        s.command('accept',{'output_id':'out','manual_review_confirmed':True},command_id='invalid-accept',work_id=w,expected_revision=s.snapshot(w)['revision'])
    # Database guard is independently authoritative too.
    with pytest.raises(ProductionError):
        with s.store.transaction() as conn:
            conn.execute("INSERT INTO acceptances VALUES ('forged',?,'out','explicit_manual_review',?)",(w,now()))


def test_missing_human_fact_blocks_but_creator_can_resolve_content_findings(env):
    s,c,seg,w,run=historical(env)
    with pytest.raises(ProductionError) as error:
        s.command('accept',{'output_id':'out'},command_id='no-human',work_id=w,expected_revision=s.snapshot(w)['revision'])
    assert error.value.code=='manual_review_confirmation_required'
    with s.store.transaction() as conn:
        checksum=conn.execute("SELECT digest FROM artifacts WHERE id='out'").fetchone()[0]
        conn.execute('INSERT INTO quality_checks VALUES (?,?,?,?,?,?,?,?)',('failure','out',checksum,'semantic','fixture','fail',encode({'findings':['known defect']}),now()))
    result=s.command('accept',{'output_id':'out','manual_review_confirmed':True},command_id='known-failure',work_id=w,expected_revision=s.snapshot(w)['revision'])
    assert result['output_id']=='out'
    with s.store.connection() as conn:
        assert conn.execute("SELECT status FROM quality_checks WHERE id='failure'").fetchone()[0]=='fail'
    assert Publications(s,BilibiliAdapter(s.outputs.parent)).prepare(w,'out')['output_id']=='out'
