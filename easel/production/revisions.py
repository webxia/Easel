"""Version-bound natural language revision, with deterministic protection of unaffected media."""
from __future__ import annotations
from dataclasses import replace
import asyncio
import json
from typing import Literal
from pydantic import Field
from .contracts import Contract
from .creation import CreativeEdit
from .editors import EditProject, assert_local_revision, EditError
from .artifacts import artifact_file,register_file
from .errors import ProductionError
from .model_tasks import ModelTaskError
from .service import row,fail,encode,now,new_id,digest


def request_revision(service,conn,work,data):
    service._ensure_idle(conn,work)
    output=row(conn,'artifacts',data.get('output_id',''))
    if output['work_id']!=work['id'] or output['output_revision'] is None or output.get('deleted_at') or not output['displayable']:fail('invalid_input','请选择本作品的具体成片版本')
    feedback=str(data.get('feedback','')).strip()
    if not feedback or len(feedback)>10000:fail('invalid_input','请输入需要修改的具体内容')
    source_run=row(conn,'runs',output['run_id'])
    review_id=new_id()
    conn.execute('INSERT INTO reviews(id,work_id,output_id,feedback,created_at) VALUES (?,?,?,?,?)',(review_id,work['id'],output['id'],feedback,now()))
    # Bind to the selected version, never guess the newest file.
    if work['current_plan_revision']!=source_run['plan_revision']:
        work=service._change(conn,work,current_plan_revision=source_run['plan_revision'])
    run=service._run(conn,work,'revision',plan_revision=source_run['plan_revision'],target=output['id'],payload={'review_id':review_id,'output_id':output['id']})
    return {'work_id':work['id'],'run_id':run,'review_id':review_id}


class RevisionProposal(Contract):
    summary: str = Field(min_length=1)
    affected: list[Literal['visual','captions','audio','content','materials']] = Field(min_length=1)
    expands_scope: bool
    requires_new_generation: bool
    reason: str
    edit: CreativeEdit


class RevisionTasks:
    def __init__(self,service,planning,creation):self.service,self.planning,self.creation=service,planning,creation

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
            context=self.planning.context(ctx)
            context=replace(context,brief=context.brief+'\n用户对指定版本的反馈：'+review['feedback'],
                artifacts=({'base_edit':{k:v for k,v in base.model_dump(mode='json').items() if k not in {'work_id','plan_revision','revision'}},'protected':'未指出部分保持不变'},),
                allowed_handles=context.allowed_handles|frozenset(deps))
            from .inspection import observe_media
            media,required,_=await asyncio.to_thread(observe_media,artifact_file(self.service,output),include_audio=True,max_frames=12)
            proposal=await self.planning.runner(ctx).run(context,'解释本次局部修改范围并返回完整编辑时间线。未指出部分不得改写；涉及文案、素材替换、时长变化或新增生成时明确说明影响。仅现有素材的样式、字号、裁剪、音量调整可直接继续。',RevisionProposal,media=media,required=required)
            with ctx.transaction() as conn:
                conn.execute('UPDATE reviews SET changes_json=? WHERE id=?',(encode({'schema_version':1,**proposal.model_dump(mode='json'),'base_digest':output['digest']}),review['id']))
                self.service._event(conn,ctx.work_id,'revision_proposed',{'review_id':review['id'],'summary':proposal.summary,'affected':proposal.affected},run_id=ctx.run_id)
            if proposal.expands_scope or proposal.requires_new_generation or not set(proposal.affected)<={'visual','captions','audio','materials'}:
                return TaskResult(state='needs_decision',work_state='needs_decision',error=ProductionError('revision_scope_confirmation',proposal.summary+'。'+proposal.reason,requires_decision=True),result={'review_id':review['id']})
            revised=EditProject.model_validate({**base.model_dump(), 'revision':base.revision+1,**proposal.edit.model_dump()})
            protected=base
            allowed=set(proposal.affected)-{'materials'}
            if 'materials' in proposal.affected:allowed.add('visual')
            if 'visual' in allowed:
                # Replacing a silent picture can reuse every audio byte. A source-audio
                # clip is protected because swapping its media would also swap speech.
                adjusted=[]
                for before,after in zip(base.scenes,revised.scenes):
                    if before.asset_id!=after.asset_id:
                        if before.source_audio or after.source_audio:raise EditError('更换原声画面涉及声音内容，请明确拆分或重新确认方案')
                        if after.asset_id not in deps:raise EditError('新画面尚未取得可用素材与使用权')
                        before=before.model_copy(update={'asset_id':after.asset_id})
                    adjusted.append(before)
                protected=base.model_copy(update={'scenes':tuple(adjusted)})
            assert_local_revision(protected,revised,allowed=allowed)
            records,manifest=self.creation.assets(ctx,deps)
            check=self.creation.editor.check(revised,manifest)
            if not check.valid:raise EditError('；'.join(check.diagnostics))
            folder=self.service.outputs/'_production'/'projects'/ctx.task_id;folder.mkdir(parents=True,exist_ok=True)
            path=folder/'revision.json';path.write_text(revised.model_dump_json(),encoding='utf8')
            artifact=register_file(self.service,ctx,path,kind='edit_project',media_type='application/json',metadata={'base_project_id':project_record['id'],'review_id':review['id']},dependencies=deps)
            return TaskResult(result={'review_id':review['id'],'project_id':artifact['id']},next_kind='render',next_payload={'project_id':artifact['id'],'asset_ids':deps,'repair_round':ctx.payload.get('repair_round',0)})
        except (ModelTaskError,EditError) as exc:
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
