"""Conservative, hash-bound claim review for frozen Planning Scripts."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path
from typing import Any


_FICTION_PREFIX = re.compile(r"^(?:假设|假如|如果|虚构|想象|fiction\s*:|hypothetical\s*:)", re.IGNORECASE)
_SENTENCE_BOUNDARY = re.compile(r"(?<=[。！？!?])\s*|\n+")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_DIRECTION_PREFIX = re.compile(
    r"^(?:\*\*)?(?:画面|意图|镜头|第一人称|画幅|节奏|音轨|字幕策略|文字策略|字幕与时间线细节|素材|肖像红线|素材红线|不写|禁止|约束|结构|总时长|语言)(?:\*\*)?\s*[：:]"
    r"|^Beat\s+\d+\b|^[-—]{3,}$",
    re.IGNORECASE,
)
_CLAIM_SECTION = re.compile(r"^(?:旁白|配音|台词|字幕文案|落幅文字|片尾文案|屏幕文字)$", re.IGNORECASE)
_DIRECTION_SECTION = re.compile(r"^(?:不写的内容|备注|制作约束|镜头说明|画面说明)$", re.IGNORECASE)
_MAX_SCRIPT_BYTES = 128 * 1024
_MAX_TRUTH_BYTES = 256 * 1024
_MAX_UNITS = 1000
_SYSTEM_REVIEWER = "easel_script_review"


class ScriptTruthError(ValueError):
    """Raised when Script review evidence is malformed or stale."""


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_digest(value: dict[str, Any]) -> str:
    body = {key: item for key, item in value.items() if key != "ledger_sha256"}
    payload = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha256(payload)


def _read_truth(truth_path: Path) -> tuple[bytes, dict[str, Any]]:
    if truth_path.is_symlink() or not truth_path.is_file():
        raise ScriptTruthError("Frozen Truth Packet is unavailable for Script review")
    payload = truth_path.read_bytes()
    if len(payload) > _MAX_TRUTH_BYTES:
        raise ScriptTruthError("Frozen Truth Packet exceeds review limit")
    try:
        truth = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ScriptTruthError("Frozen Truth Packet is invalid JSON") from exc
    if not isinstance(truth, dict) or truth.get("schema") != "easel-truth-packet@2":
        raise ScriptTruthError("Frozen Truth Packet schema is unsupported")
    if not isinstance(truth.get("claims"), list) or not isinstance(truth.get("personal_facts"), list):
        raise ScriptTruthError("Frozen Truth Packet evidence lists are invalid")
    return payload, truth


def _verbatim_evidence(truth: dict[str, Any]) -> dict[str, str]:
    """Return only user-authored verbatim quotes that can be checked exactly."""
    evidence: dict[str, str] = {}
    for index, item in enumerate(truth["claims"]):
        if (isinstance(item, dict) and item.get("source") == "user_statement"
                and isinstance(item.get("source_quote"), str)
                and item.get("source_quote") == item.get("claim")):
            evidence[item["source_quote"]] = f"truth_packet.claims[{index}]"
    for index, item in enumerate(truth["personal_facts"]):
        if (isinstance(item, dict) and item.get("source") == "user_statement"
                and isinstance(item.get("source_quote"), str)
                and item.get("source_quote") == item.get("fact")):
            evidence[item["source_quote"]] = f"truth_packet.personal_facts[{index}]"
    return evidence


def create_script_claim_ledger(script: str, truth_path: Path, *,
                               revision: str = "easel-script-claim-ledger@3") -> dict[str, Any]:
    """Create the only production Script ledger with full Markdown coverage."""
    if revision != "easel-script-claim-ledger@3":
        raise ScriptTruthError("Unknown Script ledger revision")
    truth_bytes, truth = _read_truth(truth_path)
    script_bytes = script.encode("utf-8")
    rows = []
    evidence = _verbatim_evidence(truth)
    from easel.integrations.script_markdown import extract_script
    try:
        markdown_units, coverage, parser = extract_script(script)
    except ValueError as exc:
        raise ScriptTruthError(str(exc)) from exc
    source_units = [(row["text"], row["direction"], row) for row in markdown_units]
    for index, (text, is_direction, source_unit) in enumerate(source_units, start=1):
        source_ref = evidence.get(text)
        if source_ref:
            status, classification = "TRUTH_SUPPORTED", "VERBATIM_SOURCE"
        elif _FICTION_PREFIX.match(text):
            status, classification = "FICTION_MARKED", "EXPLICIT_FICTION"
        elif is_direction:
            status, classification = "AUTO_REVIEWED", "CREATIVE_DIRECTION"
        else:
            status, classification = "REVIEW_REQUIRED", "UNCLASSIFIED_ASSERTION_OR_CREATIVE_TEXT"
        rows.append({
            **{key: source_unit[key] for key in ("block_id", "block_type", "source_block_span",
                "unit_ordinal_in_block", "text_sha256", "extractor_revision", "role")},
            "claim_id": f"claim-{index:04d}",
            "text": text,
            "classification": classification,
            "status": status,
            "source_ref": source_ref,
            "evidence_quote": text if source_ref else None,
            "review": ({"reviewer": "deterministic_classifier",
                        "rule": "markdown-v3-direction@1"}
                       if status == "AUTO_REVIEWED" else None),
        })
    ledger: dict[str, Any] = {
        "schema": revision,
        "parser_identity": parser, "coverage": coverage,
        "script_sha256": _sha256(script_bytes),
        "truth_packet_sha256": _sha256(truth_bytes),
        "claims": rows,
        "status": "REVIEW_REQUIRED" if any(row["status"] == "REVIEW_REQUIRED" for row in rows) else "PASSED",
    }
    ledger["ledger_sha256"] = _canonical_digest(ledger)
    return ledger


def system_review_sources(truth_path: Path) -> dict[str, str]:
    """Available frozen evidence; an external URL or model inference is not a source body."""
    _, truth = _read_truth(truth_path)
    sources = {ref: quote for quote, ref in _verbatim_evidence(truth).items()
               if ".claims[" in ref}
    for index, fact in enumerate(truth["personal_facts"]):
        if (isinstance(fact, dict) and fact.get("public_allowed") is True
                and fact.get("source") in {"profile", "user_statement"}
                and isinstance(fact.get("fact"), str) and fact["fact"].strip()):
            sources[f"truth_packet.personal_facts[{index}]"] = fact["fact"]
    return sources


def _validate_system_decision(decision: dict, claim_id: str, sources: dict[str, str]) -> str:
    if (not isinstance(decision, dict) or set(decision) != {"claim_id", "kind", "reason", "sources"}
            or decision.get("claim_id") != claim_id
            or decision.get("kind") not in {"supported_paraphrase", "creative_expression", "rewrite_required", "unresolved"}
            or not isinstance(decision.get("reason"), str) or not decision["reason"].strip()
            or len(decision["reason"]) > 2000):
        raise ScriptTruthError("系统 Script 审阅必须逐项说明判断及依据")
    references = decision["sources"]
    if not isinstance(references, list) or len(references) > 20:
        raise ScriptTruthError("系统 Script 审阅的来源列表无效")
    for source in references:
        if (not isinstance(source, dict) or set(source) != {"ref", "quote"}
                or not isinstance(source.get("ref"), str) or source["ref"] not in sources
                or source.get("quote") != sources[source["ref"]]):
            raise ScriptTruthError("系统 Script 审阅引用了不存在、不可公开或不匹配的冻结依据")
    kind = decision["kind"]
    if kind == "supported_paraphrase" and not references:
        raise ScriptTruthError("事实改写必须引用冻结依据，不能以模型判断代替来源")
    if kind == "creative_expression" and references:
        raise ScriptTruthError("创作表达与事实改写必须分别归类")
    return "REVIEW_REQUIRED" if kind in {"unresolved", "rewrite_required"} else "SYSTEM_REVIEWED"


def apply_system_script_review(script: str, truth_path: Path, ledger: dict[str, Any],
                               report: dict[str, Any]) -> dict[str, Any]:
    """Apply an executed semantic review, distinct from exact evidence and human acceptance.

    This validates provenance and coverage, not semantic entailment. The reviewer
    must read the full Script/Truth and classify factual assertions honestly.
    """
    current = validate_script_claim_ledger(script, truth_path, ledger)
    if (not isinstance(report, dict)
            or set(report) != {"schema", "script_sha256", "truth_packet_sha256", "decisions"}
            or report.get("schema") != "easel-script-assessment@1"
            or any(report.get(key) != current[key] for key in ("script_sha256", "truth_packet_sha256"))):
        raise ScriptTruthError("系统 Script 审阅未绑定当前脚本和事实底稿")
    decisions = report["decisions"]
    unresolved = {row["claim_id"] for row in current["claims"] if row["status"] == "REVIEW_REQUIRED"}
    if (not isinstance(decisions, list)
            or any(not isinstance(item, dict) or not isinstance(item.get("claim_id"), str) for item in decisions)):
        raise ScriptTruthError("系统脚本审阅条目格式无效")
    from collections import Counter
    counts = Counter(item["claim_id"] for item in decisions)
    known = {row["claim_id"]: row for row in current["claims"]}
    missing = sorted(unresolved - counts.keys())
    duplicates = sorted(key for key, count in counts.items() if count > 1)
    unknown = sorted(counts.keys() - known.keys())
    if missing or duplicates or unknown:
        raise ScriptTruthError("系统脚本审阅覆盖不完整：遗漏=" + str(missing)
                               + "；重复=" + str(duplicates) + "；未知编号=" + str(unknown))
    evidence = system_review_sources(truth_path)
    for item in decisions:
        claim_id = item["claim_id"]
        _validate_system_decision(item, claim_id, evidence)
        if claim_id not in unresolved:
            row = known[claim_id]
            allowed = (item["kind"] == "creative_expression" and row["status"] in {"AUTO_REVIEWED", "FICTION_MARKED"}
                       or item["kind"] == "supported_paraphrase" and row["status"] == "TRUTH_SUPPORTED")
            if not allowed:
                raise ScriptTruthError("额外审阅与已有判断冲突，不能覆盖：" + claim_id)
    # Harmless extra review never replaces deterministic/source-bound evidence.
    by_id = {item["claim_id"]: item for item in decisions if item["claim_id"] in unresolved}
    reviewed_at = datetime.now(timezone.utc).isoformat()
    # Copy after validation; a rejected report must not partially mutate evidence.
    current = json.loads(json.dumps(current))
    for row in current["claims"]:
        if row["claim_id"] not in by_id:
            continue
        decision = by_id[row["claim_id"]]
        row["status"] = _validate_system_decision(decision, row["claim_id"], evidence)
        row["review"] = {"reviewer": _SYSTEM_REVIEWER, "decision": decision,
                         "script_sha256": current["script_sha256"],
                         "truth_packet_sha256": current["truth_packet_sha256"], "reviewed_at": reviewed_at}
    current["status"] = "REVIEW_REQUIRED" if any(row["status"] == "REVIEW_REQUIRED" for row in current["claims"]) else "PASSED"
    current["ledger_sha256"] = _canonical_digest(current)
    return validate_script_claim_ledger(script, truth_path, current)


def validate_script_claim_ledger(script: str, truth_path: Path, ledger: dict[str, Any]) -> dict[str, Any]:
    """Validate current bytes, full text coverage, permitted dispositions, and stored digest."""
    if not isinstance(ledger, dict) or ledger.get("schema") != "easel-script-claim-ledger@3":
        raise ScriptTruthError("Script claim ledger schema is invalid")
    expected = create_script_claim_ledger(script, truth_path, revision=ledger["schema"])
    # Distinguish genuinely stale frozen source bytes before the derived
    # Markdown parser coverage. Never interpret either mismatch as a PASS.
    if ledger.get("script_sha256") != expected["script_sha256"]:
        raise ScriptTruthError("Script claim ledger is stale for current Script bytes")
    if ledger.get("truth_packet_sha256") != expected["truth_packet_sha256"]:
        raise ScriptTruthError("Script claim ledger is stale for frozen Truth Packet bytes")
    if any(ledger.get(key) != expected[key] for key in ("parser_identity", "coverage")):
        raise ScriptTruthError("Script Markdown parser identity or complete block coverage changed")
    rows = ledger.get("claims")
    if not isinstance(rows, list) or len(rows) != len(expected["claims"]):
        raise ScriptTruthError("Script claim ledger does not cover every review unit")
    system_sources = system_review_sources(truth_path) if any(
        isinstance(row, dict) and isinstance(row.get("review"), dict)
        and row["review"].get("reviewer") == _SYSTEM_REVIEWER for row in rows) else {}
    allowed = {
        "TRUTH_SUPPORTED", "FICTION_MARKED", "AUTO_REVIEWED", "REVIEW_REQUIRED",
        "HUMAN_REVIEWED", "DELEGATE_REVIEWED", "SYSTEM_REVIEWED",
    }
    for actual, base in zip(rows, expected["claims"], strict=True):
        keys = ("claim_id", "text", "classification", "source_ref", "evidence_quote")
        keys += ("block_id", "block_type", "source_block_span", "unit_ordinal_in_block",
                 "text_sha256", "extractor_revision", "role")
        if not isinstance(actual, dict) or any(actual.get(key) != base.get(key) for key in keys):
            raise ScriptTruthError("Script claim ledger entry does not match current Script/evidence")
        status = actual.get("status")
        if status not in allowed:
            raise ScriptTruthError("Script claim ledger disposition is invalid")
        if base["status"] in {"TRUTH_SUPPORTED", "FICTION_MARKED"} and status != base["status"]:
            raise ScriptTruthError("Automatic Script disposition differs from frozen evidence")
        if base["status"] == "AUTO_REVIEWED":
            review = actual.get("review")
            if (status != "AUTO_REVIEWED" or not isinstance(review, dict)
                    or review.get("reviewer") != "deterministic_classifier"
                    or review.get("rule") != base["review"]["rule"]):
                raise ScriptTruthError("Deterministic Script direction review evidence is invalid")
        if base["status"] == "REVIEW_REQUIRED" and status not in {
            "REVIEW_REQUIRED", "HUMAN_REVIEWED", "DELEGATE_REVIEWED", "SYSTEM_REVIEWED",
        }:
            raise ScriptTruthError("Unresolved Script claim cannot be auto-promoted")
        review = actual.get("review")
        if base["status"] == "REVIEW_REQUIRED" and (status == "SYSTEM_REVIEWED"
                or isinstance(review, dict) and review.get("reviewer") == _SYSTEM_REVIEWER):
            if (not isinstance(review, dict) or review.get("reviewer") != _SYSTEM_REVIEWER
                    or review.get("script_sha256") != expected["script_sha256"]
                    or review.get("truth_packet_sha256") != expected["truth_packet_sha256"]
                    or not isinstance(review.get("reviewed_at"), str)
                    or _validate_system_decision(review.get("decision"), base["claim_id"],
                                                  system_sources) != status):
                raise ScriptTruthError("系统 Script 审阅证据无效或已过期")
        elif base["status"] == "REVIEW_REQUIRED" and status in {"HUMAN_REVIEWED", "DELEGATE_REVIEWED"}:
            review = actual.get("review")
            expected_reviewer = "local_operator" if status == "HUMAN_REVIEWED" else "codex_delegate"
            if (not isinstance(review, dict) or review.get("reviewer") != expected_reviewer
                    or not isinstance(review.get("reviewed_at"), str)
                    or not isinstance(review.get("script_sha256"), str)
                    or review["script_sha256"] != expected["script_sha256"]
                    or review.get("truth_packet_sha256") != expected["truth_packet_sha256"]
                    or not review.get("claim_ids")):
                raise ScriptTruthError("Human Script review evidence is invalid")
        elif status == "REVIEW_REQUIRED" and actual.get("review") is not None:
            raise ScriptTruthError("Unreviewed Script claim contains unexpected review evidence")
    expected_status = "PASSED" if all(row["status"] in {
        "TRUTH_SUPPORTED", "FICTION_MARKED", "AUTO_REVIEWED", "HUMAN_REVIEWED", "DELEGATE_REVIEWED", "SYSTEM_REVIEWED",
    }
                                       for row in rows) else "REVIEW_REQUIRED"
    if ledger.get("status") != expected_status or ledger.get("ledger_sha256") != _canonical_digest(ledger):
        raise ScriptTruthError("Script claim ledger status or digest is invalid")
    return ledger


def apply_operator_script_review(
    script: str,
    truth_path: Path,
    ledger: dict[str, Any],
    *,
    confirm_all_claims_reviewed: bool,
    expected_script_sha256: str,
    expected_truth_packet_sha256: str,
    reviewer: str = "local_operator",
) -> dict[str, Any]:
    """Record an explicit operator or delegated-agent review for unresolved Script units."""
    current = validate_script_claim_ledger(script, truth_path, ledger)
    if reviewer not in {"local_operator", "codex_delegate"}:
        raise ScriptTruthError("Script reviewer identity is invalid")
    if not confirm_all_claims_reviewed:
        raise ScriptTruthError("Operator must explicitly confirm review of all unresolved Script claims")
    if not _SHA256.fullmatch(expected_script_sha256) or not _SHA256.fullmatch(expected_truth_packet_sha256):
        raise ScriptTruthError("Expected Script/Truth Packet hashes are invalid")
    if (expected_script_sha256 != current["script_sha256"]
            or expected_truth_packet_sha256 != current["truth_packet_sha256"]):
        raise ScriptTruthError("Script or Truth Packet changed since the operator reviewed it")
    reviewed_at = datetime.now(timezone.utc).isoformat()
    unresolved = [row["claim_id"] for row in current["claims"] if row["status"] == "REVIEW_REQUIRED"]
    for row in current["claims"]:
        if row["status"] == "REVIEW_REQUIRED":
            row["status"] = "HUMAN_REVIEWED" if reviewer == "local_operator" else "DELEGATE_REVIEWED"
            row["review"] = {
                "reviewer": reviewer,
                "reviewed_at": reviewed_at,
                "script_sha256": current["script_sha256"],
                "truth_packet_sha256": current["truth_packet_sha256"],
                "claim_ids": unresolved,
            }
    current["status"] = "PASSED"
    current["ledger_sha256"] = _canonical_digest(current)
    return current


def review_script_claims(script: str, truth_path: Path) -> dict[str, Any]:
    """Compatibility name for creating a conservative claim ledger, not a semantic fact check."""
    return create_script_claim_ledger(script, truth_path)
