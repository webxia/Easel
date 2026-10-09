"""Native CLI failure taxonomy through the actual subprocess adapter."""
import json
import subprocess

import pytest

from easel.integrations.hypit import service, authoring_publication as publication
from easel.integrations.hypit.cli import HypitCLI
from easel.integrations.hypit.errors import HypitCLIError, HypitIntegrationError
from tests.test_material_integration import material_integration_env
from tests.test_native_authoring_publication import native_owner, CheckBoundary

pytestmark = pytest.mark.parametrize("material_integration_env", [
    {"hypit_source": "easel-hypit-source@1"},
], indirect=True)


@pytest.mark.parametrize("failure", [
    "launch", "timeout", "encoding", "bad_json", "duplicate", "nonfinite",
    "unknown_diagnostic", "bad_code_type", "wrong_exit", "wrong_success",
])
def test_native_cli_local_failures_preserve_original_inputs_and_recover(
        material_integration_env, monkeypatch, failure):
    attempt, root = native_owner(material_integration_env)
    before = publication._files(root)
    client, run, calls = HypitCLI(), subprocess.run, []
    def external_process(command, **kwargs):
        if len(command) > 1 and command[0] == str(client.executable) and command[1] == "check":
            calls.append(command)
            if failure == "launch":
                raise OSError("fixture process launch failed")
            if failure == "timeout":
                raise subprocess.TimeoutExpired(command, 1)
            if failure == "encoding":
                raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "fixture invalid encoding")
            if failure == "bad_json":
                return subprocess.CompletedProcess(command, 0, "incomplete {", "")
            if failure == "duplicate":
                return subprocess.CompletedProcess(command, 0, '{"ok":true,"ok":false}', "")
            if failure == "nonfinite":
                return subprocess.CompletedProcess(command, 0, '{"duration":NaN}', "")
            if failure == "wrong_success":
                return subprocess.CompletedProcess(command, 0, '{"ok":true}', "")
            payload = {"format": "hypit.cli-error@1", "ok": False, "error": {
                "code": ([] if failure == "bad_code_type" else
                         "CLI_ERROR" if failure == "unknown_diagnostic" else "AUTHOR_INPUT_TYPE_MISMATCH"),
                "message": "fixture diagnostic without trustworthy source classification"}}
            return subprocess.CompletedProcess(command, 1 if failure in {"unknown_diagnostic", "bad_code_type"} else 2, json.dumps(payload), "")
        return run(command, **kwargs)
    monkeypatch.setattr(subprocess, "run", external_process)
    with pytest.raises(publication.AuthoringPublicationError):
        service.complete_film_authoring(attempt["attempt_id"], cli=client)
    pending = service.get_film_attempt(attempt["attempt_id"])
    assert pending["authoring_status"] == "AUTHORING_RUNNING"
    assert pending["native_authoring_validation"]["input_files"] == before
    assert not pending.get("pending_authoring_publication")
    assert publication._files(root) == before and len(calls) == 1
    monkeypatch.setattr(subprocess, "run", run)
    restored = service.complete_film_authoring(attempt["attempt_id"], cli=CheckBoundary(root))
    assert restored["authoring_status"] == "AUTHORING_READY"


def test_native_cli_known_source_diagnostic_keeps_content_repair_path(material_integration_env, monkeypatch):
    attempt, root = native_owner(material_integration_env)
    before = publication._files(root)
    client, run = HypitCLI(), subprocess.run
    def external_process(command, **kwargs):
        if len(command) > 1 and command[0] == str(client.executable) and command[1] == "check":
            payload = {"format": "hypit.cli-error@1", "ok": False,
                       "error": {"code": "AUTHOR_INPUT_TYPE_MISMATCH", "message": "fixture authored type mismatch"}}
            return subprocess.CompletedProcess(command, 1, json.dumps(payload), "")
        return run(command, **kwargs)
    monkeypatch.setattr(subprocess, "run", external_process)
    with pytest.raises(HypitIntegrationError):
        service.complete_film_authoring(attempt["attempt_id"], cli=client)
    rejected = service.get_film_attempt(attempt["attempt_id"])
    assert rejected["authoring_status"] == "AUTHORING_FAILED"
    assert not rejected.get("native_authoring_validation") and not rejected.get("pending_authoring_publication")
    assert publication._files(root) == before

@pytest.mark.parametrize("phase", ["complete", "validate"])
def test_native_cli_discovery_failure_preserves_owner_and_reuses_local_inputs(
        material_integration_env, monkeypatch, tmp_path, phase):
    attempt, root = native_owner(material_integration_env)
    ready = None
    if phase == "validate":
        ready = service.complete_film_authoring(attempt["attempt_id"], cli=CheckBoundary(root))
        runtime = tmp_path / "native-discovery-runtime.json"
        runtime.write_text(json.dumps({
            "format": "hypit.runtime-local@1", "dataRoot": ".fixture-native-discovery",
            "credentials": {}, "endpoints": {}, "bindings": {},
        }))
        service.resolve_film_attempt_runtime(attempt["attempt_id"], str(runtime))
    before, discoveries = publication._files(root), []
    def unavailable_cli(*args, **kwargs):
        discoveries.append(1)
        raise HypitCLIError("fixture CLI discovery unavailable", failure_kind="local_io")
    # Only the external CLI constructor is replaced. The real service factory,
    # installed source parser, publication and validate Owner still execute.
    with monkeypatch.context() as context:
        context.setattr(service, "HypitCLI", unavailable_cli)
        with pytest.raises(publication.AuthoringPublicationError):
            if phase == "complete":
                service.complete_film_authoring(attempt["attempt_id"])
            else:
                service.validate_film_attempt(attempt["attempt_id"], publication.RUN)
    pending = service.get_film_attempt(attempt["attempt_id"])
    assert discoveries == [1] and publication._files(root) == before
    if phase == "complete":
        assert pending["authoring_status"] == "AUTHORING_RUNNING"
        assert pending["native_authoring_validation"]["input_files"] == before
        assert not pending.get("pending_authoring_publication")
        restored = service.complete_film_authoring(attempt["attempt_id"], cli=CheckBoundary(root))
        assert restored["authoring_status"] == "AUTHORING_READY"
    else:
        assert pending["authoring_status"] == "VALIDATING"
        assert pending["authoring"]["native_publication"] == ready["authoring"]["native_publication"]
        checks, plans = [], []
        class RecoveredCLI:
            def check(self, workspace, source):
                checks.append(1)
                return ready["authoring"]["check"]
            def plan(self, *args, **kwargs):
                plans.append(1)
                return {"format": "hypit.cli-plan@1", "ok": True}
        restored = service.validate_film_attempt(
            attempt["attempt_id"], publication.RUN, cli=RecoveredCLI(), recover_interrupted=True)
        assert restored["authoring_status"] == "PLANNED" and checks == plans == [1]
        assert restored["authoring"]["native_publication"] == ready["authoring"]["native_publication"]
        assert publication._files(root) == before

