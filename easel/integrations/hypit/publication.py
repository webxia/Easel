"""Attempt-local, bounded, resumable Authoring file publication.

The existing Authoring Owner decides what can be published. This helper has
no model, provider, check, rights or build authority. It only preserves an
immutable before/candidate journal and resumes its own partially written files.
"""
from __future__ import annotations

import base64
import fcntl
import hashlib
import json
import os
import re
import stat
import tempfile
from pathlib import Path

SCHEMA = "authoring-file-publication@1"
MAX_FILES = 8
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 8 * 1024 * 1024
_PATH_PREFIX = "productions/easel-authoring/"


class AuthoringPublicationError(RuntimeError):
    """A local identity, file-integrity or storage failure; never a model retry."""


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _encode(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":")) + "\n").encode("utf-8")


def _check_name(name: str) -> None:
    if (not isinstance(name, str) or not name.startswith(_PATH_PREFIX)
            or name.startswith("/") or "\\" in name or not name.endswith((".json", ".svml", ".svrun", ".svs"))
            or any(segment in {"", ".", ".."} for segment in name.split("/"))
            or len(name) > 240):
        raise AuthoringPublicationError("Authoring publication path is not an allowed relative source")



def _validate_candidate(name: str, payload: bytes) -> None:
    """Only validated UTF-8 source, never credentials or malformed JSON, enters a journal."""
    from .secrets import SecretRedactor

    if not isinstance(payload, bytes) or len(payload) > MAX_FILE_BYTES or b"\x00" in payload:
        raise AuthoringPublicationError("Authoring candidate bytes are invalid")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AuthoringPublicationError("Authoring source must be UTF-8") from exc
    if SecretRedactor.contains_secret(text):
        raise AuthoringPublicationError("Authoring source contains forbidden credential-like content")
    if name.endswith(".json"):
        def no_duplicate(pairs):
            data = {}
            for key, value in pairs:
                if key in data:
                    raise ValueError("duplicate JSON key")
                data[key] = value
            return data
        try:
            value = json.loads(text, object_pairs_hook=no_duplicate,
                               parse_constant=lambda _value: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
        except ValueError as exc:
            raise AuthoringPublicationError("Authoring JSON candidate is not a complete unique-key object") from exc
        if not isinstance(value, dict) or SecretRedactor.contains_secret(value):
            raise AuthoringPublicationError("Authoring JSON candidate contains invalid or sensitive content")

def _path(root: Path, relative: str, *, allow_directory: bool = False) -> Path:
    parts = Path(relative).parts
    path = root
    if root.is_symlink() or not root.is_dir():
        raise AuthoringPublicationError("Authoring workspace is not a regular directory")
    for item in parts:
        path = path / item
        if path.is_symlink():
            raise AuthoringPublicationError("Authoring publication may not follow symlinks")
    if path.exists() and not (stat.S_ISREG(path.stat().st_mode)
                              or allow_directory and stat.S_ISDIR(path.stat().st_mode)):
        raise AuthoringPublicationError("Authoring source must be a regular file")
    return path


def _bytes(path: Path) -> bytes | None:
    if not path.exists():
        return None
    try:
        before = path.stat()
        if before.st_size > MAX_FILE_BYTES:
            raise AuthoringPublicationError("Authoring source exceeds fixed publication capacity")
        raw = path.read_bytes()
        after = path.stat()
    except OSError as exc:
        raise AuthoringPublicationError("Authoring source cannot be read") from exc
    if ((before.st_dev, before.st_ino, before.st_mtime_ns, before.st_size) !=
            (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_size)):
        raise AuthoringPublicationError("Authoring source changed while capturing")
    return raw


def _journal_directory(root: Path) -> Path:
    directory = _path(root, ".easel/authoring-publications", allow_directory=True)
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise AuthoringPublicationError("Authoring journal directory could not be created") from exc
    return directory


def _journal_key(*, attempt_id: str, operation_id: str, frozen_identity: str) -> str:
    for value in (attempt_id, operation_id, frozen_identity):
        if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9_.:-]{1,128}", value):
            raise AuthoringPublicationError("Authoring operation identity is invalid")
    return _digest(_encode({"schema": SCHEMA, "attempt_id": attempt_id,
                            "operation_id": operation_id, "frozen_identity": frozen_identity}))


def _atomic_create(path: Path, data: bytes) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".authoring-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        # Atomic no-clobber link: a racing journal cannot be silently replaced.
        os.link(temporary, path)
    except FileExistsError as exc:
        raise AuthoringPublicationError("Authoring journal exists or changed during preparation") from exc
    except OSError as exc:
        raise AuthoringPublicationError("Authoring journal cannot be persisted") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)

def _replace(path: Path, data: bytes) -> None:
    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".authoring-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if path.is_symlink():
            raise AuthoringPublicationError("Authoring target changed to symlink")
        os.replace(temporary, path)
        temporary = None
    except OSError as exc:
        raise AuthoringPublicationError("Authoring file replacement failed; recover this publication") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _read_journal(root: Path, journal_id: str) -> dict:
    if not re.fullmatch(r"[0-9a-f]{64}", journal_id):
        raise AuthoringPublicationError("Authoring publication id is invalid")
    path = _journal_directory(root) / (journal_id + ".json")
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 3 * MAX_TOTAL_BYTES:
        raise AuthoringPublicationError("Authoring publication journal missing or invalid")
    try:
        record = json.loads(path.read_bytes())
    except (OSError, UnicodeError, ValueError) as exc:
        raise AuthoringPublicationError("Authoring journal is unreadable") from exc
    if (not isinstance(record, dict) or record.get("schema") != SCHEMA
            or record.get("journal_id") != journal_id or not 1 <= len(record.get("targets", [])) <= MAX_FILES):
        raise AuthoringPublicationError("Authoring publication journal schema is invalid")
    expected_id = _journal_key(attempt_id=record["attempt_id"],
        operation_id=record["operation_id"], frozen_identity=record["frozen_identity"])
    if expected_id != journal_id:
        raise AuthoringPublicationError("Authoring operation identity changed")
    for target in record["targets"]:
        if not isinstance(target, dict) or set(target) != {"path", "before_sha256", "after_sha256", "candidate_b64"}:
            raise AuthoringPublicationError("Authoring publication target proof is invalid")
        _check_name(target["path"])
        try:
            candidate = base64.b64decode(target["candidate_b64"], validate=True)
        except (ValueError, TypeError) as exc:
            raise AuthoringPublicationError("Authoring publication candidate is unreadable") from exc
        if len(candidate) > MAX_FILE_BYTES or _digest(candidate) != target["after_sha256"]:
            raise AuthoringPublicationError("Authoring publication candidate bytes changed")
        _validate_candidate(target['path'], candidate)
    if len({r["path"] for r in record["targets"]}) != len(record["targets"]):
        raise AuthoringPublicationError("Authoring publication target is repeated")
    return record


def prepare(root: Path, *, attempt_id: str, operation_id: str,
            frozen_identity: str, candidates: dict[str, bytes],
            require_existing: bool = False) -> str:
    """Freeze file intents before replacing any file; exact recovery reuses the journal."""
    root = Path(root)
    journal_id = _journal_key(attempt_id=attempt_id, operation_id=operation_id, frozen_identity=frozen_identity)
    if not isinstance(candidates, dict) or not 1 <= len(candidates) <= MAX_FILES:
        raise AuthoringPublicationError("Authoring publication target count is invalid")
    directory = _journal_directory(root)
    path = _path(root, ".easel/authoring-publications/" + journal_id + ".json")
    if path.exists():
        existing = _read_journal(root, journal_id)
        proposed = {name: _digest(value) for name, value in candidates.items()
                    if isinstance(value, bytes)}
        if proposed != {row["path"]: row["after_sha256"] for row in existing["targets"]}:
            raise AuthoringPublicationError("Authoring retry changed its frozen candidates")
        return journal_id
    if require_existing:
        raise AuthoringPublicationError("Previously promoted native file lost its original journal")
    total, targets = 0, []
    for relative, candidate in sorted(candidates.items()):
        _check_name(relative)
        _validate_candidate(relative, candidate)
        total += len(candidate)
        if total > MAX_TOTAL_BYTES:
            raise AuthoringPublicationError("Authoring candidates exceed total capacity")
        before = _bytes(_path(root, relative))
        targets.append({"path": relative, "before_sha256": _digest(before) if before is not None else None,
                        "after_sha256": _digest(candidate),
                        "candidate_b64": base64.b64encode(candidate).decode("ascii")})
    record = {"schema": SCHEMA, "journal_id": journal_id, "attempt_id": attempt_id,
              "operation_id": operation_id, "frozen_identity": frozen_identity,
              "targets": targets}
    _atomic_create(path, _encode(record))
    return journal_id


def publish(root: Path, journal_id: str) -> dict:
    """Idempotently publish all candidates; mixed old/new files are legitimate after a crash."""
    root = Path(root)
    directory = _journal_directory(root)
    lock = _path(root, ".easel/authoring-publications/.publication-lock")
    with lock.open("a+b") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            record = _read_journal(root, journal_id)
            desired = []
            for item in record["targets"]:
                path = _path(root, item["path"])
                content = _bytes(path)
                digest = _digest(content) if content is not None else None
                if digest not in {item["before_sha256"], item["after_sha256"]}:
                    raise AuthoringPublicationError("An unrelated writer changed an Authoring publication file")
                desired.append((path, base64.b64decode(item["candidate_b64"], validate=True), digest))
            for path, candidate, digest in desired:
                # The initial multi-file preflight is not a filesystem CAS.
                # Re-verify each exact previous byte snapshot immediately before replacement.
                now = _bytes(_path(root, str(path.relative_to(root))))
                if (_digest(now) if now is not None else None) != digest:
                    raise AuthoringPublicationError("Another writer changed the source during publication")
                if digest != _digest(candidate):
                    _replace(path, candidate)
            completed = {"schema": SCHEMA, "journal_id": journal_id,
                         "journal_sha256": _digest(_encode(record)),
                         "after": {item["path"]: item["after_sha256"] for item in record["targets"]}}
            key = directory / (journal_id + "-complete.json")
            if key.is_symlink():
                raise AuthoringPublicationError("Authoring completion reference changed to symlink")
            if key.exists():
                if _bytes(key) != _encode(completed):
                    raise AuthoringPublicationError("Authoring completion proof changed")
            else:
                _atomic_create(key, _encode(completed))
            return completed
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def verify(root: Path, journal_id: str) -> dict:
    root = Path(root)
    record = _read_journal(root, journal_id)
    proof_path = _path(root, ".easel/authoring-publications/" + journal_id + "-complete.json")
    if not proof_path.is_file():
        raise AuthoringPublicationError("Authoring publication was not completed")
    proof = json.loads(_bytes(proof_path))
    if (proof != {"schema": SCHEMA, "journal_id": journal_id,
                  "journal_sha256": _digest(_encode(record)),
                  "after": {item["path"]: item["after_sha256"] for item in record["targets"]}}):
        raise AuthoringPublicationError("Authoring publication completion record changed")
    for item in record["targets"]:
        current = _bytes(_path(root, item["path"]))
        if current is None or _digest(current) != item["after_sha256"]:
            raise AuthoringPublicationError("Authoring published bytes no longer match the immutable intent")
    return proof
