"""SQLite domain authority, intentionally independent of Web and workflow engines."""
from __future__ import annotations

from contextlib import contextmanager, nullcontext
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Callable, Iterator
from uuid import uuid4

from .contracts import CommandEnvelope, PlanDocument, WorkCreate, canonical_json, fingerprint
from .errors import Conflict, MigrationError, NotFound, ProductionError, StaleRevision
from .migrations import MIGRATIONS

DATABASE_NAME = "production.sqlite3"
SCHEMA_VERSION = max(MIGRATIONS)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def new_id(prefix: str = "") -> str:
    return f"{prefix}_{uuid4().hex}" if prefix else uuid4().hex


def _statements(script: str) -> Iterator[str]:
    """Keep triggers intact without executescript's implicit transaction commit."""
    pending = ""
    for line in script.splitlines(keepends=True):
        pending += line
        if sqlite3.complete_statement(pending):
            yield pending
            pending = ""
    if pending.strip():
        raise MigrationError("数据库迁移脚本不完整")


def _constraint_error(error: sqlite3.IntegrityError) -> Conflict:
    known = {
        "plan_immutable": "方案修订不可原地改写，请创建新修订",
        "channel_profile_mismatch": "频道与所选画像不一致",
        "director_default_unavailable": "默认导演必须是频道关联且已接受的有效版本",
        "operation_identity_immutable": "既有外部操作的请求身份不可修改",
        "cross_run_dependency": "任务依赖不属于同一运行",
    }
    message = str(error)
    return Conflict(known.get(message, "记录违反身份、引用或状态约束"), code="constraint_conflict")


class Store:
    def __init__(self, db_path: Path | str, *, busy_timeout_ms: int = 5000):
        self.path = Path(db_path).expanduser().resolve()
        self.db_path = self.path
        if not 1 <= busy_timeout_ms <= 60000:
            raise ValueError("busy_timeout_ms must be between 1 and 60000")
        self.busy_timeout_ms = int(busy_timeout_ms)

    def _connect(self, *, create: bool = False, readonly: bool = False) -> sqlite3.Connection:
        mode = "ro" if readonly else "rwc" if create else "rw"
        connection = sqlite3.connect(
            self.path.as_uri() + f"?mode={mode}", uri=True,
            timeout=self.busy_timeout_ms / 1000, isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(f"PRAGMA busy_timeout={self.busy_timeout_ms}")
        return connection

    def initialize(self) -> None:
        """Explicitly initialize/migrate only this configured database.

        A failed migration rolls back all its DDL/data. Existing user-version
        databases newer than this implementation are never rewritten.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = self._connect(create=True)
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute("PRAGMA user_version").fetchone()[0]
            if current > SCHEMA_VERSION:
                raise MigrationError("数据库版本高于当前程序，V2 写入已停止")
            for version in range(current + 1, SCHEMA_VERSION + 1):
                if version not in MIGRATIONS:
                    raise MigrationError("缺少所需数据库迁移")
                for statement in _statements(MIGRATIONS[version]):
                    connection.execute(statement)
                connection.execute(f"PRAGMA user_version={version}")
            if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise MigrationError("数据库存在无效引用，V2 写入已停止")
            connection.commit()
        except Exception as error:
            connection.rollback()
            if isinstance(error, MigrationError):
                raise
            raise MigrationError() from error
        finally:
            connection.close()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """Read-only, consistent snapshot; callers cannot silently mutate it."""
        connection = self._connect(readonly=True)
        try:
            connection.execute("BEGIN")
            yield connection
        finally:
            connection.rollback()
            connection.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except sqlite3.IntegrityError as error:
            connection.rollback()
            raise _constraint_error(error) from error
        except sqlite3.OperationalError as error:
            connection.rollback()
            raise ProductionError("storage_unavailable", "作品存储暂不可写，请稍后重试",
                                  status_code=503, retryable=True) from error
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def execute_command(self, command_id: str, request: dict, action: Callable[[sqlite3.Connection], dict],
                        *, work_id: str | None = None, expected_revision: int | None = None, connection=None) -> dict:
        CommandEnvelope(command_id=command_id, expected_revision=expected_revision)
        request_hash = fingerprint({"work_id": work_id, "expected_revision": expected_revision, "request": request})
        with (self.transaction() if connection is None else nullcontext(connection)) as connection:
            prior = connection.execute("SELECT * FROM command_receipts WHERE command_id=?", (command_id,)).fetchone()
            if prior:
                if prior["request_hash"] != request_hash:
                    raise Conflict("同一命令标识不能用于不同请求")
                return json.loads(prior["response_json"])
            if work_id is not None:
                work = self.get_work(work_id, connection=connection)
                if expected_revision is None or work["revision"] != expected_revision:
                    raise StaleRevision()
            response = action(connection)
            if not isinstance(response, dict):
                raise TypeError("command action must return a JSON object")
            encoded = canonical_json(response)
            connection.execute(
                "INSERT INTO command_receipts(command_id,work_id,request_hash,response_json,created_at) VALUES(?,?,?,?,?)",
                (command_id, work_id, request_hash, encoded, utc_now()),
            )
            return json.loads(encoded)

    def get_work(self, work_id: str, *, connection: sqlite3.Connection | None = None) -> dict:
        if connection is None:
            with self.connection() as reader:
                return self.get_work(work_id, connection=reader)
        row = connection.execute("SELECT * FROM works WHERE id=?", (work_id,)).fetchone()
        if row is None:
            raise NotFound("作品不存在")
        return dict(row)

    def list_works(self, *, state: str | None = None, profile_ref: str | None = None,
                   channel_id: str | None = None, after: str | None = None, limit: int = 50) -> list[dict]:
        if not 1 <= limit <= 200:
            raise ValueError("limit must be between 1 and 200")
        clauses, values = [], []
        for key, value in (("state", state), ("profile_ref", profile_ref), ("channel_id", channel_id)):
            if value is not None:
                clauses.append(f"{key}=?")
                values.append(value)
        if after:
            clauses.append("id>?")
            values.append(after)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self.connection() as reader:
            return [dict(row) for row in reader.execute(
                "SELECT * FROM works" + where + " ORDER BY id LIMIT ?", (*values, limit))]

    def insert_work(self, connection: sqlite3.Connection, spec: WorkCreate | dict,
                    *, work_id: str | None = None) -> dict:
        spec = WorkCreate.model_validate(spec)
        identifier, now = work_id or new_id("work"), utc_now()
        connection.execute(
            "INSERT INTO works(id,title,input_text,profile_ref,channel_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
            (identifier, spec.title, spec.input_text, spec.profile_ref, spec.channel_id, now, now),
        )
        return self.get_work(identifier, connection=connection)

    def create_work(self, spec: WorkCreate | dict, *, work_id: str | None = None) -> dict:
        with self.transaction() as connection:
            result = self.insert_work(connection, spec, work_id=work_id)
            self.append_event(connection, result["id"], "work_created", {})
            return result

    def bump_work(self, connection: sqlite3.Connection, work_id: str, expected_revision: int, **updates) -> dict:
        allowed = {"title", "input_text", "profile_ref", "channel_id", "state", "current_plan_revision",
                   "active_run_id", "accepted_output_id", "image_limit", "video_limit", "settings_json"}
        if set(updates) - allowed:
            raise ValueError("unsupported work fields")
        if isinstance(updates.get("settings_json"), dict):
            updates["settings_json"] = canonical_json(updates["settings_json"])
        updates["updated_at"] = utc_now()
        assignments = ",".join(f"{key}=?" for key in updates)
        cursor = connection.execute(
            f"UPDATE works SET {assignments},revision=revision+1 WHERE id=? AND revision=?",
            (*updates.values(), work_id, expected_revision),
        )
        if cursor.rowcount != 1:
            if connection.execute("SELECT 1 FROM works WHERE id=?", (work_id,)).fetchone() is None:
                raise NotFound("作品不存在")
            raise StaleRevision()
        return self.get_work(work_id, connection=connection)

    def append_event(self, connection: sqlite3.Connection, work_id: str, kind: str, payload: dict,
                     *, run_id: str | None = None, actor: str = "program") -> int:
        work = self.get_work(work_id, connection=connection)
        seq = connection.execute("SELECT COALESCE(MAX(seq),0)+1 FROM events WHERE work_id=?", (work_id,)).fetchone()[0]
        connection.execute(
            "INSERT INTO events(work_id,seq,kind,run_id,work_revision,actor,payload_json,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (work_id, seq, kind, run_id, work["revision"], actor, canonical_json(payload), utc_now()),
        )
        return seq

    def snapshot(self, work_id: str) -> dict:
        with self.connection() as reader:
            work = self.get_work(work_id, connection=reader)
            cursor = reader.execute("SELECT COALESCE(MAX(seq),0) FROM events WHERE work_id=?", (work_id,)).fetchone()[0]
            return {"work": work, "event_cursor": cursor}

    def events(self, work_id: str, after: int = 0, *, limit: int = 200) -> list[dict]:
        if after < 0 or not 1 <= limit <= 1000:
            raise ValueError("invalid event cursor or limit")
        with self.connection() as reader:
            self.get_work(work_id, connection=reader)
            rows = reader.execute("SELECT * FROM events WHERE work_id=? AND seq>? ORDER BY seq LIMIT ?", (work_id, after, limit))
            result = []
            for row in rows:
                value = dict(row)
                value["payload"] = json.loads(value.pop("payload_json"))
                result.append(value)
            return result

    def save_plan(self, work_id: str, plan: PlanDocument | dict, *, expected_revision: int,
                  connection: sqlite3.Connection | None = None) -> dict:
        document = PlanDocument.model_validate(plan)
        if connection is None:
            with self.transaction() as writer:
                return self.save_plan(work_id, document, expected_revision=expected_revision, connection=writer)
        work = self.get_work(work_id, connection=connection)
        if work["revision"] != expected_revision:
            raise StaleRevision()
        if document.profile_snapshot and document.profile_snapshot.profile_ref != work["profile_ref"]:
            raise Conflict("方案画像依据不属于当前作品")
        for scene in document.scenes:
            for input_id in scene.required_input_ids:
                if connection.execute("SELECT 1 FROM work_inputs WHERE id=? AND work_id=?", (input_id, work_id)).fetchone() is None:
                    raise Conflict("方案引用了不可访问的输入")
        if document.director_revision_id and connection.execute(
            "SELECT 1 FROM director_revisions WHERE id=?", (document.director_revision_id,)).fetchone() is None:
            raise Conflict("导演版本不存在")
        revision = connection.execute("SELECT COALESCE(MAX(revision),0)+1 FROM plan_revisions WHERE work_id=?", (work_id,)).fetchone()[0]
        connection.execute(
            "INSERT INTO plan_revisions(id,work_id,revision,payload_json,plan_hash,created_at) VALUES(?,?,?,?,?,?)",
            (new_id("plan"), work_id, revision, canonical_json(document), fingerprint(document), utc_now()),
        )
        self.bump_work(connection, work_id, expected_revision, current_plan_revision=revision, state="awaiting_confirmation")
        self.append_event(connection, work_id, "plan_created", {"plan_revision": revision})
        return self.get_plan(work_id, revision, connection=connection)

    def get_plan(self, work_id: str, revision: int, *, connection: sqlite3.Connection | None = None) -> dict:
        if connection is None:
            with self.connection() as reader:
                return self.get_plan(work_id, revision, connection=reader)
        row = connection.execute("SELECT * FROM plan_revisions WHERE work_id=? AND revision=?", (work_id, revision)).fetchone()
        if row is None:
            raise NotFound("方案修订不存在")
        return dict(row)

    def backup(self, destination: Path | str) -> None:
        destination = Path(destination).resolve()
        if destination == self.path or destination.exists():
            raise ValueError("backup destination must be a new file")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as source:
            target = sqlite3.connect(destination)
            try:
                source.backup(target)
            finally:
                target.close()
