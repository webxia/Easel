"""E2E-05 synthetic Gateway failures; isolated database and in-memory HTTP only."""
import asyncio
import json
from types import SimpleNamespace

import pytest
from tests.production.test_conversation import env, entry
from web.conversation_api import VideoChat
import web.conversation_api as api


@pytest.mark.parametrize('failure', ['malformed_tool', 'truncated_stream'])
def test_failed_gateway_reply_redacts_and_never_creates_business_rows(
        env, tmp_path, monkeypatch, caplog, failure):
    service, conversation = env
    segment = entry(conversation)
    requests = []
    saved = []
    secret = 'Bearer synthetic-private-key prompt-original media-original'
    tables = ('works', 'runs', 'tasks', 'operations', 'plan_revisions',
              'authorization_grants', 'artifacts')

    def snapshot():
        with service.store.connection() as conn:
            return {table: [tuple(r) for r in conn.execute(f'SELECT * FROM {table}')]
                    for table in tables}

    before = snapshot()

    class Response:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        def raise_for_status(self): pass
        async def aiter_lines(self):
            if failure == 'malformed_tool':
                yield 'data: ' + json.dumps({'error': {'message':
                    'Provider returned an incomplete or malformed tool call ' + secret}})
            else:
                yield 'data: ' + json.dumps({'choices': [{'delta': {'content': ''}}]})

    class Client:
        def __init__(self, *args, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        def stream(self, *args, **kwargs):
            requests.append(1)
            return Response()

    monkeypatch.setattr(api.httpx, 'AsyncClient', Client)
    path = tmp_path / 'events.jsonl'
    chat = VideoChat(lambda: service, lambda _: path,
                    lambda *args: saved.append(args), gateway_url='http://fixture.invalid',
                    gateway_token='fixture-only', preflight=lambda *args: None)
    request = SimpleNamespace(sessionId='ui', turnId='fixture-stream',
                              videoSegmentId=segment, message='讨论', attachments=[])

    async def replay(*args): return 'replay'
    async def run():
        await chat.stream(request, replay)
        await chat.tasks['ui']
        await chat.stream(request, replay)

    asyncio.run(run())
    assert len(requests) == 1
    assert snapshot() == before
    events = [json.loads(line) for line in path.read_text().splitlines()]
    assert events[-1]['event'] == 'error'
    assert not any(e['event'] == 'done' for e in events)
    assert saved[0][-1]['clean_end'] is False
    for token in secret.split():
        assert token not in path.read_text() + caplog.text + str(saved)
    assert 'ValueError' in caplog.text
    with service.store.connection() as conn:
        assert conn.execute("SELECT state FROM conversation_turns WHERE id='fixture-stream'").fetchone()[0] == 'unknown'
