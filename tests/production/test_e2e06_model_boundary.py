"""Synthetic E2E-06 request shape; no personal media or live provider calls."""
import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest
from pydantic import BaseModel

from easel.production.context import TaskContext
from easel.production.model_tasks import HTTPModelTransport, ModelTaskRunner, ModelTaskError
from easel.production.model_operations import RecordedModelTransport
from easel.production.tools import MediaToolResult, ScopedTool
from tests.production.test_operations import environment, owned_request
from tests.production.test_model_call_diagnostics import SETTINGS


class Args(BaseModel):
    asset_id: str
    count: int


class Answer(BaseModel):
    summary: str


@pytest.mark.parametrize('status', [200, 500])
def test_two_tool_rounds_large_wire_body_and_durable_replay(environment, status):
    store, operations, _ = environment
    spec = owned_request(store, kind='MODEL', purpose='planning')
    requests = []
    # Opaque synthetic data exercises JSON transport, not image decoding/quality.
    image = {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + 'A' * 32000}}
    async def inspect(args, context):
        return MediaToolResult({'asset_id': args.asset_id, 'sample_count': args.count},
                               tuple(dict(image) for _ in range(args.count)), frozenset({'image'}))
    tool = ScopedTool('inspect_media', 'fixture', Args, inspect, ('asset_id',))
    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        assert len(request.content) == http.diagnostic['request_bytes']
        assert body['model'] == SETTINGS['EASEL_DIRECT_API_MODEL']
        assert 'reasoning_effort' not in body and 'max_tokens' not in body
        assert request.extensions['timeout']['read'] == 900
        round_ = len(requests)
        if round_ <= 2:
            counts = [8, 8, 8, 7] if round_ == 1 else [8] * 8
            calls = [{'id': f'c{round_}-{i}', 'type': 'function', 'function': {
                'name': 'inspect_media', 'arguments': json.dumps({'asset_id': f'a{round_}-{i}', 'count': count})}}
                for i, count in enumerate(counts)]
            message = {'tool_calls': calls, 'reasoning_content': f'private-reasoning-{round_}'}
            return httpx.Response(200, json={'choices': [{'finish_reason': 'tool_calls', 'message': message}]})
        assert len(request.content) > 5_000_000
        return httpx.Response(status, json={'choices': [{'finish_reason': 'stop', 'message': {'content': '{"summary":"ok"}'}}]})
    http = HTTPModelTransport(SETTINGS, transport=httpx.MockTransport(handler))
    handles = frozenset(f'a{r}-{i}' for r in (1, 2) for i in range(8))
    context = TaskContext(spec['work_id'], spec['run_id'], spec['task_id'], allowed_handles=handles)
    async def authorize(ctx):
        pass  # RecordedModelTransport still enforces the real isolated grant/owner.
    def execute():
        recorded = RecordedModelTransport(http, operations, SimpleNamespace(**spec, plan_revision=None),
            {k: spec[k] for k in ('provider', 'model', 'mode')}, spec['config_version'])
        return asyncio.run(ModelTaskRunner(recorded, authorize).run(context, 'revise', Answer,
            tools=(tool,), media=tuple(dict(image) for _ in range(80))))
    if status == 200:
        assert execute().summary == 'ok'
    else:
        with pytest.raises(ModelTaskError) as caught:
            execute()
        assert caught.value.code == 'provider_http_error'
        assert caught.value.diagnostic['phase'] == 'response_body'
        assert caught.value.diagnostic['http_status'] == 500
    assert [len(b['messages']) for b in requests] == [2, 8, 18]
    def images(body):
        return sum(sum(x.get('type') == 'image_url' for x in m['content'])
                   for m in body['messages'] if isinstance(m.get('content'), list))
    assert [images(b) for b in requests] == [80, 111, 175]
    assert requests[2]['messages'][:8] == requests[1]['messages']
    assert requests[1]['messages'][:2] == requests[0]['messages']
    assert requests[2]['messages'][2]['reasoning_content'] == 'private-reasoning-1'
    assert requests[2]['messages'][8]['reasoning_content'] == 'private-reasoning-2'
    # Reconstructing the task may only replay known receipts, never resend UNKNOWN.
    if status == 200:
        assert execute().summary == 'ok'
    else:
        with pytest.raises(ModelTaskError, match='不能自动重复提交'):
            execute()
    assert len(requests) == 3
    with store.connection() as conn:
        states = [r[0] for r in conn.execute('SELECT state FROM operations ORDER BY created_at,rowid')]
        assert states == ['succeeded', 'succeeded', 'succeeded' if status == 200 else 'unknown']
        events = [json.loads(r[0]) for r in conn.execute("SELECT payload_json FROM events WHERE kind='model_call_diagnostic'")]
        assert len(events) == 3
        assert 'private-reasoning' not in json.dumps(events)
