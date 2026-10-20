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
from easel.conversation_bridge import PersistentWorkToolBridge, PersistentCall, PersistentDispatch, require_persistent_gateway
from easel.work_bridge import Claim, Identity
from easel.production.service import fail


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


def create_internal_router(provider,token_provider):
    router=APIRouter(prefix='/api/chat/work-tools')
    def authenticate(value):
        token=token_provider()
        if not token or len(token)<24 or not secrets.compare_digest(value or '','Bearer '+token):
            fail('bridge_unauthorized','作品工具桥未配置或凭证无效',401)
        return PersistentWorkToolBridge(provider())
    @router.post('/claim')
    def claim(request:Claim,authorization:str|None=Header(default=None)):return authenticate(authorization).claim(request)
    @router.post('/prepare')
    def prepare(request:PersistentCall,authorization:str|None=Header(default=None)):return authenticate(authorization).prepare(request)
    @router.post('/dispatch')
    def dispatch(request:PersistentDispatch,authorization:str|None=Header(default=None)):return authenticate(authorization).dispatch(request)
    @router.post('/end')
    def end(request:Identity,authorization:str|None=Header(default=None)):return authenticate(authorization).end(request)
    return router


class VideoChat:
    """Owns only delivery; native lifecycle establishes tool authority independently."""
    def __init__(self,provider,event_file,save_turn,*,gateway_url=None,gateway_token=None,preflight=None):
        self.provider,self.event_file,self.save_turn=provider,event_file,save_turn
        self.gateway_url=gateway_url or os.environ.get('EASEL_VIDEO_GATEWAY_URL','')
        self.gateway_token=gateway_token or os.environ.get('EASEL_VIDEO_GATEWAY_TOKEN','')
        self.preflight=preflight or require_persistent_gateway
        self.tasks={}

    @staticmethod
    def interrupted_result(service,session):
        view=ConversationService(service).view(session)
        message='本轮对话回复中断；已保存的操作请以实际任务状态为准，不会自动重发。'
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

    async def _deliver(self,session,turn_id,result,event_path,*,background=False):
        service=self.provider();bridge=PersistentWorkToolBridge(service)
        seq=0;chunks=[];done=False;next_result_write=0.0
        def emit(kind,data):
            nonlocal seq
            seq+=1
            with event_path.open('a',encoding='utf-8') as f:f.write(json.dumps({'id':seq,'event':kind,'data':data},ensure_ascii=False)+'\n')
        bridge.delivery(turn_id,'dispatching')
        emit('activity','正在与 Easel 讨论创作；制作进度独立更新')
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(7200,connect=10),trust_env=False,follow_redirects=False) as client:
                async with client.stream('POST',self.gateway_url.rstrip('/')+'/v1/chat/completions',
                    headers={'Authorization':'Bearer '+self.gateway_token,'x-openclaw-session-key':result['payload']['session_key']},
                    json={'model':'openclaw/easel-video','stream':True,'messages':[{'role':'user','content':result['prompt']}]}) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.startswith('data:'):continue
                        raw=line[5:].strip()
                        if raw=='[DONE]':done=True;break
                        value=json.loads(raw)
                        if value.get('error'):raise ValueError('gateway_error')
                        text=((value.get('choices') or [{}])[0].get('delta') or {}).get('content')
                        if text:
                            chunks.append(text);emit('token',text)
                            if background and asyncio.get_running_loop().time()>=next_result_write:
                                bridge.record_result_text(turn_id,''.join(chunks))
                                next_result_write=asyncio.get_running_loop().time()+0.25
            if not done or (background and not ''.join(chunks).strip()):raise ValueError('incomplete_delivery')
            bridge.delivery(turn_id,'unknown',''.join(chunks))
            view=ConversationService(service).view(session)
            self.save_turn('web:'+session,'done',''.join(chunks),{'turn_id':turn_id})
            emit('work_card',view)
            emit('done',{'sessionKey':session})
        except asyncio.CancelledError:
            if background:bridge.record_result_text(turn_id,''.join(chunks),error='已停止本次结果回复；制作记录已保留。')
            bridge.delivery(turn_id,'unknown',''.join(chunks))
            emit('error','已停止回答；作品制作继续。原生运行结束前，本轮保持待核实。')
        except Exception as exc:
            bridge.delivery(turn_id,'unknown',''.join(chunks))
            # Record only the exception class; provider bodies may contain private data.
            logging.getLogger(__name__).warning('Video conversation delivery interrupted (%s)',type(exc).__name__)
            message='本轮对话回复中断；尚未核实任务结果，不会自动重发。'
            try:
                view,message=self.interrupted_result(service,session)
                emit('work_card',view)
                self.save_turn('web:'+session,'done',''.join(chunks),{'turn_id':turn_id,'clean_end':False})
            except Exception:pass
            if background:bridge.record_result_text(turn_id,''.join(chunks),error=message)
            emit('error',message)
        finally:self.tasks.pop(session,None)

    async def process_results_once(self):
        if self.tasks or not self.gateway_url or not self.gateway_token:return False
        service=self.provider()
        with service.store.connection() as conn:
            candidate=conn.execute("SELECT 1 FROM conversation_proposals p JOIN runs r ON r.id=json_extract(p.receipt_json,'$.run_id') JOIN works w ON w.id=r.work_id AND w.active_run_id=r.id JOIN conversation_segments s ON s.id=p.segment_id WHERE s.revoked_at IS NULL AND s.id=(SELECT id FROM conversation_segments WHERE ui_session=s.ui_session AND revoked_at IS NULL ORDER BY created_at DESC LIMIT 1) AND p.state='applied' AND json_type(p.receipt_json,'$._result_delivery')='object' AND r.state IN ('succeeded','needs_decision','failed','paused','cancelled') AND EXISTS(SELECT 1 FROM events e WHERE e.work_id=r.work_id AND e.run_id=r.id AND e.seq>json_extract(p.receipt_json,'$._result_delivery.seen_seq') AND e.kind IN ('run_completed','decision_required','task_needs_decision','task_failed','run_cancelled')) LIMIT 1").fetchone()
            reserved=conn.execute("SELECT 1 FROM conversation_turns WHERE state='reserved' AND json_extract(payload_json,'$.origin')='task_result' LIMIT 1").fetchone()
        if not candidate and not reserved:return False
        await asyncio.to_thread(self.preflight,self.gateway_url,self.gateway_token)
        from easel.conversation_results import ConversationResults
        result=await asyncio.to_thread(ConversationResults(PersistentWorkToolBridge(service)).reserve_next)
        if not result:return False
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
        return {'stopped':bool(task),'production_cancelled':False}
