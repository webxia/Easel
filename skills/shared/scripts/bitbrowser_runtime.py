#!/usr/bin/env python3
"""Small BitBrowser Local API adapter used by Xiaohongshu publisher scripts."""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen
from urllib.parse import urlparse


class BitBrowserError(RuntimeError):
    """BitBrowser Local API is unavailable or returned an invalid response."""


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_API_URL = "http://127.0.0.1:54345"


def _setting(name: str, default: str = "") -> str:
    value = os.environ.get(name, "").strip()
    if value:
        return value
    try:
        for line in (PROJECT_ROOT / ".env").read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return default


def _api_url() -> str:
    return _setting("BITBROWSER_API_URL", DEFAULT_API_URL).rstrip("/")


def _request(path: str, payload: dict[str, object] | None = None, timeout: int = 30) -> object:
    data = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")
    request = Request(
        f"{_api_url()}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (URLError, OSError, json.JSONDecodeError) as error:
        raise BitBrowserError(f"BitBrowser Local API 不可用：{error}") from error
    if not isinstance(body, dict) or not body.get("success"):
        message = body.get("msg") if isinstance(body, dict) else repr(body)
        raise BitBrowserError(f"BitBrowser Local API 返回失败：{message}")
    return body.get("data")


def profile_name(account: str | None = None) -> str:
    raw = (account or _setting("XHS_BITBROWSER_ACCOUNT", "main")).strip() or "main"
    readable = re.sub(r"[^0-9A-Za-z_-]+", "-", raw).strip("-")[:32]
    if not readable:
        readable = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"easel-xiaohongshu-{readable}"


def _profiles() -> list[dict[str, object]]:
    data = _request("/browser/list", {"page": 0, "pageSize": 100})
    if not isinstance(data, dict):
        raise BitBrowserError("BitBrowser profile 列表格式异常")
    profiles = data.get("list", [])
    return [item for item in profiles if isinstance(item, dict)]


def _proxy_payload(proxy: str | None) -> dict[str, object]:
    if not proxy:
        return {"proxyMethod": 2, "proxyType": "noproxy"}
    parsed = urlparse(proxy)
    if parsed.scheme not in {"http", "https", "socks5"} or not parsed.hostname or not parsed.port:
        raise BitBrowserError("BitBrowser 代理必须是 http(s)://host:port 或 socks5://host:port")
    payload: dict[str, object] = {
        "proxyMethod": 2,
        "proxyType": parsed.scheme,
        "host": parsed.hostname,
        "port": parsed.port,
    }
    if parsed.username:
        payload["proxyUserName"] = parsed.username
    if parsed.password:
        payload["proxyPassword"] = parsed.password
    return payload


def resolve_profile(account: str | None = None, proxy: str | None = None) -> str:
    """Find the stable XHS account environment, creating it on first use."""
    name = profile_name(account)
    for profile in _profiles():
        if profile.get("name") == name and profile.get("id"):
            return str(profile["id"])

    payload: dict[str, object] = {
        "name": name,
        "platform": "xiaohongshu.com",
        "url": "https://creator.xiaohongshu.com/",
        "remark": "Managed automatically by Easel for Xiaohongshu",
        "browserFingerPrint": {"coreVersion": "latest", "ostype": "MacOS"},
    }
    payload.update(_proxy_payload(proxy))
    created = _request("/browser/update", payload)
    if not isinstance(created, dict) or not created.get("id"):
        raise BitBrowserError("BitBrowser 已创建环境，但响应中没有 id")
    return str(created["id"])


class BitBrowserContext:
    """Context-shaped wrapper so the established publisher flow stays unchanged."""

    def __init__(self, browser, context, profile_id: str):
        self._browser = browser
        self._context = context
        self._profile_id = profile_id

    @property
    def pages(self):
        # BitBrowser opens its console and a helper extension alongside the
        # profile. Publisher scripts must never drive either as content pages.
        return [
            page for page in self._context.pages
            if not page.url.startswith(("chrome-extension://", "https://console.bitbrowser.net/"))
        ]

    def new_page(self):
        return self._context.new_page()

    def close(self) -> None:
        try:
            self._browser.close()
        finally:
            try:
                _request("/browser/close", {"id": self._profile_id})
            except BitBrowserError:
                pass


def launch(playwright, headed: bool, account: str | None = None, proxy: str | None = None):
    profile_id = resolve_profile(account=account, proxy=proxy)
    opened = _request("/browser/open", {"id": profile_id}, timeout=120)
    if not isinstance(opened, dict) or not isinstance(opened.get("ws"), str):
        raise BitBrowserError("BitBrowser 已打开环境，但没有返回 ws")
    browser = playwright.chromium.connect_over_cdp(opened["ws"])
    if not browser.contexts:
        browser.close()
        raise BitBrowserError("已连接 BitBrowser，但浏览器没有默认 context")
    return BitBrowserContext(browser, browser.contexts[0], profile_id)


def check() -> tuple[bool, str]:
    try:
        _profiles()
        return True, f"BitBrowser Local API 可用：{_api_url()}"
    except BitBrowserError as error:
        return False, str(error)
