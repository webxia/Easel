"""Planning tasks bind creative answers to program-owned immutable plan revisions."""
from __future__ import annotations
import json
import re
import hashlib
from dataclasses import replace
from pydantic import Field, model_validator, create_model
from .contracts import Contract, Scene, VideoSettings, ExplainerBoard, NarrationPolicy
from .context import TaskContext
from .model_tasks import ModelTaskRunner, ModelTaskError, parse_model_json
from .errors import ProductionError
from .model_operations import RecordedModelTransport
from .service import row, encode, digest, now, new_id


def validate_audio_replan(answer, protected):
    """Only the explicitly approved audio mode may change in a frozen work."""
    actual=answer.model_dump(mode='json') if hasattr(answer,'model_dump') else answer
    for field in CreativePlan.model_fields:
        if field=='constraints':
            expected=list(protected.get(field,[]))
            marker='本片不使用背景音乐或可选音效'
            if marker not in expected:expected.append(marker)
            if actual.get(field) not in (protected.get(field,[]),expected):
                raise ValueError('声音修订不能改变原有约束')
        elif field=='settings':
            expected={**protected[field],'audio_mode':'voice'}
            if actual[field]!=expected:raise ValueError('声音修订不能改变其他冻结设置')
        elif actual.get(field)!=protected.get(field):
            raise ValueError('声音修订不能改变已确认内容：'+field)


class CreativePlan(Contract):
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    script: str = Field(min_length=1, description='完整口播原文，与各场景narration按顺序拼接一致；不含场景编号、章节标签、时间码或导演注释，非口播说明写purpose/visual。')
    scenes: list[Scene] = Field(min_length=1)
    settings: VideoSettings
    narration_policy: NarrationPolicy | None = Field(default=None,
        description='精确片长用fixed；约数目标或未限定片长用voice_driven。BGM不改变时长策略。continuous独立控制连续口播。')
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
    @model_validator(mode='before')
    @classmethod
    def discard_unrendered_card_titles(cls, value):
        # Structured model drafts may add a title alongside BoardCard.text.
        # Only text is rendered. Normalize this single known extra in drafts;
        # the public PlanDocument and all other fields remain strict.
        if not isinstance(value, dict) or not isinstance(value.get('explainer_boards'), list):
            return value
        boards = []
        changed = False
        for board in value['explainer_boards']:
            if not isinstance(board, dict) or not isinstance(board.get('cards'), list):
                boards.append(board)
                continue
            cards = []
            for card in board['cards']:
                if (isinstance(card, dict) and isinstance(card.get('title'), str)
                        and isinstance(card.get('text'), str)):
                    cards.append({key: item for key, item in card.items() if key != 'title'})
                    changed = True
                else:
                    cards.append(card)
            boards.append({**board, 'cards': cards})
        return {**value, 'explainer_boards': boards} if changed else value

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
                    '这些说明请写在 visual 字段；script保留完整口播原文。'
                )
        spoken = ''.join(scene.narration for scene in self.scenes)
        if spoken.strip() and re.sub(r'\s+', '', self.script) != re.sub(r'\s+', '', spoken):
            raise ValueError('script须与各场景narration按顺序拼接一致；不要添加场景标签或导演说明，修改口播时同步两个字段')
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


# Same plan fields, omitted fields retain their original values. This is a
# model response format, not a second plan contract or an execution command.
CreativePlanChanges = create_model('CreativePlanChanges', __base__=Contract,
    **{name: (field.annotation, Field(default=None, description='省略表示保持原值；填写时提供该字段完整新值'))
       for name, field in CreativePlan.model_fields.items()})


def merge_plan_changes(changes, base):
    return VoiceReadyCreativePlan.model_validate({**base, **changes.model_dump(exclude_unset=True, mode='json')})


def received_plan(operation):
    value=parse_model_json(json.loads(operation['receipt_json'])['result']['message']['content'])
    request=json.loads(operation['request_json'])
    if request.get('schema',{}).get('title')=='CreativePlanChanges':
        base=json.loads(request['messages'][1]['content'][0]['text'])['plan']
        return merge_plan_changes(CreativePlanChanges.model_validate(value),base)
    return VoiceReadyCreativePlan.model_validate(value)


class DraftReview(Contract):
    suggestions: list[str] = Field(default_factory=list, max_length=16, description='非阻断的审美或表达建议；不能用于隐藏事实错误、明确要求冲突或已证实质量缺陷')
    verdict: str = Field(pattern='^(pass|fail)$')
    findings: list[str] = Field(default_factory=list,max_length=12)
    observations: list[str] = Field(default_factory=list,max_length=24)
    limitations: list[str] = Field(default_factory=list,max_length=12)


def validate_narration_revision(answer, base):
    """Narration rewrites retain confirmed delivery and visual choices."""
    proposed=answer.model_dump(mode='json')
    for field in ('duration_seconds','aspect_ratio','audio_mode','voice','subtitles'):
        if proposed['settings'].get(field)!=base['settings'].get(field):
            raise ValueError('改稿重配须保留已确认设置：'+field)
    def visuals(scenes):
        return [{k:v for k,v in scene.items() if k not in {'narration','narration_pauses','duration_seconds'}} for scene in scenes]
    if visuals(proposed['scenes'])!=visuals(base['scenes']) or proposed.get('explainer_boards',[])!=base.get('explainer_boards',[]):
        raise ValueError('本次仅改口播，须保留原场景身份、画面要求和图解内容')


def validate_board_revision(answer, base):
    proposed=answer.model_dump(mode='json')
    if proposed['settings']!=base['settings'] or proposed['script']!=base['script'] or proposed['scenes']!=base['scenes']:
        raise ValueError('图解修订不能改变口播、场景或交付设置')
    def facts(boards):
        return [{k:v for k,v in board.items() if k!='states'} for board in boards]
    if facts(proposed.get('explainer_boards',[]))!=facts(base.get('explainer_boards',[])):
        raise ValueError('图解修订须保留原图解身份、卡片文字及事实')


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

    def context(self, ctx, *, require_expression=True):
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
                basis={**(plan.get('conversation_basis') or {}),
                       'profile':profile,'director':director,'settings':plan['settings']}
            else:
                reference=ctx.payload.get('reference_plan_revision')
                if reference:
                    record=conn.execute('SELECT payload_json FROM plan_revisions WHERE work_id=? AND revision=?',(ctx.work_id,reference)).fetchone()
                    if record:plan=json.loads(record[0])
                basis=ctx.payload.get('creation_basis')
                if basis is None:
                    basis=self.service._basis(conn,work)
                    basis.pop('expression_policy',None)  # Never stamp an existing task on read.
        from .expression_policy import validate
        policy=validate(basis.get('expression_policy')) if require_expression else {}
        safe_inputs=tuple({'input_id':i['id'],'kind':i['kind'],'usage':i['usage'],'text':i['text_content'],
            'name':i['original_name'],'constraints':json.loads(i['metadata_json'])} for i in inputs)
        sound_notes=[]
        with self.service.store.connection() as reader:
            for task in reader.execute("SELECT id,payload_json FROM tasks WHERE run_id=? AND kind='supply'",(ctx.run_id,)):
                if task['id']!=ctx.task_id:
                    sound_notes.extend(json.loads(task['payload_json']).get('optional_sfx_ids',[]))
        sound_note=('\n用户后续已允许以下音效缺料时省略，优先于原方案相应音效要求；保留已取得声音，不将省略当作缺陷，交付说明如实披露：'+encode(sound_notes)) if sound_notes else ''
        return TaskContext(work_id=ctx.work_id,run_id=ctx.run_id,task_id=ctx.task_id,
            profile_ref=profile_ref,profile=basis['profile'],director=basis['director'],
            brief=work['input_text']+'\n本次明确设置：'+encode(basis['settings'])+'\n本次对话依据：'+encode(basis.get('conversation_brief'))+'\n频道定位：'+encode(basis.get('channel_basis',{}))+'\n本次补充：'+str(ctx.payload.get('request',''))+sound_note,
            inputs=safe_inputs,allowed_handles=frozenset(i['id'] for i in inputs),plan=plan,
            capabilities=self.execution_capabilities,expression_policy=policy,
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

    def runner(self, ctx, *, namespace=None, max_format_repairs=1):
        if self.transport is None:
            raise ModelTaskError('service_unavailable','请先配置创作模型服务，再授权当前任务使用')
        recorded=RecordedModelTransport(self.transport,self.operations,ctx,self.model_service,self.config_version,namespace=namespace)
        async def authorize(_context):
            # Actual per-request authorization and durable receipt happen inside recorded.complete.
            return None
        return ModelTaskRunner(recorded,authorize,max_format_repairs=max_format_repairs)

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

    @staticmethod
    def _native_operation(ctx,runner):
        transport=runner.transport
        suffix=('model:'+str(transport.index) if transport.namespace is None else
                'model:'+transport.namespace+':'+str(transport.index))
        return hashlib.sha256((ctx.task_id+':'+suffix).encode()).hexdigest()

    def _store_draft(self,ctx,draft,source,round_,history,review):
        state={'producer_task_id':ctx.task_id,'draft':draft.model_dump(mode='json'),
               'draft_hash':digest(draft.model_dump(mode='json')),'source_operation_id':source,
               'correction_round':round_,'history':history,
               'review':review.model_dump(mode='json') if review is not None else None}
        with ctx.transaction() as conn:
            payload=json.loads(row(conn,'tasks',ctx.task_id)['payload_json'])
            payload['native_draft_checkpoint']=state
            conn.execute('UPDATE tasks SET payload_json=? WHERE id=?',(encode(payload),ctx.task_id))
        return state

    def _recover_draft(self,ctx):
        """Only typed same-task successful native receipts; never operator drafts."""
        with self.service.store.connection() as conn:
            payload=json.loads(row(conn,'tasks',ctx.task_id)['payload_json'])
            ops=[dict(r) for r in conn.execute("SELECT * FROM operations WHERE task_id=? AND kind='MODEL' ORDER BY created_at",(ctx.task_id,))]
        if any(r['state'] in {'reserved','sending','submitted','unknown'} for r in ops):
            raise ModelTaskError('result_unknown','本草稿仍有结果待核实的原请求，未重新发送')
        by_id={r['id']:r for r in ops}
        def known(r):
            return (r['state']=='succeeded' and r['work_id']==ctx.work_id
                    and r['config_version']==self.config_version and r['provider']==self.model_service['provider']
                    and r['model']==self.model_service['model'] and r['mode']==self.model_service['mode'])
        state=payload.get('native_draft_checkpoint')
        if state:
            try:
                op=by_id[state['source_operation_id']]
                draft=VoiceReadyCreativePlan.model_validate(state['draft'])
                received=received_plan(op)
                if (state['producer_task_id']!=ctx.task_id or not known(op) or draft!=received
                        or json.loads(op['request_json']).get('schema',{}).get('title')not in {'VoiceReadyCreativePlan','CreativePlanChanges'}
                        or state['draft_hash']!=digest(draft.model_dump(mode='json'))
                        or not 0<=state['correction_round']<=2):raise ValueError
                return state
            except (KeyError,TypeError,ValueError):
                raise ModelTaskError('draft_provenance_missing','草稿缺少相符的本任务原生模型回执，未采用外部替换稿') from None
        return None

    async def draft_board_media(self,ctx,plan):
        """Actual local draft pixels, not registered final assets or user evidence."""
        if not plan.explainer_boards or not self.board_fonts:
            return (),frozenset()
        import asyncio
        from .boards import render_board, VERSION
        from .inspection import observe_media
        from .media import atomic_json, file_sha256
        font=self.board_fonts.get(plan.settings.subtitles.font)
        if not font:
            raise ModelTaskError('capability_unavailable','草稿图解缺少本片配置的实际字体')
        preview_key=digest({'draft':plan.model_dump(mode='json'),'renderer':VERSION,'font':file_sha256(font),'preview_version':'caption-sample-1'})
        folder=self.service.outputs/'_production'/'plan-previews'/ctx.task_id/preview_key
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
                    from .subtitles import caption_from_settings, single_line_captions
                    from .media import caption_layout,caption_image
                    from PIL import Image
                    caption=caption_from_settings(style,caption_id='draft-sample',text=sample,start=0,end=1,
                        fonts={style.font:'draft-font'})
                    width,height=(1920,1080) if plan.settings.aspect_ratio=='16:9' else (1080,1920)
                    if style.single_line:
                        caption=single_line_captions(caption,font,width=width,height=height)[0]
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
            'font_sha256':file_sha256(font),'renderer':VERSION,'preview_version':'caption-sample-1','images_sent':visual,'frames':manifest})
        return tuple(blocks),frozenset(required)

    async def plan(self,ctx):
        from .worker import TaskResult
        try:
            cached=self._committed_result(ctx)
            if cached:
                return TaskResult(result=cached,work_state='awaiting_confirmation')
            context=self.context(ctx)
            protected=ctx.payload.get('protected_plan')
            if ctx.payload.get('revision_scope')=='narration':
                context=replace(context,brief=context.brief+'\n本次只改口播和对应脚本，保留场景身份、画面要求、图解、音色、字幕样式、画幅和已确认的时长策略；为完整旁白重新分配必要场景时长。')
            if ctx.payload.get('revision_scope')=='boards':
                context=replace(context,brief=context.brief+'\n仅修订已有图解状态顺序、分组和高亮；保留文字事实、口播、场景身份、非图解画面与声音设置。不得新增未经确认的事实。')
            if protected:
                context=replace(context,plan=protected,
                    brief=context.brief+'\n仅允许audio_mode改为voice，无BGM或可选SFX；其他字段逐字保持，包括旁白、镜头、观点和时长。')
            if ctx.payload.get('request') and not protected:
                context=replace(context,brief='本轮改稿要求见本次补充，优先落实；旧稿是待修改基线。\n'+context.brief+'\n先定位要求涉及的原句和场景，按要求改变表达本身，不只替换近义词；同步script与场景narration。保留未涉及的事实与选择；本任务只产出待确认方案，不执行配音或制作。')
            media,required=await self.observe_inputs(ctx)
            with self.service.store.connection() as reader:
                selected = json.loads(row(reader, 'works', ctx.work_id)['settings_json']).get('voice')
            def check_capabilities(answer):
                # Fixed synthesis parameters belong to the selected voice configuration.
                # The creative model may not introduce extra knobs or change their values.
                if selected and answer.settings.voice:
                    from .contracts import VoiceIdentity
                    fixed=VoiceIdentity.model_validate(selected)
                    actual=answer.settings.voice
                    if all(getattr(actual,k)==getattr(fixed,k) for k in ('provider','model','voice_id','engine')):
                        actual.parameters=dict(fixed.parameters)
                if any(s.narration_pauses for s in answer.scenes):
                    from .prosody import compile_pauses
                    if not answer.settings.voice or answer.settings.audio_mode not in {'voice','mixed'}:raise ValueError('停顿控制需要固定旁白声音')
                    if any(i.get('constraints',{}).get('original_audio') for i in context.inputs):raise ValueError('保留原声时不能使用连续旁白停顿控制')
                    for scene in answer.scenes:compile_pauses(scene.narration.strip(),[p.model_dump() for p in scene.narration_pauses],answer.settings.voice)
                if protected:validate_audio_replan(answer,protected)
                if ctx.payload.get("revision_scope")=="narration":validate_narration_revision(answer,context.plan)
                if ctx.payload.get("revision_scope")=="boards":validate_board_revision(answer,context.plan)
                if answer.explainer_boards and not self.execution_capabilities.get('native_explainer_boards'):
                    raise ValueError('本次尚未配置原生图解字体，不能使用explainer_boards；不得虚构图解能力')
            recovered=self._recover_draft(ctx)
            if recovered:
                proposed=VoiceReadyCreativePlan.model_validate(recovered['draft'])
                source=recovered['source_operation_id']
            else:
                author=self.runner(ctx,max_format_repairs=2)
                proposed=await author.run(context,
                '提出完整创作方案；遵守明确时长、画幅、声音设置；全部必用输入须落实到场景。'
                '旁白片在narration_policy明确时长策略：用户明确要求精确片长才用fixed；约、大约、左右或已允许自然收尾的时长是目标，不是硬性长度，应选择voice_driven并在摘要说明实际长度随完整旁白决定。未限定片长同样用voice_driven。continuous与片长独立。'
                'Scene.narration 只能是将由 TTS 实际朗读的简短口播原文，不能包含时间码、朗读窗口、'
                '停顿/换气/语速说明、其他导演注释或舞台指令；这类说明只写入 visual；script与各场景narration按顺序拼接一致，不含分镜编号或章节标签。'
                '仅固定MiniMax speech-2.8时可按必要语义填写独立narration_pauses，after是去除首尾空白后的字符位置，seconds为0.05到1秒；不在正文写供应商标签，不逐句加停顿，默认空列表。'
                'fixed口播须适合明确片长；voice_driven的秒数只是规划估计，最终随完整实测旁白定长，不为填满估计秒数增加内容或留白。'
                '在同一次创作中先按选定导演的讲述方式组织完整思路，再落实分镜；频道提供定位与受众，不是固定文体。'
                '将本期明确的表达要求写入已有constraints，改稿继承未撤销要求并逐项落实；新反馈没有重提不代表原要求失效。'
                '区分用户硬要求和讨论建议：保留已确认观点与事实，未确认的候选概念、结构和素材不必逐项展开。'
                '口播只讲听众理解所需的信息；补充出处与资料按用途放facts或visual，不把资料清单全部念出。'
                '解释用可理解的条件、动作和关系承接术语，不强制聊天、案例数量、幽默或结尾总结。'
                '具体的分组、比较、数量关系或条件变化，可以用原生explainer_boards自主写出文字卡片、类别和前后状态；'
                '图解会由程序原样绘制，每个状态都有真实数量和概念/假设标识，不需搜索到完全相同的卡片。当前图解为固定浅底配色，visual文字不能新增底色、安全带或装饰；不能承诺未由结构化字段和实际渲染支持的设计。不适合时可不使用非必需图解。'
                '图解只作概念/假设，不编造成真实资料；文字简短，按需用，不强制每场图解。'
                '返回摘要、完整脚本、场景和视听设计。',VoiceReadyCreativePlan,
                expression_role=None if protected else "write",
                media=media,required=required,tools=self.tool_factory(ctx),validate_result=check_capabilities)
                source=self._native_operation(ctx,author)
            with self.service.store.connection() as reader:
                requested = json.loads(row(reader, 'works', ctx.work_id)['settings_json'])
            review_draft = (not protected and ctx.payload.get('revision_scope') not in {'narration', 'boards'}
                            and requested.get('audio_mode', proposed.settings.audio_mode) in {'voice', 'mixed'})
            if review_draft:
                from .contracts import SubtitleSettings, VoiceIdentity
                from .editors import EditError
                def preserve_choices(answer):
                    check_capabilities(answer)
                    for field in ('voice', 'subtitles', 'aspect_ratio', 'audio_mode', 'duration_seconds'):
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
                async def audit(draft,namespace,history):
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
                        replace(context,plan=draft.model_dump(mode='json'),
                            brief=context.brief+'\n原生既有审查记录，请逐项核对本次是否已解决；若原判断被实际像素否定，明确依据，不照搬：'+encode(history)),
                        '独立审查尚未确认草稿；只返回有依据的观察和必须修正的问题，不改稿、不声称已看过未选的库存或听过声音。'
                        '逐项核对本次brief中的明确表达要求和constraints，包括未被后续反馈撤销的原要求；有冲突时在findings引用原要求及具体句段，不能因结构通顺就pass。'
                        '遵守实际输出字段合同：script和scene.narration只放真实口播；语气、重音、停顿说明放purpose/visual或narration_pauses。即使整理后的request写了“逐字稿标注语气/停顿”，也不得要求把非口播标记塞回script或新增schema外的第二份TTS稿。'
                        '核对第一人称习惯、已做事项和成果是否确由输入/画像支持；建议做法不能写成已经长期执行的自述。'
                        '核对是否回应一句想法及画像表达目标。分析内容核对依据、逻辑与边界；感悟可以保留问题，不强制案例、教程、结论或升华。'
                        '逐项检查图解所有状态：每张卡与所在列的字面含义一致，结果、行为和结论不能混装成错误分类；'
                        '类别重命名必须在对应状态的column_titles真实填写，不能只在visual里口头说会改。'
                        '收到的PNG是当前草稿按实际字体与固定字幕样式渲染的真实像素，结合JSON及实际字幕样例边界检查文字、数量、留白及安全区；'
                        '不要仅因页脚和字幕都在底部就断言叠字，按真实合成区域判断；白字带黑描边须按实际合成字形判断可读性，不仅凭白字与浅底同色推断不可读。字幕样例不代表最终断句、时码或同步。没有PNG时明确只审文字。'
                        '按既有导演判断整片视觉策略：电影感要求光线、构图、动作与场景联系；检查是否把整片机械地替换成重复文字说明板。'
                        '图解服务关键解释，场景素材服务动作、环境与情绪，不设两者比例，不为了热闹堆无关空镜。'
                        '核对production_capabilities与供料可行性：不能凭空承诺库存必然没有品牌或有指定屏幕数据；'
                        '不新增用户没有要求的品牌禁令或匿名条件，也不放宽用户实际隐私要求；公开库存只作示意、不能伪装用户经历。'
                        '未选素材和未试听声音留到实际生产检查，不将这些正常未执行步骤列成草稿缺陷。'
                        'findings只记录事实矛盾、明确用户要求冲突、错误示意或已证实不可执行问题，注明字段、依据与受损要求；审美取舍和可选优化放suggestions，不因建议返回fail。未选素材的效果未知放limitations，留到生产观察。无明确阻断问题时pass。',
                        DraftReview,expression_role="review",media=(*media,*board_media),required=required|board_needs)
                round_=recovered['correction_round'] if recovered else 0
                history=list(recovered.get('history',[])) if recovered else []
                review=DraftReview.model_validate(recovered['review']) if recovered and recovered.get('review') else None
                self._store_draft(ctx,proposed,source,round_,history,review)
                while True:
                    if review is None:
                        review=await audit(proposed,'draft-audit-v3-'+str(round_),history)
                        history.append(review.model_dump(mode='json'))
                        self._store_draft(ctx,proposed,source,round_,history,review)
                    # Rewrite only for stated defects, never for an unexplained label or optional taste.
                    if not review.findings:break
                    if round_>=2:
                        raise ModelTaskError('draft_review_failed','原生草稿经过两轮修正仍有明确问题，未冻结、未配音',
                            diagnostic={'findings':review.findings})
                    round_+=1
                    try:
                        pictures,picture_needs=await self.draft_board_media(ctx,proposed)
                    except EditError:
                        pictures,picture_needs=(),frozenset()
                    author=self.runner(ctx,namespace='draft-correction-v3-'+str(round_),max_format_repairs=2)
                    base=proposed.model_dump(mode='json')
                    changes=await author.run(
                        replace(context,plan=base),
                        '依据独立草稿审查仅返回需要修改的顶层字段，未涉及字段省略并沿用原值，不能用null代替省略；script与scenes涉及口播时一起同步；不要重复输出未改字段。这是尚未确认的草稿，允许实际调整叙事、具体例子、'
                        '图解分类/状态与视觉策略，不得编造个人经历或事实，不改变已选声音、字幕、画幅和声音模式。'
                        '逐项解决全部有依据的问题，文案与narration一致，术语用具体条件变化解释，不能只改形容词。'
                        '电影感要落实到可取得的具体场景动作、景别、光线与镜头联系，不用无关素材凑，也不把整片放回文字板fallback。'
                        '收到的字幕样例由正式排版函数生成；若旧审查的碰撞假设被真实像素/边界否定，可保留正确布局并如实说明，'
                        '不能把未实现的后期重排写成已完成，更不能借此忽略其他内容问题。原生审查记录：'+encode(history),
                        CreativePlanChanges,expression_role="write",media=(*media,*pictures),required=required|picture_needs,
                        tools=self.tool_factory(ctx),validate_result=lambda changes: preserve_choices(merge_plan_changes(changes,base)))
                    proposed=merge_plan_changes(changes,base)
                    source=self._native_operation(ctx,author);review=None
                    self._store_draft(ctx,proposed,source,round_,history,review)
                preserve_choices(proposed)
            check_capabilities(proposed)
            with ctx.transaction() as conn:
                work=row(conn,'works',ctx.work_id)
                from .voice_budget import reserve_narration_slots
                payload=proposed.model_dump(mode='json')
                if protected:
                    validate_audio_replan(proposed,protected)
                    if '本片不使用背景音乐或可选音效' not in payload['constraints']:
                        payload['constraints'].append('本片不使用背景音乐或可选音效')
                if not protected and proposed.settings.audio_mode in {'voice', 'mixed'}:
                    protected_audio = any(i.get('constraints', {}).get('original_audio') for i in context.inputs)
                    policy = proposed.narration_policy
                    # Absence of a Work setting is not permission to shorten a confirmed plan.
                    mode = policy.duration_mode if policy else 'fixed'
                    if ctx.payload.get('revision_scope') in {'narration', 'boards'}:
                        mode = (context.plan.get('narration_policy') or {}).get('duration_mode', 'fixed')
                    if 'duration_seconds' in requested or protected_audio:
                        mode = 'fixed'
                    payload['narration_policy'] = {'continuous': not protected_audio,
                        'duration_mode': mode}
                if not protected:
                    payload=reserve_narration_slots(payload)
                freeze_basis=ctx.payload.get('creation_basis')
                if ctx.payload.get('base_plan_revision'):
                    freeze_basis={**(context.plan.get('conversation_basis') or {}),
                        'profile':context.profile,'settings':context.plan['settings']}
                payload=self.service.freeze_plan(conn,work,payload,basis=freeze_basis)
                if protected:
                    for field in ('profile_snapshot','director_revision_id','conversation_basis'):
                        payload[field]=protected.get(field)
                if ctx.payload.get('base_plan_revision'):
                    payload['profile_snapshot']=context.plan.get('profile_snapshot')
                    payload['director_revision_id']=context.plan.get('director_revision_id')
                    payload['conversation_basis']=context.plan.get('conversation_basis')
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
                        raise ModelTaskError('plan_constraint_changed','模型方案改变了本次明确设置：settings.'+field+'，需要修正方案')
                rev=conn.execute('SELECT COALESCE(MAX(revision),0)+1 FROM plan_revisions WHERE work_id=?',(ctx.work_id,)).fetchone()[0]
                conn.execute('INSERT INTO plan_revisions(id,work_id,revision,payload_json,plan_hash,created_at) VALUES (?,?,?,?,?,?)',
                    (new_id(),ctx.work_id,rev,encode(payload),digest(payload),now()))
                self.service._change(conn,work,current_plan_revision=rev,state='awaiting_confirmation')
                self.service._event(conn,ctx.work_id,'plan_created',{'plan_revision':rev},run_id=ctx.run_id)
                self._save_result(conn,ctx,{'plan_revision':rev})
            return TaskResult(result={'plan_revision':rev},work_state='awaiting_confirmation')
        except ModelTaskError as exc:
            return TaskResult(state='needs_decision',error=ProductionError(exc.code,exc.user_message,requires_decision=True,operation_id=exc.operation_id),work_state='needs_decision')

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
            answer=await self.runner(ctx).run(self.context(ctx,require_expression=False),
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
            return TaskResult(state='needs_decision',error=ProductionError(exc.code,exc.user_message,requires_decision=True,operation_id=exc.operation_id),work_state='needs_decision')


class DirectorAnalysis(Contract):
    visual_style: str = Field(min_length=1)
    storytelling: str = Field(min_length=1)
    rhythm: str = Field(min_length=1)
    sound: str = Field(min_length=1)
    typography: str = Field(min_length=1)
    invariants: list[str] = Field(min_length=1)
    freedom: list[str] = Field(min_length=1)
    evidence_notes: list[str] = Field(min_length=1)
