"""D3: original D2 Planning Proof -> actual consumer handoff, no paid build."""
from copy import deepcopy
import json
from pathlib import Path
import pytest

from easel.integrations.planning_d3_consumers import describe_consumers, POLICY
from easel.integrations.material_layer import (
    PlanningIntegration, MaterialGateIntegration, MaterialIntegrationError)
from easel.integrations.hypit import service
from easel.materials.store import AttemptMaterialStore
from tests.test_creation_preparation import prep_env, _current_vnext_planning_executor
from easel.integrations.planning_creative_authority import OWNER_POLICY
from easel.integrations.planning_d2_typed_review import POLICY as D2_POLICY


def _ready_new_d2_planning(prep_env):
    from easel import creation_preparation as prep
    def offline_d2(attempt, context):
        return _current_vnext_planning_executor(
            attempt, context, creative_claims=True, d2_review=True,
            creative_semantic_probe=True)
    offline_d2.planning_contract_version = 3
    offline_d2.creative_claim_policy = OWNER_POLICY
    offline_d2.d2_review_policy = D2_POLICY
    created = prep.prepare_creation_for_hypit(
        prep_env["work"]["id"], runtime_profile=None, planning_executor=offline_d2)
    attempt = service.get_film_attempt(created["attempt_id"])
    return attempt, PlanningIntegration().load(attempt)


def test_d3_legitimate_empty_material_planning_can_load_with_real_consumer_contract(prep_env):
    attempt, planning = _ready_new_d2_planning(prep_env)
    consumer = planning["consumer_contract"]
    assert consumer["policy"] == POLICY
    assert consumer["attempt_id"] == attempt["attempt_id"]
    assert consumer["plan_id"] == planning["plan"].plan_id
    assert consumer["readiness"] == "PLANNING_HANDOFF_ONLY"
    assert consumer["material_ready"] is False
    assert consumer["rights_granted"] is False
    assert consumer["quality_pass"] is False
    assert consumer["hard_clauses"]
    assert any(c["consumer"] == "material" for c in consumer["hard_clauses"])
    assert any(c["consumer"] == "authoring_quality_pending" for c in consumer["hard_clauses"])
    assert all(c["status"] == "PENDING_CONSUMER_EVIDENCE"
               and not c["quality_fulfilled"] and not c["material_rights_admitted"]
               for c in consumer["hard_clauses"])
    assert all(c["need_id"] in {n.need_id for n in planning["plan"].needs}
               for c in consumer["hard_clauses"])
    with pytest.raises(MaterialIntegrationError, match="MATERIAL_READY"):
        MaterialGateIntegration().assert_ready(attempt)
    assert PlanningIntegration().load(attempt)["consumer_contract"] == consumer


def test_d3_consumer_proof_tampering_cross_attempt_need_and_hard_downgrade_fail_closed(prep_env):
    attempt, planning = _ready_new_d2_planning(prep_env)
    root = Path(attempt["workspace"]["path"])
    source = json.loads((root / "planning/SEMANTIC_CHECKPOINT.json").read_text())
    plan = planning["plan"]
    valid = describe_consumers(attempt=attempt, plan=plan, checkpoint=source)
    assert valid["hard_clauses"]
    bad_attempt = {**attempt, "attempt_id": "fa_another_work"}
    with pytest.raises(ValueError, match="identity"):
        describe_consumers(attempt=bad_attempt, plan=plan, checkpoint=source)
    tampered = deepcopy(source)
    target = next(r for r in tampered["d2_decision_proof"]["reviews"]
                  if isinstance(r["need_target"][0], int) and len(r["need_target"]) == 2)
    target["candidate_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="Condition differs"):
        describe_consumers(attempt=attempt, plan=plan, checkpoint=tampered)
    tampered = deepcopy(source)
    target = next(r for r in tampered["d2_decision_proof"]["reviews"]
                  if isinstance(r["need_target"][0], int) and len(r["need_target"]) == 2)
    target["enforcing_consumer"] = "planning_review_only"
    with pytest.raises(ValueError, match="consumer responsibility"):
        describe_consumers(attempt=attempt, plan=plan, checkpoint=tampered)
    tampered = deepcopy(source)
    tampered["d2_decision_proof"]["material_ready"] = True
    with pytest.raises(ValueError, match="overstated"):
        describe_consumers(attempt=attempt, plan=plan, checkpoint=tampered)
    tampered = deepcopy(source)
    target = next(r for r in tampered["d2_decision_proof"]["reviews"]
                  if isinstance(r["need_target"][0], int) and len(r["need_target"]) == 2)
    target["consumer_fulfillment"] = "PASS"
    with pytest.raises(ValueError, match="self-certify"):
        describe_consumers(attempt=attempt, plan=plan, checkpoint=tampered)


def test_d3_soft_continuity_reference_never_proves_physical_hard(prep_env):
    from easel.materials.domain import ContinuityRef
    attempt, planning = _ready_new_d2_planning(prep_env)
    root = Path(attempt['workspace']['path'])
    checkpoint = json.loads((root / 'planning/SEMANTIC_CHECKPOINT.json').read_text())
    plan = planning['plan']
    # A synthetic capability counterexample, never persisted or submitted:
    # even a formally typed continuity ref cannot assert physical identity.
    needs = list(plan.needs)
    needs[0] = needs[0].model_copy(update={
        'continuity_refs': (ContinuityRef(kind='character', ref='frozen-identity'),)})
    hypothetical = plan.model_copy(update={'needs': tuple(needs)})
    status = describe_consumers(attempt=attempt, plan=hypothetical, checkpoint=checkpoint)
    assert status['continuity_obligations']
    assert status['continuity_obligations'][0]['hard_fulfillment'] == 'BLOCKED_UNVERIFIABLE'
    assert not status['continuity_obligations'][0]['placement_proven']
    assert not status['continuity_obligations'][0]['observed_continuity_proven']
    assert status['quality_pass'] is False


def test_d3_missing_real_postproduction_or_continuity_evidence_is_not_fulfilled(prep_env):
    attempt, planning = _ready_new_d2_planning(prep_env)
    consumer = planning["consumer_contract"]
    # No real Authoring/Build/Output or observed identity/placement has happened.
    root = Path(attempt["workspace"]["path"])
    assert not (root / "productions/easel-authoring/POSTPRODUCTION_REQUIREMENTS.json").exists()
    assert not attempt.get("outputs")
    assert consumer["quality_pass"] is False
    assert "not identity or Hard fulfillment" in consumer["continuity_rule"]
    assert all(row["hard_fulfillment"] == "BLOCKED_UNVERIFIABLE"
               and not row["physical_identity_proven"]
               and not row["placement_proven"]
               and not row["observed_continuity_proven"]
               for row in consumer["continuity_obligations"])
    assert consumer["authoring_verifier"].startswith("ProductionAuthoringIntegration")
    assert consumer["quality_verifier"].startswith("hypit.quality")
    with pytest.raises(MaterialIntegrationError, match="MATERIAL_READY"):
        MaterialGateIntegration().assert_ready(attempt)
