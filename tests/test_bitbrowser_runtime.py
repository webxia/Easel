from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "shared" / "scripts"))

import bitbrowser_runtime


def test_profile_name_is_stable_and_platform_scoped():
    assert bitbrowser_runtime.profile_name("main") == "easel-xiaohongshu-main"


def test_resolve_profile_reuses_matching_environment(monkeypatch):
    monkeypatch.setattr(bitbrowser_runtime, "_profiles", lambda: [
        {"id": "profile-1", "name": "easel-xiaohongshu-main"},
    ])
    assert bitbrowser_runtime.resolve_profile("main") == "profile-1"


def test_resolve_profile_creates_environment_when_missing(monkeypatch):
    monkeypatch.setattr(bitbrowser_runtime, "_profiles", lambda: [])
    seen = {}

    def fake_request(path, payload=None, timeout=30):
        seen["path"] = path
        seen["payload"] = payload
        return {"id": "created-1"}

    monkeypatch.setattr(bitbrowser_runtime, "_request", fake_request)
    assert bitbrowser_runtime.resolve_profile("main") == "created-1"
    assert seen["path"] == "/browser/update"
    assert seen["payload"]["platform"] == "xiaohongshu.com"


def test_launch_connects_to_returned_cdp(monkeypatch):
    monkeypatch.setattr(bitbrowser_runtime, "resolve_profile", lambda **kwargs: "profile-1")
    monkeypatch.setattr(bitbrowser_runtime, "_request", lambda *args, **kwargs: {"ws": "ws://127.0.0.1:1234"})

    class Context:
        pages = []

        def new_page(self):
            return object()

    context = Context()

    class Browser:
        contexts = [context]

        def close(self):
            pass

    class Chromium:
        def connect_over_cdp(self, url):
            assert url.startswith("ws://")
            return Browser()

    class Playwright:
        chromium = Chromium()

    assert bitbrowser_runtime.launch(Playwright(), headed=False).pages == []
