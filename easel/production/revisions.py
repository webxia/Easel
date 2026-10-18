"""Version-bound natural language revision, with deterministic protection of unaffected media."""
from __future__ import annotations
from dataclasses import replace
import asyncio
import json
from typing import Literal
from pydantic import Field
from .contracts import Contract
from .creation import CreativeEdit, project_editor_features
from .material_intent import VisualIntent
from .editors import EditProject, assert_local_revision, EditError
from .artifacts import artifact_file,register_file
from .errors import ProductionError, StaleRevision
from .model_tasks import ModelTaskError
from .service import row,fail,encode,now,new_id,digest


def request_revision(service,conn,work,data):
    service._ensure_idle(conn,work)
    output=row(conn,'artifacts',data.get('output_id',''))
    if output['work_id']!=work['id'] or output['output_revision'] is None or output.get('deleted_at') or not output['displayable']:fail('invalid_input','请选择本作品的具体成片版本')
    feedback=str(data.get('feedback','')).strip()
    if not feedback or len(feedback)>10000:fail('invalid_input','请输入需要修改的具体内容')
    if type(data.get('preserve_audio',False)) is not bool:fail('invalid_input','声音保护选项须为布尔值')
    if type(data.get('render_only',False)) is not bool:fail('invalid_input','重新导出选项须为布尔值')
    source_run=row(conn,'runs',output['run_id'])
    render_payload=None
    if data.get('render_only'):
        # Re-export an immutable registered project; do not ask a model to
        # reconstruct it or turn an acknowledged semantic failure into a pass.
        metadata=json.loads(output['metadata_json'])
        project=row(conn,'artifacts',metadata.get('project_id',''))
        if project['work_id']!=work['id'] or project['kind']!='edit_project' or project.get('deleted_at'):
            fail('invalid_input','此版本没有可重新导出的有效剪辑工程')
        base=EditProject.model_validate_json(artifact_file(service,project).read_text())
        confirmed=conn.execute('SELECT confirmed_at FROM plan_revisions WHERE work_id=? AND revision=?',
            (work['id'],source_run['plan_revision'])).fetchone()
        if base.work_id!=work['id'] or base.plan_revision!=source_run['plan_revision'] or not confirmed or not confirmed[0]:
            fail('invalid_input','剪辑工程与此版本的已确认方案不匹配')
        notes=json.loads(project['metadata_json']).get('unverified_editor_notes',[])
        failed=conn.execute("SELECT 1 FROM quality_checks WHERE artifact_id=? AND artifact_digest=? AND check_kind='semantic' AND status IN ('fail','partial')",
            (output['id'],output['digest'])).fetchone()
        if failed or any(str(note).startswith('PENDING_VISUAL_MATCH') for note in notes):
            fail('semantic_findings_require_review','此版仍有已知内容或画面缺口，请先局部修正，不能仅重新导出')
        deps=[r[0] for r in conn.execute('SELECT dependency_id FROM artifact_edges WHERE artifact_id=?',(project['id'],))]
        render_payload={'project_id':project['id'],'asset_ids':deps,'render_only':True,'source_output_id':output['id']}
    review_id=new_id()
    conn.execute('INSERT INTO reviews(id,work_id,output_id,feedback,created_at) VALUES (?,?,?,?,?)',(review_id,work['id'],output['id'],feedback,now()))
    # Bind to the selected version, never guess the newest file.
    if work['current_plan_revision']!=source_run['plan_revision']:
        work=service._change(conn,work,current_plan_revision=source_run['plan_revision'])
    run=service._run(conn,work,'revision',plan_revision=source_run['plan_revision'],target=output['id'],payload={
        'review_id':review_id,'output_id':output['id'],'preserve_audio':data.get('preserve_audio',False),**(render_payload or {})})
    if render_payload:
        conn.execute("UPDATE tasks SET kind='render' WHERE run_id=? AND kind='revise'",(run,))
        service._event(conn,work['id'],'render_only_requested',{'output_id':output['id'],'project_id':render_payload['project_id']},run_id=run)
    return {'work_id':work['id'],'run_id':run,'review_id':review_id}


class RevisionProposal(Contract):
    summary: str = Field(min_length=1)
    affected: list[Literal['visual','captions','audio','content','materials']] = Field(min_length=1)
    expands_scope: bool
    requires_new_generation: bool
    reason: str
    edit: CreativeEdit
    material_searches: list[VisualIntent] = Field(default_factory=list,max_length=4)


class RevisionTasks:
    def __init__(self,service,planning,creation,*,supply=None):
        self.service,self.planning,self.creation,self.supply=service,planning,creation,supply

    async def _observe(self,records,*,audio_native):
        from .inspection import observe_media
        blocks=[];required={'text','structured'}
        visual_count=sum(r['kind'] in {'image','video'} for r in records)
        frame_limit=max(2,min(4,96//max(1,visual_count)))
        for record in records:
            if record['kind']=='font':continue
            blocks.append({'type':'text','text':'实际候选素材句柄 '+record['id']})
            media,needs,_=await asyncio.to_thread(observe_media,artifact_file(self.service,record),
                include_audio=audio_native,max_frames=frame_limit)
            blocks.extend(media);required.update(needs)
        return blocks,required

    async def revise(self,ctx):
        from .worker import TaskResult
        try:
            with self.service.store.connection() as conn:
                review=row(conn,'reviews',ctx.payload['review_id'])
                output=row(conn,'artifacts',ctx.payload['output_id'])
                metadata=json.loads(output['metadata_json'])
                project_record=row(conn,'artifacts',metadata['project_id'])
                deps=[r[0] for r in conn.execute('SELECT dependency_id FROM artifact_edges WHERE artifact_id=?',(project_record['id'],))]
            if review['work_id']!=ctx.work_id or output['work_id']!=ctx.work_id:raise ValueError('foreign revision')
            base=EditProject.model_validate_json(artifact_file(self.service,project_record).read_text())
            # Freeze the original candidate set before any paid request. Newly
            # acquired candidates must not change a resumed request fingerprint.
            with ctx.transaction() as conn:
                payload=json.loads(row(conn,'tasks',ctx.task_id)['payload_json'])
                if 'revision_asset_ids' not in payload:
                    extras=[r[0] for r in conn.execute("""SELECT a.id FROM artifacts a JOIN runs r ON r.id=a.run_id
                        WHERE a.work_id=? AND r.plan_revision=? AND a.deleted_at IS NULL AND a.kind IN ('image','video')
                        ORDER BY a.created_at,a.id LIMIT 32""",(ctx.work_id,ctx.plan_revision))]
                    payload['revision_asset_ids']=list(dict.fromkeys([*deps,*extras]))
                    conn.execute('UPDATE tasks SET payload_json=? WHERE id=?',(encode(payload),ctx.task_id))
            records,_=self.creation.assets(ctx,payload['revision_asset_ids'])
            context=self.planning.context(ctx)
            base_data={'base_edit':{k:v for k,v in base.model_dump(mode='json').items() if k not in {'work_id','plan_revision','revision'}},
                       'protected':'未指出部分保持不变','preserve_audio':payload.get('preserve_audio',False)}
            def candidate_context(items):
                return replace(context,brief=context.brief+'\n用户对指定版本的反馈：'+review['feedback'],
                    artifacts=(base_data,*({'asset_id':r['id'],'kind':r['kind'],'metadata':{
                        k:v for k,v in json.loads(r['metadata_json']).items() if k in {'source','rights','scene_ids','role','duration','segment_id','text','technical'}}} for r in items)),
                    allowed_handles=context.allowed_handles|frozenset(r['id'] for r in items))
            from .inspection import observe_media
            audio_native=bool(self.planning.transport and 'audio' in self.planning.transport.capabilities)
            media,required,_=await asyncio.to_thread(observe_media,artifact_file(self.service,output),include_audio=audio_native,max_frames=12)
            if not audio_native:
                media=(*media,{'type':'text','text':'原片音轨未由模型听取。保留声音时逐字节复用原音频资产与完整AudioClip，不改声线、文本、时间或音量；不得声称已试听或音画语义通过。'})
            observations,needs=await self._observe(records,audio_native=audio_native)
            instruction=('解释本次局部修改范围并返回完整编辑时间线。未指出部分不得改写；保留scene_id、时长、转场、旁白和字幕文本/时间。'
                'preserve_audio=true时AudioClip必须逐字段原样返回，包括声音身份、at、duration、gain。'
                '先实际复查全部候选，禁止把未观察过的文件名当画面事实。可用同方案合格库存替换用户要求修复的画面。关键动作必须发生在实际source_start至source_start+duration内，不能用源片尾部动作冒充选取前段；technical.duration_seconds给出源片真实长度。'
                '缺少关键主体或动作时，在material_searches列出最多4个本方案场景的简短英文主体/动作搜索词，options最多4、media_types仅image/video；'
                '这里只补指定镜头的库存，不重做方案、配音或生成媒体。此时edit先保持原版，说明缺口而非给无关概念画面；没有缺口则material_searches=[]。'
                '仅实际新增文案/时长/生成需求才设expands_scope/requires_new_generation；不要把本次已明确要求的现有素材替换与字幕样式修复误作整片重建。'
                '字幕对比不足时可以使用明确的深色半透明背景与较清楚的描边，保留文字和时间。')
            proposal=await self.planning.runner(ctx).run(candidate_context(records),instruction,RevisionProposal,
                media=(*media,*observations),required=frozenset(set(required)|needs))
            if proposal.material_searches and not (proposal.expands_scope or proposal.requires_new_generation):
                if not self.supply:raise ModelTaskError('material_gap','局部库存补料尚不可用，原版与配音已保留')
                new_ids=await asyncio.to_thread(self.supply.revision_visuals,ctx,[s.model_dump(mode='json') for s in proposal.material_searches])
                records,_=self.creation.assets(ctx,list(dict.fromkeys([*payload['revision_asset_ids'],*new_ids])))
                observations,needs=await self._observe(records,audio_native=audio_native)
                proposal=await self.planning.runner(ctx,namespace='revision-stock-selection-v1',max_format_repairs=2).run(
                    candidate_context(records),instruction+'本轮有限库存补料已经完成，不能再次请求检索。根据实际新候选完成修订；仍缺关键动作时在edit.unresolved_scene_ids明确报告并停止，不能改用无关画面。',
                    RevisionProposal,media=(*media,*observations),required=frozenset(set(required)|needs))
                if proposal.material_searches:raise ModelTaskError('visual_material_gap','有限库存补料后仍缺所需画面，保留原片并等待处理')
            with ctx.transaction() as conn:
                conn.execute('UPDATE reviews SET changes_json=? WHERE id=?',(encode({'schema_version':1,**proposal.model_dump(mode='json'),'base_digest':output['digest']}),review['id']))
                self.service._event(conn,ctx.work_id,'revision_proposed',{'review_id':review['id'],'summary':proposal.summary,'affected':proposal.affected},run_id=ctx.run_id)
            if proposal.expands_scope or proposal.requires_new_generation or not set(proposal.affected)<={'visual','captions','audio','materials'}:
                return TaskResult(state='needs_decision',work_state='needs_decision',error=ProductionError('revision_scope_confirmation',proposal.summary+'。'+proposal.reason,requires_decision=True),result={'review_id':review['id']})
            edit,notes=project_editor_features(proposal.edit)
            revised=EditProject.model_validate({**base.model_dump(), 'revision':base.revision+1,**edit.model_dump()})
            if payload.get('preserve_audio') and (revised.audio!=base.audio or
                    [(s.source_audio,s.source_gain) for s in revised.scenes]!=[(s.source_audio,s.source_gain) for s in base.scenes]):
                raise EditError('本次要求保留声音，修订不能改变原音频资产、时间位置、增益或原声设置')
            protected=base
            allowed=set(proposal.affected)-{'materials'}
            if 'materials' in proposal.affected:allowed.add('visual')
            if 'visual' in allowed:
                # Replacing a silent picture can reuse every audio byte. A source-audio
                # clip is protected because swapping its media would also swap speech.
                adjusted=[]
                for before,after in zip(base.scenes,revised.scenes):
                    if before.asset_id!=after.asset_id or before.source_start!=after.source_start:
                        if before.source_audio or after.source_audio:raise EditError('更换原声画面涉及声音内容，请明确拆分或重新确认方案')
                        if after.asset_id not in {r['id'] for r in records}:raise EditError('新画面尚未取得可用素材与使用权')
                        before=before.model_copy(update={'asset_id':after.asset_id,'source_start':after.source_start})
                    adjusted.append(before)
                protected=base.model_copy(update={'scenes':tuple(adjusted)})
            assert_local_revision(protected,revised,allowed=allowed)
            from .material_binding import selected_asset_ids
            records,manifest=self.creation.assets(ctx,[r['id'] for r in records if r['id'] in selected_asset_ids(revised)])
            check=self.creation.editor.check(revised,manifest)
            if not check.valid:raise EditError('；'.join(check.diagnostics))
            folder=self.service.outputs/'_production'/'projects'/ctx.task_id;folder.mkdir(parents=True,exist_ok=True)
            path=folder/'revision.json';path.write_text(revised.model_dump_json(),encoding='utf8')
            artifact=register_file(self.service,ctx,path,kind='edit_project',media_type='application/json',metadata={'base_project_id':project_record['id'],'review_id':review['id'],
                'audio_observation':'model_native' if audio_native else 'technical_only_unverified','audio_preserved':revised.audio==base.audio,'unverified_editor_notes':notes},dependencies=list(manifest.assets))
            return TaskResult(result={'review_id':review['id'],'project_id':artifact['id']},next_kind='render',next_payload={'project_id':artifact['id'],'asset_ids':list(manifest.assets),'repair_round':ctx.payload.get('repair_round',0)})
        except StaleRevision:
            raise
        except (ModelTaskError,EditError,ProductionError) as exc:
            return TaskResult(state='needs_decision',work_state='needs_decision',error=ProductionError(getattr(exc,'code','revision_scope_changed'),getattr(exc,'user_message',str(exc)),requires_decision=True))


def confirm_revision_scope(service,conn,work,data):
    review=row(conn,'reviews',data.get('review_id',''))
    if review['work_id']!=work['id']:fail('invalid_input','修订不属于当前作品')
    changes=json.loads(review['changes_json'])
    if not changes.get('summary') or digest(changes)!=data.get('change_hash'):
        fail('stale_revision','修订影响已变化，请重新查看',409)
    active=row(conn,'runs',work['active_run_id']) if work['active_run_id'] else None
    pending=conn.execute("SELECT payload_json FROM tasks WHERE run_id=? AND kind='revise' AND state='needs_decision'",(active['id'],)).fetchone() if active else None
    if not active or active['kind'] not in {'revision','production'} or active['state']!='needs_decision' or not pending or json.loads(pending[0]).get('review_id')!=review['id']:
        fail('invalid_input','当前没有等待确认的此项修订')
    conn.execute("UPDATE runs SET state='superseded',owner_epoch=owner_epoch+1,updated_at=? WHERE id=?",(now(),active['id']))
    conn.execute("UPDATE tasks SET state='cancelled',updated_at=? WHERE run_id=? AND state!='succeeded'",(now(),active['id']))
    if data.get('services'):service._insert_grant(conn,work,'planning',data)
    run=service._run(conn,work,'planning',target=review['id'],payload={'base_plan_revision':active['plan_revision'],
        'request':'根据指定旧版本与已明确同意的修改范围提出新版完整方案，保留未受影响内容。用户反馈：'+review['feedback']+'。已确认影响：'+changes['summary']+'。'+changes.get('reason','')})
    service._event(conn,work['id'],'revision_scope_confirmed',{'review_id':review['id'],'planning_run_id':run},run_id=run)
    return {'work_id':work['id'],'run_id':run}
