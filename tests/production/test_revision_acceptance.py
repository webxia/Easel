import json
import pytest
from easel.production.store import Store
from easel.production.service import WorkService,digest
from easel.production.errors import ProductionError
from easel.production.editors import EditProject,Scene,Caption,assert_local_revision,EditError


@pytest.fixture
def prepared(tmp_path, request):
    store=Store(tmp_path/'outputs/_production/production.sqlite3');store.initialize()
    service=WorkService(store,outputs=tmp_path/'outputs',profiles=tmp_path/'profiles')
    work=service.command('create',{'title':'review'},command_id='create')['work_id']
    plan={'title':'t','summary':'s','script':'true story','scenes':[{'id':'s','purpose':'explain','visual':'video','narration':'true story'}],'settings':{'duration_seconds':1,'audio_mode':getattr(request,'param','silent')}}
    proposal=service.command('plan',{'generate':False,'plan':plan},command_id='plan',work_id=work,expected_revision=1)
    run=service.command('confirm',{'plan_revision':1,'plan_hash':proposal['plan_hash']},command_id='confirm',work_id=work,expected_revision=2)['run_id']
    path=service.outputs/'works'/work/'video.mp4';path.parent.mkdir(parents=True);path.write_bytes(b'fixture-output')
    with store.transaction() as conn:
        conn.execute("UPDATE runs SET state='succeeded' WHERE id=?",(run,))
        conn.execute("UPDATE tasks SET state='succeeded' WHERE run_id=?",(run,))
        conn.execute("UPDATE works SET state='reviewable',active_run_id=NULL WHERE id=?",(work,))
        for i,quality in [('passed','passed'),('unchecked','unchecked')]:
            conn.execute('INSERT INTO artifacts(id,work_id,run_id,kind,storage_ref,digest,size_bytes,media_type,displayable,output_revision,quality_state,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                (i,work,run,'output',path.relative_to(service.outputs).as_posix(),service._file_hash(path),path.stat().st_size,'video/mp4',1,1 if i=='passed' else 2,quality,'now'))
    return service,work


def test_accept_exact_passed_version_and_revision_keeps_selection(prepared):
    service,work=prepared
    with pytest.raises(ProductionError):service.command('accept',{'output_id':'unchecked'},command_id='bad',work_id=work,expected_revision=3)
    service.command('accept',{'output_id':'passed'},command_id='accept',work_id=work,expected_revision=3)
    snap=service.snapshot(work);assert snap['accepted_output_id']=='passed'
    request=service.command('revise',{'output_id':'passed','feedback':'只调整画面裁剪，保留声音文字'},command_id='revise',work_id=work,expected_revision=snap['revision'])
    updated=service.snapshot(work)
    assert updated['accepted_output_id']=='passed'
    assert updated['runs'][-1]['kind']=='revision'
    with service.store.connection() as conn:
        review=conn.execute('SELECT * FROM reviews WHERE id=?',(request['review_id'],)).fetchone()
        assert review['output_id']=='passed'
    assert len(updated['artifacts'])==2


def test_local_caption_scope_cannot_change_text_media_or_timing():
    base=EditProject(work_id='w',plan_revision=1,revision=1,duration=1,scenes=(Scene(scene_id='s',asset_id='a',duration=1),),captions=(Caption(caption_id='c',text='真实观点',start=0,end=1,font_asset_id='font'),))
    styled=base.model_copy(update={'revision':2,'captions':(base.captions[0].model_copy(update={'size':80}),)})
    assert_local_revision(base,styled,allowed={'captions'})
    for patch in [{'text':'另一观点'},{'start':.2}]:
        changed=base.model_copy(update={'revision':2,'captions':(base.captions[0].model_copy(update=patch),)})
        with pytest.raises(EditError):assert_local_revision(base,changed,allowed={'captions'})
    changed=base.model_copy(update={'revision':2,'scenes':(base.scenes[0].model_copy(update={'asset_id':'other'}),)})
    with pytest.raises(EditError):assert_local_revision(base,changed,allowed={'captions'})


def test_expanded_scope_starts_new_planning_from_exact_old_version(prepared):
    service,work=prepared
    request=service.command('revise',{'output_id':'passed','feedback':'增加一个新的结尾'},command_id='revise',work_id=work,expected_revision=3)
    changes={'schema_version':1,'summary':'新增结尾并重新确认时长','reason':'涉及内容和时长','base_digest':'fixture'}
    with service.store.transaction() as conn:
        conn.execute("UPDATE reviews SET changes_json=? WHERE id=?",(json.dumps(changes),request['review_id']))
        conn.execute("UPDATE runs SET state='needs_decision' WHERE id=?",(request['run_id'],))
        conn.execute("UPDATE tasks SET state='needs_decision' WHERE run_id=?",(request['run_id'],))
        conn.execute("UPDATE works SET state='needs_decision' WHERE id=?",(work,))
    rev=service.snapshot(work)['revision']
    with pytest.raises(ProductionError):
        service.command('confirm_revision',{'review_id':request['review_id'],'change_hash':'outdated'},command_id='bad-scope',work_id=work,expected_revision=rev)
    result=service.command('confirm_revision',{'review_id':request['review_id'],'change_hash':digest(changes)},command_id='scope',work_id=work,expected_revision=rev)
    with service.store.connection() as conn:
        old=conn.execute('SELECT state FROM runs WHERE id=?',(request['run_id'],)).fetchone()
        new=conn.execute('SELECT * FROM runs WHERE id=?',(result['run_id'],)).fetchone()
        task=conn.execute('SELECT * FROM tasks WHERE run_id=?',(result['run_id'],)).fetchone()
    assert old['state']=='superseded' and new['kind']=='planning'
    assert task['kind']=='plan' and json.loads(task['payload_json'])['base_plan_revision']==1
    assert '增加一个新的结尾' in json.loads(task['payload_json'])['request']
    assert service.snapshot(work)['artifacts'][0]['id'] in {'passed','unchecked'}


def test_fork_exact_output_copies_reference_without_old_authority(prepared):
    service,work=prepared
    result=service.command('fork',{'output_id':'passed','session_id':'new-session'},command_id='fork',work_id=work,expected_revision=3)
    snap=service.snapshot(result['work_id'])
    assert snap['accepted_output_id'] is None and not snap['plans'] and not snap['runs']
    assert len(snap['inputs'])==1 and snap['inputs'][0]['usage']=='reference'
    with service.store.connection() as conn:
        source=conn.execute('SELECT * FROM work_inputs WHERE work_id=?',(result['work_id'],)).fetchone()
        assert conn.execute('SELECT COUNT(*) FROM authorization_grants WHERE work_id=?',(result['work_id'],)).fetchone()[0]==0
    assert source['source_ref'].startswith('works/'+result['work_id']+'/references/')
    assert (service.outputs/source['source_ref']).read_bytes()==b'fixture-output'
    assert json.loads(source['metadata_json'])['source']['rights']['status']=='UNKNOWN'


@pytest.mark.parametrize('prepared',['voice','mixed'],indirect=True)
def test_narration_scope_is_explicit_and_protected(prepared):
    service,work=prepared
    for patch in ({'preserve_audio':True},{'render_only':True},{'scope':'invalid'}):
        with pytest.raises(ProductionError):
            service.command('revise',{'output_id':'passed','feedback':'改写口播','scope':'narration',**patch},
                command_id='reject-'+next(iter(patch)),work_id=work,expected_revision=3)
    result=service.command('revise',{'output_id':'passed','feedback':'改写口播','scope':'narration'},
        command_id='narration',work_id=work,expected_revision=3)
    snap=service.snapshot(work)
    task=next(t for t in snap['tasks'] if t['run_id']==result['run_id'])
    assert json.loads(task['payload_json'])['scope']=='narration'


def test_silent_narration_revision_rejected(prepared):
    service,work=prepared
    with pytest.raises(ProductionError,match='含旁白'):
        service.command('revise',{'output_id':'passed','feedback':'改口播','scope':'narration'},
            command_id='narration',work_id=work,expected_revision=3)


@pytest.mark.parametrize('prepared',['voice','mixed'],indirect=True)
@pytest.mark.parametrize('structured',[False,True])
def test_narration_worker_proposes_scope_then_plans_without_synthesizing(prepared,structured):
    import asyncio
    from easel.production.worker import Worker
    from easel.production.revisions import RevisionTasks
    service,work=prepared
    project=EditProject(work_id=work,plan_revision=1,revision=1,duration=1,
        scenes=(Scene(scene_id='s',asset_id='fixture',duration=1),))
    path=service.outputs/'works'/work/'project.json';path.write_text(project.model_dump_json())
    with service.store.transaction() as conn:
        source=conn.execute("SELECT run_id FROM artifacts WHERE id='passed'").fetchone()[0]
        conn.execute('INSERT INTO artifacts(id,work_id,run_id,kind,storage_ref,digest,size_bytes,media_type,created_at) VALUES (?,?,?,?,?,?,?,?,?)',
            ('project',work,source,'edit_project',path.relative_to(service.outputs).as_posix(),service._file_hash(path),path.stat().st_size,'application/json','now'))
        conn.execute("UPDATE artifacts SET metadata_json=? WHERE id='passed'",(json.dumps({'schema_version':1,'project_id':'project'}),))
    feedback=json.dumps({'agent_request':'改稿重配','user_sources':[{'source_turn':'private-turn','text':'只改末句，保留BGM和音效'}]},ensure_ascii=False) if structured else '改稿重配'
    result=service.command('revise',{'output_id':'passed','feedback':feedback,'scope':'narration'},
        command_id='rewrite',work_id=work,expected_revision=3)
    # This branch must need neither a model nor a synthesis service.
    worker=Worker(service.store,{'revise':RevisionTasks(service,None,None).revise})
    asyncio.run(worker.run_once())
    snap=service.snapshot(work)
    assert snap['state']=='needs_decision'
    review=next(r for r in snap['reviews'] if r['id']==result['review_id'])
    assert review['changes']['affected']==['audio','captions','content']
    assert review['feedback']==feedback
    assert '改稿重配' in review['changes']['reason']
    assert 'source_turn' not in review['changes']['reason']
    assert 'agent_request' not in review['changes']['reason']
    if structured:assert '只改末句，保留BGM和音效' in review['changes']['reason']
    from easel.conversation import ConversationService
    from easel.conversation_pipeline import pending
    conversations=ConversationService(service)
    segment_id=conversations.enter('scope-ui',{'work_id':work},'link-scope')['segment_id']
    def scope_choices():
        with service.store.connection() as conn:
            segment=conversations.segment(conn,'scope-ui',segment_id)
            return pending(conversations,conn,segment)['blockers'][0]['choices']
    choice=scope_choices()[0]
    assert choice['action']=='confirm_revision'
    assert choice['values']=={'review_id':review['id'],'change_hash':review['change_hash']}
    assert choice['scope']['reason']==review['changes']['reason']
    assert choice['scope']['requires_new_generation'] is True
    assert 'edit' not in choice['scope']
    assert '新方案完成后另确认制作' in choice['requires']
    with service.store.transaction() as conn:
        conn.execute('UPDATE runs SET cancel_requested=1 WHERE id=?',(result['run_id'],))
    assert scope_choices()==[]
    with service.store.transaction() as conn:
        conn.execute('UPDATE runs SET cancel_requested=0 WHERE id=?',(result['run_id'],))
    service.command('confirm_revision',{'review_id':review['id'],'change_hash':review['change_hash'],
        'services':[{'provider':'direct-api','model':'fixture','mode':'structured'}]},
        command_id='confirm-rewrite',work_id=work,expected_revision=snap['revision'])
    snap=service.snapshot(work)
    task=next(t for t in snap['tasks'] if t['run_id']==snap['active_run_id'])
    assert task['kind']=='plan'
    assert json.loads(task['payload_json'])['revision_scope']=='narration'
    assert json.loads(task['payload_json'])['base_plan_revision']==1
    from tests.production.test_planning_runtime import Transport
    from easel.production.planning import PlanningTasks,received_plan
    from easel.production.operations import OperationService
    transport=Transport({'scenes':[{'id':'s','narration':'新句。'}]})
    planning=PlanningTasks(service,OperationService(service.store),transport,
        {'provider':'direct-api','model':'fixture','mode':'structured'},'fixture-v1')
    assert asyncio.run(Worker(service.store,{'plan':planning.plan}).run_once())
    revised=service.snapshot(work)
    assert revised['state']=='awaiting_confirmation'
    latest=max(revised['plans'],key=lambda p:p['revision'])
    original=next(p for p in revised['plans'] if p['revision']==1)
    assert latest['plan']['script']=='新句。'
    assert latest['plan']['settings']==original['plan']['settings']
    assert latest['plan']['scenes'][0]['visual']==original['plan']['scenes'][0]['visual']
    assert transport.requests[0][2]['title']=='NarrationPlanChanges'
    with service.store.connection() as conn:
        ops=[dict(o) for o in conn.execute("SELECT * FROM operations WHERE work_id=?",(work,))]
    assert len(ops)==1 and ops[0]['kind']=='MODEL' and ops[0]['state']=='succeeded'
    assert received_plan(ops[0]).script=='新句。'
    assert not latest['confirmed_at']


@pytest.mark.parametrize('prepared',['voice','mixed'],indirect=True)
def test_narration_revision_still_rejects_protected_original_audio(prepared):
    service,work=prepared
    with service.store.transaction() as conn:
        conn.execute("INSERT INTO work_inputs(id,work_id,kind,usage,source_ref,digest,metadata_json,created_at) VALUES('original',?,'video','must_use','source.mp4','original',?,'now')",
                     (work,json.dumps({'schema_version':1,'original_audio':True})))
    before=service.snapshot(work)
    with pytest.raises(ProductionError,match='保留原声'):
        service.command('revise',{'output_id':'passed','feedback':'只改结尾','scope':'narration'},
                        command_id='protected-original',work_id=work,expected_revision=3)
    after=service.snapshot(work)
    assert after['runs']==before['runs'] and after['tasks']==before['tasks']
    assert after['artifacts']==before['artifacts']


def test_revision_feedback_projection_preserves_plain_and_unknown_json():
    from easel.production.revisions import revision_feedback_text
    for text in ['只改末句', '{"text":"保留JSON示例"}', '{bad json']:
        assert revision_feedback_text(text)==text
    source={'agent_request':'改末句','user_sources':[{'source_turn':'private-id','text':'保留音乐和音效'}]}
    assert revision_feedback_text(json.dumps(source,ensure_ascii=False))=='保留音乐和音效\n改末句'


@pytest.fixture
def audio_preview(prepared):
    from easel.production.editors import AudioClip
    from easel.conversation import ConversationService
    from tests.production.test_store import insert_artifact
    from tests.production.test_conversation import entry
    service,work=prepared
    root=service.outputs/'works'/work
    project=EditProject(work_id=work,plan_revision=1,revision=1,duration=1,audio_mode='mixed',
        scenes=(Scene(scene_id='s',asset_id='video',duration=1),),
        audio=tuple(AudioClip(clip_id=role,asset_id='audio-'+role,role=role,at=.1 if role=='voice' else 0,
                              duration=.8 if role=='voice' else 1,gain=.2)
                    for role in ('voice','music','sfx')))
    path=root/'mix.json';path.write_text(project.model_dump_json())
    silent=root/'other.json';silent.write_text(EditProject(work_id=work,plan_revision=1,revision=2,duration=1,audio_mode='voice',
        scenes=(Scene(scene_id='other',asset_id='video',duration=1,source_audio=True),)).model_dump_json())
    with service.store.transaction() as conn:
        run=conn.execute("SELECT run_id FROM artifacts WHERE id='passed'").fetchone()[0]
        for name,file in [('project',path),('other-project',silent)]:
            insert_artifact(conn,work,name,run_id=run,kind='edit_project',storage_ref=file.relative_to(service.outputs).as_posix(),
                digest=service._file_hash(file),size_bytes=file.stat().st_size,metadata_json=json.dumps({'schema_version':1}))
        for role in ('voice','music','sfx','unselected'):
            file=root/(role+'.dat');file.write_bytes(('registered-'+role).encode())
            insert_artifact(conn,work,'audio-'+role,run_id=run,kind='audio',storage_ref=file.relative_to(service.outputs).as_posix(),
                digest=service._file_hash(file),size_bytes=file.stat().st_size,
                metadata_json=json.dumps({'schema_version':1,'source':{'provider':'fixture','creator':'Composer',
                    'download_url':'https://private.example/SECRET','local_path':'SECRET/private'}}))
            if role!='unselected':conn.execute('INSERT INTO artifact_edges VALUES (?,?,?)',('project','audio-'+role,'material'))
        for output,project_id in [('passed','project'),('unchecked','other-project')]:
            conn.execute('UPDATE artifacts SET metadata_json=? WHERE id=?',(json.dumps({'schema_version':1,'project_id':project_id}),output))
            conn.execute('INSERT INTO artifact_edges VALUES (?,?,?)',(output,project_id,'project'))
        conn.execute("UPDATE artifacts SET quality_state='needs_fix' WHERE id='passed'")
        for kind,status,findings in [('technical','pass',{'probe':{'streams':[
                {'codec_type':'video'},{'codec_type':'audio','codec_name':'aac','duration':'1.0','channels':2}]}}),('semantic','not_tested',{
                'scope':'sampled_visual_only','visual_status':'pass','audio_reviewed':False,
                'review':{'verdict':'pass','findings':[],'suggestions':['构图可以更松一点']}})]:
            conn.execute('INSERT INTO quality_checks VALUES (?,?,?,?,?,?,?,?)',
                ('preview-'+kind,'passed',service._file_hash(root/'video.mp4'),kind,'fixture',status,json.dumps(findings),'now'))
    c=ConversationService(service);seg=entry(c,work_id=work)
    return service,c,seg,work,path,project


@pytest.mark.parametrize('prepared',['mixed'],indirect=True)
def test_native_preview_reports_exact_version_mix_and_is_read_only(audio_preview):
    from tests.production.test_conversation import turn
    from tests.production.test_conversation_pipeline import pipe
    s,c,seg,work,path,project=audio_preview
    before=s.snapshot(work)
    b,i,_=turn(s,c,seg,'只核对第1版的BGM和音效')
    result=pipe(b,i,'preview',values={'output_revision':1})
    usage=result['preview_output']['audio_usage']
    assert usage['status']=='available' and usage['output_id']=='passed'
    assert usage['input_clip_counts']=={'voice':1,'music':1,'sfx':1}
    assert all(t['gain']==.2 for t in usage['input_clips'])
    spoken=next(t for t in usage['input_clips'] if t['role']=='voice')
    assert spoken['at']==.1 and spoken['duration']==.8
    assert usage['project_duration']==1
    assert usage['exported_audio']=={'status':'available','stream_count':1,
        'streams':[{'codec_name':'aac','duration':'1.0','channels':2}]}
    assert all(t['source']=={'provider':'fixture','creator':'Composer'} for t in usage['input_clips'])
    assert 'not listening' in usage['evidence_scope']
    assert 'audio-unselected' not in json.dumps(usage)
    assert 'SECRET' not in json.dumps(result) and str(s.outputs) not in json.dumps(result)
    full=pipe(b,i,'pending',values={'detail':'full'})
    presented=next(a for a in full['work']['artifacts'] if a['id']=='passed')
    assert 'quality_state' not in presented
    checked=next(q for q in presented['checks'] if q['scope']=='sampled_visual_only')
    assert checked['findings']==[] and checked['suggestions']==['构图可以更松一点']
    assert checked['audio_reviewed'] is False
    assert next(a for a in s.snapshot(work)['artifacts'] if a['id']=='passed')['quality_state']=='needs_fix'
    # Latest output has no separate tracks, but does retain original scene audio.
    latest=pipe(b,i,'preview')['preview_output']['audio_usage']
    assert latest['output_id']=='unchecked' and latest['input_clips']==[]
    assert latest['source_audio_scenes']==['other']
    assert latest['input_clip_counts']=={'voice':0,'music':0,'sfx':0}
    assert latest['exported_audio']['status']=='unavailable'
    assert s.snapshot(work)==before


@pytest.mark.parametrize('prepared',['mixed'],indirect=True)
@pytest.mark.parametrize('fault',['project_changed','audio_changed','project_deleted','audio_deleted',
                                   'project_edge_missing','audio_edge_missing','foreign_project','project_missing','foreign_audio'])
def test_preview_unverifiable_mix_is_not_reported_as_no_audio(audio_preview,fault):
    from easel.conversation_pipeline import preview
    s,c,seg,work,path,project=audio_preview
    if fault=='foreign_audio':
        foreign=s.command('create',{'title':'other'},command_id='other-work')['work_id']
    with s.store.transaction() as conn:
        altered=None
        if fault=='project_changed':path.write_text('{}')
        elif fault=='audio_changed':(path.parent/'music.dat').write_bytes(b'changed')
        elif fault in {'project_deleted','audio_deleted'}:
            conn.execute("UPDATE artifacts SET deleted_at='now' WHERE id=?",('project' if fault=='project_deleted' else 'audio-music',))
        elif fault.endswith('_edge_missing'):
            conn.execute('DELETE FROM artifact_edges WHERE artifact_id=? AND dependency_id=?',
                ('passed','project') if fault=='project_edge_missing' else ('project','audio-music'))
        elif fault=='foreign_project':
            # Even a matching file digest cannot make a foreign Work project valid.
            altered=project.model_copy(update={'work_id':'foreign-work'})
        elif fault=='project_missing':
            conn.execute("UPDATE artifacts SET metadata_json=? WHERE id='passed'",(json.dumps({'schema_version':1,'project_id':'missing'}),))
        elif fault=='foreign_audio':
            from tests.production.test_store import insert_artifact
            f=path.parent/'music.dat'
            insert_artifact(conn,foreign,'foreign-audio',kind='audio',storage_ref=f.relative_to(s.outputs).as_posix(),
                digest=s._file_hash(f),size_bytes=f.stat().st_size)
            altered=project.model_copy(update={'audio':(project.audio[0].model_copy(update={'asset_id':'foreign-audio'}),*project.audio[1:])})
        if altered:
            # Register a distinct fixture identity; immutable artifacts stay immutable.
            from tests.production.test_store import insert_artifact
            changed=path.parent/'altered.json';changed.write_text(altered.model_dump_json())
            run=conn.execute("SELECT run_id FROM artifacts WHERE id='passed'").fetchone()[0]
            insert_artifact(conn,work,'altered-project',run_id=run,kind='edit_project',
                storage_ref=changed.relative_to(s.outputs).as_posix(),digest=s._file_hash(changed),size_bytes=changed.stat().st_size)
            conn.execute("UPDATE artifacts SET metadata_json=? WHERE id='passed'",(json.dumps({'schema_version':1,'project_id':'altered-project'}),))
            conn.execute('INSERT INTO artifact_edges VALUES (?,?,?)',('passed','altered-project','project'))
            for clip in altered.audio:
                conn.execute('INSERT INTO artifact_edges VALUES (?,?,?)',('altered-project',clip.asset_id,'material'))
    with s.store.connection() as conn:segment=c.segment(conn,'ui',seg)
    result=preview(c,segment,{'output_id':'passed'})
    usage=result['preview_output']['audio_usage']
    assert usage['status']=='unavailable'
    assert 'input_clip_counts' not in usage and 'input_clips' not in usage
    assert '不能据此断言没有' in usage['reason']
