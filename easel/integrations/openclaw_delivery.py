"""Persist and observe OpenClaw gateway calls belonging to a Creation delivery.

The installed gateway's agent.idempotencyKey is its runId; agent.wait observes
that exact run. A transport timeout never authorizes another submission.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import uuid
from typing import Any, Callable, Sequence

from easel import creation
from easel.creation_delivery import DeliveryExecutionUncertain, DeliveryReportError, active_delivery, reserve_delivery_call


class DeliveryAgentPending(DeliveryExecutionUncertain):
    """The same gateway run still needs observation, not another model call."""


class DeliveryAgentRejected(RuntimeError):
    """Gateway explicitly rejected the request before accepting execution."""


def _rpc(prefix: Sequence[str], profile: str, method: str, params: dict,
         runner: Callable, kwargs: dict) -> dict:
    command = [*prefix, "--profile", profile, "gateway", "call", method,
               "--params", json.dumps(params, ensure_ascii=False, separators=(",", ":")),
               "--timeout", "15000", "--json"]
    try:
        result = runner(command, **{**kwargs, "timeout": 20, "capture_output": True, "text": True})
        payload = json.loads(result.stdout)
        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        if (isinstance(payload, dict) and payload.get("ok") is False and isinstance(error, dict)
                and error.get("type") == "gateway_request_error"
                and error.get("code") == "INVALID_REQUEST"):
            detail = str(error.get("message", ""))
            reason = ("当前模型不接受图片输入" if "active model does not accept image inputs" in detail
                      else "当前网关不允许单次切换模型" if "provider/model overrides are not authorized" in detail
                      else "请求不符合网关合同")
            raise DeliveryAgentRejected(f"编排网关明确拒绝请求，任务未启动：{reason}；请修正后重试")
        if result.returncode:
            raise DeliveryExecutionUncertain("暂时无法核实编排网关的执行结果")
    except (subprocess.TimeoutExpired, OSError, ValueError) as exc:
        raise DeliveryExecutionUncertain("编排网关状态连接中断；保留同一运行身份") from exc
    if not isinstance(payload, dict):
        raise DeliveryExecutionUncertain("编排网关返回的执行记录无效")
    return payload


def _visual_model(prefix, profile, agent_id, runner, kwargs):
    catalog = _rpc(prefix, profile, "models.list", {"agentId": agent_id, "includeDetails": True}, runner, kwargs)
    defaults = [m for m in catalog.get("models", []) if "default" in m.get("tags", [])]
    if len(defaults) != 1 or "image" not in defaults[0].get("input", []) or defaults[0].get("available") is not True:
        raise DeliveryAgentRejected("当前创作模型未具备可用的图片输入能力，素材核对尚未启动；请修正模型配置后重试")
    model = defaults[0]
    return {"provider": model["provider"], "model": model["id"]}


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
            if call.get('capture_reply'):
                from easel.integrations.hypit.secrets import SecretRedactor
                reply = payload.get('terminalReply')
                text = reply.get('text') if isinstance(reply, dict) and reply.get('disposition') == 'visible' else None
                valid = (status == 'ok' and payload.get('stopReason') != 'length'
                         and isinstance(text, str) and bool(text.strip())
                         and len(text.encode('utf-16-le')) // 2 <= 3000
                         and not text.rstrip().endswith('…'))
                if valid and SecretRedactor.redact_text(text) == text:
                    digest = hashlib.sha256(text.encode()).hexdigest()
                    previous = call.get('terminal_reply')
                    if previous is not None and previous != {'sha256': digest, 'text': text}:
                        raise DeliveryExecutionUncertain('同一运行的终态结果发生变化，不能覆盖已保存证据')
                    call['terminal_reply'] = {'sha256': digest, 'text': text}
                else:
                    call['reply_failure_kind'] = (
                        'output_incomplete' if payload.get('stopReason') == 'length'
                        or isinstance(text, str) and text.rstrip().endswith('…') else
                        'output_missing' if not isinstance(text, str) or not text.strip() else
                        'output_capacity' if len(text.encode('utf-16-le')) // 2 > 3000 else
                        'sensitive_output'
                    )
                    call['reply_error'] = '运行结果缺失、截断、超出协议容量或包含敏感内容；保留原运行，不重新派发'
            if call.get("session_key") and call.get("runtime_release") != "released":
                call["runtime_release"] = "pending"
            if status == "error":
                # Persist only an allowlisted category, never raw gateway/model
                # output (which can contain prompts, paths or credentials).
                detail = json.dumps(payload, ensure_ascii=False).lower()
                call["failure_reason"] = (
                    "编排网关的临时工具环境已达上限，需释放已完成会话后重试"
                    if "live runtime limit" in detail else
                    "编排网关已确认本次执行失败；保留输入并按阶段恢复"
                )
        elif status in {"accepted", "pending", "timeout"} or payload.get("yielded"):
            call.update(status="pending", observed_at=creation._now())
        else:
            raise DeliveryExecutionUncertain("编排网关尚未提供可核实的执行终态")


def _release_call_runtime(creation_id: str, key: str, *, command_prefix: Sequence[str],
                          profile: str, runner: Callable, kwargs: dict) -> None:
    """Retire a finished delivery session's MCP runtime, retaining its history.

    OpenClaw 2026.9.4 sessions.abort(clearQueued=true) awaits session-stop MCP
    retirement even with no active run. Run-scoped abort does not retire it.
    Only delivery-owned keys with a timestamped terminal run reach this RPC;
    transport failure/yield/pending must never stop a possibly live executor.
    """
    call = creation.get_creation(creation_id)["delivery"]["agent_calls"][key]
    if call.get("runtime_release") != "pending":
        return
    if (call["status"] not in {"ok", "error"} or not call.get("ended_at")
            or not call.get("session_key") or call["profile"] != profile):
        raise DeliveryExecutionUncertain("临时工具环境清理身份尚未核实")
    try:
        payload = _rpc(command_prefix, profile, "sessions.abort", {
            "key": call["session_key"], "agentId": call["agent_id"], "clearQueued": True,
        }, runner, kwargs)
        # An unexpected active run cannot establish successful terminal-only
        # retirement. Do not mark cleanup complete on a generic RPC response.
        if (payload.get("ok") is not True or payload.get("status") != "no-active-run"
                or payload.get("abortedRunId") is not None):
            raise DeliveryExecutionUncertain("临时工具环境释放尚未核实")
    except (DeliveryExecutionUncertain, DeliveryAgentRejected) as exc:
        raise DeliveryExecutionUncertain("执行已结束，临时工具环境释放尚未核实；正在接续清理") from exc
    with creation.edit_creation(creation_id) as work:
        current = work["delivery"]["agent_calls"][key]
        if current["run_id"] != call["run_id"]:
            raise DeliveryExecutionUncertain("临时工具环境清理对应的运行已变化")
        current.update(runtime_release="released", runtime_released_at=creation._now())


def reconcile_agent_calls(creation_id: str, *, command_prefix: Sequence[str], profile: str,
                          runner: Callable = subprocess.run, **kwargs) -> None:
    calls = creation.get_creation(creation_id)["delivery"].get("agent_calls", {})
    for key, call in calls.items():
        if (call["status"] not in {"submitting", "pending"}
                and call.get("runtime_release") != "pending"):
            continue
        if call["profile"] != profile:
            raise DeliveryExecutionUncertain("编排网关配置已变化，不能用另一网关认领执行结果")
        if call["status"] in {"submitting", "pending"}:
            payload = _rpc(command_prefix, profile, "agent.wait", {"runId": call["run_id"], "timeoutMs": 0},
                           runner, kwargs)
            _observe_payload(creation_id, key, payload)
        _release_call_runtime(creation_id, key, command_prefix=command_prefix, profile=profile,
                              runner=runner, kwargs=kwargs)


def run_delivery_agent(command: Sequence[str], *, runner: Callable = subprocess.run,
                       attachments: list[dict] | None = None, capture_reply: bool = False, **kwargs):
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
    digest = hashlib.sha256(json.dumps({"profile": profile, **request,
                                      **({'reply_contract': 'material-result-v1'} if capture_reply else {})}, sort_keys=True,
                                      ensure_ascii=False).encode()).hexdigest()
    submit = False
    existing = creation.get_creation(creation_id)["delivery"].get("agent_calls", {}).get(digest)
    if existing and existing.get("runtime_release") == "pending":
        _release_call_runtime(creation_id, digest, command_prefix=prefix, profile=profile,
                              runner=runner, kwargs=kwargs)
    visual_model = None
    if attachments and (existing is None or (existing.get("status") == "error" and existing.get("failure_observed"))):
        visual_model = _visual_model(prefix, profile, request["agentId"], runner, kwargs)
    with creation.edit_creation(creation_id) as work:
        calls = work["delivery"].setdefault("agent_calls", {})
        call = calls.get(digest)
        if call is None or (call.get("status") == "error" and call.get("failure_observed")):
            if any(c.get("status") in {"submitting", "pending"}
                   for c in calls.values()):
                raise DeliveryExecutionUncertain("已有未知提交，先核对原执行，不派发不同请求")
            # Freeze the cumulative reservation before the possibly uncertain RPC.
            # Terminal histories remain available when a digest is retried.
            history = ([*call.get("history", []), {k: v for k, v in call.items() if k != "history"}]
                       if call else [])
            session = request.get("sessionKey") or ""
            category = ("report_repair" if "上次报告" in request["message"] or "报告局部合同修复" in request["message"] else
                        "supplement" if re.search(r'"observation_round"\s*:\s*[23]', request["message"]) else "initial")
            frame_count = 1
            if "quality-" in session:
                match = re.search(r'"frame_total"\s*:\s*(\d+)', request["message"])
                frame_count = int(match[1]) if match else 1
            stage_override = ('quality' if 'quality-' in session else 'material' if 'visual-' in session or 'material-recovery' in session
                              else 'author' if request['agentId'].startswith('easel-author-') else None)
            stage, ordinal = reserve_delivery_call(work, category=category, frame_count=frame_count, stage_override=stage_override)
            call = {"run_id": "easel-" + uuid.uuid4().hex, "request_sha256": digest,
                    "profile": profile, "status": "submitting", "created_at": creation._now()}
            if capture_reply:
                call['capture_reply'] = True
            if request["sessionKey"]:
                call.update(session_key=request["sessionKey"], agent_id=request["agentId"])
            call.update(stage=stage, stage_ordinal=ordinal, category=category, history=history)
            calls[digest] = call
            if visual_model:
                call["visual_model"] = visual_model
            submit = True
        elif call["status"] == "error":
            call["failure_observed"] = True
        call = dict(call)
    if submit:
        # Save run identity BEFORE calling the gateway. If the caller dies here,
        # recovery observes this run; it never guesses that submission failed.
        try:
            # Keep the configured session route. CLI operators cannot override
            # provider/model per run; the gateway checks the effective model too.
            payload = _rpc(prefix, profile, "agent", {**request,
                           "idempotencyKey": call["run_id"]}, runner, kwargs)
        except DeliveryAgentRejected:
            with creation.edit_creation(creation_id) as work:
                work["delivery"]["agent_calls"][digest].update(
                    status="error", failure_observed=True, rejected_before_start=True,
                    observed_at=creation._now())
            raise
        _observe_payload(creation_id, digest, payload)
    else:
        if call["status"] == "ok":
            if not capture_reply:
                return subprocess.CompletedProcess(args, 0, "", "")
            if call.get('terminal_reply') or call.get('reply_error'):
                return _completed_reply(args, call)
            payload = _rpc(prefix, profile, 'agent.wait', {'runId': call['run_id'], 'timeoutMs': 0}, runner, kwargs)
            _observe_payload(creation_id, digest, payload)
            current = creation.get_creation(creation_id)['delivery']['agent_calls'][digest]
            return _completed_reply(args, current)
        if call["status"] == "error":
            raise RuntimeError(call.get("failure_reason") or "编排网关已确认本次执行失败；保留输入并按阶段恢复")
        payload = _rpc(prefix, profile, "agent.wait", {"runId": call["run_id"], "timeoutMs": 0}, runner, kwargs)
        _observe_payload(creation_id, digest, payload)
    _release_call_runtime(creation_id, digest, command_prefix=prefix, profile=profile,
                          runner=runner, kwargs=kwargs)
    current = creation.get_creation(creation_id)["delivery"]["agent_calls"][digest]
    if current["status"] == "ok":
        if capture_reply:
            if not current.get('terminal_reply') and not current.get('reply_error'):
                payload = _rpc(prefix, profile, 'agent.wait', {'runId': current['run_id'], 'timeoutMs': 0}, runner, kwargs)
                _observe_payload(creation_id, digest, payload)
                current = creation.get_creation(creation_id)['delivery']['agent_calls'][digest]
            return _completed_reply(args, current)
        return subprocess.CompletedProcess(args, 0, "", "")
    if current["status"] == "error":
        with creation.edit_creation(creation_id) as work:
            work["delivery"]["agent_calls"][digest]["failure_observed"] = True
        raise RuntimeError(current.get("failure_reason") or "编排网关已确认本次执行失败；保留输入并按阶段恢复")
    raise DeliveryAgentPending("编排任务已提交，继续等待同一项执行")


def _completed_reply(args, call):
    reply = call.get('terminal_reply')
    if (call.get('status') != 'ok' or not isinstance(reply, dict)
            or hashlib.sha256(str(reply.get('text', '')).encode()).hexdigest() != reply.get('sha256')):
        raise DeliveryReportError(call.get('reply_error') or '原运行没有可核实的完整结果；不重复派发模型',
                                  failure_kind=call.get('reply_failure_kind', 'report_invalid'))
    return subprocess.CompletedProcess(args, 0, reply['text'], '')
