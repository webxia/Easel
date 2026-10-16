"""D2 strict typed review - new-only local contract, without paid model calls."""
import pytest

from easel.integrations.planning_authority import digest
from easel.integrations.planning_d2_typed_review import (
    AXES, POLICY, classify_question, compile_proof, validate_typed_issue,
)
from tests.test_planning_creative_authority_d0 import CASES, frozen_r02
from tests.test_material_integration import material_integration_env

def _question(kind="complete_obligation"):
    record = {"path": "needs/0/conditions/0", "scope_ref": "scope-original",
              "condition_sha256": "a" * 64, "claim": {"reason": "frozen director reason"}}
    q = {"question": 12, "kind": kind, "target": [0, 0],
         "candidate": {"text": "frozen visual obligation", "strength": "required",
                       "responsibility": "material"},
         "creative_dependency": {"envelope_scope_ref": "scope-original",
             "claim_sha256_by_ref": {"needs/0/conditions/0": digest(record)}}}
    return q, record


def test_d2_actual_claim_and_review_axes_are_frozen_and_non_authorizing():
    question, record = _question()
    compiled = classify_question(
        question, conditions={record["path"]: record}, headers={},
        envelope={"scope_ref": "scope-original"})
    assert compiled["d2_review"]["policy"] == POLICY
    assert "delegated_creative_validity" in compiled["d2_review"]["axes"]
    assert compiled["d2_review"]["claim_records"][record["path"]]["claim"]["reason"] == "frozen director reason"
    assert "d2_review" not in question
    answer = {"decision": "ACCEPT", "issue_code": "none", "issue_owner": "none",
              "support": [], "reason": "separate B judgment"}
    proof = compile_proof(compiled, answer, attempt_id="fa-new", original_wire_sha256="f" * 64)
    assert proof["authorized"] and not proof["material_ready"] and not proof["rights_granted"]


@pytest.mark.parametrize("decision,code,owner", [
    ("ACCEPT", "director_replan_needed", "director"),
    ("CHALLENGE", "material_supply_pending", "material"),
    ("UNRESOLVED", "none", "none"),
    ("ACCEPT", "none", "creator"),
    ("ACCEPT", "creator_decision_required", "creator"),
    ("CHALLENGE", "source_or_truth_violation", "material"),
])
def test_d2_rejects_unsafe_decision_issue_owner_combinations(decision, code, owner):
    question, record = _question()
    compiled = classify_question(question, conditions={record["path"]: record},
                                 headers={}, envelope={"scope_ref": "scope-original"})
    with pytest.raises(ValueError, match="illegal combination"):
        validate_typed_issue(compiled, {"decision": decision,
            "issue_code": code, "issue_owner": owner})


@pytest.mark.parametrize("decision,code,owner", [
    ("CHALLENGE", "director_replan_needed", "director"),
    ("UNRESOLVED", "creator_decision_required", "creator"),
    ("CHALLENGE", "source_or_truth_violation", "source_truth"),
])
def test_d2_recognizes_block_and_repair_disposition_without_proof(decision, code, owner):
    question, record = _question()
    compiled = classify_question(question, conditions={record["path"]: record},
                                 headers={}, envelope={"scope_ref": "scope-original"})
    answer = {"decision": decision, "issue_code": code, "issue_owner": owner}
    assert validate_typed_issue(compiled, answer)["issue"] == code
    with pytest.raises(ValueError, match="Unaccepted"):
        compile_proof(compiled, answer, attempt_id="fa-new", original_wire_sha256="f" * 64)


def test_d2_refuses_tampered_claim_wrong_scope_and_fake_supply():
    question, record = _question()
    with pytest.raises(ValueError, match="differs"):
        classify_question(question, conditions={record["path"]: {**record, "condition_sha256": "other"}},
                          headers={}, envelope={"scope_ref": "scope-original"})
    with pytest.raises(ValueError, match="lacks original"):
        classify_question(question, conditions={record["path"]: record}, headers={},
                          envelope={"scope_ref": "other"})
    pending, rec = _question("unresolved_classification")
    compiled = classify_question(pending, conditions={rec["path"]: rec}, headers={},
                                 envelope={"scope_ref": "scope-original"})
    with pytest.raises(ValueError, match="MaterialNeed"):
        validate_typed_issue(compiled, {"decision": "ACCEPT", "issue_code": "material_supply_pending",
                                        "issue_owner": "material", "related_needs": []})
    assert validate_typed_issue(compiled, {"decision": "ACCEPT",
        "issue_code": "material_supply_pending", "issue_owner": "material",
        "related_needs": ["candidate_000"]})["issue"] == "material_supply_pending"


@pytest.mark.parametrize(
    "number,kind,target,value_sha,old_decision,request_sha,strength,responsibility,meaning",
    CASES,
)
def test_d2_r02_original_nine_remain_not_accepted_and_typed_synthetics_do_not_upgrade(
        frozen_r02, number, kind, target, value_sha, old_decision, request_sha,
        strength, responsibility, meaning):
    """Preserve the real 9 B receipts; typed examples are expectations, NOT new model replies."""
    import json
    from copy import deepcopy
    from tests.test_planning_creative_authority_d0 import EXPECTED_B_SHA
    journal, requests = frozen_r02
    question, packet, frozen_request = requests[number]
    assert frozen_request == request_sha
    assert question["kind"] == kind and question["target"] == target
    assert digest(question["candidate"]) == value_sha
    original_call = journal["calls"][f"B-{number // 8:03d}"]
    assert original_call["reply_sha256"] == EXPECTED_B_SHA[f"B-{number // 8:03d}"]
    actual = next(row["answer"] for row in json.loads(original_call["reply"])["answers"]
                  if row["question_id"] == f"question-{number:04d}")
    assert actual["decision"] == old_decision and old_decision != "ACCEPT"
    with pytest.raises(ValueError, match="lacks original D1"):
        classify_question(question, conditions={}, headers={},
                          envelope={"scope_ref": "new-D2-only-synthetic-scope"})
    # A synthetic positive type demonstrates only well-typed original blocking;
    # it never promotes the immutable old decision to a new Planning Proof.
    row = {"path": f"needs/{number}/conditions/0", "scope_ref": "synthetic-d2",
           "condition_sha256": value_sha, "claim": {"reason": "illustrative only"}}
    supplied = {**deepcopy(question), "creative_dependency": {
        "envelope_scope_ref": "synthetic-d2",
        "claim_sha256_by_ref": {row["path"]: digest(row)}}}
    compiled = classify_question(supplied, conditions={row["path"]: row}, headers={},
                                 envelope={"scope_ref": "synthetic-d2"})
    code, owner = (("source_or_truth_violation", "source_truth") if old_decision == "CHALLENGE"
                   else ("creator_decision_required", "creator"))
    synthetic = {**actual, "issue_code": code, "issue_owner": owner}
    assert validate_typed_issue(compiled, synthetic)["decision"] == old_decision
    with pytest.raises(ValueError, match="Unaccepted"):
        compile_proof(compiled, synthetic, attempt_id="new-synthetic-attempt",
                      original_wire_sha256="f" * 64)
    with pytest.raises(ValueError, match="illegal combination"):
        validate_typed_issue(compiled, {**synthetic, "decision": "ACCEPT"})


@pytest.mark.parametrize("index", range(3))
def test_d2_same_mode_three_distinct_content_claim_proofs_isolate(
        material_integration_env, monkeypatch, index):
    """Three lawful confirmed Content sources: D2 synthetic review cannot cross Claim scope."""
    from tests.test_planning_creative_authority_d1_prototype import _setup
    env, _, _, value, _, conditions = _setup(
        material_integration_env, monkeypatch, index=index)
    key = "needs/0/conditions/0"
    record = conditions[key]
    condition = value["needs"][0]["conditions"][0]
    q = {"question": 0, "kind": "complete_obligation", "target": [0, 0],
         "candidate": condition, "creative_dependency": {
             "envelope_scope_ref": env["scope_ref"],
             "claim_sha256_by_ref": {key: digest(record)}}}
    frozen = classify_question(q, conditions=conditions, headers={}, envelope=env)
    answer = {"decision": "ACCEPT", "issue_code": "none", "issue_owner": "none",
              "support": [], "reason": "synthetic independent B judgment"}
    proof = compile_proof(frozen, answer, attempt_id=env["context"]["attempt_id"],
                          original_wire_sha256="a" * 64)
    assert proof["attempt_id"] == env["context"]["attempt_id"]
    assert not proof["rights_granted"] and not proof["material_ready"]
    other = _setup(material_integration_env, monkeypatch, index=(index + 1) % 3)[0]
    assert env["context"]["creative_mode_sha256"] == other["context"]["creative_mode_sha256"]
    with pytest.raises(ValueError, match="lacks original D1"):
        classify_question(q, conditions=conditions, headers={}, envelope=other)

