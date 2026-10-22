"""Offline rule provenance, explicit assembly and new-task recovery contracts.

These assertions verify routing and protection, not the model's writing quality.
"""
import asyncio
from copy import deepcopy
from dataclasses import replace
import json
from types import SimpleNamespace

import pytest

from easel.production import expression_policy as policy
from easel.production.context import TaskContext
from easel.production.errors import ProductionError
from easel.production.service import row
from .test_model_tasks import run, Answer
from .test_planning_runtime import setup
from .test_director_runtime import claim_context


def change_defaults(monkeypatch):
    monkeypatch.setattr(policy, 'VERSION', 'test-next-version')
    monkeypatch.setattr(policy, 'RULES', {**policy.RULES, 'core': 'Changed future default.'})


@pytest.mark.parametrize('role', ['write', 'visual', 'review'])
@pytest.mark.parametrize('director', [{}, {'narrative': '严肃分析，保留术语与推理'}])
def test_explicit_role_uses_shared_core_without_changing_director_or_facts(role, director):
    saved = policy.snapshot()
    text = '我计划做一次试验；仅当条件成立时可能有效，不代表必然有效。'
    ctx = TaskContext('w', 'r', 't', director=director, facts=(text,),
                      expression_policy=saved,
                      plan={'script': text, 'conversation_basis': {'expression_policy': saved}})
    runner, transport, authorized = run([{'content': '{"summary":"ok"}'}])
    asyncio.run(runner.run(ctx, '任意任务名，与角色选择无关', Answer, expression_role=role))
    assert authorized == ['t'] and len(transport.calls) == 1
    system = transport.calls[0][0]['content']
    assert saved['rules']['core'] in system and saved['rules'][role] in system
    for other in {'write', 'visual', 'review'} - {role}:
        assert saved['rules'][other] not in system
    data = json.loads(transport.calls[0][1]['content'][0]['text'])
    assert data['director'] == director and data['facts'] == [text]
    assert data['plan']['script'] == text
    assert 'expression_policy' not in data['plan']['conversation_basis']
    assert ctx.plan['conversation_basis']['expression_policy'] == saved


def test_noncreative_task_does_not_infer_role_from_description():
    runner, transport, _ = run([{'content': '{"summary":"ok"}'}])
    asyncio.run(runner.run(TaskContext('w', 'r', 't'), '去AI味 写作 剪辑 审片 导演拆解', Answer))
    assert policy.RULES['core'] not in transport.calls[0][0]['content']


@pytest.mark.parametrize('tamper', ['missing', 'text', 'digest', 'shape'])
def test_missing_or_corrupt_snapshot_stops_before_authorization(tamper):
    saved = policy.snapshot()
    if tamper == 'missing': saved = {}
    elif tamper == 'text': saved['rules']['write'] += 'forged'
    elif tamper == 'digest': saved['digest'] = 'forged'
    else: saved['rules']['extra'] = 'not a supported fragment'
    runner, transport, authorized = run([])
    with pytest.raises(ProductionError) as caught:
        asyncio.run(runner.run(TaskContext('w', 'r', 't', expression_policy=saved),
                               'plan', Answer, expression_role='write'))
    assert caught.value.code == ('expression_policy_missing' if tamper == 'missing' else 'expression_policy_invalid')
    assert not transport.calls and not authorized


def test_context_fingerprint_tracks_rule_text_without_duplicate_model_metadata(monkeypatch):
    old = policy.snapshot()
    first = TaskContext('w', 'r', 't', expression_policy=old)
    change_defaults(monkeypatch)
    second = replace(first, expression_policy=policy.snapshot())
    assert first.creative_data() == second.creative_data()
    assert first.fingerprint != second.fingerprint
    assert policy.validate(old) == old  # Prior saved version remains supported.


def test_plan_uses_creation_snapshot_and_receipt_after_default_change_and_crash(tmp_path, monkeypatch):
    service, work, transport, worker = setup(tmp_path)
    planning = worker.handlers['plan'].__self__
    ctx = claim_context(worker)
    saved = deepcopy(ctx.payload['creation_basis']['expression_policy'])
    freeze = service.freeze_plan
    def crash(*args, **kwargs):
        raise RuntimeError('simulate crash after model receipt, before Plan commit')
    monkeypatch.setattr(service, 'freeze_plan', crash)
    with pytest.raises(RuntimeError):
        asyncio.run(planning.plan(ctx))
    assert transport.calls == 1 and not service.snapshot(work)['plans']
    with service.store.connection() as conn:
        before = dict(conn.execute('SELECT * FROM operations').fetchone())
    change_defaults(monkeypatch)
    monkeypatch.setattr(service, 'freeze_plan', freeze)
    assert asyncio.run(planning.plan(ctx)).state == 'succeeded'
    assert transport.calls == 1
    plan = service.snapshot(work)['plans'][0]['plan']
    assert plan['conversation_basis']['expression_policy'] == saved
    with service.store.connection() as conn:
        after = dict(conn.execute('SELECT * FROM operations').fetchone())
    assert after['request_json'] == before['request_json']
    assert after['receipt_json'] == before['receipt_json']
    selected = SimpleNamespace(work_id=work, run_id=ctx.run_id, task_id=ctx.task_id, plan_revision=1, payload={})
    assert planning.context(selected).expression_policy == saved


def test_unknown_is_not_reissued_even_after_default_change(tmp_path, monkeypatch):
    service, _, transport, worker = setup(tmp_path, fail=True)
    planning = worker.handlers['plan'].__self__
    ctx = claim_context(worker)
    with pytest.raises(TimeoutError): asyncio.run(planning.plan(ctx))
    change_defaults(monkeypatch)
    outcome = asyncio.run(planning.plan(ctx))
    assert outcome.state == 'needs_decision' and outcome.error.code == 'result_unknown'
    assert transport.calls == 1
    with service.store.connection() as conn:
        assert conn.execute('SELECT state FROM operations').fetchone()[0] == 'unknown'


def test_historical_planning_task_is_not_stamped_or_called(tmp_path):
    service, work, transport, worker = setup(tmp_path)
    with service.store.transaction() as conn:
        task = dict(conn.execute('SELECT * FROM tasks').fetchone())
        payload = json.loads(task['payload_json'])
        payload['creation_basis'].pop('expression_policy')
        raw = json.dumps(payload)
        conn.execute('UPDATE tasks SET payload_json=? WHERE id=?', (raw, task['id']))
    asyncio.run(worker.run_once())
    after = service.snapshot(work)
    assert after['state'] == 'needs_decision' and not after['plans']
    assert json.loads(after['tasks'][0]['error_json'])['code'] == 'expression_policy_missing'
    assert after['tasks'][0]['payload_json'] == raw and transport.calls == 0
    with service.store.connection() as conn:
        assert conn.execute('SELECT count(*) FROM operations').fetchone()[0] == 0


def test_manual_freeze_ignores_client_policy_and_does_not_rewrite_script(tmp_path):
    service, work, transport, _ = setup(tmp_path)
    submitted = deepcopy(transport.answer)
    submitted['script'] = '仅当条件成立时可能有效，不代表必然有效。'
    submitted['conversation_basis'] = {'expression_policy': {'rules': 'client instructions'}}
    with service.store.transaction() as conn:
        frozen = service.freeze_plan(conn, row(conn, 'works', work), submitted)
    assert frozen['conversation_basis']['expression_policy'] == policy.snapshot()
    assert frozen['script'] == submitted['script'] and frozen['scenes'] == submitted['scenes']
    assert transport.calls == 0


def test_protected_replan_keeps_saved_policy_without_write_instructions(tmp_path):
    service, work, transport, worker = setup(tmp_path)
    with service.store.transaction() as conn:
        protected = service.freeze_plan(conn, row(conn, 'works', work), transport.answer)
    # This path changes only audio mode. Use a short protected voice script.
    voice = {'provider': 'fixture', 'model': 'voice', 'voice_id': 'fixed', 'engine': 'fixture', 'parameters': {}}
    protected['settings'].update(audio_mode='mixed', voice=voice)
    transport.answer['settings'].update(audio_mode='voice', voice=voice)
    with service.store.transaction() as conn:
        settings = json.loads(conn.execute('SELECT settings_json FROM works WHERE id=?', (work,)).fetchone()[0])
        settings.update(audio_mode='voice', voice=voice)
        conn.execute('UPDATE works SET settings_json=? WHERE id=?', (json.dumps(settings), work))
        task = dict(conn.execute('SELECT * FROM tasks').fetchone())
        payload = json.loads(task['payload_json'])
        payload['protected_plan'] = protected
        conn.execute('UPDATE tasks SET payload_json=? WHERE id=?', (json.dumps(payload), task['id']))
    asyncio.run(worker.run_once())
    assert transport.calls == 1
    assert policy.RULES['core'] not in transport.requests[0][0][0]['content']
    snap = service.snapshot(work)
    assert snap['state'] == 'awaiting_confirmation', snap['tasks']
    frozen = snap['plans'][0]['plan']
    assert frozen['script'] == protected['script'] and frozen['scenes'] == protected['scenes']
    assert frozen['conversation_basis'] == protected['conversation_basis']


def test_old_confirmed_plan_cannot_start_supply_or_spend(tmp_path):
    from easel.production.store import Store
    from easel.production.service import WorkService
    from easel.production.operations import OperationService
    from easel.production.supply_tasks import SupplyTasks
    from easel.production.worker import TaskContext as WorkerContext
    from .test_operations import owned_request
    store = Store(tmp_path / 'old.sqlite3'); store.initialize()
    spec = owned_request(store)  # Historical plan deliberately has no policy.
    service = WorkService(store, outputs=tmp_path / 'outputs', profiles=tmp_path / 'profiles')
    ctx = WorkerContext(store, spec['work_id'], spec['run_id'], spec['task_id'],
                        'owner', 1, 1, 'input', {}, lambda: 1000)
    before = service.snapshot(spec['work_id'])['plans']
    result = asyncio.run(SupplyTasks(service, OperationService(store)).supply(ctx))
    assert result.state == 'needs_decision' and result.error.code == 'expression_policy_missing'
    assert service.snapshot(spec['work_id'])['plans'] == before
    with store.connection() as conn:
        assert conn.execute('SELECT count(*) FROM operations').fetchone()[0] == 0
