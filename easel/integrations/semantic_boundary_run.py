"""vNext policy in the existing Planning request/recovery and publish boundary."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from copy import deepcopy

from easel import output_admission as admission
from easel.integrations import planning_stage_recovery as stage_loop
from easel.creation_delivery import DeliveryExecutionUncertain

from easel.integrations import planning_authority as authority
from easel.integrations import planning_semantic_review as review
from easel.integrations import planning_candidate_review as correction
from easel.integrations import planning_creative_authority as creative
from easel.integrations import planning_d2_typed_review as d2
from easel.integrations.planning_capture import capture
from easel.integrations.planning_result_contract import MAX_RESULT_BYTES, semantic_tool_schema, FLEXIBLE_QUERY_POLICY
from easel.integrations import planning_structured as structured
from easel.integrations import planning_review_support as support
from easel.integrations import planning_wire as wire
from easel.integrations import planning_repair_evidence as repair_evidence
from easel.integrations import planning_staged_proposal as staged
from easel.integrations import planning_input_view as input_views
from easel.integrations import planning_request_view as request_view
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
VIEW_CHECKPOINT = 'semantic-planning-frozen@22'
VIEW_JOURNAL = 'semantic-planning-checkpoint@22'
MAX_SHARED_REPAIRS = 3
MAX_CHECKPOINT_BYTES = 32 * MAX_RESULT_BYTES
# A technical bound, never authorization to spend. The real evaluator's
# shared submission/time/subscription ledger remains independently binding.
MAX_PLANNING_CALLS = 72


def transport_identity(catalog, *, intake_inputs=None, intake_policy=None):
    if intake_inputs is not None and intake_policy is None:
        intake_policy = review.INTAKE_POLICY
    canonical = semantic_tool_schema(catalog, compiled=True,
        flexible_queries=intake_policy in {review.FLEXIBLE_INTAKE_POLICY, review.BOUNDED_BATCH_INTAKE_POLICY, review.FRAMING_INTAKE_POLICY, review.QUOTE_INTAKE_POLICY, review.ATOMIC_DETAILS_INTAKE_POLICY, review.SOUND_TEMPO_INTAKE_POLICY, review.COMPLETE_GUIDANCE_INTAKE_POLICY, review.ROOT_ECHO_INTAKE_POLICY, review.SFX_GUIDANCE_INTAKE_POLICY, review.SCHEMA_SHAPE_INTAKE_POLICY})
    projection = wire.project(canonical, 'A', atomic_framing=True)
    request = structured.request_for(projection.schema)
    selection = input_views.SourceSelection(canonical, catalog).schema
    if intake_inputs is not None:
        intake_policy = review.INTAKE_POLICY if intake_policy is None else intake_policy
        if intake_policy not in review.INTAKE_POLICIES:
            raise ValueError('Unknown confirmed Planning intake policy')
        selection = review.intake_selection_schema(selection, intake_inputs)
    elif intake_policy is not None:
        raise ValueError('An intake policy requires its frozen inputs')
    return {'policy': structured.VERSION, 'reply_contract': structured.CONTRACT,
            'context_policy': structured.CONTEXT_POLICY,
            **({'intake_policy': intake_policy} if intake_inputs is not None else {}),
            **({'output_admission': admission.policy_identity(admission.SELECTION_PROFILE
                if intake_policy in {review.ROOT_ECHO_INTAKE_POLICY, review.SFX_GUIDANCE_INTAKE_POLICY, review.SCHEMA_SHAPE_INTAKE_POLICY} else admission.LEGACY_SELECTION_PROFILE)}
               if intake_policy in {review.ADMISSION_INTAKE_POLICY, review.FLEXIBLE_INTAKE_POLICY, review.BOUNDED_BATCH_INTAKE_POLICY, review.FRAMING_INTAKE_POLICY, review.QUOTE_INTAKE_POLICY, review.ATOMIC_DETAILS_INTAKE_POLICY, review.SOUND_TEMPO_INTAKE_POLICY, review.COMPLETE_GUIDANCE_INTAKE_POLICY, review.ROOT_ECHO_INTAKE_POLICY, review.SFX_GUIDANCE_INTAKE_POLICY, review.SCHEMA_SHAPE_INTAKE_POLICY} else {}),
            **({'query_cardinality_policy': FLEXIBLE_QUERY_POLICY}
               if intake_policy in {review.FLEXIBLE_INTAKE_POLICY, review.BOUNDED_BATCH_INTAKE_POLICY, review.FRAMING_INTAKE_POLICY, review.QUOTE_INTAKE_POLICY, review.ATOMIC_DETAILS_INTAKE_POLICY, review.SOUND_TEMPO_INTAKE_POLICY, review.COMPLETE_GUIDANCE_INTAKE_POLICY, review.ROOT_ECHO_INTAKE_POLICY, review.SFX_GUIDANCE_INTAKE_POLICY, review.SCHEMA_SHAPE_INTAKE_POLICY} else {}),
            **({'candidate_batch_policy': {'id': review.CURRENT_CANDIDATE_BATCH_POLICY if intake_policy == review.INTAKE_POLICY else review.CANDIDATE_BATCH_POLICY,
                                          'max_questions': review.CURRENT_CANDIDATE_BATCH_LIMIT if intake_policy == review.INTAKE_POLICY else review.CANDIDATE_BATCH_LIMIT}}
               if intake_policy in {review.BOUNDED_BATCH_INTAKE_POLICY, review.FRAMING_INTAKE_POLICY, review.QUOTE_INTAKE_POLICY, review.ATOMIC_DETAILS_INTAKE_POLICY, review.SOUND_TEMPO_INTAKE_POLICY, review.COMPLETE_GUIDANCE_INTAKE_POLICY, review.ROOT_ECHO_INTAKE_POLICY, review.SFX_GUIDANCE_INTAKE_POLICY, review.SCHEMA_SHAPE_INTAKE_POLICY} else {}),
            **({'framing_guidance_policy': review.FRAMING_GUIDANCE_POLICY}
               if intake_policy in {review.FRAMING_INTAKE_POLICY, review.QUOTE_INTAKE_POLICY, review.ATOMIC_DETAILS_INTAKE_POLICY, review.SOUND_TEMPO_INTAKE_POLICY, review.COMPLETE_GUIDANCE_INTAKE_POLICY, review.ROOT_ECHO_INTAKE_POLICY, review.SFX_GUIDANCE_INTAKE_POLICY, review.SCHEMA_SHAPE_INTAKE_POLICY} else {}),
            **({'b_quote_guidance_policy': review.B_QUOTE_GUIDANCE_POLICY}
               if intake_policy in {review.QUOTE_INTAKE_POLICY, review.ATOMIC_DETAILS_INTAKE_POLICY, review.SOUND_TEMPO_INTAKE_POLICY, review.COMPLETE_GUIDANCE_INTAKE_POLICY, review.ROOT_ECHO_INTAKE_POLICY, review.SFX_GUIDANCE_INTAKE_POLICY, review.SCHEMA_SHAPE_INTAKE_POLICY} else {}),
            **({'atomic_detail_guidance_policy': review.ATOMIC_DETAIL_GUIDANCE_POLICY}
               if intake_policy in {review.ATOMIC_DETAILS_INTAKE_POLICY, review.SOUND_TEMPO_INTAKE_POLICY, review.COMPLETE_GUIDANCE_INTAKE_POLICY, review.ROOT_ECHO_INTAKE_POLICY, review.SFX_GUIDANCE_INTAKE_POLICY, review.SCHEMA_SHAPE_INTAKE_POLICY} else {}),
            **({'sound_tempo_guidance_policy': review.SOUND_TEMPO_GUIDANCE_POLICY}
               if intake_policy in {review.SOUND_TEMPO_INTAKE_POLICY, review.COMPLETE_GUIDANCE_INTAKE_POLICY, review.ROOT_ECHO_INTAKE_POLICY, review.SFX_GUIDANCE_INTAKE_POLICY, review.SCHEMA_SHAPE_INTAKE_POLICY} else {}),
            **({'sfx_guidance_policy': review.SFX_GUIDANCE_POLICY}
               if intake_policy in {review.SFX_GUIDANCE_INTAKE_POLICY, review.SCHEMA_SHAPE_INTAKE_POLICY} else {}),
            **({'schema_shape_guidance_policy': review.SCHEMA_SHAPE_GUIDANCE_POLICY}
               if intake_policy == review.SCHEMA_SHAPE_INTAKE_POLICY else {}),
            'schema_sha256': request['schemaSha256'],
            'producer': {'policy': staged.POLICY, 'selection_schema_sha256':
                structured.request_for(selection)['schemaSha256']},
            'input_view_policy': input_views.PlanningInputView.POLICY,
            'source_selection_policy': input_views.SourceSelection.POLICY,
            'detail_batch_policy': staged.MODALITY_FAMILY_BATCH_POLICY if intake_policy == review.INTAKE_POLICY else staged.DETAIL_BATCH_POLICY,
            **({'details_recovery_policy': admission.DETAILS_RECOVERY_POLICY,
                'shared_repair_limit': MAX_SHARED_REPAIRS,
                 'stage_regeneration_policy': stage_loop.POLICY,
                 'max_regenerations_per_details_batch': stage_loop.MAX_STAGE_REGENERATIONS}
               if intake_policy == review.INTAKE_POLICY else {}),
            **({'request_view_policy': request_view.POLICY, 'planning_call_limit': MAX_PLANNING_CALLS,
                 'b_root_title_policy': structured.B_ROOT_TITLE_POLICY,
                 'b_batch_repair_policy': correction.B_BATCH_REPAIR_POLICY}
                if intake_policy == review.INTAKE_POLICY else {}),
            'review_source_policy': review.SOURCE_POLICY,
            'runtime_sha256': authority.digest(structured.RUNTIME_PARTS),
            'support_policy': support.REVISION,
            'wire': projection.identity}


def validate_transport(version, scope, *, frozen=False):
    if version != (VIEW_CHECKPOINT if frozen else VIEW_JOURNAL):
        raise ValueError('Historical Planning protocol is read-only; no recovery dispatch')
    intake = intake_enabled(scope)
    if (scope.get('transport') != transport_identity(scope['catalog'],
            intake_inputs=scope['inputs'] if intake else None,
            intake_policy=scope.get('transport', {}).get('intake_policy'))
            or scope.get('input_view') != input_views.PlanningInputView(scope['inputs'], scope['catalog']).identity):
        raise ValueError('Planning input view transport identity changed')
    return True


def intake_enabled(scope):
    policy = scope.get('transport', {}).get('intake_policy')
    if policy is not None and policy not in review.INTAKE_POLICIES:
        raise ValueError('Unknown confirmed Planning intake policy')
    return policy is not None


def intake_selection(scope, schema):
    return review.intake_selection_schema(schema, scope['inputs']) if intake_enabled(scope) else schema


def admission_enabled(scope):
    return scope.get('transport', {}).get('intake_policy') in {review.ADMISSION_INTAKE_POLICY, review.FLEXIBLE_INTAKE_POLICY, review.BOUNDED_BATCH_INTAKE_POLICY, review.FRAMING_INTAKE_POLICY, review.QUOTE_INTAKE_POLICY, review.ATOMIC_DETAILS_INTAKE_POLICY, review.SOUND_TEMPO_INTAKE_POLICY, review.COMPLETE_GUIDANCE_INTAKE_POLICY, review.ROOT_ECHO_INTAKE_POLICY, review.SFX_GUIDANCE_INTAKE_POLICY, review.SCHEMA_SHAPE_INTAKE_POLICY}


def flexible_queries(scope):
    return scope.get('transport', {}).get('intake_policy') in {review.FLEXIBLE_INTAKE_POLICY, review.BOUNDED_BATCH_INTAKE_POLICY, review.FRAMING_INTAKE_POLICY, review.QUOTE_INTAKE_POLICY, review.ATOMIC_DETAILS_INTAKE_POLICY, review.SOUND_TEMPO_INTAKE_POLICY, review.COMPLETE_GUIDANCE_INTAKE_POLICY, review.ROOT_ECHO_INTAKE_POLICY, review.SFX_GUIDANCE_INTAKE_POLICY, review.SCHEMA_SHAPE_INTAKE_POLICY}


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
    profile = scope['transport']['output_admission']['profile']
    result = admission.admit_json(raw, schema, stage='A-selection', channel='tool',
        binding=binding, profile=profile, max_bytes=MAX_RESULT_BYTES)
    receipt, value = result['receipt'], result['candidate']
    if profile == admission.SELECTION_PROFILE:
        # ADR-005: Owner eligibility cannot overwrite the pure admission receipt.
        result['owner_eligibility'] = selection_eligibility(scope, result)
    else:
        # Historical combined receipt, read-only reconstruction.
        receipt['decision'] = selection_decision(scope, receipt, value)
    return result


def selection_decision(scope, receipt, value):
    decision = deepcopy(receipt['decision'])
    # Preserve the pre-existing route for shape-safe candidate leaf faults and
    # missing BGM. Eligibility does not spend or enlarge the shared allowance.
    if value is not None and receipt['remaining_errors']['total']:
        try:
            view = input_views.PlanningInputView(scope['inputs'], scope['catalog'])
            view.codec.validate_source_choices(value)
            decoded = view.codec.decode(value, view.codec.identity, diagnostic=True)
            staged._read_only_staged(query_schema(scope)).details_contract(
                decoded, diagnostic=True)
        except (ValueError, TypeError, KeyError):
            decision['code'] = 'SELECTION_SHAPE_OR_REFERENCE_INVALID'
        else:
            decision.update(outcome='BOUNDED_REPAIR', code='EXISTING_CANDIDATE_REPAIR_REQUIRED')
    return decision


def selection_eligibility(scope, result):
    receipt, value = result['receipt'], result['candidate']
    return {'policy': 'planning-selection-eligibility@1',
        'decision': selection_decision(scope, receipt, value),
        'receipt_sha256': authority.digest(receipt),
        'candidate_sha256': authority.digest(value), 'scope_sha256': authority.digest(scope)}


def require_selection_admission(result, *, scope=None):
    decision = result['receipt']['decision']
    if scope is not None and result['receipt']['policy'] != scope['transport']['output_admission']:
        raise ValueError('Planning selection admission profile changed')
    if result['receipt']['policy']['profile'] == admission.SELECTION_PROFILE:
        eligibility = result.get('owner_eligibility') or {}
        if scope is None or eligibility != selection_eligibility(scope, result):
            raise ValueError('Planning selection eligibility binding changed')
        decision = eligibility['decision']
    if decision['outcome'] == 'REJECT':
        raise ValueError('Planning selection admission rejected: ' + decision['code'])
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
    validate_transport(state.get('schema'), state['scope'])
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
    """The only new executor policy is the vNext identity.

    Older journal bytes are immutable evidence, not a resumed business route.
    """
    if default != POLICY:
        raise ValueError('旧 Planning 策略不可用于新生产')
    store = AttemptMaterialStore(attempt['workspace']['path'])
    if store.read_recovery_record('semantic-planning-v3') is not None:
        raise ValueError('历史 Planning journal 只读，不以新版继续派发')
    state = store.read_recovery_record(STATE_KEY)
    if state is not None:
        if state.get('scope', {}).get('policy') != POLICY:
            raise ValueError('Planning 冻结策略变化，不降级恢复')
        validate_transport(state.get('schema'), state['scope'])
    return POLICY





def descriptors(targets):
    return [{k: v for k, v in target.items() if k != 'annotation'} for target in targets]




def view_a_message(scope, view, stage, *, selection=None, binding=None, detail_batch=None):
    expanded_audio = scope.get('transport', {}).get('intake_policy') in {review.AUDIO_INTAKE_POLICY, review.P3_INTAKE_POLICY, review.RELATIONAL_INTAKE_POLICY, review.ADMISSION_INTAKE_POLICY, review.FLEXIBLE_INTAKE_POLICY, review.BOUNDED_BATCH_INTAKE_POLICY, review.FRAMING_INTAKE_POLICY, review.QUOTE_INTAKE_POLICY, review.ATOMIC_DETAILS_INTAKE_POLICY, review.SOUND_TEMPO_INTAKE_POLICY, review.COMPLETE_GUIDANCE_INTAKE_POLICY, review.ROOT_ECHO_INTAKE_POLICY, review.SFX_GUIDANCE_INTAKE_POLICY, review.SCHEMA_SHAPE_INTAKE_POLICY}
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
    if scope.get('creative_authority') is not None:
        # A chooses creative meaning; Program owns Need source identity,
        # necessity binding and exact continuity hashes. B reviews authority.
        context['visual_claim_reference_contract'] = {
            'policy': creative.SOURCE_BRIDGE_POLICY,
            'need_scope': '具体Need的已确认场景/事件位置；原SourceSelection只读、不得伪造',
            'creative_goal_ref': '独立的冻结创作依据src引用；可以是全文global或适用的其他合法范围，不必与Need.scope相同',
            'model_writes': ['claimed_kind', 'creative_goal_ref', 'reason'],
            'program_binds': ['need_source_ref', 'claimed_necessity', 'continuity_choices_sha256'],
            'review': 'Claim是待审主张，不因为引用合法就被证明为Mode/Creator已确认；B分别核实来源支持、委托、必要性与消费责任',
        }
    if admission_enabled(scope):
        context['output_admission'] = scope['transport']['output_admission']
    if correction.enabled(scope):
        context['candidate_review_policy'] = correction.policy_for(scope)
    if expanded_audio:
        context['scope_reference_contract'] = {
            'policy': view.codec.POLICY,
            'global_scope': view.codec.to_wire['global'],
            'usage_scope_is_evidence': False,
            'allowed_scope': {modality: {'handles': handles,
                'kinds': sorted({view.codec.references[h]['kind'] for h in handles})}
                for modality, handles in view.codec.allowed_scopes.items()},
            'instruction': 'scope绑定冻结文本位置和来源种类，不是素材使用点位或镜头编号。'
                '逐模态只从allowed_scope的handles中选择；原文行choices给出这些句柄。'
                'SFX只能选其允许的event引用，同文scene与event不是可互换身份；'
                '其他模态按各自允许集合选择，不增添范围限制。'
                '时序及镜头对齐另由后期处理；语义支持仍核对完整冻结内容，不由kind自动通过。'
                '不得按镜头数字拼造引用，也不得自动改写已选择的来源。'}
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
                       'scope只选择该modality在工具Schema中允许的冻结来源src引用，'
                       '它是文本位置和来源种类，不是素材使用点位或镜头编号。')
    elif stage == 'A-details':
        opaque = view.opaque_headers(selection)
        context.update(candidate_slots={f'slot_{i:03}': need for i, need in enumerate(opaque['needs'])},
                       selection_unresolved=opaque['unresolved'], detail_binding=binding)
        if detail_batch is not None:
            context['all_candidate_slots'] = context['candidate_slots']
            context['candidate_slots'] = {key: context['all_candidate_slots'][key]
                                          for key in detail_batch['slots']}
            context['detail_batch'] = {key: detail_batch[key] for key in ('key', 'slots')}
        instruction = ('为每个固定slot填写完整条件、用途与相应模态详情；不能改header或增删slot。'
                       'required/preference及素材/后期/叙事责任由完整语义决定；源画幅/时长不继承成片规格。')
        if detail_batch is not None:
            instruction += ('本次只填写candidate_slots中的完整素材；all_candidate_slots和完整冻结输入保留全局上下文。'
                '不得输出其他批次slot。selection_unresolved原件由程序保留，本批unresolved记录新遇到的未决问题；'
                '不能忽略跨素材冲突。所有批次报告按固定序保留，程序不会去重、删除或解释。')
            if scope.get('creative_authority') is not None:
                family = ('visual' if all(selection['needs'][int(slot.removeprefix('slot_'))]['modality'] in {'image', 'video'}
                           for slot in detail_batch['slots']) else 'audio')
                if family == 'audio' and any(selection['needs'][int(slot.removeprefix('slot_'))]['modality'] in {'image', 'video'}
                                              for slot in detail_batch['slots']):
                    raise ValueError('A-details mixed visual and audio family is not admissible')
                context['detail_modality_family'] = family
                instruction += (('本次仅包含视觉 image/video 的槽位，每条视觉 Condition 必须按闭合Schema提交 claim。'
                                 if family == 'visual' else
                                 '本次仅包含非视觉音频 BGM/SFX 的槽位，所有 Condition 严禁包含 claim、Director Claim 或其他额外字段；'
                                 '只填写对应音频条件的 text/strength/responsibility/meaning，完全遵守闭合工具Schema。'))
    else:
        raise ValueError('Unknown input-view Planning stage')
    if correction.policy_for(scope) == correction.RELATIONAL_POLICY and stage == 'A-selection':
        instruction = ('你负责提出语义素材Need，不是等待程序自动生成候选。先完整承接冻结画面的image/video需求，'
                       '再列独立配乐/音效；仅已确认的程序旁白不重复提出。素材文件尚未检索不等于Need可以省略。' + instruction)
    if scope.get('creative_authority') is not None:
        if stage == 'A-selection':
            instruction += ('只有image/video允许header_claim；bgm/sfx不得填写header_claim，空对象或null也不得提交。'
                '视觉header_claim只填写Schema的claimed_kind、creative_goal_ref、reason。'
                'Need.scope定位具体应被承接的冻结场景/事件；creative_goal_ref是你援引的创作依据，'
                '两者角色不同，可以引用合法全文global。不得将来源引用当成已证实的Director规则。'
                '不要计算SHA、回填claimed_necessity或伪造任何程序身份；程序从所选Need冻结必要性与连续性摘要。')
        else:
            instruction += ('视觉Condition claim中的creative_goal_ref是待审创作依据，不是Need来源身份；'
                '必须从候选槽位/冻结输入的src_*句柄中选择；不要输出内部event-*/global名称、'
                '编造引用或替程序换掉Need.scope。独立B将审核引用的真实支持性和Hard消费者。')
    if scope.get('transport', {}).get('intake_policy') in {review.FRAMING_INTAKE_POLICY, review.QUOTE_INTAKE_POLICY, review.ATOMIC_DETAILS_INTAKE_POLICY, review.SOUND_TEMPO_INTAKE_POLICY, review.COMPLETE_GUIDANCE_INTAKE_POLICY, review.ROOT_ECHO_INTAKE_POLICY, review.SFX_GUIDANCE_INTAKE_POLICY, review.SCHEMA_SHAPE_INTAKE_POLICY}:
        # @8 and @9 A requests share exact guidance; existing frozen digests stay unchanged.
        if stage == 'A-selection':
            instruction += (
                '只为实际外部音画源建立Need；静默、淡出、拉远、字幕和ducking'
                '是后期行为，不得为它们单独建立SFX/图片Need。'
                'SFX只能代表实际可听事件（敲键盘、放杯子），不能把静默当音效。'
                '静态键盘image只承接可观察的键盘/手部构图；'
                '若源素材必须出现真实按压动作应选择video，不能让image承担源运动。'
                '同一场景优先一个能完整承接义务的主视觉Need；两种可替代画面'
                '不等于两个同时required的素材Need。只有真实需要两个独立源且'
                '一份源素材不能承接时才拆开，不把没有必要的备选视频另列Need。'
                '保留全部实际冻结义务，精简重复候选不是删减需求。')
        elif stage == 'A-details':
            instruction += (
                '提交前逐slot自检：每个素材Need必须至少有1条有冻结依据的'
                'strength=required、responsibility=material、可核实源资产条件。'
                '静态image只能要求静态可观察主体与构图，'
                '不能要求required material dynamic_action。'
                'BGM的material条件必须描述真实曲目的风格、器乐或无歌词等源属性；'
                'ducking/混音/音量是postproduction。'
                'SFX的material条件必须描述实际可听声音事件，'
                '静默或剪辑淡出不属于SFX源素材。'
                '若固定slot没有合法且有来源支持的素材义务，保留未决且不得伪造源属性。'
                '每条conditions采用短而完整的独立判断，不重复header和整段分镜原文；'
                '只填写该slot工具Schema内允许的属性，不重复键，不在JSON字符串内写裸换行，'
                '不得输出API密钥、令牌或凭证样例；保持冻结语义不删义务。')
    if (scope.get('transport', {}).get('intake_policy') in {review.FRAMING_INTAKE_POLICY, review.QUOTE_INTAKE_POLICY, review.ATOMIC_DETAILS_INTAKE_POLICY, review.SOUND_TEMPO_INTAKE_POLICY, review.COMPLETE_GUIDANCE_INTAKE_POLICY, review.ROOT_ECHO_INTAKE_POLICY, review.SFX_GUIDANCE_INTAKE_POLICY, review.SCHEMA_SHAPE_INTAKE_POLICY}
            and stage == 'A-details'):
        # The previous real A tool returned {mode:match_output,ratio:9:16}
        # for all image slots. Never mutate that historical rejection; teach
        # only the next frozen request the precise existing atomic contract.
        context['source_framing_contract'] = {
            'unconstrained': {'framing': {'mode': 'unconstrained'}},
            'match_output': {'framing': {'mode': 'match_output'}},
            'native': {'mode': 'native', 'ratio_required': True, 'only_when': 'frozen source explicitly requires a native ratio'},
        }
        instruction += ('原子framing严格区分：mode=unconstrained或match_output时只提交mode键，'
            '绝不能包含ratio（即使ratio=9:16或null也不填）。只有冻结源素材确实要求原生固定画幅时'
            '才使用mode=native并填写合法ratio。成片9:16是后期输出规格，不能授权source native画幅；'
            '若源图可通过裁切匹配输出，使用{mode:match_output}但不加ratio。')
    if scope.get('transport', {}).get('intake_policy') in {review.ATOMIC_DETAILS_INTAKE_POLICY, review.COMPLETE_GUIDANCE_INTAKE_POLICY, review.ROOT_ECHO_INTAKE_POLICY, review.SFX_GUIDANCE_INTAKE_POLICY, review.SCHEMA_SHAPE_INTAKE_POLICY}:
        # @11 omitted this guidance; preserve its captured request bytes.
        # Only new @12 requests inherit both atomic and tempo guidance.
        if stage == 'A-selection':
            instruction += (
                'role只写素材候选的简短用途标签，建议少于80个汉字，严禁超过200字符。'
                '不要把整段分镜、BGM混音细则、时间轴和所有冻结上下文复制进role；'
                '完整含义仍通过冻结input_view和下一轮details承接。')
        elif stage == 'A-details':
            expected_names = sorted(context['candidate_slots'])
            context['atomic_slot_output_contract'] = {
                'exact_names': expected_names,
                'total': len(expected_names),
                'slots_root_only': 'slot_000 ... slot_NNN; no loose properties',
                'condition_properties': ['text', 'strength', 'responsibility', 'meaning'],
            }
            instruction += (
                '只向slots对象写入本批固定的' + str(len(expected_names)) + '个slot_XXX属性，'
                '名字必须与atomic_slot_output_contract.exact_names逐字匹配。'
                '严禁在slots对象顶层输出item、meaning、responsibility、purpose、sound、'
                'source_seconds等游离属性；这些必须属于各自对应slot或condition。'
                '逐个slot完整闭合conditions数组和当前slot对象后，才生成下一个slot。'
                '每条condition对象必须明确包含text、strength、responsibility、meaning。'
                '工具JSON里不得嵌入未转义的引号、原始换行或数组以外散落的condition。'
                '全部输出前按exact_names核对slots键集合：不缺失、不新增、不重复。'
                '禁止猜造新的源事实；实在无法判断则如实写入unresolved。')
    if (scope.get('transport', {}).get('intake_policy') in {review.SFX_GUIDANCE_INTAKE_POLICY, review.SCHEMA_SHAPE_INTAKE_POLICY}
            and stage == 'A-details'):
        instruction += (
            'meaning=dynamic_action与strength=required、responsibility=material的组合'
            '仅表示源video必须包含真实可见动作，image/voice/bgm/sfx均不能使用该组合。'
            'SFX的实际可听事件、音色、短促或拖尾等是音频源的可观察属性，meaning=observable；'
            '声音由动作产生不等于源视频动作义务。与画面同步、点位对齐、混音和响度安排'
            '另写responsibility=postproduction条件，不混进material源条件。'
            '完整保留冻结声音事件和后期同步义务，不能降为preference、删除SFX或伪造来源。')
    if (scope.get('transport', {}).get('intake_policy') in {review.SOUND_TEMPO_INTAKE_POLICY, review.COMPLETE_GUIDANCE_INTAKE_POLICY, review.ROOT_ECHO_INTAKE_POLICY, review.SFX_GUIDANCE_INTAKE_POLICY, review.SCHEMA_SHAPE_INTAKE_POLICY}
            and stage == 'A-details'):
        # Only new requests. SoundIntent.tempo_bpm is an optional two-int tuple.
        instruction += (
            'sound.tempo_bpm是可选字段，冻结原文没有明确要求源音乐BPM时直接省略，'
            '绝不根据“缓慢/克制”等词猜出数值。明确要求时只能填写两个1到400整数'
            '组成的JSON数组，如"tempo_bpm":[60,90]。绝不能写'
            '{"item":[60,90]}、{"array":[60,90]}、字符串、单数或其他对象包装。'
            '字段说明不授予新增或修改音乐意图的权利。')
    if (scope.get('transport', {}).get('intake_policy') == review.SCHEMA_SHAPE_INTAKE_POLICY
            and stage == 'A-details'):
        # Explain the exact existing tool schema; do not repair returned objects
        # or change historical request bytes and semantic obligations.
        contract = staged._read_only_staged(query_schema(scope)).details_contract(selection, diagnostic=True)
        schema = wire.project(detail_batch['schema'] if detail_batch else contract['schema'],
                              detail_batch['key'] if detail_batch else stage, atomic_framing=True).schema
        slots = schema['properties']['slots']['properties']
        condition = next(iter(slots.values()))['properties']['conditions']['items']
        context['detail_shape_contract'] = {
            'policy': review.SCHEMA_SHAPE_GUIDANCE_POLICY,
            'condition_same_level_fields': {
                key: {name: deepcopy(value[name]) for name in ('type', 'enum') if name in value}
                for key, value in condition['properties'].items()},
            'condition_required': condition['required'],
            'slots': {key: {'allowed_properties': sorted(value['properties']),
                            'required_properties': value['required']}
                      for key, value in slots.items()},
        }
        instruction += (
            'detail_shape_contract逐项摘自本次工具Schema，不增加新的语义约定。'
            '每条condition的text、strength、responsibility、meaning是同一对象内的平级字段；'
            '各枚举值必须是字符串，不得把其他字段嵌套到strength或其他枚举值里。'
            '每个slot只能使用其allowed_properties列出的键；未列出的键必须省略，空数组也不能提交。'
            'queries只用于允许它的视觉slot，音频slot不得提交queries，包括空数组。')
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
            **({'input_view': view.identity, 'opaque_headers_sha256': authority.digest(view.opaque_headers(selection))})}


def frozen_detail_plan(scope, codec, selection, raw_sha256, view, receipt):
    plan = codec.detail_batches(selection, modality_family=scope.get('creative_authority') is not None)
    coverage = 1 + len(scope['catalog'].get('scene', {}))
    visual = sum(need['modality'] in review.VISUAL for need in selection['needs'])
    size = scope['transport']['candidate_batch_policy']['max_questions']
    a_calls = 1 + len(plan['batches'])
    # Complete conditions, visual choice/necessity, all reports and the entire
    # existing recheck reserve. Reject before the first details dispatch.
    initial_max = (visual * 14 + coverage + 16 + size - 1) // size
    recheck_max = (16 * 14 + coverage + 16 + size - 1) // size
    maximum = a_calls + initial_max + MAX_SHARED_REPAIRS + recheck_max
    if maximum > MAX_PLANNING_CALLS:
        raise ValueError('Complete batched Planning exceeds original call capacity')
    binding = detail_binding(scope, selection, raw_sha256, plan['complete'], view,
                             admission_receipt=receipt)
    binding.update(batch_identity=plan['identity'], a_calls=a_calls,
                   maximum_planning_calls=maximum)
    messages = {batch['key']: view_a_message(scope, view, 'A-details', selection=selection,
                  binding=binding, detail_batch=batch) for batch in plan['batches']}
    # Compile every request before any batch can be sent.
    for batch in plan['batches']:
        structured.request_for(wire.project(batch['schema'], batch['key'], atomic_framing=True).schema)
    return plan, binding, messages


def validate_canonical(catalog, value, *, compiled=False):
    if not wire.Draft202012Validator(semantic_tool_schema(catalog, compiled=compiled)).is_valid(value):
        raise ValueError('Complete canonical Planning schema rejected')


def repair_quote_null_guidance(schema):
    """Pure hint compiled from frozen per-target source branches; never authority.

    Only emits source IDs that the existing Schema already restricts to a
    null quote. Validation still uses the complete unchanged wire contract.
    """
    hints = {}
    definitions = schema.get('$defs', {})
    for target, answer in schema.get('properties', {}).items():
        if not target.startswith('target-'):
            continue
        support = answer.get('properties', {}).get('support', {})
        item = support.get('items', {})
        ref = item.get('$ref') if isinstance(item, dict) else None
        # The wire compiler inlines local $defs before building the request.
        definition = (definitions.get(ref.removeprefix('#/$defs/'), {})
                      if isinstance(ref, str) and ref.startswith('#/$defs/')
                      else item if isinstance(item, dict) else {})
        null_sources = set()
        for branch in definition.get('oneOf', []):
            props = branch.get('properties', {})
            if props.get('quote', {}).get('type') == 'null':
                null_sources.update(props.get('source', {}).get('enum', []))
        if null_sources:
            hints[target] = sorted(null_sources)
    return hints





def details_root_repair_message(original_message, original, stage, admitted):
    """Obtain explicit model-authored unresolved semantics from captured Slots.

    The original stage prompt retains the full frozen source context. The
    original reply remains unchanged and is the only basis for the patch.
    """
    if admitted['decision'] != 'BOUNDED_REPAIR' or admitted['repair_path'] != ['unresolved']:
        raise ValueError('A-details root reply cannot enter shared repair')
    return review.checked_message(original_message + '\n'
        + '〔Easel 原A-details的受控局部补答〕\n'
        + '原始Slots及所有视觉Claim冻结不变。只按工具Schema提交unresolved数组，'
        + '不可重新输出或更改Slots。请核对冻结全片输入与原始回复，'
        + '有未决创作语义请明确列出；确实无新增未决项时由模型明确提交空数组。'
        + '不得假定系统默认空数组，不能制造Creator/Rights授权。\n'
        + review.compact({'origin_stage': stage,
            'original_reply_sha256': admitted['original_sha256'],
            'original_reply': original,
            'repair_path': ['unresolved'],
            'admission_policy': admitted['policy']}))



def reserve_repair_slot(state, stage, identity, save):
    """Reserve one of three Attempt-wide repair operations before model dispatch.

    Existing reservation with an identical identity is reusable only for
    replay/reconciliation of the same session; it never grants a fourth call.
    """
    rows = state['repair_ledger']
    if (not isinstance(rows, list) or state['repair_count'] != len(rows)
            or bool(rows) != state['repair_used']):
        raise ValueError('Shared repair ledger identity changed')
    matching = [row for row in rows if row['stage'] == stage]
    if matching:
        if len(matching) != 1:
            raise ValueError('Duplicate shared repair target')
        row = matching[0]
        if (row['identity'] != identity or
                row['reservation_sha256'] != authority.digest(
                    {k: v for k, v in row.items() if k != 'reservation_sha256'})):
            raise ValueError('Shared repair target or reservation changed')
        return row
    if len(rows) >= MAX_SHARED_REPAIRS:
        raise ValueError('Whole Planning shared repair allowance exhausted (3)')
    core = {'stage': stage, 'key': f'repair-{len(rows):03}',
            'identity': deepcopy(identity)}
    row = {**core, 'reservation_sha256': authority.digest(core)}
    rows.append(row)
    state['repair_count'] = len(rows)
    state['repair_used'] = True
    save()
    return row

def repair_message(scope, original, targets, context=None, *, evidence_ref=False):
    if evidence_ref is True:
        evidence_ref = repair_evidence.POLICY
    support_batch = context if context and context.get('support_policy') == support.REVISION else None
    patcher = correction if correction.enabled(scope) else review
    schema = patcher.patch_schema(targets, support_batch=support_batch, slots=True)
    projection = (repair_evidence.RepairEvidenceProjection(schema, policy=evidence_ref) if evidence_ref
                  else wire.project(schema, 'repair', atomic_framing=True))
    schema = projection.schema
    if correction.enabled(scope):
        prefix = ('〔Easel Planning vNext 单次局部修复〕\n'
            '只提交固定target槽位对应的value，不提交整个对象，不删除Need或原未决报告。'
            'confirmed_necessity只允许按独立冻结依据将被挑战字段从optional改required；'
            'visual_choices仍须保持原conditions/queries/necessity，不得借整体头部升降级。'
            'candidate_answer只修该条响应并提供真实冻结引用；其他已接受答案不可变。'
            + ('candidate_answer每条support只提交合法evidence_ref，文字证据同时提交完整真实quote；'
               '非文本证据只提交evidence_ref，不允许quote。'
               '从本目标evidence_choices_by_target表中选择，不允许跨目标、猜测或创造ref。'
               '模型仍须独立判断该引用是否真正支持当前回答。'
               if evidence_ref else
               'candidate_answer的每项support必须同时提交source、role、quote三个字段，不能省略quote。'
               '当source对应可引用的文本原文时，quote必须是该source的非空连续原文字符串；'
               '当source对应非文本原件时，quote必须显式填写JSON null（不是字符串null），不可漏字段。'
               'source必须从本目标冻结候选中选择，role与source必须满足同一Schema分支，'
               '不要复制其他目标的source或把不合法引用放进修复结果。'
               '特别注意quote_null_source_ids_by_target：本目标的support只要使用列出的source，'
               'quote就只能是JSON null，不论原对象里存在何种数字、版本或文本样值。')
            + '未列出的字段及全部原件不可变，不推定任何授权或素材就绪。修后重新独立核对受影响义务。'
            '不写文件、不供应、不制作。')
        payload = {
                'schema': schema, 'targets': descriptors(targets), 'original': original,
                'inputs': scope['inputs'], 'review_context': context,
                'candidate_review_policy': correction.policy_for(scope),
                'wire_representation': ('证据必须按evidence_ref专属Schema提交，文本引用保留quote，非文本引用不得填写quote。'
                    if evidence_ref else wire.guidance(schema)) + wire.FRAME_GUIDANCE,
                **({'evidence_ref_policy': evidence_ref,
                    'evidence_choices_by_target': {target: [
                        {'evidence_ref': ref, 'source': source, 'role': role, 'quote_kind': kind}
                        for ref, (source, role, kind) in choices.items()]
                        for target, choices in projection.choices.items()}}
                   if evidence_ref else {'quote_null_source_ids_by_target': repair_quote_null_guidance(schema)})}
        if scope['transport'].get('request_view_policy') == request_view.POLICY:
            schema = structured.request_for(schema)['schema']
            payload['schema'] = schema
            payload = request_view.project(payload, schema, stage='repair')
            prefix += request_view.GUIDANCE
        return review.checked_message(prefix + '\n' + review.compact(payload))
    return review.checked_message('〔Easel Planning vNext 单次局部修复〕\n' +
        ('仅修targets列出的未接受局部，按数组下标对应固定target槽位。原件、已接受语义、必要性、') +
        '已接受答案及所有其他字段不可变。不能返回整个对象、删需求、扩授权或放宽准入。'
        'visual_choices的value交同一Need，仅修其header，conditions/queries/necessity须保持。'
        'coverage缺口只能补充有冻结支持的视觉Need，不能改掉原Need。改后再次独立复核。'
        + ('通过唯一工具按schema固定target槽位提交value；不填写target/question/evidence身份，不写文件。\n') + review.compact({
            'schema': schema, 'targets': descriptors(targets),
            **({'wire_representation': wire.GUIDANCE + (wire.FRAME_GUIDANCE)}
               if 'wire' in scope.get('transport', {}) else {}),
            'original': original, 'inputs': scope['inputs'], 'review_context': context}))


def bind_d1_d2_review(directory, *, envelope, state, d2_enabled):
    """One deterministic B directory for live Owner and cold replay."""
    bound = creative.bind_review_claims(directory, envelope=envelope,
                                        conditions=state['conditions'], headers=state['headers'])
    if d2_enabled:
        bound = d2.bind_directory(bound, envelope=envelope,
                                  conditions=state['conditions'], headers=state['headers'])
    return bound


def run(attempt, planning_context, canonical, mode, route, dispatch):
    store = AttemptMaterialStore(attempt['workspace']['path'])
    root = store.attempt_root
    state = store.read_recovery_record(STATE_KEY)
    if state is not None and state.get('schema') != VIEW_JOURNAL:
        raise ValueError('Historical Planning protocol is read-only; no recovery dispatch')
    if state is not None and state.get('scope', {}).get('transport', {}).get('intake_policy') != review.INTAKE_POLICY:
        raise ValueError('Historical Planning intake is read-only; no recovery dispatch')
    requested_creative = planning_context.get('creative_claim_policy')
    if (requested_creative not in (None, creative.OWNER_POLICY)
            or attempt.get('creative_claim_policy') != requested_creative):
        raise ValueError('Frozen D1 Attempt and Planning Context policy differ')
    requested_d2 = planning_context.get('d2_review_policy')
    if (requested_d2 not in (None, d2.POLICY)
            or attempt.get('d2_review_policy') != requested_d2
            or (requested_d2 and requested_creative != creative.OWNER_POLICY)):
        raise ValueError('Frozen D2 Attempt and Planning Context policy differ')
    inputs = authority.load_inputs(attempt, canonical, planning_context, mode)
    catalog = source_catalog(canonical, {'creator_context': inputs['creator_context'], 'proposal': inputs.get('proposal')})
    scope = {'policy': POLICY, 'creation_id': attempt['creation_id'], 'attempt_id': attempt['attempt_id'],
             'context_refs': planning_context['context_refs'], 'canonical': canonical, 'mode': mode,
             'inputs': inputs, 'catalog': catalog}
    delegation = (creative.compile_envelope(attempt, canonical, planning_context, mode)
                  if requested_creative == creative.OWNER_POLICY else None)
    if delegation is not None:
        scope['creative_authority'] = {'policy': creative.OWNER_POLICY, 'envelope': delegation}
    if requested_d2:
        scope['d2_review_policy'] = d2.POLICY
    if state is not None:
        validate_transport(state.get('schema'), state['scope'])
    view = input_views.PlanningInputView(inputs, catalog)
    scope['input_view'] = view.identity
    scope['transport'] = state['scope']['transport'] if state is not None else transport_identity(catalog, intake_inputs=inputs)
    if state is None:
        if store.read_recovery_record('semantic-planning-v3') is not None or list(
                (root / 'materials/recoveries').glob('planning-structure-repair-*.json')):
            raise ValueError('Historical Planning journal is read-only; no recovery dispatch')
        state = {'schema': VIEW_JOURNAL, 'scope': scope, 'route': route,
                 'calls': {}, 'repair_used': False, 'repair_count': 0,
                  'repair_ledger': [], 'wire_admissions': {}, 'wire_repairs': {},
                   'stage_regenerations': {}, 'b_normalizations': {},
                  'input_view_snapshot': view.snapshot(),
                 'b_identity_policy': wire.B_IDENTITY_POLICY if correction.enabled(scope) else None,
                 'repair_evidence_policy': repair_evidence.POLICY if correction.enabled(scope) else None}
        store.write_recovery_record(STATE_KEY, state)
    elif (state.get('scope') != scope or state.get('route') != route):
        raise ValueError('Frozen vNext input, policy or execution route changed; no refreshed allowance')
    if not admission_enabled(scope) and 'admissions' in state:
        raise ValueError('Selection admission policy cannot be removed or downgraded')
    if state.get('terminal_failure'):
        raise ValueError('Original Planning frozen-source violation is reject-only; no recovery dispatch')
    if state.get('input_view_snapshot') != view.snapshot():
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
    def b_projection(schema, key):
        if key.startswith('repair-') and any(row['key'] == key and
                row['stage'].startswith('regen:') for row in state['repair_ledger']):
            return wire.project(schema, key, atomic_framing=True)
        if key.startswith('repair-') and state.get('repair_evidence_policy') in (repair_evidence.POLICY, repair_evidence.LEGACY_POLICY):
            return repair_evidence.RepairEvidenceProjection(schema, policy=state['repair_evidence_policy'])
        if (key.startswith('B-') and state.get('b_identity_policy') == wire.B_IDENTITY_POLICY):
            return wire.b_identity_project(schema, key)
        return wire.project(schema, key, atomic_framing=True)

    def invoke(key, message, schema=None):
        frozen()
        if key not in state['calls'] and len(state['calls']) >= MAX_PLANNING_CALLS:
            raise ValueError('Fixed Planning call range exhausted; no new dispatch')
        try:
            projection = b_projection(schema, key)
            binding = state.setdefault('schema_bindings', {}).get(key)
            if binding is not None and binding != projection.identity:
                raise ValueError('Planning stage wire identity changed')
            state['schema_bindings'][key] = projection.identity
            save()  # Exact canonical/wire identity precedes submission.
            schema = projection.schema
            if (scope['transport'].get('b_root_title_policy') == structured.B_ROOT_TITLE_POLICY
                    and key.startswith('B-') and state.get('b_identity_policy') != wire.B_IDENTITY_POLICY):
                schema = structured.b_review_parameters(schema)
            def reconcile_p0(original_key, original_message, original_session):
                # A prior B submission may already be terminal in the external
                # owner even if the local capture was marked TRANSPORT_FAILED
                # while its transcript was temporarily unavailable.
                from easel import creation
                calls = (creation.get_creation(attempt['creation_id']).get('delivery') or {}).get('agent_calls', {})
                matches = [call for call in calls.values()
                           if call.get('session_key') == 'agent:main:' + original_session]
                if (len(matches) != 1 or matches[0].get('status') != 'ok'
                        or matches[0].get('reply_contract') != 'planning-result-v3'
                        or matches[0].get('runtime_release') != 'released'
                        or not matches[0].get('terminal_receipt')):
                    from easel.creation_delivery import DeliveryExecutionUncertain
                    raise DeliveryExecutionUncertain('P0 original run has no verified terminal receipt')
                # retry_failed=False at the existing Owner boundary makes
                # this a read of the same terminal run, never a new model call.
                return dispatch('structure_repair' if original_key.startswith('repair-') else 'planning',
                    original_message, original_session,
                    structured_result=structured.request_for(projection.schema),
                    expected_runtime_sha256=scope['transport']['runtime_sha256'])
            result = capture(state['calls'], key, review.checked_message(message),
                f"semantic-{attempt['attempt_id']}-vnext-{key}",
                lambda key, text, session: dispatch('structure_repair' if key.startswith('repair-') else 'planning', text, session,
                    **({'structured_result': structured.request_for(schema)} if schema is not None else {}),
                    expected_runtime_sha256=scope['transport']['runtime_sha256']), save,
                refuse_uncertain_reentry=(key.startswith('repair-') or
                    key.startswith('A-details-') or key.startswith('B-') and state.get('b_identity_policy') == wire.B_IDENTITY_POLICY),
                reconcile=reconcile_p0 if (key.startswith('repair-') or
                    key.startswith('A-details-') or key.startswith('B-') and state.get('b_identity_policy') == wire.B_IDENTITY_POLICY) else None)
        finally:
            frozen()  # Async/uncertain results cannot skip source-integrity recording.
        return result
    def candidate(key, original, schema, *, strict=False):
        projection = b_projection(schema, key)
        if state['schema_bindings'].get(key) != projection.identity:
            raise ValueError('Planning stage wire identity changed')
        errors = projection.errors(original)
        diagnostic = {'wire_errors': errors, 'original_sha256': state['calls'][key]['reply_sha256']}
        if isinstance(projection, wire.BIdentityProjection):
            n = projection.normalization_receipt(original)
            evidence = {k:v for k,v in n.items() if k!='normalized'} if n else None
            if evidence is not None:
                earlier = state['b_normalizations'].get(key)
                if earlier is not None and earlier != evidence:
                    raise ValueError('B normalized representation identity changed')
                state['b_normalizations'][key] = evidence
            elif key in state['b_normalizations']:
                raise ValueError('Frozen B normalization silently disappeared')
        previous = state.setdefault('wire_diagnostics', {}).get(key)
        if previous is not None and previous != diagnostic:
            raise ValueError('Original wire validation changed')
        state['wire_diagnostics'][key] = diagnostic
        save()
        if strict and errors:
            raise ValueError('Complete Planning wire schema rejected')
        return projection.decode_valid(original) if strict else projection.decode_candidate(original)
    def reserve_shared_repair(stage, identity):
        return reserve_repair_slot(state, stage, identity, save)
    def admitted_details(key, original, schema):
        """Strict A-details admission or explicit model-authored missing root."""
        projection = b_projection(schema, key)
        raw = state['calls'][key]['reply']
        receipt = admission.classify_details_wire(raw, projection.schema,
            binding={'attempt_id': attempt['attempt_id'], 'stage': key,
                     'source_sha256': authority.digest(view.codec.references),
                     'schema_binding_sha256': authority.digest(projection.identity)})
        old_receipt = state['wire_admissions'].get(key)
        if old_receipt is not None and old_receipt != receipt:
            raise ValueError('Frozen A-details output admission changed')
        state['wire_admissions'][key] = receipt
        save()
        if receipt['decision'] == 'ACCEPT':
            return candidate(key, original, schema, strict=True)
        candidate(key, original, schema, strict=False)  # Capture original errors.
        if receipt['decision'] != 'BOUNDED_REPAIR':
            raise ValueError('Complete Planning wire schema rejected (not recoverable)')
        identity = {'policy': admission.DETAILS_RECOVERY_POLICY,
                    'stage': key, 'origin_sha256': receipt['original_sha256'],
                    'schema_sha256': receipt['schema_sha256'],
                    'admission_sha256': authority.digest(receipt),
                    'target_path': ['unresolved']}
        row = reserve_shared_repair('wire:' + key, identity)
        patch_schema = admission.details_repair_schema(projection.schema)
        message = details_root_repair_message(detail_messages[key], raw, key, receipt)
        patch_raw = invoke(row['key'], message, patch_schema)
        patch = candidate(row['key'], patch_raw, patch_schema, strict=True)
        complete = admission.bind_details_repair(original, patch, projection.schema)
        evidence = {'policy': admission.DETAILS_RECOVERY_POLICY, 'stage': key,
                    'repair_stage': row['key'], 'reservation_sha256': row['reservation_sha256'],
                    'original_reply_sha256': receipt['original_sha256'],
                    'patch_reply_sha256': state['calls'][row['key']]['reply_sha256'],
                    'effective_wire_sha256': authority.digest(complete),
                    'admission_sha256': authority.digest(receipt)}
        prior = state['wire_repairs'].get(key)
        if prior is not None and prior != evidence:
            raise ValueError('Recovered A-details differs from frozen original and patch')
        state['wire_repairs'][key] = evidence
        save()
        return projection.decode_valid(complete)

    def terminal_failure_for(key, schema):
        # The currently configured dispatch alone may inspect its own native
        # failed Run; a generic Python exception cannot authorize re-dispatch.
        inspector = getattr(dispatch, 'inspect_terminal_no_tool', None)
        if not callable(inspector):
            return None
        projection = b_projection(schema, key)
        session = f"semantic-{attempt['attempt_id']}-vnext-{key}"
        schema_sha = structured.request_for(projection.schema)['schemaSha256']
        try:
            observed = inspector(key, session, schema_sha)
        except DeliveryExecutionUncertain:
            return None
        return stage_loop.confirmed_no_tool(observed, stage=key,
            schema_sha256=schema_sha, session=session)

    def resolve_details_stage(key, schema, original_message):
        """Only current D1 A-details receives whole-stage regeneration.

        Original Agent call is retained even if it has no valid model reply.
        New generations are distinct repair-NNN captures in the *same*
        Attempt-wide ledger. Any uncertain run still stops at its old identity.
        """
        projection = b_projection(schema, key)
        stage_entry = state['stage_regenerations'].get(key)
        if stage_entry is None:
            try:
                original = invoke(key, original_message, schema)
            except (RuntimeError, DeliveryExecutionUncertain):
                decision = terminal_failure_for(key, schema)
                if decision is None:
                    raise  # No native terminal proof: never dispatch a new Run.
                if state['calls'][key].get('reply') is not None:
                    raise ValueError('Original no-tool operation unexpectedly has a reply')
                original_admission = {
                    'policy': stage_loop.POLICY, 'decision': 'STAGE_REGENERATE',
                    'reason': 'TERMINAL_NO_TOOL',
                    'terminal_evidence_sha256': authority.digest(decision)}
                original_diagnostic = {
                    'wire_errors': [], 'original_sha256': None,
                    'terminal_failure_sha256': authority.digest(decision)}
            else:
                raw_text = state['calls'][key]['reply']
                decision = stage_loop.source_only_failure(raw_text, projection.schema)
                if decision is None:
                    return admitted_details(key, original, schema), key
                original_admission = admission.classify_details_wire(raw_text, projection.schema,
                    binding={'attempt_id': attempt['attempt_id'], 'stage': key,
                        'source_sha256': authority.digest(view.codec.references),
                        'schema_binding_sha256': authority.digest(projection.identity)})
                if original_admission['decision'] != 'REJECT':
                    raise ValueError('Invalid creative source unexpectedly admitted')
                original_diagnostic = {'wire_errors': projection.errors(original),
                                       'original_sha256': state['calls'][key]['reply_sha256']}
                if not original_diagnostic['wire_errors']:
                    raise ValueError('A-details source regression has no strict errors')
            state['wire_admissions'][key] = original_admission
            state['wire_diagnostics'][key] = original_diagnostic
            stage_entry = {'policy': stage_loop.POLICY, 'original_failure': decision,
                           'history': [], 'effective_key': None}
            state['stage_regenerations'][key] = stage_entry
            save()
        else:
            if (stage_entry.get('policy') != stage_loop.POLICY
                    or not isinstance(stage_entry.get('history'), list)
                    or len(stage_entry['history']) > stage_loop.MAX_STAGE_REGENERATIONS):
                raise ValueError('Persisted A-details recovery chain invalid')
            orig_text = state['calls'].get(key, {}).get('reply')
            if orig_text is None:
                observed = stage_loop.confirmed_no_tool(
                    stage_entry['original_failure'].get('terminal_evidence'),
                    stage=key, schema_sha256=structured.request_for(projection.schema)['schemaSha256'],
                    session=f"semantic-{attempt['attempt_id']}-vnext-{key}")
            else:
                observed = stage_loop.source_only_failure(orig_text, projection.schema)
            if observed != stage_entry['original_failure']:
                raise ValueError('Frozen original A-details recovery reason changed')

        for ordinal in range(stage_loop.MAX_STAGE_REGENERATIONS):
            prior = (stage_entry['original_failure'] if ordinal == 0 else
                     stage_entry['history'][ordinal-1].get('failure')
                     if ordinal-1 < len(stage_entry['history']) else None)
            if prior is None:
                raise ValueError('Regeneration decision chain is not reconstructible')
            identity = stage_loop.recovery_identity(key, prior, ordinal=ordinal,
                frozen_schema_sha256=structured.request_for(projection.schema)['schemaSha256'],
                detail_binding_sha256=authority.digest(binding))
            row = reserve_shared_repair('regen:' + key + ':' + str(ordinal), identity)
            expected = {'repair_stage': row['key'],
                        'reservation_sha256': row['reservation_sha256'],
                        'cause': prior}
            if ordinal < len(stage_entry['history']):
                saved = stage_entry['history'][ordinal]
                if any(saved.get(k) != v for k,v in expected.items()):
                    raise ValueError('Persisted regeneration operation changed')
            else:
                stage_entry['history'].append(expected)
                save()  # Reserve and lineage must predate real model dispatch.
            message = stage_loop.regeneration_message(original_message, key, prior, ordinal)
            try:
                generated = invoke(row['key'], message, schema)
            except (RuntimeError, DeliveryExecutionUncertain):
                failure = terminal_failure_for(row['key'], schema)
                if failure is None:
                    raise
                if state['calls'][row['key']].get('reply') is not None:
                    raise ValueError('Failed regeneration unexpectedly has model arguments')
                diagnostic = {'wire_errors': [], 'original_sha256': None,
                              'terminal_failure_sha256': authority.digest(failure)}
                if row['key'] in state['wire_diagnostics'] and state['wire_diagnostics'][row['key']] != diagnostic:
                    raise ValueError('Regeneration terminal diagnostic changed')
                state['wire_diagnostics'][row['key']] = diagnostic
            else:
                full = b_projection(schema, row['key'])
                diagnostic = {'wire_errors': full.errors(generated),
                              'original_sha256': state['calls'][row['key']]['reply_sha256']}
                if row['key'] in state['wire_diagnostics'] and state['wire_diagnostics'][row['key']] != diagnostic:
                    raise ValueError('Regeneration original wire diagnostic changed')
                state['wire_diagnostics'][row['key']] = diagnostic
                if not diagnostic['wire_errors']:
                    accepted = candidate(row['key'], generated, schema, strict=True)
                    completed = {**expected, 'result': 'ACCEPT',
                                 'reply_sha256': state['calls'][row['key']]['reply_sha256']}
                    if stage_entry['history'][ordinal] not in (expected, completed):
                        raise ValueError('Persisted regeneration accepted lineage changed')
                    stage_entry['history'][ordinal] = completed
                    stage_entry['effective_key'] = row['key']
                    save()
                    return accepted, row['key']
                failure = stage_loop.source_only_failure(
                    state['calls'][row['key']]['reply'], full.schema)
                if failure is None:
                    raise ValueError('Regenerated A-details violates an unrecoverable Schema constraint')
            rejected = {**expected, 'result': 'STAGE_REGENERATE', 'failure': failure}
            if stage_entry['history'][ordinal] not in (expected, rejected):
                raise ValueError('Persisted regeneration rejection changed')
            stage_entry['history'][ordinal] = rejected
            save()
        raise ValueError('A-details regeneration exhausted the per-stage two-attempt limit')

    def b_message(batch):
        transported = {**batch, 'response_schema': wire.project(batch['response_schema'], 'B', atomic_framing=True).schema,
                       'wire_representation': wire.guidance(batch['response_schema'])}
        return review.checked_message(review.review_message(transported))
    def repair(stage, original, targets, context=None):
        message = repair_message(scope, original, targets, context,
            evidence_ref=state.get('repair_evidence_policy') if state.get('repair_evidence_policy') in (repair_evidence.POLICY, repair_evidence.LEGACY_POLICY) else False)
        # Original A captures, not mutable sidecar Claim dictionaries, are
        # the sole pre-Repair claim authority for this fresh Attempt.
        d1_carrier = None
        if delegation is not None and d1_state is not None:
            creative.verify_a_claim_origin(delegation, d1_bridge, d1_batched,
                state['calls']['A-selection']['reply'],
                {batch['key']: state['calls'][effective_capture_keys[batch['key']]]['reply']
                    for batch in detail_plan['batches']},
                state['calls'], d1_state['headers'], d1_state['conditions'],
                effective_batches=details, capture_keys={k:v for k,v in effective_capture_keys.items() if k!=v})
            if any(t['kind'] in {'complete_obligation', 'visual_choices',
                                 'frozen_visual_coverage', 'confirmed_necessity'} for t in targets):
                d1_carrier = creative.ExtendedSharedRepairCarrier(
                    delegation, original, targets,
                    d1_state['conditions'], d1_state['headers'])
                intro, payload = message.rsplit('\n', 1)
                message = review.checked_message(intro +
                    '\n当前 D1 每个视觉修复 value 必须同槽提交 authority Claim；'
                    'Claim 不构成 Creator/Rights 授权。\n' + payload)
        repair_identity = {'stage': stage, 'targets': descriptors(targets),
                           'original_sha256': authority.digest(original), 'context_sha256': authority.digest(context),
                           **({'creative_policy': creative.OWNER_POLICY,
                               'claim_state_sha256': authority.digest(d1_state)}
                              if delegation is not None else {})}
        reservation = reserve_shared_repair(stage, repair_identity)
        state['repair'] = repair_identity
        save()
        support_batch = context if context and context.get('support_policy') == support.REVISION else None
        patcher = correction if correction.enabled(scope) else review
        schema = d1_carrier.schema if d1_carrier is not None else patcher.patch_schema(
            targets, support_batch=support_batch, slots=True)
        output = invoke(reservation['key'], message, schema)
        decoded = candidate(reservation['key'], output, schema, strict=True)
        if d1_carrier is not None:
            result, d1_state['conditions'], d1_state['headers'], evidence = d1_carrier.apply(
                decoded, d1_carrier.identity)
            d1_state['repair_evidence'] = evidence
            previous_claims = state.get('creative_claims')
            if (previous_claims is not None and previous_claims.get('repair_evidence') is not None
                    and previous_claims != d1_state):
                raise ValueError('Persisted D1 repaired Claim differs from original Wire replay')
            state['creative_claims'] = deepcopy(d1_state)
            save()
            return result, output
        patches = patcher.decode_patch_slots(decoded, targets, support_batch=support_batch)
        return patcher.apply_patches(original, patches, targets, support_batch=support_batch), output
    codec = staged._read_only_staged(query_schema(scope))
    d1_bridge = (creative.OpaqueHeaderBridge(view.codec, codec, delegation)
                 if delegation is not None else None)
    selection_schema = intake_selection(scope, d1_bridge.schema if d1_bridge else view.codec.schema)
    a_message_for = lambda stage, **kw: view_a_message(scope, view, stage, **kw)
    selected = invoke('A-selection', a_message_for('A-selection'), selection_schema)
    selected = candidate('A-selection', selected, selection_schema, strict=d1_bridge is not None)
    selected_receipt = None
    if admission_enabled(scope):
        admitted = selection_admission(scope, state['calls']['A-selection'], selection_schema,
                                       state['schema_bindings']['A-selection'])
        previous = state.get('admissions', {}).get('A-selection')
        if previous is None and (state.get('detail_binding') is not None
                                 or any(key.startswith('A-details') for key in state['calls'])):
            raise ValueError('Selection admission receipt missing after details binding')
        if previous is not None and previous != admitted:
            raise ValueError('Persisted selection admission or normalized candidate changed')
        state.setdefault('admissions', {})['A-selection'] = admitted
        save()
        selected = require_selection_admission(admitted, scope=scope)
        selected_receipt = admitted['receipt']
    d1_state = None
    if d1_bridge:
        selected, header_records = d1_bridge.decode(selected, d1_bridge.identity)
        d1_state = {'policy': creative.OWNER_POLICY, 'envelope': delegation,
                    'bridge_identity': d1_bridge.identity, 'headers': header_records,
                    'conditions': {}, 'a_batch': None}
        if state.get('creative_claims') is not None and state['creative_claims']['bridge_identity'] != d1_bridge.identity:
            raise ValueError('Frozen D1 source identity changed')
    else:
        selected = view.codec.decode(selected, view.codec.identity, diagnostic=True)
    detail_plan, binding, detail_messages = frozen_detail_plan(scope, codec, selected,
        state['calls']['A-selection']['reply_sha256'], view, selected_receipt)
    if state.get('detail_binding') is not None and state['detail_binding'] != binding:
        raise ValueError('Persisted details identity changed')
    state['detail_binding'] = binding
    save()
    d1_batched = (creative.BatchedVisualClaimCarrier(
        codec, selected, delegation, source_bridge_identity=d1_bridge.identity,
        source_codec=view.codec)
        if d1_bridge is not None else None)
    details = {}
    effective_capture_keys = {}
    unresolved_count = len(selected['unresolved'])
    for batch in detail_plan['batches']:
        key = batch['key']
        schema = d1_batched.batches[key] if d1_batched else batch['schema']
        if d1_batched is not None:
            details[key], effective_capture_keys[key] = resolve_details_stage(
                key, schema, detail_messages[key])
        else:
            raw = invoke(key, detail_messages[key], schema)
            details[key] = candidate(key, raw, schema, strict=False)
            effective_capture_keys[key] = key
        if d1_batched is None:
            codec.details_shape(selected, details[key], batch['schema'], repair_missing_leaves=True)
        unresolved_count += len(details[key]['unresolved'])
        if unresolved_count > 16:
            raise ValueError('Complete unresolved report capacity exceeded')
    if d1_batched is not None:
        initial, d1_state['conditions'], d1_state['a_batch'] = d1_batched.merge(details, d1_batched.identity)
        creative.verify_a_claim_origin(
            delegation, d1_bridge, d1_batched, state['calls']['A-selection']['reply'],
            {key: state['calls'][effective_capture_keys[key]]['reply'] for key in details},
            state['calls'], d1_state['headers'], d1_state['conditions'],
            effective_batches=details,
            capture_keys={k:v for k,v in effective_capture_keys.items() if k!=v})
        existing = state.get('creative_claims')
        if existing is not None and existing.get('a_batch') != d1_state['a_batch']:
            raise ValueError('D1 frozen original A Claim batch changed')
        if existing is not None and existing.get('repair_evidence') is None and existing != d1_state:
            raise ValueError('D1 original Claim journal changed')
        # A completed Repair is frozen until the exact captured Repair replays.
        # Do not overwrite its identity with a recomputed A snapshot first.
        if existing is None:
            state['creative_claims'] = deepcopy(d1_state)
            save()
    else:
        initial = codec.assemble_batches_candidate(selected, detail_plan, details, repair_missing_leaves=True)
    value = initial
    a_keys = ['A-selection', *(batch['key'] for batch in detail_plan['batches'])]
    invalid_a_wire = any(state['wire_diagnostics'][key]['wire_errors']
                         for key in a_keys if key not in state['stage_regenerations'])
    correction_result = None
    if correction.enabled(scope):
        correction_result = correction.evaluate(initial, scope, view, invoke, candidate, repair,
                                                max_calls=MAX_PLANNING_CALLS, a_calls=binding['a_calls'],
                                                b_identity=state.get('b_identity_policy') == wire.B_IDENTITY_POLICY,
                                                 claim_binding=(lambda directory: bind_d1_d2_review(
                                                     directory, envelope=delegation, state=d1_state,
                                                     d2_enabled=bool(requested_d2)))
                                                 if d1_state is not None else None)
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
        validate_canonical(catalog, value, compiled=True)
        value = proposal.model_dump(mode='json')
        initial_review_value = value
        directory = review.questions(proposal, inputs, catalog, supported=True, source_bound=True)
        view.check_review(directory)
        initial_responses, responses = [], []
        batches = review.review_batches(directory)
        coverage_count = sum(q['kind'] == 'frozen_visual_coverage' for q in directory['questions'])
        maximum_rechecks = (16 * 13 + coverage_count + 47) // 48
        if binding['a_calls'] + len(batches) + MAX_SHARED_REPAIRS + maximum_rechecks > MAX_PLANNING_CALLS:
            raise ValueError('Complete review and required recheck exceed fixed Planning call range')
        messages = [b_message(b) for b in batches]
        for index, (batch, message) in enumerate(zip(batches, messages, strict=True)):
            response = invoke(f'B-{index:03}', message, batch['response_schema'])
            initial_responses.append(response)
            response = candidate(f'B-{index:03}', response, batch['response_schema'])
            response = support.decode_slots(response, batch)
            answer_targets = review.answer_targets(response, batch)
            if answer_targets:
                response, output = repair(f'B-{index:03}', response, answer_targets, batch)
                lineage = {'stage': f'B-{index:03}', 'targets': descriptors(answer_targets), 'output': output}
            elif state['wire_diagnostics'][f'B-{index:03}']['wire_errors']:
                raise ValueError('Invalid review wire cannot be accepted without local repair')
            responses.append(review.validate_answers(response, batch))
        targets = review.semantic_targets(directory, responses)
        before_semantic = [r.model_dump(mode='json') for r in responses]
        if targets:
            value, output = repair('semantic', value, targets)
            lineage = {'stage': 'semantic', 'targets': descriptors(targets), 'output': output}
            proposal = parse_proposal(value, catalog)
            validate_canonical(catalog, value, compiled=True)
            updated = review.questions(proposal, inputs, catalog, supported=True, source_bound=True)
            view.check_review(updated)
            kept, pending = review.recheck(directory, responses, updated)
            pending_batches = review.review_batches(pending)
            messages = [b_message(b) for b in pending_batches]
            for i, (batch, message) in enumerate(zip(pending_batches, messages, strict=True)):
                response = invoke(f'B-recheck-{i:03}', message, batch['response_schema'])
                response = candidate(f'B-recheck-{i:03}', response, batch['response_schema'], strict=True)
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
    checkpoint = {'schema': VIEW_CHECKPOINT,
        'policy': POLICY, 'scope': scope,
        'initial': initial, 'initial_review_value': initial_review_value,
        **({'admissions': deepcopy(state['admissions'])} if admission_enabled(scope) else {}),
        **({'candidate_correction': correction_result['trace']} if correction_result is not None else {}),
        'initial_responses': initial_responses, 'before_semantic': before_semantic,
        'repair': lineage,
        **({'candidate_repairs': correction_result['repairs']}
           if correction_result is not None else {}),
        'draft_sha256': hashlib.sha256(effective).hexdigest(),
        'assembled_a_sha256': authority.digest(initial), 'detail_binding': state['detail_binding'],
        'proposal': proposal.model_dump(mode='json'), 'plan': plan.model_dump(mode='json'),
        'proof': proof, 'review_sha256': authority.digest(directory),        **({'creative_claims': deepcopy(d1_state)} if d1_state is not None else {}),
        'responses': [r.model_dump(mode='json') for r in responses],
        'schema_bindings': state['schema_bindings'], 'wire_diagnostics': state['wire_diagnostics'],
        'wire_admissions': deepcopy(state['wire_admissions']),
        'wire_repairs': deepcopy(state['wire_repairs']),
        'stage_regenerations': deepcopy(state['stage_regenerations']),
        'b_normalizations': deepcopy(state['b_normalizations']),
        'repair_count': state['repair_count'],
        'repair_ledger': deepcopy(state['repair_ledger']),
        **({'b_identity_policy': wire.B_IDENTITY_POLICY}
           if state.get('b_identity_policy') == wire.B_IDENTITY_POLICY else {}),
        **({'repair_evidence_policy': state['repair_evidence_policy']}
           if state.get('repair_evidence_policy') in (repair_evidence.POLICY, repair_evidence.LEGACY_POLICY) else {}),
        'wire_originals': {key: call.get('reply') for key, call in state['calls'].items()},
        'capture': {key: {k: v for k, v in call.items() if k != 'reply'}
                    for key, call in state['calls'].items()}}
    if requested_d2:
        checkpoint['d2_decision_proof'] = d2.compile_decision_proofs(
            directory, responses, attempt_id=attempt['attempt_id'],
            b_captures={key: call['reply'] for key, call in state['calls'].items()
                        if key.startswith('B-')})
    encoded = review.compact(checkpoint).encode()
    if len(encoded) > MAX_CHECKPOINT_BYTES:
        raise ValueError('Complete frozen checkpoint exceeds local artifact capacity')
    frozen()
    # Existing atomic file writer: interrupted publication recovers captured
    # results only, and cannot replace different already-published artifacts.
    try:
        write_file(root, 'SEMANTIC_INPUT_VIEW.json', review.compact(view.snapshot()).encode())
        for key, name in [('A-selection', 'SEMANTIC_A_SELECTION.json'),
                         *((b['key'], b['key'].replace('A-details-', 'SEMANTIC_A_DETAILS_') + '.json')
                           for b in detail_plan['batches'])]:
            write_file(root, name, state['calls'][effective_capture_keys.get(key, key)]['reply'].encode())
        if admission_enabled(scope):
            write_file(root, 'SEMANTIC_A_SELECTION_NORMALIZED.json',
                       admission.canonical_json(state['admissions']['A-selection']['candidate']).encode())
        write_file(root, 'SEMANTIC_A_ASSEMBLY.json', review.compact(initial).encode())
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
    frozen_owner = scope.get('creative_authority')
    frozen_policy = frozen_owner.get('policy') if isinstance(frozen_owner, dict) else None
    if (frozen_policy not in (None, creative.OWNER_POLICY)
            or attempt is None or attempt.get('creative_claim_policy') != frozen_policy):
        raise ValueError('D1 Checkpoint and frozen Attempt policy differ')
    if (scope.get('d2_review_policy') not in (None, d2.POLICY)
            or attempt.get('d2_review_policy') != scope.get('d2_review_policy')
            or (scope.get('d2_review_policy') and frozen_policy != creative.OWNER_POLICY)):
        raise ValueError('D2 Checkpoint and frozen Attempt policy differ')
    if not admission_enabled(scope) and ('admissions' in checkpoint or
            (Path(root) / 'planning/SEMANTIC_A_SELECTION_NORMALIZED.json').exists()):
        raise ValueError('Selection admission policy was removed or downgraded')
    if admission_enabled(scope) and set(checkpoint.get('admissions', {})) != {'A-selection'}:
        raise ValueError('Frozen selection admission coverage changed')
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
    view = input_views.PlanningInputView(inputs, catalog)
    if read_artifact(root, 'SEMANTIC_INPUT_VIEW.json') != review.compact(view.snapshot()).encode():
        raise ValueError('Frozen input view snapshot differs from source reconstruction')
    a_artifact = 'SEMANTIC_A_ASSEMBLY.json'
    a_raw = read_artifact(root, a_artifact, MAX_RESULT_BYTES)
    initial = json.loads(a_raw)
    if (initial != checkpoint['initial'] or (authority.digest(initial))
            != checkpoint['assembled_a_sha256']):
        raise ValueError('vNext original captured A changed')
    used_bindings = set()
    repair_rows = checkpoint.get('repair_ledger')
    if (not isinstance(repair_rows, list) or len(repair_rows) > MAX_SHARED_REPAIRS
            or checkpoint.get('repair_count') != len(repair_rows)
            or len({row.get('stage') for row in repair_rows}) != len(repair_rows)):
        raise ValueError('Frozen shared three-repair ledger changed')
    for i, row in enumerate(repair_rows):
        if (row.get('key') != f'repair-{i:03}'
                or row.get('reservation_sha256') != authority.digest(
                    {k: v for k, v in row.items() if k != 'reservation_sha256'})
                or row['key'] not in checkpoint.get('capture', {})):
            raise ValueError('Frozen repair reservation or capture changed')
    if (set(checkpoint.get('wire_admissions', {})) !=
            {batch['key'] for batch in checkpoint.get('detail_batch_plan', {}).get('batches', [])}
            and checkpoint.get('detail_batch_plan') is not None):
        raise ValueError('Frozen A-details admission coverage changed')
    def reserved_repair(stage, identity):
        matches = [row for row in repair_rows if row['stage'] == stage]
        if len(matches) != 1 or matches[0]['identity'] != identity:
            raise ValueError('Frozen shared repair target or budget differs')
        return matches[0]


    regenerated_repair_keys = {row['repair_stage'] for entry in checkpoint.get('stage_regenerations', {}).values()
                               for row in entry.get('history', [])}
    def candidate(key, original, schema, *, strict=False):
        projection = (wire.project(schema, key, atomic_framing=True)
                       if key in regenerated_repair_keys else
                       repair_evidence.RepairEvidenceProjection(schema, policy=checkpoint['repair_evidence_policy'])
                      if key.startswith('repair-') and checkpoint.get('repair_evidence_policy') in (repair_evidence.POLICY, repair_evidence.LEGACY_POLICY)
                      else wire.b_identity_project(schema, key)
                      if key.startswith('B-') and checkpoint.get('b_identity_policy') == wire.B_IDENTITY_POLICY
                      else wire.project(schema, key, atomic_framing=True))
        if checkpoint.get('schema_bindings', {}).get(key) != projection.identity:
            raise ValueError('Frozen Planning stage wire identity changed')
        used_bindings.add(key)
        raw = checkpoint.get('wire_originals', {}).get(key)
        if key == 'A-selection' or key.startswith('A-details-'):
            name = ('SEMANTIC_A_SELECTION.json' if key == 'A-selection'
                    else key.replace('A-details-', 'SEMANTIC_A_DETAILS_') + '.json')
            if read_artifact(root, name, MAX_RESULT_BYTES).decode() != raw:
                raise ValueError('Frozen staged original changed')
        if (not isinstance(raw, str) or json.loads(raw) != original
                or hashlib.sha256(raw.encode()).hexdigest() != checkpoint['capture'][key]['reply_sha256']):
            raise ValueError('Frozen wire original or capture hash changed')
        errors = projection.errors(original)
        diagnostic = {'wire_errors': errors, 'original_sha256': hashlib.sha256(raw.encode()).hexdigest()}
        if isinstance(projection, wire.BIdentityProjection):
            n = projection.normalization_receipt(original)
            evidence = {k:v for k,v in n.items() if k!='normalized'} if n else None
            if checkpoint.get('b_normalizations', {}).get(key) != evidence:
                raise ValueError('Frozen B lossless normalization receipt changed')
        if checkpoint.get('wire_diagnostics', {}).get(key) != diagnostic:
            raise ValueError('Frozen wire diagnostic changed')
        if strict and errors:
            raise ValueError('Frozen complete wire schema rejected')
        return projection.decode_valid(original) if strict else projection.decode_candidate(original)
    def patch_output(lineage, targets, batch=None):
        canonical_schema = review.patch_schema(targets, support_batch=batch, slots=True)
        value = candidate('repair', lineage['output'], canonical_schema, strict=True)
        return review.decode_patch_slots(value, targets, support_batch=batch)
    codec = staged._read_only_staged(query_schema(scope))
    owner = scope.get('creative_authority')
    delegation = None
    if owner is not None:
        if owner.get('policy') != creative.OWNER_POLICY:
            raise ValueError('Unknown D1 Claim checkpoint policy')
        delegation = creative.compile_envelope(
            attempt, actual, {'context_refs': scope['context_refs']}, mode,
            allow_missing_canonical=origin is not None)
        if owner['envelope'] != delegation:
            raise ValueError('D1 frozen creative sources changed')
    d1_bridge = (creative.OpaqueHeaderBridge(view.codec, codec, delegation)
                 if delegation is not None else None)
    selection_schema = intake_selection(scope, d1_bridge.schema if d1_bridge else view.codec.schema)
    a_message_for = lambda stage, **kw: view_a_message(scope, view, stage, **kw)
    selected = candidate('A-selection', json.loads(checkpoint['wire_originals']['A-selection']),
                         selection_schema, strict=d1_bridge is not None)
    selected_receipt = None
    if admission_enabled(scope):
        original_call = {**checkpoint['capture']['A-selection'],
                         'reply': checkpoint['wire_originals']['A-selection']}
        admitted = selection_admission(scope, original_call, selection_schema,
                                       checkpoint['schema_bindings']['A-selection'])
        if checkpoint['admissions']['A-selection'] != admitted:
            raise ValueError('Frozen selection admission cannot be rebuilt from the original capture')
        selected = require_selection_admission(admitted, scope=scope)
        if read_artifact(root, 'SEMANTIC_A_SELECTION_NORMALIZED.json', MAX_RESULT_BYTES) != admission.canonical_json(selected).encode():
            raise ValueError('Frozen normalized selection differs from original replay')
        selected_receipt = admitted['receipt']
    d1_state = None
    if d1_bridge is not None:
        selected, headers = d1_bridge.decode(selected, d1_bridge.identity)
        d1_state = {'policy': creative.OWNER_POLICY, 'envelope': delegation,
                    'bridge_identity': d1_bridge.identity, 'headers': headers,
                    'conditions': {}, 'a_batch': None}
    else:
        selected = view.codec.decode(selected, view.codec.identity, diagnostic=True)
    detail_plan, binding, detail_messages = frozen_detail_plan(scope, codec, selected,
        checkpoint['capture']['A-selection']['reply_sha256'], view, selected_receipt)
    if checkpoint.get('detail_binding') != binding:
        raise ValueError('Frozen details identity changed')
    for key, message in [('A-selection', a_message_for('A-selection')), *detail_messages.items()]:
        recorded = checkpoint['capture'][key]
        if (recorded['request_sha256'] != hashlib.sha256(message.encode()).hexdigest()
                or recorded['session'] != f"semantic-{scope['attempt_id']}-vnext-{key}"):
            raise ValueError('Frozen staged request cannot be reconstructed')
    d1_batched = (creative.BatchedVisualClaimCarrier(
        codec, selected, delegation, source_bridge_identity=d1_bridge.identity,
        source_codec=view.codec)
        if d1_bridge is not None else None)
    def replay_regenerated_detail(batch):
        key = batch['key']
        entry = checkpoint['stage_regenerations'][key]
        schema = d1_batched.batches[key]
        projection = wire.project(schema, key, atomic_framing=True)
        original_raw = checkpoint['wire_originals'].get(key)
        original_call = checkpoint['capture'].get(key, {})
        used_bindings.add(key)
        if checkpoint['schema_bindings'].get(key) != projection.identity:
            raise ValueError('Frozen regenerated original Schema binding changed')
        if original_raw is None:
            if (original_call.get('reply_sha256') is not None or
                    original_call.get('result') not in ('REQUESTED', 'TRANSPORT_FAILED')):
                raise ValueError('Failed original A-details capture was reinterpreted as a reply')
            evidence = entry.get('original_failure', {}).get('terminal_evidence')
            decision = stage_loop.confirmed_no_tool(evidence, stage=key,
                schema_sha256=structured.request_for(projection.schema)['schemaSha256'],
                session=original_call.get('session'))
            accepted_receipt = {
                'policy': stage_loop.POLICY, 'decision': 'STAGE_REGENERATE',
                'reason': 'TERMINAL_NO_TOOL',
                'terminal_evidence_sha256': authority.digest(decision)}
            diagnostic = {'wire_errors': [], 'original_sha256': None,
                          'terminal_failure_sha256': authority.digest(decision)}
        else:
            if (original_call.get('result') not in ('MODEL_COMPLETED', 'ACCEPTED')
                    or hashlib.sha256(original_raw.encode()).hexdigest()
                    != original_call.get('reply_sha256')):
                raise ValueError('Original failed A-details reply identity changed')
            decision = stage_loop.source_only_failure(original_raw, projection.schema)
            accepted_receipt = admission.classify_details_wire(original_raw, projection.schema,
                binding={'attempt_id': scope['attempt_id'], 'stage': key,
                    'source_sha256': authority.digest(view.codec.references),
                    'schema_binding_sha256': authority.digest(projection.identity)})
            if accepted_receipt['decision'] != 'REJECT':
                raise ValueError('Original invalid source was incorrectly admitted')
            diagnostic = {'wire_errors': projection.errors(staged.StagedProposal.parse_raw(original_raw)),
                          'original_sha256': original_call['reply_sha256']}
        if (decision is None or entry.get('policy') != stage_loop.POLICY
                or entry.get('original_failure') != decision
                or checkpoint['wire_admissions'].get(key) != accepted_receipt
                or checkpoint['wire_diagnostics'].get(key) != diagnostic
                or not isinstance(entry.get('history'), list)
                or not 1 <= len(entry['history']) <= stage_loop.MAX_STAGE_REGENERATIONS):
            raise ValueError('Frozen regenerated A-details original failure changed')
        prior = decision
        for ordinal, history in enumerate(entry['history']):
            identity = stage_loop.recovery_identity(key, prior, ordinal=ordinal,
                frozen_schema_sha256=structured.request_for(projection.schema)['schemaSha256'],
                detail_binding_sha256=authority.digest(binding))
            reservation = reserved_repair('regen:' + key + ':' + str(ordinal), identity)
            expected = {'repair_stage': reservation['key'],
                        'reservation_sha256': reservation['reservation_sha256'],
                        'cause': prior}
            repair_key = reservation['key']
            used_bindings.add(repair_key)
            candidate_projection = wire.project(schema, repair_key, atomic_framing=True)
            if checkpoint['schema_bindings'].get(repair_key) != candidate_projection.identity:
                raise ValueError('Frozen A-details regenerated Schema binding changed')
            message = stage_loop.regeneration_message(
                detail_messages[key], key, prior, ordinal)
            captured = checkpoint['capture'].get(repair_key, {})
            if (captured.get('request_sha256') != hashlib.sha256(
                    review.checked_message(message).encode()).hexdigest()
                    or captured.get('session') != f"semantic-{scope['attempt_id']}-vnext-{repair_key}"):
                raise ValueError('Frozen A-details regenerated request identity changed')
            raw = checkpoint['wire_originals'].get(repair_key)
            if raw is None:
                if (captured.get('reply_sha256') is not None
                        or captured.get('result') not in ('REQUESTED', 'TRANSPORT_FAILED')):
                    raise ValueError('Regenerated missing response was forged')
                failure = stage_loop.confirmed_no_tool(
                    history.get('failure', {}).get('terminal_evidence'),
                    stage=repair_key,
                    schema_sha256=structured.request_for(candidate_projection.schema)['schemaSha256'],
                    session=captured['session'])
                diag = {'wire_errors': [], 'original_sha256': None,
                        'terminal_failure_sha256': authority.digest(failure)}
            else:
                if (captured.get('result') not in ('MODEL_COMPLETED', 'ACCEPTED')
                        or hashlib.sha256(raw.encode()).hexdigest() != captured.get('reply_sha256')):
                    raise ValueError('A-details recovered Tool bytes differ from frozen capture')
                parsed = staged.StagedProposal.parse_raw(raw)
                diag = {'wire_errors': candidate_projection.errors(parsed),
                        'original_sha256': captured['reply_sha256']}
                if not diag['wire_errors']:
                    accepted = candidate(repair_key, parsed, schema, strict=True)
                    expected.update(result='ACCEPT', reply_sha256=captured['reply_sha256'])
                    if (history != expected or entry.get('effective_key') != repair_key
                            or ordinal != len(entry['history']) - 1):
                        raise ValueError('Frozen accepted A-details generation lineage changed')
                    if read_artifact(root, key.replace('A-details-', 'SEMANTIC_A_DETAILS_') +
                            '.json', MAX_RESULT_BYTES).decode() != raw:
                        raise ValueError('A-details materialized artifact is not effective capture')
                    return accepted
                failure = stage_loop.source_only_failure(raw, candidate_projection.schema)
            if failure is None:
                raise ValueError('Frozen non-recoverable A-details cannot enter regeneration')
            if checkpoint['wire_diagnostics'].get(repair_key) != diag:
                raise ValueError('Frozen failed A-details regeneration diagnosis changed')
            expected.update(result='STAGE_REGENERATE', failure=failure)
            if history != expected:
                raise ValueError('Frozen failed regeneration lineage changed: recorded failure or prior identity')
            if entry.get('effective_key') == repair_key:
                raise ValueError('Frozen failed regeneration marked effective')
            prior = failure
        raise ValueError('Frozen regeneration has no accepted effective A-details reply')

    def replay_admitted_detail(batch):
        key = batch['key']
        if key in checkpoint.get('stage_regenerations', {}):
            if d1_batched is None:
                raise ValueError('Regenerated A-details has no frozen D1 authority')
            return replay_regenerated_detail(batch)
        schema = d1_batched.batches[key] if d1_batched is not None else batch['schema']
        raw_text = checkpoint['wire_originals'][key]
        raw = staged.StagedProposal.parse_raw(raw_text)
        if d1_batched is None:
            return candidate(key, raw, schema, strict=False)
        projection = wire.project(schema, key, atomic_framing=True)
        receipt = admission.classify_details_wire(raw_text, projection.schema,
            binding={'attempt_id': scope['attempt_id'], 'stage': key,
                     'source_sha256': authority.digest(view.codec.references),
                     'schema_binding_sha256': authority.digest(projection.identity)})
        if checkpoint['wire_admissions'].get(key) != receipt:
            raise ValueError('Frozen A-details admission receipt differs')
        if receipt['decision'] == 'ACCEPT':
            if key in checkpoint['wire_repairs']:
                raise ValueError('An accepted A-details has a forged repair receipt')
            return candidate(key, raw, schema, strict=True)
        candidate(key, raw, schema, strict=False)  # The original wire errors stay frozen.
        if receipt['decision'] != 'BOUNDED_REPAIR':
            raise ValueError('Unsafe A-details original cannot be repaired on replay')
        identity = {'policy': admission.DETAILS_RECOVERY_POLICY,
                    'stage': key, 'origin_sha256': receipt['original_sha256'],
                    'schema_sha256': receipt['schema_sha256'],
                    'admission_sha256': authority.digest(receipt),
                    'target_path': ['unresolved']}
        reservation = reserved_repair('wire:' + key, identity)
        patch_schema = admission.details_repair_schema(projection.schema)
        message = details_root_repair_message(detail_messages[key], raw_text, key, receipt)
        call = checkpoint['capture'][reservation['key']]
        if (call['request_sha256'] != hashlib.sha256(message.encode()).hexdigest()
                or call['session'] != f"semantic-{scope['attempt_id']}-vnext-{reservation['key']}"):
            raise ValueError('Frozen A-details repair request or session changed')
        patch = staged.StagedProposal.parse_raw(checkpoint['wire_originals'][reservation['key']])
        patch = candidate(reservation['key'], patch, patch_schema, strict=True)
        completed = admission.bind_details_repair(raw, patch, projection.schema)
        receipt_row = {'policy': admission.DETAILS_RECOVERY_POLICY, 'stage': key,
                       'repair_stage': reservation['key'],
                       'reservation_sha256': reservation['reservation_sha256'],
                       'original_reply_sha256': receipt['original_sha256'],
                       'patch_reply_sha256': call['reply_sha256'],
                       'effective_wire_sha256': authority.digest(completed),
                       'admission_sha256': authority.digest(receipt)}
        if checkpoint['wire_repairs'].get(key) != receipt_row:
            raise ValueError('Frozen A-details repaired bytes or decision changed')
        return projection.decode_valid(completed)

    if (not isinstance(checkpoint.get('b_normalizations'), dict)
            or any(not k.startswith('B-') for k in checkpoint['b_normalizations'])):
        raise ValueError('Frozen B normalization identity is invalid')
    if not isinstance(checkpoint.get('stage_regenerations'), dict):
        raise ValueError('Frozen stage regeneration ledger missing')
    if set(checkpoint['stage_regenerations']) - {batch['key'] for batch in detail_plan['batches']}:
        raise ValueError('Frozen unexpected A-details regenerated batch')
    if set(regenerated_repair_keys) != {row['key'] for row in repair_rows
                                       if row['stage'].startswith('regen:')}:
        raise ValueError('Frozen regeneration budget/capture coverage changed')
    details = {batch['key']: replay_admitted_detail(batch)
               for batch in detail_plan['batches']}
    if set(checkpoint.get('wire_admissions', {})) != ({batch['key'] for batch in detail_plan['batches']}
            if d1_batched is not None else set()):
        raise ValueError('Frozen A-details admission stage coverage changed')
    if set(checkpoint.get('wire_repairs', {})) != {row['stage'].removeprefix('wire:')
            for row in repair_rows if row['stage'].startswith('wire:')}:
        raise ValueError('Frozen A-details repaired stage coverage changed')
    if d1_batched is not None:
        value, d1_state['conditions'], d1_state['a_batch'] = d1_batched.merge(details, d1_batched.identity)
        effective_source_keys = {key: checkpoint['stage_regenerations'][key]['effective_key']
                                 for key in checkpoint['stage_regenerations']}
        raw_batches = {key: checkpoint['wire_originals'][effective_source_keys.get(key, key)]
                       for key in details}
        captures = {key: {**checkpoint['capture'][key], 'reply': checkpoint['wire_originals'][key]}
                    for key in {'A-selection', *raw_batches, *effective_source_keys.values()}}
        creative.verify_a_claim_origin(delegation, d1_bridge, d1_batched,
            checkpoint['wire_originals']['A-selection'], raw_batches, captures,
            d1_state['headers'], d1_state['conditions'], effective_batches=details,
            capture_keys=effective_source_keys)
    else:
        value = codec.assemble_batches_candidate(selected, detail_plan, details, repair_missing_leaves=True)
    if value != initial:
        raise ValueError('Frozen assembly cannot be derived from all original batch captures')
    a_keys = ['A-selection', *(batch['key'] for batch in detail_plan['batches'])]
    invalid_a_wire = any(checkpoint['wire_diagnostics'][key]['wire_errors']
                         for key in a_keys if key not in checkpoint['stage_regenerations'])
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
            msg = repair_message(scope, original, targets, context,
                evidence_ref=checkpoint.get('repair_evidence_policy') if checkpoint.get('repair_evidence_policy') in (repair_evidence.POLICY, repair_evidence.LEGACY_POLICY) else False)
            carrier = None
            if delegation is not None:
                creative.verify_a_claim_origin(delegation, d1_bridge, d1_batched,
                    checkpoint['wire_originals']['A-selection'],
                    raw_batches, captures, d1_state['headers'], d1_state['conditions'],
                    effective_batches=details, capture_keys=effective_source_keys)
                if any(t['kind'] in {'complete_obligation', 'visual_choices',
                                     'frozen_visual_coverage', 'confirmed_necessity'} for t in targets):
                    carrier = creative.ExtendedSharedRepairCarrier(
                        delegation, original, targets,
                        d1_state['conditions'], d1_state['headers'])
                    intro, payload = msg.rsplit('\n', 1)
                    msg = review.checked_message(intro +
                        '\n当前 D1 每个视觉修复 value 必须同槽提交 authority Claim；'
                        'Claim 不构成 Creator/Rights 授权。\n' + payload)
            schema = carrier.schema if carrier is not None else correction.patch_schema(
                targets, support_batch=context, slots=True)
            identity = {'stage': stage, 'targets': descriptors(targets),
                        'original_sha256': authority.digest(original),
                        'context_sha256': authority.digest(context),
                        **({'creative_policy': creative.OWNER_POLICY,
                            'claim_state_sha256': authority.digest(d1_state)}
                           if delegation is not None else {})}
            reservation = reserved_repair(stage, identity)
            output = replay_invoke(reservation['key'], msg, schema)
            decoded = candidate(reservation['key'], output, schema, strict=True)
            if carrier is not None:
                result, d1_state['conditions'], d1_state['headers'], evidence = carrier.apply(
                    decoded, carrier.identity)
                d1_state['repair_evidence'] = evidence
                return result, output
            patches = correction.decode_patch_slots(decoded, targets, support_batch=context)
            return correction.apply_patches(original, patches, targets, support_batch=context), output
        replayed = correction.evaluate(initial, scope, view, replay_invoke, candidate, replay_repair,
                                       max_calls=MAX_PLANNING_CALLS, a_calls=binding['a_calls'],
                                       b_identity=checkpoint.get('b_identity_policy') == wire.B_IDENTITY_POLICY,
                                        claim_binding=(lambda directory: bind_d1_d2_review(
                                            directory, envelope=delegation, state=d1_state,
                                            d2_enabled=scope.get('d2_review_policy') == d2.POLICY))
                                        if d1_state is not None else None)
        if d1_state is not None:
            if checkpoint.get('creative_claims') != d1_state:
                raise ValueError('Frozen D1 Claim/Repair cannot be reconstructed from original calls')
        elif 'creative_claims' in checkpoint:
            raise ValueError('D1 Claim policy downgraded on cold replay')
        if scope.get('d2_review_policy') == d2.POLICY:
            actual_proofs = d2.compile_decision_proofs(
                replayed['directory'], replayed['responses'],
                attempt_id=attempt['attempt_id'],
                b_captures={key: raw for key, raw in checkpoint['wire_originals'].items()
                            if key.startswith('B-')})
            if checkpoint.get('d2_decision_proof') != actual_proofs:
                raise ValueError('Frozen D2 DecisionProof differs from original B/Repair capture')
        elif 'd2_decision_proof' in checkpoint:
            raise ValueError('D2 DecisionProof policy downgraded on cold replay')
        for key in ('initial_review_value', 'initial_responses', 'before_semantic', 'repair'):
            if checkpoint.get(key) != replayed[key]:
                raise ValueError('Frozen candidate correction evidence changed: ' + key)
        if (checkpoint.get('candidate_repairs') != replayed['repairs']
                or checkpoint.get('candidate_correction') != replayed['trace']):
            raise ValueError('Frozen candidate reports or full correction lineage changed')
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
        validate_canonical(catalog, value, compiled=True)
        value = proposal.model_dump(mode='json')
        if value != checkpoint['initial_review_value']: raise ValueError('Accepted initial semantics changed')
        directory = review.questions(proposal, inputs, catalog, supported=True, source_bound=True)
        view.check_review(directory)
        batches = review.review_batches(directory)
        originals = checkpoint['initial_responses']
        if len(originals) != len(batches): raise ValueError('Initial review coverage incomplete')
        responses = []
        for index, (response, batch) in enumerate(zip(originals, batches, strict=True)):
            response = candidate(f'B-{index:03}', response, batch['response_schema'])
            response = support.decode_slots(response, batch)
            if lineage and lineage['stage'] == f'B-{index:03}':
                targets = review.answer_targets(response, batch)
                if descriptors(targets) != lineage['targets']: raise ValueError('B repair scope changed')
                patches = patch_output(lineage, targets, batch)
                response = review.apply_patches(response, patches, targets, support_batch=batch)
            elif checkpoint['wire_diagnostics'][f'B-{index:03}']['wire_errors']:
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
            validate_canonical(catalog, value, compiled=True)
        elif targets:
            raise ValueError('Challenged semantics cannot be frozen without a reviewed repair')
        updated = review.questions(proposal, inputs, catalog, supported=True, source_bound=True)
        view.check_review(updated)
        kept, pending = review.recheck(directory, responses, updated)
        if lineage and lineage['stage'] == 'semantic':
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
        if (used_bindings != set(checkpoint['capture'])
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
            **({'raw_artifacts': ['SEMANTIC_A_SELECTION.json',
                                 *(batch['key'].replace('A-details-', 'SEMANTIC_A_DETAILS_') + '.json'
                                   for batch in detail_plan['batches']),
                                 'SEMANTIC_A_ASSEMBLY.json', 'SEMANTIC_INPUT_VIEW.json',
                                  *(['SEMANTIC_A_SELECTION_NORMALIZED.json'] if admission_enabled(scope) else [])]}),
            **({'origin': origin} if origin else {})}
