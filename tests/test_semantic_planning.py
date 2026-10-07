"""Independent semantic oracle and native Planning v3 integration regressions."""
from pathlib import Path
import json
import pytest
from easel.materials.domain import MaterialPlan
from easel.materials.application.visual_contract import planning_contracts

FIXTURE = Path(__file__).parent / 'fixtures/planning-semantic-contract-2026-10-07'


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


@pytest.mark.parametrize('risk', ['skip_predecessors', 'tool_drift', 'scene_drift', 'quota_unknown', 'quota_low', 'end_scene_drift'])
def test_r4_runner_preflight_refuses_unsafe_submission(prep_env, tmp_path, monkeypatch, risk):
    import hashlib, re, sys, urllib.request
    from tests.planning_material_matrix import planning_eval_run as runner
    directory = tmp_path / 'protected-eval'
    current_scene = {'old-scene': 'original-sha'}
    current_tools = {'runner': 'frozen-sha'}
    # Version/scene services and private quota HTTP are external read-only
    # boundaries. Normal confirmation and Owner/Preparation remain native.
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
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def read(self):
            quota = {} if risk == 'quota_unknown' else {'current_interval_remaining_percent': 100 if risk == 'end_scene_drift' else 24,
                                                       'current_weekly_remaining_percent': 99}
            return json.dumps({'base_resp': {'status_code': 0}, 'model_remains': [quota]}).encode()
    monkeypatch.setattr(urllib.request, 'urlopen', lambda *_args, **_kwargs: Response())
    submissions = []
    def forbidden(*args, **kwargs):
        submissions.append(args)
        if risk != 'end_scene_drift': raise AssertionError('Precheck allowed an actual model submission')
        from tests.test_creation_preparation import prep, creation, write_drafts
        message = args[0]
        work = creation.get_creation(json.loads((directory / 'roster.json').read_text())['runs'][0]['creation_id'])
        if message.startswith('〔Easel Semantic Planning V3〕'):
            Path(re.search(r'只写 (.+\.json)', message)[1]).write_text(json.dumps(semantic_draft()))
        elif message.startswith('〔Easel Planning V3 单元分类〕'):
            request=json.loads(message.splitlines()[-1])
            value=_authority_fixed_response(request) if 'controls' in request else labels()
            Path(re.search(r'只写 (.+\.json)', message)[1]).write_text(json.dumps(value))
        elif message.startswith('〔Easel Script 系统审阅〕'):
            target = Path(re.search(r'只写 (.+\.json)，JSON 结构', message)[1])
            response = json.loads(message.split('（逐项替换判断，不增加字段）：\n', 1)[1].split('\n写入后停止。', 1)[0])
            for row in response['decisions']: row.update(kind='creative_expression', reason='fixed non-factual input')
            target.write_text(json.dumps(response))
            # Read-only digest service now reports a changed historical scene.
            current_scene['old-scene'] = 'changed-after-last-model-call'
        else:
            write_drafts(work, prep.preparation_paths(work['id'], work['preparation']['operation_key'])['draft'])
        return 'external fixture complete'
    monkeypatch.setattr(runner.web, 'run_agent_sync', forbidden)
    monkeypatch.setattr(sys, 'argv', ['eval', '--directory', str(directory), '--one', '31' if risk == 'skip_predecessors' else '0'])
    if risk in {'quota_unknown', 'quota_low', 'end_scene_drift'}:
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
    assert bool(submissions) == (risk == 'end_scene_drift')


@pytest.mark.parametrize('risk', ['success', 'truth_reject', 'repair_failed', 'uncertain'])
def test_r4_native_eval_stops_before_supply(prep_env, monkeypatch, risk):
    import asyncio, re
    from tests.test_creation_preparation import web, prep, creation, write_drafts
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
            assert first['boundary_reached'] and first['owner_advanced']
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
            assert result == 'CONTRACT_VALID_SEMANTICS_PENDING' and len(runs) == expected_calls, (current['delivery'].get('last_error'), mismatch)
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
