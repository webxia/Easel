from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi import HTTPException

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "web"))

from easel import chat_capability, creation  # noqa: E402
import app as web  # noqa: E402


@pytest.fixture
def chat_creation_store(tmp_path, monkeypatch):
    outputs = tmp_path / "outputs"
    monkeypatch.setattr(creation, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(creation, "CREATIONS_DIR", outputs / "_creations")
    return outputs


def request(**overrides):
    values = {
        "message": "AI 越来越强以后，程序员真正稀缺的能力是什么？",
        "persona": "个人经营实践",
        "creativeMode": "clear_memo_video",
        "capability": "ai-film",
        "sessionId": "chat-session-123",
        "turnId": "turn-001",
    }
    values.update(overrides)
    return web.ChatRequest(**values)


def test_plain_chat_has_no_capability_or_creation(chat_creation_store):
    message, work = web._prepare_chat_request(request(capability=None))

    assert work is None
    assert "〔当前作品上下文" not in message
    assert not list(creation.CREATIONS_DIR.glob("cr_*/creation.json"))


def test_ai_film_creates_a_snapshotted_creation_and_reuses_it(chat_creation_store):
    first_message, first = web._prepare_chat_request(request())
    retry_message, retry = web._prepare_chat_request(request())
    revision_message, revision = web._prepare_chat_request(request(
        message="中间解释味太重，让人物动作承担更多信息。",
        turnId="turn-002",
        persona=None,
        creativeMode=None,
    ))

    assert first["id"] == retry["id"] == revision["id"]
    assert first["idea"] == "AI 越来越强以后，程序员真正稀缺的能力是什么？"
    assert first["profile"] == "个人经营实践"
    assert first["creative_mode"] == "clear_memo_video"
    assert first["route"] == "hypit_video"
    assert "作品 ID" in first_message and "作品 ID" in retry_message and "作品 ID" in revision_message
    assert len(list(creation.CREATIONS_DIR.glob("cr_*/creation.json"))) == 1
    assert revision.get("hypit_attempts", []) == []


def test_unknown_capability_is_rejected_without_creating_any_route(chat_creation_store):
    with pytest.raises(HTTPException) as exc:
        web._prepare_chat_request(request(capability="hypit"))

    assert exc.value.status_code == 400
    assert not list(creation.CREATIONS_DIR.glob("cr_*/creation.json"))


def test_ai_film_requires_topic_and_session(chat_creation_store):
    with pytest.raises(HTTPException, match="主题"):
        web._prepare_chat_request(request(message=" "))
    with pytest.raises(HTTPException, match="会话"):
        web._prepare_chat_request(request(sessionId=None))
    assert not list(creation.CREATIONS_DIR.glob("cr_*/creation.json"))


def test_concurrent_turns_in_one_chat_bind_one_creation(chat_creation_store):
    requests = [request(turnId=f"turn-{index}") for index in range(8)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        works = list(pool.map(lambda item: web._prepare_chat_request(item)[1], requests))

    assert len({work["id"] for work in works}) == 1
    assert len(list(creation.CREATIONS_DIR.glob("cr_*/creation.json"))) == 1


def test_binding_index_does_not_store_raw_chat_or_turn_ids(chat_creation_store):
    web._prepare_chat_request(request())
    index = (creation.CREATIONS_DIR / "_chat_bindings.json").read_text(encoding="utf-8")

    assert "chat-session-123" not in index
    assert "turn-001" not in index
    assert json.loads(index)["schema"] == "easel-chat-bindings@1"


def test_new_chat_session_starts_a_separate_creation(chat_creation_store):
    _, first = web._prepare_chat_request(request())
    _, second = web._prepare_chat_request(request(sessionId="chat-session-456"))

    assert first["id"] != second["id"]
    assert len(list(creation.CREATIONS_DIR.glob("cr_*/creation.json"))) == 2


def test_chat_request_has_capability_but_no_internal_execution_fields():
    payload = request().model_dump()

    assert payload["capability"] == "ai-film"
    assert not {"route", "runtimeProfile", "hypit", "minimax", "buildId"}.intersection(payload)


def test_chat_api_initializes_creation_before_agent_dispatch(chat_creation_store, monkeypatch):
    from fastapi.testclient import TestClient

    seen = {}

    def fake_agent(message, timeout, session_id=None):
        seen.update(message=message, session_id=session_id)
        return "dry-run response"

    monkeypatch.setattr(web, "run_agent_sync", fake_agent)
    with TestClient(web.app) as client:
        response = client.post("/api/chat", json=request().model_dump())

    assert response.status_code == 200
    payload = response.json()
    assert payload["creationId"].startswith("cr_")
    assert seen["session_id"] == "chat-session-123"
    assert payload["creationId"] in seen["message"]


def test_removing_capability_returns_to_plain_chat(chat_creation_store):
    web._prepare_chat_request(request())
    message, work = web._prepare_chat_request(request(
        message="顺便解释下 Python 的生成器", capability=None, turnId="turn-002"))

    assert work is None
    assert "〔当前作品上下文" not in message
    assert len(list(creation.CREATIONS_DIR.glob("cr_*/creation.json"))) == 1


def test_capability_registry_is_closed():
    assert chat_capability.resolve_chat_capability("ai-film")["route"] == "hypit_video"
    with pytest.raises(chat_capability.ChatCapabilityError):
        chat_capability.resolve_chat_capability("arbitrary-route")
