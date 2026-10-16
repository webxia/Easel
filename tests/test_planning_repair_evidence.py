"""New-only Repair evidence wire, no model or paid calls."""
from copy import deepcopy
import pytest
from easel.integrations import planning_candidate_review as candidate
from easel.integrations import planning_wire as wire
from easel.integrations.planning_repair_evidence import RepairEvidenceProjection, POLICY


def fixture():
    support = {'type': 'object', 'additionalProperties': False,
      'properties': {'source': {'enum': ['source-text', 'source-nontext']},
                     'role': {'enum': ['context', 'authority']},
                     'quote': deepcopy(wire.SOURCE_QUOTE_SCHEMA)},
      'required': ['source', 'role', 'quote'], 'oneOf': [
        {'properties': {'source': {'enum': ['source-text']},
                        'role': {'enum': ['context', 'authority']},
                        'quote': {'type': 'string', 'minLength': 1, 'maxLength': 512}}},
        {'properties': {'source': {'enum': ['source-nontext']},
                        'role': {'enum': ['context']}, 'quote': {'type': 'null'}}}]}
    answer = {'type': 'object', 'additionalProperties': False,
      'properties': {'decision': {'const': 'ACCEPT'}, 'reason': {'type': 'string', 'maxLength': 256},
                     'support': {'type': 'array', 'minItems': 1, 'maxItems': 3,
                                 'items': {'$ref': '#/$defs/Support'}}},
      'required': ['decision', 'reason', 'support']}
    target = {'kind': 'candidate_answer', 'policy': candidate.POLICY,
              'path': ['question-0008'], 'answer_schema': answer, 'answer_defs': {'Support': support}}
    return candidate.patch_schema([target], slots=True)


def canonical():
    return {'target-0000': {'decision': 'ACCEPT', 'reason': 'model judgment', 'support': [
        {'source': 'source-nontext', 'role': 'context', 'quote': None},
        {'source': 'source-text', 'role': 'authority', 'quote': 'literal citation'}]}}


def test_evidence_ref_stable_and_lossless():
    schema = fixture()
    a, b = RepairEvidenceProjection(schema), RepairEvidenceProjection(schema)
    assert a.identity == b.identity
    assert a.identity['repair_evidence_policy'] == POLICY
    encoded = a.encode(canonical())
    assert a.decode_valid(encoded) == canonical()
    assert encoded == b.encode(canonical())
    assert set(encoded['target-0000']['support'][0]) == {'evidence_ref'}
    assert set(encoded['target-0000']['support'][1]) == {'evidence_ref', 'quote'}
    assert encoded['target-0000']['support'][1]['quote'] == 'literal citation'
    assert len(a.choices['target-0000']) == 3


def test_cross_batch_definition_collision_preserves_each_target_contract():
    first = fixture()
    second = deepcopy(first)
    def rebind(value):
        if isinstance(value, dict):
            return {k: rebind(v) for k, v in value.items()}
        if isinstance(value, list):
            return [rebind(v) for v in value]
        return value + '-other' if value in ('source-text', 'source-nontext') else value
    second['$defs'] = rebind(second['$defs'])
    targets = [{'kind': 'candidate_answer', 'policy': candidate.POLICY,
                'path': [f'question-{index:04d}'],
                'answer_schema': item['properties']['target-0000'],
                'answer_defs': item['$defs']} for index, item in enumerate((first, second))]
    combined = candidate.patch_schema(targets, slots=True)
    full = wire.project(combined, 'repair', atomic_framing=True)
    for index, target in enumerate(targets):
        single = wire.project(candidate.patch_schema([target], slots=True), 'repair', atomic_framing=True)
        assert full.schema['properties'][f'target-{index:04d}'] == single.schema['properties']['target-0000']
    value = {'target-0000': canonical()['target-0000'],
             'target-0001': rebind(canonical()['target-0000'])}
    codec = RepairEvidenceProjection(combined)
    encoded = codec.encode(value)
    assert codec.decode_valid(encoded) == value
    wrong_target = deepcopy(encoded)
    wrong_target['target-0001']['support'] = deepcopy(encoded['target-0000']['support'])
    assert codec.errors(wrong_target)
    with pytest.raises(ValueError):
        codec.decode_valid(wrong_target)


@pytest.mark.parametrize('mutation', ['unknown', 'wrong_target', 'text_without_quote',
                                       'nontext_fake_quote', 'role_fabrication', 'empty_quote'])
def test_evidence_ref_rejects_invalid_wires(mutation):
    codec = RepairEvidenceProjection(fixture())
    value = codec.encode(canonical())
    one, two = value['target-0000']['support']
    if mutation == 'unknown': one['evidence_ref'] = 'ev_unknown'
    elif mutation == 'wrong_target': value['target-0000']['support'] = [{'source': 'source-nontext', 'role': 'context', 'quote': None}]
    elif mutation == 'text_without_quote': two.pop('quote')
    elif mutation == 'nontext_fake_quote': one['quote'] = '8.0'
    elif mutation == 'role_fabrication': one['role'] = 'output_authority'
    else: two['quote'] = ''
    assert codec.errors(value)
    with pytest.raises(ValueError): codec.decode_valid(value)


def test_canonical_wrong_source_role_and_quote_not_laundered():
    codec = RepairEvidenceProjection(fixture())
    for mutation in ('wrong_role', 'fake_quote', 'empty_text'):
        raw = canonical()
        row = raw['target-0000']['support'][0 if mutation != 'empty_text' else 1]
        if mutation == 'wrong_role': row['role'] = 'output_authority'
        elif mutation == 'fake_quote': row['quote'] = '8.0'
        else: row['quote'] = ''
        with pytest.raises(ValueError): codec.encode(raw)


def test_evidence_ref_authority_contains_not_weakened():
    schema = fixture()
    answer = schema['properties']['target-0000']
    answer['allOf'] = [{'if': {'properties': {'decision': {'const': 'ACCEPT'}}},
                        'then': {'properties': {'support': {
                            'contains': {'type': 'object',
                                         'properties': {'role': {'enum': ['authority']}},
                                         'required': ['role']}, 'minContains': 1}}}}]
    codec = RepairEvidenceProjection(schema)
    valid = codec.encode(canonical())
    assert not codec.errors(valid)
    without_authority = deepcopy(valid)
    without_authority['target-0000']['support'] = without_authority['target-0000']['support'][:1]
    assert any(error['keyword'] == 'contains' for error in codec.errors(without_authority))
    with pytest.raises(ValueError): codec.decode_valid(without_authority)


def test_evidence_ref_message_choices_match_exact_wire_schema():
    from easel.integrations import semantic_boundary_run as owner
    from easel.integrations import planning_structured as structured
    schema = fixture()
    codec = RepairEvidenceProjection(schema)
    scope = {'inputs': {'confirmed': 'offline'},
             'transport': {'intake_policy': candidate.INTAKE_POLICY}}
    target = {'kind': 'candidate_answer', 'policy': candidate.POLICY,
              'path': ['question-0008'],
              'answer_schema': deepcopy(schema['properties']['target-0000']),
              'answer_defs': deepcopy(schema['$defs'])}
    # Message reconstruction uses the original frozen target format.
    message = owner.repair_message(scope, {}, [target], evidence_ref=True)
    assert 'evidence_choices_by_target' in message
    assert 'evidence_ref_policy' in message
    assert '每项support必须同时提交source、role、quote三个字段' not in message
    for ref in codec.choices['target-0000']:
        assert ref in message
    assert structured.request_for(codec.schema)['schemaSha256'] == codec.identity['wire_schema_sha256']


def test_local_ids_differential_on_real_frozen_seven_targets():
    import json
    from pathlib import Path
    from easel.integrations.planning_repair_evidence import LEGACY_POLICY
    root = Path.home() / '.local/share/easel/creator-task-evidence/2026-10-14-real-minimax-p0-medium-s5-r02/live/eval-runtime/hypit/workspaces'
    candidates = list(root.glob('*/*/materials/recoveries/semantic-planning-vnext.json'))
    if not candidates:
        pytest.skip('R02 live original evidence not mounted')
    journal = json.loads(candidates[0].read_text())
    schema = candidate.patch_schema(journal['repair']['targets'], slots=True)
    old = RepairEvidenceProjection(schema, policy=LEGACY_POLICY)
    new = RepairEvidenceProjection(schema)
    assert len(old.choices) == len(new.choices) == 7
    assert sum(map(len, old.choices.values())) == sum(map(len, new.choices.values())) == 1323
    for target in old.choices:
        assert set(old.choices[target].values()) == set(new.choices[target].values())
        assert len(set(new.choices[target])) == 189
    keys = list(new.choices)
    assert len(set(new.choices[keys[0]]) & set(new.choices[keys[1]])) == 189
    assert old.identity['wire_schema_sha256'] != new.identity['wire_schema_sha256']
    assert len(__import__('json').dumps(new.schema, separators=(',', ':'), ensure_ascii=False)) < len(__import__('json').dumps(old.schema, separators=(',', ':'), ensure_ascii=False))
    canonical = json.loads(journal['calls']['repair']['reply'])
    for idx in (0, 6):
        canonical[f'target-{idx:04d}']['support'][1]['quote'] = None
    canonical['target-0001']['support'][1]['role'] = 'context'
    a, b = old.encode(canonical), new.encode(canonical)
    assert old.decode_valid(a) == new.decode_valid(b) == canonical
    # Incorrect quote or nonexistent frozen ID remains reject-only.
    b[keys[0]]['support'][1]['evidence_ref'] = 'e999'
    assert new.errors(b)


def test_local_short_code_does_not_authorize_wrong_target():
    schema = fixture()
    other = deepcopy(schema['properties']['target-0000'])
    other['properties']['support']['items']['$ref'] = '#/$defs/OtherSupport'
    schema['$defs']['OtherSupport'] = deepcopy(schema['$defs']['Support'])
    schema['$defs']['OtherSupport']['properties']['source']['enum'] = ['source-other', 'source-second']
    schema['$defs']['OtherSupport']['oneOf'][0]['properties']['source']['enum'] = ['source-other']
    schema['$defs']['OtherSupport']['oneOf'][1]['properties']['source']['enum'] = ['source-second']
    schema['properties']['target-0001'] = other
    schema['required'].append('target-0001')
    codec = RepairEvidenceProjection(schema)
    assert set(codec.choices['target-0000'].values()) != set(codec.choices['target-0001'].values())
    original = canonical()
    original['target-0001'] = deepcopy(original['target-0000'])
    original['target-0001']['support'] = [
        {'source': 'source-second', 'role': 'context', 'quote': None},
        {'source': 'source-other', 'role': 'authority', 'quote': 'citation'}]
    encoded = codec.encode(original)
    assert codec.decode_valid(encoded) == original
    forged = deepcopy(encoded)
    foreign = next(ref for ref, triple in codec.choices['target-0001'].items()
                   if triple not in codec.choices['target-0000'].values())
    forged['target-0000']['support'][0]['evidence_ref'] = foreign
    assert codec.errors(forged)
