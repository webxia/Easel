"""Explicit isolated Runtime component of the existing matrix; external HTTP fixture only.

Run with EASEL_TEST_RUNTIME pointing to the reviewed isolated installation copy.
This file is outside normal test discovery and never skips a required case.
"""
from pathlib import Path
import hashlib
import json
import os
import shutil

import pytest
from tests.test_semantic_planning import (
    material_integration_env, semantic_runtime, authority_runtime,
    test_vnext_bounded_review_runtime as bounded_review,
    test_vnext_confirmed_preset_truth_boundary as preset_chain,
)
from tests.test_creation_preparation import prep_env
from tests.planning_material_matrix.structured_gateway import main as gateway, EvalHttpBudget


@pytest.mark.parametrize('risk', ['real_wrapper', 'real_full_creation2', 'structural_repair', 'repair_invalid', 'xml_roundtrip', 'xml_answer_repair', 'frame_header_repair', 'm27_frame_header_repair', 'm27_staged_lifecycle', 'm27_p3_correction'])
def test_native_harness_lifecycle(authority_runtime, monkeypatch, tmp_path, risk):
    runtime = Path(os.environ['EASEL_TEST_RUNTIME']).resolve()
    assert runtime.parent == Path('/tmp').resolve() and runtime.name.startswith('easel-structured-runtime-'), 'Only inspected isolated copies'
    node = shutil.which('node')
    assert node
    records = []
    budget = EvalHttpBudget(tmp_path / 'all-model-http', hashlib.sha256(risk.encode()).hexdigest())
    def carrier(raw, request):
        index = len(records)
        payload = tmp_path / f'{index}-arguments.json'
        schema = tmp_path / f'{index}-schema.json'
        payload.write_text(raw)
        schema.write_text(json.dumps(request['schema']))
        candidate = {} if risk != 'frame_header_repair' else {
            'model_max_tokens': 131072,
            'model_params': {'params': {'max_completion_tokens': 131072, 'extra_body': {'thinking': {'type': 'adaptive'}}}},
            'expected_model_params': {'model': 'MiniMax-M3', 'thinking_mode': 'adaptive',
                                      'max_tokens': None, 'max_completion_tokens': 131072}}
        if risk.startswith('m27_'):
            candidate = {
                'model_row': {'id': 'MiniMax-M2.7', 'name': 'offline M2.7', 'reasoning': True,
                              'input': ['text'], 'contextWindow': 204800, 'maxTokens': 65536},
                'model_params': {'params': {'max_completion_tokens': 65536,
                                            'extra_body': {'thinking': {'type': 'adaptive'}}}},
                'expected_model_params': {'model': 'MiniMax-M2.7', 'thinking_mode': 'adaptive',
                                          'max_tokens': None, 'max_completion_tokens': 65536}}
        report = gateway(runtime, tmp_path / f'gateway-{index}', node, payload, schema_path=schema,
                         http_budget=budget, **candidate)
        assert report['capture']['sha256'] == hashlib.sha256(raw.encode()).hexdigest()
        assert report['capture']['schemaSha256'] == request['schemaSha256']
        assert report['terminal']['status'] == 'ok' and len(report['provider_calls']) == 1
        records.append({'transport': 'PASS', 'business_schema': request['schema'].get('title'),
                        'capture': report['capture'], 'provider_submissions': 1})
        return raw  # Exact reader equality is independently asserted inside gateway().
    if risk == 'm27_p3_correction':
        from tests.test_semantic_planning import test_p3_candidate_correction_full_boundary
        from easel.integrations import semantic_boundary_run as owner
        native_run = owner.run
        def run_through_gateway(attempt, context, canonical, mode, route, dispatch):
            def transported(stage, message, session, **options):
                raw = dispatch(stage, message, session, **options)
                return carrier(raw, options['structured_result'])
            return native_run(attempt, context, canonical, mode, route, transported)
        monkeypatch.setattr(owner, 'run', run_through_gateway)
        # Only external answers are fixtures. The original P3 integration
        # asserts joint repair, unchanged siblings, replay and tamper refusal.
        test_p3_candidate_correction_full_boundary(authority_runtime, monkeypatch, 'joint')
    else:
        bounded_review(authority_runtime, monkeypatch,
                       'frame_header_repair' if risk == 'm27_staged_lifecycle' else risk.removeprefix('m27_'),
                       carrier=carrier, two_stage=risk == 'm27_staged_lifecycle')
    assert len(records) == {'real_wrapper': 1, 'real_full_creation2': 1, 'structural_repair': 3, 'repair_invalid': 2, 'xml_roundtrip': 2, 'xml_answer_repair': 3, 'frame_header_repair': 4, 'm27_frame_header_repair': 4, 'm27_staged_lifecycle': 5, 'm27_p3_correction': 5}[risk]
    requests = json.loads(budget.path.read_text())['requests']
    assert len(requests) == len(records)
    assert all(row['provider_finish'] == 'tool_calls' and row['sse_done'] for row in requests)
    if risk == 'frame_header_repair':
        assert all(row['max_completion_tokens'] == 131072 and row['thinking_mode'] == 'adaptive' for row in requests)
    output = Path(os.environ['EASEL_TEST_EVIDENCE'])
    output.mkdir(parents=True, exist_ok=True)
    (output / f'{risk}.json').write_text(json.dumps({'risk': risk, 'result': 'PASS',
        'real_model_calls': 0, 'records': records}, ensure_ascii=False, indent=2) + '\n')


def test_native_phase_aware_output_lifecycle(prep_env, monkeypatch, tmp_path):
    from tests.planning_material_matrix import transport_recovery as transport
    original = transport._HTTPConnection.__init__
    attempted = []
    def with_one_refused_connect(self, *args, **kwargs):
        original(self, *args, **kwargs)
        connect = self._create_connection
        def once(*args, **kwargs):
            attempted.append(True)
            if len(attempted) == 1:
                raise ConnectionRefusedError(61, 'local fixture before HTTP send')
            return connect(*args, **kwargs)
        self._create_connection = once
    monkeypatch.setattr(transport._HTTPConnection, '__init__', with_one_refused_connect)
    test_native_output_admission_lifecycle(prep_env, monkeypatch, tmp_path, phase_aware=True)
    assert len(attempted) == 6



def test_native_sdk_failure_diagnostics(tmp_path):
    """Synthetic transport control through the real SDK; not historical replay."""
    runtime = Path(os.environ['EASEL_TEST_RUNTIME']).resolve()
    assert runtime.parent == Path('/tmp').resolve() and runtime.name.startswith('easel-structured-runtime-')
    from easel.integrations.planning_structured import verify_runtime
    verify_runtime(runtime)
    report = gateway(runtime, tmp_path / 'sdk-failure', shutil.which('node'),
        scenario='sdk_missing_finish',
        model_row={'id': 'MiniMax-M2.7', 'name': 'offline M2.7', 'reasoning': True,
                   'input': ['text'], 'contextWindow': 204800, 'maxTokens': 65536},
        model_params={'params': {'max_completion_tokens': 65536,
                                 'extra_body': {'thinking': {'type': 'adaptive'}}}})
    assert report['terminal']['status'] == 'error'
    assert report['capture']['state'] == 'TOOL_REJECTED'
    assert len(report['provider_calls']) == 1
    assert report['first_rejection']['category'] == 'STRUCTURED_SDK_FINISH_REASON_MISSING'
    assert report['first_rejection']['toolCallCount'] == 1
    assert report['database_and_existing_wal_unchanged']
    report.update(historical_failure_replayed=False,
                  evidence_kind='synthetic-sdk-error-control',
                  local_fixture_http=1, real_model_calls=0)
    output = Path(os.environ['EASEL_TEST_EVIDENCE'])
    output.mkdir(parents=True, exist_ok=True)
    (output / 'native-sdk-failure.json').write_text(json.dumps(report, indent=2) + '\n')

def test_native_output_admission_lifecycle(prep_env, monkeypatch, tmp_path, *, phase_aware=False):
    """Real native capture of the invalid echo, then local normalize + one repair.

    Only the upstream Provider answers and Truth/Preparation are fixtures.
    The existing Owner/Planning/Truth/persist/load boundary is not replaced.
    """
    from tests.test_semantic_planning import test_vnext_confirmed_preset_truth_boundary
    from easel.integrations import semantic_boundary_run as owner
    runtime = Path(os.environ['EASEL_TEST_RUNTIME']).resolve()
    assert runtime.parent == Path('/tmp').resolve() and runtime.name.startswith('easel-structured-runtime-')
    owner.structured.verify_runtime(runtime)
    from tests.planning_material_matrix.transport_recovery import POLICY
    budget = EvalHttpBudget(tmp_path / 'native-admission-http', hashlib.sha256(b'admission-native@1').hexdigest(),
                           transport_policy=POLICY if phase_aware else None)
    records = []
    native_run = owner.run
    def with_native_capture(attempt, context, canonical, mode, route, dispatch):
        def transported(stage, message, session, **options):
            raw = dispatch(stage, message, session, **options)
            index = len(records)
            payload, schema_file = tmp_path / f'admission-{index}.json', tmp_path / f'schema-{index}.json'
            payload.write_text(raw)
            request = options['structured_result']
            schema_file.write_text(json.dumps(request['schema']))
            report = gateway(runtime, tmp_path / f'gateway-admission-{index}', shutil.which('node'),
                payload, schema_path=schema_file, http_budget=budget,
                model_row={'id': 'MiniMax-M2.7', 'name': 'offline M2.7', 'reasoning': True,
                           'input': ['text'], 'contextWindow': 204800, 'maxTokens': 65536},
                model_params={'params': {'max_completion_tokens': 65536,
                    'extra_body': {'thinking': {'type': 'adaptive'}}}},
                expected_model_params={'model': 'MiniMax-M2.7', 'thinking_mode': 'adaptive',
                                       'max_tokens': None, 'max_completion_tokens': 65536})
            assert report['terminal']['status'] == 'ok'
            assert report['capture']['sha256'] == hashlib.sha256(raw.encode()).hexdigest()
            assert report['capture']['schemaSha256'] == request['schemaSha256']
            records.append({'stage': session.rsplit('-vnext-', 1)[-1], 'capture': report['capture']})
            return raw
        return native_run(attempt, context, canonical, mode, route, transported)
    monkeypatch.setattr(owner, 'run', with_native_capture)
    test_vnext_confirmed_preset_truth_boundary(prep_env, monkeypatch, 'music_query_repair', admission_case='joint')
    assert len(records) == 5
    assert [row['stage'] for row in records] == ['A-selection', 'A-details', 'B-000', 'repair', 'B-recheck-000']
    requests = json.loads(budget.path.read_text())['requests']
    if phase_aware:
        assert len(requests) == 6 and requests[0]['state'] == 'NOT_SENT'
        assert requests[1]['connection_retry_of'] == 1
        assert requests[1]['request_sha256'] == requests[0]['request_sha256']
        requests = requests[1:]
        assert all(row['transport']['response_complete'] for row in requests)
    assert len(requests) == 5 and all(row['provider_finish'] == 'tool_calls' for row in requests)
    output = Path(os.environ['EASEL_TEST_EVIDENCE']); output.mkdir(parents=True, exist_ok=True)
    (output / 'native-output-admission.json').write_text(json.dumps({
        'result': 'PASS', 'real_model_calls': 0, 'local_fixture_http': 5,
        'reserved_connection_attempts': 6 if phase_aware else 5, 'phase_aware': phase_aware,
        'schema_echo_preserved_in_capture': True, 'normalization_used_no_model_call': True,
        'records': records}, ensure_ascii=False, indent=2) + '\n')


def test_vnext_owner_actual_free_local_render(prep_env, monkeypatch):
    assert os.environ.get('EASEL_TEST_EVIDENCE'), 'Explicit isolated software evidence directory required'
    preset_chain(prep_env, monkeypatch, 'material_match', native_render=True)


def test_frozen_preparation_replay_new_identity_without_preparation_model(prep_env, monkeypatch):
    preset_chain(prep_env, monkeypatch, 'script_auto_pass', frozen_replay=True)


def test_native_gateway_ordinary_truth_and_report_repair_share_http_guard(tmp_path):
    import threading
    import time
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from tests.planning_material_matrix.structured_gateway import EvalGateway, EvalProviderProxy
    runtime = Path(os.environ['EASEL_TEST_RUNTIME']).resolve()
    assert runtime.parent == Path('/tmp').resolve() and runtime.name.startswith('easel-structured-runtime-')
    inputs = tmp_path / 'eval-runtime'; inputs.mkdir()
    calls = []
    class Provider(BaseHTTPRequestHandler):
        def log_message(self, *_args): pass
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            calls.append(payload)
            if payload['messages'][-1]['role'] == 'tool':
                delta = {'content': 'Saved the requested report.'}; finish = 'stop'
            else:
                tools = {row['function']['name']: row['function'] for row in payload['tools']}
                assert 'write' in tools and not set(tools) & {'exec', 'web_fetch', 'sessions_spawn'}
                properties = tools['write']['parameters']['properties']
                path_key = next(key for key in ('path', 'file_path', 'filePath') if key in properties)
                index = sum(row['messages'][-1]['role'] != 'tool' for row in calls)
                args = {path_key: str(inputs / 'truth-report.json'), 'content': json.dumps({'format_valid': index == 2})}
                delta = {'tool_calls': [{'index': 0, 'id': 'fixture-report-write-' + str(index),
                    'type': 'function', 'function': {'name': 'write', 'arguments': json.dumps(args)}}]}
                finish = 'tool_calls'
            body = ('data: ' + json.dumps({'id': 'truth-fixture', 'choices': [{'index': 0, 'delta': delta,
                'finish_reason': None}]}) + '\n\ndata: ' + json.dumps({'id': 'truth-fixture', 'choices': [
                    {'index': 0, 'delta': {}, 'finish_reason': finish}]}) + '\n\ndata: [DONE]\n\n').encode()
            self.send_response(200); self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
    provider = ThreadingHTTPServer(('127.0.0.1', 0), Provider)
    thread = threading.Thread(target=provider.serve_forever, daemon=True); thread.start()
    budget = EvalHttpBudget(tmp_path / 'http', hashlib.sha256(b'ordinary-truth-fixture').hexdigest())
    proxy = EvalProviderProxy(budget, f'http://127.0.0.1:{provider.server_port}/v1/chat/completions',
        'MiniMax-M3', 'offline-placeholder', offline=True).start()
    native = EvalGateway(runtime, tmp_path / 'gateway', shutil.which('node'), proxy,
        {'id': 'MiniMax-M3', 'name': 'offline', 'reasoning': False, 'input': ['text'],
         'contextWindow': 1000000, 'maxTokens': 8192})
    try:
        native.start()
        for index in range(2):
            run_id = 'truth-budget-' + str(index)
            native.rpc('agent', {'agentId': 'main', 'sessionKey': 'agent:main:' + run_id,
                'sessionId': run_id, 'idempotencyKey': run_id, 'deliver': False, 'timeout': 30,
                'message': 'Write the fixed report.' if index == 0 else 'Repair the report format once.'})
            terminal = native.rpc('agent.wait', {'runId': run_id, 'timeoutMs': 35000})
            assert terminal['status'] == 'ok', terminal
            assert json.loads((inputs / 'truth-report.json').read_text()) == {'format_valid': index == 1}
        rows = json.loads(budget.path.read_text())['requests']
        assert len(calls) == len(rows) == 4
        assert [row['provider_finish'] for row in rows] == ['tool_calls', 'stop', 'tool_calls', 'stop']
        assert all(row['schema_sha256'] is None and row['sse_done'] for row in rows)
    finally:
        native.stop(); proxy.stop(); provider.shutdown(); provider.server_close(); thread.join()


@pytest.mark.parametrize('qualification', [False, True, 'm27', 'engineering'], ids=['contrast', 'qualification', 'm27-qualification', 'engineering'])
def test_native_four_cell_diagnostic_runner(tmp_path, monkeypatch, qualification):
    """Actual runner, isolated confirmations, Gateway/capture and local HTTP."""
    import threading
    from types import SimpleNamespace
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from easel.runtime_config import EaselRuntimeConfig
    from tests.planning_material_matrix import planning_eval_run as runner
    from tests.planning_material_matrix import structured_gateway as gateway_module
    from tests.planning_material_matrix.run import production, protected
    runtime = Path(os.environ['EASEL_TEST_RUNTIME']).resolve()
    assert runtime.parent == Path('/tmp').resolve() and runtime.name.startswith('easel-structured-runtime-')
    source = json.loads(Path(os.environ['EASEL_TEST_CONTRAST_SOURCE']).read_text())
    probes = runner.contrast_probes(source['probes'][0], source['model_params'])
    manifest = {**source, 'schema': 'planning-carrier-contrast@1', 'original_probe': source['probes'][0],
        'fixed_commit': runner.head(), 'fixed_source': production()['sha256'],
        'tool_hashes': runner.tool_hashes(contrast=True), 'protected_files': protected(),
        'samples': [source['samples'][0]], 'probes': probes,
        'limits': {'http': 4, 'seconds': 900, 'per_cell_http': 1}}
    if qualification:
        from copy import deepcopy
        candidate = {'model_row': deepcopy(source['model_rows'][0]), 'model_params': deepcopy(source['model_params'])}
        candidate['model_row']['maxTokens'] = 131072
        candidate['model_params']['params'].update(max_completion_tokens=131072)
        candidate['model_params']['params']['extra_body']['thinking'] = {'type': 'adaptive'}
        manifest.update(schema='planning-qualification-eval@1', samples=source['samples'], probes=[],
                        limits={'http': 40, 'seconds': 2700, 'themes': 3, 'repeats': 2}, candidate=candidate,
                        tool_hashes=runner.tool_hashes())
        if qualification in {'m27', 'engineering'}:
            manifest.update(schema='planning-qualification-eval@2', candidate={
                'model_row': {'id': 'MiniMax-M2.7', 'name': 'MiniMax Token Plan · M2.7',
                    'reasoning': True, 'input': ['text'], 'contextWindow': 204800, 'maxTokens': 65536},
                'model_params': {'params': {'max_completion_tokens': 65536,
                    'extra_body': {'thinking': {'type': 'adaptive'}}}},
            })
    if qualification == 'engineering':
        from tests.planning_material_matrix.transport_recovery import POLICY
        manifest.update(schema=runner.ENGINEERING_SCHEMA, transport_policy=POLICY,
            samples=[source['samples'][0]], limits={'http': 40, 'seconds': 2700, 'themes': 1, 'repeats': 1},
            tool_hashes=runner.tool_hashes(transport_policy=POLICY))
    manifest_path = tmp_path / 'manifest.json'; manifest_path.write_text(json.dumps(manifest))
    directory = tmp_path / 'diagnostic'
    # The runner sees a synthetic account. No actual credential is loaded by it.
    home = tmp_path / 'home'; (home / '.openclaw-easel').mkdir(parents=True)
    config = {'agents': {'defaults': {'thinkingDefault': 'off', 'models': {'minimax/MiniMax-M3': source['model_params']}}},
        'models': {'providers': {'minimax': {'apiKey': 'offline-placeholder', 'models': source['model_rows']}}}}
    (home / '.openclaw-easel/openclaw.json').write_text(json.dumps(config))
    synthetic_config = EaselRuntimeConfig.load(environ={}, env_file=tmp_path / 'missing.env')
    monkeypatch.setattr(EaselRuntimeConfig, 'load', staticmethod(lambda: synthetic_config))
    monkeypatch.setattr(runner, 'model_profile', lambda: json.loads((home / '.openclaw-easel/openclaw.json').read_text()))
    monkeypatch.setattr(runner, 'check_authorized_route', lambda *_: {'kind': 'local-route-fixture'})
    provider_calls = []
    original_proxy = gateway_module.EvalProviderProxy
    class Provider(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            index = len(provider_calls)
            assert 'max_tokens' not in payload
            assert payload['max_completion_tokens'] == (65536 if qualification in {'m27', 'engineering'} else
                                                        131072 if qualification else source['model_rows'][0]['maxTokens'])
            assert payload['model'] == ('MiniMax-M2.7' if qualification in {'m27', 'engineering'} else 'MiniMax-M3')
            provider_calls.append({'thinking': payload['thinking'], 'model': payload['model'],
                                   'max_completion_tokens': payload['max_completion_tokens']})
            if qualification:
                from easel.integrations.planning_wire import FrameProjection
                from easel.integrations.planning_result_contract import semantic_tool_schema
                from tests.test_semantic_planning import supported_fixture_answers, fixture_review_wire
                import re
                text = '\n'.join(str(m.get('content', '')) for m in payload['messages'] if m['role'] == 'user')
                assert payload['thinking'] == {'type': 'adaptive'}
                function = 'submit_semantic_plan'
                if '〔Easel Semantic Planning vNext A-' in text:
                    marker = text.index('〔Easel Semantic Planning vNext A-')
                    context = json.JSONDecoder().raw_decode(text[text.index('{', marker):])[0]
                    value = {'needs': [{'scope': 'global', 'role': '背景', 'modality': 'image', 'necessity': 'required',
                        'conditions': [{'text': '静态生活照片', 'strength': 'required', 'responsibility': 'material'}]}]}
                    if qualification == 'engineering':
                        # The frozen engineering fixture explicitly includes BGM.
                        # This is a fixed reply, not measured model semantics.
                        value['needs'].append({'scope': 'global', 'role': '背景音乐', 'modality': 'bgm',
                            'necessity': 'required', 'conditions': [{'text': '轻柔无歌词背景音乐',
                                'strength': 'required', 'responsibility': 'material'}],
                            'sound': {'vocals_allowed': False}})
                    from tests.test_semantic_planning import staged_fixture_wire
                    stage = text[marker:text.index('〕', marker) + 1]
                    raw = staged_fixture_wire(stage + '\n' + json.dumps(context, ensure_ascii=False), value)
                elif '有界视觉复核' in text:
                    batch = json.JSONDecoder().raw_decode(text[text.index('{', text.index('有界视觉复核')):])[0]
                    answers = supported_fixture_answers(batch, [{'question': q['question'], 'decision': 'ACCEPT',
                        'evidence': [0], 'reason': '外部固定响应；不代表真实语义通过。'} for q in batch['questions']])
                    raw = json.dumps(fixture_review_wire(batch, answers), ensure_ascii=False)
                elif '〔Easel Truth 脚本' in text:
                    if payload['messages'][-1]['role'] == 'tool':
                        raw = None
                    else:
                        report = json.JSONDecoder().raw_decode(text.split('，不增加字段：', 1)[1])[0]
                        if report['script']:
                            for claim in report['script']['decisions']:
                                claim.update(kind='creative_expression', reason='固定外部无事实表达对照。')
                        sources = json.JSONDecoder().raw_decode(text.split('旁白身份来源：', 1)[1])[0]
                        report['voice'] = {'decision': 'MATCH', 'reason': '固定外部身份相容响应。',
                            'sources': [{'ref': k, 'quote': v} for k, v in sources.items()]}
                        target = re.search(r'只写(.+\.json)，不增加字段：', text)[1]
                        function = 'write'
                        tool = next(t['function'] for t in payload['tools'] if t['function']['name'] == function)
                        key = next(k for k in ('path', 'file_path', 'filePath') if k in tool['parameters']['properties'])
                        raw = json.dumps({key: target, 'content': json.dumps(report, ensure_ascii=False)})
                else:
                    raise AssertionError('Unexpected external stage')
            elif index == 0:
                raw = (Path(__file__).parent / 'fixtures/planning-vnext-development-2026-10-08/autonomous-convergence-A-wire.json').read_text()
            else:
                proposal = {'needs': [{'scope': 'event-1', 'role': '背景', 'modality': 'image', 'necessity': 'required',
                    'conditions': [{'text': '一张白纸', 'strength': 'required', 'responsibility': 'material'}]}]}
                raw = json.dumps(runner.contrast_projection(probes[index]).encode(proposal), ensure_ascii=False)
            delta = {'content': 'Saved fixed report.'} if raw is None else {'tool_calls': [{'index': 0,
                'id': f'original-{index}', 'type': 'function', 'function': {
                    'name': function if qualification else 'submit_semantic_plan', 'arguments': raw}}]}
            chunks = [{'choices': [{'delta': delta, 'finish_reason': None}]},
                {'choices': [{'delta': {}, 'finish_reason': 'stop' if raw is None else 'tool_calls'}]}]
            content = ''.join('data: ' + json.dumps(c) + '\n\n' for c in chunks) + 'data: [DONE]\n\n'
            encoded = content.encode()
            self.send_response(200); self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Content-Length', str(len(encoded))); self.end_headers(); self.wfile.write(encoded)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Provider)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    def local_proxy(budget, _upstream, model, key, **kwargs):
        assert key == 'offline-placeholder'
        return original_proxy(budget, f'http://127.0.0.1:{server.server_port}/v1/chat/completions',
                              model, key, offline=True, **kwargs)
    monkeypatch.setattr(gateway_module, 'EvalProviderProxy', local_proxy)
    args = SimpleNamespace(directory=directory, contrast_manifest=manifest_path, convergence_manifest=None,
        fixed_commit=manifest['fixed_commit'], fixed_source=manifest['fixed_source'], one=None)
    if qualification:
        args.contrast_manifest = None
        args.qualification_manifest = None if qualification == 'engineering' else manifest_path
        args.engineering_manifest = manifest_path if qualification == 'engineering' else None
    def invoke():
        if not qualification:
            return runner.convergence_main(args)
        # Match the actual CLI lifecycle: freeze and EACH execution use a new
        # interpreter. A warm pytest process can conceal import-time guards.
        import subprocess, sys
        child = '''
import sys,json
from pathlib import Path
from types import SimpleNamespace
from easel.runtime_config import EaselRuntimeConfig
from tests.planning_material_matrix import planning_eval_run as runner
from tests.planning_material_matrix import structured_gateway as gateway
config=json.loads(Path(sys.argv[1]).read_text())
synthetic=EaselRuntimeConfig.load(environ={},env_file=Path(sys.argv[1]).parent/'missing.env')
EaselRuntimeConfig.load=staticmethod(lambda:synthetic)
runner.model_profile=lambda:config
runner.check_authorized_route=lambda *_:{'kind':'local-route-fixture'}
original=gateway.EvalProviderProxy
def local_proxy(budget,_upstream,model,key,**kwargs):
 assert key=='offline-placeholder'
 return original(budget,sys.argv[2],model,key,offline=True,**kwargs)
gateway.EvalProviderProxy=local_proxy
value=json.loads(sys.argv[3])
for key in ('directory','qualification_manifest','engineering_manifest'):
 if value.get(key) is not None: value[key]=Path(value[key])
raise SystemExit(runner.convergence_main(SimpleNamespace(**value)))
'''
        value={k:str(v) if isinstance(v,Path) else v for k,v in vars(args).items()}
        proc=subprocess.run([sys.executable,'-c',child,str(home/'.openclaw-easel/openclaw.json'),
            f'http://127.0.0.1:{server.server_port}/v1/chat/completions',json.dumps(value)],
            cwd=runner.ROOT,capture_output=True,text=True,timeout=660)
        assert proc.returncode==0, proc.stdout + proc.stderr
        return proc.returncode
    try:
        assert invoke() == 0
        assert not provider_calls
        for i in range(1 if qualification == 'engineering' else 6 if qualification else 4):
            args.one = i
            assert invoke() == 0
            if qualification:
                runner.record_convergence_review(directory, manifest_path, i, 'PASS',
                    {'kind': 'offline execution test only; fixed judgments are NOT real semantic evidence'})
                budget = json.loads((directory / 'actual-http/http-budget.json').read_text())
                assert budget['closed'] == (i == (0 if qualification == 'engineering' else 5))
            else: assert len(provider_calls) == i + 1
        count = len(provider_calls)
        assert invoke() == 0  # Completed cell cannot submit again.
        assert len(provider_calls) == count
        if qualification:
            roster = json.loads((directory / 'roster.json').read_text())['runs']
            assert [r['sample'] for r in roster] == ([0] if qualification == 'engineering' else [0, 0, 1, 1, 2, 2])
            assert len({r['creation_id'] for r in roster}) == (1 if qualification == 'engineering' else 6)
            if qualification == 'engineering':
                result = json.loads((directory / 'runs/run-00.json').read_text())
                assert result['formal_qualification'] is False and result['production_dispatch_allowed'] is False
                assert result['supply_calls'] == 0 and result['state_violations'] == []
            assert budget['close_reason'] == 'BATCH_COMPLETE'
            assert len(budget['requests']) == count
            assert all(r['max_completion_tokens'] == (65536 if qualification in {'m27', 'engineering'} else 131072)
                       and r['thinking_mode'] == 'adaptive' for r in budget['requests'])
            assert production()['sha256'] == manifest['fixed_source'] and protected() == manifest['protected_files']
            output = Path(os.environ['EASEL_TEST_EVIDENCE']); output.mkdir(exist_ok=True, parents=True)
            (output / ('m27-qualification-runner.json' if qualification in {'m27', 'engineering'} else 'qualification-runner.json')).write_text(json.dumps({'result': 'PASS', 'real_model_calls': 0,
                'local_provider_calls': count, 'roster': [r['sample'] for r in roster], 'semantic_quality': 'NOT_TESTED',
                'production_and_protected_unchanged': True}))
            return
        assert len(provider_calls) == 4
        rows = [json.loads((directory / f'runs/run-{i:02}.json').read_text()) for i in range(4)]
        assert [row['result'] for row in rows] == ['OBSERVED_CONTRACT_REJECT', *(['OBSERVED_CONTRACT_ACCEPT'] * 3)]
        assert [row['thinking'] for row in rows] == ['disabled', 'disabled', 'adaptive', 'adaptive']
        assert all(row['supply_calls'] == 0 and row['formal_product_admission'] is False for row in rows)
        budget = json.loads((directory / 'actual-http/http-budget.json').read_text())
        assert budget['closed'] and budget['close_reason'] == 'BATCH_COMPLETE' and len(budget['requests']) == 4
        assert all(r['max_tokens_present'] is False and r['max_tokens_type'] == 'absent'
                   and r['max_completion_tokens_present'] is True and r['max_completion_tokens_type'] == 'integer'
                   and r['max_completion_tokens'] == source['model_rows'][0]['maxTokens']
                   for r in budget['requests'])
        assert production()['sha256'] == manifest['fixed_source'] and protected() == manifest['protected_files']
        report = {'result': 'PASS', 'real_model_calls': 0, 'local_provider_calls': 4,
                  'rows': [{k: row[k] for k in ('result', 'thinking', 'representation', 'transport', 'contract')} for row in rows],
                  'formal_product_admission': False, 'production_and_protected_unchanged': True}
        output = Path(os.environ['EASEL_TEST_EVIDENCE']); output.mkdir(exist_ok=True, parents=True)
        (output / 'four-cell-runner.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        server.shutdown(); server.server_close(); thread.join()
