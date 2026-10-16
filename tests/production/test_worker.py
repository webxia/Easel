import asyncio
from concurrent.futures import ThreadPoolExecutor
import json

import pytest

from easel.production.contracts import canonical_json
from easel.production.errors import ProductionError, StaleRevision
from easel.production.store import Store, utc_now
from easel.production.worker import TaskResult, Worker


def seed_run(store, *, kind="planning", first="plan", graph_version="production-1"):
    work = store.create_work({"title": "worker fixture"})
    plan_revision = None
    if kind != "planning":
        plan = store.save_plan(work["id"], {"title": "片子", "summary": "摘要", "script": "原观点",
            "scenes": [{"id": "scene1", "purpose": "解释", "visual": "实拍"}],
            "settings": {"duration_seconds": 30, "audio_mode": "silent"}}, expected_revision=1)
        plan_revision = plan["revision"]
    run_id, task_id = "run_"+work["id"], "task_"+work["id"]
    now = utc_now()
    with store.transaction() as writer:
        if plan_revision:
            writer.execute("UPDATE plan_revisions SET confirmed_at=? WHERE work_id=?", (now, work["id"]))
        writer.execute("INSERT INTO runs(id,work_id,kind,plan_revision,graph_version,input_fingerprint,created_at,updated_at) VALUES(?,?,?,?,?,'input',?,?)",
            (run_id, work["id"], kind, plan_revision, graph_version, now, now))
        writer.execute("INSERT INTO tasks(id,work_id,run_id,kind,plan_revision,input_fingerprint,created_at,updated_at) VALUES(?,?,?,?,?,'input',?,?)",
            (task_id, work["id"], run_id, first, plan_revision, now, now))
        writer.execute("UPDATE works SET active_run_id=?,state=? WHERE id=?", (run_id, "discussing" if kind == "planning" else "producing", work["id"]))
    return work["id"], run_id, task_id


@pytest.fixture
def store(tmp_path):
    result = Store(tmp_path / "production.sqlite3")
    result.initialize()
    return result


def record(store, table, identifier):
    with store.connection() as reader:
        return dict(reader.execute(f"SELECT * FROM {table} WHERE id=?", (identifier,)).fetchone())


def test_two_process_owners_cannot_claim_one_run(store):
    _, run_id, _ = seed_run(store)
    workers = [Worker(store, {}, owner_id=f"worker_{i}", clock=lambda: 10) for i in range(8)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        leases = list(pool.map(lambda worker: worker.claim_next(), workers))
    assert sum(lease is not None for lease in leases) == 1
    assert record(store, "runs", run_id)["owner_epoch"] == 1


def test_takeover_fences_old_domain_writes_and_heartbeats(store):
    _, _, task_id = seed_run(store)
    now = [10]
    first = Worker(store, {}, owner_id="first", clock=lambda: now[0], lease_seconds=5)
    lease = first.claim_next()
    ctx = first._start(lease, task_id, "plan")
    now[0] = 16
    second = Worker(store, {}, owner_id="second", clock=lambda: now[0])
    new_lease = second.claim_next()
    assert new_lease.owner_epoch == 2
    assert not first.heartbeat(lease)
    with pytest.raises(StaleRevision):
        with ctx.transaction() as writer:
            writer.execute("UPDATE works SET title='late' WHERE id=?", (ctx.work_id,))
    assert store.get_work(ctx.work_id)["title"] == "worker fixture"


def test_cancel_fences_domain_result_without_reversing_external_receipts(store):
    work_id, run_id, task_id = seed_run(store)
    worker = Worker(store, {}, clock=lambda: 10)
    lease = worker.claim_next()
    ctx = worker._start(lease, task_id, "plan")
    with store.transaction() as writer:
        writer.execute("UPDATE runs SET cancel_requested=1,state='cancelled',owner_epoch=owner_epoch+1 WHERE id=?", (run_id,))
        writer.execute("UPDATE works SET state='cancelled' WHERE id=?", (work_id,))
    with pytest.raises(StaleRevision):
        worker._finish(ctx, TaskResult(work_state="awaiting_confirmation"))
    assert record(store, "tasks", task_id)["state"] == "running"


def test_incompatible_graph_pauses_without_running_handlers(store):
    _, run_id, task_id = seed_run(store, graph_version="future-graph")
    worker = Worker(store, {})
    assert worker.claim_next() is None
    assert record(store, "runs", run_id)["state"] == "paused"
    assert json.loads(record(store, "tasks", task_id)["error_json"])["code"] == "graph_version_incompatible"


def test_expired_running_dispatch_is_not_mistaken_for_reserved(store):
    from .test_operations import owned_request
    from easel.production.operations import OperationService
    spec = owned_request(store)
    ops = OperationService(store, clock=lambda: 1000)
    ops.reserve(**spec)
    ops.mark_sending(spec["operation_id"], 1)
    worker = Worker(store, {}, clock=lambda: 2001)
    assert worker.claim_next().owner_epoch == 2
    assert ops.get(spec["operation_id"])["state"] == "unknown"


def test_planning_can_register_new_current_plan_in_guarded_transaction(store):
    work_id, run_id, _ = seed_run(store)
    async def plan(ctx):
        with ctx.transaction() as writer:
            work = store.get_work(ctx.work_id, connection=writer)
            store.save_plan(ctx.work_id, {"title": "计划", "summary": "摘要", "script": "内容",
                "scenes": [{"id": "one", "purpose": "说明", "visual": "实拍"}],
                "settings": {"duration_seconds": 60, "audio_mode": "silent"}}, expected_revision=work["revision"], connection=writer)
        return TaskResult(work_state="awaiting_confirmation")
    assert asyncio.run(Worker(store, {"plan": plan}).run_once())
    assert record(store, "runs", run_id)["state"] == "succeeded"
    assert store.get_work(work_id)["state"] == "awaiting_confirmation"
    assert store.get_work(work_id)["current_plan_revision"] == 1


def test_missing_handler_requires_decision_and_is_not_automatically_retried(store):
    _, run_id, task_id = seed_run(store, first="not_configured")
    worker = Worker(store, {})
    assert asyncio.run(worker.run_once())
    assert record(store, "runs", run_id)["state"] == "needs_decision"
    assert json.loads(record(store, "tasks", task_id)["error_json"])["code"] == "capability_unavailable"
    assert not asyncio.run(worker.run_once())


def test_retryable_failure_has_a_persistent_attempt_limit(store):
    _, run_id, task_id = seed_run(store)
    now = [10]
    async def fails(_ctx):
        raise ProductionError("local_transient", "临时资源不可用", retryable=True)
    worker = Worker(store, {"plan": fails}, clock=lambda: now[0], max_task_attempts=2)
    asyncio.run(worker.run_once())
    assert record(store, "tasks", task_id)["state"] == "retryable_failed"
    now[0] += 2
    asyncio.run(Worker(store, {"plan": fails}, clock=lambda: now[0], max_task_attempts=2).run_once())
    assert record(store, "runs", run_id)["state"] == "needs_decision"
    assert json.loads(record(store, "tasks", task_id)["error_json"])["code"] == "retry_limit"


def test_shutdown_is_resumable_and_not_user_cancel(store):
    _, run_id, task_id = seed_run(store)
    now = [10]
    async def scenario():
        entered = asyncio.Event()
        async def slow(_ctx):
            entered.set()
            await asyncio.Future()
        worker = Worker(store, {"plan": slow}, clock=lambda: now[0])
        execution = asyncio.create_task(worker.run_once())
        await asyncio.wait_for(entered.wait(), 10)
        worker.stop()
        await execution
    asyncio.run(scenario())
    assert record(store, "runs", run_id)["cancel_requested"] == 0
    assert record(store, "runs", run_id)["state"] == "pending"
    async def finish(_ctx):
        return TaskResult(work_state="awaiting_confirmation")
    now[0] += 2
    asyncio.run(Worker(store, {"plan": finish}, clock=lambda: now[0]).run_once())
    assert record(store, "tasks", task_id)["state"] == "succeeded"


def test_heartbeat_renews_without_allowing_post_expiry_revival(store):
    _, run_id, _ = seed_run(store)
    now = [10]
    worker = Worker(store, {}, clock=lambda: now[0], lease_seconds=5)
    lease = worker.claim_next()
    now[0] = 14
    assert worker.heartbeat(lease)
    assert record(store, "runs", run_id)["lease_expires_at"] == 19
    now[0] = 20
    assert not worker.heartbeat(lease)


def test_waiting_external_resumes_without_a_new_submission(store):
    from .fake_provider import FakeProvider
    from .test_operations import owned_request
    from easel.production.operations import OperationService
    spec = owned_request(store)
    with store.transaction() as writer:
        writer.execute("UPDATE runs SET lease_expires_at=0 WHERE id=?", (spec["run_id"],))
    now = [1000]
    provider = FakeProvider(store.path.with_name("provider.sqlite3"), fault="after")
    ops = OperationService(store, clock=lambda: now[0])
    async def supply(ctx):
        op = ops.reserve(**{**spec, "owner_epoch": ctx.owner_epoch})
        op = ops.submit(op["id"], provider, owner_epoch=ctx.owner_epoch) if op["state"] == "reserved" else ops.observe(op["id"], provider)
        return TaskResult("succeeded" if op["state"] == "succeeded" else "waiting_external")
    asyncio.run(Worker(store, {"supply": supply}, clock=lambda: now[0]).run_once())
    assert record(store, "runs", spec["run_id"])["state"] == "waiting_external"
    assert provider.count == 1
    now[0] += 2
    provider.fault = None
    asyncio.run(Worker(store, {"supply": supply}, clock=lambda: now[0]).run_once())
    assert record(store, "runs", spec["run_id"])["state"] == "succeeded"
    assert provider.count == 1


def test_cli_status_does_not_initialize_or_load_runtime(tmp_path, capsys):
    from easel.cli import main
    assert main(["production", "status", "--root", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out) == []
    assert not list(tmp_path.iterdir())
