"""Lossless Planning request presentation; source/answer contracts stay intact."""
from copy import deepcopy
from collections import Counter
import json

from easel.integrations.planning_authority import digest
from easel.integrations.planning_structured import request_for, TOOL

LEGACY_POLICY = 'planning-input-schema-dedup@1'
CONTEXT_POLICY = 'planning-input-context-dedup@2'
POLICY = 'planning-input-context-dedup@3'
BINDING = 'input_projection'
REFERENCE = '$easel_schema_ref'
CONTEXT_REFERENCE = '$easel_context_ref'
CONTEXT_FIELDS = ('candidate_bindings', 'evidence', 'source_catalog')
QUESTION_CONTEXT_FIELDS = ('candidate_context', 'coverage_candidates',
                           'creative_dependency', 'd2_review')


def _context_locations(value, *, evidence_choices=True):
    choices = value.get('evidence_choices_by_target')
    if evidence_choices and isinstance(choices, dict):
        for target in choices:
            yield choices, target
    context = value.get('review_context')
    if isinstance(context, dict):
        for batch in context.get('frozen_batches', []):
            for field in CONTEXT_FIELDS:
                if field in batch:
                    yield batch, field
            if evidence_choices:  # @3: full repeated question context, never answers/IDs.
                for question in batch.get('questions', []):
                    for field in QUESTION_CONTEXT_FIELDS:
                        if field in question:
                            yield question, field


def restore(view, tool_schema, *, stage, expected_original_sha256):
    value = deepcopy(view)
    binding = value.pop(BINDING, None)
    request = request_for(tool_schema)
    policy = binding.get('policy') if isinstance(binding, dict) else None
    if (policy not in (POLICY, CONTEXT_POLICY, LEGACY_POLICY) or binding != {
            'policy': policy, 'stage': stage,
            'original_sha256': expected_original_sha256,
            'projected_sha256': digest(value),
            'tool_schema_sha256': request['schemaSha256']}):
        raise ValueError('Planning input projection binding changed')
    key = 'response_schema' if stage == 'B' else 'schema'
    if value.get(key) != {'$tool_parameters': TOOL, 'sha256': request['schemaSha256']}:
        raise ValueError('Planning input tool Schema reference changed')
    value[key] = request['schema']
    catalog = value.pop('schema_catalog', {})
    used = set()
    for target in value.get('targets', []):
        for field in ('answer_schema', 'answer_defs'):
            reference = target.get(field)
            if not isinstance(reference, dict) or set(reference) != {REFERENCE}:
                continue
            identity = reference[REFERENCE]
            entry = catalog.get(identity)
            if (not isinstance(entry, dict) or set(entry) != {'sha256', 'value'}
                    or entry['sha256'] != digest(entry['value'])):
                raise ValueError('Planning input local Schema reference changed')
            target[field] = deepcopy(entry['value'])
            used.add(identity)
    if used != set(catalog):
        raise ValueError('Planning input local Schema catalog coverage changed')
    context_catalog = value.pop('context_catalog', {})
    if context_catalog and (policy not in (POLICY, CONTEXT_POLICY) or stage != 'repair'):
        raise ValueError('Planning input context catalog is not allowed')
    used_context = set()
    for batch, field in _context_locations(value, evidence_choices=policy == POLICY):
        reference = batch[field]
        if not isinstance(reference, dict) or set(reference) != {CONTEXT_REFERENCE}:
            continue
        identity = reference[CONTEXT_REFERENCE]
        entry = context_catalog.get(identity)
        if (not isinstance(entry, dict) or set(entry) != {'sha256', 'value'}
                or entry['sha256'] != digest(entry['value'])):
            raise ValueError('Planning input frozen context reference changed')
        batch[field] = deepcopy(entry['value'])
        used_context.add(identity)
    if used_context != set(context_catalog) or digest(value) != expected_original_sha256:
        raise ValueError('Planning input does not restore its frozen original')
    return value


def project(payload, tool_schema, *, stage):
    if (stage not in {'B', 'repair'} or BINDING in payload
            or 'schema_catalog' in payload or 'context_catalog' in payload):
        raise ValueError('Unknown Planning input projection or reserved field')
    request = request_for(tool_schema)
    key = 'response_schema' if stage == 'B' else 'schema'
    if payload.get(key) != request['schema']:
        raise ValueError('Planning input differs from final outgoing tool Schema')
    value = deepcopy(payload)
    value[key] = {'$tool_parameters': TOOL, 'sha256': request['schemaSha256']}
    catalog, identities = {}, {}
    if stage == 'repair':
        counts = Counter(digest(target[field]) for target in value['targets']
                         for field in ('answer_schema', 'answer_defs') if field in target)
        for target in value['targets']:
            for field in ('answer_schema', 'answer_defs'):
                if field not in target:
                    continue
                schema = target[field]
                identity_sha = digest(schema)
                if counts[identity_sha] < 2 or len(json.dumps(schema, ensure_ascii=False, sort_keys=True)) < 512:
                    continue
                if identity_sha not in identities:
                    identity = f'schema-{len(catalog):04}'
                    identities[identity_sha] = identity
                    catalog[identity] = {'sha256': identity_sha, 'value': schema}
                identity = identities[identity_sha]
                if catalog[identity]['value'] != schema:
                    raise ValueError('Planning input Schema digest collision')
                target[field] = {REFERENCE: identity}
    if catalog:
        value['schema_catalog'] = catalog
    context_catalog = {}
    if stage == 'repair':
        locations = list(_context_locations(value))
        counts = Counter(digest(batch[field]) for batch, field in locations)
        for batch, field in locations:
            original = batch[field]
            if isinstance(original, dict) and CONTEXT_REFERENCE in original:
                raise ValueError('Reserved Planning context reference in original')
            identity_sha = digest(original)
            if counts[identity_sha] < 2 or len(json.dumps(original, ensure_ascii=False)) < 512:
                continue
            identity = 'context-' + identity_sha
            entry = {'sha256': identity_sha, 'value': original}
            if identity in context_catalog and context_catalog[identity] != entry:
                raise ValueError('Planning input context digest collision')
            context_catalog[identity] = entry
            batch[field] = {CONTEXT_REFERENCE: identity}
    if context_catalog:
        value['context_catalog'] = context_catalog
    original_sha = digest(payload)
    value[BINDING] = {'policy': POLICY, 'stage': stage,
        'original_sha256': original_sha, 'projected_sha256': digest(value),
        'tool_schema_sha256': request['schemaSha256']}
    if restore(value, request['schema'], stage=stage,
               expected_original_sha256=original_sha) != payload:
        raise ValueError('Planning input projection is not lossless')
    return value


GUIDANCE = ('\n输入表示：response_schema/schema指唯一submit_semantic_plan工具的完整实际parameters，'
    '正文不重复复制；逐字段遵守工具Schema，不增加根字段。'
    'schema_catalog仅保存重复Schema元数据，$easel_schema_ref按本消息同名条目的value读取全文。'
    'context_catalog保存完整冻结上下文，$easel_context_ref必须按同名条目的value读取全部原文；'
    '包括逐题候选/创作依据/D2上下文与evidence_choices_by_target的重复完整选项表；'
    '引用保留原字段含义，每题须独立判断，每个target仍只允许其绑定表中的evidence_ref。'
    '它只消除重复副本，不省略任何候选、证据或来源，不得把引用句柄当作证据内容。'
    'input_projection是程序身份信息，不作为语义依据，也不返回它。'
    '完整来源、候选、原答案和修复目标均保留，其他审查与修复规则全部适用。')
