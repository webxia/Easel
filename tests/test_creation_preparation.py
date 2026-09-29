from __future__ import annotations

import asyncio
import json
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "web"))

from easel import chat_capability, creation, creation_preparation as prep  # noqa: E402
from easel.integrations.hypit import handoff, service  # noqa: E402
from easel.integrations.hypit.errors import HypitIntegrationError  # noqa: E402
from easel.materials.domain import (
    MaterialNeed, MaterialPlan, MediaType, NeedImportance, NeedIntent,
    NeedScope, NeedScopeType,
)
import app as web  # noqa: E402


@pytest.fixture
def prep_env(tmp_path, monkeypatch):
    outputs = tmp_path / "outputs"
    monkeypatch.setattr(creation, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(creation, "CREATIONS_DIR", outputs / "_creations")
    monkeypatch.setattr(service, "workspace_root", lambda: tmp_path / ".easel" / "hypit")
    monkeypatch.setenv("EASEL_HYPIT_HOME", str(tmp_path / ".easel" / "hypit"))
    work = creation.create_creation(
        "AI 越来越强以后，程序员真正稀缺的能力是什么？",
        profile="个人经营实践",
        creative_mode="clear_memo_video",
        route="hypit_video",
        origin={"type": "chat", "session_hash": "a" * 64, "initial_turn_hash": "b" * 64},
    )
    creation.mark_chat_proposal_ready(work["id"])
    creation.confirm_chat_proposal(work["id"], "fixture-confirmation")
    claim = prep.claim_chat_preparation(work["id"], "session-a", "turn-a")
    paths = prep.preparation_paths(work["id"], claim["operation_key"])
    write_drafts(work, paths["draft"])
    return {"tmp": tmp_path, "outputs": outputs, "work": work, "claim": claim, "paths": paths}


def write_drafts(work: dict, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    core = {
        "schema": "easel-content-core@1",
        "topic": work["idea"],
        "core_idea": "编码成本下降后，判断问题和承担结果可能更稀缺。",
        "tension": "写代码越来越快，但选择什么问题仍需要人负责。",
        "why_worth_telling": "这触及技术从业者对职业价值的现实疑问。",
        "audience": "正在重新评估职业能力的技术从业者。",
        "intended_takeaway": "把能力变化当作待验证的观察，而不是确定结论。",
        "claim_types": ["opinion", "hypothesis"],
        "boundaries": ["不声称这是所有公司的共同规律。"],
    }
    truth = {
        "schema": "easel-truth-packet@2",
        "claims": [{
            "claim": core["core_idea"],
            "kind": "hypothesis",
            "source": "model_inference",
            "confidence": "medium",
        }],
        "personal_facts": [],
        "first_person_allowed": [],
        "public_allowed": [core["topic"]],
        "forbidden_inventions": ["公司事件", "同事对话", "具体金额"],
        "uncertainty_policy": {
            "plan_is_not_experience": True,
            "learning_is_not_proven_capability": True,
            "unknown_claims": "label_uncertain",
        },
    }
    creator = {
        "schema": "easel-creator-context@1",
        "identity": {"public_description": "有开发经历的普通职场人，持续记录自己的观察。"},
        "audience": "希望看懂公司、职业和个人能力变化的普通职场人。",
        "voice": {"tone": "平等、克制", "avoid": ["导师口吻", "成功学"]},
        "relevant_context": ["有九年 Java 开发经历。"],
        "privacy_policy": {"do_not_infer_private_facts": True},
    }
    production_brief = {
        "schema": "easel-production-brief@1", "language": "zh-CN", "duration_seconds": 15,
        "aspect_ratio": "9:16", "audio_mode": "silent", "beats": [], "text_overlays": [],
        "visual_constraints": [], "material_sources": [], "ai_generation_allowed": False,
        "publication_allowed": False,
    }
    for name, value in (("content-core.json", core), ("truth-packet.json", truth),
                        ("creator-context.json", creator), ("production-brief.json", production_brief)):
        (directory / name).write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _test_planning_executor(attempt, context):
    plan = MaterialPlan(
        plan_id=f"plan-{attempt['attempt_id'][-20:]}",
        creation_id=attempt["creation_id"], attempt_id=attempt["attempt_id"],
        context_refs=context["context_refs"],
        needs=(MaterialNeed(
            need_id="required-scene-video",
            scope=NeedScope(type=NeedScopeType.SCENE, ref="scene-1"),
            media_type=MediaType.VIDEO, role="主镜头",
            intent=NeedIntent(description="与主题相关的纪录片式主镜头"),
            importance=NeedImportance.REQUIRED,
        ),),
    )
    return {"plan": plan, "context_refs": context["context_refs"],
            "treatment": "Treatment", "script": "假设脚本内容。", "scenes": "Scenes"}


def _prepare_creation(creation_id, **kwargs):
    kwargs.setdefault("planning_executor", _test_planning_executor)
    return prep.prepare_creation_for_hypit(creation_id, **kwargs)


def test_director_context_spells_out_strict_truth_and_creator_schemas(prep_env):
    prompt = prep.preparation_agent_context(
        prep_env["work"], {"action": "generate", "operation_key": prep_env["claim"]["operation_key"]})

    assert json.dumps(prep_env["work"]["idea"], ensure_ascii=False) in prompt
    assert "必须原样复制到 Content Core topic" in prompt
    assert "production-brief.json" in prompt
    assert "每条 claim 必须同时提供非空 claim、kind、source、confidence" in prompt
    assert "claims 只记录准备写进视频、且关于现实世界的具体内容主张" in prompt
    assert "claims、personal_facts、first_person_allowed 均使用空数组" in prompt
    assert "不能做到时改为 model_inference 并删除 source_quote" in prompt
    assert '"first_person_allowed":["仅允许的第一人称用途"]' in prompt
    assert '"unknown_claims":"label_uncertain"' in prompt
    assert '"identity":{"public_description":"公开身份概述"}' in prompt
    assert "不要增加 id、statement、notes 等字段" in prompt
    assert "模型归纳或推理绝不能标 user_statement" in prompt
    assert "Profile 不是 claims.source 的合法值" in prompt


def test_chat_preparation_freezes_truth_core_mode_and_attempt_without_build(prep_env, monkeypatch):
    monkeypatch.setattr(service, "_cli", lambda *_args, **_kwargs: pytest.fail("Hypit CLI must not run"))
    result = _prepare_creation(prep_env["work"]["id"], runtime_profile=None)

    work = creation.get_creation(prep_env["work"]["id"])
    attempt = service.get_film_attempt(result["attempt_id"])
    package, manifest, handoff_hash = handoff.resolve_handoff(work["id"], result["handoff_id"])
    task = (Path(attempt["workspace"]["path"]) / "AUTHORING_TASK.md").read_text(encoding="utf-8")

    assert result["status"] == "MATERIAL_NOT_READY"
    assert result["runtime_status"] == "NOT_CONFIGURED"
    assert result["execution_status"] == "BLOCKED"
    assert result["attempt_number"] == 1
    assert work["preparation"]["status"] == "MATERIAL_NOT_READY"
    assert work["status"] == "not_ready"
    assert work["preparation"]["runtime_status"] == "NOT_CONFIGURED"
    assert work["stages"]["content_core"]["status"] == "completed"
    assert attempt["authoring_status"] == "READY_FOR_EXTERNAL_AUTHORING"
    assert attempt["runtime_status"] == "NOT_CONFIGURED"
    assert attempt["execution_status"] == "BLOCKED"
    assert attempt["status"] == "MATERIAL_NOT_READY"
    assert attempt["runtime_profile"] is None
    assert attempt["material_planning"]["status"] == "PLANNING_READY"
    assert attempt["material_gate"]["status"] == "MATERIAL_NOT_READY"
    assert "production_authoring" not in attempt
    assert handoff_hash == work["hypit_handoffs"][0]["hash"]
    assert manifest["content"]["truth_packet"]["hash"]
    assert manifest["production_request"]["production_brief"]["schema"] == "easel-production-brief@1"
    assert manifest["production_request"]["production_brief_sha256"] == work["preparation"]["snapshot_hashes"]["production_brief"]
    assert manifest["creator_context"]["profile_id"] == "个人经营实践"
    assert manifest["creator_context"]["profile_source_sha256"].startswith("sha256:")
    assert "preferred_duration_seconds" not in manifest["production_request"]
    assert (package / "creative-mode" / "director-treatment.md").is_file()
    assert "YOU OWN:" in task and "Treatment and video script" in task
    assert "Do not read an old Easel storyboard" in task
    assert "hypit build" in task and "separate operator-approved action" in task
    assert not (Path(attempt["workspace"]["path"]) / "hypit.runtime.json").exists()


def test_script_truth_operator_api_is_protected_hash_bound_and_resumes(prep_env, monkeypatch):
    from fastapi.testclient import TestClient

    def unclassified_planning(attempt, context):
        result = _test_planning_executor(attempt, context)
        result["script"] = "这家公司成立于 2012 年。"
        return result

    result = _prepare_creation(
        prep_env["work"]["id"], runtime_profile=None, planning_executor=unclassified_planning,
    )
    assert result["status"] == "SCRIPT_TRUTH_REVIEW_REQUIRED"
    attempt = service.get_film_attempt(result["attempt_id"])
    workspace = Path(attempt["workspace"]["path"])
    ledger = json.loads((workspace / "planning" / "script-claims.json").read_text(encoding="utf-8"))
    monkeypatch.setattr(web, "prepare_creation_for_hypit", lambda *_args, **_kwargs: {
        "status": "READY_FOR_EXTERNAL_AUTHORING", "attempt_id": result["attempt_id"],
    })
    authoring_starts = []
    monkeypatch.setattr(web, "_start_film_authoring", lambda attempt_id: authoring_starts.append(attempt_id))
    web.app.dependency_overrides[web.require_local_operator] = lambda: None
    try:
        with TestClient(web.app) as client:
            status = client.get(f"/api/film-attempts/{result['attempt_id']}/script-truth")
            assert status.status_code == 200
            stale = client.post(
                f"/api/film-attempts/{result['attempt_id']}/script-truth/review",
                json={
                    "scriptSha256": "0" * 64,
                    "truthPacketSha256": ledger["truth_packet_sha256"],
                    "confirmAllClaimsReviewed": True,
                },
            )
            accepted = client.post(
                f"/api/film-attempts/{result['attempt_id']}/script-truth/review",
                json={
                    "scriptSha256": ledger["script_sha256"],
                    "truthPacketSha256": ledger["truth_packet_sha256"],
                    "confirmAllClaimsReviewed": True,
                    "reviewer": "codex_delegate",
                },
            )
    finally:
        web.app.dependency_overrides.pop(web.require_local_operator, None)

    assert stale.status_code == 400
    assert accepted.status_code == 200
    assert accepted.json()["script_truth"]["claims"][0]["status"] == "DELEGATE_REVIEWED"
    assert accepted.json()["script_truth"]["claims"][0]["review"]["reviewer"] == "codex_delegate"
    assert accepted.json()["preparation"]["status"] == "READY_FOR_EXTERNAL_AUTHORING"
    assert authoring_starts == [result["attempt_id"]]


def test_configured_local_material_root_runs_product_gate_before_authoring(prep_env, monkeypatch):
    local_root = prep_env["tmp"] / "local-materials"
    local_root.mkdir()
    Image.new("RGB", (720, 1280), (40, 50, 60)).save(local_root / "portrait.jpg")
    monkeypatch.setenv("EASEL_MATERIAL_LOCAL_ROOTS", str(local_root))
    monkeypatch.setattr(service, "_cli", lambda *_args, **_kwargs: pytest.fail("Material preparation must not call Hypit CLI"))

    result = _prepare_creation(prep_env["work"]["id"], runtime_profile=None)
    attempt = service.get_film_attempt(result["attempt_id"])
    assert result["status"] == "MATERIAL_NOT_READY"
    assert attempt["material_planning"]["status"] == "PLANNING_READY"
    assert attempt["material_gate"]["status"] == "MATERIAL_NOT_READY"
    assert "production_authoring" not in attempt


def test_director_planning_executor_consumes_frozen_refs_and_not_fixed_image(prep_env, monkeypatch):
    prepared = _prepare_creation(prep_env["work"]["id"], runtime_profile=None)
    attempt = service.get_film_attempt(prepared["attempt_id"])
    work = creation.get_creation(prepared["creation_id"])
    _, handoff_manifest, _ = handoff.resolve_handoff(work["id"], prepared["handoff_id"])
    hashes = work["preparation"]["snapshot_hashes"]
    refs = {
        "content_core_sha256": hashes["content_core"],
        "truth_packet_sha256": hashes["truth_packet"],
        "creator_context_sha256": hashes["creator_context"],
        "production_brief_sha256": hashes["production_brief"],
        "creative_mode_sha256": handoff_manifest["creative_mode"]["hash"],
    }
    plan = MaterialPlan(
        plan_id=f"plan-{attempt['attempt_id'][-20:]}", creation_id=attempt["creation_id"],
        attempt_id=attempt["attempt_id"], context_refs=refs,
        needs=(MaterialNeed(
            need_id="director-main-video", scope=NeedScope(type=NeedScopeType.SCENE, ref="scene-1"),
            media_type=MediaType.VIDEO, role="主镜头",
            intent=NeedIntent(description="由当前 Content 与 Director 意图决定的视频镜头"),
            importance=NeedImportance.REQUIRED,
        ),),
    )
    prompt_seen = []
    planning_dir = Path(attempt["workspace"]["path"]) / "planning"
    for name in ("MATERIAL_PLAN.json", "TREATMENT.md", "SCRIPT.md", "SCENES.md"):
        (planning_dir / name).unlink(missing_ok=True)

    def fake_agent(prompt, timeout, session_id=None):
        prompt_seen.append(prompt)
        (planning_dir / "MATERIAL_PLAN.json").write_text(plan.model_dump_json(), encoding="utf-8")
        (planning_dir / "TREATMENT.md").write_text("Treatment", encoding="utf-8")
        (planning_dir / "SCRIPT.md").write_text("Script", encoding="utf-8")
        (planning_dir / "SCENES.md").write_text("Scenes", encoding="utf-8")
        return "planned"

    monkeypatch.setattr(web, "run_agent_sync", fake_agent)
    result = web._material_planning_executor(attempt, {
        "content_core": handoff_manifest["content"]["content_core"],
        "truth_packet": handoff_manifest["content"]["truth_packet"],
        "creator_context": handoff_manifest["creator_context"],
        "context_refs": refs,
    })
    assert prompt_seen and "冻结的 Content Core、Truth Packet、Creator Context" in prompt_seen[0]
    assert "Creative Mode / Director" in prompt_seen[0]
    assert "禁止套用固定 IMAGE Need" in prompt_seen[0]
    assert "读取后立即写出" in prompt_seen[0]
    assert "production_request.production_brief" in prompt_seen[0]
    assert "scene、event、global 或 segment" in prompt_seen[0]
    assert "字幕、标题、转场" in prompt_seen[0]
    assert "不能写 orientation" in prompt_seen[0]
    assert "Planning JSON Schema" not in prompt_seen[0]
    assert result["plan"].needs[0].media_type is MediaType.VIDEO
    assert result["plan"].context_refs == refs


def test_failed_planning_and_not_ready_retry_reuse_frozen_attempt(prep_env):
    creation_id = prep_env["work"]["id"]
    original_key = prep_env["claim"]["operation_key"]

    def failed_planning(_attempt, _context):
        raise prep.PreparationError("Planning Agent did not write MaterialPlan")

    with pytest.raises(prep.PreparationError, match="MaterialPlan"):
        prep.prepare_creation_for_hypit(
            creation_id, runtime_profile=None, planning_executor=failed_planning,
        )
    failed = creation.get_creation(creation_id)
    assert failed["preparation"]["status"] == "MATERIAL_FAILED"
    attempt_id = failed["hypit_attempts"][0]["attempt_id"]

    retry = prep.claim_chat_preparation(creation_id, "session-a", "retry-planning")
    assert retry["action"] == "resume"
    assert retry["operation_key"] == original_key
    first = _prepare_creation(creation_id, runtime_profile=None)
    assert first["status"] == "MATERIAL_NOT_READY"
    assert first["attempt_id"] == attempt_id
    saved = creation.get_creation(creation_id)
    assert len(saved["hypit_handoffs"]) == 1
    assert len(saved["hypit_attempts"]) == 1


def test_planning_resume_repairs_invalid_domain_file_once(prep_env, monkeypatch):
    prepared = _prepare_creation(prep_env["work"]["id"], runtime_profile=None)
    attempt = service.get_film_attempt(prepared["attempt_id"])
    root = Path(attempt["workspace"]["path"])
    valid_json = (root / "materials" / "plan.json").read_text(encoding="utf-8")
    invalid = json.loads(valid_json)
    invalid["policy"] = {"must_be_a_string": True}
    planning_file = root / "planning" / "MATERIAL_PLAN.json"
    planning_file.write_text(json.dumps(invalid), encoding="utf-8")
    prompts = []

    def repair_agent(message, _timeout, _session_id):
        prompts.append(message)
        planning_file.write_text(valid_json, encoding="utf-8")
        return "corrected"

    monkeypatch.setattr(web, "run_agent_sync", repair_agent)
    result = web._material_planning_executor(attempt, {
        "context_refs": invalid["context_refs"],
    })
    assert len(prompts) == 1
    assert "policy.must_be_a_string:string_type" in prompts[0]
    assert "当前冻结 context_refs" in prompts[0]
    assert result["plan"].plan_id == invalid["plan_id"]


def test_chat_api_discusses_then_requires_explicit_confirmation(prep_env, monkeypatch):
    from fastapi.testclient import TestClient

    agent_calls = []

    def fake_agent(message, timeout, session_id=None):
        agent_calls.append((message, timeout, session_id))
        if "〔Creation Preparation V1：本作品的唯一准备任务〕" not in message:
            assert "视频创作方案讨论阶段" in message
            assert "提案阶段的最高优先级边界" in message
            assert "不得展开内部思考、工具/命令/会话状态或自我对话" in message
            assert "不得扫描本机素材目录" in message
            assert "只写以下四个 JSON 文件" not in message
            return "方案方向：从一个程序员日常决策的变化切入，不把结论讲成普遍规律。"
        assert "提案阶段的最高优先级边界" not in message
        match = re.search(r"只写以下四个 JSON 文件到目录 (.+)：", message)
        assert match, "Director must receive a bounded preparation output location"
        creation_match = re.search(r"CURRENT_CREATION_ID=(cr_[0-9a-f]{32})", message)
        assert creation_match, "Director must receive the backend-bound Creation ID"
        work = creation.get_creation(creation_match.group(1))
        write_drafts(work, Path(match.group(1)))
        return "已整理这部作品的内容核心和事实边界。"

    monkeypatch.setattr(web, "run_agent_sync", fake_agent)
    authoring_starts = []
    monkeypatch.setattr(web, "_start_film_authoring", lambda attempt_id: authoring_starts.append(attempt_id))
    monkeypatch.setattr(web, "_material_planning_executor", _test_planning_executor)
    monkeypatch.setattr(web, "_hypit_runtime_profile", lambda: None)
    monkeypatch.setattr(service, "workspace_root", lambda: prep_env["tmp"] / ".easel" / "hypit")
    monkeypatch.setattr(service, "_cli", lambda *_args, **_kwargs: pytest.fail("Hypit CLI must not run"))

    payload = web.ChatRequest(
        message="AI 越来越强以后，程序员真正稀缺的能力是什么？",
        persona="个人经营实践",
        creativeMode="clear_memo_video",
        capability="ai-film",
        sessionId="api-session",
        turnId="api-turn",
    )
    with TestClient(web.app) as client:
        response = client.post("/api/chat", json=payload.model_dump())
        assert response.status_code == 200
        first_body = response.json()
        first_work = creation.get_creation(first_body["creationId"])
        assert first_work["chat_workflow"]["proposal_status"] == "READY_FOR_CONFIRMATION"
        assert first_work.get("hypit_handoffs", []) == []
        assert first_work.get("hypit_attempts", []) == []
        assert first_work.get("preparation", {}).get("status") == "CREATED"

        confirmation = web.ChatRequest.model_validate({**payload.model_dump(),
            "message": "按当前方案开始制作",
            "turnId": "api-turn-confirm",
            "creationAction": "confirm_production",
            "proposalContext": [
                {"role": "user", "content": "做一个短视频，纯静音。"},
                {"role": "assistant", "content": "建议 6 个节拍、15 秒。"},
                {"role": "user", "content": "确认 6 个节拍、15 秒、不露脸。"},
            ],
        })
        response = client.post("/api/chat", json=confirmation.model_dump())

    assert response.status_code == 200
    body = response.json()
    assert body["creationId"] == first_body["creationId"]
    assert "Material Gate 未覆盖" in body["response"]
    assert len(agent_calls) == 2
    assert "CURRENT_CREATION_ID=" in agent_calls[1][0]
    work = creation.get_creation(body["creationId"])
    assert work["chat_workflow"]["proposal_status"] == "CONFIRMED"
    assert len(work["chat_workflow"]["proposal_sha256"]) == 64
    assert "CONFIRMED_PROPOSAL_TRANSCRIPT" in agent_calls[1][0]
    assert "不露脸" in agent_calls[1][0]
    _, confirmed_handoff, _ = handoff.resolve_handoff(work["id"], work["hypit_handoffs"][0]["handoff_id"])
    assert confirmed_handoff["production_request"]["confirmed_proposal_sha256"] == work["chat_workflow"]["proposal_sha256"]
    assert confirmed_handoff["production_request"]["production_brief_sha256"] == work["preparation"]["snapshot_hashes"]["production_brief"]
    assert work["preparation"]["status"] == "MATERIAL_NOT_READY"
    assert work["preparation"]["runtime_status"] == "NOT_CONFIGURED"
    assert work["id"] == body["creationId"]
    assert len(work["hypit_handoffs"]) == 1
    assert len(work["hypit_attempts"]) == 1
    assert work["hypit_attempts"][0]["authoring_status"] == "READY_FOR_EXTERNAL_AUTHORING"
    assert work["hypit_attempts"][0]["execution_status"] == "BLOCKED"
    assert work["hypit_attempts"][0]["status"] == "MATERIAL_NOT_READY"
    assert work["hypit_attempts"][0]["material_gate"]["status"] == "MATERIAL_NOT_READY"
    assert authoring_starts == []


def test_chat_proposal_revision_does_not_claim_preparation(prep_env):
    request = web.ChatRequest(
        message="不要太说教，换个角度，让人物感更强一点。",
        persona="个人经营实践",
        creativeMode="clear_memo_video",
        capability="ai-film",
        sessionId="revision-session",
        turnId="revision-turn",
    )
    _, work = web._prepare_chat_request(request)
    saved = creation.get_creation(work["id"])
    assert work["_preparation_action"] == "proposal"
    assert "视频创作方案讨论阶段" in web._prepare_chat_request(request)[0]
    assert saved.get("hypit_handoffs", []) == []
    assert saved.get("hypit_attempts", []) == []
    assert saved.get("preparation", {}).get("status") == "CREATED"


@pytest.mark.parametrize("resume", [False, True])
def test_ready_preparation_starts_authoring_without_an_extra_confirmation(monkeypatch, resume):
    started = []
    monkeypatch.setattr(web, "prepare_creation_for_hypit", lambda *_args, **_kwargs: {
        "status": "READY_FOR_EXTERNAL_AUTHORING", "attempt_id": "fa_test",
    })
    monkeypatch.setattr(web, "_hypit_runtime_profile", lambda: None)
    monkeypatch.setattr(web, "_material_planning_executor", lambda *_args: pytest.fail("Planning must be reused"))
    monkeypatch.setattr(web, "_start_film_authoring", lambda attempt_id: started.append(attempt_id))
    work = {"id": "cr_test"}

    if resume:
        asyncio.run(web._resume_confirmed_preparation(work))
    else:
        asyncio.run(web._finish_ai_film_turn(work, "generate", succeeded=True))

    assert started == ["fa_test"]


@pytest.mark.parametrize("path", ["/api/chat", "/api/chat/stream"])
def test_confirmation_is_rejected_until_a_proposal_turn_finishes(prep_env, path):
    from fastapi.testclient import TestClient

    proposal_turn = web.ChatRequest(
        message="给我一个视频创作方案",
        persona="个人经营实践",
        creativeMode="clear_memo_video",
        capability="ai-film",
        sessionId="not-ready-session",
        turnId="proposal-in-progress",
    )
    web._prepare_chat_request(proposal_turn)
    payload = web.ChatRequest(
        message="按当前方案开始制作",
        persona="个人经营实践",
        creativeMode="clear_memo_video",
        capability="ai-film",
        sessionId="not-ready-session",
        turnId="confirm-too-early",
        creationAction="confirm_production",
    )
    with TestClient(web.app) as client:
        response = client.post(path, json=payload.model_dump())
    assert response.status_code == 409
    work = chat_capability.get_chat_creation("not-ready-session")
    assert work["chat_workflow"]["confirmed_at"] is None
    assert work.get("hypit_handoffs", []) == []
    assert work.get("hypit_attempts", []) == []


def test_unconfirmed_chat_cannot_create_handoff_or_prepare(prep_env, monkeypatch):
    work = creation.create_creation(
        "另一个尚未确认的主题",
        profile="个人经营实践",
        creative_mode="clear_memo_video",
        route="hypit_video",
        origin={"type": "chat", "session_hash": "c" * 64, "initial_turn_hash": "d" * 64},
    )
    with pytest.raises(HypitIntegrationError, match="尚未明确确认"):
        service.create_creation_handoff(
            work["id"], content_core={"topic": "x"}, truth_packet={}, creator_context={})
    with pytest.raises(HypitIntegrationError, match="尚未明确确认"):
        service.create_film_attempt(
            work["id"], "ho_unapproved", preparation_key="e" * 64,
            runtime_status="NOT_CONFIGURED")
    monkeypatch.setattr(web, "get_film_attempt", lambda _attempt_id: {
        "attempt_id": "fa_legacy", "creation_id": work["id"],
    })
    with pytest.raises(HypitIntegrationError, match="尚未明确确认"):
        web._start_film_authoring("fa_legacy")
    with pytest.raises(prep.PreparationError):
        _prepare_creation(work["id"], runtime_profile=None)
    saved = creation.get_creation(work["id"])
    assert saved.get("hypit_handoffs", []) == []
    assert saved.get("hypit_attempts", []) == []


def test_confirmed_attempt_can_dispatch_existing_authoring(prep_env, monkeypatch):
    result = _prepare_creation(prep_env["work"]["id"], runtime_profile=None)
    dispatched = []

    async def fake_authoring(attempt_id):
        dispatched.append(attempt_id)

    monkeypatch.setattr(web, "_run_film_authoring", fake_authoring)

    async def dispatch_once():
        started = web._start_film_authoring(result["attempt_id"])
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        return started

    with pytest.raises(HypitIntegrationError, match="MATERIAL_READY"):
        asyncio.run(dispatch_once())
    assert result["status"] == "MATERIAL_NOT_READY"
    assert dispatched == []


def test_confirmed_interrupted_authoring_can_be_resumed_idempotently(monkeypatch):
    attempt_id = "fa_interrupted"
    attempt = {"attempt_id": attempt_id, "creation_id": "cr_interrupted",
               "authoring_status": "AUTHORING_RUNNING"}
    monkeypatch.setattr(web, "get_film_attempt", lambda _id: attempt)
    monkeypatch.setattr(web, "get_creation", lambda _id: {})
    monkeypatch.setattr(web, "require_chat_proposal_confirmed", lambda _creation: None)
    dispatched = []

    async def fake_authoring(_attempt_id):
        dispatched.append(_attempt_id)

    monkeypatch.setattr(web, "_run_film_authoring", fake_authoring)

    async def resume_twice():
        first = web._start_film_authoring(attempt_id)
        second = web._start_film_authoring(attempt_id)
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        return first, second

    first, second = asyncio.run(resume_twice())

    assert first["authoring_status"] == second["authoring_status"] == "AUTHORING_RUNNING"
    assert dispatched == [attempt_id]


def test_authoring_repairs_machine_detectable_svrun_source_once(prep_env, monkeypatch):
    attempt_id = "fa_0123456789abcdef0123456789abcdef"
    task = {"workspace": str(prep_env["tmp"] / "workspace"), "task_path": "AUTHORING_TASK.md"}
    monkeypatch.setattr(web, "get_film_attempt", lambda _id: {"authoring_status": "AUTHORING_FAILED"})
    monkeypatch.setattr(web, "begin_film_authoring", lambda _id: {
        "authoring_status": "AUTHORING_RUNNING", "authoring_task": task,
    })
    monkeypatch.setattr(web, "_authoring_agent_message", lambda *_args: "initial authoring")
    messages = []
    monkeypatch.setattr(web, "run_attempt_scoped_authoring", lambda **kwargs: messages.append(kwargs["message"]))
    checks = 0

    def complete(_id):
        nonlocal checks
        checks += 1
        if checks == 1:
            raise HypitIntegrationError("SVRun must identify its authored SVML source")
        return {"authoring_status": "AUTHORING_READY"}

    monkeypatch.setattr(web, "complete_film_authoring", complete)
    result = asyncio.run(web._run_film_authoring(attempt_id))

    assert result["authoring_status"] == "AUTHORING_READY"
    assert checks == 2
    assert len(messages) == 2
    assert "runs/main.svrun" in messages[1]
    assert "authors/main.svml" in messages[1]


@pytest.mark.parametrize("prior_error", [None, {"message": "previous Hypit check failed"}])
def test_authoring_automatically_repairs_bounded_hypit_check_feedback(prep_env, monkeypatch, prior_error):
    attempt_id = "fa_0123456789abcdef0123456789abcdef"
    task = {"workspace": str(prep_env["tmp"] / "workspace"), "task_path": "AUTHORING_TASK.md"}
    monkeypatch.setattr(web, "get_film_attempt", lambda _id: {
        "authoring_status": "AUTHORING_FAILED",
        "last_error": prior_error,
    })
    begin_calls = []

    def begin(_id):
        begin_calls.append(_id)
        return {"authoring_status": "AUTHORING_RUNNING", "authoring_task": task}

    monkeypatch.setattr(web, "begin_film_authoring", begin)
    monkeypatch.setattr(web, "_authoring_agent_message", lambda *_args: "initial authoring")
    messages = []
    monkeypatch.setattr(web, "run_attempt_scoped_authoring", lambda **kwargs: messages.append(kwargs["message"]))
    checks = 0

    def complete(_id):
        nonlocal checks
        checks += 1
        if checks == 1:
            raise HypitIntegrationError(
                'Hypit check 失败：time:Clock requires exactly id and frame-rate.'
            )
        return {"authoring_status": "AUTHORING_READY"}

    monkeypatch.setattr(web, "complete_film_authoring", complete)
    result = asyncio.run(web._run_film_authoring(attempt_id))

    assert result["authoring_status"] == "AUTHORING_READY"
    assert checks == 2
    assert len(begin_calls) == 2  # Initial dispatch + one automatic repair round.
    assert len(messages) == 2
    assert "time:Clock requires exactly id and frame-rate" in messages[1]
    assert "不调用 Provider" in messages[1]
    assert "不运行 plan、pricing 或 build" in messages[1]


def test_authoring_agent_receives_installed_hypit_markup_contract():
    message = web._authoring_agent_message(
        "fa_0123456789abcdef0123456789abcdef",
        {"workspace": "/tmp/attempt", "task_path": "/tmp/attempt/AUTHORING_TASK.md"},
    )
    assert "裸 <svml>" in message
    assert "timeline-author@1" in message
    assert "clock={clock}" in message
    assert '不能写成字符串 clock="clock"' in message
    assert "frame-rate" in message
    assert "film:Scene/Overlay/Tracks/Metadata" in message
    assert "material-selection.json 与 runs/main.svrun 都是 Easel JSON" in message
    assert "easel-authoring-svrun@1" in message
    assert "不要手工把 Hypit markup 写进这个 JSON" in message


def test_affirmative_chat_text_is_not_a_structured_confirmation(prep_env):
    first_request = web.ChatRequest(
        message="先给一个创作方向",
        persona="个人经营实践",
        creativeMode="clear_memo_video",
        capability="ai-film",
        sessionId="text-is-not-confirmation",
        turnId="proposal-turn",
    )
    _, work = web._prepare_chat_request(first_request)
    creation.mark_chat_proposal_ready(work["id"])
    revised_request = web.ChatRequest(
        message="可以，就按这个方向吧。",
        persona="个人经营实践",
        creativeMode="clear_memo_video",
        capability="ai-film",
        sessionId="text-is-not-confirmation",
        turnId="affirmative-text",
    )
    _, work = web._prepare_chat_request(revised_request)
    saved = creation.get_creation(work["id"])
    assert work["_preparation_action"] == "proposal"
    assert saved["chat_workflow"]["confirmed_at"] is None
    assert saved.get("hypit_handoffs", []) == []
    assert saved.get("hypit_attempts", []) == []


def test_same_preparation_retry_reuses_snapshot_handoff_and_attempt(prep_env):
    creation_id = prep_env["work"]["id"]
    first = _prepare_creation(creation_id, runtime_profile=None)
    second = _prepare_creation(creation_id, runtime_profile=None)
    work = creation.get_creation(creation_id)

    assert first["handoff_id"] == second["handoff_id"]
    assert first["attempt_id"] == second["attempt_id"]
    assert len(work["hypit_handoffs"]) == 1
    assert len(work["hypit_attempts"]) == 1
    assert work["hypit_attempts"][0]["attempt_number"] == 1


def test_concurrent_preparation_calls_create_one_handoff_and_attempt(prep_env):
    creation_id = prep_env["work"]["id"]
    barrier = threading.Barrier(2)

    def prepare_at_same_time(_index):
        barrier.wait(timeout=10)
        return _prepare_creation(creation_id, runtime_profile=None)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(
            prepare_at_same_time, range(2)))
    work = creation.get_creation(creation_id)

    assert len({item["handoff_id"] for item in results}) == 1
    assert len({item["attempt_id"] for item in results}) == 1
    assert len(work["hypit_handoffs"]) == 1
    assert len(work["hypit_attempts"]) == 1


def test_claimed_turn_retry_does_not_dispatch_another_preparation(prep_env):
    first = prep.claim_chat_preparation(prep_env["work"]["id"], "session-a", "turn-a")
    retry = prep.claim_chat_preparation(prep_env["work"]["id"], "session-a", "turn-a")

    assert first["operation_key"] == retry["operation_key"]
    assert first["action"] == "in_progress"
    assert len(list((prep_env["paths"]["root"].parent).glob("*/draft"))) == 1


def test_core_rejects_storyboard_fields(prep_env):
    core_path = prep_env["paths"]["draft"] / "content-core.json"
    core = json.loads(core_path.read_text(encoding="utf-8"))
    core["storyboard"] = [{"scene": 1}]
    core_path.write_text(json.dumps(core), encoding="utf-8")

    with pytest.raises(prep.PreparationError, match="Content Core schema"):
        _prepare_creation(prep_env["work"]["id"], runtime_profile=None)


def test_truth_packet_requires_real_source_reference(prep_env):
    truth_path = prep_env["paths"]["draft"] / "truth-packet.json"
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    truth["claims"][0]["source"] = "source_evidence"
    truth_path.write_text(json.dumps(truth), encoding="utf-8")

    with pytest.raises(prep.PreparationError, match="真实 source_ref"):
        _prepare_creation(prep_env["work"]["id"], runtime_profile=None)


def test_model_inference_cannot_be_mislabeled_as_user_statement(prep_env):
    truth_path = prep_env["paths"]["draft"] / "truth-packet.json"
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    truth["claims"][0]["source"] = "user_statement"
    truth_path.write_text(json.dumps(truth), encoding="utf-8")

    with pytest.raises(prep.PreparationError, match="逐字出现在用户初始输入"):
        _prepare_creation(prep_env["work"]["id"], runtime_profile=None)


def test_profile_is_not_a_claim_source(prep_env):
    truth_path = prep_env["paths"]["draft"] / "truth-packet.json"
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    truth["claims"][0]["source"] = "profile"
    truth_path.write_text(json.dumps(truth), encoding="utf-8")

    with pytest.raises(prep.PreparationError, match="画像事实只能进入 personal_facts"):
        _prepare_creation(prep_env["work"]["id"], runtime_profile=None)


def test_user_statement_requires_claim_to_equal_verbatim_topic_quote(prep_env):
    truth_path = prep_env["paths"]["draft"] / "truth-packet.json"
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    topic = prep_env["work"]["idea"]
    truth["claims"] = [{
        "claim": "这是模型对主题的归纳",
        "kind": "observation",
        "source": "user_statement",
        "confidence": "high",
        "source_quote": topic,
    }]
    truth_path.write_text(json.dumps(truth), encoding="utf-8")

    with pytest.raises(prep.PreparationError, match="claim 与 source_quote 必须完全相同"):
        _prepare_creation(prep_env["work"]["id"], runtime_profile=None)


def test_snapshot_tampering_is_detected_on_retry(prep_env):
    creation_id = prep_env["work"]["id"]
    _prepare_creation(creation_id, runtime_profile=None)
    core = prep_env["paths"]["snapshot"] / "content-core.json"
    core.chmod(0o644)
    core.write_text("{}", encoding="utf-8")

    with pytest.raises(prep.PreparationError, match="hash 不匹配"):
        _prepare_creation(creation_id, runtime_profile=None)


def test_runtime_profile_validation_uses_installed_hypit_schema(prep_env, tmp_path):
    runtime = tmp_path / "hypit.runtime.json"
    runtime.write_text(json.dumps({
        "format": "hypit.runtime-local@1",
        "dataRoot": ".hypit/runtimes/local",
        "credentials": {},
        "endpoints": {},
        "bindings": {},
    }), encoding="utf-8")
    identity = service._runtime_identity(str(runtime))

    assert identity["format"] == "hypit.runtime-local@1"
    assert identity["path"] == str(runtime.resolve())
    assert identity["sha256"].startswith("sha256:")


def test_invalid_or_wrong_runtime_profile_format_is_rejected(prep_env, tmp_path):
    runtime = tmp_path / "wrong-runtime.json"
    runtime.write_text('{"schema":"hypit.runtime@1"}', encoding="utf-8")

    with pytest.raises(HypitIntegrationError, match="hypit.runtime-local@1"):
        service._runtime_identity(str(runtime))


def test_attempt_runtime_resolution_unblocks_same_attempt(prep_env, tmp_path):
    creation_id = prep_env["work"]["id"]
    first = _prepare_creation(creation_id, runtime_profile=None)
    runtime = tmp_path / "hypit.runtime.json"
    runtime.write_text(json.dumps({
        "format": "hypit.runtime-local@1", "dataRoot": ".hypit/runtimes/local",
        "credentials": {}, "endpoints": {}, "bindings": {},
    }), encoding="utf-8")

    resolved = service.resolve_film_attempt_runtime(first["attempt_id"], str(runtime))
    attempt = service.get_film_attempt(first["attempt_id"])
    work = creation.get_creation(creation_id)

    assert resolved["attempt_id"] == first["attempt_id"]
    assert attempt["authoring_status"] == "READY_FOR_EXTERNAL_AUTHORING"
    assert attempt["runtime_status"] == "CONFIGURED"
    assert attempt["execution_status"] == "NOT_SUBMITTED"
    assert attempt["attempt_number"] == 1
    assert attempt["runtime_profile"]["path"] == str(runtime.resolve())
    assert len(work["hypit_handoffs"]) == 1
    assert len(work["hypit_attempts"]) == 1


def test_runtime_resolution_api_uses_server_profile_and_reuses_attempt(prep_env, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    result = _prepare_creation(prep_env["work"]["id"], runtime_profile=None)
    runtime = tmp_path / "hypit.runtime.json"
    runtime.write_text(json.dumps({
        "format": "hypit.runtime-local@1", "dataRoot": ".hypit/runtimes/local",
        "credentials": {}, "endpoints": {}, "bindings": {},
    }), encoding="utf-8")
    monkeypatch.setattr(web, "_hypit_runtime_profile", lambda: str(runtime))
    web.app.dependency_overrides[web.require_local_operator] = lambda: None
    try:
        with TestClient(web.app) as client:
            response = client.post(f"/api/film-attempts/{result['attempt_id']}/runtime/resolve")
    finally:
        web.app.dependency_overrides.pop(web.require_local_operator, None)

    assert response.status_code == 200
    attempt = service.get_film_attempt(result["attempt_id"])
    assert attempt["runtime_status"] == "CONFIGURED"
    assert attempt["execution_status"] == "NOT_SUBMITTED"
    assert attempt["attempt_number"] == 1
    assert len(creation.get_creation(prep_env["work"]["id"])["hypit_attempts"]) == 1


def test_blocked_runtime_attempt_cannot_validate(prep_env):
    result = _prepare_creation(prep_env["work"]["id"], runtime_profile=None)

    with pytest.raises(HypitIntegrationError, match="MATERIAL_READY"):
        service.validate_film_attempt(result["attempt_id"], "runs/final.svrun")
    with pytest.raises(HypitIntegrationError, match="Execution 被 Runtime 配置阻塞"):
        service.estimate_film_attempt(result["attempt_id"])
    with pytest.raises(HypitIntegrationError, match="Execution 被 Runtime 配置阻塞"):
        service.submit_film_build(result["attempt_id"], title="blocked")
