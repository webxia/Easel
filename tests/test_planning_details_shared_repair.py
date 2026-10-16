"""Current New-Only single-owner A-details repair: real R04 origin and native cold replay.

No provider calls. The fake external reply represents the model *explicitly*
authoring the missing field, never a Program default or rewritten old evidence.
"""
import json
import hashlib
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import ValidationError

from easel import output_admission
from easel.integrations import semantic_boundary_run
from easel.materials.store import AttemptMaterialStore
from tests.test_creation_preparation import _current_vnext_planning_executor
from tests.test_planning_d2_owner_integration import _fresh_d2_attempt, _frozen_context
from tests.test_material_integration import material_integration_env


def test_r04_real_raw_only_has_explicit_root_repair_classification():
    original = (Path.home() / '.local/share/easel/creator-task-evidence'
                / '2026-10-15-planning-m31-actual-owner-eval-r04/live')
    journal_paths = list((original / 'eval-runtime/hypit/workspaces').glob(
        '*/*/materials/recoveries/semantic-planning-vnext.json'))
    if not journal_paths:
        pytest.skip('Prior real MiniMax R04 archive is not mounted')
    from easel.integrations import planning_input_view as views, planning_staged_proposal as staged
    from easel.integrations import planning_creative_authority as creative, planning_wire as wire
    before = journal_paths[0].read_bytes()
    journal = json.loads(before)
    scope = journal['scope']
    view = views.PlanningInputView(scope['inputs'], scope['catalog'])
    compiler = staged._read_only_staged(semantic_boundary_run.query_schema(scope))
    bridge = creative.OpaqueHeaderBridge(view.codec, compiler,
                                         scope['creative_authority']['envelope'])
    selected, _ = bridge.decode(json.loads(journal['calls']['A-selection']['reply']), bridge.identity)
    carrier = creative.BatchedVisualClaimCarrier(
        compiler, selected, scope['creative_authority']['envelope'],
        source_bridge_identity=bridge.identity, source_codec=view.codec)
    schema = wire.project(carrier.batches['A-details-000'], 'A-details-000',
                          atomic_framing=True).schema
    raw = journal['calls']['A-details-000']['reply']
    outcome = output_admission.classify_details_wire(
        raw, schema, binding={'attempt_id': scope['attempt_id'], 'stage': 'A-details-000'})
    assert outcome['decision'] == 'BOUNDED_REPAIR'
    assert outcome['repair_path'] == ['unresolved']
    assert hashlib.sha256(raw.encode()).hexdigest() == outcome['original_sha256']
    patch_schema = output_admission.details_repair_schema(schema)
    assert set(patch_schema['properties']) == {'unresolved'}
    assert 'default' not in patch_schema['properties']['unresolved']
    with pytest.raises(ValidationError):
        output_admission.bind_details_repair(json.loads(raw), {}, schema)
    with pytest.raises(ValidationError):
        output_admission.bind_details_repair(json.loads(raw),
            {'unresolved': [], 'slots': {}}, schema)
    repair = output_admission.bind_details_repair(json.loads(raw),
                                                   {'unresolved': []}, schema)
    assert repair['slots'] == json.loads(raw)['slots']
    assert journal_paths[0].read_bytes() == before




def test_one_attempt_shared_repair_has_three_durable_slots():
    from easel.integrations.semantic_boundary_run import reserve_repair_slot
    state = {'repair_ledger': [], 'repair_count': 0, 'repair_used': False}
    persisted = []
    def save():
        persisted.append(deepcopy(state))
    stages = ['wire:A-details-000', 'B-cross-batch', 'semantic']
    rows = [reserve_repair_slot(state, stage, {'origin': stage}, save)
            for stage in stages]
    assert [row['key'] for row in rows] == ['repair-000', 'repair-001', 'repair-002']
    assert state['repair_count'] == 3 and len(persisted) == 3
    assert reserve_repair_slot(state, stages[0], {'origin': stages[0]}, save) == rows[0]
    assert len(persisted) == 3  # A resumed request is never re-reserved.
    with pytest.raises(ValueError, match='exhausted'):
        reserve_repair_slot(state, 'another', {'origin': 'another'}, save)
    assert state['repair_count'] == 3 and len(persisted) == 3
    with pytest.raises(ValueError, match='target|reservation'):
        reserve_repair_slot(state, stages[0], {'origin': 'tampered'}, save)
    assert state['repair_ledger'] == rows





def test_uncertain_original_repair_never_redispatches():
    from easel.creation_delivery import DeliveryExecutionUncertain
    from easel.integrations.planning_capture import capture
    message = 'frozen pending repair request'
    session = 'semantic-fa-frozen-vnext-repair-000'
    calls = {'repair-000': {'request_sha256': hashlib.sha256(message.encode()).hexdigest(),
                            'session': session, 'input_bytes': len(message.encode()),
                            'result': 'REQUESTED'}}
    sent = []
    with pytest.raises(DeliveryExecutionUncertain):
        capture(calls, 'repair-000', message, session,
                lambda *args: sent.append(args), lambda: None,
                refuse_uncertain_reentry=True)
    assert not sent
    assert calls['repair-000']['result'] == 'REQUESTED'

def test_native_wire_then_semantic_repair_share_ledger(material_integration_env):
    attempt = _fresh_d2_attempt(material_integration_env)
    context = _frozen_context(attempt)
    result = _current_vnext_planning_executor(
        attempt, context, creative_claims=True, d2_review=True,
        wire_root_probe=True, creative_semantic_probe=True)
    root = Path(attempt['workspace']['path'])
    journal = AttemptMaterialStore(root).read_recovery_record('semantic-planning-vnext')
    checkpoint = json.loads((root / 'planning/SEMANTIC_CHECKPOINT.json').read_text())
    assert journal['repair_count'] == 2
    assert [row['key'] for row in journal['repair_ledger']] == ['repair-000', 'repair-001']
    assert journal['repair_ledger'][0]['stage'] == 'wire:A-details-000'
    assert journal['repair_ledger'][1]['stage'] == 'semantic'
    assert checkpoint['candidate_repairs'][0]['stage'] == 'semantic'
    assert semantic_boundary_run.verify(root, result['plan'], checkpoint['scope']['mode'],
                                        result['script'], attempt=attempt)

def test_native_3_repair_ledger_and_cold_replay(material_integration_env, tmp_path):
    attempt = _fresh_d2_attempt(material_integration_env)
    context = _frozen_context(attempt)
    result = _current_vnext_planning_executor(
        attempt, context, creative_claims=True, d2_review=True, wire_root_probe=True)
    root = Path(attempt['workspace']['path'])
    journal = AttemptMaterialStore(root).read_recovery_record('semantic-planning-vnext')
    checkpoint = json.loads((root / 'planning/SEMANTIC_CHECKPOINT.json').read_text())
    assert journal['repair_used']
    assert journal['repair_count'] == 1
    assert len(journal['repair_ledger']) == 1
    assert journal['repair_ledger'][0]['stage'] == 'wire:A-details-000'
    assert journal['repair_ledger'][0]['key'] == 'repair-000'
    assert 'unresolved' not in json.loads(journal['calls']['A-details-000']['reply'])
    assert json.loads(journal['calls']['repair-000']['reply']) == {'unresolved': []}
    assert checkpoint['wire_repairs']['A-details-000']['patch_reply_sha256'] == (
        journal['calls']['repair-000']['reply_sha256'])
    assert checkpoint['d2_decision_proof']['reviews']
    assert semantic_boundary_run.verify(root, result['plan'], checkpoint['scope']['mode'],
                                        result['script'], attempt=attempt)
    raw_sha = journal['calls']['A-details-000']['reply_sha256']
    keys = {key: row['reply_sha256'] for key, row in journal['calls'].items()}
    again = _current_vnext_planning_executor(
        attempt, context, creative_claims=True, d2_review=True, wire_root_probe=True)
    assert again['plan'] == result['plan']
    after = AttemptMaterialStore(root).read_recovery_record('semantic-planning-vnext')
    assert after['calls']['A-details-000']['reply_sha256'] == raw_sha
    assert {key: row['reply_sha256'] for key, row in after['calls'].items()} == keys
    import shutil
    clone = tmp_path / 'frozen'
    shutil.copytree(root, clone, symlinks=True)
    copied = deepcopy(attempt)
    copied['workspace']['path'] = str(clone)
    tampered = json.loads((clone / 'planning/SEMANTIC_CHECKPOINT.json').read_text())
    tampered['wire_repairs']['A-details-000']['effective_wire_sha256'] = 'f' * 64
    (clone / 'planning/SEMANTIC_CHECKPOINT.json').write_text(
        json.dumps(tampered, ensure_ascii=False))
    with pytest.raises(ValueError, match='A-details repaired'):
        semantic_boundary_run.verify(clone, result['plan'], checkpoint['scope']['mode'],
                                     result['script'], attempt=copied)
