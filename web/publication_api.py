"""Accepted-output routes; existing app local-write guard applies."""
from fastapi import APIRouter
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


class Cancel(BaseModel):
    model_config=ConfigDict(extra='forbid')
    revision: int=Field(gt=0)


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

    @router.post('/{identity}/submit')
    def submit(identity:str,request:Confirm):return service().submit(identity,request.revision,request.confirmation_hash)

    @router.post('/{identity}/reconcile')
    def reconcile(identity:str):return service().reconcile(identity)
    return router
