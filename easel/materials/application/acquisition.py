"""Bounded HTTPS acquisition adapted from V1 57c8e2ad, Apache-2.0.

Keeps DNS-pinned TLS transport and per-redirect validation. No V1 workspace,
Provider credentials, plan, Attempt or automatic paid generation is imported.
"""
from __future__ import annotations
import http.client
import ipaddress
import socket
import ssl
from dataclasses import dataclass
from urllib.parse import urlsplit, urljoin
from easel.materials.store import RemoteURLPolicy as Redaction

class AcquisitionError(ValueError):
    """An acquisition failure whose message never includes remote URL secrets."""

@dataclass(frozen=True)
class DownloadResponse:
    status_code: int
    headers: dict[str, str]
    body: bytes = b""

class PinnedHttpsTransport:
    """HTTPS GET that connects to the exact public IPs approved by the policy."""

    def get(
        self,
        url: str,
        *,
        headers: dict[str, str],
        timeout: float,
        max_bytes: int,
        addresses: tuple[str, ...],
    ) -> DownloadResponse:
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        port = parsed.port or 443
        target = parsed.path or "/"
        if parsed.query:
            target += "?" + parsed.query
        last_error: OSError | None = None
        for address in addresses:
            connection = _PinnedHTTPSConnection(host, address, port, timeout, ssl.create_default_context())
            try:
                connection.request("GET", target, headers=headers)
                response = connection.getresponse()
                response_headers = {key.lower(): value.strip() for key, value in response.getheaders()}
                if response.status in {301, 302, 303, 307, 308}:
                    return DownloadResponse(response.status, response_headers)
                content_length = response_headers.get("content-length")
                if content_length:
                    try:
                        parsed_length = int(content_length)
                    except ValueError as exc:
                        raise AcquisitionError("Remote response has an invalid content length") from exc
                    if parsed_length < 0 or parsed_length > max_bytes:
                        raise AcquisitionError("Remote response exceeds the configured size limit")
                body = response.read(max_bytes + 1)
                if len(body) > max_bytes:
                    raise AcquisitionError("Remote response exceeds the configured size limit")
                return DownloadResponse(response.status, response_headers, body)
            except AcquisitionError:
                raise
            except OSError as exc:
                last_error = exc
            finally:
                connection.close()
        raise AcquisitionError("Remote download connection failed") from last_error

class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, address: str, port: int, timeout: float, context: ssl.SSLContext):
        super().__init__(host, port=port, timeout=timeout, context=context)
        self._approved_address = address

    def connect(self) -> None:
        raw = socket.create_connection((self._approved_address, self.port), self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            raise


class RemoteURLPolicy:
    """Trusted provider allowlist plus public DNS validation for every hop."""

    def __init__(self, allowed_hosts: tuple[str, ...], *, resolver=None):
        if not allowed_hosts or any(not h or "/" in h or ":" in h or h.startswith(".") for h in allowed_hosts):
            raise ValueError("Explicit provider hostnames are required")
        self.allowed_hosts = tuple(h.lower() for h in allowed_hosts)
        self.resolver = resolver or self._resolve

    @staticmethod
    def _resolve(host, port):
        return tuple(sorted({item[4][0] for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)}))

    def validate(self, url: str) -> tuple[str, ...]:
        try:
            parsed = urlsplit(url)
            host = (parsed.hostname or "").lower()
            if (parsed.scheme != "https" or not host or parsed.username is not None
                    or parsed.password is not None or parsed.fragment or parsed.port not in (None, 443)):
                raise ValueError
        except ValueError as exc:
            raise AcquisitionError("Media URL must be HTTPS without credentials or a custom port") from exc
        if not any(host == domain or host.endswith("." + domain) for domain in self.allowed_hosts):
            raise AcquisitionError("Media host is not in the provider allowlist")
        try:
            addresses = tuple(self.resolver(host, 443))
            if not addresses:
                raise ValueError
            for value in addresses:
                address = ipaddress.ip_address(value)
                if not address.is_global or address.is_multicast or address.is_reserved:
                    raise ValueError
        except (OSError, ValueError) as exc:
            raise AcquisitionError("Media host did not resolve exclusively to public addresses") from exc
        return addresses[:8]

    redact = staticmethod(Redaction.redact)


@dataclass(frozen=True)
class DownloadedMedia:
    body: bytes
    mime: str
    source_url: str
    redirects: int


class MediaDownloader:
    """Download only; it cannot grant rights or submit a generation request."""

    def __init__(self, policy: RemoteURLPolicy, *, transport=None, timeout: float = 30,
                 max_bytes: int = 128 * 1024 * 1024, max_redirects: int = 5):
        if timeout <= 0 or max_bytes <= 0 or not 0 <= max_redirects <= 5:
            raise ValueError("Invalid download limits")
        self.policy, self.transport = policy, transport or PinnedHttpsTransport()
        self.timeout, self.max_bytes, self.max_redirects = timeout, max_bytes, max_redirects

    def download(self, url: str, *, media_type: str) -> DownloadedMedia:
        if media_type not in {"image", "video", "audio"}:
            raise AcquisitionError("Unsupported media type")
        current, seen = url, set()
        for redirects in range(self.max_redirects + 1):
            if current in seen:
                raise AcquisitionError("Media redirect loop")
            seen.add(current)
            addresses = self.policy.validate(current)
            response = self.transport.get(current, headers={"Accept": media_type + "/*",
                "Accept-Encoding": "identity", "User-Agent": "Easel/2 material acquisition"},
                timeout=self.timeout, max_bytes=self.max_bytes, addresses=addresses)
            headers = {key.lower(): value for key, value in response.headers.items()}
            if response.status_code in {301, 302, 303, 307, 308}:
                location = headers.get("location")
                if not location or redirects >= self.max_redirects:
                    raise AcquisitionError("Media redirect is missing or exceeds the configured limit")
                current = urljoin(current, location)
                continue
            if response.status_code != 200:
                raise AcquisitionError(f"Media download returned HTTP {response.status_code}")
            try:
                length = int(headers.get("content-length", len(response.body)))
            except (TypeError, ValueError) as exc:
                raise AcquisitionError("Invalid media content length") from exc
            if length < 0 or length > self.max_bytes or len(response.body) > self.max_bytes:
                raise AcquisitionError("Media exceeds the configured size limit")
            if "content-length" in headers and length != len(response.body):
                raise AcquisitionError("Media body is truncated or has a mismatched length")
            mime = headers.get("content-type", "").split(";", 1)[0].strip().lower()
            if not mime.startswith(media_type + "/") or not response.body:
                raise AcquisitionError("Media body is empty or has the wrong content type")
            return DownloadedMedia(response.body, mime, self.policy.redact(current) or "", redirects)
        raise AcquisitionError("Media redirect limit exceeded")
