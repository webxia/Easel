"""Lossless Planning request presentation; source/answer contracts stay intact."""
from copy import deepcopy
from collections import Counter
import json

from easel.integrations.planning_authority import digest
from easel.integrations.planning_structured import request_for, TOOL

POLICY = 'planning-input-schema-dedup@1'
BINDING = 'input_projection'
REFERENCE = '$easel_schema_ref'


def restore(view, tool_schema, *, stage, expected_original_sha256):
    value = deepcopy(view)
    binding = value.pop(BINDING, None)
    request = request_for(tool_schema)
    if (not isinstance(binding, dict) or binding != {
            'policy': POLICY, 'stage': stage,
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
    if used != set(catalog) or digest(value) != expected_original_sha256:
        raise ValueError('Planning input does not restore its frozen original')
    return value


def project(payload, tool_schema, *, stage):
    if stage not in {'B', 'repair'} or BINDING in payload or 'schema_catalog' in payload:
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
    'input_projection是程序身份信息，不作为语义依据，也不返回它。'
    '完整来源、候选、原答案和修复目标均保留，其他审查与修复规则全部适用。')
