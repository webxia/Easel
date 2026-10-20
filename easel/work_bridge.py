"""Opt-in A1 bridge seam. Not mounted by the production Web application.

The caller must supply both an explicitly constructed WorkService and a token.
This in-memory invocation registry is an A1 probe, not A2 crash recovery storage.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import threading
from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import urlsplit

import httpx

from fastapi import APIRouter, Header
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .production.errors import ProductionError


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def reject(code, status=403):
    raise ProductionError(code, '作品工具请求未通过校验', status_code=status)


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Identity(Strict):
    agent_id: str = Field(min_length=1, max_length=128)
    session_key: str = Field(min_length=1, max_length=256)
    session_id: str = Field(min_length=1, max_length=128)
    run_id: str = Field(min_length=1, max_length=128)


class Claim(Identity):
    prompt: str = Field(max_length=200000)


class Call(Identity):
    tool_call_id: str = Field(min_length=1, max_length=256)
    tool: Literal['easel_work_context', 'easel_work_create_draft', 'easel_work_request_plan']
    params: dict


class Dispatch(Call):
    ticket: str = Field(min_length=24, max_length=128)


class ContextArgs(Strict):
    pass


class DraftArgs(Strict):
    title: str = Field(min_length=1, max_length=200)
    input_text: str = Field(min_length=1, max_length=100000)


class PlanArgs(Strict):
    request: str = Field(min_length=1, max_length=100000)


ARGUMENTS = {'easel_work_context': ContextArgs, 'easel_work_create_draft': DraftArgs,
             'easel_work_request_plan': PlanArgs}


@dataclass
class Invocation:
    ui_session: str
    turn_id: str
    session_key: str
    session_id: str | None
    prompt_hash: str
    allow: frozenset[str]
    work_id: str | None = None
    revision: int | None = None
    run_id: str | None = None
    state: str = 'reserved'
    context: dict = field(default_factory=dict)
    results: dict = field(default_factory=dict)


class WorkToolBridge:
    """Model-free identity/command adapter, using existing WorkService receipts."""
    def __init__(self, service):
        self.service = service
        self.invocations = {}
        self.native_sessions = {}
        self.runs = {}
        self.tickets = {}
        self.turns = {}
        self.lock = threading.RLock()
        self.audit = []

    def reserve(self, *, ui_session, turn_id, session_key, session_id, prompt, work_id=None,
                allow=frozenset(), context=None):
        """Host-only seam; never exposed as a plugin/model HTTP endpoint."""
        request = canonical([ui_session, session_key, session_id, prompt, work_id, sorted(allow), context or {}])
        fingerprint = hashlib.sha256(request.encode()).hexdigest()
        with self.lock:
            if turn_id in self.turns:
                old, prior = self.turns[turn_id]
                if fingerprint != prior:
                    reject('turn_conflict', 409)
                return old
            if not session_key.startswith('agent:easel-video:'):
                reject('agent_mismatch')
            old = self.invocations.get(session_key)
            if old and old.state != 'ended':
                reject('invocation_pending', 409)
            session_id = session_id or self.native_sessions.get(session_key)
            revision = self.service.snapshot(work_id)['revision'] if work_id else None
            inv = Invocation(ui_session, turn_id, session_key, session_id,
                             hashlib.sha256(prompt.encode()).hexdigest(), frozenset(allow),
                             work_id, revision, context=context or {})
            self.invocations[session_key] = inv
            self.turns[turn_id] = (inv, fingerprint)
            return inv

    def _current(self, identity, *, active=True):
        inv = self.runs.get(identity.run_id)
        if (identity.agent_id != 'easel-video' or not inv
                or inv.session_key != identity.session_key or inv.session_id != identity.session_id
                or self.invocations.get(identity.session_key) is not inv
                or (active and inv.state != 'active')):
            reject('binding_mismatch')
        return inv

    def claim(self, request):
        with self.lock:
            inv = self.invocations.get(request.session_key)
            if (request.agent_id != 'easel-video' or not inv or inv.state not in {'reserved', 'active'}
                    or (inv.session_id is not None and inv.session_id != request.session_id)
                    or inv.prompt_hash != hashlib.sha256(request.prompt.encode()).hexdigest()
                    or (inv.run_id and inv.run_id != request.run_id)
                    or (request.run_id in self.runs and self.runs[request.run_id] is not inv)):
                reject('binding_mismatch')
            inv.session_id = request.session_id
            self.native_sessions[request.session_key] = request.session_id
            inv.run_id, inv.state = request.run_id, 'active'
            self.runs[request.run_id] = inv
            self.audit.append({'event': 'claim', 'turn_id': inv.turn_id, 'run_id': request.run_id,
                               'session_key': request.session_key})
            return {'bound': True}

    @staticmethod
    def _arguments(request):
        try:
            return ARGUMENTS[request.tool].model_validate(request.params)
        except ValidationError:
            reject('invalid_tool_arguments', 400)

    def prepare(self, request):
        with self.lock:
            inv = self._current(request)
            self._arguments(request)
            if request.tool not in inv.allow and request.tool != 'easel_work_context':
                reject('intent_not_authorized')
            ticket = secrets.token_urlsafe(32)
            self.tickets[ticket] = (inv, canonical(request.model_dump()))
            self.audit.append({'event': 'prepare', 'turn_id': inv.turn_id, 'run_id': request.run_id,
                               'tool_call_id': request.tool_call_id, 'tool': request.tool})
            return {'ticket': ticket}

    def dispatch(self, request):
        with self.lock:
            inv = self._current(request)
            recorded = self.tickets.get(request.ticket)
            actual = canonical(request.model_dump(exclude={'ticket'}))
            if not recorded or recorded[0] is not inv or recorded[1] != actual:
                reject('ticket_mismatch')
            args = self._arguments(request).model_dump()
            if request.tool not in inv.allow and request.tool != 'easel_work_context':
                reject('intent_not_authorized')
            if request.tool == 'easel_work_context':
                snapshot = self.service.snapshot(inv.work_id) if inv.work_id else None
                return {'context': inv.context, 'work': None if not snapshot else {
                    k: snapshot[k] for k in ('id', 'revision', 'state', 'current_plan_revision')
                }}
            fingerprint = hashlib.sha256(canonical([request.tool, args]).encode()).hexdigest()
            if fingerprint in inv.results:
                return inv.results[fingerprint]
            command_id = 'chat_' + hashlib.sha256((inv.turn_id + fingerprint).encode()).hexdigest()[:48]
            if request.tool == 'easel_work_create_draft':
                if inv.work_id:
                    reject('work_already_bound', 409)
                result = self.service.command('create', {**args, 'session_id': inv.ui_session}, command_id=command_id)
                inv.work_id = result['work_id']
            else:
                if not inv.work_id:
                    reject('work_not_bound', 409)
                result = self.service.command('plan', args, command_id=command_id,
                                              work_id=inv.work_id, expected_revision=inv.revision)
            inv.revision = result['revision']
            inv.results[fingerprint] = result
            self.audit.append({'event': 'command', 'turn_id': inv.turn_id, 'run_id': request.run_id,
                               'tool': request.tool, 'command_id': command_id, 'work_id': inv.work_id})
            return result

    def end(self, request):
        with self.lock:
            inv = self._current(request, active=False)
            inv.state = 'ended'
            self.audit.append({'event': 'end', 'turn_id': inv.turn_id, 'run_id': request.run_id})
            return {'ended': True}


def create_work_tool_router(bridge, token):
    """Explicit mount only. Host reserves invocations via Python, never via this API."""
    if len(token) < 24:
        raise ValueError('bridge credential too short')
    router = APIRouter(prefix='/api/chat/work-tools')

    def authenticate(authorization):
        if not secrets.compare_digest(authorization or '', 'Bearer ' + token):
            reject('bridge_unauthorized', 401)

    @router.post('/claim')
    def claim(request: Claim, authorization: str | None = Header(default=None)):
        authenticate(authorization)
        return bridge.claim(request)

    @router.post('/prepare')
    def prepare(request: Call, authorization: str | None = Header(default=None)):
        authenticate(authorization)
        return bridge.prepare(request)

    @router.post('/dispatch')
    def dispatch(request: Dispatch, authorization: str | None = Header(default=None)):
        authenticate(authorization)
        return bridge.dispatch(request)

    @router.post('/end')
    def end(request: Identity, authorization: str | None = Header(default=None)):
        authenticate(authorization)
        return bridge.end(request)

    return router


def require_gateway_bridge(base_url, gateway_token, *, expected_tools=None, protocol=1, agent_id='easel-video', permission_policy=None):
    """Read active plugin readiness before dispatch; never fall back to main."""
    url = urlsplit(base_url)
    if (url.scheme != 'http' or url.hostname != '127.0.0.1' or not url.port
            or url.path not in {'', '/'} or url.query or url.fragment or url.username or url.password):
        reject('gateway_endpoint_invalid')
    try:
        response = httpx.get(base_url.rstrip('/') + '/plugins/easel-work/status',
                             headers={'Authorization': 'Bearer ' + gateway_token},
                             timeout=5, follow_redirects=False, trust_env=False)
        response.raise_for_status()
        ready = response.json()
        if (ready.get('protocol') != protocol or ready.get('agent_id') != agent_id
                or (permission_policy is not None and ready.get('permission_policy') != permission_policy)
                or set(ready.get('tools', [])) != (set(ARGUMENTS) if expected_tools is None else expected_tools)):
            reject('gateway_bridge_incompatible', 503)
    except (httpx.HTTPError, ValueError, TypeError):
        reject('gateway_bridge_unavailable', 503)
    return ready
