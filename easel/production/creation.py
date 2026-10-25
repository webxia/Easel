"""Business handlers for edit -> durable render -> technical and semantic review."""
from __future__ import annotations
import asyncio
from dataclasses import replace
import json
from pathlib import Path
from pydantic import Field, ValidationError, model_serializer
from .contracts import Contract
from .editors import AssetManifest, MediaAsset, Scene, AudioClip, Caption, EditProject, FFmpegEditor, EditError
from .artifacts import register_file, artifact_file
from .inspection import observe_media
from .model_tasks import ModelTaskError
from .errors import ProductionError
from .service import row,encode,now,new_id
from .material_binding import validate_material_records, validate_audio_bindings, selected_asset_ids, fit_sound_effects
from .creative_captions import CreativeCaption, compile_captions, check_caption_layout


from .edit_observation import VisualSelection, check_visual_evidence, VISUAL_EVIDENCE_INSTRUCTION


class CreativeEdit(Contract):
    scenes: list[Scene] = Field(min_length=1)
    visual_evidence: list[VisualSelection] = Field(default_factory=list, max_length=128)
    audio: list[AudioClip] = Field(default_factory=list)
    captions: list[CreativeCaption] = Field(default_factory=list)
    required_features: list[str] = Field(default_factory=list)
    # Director's explicit gap report is not part of an executable timeline.
    unresolved_scene_ids: list[str] = Field(default_factory=list, max_length=1000, exclude=True)

    @model_serializer(mode='wrap')
    def serialize_evidence(self, handler):
        data = handler(self)
        if not self.visual_evidence:
            data.pop('visual_evidence', None)
        return data


class SemanticReview(Contract):
    suggestions: list[str] = Field(default_factory=list, max_length=16, description='非阻断的审美或表达建议；不能用于隐藏事实错误、明确要求冲突或已证实质量缺陷')
    verdict: str = Field(pattern='^(pass|fail|partial)$')
    factual_fidelity: str = Field(min_length=1)
    style_consistency: str = Field(min_length=1)
    narrative_coherence: str = Field(min_length=1)
    audiovisual_alignment: str = Field(min_length=1)
    findings: list[str]
    limitations: list[str]


def align_editor_frames(answer: CreativeEdit, *, fps: int = 30) -> CreativeEdit:
    """Quantize cumulative edit boundaries, avoiding per-clip rounding drift.

    Every resulting edit boundary stays within half a frame of the native
    timeline. Scene identities, order, source offsets and transitions remain
    unchanged; no collapsed scene or invented duration is accepted.
    """
    if fps not in (24, 25, 30):
        raise ValueError('unsupported output frame rate')
    aligned=[]; previous_seconds=0.0; previous_frame=0
    for scene in answer.scenes:
        previous_seconds += scene.duration - scene.transition_seconds
        end_frame=round(previous_seconds*fps)
        overlap=round(scene.transition_seconds*fps)/fps
        duration=(end_frame-previous_frame)/fps+overlap
        if duration<=overlap:
            raise ModelTaskError('edit_frame_alignment_conflict','镜头短于可表示的视频帧，不能删掉镜头')
        if ((scene.transition=='cut') != (overlap==0)) or overlap<0:
            raise ModelTaskError('edit_frame_alignment_invalid','转场不满足严格时间合同')
        if (abs(end_frame/fps-previous_seconds)>0.5/fps+1e-8
                or abs(overlap-scene.transition_seconds)>0.5/fps+1e-8
                or abs(duration-scene.duration)>1.5/fps+1e-8):
            raise ModelTaskError('edit_frame_alignment_invalid','镜头边界修正超出帧精度')
        aligned.append(scene.model_copy(update={'duration':duration,'transition_seconds':overlap}))
        previous_frame=end_frame
    end = previous_frame / fps
    # A background bed may round its endpoint to fewer decimal places than
    # the frame timeline. Trim only subframe excess; never touch speech/SFX.
    audio = [clip.model_copy(update={'duration':end-clip.at})
             if clip.role=='music' and clip.at<end and 1e-6<clip.at+clip.duration-end<=.5/fps+1e-8
             else clip for clip in answer.audio]
    return answer.model_copy(update={'scenes':aligned,'audio':audio})


def compensate_edit_overlap(answer: CreativeEdit, *, target_seconds: float, fps: int = 30) -> CreativeEdit:
    """Compile model's per-scene screen slots into physical source clip lengths.

    If the model summed its scene durations to the film duration but then also
    specified dissolves, adding the same transition frames to each involved
    clip preserves all intended screen slots and makes the actual overlapped
    timeline equal the confirmed duration. Never remove, invent or enlarge a
    dissolve; never fix an otherwise inconsistent total.
    """
    requested_frames = round(target_seconds * fps)
    scenes = answer.scenes
    rendered_frames = round(sum(s.duration - s.transition_seconds for s in scenes) * fps)
    raw_frames = round(sum(s.duration for s in scenes) * fps)
    if rendered_frames == requested_frames:
        return answer
    if raw_frames != requested_frames or rendered_frames > requested_frames:
        raise ModelTaskError('edit_duration_mismatch','分镜时长或转场无法落实到确认总片长')
    # Keep native slot boundaries until align_editor_frames quantizes the
    # cumulative timeline. Per-shot rounding would reintroduce frame drift.
    corrected = [s.model_copy(update={'duration': s.duration + s.transition_seconds})
                 for s in scenes]
    return answer.model_copy(update={'scenes':corrected})

def check_edit_source_bounds(answer, durations, *, target_seconds, fps=30):
    """Validate the compiled source intervals inside existing model repair rounds."""
    try:
        compiled=align_editor_frames(compensate_edit_overlap(answer,target_seconds=target_seconds,fps=fps),fps=fps)
    except ModelTaskError as exc:
        if exc.code not in {'edit_duration_mismatch','edit_frame_alignment_conflict','edit_frame_alignment_invalid'}:
            raise
        from .model_tasks import ResultCorrectionError
        actual=sum(s.duration-s.transition_seconds for s in answer.scenes)
        raw=sum(s.duration for s in answer.scenes)
        raise ResultCorrectionError(f'{exc.user_message}；确认总片长{target_seconds:.6f}秒，'
            f'当前镜头合计{raw:.6f}秒、扣除转场后{actual:.6f}秒。'
            '调整镜头时长或转场，不修改、截短或变速原旁白。') from None
    for scene in compiled.scenes:
        available=durations.get(scene.asset_id)
        if available is not None and scene.source_start+scene.duration>available+0.5/fps:
            raise ValueError(f'镜头 {scene.scene_id} 取源区间 {scene.source_start:.3f}–'
                f'{scene.source_start+scene.duration:.3f} 秒超过素材实际长度 {available:g} 秒；'
                f'编译后实际取源长度为{scene.duration:.3f}秒（已包含转场补偿），'
                f'保持此长度时起点最多为{max(0,available-scene.duration):.3f}秒；'
                '调整取源位置或重新分配镜头，保持确认总时长；不能循环、定格或截短旁白。')


def project_editor_features(answer: CreativeEdit) -> tuple[CreativeEdit,list[str]]:
    """Separate supported engine capability flags from model commentary.

    Unrecognized model strings are never passed to FFmpeg as fake capabilities
    or declared fulfilled. They remain explicit unverified review obligations
    attached to the internal preview artifact and its model receipt.
    """
    from .editors.ffmpeg import FEATURES
    if answer.unresolved_scene_ids or any(note.startswith('PENDING_VISUAL_MATCH') for note in answer.required_features):
        raise ModelTaskError('visual_material_gap','导演已确认画面不能落实方案；请补充对应素材，不能用无关画面继续渲染')
    if len(answer.required_features)>64 or any(
            not isinstance(note,str) or not note or len(note)>600
            for note in answer.required_features):
        raise ModelTaskError('invalid_editor_features','剪辑模型能力声明超出有界检查范围')
    declared=list(dict.fromkeys(x for x in answer.required_features if x in FEATURES))
    unverified=list(dict.fromkeys(x for x in answer.required_features if x not in FEATURES))
    return answer.model_copy(update={'required_features':declared}),unverified

class CreationTasks:
    def __init__(self,service,planning,editor=None,voice_tasks=None,manual_review_only=False,visual_review=False,supply=None,review_planning=None):
        self.service,self.planning=service,planning
        self.review_planning=review_planning or planning
        self.supply=supply
        self.voice_tasks=voice_tasks
        # Temporary, explicitly enabled S6-14 release policy. Do not claim the
        # absent semantic inspection passed or accept a Creator output here.
        self.manual_review_only=manual_review_only
        self.visual_review=visual_review
        self.editor=editor or FFmpegEditor(service.outputs/'_production'/'renders')

    def assets(self,ctx,ids):
        with self.service.store.connection() as conn:
            records=[row(conn,'artifacts',id) for id in ids]
        for item in records:
            if item['work_id']!=ctx.work_id or item['kind'] not in {'image','video','audio','font'}:
                raise ModelTaskError('invalid_asset','素材不属于当前作品或类型不可用')
            try:
                artifact_file(self.service,item)
            except (ValueError,OSError):
                raise ModelTaskError('invalid_asset','所引用素材已删除或发生变化，已保留其余成果') from None
        validate_material_records(self.service,ctx,records)
        manifest=AssetManifest(root=self.service.outputs,assets={r['id']:MediaAsset(locator=r['storage_ref'],sha256=r['digest'],kind=r['kind']) for r in records})
        return records,manifest

    async def supplement_visuals(self,ctx,context,answer,asset_ids):
        """One existing stock-repair pass; no Plan, voice or generation restart."""
        gaps=list(dict.fromkeys(answer.unresolved_scene_ids))
        if (not self.supply or not gaps or len(gaps)>4 or
                not set(gaps)<={s['id'] for s in context.plan['scenes']}):
            raise ModelTaskError('visual_material_gap','未落实镜头：'+','.join(gaps)+'；保留已有方案、素材与旁白，尚未渲染')
        from .material_intent import MaterialIntent
        def check(intent):
            ids=[v.scene_id for v in intent.visuals]
            if (set(ids)!=set(gaps) or len(ids)!=len(gaps) or intent.music_query or
                    intent.sound_cues or intent.unresolved or
                    any(v.board_id or v.board_state_indexes for v in intent.visuals)):
                raise ValueError('只为已报告的缺口镜头提出库存检索；不能扩大场景、音乐、图解或生成范围')
        intent=await self.planning.runner(ctx,namespace='edit-stock-intent-v1',max_format_repairs=2).run(
            context,'只为以下已观察到的画面缺口提出一次局部库存补料词，复用其余素材和旁白。'
            'visuals逐一对应缺口scene_id，query为简短英文主体/动作，options最多4；不生成媒体、不改方案。'
            +encode({'unresolved_scene_ids':gaps,'visual_evidence':[v.model_dump() for v in answer.visual_evidence]}),
            MaterialIntent,validate_result=check, expression_role="visual")
        ids=await asyncio.to_thread(self.supply.revision_visuals,ctx,[v.model_dump(mode='json') for v in intent.visuals])
        return list(dict.fromkeys([*asset_ids,*ids]))

    async def edit(self,ctx,*,_stock_assets=None):
        from .worker import TaskResult
        try:
            # A new compiler namespace may not bypass unresolved old calls.
            with self.service.store.connection() as conn:
                if conn.execute("SELECT 1 FROM operations WHERE task_id=? AND state IN ('reserved','sending','submitted','unknown')",(ctx.task_id,)).fetchone():
                    raise ModelTaskError('result_unknown','剪辑存在未确定的调用，保留原请求，不能另行提交')
            context=self.planning.context(ctx)
            if ctx.payload.get('reuse_existing_media_only'):
                context=replace(context,brief=context.brief+'\n本次恢复只用已有素材和配音修正原剪辑，不重新获取或生成媒体；不足时如实说明。')
            asset_ids=ctx.payload.get('asset_ids',[]) if _stock_assets is None else _stock_assets
            if self.voice_tasks and not ctx.payload.get('reuse_existing_media_only'):
                asset_ids,outcome=await self.voice_tasks.prepare_assets(ctx,context.plan,asset_ids)
                if outcome:return outcome
            records,manifest=self.assets(ctx,asset_ids)
            from .narration import measured_execution_plan, check_voice_schedule, aligned_captions, narration_segments, ENDING_INSTRUCTION
            execution_plan, timing = measured_execution_plan(context.plan, records)
            if timing:
                context = replace(context, plan=execution_plan,
                    brief=context.brief + ('\n本片按真实旁白定长，遵守实测音轨位置：' if timing['mode']=='voice_driven' else
                        '\n本片保持确认的固定总时长；以下是真实旁白长度与可靠字幕锚点，音轨位置仅为建议。按实际讲述安排核心画面，留白须有动作、阅读或叙事用途，不为凑时长堆积空镜。不能改写旁白、拉伸字幕或改声音参数；无法落实时如实报告未落实场景：') + encode(timing))
            context=replace(context,editor_view=True,artifacts=tuple({'asset_id':r['id'],'kind':r['kind'],'metadata':json.loads(r['metadata_json'])} for r in records),allowed_handles=context.allowed_handles|frozenset(manifest.assets))
            observations=[];required={'text','structured'};observed={};source_durations={}
            # M3.1 accepts visual frames but not input_audio. Measured local
            # acoustic properties may support an EDIT PREVIEW; they do not
            # substitute for a Director actually listening or for final QC.
            audio_native=bool(self.planning.transport and 'audio' in self.planning.transport.capabilities)
            if not audio_native and any(item['usage']=='must_use' and
                    item.get('constraints',{}).get('original_audio') for item in context.inputs):
                raise ModelTaskError('capability_unavailable',
                    '必用原声必须由真实支持听音频的服务校验，不能用技术测量替代')
            for record in records:
                if record['kind']=='font':continue
                path=artifact_file(self.service,record)
                media,needs,evidence=await asyncio.to_thread(observe_media,path,
                    include_audio=audio_native and record['kind'] in {'video','audio'},max_frames=4)
                observed[record['id']]=evidence.get('frame_times',[])
                if record['kind']=='audio' and any(u.get('role')=='sfx' for u in json.loads(record['metadata_json']).get('material_uses',[])):
                    from .media import probe_media
                    source_durations[record['id']]=(await asyncio.to_thread(probe_media,path))['duration']
                if record['kind']=='video':
                    from .media import probe_media
                    source_durations[record['id']]=(await asyncio.to_thread(probe_media,path))['duration']
                    observations.append({'type':'text','text':f"素材 {record['id']} 实测可用长度 {source_durations[record['id']]} 秒；取源结束点不得超出，转场重叠也需留足源帧。"})
                observations.append({'type':'text','text':'候选素材句柄 '+record['id']})
                observations.extend(media);required.update(needs)
                if not audio_native and record['kind'] in {'video','audio'}:
                    from .inspection import observe_audio_technical
                    measured=await asyncio.to_thread(observe_audio_technical,path)
                    observations.append({'type':'text','text':
                        '本地FFmpeg技术测量，模型未听取该素材声音。不能据此推断音乐风格、听感、歌词或SFX动作匹配。'
                        +json.dumps(measured,ensure_ascii=False)})
            from .contracts import SubtitleSettings
            style=SubtitleSettings.model_validate(context.plan['settings'].get('subtitles',{}))
            fonts={json.loads(r['metadata_json']).get('font_name'):r['id'] for r in records if r['kind']=='font'}
            font_paths={r['id']:artifact_file(self.service,r) for r in records if r['kind']=='font'}
            horizontal=context.plan['settings']['aspect_ratio']=='16:9'
            def check_measured_edit(candidate):
                from .editors.base import check_timeline_identities, check_audio_delivery
                check_timeline_identities(candidate.scenes,candidate.audio,candidate.captions)
                check_audio_delivery(context.plan['settings']['audio_mode'],candidate.scenes,candidate.audio)
                check_edit_source_bounds(candidate,source_durations,target_seconds=context.plan['settings']['duration_seconds'])
                check_visual_evidence(align_editor_frames(compensate_edit_overlap(candidate,
                    target_seconds=context.plan['settings']['duration_seconds'])),observed)
                # Same binding rules as final project validation, inside the
                # existing bounded model correction loop, after source fitting.
                from .material_binding import AUDIO_EDIT_ERRORS
                try:
                    compiled=align_editor_frames(compensate_edit_overlap(candidate,
                        target_seconds=context.plan['settings']['duration_seconds']))
                    compiled=compiled.model_copy(update={'audio':fit_sound_effects(compiled.audio,source_durations)})
                    validate_audio_bindings(compiled,records)
                    compiled_edit=compiled
                except ModelTaskError as exc:
                    if exc.code not in AUDIO_EDIT_ERRORS:raise
                    from .model_tasks import ResultCorrectionError
                    raise ResultCorrectionError(exc.user_message) from None
                from .boards import check_board_usage
                check_board_usage(candidate.scenes,records,overlays=[c for c in candidate.captions if c.role=='overlay'])
                if timing and timing['mode']=='voice_driven' and any('role' not in c.model_fields_set for c in candidate.captions):
                    raise ValueError('必须明确每条文字的role：narration为旁白字幕，overlay为独立解释字')
                try:
                    compiled=compile_captions(candidate.captions,style=style,fonts=fonts,
                        aligned=aligned_captions(candidate.audio,records) if style.enabled and (context.plan.get('narration_policy') or {}).get('continuous') else None,
                        font_paths=font_paths,width=1920 if horizontal else 1080,height=1080 if horizontal else 1920)
                    check_caption_layout(compiled,font_paths=font_paths,
                        width=1920 if horizontal else 1080,height=1080 if horizontal else 1920)
                    EditProject(work_id=ctx.work_id,plan_revision=ctx.plan_revision,revision=1,
                        width=1920 if horizontal else 1080,height=1080 if horizontal else 1920,
                        duration=context.plan['settings']['duration_seconds'],
                        audio_mode=context.plan['settings']['audio_mode'],scenes=compiled_edit.scenes,
                        audio=compiled_edit.audio,captions=compiled)

                except EditError as exc:
                    raise ValueError(str(exc)) from None
                if not timing or timing['mode']=='fixed':
                    return
                check_voice_schedule(candidate.audio, records, timing)
                actual = sum(s.duration - s.transition_seconds for s in candidate.scenes)
                raw = sum(s.duration for s in candidate.scenes)
                if min(abs(actual - timing['duration']), abs(raw - timing['duration'])) > .04:
                    raise ValueError('分镜必须按实测成片长度编排：' + str(timing['duration']))
                if candidate.unresolved_scene_ids:
                    raise ValueError('仍有未落实场景：' + ','.join(candidate.unresolved_scene_ids))
            from .edit_observation import edit_observation_tools
            observation_tools = (edit_observation_tools({r['id']: artifact_file(self.service,r)
                for r in records if r['kind']=='video'},observed)
                if self.planning.transport and 'tools' in self.planning.transport.capabilities else ())
            recovery=None
            namespace='edit-source-bounds-v1' if _stock_assets is None else 'edit-stock-selection-v1'
            if ctx.payload.get('edit_recovery_source') and _stock_assets is None:
                with self.service.store.connection() as conn:
                    source=dict(row(conn,'operations',ctx.payload['edit_recovery_source']))
                if (source['task_id']!=ctx.task_id or source['work_id']!=ctx.work_id or source['run_id']!=ctx.run_id
                        or source['state']!='succeeded' or source['kind']!='MODEL'
                        or source['config_version']!=self.planning.config_version
                        or any(source[k]!=v for k,v in self.planning.model_service.items())):
                    raise ModelTaskError('edit_recovery_invalid','剪辑修正来源与当前已知回执不符，未发起调用')
                request=json.loads(source['request_json'])
                message=json.loads(source['receipt_json'])['result']['message']
                if request['schema'].get('title')!='CreativeEdit' or message.get('tool_calls'):
                    raise ModelTaskError('edit_recovery_invalid','剪辑修正来源不是已返回的剪辑结果')
                # These tool replies are the actual observed frames sent in the
                # known request, not model-authored visual claims.
                for m in request['messages']:
                    if m.get('role')!='tool':continue
                    try:evidence=json.loads(m['content'])
                    except (ValueError,TypeError):continue
                    if isinstance(evidence,dict) and evidence.get('asset_id') in source_durations:
                        observed.setdefault(evidence['asset_id'],[]).extend(evidence.get('frame_times',[]))
                recovery=(request['messages'],message)
                namespace='edit-repair-'+source['id'][:32]
            answer=await self.planning.runner(ctx,namespace=namespace,max_format_repairs=2).run(context,
                ENDING_INSTRUCTION + VISUAL_EVIDENCE_INSTRUCTION + '已有抽样不能确认关键动作或入出点时，可用inspect_media复查候选指定时间；工具只读，不把未观察的区间当已验证。'
                '把已确认方案落实为精确剪辑时间线。只能使用给定素材句柄；逐场景决定裁剪、运动、转场、音轨和字幕。时长须精确，旁白与原声不能循环。缺素材不能用无关素材替代；无法落实的场景必须列入unresolved_scene_ids，不得把缺口藏在required_features中再输出概念替代片。字幕必须有真实字体素材。文字x/y表示整块文字的中心坐标，不是左上角；资料说明放在边缘时，按实际字体宽高预留空间。对metadata.material_uses里的音效事件，以cue_id作为AudioClip.clip_id，role=sfx；timing_basis=scene时按scene_id对应实际镜头安排音效，拆镜保留原场景ID或使用原场景ID-cut数字/原场景ID_数字；音效可跨同场景连续镜头，但不能跨到其他场景或越过场景窗口，at仅为草稿估计；absolute或未指定时保留at。duration是事件上限，短音效按实际源长播放，不循环凑长；required事件不得省略，可选事件可以省略。音乐/旁白/音效不得互换用途。'
                '连续旁白应跨镜头讲完；voice_driven严格遵守voice_schedule，fixed使用实测时间作安排依据、位置可按叙事调整，不按草稿分镜凑静默；'
                '字幕短行分语义显示，不能将整段连续旁白一次堆在画面上。选择画质与景别适合、光线与动作相接的素材，'
                '每条文字明确role：narration只显示旁白并继承频道字幕样式；overlay为独立解释文字，保留设计的字体、位置、字号，避开底部旁白区，不能叠字。'
                '同时查看素材画面里原有的字幕、标题和图表文字；避开口播字幕区域，必要时换片段、调整构图或移开独立解释字，不要在已有文字上重复叠字。'
                'material_uses含board_id的图解素材是已确认的连续状态：首次出现按board_frame_index顺序，应使必要类别、数量和关系可理解，不强制每态全幅，允许有意义的特写；'
                '同一图解可跨段落复用、回看或加局部特写，board_scene_ids是本次素材映射提示，图解定义所在的scene_id不是排他的使用限制。'
                '原生图解已为标题、分组、卡片和底部字幕留白；优先展示可读全貌与已规划状态高亮，不用机械推拉或截断邻近文字来制造变化。图解已画出标题、卡片、类别和假设/概念标识，不要只剩裁切而失去全貌，避免重复叠同义解释字；有必要时可以安排不遮挡证据的补充标注。'
                '避免同义空镜反复堆积，旁白说到具体关系时应让画面或必要字幕提供相应信息。'
                '如果输入中只有音轨技术证据，没有真实听觉观察，只能提供未试听的剪辑预览方案，不能声称已听过音频、确认了音乐情绪或音画同步；可选SFX不确定就省略，最终音画语义审核必须另行通过。',CreativeEdit,media=tuple(observations),required=frozenset(required),tools=observation_tools,validate_result=check_measured_edit,recovery=recovery, expression_role="visual")
            if answer.unresolved_scene_ids:
                if _stock_assets is None and self.supply and not ctx.payload.get('reuse_existing_media_only'):
                    ids=await self.supplement_visuals(ctx,context,answer,asset_ids)
                    with ctx.transaction() as conn:
                        payload=json.loads(row(conn,'tasks',ctx.task_id)['payload_json'])
                        payload['asset_ids']=ids
                        conn.execute('UPDATE tasks SET payload_json=? WHERE id=?',(encode(payload),ctx.task_id))
                    return await self.edit(ctx,_stock_assets=ids)
                raise ModelTaskError('visual_material_gap','未落实镜头：'+','.join(answer.unresolved_scene_ids)+
                    '；已有局部补料仍不足时不重复检索，保留方案、素材与旁白，尚未渲染')
            settings=context.plan['settings']
            answer=align_editor_frames(compensate_edit_overlap(answer,target_seconds=settings['duration_seconds']))
            answer,unverified_editor_notes=project_editor_features(answer)
            horizontal=settings['aspect_ratio']=='16:9'
            if not style.enabled and answer.captions:
                raise ModelTaskError('subtitle_disabled','方案关闭了字幕，剪辑不能擅自添加')
            aligned = aligned_captions(answer.audio, records) if (context.plan.get('narration_policy') or {}).get('continuous') else None
            captions=compile_captions(answer.captions,style=style,fonts=fonts,aligned=aligned if style.enabled else None,
                font_paths=font_paths,width=1920 if horizontal else 1080,height=1080 if horizontal else 1920)
            answer=answer.model_copy(update={'audio':fit_sound_effects(answer.audio,source_durations)})
            data=answer.model_dump(exclude={'visual_evidence'});data['captions']=captions
            project=EditProject(work_id=ctx.work_id,plan_revision=ctx.plan_revision,revision=1,
                width=1920 if horizontal else 1080,height=1080 if horizontal else 1920,
                duration=settings['duration_seconds'],audio_mode=settings['audio_mode'],**data)
            used={s.asset_id for s in project.scenes}|{a.asset_id for a in project.audio}
            mapping={json.loads(r['metadata_json']).get('input_id'):r['id'] for r in records}
            for input in context.inputs:
                if input['usage']=='must_use' and input['kind'] in {'image','video','audio'}:
                    if mapping.get(input['input_id']) not in used:raise ModelTaskError('required_input_missing','剪辑未使用已指定的必用素材')
                    if input['constraints'].get('original_audio'):
                        id=mapping[input['input_id']]
                        ranges=[(s.source_start,s.source_start+s.duration) for s in project.scenes if s.asset_id==id and s.source_audio and s.source_gain>0]
                        ranges += [(a.source_start,a.source_start+a.duration) for a in project.audio if a.asset_id==id and a.gain>0]
                        if not ranges:raise ModelTaskError('original_audio_missing','剪辑未保留已指定的原声')
                        interval=input['constraints'].get('interval')
                        if interval:
                            covered=interval['start']
                            for start,end in sorted(ranges):
                                if start<=covered+.02:covered=max(covered,end)
                            if covered<interval['end']-.02:raise ModelTaskError('original_audio_interval_missing','剪辑未覆盖明确指定的完整原声区间')
            for media in records:
                metadata=json.loads(media['metadata_json'])
                if metadata.get('role')=='voice':
                    clips=[a for a in project.audio if a.asset_id==media['id'] and a.role=='voice']
                    if len(clips)!=1 or clips[0].source_start!=0 or abs(clips[0].duration-metadata['duration'])>.05 or clips[0].gain<=0:
                        raise ModelTaskError('narration_changed','剪辑不能丢弃、截短或静音已确认的旁白')
            expected_segments=[segment['segment_id'] for segment in narration_segments(context.plan)]
            voiced={r['id']:json.loads(r['metadata_json']) for r in records if json.loads(r['metadata_json']).get('role')=='voice'}
            spoken=sorted((a for a in project.audio if a.asset_id in voiced),key=lambda a:a.at)
            expected=[segment for segment in expected_segments if segment in {m.get('segment_id') for m in voiced.values()}]
            if [voiced[a.asset_id].get('segment_id') for a in spoken]!=expected or any(a.at+a.duration>b.at+.02 for a,b in zip(spoken,spoken[1:])):
                raise ModelTaskError('narration_order_changed','旁白句段不能倒序或互相覆盖播放')
            if style.enabled and spoken and not project.captions:
                raise ModelTaskError('subtitles_missing','已开启字幕的旁白不能省略字幕')
            validate_audio_bindings(project,records)
            selected = selected_asset_ids(project)
            records = [r for r in records if r['id'] in selected]
            manifest = AssetManifest(root=manifest.root,assets={k:v for k,v in manifest.assets.items() if k in selected})
            validate_material_records(self.service,ctx,records)
            check=await asyncio.to_thread(self.editor.check,project,manifest)
            if not check.valid:raise ModelTaskError(check.code or 'editor_rejected','；'.join(check.diagnostics))
            temp=self.service.outputs/'_production'/'projects'/ctx.task_id
            temp.mkdir(parents=True,exist_ok=True)
            path=temp/'project.json';path.write_text(project.model_dump_json(),encoding='utf8')
            artifact=register_file(self.service,ctx,path,kind='edit_project',media_type='application/json',metadata={'plan_revision':ctx.plan_revision,
                    'audio_observation': 'model_native' if audio_native else 'technical_only_unverified',
                    'execution_timing': timing, 'subtitle_alignment': (
                        'local_acoustic_estimate' if aligned and any(
                            json.loads(r['metadata_json']).get('timing', {}).get('local_alignment', {}).get('status') == 'received'
                            for r in records if r['kind'] == 'audio')
                        else 'provider' if aligned else 'editor_preview'),
                    'caption_roles':{c.caption_id:c.role for c in answer.captions},
                    **({'subtitle_layout': {'line_mode': 'single',
                        'overflow_timing': 'proportional_within_existing_cue'}} if style.single_line else {}),
                    'visual_evidence':[e.model_dump() for e in answer.visual_evidence],
                    'unverified_editor_notes':unverified_editor_notes},
                    dependencies=list(manifest.assets))
            return TaskResult(result={'project_id':artifact['id']},next_kind='render',next_payload={'project_id':artifact['id'],'asset_ids':list(manifest.assets),'reuse_existing_media_only':ctx.payload.get('reuse_existing_media_only',False)})
        except (ModelTaskError,EditError,ValidationError) as exc:
            message=('剪辑方案不符合严格编辑合同，请检查镜头时间、声音和素材引用'
                     if isinstance(exc,ValidationError) else getattr(exc,'user_message',str(exc)))
            return TaskResult(state='needs_decision',error=ProductionError(getattr(exc,'code','invalid_edit'),message,requires_decision=True),work_state='needs_decision')

    async def render(self,ctx):
        from .worker import TaskResult
        with self.service.store.connection() as conn:record=row(conn,'artifacts',ctx.payload['project_id'])
        if record['work_id']!=ctx.work_id:raise ValueError('cross-work project')
        project=EditProject.model_validate_json(artifact_file(self.service,record).read_text())
        try:
            selected = selected_asset_ids(project)
            records,manifest=self.assets(ctx,[id for id in ctx.payload['asset_ids'] if id in selected])
            validate_audio_bindings(project,records)
        except ModelTaskError as exc:
            return TaskResult(state='needs_decision',work_state='needs_decision',
                error=ProductionError(exc.code,exc.user_message,requires_decision=True))
        attempt=ctx.payload.get('render_attempt',0)
        job_id=f'{ctx.task_id}_retry{attempt}' if attempt else ctx.task_id
        job=await asyncio.to_thread(self.editor.build,project,manifest,job_id=job_id)
        # Worker resumes this exact job ID; editor refuses conflicting content.
        job=await asyncio.to_thread(self.editor.observe,job.job_id)
        with ctx.transaction() as conn:
            self.service._event(conn,ctx.work_id,'render_progress',{'stage':job.stage,'completed_steps':job.completed_steps,'total_steps':job.total_steps},run_id=ctx.run_id)
        if job.status in {'queued','running'}:return TaskResult(state='waiting_external',result={'render_job_id':job.job_id})
        if job.status!='completed':return TaskResult(state='needs_decision',error=ProductionError('render_'+job.status,job.error or '渲染中断，请检查本地环境',requires_decision=True),work_state='needs_decision')
        output=await asyncio.to_thread(self.editor.collect,job.job_id)
        artifact=register_file(self.service,ctx,output.video_path,kind='output',media_type='video/mp4',metadata={'project_id':record['id'],'render_job_id':job.job_id},dependencies=[record['id'],*manifest.assets],output=True)
        credits=[]
        for media in records:
            credit=json.loads(media['metadata_json']).get('attribution')
            if credit:
                if credit.get('destination')!='export_credits' or not credit.get('credit_text'):
                    raise ModelTaskError('attribution_unavailable','素材署名条件无法落实')
                credits.append(credit['credit_text']+'\n'+credit.get('source_page',''))
        if credits:
            import zipfile
            bundle=output.video_path.parent/'export.zip'
            with zipfile.ZipFile(bundle,'w',compression=zipfile.ZIP_STORED) as archive:
                archive.write(output.video_path,'video.mp4')
                archive.writestr('credits.txt','\n\n'.join(dict.fromkeys(credits)))
            register_file(self.service,ctx,bundle,kind='export_bundle',media_type='application/zip',metadata={'output_id':artifact['id']},dependencies=[artifact['id']])
        return TaskResult(result={'output_id':artifact['id']},next_kind='quality',next_payload={'output_id':artifact['id'],'project_id':record['id'],'repair_round':ctx.payload.get('repair_round',0),'reuse_existing_media_only':ctx.payload.get('reuse_existing_media_only',False)})

    async def quality(self,ctx):
        from .worker import TaskResult
        from .media import probe_media
        with self.service.store.connection() as conn:
            artifact=row(conn,'artifacts',ctx.payload['output_id'])
            project_record=row(conn,'artifacts',ctx.payload['project_id'])
        if artifact['work_id']!=ctx.work_id or project_record['work_id']!=ctx.work_id:raise ValueError('cross-work quality input')
        path=artifact_file(self.service,artifact)
        project=EditProject.model_validate_json(artifact_file(self.service,project_record).read_text())
        info=await asyncio.to_thread(probe_media,path)
        technical=info['video'] and abs(info['duration']-project.duration)<=.1 and (info['width'],info['height'])==(project.width,project.height) and info['audio']==(project.audio_mode!='silent')
        self._check(ctx,artifact,'technical','pass' if technical else 'fail',{'probe':info,'expected_duration':project.duration})
        if not technical:
            self._quality_state(ctx,artifact,'needs_fix')
            return TaskResult(work_state='preview_needs_fix',result={'output_id':artifact['id'],'technical':'fail'})
        quality_context = self.planning.context(ctx)
        from .narration import project_timing_evidence
        quality_context = replace(quality_context, brief=quality_context.brief +
            '\n实际编辑时间依据（不是听审结论）：' + encode(project_timing_evidence(project,
                json.loads(project_record['metadata_json']).get('caption_roles'))))
        if ((quality_context.plan.get('narration_policy') or {}).get('duration_mode') == 'voice_driven' or
                (json.loads(project_record['metadata_json']).get('execution_timing') or {}).get('mode') == 'confirmed_ending'):
            from copy import deepcopy
            measured_plan = deepcopy(quality_context.plan)
            measured_plan['settings']['duration_seconds'] = project.duration
            quality_context = replace(quality_context, plan=measured_plan,
                brief=quality_context.brief + '\n本片按实测语音或明确确认的收尾调整执行，实际剪辑工程时长：' + str(project.duration))
        if self.manual_review_only:
            if self.visual_review and quality_context.plan.get('narration_policy'):
                try:
                    from .quality import review_visual_preview
                    status, evidence = await review_visual_preview(path,
                        runner=self.planning.runner(ctx,namespace='visual-review-v1'),context=quality_context)
                    # Existing semantic ledger, explicitly limited scope. A
                    # sampled visual pass NEVER becomes a semantic pass.
                    findings=evidence['review']['findings']
                    self._check(ctx,artifact,'semantic','fail' if findings else 'not_tested',
                        {**evidence,'visual_status':status},rule_version='visual-preview-1')
                    # Limited observation or a bare verdict is not evidence of a defect.
                    # Keep the original review, but do not rerender or block human review.
                    if findings:
                        self._quality_state(ctx,artifact,'needs_fix')
                        if findings and ctx.payload.get('repair_round',0)<1:
                            with ctx.transaction() as conn:
                                payload=json.loads(row(conn,'tasks',ctx.task_id)['payload_json'])
                                review_id=payload.get('visual_repair_review_id')
                                if not review_id:
                                    review_id=new_id()
                                    feedback=('原生视觉抽样发现以下问题，需先确认涉及声音/字幕时码或内容的修订范围，不能直接视觉重剪：'
                                        if evidence['review'].get('repair_scope')=='protected_timing_or_content' else
                                        '原生视觉抽样发现以下问题。仅修正有证据的问题，保留完整旁白、已确认观点及总时长；需要库存时使用有界补料，不用无关素材替代：')+encode(findings)
                                    conn.execute('INSERT INTO reviews(id,work_id,output_id,feedback,created_at) VALUES (?,?,?,?,?)',
                                        (review_id,ctx.work_id,artifact['id'],feedback,now()))
                                    payload['visual_repair_review_id']=review_id
                                    conn.execute('UPDATE tasks SET payload_json=? WHERE id=?',(encode(payload),ctx.task_id))
                                    self.service._event(conn,ctx.work_id,'visual_repair_requested',{'output_id':artifact['id'],'review_id':review_id},run_id=ctx.run_id)
                            return TaskResult(result={'output_id':artifact['id'],'visual':'fail'},next_kind='revise',
                                next_payload={'review_id':review_id,'output_id':artifact['id'],'repair_round':1,
                                    'preserve_audio':True,'creative_visual_repair':True,
                                    'reuse_existing_media_only':ctx.payload.get('reuse_existing_media_only',False),
                                    'repair_scope':evidence['review'].get('repair_scope','visual'),
                                    'affected_scene_ids':[sid for sid in evidence['review'].get('affected_scene_ids',[])
                                        if sid in {s.scene_id for s in project.scenes}]},work_state='producing')
                        return TaskResult(work_state='preview_needs_fix',result={'output_id':artifact['id'],'visual':status,'semantic':'not_tested'})
                except ModelTaskError as exc:
                    self._check(ctx,artifact,'semantic','not_tested',{'code':exc.code,'scope':'sampled_visual_only'},rule_version='visual-preview-1')
                    return TaskResult(state='needs_decision',work_state='needs_decision',error=ProductionError(exc.code,exc.user_message,requires_decision=True))
            # Temporary S6-14 manual-review policy, enabled ONLY by a private
            # runtime switch. Keep technical QC mandatory and retain real
            # negative semantic findings as blockers; never invent a PASS.
            with self.service.store.connection() as reader:
                prior = reader.execute("""SELECT status FROM quality_checks
                    WHERE artifact_id=? AND artifact_digest=? AND check_kind='semantic'""",
                    (artifact['id'],artifact['digest'])).fetchall()
            if any(record['status'] in {'fail','partial'} for record in prior):
                return TaskResult(state='needs_decision',work_state='needs_decision',
                    error=ProductionError('semantic_findings_require_review',
                        '已有语义检查失败或不完整，不能用人工审片开关忽略已有问题',
                        requires_decision=True))
            self._check(ctx,artifact,'semantic','not_tested',{
                'mode':'manual_review_only','reason':'creator_requested_temporary_bypass',
                'technical_check':'pass','automated_semantic_review':'not_executed',
                'creator_acceptance':'still_required'})
            # The artifact's semantic quality has NOT been checked. Preserve
            # needs_fix instead of lying with artifact.quality_state=passed.
            self._quality_state(ctx,artifact,'needs_fix')
            with ctx.transaction() as writer:
                self.service._event(writer,ctx.work_id,'manual_review_required',{
                    'output_id':artifact['id'],'technical':'pass','semantic':'not_tested',
                    'mode':'manual_review_only'},run_id=ctx.run_id)
            return TaskResult(work_state='reviewable',result={
                'output_id':artifact['id'],'technical':'pass',
                'semantic':'not_tested','manual_review_required':True})
        try:
            from .quality import review_full_video
            def progress(completed,total,segment):
                with ctx.transaction() as conn:
                    self.service._event(conn,ctx.work_id,'quality_progress',{'completed_segments':completed,'total_segments':total,
                        'start':segment['start'],'end':segment['end'],'verdict':segment['review']['verdict']},run_id=ctx.run_id)
            answer=await review_full_video(path,cache_root=self.service.outputs/'works'/ctx.work_id/'inspection'/ctx.task_id,
                info=info,transport=self.review_planning.transport,runner=self.review_planning.runner(ctx),
                context=quality_context,review_type=SemanticReview,on_segment=progress)
            self._check(ctx,artifact,'semantic',answer.verdict,{'review':answer.review,'evidence':answer.evidence})
            passed=answer.verdict=='pass' and not answer.limitations
            self._quality_state(ctx,artifact,'passed' if passed else 'needs_fix')
            if answer.verdict=='fail' and answer.findings and ctx.payload.get('repair_round',0)<1:
                with ctx.transaction() as conn:
                    review_id=new_id()
                    feedback='首版自检发现以下问题。仅修正这些问题，保留已确认内容；不得扩大范围或增加未授权调用：'+encode(answer.findings)
                    conn.execute('INSERT INTO reviews(id,work_id,output_id,feedback,created_at) VALUES (?,?,?,?,?)',
                        (review_id,ctx.work_id,artifact['id'],feedback,now()))
                    self.service._event(conn,ctx.work_id,'quality_repair_requested',{'output_id':artifact['id'],'review_id':review_id},run_id=ctx.run_id)
                return TaskResult(result={'output_id':artifact['id'],'semantic':'fail'},next_kind='revise',
                    next_payload={'review_id':review_id,'output_id':artifact['id'],'repair_round':1},work_state='producing')
            return TaskResult(work_state='reviewable' if passed else 'preview_needs_fix',result={'output_id':artifact['id'],'semantic':answer.verdict})
        except ModelTaskError as exc:
            status='partial' if exc.diagnostic.get('evidence',{}).get('reviewed_chunks') else 'not_tested'
            self._check(ctx,artifact,'semantic',status,{'code':exc.code,**exc.diagnostic})
            self._quality_state(ctx,artifact,'needs_fix')
            return TaskResult(state='needs_decision',work_state='needs_decision',error=ProductionError(exc.code,exc.user_message,requires_decision=True),result={'output_id':artifact['id'],'technical':'pass','semantic':status})

    def _check(self,ctx,artifact,kind,status,findings,*,rule_version='production-1'):
        with ctx.transaction() as conn:
            conn.execute('INSERT INTO quality_checks(id,artifact_id,artifact_digest,check_kind,rule_version,status,findings_json,created_at) VALUES (?,?,?,?,?,?,?,?)',
                (new_id(),artifact['id'],artifact['digest'],kind,rule_version,status,encode(findings),now()))
            self.service._event(conn,ctx.work_id,'quality_checked',{'output_id':artifact['id'],'kind':kind,'status':status},run_id=ctx.run_id)

    def _quality_state(self,ctx,artifact,state):
        with ctx.transaction() as conn:conn.execute('UPDATE artifacts SET quality_state=? WHERE id=?',(state,artifact['id']))
