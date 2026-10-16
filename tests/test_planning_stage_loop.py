"""Current New-Only Planning controlled stage loop, all external model calls synthetic.

A native terminal rejection in these tests is an explicit test fixture only.
Production eligibility still requires the installed OpenClaw transcript and
scoped rejection bytes, verified under the real Run/Session/Schema.
"""
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from easel.integrations import semantic_boundary_run
from easel.integrations import openclaw_delivery
from easel.integrations import planning_stage_recovery as loop
from easel.materials.store import AttemptMaterialStore
from tests.test_creation_preparation import _current_vnext_planning_executor
from tests.test_planning_d2_owner_integration import _fresh_d2_attempt, _frozen_context
from tests.test_material_integration import material_integration_env


def _run(attempt, context, **kwargs):
    return _current_vnext_planning_executor(
        attempt, context, creative_claims=True, d2_review=True, **kwargs)


def _evidence(creation_id, session, stage, *, schema_sha256, **kwargs):
    return {'policy': loop.TERMINAL_POLICY, 'state': 'CONFIRMED_TERMINAL_NO_TOOL',
            'stage': stage, 'session': session, 'schema_sha256': schema_sha256,
            'original_run_id': 'easel-' + 'a' * 32,
            'native_evidence_sha256': 'b' * 64,
            'provider_finish': 'stop', 'native_stop': 'stop',
            'tool_call_count': 0, 'native_category': 'STRUCTURED_TERMINAL_REJECTED',
            'runtime_release': 'released', 'terminal_status': 'error'}


def _journal(attempt):
    root = Path(attempt['workspace']['path'])
    record = AttemptMaterialStore(root).read_recovery_record('semantic-planning-vnext')
    checkpoint = json.loads((root / 'planning/SEMANTIC_CHECKPOINT.json').read_text())
    return root, record, checkpoint


def _verify(attempt, result):
    root, journal, checkpoint = _journal(attempt)
    assert semantic_boundary_run.verify(
        root, result['plan'], checkpoint['scope']['mode'], result['script'],
        attempt=attempt)
    assert checkpoint['d2_decision_proof']['reviews']
    return root, journal, checkpoint


def test_b_nested_item_representation_normalized_without_semantic_repair(material_integration_env, tmp_path):
    attempt = _fresh_d2_attempt(material_integration_env)
    result = _run(attempt, _frozen_context(attempt), b_wrapper_probe=True)
    root, journal, checkpoint = _verify(attempt, result)
    assert journal['repair_count'] == 0
    assert checkpoint['b_normalizations']
    for key, receipt in checkpoint['b_normalizations'].items():
        assert key.startswith('B-')
        assert receipt['policy'] == 'planning-b-lossless-nested-items@1'
        raw = json.loads(checkpoint['wire_originals'][key])
        assert set(raw) == {'answers'} and set(raw['answers'][0]) == {'answers'}
    import shutil
    clone = tmp_path / 'b-normalized-tamper'
    shutil.copytree(root, clone, symlinks=True)
    copy = deepcopy(attempt)
    copy['workspace']['path'] = str(clone)
    tampered = json.loads((clone / 'planning/SEMANTIC_CHECKPOINT.json').read_text())
    first = next(iter(tampered['b_normalizations']))
    tampered['b_normalizations'][first]['normalized_sha256'] = '0' * 64
    (clone / 'planning/SEMANTIC_CHECKPOINT.json').write_text(json.dumps(tampered))
    with pytest.raises(ValueError, match='normalization'):
        semantic_boundary_run.verify(clone, result['plan'], checkpoint['scope']['mode'],
                                     result['script'], attempt=copy)


def test_native_terminal_zero_tool_new_operation_cold_resume(material_integration_env, monkeypatch, tmp_path):
    import app as web
    attempt = _fresh_d2_attempt(material_integration_env)
    context = _frozen_context(attempt)
    original = web._run_timed_creation_agent
    seen = []
    def fail_first_stage(phase, attempt_id, message, timeout, session_id, **options):
        if session_id.endswith('vnext-A-details-000') and phase == 'planning':
            seen.append(session_id)
            raise RuntimeError('Synthetic native terminal failure: the fake model did not call a tool')
        return original(phase, attempt_id, message, timeout, session_id, **options)
    monkeypatch.setattr(openclaw_delivery, 'inspect_planning_terminal_no_tool', _evidence)
    with patch.object(web, '_run_timed_creation_agent', fail_first_stage):
        result = _run(attempt, context)
        root, journal, checkpoint = _verify(attempt, result)
        assert len(seen) == 1
        assert journal['repair_count'] == 1
        assert journal['stage_regenerations']['A-details-000']['effective_key'] == 'repair-000'
        assert journal['calls']['A-details-000'].get('reply') is None
        assert journal['calls']['repair-000']['reply_sha256']
        assert checkpoint['capture']['A-details-000'].get('reply_sha256') is None
        assert checkpoint['wire_originals']['A-details-000'] is None
        assert checkpoint['stage_regenerations']['A-details-000']['original_failure']['reason'] == 'TERMINAL_NO_TOOL'
        assert checkpoint['d2_decision_proof']['reviews']
        # Restart against the same valid current Attempt: no old failed Run or
        # accepted model call may be dispatched again.
        before = {key: call.get('reply_sha256') for key, call in journal['calls'].items()}
        again = _run(attempt, context)
        assert again['plan'] == result['plan']
        assert len(seen) == 1
        _, resumed, _ = _journal(attempt)
        assert {key: call.get('reply_sha256') for key, call in resumed['calls'].items()} == before
    import shutil
    cloned = tmp_path / 'cold'
    shutil.copytree(root, cloned, symlinks=True)
    a = deepcopy(attempt)
    a['workspace']['path'] = str(cloned)
    altered = json.loads((cloned / 'planning/SEMANTIC_CHECKPOINT.json').read_text())
    altered['stage_regenerations']['A-details-000']['history'][0]['reply_sha256'] = 'f' * 64
    (cloned / 'planning/SEMANTIC_CHECKPOINT.json').write_text(json.dumps(altered))
    with pytest.raises(ValueError, match='regeneration|capture|lineage|reply'):
        semantic_boundary_run.verify(cloned, result['plan'], checkpoint['scope']['mode'],
                                     result['script'], attempt=a)


def test_model_invalid_frozen_source_regenerates_full_batch(material_integration_env):
    attempt = _fresh_d2_attempt(material_integration_env)
    result = _run(attempt, _frozen_context(attempt), stage_loop_probe='invalid_source')
    _, journal, checkpoint = _verify(attempt, result)
    assert journal['repair_count'] == 1
    assert journal['stage_regenerations']['A-details-000']['original_failure']['reason'] == 'INVALID_CREATIVE_SOURCE'
    assert journal['stage_regenerations']['A-details-000']['effective_key'] == 'repair-000'
    assert 'src_unknown_to_frozen_source_catalog' in journal['calls']['A-details-000']['reply']
    assert 'src_unknown_to_frozen_source_catalog' not in journal['calls']['repair-000']['reply']
    assert checkpoint['d2_decision_proof']['reviews']


def test_two_bad_source_generations_count_two_shared_repairs(material_integration_env):
    attempt = _fresh_d2_attempt(material_integration_env)
    result = _run(attempt, _frozen_context(attempt), stage_loop_probe='two_invalid_sources')
    _, journal, _ = _verify(attempt, result)
    rows = journal['stage_regenerations']['A-details-000']['history']
    assert [x['result'] for x in rows] == ['STAGE_REGENERATE', 'ACCEPT']
    assert journal['repair_count'] == 2
    assert [row['key'] for row in journal['repair_ledger']] == ['repair-000', 'repair-001']
    assert journal['stage_regenerations']['A-details-000']['effective_key'] == 'repair-001'


def test_two_stage_regeneration_failures_exhaust_only_current_batch(material_integration_env):
    attempt = _fresh_d2_attempt(material_integration_env)
    with pytest.raises(ValueError, match='two-attempt limit'):
        _run(attempt, _frozen_context(attempt), stage_loop_probe='always_invalid_sources')
    root = Path(attempt['workspace']['path'])
    record = AttemptMaterialStore(root).read_recovery_record('semantic-planning-vnext')
    assert record['repair_count'] == 2
    assert len(record['stage_regenerations']['A-details-000']['history']) == 2
    assert all(row['result'] == 'STAGE_REGENERATE' for row in
               record['stage_regenerations']['A-details-000']['history'])
    assert record['stage_regenerations']['A-details-000']['effective_key'] is None
    assert not (root / 'planning/SEMANTIC_CHECKPOINT.json').exists()


def test_bad_source_plus_other_wire_violation_must_stop(material_integration_env):
    attempt = _fresh_d2_attempt(material_integration_env)
    with pytest.raises((ValueError, RuntimeError), match='schema|Schema|Planning|recoverable|invalid'):
        _run(attempt, _frozen_context(attempt), stage_loop_probe='mixed_source')
    root = Path(attempt['workspace']['path'])
    record = AttemptMaterialStore(root).read_recovery_record('semantic-planning-vnext')
    assert record['repair_count'] == 0
    assert record['stage_regenerations'] == {}


def test_unproven_native_terminal_never_starts_new_operation(material_integration_env, monkeypatch):
    import app as web
    attempt = _fresh_d2_attempt(material_integration_env)
    context = _frozen_context(attempt)
    original = web._run_timed_creation_agent
    def failed(phase, attempt_id, message, timeout, session_id, **options):
        if session_id.endswith('vnext-A-details-000'):
            raise RuntimeError('Generic failure with no native rejection evidence')
        return original(phase, attempt_id, message, timeout, session_id, **options)
    monkeypatch.setattr(openclaw_delivery, 'inspect_planning_terminal_no_tool',
                        lambda *args, **kw: None)
    with patch.object(web, '_run_timed_creation_agent', failed):
        with pytest.raises(RuntimeError, match='Generic failure'):
            _run(attempt, context)
    record = AttemptMaterialStore(Path(attempt['workspace']['path'])).read_recovery_record(
        'semantic-planning-vnext')
    assert record['repair_count'] == 0
    assert record['stage_regenerations'] == {}
    assert not any(k.startswith('repair-') for k in record['calls'])
