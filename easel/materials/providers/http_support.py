"""Small injectable HTTP boundary for deterministic Provider adapter tests."""

from __future__ import annotations

import hashlib
import json
import os
import base64
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Mapping, Protocol
from urllib.parse import urlsplit

from easel import __version__
from easel.materials.domain.models import RetrievalIntent


DEFAULT_PROVIDER_USER_AGENT = f"Easel/{__version__} MaterialProvider"


def _provider_headers(headers: Mapping[str, str]) -> dict[str, str]:
    result = dict(headers)
    if not any(str(name).casefold() == "user-agent" for name in result):
        result["User-Agent"] = DEFAULT_PROVIDER_USER_AGENT
    return result


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    headers: Mapping[str, str]
    body: bytes
    from_cache: bool = False


class HttpTransport(Protocol):
    def get(self, url: str, *, headers: Mapping[str, str], timeout: float) -> HttpResponse: ...

    def post(
        self, url: str, *, headers: Mapping[str, str], body: bytes, timeout: float
    ) -> HttpResponse: ...


class ResponseCache(Protocol):
    def get_or_fetch(self, key: str, fetch) -> HttpResponse: ...


class UrllibTransport:
    """Default HTTP implementation with one stable, non-personal User-Agent."""

    def get(self, url: str, *, headers: Mapping[str, str], timeout: float) -> HttpResponse:
        request = urllib.request.Request(url, headers=_provider_headers(headers), method="GET")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return HttpResponse(
                    status_code=response.status,
                    headers=dict(response.headers.items()),
                    body=response.read(),
                )
        except urllib.error.HTTPError as response:
            return HttpResponse(
                status_code=response.code,
                headers=dict(response.headers.items()),
                body=response.read(),
            )

    def post(self, url: str, *, headers: Mapping[str, str], body: bytes, timeout: float) -> HttpResponse:
        request = urllib.request.Request(url, data=body, headers=_provider_headers(headers), method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return HttpResponse(
                    status_code=response.status,
                    headers=dict(response.headers.items()),
                    body=response.read(),
                )
        except urllib.error.HTTPError as response:
            return HttpResponse(
                status_code=response.code,
                headers=dict(response.headers.items()),
                body=response.read(),
            )


class MemoryTTLResponseCache:
    """Process-local TTL cache for provider responses that require caching."""

    def __init__(self, *, ttl_seconds: float = 86_400, clock=time.time) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._entries: dict[str, tuple[float, HttpResponse]] = {}
        self._lock = Lock()

    def get_or_fetch(self, key: str, fetch) -> HttpResponse:
        cache_key = hashlib.sha256(key.encode("utf-8")).hexdigest()
        now = self._clock()
        with self._lock:
            entry = self._entries.get(cache_key)
            if entry is not None and entry[0] > now:
                cached = entry[1]
                return HttpResponse(cached.status_code, cached.headers, cached.body, from_cache=True)
        response = fetch()
        if response.status_code == 200:
            with self._lock:
                self._entries[cache_key] = (self._clock() + self._ttl_seconds, response)
        return response


class FileTTLResponseCache:
    """Small atomic disk cache for API terms that require cross-request retention."""

    def __init__(self, directory: Path | str | None = None, *, ttl_seconds: float = 86_400, clock=time.time) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        if directory is None:
            if sys.platform == "darwin":
                directory = Path.home() / "Library" / "Caches" / "Easel" / "material-providers" / "pixabay"
            else:
                cache_home = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
                directory = cache_home / "easel" / "material-providers" / "pixabay"
        self._directory = Path(directory).expanduser()
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._lock = Lock()

    def get_or_fetch(self, key: str, fetch) -> HttpResponse:
        cache_key = hashlib.sha256(key.encode("utf-8")).hexdigest()
        path = self._directory / f"{cache_key}.json"
        now = self._clock()
        with self._lock:
            cached = self._read(path, now)
            if cached is not None:
                return cached
            response = fetch()
            if response.status_code == 200:
                self._write(path, response, self._clock() + self._ttl_seconds)
            return response

    def _read(self, path: Path, now: float) -> HttpResponse | None:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(record, dict) or float(record.get("expires_at", 0)) <= now:
                path.unlink(missing_ok=True)
                return None
            body = base64.b64decode(record["body"], validate=True)
            headers = record["headers"]
            if not isinstance(headers, dict):
                path.unlink(missing_ok=True)
                return None
            return HttpResponse(int(record["status_code"]), headers, body, from_cache=True)
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            path.unlink(missing_ok=True)
            return None

    def _write(self, path: Path, response: HttpResponse, expires_at: float) -> None:
        self._directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        payload = json.dumps(
            {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": base64.b64encode(response.body).decode("ascii"),
                "expires_at": expires_at,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        temporary_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", prefix=".pixabay-", suffix=".tmp", dir=self._directory, delete=False
            ) as stream:
                temporary_path = stream.name
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary_path, 0o600)
            os.replace(temporary_path, path)
        finally:
            if temporary_path:
                Path(temporary_path).unlink(missing_ok=True)


def decode_json(response: HttpResponse) -> object:
    return json.loads(response.body.decode("utf-8"))


def normalized_headers(headers: Mapping[str, str]) -> dict[str, str]:
    return {str(key).lower(): str(value) for key, value in headers.items()}


def intent_fingerprint(intent: RetrievalIntent) -> str:
    return hashlib.sha256(intent.to_json().encode("utf-8")).hexdigest()[:24]


def continuation_token(intent: RetrievalIntent, query_index: int, page: int) -> str:
    return f"v1:{intent_fingerprint(intent)}:{query_index}:{page}"


def parse_continuation_token(token: str, intent: RetrievalIntent) -> tuple[int, int] | None:
    parts = token.split(":")
    if len(parts) != 4 or parts[0] != "v1" or parts[1] != intent_fingerprint(intent):
        return None
    try:
        query_index, page = int(parts[2]), int(parts[3])
    except ValueError:
        return None
    if query_index < 0 or query_index >= len(intent.semantic_queries) or page < 1:
        return None
    return query_index, page


def safe_https_url(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            return None
    except ValueError:
        return None
    return value
