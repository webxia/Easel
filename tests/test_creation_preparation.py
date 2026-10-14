from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import sys
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "web"))

from easel import chat_capability, creation, creation_preparation as prep  # noqa: E402
from easel.integrations.hypit import handoff, service  # noqa: E402
from easel.integrations.hypit.errors import HypitIntegrationError  # noqa: E402
from easel.materials.domain import (
    MaterialNeed, MaterialPlan, MediaType, NeedImportance, NeedIntent,
    NeedScope, NeedScopeType,
)
import app as web  # noqa: E402
# Bind native implementation before tests monkeypatch the Web adapter.
_NATIVE_VNEXT_PLANNING_OWNER = web._material_planning_executor


VIDEO_PROPOSAL = """## 创作表达
从日常选择的变化切入，不把结论当成普遍规律。不露脸。
## 文案
```text
先看问题，再做决定。
```
## 分镜与节奏
0–15 秒：桌面两张白纸，呈现后期叠加的屏幕文案「先看问题，再做决定。」。
## 声音设计
无旁白，无音乐。
## 制作规格
时长：15 秒
画幅：9:16
音轨：静音
语言：简体中文
"""


def _confirm_current_video_plan(work: dict, turn_id: str = 'fixture-confirmation',
                                proposal: str = VIDEO_PROPOSAL) -> dict:
    """Create a lawful @4 commission through the public Creation domain.

    No manually seeded delivery/authorization/pins and no external model call.
    """
    creation.begin_video_proposal(work['id'], turn_id)
    planned = creation.save_video_proposal(work['id'], turn_id, proposal)
    plan = planned['chat_workflow']['video_plan']
    assert plan['schema'] == 'easel-video-proposal@4'
    declaration = creation.input_use_preview(plan=plan)
    transcript = json.dumps([{'role': 'assistant', 'content': proposal}],
                            ensure_ascii=False, separators=(',', ':'))
    return creation.confirm_chat_proposal(
        work['id'], turn_id,
        delivery_proposal=transcript,
        proposal_sha256=hashlib.sha256(transcript.encode()).hexdigest(),
        video_plan_sha256=plan['sha256'],
        production_specs=plan['specs'],
        input_use_statement_sha256=declaration['statement_sha256'])


def _confirmed_delivery():
    work = creation.create_creation("隔离测试主题", creative_mode="clear_memo_video", route="hypit_video",
                                    origin={"type": "chat", "session_hash": "c" * 64})
    return _confirm_current_video_plan(work, turn_id='confirm')




def test_delivery_excludes_legacy_and_serializes_cancellation_and_restarts(prep_env):
    from easel.creation_delivery import advance_creation, enrolled_creation_ids

    legacy = creation.create_creation("历史只读测试作品", creative_mode="clear_memo_video",
                                      route="hypit_video")
    before = creation._creation_path(legacy["id"]).read_bytes()
    work = _confirmed_delivery()
    assert set(enrolled_creation_ids()) == {prep_env["work"]["id"], work["id"]}
    assert legacy["id"] not in enrolled_creation_ids()
    calls = []

    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()

        async def execute(operation, current):
            calls.append(operation)
            entered.set()
            await release.wait()
            with creation.edit_creation(current["id"]) as value:
                value["preparation"] = {"status": "MATERIAL_NOT_READY"}
                value["hypit_attempts"] = [{"attempt_id": "fa_" + "a" * 32,
                                            "material_gate": {"status": "MATERIAL_NOT_READY"}}]

        owner = asyncio.create_task(advance_creation(work["id"], execute))
        await entered.wait()
        assert await advance_creation(work["id"], execute) is False
        probe = subprocess.run([sys.executable, "-c",
            "import fcntl,sys\nf=open(sys.argv[1], 'a+b')\n"
            "try: fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)\n"
            "except BlockingIOError: sys.exit(77)\n",
            str(creation._creation_dir(work["id"]) / "delivery.lock")], check=False)
        assert probe.returncode == 77
        owner.cancel()
        await asyncio.sleep(0)
        # Cancellation/shutdown cannot release ownership while execution lives.
        assert not owner.done()
        assert await advance_creation(work["id"], execute) is False
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await owner

    asyncio.run(scenario())

    async def forbidden(*_):
        pytest.fail("checkpoint/legacy must not be dispatched")

    assert asyncio.run(advance_creation(work["id"], forbidden)) is False
    assert asyncio.run(advance_creation(legacy["id"], forbidden)) is False
    assert creation._creation_path(legacy["id"]).read_bytes() == before
    assert calls == ["prepare"]
    # Replayed old confirmations never opt a legacy work into delivery.
    with pytest.raises(creation.CreationError, match="不是聊天创建"):
        creation.confirm_chat_proposal(legacy["id"], "retry", delivery_proposal="ignored")
    assert "delivery" not in creation.get_creation(legacy["id"])
    # New authorization cannot be retrofitted by replaying either an old
    # confirmation or a managed commission that omitted the declaration.
    # A mismatched declaration cannot retroactively mutate this new commission.
    current = creation.get_creation(work['id'])
    original = creation._creation_path(current['id']).read_bytes()
    with pytest.raises(creation.CreationError, match='不能通过重放'):
        creation.confirm_chat_proposal(current['id'], 'add-input-rights',
            delivery_proposal=current['delivery']['proposal'],
            input_use_statement_sha256='0' * 64)
    assert creation._creation_path(current['id']).read_bytes() == original


@pytest.mark.parametrize('drain_ready', [False, True])
def test_delivery_replay_uses_checkpoints_and_reconciles_uncertain_submission(prep_env, monkeypatch, drain_ready):
    from itertools import count
    from easel import creation_delivery
    from easel.integrations import quality_results, result_protocols
    from easel.creation_delivery import advance_creation, next_operation, DeliveryExecutionUncertain, _advance_ready_creation

    # This test owns the Delivery scheduling / uncertain-submission state machine.
    # It has no real MP4 or native Quality receipt; test_native_quality_owner
    # separately verifies those originals. Do not reinstate legacy empty pins.
    monkeypatch.setattr(quality_results, 'verify_current_review', lambda _attempt: None)

    clock = count(0, .25)
    monkeypatch.setattr(creation_delivery, 'monotonic', lambda: next(clock))

    work = _confirmed_delivery()
    calls = []

    async def execute(operation, current):
        calls.append(operation)
        if operation == "observe_material" and calls.count("observe_material") == 1:
            raise DeliveryExecutionUncertain("素材观察已提交，等待同一执行")
        if operation == "author" and calls.count("author") == 1:
            raise RuntimeError("临时编排失败")
        if operation == "refresh" and calls.count("refresh") == 1:
            raise OSError("暂时无法读取状态")
        with creation.edit_creation(current["id"]) as value:
            if operation == "prepare":
                value["hypit_attempts"] = [{"attempt_id": "fa_" + "b" * 32,
                    "creation_id": current["id"],
                    "result_protocols": result_protocols.current(),
                    "execution_status": "NOT_SUBMITTED", "authoring_status": "READY_FOR_EXTERNAL_AUTHORING",
                    "material_planning": {'truth_review_status': 'PASSED'},
                    "material_gate": {"status": "MATERIAL_NOT_READY", "plan_revision": "p1", "bundle_revision": "b1"}}]
                return
            attempt = value["hypit_attempts"][-1]
            if operation == "observe_material":
                attempt["material_observation"] = {"status": "COMPLETE", "plan_revision": "p1",
                                                   "bundle_revision": attempt['material_gate']['bundle_revision']}
                if attempt.get('autonomous_material_recovery', {}).get('status') == 'COMPLETE':
                    attempt['material_gate']['status'] = 'MATERIAL_READY'
            elif operation == 'recover_material':
                attempt['autonomous_material_recovery'] = {'status': 'COMPLETE'}
                attempt['material_gate']['bundle_revision'] = 'b2'
            elif operation == "author":
                attempt["authoring_status"] = "AUTHORING_READY"
            elif operation == "runtime":
                attempt["runtime_status"] = "CONFIGURED"
            elif operation == "validate":
                attempt["plan"] = {"status": "ready"}
            elif operation == "price":
                attempt["cost"] = {"status": "pricing_read", "pricing": {
                    "format": "hypit.cli-pricing@1", "requestCount": 2, "noChargeRequestCount": 2, "groups": []}}
            elif operation == "approve_free":
                attempt["cost"]["approved"] = True
            elif operation == "submit":
                attempt["execution_status"] = "SUBMITTING"
                attempt["build"] = {"operation": {"operation_id": "persisted-before-call"}}
            elif operation == "reconcile":
                if calls.count("reconcile") < 2:
                    return  # No match yet is not permission to resubmit.
                attempt.update(execution_status="SUBMITTED", build={"build_id": "fixture-only"})
            elif operation == "refresh":
                attempt["execution_status"] = "BUILD_COMPLETE"
            elif operation == "export":
                attempt["outputs"] = {"final.video": {"sha256": "fixture-only"}}
            elif operation == "quality":
                attempt['review'] = {'system': {'schema': 'easel-output-quality@6', 'status': 'READY',
                    'binding': {'output_name': 'final.video', 'sha256': 'fixture-only'}}}
            else:
                pytest.fail(operation)
        if operation == "submit":
            raise TimeoutError("提交响应丢失")

    # New event loop/dispatcher for every operation models a process restart;
    # no in-memory task registry participates in deciding what runs next.
    bursts = []
    for _ in range(20):
        start = len(calls)
        asyncio.run(_advance_ready_creation(work['id'], asyncio.Event(), execute)
                    if drain_ready else advance_creation(work["id"], execute))
        bursts.append(calls[start:])
        if calls[-1:] == ["refresh"] and calls.count("refresh") == 1:
            saved = creation.get_creation(work["id"])
            assert saved["delivery"]["status"] == "observation_failed"
            assert saved["hypit_attempts"][-1]["execution_status"] == "SUBMITTED"
        if next_operation(creation.get_creation(work["id"])) == (None, "first_cut_ready"):
            break
    assert calls == ["prepare", "observe_material", "observe_material", 'recover_material', 'observe_material', "author", "author", "runtime", "validate", "price", "approve_free",
                     "submit", "reconcile", "reconcile", "refresh", "refresh", "export", "quality"]
    assert creation.get_creation(work["id"])["delivery"]["status"] == "first_cut_ready"
    if drain_ready:
        # Ready stages chain immediately; unknown execution, failed execution,
        # and an unchanged reconciliation each return to the polling clock.
        assert bursts == [
            ['prepare', 'observe_material'],
            ['observe_material', 'recover_material', 'observe_material', 'author'],
            ['author', 'runtime', 'validate', 'price', 'approve_free', 'submit'],
            ['reconcile'], ['reconcile', 'refresh'], ['refresh', 'export', 'quality'],
        ]
        stopped = asyncio.Event()
        stopped.set()
        asyncio.run(_advance_ready_creation(work['id'], stopped, execute))
        assert len(calls) == 18
    snapshot = creation.get_creation(work['id'])
    timings = snapshot['delivery']['operation_timings']
    assert sum(t['calls'] for t in timings.values()) == len(calls)
    assert sum(t['elapsed_seconds'] for t in timings.values()) == len(calls) * .25
    assert timings['preparation:prepare']['last_outcome'] == 'completed'
    attempt_id = snapshot['hypit_attempts'][-1]['attempt_id']
    assert timings[f'{attempt_id}:author']['calls'] == 2
    assert timings[f'{attempt_id}:author']['elapsed_seconds'] == .5
    assert timings[f'{attempt_id}:submit']['last_outcome'] == 'failed'
    system = snapshot['hypit_attempts'][-1]['review']['system']
    system['schema'] = 'easel-output-quality@3'
    assert next_operation(snapshot) == ('quality', 'checking_quality')
    system['schema'] = 'easel-output-quality@6'
    system['visual'] = [{'checks': {'readability': {'status': 'unknown'}}}]
    for state in ('INCOMPLETE', 'REPAIR_REQUIRED'):
        system['status'] = state
        assert next_operation(snapshot) == ('quality', 'checking_quality')
    system['observation_round'] = 3
    for state, status in [('REPAIR_REQUIRED', 'quality_repair_required'), ('INCOMPLETE', 'quality_incomplete')]:
        system['status'] = state
        assert next_operation(snapshot) == (None, status)
    system['status'] = 'READY'
    system['binding']['sha256'] = 'wrong-output'
    assert next_operation(snapshot) == ('quality', 'checking_quality')


def test_delivery_bounds_failures_preserves_authorization_and_validates_commission(prep_env):
    from easel.creation_delivery import advance_creation, retry_delivery

    work = _confirmed_delivery()
    calls = []

    async def failure(*_):
        calls.append(1)
        raise RuntimeError("可恢复的格式错误")

    for _ in range(5):
        asyncio.run(advance_creation(work["id"], failure))
    saved = creation.get_creation(work["id"])
    assert len(calls) == 3 and saved["delivery"]["status"] == "failed"
    retry_delivery(work["id"])
    asyncio.run(advance_creation(work["id"], failure))
    assert len(calls) == 4
    assert creation.get_creation(work["id"])["delivery"]["authorization"] == work["delivery"]["authorization"]
    with creation.edit_creation(work["id"]) as current:
        current["delivery"]["proposal"] = "静默篡改委托"
    tampered_original = creation._creation_path(work["id"]).read_bytes()
    asyncio.run(advance_creation(work["id"], failure))
    assert len(calls) == 4
    # A forged commission is no longer eligible for any Delivery write;
    # do not repair its stored status by mutating evidence on a failed request.
    from easel.creation_delivery import next_operation
    assert next_operation(creation.get_creation(work["id"])) == (None, "unmanaged")
    assert creation._creation_path(work["id"]).read_bytes() == tampered_original
    # A dead caller is insufficient evidence that the independent gateway job
    # stopped. A restart must not silently dispatch a second model request.
    fresh = _confirmed_delivery()
    with creation.edit_creation(fresh["id"]) as current:
        current["delivery"].update(operation="prepare", status="preparing")
    asyncio.run(advance_creation(fresh["id"], failure))
    assert len(calls) == 4
    assert creation.get_creation(fresh["id"])["delivery"]["status"] == "execution_uncertain"
    with pytest.raises(creation.CreationError, match="不能重复派发"):
        retry_delivery(fresh["id"])


def test_delivery_build_recovery_resumes_source_and_rechecks_cost_with_a_bound(prep_env, monkeypatch):
    from easel.creation_delivery import advance_creation, next_operation, MAX_BUILD_RECOVERIES

    from easel.integrations import result_protocols
    work = _confirmed_delivery()
    source_id = "fa_" + "1" * 32
    with creation.edit_creation(work["id"]) as current:
        current["hypit_attempts"] = [{
            "attempt_id": source_id, "creation_id": work["id"],
            "result_protocols": result_protocols.current(),
            "planning_contract_version": 3, "execution_status": "BUILD_FAILED"}]
    calls = []

    def fork_failed(source):
        calls.append(source)
        with creation.edit_creation(work["id"]) as current:
            assert current["delivery"]["recovering_build_from"] == source
            target = next((item for item in current["hypit_attempts"]
                           if item.get("retry_source", {}).get("attempt_id") == source), None)
            if target is None:
                target = {"attempt_id": f"fa_{len(current['hypit_attempts']) + 1:032x}",
                          "creation_id": current["id"],
                          "result_protocols": result_protocols.current(),
                          "planning_contract_version": 3,
                          "execution_status": "NOT_SUBMITTED",
                          "retry_source": {"attempt_id": source, "status": "COPYING"}}
                current["hypit_attempts"].append(target)
            else:
                target.update(retry_source={"attempt_id": source, "status": "READY"},
                              material_gate={"status": "MATERIAL_READY"},
                              authoring_status="AUTHORING_READY", runtime_status="CONFIGURED",
                              plan={"status": "pending"}, cost={"approved": False})
        if calls.count(source) == 1:
            raise RuntimeError("模拟创建目标后复制中断")

    monkeypatch.setattr(web, "retry_failed_film_build", fork_failed)
    for _ in range(MAX_BUILD_RECOVERIES):
        asyncio.run(advance_creation(work["id"], web._execute_creation_delivery))
        assert next_operation(creation.get_creation(work["id"]))[0] == "retry_build"
        asyncio.run(advance_creation(work["id"], web._execute_creation_delivery))
        saved = creation.get_creation(work["id"])
        assert calls[-2:] == [source_id, source_id]
        assert "recovering_build_from" not in saved["delivery"]
        assert next_operation(saved)[0] == "validate"
        # No previous paid approval is inherited. Even a recovered checkpoint
        # waits if its new pricing cannot prove there is no provider charge.
        with creation.edit_creation(work["id"]) as current:
            attempt = current["hypit_attempts"][-1]
            attempt.update(plan={"status": "ready"}, cost={"status": "pricing_read", "approved": False,
                "pricing": {"format": "hypit.cli-pricing@1", "requestCount": 1, "groups": []}})
        assert next_operation(creation.get_creation(work["id"])) == (None, "needs_cost_approval")
        with creation.edit_creation(work["id"]) as current:
            current["hypit_attempts"][-1]["execution_status"] = "BUILD_FAILED"
            source_id = current["hypit_attempts"][-1]["attempt_id"]
    assert next_operation(creation.get_creation(work["id"])) == (None, "production_failed")
    assert asyncio.run(advance_creation(work["id"], web._execute_creation_delivery)) is False
    assert len(calls) == 2 * MAX_BUILD_RECOVERIES


def test_delivery_quality_repair_resumes_one_checkpoint_and_stops_at_budget(prep_env, monkeypatch):
    from easel.creation_delivery import advance_creation, next_operation, MAX_QUALITY_REPAIRS
    from easel.integrations.hypit import service
    from easel.integrations import quality_results, result_protocols
    # This tests Delivery's bounded retry state machine with a synthetic
    # already-reviewed outcome, not its original MP4/receipt integrity.
    # Real native Quality bytes/provenance are covered in test_native_quality_owner.
    # Keep the new protocol pin mandatory; isolate only the upstream proof read.
    monkeypatch.setattr(quality_results, 'verify_current_review', lambda _attempt: None)
    work = _confirmed_delivery()
    def failed_output(identity):
        return {'attempt_id': identity, 'creation_id': work['id'],
                'result_protocols': result_protocols.current(),
                'planning_contract_version': 3, 'execution_status': 'BUILD_COMPLETE',
            'outputs': {'final': {'sha256': 'output-sha'}}, 'review': {'human': {'status': 'pending'}, 'system': {
                'schema': 'easel-output-quality@6', 'status': 'REPAIR_REQUIRED',
                'binding': {'output_name': 'final', 'sha256': 'output-sha'},
                'measurements': {'defects': [{'kind': 'voice_masked', 'reason': '配乐遮盖旁白', 'time_seconds': 2}]}}}}
    source = 'fa_' + '4' * 32
    with creation.edit_creation(work['id']) as current:
        current['hypit_attempts'] = [failed_output(source)]
    calls = []
    def repair(identity):
        calls.append(identity)
        with creation.edit_creation(work['id']) as current:
            assert current['delivery']['recovering_quality_from'] == identity
            target = next((a for a in current['hypit_attempts'] if a.get('retry_source', {}).get('attempt_id') == identity), None)
            if target is None:
                current['hypit_attempts'].append({'attempt_id': f"fa_{len(calls):032x}",
                    'creation_id': current['id'], 'result_protocols': result_protocols.current(),
                    'planning_contract_version': 3,
                    'execution_status': 'NOT_SUBMITTED', 'retry_source': {'attempt_id': identity, 'status': 'COPYING'}})
            else:
                target.update(authoring_status='READY_FOR_EXTERNAL_AUTHORING',
                    material_gate={'status': 'MATERIAL_READY', 'plan_revision': 'p', 'bundle_revision': 'b'},
                    material_observation={'status': 'COMPLETE', 'plan_revision': 'p', 'bundle_revision': 'b'},
                    cost={'approved': False}, retry_source={'attempt_id': identity, 'status': 'READY'})
        if calls.count(identity) == 1:
            raise RuntimeError('模拟复制中断')
    monkeypatch.setattr(service, 'repair_film_quality', repair)
    for _ in range(MAX_QUALITY_REPAIRS):
        asyncio.run(advance_creation(work['id'], web._execute_creation_delivery))
        assert next_operation(creation.get_creation(work['id']))[0] == 'repair_quality'
        asyncio.run(advance_creation(work['id'], web._execute_creation_delivery))
        current = creation.get_creation(work['id'])
        assert calls[-2:] == [source, source]
        assert next_operation(current)[0] == 'author'
        assert current['hypit_attempts'][-1]['cost']['approved'] is False
        source = current['hypit_attempts'][-1]['attempt_id']
        with creation.edit_creation(work['id']) as current:
            current['hypit_attempts'][-1] = failed_output(source)
    assert next_operation(creation.get_creation(work['id'])) == (None, 'quality_repair_required')
    assert len(calls) == 2 * MAX_QUALITY_REPAIRS


def test_gateway_submission_timeout_reconciles_same_run_without_resubmitting(prep_env):
    from easel.creation_delivery import active_delivery, DeliveryExecutionUncertain, next_operation
    from easel.integrations.openclaw_delivery import run_delivery_agent, reconcile_agent_calls

    work = _confirmed_delivery()
    calls = []
    run_id = None
    terminal = False

    def gateway(command, **kwargs):
        nonlocal run_id
        method = command[command.index("call") + 1]
        params = json.loads(command[command.index("--params") + 1])
        calls.append(method)
        if method == "models.list":
            return subprocess.CompletedProcess(command, 0, json.dumps({"models": [
                {"id": "vision", "provider": "fixture", "tags": ["default"], "input": ["text", "image"], "available": True}
            ]}), "")
        if method == "agent":
            assert 'provider' not in params and 'model' not in params
            run_id = params["idempotencyKey"]
            saved = creation.get_creation(work["id"])["delivery"]["agent_calls"]
            assert next(iter(saved.values()))["run_id"] == run_id
            assert params["deliver"] is False
            assert params["attachments"] == attachments
            raise subprocess.TimeoutExpired(command, 20)
        if method == "sessions.abort":
            assert terminal
            assert params == {"key": "fixture-session", "agentId": "main", "clearQueued": True}
            return subprocess.CompletedProcess(command, 0, json.dumps({
                "ok": True, "status": "no-active-run", "abortedRunId": None,
            }), "")
        assert method == "agent.wait" and params == {"runId": run_id, "timeoutMs": 0}
        result = {"runId": run_id, "status": "ok"}
        if terminal:
            result["endedAt"] = 1000
        else:
            # Yield can carry an end timestamp without establishing that the
            # executor has stopped. It must retain its runtime and run identity.
            result.update(endedAt=999, yielded=True)
        return subprocess.CompletedProcess(command, 0, json.dumps(result), "")

    command = ["openclaw", "--profile", "fixture", "agent", "--agent", "main",
               "--session-key", "fixture-session", "--message", "只写隔离准备文件"]
    attachments = [{"type": "image", "mimeType": "image/jpeg", "fileName": "frame-0.jpg", "content": "ZmFrZQ=="}]
    token = active_delivery.set(work["id"])
    try:
        with pytest.raises(DeliveryExecutionUncertain):
            run_delivery_agent(command, runner=gateway, attachments=attachments)
        with creation.edit_creation(work['id']) as current:
            current['delivery']['stopped'] = True
        assert next_operation(creation.get_creation(work['id'])) == ('observe_agent', 'observing_execution')
        with pytest.raises(DeliveryExecutionUncertain, match="另一网关"):
            reconcile_agent_calls(work["id"], command_prefix=["openclaw"], profile="different", runner=gateway)
        with pytest.raises(DeliveryExecutionUncertain, match="另一项执行"):
            reconcile_agent_calls(work["id"], command_prefix=["openclaw"], profile="fixture",
                runner=lambda command, **_: subprocess.CompletedProcess(command, 0,
                    json.dumps({"runId": "unrelated", "status": "ok", "endedAt": 1000}), ""))
        reconcile_agent_calls(work["id"], command_prefix=["openclaw"], profile="fixture", runner=gateway)
        assert next_operation(creation.get_creation(work['id'])) == ('observe_agent', 'observing_execution')
        with pytest.raises(DeliveryExecutionUncertain):
            run_delivery_agent(command, runner=gateway, attachments=attachments)
        terminal = True
        reconcile_agent_calls(work["id"], command_prefix=["openclaw"], profile="fixture", runner=gateway)
        assert next_operation(creation.get_creation(work['id'])) == (None, 'stopped')
        assert run_delivery_agent(command, runner=gateway, attachments=attachments).returncode == 0
        assert calls == ["models.list", "agent", "agent.wait", "agent.wait", "agent.wait", "sessions.abort"]
        stored = next(iter(creation.get_creation(work["id"])["delivery"]["agent_calls"].values()))
        assert stored["status"] == "ok" and "message" not in stored and "attachments" not in stored
        assert stored["runtime_release"] == "released"
    finally:
        active_delivery.reset(token)


@pytest.mark.parametrize('reply_kind', ['complete', 'length', 'capacity', 'other_run', 'missing'])
def test_material_result_is_received_from_same_run_and_reused_without_dispatch(prep_env, monkeypatch, reply_kind):
    from easel.creation_delivery import active_delivery, DeliveryExecutionUncertain, DeliveryReportError, advance_creation
    from easel.integrations.openclaw_delivery import run_delivery_agent
    from easel.integrations import result_protocols
    work = _confirmed_delivery()
    fixture_attempt = {'creation_id': work['id'], 'attempt_id': 'fa_' + 'f' * 32,
                       'result_protocols': result_protocols.current(),
                       'workspace': {'path': str(prep_env['tmp'] / 'report')}}
    methods, run_id = [], None
    result_text = '{"frames":[{"observed":true}]}'

    def gateway(command, **kwargs):
        nonlocal run_id
        method = command[command.index('call') + 1]
        params = json.loads(command[command.index('--params') + 1])
        methods.append(method)
        if method == 'agent':
            run_id = params['idempotencyKey']
            payload = {'runId': run_id, 'status': 'accepted'}
        elif method == 'sessions.abort':
            payload = {'ok': True, 'status': 'no-active-run', 'abortedRunId': None}
        else:
            assert method == 'agent.wait' and params['runId'] == run_id
            payload = {'runId': 'another-run' if reply_kind == 'other_run' else run_id,
                       'status': 'ok', 'endedAt': 1000,
                       'stopReason': 'length' if reply_kind == 'length' else 'stop',
                       'terminalReply': {'disposition': 'visible', 'text':
                           '界' * 3001 if reply_kind == 'capacity' else result_text}}
            if reply_kind == 'missing':
                payload.pop('terminalReply')
        return subprocess.CompletedProcess(command, 0, json.dumps(payload), '')

    command = ['openclaw', '--profile', 'fixture', 'agent', '--agent', 'main',
               '--session-key', 'fixture-material', '--message', '只返回紧凑观察结果']
    token = active_delivery.set(work['id'])
    try:
        with pytest.raises(DeliveryExecutionUncertain):
            run_delivery_agent(command, runner=gateway, capture_reply=True)
        if reply_kind == 'other_run':
            with pytest.raises(DeliveryExecutionUncertain, match='另一项执行'):
                run_delivery_agent(command, runner=gateway, capture_reply=True)
        elif reply_kind == 'missing':
            with pytest.raises(DeliveryReportError) as error:
                run_delivery_agent(command, runner=gateway, capture_reply=True)
            assert error.value.failure_kind == 'report_invalid'  # Missing terminal is not a reparable model output.
            (prep_env['tmp'] / 'report').mkdir()
            monkeypatch.setattr(web, 'run_agent_sync', lambda *a, **k: run_delivery_agent(
                command, runner=gateway, capture_reply=True).stdout)
            assert web._material_compact_result(fixture_attempt,
                                                {'protocol': 'fixture'}, 'report') == {'_invalid_json': 'MODEL_OUTPUT_REJECTED'}
        elif reply_kind != 'complete':
            for _ in range(2):
                with pytest.raises(DeliveryReportError, match='截断|容量') as error:
                    run_delivery_agent(command, runner=gateway, capture_reply=True)
                assert error.value.failure_kind == ('output_incomplete' if reply_kind == 'length' else 'output_capacity')
            def captured(*args, **kwargs):
                return run_delivery_agent(command, runner=gateway, capture_reply=True).stdout
            monkeypatch.setattr(web, 'run_agent_sync', captured)
            (prep_env['tmp'] / 'report').mkdir()
            operations, receipts_seen = [], []
            async def execute(operation, current):
                operations.append(operation)
                receipts_seen.append(web._material_compact_result(
                    fixture_attempt, {'protocol': 'fixture'}, 'compact report'))
            asyncio.run(advance_creation(work['id'], execute))
            asyncio.run(advance_creation(work['id'], execute))
            # A bounded local prepare retry may inspect the same failed reply;
            # the completed gateway run must not be resubmitted or repaired.
            assert operations == ['prepare', 'prepare']
            # A failed captured terminal is retained as a classified invalid
            # receipt, never silently promoted to material facts or re-sent.
            assert receipts_seen == [{'_invalid_json': 'MODEL_OUTPUT_REJECTED'}] * 2
        else:
            assert run_delivery_agent(command, runner=gateway, capture_reply=True).stdout == result_text
            before = list(methods)
            assert run_delivery_agent(command, runner=gateway, capture_reply=True).stdout == result_text
            assert methods == before
        assert methods.count('agent') == 1
        call = next(iter(creation.get_creation(work['id'])['delivery']['agent_calls'].values()))
        assert call['run_id'] == run_id
        assert call.get('terminal_reply', {}).get('text') == (result_text if reply_kind == 'complete' else None)
    finally:
        active_delivery.reset(token)


@pytest.mark.parametrize('terminal_status', ['ok', 'error'])
def test_gateway_runtime_retirement_recovers_without_repeating_finished_run(prep_env, terminal_status):
    from easel.creation_delivery import active_delivery, DeliveryExecutionUncertain, next_operation
    from easel.integrations.openclaw_delivery import run_delivery_agent, reconcile_agent_calls

    work = _confirmed_delivery()
    command = ['openclaw', '--profile', 'fixture', 'agent', '--agent', 'main',
               '--session-key', 'owned-fixture-session', '--message', 'write report']
    methods = []
    cleanup_response = 'lost'

    def gateway(command, **kwargs):
        method = command[command.index('call') + 1]
        params = json.loads(command[command.index('--params') + 1])
        methods.append(method)
        if method == 'agent':
            payload = {'runId': params['idempotencyKey'], 'status': terminal_status, 'endedAt': 1000,
                       'error': 'bundle-mcp: live runtime limit (256) reached; token=DO_NOT_PERSIST'}
        else:
            assert method == 'sessions.abort'
            assert params == {'key': 'owned-fixture-session', 'agentId': 'main', 'clearQueued': True}
            stored = next(iter(creation.get_creation(work['id'])['delivery']['agent_calls'].values()))
            assert stored['status'] == terminal_status and stored['runtime_release'] == 'pending'
            if cleanup_response == 'lost':
                raise subprocess.TimeoutExpired(command, 20)
            payload = ({'ok': True, 'status': 'no-active-run', 'abortedRunId': None}
                       if cleanup_response == 'released' else {'ok': True})
        return subprocess.CompletedProcess(command, 0, json.dumps(payload), '')

    token = active_delivery.set(work['id'])
    try:
        with pytest.raises(DeliveryExecutionUncertain, match='接续清理'):
            run_delivery_agent(command, runner=gateway)
        with creation.edit_creation(work['id']) as current:
            current['delivery']['stopped'] = True
        assert next_operation(creation.get_creation(work['id'])) == ('observe_agent', 'observing_execution')
        with pytest.raises(DeliveryExecutionUncertain, match='另一网关'):
            reconcile_agent_calls(work['id'], command_prefix=['openclaw'], profile='other', runner=gateway)
        cleanup_response = 'invalid'
        with pytest.raises(DeliveryExecutionUncertain, match='接续清理'):
            run_delivery_agent(command, runner=gateway)
        cleanup_response = 'released'
        reconcile_agent_calls(work['id'], command_prefix=['openclaw'], profile='fixture', runner=gateway)
        assert next_operation(creation.get_creation(work['id'])) == (None, 'stopped')
        if terminal_status == 'ok':
            assert run_delivery_agent(command, runner=gateway).returncode == 0
        else:
            with pytest.raises(RuntimeError, match='临时工具环境已达上限'):
                run_delivery_agent(command, runner=gateway)
        assert methods == ['agent', 'sessions.abort', 'sessions.abort', 'sessions.abort']
        stored = next(iter(creation.get_creation(work['id'])['delivery']['agent_calls'].values()))
        assert stored['runtime_release'] == 'released' and 'DO_NOT_PERSIST' not in json.dumps(stored)
    finally:
        active_delivery.reset(token)


@pytest.mark.parametrize('failure', ['text_only', 'rejected', 'transport'])
def test_visual_gateway_rejection_does_not_become_phantom_pending(prep_env, failure):
    from easel.creation_delivery import active_delivery, DeliveryExecutionUncertain, next_operation
    from easel.integrations.openclaw_delivery import run_delivery_agent, DeliveryAgentRejected
    work = _confirmed_delivery()
    methods = []
    def gateway(command, **kwargs):
        method = command[command.index('call') + 1]
        methods.append(method)
        if method == 'models.list':
            return subprocess.CompletedProcess(command, 0, json.dumps({'models': [{
                'id': 'vision', 'provider': 'fixture', 'tags': ['default'], 'available': True,
                'input': ['text'] if failure == 'text_only' else ['text', 'image'],
            }]}), '')
        if failure == 'transport':
            return subprocess.CompletedProcess(command, 1, '', 'connection closed')
        return subprocess.CompletedProcess(command, 1, json.dumps({'ok': False, 'error': {
            'type': 'gateway_request_error', 'code': 'INVALID_REQUEST',
            'message': 'UnsupportedAttachmentError: active model does not accept image inputs',
        }}), '')
    token = active_delivery.set(work['id'])
    try:
        with pytest.raises(DeliveryExecutionUncertain if failure == 'transport' else DeliveryAgentRejected):
            run_delivery_agent(['openclaw', '--profile', 'fixture', 'agent', '--agent', 'main',
                                '--message', 'observe'], runner=gateway,
                               attachments=[{'type': 'image', 'content': 'ZmFrZQ=='}])
        current = creation.get_creation(work['id'])
        calls = current['delivery'].get('agent_calls', {})
        if failure == 'text_only':
            assert methods == ['models.list'] and not calls
        elif failure == 'rejected':
            assert next(iter(calls.values()))['rejected_before_start'] is True
            assert next_operation(current)[0] != 'observe_agent'
        else:
            assert next_operation(current)[0] == 'observe_agent'
    finally:
        active_delivery.reset(token)


@pytest.mark.parametrize('bound_postproduction', [False, True])
def test_delivery_authoring_keeps_live_stage_and_recovers_completed_files(prep_env, bound_postproduction):
    from easel.creation_delivery import advance_creation
    from easel.integrations.openclaw_delivery import reconcile_agent_calls
    from easel.integrations.openclaw_authoring import (
        run_attempt_scoped_authoring, release_delivery_authoring, retained_authoring_message,
        postproduction_authoring_instruction,
    )
    from tests.test_openclaw_authoring_boundary import _seed_attempt, ATTEMPT_ID
    from easel.integrations import result_protocols

    work = _confirmed_delivery()
    source = _seed_attempt(prep_env["tmp"] / "durable-authoring")
    post_path = source / 'productions/easel-authoring/POSTPRODUCTION_REQUIREMENTS.json'
    if bound_postproduction:
        post_path.write_text('{"status":"PENDING_AUTHORING"}')
    original_message = f'Author only in {source}' + postproduction_authoring_instruction(source)
    parent = prep_env["tmp"] / "isolated" / "authoring-staging"
    with creation.edit_creation(work["id"]) as current:
        current["hypit_attempts"] = [{"attempt_id": ATTEMPT_ID,
            "creation_id": current["id"], "result_protocols": result_protocols.current(),
            "planning_contract_version": 3,
            "execution_status": "NOT_SUBMITTED", "authoring_status": "AUTHORING_RUNNING",
            "material_gate": {"status": "MATERIAL_READY"}}]
    entry = {}
    run_id = None
    terminal = False
    calls = []

    def runner(command, **kwargs):
        nonlocal entry, run_id
        if "patch" in command:
            entries = json.loads(kwargs["input"])["agents"]["entries"]
            agent_id, config = next(iter(entries.items()))
            entry = {"id": agent_id, **config}
            return subprocess.CompletedProcess(command, 0, "{}", "")
        if "list" in command:
            return subprocess.CompletedProcess(command, 0, json.dumps([entry]), "")
        if "validate" in command or "delete" in command:
            calls.append("delete" if "delete" in command else "validate")
            return subprocess.CompletedProcess(command, 0, "{}", "")
        assert "gateway" in command
        method = command[command.index("call") + 1]
        calls.append(method)
        params = json.loads(command[command.index("--params") + 1])
        if method == "agent":
            assert run_id is None, "recovery must not submit another Agent"
            run_id = params["idempotencyKey"]
            payload = {"runId": run_id, "status": "accepted"}
        elif method == 'sessions.abort':
            assert terminal and staged.is_dir()
            payload = {'ok': True, 'status': 'no-active-run', 'abortedRunId': None}
        else:
            assert params["runId"] == run_id
            payload = {"runId": run_id, "status": "ok" if terminal else "timeout"}
            if terminal:
                payload["endedAt"] = 1000
        return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")

    async def execute(operation, current):
        if operation == "observe_agent":
            reconcile_agent_calls(current["id"], command_prefix=["openclaw"], profile="fixture", runner=runner)
            return
        assert operation == "author"
        # Rebuilt status/error context is different after a restart; it must
        # resume the original instruction and run instead of dispatching again.
        rebuilt_message = "状态变化后的阶段恢复提示" if terminal else original_message
        message = retained_authoring_message(ATTEMPT_ID, profile="fixture") or rebuilt_message
        assert message == original_message
        run_attempt_scoped_authoring(attempt_id=ATTEMPT_ID, attempt_workspace=source,
            message=message, command_prefix=["openclaw"], profile="fixture",
            staging_parent=parent, timeout=5, thinking="off", cwd=prep_env["tmp"], env={}, runner=runner,
            validate_artifacts=lambda staged: None)
        with creation.edit_creation(current["id"]) as value:
            value["hypit_attempts"][-1]["authoring_status"] = "AUTHORING_READY"
        release_delivery_authoring(ATTEMPT_ID, command_prefix=["openclaw"], profile="fixture",
                                   cwd=prep_env["tmp"], env={}, runner=runner)

    asyncio.run(advance_creation(work["id"], execute))
    staged = Path(entry["workspace"])
    assert staged.is_dir() and "delete" not in calls
    asyncio.run(advance_creation(work["id"], execute))
    assert staged.is_dir() and calls.count("agent") == 1
    retained = next(iter(creation.get_creation(work['id'])['delivery']['authoring_stages'].values()))
    assert retained['postproduction_input_sha256'] == (
        hashlib.sha256(post_path.read_bytes()).hexdigest() if bound_postproduction else None)
    # The independent fake gateway finishes while no Easel task is running.
    for path, value in {
        "productions/easel-authoring/material-selection.json": "{}",
        "productions/easel-authoring/authors/main.svml": "<svml/>",
        "productions/easel-authoring/runs/main.svrun": "<svrun/>",
    }.items():
        target = staged / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(value)
    terminal = True
    asyncio.run(advance_creation(work["id"], execute))
    if bound_postproduction:
        original = post_path.read_bytes()
        post_path.write_text('{"status":"changed"}')
        asyncio.run(advance_creation(work['id'], execute))
        assert staged.is_dir() and calls.count('agent') == 1 and 'delete' not in calls
        assert creation.get_creation(work['id'])['delivery']['authoring_stages']
        post_path.write_bytes(original)
    asyncio.run(advance_creation(work["id"], execute))
    assert calls.count("agent") == 1 and calls.count("delete") == 1
    assert (source / "productions/easel-authoring/authors/main.svml").read_text() == "<svml/>"
    assert not staged.exists()
    saved = creation.get_creation(work["id"])
    assert saved["hypit_attempts"][-1]["authoring_status"] == "AUTHORING_READY"
    assert saved["delivery"]["authoring_stages"] == {}


@pytest.fixture
def prep_env(tmp_path, monkeypatch):
    from easel import persona
    from easel.runtime_config import EaselRuntimeConfig
    from easel.integrations import material_supply
    from easel.materials.providers import LocalProvider, ProviderRegistry

    monkeypatch.setenv('OPENCLAW_CONFIG_PATH', str(tmp_path / 'offline-openclaw.json'))
    (tmp_path / 'offline-openclaw.json').write_text(json.dumps({
        'agents': {'defaults': {'model': {'primary': 'minimax/MiniMax-M3'}}}}))
    monkeypatch.setattr(web, 'THINKING_LEVEL', '')

    load_config = EaselRuntimeConfig.load
    monkeypatch.setattr(EaselRuntimeConfig, "load", classmethod(lambda cls: load_config(
        environ={"EASEL_MATERIAL_LIBRARY_ROOT": str(tmp_path / "library"),
                 "EASEL_MATERIAL_LOCAL_ROOTS": os.environ.get("EASEL_MATERIAL_LOCAL_ROOTS", "")},
        env_file=tmp_path / "absent.env")))
    monkeypatch.delenv("EASEL_MATERIAL_LOCAL_ROOTS", raising=False)

    def local_registry(roots):
        registry = ProviderRegistry()
        if roots:
            registry.register(LocalProvider(tuple(roots)))
        return registry, ()

    monkeypatch.setattr(material_supply, "product_provider_registry", local_registry)
    profiles = tmp_path / 'profiles'
    profile = profiles / '个人经营实践'
    profile.mkdir(parents=True)
    (profile / 'identity.md').write_text('隔离测试创作者，平等克制地记录观察。', encoding='utf-8')
    monkeypatch.setattr(persona, 'PROFILES_DIR', profiles)
    monkeypatch.setattr(web, 'PROFILES_DIR', profiles)
    outputs = tmp_path / "outputs"
    monkeypatch.setattr(creation, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(creation, "CREATIONS_DIR", outputs / "_creations")
    monkeypatch.setattr(service, "workspace_root", lambda: tmp_path / ".easel" / "hypit")
    monkeypatch.setenv("EASEL_HYPIT_HOME", str(tmp_path / ".easel" / "hypit"))
    work = creation.create_creation(
        "AI 越来越强以后，程序员真正稀缺的能力是什么？",
        profile="个人经营实践",
        creative_mode="clear_memo_video",
        route="hypit_video",
        origin={"type": "chat", "session_hash": "a" * 64, "initial_turn_hash": "b" * 64},
    )
    work = _confirm_current_video_plan(work)
    claim = prep.claim_chat_preparation(work["id"], "session-a", "turn-a")
    paths = prep.preparation_paths(work["id"], claim["operation_key"])
    write_drafts(work, paths["draft"])
    return {"tmp": tmp_path, "outputs": outputs, "work": work, "claim": claim, "paths": paths}


def write_drafts(work: dict, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    core = {
        "schema": "easel-content-core@1",
        "topic": work["idea"],
        "core_idea": "编码成本下降后，判断问题和承担结果可能更稀缺。",
        "tension": "写代码越来越快，但选择什么问题仍需要人负责。",
        "why_worth_telling": "这触及技术从业者对职业价值的现实疑问。",
        "audience": "正在重新评估职业能力的技术从业者。",
        "intended_takeaway": "把能力变化当作待验证的观察，而不是确定结论。",
        "claim_types": ["opinion", "hypothesis"],
        "boundaries": ["不声称这是所有公司的共同规律。"],
    }
    truth = {
        "schema": "easel-truth-packet@2",
        "claims": [{
            "claim": core["core_idea"],
            "kind": "hypothesis",
            "source": "model_inference",
            "confidence": "medium",
        }],
        "personal_facts": [],
        "first_person_allowed": [],
        "public_allowed": [core["topic"]],
        "forbidden_inventions": ["公司事件", "同事对话", "具体金额"],
        "uncertainty_policy": {
            "plan_is_not_experience": True,
            "learning_is_not_proven_capability": True,
            "unknown_claims": "label_uncertain",
        },
    }
    creator = {
        "schema": "easel-creator-context@1",
        "identity": {"public_description": "有开发经历的普通职场人，持续记录自己的观察。"},
        "audience": "希望看懂公司、职业和个人能力变化的普通职场人。",
        "voice": {"tone": "平等、克制", "avoid": ["导师口吻", "成功学"]},
        "relevant_context": ["有九年 Java 开发经历。"],
        "privacy_policy": {"do_not_infer_private_facts": True},
    }
    production_brief = {
        "schema": "easel-production-brief@1", "language": "zh-CN", "duration_seconds": 15,
        "aspect_ratio": "9:16", "audio_mode": "silent", "beats": [], "text_overlays": [],
        "visual_constraints": [], "material_sources": [], "ai_generation_allowed": False,
        "publication_allowed": False,
    }
    for name, value in (("content-core.json", core), ("truth-packet.json", truth),
                        ("creator-context.json", creator), ("production-brief.json", production_brief)):
        (directory / name).write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _current_vnext_planning_executor(attempt, context):
    """Current Planning/Truth owner with only the external model boundary fixed.

    All v3 checkpoints, source refs, native Plan and Material writes are real.
    Unexpected model phases fail closed; never route to a paid provider.
    """
    from unittest.mock import patch
    from tests.test_semantic_planning import (
        vnext_proposal, staged_fixture_wire, supported_fixture_answers,
        fixture_review_wire, _r4_current_truth_reply,
    )
    from easel.creation_delivery import active_delivery
    # The fixed model reply may include BGM only if the frozen @4 Handoff
    # expressly requests music. Never invent a voice/music Need for silent.
    _, manifest, _ = handoff.resolve_handoff(
        attempt["creation_id"], attempt["handoff"]["handoff_id"])
    confirmed_plan = manifest["production_request"]["video_plan"]
    audio_mode = confirmed_plan["specs"]["audio_mode"]
    # This test-only video response is enabled only by explicit motion in the
    # frozen Creator-confirmed scene. It does not add model permission to silent
    # static-scene commissions.
    requested_motion = "镜头从桌面右侧连续平移" in confirmed_plan["scenes"]
    two_still_scenes = "桌面一本蓝色封面笔记本" in confirmed_plan["scenes"]

    def fixed_external(message, timeout=None, session=None, **options):
        if message.startswith('〔Easel Semantic Planning vNext A-'):
            assert options['reply_contract'] == 'planning-result-v3'
            value = vnext_proposal()
            if requested_motion:
                value['needs'][0] = {
                    'scope': 'scene-1', 'role': '桌面平移真实动态镜头',
                    'modality': 'video', 'necessity': 'required',
                    'source_seconds': 5,
                    'frame': 'match_output',
                    'conditions': [
                        {'text': '镜头从桌面右侧连续平移到左侧，两张白纸始终清晰可见。',
                         'meaning': 'dynamic_action', 'strength': 'required',
                         'responsibility': 'material'},
                    ]}
            else:
                value['needs'][0]['conditions'].append({
                    'text': '在后期叠加正文。', 'strength': 'required',
                    'responsibility': 'postproduction'})
            if two_still_scenes:
                # Only the frozen second scene authorizes this extra image Need.
                value['needs'].append({
                    'scope': 'scene-2', 'role': '桌面蓝色笔记本',
                    'modality': 'image', 'necessity': 'required',
                    'conditions': [{'text': '桌面一本蓝色封面笔记本。',
                                    'strength': 'required', 'responsibility': 'material'}]})
            if audio_mode in {'music', 'mixed'}:
                value['needs'].append({
                    'scope': 'global', 'role': '背景音乐', 'modality': 'bgm',
                    'necessity': 'required',
                    'conditions': [{'text': '柔和的无歌词钢琴背景音乐',
                                    'strength': 'required', 'responsibility': 'material'}],
                    'sound': {'vocals_allowed': False}})
            return staged_fixture_wire(message, value)
        if '有界视觉复核' in message:
            assert options['reply_contract'] == 'planning-result-v3'
            packet = json.loads(message.splitlines()[-1])
            decisions = supported_fixture_answers(packet, [{
                'question': q['question'], 'decision': 'ACCEPT',
                'evidence': [0],
                'reason': '明确离线参考：冻结两张白纸条件与后期叠字。'
            } for q in packet['questions']])
            return json.dumps(fixture_review_wire(packet, decisions))
        if message.startswith('〔Easel Truth 来源引用审阅〕'):
            _r4_current_truth_reply(message)
            return 'offline source-ref Truth review'
        pytest.fail('Unexpected external model stage in current U2-A fixture')

    token = active_delivery.set(attempt['creation_id'])
    try:
        with patch.object(web, 'run_agent_sync', fixed_external):
            return _NATIVE_VNEXT_PLANNING_OWNER(attempt, context)
    finally:
        active_delivery.reset(token)


_current_vnext_planning_executor.planning_contract_version = 3


def _test_planning_executor(attempt, context):
    plan = MaterialPlan(
        plan_id=f"plan-{attempt['attempt_id'][-20:]}",
        creation_id=attempt["creation_id"], attempt_id=attempt["attempt_id"],
        context_refs=context["context_refs"],
        needs=(MaterialNeed(
            need_id="required-scene-video",
            scope=NeedScope(type=NeedScopeType.SCENE, ref="scene-1"),
            media_type=MediaType.VIDEO, role="主镜头",
            intent=NeedIntent(description="与主题相关的纪录片式主镜头"),
            importance=NeedImportance.REQUIRED,
        ),),
    )
    from tests.test_model_output_contracts import write_fixture_requirements
    write_fixture_requirements(Path(attempt['workspace']['path']) / 'planning', plan)
    return {"plan": plan, "context_refs": context["context_refs"],
            "treatment": "Treatment", "script": "假设脚本内容。", "scenes": "Scenes"}


def _prepare_creation(creation_id, **kwargs):
    kwargs.setdefault("planning_executor", _current_vnext_planning_executor)
    return prep.prepare_creation_for_hypit(creation_id, **kwargs)


def test_director_context_spells_out_strict_truth_and_creator_schemas(prep_env):
    prompt = prep.preparation_agent_context(
        prep_env["work"], {"action": "generate", "operation_key": prep_env["claim"]["operation_key"]})

    assert json.dumps(prep_env["work"]["idea"], ensure_ascii=False) in prompt
    assert "必须原样复制到 Content Core topic" in prompt
    assert "production-brief.json" in prompt
    assert "每条 claim 必须同时提供非空 claim、kind、source、confidence" in prompt
    assert "claims 只记录准备写进视频、且关于现实世界的具体内容主张" in prompt
    assert "claims、personal_facts、first_person_allowed 均使用空数组" in prompt
    assert "不能做到时改为 model_inference 并删除 source_quote" in prompt
    assert '"first_person_allowed":["仅允许的第一人称用途"]' in prompt
    assert '"unknown_claims":"label_uncertain"' in prompt
    assert '"identity":{"public_description":"公开身份概述"}' in prompt
    assert "不要增加 id、statement、notes 等字段" in prompt
    assert "模型归纳或推理绝不能标 user_statement" in prompt
    assert "Profile 不是 claims.source 的合法值" in prompt
    assert '"beats":[]' in prompt
    assert '"label":"动作"' not in prompt
    assert "--validate-draft" in prompt


def test_preparation_preflight_rejects_placeholder_without_freezing_and_retry_has_diagnostic(prep_env):
    work = prep_env["work"]
    key = prep_env["claim"]["operation_key"]
    paths = prep.preparation_paths(work["id"], key)
    brief_path = paths["draft"] / "production-brief.json"
    brief = json.loads(brief_path.read_text())
    brief["beats"] = [{"label": "动作", "duration_seconds": 2.5, "description": "可拍摄画面"}]
    brief_path.write_text(json.dumps(brief))
    with pytest.raises(prep.PreparationError, match="合计 2.5 秒") as caught:
        prep.validate_preparation_draft(work["id"], key)
    assert not paths["snapshot"].exists()
    prep.mark_preparation_failed(work["id"], str(caught.value))
    retry = prep.claim_chat_preparation(work["id"], "test-session", "retry")
    assert retry["action"] == "generate"
    assert retry["operation_key"] == key
    assert "合计 2.5 秒" in prep.preparation_agent_context(work, retry)
    assert "作品区查看失败原因" in web._preparation_reply("FAILED", error=str(caught.value))
    brief["beats"] = []
    brief_path.write_text(json.dumps(brief))
    assert prep.validate_preparation_draft(work["id"], key)["production_brief"]["beats"] == []
    assert not paths["snapshot"].exists()
    brief["beats"] = [{"label": "已确认节拍", "duration_seconds": brief["duration_seconds"], "description": "已确认表达"}]
    brief_path.write_text(json.dumps(brief))
    assert prep.validate_preparation_draft(work["id"], key)["production_brief"] == brief


def test_proposal_card_specs_reject_examples_and_freeze_drift(prep_env):
    from easel.creator_proposal import proposal_specs

    preview = proposal_specs([
        {"role": "assistant", "content": "示例：时长：60 秒；画幅：16:9；音轨：voice；语言：英文"},
        {"role": "user", "content": "15 秒，9:16，静音，简体中文。"},
    ])
    assert preview["missing"] == []
    assert preview["specs"] == {"duration_seconds": 15, "aspect_ratio": "9:16", "audio_mode": "silent", "language": "zh-CN"}
    reopened = proposal_specs([{ "role": "user", "content": "15 秒" }, {"role": "assistant", "content": "时长：待确认"}])
    assert reopened["specs"]["duration_seconds"] is None
    ambiguous = proposal_specs([{"role": "user", "content": "时长上限 45 秒；不要静音；不是 9:16"}])
    assert all(value is None for value in ambiguous["specs"].values())
    assert all(value is None for value in proposal_specs([{"role": "assistant", "content": "示例：15 秒、9:16、静音、简体中文"}])["specs"].values())
    # Actual conversation: select an offered orientation, natural audio wording,
    # then a malformed assistant recap must not erase the user's selections.
    natural = proposal_specs([
        {"role": "assistant", "content": "时长：30 秒\n画幅：待确认\n音轨：待确认\n语言：简体中文"},
        {"role": "user", "content": "旁白 + 一小段低饱和背景乐"},
        {"role": "assistant", "content": "9:16（竖屏）→ 抖音\n1:1（方屏）→ 微博\n16:9（横屏）→ B站\n音轨：旁白 + 一小段低饱和背景乐"},
        {"role": "user", "content": "竖屏"},
        {"role": "assistant", "content": "时长：30 秒\n9:16（竖屏）\n音- 画幅：轨：旁白 + 一小段低饱和背景乐\n语言：简体中文"},
    ])
    assert natural == {'specs': {'duration_seconds': 30, 'aspect_ratio': '9:16',
                                'audio_mode': 'mixed', 'language': 'zh-CN'}, 'missing': []}
    assert proposal_specs([{'role': 'user', 'content': '竖屏'}])['specs']['aspect_ratio'] is None
    for content in ('旁白 + 不要背景音乐', '旁白 + 背景音乐？', '例如旁白 + 背景音乐'):
        assert proposal_specs([{'role': 'user', 'content': content}])['specs']['audio_mode'] is None
    work = prep_env["work"]
    with creation.edit_creation(work["id"]) as persisted:
        persisted["chat_workflow"]["production_specs"] = preview["specs"]
    key = prep_env["claim"]["operation_key"]
    draft = prep.preparation_paths(work["id"], key)["draft"] / "production-brief.json"
    brief = json.loads(draft.read_text())
    assert prep.validate_preparation_draft(work["id"], key)["production_brief"]["duration_seconds"] == 15
    brief["duration_seconds"] = 16
    draft.write_text(json.dumps(brief))
    with pytest.raises(prep.PreparationError, match="确认的方案卡不一致"):
        prep.validate_preparation_draft(work["id"], key)
    assert not prep.preparation_paths(work["id"], key)["snapshot"].exists()


def test_chat_preparation_freezes_truth_core_mode_and_attempt_without_build(prep_env, monkeypatch):
    monkeypatch.setattr(service, "_cli", lambda *_args, **_kwargs: pytest.fail("Hypit CLI must not run"))
    result = _prepare_creation(prep_env["work"]["id"], runtime_profile=None,
                               planning_executor=_current_vnext_planning_executor)

    work = creation.get_creation(prep_env["work"]["id"])
    attempt = service.get_film_attempt(result["attempt_id"])
    package, manifest, handoff_hash = handoff.resolve_handoff(work["id"], result["handoff_id"])
    task = (Path(attempt["workspace"]["path"]) / "AUTHORING_TASK.md").read_text(encoding="utf-8")

    assert result["status"] == "MATERIAL_NOT_READY"
    assert result["runtime_status"] == "NOT_CONFIGURED"
    assert result["execution_status"] == "BLOCKED"
    assert result["attempt_number"] == 1
    assert work["preparation"]["status"] == "MATERIAL_NOT_READY"
    assert work["status"] == "not_ready"
    assert work["preparation"]["runtime_status"] == "NOT_CONFIGURED"
    assert work["stages"]["content_core"]["status"] == "completed"
    assert attempt["authoring_status"] == "READY_FOR_EXTERNAL_AUTHORING"
    assert attempt["runtime_status"] == "NOT_CONFIGURED"
    assert attempt["execution_status"] == "BLOCKED"
    assert attempt["status"] == "MATERIAL_NOT_READY"
    assert attempt["runtime_profile"] is None
    assert attempt["material_planning"]["status"] == "PLANNING_READY"
    assert attempt["material_gate"]["status"] == "MATERIAL_NOT_READY"
    assert "production_authoring" not in attempt
    assert handoff_hash == work["hypit_handoffs"][0]["hash"]
    assert manifest["content"]["truth_packet"]["hash"]
    assert manifest["production_request"]["production_brief"]["schema"] == "easel-production-brief@1"
    assert manifest["production_request"]["production_brief_sha256"] == work["preparation"]["snapshot_hashes"]["production_brief"]
    assert manifest["creator_context"]["profile_id"] == "个人经营实践"
    assert manifest["creator_context"]["profile_source_sha256"].startswith("sha256:")
    assert "preferred_duration_seconds" not in manifest["production_request"]
    assert (package / "creative-mode" / "director-treatment.md").is_file()
    assert "YOU OWN:" in task and "Treatment and video script" in task
    assert "Do not read an old Easel storyboard" in task
    assert "hypit build" in task and "separate operator-approved action" in task
    assert not (Path(attempt["workspace"]["path"]) / "hypit.runtime.json").exists()


def test_historical_script_truth_operator_api_is_read_only(prep_env, monkeypatch):
    """A rejected legacy Planning executor never becomes an operator write."""
    from fastapi.testclient import TestClient

    def retired_planning(*_args, **_kwargs):
        pytest.fail('Legacy Planning executor cannot be dispatched')

    with pytest.raises(prep.PreparationError, match='旧 Planning / 未登记执行'):
        _prepare_creation(prep_env['work']['id'], runtime_profile=None,
                          planning_executor=retired_planning)
    persisted = creation.get_creation(prep_env['work']['id'])
    attempt = service.get_film_attempt(persisted['hypit_attempts'][-1]['attempt_id'])
    assert not Path(attempt['workspace']['path']).joinpath('planning/manifest.json').exists()
    # Simulate one *old record* only within the isolated test directory.
    with creation.edit_creation(persisted['id']) as old:
        old['delivery'].pop('production_contract')
    original = creation._creation_path(persisted['id']).read_bytes()
    web.app.dependency_overrides[web.require_local_operator] = lambda: None
    try:
        with TestClient(web.app) as client:
            read = client.get(f"/api/film-attempts/{attempt['attempt_id']}")
            response = client.post(
                f"/api/film-attempts/{attempt['attempt_id']}/script-truth/review",
                json={"scriptSha256": "0" * 64, "truthPacketSha256": "1" * 64,
                      "confirmAllClaimsReviewed": True, "reviewer": "local_operator"})
    finally:
        web.app.dependency_overrides.pop(web.require_local_operator, None)
    assert read.status_code == 200
    assert read.json()['operator_admission']['allowed_actions']['approve_final'] is False
    assert response.status_code == 410
    assert creation._creation_path(persisted['id']).read_bytes() == original



@pytest.mark.parametrize('risk', ['semantic_reject', 'truth_reject'])
def test_current_planning_truth_refusal_does_not_rewrite_or_supply(prep_env, monkeypatch, risk):
    """Current frozen A/B/Truth refusal replaces retired mutable Script-rewrite flow.

    Reuse the complete source-ref Owner scenario; it asserts zero downstream
    Supply and no repair-purchased acceptance when independent review rejects.
    Historical Writer messages are deliberately not reintroduced here.
    """
    from tests.test_semantic_planning import test_vnext_continuous_owner_boundary
    test_vnext_continuous_owner_boundary(prep_env, monkeypatch, risk)




def test_configured_local_material_root_runs_product_gate_before_authoring(prep_env, monkeypatch):
    local_root = prep_env["tmp"] / "local-materials"
    local_root.mkdir()
    Image.new("RGB", (720, 1280), (40, 50, 60)).save(local_root / "portrait.jpg")
    monkeypatch.setenv("EASEL_MATERIAL_LOCAL_ROOTS", str(local_root))
    monkeypatch.setattr(service, "_cli", lambda *_args, **_kwargs: pytest.fail("Material preparation must not call Hypit CLI"))

    result = _prepare_creation(prep_env["work"]["id"], runtime_profile=None)
    attempt = service.get_film_attempt(result["attempt_id"])
    assert result["status"] == "MATERIAL_NOT_READY"
    assert attempt["material_planning"]["status"] == "PLANNING_READY"
    assert attempt["material_gate"]["status"] == "MATERIAL_NOT_READY"
    assert "production_authoring" not in attempt


def test_director_planning_executor_consumes_frozen_current_refs_and_rejects_rewrites(prep_env, monkeypatch):
    """Current vNext Planning consumes real Handoff pins, never an old file Writer."""
    from easel.integrations.material_layer import PlanningIntegration
    from easel.integrations.semantic_boundary import POLICY
    prepared = _prepare_creation(prep_env['work']['id'], runtime_profile=None)
    attempt = service.get_film_attempt(prepared['attempt_id'])
    work = creation.get_creation(prepared['creation_id'])
    _, manifest, _ = handoff.resolve_handoff(work['id'], prepared['handoff_id'])
    hashes = work['preparation']['snapshot_hashes']
    refs = {
        'content_core_sha256': hashes['content_core'],
        'truth_packet_sha256': hashes['truth_packet'],
        'creator_context_sha256': hashes['creator_context'],
        'production_brief_sha256': hashes['production_brief'],
        'creative_mode_sha256': manifest['creative_mode']['hash'],
    }
    frozen = PlanningIntegration().load(attempt)
    assert frozen['plan'].context_refs == refs
    assert frozen['plan'].policy['semantic_compiler'] == POLICY
    assert len(frozen['plan'].needs) > 0
    assert attempt['planning_contract_version'] == 3
    assert frozen['manifest']['schema'] == 'easel-material-planning@3'
    root = Path(attempt['workspace']['path'])
    assert (root / 'planning/SCRIPT.md').read_bytes() == (
        work['delivery']['video_plan']['script'].encode())
    assert (root / 'planning/SCENES.md').read_bytes() == (
        work['delivery']['video_plan']['scenes'].encode())

    monkeypatch.setattr(web, 'run_agent_sync', lambda *_args, **_kwargs:
                        pytest.fail('Current confirmed Planning cannot re-buy a model call'))
    original = (root / 'planning/SCENES.md').read_bytes()
    with pytest.raises(prep.PreparationError, match='重新确认'):
        web._material_planning_executor(attempt, {
            'context_refs': refs, 'quality_repair': {
                'origin': 'system_quality', 'allowed_changes': ['planning'],
                'feedback': [{'text': '请篡改当前冻结方案'}]}})
    assert (root / 'planning/SCENES.md').read_bytes() == original
    (root / 'planning/SCENES.md').write_text('未经确认的外部重写')
    with pytest.raises(prep.PreparationError, match='冻结来源无效'):
        web._material_planning_executor(attempt, {'context_refs': refs})
    (root / 'planning/SCENES.md').write_bytes(original)
    assert PlanningIntegration().load(attempt)['plan'] == frozen['plan']




def test_failed_planning_and_not_ready_retry_reuse_frozen_attempt(prep_env):
    creation_id = prep_env["work"]["id"]
    original_key = prep_env["claim"]["operation_key"]

    def failed_planning(_attempt, _context):
        raise prep.PreparationError("Planning Agent did not write MaterialPlan")
    # A current registered executor can fail before its first response; the
    # retry must retain this same Attempt and planning_contract_version=3.
    failed_planning.planning_contract_version = 3

    with pytest.raises(prep.PreparationError, match="MaterialPlan"):
        prep.prepare_creation_for_hypit(
            creation_id, runtime_profile=None, planning_executor=failed_planning,
        )
    failed = creation.get_creation(creation_id)
    assert failed["preparation"]["status"] == "MATERIAL_FAILED"
    assert failed["preparation"]["failure_stage"] == "planning"
    attempt_id = failed["hypit_attempts"][0]["attempt_id"]

    retry = prep.claim_chat_preparation(creation_id, "session-a", "retry-planning")
    assert retry["action"] == "resume"
    assert retry["operation_key"] == original_key
    first = _prepare_creation(creation_id, runtime_profile=None)
    assert first["status"] == "MATERIAL_NOT_READY"
    assert first["attempt_id"] == attempt_id
    saved = creation.get_creation(creation_id)
    assert len(saved["hypit_handoffs"]) == 1
    assert len(saved["hypit_attempts"]) == 1


@pytest.mark.parametrize('root_echo,sfx,source_scope_experimental', [
    (False, False, False), (True, False, False), (True, True, False),
    (False, False, 'm31'), (True, True, 'reject_sfx_scope')])
def test_current_planning_inherits_atomic_and_tempo_guidance(prep_env, monkeypatch, root_echo, sfx,
                                                          source_scope_experimental):
    """Real @4 Handoff/Planning/Truth owners; only external replies are fixed."""
    from easel.integrations import semantic_boundary_run as boundary
    from easel.integrations import planning_semantic_review as review
    from easel.integrations import planning_candidate_review as candidate_review
    from easel.integrations.material_layer import PlanningIntegration
    if source_scope_experimental == 'm31':
        from scripts.configure_minimax_m3_thinking import migrated_m31_profile
        config = {'models': {'providers': {'minimax': {'api': 'openai-completions',
            'baseUrl': 'https://api.minimax.cn/v1', 'models': [{'id': 'MiniMax-M3'}]}}},
            'agents': {'defaults': {'model': {'primary': 'minimax/MiniMax-M3'}}}}
        (prep_env['tmp'] / 'offline-openclaw.json').write_text(json.dumps(migrated_m31_profile(config)))
        source_scope_experimental = False
    reject_sfx_scope = source_scope_experimental == 'reject_sfx_scope'
    source_scope_experimental = False
    messages = {}
    equivalent_details = []
    original = boundary.view_a_message
    review_messages = []
    original_review_message = candidate_review.message_for

    def observe_review(batch, **kwargs):
        message = original_review_message(batch, **kwargs)
        review_messages.append(message)
        return message

    def observe(scope, view, stage, **kwargs):
        assert scope['transport']['intake_policy'] == review.INTAKE_POLICY
        message = original(scope, view, stage, **kwargs)
        messages[stage] = message
        return message

    monkeypatch.setattr(boundary, 'view_a_message', observe)
    monkeypatch.setattr(candidate_review, 'message_for', observe_review)
    monkeypatch.setattr(service, '_cli', lambda *_a, **_kw: pytest.fail('No Hypit execution'))
    work = prep_env['work']
    if root_echo:
        from tests import test_semantic_planning as external
        original_wire = external.staged_fixture_wire

        def echoed_selection(message, value):
            if sfx:
                value['needs'].append({
                    'scope': 'event-1', 'role': '杯底轻触桌面音效', 'modality': 'sfx',
                    'necessity': 'required',
                    'conditions': [
                        {'text': '杯底轻触桌面，短促干脆的轻嗒声，无拖尾。',
                         'strength': 'required', 'responsibility': 'material', 'meaning': 'observable'},
                        {'text': '轻嗒声与杯底接触桌面的画面瞬间对齐，混音低于旁白。',
                         'strength': 'required', 'responsibility': 'postproduction', 'meaning': 'observable'}],
                    'sound': {'event_description': '杯底轻触桌面的轻嗒声', 'sound_character': '短促干脆，无拖尾'}})
            raw = original_wire(message, value)
            if sfx and message.startswith('〔Easel Semantic Planning vNext A-details〕'):
                # Same external fixture bytes through the real current Owner;
                # experiment changes no production request or journal identity.
                equivalent_details.append(json.loads(raw))
            if message.startswith('〔Easel Semantic Planning vNext A-selection〕'):
                data = json.loads(raw)
                if reject_sfx_scope:
                    data['needs'][-1]['scope'] = data['needs'][0]['scope']
                data['contains'] = {'modality': 'bgm', 'necessity': 'required'}
                return json.dumps(data, ensure_ascii=False)
            return raw

        monkeypatch.setattr(external, 'staged_fixture_wire', echoed_selection)
        work = creation.create_creation('隔离配乐回声验收', creative_mode='clear_memo_video',
            route='hypit_video', origin={'type': 'chat', 'session_hash': 'e' * 64})
        proposal = VIDEO_PROPOSAL.replace('无旁白，无音乐。', '轻柔无歌词钢琴配乐，无旁白。').replace(
            '音轨：静音', '音轨：music')
        if sfx:
            proposal = proposal.replace('0–15 秒：', '0–15 秒：杯底轻触桌面，短促干脆的轻嗒声，无拖尾；轻嗒声与杯底接触桌面的画面瞬间对齐，混音低于旁白。')
        work = _confirm_current_video_plan(work, proposal=proposal)
        claim = prep.claim_chat_preparation(work['id'], 'echo-test', 'echo-confirmed')
        paths = prep.preparation_paths(work['id'], claim['operation_key'])
        write_drafts(work, paths['draft'])
        brief_path = paths['draft'] / 'production-brief.json'
        brief = json.loads(brief_path.read_text())
        brief['audio_mode'] = 'music'
        brief_path.write_text(json.dumps(brief))
    if reject_sfx_scope:
        with pytest.raises(prep.PreparationError, match='selection admission rejected'):
            _prepare_creation(work['id'], runtime_profile=None)
        from easel.materials.store import AttemptMaterialStore
        attempt = creation.get_creation(work['id'])['hypit_attempts'][-1]
        journal = AttemptMaterialStore(attempt['workspace']['path']).read_recovery_record(boundary.STATE_KEY)
        assert set(journal['calls']) == set(messages) == {'A-selection'}
        assert journal['admissions']['A-selection']['owner_eligibility']['decision']['outcome'] == 'REJECT'
        assert not journal['repair_used'] and not journal.get('detail_binding')
        assert not journal['admissions']['A-selection']['receipt']['actions']
        assert 'contains' in json.loads(journal['calls']['A-selection']['reply'])
        assert attempt['build']['operation'] is None
        return
    result = _prepare_creation(work['id'], runtime_profile=None)
    attempt = service.get_film_attempt(result['attempt_id'])
    stored = PlanningIntegration().load(attempt)
    assert stored['plan'].needs
    assert review_messages
    assert all('quote=null' not in message and '仅合法非字符串来源' in message
               and '不得用null冒充依据' in message for message in review_messages)
    assert result['status'] == 'MATERIAL_NOT_READY'
    assert 'role只写' in messages['A-selection']
    details = messages['A-details']
    contract = json.loads(details.splitlines()[-1])['atomic_slot_output_contract']
    assert contract['condition_properties'] == ['text', 'strength', 'responsibility', 'meaning']
    assert contract['exact_names'] == (['slot_000', 'slot_001', 'slot_002'] if sfx else ['slot_000', 'slot_001'] if root_echo else ['slot_000'])
    assert 'sound.tempo_bpm是可选字段' in details
    assert '与画面同步、点位对齐' in details
    shape = json.loads(details.splitlines()[-1])['detail_shape_contract']
    assert shape['condition_same_level_fields']['strength']['type'] == 'string'
    assert shape['condition_same_level_fields']['strength']['enum'] == ['required', 'preference']
    assert shape['condition_required'] == ['text', 'strength', 'responsibility']
    assert 'queries' in shape['slots']['slot_000']['allowed_properties']
    if root_echo:
        assert 'queries' not in shape['slots']['slot_001']['allowed_properties']
    if sfx:
        assert 'queries' not in shape['slots']['slot_002']['allowed_properties']
    assert attempt['build']['operation'] is None
    if root_echo:
        from easel.materials.store import AttemptMaterialStore
        journal = AttemptMaterialStore(attempt['workspace']['path']).read_recovery_record(boundary.STATE_KEY)
        admitted = journal['admissions']['A-selection']
        if source_scope_experimental:
            assert journal['scope']['transport']['source_selection_policy'] == (
                'planning-source-kind-handles-experiment@1' if source_scope_experimental == 'kind'
                else 'test-only-planning-source-scope@3')
        assert admitted['receipt']['decision']['outcome'] == 'NORMALIZE'
        assert admitted['receipt']['actions'][0]['path'] == ['contains']
        assert 'contains' in json.loads(journal['calls']['A-selection']['reply'])
        assert 'contains' not in admitted['candidate']
        if sfx:
            from easel.integrations import planning_input_view as views, planning_staged_proposal as staged, planning_wire as wire
            scope = journal['scope']
            view = views.PlanningInputView(scope['inputs'], scope['catalog'])
            selected = view.codec.decode(boundary.require_selection_admission(admitted, scope=scope),
                                         view.codec.identity, diagnostic=True)
            codec = staged._read_only_staged(boundary.query_schema(scope))
            batch_plan = codec.detail_batches(selected)
            assert len(batch_plan['batches']) == 1
            batch, = [b for b in batch_plan['batches'] if 'slot_002' in b['slots']]
            persisted = json.loads(journal['calls'][batch['key']]['reply'])['slots']['slot_002']
            assert [(c['strength'], c['responsibility'], c['meaning']) for c in persisted['conditions']] == [
                ('required', 'material', 'observable'), ('required', 'postproduction', 'observable')]
            assert any(n.modality_spec.kind == 'sfx' for n in stored['plan'].needs)
            assert '杯底轻触桌面' in json.dumps(stored['plan'].model_dump(mode='json'), ensure_ascii=False)
            from jsonschema import Draft202012Validator
            from tests.planning_material_matrix.producer_experiment import equivalent_schema_experiment
            contract = batch_plan['complete']
            projection = wire.project(contract['schema'], 'A-details', atomic_framing=True)
            candidate, changes = equivalent_schema_experiment(projection.schema)
            assert changes and len(equivalent_details) == 1
            raw = equivalent_details[0]
            assert Draft202012Validator(candidate).is_valid(raw)
            assert Draft202012Validator(projection.schema).is_valid(raw)
            from copy import deepcopy
            # Closed modality, required fields, and condition semantics must
            # remain rejected under both schemas, including protected predicates.
            for fault in ('slot_array', 'audio_queries', 'missing_condition_text', 'sfx_action'):
                altered = deepcopy(raw)
                if fault == 'slot_array':
                    altered['slots']['slot_000'] = [altered['slots']['slot_000'], {}]
                elif fault == 'audio_queries':
                    altered['slots']['slot_002']['queries'] = []
                elif fault == 'missing_condition_text':
                    del altered['slots']['slot_002']['conditions'][0]['text']
                else:
                    altered['slots']['slot_002']['conditions'][0]['meaning'] = 'dynamic_action'
                assert not Draft202012Validator(candidate).is_valid(altered), fault
                assert not Draft202012Validator(projection.schema).is_valid(altered), fault
            canonical = codec.assemble_candidate(selected, projection.decode_candidate(raw), contract['identity'])
            from easel.integrations.planning_semantic_review import structural_targets
            assert structural_targets(canonical, local_query_faults=True, flexible_queries=True) == []


def test_captured_missing_text_stays_rejected_and_old_intake_cannot_dispatch(tmp_path):
    """Replay the real failed capture; never fill its missing creative text."""
    from copy import deepcopy
    from easel.integrations import semantic_boundary_run as boundary
    from easel.integrations import planning_input_view, planning_staged_proposal, planning_wire
    from easel.integrations import planning_semantic_review as review
    from easel.materials.store import AttemptMaterialStore
    fixture = Path(__file__).parent / 'fixtures/planning-intake11-missing-condition-text.json'
    original_bytes = fixture.read_bytes()
    state = json.loads(original_bytes)['snapshot']
    scope = state['scope']
    view = planning_input_view.PlanningInputView(scope['inputs'], scope['catalog'])
    selected = view.codec.decode(boundary.require_selection_admission(
        state['admissions']['A-selection']), view.codec.identity, diagnostic=True)
    expected_transport = boundary.transport_identity(scope['catalog'], intake_inputs=scope['inputs'],
        intake_policy=scope['transport']['intake_policy'])
    # Original carrier pins are historical evidence, never current dispatch identity.
    assert scope['transport'] != expected_transport
    assert {**scope['transport'], 'runtime_sha256': expected_transport['runtime_sha256']} == expected_transport
    with pytest.raises(ValueError, match='transport identity changed'):
        boundary.validate_transport(state['schema'], scope)
    for stage in ('A-selection', 'A-details'):
        kwargs = {} if stage == 'A-selection' else {
            'selection': selected, 'binding': state['detail_binding']}
        message = boundary.view_a_message(scope, view, stage, **kwargs)
        call = state['calls'][stage]
        assert hashlib.sha256(message.encode()).hexdigest() == call['request_sha256']
        assert hashlib.sha256(call['reply'].encode()).hexdigest() == call['reply_sha256']
    current = deepcopy(scope)
    current['transport'] = boundary.transport_identity(scope['catalog'], intake_inputs=scope['inputs'])
    assert current['transport']['intake_policy'] == review.INTAKE_POLICY
    assert boundary.query_schema(current) == boundary.query_schema(scope)
    codec = planning_staged_proposal._read_only_staged(boundary.query_schema(scope))
    contract = codec.details_contract(selected, diagnostic=True)
    projection = planning_wire.project(contract['schema'], 'A-details', atomic_framing=True)
    raw = json.loads(state['calls']['A-details']['reply'])
    errors = projection.errors(raw)
    assert {tuple(e['path']) for e in errors if e['keyword'] == 'not'} == {
        ('slots', f'slot_{i:03}', 'conditions') for i in (7, 8, 9)}
    assert any(e['keyword'] == 'required' and e['path'] == [
        'slots', 'slot_010', 'conditions', 4] for e in errors)
    with pytest.raises(ValueError, match='Candidate properties changed'):
        codec.assemble_candidate(selected, projection.decode_candidate(raw), contract['identity'])
    store = AttemptMaterialStore(tmp_path)
    store.write_recovery_record(boundary.STATE_KEY, state)
    journal = tmp_path / 'materials/recoveries/semantic-planning-vnext.json'
    before = journal.read_bytes()
    with pytest.raises(ValueError, match='Historical Planning intake is read-only'):
        boundary.run({'workspace': {'path': str(tmp_path)}}, {}, {}, {}, {},
                     lambda *_a, **_kw: pytest.fail('Historical capture must not dispatch'))
    assert journal.read_bytes() == before
    assert fixture.read_bytes() == original_bytes


@pytest.mark.parametrize("invalid_kind", ["domain", "retrieval", "video_duration"])
def test_current_planning_rejects_tampered_frozen_plan_without_model_retry(
        prep_env, monkeypatch, invalid_kind):
    """A frozen vNext derived Plan is immutable; old Writer repair is gone."""
    from easel.integrations.material_layer import PlanningIntegration
    prepared = _prepare_creation(prep_env['work']['id'], runtime_profile=None)
    attempt = service.get_film_attempt(prepared['attempt_id'])
    root = Path(attempt['workspace']['path'])
    stored = PlanningIntegration().load(attempt)
    original_plan = stored['plan']
    plan_file = root / 'planning/MATERIAL_PLAN.json'
    invalid = json.loads(plan_file.read_text())
    if invalid_kind == 'domain':
        invalid['schema'] = 'easel-material-plan@1'
        invalid['policy'] = {'must_be_a_string': True}
    elif invalid_kind == 'retrieval':
        invalid['needs'][0]['constraints'] = {'allowed_source_kinds': ['external_stock']}
    else:
        invalid['needs'][0].update(media_type='video',
            modality_spec={'kind':'video', 'duration_seconds':8})
    altered = json.dumps(invalid, ensure_ascii=False)
    plan_file.write_text(altered, encoding='utf-8')
    monkeypatch.setattr(web, 'run_agent_sync', lambda *_a, **_kw:
                        pytest.fail('Tampered current Plan must not buy a retry'))
    with pytest.raises(prep.PreparationError, match='已有派生产物'):
        web._material_planning_executor(attempt, {
            'context_refs': original_plan.context_refs})
    assert plan_file.read_text() == altered
    assert service.get_film_attempt(attempt['attempt_id'])['planning_contract_version'] == 3
    assert service.get_film_attempt(attempt['attempt_id'])['build']['operation'] is None



def test_chat_api_discusses_then_requires_explicit_confirmation(prep_env, monkeypatch):
    from fastapi.testclient import TestClient

    from dataclasses import replace
    from easel.runtime_config import EaselRuntimeConfig, MiniMaxRuntimeConfig
    config = replace(EaselRuntimeConfig.load(), minimax=MiniMaxRuntimeConfig(api_key='fixture-key'))
    monkeypatch.setattr(EaselRuntimeConfig, 'load', lambda: config)
    agent_calls = []

    def fake_agent(message, timeout, session_id=None):
        agent_calls.append((message, timeout, session_id))
        if "〔Creation Preparation V1：本作品的唯一准备任务〕" not in message:
            assert "视频创作方案讨论阶段" in message
            assert "提案阶段的最高优先级边界" in message
            assert "不得展开内部思考、工具/命令/会话状态或自我对话" in message
            assert "不得扫描本机素材目录" in message
            assert "提出一个可执行推荐及简短依据" in message
            assert "明确标为 Easel 推荐" in message
            assert "没有明确来源时，不自行补视频时长" not in message
            assert "只写以下四个 JSON 文件" not in message
            return VIDEO_PROPOSAL
        assert "提案阶段的最高优先级边界" not in message
        match = re.search(r"只写以下四个 JSON 文件到目录 (.+)：", message)
        assert match, "Director must receive a bounded preparation output location"
        creation_match = re.search(r"CURRENT_CREATION_ID=(cr_[0-9a-f]{32})", message)
        assert creation_match, "Director must receive the backend-bound Creation ID"
        work = creation.get_creation(creation_match.group(1))
        write_drafts(work, Path(match.group(1)))
        return "INTERNAL_PREPARATION outputs/content-core.json internal reasoning"

    monkeypatch.setattr(web, "run_agent_sync", fake_agent)
    monkeypatch.setattr(web, "_material_planning_executor", _current_vnext_planning_executor)
    monkeypatch.setattr(web, "_hypit_runtime_profile", lambda: None)
    monkeypatch.setattr(service, "workspace_root", lambda: prep_env["tmp"] / ".easel" / "hypit")
    monkeypatch.setattr(service, "_cli", lambda *_args, **_kwargs: pytest.fail("Hypit CLI must not run"))

    payload = web.ChatRequest(
        message="AI 越来越强以后，程序员真正稀缺的能力是什么？",
        persona="个人经营实践",
        creativeMode="clear_memo_video",
        capability="ai-film",
        sessionId="api-session",
        turnId="api-turn",
    )
    # The HTTP contract is checked without the lifespan background dispatcher.
    # Explicit Delivery advancement below remains the sole execution owner.
    async def isolated_delivery_worker(stop, _executor):
        await stop.wait()
    monkeypatch.setattr(web, "serve_delivery", isolated_delivery_worker)
    with TestClient(web.app) as client:
        response = client.post("/api/chat", json=payload.model_dump())
        assert response.status_code == 200
        first_body = response.json()
        first_work = creation.get_creation(first_body["creationId"])
        assert first_work["chat_workflow"]["proposal_status"] == "READY_FOR_CONFIRMATION"
        assert first_work.get("hypit_handoffs", []) == []
        assert first_work.get("hypit_attempts", []) == []
        assert first_work.get("preparation", {}).get("status") == "CREATED"

        confirmation = web.ChatRequest.model_validate({**payload.model_dump(),
            "message": "按当前方案开始制作",
            "turnId": "api-turn-confirm",
            "creationAction": "confirm_production",
            "videoPlanSha256": first_work["chat_workflow"]["video_plan"]["sha256"],
            "proposalContext": [
                {"role": "user", "content": "做一个短视频，纯静音。"},
                {"role": "assistant", "content": "建议 6 个节拍、15 秒。"},
                {"role": "user", "content": "确认 6 个节拍、15 秒、9:16、静音、简体中文、不露脸。"},
            ],
        })
        preview = client.post(f"/api/creations/{first_work['id']}/proposal-preview",
            json={'proposalContext': [turn.model_dump() for turn in confirmation.proposalContext]}).json()
        assert preview['confirmable'] is True
        offered = preview['generation_budget']
        assert offered['available'] is True and 'fixture-key' not in json.dumps(offered)
        declaration = preview['input_use']
        assert declaration['schema'] == 'easel-input-use@3'
        assert declaration['video_plan_sha256'] == first_work['chat_workflow']['video_plan']['sha256']
        assert declaration['audio_mode'] == 'silent'
        assert 'preset_voice_synthesis' not in declaration['operations']
        assert 'text_to_visual_generation' in declaration['operations'] and '以文字生成视觉素材' in declaration['statement']
        unsigned = {k: v for k, v in declaration.items() if k != 'statement_sha256'}
        assert declaration['statement_sha256'] == hashlib.sha256(json.dumps(
            unsigned, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
        stale = {**confirmation.model_dump(), 'inputUseStatementSha256': '0' * 64}
        assert client.post('/api/chat', json=stale).status_code == 409
        assert not creation.get_creation(first_work['id'])['chat_workflow'].get('confirmed_at')
        old_scope = {**unsigned, 'schema': 'easel-input-use@2'}
        old_scope_hash = hashlib.sha256(json.dumps(
            old_scope, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
        old_page = {**confirmation.model_dump(), 'inputUseStatementSha256': old_scope_hash}
        assert client.post('/api/chat', json=old_page).status_code == 409
        assert not creation.get_creation(first_work['id'])['chat_workflow'].get('confirmed_at')
        ordinary = {**confirmation.model_dump(), 'creationAction': None,
                    'inputUseStatementSha256': declaration['statement_sha256']}
        assert client.post('/api/chat', json=ordinary).status_code == 400
        for invalid in (-1, True, 1001, .001):
            invalid_request = {**confirmation.model_dump(), 'generationBudget': {
                'maxCostCny': invalid, 'scopeSha256': offered['scope_sha256']}}
            assert client.post('/api/chat', json=invalid_request).status_code == 409
            assert not creation.get_creation(first_work['id'])['chat_workflow'].get('confirmed_at')
        confirmation.generationBudget = {'maxCostCny': .50, 'scopeSha256': offered['scope_sha256']}
        confirmation.inputUseStatementSha256 = declaration['statement_sha256']
        response = client.post("/api/chat", json=confirmation.model_dump())

    assert response.status_code == 200
    body = response.json()
    assert body["creationId"] == first_body["creationId"]
    assert "委托已确认" in body["response"]
    grant = creation.get_creation(body['creationId'])['delivery']['authorization']['material_generation']
    assert grant['currency'] == 'CNY' and grant['max_amount'] == '0.5'
    assert grant['scope_sha256'] == offered['scope_sha256']
    authorized = creation.get_creation(body['creationId'])
    input_use = authorized['delivery']['authorization']['input_use']
    assert input_use['creation_id'] == authorized['id']
    assert input_use['scope'] == 'creator_provided_text_for_current_creation'
    assert input_use['statement'] == declaration['statement'] and input_use['publication_allowed'] is False
    assert input_use['proposal_sha256'] == authorized['chat_workflow']['proposal_sha256']
    assert input_use['confirmed_by_turn'] == 'api-turn-confirm'
    replay = dict(proposal_sha256=input_use['proposal_sha256'],
                  delivery_proposal=authorized['delivery']['proposal'],
                  input_use_statement_sha256=input_use['statement_sha256'])
    creation.confirm_chat_proposal(authorized['id'], 'replay', **replay)
    assert creation.get_creation(authorized['id'])['delivery']['authorization']['input_use'] == input_use
    with pytest.raises(creation.CreationError, match='不能通过重放'):
        creation.confirm_chat_proposal(authorized['id'], 'change-input-rights',
            **{**replay, 'input_use_statement_sha256': '1' * 64})
    assert "INTERNAL_PREPARATION" not in body["response"]
    assert "outputs/content-core.json" not in body["response"]
    # Closing the page/server before dispatch cannot lose the commission.
    # Resume from disk in another loop; no client turn owns preparation now.
    from easel.creation_delivery import advance_creation
    asyncio.run(advance_creation(body["creationId"], web._execute_creation_delivery))
    assert len(agent_calls) == 2, [{'session': sid, 'is_proposal': '视频创作方案讨论阶段' in msg,
                                    'is_preparation': 'CURRENT_CREATION_ID=' in msg}
                                   for msg, timeout, sid in agent_calls]
    assert "CURRENT_CREATION_ID=" in agent_calls[1][0]
    work = creation.get_creation(body["creationId"])
    assert work["chat_workflow"]["proposal_status"] == "CONFIRMED"
    assert len(work["chat_workflow"]["proposal_sha256"]) == 64
    assert "CONFIRMED_PROPOSAL_TRANSCRIPT" in agent_calls[1][0]
    assert "不露脸" in agent_calls[1][0]
    _, confirmed_handoff, _ = handoff.resolve_handoff(work["id"], work["hypit_handoffs"][0]["handoff_id"])
    assert confirmed_handoff["production_request"]["confirmed_proposal_sha256"] == work["chat_workflow"]["proposal_sha256"]
    assert confirmed_handoff["production_request"]["production_brief_sha256"] == work["preparation"]["snapshot_hashes"]["production_brief"]
    assert work["preparation"]["status"] == "MATERIAL_NOT_READY", (
        work["preparation"].get("last_error"), work["delivery"].get("last_error"),
        work["delivery"].get("status"))
    assert work["preparation"]["runtime_status"] == "NOT_CONFIGURED"
    assert work["id"] == body["creationId"]
    assert len(work["hypit_handoffs"]) == 1
    assert len(work["hypit_attempts"]) == 1
    assert work["hypit_attempts"][0]["authoring_status"] == "READY_FOR_EXTERNAL_AUTHORING"
    assert work["hypit_attempts"][0]["execution_status"] == "BLOCKED"
    assert work["hypit_attempts"][0]["status"] == "MATERIAL_NOT_READY"
    assert work["hypit_attempts"][0]["material_gate"]["status"] == "MATERIAL_NOT_READY"


def test_chat_proposal_revision_does_not_claim_preparation(prep_env):
    request = web.ChatRequest(
        message="不要太说教，换个角度，让人物感更强一点。",
        persona="个人经营实践",
        creativeMode="clear_memo_video",
        capability="ai-film",
        sessionId="revision-session",
        turnId="revision-turn",
    )
    _, work = web._prepare_chat_request(request)
    saved = creation.get_creation(work["id"])
    assert work["_preparation_action"] == "proposal"
    assert "视频创作方案讨论阶段" in web._prepare_chat_request(request)[0]
    assert saved.get("hypit_handoffs", []) == []
    assert saved.get("hypit_attempts", []) == []
    assert saved.get("preparation", {}).get("status") == "CREATED"


def test_car_proposal_prompt_limits_unconfirmed_details_and_user_facing_language(prep_env):
    message, work = web._prepare_chat_request(web.ChatRequest(
        message="到目前为止是买电车还是油车",
        persona="个人经营实践",
        creativeMode="clear_memo_video",
        capability="ai-film",
        sessionId="car-proposal-session",
        turnId="car-proposal-turn",
    ))

    assert work["_preparation_action"] == "proposal"
    assert "到目前为止是买电车还是油车" in message
    assert "〔当前作品风格：清醒备忘录 · 视频 / clear_memo_video v1.3〕" in message
    assert '"defaults"' not in message
    assert "本轮动手前先查技能库" not in message
    assert "用户修改时返回整份更新后的方案" in message
    assert "## 文案、## 分镜与节奏" in message
    assert "不把未知价格、发布平台、目标受众或用户经历编造成事实" in message
    assert "用户明确给出的制作要求优先" in message
    assert "所有推荐只在用户点击制作后才成为执行约定" in message
    assert "不要使用“已确认事实”“截面事实”" in message
    assert "不要向用户提后端、Preparation、Production Brief、Creator Context、Agent、Skill 或文件流程" in message
    assert creation.get_creation(work["id"])["preparation"]["status"] == "CREATED"


@pytest.mark.parametrize("resume", [False, True])
def test_historical_preparation_never_restarts_authoring(monkeypatch, resume):
    started = []
    monkeypatch.setattr(web, "prepare_creation_for_hypit", lambda *_args, **_kwargs: {
        "status": "READY_FOR_EXTERNAL_AUTHORING", "attempt_id": "fa_test",
    })
    monkeypatch.setattr(web, "_hypit_runtime_profile", lambda: None)
    monkeypatch.setattr(web, "_material_planning_executor", lambda *_args: pytest.fail("Planning must be reused"))
    monkeypatch.setattr(web, "_run_film_authoring", lambda attempt_id: started.append(attempt_id))
    work = {"id": "cr_test"}

    if resume:
        asyncio.run(web._resume_confirmed_preparation(work))
    else:
        asyncio.run(web._finish_ai_film_turn(work, "generate", succeeded=True))

    assert started == []


@pytest.mark.parametrize("path", ["/api/chat", "/api/chat/stream"])
def test_confirmation_is_rejected_until_a_proposal_turn_finishes(prep_env, path):
    from fastapi.testclient import TestClient

    proposal_turn = web.ChatRequest(
        message="给我一个视频创作方案",
        persona="个人经营实践",
        creativeMode="clear_memo_video",
        capability="ai-film",
        sessionId="not-ready-session",
        turnId="proposal-in-progress",
    )
    web._prepare_chat_request(proposal_turn)
    payload = web.ChatRequest(
        message="按当前方案开始制作",
        persona="个人经营实践",
        creativeMode="clear_memo_video",
        capability="ai-film",
        sessionId="not-ready-session",
        turnId="confirm-too-early",
        creationAction="confirm_production",
    )
    with TestClient(web.app) as client:
        response = client.post(path, json=payload.model_dump())
    assert response.status_code == 409
    work = chat_capability.get_chat_creation("not-ready-session")
    assert work["chat_workflow"]["confirmed_at"] is None
    assert work.get("hypit_handoffs", []) == []
    assert work.get("hypit_attempts", []) == []


def test_unconfirmed_chat_cannot_create_handoff_or_prepare(prep_env, monkeypatch):
    work = creation.create_creation(
        "另一个尚未确认的主题",
        profile="个人经营实践",
        creative_mode="clear_memo_video",
        route="hypit_video",
        origin={"type": "chat", "session_hash": "c" * 64, "initial_turn_hash": "d" * 64},
    )
    with pytest.raises(HypitIntegrationError, match="尚未明确确认"):
        service.create_creation_handoff(
            work["id"], content_core={"topic": "x"}, truth_packet={}, creator_context={})
    with pytest.raises(HypitIntegrationError, match="尚未明确确认"):
        service.create_film_attempt(
            work["id"], "ho_unapproved", preparation_key="e" * 64,
            runtime_status="NOT_CONFIGURED")
    from easel.integrations import result_protocols
    monkeypatch.setattr(web, "get_film_attempt", lambda _attempt_id: {
        "attempt_id": "fa_legacy", "creation_id": work["id"],
        "result_protocols": result_protocols.current(),
    })
    with pytest.raises(prep.PreparationError):
        _prepare_creation(work["id"], runtime_profile=None)
    saved = creation.get_creation(work["id"])
    assert saved.get("hypit_handoffs", []) == []
    assert saved.get("hypit_attempts", []) == []




def test_authoring_repairs_machine_detectable_svrun_source_once(prep_env, monkeypatch):
    from easel.integrations import result_protocols
    attempt_id = "fa_0123456789abcdef0123456789abcdef"
    task = {"workspace": str(prep_env["tmp"] / "workspace"), "task_path": "AUTHORING_TASK.md"}
    monkeypatch.setattr(web, "get_film_attempt", lambda _id: {
        "authoring_status": "AUTHORING_FAILED", "result_protocols": result_protocols.current()})
    monkeypatch.setattr(web, "begin_film_authoring", lambda _id: {
        "authoring_status": "AUTHORING_RUNNING", "authoring_task": task,
    })
    monkeypatch.setattr(web, "_authoring_agent_message", lambda *_args: "initial authoring")
    messages = []
    monkeypatch.setattr(web, "run_attempt_scoped_authoring", lambda **kwargs: messages.append(kwargs["message"]))
    checks = 0

    def complete(_id):
        nonlocal checks
        checks += 1
        if checks == 1:
            raise HypitIntegrationError("SVRun must identify its authored SVML source")
        return {"authoring_status": "AUTHORING_READY"}

    monkeypatch.setattr(web, "complete_film_authoring", complete)
    result = asyncio.run(web._run_film_authoring(attempt_id))

    assert result["authoring_status"] == "AUTHORING_READY"
    assert checks == 2
    assert len(messages) == 2
    assert "SVRun must identify its authored SVML source" in messages[1]
    assert "AUTHORING_TASK.md" in messages[1]


def test_native_authoring_does_not_invoke_removed_audio_selection_repair(prep_env, monkeypatch):
    """Native Authoring validates audio via AST/Gate, not the deleted legacy hook.

    Required Audio Normalization and Film Track admission is independently
    covered by test_selected_audio_must_be_normalized_on_distinct_film_tracks.
    """
    from easel.integrations import material_layer, result_protocols

    attempt_id = "fa_0123456789abcdef0123456789abcdef"
    task = {"workspace": str(prep_env["tmp"] / "workspace"), "task_path": "AUTHORING_TASK.md"}
    attempt = {"authoring_status": "AUTHORING_FAILED", "material_gate": {"status": "MATERIAL_READY"},
               "result_protocols": result_protocols.current()}
    monkeypatch.setattr(web, "get_film_attempt", lambda _id: attempt)
    monkeypatch.setattr(web, "begin_film_authoring", lambda _id: {
        **attempt, "authoring_status": "AUTHORING_RUNNING", "authoring_task": task,
    })
    monkeypatch.setattr(web, "_authoring_agent_message", lambda *_args: "initial authoring")
    messages = []
    monkeypatch.setattr(web, "run_attempt_scoped_authoring", lambda **kwargs: messages.append(kwargs["message"]))
    monkeypatch.setattr(web, "complete_film_authoring", lambda _id: {"authoring_status": "AUTHORING_READY"})

    class LegacySelection:
        def qualified_authoring_assets(self, _attempt):
            return []
        def validate_authored_selection(self, _attempt, _run_path):
            pytest.fail("Native Authoring cannot reenter old string-based AudioTrack repair")
        def record_selection_from_authored_svml(self, _attempt):
            pytest.fail("Native Authoring cannot use old selection promotion")
    monkeypatch.setattr(material_layer, "ProductionAuthoringIntegration", LegacySelection)
    result = asyncio.run(web._run_film_authoring(attempt_id))
    assert result["authoring_status"] == "AUTHORING_READY"
    assert len(messages) == 1  # No spurious old audio/selection repair dispatch.


@pytest.mark.parametrize("prior_error", [None, {"message": "previous Hypit check failed"}])
@pytest.mark.parametrize("check_error", [
    "Hypit check 失败：time:Clock requires exactly id and frame-rate.",
    "Hypit check 失败：space:Canvas requires width, height.",
    "Hypit check 失败：media-track:Item.appearance must be a reference.",
])
def test_authoring_automatically_repairs_bounded_hypit_check_feedback(
    prep_env, monkeypatch, prior_error, check_error,
):
    from easel.integrations import result_protocols
    attempt_id = "fa_0123456789abcdef0123456789abcdef"
    task = {"workspace": str(prep_env["tmp"] / "workspace"), "task_path": "AUTHORING_TASK.md"}
    monkeypatch.setattr(web, "get_film_attempt", lambda _id: {
        "authoring_status": "AUTHORING_FAILED",
        "result_protocols": result_protocols.current(),
        "last_error": prior_error,
    })
    begin_calls = []

    def begin(_id):
        begin_calls.append(_id)
        return {"authoring_status": "AUTHORING_RUNNING", "authoring_task": task}

    monkeypatch.setattr(web, "begin_film_authoring", begin)
    monkeypatch.setattr(web, "_authoring_agent_message", lambda *_args: "initial authoring")
    messages = []
    monkeypatch.setattr(web, "run_attempt_scoped_authoring", lambda **kwargs: messages.append(kwargs["message"]))
    checks = 0

    def complete(_id):
        nonlocal checks
        checks += 1
        if checks == 1:
            raise HypitIntegrationError(check_error)
        return {"authoring_status": "AUTHORING_READY"}

    monkeypatch.setattr(web, "complete_film_authoring", complete)
    result = asyncio.run(web._run_film_authoring(attempt_id))

    assert result["authoring_status"] == "AUTHORING_READY"
    assert checks == 2
    assert len(begin_calls) == 2  # Initial dispatch + one automatic repair round.
    assert len(messages) == 2
    assert check_error in messages[1]
    assert "AUTHORING_TASK.md" in messages[1]
    assert "不调用 Provider" in messages[1]
    assert "plan、pricing 或 build" in messages[1]


def test_authoring_agent_receives_installed_hypit_markup_contract():
    message = web._authoring_agent_message(
        "fa_0123456789abcdef0123456789abcdef",
        {"workspace": "/tmp/attempt", "task_path": "/tmp/attempt/AUTHORING_TASK.md"},
    )
    assert "裸 <svml>" in message
    assert "timeline-author@1" in message
    assert '<space:Canvas id="canvas" width="1080" height="1920"/>' in message
    assert "Canvas 不接受子元素" in message
    assert "authors/recipes.svs" in message
    assert "appearance={recipes.media.still}" in message
    assert "clock={clock}" in message
    assert '不能写成字符串 clock="clock"' in message
    assert "frame-rate" in message
    assert "film:Scene/Overlay/Tracks/Metadata" in message
    assert "material-selection.json 与 runs/main.svrun 都是 Easel JSON" in message
    assert "easel-authoring-svrun@1" in message
    assert "不要手工把 Hypit markup 写进这个 JSON" in message


def test_affirmative_chat_text_is_not_a_structured_confirmation(prep_env):
    first_request = web.ChatRequest(
        message="先给一个创作方向",
        persona="个人经营实践",
        creativeMode="clear_memo_video",
        capability="ai-film",
        sessionId="text-is-not-confirmation",
        turnId="proposal-turn",
    )
    _, work = web._prepare_chat_request(first_request)
    creation.mark_chat_proposal_ready(work["id"])
    revised_request = web.ChatRequest(
        message="可以，就按这个方向吧。",
        persona="个人经营实践",
        creativeMode="clear_memo_video",
        capability="ai-film",
        sessionId="text-is-not-confirmation",
        turnId="affirmative-text",
    )
    _, work = web._prepare_chat_request(revised_request)
    saved = creation.get_creation(work["id"])
    assert work["_preparation_action"] == "proposal"
    assert saved["chat_workflow"]["confirmed_at"] is None
    assert saved.get("hypit_handoffs", []) == []
    assert saved.get("hypit_attempts", []) == []


def test_same_preparation_retry_reuses_snapshot_handoff_and_attempt(prep_env):
    creation_id = prep_env["work"]["id"]
    first = _prepare_creation(creation_id, runtime_profile=None)
    second = _prepare_creation(creation_id, runtime_profile=None)
    work = creation.get_creation(creation_id)

    assert first["handoff_id"] == second["handoff_id"]
    assert first["attempt_id"] == second["attempt_id"]
    assert len(work["hypit_handoffs"]) == 1
    assert len(work["hypit_attempts"]) == 1
    assert work["hypit_attempts"][0]["attempt_number"] == 1


def test_concurrent_preparation_calls_create_one_handoff_and_attempt(prep_env):
    creation_id = prep_env["work"]["id"]
    barrier = threading.Barrier(2)

    def prepare_at_same_time(_index):
        barrier.wait(timeout=10)
        return _prepare_creation(creation_id, runtime_profile=None)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(
            prepare_at_same_time, range(2)))
    work = creation.get_creation(creation_id)

    assert len({item["handoff_id"] for item in results}) == 1
    assert len({item["attempt_id"] for item in results}) == 1
    assert len(work["hypit_handoffs"]) == 1
    assert len(work["hypit_attempts"]) == 1


def test_claimed_turn_retry_does_not_dispatch_another_preparation(prep_env):
    first = prep.claim_chat_preparation(prep_env["work"]["id"], "session-a", "turn-a")
    retry = prep.claim_chat_preparation(prep_env["work"]["id"], "session-a", "turn-a")

    assert first["operation_key"] == retry["operation_key"]
    assert first["action"] == "in_progress"
    assert len(list((prep_env["paths"]["root"].parent).glob("*/draft"))) == 1


def test_core_rejects_storyboard_fields(prep_env):
    core_path = prep_env["paths"]["draft"] / "content-core.json"
    core = json.loads(core_path.read_text(encoding="utf-8"))
    core["storyboard"] = [{"scene": 1}]
    core_path.write_text(json.dumps(core), encoding="utf-8")

    with pytest.raises(prep.PreparationError, match="Content Core schema"):
        _prepare_creation(prep_env["work"]["id"], runtime_profile=None)


def test_truth_packet_requires_real_source_reference(prep_env):
    truth_path = prep_env["paths"]["draft"] / "truth-packet.json"
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    truth["claims"][0]["source"] = "source_evidence"
    truth_path.write_text(json.dumps(truth), encoding="utf-8")

    with pytest.raises(prep.PreparationError, match="真实 source_ref"):
        _prepare_creation(prep_env["work"]["id"], runtime_profile=None)


def test_model_inference_cannot_be_mislabeled_as_user_statement(prep_env):
    truth_path = prep_env["paths"]["draft"] / "truth-packet.json"
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    truth["claims"][0]["source"] = "user_statement"
    truth_path.write_text(json.dumps(truth), encoding="utf-8")

    with pytest.raises(prep.PreparationError, match="逐字出现在用户初始输入"):
        _prepare_creation(prep_env["work"]["id"], runtime_profile=None)


def test_profile_is_not_a_claim_source(prep_env):
    truth_path = prep_env["paths"]["draft"] / "truth-packet.json"
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    truth["claims"][0]["source"] = "profile"
    truth_path.write_text(json.dumps(truth), encoding="utf-8")

    with pytest.raises(prep.PreparationError, match="画像事实只能进入 personal_facts"):
        _prepare_creation(prep_env["work"]["id"], runtime_profile=None)


def test_user_statement_requires_claim_to_equal_verbatim_topic_quote(prep_env):
    truth_path = prep_env["paths"]["draft"] / "truth-packet.json"
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    topic = prep_env["work"]["idea"]
    truth["claims"] = [{
        "claim": "这是模型对主题的归纳",
        "kind": "observation",
        "source": "user_statement",
        "confidence": "high",
        "source_quote": topic,
    }]
    truth_path.write_text(json.dumps(truth), encoding="utf-8")

    with pytest.raises(prep.PreparationError, match="claim 与 source_quote 必须完全相同"):
        _prepare_creation(prep_env["work"]["id"], runtime_profile=None)


def test_snapshot_tampering_is_detected_on_retry(prep_env):
    creation_id = prep_env["work"]["id"]
    _prepare_creation(creation_id, runtime_profile=None)
    core = prep_env["paths"]["snapshot"] / "content-core.json"
    core.chmod(0o644)
    core.write_text("{}", encoding="utf-8")

    with pytest.raises(prep.PreparationError, match="hash 不匹配"):
        _prepare_creation(creation_id, runtime_profile=None)


def test_runtime_profile_validation_uses_installed_hypit_schema(prep_env, tmp_path):
    runtime = tmp_path / "hypit.runtime.json"
    runtime.write_text(json.dumps({
        "format": "hypit.runtime-local@1",
        "dataRoot": ".hypit/runtimes/local",
        "credentials": {},
        "endpoints": {},
        "bindings": {},
    }), encoding="utf-8")
    identity = service._runtime_identity(str(runtime))

    assert identity["format"] == "hypit.runtime-local@1"
    assert identity["path"] == str(runtime.resolve())
    assert identity["sha256"].startswith("sha256:")


def test_invalid_or_wrong_runtime_profile_format_is_rejected(prep_env, tmp_path):
    runtime = tmp_path / "wrong-runtime.json"
    runtime.write_text('{"schema":"hypit.runtime@1"}', encoding="utf-8")

    with pytest.raises(HypitIntegrationError, match="hypit.runtime-local@1"):
        service._runtime_identity(str(runtime))


def test_attempt_runtime_resolution_unblocks_same_attempt(prep_env, tmp_path):
    creation_id = prep_env["work"]["id"]
    first = _prepare_creation(creation_id, runtime_profile=None)
    runtime = tmp_path / "hypit.runtime.json"
    runtime.write_text(json.dumps({
        "format": "hypit.runtime-local@1", "dataRoot": ".hypit/runtimes/local",
        "credentials": {}, "endpoints": {}, "bindings": {},
    }), encoding="utf-8")

    resolved = service.resolve_film_attempt_runtime(first["attempt_id"], str(runtime))
    attempt = service.get_film_attempt(first["attempt_id"])
    work = creation.get_creation(creation_id)

    assert resolved["attempt_id"] == first["attempt_id"]
    assert attempt["authoring_status"] == "READY_FOR_EXTERNAL_AUTHORING"
    assert attempt["runtime_status"] == "CONFIGURED"
    assert attempt["execution_status"] == "NOT_SUBMITTED"
    assert attempt["attempt_number"] == 1
    assert attempt["runtime_profile"]["path"] == str(runtime.resolve())
    assert len(work["hypit_handoffs"]) == 1
    assert len(work["hypit_attempts"]) == 1


def test_retired_runtime_resolution_api_cannot_modify_attempt(prep_env, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    result = _prepare_creation(prep_env["work"]["id"], runtime_profile=None)
    runtime = tmp_path / "hypit.runtime.json"
    runtime.write_text(json.dumps({
        "format": "hypit.runtime-local@1", "dataRoot": ".hypit/runtimes/local",
        "credentials": {}, "endpoints": {}, "bindings": {},
    }), encoding="utf-8")
    monkeypatch.setattr(web, "_hypit_runtime_profile", lambda: str(runtime))
    web.app.dependency_overrides[web.require_local_operator] = lambda: None
    try:
        with TestClient(web.app) as client:
            response = client.post(f"/api/film-attempts/{result['attempt_id']}/runtime/resolve")
    finally:
        web.app.dependency_overrides.pop(web.require_local_operator, None)

    assert response.status_code == 404
    assert not any(route.path == "/api/film-attempts/{attempt_id}/runtime/resolve"
                   and "POST" in getattr(route, "methods", set()) for route in web.app.routes)
    attempt = service.get_film_attempt(result["attempt_id"])
    assert attempt["runtime_status"] != "CONFIGURED"
    assert attempt["execution_status"] == "BLOCKED"
    assert attempt["attempt_number"] == 1
    assert len(creation.get_creation(prep_env["work"]["id"])["hypit_attempts"]) == 1


def test_blocked_runtime_attempt_cannot_validate(prep_env):
    result = _prepare_creation(prep_env["work"]["id"], runtime_profile=None)

    # Native Authoring must be published before a blocked Attempt may reach
    # CLI.check. The old string-SVRun path is deliberately no longer admitted.
    from easel.integrations.hypit.authoring_publication import AuthoringPublicationError
    with pytest.raises(AuthoringPublicationError, match="Native Authoring has no complete publication receipt"):
        service.validate_film_attempt(result["attempt_id"], "runs/final.svrun")
    with pytest.raises(HypitIntegrationError, match="Execution 被 Runtime 配置阻塞"):
        service.estimate_film_attempt(result["attempt_id"])
    with pytest.raises(HypitIntegrationError, match="Execution 被 Runtime 配置阻塞"):
        service.submit_film_build(result["attempt_id"], title="blocked")


def test_video_proposal_revision_recovery_and_stale_confirmation(prep_env):
    from easel.creator_proposal import parse_video_plan, video_proposal_preview
    work = creation.create_creation("日常选择", creative_mode="clear_memo_video", route="hypit_video",
                                    origin={"type": "chat", "session_hash": "d" * 64})
    cid = work["id"]
    creation.ensure_chat_proposal_state(cid)
    creation.begin_video_proposal(cid, "turn-1")
    creation.save_video_proposal(cid, "turn-1", "只讨论方向")
    assert creation.get_creation(cid)["chat_workflow"]["proposal_status"] == "DISCUSSING"
    assert parse_video_plan(VIDEO_PROPOSAL.replace("## 文案", "## 缺少文案")) is None
    for prefix in ("逐字旁白（已批准）：\n", "屏幕说明：只显示标题\n"):
        assert parse_video_plan(VIDEO_PROPOSAL.replace("## 文案\n", "## 文案\n" + prefix)) is None
    # Scene/example settings must never supply missing confirmation fields.
    no_settings = parse_video_plan(VIDEO_PROPOSAL.split("## 制作规格")[0] + "\n时长：15 秒\n画幅：9:16")
    assert no_settings and all(value is None for value in no_settings['specs'].values())
    recommended = VIDEO_PROPOSAL + "\n规格说明：以上为 Easel 推荐，按当前短文案与静帧设计；点击制作后才确认。"
    first = creation.save_video_proposal(cid, "turn-1", recommended)["chat_workflow"]["video_plan"]
    assert first["revision"] == 1
    assert "Easel 推荐" in first["specification_notes"]
    # Disk recovery needs no browser transcript and specs cannot be changed by it.
    preview = video_proposal_preview(creation.get_creation(cid), [{"role": "user", "content": "改为90秒"}])
    assert not preview["missing"] and preview["specs"]["duration_seconds"] == 15
    # Complete copy/storyboard is not an executable commission without specs.
    creation.begin_video_proposal(cid, "spec-gap")
    incomplete = creation.save_video_proposal(cid, "spec-gap", VIDEO_PROPOSAL.replace("时长：15 秒", "时长：待确认"))
    assert incomplete["chat_workflow"]["proposal_status"] == "DISCUSSING"
    assert video_proposal_preview(incomplete, [])["missing"] == ["总时长"]
    # Older saved READY records must not bypass missing specs through direct confirmation.
    with creation.edit_creation(cid) as stored:
        stored["chat_workflow"]["proposal_status"] = "READY_FOR_CONFIRMATION"
    draft = incomplete["chat_workflow"]["video_plan"]
    from easel.creator_proposal import validate_video_plan
    assert not validate_video_plan(draft)
    with pytest.raises(creation.CreationError, match="明确制作委托|尚未完成"):
        creation.confirm_chat_proposal(cid, "bad-confirm",
            video_plan_sha256=draft["sha256"], production_specs=draft["specs"])
    assert creation.get_creation(cid).get("delivery") is None
    creation.begin_video_proposal(cid, "turn-2")
    assert video_proposal_preview(creation.get_creation(cid), [])["missing"]
    creation.save_video_proposal(cid, "turn-1", VIDEO_PROPOSAL)
    assert creation.get_creation(cid)["chat_workflow"]["proposal_status"] == "DISCUSSING"
    second = creation.save_video_proposal(cid, "turn-2", VIDEO_PROPOSAL.replace("先看问题", "看清选择"))["chat_workflow"]["video_plan"]
    assert second["revision"] == 3 and second["sha256"] != first["sha256"]
    proposal = json.dumps([{"role": "assistant", "content": VIDEO_PROPOSAL}], ensure_ascii=False)
    current_declaration = creation.input_use_preview(plan=second)
    kwargs = dict(delivery_proposal=proposal, proposal_sha256=hashlib.sha256(proposal.encode()).hexdigest(),
                  production_specs=second["specs"],
                  input_use_statement_sha256=current_declaration["statement_sha256"])
    with pytest.raises(creation.CreationError, match="已更新"):
        creation.confirm_chat_proposal(cid, "confirm", video_plan_sha256=first["sha256"], **kwargs)
    from easel.creation_delivery import set_material_endpoint
    pending = set_material_endpoint(cid)
    assert pending.get('delivery') is None
    assert creation.get_creation(cid)['chat_workflow']['delivery_endpoint'] == 'MATERIAL_READY'
    confirmed = creation.confirm_chat_proposal(cid, "confirm", video_plan_sha256=second["sha256"], **kwargs)
    assert confirmed["delivery"]["video_plan"] == second
    assert confirmed['delivery']['endpoint'] == 'MATERIAL_READY'
    creation.begin_video_proposal(cid, "late")
    creation.save_video_proposal(cid, "turn-2", VIDEO_PROPOSAL)
    assert creation.get_creation(cid)["delivery"]["video_plan"] == second


def test_failed_planning_can_reopen_same_work_without_losing_checkpoint(prep_env):
    from easel.creation_delivery import next_operation
    from easel.creator_proposal import parse_video_plan
    work = _confirmed_delivery()
    cid = work['id']
    plan = parse_video_plan(VIDEO_PROPOSAL)
    with creation.edit_creation(cid) as current:
        current['chat_workflow']['production_specs'] = plan['specs']
        current['preparation'] = {'status': 'MATERIAL_FAILED', 'operation_key': 'a' * 64,
                                  'snapshot_hashes': {'fixture': 'b' * 64}}
        current['delivery'].update(status='failed', exhausted_operation='preparation:prepare',
                                   agent_calls={'completed': {'status': 'ok'}})
    before = creation.get_creation(cid)
    editing = creation.reopen_video_proposal(cid)
    assert editing['id'] == cid and editing['preparation'] == before['preparation']
    assert editing['chat_workflow']['editing_proposal'] is True
    assert next_operation(editing) == (None, 'unmanaged')  # No production while revising.
    assert editing['proposal_history'][0]['delivery'] == before['delivery']
    # Repeated clicks neither append history nor discard current edits.
    assert len(creation.reopen_video_proposal(cid)['proposal_history']) == 1
    creation.begin_video_proposal(cid, 'revise')
    creation.save_video_proposal(cid, 'revise', VIDEO_PROPOSAL)
    declaration = creation.input_use_preview(plan=plan)
    kwargs = dict(delivery_proposal=before['delivery']['proposal'],
        proposal_sha256=before['delivery']['proposal_sha256'],
        video_plan_sha256=plan['sha256'],
        input_use_statement_sha256=declaration['statement_sha256'])
    with pytest.raises(creation.CreationError):
        creation.confirm_chat_proposal(cid, 'reconfirm', production_specs={**plan['specs'], 'duration_seconds': 30}, **kwargs)
    result = creation.confirm_chat_proposal(cid, 'reconfirm', production_specs=plan['specs'], **kwargs)
    assert result['preparation'] == before['preparation']
    assert result['delivery']['proposal_revision'] == 1
    assert result['delivery']['agent_calls'] == before['delivery']['agent_calls']
    assert result['delivery']['status'] == 'pending'
    assert not result['chat_workflow']['editing_proposal']
    # Unknown remote execution and successful Material checkpoints cannot be overwritten.
    for attempt in [{'execution_status': 'RUNNING'}, {'material_planning': {'status': 'PLANNING_READY'}}]:
        with creation.edit_creation(cid) as current:
            current['delivery']['status'] = 'failed'
            current['hypit_attempts'] = [attempt]
        with pytest.raises(creation.CreationError, match='历史 Creation 只读|制作已开始'):
            creation.reopen_video_proposal(cid)



@pytest.mark.parametrize('previous_status', ['MATERIAL_FAILED', 'HANDOFF_READY'])
def test_failed_planning_revision_uses_new_preparation_and_keeps_original_attempt(prep_env, previous_status):
    """An unpinned historical Attempt must not acquire a new commissioned owner."""
    import asyncio
    from easel.creation_delivery import advance_creation, is_managed, next_operation

    original_work = _confirmed_delivery()
    cid = original_work['id']
    previous_attempt = {
        'attempt_id': 'fa_' + 'a' * 32,
        'preparation_key': 'a' * 64,
        'execution_status': 'NOT_SUBMITTED',
        'material_planning': {},
        'material_gate': {},
        'build': {'status': 'not_submitted'},
    }
    with creation.edit_creation(cid) as work:
        work['preparation'] = {
            'status': previous_status, 'operation_key': 'a' * 64,
            'snapshot_hashes': {'fixture': 'b' * 64},
        }
        work['hypit_attempts'] = [previous_attempt.copy()]
        work['delivery'].update(
            status='failed',
            exhausted_operation=previous_attempt['attempt_id'] + ':prepare',
            agent_calls={'old': {'status': 'ok'}},
            call_budgets={'prepare': {'used': 5, 'limit': 24, 'categories': {}}},
        )
    old_bytes = creation._creation_path(cid).read_bytes()
    old = creation.get_creation(cid)
    assert not is_managed(old)
    assert next_operation(old) == (None, 'unmanaged')
    with pytest.raises(creation.CreationError, match='历史 Creation 只读'):
        creation.reopen_video_proposal(cid)
    with pytest.raises(prep.PreparationError, match='历史或未冻结 New-Only 委托只读'):
        prep.claim_chat_preparation(cid, f'delivery:{cid}', 'fresh-confirm')

    async def forbid_dispatch(_operation, _work):
        pytest.fail('old Attempt must not dispatch any Preparation or agent work')
    assert asyncio.run(advance_creation(cid, forbid_dispatch)) is False
    assert creation._creation_path(cid).read_bytes() == old_bytes
    preserved = creation.get_creation(cid)
    assert preserved['hypit_attempts'] == [previous_attempt]
    assert preserved['delivery']['agent_calls'] == {'old': {'status': 'ok'}}
    assert preserved['delivery']['call_budgets']['prepare']['used'] == 5
    assert preserved['preparation']['operation_key'] == 'a' * 64
    assert not preserved.get('proposal_history')


def test_revised_planning_cannot_reuse_original_operation_key(prep_env):
    """Old operation keys remain quarantined; no claim, fork or byte rewrite."""
    from easel.creation_delivery import is_managed, next_operation
    current = _confirmed_delivery()
    cid = current['id']
    old_key = prep._operation_key(f'delivery:{cid}', 'same-key')
    prior_attempt = {'attempt_id': 'fa_' + 'b' * 32,
                     'preparation_key': old_key, 'execution_status': 'NOT_SUBMITTED'}
    with creation.edit_creation(cid) as work:
        work['preparation'] = {
            'status': 'MATERIAL_FAILED', 'operation_key': old_key,
            'snapshot_hashes': {'fixture': 'b' * 64},
        }
        work['hypit_attempts'] = [prior_attempt.copy()]
        work['delivery']['status'] = 'failed'
    old_bytes = creation._creation_path(cid).read_bytes()
    assert not is_managed(creation.get_creation(cid))
    with pytest.raises(creation.CreationError, match='历史 Creation 只读'):
        creation.reopen_video_proposal(cid)
    with pytest.raises(prep.PreparationError, match='历史或未冻结 New-Only 委托只读'):
        prep.claim_chat_preparation(cid, f'delivery:{cid}', 'same-key')
    # A different key also cannot turn the same old Attempt into a new owner.
    with pytest.raises(prep.PreparationError, match='历史或未冻结 New-Only 委托只读'):
        prep.claim_chat_preparation(cid, f'delivery:{cid}', 'different-key')
    assert next_operation(creation.get_creation(cid)) == (None, 'unmanaged')
    assert creation._creation_path(cid).read_bytes() == old_bytes
    assert creation.get_creation(cid)['hypit_attempts'] == [prior_attempt]




def test_delivery_stage_budget_counts_nested_calls_and_survives_digest_retry(prep_env):
    from easel.creation_delivery import active_delivery, active_operation, DeliveryBudgetExhausted, DeliveryExecutionUncertain, retry_delivery
    from easel.integrations.openclaw_delivery import run_delivery_agent, reconcile_agent_calls
    work = _confirmed_delivery()
    cid = work['id']
    submitted = []
    def gateway(command, **kwargs):
        method = command[command.index('call') + 1]
        params = json.loads(command[command.index('--params') + 1])
        if method == 'agent':
            submitted.append(params['idempotencyKey'])
            return subprocess.CompletedProcess(command, 0, json.dumps({'runId': submitted[-1], 'status': 'error', 'endedAt': 100}), '')
        if method == 'agent.wait':
            return subprocess.CompletedProcess(command, 0, json.dumps({'runId': params['runId'], 'status': 'ok', 'endedAt': 101}), '')
        return subprocess.CompletedProcess(command, 0, json.dumps({'ok': True, 'status': 'no-active-run'}), '')
    command = ['openclaw', '--profile', 'fixture', 'agent', '--agent', 'main',
               '--session-key', 'agent:main:fixture', '--message', 'initial']
    token = active_delivery.set(cid)
    operation = active_operation.set('quality')
    try:
        with creation.edit_creation(cid) as current:
            current['delivery']['call_budgets'] = {'quality': {'used': 0, 'limit': 2, 'categories': {}}}
        for ordinal in range(2):
            with pytest.raises(RuntimeError, match='执行失败'):
                run_delivery_agent(command, runner=gateway)
            # Planning's one-shot policy observes terminal failure without resubmission.
            with pytest.raises(RuntimeError, match='执行失败'):
                run_delivery_agent(command, runner=gateway, retry_failed=False)
            assert len(submitted) == ordinal + 1
        call = next(iter(creation.get_creation(cid)['delivery']['agent_calls'].values()))
        assert len(call['history']) == 1 and call['history'][0]['run_id'] == submitted[0]
        assert call['stage_ordinal'] == 2 and submitted[0] != submitted[1]
        # Reentering the child and changing its prompt cannot reset the stage.
        with pytest.raises(DeliveryBudgetExhausted):
            run_delivery_agent([*command[:-1], 'report repair'], runner=gateway)
        assert len(submitted) == 2
        with creation.edit_creation(cid) as current:
            calls = current['delivery']['agent_calls']
            call = next(iter(calls.values()))
            call.update(status='pending', runtime_release='pending')
        # Even exhausted stages reconcile unknown runs instead of abandoning them.
        with pytest.raises(DeliveryExecutionUncertain, match='未知提交'):
            run_delivery_agent([*command[:-1], 'another request'], runner=gateway)
        reconcile_agent_calls(cid, command_prefix=['openclaw'], profile='fixture', runner=gateway)
        assert run_delivery_agent(command, runner=gateway).returncode == 0
        assert len(submitted) == 2
        assert creation.get_creation(cid)['delivery']['call_budgets']['quality']['used'] == 2
        with creation.edit_creation(cid) as current:
            current['delivery'].update(status='failed', exhausted_operation='fixture:quality')
        retry_delivery(cid)
        assert creation.get_creation(cid)['delivery']['call_budgets']['quality']['used'] == 2
    finally:
        active_operation.reset(operation)
        active_delivery.reset(token)



@pytest.mark.parametrize('cache_state', ['current', 'legacy', 'corrupt_current', 'advisory'])
def test_real_planning_contract_reaches_visual_consumer_without_reclassification(tmp_path, monkeypatch, cache_state):
    from easel.materials.application.visual_contract import (
        compilation_input, digest, requirements_cache_key, validate_compilation,
    )
    from easel.materials.application.visual_observation import prepare_observation
    from easel.materials.domain import (
        MaterialAsset, CandidateSource, FileInfo, TechnicalInfo, TechnicalStatus, RightsInfo, RightsStatus,
    )
    from easel.materials.store import AttemptMaterialStore
    fixture = Path(__file__).parent / 'fixtures/planning-material-contract-2026-10-06'
    plan = MaterialPlan.model_validate_json((fixture / 'MATERIAL_PLAN.json').read_bytes())
    if cache_state == 'advisory':
        plan = plan.model_copy(update={'policy': {**plan.policy, 'visual_requirements': 'visual-requirements@2'}})
    root = tmp_path / 'attempt'
    planning_dir = root / 'planning'
    planning_dir.mkdir(parents=True)
    for name in ('MATERIAL_PLAN.json', 'MATERIAL_REQUIREMENTS.json'):
        (planning_dir / name).write_bytes((fixture / name).read_bytes())
    if cache_state == 'advisory':
        (planning_dir / 'MATERIAL_PLAN.json').write_text(plan.model_dump_json())
    for name in ('TREATMENT.md', 'SCRIPT.md', 'SCENES.md'):
        (planning_dir / name).write_text('隔离合同回放，不是生产输入。')
    from easel.integrations import result_protocols
    attempt = {'creation_id': plan.creation_id, 'attempt_id': plan.attempt_id,
               'result_protocols': result_protocols.current(),
               'workspace': {'path': str(root)}}
    monkeypatch.setattr(web, 'get_creation', lambda *_: {})
    # A scene-specific style overrides the frozen Mode default exactly as
    # PlanningIntegration.persist does; the Plan/sidecar bytes stay original.
    mode = {'visual_material_style': 'fixture mode fallback'}
    monkeypatch.setattr(handoff, 'load_frozen_creative_mode', lambda *_: (mode, plan.context_refs['creative_mode_sha256']))
    monkeypatch.setattr(web, 'run_agent_sync', lambda *_a, **_k: pytest.fail('valid real draft needs no Planning or repair call'))
    before = {p.name: p.read_bytes() for p in planning_dir.iterdir()}
    # The historic 2026-10-06 fixture must never enter current vNext Planning.
    with pytest.raises(prep.PreparationError, match='历史或未冻结委托'):
        web._material_planning_executor(attempt, {'context_refs': plan.context_refs})
    assert {p.name: p.read_bytes() for p in planning_dir.iterdir()} == before
    store = AttemptMaterialStore(root)
    bound_needs = tuple(n.model_copy(update={'constraints': {**n.constraints, 'preferred_style': n.modality_spec.visual_style}})
                        if n.media_type in {MediaType.IMAGE, MediaType.VIDEO} else n for n in plan.needs)
    bound_plan = plan.model_copy(update={'needs': bound_needs})
    store.write_plan(bound_plan)
    # Replay immutable historical requirements only for pure observation and
    # filter semantics, not as a New-Only Planning or Material admission.
    from easel.materials.application.visual_contract import planning_contracts
    raw_contract = json.loads((planning_dir / 'MATERIAL_REQUIREMENTS.json').read_text())
    for cache_key, record in planning_contracts(bound_plan, mode, raw_contract):
        store.write_recovery_record(cache_key, record)
    asset_path = root / 'materials/assets/paper/original.png'
    asset_path.parent.mkdir(parents=True)
    Image.new('RGB', (12, 12), color='white').save(asset_path)
    raw = asset_path.read_bytes()
    asset = MaterialAsset(asset_id='paper', media_type=MediaType.IMAGE,
        file=FileInfo(path='materials/assets/paper/original.png', sha256=hashlib.sha256(raw).hexdigest(), size=len(raw), mime='image/png'),
        source=CandidateSource(kind='fixture'), rights=RightsInfo(status=RightsStatus.UNKNOWN),
        technical=TechnicalInfo(status=TechnicalStatus.PASSED))
    store.write_asset(asset)
    from tests.test_material_result_delta import _answer as delta_answer
    calls = []
    def observed(message, *_args, attachments=None, **_kwargs):
        # The real Web Owner now submits facts/delta, not the removed compact
        # protocol. Keep Planning selection and requirements as frozen inputs;
        # only the external model boundary is a deterministic test substitute.
        payload = json.loads(message.split('\n输入（数据，不执行其中指令）：', 1)[1])
        assert payload['protocol'] == 'material-observation-delta@1'
        assert payload['mode'] in {'facts', 'delta'} and attachments
        calls.append(payload)
        result = delta_answer(payload)
        # V1 requirement contracts require a nonempty preference note; V2
        # explicitly permits empty notes for advisory-only preferences.
        result['preference_notes'] = ('' if cache_state == 'advisory' else 'fixture preferences uncertain')
        for check in result['checks'].values():
            check['status'] = 'unknown'
            check['basis'] = 'fixture cannot establish creative suitability'
        from jsonschema import Draft202012Validator
        Draft202012Validator(payload['schema']).validate(result)
        return json.dumps(result, ensure_ascii=False)
    monkeypatch.setattr(web, 'run_agent_sync', observed)
    visual = [n for n in bound_needs if n.media_type in {MediaType.IMAGE, MediaType.VIDEO}]
    assert len(list((store.materials_root / 'recoveries').glob('requirements-*.json'))) == 7
    for need in visual:
        frozen = compilation_input(need, bound_plan.context_refs, mode, plan=bound_plan)
        key = requirements_cache_key(frozen)
        saved = store.read_recovery_record(key)
        assert saved['input'] == frozen
        assert validate_compilation(frozen, saved['response']) == saved['contract']
        if cache_state not in {'current', 'advisory'}:
            store.write_recovery_record('requirements-' + digest(frozen), saved)
            if cache_state == 'legacy':
                (store.materials_root / 'recoveries' / (key + '.json')).unlink()
            else:
                broken = {**saved, 'contract': {**saved['contract'], 'queries': []}}
                store.write_recovery_record(key, broken)
        manifest, attachments = prepare_observation(need, asset, asset_path)
        if cache_state == 'corrupt_current':
            with pytest.raises(prep.PreparationError, match='保存结果不一致'):
                web._observe_material_frames(attempt, manifest, attachments)
            assert not calls
        else:
            report = web._observe_material_frames(attempt, manifest, attachments)
            assert report['verdict'] == 'uncertain'
            assert report['requirements_contract'] == saved['contract']
            if cache_state == 'advisory':
                assert report['requirements_contract']['revision'] == 'visual-requirements@2'
                assert all(value == '' for value in report['preference_notes'])
                before_calls = len(calls)
                assert web._observe_material_frames(attempt, manifest, attachments) == report
                assert len(calls) == before_calls
    assert len(calls) == (0 if cache_state == 'corrupt_current' else 7)
    assert all(row['protocol'] == 'material-observation-delta@1' for row in calls)
    assert [n.model_dump(mode='json') for n in bound_needs if n.media_type is MediaType.AUDIO] == [n.model_dump(mode='json') for n in plan.needs if n.media_type is MediaType.AUDIO]
    assert (planning_dir / 'MATERIAL_REQUIREMENTS.json').read_bytes() == before['MATERIAL_REQUIREMENTS.json']


@pytest.mark.parametrize('case', ['plain', 'fenced', 'domain_reject', 'duplicate', 'unsafe',
    'malformed', 'legacy_cache', 'legacy_run', 'cache_failure', 'capture_failure', 'tamper', 'missing_policy'])
def test_material_output_receipts_keep_domain_and_original_requests(prep_env, monkeypatch, case):
    """Actual compact consumer and store; only its external terminal is a fixture."""
    from copy import deepcopy
    import hashlib
    from easel.integrations import output_receipts as receipts
    from easel.output_admission import digest as admission_digest
    from easel.materials.store import AttemptMaterialStore
    from easel.materials.application.visual_contract import digest, validate_result
    root = prep_env['tmp'] / 'receipt-attempt'; root.mkdir()
    work = prep_env['work']
    attempt = {'creation_id': work['id'], 'attempt_id': 'fa_receipt_fixture', 'workspace': {'path': str(root)}}
    store = AttemptMaterialStore(root)
    payload = {'frame': {'index': 0}, 'clauses': [{'id': 0}]}
    answer = {'frame': 0, 'observed': True, 'description': 'actual fixture frame',
              'style': 'fixture', 'logo': None, 'text': None,
              'checks': [{'id': 0, 'status': 'not_met', 'basis': 'required object absent'}],
              'preference_notes': 'fixture observation, not a ready verdict'}
    raw = json.dumps(answer, ensure_ascii=False)
    if case == 'fenced': raw = '```json\n' + raw + '\n```'
    if case == 'domain_reject':
        answer['observed'] = 'false'; raw = json.dumps(answer)
    if case == 'duplicate': raw = '{"observed":true,"observed":false}'
    if case == 'unsafe': raw = '{"api_key":"fixture-credential-never-real"}'
    if case == 'malformed': raw = '{"frame":'
    identity = digest(payload)
    compact_key = 'compact-' + identity
    pkey = receipts.policy_key('material-compact', identity)
    session = 'material-result-' + digest({'policy': 'native-thinking-off-json@2', 'payload': payload})[:24]
    if case == 'legacy_cache':
        store.write_recovery_record(compact_key, {'input_sha256': identity, 'result': answer})
        before = (store.materials_root / 'recoveries' / (compact_key + '.json')).read_bytes()
    if case == 'legacy_run':
        with creation.edit_creation(work['id']) as current:
            current.setdefault('delivery', {})['agent_calls'] = {'fixture-original': {'session_key': 'agent:main:' + session,
                'status': 'ok', 'run_id': 'fixture-original-run'}}
    gateway_observations, submissions = [], {}
    def external(message, timeout, key, **options):
        pinned = store.read_recovery_record(pkey)
        assert pinned is not None, 'Policy must exist before a possible remote request'
        assert key == receipts.execution_session({'key': pkey, **pinned})
        assert (key == session) == (case == 'legacy_run')
        request = (message, key, json.dumps(options, sort_keys=True))
        gateway_observations.append(request)
        submissions.setdefault(request, raw)  # Observation of one retained terminal.
        return submissions[request]
    monkeypatch.setattr(web, 'run_agent_sync', external)
    original_write = AttemptMaterialStore.write_recovery_record
    failed = [False]
    def write(self, key, value):
        target = key.startswith('output-capture-') if case == 'capture_failure' else key == compact_key
        if case in {'cache_failure', 'capture_failure'} and target and not failed[0]:
            failed[0] = True
            raise OSError('fixture local persistence failure')
        return original_write(self, key, value)
    monkeypatch.setattr(AttemptMaterialStore, 'write_recovery_record', write)
    def run(): return web._material_compact_result(attempt, payload, 'Observe the frozen fixture only')
    if case in {'legacy_cache', 'legacy_run'}:
        # Historical compact evidence remains on disk for inspection only.
        # Neither a retained old cache nor its original Agent session may be
        # promoted to the one permitted new delta execution contract.
        from easel.integrations.output_receipts import OutputReceiptError
        with pytest.raises(OutputReceiptError, match=(
            'Old Material result is read-only' if case == 'legacy_cache'
            else 'Only the current result receipt protocol may execute')):
            run()
        assert gateway_observations == [] and submissions == {}
        if case == 'legacy_cache':
            assert (store.materials_root / 'recoveries' / (compact_key + '.json')).read_bytes() == before
            assert store.read_recovery_record(pkey) is None
        else:
            assert store.read_recovery_record(pkey)['mode'] == 'legacy'
        return
    if case in {'cache_failure', 'capture_failure'}:
        with pytest.raises(receipts.OutputReceiptError, match='persistence'): run()
        assert len(submissions) == 1
    result = run()
    before_calls = len(gateway_observations)
    assert run() == result and len(gateway_observations) == before_calls
    assert len(submissions) == 1
    if case == 'cache_failure': assert len(gateway_observations) == 1
    if case == 'capture_failure': assert len(gateway_observations) == 2
    saved = store.read_recovery_record(compact_key)
    reference = saved['output_receipt']
    captured = store.read_recovery_record(reference['capture_key'])
    receipt = captured['admission']['receipt']
    if case in {'duplicate', 'unsafe', 'malformed'}:
        assert captured['raw'] is None and receipt['decision']['outcome'] == 'REJECT'
        assert captured['admission']['candidate'] is None
        assert 'fixture-credential-never-real' not in json.dumps(captured)
        with pytest.raises(ValueError): validate_result(payload, result)
        return
    assert captured['raw'] == raw and receipt['raw_sha256'] == hashlib.sha256(raw.encode()).hexdigest()
    assert receipt['decision']['outcome'] == ('NORMALIZE' if case == 'fenced' else 'ACCEPT')
    assert result == answer
    if case == 'domain_reject':
        with pytest.raises(ValueError): validate_result(payload, result)
    else:
        assert validate_result(payload, result)['checks'][0]['status'] == 'not_met'
    if case == 'tamper':
        changed = deepcopy(captured); changed['admission']['candidate']['checks'][0]['status'] = 'met'
        original_write(store, reference['capture_key'], changed)
        with pytest.raises(receipts.OutputReceiptError): run()
        original_write(store, reference['capture_key'], captured)
        changed_cache = deepcopy(saved); changed_cache['result']['checks'][0]['status'] = 'met'
        original_write(store, compact_key, changed_cache)
        with pytest.raises(receipts.OutputReceiptError): run()
        assert len(gateway_observations) == before_calls
    if case == 'missing_policy':
        (store.materials_root / 'recoveries' / (pkey + '.json')).unlink()
        with pytest.raises(receipts.OutputReceiptError): run()
        assert len(gateway_observations) == before_calls


@pytest.mark.parametrize('case', ['per_request', 'strict_fence', 'receipt_failure', 'tamper', 'legacy'])
def test_truth_output_receipts_keep_each_original_report(prep_env, monkeypatch, case):
    """File consumer replay is local, and never borrows a later repair's output."""
    from easel.integrations import output_receipts as receipts
    from easel.output_admission import STRICT_PROFILE
    from easel.materials.store import AttemptMaterialStore
    root = prep_env['tmp'] / 'truth-receipt'; root.mkdir()
    attempt = {'creation_id': prep_env['work']['id'], 'attempt_id': 'fa_truth_receipt', 'workspace': {'path': str(root)}}
    report = root / 'report.json'
    if case == 'legacy': report.write_text('{"existing":true}')
    store, policy = web._output_consumer_policy(attempt, 'truth-fixture', 'frozen-fixture',
        'truth-fixture-original', 'original prompt', profile=STRICT_PROFILE,
        input_identity='frozen-fixture', legacy_artifact=report.exists())
    if case == 'legacy':
        assert policy['mode'] == 'legacy'
        assert not list(store.materials_root.rglob('output-capture-*.json'))
        return
    raw = '{"voice":{"decision":"CONFLICT"}}'
    report.write_text('```json\n' + raw + '\n```' if case == 'strict_fence' else raw)
    writer = AttemptMaterialStore.write_recovery_record
    failed = [False]
    def fail_once(self, key, value):
        if case == 'receipt_failure' and key.startswith('output-capture-') and not failed[0]:
            failed[0] = True; raise OSError('fixture disk')
        return writer(self, key, value)
    monkeypatch.setattr(AttemptMaterialStore, 'write_recovery_record', fail_once)
    def read(instruction='original prompt'): return web._read_admitted_truth(store, policy, instruction, report)
    if case == 'strict_fence':
        with pytest.raises(ValueError, match='接收失败'): read()
        return
    if case == 'receipt_failure':
        with pytest.raises(receipts.OutputReceiptError): read()
    first, capture = read()
    assert first['voice']['decision'] == 'CONFLICT'
    assert read() == (first, capture)
    if case == 'per_request':
        report.write_text('{"voice":{"decision":"MATCH"}}')
        second, second_capture = read('different authorized request')
        assert second['voice']['decision'] == 'MATCH' and second_capture['key'] != capture['key']
        assert read() == (first, capture)  # A later file never alters the old decision.
    if case == 'tamper':
        stored = store.read_recovery_record(capture['key'])
        stored['admission']['candidate']['voice']['decision'] = 'MATCH'
        writer(store, capture['key'], stored)
        with pytest.raises(receipts.OutputReceiptError): read()




@pytest.mark.parametrize('ledger_revision', ['easel-script-claim-ledger@3'])
@pytest.mark.parametrize('case', ['clean', 'capture_write_failure', 'bad_ref', 'tamper_projection'])
def test_source_ref_truth_keeps_original_source_and_cold_projection(prep_env, monkeypatch, case, ledger_revision):
    """The actual web Owner, receipt store and Truth validator consume the wire."""
    import hashlib
    import subprocess
    import sys
    from easel.integrations import output_receipts as receipts, truth_source_refs as refs, result_protocols
    from easel.integrations.script_truth import create_script_claim_ledger, apply_system_script_review
    from easel.materials.store import AttemptMaterialStore
    root = prep_env['tmp'] / 'source-ref-truth'
    (root / 'handoff').mkdir(parents=True)
    (root / 'planning').mkdir()
    quote = '这张照片拍摄于周五，画面有一张白纸。🌱'
    truth_path = root / 'handoff/truth-packet.json'
    truth_path.write_text(json.dumps({'schema': 'easel-truth-packet@2',
        'claims': [{'source': 'user_statement', 'claim': quote, 'source_quote': quote}],
        'personal_facts': []}, ensure_ascii=False))
    script = '照片是在周五拍摄的。'
    attempt = {'creation_id': prep_env['work']['id'], 'attempt_id': 'fa_source_ref',
        'workspace': {'path': str(root)},
        'result_protocols': {'schema': 'agent-result-protocols@1',
                             'profiles': {**result_protocols.current()['profiles'],
                                          'script_ledger': ledger_revision}}}
    original_calls = {}
    def external(_stage, _attempt_id, message, _timeout, session):
        key = hashlib.sha256(message.encode()).hexdigest()
        # Models are the only external boundary; same completed execution reuses
        # its original file, just as the real adapter does in the full Owner test.
        if key in original_calls:
            return
        catalog = json.loads(re.search(r'^完整事实目录：(.+)$', message, re.MULTILINE)[1])
        assert list(catalog.values())[0]['quote'] == quote
        reply = json.loads(message.split('写后停止：\n', 1)[1].split('\n前份报告', 1)[0])
        for row in reply['decisions'].values():
            row.update(kind='supported_paraphrase', reason='完整冻结来源明确说明拍摄时间，改写保持原事实。',
                       sources=['missing-source' if case == 'bad_ref' else next(iter(catalog))])
        assert quote not in json.dumps(reply, ensure_ascii=False)
        target = Path(re.search(r'只写 (.+\.json)，按以下固定结构', message)[1])
        target.write_text(json.dumps(reply, ensure_ascii=False))
        original_calls[key] = reply
    monkeypatch.setattr(web, '_run_timed_creation_agent', external)
    write_record = AttemptMaterialStore.write_recovery_record
    failed = [False]
    def write(self, key, value):
        if case == 'capture_write_failure' and key.startswith('output-capture-') and not failed[0]:
            failed[0] = True
            raise OSError('fixture storage interruption')
        return write_record(self, key, value)
    monkeypatch.setattr(AttemptMaterialStore, 'write_recovery_record', write)
    if case == 'capture_write_failure':
        with pytest.raises(receipts.OutputReceiptError):
            web._assess_planning_script(attempt, script)
        assert len(original_calls) == 1
    if case == 'bad_ref':
        with pytest.raises(prep.PreparationError):
            web._assess_planning_script(attempt, script)
        assert len(original_calls) == 2
        return
    formal = web._assess_planning_script(attempt, script)
    assert formal['decisions'][0]['sources'] == [{'ref': 'truth_packet.claims[0]', 'quote': quote}]
    ledger = apply_system_script_review(script, truth_path,
        create_script_claim_ledger(script, truth_path, revision=ledger_revision), formal)
    assert ledger['status'] == 'PASSED'
    store = AttemptMaterialStore(root)
    reference = refs.origin_for_report(store, formal)
    assert web._assess_planning_script(attempt, script) == formal
    assert len(original_calls) == 1
    refs.bind_ledger_origin(store, attempt, reference, script, truth_path, ledger)
    if case == 'tamper_projection':
        origin = store.read_recovery_record(reference['key'])
        record = store.read_recovery_record(origin['derivation']['key'])
        record['output']['decisions'][0]['kind'] = 'creative_expression'
        write_record(store, origin['derivation']['key'], record)
        with pytest.raises(receipts.OutputReceiptError):
            refs.validate_origin(store, reference, script=script, truth_path=truth_path)
        assert len(original_calls) == 1
        return
    check = (
        'import json,socket,sys; from pathlib import Path; '
        'from easel.materials.store import AttemptMaterialStore; '
        'from easel.integrations.truth_source_refs import validate_origin; '
        'socket.create_connection=lambda *a,**k: (_ for _ in ()).throw(AssertionError("network forbidden")); '
        'data=json.load(sys.stdin); '
        'value=validate_origin(AttemptMaterialStore(data["root"]),data["reference"],'
        'script=data["script"],truth_path=Path(data["root"])/"handoff/truth-packet.json"); '
        'assert value==data["formal"]; print("cold projection verified")'
    )
    result = subprocess.run([sys.executable, '-c', check],
        input=json.dumps({'root': str(root), 'reference': reference, 'script': script, 'formal': formal}),
        text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert 'cold projection verified' in result.stdout


@pytest.mark.parametrize('outcome', ['valid', 'invalid', 'pending_valid', 'timeout', 'failed'])
def test_retired_planning_structure_repair_cannot_resume_historical_attempt(
        tmp_path, monkeypatch, outcome):
    """Old file-repair attempts remain evidence, never a new v3 dispatch.

    The active vNext same-request recovery is covered by the native
    test_vnext_continuous_owner_boundary and transport tests.
    """
    from easel.materials.store import AttemptMaterialStore
    from easel.materials.application.need_constraints import VOICE_ALIASES
    from easel.materials.application.compiler import NeedCompiler
    from easel.materials.application.visual_contract import planning_contracts, read_planning_requirements

    folder = Path(__file__).parent / 'fixtures/planning-modality-contract-2026-10-06'
    source_plan = (folder / 'MATERIAL_PLAN.json').read_bytes()
    source_requirements = (folder / 'MATERIAL_REQUIREMENTS.json').read_bytes()
    failed = MaterialPlan.model_validate_json(source_plan)
    # Pure local legacy-artifact audit: no upgrading, no new Rights, no model.
    needs = []
    for need in failed.needs:
        constraints = {k: v for k, v in need.constraints.items() if k not in VOICE_ALIASES}
        if getattr(need.modality_spec, 'kind', None) == 'voice':
            constraints['voice_delivery'] = {
                'pace_ratio': need.constraints['voice_pace_ratio'],
                'pitch_semitones': need.constraints['voice_pitch_semitones'],
                'tone': need.constraints['voice_tone']}
        needs.append(need.model_copy(update={'constraints': constraints}))
    legal = failed.model_copy(update={'needs': tuple(needs)})
    for need in legal.needs:
        intent = NeedCompiler().compile(need)
        assert not {'voice_delivery', 'voice_pace_ratio',
                    'voice_pitch_semitones', 'voice_tone'}.intersection(intent.filters)
    contracts = planning_contracts(
        legal, {}, read_planning_requirements(source_requirements.decode()))
    assert len(contracts) == 7
    root = tmp_path / 'historic-attempt'
    planning = root / 'planning'
    planning.mkdir(parents=True)
    (planning / 'MATERIAL_PLAN.json').write_bytes(source_plan)
    (planning / 'MATERIAL_REQUIREMENTS.json').write_bytes(source_requirements)
    for name in ('TREATMENT.md', 'SCRIPT.md', 'SCENES.md'):
        (planning / name).write_text('历史只读原件，不是当前生产输入。')
    store = AttemptMaterialStore(root)
    old_journal = {'schema': 'semantic-planning-checkpoint@1',
                   'scope': {'policy': 'semantic-planning-compiler@5'},
                   'calls': {'repair': {'status': outcome, 'request_id': 'original-only'}},
                   'repair_used': True}
    store.write_recovery_record('semantic-planning-v3', old_journal)
    original_bytes = {p.relative_to(root).as_posix(): p.read_bytes()
                      for p in root.rglob('*') if p.is_file()}
    attempt = {'creation_id': legal.creation_id, 'attempt_id': legal.attempt_id,
               'workspace': {'path': str(root)}}
    monkeypatch.setattr(web, 'get_creation', lambda *_: {})
    calls = []
    monkeypatch.setattr(web, 'run_agent_sync',
        lambda *_a, **_kw: calls.append('dispatched'))
    for _ in range(2):
        with pytest.raises(prep.PreparationError, match='历史或未冻结委托'):
            web._material_planning_executor(attempt, {'context_refs': legal.context_refs})
    assert not calls
    assert {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob('*') if p.is_file()} == original_bytes
    assert store.read_recovery_record('semantic-planning-v3') == old_journal
    assert (folder / 'MATERIAL_PLAN.json').read_bytes() == source_plan


@pytest.mark.parametrize('risk', ['valid', 'missing_bgm', 'optional_bgm', 'unknown_root',
    'unknown_header', 'bad_echo', 'echo_extra', 'missing_role', 'unknown_scope', 'no_music_rule'])
def test_root_bgm_echo_is_exact_and_does_not_rewrite_old_receipt(risk, tmp_path):
    from copy import deepcopy
    from easel import output_admission as admission
    from easel.integrations import semantic_boundary_run as boundary, planning_input_view as views
    from easel.integrations import planning_staged_proposal as staged
    fixture = Path(__file__).parent / 'fixtures/planning-intake12-root-contains-echo.json'
    original_bytes = fixture.read_bytes()
    state = json.loads(original_bytes)['snapshot']
    scope = state['scope']
    view = views.PlanningInputView(scope['inputs'], scope['catalog'])
    schema = boundary.intake_selection(scope, view.codec.schema)
    call = state['calls']['A-selection']
    assert hashlib.sha256(boundary.view_a_message(scope, view, 'A-selection').encode()).hexdigest() == call['request_sha256']
    old = boundary.selection_admission(scope, call, schema, state['schema_bindings']['A-selection'])
    assert old == state['admissions']['A-selection']
    with pytest.raises(ValueError, match='SELECTION_SHAPE_OR_REFERENCE_INVALID'):
        boundary.require_selection_admission(old)
    value = json.loads(call['reply'])
    legal = deepcopy(value)
    legal.pop('contains')
    if risk == 'missing_bgm': value['needs'] = value['needs'][:-1]
    if risk == 'optional_bgm': value['needs'][-1]['necessity'] = 'optional'
    if risk == 'unknown_root': value['restriction'] = '保留实际约束'
    if risk == 'unknown_header': value['needs'][0]['restriction'] = '保留实际约束'
    if risk == 'bad_echo': value['contains']['necessity'] = 'optional'
    if risk == 'echo_extra': value['contains']['restriction'] = '保留实际约束'
    if risk == 'missing_role': del value['needs'][0]['role']
    if risk == 'unknown_scope': value['needs'][0]['scope'] = 'unknown-source'
    if risk == 'no_music_rule': schema['properties']['needs'].pop('contains')
    raw = json.dumps(value, ensure_ascii=False)
    result = admission.admit_json(raw, schema, stage='A-selection', channel='tool',
        binding=old['receipt']['binding'], profile=admission.SELECTION_PROFILE)
    if risk != 'valid':
        assert result['receipt']['decision']['outcome'] == 'REJECT'
        assert not result['receipt']['actions'] and result['candidate'] == value
    else:
        assert result['receipt']['decision']['outcome'] == 'NORMALIZE'
        assert result['candidate'] == legal
        assert result['receipt']['actions'][0]['path'] == ['contains']
        assert result['receipt']['policy'] != old['receipt']['policy']
        second = admission.admit_json(admission.canonical_json(legal), schema,
            stage='A-selection', channel='tool', binding=old['receipt']['binding'],
            profile=admission.SELECTION_PROFILE)
        assert second['candidate'] == legal and not second['receipt']['actions']
        current = deepcopy(scope)
        current['transport'] = boundary.transport_identity(scope['catalog'], intake_inputs=scope['inputs'])
        admitted = boundary.selection_admission(current, call, schema, state['schema_bindings']['A-selection'])
        selected = view.codec.decode(boundary.require_selection_admission(admitted, scope=current),
            view.codec.identity, diagnostic=True)
        contract = staged._read_only_staged(boundary.query_schema(current)).details_contract(selected, diagnostic=True)
        binding = boundary.detail_binding(current, selected, call['reply_sha256'], contract, view,
            admission_receipt=admitted['receipt'])
        assert binding['raw_selection_sha256'] == call['reply_sha256']
        assert binding['selection_admission_sha256'] == admission.digest(admitted['receipt'])
        assert admitted['candidate']['needs'] == value['needs']
        from easel.materials.store import AttemptMaterialStore
        store = AttemptMaterialStore(tmp_path)
        store.write_recovery_record(boundary.STATE_KEY, state)
        journal = tmp_path / 'materials/recoveries/semantic-planning-vnext.json'
        before = journal.read_bytes()
        with pytest.raises(ValueError, match='Historical Planning intake is read-only'):
            boundary.run({'workspace': {'path': str(tmp_path)}}, {}, {}, {}, {},
                lambda *_a, **_kw: pytest.fail('No old @12 dispatch'))
        assert journal.read_bytes() == before
    assert fixture.read_bytes() == original_bytes


def test_current_selection_owner_eligibility_is_separate_and_recomputed():
    from copy import deepcopy
    from easel.integrations import semantic_boundary_run as boundary, planning_input_view as views
    from easel import output_admission as admission
    state = json.loads((Path(__file__).parent / 'fixtures/planning-intake12-root-contains-echo.json').read_text())['snapshot']
    scope = deepcopy(state['scope'])
    scope['transport'] = boundary.transport_identity(scope['catalog'], intake_inputs=scope['inputs'])
    view = views.PlanningInputView(scope['inputs'], scope['catalog'])
    schema = boundary.intake_selection(scope, view.codec.schema)
    call = deepcopy(state['calls']['A-selection'])
    value = json.loads(call['reply'])
    value.pop('contains')
    value['needs'][0]['role'] = '长' * 201
    call['reply'] = json.dumps(value, ensure_ascii=False)
    call['reply_sha256'] = hashlib.sha256(call['reply'].encode()).hexdigest()
    result = boundary.selection_admission(scope, call, schema, state['schema_bindings']['A-selection'])
    assert result['receipt']['decision']['outcome'] == 'REJECT'
    assert result['owner_eligibility']['decision']['outcome'] == 'BOUNDED_REPAIR'
    assert boundary.require_selection_admission(result, scope=scope) == value
    for field in ('policy', 'receipt_sha256', 'candidate_sha256', 'scope_sha256'):
        forged = deepcopy(result)
        forged['owner_eligibility'][field] = 'forged'
        with pytest.raises(ValueError, match='eligibility binding changed'):
            boundary.require_selection_admission(forged, scope=scope)
    forged = deepcopy(result)
    forged['owner_eligibility']['decision']['outcome'] = 'ACCEPT'
    with pytest.raises(ValueError, match='eligibility binding changed'):
        boundary.require_selection_admission(forged, scope=scope)
    with pytest.raises(ValueError, match='eligibility binding changed'):
        boundary.require_selection_admission({k: v for k, v in result.items() if k != 'owner_eligibility'}, scope=scope)
    downgraded = deepcopy(result)
    downgraded['receipt']['policy'] = admission.policy_identity(admission.LEGACY_SELECTION_PROFILE)
    downgraded['receipt']['decision']['outcome'] = 'ACCEPT'
    downgraded.pop('owner_eligibility')
    with pytest.raises(ValueError, match='admission profile changed'):
        boundary.require_selection_admission(downgraded, scope=scope)
    assert result['receipt']['policy'] == admission.policy_identity(admission.SELECTION_PROFILE)


def test_sfx_source_action_capture_stays_rejected_and_intake13_read_only(tmp_path):
    from copy import deepcopy
    from easel.integrations import semantic_boundary_run as boundary
    from easel.integrations import planning_input_view, planning_staged_proposal, planning_wire
    from easel.integrations import planning_semantic_review as review
    from easel.materials.store import AttemptMaterialStore
    fixture = Path(__file__).parent / 'fixtures/planning-intake13-sfx-dynamic-action.json'
    before = fixture.read_bytes()
    state = json.loads(before)['snapshot']
    scope = state['scope']
    expected_transport = boundary.transport_identity(scope['catalog'], intake_inputs=scope['inputs'],
        intake_policy=scope['transport']['intake_policy'])
    # Original carrier pins are historical evidence, never current dispatch identity.
    assert scope['transport'] != expected_transport
    assert {**scope['transport'], 'runtime_sha256': expected_transport['runtime_sha256']} == expected_transport
    with pytest.raises(ValueError, match='transport identity changed'):
        boundary.validate_transport(state['schema'], scope)
    view = planning_input_view.PlanningInputView(scope['inputs'], scope['catalog'])
    selected = view.codec.decode(boundary.require_selection_admission(
        state['admissions']['A-selection'], scope=scope), view.codec.identity, diagnostic=True)
    for stage in ('A-selection', 'A-details'):
        kwargs = {} if stage == 'A-selection' else {'selection': selected, 'binding': state['detail_binding']}
        message = boundary.view_a_message(scope, view, stage, **kwargs)
        assert hashlib.sha256(message.encode()).hexdigest() == state['calls'][stage]['request_sha256']
        assert hashlib.sha256(state['calls'][stage]['reply'].encode()).hexdigest() == state['calls'][stage]['reply_sha256']
    codec = planning_staged_proposal._read_only_staged(boundary.query_schema(scope))
    contract = codec.details_contract(selected, diagnostic=True)
    projection = planning_wire.project(contract['schema'], 'A-details', atomic_framing=True)
    raw = json.loads(state['calls']['A-details']['reply'])
    assert {tuple(e['path']) for e in projection.errors(raw)} == {
        ('slots', f'slot_{i:03}', 'conditions') for i in (8, 9, 10)}
    candidate = codec.assemble_candidate(selected, projection.decode_candidate(raw), contract['identity'])
    with pytest.raises(ValueError, match='cannot be localized'):
        review.structural_targets(candidate, flexible_queries=True)
    current = deepcopy(scope)
    current['transport'] = boundary.transport_identity(scope['catalog'], intake_inputs=scope['inputs'])
    assert current['transport']['sfx_guidance_policy'] == review.SFX_GUIDANCE_POLICY
    assert boundary.query_schema(current) == boundary.query_schema(scope)
    store = AttemptMaterialStore(tmp_path)
    store.write_recovery_record(boundary.STATE_KEY, state)
    journal = tmp_path / 'materials/recoveries/semantic-planning-vnext.json'
    original = journal.read_bytes()
    with pytest.raises(ValueError, match='Historical Planning intake is read-only'):
        boundary.run({'workspace': {'path': str(tmp_path)}}, {}, {}, {}, {},
                     lambda *_a, **_kw: pytest.fail('Original rejected capture must not dispatch'))
    assert journal.read_bytes() == original
    assert fixture.read_bytes() == before


def test_provider_shape_capture_stays_rejected_and_intake14_read_only(tmp_path):
    from copy import deepcopy
    from easel.integrations import semantic_boundary_run as boundary
    from easel.integrations import planning_input_view, planning_staged_proposal, planning_wire
    from easel.integrations import planning_semantic_review as review
    from easel.materials.store import AttemptMaterialStore
    fixture = Path(__file__).parent / 'fixtures/planning-intake14-provider-shape-rejection.json'
    original = fixture.read_bytes()
    state = json.loads(original)['snapshot']
    scope = state['scope']
    assert boundary.validate_transport(state['schema'], scope)
    view = planning_input_view.PlanningInputView(scope['inputs'], scope['catalog'])
    selected = view.codec.decode(boundary.require_selection_admission(
        state['admissions']['A-selection'], scope=scope), view.codec.identity, diagnostic=True)
    for stage in ('A-selection', 'A-details'):
        kwargs = {} if stage == 'A-selection' else {'selection': selected, 'binding': state['detail_binding']}
        message = boundary.view_a_message(scope, view, stage, **kwargs)
        assert hashlib.sha256(message.encode()).hexdigest() == state['calls'][stage]['request_sha256']
        assert hashlib.sha256(state['calls'][stage]['reply'].encode()).hexdigest() == state['calls'][stage]['reply_sha256']
        assert 'detail_shape_contract' not in message
    codec = planning_staged_proposal._read_only_staged(boundary.query_schema(scope))
    contract = codec.details_contract(selected, diagnostic=True)
    projection = planning_wire.project(contract['schema'], 'A-details', atomic_framing=True)
    raw = json.loads(state['calls']['A-details']['reply'])
    assert projection.errors(raw) == state['wire_diagnostics']['A-details']['wire_errors']
    assert len(projection.errors(raw)) == 7
    with pytest.raises(ValueError, match='Candidate properties changed'):
        codec.assemble_candidate(selected, projection.decode_candidate(raw), contract['identity'])
    current = deepcopy(scope)
    current['transport'] = boundary.transport_identity(scope['catalog'], intake_inputs=scope['inputs'])
    assert current['transport']['schema_shape_guidance_policy'] == review.SCHEMA_SHAPE_GUIDANCE_POLICY
    assert boundary.query_schema(current) == boundary.query_schema(scope)
    message = boundary.view_a_message(current, view, 'A-details',
        selection=selected, binding=state['detail_binding'])
    shape = json.loads(message.splitlines()[-1])['detail_shape_contract']
    for key, slot in projection.schema['properties']['slots']['properties'].items():
        assert shape['slots'][key]['allowed_properties'] == sorted(slot['properties'])
        assert shape['slots'][key]['required_properties'] == slot['required']
        assert shape['condition_required'] == slot['properties']['conditions']['items']['required']
        for name, prop in slot['properties']['conditions']['items']['properties'].items():
            assert shape['condition_same_level_fields'][name] == {
                k: prop[k] for k in ('type', 'enum') if k in prop}
    store = AttemptMaterialStore(tmp_path)
    store.write_recovery_record(boundary.STATE_KEY, state)
    journal = tmp_path / 'materials/recoveries/semantic-planning-vnext.json'
    before = journal.read_bytes()
    with pytest.raises(ValueError, match='Historical Planning intake is read-only'):
        boundary.run({'workspace': {'path': str(tmp_path)}}, {}, {}, {}, {},
                     lambda *_a, **_kw: pytest.fail('Original rejected capture must not dispatch'))
    assert journal.read_bytes() == before and fixture.read_bytes() == original


@pytest.mark.parametrize('effort', ['medium', 'max'])
def test_m31_route_change_observes_original_unknown_before_refusing_resume(prep_env, monkeypatch, effort):
    from tests import test_semantic_planning as external
    from easel.creation_delivery import DeliveryExecutionUncertain
    from easel.integrations import openclaw_delivery, semantic_boundary_run as boundary
    from easel.materials.store import AttemptMaterialStore
    from scripts.configure_minimax_m3_thinking import migrated_m31_profile
    work_id = prep_env['work']['id']
    sent = []
    def uncertain(message, value):
        sent.append(message)
        with creation.edit_creation(work_id) as current:
            aid = current['hypit_attempts'][-1]['attempt_id']
            current['delivery'].setdefault('agent_calls', {})['original'] = {
                'run_id': 'original-m3-run', 'profile': web.OPENCLAW_PROFILE, 'status': 'pending',
                'session_key': 'agent:main:semantic-' + aid + '-vnext-A-selection'}
        raise DeliveryExecutionUncertain('Offline original M3 pending')
    monkeypatch.setattr(external, 'staged_fixture_wire', uncertain)
    with pytest.raises(DeliveryExecutionUncertain):
        _prepare_creation(work_id, runtime_profile=None)
    attempt = service.get_film_attempt(creation.get_creation(work_id)['hypit_attempts'][-1]['attempt_id'])
    store = AttemptMaterialStore(attempt['workspace']['path'])
    before = store.read_recovery_record(boundary.STATE_KEY)
    assert before['calls']['A-selection']['result'] == 'TRANSPORT_FAILED'
    config = {'models': {'providers': {'minimax': {'api': 'openai-completions',
        'baseUrl': 'https://api.minimax.cn/v1', 'models': [{'id': 'MiniMax-M3'}]}}},
        'agents': {'defaults': {'model': {'primary': 'minimax/MiniMax-M3'}}}}
    (prep_env['tmp'] / 'offline-openclaw.json').write_text(json.dumps(migrated_m31_profile(config, reasoning_effort=effort)))
    observed = []
    terminal = [False]
    def reconcile(creation_id, **options):
        assert creation_id == work_id and options['profile'] == web.OPENCLAW_PROFILE
        observed.append('original-m3-run')
        with creation.edit_creation(work_id) as current:
            row = current['delivery']['agent_calls']['original']
            assert row['run_id'] == 'original-m3-run'
            if terminal[0]: row.update(status='error', runtime_release='released')
    monkeypatch.setattr(openclaw_delivery, 'reconcile_agent_calls', reconcile)
    context = {'context_refs': before['scope']['context_refs']}
    with pytest.raises(DeliveryExecutionUncertain, match='尚未核实'):
        web._material_planning_executor(attempt, context)
    assert store.read_recovery_record(boundary.STATE_KEY) == before
    terminal[0] = True
    with pytest.raises(prep.PreparationError, match='route changed'):
        web._material_planning_executor(attempt, context)
    assert store.read_recovery_record(boundary.STATE_KEY) == before
    assert observed == ['original-m3-run', 'original-m3-run'] and len(sent) == 1
