"""Isolated installed Gateway -> SDK -> fake Provider -> terminal integration.

Explicit runner, not a real-model E2E. Never uses the live Easel profile.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import urllib.request
import urllib.error
import fcntl
import hmac
import secrets
import re
from contextlib import contextmanager


class EvalHttpBudget:
    """Evaluation-only final HTTP reservation, shared across all model stages.

    The existing structured guard owns per-run identity. This owns the explicit
    batch ceiling, including ordinary Truth and every SDK/framework attempt.
    Reservations are never refunded, even if the process dies before a receipt.
    """
    def __init__(self, directory, manifest_sha256, *, limit=40, seconds=2700, clock=time.time, transport_policy=None):
        self.directory = Path(directory).resolve()
        from tests.planning_material_matrix.transport_recovery import POLICY
        if transport_policy not in (None, POLICY):
            raise ValueError('EVAL_TRANSPORT_POLICY_INVALID')
        if (Path(directory).is_symlink() or not re.fullmatch('[a-f0-9]{64}', manifest_sha256)
                or type(limit) is not int or not 0 < limit <= 40
                or type(seconds) is not int or not 0 < seconds <= 2700):
            raise ValueError('EVAL_BUDGET_IDENTITY_INVALID')
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.directory.chmod(0o700)
        self.identity = {'manifest_sha256': manifest_sha256, 'limit': limit, 'seconds': seconds}
        if transport_policy is not None:
            self.identity['transport_policy'] = transport_policy
        self.clock = clock
        self.path = self.directory / 'http-budget.json'
        with self.edit() as state:
            if not state:
                state.update(version='planning-eval-http-budget@1', identity=self.identity,
                             closed=False, first_reserved_at=None, requests=[])

    @contextmanager
    def edit(self):
        lock = self.directory / 'http-budget.lock'
        if lock.is_symlink() or self.path.is_symlink():
            raise ValueError('EVAL_BUDGET_STORAGE_UNSAFE')
        with lock.open('a+') as stream:
            lock.chmod(0o600)
            fcntl.flock(stream, fcntl.LOCK_EX)
            state = json.loads(self.path.read_text()) if self.path.exists() else {}
            if state and (state.get('version') != 'planning-eval-http-budget@1' or
                          state.get('identity') != self.identity):
                raise ValueError('EVAL_BUDGET_IDENTITY_CHANGED')
            try:
                yield state
            finally:
                # A rejection that closes the batch is durable as well.
                temp = self.directory / ('http-budget-' + secrets.token_hex(12) + '.tmp')
                try:
                    with temp.open('x') as out:
                        temp.chmod(0o600)
                        out.write(json.dumps(state, ensure_ascii=False, separators=(',', ':')))
                        out.flush(); os.fsync(out.fileno())
                    temp.replace(self.path)
                    parent = os.open(self.directory, os.O_RDONLY)
                    try: os.fsync(parent)
                    finally: os.close(parent)
                finally:
                    temp.unlink(missing_ok=True)

    def reserve(self, metadata, *, expected_number=None):
        with self.edit() as state:
            now = self.clock()
            first = state['first_reserved_at']
            if self.identity.get('transport_policy') and any(row['state'] == 'UNKNOWN' for row in state['requests']):
                state.update(closed=True, close_reason='UPSTREAM_UNKNOWN')
                raise ValueError('EVAL_UNRESOLVED_REQUEST_CANNOT_RETRY')
            if expected_number is not None and (type(expected_number) is not int
                    or expected_number != len(state['requests']) + 1
                    or any(row['state'] == 'UNKNOWN' for row in state['requests'])):
                state.update(closed=True, close_reason='BATCH_FAILED')
                raise ValueError('EVAL_CELL_ALREADY_RESERVED_OR_UNKNOWN')
            if (state['closed'] or len(state['requests']) >= self.identity['limit'] or
                first is not None and (now < first or now - first >= self.identity['seconds'])):
                state.update(closed=True, close_reason='BATCH_LIMIT_OR_CLOSED')
                raise ValueError('EVAL_HTTP_LIMIT_REACHED')
            if first is None: state['first_reserved_at'] = now
            number = len(state['requests']) + 1
            state['requests'].append({'number': number, 'reserved_at': now,
                                     'state': 'UNKNOWN', **metadata})
            return number

    def finish(self, number, observation):
        with self.edit() as state:
            row = state['requests'][number - 1]
            if row['number'] != number or row['state'] != 'UNKNOWN':
                raise ValueError('EVAL_HTTP_RECEIPT_CHANGED')
            row.update(observation)

    def close(self, reason='BATCH_FAILED'):
        with self.edit() as state:
            state.update(closed=True)
            state.setdefault('close_reason', reason if reason in {
                'BATCH_FAILED', 'UPSTREAM_HTTP_FAILED', 'UPSTREAM_UNKNOWN', 'BATCH_COMPLETE',
                'UPSTREAM_NOT_SENT', 'LOCAL_DELIVERY_FAILED', 'LOCAL_RECEIPT_FAILED'} else 'BATCH_FAILED')

    def validate_completion(self):
        """Late terminal evidence is retained, but cannot earn batch PASS."""
        with self.edit() as state:
            first = state['first_reserved_at']
            now = self.clock()
            if (state['closed'] or first is None or now < first
                    or now - first >= self.identity['seconds']
                    or any(row['state'] == 'UNKNOWN' for row in state['requests'])):
                state.update(closed=True)
                state.setdefault('close_reason', 'BATCH_FAILED')
                raise ValueError('EVAL_BATCH_NOT_COMPLETE_WITHIN_BOUNDS')


class EvalSseObservation:
    """Bounded diagnostic side channel; never stores assistant text/arguments."""
    def __init__(self):
        self.pending = b''
        self.bytes = self.argument_bytes = self.reasoning_bytes = self.events = 0
        self.finish = 'MISSING'
        self.complete = False
        self.http_eof = False
        self.parse_unknown = False
        self.usage = {}
        # Diagnostic only: retain fixed-size digests, never model text or credentials.
        # These do not authorize execution or replace per-run identity checks.
        self.argument_streams = {}
        self.argument_finishes = {}
        self.argument_fingerprint_unknown = False

    def observe_arguments(self, choice, call, args):
        index, tool_index = choice.get('index'), call.get('index')
        if (type(index) is not int or type(tool_index) is not int
                or not 0 <= index < 16 or not 0 <= tool_index < 16):
            self.argument_fingerprint_unknown = True
            return
        key = (index, tool_index)
        if key not in self.argument_streams:
            if len(self.argument_streams) >= 16:
                self.argument_fingerprint_unknown = True
                return
            self.argument_streams[key] = {'digest': hashlib.sha256(), 'bytes': 0,
                                         'fragments': 0, 'call_id': None}
        row = self.argument_streams[key]
        call_id = call.get('id')
        if call_id is not None:
            if (not isinstance(call_id, str) or not 0 < len(call_id) <= 512
                    or row['call_id'] is not None and row['call_id'] != call_id):
                self.argument_fingerprint_unknown = True
                return
            row['call_id'] = call_id
        if args is not None:
            if not isinstance(args, str):
                self.argument_fingerprint_unknown = True
                return
            data = args.encode('utf-8')
            row['digest'].update(data)
            row['bytes'] += len(data)
            row['fragments'] += 1

    def feed(self, data):
        self.bytes += len(data)
        self.pending += data
        while b'\n' in self.pending:
            line, self.pending = self.pending.split(b'\n', 1)
            if len(line) > 65536:
                self.parse_unknown = True
                continue
            if not line.startswith(b'data:'): continue
            value = line[5:].strip()
            if value == b'[DONE]': self.complete = True; continue
            try:
                event = json.loads(value)
                self.events += 1
                usage = event.get('usage')
                if isinstance(usage, dict):
                    for key in ('prompt_tokens', 'completion_tokens', 'total_tokens'):
                        value = usage.get(key)
                        if type(value) is int and 0 <= value <= 2_000_000_000: self.usage[key] = value
                for choice in event.get('choices', []):
                    previously_finished = choice.get('index') in self.argument_finishes
                    reason = choice.get('finish_reason')
                    if reason is not None and self.finish == 'MISSING':
                        self.finish = reason if reason in {'stop', 'length', 'tool_calls',
                            'function_call', 'content_filter'} else 'UNKNOWN'
                    index = choice.get('index')
                    if reason is not None and type(index) is int and 0 <= index < 16:
                        if index in self.argument_finishes and self.argument_finishes[index] != reason:
                            self.argument_fingerprint_unknown = True
                        self.argument_finishes[index] = reason
                    delta = choice.get('delta') or choice.get('message') or {}
                    for key in ('reasoning_content', 'reasoning'):
                        if isinstance(delta.get(key), str):
                            self.reasoning_bytes += len(delta[key].encode())
                    for call in delta.get('tool_calls') or []:
                        args = (call.get('function') or {}).get('arguments')
                        if previously_finished and args not in (None, ''):
                            self.argument_fingerprint_unknown = True
                        if isinstance(args, str): self.argument_bytes += len(args.encode())
                        self.observe_arguments(choice, call, args)
            except (ValueError, TypeError, AttributeError):
                self.parse_unknown = True
        if len(self.pending) > 65536:
            self.pending = b''
            self.parse_unknown = True

    def finish_response(self):
        """Called only after HTTP read reaches clean EOF, never from an exception.

        This closes diagnostic byte accounting, not a model/Planning success.
        Native terminal, raw safety and schema validation remain independent.
        """
        tail = self.pending.strip()
        if tail.startswith(b'data:') and tail[5:].strip() == b'[DONE]':
            self.complete = True
        elif tail:
            self.parse_unknown = True  # Incomplete frame cannot imply completeness.
        self.pending = b''
        self.http_eof = True

    def result(self):
        complete = ((self.complete or self.http_eof) and self.finish == 'tool_calls' and self.argument_streams
                    and all(self.argument_finishes.get(index) == 'tool_calls'
                            for index, _ in self.argument_streams))
        state = ('UNAVAILABLE' if self.parse_unknown or self.argument_fingerprint_unknown else
                 'COMPLETE' if complete else 'INCOMPLETE')
        streams = [{'choice_index': index, 'tool_index': tool_index,
                    'sha256': row['digest'].hexdigest(), 'bytes': row['bytes'],
                    'fragments': row['fragments']}
                   for (index, tool_index), row in sorted(self.argument_streams.items())] if state == 'COMPLETE' else []
        return {'provider_finish': self.finish, 'sse_done': self.complete,
                'response_bytes': self.bytes, 'argument_delta_bytes': self.argument_bytes,
                'reasoning_delta_bytes': self.reasoning_bytes,
                'sse_events': self.events, 'diagnostic_unknown': self.parse_unknown, 'reported_usage': self.usage,
                'argument_stream_state': state, 'argument_streams': streams,
                'argument_end_basis': ('SSE_DONE' if self.complete else 'HTTP_EOF_WITH_TOOL_FINISH')
                    if state == 'COMPLETE' else 'NOT_COMPLETE'}


class EvalProviderProxy:
    """Loopback-only eval boundary. Live authentication stays in owner memory.

    Only this isolated Gateway selects the proxy. Production remains unchanged.
    Successful response bytes stream unchanged; unsafe HTTP errors are replaced
    with a closed category before the SDK can persist an upstream error body.
    """
    def __init__(self, budget, upstream, model, api_key, *, offline=False, client_token=None, before_send=None,
                 expected_payload=None, expected_number=None, expected_model_params=None):
        parsed = urllib.parse.urlsplit(upstream)
        if offline:
            allowed = parsed.scheme == 'http' and parsed.hostname in {'127.0.0.1', 'localhost'}
        else:
            allowed = upstream == 'https://api.minimax.cn/v1/chat/completions'
        if not allowed or parsed.query or parsed.fragment or parsed.username or parsed.password:
            raise ValueError('EVAL_UPSTREAM_NOT_ALLOWED')
        self.budget, self.upstream, self.model = budget, upstream, model
        self._key = api_key
        self.client_token = client_token or secrets.token_hex(32)
        self.before_send = before_send
        self.expected_payload = expected_payload
        self.expected_number = expected_number
        self.expected_model_params = expected_model_params
        owner = self
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *_args, **_kwargs): return None
        self.opener = urllib.request.build_opener(NoRedirect())

        class Proxy(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'
            def log_message(self, *_args): pass
            def failure(self, status, category):
                value = json.dumps({'error': {'message': category, 'type': 'eval_boundary'}}).encode()
                self.send_response(status); self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(value))); self.end_headers()
                self.wfile.write(value)
            def do_POST(self):
                if (self.path != '/v1/chat/completions' or not hmac.compare_digest(
                    self.headers.get('Authorization', ''), 'Bearer ' + owner.client_token)):
                    self.failure(403, 'EVAL_REQUEST_NOT_ALLOWED'); return
                try:
                    size = int(self.headers.get('Content-Length', '0'))
                    if not 0 < size <= 8 * 1024 * 1024: raise ValueError()
                    body = self.rfile.read(size)
                    payload = json.loads(body)
                    if payload.get('model') != owner.model: raise ValueError()
                    if owner.model == 'MiniMax-M2.7':
                        # This candidate is exclusively text Planning, including
                        # ordinary Truth. Do not silently drop unsupported media.
                        messages = payload.get('messages')
                        if not isinstance(messages, list) or not messages:
                            raise ValueError('EVAL_TEXT_INPUT_REQUIRED')
                        for message in messages:
                            content = message.get('content')
                            if isinstance(content, list):
                                if any(not isinstance(part, dict) or set(part) != {'type', 'text'}
                                       or part['type'] != 'text' or not isinstance(part['text'], str)
                                       for part in content):
                                    raise ValueError('EVAL_UNSUPPORTED_INPUT')
                            elif content is not None and not isinstance(content, str):
                                raise ValueError('EVAL_UNSUPPORTED_INPUT')
                            if any(k in message for k in ('audio', 'images', 'attachments')):
                                raise ValueError('EVAL_UNSUPPORTED_INPUT')
                        if 'priority' in payload:
                            raise ValueError('EVAL_PRIORITY_NOT_AUTHORIZED')
                    # Both official aliases are observable; never infer an
                    # absent output cap from the legacy field alone.
                    token_fields = {}
                    for name in ('max_tokens', 'max_completion_tokens'):
                        value = payload.get(name)
                        if name in payload and (type(value) is not int or value <= 0):
                            raise ValueError('EVAL_TOKEN_LIMIT_INVALID')
                        token_fields.update({name: value, name + '_present': name in payload,
                                             name + '_type': 'integer' if name in payload else 'absent'})
                    if (all(name in payload for name in ('max_tokens', 'max_completion_tokens'))
                            and payload['max_tokens'] != payload['max_completion_tokens']):
                        raise ValueError('EVAL_TOKEN_LIMIT_CONFLICT')
                    tools = payload.get('tools') or []
                    schema = tools[0].get('function', {}).get('parameters') if len(tools) == 1 else None
                    schema_sha = hashlib.sha256(json.dumps(schema, sort_keys=True,
                        ensure_ascii=False, separators=(',', ':')).encode()).hexdigest() if schema else None
                    metadata = {'request_sha256': hashlib.sha256(body).hexdigest(),
                        'request_bytes': len(body), 'model': owner.model, 'schema_sha256': schema_sha,
                        'run_identity': 'UNKNOWN', **token_fields,
                        'tools_count': len(tools),
                        'tool_choice_kind': payload.get('tool_choice') if payload.get('tool_choice') in ('auto', 'required', 'none') else
                            'function' if isinstance(payload.get('tool_choice'), dict) and payload['tool_choice'].get('type') == 'function' else 'UNKNOWN',
                        'thinking_mode': (payload.get('thinking') or {}).get('type')
                            if isinstance(payload.get('thinking'), dict) and payload['thinking'].get('type') in {'enabled', 'disabled', 'adaptive'} else 'UNKNOWN'}
                    if owner.expected_model_params is not None:
                        expected = owner.expected_model_params
                        if (set(expected) != {'model', 'thinking_mode', 'max_tokens', 'max_completion_tokens'}
                                or any(metadata.get(key) != value for key, value in expected.items())):
                            raise ValueError('EVAL_FROZEN_MODEL_PARAMETERS_CHANGED')
                    if owner.expected_payload is not None:
                        from easel.integrations.planning_structured import TOOL
                        expected = owner.expected_payload
                        if (not {'max_tokens', 'max_completion_tokens'} <= expected.keys()
                                or any(metadata.get(key) != value for key, value in expected.items())
                                or len(tools) != 1 or tools[0].get('type') != 'function'
                                or tools[0].get('function', {}).get('name') != TOOL
                                or payload.get('tool_choice') != {'type': 'function', 'function': {'name': TOOL}}
                                or payload.get('parallel_tool_calls') is not False):
                            raise ValueError('EVAL_FROZEN_PAYLOAD_CHANGED')
                    if owner.before_send: owner.before_send()
                    number = owner.budget.reserve(metadata, expected_number=owner.expected_number)
                except Exception:
                    owner.budget.close('BATCH_FAILED')
                    self.failure(429, 'EVAL_REQUEST_OR_BUDGET_REJECTED'); return
                observation = EvalSseObservation()
                headers_sent = False
                receipt_saved = False
                if owner.budget.identity.get('transport_policy'):
                    from tests.planning_material_matrix.transport_recovery import forward
                    request = urllib.request.Request(owner.upstream, data=body, method='POST', headers={
                        'Authorization': 'Bearer ' + owner._key, 'Content-Type': 'application/json'})
                    try:
                        forward(owner, self, request, metadata, number, EvalSseObservation)
                    except Exception:
                        # A ledger/storage failure is local, never a reason to
                        # submit the model again or expose raw exception text.
                        self.close_connection = True
                    return
                try:
                    request = urllib.request.Request(owner.upstream, data=body, method='POST', headers={
                        'Authorization': 'Bearer ' + owner._key, 'Content-Type': 'application/json'})
                    with owner.opener.open(request, timeout=300) as response:
                        self.send_response(response.status)
                        self.send_header('Content-Type', response.headers.get('Content-Type', 'text/event-stream'))
                        self.send_header('Transfer-Encoding', 'chunked'); self.end_headers()
                        headers_sent = True
                        while True:
                            data = response.read1(16384)
                            if not data: break
                            observation.feed(data)
                            self.wfile.write(f'{len(data):x}\r\n'.encode() + data + b'\r\n')
                            self.wfile.flush()
                        observation.finish_response()
                        owner.budget.finish(number, {'state': 'RESPONSE_COMPLETE', 'http_status': response.status,
                                                    **observation.result()})
                        receipt_saved = True
                        self.wfile.write(b'0\r\n\r\n'); self.wfile.flush()
                except urllib.error.HTTPError as error:
                    owner.budget.finish(number, {'state': 'HTTP_REJECTED', 'http_status': error.code})
                    owner.budget.close('UPSTREAM_HTTP_FAILED')
                    if not headers_sent: self.failure(error.code, 'EVAL_UPSTREAM_HTTP_FAILED')
                    error.close()
                except Exception:
                    # The reservation survives; no automatic retry or raw exception.
                    if not receipt_saved:
                        owner.budget.finish(number, {'state': 'UNKNOWN', **observation.result()})
                    owner.budget.close('UPSTREAM_UNKNOWN')
                    if not headers_sent:
                        try: self.failure(502, 'EVAL_UPSTREAM_UNKNOWN')
                        except OSError: pass
                    self.close_connection = True
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Proxy)
        self.server.daemon_threads = True
        self.url = f'http://127.0.0.1:{self.server.server_port}/v1'
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self):
        self.thread.start()
        return self

    def stop(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()


class EvalGateway:
    """One isolated installed Gateway, with one model and one HTTP exit.

    The Provider key belongs to the loopback proxy, never this Gateway. Agent
    network/process/session tools are absent; all model traffic reaches the cap.
    """
    def __init__(self, runtime, workspace, node, proxy, model_row, model_params=None):
        self.runtime, self.workspace, self.node = Path(runtime), Path(workspace), node
        self.workspace.mkdir(parents=True, exist_ok=False, mode=0o700)
        from easel.integrations.planning_structured import verify_runtime
        verify_runtime(self.runtime)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0)); self.port = sock.getsockname()[1]
        self.state = self.workspace / 'state'; self.state.mkdir(mode=0o700)
        config = {'gateway': {'mode': 'local', 'port': self.port, 'bind': 'loopback', 'auth': {'mode': 'none'}},
            'plugins': {'enabled': False}, 'channels': {},
            'tools': {'profile': 'minimal', 'alsoAllow': ['read', 'write', 'edit'],
                      'deny': ['group:runtime', 'group:web', 'group:ui', 'group:media', 'group:plugins',
                               'group:sessions', 'group:automation', 'group:messaging', 'group:nodes', 'group:agents'],
                      'fs': {'workspaceOnly': True}, 'elevated': {'enabled': False}},
            'agents': {'defaults': {'workspace': str(self.workspace.parent / 'eval-runtime'),
                'model': {'primary': 'minimax/' + proxy.model, 'fallbacks': []},
                'thinkingDefault': 'off', 'models': {'minimax/' + proxy.model: model_params or {}}}},
            'models': {'mode': 'replace', 'providers': {'minimax': {
                'baseUrl': proxy.url, 'api': 'openai-completions', 'apiKey': proxy.client_token,
                'models': [model_row]}}}}
        config_path = self.workspace / 'config.json'
        config_path.write_text(json.dumps(config)); config_path.chmod(0o600)
        blocker = self.workspace / 'loopback-only.mjs'
        blocker.write_text('''import net from 'node:net';
const connect=net.Socket.prototype.connect;
net.Socket.prototype.connect=function(...args){
 const first=Array.isArray(args[0])?args[0][0]:args[0];
 if(typeof first==='object' && first.path && !first.port)return connect.apply(this,args);
 const host=typeof first==='object'?first.host:(typeof args[1]==='string'?args[1]:'localhost');
 if(!['localhost','127.0.0.1','::1',undefined].includes(host))throw Error('EVAL_NETWORK_BLOCKED');
 return connect.apply(this,args);
};
''')
        self.env = {'PATH': str(Path(node).parent) + ':/usr/bin:/bin', 'HOME': str(self.workspace),
            'OPENCLAW_STATE_DIR': str(self.state), 'OPENCLAW_CONFIG_PATH': str(config_path),
            'OPENCLAW_DISABLE_MDNS': '1', 'NODE_OPTIONS': '--import=' + blocker.as_uri()}
        self.command = [node, str(self.runtime / 'openclaw.mjs')]
        self.process = None

    def start(self):
        with (self.workspace / 'gateway.log').open('w') as log:
            self.process = subprocess.Popen([*self.command, 'gateway', '--allow-unconfigured'],
                cwd=self.workspace, env=self.env, stdout=log, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            if self.process.poll() is not None: raise RuntimeError('EVAL_GATEWAY_EXITED')
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{self.port}/healthz', timeout=1) as response:
                    if response.status == 200: return self
            except OSError: time.sleep(.2)
        raise RuntimeError('EVAL_GATEWAY_NOT_READY')

    def rpc(self, method, params):
        response = subprocess.run([*self.command, 'gateway', 'call', method, '--json', '--params',
            json.dumps(params, ensure_ascii=False), '--timeout', '15000'], env=self.env,
            cwd=self.workspace, text=True, capture_output=True, timeout=30)
        if response.returncode: raise RuntimeError('EVAL_GATEWAY_RPC_FAILED')
        return json.loads(response.stdout)

    def stop(self):
        if self.process is not None:
            self.process.terminate()
            try: self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill(); self.process.wait()


def main(runtime, workspace, node, raw_path=None, scenario='valid', schema_path=None, *, http_budget=None,
         model_params=None, expected_payload=None, expected_number=None,
         model_max_tokens=16000, expected_model_params=None, model_row=None,
         argument_chunk_chars=None):
    from easel.integrations.planning_result_contract import semantic_tool_schema
    from easel.integrations.planning_structured import request_for
    if argument_chunk_chars is not None and (type(argument_chunk_chars) is not int
            or not 1 <= argument_chunk_chars <= 65536):
        raise ValueError('Offline argument chunk size must be a bounded positive integer')
    workspace.mkdir(parents=True, exist_ok=False)
    calls = []
    value = {'needs': [{'scope': 'scene-1', 'role': '背景', 'modality': 'image',
        'necessity': 'required', 'conditions': [{'text': '一张白纸',
        'strength': 'required', 'responsibility': 'material'}]}]}
    raw = raw_path.read_text() if raw_path else json.dumps(value, ensure_ascii=False)
    marker = 'synthetic-private-candidate-' + 'z' * 24
    if scenario == 'sensitive_debug':
        raw = json.dumps({'api_key': marker})
    schema = semantic_tool_schema({'scene': {'scene-1': '一张白纸'}})
    if schema_path is not None:
        schema = json.loads(schema_path.read_text())
    structured = request_for(schema)
    model_row = model_row or {'id': 'MiniMax-M3', 'name': 'offline fixture',
        'reasoning': False, 'input': ['text'], 'contextWindow': 200000, 'maxTokens': model_max_tokens}
    model_id = model_row['id']

    class Provider(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            calls.append({'tool_names': [tool['function']['name'] for tool in payload.get('tools', [])],
                          'tool_choice': payload.get('tool_choice'),
                          'description': payload.get('tools', [{}])[0].get('function', {}).get('description'),
                          'thinking': payload.get('thinking'), 'max_tokens': payload.get('max_tokens'),
                          'max_completion_tokens': payload.get('max_completion_tokens'),
                          'schema_equal': payload.get('tools', [{}])[0].get('function', {}).get('parameters') == schema})
            if scenario in {'redirect307', 'redirect308'}:
                self.send_response(int(scenario[-3:]))
                self.send_header('Location', f'http://127.0.0.1:{self.server.server_port}/v1/redirected')
                self.send_header('Content-Length', '0')
                self.end_headers()
                return
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.end_headers()
            messages = [
                {'id': 'offline-result', 'choices': [{'index': 0, 'delta': {'tool_calls': [
                    {'index': 0, 'id': 'original-native-call', 'type': 'function',
                     'function': {'name': 'submit_semantic_plan', 'arguments': raw}}]}, 'finish_reason': None}]},
                {'id': 'offline-result', 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'tool_calls'}]},
            ]
            if argument_chunk_chars is not None:
                pieces = [raw[i:i + argument_chunk_chars] for i in range(0, len(raw), argument_chunk_chars)]
                messages = [{'id': 'offline-result', 'choices': [{'index': 0, 'delta': {'tool_calls': [
                    {'index': 0, **({'id': 'original-native-call', 'type': 'function'} if i == 0 else {}),
                     'function': {**({'name': 'submit_semantic_plan'} if i == 0 else {}), 'arguments': piece}}]},
                    'finish_reason': None}]} for i, piece in enumerate(pieces)] + [messages[-1]]
            if scenario in {'terminal_stop', 'terminal_length'}:
                messages[-1]['choices'][0]['finish_reason'] = scenario.removeprefix('terminal_')
            if scenario == 'sdk_missing_finish':
                messages = messages[:-1]  # Complete HTTP, absent Provider terminal; external fixture only.
            for message in messages:
                self.wfile.write(('data: ' + json.dumps(message) + '\n\n').encode())
            if scenario != 'sdk_missing_finish':
                self.wfile.write(b'data: [DONE]\n\n')
            self.wfile.flush()

    provider = ThreadingHTTPServer(('127.0.0.1', 0), Provider)
    threading.Thread(target=provider.serve_forever, daemon=True).start()
    proxy = (EvalProviderProxy(http_budget, f'http://127.0.0.1:{provider.server_port}/v1/chat/completions',
        model_id, 'offline-placeholder', offline=True, expected_payload=expected_payload,
        expected_number=expected_number, expected_model_params=expected_model_params).start() if http_budget else None)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    state = workspace / 'state'
    state.mkdir()
    config = {'gateway': {'mode': 'local', 'port': port, 'bind': 'loopback', 'auth': {'mode': 'none'}},
              'plugins': {'enabled': False}, 'channels': {},
              'agents': {'defaults': {'workspace': str(workspace / 'agent-workspace'),
                  'model': {'primary': 'minimax/' + model_id, 'fallbacks': []},
                  'thinkingDefault': 'off', 'models': {'minimax/' + model_id: model_params or {}}}},
              'models': {'mode': 'replace', 'providers': {'minimax': {
                  'baseUrl': proxy.url if proxy else f'http://127.0.0.1:{provider.server_port}/v1', 'api': 'openai-completions',
                  'apiKey': proxy.client_token if proxy else 'offline-placeholder', 'models': [model_row]}}}}
    config_path = workspace / 'config.json'
    config_path.write_text(json.dumps(config))
    blocker = workspace / 'network-boundary.mjs'
    blocker.write_text('''import net from 'node:net';
const connect=net.Socket.prototype.connect;
net.Socket.prototype.connect=function(...args){
 const first=Array.isArray(args[0])?args[0][0]:args[0];
 if(typeof first==='object' && first.path && !first.port)return connect.apply(this,args);
 const host=typeof first==='object'?first.host:(typeof args[1]==='string'?args[1]:'localhost');
 if(!['localhost','127.0.0.1','::1',undefined].includes(host))throw Error('OFFLINE_NETWORK_BLOCKED');
 return connect.apply(this,args);
};
''')
    env = {'PATH': str(Path(node).parent) + ':/usr/bin:/bin',
           'OPENCLAW_STATE_DIR': str(state), 'OPENCLAW_CONFIG_PATH': str(config_path),
           'OPENCLAW_DISABLE_MDNS': '1', 'NODE_OPTIONS': '--import=' + blocker.as_uri()}
    if scenario == 'sensitive_debug':
        env['OPENCLAW_DEBUG_PROXY_ENABLED'] = '1'
    command = [node, str(runtime / 'openclaw.mjs')]
    log_path = workspace / 'gateway.log'
    with log_path.open('w') as log:
        gateway = subprocess.Popen([*command, 'gateway', '--allow-unconfigured'], cwd=workspace,
                                   env=env, stdout=log, stderr=subprocess.STDOUT)
    def rpc(method, params):
        result = subprocess.run([*command, 'gateway', 'call', method,
            '--json', '--params', json.dumps(params, ensure_ascii=False)], env=env, cwd=workspace,
            text=True, capture_output=True, timeout=30)
        if result.returncode:
            (workspace / 'rpc-error.txt').write_text(result.stderr + result.stdout)
            raise RuntimeError('Isolated RPC failed; see isolated rpc-error.txt')
        return json.loads(result.stdout)
    report = {'kind': 'isolated-native-gateway', 'scenario': scenario,
              'real_model_calls': 0, 'production_touched': False}
    try:
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            if gateway.poll() is not None:
                raise RuntimeError('Isolated Gateway exited; see isolated gateway.log')
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/healthz', timeout=1) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(.2)
        else:
            raise RuntimeError('Isolated Gateway did not become ready')
        run_id = 'offline-structured-run'
        submitted = rpc('agent', {'message': 'Return the semantic plan for one white paper image.',
            'agentId': 'main', 'sessionKey': 'agent:main:structured-fixture',
            'sessionId': 'structured-fixture', 'idempotencyKey': run_id,
            'deliver': False, 'timeout': 30, 'easelStructuredResult': structured})
        report['submit_status'] = submitted.get('status')
        terminal = rpc('agent.wait', {'runId': run_id, 'timeoutMs': 35000})
        report.update(terminal=terminal, provider_calls=calls)
        (workspace / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
        assert len(calls) == 1 and calls[0]['schema_equal'], 'Actual payload changed or retried'
        assert calls[0]['tool_names'] == ['submit_semantic_plan']
        if scenario == 'valid':
            assert terminal.get('status') == 'ok', 'Original isolated run did not succeed'
            assert terminal.get('stopReason') == 'tool_calls', 'Original terminal is not a tool candidate'
        else:
            assert terminal.get('status') != 'ok' or terminal.get('stopReason') != 'tool_calls'
    finally:
        gateway.terminate()
        try:
            gateway.wait(timeout=10)
        except subprocess.TimeoutExpired:
            gateway.kill()
            gateway.wait()
        provider.shutdown()
        if proxy: proxy.stop()
    if scenario == 'sensitive_debug':
        import gzip, sqlite3
        capture_rows = 0
        for path in workspace.rglob('*'):
            if not path.is_file():
                continue
            assert marker.encode() not in path.read_bytes(), 'Synthetic sensitive content persisted'
            if path.suffix != '.sqlite':
                continue
            with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as connection:
                tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")]
                for table in tables:
                    quoted = '"' + table.replace('"', '""') + '"'
                    for row in connection.execute('SELECT * FROM ' + quoted):
                        if table.endswith('capture_events'):
                            capture_rows += 1
                        for item in row:
                            content = item.encode() if isinstance(item, str) else item if isinstance(item, bytes) else b''
                            if content.startswith(b'\x1f\x8b'):
                                content = gzip.decompress(content)
                            assert marker.encode() not in content, 'Synthetic sensitive content in persisted payload'
        report.update(sensitive_persistence='ABSENT', debug_capture_rows=capture_rows)
        assert capture_rows > 0, 'Debug capture was not actually enabled'
    # Use the real read-only adapter in a new process after Gateway shutdown.
    # Report every changed file; do not infer read-only behavior from the API name.
    from easel.integrations.planning_transcript import read_original
    def snapshot():
        return {str(p.relative_to(state)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in state.rglob('*') if p.is_file()}
    before = snapshot()
    capture = read_original(command, 'fixture', {
        'agent_id': 'main', 'session_key': 'agent:main:structured-fixture',
        'session_id': 'structured-fixture', 'run_id': run_id,
        'reply_contract': 'planning-result-v3',
        'structured_result': {key: structured[key] for key in ('version', 'name', 'schemaSha256')}}, env=env)
    after = snapshot()
    changed = [name for name in sorted(before.keys() | after.keys()) if before.get(name) != after.get(name)]
    report['capture'] = {key: value for key, value in capture.items() if key != 'text'}
    report['read_changed_files'] = changed
    report['read_before'] = before
    report['read_after'] = after
    (workspace / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    if scenario == 'valid':
        assert capture.get('state') == 'FOUND' and capture.get('text') == raw
        assert capture.get('toolCallId') == 'original-native-call'
    else:
        assert capture.get('state') != 'FOUND'
    if scenario in {'terminal_stop', 'terminal_length', 'sensitive_debug', 'sdk_missing_finish'}:
        from scripts.patch_openclaw_structured_result import digest
        guard_folder = state / 'easel-structured-requests'
        files = list(guard_folder.glob('rejection-*.json'))
        assert len(files) == 1, 'Original rejection metadata missing or duplicated'
        diagnostic = json.loads(files[0].read_text())
        assert diagnostic['runId'] == run_id and diagnostic['sessionId'] == 'structured-fixture'
        assert diagnostic['schemaSha256'] == structured['schemaSha256']
        if scenario == 'sdk_missing_finish':
            assert diagnostic['category'] == 'STRUCTURED_SDK_FINISH_REASON_MISSING'
            assert diagnostic['providerFinishValue'] == 'MISSING'
            assert diagnostic['toolCallCount'] == 1, 'SDK cleanup erased the pre-error tool shape'
            assert diagnostic['uniqueExpectedTool'] is True
        elif scenario.startswith('terminal_'):
            assert diagnostic['category'] == 'STRUCTURED_TERMINAL_REJECTED'
            assert diagnostic['providerFinishValue'] == scenario.removeprefix('terminal_')
            # length discards the unfinished tool in the installed native reducer.
            expected_count = 0 if scenario == 'terminal_length' else 1
            assert diagnostic['toolCallCount'] == expected_count
            assert diagnostic['uniqueExpectedTool'] == (expected_count == 1)
        else:
            assert diagnostic['category'] == 'STRUCTURED_STORAGE_REJECTED'
        report['first_rejection'] = diagnostic
        report['first_rejection_sha256'] = digest(files[0].read_bytes())
        report['first_rejection_private'] = files[0].stat().st_mode & 0o077 == 0
        assert report['first_rejection_private']
    # SQLite mode=ro can create SHM and an empty WAL while opening a closed
    # WAL-mode database. It must not change database bytes or an existing WAL.
    empty_sha = hashlib.sha256(b'').hexdigest()
    coordination_only = all(name.endswith('.sqlite-shm') or
        name.endswith('.sqlite-wal') and name not in before and after[name] == empty_sha
        for name in changed)
    assert coordination_only, 'Read-only adapter changed persisted state; inspect file hashes'
    report['database_and_existing_wal_unchanged'] = True
    report['new_read_coordination_files'] = changed
    # Keep full file manifests locally; committed evidence uses only relevant differences.
    (workspace / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runtime', type=Path)
    parser.add_argument('workspace', type=Path)
    parser.add_argument('node')
    parser.add_argument('--raw', type=Path)
    parser.add_argument('--schema', type=Path)
    parser.add_argument('--scenario', choices=['valid', 'redirect307', 'redirect308', 'sensitive_debug',
                                              'terminal_stop', 'terminal_length'], default='valid')
    args = parser.parse_args()
    report = main(args.runtime, args.workspace, args.node, args.raw, args.scenario, args.schema)
    print(json.dumps({key: value for key, value in report.items()
                      if key not in {'read_before', 'read_after'}}, ensure_ascii=False, indent=2))
