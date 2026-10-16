"""Register immutable files and dependency edges under a fenced task transaction."""
from __future__ import annotations
import shutil
from pathlib import Path
from .media import file_sha256, local_path
from .service import encode, now, new_id, row


def register_file(service,ctx,source:Path,*,kind:str,media_type:str,metadata:dict,dependencies=(),output=False):
    checksum=file_sha256(source)
    root=service.outputs/'works'/ctx.work_id
    root.mkdir(parents=True,exist_ok=True)
    folder=root/'artifacts';folder.mkdir(exist_ok=True)
    if root.is_symlink() or folder.is_symlink() or not folder.resolve().is_relative_to(service.outputs.resolve()):
        raise ValueError('artifact storage boundary changed')
    target=folder/(checksum+source.suffix)
    if target.exists():
        if target.is_symlink() or file_sha256(target)!=checksum:raise ValueError('artifact content changed')
    else:
        temp=folder/(new_id()+'.tmp');shutil.copyfile(source,temp);temp.replace(target)
    with ctx.transaction() as conn:
        if not target.is_file() or target.is_symlink() or file_sha256(target)!=checksum:
            raise ValueError('artifact storage changed before registration')
        existing=conn.execute('SELECT * FROM artifacts WHERE work_id=? AND run_id=? AND kind=? AND digest=? AND deleted_at IS NULL',(ctx.work_id,ctx.run_id,kind,checksum)).fetchone()
        if existing:return dict(existing)
        revision=conn.execute('SELECT COALESCE(MAX(output_revision),0)+1 FROM artifacts WHERE work_id=?',(ctx.work_id,)).fetchone()[0] if output else None
        id=new_id()
        conn.execute('INSERT INTO artifacts(id,work_id,run_id,kind,storage_ref,digest,size_bytes,media_type,displayable,output_revision,metadata_json,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
            (id,ctx.work_id,ctx.run_id,kind,target.relative_to(service.outputs).as_posix(),checksum,target.stat().st_size,media_type,1,revision,encode({'schema_version':1,**metadata}),now()))
        for dependency in dependencies:
            value=row(conn,'artifacts',dependency)
            if value['work_id']!=ctx.work_id:raise ValueError('cross-work artifact dependency')
            conn.execute('INSERT INTO artifact_edges(artifact_id,dependency_id,role) VALUES (?,?,?)',(id,dependency,'source'))
        service._event(conn,ctx.work_id,'artifact_created',{'artifact_id':id,'kind':kind,'output_revision':revision},run_id=ctx.run_id)
        return row(conn,'artifacts',id)


def artifact_file(service,record):
    if record.get('deleted_at'):raise ValueError('artifact has been deleted')
    with service.store.connection() as conn:
        if row(conn,'works',record['work_id']).get('deleted_at'):raise ValueError('work has been deleted')
    path=local_path(service.outputs,record['storage_ref'])
    if file_sha256(path)!=record['digest']:raise ValueError('registered media changed')
    return path
