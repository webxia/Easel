"""Retention deletes reconstructible copies, never authority or recovery inputs."""
import json
import os
from pathlib import Path
from types import SimpleNamespace
import pytest
from easel.production.store import Store
from easel.production.media import file_sha256
from easel.production.editors.ffmpeg import _lock
from easel.production.storage_retention import completed_render_scratch, redundant_backups, storage_maintenance
from tests.production.test_worker import seed_run


@pytest.fixture
def completed(tmp_path):
    outputs=tmp_path/'outputs';store=Store(outputs/'_production/production.sqlite3');store.initialize()
    work,run,task=seed_run(store,kind='production',first='render')
    folder=outputs/'_production/renders'/task;folder.mkdir(parents=True)
    formal=outputs/'works'/work/'final.mp4';formal.parent.mkdir(parents=True);formal.write_bytes(b'canonical movie')
    source=formal.with_name('source.mp4');source.write_bytes(b'original material')
    staged=folder/'assets'/f'{file_sha256(source)}.mp4';staged.parent.mkdir();staged.write_bytes(source.read_bytes())
    scene=folder/'scenes/0000.mp4';scene.parent.mkdir();scene.write_bytes(b'reconstructible shot')
    captions=folder/'captions/frame-0.png';captions.parent.mkdir();captions.write_bytes(b'subtitle image')
    for name in ['final.mp4','montage.mp4']:(folder/name).write_bytes(formal.read_bytes())
    (folder/'job.json').write_text(json.dumps({'job_id':task,'status':'completed'}))
    (folder/'project.json').write_text(json.dumps({'work_id':work}))
    (folder/'output.json').write_text(json.dumps({'video_path':str(folder/'final.mp4'),'caption_base_path':str(folder/'montage.mp4'),'sha256':file_sha256(formal)}))
    with store.transaction() as c:
        c.execute("UPDATE runs SET state='succeeded' WHERE id=?",(run,));c.execute("UPDATE tasks SET state='succeeded' WHERE id=?",(task,))
        c.execute("UPDATE works SET state='reviewable' WHERE id=?",(work,))
        for id,path,kind,metadata in [('out',formal,'output',{'schema_version':1,'render_job_id':task}),('src',source,'video',{'schema_version':1})]:
            c.execute('INSERT INTO artifacts(id,work_id,run_id,kind,storage_ref,digest,size_bytes,media_type,metadata_json,created_at,output_revision) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(id,work,run,kind,str(path.relative_to(outputs)),file_sha256(path),path.stat().st_size,'video/mp4',json.dumps(metadata),'now',1 if kind=='output' else None))
    return SimpleNamespace(outputs=outputs,store=store),work,run,task,folder,formal,source,staged,scene,captions


def test_completed_render_cleanup_keeps_formal_source_caption_base_and_receipts(completed):
    service,work,run,task,folder,formal,source,staged,scene,captions=completed
    with service.store.transaction() as c:c.execute("UPDATE works SET accepted_output_id='out' WHERE id=?",(work,))
    preview=completed_render_scratch(service,dry_run=True)
    assert len(preview['files'])==3 and scene.exists() and staged.exists()
    result=completed_render_scratch(service)
    assert len(result['files'])==3 and not scene.exists() and not staged.exists() and not captions.exists()
    assert all((folder/n).exists() for n in ['final.mp4','montage.mp4','job.json','project.json','output.json'])
    assert formal.read_bytes()==b'canonical movie' and source.read_bytes()==b'original material'
    assert completed_render_scratch(service)['files']==[]


@pytest.mark.parametrize('case',['active','unknown','bad_output','missing_source','symlink','lock','direct_reference'])
def test_render_retention_guards(completed,case,tmp_path):
    service,work,run,task,folder,formal,source,staged,scene,captions=completed
    if case=='active':
        with service.store.transaction() as c:c.execute("UPDATE runs SET state='running' WHERE id=?",(run,))
    if case=='unknown':
        with service.store.transaction() as c:
            c.execute("INSERT INTO authorization_grants(id,work_id,purpose,plan_revision,services_json,created_at) VALUES ('g',?,'production',1,'[]','now')",(work,))
            c.execute("INSERT INTO operations(id,work_id,run_id,task_id,grant_id,kind,state,input_hash,request_key,provider,model,mode,config_version,request_json,owner_epoch,created_at,updated_at) VALUES ('op',?,?,?,'g','MODEL','unknown','hash','key','fixture','model','normal','v1','{}',1,'now','now')",(work,run,task))
    if case=='bad_output':formal.write_bytes(b'changed formal output')
    if case=='missing_source':source.unlink()
    if case=='symlink':
        scene.unlink();scene.symlink_to(formal)
    if case=='direct_reference':
        with service.store.transaction() as c:
            c.execute("INSERT INTO artifacts(id,work_id,run_id,kind,storage_ref,digest,size_bytes,created_at) VALUES ('direct',?,?,'video',?,?,?,'now')",(work,run,str(scene.relative_to(service.outputs)),file_sha256(scene),scene.stat().st_size))
    if case=='lock':
        with _lock(folder/'execution.lock'):assert completed_render_scratch(service)['files']==[]
        assert scene.exists() and staged.exists();return
    completed_render_scratch(service)
    assert formal.exists()
    if case in ['active','unknown','bad_output']:assert scene.exists() and staged.exists()
    if case=='missing_source':assert staged.exists()
    if case=='symlink':assert scene.is_symlink() and formal.exists()
    if case=='direct_reference':assert scene.exists()


def backup_files(service,monkeypatch):
    monkeypatch.setattr('easel.production.storage_retention._open_paths',lambda:set())
    directory=service.outputs/'_debug'/'trial';directory.mkdir(parents=True)
    paths=[]
    for i in range(4):
        path=directory/f'backup-{i}.sqlite3';service.store.backup(path);os.utime(path,(10+i,10+i));paths.append(path)
    return paths


def test_backup_rotation_keeps_two_newest_and_unknown_authority(completed,monkeypatch):
    service,*_=completed;paths=backup_files(service,monkeypatch)
    preview=redundant_backups(service,dry_run=True)
    assert len(preview['files'])==2 and all(p.exists() for p in paths)
    result=redundant_backups(service)
    assert len([f for f in result['files'] if f['path'].endswith('.sqlite3')])==2 and not paths[0].exists() and not paths[1].exists()
    assert paths[2].exists() and paths[3].exists() and service.store.path.exists()
    assert redundant_backups(service)['files']==[]


@pytest.mark.parametrize('case',['open','sidecar','unique_work','unique_plan','hardlink','symlink','recent'])
def test_backup_rotation_never_deletes_unknown_or_in_use_files(completed,monkeypatch,case):
    import sqlite3
    service,*_=completed;paths=backup_files(service,monkeypatch);target=paths[0]
    if case=='open':monkeypatch.setattr('easel.production.storage_retention._open_paths',lambda:{str(target)})
    if case=='sidecar':Path(str(target)+'-wal').write_bytes(b'recovery')
    if case=='unique_work':
        other=Store(target);other.create_work({'title':'unique evidence'})
    if case=='unique_plan':
        other=Store(target);work=completed[1]
        plan=json.loads(other.get_plan(work,1)['payload_json']);plan['summary']='unique plan'
        other.save_plan(work,plan,expected_revision=other.get_work(work)['revision'])
    if case in ['hardlink','symlink']:
        target.unlink()
        if case=='hardlink':os.link(service.store.path,target)
        else:target.symlink_to(service.store.path)
    if case=='recent':os.utime(target,None)
    redundant_backups(service)
    assert target.exists() and service.store.path.exists()


def test_missing_open_file_inventory_and_outer_lock_fail_closed(completed,monkeypatch):
    service,*_=completed;backup_files(service,monkeypatch)
    monkeypatch.setattr('easel.production.storage_retention._open_paths',lambda:None)
    assert redundant_backups(service)['files']==[]
    with _lock(service.outputs/'_production/storage-maintenance.lock'):
        assert storage_maintenance(service)['skipped']=='maintenance_busy'


def test_runtime_schedules_existing_maintenance_without_per_tick_sweeps(completed,monkeypatch):
    import asyncio
    from easel.production.runtime import ProductionRuntime
    from easel.production.worker import Worker
    service,*_=completed;calls=[]
    monkeypatch.setattr('easel.production.storage_retention.storage_maintenance',lambda s,**kw:calls.append(s))
    runtime=ProductionRuntime(service,Worker(service.store,{}),None,SimpleNamespace(editor=None))
    asyncio.run(runtime.maintenance_once());asyncio.run(runtime.maintenance_once())
    assert calls==[service]
    runtime._storage_next=0
    asyncio.run(runtime.maintenance_once());assert calls==[service,service]


@pytest.mark.skipif(not __import__('shutil').which('ffmpeg'),reason='FFmpeg unavailable')
def test_real_completed_render_still_collects_and_caption_preview_decodes_after_reclaim(tmp_path,monkeypatch):
    import subprocess
    from tests.production.test_creation_flow import test_confirm_to_real_render_to_reviewable_without_creator_acceptance as first_cut
    from easel.production.editors import FFmpegEditor
    first_cut(tmp_path,True,False,False,monkeypatch)
    outputs=tmp_path/'outputs';service=SimpleNamespace(outputs=outputs,store=Store(outputs/'_production/production.sqlite3'))
    editor=FFmpegEditor(outputs/'_production/renders')
    folder=next(p for p in editor.root.iterdir() if (p/'job.json').is_file())
    original=editor.collect(folder.name);sha=original.sha256
    with service.store.connection() as c:
        records=[dict(r) for r in c.execute('SELECT * FROM artifacts')]
    before={r['storage_ref']:file_sha256(outputs/r['storage_ref']) for r in records}
    result=completed_render_scratch(service)
    assert result['files'] and any('/assets/' in r['path'] for r in result['files'])
    assert editor.collect(folder.name).sha256==sha
    assert before=={ref:file_sha256(outputs/ref) for ref in before}
    project=json.loads((folder/'project.json').read_text())
    base,_=editor.caption_base(folder.name,work_id=project['work_id'])
    for path in [original.video_path,base]:subprocess.run(['ffmpeg','-v','error','-i',str(path),'-f','null','-'],check=True,capture_output=True)


def test_daily_cleanup_persists_across_restart_and_does_not_repeat_within_day(completed,monkeypatch):
    import easel.production.storage_retention as module
    service,_,_,_,folder,*_=completed;clock=[100000.0]
    monkeypatch.setattr(module,'time',SimpleNamespace(time=lambda:clock[0]))
    monkeypatch.setattr(module,'_open_paths',lambda:set())
    first=storage_maintenance(service,due_only=True)
    extra=folder/'scenes/0001.mp4';extra.write_bytes(b'later cache')
    clock[0]+=86399
    assert storage_maintenance(service,due_only=True)['skipped']=='not_due'
    assert extra.exists() and first['next_at']==186400
    clock[0]+=1
    assert storage_maintenance(service,due_only=True)['removed_bytes']>0 and not extra.exists()


@pytest.fixture
def downloads(completed,monkeypatch,tmp_path):
    from PIL import Image
    from easel.production.materials import MaterialService
    from easel.materials.library import LibraryVisibility,UseContext
    from easel.materials.domain import CandidateSource,MediaType
    from tests.production.test_materials_core import rights
    service,work,run,task,folder,formal,*_=completed
    monkeypatch.setattr('easel.production.storage_retention._open_paths',lambda:set())
    library=MaterialService(service.outputs/'_production/materials')
    source=tmp_path/'received';source.mkdir();scope=LibraryVisibility(profile_ref='profile')
    context=UseContext(work_id=work,purpose='production');items={}
    for id,color,kind in [('used',(200,30,40),'stock'),('unused',(30,200,40),'stock'),('upload',(30,40,200),'user_upload')]:
        Image.new('RGB',(32,24),color).save(source/f'{id}.png')
        handle=library.ingest_input(source_root=source,relative_path=f'{id}.png',visibility=scope,context=context,
            media_type=MediaType.IMAGE,source=CandidateSource(kind=kind,provider='pexels' if kind=='stock' else None,provider_asset_id=id),rights=rights())
        library.catalog.record_usage(handle.asset_ref,scope=scope,context=context,reference_id=id)
        path=service.outputs/'works'/work/'assets'/f'{handle.digest}.png';path.parent.mkdir(exist_ok=True);path.write_bytes(handle.local_path.read_bytes())
        metadata={'schema_version':1,**handle.artifact_metadata(),'material_scope':scope.model_dump(mode='json'),'input_id':None}
        with service.store.transaction() as c:
            c.execute('INSERT INTO artifacts(id,work_id,run_id,kind,storage_ref,digest,size_bytes,metadata_json,created_at) VALUES(?,?,?,\'image\',?,?,?,?,\'now\')',(id,work,run,str(path.relative_to(service.outputs)),handle.digest,path.stat().st_size,json.dumps(metadata)))
        items[id]=(handle,path,metadata)
    with service.store.transaction() as c:
        c.execute("INSERT INTO artifact_edges VALUES ('out','used','source')")
        # Set only test fixture admission; actual acceptance goes through service.
        c.execute("UPDATE artifacts SET displayable=1,quality_state='passed' WHERE id='out'")
    return completed,library,scope,context,items,source


def accept_download_fixture(downloads):
    from easel.production.service import WorkService
    completed,*_=downloads;service,work,*_=completed
    domain=WorkService(service.store,outputs=service.outputs,profiles=service.outputs.parent/'profiles')
    domain.command('accept',{'output_id':'out'},command_id='creator-accept',work_id=work,expected_revision=service.store.get_work(work)['revision'])


def test_unused_download_reclaimed_but_used_media_voice_and_upload_stay(downloads):
    from easel.production.storage_retention import downloaded_media
    completed,library,scope,context,items,_=downloads;service,*_=completed
    before={id:meta['rights'] for id,(_,_,meta) in items.items()}
    result=downloaded_media(service)
    assert result['artifact_ids']==['unused']
    assert not items['unused'][0].local_path.exists() and not items['unused'][1].exists()
    assert items['used'][0].local_path.exists() and items['used'][1].exists()
    assert items['upload'][0].local_path.exists() and items['upload'][1].exists()
    with service.store.connection() as c:
        assert all(json.loads(c.execute('SELECT metadata_json FROM artifacts WHERE id=?',(id,)).fetchone()[0])['rights']==rights for id,rights in before.items())


def test_used_download_requires_real_acceptance_and_keeps_formal_output_and_credits(downloads):
    from easel.production.storage_retention import downloaded_media
    completed,library,scope,context,items,_=downloads;service,work,_,_,_,formal,*_=completed
    with service.store.transaction() as c:c.execute("UPDATE works SET accepted_output_id='out' WHERE id=?",(work,))
    downloaded_media(service);assert items['used'][1].exists()  # Pointer is not consent.
    accept_download_fixture(downloads)
    result=downloaded_media(service)
    assert 'used' in result['artifact_ids'] and not items['used'][0].local_path.exists() and not items['used'][1].exists()
    assert formal.read_bytes()==b'canonical movie' and items['upload'][1].exists()
    with service.store.connection() as c:
        m=json.loads(c.execute("SELECT metadata_json FROM artifacts WHERE id='used'").fetchone()[0]);assert m['source']==items['used'][2]['source'] and m['rights']==items['used'][2]['rights']
        assert c.execute('SELECT count(*) FROM acceptances').fetchone()[0]==1
    assert downloaded_media(service)['files']==[]


@pytest.mark.parametrize('case',['active','unknown_reference','newer_output','opened','promoted'])
def test_downloads_keep_other_work_references_and_pending_versions(downloads,case,monkeypatch):
    from easel.production.storage_retention import downloaded_media
    completed,library,scope,context,items,_=downloads;service,work,run,_,_,formal,*_=completed
    accept_download_fixture(downloads)
    if case=='active':
        with service.store.transaction() as c:c.execute("UPDATE runs SET state='running' WHERE id=?",(run,))
    if case=='unknown_reference':library.catalog.record_usage(items['used'][0].asset_ref,scope=scope,context=context,reference_id='unmapped-reference')
    if case=='opened':monkeypatch.setattr('easel.production.storage_retention._open_paths',lambda:{str(items['used'][1])})
    if case=='promoted':
        from tests.production.test_materials_core import consent
        library.promote(items['used'][0].asset_ref,visibility=scope,context=context,consent=consent())
    if case=='newer_output':
        with service.store.transaction() as c:c.execute("INSERT INTO artifacts(id,work_id,run_id,kind,storage_ref,digest,size_bytes,displayable,output_revision,created_at) VALUES('out2',?,?,'output',?,?,?,1,2,'later')",(work,run,str(formal.relative_to(service.outputs)),file_sha256(formal),formal.stat().st_size))
    downloaded_media(service)
    assert items['used'][0].local_path.exists() and items['used'][1].exists()


def test_retention_withdrawal_can_redownload_but_explicit_deletion_stays_deleted(downloads):
    from easel.materials.domain import CandidateSource,MediaType
    from tests.production.test_materials_core import rights
    from easel.production.storage_retention import downloaded_media
    completed,library,scope,context,items,source=downloads
    downloaded_media(completed[0]);handle=items['unused'][0]
    again=library.ingest_input(source_root=source,relative_path='unused.png',visibility=scope,context=context,
        media_type=MediaType.IMAGE,source=CandidateSource(kind='stock',provider='pexels',provider_asset_id='unused'),rights=rights())
    assert again.asset_ref==handle.asset_ref and again.local_path.exists()
    assert library.resolve(again.asset_ref,visibility=scope,context=context).local_path.exists()
    from easel.materials.library import MaterialLibraryError
    library.release_reference(again.asset_ref,'input:'+again.asset_ref,visibility=scope,context=context)
    library.delete(again.asset_ref,visibility=scope,context=context)
    with pytest.raises(MaterialLibraryError,match='Deleted input'):
        library.ingest_input(source_root=source,relative_path='unused.png',visibility=scope,context=context,
            media_type=MediaType.IMAGE,source=CandidateSource(kind='stock',provider='pexels',provider_asset_id='unused'),rights=rights())


def test_shared_physical_object_owned_by_upload_is_not_removed(downloads):
    from easel.materials.domain import CandidateSource,MediaType
    from tests.production.test_materials_core import rights
    from easel.production.storage_retention import downloaded_media
    completed,library,scope,context,items,source=downloads
    personal=library.ingest_input(source_root=source,relative_path='used.png',visibility=scope,context=context,
        media_type=MediaType.IMAGE,source=CandidateSource(kind='user_upload',provider_asset_id='personal'),rights=rights())
    assert personal.local_path==items['used'][0].local_path
    accept_download_fixture(downloads);downloaded_media(completed[0])
    assert personal.local_path.exists() and library.resolve(personal.asset_ref,visibility=scope,context=context).local_path.exists()


def test_reclaimed_artifact_is_explicitly_unavailable_and_new_bytes_are_required(downloads):
    from easel.production.artifacts import artifact_file
    from easel.production.storage_retention import downloaded_media
    completed,*_=downloads;service=completed[0]
    downloaded_media(service)
    with service.store.connection() as c:record=dict(c.execute("SELECT * FROM artifacts WHERE id='unused'").fetchone())
    with pytest.raises(ValueError,match='重新取得素材'):artifact_file(service,record)


def test_publication_keeps_credits_after_used_stock_eviction(downloads):
    from easel.production.publication import Publications
    from easel.production.service import WorkService
    from easel.production.storage_retention import downloaded_media
    completed,*_=downloads;service,work,*_=completed
    with service.store.transaction() as c:
        metadata=json.loads(c.execute("SELECT metadata_json FROM artifacts WHERE id='used'").fetchone()[0])
        metadata['attribution']={'credit_text':'Fixture Author — CC BY','source_page':'https://example.test/source','destination':'export_credits'}
        c.execute("UPDATE artifacts SET metadata_json=? WHERE id='used'",(json.dumps(metadata),))
    accept_download_fixture(downloads);downloaded_media(service)
    domain=WorkService(service.store,outputs=service.outputs,profiles=service.outputs.parent/'profiles')
    prepared=Publications(domain,None).prepare(work,'out')
    assert 'Fixture Author — CC BY' in prepared['content']['credits']
    assert 'https://example.test/source' in prepared['content']['credits']
    assert domain.artifact_path('out')[0].is_file()
    from easel.production.errors import ProductionError
    with pytest.raises(ProductionError) as exc:domain.artifact_path('used')
    assert exc.value.code=='material_reclaimed'


def test_unknown_operation_protects_unused_downloads_too(downloads):
    from easel.production.storage_retention import downloaded_media
    completed,_,_,_,items,_=downloads;service,work,run,task,*_=completed
    with service.store.transaction() as c:
        c.execute("INSERT INTO authorization_grants(id,work_id,purpose,plan_revision,services_json,created_at) VALUES('unknown-grant',?,'production',1,'[]','now')",(work,))
        c.execute("INSERT INTO operations(id,work_id,run_id,task_id,grant_id,kind,state,input_hash,request_key,provider,model,mode,config_version,request_json,owner_epoch,created_at,updated_at) VALUES('unknown-op',?,?,?,'unknown-grant','MODEL','unknown','hash','key','fixture','model','normal','v1','{}',1,'now','now')",(work,run,task))
    assert downloaded_media(service)['files']==[]
    assert items['unused'][1].exists() and items['unused'][0].local_path.exists()


def test_work_deletion_after_download_reclaim_does_not_stall_queue(downloads):
    from easel.production.deletion import DeletionService
    from easel.production.storage_retention import downloaded_media
    completed,*_=downloads;service,work,*_=completed
    accept_download_fixture(downloads);downloaded_media(service)
    deletion=DeletionService(service.store,outputs=service.outputs)
    preview=deletion.preview(work)
    deletion.execute('delete-after-eviction',work,service.store.get_work(work)['revision'],preview['preview_hash'])
    deletion.reconcile_cleanup()
    with service.store.connection() as c:
        assert c.execute("SELECT state FROM cleanup_jobs WHERE artifact_id='used'").fetchone()[0]=='deleted'
