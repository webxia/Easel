"""D1 offline carrier experiment, not registered in the production Planning Owner."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from jsonschema import ValidationError, Draft202012Validator

from easel import creative_mode
from easel.integrations.hypit import handoff
from easel.integrations.planning_creative_authority import (
    AtomicSharedRepairCarrier, VisualClaimCarrier, compile_envelope, digest,
)
from easel.integrations.planning_staged_proposal import StagedProposal
from easel.integrations.planning_result_contract import semantic_tool_schema, maximum_compact_bytes
from easel.integrations.semantic_planning import source_catalog
from tests.test_planning_creative_authority_d0 import (
    CONTENTS, _confirmed_synthetic_attempt,
)
from tests.test_material_integration import material_integration_env


def _claim(kind="director_local_choice", strength="required", scope="scene-1",
           reason="为本次内容的镜头表达提供可复核的具体导演理由"):
    return {"claimed_kind": kind, "creative_goal_ref": scope,
            "reason": reason, "claimed_strength": strength}


def _setup(material_integration_env, monkeypatch, *, index=0):
    mode_dir = Path(__file__).resolve().parents[1] / "creative_modes"
    monkeypatch.setattr(creative_mode, "CREATIVE_MODES_DIR", mode_dir)
    monkeypatch.setattr(handoff, "CREATIVE_MODES_DIR", mode_dir, raising=False)
    mode = json.loads((mode_dir / "clear_memo_video/mode.json").read_text())
    attempt, ctx, canonical, confirmed, _ = _confirmed_synthetic_attempt(*CONTENTS[index])
    env = compile_envelope(attempt, canonical, ctx, mode, allow_missing_canonical=True)
    catalog = source_catalog(canonical, {"creator_context": ctx["creator_context"],
                                         "proposal": confirmed})
    staged = StagedProposal(semantic_tool_schema(catalog, compiled=True))
    # This is A's synthetic *candidate* with real frozen scene scope. B must
    # still decide entailment; this test verifies wire/canonical identity only.
    draft = {"needs": [{"scope": "scene-1", "role": "首个视觉镜头",
                        "modality": "image", "necessity": "required",
                        "conditions": [
                            {"text": canonical["SCENES.md"],
                             "strength": "required", "responsibility": "material",
                             "meaning": "observable"},
                            {"text": "选择克制的构图与适度停顿",
                             "strength": "preference", "responsibility": "postproduction",
                             "meaning": "observable"},
                        ]}], "unresolved": []}
    selection, details, _ = staged.encode(draft)
    carrier = VisualClaimCarrier(staged, selection, env)
    mapping = {"needs/0/conditions/0": _claim(reason="给本片确认的镜头呈现真实源画面与素材必要条件"),
               "needs/0/conditions/1": _claim("creative_preference", "preference",
                                              reason="让节奏服从本片观察主题而非固定成片模板")}
    wire = carrier.encode(details, mapping)
    canonical_a, plain, claims = carrier.decode(wire, carrier.identity)
    assert canonical_a == staged.assemble(selection, details, staged.details_contract(selection)["identity"])
    return env, carrier, wire, canonical_a, plain, claims


def test_d1_envelope_bound_to_confirmed_handoff_and_cross_content(material_integration_env, monkeypatch):
    envelope, carrier, raw, canonical, plain, claims = _setup(material_integration_env, monkeypatch)
    assert envelope["policy"] == "planning-creative-delegation-prototype@1"
    assert "assert_rights_or_asset_available" in envelope["denied"]
    assert "shot_execution" in envelope["allowed"]
    assert all(x["scope_ref"] == envelope["scope_ref"] for x in claims.values())
    assert len(claims) == 2 and set(claims) == {"needs/0/conditions/0", "needs/0/conditions/1"}
    # A-side claim never becomes a B approval or a stored Rights permit.
    assert not any("ACCEPT" in str(record) for record in claims.values())
    assert "claim" not in str(canonical)
    # Same Mode document set but different Proposal/Creation/Truth -> unique scope.
    second = _setup(material_integration_env, monkeypatch, index=1)[0]
    assert envelope["context"]["creative_mode_sha256"] == second["context"]["creative_mode_sha256"]
    assert envelope["context"]["creation_id"] != second["context"]["creation_id"]
    assert envelope["scope_ref"] != second["scope_ref"]
    tampered = deepcopy(envelope)
    tampered["context"]["proposal_sha256"] = second["context"]["proposal_sha256"]
    with pytest.raises(ValueError, match="envelope"):
        VisualClaimCarrier(carrier.staged, carrier.selection, tampered)
    cross = VisualClaimCarrier(carrier.staged, carrier.selection, second)
    with pytest.raises(ValueError, match="identity"):
        cross.decode(raw, carrier.identity)


def test_d1_wire_only_roundtrip_and_exact_original_carrier(material_integration_env, monkeypatch):
    env, carrier, raw, canonical, plain, claims = _setup(material_integration_env, monkeypatch)
    assert set(raw) == {"slots", "unresolved"}
    assert all("claim" in row for row in raw["slots"]["slot_000"]["conditions"])
    assert all("claim" not in row for row in plain["slots"]["slot_000"]["conditions"])
    assert "claim" not in json.dumps(canonical)
    assert carrier.encode(plain, {k: v["claim"] for k, v in claims.items()}) == raw
    assert carrier.decode(raw, carrier.identity)[2] == claims
    assert maximum_compact_bytes(carrier.schema) < 512 * 1024
    assert carrier.identity["selection_sha256"] == digest(carrier.selection)


@pytest.mark.parametrize("mutation", [
    "missing_claim", "unknown_claim_field", "claim_program", "claim_unauthorized_scope",
    "claim_strength", "preference_claim_required", "claim_empty_reason",
    "unknown_condition_field", "duplicate_json_key", "missing_condition",
    "changed_identity", "invalid_material_required",
])
def test_d1_claim_negative_wire_rejected(material_integration_env, monkeypatch, mutation):
    env, carrier, raw, canonical, plain, claims = _setup(material_integration_env, monkeypatch)
    broken = deepcopy(raw)
    row = broken["slots"]["slot_000"]["conditions"][0]
    target = broken["slots"]["slot_000"]["conditions"][1]
    if mutation == "missing_claim":
        row.pop("claim")
    elif mutation == "unknown_claim_field":
        row["claim"]["grant_rights"] = True
    elif mutation == "claim_program":
        row["claim"]["claimed_kind"] = "program_derived"
    elif mutation == "claim_unauthorized_scope":
        row["claim"]["creative_goal_ref"] = "scene-404"
    elif mutation == "claim_strength":
        row["claim"]["claimed_strength"] = "preference"
    elif mutation == "preference_claim_required":
        target["claim"]["claimed_kind"] = "creative_preference"
        target["claim"]["claimed_strength"] = "required"
    elif mutation == "claim_empty_reason":
        row["claim"]["reason"] = ""
    elif mutation == "unknown_condition_field":
        row["unknown_authorization"] = "fabricated"
    elif mutation == "duplicate_json_key":
        from easel.integrations.planning_staged_proposal import StagedProposal as S
        with pytest.raises(ValueError, match="Duplicate"):
            S.parse_raw('{"slots":{},"slots":{},"unresolved":[]}')
        return
    elif mutation == "missing_condition":
        # A may freely choose a different valid number of initial conditions;
        # deleting the only required/material condition, however, violates
        # the existing canonical contains obligation and must be rejected.
        broken["slots"]["slot_000"]["conditions"].pop(0)
    elif mutation == "changed_identity":
        with pytest.raises(ValueError, match="identity"):
            carrier.decode(broken, {**carrier.identity, "selection_sha256": "bad"})
        return
    elif mutation == "invalid_material_required":
        row["strength"] = "preference"
        # The required/material contains constraint must still be satisfied
        # by the original unchanged canonical validator, not by the claim.
        with pytest.raises((ValueError, ValidationError)):
            carrier.decode(broken, carrier.identity)
        return
    with pytest.raises((ValueError, ValidationError)):
        carrier.decode(broken, carrier.identity)


def _repair_setup(material_integration_env, monkeypatch):
    envelope, carrier, raw, canonical, details, claims = _setup(material_integration_env, monkeypatch)
    target = {"kind": "complete_obligation", "path": [0, 1],
              "issue": "Original B challenged this visual condition"}
    repair = AtomicSharedRepairCarrier(envelope, canonical, [target], claims)
    replacement = deepcopy(canonical["needs"][0]["conditions"][1])
    replacement["text"] = "使用舒缓节奏与画面留白衔接本片已确认的镜头"
    raw_repair = {"target-0000": {**replacement,
        "claim": _claim("creative_preference", "preference",
                         reason="为当前画面选择能实际审阅的后期节奏建议")}}
    return repair, raw_repair, canonical, claims


def test_d1_shared_repair_atomic_value_and_claim_roundtrip(material_integration_env, monkeypatch):
    repair, wire, original, claims = _repair_setup(material_integration_env, monkeypatch)
    updated, next_claims, receipt = repair.apply(wire, repair.identity)
    assert updated["needs"][0]["conditions"][1]["text"] == wire["target-0000"]["text"]
    assert updated["needs"][0]["conditions"][0] == original["needs"][0]["conditions"][0]
    assert next_claims["needs/0/conditions/0"] == claims["needs/0/conditions/0"]
    assert next_claims["needs/0/conditions/1"] != claims["needs/0/conditions/1"]
    assert receipt["decision"] == "PENDING_B_REVIEW" and receipt["recheck_required"] is True
    assert receipt["updated_claims_sha256"] == digest(next_claims)
    assert repair.apply(wire, repair.identity) == (updated, next_claims, receipt)
    # Claim-only change (same condition) invalidates old accepted identity too.
    same_condition = deepcopy(wire)
    same_condition["target-0000"]["text"] = original["needs"][0]["conditions"][1]["text"]
    same_condition["target-0000"]["claim"]["reason"] = "单独改理由，也必须触发原独立 B 再审"
    revised, revisions, new_receipt = repair.apply(same_condition, repair.identity)
    assert revised == original
    assert revisions != claims
    assert new_receipt["updated_claims_sha256"] != digest(claims)


@pytest.mark.parametrize("mutation", ["missing_claim", "extra_target", "unknown_claim", "wrong_strength",
                                      "wrong_scope", "foreign_identity", "wrong_path", "duplicate_target"])
def test_d1_shared_repair_fail_closed(material_integration_env, monkeypatch, mutation):
    repair, wire, original, claims = _repair_setup(material_integration_env, monkeypatch)
    bad = deepcopy(wire)
    if mutation == "missing_claim":
        bad["target-0000"].pop("claim")
    elif mutation == "extra_target":
        bad["target-0001"] = deepcopy(bad["target-0000"])
    elif mutation == "unknown_claim":
        bad["target-0000"]["claim"]["granted"] = True
    elif mutation == "wrong_strength":
        bad["target-0000"]["claim"]["claimed_strength"] = "required"
    elif mutation == "wrong_scope":
        bad["target-0000"]["claim"]["creative_goal_ref"] = "scene-2"
    elif mutation == "foreign_identity":
        with pytest.raises(ValueError, match="frozen targets changed"):
            repair.apply(bad, {**repair.identity, "original_sha256": "cross-content"})
        return
    elif mutation in {"wrong_path", "duplicate_target"}:
        paths = [{"kind": "complete_obligation", "path": [0, 999], "issue": "wrong"}] if mutation == "wrong_path" \
            else repair.targets + repair.targets
        with pytest.raises(ValueError):
            AtomicSharedRepairCarrier(repair.envelope, original, paths, claims)
        return
    with pytest.raises((ValueError, ValidationError)):
        repair.apply(bad, repair.identity)



def test_d1_nonvisual_details_keep_original_schema(material_integration_env, monkeypatch):
    envelope, carrier, raw, canonical, details, claims = _setup(material_integration_env, monkeypatch)
    mixed_selection = deepcopy(carrier.selection)
    mixed_selection["needs"].append({
        "scope": "global", "role": "背景音乐", "modality": "bgm",
        "necessity": "required", "continuity_choices": [],
    })
    mixed = VisualClaimCarrier(carrier.staged, mixed_selection, envelope)
    assert set(mixed.visual_slots) == {"slot_000"}
    audio_conditions = mixed.schema["properties"]["slots"]["properties"]["slot_001"]["properties"]["conditions"]["items"]
    original_audio_conditions = carrier.staged.details_contract(mixed_selection)["schema"]["properties"]["slots"]["properties"]["slot_001"]["properties"]["conditions"]["items"]
    assert audio_conditions == original_audio_conditions
    assert "claim" not in audio_conditions["properties"]


def test_d1_condition_or_claim_only_change_invalidates_proof_signature(material_integration_env, monkeypatch):
    envelope, carrier, raw, canonical, details, claims = _setup(material_integration_env, monkeypatch)
    edited = deepcopy(raw)
    edited["slots"]["slot_000"]["conditions"][1]["text"] += "，只属于本片"
    updated_canonical, _, updated = carrier.decode(edited, carrier.identity)
    assert updated_canonical != canonical
    assert updated["needs/0/conditions/1"]["record_sha256"] != claims["needs/0/conditions/1"]["record_sha256"]
    same_value = deepcopy(raw)
    same_value["slots"]["slot_000"]["conditions"][1]["claim"]["reason"] += "，需独立 B 审核"
    original_canonical, _, reason_changed = carrier.decode(same_value, carrier.identity)
    assert original_canonical == canonical
    assert reason_changed["needs/0/conditions/1"]["record_sha256"] != claims["needs/0/conditions/1"]["record_sha256"]


def test_d1_original_repair_does_not_allow_audio_or_unrelated_targets(material_integration_env, monkeypatch):
    repair, wire, original, claims = _repair_setup(material_integration_env, monkeypatch)
    with pytest.raises(ValueError, match="categories"):
        AtomicSharedRepairCarrier(repair.envelope, original, [
            {"kind": "need_necessity", "path": [0], "issue": "not this prototype"}
        ], claims)
    with pytest.raises(ValueError, match="claim"):
        AtomicSharedRepairCarrier(repair.envelope, original, repair.targets, {})
