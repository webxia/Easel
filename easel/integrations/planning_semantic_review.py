"""Planning-local bounded review and patches, without another workflow engine.

Physical provenance is application-owned. Evidence selection never proves
entailment: the review remains a fallible model judgment, not a pixel Gate.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Literal
import hashlib
import json
from pydantic import TypeAdapter, ValidationError

from easel.integrations.planning_authority import digest
from easel.integrations import planning_review_support as support
from easel.integrations.planning_result_contract import (
    Condition, NeedProposal, ReviewAnswer, ReviewResponse, SemanticProposal,
    MAX_B_ANSWERS, MAX_REQUEST_BYTES, MAX_RESULT_BYTES, maximum_compact_bytes,
)

REVISION = 'bounded-semantic-review@1'
VISUAL = {'image', 'video'}
SOURCE_POLICY = 'literal-scope-review@1'
LEGACY_INTAKE_POLICY = 'confirmed-planning-intake@1'
AUDIO_INTAKE_POLICY = 'confirmed-planning-intake@2'
P3_INTAKE_POLICY = 'confirmed-planning-intake@3'
RELATIONAL_INTAKE_POLICY = 'confirmed-planning-intake@4'
ADMISSION_INTAKE_POLICY = 'confirmed-planning-intake@5'
INTAKE_POLICY = 'confirmed-planning-intake@6'
INTAKE_POLICIES = frozenset({LEGACY_INTAKE_POLICY, AUDIO_INTAKE_POLICY, P3_INTAKE_POLICY, RELATIONAL_INTAKE_POLICY, ADMISSION_INTAKE_POLICY, INTAKE_POLICY})


def selected_source(scope, inputs, catalog):
    """Bind a literal source position, without interpreting narrative scope."""
    document = inputs['confirmed']['SCENES.md']
    document_sha = hashlib.sha256(document.encode()).hexdigest()
    if scope == 'global':
        if catalog.get('global', {}).get(scope) != document:
            raise ValueError('Global review source does not match the frozen document')
        return {'kind': 'global', 'handle': scope, 'position_kind': 'whole_document',
                'evidence_id': 0, 'document_path': 'SCENES.md', 'document_sha256': document_sha,
                'byte_start': 0, 'byte_end': len(document.encode()), 'line': None}
    positions, offset = {}, 0
    for line_number, complete in enumerate(document.splitlines(keepends=True), 1):
        text = complete.splitlines()[0]
        if text.strip():
            positions[len(positions) + 1] = {'text': text, 'line': line_number,
                'byte_start': offset, 'byte_end': offset + len(text.encode())}
        offset += len(complete.encode())
    matches = [(kind, index, row) for kind in ('scene', 'segment', 'event')
               for index, row in positions.items() if scope == f'{kind}-{index}']
    if len(matches) != 1:
        raise ValueError('Selected review scope has no exact frozen source position')
    kind, _, row = matches[0]
    if catalog.get(kind, {}).get(scope) != row['text']:
        raise ValueError('Selected review source differs from the frozen catalog')
    return {'kind': kind, 'handle': scope, 'position_kind': 'literal_line_not_shot_number',
            'document_sha256': document_sha, **row}


def questions(proposal, inputs, catalog, *, supported=False, source_bound=False):
    """Complete frozen context is independent of A, including all-audio A.

    Lines select existing scopes, never split a candidate obligation. Every
    batch retains the complete SCENES document and global evidence. Queries
    are retrieval hints and excluded from visual obligation review.
    """
    evidence = [
        {'id': 0, 'origin': 'confirmed_original', 'value': inputs['confirmed']},
        {'id': 1, 'origin': 'confirmed_spec', 'value': (inputs.get('proposal') or {}).get('specs', {})},
        {'id': 2, 'origin': 'frozen_director', 'value': inputs['mode_documents']},
        {'id': 3, 'origin': 'creator_boundary', 'value': inputs.get('creator_context', {})},
        {'id': 4, 'origin': 'truth_boundary', 'value': inputs.get('truth_packet', {})},
        {'id': 5, 'origin': 'content_boundary', 'value': inputs.get('content_core', {})},
        {'id': 6, 'origin': 'derived_preparation', 'value': inputs.get('preparation')},
    ]
    rows = []
    def add(kind, target, value):
        rows.append({'question': len(rows), 'kind': kind, 'target': target,
                     'candidate': value, 'evidence': list(range(len(evidence)))})
    for index, need in enumerate(proposal.needs):
        if need.modality not in VISUAL:
            continue  # No new audio semantic reviewer.
        value = need.model_dump(mode='json')
        header = {k: v for k, v in value.items() if k not in {'conditions', 'queries'}}
        add('visual_choices', [index], header)
        binding = selected_source(need.scope, inputs, catalog) if source_bound else None
        if source_bound:
            rows[-1]['selected_source'] = binding
        for ordinal, condition in enumerate(value['conditions']):
            add('complete_obligation', [index, ordinal], condition)
            # An unchanged clause is not the same judgment under a changed
            # scope, modality or purpose. Bind reuse to its semantic header.
            rows[-1]['need_context'] = header
            if source_bound:
                rows[-1]['selected_source'] = binding
    candidates = [{'candidate': i, 'scope': n.scope, 'necessity': n.necessity,
                   'conditions': [c.model_dump(mode='json') for c in n.conditions],
                   'purpose': n.purpose, 'modality': n.modality}
                  for i, n in enumerate(proposal.needs) if n.modality in VISUAL]
    # The current entrance is video; A cannot opt itself out of visual coverage.
    # Scene aliases cover each physical line once. Segment/event are aliases,
    # not independent copies of the same upstream obligation.
    scopes = [('global', catalog['global']['global']), *catalog.get('scene', {}).items()]
    for scope, original in scopes:
        add('frozen_visual_coverage', [scope], {'scope_original': original})
    if not rows or len(rows) > 4096:
        raise ValueError('Complete semantic questions exceed bounded identity capacity')
    return {'schema': REVISION, 'proposal_sha256': digest(proposal.model_dump(mode='json')),
            **({'review_source_policy': SOURCE_POLICY} if source_bound else {}),
            **({'support_policy': support.REVISION} if supported else {}),
            'inputs_sha256': digest(inputs), 'evidence': evidence, 'questions': rows,
            'visual_candidates': candidates,
            'authority': 'eligibility_is_not_entailment; derived_preparation_is_not_new_authorization'}


def review_batches(directory):
    result = []
    for offset in range(0, len(directory['questions']), MAX_B_ANSWERS):
        batch = {**{k: v for k, v in directory.items() if k != 'questions'},
                       'questions': directory['questions'][offset:offset + MAX_B_ANSWERS],
                       'response_schema': ReviewResponse.model_json_schema()}
        if directory.get('support_policy') == support.REVISION:
            batch['source_catalog'] = support.source_catalog(batch)
            batch['response_schema'] = support.response_schema(batch)
        result.append(batch)
    return result


def review_message(batch):
    source_guidance = ('selected_source由程序绑定所选原文行或全局范围；编号不是分镜序号。'
        'global的evidence_id=0与document_path引用本批完整原文，不是省略来源。'
        '核对该Need义务是否确实对应选定来源，全文别处存在相似内容不能替错绑背书。'
        '保留完整上下文，标题与后续正文的关联及跨行义务由你判断，不能机械限于单行授权。'
        if batch.get('review_source_policy') == SOURCE_POLICY else '')
    if batch.get('support_policy') == support.REVISION:
        return ('〔Easel Planning vNext 有界视觉复核〕\n'
            + source_guidance +
            '逐个必填槽位审核完整候选义务、必要性/偏好、模态、原素材/后期/叙事归属及视觉遗漏。'
            'scope覆盖独立于A，A全audio仍查视觉遗漏，不审核声音语义。'
            '只使用Harness提供的工具提交本轮复核结果，严格遵守response_schema；不提出新计划。'
            'question/evidence身份由程序派生，不自行填写。support选择source_catalog的原有handle，'
            '字符串quote必须原样存在于该来源；非字符串值以quote=null绑定原值。'
            'authority与context分开：Preparation不创造授权，成片规格不直接授权native源属性；'
            'output_authority仅用于实际后期义务。引用存在不证明蕴含，不能用一处真实引用'
            '放行整个复合义务。判断还须涵盖所有含义，软偏好不能升级required。'
            '缺支持或不确定时CHALLENGE/UNRESOLVED；不删义务、不猜来源、不写文件、不调用供给或制作。\n'
            + compact(batch))
    return ('〔Easel Planning vNext 有界视觉复核〕\n'
        '逐题按序回答。审核候选对冻结含义的忠实承接、合法具体化、必要性/偏好、模态、'
        '原素材与后期/叙事责任及遗漏。保留完整义务，不重新切割正式字符串。'
        'frozen_visual_coverage独立于A，A全audio也不能自行免审；只查视觉遗漏，不审核声音语义。'
        'evidence只是本题出处资格，不证明蕴含；A不是自己的来源，Preparation不创造作者新授权。'
        '成片规格不自动要求源素材同规格；软风格不升级required。未知或上下文不足用UNRESOLVED，'
        '不放宽义务。ACCEPT给实际支持证据及非空理由。只返回response_schema JSON；'
        '不写文件，不调用工具、供应、生成或制作。\n' + compact(batch))


def compact(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def checked_message(message):
    if len(message.encode()) > MAX_REQUEST_BYTES:
        raise ValueError('Complete semantic context exceeds request capacity; no clipping')
    return message


def validate_answers(value, batch):
    supported = batch.get('support_policy') == support.REVISION
    response = (support.SupportedResponse if supported else ReviewResponse).model_validate(value)
    if [a.question for a in response.answers] != [q['question'] for q in batch['questions']]:
        raise ValueError('Review must cover actual local questions exactly once and in order')
    for answer, question in zip(response.answers, batch['questions'], strict=True):
        if supported:
            support.validate_support(answer, question, batch)
        if (not answer.reason.strip() or len(set(answer.evidence)) != len(answer.evidence)
                or not set(answer.evidence) <= set(question['evidence'])):
            raise ValueError('Review evidence selection or reason is invalid')
        if answer.decision == 'ACCEPT' and (not answer.evidence or not set(answer.evidence) & set(range(6))):
            raise ValueError('Accepted review requires actual independent frozen evidence')
    return response


def structural_targets(value, *, local_query_faults=False, flexible_queries=False):
    """Localize schema leaves only. Ambiguous whole-object faults reject.

    Unknown execution structures are not silently deleted. A missing complete
    plan is not an invitation to regenerate one under a repair label.
    """
    try:
        SemanticProposal.model_validate(value, context={'local_query_faults': local_query_faults,
                                                       'flexible_queries': flexible_queries})
    except ValidationError as exc:
        result = []
        errors = exc.errors(include_input=False, include_url=False)
        for error in errors:
            path = list(error['loc'])
            # Pydantic reports a parent tuple's post-validation size after it
            # discards invalid children. This is a consequence of the leaf
            # fault, not permission to replace the original valid-size tuple.
            if error['type'] == 'too_short' and any(list(e['loc'])[:len(path)] == path
                    and len(e['loc']) > len(path) for e in errors):
                node = value
                for part in path: node = node[part]
                limit = 16 if path == ['needs'] else 12 if path[-1] == 'conditions' else 0
                if isinstance(node, list) and 1 <= len(node) <= limit:
                    continue
            if (error['type'] == 'extra_forbidden' or len(path) < 3
                    or path[0] != 'needs' or type(path[1]) is not int):
                raise ValueError('A fault cannot be localized without replacing valid semantics') from None
            field = path[2]
            if field not in NeedProposal.model_fields:
                raise ValueError('Unknown A repair field') from None
            annotation = NeedProposal.model_fields[field].rebuild_annotation()
            if field == 'conditions':
                if len(path) != 5 or type(path[3]) is not int or path[4] not in Condition.model_fields:
                    raise ValueError('Whole condition fault cannot replace valid siblings') from None
                annotation = Condition.model_fields[path[4]].rebuild_annotation()
            elif len(path) != 3:
                raise ValueError('Nested A fault requires a separately localized contract') from None
            result.append({'kind': 'structural_leaf', 'path': path, 'annotation': annotation,
                           'issue': error['msg']})
        return result
    return []


def confirmed_music_mode(inputs):
    """Only the already-confirmed typed spec; never infer from prose/defaults."""
    proposal = inputs.get('proposal')
    specs = proposal.get('specs') if isinstance(proposal, dict) else None
    mode = specs.get('audio_mode') if isinstance(specs, dict) else None
    return mode if mode in ('mixed', 'music') else None


def intake_selection_schema(schema, inputs):
    """Expose an existing mandatory modality, without choosing its semantics."""
    result = deepcopy(schema)
    if confirmed_music_mode(inputs):
        result['properties']['needs']['contains'] = {
            'type': 'object', 'properties': {
                'modality': {'const': 'bgm'}, 'necessity': {'const': 'required'}},
            'required': ['modality', 'necessity']}
    return result


def intake_targets(value, inputs, *, flexible_queries=False):
    """One shared repair: query leaves plus explicit music-presence obligations.

    The model supplies a missing BGM's intent. This does not review audio
    semantics, select a track, grant generation rights, or alter existing Needs.
    """
    targets = structural_targets(value, local_query_faults=True, flexible_queries=flexible_queries)
    mode = confirmed_music_mode(inputs)
    if not mode:
        return targets
    music = [(i, n) for i, n in enumerate(value['needs']) if n.get('modality') == 'bgm']
    if any(n.get('necessity') == 'required' for _, n in music):
        return targets
    if any(n.get('modality') not in {'image', 'video', 'voice', 'bgm', 'sfx'} for n in value['needs']):
        raise ValueError('Unknown modality prevents a localized music-coverage repair')
    issue = 'Confirmed specs.audio_mode=' + mode + ' requires BGM; preserve frozen sound intent and all existing Needs'
    if not music:
        targets.append({'kind': 'confirmed_music_coverage', 'path': ['bgm'], 'issue': issue})
    elif len(music) == 1:
        path = ['needs', music[0][0], 'necessity']
        targets = [t for t in targets if t['path'] != path]
        targets.append({'kind': 'structural_leaf', 'path': path,
                        'annotation': Literal['required'], 'issue': issue})
    else:
        raise ValueError('Multiple optional BGM candidates cannot be promoted by guesswork')
    return targets


def answer_targets(value, batch):
    """Preserve all valid answers while repairing malformed local answers."""
    if not isinstance(value, dict) or set(value) != {'answers'} or not isinstance(value['answers'], list):
        raise ValueError('Review wrapper cannot be repaired by regenerating a batch')
    rows = value['answers']
    if (len(rows) != len(batch['questions']) or any(not isinstance(a, dict)
            or type(a.get('question')) is not int for a in rows)
            or [a['question'] for a in rows] != [q['question'] for q in batch['questions']]):
        raise ValueError('Unknown, missing or duplicate question identity is reject-only')
    targets = []
    for index, (answer, question) in enumerate(zip(rows, batch['questions'], strict=True)):
        try: validate_answers({'answers': [answer]}, {**batch, 'questions': [question]})
        except ValueError:
            targets.append({'kind': 'answer', 'path': [index], 'issue': 'Invalid local review answer',
                            'question': question})
    return targets


def semantic_targets(directory, answers):
    by_id = {a.question: a for r in answers for a in r.answers}
    result = []
    for question in directory['questions']:
        answer = by_id[question['question']]
        if answer.decision != 'ACCEPT':
            result.append({'kind': question['kind'], 'path': question['target'],
                           'issue': answer.model_dump(mode='json')})
    return result


def recheck(directory, responses, updated):
    """Immutable accepted answers survive; changed coverage is re-reviewed."""
    old = {a.question: a.model_dump(mode='json') for r in responses for a in r.answers}
    def signature(question): return digest({k: v for k, v in question.items() if k != 'question'})
    accepted = {signature(q): old[q['question']] for q in directory['questions']
                if q['kind'] != 'frozen_visual_coverage' and old[q['question']]['decision'] == 'ACCEPT'}
    kept, pending = {}, []
    for question in updated['questions']:
        answer = accepted.get(signature(question))
        if answer is None: pending.append(question)
        else: kept[question['question']] = {**answer, 'question': question['question']}
    return kept, {**updated, 'questions': pending}


def patch_schema(targets, *, support_batch=None, slots=False):
    """Finite program-assigned patch handles, never model-supplied paths."""
    variants, definitions = [], {}
    for index, target in enumerate(targets):
        kind = target['kind']
        if kind == 'answer' and support_batch is not None:
            complete = support.response_schema({**support_batch, 'questions': [target['question']]})
            schema = {**complete['properties'][support.slot(target['question'])], '$defs': complete['$defs']}
        else:
            schema = (TypeAdapter(target['annotation']).json_schema() if kind == 'structural_leaf'
                  else (Condition if kind == 'complete_obligation' else
                        ReviewAnswer if kind == 'answer' else NeedProposal).model_json_schema())
        if kind == 'confirmed_music_coverage':
            schema['properties']['modality'] = {'const': 'bgm', 'type': 'string'}
            schema['properties']['necessity'] = {'const': 'required', 'type': 'string'}
        if kind == 'confirmed_music_coverage':
            schema['properties']['modality'] = {'type': 'string', 'const': 'bgm'}
            schema['properties']['necessity'] = {'type': 'string', 'const': 'required'}
        definitions.update(schema.pop('$defs', {}))
        variants.append({'type': 'object', 'additionalProperties': False,
            'properties': {'target': {'type': 'integer', 'const': index}, 'value': schema},
            'required': ['target', 'value']})
    if not variants or len(variants) > MAX_B_ANSWERS:
        raise ValueError('Local repair exceeds bounded patch capacity')
    schema = {'type': 'object', 'additionalProperties': False, '$defs': definitions,
        'properties': {'patches': {'type': 'array', 'minItems': len(targets), 'maxItems': len(targets),
                                   'items': {'anyOf': variants}}}, 'required': ['patches']}
    if slots:
        schema.update(title='PlanningLocalRepair', properties={f'target-{i:04}': item['properties']['value']
            for i, item in enumerate(variants)}, required=[f'target-{i:04}' for i in range(len(variants))])
    if maximum_compact_bytes(schema) > MAX_RESULT_BYTES:
        raise ValueError('Complete patch response exceeds capture capacity')
    return schema


def decode_patch_slots(value, targets, *, support_batch=None):
    keys = [f'target-{i:04}' for i in range(len(targets))]
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError('Repair slots must cover exact frozen targets')
    rows = []
    for index, (key, target) in enumerate(zip(keys, targets, strict=True)):
        replacement = value[key]
        if target['kind'] == 'answer' and support_batch is not None:
            replacement = support.decode_slots({support.slot(target['question']): replacement},
                {**support_batch, 'questions': [target['question']]})['answers'][0]
        rows.append({'target': index, 'value': replacement})
    return {'patches': rows}


def apply_patches(original, value, targets, *, support_batch=None):
    if not isinstance(value, dict) or set(value) != {'patches'} or not isinstance(value['patches'], list):
        raise ValueError('Repair returns only bounded patches')
    rows = value['patches']
    if (len(rows) != len(targets) or any(not isinstance(r, dict) or set(r) != {'target', 'value'}
            or type(r['target']) is not int for r in rows)
            or [r['target'] for r in rows] != list(range(len(targets)))):
        raise ValueError('Repair targets must match in order exactly once')
    result = deepcopy(original)
    for row, target in zip(rows, targets, strict=True):
        path, kind, replacement = target['path'], target['kind'], row['value']
        if kind == 'structural_leaf':
            adapter = TypeAdapter(target['annotation'])
            # The canonical carrier is JSON data. Typed tuples must become
            # JSON arrays before the unchanged wire/schema admission check.
            replacement = adapter.dump_python(adapter.validate_python(replacement), mode='json')
            node = result
            for part in path[:-1]: node = node[part]
            node[path[-1]] = replacement
        elif kind == 'complete_obligation':
            replacement = Condition.model_validate(replacement).model_dump(mode='json')
            result['needs'][path[0]]['conditions'][path[1]] = replacement
        elif kind == 'visual_choices':
            old = result['needs'][path[0]]
            replacement = NeedProposal.model_validate(replacement).model_dump(mode='json')
            # The header was challenged; conditions were separately reviewed.
            if (replacement['conditions'] != old['conditions'] or replacement['queries'] != old['queries']
                    or replacement['necessity'] != old['necessity'] or replacement['modality'] not in VISUAL):
                raise ValueError('Header patch cannot rewrite accepted conditions, necessity or queries')
            result['needs'][path[0]] = replacement
        elif kind == 'confirmed_music_coverage':
            if path != ['bgm'] or any(n.get('modality') == 'bgm' for n in result['needs']):
                raise ValueError('Music-presence patch cannot replace or duplicate an existing BGM')
            replacement = NeedProposal.model_validate(replacement).model_dump(mode='json')
            if replacement['modality'] != 'bgm' or replacement['necessity'] != 'required':
                raise ValueError('Confirmed music coverage requires a required BGM candidate')
            result['needs'].append(replacement)
        elif kind == 'frozen_visual_coverage':
            replacement = NeedProposal.model_validate(replacement).model_dump(mode='json')
            if replacement['modality'] not in VISUAL:
                raise ValueError('Visual coverage cannot be repaired with an audio Need')
            result['needs'].append(replacement)  # Never remove existing obligations.
        elif kind == 'answer':
            replacement = (support.SupportedAnswer if support_batch is not None else
                           ReviewAnswer).model_validate(replacement).model_dump(mode='json')
            if support_batch is not None:
                validate_answers({'answers': [replacement]}, {**support_batch, 'questions': [target['question']]})
            result['answers'][path[0]] = replacement
        else:
            raise ValueError('Unknown patch contract')
    return result
