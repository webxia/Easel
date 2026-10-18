"""Production-process source freshness: detect a stale loaded Worker.

A service that started before an in-place source change must not accept another
production/resume command with outdated Python objects.  Read-only inspection,
Creator acceptance and cancellation stay accessible for recovery.
"""
from __future__ import annotations

from pathlib import Path

from .errors import ProductionError

_MODULE_ROOT = Path(__file__).resolve().parent


def _capture_production_sources() -> dict[str, tuple[int, int]]:
    current: dict[str, tuple[int, int]] = {}
    for path in _MODULE_ROOT.rglob("*.py"):
        # Local project-owned Python modules only. No private credentials,
        # materials, caches, secrets or generated media are inspected.
        if path.is_symlink() or not path.is_file():
            continue
        stat = path.stat()
        current[path.relative_to(_MODULE_ROOT).as_posix()] = (stat.st_mtime_ns, stat.st_size)
    return current


_LOADED_SOURCES = _capture_production_sources()


def backend_code_freshness() -> dict[str, bool]:
    return {"reload_required": _capture_production_sources() != _LOADED_SOURCES}


def require_current_backend() -> None:
    if backend_code_freshness()["reload_required"]:
        raise ProductionError(
            "backend_reload_required",
            "V2 生产源码已修改，但服务仍使用旧版本；请重启唯一的主工作区 Easel 服务后再执行",
            status_code=503)
