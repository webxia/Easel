"""New-Only D1 Claim: real native Owner A -> B -> Checkpoint / cold verify."""
from copy import deepcopy
import json
from pathlib import Path
import shutil

import pytest
from easel.integrations.planning_creative_authority import OWNER_POLICY
from easel.integrations import semantic_boundary_run
from easel.materials.store import AttemptMaterialStore
from easel.integrations.hypit import handoff
from tests.test_creation_preparation import _current_vnext_planning_executor
from tests.test_material_integration import material_integration_env




def _new_frozen_d1_attempt(existing):
    """Fresh legal D1 Attempt, never upgrading an already-created fixture Attempt."""
    from easel.integrations.hypit import service
    from easel.integrations import result_protocols
    created = service.create_film_attempt(
        existing['creation_id'], existing['handoff']['handoff_id'],
        preparation_key='c' * 64, runtime_status='NOT_CONFIGURED',
        result_protocols=result_protocols.inherited(existing),
        creative_claim_policy=OWNER_POLICY)
    return service.update_film_attempt(
        created['attempt_id'], event='planning_contract_registered',
        planning_contract_version=3)

def test_d1_frozen_policy_rejects_direct_owner_and_generic_attempt_mutation(material_integration_env, monkeypatch):
    """Attempt is the only D1 policy authority across public and internal entrypoints."""
    from easel.integrations.hypit import service
    from easel.integrations.hypit.errors import HypitIntegrationError
    from tests.test_creation_preparation import web
    current = _new_frozen_d1_attempt(material_integration_env)
    legacy = material_integration_env

    def must_not_enter(*args, **kwargs):
        pytest.fail("Mismatched D1 identity reached model boundary")
    monkeypatch.setattr(web, "_semantic_material_planning_executor", must_not_enter)
    with pytest.raises(Exception, match="D1 frozen Attempt/PlanningContext Policy mismatch"):
        web._material_planning_executor(current, {"context_refs": {}})
    with pytest.raises(Exception, match="D1 frozen Attempt/PlanningContext Policy mismatch"):
        web._material_planning_executor(legacy, {"creative_claim_policy": OWNER_POLICY})
    with pytest.raises(ValueError, match="Frozen D1 Attempt and Planning Context policy differ"):
        semantic_boundary_run.run(current, {}, None, None, None, must_not_enter)
    with pytest.raises(ValueError, match="Frozen D1 Attempt and Planning Context policy differ"):
        semantic_boundary_run.run(legacy, {"creative_claim_policy": OWNER_POLICY}, None, None, None, must_not_enter)

    frozen_before = service.get_film_attempt(current["attempt_id"])
    legacy_before = service.get_film_attempt(legacy["attempt_id"])
    for value in (None, "unauthorized"):
        with pytest.raises(HypitIntegrationError, match="frozen D1 policy"):
            service.update_film_attempt(current["attempt_id"], event="d1_guard_probe",
                                        creative_claim_policy=value)
    with pytest.raises(HypitIntegrationError, match="frozen D1 policy"):
        service.update_film_attempt(legacy["attempt_id"], event="d1_guard_probe",
                                    creative_claim_policy=OWNER_POLICY)
    # Also cover lower-level callback mutation, not only the public update wrapper.
    with pytest.raises(HypitIntegrationError, match="frozen D1 policy"):
        service._save_attempt(current["attempt_id"],
                              lambda item: {k: v for k, v in item.items()
                                            if k != "creative_claim_policy"})
    def tamper_in_place(item):
        item.pop('creative_claim_policy', None)
        return item
    with pytest.raises(HypitIntegrationError, match='frozen D1 policy'):
        service._save_attempt(current['attempt_id'], tamper_in_place)
    assert service.get_film_attempt(current["attempt_id"]) == frozen_before
    assert service.get_film_attempt(legacy["attempt_id"]) == legacy_before


def test_native_d1_claim_owner_and_frozen_verify(material_integration_env, tmp_path):
    attempt = _new_frozen_d1_attempt(material_integration_env)
    root = Path(attempt["workspace"]["path"])
    _, manifest, _ = handoff.resolve_handoff(
        attempt["creation_id"], attempt["handoff"]["handoff_id"])
    handoff_root = root / "handoff"
    inputs = {key: json.loads((handoff_root / value["path"]).read_text())
              for key, value in (("content_core", manifest["content"]["content_core"]),
                                 ("truth_packet", manifest["content"]["truth_packet"]),
                                 ("creator_context", manifest["creator_context"]))}
    refs = {
        "content_core_sha256": manifest["content"]["content_core"]["hash"],
        "truth_packet_sha256": manifest["content"]["truth_packet"]["hash"],
        "creator_context_sha256": manifest["creator_context"]["hash"],
        "production_brief_sha256": manifest["production_request"]["production_brief_sha256"],
        "creative_mode_sha256": manifest["creative_mode"]["hash"]}
    result = _current_vnext_planning_executor(
        attempt, {**inputs, "context_refs": refs}, creative_claims=True)
    journal = AttemptMaterialStore(root).read_recovery_record("semantic-planning-vnext")
    checkpoint_path = root / "planning" / "SEMANTIC_CHECKPOINT.json"
    checkpoint = json.loads(checkpoint_path.read_text())
    assert checkpoint["scope"]["creative_authority"]["policy"] == OWNER_POLICY
    assert checkpoint["creative_claims"]["policy"] == OWNER_POLICY
    assert checkpoint["creative_claims"]["headers"]
    assert checkpoint["creative_claims"]["conditions"]
    assert journal["creative_claims"] == checkpoint["creative_claims"]
    assert set(journal["calls"]) == set(checkpoint["wire_originals"])
    assert all("claim" in checkpoint["wire_originals"][key]
               for key in journal["calls"] if key == "A-selection" or key.startswith("A-details"))
    replayed = semantic_boundary_run.verify(
        root, result["plan"], checkpoint["scope"]["mode"], result["script"], attempt=attempt)
    assert replayed["policy"] == semantic_boundary_run.POLICY

    clone = tmp_path / "cold"
    shutil.copytree(root, clone, symlinks=True)
    copy_attempt = deepcopy(attempt)
    copy_attempt["workspace"]["path"] = str(clone)
    assert semantic_boundary_run.verify(
        clone, result["plan"], checkpoint["scope"]["mode"],
        result["script"], attempt=copy_attempt)["policy"] == semantic_boundary_run.POLICY
    mismatched_attempt = {**copy_attempt, 'creative_claim_policy': None}
    with pytest.raises(ValueError, match='D1 Checkpoint and frozen Attempt policy differ'):
        semantic_boundary_run.verify(
            clone, result['plan'], checkpoint['scope']['mode'],
            result['script'], attempt=mismatched_attempt)
    artifact = clone / "planning" / "SEMANTIC_CHECKPOINT.json"
    tampered = json.loads(artifact.read_text())
    tampered["creative_claims"]["headers"]["needs/0/header"]["claim"]["reason"] += " altered"
    artifact.write_text(json.dumps(tampered, ensure_ascii=False))
    with pytest.raises(ValueError):
        semantic_boundary_run.verify(clone, result["plan"], checkpoint["scope"]["mode"],
            result["script"], attempt=copy_attempt)


def test_native_d1_semantic_repair_forces_b_recheck(material_integration_env):
    attempt = _new_frozen_d1_attempt(material_integration_env)
    root = Path(attempt["workspace"]["path"])
    _, manifest, _ = handoff.resolve_handoff(
        attempt["creation_id"], attempt["handoff"]["handoff_id"])
    handoff_root = root / "handoff"
    inputs = {key: json.loads((handoff_root / value["path"]).read_text())
              for key, value in (("content_core", manifest["content"]["content_core"]),
                                 ("truth_packet", manifest["content"]["truth_packet"]),
                                 ("creator_context", manifest["creator_context"]))}
    refs = {
        "content_core_sha256": manifest["content"]["content_core"]["hash"],
        "truth_packet_sha256": manifest["content"]["truth_packet"]["hash"],
        "creator_context_sha256": manifest["creator_context"]["hash"],
        "production_brief_sha256": manifest["production_request"]["production_brief_sha256"],
        "creative_mode_sha256": manifest["creative_mode"]["hash"]}
    result = _current_vnext_planning_executor(
        attempt, {**inputs, "context_refs": refs},
        creative_claims=True, creative_semantic_probe=True)
    journal = AttemptMaterialStore(root).read_recovery_record("semantic-planning-vnext")
    checkpoint = json.loads((root / "planning" / "SEMANTIC_CHECKPOINT.json").read_text())
    assert journal["repair_used"] is True
    assert "repair" in journal["calls"]
    assert any(key.startswith("B-recheck-") for key in journal["calls"])
    assert checkpoint["creative_claims"]["repair_evidence"]["decision"] == "PENDING_B_REVIEW"
    assert checkpoint["creative_claims"]["headers"]["needs/0/header"]["claim"]
    assert semantic_boundary_run.verify(
        root, result["plan"], checkpoint["scope"]["mode"],
        result["script"], attempt=attempt)["policy"] == semantic_boundary_run.POLICY
    captured_before = {key: (call["request_sha256"], call["reply_sha256"], call["session"])
                       for key, call in journal["calls"].items()}
    recovered = _current_vnext_planning_executor(
        attempt, {**inputs, "context_refs": refs},
        creative_claims=True, creative_semantic_probe=True)
    assert recovered["plan"] == result["plan"]
    again = AttemptMaterialStore(root).read_recovery_record("semantic-planning-vnext")
    assert {key: (call["request_sha256"], call["reply_sha256"], call["session"])
            for key, call in again["calls"].items()} == captured_before
    assert again["repair_used"] is True
    from easel.creation_preparation import PreparationError
    forged = deepcopy(again)
    forged["creative_claims"]["headers"]["needs/0/header"]["claim"]["reason"] += " forged"
    AttemptMaterialStore(root).write_recovery_record("semantic-planning-vnext", forged)
    with pytest.raises(PreparationError, match="Persisted D1 repaired Claim differs"):
        _current_vnext_planning_executor(
            attempt, {**inputs, "context_refs": refs},
            creative_claims=True, creative_semantic_probe=True)


def test_native_d1_checkpoint_write_failure_reuses_original_operations(
        material_integration_env, monkeypatch):
    from easel.creation_preparation import PreparationError
    attempt = _new_frozen_d1_attempt(material_integration_env)
    root = Path(attempt["workspace"]["path"])
    _, manifest, _ = handoff.resolve_handoff(
        attempt["creation_id"], attempt["handoff"]["handoff_id"])
    handoff_root = root / "handoff"
    inputs = {key: json.loads((handoff_root / value["path"]).read_text())
              for key, value in (("content_core", manifest["content"]["content_core"]),
                                 ("truth_packet", manifest["content"]["truth_packet"]),
                                 ("creator_context", manifest["creator_context"]))}
    refs = {
        "content_core_sha256": manifest["content"]["content_core"]["hash"],
        "truth_packet_sha256": manifest["content"]["truth_packet"]["hash"],
        "creator_context_sha256": manifest["creator_context"]["hash"],
        "production_brief_sha256": manifest["production_request"]["production_brief_sha256"],
        "creative_mode_sha256": manifest["creative_mode"]["hash"]}
    context = {**inputs, "context_refs": refs}
    writer = semantic_boundary_run.write_file
    fail = {"once": True}

    def interrupted_write(root_path, name, data):
        if name == "SEMANTIC_CHECKPOINT.json" and fail["once"]:
            fail["once"] = False
            raise OSError("injected d1 checkpoint storage interruption")
        return writer(root_path, name, data)

    monkeypatch.setattr(semantic_boundary_run, "write_file", interrupted_write)
    with pytest.raises(PreparationError, match="injected d1 checkpoint"):
        _current_vnext_planning_executor(
            attempt, context, creative_claims=True, creative_semantic_probe=True)
    before = AttemptMaterialStore(root).read_recovery_record("semantic-planning-vnext")
    assert before["publication_result"] == "PERSIST_FAILED"
    assert before["repair_used"]
    assert "repair" in before["calls"]
    assert any(key.startswith("B-recheck") for key in before["calls"])
    frozen_calls = deepcopy(before["calls"])
    result = _current_vnext_planning_executor(
        attempt, context, creative_claims=True, creative_semantic_probe=True)
    after = AttemptMaterialStore(root).read_recovery_record("semantic-planning-vnext")
    assert after["publication_result"] == "ACCEPTED"
    assert after["calls"] == frozen_calls
    checkpoint = json.loads((root / "planning" / "SEMANTIC_CHECKPOINT.json").read_text())
    assert semantic_boundary_run.verify(
        root, result["plan"], checkpoint["scope"]["mode"], result["script"],
        attempt=attempt)["policy"] == semantic_boundary_run.POLICY



