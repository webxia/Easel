"""The ordinary Web stream must not deliver the entry agent's second draft.

Exercise the actual HTTP supervisor and its event journal, without a Gateway,
production database or user configuration. Pipeline-only tests miss this hop.
"""
import asyncio
import json

import pytest

import web.app as web
from web.conversation_api import natural_entry


@pytest.mark.parametrize('entered,ready', [(False, False), (True, True), (True, False)])
@pytest.mark.parametrize('early_raw_end',[False,True])
def test_natural_entry_delivers_only_scoped_answer(tmp_path, monkeypatch, entered, ready,early_raw_end):
    import httpx
    import easel.conversation_bridge as bridge_module

    saved = []
    source = {'id': None}
    monkeypatch.setattr(web, 'SESSIONS_DIR', tmp_path)
    monkeypatch.setattr(web, 'DEBUG_DIR', tmp_path / 'debug')
    monkeypatch.setattr(web, 'SHARED_RAW_STREAM', tmp_path / 'raw')
    monkeypatch.setattr(web, '_chat_backend', lambda _: 'openclaw')
    monkeypatch.setattr(web, '_harness_settings', lambda: {})
    monkeypatch.setattr(web, '_chat_message', lambda req: req.message)
    monkeypatch.setattr(web, '_save_turn', lambda *args: saved.append(args))
    monkeypatch.setattr(web, '_heal_openclaw_session', lambda _: None)
    monkeypatch.setattr(web, '_openclaw_session_id', lambda _: 'native-fixture')
    monkeypatch.setattr(web, '_persona_prefix', lambda _: '')
    monkeypatch.setattr(web, 'openclaw_base_cmd', lambda: ['unused'])
    monkeypatch.setattr(web, '_agent_thinking_level', lambda: 'off')
    monkeypatch.setattr(web, '_proxy_env', lambda: {})
    monkeypatch.setattr(web, 'question_bridge_supported', lambda: False)
    monkeypatch.setattr(web, 'GatewayClient', None)
    monkeypatch.setattr(web, '_resolve_transport', lambda _: 'http')
    monkeypatch.setattr(web, '_pin_transport', lambda *args: None)
    monkeypatch.setattr(web, 'gateway_auth_headers', lambda: {})
    monkeypatch.setattr(web, 'chat_completions_url', lambda: 'http://fixture/chat')
    monkeypatch.setattr(web, '_production_service', lambda: None)
    monkeypatch.setattr(natural_entry, 'reserve', lambda *args, **kw: None)
    monkeypatch.setattr(natural_entry, 'release', lambda *args: None)
    monkeypatch.setattr(natural_entry, 'source', lambda *args: source['id'])

    class Lock:
        def acquire(self, *args): return True
        def release(self): pass

    monkeypatch.setattr(web, '_CrossProcLock', lambda _: Lock())
    monkeypatch.setattr(web, '_session_lock', lambda _: asyncio.Lock())
    if early_raw_end:
        import builtins
        class BrokenRaw:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def seek(self,*args):pass
            def readline(self):raise OSError('auxiliary reader failed')
        def raw_open(path,*args,**kwargs):
            return BrokenRaw() if path==tmp_path/'raw' else builtins.open(path,*args,**kwargs)
        monkeypatch.setattr(web,'open',raw_open,raising=False)

    class Bridge:
        def __init__(self, *args): pass
        def continue_handoff(self, *args):
            return {'turn_id': 'scoped'} if ready else None

    monkeypatch.setattr(bridge_module, 'PersistentWorkToolBridge', Bridge)

    async def deliver(*args, event_sink, **kwargs):
        event_sink('token', '目标管线唯一答复')
        event_sink('done', {})

    monkeypatch.setattr(web._video_chat, '_deliver', deliver)

    class Response:
        status_code = 200
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def aiter_lines(self):
            await asyncio.sleep(.05)  # let the optional raw reader fail first
            if entered:
                source['id'] = 'source'
            text = '入口重复正文' if entered else '普通对话正文'
            for part in [text[:2],text[2:]]:
                yield 'data: ' + json.dumps({'choices': [{'delta': {'content': part}}]})
            yield 'data: ' + json.dumps({'choices': [{'delta': {}, 'finish_reason': 'stop'}]})
            yield 'data: [DONE]'

    class Client:
        def __init__(self, *args, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        def stream(self, *args, **kwargs): return Response()

    monkeypatch.setattr(httpx, 'AsyncClient', Client)

    async def exercise():
        response = await web.api_chat_stream(web.ChatRequest(
            message='讨论视频', sessionId='natural-fixture', turnId='natural-turn'))
        async for _ in response.body_iterator: pass
        await asyncio.sleep(0)

    asyncio.run(exercise())
    events = web._read_job_events('natural-turn', 0)
    text = ''.join(e['data'] for e in events if e['event'] == 'token')
    assert '入口重复正文' not in text
    assert [e['event'] for e in events].count('done') == 1
    if not entered:
        assert text == '普通对话正文'
        assert saved[-1][2] == text and saved[-1][3]['clean_end']
    elif ready:
        assert text == '目标管线唯一答复'
    else:
        assert text == ''
        assert any(e['event'] == 'error' for e in events)
        assert saved[-1][2] == '' and not saved[-1][3]['clean_end']
