"""D1 extended OFFLINE-only Header/Repair/Cold-proof regression.

No original R02 Attempt writes, model calls, production Owner integration or
Material Domain change. The new Claim is unreviewed, not a DecisionProof.
"""
from copy import deepcopy
import json

import pytest
from jsonschema import ValidationError

from easel.integrations import planning_candidate_review
from easel.integrations.planning_creative_authority import (
    VisualHeaderClaimCarrier, ExtendedSharedRepairCarrier,
    freeze_offline_receipt, verify_offline_receipt, digest,
)
from tests.test_planning_creative_authority_d1_prototype import _setup, _claim
from tests.test_material_integration import material_integration_env


def _header_claim(need, *, reason="只属于本片的具体镜头安排，等待独立 B 审查"):
    return {
        "claimed_kind": "director_local_choice",
        "creative_goal_ref": need["scope"],
        "reason": reason,
        "claimed_necessity": need["necessity"],
        "continuity_choices_sha256": digest(need["continuity_choices"]),
    }


def _wire_header_claim(need):
    """Repair model writes only creative decisions; Program binds header SHA."""
    return {k: v for k, v in _header_claim(need).items()
            if k in ("claimed_kind", "creative_goal_ref", "reason")}


def _setup_header(material_integration_env, monkeypatch):
    env, details_carrier, raw, original, details, condition_claims = _setup(
        material_integration_env, monkeypatch)
    staged = details_carrier.staged
    selection = staged.encode(original)[0]
    header = VisualHeaderClaimCarrier(staged, env)
    header_wire = header.encode(selection, {
        f"needs/{i}/header": _header_claim(need)
        for i, need in enumerate(selection["needs"]) if need["modality"] in {"image", "video"}
    })
    decoded, header_claims = header.decode(header_wire, header.identity)
    assert decoded == selection
    return env, header, header_wire, original, condition_claims, header_claims


def test_d1_visual_header_captures_necessity_and_continuity_no_authorization(material_integration_env, monkeypatch):
    env, header, raw, original, conds, headers = _setup_header(material_integration_env, monkeypatch)
    assert len(headers) == 1 and "needs/0/header" in headers
    assert headers["needs/0/header"]["header_sha256"] == digest(
        {k: original["needs"][0][k] for k in ("scope", "role", "modality", "necessity", "continuity_choices")})
    assert "ACCEPT" not in str(headers)
    assert "header_claim" not in str(original)
    assert len(header.encode(header.decode(raw, header.identity)[0], {
        "needs/0/header": headers["needs/0/header"]["claim"],
    })["needs"]) == 1
    assert header.identity["envelope_scope_ref"] == env["scope_ref"]


@pytest.mark.parametrize("bad", ["missing", "unknown", "scope", "continuity", "necessity", "short_reason",
                                  "self_derived", "extra_root", "old_policy"])
def test_d1_visual_header_illegal_claim_fail_closed(material_integration_env, monkeypatch, bad):
    env, header, wire, original, conds, headers = _setup_header(material_integration_env, monkeypatch)
    broken = deepcopy(wire)
    claim = broken["needs"][0]["header_claim"]
    if bad == "missing":
        del broken["needs"][0]["header_claim"]
    elif bad == "unknown":
        claim["owner_permission"] = "granted"
    elif bad == "scope":
        claim["creative_goal_ref"] = "scene-999"
    elif bad == "continuity":
        claim["continuity_choices_sha256"] = "0" * 64
    elif bad == "necessity":
        claim["claimed_necessity"] = "optional"
    elif bad == "short_reason":
        claim["reason"] = "短"
    elif bad == "self_derived":
        claim["claimed_kind"] = "program_derived"
    elif bad == "extra_root":
        broken["claimed_permission"] = "REAL"
    elif bad == "old_policy":
        with pytest.raises(ValueError):
            header.decode(broken, {**header.identity, "policy": "old"})
        return
    with pytest.raises((ValueError, ValidationError)):
        header.decode(broken, header.identity)


def _mixed(material_integration_env, monkeypatch, target_kind):
    env, header, raw, original, conditions, headers = _setup_header(
        material_integration_env, monkeypatch)
    need = deepcopy(original["needs"][0])
    if target_kind == "complete_obligation":
        target = {"kind": target_kind, "path": [0, 1], "issue": "独立 B 需重新审查条件"}
        replacement = deepcopy(need["conditions"][1])
        replacement["text"] = "画面停顿与阅读节奏与本片的构图保持协调"
        wire = {"target-0000": {"value": replacement, "authority": {
            "header_claim": None,
            "condition_claims": [_claim("creative_preference", "preference",
                                        reason="本片以轻微停顿引导观众回到所观察的问题")]}}}
    elif target_kind == "visual_choices":
        target = {"kind": target_kind, "path": [0], "issue": "视觉头部需要导演决定"}
        replacement = deepcopy(need)
        replacement["role"] = "同一片内的静态开场镜头"
        wire = {"target-0000": {"value": replacement, "authority": {
            "header_claim": _wire_header_claim(replacement),
            "condition_claims": [
                _claim("director_local_choice", cond["strength"],
                       reason="本次视觉选择为已确认表达服务，事实是否支持另由 B 独立核验")
                for cond in replacement["conditions"]]}}}
    elif target_kind == "frozen_visual_coverage":
        target = {"kind": target_kind, "path": ["scene-1"], "issue": "真实视觉遗漏待 B 审核"}
        replacement = deepcopy(need)
        replacement["role"] = "补足缺失的不同视觉镜头"
        wire = {"target-0000": {"value": replacement, "authority": {
            "header_claim": _wire_header_claim(replacement),
            "condition_claims": [
                _claim("director_local_choice", cond["strength"],
                       reason="新视觉镜头候选，仅允许经现有 B 审核后进入正式计划")
                for cond in replacement["conditions"]]}}}
    else:
        raise AssertionError(target_kind)
    carrier = ExtendedSharedRepairCarrier(env, original, [target], conditions, headers)
    return carrier, wire, original, conditions, headers


@pytest.mark.parametrize("kind", ["complete_obligation", "visual_choices", "frozen_visual_coverage"])
def test_d1_visual_repair_kinds_are_atomic_and_recheck(material_integration_env, monkeypatch, kind):
    carrier, wire, original, conditions, headers = _mixed(
        material_integration_env, monkeypatch, kind)
    result, new_conds, new_headers, receipt = carrier.apply(wire, carrier.identity)
    assert receipt["decision"] == "PENDING_B_REVIEW"
    assert receipt["recheck_required"]
    assert receipt["condition_claims_sha256"] == digest(new_conds)
    assert receipt["header_claims_sha256"] == digest(new_headers)
    assert carrier.apply(wire, carrier.identity) == (result, new_conds, new_headers, receipt)
    if kind == "complete_obligation":
        assert result["needs"][0]["conditions"][0] == original["needs"][0]["conditions"][0]
        assert new_conds["needs/0/conditions/1"] != conditions["needs/0/conditions/1"]
        assert new_headers == headers
    elif kind == "visual_choices":
        assert result["needs"][0]["role"] != original["needs"][0]["role"]
        assert result["needs"][0]["conditions"] == original["needs"][0]["conditions"]
        assert new_headers["needs/0/header"] != headers["needs/0/header"]
    else:
        assert len(result["needs"]) == len(original["needs"]) + 1
        assert result["needs"][0] == original["needs"][0]
        assert "needs/1/header" in new_headers
        assert set(new_conds) >= {"needs/1/conditions/0", "needs/1/conditions/1"}


@pytest.mark.parametrize("kind", ["complete_obligation", "visual_choices", "frozen_visual_coverage"])
@pytest.mark.parametrize("bad", ["missing_claims", "wrong_strength", "wrong_scene", "extra_slot", "changed_identity"])
def test_d1_visual_repair_rejects_unmapped_or_unapproved_claim(
        material_integration_env, monkeypatch, kind, bad):
    carrier, wire, original, conditions, headers = _mixed(
        material_integration_env, monkeypatch, kind)
    bad_wire = deepcopy(wire)
    authority = bad_wire["target-0000"]["authority"]
    if bad == "missing_claims":
        authority["condition_claims"].clear()
    elif bad == "wrong_strength":
        authority["condition_claims"][0]["claimed_strength"] = "preference" \
            if authority["condition_claims"][0]["claimed_strength"] == "required" else "required"
    elif bad == "wrong_scene":
        if kind == "complete_obligation":
            authority["condition_claims"][0]["creative_goal_ref"] = "scene-999"
        else:
            authority["header_claim"]["creative_goal_ref"] = "scene-999"
    elif bad == "extra_slot":
        bad_wire["target-0001"] = deepcopy(bad_wire["target-0000"])
    else:
        with pytest.raises(ValueError):
            carrier.apply(bad_wire, {**carrier.identity, "targets_sha256": "wrong"})
        return
    with pytest.raises((ValueError, ValidationError)):
        carrier.apply(bad_wire, carrier.identity)


def test_d1_confirmed_necessity_stays_program_derived_from_frozen_B(material_integration_env, monkeypatch):
    env, header, raw, original, conditions, headers = _setup_header(material_integration_env, monkeypatch)
    draft = deepcopy(original)
    draft["needs"][0]["necessity"] = "optional"
    old = deepcopy(headers)
    old["needs/0/header"]["header_sha256"] = digest({
        k: draft["needs"][0][k] for k in ("scope","role","modality","necessity","continuity_choices")})
    target = {"kind": "confirmed_necessity", "policy": planning_candidate_review.POLICY,
              "path": ["needs", 0, "necessity"], "old_value": "optional",
              "need_sha256": digest(draft["needs"][0]),
              "inputs_sha256": "test-frozen-input", "judgment": {"decision": "CHALLENGE"}}
    carrier = ExtendedSharedRepairCarrier(env, draft, [target], conditions, old)
    result, con, hdr, receipt = carrier.apply({"target-0000": "required"}, carrier.identity)
    assert result["needs"][0]["necessity"] == "required"
    assert hdr["needs/0/header"]["origin"] == "program_derived_from_frozen_B_necessity"
    assert hdr["needs/0/header"]["claim"] is None
    assert receipt["recheck_required"]
    for forbidden in ("optional", "unverified"):
        with pytest.raises((ValueError, ValidationError)):
            carrier.apply({"target-0000": forbidden}, carrier.identity)


def test_d1_b_answer_repair_preserves_original_schema_and_no_creative_claim(material_integration_env, monkeypatch):
    env, header, raw, original, conditions, headers = _setup_header(material_integration_env, monkeypatch)
    answer = {"decision": "ACCEPT", "reason": "原始模型回答", "support": []}
    schema = {"type": "object", "additionalProperties": False, "properties": {
        "decision": {"type":"string", "enum": ["ACCEPT","CHALLENGE","UNRESOLVED"]},
        "reason": {"type":"string", "minLength": 1, "maxLength": 512},
        "support": {"type":"array", "maxItems": 8, "items": {"type": "string", "maxLength": 30}}}, "required": ["decision","reason","support"]}
    target = {"kind": "candidate_answer", "policy": planning_candidate_review.POLICY,
              "path": ["question-0000"], "old_sha256": digest(answer),
              "answer_schema": schema, "answer_defs": {}}
    carrier = ExtendedSharedRepairCarrier(env, {"question-0000": answer}, [target], {}, {})
    reply = {"target-0000": {"decision": "CHALLENGE", "reason": "该题需独立证据", "support": []}}
    result, con, hdr, receipt = carrier.apply(reply, carrier.identity)
    assert result["question-0000"]["decision"] == "CHALLENGE"
    assert not con and not hdr
    assert "authority" not in carrier.schema["properties"]["target-0000"]


def test_d1_header_audio_branch_keeps_original_contract(material_integration_env, monkeypatch):
    env, header, wire, original, conditions, headers = _setup_header(material_integration_env, monkeypatch)
    selection = deepcopy(header.staged.encode(original)[0])
    selection["needs"].append({"scope": "global", "role": "背景音乐", "modality": "bgm",
                               "necessity": "required", "continuity_choices": []})
    wrapped = header.encode(selection, {"needs/0/header": _header_claim(selection["needs"][0])})
    restored, records = header.decode(wrapped, header.identity)
    assert restored == selection and len(records) == 1
    wrapped["needs"][1]["header_claim"] = _header_claim(selection["needs"][1])
    with pytest.raises((ValueError, ValidationError)):
        header.decode(wrapped, header.identity)


def test_d1_cold_header_details_and_repair_verify_from_frozen_bytes(material_integration_env, monkeypatch, tmp_path):
    from easel.integrations.planning_creative_authority import (
        VisualClaimCarrier, freeze_offline_receipt, verify_offline_receipt)
    env, header, wire, original, conditions, headers = _setup_header(
        material_integration_env, monkeypatch)
    frozen = freeze_offline_receipt(env, header.identity, wire,
                                    header.decode(wire, header.identity))
    file = tmp_path / "d1-header-cold.json"
    file.write_text(json.dumps(frozen, ensure_ascii=False))
    loaded = json.loads(file.read_text())
    rebuilt = VisualHeaderClaimCarrier(header.staged, env)
    assert verify_offline_receipt(loaded, env, rebuilt.identity, rebuilt.decode) == (
        header.decode(wire, header.identity))
    for field, changed in [
        ("policy", "older"), ("envelope_scope_ref", "other"),
        ("raw_tool_arguments", "malformed"), ("decoded_sha256", "other"),
        ("record_sha256", "other"),
    ]:
        altered = deepcopy(loaded)
        altered[field] = changed
        with pytest.raises((ValueError, ValidationError)):
            verify_offline_receipt(altered, env, rebuilt.identity, rebuilt.decode)
    other_identity = {**rebuilt.identity, "wire_schema_sha256": "different"}
    with pytest.raises(ValueError):
        verify_offline_receipt(loaded, env, other_identity, rebuilt.decode)
    # Repair bytes and decision claims are also frozen, not inferred on load.
    repair, raw_repair, _, _, _ = _mixed(material_integration_env, monkeypatch, "visual_choices")
    receipt = freeze_offline_receipt(repair.envelope, repair.identity, raw_repair,
                                     repair.apply(raw_repair, repair.identity))
    repair_file = tmp_path / "d1-repair-cold.json"
    repair_file.write_text(json.dumps(receipt, ensure_ascii=False))
    reconstructed = ExtendedSharedRepairCarrier(
        repair.envelope, repair.original, repair.targets,
        repair.condition_claims, repair.header_claims)
    assert verify_offline_receipt(
        json.loads(repair_file.read_text()), repair.envelope,
        reconstructed.identity, reconstructed.apply) == repair.apply(
            raw_repair, repair.identity)


def test_d1_confirmed_necessity_rejects_swapped_header_evidence(material_integration_env, monkeypatch):
    env, header, raw, original, conditions, headers = _setup_header(
        material_integration_env, monkeypatch)
    optional = deepcopy(original)
    optional["needs"][0]["necessity"] = "optional"
    target = {"kind": "confirmed_necessity", "policy": planning_candidate_review.POLICY,
              "path": ["needs", 0, "necessity"], "old_value": "optional",
              "need_sha256": digest(optional["needs"][0]), "inputs_sha256": "frozen",
              "judgment": {"decision": "CHALLENGE"}}
    # Original Header record is for a required Need, not this optional Need.
    with pytest.raises(ValueError, match="Header identity"):
        ExtendedSharedRepairCarrier(env, optional, [target], conditions, headers)


def test_d1_existing_audio_music_repair_does_not_gain_director_claim(material_integration_env, monkeypatch):
    env, header, raw, original, conditions, headers = _setup_header(
        material_integration_env, monkeypatch)
    target = {"kind": "confirmed_music_coverage", "path": ["bgm"],
              "issue": "Frozen confirmed sound requires background music"}
    carrier = ExtendedSharedRepairCarrier(env, original, [target], conditions, headers)
    value = {"scope": "global", "role": "背景音乐", "modality": "bgm",
             "necessity": "required", "continuity_choices": [],
             "conditions": [{"text": "来自冻结方案的轻柔无歌词音乐",
                             "strength": "required", "responsibility": "material"}],
             "sound": {"mood": "柔和", "vocals_allowed": False}}
    result, cond, hdr, receipt = carrier.apply({"target-0000": value}, carrier.identity)
    assert result["needs"][-1]["modality"] == "bgm"
    assert cond == conditions and hdr == headers
    assert "authority" not in carrier.schema["properties"]["target-0000"]
    assert receipt["recheck_required"]
    with pytest.raises((ValueError, ValidationError)):
        carrier.apply({"target-0000": {**value, "authority": {"granted": True}}}, carrier.identity)


def test_d1_visual_structural_leaf_requires_a_new_claim_not_value_only(material_integration_env, monkeypatch):
    from typing import Annotated
    from pydantic import Field
    env, header, raw, original, conditions, headers = _setup_header(
        material_integration_env, monkeypatch)
    target = {"kind": "structural_leaf", "path": ["needs", 0, "role"],
              "annotation": Annotated[str, Field(min_length=1, max_length=200)],
              "issue": "Original malformed model leaf"}
    with pytest.raises(ValueError, match="new Claim"):
        ExtendedSharedRepairCarrier(env, original, [target], conditions, headers)


def test_d1_cold_receipt_recomputed_digest_cannot_approve_new_claim(material_integration_env, monkeypatch):
    from easel.integrations.planning_creative_authority import (
        freeze_offline_receipt, verify_offline_receipt)
    env, header, wire, original, conditions, headers = _setup_header(
        material_integration_env, monkeypatch)
    record = freeze_offline_receipt(env, header.identity, wire, header.decode(wire, header.identity))
    changed = deepcopy(record)
    payload = json.loads(changed["raw_tool_arguments"])
    payload["needs"][0]["header_claim"]["creative_goal_ref"] = "scene-999"
    changed["raw_tool_arguments"] = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    changed["record_sha256"] = digest({k:v for k,v in changed.items() if k != "record_sha256"})
    with pytest.raises((ValueError, ValidationError)):
        verify_offline_receipt(changed, env, header.identity, header.decode)

