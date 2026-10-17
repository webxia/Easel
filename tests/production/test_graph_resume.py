import asyncio
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from easel.production.worker import TaskResult, Worker
from .test_worker import record, seed_run, store


def test_dynamic_stages_use_real_sqlite_checkpoints_and_do_not_plan_production(store):
    work_id, run_id, _ = seed_run(store, kind="production", first="supply")
    called = []
    async def plan(_ctx):
        pytest.fail("production must read the frozen plan")
    async def supply(ctx):
        called.append("supply")
        assert ctx.plan_revision == 1
        return TaskResult(result={"artifact_id": "existing"}, next_kind="inspect", next_payload={"artifact_id": "existing"})
    async def inspect(ctx):
        called.append("inspect")
        assert ctx.payload["artifact_id"] == "existing"
        return TaskResult(work_state="reviewable")
    worker = Worker(store, {"plan": plan, "supply": supply, "inspect": inspect})
    assert asyncio.run(worker.run_once())
    assert called == ["supply", "inspect"]
    assert record(store, "runs", run_id)["state"] == "succeeded"
    assert store.get_work(work_id)["state"] == "reviewable"
    with sqlite3.connect(worker.checkpoint_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM checkpoints WHERE thread_id=?", (run_id,)).fetchone()[0] >= 5


def test_host_tracing_environment_is_not_used(store, monkeypatch):
    from langsmith.client import Client
    seed_run(store)
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "not-a-real-key")
    monkeypatch.setattr(Client, "create_run", lambda *a, **k: pytest.fail("cloud trace is forbidden"))
    async def plan(_ctx):
        return TaskResult()
    assert asyncio.run(Worker(store, {"plan": plan}).run_once())


def test_domain_commit_before_checkpoint_crash_does_not_repeat_stage(store):
    _, run_id, task_id = seed_run(store)
    calls = []
    now = [10]
    class ProcessCrash(BaseException):
        pass
    async def plan(_ctx):
        calls.append("plan")
        return TaskResult(next_kind="inspect")
    async def inspect(_ctx):
        calls.append("inspect")
        return TaskResult()
    worker = Worker(store, {"plan": plan, "inspect": inspect}, clock=lambda: now[0])
    finish = worker._finish
    def crash(ctx, outcome):
        finish(ctx, outcome)
        raise ProcessCrash()
    worker._finish = crash
    with pytest.raises(ProcessCrash):
        asyncio.run(worker.run_once())
    assert record(store, "tasks", task_id)["state"] == "succeeded"
    now[0] += 2
    asyncio.run(Worker(store, {"plan": plan, "inspect": inspect}, clock=lambda: now[0]).run_once())
    assert calls == ["plan", "inspect"]
    assert record(store, "runs", run_id)["state"] == "succeeded"


def test_completed_checkpoint_cannot_skip_pending_domain_task(store):
    _, run_id, task_id = seed_run(store)
    calls = []
    async def handler(_ctx):
        calls.append("done")
        return TaskResult()
    worker = Worker(store, {"plan": handler})
    asyncio.run(worker.run_once())
    # Fault injection: a stale completed checkpoint exists while DB needs work.
    with store.transaction() as writer:
        writer.execute("UPDATE runs SET state='pending',lease_expires_at=NULL WHERE id=?", (run_id,))
        writer.execute("UPDATE tasks SET state='pending',result_json=NULL WHERE id=?", (task_id,))
    asyncio.run(Worker(store, {"plan": handler}).run_once())
    assert calls == ["done", "done"]
    assert record(store, "tasks", task_id)["state"] == "succeeded"


def test_fresh_process_recovers_inflight_operation_after_hard_exit(store):
    from .test_operations import owned_request
    from easel.production.operations import OperationService
    from .fake_provider import FakeProvider
    spec = owned_request(store)
    with store.transaction() as writer:
        writer.execute("UPDATE runs SET lease_expires_at=0 WHERE id=?", (spec["run_id"],))
    script = r'''
import asyncio, json, os, sys
from pathlib import Path
from easel.production.store import Store
from easel.production.operations import OperationService
from easel.production.worker import Worker, TaskResult
from tests.production.fake_provider import FakeProvider
store = Store(sys.argv[1]); spec = json.loads(sys.argv[2]); crash = sys.argv[3] == 'crash'
provider = FakeProvider(store.path.with_name('provider.sqlite3'))
ops = OperationService(store, clock=lambda: 3000 if crash else 4000)
async def supply(ctx):
    current = {**spec, 'owner_epoch':ctx.owner_epoch}
    op = ops.reserve(**current)
    if crash:
        assert ops.mark_sending(op['id'], ctx.owner_epoch)
        provider.submit(op['request'], request_key=op['request_key'])
        os._exit(86)
    observed = ops.observe(op['id'], provider)
    assert observed['state'] == 'succeeded'
    return TaskResult()
asyncio.run(Worker(store, {'supply':supply}, clock=lambda: 3000 if crash else 4000).run_once())
'''
    import json
    root = str(Path(__file__).resolve().parents[2])
    env = {key: value for key, value in os.environ.items() if key in {"PATH", "SYSTEMROOT", "WINDIR", "LANG", "TMP", "TEMP"}}
    env["PYTHONPATH"] = root
    crash = subprocess.run([sys.executable, "-c", script, str(store.path), json.dumps(spec), "crash"], env=env, capture_output=True, timeout=30)
    assert crash.returncode == 86, crash.stderr.decode()
    assert OperationService(store).get(spec["operation_id"])["state"] == "sending"
    resumed = subprocess.run([sys.executable, "-c", script, str(store.path), json.dumps(spec), "resume"], env=env, capture_output=True, timeout=30)
    assert resumed.returncode == 0, resumed.stderr.decode()
    assert OperationService(store).get(spec["operation_id"])["state"] == "succeeded"
    assert FakeProvider(store.path.with_name("provider.sqlite3")).count == 1
    assert record(store, "runs", spec["run_id"])["state"] == "succeeded"
