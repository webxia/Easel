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


VIDEO_PROPOSAL = """## 创作表达
从日常选择的变化切入，不把结论当成普遍规律。不露脸。
## 文案
先看问题，再做决定。
## 分镜与节奏
0–15 秒：桌面笔记，呈现屏幕文案「先看问题，再做决定。」。
## 声音设计
无旁白，无音乐。
## 制作规格
时长：15 秒
画幅：9:16
音轨：静音
语言：简体中文
"""


def _confirmed_delivery():
    work = creation.create_creation("隔离测试主题", creative_mode="clear_memo_video", route="hypit_video",
                                    origin={"type": "chat", "session_hash": "c" * 64})
    creation.mark_chat_proposal_ready(work["id"])
    proposal = '[{"role":"user","content":"已确认的隔离测试方案"}]'
    return creation.confirm_chat_proposal(work["id"], "confirm", delivery_proposal=proposal,
                                          proposal_sha256=hashlib.sha256(proposal.encode()).hexdigest())


def test_delivery_excludes_legacy_and_serializes_cancellation_and_restarts(prep_env):
    from easel.creation_delivery import advance_creation, enrolled_creation_ids

    legacy = prep_env["work"]
    before = creation._creation_path(legacy["id"]).read_bytes()
    work = _confirmed_delivery()
    assert enrolled_creation_ids() == [work["id"]]
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
    creation.confirm_chat_proposal(legacy["id"], "retry", delivery_proposal="ignored")
    assert "delivery" not in creation.get_creation(legacy["id"])
    # New authorization cannot be retrofitted by replaying either an old
    # confirmation or a managed commission that omitted the declaration.
    declaration = creation.input_use_preview()['statement_sha256']
    for current in (creation.get_creation(legacy['id']), creation.get_creation(work['id'])):
        original = creation._creation_path(current['id']).read_bytes()
        with pytest.raises(creation.CreationError, match='不能通过重放'):
            creation.confirm_chat_proposal(current['id'], 'add-input-rights',
                delivery_proposal=current.get('delivery', {}).get('proposal', 'ignored'),
                input_use_statement_sha256=declaration)
        assert creation._creation_path(current['id']).read_bytes() == original


def test_delivery_replay_uses_checkpoints_and_reconciles_uncertain_submission(prep_env):
    from easel.creation_delivery import advance_creation, next_operation, DeliveryExecutionUncertain

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
                attempt['review'] = {'system': {'schema': 'easel-output-quality@5', 'status': 'READY',
                    'binding': {'output_name': 'final.video', 'sha256': 'fixture-only'}}}
            else:
                pytest.fail(operation)
        if operation == "submit":
            raise TimeoutError("提交响应丢失")

    # New event loop/dispatcher for every operation models a process restart;
    # no in-memory task registry participates in deciding what runs next.
    for _ in range(20):
        asyncio.run(advance_creation(work["id"], execute))
        if calls[-1:] == ["refresh"] and calls.count("refresh") == 1:
            saved = creation.get_creation(work["id"])
            assert saved["delivery"]["status"] == "observation_failed"
            assert saved["hypit_attempts"][-1]["execution_status"] == "SUBMITTED"
        if next_operation(creation.get_creation(work["id"])) == (None, "first_cut_ready"):
            break
    assert calls == ["prepare", "observe_material", "observe_material", 'recover_material', 'observe_material', "author", "author", "runtime", "validate", "price", "approve_free",
                     "submit", "reconcile", "reconcile", "refresh", "refresh", "export", "quality"]
    assert creation.get_creation(work["id"])["delivery"]["status"] == "first_cut_ready"
    snapshot = creation.get_creation(work['id'])
    system = snapshot['hypit_attempts'][-1]['review']['system']
    system['schema'] = 'easel-output-quality@3'
    assert next_operation(snapshot) == ('quality', 'checking_quality')
    system['schema'] = 'easel-output-quality@5'
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
    asyncio.run(advance_creation(work["id"], failure))
    assert len(calls) == 4
    assert creation.get_creation(work["id"])["delivery"]["status"] == "commission_invalid"
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

    work = _confirmed_delivery()
    source_id = "fa_" + "1" * 32
    with creation.edit_creation(work["id"]) as current:
        current["hypit_attempts"] = [{"attempt_id": source_id, "execution_status": "BUILD_FAILED"}]
    calls = []

    def fork_failed(source):
        calls.append(source)
        with creation.edit_creation(work["id"]) as current:
            assert current["delivery"]["recovering_build_from"] == source
            target = next((item for item in current["hypit_attempts"]
                           if item.get("retry_source", {}).get("attempt_id") == source), None)
            if target is None:
                target = {"attempt_id": f"fa_{len(current['hypit_attempts']) + 1:032x}",
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
    work = _confirmed_delivery()
    def failed_output(identity):
        return {'attempt_id': identity, 'execution_status': 'BUILD_COMPLETE',
            'outputs': {'final': {'sha256': 'output-sha'}}, 'review': {'human': {'status': 'pending'}, 'system': {
                'schema': 'easel-output-quality@5', 'status': 'REPAIR_REQUIRED',
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
    from easel.creation_delivery import active_delivery, DeliveryExecutionUncertain
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
        if method == "agent":
            run_id = params["idempotencyKey"]
            saved = creation.get_creation(work["id"])["delivery"]["agent_calls"]
            assert next(iter(saved.values()))["run_id"] == run_id
            assert params["deliver"] is False
            assert params["attachments"] == attachments
            raise subprocess.TimeoutExpired(command, 20)
        assert method == "agent.wait" and params == {"runId": run_id, "timeoutMs": 0}
        result = {"runId": run_id, "status": "ok" if terminal else "timeout"}
        if terminal:
            result["endedAt"] = 1000
        return subprocess.CompletedProcess(command, 0, json.dumps(result), "")

    command = ["openclaw", "--profile", "fixture", "agent", "--agent", "main",
               "--session-key", "fixture-session", "--message", "只写隔离准备文件"]
    attachments = [{"type": "image", "mimeType": "image/jpeg", "fileName": "frame-0.jpg", "content": "ZmFrZQ=="}]
    token = active_delivery.set(work["id"])
    try:
        with pytest.raises(DeliveryExecutionUncertain):
            run_delivery_agent(command, runner=gateway, attachments=attachments)
        with pytest.raises(DeliveryExecutionUncertain, match="另一网关"):
            reconcile_agent_calls(work["id"], command_prefix=["openclaw"], profile="different", runner=gateway)
        with pytest.raises(DeliveryExecutionUncertain, match="另一项执行"):
            reconcile_agent_calls(work["id"], command_prefix=["openclaw"], profile="fixture",
                runner=lambda command, **_: subprocess.CompletedProcess(command, 0,
                    json.dumps({"runId": "unrelated", "status": "ok", "endedAt": 1000}), ""))
        reconcile_agent_calls(work["id"], command_prefix=["openclaw"], profile="fixture", runner=gateway)
        with pytest.raises(DeliveryExecutionUncertain):
            run_delivery_agent(command, runner=gateway, attachments=attachments)
        terminal = True
        reconcile_agent_calls(work["id"], command_prefix=["openclaw"], profile="fixture", runner=gateway)
        assert run_delivery_agent(command, runner=gateway, attachments=attachments).returncode == 0
        assert calls == ["agent", "agent.wait", "agent.wait", "agent.wait"]
        stored = next(iter(creation.get_creation(work["id"])["delivery"]["agent_calls"].values()))
        assert stored["status"] == "ok" and "message" not in stored and "attachments" not in stored
    finally:
        active_delivery.reset(token)


def test_delivery_authoring_keeps_live_stage_and_recovers_completed_files(prep_env):
    from easel.creation_delivery import advance_creation
    from easel.integrations.openclaw_delivery import reconcile_agent_calls
    from easel.integrations.openclaw_authoring import (
        run_attempt_scoped_authoring, release_delivery_authoring, retained_authoring_message,
    )
    from tests.test_openclaw_authoring_boundary import _seed_attempt, ATTEMPT_ID

    work = _confirmed_delivery()
    source = _seed_attempt(prep_env["tmp"] / "durable-authoring")
    parent = prep_env["tmp"] / "isolated" / "authoring-staging"
    with creation.edit_creation(work["id"]) as current:
        current["hypit_attempts"] = [{"attempt_id": ATTEMPT_ID,
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
        original_message = f"Author only in {source}"
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
    asyncio.run(advance_creation(work["id"], execute))
    assert calls.count("agent") == 1 and calls.count("delete") == 1
    assert (source / "productions/easel-authoring/authors/main.svml").read_text() == "<svml/>"
    assert not staged.exists()
    saved = creation.get_creation(work["id"])
    assert saved["hypit_attempts"][-1]["authoring_status"] == "AUTHORING_READY"
    assert saved["delivery"]["authoring_stages"] == {}


@pytest.fixture
def prep_env(tmp_path, monkeypatch):
    from easel.runtime_config import EaselRuntimeConfig
    from easel.integrations import material_supply
    from easel.materials.providers import LocalProvider, ProviderRegistry

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
    creation.mark_chat_proposal_ready(work["id"])
    creation.confirm_chat_proposal(work["id"], "fixture-confirmation")
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
    return {"plan": plan, "context_refs": context["context_refs"],
            "treatment": "Treatment", "script": "假设脚本内容。", "scenes": "Scenes"}


def _prepare_creation(creation_id, **kwargs):
    kwargs.setdefault("planning_executor", _test_planning_executor)
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
    result = _prepare_creation(prep_env["work"]["id"], runtime_profile=None)

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


def test_script_truth_operator_api_is_protected_hash_bound_and_resumes(prep_env, monkeypatch):
    from fastapi.testclient import TestClient

    def unclassified_planning(attempt, context):
        result = _test_planning_executor(attempt, context)
        result["script"] = "画面：桌面上放着笔记本。\n这家公司成立于 2012 年。"
        return result

    result = _prepare_creation(
        prep_env["work"]["id"], runtime_profile=None, planning_executor=unclassified_planning,
    )
    assert result["status"] == "SCRIPT_TRUTH_REVIEW_REQUIRED"
    attempt = service.get_film_attempt(result["attempt_id"])
    workspace = Path(attempt["workspace"]["path"])
    ledger = json.loads((workspace / "planning" / "script-claims.json").read_text(encoding="utf-8"))
    monkeypatch.setattr(web, "prepare_creation_for_hypit", lambda *_args, **_kwargs: {
        "status": "READY_FOR_EXTERNAL_AUTHORING", "attempt_id": result["attempt_id"],
    })
    authoring_starts = []
    monkeypatch.setattr(web, "_start_film_authoring", lambda attempt_id: authoring_starts.append(attempt_id))
    web.app.dependency_overrides[web.require_local_operator] = lambda: None
    try:
        with TestClient(web.app) as client:
            status = client.get(f"/api/film-attempts/{result['attempt_id']}/script-truth")
            assert status.status_code == 200
            stale = client.post(
                f"/api/film-attempts/{result['attempt_id']}/script-truth/review",
                json={
                    "scriptSha256": "0" * 64,
                    "truthPacketSha256": ledger["truth_packet_sha256"],
                    "confirmAllClaimsReviewed": True,
                },
            )
            accepted = client.post(
                f"/api/film-attempts/{result['attempt_id']}/script-truth/review",
                json={
                    "scriptSha256": ledger["script_sha256"],
                    "truthPacketSha256": ledger["truth_packet_sha256"],
                    "confirmAllClaimsReviewed": True,
                    "reviewer": "codex_delegate",
                },
            )
    finally:
        web.app.dependency_overrides.pop(web.require_local_operator, None)

    assert stale.status_code == 400
    assert accepted.status_code == 200
    assert accepted.json()["script_truth"]["claims"][0]["status"] == "AUTO_REVIEWED"
    assert accepted.json()["script_truth"]["claims"][1]["status"] == "DELEGATE_REVIEWED"
    assert accepted.json()["script_truth"]["claims"][1]["review"]["reviewer"] == "codex_delegate"
    assert accepted.json()["preparation"]["status"] == "READY_FOR_EXTERNAL_AUTHORING"
    assert authoring_starts == [result["attempt_id"]]


@pytest.mark.parametrize("repair_succeeds", [True, False])
def test_managed_planning_repairs_own_claim_then_supplies_without_human_truth_review(prep_env, monkeypatch, repair_succeeds):
    from easel.creation_delivery import DeliveryExecutionUncertain
    from easel.integrations.material_layer import PlanningIntegration
    from easel.integrations.material_supply import ProductMaterialSupply

    work = _confirmed_delivery()
    claimed = prep.claim_chat_preparation(work["id"], f"delivery:{work['id']}", work["delivery"]["confirmed_by_turn"])
    write_drafts(work, prep.preparation_paths(work["id"], claimed["operation_key"])["draft"])
    calls = []
    root = None

    def agent(message, *_args):
        nonlocal root
        if message.startswith("〔Easel Material Creative Planning V1〕"):
            calls.append("plan")
            root = Path(re.search(r"^Attempt workspace: (.+)$", message, re.MULTILINE)[1])
            attempt_id = re.search(r"^Attempt ID: (.+)$", message, re.MULTILINE)[1]
            refs = json.loads(re.search(r"^context_refs: (.+)$", message, re.MULTILINE)[1])
            planning = _test_planning_executor({"attempt_id": attempt_id, "creation_id": work["id"]},
                                               {"context_refs": refs})
            for name, value in {"MATERIAL_PLAN.json": planning["plan"].model_dump_json(),
                                "TREATMENT.md": planning["treatment"], "SCENES.md": planning["scenes"],
                                "SCRIPT.md": "我去年在公司推行了这个方法。"}.items():
                (root / "planning" / name).write_text(value)
        elif message.startswith("〔Easel Script 系统审阅〕"):
            calls.append("assess")
            report_path = Path(re.search(r"只写 (.+\.json)，JSON 结构", message)[1])
            report = json.loads(message.split("（逐项替换判断，不增加字段）：\n", 1)[1].split("\n写入后停止。", 1)[0])
            is_rewritten = "我更愿意" in (root / "planning/SCRIPT.md").read_text()
            for decision in report["decisions"]:
                decision.update(kind="creative_expression" if is_rewritten else "rewrite_required",
                                reason="这是主观选择，不声称实际成效。" if is_rewritten else "公司经历没有来源，应删除自行添加的亲历。")
            report_path.write_text(json.dumps(report))
        elif message.startswith("〔Easel Planning：修正系统自行引入的事实问题〕"):
            calls.append("rewrite")
            (root / "planning/SCRIPT.md").write_text("我更愿意先看清问题，再决定下一步。" if repair_succeeds
                                                   else "我后来在公司实现了百分之十的增长。")
            # The adapter's same-run reconciliation is covered separately.
            # Here the completed rewrite outlives its caller before Planning
            # can persist a ledger, exercising durable repair accounting.
            if calls.count("rewrite") == 1:
                raise DeliveryExecutionUncertain("模拟修正结束但调用方未收到完成响应")
        else:
            pytest.fail("unexpected model phase")
        return ""

    supplied = []
    native_supply = ProductMaterialSupply.run

    def supply(self, plan, attempt, **kwargs):
        ledger = PlanningIntegration().load(attempt)["truth_ledger"]
        assert ledger["status"] == "PASSED"
        assert [row["status"] for row in ledger["claims"]] == ["SYSTEM_REVIEWED"]
        supplied.append(plan)
        return native_supply(self, plan, attempt, **kwargs)

    monkeypatch.setattr(web, "run_agent_sync", agent)
    monkeypatch.setattr(web, "_hypit_runtime_profile", lambda: None)
    monkeypatch.setattr(ProductMaterialSupply, "run", supply)
    with pytest.raises(DeliveryExecutionUncertain):
        asyncio.run(web._execute_creation_delivery("prepare", creation.get_creation(work["id"])))
    assert not supplied
    saved = creation.get_creation(work["id"])
    assert len(next(iter(saved["delivery"]["script_repairs"].values()))) == 1
    if repair_succeeds:
        asyncio.run(web._execute_creation_delivery("prepare", saved))
    else:
        with pytest.raises(prep.PreparationError, match="修正次数已用完"):
            asyncio.run(web._execute_creation_delivery("prepare", saved))
    saved = creation.get_creation(work["id"])
    assert saved["preparation"]["status"] == ("MATERIAL_NOT_READY" if repair_succeeds else "MATERIAL_FAILED")
    assert calls == ["plan", "assess", "rewrite", "assess"]
    assert len(supplied) == (1 if repair_succeeds else 0)
    assert len(saved["hypit_attempts"]) == 1
    if not repair_succeeds:
        from easel.creation_delivery import retry_delivery, MAX_FAILURES
        attempt_id = saved["hypit_attempts"][-1]["attempt_id"]
        failure_key = f"{attempt_id}:prepare"
        with creation.edit_creation(work["id"]) as current:
            current["delivery"].update(status="failed", exhausted_operation=failure_key,
                                        failures={failure_key: MAX_FAILURES})
        retried = retry_delivery(work["id"])
        assert retried["delivery"]["script_repair_rounds"][attempt_id] == 1
        assert attempt_id not in retried["delivery"]["script_repairs"]
        repair_succeeds = True
        asyncio.run(web._execute_creation_delivery("prepare", retried))
        assert calls.count("rewrite") == 2
        assert len(supplied) == 1


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


def test_director_planning_executor_consumes_frozen_refs_and_not_fixed_image(prep_env, monkeypatch):
    prepared = _prepare_creation(prep_env["work"]["id"], runtime_profile=None)
    attempt = service.get_film_attempt(prepared["attempt_id"])
    work = creation.get_creation(prepared["creation_id"])
    _, handoff_manifest, _ = handoff.resolve_handoff(work["id"], prepared["handoff_id"])
    hashes = work["preparation"]["snapshot_hashes"]
    refs = {
        "content_core_sha256": hashes["content_core"],
        "truth_packet_sha256": hashes["truth_packet"],
        "creator_context_sha256": hashes["creator_context"],
        "production_brief_sha256": hashes["production_brief"],
        "creative_mode_sha256": handoff_manifest["creative_mode"]["hash"],
    }
    plan = MaterialPlan(
        plan_id=f"plan-{attempt['attempt_id'][-20:]}", creation_id=attempt["creation_id"],
        attempt_id=attempt["attempt_id"], context_refs=refs,
        needs=(MaterialNeed(
            need_id="director-main-video", scope=NeedScope(type=NeedScopeType.SCENE, ref="scene-1"),
            media_type=MediaType.VIDEO, role="主镜头",
            intent=NeedIntent(description="由当前 Content 与 Director 意图决定的视频镜头"),
            importance=NeedImportance.REQUIRED,
        ),),
    )
    prompt_seen = []
    planning_dir = Path(attempt["workspace"]["path"]) / "planning"
    for name in ("MATERIAL_PLAN.json", "TREATMENT.md", "SCRIPT.md", "SCENES.md"):
        (planning_dir / name).unlink(missing_ok=True)

    def fake_agent(prompt, timeout, session_id=None):
        prompt_seen.append(prompt)
        (planning_dir / "MATERIAL_PLAN.json").write_text(plan.model_dump_json(), encoding="utf-8")
        (planning_dir / "TREATMENT.md").write_text("Treatment", encoding="utf-8")
        (planning_dir / "SCRIPT.md").write_text("Script", encoding="utf-8")
        (planning_dir / "SCENES.md").write_text("Scenes", encoding="utf-8")
        return "planned"

    monkeypatch.setattr(web, "run_agent_sync", fake_agent)
    result = web._material_planning_executor(attempt, {
        "content_core": handoff_manifest["content"]["content_core"],
        "truth_packet": handoff_manifest["content"]["truth_packet"],
        "creator_context": handoff_manifest["creator_context"],
        "context_refs": refs,
    })
    assert prompt_seen and "冻结的 Content Core、Truth Packet、Creator Context" in prompt_seen[0]
    assert "Creative Mode / Director" in prompt_seen[0]
    assert "禁止套用固定 IMAGE Need" in prompt_seen[0]
    assert "读取后立即写出" in prompt_seen[0]
    assert "production_request.production_brief" in prompt_seen[0]
    assert "scene、event、global 或 segment" in prompt_seen[0]
    assert "字幕、标题、转场" in prompt_seen[0]
    assert "不能写 orientation" in prompt_seen[0]
    contract = json.loads(prompt_seen[0].split("〔MaterialPlan 正式 JSON Schema〕\n")[1].split("\n〔正式合同结束〕")[0])
    assert contract == MaterialPlan.model_json_schema()
    assert "duration_seconds" not in contract["$defs"]["VideoNeedSpec"]["properties"]
    assert "target_seconds" in contract["$defs"]["DurationHint"]["properties"]
    assert result["plan"].needs[0].media_type is MediaType.VIDEO
    assert result["plan"].context_refs == refs

    # A copied, valid plan must not short-circuit an output-bound rewrite.
    # It uses the same executor and frozen references, with explicit scope.
    feedback = {'origin': 'system_quality', 'allowed_changes': ['planning'],
                'feedback': [{'text': '先解释问题，再反思结论', 'time_seconds': 2}]}
    web._material_planning_executor(attempt, {'context_refs': refs, 'quality_repair': feedback})
    assert len(prompt_seen) == 2
    assert '修正系统审片发现的内容问题' in prompt_seen[-1]
    assert json.dumps(feedback, ensure_ascii=False) in prompt_seen[-1]
    assert '不得增加或删除 Need' in prompt_seen[-1]

    # A discussed/confirmed plan is supplied by Easel, not re-authored by Planning.
    from easel.creator_proposal import parse_video_plan
    confirmed = parse_video_plan(VIDEO_PROPOSAL)
    with creation.edit_creation(work["id"]) as current:
        current["delivery"] = {"video_plan": confirmed}
    for path in planning_dir.iterdir():
        if path.name in {"SCRIPT.md", "SCENES.md", "TREATMENT.md", "MATERIAL_PLAN.json"}:
            path.unlink()
    def material_only(prompt, *_):
        assert (planning_dir / "SCRIPT.md").read_text() == confirmed["script"]
        assert (planning_dir / "SCENES.md").read_text() == confirmed["scenes"]
        (planning_dir / "MATERIAL_PLAN.json").write_text(plan.model_dump_json())
        return "完成素材需求"
    monkeypatch.setattr(web, "run_agent_sync", material_only)
    result = web._material_planning_executor(attempt, {"context_refs": refs})
    assert result["script"] == confirmed["script"]
    assert result["scenes"] == confirmed["scenes"]
    (planning_dir / "SCRIPT.md").write_text("擅自重写")
    monkeypatch.setattr(web, "run_agent_sync", lambda *_: "不修复")
    with pytest.raises(prep.PreparationError, match="改变了已确认"):
        web._material_planning_executor(attempt, {"context_refs": refs})
    with pytest.raises(prep.PreparationError, match="回到方案讨论"):
        web._material_planning_executor(attempt, {"context_refs": refs, "quality_repair": feedback})


def test_failed_planning_and_not_ready_retry_reuse_frozen_attempt(prep_env):
    creation_id = prep_env["work"]["id"]
    original_key = prep_env["claim"]["operation_key"]

    def failed_planning(_attempt, _context):
        raise prep.PreparationError("Planning Agent did not write MaterialPlan")

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


@pytest.mark.parametrize("invalid_kind", ["domain", "retrieval", "video_duration"])
def test_planning_resume_repairs_invalid_domain_file_once(prep_env, monkeypatch, invalid_kind):
    prepared = _prepare_creation(prep_env["work"]["id"], runtime_profile=None)
    attempt = service.get_film_attempt(prepared["attempt_id"])
    root = Path(attempt["workspace"]["path"])
    valid_json = (root / "materials" / "plan.json").read_text(encoding="utf-8")
    invalid = json.loads(valid_json)
    if invalid_kind == "domain":
        invalid["policy"] = {"must_be_a_string": True}
        invalid["schema"] = "easel-material-plan@1"
    elif invalid_kind == "retrieval":
        invalid["needs"][0]["constraints"] = {"allowed_source_kinds": ["external_stock"]}
    else:
        invalid["needs"][0].update(media_type="video", modality_spec={"kind": "video", "duration_seconds": 8})
    planning_file = root / "planning" / "MATERIAL_PLAN.json"
    planning_file.write_text(json.dumps(invalid), encoding="utf-8")
    prompts = []

    def repair_agent(message, _timeout, _session_id):
        prompts.append(message)
        planning_file.write_text(valid_json, encoding="utf-8")
        return "corrected"

    monkeypatch.setattr(web, "run_agent_sync", repair_agent)
    result = web._material_planning_executor(attempt, {
        "context_refs": invalid["context_refs"],
    })
    assert len(prompts) == 1
    if invalid_kind == "domain":
        assert "policy.must_be_a_string:string_type" in prompts[0]
        assert "schema:extra_forbidden" in prompts[0]
        assert "必须删除顶层 schema 字段" in prompts[0]
    elif invalid_kind == "retrieval":
        assert "retrieval validation failed" in prompts[0]
        assert "required_source_kind=stock" in prompts[0]
    else:
        assert "modality_spec.video.duration_seconds:extra_forbidden" in prompts[0]
        assert "Need.duration_hint.target_seconds" in prompts[0]
    contract = json.loads(prompts[0].split("〔MaterialPlan 正式 JSON Schema〕\n")[1].split("\n〔正式合同结束〕")[0])
    assert contract == MaterialPlan.model_json_schema()
    assert "当前冻结 context_refs" in prompts[0]
    assert result["plan"].plan_id == invalid["plan_id"]


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
    authoring_starts = []
    monkeypatch.setattr(web, "_start_film_authoring", lambda attempt_id: authoring_starts.append(attempt_id))
    monkeypatch.setattr(web, "_material_planning_executor", _test_planning_executor)
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
        offered = preview['generation_budget']
        assert offered['available'] is True and 'fixture-key' not in json.dumps(offered)
        declaration = preview['input_use']
        assert declaration['schema'] == 'easel-input-use@2'
        assert 'text_to_visual_generation' in declaration['operations'] and '以文字生成图片或视频素材' in declaration['statement']
        unsigned = {k: v for k, v in declaration.items() if k != 'statement_sha256'}
        assert declaration['statement_sha256'] == hashlib.sha256(json.dumps(
            unsigned, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
        stale = {**confirmation.model_dump(), 'inputUseStatementSha256': '0' * 64}
        assert client.post('/api/chat', json=stale).status_code == 409
        assert not creation.get_creation(first_work['id'])['chat_workflow'].get('confirmed_at')
        old_page = {**confirmation.model_dump(), 'inputUseStatementSha256': creation.input_use_preview(version=1)['statement_sha256']}
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
    assert len(agent_calls) == 2
    assert "CURRENT_CREATION_ID=" in agent_calls[1][0]
    work = creation.get_creation(body["creationId"])
    assert work["chat_workflow"]["proposal_status"] == "CONFIRMED"
    assert len(work["chat_workflow"]["proposal_sha256"]) == 64
    assert "CONFIRMED_PROPOSAL_TRANSCRIPT" in agent_calls[1][0]
    assert "不露脸" in agent_calls[1][0]
    _, confirmed_handoff, _ = handoff.resolve_handoff(work["id"], work["hypit_handoffs"][0]["handoff_id"])
    assert confirmed_handoff["production_request"]["confirmed_proposal_sha256"] == work["chat_workflow"]["proposal_sha256"]
    assert confirmed_handoff["production_request"]["production_brief_sha256"] == work["preparation"]["snapshot_hashes"]["production_brief"]
    assert work["preparation"]["status"] == "MATERIAL_NOT_READY"
    assert work["preparation"]["runtime_status"] == "NOT_CONFIGURED"
    assert work["id"] == body["creationId"]
    assert len(work["hypit_handoffs"]) == 1
    assert len(work["hypit_attempts"]) == 1
    assert work["hypit_attempts"][0]["authoring_status"] == "READY_FOR_EXTERNAL_AUTHORING"
    assert work["hypit_attempts"][0]["execution_status"] == "BLOCKED"
    assert work["hypit_attempts"][0]["status"] == "MATERIAL_NOT_READY"
    assert work["hypit_attempts"][0]["material_gate"]["status"] == "MATERIAL_NOT_READY"
    assert authoring_starts == []


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
    assert "不自行补视频时长、价格区间、平台、画幅或目标受众" in message
    assert "不要使用“已确认事实”“截面事实”" in message
    assert "不要向用户提后端、Preparation、Production Brief、Creator Context、Agent、Skill 或文件流程" in message
    assert creation.get_creation(work["id"])["preparation"]["status"] == "CREATED"


@pytest.mark.parametrize("resume", [False, True])
def test_ready_preparation_starts_authoring_without_an_extra_confirmation(monkeypatch, resume):
    started = []
    monkeypatch.setattr(web, "prepare_creation_for_hypit", lambda *_args, **_kwargs: {
        "status": "READY_FOR_EXTERNAL_AUTHORING", "attempt_id": "fa_test",
    })
    monkeypatch.setattr(web, "_hypit_runtime_profile", lambda: None)
    monkeypatch.setattr(web, "_material_planning_executor", lambda *_args: pytest.fail("Planning must be reused"))
    monkeypatch.setattr(web, "_start_film_authoring", lambda attempt_id: started.append(attempt_id))
    work = {"id": "cr_test"}

    if resume:
        asyncio.run(web._resume_confirmed_preparation(work))
    else:
        asyncio.run(web._finish_ai_film_turn(work, "generate", succeeded=True))

    assert started == ["fa_test"]


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
    monkeypatch.setattr(web, "get_film_attempt", lambda _attempt_id: {
        "attempt_id": "fa_legacy", "creation_id": work["id"],
    })
    with pytest.raises(HypitIntegrationError, match="尚未明确确认"):
        web._start_film_authoring("fa_legacy")
    with pytest.raises(prep.PreparationError):
        _prepare_creation(work["id"], runtime_profile=None)
    saved = creation.get_creation(work["id"])
    assert saved.get("hypit_handoffs", []) == []
    assert saved.get("hypit_attempts", []) == []


def test_confirmed_attempt_can_dispatch_existing_authoring(prep_env, monkeypatch):
    result = _prepare_creation(prep_env["work"]["id"], runtime_profile=None)
    dispatched = []

    async def fake_authoring(attempt_id):
        dispatched.append(attempt_id)

    monkeypatch.setattr(web, "_run_film_authoring", fake_authoring)

    async def dispatch_once():
        started = web._start_film_authoring(result["attempt_id"])
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        return started

    with pytest.raises(HypitIntegrationError, match="MATERIAL_READY"):
        asyncio.run(dispatch_once())
    assert result["status"] == "MATERIAL_NOT_READY"
    assert dispatched == []


def test_confirmed_interrupted_authoring_can_be_resumed_idempotently(monkeypatch):
    attempt_id = "fa_interrupted"
    attempt = {"attempt_id": attempt_id, "creation_id": "cr_interrupted",
               "authoring_status": "AUTHORING_RUNNING"}
    monkeypatch.setattr(web, "get_film_attempt", lambda _id: attempt)
    monkeypatch.setattr(web, "get_creation", lambda _id: {})
    monkeypatch.setattr(web, "require_chat_proposal_confirmed", lambda _creation: None)
    dispatched = []

    async def fake_authoring(_attempt_id):
        dispatched.append(_attempt_id)

    monkeypatch.setattr(web, "_run_film_authoring", fake_authoring)

    async def resume_twice():
        first = web._start_film_authoring(attempt_id)
        second = web._start_film_authoring(attempt_id)
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        return first, second

    first, second = asyncio.run(resume_twice())

    assert first["authoring_status"] == second["authoring_status"] == "AUTHORING_RUNNING"
    assert dispatched == [attempt_id]


def test_authoring_repairs_machine_detectable_svrun_source_once(prep_env, monkeypatch):
    attempt_id = "fa_0123456789abcdef0123456789abcdef"
    task = {"workspace": str(prep_env["tmp"] / "workspace"), "task_path": "AUTHORING_TASK.md"}
    monkeypatch.setattr(web, "get_film_attempt", lambda _id: {"authoring_status": "AUTHORING_FAILED"})
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


def test_authoring_repairs_missing_audio_normalize_once(prep_env, monkeypatch):
    from easel.integrations import material_layer

    attempt_id = "fa_0123456789abcdef0123456789abcdef"
    task = {"workspace": str(prep_env["tmp"] / "workspace"), "task_path": "AUTHORING_TASK.md"}
    attempt = {"authoring_status": "AUTHORING_FAILED", "material_gate": {"status": "MATERIAL_READY"}}
    monkeypatch.setattr(web, "get_film_attempt", lambda _id: attempt)
    monkeypatch.setattr(web, "begin_film_authoring", lambda _id: {
        **attempt, "authoring_status": "AUTHORING_RUNNING", "authoring_task": task,
    })
    monkeypatch.setattr(web, "_authoring_agent_message", lambda *_args: "initial authoring")
    messages = []
    monkeypatch.setattr(web, "run_attempt_scoped_authoring", lambda **kwargs: messages.append(kwargs["message"]))
    monkeypatch.setattr(web, "complete_film_authoring", lambda _id: {"authoring_status": "AUTHORING_READY"})

    class Selection:
        def qualified_authoring_assets(self, _attempt):
            return []

        def record_selection_from_authored_svml(self, _attempt):
            return None

        def validate_authored_selection(self, _attempt, _run_path):
            if len(messages) == 1:
                raise material_layer.MaterialIntegrationError(
                    "SVML selected audio Asset is not normalized, placed on an AudioTrack, "
                    "and included in Film: voice-asset"
                )
            return {"attempt": attempt}

    monkeypatch.setattr(material_layer, "ProductionAuthoringIntegration", Selection)
    result = asyncio.run(web._run_film_authoring(attempt_id))

    assert result["authoring_status"] == "AUTHORING_READY"
    assert len(messages) == 2
    assert "AudioTrack" in messages[1]
    assert "AUTHORING_TASK.md" in messages[1]
    assert "Provider 或调用 plan、pricing、build" in messages[1]


@pytest.mark.parametrize("prior_error", [None, {"message": "previous Hypit check failed"}])
@pytest.mark.parametrize("check_error", [
    "Hypit check 失败：time:Clock requires exactly id and frame-rate.",
    "Hypit check 失败：space:Canvas requires width, height.",
    "Hypit check 失败：media-track:Item.appearance must be a reference.",
])
def test_authoring_automatically_repairs_bounded_hypit_check_feedback(
    prep_env, monkeypatch, prior_error, check_error,
):
    attempt_id = "fa_0123456789abcdef0123456789abcdef"
    task = {"workspace": str(prep_env["tmp"] / "workspace"), "task_path": "AUTHORING_TASK.md"}
    monkeypatch.setattr(web, "get_film_attempt", lambda _id: {
        "authoring_status": "AUTHORING_FAILED",
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


def test_runtime_resolution_api_uses_server_profile_and_reuses_attempt(prep_env, tmp_path, monkeypatch):
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

    assert response.status_code == 200
    attempt = service.get_film_attempt(result["attempt_id"])
    assert attempt["runtime_status"] == "CONFIGURED"
    assert attempt["execution_status"] == "NOT_SUBMITTED"
    assert attempt["attempt_number"] == 1
    assert len(creation.get_creation(prep_env["work"]["id"])["hypit_attempts"]) == 1


def test_blocked_runtime_attempt_cannot_validate(prep_env):
    result = _prepare_creation(prep_env["work"]["id"], runtime_profile=None)

    with pytest.raises(HypitIntegrationError, match="MATERIAL_READY"):
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
    first = creation.save_video_proposal(cid, "turn-1", VIDEO_PROPOSAL)["chat_workflow"]["video_plan"]
    assert first["revision"] == 1
    # Disk recovery needs no browser transcript and specs cannot be changed by it.
    preview = video_proposal_preview(creation.get_creation(cid), [{"role": "user", "content": "改为90秒"}])
    assert not preview["missing"] and preview["specs"]["duration_seconds"] == 15
    creation.begin_video_proposal(cid, "turn-2")
    assert video_proposal_preview(creation.get_creation(cid), [])["missing"]
    creation.save_video_proposal(cid, "turn-1", VIDEO_PROPOSAL)
    assert creation.get_creation(cid)["chat_workflow"]["proposal_status"] == "DISCUSSING"
    second = creation.save_video_proposal(cid, "turn-2", VIDEO_PROPOSAL.replace("先看问题", "看清选择"))["chat_workflow"]["video_plan"]
    assert second["revision"] == 2 and second["sha256"] != first["sha256"]
    proposal = json.dumps([{"role": "assistant", "content": VIDEO_PROPOSAL}], ensure_ascii=False)
    kwargs = dict(delivery_proposal=proposal, proposal_sha256=hashlib.sha256(proposal.encode()).hexdigest(),
                  production_specs=second["specs"])
    with pytest.raises(creation.CreationError, match="已更新"):
        creation.confirm_chat_proposal(cid, "confirm", video_plan_sha256=first["sha256"], **kwargs)
    confirmed = creation.confirm_chat_proposal(cid, "confirm", video_plan_sha256=second["sha256"], **kwargs)
    assert confirmed["delivery"]["video_plan"] == second
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
    assert next_operation(editing) == (None, 'revising_proposal')
    assert editing['proposal_history'][0]['delivery'] == before['delivery']
    # Repeated clicks neither append history nor discard current edits.
    assert len(creation.reopen_video_proposal(cid)['proposal_history']) == 1
    creation.begin_video_proposal(cid, 'revise')
    creation.save_video_proposal(cid, 'revise', VIDEO_PROPOSAL)
    kwargs = dict(delivery_proposal=before['delivery']['proposal'],
        proposal_sha256=before['delivery']['proposal_sha256'], video_plan_sha256=plan['sha256'])
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
        with pytest.raises(creation.CreationError, match='制作已开始'):
            creation.reopen_video_proposal(cid)
