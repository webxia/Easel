"""Viewing and Creator acceptance never schedule production or rewrite QC."""
import json
import pytest
from easel.production.errors import ProductionError
from easel.production.publication import Publications
from easel.production.store import Store
from easel.work_bridge import Identity
from tests.production.test_conversation import env, draft, output_fixture, now, encode, turn
from tests.production.test_conversation_pipeline import pipe
from tests.production.test_publication import Fake


def checked(env):
    s,c,seg,w=draft(env)
    path=output_fixture(s,w,style=False)
    with s.store.transaction() as conn:
        checksum=conn.execute("SELECT digest FROM artifacts WHERE id='out'").fetchone()[0]
        conn.execute('INSERT INTO quality_checks VALUES (?,?,?,?,?,?,?,?)',
            ('visual','out',checksum,'semantic','visual-preview-1','fail',
             encode({'scope':'sampled_visual_only','visual_status':'fail',
                     'review':{'findings':['本版画面待人工判断'],'observations':['long observation']}}),now()))
    return s,c,seg,w,path


def tables(s):
    with s.store.connection() as conn:
        return {t:[tuple(r) for r in conn.execute('SELECT * FROM '+t+' ORDER BY rowid')]
                for t in ('works','runs','tasks','operations','artifacts','quality_checks','reviews','acceptances','conversation_proposals')}


@pytest.mark.parametrize('selector',[{}, {'output_id':'out'}, {'output_revision':1}])
def test_preview_is_read_only_and_durable_even_if_model_stops(env,selector):
    s,c,seg,w,path=checked(env)
    before=tables(s)
    b,i,_=turn(s,c,seg,'看下第一版',id='preview')
    result=pipe(b,i,'preview',values=selector)
    assert result['read_only'] and not result['requires_user_confirmation']
    assert '<video controls src="/api/production/artifacts/out/content">' in result['preview_text']
    assert '本版画面待人工判断' in result['preview_text']
    assert 'long observation' not in result['preview_text']
    b.end(Identity(**i))
    assert result['preview_text'] in [m['content'] for m in c.view('ui')['result_messages']]
    assert tables(s)==before
    assert c.view('ui')['result_messages']==c.view('ui')['result_messages']


def test_pending_keeps_real_link_and_current_version_findings(env):
    s,c,seg,w,path=checked(env)
    b,i,reserved=turn(s,c,seg,'查看最新版本',id='preview')
    assert '/api/production/artifacts/out/content' in reserved['prompt']
    output=pipe(b,i,'pending')['work']['artifacts'][0]
    assert output['playback_url']=='/api/production/artifacts/out/content'
    assert output['manual_review_required'] and output['delivery']['can_accept']
    assert output['checks'][-1]['findings']==['本版画面待人工判断']


def test_preview_latest_and_explicit_version_never_mix_findings(env):
    s,c,seg,w,path=checked(env)
    with s.store.transaction() as conn:
        conn.execute("""INSERT INTO artifacts(id,work_id,run_id,kind,storage_ref,digest,size_bytes,
            displayable,output_revision,quality_state,created_at)
            SELECT 'out2',work_id,run_id,kind,storage_ref,digest,size_bytes,displayable,2,quality_state,created_at
            FROM artifacts WHERE id='out'""")
        conn.execute("""INSERT INTO quality_checks SELECT 'visual2','out2',digest,'semantic',
            'visual-preview-1','fail',?,? FROM artifacts WHERE id='out2'""",
            (encode({'scope':'sampled_visual_only','review':{'findings':['第二版新问题']}}),now()))
    b,i,_=turn(s,c,seg,'看第二版',id='preview')
    newest=pipe(b,i,'preview')
    assert newest['preview_output']['output_revision']==2
    assert '第二版新问题' in newest['preview_text'] and '本版画面待人工判断' not in newest['preview_text']
    first=pipe(b,i,'preview',values={'output_revision':1})
    assert '本版画面待人工判断' in first['preview_text'] and '第二版新问题' not in first['preview_text']


@pytest.mark.parametrize('values',[{'output_id':'foreign'}, {'output_revision':9}, {'feedback':'重做'}])
def test_preview_rejects_wrong_version_or_effectful_parameters(env,values):
    s,c,seg,w,path=checked(env)
    before=tables(s)
    b,i,_=turn(s,c,seg,'查看',id='preview')
    with pytest.raises(ProductionError):pipe(b,i,'preview',values=values)
    assert tables(s)==before


def test_complete_human_review_accepts_and_publishes_without_new_production(env):
    s,c,seg,w,path=checked(env)
    before=tables(s);original=path.read_bytes()
    b,i,_=turn(s,c,seg,'我已完整审阅这版画面声音字幕同步，全部通过，接受此版',id='accept')
    result=pipe(b,i,'offer',action='accept',values={'output_id':'out','manual_review_confirmed':True},
                user_quote='我已完整审阅这版画面声音字幕同步，全部通过，接受此版')
    assert result['output_id']=='out' and not result['requires_user_confirmation']
    after=tables(s)
    for table in ('runs','tasks','operations','artifacts','quality_checks','reviews'):
        assert after[table]==before[table]
    assert path.read_bytes()==original
    assert len(after['acceptances'])==1 and after['acceptances'][0][3]=='explicit_manual_review'
    output=s.snapshot(w)['artifacts'][0]
    assert output['quality_state']=='needs_fix' and output['delivery']['can_publish']
    with s.store.connection() as conn:
        event=json.loads(conn.execute("SELECT payload_json FROM events WHERE kind='output_accepted'").fetchone()[0])
        assert 'visual' in event['reviewed_check_ids'] and event['artifact_digest']==output['digest']
    pub=Publications(s,Fake());draft=pub.prepare(w,'out')
    assert draft['output_id']=='out' and draft['attempts']==[] and pub.adapter.calls==0


@pytest.mark.parametrize('failure',['no_human','technical','missing','changed','unfinished','cancelled'])
def test_human_review_retains_identity_completion_and_file_integrity(env,failure):
    s,c,seg,w,path=checked(env)
    if failure=='missing':path.unlink()
    if failure=='changed':path.write_bytes(b'changed')
    with s.store.transaction() as conn:
        if failure=='technical':
            conn.execute("UPDATE quality_checks SET status='fail' WHERE check_kind='technical'")
        if failure=='unfinished':conn.execute("UPDATE runs SET state='needs_decision' WHERE kind='production'")
        if failure=='cancelled':conn.execute("UPDATE works SET state='cancelled' WHERE id=?",(w,))
    with pytest.raises(ProductionError):
        s.command('accept',{'output_id':'out','manual_review_confirmed':failure!='no_human'},
                  command_id='accept',work_id=w,expected_revision=s.snapshot(w)['revision'])
    assert s.snapshot(w)['accepted_output_id'] is None


def test_schema_seven_upgrade_retains_all_existing_rows(tmp_path,monkeypatch):
    import easel.production.store as module
    with monkeypatch.context() as patch:
        patch.setattr(module,'SCHEMA_VERSION',7)
        old_env=env.__wrapped__(tmp_path)
        s,c,seg,w,path=checked(old_env)
    before=tables(s)
    Store(s.store.path).initialize()
    assert tables(s)==before
    with s.store.connection() as conn:
        assert conn.execute('PRAGMA user_version').fetchone()[0]==8
        assert not conn.execute('PRAGMA foreign_key_check').fetchall()
    s.command('accept',{'output_id':'out','manual_review_confirmed':True},command_id='accept',
              work_id=w,expected_revision=s.snapshot(w)['revision'])


def test_followup_stays_in_dialogue_text_with_specific_next_steps(env):
    s,c,seg,w,path=checked(env);before=tables(s)
    b,i,_=turn(s,c,seg,'只重新展示当前视频，不修改',id='dialogue-followup')
    result=pipe(b,i,'preview')
    assert '本版画面待人工判断' in result['preview_text']
    assert '要改画面' in result['preview_text'] and '原句和替换句' in result['preview_text']
    assert '完整看过并确认' in result['preview_text'] and '接受第1版' in result['preview_text']
    assert 'output_followup' not in c.view('ui')
    b.end(Identity(**i));assert tables(s)==before
