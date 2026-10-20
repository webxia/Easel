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
    'plan': {'request','services'},
    'confirm': {'plan_revision','plan_hash','services','allow_ai','image_limit','video_limit'},
    'grant': {'purpose','services','allow_ai','image_limit','video_limit','target_ref','plan_revision','decision_id'},
    'resume': {'decision_id'}, 'cancel': set(),
    'basis': {'settings','input_text'},
    'revise': {'output_id','feedback','preserve_audio'},
    'confirm_revision': {'review_id','change_hash','services'},
    'accept': {'output_id','manual_review_confirmed'},
}
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
        proposals.append(proposal)
    from .production.configuration import capabilities
    services = capabilities(conversations.service.outputs.parent)
    work = conversations.service.snapshot(segment['work_id']) if segment['work_id'] else None
    # snapshot reads only committed business state; pending() is called before writes.
    last=conn.execute('SELECT payload_json FROM conversation_turns WHERE segment_id=? ORDER BY created_at DESC,id DESC LIMIT 1',(segment['id'],)).fetchone()
    handoff=json.loads(last[0]).get('pipeline_binding') if last else None
    return {'handoff_result':handoff,'context':context,'channels':channels,'directors':directors,'pending':proposals,
            'work':work,'capabilities':services,
            'missing_choices':[name for name,value in [('channel',entry.get('channel_id')),('director',entry.get('settings',{}).get('director_revision'))] if not value] if entry.get('kind','new_work') not in {'channel_create','director_formation'} else []}


def require_choices(segment):
    entry=json.loads(segment['context_json'])
    if not entry.get('channel_id') or not entry.get('settings',{}).get('director_revision'):
        fail('selection_required','请先在对话中让用户选择频道和导演；已有选择不重复询问',409)


def scoped(conversations,conn,segment,action,values):
    kind=json.loads(segment['context_json']).get('kind','new_work')
    if action not in WORK_ACTIONS and action not in CATALOG_ACTIONS:
        fail('invalid_input','不支持的管线动作')
    if action in WORK_ACTIONS:
        if kind=='channel_create' or (kind=='director_formation' and action not in {'input','grant','resume','cancel'}):
            fail('pipeline_mismatch','请先通过对话切换到对应管线',409)
        if action in {'plan','confirm'}: require_choices(segment)
        if set(values)-WORK_ACTIONS[action]:fail('invalid_input','动作包含未允许字段')
        if not segment['work_id']:fail('work_not_bound','先建立本期草稿',409)
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


def offer(conversations,conn,segment,turn_id,action,values,summary):
    scoped(conversations,conn,segment,action,values)
    if action=='confirm':
        work=row(conn,'works',segment['work_id'])
        plan=conn.execute('SELECT * FROM plan_revisions WHERE work_id=? AND revision=?',(work['id'],values.get('plan_revision'))).fetchone()
        if not plan or work['current_plan_revision']!=values.get('plan_revision') or plan['plan_hash']!=values.get('plan_hash') or plan['confirmed_at']:
            fail('stale_revision','当前没有这版可确认方案；修改创作依据会使旧方案失效。请先读取pending，确需改稿时重新规划并展示完整方案，不要重复提出失效版本的制作确认',409)
    if action=='plan':values=planning_values(conversations,conn,segment,values)
    if action=='grant':
        values=grant_values(conversations,conn,segment,values)
        names='、'.join(s['provider']+'/'+s['model']+'/'+s['mode'] for s in values['services'])
        summary=f"授权服务：{names}；用途：{values['purpose']}。"+('授权后继续原整理方案任务。' if values.get('decision_id') else '本提案仅保存授权。')
    target={}
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
    if action=='input':
        attachment,checksum=selected_attachment(conversations,conn,segment,data)
        if checksum!=values['catalog_target']['attachment_digest']:fail('stale_revision','素材已变化，请重新核对确认',409)
        rights={'status':'KNOWN','license_name':'用户声明本片使用权','evidence':[{'kind':'user_declaration','reference':key,'summary':'经对话提案及用户答复确认本片使用权'}]} if data.get('rights_confirmed') else {}
        return conversations.service.command('input',{'attachment':attachment,'session_id':segment['ui_session'],'usage':data.get('usage','reference'),'original_audio':data.get('original_audio',False),'interval':data.get('interval'),'rights':rights},command_id=key+'_work',work_id=segment['work_id'],expected_revision=body['work_revision'],_connection=conn)
    if action in WORK_ACTIONS:
        if action=='plan':data=planning_values(conversations,conn,segment,data,applying=True)
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


def dispatch(bridge,conn,record,payload,segment,args,command_id):
    conversations=bridge.conversations
    mode=args['mode']
    if mode=='pending':return pending(conversations,conn,segment)
    quote=args.get('user_quote','').strip()
    if mode in {'answer','bind','draft'} and (not quote or quote not in payload['message']):
        fail('invalid_source','操作必须引用本轮用户的原话',403)
    if mode=='bind':
        values=args.get('values',{})
        if set(values)-{'kind','channel_id','director_revision','director_trial','work_id','output_id'}:fail('invalid_input','不能通过管线切换修改画像')
        previous=json.loads(segment['context_json'])
        next_kind=values.get('kind',previous.get('kind','new_work'))
        inherited={}
        if next_kind=='new_work' or next_kind==previous.get('kind','new_work'):
            if previous.get('channel_id'):inherited['channel_id']=previous['channel_id']
            for key in ('director_revision','director_trial'):
                if key in previous.get('settings',{}):inherited[key]=previous['settings'][key]
        entry={'profile_ref':segment['profile_ref'],'kind':next_kind,**inherited,**values}
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
        unchanged=(not segment['work_id'] and not entry.get('work_id')
            and entry['kind']==previous.get('kind','new_work')
            and entry.get('channel_id')==previous.get('channel_id')
            and entry.get('director_revision')==previous.get('settings',{}).get('director_revision')
            and bool(entry.get('director_trial'))==bool(previous.get('settings',{}).get('director_trial'))
            and entry.get('output_id')==previous.get('output_id'))
        if unchanged:
            return {'already_bound':True,'queued':False,
                'missing_choices':[k for k,v in [('channel',entry.get('channel_id')),('director',entry.get('director_revision'))] if not v] if next_kind=='new_work' else [],
                'message':'当前已在此管线，无需结束本轮。请继续读取pending与用户来源，解析已明确的频道/导演并绑定真实目标；已有选择不要重复询问。'}
        # Native turn must end before a new immutable segment may become current.
        payload['pipeline_entry']=entry
        prior=json.loads(segment['context_json']).get('handoff',{}).get('messages',[])
        messages=[{'source_turn':r['id'],'text':json.loads(r['payload_json']).get('message','')} for r in conn.execute('SELECT id,payload_json FROM conversation_turns WHERE segment_id=? ORDER BY created_at,id',(segment['id'],))]
        payload['pipeline_handoff']={'source_segment':segment['id'],'source_turn':record['id'],'user_message':payload['message'],'messages':(prior+messages)[-40:]}
        return {'queued':True,'message':'本轮结束后绑定所选管线；请结束本轮，下一轮继续。','entry':entry}
    if mode=='draft':
        kind=json.loads(segment['context_json']).get('kind','new_work')
        if kind=='channel_create':fail('pipeline_mismatch','频道设置不创建作品',409)
        if kind!='director_formation':require_choices(segment)
        if segment['work_id']:return {'work_id':segment['work_id'],'already_created':True}
        result=conversations.proposal(conn,segment,'draft',args.get('values',{}),[record['id']])
        return conversations.apply(segment['ui_session'],result['proposal_id'],result['hash'],command_id,_connection=conn,_turn_id=record['id'])
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
        result=conversations.apply(segment['ui_session'],p['id'],p['body_hash'],command_id,dismiss=args.get('dismiss',False),_connection=conn,_turn_id=record['id'])
        return {**result,'user_source':record['id'],'answered_proposal':p['id']}
    fail('invalid_input','管线操作无效')
