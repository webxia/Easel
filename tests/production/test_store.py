"""Real SQLite tests: concurrency, rollback, immutable revisions and references."""
from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3

import pytest

from easel.production import store as module
from easel.production.contracts import PlanDocument
from easel.production.errors import Conflict, MigrationError, ProductionError, StaleRevision
from easel.production.store import Store, utc_now


@pytest.fixture
def store(tmp_path):
    result = Store(tmp_path / "private" / "production.sqlite3")
    result.initialize()
    return result


def plan():
    return PlanDocument.model_validate({
        "title": "测试作品", "summary": "摘要", "script": "完整创作表达",
        "scenes": [{"id": "first", "purpose": "表达", "visual": "已有素材"}],
        "settings": {"duration_seconds": 90, "audio_mode": "silent"},
    })


def insert_run(conn, work_id, run_id="run", *, kind="planning", revision=None, state="pending"):
    conn.execute("INSERT INTO runs(id,work_id,kind,state,plan_revision,graph_version,input_fingerprint,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                 (run_id, work_id, kind, state, revision, "v1", "fingerprint", utc_now(), utc_now()))


def insert_artifact(conn, work_id, artifact_id="artifact", **overrides):
    fields = {"id": artifact_id, "work_id": work_id, "kind": "video", "storage_ref": f"works/{work_id}/{artifact_id}.mp4",
              "digest": "a" * 64, "size_bytes": 1, "created_at": utc_now(), **overrides}
    conn.execute(f"INSERT INTO artifacts({','.join(fields)}) VALUES({','.join('?' for _ in fields)})", tuple(fields.values()))


def test_import_and_construction_do_not_initialize_user_data(tmp_path):
    target = tmp_path / "absent" / "production.sqlite3"
    Store(target)
    assert not target.parent.exists()


def test_schema_covers_all_record_families_and_initialization_is_idempotent(store):
    store.initialize()
    with store.connection() as reader:
        tables = {row[0] for row in reader.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"profile_refs", "channels", "directors", "director_revisions", "channel_directors", "works", "work_inputs",
                "plan_revisions", "authorization_grants", "runs", "tasks", "task_dependencies", "operations", "artifacts",
                "artifact_edges", "quality_checks", "reviews", "acceptances", "events", "command_receipts"} <= tables
        assert reader.execute("PRAGMA user_version").fetchone()[0] == module.SCHEMA_VERSION
        assert reader.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert reader.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        with pytest.raises(sqlite3.OperationalError):
            reader.execute("DELETE FROM works")


def test_duplicate_concurrent_command_executes_action_once(store):
    def command():
        def action(conn):
            work = store.insert_work(conn, {"title": "一次创建"})
            store.append_event(conn, work["id"], "created", {})
            return {"work_id": work["id"]}
        return store.execute_command("create_1", {"title": "一次创建"}, action)
    with ThreadPoolExecutor(max_workers=8) as executor:
        responses = list(executor.map(lambda _: command(), range(16)))
    assert all(response == responses[0] for response in responses)
    assert len(store.list_works()) == 1
    assert len(store.events(responses[0]["work_id"])) == 1
    with pytest.raises(Conflict):
        store.execute_command("create_1", {"title": "不同请求"}, lambda _: {})


def test_replayed_update_returns_original_receipt_before_stale_check(store):
    work = store.create_work({"title": "原名"})
    def action(conn):
        result = store.bump_work(conn, work["id"], 1, title="新名")
        store.append_event(conn, work["id"], "renamed", {"title": "新名"})
        return result
    first = store.execute_command("rename", {"title": "新名"}, action, work_id=work["id"], expected_revision=1)
    assert first["revision"] == 2
    assert store.execute_command("rename", {"title": "新名"}, action, work_id=work["id"], expected_revision=1) == first
    with pytest.raises(StaleRevision):
        store.execute_command("another", {"title": "其他"}, lambda _: {}, work_id=work["id"], expected_revision=1)
    assert len(store.events(work["id"])) == 2


def test_command_failure_rolls_back_work_event_and_receipt(store):
    work = store.create_work({"title": "保留"})
    def action(conn):
        store.bump_work(conn, work["id"], 1, title="不应保存")
        store.append_event(conn, work["id"], "bad", {})
        raise RuntimeError("injected failure")
    with pytest.raises(RuntimeError):
        store.execute_command("failed", {}, action, work_id=work["id"], expected_revision=1)
    assert store.get_work(work["id"])["title"] == "保留"
    assert len(store.events(work["id"])) == 1
    with store.connection() as reader:
        assert reader.execute("SELECT COUNT(*) FROM command_receipts").fetchone()[0] == 0


def test_immutable_plan_new_revision_and_snapshot_cursor(store):
    work = store.create_work({"title": "作品"})
    first = store.save_plan(work["id"], plan(), expected_revision=1)
    with store.transaction() as writer:
        writer.execute("UPDATE plan_revisions SET confirmed_at=? WHERE id=?", (utc_now(), first["id"]))
    for sql in ("UPDATE plan_revisions SET payload_json='{}' WHERE id=?", "UPDATE plan_revisions SET confirmed_at=NULL WHERE id=?"):
        with pytest.raises(Conflict):
            with store.transaction() as writer:
                writer.execute(sql, (first["id"],))
    second_plan = plan()
    second_plan.summary = "新的摘要"
    second = store.save_plan(work["id"], second_plan, expected_revision=2)
    assert second["revision"] == 2 and first["plan_hash"] != second["plan_hash"]
    assert json.loads(store.get_plan(work["id"], 1)["payload_json"])["summary"] == "摘要"
    snapshot = store.snapshot(work["id"])
    assert snapshot["work"]["revision"] == 3
    assert snapshot["event_cursor"] == 3
    assert store.events(work["id"], after=2)[0]["payload"]["plan_revision"] == 2


def test_missing_schema_version_cannot_bypass_sqlite_check(store):
    work = store.create_work({"title": "作品"})
    with pytest.raises(Conflict):
        with store.transaction() as writer:
            writer.execute("UPDATE works SET settings_json='{}' WHERE id=?", (work["id"],))


def test_plan_foreign_input_and_foreign_profile_rejected(store):
    work = store.create_work({"title": "无画像"})
    payload = plan().model_dump()
    payload["scenes"][0]["required_input_ids"] = ["foreign_input"]
    with pytest.raises(Conflict):
        store.save_plan(work["id"], payload, expected_revision=1)
    payload = plan().model_dump()
    payload["profile_snapshot"] = {"profile_ref": "other", "content": "private", "content_hash": "a" * 64}
    with pytest.raises(Conflict):
        store.save_plan(work["id"], payload, expected_revision=1)


def test_channel_profile_binding_is_enforced_in_database(store):
    now = utc_now()
    with store.transaction() as writer:
        writer.execute("INSERT INTO profile_refs(id,name,created_at) VALUES('profile_a','A',?)", (now,))
        writer.execute("INSERT INTO profile_refs(id,name,created_at) VALUES('profile_b','B',?)", (now,))
        writer.execute("INSERT INTO channels(id,profile_ref,name,created_at,updated_at) VALUES('channel','profile_a','学习',?,?)", (now, now))
    with pytest.raises(Conflict):
        store.create_work({"title": "wrong", "channel_id": "channel", "profile_ref": "profile_b"})
    assert store.create_work({"title": "right", "channel_id": "channel", "profile_ref": "profile_a"})["profile_ref"] == "profile_a"


def test_only_one_active_run_and_production_requires_confirmed_plan(store):
    work = store.create_work({"title": "作品"})
    planned = store.save_plan(work["id"], plan(), expected_revision=1)
    with pytest.raises(Conflict):
        with store.transaction() as writer:
            insert_run(writer, work["id"], kind="production", revision=1)
    with store.transaction() as writer:
        writer.execute("UPDATE plan_revisions SET confirmed_at=? WHERE id=?", (utc_now(), planned["id"]))
        insert_run(writer, work["id"], kind="production", revision=1)
    with pytest.raises(Conflict):
        with store.transaction() as writer:
            insert_run(writer, work["id"], "other")


def test_output_reference_cannot_point_to_another_work(store):
    first = store.create_work({"title": "第一部"})
    second = store.create_work({"title": "第二部"})
    with store.transaction() as writer:
        insert_artifact(writer, second["id"])
    with pytest.raises(Conflict):
        with store.transaction() as writer:
            store.bump_work(writer, first["id"], 1, accepted_output_id="artifact")


def test_accepted_or_dependent_artifact_cannot_be_removed(store):
    work = store.create_work({"title": "作品"})
    with store.transaction() as writer:
        insert_artifact(writer, work["id"], output_revision=1, displayable=1, quality_state="passed")
        writer.execute("INSERT INTO acceptances(id,work_id,output_id,source,created_at) VALUES('accepted',?,'artifact','explicit-user',?)", (work["id"], utc_now()))
    with pytest.raises(Conflict):
        with store.transaction() as writer:
            writer.execute("DELETE FROM artifacts WHERE id='artifact'")
    with pytest.raises(Conflict):
        with store.transaction() as writer:
            writer.execute("UPDATE artifacts SET digest=? WHERE id='artifact'", ("b" * 64,))


def test_unchecked_output_cannot_be_accepted(store):
    work = store.create_work({"title": "作品"})
    with store.transaction() as writer:
        insert_artifact(writer, work["id"], output_revision=1, displayable=1)
    with pytest.raises(Conflict):
        with store.transaction() as writer:
            writer.execute("INSERT INTO acceptances(id,work_id,output_id,source,created_at) VALUES('accepted',?,'artifact','explicit-user',?)", (work["id"], utc_now()))


def test_failed_forward_migration_preserves_previous_data(store, monkeypatch):
    work = store.create_work({"title": "不能丢"})
    previous = module.SCHEMA_VERSION
    monkeypatch.setattr(module, "SCHEMA_VERSION", previous+1)
    monkeypatch.setattr(module, "MIGRATIONS", {**module.MIGRATIONS, previous+1: "CREATE TABLE partial(id TEXT);\nINSERT INTO missing_table VALUES(1);\n"})
    with pytest.raises(MigrationError):
        store.initialize()
    assert store.get_work(work["id"])["title"] == "不能丢"
    with store.connection() as reader:
        assert reader.execute("PRAGMA user_version").fetchone()[0] == previous
        assert reader.execute("SELECT 1 FROM sqlite_master WHERE name='partial'").fetchone() is None


def test_newer_database_refuses_downgrade(store):
    with store.transaction() as writer:
        writer.execute("PRAGMA user_version=999")
    with pytest.raises(MigrationError):
        store.initialize()


def test_online_backup_captures_wal_data(store, tmp_path):
    work = store.create_work({"title": "备份"})
    backup = tmp_path / "backup.sqlite3"
    store.backup(backup)
    assert Store(backup).get_work(work["id"])["title"] == "备份"


def test_settings_update_cannot_replace_bound_source_session(store):
    work = store.create_work({"title": "作品"})
    with store.transaction() as writer:
        store.bump_work(writer, work["id"], 1, settings_json={"schema_version": 1, "subtitles": {"size": 60}})
    assert json.loads(store.get_work(work["id"])["settings_json"])["subtitles"]["size"] == 60
    with pytest.raises(ValueError):
        with store.transaction() as writer:
            store.bump_work(writer, work["id"], 2, source_session_id="other")
