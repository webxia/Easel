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


@pytest.mark.parametrize('prepared',['voice'],indirect=True)
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


def test_non_voice_narration_revision_rejected(prepared):
    service,work=prepared
    with pytest.raises(ProductionError,match='纯旁白'):
        service.command('revise',{'output_id':'passed','feedback':'改口播','scope':'narration'},
            command_id='narration',work_id=work,expected_revision=3)


@pytest.mark.parametrize('prepared',['voice'],indirect=True)
def test_narration_worker_proposes_scope_then_plans_without_synthesizing(prepared):
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
    result=service.command('revise',{'output_id':'passed','feedback':'改稿重配','scope':'narration'},
        command_id='rewrite',work_id=work,expected_revision=3)
    # This branch must need neither a model nor a synthesis service.
    worker=Worker(service.store,{'revise':RevisionTasks(service,None,None).revise})
    asyncio.run(worker.run_once())
    snap=service.snapshot(work)
    assert snap['state']=='needs_decision'
    review=next(r for r in snap['reviews'] if r['id']==result['review_id'])
    assert review['changes']['affected']==['audio','captions','content']
    service.command('confirm_revision',{'review_id':review['id'],'change_hash':review['change_hash']},
        command_id='confirm-rewrite',work_id=work,expected_revision=snap['revision'])
    snap=service.snapshot(work)
    task=next(t for t in snap['tasks'] if t['run_id']==snap['active_run_id'])
    assert task['kind']=='plan'
    assert json.loads(task['payload_json'])['revision_scope']=='narration'
    assert json.loads(task['payload_json'])['base_plan_revision']==1
