"""D4: three distinct Content, same Creator/Mode, true native Owner software chain."""
import hashlib
import json
from pathlib import Path
from copy import deepcopy
import pytest

from easel import creative_mode
from easel.integrations.hypit import handoff, service
from easel.integrations import semantic_boundary_run, result_protocols
from easel.integrations.planning_creative_authority import OWNER_POLICY
from easel.integrations.planning_d2_typed_review import POLICY as D2_POLICY
from easel.integrations.material_layer import PlanningIntegration, MaterialGateIntegration, MaterialIntegrationError
from easel.materials.store import AttemptMaterialStore
from tests.test_material_integration import material_integration_env
from tests.test_creation_preparation import _current_vnext_planning_executor
from tests.test_planning_creative_authority_d0 import _confirmed_synthetic_attempt, CONTENTS


@pytest.mark.parametrize("index", range(3))
def test_d4_three_distinct_content_original_owner_through_truth_and_cold_load(
        material_integration_env, monkeypatch, index):
    root_modes = Path(__file__).resolve().parents[1] / "creative_modes"
    monkeypatch.setattr(creative_mode, "CREATIVE_MODES_DIR", root_modes)
    monkeypatch.setattr(handoff, "CREATIVE_MODES_DIR", root_modes, raising=False)
    legacy, ctx, canonical, confirmed, _ = _confirmed_synthetic_attempt(*CONTENTS[index])
    assert CONTENTS[index][1] in canonical['SCRIPT.md']
    assert CONTENTS[index][2] in canonical['SCENES.md']
    assert ctx['creator_context']['identity']['public_description'] == 'D0 合成测试创作者'
    attempt = service.create_film_attempt(
        legacy["creation_id"], legacy["handoff"]["handoff_id"],
        preparation_key=hashlib.sha256(f"d4-{index}".encode()).hexdigest(),
        runtime_status="NOT_CONFIGURED",
        result_protocols=result_protocols.inherited(legacy),
        creative_claim_policy=OWNER_POLICY, d2_review_policy=D2_POLICY)
    attempt = service.update_film_attempt(
        attempt["attempt_id"], event="planning_contract_registered", planning_contract_version=3)
    result = _current_vnext_planning_executor(
        attempt, ctx, creative_claims=True, d2_review=True)
    persisted = PlanningIntegration().persist(
        attempt, result["plan"], treatment=result["treatment"],
        script=result["script"], scenes=result["scenes"],
        script_assessment=result.get("script_assessment"))
    attempt = persisted["attempt"]
    ready = PlanningIntegration().load(service.get_film_attempt(attempt["attempt_id"]))
    assert ready["plan"] == result["plan"]
    assert ready["manifest"]["truth_result"]
    assert ready["truth_ledger"]["status"] == "PASSED"
    assert ready["plan"].context_refs == ctx["context_refs"]
    assert ready["consumer_contract"]["d2_proof_sha256"]
    assert ready["consumer_contract"]["readiness"] == "PLANNING_HANDOFF_ONLY"
    root = Path(attempt["workspace"]["path"])
    journal = AttemptMaterialStore(root).read_recovery_record("semantic-planning-vnext")
    assert any(k.startswith("A-details-") for k in journal["calls"])
    assert any(k.startswith("B-") for k in journal["calls"])
    assert (root / "planning/script-claims.json").exists()
    checkpoint = json.loads((root / "planning/SEMANTIC_CHECKPOINT.json").read_text())
    assert checkpoint["d2_decision_proof"]["reviews"]
    assert checkpoint["scope"]["inputs"]["confirmed"]["SCENES.md"] == canonical["SCENES.md"]
    assert checkpoint["scope"]["context_refs"] == ctx["context_refs"]
    assert checkpoint["scope"]["creative_authority"]["envelope"]["context"]["attempt_id"] == attempt["attempt_id"]
    assert not (root / "productions/easel-authoring/authors/main.svml").exists()
    assert semantic_boundary_run.verify(
        root, result["plan"], checkpoint["scope"]["mode"],
        result["script"], attempt=service.get_film_attempt(attempt["attempt_id"]))
    bad_attempt = {**attempt, 'attempt_id': 'fa_wrong_d4_content'}
    with pytest.raises(ValueError, match='Attempt|identity'):
        semantic_boundary_run.verify(
            root, result['plan'], checkpoint['scope']['mode'], result['script'],
            attempt=bad_attempt)
    wrong_mode = deepcopy(checkpoint['scope']['mode'])
    wrong_mode['visual_material_style'] = 'unconfirmed different Creative Mode'
    with pytest.raises(ValueError, match='Mode|mode|identity|context'):
        semantic_boundary_run.verify(
            root, result['plan'], wrong_mode, result['script'], attempt=attempt)
    before = {k: v["reply_sha256"] for k, v in journal["calls"].items()}
    _current_vnext_planning_executor(attempt, ctx, creative_claims=True, d2_review=True)
    after = AttemptMaterialStore(root).read_recovery_record("semantic-planning-vnext")
    assert {k: v["reply_sha256"] for k, v in after["calls"].items()} == before
    with pytest.raises(MaterialIntegrationError, match="MATERIAL_READY"):
        MaterialGateIntegration().assert_ready(service.get_film_attempt(attempt["attempt_id"]))
