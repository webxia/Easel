from __future__ import annotations
import hashlib
from pathlib import Path
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from easel.production.store import Store
from easel.production.service import WorkService
from easel.production.errors import ProductionError
from web.production_api import create_router, production_error_handler


@pytest.fixture
def service(tmp_path):
    outputs=tmp_path/'outputs';profiles=tmp_path/'profiles';profiles.mkdir()
    store=Store(outputs/'_production/production.sqlite3');store.initialize()
    return WorkService(store,outputs=outputs,profiles=profiles)


@pytest.fixture
def client(service):
    app=FastAPI();app.add_exception_handler(ProductionError,production_error_handler)
    app.include_router(create_router(lambda:service))
    return TestClient(app)


def send(client,path,payload=None,revision=None,key=None):
    return client.post('/api/production/'+path,json={'command_id':key or uuid.uuid4().hex,
        'expected_revision':revision,'payload':payload or {}})


def create(client,**extra):
    response=send(client,'works',{'title':'AI与科技','input_text':'保持观点，制作短视频',**extra})
    assert response.status_code==202,response.text
    return response.json()['work_id']


def plan():
    return {'schema_version':1,'title':'AI与科技','summary':'解释概念','script':'技术应服务人。',
            'scenes':[{'id':'s1','purpose':'开场','visual':'真实科技画面','narration':'技术应服务人。','duration_seconds':3,'required_input_ids':[]}],
            'settings':{'duration_seconds':3,'aspect_ratio':'16:9','audio_mode':'silent'}}


def test_confirm_idempotent_freezes_plan_creates_single_run(client,service):
    id=create(client)
    result=send(client,f'works/{id}/plans',{'generate':False,'plan':plan()},1)
    assert result.status_code==202,result.text
    payload={'plan_hash':result.json()['plan_hash'],'services':[]}
    first=send(client,f'works/{id}/plans/1/confirm',payload,2,'confirm')
    repeat=send(client,f'works/{id}/plans/1/confirm',payload,2,'confirm')
    assert first.status_code==202,first.text
    assert first.json()==repeat.json()
    snapshot=client.get(f'/api/production/works/{id}').json()
    assert snapshot['state']=='producing'
    assert [run['kind'] for run in snapshot['runs']]==['production']
    assert [task['kind'] for task in snapshot['tasks']]==['supply']
    assert snapshot['plans'][0]['confirmed_at']
    stale=send(client,f'works/{id}/cancel',{},2)
    assert stale.status_code==409
    assert snapshot['accepted_output_id'] is None


def test_no_profile_and_durable_planning_not_tied_to_chat(client,service):
    id=create(client)
    result=send(client,f'works/{id}/plans',{},1)
    assert result.status_code==202
    rebuilt=WorkService(Store(service.store.path),outputs=service.outputs,profiles=service.profiles)
    assert rebuilt.list_works()['items'][0]['id']==id
    snap=rebuilt.snapshot(id)
    assert snap['profile_ref'] is None
    assert snap['runs'][0]['kind']=='planning'
    assert not snap['plans']


def test_command_key_reuse_different_payload_rejected(client):
    assert send(client,'works',{'title':'A'},key='same').status_code==202
    assert send(client,'works',{'title':'B'},key='same').status_code==409


def upload(service,session='owned'):
    scope=hashlib.sha256(session.encode()).hexdigest()[:20]
    rel=f'_inbox/{scope}/batch/clip.mp4'
    path=service.outputs/rel;path.parent.mkdir(parents=True);path.write_bytes(b'original')
    return {'id':hashlib.sha256((scope+'\0'+rel).encode()).hexdigest()[:24],'path':rel,'name':'clip.mp4'}


def test_attachment_scope_and_required_inputs(client,service):
    attachment=upload(service)
    id=create(client,session_id='owned')
    assert send(client,f'works/{id}/inputs',{'session_id':'other','attachment':attachment},1).status_code==403
    good=send(client,f'works/{id}/inputs',{'session_id':'owned','attachment':attachment,'usage':'must_use','original_audio':True},1)
    assert good.status_code==202,good.text
    bad=send(client,f'works/{id}/plans',{'generate':False,'plan':plan()},2)
    assert bad.status_code==422
    updated=plan();updated['scenes'][0]['required_input_ids']=[good.json()['input_id']]
    assert send(client,f'works/{id}/plans',{'generate':False,'plan':updated},2).status_code==202
    assert (service.outputs/attachment['path']).read_bytes()==b'original'


def test_arbitrary_paths_and_cross_work_refs_rejected(client,service):
    id=create(client,session_id='owned')
    for path in ['/etc/passwd','../../x','_production/production.sqlite3']:
        assert send(client,f'works/{id}/inputs',{'session_id':'owned','attachment':{'path':path,'id':'x'}},1).status_code==403
    value=plan();value['scenes'][0]['required_input_ids']=['another_work']
    assert send(client,f'works/{id}/plans',{'generate':False,'plan':value},1).status_code==422


def test_cancel_revokes_and_fork_does_not_copy_authority(client,service):
    id=create(client)
    r=send(client,f'works/{id}/plans',{'generate':False,'plan':plan()},1).json()
    send(client,f'works/{id}/plans/1/confirm',{'plan_hash':r['plan_hash'],'allow_ai':True,'image_limit':2,'services':[]},2)
    cancelled=send(client,f'works/{id}/cancel',{},3)
    assert cancelled.status_code==202
    snap=service.snapshot(id)
    assert snap['state']=='cancelled' and snap['runs'][0]['cancel_requested']
    fork=send(client,f'works/{id}/fork',{},4)
    assert fork.status_code==202,fork.text
    fresh=service.snapshot(fork.json()['work_id'])
    assert fresh['image_limit']==0 and not fresh['plans'] and not fresh['runs']
