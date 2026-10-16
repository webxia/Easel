"""D0 only: archived R02 frozen evidence and three isolated synthetic @4 works.

This is acceptance-fixture verification, NOT a new Director authority policy
or a replacement for B semantic review / D1 Claim + Proof.
No paid model, material provider, Hypit Build, or historical mutation.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from easel import creation, creative_mode
from easel.creator_proposal import validate_video_plan
from easel.creation_preparation import _canonical_bytes, _sha256
from easel.integrations import planning_authority
from easel.integrations.hypit import handoff, service
from tests.test_creation_preparation import _confirm_current_video_plan, VIDEO_PROPOSAL
from tests.test_material_integration import material_integration_env  # Reuse legitimate isolated @4 fixture


ARCHIVE = (Path.home() / ".local/share/easel/creator-task-evidence"
           / "2026-10-14-real-minimax-p0-medium-s5-r02")
RAW_MODE_SHA = "sha256:c8b997c24bb021bcfe1edf3e811f0d2860bb1078b5e7bdb220f4bce2314477e0"
JOURNAL_SHA = "1a193231ad50dd3e763b42d6f67b38260c6cf48716df6e7433179ae3e9b1c4e4"
# (number, question kind, target, original A candidate sha256,
#  real B decision, R02 raw request SHA, expected A strength / responsibility / meaning)
CASES = (
    (2, "complete_obligation", [0, 1], "4fe6ec03ec613a34b97a211a9453bb184edc617dbf408e0ca82a47fbe897e6c9", "CHALLENGE", "51632c97adf3451dece2d282b0b627555f33d223826b02a8df77b157d68fdbc1", "required", "material", "dynamic_action"),
    (4, "complete_obligation", [0, 3], "6b0f61f5a529cdd23285320b94a433d058bf81dbeccdc3ec604b2cf7e49b49fa", "CHALLENGE", "51632c97adf3451dece2d282b0b627555f33d223826b02a8df77b157d68fdbc1", "required", "material", "dynamic_action"),
    (7, "complete_obligation", [0, 6], "aa881fdfe14b6d14625e004fc1fa4f810f4ef4ae746884105b9531757bb5070d", "CHALLENGE", "51632c97adf3451dece2d282b0b627555f33d223826b02a8df77b157d68fdbc1", "preference", "material", "observable"),
    (34, "complete_obligation", [5, 0], "ee68eda19971c528401a97e594abd055bc51d3b10ea33cedcb782e122ed6eb2d", "CHALLENGE", "8d926ecbc8cc880ec606e1b4cdbaaf8f40feacc3a6bc4c22d397646783fba094", "required", "material", "observable"),
    (36, "complete_obligation", [5, 2], "592612cd45c8f0ab11dde8ab1448e6b309f72dc118e29db9dd710302be3a5ede", "CHALLENGE", "8d926ecbc8cc880ec606e1b4cdbaaf8f40feacc3a6bc4c22d397646783fba094", "required", "material", "observable"),
    (41, "complete_obligation", [6, 0], "7fbbbeb265fb07ac93c05e1d861e4e82c333ad1e39ce04e2e6c11a1ceda888b1", "UNRESOLVED", "3ad11764fb03492a4f0cb2e1d9e439392be6f81a2d8261e67e90c93a6e020b22", "required", "material", "observable"),
    (65, "unresolved_classification", [1], "0659ab41d92ed2381e6a2670a6d8eae508d386c3d879f5c4ea6425783ec079dd", "CHALLENGE", "b01e362dd38f3bef4a73de76ac461b124c6aa24d40e2e5b0ff06a50701bd26f6", None, None, None),
    (66, "unresolved_classification", [2], "30c03b8f8909a0bae955b8db8c1ba5c76b4d8a7fa141b5fc09c8698b09d97ec1", "CHALLENGE", "b01e362dd38f3bef4a73de76ac461b124c6aa24d40e2e5b0ff06a50701bd26f6", None, None, None),
    (68, "unresolved_classification", [4], "56a5089cfe856e347cca88872cfa22aa15061cf21a9813e17ce10352f37b4122", "CHALLENGE", "b01e362dd38f3bef4a73de76ac461b124c6aa24d40e2e5b0ff06a50701bd26f6", None, None, None),
)
EXPECTED_B_SHA = {
    "B-000": "ace6c88b8834899bcf7602384b80a76bf08bef9aaaf7db5a628c3318bcb24bdd",
    "B-004": "38246665c156a52f7b93b89122d9ee804bd03d0c8d94984b5aac69481f97eb3b",
    "B-005": "4f0b9750d05cdeac5c9f59c87a67ddaac54eb81f8d46c09031299bbf5b53e818",
    "B-008": "cce4af07df799602927f092f610cdfd8b3ae121d780b64557495e158b98d9718",
}


def digest(value):
    return planning_authority.digest(value)


@pytest.fixture(scope="module")
def frozen_r02():
    if not ARCHIVE.is_dir():
        pytest.skip("Private original R02 archive unavailable; never synthesize its model reply")
    matches = list((ARCHIVE / "live/eval-runtime/hypit/workspaces").glob(
        "*/*/materials/recoveries/semantic-planning-vnext.json"))
    assert len(matches) == 1
    path = matches[0]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == JOURNAL_SHA
    journal = json.loads(path.read_text())
    assert journal["scope"]["context_refs"]["creative_mode_sha256"] == RAW_MODE_SHA
    assert journal["scope"]["mode"]["version"] == "1.3"
    frozen_mode_documents = journal["scope"]["inputs"]["mode_documents"]
    assert json.loads(frozen_mode_documents["mode.json"]) == journal["scope"]["mode"]
    assert len(frozen_mode_documents) >= 5
    for call in journal["calls"].values():
        if call.get("result") == "MODEL_COMPLETED":
            assert hashlib.sha256(call["reply"].encode()).hexdigest() == call["reply_sha256"]

    requests = {}
    for request in (ARCHIVE / "live/requests").glob("*.json"):
        payload = json.loads(request.read_text())
        body = payload["messages"][-1]["content"]
        if "有界视觉复核" not in body:
            continue
        message = next(json.loads(line) for line in body.splitlines()
                       if line.startswith("{") and '"questions"' in line)
        sha = hashlib.sha256(request.read_bytes()).hexdigest()
        for question in message["questions"]:
            key = question["question"]
            assert key not in requests
            requests[key] = (question, message, sha)
    assert len(requests) == 72
    return journal, requests


@pytest.mark.parametrize("number,kind,target,value_sha,b_decision,request_sha,strength,responsibility,meaning", CASES,
                         ids=lambda v: str(v) if isinstance(v, int) else None)
def test_d0_nine_original_a_b_boundaries_and_tamper(
        frozen_r02, number, kind, target, value_sha, b_decision, request_sha,
        strength, responsibility, meaning):
    journal, requests = frozen_r02
    question, package, raw_request_sha = requests[number]
    assert question["kind"] == kind
    assert question["target"] == target
    assert raw_request_sha == request_sha
    value = question["candidate"]
    assert digest(value) == value_sha
    original_selection = json.loads(journal["calls"]["A-selection"]["reply"])
    details = [json.loads(journal["calls"][f"A-details-{i:03d}"]["reply"])
               for i in range(3)]
    if kind == "complete_obligation":
        actual_a = details[target[0] // 4]["slots"][f"slot_{target[0]:03d}"]["conditions"][target[1]]
        assert actual_a == value  # Link B request binding to original A raw bytes.
        assert original_selection["needs"][target[0]]["modality"] in {"image", "video"}
    else:
        reports = [*original_selection["unresolved"], *(row for batch in details for row in batch["unresolved"])]
        assert reports[target[0]] == value["report"]  # Original A report, not reconstructed B judgment.

    if kind == "complete_obligation":
        assert (value["strength"], value["responsibility"], value["meaning"]) == (
            strength, responsibility, meaning)
        actual = package["candidate_bindings"][f"candidate_{target[0]:03d}"]
        assert actual["value"]["conditions"][target[1]] == value
        assert actual["sha256"] == digest(actual["value"])
        assert question["selected_source"]["document_sha256"]
    else:
        assert not {"strength", "responsibility", "meaning", "text"} & value.keys()
        assert value["report_sha256"] == digest(value["report"])
        assert question.get("selected_source") is None
    altered = deepcopy(value)
    if kind == "complete_obligation":
        altered["strength"] = ("required" if strength == "preference" else "preference")
    else:
        altered["report"] += "伪造授权"
    assert digest(altered) != value_sha
    batch_key = f"B-{number // 8:03d}"
    raw = journal["calls"][batch_key]
    assert raw["reply_sha256"] == EXPECTED_B_SHA[batch_key]
    answers = json.loads(raw["reply"])["answers"]
    answer = next(row["answer"] for row in answers
                  if row["question_id"] == f"question-{number:04d}")
    assert answer["decision"] == b_decision
    assert answer["support"]
    # Literal sources are evidence eligibility; they are not entitlement.
    for support in answer["support"]:
        original = package["source_catalog"][support["source"]]
        assert support["role"] in original["roles"]
        if isinstance(original["value"], str):
            assert support["quote"] in original["value"]
        else:
            assert support["quote"] is None
    assert answer["decision"] != "ACCEPT"  # Historical truth is not relabeled.


CONTENTS = (
    ("AI 学习", "一次模型回答不能代表已经理解。", "桌面两张白纸记录提问与复核，不展示任何真实账号。"),
    ("工作实践", "复盘一个虚构的异常排查示例。", "抽象日志示例与手写时间线，没有真实客户数据。"),
    ("生活观察", "短途步行时观察光线的变化。", "路边静物与光影，没有可识别人物或住址。"),
)


def _proposal(script, scene):
    return VIDEO_PROPOSAL.replace(
        "先看问题，再做决定。", script).replace(
        "0–15 秒：桌面两张白纸，呈现后期叠加的屏幕文案「" + script + "」。",
        "0–15 秒：" + scene
    ).replace(
        "0–15 秒：桌面两张白纸，呈现后期叠加的屏幕文案「先看问题，再做决定。」。",
        "0–15 秒：" + scene)


def _confirmed_synthetic_attempt(theme, script, scene):
    work = creation.create_creation(
        "D0 合成测试：" + theme, profile="D0-测试创作者",
        creative_mode="clear_memo_video", route="hypit_video",
        origin={"type": "chat", "session_hash": hashlib.sha256(theme.encode()).hexdigest()})
    work = _confirm_current_video_plan(work, turn_id="d0-synthetic-" + hashlib.sha256(
        theme.encode()).hexdigest()[:8], proposal=_proposal(script, scene))
    confirmed = work["delivery"]["video_plan"]
    assert validate_video_plan(confirmed)
    assert script in confirmed["script"] and scene in confirmed["scenes"]
    brief = {"schema": "easel-production-brief@1", "language": "zh-CN",
             "duration_seconds": 15, "aspect_ratio": "9:16", "audio_mode": "silent",
             "beats": [], "text_overlays": [], "visual_constraints": [],
             "material_sources": [], "ai_generation_allowed": False,
             "publication_allowed": False}
    truth = {"schema": "easel-truth-packet@2", "claims": [], "personal_facts": [],
             "first_person_allowed": [], "public_allowed": [],
             "forbidden_inventions": ["不得把" + theme + "合成示例编造为本人经历"], "uncertainty_policy": {
                 "plan_is_not_experience": True,
                 "learning_is_not_proven_capability": True,
                 "unknown_claims": "label_uncertain"}}
    creator = {"schema": "easel-creator-context@1",
               "identity": {"public_description": "D0 合成测试创作者"},
               "audience": "测试观众", "voice": {"tone": "克制", "avoid": ["虚构经历"]},
               "relevant_context": [],
               "privacy_policy": {"do_not_infer_private_facts": True}}
    package = service.create_creation_handoff(
        work["id"], content_core={"schema": "content-core@1", "question": theme},
        truth_packet=truth, creator_context=creator,
        production_request={"media_type": "video", "orientation": "9:16",
                            "language": "zh-CN", "production_brief": brief,
                            "production_brief_sha256": _sha256(_canonical_bytes(brief)),
                            "video_plan": confirmed,
                            "confirmed_proposal_sha256": work["chat_workflow"]["proposal_sha256"]},
        max_budget_usd=5)
    attempt = service.create_film_attempt(
        work["id"], package["handoff_id"],
        preparation_key=hashlib.sha256(("D0-" + theme).encode()).hexdigest(),
        runtime_status="NOT_CONFIGURED")
    root = Path(attempt["workspace"]["path"])
    _, manifest, _ = handoff.resolve_handoff(work["id"], package["handoff_id"])
    refs = {"content_core_sha256": manifest["content"]["content_core"]["hash"],
            "truth_packet_sha256": manifest["content"]["truth_packet"]["hash"],
            "creator_context_sha256": manifest["creator_context"]["hash"],
            "creative_mode_sha256": manifest["creative_mode"]["hash"],
            "production_brief_sha256": manifest["production_request"]["production_brief_sha256"]}
    ctx = {"content_core": {"schema": "content-core@1", "question": theme},
           "truth_packet": truth, "creator_context": creator, "context_refs": refs}
    canonical = {"SCRIPT.md": confirmed["script"], "SCENES.md": confirmed["scenes"],
                 "TREATMENT.md": confirmed["treatment"] + "\n\n## 声音设计\n" + confirmed["sound"]}
    return attempt, ctx, canonical, confirmed, root


def test_d0_three_independent_confirmed_contents_and_cross_source_rejection(
        material_integration_env, monkeypatch):
    # Reuse existing isolated Creation / Web-consent fixture; make the three
    # independent works freeze the actual project Mode v1.3 documents.
    project_mode = Path(__file__).resolve().parents[1] / "creative_modes"
    monkeypatch.setattr(creative_mode, "CREATIVE_MODES_DIR", project_mode)
    monkeypatch.setattr(handoff, "CREATIVE_MODES_DIR", project_mode, raising=False)
    mode = json.loads((project_mode / "clear_memo_video/mode.json").read_text())
    assert mode["version"] == "1.3"
    works = [_confirmed_synthetic_attempt(*row) for row in CONTENTS]
    assert len({p["SCENES.md"] for _, _, p, _, _ in works}) == 3
    assert all(a["handoff"]["hash"] for a, *_ in works)

    assert len({a["creation_id"] for a, *_ in works}) == 3
    assert len({a["attempt_id"] for a, *_ in works}) == 3
    assert len({p["sha256"] for _, _, _, p, _ in works}) == 3
    assert len({refs["context_refs"]["creative_mode_sha256"] for _, refs, *_ in works}) == 1
    assert len({refs["context_refs"]["content_core_sha256"] for _, refs, *_ in works}) == 3
    assert len({ctx["context_refs"]["truth_packet_sha256"] for _, ctx, *_ in works}) == 3
    assert len({planning_authority.digest({"attempt": a["attempt_id"], "proposal": p["sha256"],
                                              "content": ctx["context_refs"]["content_core_sha256"]})
                for a, ctx, _, p, _ in works}) == 3  # D0 proof identity expectation, not runtime Proof.

    for index, (attempt, ctx, canonical, confirmed, root) in enumerate(works):
        inputs = planning_authority.load_inputs(attempt, canonical, ctx, mode, allow_missing_canonical=True)
        assert inputs["confirmed"] == canonical
        assert inputs["proposal"]["sha256"] == confirmed["sha256"]
        assert inputs["proposal"]["specs"]["audio_mode"] == "silent"
        assert inputs["truth_packet"] == ctx["truth_packet"]
        assert inputs["creator_context"] == ctx["creator_context"]
        source_catalog = planning_authority.catalog(inputs)
        assert source_catalog["schema"] == planning_authority.REVISION
        assert any(row["origin"] == "confirmed_scene" for row in source_catalog["sources"])
        assert any(row["origin"] == "mode_soft" for row in source_catalog["sources"])
        assert source_catalog["inputs_sha256"] == planning_authority.digest(inputs)

        assert inputs["mode_documents"]["mode.json"] == (project_mode / "clear_memo_video/mode.json").read_text()
        assert all(script not in canonical["SCRIPT.md"] for j, (_, script, _) in enumerate(CONTENTS) if j != index)
        wrong = works[(index + 1) % 3]
        with pytest.raises(ValueError):
            planning_authority.load_inputs(attempt, wrong[2], ctx, mode, allow_missing_canonical=True)
        with pytest.raises(ValueError):
            planning_authority.load_inputs(attempt, canonical, wrong[1], mode, allow_missing_canonical=True)
        fake_mode = {**mode, "visual_material_style": "unauthorized mutation"}
        with pytest.raises(ValueError):
            planning_authority.load_inputs(attempt, canonical, ctx, fake_mode, allow_missing_canonical=True)
        tampered = deepcopy(confirmed)
        tampered["script"] += "未经确认的经历。"
        assert not validate_video_plan(tampered)
        tampered_sound = deepcopy(confirmed)
        tampered_sound["sound"] = "未确认的旁白与BGM"
        assert not validate_video_plan(tampered_sound)

    # D1 Claim/Proof does not yet exist: these checks prove only existing
    # Handoff/Proposal/Truth/source isolation, never production Proof validation.
