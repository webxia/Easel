"""Attempt-local receipts for existing model consumers, not execution authority.

The existing Delivery adapter must validate the original run before capture.
Old caches/calls retain their parser. New policies are pinned before dispatch;
replay validates safe raw data rather than trusting a normalized flag. Domain
validators still decide Truth/Material acceptance and never use these receipts
as a substitute for evidence, authorization or readiness.
"""
from __future__ import annotations

from copy import deepcopy
from easel import output_admission as admission

POLICY = 'stage-output-receipts@1'
OBJECT_SCHEMA = {'type': 'object'}


class OutputReceiptError(RuntimeError):
    """Integrity/storage failure, not an instruction to ask a model to repair."""


SPEC_POLICY = 'stage-output-receipts@2'
SPEC_REVISION = 'model-result-spec@1'


class ModelResultRejected(ValueError):
    """Captured model rejection; not a local storage failure or repair authority."""

    def __init__(self, capture):
        receipt = capture.get('receipt', {})
        self.code = receipt.get('decision', {}).get('code', 'MODEL_OUTPUT_REJECTED')
        self.stage = receipt.get('stage')
        self.capture_key = capture.get('key')
        self.diagnostics = deepcopy(receipt.get('remaining_errors', {}))
        super().__init__('Model result rejected: ' + self.code)


def result_spec(*, stage, channel, profile, schema, max_bytes, validator, derivation):
    """Fix the actual JSON consumer contract before its first dispatch."""
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import SchemaError
    if (not isinstance(stage, str) or not stage or channel not in {'tool', 'text-json', 'file-json'}
            or type(max_bytes) is not int or not 0 < max_bytes <= 8 * 1024 * 1024
            or not isinstance(validator, str) or not validator
            or not isinstance(derivation, str) or not derivation):
        raise OutputReceiptError('Invalid result specification')
    try:
        Draft202012Validator.check_schema(schema)
        admission.canonical_json(schema).encode('utf-8')
        admission.policy_identity(profile)
    except (ValueError, TypeError, UnicodeError, SchemaError) as exc:
        raise OutputReceiptError('Invalid result schema or admission profile') from exc
    return {'schema': SPEC_REVISION, 'stage': stage, 'channel': channel,
            'format': 'json', 'profile': profile, 'result_schema': deepcopy(schema),
            'result_schema_sha256': admission.digest(schema), 'max_bytes': max_bytes,
            'validator': validator, 'derivation': derivation}


def _result_schema(policy):
    return policy['spec']['result_schema'] if policy['schema'] == SPEC_POLICY else OBJECT_SCHEMA


def require_accepted_candidate(capture):
    """Formal consumption; stage Owners retain their own safe repair paths."""
    if capture['receipt']['decision']['outcome'] not in {'ACCEPT', 'NORMALIZE'}:
        raise ModelResultRejected(capture)
    if not isinstance(capture['candidate'], dict):
        raise OutputReceiptError('Accepted output is not a complete object')
    return deepcopy(capture['candidate'])


def record_derivation(store, capture, *, revision, input_binding, output, require_existing=False):
    """Persist deterministic full output AFTER the caller's domain validation."""
    require_accepted_candidate(capture)
    value = {'schema': 'model-result-derivation@1', 'revision': revision,
             'capture_key': capture['key'],
             'capture_receipt_sha256': admission.digest(capture['receipt']),
             'input_binding': deepcopy(input_binding), 'output': deepcopy(output),
             'output_sha256': admission.digest(output)}
    key = 'output-derivation-' + admission.digest({'capture': capture['key'], 'revision': revision})
    saved = read_record(store, key)
    if saved is not None and saved != value:
        raise OutputReceiptError('Result derivation or frozen inputs changed')
    if saved is None:
        if require_existing:
            raise OutputReceiptError('Result derivation is missing; recover from the original capture locally')
        _write(store, key, value)
    return {'key': key, 'sha256': admission.digest(value)}


def policy_key(stage, logical_id):
    return 'output-policy-' + admission.digest({'stage': stage, 'logical_id': logical_id})


def read_record(store, key):
    try:
        return store.read_recovery_record(key)
    except (OSError, ValueError) as exc:
        raise OutputReceiptError('Output receipt storage is invalid; do not request model repair') from exc


def execution_session(policy):
    base = policy['identity']['binding']['session']
    return base if policy['mode'] == 'legacy' else base + '-ad-' + admission.digest(policy)[:12]


def _write(store, key, value):
    try:
        store.write_recovery_record(key, value)
    except (OSError, ValueError) as exc:
        raise OutputReceiptError('Output receipt persistence failed; recover locally') from exc


def pin_policy(store, *, stage, logical_id, binding, profile, legacy_started=False, spec=None):
    key = policy_key(stage, logical_id)
    identity = {'stage': stage, 'logical_id': logical_id, 'binding': deepcopy(binding)}
    current_policy = admission.policy_identity(profile)
    if spec is not None:
        if not isinstance(spec, dict) or spec != result_spec(
                stage=stage, channel=spec.get('channel'), profile=profile,
                schema=spec.get('result_schema'), max_bytes=spec.get('max_bytes'),
                validator=spec.get('validator'), derivation=spec.get('derivation')):
            raise OutputReceiptError('Result specification changed')
        if legacy_started:
            raise OutputReceiptError('An existing run cannot acquire a new result specification')
    receipt_schema = SPEC_POLICY if spec is not None else POLICY
    saved = read_record(store, key)
    prefix = 'output-capture-' + key.removeprefix('output-policy-')[:24] + '-'
    captures = (store.has_capture_prefix(prefix) if hasattr(store, 'has_capture_prefix')
                else any((store.materials_root / 'recoveries').glob(prefix + '*.json')))
    if captures and (not isinstance(saved, dict) or saved.get('mode') != 'current'):
        raise OutputReceiptError('Existing captures lost their pinned consumer policy')
    if saved is None:
        saved = {'schema': receipt_schema, 'identity': identity,
                 'mode': 'legacy' if legacy_started else 'current',
                 'policy': None if legacy_started else current_policy,
                 **({'spec': deepcopy(spec)} if spec is not None else {})}
        _write(store, key, saved)
    if (not isinstance(saved, dict) or set(saved) != ({'schema', 'identity', 'mode', 'policy'} | ({'spec'} if spec is not None else set()))
            or saved['schema'] != receipt_schema or saved['identity'] != identity
            or spec is not None and saved.get('spec') != spec
            or saved['mode'] not in {'legacy', 'current'}
            or saved['policy'] != (None if saved['mode'] == 'legacy' else current_policy)):
        raise OutputReceiptError('Output consumer policy or input identity changed')
    return {'key': key, **saved}


def _capture_identity(policy, request_sha256, channel, max_bytes):
    if policy['mode'] != 'current':
        raise OutputReceiptError('Legacy output cannot obtain a new receipt')
    if policy['schema'] == SPEC_POLICY and (channel != policy['spec']['channel'] or max_bytes != policy['spec']['max_bytes']):
        raise OutputReceiptError('Capture carrier or limits differ from the pinned specification')
    return {'policy_key': policy['key'], 'policy_sha256': admission.digest(policy),
            'request_sha256': request_sha256, 'channel': channel, 'max_bytes': max_bytes}


def capture_key(policy, request_sha256, channel, max_bytes):
    prefix = policy['key'].removeprefix('output-policy-')[:24]
    return 'output-capture-' + prefix + '-' + admission.digest(_capture_identity(policy, request_sha256, channel, max_bytes))


def _admit(policy, request_sha256, raw, channel, max_bytes):
    return admission.admit_json(raw, _result_schema(policy), stage=policy['identity']['stage'],
        channel=channel, profile=policy['policy']['profile'], max_bytes=max_bytes,
        binding={**policy['identity']['binding'], 'consumer_policy_sha256': admission.digest(policy),
                 'request_sha256': request_sha256})


def load_capture(store, policy, request_sha256, *, channel, max_bytes):
    key = capture_key(policy, request_sha256, channel, max_bytes)
    saved = read_record(store, key)
    if saved is None:
        return None
    identity = _capture_identity(policy, request_sha256, channel, max_bytes)
    if (not isinstance(saved, dict) or set(saved) != {'schema', 'identity', 'raw', 'admission'}
            or saved['schema'] != policy['schema'] or saved['identity'] != identity
            or not isinstance(saved['admission'], dict)
            or set(saved['admission']) != {'candidate', 'receipt'}
            or not isinstance(saved['admission']['receipt'], dict)
            or saved['raw'] is not None and not isinstance(saved['raw'], str)):
        raise OutputReceiptError('Saved output capture identity changed')
    if saved['raw'] is not None:
        reconstructed = _admit(policy, request_sha256, saved['raw'], channel, max_bytes)
        if reconstructed != saved['admission'] or reconstructed['candidate'] is None:
            raise OutputReceiptError('Saved output raw/candidate/receipt changed')
    else:
        # Unsafe/unparseable data is deliberately not retained. Such a receipt
        # can only remain a rejection; it can never become a usable candidate.
        value = saved.get('admission', {})
        receipt = value.get('receipt', {}) if isinstance(value, dict) else {}
        if (value.get('candidate') is not None
                or receipt.get('schema') != admission.RECEIPT
                or receipt.get('policy') != policy['policy']
                or receipt.get('binding') != {**policy['identity']['binding'],
                    'consumer_policy_sha256': admission.digest(policy), 'request_sha256': request_sha256}
                or receipt.get('stage') != policy['identity']['stage']
                or receipt.get('channel') != channel
                or receipt.get('wire_schema_sha256') != admission.digest(_result_schema(policy))
                or receipt.get('decision', {}).get('outcome') != 'REJECT'):
            raise OutputReceiptError('Rejected output receipt cannot be promoted')
    return {'key': key, **deepcopy(saved['admission'])}


def capture_result(store, policy, request_sha256, raw, *, channel, max_bytes):
    existing = load_capture(store, policy, request_sha256, channel=channel, max_bytes=max_bytes)
    value = _admit(policy, request_sha256, raw, channel, max_bytes)
    if existing is not None:
        if {k: existing[k] for k in ('candidate', 'receipt')} != value:
            raise OutputReceiptError('Original model output changed for the same request')
        return existing
    key = capture_key(policy, request_sha256, channel, max_bytes)
    # Parse/safety checks precede durable content. No secret or partially parsed
    # response is copied into a receipt, including data inside an excluded field.
    saved = {'schema': policy['schema'],
             'identity': _capture_identity(policy, request_sha256, channel, max_bytes),
             'raw': raw if value['candidate'] is not None else None, 'admission': value}
    _write(store, key, saved)
    return {'key': key, **value}


def usable_result(capture):
    """Compatibility only; new profiles use require_accepted_candidate."""
    if capture['receipt']['decision']['outcome'] not in {'ACCEPT', 'NORMALIZE'}:
        return {'_invalid_json': 'MODEL_OUTPUT_REJECTED'}
    if not isinstance(capture['candidate'], dict):
        raise OutputReceiptError('Accepted output is not a complete object')
    return deepcopy(capture['candidate'])


def record_projection(store, capture, *, input_report, required_claims, reviewed_ledger):
    """Record a projection only AFTER the existing Truth validator succeeds.

    This is derivation evidence, not a normalization of a judgment. Unknown or
    conflicting extra claims are rejected by the caller's validator first.
    """
    if capture is None:
        return
    decisions = input_report.get('decisions', [])
    required = set(required_claims)
    value = {'schema': 'truth-validated-projection@1', 'capture_key': capture['key'],
             'capture_receipt_sha256': admission.digest(capture['receipt']),
             'report_sha256': admission.digest(input_report),
             'contributing_claims': [r['claim_id'] for r in decisions if r['claim_id'] in required],
             'compatible_extra_claims': [r['claim_id'] for r in decisions if r['claim_id'] not in required],
             'validated_semantics_sha256': admission.digest({
                 'script_sha256': reviewed_ledger['script_sha256'],
                 'truth_packet_sha256': reviewed_ledger['truth_packet_sha256'],
                 'status': reviewed_ledger['status'],
                 'claims': [{'claim_id': row['claim_id'], 'status': row['status']}
                            for row in reviewed_ledger['claims']]})}
    key = 'output-projection-' + admission.digest({'capture_key': capture['key'], 'report': value['report_sha256']})
    saved = read_record(store, key)
    if saved is not None and saved != value:
        raise OutputReceiptError('Validated Truth projection changed')
    if saved is None:
        _write(store, key, value)
