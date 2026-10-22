from concurrent.futures import ThreadPoolExecutor
import json

import pytest

from easel.production.contracts import canonical_json
from easel.production.errors import Conflict, ProductionError, StaleRevision
from easel.production.operations import OperationService
from easel.production.providers.base import ProviderCapabilities, ProviderResult
from easel.production.store import Store, utc_now
from .fake_provider import FakeProvider


@pytest.fixture
def environment(tmp_path):
    store = Store(tmp_path / "production.sqlite3")
    store.initialize()
    return store, OperationService(store, clock=lambda: 1000), FakeProvider(tmp_path / "provider.sqlite3")


def owned_request(store, *, kind="IMAGE", limit=1, purpose="production", expression_policy=None):
    work = store.create_work({"title": "真实事务测试"})
    revision = None
    if purpose == "production":
        saved = store.save_plan(work["id"], {
            "title": "片子", "summary": "摘要", "script": "完整表达",
            "conversation_basis": {"expression_policy": expression_policy} if expression_policy else None,
            "scenes": [{"id": "s1", "purpose": "说明", "visual": "桌面素材"}],
            "settings": {"duration_seconds": 90, "audio_mode": "silent"},
        }, expected_revision=1)
        revision = saved["revision"]
    run_id, task_id, grant_id = "run_" + work["id"], "task_" + work["id"], "grant_" + work["id"]
    service = {"provider": "fixture", "model": kind.lower(), "mode": "normal"}
    now = utc_now()
    with store.transaction() as conn:
        if revision:
            conn.execute("UPDATE plan_revisions SET confirmed_at=? WHERE work_id=?", (now, work["id"]))
        conn.execute("""INSERT INTO runs(id,work_id,kind,state,plan_revision,graph_version,input_fingerprint,
                        owner_id,owner_epoch,lease_expires_at,created_at,updated_at)
                        VALUES(?,?,?,'running',?,'production-1','input','owner',1,2000,?,?)""",
                     (run_id, work["id"], "production" if revision else "planning", revision, now, now))
        conn.execute("""INSERT INTO tasks(id,work_id,run_id,kind,state,plan_revision,input_fingerprint,owner_epoch,created_at,updated_at)
                        VALUES(?,?,?,'supply','running',?,'input',1,?,?)""",
                     (task_id, work["id"], run_id, revision, now, now))
        conn.execute("UPDATE works SET active_run_id=?,image_limit=?,video_limit=? WHERE id=?", (run_id, limit, limit, work["id"]))
        conn.execute("""INSERT INTO authorization_grants(id,work_id,purpose,plan_revision,services_json,allow_ai,image_limit,video_limit,created_at)
                        VALUES(?,?,?,?,?,?,?,?,?)""",
                     (grant_id, work["id"], purpose, revision, canonical_json([service]), int(purpose == "production"),
                      limit if revision else 0, limit if revision else 0, now))
    return {"operation_id": "op_" + work["id"], "work_id": work["id"], "run_id": run_id, "task_id": task_id,
            "grant_id": grant_id, "kind": kind, **service, "config_version": "fixture-1", "request": {"prompt": "same"}, "owner_epoch": 1}


def test_parallel_requests_cannot_spend_the_same_last_slot(environment):
    store, ops, _ = environment
    spec = owned_request(store)
    def reserve(index):
        try:
            return ops.reserve(**{**spec, "operation_id": f"op_{index}"})["id"]
        except ProductionError as error:
            return error.code
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(reserve, range(16)))
    assert sum(result.startswith("op_") for result in results) == 1
    assert results.count("quota_exhausted") == 15


def test_replayed_operation_returns_receipt_but_explicit_regeneration_is_new(environment):
    store, ops, provider = environment
    spec = owned_request(store, limit=2)
    ops.reserve(**spec)
    first = ops.submit(spec["operation_id"], provider, owner_epoch=1)
    assert first["state"] == "succeeded"
    ops.reserve(**spec)
    ops.submit(spec["operation_id"], provider, owner_epoch=1)
    assert provider.count == 1
    second = {**spec, "operation_id": "explicit_new_generation"}
    ops.reserve(**second)
    ops.submit(second["operation_id"], provider, owner_epoch=1)
    assert provider.count == 2
    assert ops.quota(spec["work_id"])["IMAGE"]["used"] == 2
    with pytest.raises(Conflict):
        ops.reserve(**{**spec, "request": {"prompt": "silently changed"}})


def test_crash_after_remote_receipt_is_observed_not_resent(environment):
    store, ops, provider = environment
    spec = owned_request(store)
    provider.fault = "after"
    ops.reserve(**spec)
    assert ops.submit(spec["operation_id"], provider, owner_epoch=1)["state"] == "unknown"
    assert provider.count == 1
    restarted = OperationService(Store(store.path), clock=lambda: 1000)
    assert restarted.submit(spec["operation_id"], provider, owner_epoch=1)["state"] == "unknown"
    provider.fault = None
    assert restarted.observe(spec["operation_id"], provider)["state"] == "succeeded"
    assert restarted.observe(spec["operation_id"], provider)["state"] == "succeeded"
    assert provider.count == 1
    assert restarted.quota(spec["work_id"])["IMAGE"] == {"limit": 1, "used": 1, "unknown": 0, "reserved": 0, "available": 0}


def test_sending_process_crash_without_exception_handler_is_not_replayed(environment):
    store, ops, provider = environment
    spec = owned_request(store)
    ops.reserve(**spec)
    assert ops.mark_sending(spec["operation_id"], 1)
    provider.submit(spec["request"], request_key=spec["operation_id"])
    restarted = OperationService(store, clock=lambda: 1000)
    assert not restarted.mark_sending(spec["operation_id"], 1)
    assert restarted.observe(spec["operation_id"], provider)["state"] == "succeeded"
    assert provider.count == 1


def test_no_query_and_not_found_never_refund_unknown(environment):
    store, ops, provider = environment
    spec = owned_request(store)
    ops.reserve(**spec)
    provider.fault = "after"
    ops.submit(spec["operation_id"], provider, owner_epoch=1)
    provider.capabilities = ProviderCapabilities()
    assert ops.observe(spec["operation_id"], provider)["state"] == "unknown"
    provider.capabilities = ProviderCapabilities(query_by_request_key=True)
    provider.fault = "not_found"
    assert ops.observe(spec["operation_id"], provider)["state"] == "unknown"
    assert ops.quota(spec["work_id"])["IMAGE"]["unknown"] == 1
    with pytest.raises(Conflict):
        ops.mark_not_submitted(spec["operation_id"])


@pytest.mark.parametrize("fault,used,available", [("before", 0, 1), ("failed", 1, 0)])
def test_only_proven_non_submission_releases_reservation(environment, fault, used, available):
    store, ops, provider = environment
    spec = owned_request(store)
    provider.fault = fault
    ops.reserve(**spec)
    ops.submit(spec["operation_id"], provider, owner_epoch=1)
    quota = ops.quota(spec["work_id"])["IMAGE"]
    assert quota["used"] == used and quota["available"] == available


def test_failed_poll_does_not_erase_known_submission(environment):
    store, ops, provider = environment
    spec = owned_request(store)
    provider.fault = "pending"
    ops.reserve(**spec)
    assert ops.submit(spec["operation_id"], provider, owner_epoch=1)["state"] == "submitted"
    provider.fault = "poll"
    assert ops.observe(spec["operation_id"], provider)["state"] == "submitted"
    assert ops.quota(spec["work_id"])["IMAGE"]["used"] == 1


def test_stale_owner_cannot_send_reserved_operation_after_takeover(environment):
    store, ops, provider = environment
    spec = owned_request(store)
    ops.reserve(**spec)
    with store.transaction() as conn:
        conn.execute("UPDATE runs SET owner_id='next',owner_epoch=2 WHERE id=?", (spec["run_id"],))
        conn.execute("UPDATE tasks SET owner_epoch=2 WHERE id=?", (spec["task_id"],))
    with pytest.raises(StaleRevision):
        ops.mark_sending(spec["operation_id"], 1)
    assert provider.count == 0
    assert ops.submit(spec["operation_id"], provider, owner_epoch=2)["state"] == "succeeded"
    assert not ops.mark_sending(spec["operation_id"], 1)
    assert provider.count == 1


def test_cancellation_blocks_sending_but_accepts_inflight_receipt(environment):
    store, ops, provider = environment
    spec = owned_request(store, limit=2)
    ops.reserve(**spec)
    other = {**spec, "operation_id": "not_sent_yet"}
    ops.reserve(**other)
    assert ops.mark_sending(spec["operation_id"], 1)
    with store.transaction() as conn:
        conn.execute("UPDATE runs SET cancel_requested=1,state='cancelled',owner_epoch=2 WHERE id=?", (spec["run_id"],))
        conn.execute("UPDATE authorization_grants SET revoked_at=? WHERE id=?", (utc_now(), spec["grant_id"]))
    with pytest.raises(ProductionError):
        ops.mark_sending(other["operation_id"], 1)
    receipt = provider.submit(spec["request"], request_key=spec["operation_id"])
    assert ops.receive(spec["operation_id"], receipt)["state"] == "succeeded"
    assert provider.count == 1


def test_revocation_and_unapproved_mode_block_even_with_quota(environment):
    store, ops, _ = environment
    spec = owned_request(store, limit=5)
    with pytest.raises(ProductionError, match="模式"):
        ops.reserve(**{**spec, "mode": "expensive"})
    ops.reserve(**spec)
    with store.transaction() as conn:
        conn.execute("UPDATE authorization_grants SET revoked_at=? WHERE id=?", (utc_now(), spec["grant_id"]))
    with pytest.raises(ProductionError):
        ops.mark_sending(spec["operation_id"], 1)


@pytest.mark.parametrize("kind", ["VOICE", "MODEL"])
def test_model_and_voice_are_audited_but_not_image_video_quota(environment, kind):
    store, ops, provider = environment
    provider.model = kind.lower()
    spec = owned_request(store, kind=kind, limit=0)
    ops.reserve(**spec)
    assert ops.submit(spec["operation_id"], provider, owner_epoch=1)["state"] == "succeeded"
    assert all(item["used"] == item["unknown"] == item["reserved"] == 0 for item in ops.quota(spec["work_id"]).values())


def test_planning_authorization_only_permits_model_calls(environment):
    store, ops, provider = environment
    provider.model = "model"
    spec = owned_request(store, kind="MODEL", purpose="planning")
    ops.reserve(**spec)
    assert ops.submit(spec["operation_id"], provider, owner_epoch=1)["state"] == "succeeded"
    with pytest.raises(ProductionError):
        ops.reserve(**{**spec, "operation_id": "not-authorized", "kind": "IMAGE"})


def test_result_identity_and_terminal_result_cannot_be_replaced(environment):
    store, ops, provider = environment
    spec = owned_request(store)
    ops.reserve(**spec)
    ops.submit(spec["operation_id"], provider, owner_epoch=1)
    with pytest.raises(Conflict):
        ops.receive(spec["operation_id"], ProviderResult("succeeded", "foreign", {"media_ref": "other"}))
    assert ops.get(spec["operation_id"])["receipt"]["result"]["media_ref"] == "test-media"


def test_expired_lease_cannot_create_operation(environment):
    store, ops, provider = environment
    spec = owned_request(store)
    with store.transaction() as conn:
        conn.execute("UPDATE runs SET lease_expires_at=999 WHERE id=?", (spec["run_id"],))
    with pytest.raises(StaleRevision):
        ops.reserve(**spec)
    assert provider.count == 0


def test_actual_adapter_must_match_authorized_service(environment):
    store, ops, provider = environment
    spec = owned_request(store)
    ops.reserve(**spec)
    provider.model = "expensive-unapproved-model"
    with pytest.raises(ProductionError, match="配置"):
        ops.submit(spec["operation_id"], provider, owner_epoch=1)
    assert provider.count == 0
    assert ops.get(spec["operation_id"])["state"] == "reserved"
    with pytest.raises(ProductionError):
        ops.observe(spec["operation_id"], provider)
