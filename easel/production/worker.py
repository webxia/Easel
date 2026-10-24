"""Leased local execution. Domain transactions remain authoritative over checkpoints."""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from dataclasses import dataclass, field
import json
from pathlib import Path
import time
from typing import Awaitable, Callable

from .contracts import WorkState, canonical_json, fingerprint
from .errors import ProductionError, StaleRevision
from .store import Store, new_id, utc_now

GRAPH_VERSION = "production-1"
_READY = ("pending", "running", "waiting_external", "retryable_failed")


@dataclass(frozen=True)
class TaskResult:
    state: str = "succeeded"
    result: dict = field(default_factory=dict)
    next_kind: str | None = None
    next_payload: dict | None = None
    next_fingerprint: str | None = None
    work_state: str | None = None
    error: ProductionError | None = None

    def __post_init__(self):
        if self.state not in {"succeeded", "waiting_external", "needs_decision", "retryable_failed", "failed"}:
            raise ValueError("unsupported task outcome")
        if self.next_kind and self.state != "succeeded":
            raise ValueError("only a successful task can create its successor")
        if self.work_state is not None:
            WorkState(self.work_state)
        canonical_json(self.result)
        if self.next_payload is not None:
            canonical_json(self.next_payload)


@dataclass(frozen=True)
class RunLease:
    work_id: str
    run_id: str
    owner_id: str
    owner_epoch: int


@dataclass(frozen=True)
class TaskContext:
    store: Store
    work_id: str
    run_id: str
    task_id: str
    owner_id: str
    owner_epoch: int
    plan_revision: int | None
    input_fingerprint: str
    payload: dict
    clock: Callable[[], float] = field(repr=False)

    def _check(self, connection):
        run, work = _check_lease(connection, self, self.clock())
        task = connection.execute("SELECT * FROM tasks WHERE id=?", (self.task_id,)).fetchone()
        if (task is None or task["run_id"] != self.run_id or task["work_id"] != self.work_id
                or task["state"] != "running" or task["owner_epoch"] != self.owner_epoch
                or task["input_fingerprint"] != self.input_fingerprint
                or task["plan_revision"] != self.plan_revision):
            raise StaleRevision("任务或执行所有权已变化")
        return run, work, task

    @contextmanager
    def transaction(self):
        """Use for artifact/plan registration; never hold over network or rendering."""
        with self.store.transaction() as writer:
            self._check(writer)
            yield writer

    def assert_current(self):
        with self.store.connection() as reader:
            self._check(reader)


def _check_lease(connection, lease, now):
    run = connection.execute("SELECT * FROM runs WHERE id=?", (lease.run_id,)).fetchone()
    work = connection.execute("SELECT * FROM works WHERE id=?", (lease.work_id,)).fetchone()
    if (run is None or work is None or run["work_id"] != lease.work_id
            or work["active_run_id"] != lease.run_id or work["state"] == "cancelled"
            or run["state"] != "running" or run["cancel_requested"]
            or run["owner_id"] != lease.owner_id or run["owner_epoch"] != lease.owner_epoch
            or run["lease_expires_at"] is None or run["lease_expires_at"] <= now
            or (run["kind"] != "planning" and run["plan_revision"] != work["current_plan_revision"])):
        raise StaleRevision("执行所有权、当前方案或取消状态已变化")
    return run, work


def tasks_completed(connection, run_id):
    """Retired failed renders count only with a committed recovery and replacement.

    Cancellation itself is never success; dependency edges remain authoritative.
    """
    tasks = {t['id']: t for t in connection.execute('SELECT * FROM tasks WHERE run_id=?', (run_id,))}
    if not tasks or connection.execute("SELECT 1 FROM operations WHERE run_id=? AND state IN ('reserved','sending','submitted','unknown')", (run_id,)).fetchone():
        return False
    dependencies = [(d['task_id'], d['depends_on']) for d in connection.execute(
        'SELECT d.* FROM task_dependencies d JOIN tasks t ON t.id=d.task_id WHERE t.run_id=?', (run_id,))]
    if any(child not in tasks or parent not in tasks or tasks[parent]['state'] != 'succeeded'
           for child, parent in dependencies):
        return False
    retired = set()
    for event in connection.execute("SELECT * FROM events WHERE run_id=? AND kind='edit_recovery_requested'", (run_id,)):
        data = json.loads(event['payload_json'])
        old, edit = tasks.get(data.get('render_task_id')), tasks.get(data.get('edit_task_id'))
        if (old is None or edit is None or old['kind'] != 'render' or old['state'] != 'cancelled'
                or edit['kind'] != 'edit' or edit['state'] != 'succeeded'
                or (old['id'], edit['id']) not in dependencies):
            continue
        if any(t['kind'] == 'render' and t['state'] == 'succeeded'
               and t['created_at'] >= event['created_at'] and (t['id'], edit['id']) in dependencies
               for t in tasks.values()):
            retired.add(old['id'])
    return all(t['state'] == 'succeeded' or t['id'] in retired for t in tasks.values())


Handler = Callable[[TaskContext], Awaitable[TaskResult]]


class Worker:
    def __init__(self, store: Store, handlers: dict[str, Handler], *, checkpoint_path: Path | str | None = None,
                 owner_id: str | None = None, lease_seconds: float = 30, poll_interval: float = 1,
                 clock: Callable[[], float] = time.time, max_task_attempts: int = 3):
        if lease_seconds <= 0 or poll_interval <= 0 or max_task_attempts < 1:
            raise ValueError("worker intervals and attempt limit must be positive")
        self.store, self.handlers, self.clock = store, dict(handlers), clock
        self.checkpoint_path = Path(checkpoint_path or store.path.with_name("checkpoints.sqlite3"))
        if self.checkpoint_path.resolve() == store.path:
            raise ValueError("checkpoint and business databases must be separate")
        self.owner_id = owner_id or new_id("worker")
        self.lease_seconds, self.poll_interval = lease_seconds, poll_interval
        self.max_task_attempts = max_task_attempts
        self._stopping = asyncio.Event()
        self._active: asyncio.Task | None = None
        self._running = False
        self._lease_lost = False

    def claim_next(self) -> RunLease | None:
        """SQLite serializes claim/epoch increments across independent processes."""
        with self.store.transaction() as writer:
            rows = writer.execute("""SELECT r.* FROM runs r JOIN works w ON w.active_run_id=r.id
                WHERE r.state IN ('pending','running','waiting_external') AND r.cancel_requested=0
                AND w.state!='cancelled' AND (r.lease_expires_at IS NULL OR r.lease_expires_at<=?)
                ORDER BY r.created_at,r.id""", (self.clock(),)).fetchall()
            for row in rows:
                if row["graph_version"] != GRAPH_VERSION:
                    error = ProductionError("graph_version_incompatible", "制作流程版本不兼容，需确认恢复方案", requires_decision=True)
                    writer.execute("UPDATE runs SET state='paused',owner_id=NULL,lease_expires_at=NULL,revision=revision+1,updated_at=? WHERE id=?", (utc_now(), row["id"]))
                    writer.execute("UPDATE tasks SET state='needs_decision',error_json=?,updated_at=? WHERE run_id=? AND state IN ('pending','running','waiting_external','retryable_failed')", (canonical_json(error.as_dict()), utc_now(), row["id"]))
                    self.store.append_event(writer, row["work_id"], "decision_required", error.as_dict(), run_id=row["id"])
                    continue
                work = self.store.get_work(row["work_id"], connection=writer)
                if row["kind"] != "planning" and row["plan_revision"] != work["current_plan_revision"]:
                    writer.execute("UPDATE runs SET state='superseded',owner_epoch=owner_epoch+1,owner_id=NULL,lease_expires_at=NULL,updated_at=? WHERE id=?", (utc_now(), row["id"]))
                    self.store.append_event(writer, row["work_id"], "run_superseded", {"run_id": row["id"]}, run_id=row["id"])
                    continue
                epoch = row["owner_epoch"] + 1
                writer.execute("""UPDATE runs SET state='running',owner_id=?,owner_epoch=?,lease_expires_at=?,
                    revision=revision+1,updated_at=? WHERE id=?""",
                    (self.owner_id, epoch, self.clock()+self.lease_seconds, utc_now(), row["id"]))
                # Crossing sending was durable. A restarted worker must observe, never submit again.
                unknown = writer.execute("UPDATE operations SET state='unknown',error_code='result_unknown',revision=revision+1,updated_at=? WHERE run_id=? AND state='sending'", (utc_now(), row["id"])).rowcount
                if unknown:
                    self.store.append_event(writer, row["work_id"], "operation_waiting", {"state": "unknown", "count": unknown}, run_id=row["id"])
                self.store.append_event(writer, row["work_id"], "run_claimed", {"owner_epoch": epoch}, run_id=row["id"])
                return RunLease(row["work_id"], row["id"], self.owner_id, epoch)
        return None

    def heartbeat(self, lease: RunLease) -> bool:
        with self.store.transaction() as writer:
            try:
                _check_lease(writer, lease, self.clock())
            except StaleRevision:
                return False
            writer.execute("UPDATE runs SET lease_expires_at=?,updated_at=? WHERE id=?", (self.clock()+self.lease_seconds, utc_now(), lease.run_id))
            return True

    def _next(self, lease: RunLease) -> dict | None:
        with self.store.transaction() as writer:
            try:
                _check_lease(writer, lease, self.clock())
            except StaleRevision:
                return None
            row = writer.execute("""SELECT t.* FROM tasks t WHERE t.run_id=?
                AND t.state IN ('pending','running','waiting_external','retryable_failed')
                AND NOT EXISTS(SELECT 1 FROM task_dependencies d JOIN tasks dep ON dep.id=d.depends_on
                    WHERE d.task_id=t.id AND dep.state!='succeeded')
                ORDER BY t.created_at,t.id LIMIT 1""", (lease.run_id,)).fetchone()
            if row:
                return dict(row)
            if tasks_completed(writer, lease.run_id):
                writer.execute("UPDATE runs SET state='succeeded',revision=revision+1,updated_at=? WHERE id=?", (utc_now(), lease.run_id))
                self.store.append_event(writer, lease.work_id, "run_completed", {"run_id": lease.run_id}, run_id=lease.run_id)
            else:
                error = ProductionError("dependency_blocked", "任务依赖未完成，需核实后继续", requires_decision=True)
                writer.execute("UPDATE runs SET state='needs_decision',revision=revision+1,updated_at=? WHERE id=?", (utc_now(), lease.run_id))
                self.store.append_event(writer, lease.work_id, "decision_required", error.as_dict(), run_id=lease.run_id)
            return None

    def reconcile_completed_run(self, run_id: str) -> bool:
        """Close a proven dependency-only false stop without executing any task."""
        with self.store.transaction() as writer:
            run = writer.execute('SELECT * FROM runs WHERE id=?', (run_id,)).fetchone()
            if run is None or run['state'] != 'needs_decision' or run['owner_id'] or run['cancel_requested']:
                return False
            work = self.store.get_work(run['work_id'], connection=writer)
            if (work['active_run_id'] != run_id or work['state'] == 'cancelled' or work.get('deleted_at')
                    or run['graph_version'] != GRAPH_VERSION or run['plan_revision'] != work['current_plan_revision']):
                return False
            event = writer.execute('SELECT * FROM events WHERE run_id=? ORDER BY seq DESC LIMIT 1', (run_id,)).fetchone()
            if (not event or event['kind'] != 'decision_required'
                    or json.loads(event['payload_json']).get('code') != 'dependency_blocked'
                    or not tasks_completed(writer, run_id)):
                return False
            writer.execute("UPDATE runs SET state='succeeded',revision=revision+1,updated_at=? WHERE id=?", (utc_now(), run_id))
            self.store.append_event(writer, run['work_id'], 'run_completed',
                                    {'run_id': run_id, 'reconciled_event_seq': event['seq']}, run_id=run_id)
            return True

    def _start(self, lease: RunLease, task_id: str, kind: str) -> TaskContext | None:
        with self.store.transaction() as writer:
            try:
                _check_lease(writer, lease, self.clock())
            except StaleRevision:
                return None
            task = writer.execute("SELECT * FROM tasks WHERE id=? AND run_id=?", (task_id, lease.run_id)).fetchone()
            # A checkpoint can replay an already committed node; it must not call its handler.
            if task is None or task["state"] not in _READY:
                return None
            if task["kind"] != kind:
                raise StaleRevision("检查点任务种类与领域记录不一致")
            if writer.execute("SELECT 1 FROM task_dependencies d JOIN tasks t ON t.id=d.depends_on WHERE d.task_id=? AND t.state!='succeeded'", (task_id,)).fetchone():
                return None
            writer.execute("UPDATE tasks SET state='running',owner_epoch=?,revision=revision+1,updated_at=? WHERE id=?", (lease.owner_epoch, utc_now(), task_id))
            self.store.append_event(writer, lease.work_id, "task_started", {"task_id": task_id, "kind": kind}, run_id=lease.run_id)
            return TaskContext(self.store, lease.work_id, lease.run_id, task_id, lease.owner_id,
                               lease.owner_epoch, task["plan_revision"], task["input_fingerprint"],
                               json.loads(task["payload_json"]), self.clock)

    def _finish(self, ctx: TaskContext, outcome: TaskResult):
        with ctx.transaction() as writer:
            error = outcome.error.as_dict() if outcome.error else None
            state = outcome.state
            if state == "retryable_failed":
                attempts = writer.execute("SELECT COUNT(*) FROM events WHERE run_id=? AND kind='task_retryable_failed' AND json_extract(payload_json,'$.task_id')=?", (ctx.run_id, ctx.task_id)).fetchone()[0] + 1
                if attempts >= self.max_task_attempts:
                    state = "needs_decision"
                    error = ProductionError("retry_limit", "任务恢复次数已达上限，需核实后继续", requires_decision=True).as_dict()
            writer.execute("UPDATE tasks SET state=?,result_json=?,error_json=?,revision=revision+1,updated_at=? WHERE id=?",
                           (state, canonical_json(outcome.result), canonical_json(error) if error else None, utc_now(), ctx.task_id))
            if outcome.next_kind:
                payload = {"schema_version": 1, **(outcome.next_payload if outcome.next_payload is not None else ctx.payload)}
                if payload["schema_version"] != 1:
                    raise ValueError("unsupported task payload schema")
                task_id = new_id("task")
                writer.execute("""INSERT INTO tasks(id,work_id,run_id,kind,plan_revision,input_fingerprint,payload_json,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?)""", (task_id, ctx.work_id, ctx.run_id, outcome.next_kind, ctx.plan_revision,
                    outcome.next_fingerprint or fingerprint({"previous": ctx.input_fingerprint, "kind": outcome.next_kind, "payload": payload}),
                    canonical_json(payload), utc_now(), utc_now()))
                writer.execute("INSERT INTO task_dependencies(task_id,depends_on) VALUES(?,?)", (task_id, ctx.task_id))
            run_state = {"waiting_external": "waiting_external", "retryable_failed": "pending", "needs_decision": "needs_decision", "failed": "failed"}.get(state)
            if run_state:
                writer.execute("UPDATE runs SET state=?,revision=revision+1,updated_at=? WHERE id=?", (run_state, utc_now(), ctx.run_id))
            work_state = outcome.work_state or ("needs_decision" if state == "needs_decision" else None)
            if work_state:
                work = self.store.get_work(ctx.work_id, connection=writer)
                self.store.bump_work(writer, ctx.work_id, work["revision"], state=work_state)
            self.store.append_event(writer, ctx.work_id, "task_"+state, {"task_id": ctx.task_id, "kind": writer.execute("SELECT kind FROM tasks WHERE id=?", (ctx.task_id,)).fetchone()[0]}, run_id=ctx.run_id)
            if state == "needs_decision":
                self.store.append_event(writer, ctx.work_id, "decision_required", error or {"task_id": ctx.task_id}, run_id=ctx.run_id)

    async def dispatch(self, lease: RunLease, task_id: str, kind: str):
        ctx = self._start(lease, task_id, kind)
        if ctx is None:
            return
        handler = self.handlers.get(kind)
        try:
            if handler is None:
                raise ProductionError("capability_unavailable", "当前任务能力尚未配置", requires_decision=True)
            outcome = await handler(ctx)
            if not isinstance(outcome, TaskResult):
                raise TypeError("handler must return TaskResult")
        except StaleRevision:
            return
        except ProductionError as error:
            outcome = TaskResult("needs_decision" if error.requires_decision else "retryable_failed" if error.retryable else "failed", error=error)
        except Exception:
            outcome = TaskResult("failed", error=ProductionError("task_failed", "任务执行失败，已保留已有成果"))
        try:
            self._finish(ctx, outcome)
        except StaleRevision:
            # Already received operation receipts survive, but stale domain output cannot win.
            return

    def _release(self, lease: RunLease):
        with self.store.transaction() as writer:
            row = writer.execute("SELECT * FROM runs WHERE id=?", (lease.run_id,)).fetchone()
            if row is None or row["owner_id"] != lease.owner_id or row["owner_epoch"] != lease.owner_epoch:
                return
            state = "pending" if row["state"] == "running" else row["state"]
            delay = self.poll_interval if state in {"pending", "waiting_external"} else 0
            writer.execute("UPDATE runs SET state=?,owner_id=NULL,lease_expires_at=?,updated_at=? WHERE id=?", (state, self.clock()+delay if delay else None, utc_now(), lease.run_id))

    async def _keep_alive(self, lease, stopped):
        while not stopped.is_set():
            try:
                await asyncio.wait_for(stopped.wait(), timeout=self.lease_seconds/3)
            except asyncio.TimeoutError:
                if not self.heartbeat(lease):
                    with self.store.connection() as reader:
                        row = reader.execute("SELECT state,owner_id,owner_epoch,cancel_requested FROM runs WHERE id=?", (lease.run_id,)).fetchone()
                    # Normal node completion may end the run before its checkpoint flush.
                    lost = row is None or row["owner_id"] != lease.owner_id or row["owner_epoch"] != lease.owner_epoch or row["cancel_requested"] or row["state"] == "running"
                    if lost and self._active:
                        self._lease_lost = True
                        self._active.cancel()
                    return

    def _pause(self, lease, error):
        with self.store.transaction() as writer:
            try:
                _check_lease(writer, lease, self.clock())
            except StaleRevision:
                return
            writer.execute("UPDATE runs SET state='paused',revision=revision+1,updated_at=? WHERE id=?", (utc_now(), lease.run_id))
            writer.execute("UPDATE tasks SET state='needs_decision',error_json=?,updated_at=? WHERE run_id=? AND state='running'", (canonical_json(error.as_dict()), utc_now(), lease.run_id))
            self.store.append_event(writer, lease.work_id, "decision_required", error.as_dict(), run_id=lease.run_id)

    async def run_once(self) -> bool:
        if self._running:
            raise RuntimeError("a worker instance cannot run two loops concurrently")
        self._running = True
        self._lease_lost = False
        lease = None
        heartbeat = None
        stopped = asyncio.Event()
        try:
            from .graph import PersistentGraph
            graph = PersistentGraph(self)
            graph.require_dependencies()  # Missing extras must not consume/claim a task.
            lease = self.claim_next()
            if lease is None:
                return False
            self._active = asyncio.create_task(graph.run(lease))
            heartbeat = asyncio.create_task(self._keep_alive(lease, stopped))
            try:
                await self._active
            except asyncio.CancelledError:
                if not self._stopping.is_set() and not self._lease_lost:
                    # If outer caller cancelled, propagate; takeover is already fenced in DB.
                    with self.store.connection() as reader:
                        row = reader.execute("SELECT owner_epoch,cancel_requested FROM runs WHERE id=?", (lease.run_id,)).fetchone()
                    if row and row[0] == lease.owner_epoch and not row[1]:
                        raise
            except Exception:
                self._pause(lease, ProductionError("checkpoint_failed", "执行检查点无法安全恢复，已保留领域记录", requires_decision=True))
            return True
        finally:
            stopped.set()
            if heartbeat:
                await heartbeat
            self._active = None
            if lease:
                self._release(lease)
            self._running = False

    async def run_forever(self, stop_event: asyncio.Event | None = None):
        while not self._stopping.is_set() and not (stop_event and stop_event.is_set()):
            await self.run_once()
            if self._stopping.is_set() or (stop_event and stop_event.is_set()):
                break
            try:
                await asyncio.wait_for(self._stopping.wait(), timeout=self.poll_interval)
            except asyncio.TimeoutError:
                pass

    def stop(self):
        """Service shutdown releases a lease; it is not a Creator cancellation."""
        self._stopping.set()
        if self._active:
            self._active.cancel()

    def status(self) -> list[dict]:
        with self.store.connection() as reader:
            return [dict(row) for row in reader.execute("SELECT id,work_id,kind,state,graph_version,owner_epoch,lease_expires_at,updated_at FROM runs ORDER BY created_at DESC LIMIT 100")]
