"""Opt-in video conversation HTTP adapter; ordinary Easel chat is unchanged."""
from __future__ import annotations
import asyncio
import json
import logging
import os
import secrets
from pathlib import Path

import httpx
from fastapi import APIRouter, Header
from pydantic import BaseModel, ConfigDict, Field
from sse_starlette.sse import EventSourceResponse

from easel.conversation import ConversationService
from easel.conversation_bridge import PersistentWorkToolBridge, PersistentCall, PersistentDispatch, ExecutionPoll, BootstrapContext, require_persistent_gateway
from easel.work_bridge import Claim, Identity
from easel.production.service import fail
from easel.native_diagnostics import NativeEnd
from easel.conversation_compaction import ContextPreparation, ContextPreparationError, SessionRPC


def interrupt_committed_handoff(url, token, payload):
    """Stop only the obsolete native run; agent_end still owns binding."""
    rpc=SessionRPC(url,token)
    try:
        current=rpc.describe(payload['session_key'])
        if current.get('sessionId')!=payload['native_session_id']:
            raise ValueError('handoff_session_changed')
        return rpc.client.rpc('chat.abort',{'sessionKey':payload['session_key'],
            'runId':payload['run_id'],'agentId':'main','preserveSideRuns':True})
    finally:
        rpc.close()


class Entry(BaseModel):
    model_config=ConfigDict(extra='forbid')
    command_id:str=Field(min_length=1,max_length=100)
    entry:dict=Field(default_factory=dict)

class ProposalAction(BaseModel):
    model_config=ConfigDict(extra='forbid')
    command_id:str=Field(min_length=1,max_length=100)
    hash:str
    dismiss:bool=False


class ReferenceImport(BaseModel):
    model_config=ConfigDict(extra='forbid')
    command_id:str=Field(min_length=1,max_length=100,pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]*$')
    segment_id:str
    expected_revision:int=Field(gt=0)
    url:str=Field(min_length=1,max_length=4000)


def create_router(provider):
    router=APIRouter(prefix='/api/chat/video')
    @router.get('/{session}')
    def view(session:str):return ConversationService(provider()).view(session)
    @router.post('/{session}/enter')
    def enter(session:str,request:Entry):return ConversationService(provider()).enter(session,request.entry,request.command_id)
    @router.post('/{session}/proposals/{id}/apply')
    def apply(session:str,id:str,request:ProposalAction):return ConversationService(provider()).apply(session,id,request.hash,request.command_id,dismiss=request.dismiss)
    @router.post('/{session}/reference-import')
    def reference_import(session:str,request:ReferenceImport):
        from easel.reference_import import import_reference
        try:
            return import_reference(provider(),session,request.segment_id,request.url,request.command_id,request.expected_revision)
        except Exception as exc:
            from easel.production.errors import ProductionError
            if isinstance(exc,ProductionError):raise
            fail('reference_import_unavailable','参考导入未完成，已保留待核实记录；可改为上传已取得的视频',503)
    @router.delete('/{session}')
    def delete(session:str):return ConversationService(provider()).revoke(session)
    return router


class EntryCall(Claim):
    mode: str
    kind: str = ''
    user_quote: str = ''
    tool_call_id: str = ''


class NaturalEntry:
    """Ephemeral authority for an active Web turn; durable state uses enter/turns."""
    def __init__(self):
        import threading
        self.lock = threading.RLock()
        self.turns = {}

    def reserve(self, session, native, turn, prompt, message, profile, attachments=None, *, quoted_message=None):
        with self.lock:
            # HTTP Gateway owns the native UUID and may ignore the client hint.
            # Adopt it only from the authenticated hook claiming this exact turn.
            self.turns['agent:main:'+session] = dict(session=session, native=None,
                turn=turn, prompt=prompt, message=message, quoted_message=quoted_message or message,
                profile=profile, attachments=attachments or [], run=None, result=None)

    def release(self, session, turn):
        with self.lock:
            key='agent:main:'+session
            if self.turns.get(key,{}).get('turn')==turn:self.turns.pop(key,None)

    def call(self, service, request):
        import hashlib
        from easel.production.service import encode, now, row
        from easel.conversation_pipeline import pending
        with self.lock:
            t=self.turns.get(request.session_key)
            if request.agent_id=='main' and not t and request.mode=='claim':
                return {'bound':False}
            if request.agent_id!='main' or not t:
                fail('binding_mismatch','当前Web讨论回合未绑定',409)
            if request.mode=='claim':
                if (request.prompt!=t['prompt'] or t['run'] not in (None,request.run_id)
                        or t['native'] not in (None,request.session_id)):
                    fail('binding_mismatch','当前输入或原生回合不匹配',409)
                t['native']=request.session_id
                t['run']=request.run_id
                return {'bound':True}
            if request.mode=='end':
                if t['run']!=request.run_id or t['native']!=request.session_id:
                    fail('binding_mismatch','入口结束身份不匹配',409)
                if t['result']:
                    with service.store.transaction() as conn:
                        source=row(conn,'conversation_turns',t['result']['source_turn_id'])
                        payload=json.loads(source['payload_json'])
                        payload['pipeline_binding']={'segment_id':t['result']['segment_id']}
                        conn.execute('UPDATE conversation_turns SET payload_json=? WHERE id=?',(encode(payload),source['id']))
                return {'ended':True}
            if request.mode!='enter' or t['run']!=request.run_id or t['native']!=request.session_id or not request.tool_call_id:
                fail('binding_mismatch','入口需要当前原生工具回执',409)
            # Native claim authenticates the current Web turn. Model text is
            # never an authority source; legacy user_quote is accepted but ignored.
            if request.kind not in ('new_work','channel_create','director_formation'):
                fail('invalid_input','入口只接受既有管线类型',400)
            if t['result']:
                if request.kind!=t['kind']:fail('binding_mismatch','本轮已进入另一管线',409)
                return t['result']
            if not t['profile'] and request.kind=='channel_create':fail('invalid_input','创建频道须先选择画像；临时视频创作不需要画像',400)
            conversations=ConversationService(service)
            cid='natural_entry_'+hashlib.sha256((t['session']+'\0'+t['turn']).encode()).hexdigest()[:40]
            with service.store.transaction() as conn:
                result=conversations.enter(t['session'],{'kind':request.kind,'profile_ref':t['profile']},cid,_connection=conn)
                # Keep genuine user input as an ended source, not a new execution or grant.
                payload={'origin':'user','message':t['message'],'attachments':t['attachments'],
                    'session_key':'agent:main:easel-pipeline:'+result['segment_id'],
                    'answer':'','tickets':{},'results':{},'calls':{}}
                conn.execute('INSERT OR IGNORE INTO conversation_turns VALUES (?,?,?,?,?,?)',
                    (cid,result['segment_id'],hashlib.sha256(t['message'].encode()).hexdigest(),encode(payload),'ended',now()))
                segment=conversations.segment(conn,t['session'],result['segment_id'])
                state=pending(conversations,conn,segment)
            t['kind']=request.kind
            t['result']={'entered':True,'segment_id':result['segment_id'],'source_turn_id':cid,'pending':state,
                'instruction':'只建立讨论上下文，未创建作品或授权费用。本轮停止其他工具并简短结束；宿主在原生结束后自动续接，不要求用户回复继续，缺项由目标管线合并询问。'}
            return t['result']

    def source(self, session, turn):
        with self.lock:
            value=self.turns.get('agent:main:'+session,{})
            return (value.get('result') or {}).get('source_turn_id') if value.get('turn')==turn else None


natural_entry = NaturalEntry()


def create_internal_router(provider,token_provider):
    router=APIRouter(prefix='/api/chat/work-tools')
    def authenticate(value):
        token=token_provider()
        if not token or len(token)<24 or not secrets.compare_digest(value or '','Bearer '+token):
            fail('bridge_unauthorized','作品工具桥未配置或凭证无效',401)
        return PersistentWorkToolBridge(provider())
    @router.post('/entry')
    def entry(request:EntryCall,authorization:str|None=Header(default=None)):
        bridge=authenticate(authorization)
        return natural_entry.call(bridge.service,request)
    @router.post('/claim')
    def claim(request:Claim,authorization:str|None=Header(default=None)):return authenticate(authorization).claim(request)
    @router.post('/bootstrap')
    def bootstrap(request:BootstrapContext,authorization:str|None=Header(default=None)):
        return authenticate(authorization).bootstrap(request)
    @router.post('/prepare')
    def prepare(request:PersistentCall,authorization:str|None=Header(default=None)):return authenticate(authorization).prepare(request)
    @router.post('/dispatch')
    def dispatch(request:PersistentDispatch,authorization:str|None=Header(default=None)):return authenticate(authorization).dispatch(request)
    @router.post('/result')
    def execution_result(request:ExecutionPoll,authorization:str|None=Header(default=None)):
        from easel.conversation_results import ConversationResults
        return ConversationResults(authenticate(authorization)).poll(request)
    @router.post('/end')
    def end(request:NativeEnd,authorization:str|None=Header(default=None)):return authenticate(authorization).end(request)
    return router


class VideoChat:
    """Owns only delivery; native lifecycle establishes tool authority independently."""
    def __init__(self,provider,event_file,save_turn,*,gateway_url=None,gateway_token=None,preflight=None,context_preparer=ContextPreparation,handoff_interrupter=interrupt_committed_handoff):
        self.provider,self.event_file,self.save_turn=provider,event_file,save_turn
        self.gateway_url=gateway_url or os.environ.get('EASEL_VIDEO_GATEWAY_URL','')
        self.gateway_token=gateway_token or os.environ.get('EASEL_VIDEO_GATEWAY_TOKEN','')
        self.preflight=preflight or require_persistent_gateway
        self.context_preparer=context_preparer
        self.handoff_interrupter=handoff_interrupter
        self.tasks={}

    @staticmethod
    def interrupted_result(service,session,turn_id=None):
        view=ConversationService(service).view(session)
        message='本轮对话回复中断；已保存的操作请以实际任务状态为准，不会自动重发。'
        if turn_id:
            with service.store.connection() as conn:
                turn=conn.execute('SELECT payload_json FROM conversation_turns WHERE id=? AND segment_id=?',
                    (turn_id,view['segment_id'])).fetchone()
            diagnostic=json.loads(turn[0]).get('model_diagnostic',{}) if turn else {}
            if diagnostic.get('stop_reason')=='length':
                message='本轮助手返回长度限制（length）而中断；现有回执不足以判断是输入上下文还是输出额度所致。不会自动重发，已执行操作以任务回执为准。'
        if view['work_id']:
            work=service.snapshot(view['work_id'])
            tasks=[t for t in work['tasks'] if t['run_id']==work['active_run_id']]
            if any(json.loads(t.get('error_json') or '{}').get('code')=='permission_missing' for t in tasks):
                message+=' 当前任务等待模型服务授权，请在本对话核对所需服务并确认后继续原任务。'
        return view,message

    async def stream(self,req,replay):
        if not req.sessionId or not req.turnId or not req.videoSegmentId:fail('invalid_input','视频对话须带持久运行段和本轮标识',400)
        service=self.provider();bridge=PersistentWorkToolBridge(service)
        with service.store.connection() as conn:
            existing=conn.execute('SELECT 1 FROM conversation_turns WHERE id=?',(req.turnId,)).fetchone()
        if existing:
            await asyncio.to_thread(bridge.reserve,ui_session=req.sessionId,turn_id=req.turnId,segment_id=req.videoSegmentId,message=req.message,attachments=[a.model_dump() for a in req.attachments])
            recovery=ContextPreparation.recoverable(bridge,turn_id=req.turnId)
            if recovery and req.sessionId not in self.tasks:
                path=self.event_file(req.turnId)
                self.tasks[req.sessionId]=asyncio.create_task(self._deliver(req.sessionId,req.turnId,recovery,path))
            return await replay(req.turnId,0)
        if not self.gateway_url or not self.gateway_token:
            fail('capability_unavailable','受限视频对话尚未配置，请核实Gateway和插件接入；本轮未调用模型或制作',503)
        # No model dispatch before plugin-ready validation; never use ordinary main/CLI fallback.
        await asyncio.to_thread(self.preflight,self.gateway_url,self.gateway_token)
        result=await asyncio.to_thread(bridge.reserve,ui_session=req.sessionId,turn_id=req.turnId,segment_id=req.videoSegmentId,message=req.message,attachments=[a.model_dump() for a in req.attachments])
        if not result['new']:
            return await replay(req.turnId,0)
        event_path=self.event_file(req.turnId)
        event_path.parent.mkdir(parents=True,exist_ok=True);event_path.write_text('')
        self.tasks[req.sessionId]=asyncio.create_task(self._deliver(req.sessionId,req.turnId,result,event_path))
        return await replay(req.turnId,0)

    async def _deliver(self,session,turn_id,result,event_path,*,background=False,event_sink=None,display_turn_id=None):
        service=self.provider();bridge=PersistentWorkToolBridge(service)
        seq=0;chunks=[];done=False;next_result_write=0.0;finish_reason=None
        preparation=self.context_preparer(bridge,self.gateway_url,self.gateway_token)
        submitted=False
        # Before a Work is bound, a native turn can hand off to a new segment.
        # Its prose is intermediate; publish only the final segment's reply.
        with service.store.connection() as conn:
            segment=bridge.conversations.segment(conn,session)
        buffer_reply=not segment['work_id']
        if event_path.exists() and event_sink is None:
            for line in event_path.read_text().splitlines():
                try:seq=max(seq,json.loads(line).get('id',0))
                except (ValueError,TypeError):pass
        def emit(kind,data):
            nonlocal seq
            if event_sink is not None:
                event_sink(kind,data)
                return
            seq+=1
            with event_path.open('a',encoding='utf-8') as f:f.write(json.dumps({'id':seq,'event':kind,'data':data},ensure_ascii=False)+'\n')
        emit('activity','正在处理本轮创作，确认执行后等待实际结果')
        async def keep_delivery():
            from easel.conversation_results import ConversationResults
            previous=None
            while True:
                await asyncio.sleep(10)
                await asyncio.to_thread(bridge.delivery_heartbeat,turn_id)
                activity=await asyncio.to_thread(ConversationResults(bridge).activity,turn_id)
                if activity and activity!=previous:
                    emit('activity',activity);previous=activity
        heartbeat=asyncio.create_task(keep_delivery())
        async def stop_obsolete_run():
            # A successful bind has already committed the next immutable target.
            # Do not rely on an LLM to stop asking old-segment tools forever.
            while True:
                await asyncio.sleep(.25)
                with service.store.connection() as conn:
                    record=conn.execute('SELECT state,payload_json FROM conversation_turns WHERE id=?',(turn_id,)).fetchone()
                if not record or record['state']=='ended':return
                payload=json.loads(record['payload_json'])
                if not payload.get('pipeline_entry'):continue
                if not all(payload.get(k) for k in ('session_key','native_session_id','run_id')):return
                emit('activity','正在衔接已确认的创作配置')
                try:
                    await asyncio.to_thread(self.handoff_interrupter,self.gateway_url,self.gateway_token,payload)
                except Exception as exc:
                    logging.getLogger(__name__).warning('Native handoff interruption deferred (%s)',type(exc).__name__)
                return  # Never retry an uncertain native interruption.
        handoff_stop=asyncio.create_task(stop_obsolete_run()) if buffer_reply else None
        try:
            result=await asyncio.to_thread(preparation.prepare,turn_id)
            preparation.submitted(turn_id,result['preparation_owner'])
            submitted=True
            stream_error=None
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(7200,connect=10),trust_env=False,follow_redirects=False) as client:
                    async with client.stream('POST',self.gateway_url.rstrip('/')+'/v1/chat/completions',
                        headers={'Authorization':'Bearer '+self.gateway_token,'x-openclaw-agent-id':'main','x-openclaw-session-key':result['payload']['session_key']},
                        json={'model':'openclaw/main','stream':True,'messages':[{'role':'user','content':result['prompt']}]}) as response:
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            if not line.startswith('data:'):continue
                            raw=line[5:].strip()
                            if raw=='[DONE]':done=True;break
                            value=json.loads(raw)
                            if value.get('error'):raise ValueError('gateway_error')
                            choice=(value.get('choices') or [{}])[0]
                            finish_reason=choice.get('finish_reason') or finish_reason
                            text=(choice.get('delta') or {}).get('content')
                            if text:
                                chunks.append(text)
                                if not buffer_reply:emit('token',text)
                                if background and asyncio.get_running_loop().time()>=next_result_write:
                                    bridge.record_result_text(turn_id,''.join(chunks))
                                    next_result_write=asyncio.get_running_loop().time()+0.25
            except Exception as exc:
                stream_error=exc
            # Native end is the authority to switch context. A stream ending
            # alone never releases an UNKNOWN invocation.
            continuation=None
            for _ in range(100):
                with service.store.connection() as conn:
                    current=conn.execute('SELECT state,payload_json FROM conversation_turns WHERE id=?',(turn_id,)).fetchone()
                data=json.loads(current['payload_json'])
                if not data.get('pipeline_entry'):break
                if current['state']=='ended':
                    continuation=await asyncio.to_thread(bridge.continue_handoff,session,turn_id)
                    break
                await asyncio.sleep(.05)
            if continuation:
                await self._deliver(session,continuation['turn_id'],continuation,event_path,
                    event_sink=emit,display_turn_id=display_turn_id or turn_id)
                return
            if data.get('pipeline_entry'):
                raise ValueError('handoff_not_ready')
            if stream_error:raise stream_error
            if finish_reason=='length':raise ValueError('assistant_output_length')
            if not done or not ''.join(chunks).strip():raise ValueError('incomplete_delivery')
            if buffer_reply:emit('token',''.join(chunks))
            bridge.complete_delivery(turn_id,''.join(chunks))
            view=ConversationService(service).view(session)
            self.save_turn('web:'+session,'done',''.join(chunks),{'turn_id':display_turn_id or turn_id})
            emit('work_card',view)
            emit('done',{'sessionKey':session})
        except ContextPreparationError as exc:
            message='本轮消息尚未发送：上下文准备未完成，原消息与任务记录已保留。'
            if exc.code=='compaction_unresolved':message='历史整理的结果尚待核实，本轮消息未发送；不会重复发起压缩或制作。'
            if background:bridge.record_result_text(turn_id,'',error=message)
            emit('error',message)
        except asyncio.CancelledError:
            if not submitted:
                preparation.cancel(turn_id)
                emit('error','已停止本次回答，本轮消息尚未发送；任务记录已保留。')
                return
            if background:bridge.record_result_text(turn_id,''.join(chunks),error='已停止本次结果回复；制作记录已保留。')
            bridge.delivery(turn_id,'unknown',''.join(chunks))
            emit('error','已停止回答；作品制作继续。原生运行结束前，本轮保持待核实。')
        except Exception as exc:
            bridge.delivery(turn_id,'unknown',''.join(chunks))
            # Record only the exception class; provider bodies may contain private data.
            logging.getLogger(__name__).warning('Video conversation delivery interrupted (%s)',type(exc).__name__)
            message='本轮对话回复中断；尚未核实任务结果，不会自动重发。'
            try:
                # The gateway can emit its stream error just before agent_end reaches
                # the local bridge. Briefly observe that callback; never retry a model
                # or release an UNKNOWN native invocation based on elapsed time.
                for _ in range(10):
                    with service.store.connection() as conn:
                        terminal=conn.execute('SELECT state FROM conversation_turns WHERE id=?',(turn_id,)).fetchone()
                    if not terminal or terminal['state']=='ended':break
                    await asyncio.sleep(.05)
                view,message=self.interrupted_result(service,session,turn_id)
                if finish_reason=='length':message='本轮助手返回长度限制（length）而中断；不能仅凭此回执判断是否耗尽输出额度。已执行操作以任务回执为准，不会自动重发。'
                emit('work_card',view)
                self.save_turn('web:'+session,'done',''.join(chunks),{'turn_id':display_turn_id or turn_id,'clean_end':False})
            except Exception:pass
            if background:bridge.record_result_text(turn_id,''.join(chunks),error=message)
            emit('error',message)
        finally:
            heartbeat.cancel()
            if handoff_stop:handoff_stop.cancel()
            await asyncio.gather(heartbeat,*([handoff_stop] if handoff_stop else []),return_exceptions=True)
            self.tasks.pop(session,None)

    async def process_results_once(self):
        if self.tasks or not self.gateway_url or not self.gateway_token:return False
        service=self.provider()
        recovery=ContextPreparation.recoverable(PersistentWorkToolBridge(service))
        if recovery:
            path=self.event_file(recovery['turn_id']);path.parent.mkdir(parents=True,exist_ok=True)
            self.tasks[recovery['ui_session']]=asyncio.create_task(self._deliver(recovery['ui_session'],recovery['turn_id'],recovery,path,background=recovery['payload'].get('origin')=='task_result'))
            return True
        with service.store.connection() as conn:
            candidate=conn.execute("SELECT 1 FROM conversation_proposals p JOIN runs r ON r.id=json_extract(p.receipt_json,'$.run_id') JOIN works w ON w.id=r.work_id AND w.active_run_id=r.id JOIN conversation_segments s ON s.id=p.segment_id WHERE s.revoked_at IS NULL AND s.id=(SELECT id FROM conversation_segments WHERE ui_session=s.ui_session AND revoked_at IS NULL ORDER BY created_at DESC LIMIT 1) AND p.state='applied' AND json_type(p.receipt_json,'$._result_delivery')='object' AND r.state IN ('succeeded','needs_decision','failed','paused','cancelled') AND EXISTS(SELECT 1 FROM events e WHERE e.work_id=r.work_id AND e.run_id=r.id AND e.seq>json_extract(p.receipt_json,'$._result_delivery.seen_seq') AND e.kind IN ('run_completed','decision_required','task_needs_decision','task_failed','run_cancelled')) LIMIT 1").fetchone()
            reserved=conn.execute("SELECT 1 FROM conversation_turns WHERE state='reserved' AND json_extract(payload_json,'$.origin')='task_result' LIMIT 1").fetchone()
        if not candidate and not reserved:return False
        from easel.conversation_results import ConversationResults
        result=await asyncio.to_thread(ConversationResults(PersistentWorkToolBridge(service)).reserve_next)
        if not result:return False
        if result.get('local_delivery'):
            self.save_turn('web:'+result['ui_session'],'done',result['answer'],{'turn_id':result['turn_id']})
            return True
        try:
            await asyncio.to_thread(self.preflight,self.gateway_url,self.gateway_token)
        except Exception:
            # No chat was submitted: retain the existing reservation for recovery.
            with service.store.transaction() as conn:
                conn.execute("UPDATE conversation_turns SET state='reserved' WHERE id=? AND state='dispatching' AND json_extract(payload_json,'$.run_id') IS NULL",(result['turn_id'],))
            raise
        path=self.event_file(result['turn_id']);path.parent.mkdir(parents=True,exist_ok=True);path.write_text('')
        self.tasks[result['ui_session']]=asyncio.create_task(self._deliver(result['ui_session'],result['turn_id'],result,path,background=True))
        return True

    async def results_forever(self):
        while True:
            try:
                await self.process_results_once()
            except asyncio.CancelledError:raise
            except Exception as exc:
                logging.getLogger(__name__).warning('Conversation result relay deferred (%s)',type(exc).__name__)
                await asyncio.sleep(20)
            await asyncio.sleep(2)

    def stop(self,session):
        task=self.tasks.get(session)
        if task:task.cancel()
        bridge=PersistentWorkToolBridge(self.provider())
        with bridge.store.connection() as conn:
            turns=[r[0] for r in conn.execute("SELECT t.id FROM conversation_turns t JOIN conversation_segments s ON s.id=t.segment_id WHERE s.ui_session=? AND t.state IN ('reserved','dispatching')",(session,))]
        stopped=bool(task)
        for turn_id in turns:
            stopped=self.context_preparer(bridge,self.gateway_url,self.gateway_token).cancel(turn_id) or stopped
        return {'stopped':stopped,'production_cancelled':False}
