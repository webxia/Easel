"""Real domain commands in isolated DB; no model/network/media generation."""
import json
import pytest
from tests.production.test_conversation import env, entry, turn, tool, raises, proposal
from easel.work_bridge import Identity
from easel.production.service import now, encode, row
from easel.production.catalog import CreativeCatalog
from easel.production.errors import ProductionError
from easel.production.planning import DRAFT_REVIEW_CONTEXT_VERSION


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


@pytest.mark.parametrize('mode', ['bind', 'draft'])
def test_pipeline_source_error_locates_root_quote_without_side_effects(env, mode):
    s,c=env;seg=entry(c,profile_ref='one')
    b,i,_=turn(s,c,seg,'做一条视频')
    for args in ({}, {'values':{'user_quote':'做一条视频'}}, {'user_quote':'助手同意'}):
        with pytest.raises(ProductionError) as error:
            pipe(b,i,mode,**args)
        assert error.value.code=='invalid_source'
        assert '顶层传user_quote' in error.value.user_message
    assert s.list_works()['items']==[]


def test_local_draft_and_plan_confirmation_are_separate(env):
    channel=seed(env);s,c=env;seg=entry(c,profile_ref='one',channel_id=channel,director_revision='v4',director_trial=True)
    b,i,_=turn(s,c,seg,'把今天的想法做视频')
    with pytest.raises(ProductionError) as error:
        pipe(b,i,'draft',user_quote='把今天的想法做视频',values={'title':'想法','input_text':'今天的想法','settings':{}})
    assert error.value.code == 'invalid_input'
    assert 'title和input_text' in error.value.user_message
    assert s.list_works()['items'] == []
    d=pipe(b,i,'draft',user_quote='把今天的想法做视频',values={'title':'想法','input_text':'今天的想法'})
    assert not s.snapshot(d['work_id'])['runs']
    p=pipe(b,i,'offer',action='plan',values={'request':'深入分析','services':[]},summary='整理完整方案')
    raises('confirmation_required',lambda:pipe(b,i,'answer',dismiss=False,proposal_id=p['proposal_id'],hash=p['hash'],user_quote='把今天的想法做视频'))
    b.end(Identity(**i))
    b,i,_=turn(s,c,seg,'同意整理方案',id='answer')
    result=pipe(b,i,'answer',dismiss=False,proposal_id=p['proposal_id'],hash=p['hash'],user_quote='同意整理方案')
    assert result['run_id']
    assert pipe(b,i,'answer',dismiss=False,proposal_id=p['proposal_id'],hash=p['hash'],user_quote='同意整理方案')==result
    assert len(s.snapshot(d['work_id'])['runs'])==1
    with s.store.connection() as conn:assert conn.execute('SELECT count(*) FROM operations').fetchone()[0]==0


def test_channel_save_from_user_reply_and_forbidden_source(env):
    s,c=env;seg=entry(c,profile_ref='one',kind='channel_create')
    b,i,_=turn(s,c,seg,'创建一个学习频道')
    p=proposal(s,c,seg,'channel_create',{'name':'学习频道','creative_basis':{'position':'学习','themes':'实践','audience':'普通人'}})
    b.end(Identity(**i))
    b,i,_=turn(s,c,seg,'保存这个频道',id='save')
    raises('invalid_source',lambda:pipe(b,i,'answer',dismiss=False,proposal_id=p['proposal_id'],hash=p['hash'],user_quote='助手说同意'))
    saved=pipe(b,i,'answer',dismiss=False,proposal_id=p['proposal_id'],hash=p['hash'],user_quote='保存这个频道')
    assert c.view('ui')['context']['channel_id']==saved['id']
    assert s.list_works()['items']==[]


def test_director_revision_then_style_confirm_without_acceptance(env):
    seed(env);s,c=env;seg=entry(c,profile_ref='one',kind='director_formation',director_revision='v4')
    b,i,_=turn(s,c,seg,'把节奏改松弛')
    with s.store.connection() as conn:rev=row(conn,'directors','director')['revision']
    p=proposal(s,c,seg,'director_revision',{'style':{'visual_style':'清晰','storytelling':'松弛'},'base_revision':rev})
    b.end(Identity(**i))
    b,i,_=turn(s,c,seg,'保存新风格',id='save')
    pipe(b,i,'answer',dismiss=False,proposal_id=p['proposal_id'],hash=p['hash'],user_quote='保存新风格')
    with s.store.connection() as conn:v=dict(conn.execute('SELECT * FROM director_revisions ORDER BY revision DESC').fetchone())
    assert v['revision']==5 and not v['style_confirmed'] and not v['accepted_at']
    p=pipe(b,i,'offer',action='director_style',values={'revision_id':v['id']},summary='确认新风格，仍待试片')
    b.end(Identity(**i))
    b,i,_=turn(s,c,seg,'确认这个风格',id='confirm')
    pipe(b,i,'answer',dismiss=False,proposal_id=p['proposal_id'],hash=p['hash'],user_quote='确认这个风格')
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
    raises('stale_revision',lambda:pipe(b,i,'answer',dismiss=False,proposal_id=first['proposal_id'],hash=first['hash'],user_quote='保存'))
    pipe(b,i,'answer',dismiss=False,proposal_id=second['proposal_id'],hash=second['hash'],user_quote='保存')


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
    values={'plan_revision':created['plan_revision'],'plan_hash':created['plan_hash'],'services':[],'image_limit':0,'video_limit':0,'allow_ai':False}
    p=pipe(b,i,'offer',action='confirm',values=values,summary='按方案制作，不授权生成素材')
    assert '待正式确认制作，尚未启动' in p['values']['summary']
    assert '明确同意本提案后才确认方案并启动制作' in p['values']['summary']
    assert s.snapshot(d['work_id'])['plans'][0]['confirmed_at'] is None
    assert not s.snapshot(d['work_id'])['runs']
    repeated_question=pipe(b,i,'offer',action='confirm',values=values,summary='相同范围的不同说明')
    assert repeated_question['proposal_id']==p['proposal_id']
    raises('confirmation_required',lambda:pipe(b,i,'answer',dismiss=False,proposal_id=p['proposal_id'],hash=p['hash'],user_quote='给我看看方案'))
    before=s.snapshot(d['work_id'])
    raises('proposal_already_offered',lambda:tool(b,i,'easel_work_update_brief',{'entries':[{'kind':'user_requirement','text':'给我看看方案','source_refs':['show']}]}))
    after=s.snapshot(d['work_id'])
    assert (after['revision'],after['current_plan_revision'])==(before['revision'],before['current_plan_revision'])
    b.end(Identity(**i))
    b,i,_=turn(s,c,seg,'就按这个方案制作',id='produce')
    repeated_question=pipe(b,i,'offer',action='confirm',values=values,summary='再次提及同一制作范围')
    assert repeated_question['already_proposed']
    assert (repeated_question['proposal_id'],repeated_question['hash'])==(p['proposal_id'],p['hash'])
    result=pipe(b,i,'answer',dismiss=False,proposal_id=p['proposal_id'],hash=p['hash'],user_quote='就按这个方案制作')
    b.end(Identity(**i));b,i,_=turn(s,c,seg,'就按这个方案制作',id='duplicate')
    repeated=pipe(b,i,'answer',dismiss=False,proposal_id=p['proposal_id'],hash=p['hash'],user_quote='就按这个方案制作')
    assert repeated['run_id']==result['run_id']
    snapshot=s.snapshot(d['work_id']);assert len(snapshot['runs'])==1
    assert snapshot['plans'][0]['confirmed_at'] is not None
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


def test_input_rights_and_original_audio_require_prior_dialogue_confirmation(env):
    from tests.production.test_conversation import attachment
    seed(env);s,c=env;seg=entry(c,profile_ref='one',kind='director_formation')
    a=attachment(s)
    b,i,_=turn(s,c,seg,'参考我上传的视频',attachments=[a])
    work=pipe(b,i,'draft',user_quote='参考我上传的视频',values={'title':'参考','input_text':'分析参考'})['work_id']
    raises('rights_confirmation_required',lambda:tool(b,i,'easel_work_register_inputs',{'attachment_id':a['id'],'original_audio':True}))
    p=pipe(b,i,'offer',action='input',values={'attachment_id':a['id'],'usage':'must_use','original_audio':True,'interval':{'start':1,'end':3},'rights_confirmed':True},summary='将clip.mp4用于本片，保留1到3秒原声，请确认本片使用权')
    raises('confirmation_required',lambda:pipe(b,i,'answer',dismiss=False,proposal_id=p['proposal_id'],hash=p['hash'],user_quote='参考我上传的视频'))
    assert not s.snapshot(work)['inputs']
    b.end(Identity(**i));b,i,_=turn(s,c,seg,'确认，我有本片使用权，保留这段原声',id='rights')
    r=pipe(b,i,'answer',dismiss=False,proposal_id=p['proposal_id'],hash=p['hash'],user_quote='确认，我有本片使用权，保留这段原声')
    assert pipe(b,i,'answer',dismiss=False,proposal_id=p['proposal_id'],hash=p['hash'],user_quote='确认，我有本片使用权，保留这段原声')==r
    snap=s.snapshot(work);assert len(snap['inputs'])==1 and not snap['runs']
    meta=json.loads(snap['inputs'][0]['metadata_json'])
    assert meta['original_audio'] and meta['interval']=={'start':1,'end':3}
    assert meta['source']['rights']['status']=='KNOWN'


def test_input_confirmation_rejects_foreign_or_changed_attachment(env):
    from tests.production.test_conversation import attachment
    seed(env);s,c=env;seg=entry(c,profile_ref='one',kind='director_formation')
    a=attachment(s);b,i,_=turn(s,c,seg,'登记素材',attachments=[a])
    work=pipe(b,i,'draft',user_quote='登记素材',values={'title':'参考','input_text':'参考'})['work_id']
    raises('attachment_not_bound',lambda:pipe(b,i,'offer',action='input',values={'attachment_id':'foreign'},summary='bad'))
    p=pipe(b,i,'offer',action='input',values={'attachment_id':a['id'],'original_audio':True},summary='保留原声但未声明使用权')
    b.end(Identity(**i));(s.outputs/a['path']).write_bytes(b'changed video')
    b,i,_=turn(s,c,seg,'确认登记',id='changed')
    raises('stale_revision',lambda:pipe(b,i,'answer',dismiss=False,proposal_id=p['proposal_id'],hash=p['hash'],user_quote='确认登记'))
    assert not s.snapshot(work)['inputs']


def test_partial_selection_reports_remaining_choice_and_channel_scope(env):
    channel=seed(env);s,c=env;seg=entry(c,profile_ref='one',channel_id=channel)
    b,i,_=turn(s,c,seg,'还缺什么')
    assert pipe(b,i,'pending')['missing_choices']==['director']
    raises('pipeline_mismatch',lambda:pipe(b,i,'offer',action='channel_director',values={'revision_id':'v4'},summary='bad'))
    b.end(Identity(**i))
    seg=entry(c,profile_ref='one',kind='channel_create',channel_id=channel)
    b,i,_=turn(s,c,seg,'修改频道',id='channel-edit')
    p=proposal(s,c,seg,'channel_defaults',{'name':'新频道名'},ref='channel-edit')
    b.end(Identity(**i));b,i,_=turn(s,c,seg,'确认保存',id='channel-save')
    pipe(b,i,'answer',dismiss=False,proposal_id=p['proposal_id'],hash=p['hash'],user_quote='确认保存')
    assert c.view('ui')['context']['channel']['name']=='新频道名'
    assert not s.list_works()['items']


@pytest.mark.parametrize('legacy',[True,False])
def test_plan_confirmation_runs_worker_with_bound_model_grant(env,legacy):
    import asyncio
    from tests.production.test_planning_runtime import Transport
    from easel.production.operations import OperationService
    from easel.production.planning import PlanningTasks
    from easel.production.worker import Worker
    s,c=env;channel=seed(env)
    with s.store.transaction() as conn:
        conn.execute('update channels set settings_json=? where id=?',(encode({'schema_version':1,'duration_seconds':3,'aspect_ratio':'16:9','audio_mode':'silent'}),channel))
    seg=entry(c,profile_ref='one',channel_id=channel,director_revision='v4',director_trial=True)
    b,i,_=turn(s,c,seg,'把今天的想法做视频')
    d=pipe(b,i,'draft',user_quote='把今天的想法做视频',values={'title':'想法','input_text':'今天的想法'})
    model={'provider':'direct-api','model':'fixture-model','mode':'structured'}
    p=tool(b,i,'easel_work_request_plan',{'request':'整理方案'}) if legacy else pipe(b,i,'offer',action='plan',values={'request':'整理方案'},summary='整理方案')
    values=p['values'] if legacy else p['values']['payload']
    assert values['services']==[model]
    with s.store.connection() as conn:
        assert conn.execute('select count(*) from authorization_grants').fetchone()[0]==0
        assert conn.execute('select count(*) from runs').fetchone()[0]==0
    b.end(Identity(**i))
    b,i,_=turn(s,c,seg,'同意使用所述模型整理方案',id='yes')
    result=pipe(b,i,'answer',dismiss=False,proposal_id=p['proposal_id'],hash=p['hash'],user_quote='同意使用所述模型整理方案')
    assert pipe(b,i,'answer',dismiss=False,proposal_id=p['proposal_id'],hash=p['hash'],user_quote='同意使用所述模型整理方案')==result
    b.end(Identity(**i))
    answer={'title':'想法','summary':'具体分析','script':'今天的想法','scenes':[{'id':'s1','purpose':'解释','visual':'书桌','narration':''}], 'settings':{'duration_seconds':3,'aspect_ratio':'16:9','audio_mode':'silent'}}
    transport=Transport(answer)
    planning=PlanningTasks(s,OperationService(s.store),transport,model,'fixture-version')
    worker=Worker(s.store,{'plan':planning.plan})
    assert asyncio.run(worker.run_once())
    snap=s.snapshot(d['work_id'])
    assert snap['state']=='awaiting_confirmation',[t['error_json'] for t in snap['tasks']]
    assert transport.calls==1
    assert len(snap['runs'])==1
    assert not asyncio.run(worker.run_once())


@pytest.mark.parametrize('change',['model','revoked','old'])
def test_plan_apply_never_adds_unshown_or_changed_authority(env,change):
    from tests.production.test_conversation import draft,apply
    from easel.production.service import digest
    s,c,seg,work=draft(env)
    model={'provider':'direct-api','model':'fixture-model','mode':'structured'}
    if change=='revoked':
        s.command('grant',{'purpose':'planning','services':[model]},command_id='grant',work_id=work,expected_revision=s.snapshot(work)['revision'])
    p=proposal(s,c,seg,'plan',{'request':'整理'})
    if change=='model':
        (s.outputs.parent/'.env').write_text('EASEL_DIRECT_API_BASE_URL=http://127.0.0.1:1/v1\nEASEL_DIRECT_API_MODEL=changed-model\n')
    elif change=='revoked':
        with s.store.transaction() as conn:conn.execute("update authorization_grants set revoked_at='revoked'")
    else:
        with s.store.transaction() as conn:
            body=json.loads(row(conn,'conversation_proposals',p['proposal_id'])['body_json']);body['values'].pop('services')
            p['hash']=digest(body)
            conn.execute('update conversation_proposals set body_json=?,body_hash=? where id=?',(encode(body),p['hash'],p['proposal_id']))
    raises('stale_revision' if change=='model' else 'permission_missing',lambda:apply(c,p))
    assert s.snapshot(work)['runs']==[]


def test_unconfigured_model_cannot_enqueue_conversation_plan(env):
    from tests.production.test_conversation import draft
    s,c,seg,work=draft(env)
    (s.outputs.parent/'.env').write_text('')
    raises('capability_unavailable',lambda:proposal(s,c,seg,'plan',{'request':'整理'}))
    assert s.snapshot(work)['runs']==[]


@pytest.mark.parametrize("minimal",[True,False])
def test_existing_permission_pause_is_granted_and_resumed_by_one_answer(env,minimal):
    from tests.production.test_conversation import draft
    s,c,seg,work=draft(env)
    run=s.command('plan',{},command_id='legacy-plan',work_id=work,expected_revision=s.snapshot(work)['revision'])
    task=s.snapshot(work)['tasks'][0]
    with s.store.transaction() as conn:
        conn.execute("update tasks set state='needs_decision',error_json=? where id=?",(encode({'code':'permission_missing'}),task['id']))
        conn.execute("update runs set state='needs_decision' where id=?",(run['run_id'],))
        conn.execute("update works set state='needs_decision' where id=?",(work,))
    b,i,_=turn(s,c,seg,'继续原任务',id='recover')
    values={'purpose':'planning'} if minimal else {'purpose':'planning','services':[{'provider':'direct-api','model':'fixture-model','mode':'structured'}],'decision_id':task['id']}
    p=pipe(b,i,'offer',action='grant',values=values,summary='授权模型并继续原整理方案任务')
    assert p['values']['payload']['decision_id']==task['id']
    assert p['values']['payload']['services']==[{'provider':'direct-api','model':'fixture-model','mode':'structured'}]
    assert '继续原整理方案' in p['values']['summary']
    b.end(Identity(**i))
    b,i,_=turn(s,c,seg,'同意授权并继续',id='grant-yes')
    result=pipe(b,i,'answer',dismiss=False,proposal_id=p['proposal_id'],hash=p['hash'],user_quote='同意授权并继续')
    assert result['run_id']==run['run_id']
    assert pipe(b,i,'answer',dismiss=False,proposal_id=p['proposal_id'],hash=p['hash'],user_quote='同意授权并继续')==result
    snap=s.snapshot(work)
    assert len(snap['runs'])==1 and snap['tasks'][0]['state']=='pending'
    with s.store.connection() as conn:
        assert conn.execute('select count(*) from authorization_grants').fetchone()[0]==1
        assert conn.execute('select count(*) from operations').fetchone()[0]==0


def test_interrupted_reply_reports_saved_permission_pause_without_replaying(env):
    from tests.production.test_conversation import draft
    from web.conversation_api import VideoChat
    s,c,seg,work=draft(env)
    s.command('plan',{},command_id='legacy-plan',work_id=work,expected_revision=s.snapshot(work)['revision'])
    with s.store.transaction() as conn:
        conn.execute("update tasks set state='needs_decision',error_json=? where work_id=?",(encode({'code':'permission_missing'}),work))
    before=s.snapshot(work)
    view,message=VideoChat.interrupted_result(s,'ui')
    assert view['work_id']==work and '本对话' in message and '不会自动重发' in message
    assert '制作工作台' not in message
    assert s.snapshot(work)==before


def test_stream_failure_preserves_turn_and_does_not_dispatch_twice(env,tmp_path,monkeypatch):
    import asyncio
    from tests.production.test_context_preparation import NoPressureRPC
    monkeypatch.setattr('easel.conversation_compaction.SessionRPC', NoPressureRPC)
    from types import SimpleNamespace
    from web.conversation_api import VideoChat
    import web.conversation_api as api
    s,c=env;seg=entry(c)
    requests=[];saved=[]
    class Response:
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        def raise_for_status(self):pass
        async def aiter_lines(self):
            yield 'data: '+json.dumps({'error':{'message':'private-provider-detail'}})
    class Client:
        def __init__(self,*args,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        def stream(self,*args,**kwargs):requests.append(1);return Response()
    monkeypatch.setattr(api.httpx,'AsyncClient',Client)
    chat=VideoChat(lambda:s,lambda _:tmp_path/'events.jsonl',lambda *args:saved.append(args),gateway_url='http://fixture',gateway_token='fixture',preflight=lambda *args:None)
    req=SimpleNamespace(sessionId='ui',turnId='stream-turn',videoSegmentId=seg,message='讨论',attachments=[])
    async def replay(*args):return 'replay'
    async def run():
        assert await chat.stream(req,replay)=='replay'
        await chat.tasks['ui']
        assert await chat.stream(req,replay)=='replay'
    asyncio.run(run())
    assert len(requests)==1
    events=[json.loads(line) for line in (tmp_path/'events.jsonl').read_text().splitlines()]
    assert events[-1]['event']=='error' and '回复中断' in events[-1]['data']
    assert 'private-provider-detail' not in str(events)
    assert any(e['event']=='work_card' for e in events)
    assert saved[0][-1]['clean_end'] is False
    with s.store.connection() as conn:
        assert conn.execute("select state from conversation_turns where id='stream-turn'").fetchone()[0]=='unknown'
        assert conn.execute('select count(*) from runs').fetchone()[0]==0


MODEL_SERVICE={'provider':'direct-api','model':'fixture-model','mode':'structured'}


@pytest.mark.parametrize('services',[
    {'item':'fixture-model'}, {'item':MODEL_SERVICE}, {**MODEL_SERVICE,'label':'创作模型'},
    {'item':{**MODEL_SERVICE,'label':'创作模型','service':'创作模型'}},
    [{**MODEL_SERVICE,'label':'创作模型'}], 'fixture-model', [],
])
def test_malformed_grant_is_rejected_before_becoming_a_question(env,services):
    from tests.production.test_conversation import draft
    s,c,seg,work=draft(env)
    b,i,_=turn(s,c,seg,'授权创作模型',id='grant-offer')
    before=c.view('ui')['proposals']
    with pytest.raises(ProductionError,match='services必须是数组'):
        pipe(b,i,'offer',action='grant',values={'purpose':'planning','services':services})
    assert c.view('ui')['proposals']==before
    with s.store.connection() as conn:
        assert conn.execute('select count(*) from authorization_grants').fetchone()[0]==0
        assert conn.execute('select count(*) from runs').fetchone()[0]==0


def test_legacy_bad_grant_is_unanswerable_and_replacement_uses_catalog(env):
    from tests.production.test_conversation import draft
    s,c,seg,work=draft(env)
    old=proposal(s,c,seg,'pipeline',{'action':'grant','payload':{'purpose':'planning','services':{'item':MODEL_SERVICE}},'summary':'旧错误提案','catalog_target':{}})
    b,i,_=turn(s,c,seg,'重新授权',id='repair-offer')
    pending=pipe(b,i,'pending')
    bad=next(p for p in pending['pending'] if p['id']==old['proposal_id'])
    assert bad['can_answer'] is False
    assert bad['next_action']=={'mode':'offer','action':'grant','values':{'purpose':'planning'}}
    raises('invalid_input',lambda:pipe(b,i,'answer',dismiss=False,proposal_id=old['proposal_id'],hash=old['hash'],user_quote='重新授权'))
    p=pipe(b,i,**bad['next_action'])
    assert p['values']['payload']['services']==[MODEL_SERVICE]
    assert next(p for p in c.view('ui')['proposals'] if p['id']==old['proposal_id'])['state']=='stale'
    b.end(Identity(**i))
    b,i,_=turn(s,c,seg,'同意这次授权',id='repair-answer')
    result=pipe(b,i,'answer',dismiss=False,proposal_id=p['proposal_id'],hash=p['hash'],user_quote='同意这次授权')
    assert result['grant_id']
    with s.store.connection() as conn:
        assert json.loads(conn.execute('select services_json from authorization_grants').fetchone()[0])==[MODEL_SERVICE]


@pytest.mark.parametrize('changed',['model','decision'])
def test_grant_rechecks_displayed_scope_before_saving(env,changed):
    from tests.production.test_conversation import draft
    s,c,seg,work=draft(env)
    if changed=='decision':
        s.command('plan',{},command_id='old-plan',work_id=work,expected_revision=s.snapshot(work)['revision'])
        with s.store.transaction() as conn:
            conn.execute("update tasks set state='needs_decision',error_json=?",(encode({'code':'permission_missing'}),))
            conn.execute("update runs set state='needs_decision'")
    b,i,_=turn(s,c,seg,'需要授权',id='offer-grant')
    p=pipe(b,i,'offer',action='grant',values={'purpose':'planning'})
    b.end(Identity(**i))
    if changed=='model':
        (s.outputs.parent/'.env').write_text('EASEL_DIRECT_API_BASE_URL=http://127.0.0.1:1/v1\nEASEL_DIRECT_API_MODEL=changed\n')
    else:
        with s.store.transaction() as conn:conn.execute("update tasks set error_json=?",(encode({'code':'result_unknown'}),))
    b,i,_=turn(s,c,seg,'同意授权',id='answer-grant')
    raises('capability_unavailable' if changed=='model' else 'stale_revision',lambda:pipe(b,i,'answer',dismiss=False,proposal_id=p['proposal_id'],hash=p['hash'],user_quote='同意授权'))
    with s.store.connection() as conn:assert conn.execute('select count(*) from authorization_grants').fetchone()[0]==0


def test_grant_with_forged_recovery_target_never_becomes_a_proposal(env):
    from tests.production.test_conversation import draft
    s,c,seg,work=draft(env)
    b,i,_=turn(s,c,seg,'需要授权',id='offer-grant')
    raises('stale_revision',lambda:pipe(b,i,'offer',action='grant',values={'purpose':'planning','decision_id':'foreign-task'}))


def test_automatic_recovery_binding_never_replays_unknown_operation(tmp_path):
    import asyncio
    from tests.production.test_planning_runtime import setup
    from easel.conversation import ConversationService
    s,work,transport,worker=setup(tmp_path,fail=True)
    (tmp_path/'.env').write_text('EASEL_DIRECT_API_BASE_URL=http://127.0.0.1:1/v1\nEASEL_DIRECT_API_MODEL=fixture\n')
    asyncio.run(worker.run_once())
    with s.store.transaction() as conn:
        assert conn.execute("select count(*) from operations where state='unknown'").fetchone()[0]==1
        conn.execute("update tasks set state='needs_decision',error_json=?",(encode({'code':'permission_missing'}),))
        before_grants=conn.execute('select count(*) from authorization_grants').fetchone()[0]
    c=ConversationService(s);seg=entry(c,work_id=work)
    b,i,_=turn(s,c,seg,'授权并继续',id='unknown-recovery')
    raises('result_unknown',lambda:pipe(b,i,'offer',action='grant',values={'purpose':'planning'}))
    assert transport.calls==1
    with s.store.connection() as conn:
        assert conn.execute('select count(*) from authorization_grants').fetchone()[0]==before_grants
        assert conn.execute("select count(*) from operations where state='unknown'").fetchone()[0]==1


def test_unconfigured_planning_grant_fails_before_question(env):
    from tests.production.test_conversation import draft
    s,c,seg,work=draft(env)
    (s.outputs.parent/'.env').write_text('')
    b,i,_=turn(s,c,seg,'授权',id='unconfigured-grant')
    raises('capability_unavailable',lambda:pipe(b,i,'offer',action='grant',values={'purpose':'planning'}))
    assert len(c.view('ui')['proposals'])==1


def test_reentering_current_pipeline_does_not_end_turn_or_lose_explicit_choices(env):
    channel=seed(env);s,c=env;seg=entry(c,profile_ref='one')
    b,i,_=turn(s,c,seg,'用频道甲和导演甲版本4做视频，不要重复让我选择')
    noop=pipe(b,i,'bind',user_quote='做视频',values={'kind':'new_work'})
    assert noop['already_bound'] and not noop['queued']
    assert noop['missing_choices']==['channel','director']
    assert pipe(b,i,'pending')['channels'][0]['id']==channel
    selected=pipe(b,i,'bind',user_quote='用频道甲和导演甲版本4',values={'kind':'new_work','channel_id':channel,'director_revision':'v4','director_trial':True})
    assert selected['queued']
    b.end(Identity(**i))
    view=c.view('ui');assert view['context']['channel_id']==channel
    assert view['context']['settings']['director_revision']=='v4'


def test_same_selected_pipeline_can_create_draft_in_current_turn(env):
    channel=seed(env);s,c=env;seg=entry(c,profile_ref='one',channel_id=channel,director_revision='v4',director_trial=True)
    b,i,_=turn(s,c,seg,'按已选频道导演继续做视频')
    result=pipe(b,i,'bind',user_quote='继续做视频',values={'kind':'new_work'})
    assert result['already_bound'] and not result['queued']
    draft=pipe(b,i,'draft',user_quote='按已选频道导演继续做视频',values={'title':'小事','input_text':'完成一件小事'})
    assert draft['work_id']
    assert not s.snapshot(draft['work_id'])['runs']


def test_invalid_answer_identity_guides_model_to_existing_pending_without_new_proposal(env):
    seed(env);s,c=env;seg=entry(c,profile_ref='one')
    b,i,_=turn(s,c,seg,'确认之前已展示的内容')
    before=c.view('ui')['proposals']
    with pytest.raises(ProductionError,match='重新读取pending') as error:
        pipe(b,i,'answer',dismiss=False,proposal_id='shortened...',hash='fake',user_quote='确认之前已展示的内容')
    assert error.value.code=='not_found'
    assert c.view('ui')['proposals']==before
    assert s.list_works()['items']==[]


def test_changed_brief_rejects_old_plan_at_offer_before_asking_again(env):
    channel=seed(env);s,c=env;seg=entry(c,profile_ref='one',channel_id=channel,director_revision='v4',director_trial=True)
    b,i,_=turn(s,c,seg,'做个视频')
    d=pipe(b,i,'draft',user_quote='做个视频',values={'title':'小事','input_text':'具体想法'})
    b.end(Identity(**i))
    plan={'title':'小事','summary':'分析一个问题','script':'这是具体分析。','scenes':[{'id':'s1','purpose':'解释','visual':'书桌','narration':''}],'settings':{'duration_seconds':1,'aspect_ratio':'16:9','audio_mode':'silent'}}
    created=s.command('plan',{'generate':False,'plan':plan},command_id='fixture-plan',work_id=d['work_id'],expected_revision=s.snapshot(d['work_id'])['revision'])
    b,i,_=turn(s,c,seg,'改成两件小事',id='change')
    tool(b,i,'easel_work_update_brief',{'entries':[{'kind':'user_requirement','text':'改成两件小事','source_refs':['change']}]})
    raises('stale_revision',lambda:pipe(b,i,'offer',action='confirm',values={'plan_revision':created['plan_revision'],'plan_hash':created['plan_hash'],'services':[]},summary='不能展示旧版为可制作方案'))
    assert s.snapshot(d['work_id'])['current_plan_revision'] is None
    with s.store.connection() as conn:
        assert not conn.execute("SELECT 1 FROM conversation_proposals WHERE kind='pipeline' AND json_extract(body_json,'$.values.action')='confirm'").fetchone()


def test_changed_production_scope_still_needs_a_new_human_answer(env):
    channel=seed(env);s,c=env;seg=entry(c,profile_ref='one',channel_id=channel,director_revision='v4',director_trial=True)
    b,i,_=turn(s,c,seg,'做个视频')
    d=pipe(b,i,'draft',user_quote='做个视频',values={'title':'小事','input_text':'具体想法'})
    b.end(Identity(**i))
    plan={'title':'小事','summary':'分析一个问题','script':'这是具体分析。','scenes':[{'id':'s1','purpose':'解释','visual':'书桌','narration':''}],'settings':{'duration_seconds':1,'aspect_ratio':'16:9','audio_mode':'silent'}}
    created=s.command('plan',{'generate':False,'plan':plan},command_id='fixture-plan',work_id=d['work_id'],expected_revision=s.snapshot(d['work_id'])['revision'])
    b,i,_=turn(s,c,seg,'看看方案',id='show')
    values={'plan_revision':created['plan_revision'],'plan_hash':created['plan_hash'],'services':[],'allow_ai':False,'image_limit':0,'video_limit':0}
    original=pipe(b,i,'offer',action='confirm',values=values,summary='原范围')
    b.end(Identity(**i));b,i,_=turn(s,c,seg,'增加一张生图',id='expanded')
    changed=pipe(b,i,'offer',action='confirm',values={**values,'allow_ai':True,'image_limit':1},summary='扩大范围')
    assert changed['proposal_id']!=original['proposal_id']
    raises('confirmation_required',lambda:pipe(b,i,'answer',dismiss=False,proposal_id=changed['proposal_id'],hash=changed['hash'],user_quote='增加一张生图'))
    assert not s.snapshot(d['work_id'])['runs']


def test_human_turn_is_explicit_and_follows_quoted_historical_context(env):
    s,c=env;seg=entry(c,profile_ref='one')
    b,i,_=turn(s,c,seg,'之前在等任务结果')
    b.end(Identity(**i))
    _,_,result=turn(s,c,seg,'确认当前修订提案',id='next-human')
    assert result['payload']['origin']=='user'
    assert result['prompt'].startswith('【真实用户新回合；不是宿主任务结果】')
    assert result['prompt'].index('【本轮用户原话；请回应这条新消息】')>result['prompt'].index('【服务端创作上下文与历史来源')
    assert result['prompt'].count('【本轮用户原话；请回应这条新消息】\n确认当前修订提案')==1


def test_nested_answer_identity_is_lossless_and_still_requires_current_human_quote(env):
    channel=seed(env);s,c=env;seg=entry(c,profile_ref='one',channel_id=channel,director_revision='v4',director_trial=True)
    b,i,_=turn(s,c,seg,'做个视频')
    d=pipe(b,i,'draft',user_quote='做个视频',values={'title':'小事','input_text':'具体想法'})
    p=pipe(b,i,'offer',action='plan',values={'request':'整理方案'},summary='仅用已展示的规划模型')
    b.end(Identity(**i));b,i,_=turn(s,c,seg,'确认这条方案提案',id='answer')
    nested={'dismiss':False,'proposal_id':p['proposal_id'],'hash':p['hash'],'user_quote':'做个视频'}
    raises('invalid_source',lambda:pipe(b,i,'answer',values=nested))
    nested['user_quote']='确认这条方案提案'
    raises('invalid_tool_arguments',lambda:pipe(b,i,'answer',values=nested,proposal_id='conflicting'))
    raises('invalid_tool_arguments',lambda:pipe(b,i,'answer',values={**nested,'services':[]}))
    result=pipe(b,i,'answer',values=nested)
    assert result['run_id']
    assert len(s.snapshot(d['work_id'])['runs'])==1


@pytest.mark.parametrize("binding", [{}, {"kind":"continue"}, {"kind":"new_work"}])
def test_rebinding_current_choices_keeps_work(env,binding):
    channel=seed(env);s,c=env
    seg=entry(c,profile_ref='one',channel_id=channel,director_revision='v4',director_trial=True)
    b,i,_=turn(s,c,seg,'创建作品')
    work=pipe(b,i,'draft',user_quote='创建作品',values={'title':'同名','input_text':'内容'})['work_id']
    b.end(Identity(**i));b,i,_=turn(s,c,seg,'继续原作品',id='rebind')
    pipe(b,i,'bind',user_quote='继续原作品',values=binding)
    b.end(Identity(**i));seg=c.view('ui')['segment_id']
    assert c.view('ui')['work_id']==work
    b,i,_=turn(s,c,seg,'继续',id='same-draft')
    assert pipe(b,i,'draft',user_quote='继续',values={'title':'同名','input_text':'内容'})['work_id']==work
    assert len(s.list_works()['items'])==1


def test_basis_types_rejected_before_offer(env):
    channel=seed(env);s,c=env
    seg=entry(c,profile_ref='one',channel_id=channel,director_revision='v4',director_trial=True)
    b,i,_=turn(s,c,seg,'创建作品')
    pipe(b,i,'draft',user_quote='创建作品',values={'title':'同名','input_text':'内容'})
    raises('invalid_input',lambda:pipe(b,i,'offer',action='basis',values={'settings':{'duration_seconds':'30'}}))


def test_confirm_binds_current_plan_and_model_before_answer(env):
    channel=seed(env);s,c=env
    seg=entry(c,profile_ref='one',channel_id=channel,director_revision='v4',director_trial=True)
    b,i,_=turn(s,c,seg,'创建作品')
    work=pipe(b,i,'draft',user_quote='创建作品',values={'title':'标题','input_text':'内容'})['work_id']
    b.end(Identity(**i))
    s.command('plan',{'generate':False,'plan':{'title':'标题','summary':'概要','script':'原稿','scenes':[{'id':'s1','purpose':'说明','visual':'桌面'}],'settings':{'duration_seconds':10,'audio_mode':'silent'}}},command_id='plan',work_id=work,expected_revision=s.snapshot(work)['revision'])
    b,i,_=turn(s,c,seg,'看看方案',id='offer')
    p=pipe(b,i,'offer',action='confirm',values={'allow_ai':False})
    state=pipe(b,i,'pending')
    payload=next(x for x in state['pending'] if x['id']==p['proposal_id'])['body']['values']['payload']
    assert payload['plan_hash']==state['current_plan']['plan_hash']
    assert payload['services']==[{'provider':'direct-api','model':'fixture-model','mode':'structured'}]
    assert 'IMAGE' not in str(payload['services'])
    detailed=pipe(b,i,'pending',values={'detail':'full'})
    assert detailed['current_plan']['plan']['script']=='原稿'
    current=next(plan for plan in detailed['work']['plans'] if plan['revision']==detailed['current_plan']['revision'])
    assert current['plan_ref']=='current_plan.plan' and 'plan' not in current
    assert s.snapshot(work)['plans'][0]['plan']['script']=='原稿'


def test_confirm_freezes_complete_services_and_never_expands_on_answer(env,monkeypatch):
    from easel.production import configuration
    channel=seed(env);s,c=env
    seg=entry(c,profile_ref='one',channel_id=channel,director_revision='v4',director_trial=True)
    b,i,_=turn(s,c,seg,'创建作品')
    work=pipe(b,i,'draft',user_quote='创建作品',values={'title':'标题','input_text':'内容'})['work_id']
    b.end(Identity(**i))
    s.command('plan',{'generate':False,'plan':{'title':'标题','summary':'概要','script':'原稿','scenes':[{'id':'s1','purpose':'说明','visual':'桌面'}],'settings':{'duration_seconds':10,'audio_mode':'music'}}},command_id='plan',work_id=work,expected_revision=s.snapshot(work)['revision'])
    services=[{'provider':'direct-api','model':'fixture-model','mode':'structured','available':True},
              {'provider':'pexels','model':'stock','mode':'search','available':True,'supports_auto_supply':True,'media_types':['video']},
              {'provider':'wikimedia_bgm','model':'stock','mode':'search','available':True,'supports_auto_supply':True,'media_types':['audio'],'audio_roles':['music']},
              {'provider':'minimax','model':'image-01','mode':'text_to_image','kind':'IMAGE','available':True}]
    monkeypatch.setattr(configuration,'capabilities',lambda root:{'services':services})
    b,i,_=turn(s,c,seg,'看看方案',id='offer')
    p=pipe(b,i,'offer',action='confirm',values={'allow_ai':False})
    assert {x['provider'] for x in p['values']['payload']['services']}=={'direct-api','pexels','wikimedia_bgm'}
    assert 'direct-api' in p['values']['summary']
    b.end(Identity(**i))
    services.append({'provider':'pixabay','model':'stock','mode':'search','available':True,'supports_auto_supply':True,'media_types':['video']})
    b,i,_=turn(s,c,seg,'确认',id='answer')
    raises('stale_revision',lambda:pipe(b,i,'answer',dismiss=False,proposal_id=p['proposal_id'],hash=p['hash'],user_quote='确认'))
    assert s.snapshot(work)['runs']==[]
    assert s.snapshot(work)['plans'][0]['confirmed_at'] is None


def test_cancel_offer_reports_work_scope_and_new_work_entry_still_works(env):
    channel=seed(env);s,c=env
    seg=entry(c,profile_ref='one',channel_id=channel,director_revision='v4',director_trial=True)
    b,i,_=turn(s,c,seg,'创建作品')
    work=pipe(b,i,'draft',user_quote='创建作品',values={'title':'标题','input_text':'内容'})['work_id']
    p=pipe(b,i,'offer',action='cancel',values={},summary='仅结束运行')
    assert '整部' in p['values']['summary'] and '撤销' in p['values']['summary']
    b.end(Identity(**i))
    seg=entry(c,profile_ref='one',channel_id=channel,director_revision='v4',director_trial=True)
    b,i,_=turn(s,c,seg,'另建作品',id='new')
    new=pipe(b,i,'draft',user_quote='另建作品',values={'title':'标题','input_text':'内容'})['work_id']
    assert new!=work
    assert len(s.list_works()['items'])==2


@pytest.mark.parametrize('allow_ai',[False,True])
@pytest.mark.parametrize('no_optional_audio',[False,True])
@pytest.mark.parametrize('narrow_sfx',[False,True])
def test_production_services_use_frozen_voice_and_ai_scope(env,monkeypatch,allow_ai,no_optional_audio,narrow_sfx):
    from types import SimpleNamespace
    from easel.production import configuration,voice as voice_module
    from easel.production.contracts import VoiceIdentity
    from easel.conversation_pipeline import production_values
    s,c=env
    w=s.command('create',{'title':'标题','input_text':'内容'},command_id='create')['work_id']
    voice=VoiceIdentity(provider='speech',model='fixed',voice_id='selected',engine='fixed')
    s.command('plan',{'generate':False,'plan':{'title':'标题','summary':'观点','script':'口播','scenes':[{'id':'s1','purpose':'说明','visual':'桌面'}],'settings':{'duration_seconds':10,'audio_mode':'voice','voice':voice.model_dump()},'constraints':['本片不使用背景音乐或可选音效'] if no_optional_audio else []}},command_id='plan',work_id=w,expected_revision=s.snapshot(w)['revision'])
    caps=[{'provider':'direct-api','model':'fixture-model','mode':'structured','available':True},
          {'provider':'speech','model':'fixed','mode':'speech','available':True},
          {'provider':'speech','model':'other','mode':'speech','available':True},
          {'provider':'wikimedia_sfx','model':'stock','mode':'search','available':True,'media_types':['audio'],'audio_roles':['sfx'],'supports_auto_supply':True},
          {'provider':'wikimedia_bgm','model':'stock','mode':'search','available':True,'media_types':['audio'],'audio_roles':['music'],'supports_auto_supply':True},
          {'provider':'minimax','model':'image-01','mode':'text_to_image','kind':'IMAGE','available':True}]
    monkeypatch.setattr(configuration,'capabilities',lambda root:{'services':caps})
    monkeypatch.setattr(voice_module,'configured_speech_configs',lambda config:[SimpleNamespace(voices=[SimpleNamespace(available=True,identity=voice)])])
    values={'allow_ai':allow_ai,'image_limit':2}
    if narrow_sfx:
        values['services']=[{'provider':'direct-api','model':'fixture-model','mode':'structured'},
                            {'provider':'speech','model':'fixed','mode':'speech'}]
    with s.store.connection() as conn:
        result=production_values(c,conn,{'work_id':w},values)
        applied=production_values(c,conn,{'work_id':w},result,applying=True)
    assert applied==result
    assert {x['model'] for x in result['services']}==({'fixture-model','fixed'} | ({'image-01'} if allow_ai else set()) | (set() if no_optional_audio or narrow_sfx else {'stock'}))
    assert 'wikimedia_bgm' not in {x['provider'] for x in result['services']}


def test_topic_only_cannot_bind_available_channel_and_director(env):
    channel=seed(env);s,c=env;seg=entry(c,profile_ref='one')
    quote='讨论吾日三省吾身，完整方案和制作等我确认'
    b,i,_=turn(s,c,seg,quote)
    p=pipe(b,i,'bind',user_quote=quote,values={'channel_id':channel,'director_revision':'v4','director_trial':True})
    assert p['selection_pending'] and not p['queued']
    assert c.view('ui')['context']['channel_id'] is None
    raises('confirmation_required',lambda:pipe(b,i,'answer',dismiss=False,proposal_id=p['proposal_id'],hash=p['hash'],user_quote=quote))
    b.end(Identity(**i))
    assert c.view('ui')['segment_id']==seg
    assert b.continue_handoff('ui','turn') is None
    assert not s.list_works()['items']


@pytest.mark.parametrize('answer',['就这两个','选第一组','频道甲和导演甲'])
def test_human_selects_shown_pair_binds_without_another_confirmation(env,answer):
    channel=seed(env);s,c=env;seg=entry(c,profile_ref='one')
    b,i,_=turn(s,c,seg,'讨论视频')
    values={'channel_id':channel,'director_revision':'v4','director_trial':True}
    p=pipe(b,i,'bind',user_quote='讨论视频',values=values)
    b.end(Identity(**i))
    b,i,_=turn(s,c,seg,answer,id='selection')
    result=pipe(b,i,'bind',user_quote=answer,values=values)
    assert result['queued'] and not result.get('selection_pending')
    assert pipe(b,i,'bind',user_quote=answer,values=values)==result
    b.end(Identity(**i))
    view=c.view('ui')
    assert view['context']['channel_id']==channel
    assert view['context']['settings']['director_revision']=='v4'
    assert not s.list_works()['items']


def test_rejected_selection_stays_unbound(env):
    channel=seed(env);s,c=env;seg=entry(c,profile_ref='one')
    b,i,_=turn(s,c,seg,'讨论视频')
    p=pipe(b,i,'bind',user_quote='讨论视频',values={'channel_id':channel})
    b.end(Identity(**i))
    b,i,_=turn(s,c,seg,'不要绑定',id='decline')
    result=pipe(b,i,'answer',proposal_id=p['proposal_id'],hash=p['hash'],user_quote='不要绑定',dismiss=True)
    assert result['dismissed'] and c.view('ui')['context']['channel_id'] is None


@pytest.mark.parametrize('code,visible',[('draft_review_failed',True),('plan_constraint_changed',False)])
def test_current_draft_failure_exposes_bounded_findings_not_raw_checkpoint(env,code,visible):
    import asyncio
    from easel.production.worker import Worker,TaskResult
    s,c=env;channel=seed(env)
    seg=entry(c,profile_ref='one',channel_id=channel,director_revision='v4',director_trial=True)
    b,i,_=turn(s,c,seg,'做视频')
    work=pipe(b,i,'draft',user_quote='做视频',values={'title':'本期','input_text':'讨论问题'})['work_id']
    b.end(Identity(**i))
    s.command('plan',{'request':'完整方案'},work_id=work,expected_revision=s.snapshot(work)['revision'],command_id='start')
    async def failed(ctx):
        with ctx.transaction() as conn:
            payload=json.loads(row(conn,'tasks',ctx.task_id)['payload_json'])
            payload['native_draft_checkpoint']={'source_operation_id':'known-native-receipt',
                'draft':{'private_marker':'full-draft-must-stay-private'},
                'review':{'findings':['场景与状态不符','长'*3000]+['其他']*12,'observations':['not-for-summary']}}
            conn.execute('UPDATE tasks SET payload_json=? WHERE id=?',(encode(payload),ctx.task_id))
        return TaskResult(state='needs_decision',work_state='needs_decision',
            error=ProductionError(code,'草稿未通过',requires_decision=True))
    asyncio.run(Worker(s.store,{'plan':failed}).run_once())
    b,i,_=turn(s,c,seg,'为什么没完成',id='explain')
    state=pipe(b,i,'pending')
    blocker=state['blockers'][0]
    assert ('draft_review' in blocker)==visible
    if visible:
        detail=blocker['draft_review']
        assert any(choice['action']=='resume' and choice['values']['decision_id']==s.snapshot(work)['tasks'][0]['id']
                   for choice in blocker['choices'])
        assert detail['findings'][0]=='场景与状态不符'
        assert len(detail['findings'])==8 and len(detail['findings'][1])==2000
        assert '不是新增用户要求' in detail['scope']
    assert 'full-draft-must-stay-private' not in encode(state)
    assert 'not-for-summary' not in encode(state)


@pytest.mark.parametrize('scope,code,expected',[('narration','invalid_model_output',True),('boards','invalid_model_output',False),('narration','result_unknown',False),(None,'invalid_model_output',False)])
def test_only_failed_narration_delta_has_existing_resume_option(scope,code,expected):
    from easel.conversation_pipeline import has_edit_resume
    assert has_edit_resume({'kind':'plan','error_json':encode({'code':code}),
                           'payload_json':encode({'revision_scope':scope})}) is expected


@pytest.mark.parametrize('version,code,source,expected',[
    (None,'draft_review_failed',True,True),
    (DRAFT_REVIEW_CONTEXT_VERSION,'draft_review_failed',True,False),
    ('current-draft-1','draft_review_failed',True,True),
    (None,'draft_review_failed',False,False),
    ('current-draft-1','draft_provenance_missing',True,True),
    (DRAFT_REVIEW_CONTEXT_VERSION,'draft_provenance_missing',True,False),
    ('current-draft-1','draft_provenance_missing',False,False),
    (None,'result_unknown',True,False),
    ('current-draft-2','command_conflict',True,True),
    ('current-draft-2','command_conflict',False,False)])
def test_native_draft_reaudit_resume_is_only_exposed_for_outdated_known_view(version,code,source,expected):
    from easel.conversation_pipeline import has_edit_resume
    checkpoint={'draft':{'script':'候选稿'},'review_context_version':version}
    if source:checkpoint['source_operation_id']='known-native-receipt'
    assert has_edit_resume({'kind':'plan','error_json':encode({'code':code}),
        'payload_json':encode({'native_draft_checkpoint':checkpoint})}) is expected


@pytest.mark.parametrize('updated_brief',[False,True])
def test_existing_plan_cannot_stage_a_first_plan_question_but_grant_is_independent(env,updated_brief):
    s,c=env;channel=seed(env)
    seg=entry(c,profile_ref='one',channel_id=channel,director_revision='v4',director_trial=True)
    b,i,_=turn(s,c,seg,'建立作品')
    work=pipe(b,i,'draft',user_quote='建立作品',values={'title':'本期','input_text':'一个问题'})['work_id']
    b.end(Identity(**i))
    s.command('plan',{'generate':False,'plan':{'title':'本期','summary':'概要','script':'原稿',
        'scenes':[{'id':'s1','purpose':'说明','visual':'设备'}],'settings':{'duration_seconds':10,'audio_mode':'silent'}}},
        command_id='frozen',work_id=work,expected_revision=s.snapshot(work)['revision'])
    b,i,_=turn(s,c,seg,'整篇重写，沿用现有范围，只出方案',id='rewrite')
    if updated_brief:
        tool(b,i,'easel_work_update_brief',{'entries':[{'kind':'user_requirement','text':'整篇重写，沿用现有范围，只出方案','source_refs':['rewrite']}]})
        assert s.snapshot(work)['current_plan_revision'] is None
    before=s.snapshot(work)
    raises('plan_revision_required',lambda:pipe(b,i,'offer',action='plan',values={'request':'整篇重写'},user_quote='整篇重写'))
    assert s.snapshot(work)==before
    assert not pipe(b,i,'pending')['pending']
    grant=pipe(b,i,'offer',action='grant',values={'purpose':'planning'})
    assert grant['values']['action']=='grant'
    assert s.snapshot(work)==before


@pytest.mark.parametrize('decision', ['omitted', None, 'false', 'true', 0, 1])
def test_answer_missing_or_coerced_decision_cannot_authorize_or_cancel_work(env, decision):
    channel=seed(env);s,c=env
    seg=entry(c,profile_ref='one',channel_id=channel,director_revision='v4',director_trial=True)
    b,i,_=turn(s,c,seg,'做个视频')
    d=pipe(b,i,'draft',user_quote='做个视频',values={'title':'小事','input_text':'具体想法'})
    p=pipe(b,i,'offer',action='plan',values={'request':'整理方案'},summary='只规划')
    b.end(Identity(**i))
    quote='先取消这条提案，只保留方案和作品，继续改稿，不制作。'
    b,i,_=turn(s,c,seg,quote,id='decline')
    before=s.snapshot(d['work_id'])
    args={'proposal_id':p['proposal_id'],'hash':p['hash'],'user_quote':quote}
    if decision!='omitted':args['dismiss']=decision
    raises('invalid_tool_arguments',lambda:pipe(b,i,'answer',**args))
    assert s.snapshot(d['work_id'])==before
    assert next(x for x in c.view('ui')['proposals'] if x['id']==p['proposal_id'])['state']=='proposed'
    result=pipe(b,i,'answer',**{**args,'dismiss':True})
    assert result['dismissed']
    assert s.snapshot(d['work_id'])==before
    assert next(x for x in c.view('ui')['proposals'] if x['id']==p['proposal_id'])['state']=='dismissed'


def test_nested_answer_must_also_supply_explicit_decision():
    from pydantic import ValidationError
    from easel.conversation_bridge import PipelineArgs
    with pytest.raises(ValidationError,match='explicit dismiss'):
        PipelineArgs(mode='answer',values={'proposal_id':'a'*32,'hash':'b'*64,'user_quote':'取消'})
    assert PipelineArgs(mode='answer',values={'dismiss':True}).dismiss is True
    assert PipelineArgs(mode='pending').mode=='pending'


def test_worker_receives_literal_human_revocations_even_when_summary_omits_them(env):
    from types import SimpleNamespace
    from easel.production.planning import PlanningTasks
    from easel.production.operations import OperationService
    s,c=env;channel=seed(env)
    seg=entry(c,profile_ref='one',channel_id=channel,director_revision='v4',director_trial=True)
    message='做完整方案。撤销杯子归位、纸张叠齐条件；不要图解，BGM和音效保留。'
    b,i,_=turn(s,c,seg,message)
    w=pipe(b,i,'draft',user_quote='做完整方案',values={'title':'真实要求','input_text':'一个小变化'})['work_id']
    question=pipe(b,i,'offer',action='plan',values={'request':'改成纯实拍'})
    scope=json.loads(question['values']['payload']['request'])
    assert scope=={'user_sources':[{'source_turn':'turn','text':message}],'agent_request':'改成纯实拍'}
    b.end(Identity(**i));b,i,_=turn(s,c,seg,'确认规划服务，只出方案',id='yes')
    result=pipe(b,i,'answer',dismiss=False,proposal_id=question['proposal_id'],hash=question['hash'],user_quote='确认规划服务，只出方案')
    snap=s.snapshot(w);task=snap['tasks'][0];payload=json.loads(task['payload_json'])
    actual=json.loads(payload['request'])
    assert actual['agent_request']==scope['agent_request']
    assert actual['user_sources']==[*scope['user_sources'],{'source_turn':'yes','text':'确认规划服务，只出方案'}]
    ctx=SimpleNamespace(work_id=w,run_id=result['run_id'],task_id=task['id'],plan_revision=None,payload=payload)
    view=PlanningTasks(s,OperationService(s.store),None,{'provider':'direct-api','model':'fixture-model','mode':'structured'},'fixture').context(ctx)
    assert message in view.brief and '改成纯实拍' in view.brief
    assert not snap['artifacts'] and len(snap['runs'])==1


def test_creative_source_capture_does_not_treat_task_events_as_human(env):
    s,c=env;channel=seed(env)
    seg=entry(c,profile_ref='one',channel_id=channel,director_revision='v4',director_trial=True)
    b,i,_=turn(s,c,seg,'只讨论，不规划')
    # A task result can stage a proposal, never manufacture a human source.
    with s.store.transaction() as conn:
        t=row(conn,'conversation_turns','turn');p=json.loads(t['payload_json']);p['origin']='task_result'
        conn.execute('UPDATE conversation_turns SET payload_json=? WHERE id=?',(encode(p),'turn'))
        q=c.proposal(conn,c.segment(conn,'ui',seg),'plan',{'request':'待讨论提案'},['turn'])
        body=json.loads(row(conn,'conversation_proposals',q['proposal_id'])['body_json'])
        assert body['values']['request']=='待讨论提案'
    assert not s.list_works()['items']


def test_creative_source_preserves_false_literals_and_rejects_size_overflow(env):
    s,c=env;seg=entry(c,profile_ref='one')
    text='不要图解。'+('原文不可省略。'*7000)
    b,i,_=turn(s,c,seg,text)
    with s.store.transaction() as conn:
        raises('invalid_input',lambda:c.proposal(conn,c.segment(conn,'ui',seg),'plan',{'request':'摘要'*40000},['turn']))
        assert conn.execute('SELECT count(*) FROM conversation_proposals').fetchone()[0]==0
    assert not s.list_works()['items']


def test_output_revision_receives_original_feedback_not_only_model_summary(env):
    from tests.production.test_conversation import output_fixture
    s,c=env
    work=s.command('create',{'title':'成片','input_text':'一件小事','profile_ref':'one'},command_id='revision-work')['work_id']
    output_fixture(s,work)
    channel=CreativeCatalog(s).command('channels','create',{'name':'频道','profile_ref':'one'},command_id='revision-channel')['id']
    seg=entry(c,profile_ref='one',channel_id=channel,director_revision='style',director_trial=True,work_id=work,kind='revise',output_id='out')
    text='撤销之前的图解许可，只用实拍；不要重配旁白，保留BGM和音效。'
    b,i,_=turn(s,c,seg,text)
    q=pipe(b,i,'offer',action='revise',values={'output_id':'out','feedback':'换画面','preserve_audio':True})
    scope=json.loads(q['values']['payload']['feedback'])
    assert scope['user_sources']==[{'source_turn':'turn','text':text}]
    assert scope['agent_request']=='换画面'
    b.end(Identity(**i));b,i,_=turn(s,c,seg,'同意这次修订',id='revision-yes')
    pipe(b,i,'answer',dismiss=False,proposal_id=q['proposal_id'],hash=q['hash'],user_quote='同意这次修订')
    task=next(t for t in s.snapshot(work)['tasks'] if t['kind']=='revise')
    payload=json.loads(task['payload_json'])
    with s.store.connection() as conn:
        assert json.loads(row(conn,'reviews',payload['review_id'])['feedback'])==scope
    assert payload['preserve_audio'] is True


def test_planning_answer_preserves_added_content_without_mutating_proposal_scope(env):
    channel=seed(env);s,c=env;seg=entry(c,profile_ref='one',channel_id=channel,director_revision='v4',director_trial=True)
    b,i,_=turn(s,c,seg,'做一个记录疑问的视频')
    d=pipe(b,i,'draft',user_quote='做一个记录疑问的视频',values={'title':'疑问','input_text':'记录疑问'})
    p=pipe(b,i,'offer',action='plan',values={'request':'记录疑问','services':[]},summary='只规划')
    with s.store.connection() as conn:before=dict(conn.execute('SELECT * FROM conversation_proposals WHERE id=?',(p['proposal_id'],)).fetchone())
    b.end(Identity(**i))
    message='确认规划；开头用“有些问题，我当时想不明白。”结尾用“先记在这里，过几天再看。”不制作。'
    b,i,_=turn(s,c,seg,message,id='mixed-answer')
    result=pipe(b,i,'answer',proposal_id=p['proposal_id'],hash=p['hash'],dismiss=False,user_quote=message)
    repeated=pipe(b,i,'answer',proposal_id=p['proposal_id'],hash=p['hash'],dismiss=False,user_quote=message)
    assert repeated==result
    snapshot=s.snapshot(d['work_id']);assert len(snapshot['runs'])==1
    assert all(t['kind']=='plan' for t in snapshot['tasks'])
    with s.store.connection() as conn:
        task=conn.execute("SELECT payload_json FROM tasks WHERE run_id=? AND kind='plan'",(result['run_id'],)).fetchone()
        request=json.loads(json.loads(task[0])['request'])
        assert request['agent_request']=='记录疑问'
        assert request['user_sources'][-1]=={'source_turn':'mixed-answer','text':message}
        after=dict(conn.execute('SELECT * FROM conversation_proposals WHERE id=?',(p['proposal_id'],)).fetchone())
        assert before['body_json']==after['body_json'] and before['body_hash']==after['body_hash']
        assert conn.execute('SELECT count(*) FROM operations').fetchone()[0]==0


def test_planning_answer_context_is_scoped_and_never_uses_task_events(env):
    from easel.conversation_pipeline import planning_answer_values
    s,c=env;seg=entry(c,profile_ref='one')
    b,i,_=turn(s,c,seg,'用户原话',id='source')
    with s.store.transaction() as conn:
        segment=c.segment(conn,'ui',seg);data={'request':'原提案','services':[]}
        assert planning_answer_values(conn,segment,data,'missing')==data
        other={**dict(segment),'id':'another-segment'}
        assert planning_answer_values(conn,other,data,'source')==data
        raw=json.loads(conn.execute('SELECT payload_json FROM conversation_turns WHERE id=?',('source',)).fetchone()[0])
        raw['origin']='task_result'
        conn.execute('UPDATE conversation_turns SET payload_json=? WHERE id=?',(encode(raw),'source'))
        assert planning_answer_values(conn,segment,data,'source')==data


@pytest.mark.parametrize('scope,preserve_audio',[('edit',True),('narration',False)])
def test_rendered_revision_explicit_target_does_not_require_preselected_output(env,scope,preserve_audio):
    from tests.production.test_conversation import output_fixture
    from pydantic import ValidationError
    s,c=env
    work=s.command('create',{'title':'成片','input_text':'已成片内容','profile_ref':'one'},command_id='film')['work_id']
    output_fixture(s,work)
    seg=entry(c,profile_ref='one',work_id=work)
    before=s.snapshot(work)
    b,i,_=turn(s,c,seg,'只提出修改范围，等我确认',id='explicit-output')
    with pytest.raises(ValidationError):
        tool(b,i,'easel_work_request_revision',{'feedback':'改末句'})
    q=pipe(b,i,'offer',action='revise',values={'output_id':'out','scope':scope,'preserve_audio':preserve_audio,'feedback':'只改指定部分'})
    assert q['requires_user_confirmation']
    values=q['values']['payload']
    assert values['output_id']=='out' and values['scope']==scope and values['preserve_audio'] is preserve_audio
    after=s.snapshot(work)
    for key in ['plans','runs','tasks','artifacts']:
        assert after[key]==before[key]
    with s.store.connection() as conn:
        assert conn.execute('SELECT count(*) FROM operations').fetchone()[0]==0


def test_retired_revision_proposal_cannot_be_created_or_executed(env):
    s,c=env;seg=entry(c,profile_ref='one');b,i,_=turn(s,c,seg,'展示改稿范围',id='retired-source')
    with s.store.transaction() as conn:
        segment=c.segment(conn,'ui',seg)
        raises('invalid_input',lambda:c.proposal(conn,segment,'revision',{'feedback':'旧入口'},['retired-source']))
        body={'values':{'feedback':'旧入口'},'source_refs':['retired-source'],'target':{},'work_id':None,'work_revision':None}
        conn.execute('INSERT INTO conversation_proposals(id,segment_id,kind,revision,body_json,body_hash,state,receipt_json,created_at) VALUES (?,?,?,?,?,?,?,?,?)',('retired',seg,'revision',1,encode(body),'hash','proposed',None,now()))
    b.end(Identity(**i))
    raises('invalid_input',lambda:c.apply('ui','retired','hash','no-old-execution'))
    assert s.list_works()['items']==[]


def test_planning_fee_scope_is_task_policy_not_one_invocation_and_keeps_identity(env):
    from easel.conversation_pipeline import planning_execution_scope
    channel=seed(env);s,c=env
    seg=entry(c,profile_ref='one',channel_id=channel,director_revision='v4',director_trial=True)
    b,i,_=turn(s,c,seg,'整理精确20秒的方案')
    work=pipe(b,i,'draft',user_quote='整理精确20秒的方案',values={'title':'20秒','input_text':'一个观察'})['work_id']
    values={'request':'只整理方案，保留完整旁白','duration_seconds':20}
    p=pipe(b,i,'offer',action='plan',values=values)
    scope=p['execution_scope']
    assert scope['execution_unit']=='planning_task' and scope['scope_kind']=='execution_policy_not_actual_usage'
    assert 'unit' not in scope and '固定计费单位' in scope['billing_basis']
    assert scope['service_count']==1 and scope['fixed_model_call_count'] is None
    assert scope['may_make_multiple_model_calls'] is True
    assert scope['includes_media_production'] is False
    assert '多次模型调用' in scope['fee_message'] and '不等于只调用或只计费一次' in scope['fee_message']
    with s.store.connection() as conn:
        stored=dict(conn.execute('SELECT * FROM conversation_proposals WHERE id=?',(p['proposal_id'],)).fetchone())
    assert 'execution_scope' not in json.loads(stored['body_json'])
    before=s.snapshot(work)
    for detail in ({},{'detail':'full'}):
        shown=next(x for x in pipe(b,i,'pending',values=detail)['pending'] if x['id']==p['proposal_id'])
        assert shown['execution_scope']==scope
        assert shown['hash']==p['hash'] and shown['body']==json.loads(stored['body_json'])
    again=pipe(b,i,'offer',action='plan',values=values)
    assert (again['proposal_id'],again['hash'])==(p['proposal_id'],p['hash'])
    assert again['execution_scope']==scope
    with s.store.connection() as conn:
        assert dict(conn.execute('SELECT * FROM conversation_proposals WHERE id=?',(p['proposal_id'],)).fetchone())==stored
    assert s.snapshot(work)==before
    assert before['runs']==[] and before['pending_operations']==[]
    assert planning_execution_scope('confirm',{}) is None


def test_full_context_returns_current_plan_once_without_losing_distinct_history():
    import copy
    from easel.conversation_pipeline import full_context
    current={'revision':2,'plan_hash':'current','confirmed_at':None,
             'plan':{'script':'全部真实口播','scenes':[{'id':'s1','visual':'实拍，不用图解'}],
                     'constraints':['BGM和音效都要','AI额度0','完整旁白不能截断'],
                     'settings':{'duration_seconds':20,'voice':{'voice_id':'fixed','speed':1}}}}
    historical={'revision':1,'plan_hash':'old','plan':{'script':'历史稿'}}
    inconsistent={**copy.deepcopy(current),'plan':{'script':'身份相同但内容不同，不能隐藏'}}
    source={'context':{'sources':[{'text':'用户原话','ref':'user'}]},'current_plan':current,
            'pending':[{'body':{'rights':'完整许可约束'}}],
            'work':{'plans':[historical,copy.deepcopy(current),inconsistent],
                    'tasks':[{'payload_json':'原记录'}],'artifacts':[{'kind':'output','checks':['原始检查']}]} }
    before=copy.deepcopy(source)
    view=full_context(source)
    assert view['current_plan']==current
    assert view['work']['plans'][0]==historical
    assert view['work']['plans'][1]['plan_ref']=='current_plan.plan'
    assert 'plan' not in view['work']['plans'][1]
    assert view['work']['plans'][2]==inconsistent
    assert view['context']==source['context'] and view['pending']==source['pending']
    assert view['work']['tasks']==source['work']['tasks']
    assert view['work']['artifacts']==source['work']['artifacts']
    assert source==before
    assert full_context(view)==view
    assert full_context({'current_plan':None,'work':{'plans':[]}})=={'current_plan':None,'work':{'plans':[]}}


def test_pending_and_context_refresh_within_turn_after_plan_finishes(env):
    channel=seed(env);service,c=env
    segment=entry(c,profile_ref='one',channel_id=channel,director_revision='v4',director_trial=True)
    b,i,_=turn(service,c,segment,'创建本期作品')
    work=pipe(b,i,'draft',user_quote='创建本期作品',values={'title':'本期','input_text':'真实输入'})['work_id']
    b.end(Identity(**i))
    b,i,_=turn(service,c,segment,'查看最新方案',id='read-fresh')
    before=pipe(b,i,'pending')
    context_before=tool(b,i,'easel_work_context',{})
    assert before['current_plan'] is None
    service.command('plan',{'generate':False,'plan':{'title':'本期','summary':'概要','script':'新稿',
        'scenes':[{'id':'s1','purpose':'讲述','visual':'桌面'}],
        'settings':{'duration_seconds':10,'audio_mode':'silent'}}},command_id='offline-plan',
        work_id=work,expected_revision=service.snapshot(work)['revision'])
    after=pipe(b,i,'pending')
    context_after=tool(b,i,'easel_work_context',{})
    assert after['current_plan']['revision']==1
    assert context_after['work']['current_plan_revision']==1
    assert context_before['work']['current_plan_revision'] is None
    compact=pipe(b,i,'pending',values={'detail':'plan'})
    complete=pipe(b,i,'pending',values={'detail':'full'})
    assert compact['current_plan']['plan_hash']==complete['current_plan']['plan_hash']
    assert compact['current_plan']['plan']['script']=='新稿'
    for field,value in compact['current_plan']['plan'].items():
        assert value==complete['current_plan']['plan'][field]
    assert 'conversation_basis' not in compact['current_plan']['plan']
    assert 'profile_snapshot' not in compact['current_plan']['plan']
    assert 'context' not in compact and 'operation_guide' not in compact
    assert compact['work']['state']==service.snapshot(work)['state']
    assert service.snapshot(work)['plans'][0]['plan']==complete['current_plan']['plan']
