"""Private director-to-supply projection of an already confirmed plan.

This is not a second PlanDocument and never writes plan/authorization records.
One persisted, bounded interpretation is shared by all configured providers.
"""
from __future__ import annotations

import json
from typing import Literal
from pydantic import Field
from .contracts import Contract, Identifier, PlanDocument, canonical_json
from .model_tasks import ModelTaskError


class VisualIntent(Contract):
    scene_id: Identifier
    query: str = Field(min_length=1, max_length=100, description='简短英文主体/动作词；明确给定Pexels具体视频页时可用规范HTTPS页面URL（options=1），不接收任意媒体URL；不混入导演长说明')
    media_types: list[Literal['image', 'video']] = Field(min_length=1, max_length=2)
    options: int = Field(default=2, ge=1, le=4)
    board_id: Identifier | None = Field(default=None,description='原生图解的scene_id；可在不同叙事场景复用同一图解')
    board_state_indexes: list[int] = Field(default_factory=list,max_length=4,description='所用状态的0起始索引；仅board_id非空时填写')


class SoundCue(Contract):
    cue_id: str = Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]{0,95}$')
    scene_id: Identifier
    query: str = Field(min_length=1, max_length=100)
    at: float = Field(ge=0, le=900, allow_inf_nan=False)
    duration: float = Field(gt=0, le=900, allow_inf_nan=False)
    timing_basis: Literal['absolute', 'scene'] = Field(default='absolute',
        description='absolute保留明确绝对时间；自然定长普通音效用scene，at仅为草稿估计，由剪辑按scene_id的实际画面安排。')
    required: bool = False
    basis: str = Field(min_length=1, max_length=1200)


class MaterialIntent(Contract):
    # Do not silently impose a new scene-count limit on an accepted Plan.
    # Response size is bounded by the model runner; exact scene identity and
    # cardinality are checked against the frozen plan below.
    visuals: list[VisualIntent] = Field(default_factory=list)
    music_query: str | None = Field(default=None, min_length=1, max_length=100)
    sound_cues: list[SoundCue] = Field(default_factory=list, max_length=64)
    unresolved: list[str] = Field(default_factory=list, max_length=16)


def check_intent(intent: MaterialIntent, plan: PlanDocument) -> None:
    scenes = {scene.id for scene in plan.scenes}
    ids = [item.scene_id for item in intent.visuals]
    if set(ids) != scenes or len(ids) != len(scenes):
        raise ModelTaskError('invalid_material_intent', '素材意图必须逐一对应已确认场景，不能增删场景')
    if any(len(set(v.media_types)) != len(v.media_types) or not v.query.strip() for v in intent.visuals):
        raise ModelTaskError('invalid_material_intent', '素材意图的媒体类型或检索词无效')
    boards={b.scene_id:b for b in plan.explainer_boards};covered=set()
    for visual in intent.visuals:
        if visual.board_id is None:
            if visual.board_state_indexes:raise ModelTaskError('invalid_material_intent','图解状态须引用真实board_id')
            continue
        if (visual.board_id not in boards or visual.media_types!=['image'] or not visual.board_state_indexes
            or len(set(visual.board_state_indexes))!=len(visual.board_state_indexes)
            or any(type(i) is not int or not 0<=i<len(boards[visual.board_id].states) for i in visual.board_state_indexes)):
            raise ModelTaskError('invalid_material_intent','图解映射须引用真实board_id及其0起始状态索引，媒体类型为image')
        covered.update((visual.board_id,i) for i in visual.board_state_indexes)
    expected={(b.scene_id,i) for b in plan.explainer_boards for i in range(len(b.states))}
    if covered!=expected:
        raise ModelTaskError('invalid_material_intent','原生图解的全部状态须映射到叙事场景；可跨场景复用，不应另搜相似道具')
    if plan.settings.audio_mode in {'music', 'mixed'} and not (intent.music_query or '').strip():
        raise ModelTaskError('invalid_material_intent', '已确认音乐模式必须保留背景音乐意图')
    if plan.settings.audio_mode not in {'music', 'mixed'} and intent.music_query is not None:
        raise ModelTaskError('invalid_material_intent', '不得在已确认声音模式之外增加背景音乐')
    if plan.settings.audio_mode == 'silent' and intent.sound_cues:
        raise ModelTaskError('invalid_material_intent', '静音方案不能自动增加音效')
    if '本片不使用背景音乐或可选音效' in plan.constraints and (intent.music_query or intent.sound_cues):
        raise ModelTaskError('invalid_material_intent', '本片明确无背景音乐或可选音效，不能增加音轨')
    cue_ids = [cue.cue_id for cue in intent.sound_cues]
    if len(cue_ids) != len(set(cue_ids)):
        raise ModelTaskError('invalid_material_intent', '音效事件身份不能重复')
    for cue in intent.sound_cues:
        if cue.scene_id not in scenes or cue.at + cue.duration > plan.settings.duration_seconds + 1e-6:
            raise ModelTaskError('invalid_material_intent', '音效事件必须属于已确认场景且位于作品时间范围内')
        if not cue.query.strip() or not cue.basis.strip():
            raise ModelTaskError('invalid_material_intent', '音效意图需要明确用途与创作依据')


def check_timing_basis(intent, plan):
    if (plan.narration_policy and plan.narration_policy.duration_mode == 'voice_driven'
            and any(c.timing_basis == 'absolute' for c in intent.sound_cues)):
        raise ModelTaskError('timed_audio_requires_fixed_duration',
            '自然定长不能冻结草稿估计的音效秒数。普通画面动作音效应使用scene；'
            '确有不可移动的绝对事件须保留absolute并等待调整方案，不能移动原声或固定事件。')


def check_timing_repair(candidate, original, plan):
    """Only a director's explicit timing-coordinate correction is admissible."""
    check_intent(candidate, plan)
    before=original.model_dump(mode='json');after=candidate.model_dump(mode='json')
    if len(after['sound_cues']) != len(before['sound_cues']):
        raise ValueError('时间分类修正不能增删音效')
    for old,new in zip(before['sound_cues'],after['sound_cues']):
        new['timing_basis']=old['timing_basis']
    if after != before:
        raise ValueError('仅可修正timing_basis，不能改素材查询、场景、时间估计、声音用途或必需性')


def fixed_visual_intent(plan: PlanDocument, context) -> MaterialIntent | None:
    """No semantic call is needed for a silent work fully covered by mandatory inputs."""
    if plan.settings.audio_mode != 'silent':
        return None
    inputs = {item['input_id']:item for item in context.inputs if item.get('usage')=='must_use'
              and item.get('kind') in {'image','video'}}
    visuals=[]
    boards={b.scene_id for b in plan.explainer_boards}
    for scene in plan.scenes:
        if scene.id in boards:
            board=next(b for b in plan.explainer_boards if b.scene_id==scene.id)
            visuals.append(VisualIntent(scene_id=scene.id,query='native schematic',media_types=['image'],options=1,
                board_id=scene.id,board_state_indexes=list(range(len(board.states)))))
            continue
        kinds=sorted({inputs[id]['kind'] for id in scene.required_input_ids if id in inputs})
        if not kinds:
            return None
        # This label is never an external query: every scene already has a
        # fixed visual input. The complete creative plan stays in context.
        visuals.append(VisualIntent(scene_id=scene.id,query='已确认的必用视觉素材',
                                    media_types=kinds,options=1))
    return MaterialIntent(visuals=visuals)


class FrozenIntentCompiler:
    def __init__(self, planning):
        self.planning = planning

    async def prepare(self, ctx, plan: PlanDocument):
        context = self.planning.context(ctx)
        context_hash = context.fingerprint
        with ctx.store.connection() as reader:
            payload = json.loads(reader.execute('SELECT payload_json FROM tasks WHERE id=?', (ctx.task_id,)).fetchone()[0])
        saved = payload.get('material_intent')
        if saved is not None:
            if payload.get('material_intent_context_hash') != context_hash:
                raise ModelTaskError('material_context_changed', '已保存素材意图的冻结上下文已变化，不能复用或自动重发')
            intent = MaterialIntent.model_validate(saved)
        else:
            intent = fixed_visual_intent(plan,context)
            if intent is None:
                def checked(candidate):
                    try:
                        check_intent(candidate,plan)
                        check_timing_basis(candidate,plan)
                    except ModelTaskError as exc:raise ValueError(exc.user_message) from None
                # One extra bounded correction is allowed for this private
                # projection. Recorded receipts from earlier attempts replay;
                # only the new correction round can issue another MODEL call.
                intent = await self.planning.runner(ctx, namespace='material-intent-v1',
                    max_format_repairs=2).run(context,
                    '仅把已确认方案翻译成素材检索意图，不重写方案。每个场景给一个visuals项，query最多100字；'
                    'visuals.query使用简短英文主体和关键动作（如 using phone in bed、eating while using phone、putting phone down），不要把中文导演说明、许可条款、灯光和构图整段塞进搜索词；必须保留方案要求的核心物件及动作。'
                    '媒体类型根据冻结创作需求选择，options为有限候选数。music/mixed必须给music_query，其余为null。'
                    'music_query使用1至3个核心英文流派或乐器关键词（如ambient、acoustic guitar）；不要堆叠情绪形容词、逗号或no vocals等混音要求，完整声音意图仍保留在方案中供选材。'
                    '需要真实动作和场景连续性的镜头优先检索video，资料证据或静物关系适合时再用image；'
                    '不要把比喻或抽象判断按字面变成无关道具查询。'
                    '按冻结visual语义将explainer_boards的状态映射到对应段落：每段仍给一个visuals，图解段设置board_id为图解scene_id、board_state_indexes为0起始状态索引，media_types=[image]、query=native schematic、options=1；'
                    '同一图解可以跨多个段落使用、回看或复用某状态，不要求所有状态挤在图解定义的单个场景内；每个已定义状态至少在一处展示。图解段不搜索相似道具，其余段落照常给真实库存查询。'
                    '自然定长的普通装饰音效使用timing_basis=scene，跟随scene_id实际画面；明确绝对时间事件使用absolute，不得挪动原声或固定事件。'
                    'sound_cues按本片实际需要提出：给稳定cue_id、已知scene_id、全片时间at/duration、query和basis。'
                    '音效query必须是方便Wikimedia Commons检索的简短英文关键词（如room tone、keyboard typing、city traffic、mouse click）；'
                    'basis必须明确中文声音用途和与实际画面动作的对应依据，后续仍要实际试听及Rights核验。'
                    '只有Creator逐项明确指定不可省略，或缺失会改变核心信息含义的声音才required=true；泛称有音效不代表每个拟定动作声都必需。普通动作点缀默认可省略，不为凑数量塞入无关声音。方案中因导演建议出现的环境声、'
                    '按需点缀或交互反馈全部required=false，缺合法候选时可省略，不得把建议变成强制素材。'
                    '不需要的音效不要提出。'
                    '静音方案禁止音效；固定旁白不交由图库替代。结合完整画像、导演风格、事实、禁区和适配许可，'
                    '不把候选或文字意图称作已看过/听过素材。具体候选、许可证、署名、混音与音效动作匹配'
                    '本来就由后续供料、绑定和审片验证，不能在检索前把这些待执行工作写成阻断问题；'
                    '仅将需要 Creator 提供、在当前冻结方案中确实缺失的创作信息列入unresolved。', MaterialIntent,validate_result=checked, expression_role="visual")
            check_intent(intent, plan)
            with ctx.transaction() as writer:
                current = json.loads(writer.execute('SELECT payload_json FROM tasks WHERE id=?', (ctx.task_id,)).fetchone()[0])
                if current.get('material_intent') is not None and (
                        current.get('material_intent_context_hash') != context_hash or current['material_intent'] != intent.model_dump(mode='json')):
                    raise ModelTaskError('material_context_changed', '并发素材意图发生冲突，保留原结果')
                current.update(material_intent=intent.model_dump(mode='json'), material_intent_context_hash=context_hash)
                writer.execute('UPDATE tasks SET payload_json=? WHERE id=?', (canonical_json(current), ctx.task_id))
                ctx.store.append_event(writer, ctx.work_id, 'material_intent_prepared',
                    {'scene_count': len(intent.visuals), 'sfx_count': len(intent.sound_cues), 'context_hash': context_hash}, run_id=ctx.run_id)
        check_intent(intent, plan)
        check_timing_basis(intent, plan)
        # An intent projection cannot pre-emptively decide that actual assets/rights are
        # unavailable: finding candidates and checking licenses are Supply's job.
        # Keep model uncertainty in the persisted projection and trace it, but let
        # downstream qualified supply / Rights / binding gates decide real gaps.
        if intent.unresolved:
            with ctx.transaction() as writer:
                ctx.store.append_event(writer, ctx.work_id, 'material_intent_deferred_notes',
                    {'count': len(intent.unresolved), 'verification': 'supply_and_binding'}, run_id=ctx.run_id)
        return intent, context


    async def repair_audio_timing(self, ctx, context, records):
        """Repair a known projection mistake, reusing every acquired file and voice.

        The original intent and MODEL receipt remain unchanged. Only this run's
        unrendered material-use bindings may change, after a recorded decision.
        """
        from dataclasses import replace
        from .service import row, encode
        plan=PlanDocument.model_validate(context.plan)
        metadata={r['id']:json.loads(r['metadata_json']) for r in records}
        if any(m.get('original_audio') for m in metadata.values()):
            raise ModelTaskError('timed_audio_requires_fixed_duration','受保护原声不能通过音效分类修正移动')
        with ctx.store.connection() as conn:
            source=conn.execute("SELECT payload_json FROM tasks WHERE run_id=? AND kind='supply' AND plan_revision=?",(ctx.run_id,ctx.plan_revision)).fetchone()
        saved=json.loads(source[0]).get('material_intent') if source else None
        if saved is None:
            raise ModelTaskError('timed_audio_requires_fixed_duration','缺少本运行原素材意图，不能推断固定事件可移动')
        original=MaterialIntent.model_validate(saved)
        ids={c.cue_id for c in original.sound_cues}
        with ctx.store.connection() as conn:
            if conn.execute("SELECT 1 FROM artifacts WHERE run_id=? AND kind='edit_project'",(ctx.run_id,)).fetchone():
                raise ModelTaskError('timed_audio_requires_fixed_duration','已有剪辑工程的音效时间绑定不能在原记录上改写')
        if any(r['run_id']!=ctx.run_id or u.get('cue_id') not in ids
               for r in records for u in metadata[r['id']].get('material_uses',[])
               if u.get('role')=='sfx' and u.get('timing_basis','absolute')=='absolute'):
            raise ModelTaskError('timed_audio_requires_fixed_duration','历史或未登记的固定事件不能自动修正')
        view=replace(context,editor_view=True,artifacts=({'material_intent':saved},))
        answer=await self.planning.runner(ctx,namespace='sfx-timing-repair-v1',max_format_repairs=1).run(
            view,'原素材意图把部分普通动作音效标为absolute，导致已确认voice_driven剪辑被阻断。'
            '只核对本期真实依据并修正timing_basis：scene跟随实际场景动作，at是规划估计；absolute只用于不可移动的明确绝对事件。'
            '所有其他字段逐项保留，不增删音效、不改查询、用途、时间估计或素材，不重配旁白。'
            '若方案确实要求绝对事件，必须保留absolute，程序会停止等待调整方案；不能为了通过而降级原声或固定事件。',
            MaterialIntent,validate_result=lambda candidate:check_timing_repair(candidate,original,plan),expression_role='visual')
        check_timing_basis(answer,plan)
        timing={c.cue_id:c.timing_basis for c in answer.sound_cues}
        changed=[]
        with ctx.transaction() as conn:
            operation=conn.execute("SELECT id FROM operations WHERE task_id=? AND kind='MODEL' AND state='succeeded' ORDER BY created_at DESC,id DESC LIMIT 1",(ctx.task_id,)).fetchone()
            if not operation:raise ModelTaskError('timing_repair_missing','缺少已知模型修正回执')
            if conn.execute("SELECT 1 FROM artifacts WHERE run_id=? AND kind='edit_project'",(ctx.run_id,)).fetchone():
                raise ModelTaskError('material_binding_invalid','剪辑工程已建立，不能改写时间绑定')
            for record in records:
                meta=metadata[record['id']];altered=False
                for use in meta.get('material_uses',[]):
                    if use.get('role')=='sfx' and use.get('cue_id') in timing and use.get('timing_basis','absolute')!=timing[use['cue_id']]:
                        use['timing_basis']=timing[use['cue_id']];changed.append(use['cue_id']);altered=True
                if not altered:continue
                current=row(conn,'artifacts',record['id'])
                if current['run_id']!=ctx.run_id or current['metadata_json']!=record['metadata_json']:
                    raise ModelTaskError('material_binding_invalid','音效绑定已变化，保留原结果')
                record['metadata_json']=encode(meta)
                conn.execute('UPDATE artifacts SET metadata_json=? WHERE id=?',(record['metadata_json'],record['id']))
            ctx.store.append_event(conn,ctx.work_id,'sound_timing_corrected',
                {'operation_id':operation['id'],'cue_ids':sorted(set(changed)),
                 'scope':'only timing_basis; original intent, receipts, files and voice unchanged'},run_id=ctx.run_id)
        return records
