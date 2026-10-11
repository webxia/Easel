"""New Web video ingress is Delivery-owned; old rows remain read-only."""
from __future__ import annotations
import asyncio
from contextlib import nullcontext
import pytest
from fastapi.testclient import TestClient
from web import app as web

@pytest.fixture
def guarded_web(monkeypatch):
    creation_id = "cr_" + "a" * 32
    attempt_id = "fa_" + "b" * 32
    work = {"id": creation_id, "route": "hypit_video",
            "origin": {"type": "chat"},
            "delivery": {"schema": "easel-creation-delivery@1"}}
    attempt = {"attempt_id": attempt_id, "creation_id": creation_id}
    monkeypatch.setattr(web, "get_creation", lambda _: work)
    monkeypatch.setattr(web, "get_film_attempt", lambda _: attempt)
    monkeypatch.setattr(web, "_hypit_runtime_profile", lambda: "/fixture/runtime.json")
    monkeypatch.setattr(web, "execution_lock", lambda _: nullcontext(True))
    web.app.dependency_overrides[web.require_local_operator] = lambda: None
    try:
        yield TestClient(web.app), creation_id, attempt_id, work, attempt
    finally:
        web.app.dependency_overrides.pop(web.require_local_operator, None)

@pytest.mark.parametrize("suffix,body", [
    ("/runtime/resolve", None),
    ("/validate", {"runPath": "productions/easel-authoring/runs/main.svrun"}),
    ("/estimate", None),
    ("/build", {"title": "必须由 Delivery 提交"}),
    ("/refresh", None),
    ("/retry-failed-build", None),
    ("/reconcile", {}),
    ("/export", {"outputName": "final.video"}),
    ("/author", None),
    ("/material-generation/minimax", {"requestId": "fixture1", "needId": "visual-1", "confirmPaid": True}),
    ("/material-generation/minimax-video", {"requestId": "fixture2", "needId": "visual-1", "confirmPaid": True}),
])
def test_managed_video_rejects_direct_stage_dispatch(guarded_web, suffix, body):
    client, _, attempt_id, _, _ = guarded_web
    url = f"/api/film-attempts/{attempt_id}{suffix}"
    reply = client.post(url, json=body) if body is not None else client.post(url)
    assert reply.status_code == 410, (url, reply.status_code, reply.text)
    assert "Delivery" in str(reply.json()["detail"])

@pytest.mark.parametrize("suffix,method,body", [
    ("/handoff", "post", {"contentCore": {}, "truthPacket": {}, "creatorContext": {}}),
    ("/film-attempts", "post", {"handoffId": "ho", "runtimeProfile": "/fixture/runtime.json"}),
    ("/stage/qc", "patch", {"status": "completed", "decision": "ready"}),
])
def test_managed_video_rejects_manual_creation_writer(guarded_web, suffix, method, body):
    client, creation_id, _, _, _ = guarded_web
    reply = getattr(client, method)(f"/api/creations/{creation_id}{suffix}", json=body)
    assert reply.status_code == (409 if suffix.startswith('/stage/') else 410), (suffix, reply.status_code, reply.text)

def test_unconfirmed_chat_video_also_rejects_manual_handoff(guarded_web):
    client, creation_id, _, work, _ = guarded_web
    work["delivery"] = {}  # Before the confirmed commission was enrolled.
    reply = client.post(f"/api/creations/{creation_id}/handoff",
                        json={"contentCore": {}, "truthPacket": {}, "creatorContext": {}})
    assert reply.status_code == 410

def test_historical_attempt_is_readable_but_not_upgraded(guarded_web):
    client, _, attempt_id, work, attempt = guarded_web
    work["delivery"] = {}
    work["origin"] = {"type": "legacy"}
    attempt["result_protocols"] = {"schema": "agent-result-protocols@1", "profiles": {}}
    reply = client.get(f"/api/film-attempts/{attempt_id}")
    assert reply.status_code == 200
    assert reply.json()["result_protocols"]["profiles"] == {}
    assert attempt["result_protocols"]["profiles"] == {}

def test_managed_human_cost_approval_remains_available(guarded_web, monkeypatch):
    client, _, attempt_id, _, _ = guarded_web
    calls = []
    def cost_approval(attempt_id_arg, amount):
        calls.append((attempt_id_arg, amount))
        return {"approved": True}
    monkeypatch.setattr(web, "approve_film_cost", cost_approval)
    reply = client.post(f"/api/film-attempts/{attempt_id}/approve-cost",
                        json={"maxBudgetUsd": 0.0})
    assert reply.status_code == 200, reply.text
    assert calls == [(attempt_id, 0.0)]


def test_historical_truth_review_rejects_before_any_write(guarded_web):
    client, _, attempt_id, work, _ = guarded_web
    work["delivery"] = {}
    work["origin"] = {"type": "legacy"}
    reply = client.post(f"/api/film-attempts/{attempt_id}/script-truth/review",
                        json={"scriptSha256": "a" * 64, "truthPacketSha256": "b" * 64,
                              "confirmAllClaimsReviewed": True})
    assert reply.status_code == 410


def test_historical_chat_completion_does_not_dispatch_old_preparation(monkeypatch):
    async def forbidden(*_args, **_kwargs):
        pytest.fail("old Preparation must never be dispatched")
    monkeypatch.setattr(web, "prepare_creation_for_hypit", forbidden)
    work = {"id": "cr_" + "a" * 32, "delivery": {},
            "chat_workflow": {"video_plan_required": True}}
    reply = asyncio.run(web._finish_ai_film_turn(work, "generate", succeeded=True, response="legacy"))
    assert reply == ""
    reply = asyncio.run(web._resume_confirmed_preparation(work))
    assert "旧版 Preparation 已停用" in reply


def test_current_web_frontend_does_not_dispatch_old_stages():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "web/frontend/src/components/FilmOperatorPage.tsx").read_text()
    for old in ("legacyDelivery", "startFilmAuthoring(", "submitFilmBuild(",
                "resolveFilmRuntime(", "generateMiniMaxMaterial(", "retryFailedFilmBuild(",
                "validateFilmAttempt(", "exportFilmOutput(", "reconcileFilmBuild("):
        assert old not in source, old
    backend = (Path(__file__).resolve().parents[1] / "web/app.py").read_text()
    assert "def _start_film_authoring(" not in backend
    assert "async def _run_film_authoring(" in backend  # The live Delivery-owned executor.
