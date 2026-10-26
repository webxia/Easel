"""Original file publishing cover sources; no Work or acceptance is created."""
import hashlib
import re
from pathlib import Path
from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ConfigDict
from easel.production.publication_covers import encode_cover, MAX_IMAGE_BYTES
from easel.production.media import file_sha256
from easel.production.service import fail


def file_cover_path(outputs, cover):
    if (not isinstance(cover,dict) or set(cover)!={'digest','width','height'} or
            not isinstance(cover.get('digest'),str) or not re.fullmatch('[a-f0-9]{64}',cover['digest'])):
        fail('invalid_cover','封面引用无效')
    folder=Path(outputs)/'_publish'/'covers'
    path=folder/(cover['digest']+'.jpg')
    if any(p.is_symlink() for p in (folder,folder.parent,path)):
        fail('invalid_cover','封面存储不可用')
    try:
        from PIL import Image
        if file_sha256(path)!=cover['digest']:raise ValueError()
        with Image.open(path) as image:
            if image.size!=(cover['width'],cover['height']):raise ValueError()
    except (OSError,ValueError):fail('cover_changed','封面缺失或已变化，请重新选择',409)
    return path


def create_file_cover_router(outputs_provider, resolve):
    def public_source(locator):
        from easel.production.media import local_path
        from pathlib import PurePosixPath
        parts=PurePosixPath(locator).parts
        if not parts or any(part.startswith(('.', '_')) for part in parts) or parts[0] in {'works','analytics','wechat'}:
            fail('invalid_cover','请从公共媒体列表选择来源')
        resolve(locator)  # Preserve the original app's access boundary too.
        try:return local_path(Path(outputs_provider()),locator)
        except ValueError:fail('invalid_cover','媒体来源不可用')
    router=APIRouter(prefix='/api/publish/covers')
    def store(data):
        payload,width,height=encode_cover(data)
        cover={'digest':hashlib.sha256(payload).hexdigest(),'width':width,'height':height}
        folder=Path(outputs_provider())/'_publish'/'covers'
        if folder.is_symlink() or folder.parent.is_symlink():fail('invalid_cover','封面存储不可用')
        folder.mkdir(parents=True,exist_ok=True)
        path=folder/(cover['digest']+'.jpg')
        if path.is_symlink():fail('invalid_cover','封面存储不可用')
        if not path.exists():
            # Content-addressed writes are idempotent; no user file is overwritten.
            import tempfile
            with tempfile.NamedTemporaryFile(dir=folder,delete=False) as f:f.write(payload);temp=Path(f.name)
            temp.replace(path)
        return cover
    class Source(BaseModel):
        model_config=ConfigDict(extra='forbid')
        library_path:str|None=None
        video_path:str|None=None
        at:float|None=Field(default=None,ge=0,allow_inf_nan=False)
    @router.post('')
    def source(request:Source):
        if request.library_path is not None and request.video_path is None and request.at is None:
            path=public_source(request.library_path)
            if path.stat().st_size>MAX_IMAGE_BYTES:fail('cover_too_large','图片不能超过20MB')
            return store(path.read_bytes())
        if request.video_path is not None and request.library_path is None and request.at is not None:
            from easel.production.inspection import observe_media
            import base64
            path=public_source(request.video_path)
            try:
                blocks,_,_=observe_media(path,max_frames=1,frame_times=(request.at,))
                block=next(b for b in blocks if b.get('type')=='image_url')
            except (ValueError,OSError,StopIteration):fail('cover_frame_unavailable','无法截取此时点，请选择视频内的其他时间')
            return store(base64.b64decode(block['image_url']['url'].split(',',1)[1]))
        fail('invalid_cover','请选择图片或视频内的时点')
    @router.post('/upload')
    def upload(file:UploadFile=File(...)):
        return store(file.file.read(MAX_IMAGE_BYTES+1))
    @router.get('/{checksum}')
    def preview(checksum:str):
        if not re.fullmatch('[a-f0-9]{64}',checksum):fail('invalid_cover','封面引用无效')
        from PIL import Image
        path=Path(outputs_provider())/'_publish'/'covers'/(checksum+'.jpg')
        if path.is_symlink():fail('invalid_cover','封面存储不可用')
        try:
            with Image.open(path) as im:width,height=im.size
        except OSError:fail('cover_changed','封面不可用',404)
        return FileResponse(file_cover_path(outputs_provider(),{'digest':checksum,'width':width,'height':height}),media_type='image/jpeg')
    return router
