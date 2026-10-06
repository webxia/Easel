"""Attempt-local requirements and bounded results; no new Material semantics.

Natural-language classification remains Planning's responsibility. Span checks
prove coverage/identity, not that a model interpreted the creator correctly.
"""
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel

from easel.materials.application.visual_observation import SCHEMA, ASSESSMENT_REVISION, need_identity

REVISION = 'visual-requirements@1'
RESULT_LIMIT = 3000
KINDS = {'required', 'preference', 'postproduction', 'unresolved'}
QUERY_FIELDS = {'search_query_en', 'search_query_variants_en',
                'search_query_variants_primary', 'search_query_variants_alternate', 'search_query_variants_relaxed'}


class PlanningClause(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    path: str = Field(min_length=1)
    text: str = Field(min_length=1)
    kind: Literal['required', 'preference', 'postproduction', 'unresolved']
    preference_path: str | None


class PlanningRequirement(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    clauses: list[PlanningClause] = Field(min_length=1, max_length=40)
    queries: list[str] = Field(max_length=3)


class PlanningRequirements(RootModel[dict[str, PlanningRequirement]]):
    """Canonical sidecar: visual Need ID -> literal clauses and queries."""
    model_config = ConfigDict(strict=True)


def read_planning_requirements(text):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Planning 要求 JSON 对象键重复：' + key)
            result[key] = value
        return result
    return json.loads(text, object_pairs_hook=unique_object)


def requirements_cache_key(frozen):
    return 'requirements-' + digest({'compiler_policy': 'indexed-unit-classification@7', 'input': frozen})


def normalize_planning_requirements(plan, response):
    """Convert the observed transport shape, never infer a missing hard clause.

    The original sidecar and Plan are untouched. Audio belongs to its own
    contracts; only known current audio IDs may be excluded from the wrapper.
    """
    visual = {n.need_id: n for n in plan.needs if n.media_type.value in {'image', 'video'}}
    data = deepcopy(response)
    if isinstance(data, dict) and set(data) == {'plan_id', 'creation_id', 'attempt_id', 'context_refs', 'visual_requirements'}:
        if any(data[key] != getattr(plan, key) for key in ('plan_id', 'creation_id', 'attempt_id', 'context_refs')):
            raise ValueError('Planning 要求包装身份与当前 Plan 不一致')
        rows = data['visual_requirements']
        if not isinstance(rows, list):
            raise ValueError('Planning 要求包装须为列表')
        known = {n.need_id for n in plan.needs}
        seen, converted = set(), {}
        for row in rows:
            if not isinstance(row, dict) or set(row) != {'need_id', 'clauses', 'queries'}:
                raise ValueError('Planning 要求包装行字段无效')
            need_id = row['need_id']
            if not isinstance(need_id, str) or need_id not in known or need_id in seen:
                raise ValueError('Planning 要求 Need ID 未知或重复')
            seen.add(need_id)
            raw = {key: row[key] for key in ('clauses', 'queries')}
            # Even excluded audio rows must obey the observed row schema.
            PlanningRequirement.model_validate(raw)
            if need_id not in visual:
                continue
            sources = {s['path']: s['text'] for s in sources_for(visual[need_id])}
            cursors = {path: 0 for path in sources}
            for clause in raw['clauses']:
                for key in ('path', 'preference_path'):
                    if clause[key] == 'modality_spec/visual_style':
                        clause[key] = 'modality/visual_style'
                if clause['preference_path'] == '':
                    clause['preference_path'] = None
                path, text = clause['path'], clause['text']
                if path in sources:
                    begin = cursors[path]
                    literal = sources[path][begin:begin + len(text)]
                    # The observed wrapper copied curved single quotes as
                    # ASCII. Bind only this same-position, same-length drift
                    # back to the source; canonical maps remain verbatim.
                    if len(literal) == len(text) and all(
                            a == b or a in '\u2018\u2019' and b == "'"
                            for a, b in zip(literal, text)):
                        clause['text'] = literal
                    cursors[path] += len(text)
            converted[need_id] = raw
        data = converted
    if not isinstance(data, dict) or set(data) != set(visual):
        raise ValueError('Planning 要求根对象须仅以全部视觉 Need ID 作键（含 optional）')
    PlanningRequirements.model_validate(data)
    for need_id, raw in data.items():
        present = {c['path'] for c in raw['clauses']}
        for source in sources_for(visual[need_id]):
            # A whole explicit soft source has no classification ambiguity.
            # Partial coverage or promotion is left to the strict validator.
            if source['preference'] and source['path'] not in present:
                raw['clauses'].append({'path': source['path'], 'text': source['text'],
                                      'kind': 'preference', 'preference_path': None})
    return PlanningRequirements.model_validate(data).model_dump(mode='json')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def sources_for(need):
    from easel.materials.application.need_constraints import validate_modality_constraints
    validate_modality_constraints((need,))
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
        if key not in QUERY_FIELDS | {'voice_delivery', 'required_source_kind', 'usage'}:
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



def classification_units(input_data):
    """Program owns exact punctuation/space boundaries; model owns meaning."""
    units = []
    for source, row in enumerate(input_data['sources']):
        if row['preference']:
            continue
        pattern = r'.+\Z' if row['path'] == 'intent/function' else r'.*?(?:[,;，；。]|\Z)'
        for match in re.finditer(pattern, row['text'], re.DOTALL):
            if match.start() == match.end():
                continue
            units.append({'id': len(units), 'source': source, 'start': match.start(),
                          'end': match.end(), 'text': match.group()})
    if not 1 <= len(units) + sum(r['preference'] for r in input_data['sources']) <= 40:
        raise ValueError('原文分类单元超出有界合同；未派发或删减要求')
    return units


def bind_classifications(input_data, response):
    units = classification_units(input_data)
    rows = response.get('classifications') if isinstance(response, dict) else None
    if (not isinstance(rows, list) or len(rows) != len(units)
            or any(not isinstance(r, dict) or set(r) != {'id', 'kind', 'preference_source'} for r in rows)
            or any(type(r['id']) is not int for r in rows)
            or [r['id'] for r in rows] != [u['id'] for u in units]):
        raise ValueError('分类须按实际unit编号完整返回一次；不能漏报、重复或自行新增原文')
    clauses = [[u['source'], u['start'], u['end'], r['kind'], r['preference_source']]
               for u, r in zip(units, rows)]
    clauses.extend([i, 0, len(row['text']), 'preference', i]
                   for i, row in enumerate(input_data['sources']) if row['preference'])
    result = {'clauses': clauses, 'queries': response.get('queries', [])}
    validate_compilation(input_data, result)
    return result

def validate_compilation(input_data, response):
    rows = response.get('clauses') if isinstance(response, dict) else None
    if not isinstance(rows, list) or not 1 <= len(rows) <= 40:
        raise ValueError('审核要求须有完整且有界的原文条款')
    coverage = {i: [] for i in range(len(input_data['sources']))}
    clauses = []
    quote_cursors = {i: 0 for i in coverage}
    for index, row in enumerate(rows):
        if isinstance(row, list) and len(row) == 4 and isinstance(row[1], str):
            row = dict(zip(('source', 'text', 'kind', 'preference_source'), row))
        if isinstance(row, dict) and set(row) == {'source', 'text', 'kind', 'preference_source'}:
            source, text = row['source'], row['text']
            if (type(source) is not int or source not in coverage or not isinstance(text, str) or not text
                    or not input_data['sources'][source]['text'].startswith(text, quote_cursors[source])):
                raise ValueError('条款须逐段逐字引用冻结原文，不能改写、遗漏或重排')
            begin = quote_cursors[source]
            quote_cursors[source] += len(text)
            row = {'source': source, 'start': begin, 'end': quote_cursors[source],
                   'kind': row['kind'], 'preference_source': row['preference_source']}
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
    # Plan a concise escaped representation, including supplementary Unicode.
    # Actual results still have the strict total gateway cap. Split
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
    if len(json.dumps(response, ensure_ascii=False, separators=(',', ':')).encode('utf-16-le')) // 2 > RESULT_LIMIT:
        raise ValueError('观察报告超出总容量')
    for key in ('description', 'style', 'preference_notes'):
        if not isinstance(response[key], str) or not response[key].strip():
            raise ValueError('观察事实缺失')
    if any(response[k] is not None and type(response[k]) is not bool for k in ('logo', 'text')):
        raise ValueError('实际文字/标志须为布尔或未知')
    rows = response['checks']
    if not isinstance(rows, list) or [r.get('id') for r in rows if isinstance(r, dict)] != [c['id'] for c in batch['clauses']]:
        raise ValueError('必要项漏报、重复或编号错误')
    for row in rows:
        if (set(row) != {'id', 'status', 'basis'} or type(row['id']) is not int
                or row['status'] not in {'met', 'not_met', 'unknown'}
                or not isinstance(row['basis'], str) or not row['basis'].strip()
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
    response = normalize_planning_requirements(plan, response)
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
        bound.append((requirements_cache_key(frozen), {'input': frozen, 'response': compiled, 'contract': contract}))
    return bound
