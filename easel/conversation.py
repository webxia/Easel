"""Durable, scoped conversation adapter. WorkService remains production authority."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .production.service import digest, encode, fail, new_id, now, row
from .production.catalog import CreativeCatalog, validate_channel_basis, validate_director_references

PROPOSALS = {'draft', 'plan', 'revision', 'channel_create', 'channel_defaults', 'director_formation', 'profile', 'director_revision', 'pipeline'}


class ConversationService:
    def __init__(self, service):
        self.service, self.store = service, service.store

    def segment(self, conn, session, segment_id=None):
        value=conn.execute('SELECT * FROM conversation_segments WHERE ui_session=? AND revoked_at IS NULL '+
            ('AND id=? ' if segment_id else '')+'ORDER BY created_at DESC LIMIT 1',
            (session,segment_id) if segment_id else (session,)).fetchone()
        if not value: fail('conversation_not_bound','请先进入视频创作对话',409)
        return dict(value)

    def enter(self, session, entry, command_id, *, _connection=None):
        if not isinstance(session,str) or not session.strip() or len(session)>256:
            fail('invalid_input','无效会话',400)
        allowed={'profile_ref','channel_id','director_revision','director_trial','work_id','output_id','kind'}
        if set(entry)-allowed: fail('invalid_input','创作入口包含未知字段',400)
        def execute(conn):
            # A UI conversation can retain multiple immutable native segments.
            active=conn.execute("SELECT 1 FROM conversation_turns t JOIN conversation_segments s ON s.id=t.segment_id WHERE s.ui_session=? AND t.state IN ('reserved','active','dispatching','unknown')",(session,)).fetchone()
            if active: fail('invocation_pending','上一轮尚未结束或待核实，不能切换创作依据',409)
            work=row(conn,'works',entry['work_id']) if entry.get('work_id') else None
            if work and work.get('deleted_at'):fail('not_found','作品已删除',404)
            profile=work['profile_ref'] if work else self.service._profile(conn,entry.get('profile_ref'))
            channel=work['channel_id'] if work else entry.get('channel_id')
            context={'kind':entry.get('kind','new_work'),'profile_ref':profile,'channel_id':channel}
            if channel:
                ch=row(conn,'channels',channel)
                if not work and ch['archived']:fail('invalid_input','频道已归档')
                if not profile:profile=ch['profile_ref'];context['profile_ref']=profile
                if ch['profile_ref']!=profile:fail('invalid_input','频道与画像不一致')
                context['channel']={'id':ch['id'],'name':ch['name'],'revision':ch['revision'],'creative_basis':json.loads(ch['creative_basis_json'])}
            if work:
                settings=json.loads(work['settings_json'])
            else:
                from .production.settings import merge_creation_settings
                settings={}
                if profile:settings.update(json.loads(row(conn,'profile_refs',profile)['settings_json']))
                if channel:
                    settings=merge_creation_settings(settings,json.loads(ch['settings_json']))
                    if ch['default_director_revision']:settings['director_revision']=ch['default_director_revision']
                if entry.get('director_revision'):
                    settings['director_revision']=entry['director_revision'];settings['director_trial']=bool(entry.get('director_trial'))
                if settings.get('director_revision'):
                    if entry.get('kind')=='director_formation':
                        version=row(conn,'director_revisions',settings['director_revision'])
                        if row(conn,'directors',version['director_id'])['archived']:fail('invalid_input','导演已归档')
                    else:self.service._director_version(conn,settings['director_revision'],bool(settings.get('director_trial')))
            context['profile_name']=row(conn,'profile_refs',profile)['name'] if profile else None
            if work and context.get('channel'):context['channel']['creative_basis']=json.loads(work['creation_context_json']).get('channel_basis',context['channel']['creative_basis'])
            context['settings']=settings
            context['director_source']='explicit' if entry.get('director_revision') else 'channel_default' if channel else 'none'
            if entry.get('output_id'):
                output=row(conn,'artifacts',entry['output_id'])
                if not work or output['work_id']!=work['id'] or output.get('deleted_at') or output['output_revision'] is None:fail('invalid_input','成片不属于续接作品')
                context['output_id']=output['id']
            # Returning to precisely the same Work uses its own segment, never another Work's transcript.
            old=conn.execute('SELECT * FROM conversation_segments WHERE ui_session=? AND work_id IS ? AND profile_ref IS ? AND context_json=? AND revoked_at IS NULL ORDER BY created_at DESC LIMIT 1',(session,work['id'] if work else None,profile,encode(context))).fetchone()
            sid=old['id'] if old else new_id()
            if not old:conn.execute('INSERT INTO conversation_segments(id,ui_session,profile_ref,work_id,context_json,created_at) VALUES (?,?,?,?,?,?)',(sid,session,profile,work['id'] if work else None,encode(context),now()))
            # Select current without mutating identity or historical context.
            conn.execute('UPDATE conversation_segments SET created_at=? WHERE id=?',(now(),sid))
            if work:conn.execute('INSERT OR IGNORE INTO work_conversation_links VALUES (?,?,?)',(work['id'],session,now()))
            return {'segment_id':sid,'work_id':work['id'] if work else None,'context':context}
        return self.store.execute_command(command_id,{'enter':entry,'session':session},execute,connection=_connection)

    def context(self, conn, segment):
        entry=json.loads(segment['context_json'])
        work=row(conn,'works',segment['work_id']) if segment['work_id'] else None
        if work:
            # Actual frozen history rather than newly changed catalog defaults.
            plan=conn.execute('SELECT payload_json FROM plan_revisions WHERE work_id=? ORDER BY revision DESC LIMIT 1',(work['id'],)).fetchone()
            if plan:
                payload=json.loads(plan[0]);snap=payload.get('profile_snapshot')
                profile=json.loads(snap['content']) if snap else {}
                entry={**entry,'settings':{**payload['settings'],'director_revision':payload.get('director_revision_id')},'frozen_basis':payload.get('conversation_basis')}
            else:
                profile=self.service.profile_snapshot(conn,segment['profile_ref'])
                entry={**entry,'settings':json.loads(work['settings_json'])}
        else:profile=self.service.profile_snapshot(conn,segment['profile_ref'])
        director_id=entry.get('settings',{}).get('director_revision')
        if director_id:
            version=row(conn,'director_revisions',director_id)
            entry['director_style']=json.loads(version['style_json'])
            director=row(conn,'directors',version['director_id'])
            entry['director']={'id':director['id'],'revision':director['revision'],'selected_revision_id':director_id}
        brief=conn.execute('SELECT * FROM work_briefs WHERE work_id=? ORDER BY revision DESC LIMIT 1',(segment['work_id'],)).fetchone()
        sources=[]
        for t in self.scoped_turns(conn,segment):
            payload=json.loads(t['payload_json'])
            if payload.get('message') is not None:
                sources.append({'ref':t['id'],'text':payload['message'],'attachments':payload.get('attachments',[])})
        save_target=self.service.profile_snapshot(conn,segment['profile_ref']) if segment['profile_ref'] else {}
        save_target={k:v for k,v in save_target.items() if k in {'style','preferences','memory'}}
        return {'entry':entry,'profile':profile,'sources':sources[-40:],
            'profile_save_target':{'files':save_target,'hashes':{k:hashlib.sha256(v.encode()).hexdigest() for k,v in save_target.items()}},
            'brief':json.loads(brief['body_json']) if brief else None,
            'profile_hashes':{k:hashlib.sha256(v.encode()).hexdigest() for k,v in profile.items()},
            'inputs':[] if not work else [{k:r[k] for k in ('id','kind','usage','original_name','digest')} for r in conn.execute('SELECT * FROM work_inputs WHERE work_id=?',(work['id'],))],
            'work':None if not work else {k:work[k] for k in ('id','revision','state','input_text','current_plan_revision')}}

    def scoped_turns(self,conn,segment):
        turns=[dict(r) for r in conn.execute('SELECT * FROM conversation_turns WHERE segment_id=? ORDER BY created_at,id',(segment['id'],))]
        inherited=json.loads(segment['context_json']).get('handoff',{}).get('messages',[])
        for source in inherited:
            record=conn.execute('SELECT t.* FROM conversation_turns t JOIN conversation_segments s ON s.id=t.segment_id WHERE t.id=? AND s.ui_session=? AND s.profile_ref IS ? AND s.revoked_at IS NULL',(source.get('source_turn'),segment['ui_session'],segment['profile_ref'])).fetchone()
            if record and json.loads(record['payload_json']).get('message')==source.get('text'):
                turns.insert(0,dict(record))
        return list({r['id']:r for r in turns}.values())

    def source_refs(self, conn, segment, refs, *, allow_results=False):
        if not isinstance(refs,list) or not refs or len(refs)>40:fail('invalid_source','请引用本运行段或可信交接中的用户消息')
        allowed={r['id'] for r in self.scoped_turns(conn,segment) if allow_results or json.loads(r['payload_json']).get('origin')!='task_result'}
        if any(not isinstance(ref,str) or ref not in allowed for ref in refs):
            fail('invalid_source','依据不属于当前管线或可信交接',403)
        return list(dict.fromkeys(refs))

    def brief(self,conn,segment,entries):
        if not segment['work_id']:fail('work_not_bound','请先确认作品草稿',409)
        work=row(conn,'works',segment['work_id']);self.service._ensure_idle(conn,work)
        if conn.execute('SELECT 1 FROM plan_revisions WHERE work_id=? AND confirmed_at IS NOT NULL',(work['id'],)).fetchone():
            fail('revision_required','已有确认方案；本片修改意见请绑定具体成片走修订，讨论仍可继续',409)
        if not isinstance(entries,list) or not entries or len(entries)>100:fail('invalid_input','创作依据无效')
        for item in entries:
            if not isinstance(item,dict) or set(item)!={'kind','text','source_refs'} or item['kind'] not in {'user_requirement','suggestion','unresolved'} or not isinstance(item['text'],str) or not item['text'].strip() or len(item['text'])>10000:fail('invalid_input','请区分用户要求、建议与未决项')
            self.source_refs(conn,segment,item['source_refs'])
            if item['kind']=='user_requirement':
                texts=[json.loads(row(conn,'conversation_turns',ref)['payload_json']).get('message','') for ref in item['source_refs']]
                if not any(item['text'] in t for t in texts):fail('invalid_source','用户硬要求必须引用原话；归纳请标为建议')
        body={'entries':entries,'sources':{ref:json.loads(row(conn,'conversation_turns',ref)['payload_json']).get('message','') for entry in entries for ref in entry['source_refs']}};revision=conn.execute('SELECT COALESCE(MAX(revision),0)+1 FROM work_briefs WHERE work_id=?',(work['id'],)).fetchone()[0]
        conn.execute('INSERT INTO work_briefs VALUES (?,?,?,?,?)',(work['id'],revision,encode(body),digest(body),now()))
        self.service._change(conn,work,current_plan_revision=None,state='discussing')
        conn.execute("UPDATE conversation_proposals SET state='stale' WHERE state='proposed' AND kind IN ('plan','revision','director_formation') AND json_extract(body_json,'$.work_id')=?",(work['id'],))
        self.service._event(conn,work['id'],'brief_updated',{'brief_revision':revision,'brief_hash':digest(body)})
        return {'work_id':work['id'],'revision':row(conn,'works',work['id'])['revision'],'brief_revision':revision,'brief_hash':digest(body)}

    def proposal(self,conn,segment,kind,values,refs):
        if kind not in PROPOSALS or not isinstance(values,dict) or len(encode(values))>100000:fail('invalid_input','提议类型或内容无效')
        refs=self.source_refs(conn,segment,refs,allow_results=True)
        if kind in {'channel_create','channel_defaults'} and 'creative_basis' in values:
            validate_channel_basis(values['creative_basis'])
        if kind=='director_revision' and set(values)-{'style','base_revision'}:
            fail('invalid_input','director_revision.values只能含style和base_revision；导演目标来自当前选择，不得包含name或base_director_id')
        if kind=='director_formation':
            if values.get('analysis_scope','full') not in {'full','visual'}:fail('invalid_input','导演分析范围须为full或visual')
            if not segment['work_id']:fail('work_not_bound','请先确认参考作品并登记视频',409)
            validate_director_references(conn,segment['work_id'],values.get('reference_input_ids'))
        if kind=='plan' and segment['work_id'] and conn.execute('SELECT 1 FROM plan_revisions WHERE work_id=? AND confirmed_at IS NOT NULL',(segment['work_id'],)).fetchone():
            fail('revision_required','已有确认方案；请指定成片修订或基于旧版创建新作',409)
        if kind=='plan':
            from .conversation_pipeline import planning_values
            values=planning_values(self,conn,segment,values)
        # Proposed target comes only from the selected entry/Work, never free model IDs/paths.
        target=json.loads(segment['context_json'])
        if segment['work_id']:target={**target,'settings':json.loads(row(conn,'works',segment['work_id'])['settings_json'])}
        if kind=='channel_defaults' and target.get('channel_id'):
            channel=row(conn,'channels',target['channel_id'])
            target['channel']={'id':channel['id'],'name':channel['name'],'revision':channel['revision'],'settings':json.loads(channel['settings_json']),'creative_basis':json.loads(channel['creative_basis_json'])}
        body={'values':values,'source_refs':refs,'target':target,
              'work_id':segment['work_id'],'work_revision':row(conn,'works',segment['work_id'])['revision'] if segment['work_id'] else None}
        # Repeating an unchanged pending production question does not create a
        # new question. Keep its original sources, so a later human answer is
        # still answering what was already shown. Changed scope remains new.
        if kind=='pipeline' and values.get('action')=='confirm':
            for pending in conn.execute("SELECT * FROM conversation_proposals WHERE segment_id=? AND kind='pipeline' AND state='proposed'",(segment['id'],)):
                prior=json.loads(pending['body_json'])
                if (all(prior.get(k)==body[k] for k in ('target','work_id','work_revision'))
                        and all(prior['values'].get(k)==values.get(k) for k in ('action','payload','catalog_target'))):
                    return {'proposal_id':pending['id'],'hash':pending['body_hash'],'state':'proposed','already_proposed':True,
                            'message':'这是已经展示的同一制作提案，未新建或修改。若本轮用户明确确认，请answer这个原提案，不要再要求确认。'}
        checksum=digest(body)
        previous=conn.execute('SELECT * FROM conversation_proposals WHERE segment_id=? AND kind=? AND body_hash=?',(segment['id'],kind,checksum)).fetchone()
        details={'values':values,'requires_user_confirmation':True} if kind=='plan' or (kind=='pipeline' and values.get('action') in {'plan','grant','replan_after_unknown'}) else {}
        if previous:return {'proposal_id':previous['id'],'hash':checksum,'state':previous['state'],**details}
        # A new version invalidates pending cards of the same kind in this segment.
        conn.execute("UPDATE conversation_proposals SET state='stale' WHERE segment_id=? AND kind=? AND state='proposed'",(segment['id'],kind))
        id=new_id();conn.execute('INSERT INTO conversation_proposals(id,segment_id,kind,body_json,body_hash,created_at) VALUES (?,?,?,?,?,?)',(id,segment['id'],kind,encode(body),checksum,now()))
        return {'proposal_id':id,'hash':checksum,'state':'proposed',**details}

    def view(self,session):
        with self.store.connection() as conn:
            segment=self.segment(conn,session)
            proposals=[]
            for r in conn.execute('SELECT * FROM conversation_proposals WHERE segment_id=? ORDER BY created_at,id',(segment['id'],)):
                p=dict(r);p['body']=json.loads(p.pop('body_json'));p['receipt']=json.loads(p.pop('receipt_json')) if p['receipt_json'] else None;proposals.append(p)
            return {'segment_id':segment['id'],'work_id':segment['work_id'],'context':json.loads(segment['context_json']),
                'result_messages':[{'role':'assistant','content':v.get('answer',''),'serverTurnId':t['id'],'resultState':t['state'],'deliveryError':v.get('delivery_error')} for t in conn.execute("SELECT id,state,payload_json FROM conversation_turns WHERE segment_id=? AND json_extract(payload_json,'$.origin')='task_result' ORDER BY created_at,id",(segment['id'],)) for v in [json.loads(t['payload_json'])]],
                'proposals':proposals,'messages':[message for t in conn.execute('SELECT payload_json FROM conversation_turns WHERE segment_id=? ORDER BY created_at,id',(segment['id'],)) for message in self._visible_messages(json.loads(t['payload_json']))], 'turns':[{'id':r['id'],'state':r['state']} for r in conn.execute('SELECT id,state FROM conversation_turns WHERE segment_id=?',(segment['id'],))]}

    @staticmethod
    def _visible_messages(payload):
        messages=[]
        if payload.get('message'):messages.append({'role':'user','content':payload['message']})
        if payload.get('answer'):messages.append({'role':'assistant','content':payload['answer']})
        return messages

    def apply(self,session,id,checksum,command_id,*,dismiss=False,_connection=None,_turn_id=None):
        def execute(conn):
            p=row(conn,'conversation_proposals',id);segment=self.segment(conn,session,p['segment_id'])
            if conn.execute("SELECT 1 FROM conversation_turns WHERE segment_id=? AND id!=? AND state IN ('reserved','active','dispatching','unknown')",(segment['id'],_turn_id or '')).fetchone():fail('invocation_pending','本轮尚未结束，请先核实结果',409)
            if self.segment(conn,session)['id']!=segment['id']:fail('stale_revision','当前创作依据已切换，旧卡不可提交',409)
            if p['body_hash']!=checksum:fail('stale_revision','提议已变化',409)
            if p['state']=='applied':
                from .conversation_results import public_receipt
                return public_receipt(json.loads(p['receipt_json']))
            if p['state']!='proposed':fail('stale_revision','此卡已失效，请查看最新提议',409)
            if dismiss:
                conn.execute("UPDATE conversation_proposals SET state='dismissed' WHERE id=?",(id,));return {'dismissed':True}
            body=json.loads(p['body_json']);values=body['values'];target=body['target'];kind=p['kind']
            self.source_refs(conn,segment,body['source_refs'],allow_results=True)
            if kind=='pipeline':
                from .conversation_pipeline import execute_action
                result=execute_action(self,conn,segment,body,command_id)
            elif kind=='draft':
                if segment['work_id']:fail('work_already_bound','运行段已绑定作品',409)
                if set(values)-{'title','input_text'}:fail('invalid_input','草稿字段无效')
                if target.get('channel'):
                    current=row(conn,'channels',target['channel_id'])
                    if current['revision']!=target['channel']['revision']:fail('stale_revision','频道默认已变化，请重新选择',409)
                result=self.service.command('create',{**values,'profile_ref':segment['profile_ref'],'channel_id':target.get('channel_id'),'settings':target.get('settings',{}),'session_id':session},command_id=command_id+'_work',_connection=conn)
                conn.execute('UPDATE conversation_segments SET work_id=? WHERE id=?',(result['work_id'],segment['id']))
                conn.execute('INSERT OR IGNORE INTO work_conversation_links VALUES (?,?,?)',(result['work_id'],session,now()))
                self._capture_messages(conn,segment,result['work_id'])
                # Planning can be proposed during discussion before a Work exists.
                # After draft approval, issue a new card against the saved Work;
                # keep the old hash stale rather than running with revision=None.
                pending_plans=conn.execute("SELECT body_json FROM conversation_proposals WHERE segment_id=? AND kind='plan' AND state='proposed' AND json_extract(body_json,'$.work_id') IS NULL",(segment['id'],)).fetchall()
                bound=self.segment(conn,session,segment['id'])
                for pending_plan in pending_plans:
                    proposed=json.loads(pending_plan['body_json'])
                    self.proposal(conn,bound,'plan',proposed['values'],proposed['source_refs'])
            elif kind in {'plan','revision'}:
                if not segment['work_id']:fail('work_not_bound','请先确认作品',409)
                allowed={'request','services','duration_seconds'} if kind=='plan' else {'feedback','protected','interval'}
                if set(values)-allowed:fail('invalid_input','提案字段无效')
                if kind=='plan':
                    from .conversation_pipeline import planning_values
                    payload=planning_values(self,conn,segment,values,applying=True)
                else:payload={'output_id':target.get('output_id'),'feedback':str(values.get('feedback',''))+'\n保护项：'+encode(values.get('protected',[]))+'\n区间：'+encode(values.get('interval'))}
                result=self.service.command('plan' if kind=='plan' else 'revise',payload,command_id=command_id+'_work',work_id=segment['work_id'],expected_revision=body['work_revision'],_connection=conn)
            elif kind in {'channel_create','channel_defaults'}:
                if set(values)-{'name','creative_basis','settings'}:fail('invalid_input','频道提案字段无效')
                channel=target.get('channel') if kind=='channel_defaults' else None
                if kind=='channel_defaults' and not channel:fail('invalid_input','没有指定目标频道')
                if channel:
                    values={**values}
                    if 'creative_basis' in values and not isinstance(values['creative_basis'],dict):fail('invalid_input','频道创作依据格式无效')
                    if 'creative_basis' in values:values['creative_basis']={**channel.get('creative_basis',{}),**values['creative_basis']}
                    if 'settings' in values:
                        patch=values['settings'];old=channel.get('settings',{})
                        if not isinstance(patch,dict):fail('invalid_input','频道设置格式无效')
                        if 'subtitles' in patch and not isinstance(patch['subtitles'],dict):fail('invalid_input','字幕设置格式无效')
                        values['settings']={**old,**patch}
                        if 'subtitles' in patch:values['settings']['subtitles']={**old.get('subtitles',{}),**patch['subtitles']}
                result=CreativeCatalog(self.service).command('channels','edit' if channel else 'create',{**values,'profile_ref':segment['profile_ref']},command_id=command_id+'_catalog',id=channel['id'] if channel else None,expected_revision=channel['revision'] if channel else None,_connection=conn)
                if not channel and not segment['work_id']:
                    resolved={**target.get('settings',{}),**values.get('settings',{})}
                    if 'subtitles' in values.get('settings',{}):resolved['subtitles']={**target.get('settings',{}).get('subtitles',{}),**values['settings']['subtitles']}
                    target['settings']=resolved
                    target['channel_id']=result['id'];target['channel']={'id':result['id'],'revision':result['revision'],'name':values.get('name'),'creative_basis':values.get('creative_basis',{})}
                    conn.execute('UPDATE conversation_segments SET context_json=? WHERE id=?',(encode(target),segment['id']))
                if not segment['work_id']:
                    saved=row(conn,'channels',result['id'])
                    from .production.settings import merge_creation_settings
                    settings=merge_creation_settings(json.loads(row(conn,'profile_refs',segment['profile_ref'])['settings_json']),json.loads(saved['settings_json']))
                    for key in ('director_revision','director_trial'):
                        if key in target.get('settings',{}):settings[key]=target['settings'][key]
                    target.update(channel_id=saved['id'],channel={'id':saved['id'],'name':saved['name'],'revision':saved['revision'],'creative_basis':json.loads(saved['creative_basis_json'])},settings=settings)
                    conn.execute('UPDATE conversation_segments SET context_json=? WHERE id=?',(encode(target),segment['id']))
            elif kind=='director_formation':
                if set(values)-{'name','reference_input_ids','analysis_scope','base_director_id','base_revision'}:fail('invalid_input','导演提案字段无效')
                if not segment['work_id']:fail('work_not_bound','请先确认参考作品并登记视频',409)
                if values.get('base_director_id'):
                    selected=target.get('settings',{}).get('director_revision')
                    if not selected or row(conn,'director_revisions',selected)['director_id']!=values['base_director_id']:
                        fail('permission_missing','重新拆解只能针对本次明确选择的导演',403)
                result=CreativeCatalog(self.service).command('directors','analyze' if values.get('base_director_id') else 'create',
                    {'name':values.get('name'),'reference_input_ids':values.get('reference_input_ids',[]),'analysis_scope':values.get('analysis_scope','full'),'work_id':segment['work_id'],'work_revision':body['work_revision']},
                    command_id=command_id+'_catalog',id=values.get('base_director_id'),expected_revision=values.get('base_revision'),_connection=conn)
            elif kind=='profile':
                result=self._profile_save(conn,segment,body,command_id)
            elif kind=='director_revision':
                version_id=target.get('settings',{}).get('director_revision')
                version=row(conn,'director_revisions',version_id or '')
                director=row(conn,'directors',version['director_id'])
                if values.get('base_revision')!=director['revision']:fail('stale_revision','导演已变化',409)
                if set(values)-{'style','base_revision'}:fail('invalid_input','风格提案字段无效')
                result=CreativeCatalog(self.service).command('directors','revision',{'style':values['style'],'evidence':json.loads(version['evidence_json'])},command_id=command_id+'_catalog',id=director['id'],expected_revision=director['revision'],_connection=conn)
            else:fail('invalid_input','尚不支持此提议')
            from .conversation_results import watched_receipt
            conn.execute("UPDATE conversation_proposals SET state='applied',receipt_json=? WHERE id=?",(encode(watched_receipt(conn,result)),id))
            return result
        return self.store.execute_command(command_id,{'proposal':id,'hash':checksum,'session':session,'dismiss':dismiss},execute,connection=_connection)

    def _capture_messages(self,conn,segment,work_id):
        # Preserve necessary user evidence independently of deleting chat text.
        entries=[{'kind':'user_requirement','text':json.loads(r['payload_json'])['message'],'source_refs':[r['id']]} for r in self.scoped_turns(conn,segment) if json.loads(r['payload_json']).get('message')]
        body={'entries':entries,'handoff':json.loads(segment['context_json']).get('handoff')}
        conn.execute('INSERT INTO work_briefs VALUES (?,1,?,?,?)',(work_id,encode(body),digest(body),now()))

    def _profile_save(self,conn,segment,body,command_id):
        import os, tempfile
        from .production.editors.ffmpeg import _lock
        values=body['values']
        if set(values)!={'file','before_hash','after','entries'} or not isinstance(values['file'],str) or values['file'] not in {'style','preferences','memory'} or not isinstance(values['before_hash'],str) or len(values['before_hash'])!=64 or not isinstance(values['after'],str) or len(values['after'])>100000 or not isinstance(values['entries'],list) or not 1<=len(values['entries'])<=3:fail('invalid_input','请选择1～3条明确画像偏好及文件差异')
        if not segment['profile_ref']:fail('invalid_input','未选择画像，不自动创建或写入')
        profile=row(conn,'profile_refs',segment['profile_ref']);root=(self.service.profiles/profile['name'])
        path=root/(values['file']+'.md')
        if root.is_symlink() or path.is_symlink() or root.resolve().parent!=self.service.profiles:fail('permission_missing','画像路径无效',403)
        root.mkdir(exist_ok=True)
        with _lock(root/'.conversation-save.lock'):
            before=path.read_text(encoding='utf-8') if path.exists() else ''
            after=values['after'];current=hashlib.sha256(before.encode()).hexdigest();after_hash=hashlib.sha256(after.encode()).hexdigest()
            if current not in {values['before_hash'],after_hash}:fail('stale_revision','画像已被其他编辑修改，请重新比较',409)
            # Recovery of a file write whose SQLite receipt was interrupted.
            if current!=after_hash:
                if any(isinstance(e,str) and e.strip() and e in before for e in values['entries']):fail('duplicate_preference','所选条目已存在，不重复追加',409)
                if not after.startswith(before) or any(not isinstance(e,str) or not e.strip() or e not in after[len(before):] for e in values['entries']):fail('invalid_input','长期保存仅追加卡片显示的条目，不覆盖已有画像')
                with tempfile.NamedTemporaryFile(mode='w',encoding='utf8',dir=root,delete=False) as tmp:
                    tmp.write(after);tmp.flush();os.fsync(tmp.fileno());name=tmp.name
                os.replace(name,path)
            return {'target_ref':profile['id'],'file':values['file'],'before_hash':values['before_hash'],'after_hash':after_hash,'command_id':command_id}

    def revoke(self,session):
        with self.store.transaction() as conn:
            conn.execute('UPDATE conversation_segments SET revoked_at=? WHERE ui_session=?',(now(),session))
            # Retain minimal tool/command identities for late result reconciliation.
            for t in conn.execute('SELECT t.* FROM conversation_turns t JOIN conversation_segments s ON s.id=t.segment_id WHERE s.ui_session=?',(session,)).fetchall():
                payload=json.loads(t['payload_json']);payload.pop('message',None);payload.pop('attachments',None);payload.pop('prompt',None);payload.pop('context',None);payload.pop('answer',None)
                payload.pop('result_prompt',None);payload.pop('delivery_error',None)
                if payload.get('result_event'):payload['result_event']={k:v for k,v in payload['result_event'].items() if k in {'work_id','run_id','seq','run_state'}}
                payload['results']={k:{x:v for x,v in result.items() if x in {'work_id','proposal_id','revision','brief_revision','brief_hash','hash','state','input_id','requires_card_confirmation'}} for k,result in payload.get('results',{}).items()}
                conn.execute('UPDATE conversation_turns SET payload_json=? WHERE id=?',(encode(payload),t['id']))
            conn.execute("UPDATE conversation_proposals SET state='dismissed' WHERE segment_id IN (SELECT id FROM conversation_segments WHERE ui_session=?) AND state='proposed'",(session,))
        return {'deleted':True,'works_preserved':True}
