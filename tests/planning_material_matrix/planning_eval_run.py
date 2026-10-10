"""R4 controlled real runner. Default freeze performs no model calls.

Run one roster index at a time and inspect its independent semantic oracle
before proceeding. Stored files are local, protected, and never Git artifacts.
"""
from __future__ import annotations
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import subprocess
import fcntl

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'web'))
from tests.planning_material_matrix.run import production, protected
from tests.planning_material_matrix.planning_eval import confirm_sample, isolated_process, PlanningEvalBoundary, EvalStateViolation
from easel import creation
from easel.integrations.hypit.secrets import SecretRedactor
from easel.materials.store import AttemptMaterialStore
import app as web

COMMIT = '99b3ca836f7c50f5ecfbea46661f91d4c40c808b'
SOURCE = '0907c35cf4ee98254ac0a598f924d7b757b4aaf29cc24d1ac1d3f234d5e65217'
SAMPLES = ROOT / 'tests/fixtures/planning-eval-r4-2026-10-07/samples.json'
TOOL_PATHS = ('tests/planning_material_matrix/planning_eval.py',
              'tests/planning_material_matrix/planning_eval_run.py',
              'tests/planning_material_matrix/cases.py', 'tests/planning_material_matrix/conftest.py',
              'tests/planning_material_matrix/run.py', 'tests/test_semantic_planning.py',
              'tests/planning_material_matrix/structured_gateway.py', 'tests/structured_planning_product.py')

CONTRAST_RESULTS = {'OBSERVED_CONTRACT_ACCEPT', 'OBSERVED_CONTRACT_REJECT'}
ENGINEERING_SCHEMA = 'planning-engineering-check@1'


def transport_policy_for(manifest):
    from tests.planning_material_matrix.transport_recovery import POLICY
    policy = manifest.get('transport_policy')
    if policy not in (None, POLICY) or manifest.get('schema') == ENGINEERING_SCHEMA and policy != POLICY:
        raise EvalStateViolation('Explicit engineering transport policy required')
    return policy


def model_profile():
    # Authentication remains private; deterministic integration fixtures replace
    # this external configuration read, not the runner or its internal modules.
    return json.loads((Path.home() / '.openclaw-easel/openclaw.json').read_text())


def contrast_probes(original, model_params):
    """Freeze the only mechanical differences before any real submission."""
    from copy import deepcopy
    from easel.integrations.planning_structured import request_for
    from tests.planning_material_matrix.producer_experiment import ProducerUnionExperiment
    offset = original['message'].index('{')
    prefix, context = original['message'][:offset], json.loads(original['message'][offset:])
    if 'schema' in context:
        raise EvalStateViolation('Unexpected embedded response schema in original task')
    rows = []
    for index in range(4):
        probe = deepcopy(original)
        probe.update(representation='current' if index % 2 == 0 else 'union',
                     thinking='disabled' if index < 2 else 'adaptive')
        probe['model_params'] = deepcopy(model_params)
        probe['model_params']['params']['extra_body']['thinking'] = {'type': probe['thinking']}
        if probe['representation'] == 'union':
            codec = ProducerUnionExperiment(original['canonical_schema'])
            probe['schema'] = codec.schema
            changed = deepcopy(context)
            changed['transport']['schema_sha256'] = request_for(codec.schema)['schemaSha256']
            changed['transport']['wire'] = {'codec_policy': 'planning-union-experiment@1',
                'canonical_schema_sha256': request_for(original['canonical_schema'])['schemaSha256'],
                'wire_schema_sha256': request_for(codec.schema)['schemaSha256']}
            changed['wire_representation'] += ' 本次诊断按modality选择工具Schema分支，只填写该分支字段；Condition仍保持原字段。'
            probe['message'] = prefix + json.dumps(changed, ensure_ascii=False, separators=(',', ':'))
        probe['mechanical_differences'] = ([] if index % 2 == 0 else
            ['tool schema', 'transport.schema_sha256', 'transport.wire', 'wire_representation'])
        rows.append(probe)
    return rows


def require_contrast_terminal(current):
    calls = list(current.get('delivery', {}).get('agent_calls', {}).values())
    if (len(calls) != 1 or calls[0].get('status') != 'ok'
            or calls[0].get('runtime_release') != 'released'
            or calls[0].get('reply_contract') != 'planning-result-v3'):
        raise EvalStateViolation('Contrast requires one original successful released native run')
    return calls[0]['run_id']


def contrast_projection(probe):
    """Experiment-only codec. Never selects a product Planning policy."""
    from easel.integrations.planning_wire import FrameProjection
    from tests.planning_material_matrix.producer_experiment import ProducerUnionExperiment
    if probe['representation'] == 'current':
        codec = FrameProjection(probe['canonical_schema'], 'A')
    elif probe['representation'] == 'union':
        codec = ProducerUnionExperiment(probe['canonical_schema'])
    else:
        raise EvalStateViolation('Unknown contrast representation')
    if codec.schema != probe['schema']:
        raise EvalStateViolation('Frozen contrast codec/schema changed')
    return codec


def classify_contrast(probe, raw):
    """Called only after original native run success and safe full capture.

    Contract rejections are data in this one authorized diagnostic experiment,
    never a successful product result or permission to repair/retry.
    """
    from easel.integrations.semantic_boundary import parse_proposal
    codec = contrast_projection(probe)
    value = json.loads(raw)  # A broken transport is not a business rejection.
    result = {'original_result_sha256': hashlib.sha256(raw.encode()).hexdigest(),
              'original_result_bytes': len(raw.encode()), 'transport': 'COMPLETE_NATIVE_SUCCESS',
              'semantic_review': 'NOT_REVIEWED', 'formal_product_admission': False}
    try:
        decoded = codec.decode_valid(value) if probe['representation'] == 'current' else codec.decode(value)
        parse_proposal(decoded, probe['catalog'])
    except ValueError:
        result.update(result='OBSERVED_CONTRACT_REJECT', contract='REJECT')
    else:
        result.update(result='OBSERVED_CONTRACT_ACCEPT', contract='ACCEPT', decoded=decoded)
    return result


def frozen_sample(sample):
    """Fresh isolated confirmation. Its fixture scope cannot purchase media."""
    from easel.integrations import voice_identity
    from easel.integrations.material_generation import generation_budget_preview
    from tests.planning_material_matrix.planning_eval import replay_frozen_preparation
    work = creation.create_creation(sample['theme'], profile='个人经营实践', creative_mode='clear_memo_video',
        route='hypit_video', origin={'type': 'chat', 'session_hash': hashlib.sha256(sample['proposal'].encode()).hexdigest()})
    turn = 'convergence-proposal-' + work['id']
    creation.begin_video_proposal(work['id'], turn, preset_contract=True,
                                 voice_profile_offer=voice_identity.verified_profile())
    saved = creation.save_video_proposal(work['id'], turn, sample['proposal'])
    plan = saved['chat_workflow'].get('video_plan')
    if not plan or plan['schema'] != 'easel-video-proposal@3':
        raise EvalStateViolation('Frozen input is not a legal current proposal')
    transcript = json.dumps([{'role': 'user', 'content': sample['theme']},
                             {'role': 'assistant', 'content': sample['proposal']}], ensure_ascii=False)
    preview = generation_budget_preview()
    work = creation.confirm_chat_proposal(work['id'], 'convergence-confirm-' + work['id'],
        video_plan_sha256=plan['sha256'], production_specs=plan['specs'], delivery_proposal=transcript,
        proposal_sha256=hashlib.sha256(transcript.encode()).hexdigest(),
        generation_budget={'maxCostCny': 1, 'scopeSha256': preview['scope_sha256'], 'allowedModalities': ['voice']},
        input_use_statement_sha256=creation.input_use_preview()['statement_sha256'])
    mapping = replay_frozen_preparation(work, sample['inputs'])
    return work, mapping


def validate_probe(probe, raw):
    from easel.integrations import planning_wire as wire, planning_semantic_review as review
    from easel.integrations import planning_review_support as support
    from easel.integrations.semantic_boundary import parse_proposal
    projection = wire.project(probe['canonical_schema'], probe['stage'], atomic_framing=True)
    if projection.schema != probe['schema']: raise EvalStateViolation('Frozen probe wire changed')
    decoded = projection.decode_valid(json.loads(raw))
    if probe['stage'] == 'A':
        parse_proposal(decoded, probe['catalog'])
    elif probe['stage'] == 'B':
        review.validate_answers(support.decode_slots(decoded, probe['batch']), probe['batch'])
    elif probe['stage'] == 'repair':
        patches = review.decode_patch_slots(decoded, probe['targets'])
        patched = review.apply_patches(probe['original'], patches, probe['targets'])
        from easel.integrations.semantic_boundary_run import validate_canonical
        validate_canonical(probe['catalog'], patched, compiled=True)
        parse_proposal(patched, probe['catalog'])
    else: raise EvalStateViolation('Unknown frozen probe stage')
    return decoded


def record_convergence_review(directory, manifest_path, index, decision, evidence):
    """Independent evaluation oracle only; never changes formal product files."""
    from tests.planning_material_matrix.structured_gateway import EvalHttpBudget
    manifest_bytes = Path(manifest_path).read_bytes()
    manifest = json.loads(manifest_bytes)
    engineering = manifest.get('schema') == ENGINEERING_SCHEMA
    qualification = manifest.get('schema') in {
        'planning-qualification-eval@1', 'planning-qualification-eval@2'}
    first, total = (0, 1) if engineering else (0, 6) if qualification else (4, 10)
    if index not in range(first, total) or decision not in {'PASS', 'FAIL'} or not evidence:
        raise EvalStateViolation('Independent evaluation review invalid')
    manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
    budget = EvalHttpBudget(Path(directory) / 'actual-http', manifest_sha,
                           transport_policy=transport_policy_for(manifest))
    path = Path(directory) / 'runs' / f'run-{index:02}.json'
    result = json.loads(path.read_text())
    if result['manifest_sha256'] != manifest_sha or result['result'] != 'CONTRACT_VALID_SEMANTICS_PENDING':
        raise EvalStateViolation('Evaluation oracle cannot repair a failed product result')
    if result.get('semantic_review') != 'NOT_REVIEWED':
        raise EvalStateViolation('Independent review is immutable')
    try: budget.validate_completion()
    except ValueError: decision = 'FAIL'
    result.update(semantic_review=decision, independent_oracle=evidence)
    if engineering:
        result.update(evaluation_kind='engineering_planning_check', formal_qualification=False,
                      production_dispatch_allowed=False)
    if decision == 'FAIL': result['result'] = 'FAIL'; budget.close()
    save(path, result)
    if index == total - 1 and decision == 'PASS':
        prior = [json.loads((Path(directory) / 'runs' / f'run-{i:02}.json').read_text()) for i in range(total)]
        if any(r['result'] != 'PROBE_PASS' for r in prior[:first]) or any(
                r.get('semantic_review') != 'PASS' or r['result'] != 'CONTRACT_VALID_SEMANTICS_PENDING'
                for r in prior[first:]):
            budget.close(); raise EvalStateViolation('Whole batch lacks complete oracle PASS')
        budget.validate_completion(); budget.close('BATCH_COMPLETE')


def accept_convergence_stage(output, budget):
    if output['result'] == 'FAIL': budget.close()
    else: budget.validate_completion()


def qualification_profile(manifest):
    """One explicit candidate, retaining the unchanged live profile baseline."""
    from copy import deepcopy
    if manifest.get('schema') in {'planning-qualification-eval@2', ENGINEERING_SCHEMA}:
        # An isolated, text-only alternative. Never rewrite the live profile
        # or reinterpret an old M3 manifest as authorization for this model.
        candidate = {
            'model_row': {'id': 'MiniMax-M2.7', 'name': 'MiniMax Token Plan · M2.7',
                'reasoning': True, 'input': ['text'], 'contextWindow': 204800, 'maxTokens': 65536},
            'model_params': {'params': {'max_completion_tokens': 65536,
                'extra_body': {'thinking': {'type': 'adaptive'}}}},
        }
        if manifest.get('candidate') != candidate:
            raise EvalStateViolation('Qualification text-only candidate differs from frozen contract')
        return candidate
    row = deepcopy(manifest['model_rows'][0])
    params = deepcopy(manifest['model_params'])
    if row['id'] != 'MiniMax-M3':
        raise EvalStateViolation('Qualification cannot switch model entitlement')
    row['maxTokens'] = 131072
    params.setdefault('params', {})['max_completion_tokens'] = 131072
    params['params'].setdefault('extra_body', {})['thinking'] = {'type': 'adaptive'}
    candidate = {'model_row': row, 'model_params': params}
    if manifest.get('candidate') != candidate:
        raise EvalStateViolation('Qualification candidate differs from frozen minimal parameter change')
    return candidate


def convergence_main(args):
    """One confirmed batch, using the existing Owner and Supply stop adapter.

    Freeze is call-free. Execution is one immutable roster index at a time;
    independent offline semantic reviews are evaluation records, never product
    reports. A FAIL or crash/UNKNOWN permanently closes the shared HTTP budget.
    """
    from dataclasses import replace
    from easel.runtime_config import EaselRuntimeConfig
    from easel.creation_delivery import active_delivery
    from tests.planning_material_matrix.structured_gateway import EvalHttpBudget, EvalProviderProxy, EvalGateway
    from easel.integrations.planning_structured import request_for, RUNTIME_PARTS, verify_runtime
    directory = args.directory.resolve()
    if directory == ROOT or ROOT in directory.parents or args.directory.is_symlink():
        raise EvalStateViolation('Convergence evidence must have a protected root outside source')
    directory.mkdir(parents=True, exist_ok=True, mode=0o700); directory.chmod(0o700)
    contrast = bool(getattr(args, 'contrast_manifest', None))
    engineering = bool(getattr(args, 'engineering_manifest', None))
    qualification = engineering or bool(getattr(args, 'qualification_manifest', None))
    manifest_path = (args.engineering_manifest if engineering else args.qualification_manifest if qualification
                     else args.contrast_manifest if contrast else args.convergence_manifest)
    raw_manifest = manifest_path.read_bytes()
    manifest = json.loads(raw_manifest)
    manifest_sha = hashlib.sha256(raw_manifest).hexdigest()
    schemas = ({ENGINEERING_SCHEMA} if engineering else
               {'planning-qualification-eval@1', 'planning-qualification-eval@2'} if qualification else
               {'planning-carrier-contrast@1'} if contrast else {'autonomous-convergence-eval@1'})
    if (manifest.get('schema') not in schemas
            or len(manifest['samples']) != (1 if contrast or engineering else 3)
            or len(manifest['probes']) != (0 if qualification else 4) or manifest['fixed_commit'] != args.fixed_commit
            or manifest['fixed_source'] != args.fixed_source):
        raise EvalStateViolation('Convergence manifest/caps/release invalid')
    runtime = Path(manifest['runtime']).resolve(); verify_runtime(runtime)
    transport_policy = transport_policy_for(manifest)
    if contrast and transport_policy is not None:
        raise EvalStateViolation('Historical diagnostic cell cannot add retries')
    budget = EvalHttpBudget(directory / 'actual-http', manifest_sha,
                           limit=4 if contrast else 40, seconds=900 if contrast else 2700,
                           transport_policy=transport_policy)
    first = 0 if qualification else 4
    total = 1 if engineering else 6 if qualification else 4 if contrast else 10
    if qualification:
        expected_limits = {'http': 40, 'seconds': 2700,
                           'themes': 1 if engineering else 3, 'repeats': 1 if engineering else 2}
        if manifest['limits'] != expected_limits:
            raise EvalStateViolation('Qualification limits changed')
        qualification_profile(manifest)
    if contrast:
        if manifest['limits'] != {'http': 4, 'seconds': 900, 'per_cell_http': 1}:
            raise EvalStateViolation('Contrast limits changed')
        for index, probe in enumerate(manifest['probes']):
            if (probe['representation'], probe['thinking']) != (
                    'current' if index % 2 == 0 else 'union', 'disabled' if index < 2 else 'adaptive'):
                raise EvalStateViolation('Contrast roster changed')
            contrast_projection(probe)
        if contrast_probes(manifest['original_probe'], manifest['model_params']) != manifest['probes']:
            raise EvalStateViolation('Contrast task semantics or extra variables changed')
    def integrity():
        if (head() != args.fixed_commit or production()['sha256'] != args.fixed_source
                or hashlib.sha256(manifest_path.read_bytes()).hexdigest() != manifest_sha
                or tool_hashes(contrast=contrast, transport_policy=transport_policy) != manifest['tool_hashes']
                or protected() != manifest['protected_files']):
            raise EvalStateViolation('Frozen convergence source/tool/input/scene changed')
        verify_runtime(runtime)
        for sample in manifest['samples']:
            for row in sample['inputs'].values():
                if hashlib.sha256(Path(row['path']).read_bytes()).hexdigest() != row['sha256']:
                    raise EvalStateViolation('Frozen input bytes changed')
        if contrast or qualification:
            for name, expected in manifest.get('context_files', {}).items():
                if Path(name).name != name:
                    raise EvalStateViolation('Invalid frozen workspace context name')
                path = directory / 'eval-runtime' / name
                if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                    raise EvalStateViolation('Frozen workspace instructions changed')
    integrity()
    original_config = EaselRuntimeConfig.load
    config = original_config()
    # A synthetic media credential binds only these isolated test carriers.
    # It is never sent anywhere: the stop trace prevents every supply/generation.
    fixture_config = replace(config, minimax=replace(config.minimax, api_key='eval-no-media-credential'))
    EaselRuntimeConfig.load = staticmethod(lambda: fixture_config)
    proxy = gateway = None
    original_web = {key: getattr(web, key) for key in ('openclaw_base_cmd', '_proxy_env', 'OPENCLAW_PROFILE', '_hypit_runtime_profile')}
    try:
        with isolated_process(directory / 'eval-runtime', web):
            roster_path = directory / 'roster.json'
            if not roster_path.exists():
                rows = []
                for index in range(total):
                    sample_index = 0 if index < first or engineering else (index - first) // 2
                    work, mapping = frozen_sample(manifest['samples'][sample_index])
                    rows.append({'index': index, 'creation_id': work['id'], 'sample': sample_index,
                                 'kind': 'engineering-planning-check' if engineering else 'protocol-probe' if index < first else 'planning-eval',
                                 'input_mapping': mapping})
                save(roster_path, {'manifest_sha256': manifest_sha, 'runs': rows,
                    'kind': 'isolated evaluation carriers; no production works or media authorization'})
            roster = json.loads(roster_path.read_text())
            if roster['manifest_sha256'] != manifest_sha: raise EvalStateViolation('Roster identity changed')
            if args.one is None:
                print(json.dumps({'frozen': total, 'real_model_calls': 0})); return 0
            if not 0 <= args.one < total: raise EvalStateViolation('Convergence index outside confirmed batch')
            previous = directory / 'runs'; previous.mkdir(exist_ok=True, mode=0o700)
            if list(previous.glob('run-*.json')):
                outcomes = [json.loads(p.read_text()) for p in previous.glob('run-*.json')]
                if any(r.get('result') == 'FAIL' for r in outcomes):
                    budget.close(); raise EvalStateViolation('This real batch failed permanently')
            for i in range(args.one):
                prior = json.loads((previous / f'run-{i:02}.json').read_text())
                if prior['result'] not in (CONTRAST_RESULTS if contrast else {'PROBE_PASS', 'CONTRACT_VALID_SEMANTICS_PENDING'}):
                    raise EvalStateViolation('Previous batch item unfinished')
                if not contrast and i >= first and prior.get('semantic_review') != 'PASS':
                    raise EvalStateViolation('Independent frozen semantic oracle must pass before next input')
            result_path = previous / f'run-{args.one:02}.json'
            if result_path.exists():
                result = json.loads(result_path.read_text())
                if result['result'] in (CONTRAST_RESULTS if contrast else {'PROBE_PASS', 'CONTRACT_VALID_SEMANTICS_PENDING'}):
                    print(json.dumps({'already_completed': args.one, 'new_calls': 0})); return 0
                budget.close(); raise EvalStateViolation('Interrupted item is observation-only; no new submit')
            state = json.loads(budget.path.read_text())
            if state['closed'] or any(r['state'] == 'UNKNOWN' for r in state['requests']):
                budget.close(); raise EvalStateViolation('Closed/unknown batch cannot submit')
            check_authorized_route(directory, 'convergence-start')
            live_config = model_profile()
            provider = live_config['models']['providers']['minimax']
            if [{k: row.get(k) for k in ('id', 'name', 'reasoning', 'input', 'contextWindow', 'maxTokens')} for row in provider['models']] != manifest['model_rows']:
                raise EvalStateViolation('Frozen model capability or output budget changed')
            if (live_config['agents']['defaults'].get('thinkingDefault') != 'off'
                    or live_config['agents']['defaults'].get('models', {}).get('minimax/MiniMax-M3', {}) != manifest['model_params']):
                raise EvalStateViolation('Frozen model thinking/request parameters changed')
            def before_http():
                integrity(); check_authorized_route(directory, 'actual-http')
                current = model_profile()
                defaults = current['agents']['defaults']
                if (current['models']['providers']['minimax'] != provider
                        or defaults.get('thinkingDefault') != 'off'
                        or defaults.get('models', {}).get('minimax/MiniMax-M3', {}) != manifest['model_params']):
                    raise EvalStateViolation('Model parameters changed before actual send')
            expected_payload = None
            params = manifest['model_params']
            model_row = manifest['model_rows'][0]
            expected_model_params = None
            if qualification:
                candidate = qualification_profile(manifest)
                params, model_row = candidate['model_params'], candidate['model_row']
                expected_model_params = {'model': model_row['id'], 'thinking_mode': 'adaptive',
                    'max_tokens': None, 'max_completion_tokens': model_row['maxTokens']}
            if contrast:
                probe = manifest['probes'][args.one]
                params = probe['model_params']
                expected_payload = {'model': 'MiniMax-M3', 'schema_sha256': request_for(probe['schema'])['schemaSha256'],
                    'thinking_mode': probe['thinking'], 'tools_count': 1, 'tool_choice_kind': 'function',
                    'max_tokens': None, 'max_completion_tokens': manifest['model_rows'][0]['maxTokens']}
            proxy = EvalProviderProxy(budget, 'https://api.minimax.cn/v1/chat/completions', model_row['id'],
                provider['apiKey'], before_send=before_http, expected_payload=expected_payload,
                expected_number=args.one + 1 if contrast else None,
                expected_model_params=expected_model_params).start()
            gateway = EvalGateway(runtime, directory / f'gateway-{args.one:02}', __import__('shutil').which('node'),
                proxy, model_row, params).start()
            web.openclaw_base_cmd = lambda: gateway.command
            web._proxy_env = lambda: gateway.env
            web.OPENCLAW_PROFILE = 'convergence-eval'
            web._hypit_runtime_profile = lambda: None
            row = roster['runs'][args.one]
            output = {**row, 'result': 'IN_PROGRESS', 'manifest_sha256': manifest_sha,
                      'started_at': time.time(), 'engineering_intervention': 0, 'supply_calls': 0}
            save(result_path, output)
            try:
                if engineering:
                    output.update(evaluation_kind='engineering_planning_check', formal_qualification=False,
                                  production_dispatch_allowed=False)
                if args.one < first:
                    probe = manifest['probes'][args.one]
                    token = active_delivery.set(row['creation_id'])
                    try:
                        from easel.creation_delivery import DeliveryExecutionUncertain
                        from easel.integrations.openclaw_delivery import reconcile_agent_calls
                        deadline = time.monotonic() + 600
                        while True:
                            try:
                                raw = web._run_timed_creation_agent('planning', 'protocol-probe-' + str(args.one),
                                    probe['message'], 300, 'convergence-probe-' + str(args.one), capture_reply=True,
                                    retry_failed=False, reply_contract='planning-result-v3', structured_result=request_for(probe['schema']))
                                break
                            except DeliveryExecutionUncertain:
                                if time.monotonic() >= deadline: raise
                                time.sleep(1)
                                reconcile_agent_calls(row['creation_id'], command_prefix=gateway.command,
                                    profile=web.OPENCLAW_PROFILE, cwd=str(ROOT), env=gateway.env)
                    finally: active_delivery.reset(token)
                    if contrast:
                        run_id = require_contrast_terminal(creation.get_creation(row['creation_id']))
                        output.update(classify_contrast(probe, raw), representation=probe['representation'],
                                      thinking=probe['thinking'], original_run_id=run_id)
                        # The capture adapter has already checked stored content.
                        # Exact raw arguments remain in native capture, not redacted/re-written as formal evidence.
                    else:
                        output['decoded'] = validate_probe(probe, raw)
                        output.update(result='PROBE_PASS', original_result_sha256=hashlib.sha256(raw.encode()).hexdigest())
                else:
                    boundary = PlanningEvalBoundary()
                    def checkpoint(state, current, result):
                        integrity(); output.update(state); save(result_path, output)
                    state, current, result = asyncio.run(drain_checkpoints(boundary, row['creation_id'], web,
                                                                          checkpoint, max_seconds=600))
                    output.update(state, result='CONTRACT_VALID_SEMANTICS_PENDING' if state['boundary_reached'] else 'FAIL',
                                  semantic_review='NOT_REVIEWED', supply_calls=boundary.supply_calls,
                                  state_violations=boundary.state_violations)
                    if state['boundary_reached']:
                        loaded = boundary.cuts[-1]['planning']
                        output.update(plan=loaded['plan'].model_dump(mode='json'), truth=loaded['truth_ledger'])
                integrity()
                accept_convergence_stage(output, budget)
                if contrast and args.one == 3:
                    budget.close('BATCH_COMPLETE')
            except Exception as exc:
                output.update(result='FAIL', error_type=type(exc).__name__, error=SecretRedactor.redact_text(str(exc)))
                budget.close()
            finally:
                output.update(ended_at=time.time(), delivery=creation.get_creation(row['creation_id'])['delivery'],
                              http_budget=json.loads(budget.path.read_text()))
                save(result_path, output)
            print(json.dumps({'index': args.one, 'result': output['result'],
                              'actual_http': len(output['http_budget']['requests'])}, ensure_ascii=False))
            return 0 if output['result'] in (CONTRAST_RESULTS if contrast else {'PROBE_PASS', 'CONTRACT_VALID_SEMANTICS_PENDING'}) else 2
    finally:
        # Only terminal local runs can be retired. Unknown runs leave their
        # isolated Gateway/config available; the closed batch forbids resubmit.
        pending = False
        if gateway:
            for path in (directory / 'eval-runtime/outputs/_creations').glob('*/creation.json'):
                calls = json.loads(path.read_text()).get('delivery', {}).get('agent_calls', {}).values()
                pending |= any(c.get('status') in {'pending', 'submitting'} or c.get('runtime_release') == 'pending' for c in calls)
            if not pending: gateway.stop()
            else: budget.close()
        if proxy: proxy.stop()
        for key, value in original_web.items(): setattr(web, key, value)
        EaselRuntimeConfig.load = original_config


def tool_hashes(*, contrast=False, transport_policy=None):
    paths = (*TOOL_PATHS, 'tests/planning_material_matrix/producer_experiment.py',
             'tests/test_openclaw_structured_result.py') if contrast else TOOL_PATHS
    if transport_policy is not None:
        transport_policy_for({'transport_policy': transport_policy})
        paths = (*paths, 'tests/planning_material_matrix/transport_recovery.py')
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in paths}


def head():
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()


def save(path, payload):
    text = json.dumps(SecretRedactor.redact(payload), ensure_ascii=False, indent=2) + '\n'
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(text); temp.chmod(0o600); temp.replace(path)


def development_samples(samples):
    rows = [row for row in samples if row['split'] == 'development'][:3]
    if len(rows) != 3: raise EvalStateViolation('Three fixed development themes required; no held-out substitution')
    return rows


def reserve_development_request(goal_directory, directory, round_number, index, phase, *, now=None):
    """One persistent Goal ledger across two rounds; observations do not spend again.

    Records count conservative request reservations, not an unverifiable bill.
    Original requests may be observed after a deadline. No new identity may.
    """
    now = time.time() if now is None else now
    if Path(goal_directory).is_symlink():
        raise EvalStateViolation('Development budget root cannot be a symlink')
    parent, directory = Path(goal_directory).resolve(), Path(directory).resolve()
    if parent == directory or parent == ROOT or ROOT in parent.parents:
        raise EvalStateViolation('Development budget must have its own protected root outside source')
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if parent.is_symlink(): raise EvalStateViolation('Development budget root cannot be a symlink')
    lock, path = parent / 'development-budget.lock', parent / 'development-budget.json'
    if lock.is_symlink() or path.is_symlink(): raise EvalStateViolation('Development budget path unsafe')
    with lock.open('a+') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        budget = json.loads(path.read_text()) if path.exists() else {
            'schema': 'vnext-development-budget@1', 'rounds': {}, 'requests': {}, 'stopped': False}
        if budget.get('schema') != 'vnext-development-budget@1' or round_number not in {1, 2} or not 0 <= index < 6:
            raise EvalStateViolation('Development Goal bounds or ledger invalid')
        identity = hashlib.sha256(json.dumps({k: phase.get(k) for k in (
            'attempt_id', 'session_id', 'message_sha256', 'capture_reply', 'reply_contract', 'timeout', 'retry_failed')},
            sort_keys=True).encode()).hexdigest()
        existing = budget['requests'].get(identity)
        if existing:
            if existing['round'] != round_number or existing['directory'] != str(directory):
                raise EvalStateViolation('Original request cannot be reassigned to another round')
            return {'existing_request_observation': True, 'request_sha256': identity}
        key = str(round_number)
        gate = budget.get('round2_software_gate') or {}
        prior = budget['rounds'].get('1', {})
        second_allowed = (round_number == 2 and key not in budget['rounds'] and prior.get('status') == 'FAIL'
            and isinstance(gate, dict) and gate.get('status') == 'PASS'
            and gate.get('commit') == phase.get('fixed_commit') and gate.get('source_sha256') == phase.get('fixed_source')
            and gate.get('source_sha256') != prior.get('source_sha256') and bool(gate.get('root_cause'))
            and gate.get('original_execution_reconciled') is True and gate.get('historical_unchanged') is True)
        if budget.get('stopped'):
            if not second_allowed: raise EvalStateViolation('Development Goal is stopped; no new request')
            budget['stopped'] = False  # One explicit targeted-fix gate, never a refreshed ledger.
        if key not in budget['rounds']:
            if round_number == 2 and not second_allowed:
                raise EvalStateViolation('Second round requires the one targeted-fix software gate')
            budget['rounds'][key] = {'directory': str(directory), 'started_at': now, 'samples': {},
                                   'source_sha256': phase.get('fixed_source'), 'status': 'IN_PROGRESS'}
        current = budget['rounds'][key]
        if current['directory'] != str(directory): raise EvalStateViolation('Round directory changed; no reset')
        samples = current['samples']
        started = samples.setdefault(str(index), phase.get('sample_started_at', now))
        round_requests = [r for r in budget['requests'].values() if r['round'] == round_number]
        # Completed rounds retain their elapsed duration; switching versions
        # must not erase prior wall time. The active round includes review time.
        elapsed = sum(r.get('elapsed_seconds', 0) for n, r in budget['rounds'].items() if n != key)
        elapsed += now - current['started_at']
        if (len(budget['requests']) >= 64 or len(round_requests) >= 32 or len(samples) > 6
                or now - started >= 480 or now - current['started_at'] >= 3600 or elapsed >= 7200):
            budget.update(stopped=True, stop_reason='Development submission/sample/time limit reached')
            current['elapsed_seconds'] = now - current['started_at']
            save(path, budget)
            raise EvalStateViolation('Development bounds exhausted; original unknown execution remains observation-only')
        budget['requests'][identity] = {'round': round_number, 'index': index, 'directory': str(directory), 'at': now}
        current['elapsed_seconds'] = now - current['started_at']
        save(path, budget)
        return {'existing_request_observation': False, 'request_sha256': identity}


def finish_development_run(goal_directory, round_number, directory, output, *, now=None):
    """Seal fail/time outcomes without changing any native product artifact."""
    now = time.time() if now is None else now
    parent = Path(goal_directory).resolve(); path = parent / 'development-budget.json'
    if not path.exists(): return  # A pre-dispatch rejection spent no allowance.
    with (parent / 'development-budget.lock').open('a+') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        budget = json.loads(path.read_text()); current = budget['rounds'].get(str(round_number))
        if current is None or current['directory'] != str(Path(directory).resolve()):
            raise EvalStateViolation('Development finalization identity changed')
        if current.get('status') in {'PASS', 'FAIL'}:
            return  # Original terminal accounting is immutable during later observation.
        current['elapsed_seconds'] = now - current['started_at']
        total = sum(r.get('elapsed_seconds', 0) for r in budget['rounds'].values())
        started = current['samples'].get(str(output['index']), now)
        overdue = now - started >= 480 or current['elapsed_seconds'] >= 3600 or total >= 7200
        if overdue:
            output.update(result='FAIL', batch_stop_reason='Development time bound exceeded; terminal evidence retained')
        if output.get('result') != 'CONTRACT_VALID_SEMANTICS_PENDING' or output.get('semantic_review') == 'FAIL':
            current['status'] = 'FAIL'
            budget.update(stopped=True, stop_reason=output.get('batch_stop_reason') or output.get('result'))
        elif output['index'] == 5 and output.get('semantic_review') == 'PASS':
            current['status'] = 'PASS'
            budget.update(stopped=True, stop_reason='Development round passed; no Formal R4 dispatch')
        if current['status'] in {'PASS', 'FAIL'}:
            current['ended_at'] = now
        save(path, budget)


def authorize_development_submit(goal_directory, directory, round_number, reservation, run_id, *, now=None):
    """Guard the actual native agent RPC, after its original run handle is durable."""
    now = time.time() if now is None else now
    parent = Path(goal_directory).resolve(); path = parent / 'development-budget.json'
    with (parent / 'development-budget.lock').open('a+') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        budget = json.loads(path.read_text())
        request = budget['requests'].get(reservation or '')
        current = budget['rounds'].get(str(round_number))
        if (not request or not current or request['round'] != round_number
                or request['directory'] != str(Path(directory).resolve())
                or current['directory'] != request['directory']):
            raise EvalStateViolation('Native submission has no exact Development reservation')
        elapsed = now - current['started_at']
        total = elapsed + sum(r.get('elapsed_seconds', 0) for n,r in budget['rounds'].items() if n != str(round_number))
        if (budget.get('stopped') or current['status'] != 'IN_PROGRESS'
                or now - current['samples'][str(request['index'])] >= 480
                or elapsed >= 3600 or total >= 7200 or request.get('native_run_id')):
            raise EvalStateViolation('Native new submission forbidden; reserved identity is not an original execution')
        if not isinstance(run_id, str) or not run_id.startswith('easel-'):
            raise EvalStateViolation('Native submitting handle missing')
        request['native_run_id'] = run_id
        request['submission_reserved_at'] = now
        save(path, budget)


def observe_original_handles(directory, row, web):
    """Only wait/release existing native handles. No Owner, quota or new model phase."""
    from easel.integrations.openclaw_delivery import reconcile_agent_calls
    current = creation.get_creation(row['creation_id'])
    calls = current.get('delivery', {}).get('agent_calls', {})
    pending = [c for c in calls.values() if c.get('status') in {'submitting', 'pending'}
               or c.get('runtime_release') == 'pending']
    profiles = {c.get('profile') for c in pending}
    if len(profiles) > 1 or (profiles and not next(iter(profiles))):
        raise EvalStateViolation('Original pending route is ambiguous')
    if pending:
        reconcile_agent_calls(row['creation_id'], command_prefix=web.openclaw_base_cmd(),
            profile=next(iter(profiles)), cwd=str(ROOT), env=web._proxy_env())
    refreshed = creation.get_creation(row['creation_id'])
    report = {'index': row['index'], 'kind': 'original-handle-observation-only', 'new_submissions': 0,
              'at': time.time(), 'agent_calls': refreshed.get('delivery', {}).get('agent_calls', {})}
    folder = directory / 'observations'; folder.mkdir(exist_ok=True, mode=0o700)
    save(folder / f"run-{row['index']:02}-{time.time_ns()}.json", report)
    return report


def check_authorized_route(directory, stage):
    """Local identity check only; account quota is not an execution gate.

    Keep the existing credential fingerprint file for compatibility. Its
    historical name does not require a new quota response or balance snapshot.
    Actual HTTP/time budgets and unknown-request guards remain independent.
    """
    config = model_profile()
    model = config['agents']['defaults']['model']
    provider = config['models']['providers']['minimax']
    if model != {'primary': 'minimax/MiniMax-M3', 'fallbacks': []} or provider['baseUrl'] != 'https://api.minimax.cn/v1':
        raise EvalStateViolation('Frozen model/route changed; no fallback permitted')
    key = provider['apiKey']
    if not isinstance(key, str) or not key or key.startswith('${'):
        raise EvalStateViolation('Cannot prove configured credential route')
    credential_sha = hashlib.sha256(key.encode()).hexdigest()
    original = json.loads((directory / 'subscription-quota-readonly.json').read_text())
    if credential_sha != original['credential_fingerprint']:
        raise EvalStateViolation('Credential changed; original authorization cannot be reused')
    return {'stage': stage, 'credential_sha256': credential_sha,
            'quota_status': 'NOT_QUERIED', 'cash_fallback_allowed': False,
            'actual_invoice': 'NOT_AVAILABLE'}

def classify_checkpoint(state, current):
    """Classify durable native evidence, never a UI status alone."""
    if state['boundary_reached']:
        return 'CONTRACT_VALID_SEMANTICS_PENDING'
    delivery = current.get('delivery', {})
    calls = list(delivery.get('agent_calls', {}).values())
    if any(c.get('status') in {'pending', 'submitting'} or c.get('runtime_release') == 'pending' for c in calls):
        return 'UNKNOWN_OR_PENDING'
    if any(c.get('status') == 'error' for c in calls) or delivery.get('last_error'):
        return 'FAIL'
    if state['native_next_operation'] in {'prepare', 'observe_agent'}:
        return 'IN_PROGRESS'
    return 'FAIL'


async def drain_checkpoints(boundary, creation_id, web, checkpoint, *, pause=10, max_seconds=1800):
    """Drive existing Owner; observe original handles before continuing."""
    started = time.monotonic()
    while True:
        current = creation.get_creation(creation_id)
        calls = list(current.get('delivery', {}).get('agent_calls', {}).values())
        if any(c.get('status') == 'error' for c in calls) and not any(c.get('runtime_release') == 'pending' for c in calls):
            from easel.creation_delivery import next_operation
            operation, status = next_operation(current)
            state = {'boundary_reached': False, 'owner_advanced': False,
                     'native_next_operation': operation, 'native_delivery_status': status}
            checkpoint(state, current, 'FAIL')
            return state, current, 'FAIL'
        state = await boundary.advance(creation_id, web)
        current = creation.get_creation(creation_id)
        result = classify_checkpoint(state, current)
        checkpoint(state, current, result)
        if result in {'CONTRACT_VALID_SEMANTICS_PENDING', 'FAIL'}:
            return state, current, result
        if time.monotonic() - started >= max_seconds:
            # A bounded client wait is not evidence of model failure. The
            # next invocation must observe this same persisted request.
            return state, current, 'INCOMPLETE_RECOVERABLE'
        await asyncio.sleep(pause if result == 'UNKNOWN_OR_PENDING' else 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--one', type=int, help='One already-frozen roster index; omitting this only freezes input')
    parser.add_argument('--fixed-commit', default=COMMIT, help='Explicit independently accepted release commit')
    parser.add_argument('--fixed-source', default=SOURCE, help='Explicit accepted production source fingerprint')
    parser.add_argument('--development', action='store_true', help='vNext bounded Development Eval, never Formal R4')
    parser.add_argument('--goal-directory', type=Path, help='Persistent shared two-round Development budget root')
    parser.add_argument('--round', type=int, choices=(1, 2), default=1)
    parser.add_argument('--observe-only', action='store_true', help='Wait/release original handles only; never advance Owner')
    parser.add_argument('--convergence-manifest', type=Path, help='Confirmed frozen-Preparation/actual-HTTP convergence batch')
    parser.add_argument('--contrast-manifest', type=Path, help='Authorized fixed four-cell A-only diagnostic experiment')
    parser.add_argument('--qualification-manifest', type=Path, help='Separate three-theme six-case full Planning batch')
    parser.add_argument('--engineering-manifest', type=Path, help='One complete Planning/Truth engineering check; not stability or media authorization')
    args = parser.parse_args()
    if sum(bool(value) for value in (args.contrast_manifest, args.convergence_manifest, args.qualification_manifest, args.engineering_manifest)) > 1:
        raise EvalStateViolation('Exactly one immutable batch mode is required')
    if args.convergence_manifest or args.contrast_manifest or args.qualification_manifest or args.engineering_manifest:
        return convergence_main(args)
    directory = args.directory.resolve()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory.chmod(0o700)
    fixed_commit, fixed_source = args.fixed_commit, args.fixed_source
    if head() != fixed_commit:
        raise EvalStateViolation('Actual HEAD differs from the fixed commit')
    if production()['sha256'] != fixed_source:
        raise EvalStateViolation('Production source differs from accepted/fixed SHA')
    samples = json.loads(SAMPLES.read_text())['samples']
    if args.development:
        if args.goal_directory is None: raise EvalStateViolation('Development requires a persistent Goal budget root')
        samples = development_samples(samples)
    roster_path = directory / 'roster.json'
    with isolated_process(directory / 'eval-runtime', web):
        if not roster_path.exists():
            roster = []
            for sample in samples:
                for repeat in range(2):
                    work = confirm_sample(sample)
                    roster.append({'index': len(roster), 'sample_id': sample['id'], 'split': sample['split'],
                        'repeat': repeat + 1, 'creation_id': work['id'],
                        'proposal_sha256': work['delivery']['video_plan']['sha256'],
                        'script_sha256': sample['expected_script_sha256']})
            save(roster_path, {'commit': fixed_commit, 'source_sha256': fixed_source,
                               'samples_sha256': hashlib.sha256(SAMPLES.read_bytes()).hexdigest(), 'runs': roster,
                               'evaluation_kind': 'development' if args.development else 'formal_r4',
                               'round': args.round if args.development else None,
                               'goal_directory': str(args.goal_directory.resolve()) if args.development else None})
        frozen = json.loads(roster_path.read_text())
        if frozen['commit'] != fixed_commit or frozen['source_sha256'] != fixed_source:
            raise EvalStateViolation('An existing batch cannot change its fixed release')
        if frozen['samples_sha256'] != hashlib.sha256(SAMPLES.read_bytes()).hexdigest():
            raise EvalStateViolation('Frozen samples changed; cannot reuse this batch')
        if frozen.get('evaluation_kind', 'formal_r4') != ('development' if args.development else 'formal_r4'):
            raise EvalStateViolation('A frozen batch cannot change evaluation kind')
        if args.development and (len(frozen['runs']) != 6 or frozen.get('round') != args.round
                or frozen.get('goal_directory') != str(args.goal_directory.resolve())):
            raise EvalStateViolation('Development roster/round identity changed')
        batch_path = directory / 'batch-baseline.json'
        if not batch_path.exists():
            if list((directory / 'runs').glob('run-*.json')):
                raise EvalStateViolation('Cannot create a new baseline after real execution')
            # Pure paths and digests, no credential/config contents. Preserve
            # path keys literally rather than applying secret-field redaction.
            batch_path.write_text(json.dumps({'protected_files': protected(), 'tool_hashes': tool_hashes()}, indent=2) + '\n')
            batch_path.chmod(0o600)
        batch = json.loads(batch_path.read_text())
        if batch['tool_hashes'] != tool_hashes() or batch['protected_files'] != protected():
            raise EvalStateViolation('Frozen evaluation tool or historical scene baseline changed')
        if args.one is None:
            print(json.dumps({'roster_frozen': len(frozen['runs']), 'real_eval_calls': 0})); return 0
        authorization = json.loads((directory / 'user-authorization.json').read_text())
        if not authorization['raw_stream_exception_accepted'] or authorization['billing_scope'] != 'existing purchased text subscription quota only':
            raise EvalStateViolation('Missing batch fee/evidence authorization')
        if not 0 <= args.one < len(frozen['runs']):
            raise EvalStateViolation('Index outside the frozen batch')
        if args.observe_only:
            report = observe_original_handles(directory, frozen['runs'][args.one], web)
            print(json.dumps({'index': args.one, 'original_observation': True, 'new_calls': 0}))
            return 0
        results_dir = directory / 'runs'; results_dir.mkdir(exist_ok=True, mode=0o700)
        previous = [json.loads(p.read_text()) for p in results_dir.glob('run-*.json')]
        if any(r['result'] == 'FAIL' or r.get('semantic_review') == 'FAIL' for r in previous):
            if args.development:
                for result in previous:
                    if result['result'] == 'FAIL' or result.get('semantic_review') == 'FAIL':
                        finish_development_run(args.goal_directory, args.round, directory, result)
            raise EvalStateViolation('A previous actual run failed; this R4 batch is stopped')
        by_index = {r['index']: r for r in previous}
        if any(i not in by_index or by_index[i]['result'] != 'CONTRACT_VALID_SEMANTICS_PENDING'
               or by_index[i].get('semantic_review') != 'PASS' for i in range(args.one)):
            raise EvalStateViolation('Every earlier index must have valid contract and independent semantic PASS')
        row = frozen['runs'][args.one]
        result_path = results_dir / f'run-{args.one:02}.json'
        if result_path.exists() and json.loads(result_path.read_text())['result'] == 'CONTRACT_VALID_SEMANTICS_PENDING':
            completed = json.loads(result_path.read_text())
            if args.development:
                finish_development_run(args.goal_directory, args.round, directory, completed)
                save(result_path, completed)
            print(json.dumps({'already_completed': args.one, 'result': completed['result'], 'new_calls': 0}))
            return 0 if completed['result'] == 'CONTRACT_VALID_SEMANTICS_PENDING' else 2
        baseline = batch['protected_files']
        before = time.monotonic()
        reserved_identity = [None]
        def pre_stage(phase):
            if (production()['sha256'] != fixed_source or protected() != baseline or batch['tool_hashes'] != tool_hashes()
                    or head() != fixed_commit or frozen['samples_sha256'] != hashlib.sha256(SAMPLES.read_bytes()).hexdigest()):
                raise EvalStateViolation('Fixed source or historical evidence changed; no next call')
            check_authorized_route(directory, phase['phase'])
            if args.development:
                reserved = reserve_development_request(args.goal_directory, directory, args.round, args.one,
                    {**phase, 'fixed_commit': fixed_commit, 'fixed_source': fixed_source,
                     'sample_started_at': output['lifecycle_started_at']})
                reserved_identity[0] = reserved['request_sha256']
            print(json.dumps({'index': args.one, 'phase': phase['phase'], 'session': phase['session_id']}), flush=True)
        def before_submit(params):
            if args.development:
                authorize_development_submit(args.goal_directory, directory, args.round,
                                             reserved_identity[0], params.get('idempotencyKey'))
        boundary = PlanningEvalBoundary(pre_stage, before_submit)
        previous_output = json.loads(result_path.read_text()) if result_path.exists() else {}
        output = {**row, 'result': 'IN_PROGRESS', 'semantic_review': 'NOT_REVIEWED',
                  'source_sha256': fixed_source, 'engineering_intervention': 0}
        output['lifecycle_started_at'] = previous_output.get('lifecycle_started_at', time.time())
        output['checkpoints'] = previous_output.get('checkpoints', [])
        output['prior_phase_invocations'] = previous_output.get('prior_phase_invocations', []) + previous_output.get('phase_invocations', [])
        invocations = directory / 'run-invocations'; invocations.mkdir(exist_ok=True, mode=0o700)
        invocation_path = invocations / f'run-{args.one:02}-{time.time_ns()}.json'
        save(result_path, output)
        try:
            def checkpoint(state, current, result):
                # Integrity is checked at observations too, even when no new
                # model request is necessary. Keep all native transitions.
                output.update(state)
                if (protected() != baseline or tool_hashes() != batch['tool_hashes']
                        or production()['sha256'] != fixed_source or head() != fixed_commit):
                    raise EvalStateViolation('Checkpoint integrity changed')
                output['checkpoints'].append({'at': time.time(), 'result': result, **state,
                    'agent_calls': current.get('delivery', {}).get('agent_calls', {})})
                output.update(result=result)
                save(result_path, output)
                print(json.dumps({'index': args.one, 'checkpoint': result,
                                  'next': state['native_next_operation']}), flush=True)
            state, current, result = asyncio.run(drain_checkpoints(boundary, row['creation_id'], web, checkpoint,
                max_seconds=480 if args.development else 1800))
            attempt = current.get('hypit_attempts', [{}])[-1] if current.get('hypit_attempts') else {}
            output.update(state)
            output['attempt_id'] = attempt.get('attempt_id')
            output['delivery'] = current.get('delivery')
            output['preparation'] = current.get('preparation')
            if attempt.get('workspace'):
                store = AttemptMaterialStore(Path(attempt['workspace']['path']))
                recovery = store.read_recovery_record('semantic-planning-vnext' if args.development else 'semantic-planning-v3') or {}
                output['semantic_recovery'] = recovery
                output['repair_triggered'] = bool(recovery.get('repair_used'))
                output['planning_calls'] = list(recovery.get('calls', {}))
            if state['boundary_reached']:
                output['result'] = 'CONTRACT_VALID_SEMANTICS_PENDING'
                saved = boundary.cuts[-1]['planning']
                output['plan'] = saved['plan'].model_dump(mode='json')
                output['truth'] = saved['truth_ledger']
                output['requirements'] = json.loads((Path(attempt['workspace']['path']) / 'planning/MATERIAL_REQUIREMENTS.json').read_text())
            else:
                output['result'] = result
        except Exception as exc:
            output.update(result='FAIL', error=SecretRedactor.redact_text(str(exc)), error_type=type(exc).__name__)
        finally:
            output.update(elapsed_seconds=round(time.monotonic() - before, 3),
                lifecycle_elapsed_seconds=round(time.time() - output['lifecycle_started_at'], 3), phase_invocations=boundary.phase_calls,
                supply_calls=boundary.supply_calls, state_violations=boundary.state_violations)
            try:
                output.update(historical_scene_unchanged=protected() == baseline,
                    production_unchanged=production()['sha256'] == fixed_source, tool_unchanged=batch['tool_hashes'] == tool_hashes(),
                    head_unchanged=head() == fixed_commit,
                    samples_unchanged=frozen['samples_sha256'] == hashlib.sha256(SAMPLES.read_bytes()).hexdigest())
            except Exception as exc:
                output.update(result='FAIL', reconciliation_error=SecretRedactor.redact_text(str(exc)))
            if (not all(output.get(k, False) for k in ('historical_scene_unchanged', 'production_unchanged', 'tool_unchanged', 'head_unchanged', 'samples_unchanged'))
                    or boundary.supply_calls or boundary.state_violations):
                output['result'] = 'FAIL'
                output['batch_stop_reason'] = 'Frozen code/tool/scene mismatch or forbidden downstream entry'
            if args.development:
                finish_development_run(args.goal_directory, args.round, directory, output)
            save(result_path, output)
            save(invocation_path, output)
        print(json.dumps({k: output.get(k) for k in ('index', 'result', 'attempt_id', 'elapsed_seconds', 'repair_triggered', 'supply_calls', 'error_type')}, ensure_ascii=False), flush=True)
        return 0 if output['result'] == 'CONTRACT_VALID_SEMANTICS_PENDING' else 2


if __name__ == '__main__':
    raise SystemExit(main())
