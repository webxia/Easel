"""Deterministic inbound JSON admission, not a workflow or semantic repair.

The caller owns terminal/run validation, persistence, domain validation and
repair authority. Only registered, channel-specific representation rules run
here. Raw inputs are never mutated or returned as diagnostic error bodies.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
import re

from jsonschema import Draft202012Validator

from easel.output_contract import output_decision
from easel.integrations.hypit.secrets import SecretRedactor

POLICY = 'model-output-admission@1'
RECEIPT = 'model-output-admission-receipt@1'
LEGACY_SELECTION_PROFILE = 'planning-selection@1'
SELECTION_PROFILE = 'planning-selection@2'
TEXT_PROFILE = 'complete-json-container@1'
STRICT_PROFILE = 'strict-json-object@1'
MAX_ACTIONS = 16
MAX_DIAGNOSTICS = 32
RULES = {
    'selection-root-bgm-contains-echo@1': {
        'stage': 'A-selection', 'channel': 'tool', 'path': ['contains'],
        'value': {'modality': 'bgm', 'necessity': 'required'},
        'guard': 'Exact active array rule; root echo only; entire remaining selection strictly valid',
    },
    'selection-bgm-contains-echo@1': {
        'stage': 'A-selection', 'channel': 'tool',
        'path': ['needs', '*', 'contains'],
        'value': {'modality': 'bgm', 'necessity': 'required'},
        'guard': 'Exact active array rule and valid identical outer header; no unknown children',
    },
    'complete-json-fence@1': {
        'channels': ['text-json', 'file-json'],
        'guard': 'Entire input is one closed json fence with whitespace only outside; parse every byte inside',
    },
}
PROFILES = {
    LEGACY_SELECTION_PROFILE: {'stages': ['A-selection'], 'channels': ['tool'],
                        'rules': ['selection-bgm-contains-echo@1']},
    SELECTION_PROFILE: {'stages': ['A-selection'], 'channels': ['tool'],
                        'rules': ['selection-bgm-contains-echo@1', 'selection-root-bgm-contains-echo@1']},
    TEXT_PROFILE: {'stages': None, 'channels': ['text-json', 'file-json'],
                   'rules': ['complete-json-fence@1']},
    STRICT_PROFILE: {'stages': None, 'channels': ['tool', 'text-json', 'file-json'], 'rules': []},
}
_MUSIC_RULE = {'type': 'object', 'properties': {
    'modality': {'const': 'bgm'}, 'necessity': {'const': 'required'}},
    'required': ['modality', 'necessity']}


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical_json(value).encode('utf-8')).hexdigest()


def policy_identity(profile):
    if profile not in PROFILES:
        raise ValueError('Unknown output admission profile')
    definition = PROFILES[profile]
    return {'policy': POLICY, 'profile': profile,
            'rules_sha256': digest({'profile': definition,
                'rules': {key: RULES[key] for key in definition['rules']},
                'max_actions': MAX_ACTIONS, 'max_diagnostics': MAX_DIAGNOSTICS})}


class AdmissionError(ValueError):
    """Safe fixed classification; never includes raw input or an unknown key."""


def _parse_object(text):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise AdmissionError('DUPLICATE_JSON_KEY')
            if SecretRedactor.contains_secret(item, parent_key=key):
                raise AdmissionError('UNSAFE_JSON_CONTENT')
            value[key] = item
        return value
    def number(text):
        value = float(text)
        if not math.isfinite(value):
            raise AdmissionError('NONFINITE_JSON_NUMBER')
        return value
    def constant(_):
        raise AdmissionError('NONFINITE_JSON_NUMBER')
    try:
        value = json.loads(text, object_pairs_hook=pairs,
                           parse_float=number, parse_constant=constant)
        if not isinstance(value, dict):
            raise AdmissionError('EXPECTED_JSON_OBJECT')
        if SecretRedactor.contains_secret(value):
            raise AdmissionError('UNSAFE_JSON_CONTENT')
        canonical_json(value).encode('utf-8')  # Also reject lone escaped surrogates.
        return value
    except AdmissionError:
        raise
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise AdmissionError('INVALID_COMPLETE_JSON') from None


def schema_diagnostics(value, schema):
    rows, total = [], 0
    for error in Draft202012Validator(schema).iter_errors(value):
        total += 1
        if len(rows) < MAX_DIAGNOSTICS:
            row = {'path': list(error.absolute_path),
                   'schema_path': list(error.absolute_schema_path),
                   'constraint': error.validator}
            if error.validator in {'maxLength', 'minLength', 'maxItems', 'minItems'}:
                row.update(limit=error.validator_value, actual_length=len(error.instance))
            rows.append(row)
    return {'items': rows, 'total': total, 'omitted': total - len(rows)}


def _normalize_selection(value, schema, *, root_echo=False):
    result, actions = deepcopy(value), []
    array = schema.get('properties', {}).get('needs', {})
    item = array.get('items', {})
    if (array.get('type') != 'array' or array.get('contains') != _MUSIC_RULE
            or not isinstance(item, dict) or item.get('type') != 'object'
            or item.get('additionalProperties') is not False
            or 'contains' in item.get('properties', {})):
        return result, actions
    rows = result.get('needs')
    if not isinstance(rows, list) or len(rows) > MAX_ACTIONS:
        return result, actions
    # A root echo is excluded only in isolation. Never combine it with header
    # cleanup or let it stand in for a missing/optional BGM candidate.
    if root_echo and 'contains' in result:
        rule = 'selection-root-bgm-contains-echo@1'
        echo = result['contains']
        candidate = {key: item for key, item in result.items() if key != 'contains'}
        if (schema.get('type') == 'object' and schema.get('additionalProperties') is False
                and 'contains' not in schema.get('properties', {})
                and echo == RULES[rule]['value']
                and Draft202012Validator(schema).is_valid(candidate)):
            return candidate, [{'rule': rule, 'operation': 'exclude_redundant_field',
                'path': ['contains'], 'old_value_sha256': digest(echo),
                'evidence': 'active-array-rule-and-entire-valid-selection'}]
        return result, actions
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or 'contains' not in row:
            continue
        echo = row['contains']
        expected = RULES['selection-bgm-contains-echo@1']['value']
        if (not isinstance(echo, dict) or echo != expected
                or any(row.get(key) != wanted for key, wanted in expected.items())):
            continue
        candidate = {key: item for key, item in row.items() if key != 'contains'}
        # Unknown siblings, missing fields, invalid scope and type errors cannot
        # be hidden by calling this duplicate a harmless echo.
        if not Draft202012Validator(item).is_valid(candidate):
            continue
        actions.append({'rule': 'selection-bgm-contains-echo@1',
                        'operation': 'exclude_redundant_field',
                        'path': ['needs', index, 'contains'],
                        'old_value_sha256': digest(echo),
                        'evidence': 'active-array-rule-and-identical-valid-header'})
        result['needs'][index] = candidate
    return result, actions


def admit_json(raw, schema, *, stage, channel, binding, profile=STRICT_PROFILE,
               max_bytes=8 * 1024 * 1024):
    """Return candidate + reproducible receipt; a REJECT is never permission.

    This is syntax/representation admission only. Even ACCEPT/NORMALIZE must
    pass the caller's semantic, identity and domain checks. The owner may mark
    schema-invalid but safely reviewable leaves BOUNDED_REPAIR under its
    existing policy; this module never dispatches or allocates repair budget.
    """
    identity = policy_identity(profile)
    definition = PROFILES[profile]
    if (channel not in definition['channels'] or
            definition['stages'] is not None and stage not in definition['stages']):
        raise ValueError('Output admission channel or stage does not match profile')
    if not isinstance(binding, dict) or SecretRedactor.contains_secret(binding):
        raise ValueError('Output admission binding is unsafe')
    if type(max_bytes) is not int or max_bytes <= 0:
        raise ValueError('Output admission size limit is invalid')
    Draft202012Validator.check_schema(schema)
    receipt = {'schema': RECEIPT, 'policy': identity, 'stage': stage,
               'channel': channel, 'binding': deepcopy(binding),
               'wire_schema_sha256': digest(schema), 'raw_sha256': None,
               'normalized_sha256': None, 'actions': [],
               'raw_errors': None, 'remaining_errors': None}
    candidate, text = None, raw
    try:
        if not isinstance(raw, str):
            raise AdmissionError('EXPECTED_TEXT_PAYLOAD')
        data = raw.encode('utf-8')
        if len(data) > max_bytes:
            raise AdmissionError('PAYLOAD_SIZE_LIMIT')
        receipt['raw_sha256'] = hashlib.sha256(data).hexdigest()
        if SecretRedactor.contains_secret(raw):
            raise AdmissionError('UNSAFE_JSON_CONTENT')
        if profile == TEXT_PROFILE:
            match = re.fullmatch(r'\s*```json\r?\n([\s\S]*?)\r?\n```\s*', raw)
            if match:
                text = match[1]
        original = _parse_object(text)
        if text != raw:
            receipt['actions'].append({'rule': 'complete-json-fence@1',
                'operation': 'unwrap_complete_container', 'path': [],
                'old_value_sha256': receipt['raw_sha256']})
        receipt['raw_errors'] = schema_diagnostics(original, schema)
        candidate = deepcopy(original)
        if profile in {LEGACY_SELECTION_PROFILE, SELECTION_PROFILE}:
            candidate, actions = _normalize_selection(candidate, schema,
                root_echo=profile == SELECTION_PROFILE)
            receipt['actions'].extend(actions)
        receipt['normalized_sha256'] = digest(candidate)
        receipt['remaining_errors'] = schema_diagnostics(candidate, schema)
        outcome = ('REJECT' if receipt['remaining_errors']['total'] else
                   'NORMALIZE' if receipt['actions'] else 'ACCEPT')
        code = 'SCHEMA_INVALID' if outcome == 'REJECT' else 'REPRESENTATION_VALID'
    except (AdmissionError, UnicodeError) as exc:
        outcome, code = 'REJECT', str(exc) if isinstance(exc, AdmissionError) else 'INVALID_UTF8'
        candidate = None
        receipt['actions'] = []  # Never claim a transformation of unsafe data.
    receipt['decision'] = output_decision(stage, outcome, code,
        policy_revision=POLICY)
    receipt['decision']['input_sha256'] = receipt['raw_sha256']
    return {'candidate': candidate, 'receipt': receipt}

# Classification is pure; only the existing Planning Owner can spend on Repair.
DETAILS_RECOVERY_POLICY = 'planning-a-details-root-admission@1'


def classify_details_wire(raw, schema, *, binding):
    """Describe exact representation errors without inventing missing semantics.

    The only current pre-assembly repair candidate is an omitted root
    unresolved array when every other Slot/Claim passes the original Schema.
    All other violations remain reject-only.
    """
    admitted = admit_json(raw, schema, stage='A-details', channel='tool',
                          binding=binding, profile=STRICT_PROFILE)
    receipt = admitted['receipt']
    original = admitted['candidate']
    decision = receipt['decision']['outcome']
    errors = [] if not isinstance(original, dict) else list(
        Draft202012Validator(schema).iter_errors(original))
    permitted = (decision == 'REJECT' and isinstance(original, dict)
        and set(original) == {'slots'}
        and schema.get('required') == ['slots', 'unresolved']
        and len(errors) == 1 and errors[0].validator == 'required'
        and not list(errors[0].absolute_path)
        and 'unresolved' in errors[0].validator_value
        and 'unresolved' in schema.get('properties', {}))
    if permitted:
        decision = 'BOUNDED_REPAIR'
    return {'policy': DETAILS_RECOVERY_POLICY, 'receipt': receipt,
            'decision': decision,
            'repair_path': ['unresolved'] if permitted else None,
            'original_sha256': receipt['raw_sha256'],
            'schema_sha256': digest(schema)}


def details_repair_schema(schema):
    """Exactly one model-authored field; never substitute a default."""
    if (schema.get('type') != 'object'
            or schema.get('additionalProperties') is not False
            or schema.get('required') != ['slots', 'unresolved']
            or set(schema.get('properties', {})) != {'slots', 'unresolved'}):
        raise ValueError('Unexpected A-details root contract')
    field = deepcopy(schema['properties']['unresolved'])
    field.pop('default', None)
    result = {'type': 'object', 'additionalProperties': False,
              'properties': {'unresolved': field}, 'required': ['unresolved']}
    Draft202012Validator.check_schema(result)
    return result


def bind_details_repair(original, supplement, schema):
    """Recombine under the original strict Schema, preserving every Slot."""
    if not isinstance(original, dict) or set(original) != {'slots'}:
        raise ValueError('No exact original incomplete A-details to repair')
    Draft202012Validator(details_repair_schema(schema)).validate(supplement)
    repaired = {**deepcopy(original), 'unresolved': deepcopy(supplement['unresolved'])}
    Draft202012Validator(schema).validate(repaired)
    if repaired['slots'] != original['slots']:
        raise ValueError('A-details repaired Slot identity changed')
    return repaired
