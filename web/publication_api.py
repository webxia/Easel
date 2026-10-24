"""Accepted-output routes; existing app local-write guard applies."""
from typing import Literal
from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from easel.production.publication import Publications
from easel.publication_bilibili import BilibiliAdapter


class Source(BaseModel):
    model_config=ConfigDict(extra='forbid')
    work_id: str
    output_id: str


class Edit(BaseModel):
    model_config=ConfigDict(extra='forbid')
    revision: int=Field(gt=0)
    content: dict


class Confirm(BaseModel):
    model_config=ConfigDict(extra='forbid')
    revision: int=Field(gt=0)
    confirmation_hash: str


class ResolveAbsent(Confirm):
    attempt_id: str
    confirmed_absent: Literal[True]


class Cancel(BaseModel):
    model_config=ConfigDict(extra='forbid')
    revision: int=Field(gt=0)


class CoverSource(Cancel):
    library_path: str | None = None
    at: float | None = Field(default=None, ge=0, allow_inf_nan=False)


def create_publication_router(service_provider,adapter_provider=None):
    router=APIRouter(prefix='/api/production/publications')
    def service():
        production=service_provider()
        return Publications(production,adapter_provider() if adapter_provider else BilibiliAdapter(production.outputs.parent))

    @router.get('')
    def listing(work_id:str|None=None):return service().list(work_id)

    @router.post('/prepare')
    def prepare(request:Source):return service().prepare(request.work_id,request.output_id)

    @router.post('/account')
    def account():return service().adapter.account()

    @router.get('/{identity}')
    def get(identity:str):return service().get(identity)

    @router.put('/{identity}')
    def save(identity:str,request:Edit):return service().save(identity,request.revision,request.content)

    @router.post('/{identity}/cancel')
    def cancel(identity:str,request:Cancel):return service().cancel(identity,request.revision)

    @router.post('/{identity}/covers')
    def cover(identity:str,request:CoverSource):
        from easel.production.publication_covers import prepare_cover
        return prepare_cover(service(),identity,request.revision,library_path=request.library_path,at=request.at)

    @router.post('/{identity}/covers/upload')
    def upload_cover(identity:str,revision:int=Form(...),file:UploadFile=File(...)):
        from easel.production.publication_covers import prepare_cover, MAX_IMAGE_BYTES
        return prepare_cover(service(),identity,revision,data=file.file.read(MAX_IMAGE_BYTES+1))

    @router.get('/{identity}/covers/{checksum}')
    def preview_cover(identity:str,checksum:str):
        from easel.production.publication_covers import cover_path
        from easel.production.media import local_path
        from easel.production.service import fail
        from PIL import Image
        import re
        pub=service();draft=pub.get(identity)
        if not re.fullmatch(r'[a-f0-9]{64}',checksum):fail('invalid_cover','封面引用无效')
        try:
            path=local_path(pub.service.outputs,f'_production/publication-covers/{identity}/{checksum}.jpg')
            with Image.open(path) as image:width,height=image.size
        except (ValueError,OSError):fail('cover_changed','封面不可用',404)
        path=cover_path(pub,draft,{'digest':checksum,'width':width,'height':height})
        return FileResponse(path,media_type='image/jpeg',headers={'Cache-Control':'no-store'})

    @router.post('/{identity}/submit')
    def submit(identity:str,request:Confirm):return service().submit(identity,request.revision,request.confirmation_hash)

    @router.post('/{identity}/resolve-absent')
    def resolve_absent(identity:str,request:ResolveAbsent):
        return service().resolve_absent(identity,request.revision,request.confirmation_hash,request.attempt_id,request.confirmed_absent)

    @router.post('/{identity}/reconcile')
    def reconcile(identity:str):return service().reconcile(identity)
    return router
