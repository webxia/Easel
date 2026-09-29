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


def _units(script: str) -> list[tuple[str, bool]]:
    encoded = script.encode("utf-8")
    if len(encoded) > _MAX_SCRIPT_BYTES or "\x00" in script:
        raise ScriptTruthError("Script is invalid or exceeds review limit")
    units: list[tuple[str, bool]] = []
    directive_section = False
    for line in script.splitlines():
        heading = re.match(r"^\s*#{1,6}\s+(.+?)\s*#*\s*$", line)
        if heading:
            section = heading.group(1).strip()
            if _DIRECTION_SECTION.fullmatch(section):
                directive_section = True
            elif _CLAIM_SECTION.fullmatch(section):
                directive_section = False
            continue
        if line.strip() in {"---", "***", "___"}:
            continue
        value = re.sub(r"^\s*(?:#{1,6}\s+|[-*+]\s+|>\s*)", "", line).strip()
        if not value:
            continue
        if value.casefold() in {"script", "narration", "脚本", "旁白"}:
            continue
        direction = directive_section or bool(_DIRECTION_PREFIX.match(value))
        for part in _SENTENCE_BOUNDARY.split(value):
            text = part.strip()
            if text:
                if len(text) > 4000:
                    raise ScriptTruthError("Script sentence exceeds review limit")
                units.append((text, direction))
    if not units:
        raise ScriptTruthError("Script contains no reviewable text")
    if len(units) > _MAX_UNITS:
        raise ScriptTruthError("Script has too many review units")
    return units


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


def create_script_claim_ledger(script: str, truth_path: Path) -> dict[str, Any]:
    """Create a complete ledger; only exact frozen user quotes pass automatically."""
    truth_bytes, truth = _read_truth(truth_path)
    script_bytes = script.encode("utf-8")
    rows = []
    evidence = _verbatim_evidence(truth)
    for index, (text, is_direction) in enumerate(_units(script), start=1):
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
            "claim_id": f"claim-{index:04d}",
            "text": text,
            "classification": classification,
            "status": status,
            "source_ref": source_ref,
            "evidence_quote": text if source_ref else None,
            "review": ({"reviewer": "deterministic_classifier", "rule": "non-claim-directive-v1"}
                       if status == "AUTO_REVIEWED" else None),
        })
    ledger: dict[str, Any] = {
        "schema": "easel-script-claim-ledger@2",
        "script_sha256": _sha256(script_bytes),
        "truth_packet_sha256": _sha256(truth_bytes),
        "claims": rows,
        "status": "REVIEW_REQUIRED" if any(row["status"] == "REVIEW_REQUIRED" for row in rows) else "PASSED",
    }
    ledger["ledger_sha256"] = _canonical_digest(ledger)
    return ledger


def validate_script_claim_ledger(script: str, truth_path: Path, ledger: dict[str, Any]) -> dict[str, Any]:
    """Validate current bytes, full text coverage, permitted dispositions, and stored digest."""
    expected = create_script_claim_ledger(script, truth_path)
    if not isinstance(ledger, dict) or ledger.get("schema") != "easel-script-claim-ledger@2":
        raise ScriptTruthError("Script claim ledger schema is invalid")
    if ledger.get("script_sha256") != expected["script_sha256"]:
        raise ScriptTruthError("Script claim ledger is stale for current Script bytes")
    if ledger.get("truth_packet_sha256") != expected["truth_packet_sha256"]:
        raise ScriptTruthError("Script claim ledger is stale for frozen Truth Packet bytes")
    rows = ledger.get("claims")
    if not isinstance(rows, list) or len(rows) != len(expected["claims"]):
        raise ScriptTruthError("Script claim ledger does not cover every review unit")
    allowed = {
        "TRUTH_SUPPORTED", "FICTION_MARKED", "AUTO_REVIEWED", "REVIEW_REQUIRED",
        "HUMAN_REVIEWED", "DELEGATE_REVIEWED",
    }
    for actual, base in zip(rows, expected["claims"], strict=True):
        if not isinstance(actual, dict) or any(actual.get(key) != base.get(key) for key in (
            "claim_id", "text", "classification", "source_ref", "evidence_quote",
        )):
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
                    or review.get("rule") != "non-claim-directive-v1"):
                raise ScriptTruthError("Deterministic Script direction review evidence is invalid")
        if base["status"] == "REVIEW_REQUIRED" and status not in {
            "REVIEW_REQUIRED", "HUMAN_REVIEWED", "DELEGATE_REVIEWED",
        }:
            raise ScriptTruthError("Unresolved Script claim cannot be auto-promoted")
        if base["status"] == "REVIEW_REQUIRED" and status in {"HUMAN_REVIEWED", "DELEGATE_REVIEWED"}:
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
        "TRUTH_SUPPORTED", "FICTION_MARKED", "AUTO_REVIEWED", "HUMAN_REVIEWED", "DELEGATE_REVIEWED",
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
