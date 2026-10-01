from __future__ import annotations

import json
import hashlib
from io import BytesIO
from pathlib import Path

import pytest

from easel.materials.application import GenerationApprovalRequired, GenerationRequestConflict
from easel.materials.application import generation as generation_module
from easel.materials.application.generation import MiniMaxVideoMaterialGeneration
from easel.materials.domain import (
    CandidateSource,
    FileInfo,
    MaterialAsset,
    MaterialNeed,
    MaterialPlan,
    MediaType,
    NeedImportance,
    NeedIntent,
    NeedScope,
    NeedScopeType,
    RightsInfo,
    RightsStatus,
    TechnicalInfo,
    TechnicalStatus,
)
from easel.materials.providers.http_support import HttpResponse
from easel.materials.providers.minimax_video import MiniMaxVideoAdapter, MiniMaxVideoError, MiniMaxVideoObservationPending
from easel.materials.store import AttemptMaterialStore


class FakeTransport:
    def __init__(self, *, post_payload=None, get_payloads=()):
        self.post_payload = post_payload or {"task_id": "task-123", "base_resp": {"status_code": 0}}
        self.get_payloads = list(get_payloads)
        self.post_calls = []

    def post(self, url, *, headers, body, timeout):
        self.post_calls.append((url, dict(headers), json.loads(body.decode("utf-8"))))
        return HttpResponse(200, {}, json.dumps(self.post_payload).encode("utf-8"))

    def get(self, url, *, headers, timeout):
        payload = self.get_payloads.pop(0)
        return HttpResponse(200, {}, json.dumps(payload).encode("utf-8"))


def test_minimax_submit_uses_v2_contract_and_never_persists_api_key():
    transport = FakeTransport()
    adapter = MiniMaxVideoAdapter("test-secret", transport=transport)

    task = adapter.submit("清晨的城市街道", duration_seconds=5, ratio="9:16")

    assert task.task_id == "task-123"
    url, headers, body = transport.post_calls[0]
    assert url == "https://api.minimax.cn/v2/video_generation"
    assert headers["Authorization"] == "Bearer test-secret"
    assert body == {
        "model": "MiniMax-H3-Max",
        "content": [{"type": "text", "text": "清晨的城市街道"}],
        "resolution": "480P",
        "duration": 5,
        "ratio": "9:16",
    }


@pytest.mark.parametrize('outcome', ['success', 'rate_limited', 'server_error', 'auth_error', 'cancelled', 'wrong_task'])
def test_minimax_wait_polls_until_success_and_accepts_only_provider_video_urls(outcome):
    transport = FakeTransport(get_payloads=[
        {"task": {"id": "task-123", "model": "MiniMax-H3-Max", "status": "running"}},
        {"task": {"id": "task-123", "model": "MiniMax-H3-Max", "status": "succeeded",
                   "content": {"url": "https://video-product.cdn.minimax.io/output.mp4"}, "duration": 5}},
    ])
    if outcome in {'rate_limited', 'server_error', 'auth_error'}:
        code = {'rate_limited': 429, 'server_error': 500, 'auth_error': 401}[outcome]
        transport.get = lambda *args, **kwargs: HttpResponse(code, {}, b'<html>upstream response</html>')
    elif outcome == 'cancelled':
        transport.get_payloads = [{'task': {'id': 'task-123', 'status': 'cancelled'}}]
    elif outcome == 'wrong_task':
        transport.get_payloads = [{'task': {'id': 'other-task', 'status': 'succeeded'}}]
    adapter = MiniMaxVideoAdapter("test-secret", transport=transport, sleep=lambda _seconds: None)

    if outcome != 'success':
        with pytest.raises(MiniMaxVideoError) as caught:
            adapter.wait('task-123')
        assert isinstance(caught.value, MiniMaxVideoObservationPending) == (outcome in {'rate_limited', 'server_error', 'wrong_task'})
        assert not transport.post_calls  # Observation can never purchase a replacement.
        return
    task = adapter.wait("task-123")

    assert task.status == "succeeded"
    assert task.duration_seconds == 5
    assert len(transport.get_payloads) == 0


def test_minimax_rejects_bad_model_parameters_and_untrusted_media_hosts():
    adapter = MiniMaxVideoAdapter("test-secret", transport=FakeTransport())
    with pytest.raises(MiniMaxVideoError, match="duration"):
        adapter.submit("prompt", duration_seconds=4)
    with pytest.raises(MiniMaxVideoError, match="official HTTPS API host"):
        MiniMaxVideoAdapter("test-secret", base_url="https://attacker.example")
    assert not adapter._official_media_url("https://attacker.example/video.mp4")
    assert not adapter._official_media_url("http://video-product.cdn.minimax.io/video.mp4")
    assert adapter._official_media_url("https://algeng-video-infer.oss-cn-shanghai.aliyuncs.com/video.mp4")


def test_generation_download_resolver_uses_doh_only_for_allowlisted_provider_host(monkeypatch):
    monkeypatch.setattr(
        generation_module.RemoteURLPolicy,
        "_resolve",
        staticmethod(lambda _host, _port: ("198.18.0.26",)),
    )
    requested = []
    def doh(url, timeout):
        requested.append(url)
        return BytesIO(json.dumps({"Status": 0, "Answer": [{"type": 1, "data": "47.102.9.67"}]}).encode())
    monkeypatch.setattr(generation_module, "urlopen", doh)

    addresses = generation_module._resolve_generation_host(
        "algeng-video-infer.oss-cn-shanghai.aliyuncs.com", 443,
    )

    assert addresses == ("47.102.9.67",)
    assert requested[0].startswith("https://dns.google/resolve?")
    with pytest.raises(OSError, match="non-provider"):
        generation_module._resolve_generation_host("attacker.example", 443)


def _plan_and_need() -> tuple[MaterialPlan, MaterialNeed]:
    need = MaterialNeed(
        need_id="need-video",
        scope=NeedScope(type=NeedScopeType.SCENE, ref="scene-1"),
        media_type=MediaType.VIDEO,
        role="b-roll",
        intent=NeedIntent(description="一位创作者在清晨走进工作室"),
        constraints={"allow_generation": True, "orientation": "portrait"},
        importance=NeedImportance.REQUIRED,
    )
    plan = MaterialPlan(
        plan_id="plan-1", creation_id="creation-1", attempt_id="attempt-1",
        context_refs={"script_sha256": "script-hash"}, needs=(need,),
    )
    return plan, need


class FakeAdapter:
    model = "MiniMax-H3-Max"

    def __init__(self):
        self.submit_calls = 0
        self.wait_calls = 0

    def submit(self, _prompt, **_kwargs):
        self.submit_calls += 1
        return type("Task", (), {"task_id": "task-123"})()

    def wait(self, _task_id):
        self.wait_calls += 1
        return type("Task", (), {"task_id": "task-123", "video_url": "https://video-product.cdn.minimax.io/output.mp4"})()


def test_generation_requires_paid_confirmation_and_request_id_is_idempotent(tmp_path: Path, monkeypatch):
    plan, need = _plan_and_need()
    store = AttemptMaterialStore(tmp_path)
    adapter = FakeAdapter()
    service = MiniMaxVideoMaterialGeneration(adapter)

    with pytest.raises(GenerationApprovalRequired):
        service.generate(plan, need, store, request_id="req-1", confirmed_paid=False)
    assert adapter.submit_calls == 0

    asset = MaterialAsset(
        asset_id="asset-1", media_type=MediaType.VIDEO,
        file=FileInfo(path="materials/assets/asset-1/original.mp4", sha256="a" * 64,
                      size=10, mime="video/mp4"),
        source=CandidateSource(kind="generative", provider="minimax", provider_asset_id="task-123"),
        rights=RightsInfo(status=RightsStatus.UNKNOWN),
        technical=TechnicalInfo(status=TechnicalStatus.PENDING),
    )

    class FakeAcquirer:
        def __init__(self, store): self.store = store
        def acquire(self, _candidate):
            body = b"fake video"
            path = self.store.write_asset_bytes(asset.asset_id, "original.mp4", body)
            item = asset.model_copy(update={"file": asset.file.model_copy(update={
                "path": path, "sha256": hashlib.sha256(body).hexdigest(), "size": len(body),
            })})
            self.store.write_asset(item)
            return item

    class FakeInspector:
        def __init__(self, store): self.store = store
        def inspect_and_persist(self, item):
            checked = item.model_copy(update={"technical": TechnicalInfo(status=TechnicalStatus.PASSED, mime="video/mp4")})
            self.store.write_asset(checked)
            return checked

    monkeypatch.setattr(generation_module, "MaterialAcquirer", FakeAcquirer)
    monkeypatch.setattr(generation_module, "TechnicalInspector", FakeInspector)
    service = MiniMaxVideoMaterialGeneration(adapter, acquirer_factory=FakeAcquirer)
    result = service.generate(plan, need, store, request_id="req-1", confirmed_paid=True)
    assert result.asset.rights.status is RightsStatus.UNKNOWN
    assert result.record["status"] == "COMPLETE"
    assert result.record["prompt_sha256"]
    assert "一位创作者" not in json.dumps(result.record, ensure_ascii=False)
    repeated = service.generate(plan, need, store, request_id="req-1", confirmed_paid=True)
    assert repeated.asset.asset_id == result.asset.asset_id
    assert adapter.submit_calls == 1


def test_generation_resumes_material_intake_from_existing_task_without_resubmitting(tmp_path: Path, monkeypatch):
    plan, need = _plan_and_need()
    store = AttemptMaterialStore(tmp_path)
    adapter = FakeAdapter()
    service = MiniMaxVideoMaterialGeneration(adapter)
    asset = MaterialAsset(
        asset_id="asset-resume", media_type=MediaType.VIDEO,
        file=FileInfo(path="materials/assets/asset-resume/original.mp4", sha256="b" * 64,
                      size=10, mime="video/mp4"),
        source=CandidateSource(kind="generative", provider="minimax", provider_asset_id="task-123"),
        rights=RightsInfo(status=RightsStatus.UNKNOWN),
        technical=TechnicalInfo(status=TechnicalStatus.PENDING),
    )

    class FakeAcquirer:
        calls = 0
        def __init__(self, store): self.store = store
        def acquire(self, _candidate):
            type(self).calls += 1
            asset_id = f"{asset.asset_id}-{type(self).calls}"
            body = b"fake video"
            path = self.store.write_asset_bytes(asset_id, "original.mp4", body)
            item = asset.model_copy(update={"asset_id": asset_id, "file": asset.file.model_copy(update={
                "path": path, "sha256": hashlib.sha256(body).hexdigest(), "size": len(body),
            })})
            self.store.write_asset(item)
            return item

    class FailOnceInspector:
        calls = 0
        def __init__(self, store): self.store = store
        def inspect_and_persist(self, item):
            type(self).calls += 1
            if type(self).calls == 1:
                raise ValueError("transient inspection failure")
            checked = item.model_copy(update={"technical": TechnicalInfo(status=TechnicalStatus.PASSED, mime="video/mp4")})
            self.store.write_asset(checked)
            return checked

    monkeypatch.setattr(generation_module, "MaterialAcquirer", FakeAcquirer)
    monkeypatch.setattr(generation_module, "TechnicalInspector", FailOnceInspector)
    service = MiniMaxVideoMaterialGeneration(adapter, acquirer_factory=FakeAcquirer)
    with pytest.raises(ValueError, match="transient"):
        service.generate(plan, need, store, request_id="req-resume", confirmed_paid=True)

    result = service.generate(plan, need, store, request_id="req-resume", confirmed_paid=True)

    assert result.record["status"] == "COMPLETE"
    assert adapter.submit_calls == 1
    assert adapter.wait_calls == 2
