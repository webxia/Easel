"""Independent semantic oracle and native Planning v3 integration regressions."""
from pathlib import Path
import json
import pytest
from easel.materials.domain import MaterialPlan
from easel.materials.application.visual_contract import planning_contracts

FIXTURE = Path(__file__).parent / 'fixtures/planning-semantic-contract-2026-10-07'

def _r4_current_truth_reply(message, *, reject=False):
    """Create a real source-ref file-json result using only the frozen prompt.

    This simulates the model only; Easel owns SourceUnit extraction, original
    receipt capture, source IDs and persisted Truth/voice judgment validation.
    """
    import re
    assert message.startswith('〔Easel Truth 来源引用审阅〕')
    report = json.loads(message.split('写后停止：\n', 1)[1].split('\n前份报告', 1)[0])
    context = json.loads(message.split('\n旁白独立上下文：', 1)[1].split('\n只写 ', 1)[0])
    # Source-ref with no bound preset voice is a bare SCRIPT decision map,
    # whereas voice-bound requests wrap it under a separate 'script' key.
    body = report.get('script') if 'script' in report else report
    if body:
        for row in body['decisions'].values():
            row.update(kind='unresolved' if reject else 'creative_expression',
                       reason='冻结声明缺少证据' if reject else '独立固定创作表达无新事实')
    if report.get('voice') is not None:
        report['voice'] = {'decision': 'MATCH',
                           'reason': '冻结官方身份与全部实际声源控制对应',
                           'sources': [{'ref': key, 'quote': quote}
                                       for key, quote in context['sources'].items()]}
    target = Path(re.search(r'只写 (.+?\.json)，按以下固定结构', message)[1])
    target.write_text(json.dumps(report, ensure_ascii=False))
    return target



def test_real_fourth_failure_replays_before_any_supply():
    plan = MaterialPlan.model_validate_json((FIXTURE / 'MATERIAL_PLAN.json').read_text())
    raw = json.loads((FIXTURE / 'MATERIAL_REQUIREMENTS.json').read_text())
    with pytest.raises(ValueError, match='原文路径无效'):
        planning_contracts(plan, {}, raw)
    repair = json.loads((FIXTURE / 'repair.json').read_text())
    assert 'needs.9.modality_spec.voice:value_error' in repair['message']
    assert 'constraints/subtitle_overlay_only' not in repair['message']


def test_r4_frozen_samples_are_legal_normal_proposals(prep_env):
    from tests.planning_material_matrix.planning_eval import confirm_sample
    import hashlib
    payload = json.loads((Path(__file__).parent / 'fixtures/planning-eval-r4-2026-10-07/samples.json').read_text())
    assert len(payload['samples']) == 16 and payload['runs_per_theme'] == 2
    assert [s['split'] for s in payload['samples']].count('held_out') == 8
    identities = []
    for sample in payload['samples']:
        for _ in range(2):
            work = confirm_sample(sample)
            plan = work['delivery']['video_plan']
            assert plan['schema'] == 'easel-video-proposal@2'
            assert hashlib.sha256(plan['script'].encode()).hexdigest() == sample['expected_script_sha256']
            assert work['chat_workflow']['proposal_status'] == 'CONFIRMED'
            assert not work.get('hypit_attempts') and not work['delivery'].get('generation_budget')
            identities.append(work['id'])
    assert len(set(identities)) == 32


def test_r4_validator_child_uses_isolated_root(prep_env, tmp_path):
    import os, subprocess, sys
    from tests.test_creation_preparation import web, prep, creation, write_drafts
    from tests.planning_material_matrix.planning_eval import confirm_sample, isolated_process
    sample = json.loads((Path(__file__).parent / 'fixtures/planning-eval-r4-2026-10-07/samples.json').read_text())['samples'][0]
    root = tmp_path / 'eval-storage'
    with isolated_process(root, web):
        work = confirm_sample(sample)
        claim = prep.claim_chat_preparation(work['id'], 'validator-test', 'confirmed')
        draft = prep.preparation_paths(work['id'], claim['operation_key'])['draft']
        write_drafts(work, draft)
        context = web.preparation_agent_context(work, claim)
        assert 'EASEL_PLANNING_EVAL_ROOT=' in context
        env = {**os.environ, 'EASEL_PLANNING_EVAL_ROOT': str(root),
               'PYTHONPATH': str(root / 'validator-bootstrap') + os.pathsep + str(creation.PROJECT_ROOT)}
        result = subprocess.run([sys.executable, '-m', 'easel.creation_preparation', '--validate-draft',
            work['id'], claim['operation_key']], cwd=creation.PROJECT_ROOT, env=env,
            capture_output=True, text=True, timeout=20)
        assert result.returncode == 0, result.stderr
        assert not (creation.PROJECT_ROOT / 'outputs/_creations' / work['id']).exists()


@pytest.mark.parametrize('risk', ['skip_predecessors', 'tool_drift', 'scene_drift',
    'quota_unknown', 'quota_low', 'end_scene_drift', 'credential_changed',
    'route_changed', 'missing_key', 'cash_fallback'])
def test_r4_runner_preflight_refuses_unsafe_submission(prep_env, tmp_path, monkeypatch, risk):
    import hashlib, re, sys, urllib.request
    from tests.planning_material_matrix import planning_eval_run as runner
    # This archived Formal R4 protocol remains @7, not a vNext evaluation.
    monkeypatch.setattr(runner.web, 'PLANNING_COMPILER_POLICY', 'semantic-planning-compiler@7')
    directory = tmp_path / 'protected-eval'
    current_scene = {'old-scene': 'original-sha'}
    current_tools = {'runner': 'frozen-sha'}
    # Only external model/config facts are fixtures. The native runner must
    # finish without querying account quota, while keeping local identity gates.
    monkeypatch.setattr(runner, 'production', lambda: {'sha256': runner.SOURCE})
    monkeypatch.setattr(runner, 'protected', lambda: dict(current_scene))
    monkeypatch.setattr(runner, 'tool_hashes', lambda: dict(current_tools))
    monkeypatch.setattr(runner, 'head', lambda: runner.COMMIT)
    monkeypatch.setattr(sys, 'argv', ['eval', '--directory', str(directory)])
    assert runner.main() == 0
    (directory / 'user-authorization.json').write_text(json.dumps({'raw_stream_exception_accepted': True,
        'billing_scope': 'existing purchased text subscription quota only'}))
    if risk == 'tool_drift': current_tools['runner'] = 'changed-sha'
    if risk == 'scene_drift': current_scene['old-scene'] = 'changed-sha'
    key = 'fixture-credential-never-real'
    home = tmp_path / 'quota-home'; (home / '.openclaw-easel').mkdir(parents=True)
    monkeypatch.setenv('HOME', str(home))
    (home / '.openclaw-easel/openclaw.json').write_text(json.dumps({'agents': {'defaults': {'model': {
        'primary': 'minimax/MiniMax-M3', 'fallbacks': []}}}, 'models': {'providers': {'minimax': {
        'baseUrl': 'https://api.minimax.cn/v1', 'apiKey': key}}}}))
    (directory / 'subscription-quota-readonly.json').write_text(json.dumps({'credential_fingerprint': hashlib.sha256(key.encode()).hexdigest()}))
    profile_path = home / '.openclaw-easel/openclaw.json'
    configured = json.loads(profile_path.read_text())
    if risk == 'credential_changed': configured['models']['providers']['minimax']['apiKey'] = 'different-fixture-credential'
    if risk == 'route_changed': configured['models']['providers']['minimax']['baseUrl'] = 'https://unapproved.invalid/v1'
    if risk == 'missing_key': configured['models']['providers']['minimax']['apiKey'] = ''
    if risk == 'cash_fallback': configured['agents']['defaults']['model']['fallbacks'] = ['unapproved-paid-model']
    profile_path.write_text(json.dumps(configured))
    # Even an archived low balance must not gate new execution. No remote
    # balance request is allowed in either the success or the refusal paths.
    if risk == 'quota_low':
        snapshot = directory / 'quota-checks' / 'historical.json'
        snapshot.parent.mkdir()
        snapshot.write_text(json.dumps({'quota': [{'current_interval_remaining_percent': 0,
            'current_weekly_remaining_percent': 0}]}))
    quota_files_before = {str(p): p.read_bytes() for p in (directory / 'quota-checks').glob('*.json')}
    network_calls = []
    def no_quota_network(*args, **kwargs):
        network_calls.append(True)
        raise AssertionError('Evaluation must not request remote account quota')
    monkeypatch.setattr(urllib.request, 'urlopen', no_quota_network)
    submissions = []
    def forbidden(*args, **kwargs):
        submissions.append(args)
        if risk not in {'quota_unknown', 'quota_low', 'end_scene_drift'}:
            raise AssertionError('Precheck allowed an unauthorized model submission')
        from tests.test_creation_preparation import prep, creation, write_drafts
        message = args[0]
        work = creation.get_creation(json.loads((directory / 'roster.json').read_text())['runs'][0]['creation_id'])
        if message.startswith('〔Easel Semantic Planning V3〕'):
            Path(re.search(r'只写 (.+\.json)', message)[1]).write_text(json.dumps(semantic_draft()))
        elif message.startswith('〔Easel Planning V3 单元分类〕'):
            request=json.loads(message.splitlines()[-1])
            value=_authority_fixed_response(request) if 'controls' in request else labels()
            Path(re.search(r'只写 (.+\.json)', message)[1]).write_text(json.dumps(value))
        elif message.startswith('〔Easel Truth 来源引用审阅〕'):
            # Current source-ref and Voice Owner: fixed decisions reference
            # frozen source IDs; the fixture does not invent old JSON reviews.
            report = json.loads(message.split('写后停止：\n', 1)[1])
            context = json.loads(message.split('\n旁白独立上下文：', 1)[1].split('\n只写 ', 1)[0])
            script_decisions = (report.get('script') if 'script' in report else report)
            if script_decisions:
                for row in script_decisions['decisions'].values():
                    row.update(kind='creative_expression', reason='固定样例不引入外部事实')
            if report.get('voice'):
                report['voice'] = {'decision': 'MATCH',
                    'reason': '官方声音身份与冻结执行控制相符',
                    'sources': [{'ref': ref, 'quote': quote} for ref, quote in context['sources'].items()]}
            target = Path(re.search(r'只写 (.+\.json)，按以下固定结构', message)[1])
            target.write_text(json.dumps(report, ensure_ascii=False))
            if risk == 'end_scene_drift':
                current_scene['old-scene'] = 'changed-after-last-model-call'
        elif message.startswith('〔Easel Script 系统审阅〕'):
            target = Path(re.search(r'只写 (.+\.json)，JSON 结构', message)[1])
            response = json.loads(message.split('（逐项替换判断，不增加字段）：\n', 1)[1].split('\n写入后停止。', 1)[0])
            for row in response['decisions']: row.update(kind='creative_expression', reason='fixed non-factual input')
            target.write_text(json.dumps(response))
            # Read-only digest service now reports a changed historical scene.
            if risk == 'end_scene_drift': current_scene['old-scene'] = 'changed-after-last-model-call'
        else:
            write_drafts(work, prep.preparation_paths(work['id'], work['preparation']['operation_key'])['draft'])
        return 'external fixture complete'
    monkeypatch.setattr(runner.web, 'run_agent_sync', forbidden)
    monkeypatch.setattr(sys, 'argv', ['eval', '--directory', str(directory), '--one', '31' if risk == 'skip_predecessors' else '0'])
    if risk in {'quota_unknown', 'quota_low'}:
        assert runner.main() == 0
        result = json.loads((directory / 'runs/run-00.json').read_text())
        assert result['result'] == 'CONTRACT_VALID_SEMANTICS_PENDING'
        assert result['boundary_reached'] and result['supply_calls'] == 0
        assert result['historical_scene_unchanged'] is True
    elif risk in {'credential_changed', 'route_changed', 'missing_key', 'cash_fallback', 'end_scene_drift'}:
        assert runner.main() == 2
        result = json.loads((directory / 'runs/run-00.json').read_text())
        assert result['result'] == 'FAIL'
        if risk == 'end_scene_drift':
            assert result['boundary_reached'] and result['historical_scene_unchanged'] is False
            assert result['supply_calls'] == 0
            monkeypatch.setattr(sys, 'argv', ['eval', '--directory', str(directory), '--one', '1'])
            with pytest.raises(runner.EvalStateViolation): runner.main()
        else:
            assert result['phase_invocations'] == []
    else:
        with pytest.raises(runner.EvalStateViolation): runner.main()
    assert bool(submissions) == (risk in {'quota_unknown', 'quota_low', 'end_scene_drift'})
    assert network_calls == []
    assert {str(p): p.read_bytes() for p in (directory / 'quota-checks').glob('*.json')} == quota_files_before

@pytest.mark.parametrize('risk', ['success', 'truth_reject', 'repair_failed', 'uncertain'])
def test_r4_native_eval_stops_before_supply(prep_env, monkeypatch, risk):
    import asyncio, re
    from tests.test_creation_preparation import web, prep, creation, write_drafts
    monkeypatch.setattr(web, 'PLANNING_COMPILER_POLICY', 'semantic-planning-compiler@7')
    from tests.planning_material_matrix.planning_eval import confirm_sample, PlanningEvalBoundary
    from easel.creation_delivery import DeliveryExecutionUncertain
    from easel.integrations.material_layer import PlanningIntegration
    sample = json.loads((Path(__file__).parent / 'fixtures/planning-eval-r4-2026-10-07/samples.json').read_text())['samples'][0]
    work = confirm_sample(sample)
    calls = []
    injected_uncertain = False
    def gateway(message, _timeout=None, session=None, **kwargs):
        nonlocal injected_uncertain
        if message.startswith('〔Easel Semantic Planning V3〕'):
            calls.append(('A', session))
            if risk == 'uncertain' and not injected_uncertain:
                injected_uncertain = True
                raise DeliveryExecutionUncertain('fixture transport unknown; original session must resume')
            target = Path(re.search(r'只写 (.+\.json)', message)[1])
            output = semantic_draft()
            if risk == 'repair_failed': output['needs'][0]['modality_spec']['kind'] = 'unknown'
            target.write_text(json.dumps(output))
        elif message.startswith('〔Easel Planning V3 单元分类〕'):
            calls.append(('B', session))
            target = Path(re.search(r'只写 (.+\.json)', message)[1])
            request=json.loads(message.splitlines()[-1])
            value=_authority_fixed_response(request) if 'controls' in request else labels()
            target.write_text(json.dumps(value))
        elif message.startswith('〔Easel Planning V3 单次语义合同修正〕'):
            calls.append(('repair', session))
            request = json.loads(message.splitlines()[-1])
            target = Path(request['output_paths'][request['targets'][0]])
            output = semantic_draft(); output['needs'][0]['modality_spec']['kind'] = 'unknown'
            target.write_text(json.dumps(output))
        elif message.startswith('〔Easel Truth 来源引用审阅〕'):
            calls.append(('Truth', session))
            _r4_current_truth_reply(message, reject=risk == 'truth_reject')
        elif message.startswith('〔Easel Script 系统审阅〕'):
            calls.append(('Truth', session))
            target = Path(re.search(r'只写 (.+\.json)，JSON 结构', message)[1])
            response = json.loads(message.split('（逐项替换判断，不增加字段）：\n', 1)[1].split('\n写入后停止。', 1)[0])
            for row in response['decisions']:
                row.update(kind='unresolved' if risk == 'truth_reject' else 'creative_expression',
                           reason='independent fixture rejection' if risk == 'truth_reject' else 'known creative expression fixture')
            target.write_text(json.dumps(response))
        else:
            calls.append(('Preparation', session))
            assert 'CONFIRMED_PROPOSAL_SHA256=' in message, message[:80]
            current = creation.get_creation(work['id'])
            paths = prep.preparation_paths(work['id'], current['preparation']['operation_key'])
            write_drafts(current, paths['draft'])
        return 'fixed external fixture'
    monkeypatch.setattr(web, 'run_agent_sync', gateway)
    monkeypatch.setattr(web, '_hypit_runtime_profile', lambda: None)
    boundary = PlanningEvalBoundary()
    # The second invocation deliberately reuses the event loop/executor: trace
    # protection must survive endpoint exception and pool-thread reuse.
    async def scenario():
        first = await boundary.advance(work['id'], web)
        if risk == 'uncertain':
            assert not first['boundary_reached']
            second = await boundary.advance(work['id'], web)
            # This external fixture has no durable Gateway reconciliation
            # result: Owner must remain unknown rather than resubmit. The
            # real adapter's same-run RPC recovery is a separate existing test.
            assert not second['boundary_reached']
            a_sessions = [sid for stage, sid in calls if stage == 'A']
            assert len(a_sessions) == 1
        elif risk == 'success':
            assert first['boundary_reached'] and first['owner_advanced'], (first, creation.get_creation(work['id']).get('delivery', {}).get('last_error'), calls)
            assert first['native_next_operation'] == 'prepare'
            count = len(calls)
            second = await boundary.advance(work['id'], web)
            assert second['boundary_reached'] and len(calls) == count
        else:
            assert not first['boundary_reached']
    asyncio.run(scenario())
    assert boundary.supply_calls == 0 and not boundary.state_violations
    if risk == 'success':
        attempt = creation.get_creation(work['id'])['hypit_attempts'][-1]
        loaded = PlanningIntegration().load(attempt)
        assert loaded['truth_ledger']['status'] == 'PASSED'
        assert json.loads((Path(attempt['workspace']['path']) / 'planning/manifest.json').read_text())['schema'] == 'easel-material-planning@3'
        assert not attempt.get('material_gate') and not attempt.get('production_authoring')
        assert (Path(attempt['workspace']['path']) / 'planning/SCRIPT.md').read_bytes() == work['delivery']['video_plan']['script'].encode()
    if risk == 'repair_failed': assert [stage for stage, _ in calls].count('repair') == 1


@pytest.mark.parametrize('risk', ['accepted', 'wait_timeout', 'release_pending', 'restart', 'lost', 'terminal_error', 'repair_A', 'repair_B'])
def test_r4_native_async_owner_checkpoints(prep_env, monkeypatch, risk, evidence=None):
    from tests.test_creation_preparation import web
    monkeypatch.setattr(web, 'PLANNING_COMPILER_POLICY', 'semantic-planning-compiler@7')
    import asyncio, re, subprocess
    from tests.test_creation_preparation import web, prep, creation, write_drafts
    from tests.planning_material_matrix.planning_eval import confirm_sample, PlanningEvalBoundary
    from tests.planning_material_matrix.planning_eval_run import drain_checkpoints, classify_checkpoint
    from easel.integrations import openclaw_delivery as gateway
    sample = json.loads((Path(__file__).parent / 'fixtures/planning-eval-r4-2026-10-07/samples.json').read_text())['samples'][0]
    work = confirm_sample(sample)
    runs, methods, snapshots = {}, [], []
    default_cwd = prep_env['tmp'] / 'gateway-default-workspace'
    default_cwd.mkdir()
    output_paths = []
    mismatch = []
    class ObservedBoundary(PlanningEvalBoundary):
        def trace(self, frame, event, arg):
            # Read-only evidence at the actual native rejection; do not
            # substitute a validator, request or production function.
            if (event == 'call' and frame.f_globals.get('__name__') == 'easel.integrations.semantic_planning'
                    and frame.f_code.co_name == 'problem' and frame.f_locals.get('field') == 'request'):
                caller = frame.f_back
                saved = caller.f_locals.get('record', {})
                incoming = caller.f_locals.get('message', '')
                if saved.get('message') and incoming:
                    import hashlib
                    mismatch.append(('request_text_sha256', hashlib.sha256(saved['message'].encode()).hexdigest(),
                                     hashlib.sha256(incoming.encode()).hexdigest()))
                    left, right = json.loads(saved['message'].splitlines()[-1]), json.loads(incoming.splitlines()[-1])
                    def differences(a, b, path=''):
                        if isinstance(a, dict) and isinstance(b, dict):
                            if list(a) != list(b): mismatch.append((path, list(a), list(b)))
                            for k in a.keys() & b.keys(): differences(a[k], b[k], path + '/' + k)
                        elif a != b: mismatch.append((path, a, b))
                    differences(left, right)
                    mismatch.insert(0, ('semantic_payload_equal', left == right))
            return super().trace(frame, event, arg)
    uncertain_once = False
    def write_response(message):
        if message.startswith('〔Easel Semantic Planning V3〕'):
            target = Path(re.search(r'只写 (.+\.json)', message)[1])
            value = semantic_draft()
            if risk == 'repair_A': value['policy'] = {'invalid_bool': True}
            target.write_text(json.dumps(value)); output_paths.append(target)
        elif message.startswith('〔Easel Planning V3 单元分类〕'):
            target = Path(re.search(r'只写 (.+\.json)', message)[1])
            request = json.loads(message.splitlines()[-1])
            value = _authority_fixed_response(request) if 'controls' in request else _classification_fixture_from_schema(request['output_schema'])
            if risk == 'repair_B': value['classifications'][0]['kind'] = 'narrative_or_postproduction'
            target.write_text(json.dumps(value)); output_paths.append(target)
        elif message.startswith('〔Easel Planning V3 单次语义合同修正〕'):
            request = json.loads(message.splitlines()[-1])
            # A fresh external session knows only the actual request and its
            # default cwd. No Creation lookup or hidden Attempt/root binding.
            name = request['targets'][0]
            target = Path(request.get('output_paths', {}).get(name, name))
            if not target.is_absolute(): target = default_cwd / target
            value = semantic_draft() if risk == 'repair_A' else (
                {'batches':[{'index':b['index'],**_authority_fixed_response(b)} for b in request['context']['batches']]}
                if 'controls' in request['context']['batches'][0] else _classification_fixture_from_schema(request['context']['response_schema']))
            target.write_text(json.dumps(value)); output_paths.append(target)
        elif message.startswith('〔Easel Truth 来源引用审阅〕'):
            output_paths.append(_r4_current_truth_reply(message))
        elif message.startswith('〔Easel Script 系统审阅〕'):
            target = Path(re.search(r'只写 (.+\.json)，JSON 结构', message)[1])
            value = json.loads(message.split('（逐项替换判断，不增加字段）：\n', 1)[1].split('\n写入后停止。', 1)[0])
            for item in value['decisions']: item.update(kind='creative_expression', reason='known creative fixture')
            target.write_text(json.dumps(value))
        else:
            current = creation.get_creation(work['id'])
            write_drafts(current, prep.preparation_paths(work['id'], current['preparation']['operation_key'])['draft'])
    def transport(command, **kwargs):
        nonlocal uncertain_once
        method = command[command.index('call') + 1]
        params = json.loads(command[command.index('--params') + 1])
        methods.append((method, params))
        if method == 'agent':
            run_id = params['idempotencyKey']
            assert run_id not in runs
            runs[run_id] = {'request': params, 'waits': 0}
            payload = {'runId': run_id, 'status': 'accepted'}
        elif method == 'agent.wait':
            run_id = params['runId']; original = runs[run_id]; original['waits'] += 1
            assert params == {'runId': run_id, 'timeoutMs': 0}
            if risk == 'wait_timeout' and not uncertain_once:
                uncertain_once = True; raise subprocess.TimeoutExpired(command, 20)
            if risk == 'lost':
                payload = {'runId': run_id, 'status': 'lost'}
            elif original['waits'] == 1:
                payload = {'runId': run_id, 'status': 'pending'}
            elif risk == 'terminal_error':
                payload = {'runId': run_id, 'status': 'error', 'endedAt': 1000, 'error': 'fixture terminal failure'}
            else:
                write_response(original['request']['message'])
                payload = {'runId': run_id, 'status': 'ok', 'endedAt': 1000}
        else:
            assert method == 'sessions.abort'
            assert any(r['request']['sessionKey'] == params['key'] and r['waits'] > 1 for r in runs.values())
            if risk == 'release_pending' and not uncertain_once:
                uncertain_once = True; raise subprocess.TimeoutExpired(command, 20)
            payload = {'ok': True, 'status': 'no-active-run'}
        return subprocess.CompletedProcess(command, 0, json.dumps(payload), '')
    native_rpc = gateway._rpc
    monkeypatch.setattr(gateway, '_rpc', lambda prefix, profile, method, params, _runner, kwargs:
        native_rpc(prefix, profile, method, params, transport, kwargs))
    def external_agent(message, timeout=None, session_id=None, **kwargs):
        command = ['openclaw', '--profile', web.OPENCLAW_PROFILE, 'agent', '--agent', 'main',
                   '--session-key', 'agent:main:' + session_id, '--thinking', 'off',
                   '--timeout', str(timeout or 60), '--message', message]
        return gateway.run_delivery_agent(command, retry_failed=kwargs.get('retry_failed', True)).stdout
    monkeypatch.setattr(web, 'run_agent_sync', external_agent)
    monkeypatch.setattr(web, '_hypit_runtime_profile', lambda: None)
    def checkpoint(state, current, result):
        snapshots.append((result, state, current['delivery'].get('agent_calls', {})))
        if any(c.get('status') == 'pending' for c in snapshots[-1][2].values()):
            assert result == 'UNKNOWN_OR_PENDING'
    async def scenario():
        boundary = ObservedBoundary()
        if risk == 'restart':
            state = await boundary.advance(work['id'], web)
            current = creation.get_creation(work['id'])
            assert classify_checkpoint(state, current) == 'UNKNOWN_OR_PENDING'
            original = {k: (c['run_id'], c['request_sha256']) for k, c in current['delivery']['agent_calls'].items()}
            boundary = ObservedBoundary()  # new client, durable Owner unchanged
        state, current, result = await drain_checkpoints(boundary, work['id'], web, checkpoint,
            pause=0, max_seconds=0 if risk == 'lost' else 5)
        if evidence:
            evidence.note('native lifecycle result', result)
            evidence.note('original model submissions', len(runs))
            evidence.note('request identity rejection evidence', mismatch)
            evidence.note('native checkpoints', [item[0] for item in snapshots])
            evidence.note('RPC methods', [method for method, _ in methods])
            evidence.note('external response destinations', [str(p) for p in output_paths])
        assert boundary.supply_calls == 0 and not boundary.state_violations
        if risk == 'lost':
            assert result == 'INCOMPLETE_RECOVERABLE' and len(runs) == 1
            assert not any(method == 'sessions.abort' for method, _ in methods)
        elif risk == 'terminal_error':
            assert result == 'FAIL' and len(runs) == 1
            before = len(methods)
            await drain_checkpoints(PlanningEvalBoundary(), work['id'], web, checkpoint, pause=0)
            assert len(methods) == before  # known failure cannot refresh Preparation retry
        else:
            expected_calls = 5 if risk in {'repair_A', 'repair_B'} else 4
            assert result == 'CONTRACT_VALID_SEMANTICS_PENDING' and len(runs) == expected_calls, (current['delivery'].get('last_error'), mismatch, [(x[0],x[1]) for x in snapshots[-8:]], list(runs.values())[-1:] )
            calls = current['delivery']['agent_calls']
            assert all(c['status'] == 'ok' and c['runtime_release'] == 'released' for c in calls.values())
            assert set(c['run_id'] for c in calls.values()) == set(runs)
            assert all(c['request_sha256'] == key for key, c in calls.items())
            if risk == 'restart':
                assert original.items() <= {k: (c['run_id'], c['request_sha256']) for k, c in calls.items()}.items()
            assert state['boundary_reached']
            attempt = current['hypit_attempts'][-1]
            from easel.materials.store import AttemptMaterialStore
            recovery = AttemptMaterialStore(Path(attempt['workspace']['path'])).read_recovery_record('semantic-planning-v3')
            assert bool(recovery.get('repair_used')) == (risk in {'repair_A', 'repair_B'})
            assert not list(default_cwd.iterdir())
            if risk in {'repair_A', 'repair_B'}:
                repair_request = next(v['request'] for v in runs.values() if '单次语义合同修正' in v['request']['message'])
                assert repair_request['sessionKey'].endswith('-repair')
                payload = json.loads(repair_request['message'].splitlines()[-1])
                assert Path(payload['attempt_workspace']) == Path(attempt['workspace']['path'])
                assert all(Path(p).parent == Path(attempt['workspace']['path']) / 'planning'
                           and Path(p).name == name for name, p in payload['output_paths'].items())
        assert sum(method == 'agent' for method, _ in methods) == len(runs)
    asyncio.run(scenario())


def semantic_draft():
    # Independent fixed input and expected labels, never derived with sources_for.
    return {'schema': 'semantic-planning-draft@1', 'needs': [{
        'scope': {'type': 'scene', 'ref': 'scene-1'}, 'role': 'visual',
        'intent': {'description': '两张白纸放在桌上。', 'function': '让观众先看问题。'},
        'importance': 'required', 'modality_spec': {'kind': 'image'},
        'constraints': {'preferred_visual_details': '暖光。'},
        'queries': ['white paper desk', 'two sheets table', 'paper documents room']} ]}


@pytest.mark.parametrize('risk', ['history_quotes', 'nested_quotes', 'unclosed_quote',
                                  'apostrophe_dimensions', 'semantic_limit', 'native_confirmed_basis',
                                  'legacy_policy', 'policy_identity_caps'])
def test_semantic_relation_units_and_independent_failure(semantic_runtime, risk, evidence=None):
    """Fixed semantic expectations, never labels generated by the splitter."""
    from easel.materials.application.visual_contract import compilation_input, bind_classifications, validate_compilation
    folder = FIXTURE / 'batch04'
    mode = json.loads((folder / 'mode-original.json').read_text())
    if risk == 'history_quotes':
        draft = (folder / 'A-original.json').read_bytes()
        plan = compile_draft(draft, creation_id='synthetic', attempt_id='synthetic-relation',
            refs={}, mode=mode, script=(folder / 'SCRIPT-original.md').read_text(),
            allowed_refs={'global': {'global'}})
        units = classification_batches(plan, mode)[0]['units']
        quoted = '正文「先看问题，再做决定。」不在图中，'
        assert quoted in [u['text'] for u in units]
        assert len(units) == 8
        if evidence: evidence.note('real quote preserved as one unit', quoted)
    elif risk == 'nested_quotes':
        draft = semantic_draft()
        draft['needs'][0]['intent']['description'] = (
            '两张白纸（纸面空白，无图案）；正文「看到“问题，决定。”再行动」不在图中，后期叠加正文。')
        units = classification_batches(compile_input(draft), {})[0]['units']
        assert [u['text'] for u in units] == [
            '两张白纸（纸面空白，无图案）；', '正文「看到“问题，决定。”再行动」不在图中，',
            '后期叠加正文。', '让观众先看问题。']
        draft['needs'][0]['intent']['description'] = '白纸。正文"A \\"B,C\\" D"不在图中，后期叠加正文。'
        units = classification_batches(compile_input(draft), {})[0]['units']
        assert [u['text'] for u in units] == [
            '白纸。', '正文"A \\"B,C\\" D"不在图中，', '后期叠加正文。', '让观众先看问题。']
    elif risk == 'unclosed_quote':
        draft = semantic_draft()
        draft['needs'][0]['intent']['description'] = '白纸。正文「先看问题，再做决定。'
        with pytest.raises(ValueError, match='配对'):
            classification_batches(compile_input(draft), {})
    elif risk == 'apostrophe_dimensions':
        for description, expected in [
            ('A person\'s desk, a 12" screen, papers.', ["A person's desk,", ' a 12" screen,', ' papers.']),
            ('James’ desk, a 12” screen, papers.', ['James’ desk,', ' a 12” screen,', ' papers.']),
        ]:
            draft = semantic_draft(); draft['needs'][0]['intent']['description'] = description
            units = classification_batches(compile_input(draft), {})[0]['units']
            assert [u['text'] for u in units] == expected + ['让观众先看问题。']
    elif risk == 'semantic_limit':
        # The real old canonical contract is structurally complete but wrong.
        # Replaying it is evidence of the semantic failure, never a rescued run.
        plan = MaterialPlan.model_validate_json((folder / 'Plan-original.json').read_bytes())
        response = json.loads((folder / 'B-original.json').read_text())
        response['queries'] = json.loads((folder / 'Requirements-original.json').read_text())[plan.needs[0].need_id]['queries']
        frozen = compilation_input(plan.needs[0], plan.context_refs, mode)
        compiled = validate_compilation(frozen, bind_classifications(frozen, response))
        actual = next(c['kind'] for c in compiled['clauses'] if c['text'] == '由后期叠加。')
        expected = json.loads((folder / 'expected.json').read_text())['real_incorrect_kind']['expected']
        assert actual == 'required' and expected == 'postproduction' and actual != expected
        if evidence: evidence.note('old real result', {'structure': 'PASS', 'independent_semantics': 'FAIL'})
        new = compile_draft((folder / 'A-original.json').read_bytes(),
            creation_id='synthetic', attempt_id='synthetic-relation', refs={}, mode=mode,
            script=(folder / 'SCRIPT-original.md').read_text(), allowed_refs={'global': {'global'}})
        # Independent new-shape control: all valid IDs, deliberately wrong kind.
        wrong = {'classifications': [
            {'id': 0, 'kind': 'required', 'preference_source': None},
            {'id': 1, 'kind': 'required', 'preference_source': None},
            {'id': 2, 'kind': 'required', 'preference_source': None},
            {'id': 3, 'kind': 'required', 'preference_source': None},
            {'id': 4, 'kind': 'required', 'preference_source': None},
            {'id': 5, 'kind': 'required', 'preference_source': None},
            {'id': 6, 'kind': 'postproduction', 'preference_source': None},
            {'id': 7, 'kind': 'required', 'preference_source': None}]}
        bound = assemble_requirements(new, mode, [wrong])[new.needs[0].need_id]['clauses']
        assert next(c['kind'] for c in bound if c['text'] == '由后期叠加。') != expected
        correct = deepcopy(wrong); correct['classifications'][5]['kind'] = 'postproduction'
        bound = assemble_requirements(new, mode, [correct])[new.needs[0].need_id]['clauses']
        assert next(c['kind'] for c in bound if c['text'] == '由后期叠加。') == expected
        assert next(c['kind'] for c in bound if c['text'] == '正文「先看问题，再做决定。」不在图中，') == 'required'
        if evidence: evidence.note('new IDs / valid shape',
            {'wrong_kind': 'structure PASS, independent semantics FAIL',
             'correct_kind': 'compiler can express postproduction; not live model evidence'})
    elif risk == 'legacy_policy':
        from easel.integrations.semantic_planning import LEGACY_POLICY
        checkpoint = json.loads((folder / 'checkpoint-original.json').read_text())
        scope = checkpoint['scope']
        old = compile_draft(checkpoint['draft'], creation_id=scope['creation_id'],
            attempt_id=scope['attempt_id'], refs=scope['context_refs'], mode=scope['mode'],
            script=scope['canonical']['SCRIPT.md'], allowed_refs=scope['catalog'], compiler_policy=LEGACY_POLICY)
        original = MaterialPlan.model_validate_json((folder / 'Plan-original.json').read_bytes())
        assert old == original
        root = semantic_runtime['root'] / 'legacy-replay'; (root / 'planning').mkdir(parents=True)
        for name, fixture in [('SEMANTIC_CHECKPOINT.json', 'checkpoint-original.json'),
            ('SEMANTIC_PLAN.json', 'A-original.json'), ('MATERIAL_REQUIREMENTS.json', 'Requirements-original.json')]:
            (root / 'planning' / name).write_bytes((folder / fixture).read_bytes())
        for name, text in scope['canonical'].items(): (root / 'planning' / name).write_bytes(text.encode())
        record = verify_semantic_checkpoint(root, original, scope['mode'], scope['canonical']['SCRIPT.md'])
        assert record['policy'] == LEGACY_POLICY
        copied = original.model_copy(update={'creation_id': 'synthetic', 'attempt_id': 'synthetic-copy', 'plan_id': 'synthetic-plan-copy'})
        origin = {k: getattr(original, k) for k in ('creation_id', 'attempt_id', 'plan_id')}
        assert verify_semantic_checkpoint(root, copied, scope['mode'], scope['canonical']['SCRIPT.md'], origin)['origin'] == origin
        corrupted = deepcopy(checkpoint); corrupted['scope']['policy'] = 'semantic-planning-compiler@2'
        (root / 'planning/SEMANTIC_CHECKPOINT.json').write_bytes(encode(corrupted))
        with pytest.raises(ValueError): verify_semantic_checkpoint(root, original, scope['mode'], scope['canonical']['SCRIPT.md'])
        if evidence: evidence.note('real @1 policy replay / copy', 'original Plan identity exactly preserved; conflict rejects')
    elif risk == 'policy_identity_caps':
        from easel.integrations.semantic_planning import LEGACY_POLICY, BASE_POLICY as POLICY
        from easel.materials.application.visual_contract import requirements_cache_key, classification_units
        old = compile_input(compiler_policy=LEGACY_POLICY); new = compile_input()
        assert old.plan_id != new.plan_id and old.needs[0].need_id != new.needs[0].need_id
        assert requirements_cache_key(compilation_input(old.needs[0], old.context_refs, {})) != requirements_cache_key(
            compilation_input(new.needs[0], new.context_refs, {}))
        for unknown in ('unknown', {}, False):
            with pytest.raises(ValueError): compile_input(compiler_policy=unknown)
        with pytest.raises(ValueError): classification_units(compilation_input(new.needs[0], {}, {}), unit_policy='unknown')
        canonical = dict(semantic_runtime['canonical'])
        first = classification_batches(new, {}, canonical=canonical)
        changed = {**canonical, 'SCENES.md': canonical['SCENES.md'] + '字'}
        assert classification_batches(new, {}, canonical=changed)[0]['batch_id'] != first[0]['batch_id']
        assert first[0]['compiler_policy'] == POLICY and first[0]['unit_policy'] == 'indexed-unit-classification@8'
        huge = {**canonical, 'SCENES.md': '字' * (256 * 1024)}
        with pytest.raises(SemanticPlanningError, match='容量'): classification_batches(new, {}, canonical=huge)
        draft = semantic_draft(); draft['needs'][0]['intent']['description'] = '纸。' * 40
        with pytest.raises(ValueError, match='容量|有界'): classification_batches(compile_input(draft), {})
        from easel.materials.store import AttemptMaterialStore
        from easel.integrations.semantic_planning import source_catalog
        rt = semantic_runtime
        state = {'schema': 'semantic-planning-checkpoint@1', 'scope': {
            'policy': LEGACY_POLICY, 'attempt_id': rt['attempt']['attempt_id'],
            'creation_id': rt['attempt']['creation_id'], 'context_refs': rt['context']['context_refs'],
            'canonical': rt['canonical'], 'mode': rt['mode'], 'catalog': source_catalog(rt['canonical'], rt['context'])},
            'route': {'profile': 'fixture-only', 'thinking': 'off', 'timeout': 60},
            'calls': {'A': {'status': 'pending', 'message': 'original legacy request'}}, 'repair_used': False}
        store = AttemptMaterialStore(rt['root']); store.write_recovery_record('semantic-planning-v3', state)
        with pytest.raises(SemanticPlanningError, match='版本'): rt['run']()
        assert store.read_recovery_record('semantic-planning-v3') == state and not rt['calls']
        if evidence: evidence.note('policy/canonical/cache/caps', 'identity isolated; unknown policy and oversized full input refuse')
    else:
        rt = semantic_runtime
        scene = '桌上有两张白纸；正文「先看问题，再做决定。」在后期叠加。'
        rt['canonical']['SCENES.md'] = scene
        write_file(rt['root'], 'SCENES.md', scene.encode(), replace=True)
        requests = []
        def execute(stage, message, session):
            if '单元分类' in message:
                payload = json.loads(message.splitlines()[-1])
                assert payload['confirmed'] == rt['canonical']
                requests.append(message)
            rt['execute'](stage, message, session)
        from easel.integrations.material_layer import PlanningIntegration
        first = rt['run'](execute)
        saved = PlanningIntegration().persist(rt['attempt'],
            **{k: first[k] for k in ('plan', 'script', 'scenes', 'treatment')})
        assert PlanningIntegration().load(saved['attempt'])['plan'] == first['plan']
        assert rt['run'](execute)['plan'] == first['plan'] and len(requests) == 1
        assert len(rt['calls']) == 2
        if evidence: evidence.note('native frozen basis / persist / load / reentry', 'one A + one B, no Supply')


@pytest.mark.parametrize('risk', ['history_review_target', 'observable_contrasts', 'native_target',
                                  'repair_target', 'repair_A_target', 'old_v2_checkpoint', 'target_identity', 'old_v2_pending'])
def test_semantic_review_target_contract(semantic_runtime, risk, evidence=None):
    """Explicit target provenance; offline labels never count as model accuracy."""
    from easel.integrations.semantic_planning import digest, source_catalog, BASE_POLICY as POLICY, REVIEW_TARGET
    from easel.integrations.material_layer import PlanningIntegration
    from easel.materials.store import AttemptMaterialStore
    folder = FIXTURE / 'batch05'
    checkpoint = json.loads((folder / 'checkpoint-original.json').read_text())
    scope = checkpoint['scope']; policy2 = 'semantic-planning-compiler@2'
    draft = (folder / 'A-original.json').read_bytes()
    response = json.loads((folder / 'B-original.json').read_text())
    expected = json.loads((folder / 'expected.json').read_text())
    rt = semantic_runtime
    if risk == 'history_review_target':
        original = MaterialPlan.model_validate_json((folder / 'Plan-original.json').read_bytes())
        bound = assemble_requirements(original, scope['mode'], [response],
            canonical=scope['canonical'], compiler_policy=policy2)
        wrong = next(c for c in bound[original.needs[0].need_id]['clauses']
                     if c['text'] == expected['real_failure']['text'])
        assert wrong['kind'] == expected['real_failure']['actual_kind'] != expected['real_failure']['expected_kind']
        assert bound == json.loads((folder / 'Requirements-original.json').read_text())
        new = compile_draft(draft, creation_id='synthetic', attempt_id='new-target', refs={},
            mode=scope['mode'], script=scope['canonical']['SCRIPT.md'], allowed_refs=scope['catalog'])
        new_bound = assemble_requirements(new, scope['mode'], [response], canonical=scope['canonical'])
        assert next(c['kind'] for c in new_bound[new.needs[0].need_id]['clauses']
                    if c['text'] == expected['real_failure']['text']) != expected['real_failure']['expected_kind']
        if evidence: evidence.note('same-asset/different-narrative counterfactual',
            {'source_exists': True, 'old_and_new_structure': 'PASS', 'independent_semantics': 'FAIL'})
    elif risk == 'observable_contrasts':
        # Same prohibition form, independent hard observable and narrative targets.
        d = semantic_draft(); d['needs'][0]['intent'] = {
            'description': '原图片中不出现可识别公司文字。不虚构作者在这家公司工作过。',
            'function': '承载克制的主观表达。'}
        plan = compile_input(d)
        labels_fixed = {'classifications': [{'id': 0, 'kind': 'required', 'preference_source': None},
            {'id': 1, 'kind': 'postproduction', 'preference_source': None},
            {'id': 2, 'kind': 'postproduction', 'preference_source': None}]}
        clauses = assemble_requirements(plan, {}, [labels_fixed])[plan.needs[0].need_id]['clauses']
        assert [(c['text'], c['kind']) for c in clauses] == [
            ('原图片中不出现可识别公司文字。', 'required'),
            ('不虚构作者在这家公司工作过。', 'postproduction'), ('承载克制的主观表达。', 'postproduction'),
            ('暖光。', 'preference')]
        action = semantic_draft(); action['needs'][0]['intent'] = {
            'description': '白色杯子。', 'function': '杯子在原视频中连续落下。'}
        action['needs'][0]['modality_spec'] = {'kind': 'video'}
        action['needs'][0]['constraints'] = {'requires_dynamic_action': True}
        video = compile_input(action)
        exact = {'classifications': [{'id': 0, 'kind': 'required', 'preference_source': None},
                                     {'id': 1, 'kind': 'required', 'preference_source': None}]}
        c = assemble_requirements(video, {}, [exact])[video.needs[0].need_id]['clauses']
        assert c[1]['text'] == expected['contrasts'][2]['text'] and c[1]['kind'] == 'required'
        bad = deepcopy(exact); bad['classifications'][1]['kind'] = 'postproduction'
        with pytest.raises(SemanticPlanningError, match='源动作'): assemble_requirements(video, {}, [bad])
        if evidence: evidence.note('independent contrast', 'asset text ban required, narrative obligation post; source action in function required')
    elif risk == 'old_v2_checkpoint':
        root = rt['root'] / 'v2-replay'; (root / 'planning').mkdir(parents=True)
        for name, fixture in [('SEMANTIC_CHECKPOINT.json', 'checkpoint-original.json'),
            ('SEMANTIC_PLAN.json', 'A-original.json'), ('MATERIAL_REQUIREMENTS.json', 'Requirements-original.json')]:
            (root / 'planning' / name).write_bytes((folder / fixture).read_bytes())
        for name, text in scope['canonical'].items(): (root / 'planning' / name).write_bytes(text.encode())
        original = MaterialPlan.model_validate_json((folder / 'Plan-original.json').read_bytes())
        assert compile_draft(draft, creation_id=scope['creation_id'], attempt_id=scope['attempt_id'],
            refs=scope['context_refs'], mode=scope['mode'], script=scope['canonical']['SCRIPT.md'],
            allowed_refs=scope['catalog'], compiler_policy=policy2) == original
        assert verify_semantic_checkpoint(root, original, scope['mode'], scope['canonical']['SCRIPT.md'])['policy'] == policy2
        copied = original.model_copy(update={'creation_id': 'synthetic', 'attempt_id': 'copy-v2', 'plan_id': 'copy-plan'})
        origin = {k: getattr(original, k) for k in ('creation_id', 'attempt_id', 'plan_id')}
        assert verify_semantic_checkpoint(root, copied, scope['mode'], scope['canonical']['SCRIPT.md'], origin)['origin'] == origin
        (root / 'planning/SCENES.md').write_text(scope['canonical']['SCENES.md'] + '改')
        with pytest.raises(ValueError, match='确认原件'): verify_semantic_checkpoint(root, original, scope['mode'], scope['canonical']['SCRIPT.md'])
        (root / 'planning/SCENES.md').write_text(scope['canonical']['SCENES.md'])
        wrong = deepcopy(checkpoint); wrong['batches_sha256'] = '0' * 64
        (root / 'planning/SEMANTIC_CHECKPOINT.json').write_bytes(encode(wrong))
        with pytest.raises(ValueError, match='单元摘要'): verify_semantic_checkpoint(root, original, scope['mode'], scope['canonical']['SCRIPT.md'])
    elif risk == 'target_identity':
        old = compile_input(compiler_policy=policy2)
        new = compile_input(compiler_policy='semantic-planning-compiler@3')
        assert old.plan_id != new.plan_id and old.needs[0].need_id != new.needs[0].need_id
        before = classification_batches(old, {}, canonical=rt['canonical'], compiler_policy=policy2)[0]
        after = classification_batches(new, {}, canonical=rt['canonical'], compiler_policy='semantic-planning-compiler@3')[0]
        assert 'review_target' not in before and after['review_target']['scope'] == 'original_asset'
        assert before['batch_id'] != after['batch_id'] and after['unit_policy'] == 'indexed-unit-classification@8'
    elif risk == 'old_v2_pending':
        state = {'schema': 'semantic-planning-checkpoint@1', 'scope': {
            'policy': policy2, 'attempt_id': rt['attempt']['attempt_id'], 'creation_id': rt['attempt']['creation_id'],
            'context_refs': rt['context']['context_refs'], 'canonical': rt['canonical'], 'mode': rt['mode'],
            'catalog': source_catalog(rt['canonical'], rt['context'])},
            'route': {'profile': 'fixture-only', 'thinking': 'off', 'timeout': 60},
            'calls': {'B0': {'status': 'pending', 'message': 'original v2 request'}}, 'repair_used': True}
        store = AttemptMaterialStore(rt['root']); store.write_recovery_record('semantic-planning-v3', state)
        with pytest.raises(SemanticPlanningError, match='版本'): rt['run']()
        assert not rt['calls'] and store.read_recovery_record('semantic-planning-v3') == state
    else:
        # Real orchestrator receives the historical semantic draft through the
        # external boundary, including the wrong-target sentence unchanged.
        for name, text in scope['canonical'].items():
            rt['canonical'][name] = text; write_file(rt['root'], name, text.encode(), replace=True)
        original = json.loads(draft); fixed = deepcopy(response)
        fixed['classifications'][12]['kind'] = expected['real_failure']['expected_kind']
        requests = []; repairs = []
        def execute(stage, message, session):
            rt['calls'].append({'stage': stage, 'session': session, 'message': message})
            data = json.loads(message.splitlines()[-1])
            if message.startswith('〔Easel Semantic'):
                assert data['review_target']['scope'] == 'original_asset'
                name = 'SEMANTIC_PLAN.json'; out = deepcopy(original)
                if risk == 'repair_A_target': out['unknown'] = 'transport-error'
            elif '单元分类' in message:
                assert data['confirmed'] == rt['canonical']
                assert data['review_target'] == REVIEW_TARGET
                requests.append(data); name = 'CLASSIFICATIONS-000.json'; out = deepcopy(fixed)
                if risk == 'repair_target': out['classifications'][0]['id'] = 99
            else:
                assert data['review_target']['scope'] == 'original_asset'
                repairs.append(session)
                if risk == 'repair_A_target': name = 'SEMANTIC_PLAN.json'; out = original
                else:
                    assert data['context']['batches'][0]['review_target'] == requests[0]['review_target']
                    name = 'CLASSIFICATIONS-REPAIR.json'; out = {'batches': [{'index': 0, **fixed}]}
            target = Path(data['output_paths'][name]) if stage == 'structure_repair' else rt['root'] / 'planning' / name
            target.write_bytes(encode(out))
        first = rt['run'](execute)
        saved = PlanningIntegration().persist(rt['attempt'], **{k: first[k] for k in ('plan', 'script', 'scenes', 'treatment')})
        assert PlanningIntegration().load(saved['attempt'])['plan'] == first['plan']
        contracts = json.loads(read_file(rt['root'], 'MATERIAL_REQUIREMENTS.json'))
        found = next(c for c in contracts[first['plan'].needs[0].need_id]['clauses'] if c['text'] == expected['real_failure']['text'])
        assert found['kind'] == expected['real_failure']['expected_kind']
        assert rt['run'](execute)['plan'] == first['plan'] and len(requests) == 1
        assert len(repairs) == (risk in {'repair_target', 'repair_A_target'})
        checkpoint_new = json.loads(read_file(rt['root'], 'SEMANTIC_CHECKPOINT.json'))
        assert checkpoint_new['policy'] == POLICY
        bad_checkpoint = deepcopy(checkpoint_new); bad_checkpoint['batches_sha256'] = '0' * 64
        write_file(rt['root'], 'SEMANTIC_CHECKPOINT.json', encode(bad_checkpoint), replace=True)
        with pytest.raises(ValueError, match='单元摘要'):
            verify_semantic_checkpoint(rt['root'], first['plan'], rt['mode'], rt['canonical']['SCRIPT.md'])
        if evidence: evidence.note('native target/persist/reentry',
            {'model_boundary': 'fixed independent response, not live model', 'requests': len(rt['calls']), 'Supply': 0})


@pytest.mark.parametrize('risk', ['history_purpose', 'purpose_contrasts', 'native_purpose',
                                  'purpose_repair', 'old_v3_checkpoint', 'purpose_identity', 'old_v3_pending'])
def test_semantic_predicate_purpose_contract(semantic_runtime, risk, evidence=None):
    """Independent source-property oracle; fixed labels do not prove model accuracy."""
    from easel.integrations.semantic_planning import digest, source_catalog
    from easel.integrations.material_layer import PlanningIntegration
    from easel.materials.store import AttemptMaterialStore
    folder = FIXTURE / 'batch06'
    checkpoint = json.loads((folder / 'checkpoint-original.json').read_text())
    scope = checkpoint['scope']; old_policy = 'semantic-planning-compiler@3'
    draft = (folder / 'A-original.json').read_bytes()
    response = json.loads((folder / 'B-original.json').read_text())
    expected = json.loads((folder / 'expected.json').read_text())
    rt = semantic_runtime
    if risk == 'history_purpose':
        original = MaterialPlan.model_validate_json((folder / 'Plan-original.json').read_bytes())
        old = assemble_requirements(original, scope['mode'], [response],
            canonical=scope['canonical'], compiler_policy=old_policy)
        assert old == json.loads((folder / 'Requirements-original.json').read_text())
        wrong = next(c for c in old[original.needs[0].need_id]['clauses'] if c['text'] == expected['real_failure']['text'])
        assert wrong['kind'] == 'postproduction' != expected['real_failure']['expected_kind']
        # The correct duplicated preference is retained, but cannot erase the
        # independent wrong-kind. Neither old nor new Schema guarantees meaning.
        assert any(expected['real_failure']['preference_source_text'] in c['text'] and c['kind'] == 'preference'
                   for c in old[original.needs[0].need_id]['clauses'])
        new = compile_draft(draft, creation_id='synthetic', attempt_id='new-purpose', refs={},
            mode=scope['mode'], script=scope['canonical']['SCRIPT.md'], allowed_refs=scope['catalog'])
        new_bound = assemble_requirements(new, scope['mode'], [response], canonical=scope['canonical'])
        assert next(c['kind'] for c in new_bound[new.needs[0].need_id]['clauses']
                    if c['text'] == expected['real_failure']['text']) == 'postproduction'
        if evidence: evidence.note('actual original wrong-kind replay',
            {'old_and_new_structure': 'PASS', 'independent_semantics': 'FAIL', 'preference_omission': False})
    elif risk == 'purpose_contrasts':
        for row in expected['contrasts']:
            d = semantic_draft(); n = d['needs'][0]
            n['intent'] = {'description': '两张白纸放在桌上。', 'function': row['text']}
            if row['kind'] == 'preference': n['constraints'] = {'preferred_visual_details': row['soft_source']}
            if row['name'] == 'source_action_with_purpose':
                n['modality_spec'] = {'kind': 'video'}
                n['constraints'] = {'requires_dynamic_action': True}
            plan = compile_input(d)
            # Explicit oracle labels, not a text-matching production classifier.
            fixed = {'classifications': [{'id': 0, 'kind': 'required', 'preference_source': None},
                {'id': 1, 'kind': row['kind'], 'preference_source': 0 if row['kind'] == 'preference' else None}]}
            clauses = assemble_requirements(plan, {}, [fixed])[plan.needs[0].need_id]['clauses']
            assert next(c['kind'] for c in clauses if c['text'] == row['text']) == row['kind']
            if row['kind'] == 'preference':
                bad = deepcopy(fixed); bad['classifications'][1]['preference_source'] = None
                with pytest.raises(SemanticPlanningError): assemble_requirements(plan, {}, [bad])
            if row['name'] == 'source_action_with_purpose':
                bad = deepcopy(fixed); bad['classifications'][1]['kind'] = 'postproduction'
                with pytest.raises(SemanticPlanningError, match='源动作'): assemble_requirements(plan, {}, [bad])
        if evidence: evidence.note('independent paired relations', expected['contrasts'])
    elif risk == 'old_v3_checkpoint':
        root = rt['root'] / 'v3-replay'; (root / 'planning').mkdir(parents=True)
        for name, fixture in [('SEMANTIC_CHECKPOINT.json', 'checkpoint-original.json'),
            ('SEMANTIC_PLAN.json', 'A-original.json'), ('MATERIAL_REQUIREMENTS.json', 'Requirements-original.json')]:
            (root / 'planning' / name).write_bytes((folder / fixture).read_bytes())
        for name, text in scope['canonical'].items(): (root / 'planning' / name).write_bytes(text.encode())
        original = MaterialPlan.model_validate_json((folder / 'Plan-original.json').read_bytes())
        assert compile_draft(draft, creation_id=scope['creation_id'], attempt_id=scope['attempt_id'],
            refs=scope['context_refs'], mode=scope['mode'], script=scope['canonical']['SCRIPT.md'],
            allowed_refs=scope['catalog'], compiler_policy=old_policy) == original
        batches = classification_batches(original, scope['mode'], canonical=scope['canonical'], compiler_policy=old_policy)
        actual = json.loads((folder / 'B-request-original.txt').read_text().splitlines()[-1])
        assert json.loads(encode(batches)) == [actual] and digest(batches) == checkpoint['batches_sha256']
        assert verify_semantic_checkpoint(root, original, scope['mode'], scope['canonical']['SCRIPT.md'])['policy'] == old_policy
        copied = original.model_copy(update={'creation_id': 'synthetic', 'attempt_id': 'copy-v3', 'plan_id': 'copy-plan'})
        origin = {k: getattr(original, k) for k in ('creation_id', 'attempt_id', 'plan_id')}
        assert verify_semantic_checkpoint(root, copied, scope['mode'], scope['canonical']['SCRIPT.md'], origin)['origin'] == origin
        bad = deepcopy(checkpoint); bad['batches_sha256'] = '0' * 64
        (root / 'planning/SEMANTIC_CHECKPOINT.json').write_bytes(encode(bad))
        with pytest.raises(ValueError, match='单元摘要'):
            verify_semantic_checkpoint(root, original, scope['mode'], scope['canonical']['SCRIPT.md'])
    elif risk == 'purpose_identity':
        old = compile_input(compiler_policy=old_policy)
        new = compile_input(compiler_policy='semantic-planning-compiler@4')
        assert old.plan_id != new.plan_id and old.needs[0].need_id != new.needs[0].need_id
        before = classification_batches(old, {}, canonical=rt['canonical'], compiler_policy=old_policy)[0]
        after = classification_batches(new, {}, canonical=rt['canonical'], compiler_policy='semantic-planning-compiler@4')[0]
        assert before['review_target']['schema'] == 'material-review-target@1'
        assert after['review_target']['schema'] == 'material-review-target@2'
        assert before['batch_id'] != after['batch_id']
        assert before['unit_policy'] == after['unit_policy'] == 'indexed-unit-classification@8'
    elif risk == 'old_v3_pending':
        state = {'schema': 'semantic-planning-checkpoint@1', 'scope': {
            'policy': old_policy, 'attempt_id': rt['attempt']['attempt_id'], 'creation_id': rt['attempt']['creation_id'],
            'context_refs': rt['context']['context_refs'], 'canonical': rt['canonical'], 'mode': rt['mode'],
            'catalog': source_catalog(rt['canonical'], rt['context'])},
            'route': {'profile': 'fixture-only', 'thinking': 'off', 'timeout': 60},
            'calls': {'B0': {'status': 'pending', 'message': 'original v3 request'}}, 'repair_used': True}
        store = AttemptMaterialStore(rt['root']); store.write_recovery_record('semantic-planning-v3', state)
        with pytest.raises(SemanticPlanningError, match='版本'): rt['run']()
        assert not rt['calls'] and store.read_recovery_record('semantic-planning-v3') == state
    else:
        for name, text in scope['canonical'].items():
            rt['canonical'][name] = text; write_file(rt['root'], name, text.encode(), replace=True)
        original = json.loads(draft); fixed = deepcopy(response)
        fixed['classifications'][5].update(kind='preference', preference_source=1)
        messages = []
        def execute(stage, message, session):
            rt['calls'].append({'stage': stage, 'session': session, 'message': message})
            data = json.loads(message.splitlines()[-1]); messages.append(data)
            from easel.integrations.semantic_planning import REVIEW_TARGET
            assert data['review_target'] == REVIEW_TARGET
            assert data['review_target']['precedence'] == ['predicate_and_purpose', 'target', 'strength', 'kind']
            assert {k: data['review_target']['relation_rules'][k] for k in ('asset_property_with_purpose', 'pure_postproduction', 'mixed_independent_obligations', 'interpretation')} == {
                'asset_property_with_purpose': 'classify_asset_property_by_source_strength',
                'pure_postproduction': 'actual_editing_or_narrative_obligation',
                'mixed_independent_obligations': 'unresolved_if_not_losslessly_classifiable',
                'interpretation': 'semantic_relation_not_word_order_or_keywords'}
            if message.startswith('〔Easel Semantic'):
                name = 'SEMANTIC_PLAN.json'; out = deepcopy(original)
            elif '单元分类' in message:
                assert data['confirmed'] == rt['canonical']
                prefs = next(iter(data['contexts'].values()))['preferences']
                source = next(p['id'] for p in prefs if p['text'] == original['needs'][0]['constraints']['preferred_visual_details'])
                fixed['classifications'][5]['preference_source'] = source
                name = 'CLASSIFICATIONS-000.json'; out = deepcopy(fixed)
                if risk == 'purpose_repair': out['classifications'][0]['id'] = 99
            else:
                assert data['context']['batches'][0]['review_target'] == messages[1]['review_target']
                name = 'CLASSIFICATIONS-REPAIR.json'; out = {'batches': [{'index': 0, **fixed}]}
            target = Path(data['output_paths'][name]) if stage == 'structure_repair' else rt['root'] / 'planning' / name
            target.write_bytes(encode(out))
        first = rt['run'](execute)
        saved = PlanningIntegration().persist(rt['attempt'], **{k: first[k] for k in ('plan', 'script', 'scenes', 'treatment')})
        assert PlanningIntegration().load(saved['attempt'])['plan'] == first['plan']
        clauses = json.loads(read_file(rt['root'], 'MATERIAL_REQUIREMENTS.json'))[first['plan'].needs[0].need_id]['clauses']
        found = next(c for c in clauses if c['text'] == expected['real_failure']['text'])
        assert found['kind'] == expected['real_failure']['expected_kind'] and found['preference_path'] == 'constraints/preferred_visual_details'
        assert rt['run'](execute)['plan'] == first['plan'] and len(messages) == (3 if risk == 'purpose_repair' else 2)
        from easel.integrations.semantic_planning import BASE_POLICY as POLICY
        assert json.loads(read_file(rt['root'], 'SEMANTIC_CHECKPOINT.json'))['policy'] == POLICY
        if evidence: evidence.note('real native persistence / reload / reentry',
            {'external_response': 'independent fixed labels, not model proof', 'submissions': len(messages), 'Supply': 0})


def test_semantic_draft_compiles_identity_and_lossless_independent_contract():
    from easel.integrations.semantic_planning import compile_draft, classification_batches, assemble_requirements
    refs = {'creative_mode_sha256': 'm'}
    plan = compile_draft(semantic_draft(), creation_id='synthetic', attempt_id='synthetic-a',
                         refs=refs, mode={}, script='先看问题。', allowed_refs={'scene': {'scene-1'}})
    assert plan.needs[0].intent.description == '两张白纸放在桌上。'
    assert plan.needs[0].importance.value == 'required'
    batches = classification_batches(plan, {})
    response = {'classifications': [{'id': 0, 'kind': 'required', 'preference_source': None},
                                   {'id': 1, 'kind': 'postproduction', 'preference_source': None}]}
    result = assemble_requirements(plan, {}, [response])
    rows = result[plan.needs[0].need_id]['clauses']
    assert [(r['path'], r['text'], r['kind']) for r in rows] == [
        ('intent/description', '两张白纸放在桌上。', 'required'),
        ('intent/function', '让观众先看问题。', 'postproduction'),
        ('constraints/preferred_visual_details', '暖光。', 'preference')]
    assert len(batches) == 1


from tests.test_creation_preparation import prep_env


def test_semantic_product_owner_reaches_first_supply_and_observation(prep_env, tmp_path, monkeypatch):
    from tests.planning_material_matrix.cases import test_26_semantic_owner_supply
    from tests.planning_material_matrix.conftest import Trace
    from tests.test_creation_preparation import web
    monkeypatch.setattr(web, '_hypit_runtime_profile', lambda: None)
    test_26_semantic_owner_supply(prep_env, tmp_path, monkeypatch, Trace())

from copy import deepcopy
from tests.test_material_integration import material_integration_env
from easel.integrations.semantic_planning import (
    compile_draft, classification_batches, assemble_requirements, SemanticPlanningError,
    run_semantic_planning, read_file, write_file, encode, verify_semantic_checkpoint,
)


def compile_input(draft=None, **extra):
    return compile_draft(draft or semantic_draft(),creation_id='synthetic',attempt_id='synthetic-a',
        refs={'creative_mode_sha256':'m'},mode={},script='先看问题。',
        allowed_refs={'scene':{'scene-1'}, 'event':{'event-1'}},**extra)


@pytest.mark.parametrize('variant', ['derived_id','wrong_modality','voice_text','unknown_scope','duplicate_json',
                                    'bad_query','query_copy','missing_required','voice_on_visual'])
def test_semantic_transport_rejects_independent_bad_inputs(variant):
    d=semantic_draft();n=d['needs'][0]
    if variant=='derived_id':n['need_id']='invented'
    elif variant=='wrong_modality':n['modality_spec']['kind']='unknown'
    elif variant=='voice_text':
        n['modality_spec']={'kind':'voice','identity':{'source':'explicit_user','reference':'中性旁白'},'text_ref':'planning/SCRIPT.md'}
    elif variant=='unknown_scope':n['scope']['ref']='not-confirmed'
    elif variant=='duplicate_json':d='{"schema":"semantic-planning-draft@1","needs":[],"needs":[]}'
    elif variant=='bad_query':n['queries']=['paper','paper','paper']
    elif variant=='query_copy':n['constraints']['search_query_en']='paper'
    elif variant=='missing_required':n['importance']='optional'
    elif variant=='voice_on_visual':n['constraints']['voice_delivery']={'tone':'neutral'}
    with pytest.raises(SemanticPlanningError):compile_input(d)


def labels():
    return {'classifications':[{'id':0,'kind':'required','preference_source':None},
                              {'id':1,'kind':'postproduction','preference_source':None}]}


@pytest.mark.parametrize('variant',['unknown','missing','duplicate','preference','unresolved','empty_required','metadata'])
def test_classification_binding_rejects_independent_relational_errors(variant):
    response=labels()
    if variant=='unknown':response['classifications'][0]['id']=99
    elif variant=='missing':response['classifications'].pop()
    elif variant=='duplicate':response['classifications'][1]['id']=0
    elif variant=='preference':response['classifications'][0].update(kind='preference',preference_source=99)
    elif variant=='unresolved':response['classifications'][0]['kind']='unresolved'
    elif variant=='empty_required':response['classifications'][0]['kind']='postproduction'
    elif variant=='metadata':response['queries']=['invented','query','copy']
    with pytest.raises(SemanticPlanningError):assemble_requirements(compile_input(),{},[response])


def test_semantic_identity_key_order_crlf_and_required_source_action_protection():
    d=semantic_draft();a=compile_input(d)
    reordered=json.loads(json.dumps(d,sort_keys=True));assert compile_input(reordered)==a
    changed=deepcopy(d);changed['needs'][0]['intent']['description']='两张白纸放在桌上。\r\n没有标志。'
    b=compile_input(changed);assert b.plan_id!=a.plan_id and b.needs[0].need_id!=a.needs[0].need_id
    units=classification_batches(b,{})[0]['units']
    assert ''.join(u['text'] for u in units if u['source']==0)=='两张白纸放在桌上。\r\n没有标志。'
    d['needs'][0]['constraints']['requires_dynamic_action']=True
    with pytest.raises(SemanticPlanningError):assemble_requirements(compile_input(d),{},[labels()])


def test_semantic_multibatch_merges_whole_need_and_optional_without_dropping_units():
    d=semantic_draft();d['needs'][0]['intent']={'description':'纸。'*38,'function':'后期字幕。'}
    optional=deepcopy(d['needs'][0]);optional.update(importance='optional',intent={'description':'杯子。茶。'})
    d['needs'].append(optional)
    plan=compile_input(d);batches=classification_batches(plan,{})
    assert [len(b['units']) for b in batches]==[40,1]
    responses=[{'classifications':[{'id':u['id'],'kind':'postproduction' if u['text']=='后期字幕。' else 'required',
                 'preference_source':None} for u in b['units']]} for b in batches]
    result=assemble_requirements(plan,{},responses)
    assert len(result)==2 and len(result[plan.needs[0].need_id]['clauses'])==40
    with pytest.raises(SemanticPlanningError):assemble_requirements(plan,{},responses[:1])


@pytest.fixture
def semantic_runtime(material_integration_env, tmp_path, monkeypatch):
    from easel.integrations.hypit.handoff import load_frozen_creative_mode
    from easel.integrations.hypit import service
    monkeypatch.setenv('HOME',str(tmp_path/'isolated-home'))
    attempt=service.update_film_attempt(material_integration_env['attempt_id'],event='test_v3',planning_contract_version=3)
    mode,mode_hash=load_frozen_creative_mode(attempt)
    canonical={'SCRIPT.md':'先看问题。\r\n再做决定。','SCENES.md':'桌上的两张白纸。','TREATMENT.md':'暂停观察。'}
    root=Path(attempt['workspace']['path'])
    for name,text in canonical.items():write_file(root,name,text.encode())
    context={'context_refs':{'creative_mode_sha256':mode_hash},'creator_context':{}}
    calls=[]
    def execute(stage,message,session):
        calls.append({'stage':stage,'session':session,'message':message})
        if message.startswith('〔Easel Semantic Planning V3〕'):name='SEMANTIC_PLAN.json';out=semantic_draft()
        elif message.startswith('〔Easel Planning V3 单元分类〕'):
            name='CLASSIFICATIONS-000.json';data=json.loads(message.splitlines()[-1])
            assert [u['text'] for u in data['units']]==['两张白纸放在桌上。','让观众先看问题。']
            out=labels()
        else:
            data=json.loads(message.splitlines()[-1]);name=data['targets'][0]
            out=semantic_draft() if name=='SEMANTIC_PLAN.json' else {'batches':[{'index':0,**labels()}]}
        target = Path(data['output_paths'][name]) if '单次语义合同修正' in message else root/'planning'/name
        target.write_bytes(encode(out))
    def run(dispatch=None):return run_semantic_planning(attempt,context,canonical,mode,
                     {'profile':'fixture-only','thinking':'off','timeout':60},dispatch or execute,
                     compiler_policy='semantic-planning-compiler@6')
    return {'attempt':attempt,'root':root,'mode':mode,'canonical':canonical,'context':context,
            'calls':calls,'execute':execute,'run':run}


def _authority_fixed_response(batch, *, kinds=None):
    """Declared external fixture judgments, not a production semantic oracle.

    The desk fixture keeps the two-paper obligation and narrative purpose.
    Other tests supply their own frozen kind list; no lexical auto-classifier.
    """
    kinds = kinds if kinds is not None else ['required', 'postproduction']
    assert len(kinds) == len(batch['units'])
    sources = batch['authority_catalog']['sources']
    scene = next(s['id'] for s in sources if s['origin'] == 'confirmed_scene' and s['primary'])
    rows = []
    for unit, kind in zip(batch['units'], kinds):
        relation = {'required':'upstream_obligation', 'postproduction':'postproduction',
                    'preference':'preference', 'unresolved':'unresolved'}[kind]
        rows.append({'id':unit['id'],'kind':kind,'preference_source':None,
                     'basis':{'relation':relation,'source_ids':[scene] if kind=='required' else []}})
    controls=[]
    for control in batch['controls']:
        operations=[s for s in sources if s.get('operation',{}).get('need_index')==control['need_index']
                    and s.get('operation',{}).get('path')==control['path']]
        if operations: relation, ids='operational',[operations[0]['id']]
        elif control['soft']: relation,ids='preference',[]
        else: relation,ids='upstream_obligation',[scene]
        controls.append({'id':control['id'],'status':'ACCEPT','basis':{'relation':relation,'source_ids':ids}})
    return {'classifications':rows,'controls':controls}


@pytest.fixture
def authority_runtime(semantic_runtime):
    from easel.integrations.semantic_planning import AUTHORITY_POLICY
    rt=semantic_runtime
    context={'context_refs':rt['context']['context_refs'],
        **{key:json.loads((rt['root']/'handoff'/name).read_text()) for key,name in
           [('creator_context','creator-context.json'),('truth_packet','truth-packet.json'),('content_core','content-core.json')]}}
    def execute(stage,message,session):
        import re, jsonschema
        data=json.loads(message.splitlines()[-1]);rt['calls'].append({'stage':stage,'message':message,'session':session})
        if message.startswith('〔Easel Semantic'):
            out=semantic_draft();target=Path(re.search(r'只写 (.+\.json)',message)[1])
        elif '单元分类' in message:
            out=_authority_fixed_response(data);target=Path(re.search(r'只写 (.+\.json)',message)[1])
            jsonschema.Draft202012Validator.check_schema(data['output_schema'])
            jsonschema.validate(out,data['output_schema'])
        else:
            target=Path(data['output_paths'][data['targets'][0]])
            if data['targets'][0]=='SEMANTIC_PLAN.json':out=semantic_draft()
            else:
                out={'batches':[{'index':b['index'],**_authority_fixed_response(b)} for b in data['context']['batches']]}
                jsonschema.validate(out,data['context']['response_schema'])
        target.write_bytes(encode(out))
    def run(dispatch=None):return run_semantic_planning(rt['attempt'],context,rt['canonical'],rt['mode'],
        {'profile':'fixture-only','thinking':'off','timeout':60},dispatch or execute,compiler_policy=AUTHORITY_POLICY)
    return {**rt,'context':context,'execute':execute,'run':run}


@pytest.mark.parametrize('risk',['persist_reentry','repair','pending','source_tamper','catalog_tamper','missing_basis','control_missing','copy',
                                'multibatch','pure_audio','mixed_audio','capacity'])
def test_native_authority_contract(authority_runtime,risk):
    from easel.integrations.material_layer import PlanningIntegration,MaterialIntegrationError
    from easel.materials.store import AttemptMaterialStore
    from easel.integrations.hypit import service
    rt=authority_runtime
    if risk=='capacity':
        from easel.integrations import planning_authority as authority
        from easel.integrations.semantic_planning import AUTHORITY_POLICY,source_catalog,parse_draft
        inputs=authority.load_inputs(rt['attempt'],rt['canonical'],rt['context'],rt['mode'])
        def compiled(d):return compile_draft(d,creation_id=rt['attempt']['creation_id'],attempt_id=rt['attempt']['attempt_id'],
            refs=rt['context']['context_refs'],mode=rt['mode'],script=rt['canonical']['SCRIPT.md'],
            allowed_refs=source_catalog(rt['canonical'],rt['context']),compiler_policy=AUTHORITY_POLICY,authority_inputs=inputs)
        def batched(d):
            p=compiled(d);directory=authority.catalog(inputs,authority.applied_operations(parse_draft(d),p,rt['mode']))
            return classification_batches(p,rt['mode'],canonical=rt['canonical'],compiler_policy=AUTHORITY_POLICY,authority_catalog=directory)
        d=semantic_draft();d['needs'][0]['constraints']={f'flag_{i}':True for i in range(33)}
        with pytest.raises(SemanticPlanningError,match='32'):batched(d)
        d=semantic_draft();d['needs'][0]['constraints']={f'flag_{i}':True for i in range(12)};d['needs']*=10
        with pytest.raises(SemanticPlanningError,match='128'):batched(d)
        inputs['mode_documents']['oversized.md']='bounded context '*25000
        with pytest.raises(SemanticPlanningError,match='容量'):batched(semantic_draft())
        assert not rt['calls'] and not (rt['root']/'planning/MATERIAL_PLAN.json').exists()
        # Actual invocation: JSON fits, but the full B instruction does not.
        from unittest.mock import patch
        rt['run']()
        bmessage=next(c['message'] for c in rt['calls'] if '单元分类' in c['message'])
        limit=len(json.dumps(json.loads(bmessage.splitlines()[-1]),ensure_ascii=False).encode())+1
        assert len(bmessage.encode())>limit and len(rt['calls'][0]['message'].encode())<limit
        target=service.create_film_attempt(rt['attempt']['creation_id'],rt['attempt']['handoff']['handoff_id'],
            preparation_key='e'*64,runtime_status='NOT_CONFIGURED')
        target=service.update_film_attempt(target['attempt_id'],event='fixture_message_capacity',planning_contract_version=3)
        targetroot=Path(target['workspace']['path'])
        for name,text in rt['canonical'].items():write_file(targetroot,name,text.encode())
        with patch('easel.integrations.semantic_planning.MAX_FILE_BYTES',limit):
            with pytest.raises(SemanticPlanningError,match='完整B消息'):
                run_semantic_planning(target,rt['context'],rt['canonical'],rt['mode'],
                    {'profile':'fixture-only','thinking':'off','timeout':60},rt['execute'],compiler_policy=AUTHORITY_POLICY)
        state=AttemptMaterialStore(targetroot).read_recovery_record('semantic-planning-v3')
        assert set(state['calls'])=={'A'} and not state['repair_used']
        assert len(rt['calls'])==3 and not (targetroot/'planning/MATERIAL_PLAN.json').exists()
        return
    if risk in {'multibatch','pure_audio','mixed_audio'}:
        import re
        d=audio_draft() if risk=='pure_audio' else semantic_draft()
        if risk=='mixed_audio':d['needs'].extend(audio_draft()['needs'])
        if risk=='multibatch':
            d['needs'][0]['intent']={'description':'纸。'*38,'function':'后期字幕。'}
            second=deepcopy(d['needs'][0]);second.update(importance='optional',intent={'description':'杯子。茶。'})
            d['needs'].append(second)
        batches_seen=[]
        def fixed(batch):
            # Explicit fixture expected labels for repeated paper / two cup units.
            kinds=['postproduction' if u['text']=='后期字幕。' else 'required' for u in batch['units']] if risk=='multibatch' else None
            return _authority_fixed_response(batch,kinds=kinds)
        def execute(stage,message,session):
            import jsonschema
            data=json.loads(message.splitlines()[-1]);rt['calls'].append({'stage':stage,'message':message,'session':session})
            if message.startswith('〔Easel Semantic'):
                out=d;target=Path(re.search(r'只写 (.+\.json)',message)[1])
            elif '单元分类' in message:
                batches_seen.append(data);out=fixed(data);target=Path(re.search(r'只写 (.+\.json)',message)[1])
                jsonschema.Draft202012Validator.check_schema(data['output_schema'])
                jsonschema.validate(out,data['output_schema'])
                if risk=='multibatch' and session.endswith('B1'):out['classifications'][0]['id']=99999
            else:
                assert [b['index'] for b in data['context']['batches']]==[1]
                out={'batches':[{'index':1,**fixed(data['context']['batches'][0])}]}
                jsonschema.Draft202012Validator.check_schema(data['context']['response_schema'])
                jsonschema.validate(out,data['context']['response_schema'])
                target=Path(data['output_paths'][data['targets'][0]])
            target.write_bytes(encode(out))
        result=rt['run'](execute)
        assert len(rt['calls'])=={'multibatch':4,'pure_audio':1,'mixed_audio':2}[risk]
        if risk=='multibatch':
            ids=[c['id'] for b in batches_seen for c in b['controls']]
            assert len(ids)==len(set(ids)) and batches_seen[1]['controls']==[]
            first=read_file(rt['root'],'CLASSIFICATIONS-000.json')
            assert rt['run'](execute)['plan']==result['plan'] and len(rt['calls'])==4
            assert read_file(rt['root'],'CLASSIFICATIONS-000.json')==first
        else:
            import hashlib
            voice=next(n.modality_spec for n in result['plan'].needs if n.role=='voice')
            assert voice.text_sha256==hashlib.sha256(rt['canonical']['SCRIPT.md'].encode()).hexdigest()
            assert [n.role for n in result['plan'].needs if n.media_type.value=='audio']==['voice','bgm','sfx']
    elif risk=='pending':
        from easel.creation_delivery import DeliveryObservationPending
        pending=[]
        def execute(stage,message,session):
            if '单元分类' in message and not pending:
                pending.append((message,session));raise DeliveryObservationPending('same original run',disconnected=False)
            if '单元分类' in message:assert (message,session)==pending[0]
            rt['execute'](stage,message,session)
        with pytest.raises(DeliveryObservationPending):rt['run'](execute)
        result=rt['run'](execute)
        assert len(rt['calls'])==2
        assert not AttemptMaterialStore(rt['root']).read_recovery_record('semantic-planning-v3')['repair_used']
    elif risk in {'repair','missing_basis','control_missing'}:
        def execute(stage,message,session):
            rt['execute'](stage,message,session)
            if '单元分类' in message:
                target=rt['root']/'planning/CLASSIFICATIONS-000.json';out=json.loads(target.read_text())
                if risk=='control_missing':out['controls'].pop()
                elif risk=='missing_basis':out['classifications'][0].pop('basis')
                else:out['classifications'][0]['basis']['source_ids']=[99999]
                target.write_bytes(encode(out))
        result=rt['run'](execute)
        assert len(rt['calls'])==3 and sum(c['stage']=='structure_repair' for c in rt['calls'])==1
        assert rt['run'](execute)['plan']==result['plan'] and len(rt['calls'])==3
    else:result=rt['run']()
    saved=PlanningIntegration().persist(rt['attempt'],**{k:result[k] for k in ('plan','script','scenes','treatment')})
    assert PlanningIntegration().load(saved['attempt'])['plan']==result['plan']
    if risk=='source_tamper':
        path=rt['root']/'handoff/creative-mode/visual-bible.md';path.chmod(0o600);path.write_bytes(path.read_bytes()+b'changed')
        with pytest.raises(MaterialIntegrationError):PlanningIntegration().load(saved['attempt'])
    elif risk=='catalog_tamper':
        path=rt['root']/'planning/SEMANTIC_CHECKPOINT.json';cp=json.loads(path.read_text())
        cp['authority_catalog']['sources'][0]['relations'].append('operational');path.write_bytes(encode(cp))
        with pytest.raises(MaterialIntegrationError):PlanningIntegration().load(saved['attempt'])
        # Bypass manifest hash alone is insufficient: the real verifier rebuilds origins.
        with pytest.raises(ValueError,match='目录'):
            verify_semantic_checkpoint(rt['root'],result['plan'],rt['mode'],result['script'],attempt=rt['attempt'])
    elif risk=='copy':
        source=PlanningIntegration().load(saved['attempt']);original=source['plan']
        target=service.create_film_attempt(original.creation_id,saved['attempt']['handoff']['handoff_id'],
            preparation_key='d'*64,runtime_status='NOT_CONFIGURED')
        target=service.update_film_attempt(target['attempt_id'],event='fixture_authority_copy',planning_contract_version=3)
        targetroot=Path(target['workspace']['path'])
        for name in ('MATERIAL_REQUIREMENTS.json','SEMANTIC_PLAN.json','SEMANTIC_CHECKPOINT.json'):
            service._copy_retry_checkpoint_file(rt['root'],targetroot,Path('planning')/name)
        copied=original.model_copy(update={'attempt_id':target['attempt_id'],'plan_id':'fixture-authority-copy'})
        origin={k:getattr(original,k) for k in ('creation_id','attempt_id','plan_id')}
        persisted=PlanningIntegration().persist(target,copied,script=result['script'],scenes=result['scenes'],treatment=result['treatment'],
            requirements_source={**source['requirements'],'origin':origin})
        assert PlanningIntegration().load(persisted['attempt'])['plan']==copied
    else:
        count=len(rt['calls']);assert rt['run']()['plan']==result['plan'] and len(rt['calls'])==count


def test_native_semantic_checkpoint_persistence_reentry_and_tamper(semantic_runtime):
    from easel.integrations.material_layer import PlanningIntegration, MaterialIntegrationError
    rt=semantic_runtime;result=rt['run']();assert len(rt['calls'])==2
    expected=result['plan'];assert rt['run']()['plan']==expected and len(rt['calls'])==2
    saved=PlanningIntegration().persist(rt['attempt'],**{k:result[k] for k in ('plan','script','scenes','treatment')})
    assert saved['manifest']['schema']=='easel-material-planning@3'
    assert PlanningIntegration().load(saved['attempt'])['plan']==expected
    for name in ('SEMANTIC_PLAN.json','SEMANTIC_CHECKPOINT.json'):
        raw=read_file(rt['root'],name);(rt['root']/'planning'/name).write_bytes(raw+b' ')
        with pytest.raises(MaterialIntegrationError):PlanningIntegration().load(saved['attempt'])
        (rt['root']/'planning'/name).write_bytes(raw)
    assert len(rt['calls'])==2


@pytest.mark.parametrize('stage',['A','B'])
def test_native_semantic_shared_repair_once_and_repeat_uses_original_request(semantic_runtime,stage):
    rt=semantic_runtime
    def dispatch(s,message,session):
        rt['execute'](s,message,session)
        if s=='planning' and (stage=='A' and message.startswith('〔Easel Semantic') or stage=='B' and '单元分类' in message):
            name='SEMANTIC_PLAN.json' if stage=='A' else 'CLASSIFICATIONS-000.json'
            data=semantic_draft() if stage=='A' else labels()
            if stage=='A':data['invented_id']='not-allowed'
            else:data['classifications'][0]['id']=99
            (rt['root']/'planning'/name).write_bytes(encode(data))
    first=rt['run'](dispatch);assert len(rt['calls'])==3
    assert [c['stage'] for c in rt['calls']].count('structure_repair')==1
    assert rt['run'](dispatch)['plan']==first['plan'] and len(rt['calls'])==3



@pytest.mark.parametrize('location', ['root', 'planning', 'target'])
def test_native_semantic_repair_rejects_symlink_before_submission(semantic_runtime, location):
    rt = semantic_runtime
    repair_calls = []
    def link(path):
        moved = path.with_name(path.name + '-original')
        path.rename(moved)
        path.symlink_to(moved, target_is_directory=moved.is_dir())
    if location == 'root':
        link(rt['root'])
    def dispatch(stage, message, session):
        if stage == 'structure_repair': repair_calls.append(session)
        rt['execute'](stage, message, session)
        if message.startswith('〔Easel Semantic'):
            target = rt['root'] / 'planning/SEMANTIC_PLAN.json'
            bad = semantic_draft(); bad['policy'] = {'invalid': True}
            target.write_bytes(encode(bad))
            link(target.parent if location == 'planning' else target)
    with pytest.raises(ValueError): rt['run'](dispatch)
    assert repair_calls == []


def test_native_semantic_a_repair_then_b_error_does_not_buy_second_repair(semantic_runtime):
    rt=semantic_runtime
    def dispatch(s,message,session):
        rt['execute'](s,message,session)
        if message.startswith('〔Easel Semantic'):
            d=semantic_draft();d['unknown']='field';(rt['root']/'planning/SEMANTIC_PLAN.json').write_bytes(encode(d))
        elif '单元分类' in message:
            d=labels();d['classifications'].pop();(rt['root']/'planning/CLASSIFICATIONS-000.json').write_bytes(encode(d))
    for _ in range(2):
        with pytest.raises(SemanticPlanningError,match='额度已用完'):rt['run'](dispatch)
    assert len(rt['calls'])==3
    assert not (rt['root']/'planning/MATERIAL_PLAN.json').exists()


def test_native_semantic_unknown_execution_recovers_same_stage_and_snapshot_change_stops(semantic_runtime):
    from easel.creation_delivery import DeliveryExecutionUncertain
    rt=semantic_runtime;pending=[True]
    def dispatch(s,message,session):
        if pending[0] and '单元分类' in message:
            pending[0]=False
            rt['calls'].append({'stage':s,'session':session,'message':message})
            raise DeliveryExecutionUncertain('fixture unknown')
        rt['execute'](s,message,session)
    with pytest.raises(DeliveryExecutionUncertain):rt['run'](dispatch)
    assert not (rt['root']/'planning/MATERIAL_PLAN.json').exists()
    result=rt['run'](dispatch)
    assert rt['calls'][1]['session']==rt['calls'][2]['session']
    assert result['plan'].needs[0].importance.value=='required'
    rt['canonical']['SCRIPT.md']+='改字。'
    with pytest.raises(SemanticPlanningError,match='输入、版本'):rt['run'](dispatch)
    assert len(rt['calls'])==3


@pytest.mark.parametrize('field', ['intent','importance','constraints','modality_spec','queries','duration_hint'])
def test_native_repair_cannot_change_valid_semantics_on_first_or_resumed_run(semantic_runtime,field):
    rt=semantic_runtime
    original=semantic_draft();original['unknown']='transport-error'
    original['needs'][0]['duration_hint']={'target_seconds':3}
    repaired=deepcopy(original);repaired.pop('unknown')
    changes={'intent':{'description':'一张纸。'},'importance':'optional','constraints':{},
             'modality_spec':{'kind':'video'},'queries':['cup table','glass room','mug counter'],
             'duration_hint':{'target_seconds':2}}
    repaired['needs'][0][field]=changes[field]
    def dispatch(s,message,session):
        rt['calls'].append({'stage':s,'session':session})
        assert '单元分类' not in message
        (rt['root']/'planning/SEMANTIC_PLAN.json').write_bytes(encode(repaired if s=='structure_repair' else original))
    for _ in range(2):
        with pytest.raises(SemanticPlanningError,match='有效需求语义'):rt['run'](dispatch)
    assert len(rt['calls'])==2 and not (rt['root']/'planning/MATERIAL_PLAN.json').exists()


def test_native_repair_can_correct_invalid_importance_without_changing_valid_intent(semantic_runtime):
    rt=semantic_runtime
    def dispatch(s,message,session):
        rt['execute'](s,message,session)
        if message.startswith('〔Easel Semantic'):
            d=semantic_draft();d['needs'][0]['importance']='requird'
            (rt['root']/'planning/SEMANTIC_PLAN.json').write_bytes(encode(d))
    assert rt['run'](dispatch)['plan'].needs[0].importance.value=='required'
    rt['run'](dispatch);assert len(rt['calls'])==3


def audio_draft():
    d={'schema':'semantic-planning-draft@1','needs':[]}
    for kind in ('voice','bgm','sfx'):
        spec={'kind':kind}
        if kind=='voice':spec['identity']={'source':'creator_context','reference':'creator_context.voice'}
        if kind=='sfx':spec['event_description']='杯子落桌声。'
        d['needs'].append({'scope':{'type':'event' if kind=='sfx' else 'global',
                                  'ref':'event-1' if kind=='sfx' else 'global'},'role':kind,
            'intent':{'description':{'voice':'克制讲述。','bgm':'轻音乐。','sfx':'杯子落桌声。'}[kind]},
            'importance':'required','modality_spec':spec})
    return d


def test_native_pure_audio_and_mixed_plan_keep_all_modalities_and_voice_byte_binding(semantic_runtime):
    from easel.integrations.material_layer import PlanningIntegration
    import hashlib
    rt=semantic_runtime;rt['context']['creator_context']={'voice':{'tone':'克制'}}
    draft=audio_draft()
    def dispatch(s,message,session):
        rt['calls'].append({'stage':s,'session':session})
        assert '单元分类' not in message
        (rt['root']/'planning/SEMANTIC_PLAN.json').write_bytes(encode(draft))
    result=rt['run'](dispatch);plan=result['plan']
    assert [n.modality_spec.kind for n in plan.needs]==['voice','bgm','sfx']
    voice=plan.needs[0].modality_spec
    assert voice.text_ref=='planning/SCRIPT.md' and voice.text_sha256==hashlib.sha256(rt['canonical']['SCRIPT.md'].encode()).hexdigest()
    assert json.loads(read_file(rt['root'],'MATERIAL_REQUIREMENTS.json'))=={}
    saved=PlanningIntegration().persist(rt['attempt'],**{k:result[k] for k in ('plan','script','scenes','treatment')})
    assert PlanningIntegration().load(saved['attempt'])['plan']==plan
    rt['run'](dispatch);assert len(rt['calls'])==1
    mixed=semantic_draft();mixed['needs'].extend(draft['needs'])
    mixedplan=compile_draft(mixed,creation_id='synthetic',attempt_id='synthetic-a',refs={},mode={},script='克制讲述。',
        allowed_refs={'scene':{'scene-1'},'event':{'event-1'},'global':{'global'},'voice':{'creator_context.voice':{'source':'creator_context'}}})
    assert len(mixedplan.needs)==4 and len(assemble_requirements(mixedplan,{},[labels()]))==1
    bad=deepcopy(mixed);bad['needs'][1]['modality_spec']['identity']['reference']='invented provider voice'
    with pytest.raises(SemanticPlanningError,match='实际存在'):
        compile_draft(bad,creation_id='synthetic',attempt_id='synthetic-a',refs={},mode={},script='克制讲述。',
            allowed_refs={'scene':{'scene-1'},'event':{'event-1'},'global':{'global'},'voice':{'creator_context.voice':{'source':'creator_context'}}})


def test_native_classifier_tamper_freezes_failure_and_partial_outputs_never_commit(semantic_runtime):
    rt=semantic_runtime
    def dispatch(s,message,session):
        rt['execute'](s,message,session)
        if '单元分类' in message:
            d=semantic_draft();d['needs'][0]['importance']='optional'
            (rt['root']/'planning/SEMANTIC_PLAN.json').write_bytes(encode(d))
    with pytest.raises(SemanticPlanningError,match='分类阶段改写'):rt['run'](dispatch)
    with pytest.raises(SemanticPlanningError,match='有效语义草稿原件变化'):rt['run'](dispatch)
    assert len(rt['calls'])==2 and not (rt['root']/'planning/MATERIAL_PLAN.json').exists()


def test_native_semantic_checkpoint_copy_binds_new_attempt_without_replanning(semantic_runtime):
    from easel.integrations.hypit import service
    from easel.integrations.material_layer import PlanningIntegration,MaterialIntegrationError
    rt=semantic_runtime;result=rt['run']()
    saved=PlanningIntegration().persist(rt['attempt'],**{k:result[k] for k in ('plan','script','scenes','treatment')})
    source=PlanningIntegration().load(saved['attempt']);original=source['plan']
    target=service.create_film_attempt(original.creation_id,saved['attempt']['handoff']['handoff_id'],
                                      preparation_key='c'*64,runtime_status='NOT_CONFIGURED')
    target=service.update_film_attempt(target['attempt_id'],event='test_copy_v3',planning_contract_version=3)
    targetroot=Path(target['workspace']['path'])
    for name in ('MATERIAL_REQUIREMENTS.json','SEMANTIC_PLAN.json','SEMANTIC_CHECKPOINT.json'):
        service._copy_retry_checkpoint_file(rt['root'],targetroot,Path('planning')/name)
    copied=original.model_copy(update={'attempt_id':target['attempt_id'],'plan_id':'copied-plan'})
    origin={'creation_id':original.creation_id,'attempt_id':original.attempt_id,'plan_id':original.plan_id}
    persisted=PlanningIntegration().persist(target,copied,script=result['script'],scenes=result['scenes'],
        treatment=result['treatment'],requirements_source={**source['requirements'],'origin':origin})
    assert PlanningIntegration().load(persisted['attempt'])['plan']==copied
    assert len(rt['calls'])==2
    bad={**source['requirements'],'origin':{**origin,'attempt_id':'unrelated'}}
    with pytest.raises(MaterialIntegrationError):
        PlanningIntegration().persist(target,copied,script=result['script'],scenes=result['scenes'],
            treatment=result['treatment'],requirements_source=bad)


def test_native_multibatch_repairs_only_affected_batch_and_keeps_successful_response(semantic_runtime):
    rt=semantic_runtime;d=semantic_draft()
    d['needs'][0]['intent']={'description':'纸。'*38,'function':'后期字幕。'}
    optional=deepcopy(d['needs'][0]);optional.update(importance='optional',intent={'description':'杯子。茶。'})
    d['needs'].append(optional)
    def correct(batch):return {'classifications':[{'id':u['id'],
        'kind':'postproduction' if u['text']=='后期字幕。' else 'required','preference_source':None} for u in batch['units']]}
    def dispatch(s,message,session):
        rt['calls'].append({'stage':s,'session':session,'message':message})
        data=json.loads(message.splitlines()[-1])
        if message.startswith('〔Easel Semantic'):name='SEMANTIC_PLAN.json';out=d
        elif '单元分类' in message:
            index=0 if session.endswith('B0') else 1;name=f'CLASSIFICATIONS-{index:03}.json';out=correct(data)
            if index==1:out['classifications'][0]['id']=99
        else:
            assert [b['index'] for b in data['context']['batches']]==[1]
            name='CLASSIFICATIONS-REPAIR.json';out={'batches':[{'index':1,**correct(data['context']['batches'][0])}]}
            import jsonschema
            assert not list(jsonschema.Draft202012Validator(data['context']['response_schema']).iter_errors(out))
        (rt['root']/'planning'/name).write_bytes(encode(out))
    result=rt['run'](dispatch);assert len(result['plan'].needs)==2
    raw=read_file(rt['root'],'CLASSIFICATIONS-000.json')
    rt['run'](dispatch)
    assert len(rt['calls'])==4 and read_file(rt['root'],'CLASSIFICATIONS-000.json')==raw


@pytest.mark.parametrize('outcome',['timeout','release_pending'])
def test_native_v3_gateway_adapter_recovers_original_run_without_resubmission(semantic_runtime,outcome):
    import subprocess
    from easel import creation
    from easel.creation_delivery import active_delivery, DeliveryExecutionUncertain
    from easel.integrations.openclaw_delivery import run_delivery_agent
    rt=semantic_runtime;cid=rt['attempt']['creation_id']
    with creation.edit_creation(cid) as work:work['delivery']={'agent_calls':{},'last_operation':'prepare'}
    methods=[];run_id=None;terminal=False;released=False;pending_message=None;pending_session=None
    def rpc(command,**kwargs):
        nonlocal run_id,released,pending_message,pending_session
        method=command[command.index('call')+1];params=json.loads(command[command.index('--params')+1]);methods.append(method)
        if method=='agent':
            if '单元分类' not in params['message']:
                rt['execute']('planning',params['message'],params['sessionKey'])
                return subprocess.CompletedProcess(command,0,json.dumps({'runId':params['idempotencyKey'],'status':'ok','endedAt':1000}),'')
            run_id=params['idempotencyKey'];pending_message=params['message'];pending_session=params['sessionKey']
            if outcome=='timeout':raise subprocess.TimeoutExpired(command,20)
            rt['execute']('planning',pending_message,pending_session)
            return subprocess.CompletedProcess(command,0,json.dumps({'runId':run_id,'status':'ok','endedAt':1000}),'')
        if method=='agent.wait':
            assert params=={'runId':run_id,'timeoutMs':0}
            if terminal:rt['execute']('planning',pending_message,pending_session)
            return subprocess.CompletedProcess(command,0,json.dumps({'runId':run_id,'status':'ok' if terminal else 'pending',
                                                                     'endedAt':1000 if terminal else None}),'')
        assert method=='sessions.abort'
        if outcome=='release_pending' and pending_session==params['key'] and not released:
            released=True;raise subprocess.TimeoutExpired(command,20)
        return subprocess.CompletedProcess(command,0,json.dumps({'ok':True,'status':'no-active-run'}),'')
    def dispatch(stage,message,session):
        cmd=['openclaw','--profile','fixture-only','agent','--agent','main','--session-key','agent:main:'+session,
             '--thinking','off','--timeout','60','--message',message]
        return run_delivery_agent(cmd,runner=rpc,retry_failed=False)
    token=active_delivery.set(cid)
    try:
        with pytest.raises((DeliveryExecutionUncertain,subprocess.TimeoutExpired)):rt['run'](dispatch)
        stored=creation.get_creation(cid)['delivery']['agent_calls']
        old={k:(v['run_id'],v['request_sha256']) for k,v in stored.items()}
        if outcome=='timeout':
            with pytest.raises(DeliveryExecutionUncertain):rt['run'](dispatch)
            terminal=True
        result=rt['run'](dispatch);rt['run'](dispatch)
        stored=creation.get_creation(cid)['delivery']['agent_calls']
        assert old=={k:(v['run_id'],v['request_sha256']) for k,v in stored.items()}
        assert methods.count('agent')==2 and all(v['runtime_release']=='released' for v in stored.values())
        assert result['plan'].needs[0].intent.description=='两张白纸放在桌上。'
    finally:active_delivery.reset(token)


@pytest.mark.parametrize('legacy',['ok','error','release_pending','artifact','repair'])
def test_native_preparation_does_not_upgrade_existing_legacy_planning(prep_env,monkeypatch,legacy):
    from tests.test_creation_preparation import _prepare_creation,creation,service,prep
    from easel.creator_proposal import parse_video_plan
    from tests.test_model_output_contracts import proposal
    from easel.materials.store import AttemptMaterialStore
    work=prep_env['work'];result=_prepare_creation(work['id'],runtime_profile=None)
    attempt=service.get_film_attempt(result['attempt_id'])
    service.update_film_attempt(attempt['attempt_id'],event='test_legacy_uncommitted',
                                planning_contract_version=None,material_planning={})
    root=Path(attempt['workspace']['path'])
    for name in ('MATERIAL_PLAN.json','MATERIAL_REQUIREMENTS.json'):
        (root/'planning'/name).unlink(missing_ok=True)
    with creation.edit_creation(work['id']) as current:
        current['preparation']['status']='MATERIAL_FAILED'
        current['delivery']={'video_plan':parse_video_plan(proposal('先看问题。')),'agent_calls':{}}
        if legacy in {'ok','error','release_pending'}:
            current['delivery']['agent_calls']['original']={'status':'error' if legacy=='error' else 'ok',
                'session_key':'agent:main:material-planning-'+attempt['attempt_id'],
                'runtime_release':'pending' if legacy=='release_pending' else 'released'}
    if legacy=='artifact':(root/'planning/MATERIAL_PLAN.json').write_bytes(b'{}')
    if legacy=='repair':AttemptMaterialStore(root).write_recovery_record('planning-structure-repair-original',{'status':'failed'})
    seen=[]
    def observe_only(a,context):
        seen.append(a.get('planning_contract_version'))
        raise prep.PreparationError('fixture stopped before legacy dispatch')
    observe_only.planning_contract_version=3
    with pytest.raises(prep.PreparationError,match='fixture stopped'):
        _prepare_creation(work['id'],runtime_profile=None,planning_executor=observe_only)
    assert seen==[None] and service.get_film_attempt(attempt['attempt_id']).get('planning_contract_version') is None


def test_native_repair_protects_valid_child_while_fixing_invalid_sibling(semantic_runtime):
    rt=semantic_runtime
    original=semantic_draft();original['needs'][0]['intent']['function']=123
    def dispatch(s,message,session):
        rt['calls'].append({'stage':s,'session':session})
        result=deepcopy(original)
        if s=='structure_repair':
            result['needs'][0]['intent']={'description':'一张纸。','function':'让观众先看问题。'}
        (rt['root']/'planning/SEMANTIC_PLAN.json').write_bytes(encode(result))
    for _ in range(2):
        with pytest.raises(SemanticPlanningError,match='intent.description'):rt['run'](dispatch)
    assert len(rt['calls'])==2


def test_native_repair_can_remove_misplaced_audio_control_and_preserve_visual(semantic_runtime):
    rt=semantic_runtime
    def dispatch(s,message,session):
        rt['execute'](s,message,session)
        if message.startswith('〔Easel Semantic'):
            d=semantic_draft();d['needs'][0]['constraints']['voice_delivery']={'tone':'neutral'}
            (rt['root']/'planning/SEMANTIC_PLAN.json').write_bytes(encode(d))
    result=rt['run'](dispatch);assert result['plan'].needs[0].intent.description=='两张白纸放在桌上。'
    rt['run'](dispatch);assert len(rt['calls'])==3


def test_repair_preserves_optional_model_and_voice_delivery_valid_children():
    from easel.integrations.semantic_planning import _preserve_repair_semantics
    d=semantic_draft();d['needs'][0]['duration_hint']={'target_seconds':3,'unknown':'transport'}
    fixed=deepcopy(d);fixed['needs'][0]['duration_hint']={'target_seconds':3}
    _preserve_repair_semantics(encode(d),encode(fixed))
    bad=deepcopy(fixed);bad['needs'][0]['duration_hint']['target_seconds']=1
    with pytest.raises(SemanticPlanningError,match='target_seconds'):_preserve_repair_semantics(encode(d),encode(bad))
    d=audio_draft();d['needs'][0]['constraints']={'voice_delivery':{'tone':'neutral','pace_ratio':1.05,'unknown':1}}
    fixed=deepcopy(d);fixed['needs'][0]['constraints']['voice_delivery'].pop('unknown')
    _preserve_repair_semantics(encode(d),encode(fixed))
    for key,value in [('tone','happy'),('pace_ratio',1.1)]:
        bad=deepcopy(fixed);bad['needs'][0]['constraints']['voice_delivery'][key]=value
        with pytest.raises(SemanticPlanningError,match=key):_preserve_repair_semantics(encode(d),encode(bad))
    d=semantic_draft();d['policy']={'strategy':'bulk_first'}
    fixed=deepcopy(d);fixed['policy']['strategy']='changed'
    with pytest.raises(SemanticPlanningError,match='策略'):_preserve_repair_semantics(encode(d),encode(fixed))


@pytest.mark.parametrize('variant',['optional_duration','voice_parameter'])
def test_native_repair_valid_children_remain_protected_after_reentry(semantic_runtime,variant):
    rt=semantic_runtime;original=semantic_draft()
    if variant=='optional_duration':
        original['needs'][0]['duration_hint']={'target_seconds':3,'unknown':'transport'}
        repaired=deepcopy(original);repaired['needs'][0]['duration_hint']={'target_seconds':1}
        location='target_seconds'
    else:
        rt['context']['creator_context']={'voice':{'tone':'克制'}}
        original=audio_draft();original['needs']=original['needs'][:1]
        original['needs'][0]['constraints']={'voice_delivery':{'tone':'sad','pace_ratio':3}}
        repaired=deepcopy(original);repaired['needs'][0]['constraints']['voice_delivery']={'tone':'happy','pace_ratio':1}
        location='voice_delivery.tone'
    def dispatch(s,message,session):
        rt['calls'].append({'stage':s,'session':session})
        assert '单元分类' not in message
        (rt['root']/'planning/SEMANTIC_PLAN.json').write_bytes(encode(repaired if s=='structure_repair' else original))
    for _ in range(2):
        with pytest.raises(SemanticPlanningError,match=location):rt['run'](dispatch)
    assert len(rt['calls'])==2 and not (rt['root']/'planning/MATERIAL_PLAN.json').exists()


@pytest.mark.parametrize('risk', ['aggregate_history', 'constraint_erasure', 'policy_child',
    'schema_constraints', 'schema_continuity', 'legal_policy', 'legal_reference', 'legal_audio'])
def test_a_compiler_contract_alignment(semantic_runtime, risk, evidence=None):
    rt = semantic_runtime
    if risk == 'aggregate_history':
        raw = (FIXTURE / 'batch03/A-original.json').read_bytes()
        catalog = json.loads((FIXTURE / 'batch03/catalog.json').read_text())
        with pytest.raises(SemanticPlanningError) as caught:
            compile_draft(raw, creation_id='synthetic-history', attempt_id='synthetic-history-a',
                refs={}, mode={}, script='先看问题，再做决定。', allowed_refs=catalog)
        issues = caught.value.issues
        if evidence: evidence.note('all independent actual issues', issues)
        assert any(i['field'].startswith('policy.') for i in issues)
        assert any(i['field'] == 'needs.0' and 'scalar retrieval filter' in i['message'] for i in issues)
        assert any(i['field'] == 'needs.1' and 'continuity' in i['message'] for i in issues)
        combined = json.loads(raw)
        combined['needs'][0]['scope']['ref'] = 'unknown'
        combined['needs'][0]['continuity_refs'] = [{'kind':'image','ref':'unknown'}]
        with pytest.raises(SemanticPlanningError) as combined_error:
            compile_draft(combined, creation_id='synthetic-history', attempt_id='synthetic-history-a',
                refs={}, mode={}, script='先看问题，再做决定。', allowed_refs=catalog)
        assert sum(i['field'] == 'needs.0' for i in combined_error.value.issues) == 3
        return
    if risk in {'constraint_erasure', 'policy_child'}:
        original = semantic_draft()
        if risk == 'constraint_erasure':
            original['needs'][0]['constraints']['must_contain'] = ['不可丢失的角标']
            fixed = deepcopy(original); fixed['needs'][0]['constraints'].pop('must_contain')
        else:
            original['policy'] = {'language': 'zh-CN', 'broken': True}
            fixed = deepcopy(original); fixed['policy'] = {'language': 'en', 'broken': 'true'}
        def dispatch(stage, message, session):
            if '单元分类' in message: return rt['execute'](stage, message, session)
            rt['calls'].append({'stage':stage, 'session':session})
            target = rt['root'] / 'planning/SEMANTIC_PLAN.json'
            target.write_bytes(encode(fixed if stage == 'structure_repair' else original))
        for _ in range(2):
            with pytest.raises(SemanticPlanningError): rt['run'](dispatch)
        assert len(rt['calls']) == 2 and not (rt['root'] / 'planning/MATERIAL_PLAN.json').exists()
        if evidence: evidence.note('rejected erasure without formal Plan', {'risk':risk,'calls':2})
        return
    import jsonschema
    candidate = semantic_draft()
    if risk == 'schema_constraints': candidate['needs'][0]['constraints']['must_contain'] = ['两张白纸']
    elif risk == 'schema_continuity': candidate['needs'][0]['continuity_refs'] = [{'kind':'image','ref':'unknown'}]
    elif risk == 'legal_policy': candidate['policy'] = {'strategy':'bulk_first','language':'zh-CN'}
    elif risk == 'legal_reference':
        rt['context']['creator_context'] = {'asset':{'id':'asset-one'}}
        candidate['needs'][0]['continuity_refs'] = [{'kind':'image','ref':'asset-one'}]
    elif risk == 'legal_audio':
        rt['context']['creator_context'] = {'voice':{'tone':'克制'}}
        candidate = audio_draft(); candidate['needs'][0]['constraints'] = {'voice_delivery':{'tone':'neutral'}}
    messages = []
    def dispatch(stage, message, session):
        if message.startswith('〔Easel Semantic'):
            messages.append(message)
            rt['calls'].append({'stage':stage,'session':session})
            # Legal baseline traverses the actual compiler/classifier before
            # testing the published Schema against independent variants.
            out = candidate if risk.startswith('legal_') else semantic_draft()
            (rt['root'] / 'planning/SEMANTIC_PLAN.json').write_bytes(encode(out))
        else: rt['execute'](stage, message, session)
    result = rt['run'](dispatch)
    schema = json.loads(messages[0].splitlines()[-1])['schema']
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(candidate))
    if evidence: evidence.note('published Schema validation', {'risk':risk,'errors':[e.message for e in errors]})
    if risk.startswith('schema_'):
        assert errors, 'published Schema accepts a downstream-invalid structure'
        if risk == 'schema_constraints':
            variants = [semantic_draft() for _ in range(4)]
            variants[0]['needs'][0].pop('queries')
            variants[1]['needs'][0]['constraints']['voice_delivery'] = {'tone':'neutral'}
            variants[2]['needs'][0]['constraints']['search_query_en'] = 'paper'
            variants[3]['needs'][0]['constraints']['voice_tone'] = 'neutral'
            assert all(list(jsonschema.Draft202012Validator(schema).iter_errors(v)) for v in variants)
    else:
        assert not errors and all(n.importance.value == 'required' for n in result['plan'].needs)
        if risk == 'legal_audio':
            for invalid in ({'pace_ratio':0.4}, {'pitch_semitones':True}, {'tone':'invented'}, {'unknown':1}):
                bad = deepcopy(candidate);bad['needs'][0]['constraints']['voice_delivery'] = invalid
                assert list(jsonschema.Draft202012Validator(schema).iter_errors(bad))


def _classification_fixture_from_schema(schema):
    """External fixed semantic answers; envelope/IDs come only from submitted schema."""
    properties = schema['properties']
    if 'batches' in properties:
        return {'batches': [dict(index=item['properties']['index']['const'],
            **_classification_fixture_from_schema({'properties': {'classifications': item['properties']['classifications']}}))
            for item in properties['batches']['prefixItems']]}
    return {'classifications': [{'id': item['properties']['id']['const'],
        'kind': 'required', 'preference_source': None}
        for item in properties['classifications']['prefixItems']]}


@pytest.mark.parametrize('risk', ['history_diagnostic', 'bad_shapes', 'schema_and_preferences',
                                  'native_schema_repair', 'old_v4_checkpoint', 'output_identity', 'old_v4_pending'])
def test_b_output_contract(semantic_runtime, risk, evidence=None):
    from easel.integrations.semantic_planning import _merge_repaired, BASE_POLICY as POLICY, digest
    from easel.integrations.material_layer import PlanningIntegration
    from easel.materials.store import AttemptMaterialStore
    import jsonschema
    folder = FIXTURE / 'batch07'; rt = semantic_runtime
    scope = json.loads((folder / 'scope-original.json').read_text())
    partial = json.loads((folder / 'partial-snapshot-original.json').read_text())
    plan = MaterialPlan.model_validate_json(json.dumps(partial['plan']))
    bad = json.loads((folder / 'B-original.json').read_text())
    expected = json.loads((folder / 'expected.json').read_text())
    if risk == 'history_diagnostic':
        with pytest.raises(SemanticPlanningError) as caught:
            assemble_requirements(plan, scope['mode'], [bad], canonical=scope['canonical'], compiler_policy=scope['policy'])
        assert any(i['field'] == expected['expected_issue_field'] and 'kind' in i['message'] for i in caught.value.issues)
        assert not any('引用不属于冻结原文' in i['message'] for i in caught.value.issues)
        repair = json.loads((folder / 'B-repair-original.json').read_text())
        with pytest.raises(SemanticPlanningError) as caught: _merge_repaired([bad], repair, [0])
        assert caught.value.issues[0]['field'] == expected['expected_repair_issue_field']
        if evidence: evidence.note('actual raw replay', {'initial': 'REJECT at unit.8.kind', 'repair': 'REJECT wrapper', 'semantics': 'UNVERIFIED'})
    elif risk == 'bad_shapes':
        plan = compile_input(); good = labels()
        variants = [('batches.0.wrapper', {'responses': good}),
            ('batches.0.ids', {'classifications': [dict(good['classifications'][0], id=True), good['classifications'][1]]}),
            ('batches.0.ids', {'classifications': list(reversed(good['classifications']))})]
        for value in ['narrative_or_postproduction', {}, [], True, None]:
            v = deepcopy(good); v['classifications'][0]['kind'] = value
            variants.append(('unit.0.kind', v))
        v = deepcopy(good); v['classifications'][0]['preference_source'] = True
        variants.append(('unit.0.preference_source', v))
        for field, value in variants:
            with pytest.raises(SemanticPlanningError) as caught: assemble_requirements(plan, {}, [value])
            assert caught.value.issues[0]['field'] == field
        for value in [{'responses': []}, {'batches': [{'index': True, **good}]},
            {'batches': [{'index': 1, **good}, {'index': 0, **good}]},
            {'batches': [{'index': 0, **good}, {'index': 0, **good}]}, {'batches': []}]:
            with pytest.raises(SemanticPlanningError): _merge_repaired([good, good], value, [0, 1])
        assert _merge_repaired([good, None], {'batches': [{'index': 1, **good}]}, [1]) == [good, good]
    elif risk == 'schema_and_preferences':
        d = semantic_draft(); d['needs'][0]['constraints'] = {'preferred_visual_details': 'soft light'}
        other = deepcopy(d['needs'][0]); other['constraints'] = {'preferred_visual_details': 'cool tone'}; d['needs'].append(other)
        plan = compile_input(d); batch = classification_batches(plan, {})[0]
        schema = batch['output_schema']; validator = jsonschema.Draft202012Validator(schema)
        assert schema['$schema'] == 'https://json-schema.org/draft/2020-12/schema'
        jsonschema.Draft202012Validator.check_schema(schema)
        fixed = {'classifications': []}
        for u, item in zip(batch['units'], schema['properties']['classifications']['prefixItems']):
            context = batch['contexts'][u['need']]
            own = [p['id'] for p in context['preferences']]
            assert item['properties']['preference_source']['enum'] == [None, *own]
            explicit = context['input']['sources'][u['source']]['preference']
            fixed['classifications'].append({'id': u['id'], 'kind': 'preference' if explicit else 'required',
                'preference_source': own[0] if explicit else None})
        assert not list(validator.iter_errors(fixed)); assemble_requirements(plan, {}, [fixed])
        for alter in ['unknown_kind', 'bool_id', 'wrapper', 'extra_row', 'wrong_preference', 'reorder']:
            v = deepcopy(fixed)
            if alter == 'unknown_kind': v['classifications'][0]['kind'] = 'narrative_or_postproduction'
            elif alter == 'bool_id': v['classifications'][0]['id'] = True
            elif alter == 'wrapper': v = {'batch_id': batch['batch_id'], **v}
            elif alter == 'extra_row': v['classifications'].append(v['classifications'][0])
            elif alter == 'wrong_preference': v['classifications'][0]['preference_source'] = batch['contexts'][plan.needs[1].need_id]['preferences'][0]['id']
            else: v['classifications'].reverse()
            assert list(validator.iter_errors(v)), alter
            with pytest.raises(SemanticPlanningError): assemble_requirements(plan, {}, [v])
    elif risk == 'native_schema_repair':
        def execute(stage, message, session):
            import re
            rt['calls'].append({'stage': stage, 'message': message, 'session': session})
            data = json.loads(message.splitlines()[-1])
            if message.startswith('〔Easel Semantic'):
                out = semantic_draft(); target = Path(re.search(r'只写 (.+\.json)', message)[1])
            elif '单元分类' in message:
                schema = data['output_schema']; out = _classification_fixture_from_schema(schema)
                assert not list(jsonschema.Draft202012Validator(schema).iter_errors(out))
                out['classifications'][0]['kind'] = 'narrative_or_postproduction'
                target = Path(re.search(r'只写 (.+\.json)', message)[1])
            else:
                assert data['issues'][0]['field'] == 'unit.0.kind'
                schema = data['context']['response_schema']; out = _classification_fixture_from_schema(schema)
                assert not list(jsonschema.Draft202012Validator(schema).iter_errors(out))
                assert schema['properties']['batches']['prefixItems'][0]['properties']['classifications'] == data['context']['batches'][0]['output_schema']['properties']['classifications']
                target = Path(data['output_paths'][data['targets'][0]])
            assert target.is_absolute(); target.write_bytes(encode(out))
        result = rt['run'](execute)
        saved = PlanningIntegration().persist(rt['attempt'], **{k: result[k] for k in ('plan','script','scenes','treatment')})
        assert PlanningIntegration().load(saved['attempt'])['plan'] == result['plan']
        assert rt['run'](execute)['plan'] == result['plan'] and len(rt['calls']) == 3
        if evidence: evidence.note('native Schema-guided repair', {'submissions': 3, 'repeat_submissions': 0, 'external_semantics': 'fixed answers, no model accuracy claim'})
    elif risk == 'old_v4_checkpoint':
        checkpoint = json.loads((folder / 'legal-checkpoint-original.json').read_text()); old_scope = checkpoint['scope']
        original = MaterialPlan.model_validate_json((folder / 'legal-Plan-original.json').read_bytes())
        old_batches = classification_batches(original, old_scope['mode'], canonical=old_scope['canonical'], compiler_policy='semantic-planning-compiler@4')
        assert all('output_schema' not in b for b in old_batches) and digest(old_batches) == checkpoint['batches_sha256']
        root = rt['root'] / 'old-v4'; (root / 'planning').mkdir(parents=True)
        for name, src in [('SEMANTIC_CHECKPOINT.json','legal-checkpoint-original.json'), ('SEMANTIC_PLAN.json','legal-A-original.json'), ('MATERIAL_REQUIREMENTS.json','legal-Requirements-original.json')]:
            (root/'planning'/name).write_bytes((folder/src).read_bytes())
        for name, text in old_scope['canonical'].items(): (root/'planning'/name).write_bytes(text.encode())
        assert verify_semantic_checkpoint(root, original, old_scope['mode'], old_scope['canonical']['SCRIPT.md'])['policy'] == 'semantic-planning-compiler@4'
    elif risk == 'output_identity':
        old = compile_input(compiler_policy='semantic-planning-compiler@4'); new = compile_input()
        assert POLICY != 'semantic-planning-compiler@4' and old.plan_id != new.plan_id
        old_batch = classification_batches(old, {}, compiler_policy='semantic-planning-compiler@4')[0]
        new_batch = classification_batches(new, {})[0]
        assert 'output_schema' not in old_batch and 'output_schema' in new_batch
        assert old_batch['review_target']['schema'] == 'material-review-target@2'
        from easel.integrations.semantic_planning import REVIEW_TARGET
        assert new_batch['review_target'] == REVIEW_TARGET
        assert old_batch['batch_id'] != new_batch['batch_id']
    else:
        state = {'schema':'semantic-planning-checkpoint@1','scope': {
            'policy':'semantic-planning-compiler@4','attempt_id':rt['attempt']['attempt_id'],'creation_id':rt['attempt']['creation_id'],
            'context_refs':rt['context']['context_refs'],'canonical':rt['canonical'],'mode':rt['mode']},
            'route':{'profile':'fixture-only','thinking':'off','timeout':60},'calls':{'B0':{'status':'pending','message':'original v4 request'}},'repair_used':True}
        store = AttemptMaterialStore(rt['root']); store.write_recovery_record('semantic-planning-v3', state)
        with pytest.raises(SemanticPlanningError, match='版本'): rt['run']()
        assert not rt['calls'] and store.read_recovery_record('semantic-planning-v3') == state


@pytest.mark.parametrize('risk', ['history_use', 'use_contrasts', 'native_use_repair',
                                  'old_v5_checkpoint', 'use_identity_pending'])
def test_asset_versus_use_task(semantic_runtime, risk, evidence=None):
    from easel.integrations.semantic_planning import BASE_POLICY as POLICY, digest, source_catalog
    from easel.integrations.material_layer import PlanningIntegration
    from easel.materials.store import AttemptMaterialStore
    folder = FIXTURE/'batch08'; rt = semantic_runtime
    scope = json.loads((folder/'scope-original.json').read_text())
    original = MaterialPlan.model_validate_json(json.dumps(json.loads((folder/'partial-snapshot-original.json').read_text())['plan']))
    response = json.loads((folder/'B-original.json').read_text())
    expected = json.loads((folder/'expected.json').read_text())
    if risk == 'history_use':
        for policy in ['semantic-planning-compiler@5', POLICY]:
            with pytest.raises(SemanticPlanningError, match='分类仍有歧义'):
                assemble_requirements(original, scope['mode'], [response], canonical=scope['canonical'], compiler_policy=policy)
            fixed = deepcopy(response); fixed['classifications'][5]['kind'] = expected['independent_reasonable_counterfactual_kind']
            bound = assemble_requirements(original, scope['mode'], [fixed], canonical=scope['canonical'], compiler_policy=policy)
            function = [c for c in bound[original.needs[0].need_id]['clauses'] if c['path']=='intent/function']
            assert len(function)==1 and function[0]['kind']=='postproduction'
        if evidence: evidence.note('actual vs independent reasonable contrast', {'wire':'PASS','actual usable contract':'FAIL unresolved','independent fixed use kind':'postproduction','granularity defect proven':False})
    elif risk == 'use_contrasts':
        for row in expected['contrasts']:
            d = semantic_draft(); n=d['needs'][0]; n['intent']={'description':'原素材中有两张白纸。','function':row['text']}
            if row.get('modality'):n['modality_spec']={'kind':row['modality']}
            if row['kind']=='preference':n['constraints']={'preferred_visual_details':row['soft_source']}
            plan=compile_input(d);batch=classification_batches(plan,{})[0]
            fixed={'classifications':[{'id':u['id'],'kind':row['kind'] if batch['contexts'][u['need']]['input']['sources'][u['source']]['path']=='intent/function' else 'required',
                'preference_source':0 if row['kind']=='preference' and batch['contexts'][u['need']]['input']['sources'][u['source']]['path']=='intent/function' else None} for u in batch['units']]}
            if row['kind']=='unresolved':
                with pytest.raises(SemanticPlanningError,match='歧义'):assemble_requirements(plan,{},[fixed])
            else:
                bound=assemble_requirements(plan,{},[fixed])[plan.needs[0].need_id]['clauses']
                assert next(c['kind'] for c in bound if c['path']=='intent/function')==row['kind']
        if evidence:evidence.note('independent obligation-target contrasts',expected['contrasts'])
    elif risk == 'native_use_repair':
        for name,text in scope['canonical'].items():rt['canonical'][name]=text;write_file(rt['root'],name,text.encode(),replace=True)
        fixed=deepcopy(response);fixed['classifications'][5]['kind']='postproduction'
        def execute(stage,message,session):
            import re
            data=json.loads(message.splitlines()[-1]);rt['calls'].append({'stage':stage,'session':session,'message':message})
            assert data['review_target']['schema']=='material-review-target@3'
            assert data['review_target']['relation_rules']['asset_intrinsic_vs_timeline_use']=='classify_obligation_target_not_repeated_subject_or_field'
            assert data['review_target']['counterfactual']['scope']=='obligation_target_not_editability'
            if message.startswith('〔Easel Semantic'):
                out=json.loads((folder/'A-original.json').read_text());target=Path(re.search(r'只写 (.+\.json)',message)[1])
            elif '单元分类' in message:
                assert 'output_schema' in data;out=response;target=Path(re.search(r'只写 (.+\.json)',message)[1])
            else:
                out={'batches':[{'index':0,**fixed}]};target=Path(data['output_paths'][data['targets'][0]])
                assert data['context']['batches'][0]['review_target']==data['review_target']
            target.write_bytes(encode(out))
        result=rt['run'](execute);saved=PlanningIntegration().persist(rt['attempt'],**{k:result[k] for k in ('plan','script','scenes','treatment')})
        assert PlanningIntegration().load(saved['attempt'])['plan']==result['plan']
        assert rt['run'](execute)['plan']==result['plan'] and len(rt['calls'])==3
        if evidence:evidence.note('fixed external answers',{'persist/reload/reentry':'PASS','model semantics proven':False,'Supply':0})
    elif risk == 'old_v5_checkpoint':
        batches=classification_batches(original,scope['mode'],canonical=scope['canonical'],compiler_policy='semantic-planning-compiler@5')
        actual=json.loads((folder/'B-request-original.txt').read_text().splitlines()[-1])
        assert json.loads(encode(batches))==[actual] and 'output_schema' in batches[0]
        # No successful real @5 freeze exists. Derive a clearly offline legal
        # @5 freeze with real internals from the independent genuine @4 inputs.
        oldfolder=FIXTURE/'batch07';cp=json.loads((oldfolder/'legal-checkpoint-original.json').read_text());sc=deepcopy(cp['scope']);sc['policy']='semantic-planning-compiler@5'
        raw=(oldfolder/'legal-A-original.json').read_bytes()
        plan=compile_draft(raw,creation_id=sc['creation_id'],attempt_id=sc['attempt_id'],refs=sc['context_refs'],mode=sc['mode'],script=sc['canonical']['SCRIPT.md'],allowed_refs=sc['catalog'],compiler_policy=sc['policy'])
        bs=classification_batches(plan,sc['mode'],canonical=sc['canonical'],compiler_policy=sc['policy']);req=assemble_requirements(plan,sc['mode'],cp['responses'],canonical=sc['canonical'],compiler_policy=sc['policy'])
        cp.update(scope=sc,plan=plan.model_dump(mode='json'),policy=sc['policy'],batches_sha256=digest(bs))
        root=rt['root']/'old-v5';(root/'planning').mkdir(parents=True)
        for name,raw in [('SEMANTIC_CHECKPOINT.json',encode(cp)),('SEMANTIC_PLAN.json',raw),('MATERIAL_REQUIREMENTS.json',encode(req))]:write_file(root,name,raw)
        for name,text in sc['canonical'].items():write_file(root,name,text.encode())
        assert verify_semantic_checkpoint(root,plan,sc['mode'],sc['canonical']['SCRIPT.md'])['policy']==sc['policy']
        if evidence:evidence.note('old @5 evidence types',{'exact_actual_batch':'PASS','valid_checkpoint':'offline derived, not real historical PASS'})
    else:
        assert POLICY=='semantic-planning-compiler@6'
        old=compile_input(compiler_policy='semantic-planning-compiler@5');new=compile_input()
        before=classification_batches(old,{},compiler_policy='semantic-planning-compiler@5')[0];after=classification_batches(new,{})[0]
        assert before['review_target']['schema']=='material-review-target@2' and after['review_target']['schema']=='material-review-target@3'
        assert 'output_schema' in before and 'output_schema' in after and old.plan_id!=new.plan_id and before['batch_id']!=after['batch_id']
        state={'schema':'semantic-planning-checkpoint@1','scope':{'policy':'semantic-planning-compiler@5','creation_id':rt['attempt']['creation_id'],'attempt_id':rt['attempt']['attempt_id']},'route':{'profile':'fixture-only','thinking':'off','timeout':60},'calls':{'B0':{'status':'pending','message':'original v5 request'}},'repair_used':True}
        store=AttemptMaterialStore(rt['root']);store.write_recovery_record('semantic-planning-v3',state)
        with pytest.raises(SemanticPlanningError,match='版本'):rt['run']()
        assert not rt['calls'] and store.read_recovery_record('semantic-planning-v3')==state


@pytest.mark.parametrize('risk', ['complete', 'length', 'no_result', 'invalid', 'persist_failure', 'pending'])
def test_vnext_capture_transport(prep_env, tmp_path, risk):
    import subprocess
    from tests.test_creation_preparation import _confirmed_delivery
    from easel import creation
    from easel.creation_delivery import active_delivery, DeliveryExecutionUncertain
    from easel.integrations.openclaw_delivery import run_delivery_agent, PlanningResultError
    from easel.integrations.planning_capture import capture, persist_captured
    work = _confirmed_delivery()
    methods, run_id, calls = [], None, {}
    reply = '{"decision":"ACCEPT"}' if risk != 'invalid' else '{'
    pending = risk == 'pending'

    def gateway(command, **kwargs):
        nonlocal run_id, pending
        method = command[command.index('call')+1]
        params = json.loads(command[command.index('--params')+1]); methods.append(method)
        if method == 'agent':
            run_id = params['idempotencyKey']; payload = {'runId': run_id, 'status': 'accepted'}
        elif method == 'sessions.abort':
            payload = {'ok': True, 'status': 'no-active-run', 'abortedRunId': None}
        elif pending:
            pending = False; payload = {'runId': run_id, 'status': 'pending'}
        else:
            payload = {'runId': run_id, 'status': 'ok', 'endedAt': 1000,
                       'stopReason': 'length' if risk == 'length' else 'stop'}
            if risk != 'no_result': payload['terminalReply'] = {'disposition': 'visible', 'text': reply}
        return subprocess.CompletedProcess(command, 0, json.dumps(payload), '')

    def dispatch(key, message, session):
        cmd = ['openclaw', '--profile', 'fixture', 'agent', '--agent', 'main',
               '--session-key', session, '--message', message]
        return run_delivery_agent(cmd, runner=gateway, capture_reply=True,
                                  reply_contract='planning-result-v1', retry_failed=False).stdout

    saves = []
    save = lambda: saves.append(json.loads(json.dumps(calls)))
    token = active_delivery.set(work['id'])
    try:
        with pytest.raises(DeliveryExecutionUncertain):
            capture(calls, 'A', 'compact', 'vnext', dispatch, save)
        if risk == 'pending':
            with pytest.raises(DeliveryExecutionUncertain): capture(calls, 'A', 'compact', 'vnext', dispatch, save)
            assert calls['A']['result'] == 'TRANSPORT_FAILED'
        if risk in {'length', 'no_result', 'invalid'}:
            expected = {'length': 'MODEL_TRUNCATED', 'no_result': 'MODEL_NO_RESULT',
                        'invalid': 'STRUCTURED_OUTPUT_INVALID'}[risk]
            for _ in range(2):
                with pytest.raises(PlanningResultError, match=expected):
                    capture(calls, 'A', 'compact', 'vnext', dispatch, save)
            assert calls['A']['result'] == expected
        else:
            assert capture(calls, 'A', 'compact', 'vnext', dispatch, save) == {'decision': 'ACCEPT'}
            assert calls['A']['result'] == 'MODEL_COMPLETED'
            if risk == 'persist_failure':
                def broken(raw): raise OSError('disk full')
                with pytest.raises(OSError): persist_captured(calls, 'A', broken, save)
                assert calls['A']['result'] == 'PERSIST_FAILED'
            output = tmp_path/'captured.json'
            persist_captured(calls, 'A', output.write_bytes, save)
            assert output.read_text() == reply and calls['A']['result'] == 'ACCEPTED'
            assert capture(calls, 'A', 'compact', 'vnext', dispatch, save) == {'decision': 'ACCEPT'}
        assert methods.count('agent') == 1
        native = next(iter(creation.get_creation(work['id'])['delivery']['agent_calls'].values()))
        assert native['reply_contract'] == 'planning-result-v1'
        assert 'compact' not in native.values()
    finally:
        active_delivery.reset(token)


def vnext_capacity_payload(stage):
    from easel.integrations.planning_result_contract import SemanticProposal, ReviewResponse
    text = ('画面与留白🖼️。' * 500)[:2000]
    if stage == 'A':
        value = {'needs':[{'scope':'scene-1','role':'背景','modality':'video',
            'necessity':'required','conditions':[{'text':text,'strength':'required',
                'responsibility':'material'} for _ in range(12)],
            'queries':['white paper table','blank page desk','empty document closeup'],
            'frame':'match_output','purpose':text,'visual_preference':text[:200],
            'source_seconds':3600} for _ in range(16)]}
        return SemanticProposal.model_validate(value).model_dump_json()
    return ReviewResponse.model_validate({'answers':[{'question':i,'decision':'ACCEPT',
        'evidence':list(range(16)),'reason':text} for i in range(48)]}).model_dump_json()


def test_vnext_tool_schema_matches_frozen_choices_and_existing_modality_rules():
    """Prompt schema must expose rules already enforced by the real consumer."""
    import copy
    from jsonschema import Draft202012Validator
    from easel.integrations.planning_result_contract import semantic_tool_schema, result_schema
    from easel.integrations.semantic_boundary import parse_proposal
    catalog = {'global': {'global': '全部场景'}, 'scene': {'scene-1': '白纸'},
               'segment': {}, 'event': {}, 'continuity': {'paper': {'kind': 'object'}, 'untyped': {}},
               'voice': {'creator_context.voice': {}}}
    original_catalog = copy.deepcopy(catalog)
    original_schema = result_schema('A')
    schema = semantic_tool_schema(catalog)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    base = {'scope': 'scene-1', 'role': '背景', 'modality': 'image', 'necessity': 'required',
            'conditions': [{'text': '一张白纸', 'strength': 'required', 'responsibility': 'material'}]}
    cases = [
        ({}, True), ({'necessity': 'optional'}, True),
        ({'frame': 'native', 'native_ratio': '9:16'}, True),
        ({'continuity_choices': ['paper']}, True),
        ({'modality': 'video', 'source_seconds': 15}, True),
        ({'modality': 'voice', 'voice_choice': 'creator_context.voice'}, True),
        ({'modality': 'bgm', 'sound': {'mood': '宁静'}}, True),
        ({'modality': 'sfx', 'sound': {'event_description': '倒水'}}, True),
        ({'scope': 'invented'}, False), ({'source_seconds': 15}, False),
        ({'native_ratio': '9:16'}, False), ({'frame': 'native'}, False),
        ({'voice_choice': 'creator_context.voice'}, False),
        ({'continuity_choices': ['invented']}, False),
        ({'continuity_choices': ['untyped']}, False),
        ({'modality': 'voice', 'voice_choice': 'invented'}, False),
        ({'modality': 'voice', 'voice_choice': 'creator_context.voice', 'frame': 'native',
          'native_ratio': '9:16'}, False),
        ({'modality': 'bgm'}, False),
        ({'modality': 'bgm', 'sound': {'event_description': '倒水'}}, False),
        ({'modality': 'sfx', 'sound': {'mood': '宁静'}}, False),
        ({'modality': 'sfx', 'sound': {'event_description': '倒水', 'vocals_allowed': True}}, False),
        ({'queries': ['one']}, False), ({'queries': ['纸张', 'white paper', 'blank page']}, False),
        ({'conditions': [{'text': '连续倒水', 'strength': 'required',
                         'responsibility': 'material', 'meaning': 'dynamic_action'}]}, False),
    ]
    for changes, expected in cases:
        value = {'needs': [{**copy.deepcopy(base), **changes}]}
        if changes.get('necessity') == 'optional':
            value['needs'].append(copy.deepcopy(base))
        assert validator.is_valid(value) == expected, changes
        try:
            parse_proposal(value, catalog)
            accepted = True
        except ValueError:
            accepted = False
        assert accepted == expected, changes
    # Schemas are per-request; an empty directory cannot become an arbitrary string.
    empty = {**catalog, 'voice': {}, 'continuity': {}}
    empty_validator = Draft202012Validator(semantic_tool_schema(empty))
    assert empty_validator.is_valid({'needs': [base]})
    assert not empty_validator.is_valid({'needs': [{**base, 'continuity_choices': ['paper']}]})
    assert not empty_validator.is_valid({'needs': [{**base, 'modality': 'voice',
        'voice_choice': 'creator_context.voice'}]})
    # Legal maximum capacity remains valid; do not trim conditions or shorten text.
    assert validator.is_valid(json.loads(vnext_capacity_payload('A')))
    assert catalog == original_catalog and result_schema('A') == original_schema


@pytest.mark.parametrize('risk', ['A', 'B', 'repair_capacity', 'preview', 'length',
    'identity', 'late', 'missing', 'lost_terminal', 'duplicate_json', 'persist_failure',
    'input_os_capacity', 'escaped_secret', 'sensitive_key',
    'tool_valid', 'tool_wrong_name', 'tool_wrong_schema', 'tool_wrong_terminal',
    'tool_runtime_upgrade', 'tool_runtime_readback'])
def test_vnext_full_capture(prep_env, tmp_path, risk):
    import hashlib
    import subprocess
    from tests.test_creation_preparation import _confirmed_delivery
    from easel import creation
    from easel.creation_delivery import active_delivery, DeliveryExecutionUncertain
    from easel.integrations.openclaw_delivery import run_delivery_agent, PlanningResultError
    from easel.integrations.planning_capture import capture, persist_captured
    from easel.integrations.planning_result_contract import MAX_RESULT_BYTES, maximum_compact_bytes, result_schema
    from easel.integrations.planning_structured import request_for
    structured = request_for(result_schema('A')) if risk.startswith('tool_') else None
    for stage in ('A','B'):
        assert maximum_compact_bytes(result_schema(stage)) < MAX_RESULT_BYTES
    reply = vnext_capacity_payload('B' if risk == 'B' else 'A')
    if risk == 'repair_capacity': reply += ' ' * (MAX_RESULT_BYTES-len(reply.encode()))
    if risk == 'duplicate_json': reply = '{"needs":[],"needs":[]}'
    if risk == 'sensitive_key': reply = json.dumps({'api_key':'synthetic-credential-value'})
    if risk == 'escaped_secret':
        reply = '{"purpose":"' + r'\u0073\u006b-' + 'x'*16 + '"}'
        from easel.integrations.hypit.secrets import SecretRedactor
        assert not SecretRedactor.contains_secret(reply)  # Old raw scan misses it.
        assert SecretRedactor.contains_secret(json.loads(reply))
    methods, read_count, run_id, saved = [], 0, None, {}
    session_id = 'fixture-session'
    work = _confirmed_delivery()
    def gateway(command, **kwargs):
        nonlocal run_id
        method=command[command.index('call')+1]; methods.append(method)
        params=json.loads(command[command.index('--params')+1])
        if method=='agent':
            assert params.get('easelStructuredResult') == structured
            run_id=params['idempotencyKey']; result={'runId':run_id,'status':'accepted'}
        elif method=='sessions.abort': result={'ok':True,'status':'no-active-run'}
        else:
            result={'runId':run_id,'status':'ok','endedAt':1000,'stopReason':'stop',
                'terminalReply':{'disposition':'visible','text':'preview…'}}
            if structured and risk != 'tool_wrong_terminal': result['stopReason'] = 'tool_calls'
            if risk != 'lost_terminal': result['terminalReceipt']={
                'runId':run_id,'sessionId':session_id,'turnId':run_id,
                'effective':{'provider':'offline','model':'fixture'}}
        return subprocess.CompletedProcess(command,0,json.dumps(result),'')
    def transcript(*args, **kwargs):
        nonlocal read_count
        read_count+=1
        if risk == 'late' and read_count==1 or risk=='missing': return {'state':'MISSING'}
        value = {'state':'FOUND','runId':run_id if risk!='identity' else 'another-run',
            'sessionId':session_id,'text':reply,'sha256':hashlib.sha256(reply.encode()).hexdigest(),
            'bytes':len(reply.encode()),'stopReason':'length' if risk=='length' else 'stop',
            'messageId':'original-message','sequence':10,'runtimeVersion':'2026.9.4'}
        if structured:
            value.update(stopReason='toolUse', providerFinishReason='tool_calls', toolCallId='original-tool-id',
                toolName='exec' if risk == 'tool_wrong_name' else structured['name'],
                schemaSha256='wrong' if risk == 'tool_wrong_schema' else structured['schemaSha256'])
        return value
    expected_runtime = [None]
    if risk == 'tool_runtime_upgrade': expected_runtime[0] = '0' * 64
    def dispatch(key,message,session):
        return run_delivery_agent(['openclaw','--profile','fixture','agent','--agent','main',
            '--session-key','agent:main:'+session,'--session-id',session_id,'--message',message],
            runner=gateway,capture_reply=True,reply_contract='planning-result-v3' if structured else 'planning-result-v2',
            structured_result=structured, expected_runtime_sha256=expected_runtime[0],
            transcript_reader=transcript,retry_failed=False).stdout
    token=active_delivery.set(work['id'])
    try:
        if risk == 'tool_runtime_upgrade':
            before = creation.get_creation(work['id'])['delivery']
            with pytest.raises(ValueError, match='Frozen Planning Runtime'):
                capture(saved, 'A', 'frozen input', 'new-vnext', dispatch, lambda: None)
            assert not methods and creation.get_creation(work['id'])['delivery'] == before
            return
        if risk == 'input_os_capacity':
            # Within raw input budget, but escaped JSON exceeds the real argv budget.
            before=creation.get_creation(work['id'])['delivery']
            with pytest.raises(PlanningResultError,match='CONTRACT_REJECTED'):
                capture(saved,'A','\"'*600000,'new-vnext',dispatch,lambda:None)
            assert creation.get_creation(work['id'])['delivery']==before
            assert not methods
            return
        for _ in range(1+(risk=='late')):
            with pytest.raises(DeliveryExecutionUncertain): capture(saved,'A','frozen input','new-vnext',dispatch,lambda:None)
        if risk == 'tool_runtime_readback': expected_runtime[0] = '0' * 64
        if risk in {'identity','lost_terminal'}:
            for _ in range(2):
                with pytest.raises(DeliveryExecutionUncertain): capture(saved,'A','frozen input','new-vnext',dispatch,lambda:None)
        elif risk in {'length','duplicate_json','missing','escaped_secret','sensitive_key',
                      'tool_wrong_name','tool_wrong_schema','tool_wrong_terminal'}:
            if risk=='missing':
                for _ in range(2):
                    with pytest.raises(DeliveryExecutionUncertain): capture(saved,'A','frozen input','new-vnext',dispatch,lambda:None)
            expected={'length':'MODEL_TRUNCATED','missing':'MODEL_NO_RESULT'}.get(risk,'STRUCTURED_OUTPUT_INVALID')
            with pytest.raises(PlanningResultError,match=expected): capture(saved,'A','frozen input','new-vnext',dispatch,lambda:None)
            if risk in {'escaped_secret','sensitive_key','duplicate_json'}:
                assert 'reply' not in saved['A']
                native=next(iter(creation.get_creation(work['id'])['delivery']['agent_calls'].values()))
                assert 'terminal_reply' not in native
                with pytest.raises(PlanningResultError,match=expected): capture(saved,'A','frozen input','new-vnext',dispatch,lambda:None)
        else:
            value=capture(saved,'A','frozen input','new-vnext',dispatch,lambda:None)
            assert value==json.loads(reply) and saved['A']['reply']==reply
            if risk=='persist_failure':
                def broken(raw): raise OSError('isolated disk failure')
                with pytest.raises(OSError): persist_captured(saved,'A',broken,lambda:None)
            output=tmp_path/'program-result.json'
            persist_captured(saved,'A',output.write_bytes,lambda:None)
            before=read_count
            assert capture(saved,'A','frozen input','new-vnext',dispatch,lambda:None)==value
            assert output.read_bytes()==reply.encode() and read_count==before
            native=next(iter(creation.get_creation(work['id'])['delivery']['agent_calls'].values()))
            assert native['result_source']['kind']=='readonly-active-transcript'
            assert native['terminal_reply']['text']==reply
        assert methods.count('agent')==1
    finally: active_delivery.reset(token)


@pytest.mark.parametrize('risk', ['entities', 'aliases', 'duration', 'scope_integrity'])
def test_vnext_canonical_facts(risk):
    from easel.integrations.planning_facts import bind_facts, fact_value, project_asset
    scope = json.loads((FIXTURE / 'batch09/scope-original.json').read_text())
    inputs = {'schema': 'planning-authority-inputs@1', 'confirmed': scope['canonical'],
              'proposal': {'specs': {key: value for key, value in json.loads(
                  (FIXTURE / 'batch09/production-brief-original.json').read_text()).items()
                  if key in {'aspect_ratio', 'duration_seconds', 'audio_mode', 'language'}}},
              'mode_documents': {'mode.json': json.dumps(scope['mode'])}}
    bound = bind_facts(inputs)
    assert bind_facts(json.loads(json.dumps(inputs))) == bound
    final_ratio = fact_value(bound, 'final_output', 'frame')
    assert final_ratio == '9:16'
    if risk == 'entities':
        free = project_asset(bound, kind='image')
        assert 'aspect_ratio' not in free['modality_spec'] and free['duration_hint'] is None
        assert project_asset(bound, kind='video')['media_type'] == 'video'
        assert fact_value(bound, 'final_output', 'audio_mode') == 'silent'
    elif risk == 'aliases':
        derived = project_asset(bound, kind='image', frame='match_output')
        assert derived['modality_spec']['aspect_ratio'] == final_ratio
        assert not {'aspect_ratio', 'media_type', 'visual_style'} & derived['constraints'].keys()
        assert derived['modality_spec']['visual_style'] == derived['constraints']['preferred_style']
        with pytest.raises(ValueError, match='alias'):
            project_asset(bound, kind='image', native_ratio='9:16')
    elif risk == 'duration':
        assert project_asset(bound, kind='video', source_seconds=3)['duration_hint'] == {'target_seconds': 3}
        assert fact_value(bound, 'final_output', 'duration') == 15
        with pytest.raises(ValueError, match='time-based'):
            project_asset(bound, kind='image', source_seconds=15)
    else:
        changed = deepcopy(inputs); changed['confirmed']['SCENES.md'] += '不得出现文字。'
        assert bind_facts(changed)['sha256'] != bound['sha256']
        assert all(row['authority'] != 'candidate' for row in bound['facts'])


@pytest.mark.parametrize('risk', ['history', 'basis_transport', 'scalar_controls', 'catalog_eligibility',
                                'operational_origin', 'control_guard', 'creative_contrast', 'verified_loader'])
def test_batch09_hard_authority_baseline(semantic_runtime, risk, evidence=None):
    """Actual source integrity and formal admission are not semantic authority.

    The two new guard expectations intentionally expose the pre-change gap.
    They do not rewrite the old @6 contract or rescore its historical FAIL.
    """
    folder = FIXTURE / 'batch09'
    scope = json.loads((folder / 'scope-original.json').read_text())
    raw = (folder / 'A-original.json').read_bytes()
    response = json.loads((folder / 'B-original.json').read_text())
    plan = compile_draft(raw, creation_id=scope['creation_id'], attempt_id=scope['attempt_id'],
        refs=scope['context_refs'], mode=scope['mode'], script=scope['canonical']['SCRIPT.md'],
        allowed_refs=scope['catalog'], compiler_policy=scope['policy'])
    requirements = assemble_requirements(plan, scope['mode'], [response],
        canonical=scope['canonical'], compiler_policy=scope['policy'])
    expected = json.loads((folder / 'expected.json').read_text())
    bad_text = {row['text'] for row in expected['actual_failed_clauses']}
    if risk == 'history':
        assert plan == MaterialPlan.model_validate_json((folder / 'Plan-original.json').read_bytes())
        assert requirements == json.loads((folder / 'Requirements-original.json').read_text())
        assert len(planning_contracts(plan, scope['mode'], requirements)) == 1
        hard = {clause['text'] for row in requirements.values() for clause in row['clauses']
                if clause['kind'] == 'required'}
        assert bad_text <= hard and expected['status'] == 'FAIL'
        assert expected['required_omissions'] == expected['required_downgrades'] == 0
        assert all(text not in ''.join(scope['canonical'].values()) for text in bad_text)
        for name, meta in json.loads((folder / 'provenance.json').read_text())['files'].items():
            import hashlib
            assert hashlib.sha256((folder / name).read_bytes()).hexdigest() == meta['sha256']
        if evidence: evidence.note('historical formal / independent semantic', 'PASS / FAIL; original bytes unchanged')
        return
    if risk in {'catalog_eligibility', 'operational_origin', 'control_guard', 'creative_contrast', 'verified_loader'}:
        from easel.integrations import planning_authority as authority
        from easel.integrations.semantic_planning import parse_draft
        import jsonschema
        inputs = {'schema': 'planning-authority-inputs@1', 'handoff_sha256': 'offline-fixture-only',
            'confirmed': scope['canonical'], 'proposal': None,
            'preparation': json.loads((folder / 'production-brief-original.json').read_text()),
            'creator_context': json.loads((folder / 'creator-context-original.json').read_text()),
            'truth_packet': json.loads((folder / 'truth-packet-original.json').read_text()),
            'mode_documents': {'mode.json': (folder / 'mode-original.json').read_text(),
                'visual-bible.md': (folder / 'visual-bible-original.md').read_text(),
                'director-treatment.md': (folder / 'director-treatment-original.md').read_text()}}
        directory = authority.catalog(inputs)
        scene = next(s['id'] for s in directory['sources'] if s['origin'] == 'confirmed_scene')
        style = next(s['id'] for s in directory['sources'] if s['origin'] == 'mode_soft')
        private = next(s['id'] for s in directory['sources'] if s['origin'] == 'derived_creator_context')
        preparation = next(s['id'] for s in directory['sources'] if s['origin'] == 'derived_preparation')
        def basis(relation, ids): return {'relation': relation, 'source_ids': ids}
        if risk == 'catalog_eligibility':
            assert directory == authority.catalog(inputs)
            assert not any(s['origin'] == 'candidate' for s in directory['sources'])
            for ids in ([], [style], [private], [preparation], [scene, private], [scene, preparation],
                        [scene, scene], [99999], [True]):
                with pytest.raises(ValueError): authority.validate_basis(basis('upstream_obligation', ids), directory,
                    'scene-1', kind='required')
            with pytest.raises(ValueError): authority.validate_basis(basis('upstream_obligation', [scene]),
                directory, 'scene-2', kind='required')
            authority.validate_basis(basis('upstream_obligation', [scene]), directory, 'scene-1', kind='required')
            authority.validate_basis(basis('preference', []), directory, 'scene-1', kind='preference')
            jsonschema.Draft202012Validator.check_schema(authority.basis_schema(directory, 'scene-1'))
        elif risk == 'operational_origin':
            explicit = semantic_draft()
            explicit['needs'][0]['desired_options'] = 1
            omitted = deepcopy(explicit); omitted['needs'][0].pop('desired_options')
            a = parse_draft(explicit); b = parse_draft(omitted)
            p = compile_input(explicit)
            assert not any(op['path'] == 'desired_options' for op in authority.applied_operations(a, p, {}))
            operations = authority.applied_operations(b, p, {})
            record = next(op for op in operations if op['path'] == 'desired_options')
            assert record['input'] == {'field_absent': True} and record['value'] == 1
            traced = authority.catalog(inputs, operations)
            source = next(s['id'] for s in traced['sources'] if s.get('operation', {}).get('path') == 'desired_options')
            control = next(c for c in authority.control_rows(p.needs[0], 0) if c['path'] == 'desired_options')
            authority.validate_basis(basis('operational', [source]), traced, 'scene-1', kind='ACCEPT', control=control)
            for wrong in (dict(control, path='constraints/screens'), dict(control, need_index=1),
                          dict(control, value=1.0, value_sha256=authority.digest(1.0))):
                with pytest.raises(ValueError): authority.validate_basis(basis('operational', [source]), traced,
                    'scene-1', kind='ACCEPT', control=wrong)
            with pytest.raises(ValueError): authority.validate_basis(basis('operational', [source]),
                traced, 'scene-1', kind='required')
        elif risk == 'control_guard':
            candidate = json.loads(raw); candidate['needs'][0]['constraints']['screens'] = False
            p = compile_draft(candidate, creation_id='control', attempt_id='control-a', refs={},
                mode=scope['mode'], script=scope['canonical']['SCRIPT.md'], allowed_refs=scope['catalog'])
            control = next(c for c in authority.control_rows(p.needs[0], 0) if c['path'] == 'constraints/screens')
            from easel.materials.application.compiler import NeedCompiler
            assert NeedCompiler().compile(p.needs[0]).filters['screens'] is False
            for relation, ids in [('preference', [style]), ('postproduction', []),
                                  ('operational', []), ('upstream_obligation', [private])]:
                with pytest.raises(ValueError): authority.validate_basis(basis(relation, ids), directory,
                    'scene-1', kind='ACCEPT', control=control)
            with pytest.raises(ValueError): authority.validate_basis(basis('unresolved', []), directory,
                'scene-1', kind='UNRESOLVED', control=control)
            for path in ('importance', 'desired_options', 'modality/kind', 'modality/aspect_ratio'):
                assert any(c['path'] == path for c in authority.control_rows(p.needs[0], 0))
            assert p.needs[0].constraints['screens'] is False, 'rejection does not delete the hard filter'
        elif risk == 'creative_contrast':
            goal = next(s['id'] for s in directory['sources'] if s['origin'] == 'confirmed_treatment'
                        and '主观创作意图' in s['text'])
            authority.validate_basis(basis('director_realization', [goal]), directory, 'scene-1', kind='required')
            # Both the legitimate cup choice and the unsupported screen ban can
            # have a structurally legal goal reference. This is not an oracle.
            legitimate = semantic_draft(); legitimate['needs'][0]['intent']['description'] = '桌上一只空杯表达停顿。'
            assert compile_input(legitimate).needs[0].importance.value == 'required'
            assert '杯' not in scope['canonical']['SCENES.md']
            assert expected['status'] == 'FAIL' and bad_text
            if evidence: evidence.note('semantic boundary', 'legal goal ID is not proof; actual banned-screen realization remains FAIL')
        else:
            rt = semantic_runtime
            package = rt['root'] / 'handoff'
            actual = {'context_refs': rt['context']['context_refs'],
                'creator_context': json.loads((package / 'creator-context.json').read_text()),
                'truth_packet': json.loads((package / 'truth-packet.json').read_text()),
                'content_core': json.loads((package / 'content-core.json').read_text())}
            loaded = authority.load_inputs(rt['attempt'], rt['canonical'], actual, rt['mode'])
            assert loaded['creator_context'] == actual['creator_context']
            assert loaded['mode_documents']['mode.json'] == (package / 'creative-mode/mode.json').read_text()
            for changed_context in (dict(actual, creator_context={}),
                    dict(actual, context_refs={**actual['context_refs'], 'production_brief_sha256': 'bare-sha'})):
                with pytest.raises(ValueError): authority.load_inputs(rt['attempt'], rt['canonical'], changed_context, rt['mode'])
            with pytest.raises(ValueError): authority.load_inputs(rt['attempt'], rt['canonical'], actual, {**rt['mode'], 'name': 'global-current-version'})
            with pytest.raises(ValueError): authority.load_inputs(rt['attempt'],
                {**rt['canonical'], 'SCENES.md': 'new unconfirmed scene'}, actual, rt['mode'])
            from easel.integrations.hypit.errors import HypitIntegrationError
            with pytest.raises(HypitIntegrationError): authority.load_inputs(
                {**rt['attempt'], 'handoff': {**rt['attempt']['handoff'], 'hash': 'wrong-hash'}},
                rt['canonical'], actual, rt['mode'])
            target = package / 'creative-mode/visual-bible.md'
            original = target.read_bytes()
            target.chmod(0o600)
            target.write_bytes(original + b'\nchanged')
            with pytest.raises(HypitIntegrationError): authority.load_inputs(rt['attempt'], rt['canonical'], actual, rt['mode'])
            target.write_bytes(original); target.chmod(0o444)
        if evidence: evidence.note(risk, 'authority component invariants executed; product wiring not yet accepted')
        return
    # Explicit @7 offline contract projection; never rescore the actual @6 run.
    from easel.integrations import planning_authority as authority
    from easel.integrations.semantic_planning import AUTHORITY_POLICY, parse_draft
    inputs = {'schema':'planning-authority-inputs@1', 'handoff_sha256':'offline-fixture-only',
        'confirmed':scope['canonical'], 'proposal':None, 'preparation':None,
        'mode_documents':{'mode.json':json.dumps(scope['mode'])}}
    current = compile_draft(raw, creation_id='synthetic-authority', attempt_id='synthetic-authority-a',
        refs=scope['context_refs'], mode=scope['mode'], script=scope['canonical']['SCRIPT.md'],
        allowed_refs=scope['catalog'], compiler_policy=AUTHORITY_POLICY, authority_inputs=inputs)
    directory=authority.catalog(inputs,authority.applied_operations(parse_draft(raw),current,scope['mode']))
    batch = classification_batches(current, scope['mode'], canonical=scope['canonical'],
        compiler_policy=AUTHORITY_POLICY,authority_catalog=directory)[0]
    if risk == 'basis_transport':
        row = batch['output_schema']['properties']['classifications']['prefixItems'][0]
        assert 'basis' in row['required'], 'current B wire contract has no independent upstream basis'
        assert batch.get('authority_catalog'), 'A frozen candidate is not its own upstream authority'
    elif risk == 'scalar_controls':
        changed = json.loads(raw)
        changed['needs'][0]['constraints']['screens'] = False
        controlled = compile_draft(changed, creation_id='synthetic-controls', attempt_id='synthetic-controls-a',
            refs=scope['context_refs'], mode=scope['mode'], script=scope['canonical']['SCRIPT.md'],
            allowed_refs=scope['catalog'],compiler_policy=AUTHORITY_POLICY,authority_inputs=inputs)
        from easel.materials.application.compiler import NeedCompiler
        assert NeedCompiler().compile(controlled.needs[0]).filters['screens'] is False
        if evidence: evidence.note('actual retrieval side effect', 'constraints/screens=false is a hard filter')
        directory=authority.catalog(inputs,authority.applied_operations(parse_draft(changed),controlled,scope['mode']))
        batches = classification_batches(controlled, scope['mode'], canonical=scope['canonical'],
            compiler_policy=AUTHORITY_POLICY,authority_catalog=directory)
        reviewed = [control for b in batches for control in b.get('controls', [])]
        assert any(unit.get('path') == 'constraints/screens' for unit in reviewed), \
            'scalar false reaches retrieval filters without being a classified source'
    else:
        raise AssertionError('unknown authority baseline risk')


@pytest.mark.parametrize('risk', ['mixed_projection', 'source_frame', 'identity_cache', 'forbidden_aliases', 'real_audio_postproduction'])
def test_vnext_semantic_projection(risk):
    from easel.integrations.semantic_boundary import parse_proposal, project_proposal
    from easel.materials.application.compiler import NeedCompiler
    from easel.materials.application.visual_contract import planning_contracts
    from easel.integrations.planning_result_contract import maximum_compact_bytes, result_schema, MAX_RESULT_BYTES
    scope=json.loads((FIXTURE/'batch09/scope-original.json').read_text())
    brief=json.loads((FIXTURE/'batch09/production-brief-original.json').read_text())
    inputs={'schema':'planning-authority-inputs@1','confirmed':scope['canonical'],
        'proposal':{'specs':{key:value for key,value in brief.items()
            if key in {'aspect_ratio','duration_seconds','audio_mode','language'}}},
        'mode_documents':{'mode.json':json.dumps(scope['mode'])}}
    item={'scope':'scene-1','role':'背景','modality':'image','necessity':'required',
        'conditions':[{'text':'桌上有两张白纸。','strength':'required','responsibility':'material'},
            {'text':'留白，以便后期叠字。','strength':'preference','responsibility':'material'},
            {'text':'后期叠加正文。','strength':'required','responsibility':'postproduction'},
            {'text':'不虚构两张纸的来由。','strength':'required','responsibility':'narrative'}]}
    value={'needs':[item]}
    def compile(value, **overrides):
        proposal=parse_proposal(value,scope['catalog'])
        return project_proposal(proposal,inputs=inputs,catalog=scope['catalog'],
            creation_id=scope['creation_id'],attempt_id=overrides.get('attempt_id',scope['attempt_id']),
            refs=scope['context_refs'],mode=scope['mode'])
    if risk == 'real_audio_postproduction':
        from copy import deepcopy
        from easel.integrations.planning_result_contract import SemanticProposal
        real = Path(__file__).parent / 'fixtures/planning-vnext-development-2026-10-08'
        candidate = json.loads((real / 'autonomous-full-development2-A.json').read_text())
        context = json.loads((real / 'autonomous-full-development2-replay-input.json').read_text())
        # Deliberately derived isolation, never a normalized/rescored live A.
        # A's unresolved/frame failures remain in the immutable original.
        sfx = deepcopy(candidate['needs'][8])
        proposal = SemanticProposal.model_validate({'needs': [sfx]})
        # Formal revalidation now rejects this optional-only isolation before
        # projection. Preserve that rejection, and independently exercise the
        # source-obligation gate with a clearly labelled counterfactual control.
        with pytest.raises(ValueError, match='At least one required Need must remain'):
            project_proposal(proposal, inputs=context['inputs'], catalog=context['catalog'],
                creation_id='offline-creation', attempt_id='offline-attempt',
                refs=scope['context_refs'], mode=context['mode'])
        control = deepcopy(sfx)
        control['necessity'] = 'required'  # Test-only isolation, not a repaired live result.
        with pytest.raises(ValueError, match='actual source obligation'):
            project_proposal(SemanticProposal.model_validate({'needs': [control]}),
                inputs=context['inputs'], catalog=context['catalog'],
                creation_id='offline-creation', attempt_id='offline-attempt',
                refs=scope['context_refs'], mode=context['mode'])
        assert sfx == candidate['needs'][8]
        return
    if risk=='forbidden_aliases':
        for key in ('need_id','source_path','constraints','modality_spec','hash','policy'):
            with pytest.raises(ValueError): compile({'needs':[{**item,key:'invented'}]})
        with pytest.raises(ValueError,match='scope'): compile({'needs':[{**item,'scope':'unknown'}]})
        with pytest.raises(ValueError,match='Unresolved'): compile({'needs':[item],'unresolved':['源条件未知']})
        return
    if risk=='mixed_projection':
        value['needs'] += [
            {**item,'modality':'video','necessity':'optional','source_seconds':3,
                'conditions':[{'text':'原视频连续倒水。','strength':'required','responsibility':'material','meaning':'dynamic_action'}]},
            {'scope':'global','role':'旁白','modality':'voice','necessity':'required','voice_choice':'creator_context.voice',
                'voice_expression':'克制。','conditions':[{'text':'朗读已确认正文。','strength':'required','responsibility':'material'}]},
            {'scope':'global','role':'配乐','modality':'bgm','necessity':'required','sound':{'mood':'安静'},
                'conditions':[{'text':'轻柔器乐。','strength':'required','responsibility':'material'}]},
            {'scope':'event-1','role':'声音事件','modality':'sfx','necessity':'optional','sound':{'event_description':'水声'},
                'conditions':[{'text':'真实倒水声音。','strength':'required','responsibility':'material'}]}]
    elif risk=='source_frame':
        item.update(frame='native',native_ratio='4:5')
    plan,requirements,proof=compile(value)
    contracts=planning_contracts(plan,scope['mode'],requirements)
    assert len(requirements)==len(contracts)==(2 if risk=='mixed_projection' else 1)
    first=plan.needs[0]
    assert first.intent.description=='桌上有两张白纸。'
    assert first.intent.function=='后期叠加正文。\n不虚构两张纸的来由。'
    kinds={(c['text'],c['kind']) for c in requirements[first.need_id]['clauses']}
    assert ('桌上有两张白纸。','required') in kinds
    assert ('留白，以便后期叠字。','preference') in kinds
    assert ('后期叠加正文。\n不虚构两张纸的来由。','postproduction') in kinds
    intent=NeedCompiler.for_plan(plan).compile(first)
    assert 'preferred_style' not in intent.filters and 'preferred_visual_details' not in intent.filters
    assert not {'query','media_type','visual_style'} & set(first.constraints)
    assert first.duration_hint is None
    if risk=='source_frame':
        assert first.modality_spec.aspect_ratio==first.constraints['aspect_ratio']=='4:5'
        assert ('4:5','required') in kinds  # Formal observation cannot lose source framing.
    else:
        assert first.modality_spec.aspect_ratio is None and 'aspect_ratio' not in first.constraints
    if risk=='mixed_projection':
        assert [n.modality_spec.kind for n in plan.needs]==['image','video','voice','bgm','sfx']
        assert plan.needs[1].importance.value=='optional' and plan.needs[1].constraints['requires_dynamic_action']
        assert plan.needs[1].duration_hint.target_seconds==3
        assert plan.needs[2].modality_spec.text_sha256==__import__('hashlib').sha256(scope['canonical']['SCRIPT.md'].encode()).hexdigest()
        assert all('search_query_variants_en' not in n.constraints for n in plan.needs[2:])
    if risk=='identity_cache':
        same=compile(value); assert same[0]==plan and same[1]==requirements
        changed=compile(value,attempt_id='fresh-attempt')[0]; assert changed.plan_id!=plan.plan_id
        assert changed.needs[0].need_id!=first.need_id
        legacy=plan.model_copy(update={'policy':{'strategy':'bulk_first'}})
        assert 'preferred_style' in NeedCompiler.for_plan(legacy).compile(first).filters
    assert proof['identity'] and maximum_compact_bytes(result_schema('A')) < MAX_RESULT_BYTES


@pytest.mark.parametrize('origin', ['batch03', 'batch10'])
def test_vnext_historical_projection(origin):
    from easel.integrations.semantic_boundary import parse_proposal, project_proposal
    from easel.materials.application.visual_contract import planning_contracts
    from easel.materials.application.compiler import NeedCompiler
    if origin=='batch10':
        data=json.loads((Path(__file__).resolve().parents[1]/'docs/acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/batch10-projection-input.json').read_text())
        source=data['A']; scope=data['scope']; inputs=scope['authority_inputs']
        assert data['provenance']['historical_result']=='FAIL'
    else:
        source=json.loads((FIXTURE/'batch03/A-original.json').read_text())
        catalog=json.loads((FIXTURE/'batch03/catalog.json').read_text())
        # Only the structural regression has originals here; the context is
        # explicitly a derived counterfactual, not a historical successful Plan.
        scope={'catalog':catalog,'creation_id':'derived-batch03','attempt_id':'derived-batch03-a',
               'context_refs':{},'mode':{},'canonical':{'SCRIPT.md':'先看问题，再做决定。','SCENES.md':catalog['global']['global'],'TREATMENT.md':'静态背景。'}}
        inputs={'schema':'planning-authority-inputs@1','confirmed':scope['canonical'],
                'proposal':{'specs':{'aspect_ratio':'9:16'}},'mode_documents':{'mode.json':'{}'}}
    original=source['needs'][0]
    body=original['intent']['description']
    conditions=[{'text':body,'strength':'required','responsibility':'material'}]
    if origin=='batch03':
        for key in ('must_contain','must_not_contain'):
            for text in original['constraints'][key]:
                conditions.append({'text':text,'strength':'required','responsibility':'material'})
    item={'scope':original['scope']['ref'],'role':original['role'],'modality':original['modality_spec']['kind'],
          'necessity':original['importance'],'conditions':conditions,'purpose':original['intent'].get('function'),
          'frame':'match_output'}
    if origin=='batch10': item['visual_preference']=original['constraints']['visual_style']
    proposal=parse_proposal({'needs':[item]},scope['catalog'])
    plan,requirements,_=project_proposal(proposal,inputs=inputs,catalog=scope['catalog'],
        creation_id=scope['creation_id'],attempt_id=scope['attempt_id'],refs=scope['context_refs'],mode=scope['mode'])
    assert plan.policy=={'strategy':'bulk_first','semantic_compiler':'planning-semantic-boundary@1'}
    need=plan.needs[0]
    assert need.media_type.value==need.modality_spec.kind=='image'
    assert need.modality_spec.aspect_ratio==need.constraints['aspect_ratio']=='9:16'
    assert need.duration_hint is None
    assert need.intent.description=='\n'.join(c['text'] for c in conditions)
    assert not {'must_contain','must_not_contain','static','media_type','visual_style'} & need.constraints.keys()
    planning_contracts(plan,scope['mode'],requirements)
    assert 'preferred_style' not in NeedCompiler.for_plan(plan).compile(need).filters
    with pytest.raises(ValueError): parse_proposal(source,scope['catalog'])  # No old-shape migration/normalization.
    if origin=='batch03':
        # Unknown continuity cannot be erased while converting a whole proposal.
        unresolved={**item,'continuity_choices':['not-in-frozen-catalog']}
        with pytest.raises(ValueError,match='continuity'): parse_proposal({'needs':[item,unresolved]},scope['catalog'])


def vnext_proposal():
    return {'needs': [{'scope': 'scene-1', 'role': '背景', 'modality': 'image', 'necessity': 'required',
        'conditions': [{'text': '两张白纸放在桌上。', 'strength': 'required', 'responsibility': 'material'},
                       {'text': '让观众先看问题。', 'strength': 'required', 'responsibility': 'narrative'}]}]}


def staged_fixture_parts(message, value):
    """External fixed response: select visible source choices, not private lineage."""
    from copy import deepcopy
    from easel.integrations.planning_staged_proposal import StagedProposal
    from easel.integrations.planning_result_contract import semantic_tool_schema
    payload = json.loads(message.splitlines()[-1])
    view = payload.get('input_view')
    mapping = {}
    if view is None:
        catalog = payload['catalog']
    else:
        catalog = deepcopy(view['catalog'])
        document = view['inputs']['confirmed']['SCENES.md']
        text = ''.join(row['text'] for row in document['lines'])
        catalog['global'] = {'global': text}; mapping['global'] = document['whole_document']
        for kind in ('scene', 'segment', 'event'): catalog[kind] = {}
        ordinal = 0
        for row in document['lines']:
            if row['text'].strip():
                ordinal += 1
                for kind, handle in row.get('choices', {}).items():
                    original = f'{kind}-{ordinal}'
                    catalog[kind][original] = row['text'].splitlines()[0]
                    mapping[original] = handle
    selection, details, _ = StagedProposal(semantic_tool_schema(catalog, compiled=True)).encode(value)
    if view is not None:
        for row in selection['needs']:
            row['scope'] = mapping[row['scope']]
            if catalog.get('continuity') == {}:
                assert row.pop('continuity_choices') == []
    return selection, details, mapping


def staged_fixture_wire(message, value, *, invalid=None):
    """Fixed external response only; none of these responses are real model evidence."""
    from copy import deepcopy
    selection, details, mapping = staged_fixture_parts(message, value)
    if invalid == 'duplicate_voice':
        selection['needs'].append({'scope': mapping.get('global', 'global'), 'role': '旁白', 'modality': 'voice',
                                   'necessity': 'required', **({} if mapping else {'continuity_choices': []})})
    elif invalid == 'capacity':
        selection['needs'] = [deepcopy(selection['needs'][0]) for _ in range(16)]
    return json.dumps(selection if 'A-selection〕' in message else details, ensure_ascii=False)


def supported_fixture_answers(batch, answers):
    """External judgment fixture only; reference validity does not prove entailment."""
    from easel.integrations import planning_review_support as support
    if batch.get('support_policy') != support.REVISION:
        return answers
    catalog = support.source_catalog(batch)
    source, entry = next((key, row) for key, row in catalog.items()
        if row['origin'] == 'confirmed_original' and row['path'] == ['SCENES.md'])
    for answer in answers:
        answer['support'] = [{'source': source, 'quote': entry['value'][:512], 'role': 'authority'}]
        answer['evidence'] = [entry['evidence_id']]
    return answers


def fixture_review_wire(batch, answers):
    from easel.integrations import planning_review_support as support
    if batch.get('support_policy') != support.REVISION:
        return {'answers': answers}
    result = {support.slot(answer): {k: answer[k] for k in ('decision', 'support', 'reason')}
              for answer in answers}
    if batch.get('candidate_policy') == 'planning-candidate-review@2':
        # Declared external fixture relations, never a production classifier.
        candidates = batch['candidate_bindings']
        visual = [k for k, row in candidates.items() if row['value']['modality'] in {'image', 'video'}]
        by_id = {a['question']: a for a in answers}
        for question in batch['questions']:
            row = result[support.slot(question)]
            supplied = by_id[question['question']]
            if question['kind'] == 'frozen_visual_coverage':
                decision = row['decision']
                row['coverage'] = supplied.get('coverage', ('covered' if visual else 'no_material_obligation')
                    if decision == 'ACCEPT' else 'missing' if decision == 'CHALLENGE' else 'unknown')
                row['related_needs'] = supplied.get('related_needs', visual if row['coverage'] == 'covered' else [])
            elif question['kind'] == 'unresolved_classification':
                row['required_kinds'] = supplied.get('required_kinds', ['visual'] if row['decision'] == 'ACCEPT' else [])
                row['related_needs'] = supplied.get('related_needs', visual[:1] if row['decision'] == 'ACCEPT' else [])
    if 'wire_representation' in batch:
        for answer in result.values():
            for reference in answer['support']:
                value = reference['quote']
                reference['quote'] = {'null': True} if value is None else {'value': value}
    return result


def xml_reference_transport(raw, request):
    """Execute the archived public parser and official XML template, offline.

    This demonstrates a reference mechanism, not the online service's code.
    AST loading avoids installing SGLang or bypassing any production gateway.
    """
    import ast
    import hashlib
    import re
    import logging
    from jinja2 import Environment
    root = Path(__file__).parent / 'fixtures/planning-vnext-development-2026-10-08/m3-reference'
    provenance = json.loads((root / 'provenance.json').read_text())
    for row in provenance['sources']:
        assert hashlib.sha256((root / row['file']).read_bytes()).hexdigest() == row['sha256']
    tree = ast.parse((root / 'sglang_minimax_m3.py.txt').read_text())
    util = ast.parse((root / 'sglang_function_utils.py.txt').read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'MinimaxM3Detector')
    cls.bases = [ast.Name(id='object', ctx=ast.Load())]
    module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0),
        *[n for n in tree.body if isinstance(n, (ast.Assign, ast.AnnAssign))],
        next(n for n in util.body if isinstance(n, ast.FunctionDef) and n.name == 'get_schema_properties'), cls], type_ignores=[])
    namespace = {'json': json, 're': re, 'logging': logging, '__name__': 'offline_public_m3_reference'}
    exec(compile(ast.fix_missing_locations(module), 'archived-public-m3-parser', 'exec'), namespace)
    parser = object.__new__(namespace['MinimaxM3Detector'])
    template = (root / 'huggingface.co_MiniMaxAI_MiniMax-M3_raw_main_chat_template.jinja').read_text()
    render = Environment().from_string(template).make_module({'messages': [], 'tools': []}).to_xml
    xml = render(json.loads(raw), namespace['MINIMAX_NS_TOKEN'])
    return json.dumps(parser._parse_parameter(xml, request['schema']), ensure_ascii=False)


@pytest.mark.parametrize('queries', [
    ['玄关 钥匙 竖屏 静态照片', 'entrance keys everyday vertical photo'],
    ['white paper desk', 'blank paper table'],
    ['white paper desk', ' WHITE PAPER DESK ', 'blank paper table'],
])
def test_vnext_query_fault_is_field_local_and_preserves_other_semantics(queries):
    """A field-only defect must not require replacing a complete valid Need."""
    from easel.integrations import planning_semantic_review as review
    from easel.integrations.planning_result_contract import SemanticProposal
    original = vnext_proposal()
    original['needs'][0]['queries'] = queries
    untouched = deepcopy(original)
    with pytest.raises(ValueError):
        SemanticProposal.model_validate(original)
    with pytest.raises(ValueError, match='cannot be localized'):
        review.structural_targets(original)  # Unmarked historical policy retains its failure.
    targets = review.structural_targets(original, local_query_faults=True)
    assert [t['path'] for t in targets] == [['needs', 0, 'queries']]
    replacement = ['white paper desk', 'blank paper tabletop', 'two plain sheets']
    patched = review.apply_patches(original, {'patches': [{'target': 0, 'value': replacement}]}, targets)
    accepted = SemanticProposal.model_validate(patched)
    assert list(accepted.needs[0].queries) == replacement
    assert isinstance(patched['needs'][0]['queries'], list)
    assert original == untouched
    assert {k: v for k, v in patched['needs'][0].items() if k != 'queries'} == {
        k: v for k, v in original['needs'][0].items() if k != 'queries'}
    assert len(patched['needs']) == len(original['needs'])
    wrong = review.apply_patches(original, {'patches': [{'target': 0, 'value': queries}]}, targets)
    with pytest.raises(ValueError):
        SemanticProposal.model_validate(wrong)
    unsafe = deepcopy(original)
    unsafe['needs'][0]['invented_authorization'] = True
    with pytest.raises(ValueError):
        review.structural_targets(unsafe)
    unrelated = vnext_proposal()
    unrelated['needs'][0]['source_seconds'] = 15
    with pytest.raises(ValueError):
        review.structural_targets(unrelated)


@pytest.mark.parametrize('mode', ['mixed', 'music', 'voice', 'silent', None])
def test_confirmed_music_intake_uses_only_typed_obligation(mode):
    from easel.integrations import planning_semantic_review as review
    from easel.integrations.planning_result_contract import SemanticProposal
    value = vnext_proposal()
    inputs = {'proposal': {'specs': {'audio_mode': mode}},
              'preparation': {'audio_mode': 'mixed'}, 'mode_documents': {'audio-bible.md': 'Music required'}}
    original = deepcopy(value)
    targets = review.intake_targets(value, inputs)
    if mode not in {'mixed', 'music'}:
        assert targets == []  # Defaults and prose cannot create confirmed authority.
        return
    assert [t['kind'] for t in targets] == ['confirmed_music_coverage']
    music = {'scope': 'global', 'role': '配乐', 'modality': 'bgm', 'necessity': 'required',
             'conditions': [{'text': '轻柔无歌词背景音乐。', 'strength': 'required', 'responsibility': 'material'}],
             'sound': {'vocals_allowed': False}}
    patched = review.apply_patches(value, {'patches': [{'target': 0, 'value': music}]}, targets)
    SemanticProposal.model_validate(patched)
    assert value == original and patched['needs'][:-1] == original['needs']
    assert review.intake_targets(patched, inputs) == []
    with pytest.raises(ValueError, match='duplicate'):
        review.apply_patches(patched, {'patches': [{'target': 0, 'value': music}]}, targets)
    optional = deepcopy(patched)
    optional['needs'][-1]['necessity'] = 'optional'
    promoted = review.intake_targets(optional, inputs)
    assert [t['path'] for t in promoted] == [['needs', 1, 'necessity']]
    assert review.apply_patches(optional, {'patches': [{'target': 0, 'value': 'required'}]}, promoted) == patched
    optional['needs'].append(deepcopy(optional['needs'][-1]))
    with pytest.raises(ValueError, match='Multiple optional'):
        review.intake_targets(optional, inputs)


@pytest.mark.parametrize('risk', ['empty_visual', 'wrong_modality', 'no_material', 'quote_feedback', 'missing_fields', 'catalog_order', 'message_projection', 'legacy'])
def test_relational_review_evidence_contract(authority_runtime, risk):
    """Exercise typed witnesses and exact diagnostics, not model entailment."""
    from easel.integrations import planning_candidate_review as correction
    from easel.integrations import planning_review_support as support
    from easel.integrations import planning_authority as authority
    from easel.integrations.semantic_boundary import parse_review_candidate
    from easel.integrations.semantic_planning import source_catalog
    rt = authority_runtime
    canonical = dict(rt['canonical'])
    if risk == 'quote_feedback': canonical['SCENES.md'] = '桌上两张白纸。' * 150
    if risk == 'no_material': canonical['SCENES.md'] = '字幕文字：暂停一下。'
    if risk == 'catalog_order': canonical['SCENES.md'] = '\n'.join(f'第{i}段已确认画面。' for i in range(12))
    # Only the frozen test context changes; no live Creation or original fixture.
    inputs = authority.load_inputs(rt['attempt'], rt['canonical'], rt['context'], rt['mode'])
    inputs['confirmed'] = canonical
    catalog = source_catalog(canonical, {'creator_context': inputs['creator_context'], 'proposal': inputs.get('proposal')})
    initial = {'needs': [{'scope': 'global', 'role': '配乐', 'modality': 'bgm', 'necessity': 'required',
        'sound': {'vocals_allowed': False}, 'conditions': [{'text': '无歌词音乐。', 'strength': 'required', 'responsibility': 'material'}]}],
        'unresolved': ['图片素材尚未搜索。']}
    if risk == 'message_projection':
        from copy import deepcopy
        visuals = [deepcopy(vnext_proposal()['needs'][0]) for _ in range(6)]
        for index, need in enumerate(visuals):
            need['role'] = f'固定视觉候选{index}'
        initial['needs'] = [*visuals, *initial['needs']]
        initial['unresolved'] *= 4
    policy = correction.POLICY if risk == 'legacy' else correction.RELATIONAL_POLICY
    directory = correction.directory_for(parse_review_candidate(initial, catalog), inputs, catalog, policy=policy)
    if risk == 'message_projection':
        from copy import deepcopy
        from easel.integrations import planning_semantic_review as review
        for batch in correction.batches(directory):
            original = deepcopy(batch)
            projected = correction.message_context(batch)
            assert batch == original
            assert len(review.compact(projected).encode()) < len(review.compact(batch).encode())
            for key in ('candidate_bindings', 'evidence', 'source_catalog', 'response_schema'):
                assert projected[key] == original[key]
            restored = deepcopy(projected)
            assert restored.pop('candidate_reference_policy') == 'candidate-context-references@1'
            for question in restored['questions']:
                for field in ('coverage_candidates', 'candidate_context'):
                    if field not in question:
                        continue
                    full = {}
                    for key, ref in question[field].items():
                        expected = original['candidate_bindings'][key]
                        assert ref == {k: expected[k] for k in ('index', 'sha256')}
                        full[key] = deepcopy(expected)
                    question[field] = full
            assert restored == original, 'Every original question and semantic value must be recoverable'
            request = json.loads(correction.message_for(batch).splitlines()[-1])
            assert request['candidate_bindings'] == original['candidate_bindings']
            bad = deepcopy(batch)
            q = next(q for q in bad['questions'] if q.get('coverage_candidates'))
            q['coverage_candidates'] = deepcopy(q['coverage_candidates'])
            next(iter(q['coverage_candidates'].values()))['sha256'] = '0' * 64
            with pytest.raises(ValueError, match='reference'):
                correction.message_context(bad)
            legacy = {**batch, 'candidate_policy': correction.POLICY}
            assert correction.message_context(legacy) == legacy
        return
    if risk == 'catalog_order':
        restored = json.loads(json.dumps(catalog, sort_keys=True))
        assert correction.directory_for(parse_review_candidate(initial, restored), inputs, restored,
                                        policy=policy) == directory
        return
    batch = correction.batches(directory)[0]
    source, entry = next((k, row) for k, row in support.source_catalog(batch).items()
                        if row['origin'] == 'confirmed_original' and row['path'] == ['SCENES.md'])
    common = {'decision': 'ACCEPT', 'support': [{'source': source, 'quote': entry['value'][:120], 'role': 'authority'}],
              'reason': 'Declared isolated review answer.'}
    coverage = next(q for q in batch['questions'] if q['kind'] == 'frozen_visual_coverage')
    triage = next(q for q in batch['questions'] if q['kind'] == 'unresolved_classification')
    if risk == 'legacy':
        # The old replay protocol remains byte/behavior compatible, not endorsed anew.
        assert correction._row(common, coverage, batch).decision == 'ACCEPT'
        assert correction._row({**common, 'related_needs': ['candidate_000']}, triage, batch).decision == 'ACCEPT'
        return
    if risk == 'empty_visual':
        with pytest.raises(ValueError, match='witness'):
            correction._row({**common, 'coverage': 'covered', 'related_needs': []}, coverage, batch)
        with pytest.raises(ValueError, match='image/video'):
            correction._row({**common, 'coverage': 'covered', 'related_needs': ['candidate_000']}, coverage, batch)
    elif risk == 'wrong_modality':
        with pytest.raises(ValueError, match='modalities'):
            correction._row({**common, 'related_needs': ['candidate_000'], 'required_kinds': ['visual']}, triage, batch)
    elif risk == 'no_material':
        answer = correction._row({**common, 'coverage': 'no_material_obligation', 'related_needs': []}, coverage, batch)
        assert answer.coverage == 'no_material_obligation'
    else:
        answer = {**common, 'related_needs': ['candidate_000'], 'required_kinds': ['bgm']}
        if risk == 'quote_feedback': answer['support'][0]['quote'] = entry['value'][:980]
        else: del answer['required_kinds']
        single = {**batch, 'questions': [triage]}
        targets = correction._answer_targets({support.slot(triage): answer}, single)
        assert len(targets) == 1
        errors = targets[0]['issue']['errors']
        if risk == 'quote_feedback':
            assert any(e.get('constraint') == 'maxLength' and e.get('limit') == 512
                       and e.get('actual_length') == 980 for e in errors)
            assert entry['value'][:980] not in json.dumps(targets[0]['issue'], ensure_ascii=False)
        else:
            assert any('required_kinds' in e.get('missing_fields', []) for e in errors)


@pytest.mark.parametrize('risk', ['echo', 'legal', 'restriction', 'conflict', 'unknown_extra',
    'missing_field', 'unknown_scope', 'no_music_rule', 'duplicate', 'truncated',
    'tool_fence', 'text_fence', 'text_prose', 'text_duplicate', 'nonfinite', 'sensitive'])
def test_output_admission_registered_rules(authority_runtime, risk):
    from copy import deepcopy
    from easel import output_admission as admission
    from easel.integrations import planning_authority as authority
    from easel.integrations import planning_semantic_review as review
    from easel.integrations.planning_input_view import PlanningInputView
    from easel.integrations.semantic_planning import source_catalog
    rt = authority_runtime
    inputs = authority.load_inputs(rt['attempt'], rt['canonical'], rt['context'], rt['mode'])
    # Isolated schema input, not a fabricated production approval.
    inputs['proposal'] = {'specs': {'audio_mode': 'music'}}
    catalog = source_catalog(rt['canonical'], {'creator_context': inputs['creator_context']})
    view = PlanningInputView(inputs, catalog)
    schema = review.intake_selection_schema(view.codec.schema, inputs)
    value = {'needs': [{'scope': view.codec.to_wire['global'], 'modality': 'bgm',
                       'necessity': 'required', 'role': '配乐'}], 'unresolved': []}
    if not view.codec.empty_continuity: value['needs'][0]['continuity_choices'] = []
    legal = deepcopy(value)
    if risk != 'legal':
        value['needs'][0]['contains'] = {'modality': 'bgm', 'necessity': 'required'}
    if risk == 'restriction': value['needs'][0]['contains']['restriction'] = '仅非商业用途'
    if risk == 'conflict': value['needs'][0]['contains']['necessity'] = 'optional'
    if risk == 'unknown_extra': value['needs'][0]['instruction'] = '必须保留这个真实要求'
    if risk == 'missing_field': del value['needs'][0]['role']
    if risk == 'unknown_scope': value['needs'][0]['scope'] = 'not-a-source'
    if risk == 'no_music_rule': schema['properties']['needs'].pop('contains')
    raw = json.dumps(value, ensure_ascii=False)
    profile, channel = admission.SELECTION_PROFILE, 'tool'
    if risk == 'duplicate': raw = raw[:-1] + ',"unresolved":[]}'
    if risk == 'truncated': raw = raw[:-2]
    if risk == 'tool_fence': raw = '```json\n' + raw + '\n```'
    if risk.startswith('text_'):
        profile, channel = admission.TEXT_PROFILE, 'file-json'
        schema = {'type': 'object', 'additionalProperties': False,
                  'properties': {'check': {'type': 'boolean'}}, 'required': ['check']}
        raw = '```json\n{"check":false}\n```'
        if risk == 'text_prose': raw = '说明：\n' + raw
        if risk == 'text_duplicate': raw = '```json\n{"check":false,"check":true}\n```'
    if risk == 'nonfinite': raw = '{"value":1e400}'
    if risk == 'sensitive': raw = '{"api_key":"fixture-private-value-not-a-real-key"}'
    before = deepcopy(value)
    result = admission.admit_json(raw, schema, stage='A-selection', channel=channel,
        binding={'request_sha256': 'a' * 64}, profile=profile)
    assert value == before
    expected = 'NORMALIZE' if risk in {'echo', 'text_fence'} else 'ACCEPT' if risk == 'legal' else 'REJECT'
    assert result['receipt']['decision']['outcome'] == expected
    if risk in {'echo', 'legal'}:
        assert result['candidate'] == legal
        second = admission.admit_json(admission.canonical_json(result['candidate']), schema,
            stage='A-selection', channel=channel, binding={'request_sha256': 'a' * 64}, profile=profile)
        assert second['candidate'] == result['candidate'] and not second['receipt']['actions']
        assert result == admission.admit_json(raw, schema, stage='A-selection', channel=channel,
            binding={'request_sha256': 'a' * 64}, profile=profile)
    if risk == 'text_fence': assert result['candidate'] == {'check': False}
    if risk in {'restriction', 'conflict', 'unknown_extra', 'missing_field', 'unknown_scope', 'no_music_rule'}:
        assert result['candidate'] == value and not result['receipt']['actions']
    if risk in {'duplicate', 'truncated', 'tool_fence', 'text_prose', 'text_duplicate', 'nonfinite', 'sensitive'}:
        assert result['candidate'] is None
        assert not result['receipt']['actions']
        assert raw not in json.dumps(result['receipt'], ensure_ascii=False)


@pytest.mark.parametrize('case', ['clean', 'joint', 'receipt_failure', 'pending', 'cold_replay', 'tamper', 'reject', 'legacy'])
def test_output_admission_planning_truth_boundary(prep_env, monkeypatch, case):
    # The existing integration executes normal confirm/Preparation/Planning/
    # Truth/persist/load. Only the external replies contain the controlled echo.
    if case == 'pending':
        from easel.integrations import semantic_boundary_run as owner
        from easel.materials.store import AttemptMaterialStore
        from easel.creation_delivery import DeliveryExecutionUncertain
        native_run = owner.run
        def observe_same_planning_request(*args, **kwargs):
            try:
                return native_run(*args, **kwargs)
            except DeliveryExecutionUncertain:
                # The external fixture below now has the same request's terminal
                # response available. Re-enter only the Planning checkpoint while
                # the same Owner still holds the operation, not a new workflow.
                journal = AttemptMaterialStore(args[0]['workspace']['path']).read_recovery_record(owner.STATE_KEY)
                assert journal['admissions']['A-selection']['receipt']['decision']['outcome'] == 'NORMALIZE'
                assert set(journal['calls']) == {'A-selection', 'A-details'}
                assert not journal['repair_used']
                return native_run(*args, **kwargs)
        monkeypatch.setattr(owner, 'run', observe_same_planning_request)
    test_vnext_confirmed_preset_truth_boundary(prep_env, monkeypatch, 'music_query_repair', admission_case=case)


@pytest.mark.parametrize('risk', ['joint', 'optional', 'conflict', 'unknown_binding',
    'false_authority', 'forged_patch', 'exhausted', 'persist_failure', 'pending',
    'cold_replay', 'legacy', 'legacy_unresolved', 'wire_type_coercion',
    'answer_repair', 'recheck_rejected'])
def test_p3_candidate_correction_full_boundary(authority_runtime, monkeypatch, risk):
    """Real capture/review/patch/compile/verify; only external answers are fixtures."""
    import hashlib
    import subprocess
    import sys
    from copy import deepcopy
    from easel.integrations import semantic_boundary_run as boundary
    from easel.integrations import planning_candidate_review as correction
    from easel.integrations import planning_semantic_review as review
    from easel.integrations import planning_review_support as support
    from easel.integrations import planning_authority as authority
    from easel.integrations.semantic_planning import source_catalog
    from easel.materials.store import AttemptMaterialStore
    from easel.creation_delivery import DeliveryExecutionUncertain
    rt = authority_runtime
    canonical = dict(rt['canonical'])
    canonical['SCENES.md'] = '必须展示桌上两张白纸。装饰便签可有可无。'
    if risk == 'cold_replay':
        canonical['SCENES.md'] = '\n'.join(['必须展示两张白纸，便签可选。'] * 12)
    for name, text in canonical.items():
        (rt['root'] / 'planning' / name).write_bytes(text.encode())
    initial = vnext_proposal()
    initial['needs'][0]['necessity'] = 'optional'
    decoration = {'scope': 'scene-1', 'role': '装饰便签', 'modality': 'image', 'necessity': 'optional',
        'conditions': [{'text': '装饰便签。', 'strength': 'required', 'responsibility': 'material'}]}
    initial['needs'].append(decoration)
    initial['unresolved'] = ['两张白纸照片尚未检索，需取得符合已确认画面的素材。']
    if risk in {'joint', 'persist_failure', 'pending', 'cold_replay'}:
        initial['needs'][0]['queries'] = ['白纸 桌面', 'white paper desk']
    if risk in {'optional', 'answer_repair', 'wire_type_coercion'}:
        initial['needs'][0]['necessity'] = 'required'
        initial['unresolved'] = []
    if risk == 'wire_type_coercion':
        initial['needs'].append({'scope': 'global', 'role': '配乐', 'modality': 'bgm',
            'necessity': 'required', 'conditions': [{'text': '无歌词背景音乐。',
                'strength': 'required', 'responsibility': 'material'}],
            'sound': {'vocals_allowed': False}})
    if risk == 'conflict':
        initial['unresolved'] = ['画面到底使用真人还是插画尚未决定。']
    if risk == 'exhausted':
        initial['needs'][0]['necessity'] = 'OPTIONAL'
    legacy = risk.startswith('legacy')
    if legacy:
        initial['needs'][0]['necessity'] = 'required'
        if risk == 'legacy': initial['unresolved'] = []
    raw_replies, calls, pending = {}, [], {}
    original = deepcopy(initial)
    last_batch = [None]
    def answers_for(batch, *, invalid=False):
        refs = support.source_catalog(batch)
        source, entry = next((key, row) for key, row in refs.items()
                             if row['origin'] == 'confirmed_original' and row['path'] == ['SCENES.md'])
        rows = []
        for q in batch['questions']:
            decision = 'ACCEPT'
            if q['kind'] == 'need_necessity' and q['target'] == [0] and q['candidate']['necessity'] == 'optional':
                decision = 'CHALLENGE'
            if q['kind'] == 'unresolved_classification' and risk == 'conflict':
                decision = 'UNRESOLVED'
            row = {'question': q['question'], 'decision': decision, 'evidence': [entry['evidence_id']],
                   'support': [{'source': source, 'quote': entry['value'], 'role': 'authority'}],
                   'reason': '独立固定判断：两纸为明确必需，便签为可选；只检索尚未执行，不代表新授权。'}
            if q['kind'] == 'need_necessity' and decision == 'CHALLENGE' and risk == 'false_authority':
                key, ref = next((key, row) for key, row in refs.items() if row['origin'] == 'derived_preparation')
                row['support'] = [{'source': key, 'quote': ref['value'] if isinstance(ref['value'], str) else None, 'role': 'context'}]
                row['evidence'] = [ref['evidence_id']]
            rows.append(row)
        result = fixture_review_wire(batch, rows)
        for q in batch['questions']:
            if q['kind'] == 'unresolved_classification':
                result[support.slot(q)]['related_needs'] = ([] if risk == 'conflict' else
                    ['candidate_999' if risk == 'unknown_binding' else 'candidate_000'])
        return result
    def dispatch(stage, message, session, **options):
        if session in pending:
            prior_message, prior_options, text = pending[session]
            assert (message, options) == (prior_message, prior_options)
            return text
        calls.append((session, message))
        payload = json.loads(message.splitlines()[-1])
        if message.startswith('〔Easel Semantic Planning vNext A-'):
            seed = deepcopy(initial)
            seed['needs'][0]['queries'] = []
            if risk == 'exhausted': seed['needs'][0]['necessity'] = 'optional'
            selection, details, _ = staged_fixture_parts(message, seed)
            if risk == 'exhausted': selection['needs'][0]['necessity'] = 'OPTIONAL'
            if initial['needs'][0].get('queries'):
                details['slots']['slot_000']['queries'] = initial['needs'][0]['queries']
            if risk == 'wire_type_coercion':
                details['slots']['slot_002']['sound']['vocals_allowed'] = 'false'
            result = selection if session.endswith('A-selection') else details
        elif '有界视觉复核' in message:
            last_batch[0] = payload
            result = answers_for(payload)
            if risk == 'answer_repair' and session.endswith('B-000'):
                result[next(iter(result))]['reason'] = ''
            if risk == 'recheck_rejected' and '-B-recheck-' in session:
                q = next(q for q in payload['questions'] if q['kind'] == 'complete_obligation')
                result[support.slot(q)]['decision'] = 'CHALLENGE'
        elif '单次局部修复' in message:
            result = {}
            for i, target in enumerate(payload['targets']):
                if target['kind'] == 'confirmed_necessity':
                    value = {'necessity': 'required', 'role': 'forged'} if risk == 'forged_patch' else 'required'
                elif target['kind'] == 'structural_leaf':
                    value = (['white paper desk', 'two plain sheets', 'blank paper tabletop']
                             if target['path'][-1] == 'queries' else 'optional')
                elif target['kind'] == 'candidate_answer':
                    value = answers_for(last_batch[0])[target['path'][0]]
                else:
                    raise AssertionError('Unexpected P3 repair target: ' + target['kind'])
                result[f'target-{i:04}'] = value
        else:
            raise AssertionError('Unexpected external stage')
        raw = json.dumps(result, ensure_ascii=False)
        raw_replies[session.rsplit('-vnext-', 1)[-1]] = raw
        if risk == 'pending' and session.endswith('B-000') and session not in pending:
            pending[session] = (message, options, raw)
            raise DeliveryExecutionUncertain('Original fixture review request remains pending')
        return raw
    route = {'profile': 'fixture-only', 'thinking': 'off', 'timeout': 60}
    inputs = authority.load_inputs(rt['attempt'], canonical, rt['context'], rt['mode'])
    catalog = source_catalog(canonical, {'creator_context': inputs['creator_context'], 'proposal': inputs.get('proposal')})
    if legacy:
        view = boundary.input_views.PlanningInputView(inputs, catalog)
        scope = {'policy': boundary.POLICY, 'creation_id': rt['attempt']['creation_id'], 'attempt_id': rt['attempt']['attempt_id'],
            'context_refs': rt['context']['context_refs'], 'canonical': canonical, 'mode': rt['mode'],
            'inputs': inputs, 'catalog': catalog, 'input_view': view.identity,
            'transport': boundary.transport_identity(catalog, projected=True, atomic=True, source_bound=True,
                staged_a=True, source_view=True, intake_inputs=inputs, intake_policy=review.AUDIO_INTAKE_POLICY)}
        AttemptMaterialStore(rt['root']).write_recovery_record(boundary.STATE_KEY,
            {'schema': boundary.VIEW_JOURNAL, 'scope': scope, 'route': route,
             'calls': {}, 'repair_used': False, 'input_view_snapshot': view.snapshot()})
    def run():
        return boundary.run(rt['attempt'], rt['context'], canonical, rt['mode'], route, dispatch)
    failures = {'conflict', 'unknown_binding', 'false_authority', 'forged_patch', 'exhausted',
                'legacy_unresolved', 'wire_type_coercion', 'recheck_rejected'}
    if risk in failures:
        with pytest.raises(ValueError): run()
        before = len(calls)
        with pytest.raises(ValueError): run()
        assert len(calls) == before
        assert not (rt['root'] / 'planning/MATERIAL_PLAN.json').exists()
        assert sum('单次局部修复' in text for _, text in calls) <= 1
        if risk == 'wire_type_coercion':
            assert not any('有界视觉复核' in text for _, text in calls)
            assert json.loads(raw_replies['A-details'])['slots']['slot_002']['sound']['vocals_allowed'] == 'false'
        if risk == 'recheck_rejected':
            assert sum('单次局部修复' in text for _, text in calls) == 1
            assert any('-B-recheck-' in session for session, _ in calls)
        assert initial == original
        return
    if risk == 'pending':
        with pytest.raises(DeliveryExecutionUncertain): run()
    if risk == 'persist_failure':
        writer = boundary.write_file
        failed = [False]
        def fail_once(root, name, raw, **kwargs):
            if name == 'SEMANTIC_CHECKPOINT.json' and not failed[0]:
                failed[0] = True
                raise OSError('fixture disk failure after complete review')
            return writer(root, name, raw, **kwargs)
        monkeypatch.setattr(boundary, 'write_file', fail_once)
        with pytest.raises(OSError): run()
        completed_calls = len(calls)
    result = run()
    if risk == 'persist_failure': assert len(calls) == completed_calls
    before = len(calls)
    assert run()['plan'] == result['plan'] and len(calls) == before
    verified = boundary.verify(rt['root'], result['plan'], rt['mode'], canonical['SCRIPT.md'],
                               canonical=canonical, attempt=rt['attempt'])
    checkpoint_path = rt['root'] / 'planning/SEMANTIC_CHECKPOINT.json'
    checkpoint = json.loads(checkpoint_path.read_text())
    assert [n.importance.value for n in result['plan'].needs] == ['required', 'optional']
    assert checkpoint['proposal']['unresolved'] == []
    assert checkpoint['initial']['unresolved'] == original['unresolved']
    for key in ('A-selection', 'A-details'):
        assert checkpoint['wire_originals'][key] == raw_replies[key]
    assert initial == original
    if legacy:
        assert 'candidate_correction' not in checkpoint
        assert 'candidate_review_policy' not in calls[0][1]
        return
    assert checkpoint['scope']['transport']['intake_policy'] == correction.INTAKE_POLICY
    trace = checkpoint['candidate_correction']
    assert trace['reviewed_candidate']['unresolved'] == original['unresolved']
    assert len(trace['execution_pending_reports']) == len(original['unresolved'])
    expected_repairs = 0 if risk == 'optional' else 1
    assert trace['repair_calls'] == expected_repairs
    assert sum('单次局部修复' in text for _, text in calls) == expected_repairs
    if original['needs'][0].get('queries'):
        assert {t['kind'] for t in checkpoint['repair']['targets']} == {'structural_leaf', 'confirmed_necessity'}
        assert checkpoint['initial']['needs'][0]['queries'] == original['needs'][0]['queries']
    if risk == 'joint':
        reviewed_again = [q for session, text in calls if '-B-recheck-' in session
                          for q in json.loads(text.splitlines()[-1])['questions']]
        assert {'need_necessity', 'visual_choices', 'complete_obligation',
                'unresolved_classification', 'frozen_visual_coverage'} <= {q['kind'] for q in reviewed_again}
        assert not any(q['kind'] == 'need_necessity' and q['target'] == [1] for q in reviewed_again)
    if risk == 'cold_replay':
        fixture = rt['root'] / 'cold-correction.json'
        fixture.write_text(json.dumps({'root': str(rt['root']), 'plan': result['plan'].model_dump(mode='json'),
            'mode': rt['mode'], 'canonical': canonical, 'attempt': rt['attempt']}))
        child = '''import json,sys,socket
from pathlib import Path
from easel.integrations import semantic_boundary_run as b
from easel.materials.domain import MaterialPlan
def no_network(*a,**k): raise AssertionError('Cold verify must not dispatch')
socket.socket.connect=no_network
x=json.loads(Path(sys.argv[1]).read_text())
r=b.verify(x['root'],MaterialPlan.model_validate_json(json.dumps(x['plan'])),x['mode'],x['canonical']['SCRIPT.md'],canonical=x['canonical'],attempt=x['attempt'])
print(json.dumps(r))
'''
        process = subprocess.run([sys.executable, '-c', child, str(fixture)], cwd=Path(__file__).resolve().parents[1],
                                 capture_output=True, text=True, timeout=60)
        assert process.returncode == 0, process.stderr
        assert json.loads(process.stdout) == verified
    # Stored evidence, not a mutable flag, controls the effective formal result.
    for fault in ('policy', 'report', 'judgment', 'original', 'extra_capture'):
        bad = deepcopy(checkpoint)
        if fault == 'policy': bad['scope']['transport']['intake_policy'] = review.AUDIO_INTAKE_POLICY
        elif fault == 'report': bad['candidate_correction']['reviewed_candidate']['unresolved'] = ['fabricated']
        elif fault == 'judgment': bad['candidate_correction']['repair_calls'] += 1
        elif fault == 'original': bad['initial']['needs'][0]['necessity'] = 'optional' if bad['initial']['needs'][0]['necessity'] == 'required' else 'required'
        else: bad['capture']['invented'] = {}
        checkpoint_path.write_text(json.dumps(bad, ensure_ascii=False))
        with pytest.raises(ValueError):
            boundary.verify(rt['root'], result['plan'], rt['mode'], canonical['SCRIPT.md'], canonical=canonical, attempt=rt['attempt'])
    checkpoint_path.write_text(json.dumps(checkpoint, ensure_ascii=False))


@pytest.mark.parametrize('risk', ['reentry', 'audio_omission', 'structural_repair', 'query_repair', 'staged_query_repair', 'semantic_repair',
    'exhausted', 'answer_repair', 'pending', 'persist_failure', 'tamper', 'unknown_question', 'multibatch', 'legacy_resume',
    'legacy_carrier_pending', 'legacy_tool_pending', 'carrier_removed', 'carrier_changed', 'missing_slot',
    'forged_support', 'derived_authority', 'real_wrapper', 'real_full_creation', 'real_full_creation2', 'repair_invalid', 'legacy_supported_pending',
    'legacy_supported_current', 'legacy_wire_current', 'legacy_frame_current', 'source_binding_verify', 'xml_roundtrip', 'xml_answer_repair', 'wire_tamper', 'frame_header_repair', 'staged_header_repair', 'staged_structural_repair'])
def test_vnext_bounded_review_runtime(authority_runtime, monkeypatch, risk, *, carrier=None, two_stage=False, crash=None):
    from copy import deepcopy
    import jsonschema
    from easel.integrations import semantic_boundary_run as boundary
    from easel.integrations import planning_semantic_review as review
    from easel.integrations.openclaw_delivery import PlanningResultError
    from easel.creation_delivery import DeliveryExecutionUncertain
    rt = authority_runtime
    legacy_staged = bool(crash and crash.startswith('legacy_'))
    if legacy_staged: crash = crash.removeprefix('legacy_')
    staged_design = risk in {'staged_header_repair', 'staged_structural_repair'}
    if staged_design:
        risk = 'frame_header_repair' if risk == 'staged_header_repair' else 'structural_repair'
    staged_candidates = []
    if risk in {'query_repair', 'staged_query_repair'}:
        risk, two_stage = 'query_repair', True
    if risk == 'legacy_resume':
        first = rt['run']()
        assert boundary.policy_for(rt['attempt']) == 'semantic-planning-compiler@7'
        calls = len(rt['calls'])
        with pytest.raises(ValueError, match='Old Planning journal'):
            boundary.run(rt['attempt'], rt['context'], rt['canonical'], rt['mode'],
                {'profile': 'fixture-only', 'thinking': 'off', 'timeout': 60}, lambda *_: pytest.fail('new dispatch'))
        assert rt['run']()['plan'] == first['plan'] and len(rt['calls']) == calls
        return
    initial = vnext_proposal()
    atomic = risk not in {'legacy_carrier_pending', 'legacy_tool_pending', 'legacy_supported_pending', 'legacy_supported_current', 'legacy_wire_current'}
    projected = risk not in {'legacy_carrier_pending', 'legacy_tool_pending', 'legacy_supported_pending', 'legacy_supported_current'}
    def encode_wire(value, schema):
        # Offline external fixture only; the real model owns its response.
        properties = schema.get('properties', {})
        if (schema.get('type') == 'object' and set(properties) == {'null', 'value'}
                and properties['null'].get('const') is True and 'anyOf' in schema):
            return {'null': True} if value is None else {'value': encode_wire(value, properties['value'])}
        if isinstance(value, dict):
            if schema.get('title') == 'NeedProposal' and 'framing' in properties:
                value = deepcopy(value)
                frame = value.pop('frame', 'unconstrained'); ratio = value.pop('native_ratio', None)
                value['framing'] = {'mode': frame, **({'ratio': ratio} if frame == 'native' else {})}
            return {key: encode_wire(item, properties.get(key, {})) for key, item in value.items()}
        if isinstance(value, list):
            prefix = schema.get('prefixItems', [])
            return [encode_wire(item, prefix[i] if i < len(prefix) else schema.get('items', {}))
                    for i, item in enumerate(value)]
        return value
    if risk in {'structural_repair', 'exhausted', 'repair_invalid'}: initial['needs'][0]['necessity'] = 'NECESSARY'
    if risk == 'query_repair':
        initial['needs'][0]['queries'] = ['白纸 桌面', 'white paper desk']
    if risk in {'real_wrapper', 'real_full_creation', 'real_full_creation2'}:
        fixture = {'real_full_creation': 'autonomous-full-development1-A.json',
                   'real_full_creation2': 'autonomous-full-development2-A.json',
                   'real_wrapper': 'autonomous-round2-A.json'}[risk]
        initial = json.loads((Path(__file__).parent / 'fixtures/planning-vnext-development-2026-10-08' / fixture).read_text())
    if risk == 'semantic_repair':
        initial['needs'][0]['conditions'].append({'text': '不许出现手部。', 'strength': 'required', 'responsibility': 'material'})
    if risk == 'frame_header_repair':
        initial['needs'][0].update(frame='native', native_ratio='4:5')
    if risk == 'audio_omission':
        initial = {'needs': [{'scope': 'global', 'role': '配乐', 'modality': 'bgm', 'necessity': 'required',
            'sound': {'mood': '安静'}, 'conditions': [{'text': '安静配乐。', 'strength': 'required', 'responsibility': 'material'}]}]}
    if risk == 'multibatch':
        initial['needs'] = [deepcopy(initial['needs'][0]) for _ in range(16)]
        for item in initial['needs']:
            item['conditions'] = deepcopy(item['conditions']) * 4
    calls, pending = [], [risk == 'pending']
    accepted_initial = {}
    staged_external = {}
    def execute(stage, message, session, *, structured_result=None, expected_runtime_sha256=None):
        calls.append((session, message))
        assert expected_runtime_sha256 == (None if risk == 'legacy_carrier_pending' else
            boundary.TOOL_A_RUNTIME_SHA if risk == 'legacy_tool_pending' else
            boundary.SUPPORTED_RUNTIME_SHA if risk == 'legacy_supported_pending' else
            __import__('easel.integrations.planning_authority', fromlist=['digest']).digest(boundary.structured.RUNTIME_PARTS))
        payload = json.loads(message.splitlines()[-1])
        if two_stage and message.startswith('〔Easel Semantic Planning vNext A-'):
            from easel.integrations.planning_staged_proposal import StagedProposal
            from easel.integrations.planning_result_contract import semantic_tool_schema
            if not staged_external:
                seed = deepcopy(initial)
                if risk == 'structural_repair': seed['needs'][0]['necessity'] = 'required'
                if risk == 'query_repair': seed['needs'][0]['queries'] = []
                selection, details, _ = staged_fixture_parts(message, seed)
                if risk == 'structural_repair': selection['needs'][0]['necessity'] = 'NECESSARY'
                if risk == 'query_repair': details['slots']['slot_000']['queries'] = deepcopy(initial['needs'][0]['queries'])
                if crash == 'invalid_continuity': selection['needs'][0]['continuity_choices'] = ['segment-1']
                staged_external.update(selection=selection, details=details)
            result = staged_external['selection' if session.endswith('A-selection') else 'details']
            if risk not in {'structural_repair', 'query_repair'}: jsonschema.validate(result, structured_result['schema'])
            return json.dumps(result, ensure_ascii=False)
        if message.startswith('〔Easel Semantic Planning vNext〕'):
            from easel.integrations.planning_result_contract import semantic_tool_schema
            from easel.integrations.planning_structured import request_for
            if risk == 'legacy_carrier_pending':
                assert structured_result is None and 'schema' in payload
            else:
                from easel.integrations import planning_wire
                canonical = semantic_tool_schema(payload['catalog'], compiled=atomic)
                expected = planning_wire.project(canonical, 'A', atomic_framing=atomic).schema if projected else canonical
                assert structured_result == request_for(expected)
                assert payload['transport']['schema_sha256'] == structured_result['schemaSha256']
                assert 'schema' not in payload
            if risk in {'xml_roundtrip', 'xml_answer_repair'}:
                initial['needs'][0].update(purpose='null', queries=['white paper desk', 'plain table paper', 'two blank sheets'])
                initial['needs'].extend([
                    {'scope': 'global', 'role': '配乐', 'modality': 'bgm', 'necessity': 'required',
                     'conditions': [{'text': '安静配乐。', 'strength': 'required', 'responsibility': 'material'}],
                     'sound': {'mood': '安静', 'instruments': ['钢琴', '柔和弦乐'], 'vocals_allowed': False, 'tempo_bpm': [60, 90]}},
                    {'scope': 'global', 'role': '旁白', 'modality': 'voice', 'necessity': 'required',
                     'conditions': [{'text': '读出冻结正文。', 'strength': 'required', 'responsibility': 'material'}],
                     'voice_choice': next(iter(payload['catalog']['voice']))},
                    {'scope': next(iter(payload['catalog']['event'])), 'role': '音效', 'modality': 'sfx', 'necessity': 'optional',
                     'conditions': [{'text': '纸张轻响。', 'strength': 'required', 'responsibility': 'material'}],
                     'sound': {'event_description': '纸张轻响'}}]) if len(initial['needs']) == 1 else None
            if risk == 'real_full_creation2':
                return (Path(__file__).parent / 'fixtures/planning-vnext-development-2026-10-08' /
                        'autonomous-full-development2-A.json').read_text()
            return json.dumps(encode_wire(initial, expected) if atomic and risk not in {'real_wrapper', 'real_full_creation'} else initial, ensure_ascii=False)
        from easel.integrations.planning_structured import request_for
        if risk in {'legacy_carrier_pending', 'legacy_tool_pending'}:
            assert structured_result is None
        else:
            assert structured_result == request_for(payload['schema'] if '单次局部修复' in message else payload['response_schema'])
        if '单次局部修复' in message:
            patches = []
            for index, target in enumerate(payload['targets']):
                kind = target['kind']
                if kind == 'structural_leaf':
                    if risk == 'query_repair':
                        assert target['path'] == ['needs', 0, 'queries']
                        value = ['white paper desk', 'blank paper tabletop', 'two plain sheets']
                    else:
                        value = 'INVALID' if risk == 'repair_invalid' else 'required'
                elif kind == 'frozen_visual_coverage': value = vnext_proposal()['needs'][0]
                elif kind == 'complete_obligation':
                    value = {'text': '手部可不出现。', 'strength': 'preference', 'responsibility': 'material'}
                elif kind == 'answer':
                    value = {**payload['original']['answers'][target['path'][0]], 'decision': 'ACCEPT'}
                elif kind == 'visual_choices' and risk == 'frame_header_repair':
                    value = {**payload['original']['needs'][target['path'][0]], 'frame': 'unconstrained', 'native_ratio': None}
                else: raise AssertionError('unexpected target')
                patches.append({'target': index, 'value': value})
            result = {'patches': patches}
            if structured_result is not None:
                result = {f'target-{row["target"]:04}': {k: v for k, v in row['value'].items() if k not in {'question', 'evidence'}}
                    if payload['targets'][row['target']]['kind'] == 'answer' else row['value'] for row in patches}
            if projected:
                result = encode_wire(result, payload['schema'])
            if risk != 'repair_invalid': jsonschema.validate(result, payload['schema'])
            return json.dumps(result, ensure_ascii=False)
        assert '有界视觉复核' in message
        # Full frozen originals and upstream context are present in each batch.
        assert payload['evidence'][0]['value'] == rt['canonical']
        assert 'query' not in review.compact(payload['questions'])
        assert all(q['kind'] != 'audio_semantics' for q in payload['questions'])
        if pending[0]:
            pending[0] = False
            raise DeliveryExecutionUncertain('original fake run still pending')
        if risk == 'multibatch' and session.endswith('B-001'):
            raise PlanningResultError('MODEL_TRUNCATED')
        answers = [{'question': q['question'], 'decision': 'ACCEPT', 'evidence': [0],
                    'reason': '固定独立对照：忠实承接桌上两纸及叙事用途。'} for q in payload['questions']]
        answers = supported_fixture_answers(payload, answers)
        if risk == 'frame_header_repair' and session.endswith('B-000'):
            next(a for a, q in zip(answers, payload['questions'], strict=True)
                 if q['kind'] == 'visual_choices')['decision'] = 'CHALLENGE'
        if risk in {'xml_roundtrip', 'xml_answer_repair'}:
            from easel.integrations.planning_review_support import source_catalog
            handle, entry = next((key, item) for key, item in source_catalog(payload).items()
                if not isinstance(item['value'], str) and item['evidence_id'] in payload['questions'][0]['evidence'])
            answers[0]['support'].append({'source': handle, 'quote': None, 'role': 'context'})
            answers[0]['evidence'] = sorted({*answers[0]['evidence'], entry['evidence_id']})
        if risk in {'forged_support', 'derived_authority', 'output_as_source'}:
            row = answers[0]['support'][0]
            if risk == 'forged_support': row['quote'] = '冻结输入中不存在的原文'
            else:
                from easel.integrations.planning_review_support import source_catalog
                origin = 'derived_preparation' if risk == 'derived_authority' else 'confirmed_spec'
                source, entry = next((key, item) for key, item in source_catalog(payload).items()
                                     if item['origin'] == origin)
                row.update(source=source, quote=entry['value'][:512] if isinstance(entry['value'], str) else None,
                           role='authority' if risk == 'derived_authority' else 'output_authority')
                answers[0]['evidence'] = [entry['evidence_id']]
        if 'recheck' not in session:
            if risk == 'audio_omission':
                assert not payload['visual_candidates']
                assert all(q['kind'] == 'frozen_visual_coverage' for q in payload['questions'])
                # One independent complete-scope failure, not A's self-assessment.
                answers[-1].update(decision='CHALLENGE', reason='冻结场景要求两纸背景，A遗漏全部视觉素材。')
            elif risk == 'semantic_repair':
                answers[3].update(decision='CHALLENGE', reason='无冻结硬依据的手部禁令。')
            elif risk == 'exhausted': answers[1].update(decision='UNRESOLVED', reason='语义未决。')
            elif risk in {'answer_repair', 'xml_answer_repair'}: answers[1]['decision'] = 'YES'
            elif risk == 'unknown_question': answers[1]['question'] = 999
            accepted_initial.update({a['question']: a for a in answers if a['decision'] == 'ACCEPT'})
        elif risk == 'semantic_repair':
            # Unchanged header/two-paper/narrative judgments remain reusable.
            # P3 necessity binds the whole Need, so changed conditions require
            # its recheck; legacy policies retain the original exact question set.
            expected_kinds = {'complete_obligation', 'frozen_visual_coverage'}
            if payload.get('candidate_policy') in {'planning-candidate-review@1', 'planning-candidate-review@2'}:
                expected_kinds.add('need_necessity')
            assert {q['kind'] for q in payload['questions']} == expected_kinds
            assert not any(q['candidate'].get('text') == '两张白纸放在桌上。' for q in payload['questions'])
        wire = fixture_review_wire(payload, answers)
        if risk == 'missing_slot': del wire[next(iter(wire))]
        return json.dumps(wire, ensure_ascii=False)
    uncertain_details = {}
    def transported(stage, message, session, **options):
        if session in uncertain_details:
            original_message, original_options, raw = uncertain_details[session]
            assert (message, options) == (original_message, original_options), 'Observation must retain exact request'
            return raw  # Existing external request terminal, not a new model submission.
        raw = execute(stage, message, session, **options)
        if crash == 'details_unknown' and session.endswith('A-details'):
            uncertain_details[session] = (message, options, raw)
            raise DeliveryExecutionUncertain('isolated existing details request is pending')
        if staged_design and message.startswith('〔Easel Semantic Planning vNext〕'):
            # Only the external candidate fixture is split/assembled here.
            # Real B, repair, recheck and Planning persistence remain in charge;
            # this does NOT test a new two-request journal or its recovery.
            from easel.integrations.planning_result_contract import semantic_tool_schema
            from easel.integrations.planning_wire import FrameProjection
            from tests.planning_material_matrix.producer_experiment import StagedProducerExperiment
            schema = semantic_tool_schema(json.loads(message.splitlines()[-1])['catalog'], compiled=True)
            frame = FrameProjection(schema, 'A')
            codec = StagedProducerExperiment(schema)
            seed = frame.decode_candidate(json.loads(raw))
            if risk == 'structural_repair':
                # Construct a deliberately invalid external selection fixture;
                # never use this fixture setup as a runtime correction.
                seed['needs'][0]['necessity'] = 'required'
            selection, details, receipt = codec.encode(seed)
            if risk == 'structural_repair':
                selection['needs'][0]['necessity'] = 'NECESSARY'
                receipt = codec.details_contract(selection, diagnostic=True)['identity']
            assembled = codec.assemble_candidate(selection, details, receipt)
            staged_candidates.append((selection, details, receipt))
            raw = json.dumps(frame.encode(assembled), ensure_ascii=False)
        if risk in {'xml_roundtrip', 'xml_answer_repair'}:
            raw = xml_reference_transport(raw, options['structured_result'])
        return carrier(raw, options['structured_result']) if carrier else raw
    def run(): return boundary.run(rt['attempt'], rt['context'], rt['canonical'], rt['mode'],
        {'profile': 'fixture-only', 'thinking': 'off', 'timeout': 60}, transported)
    if (not two_stage or legacy_staged) and risk != 'legacy_resume':
        # Explicit @7 fixture: keep the complete former contract regression
        # while separate two_stage cases exercise the actual fresh default.
        from easel.materials.store import AttemptMaterialStore
        from easel.integrations import planning_authority as authority
        from easel.integrations.semantic_planning import source_catalog
        inputs = authority.load_inputs(rt['attempt'], rt['canonical'], rt['context'], rt['mode'])
        catalog = source_catalog(rt['canonical'], {'creator_context': inputs['creator_context'], 'proposal': inputs.get('proposal')})
        scope = {'policy': boundary.POLICY, 'creation_id': rt['attempt']['creation_id'], 'attempt_id': rt['attempt']['attempt_id'],
                 'context_refs': rt['context']['context_refs'], 'canonical': rt['canonical'], 'mode': rt['mode'],
                 'inputs': inputs, 'catalog': catalog,
                 'transport': boundary.transport_identity(catalog, projected=True, atomic=True, source_bound=True, staged_a=legacy_staged)}
        AttemptMaterialStore(rt['root']).write_recovery_record(boundary.STATE_KEY,
            {'schema': boundary.STAGED_JOURNAL if legacy_staged else boundary.JOURNAL, 'scope': scope, 'route': {'profile': 'fixture-only', 'thinking': 'off', 'timeout': 60},
             'calls': {}, 'repair_used': False})
    if risk in {'legacy_carrier_pending', 'legacy_tool_pending', 'legacy_supported_pending', 'legacy_supported_current', 'legacy_wire_current', 'legacy_frame_current'}:
        from easel.integrations import planning_authority as authority
        from easel.integrations.semantic_planning import source_catalog
        from easel.materials.store import AttemptMaterialStore
        inputs = authority.load_inputs(rt['attempt'], rt['canonical'], rt['context'], rt['mode'])
        scope = {'policy': boundary.POLICY, 'creation_id': rt['attempt']['creation_id'],
            'attempt_id': rt['attempt']['attempt_id'], 'context_refs': rt['context']['context_refs'],
            'canonical': rt['canonical'], 'mode': rt['mode'], 'inputs': inputs,
            'catalog': source_catalog(rt['canonical'], {'creator_context': inputs['creator_context']})}
        if risk == 'legacy_tool_pending':
            scope['transport'] = boundary.transport_identity(scope['catalog'], supported=False)
        if risk == 'legacy_supported_pending':
            scope['transport'] = boundary.transport_identity(scope['catalog'], runtime_sha=boundary.SUPPORTED_RUNTIME_SHA)
        if risk == 'legacy_supported_current':
            scope['transport'] = boundary.transport_identity(scope['catalog'])
        if risk == 'legacy_frame_current':
            scope['transport'] = boundary.transport_identity(scope['catalog'], projected=True, atomic=True)
        if risk == 'legacy_wire_current':
            scope['transport'] = boundary.transport_identity(scope['catalog'], projected=True)
        message = boundary.a_message(scope)
        import hashlib
        session = f"semantic-{rt['attempt']['attempt_id']}-vnext-A"
        AttemptMaterialStore(rt['root']).write_recovery_record(boundary.STATE_KEY, {
            'schema': boundary.FRAME_JOURNAL if risk == 'legacy_frame_current' else boundary.WIRE_JOURNAL if risk == 'legacy_wire_current' else boundary.SUPPORTED_JOURNAL if risk in {'legacy_supported_pending', 'legacy_supported_current'} else boundary.TOOL_A_JOURNAL if risk == 'legacy_tool_pending' else boundary.LEGACY_JOURNAL, 'scope': scope,
            'route': {'profile': 'fixture-only', 'thinking': 'off', 'timeout': 60},
            'calls': {'A': {'request_sha256': hashlib.sha256(message.encode()).hexdigest(),
                'session': session, 'input_bytes': len(message.encode()), 'result': 'TRANSPORT_FAILED'}},
            'repair_used': False})
    if risk in {'exhausted', 'unknown_question', 'multibatch', 'missing_slot', 'forged_support', 'derived_authority', 'output_as_source', 'real_wrapper', 'real_full_creation', 'real_full_creation2', 'repair_invalid'}:
        with pytest.raises(ValueError): run()
        before = len(calls)
        with pytest.raises(ValueError): run()
        assert len(calls) == before
        assert not (rt['root'] / 'planning/MATERIAL_PLAN.json').exists()
        assert sum('单次局部修复' in m for _, m in calls) == (1 if risk in {'exhausted', 'forged_support', 'derived_authority', 'output_as_source', 'repair_invalid'} else 0)
        return
    if risk == 'pending':
        with pytest.raises(DeliveryExecutionUncertain): run()
    if risk == 'persist_failure':
        real_write = boundary.write_file
        fail = [True]
        def write(root, name, raw, **kwargs):
            if name == 'SEMANTIC_CHECKPOINT.json' and fail[0]:
                fail[0] = False
                raise OSError('isolated disk failure')
            return real_write(root, name, raw, **kwargs)
        monkeypatch.setattr(boundary, 'write_file', write)
        with pytest.raises(OSError): run()
        before = len(calls)
    if crash == 'invalid_continuity':
        # Only external responses are fixed. Real capture/diagnostics/assembly,
        # one allowed sibling repair, canonical validation and reentry execute.
        with pytest.raises(ValueError): run()
        before = len(calls)
        with pytest.raises(ValueError): run()
        assert len(calls) == before == (3 if legacy_staged else 1)
        from easel.materials.store import AttemptMaterialStore
        state = AttemptMaterialStore(rt['root']).read_recovery_record(boundary.STATE_KEY)
        assert state['repair_used'] == legacy_staged
        assert set(state['calls']) == ({'A-selection', 'A-details', 'repair'} if legacy_staged else {'A-selection'})
        captured = json.loads(state['calls']['A-selection']['reply'])
        assert captured['needs'][0]['continuity_choices'] == ['segment-1']
        assert state['wire_diagnostics']['A-selection']['wire_errors']
        assert not (rt['root'] / 'planning/MATERIAL_PLAN.json').exists()
        return
    if crash in {'selection_captured', 'details_registered'}:
        from easel.materials.store import AttemptMaterialStore
        original_save = AttemptMaterialStore.write_recovery_record
        interrupted = []
        def crash_save(store, key, value):
            result = original_save(store, key, value)
            hit = (value.get('calls', {}).get('A-selection', {}).get('result') == 'MODEL_COMPLETED'
                   and ('detail_binding' in value) == (crash == 'details_registered')
                   and 'A-details' not in value.get('calls', {}))
            if key == boundary.STATE_KEY and hit and not interrupted:
                interrupted.append(True)
                raise OSError('isolated durable checkpoint crash')
            return result
        monkeypatch.setattr(AttemptMaterialStore, 'write_recovery_record', crash_save)
        with pytest.raises(OSError, match='durable checkpoint'): run()
        assert len(calls) == 1 and calls[0][0].endswith('A-selection')
    elif crash == 'details_unknown':
        with pytest.raises(DeliveryExecutionUncertain): run()
        assert len(calls) == 2
    result = run()
    plan = result['plan']
    verified = boundary.verify(rt['root'], plan, rt['mode'], rt['canonical']['SCRIPT.md'],
                               canonical=rt['canonical'], attempt=rt['attempt'])
    assert verified['policy'] == 'planning-semantic-boundary@1'
    assert plan.needs[0].importance.value == 'required'
    if staged_design:
        assert len(staged_candidates) == 1, 'B/structural repair must not regenerate selection/details'
        assert sum('单次局部修复' in text for _, text in calls) == 1
    if risk == 'query_repair':
        from easel.integrations.planning_result_contract import SemanticProposal
        expected = deepcopy(initial)
        expected['needs'][0]['queries'] = ['white paper desk', 'blank paper tabletop', 'two plain sheets']
        checkpoint = json.loads((rt['root'] / 'planning/SEMANTIC_CHECKPOINT.json').read_text())
        assert checkpoint['proposal'] == SemanticProposal.model_validate(expected).model_dump(mode='json')
        assert checkpoint['initial']['needs'][0]['queries'] == ['白纸 桌面', 'white paper desk']
        assert sum('单次局部修复' in text for _, text in calls) == 1
        assert any('有界视觉复核' in text for _, text in calls)
    if risk == 'audio_omission':
        assert [n.modality_spec.kind for n in plan.needs] == ['bgm', 'image']
    if risk in {'xml_roundtrip', 'xml_answer_repair'}:
        assert [n.modality_spec.kind for n in plan.needs] == ['image', 'bgm', 'voice', 'sfx']
        assert plan.needs[0].intent.function == '让观众先看问题。\nnull'
        assert plan.needs[1].modality_spec.vocals_allowed is False
    if risk == 'semantic_repair':
        assert plan.needs[0].intent.description == '两张白纸放在桌上。'
        assert plan.needs[0].constraints['preferred_visual_details'] == '手部可不出现。'
    if risk == 'frame_header_repair':
        assert plan.needs[0].modality_spec.aspect_ratio is None
        assert plan.needs[0].intent.description == '两张白纸放在桌上。'
        assert sum('单次局部修复' in text for _, text in calls) == 1
    if risk == 'reentry':
        from easel.integrations.material_layer import PlanningIntegration
        integration = PlanningIntegration()
        formal = {key: result[key] for key in ('plan', 'script', 'scenes', 'treatment')}
        frozen = integration.persist(rt['attempt'], **formal)
        assert integration.load(frozen['attempt'])['plan'] == plan
        downgraded = {**rt['attempt'], 'planning_contract_version': 2}
        with pytest.raises(ValueError, match='不能降级'): integration.persist(downgraded, **formal)
        # Exact existing frozen-copy path, no model rerun or reinterpretation.
        from easel.integrations.hypit import service
        source = integration.load(frozen['attempt'])
        target = service.create_film_attempt(plan.creation_id, rt['attempt']['handoff']['handoff_id'],
                                            preparation_key='e' * 64, runtime_status='NOT_CONFIGURED')
        target = service.update_film_attempt(target['attempt_id'], event='test_vnext_copy', planning_contract_version=3)
        targetroot = Path(target['workspace']['path'])
        for name in ['MATERIAL_REQUIREMENTS.json', 'SEMANTIC_PLAN.json', 'SEMANTIC_CHECKPOINT.json',
                     *verified.get('raw_artifacts', ['SEMANTIC_A_RESULT.json'])]:
            service._copy_retry_checkpoint_file(rt['root'], targetroot, Path('planning') / name)
        copied = plan.model_copy(update={'attempt_id': target['attempt_id'], 'plan_id': 'vnext-frozen-copy'})
        origin = {'creation_id': plan.creation_id, 'attempt_id': plan.attempt_id, 'plan_id': plan.plan_id}
        copied_result = integration.persist(target, copied, script=result['script'], scenes=result['scenes'],
            treatment=result['treatment'], requirements_source={**source['requirements'], 'origin': origin})
        assert integration.load(copied_result['attempt'])['plan'] == copied
    before = len(calls)
    assert run()['plan'] == plan and len(calls) == before
    state = __import__('easel.materials.store', fromlist=['AttemptMaterialStore']).AttemptMaterialStore(rt['root']).read_recovery_record(boundary.STATE_KEY)
    assert sum(key == 'repair' for key in state['calls']) <= 1
    if two_stage:
        assert state['schema'] == (boundary.STAGED_JOURNAL if legacy_staged else boundary.VIEW_JOURNAL) and 'A' not in state['calls']
        assert sum(session.endswith('A-selection') for session, _ in calls) == 1
        assert sum(session.endswith('A-details') for session, _ in calls) == 1
        checkpoint = json.loads((rt['root'] / 'planning/SEMANTIC_CHECKPOINT.json').read_text())
        assert checkpoint['schema'] == (boundary.STAGED_CHECKPOINT if legacy_staged else boundary.VIEW_CHECKPOINT) and 'raw_a_sha256' not in checkpoint
        assert (rt['root'] / 'planning/SEMANTIC_INPUT_VIEW.json').exists() != legacy_staged
        assert not (rt['root'] / 'planning/SEMANTIC_A_RESULT.json').exists()
    assert boundary.policy_for(rt['attempt'], default='semantic-planning-compiler@7') == 'planning-semantic-boundary@1'
    with pytest.raises(ValueError, match='不能降级'):
        run_semantic_planning(rt['attempt'], rt['context'], rt['canonical'], rt['mode'],
            {'profile': 'fixture-only', 'thinking': 'off', 'timeout': 60}, execute,
            compiler_policy='semantic-planning-compiler@7')
    assert len(calls) == before
    if risk in {'carrier_removed', 'carrier_changed'}:
        from easel.materials.store import AttemptMaterialStore
        changed = deepcopy(state)
        if risk == 'carrier_removed': del changed['scope']['transport']
        else: changed['scope']['transport']['schema_sha256'] = '0' * 64
        AttemptMaterialStore(rt['root']).write_recovery_record(boundary.STATE_KEY, changed)
        with pytest.raises(ValueError, match='transport identity'): run()
        assert len(calls) == before
        checkpoint = rt['root'] / 'planning/SEMANTIC_CHECKPOINT.json'
        value = json.loads(checkpoint.read_text()); value['scope'] = changed['scope']
        checkpoint.write_text(json.dumps(value))
        with pytest.raises(ValueError, match='transport identity'):
            boundary.verify(rt['root'], plan, rt['mode'], rt['canonical']['SCRIPT.md'], attempt=rt['attempt'])
    if risk == 'legacy_frame_current':
        assert state['schema'] == boundary.FRAME_JOURNAL
        assert calls[0] == (session, message)
        checkpoint = json.loads((rt['root'] / 'planning/SEMANTIC_CHECKPOINT.json').read_text())
        assert checkpoint['schema'] == boundary.FRAME_CHECKPOINT
        for _, text in calls:
            if '有界视觉复核' in text:
                payload = json.loads(text.splitlines()[-1])
                assert 'review_source_policy' not in payload
                assert not any('selected_source' in q for q in payload['questions'])
    if risk == 'source_binding_verify':
        assert state['schema'] == boundary.JOURNAL
        assert state['scope']['transport']['review_source_policy'] == review.SOURCE_POLICY
        assert any('selected_source' in text for _, text in calls if '有界视觉复核' in text)
        original_binding = review.selected_source
        def wrong_position(*args):
            value = original_binding(*args); value['byte_start'] += 1
            return value
        with monkeypatch.context() as patch:
            patch.setattr(review, 'selected_source', wrong_position)
            with pytest.raises(ValueError, match='review identity'):
                boundary.verify(rt['root'], plan, rt['mode'], rt['canonical']['SCRIPT.md'], attempt=rt['attempt'])
        from easel.materials.store import AttemptMaterialStore
        changed = deepcopy(state); changed['scope']['transport']['review_source_policy'] = 'unknown'
        AttemptMaterialStore(rt['root']).write_recovery_record(boundary.STATE_KEY, changed)
        with pytest.raises(ValueError, match='transport identity'): run()
        assert len(calls) == before
    if risk == 'legacy_supported_pending':
        assert state['schema'] == boundary.SUPPORTED_JOURNAL
        assert state['scope']['transport']['runtime_sha256'] == boundary.SUPPORTED_RUNTIME_SHA
        assert calls[0] == (session, message)
    if risk == 'legacy_supported_current':
        assert state['schema'] == boundary.SUPPORTED_JOURNAL
        assert json.loads((rt['root'] / 'planning/SEMANTIC_CHECKPOINT.json').read_text())['schema'] == boundary.SUPPORTED_CHECKPOINT
    if risk == 'legacy_wire_current':
        assert state['schema'] == boundary.WIRE_JOURNAL
        assert json.loads((rt['root'] / 'planning/SEMANTIC_CHECKPOINT.json').read_text())['schema'] == boundary.WIRE_CHECKPOINT
        assert calls[0] == (session, message) and 'stage_ownership' not in json.loads(message.splitlines()[-1])
    if risk == 'legacy_tool_pending':
        assert state['schema'] == boundary.TOOL_A_JOURNAL
        assert 'support_policy' not in state['scope']['transport']
        assert json.loads((rt['root'] / 'planning/SEMANTIC_CHECKPOINT.json').read_text())['schema'] == boundary.TOOL_A_CHECKPOINT
        assert calls[0] == (session, message)
    if risk == 'legacy_carrier_pending':
        assert state['schema'] == boundary.LEGACY_JOURNAL and 'transport' not in state['scope']
        assert json.loads((rt['root'] / 'planning/SEMANTIC_CHECKPOINT.json').read_text())['schema'] == boundary.LEGACY_CHECKPOINT
        assert calls[0] == (session, message)
    if risk == 'tamper':
        checkpoint = rt['root'] / 'planning/SEMANTIC_CHECKPOINT.json'
        value = json.loads(checkpoint.read_text()); value['proposal']['needs'][0]['necessity'] = 'optional'
        checkpoint.write_text(json.dumps(value))
        with pytest.raises(ValueError): boundary.verify(rt['root'], plan, rt['mode'], rt['canonical']['SCRIPT.md'], attempt=rt['attempt'])
    if risk == 'wire_tamper':
        checkpoint = rt['root'] / 'planning/SEMANTIC_CHECKPOINT.json'
        value = json.loads(checkpoint.read_text())
        value['schema_bindings']['B-000']['stage'] = 'B-001'
        checkpoint.write_text(json.dumps(value))
        with pytest.raises(ValueError, match='wire identity'):
            boundary.verify(rt['root'], plan, rt['mode'], rt['canonical']['SCRIPT.md'], attempt=rt['attempt'])


@pytest.mark.parametrize('risk,crash', [
    ('reentry', None), ('structural_repair', None), ('semantic_repair', None),
    ('frame_header_repair', 'selection_captured'), ('frame_header_repair', 'details_registered'),
    ('frame_header_repair', 'details_unknown'), ('structural_repair', 'invalid_continuity'),
    ('frame_header_repair', 'legacy_details_unknown'), ('structural_repair', 'legacy_invalid_continuity'),
])
def test_vnext_staged_request_recovery(authority_runtime, monkeypatch, risk, crash):
    test_vnext_bounded_review_runtime(authority_runtime, monkeypatch, risk, two_stage=True, crash=crash)


def test_vnext_staged_capture_replay_identity(authority_runtime, monkeypatch):
    from copy import deepcopy
    from easel.integrations import semantic_boundary_run as boundary
    from easel.materials.store import AttemptMaterialStore
    rt = authority_runtime
    test_vnext_bounded_review_runtime(rt, monkeypatch, 'frame_header_repair', two_stage=True)
    plan = MaterialPlan.model_validate_json(read_file(rt['root'], 'MATERIAL_PLAN.json'))
    checkpoint = rt['root'] / 'planning/SEMANTIC_CHECKPOINT.json'
    original = checkpoint.read_bytes()
    for fault in ('binding', 'request', 'session', 'original', 'assembly',
                  'view', 'mapping', 'metadata', 'opaque_headers'):
        value = json.loads(original)
        target = checkpoint
        if fault == 'binding': value['detail_binding']['raw_selection_sha256'] = '0' * 64
        elif fault == 'opaque_headers': value['detail_binding']['opaque_headers_sha256'] = '0' * 64
        elif fault == 'request': value['capture']['A-details']['request_sha256'] = '0' * 64
        elif fault == 'session': value['capture']['A-details']['session'] += '-another'
        elif fault in {'original', 'assembly'}:
            target = rt['root'] / 'planning' / ('SEMANTIC_A_SELECTION.json' if fault == 'original' else 'SEMANTIC_A_ASSEMBLY.json')
        elif fault in {'view', 'mapping', 'metadata'}:
            target = rt['root'] / 'planning/SEMANTIC_INPUT_VIEW.json'
        previous = target.read_bytes()
        if target == checkpoint: target.write_text(json.dumps(value, ensure_ascii=False))
        elif fault == 'original': target.write_bytes(previous + b'\n')
        elif fault in {'view', 'mapping', 'metadata'}:
            snapshot = json.loads(previous)
            if fault == 'view': snapshot['view']['policy'] += '-forged'
            elif fault == 'mapping': snapshot['source_mapping'].clear()
            else: snapshot['metadata'].append({'path': ['inputs', 'forged'], 'value': True})
            target.write_text(json.dumps(snapshot, ensure_ascii=False))
        else:
            assembly = json.loads(previous); assembly['needs'][0]['necessity'] = 'optional'
            target.write_text(json.dumps(assembly, ensure_ascii=False))
        with pytest.raises(ValueError):
            boundary.verify(rt['root'], plan, rt['mode'], rt['canonical']['SCRIPT.md'], attempt=rt['attempt'])
        target.write_bytes(previous)
    store = AttemptMaterialStore(rt['root'])
    journal = store.read_recovery_record(boundary.STATE_KEY)
    changed = deepcopy(journal); changed['detail_binding']['scope_sha256'] = '0' * 64
    store.write_recovery_record(boundary.STATE_KEY, changed)
    with pytest.raises(ValueError, match='details identity'):
        boundary.run(rt['attempt'], rt['context'], rt['canonical'], rt['mode'],
                     journal['route'], lambda *_a, **_kw: pytest.fail('tamper must not dispatch'))
    store.write_recovery_record(boundary.STATE_KEY, journal)
    changed = deepcopy(journal)
    changed['input_view_snapshot']['source_mapping'].clear()
    store.write_recovery_record(boundary.STATE_KEY, changed)
    with pytest.raises(ValueError, match='input view'):
        boundary.run(rt['attempt'], rt['context'], rt['canonical'], rt['mode'],
                     journal['route'], lambda *_a, **_kw: pytest.fail('snapshot tamper must not dispatch'))
    store.write_recovery_record(boundary.STATE_KEY, journal)
    assert boundary.verify(rt['root'], plan, rt['mode'], rt['canonical']['SCRIPT.md'], attempt=rt['attempt'])['policy'] == boundary.POLICY


@pytest.mark.parametrize('risk', ['immutable_patch', 'whole_context', 'capacity', 'false_accept_risk', 'xml_codec', 'atomic_frame', 'literal_source_binding'])
def test_vnext_review_contract_protection(risk):
    if risk == 'literal_source_binding':
        from copy import deepcopy
        import hashlib
        from easel.integrations import planning_semantic_review as review
        from easel.integrations.semantic_planning import source_catalog
        from easel.integrations.planning_result_contract import SemanticProposal
        document = '1. 开场标题\r\n\r\n画面：门边人物与钥匙。\u2028' + '2. 固定位置\n画面：小钥匙托盘，中文「标点」。\n'
        inputs = {'confirmed': {'SCENES.md': document, 'SCRIPT.md': '冻结正文。'}, 'mode_documents': {}}
        catalog = source_catalog(inputs['confirmed'], {})
        original = vnext_proposal(); original['needs'][0]['scope'] = 'scene-2'
        original['needs'][0]['conditions'] = [{'text': '小钥匙托盘。', 'strength': 'required', 'responsibility': 'material'}]
        proposal = SemanticProposal.model_validate(original)
        old = review.questions(proposal, inputs, catalog, supported=True)
        new = review.questions(proposal, inputs, catalog, supported=True, source_bound=True)
        assert old['evidence'] == new['evidence'] and len(old['questions']) == len(new['questions'])
        assert [q for q in old['questions'] if q['kind'] == 'frozen_visual_coverage'] == [q for q in new['questions'] if q['kind'] == 'frozen_visual_coverage']
        assert 'selected_source' not in old['questions'][0]
        binding = new['questions'][0]['selected_source']
        assert binding['text'] == '画面：门边人物与钥匙。'  # Wrong semantic source is visible, never auto-accepted.
        assert binding['line'] == 3 and binding['document_sha256'] == hashlib.sha256(document.encode()).hexdigest()
        assert document.encode()[binding['byte_start']:binding['byte_end']].decode() == binding['text']
        assert '小钥匙托盘' not in binding['text'] and '小钥匙托盘' in new['visual_candidates'][0]['conditions'][0]['text']
        assert review.selected_source('scene-3', inputs, catalog)['text'] == '2. 固定位置'  # Title + full context remains reviewable.
        assert '小钥匙托盘' in review.selected_source('scene-4', inputs, catalog)['text']
        for kind in ('scene', 'segment', 'event'):
            assert review.selected_source(f'{kind}-4', inputs, catalog)['kind'] == kind
        global_binding = review.selected_source('global', inputs, catalog)
        assert 'text' not in global_binding and global_binding['line'] is None
        assert old['evidence'][global_binding['evidence_id']]['value'][global_binding['document_path']] == document
        bad = deepcopy(catalog); bad['scene']['scene-2'] = '其他原文'
        with pytest.raises(ValueError, match='catalog'): review.selected_source('scene-2', inputs, bad)
        with pytest.raises(ValueError, match='source position'): review.selected_source('scene-99', inputs, catalog)
        bad_global = deepcopy(catalog); bad_global['global']['global'] = '替换全文'
        with pytest.raises(ValueError, match='Global review source'): review.selected_source('global', inputs, bad_global)
        # New bindings participate in the existing complete-question reuse signature.
        answers = review.validate_answers({'answers': [{'question': q['question'], 'decision': 'ACCEPT', 'evidence': [0], 'reason': '外部固定对照'} for q in old['questions']]}, {**old, 'support_policy': None})
        kept, pending = review.recheck(old, [answers], new)
        assert not kept and len(pending['questions']) == len(new['questions'])
        # The whole-document evidence is already present. Repeating it per
        # global condition would turn a legal request into a capacity failure.
        long_doc = '中文场景。' * 15000
        long_inputs = {'confirmed': {'SCENES.md': long_doc, 'SCRIPT.md': '正文'}, 'mode_documents': {}}
        long_catalog = source_catalog(long_inputs['confirmed'], {})
        global_item = deepcopy(original); global_item['needs'][0]['scope'] = 'global'
        global_item['needs'][0]['conditions'] *= 8
        global_proposal = SemanticProposal.model_validate(global_item)
        before = review.review_batches(review.questions(global_proposal, long_inputs, long_catalog, supported=True))[0]
        after = review.review_batches(review.questions(global_proposal, long_inputs, long_catalog, supported=True, source_bound=True))[0]
        assert before['evidence'] == after['evidence'] and after['evidence'][0]['value']['SCENES.md'] == long_doc
        before_text = review.checked_message(review.review_message(before))
        after_text = review.checked_message(review.review_message(after))
        assert len(after_text.encode()) - len(before_text.encode()) < 12000
        for q in after['questions']:
            if 'selected_source' in q:
                ref = q['selected_source']
                bound = after['evidence'][ref['evidence_id']]['value'][ref['document_path']]
                assert hashlib.sha256(bound.encode()).hexdigest() == ref['document_sha256']
                assert ref['byte_start'] == 0 and ref['byte_end'] == len(bound.encode())
        return
    if risk == 'atomic_frame':
        from copy import deepcopy
        from easel.integrations import planning_wire
        from easel.integrations.planning_result_contract import semantic_tool_schema, SemanticProposal
        catalog = {'global': {'global': '原稿'}, 'scene': {'scene-1': '原稿'},
                   'event': {'event-1': '原稿'}, 'voice': {}, 'continuity': {}}
        canonical = semantic_tool_schema(catalog, compiled=True)
        codec = planning_wire.project(canonical, 'A', atomic_framing=True)
        for fields in [{}, {'frame': 'unconstrained'}, {'frame': 'match_output'},
                       {'frame': 'native', 'native_ratio': '4:5'}]:
            original = vnext_proposal(); original['needs'][0].update(fields)
            original['needs'][0]['purpose'] = '保留原文中的framing和中文「标点」。'
            encoded = codec.encode(original)
            assert 'frame' not in encoded['needs'][0] and 'native_ratio' not in encoded['needs'][0]
            assert not codec.errors(encoded)
            transported = json.loads(xml_reference_transport(json.dumps(encoded, ensure_ascii=False), {'schema': codec.schema}))
            assert SemanticProposal.model_validate(codec.decode_valid(transported)) == SemanticProposal.model_validate(original)
        for framing in [{'mode': 'match_output', 'ratio': '9:16'}, {'mode': 'native'},
                        {'mode': 'unknown'}, None, {'mode': 'native', 'ratio': '9：16'},
                        {'mode': 'unconstrained', 'extra': True}]:
            invalid = codec.encode(vnext_proposal()); invalid['needs'][0]['framing'] = framing
            assert codec.errors(invalid)
            with pytest.raises(ValueError, match='atomic frame'): codec.decode_candidate(invalid)
        invalid = vnext_proposal(); invalid['needs'][0].update(frame='match_output', native_ratio='9:16')
        with pytest.raises(ValueError, match='Illegal split frame'): codec.encode(invalid)
        with pytest.raises(ValueError, match='Split frame'): codec.decode_candidate(invalid)
        # Known field names elsewhere never receive a guessed semantic rewrite.
        unrelated = planning_wire.project({'type': 'object', 'additionalProperties': False,
            'properties': {'frame': {'type': 'string', 'maxLength': 8},
                           'native_ratio': {'type': 'string', 'maxLength': 8}},
            'required': ['frame', 'native_ratio']}, 'fixture', atomic_framing=True)
        assert unrelated.decode_valid(unrelated.encode({'frame': 'raw', 'native_ratio': 'literal'})) == {'frame': 'raw', 'native_ratio': 'literal'}
        for item_schema in [
                {'$ref': '#/$defs/NeedProposal', 'properties': {'frame': {'const': 'native'}}},
                {'allOf': [{'$ref': '#/$defs/NeedProposal'}, {'properties': {'native_ratio': {'const': '4:5'}}}]}]:
            constrained = deepcopy(canonical)
            constrained['properties']['needs']['items'] = item_schema
            with pytest.raises(ValueError, match='predicate'):
                planning_wire.project(constrained, 'A', atomic_framing=True)
        bad = vnext_proposal(); bad['needs'][0]['framing'] = {'mode': 'native', 'ratio': '4:5'}
        with pytest.raises(ValueError): codec.encode(bad)
        return
    if risk == 'xml_codec':
        from copy import deepcopy
        from jsonschema import Draft202012Validator
        from easel.integrations import planning_wire
        schema = {'type': 'object', 'additionalProperties': False,
            '$defs': {'Text': {'anyOf': [{'type': 'string', 'minLength': 1, 'maxLength': 4}, {'type': 'null'}]}},
            'properties': {'quote': {'$ref': '#/$defs/Text', 'description': '原引用'}}, 'required': ['quote']}
        codec = planning_wire.project(schema, 'B-000')
        assert codec.identity['canonical_schema_sha256'] != codec.identity['wire_schema_sha256']
        for original in [{'quote': None}, {'quote': 'null'}, {'quote': '中文'}, {'quote': 'false'}]:
            encoded = codec.encode(original)
            if Draft202012Validator(schema).is_valid(original):
                assert not codec.errors(encoded)
                transported = json.loads(xml_reference_transport(json.dumps(encoded, ensure_ascii=False), {'schema': codec.schema}))
                assert codec.decode_valid(transported) == original
            else:
                assert codec.errors(encoded)  # Original length bound retained at value.
        for quote in [{}, {'null': 1}, {'null': False}, {'value': None}, {'value': 'x', 'null': True}, {'unknown': True}, None, 'null']:
            candidate = {'quote': quote}
            assert codec.errors(candidate)
            with pytest.raises(ValueError): codec.decode_candidate(candidate)
        assert codec.errors({'quote': {'value': 'abcde'}})
        # Reference siblings are conjunctions, not overwritten constraints.
        sibling = deepcopy(schema)
        sibling['properties']['quote']['maxLength'] = 2
        projected = planning_wire.project(sibling, 'repair')
        assert projected.errors(projected.encode({'quote': 'null'}))
        assert not projected.errors(projected.encode({'quote': '中'}))
        for constraint in [{'enum': ['x']}, {'not': {'type': 'null'}}]:
            excluded = deepcopy(schema)
            excluded['properties']['quote'].update(constraint)
            protected = planning_wire.project(excluded, 'B')
            assert protected.errors({'quote': {'null': True}})
            with pytest.raises(ValueError): protected.decode_candidate({'quote': {'null': True}})
            for value in ['x', 'null', None]:
                encoded = protected.encode({'quote': value})
                assert (not protected.errors(encoded)) == Draft202012Validator(excluded).is_valid({'quote': value})
        for keyword, predicate in [('if', {'properties': {'quote': {'const': None}}}),
                                   ('allOf', [{'properties': {'quote': {'type': 'null'}}}]),
                                   ('dependentSchemas', {'quote': {'required': ['quote']}})]:
            with pytest.raises(ValueError, match='predicate'):
                planning_wire.project({**schema, keyword: predicate}, 'B')
        recursive = deepcopy(schema); recursive['$defs']['Text'] = {'$ref': '#/$defs/Text'}
        with pytest.raises(ValueError, match='nonrecursive'): planning_wire.project(recursive, 'B')
        with pytest.raises(ValueError, match='local'): planning_wire.project({'$ref': 'https://example.invalid/schema'}, 'B')
        return
    from easel.integrations import planning_semantic_review as review
    from easel.integrations.semantic_boundary import parse_proposal, project_proposal
    from easel.integrations.planning_result_contract import MAX_REQUEST_BYTES
    data = json.loads((Path(__file__).resolve().parents[1] / 'docs/acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/batch10-projection-input.json').read_text())
    scope = data['scope']; inputs = scope['authority_inputs']
    value = vnext_proposal()
    value['needs'][0]['queries'] = ['white paper desk', 'two blank sheets table', 'paper room still life']
    proposal = parse_proposal(value, scope['catalog'])
    normalized = proposal.model_dump(mode='json')
    directory = review.questions(proposal, inputs, scope['catalog'])
    if risk == 'immutable_patch':
        target = [{'kind': 'visual_choices', 'path': [0], 'issue': 'unaccepted framing'}]
        for field, replacement in [('necessity', 'optional'), ('conditions', []), ('queries', [])]:
            changed = {**normalized['needs'][0], field: replacement}
            with pytest.raises(ValueError): review.apply_patches(normalized, {'patches': [{'target': 0, 'value': changed}]}, target)
        with pytest.raises(ValueError): review.apply_patches(normalized, {'patches': [{'target': 99, 'value': normalized['needs'][0]}]}, target)
        response = {'answers': [{'question': q['question'], 'decision': 'ACCEPT', 'evidence': [], 'reason': '猜测'} for q in directory['questions']]}
        with pytest.raises(ValueError, match='evidence'): review.validate_answers(response, review.review_batches(directory)[0])
        responses = [review.validate_answers({'answers': [
            {'question': q['question'], 'decision': 'ACCEPT', 'evidence': [0], 'reason': '原冻结语境支持。'}
            for q in b['questions']]}, b) for b in review.review_batches(directory)]
        for field, replacement in [('scope', 'global'), ('purpose', '另一个用途'), ('modality', 'video')]:
            from copy import deepcopy
            changed = deepcopy(normalized); changed['needs'][0][field] = replacement
            if changed == normalized: continue
            updated = review.questions(parse_proposal(changed, scope['catalog']), inputs, scope['catalog'])
            kept, pending = review.recheck(directory, responses, updated)
            required_recheck = [q['question'] for q in updated['questions']
                               if q['kind'] == 'complete_obligation' and q['target'][0] == 0]
            assert required_recheck and all(q not in kept for q in required_recheck)
            assert set(required_recheck) <= {q['question'] for q in pending['questions']}
    elif risk == 'whole_context':
        for batch in review.review_batches(directory):
            assert batch['evidence'][0]['value'] == inputs['confirmed']
            assert batch['evidence'][2]['value'] == inputs['mode_documents']
            assert batch['evidence'][4]['value'] == inputs['truth_packet']
            assert 'white paper desk' not in review.compact(batch)
        # Candidate punctuation and source text are not re-split into units.
        quoted = '正文「先看问题，再做决定。」不在图中；由后期叠加。'
        normalized['needs'][0]['conditions'][1]['text'] = quoted
        changed = review.questions(parse_proposal(normalized, scope['catalog']), inputs, scope['catalog'])
        assert any(q['candidate'].get('text') == quoted for q in changed['questions'])
    elif risk == 'capacity':
        with pytest.raises(ValueError, match='no clipping'): review.checked_message('语' * MAX_REQUEST_BYTES)
        from easel.integrations.planning_result_contract import maximum_compact_bytes, MAX_RESULT_BYTES
        schema = review.patch_schema([{'kind': 'complete_obligation', 'path': [0, 0], 'issue': 'unaccepted'}])
        assert maximum_compact_bytes(schema) < MAX_RESULT_BYTES
    else:
        # Explicit residual risk: valid provenance + incorrect B ACCEPT is not
        # a semantic theorem. Software cannot invent a lexical entailment Gate.
        normalized['needs'][0]['conditions'].append({'text': '禁止任何手部。', 'strength': 'required',
                                                      'responsibility': 'material', 'meaning': 'observable'})
        proposal = parse_proposal(normalized, scope['catalog'])
        directory = review.questions(proposal, inputs, scope['catalog'])
        responses = [review.validate_answers({'answers': [
            {'question': q['question'], 'decision': 'ACCEPT', 'evidence': [0], 'reason': '故意错误的外部判断对照。'}
            for q in b['questions']]}, b) for b in review.review_batches(directory)]
        assert not review.semantic_targets(directory, responses)
        plan, _, _ = project_proposal(proposal, inputs=inputs, catalog=scope['catalog'],
            creation_id=scope['creation_id'], attempt_id=scope['attempt_id'], refs=scope['context_refs'], mode=scope['mode'])
        assert '禁止任何手部。' in plan.needs[0].intent.description
        independent_expected = 'FAIL: no frozen hard prohibition of every hand'
        assert independent_expected.startswith('FAIL')  # Never report this as semantic success.


@pytest.mark.parametrize('risk', ['success', 'semantic_reject', 'truth_reject', 'capture_truncated', 'source_tamper', 'async_tamper', 'between_resume', 'output_as_source'])
def test_vnext_continuous_owner_boundary(prep_env, monkeypatch, risk):
    import asyncio, re, hashlib
    from tests.test_creation_preparation import web, prep, creation, write_drafts
    from tests.planning_material_matrix.planning_eval import confirm_sample, PlanningEvalBoundary
    from easel.integrations.material_layer import PlanningIntegration
    from easel.integrations.openclaw_delivery import PlanningResultError
    # No policy override: this exercises the actual fresh product default.
    assert web.PLANNING_COMPILER_POLICY == 'planning-semantic-boundary@1'
    sample = json.loads((Path(__file__).parent / 'fixtures/planning-eval-r4-2026-10-07/samples.json').read_text())['samples'][0]
    work = confirm_sample(sample)
    calls = []
    def external(message, timeout=None, session=None, **options):
        calls.append((session, message))
        if message.startswith('〔Easel Semantic Planning vNext A-'):
            assert options['capture_reply'] and options['reply_contract'] == 'planning-result-v3'
            assert options['structured_result']['name'] == 'submit_semantic_plan'
            assert options['retry_failed'] is False
            if risk == 'capture_truncated': raise PlanningResultError('MODEL_TRUNCATED')
            if risk in {'source_tamper', 'async_tamper'}:
                attempt = creation.get_creation(work['id'])['hypit_attempts'][-1]
                (Path(attempt['workspace']['path']) / 'planning/SCENES.md').write_text('被外部执行修改的确认稿。')
                if risk == 'async_tamper':
                    from easel.creation_delivery import DeliveryExecutionUncertain
                    raise DeliveryExecutionUncertain('Original external request still pending')
            value = vnext_proposal()
            value['needs'][0]['conditions'].append({'text': '在后期叠加正文。', 'strength': 'required', 'responsibility': 'postproduction'})
            return staged_fixture_wire(message, value)
        if '有界视觉复核' in message:
            if risk == 'between_resume':
                from easel.creation_delivery import DeliveryExecutionUncertain
                with creation.edit_creation(work['id']) as current:
                    attempt_id = current['hypit_attempts'][-1]['attempt_id']
                    current['delivery'].setdefault('agent_calls', {})['original-B'] = {
                        'run_id': 'easel-original-B', 'profile': web.OPENCLAW_PROFILE, 'status': 'pending',
                        'session_key': 'agent:main:semantic-' + attempt_id + '-vnext-B-000'}
                raise DeliveryExecutionUncertain('Original B still pending')
            assert options['capture_reply'] and options['reply_contract'] == 'planning-result-v3'
            payload = json.loads(message.splitlines()[-1])
            from easel.integrations.planning_structured import request_for
            assert options['structured_result'] == request_for(payload['response_schema'])
            answers = supported_fixture_answers(payload, [{'question': q['question'],
                'decision': 'UNRESOLVED' if risk == 'semantic_reject' else 'ACCEPT',
                'evidence': [0], 'reason': '明确外部对照：冻结两纸条件/后期叠字及正常表达。'} for q in payload['questions']])
            if risk == 'output_as_source':
                from easel.integrations.planning_review_support import source_catalog
                source, entry = next((key, row) for key, row in source_catalog(payload).items()
                                     if row['origin'] == 'confirmed_spec')
                answers[0]['support'] = [{'source': source,
                    'quote': entry['value'] if isinstance(entry['value'], str) else None, 'role': 'output_authority'}]
                answers[0]['evidence'] = [entry['evidence_id']]
            return json.dumps(fixture_review_wire(payload, answers))
        if '单次局部修复' in message:
            # Deliberately invalid local result; no second allowance or Truth.
            return json.dumps({'patches': []})
        if message.startswith('〔Easel Truth 来源引用审阅〕'):
            _r4_current_truth_reply(message, reject=risk == 'truth_reject')
            return 'fixed source-ref Truth review'
        if message.startswith('〔Easel Script 系统审阅〕'):
            target = Path(re.search(r'只写 (.+\.json)，JSON 结构', message)[1])
            response = json.loads(message.split('（逐项替换判断，不增加字段）：\n', 1)[1].split('\n写入后停止。', 1)[0])
            for row in response['decisions']:
                row.update(kind='unresolved' if risk == 'truth_reject' else 'creative_expression', reason='独立固定Truth判断。')
            target.write_text(json.dumps(response))
        elif message.startswith('〔Easel Script 审阅报告修正〕'):
            # Existing bounded report repair stays unresolved; never bypass it.
            return 'fixed unresolved external report'
        else:
            current = creation.get_creation(work['id'])
            paths = prep.preparation_paths(work['id'], current['preparation']['operation_key'])
            write_drafts(current, paths['draft'])
        return 'fixed external boundary complete'
    monkeypatch.setattr(web, 'run_agent_sync', external)
    monkeypatch.setattr(web, '_hypit_runtime_profile', lambda: None)
    if risk == 'between_resume':
        from easel.integrations import openclaw_delivery
        def original_terminal(creation_id, **kwargs):
            with creation.edit_creation(creation_id) as current:
                assert current['delivery']['agent_calls']['original-B']['run_id'] == 'easel-original-B'
                current['delivery']['agent_calls']['original-B']['status'] = 'ok'
        monkeypatch.setattr(openclaw_delivery, 'reconcile_agent_calls', original_terminal)
    boundary = PlanningEvalBoundary()
    async def scenario():
        first = await boundary.advance(work['id'], web)
        assert first['boundary_reached'] == (risk == 'success')
        count = len(calls)
        if risk == 'between_resume':
            attempt = creation.get_creation(work['id'])['hypit_attempts'][-1]
            (Path(attempt['workspace']['path']) / 'planning/SCENES.md').write_text('重入前修改的确认稿。')
        second = await boundary.advance(work['id'], web)
        if risk == 'between_resume':
            await boundary.advance(work['id'], web)  # Original observation precedes Planning recovery.
        assert len(calls) == count
        if risk == 'success': assert second['boundary_reached']
    asyncio.run(scenario())
    assert boundary.supply_calls == 0 and not boundary.state_violations
    current = creation.get_creation(work['id'])
    attempt = current['hypit_attempts'][-1]
    root = Path(attempt['workspace']['path'])
    assert not attempt.get('material_gate') and not attempt.get('production_authoring')
    if risk == 'success':
        loaded = PlanningIntegration().load(attempt)
        assert loaded['truth_ledger']['status'] == 'PASSED'
        assert loaded['plan'].policy['semantic_compiler'] == web.PLANNING_COMPILER_POLICY
        assert loaded['plan'].needs[0].intent.description == '两张白纸放在桌上。'
        assert '在后期叠加正文。' in loaded['plan'].needs[0].intent.function
        assert root.joinpath('planning/SCRIPT.md').read_bytes() == current['delivery']['video_plan']['script'].encode()
        for name in ('SEMANTIC_A_SELECTION.json', 'SEMANTIC_A_DETAILS.json'):
            assert hashlib.sha256(root.joinpath('planning', name).read_bytes()).hexdigest()
    if risk in {'semantic_reject', 'capture_truncated', 'source_tamper', 'async_tamper', 'between_resume'}:
        assert not root.joinpath('planning/manifest.json').exists()
    if risk in {'source_tamper', 'async_tamper', 'between_resume'}:
        from easel.materials.store import AttemptMaterialStore
        state = AttemptMaterialStore(root).read_recovery_record('semantic-planning-vnext')
        assert state['terminal_failure'] == 'FROZEN_SOURCE_CHANGED'
        assert root.joinpath('planning/SCENES.md').read_text() != current['delivery']['video_plan']['scenes']
    if risk == 'capture_truncated':
        assert not any('视觉复核' in m or '局部修复' in m for _, m in calls)


@pytest.mark.parametrize('risk', ['submissions', 'deadline_observation', 'round2_gate', 'roster'])
def test_vnext_development_bounds(tmp_path, risk):
    from tests.planning_material_matrix import planning_eval_run as runner
    parent, first, second = tmp_path / 'goal', tmp_path / 'round1', tmp_path / 'round2'
    def phase(index, source='one', started=100):
        return {'attempt_id': 'isolated', 'session_id': f'isolated-{index}', 'message_sha256': f'message-{index}',
                'capture_reply': True, 'reply_contract': 'planning-result-v2', 'retry_failed': False,
                'fixed_commit': 'fixed', 'fixed_source': source, 'sample_started_at': started}
    if risk == 'roster':
        rows = json.loads(runner.SAMPLES.read_text())['samples']
        selected = runner.development_samples(rows)
        assert len(selected) == 3 and all(s['split'] == 'development' for s in selected)
        return
    runner.reserve_development_request(parent, first, 1, 0, phase(0), now=100)
    if risk == 'submissions':
        for index in range(1, 32): runner.reserve_development_request(parent, first, 1, 0, phase(index), now=100 + index)
        with pytest.raises(runner.EvalStateViolation): runner.reserve_development_request(parent, first, 1, 0, phase(32), now=140)
        assert len(json.loads((parent / 'development-budget.json').read_text())['requests']) == 32
    elif risk == 'deadline_observation':
        with pytest.raises(runner.EvalStateViolation): runner.reserve_development_request(parent, first, 1, 0, phase(1), now=581)
        observed = runner.reserve_development_request(parent, first, 1, 0, phase(0), now=1000)
        assert observed['existing_request_observation']
        with pytest.raises(runner.EvalStateViolation, match='new submission forbidden'):
            runner.authorize_development_submit(parent, first, 1, observed['request_sha256'], 'easel-original', now=1000)
        outcome = {'index': 0, 'result': 'CONTRACT_VALID_SEMANTICS_PENDING'}
        runner.finish_development_run(parent, 1, first, outcome, now=590)
        assert outcome['result'] == 'FAIL'  # A late valid contract is no Eval PASS.
    else:
        outcome = {'index': 0, 'result': 'FAIL'}
        runner.finish_development_run(parent, 1, first, outcome, now=110)
        sealed = (parent / 'development-budget.json').read_bytes()
        runner.finish_development_run(parent, 1, first, outcome, now=9000)
        assert (parent / 'development-budget.json').read_bytes() == sealed
        with pytest.raises(runner.EvalStateViolation): runner.reserve_development_request(parent, second, 2, 0, phase(100, 'two'), now=200)
        path = parent / 'development-budget.json'; budget = json.loads(path.read_text())
        budget['round2_software_gate'] = {'status': 'PASS', 'commit': 'fixed', 'source_sha256': 'two',
            'root_cause': 'targeted software fault', 'original_execution_reconciled': True, 'historical_unchanged': True}
        path.write_text(json.dumps(budget))
        runner.reserve_development_request(parent, second, 2, 0, phase(100, 'two', 200), now=200)
        final = json.loads(path.read_text())
        assert len(final['requests']) == 2 and final['rounds']['1']['elapsed_seconds'] == 10
        with pytest.raises(runner.EvalStateViolation): runner.reserve_development_request(parent, second, 3, 0, phase(101, 'three'), now=201)


@pytest.mark.parametrize('risk', ['goal_identity', 'stopped_observation', 'native_submit_cut', 'completed_seal'])
def test_vnext_development_recovery(prep_env, tmp_path, monkeypatch, risk):
    import sys
    from tests.planning_material_matrix import planning_eval_run as runner
    from tests.planning_material_matrix.planning_eval import PlanningEvalBoundary
    from easel.creation_delivery import active_delivery
    from easel.integrations.openclaw_delivery import run_delivery_agent
    parent, directory = tmp_path / 'goal', tmp_path / 'round1'
    monkeypatch.setattr(runner, 'production', lambda: {'sha256': runner.SOURCE})
    monkeypatch.setattr(runner, 'protected', lambda: {})
    monkeypatch.setattr(runner, 'tool_hashes', lambda: {})
    monkeypatch.setattr(runner, 'head', lambda: runner.COMMIT)
    args = ['eval', '--directory', str(directory), '--development', '--goal-directory', str(parent)]
    monkeypatch.setattr(sys, 'argv', args)
    assert runner.main() == 0
    roster = json.loads((directory / 'roster.json').read_text()); row = roster['runs'][0]
    (directory / 'user-authorization.json').write_text(json.dumps({'raw_stream_exception_accepted': True,
        'billing_scope': 'existing purchased text subscription quota only'}))
    phase = {'attempt_id': 'test', 'session_id': 'test', 'message_sha256': 'test',
             'fixed_commit': runner.COMMIT, 'fixed_source': runner.SOURCE, 'sample_started_at': 100}
    reserved = runner.reserve_development_request(parent, directory, 1, 0, phase, now=100)
    results = directory / 'runs'; results.mkdir()
    if risk == 'goal_identity':
        monkeypatch.setattr(sys, 'argv', args[:-1] + [str(tmp_path / 'replacement-goal')])
        with pytest.raises(runner.EvalStateViolation, match='identity changed'): runner.main()
    elif risk == 'stopped_observation':
        runner.save(results / 'run-00.json', {'index': 0, 'result': 'FAIL'})
        observed = []
        with runner.isolated_process(directory / 'eval-runtime', runner.web):
            with runner.creation.edit_creation(row['creation_id']) as work:
                work['delivery']['agent_calls'] = {'original': {'run_id': 'easel-original', 'profile': 'fixture', 'status': 'pending'}}
        from easel.integrations import openclaw_delivery
        monkeypatch.setattr(openclaw_delivery, 'reconcile_agent_calls', lambda *a, **k: observed.append(a[0]))
        monkeypatch.setattr(runner, 'check_authorized_route', lambda *a: pytest.fail('Observation used submission admission'))
        monkeypatch.setattr(runner.web, 'run_agent_sync', lambda *a, **k: pytest.fail('Observation submitted'))
        before = (parent / 'development-budget.json').read_bytes()
        monkeypatch.setattr(sys, 'argv', args + ['--one', '0', '--observe-only'])
        assert runner.main() == 0 and observed == [row['creation_id']]
        assert (parent / 'development-budget.json').read_bytes() == before
    elif risk == 'completed_seal':
        runner.save(results / 'run-00.json', {'index': 0, 'result': 'CONTRACT_VALID_SEMANTICS_PENDING'})
        monkeypatch.setattr(runner.time, 'time', lambda: 590)
        monkeypatch.setattr(sys, 'argv', args + ['--one', '0'])
        assert runner.main() == 2
        assert json.loads((results / 'run-00.json').read_text())['result'] == 'FAIL'
    else:
        with runner.isolated_process(directory / 'eval-runtime', runner.web):
            boundary = PlanningEvalBoundary(before_submit=lambda params: runner.authorize_development_submit(
                parent, directory, 1, reserved['request_sha256'], params['idempotencyKey'], now=1000))
            token = active_delivery.set(row['creation_id'])
            try:
                with boundary.guarded(), pytest.raises(runner.EvalStateViolation, match='new submission forbidden'):
                    run_delivery_agent([*runner.web.openclaw_base_cmd(), '--profile', 'easel', 'agent', '--agent', 'main',
                        '--session-key', 'agent:main:isolated-test', '--session-id', 'isolated-test', '--message', '{}'],
                        capture_reply=True, reply_contract='planning-result-v2',
                        runner=lambda *a, **k: pytest.fail('RPC escaped expired native submission guard'))
            finally: active_delivery.reset(token)
            calls = runner.creation.get_creation(row['creation_id'])['delivery']['agent_calls']
            assert len(calls) == 1 and next(iter(calls.values()))['status'] == 'submitting'


@pytest.mark.parametrize('risk', ['slots', 'final_source', 'derived', 'forged_quote',
                                 'unknown_field', 'legitimate_native', 'postproduction', 'whole_obligation', 'capacity'])
def test_supported_review_frozen_references(risk):
    """Derived offline controls; the real failed B and its verdict remain intact."""
    from copy import deepcopy
    import jsonschema
    from easel.integrations import planning_review_support as support
    folder = Path(__file__).parent / 'fixtures/planning-vnext-development-2026-10-08'
    original = json.loads((folder / 'autonomous-round1-review-input.json').read_text())
    batch = deepcopy(original)
    if risk == 'capacity':
        from easel.integrations.planning_result_contract import maximum_compact_bytes, MAX_RESULT_BYTES
        batch['questions'] = [{**batch['questions'][0], 'question': i} for i in range(48)]
        assert maximum_compact_bytes(support.response_schema(batch)) <= MAX_RESULT_BYTES
        assert support.source_catalog(batch) == support.source_catalog(original)
        return
    if risk == 'legitimate_native':
        batch['evidence'][0]['value']['SCENES.md'] += '\n源图必须原生9:16；这是独立素材要求。'
    question = batch['questions'][3 if risk == 'postproduction' else 1 if risk == 'whole_obligation' else 0]
    batch['questions'] = [question]
    catalog = support.source_catalog(batch)
    def source(origin, path):
        return next((key, row) for key, row in catalog.items() if row['origin'] == origin and row['path'] == path)
    handle, row = source('confirmed_original', ['SCENES.md'])
    quote = ('源图必须原生9:16；这是独立素材要求。' if risk == 'legitimate_native' else
             '在后期叠加正文' if risk == 'postproduction' else '一张静态桌面图')
    role = 'authority'
    if risk == 'final_source':
        handle, row = source('confirmed_spec', ['aspect_ratio']);quote = row['value'];role = 'output_authority'
    elif risk == 'derived':
        handle, row = source('derived_preparation', ['visual_constraints', 1]);quote = row['value']
    elif risk == 'forged_quote':
        quote = '一张静态桌面图，无人物、无动作'
        assert quote not in row['value']
    elif risk == 'unknown_field':
        assert not any(r['origin'] == 'derived_preparation' and r['path'] == ['visual_preference'] for r in catalog.values())
        handle = 'brief.visual_preference'  # Never a program-issued source handle.
    payload = {support.slot(question): {'decision': 'ACCEPT', 'reason': '离线支持资格对照，非真实审核结论。',
        'support': [{'source': handle, 'quote': quote, 'role': role}]}}
    if risk == 'slots':
        with pytest.raises(ValueError, match='slots'): support.decode_slots({}, batch)
        with pytest.raises(ValueError, match='slots'): support.decode_slots({**payload, 'question-9999': {}}, batch)
        assert 'question' not in support.response_schema(batch)['properties'][support.slot(question)]['properties']
        return
    if risk != 'unknown_field': jsonschema.validate(payload, support.response_schema(batch))
    value = support.decode_slots(payload, batch)
    answer = support.SupportedResponse.model_validate(value).answers[0]
    assert answer.question == question['question']
    if risk in {'final_source', 'derived', 'forged_quote', 'unknown_field'}:
        with pytest.raises(ValueError): support.validate_support(answer, question, batch)
    else:
        support.validate_support(answer, question, batch)
        assert answer.evidence == (0,)
    if risk == 'whole_obligation':
        assert '无人物' in question['candidate']['text'] and '无人物' not in quote
        # A truthful partial citation is NOT proof of the compound obligation.
        # Program verification stays explicit about this residual model risk.
        independent_semantic_expected = 'CHALLENGE: quoted static image does not establish absence of people'
        assert independent_semantic_expected.startswith('CHALLENGE:')
    assert json.loads((folder / 'autonomous-round1-review-input.json').read_text()) == original


def test_advisory_query_policy_preserves_intake5_repair_and_cold_verify(prep_env, monkeypatch):
    from easel.integrations import planning_semantic_review as review
    monkeypatch.setattr(review, 'INTAKE_POLICY', review.ADMISSION_INTAKE_POLICY)
    test_vnext_confirmed_preset_truth_boundary(prep_env, monkeypatch, 'music_query_repair',
        admission_case='cold_replay')


@pytest.mark.parametrize('query_count', [0, 1, 2, 3])
def test_advisory_query_count_keeps_full_planning_and_cold_verify(prep_env, monkeypatch, query_count):
    queries = ['white paper desk', 'blank paper tabletop', 'two plain sheets'][:query_count]
    test_vnext_confirmed_preset_truth_boundary(prep_env, monkeypatch, 'music_query_repair',
        admission_case='clean', advisory_queries=queries)


@pytest.mark.parametrize('risk', ['match', 'music_query_repair', 'music_missing', 'music_optional', 'script_auto_pass', 'old_script_cache', 'conflict',
    'unresolved', 'unknown_handle', 'empty_script', 'missing_binding', 'duplicate_voice', 'capacity',
    'report_format', 'repair_changes_decision', 'fake_quote', 'missing_report', 'scope_drift', 'profile_drift',
    'material_match', 'material_preset', 'material_bundle_swap', 'material_forged_rights',
    'material_forged_record', 'material_bytes', 'material_cache',
    'conflict_missing_script', 'unresolved_extra_outer', 'match_outer_repair_changes',
    'material_fork', 'material_fork_report', 'material_fork_plan', 'material_fork_record',
    'material_fork_fingerprint', 'material_fork_creation', 'material_fork_cycle', 'material_fork_copy'])
def test_vnext_confirmed_preset_truth_boundary(prep_env, monkeypatch, risk, *, native_render=False, frozen_replay=False, admission_case=None, advisory_queries=None, truth_profile=False, script_override=None, ledger_revision=None, run_promotion=False):
    """Normal proposal/Owner/Handoff/A/B/Truth and persisted consumer contracts.

    Only model/config boundaries are fixed; all internal transitions are real.
    A successful trace stops at the existing Supply boundary, before purchase.
    """
    # The legacy Truth Owner no longer exists; all cases exercise the same
    # five pinned source-ref/Markdown@3 contracts and retain their failure
    # assertions (Truth/rights/Need/voice/Material).
    truth_profile = True
    import asyncio, hashlib, re
    from copy import deepcopy
    from dataclasses import replace
    from tests.test_creation_preparation import web, prep, creation, write_drafts, VIDEO_PROPOSAL
    from tests.planning_material_matrix.planning_eval import PlanningEvalBoundary
    from easel.runtime_config import EaselRuntimeConfig, MiniMaxRuntimeConfig
    from easel.integrations import voice_identity as voice
    from easel.integrations.material_generation import generation_budget_preview
    from easel.integrations import result_protocols
    # A source-ref test must exercise the complete immutable five-stage pin,
    # never the old partial opt-in that is now read-only.
    profiles = result_protocols.current()['profiles'] if truth_profile else {}
    if ledger_revision:
        profiles['script_ledger'] = ledger_revision
    if run_promotion:
        profiles['hypit_run_promotion'] = 'hypit-run-promotion@1'
    monkeypatch.setattr(result_protocols, 'DEFAULT_PROFILES', profiles)
    truth_prefix = '〔Easel Truth 来源引用审阅〕' if truth_profile else '〔Easel Truth 脚本与预置旁白身份独立审阅〕'
    from easel.integrations.material_layer import PlanningIntegration, MaterialIntegrationError
    from easel.integrations.planning_wire import project
    config = replace(EaselRuntimeConfig.load(), minimax=MiniMaxRuntimeConfig(api_key='fixture-key'))
    monkeypatch.setattr(EaselRuntimeConfig, 'load', lambda: config)
    music_case = risk in {'music_query_repair', 'music_missing', 'music_optional'}
    request = web.ChatRequest(message=('制作一个15秒桌面短片，选择已核实预置旁白，配轻柔无歌词授权背景音乐。'
                                      if music_case else '制作一个15秒桌面短片，选择已核实预置旁白，不添加音乐。'),
        capability='ai-film', creativeMode='clear_memo_video', persona='个人经营实践',
        sessionId='preset-' + risk, turnId='preset-proposal')
    message, work = web._prepare_chat_request(request)
    assert voice.HANDLE in message and voice.verified_profile()['label'] in message
    sound = '预置旁白：' + (voice.HANDLE if risk != 'unknown_handle' else 'unknown') + '\n使用已选择的预置身份逐字朗读；不添加音乐，不承诺未核实的听感。'
    if music_case:
        sound = sound.replace('不添加音乐', '配轻柔无歌词授权背景音乐')
    if risk.startswith('conflict'): sound += '\n只能使用另一预置身份，拒绝本版展示的身份。'
    if risk.startswith('unresolved'): sound += '\n必须是低沉女性音色，满足未核实的指定音域。'
    auto_pass = risk != 'match' and not (truth_profile and risk.startswith('material_fork'))
    script = script_override if script_override is not None else ('假设桌上有两张白纸。' if auto_pass else '先看问题，再做决定。')
    proposal = VIDEO_PROPOSAL.replace('无旁白，无音乐。', sound).replace(
        '音轨：静音', '音轨：旁白与音乐' if music_case else '音轨：纯旁白')
    if script_override is not None:
        proposal = proposal.replace('```text\n先看问题，再做决定。\n```', '```text\n' + script + '\n```')
    else:
        proposal = proposal.replace('先看问题，再做决定。', '' if risk == 'empty_script' else script)
    proposal = proposal.replace('桌面笔记', '两张白纸放在桌上')
    material_case = risk.startswith('material_')
    if material_case:
        proposal = proposal.replace('0–15 秒：两张白纸放在桌上，', '0–15 秒：后期排字；两张白纸背景为可选，')
    saved = creation.save_video_proposal(work['id'], 'preset-proposal', proposal)
    if risk in {'unknown_handle', 'empty_script'}:
        assert not saved['chat_workflow'].get('video_plan') and not saved.get('hypit_attempts')
        assert saved['chat_workflow']['output_decision']['outcome'] == 'REJECT'
        return
    plan = saved['chat_workflow']['video_plan']
    if script_override is not None:
        assert plan['script'] == script
    assert plan['schema'] == 'easel-video-proposal@3'
    assert plan['sound_source'] == sound and plan['sound'] == voice.render_sound(sound, voice.verified_profile())
    assert voice._PRESET not in json.dumps(plan)
    transcript = json.dumps([{'role': 'user', 'content': request.message},
                             {'role': 'assistant', 'content': proposal}], ensure_ascii=False)
    preview = generation_budget_preview()
    work = creation.confirm_chat_proposal(work['id'], 'preset-confirm', video_plan_sha256=plan['sha256'],
        production_specs=plan['specs'], delivery_proposal=transcript,
        proposal_sha256=hashlib.sha256(transcript.encode()).hexdigest(),
        generation_budget={'maxCostCny': 1, 'scopeSha256': preview['scope_sha256'], 'allowedModalities': ['voice']},
        input_use_statement_sha256=creation.input_use_preview()['statement_sha256'])
    assert voice.require_binding(work)['plan_sha256'] == plan['sha256']
    if risk == 'missing_binding':
        with creation.edit_creation(work['id']) as current: current['delivery'].pop('voice_binding')
    if frozen_replay:
        from tests.planning_material_matrix.planning_eval import replay_frozen_preparation
        inputs_root = prep_env['tmp'] / 'approved-preparation-inputs'
        inputs_root.mkdir()
        write_drafts(work, inputs_root)
        brief_path = inputs_root / 'production-brief.json'
        brief = json.loads(brief_path.read_text()); brief.update(plan['specs'])
        brief_path.write_text(json.dumps(brief, ensure_ascii=False))
        inputs = {p.name: {'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                  for p in inputs_root.glob('*.json')}
        replay = replay_frozen_preparation(work, inputs)
        assert replay['real_preparation_calls'] == 0 and replay['creation_id'] == work['id']
        assert not creation.get_creation(work['id']).get('hypit_attempts')
    admission_raw, pending_admission = {}, {}
    admission_write_failed = [False]
    if admission_case:
        from easel.integrations import semantic_boundary_run as semantic_boundary
        from easel.materials.store import AttemptMaterialStore
        if admission_case == 'legacy':
            native_identity = semantic_boundary.transport_identity
            def old_identity(catalog, **options):
                if options.get('intake_inputs') is not None and options.get('intake_policy') is None:
                    options['intake_policy'] = 'confirmed-planning-intake@4'
                return native_identity(catalog, **options)
            monkeypatch.setattr(semantic_boundary, 'transport_identity', old_identity)
        if admission_case == 'receipt_failure':
            native_write = AttemptMaterialStore.write_recovery_record
            def fail_receipt_once(self, key, value, *args, **kwargs):
                if key == semantic_boundary.STATE_KEY and value.get('admissions') and not admission_write_failed[0]:
                    assert 'A-details' not in value['calls']
                    admission_write_failed[0] = True
                    raise OSError('fixture admission receipt disk failure')
                return native_write(self, key, value, *args, **kwargs)
            monkeypatch.setattr(AttemptMaterialStore, 'write_recovery_record', fail_receipt_once)
    music_candidate = {'scope': 'global', 'role': '配乐', 'modality': 'bgm', 'necessity': 'required',
        'conditions': [{'text': '轻柔无歌词背景音乐。', 'strength': 'required', 'responsibility': 'material'}],
        'sound': {'vocals_allowed': False}}
    ledger_io_target, ledger_io_failures = [None], []
    if risk == 'old_script_cache_io':
        from easel.integrations import output_receipts
        original_read = Path.read_text
        original_owner = web._assess_source_ref_truth
        def fail_ledger_read(path, *args, **kwargs):
            if path == ledger_io_target[0] and not ledger_io_failures:
                ledger_io_failures.append('unreadable')
                raise OSError('fixture existing ledger read interrupted')
            return original_read(path, *args, **kwargs)
        def checked_owner(*args, **kwargs):
            try:
                return original_owner(*args, **kwargs)
            except output_receipts.OutputReceiptError:
                ledger_io_failures.append('local_receipt_error')
                raise
        monkeypatch.setattr(Path, 'read_text', fail_ledger_read)
        monkeypatch.setattr(web, '_assess_source_ref_truth', checked_owner)
    calls = []
    def external(message, timeout=None, session=None, **options):
        if session in pending_admission:
            previous_message, previous_options, response = pending_admission[session]
            assert (message, options) == (previous_message, previous_options)
            return response
        calls.append(message)
        if message.startswith('〔Easel Semantic Planning vNext A-'):
            payload = json.loads(message.splitlines()[-1])
            if 'input_view' in payload:
                view = payload['input_view']
                assert view['inputs']['proposal']['voice_profile'] == voice.verified_profile()
                if music_case:
                    # Program resolves textual pointers; the model sees the
                    # exact frozen audio intent, not a byte range to interpret.
                    assert view['inputs']['proposal']['sound'] == plan['sound']
                    assert view['inputs']['proposal']['sound_source'] == plan['sound_source']
                    assert payload['scope_reference_contract']['global_scope'] == view['inputs']['confirmed']['SCENES.md']['whole_document']
                    assert payload['scope_reference_contract']['usage_scope_is_evidence'] is False
                    assert payload['program_owned_voice']['may_resubmit_as_other_modality'] is False
                assert view['catalog']['derived_voice']['profile'] == {
                    'program_reference': {'json_path': ['inputs', 'proposal', 'voice_profile']}}
            else:
                assert payload['catalog']['derived_voice']['profile'] == voice.verified_profile()
            value = vnext_proposal()
            if material_case: value['needs'][0]['necessity'] = 'optional'
            if risk in {'old_script_cache', 'old_script_cache_io'}:
                from easel.integrations.script_truth import create_script_claim_ledger
                attempt = creation.get_creation(work['id'])['hypit_attempts'][-1]
                root = Path(attempt['workspace']['path'])
                ledger = create_script_claim_ledger(script, root / 'handoff/truth-packet.json')
                assert ledger['status'] == 'PASSED'
                (root / 'planning/script-claims.json').write_text(json.dumps(ledger))
                if risk == 'old_script_cache_io':
                    ledger_io_target[0] = root / 'planning/script-claims.json'
            if music_case:
                if risk == 'music_optional':
                    value['needs'].append({**deepcopy(music_candidate), 'necessity': 'optional'})
                if admission_case:
                    value['needs'].append(deepcopy(music_candidate))
                selection, details, _ = staged_fixture_parts(message, value)
                if advisory_queries is not None:
                    # The fake Provider supplies this response; product code must
                    # accept it without filling or deleting search phrases.
                    details['slots']['slot_000']['queries'] = list(advisory_queries)
                if risk == 'music_query_repair' and admission_case != 'clean':
                    details['slots']['slot_000']['queries'] = ['白纸 桌面', 'white paper desk']
                is_selection = 'A-selection〕' in message
                if admission_case and is_selection:
                    selection['needs'][-1]['contains'] = {'modality': 'bgm', 'necessity': 'required'}
                    if admission_case == 'reject':
                        selection['needs'][-1]['contains']['restriction'] = '不得商业使用'
                raw = json.dumps(selection if is_selection else details, ensure_ascii=False)
                if admission_case:
                    admission_raw['A-selection' if is_selection else 'A-details'] = raw
                    if admission_case == 'pending' and not is_selection:
                        from easel.creation_delivery import DeliveryExecutionUncertain
                        pending_admission[session] = (message, options, raw)
                        raise DeliveryExecutionUncertain('fixture original details is still pending')
                return raw
            # External transport encoding only, no application-side repair.
            return staged_fixture_wire(message, value, invalid=risk if risk in {'duplicate_voice', 'capacity'} else None)
        if '有界视觉复核' in message:
            batch = json.loads(message.splitlines()[-1])
            answers = supported_fixture_answers(batch, [{'question': q['question'], 'decision': 'ACCEPT',
                'evidence': [0], 'reason': '独立固定对照：两纸源条件及已确认场景。'} for q in batch['questions']])
            return json.dumps(fixture_review_wire(batch, answers), ensure_ascii=False)
        if message.startswith(truth_prefix):
            attempt = creation.get_creation(work['id'])['hypit_attempts'][-1]
            root = Path(attempt['workspace']['path'])
            from easel.integrations.script_truth import create_script_claim_ledger
            from easel.materials.domain import MaterialPlan
            material_plan = MaterialPlan.model_validate_json((root / 'planning/MATERIAL_PLAN.json').read_text())
            context = voice.review_context(creation.get_creation(work['id']), material_plan, script,
                create_script_claim_ledger(script, root / 'handoff/truth-packet.json',
                    revision=result_protocols.selected(attempt, 'script_ledger') or 'easel-script-claim-ledger@2'))
            report = json.loads(message.split('写后停止：\n' if truth_profile else '，不增加字段：', 1)[1].split('\n前份报告', 1)[0])
            if report['script'] is not None:
                decisions = report['script']['decisions']
                for row in (decisions.values() if truth_profile else decisions):
                    row.update(kind='creative_expression', reason='独立对照：不含事实主张的创作建议。')
            report['voice'] = {'decision': 'CONFLICT' if risk.startswith('conflict') else 'UNRESOLVED' if risk.startswith('unresolved') else 'MATCH',
                'reason': '独立固定语义对照：完整声音要求及实际身份和执行控制相容。',
                'sources': [{'ref': ref, 'quote': source} for ref, source in context['sources'].items()]}
            truth_count = sum(m.startswith(truth_prefix) for m in calls)
            if risk == 'report_format' and truth_count == 1: report.pop('voice')
            if risk == 'repair_changes_decision':
                if truth_count == 1: report['script'] = {}
                else: report['voice']['decision'] = 'CONFLICT'
            if risk == 'conflict_missing_script': report.pop('script')
            if risk == 'unresolved_extra_outer': report['extra'] = 'invalid outer metadata'
            if risk == 'match_outer_repair_changes':
                if truth_count == 1: report['extra'] = 'invalid outer metadata'
                else: report['voice']['decision'] = 'CONFLICT'
            if risk == 'fake_quote': report['voice']['sources'][0]['quote'] = '不是冻结原文的承诺'
            target = Path(re.search(r'只写 (.+\.json)，按以下固定结构' if truth_profile else r'只写(.+\.json)，不增加字段：', message)[1])
            target.write_text(json.dumps(report, ensure_ascii=False))
            return 'fixed external Truth report'
        if '单次局部修复' in message:
            if music_case:
                import jsonschema
                payload = json.loads(message.splitlines()[-1])
                result = {}
                for i, target in enumerate(payload['targets']):
                    if target['kind'] == 'confirmed_music_coverage':
                        value = deepcopy(music_candidate)
                    elif target['path'][-1] == 'queries':
                        value = ['white paper desk', 'blank paper tabletop', 'two plain sheets']
                    else:
                        assert target['path'][-1] == 'necessity'
                        value = 'required'
                    result[f'target-{i:04}'] = value
                jsonschema.validate(result, payload['schema'])
                return json.dumps(result, ensure_ascii=False)
            return json.dumps({'patches': []})
        assert not frozen_replay, 'Frozen Preparation replay must never call the Preparation model'
        current = creation.get_creation(work['id'])
        paths = prep.preparation_paths(work['id'], current['preparation']['operation_key'])
        write_drafts(current, paths['draft'])
        brief_path = paths['draft'] / 'production-brief.json'
        brief = json.loads(brief_path.read_text())
        brief.update(current['delivery']['video_plan']['specs'])
        brief_path.write_text(json.dumps(brief, ensure_ascii=False))
        return 'fixed external Preparation'
    monkeypatch.setattr(web, 'run_agent_sync', external)
    monkeypatch.setattr(web, '_hypit_runtime_profile', lambda: None)
    boundary = PlanningEvalBoundary()
    outcome = asyncio.run(boundary.advance(work['id'], web))
    if risk == 'old_script_cache_io':
        assert not outcome['boundary_reached']
        assert ledger_io_failures == ['unreadable', 'local_receipt_error']
        assert not any(m.startswith(truth_prefix) for m in calls)
        interrupted = creation.get_creation(work['id'])['hypit_attempts'][-1]
        evidence = Path(interrupted['workspace']['path']) / 'materials/recoveries'
        assert not list(evidence.glob('truth-source-request-*.json'))
        assert not list(evidence.glob('truth-source-slot-*.json'))
        outcome = asyncio.run(boundary.advance(work['id'], web))
    if admission_case == 'receipt_failure':
        assert not outcome['boundary_reached']
        interrupted = creation.get_creation(work['id'])['hypit_attempts'][-1]
        interrupted_root = Path(interrupted['workspace']['path'])
        journal = AttemptMaterialStore(interrupted_root).read_recovery_record(semantic_boundary.STATE_KEY)
        assert journal['calls']['A-selection']['result'] == 'MODEL_COMPLETED'
        assert journal['calls']['A-selection']['reply'] == admission_raw['A-selection']
        assert not journal['repair_used'] and not (interrupted_root / 'planning/MATERIAL_PLAN.json').exists()
        assert 'admissions' not in journal and 'A-details' not in journal['calls']
        # Resume the same native Owner checkpoint, not a new Creation/Attempt or
        # a regenerated reply. A normal advance deliberately stops at a checkpoint.
        outcome = asyncio.run(boundary.advance(work['id'], web))
    if admission_case in {'reject', 'legacy'}:
        assert not outcome['boundary_reached'] and boundary.supply_calls == 0
        current = creation.get_creation(work['id'])
        failed_attempt = current['hypit_attempts'][-1]
        failed_root = Path(failed_attempt['workspace']['path'])
        journal = AttemptMaterialStore(failed_root).read_recovery_record(semantic_boundary.STATE_KEY)
        assert set(journal['calls']) == {'A-selection'} and not journal['repair_used']
        assert journal['calls']['A-selection']['reply'] == admission_raw['A-selection']
        assert not (failed_root / 'planning/MATERIAL_PLAN.json').exists()
        if admission_case == 'reject':
            assert journal['admissions']['A-selection']['receipt']['decision']['outcome'] == 'REJECT'
        else:
            assert 'admissions' not in journal
        return
    successful = music_case or material_case or risk in {'match', 'script_auto_pass', 'old_script_cache', 'old_script_cache_io', 'report_format', 'missing_report', 'scope_drift', 'profile_drift'}
    assert outcome['boundary_reached'] == successful, (outcome,
        creation.get_creation(work['id']).get('preparation', {}).get('last_error'))
    assert boundary.supply_calls == 0 and not boundary.state_violations
    if frozen_replay:
        assert all(hashlib.sha256(Path(row['path']).read_bytes()).hexdigest() == row['sha256'] for row in inputs.values())
        assert not any('CONFIRMED_PROPOSAL_TRANSCRIPT=' in message for message in calls)
    current = creation.get_creation(work['id'])
    attempt = current['hypit_attempts'][-1]
    truth_calls = sum(m.startswith(truth_prefix) for m in calls)
    if risk in {'missing_binding', 'duplicate_voice', 'capacity'}:
        assert truth_calls == 0
    else:
        assert truth_calls == (2 if risk in {'report_format', 'repair_changes_decision', 'fake_quote', 'match_outer_repair_changes'} else 1)
    if successful:
        loaded = PlanningIntegration().load(attempt)
        assert len(loaded['plan'].needs) == (3 if music_case else 2) and loaded['plan'].needs[-1].modality_spec.kind == 'voice'
        assert loaded['plan'].needs[-1].importance.value == 'required'
        assert loaded['plan'].needs[-1].modality_spec.text_sha256 == hashlib.sha256(script.encode()).hexdigest()
        root = Path(attempt['workspace']['path'])
        if music_case:
            from easel.integrations import semantic_boundary_run as semantic_boundary
            from easel.integrations import planning_semantic_review as review
            checkpoint = json.loads((root / 'planning/SEMANTIC_CHECKPOINT.json').read_text())
            assert checkpoint['scope']['transport']['intake_policy'] == review.INTAKE_POLICY
            if advisory_queries is not None:
                from easel.materials.application.query_hints import query_hints, QUERY_FIELDS
                from easel.materials.application.compiler import NeedCompiler
                from easel.integrations.planning_result_contract import semantic_tool_schema
                from jsonschema import Draft202012Validator
                visual = loaded['plan'].needs[0]
                assert checkpoint['scope']['transport']['intake_policy'] == 'confirmed-planning-intake@6'
                assert loaded['plan'].policy['visual_requirements'] == 'visual-requirements@2'
                assert list(query_hints(visual.constraints)) == advisory_queries
                assert checkpoint['initial']['needs'][0]['queries'] == advisory_queries
                assert list(json.loads((root / 'planning/MATERIAL_REQUIREMENTS.json').read_text()).values())[0]['queries'] == advisory_queries
                retrieval = NeedCompiler.for_plan(loaded['plan']).compile(visual)
                assert not (set(retrieval.filters) & QUERY_FIELDS)
                assert visual.intent.description == '两张白纸放在桌上。' and visual.importance.value == 'required'
                legacy = semantic_tool_schema(checkpoint['scope']['catalog'], compiled=True)
                assert Draft202012Validator(legacy).is_valid(checkpoint['initial']) == (len(advisory_queries) in {0, 3})
            if admission_case == 'clean':
                assert checkpoint['repair'] is None
                assert sum('单次局部修复' in m for m in calls) == 0
            else:
                assert checkpoint['repair']['stage'] == 'semantic'  # Same one shared allowance, normalization does not spend it.
                assert sum('单次局部修复' in m for m in calls) == 1
            bgm = [n for n in loaded['plan'].needs if n.modality_spec.kind == 'bgm']
            assert len(bgm) == 1 and bgm[0].importance.value == 'required'
            assert bgm[0].modality_spec.vocals_allowed is False
            if risk == 'music_query_repair' and admission_case != 'clean':
                assert checkpoint['initial']['needs'][0]['queries'] == ['白纸 桌面', 'white paper desk']
                assert len(checkpoint['repair']['targets']) == (1 if admission_case else 2)
            before = len(calls)
            assert PlanningIntegration().load(attempt)['plan'] == loaded['plan']
            assert len(calls) == before
            if admission_case:
                from easel import output_admission as admission
                normalized_path = root / 'planning/SEMANTIC_A_SELECTION_NORMALIZED.json'
                record = checkpoint['admissions']['A-selection']
                assert record['receipt']['decision']['outcome'] == 'NORMALIZE'
                assert record['receipt']['raw_errors']['total'] == 1
                assert record['receipt']['remaining_errors']['total'] == 0
                assert len(record['receipt']['actions']) == 1
                assert checkpoint['wire_originals']['A-selection'] == admission_raw['A-selection']
                assert (root / 'planning/SEMANTIC_A_SELECTION.json').read_text() == admission_raw['A-selection']
                candidate = json.loads(admission_raw['A-selection'])
                del candidate['needs'][-1]['contains']
                assert record['candidate'] == candidate == json.loads(normalized_path.read_text())
                assert checkpoint['detail_binding']['normalized_wire_sha256'] == admission.digest(candidate)
                assert sum('A-selection〕' in m for m in calls) == 1
                assert sum('A-details〕' in m for m in calls) == 1
                if admission_case == 'receipt_failure': assert admission_write_failed[0]
                if admission_case == 'pending': assert len(pending_admission) == 1
                if admission_case == 'cold_replay' or advisory_queries is not None:
                    import subprocess, sys
                    cold = root / 'cold-admission.json'
                    cold.write_text(json.dumps({'root': str(root), 'attempt': attempt,
                        'plan': loaded['plan'].model_dump(mode='json'), 'scope': checkpoint['scope'],
                        'outputs': str(prep_env['outputs']), 'tmp': str(prep_env['tmp'])}))
                    child = '''import json,sys,socket
from pathlib import Path
from dataclasses import replace
from easel import creation
from easel.runtime_config import EaselRuntimeConfig, MiniMaxRuntimeConfig
from easel.integrations import semantic_boundary_run as b
from easel.materials.domain import MaterialPlan
x=json.loads(Path(sys.argv[1]).read_text())
creation.OUTPUTS_DIR=Path(x['outputs']); creation.CREATIONS_DIR=creation.OUTPUTS_DIR/'_creations'
config=replace(EaselRuntimeConfig.load(environ={'EASEL_MATERIAL_LIBRARY_ROOT':str(Path(x['tmp'])/'library')},env_file=Path(x['tmp'])/'absent.env'),minimax=MiniMaxRuntimeConfig(api_key='fixture-key'))
EaselRuntimeConfig.load=classmethod(lambda cls:config)
def forbidden(*a,**k): raise AssertionError('Cold admission must not dispatch')
socket.socket.connect=forbidden
scope=x['scope']
b.verify(x['root'],MaterialPlan.model_validate_json(json.dumps(x['plan'])),scope['mode'],scope['canonical']['SCRIPT.md'],canonical=scope['canonical'],attempt=x['attempt'])
print('COLD_ADMISSION_PASS')
'''
                    process = subprocess.run([sys.executable, '-c', child, str(cold)],
                        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=60)
                    assert process.returncode == 0, process.stderr
                    assert 'COLD_ADMISSION_PASS' in process.stdout
                if admission_case == 'tamper':
                    for fault in ('action', 'candidate', 'rule', 'missing', 'detail_binding', 'policy'):
                        bad = deepcopy(checkpoint)
                        if fault == 'action': bad['admissions']['A-selection']['receipt']['actions'][0]['path'] = ['needs', 0]
                        elif fault == 'candidate': bad['admissions']['A-selection']['candidate']['needs'][0]['necessity'] = 'optional'
                        elif fault == 'rule': bad['admissions']['A-selection']['receipt']['policy']['rules_sha256'] = '0' * 64
                        elif fault == 'missing': bad.pop('admissions')
                        elif fault == 'detail_binding': bad['detail_binding']['normalized_wire_sha256'] = '0' * 64
                        else:
                            bad['scope']['transport']['intake_policy'] = 'confirmed-planning-intake@4'
                            bad['scope']['transport'].pop('output_admission')
                        (root / 'planning/SEMANTIC_CHECKPOINT.json').write_text(json.dumps(bad, ensure_ascii=False))
                        with pytest.raises(ValueError):
                            semantic_boundary.verify(root, loaded['plan'], checkpoint['scope']['mode'], script,
                                canonical=checkpoint['scope']['canonical'], attempt=attempt)
                    (root / 'planning/SEMANTIC_CHECKPOINT.json').write_text(json.dumps(checkpoint, ensure_ascii=False))
                    normalized_bytes = normalized_path.read_bytes()
                    normalized_path.write_text('{}')
                    with pytest.raises(ValueError):
                        semantic_boundary.verify(root, loaded['plan'], checkpoint['scope']['mode'], script,
                            canonical=checkpoint['scope']['canonical'], attempt=attempt)
                    normalized_path.write_bytes(normalized_bytes)
            bad = deepcopy(checkpoint)
            bad['scope']['transport'].pop('intake_policy')
            (root / 'planning/SEMANTIC_CHECKPOINT.json').write_text(json.dumps(bad, ensure_ascii=False))
            with pytest.raises(ValueError):
                semantic_boundary.verify(root, loaded['plan'], checkpoint['scope']['mode'], script,
                    canonical=checkpoint['scope']['canonical'], attempt=attempt)
            (root / 'planning/SEMANTIC_CHECKPOINT.json').write_text(json.dumps(checkpoint, ensure_ascii=False))
            return
        if risk == 'missing_report': (root / 'planning/voice-identity-review.json').unlink()
        if risk in {'scope_drift', 'profile_drift'}:
            with creation.edit_creation(work['id']) as value:
                if risk == 'scope_drift': value['delivery']['authorization']['material_generation']['scope']['speech_voice_id'] = 'another'
                else: value['delivery']['video_plan']['voice_profile']['label'] = 'modified'
        if risk in {'missing_report', 'scope_drift', 'profile_drift'}:
            with pytest.raises(MaterialIntegrationError): PlanningIntegration().load(attempt)
        if material_case:
            # Continue through actual Supply, generation receipt, independent
            # observation, Rights, Match and Gate using external fixed fixtures.
            import subprocess
            from easel.integrations.material_layer import MaterialProductOrchestrator, MaterialGateIntegration
            from easel.integrations import material_generation
            from easel.materials.application import voice_delivery
            from easel.materials.providers import minimax_pricing
            from easel.materials.providers.minimax_speech import MiniMaxSpeechResult
            from easel.materials.store import AttemptMaterialStore
            from easel.creation_delivery import active_delivery
            from easel.integrations.hypit import service
            from tests.test_minimax_image_speech_generation import MINIMAX_TERMS_FIXTURE
            mp3 = root / 'fixture-voice.mp3'
            subprocess.run(['ffmpeg', '-nostdin', '-loglevel', 'error', '-f', 'lavfi', '-i',
                'sine=frequency=350:sample_rate=16000:duration=5', str(mp3)], check=True, capture_output=True)
            speech_calls, asr_calls = [], []
            class Speech:
                model = config.minimax.speech_model
                voice_id = config.minimax.speech_voice_id
                def __init__(self, *args, **kwargs): assert kwargs['voice_id'] == self.voice_id
                def generate(self, text, **controls):
                    speech_calls.append((text, controls))
                    return MiniMaxSpeechResult(self.model, self.voice_id, mp3.read_bytes(), 'mp3', (), 'fixture-no-provider-timing')
            monkeypatch.setattr('easel.materials.providers.minimax_speech.MiniMaxSpeechAdapter', Speech)
            monkeypatch.setattr('easel.materials.providers.MiniMaxSpeechAdapter', Speech)
            def public_document(url):
                if url == minimax_pricing.TERMS_URL: return MINIMAX_TERMS_FIXTURE
                if url == minimax_pricing.VOICE_URL: return '| 中文 | `male-qn-qingse` | 青涩青年音色 |'
                return '## 语音\n单价：元/万字符。1 个汉字算 2 个字符\n| 同步语音合成 | speech-2.8-hd | 3.5 |\n'
            monkeypatch.setattr(minimax_pricing, 'read_public_contract', public_document)
            monkeypatch.setattr(material_generation, 'MINIMAX_INTERNAL_TERMS_SHA256',
                minimax_pricing.usage_terms_evidence(public_document)['sha256'])
            monkeypatch.setattr(voice_delivery, 'require_local_voice_model', lambda *_: None)
            monkeypatch.setattr(voice_delivery, 'voice_verification_identity', lambda *_: {'model_sha256': 'fixture-asr'})
            def recognize(path, *_):
                asr_calls.append(path)
                return {'engine': 'fixture-asr', 'words': [{'text': script, 'start_seconds': .1,
                    'end_seconds': 4.8, 'probability': .99}]}
            monkeypatch.setattr(voice_delivery, 'read_local_voice', recognize)
            orchestrator = MaterialProductOrchestrator()
            if native_render:
                from easel.creation_delivery import advance_creation
                for _ in range(12):
                    asyncio.run(advance_creation(work['id'], web._execute_creation_delivery))
                    current_work = creation.get_creation(work['id'])
                    refreshed = service.get_film_attempt(attempt['attempt_id'])
                    assert current_work['delivery']['status'] != 'failed', current_work['delivery']
                    if refreshed.get('material_gate', {}).get('status') == 'MATERIAL_READY': break
                else: pytest.fail('Real Owner did not progress Supply/voice observation to Gate')
            else:
                initial_supply = orchestrator._run(attempt, (), planning=loaded)
                assert initial_supply['status'] == 'MATERIAL_NOT_READY'
                refreshed = service.get_film_attempt(attempt['attempt_id'])
                current_work = creation.get_creation(work['id'])
                assert material_generation.pending_generated_need(current_work, refreshed, loaded['plan']) is not None, (
                    refreshed.get('material_gate'), [n.model_dump(mode='json') for n in loaded['plan'].needs])
                token = active_delivery.set(work['id'])
                try:
                    material_generation.generate_for_commission(attempt['attempt_id'])
                    orchestrator.recover_voice_timing(attempt['attempt_id'])
                    orchestrator.observe_visual_materials(attempt['attempt_id'],
                        executor=lambda *_: pytest.fail('optional unsupplied image has no observation'))
                finally:
                    active_delivery.reset(token)
            assert (len(speech_calls), len(asr_calls)) == (1, 1), [
                (r.get('status'), r.get('voice_timing')) for r in AttemptMaterialStore(root).list_generation_records()]
            attempt = service.get_film_attempt(attempt['attempt_id'])
            gate = MaterialGateIntegration()
            ready_plan, bundle, _ = gate.assert_ready(attempt)
            assert attempt['material_gate']['voice_identity_evidence']['approved']
            assert ready_plan == loaded['plan']
            store = AttemptMaterialStore(root)
            record = store.list_generation_records()[0]
            asset = store.read_asset(record['asset_id'])
            if native_render:
                assert risk == 'material_match'
                from tests.test_creator_content_replay import replay_vnext_native_hypit
                replay_vnext_native_hypit(work, attempt, asset, monkeypatch, prep_env['tmp'])
                assert truth_calls == len(asr_calls) == len(speech_calls) == 1
                return
            if risk.startswith('material_fork'):
                original_receipts = deepcopy(creation.get_creation(work['id'])['delivery']['material_generations'])
                from easel.integrations.material_layer import ProductionAuthoringIntegration
                from tests.test_hypit_integration import measured_narration_fixture, FakeHypit
                class Renderer(FakeHypit):
                    def check(self, workspace, run_source):
                        from easel.integrations.hypit.native_source import parse_file, parse_run
                        from easel.integrations.hypit import authoring_publication as native
                        parse_file(workspace / native.AUTHOR, workspace=workspace)
                        _, parsed, _ = parse_run(run_source, workspace=workspace)
                        assert parsed['targets'] == [{'output': 'final.video'}]
                        return {'format': 'hypit.cli-check@1', 'ok': True,
                                'sourceKind': 'run', 'run': native.RUN, 'author': native.AUTHOR,
                                'frontend': '@hypit/run-markup@1', 'targetCount': 1,
                                'targets': ['final.video'], 'candidates': 0,
                                'satisfactions': 0, 'historicalOutputCount': 0}
                    def pricing(self, *_args, **_kwargs):
                        return {'format': 'hypit.cli-pricing@1', 'requestCount': 1,
                                'noChargeRequestCount': 1, 'groups': []}
                    def build(self, *_args, **_kwargs):
                        self.build_count += 1
                        return {'format': 'hypit.cli-build@1', 'build': {
                            'id': 'bld_identity_' + str(self.build_count), 'work': {'outcome': 'failed'}}}
                    def status(self, _workspace, build_id, **_kwargs):
                        return {'format': 'hypit.cli-status@1', 'build': {'id': build_id, 'work': {'outcome': 'failed'}}}
                renderer = Renderer()
                monkeypatch.setattr(service, '_cli', lambda cli=None: renderer if cli is renderer else pytest.fail('unmocked renderer'))
                production = ProductionAuthoringIntegration()
                prepared = production.prepare(attempt, selected_asset_ids=[asset.asset_id])['attempt']
                source, _, _ = measured_narration_fixture()
                source = source.replace('end="4s"', 'end="15s"')
                source = re.sub(r'<media:Audio id="music-source".*?</audio:Track>', '', source, flags=re.DOTALL)
                source = source.replace('<film:Track source={music-track.audio}/>', '')
                source = source.replace('./voice.wav', store.hypit_source_path(asset, 'productions/easel-authoring/authors/main.svml'))
                author = root / 'productions/easel-authoring/authors/main.svml'
                author.parent.mkdir(parents=True, exist_ok=True)
                # Native parser resolves imported recipes before code-owned
                # narration derivation; the removed regex writer never did.
                author.with_name('recipes.svs').write_text('<?svml using="@hypit/svs@1"?>\n<sheet version="1">\n'
                    'film.memo { background: #101820; }\ntext.caption { stack-order: 20; size: 48; fill: #FFFFFF; }\n</sheet>\n')
                source = production.compile_narration(prepared, source)
                author.write_text(source)
                run = root / 'productions/easel-authoring/runs/main.svrun'
                run.parent.mkdir(parents=True, exist_ok=True)
                ready = gate.assert_ready(prepared)[2]
                run.write_text(json.dumps({'schema': 'easel-authoring-svrun@1', 'creation_id': work['id'],
                    'attempt_id': attempt['attempt_id'], 'plan_id': ready_plan.plan_id, 'plan_revision': ready.plan_revision,
                    'bundle_id': bundle.bundle_id, 'bundle_revision': ready.bundle_revision,
                    'readiness_revision': ready.bundle_revision, 'authoring_source': '../authors/main.svml',
                    'material_selection': '../material-selection.json', 'status': 'AUTHORING_READY',
                    'publication_allowed': False, 'build': {'enabled': False, 'reason': 'stops_before_hypit_build'}}))
                service.begin_film_authoring(attempt['attempt_id'])
                service.complete_film_authoring(attempt['attempt_id'], cli=renderer)
                runtime = prep_env['tmp'] / 'fixture-free-runtime.json'
                runtime.write_text(json.dumps({'format': 'hypit.runtime-local@1', 'dataRoot': '.fixture-runtime'}))
                service.resolve_film_attempt_runtime(attempt['attempt_id'], str(runtime))
                def fail_build(item):
                    service.validate_film_attempt(item['attempt_id'], 'productions/easel-authoring/runs/main.svrun', cli=renderer)
                    service.estimate_film_attempt(item['attempt_id'], cli=renderer)
                    service.approve_film_cost(item['attempt_id'], 0, use_commission=True)
                    failed = service.submit_film_build(item['attempt_id'], title='offline fixture', cli=renderer)
                    assert failed['execution_status'] == 'BUILD_FAILED'
                    return failed
                failed = fail_build(attempt)
                copies = service._copy_retry_checkpoint_file
                interrupted = []
                def interrupted_copy(old_root, new_root, relative):
                    copies(old_root, new_root, relative)
                    if risk == 'material_fork_copy' and relative.parts[:2] == ('materials', 'assets') and not interrupted:
                        interrupted.append(str(new_root))
                        raise OSError('fixture checkpoint copy interrupted')
                monkeypatch.setattr(service, '_copy_retry_checkpoint_file', interrupted_copy)
                if risk == 'material_fork_copy':
                    with pytest.raises(OSError, match='copy interrupted'):
                        service.retry_failed_film_build(failed['attempt_id'], cli=renderer)
                inherited = service.retry_failed_film_build(failed['attempt_id'], cli=renderer)
                assert inherited['retry_source']['status'] == 'READY'
                inherited_store = AttemptMaterialStore(inherited['workspace']['path'])
                assert inherited_store.list_generation_records() == (record,)
                gate.assert_ready(inherited)
                if risk in {'material_fork', 'material_fork_copy'}:
                    second_failed = fail_build(inherited)
                    twice = service.retry_failed_film_build(second_failed['attempt_id'], cli=renderer)
                    gate.assert_ready(twice)
                    assert AttemptMaterialStore(twice['workspace']['path']).list_generation_records() == (record,)
                    assert truth_calls == len(asr_calls) == len(speech_calls) == 1
                    assert creation.get_creation(work['id'])['delivery']['material_generations'] == original_receipts
                    if truth_profile:
                        original_truth = PlanningIntegration().load(attempt)['manifest']['truth_result']
                        assert original_truth is not None
                        for child in (inherited, twice):
                            loaded_child = PlanningIntegration().load(child)
                            assert child['result_protocols'] == attempt['result_protocols']
                            assert loaded_child['manifest']['truth_result'] == original_truth
                            if ledger_revision:
                                original_ledger = PlanningIntegration().load(attempt)['truth_ledger']
                                child_ledger = loaded_child['truth_ledger']
                                assert child_ledger['schema'] == ledger_revision
                                assert child_ledger['parser_identity'] == original_ledger['parser_identity']
                                assert child_ledger['coverage'] == original_ledger['coverage']
                                assert child_ledger == original_ledger
                                assert Path(child['workspace']['path']).joinpath('planning/SCRIPT.md').read_bytes() == script.encode('utf-8')
                        assert sum(m.startswith(truth_prefix) for m in calls) == 1
                    return
                if risk == 'material_fork_report':
                    report_path = root / 'planning/voice-identity-review.json'
                    altered = json.loads(report_path.read_text()); altered['result']['reason'] += ' changed'
                    report_path.write_text(json.dumps(altered))
                elif risk == 'material_fork_plan':
                    store.write_plan(ready_plan.model_copy(update={'needs': tuple(reversed(ready_plan.needs))}))
                elif risk == 'material_fork_record':
                    changed = {**record, 'voice_id': 'different-preset'}
                    inherited_store.write_generation_record(record['generation_id'], changed)
                else:
                    edge = inherited['retry_source'].copy()
                    if risk == 'material_fork_fingerprint': edge['fingerprint'] = 'sha256:' + '0' * 64
                    if risk == 'material_fork_cycle': edge['attempt_id'] = inherited['attempt_id']
                    if risk == 'material_fork_creation':
                        from tests.test_hypit_integration import create_test_handoff
                        other = creation.create_creation('另一隔离作品', creative_mode='clear_memo_video')
                        other_handoff = create_test_handoff(other)
                        edge['attempt_id'] = service.create_film_attempt(other['id'], other_handoff['handoff_id'],
                            runtime_profile=str(runtime))['attempt_id']
                    inherited = service.update_film_attempt(inherited['attempt_id'], event='fixture_origin_tamper', retry_source=edge)
                if risk in {'material_fork_report', 'material_fork_plan'}:
                    # A changed parent Report/Plan invalidates the published
                    # native Authoring domain, not a model-repairable reply.
                    from easel.integrations.hypit.authoring_publication import AuthoringPublicationError
                    with pytest.raises(AuthoringPublicationError,
                                       match='Frozen Authoring domain evidence cannot be verified') as rejected:
                        gate.assert_ready(inherited)
                    assert isinstance(rejected.value.__cause__, MaterialIntegrationError)
                elif risk in {'material_fork_creation', 'material_fork_cycle'}:
                    # Truth source-ref ownership checks fail before Gate when
                    # the retry lineage crosses a Creation or loops back.
                    from easel.integrations.output_receipts import OutputReceiptError
                    expected = ('Truth checkpoint lineage crosses frozen Creation inputs'
                                if risk == 'material_fork_creation'
                                else 'Truth checkpoint lineage is cyclic or exceeds its bound')
                    with pytest.raises(OutputReceiptError, match=expected):
                        gate.assert_ready(inherited)
                else:
                    with pytest.raises((ValueError, MaterialIntegrationError)):
                        gate.assert_ready(inherited)
                assert truth_calls == len(asr_calls) == len(speech_calls) == 1
                return
            if risk == 'material_match':
                assert gate.assert_ready(attempt)[1] == bundle
                assert len(speech_calls) == len(asr_calls) == 1
                return
            if risk in {'material_preset', 'material_cache'}:
                record['voice_id'] = 'same-script-different-preset'
                store.write_generation_record(record['generation_id'], record)
            if risk == 'material_forged_record':
                record['need_sha256'] = '0' * 64
                store.write_generation_record(record['generation_id'], record)
            if risk == 'material_bytes': store.resolve_asset_locator(asset.file.path).write_bytes(b'changed audio')
            if risk == 'material_forged_rights':
                altered = asset.model_copy(update={'rights': asset.rights.model_copy(update={
                    'evidence': tuple(e for e in asset.rights.evidence if e.kind != 'asset_commission_use')})})
                store.write_asset(altered)
                bundle = bundle.model_copy(update={'assets': tuple(altered if a.asset_id == asset.asset_id else a for a in bundle.assets)})
            if risk == 'material_bundle_swap':
                # Keep the correct candidate, approve a different same-text one.
                swapped_id = 'different-same-text-asset'
                swapped_path = store.write_asset_bytes(swapped_id, 'original.mp3', store.resolve_asset_locator(asset.file.path).read_bytes())
                altered = asset.model_copy(update={'asset_id': swapped_id,
                    'file': asset.file.model_copy(update={'path': swapped_path})})
                store.write_asset(altered)
                bundle = bundle.model_copy(update={'assets': (*bundle.assets, altered),
                    'matches': tuple(m.model_copy(update={'asset_id': altered.asset_id}) if m.asset_id == asset.asset_id else m
                                     for m in bundle.matches)})
            if risk in {'material_forged_rights', 'material_bundle_swap'}:
                from easel.materials.application.assembly import MaterialBundleAssembler
                from easel.materials.application.readiness import MaterialReadinessCalculator
                bundle = bundle.model_copy(update={'revision': MaterialBundleAssembler.revision(bundle)})
                store.write_bundle(bundle)
                readiness, gaps = MaterialReadinessCalculator(store=store).calculate(ready_plan, bundle)
                assert readiness.status.value == 'READY'
                with pytest.raises(MaterialIntegrationError, match='旁白|Rights|生成记录'):
                    gate.record(attempt, ready_plan, bundle, store.read_supply_run(bundle.supply_run_id), readiness, gaps)
            with pytest.raises(MaterialIntegrationError): gate.assert_ready(attempt)
            assert len(speech_calls) == len(asr_calls) == 1
    else:
        assert not Path(attempt['workspace']['path']).joinpath('planning/manifest.json').exists()


@pytest.mark.parametrize('risk', ['match', 'script_auto_pass', 'report_format',
    'conflict_missing_script', 'unresolved_extra_outer', 'match_outer_repair_changes', 'fake_quote',
    'old_script_cache_io', 'material_fork', 'material_fork_copy'])
def test_source_ref_truth_uses_normal_owner_and_preserves_voice_refusals(prep_env, monkeypatch, risk):
    test_vnext_confirmed_preset_truth_boundary(prep_env, monkeypatch, risk, truth_profile=True)


def test_markdown_source_ref_persist_and_two_forks_preserve_full_coverage(prep_env, monkeypatch):
    script = ('## 旁白\r\n先看**问题**，再做[决定][choice]。🌱\r'
              '- 第二步看 `记录`。\n> 第三步保留疑问。\r\n\r\n'
              '## 镜头说明\n画面：白纸放在桌上。\n'
              '## 未经证实的增长数字\r\n~~~text\n它声称去年增长了20%。\n~~~\n\n'
              '| 项目 | 描述 |\n| --- | --- |\n| 结果 | 等待核实 |\n\n'
              '![说明文字](fixture.png)\r\n\r\n[choice]: https://example.test/choice')
    test_vnext_confirmed_preset_truth_boundary(prep_env, monkeypatch, 'material_fork',
        truth_profile=True, script_override=script, ledger_revision='easel-script-claim-ledger@3')
