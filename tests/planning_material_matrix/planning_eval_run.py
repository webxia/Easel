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
              'tests/planning_material_matrix/run.py', 'tests/test_semantic_planning.py')


def tool_hashes():
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in TOOL_PATHS}


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
    parser.add_argument('--development', action='store_true', help='vNext bounded Development Eval, never Formal R4')
    parser.add_argument('--goal-directory', type=Path, help='Persistent shared two-round Development budget root')
    parser.add_argument('--round', type=int, choices=(1, 2), default=1)
    parser.add_argument('--observe-only', action='store_true', help='Wait/release original handles only; never advance Owner')
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
            quota_check(directory, phase['phase'])
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
