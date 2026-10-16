"""S1 regressions: multi-Need Claim indices, claim-only recheck and raw SHA."""
from copy import deepcopy
import json
import pytest
from easel.integrations.planning_creative_authority import (
    ExtendedSharedRepairCarrier, bind_review_claims,
    freeze_original_capture, verify_original_capture, digest,
)
from easel.integrations.planning_semantic_review import recheck
from easel.integrations.planning_result_contract import ReviewResponse
from tests.test_planning_creative_authority_d1_extended import _setup_header, _header_claim, _wire_header_claim
from tests.test_planning_creative_authority_d1_prototype import _claim
from tests.test_material_integration import material_integration_env


def test_s1_two_appended_needs_preserve_distinct_claims(material_integration_env, monkeypatch):
    env, header, raw, original, conditions, headers = _setup_header(
        material_integration_env, monkeypatch)
    value = deepcopy(original["needs"][0])
    targets = [{"kind": "frozen_visual_coverage", "path": ["scene-1"], "issue": "first"},
               {"kind": "frozen_visual_coverage", "path": ["scene-2"], "issue": "second"}]
    carrier = ExtendedSharedRepairCarrier(env, original, targets, conditions, headers)
    wire = {}
    for i in range(2):
        item = {**deepcopy(value), "role": f"new Need {i}"}
        wire[f"target-{i:04d}"] = {"value": item, "authority": {
            "header_claim": _wire_header_claim(item),
            "condition_claims": [_claim(
                "director_local_choice", condition["strength"],
                reason="This new Need remains subject to independent B review")
                for condition in item["conditions"]]}}
    result, con, hdr, receipt = carrier.apply(wire, carrier.identity)
    assert len(result["needs"]) == 3
    assert {"needs/1/header", "needs/2/header"} <= set(hdr)
    assert {"needs/1/conditions/0", "needs/2/conditions/0"} <= set(con)
    assert len({hdr[key]["record_sha256"] for key in ("needs/1/header", "needs/2/header")}) == 2
    assert receipt["decision"] == "PENDING_B_REVIEW"


def test_s1_claim_only_change_rechecks_old_accept(material_integration_env, monkeypatch):
    env, header, raw, original, conditions, headers = _setup_header(
        material_integration_env, monkeypatch)
    question = {"question": 0, "kind": "visual_choices", "target": [0],
                "candidate": {"role": original["needs"][0]["role"]}}
    directory = bind_review_claims({"questions": [question]}, envelope=env,
                                   conditions=conditions, headers=headers)
    replies = [ReviewResponse.model_validate({"answers": [{
        "question": 0, "decision": "ACCEPT", "reason": "reviewed original",
        "evidence": [0]}]})]
    kept, pending = recheck(directory, replies, deepcopy(directory))
    assert kept[0]["decision"] == "ACCEPT" and not pending["questions"]
    revised = deepcopy(headers)
    revised["needs/0/header"]["claim"]["reason"] += " changed"
    changed = bind_review_claims({"questions": [question]}, envelope=env,
                                 conditions=conditions, headers=revised)
    kept, pending = recheck(directory, replies, changed)
    assert kept == {} and len(pending["questions"]) == 1
    modified_policy = deepcopy(changed)
    modified_policy["questions"][0]["creative_dependency"]["policy"] = "future"
    kept, pending = recheck(changed, replies, modified_policy)
    assert not kept and len(pending["questions"]) == 1


def test_s1_original_capture_exact_bytes_and_tamper(material_integration_env, monkeypatch):
    env, header, raw, original, conditions, headers = _setup_header(
        material_integration_env, monkeypatch)
    reply = json.dumps(raw, ensure_ascii=False, indent=2) + "\n"
    expected = header.decode(raw, header.identity)
    record = freeze_original_capture(env, header.identity, reply, expected)
    assert record["original_reply"] == reply
    assert verify_original_capture(record, env, header.identity, header.decode) == expected
    edited = deepcopy(record)
    edited["original_reply"] = json.dumps(raw, ensure_ascii=False)
    with pytest.raises(ValueError, match="SHA"):
        verify_original_capture(edited, env, header.identity, header.decode)
    changed = deepcopy(record)
    changed["codec_identity"]["policy"] = "old"
    with pytest.raises(ValueError):
        verify_original_capture(changed, env, header.identity, header.decode)


@pytest.mark.parametrize("target_order", ["visual_first", "necessity_first"])
def test_s1_same_need_mixed_header_and_necessity_preserves_both(
        material_integration_env, monkeypatch, target_order):
    from easel.integrations import planning_candidate_review
    from easel.integrations.planning_creative_authority import _header_fields
    env, _, _, original, conditions, headers = _setup_header(
        material_integration_env, monkeypatch)
    original = deepcopy(original)
    original["needs"][0]["necessity"] = "optional"
    old = deepcopy(headers)
    old["needs/0/header"]["header_sha256"] = digest(_header_fields(original["needs"][0]))
    visual = {"kind": "visual_choices", "path": [0], "issue": "visual header"}
    necessity = {
        "kind": "confirmed_necessity",
        "policy": planning_candidate_review.POLICY,
        "path": ["needs", 0, "necessity"], "old_value": "optional",
        "need_sha256": digest(original["needs"][0]),
        "inputs_sha256": "frozen-test-input",
        "judgment": {"decision": "CHALLENGE"},
    }
    targets = [visual, necessity] if target_order == "visual_first" else [necessity, visual]
    carrier = ExtendedSharedRepairCarrier(env, original, targets, conditions, old)
    new_need = deepcopy(original["needs"][0])
    new_need["role"] = "new director scene composition"
    director = _wire_header_claim(new_need)
    values = {
        "visual_choices": {
            "value": new_need,
            "authority": {
                "header_claim": director,
                "condition_claims": [_claim(
                    "director_local_choice", c["strength"],
                    reason="New shot reason must survive necessity promotion")
                    for c in new_need["conditions"]],
            },
        },
        "confirmed_necessity": "required",
    }
    wire = {f"target-{i:04d}": deepcopy(values[t["kind"]])
            for i, t in enumerate(targets)}
    if target_order == "necessity_first":
        # Existing canonical patch order prohibits a subsequent stale optional
        # Header replacing a program-confirmed required Need.
        with pytest.raises(ValueError, match="Header patch cannot rewrite"):
            carrier.apply(wire, carrier.identity)
        return
    result, new_conditions, new_headers, receipt = carrier.apply(wire, carrier.identity)
    row = new_headers["needs/0/header"]
    assert result["needs"][0]["necessity"] == "required"
    assert result["needs"][0]["role"] == new_need["role"]
    assert row["claim"] == _header_claim(new_need)
    assert row["necessity_evidence"]["origin"] == "program_derived_from_frozen_B_necessity"
    assert row["necessity_evidence"]["claim_header_sha256"] == digest(_header_fields(new_need))
    assert row["necessity_evidence"]["target_sha256"] == digest(necessity)
    assert row["header_sha256"] == digest(_header_fields(result["needs"][0]))
    assert row["header_sha256"] != row["necessity_evidence"]["claim_header_sha256"]
    assert row["recheck_required"] and receipt["decision"] == "PENDING_B_REVIEW"
    assert carrier.apply(wire, carrier.identity) == (result, new_conditions, new_headers, receipt)


def test_s1_mixed_repair_wrong_necessity_fails_without_claim_promotion(
        material_integration_env, monkeypatch):
    from easel.integrations import planning_candidate_review
    from easel.integrations.planning_creative_authority import _header_fields
    env, _, _, original, conditions, headers = _setup_header(
        material_integration_env, monkeypatch)
    original = deepcopy(original)
    original["needs"][0]["necessity"] = "optional"
    headers = deepcopy(headers)
    headers["needs/0/header"]["header_sha256"] = digest(_header_fields(original["needs"][0]))
    targets = [
        {"kind": "visual_choices", "path": [0], "issue": "visual"},
        {"kind": "confirmed_necessity", "policy": planning_candidate_review.POLICY,
         "path": ["needs", 0, "necessity"], "old_value": "optional",
         "need_sha256": digest(original["needs"][0]), "inputs_sha256": "frozen",
         "judgment": {"decision": "CHALLENGE"}},
    ]
    carrier = ExtendedSharedRepairCarrier(env, original, targets, conditions, headers)
    need = deepcopy(original["needs"][0])
    wire = {
        "target-0000": {"value": need, "authority": {
            "header_claim": _wire_header_claim(need),
            "condition_claims": [_claim(
                "director_local_choice", c["strength"],
                reason="Valid local condition still needs B review")
                for c in need["conditions"]]}},
        "target-0001": "optional",
    }
    with pytest.raises((ValueError, Exception)):
        carrier.apply(wire, carrier.identity)

