from __future__ import annotations

# ADR-005 legacy coverage preserved here only for still-current invariants.
# The 20 obsolete string-SVRun/partial-pin functions (25 parametrized cases)
# were mapped one-for-one to actual current Native regression coverage in:
# docs/acceptance/adr005-hypit-native-legacy-test-retirement-2026-10-10.md
# Exact original source is preserved in Git bb01aede:tests/test_hypit_integration.py.
# Never restore deleted producers just to satisfy a historical test mock.

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




def test_system_quality_cannot_pass_unseen_or_stale_frames():
    from easel.integrations.hypit.quality import SCHEMA, VISUAL_CHECKS, validate_visual_review
    manifest = {'input_sha256': 'fixture', 'frames': [{'index': 0}]}
    report = {'schema': SCHEMA, 'input_sha256': 'fixture',
              'frames': [{'index': 0, 'observed': True, 'description': 'Actual output frame'}],
              'checks': {k: {'status': 'pass', 'reason': 'Observed output evidence', 'frame_indices': [0]} for k in VISUAL_CHECKS}}
    validate_visual_review(manifest, report)
    for key in ('creator', 'truth_expression', 'narrative'):
        report['checks'][key]['status'] = 'fail'
        with pytest.raises(ValueError, match='内容表达缺陷'):
            validate_visual_review(manifest, report)
        report['checks'][key]['repair_target'] = 'visual_material'
        validate_visual_review(manifest, report)
        report['checks'][key]['repair_target'] = 'rewrite_script'
        with pytest.raises(ValueError, match='内容表达缺陷'):
            validate_visual_review(manifest, report)
        report['checks'][key]['status'] = 'pass'
    report['frames'][0]['observed'] = False
    with pytest.raises(ValueError, match='未看到'):
        validate_visual_review(manifest, report)
    report['frames'][0]['observed'] = True
    manifest['frames'].append({'index': 1, 'expression_need_ids': ['essential']})
    report['frames'].append({'index': 1, 'observed': True, 'description': '必要关系承担帧'})
    with pytest.raises(ValueError, match='必要表达通过结论'):
        validate_visual_review(manifest, report)
    report['checks']['narrative']['frame_indices'].append(1)
    validate_visual_review(manifest, report)
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

    # A real visual mismatch can use an admitted same-Need alternative. This
    # permission cannot change narration, schedule or arbitrary other sources.
    visual = original.replace('<film:Film',
        '<import as="media-track" from="@hypit/media-track@1"/>'
        '<media:Image id="picture" src="./old.png"/>'
        '<space:Extent id="picture-size" width="64" height="96"/>'
        '<media-track:Track id="pictures" canvas={canvas} timeline={program.timeline}>'
        '<media-track:Item image={picture} extent={picture-size} at="0s" for="4s"/>'
        '</media-track:Track><film:Film')
    base.write_text(visual)
    revised = visual.replace('./old.png', './new.png').replace('width="64" height="96"', 'width="128" height="192"')
    target.write_text(revised)
    alternatives = {'./old.png': {'./new.png': {'media_type': 'image', 'width': 128, 'height': 192}}}
    with pytest.raises(HypitIntegrationError, match='未授权部分'):
        assert_quality_revision(base, target, {'visual'})
    assert_quality_revision(base, target, {'visual', 'visual_material'}, replacements=alternatives)
    for invalid in (revised.replace('./new.png', './unknown.png'), revised.replace('width="128"', 'width="129"'),
                    revised.replace('./voice.wav', './another.wav'), revised.replace('for="4s"', 'for="3s"')):
        target.write_text(invalid)
        with pytest.raises(HypitIntegrationError, match='未授权部分'):
            assert_quality_revision(base, target, {'visual', 'visual_material'}, replacements=alternatives)
    # Native media-track can carry source audio without an audio-track node.
    # A visual permission must not silently replace that sound with another clip.
    with_sound = visual.replace('<media:Image id="picture" src="./old.png"/>',
        '<media:Video id="footage" src="./old.mp4"/>'
        '<pipeline:Normalize id="picture" source={footage} clock={clock}/>')
    with_sound = with_sound.replace('image={picture} extent={picture-size}',
                                   'media={picture.media} source-audio="content"')
    base.write_text(with_sound)
    target.write_text(with_sound.replace('./old.mp4', './new.mp4'))
    with pytest.raises(HypitIntegrationError, match='未授权部分'):
        assert_quality_revision(base, target, {'visual', 'visual_material'}, replacements={
            './old.mp4': {'./new.mp4': {'media_type': 'video', 'width': 64, 'height': 96}}})


def test_initial_expression_coverage_requires_visible_graph_and_actual_windows(tmp_path):
    from easel.integrations.hypit.revision import expression_uses
    source, timings, paths = measured_narration_fixture()
    source = source.replace('<typo:Track id="easel-captions"', '''<copy:Value id="one-item">今天这一件</copy:Value>
<typo:Track id="choice-graphic" timeline={program.timeline}>
<typo:Area id="selected-item" content={one-item} placement={easel-caption-frame} style={easel-caption-style} at="1s" for="2s"/>
</typo:Track>
<typo:Track id="easel-captions"''').replace('<film:Track source={voice-track.audio}/>',
        '<film:Track source={choice-graphic.track}/><film:Track source={voice-track.audio}/>')
    row = {'need_id': 'choice', 'element_ids': ['selected-item'], 'at_seconds': 1, 'end_seconds': 3, 'responsibility': 'graphic'}
    path = tmp_path / 'main.svml'
    def write(text, value=row):
        path.write_text(text + '\n<!-- Easel expression: ' + json.dumps(value) + ' -->')
    write(source)
    assert expression_uses(path, required_need_ids={'choice'}) == [row]
    from easel.integrations.hypit.revision import assert_quality_revision
    revised = tmp_path / 'revised.svml'
    revised.write_text(path.read_text().replace('\"at_seconds\": 1', '\"at_seconds\": 1.5'))
    with pytest.raises(HypitIntegrationError, match='未授权部分'):
        assert_quality_revision(path, revised, {'visual', 'captions'})
    write(source.replace('<film:Track source={choice-graphic.track}/>', ''))
    with pytest.raises(HypitIntegrationError, match='未进入 Film'):
        expression_uses(path, required_need_ids={'choice'})
    write(source, {**row, 'end_seconds': 4})
    with pytest.raises(HypitIntegrationError, match='播放窗口'):
        expression_uses(path, required_need_ids={'choice'})
    write(source, {**row, 'element_ids': ['voice-track']})
    with pytest.raises(HypitIntegrationError):
        expression_uses(path, required_need_ids={'choice'})
    write(source)
    with pytest.raises(HypitIntegrationError, match='完整覆盖'):
        expression_uses(path, required_need_ids={'choice', 'other'})
