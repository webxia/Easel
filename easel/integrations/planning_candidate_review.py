"""Versioned P3 correction inside the existing Planning owner.

No model dispatch, workflow, file write or authorization lives here. The owner
supplies its existing capture/repair callbacks; frozen verification replays the
same algorithm using original replies only. Candidate reports stay immutable.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Annotated, Literal

from jsonschema import Draft202012Validator
from pydantic import Field, ValidationError

from easel.integrations import planning_semantic_review as review
from easel.integrations import planning_review_support as support
from easel.integrations import planning_wire as wire
from easel.integrations.planning_authority import digest
from easel.integrations.planning_result_contract import (
    Carrier, Handle, MAX_B_ANSWERS, MAX_RESULT_BYTES, maximum_compact_bytes,
    semantic_tool_schema,
)
from easel.integrations.semantic_boundary import parse_proposal, parse_review_candidate

POLICY = 'planning-candidate-review@1'
RELATIONAL_POLICY = 'planning-candidate-review@2'
LEGACY_INTAKE_POLICY = 'confirmed-planning-intake@3'
RELATIONAL_INTAKE_POLICY = 'confirmed-planning-intake@4'
ADMISSION_INTAKE_POLICY = 'confirmed-planning-intake@5'
INTAKE_POLICY = 'confirmed-planning-intake@6'
MATERIAL_KINDS = ('visual', 'voice', 'bgm', 'sfx')


class CandidateAnswer(support.SupportedAnswer):
    related_needs: Annotated[tuple[Handle, ...], Field(max_length=16)] = ()


class CandidateResponse(Carrier):
    answers: Annotated[tuple[CandidateAnswer, ...], Field(min_length=1, max_length=MAX_B_ANSWERS)]


class RelationalAnswer(CandidateAnswer):
    coverage: Literal['covered', 'no_material_obligation', 'missing', 'unknown'] | None = None
    required_kinds: Annotated[tuple[Literal['visual', 'voice', 'bgm', 'sfx'], ...], Field(max_length=4)] = ()


class RelationalResponse(Carrier):
    answers: Annotated[tuple[RelationalAnswer, ...], Field(min_length=1, max_length=MAX_B_ANSWERS)]


def enabled(scope):
    return scope.get('transport', {}).get('intake_policy') in {LEGACY_INTAKE_POLICY, RELATIONAL_INTAKE_POLICY, ADMISSION_INTAKE_POLICY, INTAKE_POLICY}


def policy_for(scope):
    return RELATIONAL_POLICY if scope.get('transport', {}).get('intake_policy') in {RELATIONAL_INTAKE_POLICY, ADMISSION_INTAKE_POLICY, INTAKE_POLICY} else POLICY


def _relational(batch):
    return batch.get('candidate_policy') == RELATIONAL_POLICY


def _material_kind(need):
    return 'visual' if need['modality'] in review.VISUAL else need['modality']


def directory_for(proposal, inputs, catalog, *, policy=POLICY):
    if policy not in {POLICY, RELATIONAL_POLICY}:
        raise ValueError('Unknown candidate review policy')
    if policy == RELATIONAL_POLICY:
        # Stored dictionaries are sorted lexically (scene-10 precedes scene-2).
        # New review questions must follow physical source order in both live
        # execution and cold verification, independent of JSON key insertion.
        scenes = catalog.get('scene', {})
        ordered = sorted(scenes, key=lambda key: (int(key.removeprefix('scene-')), key))
        catalog = {**catalog, 'scene': {key: scenes[key] for key in ordered}}
    directory = review.questions(proposal, inputs, catalog, supported=True, source_bound=True)
    # Only already-frozen author text is added; no Provider or rights assertions.
    audio = {key: inputs.get('proposal', {}).get(key) for key in ('sound', 'sound_source')
             if isinstance(inputs.get('proposal'), dict) and key in inputs['proposal']}
    if audio:
        if any(not isinstance(value, str) for value in audio.values()):
            raise ValueError('Confirmed audio source must remain literal')
        directory['evidence'].append({'id': 7, 'origin': 'confirmed_audio', 'value': audio})
    evidence = [row['id'] for row in directory['evidence']]
    bindings = {f'candidate_{i:03}': {'index': i, 'value': need.model_dump(mode='json', exclude={'queries'})}
                for i, need in enumerate(proposal.needs)}
    for row in bindings.values():
        row['sha256'] = digest(row['value'])
    directory.update(candidate_policy=policy, candidate_bindings=bindings)
    questions = directory['questions']
    for question in questions:
        question['evidence'] = evidence
        if question['kind'] == 'visual_choices':
            question['necessity_judgment'] = 'separate need_necessity question; do not rewrite necessity here'
    if policy == RELATIONAL_POLICY:
        visual = {key: row for key, row in bindings.items() if row['value']['modality'] in review.VISUAL}
        for question in questions:
            if question['kind'] == 'frozen_visual_coverage':
                # Existence and modality are mechanical; whether these Needs
                # cover the whole source obligation remains an independent judgment.
                question['coverage_candidates'] = visual
                question['coverage_task'] = 'Map this frozen source obligation to actual visual candidates, not to other source lines.'
    for i, need in enumerate(proposal.needs):
        if need.modality not in review.VISUAL:
            continue
        questions.append({'question': len(questions), 'kind': 'need_necessity',
            'target': [i], 'candidate': bindings[f'candidate_{i:03}']['value'],
            'selected_source': review.selected_source(need.scope, inputs, catalog),
            'evidence': evidence})
    for i, text in enumerate(proposal.unresolved):
        questions.append({'question': len(questions), 'kind': 'unresolved_classification',
            'target': [i], 'candidate': {'report': text, 'report_sha256': digest(text)},
            # Any changed material intent invalidates the previous classification.
            'candidate_context': bindings, 'evidence': evidence})
    if len(questions) > 4096:
        raise ValueError('Complete candidate review exceeds question capacity')
    return directory


def batches(directory):
    result = review.review_batches(directory)
    for batch in result:
        schema = batch['response_schema']
        for question in batch['questions']:
            triage = question['kind'] == 'unresolved_classification'
            coverage = _relational(batch) and question['kind'] == 'frozen_visual_coverage'
            if not (triage or coverage):
                continue
            row = schema['properties'][support.slot(question)]
            handles = list(question['coverage_candidates']) if coverage else list(batch['candidate_bindings'])
            row['properties']['related_needs'] = {'type': 'array', 'maxItems': 16,
                'uniqueItems': True, 'items': {'type': 'string', 'enum': handles} if handles else False}
            row['required'].append('related_needs')
            if coverage:
                row['properties']['coverage'] = {'type': 'string', 'enum':
                    ['covered', 'no_material_obligation', 'missing', 'unknown']}
                row['required'].append('coverage')
            elif _relational(batch):
                row['properties']['required_kinds'] = {'type': 'array', 'maxItems': 4,
                    'uniqueItems': True, 'items': {'type': 'string', 'enum': list(MATERIAL_KINDS)}}
                row['required'].append('required_kinds')
            # Decision/binding coherence is checked by _row after the existing
            # nullable-support wire codec; do not add an unsupported cross-path predicate.
        Draft202012Validator.check_schema(schema)
        if maximum_compact_bytes(schema) > MAX_RESULT_BYTES:
            raise ValueError('Complete candidate response exceeds capture capacity')
    return result


def message_context(batch):
    """Lossless request view; full candidates remain once in the shared table.

    Canonical questions still own complete values for identity and recheck.
    Only the new, unreleased relational policy uses these local references;
    old request text and frozen verification are unchanged.
    """
    if not _relational(batch):
        return batch
    shared = batch['candidate_bindings']
    for row in shared.values():
        if (not isinstance(row, dict) or set(row) != {'index', 'value', 'sha256'}
                or row['sha256'] != digest(row['value'])):
            raise ValueError('Shared candidate reference differs from its full value')
    projected = deepcopy(batch)
    for question in projected['questions']:
        for field in ('coverage_candidates', 'candidate_context'):
            if field not in question:
                continue
            selected = question[field]
            if (not isinstance(selected, dict) or any(key not in shared or row != shared[key]
                                                      for key, row in selected.items())):
                raise ValueError('Question candidate reference differs from the shared table')
            question[field] = {key: {'index': shared[key]['index'], 'sha256': shared[key]['sha256']}
                               for key in selected}
    projected['candidate_reference_policy'] = 'candidate-context-references@1'
    return projected


def message_for(batch):
    transported = {**message_context(batch), 'response_schema': wire.project(batch['response_schema'], 'B', atomic_framing=True).schema,
                   'wire_representation': wire.GUIDANCE}
    prefix = review.review_message(transported).rsplit('\n', 1)[0]
    instruction = ('\nP3候选审核：候选尚未被正式接受。visual_choices只判断其他头部；necessity独立由need_necessity判断，'
        '不要仅因必要性错误重复挑战整个头部。need_necessity的ACCEPT表示当前值忠实，CHALLENGE表示有冻结来源明确要求'
        '该optional候选为required；不得把软偏好升级。required需要降级、语义不明确或依据不足用UNRESOLVED。'
        'unresolved_classification逐条判断整份报告是否仅为已明确意图的下游供给待办：只有报告中的全部要求已由'
        'related_needs指定候选完整承担、没有新决策/权利/授权缺口时才能ACCEPT；该判断不是素材READY或权利许可。'
        '真实冲突、隐含未承接条件、需要新授权或无法判断用CHALLENGE/UNRESOLVED并令related_needs为空。'
        '声音只做该未决性质分类，不新作声音审美、音色或授权判断。不因词语“待检索”就放行。'
        '分类依据必须引用冻结原文；Preparation及候选不是自己的权威来源。queries是待修检索提示，不参与义务审核。')
    if _relational(batch):
        instruction += ('\n关系核对：来源原文存在不等于候选覆盖。frozen_visual_coverage必须同时填写coverage和related_needs。'
            'covered/ACCEPT必须指向coverage_candidates内实际承担全部义务的image/video；缺少候选用missing/CHALLENGE。'
            '仅当本段确实不要求外部视觉素材（例如纯字幕/叙事行）才用no_material_obligation/ACCEPT与空关联；'
            '不能因当前候选为空就说没有视觉义务。不确定用unknown/UNRESOLVED与空关联。'
            'unresolved_classification的required_kinds按原报告含义选择visual/voice/bgm/sfx，而不是根据现有候选倒推。'
            'ACCEPT须有非空类别与对应related_needs，二者类别完全匹配；BGM不能承担图片/视频待办。'
            '真实冲突或没有候选完整承接时用CHALLENGE/UNRESOLVED，两个列表为空；不补造候选。'
            '每题coverage_candidates/candidate_context只列同名candidate_bindings的index和SHA引用；'
            '完整候选正文就在本请求共享candidate_bindings中，必须按同名键读取，不需要外部检索。'
            '引用存在不是覆盖成立，必须核对完整候选实际承担的义务。'
            '每个support.quote只能选择同一冻结来源中的简短连续原文，最多512字符，不粘贴整个分镜或总结改写。')
    return review.checked_message(prefix + instruction + '\n' + review.compact(transported))


def _row(value, question, batch):
    expected = {'decision', 'support', 'reason'}
    triage = question['kind'] == 'unresolved_classification'
    relational = _relational(batch)
    coverage = relational and question['kind'] == 'frozen_visual_coverage'
    if triage or coverage:
        expected.add('related_needs')
    if coverage:
        expected.add('coverage')
    elif triage and relational:
        expected.add('required_kinds')
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError('Candidate answer fields changed')
    key = support.slot(question)
    basic = {k: v for k, v in value.items() if k not in {'related_needs', 'coverage', 'required_kinds'}}
    single = {**batch, 'questions': [question]}
    decoded = support.decode_slots({key: basic}, single)
    review.validate_answers(decoded, single)  # Original provenance/quote checks.
    answer_type = RelationalAnswer if relational else CandidateAnswer
    answer = answer_type.model_validate({**decoded['answers'][0],
        'related_needs': value.get('related_needs', []),
        **({'coverage': value.get('coverage'), 'required_kinds': value.get('required_kinds', [])} if relational else {})})
    needs = answer.related_needs
    if triage:
        if (len(needs) != len(set(needs)) or not set(needs) <= set(batch['candidate_bindings'])
                or (answer.decision == 'ACCEPT') != bool(needs)):
            raise ValueError('Execution report needs exact existing candidate bindings')
    if coverage:
        allowed = question['coverage_candidates']
        if len(needs) != len(set(needs)) or not set(needs) <= set(allowed):
            raise ValueError('Visual coverage must reference existing image/video candidates only')
        expected_decision = {'covered': 'ACCEPT', 'no_material_obligation': 'ACCEPT',
                             'missing': 'CHALLENGE', 'unknown': 'UNRESOLVED'}
        if (answer.decision != expected_decision.get(answer.coverage)
                or (answer.coverage == 'covered') != bool(needs)):
            raise ValueError('Coverage decision requires matching material-candidate witnesses')
    if triage and relational:
        kinds = answer.required_kinds
        actual = {_material_kind(batch['candidate_bindings'][key]['value']) for key in needs}
        if (len(kinds) != len(set(kinds)) or (answer.decision == 'ACCEPT') != bool(kinds)
                or set(kinds) != actual):
            raise ValueError('Pending-report kinds must match related candidate modalities; BGM cannot supply visuals')
    sources = support.source_catalog(batch)
    if ((question['kind'] == 'need_necessity' and answer.decision == 'CHALLENGE')
            or (triage and answer.decision == 'ACCEPT')):
        origins = {'confirmed_original', 'frozen_director'}
        if triage:
            origins.add('confirmed_audio')
        if not any(ref.role == 'authority' and sources[ref.source]['origin'] in origins
                   for ref in answer.support):
            raise ValueError('Candidate correction requires independent frozen authority')
    return answer


def _wrapper(value, batch):
    if not isinstance(value, dict) or set(value) != {support.slot(q) for q in batch['questions']}:
        raise ValueError('Missing or extra candidate-review question; no regenerated wrapper')


def _answer_diagnostics(value, question, batch, error):
    """Bounded errors without copying raw model values into diagnostic fields."""
    schema = {**batch['response_schema']['properties'][support.slot(question)],
              '$defs': batch['response_schema'].get('$defs', {})}
    issues = []
    def leaf_errors(item):
        if item.context:
            for child in item.context:
                yield from leaf_errors(child)
        else:
            yield item
    for parent in Draft202012Validator(schema).iter_errors(value):
        for item in leaf_errors(parent):
            row = {'path': list(item.absolute_path), 'constraint': item.validator}
            if item.validator in {'maxLength', 'minLength', 'maxItems', 'minItems'}:
                row.update(limit=item.validator_value, actual_length=len(item.instance))
            elif item.validator == 'required' and isinstance(item.instance, dict):
                row['missing_fields'] = [k for k in item.validator_value if k not in item.instance]
            elif item.validator == 'type':
                row.update(expected_type=item.validator_value, actual_type=type(item.instance).__name__)
            issues.append(row)
    catalog = support.source_catalog(batch)
    references = value.get('support', []) if isinstance(value, dict) else []
    for index, reference in enumerate(references if isinstance(references, list) else []):
        if not isinstance(reference, dict):
            continue
        source = catalog.get(reference.get('source')) if isinstance(reference.get('source'), str) else None
        path = ['support', index]
        if source is None:
            issues.append({'path': [*path, 'source'], 'constraint': 'unknown_frozen_source'})
            continue
        if reference.get('role') not in source['roles']:
            issues.append({'path': [*path, 'role'], 'constraint': 'source_role', 'allowed_roles': source['roles']})
        if source['evidence_id'] not in question['evidence']:
            issues.append({'path': [*path, 'source'], 'constraint': 'source_not_eligible_for_question'})
        quote, original = reference.get('quote'), source['value']
        if isinstance(original, str) and isinstance(quote, str) and quote not in original:
            issues.append({'path': [*path, 'quote'], 'constraint': 'quote_not_literal_in_selected_source'})
        elif not isinstance(original, str) and quote is not None:
            issues.append({'path': [*path, 'quote'], 'constraint': 'non_text_source_requires_null_quote'})
    if isinstance(error, ValidationError):
        for item in error.errors(include_input=False, include_url=False):
            issues.append({'path': list(item['loc']), 'constraint': item['type']})
    else:
        # The local validators emit fixed explanations, not provider error bodies.
        issues.append({'path': [], 'constraint': 'semantic_binding', 'message': str(error)[:240]})
    return {'errors': issues[:24], 'total_errors': len(issues),
            'more_errors': max(0, len(issues) - 24),
            'instruction': 'Repair only this answer. For maxLength select a shorter exact source quote; do not copy the whole source or fabricate text.'}


def _answer_targets(value, batch):
    _wrapper(value, batch)
    targets = []
    for question in batch['questions']:
        key = support.slot(question)
        try:
            _row(value[key], question, batch)
        except ValueError as error:
            targets.append({'kind': 'candidate_answer', 'path': [key], 'policy': POLICY,
                'old_sha256': digest(value[key]), 'batch_sha256': digest(batch),
                'answer_schema': deepcopy(batch['response_schema']['properties'][key]),
                'answer_defs': deepcopy(batch['response_schema'].get('$defs', {})),
                'issue': (_answer_diagnostics(value[key], question, batch, error) if _relational(batch) else
                          'Repair this invalid local answer only; cite frozen authority and preserve other answers')})
    return targets


def decode_answers(value, batch):
    _wrapper(value, batch)
    response_type = RelationalResponse if _relational(batch) else CandidateResponse
    return response_type(answers=tuple(_row(value[support.slot(q)], q, batch) for q in batch['questions']))


def semantic_targets(directory, responses, original):
    by_id = {a.question: a for response in responses for a in response.answers}
    targets, dispositions = [], []
    for question in directory['questions']:
        answer = by_id[question['question']]
        kind = question['kind']
        if kind == 'unresolved_classification':
            if answer.decision != 'ACCEPT':
                raise ValueError('Creative intent or authorization remains unresolved')
            i = question['target'][0]
            if question['candidate']['report'] != original['unresolved'][i]:
                raise ValueError('Original unresolved report changed')
            dispositions.append({'index': i, 'report': original['unresolved'][i],
                'report_sha256': digest(original['unresolved'][i]), 'classification': 'execution_pending',
                'related_needs': [deepcopy(directory['candidate_bindings'][key]) for key in answer.related_needs],
                'judgment': answer.model_dump(mode='json')})
        elif kind == 'need_necessity':
            if answer.decision == 'ACCEPT':
                continue
            i = question['target'][0]
            need = original['needs'][i]
            if answer.decision != 'CHALLENGE' or need['necessity'] != 'optional':
                raise ValueError('Unresolved necessity or required downgrade is not authorized')
            targets.append({'kind': 'confirmed_necessity', 'policy': POLICY,
                'path': ['needs', i, 'necessity'], 'old_value': 'optional',
                'need_sha256': digest(need), 'inputs_sha256': directory['inputs_sha256'],
                'judgment': answer.model_dump(mode='json'), 'issue': 'Only optional to required, supported by this independent judgment'})
        elif answer.decision != 'ACCEPT':
            if answer.decision == 'UNRESOLVED':
                raise ValueError('Independent semantics remain unresolved')
            targets.append({'kind': kind, 'path': question['target'], 'issue': answer.model_dump(mode='json')})
    if len(dispositions) != len(original['unresolved']):
        raise ValueError('Unresolved-report classification coverage incomplete')
    return targets, dispositions


def patch_schema(targets, *, support_batch=None, slots=False):
    properties, definitions = {}, {}
    for i, target in enumerate(targets):
        if target['kind'] == 'confirmed_necessity':
            field, defs = {'type': 'string', 'const': 'required'}, {}
        elif target['kind'] == 'candidate_answer':
            field, defs = deepcopy(target['answer_schema']), deepcopy(target['answer_defs'])
        else:
            single = review.patch_schema([target], support_batch=support_batch, slots=True)
            field, defs = single['properties']['target-0000'], single.get('$defs', {})
        for name, value in defs.items():
            if name in definitions and definitions[name] != value:
                raise ValueError('Conflicting patch definitions')
            definitions[name] = value
        properties[f'target-{i:04}'] = field
    if not slots or not 1 <= len(properties) <= MAX_B_ANSWERS:
        raise ValueError('Candidate repair requires bounded exact target slots')
    schema = {'title': 'PlanningLocalRepair', 'type': 'object', 'additionalProperties': False,
              '$defs': definitions, 'properties': properties, 'required': list(properties)}
    Draft202012Validator.check_schema(schema)
    if maximum_compact_bytes(schema) > MAX_RESULT_BYTES:
        raise ValueError('Complete candidate patch exceeds capacity')
    return schema


def decode_patch_slots(value, targets, *, support_batch=None):
    keys = [f'target-{i:04}' for i in range(len(targets))]
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError('Candidate repair must match exact target slots')
    return {'patches': [{'target': i, 'value': value[key]} for i, key in enumerate(keys)]}


def apply_patches(original, value, targets, *, support_batch=None):
    if (not isinstance(value, dict) or set(value) != {'patches'} or not isinstance(value['patches'], list)
            or len(value['patches']) != len(targets) or any(not isinstance(r, dict) or set(r) != {'target', 'value'}
            or type(r['target']) is not int or r['target'] != i for i, r in enumerate(value['patches']))):
        raise ValueError('Candidate repair target identity changed')
    result = deepcopy(original)
    for row, target in zip(value['patches'], targets, strict=True):
        path, replacement, kind = target['path'], row['value'], target['kind']
        if kind in {'confirmed_necessity', 'candidate_answer'} and target.get('policy') != POLICY:
            raise ValueError('Candidate repair policy missing')
        if kind == 'confirmed_necessity':
            if (len(path) != 3 or path[0] != 'needs' or path[2] != 'necessity'
                    or type(path[1]) is not int or not 0 <= path[1] < len(original['needs'])):
                raise ValueError('Necessity target path changed')
            old = original['needs'][path[1]]
            if (target['old_value'] != 'optional' or old['necessity'] != 'optional'
                    or digest(old) != target['need_sha256'] or replacement != 'required'
                    or target['judgment']['decision'] != 'CHALLENGE'):
                raise ValueError('Necessity patch cannot rebind, downgrade or rewrite a Need')
            result['needs'][path[1]]['necessity'] = 'required'
        elif kind == 'candidate_answer':
            if len(path) != 1 or path[0] not in original or digest(original[path[0]]) != target['old_sha256']:
                raise ValueError('Original candidate answer changed')
            result[path[0]] = deepcopy(replacement)  # Full original support validation follows.
        else:
            result = review.apply_patches(result, {'patches': [{'target': 0, 'value': replacement}]},
                                          [target], support_batch=support_batch)
    return result


def evaluate(initial, scope, view, invoke, candidate, repair, *, max_calls):
    """Same deterministic evaluation for live owner and read-only frozen replay."""
    inputs, catalog = scope['inputs'], scope['catalog']
    flexible = scope.get('transport', {}).get('intake_policy') == 'confirmed-planning-intake@6'
    lineage = None
    repairs = 0
    def fix(stage, original, targets, context=None):
        nonlocal lineage, repairs
        if repairs:
            raise ValueError('Whole Planning shared repair allowance exhausted')
        repairs += 1
        value, output = repair(stage, original, targets, context)
        lineage = {'stage': stage, 'targets': [{k: v for k, v in t.items() if k != 'annotation'} for t in targets],
                   'output': output}
        return value
    value = deepcopy(initial)
    pending = review.intake_targets(value, inputs, flexible_queries=flexible)
    try:
        proposal = parse_review_candidate(value, catalog, query_diagnostics=True, flexible_queries=flexible)
    except ValidationError:
        # Unreviewable local typed leaves use the original one repair first.
        if not pending:
            raise
        value = fix('A', value, pending)
        proposal = parse_review_candidate(value, catalog, flexible_queries=flexible)
        pending = review.intake_targets(value, inputs, flexible_queries=flexible)
    query_paths = [tuple(t['path']) for t in pending if t['kind'] == 'structural_leaf' and t['path'][-1] == 'queries']
    # Check the original JSON types before Pydantic normalization. A candidate
    # view must not launder an unrequested boolean/number coercion into ACCEPT.
    for error in Draft202012Validator(semantic_tool_schema(catalog, compiled=True, flexible_queries=flexible)).iter_errors(value):
        if not any(tuple(error.absolute_path)[:len(path)] == path for path in query_paths):
            raise ValueError('Candidate violates a non-query canonical constraint')
    value = proposal.model_dump(mode='json')
    if any(t['kind'] == 'confirmed_music_coverage' for t in pending) and len(value['needs']) >= semantic_tool_schema(catalog, compiled=True, flexible_queries=flexible)['properties']['needs']['maxItems']:
        raise ValueError('Required BGM cannot fit without removing a Need')
    directory = directory_for(proposal, inputs, catalog, policy=policy_for(scope))
    view.check_review(directory)
    initial_directory = directory
    initial_value = deepcopy(value)
    initial_responses, responses = [], []
    initial_batches = batches(directory)
    coverage = sum(q['kind'] == 'frozen_visual_coverage' for q in directory['questions'])
    if 2 + len(initial_batches) + 1 + (16 * 14 + coverage + 16 + 47) // 48 > max_calls:
        raise ValueError('Complete candidate review/recheck exceeds original call capacity')
    def ask(key, batch, *, recheck=False):
        message = message_for(batch)
        raw = invoke(key, message, batch['response_schema'])
        decoded = candidate(key, raw, batch['response_schema'])
        faults = _answer_targets(decoded, batch)
        if faults:
            if recheck:
                raise ValueError('Recheck answer invalid after the single repair')
            decoded = fix(key, decoded, faults, batch)
        return raw, decode_answers(decoded, batch)
    # Precompute all full messages before any independent review dispatch.
    for batch in initial_batches:
        message_for(batch)
    for i, batch in enumerate(initial_batches):
        raw, response = ask(f'B-{i:03}', batch)
        initial_responses.append(raw)
        responses.append(response)
    semantic, _ = semantic_targets(directory, responses, value)
    targets = [*pending, *semantic]
    before_semantic = [r.model_dump(mode='json') for r in responses]
    if targets:
        value = fix('semantic', value, targets)
        proposal = parse_review_candidate(value, catalog, flexible_queries=flexible)
        if review.intake_targets(value, inputs, flexible_queries=flexible):
            raise ValueError('Candidate intake still invalid after the single repair')
        Draft202012Validator(semantic_tool_schema(catalog, compiled=True, flexible_queries=flexible)).validate(value)
        value = proposal.model_dump(mode='json')
        updated = directory_for(proposal, inputs, catalog, policy=policy_for(scope))
        view.check_review(updated)
        kept, to_review = review.recheck(directory, responses, updated)
        pending_batches = batches(to_review)
        for batch in pending_batches:
            message_for(batch)
        for i, batch in enumerate(pending_batches):
            _, response = ask(f'B-recheck-{i:03}', batch, recheck=True)
            for answer in response.answers:
                kept[answer.question] = answer.model_dump(mode='json')
        directory = updated
        response_type = RelationalResponse if _relational(directory) else CandidateResponse
        answer_type = RelationalAnswer if _relational(directory) else CandidateAnswer
        responses = [response_type(answers=tuple(answer_type.model_validate(kept[q['question']])
                     for q in batch['questions'])) for batch in batches(directory)]
    remaining, dispositions = semantic_targets(directory, responses, value)
    if remaining or review.intake_targets(value, inputs, flexible_queries=flexible):
        raise ValueError('Candidate remains challenged after bounded review')
    # Formal projection only: original reports remain in captures and this trace.
    # Every excluded report has independently accepted, still-current Need bindings.
    formal = parse_proposal({**value, 'unresolved': []}, catalog, flexible_queries=flexible)
    return {'proposal': formal, 'directory': directory, 'responses': responses,
        'initial_review_value': initial_value, 'initial_responses': initial_responses,
        'before_semantic': before_semantic, 'repair': lineage,
        'trace': {'policy': policy_for(scope), 'original_sha256': digest(initial),
            'initial_review_sha256': digest(initial_directory), 'reviewed_candidate': value,
            'execution_pending_reports': dispositions, 'repair_calls': repairs}}
