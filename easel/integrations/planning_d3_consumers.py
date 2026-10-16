"""D3 read-only Planning Proof -> existing Material/Authoring/Quality consumer contract.

The result describes *who must enforce* accepted Hard requirements. No D3
state machine, new readiness, model dispatch, rights grant, or fulfillment.
"""
from __future__ import annotations
from easel.integrations.planning_authority import digest
from easel.integrations.planning_d2_typed_review import POLICY as D2_POLICY

POLICY = "planning-d3-consumer-handoff@1"


def describe_consumers(*, attempt, plan, checkpoint):
    """Derive verifiable consumer responsibility from original frozen D2 proof.

    Only called after the existing native Planning verify() succeeded.
    All required clauses remain PENDING until the respective consumer produces
    independently checked assets, authoring output or quality evidence.
    """
    if attempt.get("d2_review_policy") != D2_POLICY:
        raise ValueError("D3 requires the original D2 Attempt identity")
    if (not isinstance(checkpoint, dict)
            or checkpoint.get("scope", {}).get("attempt_id") != attempt.get("attempt_id")
            or checkpoint.get("scope", {}).get("d2_review_policy") != D2_POLICY):
        raise ValueError("D3 checkpoint/Attempt identity mismatch")
    proof = checkpoint.get("d2_decision_proof")
    if (not isinstance(proof, dict) or proof.get("policy") != D2_POLICY
            or proof.get("attempt_id") != attempt["attempt_id"]
            or proof.get("material_ready") is not False
            or proof.get("rights_granted") is not False):
        raise ValueError("D3 missing or overstated frozen DecisionProof")
    layouts = checkpoint.get("proof", {}).get("layouts", [])
    if not isinstance(layouts, list):
        raise ValueError("D3 missing formal candidate-to-Need layouts")
    by_index = {}
    for item in layouts:
        if (type(item.get("candidate_index")) is not int
                or item["candidate_index"] in by_index
                or not isinstance(item.get("need_id"), str)
                or not isinstance(item.get("conditions"), list)):
            raise ValueError("D3 duplicate or invalid frozen layout")
        by_index[item["candidate_index"]] = item
    needs = {n.need_id: n for n in plan.needs}
    if (plan.attempt_id != attempt["attempt_id"]
            or plan.creation_id != attempt["creation_id"]
            or set(record["need_id"] for record in layouts) - set(needs)):
        raise ValueError("D3 formal Plan and frozen Proof do not share Attempt/Need identity")
    covered = []
    clauses = []
    for item in proof.get("reviews", []):
        if (item.get("policy") != D2_POLICY
                or item.get("attempt_id") != attempt["attempt_id"]
                or item.get("rights_granted") is not False
                or item.get("material_ready") is not False
                or item.get("consumer_fulfillment") != "PENDING_OR_NOT_APPLICABLE"
                or item.get("review_decision") != "ACCEPT"
                or item.get("classification", {}).get("decision") != "ACCEPT"):
            raise ValueError("D3 DecisionProof cannot self-certify downstream fulfillment")
        target = item.get("need_target")
        if not isinstance(target, list):
            raise ValueError("D3 invalid frozen question target")
        if (not target or type(target[0]) is not int):
            # Global coverage question has no single Need and no Hard grant.
            if item.get("enforcing_consumer") != "planning_review_only":
                raise ValueError("D3 global coverage cannot grant consumer fulfillment")
            continue
        layout = by_index.get(target[0])
        if layout is None:
            raise ValueError("D3 reviewed candidate has no current MaterialNeed")
        need = needs[layout["need_id"]]
        consumer = item.get("enforcing_consumer")
        if consumer not in {"material", "authoring_quality_pending", "planning_review_only"}:
            raise ValueError("D3 unknown consumer designation")
        if len(target) == 2 and type(target[1]) is int:
            if not 0 <= target[1] < len(layout["conditions"]):
                raise ValueError("D3 Condition index is not in frozen Need")
            clause = layout["conditions"][target[1]]
            if digest(clause) != item.get("candidate_sha256"):
                raise ValueError("D3 frozen Condition differs from final source")
            strength, responsibility = clause.get("strength"), clause.get("responsibility")
            if strength != item.get("strength") or responsibility != item.get("responsibility"):
                raise ValueError("D3 final strength/responsibility differs from Proof")
            expected = ("material" if responsibility == "material" else "authoring_quality_pending")
            if consumer != expected:
                raise ValueError("D3 required consumer responsibility changed")
            content = (need.intent.description if responsibility == "material"
                       else need.intent.function)
            if not isinstance(content, str) or clause["text"] not in content:
                raise ValueError("D3 required expression is absent from formal Need")
            if strength == "required":
                clauses.append({"need_id": need.need_id, "need_index": target[0],
                                "condition_index": target[1], "text_sha256": digest(clause),
                                "responsibility": responsibility,
                                "consumer": consumer,
                                "status": "PENDING_CONSUMER_EVIDENCE",
                                "material_rights_admitted": False,
                                "quality_fulfilled": False})
        covered.append({"question_id": item.get("question_id"),
                        "need_id": need.need_id, "consumer": consumer})
    return {
        "policy": POLICY, "attempt_id": attempt["attempt_id"], "plan_id": plan.plan_id,
        "plan_sha256": digest(plan.model_dump(mode="json")),
        "d2_proof_sha256": digest(proof),
        "hard_clauses": clauses, "reviewed_needs": covered,
        "material_verifier": "MaterialGateIntegration.assert_ready",
        "authoring_verifier": "ProductionAuthoringIntegration.prepare/openclaw_authoring input SHA",
        "quality_verifier": "hypit.quality.inspect_output/Output SHA/observed frames",
        "continuity_rule": "continuity_refs are preference/matching signals, not identity or Hard fulfillment",
        "continuity_obligations": [
            {"need_id": need.need_id,
             "source_refs": [ref.model_dump(mode="json") for ref in need.continuity_refs],
             "physical_identity_proven": False, "placement_proven": False,
             "observed_continuity_proven": False,
             "hard_fulfillment": "BLOCKED_UNVERIFIABLE"}
            for need in plan.needs if need.continuity_refs],
        "readiness": "PLANNING_HANDOFF_ONLY",
        "rights_granted": False, "material_ready": False, "quality_pass": False,
    }
