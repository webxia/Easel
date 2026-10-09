"""Native owner recovery through actual managed Delivery and checkpoint forks."""
import asyncio
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from easel import creation
from easel.creation_delivery import active_delivery
from easel.integrations import openclaw_authoring as scoped
from easel.integrations.output_receipts import OutputReceiptError
from easel.integrations.hypit import service, authoring_publication as publication
from easel.integrations.hypit.cli import HypitCLI
from tests.test_material_integration import material_integration_env
from tests.test_native_authoring_publication import native_owner, CheckBoundary

pytestmark = pytest.mark.parametrize("material_integration_env", [
    {"hypit_source": "easel-hypit-source@1"},
], indirect=True)


def test_managed_native_authoring_promotion_io_reclaims_original_stage_without_agent(
        material_integration_env, monkeypatch, tmp_path):
    from web import app as web
    attempt, root = native_owner(material_integration_env)
    raw_outputs = {name: (root / name).read_bytes() for name in (
        publication.SELECTION, publication.AUTHOR, publication.RUN,
        "productions/easel-authoring/authors/recipes.svs")}
    for name in (publication.AUTHOR, publication.RUN, "productions/easel-authoring/authors/recipes.svs"):
        (root / name).unlink()
    with creation.edit_creation(attempt["creation_id"]) as current:
        current["origin"] = {"type": "chat", "session_hash": "d" * 64}
    creation.mark_chat_proposal_ready(attempt["creation_id"])
    proposal = json.dumps([{"role": "user", "content": "已确认本测试作品及假设脚本内容。"}], ensure_ascii=False)
    creation.confirm_chat_proposal(attempt["creation_id"], "fixture-confirm",
        delivery_proposal=proposal, proposal_sha256=hashlib.sha256(proposal.encode()).hexdigest())

    policies, methods, messages, deletes = {}, [], [], []
    agent_invokes, run_id, stage_workspace = 0, None, None
    def gateway(command, **kwargs):
        nonlocal agent_invokes, run_id, stage_workspace
        payload = {}
        if "config" in command and "patch" in command:
            policies.update(json.loads(kwargs["input"])["agents"]["entries"])
        elif "agents" in command and "list" in command:
            payload = [{"id": key, "workspace": value["workspace"]} for key, value in policies.items()]
        elif "agents" in command and "delete" in command:
            deletes.append(command)
        elif "gateway" in command and "call" in command:
            method = command[command.index("call") + 1]
            params = json.loads(command[command.index("--params") + 1])
            methods.append(method)
            if method == "agent":
                agent_invokes += 1
                assert agent_invokes == 1, "recovery may not submit another Agent"
                run_id = params["idempotencyKey"]
                stage_workspace = Path(policies[params["agentId"]]["workspace"])
                for name, raw in raw_outputs.items():
                    target = stage_workspace / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(raw)
                payload = {"runId": run_id, "status": "ok", "endedAt": 1000}
            elif method == "sessions.abort":
                payload = {"ok": True, "status": "no-active-run", "abortedRunId": None}
            else:
                raise AssertionError("unexpected gateway method: " + method)
        return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")

    real_scoped = scoped.run_attempt_scoped_authoring
    def invoke_scoped(**kwargs):
        messages.append(kwargs["message"])
        kwargs.update(staging_parent=tmp_path / "stage", cwd=tmp_path, env={}, timeout=5)
        return real_scoped(**kwargs, runner=gateway)
    monkeypatch.setattr(web, "run_attempt_scoped_authoring", invoke_scoped)
    monkeypatch.setattr(web, "openclaw_base_cmd", lambda: ["openclaw"])
    monkeypatch.setattr(web, "_proxy_env", lambda: {})
    monkeypatch.setattr(HypitCLI, "vocabulary", lambda self, workspace, packages: {
        "surfaces": [{"package": name, "fixture": "CLI boundary"} for name in packages]})
    checks = []
    class LocalCheck:
        def check(self, workspace, source):
            boundary = CheckBoundary(root)
            checks.append(boundary)
            return boundary.check(workspace, source)
    monkeypatch.setattr(service, "_cli", lambda supplied=None: LocalCheck())

    replace = scoped.os.replace
    cut = True
    def replace_then_interrupt(source, destination):
        nonlocal cut
        result = replace(source, destination)
        if cut and Path(destination) == root / publication.AUTHOR and Path(source).name.startswith(".authoring-"):
            cut = False
            raise OSError("fixture raw promotion failed after durable replacement")
        return result
    monkeypatch.setattr(scoped.os, "replace", replace_then_interrupt)
    token = active_delivery.set(attempt["creation_id"])
    try:
        with pytest.raises(OutputReceiptError, match="promotion failed locally"):
            asyncio.run(web._run_film_authoring(attempt["attempt_id"]))
        failed = service.get_film_attempt(attempt["attempt_id"])
        assert failed["authoring_status"] == "AUTHORING_RUNNING"
        assert not failed.get("pending_authoring_publication") and not failed.get("native_authoring_validation")
        work = creation.get_creation(attempt["creation_id"])
        assert len(work["delivery"]["authoring_stages"]) == len(work["delivery"]["agent_calls"]) == 1
        stage_key, stage = next(iter(work["delivery"]["authoring_stages"].items()))
        receipt_key, receipt = next(iter(work["delivery"]["agent_calls"].items()))
        assert receipt["status"] == "ok" and receipt["run_id"] == run_id
        assert receipt["runtime_release"] == "released" and stage["inputs_ready"] is True
        stage_root = Path(stage["stage_root"])
        assert stage_workspace == stage_root / "workspace" and stage_root.is_dir()
        assert all((stage_workspace / name).read_bytes() == raw for name, raw in raw_outputs.items())
        instruction = scoped.retained_authoring_message(attempt["attempt_id"], profile=web.OPENCLAW_PROFILE)
        assert instruction == messages[0] and agent_invokes == 1 and not checks and not deletes
        monkeypatch.setattr(scoped.os, "replace", replace)
        ready = asyncio.run(web._run_film_authoring(attempt["attempt_id"]))
        assert ready["authoring_status"] == "AUTHORING_READY"
        assert agent_invokes == 1 and len(checks) == 1 and messages == [instruction, instruction]
        restored = creation.get_creation(attempt["creation_id"])
        assert set(restored["delivery"]["agent_calls"]) == {receipt_key}
        assert restored["delivery"]["agent_calls"][receipt_key]["run_id"] == run_id
        assert set(restored["delivery"]["authoring_stages"]) == {stage_key} and stage_root.is_dir()
        scoped.release_delivery_authoring(attempt["attempt_id"], command_prefix=["openclaw"],
            profile=web.OPENCLAW_PROFILE, cwd=tmp_path, env={}, runner=gateway)
        final = creation.get_creation(attempt["creation_id"])
        assert not stage_root.exists() and not final["delivery"]["authoring_stages"]
        assert final["delivery"]["agent_calls"][receipt_key]["run_id"] == run_id
    finally:
        active_delivery.reset(token)


@pytest.mark.parametrize("cut", ["before_intent", "after_target"])
def test_native_checkpoint_fork_recovers_without_recopying_frozen_inputs(
        material_integration_env, monkeypatch, tmp_path, cut):
    attempt, root = native_owner(material_integration_env)
    service.complete_film_authoring(attempt["attempt_id"], cli=CheckBoundary(root))
    checks, builds, failed = [], [], False
    class CLI:
        def check(self, workspace, source):
            nonlocal failed
            if "native-authoring" not in workspace.parts:
                return {"format": "hypit.cli-check@1", "ok": True, "sourceKind": "run",
                        "run": publication.RUN, "author": publication.AUTHOR, "frontend": "@hypit/run-markup@1",
                        "targetCount": 1, "targets": ["final.video"], "candidates": 0, "satisfactions": 0}
            checks.append(workspace)
            if cut == "before_intent" and not failed:
                failed = True
                raise OSError("fixture child local check interrupted")
            return CheckBoundary(workspace.parents[3]).check(workspace, source)
        def plan(self, *args, **kwargs):
            return {"format": "hypit.cli-plan@1", "ok": True}
        def pricing(self, *args, **kwargs):
            return {"format": "hypit.cli-pricing@1", "requestCount": 1, "groups": []}
        def build(self, *args, **kwargs):
            builds.append(1)
            return {"format": "hypit.cli-build@1", "build": {"id": "bld_native_retry_001", "work": {"outcome": "failed"}}}
        def status(self, workspace, build_id, **kwargs):
            return {"format": "hypit.cli-status@1", "build": {"id": build_id, "work": {"outcome": "failed"}}}
    cli = CLI()
    runtime = tmp_path / "native-retry-runtime.json"
    runtime.write_text(json.dumps({"format": "hypit.runtime-local@1", "dataRoot": ".fixture-native-retry-runtime",
                                   "credentials": {}, "endpoints": {}, "bindings": {}}))
    service.resolve_film_attempt_runtime(attempt["attempt_id"], str(runtime))
    service.validate_film_attempt(attempt["attempt_id"], publication.RUN, cli=cli)
    service.estimate_film_attempt(attempt["attempt_id"], cli=cli)
    service.approve_film_cost(attempt["attempt_id"], 1)
    parent = service.submit_film_build(attempt["attempt_id"], title="offline native retry fixture", cli=cli)
    assert parent["execution_status"] == "BUILD_FAILED"
    publish = publication._publish_file
    def interrupt(workspace, row, raw):
        nonlocal failed
        publish(workspace, row, raw)
        if cut == "after_target" and not failed:
            failed = True
            raise OSError("fixture child prefix interrupted")
    monkeypatch.setattr(publication, "_publish_file", interrupt)
    with pytest.raises(publication.AuthoringPublicationError):
        service.retry_failed_film_build(attempt["attempt_id"], cli=cli)
    work = creation.get_creation(attempt["creation_id"])
    child = next(row for row in work["hypit_attempts"] if row.get("retry_source", {}).get("attempt_id") == attempt["attempt_id"])
    child_id = child["attempt_id"]
    assert child.get("native_authoring_validation")
    if cut == "after_target":
        assert child.get("pending_authoring_publication")
    monkeypatch.setattr(publication, "_publish_file", publish)
    def no_checkpoint_copy(*args, **kwargs):
        raise AssertionError("resume must not rewrite the child's frozen Planning/Gate/checkpoint")
    monkeypatch.setattr(service, "_copy_retry_checkpoint_file", no_checkpoint_copy)
    restored = service.retry_failed_film_build(attempt["attempt_id"], cli=cli)
    assert restored["attempt_id"] == child_id
    assert restored["authoring_status"] == "AUTHORING_READY" and restored["retry_source"]["status"] == "READY"
    assert len(builds) == 1 and len(checks) == (2 if cut == "before_intent" else 1)
    assert not restored.get("native_authoring_validation") and not restored.get("pending_authoring_publication")
