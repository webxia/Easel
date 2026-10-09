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
SELECTION_PROFILE = 'planning-selection@1'
TEXT_PROFILE = 'complete-json-container@1'
STRICT_PROFILE = 'strict-json-object@1'
MAX_ACTIONS = 16
MAX_DIAGNOSTICS = 32
RULES = {
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
    SELECTION_PROFILE: {'stages': ['A-selection'], 'channels': ['tool'],
                        'rules': ['selection-bgm-contains-echo@1']},
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


def _normalize_selection(value, schema):
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
        if profile == SELECTION_PROFILE:
            candidate, actions = _normalize_selection(candidate, schema)
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
