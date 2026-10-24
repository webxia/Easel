"""Production routes, mounted behind the existing application's local-write guard."""
from __future__ import annotations

import asyncio
import json
from typing import Callable, Literal

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sse_starlette.sse import EventSourceResponse

from easel.production.errors import ProductionError
from easel.production.catalog import CreativeCatalog
from easel.production.service import WorkService


class Command(BaseModel):
    model_config = ConfigDict(extra='forbid')
    command_id: str = Field(min_length=1, max_length=128, pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]*$')
    expected_revision: int | None = Field(default=None, gt=0, strict=True)
    payload: dict = Field(default_factory=dict)


class StockPreviewSearch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    query: str = Field(min_length=1, max_length=140)
    limit: int = Field(default=10, ge=1, le=20)


def create_router(service_provider: Callable[[], WorkService]) -> APIRouter:
    router = APIRouter(prefix='/api/production')

    def command(action, request: Command, work_id=None, **extra):
        return service_provider().command(action,{**request.payload,**extra},command_id=request.command_id,
            work_id=work_id,expected_revision=request.expected_revision)

    @router.get('/capabilities')
    def service_capabilities():
        from easel.production.configuration import capabilities
        from easel.production.runtime_readiness import backend_code_freshness
        return {**capabilities(service_provider().outputs.parent),
                'backend':backend_code_freshness()}

    @router.get('/maintenance/summary')
    def maintenance_summary():
        from easel.production.maintenance import operating_summary
        return operating_summary(service_provider())

    @router.get('/maintenance/render-cache/{job_id}')
    def cache_preview(job_id:str):
        from easel.production.maintenance import render_cache
        return render_cache(service_provider(),job_id)

    @router.post('/maintenance/render-cache/{job_id}')
    def cache_reclaim(job_id:str,request:Command):
        from easel.production.maintenance import render_cache
        value=request.payload.get('preview_hash')
        if not isinstance(value,str) or not value:raise ProductionError('invalid_input','请先取得具体缓存清理预览')
        return render_cache(service_provider(),job_id,preview_hash=value)

    @router.post('/material-sources/unsplash/preview-search')
    def unsplash_preview_search(request: StockPreviewSearch):
        # Read-only discovery from an explicit UI command, never background supply.
        # No asset is downloaded, tracked or entered into the material catalog.
        from easel.direct_api import read_settings
        from easel.production.providers.stock import StockUnavailable
        from easel.production.providers.unsplash import UnsplashDiscoveryProvider
        service = service_provider()
        settings = read_settings(service.outputs.parent / '.env')
        provider = UnsplashDiscoveryProvider(settings.get('UNSPLASH_ACCESS_KEY', ''))
        try:
            results = provider.search(request.query, limit=request.limit)
        except StockUnavailable as exc:
            raise ProductionError('source_unavailable', 'Unsplash 预览检索不可用；不会自动下载或重复请求', status_code=503) from exc
        return {'provider': provider.provider_id, 'production_ready': False, 'results': list(results)}

    @router.get('/library')
    def accepted_library(scope: Literal['accepted', 'unaccepted'] = 'accepted'):
        service=service_provider()
        with service.store.connection() as conn:
            if scope == 'unaccepted':
                return [dict(r) for r in conn.execute("""SELECT w.id AS work_id,w.title,w.state,
                    w.revision,a.id AS artifact_id,a.output_revision
                    FROM works w LEFT JOIN artifacts a ON a.id=(
                        SELECT id FROM artifacts WHERE work_id=w.id AND kind='output'
                        AND output_revision IS NOT NULL AND deleted_at IS NULL AND displayable=1
                        ORDER BY output_revision DESC,id DESC LIMIT 1)
                    WHERE w.deleted_at IS NULL AND w.accepted_output_id IS NULL
                    ORDER BY w.updated_at DESC,w.id""")]
            return [dict(r) for r in conn.execute('''SELECT w.id AS work_id,w.title,a.id AS artifact_id,a.output_revision
                FROM works w JOIN artifacts a ON a.id=w.accepted_output_id AND a.work_id=w.id
                WHERE w.deleted_at IS NULL AND a.deleted_at IS NULL AND a.displayable=1
                ORDER BY w.updated_at DESC''')]

    @router.get('/works')
    def list_works(after:str|None=None,limit:int=30,state:str|None=None,profile_ref:str|None=None,channel_id:str|None=None):
        return service_provider().list_works(after=after,limit=limit,state=state,profile_ref=profile_ref,channel_id=channel_id)

    @router.post('/works',status_code=202)
    def create_work(request:Command):
        return command('create',request)

    @router.get('/works/{work_id}')
    def get_work(work_id:str):
        return service_provider().snapshot(work_id)

    @router.post('/works/{work_id}/basis',status_code=202)
    def basis(work_id:str,request:Command):return command('basis',request,work_id)

    @router.post('/works/{work_id}/inputs',status_code=202)
    def add_input(work_id:str,request:Command):return command('input',request,work_id)

    @router.post('/works/{work_id}/plans',status_code=202)
    def plan(work_id:str,request:Command):return command('plan',request,work_id)

    @router.post('/works/{work_id}/plans/{revision}/confirm',status_code=202)
    def confirm(work_id:str,revision:int,request:Command):return command('confirm',request,work_id,plan_revision=revision)

    @router.post('/works/{work_id}/cancel',status_code=202)
    def cancel(work_id:str,request:Command):return command('cancel',request,work_id)

    @router.post('/works/{work_id}/authorization-grants',status_code=202)
    def grant(work_id:str,request:Command):return command('grant',request,work_id)

    @router.post('/works/{work_id}/resume',status_code=202)
    def resume(work_id:str,request:Command):return command('resume',request,work_id)

    @router.post('/works/{work_id}/outputs/{output_id}/accept',status_code=202)
    def accept(work_id:str,output_id:str,request:Command):return command('accept',request,work_id,output_id=output_id)

    @router.post('/works/{work_id}/assignment',status_code=202)
    def assign(work_id:str,request:Command):return command('assignment',request,work_id)

    @router.post('/works/{work_id}/revisions/confirm',status_code=202)
    def confirm_revision(work_id:str,request:Command):return command('confirm_revision',request,work_id)

    @router.post('/works/{work_id}/revisions',status_code=202)
    def revise(work_id:str,request:Command):return command('revise',request,work_id)

    @router.post('/works/{work_id}/fork',status_code=202)
    def fork(work_id:str,request:Command):return command('fork',request,work_id)

    @router.get('/works/{work_id}/artifacts')
    def artifacts(work_id:str):return service_provider().snapshot(work_id)['artifacts']

    @router.get('/artifacts/{artifact_id}/content')
    def content(artifact_id:str):
        path,media_type=service_provider().artifact_path(artifact_id)
        return FileResponse(path,media_type=media_type,headers={'Cache-Control':'no-store'})

    @router.get('/works/{work_id}/events')
    async def events(work_id:str,request:Request,after:int=0):
        service=service_provider()
        snapshot=await asyncio.to_thread(service.snapshot,work_id)
        if after<0:raise ProductionError('invalid_input','无效事件游标',status_code=400)
        async def stream():
            cursor=after
            if not after or after>snapshot['cursor']:
                cursor=snapshot['cursor']
                yield {'event':'snapshot','id':str(cursor),'data':json.dumps(snapshot,ensure_ascii=False)}
            while not await request.is_disconnected():
                records=await asyncio.to_thread(service.store.events,work_id,cursor)
                for event in records:
                    cursor=event['seq']
                    yield {'event':event['kind'],'id':str(cursor),'data':json.dumps(event,ensure_ascii=False)}
                await asyncio.sleep(.5)
        return EventSourceResponse(stream(),ping=15)

    @router.get('/channels')
    def channels():return CreativeCatalog(service_provider()).list('channels')

    @router.get('/directors')
    def directors():return CreativeCatalog(service_provider()).list('directors')

    @router.post('/channels',status_code=202)
    def create_channel(request:Command):
        return CreativeCatalog(service_provider()).command('channels','create',request.payload,command_id=request.command_id)

    @router.patch('/channels/{id}',status_code=202)
    def patch_channel(id:str,request:Command):
        return CreativeCatalog(service_provider()).command('channels','edit',request.payload,command_id=request.command_id,id=id,expected_revision=request.expected_revision)

    @router.post('/directors',status_code=202)
    def create_director(request:Command):
        return CreativeCatalog(service_provider()).command('directors','create',request.payload,command_id=request.command_id)

    @router.patch('/directors/{id}',status_code=202)
    def patch_director(id:str,request:Command):
        return CreativeCatalog(service_provider()).command('directors','edit',request.payload,command_id=request.command_id,id=id,expected_revision=request.expected_revision)

    @router.post('/directors/{id}/revisions',status_code=202)
    def director_revision(id:str,request:Command):
        return CreativeCatalog(service_provider()).command('directors','revision',request.payload,command_id=request.command_id,id=id,expected_revision=request.expected_revision)

    @router.post('/directors/{id}/analyses',status_code=202)
    def reanalyze_director(id:str,request:Command):
        return CreativeCatalog(service_provider()).command('directors','analyze',request.payload,command_id=request.command_id,id=id,expected_revision=request.expected_revision)

    @router.post('/directors/{id}/accept',status_code=202)
    def accept_director(id:str,request:Command):
        return CreativeCatalog(service_provider()).command('directors','accept',request.payload,command_id=request.command_id,id=id,expected_revision=request.expected_revision)

    @router.get('/works/{work_id}/deletion-preview')
    def deletion_preview(work_id:str,output_id:str|None=None):
        from easel.production.deletion import DeletionService
        service=service_provider()
        return DeletionService(service.store,outputs=service.outputs).preview(work_id,output_id)

    @router.post('/works/{work_id}/delete')
    def delete_work(work_id:str,request:Command):
        from easel.production.deletion import DeletionService
        service=service_provider()
        return DeletionService(service.store,outputs=service.outputs).execute(request.command_id,work_id,
            request.expected_revision,request.payload.get('preview_hash',''),request.payload.get('output_id'))

    return router


async def production_error_handler(request:Request,exc:ProductionError):
    return JSONResponse(status_code=exc.status_code,content={'error':exc.as_dict()})
