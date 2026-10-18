"""Opt-in video conversation HTTP adapter; ordinary Easel chat is unchanged."""
from __future__ import annotations
import asyncio
import json
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
        async def run():
            seq=0;chunks=[];done=False
            def emit(kind,data):
                nonlocal seq
                seq+=1
                with event_path.open('a') as f:f.write(json.dumps({'id':seq,'event':kind,'data':data},ensure_ascii=False)+'\n')
            bridge.delivery(req.turnId,'dispatching')
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
                            if text:chunks.append(text);emit('token',text)
                if not done:raise ValueError('incomplete_delivery')
                bridge.delivery(req.turnId,'unknown',''.join(chunks))
                view=ConversationService(service).view(req.sessionId)
                self.save_turn('web:'+req.sessionId,'done',''.join(chunks),{'turn_id':req.turnId})
                emit('work_card',view)
                emit('done',{'sessionKey':req.sessionId})
            except asyncio.CancelledError:
                bridge.delivery(req.turnId,'unknown',''.join(chunks))
                emit('error','已停止回答；作品制作继续。原生运行结束前，本轮保持待核实。')
            except Exception:
                bridge.delivery(req.turnId,'unknown',''.join(chunks))
                try:
                    ConversationService(service).view(req.sessionId)
                    self.save_turn('web:'+req.sessionId,'done',''.join(chunks),{'turn_id':req.turnId,'clean_end':False})
                except Exception:pass
                emit('error','作品对话未完整返回，请核实本轮结果；不会自动重发或切换普通助手。')
            finally:self.tasks.pop(req.sessionId,None)
        self.tasks[req.sessionId]=asyncio.create_task(run())
        return await replay(req.turnId,0)

    def stop(self,session):
        task=self.tasks.get(session)
        if task:task.cancel()
        return {'stopped':bool(task),'production_cancelled':False}
