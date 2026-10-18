"""Read-only attachment validation shared with pre-Work conversation staging."""
import hashlib
from pathlib import Path
from .production.service import fail


def validate_attachment(service,session,attachment):
    rel=Path(attachment.get('path',''));scope=hashlib.sha256(session.strip().encode()).hexdigest()[:20]
    if rel.is_absolute() or '..' in rel.parts or len(rel.parts)!=4 or rel.parts[:2]!=('_inbox',scope):fail('permission_missing','附件不属于当前会话',403)
    expected=hashlib.sha256((scope+'\0'+rel.as_posix()).encode()).hexdigest()[:24]
    path=service.outputs/rel
    if attachment.get('id')!=expected or not path.is_file() or service.outputs/'_inbox'/scope not in path.resolve().parents or any(p.is_symlink() for p in [path,*list(path.parents)[:3]]):fail('permission_missing','附件句柄或路径无效',403)
    return path
