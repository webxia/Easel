"""Business handlers for edit -> durable render -> technical and semantic review."""
from __future__ import annotations
import asyncio
from dataclasses import replace
import json
from pathlib import Path
from pydantic import Field
from .contracts import Contract
from .editors import AssetManifest, MediaAsset, Scene, AudioClip, Caption, EditProject, FFmpegEditor, EditError
from .artifacts import register_file, artifact_file
from .inspection import observe_media
from .model_tasks import ModelTaskError
from .errors import ProductionError
from .service import row,encode,now,new_id


class CreativeEdit(Contract):
    scenes: list[Scene] = Field(min_length=1)
    audio: list[AudioClip] = Field(default_factory=list)
    captions: list[Caption] = Field(default_factory=list)
    required_features: list[str] = Field(default_factory=list)


class SemanticReview(Contract):
    verdict: str = Field(pattern='^(pass|fail|partial)$')
    factual_fidelity: str = Field(min_length=1)
    style_consistency: str = Field(min_length=1)
    narrative_coherence: str = Field(min_length=1)
    audiovisual_alignment: str = Field(min_length=1)
    findings: list[str]
    limitations: list[str]


class CreationTasks:
    def __init__(self,service,planning,editor=None,voice_tasks=None):
        self.service,self.planning=service,planning
        self.voice_tasks=voice_tasks
        self.editor=editor or FFmpegEditor(service.outputs/'_production'/'renders')

    def assets(self,ctx,ids):
        with self.service.store.connection() as conn:
            records=[row(conn,'artifacts',id) for id in ids]
        for item in records:
            if item['work_id']!=ctx.work_id or item['kind'] not in {'image','video','audio','font'}:
                raise ModelTaskError('invalid_asset','素材不属于当前作品或类型不可用')
            artifact_file(self.service,item)
        manifest=AssetManifest(root=self.service.outputs,assets={r['id']:MediaAsset(locator=r['storage_ref'],sha256=r['digest'],kind=r['kind']) for r in records})
        return records,manifest

    async def edit(self,ctx):
        from .worker import TaskResult
        try:
            context=self.planning.context(ctx)
            asset_ids=ctx.payload.get('asset_ids',[])
            if self.voice_tasks:
                asset_ids,outcome=await self.voice_tasks.prepare_assets(ctx,context.plan,asset_ids)
                if outcome:return outcome
            records,manifest=self.assets(ctx,asset_ids)
            context=replace(context,artifacts=tuple({'asset_id':r['id'],'kind':r['kind'],'metadata':json.loads(r['metadata_json'])} for r in records),allowed_handles=context.allowed_handles|frozenset(manifest.assets))
            observations=[];required={'text','structured'}
            for record in records:
                if record['kind']=='font':continue
                media,needs,_=await asyncio.to_thread(observe_media,artifact_file(self.service,record),include_audio=record['kind'] in {'video','audio'},max_frames=4)
                observations.append({'type':'text','text':'候选素材句柄 '+record['id']})
                observations.extend(media);required.update(needs)
            answer=await self.planning.runner(ctx).run(context,
                '把已确认方案落实为精确剪辑时间线。只能使用给定素材句柄；逐场景决定裁剪、运动、转场、音轨和字幕。时长须精确，旁白与原声不能循环。缺素材不能用无关素材替代。字幕必须有真实字体素材。',CreativeEdit,media=tuple(observations),required=frozenset(required))
            settings=context.plan['settings'];horizontal=settings['aspect_ratio']=='16:9'
            from .contracts import SubtitleSettings
            from .subtitles import caption_from_settings
            style=SubtitleSettings.model_validate(settings.get('subtitles',{}))
            fonts={json.loads(r['metadata_json']).get('font_name'):r['id'] for r in records if r['kind']=='font'}
            if not style.enabled and answer.captions:
                raise ModelTaskError('subtitle_disabled','方案关闭了字幕，剪辑不能擅自添加')
            captions=[caption_from_settings(style,caption_id=c.caption_id,text=c.text,start=c.start,end=c.end,fonts=fonts) for c in answer.captions]
            data=answer.model_dump();data['captions']=captions
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
            from .voice import sentence_segments
            expected_segments=[scene['id']+'-'+segment['segment_id'] for scene in context.plan['scenes'] for segment in sentence_segments(scene.get('narration',''))]
            voiced={r['id']:json.loads(r['metadata_json']) for r in records if json.loads(r['metadata_json']).get('role')=='voice'}
            spoken=sorted((a for a in project.audio if a.asset_id in voiced),key=lambda a:a.at)
            expected=[segment for segment in expected_segments if segment in {m.get('segment_id') for m in voiced.values()}]
            if [voiced[a.asset_id].get('segment_id') for a in spoken]!=expected or any(a.at+a.duration>b.at+.02 for a,b in zip(spoken,spoken[1:])):
                raise ModelTaskError('narration_order_changed','旁白句段不能倒序或互相覆盖播放')
            if style.enabled and spoken and not project.captions:
                raise ModelTaskError('subtitles_missing','已开启字幕的旁白不能省略字幕')
            check=await asyncio.to_thread(self.editor.check,project,manifest)
            if not check.valid:raise ModelTaskError(check.code or 'editor_rejected','；'.join(check.diagnostics))
            temp=self.service.outputs/'_production'/'projects'/ctx.task_id
            temp.mkdir(parents=True,exist_ok=True)
            path=temp/'project.json';path.write_text(project.model_dump_json(),encoding='utf8')
            artifact=register_file(self.service,ctx,path,kind='edit_project',media_type='application/json',metadata={'plan_revision':ctx.plan_revision},dependencies=list(manifest.assets))
            return TaskResult(result={'project_id':artifact['id']},next_kind='render',next_payload={'project_id':artifact['id'],'asset_ids':list(manifest.assets)})
        except (ModelTaskError,EditError) as exc:
            return TaskResult(state='needs_decision',error=ProductionError(getattr(exc,'code','invalid_edit'),getattr(exc,'user_message',str(exc)),requires_decision=True),work_state='needs_decision')

    async def render(self,ctx):
        from .worker import TaskResult
        with self.service.store.connection() as conn:record=row(conn,'artifacts',ctx.payload['project_id'])
        if record['work_id']!=ctx.work_id:raise ValueError('cross-work project')
        project=EditProject.model_validate_json(artifact_file(self.service,record).read_text())
        records,manifest=self.assets(ctx,ctx.payload['asset_ids'])
        job=await asyncio.to_thread(self.editor.build,project,manifest,job_id=ctx.task_id)
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
        return TaskResult(result={'output_id':artifact['id']},next_kind='quality',next_payload={'output_id':artifact['id'],'project_id':record['id'],'repair_round':ctx.payload.get('repair_round',0)})

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
        try:
            from .quality import review_full_video
            def progress(completed,total,segment):
                with ctx.transaction() as conn:
                    self.service._event(conn,ctx.work_id,'quality_progress',{'completed_segments':completed,'total_segments':total,
                        'start':segment['start'],'end':segment['end'],'verdict':segment['review']['verdict']},run_id=ctx.run_id)
            answer=await review_full_video(path,cache_root=self.service.outputs/'works'/ctx.work_id/'inspection'/ctx.task_id,
                info=info,transport=self.planning.transport,runner=self.planning.runner(ctx),
                context=self.planning.context(ctx),review_type=SemanticReview,on_segment=progress)
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

    def _check(self,ctx,artifact,kind,status,findings):
        with ctx.transaction() as conn:
            conn.execute('INSERT INTO quality_checks(id,artifact_id,artifact_digest,check_kind,rule_version,status,findings_json,created_at) VALUES (?,?,?,?,?,?,?,?)',
                (new_id(),artifact['id'],artifact['digest'],kind,'production-1',status,encode(findings),now()))
            self.service._event(conn,ctx.work_id,'quality_checked',{'output_id':artifact['id'],'kind':kind,'status':status},run_id=ctx.run_id)

    def _quality_state(self,ctx,artifact,state):
        with ctx.transaction() as conn:conn.execute('UPDATE artifacts SET quality_state=? WHERE id=?',(state,artifact['id']))
