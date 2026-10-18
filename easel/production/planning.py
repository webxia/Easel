"""Planning tasks bind creative answers to program-owned immutable plan revisions."""
from __future__ import annotations
import json
import re
from pydantic import Field, model_validator
from .contracts import Contract, Scene, VideoSettings
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
                f'45秒分镜旁白预留失败（{exc.code}）：{exc.user_message}。'
                '请大幅压缩每个场景 narration 的真实口播字数，'
                '确保所有场景总长仍为45秒，并保留固定音色与导演风格。'
            ) from None
        return self


class PlanningTasks:
    def __init__(self, service, operations, transport, model_service, config_version):
        self.service, self.operations, self.transport = service, operations, transport
        self.model_service, self.config_version = model_service, config_version
        self.tool_factory=lambda ctx: ()

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
                media,needs,_=await asyncio.to_thread(observe_media,path,include_audio=True,max_frames=8)
                blocks.extend(media);required.update(needs)
        return tuple(blocks),frozenset(required)

    async def plan(self,ctx):
        from .worker import TaskResult
        try:
            cached=self._committed_result(ctx)
            if cached:
                return TaskResult(result=cached,work_state='awaiting_confirmation')
            context=self.context(ctx)
            media,required=await self.observe_inputs(ctx)
            proposed=await self.runner(ctx,max_format_repairs=2).run(context,
                '提出完整创作方案；遵守明确时长、画幅、声音设置；全部必用输入须落实到场景。'
                'Scene.narration 只能是将由 TTS 实际朗读的简短口播原文，不能包含时间码、朗读窗口、'
                '停顿/换气/语速说明、其他导演注释或舞台指令；这类说明写入 script/visual。'
                '中文口播要有明显时间余量，不超过冻结时长预算；所有镜头累计时长仍须精确。'
                '返回摘要、完整脚本、场景和视听设计。',VoiceReadyCreativePlan,
                media=media,required=required,tools=self.tool_factory(ctx))
            with ctx.transaction() as conn:
                work=row(conn,'works',ctx.work_id)
                from .voice_budget import reserve_narration_slots
                payload=self.service.freeze_plan(conn,work,reserve_narration_slots(proposed.model_dump(mode='json')),basis=ctx.payload.get('creation_basis'))
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
                media,needs,evidence=await asyncio.to_thread(observe_media,path,include_audio=True)
                blocks.append({'type':'text','text':'导演参考输入句柄 '+item['id']+'；以下实际媒体仅用于风格证据，不代表主人设经历。'})
                blocks.extend(media);required.update(needs)
                observations.append({'input_id':item['id'],'digest':item['digest'],**evidence})
            answer=await self.runner(ctx).run(self.context(ctx),
                '根据实际参考画面和音轨拆解可跨题材复用的视听风格、叙事方式和变化边界。不要将参考中的人物事实变成主人设，也不要固定脚本套路。',
                DirectorAnalysis,required=frozenset(required),media=tuple(blocks))
            with ctx.transaction() as conn:
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
