"""vNext policy in the existing Planning request/recovery and publish boundary."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from copy import deepcopy

from easel import output_admission as admission

from easel.integrations import planning_authority as authority
from easel.integrations import planning_semantic_review as review
from easel.integrations import planning_candidate_review as correction
from easel.integrations.planning_capture import capture
from easel.integrations.planning_result_contract import SemanticProposal, MAX_RESULT_BYTES, semantic_tool_schema, FLEXIBLE_QUERY_POLICY
from easel.integrations import planning_structured as structured
from easel.integrations import planning_review_support as support
from easel.integrations import planning_wire as wire
from easel.integrations import planning_staged_proposal as staged
from easel.integrations import planning_input_view as input_views
from easel.integrations.semantic_boundary import POLICY, parse_proposal, project_proposal
from easel.integrations.semantic_planning import source_catalog, write_file
from easel.materials.store import AttemptMaterialStore

STATE_KEY = 'semantic-planning-vnext'
STAGE_OWNERSHIP = {
    'voice_catalog': 'Frozen creative identity references, not Provider preset IDs or an available-voice list.',
    'voice_planning': 'Preserve frozen identity and expression; this stage does not choose a technical preset or prove execution binding.',
    'bgm_planning': 'Preserve required/optional, sound intent and source authorization; do not invent a track or license.',
    'material_binding': 'Actual track/file, observation, Rights and supported execution resources bind in Material; their absence before search is not itself unknown creative intent.',
    'source_obligation': 'Each material Need, including optional, requires an actual material/source obligation; a fade or subtitle edit alone does not create an SFX/image asset.',
    'unknown': 'Unknown intent/identity/authorization remains unresolved; never delete or guess it to advance.',
}
VIEW_CHECKPOINT = 'semantic-planning-frozen@9'
CHECKPOINT = 'semantic-planning-frozen@7'
STAGED_CHECKPOINT = 'semantic-planning-frozen@8'
FRAME_CHECKPOINT = 'semantic-planning-frozen@6'
WIRE_CHECKPOINT = 'semantic-planning-frozen@5'
SUPPORTED_CHECKPOINT = 'semantic-planning-frozen@4'
TOOL_A_CHECKPOINT = 'semantic-planning-frozen@3'
LEGACY_CHECKPOINT = 'semantic-planning-frozen@2'
VIEW_JOURNAL = 'semantic-planning-checkpoint@9'
JOURNAL = 'semantic-planning-checkpoint@7'
STAGED_JOURNAL = 'semantic-planning-checkpoint@8'
FRAME_JOURNAL = 'semantic-planning-checkpoint@6'
WIRE_JOURNAL = 'semantic-planning-checkpoint@5'
SUPPORTED_JOURNAL = 'semantic-planning-checkpoint@4'
TOOL_A_JOURNAL = 'semantic-planning-checkpoint@3'
LEGACY_JOURNAL = 'semantic-planning-checkpoint@2'
MAX_CHECKPOINT_BYTES = 32 * MAX_RESULT_BYTES
# A technical bound, never authorization to spend. The real evaluator's
# shared submission/time/subscription ledger remains independently binding.
MAX_PLANNING_CALLS = 30
TOOL_A_RUNTIME_SHA = 'd1fcdf97eb14318e7dbeb251f97b8f525c5ff38df97a699c0e681e982b5ac3b9'


SUPPORTED_RUNTIME_SHA = 'b9253571641373c33a4e2c2cf5f049f12ed97d99a8ff03910f776f3144779e44'


def transport_identity(catalog, *, supported=True, runtime_sha=None, projected=False, atomic=False, source_bound=False, staged_a=False, source_view=False, intake_inputs=None, intake_policy=None):
    if intake_inputs is not None and intake_policy is None:
        intake_policy = review.INTAKE_POLICY
    canonical = semantic_tool_schema(catalog, compiled=atomic,
        flexible_queries=intake_policy == 'confirmed-planning-intake@6')
    projection = wire.project(canonical, 'A', atomic_framing=atomic) if projected else None
    request = structured.request_for(projection.schema if projection else canonical)
    selection = (input_views.SourceSelection(canonical, catalog).schema if source_view else
                 staged.StagedProposal(canonical).selection_schema) if staged_a else None
    if intake_inputs is not None:
        if not source_view or not staged_a:
            raise ValueError('Confirmed intake requires the versioned staged input view')
        intake_policy = review.INTAKE_POLICY if intake_policy is None else intake_policy
        if intake_policy not in review.INTAKE_POLICIES:
            raise ValueError('Unknown confirmed Planning intake policy')
        selection = review.intake_selection_schema(selection, intake_inputs)
    elif intake_policy is not None:
        raise ValueError('An intake policy requires its frozen inputs')
    return {'policy': structured.VERSION, 'reply_contract': structured.CONTRACT,
            **({'intake_policy': intake_policy} if intake_inputs is not None else {}),
            **({'output_admission': admission.policy_identity(admission.SELECTION_PROFILE)}
               if intake_policy in {'confirmed-planning-intake@5', 'confirmed-planning-intake@6'} else {}),
            **({'query_cardinality_policy': FLEXIBLE_QUERY_POLICY}
               if intake_policy == 'confirmed-planning-intake@6' else {}),
            'schema_sha256': request['schemaSha256'],
            **({'producer': {'policy': staged.POLICY, 'selection_schema_sha256':
                structured.request_for(selection)['schemaSha256']}}
               if staged_a else {}),
            **({'input_view_policy': input_views.PlanningInputView.POLICY,
                'source_selection_policy': input_views.SourceSelection.POLICY} if source_view else {}),
            **({'review_source_policy': review.SOURCE_POLICY} if source_bound else {}),
            'runtime_sha256': (runtime_sha or authority.digest(structured.RUNTIME_PARTS)) if supported else TOOL_A_RUNTIME_SHA,
            **({'support_policy': support.REVISION} if supported else {}),
            **({'wire': projection.identity} if projection else {})}


def validate_transport(version, scope, *, frozen=False):
    current, legacy = (CHECKPOINT, LEGACY_CHECKPOINT) if frozen else (JOURNAL, LEGACY_JOURNAL)
    previous = SUPPORTED_CHECKPOINT if frozen else SUPPORTED_JOURNAL
    tool_a = TOOL_A_CHECKPOINT if frozen else TOOL_A_JOURNAL
    if version == legacy and 'transport' not in scope:
        return False
    intake = intake_enabled(scope)
    if intake and version != (VIEW_CHECKPOINT if frozen else VIEW_JOURNAL):
        raise ValueError('Confirmed intake cannot reinterpret an older Planning protocol')
    if version == (VIEW_CHECKPOINT if frozen else VIEW_JOURNAL):
        if (scope.get('transport') != transport_identity(scope['catalog'], projected=True, atomic=True,
                source_bound=True, staged_a=True, source_view=True,
                intake_inputs=scope['inputs'] if intake else None,
                intake_policy=scope.get('transport', {}).get('intake_policy'))
                or scope.get('input_view') != input_views.PlanningInputView(scope['inputs'], scope['catalog']).identity):
            raise ValueError('Planning input view transport identity changed')
        return True
    if version == (STAGED_CHECKPOINT if frozen else STAGED_JOURNAL) and scope.get('transport') == transport_identity(
            scope['catalog'], projected=True, atomic=True, source_bound=True, staged_a=True):
        return True
    if version == current and scope.get('transport') == transport_identity(scope['catalog'], projected=True, atomic=True, source_bound=True):
        return True
    if version == (FRAME_CHECKPOINT if frozen else FRAME_JOURNAL) and scope.get('transport') == transport_identity(scope['catalog'], projected=True, atomic=True):
        return True
    if version == (WIRE_CHECKPOINT if frozen else WIRE_JOURNAL) and scope.get('transport') == transport_identity(scope['catalog'], projected=True):
        return True
    if version == previous and scope.get('transport') in (transport_identity(scope['catalog']),
            transport_identity(scope['catalog'], runtime_sha=SUPPORTED_RUNTIME_SHA)):
        return True
    if version == tool_a and scope.get('transport') == transport_identity(scope['catalog'], supported=False):
        return True
    raise ValueError('Frozen Planning transport identity changed; no downgrade or refreshed allowance')


def intake_enabled(scope):
    policy = scope.get('transport', {}).get('intake_policy')
    if policy is not None and policy not in review.INTAKE_POLICIES:
        raise ValueError('Unknown confirmed Planning intake policy')
    return policy is not None


def intake_selection(scope, schema):
    return review.intake_selection_schema(schema, scope['inputs']) if intake_enabled(scope) else schema


def admission_enabled(scope):
    return scope.get('transport', {}).get('intake_policy') in {'confirmed-planning-intake@5', 'confirmed-planning-intake@6'}


def flexible_queries(scope):
    return scope.get('transport', {}).get('intake_policy') == 'confirmed-planning-intake@6'


def query_schema(scope, *, compiled=True):
    return semantic_tool_schema(scope['catalog'], compiled=compiled,
                                flexible_queries=flexible_queries(scope))


def selection_admission(scope, call, schema, schema_binding):
    """Rebuild a receipt from the Owner-validated original capture, never a flag.

    The existing Delivery boundary owns concrete run/tool-call terminal checks.
    Its unique capture session/request/raw SHA is the provenance reference; no
    synthetic run or tool-call identity is introduced by normalization.
    """
    raw = call.get('reply')
    if (not admission_enabled(scope) or call.get('result') != 'MODEL_COMPLETED'
            or not isinstance(raw, str)
            or hashlib.sha256(raw.encode()).hexdigest() != call.get('reply_sha256')):
        raise ValueError('Selection admission requires the original completed capture')
    binding = {'creation_id': scope['creation_id'], 'attempt_id': scope['attempt_id'],
        'frozen_inputs_sha256': authority.digest(scope['inputs']),
        'scope_sha256': authority.digest(scope), 'runtime_sha256': scope['transport']['runtime_sha256'],
        'tool': structured.TOOL, 'reply_contract': structured.CONTRACT,
        'capture_reference': {'kind': 'owner-validated-original-capture',
            'stage': 'A-selection', 'session': call['session'],
            'request_sha256': call['request_sha256'], 'raw_sha256': call['reply_sha256']},
        'stage_schema_binding': schema_binding}
    result = admission.admit_json(raw, schema, stage='A-selection', channel='tool',
        binding=binding, profile=admission.SELECTION_PROFILE, max_bytes=MAX_RESULT_BYTES)
    receipt, value = result['receipt'], result['candidate']
    # Preserve the pre-existing route for shape-safe candidate leaf faults and
    # missing BGM. Eligibility does not spend or enlarge the shared allowance.
    if value is not None and receipt['remaining_errors']['total']:
        try:
            view = input_views.PlanningInputView(scope['inputs'], scope['catalog'])
            decoded = view.codec.decode(value, view.codec.identity, diagnostic=True)
            staged.StagedProposal(query_schema(scope)).details_contract(
                decoded, diagnostic=True)
        except (ValueError, TypeError, KeyError):
            receipt['decision']['code'] = 'SELECTION_SHAPE_OR_REFERENCE_INVALID'
        else:
            receipt['decision'].update(outcome='BOUNDED_REPAIR', code='EXISTING_CANDIDATE_REPAIR_REQUIRED')
    return result


def require_selection_admission(result):
    if result['receipt']['decision']['outcome'] == 'REJECT':
        raise ValueError('Planning selection admission rejected: ' + result['receipt']['decision']['code'])
    return result['candidate']


def intake_targets(scope, value):
    if not intake_enabled(scope):
        return review.structural_targets(value)
    targets = review.intake_targets(value, scope['inputs'], flexible_queries=flexible_queries(scope))
    maximum = query_schema(scope)['properties']['needs']['maxItems']
    if any(t['kind'] == 'confirmed_music_coverage' for t in targets) and len(value['needs']) >= maximum:
        raise ValueError('Required BGM cannot fit without removing existing Needs')
    return targets


def check_existing_sources(attempt):
    """Check a new-policy journal before any legacy restoration can hide edits."""
    store = AttemptMaterialStore(attempt['workspace']['path'])
    state = store.read_recovery_record(STATE_KEY)
    if state is None:
        return
    if state.get('terminal_failure'):
        raise ValueError('Original Planning frozen-source violation is reject-only')
    scope = state['scope']
    try:
        if authority.load_inputs(attempt, scope['canonical'],
                {'context_refs': scope['context_refs']}, scope['mode']) != scope['inputs']:
            raise ValueError('Frozen Planning sources changed before recovery')
    except ValueError:
        state['terminal_failure'] = 'FROZEN_SOURCE_CHANGED'
        store.write_recovery_record(STATE_KEY, state)
        raise


def policy_for(attempt, *, default=POLICY):
    """New entrance uses vNext; old pending journals retain their exact policy."""
    store = AttemptMaterialStore(attempt['workspace']['path'])
    old = store.read_recovery_record('semantic-planning-v3')
    new = store.read_recovery_record(STATE_KEY)
    if old is not None and new is not None:
        raise ValueError('Multiple Planning policies own this Attempt; no dispatch')
    if old is not None:
        from easel.integrations.semantic_planning import _compiler_policy
        policy = old.get('scope', {}).get('policy')
        if not policy: raise ValueError('Old pending policy missing; never assume the current default')
        return _compiler_policy(policy)
    if new is not None:
        if new.get('scope', {}).get('policy') != POLICY:
            raise ValueError('Unknown vNext journal policy; no downgrade')
        validate_transport(new.get('schema'), new['scope'])
        return POLICY
    if default != POLICY:
        from easel.integrations.semantic_planning import _compiler_policy
        return _compiler_policy(default)
    return POLICY


def a_message(scope):
    atomic = scope.get('transport', {}).get('wire', {}).get('semantic_representation') == wire.FRAME_POLICY
    return review.checked_message('〔Easel Semantic Planning vNext〕\n'
        '只提出语义计划；正式ID、路径、hash、技术别名、sidecar、缓存及文件由程序负责。'
        '完整承接冻结要求，不省略required。条件逐项保留完整含义并区分强度与素材/后期/叙事责任；'
        '用途不改变源属性归属。源画幅/源时长是独立语义选择，不能自动继承成片规格。'
        '软风格不升级required，Preparation不创造作者新增授权。scope/continuity/voice只选目录。'
        'queries为可选检索提示，不是视觉原文或硬filter。未知含义写unresolved，不能猜测。'
        + ('通过唯一 submit_semantic_plan 工具提交完整语义计划，参数遵守工具Schema；'
           '不写文件、不调用供应、生成或制作。\n' if 'transport' in scope else
           '只返回schema JSON；不写文件，不调用工具、供应、生成或制作。\n') + review.compact({
            **({'transport': scope['transport']} if 'transport' in scope else
               {'schema': SemanticProposal.model_json_schema()}), 'inputs': scope['inputs'],
            'catalog': scope['catalog'],
            **({'program_owned_voice': '已确认预置旁白由程序派生唯一required Voice并预留1个Need位置；A不得重复生成Voice。完整声音意图保持冻结，具体音乐file由Material绑定，未知语义仍写unresolved。'}
               if scope['catalog'].get('derived_voice') else {}),
            **({'wire_representation': wire.GUIDANCE + (wire.FRAME_GUIDANCE if atomic else '')}
               if 'wire' in scope.get('transport', {}) else {}),
            **({'stage_ownership': STAGE_OWNERSHIP} if atomic else {})}))


def descriptors(targets):
    return [{k: v for k, v in target.items() if k != 'annotation'} for target in targets]


def staged_a_message(scope, stage, *, selection=None, binding=None):
    # Full frozen originals remain available in both requests. No new creative
    # interpretation, source segmentation, or approval is derived here.
    context = json.loads(a_message(scope).splitlines()[-1])
    if stage == 'A-selection':
        instruction = ('先列出完整素材候选的scope/role/modality/necessity/continuity_choices及unresolved。'
            '这一轮不填写条件、用途、检索或模态详情。候选不是批准，不能漏掉required或将偏好升级required。')
    elif stage == 'A-details':
        instruction = ('为每个固定slot提交完整条件、用途和该模态详情；不重填或更改候选header，不遗漏或新增slot。'
            '条件逐项保留完整含义，区分required/preference及素材/后期/叙事责任；用途不改变源属性归属。'
            '源画幅/源时长不自动继承成片规格。queries仅是可选检索提示，不是硬filter。')
        context.update(candidate_slots={f'slot_{i:03}': need for i, need in enumerate(selection['needs'])},
                       selection_unresolved=selection['unresolved'], detail_binding=binding)
    else:
        raise ValueError('Unknown staged Planning request')
    return review.checked_message(f'〔Easel Semantic Planning vNext {stage}〕\n' + instruction +
        'scope/continuity/voice只选冻结目录，编号不是分镜序号；Preparation不创造新增授权。'
        '保留未知语义，不猜测、不删除；正式ID/hash/路径/sidecar由程序负责。'
        '仅用submit_semantic_plan按工具Schema提交，不写文件、不供应、不生成、不制作。\n' + review.compact(context))


def view_a_message(scope, view, stage, *, selection=None, binding=None):
    expanded_audio = scope.get('transport', {}).get('intake_policy') in {review.AUDIO_INTAKE_POLICY, review.P3_INTAKE_POLICY, review.RELATIONAL_INTAKE_POLICY, review.ADMISSION_INTAKE_POLICY, review.INTAKE_POLICY}
    presented = deepcopy(view.view) if expanded_audio else view.view
    if expanded_audio:
        # Resolve the two known text references from verified frozen inputs.
        # Preserve the canonical view/snapshot and every original word; a model
        # must not interpret byte ranges to recover its creative input.
        proposal = scope['inputs'].get('proposal')
        if isinstance(proposal, dict):
            for field in ('sound', 'sound_source'):
                if field in proposal:
                    if not isinstance(proposal[field], str):
                        raise ValueError('Frozen audio input must remain literal text')
                    presented['inputs']['proposal'][field] = proposal[field]
    context = {'input_view': presented, 'stage_ownership': STAGE_OWNERSHIP}
    if admission_enabled(scope):
        context['output_admission'] = scope['transport']['output_admission']
    if correction.enabled(scope):
        context['candidate_review_policy'] = correction.policy_for(scope)
    if expanded_audio:
        context['scope_reference_contract'] = {
            'global_scope': view.codec.to_wire['global'],
            'usage_scope_is_evidence': False,
            'instruction': 'scope选择工具enum中的实际使用范围，不是声音原文的出处或字节区间。全片素材可选global_scope；局部素材可选对应场景引用。原文支持由完整冻结内容核对，不根据范围数字拼造src引用。'}
    if intake_enabled(scope):
        context['query_contract'] = ('视觉queries可以省略或为空；提供时必须是三个不同的简短英文短语，'
                                     '不得用中文查询或一中一英组合；查询不是素材硬条件。')
        if flexible_queries(scope):
            context['query_cardinality_policy'] = FLEXIBLE_QUERY_POLICY
            context['query_contract'] = ('视觉queries允许0至3条不同的简短英文短语，按实际需要提供，不凑数、不补词；'
                                         '保留每条提示，完整素材要求仍写入conditions，查询不是硬条件。')
        music_mode = review.confirmed_music_mode(scope['inputs'])
        if music_mode:
            context['confirmed_music_requirement'] = {
                'source': 'confirmed proposal/specs/audio_mode', 'value': music_mode,
                'required_modality': 'bgm',
                'instruction': '已确认音乐必须由required BGM候选承接；条件和sound由你依据完整冻结声音方案提出。实际文件/许可由Material处理，不能漏项或改optional。'}
    if correction.policy_for(scope) == correction.RELATIONAL_POLICY:
        context['semantic_need_ownership'] = {
            'A_selection_owns': '逐项提出冻结分镜需要的image/video语义候选，以及独立BGM/SFX候选；尚未找到素材不影响先提出Need。',
            'A_details_owns': '为已固定的每个Need填写源素材条件、用途和模态详情。',
            'program_owns': '编译Need身份，随后检索/生成并绑定asset；不会替A凭空补列被遗漏的视觉Need。',
            'only_preplanned_exception': '已明确标记program_owned_voice的预置旁白；这个例外不适用于image/video/BGM/SFX。',
            'check_before_submit': '检查冻结画面是否均有候选承担；字幕或镜头运动只是后期，不替代其底下需要的照片或视频。'}
    if stage == 'A-selection':
        instruction = ('只填写工具Schema列出的素材候选header与unresolved；完整承接required义务。'
                       'scope必须选择原文旁对应kind的src引用，它是文本位置而非镜头编号。')
    elif stage == 'A-details':
        opaque = view.opaque_headers(selection)
        context.update(candidate_slots={f'slot_{i:03}': need for i, need in enumerate(opaque['needs'])},
                       selection_unresolved=opaque['unresolved'], detail_binding=binding)
        instruction = ('为每个固定slot填写完整条件、用途与相应模态详情；不能改header或增删slot。'
                       'required/preference及素材/后期/叙事责任由完整语义决定；源画幅/时长不继承成片规格。')
    else:
        raise ValueError('Unknown input-view Planning stage')
    if correction.policy_for(scope) == correction.RELATIONAL_POLICY and stage == 'A-selection':
        instruction = ('你负责提出语义素材Need，不是等待程序自动生成候选。先完整承接冻结画面的image/video需求，'
                       '再列独立配乐/音效；仅已确认的程序旁白不重复提出。素材文件尚未检索不等于Need可以省略。' + instruction)
    if view.codec.empty_continuity:
        context['continuity'] = '冻结目录为空；本版不请求模型填空列表，由程序确定性补[]。'
    if scope['catalog'].get('derived_voice'):
        context['program_owned_voice'] = ({
            'already_planned': True,
            'may_resubmit_as_other_modality': False,
            'instruction': '确认预置旁白及其朗读控制已有唯一程序Voice承担；它不是待规划素材，不能以Voice、BGM、SFX、image或video重新建候选。音乐候选只承担独立配乐意图。'} if expanded_audio else
            '确认预置旁白已由程序派生唯一required Voice；不得再建Voice或用image代替它。')
    return review.checked_message(f'〔Easel Semantic Planning vNext {stage}〕\n' + instruction +
        '保留未知语义，不猜测、不删除；节目字幕和后期效果自身不建立图片素材Need。'
        'ID/hash/sidecar和实际文件绑定由程序负责；素材尚未搜索不是未知创作意图。'
        '默认值不能覆盖已确认要求，Preparation不创造授权。只用submit_semantic_plan，不写文件、不供应或制作。\n'
        + review.compact(context))


def detail_binding(scope, selection, raw_sha256, contract, view=None, *, admission_receipt=None):
    if admission_enabled(scope) and admission_receipt is None:
        raise ValueError('Details requires the durable selection admission receipt')
    return {**contract['identity'], 'scope_sha256': authority.digest(scope),
            'raw_selection_sha256': raw_sha256, 'runtime_sha256': scope['transport']['runtime_sha256'],
            **({'selection_admission_sha256': authority.digest(admission_receipt),
                'normalized_selection_sha256': authority.digest(selection),
                'normalized_wire_sha256': admission_receipt['normalized_sha256']}
               if admission_enabled(scope) else {}),
            **({'input_view': view.identity, 'opaque_headers_sha256': authority.digest(view.opaque_headers(selection))}
               if view is not None else {})}


def validate_canonical(catalog, value, *, compiled=False):
    if not wire.Draft202012Validator(semantic_tool_schema(catalog, compiled=compiled)).is_valid(value):
        raise ValueError('Complete canonical Planning schema rejected')


def repair_message(scope, original, targets, context=None):
    atomic = scope.get('transport', {}).get('wire', {}).get('semantic_representation') == wire.FRAME_POLICY
    supported = scope.get('transport', {}).get('support_policy') == support.REVISION
    support_batch = context if supported and context and context.get('support_policy') == support.REVISION else None
    patcher = correction if correction.enabled(scope) else review
    schema = patcher.patch_schema(targets, support_batch=support_batch, slots=supported)
    if 'wire' in scope.get('transport', {}):
        schema = wire.project(schema, 'repair', atomic_framing=atomic).schema
    if correction.enabled(scope):
        return review.checked_message('〔Easel Planning vNext 单次局部修复〕\n'
            '只提交固定target槽位对应的value，不提交整个对象，不删除Need或原未决报告。'
            'confirmed_necessity只允许按独立冻结依据将被挑战字段从optional改required；'
            'visual_choices仍须保持原conditions/queries/necessity，不得借整体头部升降级。'
            'candidate_answer只修该条响应并提供真实冻结引用；其他已接受答案不可变。'
            '未列出的字段及全部原件不可变，不推定任何授权或素材就绪。修后重新独立核对受影响义务。'
            '不写文件、不供应、不制作。\n' + review.compact({
                'schema': schema, 'targets': descriptors(targets), 'original': original,
                'inputs': scope['inputs'], 'review_context': context,
                'candidate_review_policy': correction.policy_for(scope),
                'wire_representation': wire.GUIDANCE + (wire.FRAME_GUIDANCE if atomic else '')}))
    return review.checked_message('〔Easel Planning vNext 单次局部修复〕\n' +
        ('仅修targets列出的未接受局部，按数组下标对应固定target槽位。原件、已接受语义、必要性、'
         if supported else '仅修targets列出的未接受局部，target是程序提供的整数标签。原件、已接受语义、必要性、') +
        '已接受答案及所有其他字段不可变。不能返回整个对象、删需求、扩授权或放宽准入。'
        'visual_choices的value交同一Need，仅修其header，conditions/queries/necessity须保持。'
        'coverage缺口只能补充有冻结支持的视觉Need，不能改掉原Need。改后再次独立复核。'
        + ('通过唯一工具按schema固定target槽位提交value；不填写target/question/evidence身份，不写文件。\n'
           if supported else '只返回schema JSON，不调用工具或写文件。\n') + review.compact({
            'schema': schema, 'targets': descriptors(targets),
            **({'wire_representation': wire.GUIDANCE + (wire.FRAME_GUIDANCE if atomic else '')}
               if 'wire' in scope.get('transport', {}) else {}),
            'original': original, 'inputs': scope['inputs'], 'review_context': context}))


def run(attempt, planning_context, canonical, mode, route, dispatch):
    store = AttemptMaterialStore(attempt['workspace']['path'])
    root = store.attempt_root
    inputs = authority.load_inputs(attempt, canonical, planning_context, mode)
    catalog = source_catalog(canonical, {'creator_context': inputs['creator_context'], 'proposal': inputs.get('proposal')})
    scope = {'policy': POLICY, 'creation_id': attempt['creation_id'], 'attempt_id': attempt['attempt_id'],
             'context_refs': planning_context['context_refs'], 'canonical': canonical, 'mode': mode,
             'inputs': inputs, 'catalog': catalog}
    state = store.read_recovery_record(STATE_KEY)
    uses_view = state is None or state.get('schema') == VIEW_JOURNAL
    uses_staged = state is None or state.get('schema') in {VIEW_JOURNAL, STAGED_JOURNAL}
    uses_source = state is None or state.get('schema') in {VIEW_JOURNAL, STAGED_JOURNAL, JOURNAL}
    uses_atomic = state is None or state.get('schema') in {VIEW_JOURNAL, STAGED_JOURNAL, JOURNAL, FRAME_JOURNAL}
    uses_wire = state is None or state.get('schema') in {VIEW_JOURNAL, STAGED_JOURNAL, JOURNAL, FRAME_JOURNAL, WIRE_JOURNAL}
    uses_support = state is None or state.get('schema') in {VIEW_JOURNAL, STAGED_JOURNAL, JOURNAL, FRAME_JOURNAL, WIRE_JOURNAL, SUPPORTED_JOURNAL}
    uses_tool = state is None or validate_transport(state.get('schema'), state['scope'])
    view = input_views.PlanningInputView(inputs, catalog) if uses_view else None
    if view is not None:
        scope['input_view'] = view.identity
    if uses_tool:
        scope['transport'] = state['scope']['transport'] if state is not None else transport_identity(catalog, supported=uses_support, projected=True, atomic=True, source_bound=True, staged_a=uses_staged, source_view=uses_view, intake_inputs=inputs if uses_view else None)
    if state is None:
        if store.read_recovery_record('semantic-planning-v3') is not None or list(
                (root / 'materials/recoveries').glob('planning-structure-repair-*.json')):
            raise ValueError('Old Planning journal must resume its exact policy, not obtain new repair')
        state = {'schema': VIEW_JOURNAL, 'scope': scope, 'route': route,
                 'calls': {}, 'repair_used': False, 'input_view_snapshot': view.snapshot()}
        store.write_recovery_record(STATE_KEY, state)
    elif (state.get('scope') != scope or state.get('route') != route):
        raise ValueError('Frozen vNext input, policy or execution route changed; no refreshed allowance')
    if not admission_enabled(scope) and 'admissions' in state:
        raise ValueError('Selection admission policy cannot be removed or downgraded')
    if state.get('terminal_failure'):
        raise ValueError('Original Planning frozen-source violation is reject-only; no recovery dispatch')
    if view is not None and state.get('input_view_snapshot') != view.snapshot():
        raise ValueError('Persisted input view is not derived from frozen sources')
    def save(): store.write_recovery_record(STATE_KEY, state)
    def frozen():
        try:
            if authority.load_inputs(attempt, canonical, planning_context, mode) != inputs:
                raise ValueError('Frozen Planning sources changed during execution')
        except ValueError:
            state['terminal_failure'] = 'FROZEN_SOURCE_CHANGED'
            save()
            raise
    def invoke(key, message, schema=None):
        frozen()
        if key not in state['calls'] and len(state['calls']) >= MAX_PLANNING_CALLS:
            raise ValueError('Fixed Planning call range exhausted; no new dispatch')
        try:
            schema = query_schema(scope, compiled=uses_atomic) if uses_tool and key == 'A' else schema
            if uses_wire:
                projection = wire.project(schema, key, atomic_framing=uses_atomic)
                binding = state.setdefault('schema_bindings', {}).get(key)
                if binding is not None and binding != projection.identity:
                    raise ValueError('Planning stage wire identity changed')
                state['schema_bindings'][key] = projection.identity
                save()  # Exact canonical/wire identity precedes submission.
                schema = projection.schema
            result = capture(state['calls'], key, review.checked_message(message),
                f"semantic-{attempt['attempt_id']}-vnext-{key}",
                lambda key, text, session: dispatch('structure_repair' if key == 'repair' else 'planning', text, session,
                    **({'structured_result': structured.request_for(schema)} if schema is not None else {}),
                    **({'expected_runtime_sha256': scope['transport']['runtime_sha256']} if uses_tool else {})), save)
        finally:
            frozen()  # Async/uncertain results cannot skip source-integrity recording.
        return result
    def candidate(key, original, schema, *, strict=False):
        if not uses_wire:
            return original
        projection = wire.project(schema, key, atomic_framing=uses_atomic)
        if state['schema_bindings'].get(key) != projection.identity:
            raise ValueError('Planning stage wire identity changed')
        errors = projection.errors(original)
        diagnostic = {'wire_errors': errors, 'original_sha256': state['calls'][key]['reply_sha256']}
        previous = state.setdefault('wire_diagnostics', {}).get(key)
        if previous is not None and previous != diagnostic:
            raise ValueError('Original wire validation changed')
        state['wire_diagnostics'][key] = diagnostic
        save()
        if strict and errors:
            raise ValueError('Complete Planning wire schema rejected')
        return projection.decode_valid(original) if strict else projection.decode_candidate(original)
    def b_message(batch):
        if not uses_wire:
            return review.checked_message(review.review_message(batch))
        transported = {**batch, 'response_schema': wire.project(batch['response_schema'], 'B', atomic_framing=uses_atomic).schema,
                       'wire_representation': wire.GUIDANCE}
        return review.checked_message(review.review_message(transported))
    def repair(stage, original, targets, context=None):
        message = repair_message(scope, original, targets, context)  # Capacity before consuming allowance.
        repair_identity = {'stage': stage, 'targets': descriptors(targets),
                           'original_sha256': authority.digest(original), 'context_sha256': authority.digest(context)}
        if state['repair_used'] and state.get('repair') != repair_identity:
            raise ValueError('Whole Planning shared repair allowance exhausted')
        state.update(repair_used=True, repair=repair_identity)
        save()  # Written before dispatch; restart never refreshes allowance.
        support_batch = context if uses_support and context and context.get('support_policy') == support.REVISION else None
        patcher = correction if correction.enabled(scope) else review
        schema = patcher.patch_schema(targets, support_batch=support_batch, slots=True) if uses_support else None
        output = invoke('repair', message, schema)
        decoded = candidate('repair', output, schema, strict=True) if uses_wire else output
        patches = patcher.decode_patch_slots(decoded, targets, support_batch=support_batch) if uses_support else decoded
        return patcher.apply_patches(original, patches, targets, support_batch=support_batch), output

    if uses_staged:
        codec = staged.StagedProposal(query_schema(scope))
        selection_schema = intake_selection(scope, view.codec.schema if view is not None else codec.selection_schema)
        a_message_for = (lambda stage, **kw: view_a_message(scope, view, stage, **kw)) if view is not None else (lambda stage, **kw: staged_a_message(scope, stage, **kw))
        selected = invoke('A-selection', a_message_for('A-selection'), selection_schema)
        selected = candidate('A-selection', selected, selection_schema)
        selected_receipt = None
        if admission_enabled(scope):
            admitted = selection_admission(scope, state['calls']['A-selection'], selection_schema,
                                           state['schema_bindings']['A-selection'])
            previous = state.get('admissions', {}).get('A-selection')
            if previous is None and (state.get('detail_binding') is not None or 'A-details' in state['calls']):
                raise ValueError('Selection admission receipt missing after details binding')
            if previous is not None and previous != admitted:
                raise ValueError('Persisted selection admission or normalized candidate changed')
            state.setdefault('admissions', {})['A-selection'] = admitted
            save()  # Completed raw capture is reused if this local write fails.
            selected = require_selection_admission(admitted)
            selected_receipt = admitted['receipt']
        if view is not None:
            selected = view.codec.decode(selected, view.codec.identity, diagnostic=True)
        contract = codec.details_contract(selected, diagnostic=True)
        binding = detail_binding(scope, selected, state['calls']['A-selection']['reply_sha256'], contract, view,
                                 admission_receipt=selected_receipt)
        if state.get('detail_binding') is not None and state['detail_binding'] != binding:
            raise ValueError('Persisted details identity changed')
        state['detail_binding'] = binding
        save()  # Durable original selection and details identity precede any details dispatch.
        details = invoke('A-details', a_message_for('A-details', selection=selected, binding=binding), contract['schema'])
        details = candidate('A-details', details, contract['schema'])
        initial = codec.assemble_candidate(selected, details, contract['identity'])
        value = initial
        invalid_a_wire = any(state['wire_diagnostics'][key]['wire_errors'] for key in ('A-selection', 'A-details'))
    else:
        initial = invoke('A', a_message(scope))
        value = candidate('A', initial, query_schema(scope, compiled=uses_atomic)) if uses_wire else initial
        invalid_a_wire = uses_wire and state['wire_diagnostics']['A']['wire_errors']
    correction_result = None
    if correction.enabled(scope):
        correction_result = correction.evaluate(initial, scope, view, invoke, candidate, repair,
                                                max_calls=MAX_PLANNING_CALLS)
        proposal = correction_result['proposal']
        directory, responses = correction_result['directory'], correction_result['responses']
        initial_review_value = correction_result['initial_review_value']
        initial_responses, before_semantic = correction_result['initial_responses'], correction_result['before_semantic']
        lineage = correction_result['repair']
    else:
        lineage = None
        targets = intake_targets(scope, value)
        if targets:
            value, output = repair('A', value, targets)
            lineage = {'stage': 'A', 'targets': descriptors(targets), 'output': output}
        elif invalid_a_wire:
            raise ValueError('Invalid wire candidate cannot enter independent review without local repair')
        if intake_enabled(scope) and intake_targets(scope, value):
            raise ValueError('Confirmed intake remains invalid after the single shared repair')
        proposal = parse_proposal(value, catalog)
        if uses_wire:
            validate_canonical(catalog, value, compiled=uses_atomic)
        value = proposal.model_dump(mode='json')
        initial_review_value = value
        directory = review.questions(proposal, inputs, catalog, supported=uses_support, source_bound=uses_source)
        if view is not None: view.check_review(directory)
        initial_responses, responses = [], []
        batches = review.review_batches(directory)
        coverage_count = sum(q['kind'] == 'frozen_visual_coverage' for q in directory['questions'])
        maximum_rechecks = (16 * 13 + coverage_count + 47) // 48
        if (2 if uses_staged else 1) + len(batches) + 1 + maximum_rechecks > MAX_PLANNING_CALLS:
            raise ValueError('Complete review and required recheck exceed fixed Planning call range')
        messages = [b_message(b) for b in batches]
        for index, (batch, message) in enumerate(zip(batches, messages, strict=True)):
            response = invoke(f'B-{index:03}', message, batch['response_schema'] if uses_support else None)
            initial_responses.append(response)
            response = candidate(f'B-{index:03}', response, batch['response_schema']) if uses_wire else response
            if uses_support:
                response = support.decode_slots(response, batch)
            answer_targets = review.answer_targets(response, batch)
            if answer_targets:
                response, output = repair(f'B-{index:03}', response, answer_targets, batch)
                lineage = {'stage': f'B-{index:03}', 'targets': descriptors(answer_targets), 'output': output}
            elif uses_wire and state['wire_diagnostics'][f'B-{index:03}']['wire_errors']:
                raise ValueError('Invalid review wire cannot be accepted without local repair')
            responses.append(review.validate_answers(response, batch))
        targets = review.semantic_targets(directory, responses)
        before_semantic = [r.model_dump(mode='json') for r in responses]
        if targets:
            value, output = repair('semantic', value, targets)
            lineage = {'stage': 'semantic', 'targets': descriptors(targets), 'output': output}
            proposal = parse_proposal(value, catalog)
            if uses_wire:
                validate_canonical(catalog, value, compiled=uses_atomic)
            updated = review.questions(proposal, inputs, catalog, supported=uses_support, source_bound=uses_source)
            if view is not None: view.check_review(updated)
            kept, pending = review.recheck(directory, responses, updated)
            pending_batches = review.review_batches(pending)
            messages = [b_message(b) for b in pending_batches]
            for i, (batch, message) in enumerate(zip(pending_batches, messages, strict=True)):
                response = invoke(f'B-recheck-{i:03}', message, batch['response_schema'] if uses_support else None)
                response = candidate(f'B-recheck-{i:03}', response, batch['response_schema'], strict=True) if uses_wire else response
                if uses_support:
                    response = support.decode_slots(response, batch)
                for answer in review.validate_answers(response, batch).answers:
                    kept[answer.question] = answer.model_dump(mode='json')
            directory = updated
            batches = review.review_batches(directory)
            responses = [review.validate_answers({'answers': [kept[q['question']] for q in b['questions']]}, b)
                         for b in batches]
            if review.semantic_targets(directory, responses):
                raise ValueError('Semantic review still challenged or unresolved after single shared repair')
    plan, requirements, proof = project_proposal(proposal, inputs=inputs, catalog=catalog,
        creation_id=attempt['creation_id'], attempt_id=attempt['attempt_id'],
        refs=planning_context['context_refs'], mode=mode, transport=scope.get('transport'))
    effective = review.compact(proposal.model_dump(mode='json')).encode()
    checkpoint = {'schema': (VIEW_CHECKPOINT if uses_view else STAGED_CHECKPOINT if uses_staged else CHECKPOINT if uses_source else FRAME_CHECKPOINT if uses_atomic else WIRE_CHECKPOINT if uses_wire else SUPPORTED_CHECKPOINT if uses_support else TOOL_A_CHECKPOINT if uses_tool else LEGACY_CHECKPOINT),
        'policy': POLICY, 'scope': scope,
        'initial': initial, 'initial_review_value': initial_review_value,
        **({'admissions': deepcopy(state['admissions'])} if admission_enabled(scope) else {}),
        **({'candidate_correction': correction_result['trace']} if correction_result is not None else {}),
        'initial_responses': initial_responses, 'before_semantic': before_semantic,
        'repair': lineage, 'draft_sha256': hashlib.sha256(effective).hexdigest(),
        **({'assembled_a_sha256': authority.digest(initial), 'detail_binding': state['detail_binding']}
           if uses_staged else {'raw_a_sha256': state['calls']['A']['reply_sha256']}),
        'proposal': proposal.model_dump(mode='json'), 'plan': plan.model_dump(mode='json'),
        'proof': proof, 'review_sha256': authority.digest(directory),
        'responses': [r.model_dump(mode='json') for r in responses],
        **({'schema_bindings': state['schema_bindings'], 'wire_diagnostics': state['wire_diagnostics'],
            'wire_originals': {key: call['reply'] for key, call in state['calls'].items() if key != 'A'}} if uses_wire else {}),
        'capture': {key: {k: v for k, v in call.items() if k != 'reply'}
                    for key, call in state['calls'].items()}}
    encoded = review.compact(checkpoint).encode()
    if len(encoded) > MAX_CHECKPOINT_BYTES:
        raise ValueError('Complete frozen checkpoint exceeds local artifact capacity')
    frozen()
    # Existing atomic file writer: interrupted publication recovers captured
    # results only, and cannot replace different already-published artifacts.
    try:
        if view is not None:
            write_file(root, 'SEMANTIC_INPUT_VIEW.json', review.compact(view.snapshot()).encode())
        if uses_staged:
            for key, name in (('A-selection', 'SEMANTIC_A_SELECTION.json'), ('A-details', 'SEMANTIC_A_DETAILS.json')):
                write_file(root, name, state['calls'][key]['reply'].encode())
            if admission_enabled(scope):
                write_file(root, 'SEMANTIC_A_SELECTION_NORMALIZED.json',
                           admission.canonical_json(state['admissions']['A-selection']['candidate']).encode())
            write_file(root, 'SEMANTIC_A_ASSEMBLY.json', review.compact(initial).encode())
        else:
            write_file(root, 'SEMANTIC_A_RESULT.json', state['calls']['A']['reply'].encode())
        write_file(root, 'SEMANTIC_PLAN.json', effective)
        write_file(root, 'SEMANTIC_CHECKPOINT.json', encoded)
        write_file(root, 'MATERIAL_PLAN.json', (plan.model_dump_json(indent=2) + '\n').encode())
        write_file(root, 'MATERIAL_REQUIREMENTS.json', review.compact(requirements).encode())
    except OSError:
        state['publication_result'] = 'PERSIST_FAILED'
        save()
        raise
    state['publication_result'] = 'ACCEPTED'
    save()
    from easel.output_contract import output_decision
    return {'plan': plan, 'context_refs': plan.context_refs, 'script': canonical['SCRIPT.md'],
            'scenes': canonical['SCENES.md'], 'treatment': canonical['TREATMENT.md'],
            **({'output_admission': {'policy': scope['transport']['output_admission'],
                'selection_decision': state['admissions']['A-selection']['receipt']['decision'],
                'normalization_actions': len(state['admissions']['A-selection']['receipt']['actions']),
                'receipt_sha256': authority.digest(state['admissions']['A-selection']['receipt'])}}
               if admission_enabled(scope) else {}),
            'output_decision': output_decision('planning', 'ACCEPT', 'semantic_compiled', policy_revision=POLICY)}


def read_artifact(root, name, limit=MAX_CHECKPOINT_BYTES):
    path = Path(root) / 'planning' / name
    if path.parent.is_symlink() or path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise ValueError('vNext Planning artifact missing or unsafe')
    return path.read_bytes()


def verify(root, plan, mode, script, origin=None, *, canonical=None, attempt=None):
    raw = read_artifact(root, 'SEMANTIC_CHECKPOINT.json')
    checkpoint = json.loads(raw)
    if checkpoint.get('policy') != POLICY:
        raise ValueError('Unknown vNext frozen contract; no downgrade')
    scope = checkpoint['scope']
    validate_transport(checkpoint.get('schema'), scope, frozen=True)
    if not admission_enabled(scope) and ('admissions' in checkpoint or
            (Path(root) / 'planning/SEMANTIC_A_SELECTION_NORMALIZED.json').exists()):
        raise ValueError('Selection admission policy was removed or downgraded')
    if admission_enabled(scope) and set(checkpoint.get('admissions', {})) != {'A-selection'}:
        raise ValueError('Frozen selection admission coverage changed')
    uses_view = checkpoint['schema'] == VIEW_CHECKPOINT
    uses_staged = checkpoint['schema'] in {VIEW_CHECKPOINT, STAGED_CHECKPOINT}
    uses_source = checkpoint['schema'] in {VIEW_CHECKPOINT, STAGED_CHECKPOINT, CHECKPOINT}
    uses_atomic = checkpoint['schema'] in {VIEW_CHECKPOINT, STAGED_CHECKPOINT, CHECKPOINT, FRAME_CHECKPOINT}
    uses_wire = checkpoint['schema'] in {VIEW_CHECKPOINT, STAGED_CHECKPOINT, CHECKPOINT, FRAME_CHECKPOINT, WIRE_CHECKPOINT}
    uses_support = checkpoint['schema'] in {VIEW_CHECKPOINT, STAGED_CHECKPOINT, CHECKPOINT, FRAME_CHECKPOINT, WIRE_CHECKPOINT, SUPPORTED_CHECKPOINT}
    actual = canonical if canonical is not None else {name: read_artifact(root, name).decode()
                                                    for name in ('SCRIPT.md', 'SCENES.md', 'TREATMENT.md')}
    identities = origin or {'creation_id': plan.creation_id, 'attempt_id': plan.attempt_id, 'plan_id': plan.plan_id}
    if (attempt is None or Path(attempt['workspace']['path']).resolve() != Path(root).resolve()
            or attempt['creation_id'] != plan.creation_id or attempt['attempt_id'] != plan.attempt_id
            or scope['policy'] != POLICY or scope['creation_id'] != identities['creation_id']
            or scope['attempt_id'] != identities['attempt_id'] or scope['mode'] != mode
            or scope['context_refs'] != plan.context_refs or actual != scope['canonical']
            or actual['SCRIPT.md'] != script):
        raise ValueError('vNext actual Attempt, identity or frozen context changed')
    inputs = authority.load_inputs(attempt, actual, {'context_refs': scope['context_refs']}, mode,
                                   allow_missing_canonical=origin is not None)
    catalog = source_catalog(actual, {'creator_context': inputs['creator_context'], 'proposal': inputs.get('proposal')})
    if inputs != scope['inputs'] or catalog != scope['catalog']:
        raise ValueError('vNext source binding cannot be reconstructed from frozen originals')
    view = input_views.PlanningInputView(inputs, catalog) if uses_view else None
    if view is not None and read_artifact(root, 'SEMANTIC_INPUT_VIEW.json') != review.compact(view.snapshot()).encode():
        raise ValueError('Frozen input view snapshot differs from source reconstruction')
    a_artifact = 'SEMANTIC_A_ASSEMBLY.json' if uses_staged else 'SEMANTIC_A_RESULT.json'
    a_raw = read_artifact(root, a_artifact, MAX_RESULT_BYTES)
    initial = json.loads(a_raw)
    if (initial != checkpoint['initial'] or (authority.digest(initial) if uses_staged else hashlib.sha256(a_raw).hexdigest())
            != checkpoint['assembled_a_sha256' if uses_staged else 'raw_a_sha256']):
        raise ValueError('vNext original captured A changed')
    used_bindings = set()
    def candidate(key, original, schema, *, strict=False):
        if not uses_wire:
            return original
        projection = wire.project(schema, key, atomic_framing=uses_atomic)
        if checkpoint.get('schema_bindings', {}).get(key) != projection.identity:
            raise ValueError('Frozen Planning stage wire identity changed')
        used_bindings.add(key)
        raw = (read_artifact(root, 'SEMANTIC_A_RESULT.json', MAX_RESULT_BYTES).decode()
               if key == 'A' else checkpoint.get('wire_originals', {}).get(key))
        if uses_staged and key in {'A-selection', 'A-details'}:
            name = 'SEMANTIC_A_SELECTION.json' if key == 'A-selection' else 'SEMANTIC_A_DETAILS.json'
            if read_artifact(root, name, MAX_RESULT_BYTES).decode() != raw:
                raise ValueError('Frozen staged original changed')
        if (not isinstance(raw, str) or json.loads(raw) != original
                or hashlib.sha256(raw.encode()).hexdigest() != checkpoint['capture'][key]['reply_sha256']):
            raise ValueError('Frozen wire original or capture hash changed')
        errors = projection.errors(original)
        diagnostic = {'wire_errors': errors, 'original_sha256': hashlib.sha256(raw.encode()).hexdigest()}
        if checkpoint.get('wire_diagnostics', {}).get(key) != diagnostic:
            raise ValueError('Frozen wire diagnostic changed')
        if strict and errors:
            raise ValueError('Frozen complete wire schema rejected')
        return projection.decode_valid(original) if strict else projection.decode_candidate(original)
    def patch_output(lineage, targets, batch=None):
        canonical_schema = review.patch_schema(targets, support_batch=batch, slots=True)
        value = candidate('repair', lineage['output'], canonical_schema, strict=True) if uses_wire else lineage['output']
        return review.decode_patch_slots(value, targets, support_batch=batch) if uses_support else value
    if uses_staged:
        codec = staged.StagedProposal(query_schema(scope))
        selection_schema = intake_selection(scope, view.codec.schema if view is not None else codec.selection_schema)
        a_message_for = (lambda stage, **kw: view_a_message(scope, view, stage, **kw)) if view is not None else (lambda stage, **kw: staged_a_message(scope, stage, **kw))
        selected = candidate('A-selection', json.loads(checkpoint['wire_originals']['A-selection']), selection_schema)
        selected_receipt = None
        if admission_enabled(scope):
            original_call = {**checkpoint['capture']['A-selection'],
                             'reply': checkpoint['wire_originals']['A-selection']}
            admitted = selection_admission(scope, original_call, selection_schema,
                                           checkpoint['schema_bindings']['A-selection'])
            if checkpoint['admissions']['A-selection'] != admitted:
                raise ValueError('Frozen selection admission cannot be rebuilt from the original capture')
            selected = require_selection_admission(admitted)
            if read_artifact(root, 'SEMANTIC_A_SELECTION_NORMALIZED.json', MAX_RESULT_BYTES) != admission.canonical_json(selected).encode():
                raise ValueError('Frozen normalized selection differs from original replay')
            selected_receipt = admitted['receipt']
        if view is not None:
            selected = view.codec.decode(selected, view.codec.identity, diagnostic=True)
        contract = codec.details_contract(selected, diagnostic=True)
        binding = detail_binding(scope, selected, checkpoint['capture']['A-selection']['reply_sha256'], contract, view,
                                 admission_receipt=selected_receipt)
        if checkpoint.get('detail_binding') != binding:
            raise ValueError('Frozen details identity changed')
        for key, message in (
                ('A-selection', a_message_for('A-selection')),
                ('A-details', a_message_for('A-details', selection=selected, binding=binding))):
            recorded = checkpoint['capture'][key]
            if (recorded['request_sha256'] != hashlib.sha256(message.encode()).hexdigest()
                    or recorded['session'] != f"semantic-{scope['attempt_id']}-vnext-{key}"):
                raise ValueError('Frozen staged request cannot be reconstructed')
        details = candidate('A-details', json.loads(checkpoint['wire_originals']['A-details']), contract['schema'])
        value = codec.assemble_candidate(selected, details, contract['identity'])
        if value != initial:
            raise ValueError('Frozen assembly cannot be derived from both original captures')
        invalid_a_wire = any(checkpoint['wire_diagnostics'][key]['wire_errors'] for key in ('A-selection', 'A-details'))
    else:
        value = candidate('A', initial, query_schema(scope, compiled=uses_atomic)) if uses_wire else initial
        invalid_a_wire = uses_wire and checkpoint['wire_diagnostics']['A']['wire_errors']
    if correction.enabled(scope):
        def replay_invoke(key, message, schema):
            recorded = checkpoint['capture'].get(key, {})
            if (recorded.get('request_sha256') != hashlib.sha256(message.encode()).hexdigest()
                    or recorded.get('session') != f"semantic-{scope['attempt_id']}-vnext-{key}"):
                raise ValueError('Frozen candidate review request cannot be reconstructed')
            raw_reply = checkpoint.get('wire_originals', {}).get(key)
            if not isinstance(raw_reply, str):
                raise ValueError('Frozen candidate reply missing')
            return staged.StagedProposal.parse_raw(raw_reply)
        def replay_repair(stage, original, targets, context=None):
            schema = correction.patch_schema(targets, support_batch=context, slots=True)
            output = replay_invoke('repair', repair_message(scope, original, targets, context), schema)
            decoded = candidate('repair', output, schema, strict=True)
            patches = correction.decode_patch_slots(decoded, targets, support_batch=context)
            return correction.apply_patches(original, patches, targets, support_batch=context), output
        replayed = correction.evaluate(initial, scope, view, replay_invoke, candidate, replay_repair,
                                       max_calls=MAX_PLANNING_CALLS)
        for key in ('initial_review_value', 'initial_responses', 'before_semantic', 'repair'):
            if checkpoint.get(key) != replayed[key]:
                raise ValueError('Frozen candidate correction evidence changed: ' + key)
        if checkpoint.get('candidate_correction') != replayed['trace']:
            raise ValueError('Frozen candidate reports or correction lineage changed')
        proposal, directory = replayed['proposal'], replayed['directory']
        responses = replayed['responses']
        if checkpoint['responses'] != [r.model_dump(mode='json') for r in responses]:
            raise ValueError('Frozen candidate final answers changed')
        if (used_bindings != set(checkpoint['capture'])
                or used_bindings != set(checkpoint.get('schema_bindings', {}))
                or used_bindings != set(checkpoint.get('wire_diagnostics', {}))
                or used_bindings != set(checkpoint.get('wire_originals', {}))):
            raise ValueError('Frozen candidate stage coverage changed')
    else:
        if 'candidate_correction' in checkpoint:
            raise ValueError('Candidate correction policy was removed or downgraded')
        lineage = checkpoint['repair']
        if lineage and lineage['stage'] == 'A':
            targets = intake_targets(scope, value)
            if descriptors(targets) != lineage['targets']: raise ValueError('A repair scope changed')
            patches = patch_output(lineage, targets)
            value = review.apply_patches(value, patches, targets)
        elif invalid_a_wire:
            raise ValueError('Invalid A wire was not locally repaired')
        if intake_enabled(scope) and intake_targets(scope, value):
            raise ValueError('Frozen confirmed intake is incomplete')
        proposal = parse_proposal(value, catalog)
        if uses_wire:
            validate_canonical(catalog, value, compiled=uses_atomic)
        value = proposal.model_dump(mode='json')
        if value != checkpoint['initial_review_value']: raise ValueError('Accepted initial semantics changed')
        directory = review.questions(proposal, inputs, catalog, supported=uses_support, source_bound=uses_source)
        if view is not None: view.check_review(directory)
        batches = review.review_batches(directory)
        originals = checkpoint['initial_responses']
        if len(originals) != len(batches): raise ValueError('Initial review coverage incomplete')
        responses = []
        for index, (response, batch) in enumerate(zip(originals, batches, strict=True)):
            if uses_wire:
                response = candidate(f'B-{index:03}', response, batch['response_schema'])
            if uses_support:
                response = support.decode_slots(response, batch)
            if lineage and lineage['stage'] == f'B-{index:03}':
                targets = review.answer_targets(response, batch)
                if descriptors(targets) != lineage['targets']: raise ValueError('B repair scope changed')
                patches = patch_output(lineage, targets, batch if uses_support else None)
                response = review.apply_patches(response, patches, targets, support_batch=batch if uses_support else None)
            elif uses_wire and checkpoint['wire_diagnostics'][f'B-{index:03}']['wire_errors']:
                raise ValueError('Invalid B wire was not locally repaired')
            responses.append(review.validate_answers(response, batch))
        if [r.model_dump(mode='json') for r in responses] != checkpoint['before_semantic']:
            raise ValueError('Initial accepted review answers changed')
        targets = review.semantic_targets(directory, responses)
        if lineage and lineage['stage'] == 'semantic':
            if descriptors(targets) != lineage['targets']: raise ValueError('Semantic repair scope changed')
            patches = patch_output(lineage, targets)
            value = review.apply_patches(value, patches, targets)
            proposal = parse_proposal(value, catalog)
            if uses_wire:
                validate_canonical(catalog, value, compiled=uses_atomic)
        elif targets:
            raise ValueError('Challenged semantics cannot be frozen without a reviewed repair')
        updated = review.questions(proposal, inputs, catalog, supported=uses_support, source_bound=uses_source)
        if view is not None: view.check_review(updated)
        kept, pending = review.recheck(directory, responses, updated)
        if uses_wire and lineage and lineage['stage'] == 'semantic':
            for index, batch in enumerate(review.review_batches(pending)):
                key = f'B-recheck-{index:03}'
                original = json.loads(checkpoint['wire_originals'][key])
                decoded = candidate(key, original, batch['response_schema'], strict=True)
                for answer in review.validate_answers(support.decode_slots(decoded, batch), batch).answers:
                    kept[answer.question] = answer.model_dump(mode='json')
        directory = updated
        batches = review.review_batches(directory)
        if len(checkpoint['responses']) != len(batches): raise ValueError('Final review coverage incomplete')
        responses = [review.validate_answers(r, b) for r, b in zip(checkpoint['responses'], batches, strict=True)]
        final_by_id = {a.question: a.model_dump(mode='json') for r in responses for a in r.answers}
        if any(final_by_id.get(index) != answer for index, answer in kept.items()):
            raise ValueError('Previously accepted unchanged semantic review was overwritten')
        if uses_wire and (used_bindings != set(checkpoint['capture'])
                or used_bindings != set(checkpoint.get('schema_bindings', {}))
                or used_bindings != set(checkpoint.get('wire_diagnostics', {}))
                or used_bindings - {'A'} != set(checkpoint.get('wire_originals', {}))):
            raise ValueError('Frozen wire stage coverage changed')
        if review.semantic_targets(directory, responses): raise ValueError('Final review not accepted')
        if not lineage or lineage['stage'] != 'semantic':
            if checkpoint['responses'] != checkpoint['before_semantic']: raise ValueError('Accepted review overwritten')
    effective = review.compact(proposal.model_dump(mode='json')).encode()
    if (checkpoint['proposal'] != proposal.model_dump(mode='json') or read_artifact(root, 'SEMANTIC_PLAN.json') != effective
            or hashlib.sha256(effective).hexdigest() != checkpoint['draft_sha256']
            or checkpoint['review_sha256'] != authority.digest(directory)):
        raise ValueError('vNext candidate or review identity changed')
    projected, requirements, proof = project_proposal(proposal, inputs=inputs, catalog=catalog,
        creation_id=scope['creation_id'], attempt_id=scope['attempt_id'], refs=scope['context_refs'], mode=mode,
        transport=scope.get('transport'))
    if (projected.plan_id != identities['plan_id'] or projected.model_dump(mode='json') != checkpoint['plan']
            or projected.model_copy(update={k: getattr(plan, k) for k in ('creation_id', 'attempt_id', 'plan_id')}) != plan
            or proof != checkpoint['proof'] or json.loads(read_artifact(root, 'MATERIAL_REQUIREMENTS.json')) != requirements):
        raise ValueError('Formal contract cannot be derived from accepted vNext semantics')
    return {'path': 'planning/SEMANTIC_CHECKPOINT.json', 'sha256': hashlib.sha256(raw).hexdigest(),
            'draft_sha256': checkpoint['draft_sha256'], 'policy': POLICY,
            **({'raw_artifacts': ['SEMANTIC_A_SELECTION.json', 'SEMANTIC_A_DETAILS.json',
                                 'SEMANTIC_A_ASSEMBLY.json', *(['SEMANTIC_INPUT_VIEW.json'] if uses_view else []),
                                  *(['SEMANTIC_A_SELECTION_NORMALIZED.json'] if admission_enabled(scope) else [])]} if uses_staged else {}),
            **({'origin': origin} if origin else {})}
