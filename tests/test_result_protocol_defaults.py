"""New-only ADR-005 protocol pins and historical Attempt rejection."""
from __future__ import annotations

from copy import deepcopy
import pytest

from easel import creation
from easel.integrations import result_protocols
from easel.integrations.hypit import service
from easel.integrations.output_receipts import OutputReceiptError
from tests.test_material_integration import material_integration_env

EXPECTED_NEW = {
    "truth_reply": "truth-source-ref@1",
    "material_observation": "material-observation-delta@1",
    "script_ledger": "easel-script-claim-ledger@3",
    "quality_review": "quality-review-delta@1",
    "hypit_source": "easel-hypit-source@1",
}


def new_attempt(attempt, suffix, *, protocols=None):
    return service.create_film_attempt(
        attempt["creation_id"], attempt["handoff"]["handoff_id"],
        preparation_key=suffix * 64, runtime_status="NOT_CONFIGURED",
        **({"result_protocols": protocols} if protocols is not None else {}),
    )


def test_new_only_default_is_complete_and_cannot_be_modified_by_caller():
    current = result_protocols.current()
    assert current == {"schema": result_protocols.SCHEMA, "profiles": EXPECTED_NEW}
    assert set(result_protocols.SUPPORTED) == set(EXPECTED_NEW)
    current["profiles"].clear()
    assert result_protocols.current()["profiles"] == EXPECTED_NEW


def test_mutating_the_default_does_not_enable_legacy_profiles(monkeypatch):
    # Even an accidental runtime configuration override cannot revive old Writer.
    monkeypatch.setattr(result_protocols, "DEFAULT_PROFILES", {})
    with pytest.raises(OutputReceiptError, match="read-only"):
        result_protocols.current()
    with pytest.raises(OutputReceiptError, match="read-only"):
        result_protocols.validate({"schema": result_protocols.SCHEMA, "profiles": {}})


def test_real_new_attempt_is_pinned_and_idempotent(material_integration_env):
    attempt = material_integration_env
    created = new_attempt(attempt, "c")
    assert result_protocols.inherited(created)["profiles"] == EXPECTED_NEW
    assert created["execution_status"] == "BLOCKED"
    assert new_attempt(attempt, "c")["attempt_id"] == created["attempt_id"]
    assert service.get_film_attempt(created["attempt_id"])["result_protocols"] == result_protocols.current()


@pytest.mark.parametrize("pins", [
    {}, {"hypit_source": "easel-hypit-source@1"},
    {"hypit_run_promotion": "hypit-run-promotion@1"},
    {**EXPECTED_NEW, "hypit_run_promotion": "hypit-run-promotion@1"},
    {**EXPECTED_NEW, "quality_review": "old-full-review"},
])
def test_old_partial_transitional_protocols_cannot_create_attempt(material_integration_env, pins):
    from pathlib import Path
    attempt = material_integration_env
    root = Path(attempt["workspace"]["root"])
    before = set(root.iterdir())
    with pytest.raises(OutputReceiptError, match="read-only"):
        new_attempt(attempt, "d", protocols={"schema": result_protocols.SCHEMA, "profiles": pins})
    assert set(root.iterdir()) == before


def test_existing_old_attempt_remains_readable_but_all_mutations_stop(material_integration_env):
    attempt = material_integration_env
    attempt_id = attempt["attempt_id"]
    with creation.edit_creation(attempt["creation_id"]) as current:
        for record in current["hypit_attempts"]:
            if record["attempt_id"] == attempt_id:
                record["result_protocols"] = {"schema": result_protocols.SCHEMA, "profiles": {}}
                break
    frozen = deepcopy(service.get_film_attempt(attempt_id))
    assert frozen["result_protocols"]["profiles"] == {}
    with pytest.raises(OutputReceiptError, match="read-only"):
        service.update_film_attempt(attempt_id, event="legacy_blocked", status="AUTHORING_RUNNING")
    class NoCheck:
        def check(self, *_a, **_kw):
            pytest.fail("historical Attempt must never invoke Hypit")
    with pytest.raises(OutputReceiptError, match="read-only"):
        service.complete_film_authoring(attempt_id, cli=NoCheck())
    with pytest.raises(OutputReceiptError, match="read-only"):
        new_attempt(attempt, "b")

    class NoExternal:
        def __getattr__(self, name):
            raise AssertionError("An old Attempt must not resolve any Hypit/Provider method: " + name)

    external = NoExternal()
    forbidden_operations = (
        lambda: service.authoring_agent_task(attempt_id),
        lambda: service.begin_film_authoring(attempt_id),
        lambda: service.validate_film_attempt(
            attempt_id, "productions/easel-authoring/runs/main.svrun", cli=external),
        lambda: service.estimate_film_attempt(attempt_id, cli=external),
        lambda: service.approve_film_cost(attempt_id, 1),
        lambda: service.submit_film_build(attempt_id, title="no legacy Build", cli=external),
        lambda: service.cancel_film_build(attempt_id, cli=external),
        lambda: service.retry_failed_film_build(attempt_id, cli=external),
        lambda: service.resolve_film_attempt_runtime(attempt_id, "/nonexistent-runtime"),
        lambda: service.revise_film_output(
            attempt_id, output_name="final.video", sha256="a"*64, cli=external),
        lambda: service.repair_film_quality(attempt_id, cli=external),
    )
    for operation in forbidden_operations:
        with pytest.raises(OutputReceiptError, match="read-only"):
            operation()
    assert service.get_film_attempt(attempt_id) == frozen
