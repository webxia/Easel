"""Redact provider credentials before Hypit data reaches logs or Creation state."""

from __future__ import annotations

import re
from typing import Any


class SecretRedactor:
    _KEY = re.compile(
        r"(?:api.?key|access.?token|\btoken\b|password|secret|credential|private.?key|authorization)",
        re.I,
    )
    _PATTERNS = (
        re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{8,}={0,2}"),
        re.compile(r"(?i)\b(?:sk|key|token)[-_][A-Za-z0-9_-]{12,}\b"),
        re.compile(
            r"(?i)\b(?:[A-Z0-9_-]*(?:API[_-]?KEY|ACCESS[_-]?TOKEN|SECRET|PASSWORD|AUTHORIZATION))"
            r"\s*[:=]\s*[\"']?[^\s,;\"']+"
        ),
    )
    _REPLACEMENT = "[REDACTED]"

    @classmethod
    def redact_text(cls, value: str) -> str:
        result = value
        for pattern in cls._PATTERNS:
            result = pattern.sub(cls._REPLACEMENT, result)
        return result

    @classmethod
    def redact(cls, value: Any, *, parent_key: str = "") -> Any:
        if cls._KEY.search(parent_key):
            return cls._REPLACEMENT if value not in (None, "", [], {}) else value
        if isinstance(value, dict):
            return {key: cls.redact(item, parent_key=str(key)) for key, item in value.items()}
        if isinstance(value, list):
            return [cls.redact(item) for item in value]
        if isinstance(value, tuple):
            return tuple(cls.redact(item) for item in value)
        if isinstance(value, str):
            return cls.redact_text(value)
        return value

    @classmethod
    def contains_secret(cls, value: Any, *, parent_key: str = "") -> bool:
        if cls._KEY.search(parent_key):
            return value not in (None, "", [], {})
        if isinstance(value, dict):
            return any(cls.contains_secret(item, parent_key=str(key)) for key, item in value.items())
        if isinstance(value, (list, tuple)):
            return any(cls.contains_secret(item) for item in value)
        if isinstance(value, str):
            return cls.redact_text(value) != value
        return False
