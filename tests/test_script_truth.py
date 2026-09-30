import json

import pytest

from easel.integrations.script_truth import (
    ScriptTruthError,
    apply_operator_script_review,
    apply_system_script_review,
    create_script_claim_ledger,
    validate_script_claim_ledger,
)


def _truth(tmp_path, *, quote="我在团队做过这个项目。"):
    path = tmp_path / "truth-packet.json"
    path.write_text(json.dumps({
        "schema": "easel-truth-packet@2",
        "claims": [{
            "claim": quote,
            "kind": "observation",
            "source": "user_statement",
            "confidence": "high",
            "source_quote": quote,
        }],
        "personal_facts": [],
    }, ensure_ascii=False), encoding="utf-8")
    return path


def test_exact_user_quote_is_source_backed_and_other_sentences_require_review(tmp_path):
    path = _truth(tmp_path)
    ledger = create_script_claim_ledger(
        "我在团队做过这个项目。行业变化很快。", path,
    )
    assert ledger["status"] == "REVIEW_REQUIRED"
    assert [item["status"] for item in ledger["claims"]] == [
        "TRUTH_SUPPORTED", "REVIEW_REQUIRED",
    ]
    assert ledger["claims"][0]["source_ref"] == "truth_packet.claims[0]"


def test_non_first_person_factual_statement_cannot_pass_automatically(tmp_path):
    ledger = create_script_claim_ledger("这家公司成立于 2012 年。", _truth(tmp_path))
    assert ledger["status"] == "REVIEW_REQUIRED"
    assert ledger["claims"][0]["status"] == "REVIEW_REQUIRED"


def test_first_person_statement_without_exact_source_quote_requires_review(tmp_path):
    ledger = create_script_claim_ledger("我后来改变了团队的工作方式。", _truth(tmp_path))
    assert ledger["claims"][0]["status"] == "REVIEW_REQUIRED"


def test_production_directions_are_auto_checked_but_voiceover_claims_still_need_review(tmp_path):
    script = (
        "## Beat 1 — opening\n"
        "**画面**：手停在键盘上方。\n"
        "**意图**：呈现冲动与停顿。\n"
        "## 旁白\n"
        "问题没有看清就开始敲字，最后会偏离目标。\n"
    )
    ledger = create_script_claim_ledger(script, _truth(tmp_path))
    assert [item["status"] for item in ledger["claims"]] == [
        "AUTO_REVIEWED", "AUTO_REVIEWED", "REVIEW_REQUIRED",
    ]
    assert ledger["claims"][0]["review"]["reviewer"] == "deterministic_classifier"


def test_explicitly_marked_fiction_is_distinguished(tmp_path):
    ledger = create_script_claim_ledger("假设一个团队遇到相同问题。", _truth(tmp_path))
    assert ledger["status"] == "PASSED"
    assert ledger["claims"][0]["classification"] == "EXPLICIT_FICTION"
    assert ledger["claims"][0]["status"] == "FICTION_MARKED"


def test_operator_review_is_explicit_hash_bound_and_never_claimed_as_source_truth(tmp_path):
    truth_path = _truth(tmp_path)
    script = "行业变化很快。"
    ledger = create_script_claim_ledger(script, truth_path)
    with pytest.raises(ScriptTruthError, match="explicitly confirm"):
        apply_operator_script_review(
            script, truth_path, ledger,
            confirm_all_claims_reviewed=False,
            expected_script_sha256=ledger["script_sha256"],
            expected_truth_packet_sha256=ledger["truth_packet_sha256"],
        )
    reviewed = apply_operator_script_review(
        script, truth_path, ledger,
        confirm_all_claims_reviewed=True,
        expected_script_sha256=ledger["script_sha256"],
        expected_truth_packet_sha256=ledger["truth_packet_sha256"],
    )
    assert reviewed["status"] == "PASSED"
    assert reviewed["claims"][0]["status"] == "HUMAN_REVIEWED"
    assert reviewed["claims"][0]["review"]["reviewer"] == "local_operator"
    assert validate_script_claim_ledger(script, truth_path, reviewed) == reviewed


def test_delegated_review_is_audited_separately_from_human_review(tmp_path):
    truth_path = _truth(tmp_path)
    script = "行业变化很快。"
    ledger = create_script_claim_ledger(script, truth_path)
    reviewed = apply_operator_script_review(
        script, truth_path, ledger,
        confirm_all_claims_reviewed=True,
        expected_script_sha256=ledger["script_sha256"],
        expected_truth_packet_sha256=ledger["truth_packet_sha256"],
        reviewer="codex_delegate",
    )
    assert reviewed["status"] == "PASSED"
    assert reviewed["claims"][0]["status"] == "DELEGATE_REVIEWED"
    assert reviewed["claims"][0]["review"]["reviewer"] == "codex_delegate"
    assert validate_script_claim_ledger(script, truth_path, reviewed) == reviewed


def test_stale_script_or_truth_packet_invalidates_operator_review(tmp_path):
    truth_path = _truth(tmp_path)
    script = "行业变化很快。"
    ledger = create_script_claim_ledger(script, truth_path)
    reviewed = apply_operator_script_review(
        script, truth_path, ledger,
        confirm_all_claims_reviewed=True,
        expected_script_sha256=ledger["script_sha256"],
        expected_truth_packet_sha256=ledger["truth_packet_sha256"],
    )
    with pytest.raises(ScriptTruthError, match="stale for current Script"):
        validate_script_claim_ledger(script + "新增一句。", truth_path, reviewed)
    truth_path.write_text(truth_path.read_text(encoding="utf-8").replace("团队", "小组"), encoding="utf-8")
    with pytest.raises(ScriptTruthError, match="stale for frozen Truth"):
        validate_script_claim_ledger(script, truth_path, reviewed)


def test_omitted_or_edited_claim_entry_fails_complete_coverage(tmp_path):
    truth_path = _truth(tmp_path)
    script = "第一句。第二句。"
    ledger = create_script_claim_ledger(script, truth_path)
    omitted = dict(ledger, claims=ledger["claims"][:1])
    with pytest.raises(ScriptTruthError, match="does not cover every"):
        validate_script_claim_ledger(script, truth_path, omitted)
    spoofed = json.loads(json.dumps(ledger))
    spoofed["claims"][0]["status"] = "TRUTH_SUPPORTED"
    with pytest.raises(ScriptTruthError, match="cannot be auto-promoted"):
        validate_script_claim_ledger(script, truth_path, spoofed)


def test_duplicate_extra_and_invalid_source_reference_entries_are_rejected(tmp_path):
    from easel.integrations.script_truth import _canonical_digest

    truth_path = _truth(tmp_path)
    script = "第一句。第二句。"
    ledger = create_script_claim_ledger(script, truth_path)

    duplicate = json.loads(json.dumps(ledger))
    duplicate["claims"][1] = duplicate["claims"][0]
    duplicate["ledger_sha256"] = _canonical_digest(duplicate)
    with pytest.raises(ScriptTruthError, match="does not match current Script/evidence"):
        validate_script_claim_ledger(script, truth_path, duplicate)

    extra = json.loads(json.dumps(ledger))
    extra["claims"].append(dict(extra["claims"][-1]))
    extra["ledger_sha256"] = _canonical_digest(extra)
    with pytest.raises(ScriptTruthError, match="does not cover every review unit"):
        validate_script_claim_ledger(script, truth_path, extra)

    invalid_ref = json.loads(json.dumps(ledger))
    invalid_ref["claims"][0]["source_ref"] = "truth_packet.claims[99]"
    invalid_ref["ledger_sha256"] = _canonical_digest(invalid_ref)
    with pytest.raises(ScriptTruthError, match="does not match current Script/evidence"):
        validate_script_claim_ledger(script, truth_path, invalid_ref)


def test_lexical_overlap_alone_does_not_establish_truth_support(tmp_path):
    ledger = create_script_claim_ledger("团队可能在未来做过这个项目。", _truth(tmp_path))
    assert ledger["claims"][0]["status"] == "REVIEW_REQUIRED"


def test_system_review_distinguishes_paraphrase_expression_and_missing_facts(tmp_path):
    path = _truth(tmp_path)
    script = "我参与过团队的这个项目。先看清问题，再决定往哪走。该公司在 2012 年成立。"
    ledger = create_script_claim_ledger(script, path)
    report = {"schema": "easel-script-assessment@1", "script_sha256": ledger["script_sha256"],
              "truth_packet_sha256": ledger["truth_packet_sha256"], "decisions": [
        {"claim_id": "claim-0001", "kind": "supported_paraphrase", "reason": "仅改写已陈述的团队项目经历，未增加结果或身份。",
         "sources": [{"ref": "truth_packet.claims[0]", "quote": "我在团队做过这个项目。"}]},
        {"claim_id": "claim-0002", "kind": "creative_expression", "reason": "表达选择与行动的主观取向，不断言现实成效。", "sources": []},
        {"claim_id": "claim-0003", "kind": "unresolved", "reason": "委托要求介绍该公司，但底稿没有成立年份依据。", "sources": []},
    ]}
    reviewed = apply_system_script_review(script, path, ledger, report)
    assert [row["status"] for row in reviewed["claims"]] == ["SYSTEM_REVIEWED", "SYSTEM_REVIEWED", "REVIEW_REQUIRED"]
    assert reviewed["status"] == "REVIEW_REQUIRED"
    assert all(row["review"] is None for row in ledger["claims"])
    assert validate_script_claim_ledger(script, path, reviewed) == reviewed
    human = apply_operator_script_review(script, path, reviewed, confirm_all_claims_reviewed=True,
        expected_script_sha256=ledger["script_sha256"], expected_truth_packet_sha256=ledger["truth_packet_sha256"])
    assert [row["status"] for row in human["claims"]] == ["SYSTEM_REVIEWED", "SYSTEM_REVIEWED", "HUMAN_REVIEWED"]
    assert human["status"] == "PASSED"
    assert validate_script_claim_ledger(script, path, human) == human
    with pytest.raises(ScriptTruthError, match="stale"):
        validate_script_claim_ledger(script + "新事实。", path, reviewed)


@pytest.mark.parametrize("invalid", ["missing_source", "wrong_quote", "private_fact", "stale", "missing_claim"])
def test_system_review_cannot_replace_evidence_or_coverage_with_a_pass_flag(tmp_path, invalid):
    path = _truth(tmp_path)
    truth = json.loads(path.read_text())
    truth["personal_facts"] = [{"source": "profile", "fact": "未公开的收入情况。", "public_allowed": False}]
    path.write_text(json.dumps(truth))
    script = "我参与过团队的这个项目。"
    ledger = create_script_claim_ledger(script, path)
    decision = {"claim_id": "claim-0001", "kind": "supported_paraphrase", "reason": "改写底稿中已给出的经历。",
                "sources": [{"ref": "truth_packet.claims[0]", "quote": "我在团队做过这个项目。"}]}
    report = {"schema": "easel-script-assessment@1", "script_sha256": ledger["script_sha256"],
              "truth_packet_sha256": ledger["truth_packet_sha256"], "decisions": [decision]}
    if invalid == "missing_source":
        decision["sources"] = []
    elif invalid == "wrong_quote":
        decision["sources"][0]["quote"] = "我领导了这个团队。"
    elif invalid == "private_fact":
        decision["sources"] = [{"ref": "truth_packet.personal_facts[0]", "quote": "未公开的收入情况。"}]
    elif invalid == "stale":
        report["truth_packet_sha256"] = "0" * 64
    else:
        report["decisions"] = []
    with pytest.raises(ScriptTruthError):
        apply_system_script_review(script, path, ledger, report)
    assert ledger["claims"][0]["status"] == "REVIEW_REQUIRED"
