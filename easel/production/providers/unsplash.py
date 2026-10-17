"""Unsplash discovery/preview only. Never download or silently bypass API rules.

Images must be hotlinked in the UI, with photographer and Unsplash credit.
Production asset import requires a separate explicit selection and required
download-tracking integration; this adapter deliberately does neither.
"""
from __future__ import annotations

import json
from urllib.parse import urlencode, urlsplit, urlunsplit

import httpx

from .stock import StockUnavailable, _https_url


class UnsplashDiscoveryProvider:
    provider_id = "unsplash"
    media_types = ("image",)
    preview_hosts = ("images.unsplash.com",)

    def __init__(self, access_key: str, *, transport: httpx.BaseTransport | None = None,
                 timeout: float = 20.0):
        if timeout <= 0:
            raise ValueError("Timeout must be positive")
        self._key, self._transport, self._timeout = access_key.strip(), transport, timeout

    @property
    def available(self):
        return bool(self._key)

    @staticmethod
    def _credit_url(raw):
        url = _https_url(raw, ("unsplash.com",))
        if url is None:
            return None
        parsed = urlsplit(url)
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path,
                           urlencode({"utm_source": "easel", "utm_medium": "referral"}), ""))

    def search(self, query: str, *, limit: int = 10):
        """One explicitly requested preview search; never triggered from production supply."""
        if not self.available:
            raise StockUnavailable("capability_unavailable: Unsplash is not configured", code="capability_unavailable")
        if not isinstance(query, str) or not query.strip() or len(query) > 140 or not 1 <= limit <= 20:
            raise ValueError("Invalid Unsplash preview search")
        try:
            with httpx.Client(transport=self._transport, trust_env=False, follow_redirects=False,
                              timeout=self._timeout) as client:
                with client.stream("GET", "https://api.unsplash.com/search/photos",
                    params={"query": query.strip(), "page": 1, "per_page": limit, "content_filter": "high"},
                    headers={"Authorization": "Client-ID " + self._key,
                             "Accept-Version": "v1", "Accept": "application/json"}) as response:
                    if response.status_code != 200:
                        raise StockUnavailable(f"Unsplash preview search returned HTTP {response.status_code}")
                    raw = bytearray()
                    for chunk in response.iter_bytes():
                        raw.extend(chunk)
                        if len(raw) > 4 * 1024 * 1024:
                            raise StockUnavailable("Unsplash preview response is too large")
            body = json.loads(raw)
        except StockUnavailable:
            raise
        except (httpx.HTTPError, ValueError, TypeError):
            raise StockUnavailable("Unsplash preview search returned invalid data") from None
        results = body.get("results") if isinstance(body, dict) else None
        if not isinstance(results, list):
            raise StockUnavailable("Unsplash preview search shape is invalid")
        previews = []
        for item in results[:limit]:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                continue
            urls = item.get("urls")
            links = item.get("links")
            user = item.get("user")
            if not isinstance(urls, dict) or not isinstance(links, dict) or not isinstance(user, dict):
                continue
            preview = _https_url(urls.get("small"), self.preview_hosts)
            page = self._credit_url(links.get("html"))
            name = user.get("name")
            user_links = user.get("links")
            credit = self._credit_url(user_links.get("html")) if isinstance(user_links, dict) else None
            if not preview or not page or not credit or not isinstance(name, str) or not name.strip():
                continue
            previews.append({"provider": "unsplash", "asset_id": item["id"], "preview_url": preview,
                             "source_page": page, "creator": name, "creator_page": credit,
                             "attribution_required": True, "production_ready": False,
                             "selection_required": True})
        return tuple(previews)
