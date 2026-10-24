"""Explicitly refresh the existing SFX text index; never modify catalog/media."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from easel.materials.domain import MediaType
from easel.materials.library import LibraryVisibility, UseContext
from easel.materials.local_embedding import LocalSfxEmbedding
from easel.production.materials import MaterialService


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--model-path', type=Path, required=True)
    parser.add_argument('--owner', default='local')
    parser.add_argument('--profile')
    args = parser.parse_args()
    root = args.library.expanduser().resolve(strict=True)
    if not (root / 'catalog.db').is_file():
        parser.error('Existing V2 catalog required')
    index = root / 'semantic-index.db'
    if index.is_file():
        backup = index.with_name('semantic-index.backup-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f') + '.db')
        with sqlite3.connect(f'file:{index}?mode=ro', uri=True) as source, sqlite3.connect(backup) as dest:
            source.backup(dest)
    service = MaterialService(root)
    # Retrieval acceptance is calibrated separately; indexing does not search.
    provider = LocalSfxEmbedding(args.model_path, minimum_score=1.)
    updated = service.index.rebuild(LibraryVisibility(owner_id=args.owner, profile_ref=args.profile),
        provider, context=UseContext(work_id='sfx-index-maintenance'),
        media_type=MediaType.AUDIO, audio_role='sfx', skip_fresh=True)
    print(f'updated_sfx_vectors={len(updated)}; catalog and media retained')


if __name__ == '__main__':
    main()
