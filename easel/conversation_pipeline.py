"""Easel pending → answer → resume adapter; domain services own execution.

No provider calls, independent scheduler, or model-supplied user authority.
"""
from __future__ import annotations
import json
from .production.service import row, fail, encode, digest
from .production.catalog import CreativeCatalog
from .production.errors import ProductionError

WORK_ACTIONS = {
    'input': {'attachment_id','usage','original_audio','interval','rights_confirmed'},
    'plan': {'request','services','duration_seconds','settings','restore_cancelled','decision_id','intent'},
    'confirm': {'plan_revision','plan_hash','services','allow_ai','image_limit','video_limit'},
    'grant': {'purpose','services','allow_ai','image_limit','video_limit','target_ref','plan_revision','decision_id'},
    'resume': {'decision_id'}, 'cancel': set(),
    'replan_after_unknown': {'decision_id'},
    'basis': {'settings','input_text'},
    'revise': {'output_id','feedback','preserve_audio','scope','duration_seconds'},
    'confirm_revision': {'review_id','change_hash','services'},
    'accept': {'output_id','manual_review_confirmed'},
}
PUBLICATION_ACTIONS = {'publication_prepare': {'output_id'}, 'publication_save': {'draft_id','revision','changes'}}


def publications(conversations):
    from .production.publication import Publications
    from .publication_bilibili import BilibiliAdapter
    return Publications(conversations.service, BilibiliAdapter(conversations.service.outputs.parent))


CATALOG_ACTIONS = {'director_style','director_accept','channel_director'}


def planning_decision(conversations,conn,segment):
    return conn.execute("""SELECT t.* FROM tasks t JOIN works w ON w.active_run_id=t.run_id
        WHERE w.id=? AND t.kind='plan' AND t.state='needs_decision'
        AND json_extract(t.error_json,'$.code')='permission_missing'""",(segment['work_id'],)).fetchone()


def grant_values(conversations,conn,segment,values,*,applying=False):
    """Resolve the exact authority before proposing it, never after consent."""
    purpose=values.get('purpose')
    if purpose not in {'planning','preview','production'}:
        fail('invalid_input','授权提案须指定purpose：planning、preview或production；整理方案用planning')
    data=dict(values)
    if purpose=='planning' and 'services' not in data and not applying:
        from .production.configuration import model_configuration
        _,model,_=model_configuration(conversations.service.outputs.parent)
        if not model:fail('capability_unavailable','创作模型尚未配置，暂不能提出规划授权',409)
        data['services']=[model]
    services=data.get('services')
    if not isinstance(services,list) or not services or any(not isinstance(s,dict) or set(s)!={'provider','model','mode'} or any(not isinstance(v,str) or not v.strip() for v in s.values()) for s in services):
        fail('invalid_input','授权参数services必须是数组，每项仅含provider、model、mode三个非空字符串；不能含item、label或service。规划授权请重新offer grant，values只传{"purpose":"planning"}，由程序生成服务与恢复目标；不要重复提交旧提案')
    from .production.configuration import capabilities
    available=[{k:s[k] for k in ('provider','model','mode')} for s in capabilities(conversations.service.outputs.parent)['services'] if s.get('available')]
    if any(s not in available for s in services):
        fail('capability_unavailable','提案中的服务已不可用或不在当前能力目录，请重新核对服务后提出授权',409)
    for key in ('image_limit','video_limit'):
        if key in data and (type(data[key]) is not int or data[key]<0):fail('invalid_input','生成次数须为非负整数')
    if 'allow_ai' in data and type(data['allow_ai']) is not bool:fail('invalid_input','allow_ai须为布尔值')
    if purpose=='planning':
        planning_values(conversations,conn,segment,{'services':services},applying=True)
        decision=planning_decision(conversations,conn,segment)
        if decision and not data.get('decision_id'):
            if applying:fail('stale_revision','此旧授权提案未绑定暂停任务，请重新offer grant，values只传{"purpose":"planning"}，展示授权并继续原任务后确认',409)
            data['decision_id']=decision['id']
        if data.get('decision_id') and (not decision or decision['id']!=data['decision_id']):
            fail('stale_revision','待恢复的授权阻断已变化或不属于当前作品，请重新核对当前任务',409)
        if decision and conn.execute("SELECT 1 FROM operations WHERE run_id=? AND state IN ('reserved','sending','submitted','unknown')",(decision['run_id'],)).fetchone():
            fail('result_unknown','当前运行仍有外部请求待核实，不能通过补授权重发',409)
    elif data.get('decision_id'):
        fail('invalid_input','合并授权恢复仅用于当前整理方案的授权阻断',409)
    return data


def planning_values(conversations,conn,segment,values,*,applying=False):
    """Bind the model before asking; never expand an already approved proposal."""
    if set(values)-WORK_ACTIONS['plan']:fail('invalid_input','规划提案字段无效')
    work=row(conn,'works',segment['work_id']) if segment['work_id'] else None
    if 'intent' in values and values['intent']!='replan':fail('invalid_input','不支持的规划意图')
    if values.get('intent')=='replan':
        if not work or set(values)-{'intent','request','services'} or not str(values.get('request','')).strip():
            fail('invalid_input','重新规划须绑定当前作品并说明变更范围')
        conversations.service.replanning_target(conn,work)
    elif work and work['active_run_id'] and not values.get('decision_id') and 'settings' not in values:
        run=row(conn,'runs',work['active_run_id'])
        if run['kind']=='production' and run['state'] in {'needs_decision','paused','failed'}:
            fail('resume_required','请按本轮真实意图区分：继续原制作使用resume；用户明确要求重新规划时使用plan并传intent=replan和具体request；只重剪使用既有修订入口，不从暂停状态推断用户意图。',409)
    if values.get('decision_id'):
        conversations.service.failed_planning_target(conn,row(conn,'works',segment['work_id']),values['decision_id'])
        if set(values)-{'decision_id','request','services'}:fail('invalid_input','首次规划恢复须保持现有创作设置')
    if 'duration_seconds' in values:
        conversations.service._validate_settings({'duration_seconds':values['duration_seconds']})
    if 'settings' in values:
        conversations.service._validate_settings(values['settings'])
        conversations.service.preoutput_target(conn,row(conn,'works',segment['work_id']),values)
    from .production.configuration import model_configuration
    _,model,_=model_configuration(conversations.service.outputs.parent)
    if not model:fail('capability_unavailable','创作模型尚未配置，暂不能整理完整方案；请先配置可用模型',409)
    grants=conn.execute("SELECT services_json FROM authorization_grants WHERE work_id=? AND purpose='planning' AND revoked_at IS NULL",(segment['work_id'],)).fetchall()
    authorized=any(model in json.loads(g[0]) for g in grants)
    services=values.get('services',[])
    if not isinstance(services,list):fail('invalid_input','规划服务须为列表')
    if not applying and not services and not authorized:services=[model]
    if any(s!=model for s in services):fail('stale_revision','规划模型已变化或提案包含非规划服务，请在对话重新展示当前服务并确认',409)
    if not services and not authorized:
        fail('permission_missing','此旧提案未包含当前规划模型授权，请在对话重新展示规划服务并确认；尚未创建任务',409)
    return {**values,'services':services}



def unknown_replan_target(conversations, conn, segment, values):
    """Bind an explicit NEW planning attempt; never resume/reclassify UNKNOWN."""
    work = row(conn, 'works', segment['work_id'])
    task = conn.execute("SELECT * FROM tasks WHERE id=? AND work_id=? AND run_id=? AND kind='plan' AND state='needs_decision'",
                        (values.get('decision_id'), work['id'], work['active_run_id'])).fetchone()
    if not task or work['current_plan_revision'] is not None:
        fail('stale_revision', '当前没有可另行规划的未知结果阻断，请重新读取pending', 409)
    run = row(conn, 'runs', task['run_id'])
    if run['state'] != 'needs_decision' or run['owner_id'] or run['cancel_requested']:
        fail('stale_revision', '旧运行仍在执行或状态已变化，不能另行规划', 409)
    operations = [dict(r) for r in conn.execute('SELECT * FROM operations WHERE run_id=? ORDER BY id', (run['id'],))]
    unknown = [op for op in operations if op['state'] == 'unknown']
    if (not unknown or any(op['kind'] != 'MODEL' or op['task_id'] != task['id'] for op in unknown)
            or conn.execute("SELECT 1 FROM operations WHERE work_id=? AND state IN ('reserved','sending','submitted')", (work['id'],)).fetchone()):
        fail('result_unknown', '存在尚在执行的请求或非规划未知结果，不能通过此提案重开', 409)
    from .production.configuration import model_configuration
    settings, model, version = model_configuration(conversations.service.outputs.parent)
    if not model or any(any(op[k] != model[k] for k in model) for op in operations):
        fail('stale_revision', '规划模型与旧调用不一致，须另行核对，不能沿用本恢复提案', 409)
    # A fresh proposal can authorize a NEW attempt under current configuration.
    # Its target pins that configuration through answer; old operations and their
    # replay identity remain immutable. Never apply an old proposal after a change.
    config_changed = any(op['config_version'] != version for op in operations)
    payload = json.loads(task['payload_json'])
    basis = payload.get('creation_basis')
    if not basis or basis != conversations.service._basis(conn, work):
        fail('stale_revision', '创作依据已变化，须先核对变更，不能声称按旧依据重新规划', 409)
    if conn.execute('SELECT 1 FROM work_inputs WHERE work_id=? AND created_at>?', (work['id'], task['created_at'])).fetchone():
        fail('stale_revision', '旧调用后新增了素材，须先核对依据', 409)
    return {'task_id': task['id'], 'task_revision': task['revision'],
            'run_id': run['id'], 'run_revision': run['revision'],
            'operations': [{'id': op['id'], 'revision': op['revision'], 'state': op['state']} for op in operations],
            'basis_hash': digest(basis), 'config_version': version,
            'config_changed': config_changed,
            'reasoning_effort': settings.get('EASEL_PRODUCTION_REASONING_EFFORT', '').strip() or 'provider_default',
            'request': payload.get('request', ''), 'services': [model]}


def call_status(conversations, conn, segment):
    if not segment['work_id']: return {'diagnostics': [], 'recovery': None}
    diagnostics = [json.loads(r[0]) for r in conn.execute(
        "SELECT payload_json FROM events WHERE work_id=? AND kind='model_call_diagnostic' ORDER BY seq DESC LIMIT 5", (segment['work_id'],))]
    task = conn.execute("SELECT t.id FROM tasks t JOIN works w ON w.active_run_id=t.run_id WHERE w.id=? AND t.kind='plan' AND t.state='needs_decision' AND EXISTS (SELECT 1 FROM operations o WHERE o.task_id=t.id AND o.state='unknown')", (segment['work_id'],)).fetchone()
    recovery = None
    if task:
        recovery = {'can_offer': False, 'old_result': 'UNKNOWN', 'automatic_retry': False,
                    'note': '同步模型调用没有结果查询能力；没有诊断记录的旧调用不能补推超时分型。新尝试可能重复计费，必须另行展示并确认。'}
        try:
            unknown_replan_target(conversations, conn, segment, {'decision_id': task['id']})
            recovery.update(can_offer=True, next_action={'mode': 'offer', 'action': 'replan_after_unknown', 'values': {'decision_id': task['id']}})
        except ProductionError as exc:
            recovery.update(code=exc.code, reason=exc.user_message)
    return {'diagnostics': diagnostics, 'recovery': recovery}

def turn_context(context):
    """Project the current state for automatic injection; full reads stay available.

    Never replay finished proposals, full plans and task output blobs on every
    human turn. This is a view only: pending/context and confirmation authority
    continue to read the same durable records.
    """
    result={**context}
    result['context']={k:v for k,v in context['context'].items() if k!='profile_save_target'}
    result['context']['sources']=[{k:v for k,v in source.items() if k!='text'}
                                  for source in context['context'].get('sources',[])]
    result['pending']=[p for p in context['pending'] if p['state']=='proposed']
    work=context.get('work')
    if work:
        result['work']={k:v for k,v in work.items() if k not in {'plans','tasks','artifacts','creation_context','conversation_brief'}}
        result['work']['plans']=[{k:v for k,v in p.items() if k not in {'payload_json','plan'}} for p in work['plans']]
        result['work']['tasks']=[{k:v for k,v in t.items() if k in {'id','run_id','kind','state','error_json'}} for t in work['tasks']]
        result['work']['reviews']=[{k:v for k,v in review.items() if k not in {'changes_json','changes'}} for review in work.get('reviews',[])]
        result['work']['artifacts']=[output_summary(a) for a in work['artifacts'] if a['kind']=='output']
    plan=context.get('current_plan')
    result['current_plan']={k:v for k,v in plan.items() if k not in {'payload_json','plan'}} if plan else None
    result['detail_access']='这是当前状态摘要；sources仅列来源引用，正文通过easel_work_context读取，本轮原话在新消息区。历史提案和产物详情通过现有easel_pipeline pending传values.detail=full读取；画像保存目标及来源通过easel_work_context读取。摘要省略不代表记录被删除或授权改变。'
    return result


def output_summary(artifact):
    """Only this version's current findings; observation prose stays in full detail."""
    result={k:v for k,v in artifact.items() if k in {
        'id','kind','output_revision','deleted_at','quality_state','manual_review_required','delivery','playback_url'}}
    latest={}
    for check in artifact.get('checks',[]):
        findings=check.get('findings',{})
        scope=findings.get('scope',check['kind'])
        latest[(check['kind'],scope)]={'kind':check['kind'],'status':check['status'],'scope':scope,
            'findings':findings.get('review',{}).get('findings',findings.get('findings',[]))}
        if scope=='sampled_visual_only' and findings.get('visual_status') in {'pass','fail','partial'}:
            latest[(check['kind'],scope)]['visual_status']=findings['visual_status']
    result['checks']=list(latest.values())
    return result


def preview(conversations, segment, values):
    if set(values)-{'output_id','output_revision'}:
        fail('invalid_input','查看成片只需output_id或output_revision，不接受制作参数')
    if not segment['work_id']:fail('not_found','当前对话尚无成片',404)
    work=conversations.service.snapshot(segment['work_id'])
    outputs=[a for a in work['artifacts'] if a['kind']=='output' and a.get('playback_url')]
    if values.get('output_id'):
        outputs=[a for a in outputs if a['id']==values['output_id']]
    if values.get('output_revision') is not None:
        outputs=[a for a in outputs if a['output_revision']==values['output_revision']]
    if not outputs:fail('not_found','当前作品没有指定的可查看成片，请读取pending选择实际版本',404)
    output=max(outputs,key=lambda a:a['output_revision'])
    from .conversation_results import preview_text
    return {'work_id':work['id'],'preview_output':output,'preview_text':preview_text(output),
            'read_only':True,'requires_user_confirmation':False}


def has_edit_resume(task):
    """Existing edit recovery route, shared with user-facing continuation hints."""
    from .production.material_binding import AUDIO_EDIT_ERRORS
    error=json.loads(task.get('error_json') or '{}')
    scoped_plan=(task['kind']=='plan' and error.get('code')=='invalid_model_output'
                 and json.loads(task.get('payload_json') or '{}').get('revision_scope')=='narration')
    return (scoped_plan or (task['kind']=='render' and error.get('code')=='render_failed') or
            (task['kind']=='revise' and error.get('code') in {'invalid_revision_search','invalid_model_output'}) or
            (task['kind']=='edit' and error.get('code') in (AUDIO_EDIT_ERRORS | {
                'invalid_edit_project','invalid_edit','invalid_model_output','editor_rejected',
                'edit_duration_mismatch','visual_material_gap'})))


def pending(conversations, conn, segment):
    context = conversations.context(conn, segment)
    entry = context['entry']
    channels = []
    for r in conn.execute('SELECT * FROM channels WHERE profile_ref IS ? AND archived=0 ORDER BY created_at,id',(segment['profile_ref'],)):
        channels.append({k:r[k] for k in ('id','name','revision','default_director_revision')})
    directors = []
    for r in conn.execute('SELECT v.*,d.name,d.revision AS catalog_revision FROM director_revisions v JOIN directors d ON d.id=v.director_id WHERE d.archived=0 ORDER BY d.created_at,d.id,v.revision DESC'):
        directors.append({k:r[k] for k in ('id','director_id','name','revision','catalog_revision','style_confirmed','accepted_at')})
    proposals = []
    for r in conn.execute("SELECT * FROM conversation_proposals WHERE segment_id=? AND state IN ('proposed','applied') ORDER BY created_at,id",(segment['id'],)):
        proposal={'id':r['id'],'hash':r['body_hash'],'kind':r['kind'],'state':r['state'],'body':json.loads(r['body_json']),'receipt':json.loads(r['receipt_json']) if r['receipt_json'] else None}
        values=proposal['body']['values']
        if r['state']=='proposed' and r['kind']=='pipeline' and values.get('action')=='grant':
            try:
                grant_values(conversations,conn,segment,values['payload'],applying=True)
                proposal['can_answer']=True
            except ProductionError as exc:
                proposal.update(can_answer=False,validation_code=exc.code,validation_error=str(exc),next_action={'mode':'offer','action':'grant','values':{'purpose':'planning'}} if values['payload'].get('purpose')=='planning' and exc.code in {'invalid_input','stale_revision'} else None)
        if r['state']=='proposed' and (r['kind']=='revision' or r['kind']=='pipeline' and values.get('action') in {'revise','confirm_revision'}):
            try:
                if r['kind']=='revision':
                    from .production.revisions import revision_output
                    revision_output(conn,row(conn,'works',segment['work_id']),{'output_id':proposal['body']['target'].get('output_id','')})
                else:
                    scoped(conversations,conn,segment,values['action'],values['payload'])
                proposal['can_answer']=True
            except ProductionError as exc:
                proposal.update(can_answer=False,validation_code=exc.code,validation_error=str(exc))
        proposals.append(proposal)
    from .production.configuration import capabilities
    services = capabilities(conversations.service.outputs.parent)
    work = conversations.service.snapshot(segment['work_id']) if segment['work_id'] else None
    if work:
        from .conversation_results import dialogue_task
        work['tasks']=[dialogue_task(t) for t in work['tasks']]
    # snapshot reads only committed business state; pending() is called before writes.
    last=conn.execute('SELECT payload_json FROM conversation_turns WHERE segment_id=? ORDER BY created_at DESC,id DESC LIMIT 1',(segment['id'],)).fetchone()
    handoff=json.loads(last[0]).get('pipeline_binding') if last else None
    recovery=None
    if work and work['current_plan_revision']:
        delta={'settings':{'audio_mode':'voice'}}
        if work['state']=='cancelled':delta['restore_cancelled']=True
        try:
            conversations.service.preoutput_target(conn,row(conn,'works',work['id']),delta)
            recovery={'can_offer':True,'action':'plan','values':delta,
                'requires_restore_intent':work['state']=='cancelled',
                'note':'仅当用户要求此声音变更及必要的恢复时提出；新规划另有模型费用，保留旧方案，须下一真人回合确认。'}
        except ProductionError as exc:
            recovery={'can_offer':False,'code':exc.code,'reason':exc.user_message}
    failed_recovery=None
    if work and work['state']=='needs_decision' and work['current_plan_revision'] is None:
        task=conn.execute("SELECT id FROM tasks WHERE run_id=? AND kind='plan' AND state='needs_decision'",(work['active_run_id'],)).fetchone()
        if task:
            try:
                conversations.service.failed_planning_target(conn,row(conn,'works',work['id']),task['id'])
                failed_recovery={'can_offer':True,'action':'plan','values':{'decision_id':task['id']},
                    'note':'保留同一作品与历史回执，替换已失败的规划运行；新的规划可能收费，须展示提案并经下一真人回合确认，不取消作品。'}
            except ProductionError as exc:
                failed_recovery={'can_offer':False,'code':exc.code,'reason':exc.user_message}
    blockers=[]
    if work:
        from .conversation_results import material_search_summary
        searches=[json.loads(r[0]) for r in conn.execute("SELECT payload_json FROM events WHERE work_id=? AND run_id=? AND kind='material_search_completed' ORDER BY seq",(work['id'],work['active_run_id']))]
        unknown=conn.execute("SELECT 1 FROM operations WHERE work_id=? AND run_id=? AND state='unknown'",(work['id'],work['active_run_id'])).fetchone()
        active_run=row(conn,'runs',work['active_run_id']) if work['active_run_id'] else None
        for task in work['tasks']:
            if task['run_id']!=work['active_run_id'] or task['state'] not in {'needs_decision','failed'}:continue
            error=json.loads(task.get('error_json') or '{}')
            choices=[]
            if not unknown and task['kind']=='supply' and error.get('code') in {
                'material_gap','music_material_gap','sfx_material_gap','required_material_unavailable','material_invalid','generated_material_unavailable'}:
                if not active_run or active_run['state'] not in {'pending','running','waiting_external','needs_decision','paused'}:
                    choices.append({'kind':'provide_material','label':'提供符合本片用途的素材及使用依据','requires':'通过现有附件/input提案登记；必用素材不可擅自替换'})
                if error.get('code') in {'music_material_gap','sfx_material_gap'} and recovery and recovery.get('can_offer'):
                    choices.append({'kind':'voice_only_plan','label':'调整为纯旁白方案','action':'plan','values':recovery['values'],
                        'requires':'用户明确改变音频方案；展示规划费用，再确认；新方案仍须确认制作'})
            if (not unknown and active_run and not active_run['cancel_requested']
                    and active_run['state'] in {'needs_decision','paused','failed'}
                    and task['kind']=='supply' and error.get('code')=='music_material_gap'):
                choices.append({'kind':'resume','label':'解决音乐检索缺口后继续原制作',
                    'action':'resume','values':{'decision_id':task['id']},
                    'requires':'展示原音乐来源内的有限补料及后续配音/剪辑费用，确认后恢复；保留已取得素材、原方案和BGM，不重发UNKNOWN。'})
            if (not unknown and active_run and not active_run['cancel_requested']
                    and active_run['state'] in {'needs_decision','paused','failed'}
                    and has_edit_resume(task)):
                choices.append({'kind':'resume','label':('阻断解决后继续原改稿，保留已确认修订范围' if task['kind']=='plan' else '阻断解决后继续原剪辑，复用已成功产物'),
                    'action':'resume','values':{'decision_id':task['id']},
                    'requires':'先核对阻断已解决或已具备原结果修正入口。改稿差量修复使用新响应合同，不重发旧调用；新增模型费用须明确。用户明确要求继续原制作或原改稿时，offer action=resume并用user_quote引用本轮原话，在原授权内直接恢复，无需再次确认；文字越界已有原剪辑修正入口。只询问或尚未授权时说明范围后等待。不重跑已成功素材或配音，不改方案，不重发UNKNOWN。'})
            if (not unknown and active_run and not active_run['cancel_requested']
                    and task['kind']=='revise' and error.get('code')=='revision_scope_confirmation'):
                # This is an existing scope decision, not a failed creative call.
                # Expose only its bound summary and confirmation identity, not
                # the full source edit (which can dominate the next context).
                from .production.revisions import revision_confirmation
                review_id=json.loads(task['payload_json']).get('review_id')
                review=next((r for r in work.get('reviews',[]) if r['id']==review_id),None)
                if review:
                    values={'review_id':review['id'],'change_hash':review['change_hash']}
                    try:
                        _,changes,_,_=revision_confirmation(conn,row(conn,'works',work['id']),values)
                    except ProductionError:
                        pass
                    else:
                        choices.append({'kind':'confirm_revision','label':changes['summary'],
                            'action':'confirm_revision','values':values,
                            'scope':{k:changes[k] for k in ('summary','affected','reason','requires_new_generation') if k in changes},
                            'requires':'这是本轮已生成的实际修订范围待确认，不是旧约束冲突；展示本条真实范围和规划服务费用，offer confirm_revision并等待真人答复。不要新建revise、取消作品或臆测冲突；新方案完成后另确认制作，未确认不配音。'})
            blockers.append({'task_kind':task['kind'],'code':error.get('code'),'message':error.get('user_message'),
                'searches':material_search_summary(searches) if task['kind']=='supply' else [],
                'choices':choices,'unknown':bool(unknown),
                'input_change_available':not active_run or active_run['state'] not in {'pending','running','waiting_external','needs_decision','paused'},
                'input_constraint':'活动运行不允许改创作输入，不能承诺上传即可续作；不得为解除阻断擅自取消作品。',
                'resume_instruction':'UNKNOWN不重发；普通恢复先核对缺口条件是否已改变，或是否为可安全重试的临时故障。resume不是修复本身，不盲目反复继续。',
                'coverage':'本条是当前有效阻断；旧对话或旧尝试的错误不代表仍未解决，不合并为当前故障。正常模型回执不等于剪辑通过。未执行步骤不声称通过或失败。只提供本条choices实际支持的恢复选项，不为绑定错误推荐取消BGM或改纯旁白。选项不构成授权。'})
            if task['kind']=='plan' and error.get('code')=='draft_review_failed':
                checkpoint=json.loads(row(conn,'tasks',task['id'])['payload_json']).get('native_draft_checkpoint') or {}
                review=checkpoint.get('review') or {}
                findings=review.get('findings',[])
                blockers[-1]['draft_review']={
                    'findings':[value[:2000] for value in findings if isinstance(value,str)][:8],
                    'scope':'当前草稿的模型审阅意见，不是新增用户要求或已核实事实；核对字段合同及实际证据，不能只凭通用失败码猜测原因或擅自缩减交付范围。'}
    return {'replanning':{'action':'plan','values':{'intent':'replan'},'instruction':'未确认方案改口播、分镜或结构均使用此入口；已确认方案仅在真人明确要求重新规划时使用。request写明变更范围，user_quote引用真实原话；沿用已有规划授权直接执行。继续制作使用resume。新方案完成后仍须确认制作。'},'blockers':blockers,'failed_planning_replan':failed_recovery,'handoff_result':handoff,'context':context,'channels':channels,'directors':directors,'pending':proposals,
            'preoutput_replan':recovery,
            'current_plan':next((p for p in work['plans'] if p['revision']==work['current_plan_revision']),None) if work else None,
            'publication':{'platform':'bilibili','drafts':[publications(conversations)._get(conn,r[0]) for r in conn.execute('SELECT id FROM publication_drafts WHERE work_id=? ORDER BY updated_at DESC',(segment['work_id'],))], 'account_status':'not_checked','submission':'existing_publication_page_final_confirmation'},
            'work':work,'capabilities':services,'model_calls':call_status(conversations,conn,segment),
            'missing_choices':[name for name,value in [('channel',entry.get('channel_id') or not segment['profile_ref']),('director',entry.get('settings',{}).get('director_revision'))] if not value] if entry.get('kind','new_work') not in {'channel_create','director_formation'} else []}


def require_choices(segment):
    entry=json.loads(segment['context_json'])
    if (segment['profile_ref'] and not entry.get('channel_id')) or not entry.get('settings',{}).get('director_revision'):
        fail('selection_required','请先在对话中让用户选择频道和导演；已有选择不重复询问',409)


def scoped(conversations,conn,segment,action,values):
    kind=json.loads(segment['context_json']).get('kind','new_work')
    if action not in WORK_ACTIONS and action not in CATALOG_ACTIONS and action not in PUBLICATION_ACTIONS:
        fail('invalid_input','不支持的管线动作')
    if action in PUBLICATION_ACTIONS:
        if kind in {'channel_create','director_formation'} or not segment['work_id']:
            fail('pipeline_mismatch','请从具体成片的原对话准备发布',409)
        if set(values)!=PUBLICATION_ACTIONS[action]:fail('invalid_input','请提供具体成片或草稿版本与修改字段')
        if action=='publication_prepare':
            publications(conversations)._source(conn,segment['work_id'],values['output_id'])
        else:
            draft=publications(conversations)._get(conn,values['draft_id'])
            if draft['work_id']!=segment['work_id']:fail('binding_mismatch','草稿不属于当前作品',403)
            changes=values['changes']
            if not isinstance(changes,dict) or set(changes)-{'title','body','tags','tid','copyright','source'}:
                fail('invalid_publication','对话只能修改发布文案，账号、署名和投稿动作沿用发布页')
    elif action in WORK_ACTIONS:
        if kind=='channel_create' or (kind=='director_formation' and action not in {'input','grant','resume','cancel'}):
            fail('pipeline_mismatch','请先通过对话切换到对应管线',409)
        if action in {'plan','confirm','replan_after_unknown'}: require_choices(segment)
        if set(values)-WORK_ACTIONS[action]:fail('invalid_input','动作包含未允许字段')
        if not segment['work_id']:fail('work_not_bound','先建立本期草稿',409)
        if action in {'revise','confirm_revision'}:
            from .production.revisions import revision_output,revision_confirmation
            work=row(conn,'works',segment['work_id'])
            if action=='revise':revision_output(conn,work,values)
            else:revision_confirmation(conn,work,values)
        if values.get('output_id'):
            artifact=row(conn,'artifacts',values['output_id'])
            if artifact['work_id']!=segment['work_id'] or artifact.get('deleted_at'):fail('binding_mismatch','成片不属于当前作品',403)
    elif action=='director_style':
        if kind!='director_formation':fail('pipeline_mismatch','请先进入导演管线',409)
        if set(values)!={'revision_id'}:fail('invalid_input','请指定导演版本')
    elif action=='director_accept':
        if set(values)!={'revision_id','trial_artifact_id','manual_review_confirmed'}:fail('invalid_input','请明确试片及审阅结果')
        artifact=row(conn,'artifacts',values['trial_artifact_id'])
        if artifact['work_id']!=segment['work_id']:fail('binding_mismatch','试片不属于当前作品',403)
    elif action=='channel_director':
        if kind!='channel_create' or set(values)!={'revision_id'}:fail('pipeline_mismatch','请在频道管线设置默认导演',409)



def selected_attachment(conversations,conn,segment,values):
    attachment=next((a for t in conversations.scoped_turns(conn,segment) for a in json.loads(t['payload_json']).get('attachments',[]) if a['id']==values.get('attachment_id')),None)
    if not attachment:fail('attachment_not_bound','请先在当前对话提供素材附件',403)
    from .conversation_inputs import validate_attachment
    path=validate_attachment(conversations.service,segment['ui_session'],attachment)
    if values.get('usage','reference') not in {'reference','must_use'} or any(not isinstance(values.get(k,False),bool) for k in ('original_audio','rights_confirmed')):
        fail('invalid_input','素材用途、原声与权益声明须明确')
    return attachment,conversations.service._file_hash(path)


def production_values(conversations,conn,segment,values,*,applying=False):
    """Freeze the actual dependency identities before the human sees the offer."""
    from .production.configuration import capabilities
    work=row(conn,'works',segment['work_id'])
    plan=conn.execute('SELECT * FROM plan_revisions WHERE work_id=? AND revision=?',
                      (work['id'],work['current_plan_revision'])).fetchone()
    if not plan or plan['confirmed_at']:fail('stale_revision','当前没有待确认方案',409)
    data=dict(values)
    data.setdefault('allow_ai',False)
    data.setdefault('image_limit',work['image_limit'])
    data.setdefault('video_limit',work['video_limit'])
    for key,value in [('plan_revision',plan['revision']),('plan_hash',plan['plan_hash'])]:
        if key in data and data[key]!=value:fail('stale_revision','方案版本已变化，请查看当前完整方案',409)
        if applying and key not in data:fail('stale_revision','旧提案未绑定方案，请重新展示',409)
        data[key]=value
    if 'allow_ai' in data and type(data['allow_ai']) is not bool:fail('invalid_input','allow_ai须为布尔值')
    for key in ('image_limit','video_limit'):
        if key in data and (type(data[key]) is not int or data[key]<0):fail('invalid_input','生成次数须为非负整数')
    document=json.loads(plan['payload_json']);settings=document['settings']
    supplied=data.get('services',[])
    if not isinstance(supplied,list):
        fail('invalid_input','服务清单必须是数组')
    voice=settings.get('voice') or {}
    required=[]
    available=capabilities(conversations.service.outputs.parent)['services']
    if not any(s['mode']=='structured' and s.get('available') for s in available):
        fail('capability_unavailable','素材意图、剪辑及检查所需模型未配置，暂不能制作',409)
    if settings['audio_mode'] in {'voice','mixed'}:
        from .production.configuration import model_configuration
        from .production.voice import configured_speech_configs
        config,_,_=model_configuration(conversations.service.outputs.parent)
        if not any(option.available and all(option.identity.model_dump(mode='json')[k]==voice.get(k,'') for k in ('provider','model','voice_id','engine'))
                   for speech in configured_speech_configs(config) for option in speech.voices):
            fail('capability_unavailable','冻结声音当前不可用，请先核对声音配置',409)
    for item in available:
        if not item.get('available'):continue
        include=item['mode']=='structured'
        if item['provider']=='brave' and item['model']=='web-search':
            include=True
        if item.get('supports_auto_supply'):
            include=bool(set(item.get('media_types',[]))&{'image','video'})
            if 'audio' in item.get('media_types',[]):
                roles=set(item.get('audio_roles',['music','sfx']))
                audio_allowed=('music' in roles and settings['audio_mode'] in {'music','mixed'} or
                    'sfx' in roles and settings['audio_mode']!='silent' and
                    '本片不使用背景音乐或可选音效' not in document.get('constraints',[]))
                # An explicit service list may omit optional SFX search. Do not
                # silently put it back into the offer or expand it on answer.
                identity={k:item[k] for k in ('provider','model','mode')}
                if roles=={'sfx'} and supplied and identity not in supplied:
                    audio_allowed=False
                include=include or audio_allowed
        if item['mode']=='speech':
            include=(settings['audio_mode'] in {'voice','mixed'} and
                     item['provider']==voice.get('provider') and item['model']==voice.get('model'))
        if item.get('kind') in {'IMAGE','VIDEO'}:
            include=bool(data.get('allow_ai') and data.get('image_limit' if item['kind']=='IMAGE' else 'video_limit',0))
        identity={k:item[k] for k in ('provider','model','mode')}
        if include and identity not in required:required.append(identity)
    if not isinstance(supplied,list) or any(s not in required for s in supplied):
        fail('invalid_input','服务清单包含当前方案未使用或未允许的服务')
    if applying and supplied!=required:
        fail('stale_revision','执行服务已变化，请重新展示完整服务清单并确认',409)
    data['services']=required
    return data


def offer(conversations,conn,segment,turn_id,action,values,summary):
    scoped(conversations,conn,segment,action,values)
    if action=='basis':
        conversations.service._validate_settings(values.get('settings',{}))
    if action=='cancel':
        summary='取消整部当前作品，停止本地后续派发并撤销现有授权；保留方案、素材和回执，不能取消或判定远端未知请求。'
    if action=='confirm':
        values=production_values(conversations,conn,segment,values)
        summary=('待正式确认制作，尚未启动。接受方案内容不等于已授权制作；明确同意本提案后才确认方案并启动制作。授权服务：'+'、'.join('/'.join(s.values()) for s in values['services'])+
                 f"。AI生成许可：{'允许' if values.get('allow_ai') else '不允许'}；图片累计上限 {values.get('image_limit',0)}，视频累计上限 {values.get('video_limit',0)}。模型、配音、检索及生成服务可能产生费用；仅按展示范围执行。")
    if action=='plan':values=planning_values(conversations,conn,segment,values)
    if action=='grant':
        values=grant_values(conversations,conn,segment,values)
        names='、'.join(s['provider']+'/'+s['model']+'/'+s['mode'] for s in values['services'])
        summary=f"授权服务：{names}；用途：{values['purpose']}。"+('授权后继续原整理方案任务。' if values.get('decision_id') else '本提案仅保存授权。')
    target={}
    if action=='plan' and values.get('intent')=='replan':
        target=conversations.service.replanning_target(conn,row(conn,'works',segment['work_id']))
        summary='按本轮明确要求重新整理方案，保留旧方案、素材和配音；只替换已停止的运行，新方案完成后仍须确认制作。'+summary
    if action=='plan' and values.get('decision_id'):
        target=conversations.service.failed_planning_target(conn,row(conn,'works',segment['work_id']),values['decision_id'])
        from .production.configuration import model_configuration
        _,model,_=model_configuration(conversations.service.outputs.parent)
        values={**values,'services':[model]}
        summary=('保留当前作品、创作设置和历史回执，只替换已失败的规划运行；不取消整部作品。'
                 '重新整理方案可能产生新的模型调用及有界格式纠正费用，服务：'+'/'.join(model.values())+
                 '。方案完成后仍须确认才能制作；请确认后再执行。')
    if action=='plan' and 'settings' in values:
        target=conversations.service.preoutput_target(conn,row(conn,'works',segment['work_id']),values)
        # Recovery revokes the old grants; this proposal always shows the new cost.
        from .production.configuration import model_configuration
        _,model,_=model_configuration(conversations.service.outputs.parent)
        values={**values,'services':[model]}
        summary=('恢复当前作品并将已确认方案改为纯旁白，无背景音乐或可选音效；保留原观点、逐字稿、镜头及其他设置。'
                 '旧方案、素材和回执保留，结束旧运行并撤销旧授权；新方案须重新确认后才能制作。'
                 '本次规划服务：'+ '/'.join(model.values())+'，可能产生新的模型调用费用及有界格式纠正费用。')
    if action=='replan_after_unknown':
        target=unknown_replan_target(conversations,conn,segment,values)
        model=target['services'][0]
        configuration_note=(f"当前模型配置已变化，新任务使用当前配置（思考强度：{target['reasoning_effort']}）；旧请求不改配置、不重放。" if target['config_changed'] else '')
        summary=(f"结束旧本地规划运行并撤销旧活动授权，保留旧UNKNOWN及全部回执；这不能取消或确认远端请求，可能重复计费。"
                 f"以相同创作依据和{model['provider']}/{model['model']}/{model['mode']}发起一次新的规划任务，仅整理方案，不制作视频。"
                 f"{configuration_note}"
                 "保留现有规划的有界工具/格式修复规则，一次规划任务不代表只有一次模型调用。请明确确认以上范围后再执行。")
    if action=='input':
        _,target['attachment_digest']=selected_attachment(conversations,conn,segment,values)
    if action in CATALOG_ACTIONS:
        version=row(conn,'director_revisions',values['revision_id'])
        director=row(conn,'directors',version['director_id'])
        if director['archived']:fail('invalid_input','导演已归档')
        entry=json.loads(segment['context_json'])
        if action!='channel_director':
            selected=entry.get('settings',{}).get('director_revision')
            formed=conn.execute("SELECT 1 FROM tasks WHERE work_id=? AND kind='analyze_director' AND json_extract(payload_json,'$.director_id')=?",(segment['work_id'],director['id'])).fetchone()
            if not formed and (not selected or row(conn,'director_revisions',selected)['director_id']!=director['id']):fail('binding_mismatch','不是当前选定的导演',403)
        target={'director_id':director['id'],'director_revision':director['revision']}
        if action=='channel_director':
            channel=row(conn,'channels',entry.get('channel_id') or '')
            if channel['profile_ref']!=segment['profile_ref']:fail('binding_mismatch','频道画像不一致',403)
            target.update(channel_id=channel['id'],channel_revision=channel['revision'])
    return conversations.proposal(conn,segment,'pipeline',{'action':action,'payload':values,'summary':summary,'catalog_target':target},[turn_id])


def execute_action(conversations,conn,segment,body,key):
    values=body['values'];action=values['action'];data=values['payload']
    scoped(conversations,conn,segment,action,data)
    if action in PUBLICATION_ACTIONS:
        pub=publications(conversations)
        if action=='publication_prepare':
            draft=pub.prepare(segment['work_id'],data['output_id'],_connection=conn)
        else:
            previous=pub._get(conn,data['draft_id'])
            draft=pub.save(previous['id'],data['revision'],{**previous['content'],**data['changes']},_connection=conn)
        return {'publication':draft,'draft_url':'/#publication='+draft['id'],'submitted':False}
    if action=='replan_after_unknown':
        target=unknown_replan_target(conversations,conn,segment,data)
        if target!=values['catalog_target']:
            fail('stale_revision','旧任务、调用结果或配置已变化，请重新核对并展示提案',409)
        # Both domain commands share the enclosing answer transaction. A failed
        # new plan rolls back cancellation too. UNKNOWN rows remain untouched.
        stopped=conversations.service.command('cancel',{},command_id=key+'_stop',work_id=segment['work_id'],expected_revision=body['work_revision'],_connection=conn)
        result=conversations.service.command('plan',{'request':target['request'],'services':target['services']},command_id=key+'_plan',work_id=segment['work_id'],expected_revision=stopped['revision'],_connection=conn)
        return {**result,'previous_run_id':target['run_id'],'previous_result':'UNKNOWN'}
    if action=='input':
        attachment,checksum=selected_attachment(conversations,conn,segment,data)
        if checksum!=values['catalog_target']['attachment_digest']:fail('stale_revision','素材已变化，请重新核对确认',409)
        rights={'status':'KNOWN','license_name':'用户声明本片使用权','evidence':[{'kind':'user_declaration','reference':key,'summary':'经对话提案及用户答复确认本片使用权'}]} if data.get('rights_confirmed') else {}
        return conversations.service.command('input',{'attachment':attachment,'session_id':segment['ui_session'],'usage':data.get('usage','reference'),'original_audio':data.get('original_audio',False),'interval':data.get('interval'),'rights':rights},command_id=key+'_work',work_id=segment['work_id'],expected_revision=body['work_revision'],_connection=conn)
    if action in WORK_ACTIONS:
        if action=='confirm':data=production_values(conversations,conn,segment,data,applying=True)
        if action=='plan':
            data=planning_values(conversations,conn,segment,data,applying=True)
            if data.get('intent')=='replan':
                target=conversations.service.replanning_target(conn,row(conn,'works',segment['work_id']))
                if target!=values['catalog_target']:fail('stale_revision','重新规划目标已变化',409)
                data={**data,'replanning_target':target}
            if data.get('decision_id'):
                target=conversations.service.failed_planning_target(conn,row(conn,'works',segment['work_id']),data['decision_id'])
                if target!=values['catalog_target']:fail('stale_revision','失败规划目标已变化，请重新确认',409)
                data={**data,'failed_planning_target':target}
            if 'settings' in data:
                target=conversations.service.preoutput_target(conn,row(conn,'works',segment['work_id']),data)
                if target!=values['catalog_target']:fail('stale_revision','恢复目标已变化，请重新确认',409)
                data={**data,'recovery_target':target}
        if action=='grant':data=grant_values(conversations,conn,segment,data,applying=True)
        if action=='grant' and data.get('decision_id'):
            task=row(conn,'tasks',data['decision_id'])
            work=row(conn,'works',segment['work_id'])
            grant=conversations.service.command('grant',{k:v for k,v in data.items() if k!='decision_id'},command_id=key+'_grant',work_id=work['id'],expected_revision=body['work_revision'],_connection=conn)
            result=conversations.service.command('resume',{'decision_id':task['id']},command_id=key+'_resume',work_id=work['id'],expected_revision=grant['revision'],_connection=conn)
            return {**result,'grant_id':grant['grant_id']}
        return conversations.service.command(action,data,command_id=key+'_work',work_id=segment['work_id'],expected_revision=body['work_revision'],_connection=conn)
    target=values['catalog_target'];catalog=CreativeCatalog(conversations.service)
    if action=='channel_director':
        channel=row(conn,'channels',target['channel_id'])
        ids=[r[0] for r in conn.execute('SELECT director_id FROM channel_directors WHERE channel_id=?',(channel['id'],))]
        result=catalog.command('channels','edit',{'director_ids':list(dict.fromkeys(ids+[target['director_id']])),'default_director_revision':data['revision_id']},command_id=key+'_catalog',id=channel['id'],expected_revision=target['channel_revision'],_connection=conn)
    else:
        payload={**data,'style_confirmed':True} if action=='director_style' else data
        result=catalog.command('directors','edit' if action=='director_style' else 'accept',payload,command_id=key+'_catalog',id=target['director_id'],expected_revision=target['director_revision'],_connection=conn)
    return result


def bind_selection(conversations,conn,record,payload,segment,values,*,confirmed=False):
    if set(values)-{'kind','channel_id','director_revision','director_trial','work_id','output_id'}:fail('invalid_input','不能通过管线切换修改画像')
    previous=json.loads(segment['context_json'])
    next_kind=values.get('kind',previous.get('kind','new_work'))
    inherited={}
    if next_kind=='new_work' or next_kind==previous.get('kind','new_work') or (segment['work_id'] and next_kind in {'continue','revise'}):
        if previous.get('channel_id'):inherited['channel_id']=previous['channel_id']
        for key in ('director_revision','director_trial'):
            if key in previous.get('settings',{}):inherited[key]=previous['settings'][key]
    entry={'profile_ref':segment['profile_ref'],'kind':next_kind,**inherited,**values}
    if entry.get('channel_id') and not entry.get('director_revision'):
        default=row(conn,'channels',entry['channel_id'])['default_director_revision']
        if default:entry['director_revision']=default
    if segment['work_id'] and next_kind in {'new_work','continue','revise'}:
        # New works use the explicit conversation entry, never an accidental
        # omission in a model's rebind call.
        entry.setdefault('work_id',segment['work_id'])
        if (entry.get('channel_id')!=previous.get('channel_id')
            or entry.get('director_revision')!=previous.get('settings',{}).get('director_revision')
            or bool(entry.get('director_trial'))!=bool(previous.get('settings',{}).get('director_trial'))):
            fail('revision_required','当前作品的设置变更须使用 basis 或方案修订；另建作品请使用新作入口',409)
    if entry.get('kind','new_work') not in {'new_work','channel_create','director_formation','revise','continue'}:fail('invalid_input','管线无效')
    if entry.get('work_id'):
        work=row(conn,'works',entry['work_id'])
        if work['profile_ref']!=segment['profile_ref']:fail('binding_mismatch','不能切换到其他画像作品',403)
        if work['id']!=segment['work_id']:fail('binding_mismatch','请从作品库打开其他作品',403)
    if entry.get('channel_id'):
        channel=row(conn,'channels',entry['channel_id'])
        if channel['archived'] or channel['profile_ref']!=segment['profile_ref']:fail('binding_mismatch','频道不可用或画像不一致',403)
    if entry.get('director_revision'):
        version=row(conn,'director_revisions',entry['director_revision'])
        if row(conn,'directors',version['director_id'])['archived']:fail('invalid_input','导演已归档')
        if entry.get('kind')!='director_formation':
            conversations.service._director_version(conn,version['id'],bool(entry.get('director_trial')))
    # Selecting the already active, unbound pipeline is not a handoff.
    # Keep the native turn alive so explicit user choices can be resolved
    # and used now, rather than asking the Creator to repeat them next turn.
    unchanged=(segment['work_id']==entry.get('work_id')
        and entry['kind']==previous.get('kind','new_work')
        and entry.get('channel_id')==previous.get('channel_id')
        and entry.get('director_revision')==previous.get('settings',{}).get('director_revision')
        and bool(entry.get('director_trial'))==bool(previous.get('settings',{}).get('director_trial'))
        and entry.get('output_id')==previous.get('output_id'))
    if unchanged:
        return {'already_bound':True,'queued':False,
            'missing_choices':[k for k,v in [('channel',entry.get('channel_id') or not segment['profile_ref']),('director',entry.get('director_revision'))] if not v] if next_kind=='new_work' else [],
            'message':'当前已在此管线，无需结束本轮。请继续读取pending与用户来源，解析已明确的频道/导演并绑定真实目标；已有选择不要重复询问。'}
    selection_changed=(entry.get('channel_id')!=previous.get('channel_id')
        or entry.get('director_revision')!=previous.get('settings',{}).get('director_revision')
        or bool(entry.get('director_trial'))!=bool(previous.get('settings',{}).get('director_trial')))
    if selection_changed and not confirmed:
        # Semantic intent stays with the creator agent. Require concrete target
        # provenance: names in this human turn, or a previously shown selection.
        quote=payload.get('message','')
        targets=[]
        if entry.get('channel_id')!=previous.get('channel_id') and entry.get('channel_id'):
            targets.append((entry['channel_id'],row(conn,'channels',entry['channel_id'])['name']))
        if (entry.get('director_revision')!=previous.get('settings',{}).get('director_revision')
                or bool(entry.get('director_trial'))!=bool(previous.get('settings',{}).get('director_trial'))):
            if entry.get('director_revision'):
                version=row(conn,'director_revisions',entry['director_revision'])
                targets.append((version['id'],row(conn,'directors',version['director_id'])['name']))
        confirmed=bool(targets) and all(any(value and value in quote for value in target) for target in targets)
        if not confirmed:
            for proposal_id in payload.get('visible_proposals',[]):
                proposal=conn.execute("SELECT * FROM conversation_proposals WHERE id=? AND segment_id=? AND state='proposed'",(proposal_id,segment['id'])).fetchone()
                if not proposal:continue
                body=json.loads(proposal['body_json'])
                selection=body.get('values',{})
                if (selection.get('action')=='binding' and
                        all(selection.get('payload',{}).get(k)==entry.get(k) for k in ('kind','channel_id','director_revision','director_trial','work_id','output_id'))):
                    return conversations.apply(segment['ui_session'],proposal_id,proposal['body_hash'],
                        'binding_answer_'+record['id'],_connection=conn,_turn_id=record['id'],
                        _bind=lambda values:bind_selection(conversations,conn,record,payload,segment,values,confirmed=True))
    if selection_changed and not confirmed:
        names=[]
        if entry.get('channel_id'):
            names.append('频道「'+row(conn,'channels',entry['channel_id'])['name']+'」')
        if entry.get('director_revision'):
            version=row(conn,'director_revisions',entry['director_revision'])
            names.append('导演「'+row(conn,'directors',version['director_id'])['name']+'」版本'+str(version['revision'])+('（试片）' if entry.get('director_trial') else ''))
        proposal=conversations.proposal(conn,segment,'pipeline',
            {'action':'binding','payload':{k:v for k,v in entry.items() if k!='profile_ref'},'summary':'建议选择'+'、'.join(names)+'；尚未绑定，请确认或调整。'},[record['id']])
        return {**proposal,'queued':False,'selection_pending':True,
            'message':'仅已建立选择提案，未绑定、未建草稿。简短展示这些具体选择，等用户答复后answer；不要声称已生效，也不要展开完整方案。'}
    # Native turn must end before a new immutable segment may become current.
    payload['pipeline_entry']=entry
    prior=json.loads(segment['context_json']).get('handoff',{}).get('messages',[])
    messages=[{'source_turn':r['id'],'text':json.loads(r['payload_json']).get('message','')} for r in conn.execute('SELECT id,payload_json FROM conversation_turns WHERE segment_id=? ORDER BY created_at,id',(segment['id'],))]
    payload['pipeline_handoff']={'source_segment':segment['id'],'source_turn':record['id'],'user_message':payload['message'],'messages':(prior+messages)[-40:]}
    return {'queued':True,'message':'本轮结束后绑定所选管线，由宿主自动续接；不要让用户为了内部切换回复继续。','entry':entry}


def dispatch(bridge,conn,record,payload,segment,args,command_id):
    conversations=bridge.conversations
    mode=args['mode']
    if mode=='preview':return preview(conversations,segment,args.get('values',{}))
    if mode=='pending':
        state=pending(conversations,conn,segment)
        detail=args.get('values',{}).get('detail')
        if detail=='full':return state
        if detail is not None:fail('invalid_input','详情使用values.detail=full')
        summary=turn_context(state)
        # The current actionable plan remains available for actual confirmation;
        # archived plans/artifacts are read explicitly instead of repeated.
        summary['current_plan']=state['current_plan']
        return summary
    quote=args.get('user_quote','').strip()
    if mode in {'answer','bind','draft'} and (not quote or quote not in payload['message']):
        fail('invalid_source','操作必须引用本轮用户的原话',403)
    if mode=='bind':
        return bind_selection(conversations,conn,record,payload,segment,args.get('values',{}))
    if mode=='draft':
        kind=json.loads(segment['context_json']).get('kind','new_work')
        if kind=='channel_create':fail('pipeline_mismatch','频道设置不创建作品',409)
        if kind!='director_formation':require_choices(segment)
        if segment['work_id']:return {'work_id':segment['work_id'],'already_created':True}
        result=conversations.proposal(conn,segment,'draft',args.get('values',{}),[record['id']])
        return conversations.apply(segment['ui_session'],result['proposal_id'],result['hash'],command_id,_connection=conn,_turn_id=record['id'])
    if mode=='offer' and args.get('action')=='plan' and args.get('values',{}).get('intent')=='replan' and quote:
        if payload.get('origin','user')!='user' or quote not in payload.get('message',''):
            fail('invalid_source','重新规划必须引用本轮真人明确要求',403)
        values=planning_values(conversations,conn,segment,args['values'])
        result=offer(conversations,conn,segment,record['id'],'plan',values,args.get('summary',''))
        # Existing planning permission covers a new plan, not a new production run.
        from .production.configuration import model_configuration
        _,model,_=model_configuration(conversations.service.outputs.parent)
        authorized=any(model in json.loads(g[0]) for g in conn.execute(
            "SELECT services_json FROM authorization_grants WHERE work_id=? AND purpose='planning' AND revoked_at IS NULL",(segment['work_id'],)))
        if not authorized:return result
        receipt=conversations.apply(segment['ui_session'],result['proposal_id'],result['hash'],command_id,
                                    _connection=conn,_turn_id=record['id'])
        return {**receipt,'user_source':record['id'],'replanned':True,'requires_user_confirmation':False}
    if mode=='offer' and args.get('action') in {'accept',*PUBLICATION_ACTIONS} and quote:
        if payload.get('origin','user')!='user' or quote not in payload.get('message',''):
            fail('invalid_source','接受与草稿修改必须引用本轮真人明确要求',403)
        result=offer(conversations,conn,segment,record['id'],args['action'],args.get('values',{}),args.get('summary',''))
        receipt=conversations.apply(segment['ui_session'],result['proposal_id'],result['hash'],command_id,
                                   _connection=conn,_turn_id=record['id'])
        return {**receipt,'user_source':record['id'],'requires_user_confirmation':False}
    if mode=='offer' and args.get('action')=='resume' and quote:
        if payload.get('origin','user')!='user' or quote not in payload.get('message',''):
            fail('invalid_source','恢复必须引用本轮真人明确续作原话',403)
        values=args.get('values',{})
        scoped(conversations,conn,segment,'resume',values)
        work=row(conn,'works',segment['work_id'])
        task=row(conn,'tasks',values.get('decision_id',''))
        if task['run_id']!=work['active_run_id'] or task['work_id']!=work['id']:
            fail('stale_revision','恢复目标已变化，请读取当前断点',409)
        if conn.execute("SELECT 1 FROM operations WHERE run_id=? AND state IN ('reserved','sending','submitted','unknown')",(task['run_id'],)).fetchone():
            fail('result_unknown','存在未确定调用，不能重新派发',409)
        result=offer(conversations,conn,segment,record['id'],'resume',values,args.get('summary',''))
        receipt=conversations.apply(segment['ui_session'],result['proposal_id'],result['hash'],command_id,
                                    _connection=conn,_turn_id=record['id'])
        return {**receipt,'user_source':record['id'],'resumed':True,'requires_user_confirmation':False}
    if mode=='offer':
        return offer(conversations,conn,segment,record['id'],args.get('action',''),args.get('values',{}),args.get('summary',''))
    if mode=='answer':
        p=conn.execute('SELECT * FROM conversation_proposals WHERE id=?',(args.get('proposal_id') or '',)).fetchone()
        if not p:fail('not_found','待答提案标识无效。请重新读取pending，逐字复制当前提案的完整id与hash后重试answer；不要为工具参数错误重新offer或要求用户重复确认。',404)
        if p['segment_id']!=segment['id'] or p['body_hash']!=args.get('hash'):fail('binding_mismatch','待答事项不属于当前管线或版本',403)
        body=json.loads(p['body_json'])
        if p['state'] not in {'proposed','applied'}:fail('stale_revision','待答事项已失效，请使用最新版本',409)
        # Only a previously delivered question can be answered, never a model's
        # own new proposal during the same user turn.
        if record['id'] in body['source_refs']:fail('confirmation_required','请先向用户展示具体内容，等下一轮回答',409)
        if not any(ref in payload.get('visible_proposals',[]) for ref in [p['id']]):fail('confirmation_required','该提案尚未在本轮开始前展示',409)
        kind=json.loads(segment['context_json']).get('kind','new_work')
        allowed={'channel_create':{'channel_create','channel_defaults','pipeline'},'director_formation':{'draft','director_formation','director_revision','pipeline'}}.get(kind,{'draft','plan','revision','pipeline'})
        if p['kind'] not in allowed:fail('pipeline_mismatch','此操作应在对应管线完成',409)
        if p['kind'] in {'plan','draft'} and kind!='director_formation':require_choices(segment)
        result=conversations.apply(segment['ui_session'],p['id'],p['body_hash'],command_id,dismiss=args.get('dismiss',False),_connection=conn,_turn_id=record['id'],
            _bind=lambda values:bind_selection(conversations,conn,record,payload,segment,values,confirmed=True))
        return {**result,'user_source':record['id'],'answered_proposal':p['id']}
    fail('invalid_input','管线操作无效')
