"""ADR-005 default-on policy is pinned only when creating a new Attempt.

Regression boundary: no historical migration, no duplicate Authoring Writer,
no Provider or Build, and deterministic inherited protocol identity.
"""
from __future__ import annotations

from copy import deepcopy

import pytest

from easel.integrations import result_protocols
from easel.integrations.hypit import service
from easel.integrations.hypit.errors import HypitIntegrationError
from easel.integrations.output_receipts import OutputReceiptError
from tests.test_material_integration import material_integration_env


EXPECTED_NEW = {
    "truth_reply": "truth-source-ref@1",
    "material_observation": "material-observation-delta@1",
    "script_ledger": "easel-script-claim-ledger@3",
    "quality_review": "quality-review-delta@1",
    "hypit_source": "easel-hypit-source@1",
}


def _new(attempt, operation_key, *, profiles=None):
    kwargs = {}
    if profiles is not None:
        kwargs["result_protocols"] = {
            "schema": result_protocols.SCHEMA, "profiles": profiles,
        }
    return service.create_film_attempt(
        attempt["creation_id"], attempt["handoff"]["handoff_id"],
        preparation_key=operation_key * 64, runtime_status="NOT_CONFIGURED",
        **kwargs,
    )


def test_default_is_complete_single_native_writer_and_returns_copies():
    selected = result_protocols.current()
    assert selected == {"schema": result_protocols.SCHEMA, "profiles": EXPECTED_NEW}
    assert "hypit_run_promotion" not in selected["profiles"]
    selected["profiles"].clear()
    assert result_protocols.current()["profiles"] == EXPECTED_NEW
    assert result_protocols.DEFAULT_PROFILES == EXPECTED_NEW


def test_real_new_attempt_uses_default_and_old_attempt_remains_explicit_legacy(
        material_integration_env):
    old = material_integration_env  # Fixture intentionally pinned the old empty profile.
    assert result_protocols.inherited(old)["profiles"] == {}
    original = deepcopy(service.get_film_attempt(old["attempt_id"]))
    created = _new(old, "c")
    assert result_protocols.inherited(created)["profiles"] == EXPECTED_NEW
    assert result_protocols.inherited(service.get_film_attempt(created["attempt_id"]))["profiles"] == EXPECTED_NEW
    assert created["execution_status"] == "BLOCKED"  # No Runtime, media, Provider, or Build.
    assert _new(old, "c")["attempt_id"] == created["attempt_id"]
    assert service.get_film_attempt(old["attempt_id"]) == original
    with pytest.raises(HypitIntegrationError, match="result protocols differ"):
        _new(old, "c", profiles={})


def test_explicit_legacy_and_inherited_retry_pin_not_reinterpreted_by_default(
        material_integration_env):
    old = material_integration_env
    fresh_legacy = _new(old, "d", profiles={})
    assert result_protocols.inherited(fresh_legacy)["profiles"] == {}
    assert result_protocols.inherited({"attempt_id": "historical-without-field"})["profiles"] == {}
    inherited_child = _new(old, "e", profiles=result_protocols.inherited(old)["profiles"])
    assert result_protocols.inherited(inherited_child)["profiles"] == {}
    assert _new(old, "e", profiles={})["attempt_id"] == inherited_child["attempt_id"]
    assert result_protocols.current()["profiles"] == EXPECTED_NEW


def test_native_and_transitional_writers_remain_mutually_exclusive():
    with pytest.raises(OutputReceiptError, match="two competing Hypit"):
        result_protocols.validate({
            "schema": result_protocols.SCHEMA,
            "profiles": {**EXPECTED_NEW, "hypit_run_promotion": "hypit-run-promotion@1"},
        })
