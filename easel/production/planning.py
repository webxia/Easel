"""Planning tasks bind creative answers to program-owned immutable plan revisions."""
from __future__ import annotations
import json
import re
from dataclasses import replace
from pydantic import Field, model_validator
from .contracts import Contract, Scene, VideoSettings, ExplainerBoard
from .context import TaskContext
from .model_tasks import ModelTaskRunner, ModelTaskError
from .errors import ProductionError
from .model_operations import RecordedModelTransport
from .service import row, encode, digest, now, new_id


class CreativePlan(Contract):
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    script: str = Field(min_length=1)
    scenes: list[Scene] = Field(min_length=1)
    settings: VideoSettings
    facts: list[str] = Field(default_factory=list)
    core_views: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    adaptation_permissions: list[str] = Field(default_factory=list)
    explainer_boards: list[ExplainerBoard] = Field(default_factory=list,max_length=8)

    @model_validator(mode='after')
    def executable_boards(self):
        refs=[b.scene_id for b in self.explainer_boards]
        if len(refs)!=len(set(refs)) or not set(refs)<={s.id for s in self.scenes}:
            raise ValueError('原生图解必须绑定已定义场景，每场景一组状态')
        if self.explainer_boards and self.settings.subtitles.enabled and self.settings.subtitles.position!='bottom':
            raise ValueError('原生图解当前为底部字幕留出安全区，不可改变用户字幕位置；本片可选择不使用图解')
        return self


# Validation-only wrapper for generated drafts. Existing frozen plans and
# manually entered Creator content retain their original public contract.
_SPOKEN_STAGE_DIRECTIONS = re.compile(
    r'\d{1,2}:\d{2}(?:\.\d+)?|旁白窗口|窗口前后|句前后|语速中慢|句末留白'
)


class VoiceReadyCreativePlan(CreativePlan):
    @model_validator(mode='after')
    def narration_and_budget(self):
        if self.settings.audio_mode not in {'voice', 'mixed'}:
            return self
        for scene in self.scenes:
            if _SPOKEN_STAGE_DIRECTIONS.search(scene.narration):
                raise ValueError(
                    f'场景 {scene.id} 的 narration 包含时间码或导演注释。'
                    'narration 只能是最终真实 TTS 要朗读的短句，'
                    '不要放旁白窗口、时间段、语速、停顿、换气、字幕或镜头说明；'
                    '这些说明请写在 script 或 visual 字段。'
                )
        from .voice_budget import reserve_narration_slots
        try:
            reserve_narration_slots(self.model_dump(mode='json'))
        except ModelTaskError as exc:
            raise ValueError(
                f'分镜旁白预留失败（{exc.code}）：{exc.user_message}。'
                '请调整口播量或分镜分配，'
                '遵守本次真实片长与明确设置，并保留固定音色与导演风格。'
            ) from None
        return self


class DraftReview(Contract):
    verdict: str = Field(pattern='^(pass|fail)$')
    findings: list[str] = Field(default_factory=list,max_length=12)
    observations: list[str] = Field(default_factory=list,max_length=24)
    limitations: list[str] = Field(default_factory=list,max_length=12)


class PlanningTasks:
    def __init__(self, service, operations, transport, model_service, config_version):
        self.service, self.operations, self.transport = service, operations, transport
        self.model_service, self.config_version = model_service, config_version
        self.tool_factory=lambda ctx: ()
        self.board_fonts = {}
        self.execution_capabilities = {
            'visuals': ['licensed stock footage', 'licensed images', 'captions', 'crop', 'pan_zoom', 'transitions'],
            'native_explainer_boards': False,
            'unavailable': ['arbitrary drawing or animation', 'recording the user screen', 'unprovided personal footage'],
            'narration': 'continuous speech; measured duration can drive unfixed-length films',
        }

    def context(self, ctx):
        with self.service.store.connection() as conn:
            work=row(conn,'works',ctx.work_id)
            basis=None
            inputs=[dict(r) for r in conn.execute('SELECT * FROM work_inputs WHERE work_id=?',(ctx.work_id,))]
            plan={}
            profile_ref=work['profile_ref']
            selected_plan=ctx.plan_revision or ctx.payload.get('base_plan_revision')
            if selected_plan:
                record=conn.execute('SELECT payload_json FROM plan_revisions WHERE work_id=? AND revision=?',(ctx.work_id,selected_plan)).fetchone()
                if record:plan=json.loads(record[0])
            if plan:
                snapshot=plan.get('profile_snapshot')
                profile=json.loads(snapshot['content']) if snapshot else {}
                profile_ref=snapshot['profile_ref'] if snapshot else None
                director_id=plan.get('director_revision_id')
                director=json.loads(row(conn,'director_revisions',director_id)['style_json']) if director_id else {}
                basis={'profile':profile,'director':director,'settings':plan['settings']}
            else:
                basis=ctx.payload.get('creation_basis') or self.service._basis(conn,work)
        safe_inputs=tuple({'input_id':i['id'],'kind':i['kind'],'usage':i['usage'],'text':i['text_content'],
            'name':i['original_name'],'constraints':json.loads(i['metadata_json'])} for i in inputs)
        return TaskContext(work_id=ctx.work_id,run_id=ctx.run_id,task_id=ctx.task_id,
            profile_ref=profile_ref,profile=basis['profile'],director=basis['director'],
            brief=work['input_text']+'\n本次明确设置：'+encode(basis['settings'])+'\n本次对话依据：'+encode(basis.get('conversation_brief'))+'\n频道定位：'+encode(basis.get('channel_basis',{}))+'\n本次补充：'+str(ctx.payload.get('request','')),
            inputs=safe_inputs,allowed_handles=frozenset(i['id'] for i in inputs),plan=plan,
            capabilities=self.execution_capabilities,
            facts=tuple(plan.get('facts',[])),prohibitions=tuple(plan.get('constraints',[])),
            adaptation_permissions=tuple(plan.get('adaptation_permissions',[])))

    def _committed_result(self,ctx):
        # The current DB payload is authority after a crash or tool write; an
        # earlier TaskContext may not include a just-committed business result.
        ctx.assert_current()
        with self.service.store.connection() as conn:
            payload=json.loads(row(conn,'tasks',ctx.task_id)['payload_json'])
        return payload.get('business_result')

    @staticmethod
    def _save_result(conn,ctx,result):
        payload=json.loads(row(conn,'tasks',ctx.task_id)['payload_json'])
        payload['business_result']=result
        conn.execute('UPDATE tasks SET payload_json=? WHERE id=?',(encode(payload),ctx.task_id))

    def runner(self, ctx, *, namespace=None, max_format_repairs=1, legacy_first_repair=False):
        if self.transport is None:
            raise ModelTaskError('service_unavailable','请先配置创作模型服务，再授权当前任务使用')
        recorded=RecordedModelTransport(self.transport,self.operations,ctx,self.model_service,self.config_version,namespace=namespace)
        async def authorize(_context):
            # Actual per-request authorization and durable receipt happen inside recorded.complete.
            return None
        return ModelTaskRunner(recorded,authorize,max_format_repairs=max_format_repairs,
                               legacy_first_repair=legacy_first_repair)

    async def observe_inputs(self,ctx):
        import asyncio
        from .inspection import observe_media
        from .media import local_path,file_sha256
        with self.service.store.connection() as conn:
            records=[dict(r) for r in conn.execute('SELECT * FROM work_inputs WHERE work_id=?',(ctx.work_id,))]
        blocks=[];required={'text','structured'}
        for record in records:
            if record['kind']=='text':continue
            path=local_path(self.service.outputs,record['source_ref'])
            if file_sha256(path)!=record['digest']:raise ModelTaskError('input_changed','已登记输入发生变化，请重新提供')
            blocks.append({'type':'text','text':'输入句柄 '+record['id']+'；用途 '+record['usage']})
            if record['kind']=='document':
                if path.suffix.lower() not in {'.txt','.md'}:
                    raise ModelTaskError('document_format_unavailable','当前文档需提供可读取的文本内容，未假装读取原件')
                text=path.read_text(encoding='utf8')
                if len(text)>100000:raise ModelTaskError('input_too_large','文档超出单次读取范围，请拆分输入')
                blocks.append({'type':'text','text':text})
            else:
                visual_only=record['usage']=='reference' and json.loads(record['metadata_json']).get('observation_scope')=='visual'
                if visual_only:blocks.append({'type':'text','text':'此输入仅作画面与叙事参考，原音轨未分析，不能据此判断声音。'})
                media,needs,_=await asyncio.to_thread(observe_media,path,include_audio=not visual_only,max_frames=8)
                blocks.extend(media);required.update(needs)
        return tuple(blocks),frozenset(required)

    async def draft_board_media(self,ctx,plan):
        """Actual local draft pixels, not registered final assets or user evidence."""
        if not plan.explainer_boards or not self.board_fonts:
            return (),frozenset()
        import asyncio
        from .boards import render_board
        from .inspection import observe_media
        from .media import atomic_json, file_sha256
        font=self.board_fonts.get(plan.settings.subtitles.font)
        if not font:
            raise ModelTaskError('capability_unavailable','草稿图解缺少本片配置的实际字体')
        folder=self.service.outputs/'_production'/'plan-previews'/ctx.task_id/digest(plan.model_dump(mode='json'))
        folder.mkdir(parents=True,exist_ok=True)
        blocks=[];required=set();manifest=[]
        visual=bool(self.transport and 'image' in self.transport.capabilities)
        for board in plan.explainer_boards:
            for index in range(len(board.states)):
                path=folder/(board.scene_id+'-'+str(index)+'.png')
                await asyncio.to_thread(render_board,board,index,font_path=font,
                    aspect_ratio=plan.settings.aspect_ratio,destination=path)
                entry={'board_id':board.scene_id,'state_index':index,'sha256':file_sha256(path)}
                preview=path
                style=plan.settings.subtitles
                scene=next(s for s in plan.scenes if s.id==board.scene_id)
                sample=scene.narration.strip()[:24]
                if style.enabled and sample:
                    from .subtitles import caption_from_settings
                    from .media import caption_layout,caption_image
                    from PIL import Image
                    caption=caption_from_settings(style,caption_id='draft-sample',text=sample,start=0,end=1,
                        fonts={style.font:'draft-font'})
                    width,height=(1920,1080) if plan.settings.aspect_ratio=='16:9' else (1080,1920)
                    _,_,_,bounds=caption_layout(caption,font,width=width,height=height)
                    layer=folder/(board.scene_id+'-caption.png')
                    caption_image(caption,font,width=width,height=height,destination=layer)
                    preview=path.with_name(path.stem+'-preview.png')
                    with Image.open(path) as background,Image.open(layer) as overlay:
                        Image.alpha_composite(background.convert('RGBA'),overlay.convert('RGBA')).convert('RGB').save(preview)
                    entry.update(caption_sample_bounds=list(bounds),caption_sample_source='same scene narration prefix, not final segmentation',
                                 preview_sha256=file_sha256(preview))
                manifest.append(entry)
                if visual:
                    media,needs,_=await asyncio.to_thread(observe_media,preview,include_audio=False,max_frames=1)
                    blocks.append({'type':'text','text':'尚未确认草稿的本地真实图解 '+board.scene_id+' 状态 '+str(index)+
                        '；不是实证资料。若有字幕，叠加的是当前固定样式与本段原文前缀的实际排版样例，不是最终断句或时码。实际样例边界(x,y,w,h)：'+str(entry.get('caption_sample_bounds'))})
                    blocks.extend(media);required.update(needs)
        atomic_json(folder/'manifest.json',{'draft_hash':digest(plan.model_dump(mode='json')),
            'font_sha256':file_sha256(font),'images_sent':visual,'frames':manifest})
        return tuple(blocks),frozenset(required)

    async def plan(self,ctx):
        from .worker import TaskResult
        try:
            cached=self._committed_result(ctx)
            if cached:
                return TaskResult(result=cached,work_state='awaiting_confirmation')
            context=self.context(ctx)
            media,required=await self.observe_inputs(ctx)
            def check_capabilities(answer):
                if answer.explainer_boards and not self.execution_capabilities.get('native_explainer_boards'):
                    raise ValueError('本次尚未配置原生图解字体，不能使用explainer_boards；不得虚构图解能力')
            proposed=await self.runner(ctx,max_format_repairs=2).run(context,
                '提出完整创作方案；遵守明确时长、画幅、声音设置；全部必用输入须落实到场景。'
                'Scene.narration 只能是将由 TTS 实际朗读的简短口播原文，不能包含时间码、朗读窗口、'
                '停顿/换气/语速说明、其他导演注释或舞台指令；这类说明写入 script/visual。'
                '中文口播要有明显时间余量，不超过冻结时长预算；所有镜头累计时长仍须精确。'
                '具体的分组、比较、数量关系或条件变化，可以用原生explainer_boards自主写出文字卡片、类别和前后状态；'
                '图解会由程序原样绘制，每个状态都有真实数量和概念/假设标识，不需搜索到完全相同的卡片。'
                '图解只作概念/假设，不编造成真实资料；文字简短，按需用，不强制每场图解。'
                '返回摘要、完整脚本、场景和视听设计。',VoiceReadyCreativePlan,
                media=media,required=required,tools=self.tool_factory(ctx),validate_result=check_capabilities)
            with self.service.store.connection() as reader:
                requested = json.loads(row(reader, 'works', ctx.work_id)['settings_json'])
            autonomous = ('duration_seconds' not in requested and
                          proposed.settings.audio_mode in {'voice', 'mixed'})
            if autonomous:
                from .contracts import SubtitleSettings, VoiceIdentity
                def preserve_choices(answer):
                    check_capabilities(answer)
                    for field in ('voice', 'subtitles', 'aspect_ratio', 'audio_mode'):
                        if field not in requested:
                            continue
                        expected = requested[field]
                        if field == 'voice' and expected is not None:
                            expected = VoiceIdentity.model_validate(expected).model_dump(mode='json')
                        elif field == 'subtitles':
                            expected = SubtitleSettings.model_validate(expected).model_dump(mode='json')
                        if answer.model_dump(mode='json')['settings'][field] != expected:
                            raise ValueError('不得改变已选设置：' + field)
                # Audit literal semantics and actual diagrams BEFORE freezing.
                # A native critic returns evidence; only the native author may
                # revise the draft. No operator copy or per-film diagram patch.
                async def audit(draft,namespace):
                    from .editors import EditError
                    try:
                        preserve_choices(draft)
                    except ValueError as exc:
                        return DraftReview(verdict='fail',findings=[str(exc)])
                    try:
                        board_media,board_needs=await self.draft_board_media(ctx,draft)
                    except EditError as exc:
                        return DraftReview(verdict='fail',findings=['实际草稿图解渲染失败：'+str(exc)],
                            limitations=['未获得完整可读像素；需先修正草稿文字或布局数据'])
                    return await self.runner(ctx,namespace=namespace,max_format_repairs=2).run(
                        replace(context,plan=draft.model_dump(mode='json')),
                        '独立审查尚未确认草稿；只返回有依据的观察和必须修正的问题，不改稿、不声称已看过未选的库存或听过声音。'
                        '核对是否回应一句想法、具体例子能否解释原因与边界，口语是否有鲜活的分析而非课程讲义。'
                        '逐项检查图解所有状态：每张卡与所在列的字面含义一致，结果、行为和结论不能混装成错误分类；'
                        '类别重命名必须在对应状态的column_titles真实填写，不能只在visual里口头说会改。'
                        '收到的PNG是当前草稿按实际字体与固定字幕样式渲染的真实像素，结合JSON及实际字幕样例边界检查文字、数量、留白及安全区；'
                        '不要仅因页脚和字幕都在底部就断言叠字，按真实合成区域判断；字幕样例不代表最终断句、时码或同步。没有PNG时明确只审文字。'
                        '按既有导演判断整片视觉策略：电影感要求光线、构图、动作与场景联系；检查是否把整片机械地替换成重复文字说明板。'
                        '图解服务关键解释，场景素材服务动作、环境与情绪，不设两者比例，不为了热闹堆无关空镜。'
                        '核对production_capabilities与供料可行性：不能凭空承诺库存必然没有品牌或有指定屏幕数据；'
                        '不新增用户没有要求的品牌禁令或匿名条件，也不放宽用户实际隐私要求；公开库存只作示意、不能伪装用户经历。'
                        '未选素材和未试听声音留到实际生产检查，不将这些正常未执行步骤列成草稿缺陷。'
                        '有明确问题时verdict=fail并在findings写具体字段/状态及依据；无明确问题时pass。',
                        DraftReview,media=(*media,*board_media),required=required|board_needs)
                review=await audit(proposed,'draft-audit-v2')
                if review.findings or review.verdict!='pass':
                    proposed=await self.runner(ctx,namespace='draft-correction-v2',max_format_repairs=2).run(
                        replace(context,plan=proposed.model_dump(mode='json')),
                        '依据独立草稿审查修正并返回完整可执行方案；这是尚未确认的草稿，允许调整叙事和图解分类、状态、画面策略，'
                        '不得编造个人经历或新事实，不改变已选声音、字幕、画幅与声音模式。'
                        '不要用多写风格形容词代替实际方案调整，不用无关素材凑电影感。审查：'+encode(review.model_dump(mode='json')),
                        VoiceReadyCreativePlan,media=media,required=required,tools=self.tool_factory(ctx),validate_result=preserve_choices)
                    final=await audit(proposed,'draft-recheck-v2')
                    if final.findings or final.verdict!='pass':
                        raise ModelTaskError('draft_review_failed','原生草稿修正后仍有明确语义或视觉策略问题，未冻结、未配音',
                            diagnostic={'findings':final.findings})
                preserve_choices(proposed)
            with ctx.transaction() as conn:
                work=row(conn,'works',ctx.work_id)
                from .voice_budget import reserve_narration_slots
                payload=self.service.freeze_plan(conn,work,reserve_narration_slots(proposed.model_dump(mode='json')),basis=ctx.payload.get('creation_basis'))
                if autonomous:
                    protected = any(i.get('constraints', {}).get('original_audio') for i in context.inputs)
                    payload['narration_policy'] = {'continuous': not protected,
                        'duration_mode': 'voice_driven' if not protected and proposed.settings.audio_mode == 'voice' else 'fixed'}
                if ctx.payload.get('base_plan_revision'):
                    payload['profile_snapshot']=context.plan.get('profile_snapshot')
                    payload['director_revision_id']=context.plan.get('director_revision_id')
                requested=json.loads(work['settings_json'])
                for field in ('duration_seconds','aspect_ratio','audio_mode','voice','subtitles'):
                    expected=requested.get(field)
                    if field=='subtitles' and field in requested:
                        from .contracts import SubtitleSettings
                        expected=SubtitleSettings.model_validate(expected).model_dump(mode='json')
                    if field=='voice' and expected is not None:
                        from .contracts import VoiceIdentity
                        expected=VoiceIdentity.model_validate(expected).model_dump(mode='json')
                    if field in requested and expected != payload['settings'].get(field):
                        raise ModelTaskError('plan_constraint_changed','模型方案改变了本次明确设置，需要修正方案')
                rev=conn.execute('SELECT COALESCE(MAX(revision),0)+1 FROM plan_revisions WHERE work_id=?',(ctx.work_id,)).fetchone()[0]
                conn.execute('INSERT INTO plan_revisions(id,work_id,revision,payload_json,plan_hash,created_at) VALUES (?,?,?,?,?,?)',
                    (new_id(),ctx.work_id,rev,encode(payload),digest(payload),now()))
                self.service._change(conn,work,current_plan_revision=rev,state='awaiting_confirmation')
                self.service._event(conn,ctx.work_id,'plan_created',{'plan_revision':rev},run_id=ctx.run_id)
                self._save_result(conn,ctx,{'plan_revision':rev})
            return TaskResult(result={'plan_revision':rev},work_state='awaiting_confirmation')
        except ModelTaskError as exc:
            return TaskResult(state='needs_decision',error=ProductionError(exc.code,exc.user_message,requires_decision=True),work_state='needs_decision')

    async def analyze_director(self,ctx):
        from .worker import TaskResult
        from .inspection import observe_media
        import asyncio
        try:
            cached=self._committed_result(ctx)
            if cached:
                return TaskResult(result=cached,work_state='discussing')
            references=ctx.payload.get('reference_input_ids',[])
            if not isinstance(references,list) or not references or any(not isinstance(ref,str) or not ref for ref in references) or len(set(references))!=len(references):
                raise ModelTaskError('invalid_reference','导演拆解需要本作品中不重复的视频参考句柄')
            blocks=[]; observations=[]; required={'image','structured'}
            scope=ctx.payload.get('analysis_scope','full')
            if scope not in {'full','visual'}:raise ModelTaskError('invalid_reference','导演分析范围无效')
            with self.service.store.connection() as conn:
                records=[row(conn,'work_inputs',id) for id in references]
            for item in records:
                ctx.assert_current()
                if item['work_id']!=ctx.work_id or item['kind']!='video':
                    raise ModelTaskError('invalid_reference','导演参考视频不属于当前作品')
                from .media import local_path
                path=local_path(self.service.outputs,item['source_ref'])
                if self.service._file_hash(path)!=item['digest']:
                    raise ModelTaskError('reference_changed','参考视频已变化，请重新登记')
                media,needs,evidence=await asyncio.to_thread(observe_media,path,include_audio=scope!='visual')
                evidence['analysis_scope']=scope
                if scope=='visual':
                    evidence['sampling']='bounded_frames_visual_only'
                    evidence['audio_semantics']='not_tested'
                    blocks.append({'type':'text','text':'此任务明确仅分析画面与叙事；原音轨未分析。sound字段只写独立的本期声音建议，不得声称听过参考音轨。'})
                blocks.append({'type':'text','text':'导演参考输入句柄 '+item['id']+'；以下实际媒体仅用于风格证据，不代表主人设经历。'})
                blocks.extend(media);required.update(needs)
                observations.append({'input_id':item['id'],'digest':item['digest'],**evidence})
            answer=await self.runner(ctx).run(self.context(ctx),
                '根据实际参考画面和音轨拆解可跨题材复用的视听风格、叙事方式和变化边界。不要将参考中的人物事实变成主人设，也不要固定脚本套路。',
                DirectorAnalysis,required=frozenset(required),media=tuple(blocks))
            with ctx.transaction() as conn:
                if scope=='visual':
                    answer.sound='本期声音建议（参考音轨未分析）：'+answer.sound
                    answer.evidence_notes.append('analysis_scope=visual；原音轨语义NOT_TESTED，不作为听觉风格观察证据')
                id=new_id();director_id=ctx.payload['director_id']
                revision=conn.execute('SELECT COALESCE(MAX(revision),0)+1 FROM director_revisions WHERE director_id=?',(director_id,)).fetchone()[0]
                conn.execute('INSERT INTO director_revisions(id,director_id,revision,style_json,evidence_json,created_at) VALUES (?,?,?,?,?,?)',
                    (id,director_id,revision,encode({'schema_version':1,**answer.model_dump(mode='json')}),encode(observations),now()))
                conn.execute('UPDATE directors SET revision=revision+1,updated_at=? WHERE id=?',(now(),director_id))
                self.service._event(conn,ctx.work_id,'director_analyzed',{'director_id':director_id,'revision_id':id},run_id=ctx.run_id)
                self._save_result(conn,ctx,{'director_revision_id':id})
            return TaskResult(result={'director_revision_id':id},work_state='discussing')
        except ModelTaskError as exc:
            return TaskResult(state='needs_decision',error=ProductionError(exc.code,exc.user_message,requires_decision=True),work_state='needs_decision')


class DirectorAnalysis(Contract):
    visual_style: str = Field(min_length=1)
    storytelling: str = Field(min_length=1)
    rhythm: str = Field(min_length=1)
    sound: str = Field(min_length=1)
    typography: str = Field(min_length=1)
    invariants: list[str] = Field(min_length=1)
    freedom: list[str] = Field(min_length=1)
    evidence_notes: list[str] = Field(min_length=1)
