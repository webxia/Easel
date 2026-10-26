"""Optional local text embeddings. Preparing weights is an explicit offline step."""
from __future__ import annotations

import hashlib
import json
import logging
import math
import re
from pathlib import Path
from threading import Lock


class LocalSfxEmbedding:
    provider_id = 'local-sentence-transformers'
    dimensions = 1024

    def __init__(self, path: str | Path, *, minimum_score: float):
        self.path = Path(path).expanduser().resolve(strict=True)
        identity = json.loads((self.path / 'easel-model-identity.json').read_text())
        if (identity.get('model_id') != 'BAAI/bge-m3'
                or identity.get('dimensions') != self.dimensions
                or not isinstance(identity.get('revision'), str) or not identity['revision'].strip()):
            raise ValueError('Unsupported local embedding identity')
        if not math.isfinite(minimum_score) or not -1 <= minimum_score <= 1:
            raise ValueError('Invalid calibrated retrieval score')
        from importlib.metadata import version
        self.model_version = hashlib.sha256(json.dumps({
            'identity': identity, 'encoder': version('sentence-transformers'),
            'encoding': 'cpu-cls-normalized-caption-v2',
        }, sort_keys=True).encode()).hexdigest()
        self.minimum_score = minimum_score
        self._model = None
        self._failed = False
        self._lock = Lock()

    @staticmethod
    def document_text(asset):
        # File paths and pack labels describe storage, not the sound. This is
        # a derived projection only; source metadata remains intact.
        return re.sub(r'\s+', ' ', re.sub(
            r'\b(?:foley|household|technology|electronic|\d+)\b', ' ',
            asset.semantic.caption or '', flags=re.I)).strip()

    def embed(self, text):
        with self._lock:
            if self._failed:
                raise RuntimeError('Local embedding unavailable')
            try:
                if self._model is None:
                    from sentence_transformers import SentenceTransformer
                    model = SentenceTransformer(str(self.path), device='cpu',
                        local_files_only=True, trust_remote_code=False)
                    if model.get_sentence_embedding_dimension() != self.dimensions:
                        raise ValueError('Unexpected embedding dimensions')
                    self._model = model
                return self._model.encode(text, normalize_embeddings=True,
                    show_progress_bar=False).tolist()
            except Exception:
                self._failed = True
                raise RuntimeError('Local embedding unavailable') from None


def configured_sfx_embedding(settings):
    """Never download or load a model during runtime composition."""
    if settings.get('EASEL_SFX_SEMANTIC_ENABLED', '0').strip() != '1':
        return None
    try:
        return LocalSfxEmbedding(settings['EASEL_SFX_EMBEDDING_PATH'],
            minimum_score=float(settings['EASEL_SFX_SEMANTIC_MIN_SCORE']))
    except (KeyError, ValueError, OSError, ImportError):
        logging.getLogger(__name__).warning('Local SFX semantic configuration unavailable; original search retained')
        return None
