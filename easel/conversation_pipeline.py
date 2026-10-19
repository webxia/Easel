"""Easel pending → answer → resume adapter; domain services own execution.

No provider calls, independent scheduler, or model-supplied user authority.
"""
from __future__ import annotations
import json
from .production.service import row, fail, encode, digest
from .production.catalog import CreativeCatalog

WORK_ACTIONS = {
    'input': {'attachment_id','usage','original_audio','interval','rights_confirmed'},
    'plan': {'request','services'},
    'confirm': {'plan_revision','plan_hash','services','allow_ai','image_limit','video_limit'},
    'grant': {'purpose','services','allow_ai','image_limit','video_limit','target_ref','plan_revision'},
    'resume': {'decision_id'}, 'cancel': set(),
    'basis': {'settings','input_text'},
    'revise': {'output_id','feedback','preserve_audio'},
    'confirm_revision': {'review_id','change_hash','services'},
    'accept': {'output_id','manual_review_confirmed'},
}
CATALOG_ACTIONS = {'director_style','director_accept','channel_director'}


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
        proposals.append({'id':r['id'],'hash':r['body_hash'],'kind':r['kind'],'state':r['state'],'body':json.loads(r['body_json']),'receipt':json.loads(r['receipt_json']) if r['receipt_json'] else None})
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
        p=row(conn,'conversation_proposals',args.get('proposal_id') or '')
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
