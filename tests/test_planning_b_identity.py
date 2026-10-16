"""B-only P0 explicit identity negative and conversion tests (offline)."""
from copy import deepcopy
import pytest
from easel.integrations import planning_wire as wire


def domain_schema():
    answer = {'type': 'object', 'additionalProperties': False,
              'properties': {'decision': {'type': 'string', 'enum': ['ACCEPT', 'CHALLENGE']},
                             'reason': {'type': 'string', 'minLength': 1, 'maxLength': 512}},
              'required': ['decision', 'reason']}
    return {'type': 'object', 'title': 'PlanningVisualReview', 'additionalProperties': False,
            'properties': {f'question-{i:04d}': deepcopy(answer) for i in range(8)},
            'required': [f'question-{i:04d}' for i in range(8)]}


def valid_output(codec):
    return {'answers': [
        {'question_id': f'question-{i:04d}', 'answer': {'decision': 'ACCEPT', 'reason': f'reason-{i}'}}
        for i in range(8)]}


def test_p0_frozen_identity_roundtrip_and_deterministic_identity():
    schema = domain_schema()
    codec = wire.b_identity_project(schema, 'B-000')
    original = valid_output(codec)
    canonical = codec.decode_valid(original)
    assert list(canonical) == schema['required']
    assert codec.encode(canonical) == original
    assert codec.identity == wire.b_identity_project(schema, 'B-000').identity
    assert codec.identity['b_identity_policy'] == wire.B_IDENTITY_POLICY


@pytest.mark.parametrize('mutation', ['missing', 'duplicate', 'unknown', 'extra', 'root_field',
                                      'bad_type', 'wrong_answer', 'wrong_root'])
def test_p0_rejects_structural_identity_and_field_mutations(mutation):
    codec = wire.b_identity_project(domain_schema(), 'B-001')
    raw = valid_output(codec)
    if mutation == 'missing':
        raw['answers'].pop()
    elif mutation == 'duplicate':
        raw['answers'][-1]['question_id'] = raw['answers'][0]['question_id']
    elif mutation == 'unknown':
        raw['answers'][0]['question_id'] = 'question-9999'
    elif mutation == 'extra':
        raw['answers'].append(deepcopy(raw['answers'][0]))
    elif mutation == 'root_field':
        raw['metadata'] = 'unrequested'
    elif mutation == 'bad_type':
        raw['answers'][0]['answer']['decision'] = 42
    elif mutation == 'wrong_answer':
        raw['answers'][0]['answer']['extra'] = 1
    else:
        raw = {'question-0000': raw['answers'][0]['answer']}
    assert codec.errors(raw)
    with pytest.raises(ValueError):
        codec.decode_valid(raw)


def test_p0_reordering_does_not_reassign_answers():
    codec = wire.b_identity_project(domain_schema(), 'B-002')
    raw = valid_output(codec)
    raw['answers'].reverse()
    output = codec.decode_valid(raw)
    assert output['question-0000']['reason'] == 'reason-0'
    assert output['question-0007']['reason'] == 'reason-7'


def test_p0_semantic_swap_is_not_explained_away_by_schema():
    codec = wire.b_identity_project(domain_schema(), 'B-003')
    raw = valid_output(codec)
    raw['answers'][0]['answer'], raw['answers'][1]['answer'] = (
        raw['answers'][1]['answer'], raw['answers'][0]['answer'])
    # Deliberately documented unresolved risk: structurally legal semantic misbinding.
    assert not codec.errors(raw)
    assert codec.decode_valid(raw)['question-0000']['reason'] == 'reason-1'


def test_p0_local_answer_error_remains_frozen_question_addressable():
    codec = wire.b_identity_project(domain_schema(), 'B-004')
    raw = valid_output(codec)
    raw['answers'][5]['answer']['decision'] = 'INVALID'
    assert {'path': ['question-0005', 'decision'], 'keyword': 'enum'} in codec.errors(raw)
    # Original local-invalid candidate is still available for the existing
    # strictly bounded repair; the identity map never invents replacement values.
    candidate = codec.decode_candidate(raw)
    assert candidate['question-0005']['decision'] == 'INVALID'
    assert candidate['question-0004']['decision'] == 'ACCEPT'


def test_legacy_b_codec_unchanged_and_p0_opt_in_is_distinct():
    schema = domain_schema()
    legacy = wire.project(schema, 'B-000', atomic_framing=True)
    p0 = wire.b_identity_project(schema, 'B-000')
    canonical = {f'question-{i:04d}': {'decision': 'ACCEPT', 'reason': f'reason-{i}'}
                 for i in range(8)}
    assert legacy.decode_valid(legacy.encode(canonical)) == canonical
    assert 'answers' not in legacy.schema['properties']
    assert 'answers' in p0.schema['properties']
    assert 'b_identity_policy' not in legacy.identity
    assert p0.identity['canonical_schema_sha256'] == legacy.identity['canonical_schema_sha256']


def test_p0_completed_capture_cold_replay_does_not_dispatch():
    import json
    from easel.integrations.planning_capture import capture
    codec = wire.b_identity_project(domain_schema(), 'B-010')
    original = valid_output(codec)
    calls, snapshots, dispatched = {}, [], []
    def save():
        snapshots.append(deepcopy(calls))
    def dispatch(key, message, session):
        dispatched.append(key)
        return json.dumps(original)
    message = 'frozen P0 B-010 input'
    result = capture(calls, 'B-010', message, 'new-p0-attempt-010', dispatch, save,
                     refuse_uncertain_reentry=True)
    assert codec.decode_valid(result) == codec.decode_valid(original)
    assert len(dispatched) == 1
    # Simulate cold restart from durable completed journal.
    recovered = deepcopy(snapshots[-1])
    assert codec.decode_valid(capture(recovered, 'B-010', message, 'new-p0-attempt-010',
                                       lambda *_: pytest.fail('duplicate model dispatch'),
                                       lambda: None, refuse_uncertain_reentry=True))
    assert len(dispatched) == 1
    with pytest.raises(ValueError, match='request identity changed'):
        capture(recovered, 'B-010', message + 'changed', 'new-p0-attempt-010',
                lambda *_: pytest.fail('rebinding dispatched'), lambda: None,
                refuse_uncertain_reentry=True)


@pytest.mark.parametrize('pending', ['REQUESTED', 'TRANSPORT_FAILED'])
def test_p0_pending_capture_cold_restart_is_fail_closed(pending):
    import hashlib
    from easel.creation_delivery import DeliveryExecutionUncertain
    from easel.integrations.planning_capture import capture
    message, session = 'frozen P0 B-011 input', 'new-p0-attempt-011'
    calls = {'B-011': {'request_sha256': hashlib.sha256(message.encode()).hexdigest(),
                      'session': session, 'result': pending, 'input_bytes': len(message.encode())}}
    with pytest.raises(DeliveryExecutionUncertain, match='terminal reconciliation'):
        capture(calls, 'B-011', message, session, lambda *_: pytest.fail('duplicate dispatch'),
                lambda: None, refuse_uncertain_reentry=True)
    assert calls['B-011']['result'] == pending
    assert 'reply' not in calls['B-011']


def test_p0_uncertain_first_dispatch_fails_closed_on_resume():
    from easel.creation_delivery import DeliveryExecutionUncertain
    from easel.integrations.planning_capture import capture
    calls, saved = {}, []
    def save():
        saved.append(deepcopy(calls))
    def interrupted(*_):
        raise DeliveryExecutionUncertain('connection unknown')
    with pytest.raises(DeliveryExecutionUncertain):
        capture(calls, 'B-012', 'frozen P0 B-012', 'new-p0-attempt-012', interrupted,
                save, refuse_uncertain_reentry=True)
    assert saved and saved[0]['B-012']['result'] == 'REQUESTED'
    assert calls['B-012']['result'] == 'TRANSPORT_FAILED'
    recovered = deepcopy(saved[-1])
    with pytest.raises(DeliveryExecutionUncertain, match='terminal reconciliation'):
        capture(recovered, 'B-012', 'frozen P0 B-012', 'new-p0-attempt-012',
                lambda *_: pytest.fail('second dispatch'), lambda: None,
                refuse_uncertain_reentry=True)


def test_p0_wire_local_error_and_root_error_admission_paths():
    from easel.integrations import planning_candidate_review as candidate
    codec = wire.b_identity_project(domain_schema(), 'B-005')
    reply = valid_output(codec)
    reply['answers'][3]['answer']['decision'] = 'INVALID'
    decoded = codec.decode_candidate(reply)
    assert [error['path'][0] for error in codec.errors(reply)] == ['question-0003']
    assert decoded['question-0003']['decision'] == 'INVALID'
    assert decoded['question-0002']['decision'] == 'ACCEPT'
    # The same frozen errors are localized by the *new* wire representation;
    # the old dynamic-root wire cannot inspect an unconverted P0 array.
    assert candidate is not None
    missing = valid_output(codec)
    missing['answers'] = missing['answers'][:-1]
    assert codec.errors(missing)[0]['path'] == []
    with pytest.raises(ValueError):
        codec.decode_candidate(missing)


def test_p0_new_message_uses_exact_frozen_tool_schema():
    from easel.integrations import planning_candidate_review as candidate
    from easel.integrations.planning_structured import request_for
    from easel.integrations.planning_request_view import restore
    import json
    batch = {'candidate_batch_limit': 8, 'candidate_policy': 'bounded-semantic-review@1',
             'questions': [{'question': i, 'kind': 'complete_obligation',
                            'candidate': {'responsibility': 'material'}, 'evidence': [0]}
                           for i in range(8)],
             'evidence': [{'id': 0, 'origin': 'confirmed_original', 'value': {'SCENES.md': 'x'}}],
             'response_schema': domain_schema(), 'candidate_bindings': {},
             'support_policy': None}
    # A real supported B batch has a richer semantic scope. This test pins
    # only the P0 request shape/reference; model semantics are validated elsewhere.
    rendered = candidate.message_for(batch, b_identity=True)
    doc = json.loads(rendered[rendered.index('\n{')+1:])
    schema = wire.b_identity_project(batch['response_schema'], 'B-000').schema
    request = request_for(schema)
    assert doc['input_projection']['tool_schema_sha256'] == request['schemaSha256']
    for variant in request['schema']['properties']['answers']['items']['oneOf']:
        key = variant['properties']['question_id']['const']
        answer = variant['properties']['answer']
        shape = doc['answer_shape_by_question'][key]
        assert shape['allowed_fields'] == sorted(answer['properties'])
        assert shape['required_fields'] == answer['required']
        assert shape['field_types'] == {k: v['type'] for k, v in answer['properties'].items() if 'type' in v}
    assert '不得写空字符串或item对象包装' in rendered
    assert restore(doc, schema, stage='B', expected_original_sha256=doc['input_projection']['original_sha256'])['response_schema'] == schema


def test_p0_terminal_reconciliation_reuses_original_without_dispatch():
    import hashlib, json
    from easel.integrations.planning_capture import capture
    session, key, message = 'new-p0-existing-session', 'B-021', 'same frozen request'
    calls = {key: {'request_sha256': hashlib.sha256(message.encode()).hexdigest(),
                   'session': session, 'result': 'TRANSPORT_FAILED'}}
    observed = []
    raw = valid_output(wire.b_identity_project(domain_schema(), key))
    def readonly(_key, _message, _session):
        observed.append((_key, _message, _session))
        return json.dumps(raw)
    returned = capture(calls, key, message, session,
                       lambda *_: pytest.fail('duplicate paid dispatch'), lambda: None,
                       refuse_uncertain_reentry=True, reconcile=readonly)
    assert returned == raw
    assert calls[key]['result'] == 'MODEL_COMPLETED'
    assert len(observed) == 1
    assert capture(calls, key, message, session,
                   lambda *_: pytest.fail('repeated paid dispatch'), lambda: None,
                   refuse_uncertain_reentry=True,
                   reconcile=lambda *_: pytest.fail('repeated terminal read')) == raw


def test_p0_unverified_terminal_reconciliation_keeps_pending_identity():
    import hashlib
    from easel.creation_delivery import DeliveryExecutionUncertain
    from easel.integrations.planning_capture import capture
    key, message, session = 'B-022', 'unverified original', 'new-p0-unverified-session'
    calls = {key: {'request_sha256': hashlib.sha256(message.encode()).hexdigest(),
                   'session': session, 'result': 'REQUESTED'}}
    def unresolved(*_):
        raise DeliveryExecutionUncertain('terminal receipt unavailable')
    with pytest.raises(DeliveryExecutionUncertain):
        capture(calls, key, message, session,
                lambda *_: pytest.fail('new dispatch forbidden'), lambda: None,
                refuse_uncertain_reentry=True, reconcile=unresolved)
    assert calls[key]['result'] == 'REQUESTED'
    assert 'reply' not in calls[key]


def test_p0_shared_repair_source_role_quote_contract_and_prompt():
    """Offline R02-shaped failures: missing null and cross-source role laundering."""
    from easel.integrations import planning_candidate_review as candidate
    from easel.integrations import semantic_boundary_run as owner
    answer = {'type': 'object', 'additionalProperties': False,
              'properties': {'support': {'type': 'array', 'minItems': 1,
                  'maxItems': 2, 'items': {'$ref': '#/$defs/Support'}},
                  'decision': {'const': 'ACCEPT'}, 'reason': {'type': 'string', 'maxLength': 128}},
              'required': ['decision', 'reason', 'support']}
    support = {'type': 'object', 'additionalProperties': False,
               'properties': {'source': {'enum': ['source-text', 'source-object']},
                              'role': {'enum': ['context', 'output_authority']},
                              'quote': deepcopy(wire.SOURCE_QUOTE_SCHEMA)},
               'required': ['source', 'role', 'quote'], 'oneOf': [
                 {'properties': {'source': {'const': 'source-text'},
                                 'role': {'const': 'context'},
                                 'quote': {'type': 'string', 'minLength': 1}}},
                 {'properties': {'source': {'const': 'source-object'},
                                 'role': {'const': 'context'},
                                 'quote': {'type': 'null'}}}]}
    targets = [{'kind': 'candidate_answer', 'policy': candidate.POLICY,
                'path': ['question-0020'], 'answer_schema': answer,
                'answer_defs': {'Support': support}}]
    schema = candidate.patch_schema(targets, slots=True)
    codec = wire.project(schema, 'repair', atomic_framing=True)
    valid = {'target-0000': {'decision': 'ACCEPT', 'reason': 'frozen source',
                            'support': [{'source': 'source-object', 'role': 'context',
                                         'quote': None}]}}
    assert not codec.errors(valid)
    for field, value in [('missing_quote', None), ('wrong_role', 'output_authority'),
                         ('text_null', None)]:
        invalid = deepcopy(valid)
        item = invalid['target-0000']['support'][0]
        if field == 'missing_quote': item.pop('quote')
        elif field == 'wrong_role': item['role'] = value
        else: item.update(source='source-text', quote=value)
        assert codec.errors(invalid), field
        with pytest.raises(ValueError): codec.decode_valid(invalid)
    scope = {'inputs': {'confirmed': 'offline-fixture'}, 'transport': {'intake_policy': candidate.INTAKE_POLICY}}
    rendered = owner.repair_message(scope, valid, targets)
    assert '每项support必须同时提交source、role、quote' in rendered
    assert 'quote必须显式填写JSON null' in rendered
    assert 'role与source必须满足同一Schema分支' in rendered
    assert '单次局部修复' in rendered
    assert 'target-0000' in rendered
    assert codec.decode_valid(valid) == valid


def test_p0_null_quote_guidance_matches_frozen_schema_and_does_not_change_validation():
    from easel.integrations import planning_candidate_review as candidate
    from easel.integrations import semantic_boundary_run as owner
    import json
    support = {'type': 'object', 'additionalProperties': False,
        'properties': {'source': {'enum': ['source-text', 'source-object']},
            'role': {'const': 'context'}, 'quote': deepcopy(wire.SOURCE_QUOTE_SCHEMA)},
        'required': ['source', 'role', 'quote'],
        'oneOf': [
            {'properties': {'source': {'enum': ['source-text']}, 'role': {'enum': ['context']},
                            'quote': {'type': 'string', 'minLength': 1, 'maxLength': 512}}},
            {'properties': {'source': {'enum': ['source-object']}, 'role': {'enum': ['context']},
                            'quote': {'type': 'null'}}}]}
    answer = {'type': 'object', 'additionalProperties': False,
        'properties': {'decision': {'const': 'ACCEPT'},
            'reason': {'type': 'string', 'maxLength': 128},
            'support': {'type': 'array', 'minItems': 1, 'maxItems': 2,
                        'items': {'$ref': '#/$defs/Support'}}},
        'required': ['decision', 'reason', 'support']}
    target = {'kind': 'candidate_answer', 'policy': candidate.POLICY,
              'path': ['question-0020'], 'answer_schema': answer, 'answer_defs': {'Support': support}}
    schema = wire.project(candidate.patch_schema([target], slots=True), 'repair', atomic_framing=True).schema
    assert owner.repair_quote_null_guidance(schema) == {'target-0000': ['source-object']}
    scope = {'inputs': {'confirmed': 'offline'},
             'transport': {'intake_policy': candidate.INTAKE_POLICY}}
    rendered = owner.repair_message(scope, {}, [target])
    assert 'quote_null_source_ids_by_target' in rendered
    assert 'source-object' in rendered
    codec = wire.project(candidate.patch_schema([target], slots=True), 'repair', atomic_framing=True)
    valid = {'target-0000': {'decision': 'ACCEPT', 'reason': 'grounded',
             'support': [{'source': 'source-object', 'role': 'context', 'quote': None}]}}
    assert not codec.errors(valid)
    invalid = deepcopy(valid)
    invalid['target-0000']['support'][0]['quote'] = '8.0'
    assert codec.errors(invalid)
