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
import urllib.request
import subprocess

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
              'tests/planning_material_matrix/run.py', 'tests/test_semantic_planning.py')


def tool_hashes():
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in TOOL_PATHS}


def head():
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()


def save(path, payload):
    text = json.dumps(SecretRedactor.redact(payload), ensure_ascii=False, indent=2) + '\n'
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(text); temp.chmod(0o600); temp.replace(path)


def quota_check(directory, stage):
    # Same provider credential as the frozen actual deployment; never copied
    # into records. This is a read-only official subscription usage endpoint.
    config = json.loads((Path.home() / '.openclaw-easel/openclaw.json').read_text())
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
    request = urllib.request.Request('https://www.minimax.cn/v1/token_plan/remains',
        headers={'Authorization': 'Bearer ' + key}, method='GET')
    with urllib.request.urlopen(request, timeout=20) as response:
        value = json.loads(response.read())
    rows = value.get('model_remains', [])
    if value.get('base_resp', {}).get('status_code') != 0 or not rows:
        raise EvalStateViolation('Subscription quota cannot be read; no model call')
    selected = [{k: r.get(k) for k in ('model_name', 'current_interval_remaining_percent',
                'current_weekly_remaining_percent', 'current_interval_status', 'current_weekly_status',
                'current_interval_usage_count', 'current_weekly_usage_count')} for r in rows]
    # Conservative pre-submit reserve, not a claim of atomic account billing
    # control. Server/shared quota and actual invoice remain separately noted.
    for row in selected:
        for k in ('current_interval_remaining_percent', 'current_weekly_remaining_percent'):
            if not isinstance(row[k], (int, float)) or row[k] < 25:
                raise EvalStateViolation('Quota below evaluation reserve; no credits/overage fallback')
    saved = {'stage': stage, 'at': time.time(), 'quota': selected, 'credential_sha256': credential_sha,
             'cash_fallback_allowed': False, 'actual_invoice': 'NOT_AVAILABLE'}
    folder = directory / 'quota-checks'; folder.mkdir(exist_ok=True, mode=0o700)
    save(folder / (str(time.time_ns()) + '.json'), saved)
    return saved


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
    args = parser.parse_args()
    directory = args.directory.resolve()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory.chmod(0o700)
    fixed_commit, fixed_source = args.fixed_commit, args.fixed_source
    if head() != fixed_commit:
        raise EvalStateViolation('Actual HEAD differs from the fixed commit')
    if production()['sha256'] != fixed_source:
        raise EvalStateViolation('Production source differs from accepted/fixed SHA')
    samples = json.loads(SAMPLES.read_text())['samples']
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
                               'samples_sha256': hashlib.sha256(SAMPLES.read_bytes()).hexdigest(), 'runs': roster})
        frozen = json.loads(roster_path.read_text())
        if frozen['commit'] != fixed_commit or frozen['source_sha256'] != fixed_source:
            raise EvalStateViolation('An existing batch cannot change its fixed release')
        if frozen['samples_sha256'] != hashlib.sha256(SAMPLES.read_bytes()).hexdigest():
            raise EvalStateViolation('Frozen samples changed; cannot reuse this batch')
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
        if not 0 <= args.one < 32:
            raise EvalStateViolation('Index outside the frozen 32-run batch')
        results_dir = directory / 'runs'; results_dir.mkdir(exist_ok=True, mode=0o700)
        previous = [json.loads(p.read_text()) for p in results_dir.glob('run-*.json')]
        if any(r['result'] == 'FAIL' or r.get('semantic_review') == 'FAIL' for r in previous):
            raise EvalStateViolation('A previous actual run failed; this R4 batch is stopped')
        by_index = {r['index']: r for r in previous}
        if any(i not in by_index or by_index[i]['result'] != 'CONTRACT_VALID_SEMANTICS_PENDING'
               or by_index[i].get('semantic_review') != 'PASS' for i in range(args.one)):
            raise EvalStateViolation('Every earlier index must have valid contract and independent semantic PASS')
        row = frozen['runs'][args.one]
        result_path = results_dir / f'run-{args.one:02}.json'
        if result_path.exists() and json.loads(result_path.read_text())['result'] == 'CONTRACT_VALID_SEMANTICS_PENDING':
            print(json.dumps({'already_completed': args.one, 'new_calls': 0})); return 0
        baseline = batch['protected_files']
        before = time.monotonic()
        def pre_stage(phase):
            if (production()['sha256'] != fixed_source or protected() != baseline or batch['tool_hashes'] != tool_hashes()
                    or head() != fixed_commit or frozen['samples_sha256'] != hashlib.sha256(SAMPLES.read_bytes()).hexdigest()):
                raise EvalStateViolation('Fixed source or historical evidence changed; no next call')
            quota_check(directory, phase['phase'])
            print(json.dumps({'index': args.one, 'phase': phase['phase'], 'session': phase['session_id']}), flush=True)
        boundary = PlanningEvalBoundary(pre_stage)
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
            state, current, result = asyncio.run(drain_checkpoints(boundary, row['creation_id'], web, checkpoint))
            attempt = current.get('hypit_attempts', [{}])[-1] if current.get('hypit_attempts') else {}
            output.update(state)
            output['attempt_id'] = attempt.get('attempt_id')
            output['delivery'] = current.get('delivery')
            output['preparation'] = current.get('preparation')
            if attempt.get('workspace'):
                recovery = AttemptMaterialStore(Path(attempt['workspace']['path'])).read_recovery_record('semantic-planning-v3') or {}
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
            save(result_path, output)
            save(invocation_path, output)
        print(json.dumps({k: output.get(k) for k in ('index', 'result', 'attempt_id', 'elapsed_seconds', 'repair_triggered', 'supply_calls', 'error_type')}, ensure_ascii=False), flush=True)
        return 0 if output['result'] == 'CONTRACT_VALID_SEMANTICS_PENDING' else 2


if __name__ == '__main__':
    raise SystemExit(main())
