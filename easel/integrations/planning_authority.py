"""Verified Planning provenance, not a semantic authorization oracle.

The existing B model judges entailment and legitimate Director realization.
This module owns origin, scope, known field strength, applied-operation records
and complete review of values consumed downstream. It never rewrites a Need.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from easel.integrations.hypit.secrets import SecretRedactor
from easel.materials.application.query_hints import QUERY_FIELDS

REVISION = 'planning-authority-catalog@1'
RELATIONS = frozenset({'upstream_obligation', 'director_realization', 'preference',
                       'postproduction', 'unresolved', 'operational'})
SOFT_PATHS = frozenset({'constraints/preferred_visual_details', 'constraints/preferred_style',
                        'modality/visual_style'})
MAX_CONTROLS_PER_NEED = 32
MAX_CONTROLS_PER_BATCH = 128


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def load_inputs(attempt, canonical, planning_context, mode, *, allow_missing_canonical=False):
    """Read only this Attempt's verified handoff; no global Mode or A input."""
    from easel.integrations.hypit.handoff import verify_handoff_directory
    from easel.creation_preparation import _canonical_bytes, _sha256
    from easel.creator_proposal import validate_video_plan

    package = Path(attempt['workspace']['path']) / 'handoff'
    manifest, _ = verify_handoff_directory(package, attempt['handoff']['hash'])
    if (manifest['creation_id'] != attempt['creation_id']
            or manifest['handoff_id'] != attempt['handoff']['handoff_id']):
        raise ValueError('Planning来源Handoff身份不符')
    if (set(canonical) != {'SCRIPT.md', 'SCENES.md', 'TREATMENT.md'}
            or any(not isinstance(v, str) for v in canonical.values())):
        raise ValueError('Planning来源需要完整确认三文件')
    for name, text in canonical.items():
        path = package.parent / 'planning' / name
        if path.is_symlink() or (not path.exists() and not allow_missing_canonical) or (path.exists() and path.read_bytes() != text.encode()):
            raise ValueError('Planning来源确认原件变化')
    refs = planning_context['context_refs']
    documents = {}
    for key in ('content_core', 'truth_packet', 'creator_context'):
        ref = manifest['creator_context'] if key == 'creator_context' else manifest['content'][key]
        raw = (package / ref['path']).read_bytes()
        value = json.loads(raw)
        if key in planning_context and planning_context[key] != value:
            raise ValueError('Planning来源与冻结上下文正文不符：' + key)
        if key + '_sha256' in refs and refs[key + '_sha256'] != ref['hash']:
            raise ValueError('Planning来源与冻结上下文摘要不符：' + key)
        documents[key] = value
    mode_ref = manifest['creative_mode']
    mode_documents = {entry['path']: (package / mode_ref['path'] / entry['path']).read_text()
                      for entry in mode_ref['files']}
    if json.loads(mode_documents['mode.json']) != mode:
        raise ValueError('Planning来源Mode不是当前冻结版')
    if refs.get('creative_mode_sha256') != mode_ref['hash']:
        raise ValueError('Planning来源Mode摘要不符')
    request = manifest['production_request']
    brief = request.get('production_brief')
    if brief is not None:
        brief_hash = _sha256(_canonical_bytes(brief))
        if (request.get('production_brief_sha256') != brief_hash
                or refs.get('production_brief_sha256') != brief_hash):
            raise ValueError('Planning来源Production Brief未绑定实际原件')
    elif 'production_brief_sha256' in refs:
        raise ValueError('Planning来源Production Brief仅有摘要无正文')
    proposal = request.get('video_plan')
    if proposal is not None:
        if not validate_video_plan(proposal):
            raise ValueError('Planning来源确认方案Schema/摘要无效')
        expected = {'SCRIPT.md': proposal['script'], 'SCENES.md': proposal['scenes'],
                    'TREATMENT.md': proposal['treatment'] + '\n\n## 声音设计\n' + proposal['sound']}
        if expected != canonical:
            raise ValueError('Planning来源确认方案与三原件不符')
        if brief is not None and any(brief.get(k) != v for k, v in proposal['specs'].items()):
            raise ValueError('Planning来源确认规格与Production Brief不符')
    result = {'schema': 'planning-authority-inputs@1', 'handoff_sha256': attempt['handoff']['hash'],
              'confirmed': dict(canonical), 'proposal': proposal, 'preparation': brief,
              'mode_documents': mode_documents, **documents}
    if proposal is not None and proposal.get('schema') == 'easel-video-proposal@3':
        from easel import creation
        from easel.integrations.voice_identity import require_binding
        work = creation.get_creation(attempt['creation_id'])
        binding = require_binding(work, script=canonical['SCRIPT.md'])
        if proposal != work['delivery']['video_plan'] or binding != request.get('voice_binding'):
            raise ValueError('Planning确认旁白身份与冻结Handoff不一致')
        result['voice_binding'] = binding
    if SecretRedactor.contains_secret(result):
        raise ValueError('Planning来源包含疑似凭证，未提交')
    return result


def catalog(inputs, operations=()):
    """Literal origins with eligibility only; primary never means sufficient."""
    if inputs.get('schema') != 'planning-authority-inputs@1':
        raise ValueError('Planning来源输入协议无效')
    rows = []

    def append(origin, path, value, relations, *, primary=True, scopes=None, span=None, operation=None):
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)
        rows.append({'id': len(rows), 'origin': origin, 'path': path, 'text': text,
            'sha256': hashlib.sha256(text.encode()).hexdigest(), 'span': span,
            'relations': list(relations), 'primary': primary, 'scopes': scopes,
            **({'operation': operation} if operation is not None else {})})

    def lines(origin, path, text, relations, *, primary=True, scene=False):
        start, ordinal = 0, 0
        for line in text.splitlines(keepends=True):
            if line.strip():
                ordinal += 1
                scopes = ['global', *(f'{k}-{ordinal}' for k in ('scene', 'segment', 'event'))] if scene else None
                append(origin, path, line, relations, primary=primary and not line.lstrip().startswith('#'),
                       scopes=scopes, span=[start, start + len(line)])
            start += len(line)

    interpret = ('upstream_obligation', 'director_realization', 'preference', 'postproduction')
    confirmed = inputs['confirmed']
    lines('confirmed_scene', 'SCENES.md', confirmed['SCENES.md'], interpret, scene=True)
    lines('confirmed_treatment', 'TREATMENT.md', confirmed['TREATMENT.md'], interpret)
    lines('confirmed_script', 'SCRIPT.md', confirmed['SCRIPT.md'],
          ('upstream_obligation', 'postproduction'), primary=False)
    proposal = inputs.get('proposal')
    if proposal is not None:
        for key, value in sorted(proposal['specs'].items()):
            append('confirmed_spec', 'video_plan/specs/' + key, value, ('upstream_obligation',))
    documents = inputs['mode_documents']
    for name, text in sorted(documents.items()):
        if name == 'mode.json':
            mode = json.loads(text)
            if mode.get('visual_material_style'):
                append('mode_soft', 'mode.json/visual_material_style', mode['visual_material_style'], ('preference',))
            if isinstance(mode.get('summary'), str):
                append('mode_goal', 'mode.json/summary', mode['summary'],
                       ('director_realization', 'preference', 'postproduction'))
            if mode.get('defaults'):
                append('mode_defaults', 'mode.json/defaults', mode['defaults'], ('preference',), primary=False)
        else:
            lines('director_document', name, text, interpret)
    for key in ('creator_context', 'truth_packet', 'content_core'):
        if key in inputs:
            append('derived_' + key, key, inputs[key], ('postproduction',), primary=False)
    if inputs.get('preparation') is not None:
        append('derived_preparation', 'production-brief.json', inputs['preparation'],
               ('postproduction',), primary=False)
    for operation in operations:
        if set(operation) != {'need_index', 'path', 'value', 'rule', 'input'}:
            raise ValueError('程序实际操作记录形状无效')
        append('program_operation', operation['path'], operation['value'], ('operational',),
               operation=operation)
    return {'schema': REVISION, 'inputs_sha256': digest(inputs), 'sources': rows,
            'semantics': 'eligibility_is_not_entailment_or_authorization'}


def applied_operations(draft, plan, mode):
    """Record actual defaults, not values merely resembling a default."""
    operations = []
    for index, (item, need) in enumerate(zip(draft.needs, plan.needs)):
        if need.media_type.value not in {'image', 'video'}:
            continue
        def add(path, value, rule, input_value):
            operations.append({'need_index': index, 'path': path, 'value': value,
                               'rule': rule, 'input': input_value})
        if 'desired_options' not in item.model_fields_set:
            add('desired_options', need.desired_options, 'semantic-need-default@1', {'field_absent': True})
        if not item.constraints.get('preferred_style') and need.constraints.get('preferred_style'):
            style = getattr(item.modality_spec, 'visual_style', None) or mode.get('visual_material_style')
            add('constraints/preferred_style', need.constraints['preferred_style'], 'apply-mode-style@1',
                {'source': 'candidate_visual_style' if getattr(item.modality_spec, 'visual_style', None) else 'mode_visual_material_style',
                 'value': style})
        if item.modality_spec.kind == 'video' and 'generate_audio' not in item.modality_spec.model_fields_set:
            add('modality/generate_audio', need.modality_spec.generate_audio, 'video-spec-default@1', {'field_absent': True})
    return operations


def control_rows(need, need_index):
    """Final typed values, separate from canonical quoted clause units."""
    rows = []
    def append(path, value):
        if value is None or value == [] or value == ():
            return
        rows.append({'path': path, 'value': value, 'value_sha256': digest(value),
                     'need': need.need_id, 'need_index': need_index,
                     'scope_ref': need.scope.ref, 'soft': path in SOFT_PATHS})
    append('importance', need.importance.value)
    append('desired_options', need.desired_options)
    if need.duration_hint:
        append('duration_hint/target_seconds', need.duration_hint.target_seconds)
    for key, value in sorted(need.constraints.items()):
        if key not in QUERY_FIELDS:
            append('constraints/' + key, value)
    for key, value in need.modality_spec.model_dump(mode='json').items():
        append('modality/' + key, value)
    if len(rows) > MAX_CONTROLS_PER_NEED:
        raise ValueError('视觉控制项超出32项有界合同；未删项或提交')
    return rows


def eligible(source, relation, scope_ref, *, control=None):
    if relation not in source['relations'] or (source['scopes'] is not None and scope_ref not in source['scopes']):
        return False
    if relation == 'operational':
        operation = source.get('operation')
        return bool(control is not None and operation
            and operation['need_index'] == control['need_index']
            and operation['path'] == control['path']
            and digest(operation['value']) == control['value_sha256'])
    if source['origin'] == 'confirmed_spec':
        if control is None:
            return False
        field = source['path'].split('/')[-1]
        applicable = {'aspect_ratio': {'modality/aspect_ratio', 'constraints/orientation'},
                      'duration_seconds': {'duration_hint/target_seconds', 'constraints/min_duration',
                          'constraints/min_duration_seconds', 'constraints/max_duration',
                          'constraints/max_duration_seconds', 'constraints/duration_seconds',
                          'constraints/target_duration_seconds'},
                      'audio_mode': {'modality/generate_audio', 'modality/kind'}, 'language': set()}
        return control['path'] in applicable.get(field, set())
    return True


def basis_schema(directory, scope_ref, *, control=None):
    choices = []
    relations = RELATIONS - {'operational'} if control is None else (
        {'preference', 'operational', 'unresolved'} if control['soft'] else
        {'upstream_obligation', 'director_realization', 'operational', 'unresolved'})
    for relation in sorted(relations):
        ids = [source['id'] for source in directory['sources'] if eligible(source, relation, scope_ref, control=control)]
        nonempty = relation in {'upstream_obligation', 'director_realization', 'operational'}
        choices.append({'type': 'object', 'additionalProperties': False,
            'required': ['relation', 'source_ids'], 'properties': {
                'relation': {'const': relation},
                'source_ids': {'type': 'array', 'minItems': int(nonempty), 'maxItems': 4,
                    'uniqueItems': True, 'items': {'type': 'integer', 'enum': ids} if ids else False}}})
    return {'oneOf': choices}


def validate_basis(basis, directory, scope_ref, *, kind=None, control=None):
    if not isinstance(basis, dict) or set(basis) != {'relation', 'source_ids'}:
        raise ValueError('依据仅允许relation/source_ids；不能自填授权标签')
    relation, ids = basis['relation'], basis['source_ids']
    if (not isinstance(relation, str) or relation not in RELATIONS or not isinstance(ids, list) or len(ids) > 4
            or any(type(value) is not int for value in ids) or len(set(ids)) != len(ids)):
        raise ValueError('依据关系/引用形状无效')
    allowed = {'required': {'upstream_obligation', 'director_realization'},
               'preference': {'preference'}, 'postproduction': {'postproduction'},
               'unresolved': {'unresolved'}}
    if control is None:
        if relation not in allowed.get(kind, set()):
            raise ValueError('原文kind与依据关系不一致')
    elif kind == 'UNRESOLVED':
        if relation != 'unresolved':
            raise ValueError('歧义control不能伪装已接受')
    elif kind != 'ACCEPT' or relation not in (
            {'preference', 'operational'} if control['soft'] else
            {'upstream_obligation', 'director_realization', 'operational'}):
        raise ValueError('硬控制不能用偏好/后期放行，也不能丢弃原值')
    by_id = {source['id']: source for source in directory['sources']}
    if any(value not in by_id or not eligible(by_id[value], relation, scope_ref, control=control) for value in ids):
        raise ValueError('依据引用未知、scope不适用或字段资格不符')
    if relation in {'upstream_obligation', 'director_realization', 'operational'}:
        if not ids or not any(by_id[value]['primary'] for value in ids):
            raise ValueError('硬条件/控制缺少合适的主要依据；候选不能自证')
    if control is not None and kind == 'UNRESOLVED':
        raise ValueError('control仍有歧义，整个Planning不提交')
