"""New-only D2 typed B/Proof running through native Planning Owner, fixed external replies."""
from copy import deepcopy
import json
from pathlib import Path
import shutil

import pytest

from easel.integrations import semantic_boundary_run
from easel.integrations.hypit import handoff, service
from easel.integrations import result_protocols
from easel.integrations.planning_d2_typed_review import POLICY
from easel.integrations.planning_creative_authority import OWNER_POLICY
from easel.materials.store import AttemptMaterialStore
from tests.test_creation_preparation import _current_vnext_planning_executor, prep_env
from tests.test_material_integration import material_integration_env


def _fresh_d2_attempt(original):
    new = service.create_film_attempt(
        original["creation_id"], original["handoff"]["handoff_id"],
        preparation_key="d" * 64, runtime_status="NOT_CONFIGURED",
        result_protocols=result_protocols.inherited(original),
        creative_claim_policy=OWNER_POLICY, d2_review_policy=POLICY)
    return service.update_film_attempt(
        new["attempt_id"], event="planning_contract_registered",
        planning_contract_version=3)


def _frozen_context(attempt):
    root = Path(attempt["workspace"]["path"])
    _, manifest, _ = handoff.resolve_handoff(
        attempt["creation_id"], attempt["handoff"]["handoff_id"])
    handoff_root = root / "handoff"
    inputs = {key: json.loads((handoff_root / value["path"]).read_text())
              for key, value in (
                  ("content_core", manifest["content"]["content_core"]),
                  ("truth_packet", manifest["content"]["truth_packet"]),
                  ("creator_context", manifest["creator_context"]))}
    refs = {
        "content_core_sha256": manifest["content"]["content_core"]["hash"],
        "truth_packet_sha256": manifest["content"]["truth_packet"]["hash"],
        "creator_context_sha256": manifest["creator_context"]["hash"],
        "production_brief_sha256": manifest["production_request"]["production_brief_sha256"],
        "creative_mode_sha256": manifest["creative_mode"]["hash"]}
    return {**inputs, "context_refs": refs}


@pytest.mark.parametrize("repair", [False, True])
def test_d2_native_review_proof_original_wire_cold_verify(material_integration_env, tmp_path, repair):
    attempt = _fresh_d2_attempt(material_integration_env)
    context = _frozen_context(attempt)
    result = _current_vnext_planning_executor(
        attempt, context, creative_claims=True, d2_review=True, creative_semantic_probe=repair)
    root = Path(attempt["workspace"]["path"])
    checkpoint = json.loads((root / "planning/SEMANTIC_CHECKPOINT.json").read_text())
    journal = AttemptMaterialStore(root).read_recovery_record("semantic-planning-vnext")
    assert checkpoint["scope"]["d2_review_policy"] == POLICY
    proof = checkpoint["d2_decision_proof"]
    assert proof["policy"] == POLICY and proof["reviews"]
    assert not proof["material_ready"] and not proof["rights_granted"]
    assert journal["repair_used"] is repair
    assert any(key.startswith("B-recheck-") for key in journal["calls"]) is repair
    assert semantic_boundary_run.verify(
        root, result["plan"], checkpoint["scope"]["mode"],
        result["script"], attempt=attempt)["policy"] == semantic_boundary_run.POLICY
    clone = tmp_path / "d2-cold"
    shutil.copytree(root, clone, symlinks=True)
    copied_attempt = deepcopy(attempt)
    copied_attempt["workspace"]["path"] = str(clone)
    assert semantic_boundary_run.verify(
        clone, result["plan"], checkpoint["scope"]["mode"],
        result["script"], attempt=copied_attempt)
    changed = json.loads((clone / "planning/SEMANTIC_CHECKPOINT.json").read_text())
    changed["d2_decision_proof"]["reviews"][0]["authorized"] = False
    (clone / "planning/SEMANTIC_CHECKPOINT.json").write_text(json.dumps(changed, ensure_ascii=False))
    with pytest.raises(ValueError, match="D2 DecisionProof"):
        semantic_boundary_run.verify(
            clone, result["plan"], checkpoint["scope"]["mode"],
            result["script"], attempt=copied_attempt)
    first = {k: (v["request_sha256"], v["reply_sha256"]) for k, v in journal["calls"].items()}
    again = _current_vnext_planning_executor(
        attempt, context, creative_claims=True, d2_review=True, creative_semantic_probe=repair)
    assert again["plan"] == result["plan"]
    new = AttemptMaterialStore(root).read_recovery_record("semantic-planning-vnext")
    assert {k: (v["request_sha256"], v["reply_sha256"]) for k, v in new["calls"].items()} == first


def test_d2_rejects_unpinned_context_and_existing_d1_upgrade(material_integration_env):
    attempt = _fresh_d2_attempt(material_integration_env)
    with pytest.raises(ValueError, match="D2 Attempt and Planning Context"):
        semantic_boundary_run.run(attempt, {"creative_claim_policy": OWNER_POLICY},
                                  None, None, None, lambda *_: pytest.fail("no dispatch"))
    from easel.integrations.hypit.errors import HypitIntegrationError
    original_d1 = service.create_film_attempt(
        material_integration_env['creation_id'],
        material_integration_env['handoff']['handoff_id'],
        preparation_key='c' * 64, runtime_status='NOT_CONFIGURED',
        creative_claim_policy=OWNER_POLICY)
    assert original_d1['creative_claim_policy'] == OWNER_POLICY
    assert 'd2_review_policy' not in original_d1
    with pytest.raises(HypitIntegrationError, match="upgrade to D2"):
        service.create_film_attempt(
            material_integration_env["creation_id"],
            material_integration_env["handoff"]["handoff_id"],
            preparation_key="c" * 64, runtime_status="NOT_CONFIGURED",
            creative_claim_policy=OWNER_POLICY, d2_review_policy=POLICY)

def test_d2_official_preparation_to_native_review_proof(prep_env):
    """The actual Preparation entry pins D2 before any external-model boundary."""
    from easel import creation_preparation as prep
    from easel.integrations.material_layer import PlanningIntegration

    from tests.test_creation_preparation import web
    assert web._material_planning_executor.d2_review_policy == POLICY
    def offline_d2(attempt, context):
        assert attempt["creative_claim_policy"] == OWNER_POLICY
        assert attempt["d2_review_policy"] == context["d2_review_policy"] == POLICY
        return _current_vnext_planning_executor(
            attempt, context, creative_claims=True, d2_review=True,
            creative_semantic_probe=True)

    offline_d2.planning_contract_version = 3
    offline_d2.creative_claim_policy = OWNER_POLICY
    offline_d2.d2_review_policy = POLICY

    cid = prep_env["work"]["id"]
    result = prep.prepare_creation_for_hypit(
        cid, runtime_profile=None, planning_executor=offline_d2)
    attempt = service.get_film_attempt(result["attempt_id"])
    assert attempt["d2_review_policy"] == POLICY
    checkpoint = json.loads((Path(attempt["workspace"]["path"]) /
                             "planning/SEMANTIC_CHECKPOINT.json").read_text())
    assert checkpoint["d2_decision_proof"]["reviews"]
    assert PlanningIntegration().load(attempt)["plan"].attempt_id == attempt["attempt_id"]
    journal = AttemptMaterialStore(attempt["workspace"]["path"]).read_recovery_record(
        "semantic-planning-vnext")
    before = {k: v["reply_sha256"] for k, v in journal["calls"].items()}
    repeated = prep.prepare_creation_for_hypit(
        cid, runtime_profile=None, planning_executor=offline_d2)
    assert repeated["attempt_id"] == attempt["attempt_id"]
    after = AttemptMaterialStore(attempt["workspace"]["path"]).read_recovery_record(
        "semantic-planning-vnext")
    assert {k: v["reply_sha256"] for k, v in after["calls"].items()} == before

