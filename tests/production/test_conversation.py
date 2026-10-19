"""A2–A4 offline user journeys and adversarial recovery. No user DB or providers."""
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from easel.production.store import Store
from easel.production.service import WorkService, now, encode, row
from easel.production.errors import ProductionError
from easel.production.catalog import CreativeCatalog
from easel.conversation import ConversationService
from easel.conversation_bridge import PersistentWorkToolBridge, PersistentCall, PersistentDispatch
from easel.work_bridge import Claim, Identity
from web.conversation_api import create_router, create_internal_router
from web.production_api import create_router as production_router, production_error_handler


@pytest.fixture
def env(tmp_path):
    store=Store(tmp_path/'outputs/_production/db.sqlite3');store.initialize()
    service=WorkService(store,outputs=tmp_path/'outputs',profiles=tmp_path/'profiles')
    (tmp_path/'.env').write_text('EASEL_DIRECT_API_BASE_URL=http://127.0.0.1:1/v1\nEASEL_DIRECT_API_MODEL=fixture-model\n')
    for name in ('one','two'):
        root=service.profiles/name;root.mkdir(parents=True)
        for file in ('identity','style','audience','platforms','preferences','memory'):(root/(file+'.md')).write_text(name+' '+file+'\n')
    return service,ConversationService(service)


def entry(c,session='ui',**values):return c.enter(session,values,'enter_'+session+'_'+str(len(c.service.list_works()['items']))+hashlib.sha256(encode(values).encode()).hexdigest()[:12])['segment_id']

def turn(service,c,segment,message='请做一条克制的视频',id='turn',attachments=None):
    bridge=PersistentWorkToolBridge(service)
    result=bridge.reserve(ui_session='ui',turn_id=id,segment_id=segment,message=message,attachments=attachments or [])
    identity={'agent_id':'easel-video','session_key':result['payload']['session_key'],'session_id':'native-'+segment,'run_id':'run-'+id}
    bridge.claim(Claim(**identity,prompt=result['prompt']))
    return bridge,identity,result


def tool(bridge,identity,name,params,call='call'):
    request=PersistentCall(**identity,tool_call_id=call,tool=name,params=params)
    ticket=bridge.prepare(request)['ticket']
    return bridge.dispatch(PersistentDispatch(**request.model_dump(),ticket=ticket))


def proposal(service,c,segment,kind,values,ref='turn'):
    with service.store.transaction() as conn:return c.proposal(conn,c.segment(conn,'ui',segment),kind,values,[ref])


def apply(c,result,key=None):
    return c.apply('ui',result['proposal_id'],result['hash'],key or 'apply_'+result['proposal_id'])


def draft(env):
    service,c=env;segment=entry(c,profile_ref='one')
    bridge,identity,_=turn(service,c,segment)
    p=tool(bridge,identity,'easel_work_create_draft',{'title':'克制的经历','input_text':'我第一次创业的真实经历'})
    bridge.end(Identity(**identity));work=apply(c,p)['work_id']
    return service,c,segment,work


def raises(code,fn):
    with pytest.raises(ProductionError) as e:fn()
    assert e.value.code==code


def test_discussion_proposals_do_not_start_production_and_draft_is_exactly_once(env):
    service,c=env;segment=entry(c)
    bridge,identity,_=turn(service,c,segment,'先讨论，并不开始制作')
    p=tool(bridge,identity,'easel_work_create_draft',{'title':'内容','input_text':'主题'})
    assert service.list_works()['items']==[]
    raises('invocation_pending',lambda:apply(c,p))
    bridge.end(Identity(**identity))
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(lambda _:apply(c,p),range(8)))
    assert len({r['work_id'] for r in results})==1
    assert c.view('ui')['work_id']==results[0]['work_id']
    snapshot=service.snapshot(results[0]['work_id']);assert snapshot['runs']==[]
    assert c.apply('ui',p['proposal_id'],p['hash'],'another-click')['work_id']==snapshot['id']


def test_process_restart_tool_tickets_results_and_turn_conflict(env):
    service,c=env;segment=entry(c)
    bridge,identity,result=turn(service,c,segment)
    request=PersistentCall(**identity,tool_call_id='c1',tool='easel_work_create_draft',params={'title':'one','input_text':'story'})
    ticket=bridge.prepare(request)['ticket']
    rebuilt=PersistentWorkToolBridge(service)
    first=rebuilt.dispatch(PersistentDispatch(**request.model_dump(),ticket=ticket))
    second=tool(rebuilt,identity,request.tool,request.params,'different-call-id')
    assert second==first
    retry=rebuilt.reserve(ui_session='ui',turn_id='turn',segment_id=segment,message='请做一条克制的视频',attachments=[])
    assert not retry['new']
    raises('turn_conflict',lambda:rebuilt.reserve(ui_session='ui',turn_id='turn',segment_id=segment,message='different',attachments=[]))
    raises('invocation_pending',lambda:rebuilt.reserve(ui_session='ui',turn_id='later',segment_id=segment,message='new',attachments=[]))
    assert result['payload']['session_key']==retry['payload']['session_key']


def test_unknown_delivery_never_resent_or_released_until_native_end(env):
    service,c=env;segment=entry(c);bridge,identity,_=turn(service,c,segment)
    bridge.delivery('turn','unknown','partial reply')
    raises('invocation_pending',lambda:entry(c,profile_ref='two'))
    raises('binding_mismatch',lambda:tool(bridge,identity,'easel_work_context',{}))
    bridge.end(Identity(**identity))
    assert entry(c,profile_ref='two')!=segment


def test_cross_work_profile_native_transcripts_isolated_and_old_cards_stale(env):
    service,c,old,work=draft(env)
    new=entry(c,profile_ref='two')
    bridge,identity,result=turn(service,c,new,'SECOND_PROFILE_SENTINEL',id='second')
    assert identity['session_key']!='agent:easel-video:'+old
    assert '第一次创业' not in result['prompt'] and 'one identity' not in result['prompt'] and 'two identity' in result['prompt']
    bridge.end(Identity(**identity))
    raises('stale_revision',lambda:PersistentWorkToolBridge(service).reserve(ui_session='ui',turn_id='late',segment_id=old,message='late',attachments=[]))
    assert c.view('ui')['work_id'] is None
    recovered=entry(c,work_id=work)
    assert recovered!=new


def test_multiturn_sourced_brief_frozen_in_plan_request_and_no_fabricated_requirements(env):
    service,c,segment,work=draft(env)
    b,i,_=turn(service,c,segment,'不要改动真实经历，字幕简洁',id='t2')
    raises('invalid_source',lambda:tool(b,i,'easel_work_update_brief',{'entries':[{'kind':'user_requirement','text':'用户赚了一百万','source_refs':['t2']}]}))
    result=tool(b,i,'easel_work_update_brief',{'entries':[{'kind':'user_requirement','text':'不要改动真实经历','source_refs':['t2']},{'kind':'suggestion','text':'用留白体现克制','source_refs':['turn','t2']}]})
    p=tool(b,i,'easel_work_request_plan',{'request':'按上面整理'})
    assert service.snapshot(work)['runs']==[]
    b.end(Identity(**i));apply(c,p,'plan')
    snapshot=service.snapshot(work)
    assert len(snapshot['runs'])==1
    with service.store.connection() as conn:
        task=conn.execute("SELECT payload_json FROM tasks WHERE work_id=?",(work,)).fetchone()
        basis=json.loads(task[0])['creation_basis'];assert basis['conversation_brief']['hash']==result['brief_hash']
        assert basis['conversation_brief']['body']['entries'][1]['kind']=='suggestion'
        assert conn.execute('SELECT count(*) FROM operations').fetchone()[0]==0
        assert conn.execute('SELECT count(*) FROM authorization_grants').fetchone()[0]==1


def attachment(service,session='ui'):
    scope=hashlib.sha256(session.encode()).hexdigest()[:20];rel=f'_inbox/{scope}/batch/clip.mp4'
    path=service.outputs/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'synthetic video')
    return {'id':hashlib.sha256((scope+'\0'+rel).encode()).hexdigest()[:24],'name':'clip.mp4','path':rel}


def test_legit_new_conversation_upload_and_original_rights_not_minted_by_model(env):
    service,c,_,work=draft(env)
    with service.store.transaction() as conn:capture=c.segment(conn,'ui');conn.execute("UPDATE conversation_turns SET state='ended'")
    # Same UI returns to another native segment, attachment belongs to the linked UI rather than original native UUID.
    seg=entry(c,work_id=work)
    a=attachment(service)
    b,i,_=turn(service,c,seg,'参考这个视频',id='upload',attachments=[a])
    raises('rights_confirmation_required',lambda:tool(b,i,'easel_work_register_inputs',{'attachment_id':a['id'],'original_audio':True}))
    result=tool(b,i,'easel_work_register_inputs',{'attachment_id':a['id'],'usage':'reference'})
    assert result['input_id'] in [v['id'] for v in service.snapshot(work)['inputs']]
    assert tool(b,i,'easel_work_register_inputs',{'attachment_id':a['id'],'usage':'reference'},'another-id')==result
    b.end(Identity(**i))
    # A genuinely new, explicitly linked local UI session can provide its own attachment.
    new=c.enter('linked',{'work_id':work},'link')['segment_id'];assert new
    a2=attachment(service,'linked');rev=service.snapshot(work)['revision']
    service.command('input',{'session_id':'linked','attachment':a2},command_id='new-input',work_id=work,expected_revision=rev)
    raises('permission_missing',lambda:service.command('input',{'session_id':'foreign','attachment':a2},command_id='bad',work_id=work,expected_revision=service.snapshot(work)['revision']))


@pytest.mark.parametrize('malicious',[{'id':'fake','name':'x','path':'/etc/passwd'},{'id':'fake','name':'x','path':'_inbox/other/batch/clip.mp4'}])
def test_prework_upload_handles_validated(env,malicious):
    service,c=env;seg=entry(c)
    raises('permission_missing',lambda:turn(service,c,seg,attachments=[malicious]))


def test_late_native_tools_revoked_even_after_new_turn_and_deleted_chat(env):
    service,c,seg,work=draft(env)
    b,i,_=turn(service,c,seg,'修改建议',id='t2')
    req=PersistentCall(**i,tool_call_id='late',tool='easel_work_context',params={});ticket=b.prepare(req)['ticket']
    c.revoke('ui')
    raises('binding_mismatch',lambda:b.dispatch(PersistentDispatch(**req.model_dump(),ticket=ticket)))
    b.end(Identity(**i))
    assert service.snapshot(work)['input_text']=='我第一次创业的真实经历'
    with service.store.connection() as conn:
        payload=json.loads(row(conn,'conversation_turns','t2')['payload_json'])
        assert 'message' not in payload and 'answer' not in payload
        assert conn.execute('SELECT count(*) FROM work_briefs WHERE work_id=?',(work,)).fetchone()[0]==1


def test_channel_create_without_work_persists_semantic_basis_and_once_only(env):
    service,c=env;seg=entry(c,profile_ref='one');b,i,_=turn(service,c,seg,'建一个分享创业经历的频道')
    p=tool(b,i,'easel_work_propose',{'kind':'channel_create','values':{'name':'创业笔记','creative_basis':{'position':'真实经历','themes':'创业','audience':'创业者'}},'source_refs':['turn']})
    b.end(Identity(**i));result=apply(c,p)
    assert apply(c,p)==result
    channels=CreativeCatalog(service).list('channels');assert len(channels)==1
    assert channels[0]['creative_basis']['position']=='真实经历' and channels[0]['settings']=={'schema_version':1}
    assert service.list_works()['items']==[]
    assert c.view('ui')['context']['channel_id']==result['id']


def test_channel_save_without_profile_rejected_and_old_proposal_invalidated(env):
    service,c=env;seg=entry(c);b,i,_=turn(service,c,seg)
    old=proposal(service,c,seg,'channel_create',{'name':'old'})
    new=proposal(service,c,seg,'channel_create',{'name':'new'})
    b.end(Identity(**i))
    raises('stale_revision',lambda:apply(c,old))
    raises('invalid_input',lambda:apply(c,new))
    assert CreativeCatalog(service).list('channels')==[]


def test_profile_save_is_opt_in_idempotent_and_conflict_does_not_overwrite(env):
    service,c,seg,_=draft(env);b,i,_=turn(service,c,seg,'以后字幕保持简洁',id='save')
    path=service.profiles/'one/preferences.md';before=path.read_text();checksum=hashlib.sha256(before.encode()).hexdigest()
    values={'file':'preferences','before_hash':checksum,'after':before+'\n字幕保持简洁\n','entries':['字幕保持简洁']}
    p=proposal(service,c,seg,'profile',values,'save');b.end(Identity(**i))
    assert path.read_text()==before
    result=apply(c,p);assert apply(c,p)==result
    assert path.read_text().count('字幕保持简洁')==1
    b,i,_=turn(service,c,seg,'再保存一个偏好',id='save2')
    p2=proposal(service,c,seg,'profile',{**values,'after':values['after']+'避免花字','entries':['避免花字'],'before_hash':result['after_hash']},'save2');b.end(Identity(**i))
    path.write_text(path.read_text()+'手工新增\n')
    raises('stale_revision',lambda:apply(c,p2,'save2'))
    assert '手工新增' in path.read_text() and '避免花字' not in path.read_text()


def test_profile_save_recovers_file_written_before_sqlite_receipt(env):
    service,c,seg,_=draft(env);b,i,_=turn(service,c,seg,'以后保持留白',id='save')
    path=service.profiles/'one/style.md';before=path.read_text();after=before+'\n保持留白\n'
    p=proposal(service,c,seg,'profile',{'file':'style','before_hash':hashlib.sha256(before.encode()).hexdigest(),'after':after,'entries':['保持留白']},'save')
    b.end(Identity(**i));path.write_text(after) # simulate only filesystem side committed
    assert apply(c,p)['after_hash']==hashlib.sha256(after.encode()).hexdigest()
    assert path.read_text()==after


def test_rejected_learning_and_cross_segment_source_do_not_write(env):
    service,c,seg,_=draft(env);b,i,_=turn(service,c,seg,'不要记住本片临时要求',id='feedback')
    p=proposal(service,c,seg,'profile',{'file':'memory','before_hash':'x','after':'x','entries':['x']},'feedback');b.end(Identity(**i))
    c.apply('ui',p['proposal_id'],p['hash'],'dismiss',dismiss=True)
    assert (service.profiles/'one/memory.md').read_text()=='one memory\n'
    other=entry(c,profile_ref='two')
    with service.store.transaction() as conn:
        raises('invalid_source',lambda:c.proposal(conn,c.segment(conn,'ui',other),'profile',{},['feedback']))


def test_router_independent_credential_and_card_hash_guard(env):
    service,c=env;app=FastAPI();app.add_exception_handler(ProductionError,production_error_handler)
    app.include_router(create_router(lambda:service));app.include_router(create_internal_router(lambda:service,lambda:'test-credential-long-enough-32'));app.include_router(production_router(lambda:service));client=TestClient(app)
    sid=client.post('/api/chat/video/ui/enter',json={'command_id':'e','entry':{}}).json()['segment_id']
    b,i,_=turn(service,c,sid)
    p=tool(b,i,'easel_work_create_draft',{'title':'test','input_text':'test'});b.end(Identity(**i))
    assert client.post('/api/chat/work-tools/claim',json={**i,'prompt':'bad'}).status_code==401
    assert client.post('/api/chat/work-tools/accept',json={}).status_code==404
    assert client.post('/api/chat/video/ui/proposals/'+p['proposal_id']+'/apply',json={'command_id':'a','hash':'bad'}).status_code==409
    assert client.post('/api/chat/video/ui/proposals/'+p['proposal_id']+'/apply',json={'command_id':'a','hash':p['hash']}).status_code==200


def test_explicit_fork_settings_no_grants_and_original_unchanged(env):
    service,c,seg,work=draft(env)
    source=service.snapshot(work);service.command('basis',{'settings':{'duration_seconds':45,'subtitles':{'enabled':True,'font':'default','size':54,'color':'#FFFFFF','outline':'#000000','background':'transparent','position':'bottom'}}},command_id='settings',work_id=work,expected_revision=source['revision'])
    source=service.snapshot(work)
    fork=service.command('fork',{'title':'不同主题','input_text':'new','session_id':'new','inherit_settings':['subtitles','duration_seconds']},command_id='fork',work_id=work,expected_revision=source['revision'])
    new=service.snapshot(fork['work_id']);assert new['settings']['duration_seconds']==45 and new['settings']['subtitles']['size']==54
    assert service.snapshot(work)==source
    with service.store.connection() as conn:assert conn.execute('SELECT count(*) FROM authorization_grants WHERE work_id=?',(new['id'],)).fetchone()[0]==0


def test_director_reference_analysis_is_one_task_and_reanalysis_preserves_existing_evidence(env):
    service,c,seg,work=draft(env);a=attachment(service)
    snap=service.snapshot(work)
    input=service.command('input',{'session_id':'ui','attachment':a},command_id='reference',work_id=work,expected_revision=snap['revision'])
    b,i,_=turn(service,c,seg,'把这条参考形成导演',id='director')
    p=proposal(service,c,seg,'director_formation',{'name':'克制导演','reference_input_ids':[input['input_id']]},'director')
    b.end(Identity(**i));first=apply(c,p);assert apply(c,p)==first
    assert len(service.snapshot(work)['runs'])==1
    with service.store.connection() as conn:
        task=conn.execute('SELECT * FROM tasks WHERE run_id=?',(first['run_id'],)).fetchone()
        assert task['kind']=='analyze_director' and json.loads(task['payload_json'])['reference_input_ids']==[input['input_id']]
        assert conn.execute('SELECT count(*) FROM operations').fetchone()[0]==0
    # Simulate completion of an offline analysis, keeping the existing evidence immutable.
    with service.store.transaction() as conn:
        conn.execute("UPDATE runs SET state='succeeded' WHERE id=?",(first['run_id'],))
        conn.execute("UPDATE tasks SET state='succeeded' WHERE run_id=?",(first['run_id'],))
        conn.execute("INSERT INTO director_revisions(id,director_id,revision,style_json,evidence_json,created_at) VALUES ('v1',?,1,?,?,?)",(first['id'],encode({'schema_version':1,'visual_style':'克制','storytelling':'留白'}),encode([{'input_id':input['input_id'],'digest':'old'}]),now()))
    before=CreativeCatalog(service).list('directors')[0]
    result=CreativeCatalog(service).command('directors','analyze',{'work_id':work,'work_revision':service.snapshot(work)['revision'],'reference_input_ids':[input['input_id']]},command_id='reanalyze',id=first['id'],expected_revision=before['revision'])
    assert result['id']==first['id'] and len(service.snapshot(work)['runs'])==2
    assert CreativeCatalog(service).list('directors')[0]['versions']==before['versions']


def output_fixture(service,work,*,style=True):
    """Synthetic checked output for acceptance guard tests, never production evidence."""
    with service.store.transaction() as conn:
        conn.execute("INSERT INTO directors(id,name,created_at,updated_at) VALUES ('director','D',?,?)",(now(),now()))
        conn.execute("INSERT INTO director_revisions(id,director_id,revision,style_json,evidence_json,style_confirmed,created_at) VALUES ('style','director',1,?,?,1,?)",(encode({'schema_version':1,'visual_style':'静','storytelling':'简'}),encode([{'source':'fixture'}]),now()))
    snap=service.snapshot(work)
    if style:
        service.command('basis',{'settings':{'director_revision':'style','director_trial':True}},command_id='basis',work_id=work,expected_revision=snap['revision'])
    snap=service.snapshot(work)
    plan={'title':'fixture','summary':'test','script':'test','scenes':[{'id':'s1','purpose':'test','visual':'blue','narration':''}],'settings':{'duration_seconds':1,'aspect_ratio':'16:9','audio_mode':'silent'}}
    staged=service.command('plan',{'generate':False,'plan':plan},command_id='p',work_id=work,expected_revision=snap['revision'])
    confirmed=service.command('confirm',{'plan_revision':staged['plan_revision'],'plan_hash':staged['plan_hash']},command_id='confirm',work_id=work,expected_revision=staged['revision'])
    path=service.outputs/'works'/work/'test.mp4';path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'local-fixture-output')
    checksum=service._file_hash(path)
    with service.store.transaction() as conn:
        conn.execute("UPDATE runs SET state='succeeded' WHERE id=?",(confirmed['run_id'],));conn.execute("UPDATE tasks SET state='succeeded' WHERE run_id=?",(confirmed['run_id'],));conn.execute("UPDATE works SET state='reviewable' WHERE id=?",(work,))
        conn.execute("INSERT INTO artifacts(id,work_id,run_id,kind,storage_ref,digest,size_bytes,displayable,output_revision,quality_state,created_at) VALUES ('out',?,?,'output',?,?,?,1,1,'needs_fix',?)",(work,confirmed['run_id'],path.relative_to(service.outputs).as_posix(),checksum,path.stat().st_size,now()))
        for kind,status,findings in [('technical','pass',{}),('semantic','not_tested',{'mode':'manual_review_only'})]:
            conn.execute('INSERT INTO quality_checks VALUES (?,?,?,?,?,?,?,?)',(kind,'out',checksum,kind,'test',status,encode(findings),now()))
    return path


def test_independent_manual_work_and_director_acceptance_keeps_qc_truth(env):
    service,c,_,work=draft(env);output_fixture(service,work)
    catalog=CreativeCatalog(service)
    raises('manual_review_confirmation_required',lambda:catalog.command('directors','accept',{'revision_id':'style','trial_artifact_id':'out'},command_id='no-manual',id='director',expected_revision=1))
    snap=service.snapshot(work)
    service.command('accept',{'output_id':'out','manual_review_confirmed':True},command_id='accept-work',work_id=work,expected_revision=snap['revision'])
    assert not catalog.list('directors')[0]['versions'][0]['accepted_at']
    result=catalog.command('directors','accept',{'revision_id':'style','trial_artifact_id':'out','manual_review_confirmed':True},command_id='accept-director',id='director',expected_revision=1)
    assert result['revision']==2
    assert service.snapshot(work)['artifacts'][0]['quality_state']=='needs_fix'
    with service.store.connection() as conn:
        assert [r[0] for r in conn.execute("SELECT status FROM quality_checks WHERE check_kind='semantic'")]==['not_tested']
        assert conn.execute('SELECT count(*) FROM acceptances').fetchone()[0]==1
        event=json.loads(conn.execute("SELECT payload_json FROM events WHERE kind='director_accepted'").fetchone()[0]);assert event['mode']=='explicit_manual_review'


@pytest.mark.parametrize('failure',['semantic_fail','wrong_style','bytes_changed'])
def test_manual_director_acceptance_rejects_bad_evidence(env,failure):
    service,c,_,work=draft(env);path=output_fixture(service,work,style=failure!='wrong_style')
    if failure=='semantic_fail':
        with service.store.transaction() as conn:
            artifact=row(conn,'artifacts','out')
            conn.execute('INSERT INTO quality_checks VALUES (?,?,?,?,?,?,?,?)',('bad','out',artifact['digest'],'semantic','test','fail','{}',now()))
    if failure=='bytes_changed':path.write_bytes(b'changed')
    with pytest.raises(ProductionError):CreativeCatalog(service).command('directors','accept',{'revision_id':'style','trial_artifact_id':'out','manual_review_confirmed':True},command_id='bad-accept',id='director',expected_revision=1)
    assert not CreativeCatalog(service).list('directors')[0]['versions'][0]['accepted_at']


def test_channel_defaults_pin_and_frozen_basis_do_not_change_with_new_defaults(env):
    service,c=env;cat=CreativeCatalog(service)
    ch=cat.command('channels','create',{'name':'频道','profile_ref':'one','creative_basis':{'position':'旧定位'},'settings':{'duration_seconds':45}},command_id='channel')
    seg=entry(c,profile_ref='one',channel_id=ch['id'])
    b,i,_=turn(service,c,seg,'第一部');p=tool(b,i,'easel_work_create_draft',{'title':'第一部','input_text':'真实经历'});b.end(Identity(**i));work=apply(c,p)['work_id']
    old=service.snapshot(work)
    cat.command('channels','edit',{'creative_basis':{'position':'新定位'},'settings':{'duration_seconds':60}},command_id='change',id=ch['id'],expected_revision=1)
    assert service.snapshot(work)['settings']==old['settings']
    # Once queued, request carries a concrete copy; later catalog changes cannot alter it.
    service.command('plan',{},command_id='plan',work_id=work,expected_revision=old['revision'])
    with service.store.connection() as conn:before=conn.execute('SELECT payload_json FROM tasks WHERE work_id=?',(work,)).fetchone()[0]
    cat.command('channels','edit',{'creative_basis':{'position':'更晚定位'}},command_id='later',id=ch['id'],expected_revision=2)
    with service.store.connection() as conn:assert conn.execute('SELECT payload_json FROM tasks WHERE work_id=?',(work,)).fetchone()[0]==before


def test_reference_import_uses_original_command_and_unknown_never_refetched(env,monkeypatch):
    from easel.reference_import import import_reference,public_target
    service,c,seg,work=draft(env);calls=[]
    def download(url,path):
        calls.append(url);path.write_bytes(b'isolated-reference');return {'url':url,'digest':hashlib.sha256(path.read_bytes()).hexdigest()}
    rev=service.snapshot(work)['revision']
    result=import_reference(service,'ui',seg,'https://video.example/ref.mp4','ref',rev,downloader=download)
    assert import_reference(service,'ui',seg,'https://video.example/ref.mp4','ref',rev,downloader=download)==result and len(calls)==1
    with service.store.connection() as conn:
        item=row(conn,'work_inputs',result['input_id']);metadata=json.loads(item['metadata_json'])
        assert item['usage']=='reference' and metadata['source']['rights']['status']=='UNKNOWN'
        assert metadata['reference_import']['use']=='style_reference_only'
    for url in ('http://video.example/x','file:///etc/passwd','https://u:p@video.example/x'):
        raises('invalid_reference_url',lambda:public_target(url))
    monkeypatch.setattr('socket.getaddrinfo',lambda *a,**kw:[(2,1,6,'',('127.0.0.1',443))])
    raises('reference_source_blocked',lambda:public_target('https://public-name.example/ref.mp4'))
    def failed(url,path):calls.append(url);raise OSError('offline')
    with pytest.raises(OSError):import_reference(service,'ui',seg,'https://video.example/fail.mp4','unknown-ref',service.snapshot(work)['revision'],downloader=failed)
    raises('reference_import_pending',lambda:import_reference(service,'ui',seg,'https://video.example/fail.mp4','unknown-ref',service.snapshot(work)['revision'],downloader=failed))
    assert len(calls)==2


def test_additive_migration_preserves_old_work_and_receipts(tmp_path,monkeypatch):
    import easel.production.store as module
    store=Store(tmp_path/'db.sqlite3')
    with monkeypatch.context() as patch:
        patch.setattr(module,'SCHEMA_VERSION',3);store.initialize()
    with store.transaction() as conn:
        conn.execute('INSERT INTO works(id,title,input_text,created_at,updated_at) VALUES (?,?,?,?,?)',('old','第五轮兼容样本','旧内容',now(),now()))
        conn.execute('INSERT INTO command_receipts VALUES (?,?,?,?,?)',('old-command','old','a'*64,'{"work_id":"old"}',now()))
        old=dict(conn.execute('SELECT * FROM works').fetchone());receipt=dict(conn.execute('SELECT * FROM command_receipts').fetchone())
    store.initialize();store.initialize()
    with store.connection() as conn:
        migrated=dict(conn.execute('SELECT * FROM works').fetchone())
        assert {k:migrated[k] for k in old}==old
        assert dict(conn.execute('SELECT * FROM command_receipts').fetchone())==receipt
        assert migrated['creation_context_json']=='{}'


def test_bound_video_session_cannot_fall_back_to_main_by_omitting_client_mode(env,monkeypatch):
    import web.app as web
    service,c=env;entry(c)
    monkeypatch.setattr(web.app.state,'production_service',service,raising=False)
    client=TestClient(web.app,base_url='http://127.0.0.1:7860',client=('127.0.0.1',12345))
    response=client.post('/api/chat/stream',json={'sessionId':'ui','turnId':'turn','message':'ordinary-looking'})
    assert response.status_code==400 and response.json()['error']['code']=='invalid_input'
    response=client.post('/api/chat',json={'sessionId':'ui','message':'ordinary-looking'})
    assert response.status_code==409 and response.json()['error']['code']=='conversation_stream_required'
    assert service.list_works()['items']==[]


def test_plugin_credential_has_no_general_api_authority_and_requires_local_peer(env,monkeypatch):
    import web.app as web
    service,c=env;monkeypatch.setattr(web.app.state,'production_service',service,raising=False)
    token='isolated-credential-at-least-32';monkeypatch.setenv('EASEL_WORK_BRIDGE_TOKEN',token)
    client=TestClient(web.app,base_url='http://127.0.0.1:7860',client=('127.0.0.1',12345))
    assert client.post('/api/production/works',headers={'Authorization':'Bearer '+token},json={'command_id':'no','payload':{'title':'no'}}).status_code==403
    remote=TestClient(web.app,base_url='http://127.0.0.1:7860',client=('192.0.2.4',12345))
    assert remote.post('/api/chat/work-tools/claim',headers={'Authorization':'Bearer '+token,'Origin':'http://127.0.0.1:7860'},json={}).status_code==403


def test_work_setting_changes_invalidate_old_plan_and_confirmed_changes_require_revision(env):
    from web.production_settings_api import create_settings_router
    service,c,_,work=draft(env)
    app=FastAPI();app.add_exception_handler(ProductionError,production_error_handler);app.include_router(create_settings_router(lambda:service,settings_provider=lambda:{}));client=TestClient(app)
    plan={'title':'fixture','summary':'test','script':'test','scenes':[{'id':'s1','purpose':'test','visual':'blue','narration':''}],'settings':{'duration_seconds':1,'aspect_ratio':'16:9','audio_mode':'silent'}}
    staged=service.command('plan',{'generate':False,'plan':plan},command_id='plan1',work_id=work,expected_revision=1)
    changed=client.post(f'/api/production/works/{work}/settings',json={'command_id':'change','expected_revision':staged['revision'],'payload':{'scope':'work','settings':{'duration_seconds':2}}})
    assert changed.status_code==200
    assert service.snapshot(work)['current_plan_revision'] is None
    raises('stale_revision',lambda:service.command('confirm',{'plan_revision':1,'plan_hash':staged['plan_hash']},command_id='old-confirm',work_id=work,expected_revision=changed.json()['revision']))
    plan['settings']['duration_seconds']=2
    staged=service.command('plan',{'generate':False,'plan':plan},command_id='plan2',work_id=work,expected_revision=changed.json()['revision'])
    confirmed=service.command('confirm',{'plan_revision':2,'plan_hash':staged['plan_hash']},command_id='confirm2',work_id=work,expected_revision=staged['revision'])
    with service.store.transaction() as conn:
        conn.execute("UPDATE runs SET state='succeeded' WHERE id=?",(confirmed['run_id'],))
    snap=service.snapshot(work)
    blocked=client.post(f'/api/production/works/{work}/settings',json={'command_id':'bad-change','expected_revision':snap['revision'],'payload':{'scope':'work','settings':{'duration_seconds':3}}})
    assert blocked.status_code==409 and blocked.json()['error']['code']=='revision_required'
    assert service.snapshot(work)['plans'][0]['plan']['settings']['duration_seconds']==2
    seg=c.view('ui')['segment_id']
    b,i,_=turn(service,c,seg,'讨论修改，但不能绕过指定版本修订',id='after-confirm')
    raises('revision_required',lambda:tool(b,i,'easel_work_request_plan',{'request':'绕过修订重做'}))
    raises('revision_required',lambda:tool(b,i,'easel_work_update_brief',{'entries':[{'kind':'user_requirement','text':'讨论修改','source_refs':['after-confirm']}]}))
    b.end(Identity(**i))


def test_channel_defaults_proposals_preserve_other_settings_and_use_current_target_version(env):
    service,c=env;cat=CreativeCatalog(service)
    ch=cat.command('channels','create',{'name':'频道','profile_ref':'one','creative_basis':{'position':'真实','themes':'产品'},'settings':{'duration_seconds':45,'subtitles':{'enabled':True,'size':50,'font':'default','color':'#FFFFFF','outline':'#000000','background':'transparent','position':'bottom'}}},command_id='ch')
    seg=entry(c,profile_ref='one',channel_id=ch['id']);b,i,_=turn(service,c,seg,'以后字幕大一点',id='settings')
    p=proposal(service,c,seg,'channel_defaults',{'settings':{'subtitles':{'size':60}},'creative_basis':{'audience':'创业者'}},'settings');b.end(Identity(**i));apply(c,p)
    channel=cat.list('channels')[0]
    assert channel['settings']['duration_seconds']==45 and channel['settings']['subtitles']['enabled'] is True and channel['settings']['subtitles']['size']==60
    assert channel['creative_basis']=={'position':'真实','themes':'产品','audience':'创业者'}
    b,i,_=turn(service,c,seg,'主题再加设计',id='settings2')
    p=proposal(service,c,seg,'channel_defaults',{'creative_basis':{'themes':'产品与设计'}},'settings2');b.end(Identity(**i));apply(c,p)
    assert cat.list('channels')[0]['creative_basis']['themes']=='产品与设计'


def test_entry_subtitle_layers_match_work_and_explicit_director_keeps_fixed_settings(env):
    service,c=env;cat=CreativeCatalog(service)
    fixture_work=service.command('create',{'title':'fixture identities'},command_id='fixture-work')['work_id']
    with service.store.transaction() as conn:
        profile=service._profile(conn,'one')
        conn.execute('UPDATE profile_refs SET settings_json=? WHERE id=?',(encode({'schema_version':1,'subtitles':{'enabled':True,'size':62,'color':'#EFEFEF'},'audio_mode':'silent'}),profile))
        # Accepted versions are fixture identities here; native analysis/render is
        # separately exercised by the A5 local production journey.
        conn.execute("INSERT INTO artifacts(id,work_id,kind,storage_ref,digest,size_bytes,created_at) VALUES ('fixture-trial',?,'output','works/fixture.mp4',?,1,?)",(fixture_work,'0'*64,now()))
        for n in ('default','explicit'):
            conn.execute('INSERT INTO directors(id,name,created_at,updated_at) VALUES (?,?,?,?)',(n,n,now(),now()))
            conn.execute("INSERT INTO director_revisions(id,director_id,revision,style_json,evidence_json,style_confirmed,trial_artifact_id,accepted_at,created_at) VALUES (?,?,1,?,?,1,'fixture-trial',?,?)",(n+'-v',n,encode({'schema_version':1,'visual_style':n}),'[]',now(),now()))
    channel=cat.command('channels','create',{'name':'频道','profile_ref':'one','settings':{'subtitles':{'enabled':False},'duration_seconds':35},'director_ids':['default'],'default_director_revision':'default-v'},command_id='channel-settings')
    segment=entry(c,profile_ref='one',channel_id=channel['id'],director_revision='explicit-v')
    context=c.view('ui')['context'];assert context['settings']['subtitles']=={'enabled':False,'size':62,'color':'#EFEFEF'}
    assert context['settings']['director_revision']=='explicit-v'
    b,i,_=turn(service,c,segment);p=tool(b,i,'easel_work_create_draft',{'title':'本期','input_text':'具体内容'});b.end(Identity(**i))
    work=service.snapshot(apply(c,p)['work_id']);assert work['settings']['subtitles']==context['settings']['subtitles']
    assert work['settings']['director_revision']=='explicit-v' and work['settings']['duration_seconds']==35
    # A different profile cannot borrow the channel. Archived defaults never
    # silently fall through to another director.
    raises('invalid_input',lambda:c.enter('other',{'profile_ref':'two','channel_id':channel['id']},'other-profile'))
    cat.command('directors','edit',{'archived':True},command_id='archive-default',id='default',expected_revision=1)
    raises('invalid_input',lambda:c.enter('later',{'profile_ref':'one','channel_id':channel['id']},'archived-default'))
    assert service.snapshot(work['id'])['settings']['director_revision']=='explicit-v'


def test_new_work_trial_entry_preserves_confirmed_profile_voice_and_unaccepted_director(env):
    service,c=env;cat=CreativeCatalog(service)
    profile_before={str(p):p.read_bytes() for p in service.profiles.rglob('*.md')}
    voice={'provider':'fixture','model':'speech','engine':'http-speech-v1','voice_id':'fixed','parameters':{'speed':1}}
    with service.store.transaction() as conn:
        conn.execute("INSERT INTO directors(id,name,created_at,updated_at) VALUES ('trial-director','Trial',?,?)",(now(),now()))
        conn.execute("INSERT INTO director_revisions(id,director_id,revision,style_json,evidence_json,style_confirmed,created_at) VALUES ('trial-v4','trial-director',4,?,'[]',1,?)",(encode({'schema_version':1,'visual_style':'confirmed style'}),now()))
    channel=cat.command('channels','create',{'name':'Existing channel','profile_ref':'one','settings':{'voice':voice},'director_ids':['trial-director']},command_id='trial-channel')
    raises('invalid_input',lambda:c.enter('without-trial',{'profile_ref':'one','channel_id':channel['id'],'director_revision':'trial-v4'},'ordinary-unaccepted-entry'))
    segment=entry(c,profile_ref='one',channel_id=channel['id'],director_revision='trial-v4',director_trial=True)
    context=c.view('ui')['context']
    assert context['settings']['director_revision']=='trial-v4' and context['settings']['director_trial'] is True
    assert context['settings']['voice']==voice
    assert service.list_works()['items']==[]
    bridge,identity,_=turn(service,c,segment,'Use my existing profile; one new idea.')
    p=tool(bridge,identity,'easel_work_create_draft',{'title':'One idea','input_text':'One new idea'})
    bridge.end(Identity(**identity));work=service.snapshot(apply(c,p)['work_id'])
    assert work['settings']['director_revision']=='trial-v4' and work['settings']['director_trial'] is True
    assert work['settings']['voice']==voice and work['runs']==[] and work['tasks']==[]
    with service.store.connection() as conn:
        version=row(conn,'director_revisions','trial-v4')
        assert version['style_confirmed'] and version['accepted_at'] is None and version['trial_artifact_id'] is None
        assert row(conn,'channels',channel['id'])['default_director_revision'] is None
        assert conn.execute('SELECT count(*) FROM operations').fetchone()[0]==0
    assert {str(p):p.read_bytes() for p in service.profiles.rglob('*.md')}==profile_before


def test_configuration_pipelines_edit_selected_targets_without_work_or_profile_changes(env):
    service,c=env;cat=CreativeCatalog(service)
    before={str(p):p.read_bytes() for p in service.profiles.rglob('*.md')}
    voice={'provider':'fixture','model':'speech','engine':'http-speech-v1','voice_id':'fixed','parameters':{'speed':1}}
    channel=cat.command('channels','create',{'name':'Existing','profile_ref':'one','settings':{'voice':voice}},command_id='config-channel')
    segment=entry(c,kind='channel_create',profile_ref='one',channel_id=channel['id'])
    bridge,identity,_=turn(service,c,segment,'Change the selected channel audience.',id='edit-channel')
    p=tool(bridge,identity,'easel_work_propose',{'kind':'channel_defaults','values':{'creative_basis':{'audience':'New audience'}},'source_refs':['edit-channel']})
    bridge.end(Identity(**identity));apply(c,p)
    channels=cat.list('channels');assert len(channels)==1
    assert channels[0]['id']==channel['id'] and channels[0]['creative_basis']['audience']=='New audience'
    assert channels[0]['settings']['voice']==voice
    with service.store.transaction() as conn:
        conn.execute("INSERT INTO directors(id,name,created_at,updated_at) VALUES ('config-director','Existing director',?,?)",(now(),now()))
        conn.execute("INSERT INTO director_revisions(id,director_id,revision,style_json,evidence_json,style_confirmed,created_at) VALUES ('config-v1','config-director',1,?,?,1,?)",(encode({'schema_version':1,'visual_style':'Original','storytelling':'Original'}),encode([{'source':'fixture'}]),now()))
    segment=entry(c,kind='director_formation',profile_ref='one',director_revision='config-v1',director_trial=True)
    bridge,identity,_=turn(service,c,segment,'Refine the selected director style.',id='edit-director')
    p=tool(bridge,identity,'easel_work_propose',{'kind':'director_revision','values':{'base_revision':1,'style':{'visual_style':'Refined','storytelling':'Keep a clear thread'}},'source_refs':['edit-director']})
    bridge.end(Identity(**identity));apply(c,p)
    directors=cat.list('directors');assert len(directors)==1 and len(directors[0]['versions'])==2
    with service.store.connection() as conn:
        old=row(conn,'director_revisions','config-v1');assert json.loads(old['style_json'])['visual_style']=='Original' and old['accepted_at'] is None
        latest=conn.execute("SELECT * FROM director_revisions WHERE director_id='config-director' ORDER BY revision DESC LIMIT 1").fetchone()
        assert latest['revision']==2 and not latest['style_confirmed'] and latest['accepted_at'] is None
        assert conn.execute('SELECT count(*) FROM works').fetchone()[0]==0
        assert conn.execute('SELECT count(*) FROM tasks').fetchone()[0]==0
        assert conn.execute('SELECT count(*) FROM operations').fetchone()[0]==0
    assert {str(p):p.read_bytes() for p in service.profiles.rglob('*.md')}==before


@pytest.mark.parametrize('name',[None,12,[],{},'', ' '*4])
def test_channel_proposal_invalid_name_is_not_saved_or_reported_applied(env,name):
    service,c=env;segment=entry(c,profile_ref='one');b,i,_=turn(service,c,segment)
    p=tool(b,i,'easel_work_propose',{'kind':'channel_create','values':{'name':name},'source_refs':['turn']});b.end(Identity(**i))
    raises('invalid_input',lambda:apply(c,p))
    assert c.view('ui')['proposals'][0]['state']=='proposed'
    assert CreativeCatalog(service).list('channels')==[]
    assert service.list_works()['items']==[]


def test_prework_symlink_cannot_supply_an_allowed_attachment(env):
    service,c=env;segment=entry(c);a=attachment(service);path=service.outputs/a['path']
    path.unlink();target=service.outputs/'foreign.mp4';target.write_bytes(b'foreign');path.symlink_to(target)
    raises('permission_missing',lambda:turn(service,c,segment,attachments=[a]))
    with service.store.connection() as conn:assert conn.execute('SELECT count(*) FROM conversation_turns').fetchone()[0]==0


def test_channel_proposal_rejects_non_text_basis_before_showing_save_card(env):
    service,c=env
    segment=entry(c,profile_ref='one',kind='channel_create')
    turn(service,c,segment,message='频道主题是注意力与选择')
    with pytest.raises(ProductionError,match='themes'):
        proposal(service,c,segment,'channel_create',{'name':'频道','creative_basis':{'themes':{'item':['注意力','选择']}}})
    assert c.view('ui')['proposals']==[]
    with service.store.connection() as conn:
        assert conn.execute('select count(*) from channels').fetchone()[0]==0


def test_brief_update_marks_old_work_confirmation_card_stale(env):
    service,c,segment,work=draft(env)
    b,i,_=turn(service,c,segment,'把内容重点改成注意力',id='new-basis')
    pending=tool(b,i,'easel_work_request_plan',{'request':'整理本期方案'},call='plan-before-change')
    tool(b,i,'easel_work_update_brief',{'entries':[{'kind':'user_requirement','text':'把内容重点改成注意力','source_refs':['new-basis']}]},call='change-after-plan')
    card=next(p for p in c.view('ui')['proposals'] if p['id']==pending['proposal_id'])
    assert card['state']=='stale'
    b.end(Identity(**i))
    raises('stale_revision',lambda:apply(c,pending))
    assert service.snapshot(work)['runs']==[]


def test_director_proposal_rejects_object_wrapped_references_before_card(env):
    service,c,segment,work=draft(env)
    with pytest.raises(ProductionError,match='reference_input_ids'):
        proposal(service,c,segment,'director_formation',{'name':'导演','reference_input_ids':{'item':'not-an-array'}})
    assert not [p for p in c.view('ui')['proposals'] if p['kind']=='director_formation']
    assert service.snapshot(work)['runs']==[]


def test_prework_plan_card_is_reissued_after_draft_without_starting_generation(env):
    service,c=env;segment=entry(c,profile_ref='one')
    bridge,identity,_=turn(service,c,segment)
    draft_card=proposal(service,c,segment,'draft',{'title':'Test content','input_text':'A concrete thought'})
    before=proposal(service,c,segment,'plan',{'request':'Keep the confirmed direction and review before production'})
    bridge.end(Identity(**identity))
    raises('work_not_bound',lambda:apply(c,before,'before_draft'))
    work=apply(c,draft_card)['work_id']
    view=c.view('ui')
    old=next(p for p in view['proposals'] if p['id']==before['proposal_id'])
    fresh=next(p for p in view['proposals'] if p['kind']=='plan' and p['state']=='proposed')
    assert old['state']=='stale'
    assert fresh['id']!=old['id'] and fresh['body_hash']!=old['body_hash']
    assert fresh['body']['values']==old['body']['values']
    assert fresh['body']['source_refs']==old['body']['source_refs']
    assert fresh['body']['work_id']==work
    assert fresh['body']['work_revision']==service.snapshot(work)['revision']
    with service.store.connection() as conn:
        assert conn.execute('SELECT COUNT(*) FROM runs').fetchone()[0]==0
        assert conn.execute('SELECT COUNT(*) FROM operations').fetchone()[0]==0
    raises('stale_revision',lambda:apply(c,before,'old_card_click'))
    result=c.apply('ui',fresh['id'],fresh['body_hash'],'new_plan_click')
    assert result['run_id']
    assert c.apply('ui',fresh['id'],fresh['body_hash'],'new_plan_click')==result
    with service.store.connection() as conn:
        assert conn.execute('SELECT COUNT(*) FROM runs').fetchone()[0]==1
        assert conn.execute('SELECT COUNT(*) FROM operations').fetchone()[0]==0
