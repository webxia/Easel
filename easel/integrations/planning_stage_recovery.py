"""Pure, fail-closed current Planning A-details stage-regeneration policy.

This module never schedules a model call or changes source references.
Only the existing Planning owner may reserve the shared three-repair budget.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy

from jsonschema import Draft202012Validator

POLICY = 'planning-a-details-stage-loop@1'
MAX_STAGE_REGENERATIONS = 2
TERMINAL_POLICY = 'planning-native-zero-tool-terminal@1'


def _exact_object(raw):
    if not isinstance(raw, str):
        return None
    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate A-details JSON key')
            result[key] = value
        return result
    def reject_constant(value):
        raise ValueError('Non-finite A-details JSON number')
    try:
        value = json.loads(raw, object_pairs_hook=object_pairs,
                           parse_constant=reject_constant)
    except (ValueError, UnicodeError):
        return None
    return value if isinstance(value, dict) else None


def source_only_failure(raw, schema):
    """Allow whole-stage regeneration only for *exactly* invalid creative refs.

    An unknown handle is never substituted, normalized or accepted here.
    Remaining schema violations, missing fields and modality changes stay STOP.
    """
    value = _exact_object(raw)
    if value is None or not isinstance(schema, dict):
        return None
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(value), key=lambda e: tuple(map(str, e.absolute_path)))
    if not errors:
        return None
    paths = []
    for error in errors:
        path = list(error.absolute_path)
        if (error.validator != 'enum' or len(path) != 6 or
                path[0] != 'slots' or not isinstance(path[1], str) or
                not path[1].startswith('slot_') or path[2] != 'conditions' or
                type(path[3]) is not int or path[4:] != ['claim', 'creative_goal_ref'] or
                not isinstance(error.instance, str)):
            return None
        paths.append(path)
    return {'policy': POLICY, 'decision': 'STAGE_REGENERATE',
            'reason': 'INVALID_CREATIVE_SOURCE',
            'raw_sha256': hashlib.sha256(raw.encode()).hexdigest(),
            'schema_sha256': hashlib.sha256(
                json.dumps(schema, sort_keys=True, ensure_ascii=False,
                           separators=(',', ':')).encode()).hexdigest(),
            'error_paths': paths}


def confirmed_no_tool(receipt, *, stage, schema_sha256, session):
    """Accept only an independently authenticated native terminal rejection."""
    if (not isinstance(receipt, dict) or receipt.get('policy') != TERMINAL_POLICY
            or receipt.get('state') != 'CONFIRMED_TERMINAL_NO_TOOL'
            or receipt.get('stage') != stage
            or receipt.get('session') != session
            or receipt.get('schema_sha256') != schema_sha256
            or receipt.get('provider_finish') != 'stop'
            or receipt.get('native_stop') != 'stop'
            or receipt.get('tool_call_count') != 0
            or receipt.get('native_category') != 'STRUCTURED_TERMINAL_REJECTED'
            or not isinstance(receipt.get('original_run_id'), str)
            or not receipt['original_run_id'].startswith('easel-')
            or not isinstance(receipt.get('native_evidence_sha256'), str)
            or len(receipt['native_evidence_sha256']) != 64
            or receipt.get('runtime_release') != 'released'
            or receipt.get('terminal_status') != 'error'):
        return None
    return {'policy': POLICY, 'decision': 'STAGE_REGENERATE',
            'reason': 'TERMINAL_NO_TOOL', 'terminal_evidence': deepcopy(receipt)}


def recovery_identity(original_stage, original_failure, *, ordinal, frozen_schema_sha256,
                      detail_binding_sha256):
    if (not isinstance(original_stage, str) or
            not original_stage.startswith('A-details-') or
            original_failure.get('decision') != 'STAGE_REGENERATE' or
            original_failure.get('reason') not in ('TERMINAL_NO_TOOL', 'INVALID_CREATIVE_SOURCE') or
            type(ordinal) is not int or not 0 <= ordinal < MAX_STAGE_REGENERATIONS):
        raise ValueError('Stage regeneration identity not authorized')
    return {'policy': POLICY, 'original_stage': original_stage,
            'ordinal': ordinal, 'reason': original_failure['reason'],
            'failure_sha256': hashlib.sha256(json.dumps(
                original_failure, sort_keys=True, ensure_ascii=False,
                separators=(',', ':')).encode()).hexdigest(),
            'schema_sha256': frozen_schema_sha256,
            'detail_binding_sha256': detail_binding_sha256}


def regeneration_message(original_message, stage, failure, ordinal):
    if not isinstance(original_message, str) or not original_message:
        raise ValueError('Missing frozen Planning original A-details prompt')
    if ordinal < 0 or ordinal >= MAX_STAGE_REGENERATIONS:
        raise ValueError('Stage regeneration attempts exhausted')
    # No original invalid candidate is presented as a valid source of facts.
    # The full original frozen source and Tool Schema are still supplied by Owner.
    return (original_message +
        '\n〔Easel Planning Controlled Loop V1：受控整批重新生成〕\n'
        '上一独立模型操作已确认终结，但没有通过当前闭合工具合同。'
        '这是一项新模型操作，并非重派旧 Run。当前批次的所有 Slots 需要从冻结 Creator、Director、'
        'SourceSelection 和原输入重新独立决定，不继承失败答复。'
        '必须通过唯一 submit_semantic_plan 工具提交完整 Slots 与显式 unresolved，'
        'creative_goal_ref 只能从本次工具 Schema 当前允许的 src 枚举选择。'
        '不能推测或自动修正未知来源；不得更改原已冻结 Need/Mode、遗漏必要义务或创建授权。\n'
        +json.dumps({'stage': stage, 'kind': failure['reason'], 'attempt': ordinal + 1,
                     'failed_source_sha256': failure.get('raw_sha256'),
                     'bad_paths': failure.get('error_paths', [])},
                    ensure_ascii=False, separators=(',', ':')))
