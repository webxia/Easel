"""Explicit deletion previews and deferred, reference-aware local file cleanup."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath

from .contracts import fingerprint
from .errors import NotFound, StaleRevision
from .store import Store, new_id, utc_now

_INFLIGHT = ("sending", "submitted", "unknown")


class DeletionService:
    def __init__(self, store: Store, *, outputs: Path | str, materials=None):
        self.store = store
        self.outputs = Path(outputs).absolute()
        self.materials = materials

    def _impact(self, connection, work_id, output_id):
        work = self.store.get_work(work_id, connection=connection)
        if work["deleted_at"]:
            raise NotFound("作品已删除")
        artifacts = {row["id"]: dict(row) for row in connection.execute("SELECT * FROM artifacts WHERE work_id=? AND deleted_at IS NULL", (work_id,))}
        if output_id and (output_id not in artifacts or artifacts[output_id]["output_revision"] is None):
            raise NotFound("指定历史版本不存在")
        candidates = set(artifacts) if not output_id else {output_id}
        edges = [(row[0], row[1]) for row in connection.execute("SELECT artifact_id,dependency_id FROM artifact_edges")]
        if output_id:
            while True:
                expanded = candidates | {dependency for parent, dependency in edges if parent in candidates and dependency in artifacts}
                if expanded == candidates:
                    break
                candidates = expanded
        protected = {r[0] for r in connection.execute("SELECT d.output_id FROM publication_drafts d WHERE d.state='draft' OR EXISTS(SELECT 1 FROM publication_attempts p WHERE p.draft_id=d.id AND p.state IN ('sending','unknown'))")}
        if candidates & protected:
            from .service import fail
            fail('publication_reference', '此版本有待发布或待核实记录；请保留文件供发布和核实。未提交草稿可先取消。', 409)
        all_live = {row[0] for row in connection.execute("SELECT a.id FROM artifacts a JOIN works w ON w.id=a.work_id WHERE a.deleted_at IS NULL AND w.deleted_at IS NULL")}
        director_refs = {row[0] for row in connection.execute("SELECT trial_artifact_id FROM director_revisions WHERE trial_artifact_id IS NOT NULL")}
        preserved = {dependency for parent, dependency in edges if parent in all_live-candidates and dependency in candidates}
        preserved |= director_refs & candidates
        if output_id:
            # Retaining a shared dependency also retains its own prerequisites.
            while True:
                expanded = preserved | {dependency for parent, dependency in edges if parent in preserved and dependency in candidates}
                if expanded == preserved:
                    break
                preserved = expanded
            removed = (candidates-preserved) | {output_id}
        else:
            removed = candidates
        inflight = [dict(row) for row in connection.execute("SELECT id,kind,state,revision FROM operations WHERE work_id=? AND state IN ('sending','submitted','unknown') ORDER BY id", (work_id,))]
        outputs = [{"id": value["id"], "output_revision": value["output_revision"], "accepted": value["id"] == work["accepted_output_id"]}
                   for value in artifacts.values() if value["output_revision"] is not None and value["id"] in removed]
        active = [dict(row) for row in connection.execute("SELECT id,state,revision FROM runs WHERE work_id=? AND state IN ('pending','running','waiting_external','needs_decision','paused') ORDER BY id", (work_id,))]
        public = {"work_id": work_id, "output_id": output_id, "scope": "output" if output_id else "work",
                  "expected_revision": work["revision"], "outputs": sorted(outputs, key=lambda item: item["id"]),
                  "artifact_ids": sorted(removed), "preserved_artifact_ids": sorted(preserved),
                  "clears_acceptance": work["accepted_output_id"] in removed,
                  "inflight_operations": inflight, "active_runs": active,
                  "deferred_cleanup": bool(inflight or (output_id and active)),
                  "will_cancel_run": not output_id and bool(active)}
        # Include live references in the hash so a concurrent new dependency requires a new preview.
        keep_refs = sorted((parent, dependency) for parent, dependency in edges if parent in all_live and dependency in candidates)
        identity = {"impact": public, "artifacts": [{key: artifacts[item][key] for key in ("id", "digest", "storage_ref", "deleted_at")} for item in sorted(candidates)],
                    "references": keep_refs, "director_refs": sorted(director_refs & candidates)}
        public["preview_hash"] = fingerprint(identity)
        return public, artifacts, removed

    def preview(self, work_id: str, output_id: str | None = None) -> dict:
        with self.store.connection() as reader:
            return self._impact(reader, work_id, output_id)[0]

    def execute(self, command_id: str, work_id: str, expected_revision: int, preview_hash: str,
                output_id: str | None = None) -> dict:
        def action(writer):
            preview, artifacts, removed = self._impact(writer, work_id, output_id)
            if preview["preview_hash"] != preview_hash:
                raise StaleRevision("删除影响已变化，请重新查看预览")
            stamp = utc_now()
            for artifact_id in sorted(removed):
                item = artifacts[artifact_id]
                writer.execute("UPDATE artifacts SET deleted_at=?,displayable=0 WHERE id=?", (stamp, artifact_id))
                writer.execute("INSERT OR IGNORE INTO cleanup_jobs(id,work_id,artifact_id,storage_ref,digest,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                               (new_id("cleanup"), work_id, artifact_id, item["storage_ref"], item["digest"], stamp, stamp))
            if removed:
                marks = ",".join("?" for _ in removed)
                writer.execute(f"DELETE FROM acceptances WHERE work_id=? AND output_id IN ({marks})", (work_id, *sorted(removed)))
            changes = {"accepted_output_id": None} if preview["clears_acceptance"] else {}
            if output_id:
                work = self.store.get_work(work_id, connection=writer)
                remaining = writer.execute("SELECT 1 FROM artifacts WHERE work_id=? AND output_revision IS NOT NULL AND deleted_at IS NULL", (work_id,)).fetchone()
                if remaining is None and work["state"] == "reviewable":
                    changes["state"] = "discussing"
            if not output_id:
                writer.execute("UPDATE works SET deleted_at=? WHERE id=?", (stamp, work_id))
                writer.execute("UPDATE runs SET cancel_requested=1,state='cancelled',owner_epoch=owner_epoch+1,owner_id=NULL,lease_expires_at=NULL,revision=revision+1,updated_at=? WHERE work_id=? AND state IN ('pending','running','waiting_external','needs_decision','paused')", (stamp, work_id))
                writer.execute("UPDATE tasks SET state='cancelled',revision=revision+1,updated_at=? WHERE work_id=? AND state IN ('pending','running','waiting_external','retryable_failed','needs_decision')", (stamp, work_id))
                writer.execute("UPDATE operations SET state='cancelled',revision=revision+1,updated_at=? WHERE work_id=? AND state='reserved'", (stamp, work_id))
                writer.execute("UPDATE authorization_grants SET revoked_at=COALESCE(revoked_at,?) WHERE work_id=?", (stamp, work_id))
                changes.update(state="cancelled", accepted_output_id=None)
            work = self.store.get_work(work_id, connection=writer)
            self.store.bump_work(writer, work_id, work["revision"], **changes)
            receipt = {"work_id": work_id, "output_id": output_id, "deleted_artifact_ids": sorted(removed),
                       "accepted_selection_removed": preview["clears_acceptance"], "cleanup_pending": bool(removed),
                       "revision": work["revision"]+1, "deleted_at": stamp}
            self.store.append_event(writer, work_id, "deletion_requested", receipt)
            return receipt
        return self.store.execute_command(command_id, {"action": "delete", "output_id": output_id, "preview_hash": preview_hash},
                                          action, work_id=work_id, expected_revision=expected_revision)

    def _path(self, job):
        ref = job["storage_ref"]
        parts = PurePosixPath(ref).parts
        # Only owned generated work files are eligible. Library, inbox, profiles,
        # private receipts/checkpoints and any path aliases are never swept.
        if ("\\" in ref or ":" in ref or PurePosixPath(ref).is_absolute() or len(parts) < 3
                or parts[:2] != ("works", job["work_id"]) or any(p in {"", ".", ".."} for p in ref.split("/"))):
            return None
        if self.outputs.is_symlink():
            return None
        path = self.outputs
        for part in parts:
            path = path / part
            if path.is_symlink():
                return None
        if not path.resolve().is_relative_to(self.outputs.resolve()):
            return None
        return path

    def _retention_reason(self, connection, job):
        if connection.execute("SELECT 1 FROM operations WHERE work_id=? AND state IN ('sending','submitted','unknown')", (job["work_id"],)).fetchone():
            return "inflight_operation"
        if connection.execute("SELECT 1 FROM runs WHERE work_id=? AND state IN ('pending','running','waiting_external','needs_decision','paused')", (job["work_id"],)).fetchone():
            return "active_run"
        # A live artifact with the same physical file, even in another work, retains it.
        if connection.execute("SELECT 1 FROM artifacts WHERE storage_ref=? AND deleted_at IS NULL", (job["storage_ref"],)).fetchone():
            return "shared_asset"
        if connection.execute("SELECT 1 FROM work_inputs WHERE source_ref=?", (job["storage_ref"],)).fetchone():
            return "original_input"
        if connection.execute("SELECT 1 FROM director_revisions d JOIN artifacts a ON a.id=d.trial_artifact_id WHERE a.storage_ref=?", (job["storage_ref"],)).fetchone():
            return "director_evidence"
        if connection.execute("""WITH RECURSIVE retained(id) AS (
            SELECT id FROM artifacts WHERE deleted_at IS NULL
            UNION SELECT trial_artifact_id FROM director_revisions WHERE trial_artifact_id IS NOT NULL
            UNION SELECT accepted_output_id FROM works WHERE accepted_output_id IS NOT NULL
            UNION SELECT e.dependency_id FROM artifact_edges e JOIN retained r ON e.artifact_id=r.id)
            SELECT 1 FROM retained r JOIN artifacts a ON a.id=r.id WHERE a.storage_ref=?""", (job["storage_ref"],)).fetchone():
            return "artifact_dependency"
        if connection.execute("SELECT 1 FROM works w JOIN artifacts a ON a.id=w.accepted_output_id WHERE a.storage_ref=?", (job["storage_ref"],)).fetchone():
            return "accepted_output"
        return None

    def reconcile_cleanup(self, *, work_id: str | None = None, limit: int = 100) -> dict:
        if not 1 <= limit <= 1000:
            raise ValueError("cleanup batch must be between 1 and 1000")
        with self.store.connection() as reader:
            clause, params = (" AND work_id=?", [work_id]) if work_id else ("", [])
            jobs = [dict(row) for row in reader.execute("SELECT * FROM cleanup_jobs WHERE state IN ('pending','deferred','retained')"+clause+" ORDER BY created_at,id LIMIT ?", (*params, limit))]
        counts = {"deleted": 0, "deferred": 0, "retained": 0, "failed": 0}
        for job in jobs:
            path = self._path(job)
            checksum = None
            if path and path.is_file():
                try:
                    digest = hashlib.sha256()
                    with path.open("rb") as content:
                        for chunk in iter(lambda: content.read(1024*1024), b""):
                            digest.update(chunk)
                    checksum = digest.hexdigest()
                    identity = path.stat()
                except OSError:
                    checksum = "unreadable"
            with self.store.transaction() as writer:
                current = writer.execute("SELECT state FROM cleanup_jobs WHERE id=?", (job["id"],)).fetchone()
                if current is None or current[0] == "deleted":
                    continue
                reason = self._retention_reason(writer, job)
                state = "deferred" if reason in {"inflight_operation", "active_run"} else "retained"
                if not reason:
                    try:
                        self._release_material(writer, job)
                    except Exception:
                        # Separate SQLite catalogs are not an atomic transaction.
                        # Repeated release is safe; failure cannot be reported as cleanup.
                        state, reason = "deferred", "material_release_pending"
                    if reason:
                        pass
                    elif path is None or self._path(job) != path:
                        reason = "protected_path"
                    elif not path.exists():
                        state = "deleted"
                    elif checksum != job["digest"] or not path.is_file():
                        reason = "content_changed"
                    else:
                        try:
                            latest = path.stat()
                            if (latest.st_dev, latest.st_ino, latest.st_size, latest.st_mtime_ns) != (identity.st_dev, identity.st_ino, identity.st_size, identity.st_mtime_ns):
                                reason = "content_changed"
                            else:
                                # This short local unlink is inside the reference-check txn.
                                # Artifact writers must recheck file existence when registering.
                                path.unlink()
                                state = "deleted"
                        except OSError:
                            # Windows readers/antivirus may still hold the file.
                            # Keep a durable retry instead of abandoning the queue.
                            state, reason = "deferred", "local_cleanup_failed"
                writer.execute("UPDATE cleanup_jobs SET state=?,reason=?,updated_at=? WHERE id=?", (state, reason, utc_now(), job["id"]))
                counts[state] += 1
        return counts

    def _release_material(self, connection, job):
        artifact = connection.execute("SELECT metadata_json FROM artifacts WHERE id=?", (job["artifact_id"],)).fetchone()
        metadata = json.loads(artifact[0])
        asset_ref = metadata.get("asset_ref")
        if not asset_ref:
            return
        from easel.materials.library import LibraryVisibility, UseContext
        if self.materials is None:
            root = self.outputs / "_production" / "materials"
            if not (root / "catalog.db").is_file():
                raise RuntimeError("material catalog unavailable")
            from .materials import MaterialService
            self.materials = MaterialService(root)
        scope = metadata.get("material_scope")
        if not isinstance(scope, dict):
            # A mutable current work profile must not invent old library visibility.
            raise RuntimeError("original material scope unavailable")
        self.materials.release_reference(asset_ref, job["artifact_id"],
            visibility=LibraryVisibility.model_validate(scope), context=UseContext(work_id=job["work_id"], purpose="production"))
