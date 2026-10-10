"""CUT5: native-only Hypit approval/submission/reconciliation security boundary.

All Planning, Material, published Authoring bytes and native Check are real
local Easel components. Only Hypit CLI plan/pricing/build/status is substituted.
No provider, real Build, runtime auth, payment or external model is invoked.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

import pytest

from easel.integrations.hypit import service
from easel.integrations.hypit.errors import HypitIntegrationError
from easel.integrations.hypit import authoring_publication as native
from easel.integrations.hypit.native_source import parse_file, parse_run
from tests.test_material_integration import material_integration_env
from tests.test_native_authoring_publication import native_owner, CheckBoundary

pytestmark = pytest.mark.parametrize("material_integration_env", [
    {"hypit_source": "easel-hypit-source@1"},
], indirect=True)


class NativeBuildBoundary(CheckBoundary):
    """Real parser/selection; simulated CLI responses only after admission."""

    def __init__(self, root):
        super().__init__(root)
        self.build_count = 0

    def check(self, workspace, source):
        if workspace != self.root:
            return super().check(workspace, source)
        assert source == workspace / native.RUN
        parse_file(workspace / native.AUTHOR, workspace=workspace)
        _, run, _ = parse_run(source, workspace=workspace)
        assert run["targets"] == [{"output": "final.video"}]
        self.calls.append(workspace)
        return {"format": "hypit.cli-check@1", "ok": True,
                "sourceKind": "run", "run": native.RUN, "author": native.AUTHOR,
                "frontend": "@hypit/run-markup@1", "targetCount": 1,
                "targets": ["final.video"], "candidates": 0, "satisfactions": 0,
                "historicalOutputCount": 0}

    def plan(self, *_args, **_kwargs):
        return {"format": "hypit.cli-plan@1", "ok": True}

    def pricing(self, *_args, **_kwargs):
        return {"format": "hypit.cli-pricing@1", "requestCount": 1, "groups": []}

    def build(self, _workspace, _source, *, title, runtime_profile=None):
        self.build_count += 1
        return {"format": "hypit.cli-build@1",
                "build": {"id": "bld_native_integrity_001"}}

    def builds(self, _workspace, *, limit=100):
        return {"format": "hypit.cli-builds@1", "builds": []}

    def history(self, _workspace, _output_name, *, source=None, limit=100):
        return {"format": "hypit.cli-history@1", "entries": []}


def _approved_native(attempt, tmp_path, cli):
    ready = service.complete_film_authoring(attempt["attempt_id"], cli=cli)
    assert ready["authoring_status"] == "AUTHORING_READY"
    runtime = tmp_path / "native-fixture.runtime.json"
    runtime.write_text(json.dumps({
        "format": "hypit.runtime-local@1", "dataRoot": ".fixture-native-build",
        "credentials": {}, "endpoints": {}, "bindings": {},
    }) + "\n")
    service.resolve_film_attempt_runtime(attempt["attempt_id"], str(runtime))
    checked = service.validate_film_attempt(attempt["attempt_id"], native.RUN, cli=cli)
    assert checked["plan"]["status"] == "ready"
    priced = service.estimate_film_attempt(attempt["attempt_id"], cli=cli)
    assert priced['cost']['total']['status'] == 'unknown'
    assert priced['cost']['limit_enforced_by_hypit'] is False
    with pytest.raises(HypitIntegrationError, match='仅 Hypit 核实无 Provider 费用'):
        service.approve_film_cost(attempt['attempt_id'], 0)
    approved = service.approve_film_cost(attempt["attempt_id"], 1)
    assert approved["cost"]["approved"] is True
    assert cli.build_count == 0
    return runtime


def test_native_approval_invalidates_on_runtime_bytes_change_before_build(
        material_integration_env, tmp_path):
    attempt, root = native_owner(material_integration_env)
    cli = NativeBuildBoundary(root)
    runtime = _approved_native(attempt, tmp_path, cli)
    payload = json.loads(runtime.read_text())
    payload["dataRoot"] = ".changed-native-build-runtime"
    runtime.write_text(json.dumps(payload) + "\n")
    with pytest.raises(HypitIntegrationError, match="fingerprint|批准|重新"):
        service.submit_film_build(attempt["attempt_id"], title="offline integrity test", cli=cli)
    saved = service.get_film_attempt(attempt["attempt_id"])
    assert saved["cost"]["approved"] is False
    assert saved["execution_status"] == "NOT_SUBMITTED"
    assert cli.build_count == 0


def test_native_concurrent_build_clicks_keep_single_submission(
        material_integration_env, tmp_path):
    attempt, root = native_owner(material_integration_env)
    class BlockingBuild(NativeBuildBoundary):
        def __init__(self, root):
            super().__init__(root)
            self.entered = threading.Event()
            self.release = threading.Event()

        def build(self, workspace, source, *, title, runtime_profile=None):
            self.build_count += 1
            self.entered.set()
            assert self.release.wait(15), "fixture Build release is bounded"
            return {"format": "hypit.cli-build@1",
                    "build": {"id": "bld_native_concurrent_001"}}

    cli = BlockingBuild(root)
    _approved_native(attempt, tmp_path, cli)
    outcomes, errors = [], []
    def first():
        try:
            outcomes.append(service.submit_film_build(
                attempt["attempt_id"], title="offline concurrent", cli=cli))
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=first, daemon=True)
    thread.start()
    try:
        assert cli.entered.wait(15)
        replay = service.submit_film_build(attempt["attempt_id"], title="same click", cli=cli)
        assert replay["idempotent_replay"] is True
        assert replay["execution_status"] == "SUBMITTING"
        assert cli.build_count == 1
    finally:
        cli.release.set()
        thread.join(15)
    assert not thread.is_alive() and not errors
    assert outcomes[0]["build"]["build_id"] == "bld_native_concurrent_001"
    assert cli.build_count == 1


def test_native_plan_contract_drift_revokes_approval_without_build(
        material_integration_env, tmp_path):
    """An edited saved Plan cannot retain the previous operator authorization."""
    from easel import creation
    attempt, root = native_owner(material_integration_env)
    cli = NativeBuildBoundary(root)
    _approved_native(attempt, tmp_path, cli)
    with creation.edit_creation(attempt['creation_id']) as work:
        saved = next(row for row in work['hypit_attempts']
                     if row['attempt_id'] == attempt['attempt_id'])
        saved['plan']['result']['fixture_extra'] = 'unapproved changed plan'
    with pytest.raises(HypitIntegrationError, match='fingerprint|批准|重新'):
        service.submit_film_build(attempt['attempt_id'], title='offline changed plan', cli=cli)
    saved = service.get_film_attempt(attempt['attempt_id'])
    assert saved['execution_status'] == 'NOT_SUBMITTED'
    assert saved['cost']['approved'] is False
    assert cli.build_count == 0


def test_native_unknown_build_receipt_reconciles_without_resubmitting(
        material_integration_env, tmp_path):
    attempt, root = native_owner(material_integration_env)
    class AcceptedButReplyLost(NativeBuildBoundary):
        candidate = None
        def build(self, workspace, source, *, title, runtime_profile=None):
            self.build_count += 1
            self.candidate = {"id": "bld_native_uncertain_001", "title": title,
                              "run": str(source),
                              "createdAt": datetime.now(timezone.utc).isoformat(),
                              "outcome": "complete"}
            raise HypitIntegrationError("fixture terminal reply lost after acceptance")

        def builds(self, _workspace, *, limit=100):
            return {"format": "hypit.cli-builds@1", "builds": [self.candidate]}

    cli = AcceptedButReplyLost(root)
    _approved_native(attempt, tmp_path, cli)
    with pytest.raises(HypitIntegrationError, match="terminal reply lost"):
        service.submit_film_build(attempt["attempt_id"], title="offline uncertain", cli=cli)
    saved = service.get_film_attempt(attempt["attempt_id"])
    assert saved["execution_status"] == "SUBMISSION_UNCERTAIN"
    replay = service.submit_film_build(attempt["attempt_id"], title="not again", cli=cli)
    assert replay["idempotent_replay"] is True and cli.build_count == 1
    reconciled = service.reconcile_film_submission(attempt["attempt_id"], cli=cli)
    assert reconciled["status"] == "reconciled"
    assert reconciled["attempt"]["build"]["build_id"] == "bld_native_uncertain_001"
    assert cli.build_count == 1


class _NativeExportBoundary(NativeBuildBoundary):
    """Local fake CLI download, with real Easel staged file/receipt hashing."""
    def __init__(self, root):
        super().__init__(root)
        self.get_calls = []

    def get(self, workspace, build_id, output, destination):
        self.get_calls.append((build_id, output))
        Path(destination).write_bytes(("native-fixture:" + output).encode("utf-8"))
        return {"format": "hypit.cli-get@1", "build": build_id, "output": output}


def _native_completed_build(attempt, root, tmp_path, cli, monkeypatch):
    from easel import creation
    _approved_native(attempt, tmp_path, cli)
    submitted = service.submit_film_build(
        attempt["attempt_id"], title="offline Native fixture", cli=cli)
    assert submitted["execution_status"] == "SUBMITTED" and cli.build_count == 1
    # Only the external completion signal is a fixture, never Hypit Build itself.
    service.update_film_attempt(attempt["attempt_id"],
        event="fixture_external_build_completed", execution_status="BUILD_COMPLETE")
    monkeypatch.setattr(service, "_validate_video", lambda path, require_audio: {
        "duration_seconds": 20.0, "width": 720, "height": 1280,
        "audio_present": bool(require_audio), "size_bytes": Path(path).stat().st_size,
    })
    return creation.OUTPUTS_DIR


def test_native_export_validation_failure_removes_staged_media_and_leaves_no_receipt(
        material_integration_env, tmp_path, monkeypatch):
    attempt, root = native_owner(material_integration_env)
    cli = _NativeExportBoundary(root)
    outputs = _native_completed_build(attempt, root, tmp_path, cli, monkeypatch)

    def refuse_invalid_media(_path, *, require_audio):
        raise HypitIntegrationError("offline deliberately invalid media")

    monkeypatch.setattr(service, "_validate_video", refuse_invalid_media)
    with pytest.raises(HypitIntegrationError, match="deliberately invalid media"):
        service.export_film_output(attempt["attempt_id"], "final.video", cli=cli)
    saved = service.get_film_attempt(attempt["attempt_id"])
    assert not saved.get("outputs") and not saved.get("pending_output_export")
    assert not list(outputs.rglob("*.part.mp4")) and not list(outputs.rglob("final.mp4"))
    assert len(cli.get_calls) == 1


@pytest.mark.parametrize("crash_at", ["before_link", "after_link", "register"])
def test_native_export_recovers_exact_receipted_bytes_without_second_download(
        material_integration_env, tmp_path, monkeypatch, crash_at):
    from easel import creation
    attempt, root = native_owner(material_integration_env)
    cli = _NativeExportBoundary(root)
    outputs = _native_completed_build(attempt, root, tmp_path, cli, monkeypatch)
    link, save = service.os.link, service._save_attempt
    save_count = 0

    def interrupted_link(source, target):
        if crash_at == "before_link":
            raise SystemExit("offline crash before link")
        link(source, target)
        if crash_at == "after_link":
            raise SystemExit("offline crash after link")

    def interrupted_save(attempt_id, mutate):
        nonlocal save_count
        save_count += 1
        if crash_at == "register" and save_count == 2:
            raise SystemExit("offline crash before export registration")
        return save(attempt_id, mutate)

    monkeypatch.setattr(service.os, "link", interrupted_link)
    monkeypatch.setattr(service, "_save_attempt", interrupted_save)
    with pytest.raises(SystemExit, match="offline crash"):
        service.export_film_output(attempt["attempt_id"], "final.video", cli=cli)
    saved = service.get_film_attempt(attempt["attempt_id"])
    assert "pending_output_export" in saved and not saved.get("outputs")
    pending = saved["pending_output_export"]
    assert pending["output"]["result_output"] == "final.video"
    assert len(cli.get_calls) == 1

    monkeypatch.setattr(service.os, "link", link)
    monkeypatch.setattr(service, "_save_attempt", save)
    final = outputs / pending["output"]["path"]
    if crash_at == "after_link":
        original = final.read_bytes()
        final.write_bytes(b"altered-evidence")
        with pytest.raises(HypitIntegrationError, match="哈希已变化"):
            service.export_film_output(attempt["attempt_id"], "final.video", cli=cli)
        assert final.read_bytes() == b"altered-evidence"
        final.write_bytes(original)
    with pytest.raises(HypitIntegrationError, match="凭据"):
        service.export_film_output(attempt["attempt_id"], "other.video", cli=cli)
    restored = service.export_film_output(attempt["attempt_id"], "final.video", cli=cli)
    assert "pending_output_export" not in restored
    assert restored["outputs"]["final.video"] == pending["output"]
    assert restored["review"]["human"]["status"] == "pending"
    assert restored["outputs"]["final.video"]["sha256"] == service._file_sha256(final)
    assert not list(final.parent.glob("*.part.mp4"))
    assert len(cli.get_calls) == 1


def test_native_review_and_selection_are_output_bound_and_never_auto_publish(
        material_integration_env, tmp_path, monkeypatch):
    from easel import creation
    attempt, root = native_owner(material_integration_env)
    cli = _NativeExportBoundary(root)
    outputs = _native_completed_build(attempt, root, tmp_path, cli, monkeypatch)
    first = service.export_film_output(attempt["attempt_id"], "output-a", cli=cli)
    second = service.export_film_output(attempt["attempt_id"], "output-b", cli=cli)
    digest_a = first["outputs"]["output-a"]["sha256"]
    digest_b = second["outputs"]["output-b"]["sha256"]
    assert digest_a != digest_b
    with pytest.raises(HypitIntegrationError, match="审片"):
        service.select_film_attempt(attempt["creation_id"], attempt["attempt_id"], "output-a")
    with pytest.raises(HypitIntegrationError, match="PASS 缺少"):
        service.record_film_review(attempt["attempt_id"], {
            "outputName": "output-a", "sha256": digest_a,
            "truth": {"status": "pass", "notes": []},
            "style": {"status": "pass", "notes": ["approved visuals"]},
            "human": {"status": "approved"},
        })
    with pytest.raises(HypitIntegrationError, match="不匹配"):
        service.record_film_review(attempt["attempt_id"], {
            "outputName": "output-a", "sha256": digest_b,
            "truth": {"status": "pass", "notes": ["approved facts"]},
            "style": {"status": "pass", "notes": ["approved visuals"]},
            "human": {"status": "approved"},
        })
    review = service.record_film_review(attempt["attempt_id"], {
        "outputName": "output-a", "sha256": digest_a,
        "truth": {"status": "pass", "notes": ["verified actual output A"]},
        "style": {"status": "pass", "notes": ["consistent Director framing"]},
        "human": {"status": "approved"},
    })
    assert review["review_status"] == "APPROVED"
    with pytest.raises(HypitIntegrationError, match="完整审片"):
        service.select_film_attempt(attempt["creation_id"], attempt["attempt_id"], "output-b")
    selected = service.select_film_attempt(
        attempt["creation_id"], attempt["attempt_id"], "output-a")
    assert selected["selected_attempt_id"] == attempt["attempt_id"]
    assert selected["selected_output_name"] == "output-a"
    assert selected["publication"]["publish_automatically"] is False
    assert selected["publication"]["material_usage"] == first["outputs"]["output-a"]["material_usage"]
    asset = selected["content_asset"]
    archived = outputs / asset["path"]
    assert archived.read_bytes() == (outputs / first["outputs"]["output-a"]["path"]).read_bytes()
    manifest = json.loads((outputs / asset["manifest"]).read_text())
    assert manifest["source"]["creation_id"] == attempt["creation_id"]
    assert manifest["source"]["attempt_id"] == attempt["attempt_id"]
    assert manifest["source"]["build_id"] == review["build"]["build_id"]
    with pytest.raises(HypitIntegrationError, match="审片|批准|完整"):
        service.select_film_attempt(attempt["creation_id"], attempt["attempt_id"], "output-b")



def test_native_review_retraction_revokes_selected_output_and_keeps_export_evidence(
        material_integration_env, tmp_path, monkeypatch):
    """Late Creator refusal must revoke the selection without erasing actual output."""
    from easel import creation
    attempt, root = native_owner(material_integration_env)
    cli = _NativeExportBoundary(root)
    outputs = _native_completed_build(attempt, root, tmp_path, cli, monkeypatch)
    exported = service.export_film_output(attempt["attempt_id"], "final.video", cli=cli)
    record = exported["outputs"]["final.video"]
    service.record_film_review(attempt["attempt_id"], {
        "outputName": "final.video", "sha256": record["sha256"],
        "truth": {"status": "pass", "notes": ["checked actual evidence"]},
        "style": {"status": "pass", "notes": ["checked Director style"]},
        "human": {"status": "approved"},
    })
    selected = service.select_film_attempt(
        attempt["creation_id"], attempt["attempt_id"], "final.video")
    assert selected["selected_attempt_id"] == attempt["attempt_id"]
    archived = outputs / selected["content_asset"]["path"]
    assert archived.is_file()
    revoked = service.record_film_review(attempt["attempt_id"], {
        "outputName": "final.video", "sha256": record["sha256"],
        "truth": {"status": "modify", "notes": ["Truth requires further review"]},
        "style": {"status": "pass", "notes": ["Director style unchanged"]},
        "human": {"status": "pending"},
    })
    assert revoked["review_status"] == "PENDING"
    work = creation.get_creation(attempt["creation_id"])
    assert "selected_attempt_id" not in work
    assert work["publication"]["status"] == "REVIEW_REQUIRED"
    assert work["status"] == "producing"
    assert archived.is_file()
    with pytest.raises(HypitIntegrationError, match="审片|完整"):
        service.select_film_attempt(
            attempt["creation_id"], attempt["attempt_id"], "final.video")

@pytest.mark.parametrize("pricing", [
    {"format": "hypit.cli-pricing@1", "requestCount": 2,
     "groups": [{"pricing": {"kind": "provider"}}]},
    {"format": "hypit.cli-pricing@1", "requestCount": 2,
     "groups": [], "total": {"amount": 1.0}},
    {"format": "hypit.cli-pricing@1", "requestCount": 0, "groups": []},
    {"format": "hypit.cli-pricing@1", "requestCount": 1, "groups": [],
     "total": "not-a-quote"},
])
def test_native_pricing_unknown_is_not_an_implicit_spend_cap(
        material_integration_env, tmp_path, pricing):
    attempt, root = native_owner(material_integration_env)

    class PricingBoundary(NativeBuildBoundary):
        def pricing(self, *_args, **_kwargs):
            return pricing

    cli = PricingBoundary(root)
    _approved_native(attempt, tmp_path, cli)
    saved = service.get_film_attempt(attempt["attempt_id"])
    assert saved["cost"]["pricing_sha256"] == service._contract_sha256(pricing)
    assert saved["cost"]["plan_sha256"] == saved["plan"]["contract_sha256"]
    assert saved["cost"]["total"]["status"] == "unknown"
    assert saved["cost"]["approved_budget_is_hard_spend_cap"] is False
    assert saved["cost"]["limit_enforced_by_hypit"] is False
    assert cli.build_count == 0


def test_native_changed_pricing_revokes_prior_cost_approval(
        material_integration_env, tmp_path):
    from easel import creation
    attempt, root = native_owner(material_integration_env)
    cli = NativeBuildBoundary(root)
    _approved_native(attempt, tmp_path, cli)
    with creation.edit_creation(attempt["creation_id"]) as work:
        saved = next(row for row in work["hypit_attempts"]
                     if row["attempt_id"] == attempt["attempt_id"])
        saved["cost"]["pricing"] = {
            "format": "hypit.cli-pricing@1", "requestCount": 99, "groups": []}
    with pytest.raises(HypitIntegrationError, match="fingerprint|批准|重新"):
        service.submit_film_build(attempt["attempt_id"], title="changed quote", cli=cli)
    saved = service.get_film_attempt(attempt["attempt_id"])
    assert saved["execution_status"] == "NOT_SUBMITTED"
    assert saved["cost"]["approved"] is False and cli.build_count == 0


def test_native_unknown_build_failure_is_redacted_and_not_retried(
        material_integration_env, tmp_path):
    attempt, root = native_owner(material_integration_env)

    class SecretErrorBoundary(NativeBuildBoundary):
        def build(self, *_args, **_kwargs):
            self.build_count += 1
            raise HypitIntegrationError("provider says sk-testsecretvalue123456")

    cli = SecretErrorBoundary(root)
    _approved_native(attempt, tmp_path, cli)
    with pytest.raises(HypitIntegrationError):
        service.submit_film_build(attempt["attempt_id"], title="secret failure", cli=cli)
    saved = service.get_film_attempt(attempt["attempt_id"])
    assert saved["execution_status"] == "SUBMISSION_UNCERTAIN"
    redacted = saved["last_error"]["message"]
    assert "sk-testsecretvalue123456" not in redacted
    assert "[REDACTED]" in redacted
    replay = service.submit_film_build(attempt["attempt_id"], title="another click", cli=cli)
    assert replay["idempotent_replay"] is True and cli.build_count == 1




def test_native_hypit_subprocess_stderr_secret_redacted_at_error_and_persistence(
        material_integration_env, tmp_path, monkeypatch):
    """Real CLI adapter's subprocess error is redacted before any persisted Attempt."""
    from easel.integrations.hypit import cli as hypit_cli
    attempt, root = native_owner(material_integration_env)
    fake = NativeBuildBoundary(root)
    _approved_native(attempt, tmp_path, fake)

    class FailedProcess:
        returncode = 1
        stdout = "not-json"
        stderr = "MINIMAX_API_KEY=sk-testsecretvalue123456"

    observed = []
    original_run = hypit_cli.subprocess.run
    def subprocess_failure(argv, **kwargs):
        if argv and argv[0] == 'hypit':
            observed.append((argv, kwargs))
            return FailedProcess()
        # Parser's installed Node version probe remains real local tooling;
        # only the Hypit external process itself is simulated.
        return original_run(argv, **kwargs)

    monkeypatch.setattr(hypit_cli.subprocess, "run", subprocess_failure)
    adapter = hypit_cli.HypitCLI(executable="hypit")
    with pytest.raises(HypitIntegrationError) as caught:
        service.submit_film_build(attempt["attempt_id"], title="redacted-offline", cli=adapter)
    assert "sk-testsecretvalue123456" not in str(caught.value)
    saved = service.get_film_attempt(attempt["attempt_id"])
    assert saved["execution_status"] == "SUBMISSION_UNCERTAIN"
    assert saved["last_error"]["operation"] == "build_submission"
    assert "sk-testsecretvalue123456" not in saved["last_error"]["message"]
    assert "[REDACTED]" in saved["last_error"]["message"]
    assert observed and all("MINIMAX_API_KEY" not in kw["env"] for _, kw in observed)
    replay = service.submit_film_build(attempt["attempt_id"], title="retry-not-allowed", cli=adapter)
    assert replay["idempotent_replay"] is True and len(observed) == 1

def test_native_submitted_attempt_cannot_revalidate_or_reset_build(
        material_integration_env, tmp_path):
    attempt, root = native_owner(material_integration_env)
    cli = NativeBuildBoundary(root)
    _approved_native(attempt, tmp_path, cli)
    submitted = service.submit_film_build(attempt["attempt_id"], title="once", cli=cli)
    assert submitted["execution_status"] == "SUBMITTED"
    with pytest.raises(HypitIntegrationError, match="已提交"):
        service.validate_film_attempt(attempt["attempt_id"], native.RUN, cli=cli)
    saved = service.get_film_attempt(attempt["attempt_id"])
    assert saved["execution_status"] == "SUBMITTED" and cli.build_count == 1

def test_native_verified_zero_cost_pricing_permits_zero_approval_without_provider_call(
        material_integration_env, tmp_path):
    """Exactly all-local requests, not mere empty groups, authorize zero spend."""
    attempt, root = native_owner(material_integration_env)
    class FreeNative(NativeBuildBoundary):
        def pricing(self, *_args, **_kwargs):
            return {"format": "hypit.cli-pricing@1", "requestCount": 2,
                    "noChargeRequestCount": 2, "groups": []}

    cli = FreeNative(root)
    service.complete_film_authoring(attempt["attempt_id"], cli=cli)
    runtime = tmp_path / "native-local-zero-pricing.runtime.json"
    runtime.write_text(json.dumps({
        "format": "hypit.runtime-local@1", "dataRoot": ".native-zero-cost",
        "credentials": {}, "endpoints": {}, "bindings": {},
    }) + "\n")
    service.resolve_film_attempt_runtime(attempt["attempt_id"], str(runtime))
    service.validate_film_attempt(attempt["attempt_id"], native.RUN, cli=cli)
    priced = service.estimate_film_attempt(attempt["attempt_id"], cli=cli)
    assert priced["cost"]["total"] == {"status": "known", "currency": "USD",
        "amount": 0.0, "reason": "Hypit 确认全部请求无 Provider 费用"}
    approved = service.approve_film_cost(attempt["attempt_id"], 0)
    assert approved["cost"]["approved_budget_usd"] == 0
    assert cli.build_count == 0
    # Changing frozen fee proof cannot silently retain zero-budget approval.
    from easel import creation
    with creation.edit_creation(attempt["creation_id"]) as work:
        saved = next(a for a in work["hypit_attempts"]
                     if a["attempt_id"] == attempt["attempt_id"])
        saved["cost"]["pricing"]["noChargeRequestCount"] = 1
    with pytest.raises(HypitIntegrationError):
        service.submit_film_build(attempt["attempt_id"], title="zero cost revoked", cli=cli)
    assert service.get_film_attempt(attempt["attempt_id"])["cost"]["approved"] is False
    assert cli.build_count == 0


def test_native_multi_attempt_selection_cleanup_retries_after_archive_symlink_and_io(
        material_integration_env, tmp_path, monkeypatch):
    """Never destroy evidence before Content Library registration; retry only owned media."""
    from easel import creation
    from easel.content_assets import register_selected_output
    attempt, root = native_owner(material_integration_env)
    cli = _NativeExportBoundary(root)
    output_dir = _native_completed_build(attempt, root, tmp_path, cli, monkeypatch)
    exported = service.export_film_output(attempt["attempt_id"], "final.video", cli=cli)
    exported_info = exported["outputs"]["final.video"]
    output_file = output_dir / exported_info["path"]
    original_output = output_file.read_bytes()
    service.record_film_review(attempt["attempt_id"], {
        "outputName": "final.video", "sha256": exported_info["sha256"],
        "truth": {"status": "pass", "notes": ["verified output"]},
        "style": {"status": "pass", "notes": ["Director style verified"]},
        "human": {"status": "approved"},
    })
    prior = service.create_film_attempt(
        attempt["creation_id"], attempt["handoff"]["handoff_id"],
        preparation_key="d" * 64, runtime_status="NOT_CONFIGURED")
    assert prior["attempt_id"] != attempt["attempt_id"]
    service.update_film_attempt(prior["attempt_id"],
        event="fixture_prior_build_failed", execution_status="BUILD_FAILED")
    prior_root = Path(prior["workspace"]["path"])
    prior_asset = prior_root / "materials/assets/failed/media.mp4"
    prior_asset.parent.mkdir(parents=True, exist_ok=True)
    prior_asset.write_bytes(b"fixture original failed media")
    prior_meta = prior_asset.with_name("asset.json")
    prior_meta.write_text('{"evidence":"retained"}')
    current_asset = root / "materials/assets/current/media.png"
    current_asset.parent.mkdir(parents=True, exist_ok=True)
    current_asset.write_bytes(b"fixture selected attempt media")
    current_meta = current_asset.with_name("asset.json")
    current_meta.write_text('{"rights":"retained"}')
    external = tmp_path / "unowned-original.png"
    external.write_bytes(b"outside the owned Attempt tree")
    symlink = current_asset.with_name("outside.png")
    symlink.symlink_to(external)

    with monkeypatch.context() as broken_archive:
        broken_archive.setattr("easel.content_assets.register_selected_output",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                OSError("fixture durable archive registration failure")))
        with pytest.raises(OSError, match="archive registration failure"):
            service.select_film_attempt(
                attempt["creation_id"], attempt["attempt_id"], "final.video")
    before_selection = creation.get_creation(attempt["creation_id"])
    assert "selected_attempt_id" not in before_selection
    assert current_asset.read_bytes() == b"fixture selected attempt media"
    assert prior_asset.read_bytes() == b"fixture original failed media"
    assert output_file.read_bytes() == original_output

    original_unlink = Path.unlink
    def blocked_prior_unlink(path, *args, **kwargs):
        if path == prior_asset:
            raise OSError("fixture prior-media unlink interrupted")
        return original_unlink(path, *args, **kwargs)

    with monkeypatch.context() as broken_media:
        broken_media.setattr(Path, "unlink", blocked_prior_unlink)
        first = service.select_film_attempt(
            attempt["creation_id"], attempt["attempt_id"], "final.video")
    assert first["selected_attempt_id"] == attempt["attempt_id"]
    assert first["selected_output_name"] == "final.video"
    assert first["material_cleanup"]["status"] == "PENDING"
    statuses = {a["attempt_id"]: a["material_cleanup"]["status"]
                for a in first["hypit_attempts"]}
    assert statuses[attempt["attempt_id"]] == "PENDING"
    assert statuses[prior["attempt_id"]] == "PENDING"
    assert prior_asset.is_file() and current_asset.is_file()
    assert external.read_bytes() == b"outside the owned Attempt tree"
    archived = output_dir / first["content_asset"]["path"]
    assert archived.read_bytes() == original_output
    asset_id = first["content_asset"]["asset_id"]
    initial_counts = {a["attempt_id"]: a["material_cleanup"]["deleted_files"]
                      for a in first["hypit_attempts"]}

    symlink.unlink()
    resumed = service.select_film_attempt(
        attempt["creation_id"], attempt["attempt_id"], "final.video")
    assert resumed["material_cleanup"]["status"] == "COMPLETE"
    assert all(a["material_cleanup"]["status"] == "COMPLETE"
               for a in resumed["hypit_attempts"])
    assert not prior_asset.exists() and not current_asset.exists()
    assert prior_meta.read_text() == '{"evidence":"retained"}'
    assert current_meta.read_text() == '{"rights":"retained"}'
    assert external.read_bytes() == b"outside the owned Attempt tree"
    assert output_file.read_bytes() == original_output
    assert archived.read_bytes() == original_output
    assert resumed["content_asset"]["asset_id"] == asset_id
    assert service.get_film_attempt(prior["attempt_id"])["execution_status"] == "BUILD_FAILED"
    assert resumed["publication"]["publish_automatically"] is False
    assert all(a["material_cleanup"]["deleted_files"] >= initial_counts[a["attempt_id"]]
               for a in resumed["hypit_attempts"])

    repeated = service.select_film_attempt(
        attempt["creation_id"], attempt["attempt_id"], "final.video")
    assert {a["attempt_id"]: a["material_cleanup"]["deleted_files"]
            for a in repeated["hypit_attempts"]} == {
        a["attempt_id"]: a["material_cleanup"]["deleted_files"]
        for a in resumed["hypit_attempts"]}
    assert repeated["content_asset"]["asset_id"] == asset_id


def test_native_handoff_truth_bytes_tamper_blocks_native_before_build(
        material_integration_env, tmp_path):
    """Frozen handoff truth must not be rewritten after pricing approval."""
    attempt, root = native_owner(material_integration_env)
    cli = NativeBuildBoundary(root)
    _approved_native(attempt, tmp_path, cli)
    source = root / "handoff/truth-packet.json"
    assert source.is_file()
    source.chmod(0o644)
    source.write_text('{"fixture_tampered_truth":true}')
    from easel.integrations.hypit.authoring_publication import AuthoringPublicationError
    with pytest.raises(AuthoringPublicationError,
                       match="Frozen Authoring domain evidence cannot be verified") as refused:
        service.submit_film_build(attempt["attempt_id"], title="tampered truth", cli=cli)
    assert isinstance(refused.value.__cause__, HypitIntegrationError)
    assert "hash 不匹配" in str(refused.value.__cause__)
    saved = service.get_film_attempt(attempt["attempt_id"])
    assert saved["execution_status"] == "NOT_SUBMITTED"
    assert cli.build_count == 0


def test_native_failed_build_status_preserves_structured_local_failure(
        material_integration_env, tmp_path):
    attempt, root = native_owner(material_integration_env)
    class FailedStatusNative(NativeBuildBoundary):
        def status(self, workspace, build_id, *, runtime_profile=None):
            return {"format": "hypit.cli-status@1", "build": {
                "id": build_id,
                "work": {"state": "failed", "outcome": "failed"},
                "failure": "render worker failed to decode frame",
            }}
    cli = FailedStatusNative(root)
    _approved_native(attempt, tmp_path, cli)
    submitted = service.submit_film_build(attempt["attempt_id"],
                                          title="offline status failed", cli=cli)
    assert submitted["execution_status"] == "SUBMITTED"
    observed = service.refresh_film_build(attempt["attempt_id"], cli=cli)
    assert observed["execution_status"] == "BUILD_FAILED"
    assert observed["last_error"]["message"] == "render worker failed to decode frame"
    assert cli.build_count == 1

def test_native_rights_constraints_survive_export_to_manual_publication(
        material_integration_env, tmp_path, monkeypatch):
    from easel.materials.application.assembly import MaterialBundleAssembler
    from easel.materials.application.readiness import MaterialReadinessCalculator
    from easel.materials.domain import CandidateSource, RightsInfo, RightsStatus, RightsEvidence
    from easel.materials.store import AttemptMaterialStore
    from easel.integrations.material_layer import MaterialGateIntegration, ProductionAuthoringIntegration
    from tests.test_material_integration import _planning, _contracts, _stage_native_selected_image
    from easel.content_assets import assert_media_publication_allowed, ContentAssetRegistrationError

    attempt = material_integration_env
    _planning(attempt)
    root = Path(attempt["workspace"]["path"])
    plan, asset, run, bundle, _, _ = _contracts(attempt, root)
    page = "https://example.org/photo/1"
    asset = asset.model_copy(update={
        "source": CandidateSource(kind="fixture", provider="fixture", creator="Ada",
                                  source_page=page, provider_asset_id="fixture-1"),
        "rights": RightsInfo(status=RightsStatus.ATTRIBUTION_REQUIRED,
            attribution_required=True, attribution_text=f"Photo by Ada — {page}",
            usage_constraints=("internal_production_only",),
            evidence=(RightsEvidence(kind="asset_license", reference="fixture:license"),)),
    })
    store = AttemptMaterialStore(root)
    store.write_asset(asset)
    bundle = MaterialBundleAssembler().assemble(plan, run, (asset,),
        bundle.matches, bundle_id=bundle.bundle_id)
    readiness, gaps = MaterialReadinessCalculator(store=store).calculate(plan, bundle)
    assert readiness.status.value == "READY"
    attempt.update(MaterialGateIntegration().record(
        attempt, plan, bundle, run, readiness, gaps)["attempt"])
    attempt.update(ProductionAuthoringIntegration().prepare(attempt)["attempt"])
    service.begin_film_authoring(attempt["attempt_id"])
    _, check = _stage_native_selected_image(attempt, asset, root)
    ready = service.complete_film_authoring(attempt["attempt_id"], cli=check)
    assert ready["authoring_status"] == "AUTHORING_READY"
    cli = _NativeExportBoundary(root)
    outputs = _native_completed_build(attempt, root, tmp_path, cli, monkeypatch)
    exported = service.export_film_output(attempt["attempt_id"], "final.video", cli=cli)
    usage = [{"asset_id": asset.asset_id, "sha256": asset.file.sha256,
              "constraints": ["internal_production_only"]}]
    assert exported["outputs"]["final.video"]["material_usage"] == usage
    attribution = exported["outputs"]["final.video"]["attribution"]
    assert len(attribution) == 1 and attribution[0]["creator"] == "Ada"
    assert attribution[0]["credit_text"] == f"Photo by Ada — {page}"
    digest = exported["outputs"]["final.video"]["sha256"]
    service.record_film_review(attempt["attempt_id"], {
        "outputName": "final.video", "sha256": digest,
        "truth": {"status": "pass", "notes": ["verified actual facts"]},
        "style": {"status": "pass", "notes": ["verified composition"]},
        "human": {"status": "approved"},
    })
    selected = service.select_film_attempt(
        attempt["creation_id"], attempt["attempt_id"], "final.video")
    assert selected["publication"]["status"] == "RIGHTS_REVIEW_REQUIRED"
    assert selected["publication"]["material_usage"] == usage
    assert selected["publication"]["publish_automatically"] is False
    with pytest.raises(ContentAssetRegistrationError):
        assert_media_publication_allowed(outputs / selected["content_asset"]["path"])

def test_native_export_requires_real_audio_track_in_encoded_mp4(
        material_integration_env, tmp_path, monkeypatch):
    """Audio-required output rejects a genuinely decoded silent local MP4."""
    import shutil
    import subprocess
    assert shutil.which("ffmpeg") and shutil.which("ffprobe")
    attempt, root = native_owner(material_integration_env)
    class SilentMP4(_NativeExportBoundary):
        def get(self, workspace, build_id, output, destination):
            self.get_calls.append((build_id, output))
            subprocess.run([
                "ffmpeg", "-nostdin", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "color=gray:s=90x160:r=5:d=10",
                "-an", "-c:v", "libx264", "-preset", "ultrafast",
                "-t", "10", str(destination),
            ], check=True, capture_output=True, timeout=30)
            return {"format": "hypit.cli-get@1", "build": build_id, "output": output}

    cli = SilentMP4(root)
    original_video_validator = service._validate_video
    outputs = _native_completed_build(attempt, root, tmp_path, cli, monkeypatch)
    # Unlike the receipt-transaction tests, exercise the installed ffprobe
    # validator on genuine decoded bytes rather than the external-video stub.
    monkeypatch.setattr(service, "_validate_video", original_video_validator)
    service.update_film_attempt(attempt["attempt_id"],
        event="fixture_audio_required", material_audio_policy={"requires_audio": True})
    with pytest.raises(HypitIntegrationError, match="没有音频轨"):
        service.export_film_output(attempt["attempt_id"], "final.video", cli=cli)
    saved = service.get_film_attempt(attempt["attempt_id"])
    assert not saved.get("outputs") and not saved.get("pending_output_export")
    assert not list(outputs.rglob("*.part.mp4"))
    assert len(cli.get_calls) == 1

class VerifiedLocalCommissionCLI(NativeBuildBoundary):
    def pricing(self, *_args, **_kwargs):
        return {"format": "hypit.cli-pricing@1", "requestCount": 2,
                "noChargeRequestCount": 2, "groups": []}


def _prepare_verified_local_commission(attempt, tmp_path, cli):
    """Run original Native Authoring/Plan and use only verified zero-charge pricing."""
    service.complete_film_authoring(attempt["attempt_id"], cli=cli)
    runtime = tmp_path / "verified-local-commission.runtime.json"
    runtime.write_text(json.dumps({
        "format": "hypit.runtime-local@1", "dataRoot": ".verified-local-commission",
        "credentials": {}, "endpoints": {}, "bindings": {},
    }) + "\n")
    service.resolve_film_attempt_runtime(attempt["attempt_id"], str(runtime))
    service.validate_film_attempt(attempt["attempt_id"], native.RUN, cli=cli)
    priced = service.estimate_film_attempt(attempt["attempt_id"], cli=cli)
    assert service.pricing_has_no_provider_charge(priced["cost"]["pricing"])
    assert priced["cost"]["total"]["status"] == "known"
    return priced


def _confirm_real_commission(creation_id):
    """Fixture uses the real explicit chat confirmation API, not a fake approved record."""
    from easel import creation
    import hashlib
    proposal = '[{"role":"user","content":"confirmed fixture Creator video proposal"}]'
    proposal_sha256 = hashlib.sha256(proposal.encode("utf-8")).hexdigest()
    # The shared Material fixture starts from a manually created Creation.
    # Give *only this disposable Creation* a chat origin before normal enrollment.
    with creation.edit_creation(creation_id) as work:
        work["origin"] = {"type": "chat", "session_hash": "c" * 64}
    creation.ensure_chat_proposal_state(creation_id)
    creation.mark_chat_proposal_ready(creation_id)
    confirmed = creation.confirm_chat_proposal(
        creation_id, "user-confirmed-turn", delivery_proposal=proposal,
        proposal_sha256=proposal_sha256)
    assert confirmed["chat_workflow"]["proposal_status"] == "CONFIRMED"
    assert confirmed["delivery"]["proposal_sha256"] == proposal_sha256
    return confirmed


def test_verified_native_commission_requires_explicit_frozen_confirmation(
        material_integration_env, tmp_path):
    attempt, root = native_owner(material_integration_env)
    cli = VerifiedLocalCommissionCLI(root)
    _prepare_verified_local_commission(attempt, tmp_path, cli)
    with pytest.raises(HypitIntegrationError, match="没有授权"):
        service.approve_film_cost(attempt["attempt_id"], 0, use_commission=True)
    _confirm_real_commission(attempt["creation_id"])
    approved = service.approve_film_cost(attempt["attempt_id"], 0, use_commission=True)
    from easel import creation
    work = creation.get_creation(attempt["creation_id"])
    assert approved["cost"]["approval_kind"] == "confirmed_commission_no_charge"
    assert approved["cost"]["approved_budget_usd"] == 0
    assert approved["cost"]["commission_authorization"] == {
        "proposal_sha256": work["delivery"]["proposal_sha256"],
        "confirmed_at": work["delivery"]["confirmed_at"],
    }
    submitted = service.submit_film_build(attempt["attempt_id"],
                                           title="verified offline commission", cli=cli)
    assert submitted["execution_status"] == "SUBMITTED"
    replay = service.submit_film_build(attempt["attempt_id"],
                                       title="duplicate offline commission", cli=cli)
    assert replay["idempotent_replay"] is True
    assert cli.build_count == 1


@pytest.mark.parametrize("mutation", [
    "unconfirm", "stop", "remove_no_charge_authorization",
    "replace_confirmation_digest", "replace_confirmed_time",
])
def test_native_commission_revocation_blocks_build_before_external_effect(
        material_integration_env, tmp_path, mutation):
    from easel import creation
    attempt, root = native_owner(material_integration_env)
    cli = VerifiedLocalCommissionCLI(root)
    _prepare_verified_local_commission(attempt, tmp_path, cli)
    _confirm_real_commission(attempt["creation_id"])
    approved = service.approve_film_cost(attempt["attempt_id"], 0, use_commission=True)
    assert approved["cost"]["approved"] is True
    with creation.edit_creation(attempt["creation_id"]) as work:
        if mutation == "unconfirm":
            work["chat_workflow"]["proposal_status"] = "DISCUSSING"
        elif mutation == "stop":
            work["delivery"]["stopped"] = True
        elif mutation == "remove_no_charge_authorization":
            work["delivery"]["authorization"]["no_provider_charge_build"] = False
        elif mutation == "replace_confirmation_digest":
            # The user-authored proposal is no longer the confirmed one.
            work["delivery"]["proposal"] += " amended"
        elif mutation == "replace_confirmed_time":
            work["delivery"]["confirmed_at"] = "1999-12-31T00:00:00Z"
    with pytest.raises(HypitIntegrationError, match="委托|授权|确认|批准"):
        service.submit_film_build(attempt["attempt_id"], title="revoked offline commission", cli=cli)
    current = service.get_film_attempt(attempt["attempt_id"])
    assert current["execution_status"] == "NOT_SUBMITTED"
    assert cli.build_count == 0

def test_native_commission_approval_cas_rechecks_latest_creation_confirmation(
        material_integration_env, tmp_path, monkeypatch):
    """A confirmation revoked after preflight but before the locked write never approves."""
    from easel import creation
    attempt, root = native_owner(material_integration_env)
    cli = VerifiedLocalCommissionCLI(root)
    _prepare_verified_local_commission(attempt, tmp_path, cli)
    _confirm_real_commission(attempt["creation_id"])
    save_original = service._save_attempt
    injected = []

    def revoke_before_locked_approval(attempt_id, mutate, *, include_creation=False):
        if include_creation and not injected:
            injected.append(True)
            with creation.edit_creation(attempt["creation_id"]) as work:
                work["delivery"]["stopped"] = True
        return save_original(attempt_id, mutate, include_creation=include_creation)

    monkeypatch.setattr(service, "_save_attempt", revoke_before_locked_approval)
    with pytest.raises(HypitIntegrationError, match="委托|授权"):
        service.approve_film_cost(attempt["attempt_id"], 0, use_commission=True)
    saved = service.get_film_attempt(attempt["attempt_id"])
    assert injected == [True] and saved["cost"]["approved"] is False
    assert saved["execution_status"] == "NOT_SUBMITTED" and cli.build_count == 0
