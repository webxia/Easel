"""U3: bounded Authoring multi-file file publication, no Hypit/Provider calls."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from easel.integrations.hypit import publication as files


def _case(root):
    first = root / "productions/easel-authoring/authors/main.svml"
    second = root / "productions/easel-authoring/runs/main.svrun"
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    first.write_bytes(b"original authored source")
    second.write_bytes(b"original run")
    candidates = {
        "productions/easel-authoring/authors/main.svml": b'<?svml using="@hypit/markup@1"?>\n<svml/>\n',
        "productions/easel-authoring/runs/main.svrun": b'<?svml using="@hypit/run-markup@1"?>\n<svrun version="1"/>\n',
    }
    return first, second, candidates


def test_authoring_file_publication_is_bound_replayable_and_cold_verified(tmp_path):
    first, second, candidates = _case(tmp_path)
    journal = files.prepare(tmp_path, attempt_id="fa-01", operation_id="authoring-check",
                            frozen_identity="material-ready-01", candidates=candidates)
    assert first.read_bytes() == b"original authored source"
    assert second.read_bytes() == b"original run"
    proof = files.publish(tmp_path, journal)
    assert first.read_bytes() == candidates["productions/easel-authoring/authors/main.svml"]
    assert files.verify(tmp_path, journal) == proof
    assert files.prepare(tmp_path, attempt_id="fa-01", operation_id="authoring-check",
                         frozen_identity="material-ready-01", candidates=candidates) == journal
    assert files.publish(tmp_path, journal) == proof
    script = (
        "import json,socket,sys; from easel.integrations.hypit.publication import verify; "
        "socket.socket.connect=lambda *a,**k: (_ for _ in ()).throw(AssertionError('network')); "
        "ref=json.load(sys.stdin); assert verify(ref['root'],ref['id'])==ref['proof']; "
        "print('PUBLICATION_COLD_PASS')")
    child = subprocess.run([sys.executable, "-c", script],
                           input=json.dumps({"root": str(tmp_path), "id": journal, "proof": proof}),
                           capture_output=True, text=True, timeout=20)
    assert child.returncode == 0, child.stderr
    assert "PUBLICATION_COLD_PASS" in child.stdout


def test_authoring_publication_can_resume_only_its_own_partial_writes(tmp_path, monkeypatch):
    first, second, candidates = _case(tmp_path)
    journal = files.prepare(tmp_path, attempt_id="fa-01", operation_id="authoring-check",
                            frozen_identity="material-ready-01", candidates=candidates)
    original = files._replace
    count = []
    def interrupt(path, data):
        count.append(path.name)
        if len(count) == 2:
            raise files.AuthoringPublicationError("fixture crash after first file")
        original(path, data)
    monkeypatch.setattr(files, "_replace", interrupt)
    with pytest.raises(files.AuthoringPublicationError):
        files.publish(tmp_path, journal)
    assert first.read_bytes() == candidates["productions/easel-authoring/authors/main.svml"]
    assert second.read_bytes() == b"original run"
    monkeypatch.setattr(files, "_replace", original)
    files.publish(tmp_path, journal)
    assert files.verify(tmp_path, journal)


def test_authoring_publication_rejects_foreign_changes_without_writing_others(tmp_path):
    first, second, candidates = _case(tmp_path)
    journal = files.prepare(tmp_path, attempt_id="fa-01", operation_id="authoring-check",
                            frozen_identity="material-ready-01", candidates=candidates)
    first.write_bytes(b"third-party change")
    with pytest.raises(files.AuthoringPublicationError, match="unrelated writer"):
        files.publish(tmp_path, journal)
    assert second.read_bytes() == b"original run"
    with pytest.raises(files.AuthoringPublicationError):
        files.verify(tmp_path, journal)


def test_authoring_publication_conflicting_replay_and_symlink_fail_closed(tmp_path):
    first, second, candidates = _case(tmp_path)
    journal = files.prepare(tmp_path, attempt_id="fa-01", operation_id="authoring-check",
                            frozen_identity="material-ready-01", candidates=candidates)
    changed = dict(candidates)
    changed["productions/easel-authoring/authors/main.svml"] = b"other source"
    with pytest.raises(files.AuthoringPublicationError, match="changed its frozen"):
        files.prepare(tmp_path, attempt_id="fa-01", operation_id="authoring-check",
                      frozen_identity="material-ready-01", candidates=changed)
    target = tmp_path / "productions/easel-authoring/authors/alias.svml"
    target.symlink_to(first)
    with pytest.raises(files.AuthoringPublicationError, match="symlink"):
        files.prepare(tmp_path, attempt_id="fa-02", operation_id="authoring-check",
                      frozen_identity="material-ready-02", candidates={
                          "productions/easel-authoring/authors/alias.svml": b"x"})

def test_authoring_publication_stops_on_midflight_foreign_change(tmp_path, monkeypatch):
    """Even after one owned replace, never overwrite the other writer's second file."""
    first, second, candidates = _case(tmp_path)
    journal = files.prepare(tmp_path, attempt_id="fa-01", operation_id="authoring-check",
                            frozen_identity="material-ready-01", candidates=candidates)
    original = files._replace
    def foreign_writer(path, value):
        original(path, value)
        if path == first:
            second.write_bytes(b"unrelated midflight change")
    monkeypatch.setattr(files, "_replace", foreign_writer)
    with pytest.raises(files.AuthoringPublicationError, match="changed the source during publication"):
        files.publish(tmp_path, journal)
    assert first.read_bytes() == candidates["productions/easel-authoring/authors/main.svml"]
    assert second.read_bytes() == b"unrelated midflight change"


@pytest.mark.parametrize("bad_name", [
    "productions/easel-authoring/./authors/main.svml",
    "productions/easel-authoring//authors/main.svml",
    "productions/easel-authoring/../authors/main.svml",
])
def test_authoring_publication_rejects_noncanonical_candidate_paths(tmp_path, bad_name):
    _case(tmp_path)
    with pytest.raises(files.AuthoringPublicationError, match="allowed relative"):
        files.prepare(tmp_path, attempt_id="fa-03", operation_id="authoring-check",
                      frozen_identity="material-ready-03", candidates={bad_name: b"sample"})

@pytest.mark.parametrize("filename,content", [
    ("authors/main.svml", b"\xff"),
    ("authors/main.svml", b"\x00"),
    ("authors/main.svml", b"Bearer " + b"F" * 16),
    ("material-selection.json", b'{"a":1,"a":2}'),
    ("material-selection.json", b'{"example": NaN}'),
    ("material-selection.json", b'{"token": "fixture"}'),
])
def test_authoring_publication_never_journals_invalid_or_sensitive_content(tmp_path, filename, content):
    _case(tmp_path)
    with pytest.raises(files.AuthoringPublicationError):
        files.prepare(tmp_path, attempt_id="fa-sensitive", operation_id="authoring-check",
                      frozen_identity="material-ready-sensitive", candidates={
                          "productions/easel-authoring/" + filename: content})
    directory = tmp_path / ".easel/authoring-publications"
    assert not list(directory.glob("[0-9a-f]" * 64 + ".json"))  # No intent was published.

def _run_contract_fixture(root, *, new_profile=True):
    """Use real Easel Run identity verification, not a fake parser or Build."""
    from types import SimpleNamespace
    root = Path(root)
    run = root / "productions/easel-authoring/runs/main.svrun"
    author = root / "productions/easel-authoring/authors/main.svml"
    run.parent.mkdir(parents=True, exist_ok=True)
    author.parent.mkdir(parents=True, exist_ok=True)
    author.write_text("<svml></svml>", encoding="utf-8")
    attempt = {"creation_id": "cr_journal", "attempt_id": "fa_journal",
        "handoff": {"hash": "a" * 64},
        "result_protocols": {"schema": "agent-result-protocols@1",
            "profiles": ({"hypit_run_promotion": "hypit-run-promotion@1"}
                         if new_profile else {})}}
    plan = SimpleNamespace(plan_id="plan_journal")
    bundle = SimpleNamespace(bundle_id="bundle_journal", revision="bundle_01")
    readiness = SimpleNamespace(plan_revision="plan_01", bundle_revision="bundle_01")
    original = {"schema": "easel-authoring-svrun@1",
        "creation_id": "cr_journal", "attempt_id": "fa_journal",
        "plan_id": plan.plan_id, "plan_revision": readiness.plan_revision,
        "bundle_id": bundle.bundle_id, "bundle_revision": bundle.revision,
        "readiness_revision": readiness.bundle_revision,
        "authoring_source": "../authors/main.svml",
        "material_selection": "../material-selection.json",
        "status": "AUTHORING_READY", "publication_allowed": False,
        "build": {"enabled": False, "reason": "offline-authored-no-build"}}
    run.write_text(json.dumps(original, ensure_ascii=False), encoding="utf-8")
    return run, attempt, plan, bundle, readiness


@pytest.mark.parametrize("new_profile", [False, True])
def test_easel_real_native_run_conversion_keeps_original_manifest_and_frozen_identity(tmp_path, new_profile):
    from easel.integrations.material_layer import _hypit_run_markup
    run, attempt, plan, bundle, readiness = _run_contract_fixture(tmp_path, new_profile=new_profile)
    original = run.read_bytes()
    markup = _hypit_run_markup(run, tmp_path, attempt, plan, bundle, readiness)
    sidecar = run.with_suffix(".easel.json")
    assert sidecar.read_bytes() == original
    assert run.read_text() == markup
    assert markup.startswith('<?svml using="@hypit/run-markup@1"?>')
    assert _hypit_run_markup(run, tmp_path, attempt, plan, bundle, readiness) == markup
    journals = list((tmp_path / ".easel" / "authoring-publications").glob("[0-9a-f]" * 64 + ".json"))
    if new_profile:
        assert len(journals) == 1
        assert files.verify(tmp_path, journals[0].stem)["after"]
    else:
        assert journals == []


def test_native_run_two_file_promotion_recovers_original_partial_write_without_new_identity(tmp_path, monkeypatch):
    from easel.integrations.material_layer import _hypit_run_markup, MaterialIntegrationError
    run, attempt, plan, bundle, readiness = _run_contract_fixture(tmp_path)
    original = run.read_bytes()
    original_write = files._replace
    counter = []
    def interrupt(path, content):
        counter.append(path.name)
        if len(counter) == 2:
            raise files.AuthoringPublicationError("fixture failure after bound identity sidecar")
        original_write(path, content)
    monkeypatch.setattr(files, "_replace", interrupt)
    with pytest.raises(MaterialIntegrationError, match="cannot be completed"):
        _hypit_run_markup(run, tmp_path, attempt, plan, bundle, readiness)
    assert run.read_bytes() == original
    assert run.with_suffix(".easel.json").read_bytes() == original
    monkeypatch.setattr(files, "_replace", original_write)
    markup = _hypit_run_markup(run, tmp_path, attempt, plan, bundle, readiness)
    assert run.read_text() == markup
    journals = list((tmp_path / ".easel" / "authoring-publications").glob("[0-9a-f]" * 64 + ".json"))
    assert len(journals) == 1
    files.verify(tmp_path, journals[0].stem)


def test_native_run_frozen_context_mismatch_is_rejected_before_promotion(tmp_path):
    from easel.integrations.material_layer import _hypit_run_markup, MaterialIntegrationError
    run, attempt, plan, bundle, readiness = _run_contract_fixture(tmp_path)
    attempt["creation_id"] = "different_creation"
    with pytest.raises(MaterialIntegrationError, match="identity"):
        _hypit_run_markup(run, tmp_path, attempt, plan, bundle, readiness)
    assert run.with_suffix(".easel.json").exists() is False
    assert run.read_text().startswith("{")

def test_native_run_rejects_missing_original_promotion_journal(tmp_path):
    from easel.integrations.material_layer import _hypit_run_markup, MaterialIntegrationError
    run, attempt, plan, bundle, readiness = _run_contract_fixture(tmp_path)
    original = run.read_bytes()
    _hypit_run_markup(run, tmp_path, attempt, plan, bundle, readiness)
    existing_native = run.read_bytes()
    journals = list((tmp_path / ".easel/authoring-publications").glob("[0-9a-f]" * 64 + ".json"))
    assert len(journals) == 1
    journals[0].unlink()
    with pytest.raises(MaterialIntegrationError, match="cannot be completed"):
        _hypit_run_markup(run, tmp_path, attempt, plan, bundle, readiness)
    assert run.read_bytes() == existing_native
    assert run.with_suffix(".easel.json").read_bytes() == original
    assert not list((tmp_path / ".easel/authoring-publications").glob("[0-9a-f]" * 64 + ".json"))


def test_native_run_cannot_be_laundered_from_unjournaled_native_and_sidecar(tmp_path):
    from easel.integrations.material_layer import _hypit_run_markup, MaterialIntegrationError
    run, attempt, plan, bundle, readiness = _run_contract_fixture(tmp_path)
    original = run.read_bytes()
    run.with_suffix(".easel.json").write_bytes(original)
    run.write_text('<?svml using="@hypit/run-markup@1"?>\n<svrun version="1">\n'
                   '  <author source="../authors/main.svml"/>\n'
                   '  <target output="final.video"/>\n</svrun>\n', encoding="utf-8")
    with pytest.raises(MaterialIntegrationError, match="cannot be completed"):
        _hypit_run_markup(run, tmp_path, attempt, plan, bundle, readiness)
    assert run.read_text().startswith("<?svml")
    assert not list((tmp_path / ".easel/authoring-publications").glob("[0-9a-f]" * 64 + ".json"))

def test_competing_native_authoring_profiles_are_rejected_before_file_changes(tmp_path):
    from easel.integrations import result_protocols
    from easel.integrations.output_receipts import OutputReceiptError
    from easel.integrations.material_layer import _hypit_run_markup
    run, attempt, plan, bundle, readiness = _run_contract_fixture(tmp_path)
    original = run.read_bytes()
    attempt['result_protocols']['profiles']['hypit_source'] = 'easel-hypit-source@1'
    with pytest.raises(OutputReceiptError, match='competing Hypit'):
        _hypit_run_markup(run, tmp_path, attempt, plan, bundle, readiness)
    assert run.read_bytes() == original
    assert not run.with_suffix('.easel.json').exists()
    assert result_protocols.inherited({'result_protocols': {'schema': result_protocols.SCHEMA, 'profiles': {}}})['profiles'] == {}
    assert result_protocols.current()['profiles']['hypit_source'] == 'easel-hypit-source@1'
    assert 'hypit_run_promotion' not in result_protocols.current()['profiles']






