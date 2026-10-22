"""Explicit production thinking depth; no Provider calls or historical rewrites."""
import asyncio
import hashlib
import json

import httpx
import pytest
from tests.production.test_operations import environment

from easel.production.configuration import model_configuration
from easel.production.model_tasks import HTTPModelTransport, ModelTaskError

SETTINGS = {'EASEL_DIRECT_API_BASE_URL': 'https://fixture.invalid/v1',
            'EASEL_DIRECT_API_MODEL': 'MiniMax-M3.1-Flash-Preview'}


def test_explicit_effort_reaches_provider_without_disabling_thinking():
    requests = []
    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        assert body['reasoning_effort'] == 'high'
        assert 'thinking' not in body and 'max_tokens' not in body
        assert body['model'] == SETTINGS['EASEL_DIRECT_API_MODEL']
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop',
            'message': {'content': '{}', 'reasoning_content': 'private reasoning'}}]})
    transport = HTTPModelTransport({**SETTINGS, 'EASEL_PRODUCTION_REASONING_EFFORT': 'high'},
                                   transport=httpx.MockTransport(handler))
    async def complete():
        message = await transport.complete([], [], {})
        assert transport.diagnostic['reasoning_effort'] == 'high'
        return message
    message = asyncio.run(complete())
    assert message['reasoning_content'] == 'private reasoning'
    assert len(requests) == 1


@pytest.mark.parametrize('value', ['none', 'disabled', 'HIGH', 'unlimited'])
def test_invalid_effort_fails_before_request(value):
    with pytest.raises(ModelTaskError) as caught:
        HTTPModelTransport({**SETTINGS, 'EASEL_PRODUCTION_REASONING_EFFORT': value})
    assert caught.value.code == 'model_effort_invalid'


def test_parameter_identity_preserves_old_default_and_distinguishes_new_effort(tmp_path, monkeypatch):
    monkeypatch.delenv('EASEL_PRODUCTION_REASONING_EFFORT', raising=False)
    root = tmp_path
    def write(extra=''):
        (root/'.env').write_text('\n'.join(k+'='+v for k,v in SETTINGS.items())+'\n'+extra)
    write()
    settings, service, original = model_configuration(root)
    legacy = {'base':settings['EASEL_DIRECT_API_BASE_URL'], 'model':service['model'],
        'capabilities':['image'], 'video_dialect':'', 'quality_chunk_seconds':'30',
        'model_timeout_seconds':'900'}
    assert original == hashlib.sha256(json.dumps(legacy,sort_keys=True).encode()).hexdigest()
    write('EASEL_PRODUCTION_REASONING_EFFORT=high\n')
    _, same_service, high = model_configuration(root)
    assert same_service == service and high != original
    write('EASEL_PRODUCTION_REASONING_EFFORT=max\n')
    assert model_configuration(root)[2] not in (high, original)


@pytest.mark.parametrize('state', ['succeeded', 'unknown'])
def test_effort_change_cannot_replay_old_operation_with_new_parameters(environment, state):
    from types import SimpleNamespace
    from easel.production.errors import Conflict
    from easel.production.model_operations import RecordedModelTransport
    from easel.production.providers.base import ProviderResult
    from tests.production.test_operations import owned_request
    store, operations, _ = environment
    spec = owned_request(store, kind='MODEL', purpose='planning')
    identity = hashlib.sha256((spec['task_id']+':model:1').encode()).hexdigest()
    request = {'messages': [], 'tools': [], 'schema': {}}
    operations.reserve(**{**spec, 'operation_id':identity, 'request':request})
    operations.mark_sending(identity, spec['owner_epoch'])
    if state == 'unknown':
        operations.mark_unknown(identity)
    else:
        operations.receive(identity, ProviderResult('succeeded', result={'message':{'content':'{}'}}))
    calls=[]
    transport=HTTPModelTransport({**SETTINGS, 'EASEL_PRODUCTION_REASONING_EFFORT':'high'},
        transport=httpx.MockTransport(lambda req:calls.append(req)))
    recorded=RecordedModelTransport(transport,operations,SimpleNamespace(**spec,plan_revision=None),
        {k:spec[k] for k in ('provider','model','mode')},'explicit-high-config')
    with pytest.raises(Conflict):asyncio.run(recorded.complete([],[],{}))
    assert not calls and operations.get(identity)['state']==state
