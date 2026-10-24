"""Read-only operating totals and explicit, locked render-cache reclamation."""
import json
import re
import shutil
from pathlib import Path
from .contracts import fingerprint
from .errors import ProductionError
from .media import file_sha256
from .editors.ffmpeg import _lock


def operating_summary(service):
    with service.store.connection() as conn:
        calls=[dict(r) for r in conn.execute('SELECT kind,state,COUNT(*) AS count FROM operations GROUP BY kind,state')]
        tasks=[dict(r) for r in conn.execute("SELECT kind,state,COUNT(*) AS count,SUM(MAX(0,(julianday(updated_at)-julianday(created_at))*86400)) AS elapsed_seconds FROM tasks GROUP BY kind,state")]
        assets=conn.execute('SELECT COUNT(*),COALESCE(SUM(size_bytes),0) FROM artifacts WHERE deleted_at IS NULL').fetchone()
    disk=shutil.disk_usage(service.outputs)
    return {'operations':calls,'tasks':tasks,'elapsed_basis':'created_to_updated_includes_waiting',
        'registered_artifacts':assets[0],'registered_bytes':assets[1],'free_bytes':disk.free,
        'usage_cost':None,'usage_note':'Missing provider usage is unknown, not zero.',
        'automatic_cleanup':False}


def _folder(service,job_id):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,95}',job_id):raise ProductionError('invalid_input','无效渲染任务')
    path=service.outputs/'_production'/'renders'/job_id
    if not path.is_dir() or any(p.is_symlink() for p in (path,path.parent,path.parent.parent,service.outputs)):
        raise ProductionError('cache_unavailable','渲染目录不可安全检查')
    return path


def _preview(service,conn,path):
    def read(name):
        p=path/name
        if p.is_symlink() or p.stat().st_size>4*1024*1024:raise ValueError('invalid render metadata')
        return json.loads(p.read_text())
    job=read('job.json');project=read('project.json');work_id=project['work_id']
    if job['job_id']!=path.name:raise ValueError('render identity mismatch')
    work=conn.execute('SELECT * FROM works WHERE id=?',(work_id,)).fetchone()
    if not work or work['accepted_output_id'] or job['status']!='completed':
        raise ProductionError('cache_protected','仅可清理未接受作品的已完成渲染镜头缓存')
    if conn.execute("SELECT 1 FROM runs WHERE work_id=? AND state NOT IN ('succeeded','failed','cancelled','superseded')",(work_id,)).fetchone() or conn.execute("SELECT 1 FROM operations WHERE work_id=? AND state IN ('reserved','sending','submitted','unknown')",(work_id,)).fetchone():
        raise ProductionError('cache_protected','作品在途或有待核实调用，保留全部恢复依据')
    output=read('output.json')
    protected_paths={Path(output[k]).resolve() for k in ('video_path','caption_base_path') if output.get(k)}
    references={r[0] for r in conn.execute('SELECT storage_ref FROM artifacts WHERE deleted_at IS NULL')}
    folder=path/'scenes';entries=[]
    if folder.is_symlink():raise ProductionError('cache_protected','缓存目录不能是符号链接')
    if folder.is_dir():
        for item in sorted(folder.iterdir()):
            if item.is_symlink() or not item.is_file() or not re.fullmatch(r'\d{4}\.(mp4|json)',item.name):continue
            if item.resolve() in protected_paths or item.relative_to(service.outputs).as_posix() in references:continue
            entries.append({'name':item.name,'bytes':item.stat().st_size,'sha256':file_sha256(item)})
    result={'job_id':job['job_id'],'work_id':work_id,'files':entries,'bytes':sum(e['bytes'] for e in entries),
        'retained':['final video','caption base','source assets','project','receipts','checkpoints','backups']}
    return {**result,'preview_hash':fingerprint(result)}


def render_cache(service,job_id,*,preview_hash=None):
    path=_folder(service,job_id)
    try:
        with _lock(path/'execution.lock',blocking=False), _lock(path/'terminal.lock',blocking=False):
            with service.store.transaction() as conn:
                preview=_preview(service,conn,path)
                if preview_hash is None:return preview
                if preview_hash!=preview['preview_hash']:raise ProductionError('stale_revision','缓存状态已改变，请重新查看清理预览')
                # Only reconstructible scene files are eligible. No directory sweep.
                for item in preview['files']:(path/'scenes'/item['name']).unlink()
                service.store.append_event(conn,preview['work_id'],'render_cache_reclaimed',{'job_id':job_id,'bytes':preview['bytes'],'count':len(preview['files'])})
                return {'job_id':job_id,'removed_bytes':preview['bytes'],'removed_files':len(preview['files'])}
    except BlockingIOError:
        raise ProductionError('cache_busy','渲染仍在使用缓存，请稍后重新预览') from None
    except (OSError,ValueError,KeyError,TypeError):
        raise ProductionError('cache_unavailable','缓存元数据或文件不完整，未扩大清理范围') from None
