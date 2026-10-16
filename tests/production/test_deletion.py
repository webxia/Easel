import hashlib
from pathlib import Path

import pytest

from easel.production.deletion import DeletionService
from easel.production.errors import NotFound, StaleRevision
from easel.production.store import Store, utc_now
from .test_store import insert_artifact


@pytest.fixture
def env(tmp_path):
    outputs = tmp_path / "outputs"
    store = Store(outputs / "_production" / "production.sqlite3")
    store.initialize()
    work = store.create_work({"title": "删除影响"})
    return store, DeletionService(store, outputs=outputs), work["id"], outputs


def asset(env, id, *, work_id=None, revision=None, ref=None, content=None):
    store, deletion, source_work, outputs = env
    work_id = work_id or source_work
    ref = ref or f"works/{work_id}/artifacts/{id}.mp4"
    path = outputs / ref
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(content or id.encode())
    with store.transaction() as writer:
        insert_artifact(writer, work_id, id, storage_ref=ref, digest=hashlib.sha256(path.read_bytes()).hexdigest(),
                        size_bytes=path.stat().st_size, output_revision=revision, displayable=1, quality_state="passed")
    return path


def execute(deletion, work_id, output_id=None, command_id="delete_command"):
    preview = deletion.preview(work_id, output_id)
    return deletion.execute(command_id, work_id, preview["expected_revision"], preview["preview_hash"], output_id)


def test_delete_accepted_version_clears_choice_preserves_other_versions_and_shared_inputs(env):
    store, deletion, work_id, outputs = env
    old = asset(env, "old", revision=1)
    current = asset(env, "current", revision=2)
    shared = asset(env, "shared")
    exclusive = asset(env, "exclusive")
    with store.transaction() as writer:
        writer.executemany("INSERT INTO artifact_edges(artifact_id,dependency_id,role) VALUES(?,?,'source')", [("old", "shared"), ("current", "shared"), ("old", "exclusive")])
        writer.execute("UPDATE works SET accepted_output_id='old' WHERE id=?", (work_id,))
        writer.execute("INSERT INTO acceptances(id,work_id,output_id,source,created_at) VALUES('accept',?,'old','explicit',?)", (work_id, utc_now()))
    preview = deletion.preview(work_id, "old")
    assert preview["clears_acceptance"]
    assert preview["preserved_artifact_ids"] == ["shared"]
    receipt = deletion.execute("delete", work_id, preview["expected_revision"], preview["preview_hash"], "old")
    assert receipt["accepted_selection_removed"]
    assert store.get_work(work_id)["accepted_output_id"] is None
    assert deletion.reconcile_cleanup()["deleted"] == 2
    assert not old.exists() and not exclusive.exists()
    assert current.exists() and shared.exists()


def test_deleted_work_keeps_inflight_identity_and_defers_files_until_receipt(env):
    from .test_operations import owned_request
    from easel.production.operations import OperationService
    from easel.production.providers.base import ProviderResult
    store, deletion, _, outputs = env
    spec = owned_request(store)
    ops = OperationService(store, clock=lambda: 1000)
    ops.reserve(**spec)
    assert ops.mark_sending(spec["operation_id"], 1)
    path = asset(env, "existing", work_id=spec["work_id"], revision=1)
    preview = deletion.preview(spec["work_id"])
    assert preview["deferred_cleanup"] and preview["will_cancel_run"]
    execute(deletion, spec["work_id"])
    assert store.get_work(spec["work_id"])["deleted_at"]
    assert deletion.reconcile_cleanup()["deferred"] == 1
    assert path.exists()
    assert ops.receive(spec["operation_id"], ProviderResult("succeeded", result={"receipt": "kept"}))["state"] == "succeeded"
    assert deletion.reconcile_cleanup()["deleted"] == 1
    assert ops.get(spec["operation_id"])["receipt"]["result"] == {"receipt": "kept"}


def test_stale_preview_rejected_for_changed_version_or_new_dependency(env):
    store, deletion, work_id, _ = env
    old = asset(env, "old", revision=1)
    preview = deletion.preview(work_id, "old")
    asset(env, "new", revision=2)
    with store.transaction() as writer:
        writer.execute("INSERT INTO artifact_edges VALUES('new','old','source')")
    with pytest.raises(StaleRevision):
        deletion.execute("stale", work_id, preview["expected_revision"], preview["preview_hash"], "old")
    assert old.exists()


def test_replayed_delete_returns_original_receipt_after_tombstone(env):
    store, deletion, work_id, _ = env
    asset(env, "one", revision=1)
    preview = deletion.preview(work_id)
    args = ("same", work_id, preview["expected_revision"], preview["preview_hash"])
    assert deletion.execute(*args) == deletion.execute(*args)
    with pytest.raises(NotFound):
        deletion.preview(work_id)
    assert deletion.reconcile_cleanup()["deleted"] == 1
    assert deletion.reconcile_cleanup()["deleted"] == 0


def test_shared_file_in_other_work_is_never_unlinked(env):
    store, deletion, work_id, _ = env
    path = asset(env, "one", revision=1)
    other = store.create_work({"title": "另一个作品"})
    asset(env, "copy", work_id=other["id"], ref=f"works/{work_id}/artifacts/one.mp4", revision=1)
    execute(deletion, work_id)
    assert deletion.reconcile_cleanup()["retained"] == 1
    assert path.exists()


def test_inbox_and_input_originals_are_preserved(env):
    store, deletion, work_id, _ = env
    inbox = asset(env, "inbox", ref="inbox/user/video.mp4")
    original = asset(env, "original")
    with store.transaction() as writer:
        writer.execute("INSERT INTO work_inputs(id,work_id,kind,usage,source_ref,digest,created_at) VALUES('original-input',?,'video','must_use',?,?,?)",
                       (work_id, f"works/{work_id}/artifacts/original.mp4", "a"*64, utc_now()))
    execute(deletion, work_id)
    assert deletion.reconcile_cleanup()["retained"] == 2
    assert inbox.exists() and original.exists()


def test_changed_file_and_symlink_are_not_deleted(env):
    store, deletion, work_id, outputs = env
    changed = asset(env, "changed")
    link = asset(env, "link")
    target = outputs.parent / "keep-personal-file.mp4"
    target.write_bytes(link.read_bytes())
    link.unlink()
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlinks unavailable")
    changed.write_bytes(b"new-user-data")
    execute(deletion, work_id)
    assert deletion.reconcile_cleanup()["retained"] == 2
    assert changed.read_bytes() == b"new-user-data"
    assert target.exists() and link.is_symlink()


def test_director_trial_and_its_dependencies_survive_work_deletion(env):
    store, deletion, work_id, _ = env
    trial = asset(env, "trial", revision=1)
    source = asset(env, "source")
    with store.transaction() as writer:
        writer.execute("INSERT INTO artifact_edges VALUES('trial','source','source')")
        writer.execute("INSERT INTO directors(id,name,created_at,updated_at) VALUES('director','风格',?,?)", (utc_now(), utc_now()))
        writer.execute("INSERT INTO director_revisions(id,director_id,revision,style_json,trial_artifact_id,created_at) VALUES('style','director',1,'{\"schema_version\":1}','trial',?)", (utc_now(),))
    execute(deletion, work_id)
    assert deletion.reconcile_cleanup()["retained"] == 2
    assert trial.exists() and source.exists()


def test_unrelated_output_cannot_be_deleted(env):
    store, deletion, work_id, _ = env
    other = store.create_work({"title": "别的作品"})
    asset(env, "other", work_id=other["id"], revision=1)
    with pytest.raises(NotFound):
        deletion.preview(work_id, "other")


def test_schema_one_upgrades_without_changing_existing_data(tmp_path, monkeypatch):
    from easel.production import store as module
    store = Store(tmp_path / "old.sqlite3")
    with monkeypatch.context() as scoped:
        scoped.setattr(module, "SCHEMA_VERSION", 1)
        store.initialize()
        work = store.create_work({"title": "保留"})
    store.initialize()
    assert store.get_work(work["id"])["deleted_at"] is None
    assert store.get_work(work["id"])["title"] == "保留"


def test_material_reference_release_failure_is_persisted_and_retried(env):
    from easel.production.contracts import canonical_json
    store, deletion, work_id, _ = env
    path = asset(env, "material")
    with store.transaction() as writer:
        writer.execute("UPDATE artifacts SET metadata_json=? WHERE id='material'", (canonical_json({"schema_version": 1, "asset_ref": "library_asset", "material_scope": {"owner_id": "local", "profile_ref": None}}),))
    class Library:
        failing = True
        calls = []
        def release_reference(self, asset_ref, reference_id, *, visibility, context):
            if self.failing:
                raise OSError("temporary independent catalog failure")
            self.calls.append((asset_ref, reference_id, context.work_id, visibility.profile_ref))
    library = Library()
    deletion.materials = library
    execute(deletion, work_id)
    assert deletion.reconcile_cleanup()["deferred"] == 1
    assert path.exists()
    with store.connection() as reader:
        assert reader.execute("SELECT reason FROM cleanup_jobs").fetchone()[0] == "material_release_pending"
    library.failing = False
    assert deletion.reconcile_cleanup()["deleted"] == 1
    assert library.calls == [("library_asset", "material", work_id, None)]
    assert not path.exists()


def test_runtime_cancel_reaches_renderer_and_keeps_racing_completed_result(env):
    import asyncio
    from types import SimpleNamespace
    from easel.production.runtime import ProductionRuntime
    from easel.production.worker import Worker
    from .test_worker import seed_run
    store, deletion, _, outputs = env
    work_id, run_id, task_id = seed_run(store, kind="production", first="render")
    with store.transaction() as writer:
        writer.execute("UPDATE runs SET cancel_requested=1,state='cancelled' WHERE id=?", (run_id,))
        writer.execute("UPDATE tasks SET state='cancelled' WHERE id=?", (task_id,))
        writer.execute("UPDATE works SET state='cancelled' WHERE id=?", (work_id,))
    path = outputs / "_production" / "renders" / task_id / "final.mp4"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"finished just as cancellation arrived")
    class Editor:
        calls = 0
        status = "running"
        def observe(self, job_id):
            return SimpleNamespace(job_id=job_id, status=self.status)
        def cancel(self, job_id):
            self.calls += 1
            self.status = "completed"
            return self.observe(job_id)
        def collect(self, job_id):
            return SimpleNamespace(video_path=path, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    editor = Editor()
    service = SimpleNamespace(store=store, outputs=outputs)
    runtime = ProductionRuntime(service, Worker(store, {}), None, SimpleNamespace(editor=editor))
    asyncio.run(runtime.maintenance_once())
    asyncio.run(runtime.maintenance_once())
    with store.connection() as reader:
        records = reader.execute("SELECT * FROM artifacts WHERE work_id=?", (work_id,)).fetchall()
        assert len(records) == 1
        assert records[0]["kind"] == "render_receipt" and records[0]["displayable"] == 0
        assert reader.execute("SELECT state FROM runs WHERE id=?", (run_id,)).fetchone()[0] == "cancelled"
    assert editor.calls == 1 and path.exists()
    assert store.get_work(work_id)["accepted_output_id"] is None


def test_service_shutdown_does_not_cancel_independent_render(env):
    from types import SimpleNamespace
    from easel.production.runtime import ProductionRuntime
    from easel.production.worker import Worker
    store, _, _, outputs = env
    editor = SimpleNamespace(cancel=lambda *_: pytest.fail("service shutdown is not user cancel"))
    worker = Worker(store, {})
    runtime = ProductionRuntime(SimpleNamespace(store=store, outputs=outputs), worker, None, SimpleNamespace(editor=editor))
    runtime.stop()
    assert worker._stopping.is_set()


def test_deleted_work_and_artifact_are_unavailable_before_physical_cleanup(env):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from easel.production.errors import ProductionError
    from easel.production.service import WorkService
    from web.production_api import create_router, production_error_handler
    store, _, work_id, outputs = env
    path = asset(env, "version", revision=1)
    service = WorkService(store, outputs=outputs, profiles=outputs.parent / "profiles")
    app = FastAPI()
    app.add_exception_handler(ProductionError, production_error_handler)
    app.include_router(create_router(lambda: service))
    client = TestClient(app)
    prefix = "/api/production"
    assert client.get(prefix+"/artifacts/version/content").status_code == 200
    preview = client.get(prefix+f"/works/{work_id}/deletion-preview").json()
    response = client.post(prefix+f"/works/{work_id}/delete", json={"command_id": "api_delete", "expected_revision": preview["expected_revision"], "payload": {"preview_hash": preview["preview_hash"]}})
    assert response.status_code == 200, response.text
    assert path.exists()  # Domain authorization is effective before file cleanup.
    assert client.get(prefix+f"/works/{work_id}").status_code == 404
    assert client.get(prefix+"/artifacts/version/content").status_code == 404
    assert not client.get(prefix+"/works").json()["items"]


def test_temporarily_locked_file_remains_in_the_cleanup_queue(env, monkeypatch):
    _, deletion, work_id, _ = env
    path = asset(env, "locked")
    execute(deletion, work_id)
    original = Path.unlink
    def locked(target, *args, **kwargs):
        if target == path:
            raise PermissionError("simulated Windows open reader")
        return original(target, *args, **kwargs)
    with monkeypatch.context() as scoped:
        scoped.setattr(Path, "unlink", locked)
        assert deletion.reconcile_cleanup()["deferred"] == 1
    assert path.exists()
    assert deletion.reconcile_cleanup()["deleted"] == 1
    assert not path.exists()
