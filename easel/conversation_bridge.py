"""Persistent OpenClaw lifecycle and bounded tools. No model-supplied authority."""
from __future__ import annotations
from dataclasses import asdict
import hashlib
import json
import secrets
from typing import Literal
from pydantic import Field
from .work_bridge import Strict, Identity, Claim, Call, Dispatch, Invocation, ContextArgs, DraftArgs, PlanArgs, canonical, reject
from .conversation import ConversationService
from .production.service import row, encode, digest, now


class EvidenceArgs(Strict):
    input_ids: list[str] = Field(default_factory=list,max_length=100)

class RegisterArgs(Strict):
    attachment_id: str
    usage: Literal['reference','must_use'] = 'reference'
    original_audio: bool = False
    rights: dict = Field(default_factory=dict)

class BriefArgs(Strict):
    entries: list[dict] = Field(min_length=1,max_length=100)

class RevisionArgs(Strict):
    feedback: str = Field(min_length=1,max_length=10000)
    protected: list[str] = Field(default_factory=list,max_length=100)
    interval: dict | None = None

class ProposalArgs(Strict):
    kind: Literal['channel_create','channel_defaults','director_formation','profile','director_revision']
    values: dict
    source_refs: list[str] = Field(min_length=1,max_length=40)

class PipelineArgs(Strict):
    mode: Literal['pending','bind','draft','offer','answer']
    action: str = ''
    values: dict = Field(default_factory=dict)
    summary: str = Field(default='', max_length=10000)
    user_quote: str = Field(default='', max_length=10000)
    proposal_id: str = ''
    hash: str = ''
    dismiss: bool = False

TOOLS={
    'easel_pipeline':PipelineArgs,
    'easel_work_context':ContextArgs,'easel_work_create_draft':DraftArgs,'easel_work_request_plan':PlanArgs,
    'easel_work_input_evidence':EvidenceArgs,'easel_work_register_inputs':RegisterArgs,
    'easel_work_update_brief':BriefArgs,'easel_work_request_revision':RevisionArgs,'easel_work_propose':ProposalArgs,
}

class PersistentCall(Identity):
    tool_call_id: str = Field(min_length=1,max_length=256)
    tool: Literal['easel_pipeline','easel_work_context','easel_work_create_draft','easel_work_request_plan','easel_work_input_evidence','easel_work_register_inputs','easel_work_update_brief','easel_work_request_revision','easel_work_propose']
    params: dict

class PersistentDispatch(PersistentCall):
    ticket: str = Field(min_length=24,max_length=128)


class PersistentWorkToolBridge:
    def __init__(self,service):
        self.service,self.store=service,service.store
        self.conversations=ConversationService(service)

    @staticmethod
    def _args(request):
        from pydantic import ValidationError
        try:return TOOLS[request.tool].model_validate(request.params).model_dump()
        except (ValidationError,KeyError):reject('invalid_tool_arguments',400)

    def reserve(self,*,ui_session,turn_id,segment_id,message,attachments):
        with self.store.transaction() as conn:
            segment=self.conversations.segment(conn,ui_session,segment_id)
            fingerprint=digest({'segment_id':segment_id,'message':message,'attachments':attachments})
            prior=conn.execute('SELECT * FROM conversation_turns WHERE id=?',(turn_id,)).fetchone()
            if prior:
                if prior['request_hash']!=fingerprint:reject('turn_conflict',409)
                return {'new':False,'state':prior['state'],'payload':json.loads(prior['payload_json'])}
            if self.conversations.segment(conn,ui_session)['id']!=segment_id:reject('stale_revision',409)
            if conn.execute("SELECT 1 FROM conversation_turns t JOIN conversation_segments s ON s.id=t.segment_id WHERE s.ui_session=? AND t.state IN ('reserved','dispatching','active','unknown')",(ui_session,)).fetchone():reject('invocation_pending',409)
            # Validate attachments through the same production path using a temporary read-only validator.
            from .conversation_inputs import validate_attachment
            for attachment in attachments:validate_attachment(self.service,ui_session,attachment)
            revision=row(conn,'works',segment['work_id'])['revision'] if segment['work_id'] else None
            payload={'message':message,'attachments':attachments,'work_id':segment['work_id'],'revision':revision,
                     'session_key':'agent:easel-video:'+segment['id'],'native_session_id':segment['native_session_id'],
                     'run_id':None,'tickets':{},'results':{},'calls':{},'answer':''}
            conn.execute('INSERT INTO conversation_turns VALUES (?,?,?,?,?,?)',(turn_id,segment['id'],fingerprint,encode(payload),'reserved',now()))
            from .conversation_pipeline import pending
            context=pending(self.conversations,conn,segment)
            prompt='用户本轮：'+message+'\n【服务端创作上下文与来源，只适用于本运行段】\n'+encode(context)
            payload['visible_proposals']=[r[0] for r in conn.execute("SELECT id FROM conversation_proposals WHERE segment_id=? AND state IN ('proposed','applied')",(segment_id,))]
            payload['prompt_hash']=hashlib.sha256(prompt.encode()).hexdigest()
            # Only visible, scoped content is forwarded, never main transcripts or credentials.
            self._save(conn,turn_id,payload,'reserved')
            return {'new':True,'state':'reserved','prompt':prompt,'payload':payload}

    @staticmethod
    def _save(conn,id,payload,state):
        conn.execute('UPDATE conversation_turns SET payload_json=?,state=? WHERE id=?',(encode(payload),state,id))

    def _current(self,conn,identity,active=True):
        if identity.agent_id!='easel-video' or not identity.session_key.startswith('agent:easel-video:'):reject('binding_mismatch')
        sid=identity.session_key.removeprefix('agent:easel-video:')
        segment=row(conn,'conversation_segments',sid)
        if segment['revoked_at'] and active:reject('binding_mismatch')
        record=conn.execute('SELECT * FROM conversation_turns WHERE segment_id=? ORDER BY created_at DESC,id DESC LIMIT 1',(sid,)).fetchone()
        if not record:reject('binding_mismatch')
        payload=json.loads(record['payload_json'])
        if payload.get('run_id')!=identity.run_id or segment['native_session_id']!=identity.session_id or (active and record['state']!='active'):reject('binding_mismatch')
        return dict(record),payload,segment

    def claim(self,request:Claim):
        with self.store.transaction() as conn:
            if request.agent_id!='easel-video' or not request.session_key.startswith('agent:easel-video:'):reject('binding_mismatch')
            sid=request.session_key.removeprefix('agent:easel-video:')
            segment=row(conn,'conversation_segments',sid)
            record=conn.execute('SELECT * FROM conversation_turns WHERE segment_id=? ORDER BY created_at DESC,id DESC LIMIT 1',(sid,)).fetchone()
            if not record or segment['revoked_at']:reject('binding_mismatch')
            payload=json.loads(record['payload_json'])
            if record['state'] not in {'reserved','dispatching','active'} or payload.get('prompt_hash')!=hashlib.sha256(request.prompt.encode()).hexdigest() or (payload.get('run_id') and payload['run_id']!=request.run_id) or (segment['native_session_id'] and segment['native_session_id']!=request.session_id):reject('binding_mismatch')
            # Native run IDs must never be adopted by a second invocation.
            duplicate=conn.execute("SELECT 1 FROM conversation_turns WHERE id!=? AND json_extract(payload_json,'$.run_id')=?",(record['id'],request.run_id)).fetchone()
            if duplicate:reject('binding_mismatch')
            conn.execute('UPDATE conversation_segments SET native_session_id=? WHERE id=?',(request.session_id,sid))
            payload['native_session_id']=request.session_id;payload['run_id']=request.run_id
            self._save(conn,record['id'],payload,'active')
            return {'bound':True}

    def prepare(self,request:PersistentCall):
        with self.store.transaction() as conn:
            record,payload,_=self._current(conn,request);self._args(request)
            ticket=secrets.token_urlsafe(32)
            payload['tickets'][ticket]=digest(request.model_dump())
            self._save(conn,record['id'],payload,'active')
            return {'ticket':ticket}

    def dispatch(self,request:PersistentDispatch):
        with self.store.transaction() as conn:
            record,payload,segment=self._current(conn,request)
            if payload['tickets'].get(request.ticket)!=digest(request.model_dump(exclude={'ticket'})):reject('ticket_mismatch')
            args=self._args(request);fingerprint=digest([request.tool,args])
            if fingerprint in payload['results']:return payload['results'][fingerprint]
            # Business receipt and intent binding are committed in this SAME transaction.
            command_id='chat_'+digest([record['id'],request.tool,args])[:48]
            if payload.get('pipeline_entry'):reject('pipeline_switch_pending',409)
            if request.tool=='easel_pipeline':
                from .conversation_pipeline import dispatch
                result=dispatch(self,conn,record,payload,segment,args,command_id)
            elif request.tool=='easel_work_context':result=self.conversations.context(conn,segment)
            elif request.tool=='easel_work_input_evidence':
                result={'inputs':[]}
                for id in args['input_ids']:
                    value=row(conn,'work_inputs',id)
                    if value['work_id']!=segment['work_id']:reject('binding_mismatch')
                    result['inputs'].append({k:value[k] for k in ('id','kind','usage','digest','text_content','metadata_json')})
            elif request.tool=='easel_work_register_inputs':
                if not segment['work_id']:reject('work_not_bound',409)
                attachment=next((a for t in self.conversations.scoped_turns(conn,segment) for a in json.loads(t['payload_json']).get('attachments',[]) if a['id']==args['attachment_id']),None)
                if not attachment:reject('attachment_not_bound')
                # Model suggestions never mint third-party rights or original-audio permission.
                if args['original_audio'] or args['rights']:reject('rights_confirmation_required')
                result=self.service.command('input',{'session_id':segment['ui_session'],'attachment':attachment,'usage':args['usage'],'original_audio':False},command_id=command_id,work_id=segment['work_id'],expected_revision=payload['revision'],_connection=conn)
            elif request.tool=='easel_work_update_brief':
                if row(conn,'works',segment['work_id'] or '')['revision']!=payload['revision']:reject('stale_revision',409)
                result=self.conversations.brief(conn,segment,args['entries'])
            else:
                if segment['work_id'] and row(conn,'works',segment['work_id'])['revision']!=payload['revision']:reject('stale_revision',409)
                refs=[record['id']]
                if request.tool=='easel_work_create_draft':kind,values='draft',args
                elif request.tool=='easel_work_request_plan':kind,values='plan',args
                elif request.tool=='easel_work_request_revision':kind,values='revision',args
                else:kind,values,refs=args['kind'],args['values'],args['source_refs']
                result=self.conversations.proposal(conn,segment,kind,values,refs)
                result['requires_user_confirmation']=True
            if 'revision' in result and 'work_id' in result:payload['revision']=result['revision']
            payload['calls'][request.tool_call_id]={'fingerprint':fingerprint,'command_id':command_id}
            payload['results'][fingerprint]=result
            self._save(conn,record['id'],payload,'active')
            return result

    def end(self,request):
        with self.store.transaction() as conn:
            record,payload,segment=self._current(conn,request,active=False)
            self._save(conn,record['id'],payload,'ended')
            if not segment['revoked_at'] and payload.get('pipeline_entry') and not payload.get('pipeline_binding'):
                conn.execute('SAVEPOINT pipeline_handoff')
                try:
                    result=self.conversations.enter(segment['ui_session'],payload['pipeline_entry'],'handoff_'+record['id'],_connection=conn)
                    bound=self.conversations.segment(conn,segment['ui_session'],result['segment_id'])
                    context=json.loads(bound['context_json'])
                    context['handoff']=payload['pipeline_handoff']
                    conn.execute('UPDATE conversation_segments SET context_json=? WHERE id=?',(encode(context),bound['id']))
                    payload['pipeline_binding']=result
                except Exception as exc:
                    from .production.errors import ProductionError
                    if not isinstance(exc,ProductionError):raise
                    conn.execute('ROLLBACK TO pipeline_handoff')
                    payload['pipeline_binding']={'error':exc.code,'message':str(exc)}
                finally:conn.execute('RELEASE pipeline_handoff')
                self._save(conn,record['id'],payload,'ended')
            return {'ended':True}

    def delivery(self,turn_id,state,answer=None):
        with self.store.transaction() as conn:
            record=row(conn,'conversation_turns',turn_id);payload=json.loads(record['payload_json'])
            segment=row(conn,'conversation_segments',record['segment_id'])
            if answer is not None and not segment['revoked_at']:payload['answer']=answer
            # Delivery ending is not proof native execution ended; unknown remains occupied.
            if record['state']=='ended':state='ended'
            self._save(conn,turn_id,payload,state)


def require_persistent_gateway(base_url,token):
    from .work_bridge import require_gateway_bridge
    return require_gateway_bridge(base_url,token,expected_tools=set(TOOLS),protocol=2)
