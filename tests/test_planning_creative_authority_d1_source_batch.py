"""D1 read-only integration against current SourceSelection, staged batches and journal verifier.

No changes to production Owner, canonical Material contracts or historical evidence.
"""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from jsonschema import ValidationError

from easel.integrations.planning_input_view import SourceSelection
from easel.integrations.planning_creative_authority import (
    OpaqueHeaderBridge, BatchedVisualClaimCarrier, VisualClaimCarrier, digest)
from easel.integrations.planning_result_contract import semantic_tool_schema
from easel.integrations.planning_staged_proposal import StagedProposal
from easel.integrations.semantic_planning import source_catalog
from tests.test_material_integration import material_integration_env
from tests.test_planning_creative_authority_d1_prototype import _setup, _claim
from tests.test_planning_creative_authority_d1_extended import _header_claim


def _five(material_integration_env, monkeypatch):
    env, prior, _, first, _, _ = _setup(material_integration_env, monkeypatch)
    catalog = {"global": {"global": "0–15 秒：冻结画面"},
               "scene": {"scene-1": "0–15 秒：冻结画面"},
               "segment": {"segment-1": "0–15 秒：冻结画面"},
               "event": {"event-1": "0–15 秒：冻结画面"},
               "continuity": {}}
    # Preserve exactly the source domain actually confirmed by the test
    # Handoff. The producer and SourceSelection use the same original builder.
    from tests.test_planning_creative_authority_d0 import CONTENTS
    from easel.integrations import planning_authority
    assert "scene-1" in env["source_refs"]["scene"]
    orig_need = first["needs"][0]
    five = {"needs": [{**deepcopy(orig_need), "role": f"镜头 {i+1}"}
                      for i in range(5)], "unresolved": []}
    # The existing staged compiler must be derived from real confirmed source
    # references, not from the above illustration catalog.
    catalog = source_catalog(
        {"SCENES.md": CONTENTS[0][2].join(["0–15 秒：", ""]),
         "SCRIPT.md": CONTENTS[0][1], "TREATMENT.md": "从观察入手"},
        {"creator_context": {"voice": {}}, "proposal": None})
    staged = StagedProposal(semantic_tool_schema(catalog, compiled=True))
    selection, details, _ = staged.encode(five)
    source_codec = SourceSelection(staged.union.canonical, catalog)
    bridge = OpaqueHeaderBridge(source_codec, staged, env)
    header_claims = {f"needs/{i}/header": _header_claim(n)
                     for i, n in enumerate(selection["needs"])}
    raw_header = bridge.encode(selection, header_claims)
    restored, header_records = bridge.decode(raw_header, bridge.identity)
    assert restored == selection and len(header_records) == 5
    assert all(n["scope"].startswith("src_") for n in raw_header["needs"])
    assert all(n["scope"] == "scene-1" for n in restored["needs"])
    details_carrier = VisualClaimCarrier(staged, selection, env)
    claims = {f"needs/{i}/conditions/{j}": _claim(
        "creative_preference" if cond["strength"] == "preference" else "director_local_choice",
        strength=cond["strength"], scope=selection["needs"][i]["scope"],
        reason="本片冻结镜头的局部导演选择仍待独立 B 复核")
        for i, need in enumerate(five["needs"]) for j, cond in enumerate(need["conditions"])}
    all_detail_wire = details_carrier.encode(details, claims)
    batches = BatchedVisualClaimCarrier(
        staged, selection, env, source_bridge_identity=bridge.identity,
        source_codec=bridge.source_codec)
    raw_batches = batches.split(all_detail_wire)
    assert list(raw_batches) == ["A-details-000", "A-details-001"]
    return bridge, raw_header, batches, raw_batches, five, header_records


def test_d1_real_src_opaque_header_and_four_slot_batches(material_integration_env, monkeypatch, tmp_path):
    bridge, wire, batches, replies, five, headers = _five(material_integration_env, monkeypatch)
    result, claims, snapshot = batches.merge(replies, batches.identity)
    assert len(result["needs"]) == 5 and len(claims) == 10
    assert [len(batch["slots"]) for batch in replies.values()] == [4, 1]
    assert len(snapshot["original_batch_sha256"]) == 2
    from easel.integrations.planning_result_contract import SemanticProposal
    underlying = batches.staged.assemble_batches_candidate(
        batches.selection, batches.plan,
        {name: {"slots": {k: {**v, "conditions": [
            {a: b for a,b in condition.items() if a != "claim"}
            for condition in v["conditions"]]} for k, v in row["slots"].items()},
                "unresolved": row["unresolved"]} for name,row in replies.items()})
    assert result == SemanticProposal.model_validate(underlying).model_dump(mode="json")
    # Stored bytes, not in-memory object identity, reconstruct the A batch.
    root = tmp_path / "cold"
    root.mkdir()
    for name, value in replies.items():
        (root / (name + ".json")).write_text(
            json.dumps(value, ensure_ascii=False, sort_keys=True))
    (root / "checkpoint.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, sort_keys=True))
    rebuilt = BatchedVisualClaimCarrier(
        batches.staged, batches.selection, bridge.canonical.envelope,
        source_bridge_identity=bridge.identity,
        source_codec=bridge.source_codec)
    replay = {name: json.loads((root / (name + ".json")).read_text())
              for name in replies}
    checkpoint = json.loads((root / "checkpoint.json").read_text())
    assert rebuilt.verify_snapshot(replay, checkpoint, current_identity=rebuilt.identity) == (result, claims)


@pytest.mark.parametrize("fault", ["bad_handle", "cross_scope_claim", "drop_claim", "source_version", "duplicate_source"])
def test_d1_source_mapping_negative(material_integration_env, monkeypatch, fault):
    bridge, raw, batches, replies, five, headers = _five(material_integration_env, monkeypatch)
    broken = deepcopy(raw)
    if fault == "bad_handle":
        broken["needs"][0]["scope"] = "src_ffffffffffffffffffff"
    elif fault == "cross_scope_claim":
        broken["needs"][0]["header_claim"]["creative_goal_ref"] = broken["needs"][1]["scope"] + "bad"
    elif fault == "drop_claim":
        broken["needs"][0].pop("header_claim")
    elif fault == "source_version":
        with pytest.raises(ValueError):
            bridge.decode(broken, {**bridge.identity, "source_identity": {"policy": "old"}})
        return
    else:
        broken["needs"][0]["unknown_scope_evidence"] = "fabricated"
    with pytest.raises((ValueError, ValidationError)):
        bridge.decode(broken, bridge.identity)


@pytest.mark.parametrize("fault", ["missing_batch", "wrong_slot", "drop_claim", "wrong_ordinal",
                                  "edit_condition", "checkpoint_drift"])
def test_d1_multi_batch_fail_closed(material_integration_env, monkeypatch, fault):
    bridge, raw, batches, replies, five, headers = _five(material_integration_env, monkeypatch)
    canonical, claims, snapshot = batches.merge(replies, batches.identity)
    broken = deepcopy(replies)
    check = deepcopy(snapshot)
    if fault == "missing_batch":
        broken.pop("A-details-001")
    elif fault == "wrong_slot":
        broken["A-details-001"]["slots"]["slot_005"] = broken["A-details-001"]["slots"].pop("slot_004")
    elif fault == "drop_claim":
        broken["A-details-001"]["slots"]["slot_004"]["conditions"][0].pop("claim")
    elif fault == "wrong_ordinal":
        with pytest.raises(ValueError):
            batches.merge(broken, {**batches.identity, "selection_sha256": "wrong"})
        return
    elif fault == "edit_condition":
        broken["A-details-001"]["slots"]["slot_004"]["conditions"][0]["text"] += "篡改"
    else:
        check["original_batch_sha256"]["A-details-000"] = "wrong"
    with pytest.raises((ValueError, ValidationError)):
        batches.verify_snapshot(broken, check, current_identity=batches.identity)


def test_d1_real_owner_checkpoint_verify_unmodified_contract(material_integration_env, tmp_path):
    """Actual current Owner emits the Journal/Checkpoint and native verify reads it.

    It does *not* imply the D1 claim Policy is integrated into that checkpoint.
    """
    from tests.test_creation_preparation import _current_vnext_planning_executor
    from easel.integrations.hypit import handoff
    from easel.integrations import semantic_boundary_run
    from easel.materials.store import AttemptMaterialStore
    attempt = material_integration_env
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
    planning = _current_vnext_planning_executor(
        attempt, {**inputs, "context_refs": refs})
    checkpoint = AttemptMaterialStore(root).read_recovery_record("semantic-planning-vnext")
    assert checkpoint["schema"] == semantic_boundary_run.VIEW_JOURNAL
    assert checkpoint["scope"]["attempt_id"] == attempt["attempt_id"]
    assert checkpoint["calls"]["A-selection"]["reply_sha256"]
    # The original verifier reads the real official checkpoint (when emitted).
    raw = root / "planning" / "SEMANTIC_CHECKPOINT.json"
    assert raw.exists(), "Native Owner did not freeze a formal checkpoint"
    assert "planning-creative" not in raw.read_text()
    actual = semantic_boundary_run.verify(
        root, planning["plan"], checkpoint["scope"]["mode"],
        planning["script"], attempt=attempt)
    assert actual["policy"] == semantic_boundary_run.POLICY
    # Its frozen vNext journal already binds every A-details group and all
    # original stage wire versions, without adding a second operation budget.
    checkpoint_data = json.loads(raw.read_text())
    assert checkpoint_data["detail_binding"] == checkpoint["detail_binding"]
    assert checkpoint["detail_binding"]["input_view"] == checkpoint["scope"]["input_view"]
    a_keys = [key for key in checkpoint["calls"] if key.startswith("A-details-")]
    assert a_keys
    assert all(checkpoint["calls"][key]["reply_sha256"]
               for key in a_keys)
    assert all(checkpoint["schema_bindings"][key]
               for key in ["A-selection", *a_keys])
    from easel.integrations.planning_input_view import PlanningInputView
    reconstructed_view = PlanningInputView(
        checkpoint["scope"]["inputs"], checkpoint["scope"]["catalog"])
    assert checkpoint["input_view_snapshot"] == reconstructed_view.snapshot()

    # Validate the *real* owner verifier on an isolated byte-for-byte cold
    # workspace clone first; then only tamper that clone's checkpoint.
    import shutil
    copy_root = tmp_path / "official-cold-copy"
    shutil.copytree(root, copy_root, symlinks=True)
    independent = deepcopy(attempt)
    independent["workspace"]["path"] = str(copy_root)
    assert semantic_boundary_run.verify(
        copy_root, planning["plan"], checkpoint["scope"]["mode"],
        planning["script"], attempt=independent)["policy"] == semantic_boundary_run.POLICY
    copied_path = copy_root / "planning" / "SEMANTIC_CHECKPOINT.json"
    corrupted = json.loads(copied_path.read_text())
    corrupted["scope"]["context_refs"]["creative_mode_sha256"] = "sha256:" + "0" * 64
    copied_path.write_text(json.dumps(corrupted, ensure_ascii=False))
    with pytest.raises(ValueError):
        semantic_boundary_run.verify(
            copy_root, planning["plan"], checkpoint["scope"]["mode"],
            planning["script"], attempt=independent)
    # No edit to source Attempt, code, or legacy R02 checkpoint.

