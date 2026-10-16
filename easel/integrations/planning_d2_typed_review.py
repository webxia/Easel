"""D2 Planning-local typed B issue contract; no independent authorization or dispatch.

The wire-level version is opt-in only after the existing B Identity and frozen
checkpoint have a single same-version admission. No old B receipt is upgraded.
"""
from __future__ import annotations

from copy import deepcopy
from easel.integrations.planning_authority import digest

POLICY = "planning-d2-typed-b@1"
AXES = (
    "confirmed_fidelity",
    "delegated_creative_validity",
    "responsibility_enforcement",
    "coverage_uncertainty",
)
ISSUES = {
    "none": ("ACCEPT", "none"),
    "director_replan_needed": ("CHALLENGE", "director"),
    "creator_decision_required": ("UNRESOLVED", "creator"),
    "material_supply_pending": ("ACCEPT", "material"),
    "source_or_truth_violation": ("CHALLENGE", "source_truth"),
}
VISUAL_KINDS = {
    "complete_obligation": AXES[:3],
    "visual_choices": AXES[:3],
    "need_necessity": AXES[:3],
    "frozen_visual_coverage": (AXES[0], AXES[3]),
    "unresolved_classification": (AXES[0], AXES[3]),
}


def classify_question(question, *, conditions, headers, envelope):
    """Attach bounded D2 axes and actual frozen Claim records, not only SHA."""
    if question.get("kind") not in VISUAL_KINDS:
        return deepcopy(question)
    q = deepcopy(question)
    binding = q.get("creative_dependency")
    if (not isinstance(binding, dict)
            or binding.get("envelope_scope_ref") != envelope.get("scope_ref")):
        raise ValueError("D2 visual question lacks original D1 claim dependencies")
    rows = {}
    for ref, sha in binding["claim_sha256_by_ref"].items():
        record = headers.get(ref) if ref.endswith("/header") else conditions.get(ref)
        if record is None or digest(record) != sha:
            raise ValueError("D2 frozen Claim detail differs from D1 B dependency")
        rows[ref] = deepcopy(record)
    q["d2_review"] = {
        "policy": POLICY, "axes": list(VISUAL_KINDS[q["kind"]]),
        "claim_records": rows, "envelope_scope_ref": envelope["scope_ref"],
    }
    return q


def validate_typed_issue(question, answer):
    """Fail closed on unsupported decision/issue/owner combinations.

    This validates *classification* only, never grants actual Creator/Rights
    permission. Underlying support, quote, and semantic validators still run.
    """
    if question.get("kind") not in VISUAL_KINDS:
        if "issue_code" in answer or "issue_owner" in answer:
            raise ValueError("D2 labels cannot alter unrelated B answers")
        return {"policy": POLICY, "issue": "not_applicable"}
    if question.get("d2_review", {}).get("policy") != POLICY:
        raise ValueError("D2 question policy missing")
    code = answer.get("issue_code")
    owner = answer.get("issue_owner")
    decision = answer.get("decision")
    if code not in ISSUES or ISSUES[code] != (decision, owner):
        raise ValueError("D2 decision/issue/owner illegal combination")
    if code == "material_supply_pending":
        if question["kind"] != "unresolved_classification":
            raise ValueError("Material pending may only classify frozen unresolved supply")
        # The original B relational answer must already have proven actual
        # related Need(s). Empty witness lists never become supply READY.
        if not answer.get("related_needs"):
            raise ValueError("No existing MaterialNeed can inherit pending supply")
    return {"policy": POLICY, "issue": code, "owner": owner,
            "decision": decision,
            "question_sha256": digest(question),
            "answer_sha256": digest(answer)}


def compile_proof(question, answer, *, attempt_id, original_wire_sha256):
    """Produce a bounded Planning-local audit candidate, never a rights grant."""
    classification = validate_typed_issue(question, answer)
    if classification.get("decision") != "ACCEPT":
        raise ValueError("Unaccepted B question cannot produce Planning proof")
    if not isinstance(attempt_id, str) or not attempt_id:
        raise ValueError("Missing original Planning Attempt")
    if not isinstance(original_wire_sha256, str) or len(original_wire_sha256) != 64:
        raise ValueError("Missing frozen original B reply digest")
    records = question["d2_review"]["claim_records"]
    # This is the *model-proposed* claim kind, accepted only as Planning
    # semantics after independent supported B review; not a Creator grant.
    claim_kinds = sorted({record["claim"]["claimed_kind"] for record in records.values()
                          if isinstance(record.get("claim"), dict)
                          and "claimed_kind" in record["claim"]})
    candidate = question["candidate"]
    return {"policy": POLICY, "attempt_id": attempt_id,
            "original_b_reply_sha256": original_wire_sha256,
            "classification": classification,
            "authorized_kind": claim_kinds,
            "basis": {"question_sha256": digest(question),
                      "support": deepcopy(answer.get("support", [])),
                      "review_reason": answer.get("reason"),
                      "frozen_scope_ref": question["d2_review"]["envelope_scope_ref"]},
            "strength": candidate.get("strength"),
            "responsibility": candidate.get("responsibility"),
            "review_decision": classification["decision"],
            "issue_owner": classification["owner"],
            "authorized": classification["issue"] == "none",
            "material_ready": False, "rights_granted": False}

def bind_directory(directory, *, envelope, conditions, headers):
    """New-only D2 projection after the already-frozen D1 B dependencies."""
    if directory.get("d2_review_policy") is not None:
        raise ValueError("D2 directory already owns another review policy")
    updated = deepcopy(directory)
    updated["d2_review_policy"] = POLICY
    updated["questions"] = [
        classify_question(question, envelope=envelope, conditions=conditions,
                          headers=headers)
        for question in directory["questions"]
    ]
    return updated


def compile_decision_proofs(directory, responses, *, attempt_id, b_captures):
    """Derive accepted Planning proofs from original captured B wire and answers.

    Deliberately separate Planning acceptance from future Rights/Material/Quality
    fulfillment. Downstream D3 may reference it but cannot mutate this snapshot.
    """
    if directory.get("d2_review_policy") != POLICY:
        raise ValueError("D2 Proof cannot compile without frozen directory policy")
    if not isinstance(b_captures, dict) or not b_captures:
        raise ValueError("D2 original B captures required")
    captures = {}
    for key, raw in sorted(b_captures.items()):
        if not (key.startswith("B-") and isinstance(raw, str) and raw):
            raise ValueError("D2 requires original B or B-recheck wire capture")
        import hashlib
        captures[key] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    actual = {}
    for response in responses:
        for answer in response.answers:
            if answer.question in actual:
                raise ValueError("D2 duplicate B answer identity")
            actual[answer.question] = answer.model_dump(mode="json")
    if set(actual) != {q["question"] for q in directory["questions"]}:
        raise ValueError("D2 final answer coverage incomplete")
    wire_identity = digest(captures)
    rows = []
    for question in directory["questions"]:
        answer = actual[question["question"]]
        if answer.get("decision") != "ACCEPT":
            raise ValueError("D2 unreviewed B result cannot publish Planning Proof")
        row = compile_proof(question, answer, attempt_id=attempt_id,
                            original_wire_sha256=wire_identity)
        row["question_id"] = question["question"]
        row["review_axes"] = list(question.get("d2_review", {}).get("axes", ()))
        row["frozen_claims_sha256"] = digest(
            question.get("d2_review", {}).get("claim_records", {}))
        # Bind both original Need provenance and model-asserted creative basis
        # in the Planning-only Proof. A frozen path is never itself B authority.
        row["claim_source_bindings"] = [
            {"claim_path": ref,
             "need_source_ref": record.get("need_source_ref"),
             "creative_basis_ref": (record.get("claim") or {}).get("creative_goal_ref")
                if isinstance(record.get("claim"), dict) else None}
            for ref, record in sorted(question.get("d2_review", {}).get("claim_records", {}).items())
        ]
        row["need_target"] = deepcopy(question["target"])
        row["candidate_sha256"] = digest(question["candidate"])
        row["enforcing_consumer"] = (
            "material" if question["kind"] == "complete_obligation"
                and question["candidate"].get("responsibility") == "material"
            else "authoring_quality_pending" if question["kind"] == "complete_obligation"
                and question["candidate"].get("responsibility") in ("postproduction", "narrative")
            else "planning_review_only")
        row["consumer_fulfillment"] = "PENDING_OR_NOT_APPLICABLE"
        rows.append(row)
    return {
        "policy": POLICY, "attempt_id": attempt_id,
        "directory_sha256": digest(directory),
        "b_original_captures": captures,
        "reviews": rows, "material_ready": False, "rights_granted": False,
    }

