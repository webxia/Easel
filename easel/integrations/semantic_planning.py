"""Product Planning v3: one semantic draft, program-owned identity and references.

Pure compilation and durable application orchestration. Material Domain and its
admission rules remain authoritative; model labels never authorize progression.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
from typing import Annotated, Any, Literal, get_args
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from easel.materials.domain import (
    MaterialPlan, MaterialNeed, MediaType, NeedImportance, NeedScope, NeedIntent,
    DurationHint, ImageNeedSpec, VideoNeedSpec, BgmNeedSpec, SfxNeedSpec,
    VoiceNeedSpec, VoiceIdentityRef, ContinuityRef,
)
from easel.materials.application.visual_contract import (
    digest, sources_for, classification_units, compilation_input, bind_classifications,
    validate_compilation, read_planning_requirements, KINDS,
)
from easel.materials.application.query_hints import query_hints, QUERY_FIELDS
from easel.materials.application.need_constraints import validate_modality_constraints
from easel.materials.application.compiler import NeedCompiler
from easel.materials.application.voice_delivery import validate_voice_delivery
from easel.integrations.hypit.secrets import SecretRedactor

AUTHORITY_POLICY = 'semantic-planning-compiler@7'
POLICY = AUTHORITY_POLICY
UNIT_POLICY = 'indexed-unit-classification@8'
REVIEW_TARGET = {'schema': 'material-review-target@4',
 'scope': 'original_asset',
 'required_evidence': 'observable_in_asset',
 'non_asset_obligation': 'narrative_or_postproduction',
 'uncertain': 'unresolved',
 'precedence': ['predicate_and_purpose', 'target', 'strength', 'kind'],
 'relation_rules': {'asset_property_with_purpose': 'classify_asset_property_by_source_strength',
                    'pure_postproduction': 'actual_editing_or_narrative_obligation',
                    'mixed_independent_obligations': 'unresolved_if_not_losslessly_classifiable',
                    'interpretation': 'semantic_relation_not_word_order_or_keywords',
                    'asset_intrinsic_vs_timeline_use': 'classify_obligation_target_not_repeated_subject_or_field'},
 'counterfactual': {'scope': 'obligation_target_not_editability',
                    'source_condition': 'remains_about_original_asset_even_if_later_edit_can_remove_it',
                    'timeline_or_expression': 'same_asset_can_be_used_differently_without_new_intrinsic_condition',
                    'repeated_subject': 'repetition_in_usage_does_not_create_or_erase_source_obligation',
                    'independent_mixed': 'preserve_unresolved_when_not_losslessly_classifiable'},
 'authority': 'upstream_eligibility_is_not_entailment',
 'candidate_is_not_own_authority': True}
MAX_FILE_BYTES = 256 * 1024
MAX_BATCH_UNITS = 40


def _compiler_policy(value):
    # Current compilation cannot silently select an earlier policy.
    policy = AUTHORITY_POLICY if value is None else value
    if policy != AUTHORITY_POLICY:
        raise ValueError('旧语义编译政策不再用于新生产')
    return policy


class SemanticVoiceSpec(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Literal['voice'] = 'voice'
    identity: VoiceIdentityRef
    delivery_description: str | None = None


class SemanticNeed(BaseModel):
    model_config = ConfigDict(extra='forbid')
    scope: NeedScope
    role: str = Field(min_length=1)
    intent: NeedIntent
    importance: NeedImportance
    duration_hint: DurationHint | None = None
    desired_options: int = Field(default=1, ge=1)
    continuity_refs: tuple[ContinuityRef, ...] = ()
    constraints: dict[str, Any] = Field(default_factory=dict)
    queries: list[str] = Field(default_factory=list)
    modality_spec: Annotated[ImageNeedSpec | VideoNeedSpec | SemanticVoiceSpec | BgmNeedSpec | SfxNeedSpec,
                             Field(discriminator='kind')]


class SemanticPlanningDraft(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_: Literal['semantic-planning-draft@1'] = Field(alias='schema')
    policy: dict[str, str] = Field(default_factory=lambda: {'strategy': 'bulk_first'})
    needs: tuple[SemanticNeed, ...] = Field(min_length=1)


class SemanticPlanningError(ValueError):
    def __init__(self, stage, issues):
        self.stage = stage
        self.issues = issues
        super().__init__(json.dumps({'stage': stage, 'issues': issues}, ensure_ascii=False))


def planning_input_schema(catalog):
    """Project existing consumer constraints; schema never replaces compilation."""
    from easel.materials.application.voice_delivery import voice_delivery_schema
    from easel.materials.application.need_constraints import VOICE_ALIASES
    schema = SemanticPlanningDraft.model_json_schema()
    definitions = schema['$defs']
    need = definitions['SemanticNeed']
    scalar = {'type':[{str:'string',int:'integer',float:'number',bool:'boolean'}[t]
                      for t in NeedCompiler._FILTER_VALUE_TYPES]}
    constraints = {'type':'object','propertyNames':{'pattern':r'\S'},
        'additionalProperties':scalar,'properties':{
            **{key:False for key in sorted(QUERY_FIELDS | VOICE_ALIASES)},
            'voice_delivery':False,'preferred_visual_details':False}}
    need['properties']['constraints'] = constraints
    need['properties']['scope'] = {'allOf':[{'$ref':'#/$defs/NeedScope'}, {'oneOf':[
        {'properties':{'type':{'const':kind},'ref':{'enum':sorted(catalog[kind])}}}
        for kind in ('global','scene','segment','event') if catalog.get(kind)]}]}
    continuity = need['properties']['continuity_refs']
    if catalog.get('continuity'):
        continuity['items'] = {'allOf':[{'$ref':'#/$defs/ContinuityRef'},
            {'properties':{'ref':{'enum':sorted(catalog['continuity'])}}}]}
    else: continuity['maxItems'] = 0
    need['allOf'] = []
    for kind in ('image','video','voice','bgm','sfx'):
        properties = dict(constraints['properties'])
        if kind in {'image','video'}:
            properties['preferred_visual_details'] = {'type':'string','pattern':r'\S'}
        if kind == 'voice': properties['voice_delivery'] = voice_delivery_schema()
        properties['media_type'] = {'const':kind if kind in {'image','video'} else 'audio'}
        query = {'type':'array','items':{'type':'string','maxLength':100},
                 'minItems':3,'maxItems':3,'uniqueItems':True}
        if kind not in {'image','video'}:query = {'anyOf':[query,{'type':'array','maxItems':0}]}
        need['allOf'].append({'if':{'properties':{'modality_spec':{'properties':{'kind':{'const':kind}}}}},
            'then':{'properties':{'constraints':{**constraints,'properties':properties},'queries':query},
                    **({'required':['queries']} if kind in {'image','video'} else {})}})
    # Base properties must allow the conditional, modality-owned exceptions.
    constraints['properties']['voice_delivery'] = voice_delivery_schema()
    constraints['properties']['preferred_visual_details'] = {'type':'string','pattern':r'\S'}
    identities = []
    for ref, row in sorted(catalog.get('voice',{}).items()):
        assets = row.get('reference_asset_ids',[])
        identities.append({'properties':{'source':{'const':row['source']},'reference':{'const':ref},
            'reference_asset_ids':{'type':'array',**({'items':{'enum':assets}} if assets else {'maxItems':0})},
            'consent_ref':{'enum':list(dict.fromkeys([None,row.get('consent_ref')]))}}})
    definitions['SemanticVoiceSpec']['properties']['identity'] = {'allOf':[
        {'$ref':'#/$defs/VoiceIdentityRef'}, {'anyOf':identities} if identities else False]}
    return schema


PLANNING_INPUT_RULES = (
    '\nA只声明实际需要获取的素材；正文叠加、字幕布局等后期义务留在冻结SCENES/TREATMENT，'
    '相关语义可保留于intent但不得额外建立采购Need；不能把所有function默认为后期。'
    '主体、数量、源动作、禁令写入完整intent描述，不复制成must_contain等列表filter。'
    'constraints仅为已有标量检索控制、显式视觉软偏好或Voice专属voice_delivery；'
    '每条Need的queries字段与constraints并列，交三个不同英文短语，不在constraints重复任何查询字段。'
    '引用只能选本轮catalog；continuity为空则不交引用。'
    'policy可省略使用程序默认strategy；若提供则值全部为字符串，不能制造事实、授权或预算。'
    'Schema描述结构，完整程序编译仍会检查跨字段、查询及来源合法性。\n'
)


def problem(field, message, code='contract_invalid'):
    return {'field': field, 'code': code, 'message': SecretRedactor.redact_text(message)}


def parse_draft(value):
    try:
        if isinstance(value, (str, bytes)):
            value = read_planning_requirements(value.decode('utf-8') if isinstance(value, bytes) else value)
        return SemanticPlanningDraft.model_validate_json(json.dumps(value, ensure_ascii=False))
    except ValidationError as exc:
        raise SemanticPlanningError('A', [problem('.'.join(map(str, e['loc'])), e['msg'], e['type'])
                                          for e in exc.errors(include_input=False, include_context=False)]) from exc
    except (ValueError, UnicodeError) as exc:
        raise SemanticPlanningError('A', [problem('$', str(exc), 'json_invalid')]) from exc


def apply_defaults(plan, mode, script):
    """The existing soft Mode/Voice binding, shared with formal persistence."""
    bound = []
    for need in plan.needs:
        spec = need.modality_spec
        style = getattr(spec, 'visual_style', None) or mode.get('visual_material_style')
        if style and need.media_type in {MediaType.IMAGE, MediaType.VIDEO} and not need.constraints.get('preferred_style'):
            need = need.model_copy(update={'constraints': {**need.constraints, 'preferred_style': style}})
        if getattr(spec, 'kind', None) == 'voice':
            controls = need.constraints.get('voice_delivery', {})
            if not isinstance(controls, dict):
                raise ValueError('Voice Need的voice_delivery必须为参数对象')
            defaults = mode.get('voice_delivery') or {}
            if defaults or controls:
                controls = validate_voice_delivery({**defaults, **controls})
                need = need.model_copy(update={'constraints': {**need.constraints, 'voice_delivery': controls}})
            if need.importance is NeedImportance.REQUIRED:
                if spec.identity is None or spec.text_ref not in {None, 'planning/SCRIPT.md'}:
                    raise ValueError('Required Voice Need must declare provider-neutral identity and reference the frozen SCRIPT')
                spec = spec.model_copy(update={'text_ref': 'planning/SCRIPT.md',
                                               'text_sha256': hashlib.sha256(script.encode()).hexdigest()})
                need = need.model_copy(update={'modality_spec': spec})
        bound.append(need)
    return MaterialPlan.model_validate_json(plan.model_copy(update={'needs': tuple(bound)}).to_json())


def _compile_need(item, *, index, identity, allowed_refs):
    prefix = f'needs.{index}'
    issues = []
    if allowed_refs is not None:
        if item.scope.ref not in allowed_refs.get(item.scope.type.value, set()):
            issues.append(problem(prefix, 'scope.ref不存在于冻结来源；允许集合：' + repr(sorted(allowed_refs.get(item.scope.type.value, set())))))
        for ref in item.continuity_refs:
            if ref.ref not in allowed_refs.get('continuity', set()):
                issues.append(problem(prefix, 'continuity引用不存在于冻结来源'))
        if item.modality_spec.kind == 'voice' and 'voice' in allowed_refs:
            voice = item.modality_spec.identity
            entry = allowed_refs['voice'].get(voice.reference)
            if (not entry or entry['source'] != voice.source.value
                or not set(voice.reference_asset_ids).issubset(entry.get('reference_asset_ids', []))
                or voice.consent_ref not in {None, entry.get('consent_ref')}):
                issues.append(problem(prefix, 'Voice identity/素材/consent必须绑定冻结上下文中实际存在的来源'))
    if QUERY_FIELDS.intersection(item.constraints):
        issues.append(problem(prefix, 'query仅交付在queries，constraints不重复维护query'))
    constraints = dict(item.constraints)
    if item.queries:
        try:
            if len(item.queries) != 3: raise ValueError('queries须为三个不同英文短查询')
            controls = {'search_query_variants_en': dict(zip(('primary','alternate','relaxed'), item.queries))}
            query_hints(controls)
            constraints.update(controls)
        except (ValueError, TypeError) as exc: issues.append(problem(prefix, str(exc)))
    elif item.modality_spec.kind in {'image', 'video'}:
        issues.append(problem(prefix, '视觉Need须交付三个检索短语'))
    try:
        data = item.model_dump(mode='json', exclude={'queries'})
        spec = data['modality_spec']
        need = MaterialNeed.model_validate_json(json.dumps({**data, 'need_id': f'need-{identity[:24]}-{index:03}',
            'media_type': spec['kind'] if spec['kind'] in {'image','video'} else 'audio',
            'constraints': constraints}, ensure_ascii=False))
        validate_modality_constraints((need,))
        NeedCompiler().compile(need)
    except ValidationError as exc:
        issues.extend(problem(prefix+'.'+'.'.join(map(str,e['loc'])),e['msg'],e['type'])
                      for e in exc.errors(include_input=False,include_context=False))
    except (ValueError, TypeError) as exc: issues.append(problem(prefix, str(exc)))
    return (None, issues) if issues else (need, [])


def compile_draft(value, *, creation_id, attempt_id, refs, mode, script, allowed_refs=None,
                  compiler_policy=None, authority_inputs=None):
    # Inspect only structurally valid independent Needs when another field is
    # invalid. Never substitute defaults for bad input to produce a Plan.
    policy = _compiler_policy(compiler_policy)
    from easel.integrations import planning_authority as authority
    if not isinstance(authority_inputs, dict) or authority_inputs.get('schema') != 'planning-authority-inputs@1':
        raise SemanticPlanningError('A', [problem('authority', '@7不能缺少实际上游来源输入或降级编译')])
    if isinstance(value, (str, bytes)):
        try: value = read_planning_requirements(value.decode('utf-8') if isinstance(value,bytes) else value)
        except (ValueError, UnicodeError) as exc:
            raise SemanticPlanningError('A',[problem('$',str(exc),'json_invalid')]) from exc
    issues = []
    try: draft = parse_draft(value)
    except SemanticPlanningError as exc:
        draft = None
        issues.extend(exc.issues)
    if draft is None:
        items = []
        candidates = value.get('needs', []) if isinstance(value,dict) else []
        if isinstance(candidates,list):
            for index, row in enumerate(candidates):
                try: item = SemanticNeed.model_validate_json(json.dumps(row,ensure_ascii=False))
                except (ValueError,TypeError): continue  # Schema diagnostics already identify invalid structure.
                items.append((index,item))
        identity = 'diagnostic-only'  # No formal identity exists for an invalid draft.
    else:
        identity = digest({'policy': policy, 'draft': draft.model_dump(mode='json', by_alias=True),
                           'creation_id': creation_id, 'attempt_id': attempt_id, 'refs': refs,
                           'mode': mode, 'script_sha256': hashlib.sha256(script.encode()).hexdigest(),
                           **({'authority_sha256': authority.digest(authority_inputs),
                               'field_presence': [sorted(item.model_fields_set) for item in draft.needs],
                               'modality_field_presence': [sorted(item.modality_spec.model_fields_set) for item in draft.needs]})})
        items = list(enumerate(draft.needs))
    needs = []
    for index, item in items:
        need, problems = _compile_need(item,index=index,identity=identity,allowed_refs=allowed_refs)
        issues.extend(problems)
        if need is not None: needs.append(need)
    if not issues and not any(n.importance is NeedImportance.REQUIRED for n in needs):
        issues.append(problem('needs', '至少一个required Need；不把上游无效项算作通过'))
    if issues: raise SemanticPlanningError('A', issues)
    plan = MaterialPlan(plan_id=f'plan-{identity[:32]}', creation_id=creation_id, attempt_id=attempt_id,
                        context_refs=refs, policy=draft.policy, needs=tuple(needs))
    return apply_defaults(plan, mode, script)


def classification_output_schema(batch):
    """Program-owned wire shape, not a natural-language classification oracle."""
    if batch.get('compiler_policy') != AUTHORITY_POLICY:
        raise ValueError('历史分类协议只读，不生成旧结果 Schema')
    from easel.integrations import planning_authority as authority
    rows = []
    for unit in batch['units']:
        context = batch['contexts'][unit['need']]
        rows.append({'type': 'object', 'additionalProperties': False,
            'required': ['id', 'kind', 'preference_source'], 'properties': {
                'id': {'type': 'integer', 'const': unit['id']},
                'kind': {'type': 'string', 'enum': sorted(KINDS)},
                'preference_source': {'type': ['integer', 'null'],
                    'enum': [None, *[p['id'] for p in context['preferences']]]}}})
        rows[-1]['required'].append('basis')
        rows[-1]['properties']['basis'] = authority.basis_schema(batch['authority_catalog'],
            context['input']['need']['scope']['ref'])
        rows[-1]['allOf'] = [{'if': {'properties': {'kind': {'const': kind}}},
            'then': {'properties': {'basis': {'properties': {'relation': {'enum': relations}}}}}}
            for kind, relations in [('required', ['upstream_obligation', 'director_realization']),
                ('preference', ['preference']), ('postproduction', ['postproduction']), ('unresolved', ['unresolved'])]]
    schema = {'$schema': 'https://json-schema.org/draft/2020-12/schema',
        'type': 'object', 'additionalProperties': False, 'required': ['classifications'],
        'properties': {'classifications': {'type': 'array', 'minItems': len(rows),
            'maxItems': len(rows), 'prefixItems': rows, 'items': False}}}
    controls = []
    for control in batch['controls']:
        controls.append({'type': 'object', 'additionalProperties': False,
            'required': ['id', 'status', 'basis'], 'properties': {
                'id': {'type': 'integer', 'const': control['id']},
                'status': {'enum': ['ACCEPT', 'UNRESOLVED']},
                'basis': authority.basis_schema(batch['authority_catalog'], control['scope_ref'], control=control)},
            'allOf': [{'if': {'properties': {'status': {'const': status}}},
                'then': {'properties': {'basis': {'properties': {'relation': {'enum': relations}}}}}}
                for status, relations in [('UNRESOLVED', ['unresolved']),
                    ('ACCEPT', ['preference', 'operational'] if control['soft'] else
                     ['upstream_obligation', 'director_realization', 'operational'])]]})
    schema['required'].append('controls')
    schema['properties']['controls'] = {'type': 'array', 'minItems': len(controls), 'maxItems': len(controls),
                                       **({'prefixItems': controls} if controls else {}), 'items': False}
    return schema


def classification_repair_schema(batches, indexes):
    rows = []
    for index in indexes:
        schema = classification_output_schema(batches[index])
        rows.append({'type': 'object', 'additionalProperties': False,
            'required': ['index', *schema['required']],
            'properties': {'index': {'type': 'integer', 'const': index}, **schema['properties']}})
    return {'$schema': 'https://json-schema.org/draft/2020-12/schema',
        'type': 'object', 'additionalProperties': False, 'required': ['batches'],
        'properties': {'batches': {'type': 'array', 'minItems': len(rows),
            'maxItems': len(rows), 'prefixItems': rows, 'items': False}}}


def classification_batches(plan, mode, *, canonical=None, compiler_policy=None, authority_catalog=None):
    policy = _compiler_policy(compiler_policy)
    from easel.integrations import planning_authority as authority
    if not isinstance(authority_catalog, dict) or authority_catalog.get('schema') != authority.REVISION:
        raise SemanticPlanningError('B', [problem('authority', '@7必须绑定实际上游目录，不降级原分类')])
    if canonical is not None and (not isinstance(canonical, dict)
        or set(canonical) != {'SCRIPT.md', 'SCENES.md', 'TREATMENT.md'}
        or any(not isinstance(v, str) for v in canonical.values())):
        raise SemanticPlanningError('B', [problem('confirmed', '确认依据须为完整冻结三文件')])
    units, contexts, preference_id = [], {}, 0
    controls_by_need = {}
    for need_index, need in enumerate(plan.needs):
        if need.media_type not in {MediaType.IMAGE, MediaType.VIDEO}:
            continue
        frozen = compilation_input(need, plan.context_refs, mode, plan=plan)
        preferences = []
        pref_map = {}
        for source, row in enumerate(frozen['sources']):
            if row['preference']:
                pref_map[source] = preference_id
                preferences.append({'id': preference_id, 'source': source, 'text': row['text']})
                preference_id += 1
        contexts[need.need_id] = {'input': frozen, 'preferences': preferences, 'pref_map': pref_map}
        try: controls_by_need[need.need_id] = authority.control_rows(need, need_index)
        except ValueError as exc: raise SemanticPlanningError('B', [problem(need.need_id, str(exc))]) from exc
        for unit in classification_units(frozen, unit_policy=UNIT_POLICY):
            units.append({'id': len(units), 'need': need.need_id, 'local_id': unit['id'],
                          'text': unit['text'], 'source': unit['source']})
    result, seen_controls, control_id = [], set(), 0
    for start in range(0, len(units), MAX_BATCH_UNITS):
        chunk = units[start:start + MAX_BATCH_UNITS]
        names = list(dict.fromkeys(u['need'] for u in chunk))
        data = {'units': chunk, 'contexts': {k:contexts[k] for k in names}}
        controls = []
        for name in names:
            if name not in seen_controls:
                for control in controls_by_need[name]:
                    controls.append({'id': control_id, **control}); control_id += 1
                seen_controls.add(name)
        if len(controls) > authority.MAX_CONTROLS_PER_BATCH:
            raise SemanticPlanningError('B', [problem('controls', '单批控制项超出128项；不增批、不截断')])
        data.update(authority_catalog=authority_catalog, controls=controls)
        data.update(compiler_policy=policy, unit_policy=UNIT_POLICY)
        if canonical is not None:
            data['confirmed'] = dict(canonical)
        data['review_target'] = json.loads(encode(REVIEW_TARGET))
        data['output_schema'] = classification_output_schema(data)
        # Bound the entire context without truncating required content.
        if len(json.dumps(data, ensure_ascii=False).encode()) > MAX_FILE_BYTES:
            raise SemanticPlanningError('B', [problem('contexts', '单批完整上下文超过有界容量，未截断或提交')])
        data['batch_id'] = digest({'policy': policy, 'plan': plan.model_dump(mode='json'), 'data': data})
        result.append(data)
    return result


def assemble_requirements(plan, mode, responses, *, canonical=None, compiler_policy=None, authority_catalog=None):
    policy = _compiler_policy(compiler_policy)
    batches = classification_batches(plan, mode, canonical=canonical, compiler_policy=policy,
                                    authority_catalog=authority_catalog)
    from easel.integrations import planning_authority as authority
    if len(responses) != len(batches):
        raise SemanticPlanningError('B', [problem('batches', '分类批次不完整')])
    per_need = {n.need_id: [] for n in plan.needs if n.media_type in {MediaType.IMAGE, MediaType.VIDEO}}
    issues = []
    for index, (batch, response) in enumerate(zip(batches, responses)):
        expected = [u['id'] for u in batch['units']]
        wrapper = {'classifications', 'controls'}
        if not isinstance(response, dict) or set(response) != wrapper:
            issues.append(problem(f'batches.{index}.wrapper',
                'B输出顶层须完整classifications/controls，不回传输入或metadata'));continue
        rows = response['classifications']
        if (not isinstance(rows, list) or len(rows)!=len(expected)
            or any(not isinstance(r,dict) or set(r)!=({'id','kind','preference_source','basis'})
                   or type(r['id']) is not int for r in rows)
            or [r['id'] for r in rows]!=expected):
            fields='id/kind/preference_source/basis'
            issues.append(problem(f'batches.{index}.ids', f'分类字段须为{fields}；整数ID完整按序且仅一次：{expected}'));continue
        for unit, row in zip(batch['units'], rows):
            if not isinstance(row['kind'], str) or row['kind'] not in KINDS:
                issues.append(problem(f'unit.{unit["id"]}.kind', f'kind须为合法枚举{sorted(KINDS)}；任务说明标签不是kind'));continue
            pref = row['preference_source'];context = batch['contexts'][unit['need']]
            inverse = {v:k for k,v in context['pref_map'].items()}
            if pref is not None and (type(pref) is not int or pref not in inverse):
                issues.append(problem(f'unit.{unit["id"]}.preference_source', '偏好引用须为null或该Need显式软偏好的整数ID'));continue
            try:
                authority.validate_basis(row['basis'], authority_catalog, context['input']['need']['scope']['ref'], kind=row['kind'])
            except ValueError as exc:
                issues.append(problem(f'unit.{unit["id"]}.basis', str(exc)));continue
            per_need[unit['need']].append({'id':unit['local_id'], 'kind':row['kind'],
                                          'preference_source':inverse[pref] if pref is not None else None})
        controls = response['controls']
        expected_controls = batch['controls']
        if (not isinstance(controls, list) or len(controls) != len(expected_controls)
                or any(not isinstance(row, dict) or set(row) != {'id','status','basis'} or type(row['id']) is not int for row in controls)
                or [row['id'] for row in controls] != [control['id'] for control in expected_controls]):
            issues.append(problem(f'batches.{index}.controls', '全部control须按程序整数ID完整返回一次，不能漏审或增项'))
        else:
            for control, row in zip(expected_controls, controls):
                try: authority.validate_basis(row['basis'], authority_catalog, control['scope_ref'],
                                               kind=row['status'], control=control)
                except ValueError as exc: issues.append(problem(f'batches.{index}.controls.{control["id"]}', str(exc)))
    if issues:raise SemanticPlanningError('B',issues)
    result = {}
    for need in plan.needs:
        if need.need_id not in per_need:continue
        frozen = compilation_input(need, plan.context_refs, mode, plan=plan)
        try:
            labels = {'classifications':per_need[need.need_id], 'queries':list(query_hints(need.constraints))}
            bound = bind_classifications(frozen,labels,unit_policy=UNIT_POLICY)
            contract = validate_compilation(frozen,bound)
            if any(r['kind']=='unresolved' for r in contract['clauses']):
                raise ValueError('分类仍有歧义，不进入Supply')
            result[need.need_id] = {'clauses':[{'path':frozen['sources'][r['source']]['path'],
                'text':r['text'], 'kind':r['kind'],
                'preference_path':frozen['sources'][r['preference_source']]['path'] if r['preference_source'] is not None else None}
                for r in contract['clauses']], 'queries':contract['queries']}
        except (ValueError,TypeError) as exc:issues.append(problem(need.need_id,str(exc)))
    if issues:raise SemanticPlanningError('B',issues)
    return result


def read_file(root, name):
    path = root / 'planning' / name
    if path.parent.is_symlink() or path.is_symlink() or not path.is_file() or path.stat().st_size>MAX_FILE_BYTES:
        raise ValueError('Planning文件缺失、路径或容量无效：'+name)
    return path.read_bytes()


def write_file(root, name, raw, *, replace=False):
    path = root / 'planning' / name
    if path.parent.is_symlink() or path.is_symlink():raise ValueError('Planning文件不能是symlink')
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() and path.read_bytes()!=raw and not replace:
        raise ValueError('已有派生产物与有效快照冲突，不能覆盖：'+name)
    temp = path.with_name('.' + path.name + '.tmp')
    if temp.is_symlink():raise ValueError('Planning临时文件路径无效')
    with open(temp,'wb') as f:
        f.write(raw);f.flush();os.fsync(f.fileno())
    os.replace(temp,path)


def encode(value):return (json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()


def source_catalog(canonical, planning_context):
    """Program-owned scope tokens bound to literal confirmed scene lines."""
    lines = [s for s in canonical['SCENES.md'].splitlines() if s.strip()]
    catalog = {'global': {'global': canonical['SCENES.md']}}
    for kind in ('scene','segment','event'):
        catalog[kind] = {f'{kind}-{i+1}': text for i,text in enumerate(lines)}
    known = {}
    def refs(v):
        if isinstance(v,dict):
            if isinstance(v.get('id'),str):known[v['id']] = v
            for x in v.values():refs(x)
        elif isinstance(v,list):
            for x in v:refs(x)
    refs(planning_context.get('creator_context',{}))
    catalog['continuity'] = known
    creator = planning_context.get('creator_context',{})
    voice = creator.get('voice',{})
    catalog['voice'] = {}
    if isinstance(voice,dict) and any(v for k,v in voice.items() if k not in {'avoid'}):
        catalog['voice']['creator_context.voice'] = {'source':'creator_context','context':voice,
            'reference_asset_ids':voice.get('reference_asset_ids',[]),'consent_ref':voice.get('consent_ref')}
    for reference, record in known.items():
        identity = record.get('voice_identity')
        if isinstance(identity,dict) and identity.get('source') in {'creator_context','director_intent','explicit_user'}:
            catalog['voice'][reference] = {**identity,'context':record}
    from easel.integrations.voice_identity import derived_catalog, REFERENCE
    derived = derived_catalog(planning_context.get('proposal'), canonical['SCRIPT.md'])
    if derived is not None:
        catalog['derived_voice'] = derived
        catalog['voice'][REFERENCE] = {'source': 'explicit_user', 'context': derived}
    return catalog


def _preserve_repair_semantics(before, after, catalog=None):
    """Repair cannot buy success by dropping/reclassifying valid draft needs."""
    try:old = read_planning_requirements(before.decode())
    except (ValueError,UnicodeError):return
    new = read_planning_requirements(after.decode())
    if not isinstance(old,dict):return
    a,b = old.get('needs'),new.get('needs') if isinstance(new,dict) else None
    if not isinstance(a,list):return
    if not isinstance(b,list) or len(a)!=len(b):
        raise SemanticPlanningError('A',[problem('needs','修复不能删除或新增需求')])
    if isinstance(old.get('policy'),dict):
        for key,value in old['policy'].items():
            if isinstance(value,str) and (not isinstance(new.get('policy'),dict) or new['policy'].get(key)!=value):
                raise SemanticPlanningError('A',[problem('policy.'+key,'结构修复不能改写有效规划策略子项')])
    if 'policy' in old:
        from pydantic import TypeAdapter
        try:TypeAdapter(SemanticPlanningDraft.model_fields['policy'].annotation).validate_json(json.dumps(old['policy']))
        except (ValueError,TypeError):pass
        else:
            if old['policy']!=new.get('policy'):
                raise SemanticPlanningError('A',[problem('policy','结构修复不能改写有效规划策略')])
    for index,(x,y) in enumerate(zip(a,b)):
        if not isinstance(x,dict) or not isinstance(y,dict):continue
        from pydantic import TypeAdapter

        def preserve(original, repaired, annotation, path):
            try:
                TypeAdapter(annotation).validate_json(json.dumps(original))
            except (ValueError, TypeError):
                # Protect valid children even when a sibling is malformed.
                candidates = [annotation, *get_args(annotation)]
                model = next((v for v in candidates if isinstance(v,type) and issubclass(v,BaseModel)),None)
                if model is not None and isinstance(original,dict):
                    for child, field in model.model_fields.items():
                        if child in original:
                            preserve(original[child], repaired.get(child) if isinstance(repaired,dict) else None,
                                     field.annotation, path+'.'+child)
                return
            if original != repaired:
                raise SemanticPlanningError('A',[problem(path,'结构修复不能改写有效需求语义')])

        for key in ('intent','importance','scope','role','constraints','continuity_refs',
                    'modality_spec','queries','duration_hint','desired_options'):
            if key not in x:continue
            original,repaired=x[key],y.get(key)
            path=f'needs.{index}.{key}'
            if key=='queries':
                try:
                    if len(original)!=3:continue
                    query_hints({'search_query_variants_en':dict(zip(('primary','alternate','relaxed'),original))})
                except (ValueError,TypeError):continue
            elif key=='scope' and catalog is not None:
                if isinstance(original,dict) and original.get('ref') not in catalog.get(original.get('type'),{}):continue
            elif key=='continuity_refs' and isinstance(original,list) and catalog is not None:
                valid=[ref for ref in original if isinstance(ref,dict) and ref.get('ref') in catalog.get('continuity',{})]
                if any(ref not in (repaired or []) for ref in valid):
                    raise SemanticPlanningError('A',[problem(path,'结构修复不能删除有效连续性引用')])
                continue
            elif key=='constraints' and isinstance(original,dict):
                from easel.materials.application.need_constraints import VOICE_ALIASES
                kind=(x.get('modality_spec') or {}).get('kind') if isinstance(x.get('modality_spec'),dict) else None
                for field,value in original.items():
                    if field in QUERY_FIELDS or field in VOICE_ALIASES:continue
                    if field=='voice_delivery':
                        if kind!='voice':continue
                        if not isinstance(value,dict):continue
                        for control,setting in value.items():
                            try:validate_voice_delivery({control:setting})
                            except ValueError:continue
                            controls=repaired.get(field) if isinstance(repaired,dict) else None
                            if not isinstance(controls,dict) or control not in controls or controls[control]!=setting:
                                raise SemanticPlanningError('A',[problem(path+'.'+field+'.'+control,'结构修复不能改写有效声音参数')])
                        continue
                    elif field=='preferred_visual_details':
                        if kind not in {'image','video'} or not isinstance(value,str) or not value.strip():continue
                    elif isinstance(value,(dict,list)):
                        if not isinstance(repaired,dict) or field not in repaired or value!=repaired[field]:
                            raise SemanticPlanningError('A',[problem(path+'.'+field,'未定义容器语义不能删改来通过修复')])
                        continue
                    if not isinstance(repaired,dict) or field not in repaired or value!=repaired[field]:
                        raise SemanticPlanningError('A',[problem(path+'.'+field,'结构修复不能改写有效需求语义')])
                continue
            elif key=='modality_spec' and isinstance(original,dict):
                spec_type={'image':ImageNeedSpec,'video':VideoNeedSpec,'voice':SemanticVoiceSpec,
                           'bgm':BgmNeedSpec,'sfx':SfxNeedSpec}.get(original.get('kind'))
                if spec_type is None:continue
                if spec_type is SemanticVoiceSpec and catalog is not None:
                    old_identity=original.get('identity')
                    entry=catalog.get('voice',{}).get(old_identity.get('reference')) if isinstance(old_identity,dict) else None
                    if not entry or entry['source']!=old_identity.get('source'):
                        for field,info in spec_type.model_fields.items():
                            if field!='identity' and field in original:
                                preserve(original[field], repaired.get(field) if isinstance(repaired,dict) else None,
                                         info.annotation,path+'.'+field)
                        continue
                preserve(original,repaired,spec_type,path)
                continue
            preserve(original,repaired,SemanticNeed.model_fields[key].annotation,path)


def run_semantic_planning(attempt, planning_context, canonical, mode, route, dispatch, *, compiler_policy=None):
    """Only the current vNext executor may perform Planning or recovery."""
    from easel.integrations.semantic_boundary import POLICY as boundary_policy
    if compiler_policy != boundary_policy:
        raise ValueError('旧 Planning Executor/Compiler 已退役；历史原件不能恢复生产')
    from easel.integrations.semantic_boundary_run import run
    return run(attempt, planning_context, canonical, mode, route, dispatch)


def verify_semantic_checkpoint(root, plan, mode, script, origin=None, *, canonical=None, attempt=None):
    """Current frozen semantic checkpoint verification; no legacy codec."""
    from easel.integrations.semantic_boundary import POLICY as boundary_policy
    if plan.policy.get('semantic_compiler') != boundary_policy:
        raise ValueError('历史 Planning checkpoint 仅允许原件观察')
    from easel.integrations.semantic_boundary_run import verify
    return verify(root, plan, mode, script, origin, canonical=canonical, attempt=attempt)
