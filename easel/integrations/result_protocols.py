"""Fixed result versions for new Attempts; absent pins retain legacy behavior."""
from __future__ import annotations

from copy import deepcopy
from easel.integrations.output_receipts import OutputReceiptError

SCHEMA = 'agent-result-protocols@1'
SUPPORTED = {
    'truth_reply': {'truth-source-ref@1'},
    'material_observation': {'material-observation-delta@1'},
    'script_ledger': {'easel-script-claim-ledger@3'},
    'quality_review': {'quality-review-delta@1'},
    'hypit_run_promotion': {'hypit-run-promotion@1'},
    'hypit_source': {'easel-hypit-source@1'},
    # Subsequent stages are registered with their consumer implementation.
}
# New Attempts use the verified ADR-005 pipeline; existing Attempts retain their
# immutable stored protocol pins. The transitional SVRun-only Writer remains
# available solely to its explicitly pinned historical Attempts.
DEFAULT_PROFILES = {
    'truth_reply': 'truth-source-ref@1',
    'material_observation': 'material-observation-delta@1',
    'script_ledger': 'easel-script-claim-ledger@3',
    'quality_review': 'quality-review-delta@1',
    'hypit_source': 'easel-hypit-source@1',
}


def validate(value):
    if (not isinstance(value, dict) or set(value) != {'schema', 'profiles'}
            or value.get('schema') != SCHEMA or not isinstance(value.get('profiles'), dict)):
        raise OutputReceiptError('Attempt result protocol pin is invalid')
    for stage, revision in value['profiles'].items():
        if stage not in SUPPORTED or not isinstance(revision, str) or revision not in SUPPORTED[stage]:
            raise OutputReceiptError('Attempt result protocol is unsupported')
    if {'hypit_run_promotion', 'hypit_source'} <= set(value['profiles']):
        raise OutputReceiptError('Attempt cannot select two competing Hypit Authoring publication Owners')
    return deepcopy(value)


def current():
    return validate({'schema': SCHEMA, 'profiles': DEFAULT_PROFILES})


def inherited(attempt):
    return validate(attempt.get('result_protocols', {'schema': SCHEMA, 'profiles': {}}))


def selected(attempt, stage):
    if stage not in SUPPORTED:
        raise OutputReceiptError('Unknown result protocol stage')
    return inherited(attempt)['profiles'].get(stage)
