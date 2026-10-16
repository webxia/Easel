"""P0 real MiniMax A source/creative-basis regression; original evidence immutable.

No live model calls. Archived failed wire is intentionally NOT accepted under the
new version; semantic-only counterfactual demonstrates the actual responsibility
split without rewriting a single original receipt or granting B authorization.
"""
import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import ValidationError

from easel.integrations import semantic_boundary_run as owner
from easel.integrations import planning_creative_authority as creative
from easel.integrations import planning_input_view as view_module
from easel.integrations import planning_staged_proposal as staged
from easel.integrations.planning_authority import digest

EVIDENCE = (Path.home() / ".local/share/easel/creator-task-evidence"
            / "2026-10-15-planning-m31-actual-owner-eval-r01/live")
ORIGINAL_SHA = "237817c9d3e1a746fb105513d6a04c1f9f3e38cef2ccf45ceb920a55c5da3951"


@pytest.fixture
def archived_a():
    candidates = list((EVIDENCE / "eval-runtime/hypit/workspaces").glob(
        "*/*/materials/recoveries/semantic-planning-vnext.json"))
    if not candidates:
        pytest.skip("Original real MiniMax evidence not mounted; synthetic D1 regression still runs")
    assert len(candidates) == 1
    path = candidates[0]
    before = path.read_bytes()
    journal = json.loads(before)
    raw = journal["calls"]["A-selection"]["reply"]
    assert hashlib.sha256(raw.encode()).hexdigest() == ORIGINAL_SHA
    assert journal["calls"]["A-selection"]["reply_sha256"] == ORIGINAL_SHA
    scope = journal["scope"]
    view = view_module.PlanningInputView(scope["inputs"], scope["catalog"])
    assert view.snapshot() == journal["input_view_snapshot"]
    codec = staged._read_only_staged(owner.query_schema(scope))
    bridge = creative.OpaqueHeaderBridge(
        view.codec, codec, scope["creative_authority"]["envelope"])
    original = json.loads(raw)
    projected = deepcopy(original)
    for need in projected["needs"]:
        if need["modality"] in ("image", "video"):
            # These existed only because the OLD schema mistakenly asked the
            # model to fabricate a SHA / echo mechanical Need state.
            need["header_claim"].pop("claimed_necessity")
            need["header_claim"].pop("continuity_choices_sha256")
    yield bridge, original, projected, scope
    assert path.read_bytes() == before
    assert hashlib.sha256(journal["calls"]["A-selection"]["reply"].encode()).hexdigest() == ORIGINAL_SHA


def test_real_original_old_wire_is_not_silently_upgraded(archived_a):
    bridge, original, projected, scope = archived_a
    with pytest.raises(ValidationError):
        bridge.decode(original, bridge.identity)
    # Only the current *new-version* semantic subset is a legal A candidate.
    selection, headers = bridge.decode(projected, bridge.identity)
    assert len(selection["needs"]) == 11
    assert len(headers) == 7
    assert all(headers[f"needs/{i}/header"]["need_source_ref"] == f"event-{i+4}"
               for i in range(7))
    assert all(headers[f"needs/{i}/header"]["claim"]["creative_goal_ref"] == "global"
               for i in range(7))
    assert all(headers[f"needs/{i}/header"]["claim"]["continuity_choices_sha256"] == digest([])
               for i in range(7))
    assert all("ACCEPT" not in str(headers[f"needs/{i}/header"]) for i in range(7))


def test_real_a_invalid_basis_and_model_forged_sha_are_rejected(archived_a):
    bridge, original, projected, scope = archived_a
    bad = deepcopy(projected)
    bad["needs"][0]["header_claim"]["creative_goal_ref"] = "src_ffffffffffffffffffff"
    with pytest.raises(ValidationError):
        bridge.decode(bad, bridge.identity)
    bad = deepcopy(projected)
    bad["needs"][0]["header_claim"]["continuity_choices_sha256"] = "f" * 64
    with pytest.raises(ValidationError):
        bridge.decode(bad, bridge.identity)
    bad = deepcopy(projected)
    bad["needs"][0]["header_claim"]["claimed_necessity"] = "optional"
    with pytest.raises(ValidationError):
        bridge.decode(bad, bridge.identity)
    with pytest.raises(ValueError, match="identity"):
        bridge.decode(projected, {**bridge.identity, "policy": "old-unverified"})


def test_real_a_creative_basis_and_need_location_independently_invalidate_b(archived_a):
    bridge, original, projected, scope = archived_a
    selection, headers = bridge.decode(projected, bridge.identity)
    changed = deepcopy(projected)
    changed["needs"][0]["header_claim"]["creative_goal_ref"] = changed["needs"][0]["scope"]
    rewritten, changed_headers = bridge.decode(changed, bridge.identity)
    assert rewritten == selection
    assert headers["needs/0/header"]["need_source_ref"] == changed_headers["needs/0/header"]["need_source_ref"]
    assert headers["needs/0/header"]["claim"]["creative_goal_ref"] != changed_headers["needs/0/header"]["claim"]["creative_goal_ref"]
    assert headers["needs/0/header"]["record_sha256"] != changed_headers["needs/0/header"]["record_sha256"]
    from easel.integrations.planning_creative_authority import bind_review_claims
    q = {"question": 0, "kind": "visual_choices", "target": [0],
         "candidate": {"role": selection["needs"][0]["role"]}}
    first = bind_review_claims({"questions": [q]}, envelope=scope["creative_authority"]["envelope"],
                               conditions={}, headers=headers)
    second = bind_review_claims({"questions": [q]}, envelope=scope["creative_authority"]["envelope"],
                                conditions={}, headers=changed_headers)
    assert first["questions"][0]["creative_dependency"] != second["questions"][0]["creative_dependency"]
    # Prior B acceptance cannot be inherited from a different model basis.
    from easel.integrations.planning_semantic_review import recheck
    from easel.integrations.planning_result_contract import ReviewResponse
    mock_review = [ReviewResponse.model_validate({"answers": [
        {"question": 0, "decision": "ACCEPT", "reason": "previous basis", "evidence": [0]}]})]
    accepted, pending = recheck(first, mock_review, second)
    assert not accepted and len(pending["questions"]) == 1
