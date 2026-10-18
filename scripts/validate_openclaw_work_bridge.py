#!/usr/bin/env python3
"""A1: installed native OpenClaw against loopback fakes. Never uses user runtime.

Run from the repository venv. All configuration, credentials (random test-only),
transcripts and SQLite files live under a new temporary directory. No Worker.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from easel.openclaw_cmd import openclaw_base_cmd
from easel.production.errors import ProductionError
from easel.production.service import WorkService
from easel.production.store import Store
from easel.work_bridge import WorkToolBridge, create_work_tool_router, require_gateway_bridge
from web.production_api import production_error_handler

TOOLS = ['easel_work_context', 'easel_work_create_draft', 'easel_work_request_plan']


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def wait_for(predicate, timeout=40):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.1)
    raise AssertionError('Timed out waiting for isolated runtime')


class FakeModel:
    def __init__(self):
        self.requests = []
        self.emitted = set()

    async def complete(self, request: Request):
        body = await request.json()
        self.requests.append(body)
        messages = body.get('messages', [])
        last_user = max((i for i, m in enumerate(messages) if m['role'] == 'user'), default=-1)
        text = json.dumps(messages[last_user].get('content', ''), ensure_ascii=False) if last_user >= 0 else ''
        case = re.search(r'A1_CASE=([a-z_]+)', text)
        case = case[1] if case else 'discuss'
        if case in getattr(self, 'delays', {}):
            import asyncio
            await asyncio.sleep(self.delays[case])
        tool_done = text in self.emitted or any(m['role'] == 'tool' for m in messages[last_user+1:])
        name, args = None, {}
        if not tool_done:
            if case in getattr(self,'extra_cases',{}):
                value=self.extra_cases[case]
                name,args=value(body) if callable(value) else value
            elif case == 'create':
                name, args = TOOLS[1], {'title': '隔离测试作品', 'input_text': '仅假模型：克制地表达失败经历'}
            elif case == 'plan':
                name, args = TOOLS[2], {'request': '按已讨论的克制方向整理方案'}
            elif case == 'context':
                name = TOOLS[0]
            elif case.startswith('attack_'):
                name = {'attack_voice':'minimax-media__text_to_audio', 'attack_video':'minimax-media__generate_video', 'attack_old_pipeline':'exec'}.get(case, case[len('attack_'):])
                if name == 'exec':
                    args = {'command': 'echo FORBIDDEN_EXEC'}
                elif name == 'read':
                    args = {'path': '/etc/passwd'}
                else:
                    args = {'input': 'denied'}
            elif case == 'forge':
                name, args = TOOLS[2], {'request': 'forged', 'work_id': 'another-work', 'command_id': 'forged', 'services': ['paid']}
        call_id = 'call_' + str(len(self.requests))
        if name:
            self.emitted.add(text)
            calls = [{'index': 0, 'id': call_id, 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args, ensure_ascii=False)}}]
            # One turn, different native call IDs, same business intent.
            if case == 'plan':
                calls.append({**calls[0], 'index': 1, 'id': call_id + '_repeat'})
            delta, finish = {'role': 'assistant', 'tool_calls': calls}, 'tool_calls'
        else:
            delta, finish = {'role': 'assistant', 'content': '这是隔离假模型的讨论回复；未进行真实制作。'}, 'stop'
        if body.get('stream'):
            def events():
                for content in [dict(delta=delta, finish_reason=None), dict(delta={}, finish_reason=finish)]:
                    yield 'data: ' + json.dumps({'id': 'fake-completion', 'object': 'chat.completion.chunk', 'created': int(time.time()), 'model': 'a1-fake', 'choices': [{'index': 0, **content}]}, ensure_ascii=False) + '\n\n'
                yield 'data: [DONE]\n\n'
            return StreamingResponse(events(), media_type='text/event-stream')
        return {'id': 'fake-completion', 'object': 'chat.completion', 'created': int(time.time()), 'model': 'a1-fake', 'choices': [{'index': 0, 'message': delta, 'finish_reason': finish}], 'usage': {'prompt_tokens': 10, 'completion_tokens': 10, 'total_tokens': 20}}


def isolated_environment(root, node, config, guard):
    # Deliberately do not inherit provider credentials, proxies, NODE_OPTIONS or dotenv.
    return {'PATH': str(Path(node).parent) + os.pathsep + '/usr/bin:/bin',
            'TMPDIR': str(root/'tmp'), 'OPENCLAW_HOME': str(root/'home'),
            'OPENCLAW_STATE_DIR': str(root/'state'), 'OPENCLAW_CONFIG_PATH': str(config),
            'OPENCLAW_OFFLINE': '1', 'OPENCLAW_NO_AUTO_UPDATE': '1', 'OPENCLAW_DISABLE_BONJOUR': '1', 'OPENCLAW_SKIP_CHANNELS': '1',
            'NODE_OPTIONS': '--import=' + str(guard), 'NO_COLOR': '1'}


def run_probe(root):
    root = root.resolve()
    temp_bases = [Path(tempfile.gettempdir()).resolve(), Path('/tmp').resolve()]
    if not any(base in root.parents for base in temp_bases):
        raise ValueError('A1 requires a new directory below a system temporary root')
    root.mkdir(parents=True, exist_ok=True)
    for name in ('tmp', 'home', 'state', 'workspace-video', 'workspace-main', 'profiles'):
        (root/name).mkdir(exist_ok=True)
    repo = Path(__file__).resolve().parents[1]
    base = openclaw_base_cmd()
    assert len(base) == 2 and base[1].endswith('.mjs'), 'Requires installed Node OpenClaw'
    node, entry = base
    plugin = root/'plugin'
    shutil.copytree(repo/'agents/plugins/easel-work', plugin)
    # Resolution for focused SDK imports, without installing into user runtime.
    (root/'node_modules').mkdir()
    (root/'node_modules/openclaw').symlink_to(Path(entry).parent, target_is_directory=True)
    (root/'workspace-video/AGENTS.md').write_text('你是 Easel 创作助手。A1_VIDEO_CONTEXT。讨论和解释不调用规划，明确制作请求才使用作品工具。\n')
    persona_source = (repo/'agents/workspace/SOUL.md').read_text()
    persona = persona_source.split('## 你能做的事')[0] + '## 沟通风格' + persona_source.split('## 沟通风格', 1)[1]
    (root/'workspace-video/SOUL.md').write_text(persona)
    (root/'workspace-main/AGENTS.md').write_text('MAIN_ONLY_FORBIDDEN_SENTINEL\n')
    (root/'AGENTS.md').write_text('REPO_DEV_FORBIDDEN_SENTINEL\n')
    (root/'profiles/other-profile.txt').write_text('OTHER_PROFILE_FORBIDDEN_SENTINEL\n')
    (root/'workspace-main/.env').write_text('A1_FAKE_SECRET=FILE_CREDENTIAL_FORBIDDEN_SENTINEL\n')
    api_port, gateway_port = free_port(), free_port()
    guard = root/'network-guard.mjs'
    guard.write_text('''import net from 'node:net';
import fs from 'node:fs';
import dns from 'node:dns';
const lookup = dns.lookup;
dns.lookup = function(host, options, callback) {
  if (['127.0.0.1', 'localhost', '::1'].includes(host)) return lookup.apply(this, arguments);
  fs.appendFileSync(LOG, JSON.stringify({host, dns:true})+'\\n');
  const cb = typeof options === 'function' ? options : callback;
  const err = Object.assign(new Error('A1 DNS blocked'), {code:'ENOTFOUND'});
  if (cb) { queueMicrotask(() => cb(err)); return; }
  throw err;
};
const allowed = new Set(PORTS);
const original = net.Socket.prototype.connect;
net.Socket.prototype.connect = function(...args) {
  let a = Array.isArray(args[0]) ? args[0] : args;
  let options = typeof a[0] === 'object' ? a[0] : {port: a[0], host: typeof a[1] === 'string' ? a[1] : 'localhost'};
  const host = options.host ?? 'localhost';
  if (!allowed.has(Number(options.port)) || !['127.0.0.1','localhost','::1'].includes(host)) {
    fs.appendFileSync(LOG, JSON.stringify({host,port:options.port ?? null})+'\\n');
    throw new Error('A1 outbound connection blocked');
  }
  return original.apply(this, args);
};
'''.replace('PORTS', json.dumps([api_port, gateway_port])).replace('LOG', json.dumps(str(root/'network-denials.jsonl'))))
    store = Store(root/'outputs/_production/production.sqlite3')
    store.initialize()
    service = WorkService(store, outputs=root/'outputs', profiles=root/'profiles')
    bridge = WorkToolBridge(service)
    token, gateway_token = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    model = FakeModel()
    app = FastAPI()
    bridge_requests = []
    @app.middleware('http')
    async def observe(request, call_next):
        if request.url.path.startswith('/api/chat/work-tools/'):
            body = await request.json()
            bridge_requests.append({'path': request.url.path, 'body': {k:v for k,v in body.items() if k != 'ticket'}})
        return await call_next(request)
    app.add_exception_handler(ProductionError, production_error_handler)
    app.include_router(create_work_tool_router(bridge, token))
    app.add_api_route('/v1/chat/completions', model.complete, methods=['POST'])
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=api_port, log_level='error'))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    wait_for(lambda: server.started)
    config = {
        'gateway': {'mode': 'local', 'bind': 'loopback', 'port': gateway_port,
                    'auth': {'mode': 'token', 'token': gateway_token},
                    'http': {'endpoints': {'chatCompletions': {'enabled': True}}}},
        'logging': {'level': 'info', 'file': str(root/'gateway.jsonl'), 'consoleStyle': 'json'},
        'agents': {'defaults': {'model': {'primary': 'a1fake/a1-fake'}, 'models': {'a1fake/a1-fake': {}},
                               'timeoutSeconds': 30, 'heartbeat': {'every': '0m'}},
                   'entries': {
                       'main': {'default': True, 'workspace': str(root/'workspace-main'), 'tools': {'allow': ['session_status']}},
                       'easel-video': {'workspace': str(root/'workspace-video'), 'skills': [],
                                       'tools': {'profile': 'full', 'allow': TOOLS}}}},
        'models': {'mode': 'replace', 'providers': {'a1fake': {'baseUrl': f'http://127.0.0.1:{api_port}/v1',
                    'apiKey': 'a1-fake-no-payment', 'api': 'openai-completions', 'models': [
                        {'id': 'a1-fake', 'name': 'A1 local fake', 'reasoning': False, 'input': ['text'],
                         'cost': {'input': 0, 'output': 0, 'cacheRead': 0, 'cacheWrite': 0}, 'contextWindow': 32768, 'maxTokens': 2048}]}}},
        'skills': {'allowBundled': []}, 'cron': {'enabled': False},
        'update': {'checkOnStart': False, 'auto': {'enabled': False}}, 'telemetry': {'enabled': False},
        'plugins': {'allow': ['easel-work'], 'load': {'paths': [str(plugin)]}, 'slots': {'memory': 'none'},
                    'entries': {'easel-work': {'enabled': True, 'hooks': {'allowConversationAccess': True},
                               'config': {'baseUrl': f'http://127.0.0.1:{api_port}', 'token': token}}}},
    }
    config_path = root/'openclaw.json'
    config_path.write_text(json.dumps(config))
    config_path.chmod(0o600)
    env = isolated_environment(root, node, config_path, guard)
    log = (root/'gateway-console.log').open('w')
    gateway = subprocess.Popen(base + ['gateway', 'run', '--port', str(gateway_port)], cwd=root, env=env,
                               stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    headers = {'Authorization': 'Bearer ' + gateway_token}
    session_ids = {'one': str(uuid.uuid4()), 'two': str(uuid.uuid4())}
    result = {'status': 'FAIL', 'checks': [], 'production_runtime_used': False, 'paid_requests': 0}
    def check(name, condition):
        assert condition, name
        result['checks'].append(name)
    def ready():
        if gateway.poll() is not None:
            raise RuntimeError('Isolated Gateway exited. See ' + str(root/'gateway-console.log'))
        try:
            return httpx.get(f'http://127.0.0.1:{gateway_port}/health', timeout=1).status_code == 200
        except httpx.HTTPError:
            return False
    def plugin_ready():
        try:
            require_gateway_bridge(f'http://127.0.0.1:{gateway_port}', gateway_token)
            return True
        except ProductionError:
            return False
    def chat(case, session='one', work_id=None, allow=()):
        require_gateway_bridge(f'http://127.0.0.1:{gateway_port}', gateway_token)
        prompt = 'A1_CASE=' + case
        sk = 'agent:easel-video:' + session
        inv = bridge.reserve(ui_session=session, turn_id=uuid.uuid4().hex, session_key=sk,
                             session_id=None, prompt=prompt, work_id=work_id,
                             allow=allow, context={'selected_profile': session, 'marker': 'PROFILE_' + session})
        response = httpx.post(f'http://127.0.0.1:{gateway_port}/v1/chat/completions',
                              headers={**headers, 'x-openclaw-session-key': sk, 'x-openclaw-session-id': session_ids[session]},
                              json={'model': 'openclaw/easel-video', 'messages': [{'role': 'user', 'content': prompt}], 'stream': False}, timeout=80)
        if response.status_code != 200:
            raise AssertionError('Gateway response: ' + response.text[:1200])
        wait_for(lambda: inv.state == 'ended', 10)
        return inv, response.json()
    try:
        wait_for(ready, 60)
        wait_for(plugin_ready, 60)
        version = subprocess.run(base + ['--version'], cwd=root, env=env, capture_output=True, text=True, timeout=15)
        result['openclaw_version'] = version.stdout.strip()
        for _ in range(2):
            chat('discuss')
        check('two_discussion_turns_no_work_or_run', service.list_works()['items'] == [])
        inv, _ = chat('create', allow=[TOOLS[1]])
        check('native_tool_creates_one_bound_draft', inv.work_id and len(service.list_works()['items']) == 1)
        work_id = inv.work_id
        inv, _ = chat('plan', work_id=work_id, allow=[TOOLS[2]])
        snap = service.snapshot(work_id)
        check('repeated_tool_intent_creates_one_planning_run', len(snap['runs']) == 1)
        with store.connection() as conn:
            check('no_worker_or_paid_operation', conn.execute('SELECT count(*) FROM operations').fetchone()[0] == 0)
        chat('context', work_id=work_id)
        two_start = len(model.requests)
        chat('context', session='two')
        two_context = json.dumps(model.requests[two_start:], ensure_ascii=False)
        check('native_second_session_has_no_first_profile_context', 'PROFILE_two' in two_context and 'PROFILE_one' not in two_context)
        # Reuse the same native session through the installed CLI, with an explicit target.
        cli_prompt = 'A1_CASE=context A1_NONCE=' + uuid.uuid4().hex
        cli_inv = bridge.reserve(ui_session='one', turn_id=uuid.uuid4().hex,
            session_key='agent:easel-video:one', session_id=bridge.native_sessions['agent:easel-video:one'],
            prompt=cli_prompt, work_id=work_id, context={'selected_profile':'one','marker':'PROFILE_one'})
        cli = subprocess.run(base + ['agent','--agent','easel-video','--session-key',cli_inv.session_key,
            '--session-id',cli_inv.session_id,'--message',cli_prompt,'--json'],
            cwd=root, env=env, capture_output=True, text=True, timeout=60)
        (root/'cli-result.log').write_text(cli.stdout + cli.stderr)
        check('cli_preserves_agent_and_native_session', cli.returncode == 0)
        wait_for(lambda: cli_inv.state == 'ended', 10)
        check('cli_tool_uses_bound_work', any(a['event']=='prepare' and a['turn_id']==cli_inv.turn_id for a in bridge.audit))
        for tool in ('exec', 'bash', 'read', 'file_fetch', 'browser', 'web_fetch', 'sessions_spawn', 'sessions_send', 'memory_search', 'voice', 'video', 'old_pipeline'):
            chat('attack_' + tool, work_id=work_id)
        chat('forge', work_id=work_id, allow=[TOOLS[2]])
        check('forbidden_and_forged_calls_make_no_new_run', len(service.snapshot(work_id)['runs']) == 1)
        names = [{t['function']['name'] for t in body.get('tools', [])} for body in model.requests]
        check('effective_native_tool_surface_exactly_three', bool(names) and all(n == set(TOOLS) for n in names))
        prompt_text = json.dumps(model.requests, ensure_ascii=False)
        check('service_credentials_absent_from_model_input', token not in prompt_text and gateway_token not in prompt_text)
        check('curated_video_bootstrap_loaded', 'A1_VIDEO_CONTEXT' in prompt_text and '创作者的社媒内容搭子' in prompt_text)
        check('no_main_dev_other_profile_or_file_credential_context', all(x not in prompt_text for x in (
            'MAIN_ONLY_FORBIDDEN_SENTINEL', 'REPO_DEV_FORBIDDEN_SENTINEL', 'OTHER_PROFILE_FORBIDDEN_SENTINEL', 'FILE_CREDENTIAL_FORBIDDEN_SENTINEL')))
        check('native_run_identity_observed', any(x['event'] == 'claim' and x['run_id'] for x in bridge.audit))
        check('native_uuid_is_observed_not_assumed_from_header', bridge.native_sessions['agent:easel-video:one'] != session_ids['one'])
        # An unbound native request must be rejected before the fake model sees it.
        before_unbound = len(model.requests)
        unbound = httpx.post(f'http://127.0.0.1:{gateway_port}/v1/chat/completions',
            headers={**headers, 'x-openclaw-session-key':'agent:easel-video:unbound'},
            json={'model':'openclaw/easel-video','messages':[{'role':'user','content':'A1_CASE=create'}]}, timeout=30)
        check('unbound_native_chat_blocked_before_model', unbound.status_code != 200 and len(model.requests) == before_unbound)
        # Normal main uses its own surface and bootstrap; never route video through it.
        main_response = httpx.post(f'http://127.0.0.1:{gateway_port}/v1/chat/completions',
            headers={**headers, 'x-openclaw-session-key':'agent:main:control'},
            json={'model':'openclaw/main','messages':[{'role':'user','content':'A1_CASE=discuss'}]}, timeout=30)
        check('ordinary_main_surface_preserved', main_response.status_code == 200 and
            {t['function']['name'] for t in model.requests[-1].get('tools', [])} == {'session_status'})
        check('http_history_continues_previous_turns', any('A1_CASE=create' in json.dumps(b.get('messages',[])) and 'A1_CASE=plan' in json.dumps(b.get('messages',[])) for b in model.requests))
        check('all_invocations_ended', all(v.state == 'ended' for v in bridge.invocations.values()))
        result.update(product_context_source='agents/workspace/SOUL.md', product_context_source_sha256=hashlib.sha256(persona_source.encode()).hexdigest(), fake_model_requests=len(model.requests), work_count=1, planning_runs=1,
                      command_count=sum(x['event'] == 'command' for x in bridge.audit))
        # Stop only the child gateway, then validate the same isolated configuration without plugin.
        gateway.terminate(); gateway.wait(timeout=12)
        config['plugins']['entries']['easel-work']['enabled'] = False
        config_path.write_text(json.dumps(config))
        gateway = subprocess.Popen(base + ['gateway','run','--port',str(gateway_port)], cwd=root, env=env,
                                   stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        wait_for(ready, 60)
        wait_for(lambda: httpx.get(f'http://127.0.0.1:{gateway_port}/plugins/easel-work/status', headers=headers, timeout=2).status_code == 404, 30)
        before_missing = len(model.requests)
        try:
            require_gateway_bridge(f'http://127.0.0.1:{gateway_port}', gateway_token)
            raise AssertionError('Missing plugin accepted')
        except ProductionError as exc:
            check('missing_plugin_preflight_blocks_without_main_or_model', exc.code == 'gateway_bridge_unavailable' and len(model.requests) == before_missing)
        result['status'] = 'PASS'
        (root/'audit.json').write_text(json.dumps(bridge.audit, ensure_ascii=False, indent=2))
        # Requests contain only synthetic fixtures. Keep private; summary is the shareable evidence.
        (root/'fake-model-requests.json').write_text(json.dumps(model.requests, ensure_ascii=False, indent=2))
        return result
    finally:
        gateway.terminate()
        try:
            gateway.wait(timeout=12)
        except subprocess.TimeoutExpired:
            gateway.kill(); gateway.wait(timeout=5)
        log.close()
        server.should_exit = True
        thread.join(timeout=5)
        result['child_gateway_stopped'] = gateway.poll() is not None
        denials = root/'network-denials.jsonl'
        result['outbound_attempts_blocked'] = len(denials.read_text().splitlines()) if denials.exists() else 0
        result['allowed_network_destinations'] = ['isolated_gateway', 'loopback_fake_model_and_work_api']
        (root/'bridge-requests.json').write_text(json.dumps(bridge_requests, ensure_ascii=False, indent=2))
        (root/'audit.json').write_text(json.dumps(bridge.audit, ensure_ascii=False, indent=2))
        (root/'fake-model-requests.json').write_text(json.dumps(model.requests, ensure_ascii=False, indent=2))
        (root/'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, help='New empty scratch directory; never user runtime')
    args = parser.parse_args()
    root = args.root or Path(tempfile.mkdtemp(prefix='easel-openclaw-a1-'))
    if root.exists() and any(root.iterdir()):
        raise SystemExit('Refusing nonempty scratch root')
    print('A1 scratch:', root, flush=True)
    result = run_probe(root)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
