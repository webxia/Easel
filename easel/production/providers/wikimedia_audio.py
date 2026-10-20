"""Wikimedia Commons audio stock: no account, conservative file-page license checks.

Searches only the official Action API with a compliant, identifying user-agent.
Only source-file-specific CC0 1.0 / CC BY 4.0 declarations qualify. A Commons
description is evidence of a declaration, not independent proof of ownership.
The existing MaterialSupply/MediaDownloader still enforces permission, DNS,
redirects, bytes, technical validity, and attribution before editor binding.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha1
from html.parser import HTMLParser
import json
import re
from urllib.parse import urlsplit, urlunsplit

import httpx

from easel.materials.domain import (CandidateSource, MediaType, RightsEvidence,
                                    RightsInfo, RightsStatus, SemanticInfo)
from .stock import ExternalCandidate, StockUnavailable, _https_url, http_failure_code, search_failure_code


class _PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.words: list[str] = []
    def handle_data(self, data: str):
        self.words.append(data)


def _plain(value: object, *, max_length: int = 300) -> str:
    if not isinstance(value, str) or len(value) > 4096:
        return ""
    parser = _PlainText()
    try:
        parser.feed(value)
        parser.close()
    except (ValueError, TypeError):
        return ""
    return re.sub(r"\s+", " ", " ".join(parser.words)).strip()[:max_length]


def _meta(data: dict, key: str) -> str:
    item = data.get(key, {})
    return _plain(item.get("value")) if isinstance(item, dict) else ""


class WikimediaAudioProvider:
    """Two explicit, role-scoped providers backed by Wikimedia Commons audio.

    User must authorize provider/model=stock/mode=search for this work.
    Search is deliberately limited to one API page, with no paid fallback,
    guessed license, scraping, or redirects. API identity is public project URL.
    """

    allowed_hosts = ("upload.wikimedia.org",)
    media_types = frozenset({MediaType.AUDIO})
    api_url = "https://commons.wikimedia.org/w/api.php"
    contact_url = "https://github.com/webxia/Easel"
    download_user_agent = 'EaselAudio/0.1 (https://github.com/webxia/Easel)'
    license_urls = {
        "CC0": "https://creativecommons.org/publicdomain/zero/1.0/",
        "CC0 1.0": "https://creativecommons.org/publicdomain/zero/1.0/",
        "CC BY 4.0": "https://creativecommons.org/licenses/by/4.0/",
    }

    def __init__(self, role: str, *, transport: httpx.BaseTransport | None = None, timeout: float = 20, proxy_url: str | None = None):
        if role not in {"music", "sfx"}:
            raise ValueError("Wikimedia audio role must be music or sfx")
        if not 0 < timeout <= 60:
            raise ValueError("Invalid Wikimedia API timeout")
        if proxy_url:
            from easel.materials.application.proxy import loopback_proxy
            loopback_proxy(proxy_url)
        self._proxy = proxy_url or None
        self.role = role
        self.provider_id = "wikimedia_bgm" if role == "music" else "wikimedia_sfx"
        self.audio_roles = frozenset({role})
        self._transport, self._timeout = transport, timeout

    def search(self, query: str, *, media_type: MediaType, limit: int = 8) -> tuple[ExternalCandidate, ...]:
        if media_type is not MediaType.AUDIO:
            raise StockUnavailable("Wikimedia audio supports audio only", code="capability_unavailable")
        if not isinstance(query, str) or not query.strip() or len(query) > 140 or not 1 <= limit <= 20:
            raise ValueError("Invalid Wikimedia audio query")
        # Preserve the director's query. Requiring a literal phrase 'sound effect'
        # suppresses otherwise legitimate Commons audio search hits.
        # Role isolation is provided by the distinct source identity.
        params = {
            "action": "query", "format": "json", "formatversion": 2,
            "generator": "search", "gsrsearch": f"{query.strip()} filetype:audio",
            "gsrnamespace": 6, "gsrlimit": 40,
            "prop": "imageinfo", "iiprop": "url|mime|size|sha1|extmetadata",
            "maxlag": 5,
        }
        try:
            with httpx.Client(transport=self._transport, proxy=self._proxy, trust_env=False, follow_redirects=False,
                              timeout=self._timeout) as client:
                with client.stream("GET", self.api_url, params=params, headers={
                    "User-Agent": f"EaselAudio/0.1 ({self.contact_url})",
                    "Accept": "application/json"}) as response:
                    if response.status_code != 200:
                        raise StockUnavailable("Wikimedia audio search is unavailable", code=http_failure_code(response.status_code))
                    payload = bytearray()
                    for chunk in response.iter_bytes():
                        payload.extend(chunk)
                        if len(payload) > 4 * 1024 * 1024:
                            raise StockUnavailable("Wikimedia audio response exceeds limit", code="invalid_response")
            data = json.loads(payload)
        except StockUnavailable:
            raise
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise StockUnavailable("Wikimedia audio search failed", code=search_failure_code(exc)) from None
        if not isinstance(data, dict) or "error" in data:
            raise StockUnavailable("Wikimedia audio API returned an error", code="invalid_response")
        query_data = data.get('query') or {}
        if not isinstance(query_data, dict):
            raise StockUnavailable('Wikimedia audio response is invalid', code="invalid_response")
        pages = query_data.get('pages', [])
        if not isinstance(pages, list):
            raise StockUnavailable("Wikimedia audio response is invalid", code="invalid_response")
        output = []
        for page in pages[:40]:
            candidate = self._candidate(page)
            if candidate:
                output.append(candidate)
            if len(output) >= limit:
                break
        return tuple(output)

    def verify_download(self, candidate: ExternalCandidate, downloaded) -> None:
        """Bind downloaded bytes to the Commons file revision originally reviewed.

        The generic downloader separately enforces DNS/redirect/MIME/size.
        Never trust an unchanged file title if the file was replaced remotely.
        """
        recorded = candidate.source.provider_asset_id or ''
        if (candidate.source.provider != self.provider_id or
                not re.fullmatch(r'[0-9]+:[0-9a-f]{40}', recorded) or
                sha1(downloaded.body).hexdigest() != recorded.rsplit(':',1)[1]):
            raise StockUnavailable('Wikimedia source file changed after search')

    def _candidate(self, page: object) -> ExternalCandidate | None:
        if not isinstance(page, dict) or page.get("ns") != 6 or not isinstance(page.get("pageid"), int):
            return None
        title = page.get("title")
        if not isinstance(title, str) or not title.startswith("File:"):
            return None
        imageinfo = page.get("imageinfo")
        if not isinstance(imageinfo, list) or not imageinfo or not isinstance(imageinfo[0], dict):
            return None
        info = imageinfo[0]
        mime = info.get("mime")
        if not isinstance(mime, str) or not (mime.startswith("audio/") or
                mime == "application/ogg" and title.lower().endswith((".ogg", ".oga"))):
            return None
        if not isinstance(info.get("size"), int) or not 0 < info["size"] <= 128 * 1024 * 1024:
            return None
        sha1 = info.get("sha1")
        if not isinstance(sha1, str) or re.fullmatch("[0-9a-fA-F]{40}", sha1) is None:
            return None
        url = _https_url(info.get("url"), self.allowed_hosts)
        page_url = _https_url(info.get("descriptionurl"), ("commons.wikimedia.org",))
        if not url or not page_url:
            return None
        # A Commons file page is identified by its path. Drop campaign query
        # parameters so exact export credits can be revalidated without URLs
        # with volatile tracking state.
        parsed_page = urlsplit(page_url)
        page_url = urlunsplit((parsed_page.scheme, parsed_page.netloc, parsed_page.path, '', ''))
        metadata = info.get("extmetadata")
        if not isinstance(metadata, dict):
            return None
        license_name = _meta(metadata, "LicenseShortName")
        license_url = _plain(
            metadata.get("LicenseUrl", {}).get("value") if isinstance(metadata.get("LicenseUrl"), dict) else None)
        expected = self.license_urls.get(license_name)
        # Commons' CC0 metadata sometimes points at the old HTTP /deed.en.
        # Accept only the exact Creative Commons host and expected deed path;
        # unknown/NC/SA/ND licenses remain blocked.
        if not expected or not license_url:
            return None
        parsed = urlsplit(license_url)
        canonical = urlsplit(expected)
        accepted_paths = {canonical.path.rstrip('/'), canonical.path.rstrip('/') + '/deed.en'}
        if (parsed.scheme not in {'http', 'https'} or parsed.hostname != 'creativecommons.org'
                or parsed.port is not None or parsed.username or parsed.password or
                parsed.query or parsed.fragment or parsed.path.rstrip('/') not in accepted_paths):
            return None
        license_url = expected
        if license_name == 'CC0':
            license_name = 'CC0 1.0'
        name = _meta(metadata, "Artist")
        if license_name == "CC BY 4.0" and not name:
            return None
        artist = name or "Wikimedia Commons file contributor"
        stamp = datetime.now(timezone.utc)
        source = CandidateSource(kind="stock", provider=self.provider_id,
            provider_asset_id=f"{page['pageid']}:{sha1.lower()}",
            source_page=page_url, creator=artist)
        evidence = (RightsEvidence(kind="asset_wikimedia_file_license_declaration",
            reference=page_url, observed_at=stamp,
            summary="Wikimedia Commons file page declares " + license_name +
                    "; creator and underlying rights are not independently verified"),)
        title_text = _plain(title.removeprefix("File:"), max_length=160)
        if license_name == "CC BY 4.0":
            credit = f'"{title_text}" by {artist}; {page_url}; {license_name} ({license_url})'
            rights = RightsInfo(status=RightsStatus.ATTRIBUTION_REQUIRED, license_name=license_name,
                license_url=license_url, attribution_required=True, attribution_text=credit,
                usage_constraints=("attribution_required", "no_redistribution_as_stock"),
                evidence=evidence, reviewed_at=stamp)
        else:
            rights = RightsInfo(status=RightsStatus.PUBLIC_DOMAIN, license_name=license_name,
                license_url=license_url, usage_constraints=("no_redistribution_as_stock",),
                evidence=evidence, reviewed_at=stamp)
        return ExternalCandidate(f"{page['pageid']}:{sha1.lower()}", MediaType.AUDIO, url,
            source, rights, SemanticInfo(caption=title_text,
                tags=(self.role,), attributes={"audio_roles": [self.role],
                     "media_origin": "wikimedia_commons_file",
                     "license_claim_reviewed_at": stamp.isoformat()}))
