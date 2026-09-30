"""Persist and observe OpenClaw gateway calls belonging to a Creation delivery.

The installed gateway's agent.idempotencyKey is its runId; agent.wait observes
that exact run. A transport timeout never authorizes another submission.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import uuid
from typing import Any, Callable, Sequence

from easel import creation
from easel.creation_delivery import DeliveryExecutionUncertain, active_delivery


class DeliveryAgentPending(DeliveryExecutionUncertain):
    """The same gateway run still needs observation, not another model call."""


def _rpc(prefix: Sequence[str], profile: str, method: str, params: dict,
         runner: Callable, kwargs: dict) -> dict:
    command = [*prefix, "--profile", profile, "gateway", "call", method,
               "--params", json.dumps(params, ensure_ascii=False, separators=(",", ":")),
               "--timeout", "15000", "--json"]
    try:
        result = runner(command, **{**kwargs, "timeout": 20, "capture_output": True, "text": True})
        if result.returncode:
            raise DeliveryExecutionUncertain("暂时无法核实编排网关的执行结果")
        payload = json.loads(result.stdout)
    except (subprocess.TimeoutExpired, OSError, ValueError) as exc:
        raise DeliveryExecutionUncertain("编排网关状态连接中断；保留同一运行身份") from exc
    if not isinstance(payload, dict):
        raise DeliveryExecutionUncertain("编排网关返回的执行记录无效")
    return payload


def _observe_payload(creation_id: str, key: str, payload: dict) -> None:
    with creation.edit_creation(creation_id) as work:
        call = work["delivery"]["agent_calls"][key]
        if payload.get("runId") != call["run_id"]:
            raise DeliveryExecutionUncertain("编排网关返回了另一项执行的状态")
        status = payload.get("status")
        # Only a terminal, timestamped run establishes that its file writes
        # stopped. timeout/pending/yield are not terminal failures.
        ended = payload.get("endedAt")
        if (status in {"ok", "error"} and type(ended) in (int, float) and ended > 0
                and not payload.get("yielded")):
            call.update(status=status, ended_at=ended, observed_at=creation._now())
        elif status in {"accepted", "pending", "timeout"} or payload.get("yielded"):
            call.update(status="pending", observed_at=creation._now())
        else:
            raise DeliveryExecutionUncertain("编排网关尚未提供可核实的执行终态")


def reconcile_agent_calls(creation_id: str, *, command_prefix: Sequence[str], profile: str,
                          runner: Callable = subprocess.run, **kwargs) -> None:
    calls = creation.get_creation(creation_id)["delivery"].get("agent_calls", {})
    for key, call in calls.items():
        if call["status"] not in {"submitting", "pending"}:
            continue
        if call["profile"] != profile:
            raise DeliveryExecutionUncertain("编排网关配置已变化，不能用另一网关认领执行结果")
        payload = _rpc(command_prefix, profile, "agent.wait", {"runId": call["run_id"], "timeoutMs": 0},
                       runner, kwargs)
        _observe_payload(creation_id, key, payload)


def run_delivery_agent(command: Sequence[str], *, runner: Callable = subprocess.run,
                       attachments: list[dict] | None = None, **kwargs):
    """Replacement for an agent CLI call, retaining the existing file executor."""
    creation_id = active_delivery.get()
    if not creation_id:
        if attachments:
            raise ValueError("视觉观察必须属于已确认的持续交付委托")
        return runner(command, **kwargs)
    args = list(command)
    if "--message" not in args or "--agent" not in args:
        return runner(command, **kwargs)
    def flag(name: str, default=None):
        return args[args.index(name) + 1] if name in args else default

    profile = flag("--profile")
    if not profile:
        raise ValueError("持续交付的编排调用必须绑定网关配置")
    prefix = args[:args.index("--profile")]
    request = {"message": flag("--message"), "agentId": flag("--agent"),
               "sessionKey": flag("--session-key"), "thinking": flag("--thinking", "high"),
               "timeout": int(flag("--timeout", "600")), "deliver": False}
    if attachments:
        # Installed AgentParamsSchema + normalizeRpcAttachmentsToChatAttachments:
        # type/mimeType/fileName/content(base64), not paths or remote URLs.
        request["attachments"] = attachments
    if attachments and len(json.dumps(request, ensure_ascii=False).encode()) > 110_000:
        raise ValueError("编排输入超过本地网关传输上限，未提交执行")
    if flag("--session-id"):
        request["sessionId"] = flag("--session-id")
    digest = hashlib.sha256(json.dumps({"profile": profile, **request}, sort_keys=True,
                                      ensure_ascii=False).encode()).hexdigest()
    submit = False
    with creation.edit_creation(creation_id) as work:
        calls = work["delivery"].setdefault("agent_calls", {})
        call = calls.get(digest)
        if call is None or (call.get("status") == "error" and call.get("failure_observed")):
            call = {"run_id": "easel-" + uuid.uuid4().hex, "request_sha256": digest,
                    "profile": profile, "status": "submitting", "created_at": creation._now()}
            calls[digest] = call
            submit = True
        elif call["status"] == "error":
            call["failure_observed"] = True
        call = dict(call)
    if submit:
        # Save run identity BEFORE calling the gateway. If the caller dies here,
        # recovery observes this run; it never guesses that submission failed.
        payload = _rpc(prefix, profile, "agent", {**request, "idempotencyKey": call["run_id"]}, runner, kwargs)
        _observe_payload(creation_id, digest, payload)
    else:
        if call["status"] == "ok":
            return subprocess.CompletedProcess(args, 0, "", "")
        if call["status"] == "error":
            raise RuntimeError("编排网关已确认本次执行失败；保留输入并按阶段恢复")
        payload = _rpc(prefix, profile, "agent.wait", {"runId": call["run_id"], "timeoutMs": 0}, runner, kwargs)
        _observe_payload(creation_id, digest, payload)
    current = creation.get_creation(creation_id)["delivery"]["agent_calls"][digest]
    if current["status"] == "ok":
        return subprocess.CompletedProcess(args, 0, "", "")
    if current["status"] == "error":
        with creation.edit_creation(creation_id) as work:
            work["delivery"]["agent_calls"][digest]["failure_observed"] = True
        raise RuntimeError("编排网关已确认本次执行失败；保留输入并按阶段恢复")
    raise DeliveryAgentPending("编排任务已提交，继续等待同一项执行")
