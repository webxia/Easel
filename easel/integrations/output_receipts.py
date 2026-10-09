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


def pin_policy(store, *, stage, logical_id, binding, profile, legacy_started=False):
    key = policy_key(stage, logical_id)
    identity = {'stage': stage, 'logical_id': logical_id, 'binding': deepcopy(binding)}
    current_policy = admission.policy_identity(profile)
    saved = read_record(store, key)
    captures = any((store.materials_root / 'recoveries').glob('output-capture-' + key.removeprefix('output-policy-')[:24] + '-*.json'))
    if captures and (not isinstance(saved, dict) or saved.get('mode') != 'current'):
        raise OutputReceiptError('Existing captures lost their pinned consumer policy')
    if saved is None:
        saved = {'schema': POLICY, 'identity': identity,
                 'mode': 'legacy' if legacy_started else 'current',
                 'policy': None if legacy_started else current_policy}
        _write(store, key, saved)
    if (not isinstance(saved, dict) or set(saved) != {'schema', 'identity', 'mode', 'policy'}
            or saved['schema'] != POLICY or saved['identity'] != identity
            or saved['mode'] not in {'legacy', 'current'}
            or saved['policy'] != (None if saved['mode'] == 'legacy' else current_policy)):
        raise OutputReceiptError('Output consumer policy or input identity changed')
    return {'key': key, **saved}


def _capture_identity(policy, request_sha256, channel, max_bytes):
    if policy['mode'] != 'current':
        raise OutputReceiptError('Legacy output cannot obtain a new receipt')
    return {'policy_key': policy['key'], 'policy_sha256': admission.digest(policy),
            'request_sha256': request_sha256, 'channel': channel, 'max_bytes': max_bytes}


def capture_key(policy, request_sha256, channel, max_bytes):
    prefix = policy['key'].removeprefix('output-policy-')[:24]
    return 'output-capture-' + prefix + '-' + admission.digest(_capture_identity(policy, request_sha256, channel, max_bytes))


def _admit(policy, request_sha256, raw, channel, max_bytes):
    return admission.admit_json(raw, OBJECT_SCHEMA, stage=policy['identity']['stage'],
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
            or saved['schema'] != POLICY or saved['identity'] != identity
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
                or receipt.get('wire_schema_sha256') != admission.digest(OBJECT_SCHEMA)
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
    saved = {'schema': POLICY,
             'identity': _capture_identity(policy, request_sha256, channel, max_bytes),
             'raw': raw if value['candidate'] is not None else None, 'admission': value}
    _write(store, key, saved)
    return {'key': key, **value}


def usable_result(capture):
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
