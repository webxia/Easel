"""Safe diagnostics and durable UNKNOWN with no external requests."""
import asyncio
import json
from types import SimpleNamespace
import httpx
import pytest
from easel.production.model_tasks import HTTPModelTransport, ModelTaskError
from easel.production.model_operations import RecordedModelTransport
from tests.production.test_operations import environment, owned_request

SETTINGS = {'EASEL_DIRECT_API_BASE_URL':'https://fixture.invalid/v1',
            'EASEL_DIRECT_API_MODEL':'MiniMax-M3.1-Flash-Preview', 'EASEL_DIRECT_API_KEY':'secret-fixture-key'}


@pytest.mark.parametrize('error,kind', [(httpx.ConnectTimeout,'connect'), (httpx.ReadTimeout,'read'),
    (httpx.WriteTimeout,'write'), (httpx.PoolTimeout,'pool')])
def test_timeout_diagnostics_durable_and_unknown_never_resent(environment,error,kind):
    store,operations,_=environment
    spec=owned_request(store,kind='MODEL',purpose='planning')
    calls=[]
    def handler(req):
        calls.append(req)
        raise error('private exception secret-fixture-key https://private.invalid')
    transport=HTTPModelTransport(SETTINGS,transport=httpx.MockTransport(handler))
    def recorded():
        return RecordedModelTransport(transport,operations,SimpleNamespace(**spec,plan_revision=None),
            {k:spec[k] for k in ('provider','model','mode')},spec['config_version'])
    with pytest.raises(ModelTaskError) as caught:
        asyncio.run(recorded().complete([{'role':'user','content':'PRIVATE PROMPT'}],[],{}))
    assert caught.value.diagnostic['timeout_type']==kind
    assert caught.value.diagnostic['elapsed_ms']>=0
    with store.connection() as conn:
        op=dict(conn.execute('SELECT * FROM operations').fetchone())
        event=json.loads(conn.execute("SELECT payload_json FROM events WHERE kind='model_call_diagnostic'").fetchone()[0])
    assert op['state']=='unknown' and caught.value.operation_id==op['id']==event['operation_id']
    assert all(secret not in json.dumps(event) for secret in ('private exception','secret-fixture-key','PRIVATE PROMPT','private.invalid'))
    with pytest.raises(ModelTaskError,match='不能自动重复提交'):
        asyncio.run(recorded().complete([{'role':'user','content':'PRIVATE PROMPT'}],[],{}))
    assert len(calls)==1


def test_headers_and_read_phase_survive_body_timeout():
    class SlowBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'{'
            raise httpx.ReadTimeout('private')
    transport=HTTPModelTransport(SETTINGS,transport=httpx.MockTransport(lambda _:httpx.Response(200,
        headers={'x-request-id':'req-123'},stream=SlowBody())))
    with pytest.raises(ModelTaskError) as caught:
        asyncio.run(transport.complete([],[],{}))
    d=caught.value.diagnostic
    assert d['phase']=='response_body' and d['request_id']=='req-123' and d['http_status']==200
    assert 0<=d['headers_received_ms']<=d['elapsed_ms']


def test_concurrent_diagnostics_are_per_call_and_do_not_change_model_parameters():
    async def handler(req):
        body=json.loads(req.content)
        assert set(body)=={'model','messages','stream','response_format'}
        assert body['stream'] is False and body['model']==SETTINGS['EASEL_DIRECT_API_MODEL']
        assert req.extensions['timeout']['read']==900 and req.extensions['timeout']['connect']==20
        name=body['messages'][0]['content']
        if name=='slow': await asyncio.sleep(.02)
        return httpx.Response(200,headers={'x-request-id':name},json={'id':'response-'+name,
            'usage':{'prompt_tokens':8,'completion_tokens':12,'total_tokens':20,'completion_tokens_details':{'reasoning_tokens':10},'private':'secret'},
            'choices':[{'finish_reason':'stop','message':{'content':name,'reasoning_content':'PRIVATE REASONING'}}]})
    transport=HTTPModelTransport(SETTINGS,transport=httpx.MockTransport(handler))
    async def call(name):
        message=await transport.complete([{'role':'user','content':name}],[],{})
        await asyncio.sleep(.03)
        return message,transport.diagnostic
    async def run():return await asyncio.gather(call('slow'),call('fast'))
    results=asyncio.run(run())
    for (message,d),name in zip(results,['slow','fast']):
        assert message['reasoning_content']=='PRIVATE REASONING'
        assert d['request_id']==name and d['response_id']=='response-'+name and d['reasoning_tokens']==10
        assert d['outcome']=='succeeded' and d['reasoning_effort']=='provider_default'
        assert 'PRIVATE REASONING' not in json.dumps(d) and 'secret' not in json.dumps(d)


def test_untrusted_header_and_finish_reason_are_not_logged():
    transport=HTTPModelTransport(SETTINGS,transport=httpx.MockTransport(lambda _:httpx.Response(200,
        headers={'x-request-id':SETTINGS['EASEL_DIRECT_API_KEY']},json={'id':'Bearer-secret',
        'choices':[{'finish_reason':'private provider error','message':{'content':''}}]})))
    with pytest.raises(ModelTaskError) as caught:asyncio.run(transport.complete([],[],{}))
    d=caught.value.diagnostic
    assert d['finish_reason']=='other' and 'request_id' not in d and 'response_id' not in d
