"""Real domain commands in isolated DB; no model/network/media generation."""
import json
import pytest
from tests.production.test_conversation import env, entry, turn, tool, raises, proposal
from easel.work_bridge import Identity
from easel.production.service import now, encode, row
from easel.production.catalog import CreativeCatalog


def seed(env):
    service,c=env
    channel=CreativeCatalog(service).command('channels','create',{'name':'频道甲','profile_ref':'one','settings':{'schema_version':1}},command_id='channel')
    with service.store.transaction() as conn:
        conn.execute("INSERT INTO directors(id,name,created_at,updated_at) VALUES ('director','导演甲',?,?)",(now(),now()))
        conn.execute("INSERT INTO director_revisions(id,director_id,revision,style_json,evidence_json,style_confirmed,created_at) VALUES ('v4','director',4,?,?,1,?)",(encode({'schema_version':1,'visual_style':'清晰','storytelling':'朋友'}),encode([{'source':'fixture'}]),now()))
    return channel['id']


def pipe(b,i,mode,**kwargs):return tool(b,i,'easel_pipeline',{'mode':mode,**kwargs})


def test_missing_choices_and_no_implicit_only_option(env):
    channel=seed(env);s,c=env;seg=entry(c,profile_ref='one')
    b,i,_=turn(s,c,seg,'创作一个视频')
    state=pipe(b,i,'pending')
    assert state['missing_choices']==['channel','director']
    assert state['channels'][0]['id']==channel
    raises('selection_required',lambda:pipe(b,i,'draft',user_quote='创作一个视频',values={'title':'视频','input_text':'想法'}))
    assert s.list_works()['items']==[]


def test_selected_pipeline_handoff_waits_native_end(env):
    channel=seed(env);s,c=env;seg=entry(c,profile_ref='one')
    b,i,_=turn(s,c,seg,'用频道甲和导演甲')
    r=pipe(b,i,'bind',user_quote='用频道甲和导演甲',values={'kind':'new_work','channel_id':channel,'director_revision':'v4','director_trial':True})
    assert r['queued'] and c.view('ui')['segment_id']==seg
    raises('pipeline_switch_pending',lambda:tool(b,i,'easel_work_context',{}))
    b.end(Identity(**i));view=c.view('ui')
    assert view['segment_id']!=seg
    assert view['context']['settings']['director_trial'] is True
    assert view['context']['handoff']['user_message']=='用频道甲和导演甲'
    with s.store.connection() as conn:assert row(conn,'director_revisions','v4')['accepted_at'] is None
    assert s.list_works()['items']==[]


def test_local_draft_and_plan_confirmation_are_separate(env):
    channel=seed(env);s,c=env;seg=entry(c,profile_ref='one',channel_id=channel,director_revision='v4',director_trial=True)
    b,i,_=turn(s,c,seg,'把今天的想法做视频')
    d=pipe(b,i,'draft',user_quote='把今天的想法做视频',values={'title':'想法','input_text':'今天的想法'})
    assert not s.snapshot(d['work_id'])['runs']
    p=pipe(b,i,'offer',action='plan',values={'request':'深入分析','services':[]},summary='整理完整方案')
    raises('confirmation_required',lambda:pipe(b,i,'answer',proposal_id=p['proposal_id'],hash=p['hash'],user_quote='把今天的想法做视频'))
    b.end(Identity(**i))
    b,i,_=turn(s,c,seg,'同意整理方案',id='answer')
    result=pipe(b,i,'answer',proposal_id=p['proposal_id'],hash=p['hash'],user_quote='同意整理方案')
    assert result['run_id']
    assert pipe(b,i,'answer',proposal_id=p['proposal_id'],hash=p['hash'],user_quote='同意整理方案')==result
    assert len(s.snapshot(d['work_id'])['runs'])==1
    with s.store.connection() as conn:assert conn.execute('SELECT count(*) FROM operations').fetchone()[0]==0


def test_channel_save_from_user_reply_and_forbidden_source(env):
    s,c=env;seg=entry(c,profile_ref='one',kind='channel_create')
    b,i,_=turn(s,c,seg,'创建一个学习频道')
    p=proposal(s,c,seg,'channel_create',{'name':'学习频道','creative_basis':{'position':'学习','themes':'实践','audience':'普通人'}})
    b.end(Identity(**i))
    b,i,_=turn(s,c,seg,'保存这个频道',id='save')
    raises('invalid_source',lambda:pipe(b,i,'answer',proposal_id=p['proposal_id'],hash=p['hash'],user_quote='助手说同意'))
    saved=pipe(b,i,'answer',proposal_id=p['proposal_id'],hash=p['hash'],user_quote='保存这个频道')
    assert c.view('ui')['context']['channel_id']==saved['id']
    assert s.list_works()['items']==[]


def test_director_revision_then_style_confirm_without_acceptance(env):
    seed(env);s,c=env;seg=entry(c,profile_ref='one',kind='director_formation',director_revision='v4')
    b,i,_=turn(s,c,seg,'把节奏改松弛')
    with s.store.connection() as conn:rev=row(conn,'directors','director')['revision']
    p=proposal(s,c,seg,'director_revision',{'style':{'visual_style':'清晰','storytelling':'松弛'},'base_revision':rev})
    b.end(Identity(**i))
    b,i,_=turn(s,c,seg,'保存新风格',id='save')
    pipe(b,i,'answer',proposal_id=p['proposal_id'],hash=p['hash'],user_quote='保存新风格')
    with s.store.connection() as conn:v=dict(conn.execute('SELECT * FROM director_revisions ORDER BY revision DESC').fetchone())
    assert v['revision']==5 and not v['style_confirmed'] and not v['accepted_at']
    p=pipe(b,i,'offer',action='director_style',values={'revision_id':v['id']},summary='确认新风格，仍待试片')
    b.end(Identity(**i))
    b,i,_=turn(s,c,seg,'确认这个风格',id='confirm')
    pipe(b,i,'answer',proposal_id=p['proposal_id'],hash=p['hash'],user_quote='确认这个风格')
    with s.store.connection() as conn:
        v=row(conn,'director_revisions',v['id']);assert v['style_confirmed'] and not v['accepted_at']
    assert s.list_works()['items']==[]


def test_pipeline_scope_and_stale_proposals(env):
    s,c=env;seg=entry(c,profile_ref='one',kind='channel_create')
    b,i,_=turn(s,c,seg,'创建频道')
    raises('pipeline_mismatch',lambda:pipe(b,i,'draft',user_quote='创建频道',values={'title':'bad','input_text':'bad'}))
    raises('pipeline_mismatch',lambda:pipe(b,i,'offer',action='plan',values={},summary='bad'))
    first=proposal(s,c,seg,'channel_create',{'name':'旧'})
    second=proposal(s,c,seg,'channel_create',{'name':'新'})
    b.end(Identity(**i));b,i,_=turn(s,c,seg,'保存',id='save')
    raises('stale_revision',lambda:pipe(b,i,'answer',proposal_id=first['proposal_id'],hash=first['hash'],user_quote='保存'))
    pipe(b,i,'answer',proposal_id=second['proposal_id'],hash=second['hash'],user_quote='保存')


def test_bind_cross_profile_and_unconfirmed_director_rejected(env):
    seed(env);s,c=env;seg=entry(c,profile_ref='two')
    b,i,_=turn(s,c,seg,'选这个')
    with s.store.connection() as conn:ch=conn.execute('SELECT id FROM channels').fetchone()[0]
    raises('binding_mismatch',lambda:pipe(b,i,'bind',user_quote='选这个',values={'channel_id':ch}))
    with s.store.transaction() as conn:conn.execute("UPDATE director_revisions SET style_confirmed=0 WHERE id='v4'")
    raises('invalid_input',lambda:pipe(b,i,'bind',user_quote='选这个',values={'director_revision':'v4','director_trial':True}))


def test_full_plan_confirm_uses_exact_version_and_creates_only_one_run(env):
    channel=seed(env);s,c=env;seg=entry(c,profile_ref='one',channel_id=channel,director_revision='v4',director_trial=True)
    b,i,_=turn(s,c,seg,'做个视频')
    d=pipe(b,i,'draft',user_quote='做个视频',values={'title':'小事','input_text':'具体想法'})
    b.end(Identity(**i))
    plan={'title':'小事','summary':'分析一个问题','script':'这是具体分析。','scenes':[{'id':'s1','purpose':'解释','visual':'书桌','narration':''}],'settings':{'duration_seconds':1,'aspect_ratio':'16:9','audio_mode':'silent'}}
    created=s.command('plan',{'generate':False,'plan':plan},command_id='fixture-plan',work_id=d['work_id'],expected_revision=s.snapshot(d['work_id'])['revision'])
    b,i,_=turn(s,c,seg,'给我看看方案',id='show')
    p=pipe(b,i,'offer',action='confirm',values={'plan_revision':created['plan_revision'],'plan_hash':created['plan_hash'],'services':[],'image_limit':0,'video_limit':0,'allow_ai':False},summary='按方案制作，不授权生成素材')
    b.end(Identity(**i))
    b,i,_=turn(s,c,seg,'就按这个方案制作',id='produce')
    result=pipe(b,i,'answer',proposal_id=p['proposal_id'],hash=p['hash'],user_quote='就按这个方案制作')
    b.end(Identity(**i));b,i,_=turn(s,c,seg,'就按这个方案制作',id='duplicate')
    repeated=pipe(b,i,'answer',proposal_id=p['proposal_id'],hash=p['hash'],user_quote='就按这个方案制作')
    assert repeated['run_id']==result['run_id']
    snapshot=s.snapshot(d['work_id']);assert len(snapshot['runs'])==1
    with s.store.connection() as conn:
        assert conn.execute('SELECT count(*) FROM operations').fetchone()[0]==0
        assert row(conn,'director_revisions','v4')['accepted_at'] is None


def test_handoff_preserves_user_sources_without_cross_profile_leak(env):
    channel=seed(env);s,c=env;seg=entry(c,profile_ref='one')
    b,i,_=turn(s,c,seg,'讲一次失败，但不要编经历')
    b.end(Identity(**i));b,i,_=turn(s,c,seg,'选择频道甲和导演甲',id='selection')
    pipe(b,i,'bind',user_quote='选择频道甲和导演甲',values={'kind':'new_work','channel_id':channel,'director_revision':'v4','director_trial':True})
    b.end(Identity(**i));new=c.view('ui')['segment_id']
    b,i,res=turn(s,c,new,'继续',id='continue')
    assert '不要编经历' in res['prompt']
    d=pipe(b,i,'draft',user_quote='继续',values={'title':'失败','input_text':'真实失败'})
    tool(b,i,'easel_work_update_brief',{'entries':[{'kind':'user_requirement','text':'不要编经历','source_refs':['turn']}]})
    assert not s.snapshot(d['work_id'])['runs']


def test_failed_handoff_does_not_leave_turn_active(env):
    channel=seed(env);s,c=env;seg=entry(c,profile_ref='one')
    b,i,_=turn(s,c,seg,'选择频道甲')
    pipe(b,i,'bind',user_quote='选择频道甲',values={'channel_id':channel})
    with s.store.transaction() as conn:conn.execute('UPDATE channels SET archived=1 WHERE id=?',(channel,))
    b.end(Identity(**i))
    assert c.view('ui')['segment_id']==seg
    with s.store.connection() as conn:
        r=row(conn,'conversation_turns','turn');assert r['state']=='ended'
        assert json.loads(r['payload_json'])['pipeline_binding']['error']
