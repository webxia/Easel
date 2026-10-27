"""Daily byte reclamation; retain final media, provenance and domain records."""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import time
from contextlib import closing
from .editors.ffmpeg import _lock
from .media import file_sha256, atomic_json

TERMINAL = ('succeeded', 'failed', 'cancelled', 'superseded')
DAILY_INTERVAL = 86400


def _safe(root, path):
    try:
        rel=path.relative_to(root)
        return not root.is_symlink() and all(not (root.joinpath(*rel.parts[:n])).is_symlink() for n in range(1,len(rel.parts)+1))
    except ValueError:return False


def _open_paths():
    executable=shutil.which('lsof')
    if not executable:return None
    try:
        result=subprocess.run([executable,'-Fn'],capture_output=True,timeout=20)
        if result.returncode not in (0,1):return None
        return {line[1:] for line in result.stdout.decode(errors='replace').splitlines() if line.startswith('n/')}
    except (OSError,subprocess.TimeoutExpired):return None


def _remove(path, root, report):
    if not _safe(root,path) or not path.is_file():return
    before=path.stat()
    digest=file_sha256(path)
    after=path.stat()
    if (before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):return
    path.unlink()
    report.append({'path':str(path.relative_to(root)),'bytes':before.st_size,'sha256':digest})


def completed_render_scratch(service, *, limit=16, dry_run=False):
    root=service.outputs.absolute();folder=root/'_production'/'renders';removed=[];skipped=[]
    if not _safe(root,folder) or not folder.is_dir():return {'files':removed,'skipped':skipped}
    for path in sorted(folder.iterdir()):
        if len({r['job'] for r in removed})>=limit:break
        if not _safe(root,path) or not path.is_dir() or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,95}',path.name):continue
        marker=path/'scratch-reclaimed.json'
        try:
            with _lock(path/'registration.lock',blocking=False), _lock(path/'execution.lock',blocking=False), _lock(path/'terminal.lock',blocking=False):
                if any(not _safe(root,path/name) or not (path/name).is_file() or (path/name).stat().st_size>8*1024*1024
                       for name in ('job.json','project.json','output.json')):continue
                job=json.loads((path/'job.json').read_text());project=json.loads((path/'project.json').read_text());output=json.loads((path/'output.json').read_text())
                if job['job_id']!=path.name or job['status']!='completed':continue
                work=project['work_id']
                with service.store.transaction() as conn:
                    task=conn.execute('SELECT t.state,r.state AS run_state FROM tasks t JOIN runs r ON r.id=t.run_id WHERE t.id=? AND t.work_id=? AND t.kind=\'render\'',(path.name,work)).fetchone()
                    if not task or task['state']!='succeeded' or task['run_state'] not in TERMINAL:continue
                    if conn.execute("SELECT 1 FROM runs WHERE work_id=? AND state NOT IN ('succeeded','failed','cancelled','superseded')",(work,)).fetchone():continue
                    if conn.execute("SELECT 1 FROM operations WHERE work_id=? AND state IN ('reserved','sending','submitted','unknown')",(work,)).fetchone():continue
                    records=[dict(r) for r in conn.execute('SELECT storage_ref,digest,kind,metadata_json FROM artifacts WHERE deleted_at IS NULL')]
                    finals=[r for r in records if r['kind']=='output' and json.loads(r['metadata_json']).get('render_job_id')==path.name]
                    if not any(_safe(root,root/r['storage_ref']) and (root/r['storage_ref']).is_file() and not (root/r['storage_ref']).resolve().is_relative_to(path.resolve()) and r['digest']==output['sha256']==file_sha256(root/r['storage_ref']) for r in finals):continue
                    references={(root/r['storage_ref']).resolve() for r in records}
                    references.update((root/r[0]).resolve() for r in conn.execute("SELECT source_ref FROM work_inputs WHERE source_ref IS NOT NULL"))
                    protected={Path(output[k]).resolve() for k in ('video_path','caption_base_path') if output.get(k)}|references
                    originals={r['digest']:root/r['storage_ref'] for r in records if not (root/r['storage_ref']).resolve().is_relative_to(path.resolve())}
                    reclaimed={r['digest'] for r in records if json.loads(r['metadata_json']).get('local_media_retention',{}).get('state')=='reclaimed'}
                    reclaimed-={r['digest'] for r in records if json.loads(r['metadata_json']).get('local_media_retention',{}).get('state')!='reclaimed'}
                    candidates=[]
                    for sub,pattern in [('scenes',r'\d{4}\.(mp4|json)'),('captions',r'frame-\d+\.png'),('assets',r'[a-f0-9]{64}\.[A-Za-z0-9]+')]:
                        directory=path/sub
                        if not _safe(root,directory) or not directory.is_dir():continue
                        for item in directory.iterdir():
                            if not _safe(root,item) or not item.is_file() or not re.fullmatch(pattern,item.name) or item.resolve() in protected:continue
                            if sub=='assets':
                                digest=item.stem;source=originals.get(digest)
                                if file_sha256(item)!=digest:continue
                                if digest not in reclaimed and (not source or not _safe(root,source) or not source.is_file() or file_sha256(source)!=digest):continue
                            candidates.append(item)
                    for item in candidates:
                        if dry_run:removed.append({'path':str(item.relative_to(root)),'bytes':item.stat().st_size,'job':path.name})
                        else:
                            entries=[];_remove(item,root,entries)
                            removed.extend({**entry,'job':path.name} for entry in entries)
                    if not dry_run:
                        atomic_json(marker,{'version':1,'at':time.time(),'removed_files':len(candidates),'retained':['final','caption_base','project','receipts','logs']})
        except (OSError,ValueError,KeyError,TypeError,sqlite3.Error):skipped.append(path.name)
    return {'files':removed,'skipped':skipped}


def redundant_backups(service, *, keep=2, min_age=3600, dry_run=False):
    if keep<2:raise ValueError('at least two production recovery backups are required')
    root=service.outputs.absolute();opened=_open_paths();eligible=[];skipped=[];removed=[]
    if opened is None:return {'files':[],'retained':[],'skipped':['open_file_inventory_unavailable']}
    with service.store.connection() as conn:
        identities={tuple(r) for r in conn.execute('SELECT id,input_hash FROM operations')}
        works={r[0] for r in conn.execute('SELECT id FROM works')}
        plans={tuple(r) for r in conn.execute('SELECT work_id,revision,plan_hash FROM plan_revisions')}
    for folder in [root/'_debug',root/'_diagnostics',root/'_production'/'backups']:
        if not _safe(root,folder) or not folder.is_dir():continue
        for base,dirs,files in os.walk(folder,followlinks=False):
            dirs[:]=[d for d in dirs if _safe(root,Path(base)/d)]
            for name in files:
                path=Path(base)/name
                if path.suffix not in ('.sqlite3','.db') or not _safe(root,path):continue
                sidecars=[Path(str(path)+s) for s in ('-wal','-shm','-journal')]
                wal,journal=sidecars[0],sidecars[2]
                if (os.path.samefile(path,service.store.path) or any(str(p) in opened for p in [path,*sidecars])
                    or journal.exists() or (wal.exists() and wal.stat().st_size>0)):continue
                if time.time()-path.stat().st_mtime<min_age:continue
                try:
                    with closing(sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1',uri=True)) as backup:
                        bw={r[0] for r in backup.execute('SELECT id FROM works')}
                        bo=set(backup.execute('SELECT id,input_hash FROM operations'))
                        bp=set(backup.execute('SELECT work_id,revision,plan_hash FROM plan_revisions'))
                        if not bw or not bw<=works or not bo<=identities or not bp<=plans:
                            skipped.append(str(path.relative_to(root)));continue
                    eligible.append(path)
                except sqlite3.Error:continue
    eligible.sort(key=lambda p:p.stat().st_mtime_ns,reverse=True)
    retained=[]
    for path in eligible:
        if len(retained)<keep:
            try:
                with closing(sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1',uri=True)) as backup:
                    if backup.execute('PRAGMA quick_check').fetchone()[0]!='ok':continue
                retained.append(str(path.relative_to(root)))
            except sqlite3.Error:continue
        else:
            if dry_run:removed.append({'path':str(path.relative_to(root)),'bytes':path.stat().st_size})
            else:
                _remove(path,root,removed)
                if not path.exists():
                    for suffix in ('-wal','-shm'):
                        sidecar=Path(str(path)+suffix)
                        if sidecar.exists():_remove(sidecar,root,removed)
    return {'files':removed,'retained':retained,'skipped':skipped}


def storage_maintenance(service, *, dry_run=False, min_backup_age=3600, render_limit=16, due_only=False):
    root=service.outputs.absolute();private=root/'_production'
    if not _safe(root,private) or not private.is_dir():return {'removed_bytes':0,'skipped':'unsafe_root'}
    try:
        with _lock(private/'storage-maintenance.lock',blocking=False):
            schedule=private/'storage-cleanup-schedule.json';now=time.time()
            if not _safe(root,schedule):return {'removed_bytes':0,'skipped':'unsafe_schedule'}
            if due_only and schedule.exists():
                try:next_at=float(json.loads(schedule.read_text())['next_at'])
                except (ValueError,KeyError,TypeError,OSError):return {'removed_bytes':0,'skipped':'invalid_schedule'}
                if next_at>now:return {'removed_bytes':0,'skipped':'not_due','next_at':next_at}
            if not dry_run:atomic_json(schedule,{'version':1,'state':'running','last_at':now,'next_at':now+DAILY_INTERVAL})
            from .deletion import DeletionService
            deletion_queue={} if dry_run else DeletionService(service.store,outputs=service.outputs).reconcile_cleanup(limit=1000)
            downloads=downloaded_media(service,dry_run=dry_run)
            renders=completed_render_scratch(service,limit=render_limit,dry_run=dry_run)
            backups=redundant_backups(service,min_age=min_backup_age,dry_run=dry_run)
            files=downloads['files']+renders['files']+backups['files'];result={'at':time.time(),'next_at':time.time()+DAILY_INTERVAL,'dry_run':dry_run,'removed_bytes':sum(x['bytes'] for x in files),'downloads':downloads,'renders':renders,'backups':backups,'deletion_queue':deletion_queue}
            if not dry_run:atomic_json(schedule,{'version':1,'state':'completed','last_at':result['at'],'next_at':result['next_at']})
            if not dry_run and files:
                # One bounded receipt; no recursive backups of the authority.
                atomic_json(private/'storage-cleanup-latest.json',result)
            return result
    except BlockingIOError:return {'removed_bytes':0,'skipped':'maintenance_busy'}


def downloaded_media(service, *, dry_run=False):
    """Release stock bytes only; keep artifact/provenance/usage descriptions."""
    from easel.materials.library import MaterialLibraryCatalog
    from .service import encode
    root=service.outputs.absolute();library_root=root/'_production/materials'
    result={'files':[],'artifact_ids':[],'skipped':[]}
    if not _safe(root,library_root) or not (library_root/'catalog.db').is_file():return result
    opened=_open_paths()
    if opened is None:return {**result,'skipped':['open_file_inventory_unavailable']}
    catalog=MaterialLibraryCatalog(library_root)
    with service.store.connection() as conn:
        works={r['id']:dict(r) for r in conn.execute('SELECT * FROM works')}
        rows=[dict(r) for r in conn.execute('SELECT * FROM artifacts WHERE deleted_at IS NULL')]
        busy={r[0] for r in conn.execute("SELECT work_id FROM runs WHERE state NOT IN ('succeeded','failed','cancelled','superseded') UNION SELECT work_id FROM operations WHERE state IN ('reserved','sending','submitted','unknown')")}
        used={r[0] for r in conn.execute("""WITH RECURSIVE dependencies(id) AS (
            SELECT id FROM artifacts WHERE deleted_at IS NULL AND kind IN ('output','edit_project')
            UNION SELECT trial_artifact_id FROM director_revisions WHERE trial_artifact_id IS NOT NULL
            UNION SELECT e.dependency_id FROM artifact_edges e JOIN dependencies d ON d.id=e.artifact_id)
            SELECT id FROM dependencies""")}
        inputs={str((root/r[0]).resolve()) for r in conn.execute('SELECT source_ref FROM work_inputs WHERE source_ref IS NOT NULL')}
        pinned={r[0] for r in conn.execute("""WITH RECURSIVE pins(id) AS (
            SELECT trial_artifact_id FROM director_revisions WHERE trial_artifact_id IS NOT NULL
            UNION SELECT e.dependency_id FROM artifact_edges e JOIN pins p ON p.id=e.artifact_id)
            SELECT id FROM pins""")}
        accepted={r[0] for r in conn.execute('SELECT output_id FROM acceptances')}
    valid={};confirmed={}
    for wid,w in works.items():
        if wid in busy or w.get('deleted_at') or w['state'] not in ('reviewable','preview_needs_fix','cancelled'):continue
        outputs=[r for r in rows if r['work_id']==wid and r['kind']=='output']
        good=[r for r in outputs if _safe(root,root/r['storage_ref']) and (root/r['storage_ref']).is_file() and file_sha256(root/r['storage_ref'])==r['digest']]
        # Cancelled production may release unused candidates, never paid/used
        # inputs. All other works need a real final output before release.
        if not good and w['state']!='cancelled':continue
        valid[wid]=w['revision']
        chosen=next((r for r in good if r['id']==w['accepted_output_id'] and r['id'] in accepted),None)
        confirmed[wid]=bool(chosen and chosen['output_revision']==max(r['output_revision'] or 0 for r in outputs))
    groups={}
    for record in rows:
        metadata=json.loads(record['metadata_json']);ref=metadata.get('asset_ref')
        if ref:groups.setdefault(ref,[]).append((record,metadata))
    for ref,members in groups.items():
        if any(r['work_id'] not in valid or r['kind'] not in ('image','video','audio')
               or not isinstance(m.get('source'),dict) or m['source'].get('kind')!='stock' or m.get('input_id')
               or r['id'] in pinned or m.get('voice') or m.get('candidate_role')=='voice'
               or any(isinstance(u,dict) and u.get('role')=='voice' for u in (m.get('material_uses') or []))
               or str((root/r['storage_ref']).resolve()) in inputs
               or (r['id'] in used and not confirmed.get(r['work_id'])) for r,m in members):continue
        paths={root/r['storage_ref'] for r,m in members}
        if any(not _safe(root,p) or str(p) in opened or (p.exists() and file_sha256(p)!=next(r['digest'] for r,m in members if root/r['storage_ref']==p)) for p in paths):continue
        try:
            with catalog._connect() as db:
                original=db.execute('SELECT source_work_id,record_json FROM library_assets WHERE library_asset_id=?',(ref,)).fetchone()
            if not original or original['source_work_id'] not in valid:continue
            original_data=json.loads(original['record_json'])
            if str(library_root/original_data['physical_locator']) in opened:continue
            if (original_data.get('reusable') or original_data.get('owner_shared') or original_data.get('promotion_consent')
                or original_data.get('input_purpose')!='production' or original_data.get('asset',{}).get('source',{}).get('kind')!='stock'
                or (original_data.get('lifecycle_status')=='DELETED' and not original_data.get('reclaimed_at'))):continue
            refs={(r['id'],r['work_id']) for r,m in members}
            with catalog._connect() as db:
                actual={tuple(r) for r in db.execute('SELECT reference_id,work_id FROM library_asset_usage WHERE library_asset_id=?',(ref,))}
            if not actual<=refs|{('input:'+ref,original['source_work_id'])}:continue
            with service.store.transaction() as conn:
                scope={r['work_id'] for r,m in members}|{original['source_work_id']}
                if any(conn.execute('SELECT revision FROM works WHERE id=?',(wid,)).fetchone()[0]!=valid[wid] for wid in scope):continue
                if any(conn.execute("SELECT 1 FROM runs WHERE work_id=? AND state NOT IN ('succeeded','failed','cancelled','superseded')",(wid,)).fetchone()
                       or conn.execute("SELECT 1 FROM operations WHERE work_id=? AND state IN ('reserved','sending','submitted','unknown')",(wid,)).fetchone() for wid in scope):continue
                if dry_run:
                    result['artifact_ids'].extend(r['id'] for r,m in members)
                    for p in paths:
                        if p.is_file():result['files'].append({'path':str(p.relative_to(root)),'bytes':p.stat().st_size})
                    continue
                if not catalog.retire_download(ref,references=refs,source_work_id=original['source_work_id']):
                    result['skipped'].append(ref);continue
                for record,metadata in members:
                    metadata.setdefault('local_media_retention',{'state':'reclaimed','at':time.time(),'policy':'daily-downloads-v1'})
                    conn.execute('UPDATE artifacts SET metadata_json=? WHERE id=?',(encode(metadata),record['id']))
                    result['artifact_ids'].append(record['id'])
                for path in paths:
                    others=conn.execute('SELECT metadata_json FROM artifacts WHERE storage_ref=? AND deleted_at IS NULL',(str(path.relative_to(root)),)).fetchall()
                    if all(json.loads(r[0]).get('local_media_retention',{}).get('state')=='reclaimed' for r in others):
                        _remove(path,root,result['files'])
        except (OSError,ValueError,KeyError,sqlite3.Error):result['skipped'].append(ref)
    if not dry_run:
        # Catalog deletion checks shared objects and references again under its
        # own transaction, and retains source/license JSON tombstones.
        with catalog._connect() as db:
            deleted=[(r[0],library_root/r[0]) for r in db.execute("SELECT DISTINCT physical_locator FROM library_assets WHERE lifecycle_status='DELETED'")]
        before={locator:{'path':str(p.relative_to(root)),'bytes':p.stat().st_size} for locator,p in deleted if _safe(root,p) and p.is_file()}
        for locator in catalog.collect_deleted():
            if locator in before:result['files'].append(before[locator])
    return result
