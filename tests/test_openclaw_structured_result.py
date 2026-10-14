"""Offline native storage/submission boundary; no Gateway or Provider calls."""
from pathlib import Path
import json
import shutil
import subprocess
import pytest


@pytest.mark.parametrize('case', ['complete', 'connect_once', 'connect_exhausted', 'http401', 'http429',
    'after_send', 'partial_response', 'retry_budget', 'retry_deadline', 'retry_authorization'])
def test_phase_aware_proxy_retries_only_proven_unsent(tmp_path, monkeypatch, case):
    """Real local HTTP proxy, socket client and ledger; only upstream is a fixture."""
    import errno, threading, urllib.request, urllib.error
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from tests.planning_material_matrix import transport_recovery as transport
    from tests.planning_material_matrix.structured_gateway import EvalHttpBudget, EvalProviderProxy
    marker = 'synthetic-private-exception-must-not-be-saved'
    raw = b'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n'
    received, opened, checks = [], [], []
    clock = [100.]
    class Upstream(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_POST(self):
            received.append(self.rfile.read(int(self.headers['Content-Length'])))
            if case == 'after_send':
                self.connection.shutdown(2); self.connection.close(); return
            status = int(case[4:]) if case.startswith('http') else 200
            data = marker.encode() if status != 200 else raw
            self.send_response(status)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data[:8] if case == 'partial_response' else data)
            self.wfile.flush()
    server = ThreadingHTTPServer(('127.0.0.1', 0), Upstream)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    origin = f'http://127.0.0.1:{server.server_port}/v1/chat/completions'
    policy = transport.POLICY
    budget = EvalHttpBudget(tmp_path / 'ledger', 'a' * 64, transport_policy=policy,
        limit=1 if case == 'retry_budget' else 40, clock=lambda: clock[0])
    def authorize():
        checks.append(True)
        if len(checks) == 2:
            if case == 'retry_deadline': clock[0] += 2700
            if case == 'retry_authorization': raise ValueError(marker)
    native_init = transport._HTTPConnection.__init__
    def setup(self, *args, **kwargs):
        native_init(self, *args, **kwargs)
        create = self._create_connection
        def connect(*args, **kwargs):
            opened.append(True)
            if case in {'connect_exhausted', 'retry_budget', 'retry_deadline', 'retry_authorization'} or (
                    case == 'connect_once' and len(opened) == 1):
                raise ConnectionRefusedError(errno.ECONNREFUSED, marker)
            return create(*args, **kwargs)
        self._create_connection = connect
    monkeypatch.setattr(transport._HTTPConnection, '__init__', setup)
    proxy = EvalProviderProxy(budget, origin, 'fixture-model', 'fixture-only-key', offline=True,
                              before_send=authorize).start()
    try:
        request = urllib.request.Request(proxy.url + '/chat/completions',
            data=b'{"model":"fixture-model","max_tokens":64}',
            headers={'Authorization': 'Bearer ' + proxy.client_token})
        content = b''
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                try: content = response.read()
                except __import__('http.client').client.IncompleteRead: pass
        except urllib.error.HTTPError as error:
            content = error.read(); error.close()
        if case in {'complete', 'connect_once'}: assert content == raw
        assert marker.encode() not in content
    finally:
        proxy.stop(); server.shutdown(); server.server_close(); thread.join()
    state = json.loads(budget.path.read_text())
    attempts = state['requests']
    assert len(attempts) == (2 if case in {'connect_once', 'connect_exhausted'} else 1)
    assert len(received) == (1 if case in {'complete', 'connect_once', 'http401', 'http429', 'after_send', 'partial_response'} else 0)
    if case.startswith('connect') or case.startswith('retry'):
        assert attempts[0]['state'] == 'NOT_SENT'
        assert attempts[0]['transport']['request_write_attempted'] is False
        assert attempts[0]['transport']['category'] == 'CONNECTION_REFUSED'
        assert len(checks) == 2
    if case == 'connect_once':
        assert attempts[1]['connection_retry_of'] == 1
        assert attempts[1]['request_sha256'] == attempts[0]['request_sha256']
    if case in {'complete', 'connect_once'}:
        assert attempts[-1]['state'] == 'RESPONSE_COMPLETE'
        assert attempts[-1]['transport']['request_write_attempted'] is True
        assert attempts[-1]['transport']['response_complete'] is True
        assert not state['closed']
    else:
        assert state['closed']
        if case in {'after_send', 'partial_response'}:
            assert attempts[0]['state'] == 'UNKNOWN'
            assert attempts[0]['transport']['request_write_attempted'] is True
        if case.startswith('http'): assert attempts[0]['state'] == 'HTTP_REJECTED'
    assert marker not in budget.path.read_text() and 'fixture-only-key' not in budget.path.read_text()
    with pytest.raises(ValueError):
        EvalHttpBudget(tmp_path / 'ledger', 'a' * 64)  # No silent upgrade/downgrade.


@pytest.mark.parametrize('tunnel', [False, True])
def test_https_setup_failure_is_not_application_send(monkeypatch, tunnel):
    import socket, ssl
    from tests.planning_material_matrix import transport_recovery as transport
    for error in (TimeoutError('private'), ssl.SSLCertVerificationError(1, 'private')):
        progress = transport.Progress()
        connection = transport._HTTPSConnection('example.invalid', progress=progress)
        assert connection._context.context.verify_mode == ssl.CERT_REQUIRED
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(('127.0.0.1', 0)); listener.listen(1)
        left = socket.create_connection(listener.getsockname(), timeout=2)
        right, _ = listener.accept(); listener.close()
        connection._create_connection = lambda *_a, **_k: left
        if tunnel:
            connection.set_tunnel('example.invalid')
            # Exercise native send inside CONNECT setup; it is not POST data.
            connection._tunnel = lambda: connection.send(b'CONNECT example.invalid:443 HTTP/1.1\r\n\r\n')
        class Handshake:
            def wrap_socket(self, *_args, **kwargs):
                assert kwargs['server_hostname'] == 'example.invalid'
                raise error
        connection._context.context = Handshake()
        try:
            with pytest.raises(type(error)):
                connection.send(b'POST /v1/chat/completions HTTP/1.1\r\n')
            evidence = transport.failure_evidence(error, progress)
            assert evidence['phase'] == 'TLS_HANDSHAKE' and evidence['submission'] == 'NOT_SENT'
            assert evidence['safe_connection_retry'] == isinstance(error, TimeoutError)
            right.settimeout(1 if tunnel else 0)
            try: sent = right.recv(4096)
            except BlockingIOError: sent = b''
            assert b'POST' not in sent
            assert bool(sent) == tunnel
        finally:
            connection.close(); right.close()
    # A plain timeout without connection/write instrumentation proves nothing.
    assert transport.failure_evidence(TimeoutError(), transport.Progress())['submission'] == 'UNKNOWN'


@pytest.mark.parametrize('fault', ['client_midstream', 'client_after_receipt', 'receipt_write'])
def test_completed_upstream_is_not_retried_for_local_failure(tmp_path, monkeypatch, fault):
    import io
    from types import SimpleNamespace
    from tests.planning_material_matrix import transport_recovery as transport
    from tests.planning_material_matrix.structured_gateway import EvalHttpBudget, EvalSseObservation
    budget = EvalHttpBudget(tmp_path / 'ledger', 'b' * 64, transport_policy=transport.POLICY)
    number = budget.reserve({'request_sha256': 'c' * 64})
    raw = b'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n'
    opens, writes = [], []
    class Response(io.BytesIO):
        status = 200
        headers = {}
        length = None
    class Opener:
        def __init__(self, progress): self.progress = progress
        def open(self, *_args, **_kwargs):
            opens.append(True)
            self.progress.connection_observed = self.progress.request_write_attempted = True
            return Response(raw)
    monkeypatch.setattr(transport, 'observed_opener', Opener)
    class Sink(io.BytesIO):
        def write(self, data):
            if fault == 'client_midstream' or fault == 'client_after_receipt' and data == b'0\r\n\r\n':
                raise BrokenPipeError('do-not-log-private-text')
            return super().write(data)
    finish = budget.finish
    def save(number, value):
        writes.append(value)
        if fault == 'receipt_write': raise OSError('do-not-log-private-text')
        return finish(number, value)
    monkeypatch.setattr(budget, 'finish', save)
    client = SimpleNamespace(wfile=Sink(), send_response=lambda *_: None, send_header=lambda *_: None,
        end_headers=lambda: None, failure=lambda *_: None, close_connection=False)
    owner = SimpleNamespace(budget=budget, before_send=lambda: pytest.fail('No network retry'), expected_number=None)
    transport.forward(owner, client, object(), {}, number, EvalSseObservation)
    state = json.loads(budget.path.read_text())
    assert len(opens) == len(writes) == len(state['requests']) == 1
    assert state['closed'] and client.close_connection
    if fault == 'client_after_receipt':
        assert state['requests'][0]['state'] == 'RESPONSE_COMPLETE'
        assert state['close_reason'] == 'LOCAL_DELIVERY_FAILED'
    elif fault == 'receipt_write':
        assert writes[0]['transport']['response_complete'] is True
        assert state['requests'][0]['state'] == 'UNKNOWN'
        assert state['close_reason'] == 'LOCAL_RECEIPT_FAILED'
    else:
        assert state['requests'][0]['state'] == 'UNKNOWN'
        assert state['requests'][0]['transport']['phase'] == 'CLIENT_DELIVERY'
    assert 'do-not-log-private-text' not in budget.path.read_text()


@pytest.mark.parametrize('decision', ['PASS', 'FAIL'])
def test_engineering_planning_check_not_stability_or_media_grant(tmp_path, decision):
    import hashlib
    from tests.planning_material_matrix import planning_eval_run as runner
    from tests.planning_material_matrix.structured_gateway import EvalHttpBudget
    from tests.planning_material_matrix.transport_recovery import POLICY
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps({'schema': runner.ENGINEERING_SCHEMA, 'transport_policy': POLICY}))
    identity = hashlib.sha256(manifest.read_bytes()).hexdigest()
    budget = EvalHttpBudget(tmp_path / 'actual-http', identity, transport_policy=POLICY)
    number = budget.reserve({}); budget.finish(number, {'state': 'RESPONSE_COMPLETE'})
    directory = tmp_path / 'runs'; directory.mkdir()
    path = directory / 'run-00.json'
    path.write_text(json.dumps({'manifest_sha256': identity, 'result': 'CONTRACT_VALID_SEMANTICS_PENDING',
                               'semantic_review': 'NOT_REVIEWED'}))
    runner.record_convergence_review(tmp_path, manifest, 0, decision, {'kind': 'fixed independent oracle fixture'})
    result = json.loads(path.read_text()); state = json.loads(budget.path.read_text())
    assert result['semantic_review'] == decision
    assert result['formal_qualification'] is False and result['production_dispatch_allowed'] is False
    assert state['closed']
    assert state['close_reason'] == ('BATCH_COMPLETE' if decision == 'PASS' else 'BATCH_FAILED')
    with pytest.raises(ValueError): budget.reserve({})
    with pytest.raises(runner.EvalStateViolation):
        runner.record_convergence_review(tmp_path, manifest, 0, 'PASS', {'kind': 'cannot regrade'})
    assert runner.transport_policy_for({'schema': 'planning-qualification-eval@2'}) is None
    with pytest.raises(runner.EvalStateViolation):
        runner.transport_policy_for({'schema': runner.ENGINEERING_SCHEMA})


def test_eval_actual_http_ceiling_and_pre_sdk_observation(tmp_path):
    """One final HTTP boundary covers structured and ordinary model calls."""
    import concurrent.futures
    import hashlib
    import threading
    import urllib.request
    import urllib.error
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from tests.planning_material_matrix.structured_gateway import (
        EvalHttpBudget, EvalProviderProxy, EvalSseObservation,
    )
    marker = 'synthetic-sensitive-error-content'
    raw = ('data: ' + json.dumps({'choices': [{'delta': {'tool_calls': [{'function': {
        'arguments': '{"text":"中文🖼️"}'}}]}, 'finish_reason': None}]}, ensure_ascii=False)
        + '\n\ndata: {"choices":[{"delta":{},"finish_reason":"tool_calls"}]}\n\n'
        + 'data: [DONE]\n\n').encode()
    calls = []
    mode = ['valid']
    class Upstream(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_POST(self):
            body = self.rfile.read(int(self.headers['Content-Length']))
            calls.append((body, self.headers.get('Authorization')))
            if mode[0] == 'redirect':
                self.send_response(307); self.send_header('Location', '/second')
                self.send_header('Content-Length', '0'); self.end_headers(); return
            if mode[0] == 'sensitive':
                value = marker.encode()
                self.send_response(400); self.send_header('Content-Length', str(len(value)))
                self.end_headers(); self.wfile.write(value); return
            if mode[0] == 'disconnect':
                self.connection.close(); return
            self.send_response(200); self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Content-Length', str(len(raw))); self.end_headers()
            for i in range(0, len(raw), 3): self.wfile.write(raw[i:i+3])
            self.wfile.flush()
    upstream = ThreadingHTTPServer(('127.0.0.1', 0), Upstream)
    thread = threading.Thread(target=upstream.serve_forever, daemon=True); thread.start()
    origin = f'http://127.0.0.1:{upstream.server_port}/v1/chat/completions'
    manifest = hashlib.sha256(b'frozen-evaluation-manifest').hexdigest()
    clock = [100.0]
    budget = EvalHttpBudget(tmp_path / 'budget', manifest, clock=lambda: clock[0])
    proxy = EvalProviderProxy(budget, origin, 'fixture-model', 'upstream-only-placeholder',
                              offline=True, client_token='private-local-placeholder').start()
    def send(index):
        # Truth has no structured tool at all. It still crosses the same cap.
        payload = {'model': 'fixture-model', 'messages': [{'role': 'user', 'content': f'round-{index}'}],
                   'max_tokens': 8192}
        if index % 3:
            payload['tools'] = [{'type': 'function', 'function': {'name': 'submit_semantic_plan',
                'parameters': {'type': 'object', 'title': 'A' if index % 3 == 1 else 'B'}}}]
        body = json.dumps(payload).encode()
        request = urllib.request.Request(proxy.url + '/chat/completions', data=body,
            headers={'Authorization': 'Bearer ' + proxy.client_token, 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                assert response.read() == raw, 'Proxy changed successful Provider response bytes'
            return True
        except urllib.error.HTTPError as error:
            assert error.code == 429
            error.close(); return False
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            outcomes = list(pool.map(send, range(41)))
        assert sum(outcomes) == 40 and len(calls) == 40
        assert all(auth == 'Bearer upstream-only-placeholder' for _, auth in calls)
        state = json.loads(budget.path.read_text())
        assert state['closed'] and len(state['requests']) == 40
        assert all(row['provider_finish'] == 'tool_calls' and row['sse_done'] for row in state['requests'])
        assert all(row['run_identity'] == 'UNKNOWN' for row in state['requests'])
        assert any(row['schema_sha256'] is None for row in state['requests']), 'Ordinary Truth bypassed budget'
        assert all(row['response_bytes'] == len(raw) for row in state['requests'])
        restarted = EvalHttpBudget(tmp_path / 'budget', manifest, clock=lambda: clock[0])
        import pytest
        with pytest.raises(ValueError, match='EVAL_HTTP_LIMIT'): restarted.reserve({})
        assert marker not in budget.path.read_text() and 'upstream-only-placeholder' not in budget.path.read_text()
    finally:
        proxy.stop()
    # Crash/UNKNOWN is retained across restart, and expiry cannot refresh time.
    for name, scenario in [('unknown', None), ('deadline', 2700), ('rollback', -1)]:
        root = tmp_path / name
        timer = [100.0]
        current = EvalHttpBudget(root, manifest, clock=lambda: timer[0])
        current.reserve({'request_sha256': 'f' * 64})
        restored = EvalHttpBudget(root, manifest, clock=lambda: timer[0])
        if scenario is None:
            restored.close()
        else: timer[0] += scenario
        with pytest.raises(ValueError, match='EVAL_HTTP_LIMIT'): restored.reserve({})
        saved = json.loads(restored.path.read_text())
        assert saved['requests'][0]['state'] == 'UNKNOWN' and saved['first_reserved_at'] == 100
    # Redirect and sensitive errors cannot be replayed or persisted as free text.
    for scenario in ('redirect', 'sensitive', 'disconnect'):
        mode[0] = scenario
        case_budget = EvalHttpBudget(tmp_path / scenario, manifest)
        case_proxy = EvalProviderProxy(case_budget, origin, 'fixture-model', 'upstream-only-placeholder',
                                       offline=True).start()
        before = len(calls)
        try:
            request = urllib.request.Request(case_proxy.url + '/chat/completions',
                data=b'{"model":"fixture-model"}', headers={'Authorization': 'Bearer ' + case_proxy.client_token})
            with pytest.raises(urllib.error.HTTPError) as rejected: urllib.request.urlopen(request, timeout=20)
            assert marker.encode() not in rejected.value.read()
            rejected.value.close()
            assert len(calls) == before + 1
            with pytest.raises(ValueError): case_budget.reserve({})
            assert marker not in case_budget.path.read_text()
        finally: case_proxy.stop()
    upstream.shutdown(); upstream.server_close(); thread.join()
    # A split UTF-8 codepoint and final reason survive diagnostic framing.
    observation = EvalSseObservation()
    for byte in raw: observation.feed(bytes([byte]))
    assert observation.result()['argument_delta_bytes'] == len('{"text":"中文🖼️"}'.encode())
    assert observation.result()['provider_finish'] == 'tool_calls' and observation.complete
    assert observation.pending == b''
    # A request sent before the deadline but completing afterwards cannot pass.
    late_clock = [100.]
    late = EvalHttpBudget(tmp_path / 'late-completion', manifest, clock=lambda: late_clock[0])
    request = late.reserve({})
    late_clock[0] += 2700
    late.finish(request, {'state': 'RESPONSE_COMPLETE'})
    with pytest.raises(ValueError, match='NOT_COMPLETE'): late.validate_completion()
    with pytest.raises(ValueError, match='EVAL_HTTP_LIMIT'): late.reserve({})
    # An authenticated pre-send callback failure seals the batch without HTTP.
    from tests.planning_material_matrix.planning_eval import EvalStateViolation
    blocked_budget = EvalHttpBudget(tmp_path / 'callback-failure', manifest)
    def reject_integrity(): raise EvalStateViolation('synthetic private detail')
    blocked_proxy = EvalProviderProxy(blocked_budget, origin, 'fixture-model', 'offline-placeholder',
        offline=True, before_send=reject_integrity).start()
    count = len(calls)
    try:
        request = urllib.request.Request(blocked_proxy.url + '/chat/completions',
            data=b'{"model":"fixture-model"}', headers={'Authorization': 'Bearer ' + blocked_proxy.client_token})
        for _ in range(2):
            with pytest.raises(urllib.error.HTTPError) as rejected: urllib.request.urlopen(request, timeout=20)
            assert b'synthetic private' not in rejected.value.read(); rejected.value.close()
        assert len(calls) == count
        with pytest.raises(ValueError): blocked_budget.validate_completion()
        with pytest.raises(ValueError): blocked_budget.reserve({})
    finally: blocked_proxy.stop()
    from tests.planning_material_matrix.planning_eval_run import accept_convergence_stage, record_convergence_review
    ordinary_fail = EvalHttpBudget(tmp_path / 'non-exception-fail', manifest)
    accept_convergence_stage({'result': 'FAIL'}, ordinary_fail)
    with pytest.raises(ValueError): ordinary_fail.reserve({})
    # Evaluation oracle FAIL seals only the batch; it cannot edit product files.
    review_root = tmp_path / 'independent-oracle'; (review_root / 'runs').mkdir(parents=True)
    manifest_file = review_root / 'manifest.json'; manifest_file.write_text('{"frozen_expected":"unchanged"}')
    manifest_digest = hashlib.sha256(manifest_file.read_bytes()).hexdigest()
    reviewed_budget = EvalHttpBudget(review_root / 'actual-http', manifest_digest)
    number = reviewed_budget.reserve({}); reviewed_budget.finish(number, {'state': 'RESPONSE_COMPLETE'})
    result_file = review_root / 'runs/run-04.json'
    result_file.write_text(json.dumps({'manifest_sha256': manifest_digest,
        'result': 'CONTRACT_VALID_SEMANTICS_PENDING', 'semantic_review': 'NOT_REVIEWED'}))
    record_convergence_review(review_root, manifest_file, 4, 'FAIL', {'missing_obligation': 'frozen expected'})
    with pytest.raises(ValueError): reviewed_budget.reserve({})
    assert json.loads(result_file.read_text())['result'] == 'FAIL'
    # The new six-item batch begins with an evaluation, not four probe slots.
    qualification_root = tmp_path / 'qualification-oracle'; (qualification_root / 'runs').mkdir(parents=True)
    qualification_manifest = qualification_root / 'manifest.json'
    qualification_manifest.write_text('{"schema":"planning-qualification-eval@1"}')
    qualification_digest = hashlib.sha256(qualification_manifest.read_bytes()).hexdigest()
    qualification_budget = EvalHttpBudget(qualification_root / 'actual-http', qualification_digest)
    number = qualification_budget.reserve({}); qualification_budget.finish(number, {'state': 'RESPONSE_COMPLETE'})
    result_file = qualification_root / 'runs/run-00.json'
    result_file.write_text(json.dumps({'manifest_sha256': qualification_digest,
        'result': 'CONTRACT_VALID_SEMANTICS_PENDING', 'semantic_review': 'NOT_REVIEWED'}))
    record_convergence_review(qualification_root, qualification_manifest, 0, 'FAIL', {'missing_obligation': 'frozen expected'})
    with pytest.raises(ValueError): qualification_budget.reserve({})
    with pytest.raises(EvalStateViolation):
        record_convergence_review(qualification_root, qualification_manifest, 0, 'PASS', {'cannot': 're-score'})
    # Preloading pure authorization readers must not exempt generation calls.
    from tests.planning_material_matrix.planning_eval import PlanningEvalBoundary
    from easel.integrations import material_generation
    boundary = PlanningEvalBoundary()
    with boundary.guarded():
        material_generation.authorized_generation_modalities({})
    assert not boundary.state_violations
    with pytest.raises(EvalStateViolation, match='Forbidden downstream entry'):
        with boundary.guarded(): material_generation.generation_budget_preview()
    assert boundary.state_violations == ['easel.integrations.material_generation:generation_budget_preview']


def test_pre_sdk_argument_fingerprint_is_complete_bounded_and_payload_free():
    """Hash the actual per-call deltas, never repair or persist their contents."""
    import hashlib
    from tests.planning_material_matrix.structured_gateway import EvalSseObservation
    raw = json.dumps({'slots': {'slot_000': {'text': '中文🖼️ "quote"\\n{}',
        'items': [None, False, 2]}}, 'unresolved': []}, ensure_ascii=False)
    other = '{"slots":"malformed nested JSON {", "unresolved":[]}'
    def event(fragment, *, index=0, call_id=None):
        call = {'index': index, 'function': {'arguments': fragment}}
        if call_id is not None:
            call['id'] = call_id
        return ('data: ' + json.dumps({'choices': [{'index': 0, 'delta': {
            'tool_calls': [call]}, 'finish_reason': None}]}, ensure_ascii=False) + '\n\n').encode()
    end = b'data: {"choices":[{"index":0,"delta":{},"finish_reason":"tool_calls"}]}\n\ndata: [DONE]\n\n'
    observation = EvalSseObservation()
    stream = event(raw[:12], call_id='fixture-call-0') + event(other, index=1, call_id='fixture-call-1') + event(raw[12:]) + end
    for byte in stream:
        observation.feed(bytes([byte]))  # Network chunks can bisect UTF-8.
    result = observation.result()
    assert result['argument_stream_state'] == 'COMPLETE'
    rows = result['argument_streams']
    assert [(r['choice_index'], r['tool_index']) for r in rows] == [(0, 0), (0, 1)]
    assert [r['sha256'] for r in rows] == [hashlib.sha256(v.encode()).hexdigest() for v in (raw, other)]
    assert [r['bytes'] for r in rows] == [len(v.encode()) for v in (raw, other)]
    assert [r['fragments'] for r in rows] == [2, 1]
    assert 'malformed' not in json.dumps(result) and 'fixture-call' not in json.dumps(result)
    for broken, expected in [(event(raw), 'INCOMPLETE'),
            (event(raw, call_id='first') + event('', call_id='different') + end, 'UNAVAILABLE'),
            (event(raw) + b'data: not-json\n\n' + end, 'UNAVAILABLE'),
            (event(raw) + end.replace(b'tool_calls', b'length'), 'INCOMPLETE'),
            (b''.join(event('x', index=i) for i in range(17)) + end, 'UNAVAILABLE')]:
        failed = EvalSseObservation()
        failed.feed(broken)
        report = failed.result()
        assert report['argument_stream_state'] == expected
        assert report['argument_streams'] == [], 'Partial fingerprints cannot claim complete attribution'
    # HTTP clean EOF and a completed tool choice are distinct from [DONE].
    # A fingerprint proves received bytes only; native terminal/schema gates remain.
    no_done = event(raw, call_id='eof-call') + end.split(b'data: [DONE]')[0]
    clean = EvalSseObservation(); clean.feed(no_done)
    assert clean.result()['argument_stream_state'] == 'INCOMPLETE'
    clean.finish_response()
    eof_result = clean.result()
    assert eof_result['argument_stream_state'] == 'COMPLETE'
    assert eof_result['argument_end_basis'] == 'HTTP_EOF_WITH_TOOL_FINISH'
    assert eof_result['sse_done'] is False
    assert eof_result['argument_streams'][0]['sha256'] == hashlib.sha256(raw.encode()).hexdigest()
    for broken in (event(raw), event(raw) + b'data: {"incomplete":',
                   no_done.replace(b'tool_calls"}', b'length"}')):
        incomplete = EvalSseObservation(); incomplete.feed(broken); incomplete.finish_response()
        assert incomplete.result()['argument_stream_state'] != 'COMPLETE'
        assert incomplete.result()['argument_streams'] == []
    post_terminal = EvalSseObservation(); post_terminal.feed(no_done + event('changed'))
    post_terminal.finish_response()
    assert post_terminal.result()['argument_stream_state'] == 'UNAVAILABLE'


def test_entry_observation_reasons_preserve_strict_completeness_and_hide_values():
    from tests.planning_material_matrix.structured_gateway import EvalSseObservation
    private = 'synthetic-private-finish-value'
    missing = object()
    def event(reason=missing, *, args=None, call_id='fixed-id', index=0):
        choice = {'index': 0, 'delta': {}}
        if reason is not missing: choice['finish_reason'] = reason
        if args is not None:
            choice['delta'] = {'tool_calls': [{'index': index, 'id': call_id,
                                               'function': {'arguments': args}}]}
        return ('data: ' + json.dumps({'choices': [choice]}, ensure_ascii=False) + '\n\n').encode()
    start = event(args='{"text":"中文🖼️"}')
    end = event('tool_calls')
    cases = [
        (start + event(None) + end, 'COMPLETE', set(), {'MISSING': 1, 'NULL': 1, 'RECOGNIZED': 1}),
        (start + event('') + end, 'COMPLETE', {'FINISH_EMPTY'}, {'EMPTY': 1}),
        (event('', args='{"text":', call_id='') + event('', args='"中文🖼️"}', call_id='fixed-id') + end,
         'COMPLETE', {'FINISH_EMPTY', 'CALL_ID_EMPTY'}, {'EMPTY': 2}),
        (start + event('', args='', call_id='') + end, 'COMPLETE', {'CALL_ID_EMPTY'}, {}),
        (start + event(private) + end, 'UNAVAILABLE', {'FINISH_UNRECOGNIZED', 'FINISH_CONFLICT'}, {'UNRECOGNIZED': 1}),
        (start + event({'private': private}) + end, 'UNAVAILABLE', {'FINISH_UNRECOGNIZED', 'FINISH_CONFLICT'}, {'UNRECOGNIZED': 1}),
        (start + event('stop') + end, 'UNAVAILABLE', {'FINISH_CONFLICT'}, {'RECOGNIZED': 2}),
        (start + event('tool_calls', args='', call_id='changed-id'), 'UNAVAILABLE', {'CALL_ID_CONFLICT'}, {}),
        (start + end + event(args='later'), 'UNAVAILABLE', {'ARGUMENT_AFTER_FINISH'}, {}),
        (start + end + event(''), 'UNAVAILABLE', {'EMPTY_FINISH_AFTER_TERMINAL'}, {}),
        (event(args='x', index=16) + end, 'UNAVAILABLE', {'CALL_INDEX_INVALID'}, {}),
        (event(args=[]) + end, 'UNAVAILABLE', {'ARGUMENT_TYPE_INVALID'}, {}),
        (start + b'data: not-json\n\n' + end, 'UNAVAILABLE', {'SSE_JSON_INVALID'}, {}),
        (start + b'data: []\n\n' + end, 'UNAVAILABLE', {'SSE_EVENT_SHAPE_INVALID'}, {}),
        (start + b'data: {"tail":', 'UNAVAILABLE', {'HTTP_TAIL_INCOMPLETE'}, {}),
        (start, 'INCOMPLETE', {'TOOL_FINISH_MISSING', 'ARGUMENT_FINISH_INCOMPLETE'}, {}),
    ]
    for stream, state, reasons, counts in cases:
        for width in (1, 17, 16384):
            observer = EvalSseObservation()
            for offset in range(0, len(stream), width): observer.feed(stream[offset:offset + width])
            observer.finish_response()
            result = observer.result()
            assert result['argument_stream_state'] == state
            assert reasons <= set(result['observation_reasons'])
            assert result['observation_source'] == 'PROVIDER_ENTRY'
            assert all(result['finish_classes'][k] == v for k, v in counts.items())
            assert private not in json.dumps(result) and 'fixed-id' not in json.dumps(result)
            if state != 'COMPLETE': assert result['argument_streams'] == []
    for invalid in (0, False, [], {}):
        for malformed in (event(invalid) + end, event(args='{}', call_id=invalid) + end):
            observer = EvalSseObservation(); observer.feed(malformed); observer.finish_response()
            assert observer.result()['argument_stream_state'] != 'COMPLETE'
    observer = EvalSseObservation(); observer.feed(start + end)
    assert observer.result()['observation_reasons'] == ['HTTP_BOUNDARY_INCOMPLETE']
    observer.finish_classes['NULL'] = 1_000_000
    observer.feed(event(None))
    assert observer.result()['finish_classes']['NULL'] == 1_000_000
    for data, code in [(b'data: ' + b'x' * 65536 + b'\n', 'SSE_LINE_LIMIT'),
                       (b'x' * 65537, 'SSE_BUFFER_LIMIT')]:
        observer = EvalSseObservation(); observer.feed(data); observer.finish_response()
        assert code in observer.result()['observation_reasons']
        assert observer.result()['argument_stream_state'] == 'UNAVAILABLE'


def test_structured_entry_unknown_seals_actual_proxy_and_cannot_reopen(tmp_path):
    import hashlib, threading, urllib.request, urllib.error
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from tests.planning_material_matrix.structured_gateway import EvalHttpBudget, EvalProviderProxy
    calls = []
    class Upstream(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_POST(self):
            calls.append(self.rfile.read(int(self.headers['Content-Length'])))
            raw = (b'data: {"choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"function":{"arguments":"{}"}}]},"finish_reason":"unexpected-finish"}]}\n\n'
                   b'data: {"choices":[{"index":0,"delta":{},"finish_reason":"tool_calls"}]}\n\n')
            self.send_response(200); self.send_header('Content-Length', str(len(raw)))
            self.send_header('Content-Type', 'text/event-stream'); self.end_headers(); self.wfile.write(raw)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Upstream)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    schema = {'type': 'object'}
    expected = {'model': 'fixture-model', 'max_tokens': None, 'max_completion_tokens': 8192,
                'schema_sha256': hashlib.sha256(json.dumps(schema, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
                'thinking_mode': 'disabled', 'tools_count': 1, 'tool_choice_kind': 'function'}
    budget = EvalHttpBudget(tmp_path / 'ledger', 'a' * 64, limit=4)
    proxy = EvalProviderProxy(budget, f'http://127.0.0.1:{server.server_port}/v1/chat/completions',
        'fixture-model', 'offline-only', offline=True, expected_payload=expected,
        request_identity={'cell': 1, 'run_id': 'diag-1', 'session_id': 'session-1'}).start()
    payload = {'model': 'fixture-model', 'max_completion_tokens': 8192, 'thinking': {'type': 'disabled'},
               'tools': [{'type': 'function', 'function': {'name': 'submit_semantic_plan', 'parameters': schema}}],
               'tool_choice': {'type': 'function', 'function': {'name': 'submit_semantic_plan'}}, 'parallel_tool_calls': False}
    def send():
        request = urllib.request.Request(proxy.url + '/chat/completions', json.dumps(payload).encode(),
            headers={'Authorization': 'Bearer ' + proxy.client_token, 'Content-Type': 'application/json'})
        return urllib.request.urlopen(request, timeout=10)
    try:
        with send() as response: response.read()
        saved = json.loads(budget.path.read_text())
        assert saved['closed'] and saved['close_reason'] == 'ENTRY_CAPTURE_UNAVAILABLE'
        row = saved['requests'][0]
        assert row['diagnostic_identity'] == {'cell': 1, 'run_id': 'diag-1', 'session_id': 'session-1'}
        assert row['identity_source'] == 'TRUSTED_CELL_PROXY'
        assert row['state'] == 'RESPONSE_COMPLETE' and row['argument_stream_state'] == 'UNAVAILABLE'
        assert row['finish_classes']['UNRECOGNIZED'] == 1
        with pytest.raises(urllib.error.HTTPError) as failure: send()
        assert failure.value.code == 429; failure.value.close()
        restored = EvalHttpBudget(tmp_path / 'ledger', 'a' * 64, limit=4)
        with pytest.raises(ValueError): restored.reserve({})
        with pytest.raises(ValueError): restored.finish(1, {'state': 'RESPONSE_COMPLETE', 'argument_stream_state': 'COMPLETE'})
        assert len(calls) == 1
        final = json.loads(budget.path.read_text())
        assert final['requests'] == saved['requests'] and final['first_reserved_at'] == saved['first_reserved_at']
    finally:
        proxy.stop(); server.shutdown(); server.server_close(); thread.join()


def test_concurrent_diagnostic_cells_share_cap_and_keep_entry_attribution(tmp_path):
    import concurrent.futures, hashlib, threading, urllib.request
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from tests.planning_material_matrix.structured_gateway import EvalHttpBudget, EvalProviderProxy
    barrier = threading.Barrier(4)
    class Upstream(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            cell = payload['messages'][0]['content']
            barrier.wait(timeout=10)  # All four HTTP requests are in flight.
            args = json.dumps({'cell': cell})
            frames = [
                {'choices': [{'index': 0, 'delta': {'tool_calls': [{'index': 0, 'id': 'call-' + cell,
                    'function': {'arguments': args}}]}, 'finish_reason': None}]},
                {'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'tool_calls'}]},
            ]
            data = ''.join('data: ' + json.dumps(f) + '\n\n' for f in frames).encode()
            self.send_response(200); self.send_header('Content-Length', str(len(data)))
            self.end_headers(); self.wfile.write(data)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Upstream)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    schema = {'type': 'object'}
    expected = {'model': 'fixture-model', 'max_tokens': None, 'max_completion_tokens': 8192,
        'schema_sha256': hashlib.sha256(json.dumps(schema, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
        'thinking_mode': 'disabled', 'tools_count': 1, 'tool_choice_kind': 'function'}
    budget = EvalHttpBudget(tmp_path / 'ledger', 'b' * 64, limit=4)
    proxies = [EvalProviderProxy(budget, f'http://127.0.0.1:{server.server_port}/v1/chat/completions',
        'fixture-model', 'offline-only', offline=True, expected_payload=expected,
        request_identity={'cell': n, 'run_id': 'run-' + str(n), 'session_id': 'session-' + str(n)}).start()
        for n in range(1, 5)]
    def send(n):
        proxy = proxies[n - 1]
        payload = {'model': 'fixture-model', 'messages': [{'role': 'user', 'content': str(n)}],
            'max_completion_tokens': 8192, 'thinking': {'type': 'disabled'},
            'tools': [{'type': 'function', 'function': {'name': 'submit_semantic_plan', 'parameters': schema}}],
            'tool_choice': {'type': 'function', 'function': {'name': 'submit_semantic_plan'}}, 'parallel_tool_calls': False}
        req = urllib.request.Request(proxy.url + '/chat/completions', json.dumps(payload).encode(),
            headers={'Authorization': 'Bearer ' + proxy.client_token})
        with urllib.request.urlopen(req, timeout=15) as response: response.read()
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool: list(pool.map(send, range(1, 5)))
        saved = json.loads(budget.path.read_text())
        assert len(saved['requests']) == 4
        assert {r['diagnostic_identity']['cell'] for r in saved['requests']} == {1, 2, 3, 4}
        for row in saved['requests']:
            cell = str(row['diagnostic_identity']['cell'])
            assert row['diagnostic_identity']['run_id'] == 'run-' + cell
            assert row['argument_stream_state'] == 'COMPLETE'
            assert row['argument_streams'][0]['sha256'] == hashlib.sha256(json.dumps({'cell': cell}).encode()).hexdigest()
        budget.validate_completion(); budget.close('BATCH_COMPLETE')
        with pytest.raises(ValueError): budget.reserve({})
    finally:
        for proxy in proxies: proxy.stop()
        server.shutdown(); server.server_close(); thread.join()


def test_empty_delta_metadata_matches_installed_sdk_without_changing_arguments(tmp_path):
    """Real pinned SDK/reducer/guard; only Provider fetch is a fixed SSE fixture."""
    import hashlib
    from easel.integrations.planning_structured import verify_runtime
    runtime = Path.home() / '.local/node-v24.21.0-darwin-arm64/lib/node_modules/openclaw'
    verify_runtime(runtime)
    raw = '{"text":"中文🖼️"}'
    frames = [
        {'choices': [{'index': 0, 'delta': {'tool_calls': [{'index': 0, 'id': '', 'type': 'function',
            'function': {'name': 'submit_semantic_plan', 'arguments': raw[:9]}}]}, 'finish_reason': ''}]},
        {'choices': [{'index': 0, 'delta': {'tool_calls': [{'index': 0, 'id': 'fixture-id',
            'function': {'arguments': raw[9:]}}]}, 'finish_reason': ''}]},
        {'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'tool_calls'}]},
    ]
    data = ''.join('data: ' + json.dumps(f, ensure_ascii=False) + '\n\n' for f in frames)
    from tests.planning_material_matrix.structured_gateway import EvalSseObservation
    observer = EvalSseObservation()
    for byte in data.encode(): observer.feed(bytes([byte]))
    observer.finish_response(); report = observer.result()
    assert report['argument_stream_state'] == 'COMPLETE'
    assert report['finish_classes']['EMPTY'] == 2 and report['empty_call_ids'] == 1
    assert report['argument_streams'][0]['sha256'] == hashlib.sha256(raw.encode()).hexdigest()
    fixture = tmp_path / 'sse.txt'; fixture.write_text(data)
    script = tmp_path / 'sdk-empty-metadata.mjs'
    script.write_text('''
import assert from 'node:assert/strict';import fs from 'node:fs';import path from 'node:path';import net from 'node:net';
const [root,dir,fixture]=process.argv.slice(2);
net.Socket.prototype.connect=()=>{throw Error('OFFLINE_NETWORK_BLOCKED')};
const guard=await import(path.join(root,'dist/easel-structured-result.mjs'));
const {createOpenAICompletionsTransportStreamFn}=await import(path.join(root,'node_modules/@openclaw/ai/dist/transports.mjs'));
const {t:configure}=await import(path.join(root,'node_modules/@openclaw/ai/dist/host-B8YfDGd4.mjs'));
let calls=0;const fetch=async()=>{calls++;return new Response(fs.readFileSync(fixture),{headers:{'content-type':'text/event-stream'}})};
globalThis.fetch=fetch;configure({buildModelFetch:()=>fetch});
const schema={type:'object',properties:{text:{type:'string'}},required:['text']};
const request={version:guard.VERSION,name:guard.TOOL,schema,schemaSha256:guard.sha256(guard.canonical(schema))};
const model={id:'MiniMax-M3',provider:'minimax',api:'openai-completions',baseUrl:'https://offline.invalid/v1',reasoning:false,input:['text'],contextWindow:1000000,maxTokens:8192,cost:{input:0,output:0,cacheRead:0,cacheWrite:0}};
const bound=guard.bindAttempt(createOpenAICompletionsTransportStreamFn(),request,{runId:'offline-empty',sessionId:'offline-session',provider:'minimax',model:'MiniMax-M3'},dir);
const stream=bound(model,{messages:[{role:'user',content:'fixed offline input',timestamp:0}],tools:[{name:guard.TOOL,description:'fixture',parameters:schema}]},{apiKey:'offline-placeholder'});
for await(const event of stream){}const result=await stream.result();
const evidence=guard.candidateEvidence(result,request);
assert.equal(calls,1);assert.equal(result.stopReason,'toolUse');assert.equal(evidence.providerFinishReason,'tool_calls');
assert.equal(evidence.toolCallId,'fixture-id');
process.stdout.write(JSON.stringify({rawSha256:evidence.rawSha256,rawBytes:evidence.rawBytes}));
''')
    result = subprocess.run([shutil.which('node'), str(script), str(runtime), str(tmp_path / 'guard'), str(fixture)],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    native = json.loads(result.stdout)
    assert native['rawSha256'] == report['argument_streams'][0]['sha256']
    assert native['rawBytes'] == len(raw.encode())


def test_provider_argument_observation_preserves_identity_without_payload(tmp_path):
    """Real observer/receipt paths; network forbidden, only SSE bytes are fixtures."""
    helper = Path(__file__).resolve().parents[1] / 'scripts/openclaw_structured_result.mjs'
    script = tmp_path / 'observation.mjs'
    script.write_text(r'''
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import net from 'node:net';
import {pathToFileURL} from 'node:url';
net.Socket.prototype.connect=function(){throw Error('OFFLINE_NETWORK_BLOCKED')};
const g=await import(pathToFileURL(process.argv[2]));
const root=process.argv[3];
const raw='{"text":"中文🎬"}';
const event=(argumentsText, index=0, id='original', finish=null)=>'data: '+JSON.stringify({choices:[{
 index:0,delta:argumentsText===null?{}:{tool_calls:[{index,id,type:'function',
 function:{name:g.TOOL,arguments:argumentsText}}]},finish_reason:finish}]})+'\r\n\r\n';
const end=event(null,0,'original','tool_calls')+'data: [DONE]\r\n\r\n';
const split=raw.indexOf('🎬')+1;
const wire=event(raw.slice(0,split))+event(raw.slice(split))+end;
const obs=g.createArgumentObservation();
for(const b of Buffer.from(wire))obs.feed(Buffer.from([b]));
obs.finish('EOF');
const result=obs.result();
assert.equal(result.state,'COMPLETE');
assert.equal(result.streams[0].sha256,g.sha256(raw));
assert.equal(result.streams[0].bytes,Buffer.byteLength(raw));
assert.equal(result.streams[0].fragments,2);
assert.equal(JSON.stringify(result).includes('中文'),false);
for(const [bytes,finish] of [[event(raw),'ERROR'],[event(raw),'CANCEL'],
 [event(raw)+event('',0,'different')+end,'EOF'],[wire+event('changed'),'EOF'],
 [wire+'data: {"unfinished":','CANCEL'],[Buffer.concat([Buffer.from(wire),Buffer.from([0xe4,0xb8])]),'CANCEL'],
 [event('\ud800')+end,'EOF'],['data: not-json\n\n','EOF']]){
 const x=g.createArgumentObservation();x.feed(Buffer.from(bytes));x.finish(finish);
 assert.notEqual(x.result().state,'COMPLETE');assert.deepEqual(x.result().streams,[]);
}
const multi=g.createArgumentObservation();
multi.feed(Buffer.from(event(raw)+event('{}',1,'second')+end));multi.finish('EOF');
assert.equal(multi.result().state,'COMPLETE');
assert.deepEqual(multi.result().streams.map(s=>s.sha256),[g.sha256(raw),g.sha256('{}')]);
assert.notEqual(multi.result().streams[0].toolCallIdSha256,multi.result().streams[1].toolCallIdSha256);
const request={version:g.VERSION,name:g.TOOL,schema:{type:'object'},schemaSha256:g.sha256(g.canonical({type:'object'}))};
const originalResponse=new Response(wire);
const ActualResponse=globalThis.Response;
globalThis.Response=class {constructor(){throw Error('synthetic constructor failure')}};
assert.equal(g.observeProviderResponse(originalResponse,{request}),originalResponse);
globalThis.Response=ActualResponse;
assert.equal(originalResponse.body.locked,false);
assert.equal(await originalResponse.text(),wire,'Diagnostic failure consumed original bytes');
for(const mode of ['normal','terminal_before_eof','diagnostic_conflict','mismatch']){
 const directory=path.join(root,mode);fs.mkdirSync(directory,{mode:0o700});
 const scope={request,directory,identity:{runId:mode,sessionId:'session',provider:'minimax',model:'MiniMax-M3'}};
 const file=path.join(directory,'provider-arguments-'+g.sha256(g.canonical({runId:mode,sessionId:'session'}))+'.json');
 if(mode==='diagnostic_conflict')fs.writeFileSync(file,'keep-original',{mode:0o600});
 const response=g.observeProviderResponse(new Response(wire,{headers:{'content-type':'text/event-stream'}}),scope);
 const nativeRaw=mode==='mismatch'?'{}':raw;
 const message={role:'assistant',stopReason:'toolUse',easelProviderFinishReason:'tool_calls',
 content:[{type:'toolCall',id:'original',name:g.TOOL,arguments:JSON.parse(nativeRaw),easelRawArguments:nativeRaw}]};
 const delivered=[];
 const stream=g.protectedStream({push:e=>delivered.push(e),end:()=>{}},scope);
 if(mode==='terminal_before_eof')stream.push({type:'done',message});
 assert.equal(await response.text(),wire);
 if(mode!=='terminal_before_eof')stream.push({type:'done',message});
 assert.equal(delivered.at(-1).type,'done','Diagnostic changed native admission');
 if(mode==='diagnostic_conflict'){assert.equal(fs.readFileSync(file,'utf8'),'keep-original');continue;}
 const record=JSON.parse(fs.readFileSync(file,'utf8'));
 assert.equal(record.attribution,mode==='mismatch'?'MISMATCH':'MATCH');
 assert.equal(fs.statSync(file).mode&0o077,0);
 assert.equal(JSON.stringify(record).includes('中文'),false);
 const original=fs.readFileSync(file,'utf8');
 assert.equal(g.retainExecutionFailure(scope,message,new Error('private error body')),'SAVED');
 assert.equal(fs.readFileSync(file,'utf8'),original,'Later error overwrote diagnostic');
}
''')
    result = subprocess.run([shutil.which('node'), str(script), str(helper), str(tmp_path)],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr


def test_native_structured_storage_and_concurrent_submission_guard(tmp_path):
    node = shutil.which('node')
    assert node, 'Node is required for the installed-runtime integration boundary'
    helper = Path(__file__).resolve().parents[1] / 'scripts/openclaw_structured_result.mjs'
    script = tmp_path / 'guard-test.mjs'
    network_guard = tmp_path / 'no-network.mjs'
    network_guard.write_text("import net from 'node:net';\n"
        "net.Socket.prototype.connect=function(){throw Error('OFFLINE_NETWORK_BLOCKED')};\n")
    script.write_text('''
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {pathToFileURL} from 'node:url';
const guard = await import(pathToFileURL(process.argv[2]));
const {safeArguments, canonical, sha256, validatePayload, reserveSubmission} = guard;
const directory = process.argv[3];
const schema = {type:'object',properties:{text:{type:'string'}},required:['text'],additionalProperties:false};
const request = {version:guard.VERSION,name:guard.TOOL,schema,schemaSha256:sha256(canonical(schema))};
const payload = {tools:[{type:'function',function:{name:guard.TOOL,parameters:schema}}],
  tool_choice:{type:'function',function:{name:guard.TOOL}},parallel_tool_calls:false};
const identity = {runId:'original-run',sessionId:'original-session',provider:'offline',model:'fixture'};
for (const [title, expected] of [['SemanticProposal','semantic plan candidate'],
  ['PlanningVisualReview','independent review'],['PlanningLocalRepair','local repairs']]) {
  const stageSchema={...schema,title};
  const stageRequest={...request,schema:stageSchema,schemaSha256:sha256(canonical(stageSchema))};
  let actual;
  const bound=guard.bindAttempt(async (model,context,options)=>{
    actual=await options.onPayload({},model);
  },stageRequest,identity,directory);
  await bound({api:'openai-completions',provider:'offline',id:'fixture'},{});
  assert.ok(actual.tools[0].function.description.includes(expected));
  assert.deepEqual(actual.tools[0].function.parameters,stageSchema);
}

if (process.argv[4] === 'worker') {
  try { reserveSubmission(directory,identity,payload,request); process.exit(0); }
  catch (error) { assert.equal(error.message,'STRUCTURED_SUBMISSION_UNCERTAIN'); process.exit(10); }
}
const message = {role:'assistant',stopReason:'toolUse',easelProviderFinishReason:'tool_calls',
  content:[{type:'toolCall',name:guard.TOOL,id:'original-call',arguments:{},easelRawArguments:'{}'}]};
if (process.argv[4] === 'rejection-worker') {
  fs.mkdirSync(directory,{recursive:true,mode:0o700});
  const status=guard.retainRejection({directory,identity,request},
    {...message,easelProviderFinishReason:process.argv[5]},'STRUCTURED_TERMINAL_REJECTED');
  process.exit(status==='SAVED'?0:status==='RETAINED'?10:20);
}
const valid = ['{ "text" : "中文🖼️" }', String.raw`{"text":"\\u4e2d\\u6587"}`,
  '{"nested":[null,false,0,-1.5e2,{},[]]}', '{"__proto__":{"safe":"value"}}'];
for (const raw of valid) assert.equal(canonical(safeArguments(raw)),canonical(JSON.parse(raw)));
const invalid = ['{"x":1,"x":2}', String.raw`{"x":1,"\\u0078":2}`,
  '{"x":NaN}', '{"x":Infinity}', '{"x":1e999}', '{"x":01}', '{"x":1,}',
  '{"x":[1,]}', '{"x":', '[]', '{}{}', String.raw`{"x":"\\ud800"}`,
  JSON.stringify({api_key:'synthetic-value'}),
  '{"x":"'+'sk-'+'a'.repeat(16)+'"}',
  String.raw`{"x":"\\u0073\\u006b-`+'a'.repeat(16)+'"}'];
for (const raw of invalid) assert.throws(()=>safeArguments(raw),/^Error: STRUCTURED_STORAGE_REJECTED$/);
const large = JSON.stringify({text:'中'.repeat(400000)}) + ' ';
const exact = large + ' '.repeat(guard.MAX_ARGUMENT_BYTES-Buffer.byteLength(large));
assert.equal(safeArguments(exact).text.length,400000);
assert.throws(()=>safeArguments(exact+' '),/STRUCTURED_CAPACITY_REJECTED/);
validatePayload(payload,request);
for (const changed of [
  {...payload,parallel_tool_calls:true}, {...payload,tools:[]},
  {...payload,tools:[...payload.tools,...payload.tools]}, {...payload,tool_choice:'auto'},
  {...payload,tools:[{type:'function',function:{name:guard.TOOL,parameters:{type:'object'}}}]}]) {
  assert.throws(()=>reserveSubmission(directory,identity,changed,request),/STRUCTURED_PAYLOAD_CHANGED/);
}
assert.equal(fs.existsSync(directory),false); // Failed validation cannot spend a request.
const worker = ()=>new Promise((resolve,reject)=>{
  const child=spawn(process.execPath,[process.argv[1],process.argv[2],directory,'worker'],{stdio:'ignore'});
  child.on('error',reject); child.on('exit',code=>resolve(code));
});
assert.deepEqual((await Promise.all([worker(),worker()])).sort((a,b)=>a-b),[0,10]);
const files=fs.readdirSync(directory);
assert.equal(files.length,1);
const saved=fs.readFileSync(path.join(directory,files[0]),'utf8');
assert.equal(JSON.parse(saved).state,'RESERVED');
assert.throws(()=>reserveSubmission(directory,{...identity,model:'changed'},payload,request),
  /STRUCTURED_SUBMISSION_UNCERTAIN/); // Model/schema changes cannot refresh the original run.
assert.equal(fs.readFileSync(path.join(directory,files[0]),'utf8'),saved);
const blocked=path.join(directory,'not-a-directory'); fs.writeFileSync(blocked,'occupied');
assert.throws(()=>reserveSubmission(blocked,identity,payload,request),/STRUCTURED_SUBMISSION_UNCERTAIN/);
assert.equal(fs.readFileSync(blocked,'utf8'),'occupied');
const protocolDirectory=path.join(directory,'protocol');
guard.assertSessionProtocol(protocolDirectory,identity);
assert.equal(fs.existsSync(protocolDirectory),false);
guard.assertSessionProtocol(protocolDirectory,identity,request);
guard.assertSessionProtocol(protocolDirectory,identity,request);
assert.throws(()=>guard.assertSessionProtocol(protocolDirectory,identity),/STRUCTURED_RECOVERY_REQUIRED/);
assert.throws(()=>guard.assertSessionProtocol(protocolDirectory,{...identity,runId:'new-run'},request),
  /STRUCTURED_RECOVERY_REQUIRED/);
const binding=path.join(protocolDirectory,fs.readdirSync(protocolDirectory)[0]);
fs.writeFileSync(binding,'{'); // Interrupted first write cannot become a fresh session.
assert.throws(()=>guard.assertSessionProtocol(protocolDirectory,identity,request),/STRUCTURED_RECOVERY_REQUIRED/);
// First failure survives every later error, without storing model-controlled text.
const marker='Bearer '+'s'.repeat(32);
const cases=[
  ['missing_finish',(({easelProviderFinishReason,...rest})=>rest)(message),'missing','MISSING'],
  ['null_finish',{...message,easelProviderFinishReason:null},'null','NULL'],
  ['unknown_finish',{...message,easelProviderFinishReason:marker},'string','UNKNOWN'],
  ['stop',{...message,easelProviderFinishReason:'stop'},'string','stop'],
  ['length',{...message,easelProviderFinishReason:'length'},'string','length'],
  ['wrong_stop',{...message,stopReason:'stop'},'string','tool_calls'],
  ['no_call',{...message,content:[]},'string','tool_calls'],
  ['two_calls',{...message,content:[...message.content,...message.content]},'string','tool_calls'],
  ['wrong_tool',{...message,content:[{...message.content[0],name:marker}]},'string','tool_calls'],
  ['no_id',{...message,content:[{...message.content[0],id:''}]},'string','tool_calls'],
  ['sensitive_body',{...message,easelProviderFinishReason:marker,
    content:[{type:'text',text:marker},{...message.content[0],id:marker,
      easelRawArguments:JSON.stringify({api_key:marker})}]},'string','UNKNOWN'],
  ['raw_not_string',{...message,content:[{...message.content[0],easelRawArguments:{}}]},'string','tool_calls'],
  ['null_message',null,'missing','MISSING'],
];
for (const [name,candidate,finishShape,finishValue] of cases) {
  const folder=path.join(directory,name);fs.mkdirSync(folder,{mode:0o700});
  const scope={directory:folder,identity:{...identity,runId:name},request};
  const events=[];
  const stream=guard.protectedStream({push:e=>events.push(e),end(){}},scope);
  assert.throws(()=>stream.push({type:'done',message:candidate}),/^Error: STRUCTURED_/);
  assert.equal(events.length,0,'Rejected content reached subscribers');
  const file=path.join(folder,fs.readdirSync(folder)[0]);
  const first=fs.readFileSync(file,'utf8');
  assert.equal(first.includes(marker),false);
  const diagnostic=JSON.parse(first);
  assert.equal(diagnostic.providerFinishShape,finishShape);
  assert.equal(diagnostic.providerFinishValue,finishValue);
  assert.equal(diagnostic.runId,name);
  assert.equal(diagnostic.schemaSha256,request.schemaSha256);
  assert.equal(fs.statSync(file).mode&0o077,0);
  assert.equal(guard.retainRejection(scope,{...message,easelProviderFinishReason:'length'},
    'STRUCTURED_EXECUTION_FAILED'),'RETAINED');
  stream.push({type:'error',error:{errorMessage:'STRUCTURED_UNTRUSTED_CATEGORY'}});
  assert.equal(events[0].error.errorMessage,'STRUCTURED_EXECUTION_FAILED');
  assert.equal(fs.readFileSync(file,'utf8'),first);
  assert.equal(fs.readdirSync(folder).length,1);
}
// First SDK error is a rejection too; its original content/exception stays private.
for (const [name,source,expectedStop] of [
  ['first-sdk-error',{...message,errorMessage:marker},'error'],
  ['first-sdk-abort',{...message,errorMessage:marker,stopReason:'aborted'},'aborted'],
]) {
  const folder=path.join(directory,name);fs.mkdirSync(folder,{mode:0o700});
  const scopedIdentity={...identity,runId:name};
  const scope={directory:folder,identity:scopedIdentity,request};
  reserveSubmission(folder,scopedIdentity,payload,request);
  const reserved=fs.readdirSync(folder)[0];
  const reservation=fs.readFileSync(path.join(folder,reserved),'utf8');
  const events=[];let terminal;
  const stream=guard.protectedStream({push:e=>events.push(e),end:e=>{terminal=e}},scope);
  stream.push({type:'error',error:source});stream.end();
  assert.equal(events.length,1);
  assert.equal(events[0].error.errorMessage,'STRUCTURED_EXECUTION_FAILED');
  assert.equal(events[0].error.stopReason,expectedStop);
  assert.deepEqual(events[0].error.content,[]);
  assert.equal(terminal,events[0].error);
  const names=fs.readdirSync(folder).filter(n=>n.startsWith('rejection-'));
  assert.equal(names.length,1,'First SDK error diagnostic was lost');
  const file=path.join(folder,names[0]);const first=fs.readFileSync(file,'utf8');
  assert.equal(first.includes(marker),false);
  assert.equal(JSON.parse(first).runId,name);
  assert.equal(JSON.parse(first).schemaSha256,request.schemaSha256);
  assert.equal(fs.statSync(file).mode&0o077,0);
  assert.throws(()=>reserveSubmission(folder,scopedIdentity,payload,request),
    /STRUCTURED_SUBMISSION_UNCERTAIN/);
  assert.equal(fs.readFileSync(path.join(folder,reserved),'utf8'),reservation);
}
// These are diagnostic controls, not a replay of any historical Provider response.
for (const [name,error,category] of [
  ['sdk-malformed-call',Error('Provider returned an incomplete or malformed tool call'),'STRUCTURED_SDK_MALFORMED_TOOL_CALL'],
  ['sdk-finish',Error('Stream ended without finish_reason'),'STRUCTURED_SDK_FINISH_REASON_MISSING'],
  ['sdk-buffer',Error('Exceeded tool-call argument buffer limit'),'STRUCTURED_SDK_ARGUMENT_BUFFER_LIMIT'],
  ['sdk-syntax',new SyntaxError(marker),'STRUCTURED_SDK_SYNTAX_ERROR'],
  ['sdk-type',new TypeError(marker),'STRUCTURED_SDK_TYPE_ERROR'],
  ['sdk-range',new RangeError(marker),'STRUCTURED_SDK_RANGE_ERROR'],
  ['sdk-unknown',Error(marker),'STRUCTURED_EXECUTION_FAILED'],
]) {
  const folder=path.join(directory,name);fs.mkdirSync(folder,{mode:0o700});
  const scope={directory:folder,identity:{...identity,runId:name},request};
  assert.equal(guard.retainExecutionFailure(scope,message,error),'SAVED');
  const file=path.join(folder,fs.readdirSync(folder)[0]);const first=fs.readFileSync(file,'utf8');
  const record=JSON.parse(first);
  assert.equal(record.category,category);
  assert.equal(record.toolCallCount,1,'Pre-cleanup tool evidence was lost');
  assert.equal(first.includes(marker),false);
  guard.protectedStream({push(){},end(){}},scope).push({
    type:'error',error:{...message,content:[],errorMessage:marker}});
  assert.equal(fs.readFileSync(file,'utf8'),first,'Cleanup replaced the first diagnosis');
  assert.equal(guard.retainExecutionFailure({...scope,identity:{...scope.identity,model:'other'}},
    message,error),'UNAVAILABLE');
  assert.equal(fs.readFileSync(file,'utf8'),first);
}
const errorWriteFailure=path.join(directory,'error-write-failure');
fs.mkdirSync(errorWriteFailure,{mode:0o700});
const originalLink=fs.linkSync;const errorEvents=[];
try {
  fs.linkSync=()=>{throw Error('ENOSPC')};
  const scope={directory:errorWriteFailure,identity,request};
  assert.equal(guard.retainExecutionFailure(scope,message,new SyntaxError(marker)),'UNAVAILABLE');
  guard.protectedStream({push:e=>errorEvents.push(e),end(){}},scope).push({
    type:'error',error:{errorMessage:marker}});
  assert.equal(errorEvents[0].error.errorMessage,'STRUCTURED_EXECUTION_FAILED');
  assert.deepEqual(fs.readdirSync(errorWriteFailure),[]);
} finally {fs.linkSync=originalLink;}
const race=path.join(directory,'rejection-race');
const rejectWorker=finish=>new Promise((resolve,reject)=>{
  const child=spawn(process.execPath,[process.argv[1],process.argv[2],race,'rejection-worker',finish],{stdio:'ignore'});
  child.on('error',reject);child.on('exit',code=>resolve(code));
});
assert.deepEqual((await Promise.all([rejectWorker('stop'),rejectWorker('length')])).sort((a,b)=>a-b),[0,10]);
const rejection=path.join(race,fs.readdirSync(race)[0]);
const first=fs.readFileSync(rejection,'utf8');
assert.ok(['stop','length'].includes(JSON.parse(first).providerFinishValue));
assert.equal(guard.retainRejection({directory:race,identity,request},null,'STRUCTURED_TERMINAL_REJECTED'),'RETAINED');
assert.equal(fs.readFileSync(rejection,'utf8'),first);
fs.writeFileSync(rejection,'{');
assert.equal(guard.retainRejection({directory:race,identity,request},message,'STRUCTURED_TERMINAL_REJECTED'),'UNAVAILABLE');
assert.equal(fs.readFileSync(rejection,'utf8'),'{','A partial record was overwritten');
const unwritable=path.join(directory,'write-failure');fs.mkdirSync(unwritable,{mode:0o700});
const link=fs.linkSync;
try {
  fs.linkSync=()=>{throw Error('ENOSPC')};
  const stream=guard.protectedStream({push(){assert.fail('Rejected output leaked')},end(){}},
    {directory:unwritable,identity,request});
  assert.throws(()=>stream.push({type:'done',message:{...message,easelProviderFinishReason:'length'}}),
    /^Error: STRUCTURED_TERMINAL_REJECTED$/);
  assert.deepEqual(fs.readdirSync(unwritable),[]);
} finally {fs.linkSync=link;}
const unsafe=path.join(directory,'unsafe-link');fs.symlinkSync(race,unsafe);
assert.equal(guard.retainRejection({directory:unsafe,identity,request},message,'STRUCTURED_TERMINAL_REJECTED'),'UNAVAILABLE');
assert.equal(fs.readFileSync(rejection,'utf8'),'{');
assert.equal(fs.readFileSync(path.join(directory,files[0]),'utf8'),saved,'Diagnostics changed RESERVED');
const legalEvents=[];
guard.protectedStream({push:e=>legalEvents.push(e),end(){}},
  {directory:unwritable,identity,request}).push({type:'done',message});
assert.equal(legalEvents.at(-1).type,'done');
assert.deepEqual(fs.readdirSync(unwritable),[],'Legal result created a rejection');
// Fixed subreasons distinguish parser rejection from unsafe additional text.
const storageCases = [
  ['syntax','{"x":}', 'JSON_SYNTAX'],
  ['duplicate','{"x":1,"x":2}', 'DUPLICATE_KEY'],
  ['pattern',JSON.stringify({x:marker}), 'SECRET_PATTERN'],
  ['key',JSON.stringify({password:'synthetic-value'}), 'SECRET_KEY'],
  ['unicode',JSON.stringify({x:String.fromCharCode(0xd800)}), 'INVALID_UNICODE'],
  ['depth','{"x":'+'['.repeat(66)+'0'+']'.repeat(66)+'}', 'DEPTH_LIMIT'],
  ['nonfinite','{"x":1e999}', 'NONFINITE_NUMBER'],
  ['root','[]', 'ROOT_NOT_OBJECT'],
  ['trailing','{}{}', 'TRAILING_CONTENT'],
  ['message','{}', 'SECRET_PATTERN'],
];
for (const [name,raw,reason] of storageCases) {
  const folder=path.join(directory,'storage-'+name);fs.mkdirSync(folder,{mode:0o700});
  const scope={directory:folder,identity:{...identity,runId:'storage-'+name},request};
  const candidate={...message,content:[{...message.content[0],easelRawArguments:raw},
    ...name==='message'?[{type:'text',text:marker}]:[]]};
  const events=[];
  assert.throws(()=>guard.protectedStream({push:e=>events.push(e),end(){}},scope)
    .push({type:'done',message:candidate}),/^Error: STRUCTURED_STORAGE_REJECTED$/);
  assert.equal(events.length,0);
  const file=path.join(folder,fs.readdirSync(folder)[0]);const first=fs.readFileSync(file,'utf8');
  const record=JSON.parse(first);
  assert.equal(record.version,'easel-structured-rejection@2');
  assert.equal(record.storageReason,reason);
  assert.equal(record.storageStage,name==='message'?'MESSAGE_STORAGE':'RAW_ARGUMENTS');
  assert.equal(first.includes(marker),false);
  assert.equal(first.includes('synthetic-value'),false);
  // Old @1 diagnostics remain byte-identical; no retroactive subreason.
  if (name==='duplicate') {
    const {storageReason,storageStage,...legacy}=record;
    legacy.version='easel-structured-rejection@1';
    const old=JSON.stringify(legacy);fs.writeFileSync(file,old);
    assert.equal(guard.retainRejection(scope,candidate,'STRUCTURED_STORAGE_REJECTED'),'RETAINED');
    assert.equal(fs.readFileSync(file,'utf8'),old);
  } else {
    assert.equal(guard.retainRejection(scope,candidate,'STRUCTURED_STORAGE_REJECTED'),'RETAINED');
    assert.equal(fs.readFileSync(file,'utf8'),first);
  }
}
const spoof=path.join(directory,'untrusted-reason');fs.mkdirSync(spoof,{mode:0o700});
const spoofError=Object.assign(Error('STRUCTURED_STORAGE_REJECTED'),
  {storageReason:marker,storageStage:marker,reason:marker});
assert.equal(guard.retainRejection({directory:spoof,identity,request},message,
  'STRUCTURED_STORAGE_REJECTED',spoofError),'SAVED');
const spoofRecord=fs.readFileSync(path.join(spoof,fs.readdirSync(spoof)[0]),'utf8');
assert.equal(spoofRecord.includes(marker),false);
assert.equal(JSON.parse(spoofRecord).storageReason,'UNKNOWN');
assert.equal(JSON.parse(spoofRecord).storageStage,'UNKNOWN');
process.stdout.write(JSON.stringify({storage:'PASS',capacity:'PASS',payload:'PASS',concurrency:'PASS',
  rejection_diagnostics:'PASS',durable_reservations:1,network_calls:0}));
''')
    result = subprocess.run([node, str(script), str(helper), str(tmp_path / 'ledger')],
                            capture_output=True, text=True, timeout=30,
                            env={'PATH': str(Path(node).parent) + ':/usr/bin:/bin',
                                 'NODE_OPTIONS': '--import=' + str(network_guard)})
    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)
    assert evidence['durable_reservations'] == 1 and evidence['network_calls'] == 0


def test_real_convergence_tool_terminal_does_not_admit_invalid_business_contract():
    """A successful tool transport is not a valid or safely repairable plan.

    Preserve the actual rejected bytes; independently authored legal controls
    exercise the same frozen schema through the archived public XML parser.
    This does not claim equivalence with the online Provider implementation.
    """
    import hashlib
    import pytest
    from easel.integrations import planning_wire as wire, planning_semantic_review as review
    from easel.integrations.planning_result_contract import SemanticProposal, MAX_B_ANSWERS
    from tests.test_semantic_planning import xml_reference_transport
    folder = Path(__file__).parent / 'fixtures/planning-vnext-development-2026-10-08'
    raw = (folder / 'autonomous-convergence-A-wire.json').read_bytes()
    context = json.loads((folder / 'autonomous-convergence-A-contract.json').read_text())
    assert hashlib.sha256(raw).hexdigest() == context['original_sha256']
    assert context['historical_result'] == 'FAIL' and context['provider_finish'] == 'tool_calls'
    codec = wire.project(context['canonical_schema'], 'A', atomic_framing=True)
    assert codec.schema == context['wire_schema']
    value = json.loads(raw)
    errors = codec.errors(value)
    assert sum(e['path'][-1] == 'modality' for e in errors) == 6
    assert sum(e['path'][-1] == 'meaning' for e in errors) == 82
    with pytest.raises(ValueError): codec.decode_valid(value)
    targets = review.structural_targets(codec.decode_candidate(value))
    assert len(targets) > MAX_B_ANSWERS
    with pytest.raises(ValueError, match='capacity'): review.patch_schema(targets, slots=True)
    for modality, meaning, music in [('image', 'observable', True),
                                    ('video', 'dynamic_action', False), ('image', 'observable', False)]:
        candidate = {'needs': [{'scope': 'event-1', 'role': '视觉场景', 'modality': modality,
            'necessity': 'required', 'conditions': [{'text': '钥匙位于日常玄关。',
                'strength': 'required', 'responsibility': 'material', 'meaning': meaning}],
            'source_seconds': 2 if modality == 'video' else None}]}
        if music:
            candidate['needs'].append({'scope': 'global', 'role': '背景音乐', 'modality': 'bgm',
                'necessity': 'required', 'conditions': [{'text': '轻柔的无歌词器乐。',
                    'strength': 'required', 'responsibility': 'material'}],
                'sound': {'mood': '安静', 'vocals_allowed': False}})
        canonical = SemanticProposal.model_validate(candidate).model_dump(mode='json')
        encoded = codec.encode(canonical)
        assert not codec.errors(encoded)
        restored = json.loads(xml_reference_transport(json.dumps(encoded, ensure_ascii=False),
                                                     {'schema': codec.schema}))
        assert not codec.errors(restored)
        assert SemanticProposal.model_validate(codec.decode_valid(restored)).model_dump(mode='json') == canonical
    assert (folder / 'autonomous-convergence-A-wire.json').read_bytes() == raw
    # Real adaptive/131072 result: complete tool transport, but Need fields
    # escaped to the root and only one visual Need survived. Never salvage it
    # by dropping extra keys or silently moving an ambiguous root item.
    raw = (folder / 'autonomous-qualification-A-wire.json').read_bytes()
    context = json.loads((folder / 'autonomous-qualification-A-contract.json').read_text())
    assert hashlib.sha256(raw).hexdigest() == context['original_sha256']
    assert context['native_status'] == 'ok' and context['runtime_release'] == 'released'
    codec = wire.project(context['canonical_schema'], 'A', atomic_framing=True)
    assert codec.schema == context['wire_schema']
    value = json.loads(raw)
    assert codec.errors(value) == context['wire_errors']
    assert len(value['needs']) == 1 and value['item']['modality'] == 'bgm'
    with pytest.raises(ValueError): codec.decode_valid(value)
    with pytest.raises(ValueError, match='cannot be localized'):
        review.structural_targets(codec.decode_candidate(value))
    # A separately authored mixed plan survives the exact same reference
    # parser/schema; this is not a repair of the rejected production evidence.
    canonical = SemanticProposal.model_validate({'needs': [
        {'scope': 'scene-1', 'role': '视觉', 'modality': 'image', 'necessity': 'required',
         'conditions': [{'text': '玄关钥匙照片', 'strength': 'required', 'responsibility': 'material'}]},
        {'scope': 'global', 'role': '配乐', 'modality': 'bgm', 'necessity': 'required',
         'conditions': [{'text': '轻柔无歌词音乐', 'strength': 'required', 'responsibility': 'material'}],
         'sound': {'vocals_allowed': False}},
    ]}).model_dump(mode='json')
    encoded = codec.encode(canonical)
    restored = json.loads(xml_reference_transport(json.dumps(encoded, ensure_ascii=False), {'schema': codec.schema}))
    assert SemanticProposal.model_validate(codec.decode_valid(restored)).model_dump(mode='json') == canonical
    assert (folder / 'autonomous-qualification-A-wire.json').read_bytes() == raw
    # The independently authorized M2.7 batch completed transport as well.
    # Duplicate program-owned narration, invalid queries and SFX-in-BGM are
    # business failures; selecting another model cannot weaken admission.
    raw = (folder / 'autonomous-m27-qualification-A-wire.json').read_bytes()
    context = json.loads((folder / 'autonomous-m27-qualification-A-contract.json').read_text())
    assert hashlib.sha256(raw).hexdigest() == context['original_sha256']
    codec = wire.project(context['canonical_schema'], 'A', atomic_framing=True)
    assert codec.schema == context['wire_schema']
    value = json.loads(raw)
    assert codec.errors(value) == context['wire_errors']
    assert sum(n['modality'] == 'voice' for n in value['needs']) == 6
    assert len(value['needs']) == 15
    with pytest.raises(ValueError): codec.decode_valid(value)
    with pytest.raises(ValueError, match='cannot be localized'):
        review.structural_targets(codec.decode_candidate(value))
    assert (folder / 'autonomous-m27-qualification-A-wire.json').read_bytes() == raw


def test_producer_union_experiment_preserves_contract_and_repair(tmp_path):
    """A finite offline experiment, never a production or model-reliability PASS."""
    from copy import deepcopy
    from itertools import product
    import hashlib
    import pytest
    from jsonschema import Draft202012Validator, ValidationError
    from easel.integrations import planning_semantic_review as review
    from easel.integrations.planning_result_contract import semantic_tool_schema, SemanticProposal
    from easel.integrations.planning_wire import FrameProjection
    from tests.planning_material_matrix.producer_experiment import ProducerUnionExperiment, StagedProducerExperiment
    from tests.test_semantic_planning import xml_reference_transport

    catalog = {'global': {'global': {}}, 'event': {'event-1': {}}, 'scene': {'scene-1': {}},
               'voice': {'confirmed.voice_profile': {}}, 'continuity': {}}
    rows, schemas = [], []
    def roundtrip(codec, value, label):
        normalized = SemanticProposal.model_validate(value).model_dump(mode='json')
        before = deepcopy(value)
        encoded = codec.encode(value)
        assert codec.decode(encoded) == normalized
        transported = json.loads(xml_reference_transport(json.dumps(encoded, ensure_ascii=False), {'schema': codec.schema}))
        assert codec.decode(transported) == normalized, label
        staged = StagedProducerExperiment(codec.canonical)
        selection, details, receipt = staged.encode(value)
        selection = json.loads(xml_reference_transport(json.dumps(selection, ensure_ascii=False), {'schema': staged.selection_schema}))
        details = json.loads(xml_reference_transport(json.dumps(details, ensure_ascii=False),
                            {'schema': staged.details_contract(selection)['schema']}))
        assert staged.assemble(selection, details, receipt) == normalized, label
        assert before == value, 'Experiment mutated its original input'
        rows.append({'case': label, 'expected': 'canonical equality after public parser', 'actual': 'equal', 'result': 'PASS'})
        return encoded

    for derived in (False, True):
        directory = {**catalog, **({'derived_voice': {'fixture': True}} if derived else {})}
        canonical = semantic_tool_schema(directory, compiled=True)
        codec = ProducerUnionExperiment(canonical)
        compact = lambda value: json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()
        old = FrameProjection(canonical, 'A')
        schemas.append({'derived_voice': derived, 'old_wire_bytes': len(compact(old.schema)),
                        'union_wire_bytes': len(compact(codec.schema)),
                        'union_sha256': hashlib.sha256(compact(codec.schema)).hexdigest()})
        samples = []
        modalities = ('image', 'video', 'bgm', 'sfx', *(() if derived else ('voice',)))
        for modality in modalities:
            for strength, responsibility, meaning in product(('required', 'preference'),
                    ('material', 'postproduction', 'narrative'), ('observable', 'dynamic_action')):
                if modality != 'video' and (strength, responsibility, meaning) == ('required', 'material', 'dynamic_action'):
                    continue  # This combination is NOT in the original legal set.
                need = {'scope': 'event-1', 'role': '素材角色', 'modality': modality, 'necessity': 'required',
                    'conditions': [{'text': '冻结必要素材内容', 'strength': 'required', 'responsibility': 'material'},
                        {'text': '保留原文、标点“🖼️”及顺序，不猜测。', 'strength': strength,
                         'responsibility': responsibility, 'meaning': meaning}]}
                if modality in {'video', 'bgm', 'sfx'}:
                    need['source_seconds'] = 3.5
                if modality == 'voice':
                    need.update(voice_choice='confirmed.voice_profile', voice_expression='平静')
                if modality == 'bgm':
                    need['sound'] = {'mood': '安静', 'vocals_allowed': False, 'tempo_bpm': [80, 100], 'instruments': ['piano']}
                if modality == 'sfx':
                    need['sound'] = {'event_description': '钥匙轻放桌面', 'intensity': '轻', 'environment': '室内'}
                if modality in {'image', 'video'}:
                    need.update(frame='native', native_ratio='4:5', queries=['quiet room', 'keys on desk', 'empty room'])
                roundtrip(codec, {'needs': [need]}, f'{derived}/{modality}/{strength}/{responsibility}/{meaning}')
                if (strength, responsibility, meaning) == ('required', 'material', 'observable'):
                    samples.append(deepcopy(need))
        # The meaningful new risks: mixed union branch selection and repeated
        # ordered entries, not another set of isolated scalar unit assertions.
        samples.append(deepcopy(samples[0]))
        samples[0]['conditions'].append(deepcopy(samples[0]['conditions'][0]))
        roundtrip(codec, {'needs': samples}, f'{derived}/mixed-ordered-duplicates')
        minimal = {'needs': [{'scope': 'event-1', 'role': 'null', 'modality': 'image', 'necessity': 'required',
            'conditions': [{'text': 'Null', 'strength': 'required', 'responsibility': 'material'}]}]}
        for null_case in ('missing', 'null', 'string-null'):
            value = deepcopy(minimal)
            if null_case != 'missing': value['needs'][0]['purpose'] = None if null_case == 'null' else 'null'
            roundtrip(codec, value, f'{derived}/defaults/{null_case}')
        # A known field error still reaches the existing local leaf repair.
        encoded = codec.encode(minimal)
        encoded['needs'][0]['conditions'][0]['meaning'] = 'allowed'
        with pytest.raises(ValueError): codec.decode(encoded)
        diagnostic = codec.decode_candidate(encoded)
        targets = review.structural_targets(diagnostic)
        assert len(targets) == 1 and targets[0]['path'] == ['needs', 0, 'conditions', 0, 'meaning']
        repaired = review.apply_patches(diagnostic, {'patches': [{'target': 0, 'value': 'observable'}]}, targets)
        assert codec.decode(codec.encode(repaired)) == SemanticProposal.model_validate(minimal).model_dump(mode='json')
        assert encoded['needs'][0]['conditions'][0]['meaning'] == 'allowed'
        rows.append({'case': f'{derived}/original-local-repair-leaf', 'expected': 'same target, immutable original',
                     'actual': 'same target, immutable original', 'result': 'PASS'})
        # Canonical faults cannot be erased when specializing a branch.
        for bad_case in ('unknown_scope', 'image_duration', 'voice_field', 'required_action', 'unknown_modality',
                         'non_ascii_query', 'missing_required_source', 'extra_property'):
            value = deepcopy(minimal); need = value['needs'][0]
            if bad_case == 'unknown_scope': need['scope'] = 'unknown'
            elif bad_case == 'image_duration': need['source_seconds'] = 5
            elif bad_case == 'voice_field': need['voice_choice'] = 'confirmed.voice_profile'
            elif bad_case == 'required_action': need['conditions'][0]['meaning'] = 'dynamic_action'
            elif bad_case == 'unknown_modality': need['modality'] = 'audio'
            elif bad_case == 'non_ascii_query': need['queries'] = ['中文', 'keys on desk', 'empty room']
            elif bad_case == 'missing_required_source': need['conditions'][0]['strength'] = 'preference'
            elif bad_case == 'extra_property': need['unknown'] = None
            before = deepcopy(value)
            with pytest.raises((ValueError, ValidationError)): codec.encode(value)
            assert value == before
            rows.append({'case': f'{derived}/reject/{bad_case}', 'expected': 'reject without mutation',
                         'actual': 'rejected, unchanged', 'result': 'PASS'})
        # Poison the producer directly; codec admission must reject before
        # otherwise valid canonical defaults can conceal an extra field.
        for modality, forbidden, bad in [('image', 'source_seconds', 3), ('bgm', 'sound_character', '轻响'),
                                          ('sfx', 'mood', '愉悦')]:
            need = deepcopy(next(n for n in samples if n['modality'] == modality))
            value = codec.encode({'needs': [need]})
            node = value['needs'][0]['sound'] if modality in {'bgm', 'sfx'} else value['needs'][0]
            node[forbidden] = bad
            with pytest.raises(ValueError): codec.decode(value)
            with pytest.raises((ValueError, ValidationError)): codec.encode(codec.decode_candidate(value))
            rows.append({'case': f'{derived}/wire-poison/{modality}', 'expected': 'reject cross-modal poison',
                         'actual': 'rejected', 'result': 'PASS'})
        if derived:
            value = {'needs': [{'scope': 'event-1', 'role': '旁白', 'modality': 'voice', 'necessity': 'required',
                'voice_choice': 'confirmed.voice_profile', 'conditions': [{'text': '旁白', 'strength': 'required',
                                                                         'responsibility': 'material'}]}]}
            with pytest.raises(ValidationError): codec.encode(value)
            assert all(b['properties']['modality']['const'] != 'voice'
                       for b in codec.schema['properties']['needs']['items']['anyOf'])
            rows.append({'case': 'derived_voice/reject-duplicate', 'expected': 'no Voice branch',
                         'actual': 'rejected', 'result': 'PASS'})
    # Preserve the complete historical failure, including all illegal meanings.
    folder = Path(__file__).parent / 'fixtures/planning-vnext-development-2026-10-08'
    original = (folder / 'autonomous-convergence-A-wire.json').read_bytes()
    contract = json.loads((folder / 'autonomous-convergence-A-contract.json').read_text())
    codec = ProducerUnionExperiment(contract['canonical_schema'])
    with pytest.raises(ValueError): codec.decode(json.loads(original))
    assert hashlib.sha256(original).hexdigest() == contract['original_sha256']
    rows.append({'case': 'historical-real-A', 'expected': 'FAIL remains FAIL', 'actual': 'rejected', 'result': 'PASS'})
    report = {'kind': 'offline-producer-union-experiment', 'production_enabled': False,
              'actual_http': 0, 'model_reliability': 'NOT_TESTED', 'semantic_kind': 'NOT_SELECTED',
              'canonical_changed': False, 'repair_contract_changed': False,
              'schemas': schemas, 'cases': rows, 'pass': len(rows), 'fail': 0}
    (tmp_path / 'producer-union-experiment.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))


def test_equivalent_schema_experiment_preserves_assertions_and_refuses_unsafe_patterns():
    from copy import deepcopy
    from jsonschema import Draft202012Validator as Validator
    from tests.planning_material_matrix.producer_experiment import equivalent_schema_experiment
    source = {'type': 'object', 'additionalProperties': False, 'properties': {
        'text': {'anyOf': [{'type': 'string', 'minLength': 1, 'maxLength': 4, 'pattern': '^n'},
                           {'type': 'null'}], 'default': {'anyOf': [{'type': 'null'}]}},
        'number': {'anyOf': [{'type': 'number', 'exclusiveMinimum': 0, 'maximum': 2}, {'type': 'null'}]},
        'integer': {'anyOf': [{'type': 'null'}, {'type': 'integer', 'multipleOf': 2}]},
        'flag': {'anyOf': [{'type': 'boolean'}, {'type': 'null'}]},
        'queries': {'type': 'array', 'items': {'type': 'string'}, 'maxItems': 3,
                    'allOf': [{'maxItems': 3}]}}, 'required': ['text', 'queries']}
    before = deepcopy(source)
    candidate, changes = equivalent_schema_experiment(source)
    assert source == before and len(changes) == 5
    assert candidate['properties']['text']['default'] == source['properties']['text']['default']
    assert list(candidate['properties']) == list(source['properties'])
    a, b = Validator(source), Validator(candidate)
    base = {'text': None, 'queries': []}
    probes = [None, '', 'null', 'n', 'noooo', 0, -1, 1, 1.5, 2, 3, True, False, {}, [], ['a'] * 3, ['a'] * 4]
    for field in source['properties']:
        for value in probes:
            data = {**base, field: value}
            assert a.is_valid(data) == b.is_valid(data), (field, value)
        missing = {k: v for k, v in base.items() if k != field}
        assert a.is_valid(missing) == b.is_valid(missing)
    nullable = {'anyOf': [{'type': 'string', 'minLength': 1}, {'type': 'null'}]}
    unsafe = [
        {'anyOf': [{'type': 'string', 'enum': ['a']}, {'type': 'null'}]},
        {'anyOf': [{'type': 'string', 'const': 'a'}, {'type': 'null'}]},
        {'anyOf': [{'type': 'string', 'description': 'branch annotation'}, {'type': 'null'}]},
        {'anyOf': [{'type': 'array', 'items': {'type': 'string'}}, {'type': 'null'}]},
        {**nullable, 'type': 'string'}, {**nullable, 'enum': ['a', None]},
        {'anyOf': [{'type': 'string'}, {'type': 'null'}, {'type': 'number'}]},
        {'type': 'array', 'maxItems': 3, 'allOf': [{'maxItems': 2}]},
        {'oneOf': [nullable, {'type': 'number'}]}, {'not': nullable}, {'contains': nullable},
    ]
    for schema in unsafe:
        assert equivalent_schema_experiment(schema) == (schema, [])
    assert equivalent_schema_experiment(candidate) == (candidate, [])


def test_equivalent_details_schema_preserves_real_capture_rejection_and_codec():
    from copy import deepcopy
    from jsonschema import Draft202012Validator as Validator
    from easel.integrations import semantic_boundary_run as boundary, planning_input_view as views
    from easel.integrations import planning_staged_proposal as staged, planning_wire as wire
    from easel.integrations.planning_result_contract import maximum_compact_bytes
    from tests.planning_material_matrix.producer_experiment import equivalent_schema_experiment
    fixture = Path(__file__).parent / 'fixtures/planning-intake14-provider-shape-rejection.json'
    original = fixture.read_bytes()
    state = json.loads(original)['snapshot']
    scope = state['scope']
    view = views.PlanningInputView(scope['inputs'], scope['catalog'])
    selection = view.codec.decode(boundary.require_selection_admission(state['admissions']['A-selection'],
        scope=scope), view.codec.identity, diagnostic=True)
    codec = staged._read_only_staged(boundary.query_schema(scope))
    contract = codec.details_contract(selection, diagnostic=True)
    projection = wire.project(contract['schema'], 'A-details', atomic_framing=True)
    source = deepcopy(projection.schema)
    candidate, changes = equivalent_schema_experiment(source)
    assert changes and projection.schema == source
    assert maximum_compact_bytes(candidate) == maximum_compact_bytes(source)
    raw = json.loads(state['calls']['A-details']['reply'])
    assert not Validator(source).is_valid(raw) and not Validator(candidate).is_valid(raw)
    assert projection.errors(raw) == state['wire_diagnostics']['A-details']['wire_errors']
    assert fixture.read_bytes() == original


def test_source_scope_experiment_matches_exact_modality_catalog_and_keeps_original():
    from copy import deepcopy
    from jsonschema import Draft202012Validator as V, ValidationError
    from easel.integrations.planning_input_view import SourceSelection
    from easel.integrations.planning_result_contract import semantic_tool_schema
    from tests.planning_material_matrix.producer_experiment import source_scope_selection_experiment
    for events, continuity in (({'event-1': 'same frozen literal'}, {}),
                               ({}, {'paper': {'kind': 'object'}})):
        catalog = {'global': {'global': {}}, 'scene': {'scene-1': 'same frozen literal'},
                   'segment': {'segment-1': 'same frozen literal'},
                   'event': events, 'continuity': continuity,
                   'voice': {'creator_context.voice': {}}, 'derived_voice': {'owned': {}}}
        codec = SourceSelection(semantic_tool_schema(catalog, compiled=True), catalog)
        original = deepcopy(codec.schema)
        tightened, identity = source_scope_selection_experiment(codec)
        assert codec.schema == original and identity['base_codec_identity'] == codec.identity
        prior = deepcopy(original)
        clauses = []
        for modality in original['properties']['needs']['items']['properties']['modality']['enum']:
            scope_rule = codec.staged.branches[modality]['properties']['scope']
            allowed = False if scope_rule is False else {'type': 'string',
                'enum': [codec.to_wire[name] for name in scope_rule['enum']]}
            clauses.append({'if': {'properties': {'modality': {'const': modality}}, 'required': ['modality']},
                            'then': {'properties': {'scope': allowed}}})
        prior['properties']['needs']['items'].setdefault('allOf', []).extend(clauses)
        def equivalent(candidate):
            assert V(tightened).is_valid(candidate) == V(prior).is_valid(candidate)
        for modality, branch in codec.staged.branches.items():
            for source, handle in codec.to_wire.items():
                candidate = {'needs': [{'scope': handle, 'modality': modality,
                    'role': 'frozen intent', 'necessity': 'required'}], 'unresolved': []}
                if continuity:
                    candidate['needs'][0]['continuity_choices'] = ['paper']
                expected = V(branch['properties']['scope']).is_valid(source)
                assert V(tightened).is_valid(candidate) == expected, (modality, source)
                equivalent(candidate)
                for key in candidate['needs'][0]:
                    missing = deepcopy(candidate)
                    del missing['needs'][0][key]
                    equivalent(missing)
                for fault in ({'modality': 'unknown'}, {'modality': None}, {'scope': 'unknown'},
                              {'scope': []}, {'extra': True}, {'role': ''}, {'necessity': False}):
                    changed = deepcopy(candidate)
                    changed['needs'][0].update(fault)
                    equivalent(changed)
                if continuity:
                    candidate['needs'][0]['continuity_choices'] = ['invented']
                    assert not V(tightened).is_valid(candidate)
                    equivalent(candidate)
        for candidate in (None, [], {}, {'needs': {}, 'unresolved': []},
                          {'needs': [None], 'unresolved': []}, {'needs': [], 'unresolved': []}):
            equivalent(candidate)
        invalid = {'needs': [{'scope': 'unknown-handle', 'modality': 'image',
                             'role': 'frozen intent', 'necessity': 'required'}], 'unresolved': []}
        assert not V(tightened).is_valid(invalid)
        scene = codec.to_wire['scene-1']
        wrong = {'needs': [{'scope': scene, 'modality': 'sfx',
                           'role': 'sound intent', 'necessity': 'required'}], 'unresolved': []}
        assert not V(tightened).is_valid(wrong)
        if events:
            assert V(tightened).is_valid({**wrong, 'needs': [{**wrong['needs'][0], 'scope': codec.to_wire['event-1']}]})
        else:
            assert any(c['properties']['scope'] is False
                       for c in tightened['properties']['needs']['items']['anyOf'])
        voice = {**wrong, 'needs': [{**wrong['needs'][0], 'modality': 'voice'}]}
        assert not V(tightened).is_valid(voice)
    fixture = Path(__file__).parent / 'fixtures/planning-intake14-provider-shape-rejection.json'
    if fixture.is_file():
        from easel.integrations import semantic_boundary_run as boundary
        from easel.integrations.planning_input_view import PlanningInputView
        original = fixture.read_bytes()
        state = json.loads(original)['snapshot']
        view = PlanningInputView(state['scope']['inputs'], state['scope']['catalog'])
        schema, _ = source_scope_selection_experiment(view.codec)
        schema = boundary.intake_selection(state['scope'], schema)
        # Historical receipts stay untouched; test fresh current eligibility.
        accepted = deepcopy(state['admissions']['A-selection']['candidate'])
        scope = deepcopy(state['scope'])
        scope['transport'] = boundary.transport_identity(scope['catalog'], intake_inputs=scope['inputs'])
        scope['input_view'] = view.identity
        errors = list(V(schema).iter_errors(accepted))
        assert [(list(e.absolute_path), e.validator) for e in errors] == [
            (['needs', i], 'anyOf') for i in (8, 9, 10)]
        legal = deepcopy(accepted)
        for i in (8, 9, 10):
            # Synthetic positive fixture only; never written to the original
            # journal and never passed off as a model's repaired decision.
            legal['needs'][i]['scope'] = view.codec.to_wire[next(iter(state['scope']['catalog']['event']))]
        V(schema).validate(legal)
        decoded = view.codec.decode(legal, view.codec.identity)
        view.codec.staged.details_contract(decoded)
        from easel import output_admission as admission
        echoed = {**legal, 'contains': {'modality': 'bgm', 'necessity': 'required'}}
        def admit(value):
            return admission.admit_json(json.dumps(value, ensure_ascii=False), schema,
                stage='A-selection', channel='tool', profile=admission.SELECTION_PROFILE,
                binding={'kind': 'synthetic-source-scope-regression'})
        normalized = admit(echoed)
        assert normalized['receipt']['decision']['outcome'] == 'NORMALIZE'
        assert [(a['rule'], a['path']) for a in normalized['receipt']['actions']] == [
            ('selection-root-bgm-contains-echo@1', ['contains'])]
        assert normalized['candidate'] == legal
        broken = deepcopy(echoed)
        broken['needs'][8]['scope'] = next(h for h, ref in view.codec.references.items() if ref['kind'] == 'scene')
        no_music = {**echoed, 'needs': [r for r in legal['needs'] if r['modality'] != 'bgm']}
        wrong_echo = {**echoed, 'contains': {'modality': 'bgm', 'necessity': 'optional'}}
        for value in (broken, no_music, wrong_echo):
            rejected = admit(value)
            assert rejected['receipt']['decision']['outcome'] == 'REJECT'
            assert not rejected['receipt']['actions']
        no_bgm = {**legal, 'needs': [r for r in legal['needs'] if r['modality'] != 'bgm']}
        assert not V(schema).is_valid(no_bgm)
        unknown = deepcopy(legal)
        unknown['needs'][0]['scope'] = 'unknown'
        assert not V(schema).is_valid(unknown)
        voice = deepcopy(legal)
        voice['needs'][0]['modality'] = 'voice'
        assert not V(schema).is_valid(voice)
        # Current guidance and producer derive the same exact scope sets.
        base = boundary.view_a_message(scope, view, 'A-selection')
        assert 'scope选择工具enum中的实际使用范围' not in base
        assert '局部素材可选对应场景引用' not in base
        contract = json.loads(base.rsplit('\n', 1)[1])['scope_reference_contract']
        assert contract['allowed_scope']['sfx']['kinds'] == ['event']
        assert contract['policy'] == 'planning-source-selection@2'
        for modality, handles in view.codec.allowed_scopes.items():
            assert contract['allowed_scope'][modality]['handles'] == handles
        malformed = [{**legal, 'needs': rows} for rows in ([None], [1], ['x'], {'bad': {}})]
        for value in (accepted, broken, unknown, voice, *malformed):
            result = admit(value)
            result['owner_eligibility'] = boundary.selection_eligibility(scope, result)
            assert result['owner_eligibility']['decision']['outcome'] == 'REJECT'
            with pytest.raises(ValueError): boundary.require_selection_admission(result, scope=scope)
        # Other previously repairable leaves remain eligible; no scope repair.
        for value in (no_bgm, {**legal, 'needs': [{**legal['needs'][0], 'role': ''}, *legal['needs'][1:]]}):
            result = admit(value)
            result['owner_eligibility'] = boundary.selection_eligibility(scope, result)
            assert result['owner_eligibility']['decision']['outcome'] == 'BOUNDED_REPAIR'
        assert fixture.read_bytes() == original


def test_diagnostic_cell_binding_is_rebuilt_before_network(monkeypatch):
    from copy import deepcopy
    import hashlib, socket
    from easel.integrations import semantic_boundary_run as boundary, planning_input_view as views
    from easel.integrations.planning_authority import digest
    from tests.planning_material_matrix.producer_experiment import (SourceKindInputViewExperiment,
        source_scope_selection_experiment, source_scope_message_experiment, validate_source_scope_diagnostic_cell)
    state = json.loads((Path(__file__).parent / 'fixtures/planning-intake14-provider-shape-rejection.json').read_text())['snapshot']
    scope = state['scope']
    monkeypatch.setattr(socket.socket, 'connect', lambda *_: pytest.fail('No network before binding validation'))
    for variant, factory in [('L', views.PlanningInputView), ('K', SourceKindInputViewExperiment)]:
        view = factory(scope['inputs'], scope['catalog'])
        schema, binding = source_scope_selection_experiment(view.codec)
        schema = boundary.intake_selection(scope, schema)
        binding.update(schema_sha256=digest(schema), scope_sha256=digest(scope), input_view_identity=view.identity)
        message, _ = source_scope_message_experiment(boundary.view_a_message(scope, view, 'A-selection'), view.codec)
        message += '\n独立生产外来源约束实验身份：' + json.dumps(binding, ensure_ascii=False, separators=(',', ':'))
        item = {'number': 1, 'variant': variant, 'identity': {'runId': 'fixture-run', 'sessionId': 'fixture-session'},
                'schema_sha256': digest(schema), 'message_sha256': hashlib.sha256(message.encode()).hexdigest()}
        cell = {**item, 'schema': schema, 'message': message, 'experimental_binding': binding,
                'source_codec_policy': view.codec.identity['policy']}
        manifest = {'experimental_bindings': {variant: binding}}
        rebuilt = validate_source_scope_diagnostic_cell(cell, item, manifest, scope)
        assert rebuilt.identity == view.identity and rebuilt.codec.identity == view.codec.identity
        faults = []
        for policy in (None, 'unknown', 'planning-source-selection@999'):
            faults.append({**deepcopy(cell), 'source_codec_policy': policy})
        for key in ('number', 'variant', 'identity'):
            changed = deepcopy(cell); changed[key] = 'forged'; faults.append(changed)
        for key in ('base_codec_identity', 'input_view_identity', 'scope_sha256', 'schema_sha256'):
            changed = deepcopy(cell); changed['experimental_binding'][key] = 'forged'; faults.append(changed)
        for changed in faults:
            with pytest.raises(ValueError, match='Diagnostic cell'):
                validate_source_scope_diagnostic_cell(changed, item, manifest, scope)


def test_diagnostic_waits_for_durable_http_receipt_without_reissue(tmp_path):
    import threading
    from tests.planning_material_matrix.structured_gateway import EvalHttpBudget
    identity = {'cell': 1, 'run_id': 'fixture-run', 'session_id': 'fixture-session'}
    budget = EvalHttpBudget(tmp_path / 'ledger', 'a' * 64, limit=1)
    number = budget.reserve({'diagnostic_identity': identity})
    started, done = threading.Event(), threading.Event()
    result = []
    def reader():
        started.set()
        result.append(budget.wait_for_receipt(identity, timeout=2))
        done.set()
    thread = threading.Thread(target=reader); thread.start()
    assert started.wait(1) and not done.wait(.05)
    budget.finish(number, {'state': 'RESPONSE_COMPLETE', 'argument_stream_state': 'COMPLETE'})
    assert done.wait(2); thread.join()
    assert result[0]['state'] == 'RESPONSE_COMPLETE'
    assert len(json.loads(budget.path.read_text())['requests']) == 1
    before = budget.path.read_bytes()
    assert budget.wait_for_receipt(identity, timeout=.1) == result[0]
    assert budget.path.read_bytes() == before
    unknown = EvalHttpBudget(tmp_path / 'unknown', 'b' * 64, limit=1)
    number = unknown.reserve({'diagnostic_identity': identity})
    unknown.finish(number, {'state': 'UNKNOWN', 'argument_stream_state': 'UNKNOWN'})
    assert unknown.wait_for_receipt(identity, timeout=.1)['state'] == 'UNKNOWN'


def test_empty_and_multiple_argument_streams_keep_boundary_but_reject_native_candidate(tmp_path):
    from tests.planning_material_matrix.structured_gateway import EvalSseObservation, EvalHttpBudget
    runtime = Path('/Users/xgx/.local/node-v24.21.0-darwin-arm64/lib/node_modules/openclaw')
    node = runtime.parents[2] / 'bin/node'
    if not node.is_file(): pytest.skip('Installed pinned SDK unavailable')
    from easel.integrations.planning_structured import verify_runtime
    verify_runtime(runtime)
    cases = [('single-empty', [''], 'SINGLE_EMPTY'),
             ('multi-empty', [''] * 11, 'MULTIPLE_ALL_EMPTY'),
             ('multi-mixed', ['{"text":"fixed"}', ''], 'MULTIPLE_MIXED'),
             ('multi-nonempty', ['{"text":"fixed"}', '{}'], 'MULTIPLE_NONEMPTY'),
             ('single-valid', ['{"text":"fixed"}'], 'SINGLE_NONEMPTY'),
             ('empty-with-legacy', [''], 'SINGLE_EMPTY'),
             ('empty-with-markup', [''], 'SINGLE_EMPTY'),
             ('single-valid-invalid-legacy', ['{"text":"fixed"}'], 'SINGLE_NONEMPTY'),
             ('single-valid-invalid-content', ['{"text":"fixed"}'], 'SINGLE_NONEMPTY'),
             ('reasoning-only-stop', [], 'NOT_COMPLETE'),
             ('reasoning-only-length', [], 'NOT_COMPLETE'),
             ('reasoning-with-valid-tool', ['{"text":"fixed"}'], 'SINGLE_NONEMPTY')]
    fixture = []
    for name, values, expected in cases:
        calls = [{'index': i, 'id': f'call-{i}', 'type': 'function',
                  'function': {'name': 'submit_semantic_plan', 'arguments': value}} for i, value in enumerate(values)]
        frames = [{'choices': [{'index': 0, 'delta': {'tool_calls': calls}, 'finish_reason': None}]},
                  {'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'tool_calls'}]}]
        # Same observed shape as the M3.1 cell3 receipt, using synthetic text:
        # reasoning is present, but a completed stop must not become a candidate.
        reasoning_case = name.startswith('reasoning-')
        if reasoning_case:
            frames.insert(0, {'choices': [{'index': 0, 'delta': {
                'reasoning_content': 'private-reasoning-fixture'}, 'finish_reason': None}]})
            if not values:
                frames.pop(1)
                frames[-1]['choices'][0]['finish_reason'] = name.rsplit('-', 1)[1]
        alternate = '{"text":"alternate-channel-private"}'
        if name == 'empty-with-legacy':
            frames.insert(1, {'choices': [{'index': 0, 'delta': {'function_call': {
                'name': 'submit_semantic_plan', 'arguments': alternate}}, 'finish_reason': None}]})
        if name == 'empty-with-markup':
            for content in ('<tool_cal', 'ls><inv', 'oke>', alternate, '</invoke></tool_calls>'):
                frames.insert(-1, {'choices': [{'index': 0, 'delta': {'content': content}, 'finish_reason': None}]})
        if name == 'single-valid-invalid-legacy':
            frames.insert(1, {'choices': [{'index': 0, 'delta': {
                'function_call': {'name': 'submit_semantic_plan', 'arguments': '\ud800'}}, 'finish_reason': None}]})
        if name == 'single-valid-invalid-content':
            frames.insert(1, {'choices': [{'index': 0, 'delta': {'content': '\ud800'}, 'finish_reason': None}]})
            frames.insert(2, {'choices': [{'index': 0, 'delta': {
                'content': {'unexpected': 'private-hidden-content'}}, 'finish_reason': None}]})
        frames.append({'choices': [], 'base_resp': {'status_code': 0, 'status_msg': 'private-status-message'}})
        data = (''.join('data: ' + json.dumps(f) + '\n\n' for f in frames) + 'data: [DONE]\n\n').encode()
        for split in (1, 17, 16384):
            observer = EvalSseObservation()
            for i in range(0, len(data), split): observer.feed(data[i:i+split])
            observer.finish_response(); result = observer.result()
            assert result['argument_stream_state'] == ('COMPLETE' if values else 'INCOMPLETE')
            assert result['argument_payload_class'] == expected
            assert result['reasoning_delta_bytes'] == (len('private-reasoning-fixture') if reasoning_case else 0)
            if not values:
                assert result['provider_finish'] == name.rsplit('-', 1)[1]
                assert result['sse_done'] and not result['diagnostic_unknown']
                assert result['argument_streams'] == []
                assert result['argument_delta_bytes'] == 0
                assert 'ARGUMENT_STREAM_MISSING' in result['observation_reasons']
            assert ('EMPTY_ARGUMENTS' in result['observation_reasons']) == any(v == '' for v in values)
            assert ('MULTIPLE_TOOL_STREAMS' in result['observation_reasons']) == (len(values) > 1)
            channels = result['alternate_channels']
            assert channels['candidate_authority'] is False
            assert channels['provider_status_codes'] == [0]
            assert channels['legacy_argument_bytes'] == (len(alternate.encode()) if name == 'empty-with-legacy' else 0)
            assert channels['legacy_call_deltas'] == int(name in ('empty-with-legacy', 'single-valid-invalid-legacy'))
            assert channels['alternate_observation_invalid'] == name.startswith('single-valid-invalid-')
            if name == 'single-valid-invalid-content':
                assert channels['content_classes']['OTHER'] == 1
            if name.startswith('single-valid-invalid-'):
                assert result['argument_stream_state'] == 'COMPLETE'
                assert result['diagnostic_unknown'] is False
                # The old observer ignored alternate fields. Prove the new
                # diagnostics leave that same modern boundary untouched.
                class ModernOnly(EvalSseObservation):
                    def observe_alternate_channels(self, event, delta): pass
                previous = ModernOnly(); previous.feed(data); previous.finish_response()
                for key in ('argument_stream_state', 'argument_streams', 'provider_finish', 'diagnostic_unknown'):
                    assert result[key] == previous.result()[key]
            assert channels['content_tool_markers'] == (['<invoke', '<tool_call'] if name == 'empty-with-markup' else [])
            serialized = json.dumps(result)
            assert not any(value in serialized for value in ('alternate-channel-private', 'private-status-message', 'private-hidden-content', 'private-reasoning-fixture'))
        fixture.append({'name': name, 'sse': data.decode(), 'reasoning': reasoning_case,
                        'safe': name in ('single-valid', 'single-valid-invalid-legacy', 'reasoning-with-valid-tool')})
    path = tmp_path / 'cases.json'; path.write_text(json.dumps(fixture))
    script = tmp_path / 'empty-sdk.mjs'
    script.write_text(r'''
import fs from 'node:fs'; import path from 'node:path'; import net from 'node:net';
import assert from 'node:assert/strict'; import {pathToFileURL} from 'node:url';
net.Socket.prototype.connect=()=>{throw Error('OFFLINE_NETWORK_BLOCKED')};
const [runtime,dir,input]=process.argv.slice(2); const load=n=>import(pathToFileURL(path.join(runtime,n)));
const g=await load('dist/easel-structured-result.mjs');
const {createOpenAICompletionsTransportStreamFn}=await load('node_modules/@openclaw/ai/dist/transports.mjs');
const {t:host}=await load('node_modules/@openclaw/ai/dist/host-B8YfDGd4.mjs');
let wire;const fake=async()=>new Response(wire,{headers:{'content-type':'text/event-stream'}});
globalThis.fetch=fake;host({buildModelFetch:()=>fake});
const schema={type:'object',additionalProperties:false,properties:{text:{type:'string',maxLength:25}},required:['text']};
const request={version:g.VERSION,name:g.TOOL,schema,schemaSha256:g.sha256(g.canonical(schema))};
const model={id:'MiniMax-M3',provider:'minimax',api:'openai-completions',baseUrl:'https://offline.invalid/v1',reasoning:false,input:['text'],contextWindow:1000000,maxTokens:8192,cost:{input:0,output:0,cacheRead:0,cacheWrite:0}};
const results=[];
for(const f of JSON.parse(fs.readFileSync(input,'utf8'))){
 wire=f.sse;const folder=path.join(dir,f.name);fs.mkdirSync(folder,{mode:0o700});
 const selected=f.reasoning?{...model,id:'MiniMax-M3.1-Flash-Preview',reasoning:true}:model;
 const identity={runId:f.name,sessionId:'offline-'+f.name,provider:'minimax',model:selected.id};
 const bound=g.bindAttempt(createOpenAICompletionsTransportStreamFn(),request,identity,folder);
 const stream=bound(selected,{messages:[{role:'user',content:'offline fixed response',timestamp:0}],tools:[{name:g.TOOL,parameters:schema,description:'fixed'}]},{apiKey:'offline',maxTokens:8192,
  onPayload:p=>{if(f.reasoning){p.thinking={type:'adaptive'};p.reasoning_effort='low';}return p;}});
 for await(const e of stream){}const response=await stream.result();
 let safe=false;try{g.candidateEvidence(response,request);safe=true}catch{}
 assert.equal(safe,f.safe);results.push({name:f.name,safe});
}
process.stdout.write(JSON.stringify(results));
''')
    proc = subprocess.run([str(node), str(script), str(runtime), str(tmp_path), str(path)],
                          capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    results = json.loads(proc.stdout)
    for i, row in enumerate(results):
        if not row['safe']:
            budget = EvalHttpBudget(tmp_path / ('ledger-' + row['name']), f'{i + 1:064x}', limit=1)
            budget.reserve({}); budget.close('ENTRY_CAPTURE_UNAVAILABLE')
            before = budget.path.read_bytes()
            with pytest.raises(ValueError): budget.reserve({})
            state = json.loads(budget.path.read_text())
            assert len(state['requests']) == 1 and state['closed']
            assert state['requests'] == json.loads(before)['requests']


def test_shallow_details_experiment_preserves_closed_contract():
    from copy import deepcopy
    import pytest
    from jsonschema import ValidationError
    from easel.integrations.planning_result_contract import semantic_tool_schema, maximum_compact_bytes
    from tests.planning_material_matrix.producer_experiment import ShallowDetailsExperiment, StagedProducerExperiment
    catalog = {'global': {'global': {}}, 'scene': {'scene-1': {}}, 'continuity': {}}
    codec = StagedProducerExperiment(semantic_tool_schema(catalog, compiled=True))
    need = {'scope': 'scene-1', 'role': '背景', 'modality': 'image', 'necessity': 'required',
        'conditions': [{'text': '中文“🖼️”及括号{}', 'strength': 'required', 'responsibility': 'material'}]}
    bgm = {'scope': 'global', 'role': '音乐', 'modality': 'bgm', 'necessity': 'required',
        'conditions': [{'text': '轻柔无歌词音乐', 'strength': 'required', 'responsibility': 'material'}],
        'sound': {'vocals_allowed': False}}
    selection, details, binding = codec.encode({'needs': [bgm, *[deepcopy(need) for _ in range(6)]]})
    details['unresolved'] = ['未决原文必须保留', '顺序也不能改变']
    source = deepcopy(details)
    schema = codec.details_contract(selection)['schema']
    experiment = ShallowDetailsExperiment(schema, binding)
    flat = experiment.encode(details)
    assert 'slots' not in flat and len(flat) == 8
    assert experiment.decode(flat, experiment.identity) == details == source
    assert maximum_compact_bytes(experiment.schema) <= maximum_compact_bytes(schema)
    with pytest.raises(ValueError, match='binding'):
        experiment.decode(flat, {**experiment.identity, 'binding_sha256': '0' * 64})
    for fault in ('string', 'missing', 'extra', 'unresolved_missing', 'changed_field'):
        altered = deepcopy(flat)
        if fault == 'string': altered['slot_000'] = json.dumps(altered['slot_000'])
        elif fault == 'missing': del altered['slot_001']
        elif fault == 'extra': altered['slot_999'] = deepcopy(altered['slot_001'])
        elif fault == 'unresolved_missing': del altered['unresolved']
        else: altered['slot_001']['modality'] = 'video'
        with pytest.raises(ValidationError): experiment.decode(altered, experiment.identity)
    with pytest.raises(ValidationError):
        experiment.encode({'slots': json.dumps(details['slots']), 'unresolved': details['unresolved']})
    for location in ('root', 'slots'):
        altered = deepcopy(schema)
        (altered if location == 'root' else altered['properties']['slots'])['minProperties'] = 2
        with pytest.raises(ValueError): ShallowDetailsExperiment(altered, binding)
    assert details == source


def test_staged_producer_identity_and_existing_repair(tmp_path):
    """Finite design evidence only: no staged dispatcher or model call exists."""
    from copy import deepcopy
    import pytest
    from jsonschema import ValidationError
    from easel.integrations import planning_semantic_review as review
    from easel.integrations.planning_result_contract import semantic_tool_schema, maximum_compact_bytes
    from tests.planning_material_matrix.producer_experiment import StagedProducerExperiment

    catalog = {'global': {'global': {}}, 'event': {'event-1': {}},
               'scene': {'scene-1': {}}, 'voice': {'confirmed.voice_profile': {}}, 'continuity': {}}
    canonical = semantic_tool_schema(catalog, compiled=True)
    codec = StagedProducerExperiment(canonical)
    need = {'scope': 'scene-1', 'role': '画面', 'modality': 'image', 'necessity': 'optional',
            'conditions': [{'text': '白纸“🖼️”', 'strength': 'required', 'responsibility': 'material'}]}
    selection, details, receipt = codec.encode({'needs': [need, deepcopy(need)]})
    original = deepcopy((selection, details, receipt))
    rows = []
    for fault in ('missing', 'unknown', 'header', 'cross_modality', 'other_selection', 'other_schema', 'duplicate'):
        s, d, r = deepcopy(original)
        if fault == 'missing': del d['slots']['slot_001']
        elif fault == 'unknown': d['slots']['slot_002'] = deepcopy(d['slots']['slot_000'])
        elif fault == 'header': d['slots']['slot_000']['modality'] = 'video'
        elif fault == 'cross_modality': d['slots']['slot_000']['source_seconds'] = 3
        elif fault == 'other_selection': s['needs'][0]['role'] = '另一候选'
        elif fault == 'other_schema': r['canonical_sha256'] = '0' * 64
        if fault == 'duplicate':
            with pytest.raises(ValueError, match='Duplicate'):
                codec.parse_raw('{"slots":{"slot_000":{},"slot_000":{}}}')
        else:
            with pytest.raises((ValueError, ValidationError)): codec.assemble(s, d, r)
            with pytest.raises((ValueError, ValidationError)): codec.assemble_candidate(s, d, r)
        rows.append({'case': fault, 'expected': 'REJECT', 'actual': 'REJECT', 'result': 'PASS'})
    assert (selection, details, receipt) == original
    for fault, path, corrected in [('detail-leaf', ['needs', 0, 'conditions', 0, 'meaning'], 'observable'),
                                    ('selection-leaf', ['needs', 0, 'necessity'], 'optional')]:
        s, d, _ = deepcopy(original)
        if fault == 'detail-leaf': d['slots']['slot_000']['conditions'][0]['meaning'] = 'allowed'
        else: s['needs'][0]['necessity'] = 'OPTIONAL'
        r = codec.details_contract(s, diagnostic=True)['identity']
        with pytest.raises((ValueError, ValidationError)): codec.assemble(s, d, r)
        candidate = codec.assemble_candidate(s, d, r)
        targets = review.structural_targets(candidate)
        assert len(targets) == 1 and targets[0]['path'] == path
        repaired = review.apply_patches(candidate, {'patches': [{'target': 0, 'value': corrected}]}, targets)
        codec.union.encode(repaired)  # Full original validation after the bounded patch.
        assert repaired['needs'][1] == candidate['needs'][1]
        rows.append({'case': fault, 'expected': 'ORIGINAL_LOCAL_REPAIR',
                     'actual': 'ORIGINAL_LOCAL_REPAIR', 'result': 'PASS'})

    # A selection receipt is provenance, never a veto on the existing bounded
    # B repair. The original canonical consumer still decides admissibility.
    assembled = codec.assemble(selection, details, receipt)
    replacement = deepcopy(assembled['needs'][0])
    replacement.update(modality='video', source_seconds=3)
    targets = [{'kind': 'visual_choices', 'path': [0]}]
    repaired = review.apply_patches(assembled, {'patches': [{'target': 0, 'value': replacement}]}, targets)
    codec.union.encode(repaired)
    assert repaired['needs'][0]['modality'] == 'video'
    assert repaired['needs'][1] == assembled['needs'][1]
    assert codec.assemble(selection, details, receipt) == assembled
    replacement['necessity'] = 'required'
    with pytest.raises(ValueError, match='necessity'):
        review.apply_patches(assembled, {'patches': [{'target': 0, 'value': replacement}]}, targets)
    rows.extend([{'case': name, 'expected': expectation, 'actual': expectation, 'result': 'PASS'}
                 for name, expectation in [('existing-modality-repair', 'ACCEPT'),
                                          ('necessity-escalation', 'REJECT')]])

    # Unresolved claims survive both submissions; they must not disappear in
    # assembly, even though the later product consumer refuses unresolved A.
    s, d, r = deepcopy(original)
    s['unresolved'] = ['第一阶段未决']; d['unresolved'] = ['第二阶段未决']
    r = codec.details_contract(s)['identity']
    assert codec.assemble(s, d, r)['unresolved'] == ['第一阶段未决', '第二阶段未决']
    rows.append({'case': 'unresolved-preserved', 'expected': 'BOTH', 'actual': 'BOTH', 'result': 'PASS'})

    capacities = []
    for derived in (False, True):
        schema = semantic_tool_schema({**catalog, **({'derived_voice': {'fixture': True}} if derived else {})}, compiled=True)
        c = StagedProducerExperiment(schema)
        count = schema['properties']['needs']['maxItems']
        s, d, r = c.encode({'needs': [deepcopy(need) for _ in range(count)]})
        assert len(c.assemble(s, d, r)['needs']) == count
        s['needs'].append(deepcopy(s['needs'][0]))
        with pytest.raises(ValidationError): c.details_contract(s)
        s['needs'].pop()
        detail_schema = c.details_contract(s)['schema']
        compact = lambda v: len(json.dumps(v, ensure_ascii=False, separators=(',', ':')).encode())
        capacities.append({'derived_voice': derived, 'maximum_needs': count,
                           'selection_schema_bytes': compact(c.selection_schema),
                           'details_schema_bytes': compact(detail_schema),
                           'selection_max_result_bytes': maximum_compact_bytes(c.selection_schema),
                           'details_max_result_bytes': maximum_compact_bytes(detail_schema)})
        s['needs'][0]['scope'] = 'unknown'
        with pytest.raises(ValidationError): c.details_contract(s)

    folder = Path(__file__).parent / 'fixtures/planning-vnext-development-2026-10-08'
    for stem in ('autonomous-qualification-A', 'autonomous-m27-qualification-A'):
        contract = json.loads((folder / f'{stem}-contract.json').read_text())
        c = StagedProducerExperiment(contract['canonical_schema'])
        with pytest.raises((ValueError, ValidationError)):
            c.encode(json.loads((folder / f'{stem}-wire.json').read_text()))
        rows.append({'case': stem, 'expected': 'REJECT', 'actual': 'REJECT', 'result': 'PASS'})
    # Exact first @8 real selection: items:false is a business leaf schema,
    # not an object on which the diagnostic shape walker may call .get().
    contract = json.loads((folder / 'autonomous-staged-qualification-contract.json').read_text())
    raw = (folder / 'autonomous-staged-qualification-selection.json').read_text()
    captured = json.loads(raw)
    c = StagedProducerExperiment(contract['canonical_schema'])
    before_capture = deepcopy(captured)
    derived = c.details_contract(captured, diagnostic=True)
    assert captured == before_capture
    from easel.integrations import planning_wire
    assert planning_wire.project(c.selection_schema, 'A-selection').errors(captured)
    planning_wire.project(derived['schema'], 'A-details')
    with pytest.raises(ValidationError): c.details_contract(captured)
    rows.append({'case': 'real-staged-selection', 'expected': 'DIAGNOSTIC_PRESERVED_STRICT_REJECT',
                 'actual': 'DIAGNOSTIC_PRESERVED_STRICT_REJECT', 'result': 'PASS'})

    # A permitted repair on another leaf must not hide forbidden continuity.
    s, d, _ = deepcopy(original)
    s['needs'][0].update(continuity_choices=['segment-1'], necessity='OPTIONAL')
    receipt = codec.details_contract(s, diagnostic=True)['identity']
    candidate = codec.assemble_candidate(s, d, receipt)
    targets = review.structural_targets(candidate)
    assert len(targets) == 1 and targets[0]['path'] == ['needs', 0, 'necessity']
    repaired = review.apply_patches(candidate, {'patches': [{'target': 0, 'value': 'optional'}]}, targets)
    assert repaired['needs'][0]['continuity_choices'] == ['segment-1']
    with pytest.raises(ValidationError): codec.union.encode(repaired)
    assert codec.assemble(*original)['needs'][0]['continuity_choices'] == []
    rows.append({'case': 'unrelated-repair-preserves-false-schema-reject', 'expected': 'REJECT',
                 'actual': 'REJECT', 'result': 'PASS'})
    report = {'kind': 'offline-staged-producer-design', 'production_enabled': False,
              'actual_http': 0, 'model_reliability': 'NOT_TESTED', 'canonical_changed': False,
              'repair_contract_changed': False, 'cases': rows, 'capacities': capacities,
              'extra_initial_submissions_per_planning': 1, 'pass': len(rows), 'fail': 0}
    (tmp_path / 'staged-producer-design.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))


def test_four_cell_diagnostic_identity_payload_and_classification(tmp_path):
    """Real HTTP boundary + original decoders, no live credential/model calls."""
    import concurrent.futures
    import hashlib
    import threading
    import urllib.request
    import urllib.error
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from copy import deepcopy
    import pytest
    from easel.integrations.planning_structured import request_for, TOOL
    from tests.planning_material_matrix.structured_gateway import EvalHttpBudget, EvalProviderProxy
    from tests.planning_material_matrix.planning_eval_run import (
        contrast_probes, classify_contrast, require_contrast_terminal, contrast_projection,
        EvalStateViolation, accept_convergence_stage,
    )
    from easel.integrations.planning_result_contract import semantic_tool_schema
    from easel.integrations.planning_wire import FrameProjection
    catalog = {'scene': {'scene-1': {}}, 'voice': {}, 'continuity': {}}
    canonical = semantic_tool_schema(catalog, compiled=True)
    original = {'stage': 'A', 'catalog': catalog, 'canonical_schema': canonical,
        'schema': FrameProjection(canonical, 'A').schema,
        'message': '固定创作任务\n' + json.dumps({'inputs': {'SCRIPT.md': '原文不变'}, 'catalog': catalog,
            'transport': {'wire': {}, 'schema_sha256': 'original'}, 'wire_representation': '原子画幅'})}
    params = {'params': {'extra_body': {'thinking': {'type': 'disabled'}}}}
    probes = contrast_probes(original, params)
    assert params['params']['extra_body']['thinking']['type'] == 'disabled'
    for i, probe in enumerate(probes):
        context = json.loads(probe['message'].split('\n', 1)[1])
        assert context['inputs'] == {'SCRIPT.md': '原文不变'} and context['catalog'] == catalog
        assert probe['thinking'] == ('disabled' if i < 2 else 'adaptive')
        legal = {'needs': [{'scope': 'scene-1', 'role': '背景', 'modality': 'image', 'necessity': 'required',
            'conditions': [{'text': '一张白纸', 'strength': 'required', 'responsibility': 'material'}]}]}
        codec = contrast_projection(probe)
        encoded = codec.encode(legal)
        assert classify_contrast(probe, json.dumps(encoded))['result'] == 'OBSERVED_CONTRACT_ACCEPT'
        encoded['needs'][0]['conditions'][0]['meaning'] = 'allowed'
        assert classify_contrast(probe, json.dumps(encoded))['result'] == 'OBSERVED_CONTRACT_REJECT'
        with pytest.raises(ValueError): classify_contrast(probe, '{broken')
        changed = deepcopy(probe); changed['schema']['title'] = 'changed'
        with pytest.raises(EvalStateViolation): classify_contrast(changed, json.dumps(encoded))
    for status, release in [('ok', 'pending'), ('error', 'released'), ('pending', None)]:
        with pytest.raises(EvalStateViolation): require_contrast_terminal({'delivery': {'agent_calls': {'one': {
            'status': status, 'runtime_release': release, 'reply_contract': 'planning-result-v3', 'run_id': 'original'}}}})
    assert require_contrast_terminal({'delivery': {'agent_calls': {'one': {'status': 'ok', 'runtime_release': 'released',
        'reply_contract': 'planning-result-v3', 'run_id': 'original'}}}}) == 'original'
    # Per-cell occupancy is durable and atomic, including concurrent attempts.
    digest = hashlib.sha256(b'new-fixed-four-cell-manifest').hexdigest()
    timer = [100.]
    budget = EvalHttpBudget(tmp_path / 'cap', digest, limit=4, seconds=900, clock=lambda: timer[0])
    for i in range(4):
        number = budget.reserve({'cell': i}, expected_number=i + 1)
        budget.finish(number, {'state': 'RESPONSE_COMPLETE'})
        accept_convergence_stage({'result': 'OBSERVED_CONTRACT_REJECT'}, budget)
    with pytest.raises(ValueError): budget.reserve({}, expected_number=5)
    with pytest.raises(ValueError): EvalHttpBudget(tmp_path / 'cap', digest, limit=40)
    for case in ('unknown', 'released-duplicate', 'concurrent', 'deadline'):
        current = EvalHttpBudget(tmp_path / case, digest, limit=4, seconds=900, clock=lambda: timer[0])
        if case == 'concurrent':
            def reserve(_):
                try: return current.reserve({}, expected_number=1)
                except ValueError: return None
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                assert sum(x is not None for x in pool.map(reserve, range(2))) == 1
            assert len(json.loads(current.path.read_text())['requests']) == 1
            continue
        number = current.reserve({}, expected_number=1)
        if case != 'unknown': current.finish(number, {'state': 'RESPONSE_COMPLETE'})
        restored = EvalHttpBudget(tmp_path / case, digest, limit=4, seconds=900, clock=lambda: timer[0])
        if case == 'deadline': timer[0] += 900
        with pytest.raises(ValueError): restored.reserve({}, expected_number=2 if case != 'released-duplicate' else 1)
        timer[0] = 100.
    # Check the exact outbound settings before any upstream side effect.
    calls = []
    class Upstream(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_POST(self):
            calls.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            data = b'data: {"choices":[{"delta":{},"finish_reason":"tool_calls"}]}\n\ndata: [DONE]\n\n'
            self.send_response(200); self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Upstream)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    schema = probes[2]['schema']
    payload = {'model': 'MiniMax-M3', 'thinking': {'type': 'adaptive'}, 'parallel_tool_calls': False,
        'max_completion_tokens': 8192,
        'tools': [{'type': 'function', 'function': {'name': TOOL, 'parameters': schema}}],
        'tool_choice': {'type': 'function', 'function': {'name': TOOL}}}
    expected = {'schema_sha256': request_for(schema)['schemaSha256'], 'thinking_mode': 'adaptive', 'max_tokens': None,
                'max_completion_tokens': 8192,
                'tools_count': 1, 'tool_choice_kind': 'function', 'model': 'MiniMax-M3'}
    try:
        for scenario in ('valid', 'thinking', 'schema', 'tool', 'parallel', 'tokens',
                         'completion_changed', 'completion_missing', 'completion_null',
                         'completion_bool', 'completion_string', 'completion_negative'):
            changed = deepcopy(payload)
            if scenario == 'thinking': changed['thinking'] = {'type': 'disabled'}
            if scenario == 'schema': changed['tools'][0]['function']['parameters'] = {'type': 'object'}
            if scenario == 'tool': changed['tools'][0]['function']['name'] = 'other'
            if scenario == 'parallel': changed['parallel_tool_calls'] = True
            if scenario == 'tokens': changed['max_tokens'] = 123
            if scenario == 'completion_changed': changed['max_completion_tokens'] = 16384
            if scenario == 'completion_missing': changed.pop('max_completion_tokens')
            if scenario == 'completion_null': changed['max_completion_tokens'] = None
            if scenario == 'completion_bool': changed['max_completion_tokens'] = True
            if scenario == 'completion_string': changed['max_completion_tokens'] = '8192'
            if scenario == 'completion_negative': changed['max_completion_tokens'] = -1
            current = EvalHttpBudget(tmp_path / ('http-' + scenario), digest, limit=4, seconds=900)
            proxy = EvalProviderProxy(current, f'http://127.0.0.1:{server.server_port}/v1/chat/completions',
                'MiniMax-M3', 'offline-placeholder', offline=True, expected_payload=expected, expected_number=1).start()
            def send():
                request = urllib.request.Request(proxy.url + '/chat/completions', data=json.dumps(changed).encode(),
                    headers={'Authorization': 'Bearer ' + proxy.client_token})
                with urllib.request.urlopen(request, timeout=10) as response: return response.read()
            before = len(calls)
            try:
                if scenario == 'valid':
                    send(); assert len(calls) == before + 1
                    with pytest.raises(urllib.error.HTTPError): send()
                    assert len(calls) == before + 1
                else:
                    with pytest.raises(urllib.error.HTTPError): send()
                    assert len(calls) == before
                state = json.loads(current.path.read_text())
                assert state['closed'] and len(state['requests']) == (1 if scenario == 'valid' else 0)
            finally: proxy.stop()
        # The all-stage parameter guard also accepts ordinary Truth tools,
        # while rejecting drift before the Provider sees a request.
        common = {'model': 'MiniMax-M3', 'thinking_mode': 'adaptive',
                  'max_tokens': None, 'max_completion_tokens': 131072}
        for scenario in ('truth', 'drift', 'alias', 'm27-text', 'm27-image', 'm27-audio',
                         'm27-priority', 'm27-wrong-model'):
            m27 = scenario.startswith('m27-')
            model = 'MiniMax-M2.7' if m27 else 'MiniMax-M3'
            cap = 65536 if m27 else 131072
            expected_common = {**common, 'model': model, 'max_completion_tokens': cap}
            changed = {'model': model, 'thinking': {'type': 'adaptive'},
                       'max_completion_tokens': cap, 'tools': [], 'tool_choice': 'auto',
                       'messages': [{'role': 'user', 'content': [{'type': 'text', 'text': '纯文本'}]}]}
            if scenario == 'drift': changed['max_completion_tokens'] = 8192
            if scenario == 'alias': changed['max_tokens'] = 131072
            if scenario == 'm27-image': changed['messages'][0]['content'].append({'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,AA=='}})
            if scenario == 'm27-audio': changed['messages'][0]['audio'] = {'id': 'fixture'}
            if scenario == 'm27-priority': changed['priority'] = 1
            if scenario == 'm27-wrong-model': changed['model'] = 'MiniMax-M3'
            current = EvalHttpBudget(tmp_path / ('common-' + scenario), digest)
            proxy = EvalProviderProxy(current, f'http://127.0.0.1:{server.server_port}/v1/chat/completions',
                model, 'offline-placeholder', offline=True, expected_model_params=expected_common).start()
            before = len(calls)
            try:
                request = urllib.request.Request(proxy.url + '/chat/completions', data=json.dumps(changed).encode(),
                    headers={'Authorization': 'Bearer ' + proxy.client_token})
                if scenario in {'truth', 'm27-text'}:
                    with urllib.request.urlopen(request, timeout=10) as response: response.read()
                    assert len(calls) == before + 1
                else:
                    with pytest.raises(urllib.error.HTTPError) as rejected: urllib.request.urlopen(request, timeout=10)
                    rejected.value.close()
                    assert len(calls) == before and json.loads(current.path.read_text())['closed']
            finally: proxy.stop()
    finally: server.shutdown(); server.server_close(); thread.join()


def test_source_selection_view_is_reversible_not_semantic_repair(tmp_path):
    from copy import deepcopy
    import pytest
    from jsonschema import ValidationError
    from tests.planning_material_matrix.producer_experiment import SourceSelectionExperiment
    from easel.integrations.planning_result_contract import semantic_tool_schema
    folder = Path(__file__).parent / 'fixtures/planning-vnext-development-2026-10-08'
    contract = json.loads((folder / 'autonomous-staged-qualification-contract.json').read_text())
    catalog = contract['catalog']
    codec = SourceSelectionExperiment(contract['canonical_schema'], catalog)
    # Preserve every legal kind, including equal-text aliases. Position is not
    # automatically converted into a narrative shot or a different scope kind.
    observed = []
    for original, handle in codec.to_wire.items():
        selection = {'needs': [{'scope': original, 'role': 'source reference', 'modality': 'image',
                      'necessity': 'optional', 'continuity_choices': []}], 'unresolved': ['unknown meaning']}
        # Selection itself admits scope kinds; later full canonical modality
        # constraints are deliberately not relaxed by this representation.
        encoded = codec.encode(selection)
        assert encoded['needs'][0]['scope'] == handle and 'continuity_choices' not in encoded['needs'][0]
        assert codec.decode(encoded, codec.identity) == selection
        observed.append(original)
    assert len(observed) == len(codec.references) == 82
    assert len({codec.to_wire[f'{kind}-1'] for kind in ('scene', 'event', 'segment')}) == 3
    raw = json.loads((folder / 'autonomous-staged-qualification-selection.json').read_text())
    with pytest.raises(ValidationError): codec.encode(raw)  # Historical FAIL is not cleaned.
    original = deepcopy(encoded)
    for fault in ('old_handle', 'unknown', 'cross_catalog', 'injected_continuity'):
        poisoned, identity = deepcopy(encoded), deepcopy(codec.identity)
        if fault == 'old_handle': poisoned['needs'][0]['scope'] = 'scene-1'
        if fault == 'unknown': poisoned['needs'][0]['scope'] = 'src_unknown'
        if fault == 'cross_catalog': identity['catalog_sha256'] = '0' * 64
        if fault == 'injected_continuity': poisoned['needs'][0]['continuity_choices'] = ['segment-1']
        with pytest.raises((ValueError, ValidationError)): codec.decode(poisoned, identity)
        with pytest.raises((ValueError, ValidationError)): codec.decode(poisoned, identity, diagnostic=True)
    assert encoded == original
    # Nonempty continuity keeps its original selection capability, not [] inference.
    full = deepcopy(catalog); full['continuity'] = {'person-ref': {'kind': 'character', 'identity': 'approved symbolic figure'}}
    c = SourceSelectionExperiment(semantic_tool_schema(full, compiled=True), full)
    selection['needs'][0]['continuity_choices'] = ['person-ref']
    value = c.encode(selection)
    assert value['needs'][0]['continuity_choices'] == ['person-ref']
    assert c.decode(value, c.identity) == selection
    # No automatic inference about necessity or source-vs-postproduction.
    value['needs'][0]['necessity'] = 'INVALID'
    candidate = c.decode(value, c.identity, diagnostic=True)
    assert candidate['needs'][0]['necessity'] == 'INVALID'
    with pytest.raises(ValidationError): c.decode(value, c.identity)
    (tmp_path / 'source-selection-view.json').write_text(json.dumps({
        'status': 'OFFLINE_EXPERIMENT_ONLY', 'source_kinds_roundtripped': len(observed),
        'historical_invalid_selection': 'REJECT', 'semantic_inference': False,
        'new_real_calls': 0, 'production_enabled': False}, ensure_ascii=False, indent=2))


def test_planning_input_view_reconstructs_full_sources(tmp_path):
    from copy import deepcopy
    import pytest
    from tests.planning_material_matrix.producer_experiment import PlanningInputViewExperiment
    from easel.integrations import planning_authority as authority
    from easel.integrations.semantic_planning import source_catalog
    from easel.creator_proposal import parse_video_plan, validate_video_plan
    folder = Path(__file__).parent / 'fixtures/planning-vnext-development-2026-10-08'
    real = json.loads((folder / 'autonomous-staged-qualification-inputs.json').read_text())
    real_catalog = json.loads((folder / 'autonomous-staged-qualification-contract.json').read_text())['catalog']
    assert validate_video_plan(real['proposal'])
    samples = json.loads((Path(__file__).parent / 'fixtures/planning-eval-r4-2026-10-07/samples.json').read_text())
    other = deepcopy(real)
    other.pop('voice_binding')
    other['proposal'] = parse_video_plan(samples['samples'][1]['proposal'])
    assert validate_video_plan(other['proposal']) and other['proposal']['schema'] == 'easel-video-proposal@2'
    other['confirmed'] = {'SCRIPT.md': other['proposal']['script'], 'SCENES.md': other['proposal']['scenes'],
                          'TREATMENT.md': other['proposal']['treatment'] + '\n\n## 声音设计\n' + other['proposal']['sound']}
    other['creator_context'] = {'voice': {}, 'references': [{'id': 'figure-ref', 'kind': 'character',
                                                          'meaning': 'approved abstract figure'}]}
    other_catalog = source_catalog(other['confirmed'], {'creator_context': other['creator_context'], 'proposal': other['proposal']})
    assert not other_catalog['voice'] and 'derived_voice' not in other_catalog and other_catalog['continuity']
    unicode = deepcopy(other)
    # Derived representation-risk control, not a freshly confirmed work. The
    # legacy no-proposal input path permits exact independent canonical text.
    unicode['proposal'] = None
    unicode['confirmed']['SCENES.md'] = '\r\n# 标题🖼️\r\n重复：e\u0301 与 é\r\n\r\n重复：e\u0301 与 é\n末行\u2028最后。'
    unicode['confirmed']['TREATMENT.md'] = '安静🧭\r\n\r\nBGM is optional.\r\n确认稿要求配乐。'
    unicode_catalog = source_catalog(unicode['confirmed'], {'creator_context': unicode['creator_context']})
    independent = deepcopy(other)
    # A representation must preserve an independent text field even when its
    # higher-level confirmed contract would reject a mismatch. No fuzzy match.
    independent['proposal']['sound'] = '独立原文；并不在确认稿里。'
    cases = [('real-v3', real, real_catalog), ('legal-v2-no-bound-voice', other, other_catalog),
             ('unicode-legacy-canonical', unicode, unicode_catalog), ('independent-negative', independent, other_catalog)]
    reports = []
    for label, inputs, catalog in cases:
        originals = deepcopy((inputs, catalog))
        codec = PlanningInputViewExperiment(inputs, catalog)
        persisted = PlanningInputViewExperiment(json.loads(json.dumps(inputs, sort_keys=True)),
                                                json.loads(json.dumps(catalog, sort_keys=True)))
        assert persisted.snapshot() == codec.snapshot()
        assert persisted.codec.schema == codec.codec.schema
        restored, restored_catalog, sources = codec.decode(codec.view, codec.identity)
        expected = authority.catalog(inputs)
        assert restored == inputs and restored_catalog == catalog and sources == expected
        assert sources['sources'] == expected['sources']  # Includes order, repeated text, hashes and scope aliases.
        assert (inputs, catalog) == originals
        assert set(codec.view['catalog'].get('voice', {})) == set(catalog.get('voice', {}))
        assert all(g['offset_unit'] == 'python_characters' for g in codec.view['eligibility'])
        assert codec.view['inputs']['confirmed']['SCENES.md']['offset_unit'] == 'utf8_bytes'
        for field in ('mode_documents', 'preparation', 'truth_packet', 'content_core', 'creator_context'):
            assert codec.view['inputs'][field] == inputs[field]
        if label == 'independent-negative':
            assert codec.view['inputs']['proposal']['sound'] == inputs['proposal']['sound']
        if label == 'unicode-legacy-canonical':
            repeated = [r for r in sources['sources'] if r['origin'] == 'confirmed_scene' and r['text'].startswith('重复')]
            assert len(repeated) == 2 and repeated[0]['id'] != repeated[1]['id'] and repeated[0]['span'] != repeated[1]['span']
            assert any(line['byte_end'] - line['byte_start'] != len(line['text'])
                       for line in codec.view['inputs']['confirmed']['SCENES.md']['lines'])
        for fault in ('document', 'offset_unit', 'reference', 'scope', 'authority', 'order', 'cross-input'):
            changed, identity = deepcopy(codec.view), deepcopy(codec.identity)
            doc = changed['inputs']['confirmed']['SCENES.md']
            if fault == 'document': doc['lines'][0]['text'] += ' '
            if fault == 'offset_unit': doc['offset_unit'] = 'python_characters'
            if fault == 'reference':
                link = codec.links[0] if codec.links else None
                if link: codec.put(changed, link['path'], {'program_reference': {'json_path': ['../outside']}})
                else: doc['whole_document'] = 'src_unknown'
            if fault == 'scope': doc['whole_document'] = next(h for h in codec.codec.references if h != codec.codec.to_wire['global'])
            if fault == 'authority': changed['eligibility'][0]['primary'] = not changed['eligibility'][0]['primary']
            if fault == 'order':
                if len(doc['lines']) > 1: doc['lines'].reverse()
                else: changed['eligibility'].reverse()
            if fault == 'cross-input': identity['inputs_sha256'] = '0' * 64
            with pytest.raises(ValueError): codec.decode(changed, identity)
        lineage = deepcopy(codec.metadata)
        if codec.metadata:
            codec.metadata[0]['value'] = 'changed'
            with pytest.raises(ValueError, match='lineage'): codec.decode(codec.view, codec.identity)
            codec.metadata = lineage
        reports.append({'case': label, 'authority_sources': len(sources['sources']),
                        'source_mapping': len(codec.codec.references), 'result': 'PASS'})
    # The path resolver never follows filesystem paths or treats booleans as indices.
    for path in [['missing'], ['list', True], ['list', -1], ['list', '0']]:
        with pytest.raises(ValueError): PlanningInputViewExperiment.at({'list': ['x']}, path)
    (tmp_path / 'input-view-roundtrip.json').write_text(json.dumps({
        'status': 'OFFLINE_ROUNDTRIP_ONLY', 'cases': reports, 'real_calls': 0,
        'semantic_conflicts_resolved': False, 'production_enabled': False}, ensure_ascii=False, indent=2))


def test_r6_transcript_reader_only_consumes_original_structured_tool(tmp_path):
    """Real Node consumer; only the external Runtime/readonly transcript are fixtures."""
    import hashlib
    from copy import deepcopy
    from easel.integrations.planning_transcript import SELECTOR
    from easel.integrations.planning_structured import request_for
    root = tmp_path / 'offline-runtime'
    dist = root / 'dist'
    (dist / 'plugin-sdk').mkdir(parents=True)
    (root / 'package.json').write_text(json.dumps({'version': '2026.9.4', 'type': 'module'}))
    (dist / SELECTOR).write_text('export const X=events=>events.map((event,seq)=>({event,seq}));')
    profile = dist / 'startup-trace-DTSRmmXT.mjs'
    profile.write_text('export const r=()=>{};')
    (dist / 'plugin-sdk/sqlite-runtime.js').write_text('''
import fs from 'node:fs';
export const withOpenClawAgentDatabaseReadOnly=callback=>{
 const events=JSON.parse(fs.readFileSync(new URL('../events.json',import.meta.url),'utf8'));
 const db={exec(sql){if(!['BEGIN','ROLLBACK'].includes(sql))throw Error('write forbidden');},
 prepare(){return {get(){return {n:events.length,bytes:JSON.stringify(events).length};},
 all(){return events.map(event=>({event_json:JSON.stringify(event)}));}};}};
 return {found:true,value:callback({db})};
};
''')
    repo = Path(__file__).resolve().parents[1]
    guard = dist / 'easel-structured-result.mjs'
    guard.write_bytes((repo / 'scripts/openclaw_structured_result.mjs').read_bytes())
    request = request_for({'type': 'object', 'properties': {'needs': {'type': 'array'}},
                           'required': ['needs'], 'additionalProperties': False})
    raw = '{"needs":[]}'
    digest = hashlib.sha256(raw.encode()).hexdigest()
    message = {'role': 'assistant', '__openclaw': {'runId': 'original'}, 'stopReason': 'toolUse',
        'easelProviderFinishReason': 'tool_calls',
        'content': [{'type': 'toolCall', 'id': 'tool-1', 'name': request['name'],
                     'arguments': {'needs': []}, 'easelRawArguments': raw}],
        'easelStructuredResult': {'version': request['version'], 'schemaSha256': request['schemaSha256'],
            'toolCallId': 'tool-1', 'providerFinishReason': 'tool_calls', 'rawSha256': digest,
            'rawBytes': len(raw.encode())}}
    params = {'agentId': 'main', 'sessionKey': 'agent:main:original', 'sessionId': 'session',
        'runId': 'original', 'profile': 'fixture', 'maxResultBytes': 8388608, 'structured': request,
        'runtimeParts': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (dist / SELECTOR, profile)},
        'structuredParts': {'dist/easel-structured-result.mjs': hashlib.sha256(guard.read_bytes()).hexdigest()}}
    for fault in ('none', 'prose', 'schema', 'run', 'session', 'missing_contract', 'bytes', 'duplicate_tool'):
        current, options = deepcopy(message), deepcopy(params)
        if fault == 'prose':
            current.update(stopReason='stop', content=[{'type': 'text', 'text': raw}])
        if fault == 'schema': current['easelStructuredResult']['schemaSha256'] = 'wrong'
        if fault == 'run': current['__openclaw']['runId'] = 'other'
        if fault == 'session': options['sessionId'] = 'other'
        if fault == 'missing_contract': options.pop('structured')
        if fault == 'bytes': current['content'][0]['easelRawArguments'] += ' '
        if fault == 'duplicate_tool': current['content'].append(deepcopy(current['content'][0]))
        events = [{'type': 'session', 'id': 'session'}, {'type': 'message', 'id': 'message', 'message': current}]
        source = dist / 'events.json'
        source.write_text(json.dumps(events))
        before = source.read_bytes()
        completed = subprocess.run([shutil.which('node'), str(repo / 'easel/integrations/planning_transcript.mjs'), str(root)],
            input=json.dumps(options), capture_output=True, text=True, check=True, timeout=15)
        result = json.loads(completed.stdout)
        if fault == 'none':
            assert result['state'] == 'FOUND' and result['text'] == raw and result['sha256'] == digest
        else:
            assert result['state'] in {'TOOL_REJECTED', 'MISSING', 'UNAVAILABLE'}
        assert source.read_bytes() == before
