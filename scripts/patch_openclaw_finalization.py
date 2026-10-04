"""Offline compatibility patch for OpenClaw 2026.9.4; never restart services.

A truncated current assistant must not be replaced by an older settled tool
batch when deciding whether to enter tool-disabled finalization.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

VERSION = '2026.9.4'
HEADER = 'function resolveSettledToolTerminalContinuationInstruction(params) {\n\tconst { attempt } = params;\n'
GUARD = ('\t// Easel compatibility: truncated execution is not settled finalization.\n'
         '\tif (resolveCurrentAttemptAssistant(attempt)?.stopReason === "length") return null;\n')


def patched_source(source: str) -> str:
    if source.count(HEADER) != 1:
        raise ValueError('Unsupported OpenClaw finalization function; no changes made')
    if GUARD in source:
        if source.count(GUARD) != 1 or HEADER + GUARD not in source:
            raise ValueError('Unexpected existing compatibility patch')
        return source
    if 'const { assistant, allToolsProvenSettled, failedToolNames, hasUnsettledToolError, intentionalTermination } = resolveSettledToolBatchEvidence(attempt);' not in source:
        raise ValueError('OpenClaw finalization contract changed; no changes made')
    return source.replace(HEADER, HEADER + GUARD, 1)


def patch_installation(root: Path, *, apply: bool = False) -> dict:
    if json.loads((root / 'package.json').read_text())['version'] != VERSION:
        raise ValueError('Only the inspected OpenClaw 2026.9.4 release is supported')
    candidates = [p for p in (root / 'dist').glob('builtin-openclaw-*.mjs')
                  if HEADER in p.read_text()]
    if len(candidates) != 1:
        raise ValueError('Expected exactly one OpenClaw finalization bundle')
    target = candidates[0]
    original = target.read_bytes()
    updated = patched_source(original.decode()).encode()
    state = 'already_patched' if updated == original else 'patch_required'
    if apply and updated != original:
        backup = target.with_name(target.name + '.easel-finalization-original')
        if backup.exists() and backup.read_bytes() != original:
            raise ValueError('Existing backup differs; refusing to overwrite installation')
        if not backup.exists():
            with backup.open('xb') as stream:
                stream.write(original)
        fd, name = tempfile.mkstemp(dir=target.parent, prefix='.easel-finalization-')
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(updated)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(name, target.stat().st_mode & 0o777)
            if target.read_bytes() != original:
                raise ValueError('Installation changed during patch; refusing replacement')
            os.replace(name, target)
        finally:
            Path(name).unlink(missing_ok=True)
        state = 'patched_on_disk'
    return {'state': state, 'path': str(target),
            'before_sha256': hashlib.sha256(original).hexdigest(),
            'after_sha256': hashlib.sha256(updated).hexdigest(),
            'service_restarted': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('installation', type=Path)
    parser.add_argument('--apply', action='store_true', help='Patch files only; no process operations')
    args = parser.parse_args()
    print(json.dumps(patch_installation(args.installation.resolve(), apply=args.apply), indent=2))
