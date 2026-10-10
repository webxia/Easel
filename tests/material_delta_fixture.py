"""Offline, receipt-backed Material observer for migrated product tests.

Only the model is simulated. Requirement classification, facts/delta,
source receipts, frozen Attempt pin and Need/Asset proof remain production code.
"""
from __future__ import annotations

import json

from easel.integrations import material_results
from easel.integrations.hypit.handoff import load_frozen_creative_mode
from easel.materials.application.visual_contract import (
    compilation_input, classification_units, bind_classifications,
    validate_compilation, requirements_cache_key,
)
from easel.materials.application.visual_observation import GROUP_SCHEMA
from easel.materials.domain import MaterialNeed
from easel.materials.store import AttemptMaterialStore
from tests.test_material_result_delta import _owner


def observed_result(attempt, manifest, attachments, *, outcome="suitable", description="verified actual pixels",
                    style="plain", note="source frame checked", clause_kind="required",
                    invocations=None):
    """Return production delta projection with real immutable capture receipts.

    Models supplied by this fixture can only answer observed facts and indexed
    checks; they cannot forge a formal report or an eligible MaterialMatch.
    """
    if manifest.get("schema") == GROUP_SCHEMA:
        reports = {}
        for item in manifest["observations"]:
            report = observed_result(attempt, item, attachments, outcome=outcome,
                description=description, style=style, note=note, clause_kind=clause_kind)
            reports[item["need"]["need_id"]] = report
        return {"schema": GROUP_SCHEMA, "input_sha256": manifest["input_sha256"], "reports": reports}

    store = AttemptMaterialStore(attempt["workspace"]["path"])
    plan = store.read_plan()
    mode, _ = load_frozen_creative_mode(attempt)
    need = MaterialNeed.model_validate_json(json.dumps(manifest["need"]))
    assert need in plan.needs
    frozen = compilation_input(need, plan.context_refs, mode, plan=plan)
    units = classification_units(frozen)
    classifications = [{
        "id": row["id"], "kind": clause_kind, "preference_source": None
    } for row in units]
    reply = bind_classifications(frozen, {"classifications": classifications, "queries": []})
    contract = validate_compilation(frozen, reply)
    key = requirements_cache_key(frozen)
    saved = store.read_recovery_record(key)
    proposed = {"input": frozen, "response": reply, "contract": contract}
    if saved is None:
        store.write_recovery_record(key, proposed)
    else:
        assert saved == proposed, "frozen requirement classification changed"

    def answer(payload):
        from jsonschema import Draft202012Validator
        observed = outcome != "uncertain"
        status = "unknown" if not observed else "met" if outcome == "suitable" else "not_met"
        checks = {str(key): {"status": status, "basis": "actual fixture visual evidence"}
                  for key in payload["check_ids"]}
        if payload["mode"] == "facts":
            result = {"observed": observed, "description": description, "style": style,
                      "logo": False, "text": False, "preference_notes": note, "checks": checks}
        else:
            result = {"observation_ref": "observation",
                      "facts_dispute": {"kind": "none"},
                      "preference_notes": note, "checks": checks}
        errors = list(Draft202012Validator(payload["schema"]).iter_errors(result))
        assert not errors, [(list(e.path), e.message[:180]) for e in errors]
        return result

    pin, original_invoke, _ = _owner(store, answer)
    def invoke(message, session, media):
        output = original_invoke(message, session, media)
        if invocations is not None:
            invocations.append(session)  # Only actual admitted model boundary calls.
        return output
    report = material_results.observe(attempt, manifest, contract, attachments, pin=pin, invoke=invoke)
    # The real Web producer persists the qualification proof before the
    # Product owner merges the observation into MaterialAsset. Mirror that
    # ordering; never fabricate a qualification marker.
    from easel.materials.application.visual_observation import apply_observation
    asset = store.read_asset(manifest["asset_id"])
    apply_observation(need, asset, manifest, report,
        result_processor=material_results.processor(attempt, store),
        persist_qualification=True)
    store.write_observation_record(manifest["input_sha256"], report)
    return report
