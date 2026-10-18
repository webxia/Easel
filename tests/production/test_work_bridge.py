"""A1 seam tests: real WorkService in temporary SQLite, no worker/providers."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from easel.production.errors import ProductionError
from easel.production.service import WorkService
from easel.production.store import Store
from easel.work_bridge import WorkToolBridge, Claim, Identity, Call, Dispatch, create_work_tool_router
from web.production_api import production_error_handler

CONTEXT = 'easel_work_context'
CREATE = 'easel_work_create_draft'
PLAN = 'easel_work_request_plan'
TOKEN = 'test-only-not-a-production-token'


@pytest.fixture
def bridge(tmp_path):
    store = Store(tmp_path/'outputs/_production/production.sqlite3')
    store.initialize()
    return WorkToolBridge(WorkService(store, outputs=tmp_path/'outputs', profiles=tmp_path/'profiles'))


def reserve(bridge, *, turn='t1', session='one', prompt='make a video', work=None, allow=(CREATE, PLAN), native='native-one'):
    return bridge.reserve(ui_session=session, turn_id=turn, session_key=f'agent:easel-video:{session}',
                          session_id=native, prompt=prompt, work_id=work, allow=allow,
                          context={'profile': session})


def claim(bridge, inv, run='run-one'):
    value = Claim(agent_id='easel-video', session_key=inv.session_key, session_id=inv.session_id or 'assigned-native', run_id=run, prompt='make a video')
    bridge.claim(value)
    return value.model_dump(exclude={'prompt'})


def call(bridge, identity, tool=CREATE, params=None, call_id='c1'):
    args = params if params is not None else {'title': 'test', 'input_text': 'true user brief'}
    value = Call(**identity, tool=tool, params=args, tool_call_id=call_id)
    ticket = bridge.prepare(value)['ticket']
    return Dispatch(**value.model_dump(), ticket=ticket)


def error(code, fn):
    with pytest.raises(ProductionError) as caught:
        fn()
    assert caught.value.code == code


def test_claim_native_identity_and_first_session_id_adoption(bridge):
    inv = reserve(bridge, native=None)
    identity = claim(bridge, inv)
    assert inv.session_id == 'assigned-native' and inv.state == 'active'
    bridge.end(Identity(**identity))
    next_inv = reserve(bridge, turn='t2', native=None)
    assert next_inv.session_id == 'assigned-native'
    error('binding_mismatch', lambda: bridge.claim(Claim(**{**identity, 'run_id':'next-run', 'session_id':'rotated'}, prompt='make a video')))


@pytest.mark.parametrize('changed', [dict(agent_id='main'), dict(session_key='agent:easel-video:other'), dict(session_id='foreign'), dict(prompt='forged input')])
def test_claim_rejects_wrong_scope_or_prompt(bridge, changed):
    inv = reserve(bridge)
    fields = dict(agent_id='easel-video', session_key=inv.session_key, session_id=inv.session_id, run_id='r', prompt='make a video')
    error('binding_mismatch', lambda: bridge.claim(Claim(**{**fields, **changed})))
    assert inv.state == 'reserved' and not bridge.service.list_works()['items']


def test_unknown_or_active_invocation_never_releases_on_timeout_guess(bridge):
    inv = reserve(bridge)
    assert reserve(bridge) is inv
    error('turn_conflict', lambda: reserve(bridge, prompt='different content'))
    error('invocation_pending', lambda: reserve(bridge, turn='t2'))
    claim(bridge, inv)
    error('invocation_pending', lambda: reserve(bridge, turn='t2'))


def test_two_sessions_same_call_id_never_cross_work_or_profile(bridge):
    one, two = reserve(bridge), reserve(bridge, turn='t2', session='two', native='native-two')
    i1, i2 = claim(bridge, one), claim(bridge, two, 'run-two')
    w1 = bridge.dispatch(call(bridge, i1))['work_id']
    w2 = bridge.dispatch(call(bridge, i2))['work_id']
    assert w1 != w2 and one.work_id == w1 and two.work_id == w2
    c1 = bridge.dispatch(call(bridge, i1, CONTEXT, {}))
    c2 = bridge.dispatch(call(bridge, i2, CONTEXT, {}))
    assert c1['context'] == {'profile': 'one'} and c2['context'] == {'profile': 'two'}
    error('binding_mismatch', lambda: bridge.prepare(Call(**{**i1, 'session_key':two.session_key}, tool=CONTEXT, params={}, tool_call_id='c1')))


def test_host_intent_and_model_arguments_are_both_checked(bridge):
    identity = claim(bridge, reserve(bridge, allow=()))
    error('intent_not_authorized', lambda: call(bridge, identity))
    for forged in ('work_id', 'profile_ref', 'command_id', 'owner_epoch', 'services', 'allow_ai'):
        error('invalid_tool_arguments', lambda: call(bridge, identity, params={'title':'x','input_text':'x',forged:'forged'}))
    assert not bridge.service.list_works()['items']


def test_ticket_binds_call_and_exact_payload(bridge):
    identity = claim(bridge, reserve(bridge))
    original = call(bridge, identity)
    for changed in ({'params': {'title':'changed','input_text':'x'}}, {'tool_call_id':'other'}, {'ticket':'x'*32}):
        request = Dispatch(**{**original.model_dump(), **changed})
        error('ticket_mismatch', lambda: bridge.dispatch(request))
    assert not bridge.service.list_works()['items']


def test_same_intent_different_native_ids_reuses_existing_command_receipt(bridge):
    identity = claim(bridge, reserve(bridge))
    first = bridge.dispatch(call(bridge, identity))
    repeated = bridge.dispatch(call(bridge, identity, call_id='c2'))
    assert repeated == first
    args = {'request':'formal plan'}
    plan1 = bridge.dispatch(call(bridge, identity, PLAN, args, 'p1'))
    plan2 = bridge.dispatch(call(bridge, identity, PLAN, args, 'p2'))
    assert plan1 == plan2
    snap = bridge.service.snapshot(first['work_id'])
    assert len(snap['runs']) == 1 and snap['runs'][0]['kind'] == 'planning'
    with bridge.service.store.connection() as conn:
        assert conn.execute('SELECT count(*) FROM command_receipts').fetchone()[0] == 2
        assert conn.execute('SELECT count(*) FROM operations').fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM authorization_grants').fetchone()[0] == 0


def test_late_tool_cannot_attach_to_next_turn(bridge):
    inv = reserve(bridge)
    identity = claim(bridge, inv)
    old = call(bridge, identity)
    bridge.end(Identity(**identity))
    new = reserve(bridge, turn='t2')
    claim(bridge, new, 'new-run')
    error('binding_mismatch', lambda: bridge.dispatch(old))
    error('binding_mismatch', lambda: bridge.claim(Claim(**identity, prompt='make a video')))
    assert not bridge.service.list_works()['items']


def test_external_work_revision_conflict_is_not_silently_retried(bridge):
    identity = claim(bridge, reserve(bridge))
    work = bridge.dispatch(call(bridge, identity))['work_id']
    bridge.service.command('input', {'text':'new external input'}, command_id='external', work_id=work, expected_revision=1)
    error('stale_revision', lambda: bridge.dispatch(call(bridge, identity, PLAN, {'request':'formal plan'}, 'p1')))
    assert bridge.service.snapshot(work)['runs'] == []


def test_router_requires_independent_credential_and_has_no_authority_actions(bridge):
    app = FastAPI()
    app.add_exception_handler(ProductionError, production_error_handler)
    app.include_router(create_work_tool_router(bridge, TOKEN))
    client = TestClient(app)
    identity = claim(bridge, reserve(bridge))
    body = {**identity,'tool':CONTEXT,'params':{},'tool_call_id':'c1'}
    assert client.post('/api/chat/work-tools/prepare', json=body).status_code == 401
    assert client.post('/api/chat/work-tools/prepare', json=body, headers={'Authorization':'Bearer wrong'}).status_code == 401
    headers = {'Authorization':'Bearer '+TOKEN}
    for tool in ('confirm','grant','accept','delete','exec','easel_work_request_revision'):
        assert client.post('/api/chat/work-tools/prepare',json={**body,'tool':tool},headers=headers).status_code == 422
    for action in ('reserve','confirm','grant','accept','delete'):
        assert client.post('/api/chat/work-tools/'+action,json={},headers=headers).status_code == 404
    assert client.post('/api/chat/work-tools/prepare',json={**body,'params':{'path':'/etc/passwd'}},headers=headers).status_code == 400
    assert client.post('/api/chat/work-tools/prepare',json=body,headers=headers).status_code == 200


def test_gateway_preflight_rejects_missing_or_wrong_plugin(monkeypatch):
    import httpx
    from easel.work_bridge import require_gateway_bridge
    calls = []
    def get(url, **kwargs):
        calls.append((url, kwargs))
        return httpx.Response(404, request=httpx.Request('GET', url))
    monkeypatch.setattr(httpx, 'get', get)
    error('gateway_endpoint_invalid', lambda: require_gateway_bridge('https://provider.example', 'token'))
    assert not calls
    error('gateway_bridge_unavailable', lambda: require_gateway_bridge('http://127.0.0.1:12345', 'token'))
    assert calls[0][1]['trust_env'] is False and calls[0][1]['follow_redirects'] is False
    def ready(url, **kwargs):
        return httpx.Response(200, json={'protocol':1,'agent_id':'main','tools':[]}, request=httpx.Request('GET',url))
    monkeypatch.setattr(httpx,'get',ready)
    error('gateway_bridge_incompatible', lambda: require_gateway_bridge('http://127.0.0.1:12345','token'))
