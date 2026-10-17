"""Pixabay image/video stock adapter with bounded 24h response caching.

Adapted from the V1 Pixabay provider's search/credit semantics. The returned
license is a source-specific claim, not an exemption from Rights admission.
No request is sent while configuring the provider.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
from urllib.parse import urlsplit

import httpx

from easel.materials.domain import CandidateSource, MediaType, RightsEvidence, RightsInfo, RightsStatus, SemanticInfo
from easel.materials.store import reject_symlinks
from .stock import ExternalCandidate, StockUnavailable, _https_url


class PixabayStockProvider:
    provider_id = "pixabay"
    allowed_hosts = ("pixabay.com",)
    media_types = frozenset({MediaType.IMAGE, MediaType.VIDEO})
    license_url = "https://pixabay.com/service/terms/"
    license_policy_version = "pixabay-content-license-2026-10-17"
    cache_seconds = 24 * 60 * 60

    def __init__(self, api_key: str, *, transport: httpx.BaseTransport | None = None,
                 timeout: float = 20.0, cache_root: Path | None = None, clock=None):
        if timeout <= 0:
            raise ValueError("Pixabay timeout must be positive")
        self._key = api_key.strip()
        self._transport, self._timeout = transport, timeout
        self._cache_root = Path(cache_root).expanduser().absolute() if cache_root else None
        self._clock = clock or time.time
        self._memory_cache: dict[str, tuple[float, tuple[ExternalCandidate, ...]]] = {}

    @property
    def available(self):
        return bool(self._key)

    def _cache_key(self, query: str, media_type: MediaType, limit: int) -> str:
        # The key itself is never serialized or returned.
        data = json.dumps([self._key, query, media_type.value, limit], ensure_ascii=False)
        return hashlib.sha256(data.encode()).hexdigest()

    def _cache_path(self, key: str) -> Path | None:
        if self._cache_root is None:
            return None
        if any(p.is_symlink() for p in (self._cache_root, *self._cache_root.parents)):
            raise StockUnavailable("Pixabay cache root is unsafe")
        self._cache_root.mkdir(parents=True, exist_ok=True)
        target = self._cache_root / (key + ".json")
        reject_symlinks(self._cache_root, target)
        return target

    @staticmethod
    def _encode(candidates: tuple[ExternalCandidate, ...]):
        return [{"candidate_id": c.candidate_id, "media_type": c.media_type.value,
                 "download_url": c.download_url, "source": c.source.model_dump(mode="json"),
                 "rights": c.rights.model_dump(mode="json"), "semantic": c.semantic.model_dump(mode="json")}
                for c in candidates]

    @staticmethod
    def _decode(values):
        if not isinstance(values, list) or len(values) > 80:
            raise ValueError("Invalid cached candidates")
        return tuple(ExternalCandidate(
            item["candidate_id"], MediaType(item["media_type"]), item["download_url"],
            CandidateSource.model_validate_json(json.dumps(item["source"])),
            RightsInfo.model_validate_json(json.dumps(item["rights"])),
            SemanticInfo.model_validate_json(json.dumps(item["semantic"]))) for item in values)

    def _cached(self, key: str, media_type: MediaType):
        stored = self._memory_cache.get(key)
        if stored and 0 <= self._clock() - stored[0] < self.cache_seconds:
            return stored[1]
        path = self._cache_path(key)
        if path is None or not path.is_file():
            return None
        try:
            if path.stat().st_size > 1024 * 1024:
                raise ValueError("Pixabay cache exceeds limit")
            data = json.loads(path.read_text(encoding="utf-8"))
            timestamp = data["saved_at"]
            if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)):
                raise ValueError("Invalid cache timestamp")
            if not 0 <= self._clock() - timestamp < self.cache_seconds:
                return None
            result = self._decode(data["candidates"])
            for c in result:
                if (c.media_type is not media_type or c.source.kind != 'stock'
                        or not c.candidate_id.startswith('pixabay:')
                        or c.rights.status is not RightsStatus.KNOWN
                        or not c.rights.evidence or not self._public_url(c.download_url)
                        or not self._public_url(c.source.source_page) or c.source.provider != self.provider_id):
                    raise ValueError("Invalid cached source")
            self._memory_cache[key] = (timestamp, result)
            return result
        except (OSError, TypeError, ValueError, KeyError) as exc:
            raise StockUnavailable("Pixabay local search cache is invalid; no new request sent") from exc

    def _save(self, key: str, candidates: tuple[ExternalCandidate, ...]):
        saved_at = self._clock()
        path = self._cache_path(key)
        if path is not None:
            payload = json.dumps({"saved_at": saved_at, "candidates": self._encode(candidates)},
                                 ensure_ascii=False, separators=(",", ":"))
            if len(payload.encode("utf-8")) > 1024 * 1024:
                raise StockUnavailable("Pixabay cache exceeds size limit")
            fd, temporary = tempfile.mkstemp(prefix=".pixabay-", dir=path.parent)
            try:
                os.chmod(temporary, 0o600)
                with os.fdopen(fd, "w", encoding="utf-8") as output:
                    output.write(payload)
                    output.flush()
                    os.fsync(output.fileno())
                reject_symlinks(self._cache_root, path)
                os.replace(temporary, path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        self._memory_cache[key] = (saved_at, candidates)

    @classmethod
    def _public_url(cls, raw):
        url = _https_url(raw, cls.allowed_hosts)
        if url is None:
            return None
        parts = urlsplit(url)
        # Avoid archiving token-bearing query/fragment URLs in the local cache.
        return url if not parts.query and not parts.fragment else None

    def _candidates(self, body, media_type: MediaType, limit: int):
        hits = body.get("hits") if isinstance(body, dict) else None
        if not isinstance(hits, list):
            raise StockUnavailable("Pixabay search response shape is invalid")
        candidates = []
        for item in hits[:limit]:
            if not isinstance(item, dict) or type(item.get("id")) not in (str, int):
                continue
            page = self._public_url(item.get("pageURL"))
            if not page:
                continue
            if media_type is MediaType.IMAGE:
                download = self._public_url(item.get("largeImageURL")) or self._public_url(item.get("webformatURL"))
            else:
                videos = item.get("videos")
                download = None
                if isinstance(videos, dict):
                    for quality in ("large", "medium", "small", "tiny"):
                        option = videos.get(quality)
                        if isinstance(option, dict):
                            download = self._public_url(option.get("url"))
                        if download:
                            break
            if not download:
                continue
            creator = item.get("user")
            tags = item.get("tags")
            terms = tuple(tag.strip() for tag in tags.split(",") if tag.strip())[:16] if isinstance(tags, str) else ()
            source = CandidateSource(kind="stock", provider=self.provider_id,
                provider_asset_id=str(item["id"]), source_page=page,
                creator=creator if isinstance(creator, str) else None)
            rights = RightsInfo(status=RightsStatus.KNOWN, license_name="Pixabay Content License",
                license_url=self.license_url,
                usage_constraints=("no_redistribution_as_stock", "no_endorsement",
                                   "no_trademark_use", "identifiable_person_restriction"),
                evidence=(RightsEvidence(kind="asset_provider_listing", reference=page,
                                         observed_at=datetime.now(timezone.utc)),
                          RightsEvidence(kind="asset_provider_license_terms", reference=self.license_url,
                                         summary=self.license_policy_version)))
            candidates.append(ExternalCandidate("pixabay:" + str(item["id"]), media_type, download,
                source, rights, SemanticInfo(caption=tags if isinstance(tags, str) else None, tags=terms)))
        return tuple(candidates)

    def search(self, query: str, *, media_type: MediaType, limit: int = 8):
        if not self.available:
            raise StockUnavailable("capability_unavailable: Pixabay is not configured", code="capability_unavailable")
        if media_type not in self.media_types:
            raise StockUnavailable("capability_unavailable: Pixabay modality is unsupported", code="capability_unavailable")
        if not query.strip() or len(query) > 100 or not 1 <= limit <= 80:
            raise ValueError("Invalid Pixabay search input")
        query = query.strip()
        key = self._cache_key(query, media_type, limit)
        cached = self._cached(key, media_type)
        if cached is not None:
            return cached
        path = "/api/" if media_type is MediaType.IMAGE else "/api/videos/"
        try:
            with httpx.Client(transport=self._transport, trust_env=False, follow_redirects=False, timeout=self._timeout) as client:
                with client.stream("GET", "https://pixabay.com" + path,
                    params={"key": self._key, "q": query, "per_page": max(3, limit), "page": 1, "safesearch": "true"}) as response:
                    if response.status_code != 200:
                        raise StockUnavailable(f"Pixabay search returned HTTP {response.status_code}")
                    data = bytearray()
                    for piece in response.iter_bytes():
                        data.extend(piece)
                        if len(data) > 4 * 1024 * 1024:
                            raise StockUnavailable("Pixabay search response is too large")
            body = json.loads(data)
        except StockUnavailable:
            raise
        except (httpx.HTTPError, TypeError, ValueError):
            raise StockUnavailable("Pixabay search returned an invalid response") from None
        result = self._candidates(body, media_type, limit)
        self._save(key, result)
        return result
