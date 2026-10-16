"""One durable dispatch boundary for image/video and auditable model/voice calls."""
from __future__ import annotations

import json
import sqlite3
import time

from .contracts import OperationKind, canonical_json, fingerprint
from .errors import Conflict, NotFound, ProductionError, StaleRevision
from .providers.base import GenerationProvider, ProviderResult, SubmissionNotSent
from .store import Store, utc_now

_OCCUPIED = ("reserved", "sending", "submitted", "unknown", "succeeded", "failed_after_submit")
_TERMINAL = {"succeeded", "failed_after_submit", "failed_before_submit", "cancelled"}


def _denied(message: str, *, code: str = "permission_missing"):
    raise ProductionError(code, message, requires_decision=True)


class OperationService:
    def __init__(self, store: Store, *, clock=time.time):
        self.store, self.clock = store, clock

    @staticmethod
    def _row(conn: sqlite3.Connection, table: str, identifier: str) -> dict:
        row = conn.execute(f"SELECT * FROM {table} WHERE id=?", (identifier,)).fetchone()
        if row is None:
            raise NotFound("操作所需记录不存在")
        return dict(row)

    def get(self, operation_id: str) -> dict:
        with self.store.connection() as reader:
            result = self._row(reader, "operations", operation_id)
            result["request"] = json.loads(result["request_json"])
            result["receipt"] = json.loads(result["receipt_json"]) if result["receipt_json"] else None
            return result

    def _authorize(self, conn, spec: dict, owner_epoch: int, *, exclude_id: str | None = None):
        work = self._row(conn, "works", spec["work_id"])
        run = self._row(conn, "runs", spec["run_id"])
        task = self._row(conn, "tasks", spec["task_id"])
        if (run["work_id"] != work["id"] or task["run_id"] != run["id"] or task["work_id"] != work["id"]
                or work["active_run_id"] != run["id"] or task["plan_revision"] != run["plan_revision"]):
            raise StaleRevision("操作不属于当前制作修订")
        if work["state"] == "cancelled" or run["cancel_requested"]:
            _denied("作品已取消，不再派发新调用", code="cancelled")
        if (run["state"] != "running" or task["state"] != "running" or not run["owner_id"]
                or run["owner_epoch"] != owner_epoch or task["owner_epoch"] != owner_epoch
                or run["lease_expires_at"] is None or run["lease_expires_at"] <= self.clock()):
            raise StaleRevision("执行所有权已变化，不能发送新调用")
        if run["kind"] != "planning" and work["current_plan_revision"] != run["plan_revision"]:
            raise StaleRevision("当前方案已变化")
        grant = self._row(conn, "authorization_grants", spec["grant_id"])
        if grant["work_id"] != work["id"] or grant["revoked_at"]:
            _denied("服务授权已撤销或不属于本作品")
        selected = {key: spec[key] for key in ("provider", "model", "mode")}
        if selected not in json.loads(grant["services_json"]):
            _denied("本次服务、模型或模式尚未授权")
        if grant["purpose"] == "production":
            if grant["plan_revision"] != run["plan_revision"] or run["kind"] == "planning":
                _denied("生产授权不属于当前已确认方案")
            plan = conn.execute("SELECT confirmed_at FROM plan_revisions WHERE work_id=? AND revision=?",
                                (work["id"], run["plan_revision"])).fetchone()
            if plan is None or not plan[0]:
                _denied("生产方案尚未确认")
        elif grant["purpose"] == "planning":
            if run["kind"] != "planning" or spec["kind"] != "MODEL":
                _denied("规划授权只能用于规划模型调用")
        elif grant["purpose"] == "preview":
            if spec["kind"] != "VOICE" or task["kind"] != "voice_preview":
                _denied("试听授权只能用于具名声音试听")
            if not grant["target_ref"] or grant["target_ref"] not in {task["id"], run["target_ref"]}:
                _denied("试听授权未绑定本次试听")
        if grant["target_ref"] and grant["purpose"] == "planning" and grant["target_ref"] not in {
            task["id"], run["id"], run["target_ref"], run["input_fingerprint"]
        }:
            _denied("规划授权未绑定本次输入")
        if spec["kind"] in {"IMAGE", "VIDEO"}:
            if grant["purpose"] != "production" or not grant["allow_ai"]:
                _denied("当前授权不允许 AI 补料")
            parameters = [work["id"], spec["kind"], *_OCCUPIED]
            query = "SELECT COUNT(*) FROM operations WHERE work_id=? AND kind=? AND state IN (" + ",".join("?" for _ in _OCCUPIED) + ")"
            if exclude_id:
                query += " AND id!=?"
                parameters.append(exclude_id)
            occupied = conn.execute(query, parameters).fetchone()[0]
            if occupied >= work[spec["kind"].lower() + "_limit"]:
                _denied("生成次数不足，请申请追加", code="quota_exhausted")

    def reserve(self, *, operation_id: str, work_id: str, run_id: str, task_id: str, grant_id: str,
                kind: str, provider: str, model: str, mode: str, config_version: str,
                request: dict, owner_epoch: int, request_key: str | None = None) -> dict:
        kind = OperationKind(kind).value
        if not operation_id or not all((provider, model, mode, config_version)) or not isinstance(request, dict):
            raise ValueError("operation identity, service and JSON request are required")
        spec = {"id": operation_id, "work_id": work_id, "run_id": run_id, "task_id": task_id,
                "grant_id": grant_id, "kind": kind, "provider": provider, "model": model, "mode": mode,
                "config_version": config_version, "request_key": request_key or operation_id,
                "input_hash": fingerprint(request), "request_json": canonical_json(request)}
        with self.store.transaction() as writer:
            previous = writer.execute("SELECT * FROM operations WHERE id=?", (operation_id,)).fetchone()
            if previous is not None:
                if any(previous[key] != value for key, value in spec.items()):
                    raise Conflict("同一操作标识不能改写请求或授权")
                # Replaying an intent is read-only; dispatch still rechecks the live owner.
            else:
                self._authorize(writer, spec, owner_epoch)
                fields = {**spec, "owner_epoch": owner_epoch, "created_at": utc_now(), "updated_at": utc_now()}
                writer.execute(f"INSERT INTO operations({','.join(fields)}) VALUES({','.join('?' for _ in fields)})", tuple(fields.values()))
                self.store.append_event(writer, work_id, "operation_reserved", {"operation_id": operation_id, "kind": kind}, run_id=run_id)
        return self.get(operation_id)

    def mark_sending(self, operation_id: str, owner_epoch: int) -> bool:
        """True grants exactly one local send window; False never authorizes a send."""
        with self.store.transaction() as writer:
            operation = self._row(writer, "operations", operation_id)
            if operation["state"] != "reserved":
                return False
            self._authorize(writer, operation, owner_epoch, exclude_id=operation_id)
            changed = writer.execute("UPDATE operations SET state='sending',owner_epoch=?,updated_at=?,revision=revision+1 WHERE id=? AND state='reserved'",
                                     (owner_epoch, utc_now(), operation_id)).rowcount
            if changed:
                self.store.append_event(writer, operation["work_id"], "operation_sending", {"operation_id": operation_id, "kind": operation["kind"]}, run_id=operation["run_id"])
            return changed == 1

    def mark_unknown(self, operation_id: str) -> dict:
        with self.store.transaction() as writer:
            operation = self._row(writer, "operations", operation_id)
            # A failed poll cannot erase an already known submission.
            if operation["state"] == "sending":
                writer.execute("UPDATE operations SET state='unknown',error_code='result_unknown',updated_at=?,revision=revision+1 WHERE id=?", (utc_now(), operation_id))
                self.store.append_event(writer, operation["work_id"], "operation_waiting", {"operation_id": operation_id, "state": "unknown"}, run_id=operation["run_id"])
        return self.get(operation_id)

    def mark_not_submitted(self, operation_id: str) -> dict:
        """Only call with affirmative transport evidence, never from a lookup miss."""
        with self.store.transaction() as writer:
            operation = self._row(writer, "operations", operation_id)
            if operation["state"] not in {"reserved", "sending", "failed_before_submit"}:
                raise Conflict("已有提交或未知结果，不能释放次数")
            if operation["state"] != "failed_before_submit":
                writer.execute("UPDATE operations SET state='failed_before_submit',updated_at=?,revision=revision+1 WHERE id=?", (utc_now(), operation_id))
                self.store.append_event(writer, operation["work_id"], "operation_not_submitted", {"operation_id": operation_id}, run_id=operation["run_id"])
        return self.get(operation_id)

    def mark_submitted(self, operation_id: str, *, task_id: str | None = None, result: dict | None = None) -> dict:
        return self.receive(operation_id, ProviderResult("submitted", task_id=task_id, result=result or {}))

    def receive(self, operation_id: str, receipt: ProviderResult) -> dict:
        if receipt.state in {"unknown", "not_found"}:
            return self.mark_unknown(operation_id)
        state = {"submitted": "submitted", "succeeded": "succeeded", "failed": "failed_after_submit"}[receipt.state]
        encoded = canonical_json({"state": receipt.state, "task_id": receipt.task_id, "result": receipt.result})
        with self.store.transaction() as writer:
            operation = self._row(writer, "operations", operation_id)
            if operation["state"] in _TERMINAL:
                if operation["state"] == state and operation["receipt_json"] == encoded:
                    return self.get(operation_id)
                raise Conflict("终态操作不能被不同回执覆盖")
            if operation["state"] not in {"sending", "unknown", "submitted"}:
                raise Conflict("未开始发送的操作不能接收外部成功回执")
            if operation["provider_task_id"] and receipt.task_id and operation["provider_task_id"] != receipt.task_id:
                raise Conflict("回执属于不同的外部任务")
            if operation["state"] == state and operation["receipt_json"] == encoded:
                return self.get(operation_id)
            writer.execute("""UPDATE operations SET state=?,provider_task_id=COALESCE(provider_task_id,?),receipt_json=?,
                              submitted_at=COALESCE(submitted_at,?),error_code=NULL,updated_at=?,revision=revision+1 WHERE id=?""",
                           (state, receipt.task_id, encoded, utc_now(), utc_now(), operation_id))
            # Receipt reception intentionally does not require a still-live worker/grant.
            self.store.append_event(writer, operation["work_id"], "operation_observed", {"operation_id": operation_id, "state": state, "kind": operation["kind"]}, run_id=operation["run_id"])
        return self.get(operation_id)

    def submit(self, operation_id: str, provider: GenerationProvider, *, owner_epoch: int) -> dict:
        self._check_provider(self.get(operation_id), provider)
        if not self.mark_sending(operation_id, owner_epoch):
            return self.get(operation_id)
        operation = self.get(operation_id)
        try:
            receipt = provider.submit(operation["request"], request_key=operation["request_key"])
        except SubmissionNotSent:
            return self.mark_not_submitted(operation_id)
        except Exception:
            return self.mark_unknown(operation_id)
        return self.receive(operation_id, receipt)

    def observe(self, operation_id: str, provider: GenerationProvider) -> dict:
        operation = self.get(operation_id)
        self._check_provider(operation, provider)
        if operation["state"] in _TERMINAL or operation["state"] == "reserved":
            return operation
        capabilities = provider.capabilities
        if not ((operation["provider_task_id"] and capabilities.query_by_task_id) or capabilities.query_by_request_key):
            return self.mark_unknown(operation_id)
        try:
            receipt = provider.observe(task_id=operation["provider_task_id"], request_key=operation["request_key"])
        except Exception:
            return self.mark_unknown(operation_id)
        return self.receive(operation_id, receipt)

    @staticmethod
    def _check_provider(operation: dict, provider: GenerationProvider) -> None:
        if any(getattr(provider, attr, None) != operation[column] for attr, column in (
            ("provider_id", "provider"), ("model", "model"), ("mode", "mode")
        )):
            _denied("实际服务配置与本次操作授权不一致", code="provider_mismatch")

    def quota(self, work_id: str) -> dict:
        with self.store.connection() as reader:
            work = self.store.get_work(work_id, connection=reader)
            result = {}
            for kind in ("IMAGE", "VIDEO"):
                states = [row[0] for row in reader.execute("SELECT state FROM operations WHERE work_id=? AND kind=?", (work_id, kind))]
                used = sum(state in {"submitted", "succeeded", "failed_after_submit"} for state in states)
                unknown = sum(state in {"sending", "unknown"} for state in states)
                reserved = states.count("reserved")
                limit = work[kind.lower() + "_limit"]
                result[kind] = {"limit": limit, "used": used, "unknown": unknown, "reserved": reserved,
                                "available": max(0, limit-used-unknown-reserved)}
            return result
