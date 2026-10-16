"""Safe local files, adapted from V1 store.py and acquisition.py (57c8e2ad).

Apache-2.0, see repository LICENSE. V2 keeps locator, digest and atomic-copy
behavior; no Attempt, generation journal, plan or budget is stored here.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath
from urllib.parse import urlsplit, urlunsplit


class MaterialStoreError(ValueError):
    """Invalid or unavailable material files; never includes raw input bytes."""


class RemoteURLPolicy:
    @staticmethod
    def redact(url: str | None) -> str | None:
        if not url:
            return None
        try:
            parsed = urlsplit(url)
            host = parsed.hostname or ""
            if parsed.port:
                host = f"{host}:{parsed.port}"
            return urlunsplit((parsed.scheme, host, parsed.path, "[REDACTED]" if parsed.query else "", ""))
        except ValueError:
            return "[REDACTED_INVALID_URL]"


def canonical_locator(locator: str) -> str:
    if not isinstance(locator, str) or not locator or "\\" in locator or re.match(r"^[A-Za-z]:", locator):
        raise MaterialStoreError("Locator must be a POSIX relative path")
    path = PurePosixPath(locator)
    if path.is_absolute() or locator.startswith("~") or any(p in {"", ".", ".."} for p in locator.split("/")):
        raise MaterialStoreError("Locator must be canonical and relative")
    if path.as_posix() != locator:
        raise MaterialStoreError("Locator must be canonical and relative")
    return locator


def _comparison_path(path: PurePath) -> PurePath:
    """Compare equivalent resolved DOS paths without rewriting filesystem input.

    Windows non-strict resolve can retain the extended prefix when a SQLite
    sidecar disappears during resolution. Only that local absolute drive form
    is equivalent here; UNC and device namespaces retain their own anchors.
    """
    if isinstance(path, PureWindowsPath) and path.is_absolute() and re.fullmatch(r"\\\\\?\\[A-Za-z]:", path.drive):
        return PureWindowsPath(str(path)[4:])
    return path


def _reject_link(path: Path) -> None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        # A not-yet-created destination or disappearing SQLite sidecar is valid.
        return
    tag = getattr(info, "st_reparse_tag", 0)
    if stat.S_ISLNK(info.st_mode) or (tag and tag in (
        getattr(stat, "IO_REPARSE_TAG_SYMLINK", None),
        getattr(stat, "IO_REPARSE_TAG_MOUNT_POINT", None),
    )):
        raise MaterialStoreError("Symlinks and junctions are not allowed in material paths")


def reject_symlinks(root: Path, path: Path) -> None:
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise MaterialStoreError("Material path escapes its root") from exc
    current = root
    _reject_link(current)
    for part in relative.parts:
        current = current / part
        _reject_link(current)
    try:
        resolved_relative = _comparison_path(path.resolve(strict=False)).relative_to(_comparison_path(root))
        if ".." in resolved_relative.parts:
            raise ValueError("Unresolved parent component")
    except ValueError as exc:
        raise MaterialStoreError("Material path escapes its root") from exc


def digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class MaterialFileStore:
    """Access only files beneath a trusted root supplied by the input boundary.

    This class never accepts an arbitrary client absolute path. Constructors do
    not scan user directories or import old libraries.
    """

    def __init__(self, root: str | Path):
        provided = Path(root).expanduser().absolute()
        # Reject a symlink at any supplied component, including an in-root alias.
        for parent in (provided, *provided.parents):
            _reject_link(parent)
        if not provided.is_dir():
            raise MaterialStoreError("Material root must be an existing directory")
        self.root = provided.resolve(strict=True)

    def resolve_asset_locator(self, locator: str) -> Path:
        path = self.root / canonical_locator(locator)
        reject_symlinks(self.root, path)
        if not path.is_file():
            raise MaterialStoreError("Material locator is not a regular file")
        return path

    def read_acquisition_evidence(self, asset_id: str) -> dict:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", asset_id):
            raise MaterialStoreError("Invalid asset ID")
        path = self.root / "evidence" / f"{asset_id}.json"
        reject_symlinks(self.root, path)
        if not path.exists():
            return {}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise MaterialStoreError("Invalid acquisition evidence") from exc
        if not isinstance(value, dict):
            raise MaterialStoreError("Acquisition evidence must be an object")
        return value

    def stage_object(self, source: Path, locator: str, expected_sha256: str, expected_size: int) -> Path:
        """Copy, verify the temporary bytes, then publish an immutable object.

        V1's content-addressed staging is retained, with validation moved before
        replace so changed source bytes cannot briefly overwrite a valid object.
        """
        target = self.root / canonical_locator(locator)
        reject_symlinks(self.root, target)
        target.parent.mkdir(parents=True, exist_ok=True)
        reject_symlinks(self.root, target)
        if target.exists():
            if not target.is_file() or target.stat().st_size != expected_size or digest_file(target) != expected_sha256:
                raise MaterialStoreError("Object path contains invalid content")
            return target
        descriptor, name = tempfile.mkstemp(prefix=".material-", suffix=".tmp", dir=target.parent)
        temporary = Path(name)
        try:
            # O_NOFOLLOW protects the final source component during this read.
            with os.fdopen(descriptor, "wb") as output:
                source_fd = os.open(source, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
                with os.fdopen(source_fd, "rb") as stream:
                    shutil.copyfileobj(stream, output)
                    output.flush()
                    os.fsync(output.fileno())
            if temporary.stat().st_size != expected_size or digest_file(temporary) != expected_sha256:
                raise MaterialStoreError("Source content changed while staging")
            reject_symlinks(self.root, target)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        return target
