"""Attempt-local requirements and bounded results; no new Material semantics.

Natural-language classification remains Planning's responsibility. Span checks
prove coverage/identity, not that a model interpreted the creator correctly.
"""
from __future__ import annotations

import hashlib
import json

from easel.materials.application.visual_observation import SCHEMA, ASSESSMENT_REVISION, need_identity

REVISION = 'visual-requirements@1'
RESULT_LIMIT = 3000
KINDS = {'required', 'preference', 'postproduction', 'unresolved'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def sources_for(need):
    rows = []
    def append(path, value, explicit_preference=False):
        if isinstance(value, str) and value.strip():
            rows.append({'path': path, 'text': value, 'preference': explicit_preference})
        elif isinstance(value, (list, tuple)):
            for i, part in enumerate(value):
                append(f'{path}/{i}', part, explicit_preference)
    for key, value in need.intent.model_dump(mode='json').items():
        append('intent/' + key, value)
    for key, value in need.constraints.items():
        if key not in {'search_query_en', 'search_query_variants_en', 'voice_delivery', 'required_source_kind', 'usage'}:
            append('constraints/' + key, value, key in {'preferred_visual_details', 'preferred_style'})
    if need.modality_spec:
        for key, value in need.modality_spec.model_dump(mode='json').items():
            if key in {'subject', 'action', 'setting', 'description', 'visual_style'}:
                append('modality/' + key, value, key == 'visual_style')
    return rows


def compilation_input(need, context_refs, mode):
    return {'revision': REVISION, 'need_sha256': need_identity(need),
            'context_refs': context_refs, 'mode': mode, 'sources': sources_for(need),
            'need': need.model_dump(mode='json')}


def validate_compilation(input_data, response):
    rows = response.get('clauses') if isinstance(response, dict) else None
    if not isinstance(rows, list) or not 1 <= len(rows) <= 40:
        raise ValueError('审核要求须有完整且有界的原文条款')
    coverage = {i: [] for i in range(len(input_data['sources']))}
    clauses = []
    for index, row in enumerate(rows):
        if isinstance(row, list) and len(row) == 5:
            row = dict(zip(('source', 'start', 'end', 'kind', 'preference_source'), row))
        if not isinstance(row, dict) or set(row) != {'source', 'start', 'end', 'kind', 'preference_source'}:
            raise ValueError('要求条款字段无效')
        source, begin, end = row['source'], row['start'], row['end']
        if (type(source) is not int or source not in coverage or type(begin) is not int
                or type(end) is not int or not 0 <= begin < end <= len(input_data['sources'][source]['text'])
                or row['kind'] not in KINDS):
            raise ValueError('要求引用不属于冻结原文')
        explicit = input_data['sources'][source]['preference']
        pref = row['preference_source']
        if pref is not None and (type(pref) is not int or pref not in coverage
                                or not input_data['sources'][pref]['preference']):
            raise ValueError('偏好引用须属于显式允许取舍项')
        if explicit and row['kind'] not in {'preference', 'unresolved'}:
            raise ValueError('显式偏好不能自动升级必要项；有冲突应保留歧义')
        if row['kind'] == 'preference' and not explicit and pref is None:
            raise ValueError('不能将原必要表达静默降为偏好')
        if row['kind'] == 'postproduction' and input_data['need']['constraints'].get('requires_dynamic_action') is True:
            raise ValueError('必要源动作不能交给静态图片后期补出')
        coverage[source].append((begin, end))
        clauses.append({'id': index, **row, 'text': input_data['sources'][source]['text'][begin:end]})
    for source, spans in coverage.items():
        cursor = 0
        for begin, end in sorted(spans):
            if begin != cursor:
                raise ValueError('原文要求漏项或重叠，不能形成正式合同')
            cursor = end
        if cursor != len(input_data['sources'][source]['text']):
            raise ValueError('原文要求未完整覆盖')
    if not any(c['kind'] == 'required' for c in clauses):
        raise ValueError('视觉 Need 缺少必要表达，不得按空要求准入')
    queries = response.get('queries', [])
    if (not isinstance(queries, list) or len(queries) not in {0, 3}
            or any(not isinstance(q, str) or not q.strip() or len(q) > 100
                   or not q.isascii() or not any(c.isalpha() for c in q) for q in queries)
            or len({q.strip().casefold() for q in queries}) != len(queries)):
        raise ValueError('查询编译须为不同的英文主体/动作/场景短语')
    return {'queries': queries, 'source_data': input_data, 'revision': REVISION, 'input_sha256': digest(input_data),
            'need_sha256': input_data['need_sha256'], 'clauses': clauses}


def batches(manifest, contract):
    required = [c for c in contract['clauses'] if c['kind'] == 'required']
    if any(c['kind'] == 'unresolved' for c in contract['clauses']):
        raise ValueError('审核要求仍有歧义，先由 Planning 澄清，未提交观察')
    # Budget the maximum escaped representation, including supplementary Unicode.
    # A single frame/short requirement remains below the gateway cap. Split
    # before dispatch; never drop a requirement to make a reply fit.
    result = []
    for frame in manifest['frames']:
        current = []
        for clause in required:
            candidate = current + [clause]
            worst = {'frame': frame['index'], 'observed': True, 'description': '\uffff' * 64,
                     'style': '\uffff' * 32, 'logo': None, 'text': None,
                     'checks': [{'id': c['id'], 'status': 'unknown', 'basis': '\uffff' * 48} for c in candidate],
                     'preference_notes': '\uffff' * 32}
            if len(json.dumps(worst, ensure_ascii=True)) > RESULT_LIMIT:
                if not current:
                    raise ValueError('单项观察容量不足，未提交模型')
                result.append({'frame': frame, 'clauses': current})
                current = [clause]
            else:
                current = candidate
        if current:
            result.append({'frame': frame, 'clauses': current})
    return result


def validate_result(batch, response):
    if (not isinstance(response, dict) or set(response) != {'frame', 'observed', 'description', 'style', 'logo', 'text',
                                                          'checks', 'preference_notes'}
            or type(response['frame']) is not int or response['frame'] != batch['frame']['index']
            or type(response['observed']) is not bool):
        raise ValueError('观察结果帧编号或字段无效')
    for key, limit in [('description', 64), ('style', 32), ('preference_notes', 32)]:
        if not isinstance(response[key], str) or not response[key].strip() or len(response[key].encode('utf-16-le')) // 2 > limit:
            raise ValueError('观察事实缺失或超出容量')
    if any(response[k] is not None and type(response[k]) is not bool for k in ('logo', 'text')):
        raise ValueError('实际文字/标志须为布尔或未知')
    rows = response['checks']
    if not isinstance(rows, list) or [r.get('id') for r in rows if isinstance(r, dict)] != [c['id'] for c in batch['clauses']]:
        raise ValueError('必要项漏报、重复或编号错误')
    for row in rows:
        if (set(row) != {'id', 'status', 'basis'} or type(row['id']) is not int
                or row['status'] not in {'met', 'not_met', 'unknown'}
                or not isinstance(row['basis'], str) or not row['basis'].strip() or len(row['basis'].encode('utf-16-le')) // 2 > 48
                or not response['observed'] and row['status'] != 'unknown'):
            raise ValueError('必要项缺少实际依据或与观察状态矛盾')
    return response


def assemble_report(manifest, contract, results):
    response = {'queries': contract.get('queries', []), 'clauses': [{k: c[k] for k in ('source', 'start', 'end', 'kind', 'preference_source')}
                            for c in contract['clauses']]}
    if validate_compilation(contract['source_data'], response) != contract:
        raise ValueError('保存的审核合同与原文编译不一致')
    expected_batches = batches(manifest, contract)
    if not isinstance(results, list) or len(results) != len(expected_batches):
        raise ValueError('必要项分组结果未完整交付')
    for batch, result in zip(expected_batches, results):
        validate_result(batch, result)
    frames = []
    checks = []
    for frame in manifest['frames']:
        parts = [r for r in results if r['frame'] == frame['index']]
        if not parts:
            raise ValueError('实际帧未完整观察')
        first = parts[0]
        facts = ('observed', 'description', 'style', 'logo', 'text')
        if any(any(r[k] != first[k] for k in facts) for r in parts):
            raise ValueError('分组观察事实冲突，不能合并准入')
        rows = [c for r in parts for c in r['checks']]
        expected = [c['id'] for c in contract['clauses'] if c['kind'] == 'required']
        if [r['id'] for r in rows] != expected:
            raise ValueError('必要项观察不完整')
        statuses = [r['status'] for r in rows]
        satisfied = False if 'not_met' in statuses else None if 'unknown' in statuses else True
        frames.append({'index': frame['index'], 'observed': first['observed'], 'related': satisfied,
                       'meets_requirements': satisfied, 'description': first['description']})
        checks.append({'frame': frame['index'], 'requirements': rows})
    states = [f['meets_requirements'] for f in frames]
    verdict = ('uncertain' if None in states else 'suitable' if all(states) else
               'unsuitable' if not any(states) else 'partial')
    return {'requirements_contract': contract, 'compact_results': results, 'schema': SCHEMA, 'input_sha256': manifest['input_sha256'], 'assessment_revision': ASSESSMENT_REVISION,
            'requirements_sha256': digest(contract), 'requirement_checks': checks,
            'verdict': verdict, 'failure_kind': 'evidence_insufficient' if verdict == 'uncertain' else
                'content_mismatch' if verdict != 'suitable' else 'none',
            'frames': frames, 'caption': results[0]['description'], 'style': results[0]['style'],
            'reason': '; '.join(r['basis'] for p in results for r in p['checks'])[:4000],
            'preference_notes': [p['preference_notes'] for p in results],
            'logo_present': True if any(r['logo'] is True for r in results) else
                False if all(r['logo'] is False for r in results) else None,
            'visible_text_present': True if any(r['text'] is True for r in results) else
                False if all(r['text'] is False for r in results) else None}


def planning_contracts(plan, mode, response):
    """Bind a same-turn Planning sidecar after applying the existing soft default.

    The file references literal source spans, not model-copied hashes or counted
    character offsets. No accepted Plan or original text is rewritten here.
    """
    visual = [n for n in plan.needs if n.media_type.value in {'image', 'video'}]
    if not isinstance(response, dict) or set(response) != {n.need_id for n in visual}:
        raise ValueError('Planning 要求文件须覆盖全部视觉 Need')
    bound = []
    for need in visual:
        raw = response[need.need_id]
        if not isinstance(raw, dict) or set(raw) != {'clauses', 'queries'} or not isinstance(raw['clauses'], list):
            raise ValueError('Planning 要求文件字段无效')
        sources = sources_for(need)
        cursors = {r['path']: 0 for r in sources}
        rows = []
        for row in raw['clauses']:
            if not isinstance(row, dict) or set(row) != {'path', 'text', 'kind', 'preference_path'}:
                raise ValueError('Planning 要求须引用原文和类别')
            path = row['path']
            index = next((i for i, r in enumerate(sources) if r['path'] == path), None)
            if index is None or not isinstance(row['text'], str) or not row['text']:
                raise ValueError('Planning 要求原文路径无效')
            begin, end = cursors[path], cursors[path] + len(row['text'])
            if sources[index]['text'][begin:end] != row['text']:
                raise ValueError('Planning 要求引用不等于原文顺序区间')
            pref = next((i for i, r in enumerate(sources) if r['path'] == row['preference_path']), None)
            if row['preference_path'] is not None and pref is None:
                raise ValueError('Planning 偏好引用不存在')
            rows.append([index, begin, end, row['kind'], pref])
            cursors[path] = end
        # The regular persist stage appends this same explicitly soft Mode
        # default. It is provenance, not an inferred necessary requirement.
        style = getattr(need.modality_spec, 'visual_style', None) or mode.get('visual_material_style')
        if style and not need.constraints.get('preferred_style'):
            need = need.model_copy(update={'constraints': {**need.constraints, 'preferred_style': style}})
            current = sources_for(need)
            # Insertion can precede modality text; map source indices by path.
            remap = {i: next(j for j, r in enumerate(current) if r['path'] == old['path']) for i, old in enumerate(sources)}
            rows = [[remap[r[0]], r[1], r[2], r[3], remap[r[4]] if r[4] is not None else None] for r in rows]
            index = next(i for i, r in enumerate(current) if r['path'] == 'constraints/preferred_style')
            rows.append([index, 0, len(style), 'preference', None])
        frozen = compilation_input(need, plan.context_refs, mode)
        compiled = {'clauses': rows, 'queries': raw['queries']}
        contract = validate_compilation(frozen, compiled)
        bound.append((digest(frozen), {'input': frozen, 'response': compiled, 'contract': contract}))
    return bound
