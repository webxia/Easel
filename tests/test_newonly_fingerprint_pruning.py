"""Fingerprint optimization must preserve the exact frozen execution identity."""
import hashlib
import json
from pathlib import Path

import pytest

from easel.integrations.hypit.service import (
    _authoring_file_hash, _FINGERPRINT_EXCLUDED_DIRS,
)
from easel.integrations.hypit.errors import HypitIntegrationError


def _previous_fingerprint(workspace: Path, run: Path):
    rows = []
    for path in sorted(workspace.rglob("*")):
        rel = path.relative_to(workspace)
        if any(part in _FINGERPRINT_EXCLUDED_DIRS for part in rel.parts):
            continue
        if path.is_symlink():
            raise HypitIntegrationError("not allowed")
        if path.is_file():
            rows.append({"path": rel.as_posix(),
                         "sha256": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()})
    # Use exactly the original entry representation. The production _file_sha256
    # uses the prefix on each file, not only on the outer identity.
    run_path = run.relative_to(workspace).as_posix()
    run_row = next(row for row in rows if row["path"] == run_path)
    data = json.dumps(rows, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")
    deps = [x for x in rows if x["path"] != run_path]
    dep_bytes = json.dumps(deps, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")).encode("utf-8")
    return ("sha256:" + hashlib.sha256(data).hexdigest(),
            run_row["sha256"],
            "sha256:" + hashlib.sha256(dep_bytes).hexdigest(), rows)


@pytest.mark.parametrize("content", [
    ({"a.txt": "first", "aa/file.txt": "nested", "aa/inner.bin": "byte", "z.txt": "last"}),
    ({"作者/配音.svml": "UTF-8 😀", ".hidden": "hidden", "pkg/Z.txt": "Z"}),
])
def test_excluded_tree_pruning_keeps_exact_execution_fingerprint(tmp_path, content):
    run = tmp_path / "productions/easel-authoring/runs/main.svrun"
    run.parent.mkdir(parents=True)
    run.write_text('<?svml using="@hypit/run-markup@1"?>\\n<svrun/>\\n')
    for name, raw in content.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(raw)
    # Excluded state can contain thousands of receipts, even symlinked state;
    # it is not in the Authoring input graph and must not be hashed or visited.
    for root in (".easel", ".hypit", ".git"):
        history = tmp_path / root / "deep" / "records"
        history.mkdir(parents=True)
        for n in range(45):
            (history / f"{n:03}.json").write_text("{" + str(n) + "}")
    assert _authoring_file_hash(tmp_path, run) == _previous_fingerprint(tmp_path, run)


def test_included_symlink_is_never_silently_ignored(tmp_path):
    run = tmp_path / "main.svrun"
    run.write_text("fixture run")
    (tmp_path / "link").symlink_to(run)
    with pytest.raises(HypitIntegrationError, match="symlink"):
        _authoring_file_hash(tmp_path, run)


def test_ancestor_proof_is_reused_only_within_one_read_tree(monkeypatch):
    from easel.integrations.hypit import service
    original = {
        "attempt_id": "fa_parent", "hash": "a", "result_protocols": {
            "schema": "agent-result-protocols@1", "profiles": {
                "truth_reply": "truth-source-ref@1",
                "material_observation": "material-observation-delta@1",
                "script_ledger": "easel-script-claim-ledger@3",
                "quality_review": "quality-review-delta@1",
                "hypit_source": "easel-hypit-source@1",
            }},
    }
    child = {"attempt_id": "fa_child", "hash": "child"}
    calls = []

    def read_fingerprint(attempt, run_path=None):
        calls.append(attempt["attempt_id"])
        if attempt["attempt_id"] == "fa_child":
            first = service._execution_fingerprint(original)
            second = service._execution_fingerprint(original)
            assert first == second and first is not second
        return {"sha256": "sha256:" + attempt["hash"], "attempt_id": attempt["attempt_id"]}

    monkeypatch.setattr(service, "_compute_execution_fingerprint", read_fingerprint)
    assert service._execution_fingerprint(child)["attempt_id"] == "fa_child"
    assert calls == ["fa_child", "fa_parent"]
    # A separate operation cannot inherit that cache, including if the frozen
    # source version has changed or the on-disk bytes would be different.
    original["hash"] = "changed"
    assert service._execution_fingerprint(original)["sha256"] == "sha256:changed"
    assert calls == ["fa_child", "fa_parent", "fa_parent"]


def test_voice_lineage_reuses_ancestor_proof_only_during_one_read(monkeypatch):
    from easel.integrations import voice_identity
    from easel.integrations.hypit import service
    ancestor = {"attempt_id": "fa_parent", "revision": 1}
    verified = []

    def compute(attempt, run_path=None):
        verified.append(attempt["revision"])
        return {"sha256": "sha256:" + str(attempt["revision"])}

    def read_lineage(*args, **kwargs):
        left = service._execution_fingerprint(ancestor)
        right = service._execution_fingerprint(ancestor)
        assert left == right and left is not right
        return {"report": "verified"}

    monkeypatch.setattr(service, "_compute_execution_fingerprint", compute)
    monkeypatch.setattr(voice_identity, "_validate_checkpoint_evidence", read_lineage)
    assert voice_identity.validate_checkpoint(None, None, None, None, None, None) == {"report": "verified"}
    assert verified == [1]
    ancestor["revision"] = 2
    assert voice_identity.validate_checkpoint(None, None, None, None, None, None) == {"report": "verified"}
    assert verified == [1, 2]  # No stale proof may survive the public read.


def test_cycle_in_one_fingerprint_ancestry_fails_closed(monkeypatch):
    from easel.integrations.hypit import service
    attempt = {"attempt_id": "fa_cycle"}
    def recurse(current, run_path=None):
        return service._execution_fingerprint(current)
    monkeypatch.setattr(service, "_compute_execution_fingerprint", recurse)
    with pytest.raises(HypitIntegrationError, match="cyclic"):
        service._execution_fingerprint(attempt)


def test_pure_planning_schema_cache_is_exact_and_one_read_only():
    """Reuse compiled schemas, never acceptance evidence or cross-run state."""
    from copy import deepcopy
    from easel.integrations import planning_wire as wire, planning_staged_proposal as staged
    from easel.integrations.planning_result_contract import semantic_tool_schema

    schema = semantic_tool_schema({'global': {'global': 'whole'}}, compiled=True)
    original = deepcopy(schema)
    independent = wire.project(schema, 'A', atomic_framing=True)
    with wire._schema_read_scope():
        staged_first = staged._read_only_staged(schema)
        first = wire.project(schema, 'A', atomic_framing=True)
        assert first.identity == independent.identity and first.schema == independent.schema
        assert first.errors({}) == independent.errors({})  # Still reject malformed original replies.
        assert first is wire.project(deepcopy(schema), 'A', atomic_framing=True)
        assert first is not wire.project(schema, 'B', atomic_framing=True)
        assert first is not wire.project(schema, 'A', atomic_framing=False)
        assert staged_first is staged._read_only_staged(deepcopy(schema))
        assert staged_first is not staged._read_only_staged({**schema, 'title': 'other'})
        with wire._schema_read_scope():
            assert staged_first is staged._read_only_staged(schema)
    with wire._schema_read_scope():
        assert staged._read_only_staged(schema) is not staged_first
        assert wire.project(schema, 'A', atomic_framing=True) is not first
    assert schema == original  # No schema or source mutation by the cache itself.

