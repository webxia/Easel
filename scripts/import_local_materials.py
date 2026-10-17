"""Explicit, non-destructive migration of rights-verified local media into V2.

No secrets or source file contents are logged; no external requests are made.
Only media with matching SHA-256 rights sidecars may be published owner-wide.
Legacy catalogs and production databases are not migrated or modified.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from easel.materials.domain import CandidateSource, MediaType, RightsInfo, RightsStatus, SemanticInfo, TechnicalStatus
from easel.materials.library import LibraryVisibility, PromotionConsent, UseContext
from easel.materials.store import MaterialFileStore, digest_file
from easel.production.materials import MaterialService

EXTENSIONS = {".mp3": MediaType.AUDIO, ".wav": MediaType.AUDIO, ".m4a": MediaType.AUDIO,
    ".flac": MediaType.AUDIO, ".png": MediaType.IMAGE, ".jpg": MediaType.IMAGE,
    ".jpeg": MediaType.IMAGE, ".webp": MediaType.IMAGE, ".mp4": MediaType.VIDEO,
    ".mov": MediaType.VIDEO, ".webm": MediaType.VIDEO}


def _roots(env: Path) -> tuple[Path, ...]:
    if not env.is_file() or any(p.is_symlink() for p in (env, *env.parents)):
        raise ValueError("Legacy configuration is unavailable or linked")
    raw = ""
    for line in env.read_text(encoding="utf-8-sig").splitlines():
        match = re.match(r"^\s*(?:export\s+)?EASEL_MATERIAL_LOCAL_ROOTS\s*=\s*(.*)$", line)
        if match:
            raw = match.group(1).strip().strip("'\"")
    if not raw:
        raise ValueError("Legacy local media roots are not configured")
    names = json.loads(raw) if raw.startswith("[") else re.split(r"[,;]+", raw)
    if not isinstance(names, list) or len(names) > 16:
        raise ValueError("Invalid number of legacy local roots")
    roots = []
    for name in names:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Invalid local root name")
        path = Path(name).expanduser().absolute()
        if not path.is_dir() or any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError("Legacy local root is missing or linked")
        roots.append(path)
    return tuple(roots)


def _sidecars(root: Path):
    """Only bounded JSON sidecars; do not trust path-like fields inside JSON."""
    metadata, licenses = {}, {}
    for item in sorted(root.rglob("*.json")):
        if item.is_symlink() or not item.is_file() or item.stat().st_size > 256 * 1024:
            continue
        try:
            value = json.loads(item.read_text(encoding="utf-8"))
        except (ValueError, OSError, UnicodeError):
            continue
        if not isinstance(value, dict):
            continue
        if isinstance(value.get("file"), str):
            metadata.setdefault(Path(value["file"]).name, []).append(value)
        if isinstance(value.get("asset_sha256"), str) and isinstance(value.get("rights"), dict):
            licenses.setdefault(value["asset_sha256"].lower(), []).append(value["rights"])
    return metadata, licenses


def _admissible(media: Path, relative: str, sha: str, metadata, licenses):
    meta = metadata.get(media.name, ())
    rights_values = licenses.get(sha, ())
    if len(meta) != 1 or len(rights_values) != 1:
        return None
    source = meta[0]
    try:
        rights = RightsInfo.model_validate_json(json.dumps(rights_values[0]))
    except ValueError:
        return None
    if (rights.status not in {RightsStatus.KNOWN, RightsStatus.PUBLIC_DOMAIN, RightsStatus.ATTRIBUTION_REQUIRED}
            or not rights.evidence or not any(e.kind.startswith("asset_") for e in rights.evidence)
            or rights.attribution_required and not rights.attribution_text
            or rights.status is RightsStatus.KNOWN and not rights.license_name):
        return None
    url = source.get("source_url")
    if not isinstance(url, str):
        return None
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        return None
    # Source-supplied rights must name a real content license, not a fabricated default.
    if not isinstance(rights.license_url, str) or not isinstance(source.get('license_url'), str):
        return None
    rights_license = urlsplit(rights.license_url)
    source_license = urlsplit(source["license_url"])
    if (rights_license.scheme != "https" or source_license.scheme != "https"
            or rights_license.hostname != source_license.hostname
            or rights_license.path.rstrip("/") != source_license.path.rstrip("/")):
        return None
    if rights.status is RightsStatus.ATTRIBUTION_REQUIRED or rights.attribution_required:
        creator_name = source.get('creator')
        original_credit = rights.attribution_text or ''
        if not isinstance(creator_name, str) or creator_name.casefold() not in original_credit.casefold():
            return None
        # Preserve the source's exact credit; append only its separately
        # recorded asset URL so V2 can verify and export a complete credit.
        # This does not fabricate a new license or change the original sidecar.
        if url not in original_credit:
            if parts.query or parts.fragment:
                return None
            rights = rights.model_copy(update={'attribution_text': original_credit.rstrip() + '\nSource: ' + url})
    origin = CandidateSource(kind="local_import", provider="legacy_local",
        provider_asset_id=str(source.get("id") or sha), source_page=url,
        creator=source.get("creator") if isinstance(source.get("creator"), str) else None)
    mood = source.get("mood")
    semantic = SemanticInfo(caption=source.get("title") if isinstance(source.get("title"), str) else None,
        tags=tuple(x for x in mood[:12] if isinstance(x, str) and x.strip()) if isinstance(mood, list) else ())
    return origin, rights, semantic


def migrate(env: Path, target: Path, *, execute: bool) -> dict[str, int]:
    roots = _roots(env)
    stats: Counter[str] = Counter()
    material = None
    scope = LibraryVisibility(owner_id="local")
    for root in roots:
        files = MaterialFileStore(root)
        metadata, licenses = _sidecars(root)
        for media in sorted(root.rglob("*")):
            if media.suffix.lower() not in EXTENSIONS or not media.is_file():
                continue
            stats["seen"] += 1
            if media.is_symlink() or any(part.is_symlink() for part in media.parents if part.is_relative_to(root)):
                stats["blocked_unsafe_path"] += 1
                continue
            try:
                relative = media.relative_to(root).as_posix()
                verified = files.resolve_asset_locator(relative)
                digest = digest_file(verified)
                source = _admissible(verified, relative, digest, metadata, licenses)
                if source is None:
                    stats["blocked_rights_or_source"] += 1
                    continue
                stats["rights_verified"] += 1
                if not execute:
                    continue
                if material is None:
                    material = MaterialService(target)
                context = UseContext(work_id="local-import-" + digest[:32])
                origin, rights, semantic = source
                handle = material.ingest_input(source_root=root, relative_path=relative,
                    visibility=scope, context=context, media_type=EXTENSIONS[media.suffix.lower()],
                    source=origin, rights=rights, semantic=semantic, expected_sha256=digest)
                if handle.asset.technical.status is not TechnicalStatus.PASSED:
                    stats["blocked_technical"] += 1
                    continue
                material.catalog.promote(handle.asset_ref, scope=scope, context=context, owner_shared=True,
                    consent=PromotionConsent(authorized=True, actor_id="local-owner",
                        purpose="owner_shared_import", consented_at=datetime.now(timezone.utc)))
                stats["imported_or_already_present"] += 1
            except (OSError, ValueError, TypeError, RuntimeError):
                stats["blocked_validation"] += 1
    return dict(stats)


def main():
    parser = argparse.ArgumentParser(description="Import rights-verified local media without touching legacy data")
    parser.add_argument("--legacy-env", type=Path, required=True)
    parser.add_argument("--target", type=Path, default=Path(__file__).resolve().parents[1] /
                        "outputs" / "_production" / "materials")
    parser.add_argument("--execute", action="store_true", help="Opt in to copy, inspect and share verified material")
    args = parser.parse_args()
    result = migrate(args.legacy_env, args.target, execute=args.execute)
    print(json.dumps({"mode": "execute" if args.execute else "dry_run", **result}, sort_keys=True))


if __name__ == "__main__":
    main()
