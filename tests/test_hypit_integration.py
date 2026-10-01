from __future__ import annotations

import json
import hashlib
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from easel import creation, creative_mode  # noqa: E402
from easel.integrations.hypit import cli as hypit_cli  # noqa: E402
from easel.integrations.hypit import handoff, service  # noqa: E402
from easel.integrations.hypit.errors import HypitIntegrationError  # noqa: E402
from easel.materials.domain import (  # noqa: E402
    CandidateSource, FileInfo, MaterialAsset, MediaType, RightsEvidence, RightsInfo, RightsStatus,
)
from easel.materials.store import AttemptMaterialStore  # noqa: E402


@pytest.fixture
def integration_env(tmp_path, monkeypatch):
    outputs = tmp_path / "outputs"
    modes = tmp_path / "creative_modes"
    mode_dir = modes / "clear_memo_video"
    mode_dir.mkdir(parents=True)
    (mode_dir / "mode.json").write_text(json.dumps({
        "id": "clear_memo_video", "name": "清醒备忘录", "version": "1.0",
        "routes": ["douyin-video"],
    }), encoding="utf-8")
    for filename in (
        "director-treatment.md", "visual-bible.md", "audio-bible.md",
        "editing-bible.md", "qc-rubric.md",
    ):
        (mode_dir / filename).write_text(f"# {filename}\n", encoding="utf-8")

    monkeypatch.setattr(creation, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(creation, "CREATIONS_DIR", outputs / "_creations")
    monkeypatch.setattr(creative_mode, "CREATIVE_MODES_DIR", modes)
    monkeypatch.setattr(handoff, "CREATIVE_MODES_DIR", modes, raising=False)
    monkeypatch.setenv("EASEL_HYPIT_HOME", str(tmp_path / ".easel" / "hypit"))
    runtime_profile = tmp_path / "hypit-runtime.json"
    runtime_profile.write_text(json.dumps({
        "format": "hypit.runtime-local@1",
        "dataRoot": ".hypit/runtimes/local",
        "credentials": {},
        "endpoints": {},
        "bindings": {},
    }) + "\n", encoding="utf-8")
    work = creation.create_creation(
        "AI 越来越强以后，程序员真正稀缺的能力是什么？",
        profile="个人经营实践",
        creative_mode="clear_memo_video",
        route="douyin-video",
    )
    return {"tmp": tmp_path, "outputs": outputs, "work": work,
            "runtime_profile": str(runtime_profile)}


def create_test_handoff(work):
    return service.create_creation_handoff(
        work["id"],
        content_core={"schema": "content-core@1", "question": work["idea"]},
        truth_packet={
            "schema": "easel-truth-packet@1",
            "claims": [{"id": "c1", "text": "这是一个观察", "kind": "opinion"}],
            "personal_facts": [],
            "forbidden_inventions": ["不得虚构第一人称经历"],
            "uncertainty_policy": {"unknown_must_not_be_fact": True},
        },
        creator_context={
            "schema": "easel-creator-context@1",
            "identity": {"public_description": "普通技术从业者"},
            "audience": "普通职场人",
            "voice": {"tone": "克制", "avoid": ["导师口吻"]},
            "relevant_context": [],
            "privacy_policy": {"do_not_infer_private_facts": True},
        },
        production_request={
            "media_type": "video", "orientation": "9:16", "language": "zh-CN",
            "preferred_duration_seconds": {"min": 20, "max": 60},
        },
        max_budget_usd=5,
    )


class FakeHypit:
    build_count = 0

    def check(self, workspace, run_source):
        return {"format": "hypit.cli-check@1", "ok": True}

    def plan(self, workspace, run_source, *, runtime_profile=None):
        return {"format": "hypit.cli-plan@1", "ok": True, "run": str(run_source)}

    def pricing(self, workspace, run_source, *, runtime_profile=None):
        return {"format": "hypit.cli-pricing@1", "requestCount": 1, "groups": []}

    def build(self, workspace, run_source, *, title, runtime_profile=None):
        self.build_count += 1
        return {"format": "hypit.cli-build@1", "build": {"id": "bld_test_001"}}

    def status(self, workspace, build_id, *, runtime_profile=None):
        return {"format": "hypit.cli-status@1", "build": {
            "id": build_id,
            "work": {"state": "done", "outcome": "complete"},
            "result": {"state": "complete", "outputCount": 1},
        }}

    def inspect(self, workspace, build_id):
        return {"format": "hypit.cli-inspect@1", "build": {"id": build_id}}

    def get(self, workspace, build_id, output, destination):
        Path(destination).write_bytes(f"test-video:{output}".encode())
        return {"format": "hypit.cli-get@1", "build": build_id, "output": output}

    def builds(self, workspace, *, limit=100):
        return {"format": "hypit.cli-builds@1", "builds": []}

    def history(self, workspace, output_name, *, source=None, limit=100):
        return {"format": "hypit.cli-history@1", "entries": []}

    def cancel(self, workspace, build_id):
        return {"format": "hypit.cli-cancel@1", "build": build_id, "requested": True}


class FailingBuildHypit(FakeHypit):
    def build(self, workspace, run_source, *, title, runtime_profile=None):
        self.build_count += 1
        raise HypitIntegrationError("Build 提交响应丢失")


def make_attempt(work, integration_env):
    package = create_test_handoff(work)
    attempt = service.create_film_attempt(
        work["id"], package["handoff_id"], runtime_profile=integration_env["runtime_profile"])
    return package, attempt


def test_handoff_is_hashed_minimal_and_rejects_secrets(integration_env):
    work = integration_env["work"]
    package = create_test_handoff(work)
    folder, manifest, digest = handoff.resolve_handoff(work["id"], package["handoff_id"])

    assert digest == package["hash"]
    assert manifest["creative_mode"]["version"] == "1.0"
    assert (folder / "truth-packet.json").is_file()
    assert "MINIMAX_API_KEY" not in (folder / "creator-context.json").read_text(encoding="utf-8")

    with pytest.raises(HypitIntegrationError, match="凭证字段"):
        service.create_creation_handoff(
            work["id"], content_core={"idea": "x"},
            truth_packet={
                "schema": "easel-truth-packet@1", "claims": [], "personal_facts": [],
                "forbidden_inventions": [], "uncertainty_policy": {},
            },
            creator_context={
                "schema": "easel-creator-context@1",
                "identity": {"public_description": "x"}, "audience": "x",
                "voice": {"avoid": []}, "relevant_context": [],
                "privacy_policy": {"do_not_infer_private_facts": True},
                "api_key": "never-export",
            },
        )


def test_handoff_hash_detects_snapshot_tampering(integration_env):
    work = integration_env["work"]
    record = create_test_handoff(work)
    package = integration_env["outputs"] / record["path"]
    for path in package.rglob("*"):
        path.chmod(0o755 if path.is_dir() else 0o644)
    package.chmod(0o755)
    (package / "truth-packet.json").write_text("{}", encoding="utf-8")

    with pytest.raises(HypitIntegrationError, match="hash 不匹配"):
        handoff.resolve_handoff(work["id"], record["handoff_id"])


def test_normalizes_only_unambiguous_single_timeline_clock_reference(tmp_path):
    authored = tmp_path / "main.svml"
    authored.write_text(
        '<time:Clock id="clock-main" frame-rate="24"/>\n'
        '<time:Timeline id="program" clock="clock-main" end="15s"/>\n',
        encoding="utf-8",
    )

    assert service._normalize_single_timeline_clock_reference(authored) is True
    assert authored.read_text(encoding="utf-8") == (
        '<time:Clock id="clock" frame-rate="24"/>\n'
        '<time:Timeline id="program" clock={clock} end="15s"/>\n'
    )

    unchanged = tmp_path / "ambiguous.svml"
    original = (
        '<time:Clock id="clock-a" frame-rate="24"/>\n'
        '<time:Clock id="clock-b" frame-rate="30"/>\n'
        '<time:Timeline id="program" clock="clock-a" end="15s"/>\n'
    )
    unchanged.write_text(original, encoding="utf-8")
    assert service._normalize_single_timeline_clock_reference(unchanged) is False
    assert unchanged.read_text(encoding="utf-8") == original


def test_workspace_is_outside_repository_and_attempts_are_one_to_many(integration_env):
    work = integration_env["work"]
    first_package, first = make_attempt(work, integration_env)
    second = service.create_film_attempt(
        work["id"], first_package["handoff_id"], runtime_profile=integration_env["runtime_profile"])
    project_root = PROJECT_ROOT.resolve()

    assert Path(first["workspace"]["path"]).is_relative_to(
        (integration_env["tmp"] / ".easel" / "hypit").resolve())
    assert not Path(first["workspace"]["path"]).is_relative_to(project_root)
    assert first["attempt_id"] != second["attempt_id"]
    assert len(service.list_film_attempts(work["id"])) == 2
    task = Path(first["workspace"]["path"]) / "AUTHORING_TASK.md"
    assert task.is_file()
    task_text = task.read_text(encoding="utf-8")
    assert "easel-authoring-svrun@1" in task_text
    assert "publication_allowed" in task_text
    assert "build.enabled=false" in task_text
    authoring_task = task.read_text(encoding="utf-8")
    assert 'build.reason="stops_before_hypit_build"' in authoring_task
    assert "despite its extension" in authoring_task
    assert "Hypit Markup authoring contract (installed v0.2.7)" in authoring_task
    assert "`<svml>` root has no attributes and no XML namespace declarations" in authoring_task
    assert "windows (`at` + `for`) for its actual scenes" in authoring_task
    assert 'time:Clock id="clock" frame-rate="24"' in authoring_task
    assert 'time:Timeline id="program" clock={clock} end="12s"' in authoring_task
    assert "not the quoted string `clock=\"clock\"`" in authoring_task
    assert "invented `Scene`, `Overlay`, `Libraries`, `Tracks`" in authoring_task
    assert not (Path(first["workspace"]["path"]) / "hypit.runtime.json").exists()
    task.write_text("stale generated task")
    assert service.refresh_authoring_task(
        Path(first["workspace"]["path"]),
        handoff_id=first_package["handoff_id"],
        handoff_hash=first_package["hash"],
    ) is True
    assert "Hypit Markup authoring contract (installed v0.2.7)" in task.read_text(encoding="utf-8")
    assert service.refresh_authoring_task(
        Path(first["workspace"]["path"]),
        handoff_id=first_package["handoff_id"],
        handoff_hash=first_package["hash"],
    ) is False


def test_workspace_override_cannot_point_into_easel_repository(integration_env, monkeypatch):
    monkeypatch.setenv("EASEL_HYPIT_HOME", str(PROJECT_ROOT / ".local-hypit-test"))

    with pytest.raises(HypitIntegrationError, match="Easel 仓库之外"):
        service.create_film_attempt(
            integration_env["work"]["id"],
            create_test_handoff(integration_env["work"])["handoff_id"],
            runtime_profile=integration_env["runtime_profile"],
        )


def test_authoring_is_runtime_independent_and_static_check_only(integration_env):
    """Authoring can finish before a Runtime/plan/pricing/Build exists."""
    work = integration_env["work"]
    package = create_test_handoff(work)
    attempt = service.create_film_attempt(
        work["id"], package["handoff_id"],
        preparation_key="a" * 64,
        runtime_status="NOT_CONFIGURED",
    )
    started = service.begin_film_authoring(attempt["attempt_id"])
    assert started["authoring_status"] == "AUTHORING_RUNNING"
    assert started["execution_status"] == "BLOCKED"
    workspace = Path(started["workspace"]["path"])
    run = workspace / "productions" / "easel-authoring" / "runs" / "main.svrun"
    run.parent.mkdir(parents=True)
    run.write_text("<svrun version=\"1\"/>", encoding="utf-8")

    completed = service.complete_film_authoring(attempt["attempt_id"], cli=FakeHypit())
    assert completed["authoring_status"] == "AUTHORING_READY"
    assert completed["execution_status"] == "BLOCKED"
    assert completed["authoring"]["run_path"] == "productions/easel-authoring/runs/main.svrun"
    assert completed["plan"]["status"] == "pending"


def test_complete_lifecycle_requires_review_before_selection(integration_env, monkeypatch):
    work = creation.create_creation(
        "测试 Hypit Creation 状态投影；主题“看清再开始”",
        profile="个人经营实践",
        creative_mode="clear_memo_video",
        route="hypit_video",
        origin={"type": "chat", "session_hash": "c" * 64, "initial_turn_hash": "d" * 64},
    )
    creation.mark_chat_proposal_ready(work["id"])
    creation.confirm_chat_proposal(work["id"], "explicit-confirmation")
    _, attempt = make_attempt(work, integration_env)
    service.update_film_attempt(
        attempt["attempt_id"], event="test_copy_context_added",
        production_request={
            **attempt["production_request"],
            "production_brief": {"text_overlays": ["先看清。", "再开始。"]},
        },
    )
    workspace = Path(attempt["workspace"]["path"])
    (workspace / "runs" / "final.svrun").write_text("{}", encoding="utf-8")
    cli = FakeHypit()

    planned = service.validate_film_attempt(attempt["attempt_id"], "runs/final.svrun", cli=cli)
    assert planned["status"] == "PLANNED"
    with pytest.raises(HypitIntegrationError, match="成本批准"):
        service.submit_film_build(attempt["attempt_id"], title="测试", cli=cli)

    priced = service.estimate_film_attempt(attempt["attempt_id"], cli=cli)
    assert priced["cost"]["estimated_usd"] is None
    assert priced["cost"]["limit_enforced_by_hypit"] is False
    with pytest.raises(HypitIntegrationError, match="预算上限"):
        service.approve_film_cost(attempt["attempt_id"], 6.0)
    approved = service.approve_film_cost(attempt["attempt_id"], 4.0)
    assert approved["cost"]["approved"] is True
    submitted = service.submit_film_build(attempt["attempt_id"], title="测试作品", cli=cli)
    assert submitted["build"]["build_id"] == "bld_test_001"
    complete = service.refresh_film_build(attempt["attempt_id"], cli=cli)
    assert complete["status"] == "BUILD_COMPLETE"

    monkeypatch.setattr(service, "_validate_video", lambda _path, require_audio: {
        "duration_seconds": 30.0, "width": 720, "height": 1280,
        "audio_present": True, "size_bytes": 9,
    })
    exported = service.export_film_output(attempt["attempt_id"], "final.video", cli=cli)
    assert exported["status"] == "EXPORTED"
    assert (integration_env["outputs"] / exported["outputs"]["final.video"]["path"]).is_file()
    with pytest.raises(HypitIntegrationError, match="审片"):
        service.select_film_attempt(work["id"], attempt["attempt_id"], "final.video")

    with pytest.raises(HypitIntegrationError, match="PASS 缺少"):
        service.record_film_review(attempt["attempt_id"], {
            "outputName": "final.video", "sha256": exported["outputs"]["final.video"]["sha256"],
            "truth": {"status": "pass", "notes": []},
            "style": {"status": "pass", "notes": []},
            "human": {"status": "approved"},
        })

    system_review = {'schema': 'easel-output-quality@3', 'status': 'READY',
                     'binding': {'output_name': 'final.video', 'sha256': exported['outputs']['final.video']['sha256']}}
    service.update_film_attempt(attempt['attempt_id'], event='fixture_system_review',
                               review={**exported['review'], 'system': system_review})
    reviewed = service.record_film_review(attempt["attempt_id"], {
        "outputName": "final.video",
        "sha256": exported["outputs"]["final.video"]["sha256"],
        "truth": {"status": "pass", "notes": ["Creator reviewed the exported video."]},
        "style": {"status": "pass", "notes": ["Creator reviewed its style."]},
        "human": {"status": "approved"},
        "feedback": [],
    })
    assert reviewed["status"] == "REVIEW_APPROVED"
    assert reviewed['review']['system'] == system_review
    selected = service.select_film_attempt(work["id"], attempt["attempt_id"], "final.video")
    assert selected["selected_attempt_id"] == attempt["attempt_id"]
    assert selected["publication"]["status"] == "READY_FOR_MANUAL_PUBLISH"
    assert selected["publication"]["publish_automatically"] is False
    assert selected["status"] == "ready"
    content_asset = selected["content_asset"]
    library_file = integration_env["outputs"] / content_asset["path"]
    assert library_file.is_file()
    assert library_file.read_bytes() == (integration_env["outputs"] / exported["outputs"]["final.video"]["path"]).read_bytes()
    manifest = json.loads((integration_env["outputs"] / content_asset["manifest"]).read_text())
    assert manifest["source"]["creation_id"] == work["id"]
    assert manifest["source"]["attempt_id"] == attempt["attempt_id"]
    assert manifest["source"]["build_id"] == complete["build"]["build_id"]
    assert content_asset["theme"] == "看清再开始"
    assert content_asset["copy"]["on_screen"] == ["先看清。", "再开始。"]
    from easel.content_assets import register_selected_output
    repeated = register_selected_output(selected, attempt["attempt_id"], "final.video")
    assert repeated["asset_id"] == content_asset["asset_id"]
    assert len(list(integration_env["outputs"].glob("creation-*/final.mp4"))) == 1

    creation_file = integration_env["outputs"] / "_creations" / work["id"] / "creation.json"
    persisted = json.loads(creation_file.read_text(encoding="utf-8"))
    persisted["status"] = "planning"  # simulate a pre-projection summary already on disk
    persisted["preparation"] = {"status": "MATERIAL_NOT_READY"}  # stale earlier-stage snapshot
    creation_file.write_text(json.dumps(persisted), encoding="utf-8")
    assert creation.get_creation(work["id"])["status"] == "ready"
    assert next(row for row in creation.list_creations() if row["id"] == work["id"])["status"] == "ready"
    assert json.loads(creation_file.read_text(encoding="utf-8"))["status"] == "planning"

    cli.status = lambda workspace, build_id, *, runtime_profile=None: {
        "format": "hypit.cli-status@1", "build": {
            "id": build_id, "work": {"state": "working", "outcome": None},
        },
    }
    refreshed = service.refresh_film_build(attempt["attempt_id"], cli=cli)
    assert refreshed["status"] == "REVIEW_APPROVED"
    assert refreshed["execution_status"] == "BUILD_COMPLETE"
    assert refreshed["export_status"] == "EXPORTED"
    assert refreshed["review_status"] == "APPROVED"

    revoked = service.record_film_review(attempt["attempt_id"], {
        "outputName": "final.video",
        "sha256": exported["outputs"]["final.video"]["sha256"],
        "truth": {"status": "modify", "notes": ["需要重新核对"]},
        "style": {"status": "pass", "notes": ["Creator reviewed the selected style."]},
        "human": {"status": "pending"},
        "feedback": [],
    })
    assert revoked["status"] == "REVIEW_PENDING"
    assert "selected_attempt_id" not in creation.get_creation(work["id"])
    assert creation.get_creation(work["id"])["publication"]["status"] == "REVIEW_REQUIRED"
    assert creation.get_creation(work["id"])["status"] == "producing"


def test_material_audio_policy_requires_audio_stream_at_export(integration_env, monkeypatch):
    work = creation.create_creation(
        "导出音频门禁", profile="fixture", creative_mode="clear_memo_video", route="hypit_video",
        origin={"type": "chat", "session_hash": "e" * 64, "initial_turn_hash": "f" * 64},
    )
    creation.mark_chat_proposal_ready(work["id"])
    creation.confirm_chat_proposal(work["id"], "audio-policy-confirmed")
    _, attempt = make_attempt(work, integration_env)
    workspace = Path(attempt["workspace"]["path"])
    (workspace / "runs" / "final.svrun").write_text("{}", encoding="utf-8")
    cli = FakeHypit()
    service.validate_film_attempt(attempt["attempt_id"], "runs/final.svrun", cli=cli)
    service.estimate_film_attempt(attempt["attempt_id"], cli=cli)
    service.approve_film_cost(attempt["attempt_id"], 4.0)
    service.submit_film_build(attempt["attempt_id"], title="audio policy", cli=cli)
    service.refresh_film_build(attempt["attempt_id"], cli=cli)
    service.update_film_attempt(
        attempt["attempt_id"], event="material_audio_policy_tested",
        material_audio_policy={"requires_audio": True},
    )
    observed = {}

    def validate(_path, *, require_audio):
        observed["require_audio"] = require_audio
        return {"duration_seconds": 30.0, "width": 720, "height": 1280,
                "audio_present": True, "size_bytes": 9}

    monkeypatch.setattr(service, "_validate_video", validate)
    service.export_film_output(attempt["attempt_id"], "final.video", cli=cli)
    assert observed["require_audio"] is True


@pytest.mark.parametrize("pricing_payload", [
    {"format": "hypit.cli-pricing@1", "requestCount": 2, "groups": [], "total": {"amount": 1.0}},
    {"format": "hypit.cli-pricing@1", "requestCount": 2, "groups": [{"pricing": {"kind": "provider"}}]},
    {"format": "hypit.cli-pricing@1", "requestCount": 0, "groups": []},
    {"format": "hypit.cli-pricing@1", "requestCount": 1, "groups": [], "total": "not-a-quote"},
])
def test_pricing_keeps_aggregate_unknown_and_persists_contract_fingerprint(
    integration_env, pricing_payload,
):
    class PricingHypit(FakeHypit):
        def pricing(self, workspace, run_source, *, runtime_profile=None):
            return pricing_payload

    _, attempt = make_attempt(integration_env["work"], integration_env)
    workspace = Path(attempt["workspace"]["path"])
    (workspace / "runs" / "final.svrun").write_text("{}", encoding="utf-8")
    cli = PricingHypit()
    service.validate_film_attempt(attempt["attempt_id"], "runs/final.svrun", cli=cli)
    priced = service.estimate_film_attempt(attempt["attempt_id"], cli=cli)

    assert priced["cost"]["total"]["status"] == "unknown"
    assert priced["cost"]["estimated_usd"] is None
    assert priced["cost"]["pricing_sha256"] == service._contract_sha256(priced["cost"]["pricing"])
    assert priced["cost"]["plan_sha256"] == priced["plan"]["contract_sha256"]
    assert priced["cost"]["limit_enforced_by_hypit"] is False
    assert priced["cost"]["approved_budget_is_hard_spend_cap"] is False
    with pytest.raises(HypitIntegrationError, match="零预算"):
        service.approve_film_cost(attempt["attempt_id"], 0)


def test_zero_cost_commission_uses_real_contract_and_revalidates_before_build(integration_env):
    work = creation.create_creation("零费用委托测试", creative_mode="clear_memo_video", route="hypit_video",
                                    origin={"type": "chat", "session_hash": "c" * 64})
    creation.mark_chat_proposal_ready(work["id"])
    proposal = '[{"role":"user","content":"隔离测试"}]'
    creation.confirm_chat_proposal(work["id"], "confirm", delivery_proposal=proposal,
                                   proposal_sha256=hashlib.sha256(proposal.encode()).hexdigest())
    _, attempt = make_attempt(work, integration_env)
    attempt_id = attempt["attempt_id"]
    workspace = Path(attempt["workspace"]["path"])
    (workspace / "runs" / "final.svrun").write_text("{}", encoding="utf-8")

    class LocalHypit(FakeHypit):
        def pricing(self, *_args, **_kwargs):
            return {"format": "hypit.cli-pricing@1", "requestCount": 2,
                    "noChargeRequestCount": 2, "groups": []}

    cli = LocalHypit()
    service.validate_film_attempt(attempt_id, "runs/final.svrun", cli=cli)
    priced = service.estimate_film_attempt(attempt_id, cli=cli)
    assert priced["cost"]["estimated_usd"] == 0
    approved = service.approve_film_cost(attempt_id, 0, use_commission=True)
    assert approved["cost"]["approved_budget_usd"] == 0
    assert approved["cost"]["approval_kind"] == "confirmed_commission_no_charge"
    assert approved["cost"]["commission_authorization"]["proposal_sha256"] == hashlib.sha256(proposal.encode()).hexdigest()
    # The zero-cost path retains exactly the same contract/hash gates.
    service._save_attempt(attempt_id, lambda item: {
        **item, "cost": {**item["cost"], "pricing": {**item["cost"]["pricing"], "noChargeRequestCount": 1}},
    })
    with pytest.raises(HypitIntegrationError):
        service.submit_film_build(attempt_id, title="fixture", cli=cli)
    assert cli.build_count == 0
    service.validate_film_attempt(attempt_id, "runs/final.svrun", cli=cli)
    service.estimate_film_attempt(attempt_id, cli=cli)
    service.approve_film_cost(attempt_id, 0, use_commission=True)
    service.submit_film_build(attempt_id, title="fixture", cli=cli)
    service.submit_film_build(attempt_id, title="fixture duplicate", cli=cli)
    assert cli.build_count == 1


def test_pricing_change_after_approval_blocks_build(integration_env):
    attempt, _, _, cli = _approve_attempt(integration_env)

    def mutate_pricing(item):
        item["cost"] = {
            **item["cost"],
            "pricing": {"format": "hypit.cli-pricing@1", "requestCount": 99, "groups": []},
        }
        return item

    service._save_attempt(attempt["attempt_id"], mutate_pricing)
    with pytest.raises(HypitIntegrationError, match="fingerprint 不一致"):
        service.submit_film_build(attempt["attempt_id"], title="价格变化", cli=cli)

    saved = service.get_film_attempt(attempt["attempt_id"])
    assert saved["cost"]["approved"] is False
    assert saved["execution_status"] == "NOT_SUBMITTED"
    assert cli.build_count == 0


def test_plan_change_after_approval_blocks_build(integration_env):
    attempt, _, _, cli = _approve_attempt(integration_env)

    def mutate_plan(item):
        item["plan"] = {**item["plan"], "result": {"format": "hypit.cli-plan@1", "ok": True, "changed": True}}
        return item

    service._save_attempt(attempt["attempt_id"], mutate_plan)
    with pytest.raises(HypitIntegrationError, match="fingerprint 不一致"):
        service.submit_film_build(attempt["attempt_id"], title="Plan 变化", cli=cli)

    saved = service.get_film_attempt(attempt["attempt_id"])
    assert saved["cost"]["approved"] is False
    assert saved["execution_status"] == "NOT_SUBMITTED"
    assert cli.build_count == 0


def test_failed_export_keeps_final_absent_and_removes_staging(integration_env, monkeypatch):
    work = integration_env["work"]
    _, attempt = make_attempt(work, integration_env)
    workspace = Path(attempt["workspace"]["path"])
    (workspace / "runs" / "final.svrun").write_text("{}", encoding="utf-8")
    cli = FakeHypit()
    service.validate_film_attempt(attempt["attempt_id"], "runs/final.svrun", cli=cli)
    service.estimate_film_attempt(attempt["attempt_id"], cli=cli)
    service.approve_film_cost(attempt["attempt_id"], 4.0)
    service.submit_film_build(attempt["attempt_id"], title="测试", cli=cli)
    service.refresh_film_build(attempt["attempt_id"], cli=cli)
    monkeypatch.setattr(service, "_validate_video", lambda *_args, **_kwargs: (_ for _ in ()).throw(
        HypitIntegrationError("模拟视频校验失败")))

    with pytest.raises(HypitIntegrationError, match="模拟视频校验失败"):
        service.export_film_output(attempt["attempt_id"], "final.video", cli=cli)
    target = integration_env["outputs"] / "_creations" / work["id"] / "attempts" / attempt["attempt_id"]
    assert not (target / "final.mp4").exists()
    assert list(target.glob("*.part.mp4")) == []


@pytest.mark.parametrize("crash_at", ["before_link", "after_link", "register"])
def test_export_receipt_recovers_verified_bytes_without_another_get(integration_env, monkeypatch, crash_at):
    _, attempt = make_attempt(integration_env["work"], integration_env)
    attempt_id = attempt["attempt_id"]
    service.update_film_attempt(attempt_id, event="fixture_completed_build",
                                execution_status="BUILD_COMPLETE", build={"build_id": "bld_fixture"})

    class ExportOnly(FakeHypit):
        gets = 0

        def get(self, *args):
            self.gets += 1
            return super().get(*args)

    cli = ExportOnly()
    monkeypatch.setattr(service, "_validate_video", lambda *_args, **_kwargs: {
        "duration_seconds": 30.0, "width": 720, "height": 1280,
        "audio_present": True, "size_bytes": 22,
    })
    original_link, original_save = service.os.link, service._save_attempt
    saves = 0

    def interrupted_link(source, target):
        if crash_at == "before_link":
            raise SystemExit("模拟进程退出")
        original_link(source, target)
        if crash_at == "after_link":
            raise SystemExit("模拟进程退出")

    def interrupted_save(identity, mutate):
        nonlocal saves
        saves += 1
        if crash_at == "register" and saves == 2:
            raise SystemExit("模拟进程退出")
        return original_save(identity, mutate)

    monkeypatch.setattr(service.os, "link", interrupted_link)
    monkeypatch.setattr(service, "_save_attempt", interrupted_save)
    with pytest.raises(SystemExit, match="模拟进程退出"):
        service.export_film_output(attempt_id, "final.video", cli=cli)
    saved = service.get_film_attempt(attempt_id)
    assert not saved.get("outputs")
    receipt = saved["pending_output_export"]
    assert receipt["build_id"] == "bld_fixture"
    monkeypatch.setattr(service.os, "link", original_link)
    monkeypatch.setattr(service, "_save_attempt", original_save)
    if crash_at == "after_link":
        final = integration_env["outputs"] / receipt["output"]["path"]
        trusted = final.read_bytes()
        final.write_bytes(b"unrelated output")
        with pytest.raises(HypitIntegrationError, match="哈希已变化"):
            service.export_film_output(attempt_id, "final.video", cli=cli)
        assert final.read_bytes() == b"unrelated output"
        final.write_bytes(trusted)
        with pytest.raises(HypitIntegrationError, match="凭据"):
            service.export_film_output(attempt_id, "different.output", cli=cli)
    restored = service.export_film_output(attempt_id, "final.video", cli=cli)
    assert cli.gets == 1
    assert "pending_output_export" not in restored
    output = restored["outputs"]["final.video"]
    final = integration_env["outputs"] / output["path"]
    assert output == receipt["output"]
    assert output["sha256"] == "sha256:" + hashlib.sha256(final.read_bytes()).hexdigest()
    assert not list(final.parent.glob("*.part.mp4"))
    assert restored["review"]["human"]["status"] == "pending"


def test_uncertain_build_submission_is_persisted_and_cannot_be_blindly_retried(integration_env):
    work = integration_env["work"]
    _, attempt = make_attempt(work, integration_env)
    workspace = Path(attempt["workspace"]["path"])
    (workspace / "runs" / "final.svrun").write_text("{}", encoding="utf-8")
    service.validate_film_attempt(attempt["attempt_id"], "runs/final.svrun", cli=FailingBuildHypit())
    service.estimate_film_attempt(attempt["attempt_id"], cli=FailingBuildHypit())
    service.approve_film_cost(attempt["attempt_id"], 4.0)

    cli = FailingBuildHypit()
    with pytest.raises(HypitIntegrationError, match="响应丢失"):
        service.submit_film_build(attempt["attempt_id"], title="测试", cli=cli)
    saved = service.get_film_attempt(attempt["attempt_id"])
    assert saved["status"] == "SUBMISSION_UNCERTAIN"
    assert saved["last_error"]["operation"] == "build_submission"
    replay = service.submit_film_build(attempt["attempt_id"], title="重复提交", cli=cli)
    assert replay["idempotent_replay"] is True
    assert replay["build"]["operation"]["operation_id"] == saved["build"]["operation"]["operation_id"]
    assert cli.build_count == 1


def _approve_attempt(integration_env, cli=None):
    work = integration_env["work"]
    _, attempt = make_attempt(work, integration_env)
    workspace = Path(attempt["workspace"]["path"])
    run = workspace / "runs" / "final.svrun"
    run.write_text('{"run":"test"}', encoding="utf-8")
    client = cli or FakeHypit()
    service.validate_film_attempt(attempt["attempt_id"], "runs/final.svrun", cli=client)
    service.estimate_film_attempt(attempt["attempt_id"], cli=client)
    service.approve_film_cost(attempt["attempt_id"], 4.0)
    return attempt, workspace, run, client


def test_two_concurrent_build_requests_only_submit_once(integration_env):
    entered = threading.Event()
    release = threading.Event()

    class BlockingHypit(FakeHypit):
        def build(self, workspace, run_source, *, title, runtime_profile=None):
            self.build_count += 1
            entered.set()
            assert release.wait(5)
            return {"format": "hypit.cli-build@1", "build": {"id": "bld_concurrent_001"}}

    attempt, _, _, cli = _approve_attempt(integration_env, BlockingHypit())
    result = []
    failure = []

    def first_submit():
        try:
            result.append(service.submit_film_build(attempt["attempt_id"], title="并发测试", cli=cli))
        except Exception as exc:  # surfaced to the test thread
            failure.append(exc)

    first = threading.Thread(target=first_submit)
    first.start()
    assert entered.wait(5)
    replay = service.submit_film_build(attempt["attempt_id"], title="重复点击", cli=cli)
    assert replay["idempotent_replay"] is True
    assert replay["execution_status"] == "SUBMITTING"
    release.set()
    first.join(5)
    assert not first.is_alive()
    assert failure == []
    assert cli.build_count == 1
    assert result[0]["build"]["build_id"] == "bld_concurrent_001"


def test_fingerprint_change_invalidates_approval_and_blocks_build(integration_env):
    attempt, _, run, cli = _approve_attempt(integration_env)
    run.write_text('{"run":"changed after approval"}', encoding="utf-8")

    with pytest.raises(HypitIntegrationError, match="fingerprint 不一致"):
        service.submit_film_build(attempt["attempt_id"], title="输入变化", cli=cli)
    saved = service.get_film_attempt(attempt["attempt_id"])
    assert saved["cost"]["approved"] is False
    assert saved["execution_status"] == "NOT_SUBMITTED"
    assert cli.build_count == 0


def test_validate_cannot_reset_submitted_attempt(integration_env):
    attempt, _, _, cli = _approve_attempt(integration_env)
    service.submit_film_build(attempt["attempt_id"], title="已提交", cli=cli)
    with pytest.raises(HypitIntegrationError, match="已提交的 Attempt"):
        service.validate_film_attempt(attempt["attempt_id"], "runs/final.svrun", cli=cli)
    assert service.get_film_attempt(attempt["attempt_id"])["execution_status"] == "SUBMITTED"


def test_uncertain_build_can_reconcile_by_operation_marker(integration_env):
    class AcceptedButTimedOut(FakeHypit):
        candidate = None

        def build(self, workspace, run_source, *, title, runtime_profile=None):
            self.build_count += 1
            self.candidate = {
                "id": "bld_uncertain_001", "title": title, "run": str(run_source),
                "createdAt": datetime.now(timezone.utc).isoformat(), "outcome": "complete",
            }
            raise HypitIntegrationError("client timed out after Hypit accepted the build")

        def builds(self, workspace, *, limit=100):
            return {"format": "hypit.cli-builds@1", "builds": [self.candidate]}

    cli = AcceptedButTimedOut()
    attempt, _, _, _ = _approve_attempt(integration_env, cli)
    with pytest.raises(HypitIntegrationError, match="timed out"):
        service.submit_film_build(attempt["attempt_id"], title="对账测试", cli=cli)
    linked = service.reconcile_film_submission(attempt["attempt_id"], cli=cli)
    assert linked["status"] == "reconciled"
    assert linked["attempt"]["build"]["build_id"] == "bld_uncertain_001"
    assert linked["attempt"]["execution_status"] == "BUILD_COMPLETE"


def test_nonzero_status_with_valid_failed_json_is_a_build_failure(integration_env, monkeypatch):
    attempt, workspace, _, fake = _approve_attempt(integration_env)
    service.submit_film_build(attempt["attempt_id"], title="状态失败测试", cli=fake)
    payload = {"format": "hypit.cli-status@1", "build": {
        "id": "bld_test_001", "failure": "render worker failed to decode frame",
        "work": {"state": "failed", "outcome": "failed"},
    }}

    class Completed:
        returncode = 1
        stdout = json.dumps(payload)
        stderr = "provider reported failure"

    monkeypatch.setattr(hypit_cli.subprocess, "run", lambda *_args, **_kwargs: Completed())
    client = hypit_cli.HypitCLI(executable="hypit")
    refreshed = service.refresh_film_build(attempt["attempt_id"], cli=client)
    assert refreshed["execution_status"] == "BUILD_FAILED"
    assert refreshed["status"] == "BUILD_FAILED"
    assert refreshed["last_error"]["message"] == "render worker failed to decode frame"


def test_creation_lock_preserves_concurrent_attempts_and_history(integration_env):
    work = integration_env["work"]
    handoff_record = create_test_handoff(work)
    barrier = threading.Barrier(8)

    def create_one(index):
        barrier.wait()
        created = service.create_film_attempt(
            work["id"], handoff_record["handoff_id"],
            runtime_profile=integration_env["runtime_profile"],
        )
        with creation.edit_creation(work["id"]) as current:
            current["history"].append({"event": f"concurrent-{index}"})
        return created

    with ThreadPoolExecutor(max_workers=8) as pool:
        attempts = list(pool.map(create_one, range(8)))
    saved = creation.get_creation(work["id"])
    assert len(saved["hypit_attempts"]) == 8
    assert len({item["attempt_number"] for item in saved["hypit_attempts"]}) == 8
    assert sum(item["event"] == "hypit_attempt_created" for item in saved["history"]) == 8
    assert sum(item["event"].startswith("concurrent-") for item in saved["history"]) == 8
    assert len({item["attempt_id"] for item in attempts}) == 8


def test_workspace_handoff_tampering_blocks_build_and_invalidates_approval(integration_env):
    attempt, workspace, _, cli = _approve_attempt(integration_env)
    snapshot = workspace / "handoff" / "truth-packet.json"
    for path in (workspace / "handoff").rglob("*"):
        path.chmod(0o755 if path.is_dir() else 0o644)
    (workspace / "handoff").chmod(0o755)
    snapshot.write_text('{"tampered":true}', encoding="utf-8")

    with pytest.raises(HypitIntegrationError, match="hash 不匹配"):
        service.submit_film_build(attempt["attempt_id"], title="篡改测试", cli=cli)
    saved = service.get_film_attempt(attempt["attempt_id"])
    assert saved["cost"]["approved"] is False
    assert cli.build_count == 0


def test_secret_in_cli_stderr_is_redacted_before_persistence(integration_env, monkeypatch):
    attempt, _, _, _ = _approve_attempt(integration_env)

    class Completed:
        returncode = 1
        stdout = "not json"
        stderr = "MINIMAX_API_KEY=sk-testsecretvalue123456"

    monkeypatch.setattr(hypit_cli.subprocess, "run", lambda *_args, **_kwargs: Completed())
    with pytest.raises(HypitIntegrationError):
        service.submit_film_build(
            attempt["attempt_id"], title="secret error",
            cli=hypit_cli.HypitCLI(executable="hypit"),
        )
    error = service.get_film_attempt(attempt["attempt_id"])["last_error"]["message"]
    assert "sk-testsecretvalue123456" not in error
    assert "[REDACTED]" in error


def test_review_for_output_a_cannot_select_output_b(integration_env, monkeypatch):
    attempt, _, _, cli = _approve_attempt(integration_env)
    service.submit_film_build(attempt["attempt_id"], title="双 output", cli=cli)
    service.refresh_film_build(attempt["attempt_id"], cli=cli)
    monkeypatch.setattr(service, "_validate_video", lambda _path, require_audio: {
        "duration_seconds": 30.0, "width": 720, "height": 1280,
        "audio_present": True, "size_bytes": 9,
    })
    exported_a = service.export_film_output(attempt["attempt_id"], "output-a", cli=cli)
    exported_b = service.export_film_output(attempt["attempt_id"], "output-b", cli=cli)
    output_a = exported_a["outputs"]["output-a"]
    output_b = exported_b["outputs"]["output-b"]
    assert output_a["sha256"] != output_b["sha256"]
    service.record_film_review(attempt["attempt_id"], {
        "outputName": "output-a", "sha256": output_a["sha256"],
        "truth": {"status": "pass", "notes": ["Creator reviewed output-a."]},
        "style": {"status": "pass", "notes": ["Creator reviewed output-a style."]},
        "human": {"status": "approved"},
    })
    with pytest.raises(HypitIntegrationError, match="sha256 绑定"):
        service.select_film_attempt(integration_env["work"]["id"], attempt["attempt_id"], "output-b")


def test_runtime_profile_must_be_existing_absolute_file(integration_env):
    package = create_test_handoff(integration_env["work"])
    with pytest.raises(HypitIntegrationError, match="绝对文件路径"):
        service.create_film_attempt(
            integration_env["work"]["id"], package["handoff_id"], runtime_profile="relative/profile.json")
    with pytest.raises(HypitIntegrationError, match="不存在"):
        service.create_film_attempt(
            integration_env["work"]["id"], package["handoff_id"],
            runtime_profile=str(integration_env["tmp"] / "missing.json"))


def test_sensitive_hypit_api_requires_local_browser_session(integration_env):
    from fastapi.testclient import TestClient
    from web.app import app

    client = TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 54321))
    attempt_id = "fa_" + "0" * 32
    creation_id = integration_env["work"]["id"]
    checks = [
        ("GET", f"/api/creations/{creation_id}/film-attempts", None),
        ("GET", f"/api/film-attempts/{attempt_id}", None),
        ("POST", f"/api/film-attempts/{attempt_id}/runtime/resolve", None),
        ("POST", f"/api/film-attempts/{attempt_id}/validate", {"runPath": "run.sv"}),
        ("POST", f"/api/film-attempts/{attempt_id}/estimate", None),
        ("POST", f"/api/film-attempts/{attempt_id}/approve-cost", {"maxBudgetUsd": 1}),
        ("POST", f"/api/film-attempts/{attempt_id}/build", {"title": "no auth"}),
        ("POST", f"/api/film-attempts/{attempt_id}/refresh", None),
        ("GET", f"/api/film-attempts/{attempt_id}/inspect", None),
        ("POST", f"/api/film-attempts/{attempt_id}/cancel", None),
        ("POST", f"/api/film-attempts/{attempt_id}/reconcile", {}),
        ("POST", f"/api/film-attempts/{attempt_id}/material-generation/minimax", {
            "needId": "need-1", "requestId": "req-1", "confirmPaid": True,
        }),
        ("POST", f"/api/film-attempts/{attempt_id}/materials/recover", {
            "requestId": "req-1", "expectedPlanRevision": "0" * 64,
            "expectedBundleRevision": "0" * 64, "allowLicensedBgm": True,
        }),
        ("GET", f"/api/film-attempts/{attempt_id}/material-rights/candidates", None),
        ("GET", f"/api/film-attempts/{attempt_id}/material-rights/review-candidates", None),
        ("POST", f"/api/film-attempts/{attempt_id}/material-rights/review", {
            "assetId": "asset-1", "assetSha256": "a" * 64, "confirmReview": True,
            "rights": {"status": "KNOWN", "license_name": "fixture",
                       "evidence": [{"kind": "asset_license", "reference": "fixture://terms"}]},
        }),
        ("POST", f"/api/film-attempts/{attempt_id}/material-rights/review-current", {
            "assetId": "asset-1", "assetSha256": "a" * 64, "confirmReview": True,
            "rights": {"status": "KNOWN", "license_name": "fixture",
                       "evidence": [{"kind": "asset_license", "reference": "fixture://terms"}]},
        }),
        ("POST", f"/api/film-attempts/{attempt_id}/author", None),
        ("GET", f"/api/film-attempts/{attempt_id}/material-assets/asset-1/preview?sha256={'0' * 64}", None),
        ("POST", f"/api/film-attempts/{attempt_id}/material-match/review-current", {
            "assetId": "asset-1", "assetSha256": "0" * 64, "needId": "need-1",
            "observedContent": "An observed visual detail", "confirmReview": True,
        }),
        ("POST", f"/api/film-attempts/{attempt_id}/export", {"outputName": "final"}),
        ("POST", f"/api/film-attempts/{attempt_id}/review", {
            "outputName": "final", "sha256": "sha256:" + "0" * 64,
            "truth": {"status": "pass"}, "style": {"status": "pass"},
            "human": {"status": "approved"},
        }),
        ("POST", f"/api/creations/{creation_id}/select-build", {
            "attemptId": attempt_id, "outputName": "final",
        }),
    ]
    for method, path, body in checks:
        response = client.request(method, path, json=body, headers={"Origin": "http://127.0.0.1"})
        assert response.status_code == 401, (method, path, response.status_code, response.text)

    issued = client.post("/api/operator/session", headers={"Origin": "http://127.0.0.1"})
    assert issued.status_code == 200
    assert issued.json()["authenticated"] is True
    cookie = issued.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "path=/api" in cookie
    assert client.get(checks[0][1]).status_code == 200


def test_operator_session_rejects_nonlocal_and_cross_origin_requests():
    from fastapi.testclient import TestClient
    from web.app import app

    nonlocal_client = TestClient(app)
    assert nonlocal_client.post(
        "/api/operator/session", headers={"Origin": "http://testserver"},
    ).status_code == 403

    local_client = TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 54321))
    assert local_client.post(
        "/api/operator/session", headers={"Origin": "http://attacker.example"},
    ).status_code == 403
    issued = local_client.post("/api/operator/session", headers={"Origin": "http://127.0.0.1"})
    assert issued.status_code == 200
    denied = local_client.post(
        "/api/film-attempts/fa_00000000000000000000000000000000/refresh",
        headers={"Origin": "http://attacker.example"},
    )
    assert denied.status_code == 403


def test_formal_web_has_no_old_hypit_material_generation_routes(integration_env):
    from fastapi.testclient import TestClient
    from web.app import app, require_local_operator

    package = create_test_handoff(integration_env["work"])
    attempt = service.create_film_attempt(
        integration_env["work"]["id"], package["handoff_id"],
        runtime_profile=integration_env["runtime_profile"],
    )
    attempt_id = attempt["attempt_id"]
    app.dependency_overrides[require_local_operator] = lambda: None
    try:
        with TestClient(app) as client:
            base = f"/api/film-attempts/{attempt_id}/material-generation"
            assert client.get(base).status_code == 404
            for action in ("prepare", "approve-submit", "reconcile", "collect"):
                assert client.post(f"{base}/{action}", json={}).status_code == 404
    finally:
        app.dependency_overrides.pop(require_local_operator, None)
    assert "material_generation_request" not in service.get_film_attempt(attempt_id)


def test_attribution_export_metadata_is_bound_to_selected_asset(monkeypatch, tmp_path):
    source_page = "https://example.org/1"
    credit_text = "Photo by Ada — https://example.org/1"
    asset = MaterialAsset(
        asset_id="asset-1", media_type=MediaType.IMAGE,
        file=FileInfo(path="materials/assets/asset-1/a.png", sha256="a" * 64, size=1, mime="image/png"),
        source=CandidateSource(kind="fixture", creator="Ada", source_page=source_page),
        rights=RightsInfo(
            status=RightsStatus.ATTRIBUTION_REQUIRED, attribution_required=True,
            attribution_text=credit_text,
            evidence=(RightsEvidence(kind="asset_license", reference="license-evidence-1"),),
        ),
    )
    monkeypatch.setattr(AttemptMaterialStore, "read_bundle", lambda _self: type("Bundle", (), {"assets": (asset,)})())
    monkeypatch.setattr(service, "_workspace", lambda _attempt: tmp_path)
    attempt = {
        "material_planning": {"status": "PLANNING_READY"},
        "workspace": {"root": str(tmp_path)},
        "production_authoring": {
            "selection_validation": {
                "assets": [{"asset_id": "asset-1", "sha256": "a" * 64}],
                "attributions": [{
                    "asset_id": "asset-1", "creator": "Ada",
                    "credit_text": credit_text, "source_page": source_page,
                    "destination": "export_credits", "rights_status": "ATTRIBUTION_REQUIRED",
                    "evidence_references": ["license-evidence-1"],
                }],
            },
        },
    }
    result = service._validated_attribution_metadata(attempt)
    assert result[0]["asset_id"] == "asset-1"
    assert result[0]["credit_text"] == credit_text
    assert result[0]["destination"] == "export_credits"
    attempt["production_authoring"]["selection_validation"]["attributions"][0]["asset_id"] = "other"
    with pytest.raises(HypitIntegrationError, match="selected MaterialAsset Rights facts"):
        service._validated_attribution_metadata(attempt)


def test_hypit_cli_uses_json_and_does_not_inherit_provider_secrets(tmp_path, monkeypatch):
    captured = {}

    class Completed:
        returncode = 0
        stdout = '{"format":"hypit.cli-check@1","ok":true}'
        stderr = ""

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return Completed()

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    source = workspace / "runs" / "x.svrun"
    source.parent.mkdir()
    source.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("MINIMAX_API_KEY", "must-not-cross-boundary")
    monkeypatch.setattr(hypit_cli.subprocess, "run", fake_run)
    client = hypit_cli.HypitCLI(executable="hypit")

    response = client.check(workspace, source)

    assert response["ok"] is True
    assert captured["command"][-1] == "--json"
    assert str(workspace.resolve()) in captured["command"]
    assert "MINIMAX_API_KEY" not in captured["kwargs"]["env"]


def measured_narration_fixture():
    # Valid native vocabulary also used by the opt-in local static check.
    source = '''<?svml using="@hypit/markup@1"?>
<svml>
<import as="time" from="@hypit/timeline-author@1"/>
<import as="media" from="@hypit/media@1"/>
<import as="pipeline" from="@hypit/media-pipeline@1"/>
<import as="audio" from="@hypit/audio-track@1"/>
<import as="space" from="@hypit/spatial@1"/>
<import as="film" from="@hypit/film@1"/>
<import as="copy" from="@hypit/text@1"/>
<import as="typo" from="@hypit/typography-track@1"/>
<import as="fonts" from="@hypit/fonts-open@1"/>
<import as="render" from="@hypit/render-hyperframes@1"/>
<import as="recipes" source="./recipes.svs"/>
<time:Clock id="clock" frame-rate="24"/>
<time:Timeline id="program" clock={clock} end="4s"/>
<space:Canvas id="canvas" width="1080" height="1920"/>
<space:Frame id="easel-caption-frame" within={canvas} left="90px" top="1420px" right="990px" bottom="1700px"/>
<fonts:Face id="caption-font" family="noto-sans-sc" weight="400" style="normal"/>
<typo:Style id="easel-caption-style" recipe={recipes.text.caption} font={caption-font}/>
<media:Audio id="voice-source" src="./voice.wav"/>
<pipeline:Normalize id="voice-media" source={voice-source} video="none" audio="default" span-authority="audio" clock={clock}/>
<audio:Track id="voice-track" timeline={program.timeline}>
  <audio:Item source={voice-media.media} at="12f" for="1s" gain="0.9"/>
</audio:Track>
<media:Audio id="music-source" src="./music.wav"/>
<pipeline:Normalize id="music-media" source={music-source} video="none" audio="default" span-authority="audio" clock={clock}/>
<audio:Track id="music-track" timeline={program.timeline}>
  <audio:Item source={music-media.media} during="program" playback="loop" gain="0.1"/>
</audio:Track>
<typo:Track id="easel-captions" timeline={program.timeline}/>
<film:Film id="movie" canvas={canvas} timeline={program.timeline} appearance={recipes.film.memo}>
  <film:Track source={voice-track.audio}/>
  <film:Track source={music-track.audio}/>
</film:Film>
<render:Video id="output" composition={movie.composition} timeline={program.timeline}/>
</svml>
'''
    timings = {"assets": [{"status": "READY", "asset_id": "voice", "audio_duration_seconds": 3.01,
        "cues": [{"start_seconds": 0.1, "end_seconds": 1.2, "display_text": "第一句<&>。"},
                 {"start_seconds": 1.8, "end_seconds": 3., "display_text": "第二句。"}]}]}
    return source, timings, {"voice": "./voice.wav"}


def test_native_narration_uses_actual_uneven_timing_preserves_director_and_is_idempotent():
    from easel.integrations.hypit.narration import compile_measured_narration
    source, timings, paths = measured_narration_fixture()
    compiled = compile_measured_narration(source, timings, paths)
    assert 'at="12f" for="73f" playback="once" gain="0.9" fade-in="0f" fade-out="0f"' in compiled
    assert '第一句&lt;&amp;&gt;。' in compiled
    assert 'at="14f" for="27f"' in compiled
    assert 'at="55f" for="29f"' in compiled
    assert '<film:Track source={easel-captions.track}/>' in compiled
    for tag in ('space:Frame', 'typo:Style', 'audio:Track id="music-track"'):
        assert source.split('<' + tag)[1].split('</audio:Track>' if tag.startswith('audio:') else '/>')[0] in compiled
    assert compile_measured_narration(compiled, timings, paths) == compiled
    # A changed trusted input regenerates only code-owned windows/text.
    timings['assets'][0]['cues'][0]['end_seconds'] = 1.4
    updated = compile_measured_narration(compiled, timings, paths)
    assert 'at="14f" for="32f"' in updated
    assert updated.count('id="easel-cue-0"') == 1
    assert compile_measured_narration(source, {"assets": []}, paths) == source


@pytest.mark.parametrize(('old', 'new', 'reason'), [
    ('end="4s"', 'end="3s"', '不足'),
    ('at="12f" for="1s"', 'at="12f" for="1s" playback="stretch"', '拉伸'),
    ('at="12f" for="1s"', 'at="12f" for="1s" trim-start="1s"', '截取'),
    ('id="easel-caption-frame"', 'id="other-frame"', '安全区'),
    ('source={voice-track.audio}', 'source={music-track.audio}', '未进入'),
])
def test_native_narration_refuses_silent_audio_or_caption_loss(old, new, reason):
    from easel.integrations.hypit.narration import compile_measured_narration
    source, timings, paths = measured_narration_fixture()
    with pytest.raises(ValueError, match=reason):
        compile_measured_narration(source.replace(old, new), timings, paths)


def test_music_envelope_reaches_native_audio_without_restarting_or_duplicating_music(tmp_path):
    import subprocess
    import shutil
    from easel.integrations.hypit.music import compile_music_ducking, install_music_component, music_envelope
    from easel.integrations.hypit.narration import compile_measured_narration
    source, timings, paths = measured_narration_fixture()
    paths['music'] = './music.wav'
    policy = {'gain_ratio': .25, 'attack_seconds': .12, 'release_seconds': .45}
    original = compile_measured_narration(source, timings, paths)
    compiled = compile_music_ducking(original, timings, paths, {'music'}, policy)
    assert '<film:Track source={music-track.audio}/>' not in compiled
    assert compiled.count('<film:Track source={easel-duck-music-track.audio}/>') == 1
    assert compiled.count('<audio:Item source={music-media.media}') == 1
    assert compile_music_ducking(compiled, timings, paths, {'music'}, policy) == compiled
    with pytest.raises(ValueError, match='唯一'):
        compile_music_ducking(original.replace('</film:Film>', '<film:Track source={music-track.audio}/></film:Film>'),
                             timings, paths, {'music'}, policy)
    # At time zero speech starts already ducked; a short breathing gap never
    # rises, while a later long pause reaches the original authored level.
    cues = [{'start_seconds': 0., 'end_seconds': 1.},
            {'start_seconds': 1.2, 'end_seconds': 2.},
            {'start_seconds': 3.5, 'end_seconds': 4.}]
    points = music_envelope(cues, 0, 5, policy)
    assert points[0] == {'sample': 0, 'gain': .25}
    assert not any(p['gain'] > .25 and 0 < p['sample'] < 2 * 48000 for p in points)
    assert {'sample': 117600, 'gain': 1.} in points
    install_music_component(tmp_path)
    install_music_component(tmp_path)
    runtime = shutil.which('node')
    if runtime is None:
        pytest.skip('Native audio contract needs the project Node runtime')
    component = tmp_path / 'packages/audio-mix/envelope.mjs'
    # Replay the shipped operation on a looping, trimmed clip. Source position,
    # occupancy, gain, fades and audibility must survive byte-for-byte.
    track = {'id': 'music', 'kind': 'audio', 'programSpaceId': 'timeline', 'clips': [{
        'id': 'loop', 'source': {'startSample': 700, 'endSampleExclusive': 10700, 'loop': True, 'phaseSample': 135},
        'target': {'startSample': 0, 'endSampleExclusive': 240000}, 'gain': .15,
        'fadeInSamples': 1000, 'fadeOutSamples': 2000, 'playbackRate': 1,
        'audibility': [{'startSample': 0, 'endSampleExclusive': 240000}],
    }]}
    script = '''import {readFileSync} from 'node:fs';
const {duckTrack} = await import(process.argv[1]);
const {track, points} = JSON.parse(readFileSync(0, 'utf8'));
console.log(JSON.stringify(duckTrack(track, points)));'''
    output = subprocess.run([runtime, '--input-type=module', '-e', script, component.as_uri()],
                            input=json.dumps({'track': track, 'points': points}), text=True,
                            capture_output=True, check=True, timeout=10)
    ducked = json.loads(output.stdout)
    assert ducked['clips'][0].pop('gainEnvelope') == points
    assert ducked['clips'] == track['clips']
    component.write_text('// changed executable')
    with pytest.raises(ValueError, match='版本不一致'):
        install_music_component(tmp_path)


def test_output_quality_detects_masking_truncated_voice_and_decoded_black_frames(tmp_path, monkeypatch):
    import numpy as np
    import shutil
    import subprocess
    import wave
    from easel.integrations.hypit.quality import audio_measurements, measure_output
    rng = np.random.default_rng(47)
    voice = rng.normal(0, .08, 64000).astype(np.float32)
    times = np.arange(len(voice)) / 16000
    music = .01 * np.sin(2 * np.pi * 440 * times)
    cues = [{'start_seconds': .1, 'end_seconds': 1.9}, {'start_seconds': 2.1, 'end_seconds': 3.9}]
    clean = audio_measurements(.8 * voice + music, voice, cues=cues)
    with pytest.raises(HypitIntegrationError, match='无效音频采样'):
        audio_measurements(voice, np.full_like(voice, np.nan), cues=cues)
    assert clean['defects'] == []
    assert clean['voice_windows'][-1]['time_seconds'] > 3.5
    truncated = .8 * voice + music
    truncated[48000:] = music[48000:]
    assert any(d['kind'] == 'voice_missing' and d['time_seconds'] >= 3 for d in audio_measurements(truncated, voice, cues=cues)['defects'])
    masked = audio_measurements(.8 * voice + .15 * np.sin(2 * np.pi * 440 * times), voice, cues=cues)
    assert any(d['kind'] in {'voice_missing', 'voice_masked'} for d in masked['defects'])
    assert audio_measurements(np.zeros(64000, dtype=np.float32))['defects'][0]['kind'] == 'silent_audio'
    assert any(d['kind'] == 'audio_clipping' for d in audio_measurements(np.ones(64000, dtype=np.float32))['defects'])
    if not shutil.which('ffmpeg'):
        pytest.skip('Deterministic media fixture requires ffmpeg')
    source = tmp_path / 'voice.wav'
    with wave.open(str(source), 'wb') as file:
        file.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        file.writeframes((voice * 32767).astype('<i2').tobytes())
    output = tmp_path / 'fixture.mp4'
    subprocess.run(['ffmpeg', '-nostdin', '-loglevel', 'error', '-f', 'lavfi', '-i', 'color=black:s=160x90:r=10:d=2',
        '-f', 'lavfi', '-i', 'color=gray:s=160x90:r=10:d=2', '-i', str(source),
        '-filter_complex', '[0:v][1:v]concat=n=2:v=1:a=0[v]', '-map', '[v]', '-map', '2:a',
        '-c:v', 'libx264', '-c:a', 'aac', '-t', '4', str(output)], check=True, capture_output=True, timeout=20)
    result = measure_output(output, {'duration_seconds': 4, 'audio_present': True}, source, 0, cues)
    assert result['frame_count'] == 8
    assert any(d['kind'] == 'near_black' and d['time_seconds'] == 0 for d in result['defects'])
    assert result['audio']['voice_windows']
    assert not any(d['kind'] == 'voice_missing' for d in result['defects'])
    # The same real output flows through system review, stays separate from
    # human approval, and reuses completed evidence after a caller restart.
    from types import SimpleNamespace
    from easel.integrations.hypit import quality
    from easel.integrations.material_layer import PlanningIntegration, MaterialGateIntegration
    author = tmp_path / 'productions/easel-authoring/authors/main.svml'
    author.parent.mkdir(parents=True)
    author.write_text('<svml/>')
    attempt = {'attempt_id': 'fixture', 'workspace': {'path': str(tmp_path)},
        'execution_status': 'BUILD_COMPLETE', 'build': {'operation': {'execution_fingerprint': {'sha256': 'fixture-input'}}},
        'outputs': {'final': {'path': str(output), 'sha256': service._file_sha256(output),
                            'metadata': {'duration_seconds': 4, 'audio_present': True}}},
        'review': {'human': {'status': 'pending'}}}
    monkeypatch.setattr(service, 'get_film_attempt', lambda identity: attempt)
    monkeypatch.setattr(service, '_execution_fingerprint', lambda a: {'sha256': 'fixture-input'})
    monkeypatch.setattr(service, '_output_path', lambda a, o: output)
    monkeypatch.setattr(service, '_save_attempt', lambda identity, update: update(attempt))
    monkeypatch.setattr(handoff, 'load_frozen_creative_mode', lambda a: ({'id': 'fixture-mode'}, 'mode-sha'))
    planning = {'script': '已冻结的测试表达。', 'treatment': '克制地提出一个问题。', 'scenes': '一段观察。'}
    monkeypatch.setattr(PlanningIntegration, 'load', lambda self, a: planning)
    frozen = tmp_path / 'handoff'
    frozen.mkdir()
    creator = {'schema': 'easel-creator-context@1', 'identity': {'public_description': '记录日常观察的程序员'},
               'audience': '普通职场人', 'voice': {'tone': '平等、克制', 'avoid': ['导师口吻']},
               'privacy_policy': {'do_not_infer_private_facts': True}}
    content = {'topic': '技术变化后的职业判断', 'intended_takeaway': '保留疑问，不下绝对结论'}
    (frozen / 'creator-context.json').write_text(json.dumps(creator, ensure_ascii=False))
    (frozen / 'content-core.json').write_text(json.dumps(content, ensure_ascii=False))
    (frozen / 'truth-packet.json').write_text('{"claims": []}')
    monkeypatch.setattr(MaterialGateIntegration, 'assert_ready', lambda self, a:
                        (SimpleNamespace(needs=()), SimpleNamespace(assets=(), matches=()), None))
    calls = []
    def observe(a, manifest, attachments):
        calls.append(manifest)
        assert attachments and all(item['mimeType'] == 'image/jpeg' for item in attachments)
        assert manifest['binding']['sha256'] == service._file_sha256(output)
        assert manifest['creator_context'] == creator and manifest['content_core'] == content
        assert manifest['treatment'] == planning['treatment'] and manifest['scenes'] == planning['scenes']
        return {'schema': quality.SCHEMA, 'input_sha256': manifest['input_sha256'],
                'frames': [{'index': f['index'], 'observed': True, 'description': 'fixture output frame'} for f in manifest['frames']],
                'checks': {k: {'status': 'pass', 'reason': 'fixture evidence', 'frame_indices': [0]} for k in quality.VISUAL_CHECKS}}
    quality.inspect_output('fixture', executor=observe)
    assert attempt['review']['system']['status'] == 'REPAIR_REQUIRED'
    assert attempt['review']['human']['status'] == 'pending'
    count = len(calls)
    quality.inspect_output('fixture', executor=observe)
    assert len(calls) == count
    original_identity = attempt['review']['system']['input_sha256']
    context_identities = {original_identity}
    # Contract replay across three Content contexts under one Creator/Mode.
    # The media/semantic response is a fixture, not cross-Content quality proof.
    for topic, structure in [('通勤等待的观察', '等待与移动两段对照'), ('学习新工具的反思', '尝试、受挫、追问三个片段')]:
        content.update(topic=topic)
        planning.update(script=topic + '。', treatment=structure, scenes=structure)
        (frozen / 'content-core.json').write_text(json.dumps(content, ensure_ascii=False))
        quality.inspect_output('fixture', executor=observe)
        context_identities.add(attempt['review']['system']['input_sha256'])
    assert len(context_identities) == 3
    # A same-video change to the Creator's public scope cannot reuse an old
    # positive review even when script and Mode remain unchanged.
    creator['voice']['avoid'].append('将尝试冒充已证实经验')
    (frozen / 'creator-context.json').write_text(json.dumps(creator, ensure_ascii=False))
    count = len(calls)
    quality.inspect_output('fixture', executor=observe)
    assert len(calls) > count
    request = quality.repair_request(attempt)
    assert request['allowed_changes'] == ['visual']
    assert request['sha256'] == attempt['outputs']['final']['sha256']
    system = attempt['review']['system']
    system['visual'][0]['checks']['readability'] = {'status': 'fail', 'reason': '字幕与背景对比不足', 'frame_indices': [1]}
    request = quality.repair_request(attempt)
    assert request['allowed_changes'] == ['captions', 'visual']
    assert request['feedback'][-1]['time_seconds'] == system['frames'][1]['time_seconds']
    system['visual'][0]['checks']['creator']['status'] = 'fail'
    assert quality.repair_request(attempt) is None  # Visual repair cannot rewrite Creator identity/voice.
    system['visual'][0]['checks']['creator']['status'] = 'pass'
    system['visual'][0]['checks']['narrative']['status'] = 'fail'
    assert quality.repair_request(attempt) is None  # Not permission to rewrite the script.
    system['visual'][0]['checks']['narrative']['status'] = 'pass'
    system['binding']['sha256'] = 'stale-output'
    assert quality.repair_request(attempt) is None

    # Recheck only incomplete batches of this exact output. Detailed fixture
    # previews force multiple batches; signal measurements still decode MP4.
    import io
    from PIL import Image
    preview = io.BytesIO()
    Image.fromarray(rng.integers(0, 256, (180, 320, 3), dtype=np.uint8)).save(preview, format='PNG')
    decode = quality._decode
    monkeypatch.setattr(quality, '_decode', lambda path, *options:
        preview.getvalue() if '-vcodec' in options else decode(path, *options))
    planning['scenes'] += '局部证据不足回放。'
    review_calls = []
    interrupted = False
    resolve_round = 99
    def uncertain_observe(a, manifest, attachments):
        nonlocal interrupted
        review_calls.append((manifest['frame_offset'], manifest['observation_round'], manifest['input_sha256']))
        if manifest['observation_round'] == 2 and not interrupted:
            interrupted = True
            raise HypitIntegrationError('fixture interruption before report persistence')
        report = observe(a, manifest, attachments)
        if manifest['frame_offset'] == 1 and manifest['observation_round'] < resolve_round:
            report['checks']['readability'] = {'status': 'unknown', 'reason': '字幕边界仍不确定', 'frame_indices': []}
        if manifest['observation_round'] > 1:
            assert manifest['review_focus'] == {'readability': '字幕边界仍不确定'}
        return report
    quality.inspect_output('fixture', executor=uncertain_observe)
    first = attempt['review']['system']
    assert len(first['visual']) > 1 and first['observation_round'] == 1
    assert quality.needs_reobservation(first)
    with pytest.raises(HypitIntegrationError, match='fixture interruption'):
        quality.inspect_output('fixture', executor=uncertain_observe)
    assert attempt['review']['system'] == first  # The incomplete round isn't consumed.
    interrupted_request = review_calls[-1]
    quality.inspect_output('fixture', executor=uncertain_observe)
    assert review_calls[-1] == interrupted_request  # Durable executor sees the same request identity.
    assert attempt['review']['system']['observation_round'] == 2
    quality.inspect_output('fixture', executor=uncertain_observe)
    exhausted = attempt['review']['system']
    assert exhausted['observation_round'] == quality.MAX_OBSERVATION_ROUNDS
    assert not quality.needs_reobservation(exhausted)
    assert quality.repair_request(attempt) is None  # Unknown never becomes permission to rebuild.
    assert [call[0] for call in review_calls[len(first['visual']):]] == [1, 1, 1]
    count = len(review_calls)
    quality.inspect_output('fixture', executor=uncertain_observe)
    assert len(review_calls) == count

    # A fresh input has its own bound review budget; a valid later observation
    # can resolve unknown while retaining the observed technical defect.
    planning['scenes'] += '复查可取得结论的独立场景。'
    resolve_round = 2
    quality.inspect_output('fixture', executor=uncertain_observe)
    quality.inspect_output('fixture', executor=uncertain_observe)
    assert attempt['review']['system']['observation_round'] == 2
    assert not quality.needs_reobservation(attempt['review']['system'])
    assert quality.repair_request(attempt)['allowed_changes'] == ['visual']
    assert attempt['review']['human']['status'] == 'pending'
    output.write_bytes(b'changed output')
    with pytest.raises(HypitIntegrationError, match='字节已变化'):
        quality.inspect_output('fixture', executor=observe)


def test_system_quality_cannot_pass_unseen_or_stale_frames():
    from easel.integrations.hypit.quality import SCHEMA, VISUAL_CHECKS, validate_visual_review
    manifest = {'input_sha256': 'fixture', 'frames': [{'index': 0}]}
    report = {'schema': SCHEMA, 'input_sha256': 'fixture',
              'frames': [{'index': 0, 'observed': True, 'description': 'Actual output frame'}],
              'checks': {k: {'status': 'pass', 'reason': 'Observed output evidence', 'frame_indices': [0]} for k in VISUAL_CHECKS}}
    validate_visual_review(manifest, report)
    report['frames'][0]['observed'] = False
    with pytest.raises(ValueError, match='未看到'):
        validate_visual_review(manifest, report)
    report['frames'][0]['observed'] = True
    report['input_sha256'] = 'other-output'
    with pytest.raises(ValueError, match='当前输出'):
        validate_visual_review(manifest, report)


def test_system_quality_revision_changes_only_defective_layer(tmp_path):
    from easel.integrations.hypit.narration import compile_measured_narration
    from easel.integrations.hypit.revision import assert_quality_revision
    source, timings, paths = measured_narration_fixture()
    original = compile_measured_narration(source, timings, paths)
    base, target = tmp_path / 'base/main.svml', tmp_path / 'target/main.svml'
    recipe = 'film.memo { background: #101820; }\ntext.caption { size: 48; fill: #FFFFFF; features: {"text": "trim-start: 0; }", "weight": 1}; }'
    for path in (base, target):
        path.parent.mkdir()
        path.write_text(original)
        path.with_name('recipes.svs').write_text(recipe)
    target.write_text(original.replace('gain="0.1"', 'gain="0.04"'))
    assert_quality_revision(base, target, {'audio'})
    target.with_name('recipes.svs').write_text(recipe.replace('"weight": 1', '"weight": 2'))
    with pytest.raises(HypitIntegrationError, match='未授权部分'):
        assert_quality_revision(base, target, {'audio'})
    target.with_name('recipes.svs').write_text(recipe)
    with pytest.raises(HypitIntegrationError, match='未授权部分'):
        assert_quality_revision(base, target, {'visual'})
    target.write_text(original.replace('top="1420px"', 'top="1360px"'))
    target.with_name('recipes.svs').write_text(recipe.replace('size: 48', 'size: 56'))
    assert_quality_revision(base, target, {'captions'})
    with pytest.raises(HypitIntegrationError, match='未授权部分'):
        assert_quality_revision(base, target, {'audio'})
    target.with_name('recipes.svs').write_text(recipe)
    for old, new in [('src="./voice.wav"', 'src="./other.wav"'), ('at="12f"', 'at="24f"'),
                     ('第一句', '新事实'), ('<film:Track source={voice-track.audio}/>', '')]:
        target.write_text(original.replace(old, new))
        with pytest.raises(HypitIntegrationError, match='未授权部分'):
            assert_quality_revision(base, target, {'visual', 'captions', 'audio'})
