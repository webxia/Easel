"""Real domain commands in isolated DB; no model/network/media generation."""
import json
import pytest
from tests.production.test_conversation import env, entry, turn, tool, raises, proposal
from easel.work_bridge import Identity
from easel.production.service import now, encode, row
from easel.production.catalog import CreativeCatalog
from easel.production.errors import ProductionError


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
    values={'plan_revision':created['plan_revision'],'plan_hash':created['plan_hash'],'services':[],'image_limit':0,'video_limit':0,'allow_ai':False}
    p=pipe(b,i,'offer',action='confirm',values=values,summary='按方案制作，不授权生成素材')
    repeated_question=pipe(b,i,'offer',action='confirm',values=values,summary='相同范围的不同说明')
    assert repeated_question['proposal_id']==p['proposal_id']
    raises('confirmation_required',lambda:pipe(b,i,'answer',proposal_id=p['proposal_id'],hash=p['hash'],user_quote='给我看看方案'))
    before=s.snapshot(d['work_id'])
    raises('proposal_already_offered',lambda:tool(b,i,'easel_work_update_brief',{'entries':[{'kind':'user_requirement','text':'给我看看方案','source_refs':['show']}]}))
    after=s.snapshot(d['work_id'])
    assert (after['revision'],after['current_plan_revision'])==(before['revision'],before['current_plan_revision'])
    b.end(Identity(**i))
    b,i,_=turn(s,c,seg,'就按这个方案制作',id='produce')
    repeated_question=pipe(b,i,'offer',action='confirm',values=values,summary='再次提及同一制作范围')
    assert repeated_question['already_proposed']
    assert (repeated_question['proposal_id'],repeated_question['hash'])==(p['proposal_id'],p['hash'])
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


def test_input_rights_and_original_audio_require_prior_dialogue_confirmation(env):
    from tests.production.test_conversation import attachment
    seed(env);s,c=env;seg=entry(c,profile_ref='one',kind='director_formation')
    a=attachment(s)
    b,i,_=turn(s,c,seg,'参考我上传的视频',attachments=[a])
    work=pipe(b,i,'draft',user_quote='参考我上传的视频',values={'title':'参考','input_text':'分析参考'})['work_id']
    raises('rights_confirmation_required',lambda:tool(b,i,'easel_work_register_inputs',{'attachment_id':a['id'],'original_audio':True}))
    p=pipe(b,i,'offer',action='input',values={'attachment_id':a['id'],'usage':'must_use','original_audio':True,'interval':{'start':1,'end':3},'rights_confirmed':True},summary='将clip.mp4用于本片，保留1到3秒原声，请确认本片使用权')
    raises('confirmation_required',lambda:pipe(b,i,'answer',proposal_id=p['proposal_id'],hash=p['hash'],user_quote='参考我上传的视频'))
    assert not s.snapshot(work)['inputs']
    b.end(Identity(**i));b,i,_=turn(s,c,seg,'确认，我有本片使用权，保留这段原声',id='rights')
    r=pipe(b,i,'answer',proposal_id=p['proposal_id'],hash=p['hash'],user_quote='确认，我有本片使用权，保留这段原声')
    assert pipe(b,i,'answer',proposal_id=p['proposal_id'],hash=p['hash'],user_quote='确认，我有本片使用权，保留这段原声')==r
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
    raises('stale_revision',lambda:pipe(b,i,'answer',proposal_id=p['proposal_id'],hash=p['hash'],user_quote='确认登记'))
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
    pipe(b,i,'answer',proposal_id=p['proposal_id'],hash=p['hash'],user_quote='确认保存')
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
    result=pipe(b,i,'answer',proposal_id=p['proposal_id'],hash=p['hash'],user_quote='同意使用所述模型整理方案')
    assert pipe(b,i,'answer',proposal_id=p['proposal_id'],hash=p['hash'],user_quote='同意使用所述模型整理方案')==result
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
    result=pipe(b,i,'answer',proposal_id=p['proposal_id'],hash=p['hash'],user_quote='同意授权并继续')
    assert result['run_id']==run['run_id']
    assert pipe(b,i,'answer',proposal_id=p['proposal_id'],hash=p['hash'],user_quote='同意授权并继续')==result
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
    raises('invalid_input',lambda:pipe(b,i,'answer',proposal_id=old['proposal_id'],hash=old['hash'],user_quote='重新授权'))
    p=pipe(b,i,**bad['next_action'])
    assert p['values']['payload']['services']==[MODEL_SERVICE]
    assert next(p for p in c.view('ui')['proposals'] if p['id']==old['proposal_id'])['state']=='stale'
    b.end(Identity(**i))
    b,i,_=turn(s,c,seg,'同意这次授权',id='repair-answer')
    result=pipe(b,i,'answer',proposal_id=p['proposal_id'],hash=p['hash'],user_quote='同意这次授权')
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
    raises('capability_unavailable' if changed=='model' else 'stale_revision',lambda:pipe(b,i,'answer',proposal_id=p['proposal_id'],hash=p['hash'],user_quote='同意授权'))
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
        pipe(b,i,'answer',proposal_id='shortened...',hash='fake',user_quote='确认之前已展示的内容')
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
    raises('confirmation_required',lambda:pipe(b,i,'answer',proposal_id=changed['proposal_id'],hash=changed['hash'],user_quote='增加一张生图'))
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
    nested={'proposal_id':p['proposal_id'],'hash':p['hash'],'user_quote':'做个视频'}
    raises('invalid_source',lambda:pipe(b,i,'answer',values=nested))
    nested['user_quote']='确认这条方案提案'
    raises('invalid_tool_arguments',lambda:pipe(b,i,'answer',values=nested,proposal_id='conflicting'))
    raises('invalid_tool_arguments',lambda:pipe(b,i,'answer',values={**nested,'services':[]}))
    result=pipe(b,i,'answer',values=nested)
    assert result['run_id']
    assert len(s.snapshot(d['work_id'])['runs'])==1
