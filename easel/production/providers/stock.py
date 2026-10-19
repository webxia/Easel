"""External stock and explicitly reviewed public sources.

Pexels mapping adapted from V1 providers/pexels.py at 57c8e2ad (Apache-2.0).
Provider listing plus the recorded license policy is evidence; arbitrary public
URLs never acquire a license merely because a download succeeded.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import re
from typing import Literal
from typing import Protocol
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field

from easel.materials.domain import CandidateSource, MediaType, RightsEvidence, RightsInfo, RightsStatus, SemanticInfo


class StockUnavailable(ValueError):
    def __init__(self, message: str, *, code: str = "source_unavailable"):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ExternalCandidate:
    candidate_id: str
    media_type: MediaType
    download_url: str
    source: CandidateSource
    rights: RightsInfo
    semantic: SemanticInfo = field(default_factory=SemanticInfo)


class StockProvider(Protocol):
    provider_id: str
    allowed_hosts: tuple[str, ...]

    def search(self, query: str, *, media_type: MediaType, limit: int) -> tuple[ExternalCandidate, ...]: ...


def _https_url(value: object, hosts: tuple[str, ...]) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = urlsplit(value)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or parsed.port not in (None, 443) or parsed.fragment):
            return None
        if any(parsed.hostname == host or parsed.hostname.endswith("." + host) for host in hosts):
            return value
    except ValueError:
        pass
    return None


class PexelsStockProvider:
    provider_id = "pexels"
    allowed_hosts = ("pexels.com",)
    media_types = frozenset({MediaType.IMAGE, MediaType.VIDEO})
    license_url = "https://www.pexels.com/license/"
    # Source policy reviewed during migration; listing evidence is dated per hit.
    license_policy_version = "pexels-license-2026-10-17"

    def __init__(self, api_key: str, *, transport: httpx.BaseTransport | None = None, timeout: float = 20):
        self._key, self._transport, self._timeout = api_key.strip(), transport, timeout

    @property
    def available(self):
        return bool(self._key)

    def search(self, query: str, *, media_type: MediaType, limit: int = 8) -> tuple[ExternalCandidate, ...]:
        if not self.available:
            raise StockUnavailable("capability_unavailable: Pexels is not configured", code="capability_unavailable")
        if media_type not in {MediaType.IMAGE, MediaType.VIDEO}:
            raise StockUnavailable("capability_unavailable: Pexels modality is unsupported", code="capability_unavailable")
        if not query.strip() or not 1 <= limit <= 80:
            raise ValueError("Invalid Pexels search input")
        # An explicitly supplied licensed stock page is an exact provider lookup,
        # never an arbitrary URL fetch or another broad keyword search.
        exact = None
        if query.strip().lower().startswith(('http://','https://')):
            match = re.fullmatch(r'https://(?:www\.)?pexels\.com/video/(?:[a-z0-9-]+-)?([0-9]{1,12})/?',query.strip())
            if media_type is not MediaType.VIDEO or not match:
                raise ValueError('Expected a canonical Pexels video page without credentials, query or fragment')
            exact = match[1]
        endpoint = "/v1/search" if media_type is MediaType.IMAGE else "/videos/search"
        if exact:endpoint = '/v1/videos/videos/' + exact
        try:
            with httpx.Client(transport=self._transport, trust_env=False, follow_redirects=False, timeout=self._timeout) as client:
                with client.stream("GET", "https://api.pexels.com" + endpoint,
                    params={} if exact else {"query": query, "per_page": limit, "page": 1}, headers={"Authorization": self._key}) as response:
                    if response.status_code != 200:
                        raise StockUnavailable(f"Pexels search returned HTTP {response.status_code}")
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        body.extend(chunk)
                        if len(body) > 4 * 1024 * 1024:
                            raise StockUnavailable("Pexels search response is too large")
            import json
            payload = json.loads(body)
        except (httpx.HTTPError, ValueError) as exc:
            raise StockUnavailable("Pexels search did not return a valid response") from exc
        if exact and (not isinstance(payload,dict) or str(payload.get('id'))!=exact):
            raise StockUnavailable('Pexels returned a different stock identity')
        values = [payload] if exact else payload.get("photos" if media_type is MediaType.IMAGE else "videos") if isinstance(payload, dict) else None
        if not isinstance(values, list):
            raise StockUnavailable("Pexels search response has an invalid shape")
        candidates = []
        for item in values[:limit]:
            if not isinstance(item, dict) or type(item.get("id")) not in {str, int}:
                continue
            source_page = _https_url(item.get("url"), self.allowed_hosts)
            if not source_page:
                continue
            if media_type is MediaType.IMAGE:
                src = item.get("src")
                download = _https_url(src.get("original"), self.allowed_hosts) if isinstance(src, dict) else None
                creator = item.get("photographer")
            else:
                files = item.get("video_files")
                options = [f for f in files if isinstance(f, dict) and f.get("file_type") == "video/mp4"] if isinstance(files, list) else []
                # Search results have the same arbitrary SD-first ordering as
                # exact lookups. Prefer 1080p-or-better without needlessly
                # downloading 4K when an adequate 1080p stream is available.
                def stream_rank(f):
                    width, height = f.get('width') or 0, f.get('height') or 0
                    area = width * height
                    adequate = min(width, height) >= 1080
                    return (not adequate, area if adequate else -area)
                options.sort(key=stream_rank)
                download = next((_https_url(f.get("link"), self.allowed_hosts) for f in options
                                 if _https_url(f.get("link"), self.allowed_hosts)), None)
                creator = item.get("user", {}).get("name") if isinstance(item.get("user"), dict) else None
            if not download:
                continue
            source = CandidateSource(kind="stock", provider=self.provider_id, provider_asset_id=str(item["id"]),
                                     source_page=source_page, creator=creator if isinstance(creator, str) else None)
            rights = RightsInfo(status=RightsStatus.KNOWN, license_name="Pexels License", license_url=self.license_url,
                usage_constraints=("no_redistribution_as_stock", "no_endorsement", "no_trademark_use",
                                   "identifiable_person_restriction", "no_unaltered_resale"),
                evidence=(RightsEvidence(kind="asset_provider_listing", reference=source_page,
                                         observed_at=datetime.now(timezone.utc)),
                          RightsEvidence(kind="asset_provider_license_terms", reference=self.license_url,
                                         summary=self.license_policy_version)))
            candidates.append(ExternalCandidate("pexels:" + str(item["id"]), media_type, download, source, rights,
                SemanticInfo(caption=item.get("alt") if isinstance(item.get("alt"), str) else None)))
        return tuple(candidates)


class _ReviewedEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    candidate_id: str = Field(min_length=1, max_length=256)
    media_type: MediaType
    download_url: str = Field(min_length=1, max_length=4096)
    source: CandidateSource
    rights: RightsInfo
    semantic: SemanticInfo = Field(default_factory=SemanticInfo)


class _ReviewedConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal[1]
    allowed_hosts: list[str] = Field(min_length=1, max_length=32)
    candidates: list[_ReviewedEntry] = Field(min_length=1, max_length=80)


class ReviewedPublicSources:
    """Operator-reviewed, bounded public source records, never an URL crawler.

    Configured records need source identity and asset-specific rights evidence.
    Actual use still passes the common rights, media and DNS/redirect checks.
    """

    provider_id = "reviewed_public"

    def __init__(self, candidates: tuple[ExternalCandidate, ...], *, allowed_hosts: tuple[str, ...]):
        self.candidates, self.allowed_hosts = candidates, allowed_hosts
        self.media_types = frozenset(c.media_type for c in candidates)

    @classmethod
    def from_json(cls, raw: str):
        config = _ReviewedConfiguration.model_validate_json(raw)
        hosts = tuple(config.allowed_hosts)
        for host in hosts:
            if (not re.fullmatch(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}", host)
                    or host.endswith((".local", ".localhost", ".internal"))):
                raise ValueError("Public source hosts must be explicit DNS names")
        if len(set(hosts)) != len(hosts):
            raise ValueError("Public source hosts must be distinct")
        candidates = []
        for item in config.candidates:
            rights, source = item.rights, item.source
            if (not item.candidate_id.strip() or not _https_url(item.download_url, hosts)
                    or not _https_url(source.source_page, hosts)
                    or source.kind not in {"public", "external"} or source.provider != cls.provider_id
                    or not source.provider_asset_id or not source.provider_asset_id.strip()
                    or not source.creator or not source.creator.strip()):
                raise ValueError("Public source identity or URL is not reviewed")
            if (rights.status not in {RightsStatus.KNOWN, RightsStatus.PUBLIC_DOMAIN, RightsStatus.ATTRIBUTION_REQUIRED}
                    or not rights.evidence or not any(e.kind.startswith("asset_") and e.reference.strip() for e in rights.evidence)
                    or rights.status is RightsStatus.KNOWN and not rights.license_name
                    or (rights.status is RightsStatus.ATTRIBUTION_REQUIRED or rights.attribution_required)
                    and (not rights.attribution_required or not rights.attribution_text)):
                raise ValueError("Public source needs asset-specific rights and exact credit evidence")
            candidates.append(ExternalCandidate(item.candidate_id, item.media_type, item.download_url,
                                                source, rights, item.semantic))
        if len({c.candidate_id for c in candidates}) != len(candidates):
            raise ValueError("Public source candidate IDs must be distinct")
        return cls(tuple(candidates), allowed_hosts=hosts)

    def search(self, query: str, *, media_type: MediaType, limit: int = 8):
        if not query.strip() or not 1 <= limit <= 80:
            raise ValueError("Invalid reviewed public source search")
        return tuple(c for c in self.candidates if c.media_type is media_type)[:limit]
