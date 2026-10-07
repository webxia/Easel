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

LEGACY_POLICY = 'semantic-planning-compiler@1'
CANONICAL_POLICY = 'semantic-planning-compiler@2'
REVIEW_POLICY = 'semantic-planning-compiler@3'
PURPOSE_POLICY = 'semantic-planning-compiler@4'
OUTPUT_POLICY = 'semantic-planning-compiler@5'
BASE_POLICY = 'semantic-planning-compiler@6'
AUTHORITY_POLICY = 'semantic-planning-compiler@7'
POLICY = AUTHORITY_POLICY
UNIT_POLICIES = {LEGACY_POLICY: 'indexed-unit-classification@7',
                 CANONICAL_POLICY: 'indexed-unit-classification@8',
                 REVIEW_POLICY: 'indexed-unit-classification@8',
                 PURPOSE_POLICY: 'indexed-unit-classification@8',
                 OUTPUT_POLICY: 'indexed-unit-classification@8',
                 BASE_POLICY: 'indexed-unit-classification@8',
                 AUTHORITY_POLICY: 'indexed-unit-classification@8'}
LEGACY_REVIEW_TARGET = {'schema': 'material-review-target@1', 'scope': 'original_asset',
                'required_evidence': 'observable_in_asset',
                'non_asset_obligation': 'narrative_or_postproduction',
                'uncertain': 'unresolved', 'precedence': ['target', 'strength', 'kind']}
PURPOSE_REVIEW_TARGET = {'schema': 'material-review-target@2', 'scope': 'original_asset',
                'required_evidence': 'observable_in_asset',
                'non_asset_obligation': 'narrative_or_postproduction',
                'uncertain': 'unresolved',
                'precedence': ['predicate_and_purpose', 'target', 'strength', 'kind'],
                'relation_rules': {
                    'asset_property_with_purpose': 'classify_asset_property_by_source_strength',
                    'pure_postproduction': 'actual_editing_or_narrative_obligation',
                    'mixed_independent_obligations': 'unresolved_if_not_losslessly_classifiable',
                    'interpretation': 'semantic_relation_not_word_order_or_keywords'}}
REVIEW_TARGET = {**PURPOSE_REVIEW_TARGET, 'schema': 'material-review-target@3',
    'relation_rules': {**PURPOSE_REVIEW_TARGET['relation_rules'],
        'asset_intrinsic_vs_timeline_use': 'classify_obligation_target_not_repeated_subject_or_field'},
    'counterfactual': {
        'scope': 'obligation_target_not_editability',
        'source_condition': 'remains_about_original_asset_even_if_later_edit_can_remove_it',
        'timeline_or_expression': 'same_asset_can_be_used_differently_without_new_intrinsic_condition',
        'repeated_subject': 'repetition_in_usage_does_not_create_or_erase_source_obligation',
        'independent_mixed': 'preserve_unresolved_when_not_losslessly_classifiable'}}
REVIEW_TARGETS = {REVIEW_POLICY: LEGACY_REVIEW_TARGET, PURPOSE_POLICY: PURPOSE_REVIEW_TARGET,
                 OUTPUT_POLICY: PURPOSE_REVIEW_TARGET,
                 BASE_POLICY: REVIEW_TARGET,
                 AUTHORITY_POLICY: {**REVIEW_TARGET, 'schema': 'material-review-target@4',
                    'authority': 'upstream_eligibility_is_not_entailment',
                    'candidate_is_not_own_authority': True}}
OUTPUT_SCHEMA_POLICIES = frozenset({OUTPUT_POLICY, BASE_POLICY, AUTHORITY_POLICY})
MAX_FILE_BYTES = 256 * 1024
MAX_BATCH_UNITS = 40


def _compiler_policy(value):
    # Unversioned pure compiler callers retain the established @6 API. Product
    # orchestration always passes its explicit policy; @7 never falls back.
    policy = BASE_POLICY if value is None else value
    if not isinstance(policy, str) or policy not in UNIT_POLICIES:
        raise ValueError('语义编译政策未知，不能降级')
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
    if policy == AUTHORITY_POLICY:
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
                               'modality_field_presence': [sorted(item.modality_spec.model_fields_set) for item in draft.needs]}
                              if policy == AUTHORITY_POLICY else {})})
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
    rows = []
    for unit in batch['units']:
        context = batch['contexts'][unit['need']]
        rows.append({'type': 'object', 'additionalProperties': False,
            'required': ['id', 'kind', 'preference_source'], 'properties': {
                'id': {'type': 'integer', 'const': unit['id']},
                'kind': {'type': 'string', 'enum': sorted(KINDS)},
                'preference_source': {'type': ['integer', 'null'],
                    'enum': [None, *[p['id'] for p in context['preferences']]]}}})
        if batch.get('compiler_policy') == AUTHORITY_POLICY:
            from easel.integrations import planning_authority as authority
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
    if batch.get('compiler_policy') == AUTHORITY_POLICY:
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
    if policy == AUTHORITY_POLICY:
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
        frozen = compilation_input(need, plan.context_refs, mode)
        preferences = []
        pref_map = {}
        for source, row in enumerate(frozen['sources']):
            if row['preference']:
                pref_map[source] = preference_id
                preferences.append({'id': preference_id, 'source': source, 'text': row['text']})
                preference_id += 1
        contexts[need.need_id] = {'input': frozen, 'preferences': preferences, 'pref_map': pref_map}
        if policy == AUTHORITY_POLICY:
            try: controls_by_need[need.need_id] = authority.control_rows(need, need_index)
            except ValueError as exc: raise SemanticPlanningError('B', [problem(need.need_id, str(exc))]) from exc
        for unit in classification_units(frozen, unit_policy=UNIT_POLICIES[policy]):
            units.append({'id': len(units), 'need': need.need_id, 'local_id': unit['id'],
                          'text': unit['text'], 'source': unit['source']})
    result, seen_controls, control_id = [], set(), 0
    for start in range(0, len(units), MAX_BATCH_UNITS):
        chunk = units[start:start + MAX_BATCH_UNITS]
        names = list(dict.fromkeys(u['need'] for u in chunk))
        data = {'units': chunk, 'contexts': {k:contexts[k] for k in names}}
        if policy == AUTHORITY_POLICY:
            controls = []
            for name in names:
                if name not in seen_controls:
                    for control in controls_by_need[name]:
                        controls.append({'id': control_id, **control}); control_id += 1
                    seen_controls.add(name)
            if len(controls) > authority.MAX_CONTROLS_PER_BATCH:
                raise SemanticPlanningError('B', [problem('controls', '单批控制项超出128项；不增批、不截断')])
            data.update(authority_catalog=authority_catalog, controls=controls)
        if policy != LEGACY_POLICY:
            data.update(compiler_policy=policy, unit_policy=UNIT_POLICIES[policy])
            if canonical is not None:
                data['confirmed'] = dict(canonical)
        if policy in REVIEW_TARGETS:
            # Program-owned task contract, not another model-authored answer.
            data['review_target'] = json.loads(encode(REVIEW_TARGETS[policy]))
        if policy in OUTPUT_SCHEMA_POLICIES:
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
    if policy == AUTHORITY_POLICY:
        from easel.integrations import planning_authority as authority
    if len(responses) != len(batches):
        raise SemanticPlanningError('B', [problem('batches', '分类批次不完整')])
    per_need = {n.need_id: [] for n in plan.needs if n.media_type in {MediaType.IMAGE, MediaType.VIDEO}}
    issues = []
    for index, (batch, response) in enumerate(zip(batches, responses)):
        expected = [u['id'] for u in batch['units']]
        wrapper = {'classifications', 'controls'} if policy == AUTHORITY_POLICY else {'classifications'}
        if not isinstance(response, dict) or set(response) != wrapper:
            issues.append(problem(f'batches.{index}.wrapper',
                'B输出顶层须完整classifications/controls，不回传输入或metadata' if policy == AUTHORITY_POLICY else
                'B输出顶层仅允许classifications，不回传输入或metadata'));continue
        rows = response['classifications']
        if (not isinstance(rows, list) or len(rows)!=len(expected)
            or any(not isinstance(r,dict) or set(r)!=({'id','kind','preference_source','basis'} if policy == AUTHORITY_POLICY else {'id','kind','preference_source'})
                   or type(r['id']) is not int for r in rows)
            or [r['id'] for r in rows]!=expected):
            fields='id/kind/preference_source/basis' if policy == AUTHORITY_POLICY else 'id/kind/preference_source'
            issues.append(problem(f'batches.{index}.ids', f'分类字段须为{fields}；整数ID完整按序且仅一次：{expected}'));continue
        for unit, row in zip(batch['units'], rows):
            if not isinstance(row['kind'], str) or row['kind'] not in KINDS:
                issues.append(problem(f'unit.{unit["id"]}.kind', f'kind须为合法枚举{sorted(KINDS)}；任务说明标签不是kind'));continue
            pref = row['preference_source'];context = batch['contexts'][unit['need']]
            inverse = {v:k for k,v in context['pref_map'].items()}
            if pref is not None and (type(pref) is not int or pref not in inverse):
                issues.append(problem(f'unit.{unit["id"]}.preference_source', '偏好引用须为null或该Need显式软偏好的整数ID'));continue
            if policy == AUTHORITY_POLICY:
                try:
                    authority.validate_basis(row['basis'], authority_catalog, context['input']['need']['scope']['ref'], kind=row['kind'])
                except ValueError as exc:
                    issues.append(problem(f'unit.{unit["id"]}.basis', str(exc)));continue
            per_need[unit['need']].append({'id':unit['local_id'], 'kind':row['kind'],
                                          'preference_source':inverse[pref] if pref is not None else None})
        if policy == AUTHORITY_POLICY:
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
        frozen = compilation_input(need, plan.context_refs, mode)
        try:
            labels = {'classifications':per_need[need.need_id], 'queries':list(query_hints(need.constraints))}
            bound = bind_classifications(frozen,labels,unit_policy=UNIT_POLICIES[policy])
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
    from easel.materials.store import AttemptMaterialStore
    from easel.output_contract import output_decision
    root = Path(attempt['workspace']['path'])
    store = AttemptMaterialStore(root)
    root = store.attempt_root
    policy = _compiler_policy(POLICY if compiler_policy is None else compiler_policy)
    authority_inputs = None
    if policy == AUTHORITY_POLICY:
        from easel.integrations import planning_authority as authority
        try: authority_inputs = authority.load_inputs(attempt, canonical, planning_context, mode)
        except ValueError as exc: raise SemanticPlanningError('A', [problem('authority', str(exc))]) from exc
    catalog_context = {**planning_context,'creator_context':authority_inputs['creator_context']} if policy == AUTHORITY_POLICY else planning_context
    catalog = source_catalog(canonical,catalog_context)
    scope = {'policy':policy,'attempt_id':attempt['attempt_id'],'creation_id':attempt['creation_id'],
             'context_refs':planning_context['context_refs'],'canonical':canonical,'mode':mode,'catalog':catalog,
             **({'authority_inputs':authority_inputs} if policy == AUTHORITY_POLICY else {})}
    state_key = 'semantic-planning-v3'
    state = store.read_recovery_record(state_key)
    if state is None:
        # Existing legacy repair is never new repair allowance.
        if list((root/'materials/recoveries').glob('planning-structure-repair-*.json')):
            raise SemanticPlanningError('A',[problem('version','旧协议修复记录不能升级为新额度')])
        state = {'schema':'semantic-planning-checkpoint@1','scope':scope,'route':route,
                 'calls':{},'repair_used':False}
        store.write_recovery_record(state_key,state)
    elif (state.get('schema')!='semantic-planning-checkpoint@1' or state.get('scope')!=scope
          or state.get('route')!=route):
        raise SemanticPlanningError('A',[problem('checkpoint','输入、版本或执行route变化；不重置额度')])
    for name,text in canonical.items():
        if read_file(root,name)!=text.encode():
            raise SemanticPlanningError('A',[problem(name,'确认冻结原文变化，不能复用响应')])
    if state.get('snapshot') and hashlib.sha256(read_file(root,'SEMANTIC_PLAN.json')).hexdigest()!=state['snapshot']['draft_sha256']:
        raise SemanticPlanningError('A',[problem('snapshot','有效语义草稿原件变化，不能恢复或覆盖')])

    def save():store.write_recovery_record(state_key,state)
    def invoke(key, stage, message, name):
        record = state['calls'].get(key)
        if record is None:
            record={'status':'pending','message':message,'message_sha256':digest(message),'name':name}
            state['calls'][key]=record;save()
        if (record.get('message')!=message or record.get('message_sha256')!=digest(message)
            or record.get('name')!=name or record.get('status') not in {'pending','complete','failed'}):
            raise SemanticPlanningError(stage,[problem('request','原请求或记录无效；不重新派发')])
        if record['status']=='failed':raise SemanticPlanningError(stage,[problem('request','原执行已失败，不重派')])
        if record['status']=='pending':
            try:
                dispatch(stage,message,f"semantic-{attempt['attempt_id']}-{key}")
            except Exception as exc:
                from easel.creation_delivery import DeliveryExecutionUncertain, DeliveryObservationPending
                from easel.integrations.openclaw_delivery import DeliveryAgentPending
                import subprocess
                if isinstance(exc,(DeliveryExecutionUncertain,DeliveryObservationPending,DeliveryAgentPending,subprocess.TimeoutExpired)):
                    raise
                record['status']='failed';save();raise
            try:
                for name_,text_ in canonical.items():
                    if read_file(root,name_)!=text_.encode():
                        raise SemanticPlanningError(stage,[problem(name_,'模型修改了确认冻结原文')])
                if (key.startswith('B') or key=='repair' and state.get('repair_stage')=='B') and read_file(root,a_name)!=raw_a:
                    raise SemanticPlanningError(stage,[problem(a_name,'分类阶段改写了有效语义草稿')])
            except ValueError:
                record['status']='failed';save();raise
            try:
                raw = read_file(root,name)
            except ValueError:
                raw = b''  # Known terminal output fault can use shared repair, not resubmit.
            record.update(status='complete',raw=raw.decode('utf-8'),sha256=hashlib.sha256(raw).hexdigest());save()
        raw = record.get('raw','').encode('utf-8')
        if hashlib.sha256(raw).hexdigest()!=record.get('sha256'):
            raise SemanticPlanningError(stage,[problem('response','已完成响应摘要损坏')])
        return raw

    def repair(stage, initial, issues, targets, context):
        key='repair'
        planning = root / 'planning'
        if planning.is_symlink() or not planning.is_dir():
            raise SemanticPlanningError(stage,[problem('repair','Planning输出目录无效，未派发')])
        output_paths = {}
        for name in targets:
            if name not in {'SEMANTIC_PLAN.json','CLASSIFICATIONS-REPAIR.json'}:
                raise SemanticPlanningError(stage,[problem('repair','修复输出目标无效，未派发')])
            target = planning / name
            if target.is_symlink() or (target.exists() and not target.is_file()) or target.resolve().parent != planning:
                raise SemanticPlanningError(stage,[problem('repair','修复输出路径无效，未派发')])
            output_paths[name] = str(target)
        message=('〔Easel Planning V3 单次语义合同修正〕\n阶段：'+stage+'\n'
            '保留全部有效Need语义、模态、importance与冻结正文；只修下列错误；不能删除要求。'
            '仅写output_paths提供的绝对路径；不猜测当前目录，不依赖其他会话。'
            '不写正式Plan/sidecar，不调用供应/生成/Hypit。\n'
            +('B输出严格遵循context.response_schema，顶层仅batches；不回传context、responses、notes或任务标签。\n' if stage=='B' else '')
            +('每个B批次完整保留classifications和controls及各自basis。A候选不是上游授权，目录ID存在不证明语义蕴含；'
              '硬filter不可用preference/postproduction放行，operational只认实际程序操作的path/typed value。'
              '不能改控制值、删项或新增授权来修复；不足依据返回unresolved/UNRESOLVED。\n'
              if policy == AUTHORITY_POLICY else '')
            +'按要求约束的对象判断，不因function复述主体/静态就新增原素材义务。'
            '成片如何保持/使用原图、表达象征或叠字属于使用/表达/后期；真正的原主体、数量、源动作仍保留。'
            '后期可以裁掉原主体不代表原素材主体条件消失，不按字段或重复自动分类。\n'
            +json.dumps({'attempt_workspace':str(root),'output_paths':output_paths,
                        'issues':issues,'targets':targets,'context':context,
                        'review_target':REVIEW_TARGETS.get(policy, REVIEW_TARGET)},ensure_ascii=False,sort_keys=True))
        if state['repair_used'] and (key not in state['calls'] or state['calls'][key]['message']!=message):
            raise SemanticPlanningError(stage,[problem('repair','整次Planning共享单次修复额度已用完')])
        state['repair_used']=True;save()
        if len(message.encode())>MAX_FILE_BYTES:
            raise SemanticPlanningError(stage,[problem('repair','合并修复上下文超过有界容量，未提交')])
        raw=invoke(key,'structure_repair',message,targets[0])
        if stage=='A':_preserve_repair_semantics(initial,raw,catalog)
        return raw

    a_name='SEMANTIC_PLAN.json'
    message=('〔Easel Semantic Planning V3〕\nAttempt workspace: '+str(root)+'\n'
        '只交一份语义草稿，程序负责正式Plan/NeedID/身份/来源/sidecar；不输出派生字段。'
        '读取本工作区冻结handoff及Creator/Director依据；scope仅选择下列catalog。'
        'queries交三个不同英文短语；正文/场景/声音保持确认原意，required不能遗漏或降级；'
        '素材description写原素材可观察条件；构图与风格软偏好仅放明确preferred字段，不在description重复硬化。'
        '先确定要求约束谁，再区分必要/偏好；有创作来源不代表它能成为素材采购条件。'
        '辨识素材属性主谓与制作目的/用途的语义关系，不按词序或连接词分类。'
        '原图色调/构图用于某种成片表达，仍是源属性；软属性保留于preferred字段，'
        '制作目的可在function及冻结SCENES/TREATMENT承载；真正要求原主体数量或原视频动作的条件不能删改。'
        'function应解释素材在成片中的表达用途，不重复把使用时长/保持方式写成原素材固有条件。'
        '同一原图保持15秒、不切换或象征某种表达是成片使用；原图两张纸条件仍完整保留。'
        '后期裁切/排版形成留白是编辑操作，与原图具有留白不同。'
        '作者不虚构来历、不声称亲历等叙事/事实义务保留于已有confirmed/handoff/Truth或叙事function，'
        '不能复制进原素材description，也不能删除这些创作边界。'
        '原画面不出现可识别文字或人物是可观察素材条件；原视频必须发生的动态动作仍完整保留。'
        '不要仅因是否定句或位于function就决定归属。'
        '确认稿中的后期字幕/叠加工作由原SCENES/TREATMENT保留，不复制屏幕正文进背景素材需求。'
        '若原素材本身必须有印刷字/屏幕内容，仍完整保留；不把这些误删成后期。'
        '不调用供应/生成/Hypit。只写 '+str(root/'planning'/a_name)+'\n' + PLANNING_INPUT_RULES
        +json.dumps({'schema':planning_input_schema(catalog),'confirmed':canonical,
                    'catalog':catalog,'context_refs':planning_context['context_refs'],
                    'review_target':REVIEW_TARGETS.get(policy, REVIEW_TARGET),
                    **({'authority_inputs':authority_inputs,
                        'candidate_authority':'A候选不是上游授权；B须绑定实际来源和真实控制值'}
                       if policy == AUTHORITY_POLICY else {})},ensure_ascii=False,sort_keys=True))
    if len(message.encode())>MAX_FILE_BYTES:
        raise SemanticPlanningError('A',[problem('input','完整输入超过有界容量，未派发')])
    raw=invoke('A','planning',message,a_name)
    initial_a=raw
    if state.get('repair_stage')=='A':
        repair_call=state['calls'].get('repair',{})
        raw=invoke('repair','structure_repair',repair_call.get('message',''),a_name)
        _preserve_repair_semantics(initial_a,raw,catalog)
    try:
        plan=compile_draft(raw,creation_id=attempt['creation_id'],attempt_id=attempt['attempt_id'],
            refs=planning_context['context_refs'],mode=mode,script=canonical['SCRIPT.md'],
            allowed_refs=catalog, compiler_policy=policy, authority_inputs=authority_inputs)
    except SemanticPlanningError as exc:
        state['repair_stage']='A';save()
        raw=repair('A',raw,exc.issues,[a_name],{'schema':planning_input_schema(catalog),
                                            'catalog':catalog,'original':raw.decode(),
                                            **({'authority_inputs':authority_inputs} if policy == AUTHORITY_POLICY else {})})
        plan=compile_draft(raw,creation_id=attempt['creation_id'],attempt_id=attempt['attempt_id'],
            refs=planning_context['context_refs'],mode=mode,script=canonical['SCRIPT.md'],
            allowed_refs=catalog, compiler_policy=policy, authority_inputs=authority_inputs)
    raw_a=raw
    authority_catalog = None
    if policy == AUTHORITY_POLICY:
        authority_catalog = authority.catalog(authority_inputs, authority.applied_operations(parse_draft(raw), plan, mode))
    batches=classification_batches(plan,mode,canonical=canonical,compiler_policy=policy,
                                   authority_catalog=authority_catalog)
    snapshot=json.loads(encode({'draft_sha256':hashlib.sha256(raw).hexdigest(),
              'plan':plan.model_dump(mode='json'),'batches':batches,'policy':policy,
              **({'authority_catalog':authority_catalog} if policy == AUTHORITY_POLICY else {})}))
    if 'snapshot' in state and state['snapshot']!=snapshot:
        raise SemanticPlanningError('B',[problem('snapshot','有效Need快照变化，旧分类不能复用')])
    state['snapshot']=snapshot;save()
    responses=[]
    messages=[]
    for index,batch in enumerate(batches):
        name=f'CLASSIFICATIONS-{index:03}.json'
        bmessage=('〔Easel Planning V3 单元分类〕\n'
            '只分类程序提供的unit ID，完整按序各一次，不返回path/text/offset/Need映射/query。'
            '先辨识完整单元的主谓条件和目的/用途修饰，再确定审核对象、硬软强度，最后选kind；不能把所有禁令默认required。'
            '先核定义务约束原素材还是成片使用：同一原图保持15秒、担当表达或后期叠字是使用/表达/后期。'
            '用途复述两张纸或静态不自动新增采购义务；真正原图两纸或原视频源动作也不因重复/字段而删除。'
            '反事实仅辅助核定对象：原图两张纸条件在后期裁掉一张后仍约束原图，不能以可编辑为由降级。'
            '原素材可观察的必要主体/数量/禁令/源动作保持required；明确软偏好不能升级，叙事用途/后期为postproduction；'
            '有歧义返回unresolved。偏好引用只能用所属context.preferences中的id。'
            'required审核对象是原始素材自身，不是成片或后期执行。引用的SCRIPT不是背景图必须包含的文字；'
            '对拟postproduction也核对是否存在可观察的源属性；附带后期用途不把该属性整体变为编辑动作。'
            '用途在句首、句末或没有连接词都按实际关系判断，不按后期/为了等关键词处理。'
            '例如显式cool color palette软偏好支持的「原图偏冷色调用于疏离表达」或「为疏离表达选择偏冷原图」'
            '沿同一preference来源；「原图必须有两张纸用于旁边叠字」仍required；'
            '「后期在纸旁叠字」及「后期裁切和排版形成留白」才是编辑动作本身；'
            '「原视频杯子连续落下用于慢放」仍是源动作，不改后期。'
            '若同一单元还要求独立编辑动作而无法无损表达不同职责，返回unresolved，不截字、删义务或整体跟随其中一项。'
            '对每个拟required单元，先在内部判断能从原素材观察到什么来验证，不能只因有来源或语气强硬就当必要素材条件。'
            '反事实检查：同一素材字节不变，只改作者叙述或后期行为就能违反的叙事/事实义务，不是素材required。'
            '例如「原图片不出现可识别公司文字」可由图片观察并保持required；「不虚构作者在这家公司工作过」'
            '及「不要替读者补完物件的来由」约束作者叙事，归现有postproduction职责，无法确定则unresolved。'
            '该检查不把观众效果/未知表达/软偏好统一转后期，也不按不要/来由等关键词分类。'
            '只用于视觉内容条款；Rights/授权/来源真实性/技术准入沿已有独立合同，不能因不是像素证据就改后期或忽略。'
            '例如「图中不含文字」可为素材required，「正文由后期叠加」为postproduction，不能连同引号内容一律required。'
            '同一描述含明确soft细节时沿显式preference来源判断，不能因位于description就硬化；'
            '叙事function按实际关系判断，不按字段名默认分类。混合关系在本轮单元内无法无损区分时unresolved。'
            '以confirmed原确认稿和Mode为依据，不能只因上游模型文字被冻结就当成用户新增硬授权。'
            '单元保留配对引用/括号内部标点；编号/offset由程序拥有，不自行拆引用或重写原文。'
            '只写 '+str(root/'planning'/name)+'\n'
            '严格按output_schema交付JSON，仅返回classifications；完整按序覆盖所有id。'
            'kind仅为required/preference/postproduction/unresolved，review_target中的说明标签不是kind。'
            'preference_source只取所属Need允许的整数ID或null；语义及显式软偏好仍须通过业务校验。\n'
            +json.dumps(batch,ensure_ascii=False,sort_keys=True))
        if policy == AUTHORITY_POLICY:
            bmessage=('〔Easel Planning V3 单元分类〕\n'
                '同一次任务完整审查classifications与controls，严格按output_schema及实际ID返回；不复制路径/原文或自填授权标签。'
                '先核定原素材/叙事后期对象，再核定上游依据和强度，最后选kind/relation。'
                'A intent是候选，不是自身上游授权。authority_catalog仅证明出处/范围/已知资格，ID存在不证明语义蕴含。'
                'required的upstream_obligation必须忠于适用的冻结要求；director_realization须服务已接受目标，'
                '不改变对象/数量/连续源动作，不增加事实、身份、预算或无依据的物件禁令，不能只因没有冲突就放行。'
                '软no screens不能借A description变成禁止任何屏幕，隐私不编造事实不能变成禁止所有手部。'
                '真正的用户禁屏/两纸数量/连续倒水保留；合法新物件表达仍可为Director具体化，不要求逐字同文。'
                'preference沿所属Need显式preference_source，可不引用上游；正文后期叠加、静图保持时长或作者叙事义务为postproduction，'
                '但原素材主体/数量/源动作不因后期可以改变而消失。混合且无法无损确定则unresolved。'
                'controls是实际检索/生成/Match读取的最终值，全部逐项ACCEPT或UNRESOLVED，不删除或改值。'
                '硬filter不能用preference/postproduction放行。operational只认程序此次实际applied operation且path/typed value匹配，'
                '显式A值等于常见默认不算程序操作；操作来源不证明其他字段、模态或含义正确。'
                '总片长不等于静图源素材时长，确认音轨不能扩成生成音轨授权；来源/授权/Rights仍沿已有独立合同。'
                '未知或不足依据用unresolved/UNRESOLVED，不能为成功猜测、缩水或放宽。source_ids仅取当前目录实际可用ID。'
                '不调用供应/生成/Hypit。只写 '+str(root/'planning'/name)+'\n'
                +json.dumps(batch,ensure_ascii=False,sort_keys=True))
        if policy == AUTHORITY_POLICY and len(bmessage.encode()) > MAX_FILE_BYTES:
            raise SemanticPlanningError('B',[problem(f'batches.{index}.capacity','完整B消息超过有界容量，未提交任何B批次')])
        messages.append((name,bmessage))
    for index,(name,bmessage) in enumerate(messages):
        raw_b=invoke(f'B{index}','planning',bmessage,name)
        try:response=read_planning_requirements(raw_b.decode())
        except (ValueError,UnicodeError):response=None
        responses.append(response)
    if state.get('repair_stage')=='B':
        rec=state['calls'].get('repair',{})
        repaired=read_planning_requirements(invoke('repair','structure_repair',rec.get('message',''),'CLASSIFICATIONS-REPAIR.json').decode())
        responses=_merge_repaired(responses,repaired,state['repair_indexes'],batches=batches)
    try:requirements=assemble_requirements(plan,mode,responses,canonical=canonical,compiler_policy=policy,
                                         authority_catalog=authority_catalog)
    except SemanticPlanningError as exc:
        # Diagnose each complete Need only after collecting every batch.
        # Repair can address several batches in one response, never new budgets.
        affected=set()
        for issue in exc.issues:
            field=issue['field']
            if field.startswith('batches.'):
                affected.add(int(field.split('.')[1]))
            elif field.startswith('unit.'):
                unit_id=int(field.split('.')[1])
                affected.update(i for i,b in enumerate(batches) if any(u['id']==unit_id for u in b['units']))
            else:
                affected.update(i for i,b in enumerate(batches) if any(u['need']==field for u in b['units']))
        indexes=sorted(affected)
        if not indexes:raise
        state.update(repair_stage='B',repair_indexes=indexes);save()
        repaired=repair('B',b'',exc.issues,['CLASSIFICATIONS-REPAIR.json'],
            {'batches':[{**batches[i],'index':i} for i in indexes],
             'responses':[responses[i] for i in indexes],
             'response_schema':classification_repair_schema(batches,indexes)})
        responses=_merge_repaired(responses,read_planning_requirements(repaired.decode()),indexes,batches=batches)
        requirements=assemble_requirements(plan,mode,responses,canonical=canonical,compiler_policy=policy,
                                          authority_catalog=authority_catalog)
    checkpoint={'schema':'semantic-planning-frozen@1','scope':scope,'draft':raw.decode(),
                'draft_sha256':hashlib.sha256(raw).hexdigest(),'plan':plan.model_dump(mode='json'),
                'responses':responses,'policy':policy,'batches_sha256':digest(batches),
                **({'authority_catalog':authority_catalog} if policy == AUTHORITY_POLICY else {})}
    checkpoint_raw=encode(checkpoint)
    write_file(root,'SEMANTIC_CHECKPOINT.json',checkpoint_raw)
    write_file(root,'SEMANTIC_PLAN.json',raw,replace=True)
    write_file(root,'MATERIAL_PLAN.json',(plan.model_dump_json(indent=2)+'\n').encode())
    write_file(root,'MATERIAL_REQUIREMENTS.json',encode(requirements))
    return {'plan':plan,'context_refs':plan.context_refs,'script':canonical['SCRIPT.md'],
            'scenes':canonical['SCENES.md'],'treatment':canonical['TREATMENT.md'],
            'output_decision':output_decision('planning','ACCEPT','semantic_compiled',policy_revision=policy)}


def _merge_repaired(responses, repaired, indexes, *, batches=None):
    if not isinstance(repaired,dict) or set(repaired) != {'batches'}:
        raise SemanticPlanningError('B',[problem('repair.wrapper','修复输出顶层仅允许batches，不回传输入/metadata/responses')])
    rows=repaired['batches']
    if (not isinstance(rows,list) or len(rows)!=len(indexes)
        or any(not isinstance(r,dict) or type(r.get('index')) is not int or set(r) !=
            ({'index','classifications','controls'} if batches is not None and batches[indexes[i]].get('compiler_policy') == AUTHORITY_POLICY
             else {'index','classifications'}) for i,r in enumerate(rows))
        or [r['index'] for r in rows]!=indexes):
        fields='index/classifications/controls' if batches is not None and any(batches[i].get('compiler_policy')==AUTHORITY_POLICY for i in indexes) else 'index/classifications'
        raise SemanticPlanningError('B',[problem('repair.indexes',f'修复每项仅{fields}；整数index须按序覆盖全部且仅受影响批次')])
    result=list(responses)
    for r in rows:result[r['index']]={key:value for key,value in r.items() if key != 'index'}
    return result


def verify_semantic_checkpoint(root, plan, mode, script, origin=None, *, canonical=None, attempt=None):
    raw=read_file(root,'SEMANTIC_CHECKPOINT.json')
    checkpoint=read_planning_requirements(raw.decode())
    policy = _compiler_policy(checkpoint.get('policy'))
    if checkpoint.get('schema')!='semantic-planning-frozen@1' or checkpoint.get('policy')!=policy:
        raise ValueError('语义编译版本无效')
    scope=checkpoint['scope']
    if scope['policy']!=policy or scope['context_refs']!=plan.context_refs or scope['mode']!=mode or scope['canonical']['SCRIPT.md']!=script:
        raise ValueError('语义冻结输入变化')
    if policy != LEGACY_POLICY:
        actual_canonical = canonical if canonical is not None else {
            name: read_file(root, name).decode() for name in ('SCRIPT.md', 'SCENES.md', 'TREATMENT.md')}
        if actual_canonical != scope['canonical']:
            raise ValueError('确认原件与语义冻结依据不一致')
    identities=origin or {'creation_id':plan.creation_id,'attempt_id':plan.attempt_id,'plan_id':plan.plan_id}
    if scope['creation_id']!=identities['creation_id'] or scope['attempt_id']!=identities['attempt_id']:
        raise ValueError('语义编译身份无效')
    draft=checkpoint['draft'].encode()
    if hashlib.sha256(draft).hexdigest()!=checkpoint['draft_sha256']:
        raise ValueError('语义草稿摘要无效')
    if read_file(root,'SEMANTIC_PLAN.json')!=draft:raise ValueError('语义草稿原件变化')
    authority_inputs, authority_catalog = None, None
    if policy == AUTHORITY_POLICY:
        from easel.integrations import planning_authority as authority
        if attempt is None or Path(attempt['workspace']['path']).resolve() != Path(root).resolve():
            raise ValueError('新语义合同必须使用实际Attempt验证冻结来源')
        if attempt['creation_id'] != plan.creation_id or attempt['attempt_id'] != plan.attempt_id:
            raise ValueError('新语义合同Attempt身份不符')
        authority_inputs = authority.load_inputs(attempt, actual_canonical,
            {'context_refs':scope['context_refs']}, mode, allow_missing_canonical=origin is not None)
        if scope.get('authority_inputs') != authority_inputs:
            raise ValueError('实际冻结来源与语义快照不一致')
        actual_catalog = source_catalog(actual_canonical, {'creator_context':authority_inputs['creator_context']})
        if scope['catalog'] != actual_catalog:
            raise ValueError('scope及声音身份目录与实际冻结来源不一致')
    original=compile_draft(draft,creation_id=scope['creation_id'],attempt_id=scope['attempt_id'],
        refs=scope['context_refs'],mode=mode,script=script,allowed_refs=scope['catalog'],compiler_policy=policy,
        authority_inputs=authority_inputs)
    if original.model_dump(mode='json')!=checkpoint['plan'] or original.plan_id!=identities['plan_id']:
        raise ValueError('语义快照不能导出Plan')
    expected=original.model_copy(update={'creation_id':plan.creation_id,'attempt_id':plan.attempt_id,'plan_id':plan.plan_id})
    if expected!=plan:raise ValueError('正式Plan与语义快照不一致')
    if policy == AUTHORITY_POLICY:
        authority_catalog = authority.catalog(authority_inputs,
            authority.applied_operations(parse_draft(draft), original, mode))
        if checkpoint.get('authority_catalog') != authority_catalog:
            raise ValueError('来源资格或实际操作目录不能从冻结原件复算')
    if policy != LEGACY_POLICY and checkpoint.get('batches_sha256') != digest(
            classification_batches(original,mode,canonical=scope['canonical'],compiler_policy=policy,
                                   authority_catalog=authority_catalog)):
        raise ValueError('分类政策、确认依据或单元摘要变化')
    requirements=assemble_requirements(original,mode,checkpoint['responses'],canonical=scope['canonical'],compiler_policy=policy,
                                       authority_catalog=authority_catalog)
    if read_planning_requirements(read_file(root,'MATERIAL_REQUIREMENTS.json').decode())!=requirements:
        raise ValueError('正式sidecar与语义编译结果不一致')
    return {'path':'planning/SEMANTIC_CHECKPOINT.json','sha256':hashlib.sha256(raw).hexdigest(),
            'draft_sha256':checkpoint['draft_sha256'],'policy':policy,
            **({'origin':origin} if origin else {})}
