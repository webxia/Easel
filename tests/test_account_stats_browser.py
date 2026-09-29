from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "shared" / "scripts" / "account_stats.py"
SPEC = importlib.util.spec_from_file_location("account_stats_browser_test", SCRIPT)
assert SPEC and SPEC.loader
account_stats = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(account_stats)


def test_xhs_browser_automation_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("XHS_BROWSER_BACKEND", raising=False)
    try:
        account_stats._launch_context("pw", "xiaohongshu", False, None, None, None, "main")
    except SystemExit as exc:
        assert exc.code == 4
    else:
        raise AssertionError("停用状态不应启动任何小红书浏览器后端")


def test_non_xhs_keeps_persistent_playwright_profile(monkeypatch, tmp_path):
    class Chromium:
        def launch_persistent_context(self, path, **kwargs):
            return path, kwargs

    class Playwright:
        chromium = Chromium()

    result = account_stats._launch_context(Playwright(), "douyin", False, str(tmp_path), None)
    assert result[0] == str(tmp_path / "DouyinProfile")
    assert result[1]["headless"] is True
