"""Version-bound natural language revision, with deterministic protection of unaffected media."""
from __future__ import annotations
from dataclasses import replace
import asyncio
import json
import re
from typing import Literal
from pydantic import Field, model_validator
from .contracts import Contract
from .edit_observation import VisualSelection
from .creation import CreativeEdit, project_editor_features, align_editor_frames, compensate_edit_overlap
from .editors.base import Scene
from .creative_captions import CreativeCaption
from .material_intent import VisualIntent
from .editors import EditProject, assert_local_revision, EditError
from .artifacts import artifact_file,register_file
from .errors import ProductionError, StaleRevision
from .model_tasks import ModelTaskError
from .service import row,fail,encode,now,new_id,digest
from .creative_captions import edit_data, check_caption_layout


def revision_feedback_text(feedback):
    """Present verified source text without exposing its transport envelope.

    Stored feedback remains intact for provenance and model input.
    """
    try:
        value=json.loads(feedback)
    except (ValueError,TypeError):
        return feedback
    if not (isinstance(value,dict) and set(value)=={'user_sources','agent_request'}
            and isinstance(value['agent_request'],str) and isinstance(value['user_sources'],list)
            and all(isinstance(s,dict) and isinstance(s.get('text'),str) for s in value['user_sources'])):
        return feedback
    return '\n'.join(dict.fromkeys([s['text'] for s in value['user_sources']]+[value['agent_request']]))


def check_revision_caption_identity(base, revised, caption_roles):
    remaining={c.caption_id for c in revised.captions}
    before=[(c.caption_id,c.text,c.start,c.end) for c in base.captions
            if c.caption_id in remaining or caption_roles.get(c.caption_id)!='overlay']
    after=[(c.caption_id,c.text,c.start,c.end) for c in revised.captions]
    if before!=after:
        old={c.caption_id:c for c in base.captions}
        new={c.caption_id:c for c in revised.captions}
        added=[key for key in new if key not in old]
        changed=[key for key in old if key in new and
                 (old[key].text,old[key].start,old[key].end)!=(new[key].text,new[key].start,new[key].end)]
        removed=[key for key in old if key not in new and caption_roles.get(key)!='overlay']
        detail=encode({'added_caption_ids':added[:12],'changed_text_or_timing_ids':changed[:12],
                       'removed_protected_ids':removed[:12]})
        raise ValueError('局部修订文字/时间身份变化：'+detail+
            '。保持原caption_id及text/start/end；只需排版时改size/max_width/x/y/background，渲染器按max_width自动换行，不必拆成新文字条目。'
            '移除已登记overlay请用remove_caption_ids；旁白或角色未知字幕不可删除。真正改写文字须走正式改稿，不得新增或改名绕过保护；原顺序也须保留。')


def revision_output(conn,work,data):
    # Shared by proposal and execution: a plan is not a rendered output.
    output=conn.execute('SELECT * FROM artifacts WHERE id=?',(data.get('output_id',''),)).fetchone()
    if not output:
        plan=conn.execute('SELECT confirmed_at FROM plan_revisions WHERE work_id=? AND revision=?',
                          (work['id'],work['current_plan_revision'])).fetchone()
        if plan and not plan['confirmed_at']:
            fail('plan_revision_required','当前修改对象是未确认方案。改稿请使用已有plan入口，intent=replan，request写修改范围并引用本轮user_quote；已有规划授权不重复确认。不要重建成片修订提案。',409)
        fail('revision_target_missing','没有找到指定成片版本，请读取当前作品选择真实output_id；这不是对话提案丢失，不要要求重复确认。',409)
    output=dict(output)
    if output['work_id']!=work['id'] or output['output_revision'] is None or output.get('deleted_at') or not output['displayable']:fail('invalid_input','请选择本作品的具体成片版本')
    return output


def request_revision(service,conn,work,data):
    service._ensure_idle(conn,work)
    output=revision_output(conn,work,data)
    feedback=str(data.get('feedback','')).strip()
    if not feedback or len(feedback)>10000:fail('invalid_input','请输入需要修改的具体内容')
    if type(data.get('preserve_audio',False)) is not bool:fail('invalid_input','声音保护选项须为布尔值')
    if type(data.get('render_only',False)) is not bool:fail('invalid_input','重新导出选项须为布尔值')
    scope=data.get('scope','edit')
    if not isinstance(scope,str) or scope not in {'edit','narration','boards'}:fail('invalid_input','不支持的修订范围')
    if scope in {'narration','boards'} and data.get('render_only') or scope=='narration' and data.get('preserve_audio'):
        fail('invalid_input','改稿重配不能同时要求保留音轨或仅重新导出')
    if 'duration_seconds' in data:
        if scope != 'edit' or data.get('render_only') or data.get('preserve_audio'):
            fail('invalid_input','收短尾部需允许音乐剪短，不能同时冻结全部音轨或改稿')
        source_project=row(conn,'artifacts',json.loads(output['metadata_json'])['project_id'])
        from .narration import trim_confirmed_ending
        try:
            trim_confirmed_ending(EditProject.model_validate_json(artifact_file(service,source_project).read_text()),data['duration_seconds'])
        except (EditError,ValueError) as exc:
            fail('invalid_input',str(exc))
    source_run=row(conn,'runs',output['run_id'])
    if scope=='narration':
        plan=json.loads(conn.execute('SELECT payload_json FROM plan_revisions WHERE work_id=? AND revision=?',
            (work['id'],source_run['plan_revision'])).fetchone()[0])
        if plan['settings']['audio_mode'] not in {'voice','mixed'}:fail('invalid_input','改稿重配需要含旁白的作品；保留BGM和音效模式，不改成纯旁白')
        if any(json.loads(r[0]).get('original_audio') for r in conn.execute('SELECT metadata_json FROM work_inputs WHERE work_id=?',(work['id'],))):
            fail('invalid_input','保留原声的作品尚不支持改稿重配')
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
        failed=service._has_known_quality_failure(conn,output)
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
        'review_id':review_id,'output_id':output['id'],'preserve_audio':data.get('preserve_audio',False),'scope':scope,**({'duration_seconds':data['duration_seconds']} if 'duration_seconds' in data else {}),**(render_payload or {})})
    if render_payload:
        conn.execute("UPDATE tasks SET kind='render' WHERE run_id=? AND kind='revise'",(run,))
        service._event(conn,work['id'],'render_only_requested',{'output_id':output['id'],'project_id':render_payload['project_id']},run_id=run)
    return {'work_id':work['id'],'run_id':run,'review_id':review_id}


class SceneReplacement(Contract):
    scene_id: str
    scenes: list[Scene] = Field(min_length=1)


class RevisionChanges(Contract):
    scenes: list[SceneReplacement] = Field(default_factory=list)
    captions: list[CreativeCaption] = Field(default_factory=list)
    remove_caption_ids: list[str] = Field(default_factory=list, description='仅删除已登记为overlay的独立叠加文字；旁白字幕不得删除。')
    visual_evidence: list[VisualSelection] = Field(default_factory=list)


class RevisionSummary(Contract):
    summary: str = Field(min_length=1)
    affected: list[Literal['visual','captions','audio','content','materials']] = Field(min_length=1)
    expands_scope: bool
    requires_new_generation: bool
    reason: str
    material_searches: list[VisualIntent] = Field(default_factory=list,max_length=4,
        description='仅列仍阻止本轮完成的必要补料；已获许可且能实际落实的替代方案所放弃的理想素材写reason，不列入此处。非空会触发补料或暂停，不是一般局限清单。')


REVISION_MATERIAL_SCOPE = (
    '先结合用户明确要求、adaptation_permissions与实际画面判断本轮仍须满足的条件，不把检查建议自动升级为用户必需素材。'
    '用户允许替代且现有画面能够落实时，执行具体替代，在reason说明许可依据、实际改动与剩余局限；'
    '仅未达到的理想效果或已允许不提供的原始记录，不进入material_searches。'
    '允许示意不等于允许误导：用户明确必需的真实素材、不可替代的核心动作、实际画面与事实冲突仍须解决；'
    '不能只给画面标illustrative或写“不作证据”就宣布解决，须结合选用区间及实际呈现说明为何不误导。'
    'material_searches只表达未解决且阻止完成的必要素材条件，reason逐项说明受损要求和现有候选不能解决的原因；'
    '不要用它登记已接受替代后的理想素材愿望。程序不会替你删除请求或判断语义。'
)


class VisualRevisionProposal(RevisionSummary):
    model_config = {"title":"RevisionProposal"}
    changes: RevisionChanges


class RevisionProposal(RevisionSummary):
    edit: CreativeEdit | None = None
    changes: RevisionChanges | None = None

    @model_validator(mode='after')
    def one_edit(self):
        if (self.edit is None) == (self.changes is None):
            raise ValueError('只提供changes局部修改或edit完整工程其中一个')
        return self


def merge_revision_changes(proposal, base, *, caption_roles=None):
    """Apply addressed replacements; omitted scenes, captions and audio inherit."""
    if proposal.changes is None:
        return proposal.edit
    changes=proposal.changes
    replacements={c.scene_id:c.scenes for c in changes.scenes}
    known={s.scene_id for s in base.scenes}
    if len(replacements)!=len(changes.scenes) or set(replacements)-known:
        raise ValueError('局部修改必须引用不重复的已登记镜头ID')
    captions={c.caption_id:c for c in changes.captions}
    if len(captions)!=len(changes.captions):raise ValueError('局部字幕ID重复')
    removed=set(changes.remove_caption_ids)
    if (len(removed)!=len(changes.remove_caption_ids) or removed & captions.keys()
        or not removed <= {c.caption_id for c in base.captions}
        or any((caption_roles or {}).get(key)!='overlay' for key in removed)):
        raise ValueError('只能删除不重复、已登记为overlay且未同时修改的独立文字；不能删除旁白或未知字幕')
    data={k:v for k,v in base.model_dump().items() if k in CreativeEdit.model_fields}
    data.update(scenes=[s.model_dump() for old in base.scenes for s in replacements.get(old.scene_id,[old])],
        captions=[captions.pop(c.caption_id,c).model_dump() for c in base.captions if c.caption_id not in removed],
        visual_evidence=[v.model_dump() for v in changes.visual_evidence])
    data['captions'].extend(c.model_dump() for c in captions.values())
    return CreativeEdit.model_validate(data)


def stored_caption_roles(conn, project_record, base):
    """Read roles from the producing receipt when an older revision omitted metadata."""
    metadata=json.loads(project_record['metadata_json'])
    if metadata.get('caption_roles') is not None:return metadata['caption_roles']
    if not metadata.get('review_id') or not base.captions:return {}
    review=conn.execute('SELECT changes_json FROM reviews WHERE id=?',(metadata.get('review_id',''),)).fetchone()
    if not review:return {}
    edit=json.loads(review['changes_json'] or '{}').get('edit') or {}
    actual={c.caption_id:c for c in base.captions}
    return {c['caption_id']:c.get('role','narration') for c in edit.get('captions',[])
            if c.get('caption_id') in actual and (c.get('text'),c.get('start'),c.get('end')) ==
               (actual[c['caption_id']].text,actual[c['caption_id']].start,actual[c['caption_id']].end)}


def revised_caption_roles(base, edit, roles):
    original_ids={c.caption_id for c in base.captions}
    return {c.caption_id:(roles.get(c.caption_id,'narration') if c.caption_id in original_ids else c.role)
            for c in edit.captions}


def compile_revision_edit(edit, base):
    try:
        return align_editor_frames(compensate_edit_overlap(edit,target_seconds=base.duration,fps=base.fps),fps=base.fps)
    except ModelTaskError:
        actual=sum(s.duration-s.transition_seconds for s in edit.scenes)
        raise ValueError(f'修订时间线净长{actual:.3f}秒，原片{base.duration:.3f}秒，差值{actual-base.duration:+.3f}秒；转场重叠计入净长，不得补尾凑长') from None


def revision_recovery_messages(messages, instruction, result_type=RevisionProposal):
    # Keep evidence/history, but a new repair must use the current contract.
    # The stored receipt/request stays immutable; caller verified its identity.
    result=[dict(message) for message in messages]
    if result and result[0].get('role')=='system':
        prefix=result[0]['content'].split('\n任务：',1)[0]
        result[0]['content']=prefix+'\n任务：'+instruction+'\n输出schema：'+encode(result_type.model_json_schema())
    return result


def revision_plan_searches(plan, base, searches):
    """Translate registered timeline shots to frozen Plan identities for supply.

    Do not rewrite the edit, model receipt, or stock acquisition's Plan guard.
    A suffix alone is insufficient: the shot must exist in the base project.
    """
    plan_ids={s['id'] for s in plan['scenes']}
    shot_ids={s.scene_id for s in base.scenes}
    result=[]
    for search in searches:
        identity=search.scene_id
        if identity not in plan_ids and identity in shot_ids:
            # Existing recuts can themselves be split on a later revision.
            while identity not in plan_ids and re.search(r'(?:-cut|_)[1-9][0-9]*$',identity):
                identity=re.sub(r'(?:-cut|_)[1-9][0-9]*$','',identity)
        if identity not in plan_ids:
            raise ModelTaskError('invalid_revision_search','局部补料场景 '+search.scene_id+' 未映射到原方案；拆镜必须来自已登记剪辑')
        if identity in {s['scene_id'] for s in result}:
            raise ModelTaskError('invalid_revision_search','局部补料场景 '+identity+' 重复；同一原场景只能保留一条简短检索词，不同拆镜也须合并为一条请求')
        if len(result)>=4:
            raise ModelTaskError('invalid_revision_search','局部补料单次最多4个不重复的原方案场景')
        result.append({**search.model_dump(mode='json'),'scene_id':identity})
    return result


def recorded_proposal(service,ctx,review,output):
    """Recover a known native answer after post-model validation, never resend it."""
    if not review.get('changes_json'):return None
    saved=json.loads(review['changes_json'])
    if set(saved)<= {'schema_version'}:return None
    if saved.get('base_digest')!=output['digest']:
        raise ModelTaskError('revision_basis_changed','已收到的修订方案不属于此成片，不能复用或盲重发')
    proposal=RevisionProposal.model_validate({k:v for k,v in saved.items() if k in RevisionProposal.model_fields})
    if saved.get('producer_task_id')==ctx.task_id:return proposal
    # Compatibility with pre-checkpoint answers already persisted by V2.
    with service.store.connection() as conn:
        receipts=conn.execute("SELECT receipt_json FROM operations WHERE task_id=? AND kind='MODEL' AND state='succeeded'",(ctx.task_id,)).fetchall()
    for receipt in receipts:
        try:
            content=json.loads(receipt[0])['result']['message']['content']
            from .model_tasks import parse_model_json
            if RevisionProposal.model_validate(parse_model_json(content))==proposal:return proposal
        except (ValueError,KeyError,TypeError):continue
    raise ModelTaskError('revision_provenance_missing','修订方案缺少本任务已成功模型回执，未重新发送模型')


class RevisionTasks:
    def __init__(self,service,planning,creation,*,supply=None):
        self.service,self.planning,self.creation,self.supply=service,planning,creation,supply

    async def _observe(self,records,*,audio_native,observed=None,budget=None):
        from .inspection import observe_media
        blocks=[];required={'text','structured'}
        visual_count=sum(r['kind'] in {'image','video'} for r in records)
        frame_limit=max(2,min(4,96//max(1,visual_count)))
        for record in records:
            if record['kind']=='font':continue
            if budget is not None:
                if record['kind'] not in {'image','video'}:continue
                if record['id'] not in budget.observed:
                    await budget.observe(record['id'],artifact_file(self.service,record),max_frames=2)
                if observed is not None:observed.update(budget.observed)
                continue
            blocks.append({'type':'text','text':'实际候选素材句柄 '+record['id']})
            media,needs,evidence=await asyncio.to_thread(observe_media,artifact_file(self.service,record),
                include_audio=audio_native,max_frames=frame_limit)
            if observed is not None:observed[record['id']]=evidence.get('frame_times',[])
            blocks.extend(media);required.update(needs)
        return (list(budget.media),set(budget.required)) if budget is not None else (blocks,required)

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
            if 'duration_seconds' in ctx.payload:
                from .narration import trim_confirmed_ending
                from .material_binding import selected_asset_ids
                revised=trim_confirmed_ending(base,ctx.payload['duration_seconds'])
                records,manifest=self.creation.assets(ctx,[x for x in deps if x in selected_asset_ids(revised)])
                check=self.creation.editor.check(revised,manifest)
                if not check.valid:raise EditError('；'.join(check.diagnostics))
                folder=self.service.outputs/'_production'/'projects'/ctx.task_id
                folder.mkdir(parents=True,exist_ok=True)
                path=folder/'revision.json';path.write_text(revised.model_dump_json(),encoding='utf8')
                artifact=register_file(self.service,ctx,path,kind='edit_project',media_type='application/json',
                    metadata={'base_project_id':project_record['id'],'review_id':review['id'],
                              'execution_timing':{'mode':'confirmed_ending','duration':revised.duration},
                              'caption_roles':json.loads(project_record['metadata_json']).get('caption_roles')},
                    dependencies=list(manifest.assets))
                return TaskResult(result={'review_id':review['id'],'project_id':artifact['id']},next_kind='render',
                    next_payload={'project_id':artifact['id'],'asset_ids':list(manifest.assets),'repair_round':1,'reuse_existing_media_only':ctx.payload.get('reuse_existing_media_only',False)})
            if ctx.payload.get('repair_scope')=='protected_timing_or_content' or ctx.payload.get('scope') in {'narration','boards'}:
                # A known QC finding outside visual-only authority needs the
                # existing scope confirmation, not another paid creative call.
                board_revision=ctx.payload.get('scope')=='boards'
                proposal=RevisionProposal(summary='请确认图解状态与高亮修订，保留口播和声音设置' if board_revision else '请确认涉及旁白、字幕时码或内容的修订范围',
                    affected=['visual','content','materials'] if board_revision else ['audio','captions','content'],expands_scope=True,requires_new_generation=ctx.payload.get('scope')=='narration',
                    reason=(revision_feedback_text(review['feedback'])+'。生成新版图解方案及受影响图片，沿用口播与声音；确认新版方案后制作。') if board_revision else revision_feedback_text(review['feedback'])+'。确认后先改稿提出新版方案；新版制作确认后重新配音、按实测声音对齐字幕与画面，可能新增模型和配音消耗。保持音色和确认片长，不自动制作。',
                    edit=CreativeEdit.model_validate({k:v for k,v in base.model_dump().items()
                        if k in {'scenes','audio','captions','required_features'}}))
                with ctx.transaction() as conn:
                    conn.execute('UPDATE reviews SET changes_json=? WHERE id=?',
                        (encode({'schema_version':1,**proposal.model_dump(mode='json'),
                                 'base_digest':output['digest'],'producer_task_id':ctx.task_id,
                                 'source':'boards_scope' if board_revision else ('narration_scope' if ctx.payload.get('scope')=='narration' else 'quality_scope')}),review['id']))
                return TaskResult(state='needs_decision',work_state='needs_decision',
                    error=ProductionError('revision_scope_confirmation',proposal.summary+'。'+proposal.reason,
                                          requires_decision=True),result={'review_id':review['id'],'output_id':output['id']})
            # Freeze the original candidate set before any paid request. Newly
            # acquired candidates must not change a resumed request fingerprint.
            with ctx.transaction() as conn:
                payload=json.loads(row(conn,'tasks',ctx.task_id)['payload_json'])
                if 'revision_asset_ids' not in payload:
                    extras=[r[0] for r in conn.execute("""SELECT a.id FROM artifacts a JOIN runs r ON r.id=a.run_id
                        WHERE a.work_id=? AND r.plan_revision=? AND a.deleted_at IS NULL AND a.kind IN ('image','video')
                        ORDER BY a.created_at,a.id LIMIT 32""",(ctx.work_id,ctx.plan_revision))]
                    payload['revision_asset_ids']=list(dict.fromkeys([*deps,*extras]))
                    # Freeze policy before the first request. Existing tasks keep
                    # their old observation shape for durable operation replay.
                    if payload.get('creative_visual_repair'):
                        payload['observation_policy']='targeted-v1'
                    conn.execute('UPDATE tasks SET payload_json=? WHERE id=?',(encode(payload),ctx.task_id))
            candidate_ids=payload['revision_asset_ids']
            if payload.get('revision_recovery_source'):
                # A paused stock-selection receipt already saw these acquired
                # candidates. Restore only this task's durable search results;
                # creation.assets still enforces identity, files and usage rights.
                # Keep the original frozen set unchanged for operation replay.
                supplied=[ref for result in payload.get('revision_search_results',{}).values()
                          for ref in result.get('asset_ids',[])]
                candidate_ids=list(dict.fromkeys([*candidate_ids,*supplied]))
            records,_=self.creation.assets(ctx,candidate_ids)
            context=self.planning.context(ctx)
            creative_repair=bool(payload.get('creative_visual_repair') and context.plan.get('narration_policy'))
            from .visual_repair import approved_overlay_texts, assert_visual_repair
            with self.service.store.connection() as conn:
                caption_roles=stored_caption_roles(conn,project_record,base)
            protected_styles=({c.caption_id for c in base.captions if caption_roles.get(c.caption_id,'narration')=='narration'}
                if caption_roles is not None else set())
            if (context.plan.get('narration_policy') or {}).get('duration_mode') == 'voice_driven':
                from copy import deepcopy
                measured = deepcopy(context.plan)
                measured['settings']['duration_seconds'] = base.duration
                context = replace(context, plan=measured, brief=context.brief+'\n修订执行长度来自原片实测，不表示Creator重新确认过此片长；原确认方案及本轮反馈仍须分别核对。')
            base_data={'base_edit':{k:v for k,v in base.model_dump(mode='json').items() if k not in {'work_id','plan_revision','revision'}},
                       'protected':'未指出部分保持不变','preserve_audio':payload.get('preserve_audio',False),
                       'reuse_existing_media_only':payload.get('reuse_existing_media_only',False),
                       'review_output':{'asset_id':output['id'],'duration':base.duration,
                           'usage':'只读复查本次修订的成片；时间为成片时间，不是候选素材源时间；不能用作替换素材'},
                       'duration_basis':{'source':'existing_output','seconds':base.duration}}
            if caption_roles is not None:base_data['caption_roles']=caption_roles
            # Give the editor actual mix arithmetic before authoring a repair.
            # Existing visual-only repairs keep their bounded observation policy.
            if not creative_repair and not payload.get('preserve_audio'):
                from .inspection import observe_audio_technical
                from .narration import closing_mix_evidence
                measures = {}
                for record in records:
                    clips = [a for a in base.audio if a.asset_id == record['id']]
                    if record['kind'] == 'audio' and clips:
                        clip = clips[0]
                        measures[record['id']] = await asyncio.to_thread(
                            observe_audio_technical, artifact_file(self.service, record),
                            source_start=clip.source_start, sample_seconds=min(15, clip.duration))
                base_data['closing_mix_evidence'] = closing_mix_evidence(base, measures)

            def candidate_context(items):
                return replace(context,editor_view=True,brief=context.brief+'\n用户对指定版本的反馈：'+review['feedback'],
                    artifacts=(base_data,*({'asset_id':r['id'],'kind':r['kind'],'metadata':json.loads(r['metadata_json'])} for r in items)),
                    allowed_handles=context.allowed_handles|frozenset([output['id'],*(r['id'] for r in items)]))
            from .inspection import observe_media
            audio_native=bool(self.planning.transport and 'audio' in self.planning.transport.capabilities)
            from .edit_observation import ObservationBudget
            budget = ObservationBudget() if creative_repair and payload.get('observation_policy')=='targeted-v1' else None
            if budget is not None:
                affected=set(payload.get('affected_scene_ids',[]))
                selected=[s for s in base.scenes if not affected or s.scene_id in affected]
                wanted={s.asset_id for s in selected}
                # The source ranges actually in use come first. Other candidate
                # metadata stays visible and can be inspected on demand.
                initial=[r for r in records if r['id'] in wanted][:12]
                times = [at+scene.duration/2 for scene,at in zip(base.scenes,base.scene_starts()) if scene in selected]
                await budget.observe(output['id'],artifact_file(self.service,output),
                    frame_times=times[:8] if affected and times else None,max_frames=8)
                for record in initial:
                    if record['kind']=='video':
                        ranges=[s for s in selected if s.asset_id==record['id']]
                        await budget.observe(record['id'],artifact_file(self.service,record),
                            frame_times=list(dict.fromkeys(s.source_start+s.duration/2 for s in ranges))[:2])
                media, required = (), frozenset(budget.required)
            else:
                initial=records
                media,required,_=await asyncio.to_thread(observe_media,artifact_file(self.service,output),include_audio=audio_native,max_frames=12)
            if not audio_native or budget is not None:
                media=(*media,{'type':'text','text':'原片音轨未由模型听取。保留声音时逐字节复用原音频资产与完整AudioClip，不改声线、文本、时间或音量；不得声称已试听或音画语义通过。'})
            observed={}
            observations,needs=await self._observe(initial,audio_native=audio_native,observed=observed,budget=budget)
            from .edit_observation import check_visual_evidence, VISUAL_EVIDENCE_INSTRUCTION
            from .narration import ENDING_INSTRUCTION
            instruction=(ENDING_INSTRUCTION + VISUAL_EVIDENCE_INSTRUCTION + REVISION_MATERIAL_SCOPE + '修订reason逐项回应已有findings：实际改动、仍阻断的缺陷与不阻断的局限分开说明；不能只声称问题已解决。'
                '解释本次局部修改范围，优先返回changes：scenes按已登记scene_id替换该镜头（可拆镜），captions只列改动项；未列项及全部AudioClip由原工程继承，visual_evidence列实际选择证据。不要重写整份工程。仅需调整独立音轨时使用edit。未指出部分不得改写；保留scene_id、时长、转场、旁白和字幕文本/时间。'
                'preserve_audio=true时独立AudioClip继承原版；使用完整edit时逐字段保留，包括声音身份、at、duration、gain。'
                '含原声镜头的素材、source_start、duration、source_gain、实际时间线位置须保持；可改crop、frame、fit、motion等纯画面字段，不通过替换镜头意外移除或新增原声。'
                'preserve_audio=false且用户反馈涉及声音时，可调整现有音轨gain/fade_in/fade_out，保留素材身份、完整配音、位置和时长；复用配音资产不等于冻结混音参数。'
                '先实际复查全部候选，禁止把未观察过的文件名当画面事实。可用同方案合格库存替换用户要求修复的画面。关键动作必须发生在实际source_start至source_start+duration内，不能用源片尾部动作冒充选取前段；technical.duration_seconds给出源片真实长度。'
                '仍缺本轮不可替代的关键主体或动作时，在material_searches列出最多4个本方案场景的简短英文主体/动作搜索词，options最多4、media_types仅image/video；'
                '这里只补指定镜头的库存，不重做方案、配音或生成媒体。此时edit先保持原版，说明缺口而非给无关概念画面；没有缺口则material_searches=[]。'
                '仅实际新增文案/时长/生成需求才设expands_scope/requires_new_generation；不要把本次已明确要求的现有素材替换与字幕样式修复误作整片重建。'
                '字幕对比不足时可以使用明确的深色半透明背景与较清楚的描边，保留文字和时间。')
            if creative_repair:
                instruction = instruction.replace('保留scene_id、时长、转场、旁白和字幕文本/时间。', '保留叙事身份、全部原字幕字句及旁白时码；镜头与独立叠加文字调时以下述视觉修复范围为准。')
                instruction += ('本次是原生视觉复核触发的画面修复：保留完整AudioClip、全部原字幕字句、旁白与角色未知字幕时码、总长度及原场景顺序。'
                    '已登记caption_roles=overlay的原文字条目可在原所属镜头窗口内调整start/end以匹配旁白步骤，保持原caption_id和text；不是允许改旁白时间。'
                    '情境素材需要披露来源属性时，仅支持新增固定叠加“情境示意，非来源原图”，不可扩写为机构/数据断言；不因加标签免除画面事实匹配，其他新增文字仍须来自方案明确提示语。'
                    '允许原场景拆成多个镜头，scene_id采用原ID或原ID-cut1、原ID-cut2等，允许相邻场景重新分配镜头时长，保持总时长、原叙事顺序和全部原旁白时码，画面应与实际旁白对应；'
                    '这属于既有视觉修复，不因拆镜就扩大内容范围。只用实际候选或有界补料，不能用相似关键词的错误物件冒充所需画面。'
                    '解释不足时可以补方案中已有的提示语，文字仅可取自以下列表，不能新增事实或观点：'
                    +encode(approved_overlay_texts(context.plan)))
                if protected_styles:instruction+='旁白字幕的频道样式、透明背景及位置必须原样保留，不能为了对比度擅改为底框；独立解释字才可布局。'
            if budget is not None:
                instruction=instruction.replace('先实际复查全部候选，', '优先复核失败场景及实际选用区间，其他候选按需观察，')
                instruction+='本次观察有共享帧预算，已观察时点复用；预算耗尽不必继续请求，基于已有证据完成或明确缺口，不把未观察素材当事实。'
            result_type=VisualRevisionProposal if creative_repair or payload.get('preserve_audio') else RevisionProposal
            if result_type is VisualRevisionProposal:
                instruction+='本轮输出仅允许changes局部变更，禁止edit完整工程；未改镜头、字幕与所有独立音轨由原工程继承。没有修改的列表留空。'
            instruction+='需要移除已登记overlay独立文字时，使用changes.remove_caption_ids列其ID；不可用空格覆盖。旁白和角色未知的字幕禁止删除。'
            def normalize(candidate):
                proposal=RevisionProposal.model_validate(candidate.model_dump(mode='json'))
                compiled=compile_revision_edit(merge_revision_changes(proposal,base,caption_roles=caption_roles),base)
                return proposal.model_copy(update={'edit':compiled,'changes':None})

            source_durations={}
            def check_sources(edit):
                from .media import probe_media
                from .creation import check_edit_source_bounds
                selected={s.asset_id for s in edit.scenes}
                for record in records:
                    if record['kind']=='video' and record['id'] in selected and record['id'] not in source_durations:
                        source_durations[record['id']]=probe_media(artifact_file(self.service,record))['duration']
                check_edit_source_bounds(edit,source_durations,target_seconds=base.duration,fps=base.fps)

            reconsider_materials = bool(ctx.payload.get('revision_material_recovery'))
            def check_creative_repair(candidate):
                nonlocal reconsider_materials
                from .model_tasks import ResultCorrectionError
                if reconsider_materials:
                    reconsider_materials = False
                    if candidate.material_searches:
                        raise ResultCorrectionError('这是已成功返回但因必要素材请求而暂停的原回执；本次恢复只使用现有素材，不再补料。重新核对这些请求是否仍是不可替代条件，不能直接复用旧结论。' + REVISION_MATERIAL_SCOPE)
                try:
                    candidate=normalize(candidate)
                except ValueError as exc:
                    raise ResultCorrectionError(str(exc)) from None
                errors=[]
                def collect(check):
                    try:check()
                    except (EditError,ValueError) as exc:errors.append(str(exc))
                collect(lambda: check_sources(candidate.edit))
                collect(lambda: check_visual_evidence(candidate.edit,observed,pending_materials=bool(candidate.material_searches)))
                if not creative_repair and not (candidate.expands_scope or candidate.requires_new_generation):
                    collect(lambda: check_revision_caption_identity(base,candidate.edit,caption_roles))
                if candidate.material_searches and not (candidate.expands_scope or candidate.requires_new_generation):
                    try:revision_plan_searches(context.plan,base,candidate.material_searches)
                    except ModelTaskError as exc:errors.append(exc.user_message)
                if creative_repair and not (candidate.material_searches or candidate.expands_scope or candidate.requires_new_generation):
                    try:
                        draft=EditProject.model_validate({**base.model_dump(),'revision':base.revision+1,**edit_data(candidate.edit)})
                    except ValueError as exc:
                        errors.append(str(exc))
                    else:
                        collect(lambda: assert_visual_repair(base,draft,overlay_texts=approved_overlay_texts(context.plan),protected_caption_style_ids=protected_styles,allow_retiming=True,caption_roles=caption_roles))
                        from .boards import check_board_usage
                        collect(lambda: check_board_usage(draft.scenes,records))
                        collect(lambda: check_caption_layout(draft.captions,font_paths={r['id']:artifact_file(self.service,r) for r in records if r['kind']=='font'},width=base.width,height=base.height))
                if errors:
                    # A format/timing repair must not fossilize an earlier stock
                    # request. Re-evaluate its necessity under the same authority;
                    # no semantic inference or removal of searches by the program.
                    raise ResultCorrectionError('；'.join(errors) + '。' + REVISION_MATERIAL_SCOPE)
            from .edit_observation import edit_observation_tools
            def observation_tools(items):
                if not self.planning.transport or 'tools' not in self.planning.transport.capabilities:return ()
                paths={r['id']:artifact_file(self.service,r)
                    for r in items if r['kind']=='video' or (budget is not None and r['kind']=='image')}
                # The selected version is verified above; never admit unrelated
                # outputs or make the composite a replacement source candidate.
                paths[output['id']]=artifact_file(self.service,output)
                return edit_observation_tools(paths,observed,budget=budget)
            instruction += '关键动作或切点不能由现有抽样确认时，可用inspect_media复查候选指定时间或review_output中的本次成片。成片时间与素材源时间分别使用；成片只供复查，不是替换素材，不臆测未观察区间。'
            instruction+='已登记原镜头ID：'+encode([s.scene_id for s in base.scenes])+'。拆镜必须用该完整ID再加-cut1/-cut2，不能用Plan场景ID替代已登记镜头ID。'
            recovery=None
            recovery_source=ctx.payload.get('revision_recovery_source')
            if recovery_source:
                with self.service.store.connection() as conn:
                    source=dict(row(conn,'operations',recovery_source))
                if (source['task_id']!=ctx.task_id or source['work_id']!=ctx.work_id or source['run_id']!=ctx.run_id
                    or source['state']!='succeeded' or source['config_version']!=self.planning.config_version
                    or any(source[k]!=v for k,v in self.planning.model_service.items())):
                    raise ModelTaskError('revision_recovery_invalid','修订恢复来源与本次已知结果不符')
                request=json.loads(source['request_json']);message=json.loads(source['receipt_json'])['result']['message']
                if request['schema'].get('title')!='RevisionProposal' or any(
                        call.get('function',{}).get('name')!='inspect_media' for call in message.get('tool_calls',[])):
                    raise ModelTaskError('revision_recovery_invalid','修订恢复来源不是已知提案')
                for prior in request['messages']:
                    if prior.get('role')!='tool':continue
                    try:evidence=json.loads(prior['content'])
                    except (ValueError,TypeError):continue
                    if not isinstance(evidence,dict) or evidence.get('asset_id') not in {output['id'],*(r['id'] for r in records)}:continue
                    key=evidence['asset_id'];times=evidence.get('frame_times',[])
                    observed[key]=list(dict.fromkeys([*observed.get(key,[]),*times]))
                    if budget is not None:budget.observed[key]=observed[key]
                recovery=(revision_recovery_messages(request['messages'],instruction,result_type),message)
            # An explicit resume corrects a known rejected result under a new
            # operation identity; never replay its invalid compiled checkpoint.
            proposal=None if recovery is not None else recorded_proposal(self.service,ctx,review,output)
            reused=proposal is not None
            if proposal is None:
                proposal=await self.planning.runner(ctx,namespace=('revision-repair-'+recovery_source[:32]) if recovery_source else None,max_format_repairs=2 if creative_repair else 1).run(candidate_context(records),instruction,result_type,
                    media=(*media,*observations),required=frozenset(set(required)|needs),tools=observation_tools(records),validate_result=check_creative_repair, recovery=recovery, expression_role="visual")
            if not reused:proposal=normalize(proposal)
            if proposal.material_searches and payload.get('reuse_existing_media_only'):
                raise ModelTaskError('material_gap','本次只允许复用已有素材与配音；当前修订需要新增素材，原成果已保留')
            if proposal.material_searches and not (proposal.expands_scope or proposal.requires_new_generation):
                if not self.supply:raise ModelTaskError('material_gap','局部库存补料尚不可用，原版与配音已保留')
                searches=revision_plan_searches(context.plan,base,proposal.material_searches)
                new_ids=await asyncio.to_thread(self.supply.revision_visuals,ctx,searches)
                records,_=self.creation.assets(ctx,list(dict.fromkeys([*payload['revision_asset_ids'],*new_ids])))
                observations,needs=await self._observe(
                    [r for r in records if r['id'] in new_ids] if budget is not None else records,
                    audio_native=audio_native,observed=observed,budget=budget)
                proposal=await self.planning.runner(ctx,namespace='revision-stock-selection-v1',max_format_repairs=2).run(
                    candidate_context(records),instruction+'本轮有限库存补料已经完成，不能再次请求检索。按上述许可与实际画面区分必要缺口和已接受替代后的局限：可执行替代则完成修订；仍缺不可替代条件才在material_searches报告并停止（不会再次检索），不能改用无关画面。',
                    result_type,media=(*media,*observations),required=frozenset(set(required)|needs),tools=observation_tools(records),validate_result=check_creative_repair, expression_role="visual")
                proposal=normalize(proposal)
                if proposal.material_searches:raise ModelTaskError('visual_material_gap','有限库存补料后仍缺所需画面，保留原片并等待处理')
            with ctx.transaction() as conn:
                if not reused:
                    conn.execute('UPDATE reviews SET changes_json=? WHERE id=?',(encode({'schema_version':1,**proposal.model_dump(mode='json'),'base_digest':output['digest'],'producer_task_id':ctx.task_id}),review['id']))
                self.service._event(conn,ctx.work_id,'revision_proposal_reused' if reused else 'revision_proposed',{'review_id':review['id'],'summary':proposal.summary,'affected':proposal.affected},run_id=ctx.run_id)
            if proposal.expands_scope or proposal.requires_new_generation or not set(proposal.affected)<={'visual','captions','audio','materials'}:
                return TaskResult(state='needs_decision',work_state='needs_decision',error=ProductionError('revision_scope_confirmation',proposal.summary+'。'+proposal.reason,requires_decision=True),result={'review_id':review['id']})
            try:
                proposal=proposal.model_copy(update={'edit':compile_revision_edit(merge_revision_changes(proposal,base,caption_roles=caption_roles),base),'changes':None})
            except ValueError as exc:
                raise ModelTaskError('invalid_model_output',str(exc)) from None
            edit,notes=project_editor_features(proposal.edit)
            revised=EditProject.model_validate({**base.model_dump(), 'revision':base.revision+1,**edit_data(edit)})
            if payload.get('preserve_audio') and (revised.audio!=base.audio or
                    (not creative_repair and [(s.source_audio,s.source_gain) for s in revised.scenes]!=[(s.source_audio,s.source_gain) for s in base.scenes])):
                raise EditError('本次要求保留声音，修订不能改变原音频资产、时间位置、增益或原声设置')
            protected=base
            allowed=set(proposal.affected)-{'materials'}
            if 'materials' in proposal.affected:allowed.add('visual')
            if 'visual' in allowed and not creative_repair:
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
            if creative_repair:
                assert_visual_repair(base,revised,overlay_texts=approved_overlay_texts(context.plan),protected_caption_style_ids=protected_styles,allow_retiming=True,caption_roles=caption_roles)
                from .boards import check_board_usage
                try:check_board_usage(revised.scenes,records)
                except ValueError as exc:raise EditError(str(exc)) from None
                check_caption_layout(revised.captions,font_paths={r['id']:artifact_file(self.service,r) for r in records if r['kind']=='font'},
                    width=base.width,height=base.height)
            else:
                assert_local_revision(protected,revised,allowed=allowed,
                    removable_caption_ids={key for key,role in caption_roles.items() if role=='overlay'})
            from .material_binding import selected_asset_ids
            records,manifest=self.creation.assets(ctx,[r['id'] for r in records if r['id'] in selected_asset_ids(revised)])
            check=self.creation.editor.check(revised,manifest)
            if not check.valid:raise EditError('；'.join(check.diagnostics))
            folder=self.service.outputs/'_production'/'projects'/ctx.task_id;folder.mkdir(parents=True,exist_ok=True)
            path=folder/'revision.json';path.write_text(revised.model_dump_json(),encoding='utf8')
            artifact=register_file(self.service,ctx,path,kind='edit_project',media_type='application/json',metadata={'base_project_id':project_record['id'],'review_id':review['id'],
                'caption_roles':revised_caption_roles(base,edit,caption_roles),
                'execution_timing':json.loads(project_record['metadata_json']).get('execution_timing'),
                'audio_observation':'model_native' if audio_native else 'technical_only_unverified','audio_preserved':revised.audio==base.audio,'visual_evidence':[e.model_dump() for e in edit.visual_evidence],'unverified_editor_notes':notes},dependencies=list(manifest.assets))
            return TaskResult(result={'review_id':review['id'],'project_id':artifact['id']},next_kind='render',next_payload={'project_id':artifact['id'],'asset_ids':list(manifest.assets),'repair_round':ctx.payload.get('repair_round',0),'reuse_existing_media_only':payload.get('reuse_existing_media_only',False)})
        except StaleRevision:
            raise
        except (ModelTaskError,EditError,ProductionError) as exc:
            return TaskResult(state='needs_decision',work_state='needs_decision',error=ProductionError(getattr(exc,'code','revision_scope_changed'),getattr(exc,'user_message',str(exc)),requires_decision=True))


def revision_confirmation(conn,work,data):
    review=conn.execute('SELECT * FROM reviews WHERE id=?',(data.get('review_id',''),)).fetchone()
    if not review:fail('revision_review_missing','没有对应的实际修订记录；review_id不是对话proposal_id。请读取真实任务状态；未确认方案改稿走plan、intent=replan，不重建确认提案。',409)
    review=dict(review)
    if review['work_id']!=work['id']:fail('invalid_input','修订不属于当前作品')
    changes=json.loads(review['changes_json'] or '{}')
    if not changes.get('summary') or digest(changes)!=data.get('change_hash'):
        fail('stale_revision','修订影响已变化，请重新查看',409)
    active=row(conn,'runs',work['active_run_id']) if work['active_run_id'] else None
    pending=conn.execute("SELECT payload_json FROM tasks WHERE run_id=? AND kind='revise' AND state='needs_decision'",(active['id'],)).fetchone() if active else None
    if not active or active['kind'] not in {'revision','production'} or active['state']!='needs_decision' or not pending or json.loads(pending[0]).get('review_id')!=review['id']:
        fail('invalid_input','当前没有等待确认的此项修订')
    return review,changes,active,pending


def confirm_revision_scope(service,conn,work,data):
    review,changes,active,pending=revision_confirmation(conn,work,data)
    conn.execute("UPDATE runs SET state='superseded',owner_epoch=owner_epoch+1,updated_at=? WHERE id=?",(now(),active['id']))
    conn.execute("UPDATE tasks SET state='cancelled',updated_at=? WHERE run_id=? AND state!='succeeded'",(now(),active['id']))
    if data.get('services'):service._insert_grant(conn,work,'planning',data)
    run=service._run(conn,work,'planning',target=review['id'],payload={'base_plan_revision':active['plan_revision'],
        'revision_scope':json.loads(pending[0]).get('scope','edit'),
        'request':'根据指定旧版本与已明确同意的修改范围提出新版完整方案，保留未受影响内容。用户反馈：'+review['feedback']+'。已确认影响：'+changes['summary']+'。'+changes.get('reason','')})
    service._event(conn,work['id'],'revision_scope_confirmed',{'review_id':review['id'],'planning_run_id':run},run_id=run)
    return {'work_id':work['id'],'run_id':run}
