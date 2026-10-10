"""Single ADR-005 result protocol for production Attempts.

Historical Attempts remain stored and readable through their original files.
They cannot be resumed as a legacy producer, or silently upgraded to new pins.
"""
from __future__ import annotations

from copy import deepcopy
from types import MappingProxyType
from easel.integrations.output_receipts import OutputReceiptError

SCHEMA = "agent-result-protocols@1"
_REQUIRED_PROFILES = MappingProxyType({
    "truth_reply": "truth-source-ref@1",
    "material_observation": "material-observation-delta@1",
    "script_ledger": "easel-script-claim-ledger@3",
    "quality_review": "quality-review-delta@1",
    "hypit_source": "easel-hypit-source@1",
})
# A caller's mutable default is never the authority used by validate().
DEFAULT_PROFILES = dict(_REQUIRED_PROFILES)
SUPPORTED = {key: frozenset({value}) for key, value in _REQUIRED_PROFILES.items()}


def validate(value):
    if (not isinstance(value, dict) or set(value) != {"schema", "profiles"}
            or value.get("schema") != SCHEMA
            or not isinstance(value.get("profiles"), dict)):
        raise OutputReceiptError("Film Attempt result protocol pin is invalid")
    # A subset/empty/legacy pin is not a valid production choice: it must not
    # bypass the native Authoring Owner or reissue an old model request.
    if value["profiles"] != _REQUIRED_PROFILES:
        raise OutputReceiptError(
            "Legacy, transitional or partial result protocols are read-only; "
            "create a new Attempt using the five ADR-005 profiles")
    return deepcopy(value)


def current():
    return validate({"schema": SCHEMA, "profiles": DEFAULT_PROFILES})


def inherited(attempt):
    return validate(attempt.get("result_protocols"))


def selected(attempt, stage):
    if stage not in SUPPORTED:
        raise OutputReceiptError("Unsupported result protocol stage")
    return inherited(attempt)["profiles"][stage]
