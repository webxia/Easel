"""Attempt-local material acquisition with conservative remote URL controls."""

from __future__ import annotations

import hashlib
import http.client
import ipaddress
import json
import mimetypes
import os
import re
import socket
import ssl
import stat
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from easel.materials.domain import (
    Availability,
    MaterialAsset,
    RightsInfo,
    RightsStatus,
    SupplyCandidate,
    TechnicalInfo,
    TechnicalStatus,
)
from easel.materials.domain.models import FileInfo, RightsEvidence
from easel.materials.store import AttemptMaterialStore
from easel.materials.providers.minimax_video import is_minimax_media_host


MAX_ACQUIRED_BYTES = 128 * 1024 * 1024
MAX_REDIRECTS = 5
_PROVIDER_DOMAINS = {
    "pexels": ("pexels.com",),
    "pixabay": ("pixabay.com",),
    "openverse_audio": ("cdn.freesound.org", "upload.wikimedia.org"),
    "minimax": (),  # Exact/suffix host policy is shared with its task adapter.
}
_MIME_EXTENSIONS = {
    "image/avif": ".avif",
    "image/gif": ".gif",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/tiff": ".tiff",
    "image/webp": ".webp",
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/webm": ".webm",
    "video/x-matroska": ".mkv",
    "video/x-msvideo": ".avi",
    "audio/aac": ".aac",
    "audio/flac": ".flac",
    "audio/mp4": ".m4a",
    "audio/mpeg": ".mp3",
    "audio/ogg": ".ogg",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
}


class AcquisitionError(ValueError):
    """An acquisition failure whose message never includes remote URL secrets."""


@dataclass(frozen=True)
class AcquireDescriptor:
    mode: str
    provider: str
    media_type: str
    locator: str
    source_page: str | None
    media_format: str | None


@dataclass(frozen=True)
class DownloadResponse:
    status_code: int
    headers: dict[str, str]
    body: bytes = b""


class DownloadTransport(Protocol):
    def get(
        self,
        url: str,
        *,
        headers: dict[str, str],
        timeout: float,
        max_bytes: int,
        addresses: tuple[str, ...],
    ) -> DownloadResponse: ...


class RemoteURLPolicy:
    """Validate provider hosts and public DNS addresses before every request."""

    def __init__(self, resolver=None):
        self._resolver = resolver or self._resolve

    def validate(self, url: str, provider: str) -> tuple[str, ...]:
        try:
            parsed = urlsplit(url)
            host = parsed.hostname
            port = parsed.port
        except ValueError as exc:
            raise AcquisitionError("Remote URL is malformed") from exc
        if (
            parsed.scheme.lower() != "https"
            or not host
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
            or port not in (None, 443)
        ):
            raise AcquisitionError("Remote URL must be HTTPS without credentials or a custom port")
        host = host.rstrip(".").lower()
        if host in {"localhost", "localhost.localdomain"} or host.endswith((".localhost", ".local", ".internal")):
            raise AcquisitionError("Remote URL host is not public")
        allowed_domains = _PROVIDER_DOMAINS.get(provider)
        allowed = (is_minimax_media_host(host) if provider == 'minimax' else
                   bool(allowed_domains) and any(host == domain or host.endswith("." + domain) for domain in allowed_domains))
        if not allowed:
            raise AcquisitionError("Remote URL host does not match the candidate Provider")
        try:
            literal = ipaddress.ip_address(host)
            resolved = (str(literal),)
        except ValueError:
            try:
                resolved = tuple(self._resolver(host, port or 443))
            except OSError as exc:
                raise AcquisitionError("Remote URL host could not be resolved") from exc
        if not resolved:
            raise AcquisitionError("Remote URL host has no public addresses")
        for address in resolved:
            try:
                parsed_ip = ipaddress.ip_address(address)
            except ValueError as exc:
                raise AcquisitionError("Remote URL host returned an invalid address") from exc
            if not parsed_ip.is_global:
                raise AcquisitionError("Remote URL resolves to a non-public network")
        return resolved

    @staticmethod
    def _resolve(host: str, port: int) -> tuple[str, ...]:
        addresses = tuple(dict.fromkeys(
            record[4][0]
            for record in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        ))
        # Some VPNs return RFC 2544 benchmark addresses as synthetic DNS
        # answers. They must never be connected to as remote media addresses.
        if addresses and all(ipaddress.ip_address(address) in ipaddress.ip_network("198.18.0.0/15")
                             for address in addresses):
            request = Request(
                "https://cloudflare-dns.com/dns-query?" + urlencode({"name": host, "type": "A"}),
                headers={"Accept": "application/dns-json"},
            )
            try:
                with urlopen(request, timeout=10) as response:
                    payload = json.load(response)
                if not isinstance(payload, dict):
                    raise ValueError("Public DNS response is invalid")
                addresses = tuple(dict.fromkeys(
                    record["data"] for record in payload.get("Answer", ())
                    if isinstance(record, dict) and record.get("type") == 1
                    and isinstance(record.get("data"), str)
                ))
            except (OSError, ValueError, KeyError, TypeError) as exc:
                raise OSError("Public DNS fallback failed") from exc
        return addresses

    @staticmethod
    def redact(url: str | None) -> str | None:
        if not url:
            return None
        try:
            parsed = urlsplit(url)
            host = parsed.hostname or ""
            if parsed.port:
                host = f"{host}:{parsed.port}"
            return urlunsplit((parsed.scheme, host, parsed.path, "[REDACTED]" if parsed.query else "", ""))
        except ValueError:
            return "[REDACTED_INVALID_URL]"


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
                    if parsed_length > max_bytes:
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
        self.sock = self._context.wrap_socket(raw, server_hostname=self.host)


class MaterialAcquirer:
    def __init__(
        self,
        store: AttemptMaterialStore,
        *,
        transport: DownloadTransport | None = None,
        url_policy: RemoteURLPolicy | None = None,
        local_roots: tuple[str | Path, ...] | list[str | Path] = (),
        max_bytes: int = MAX_ACQUIRED_BYTES,
        timeout: float = 30.0,
        max_redirects: int = MAX_REDIRECTS,
    ):
        if max_bytes < 1 or timeout <= 0 or max_redirects < 0:
            raise ValueError("Invalid acquisition limits")
        self._store = store
        self._transport = transport or PinnedHttpsTransport()
        self._url_policy = url_policy or RemoteURLPolicy()
        self._local_roots = tuple(Path(root).expanduser().resolve(strict=True) for root in local_roots)
        if any(not root.is_dir() for root in self._local_roots):
            raise ValueError("Local acquisition roots must be directories")
        self._max_bytes = max_bytes
        self._timeout = timeout
        self._max_redirects = max_redirects

    def acquire(self, candidate: SupplyCandidate) -> MaterialAsset:
        descriptor = self._descriptor(candidate)
        if candidate.rights_hint.status is RightsStatus.RESTRICTED:
            raise AcquisitionError("Restricted candidate cannot be acquired")
        asset_id = "asset-" + uuid.uuid4().hex
        try:
            if descriptor.mode == "local_file":
                body, mime, local_origin = self._read_local(descriptor.locator, descriptor.media_type)
                requested_url = final_url = None
                redirect_count = 0
            else:
                body, mime, final_url, redirect_count = self._download(descriptor)
                local_origin = None
                requested_url = descriptor.locator

            extension = self._extension(mime)
            locator = self._store.write_asset_bytes(asset_id, f"original{extension}", body)
            digest = hashlib.sha256(body).hexdigest()
            rights = RightsInfo(
                status=candidate.rights_hint.status,
                license_name=candidate.rights_hint.license_name,
                license_url=self._url_policy.redact(candidate.rights_hint.license_url),
                attribution_required=candidate.rights_hint.attribution_required is True,
                usage_constraints=candidate.rights_hint.usage_constraints,
                evidence=self._rights_evidence(candidate),
            )
            source = candidate.source.model_copy(
                update={"source_page": self._url_policy.redact(candidate.source.source_page)}
            )
            asset = MaterialAsset(
                asset_id=asset_id,
                media_type=candidate.media_type,
                file=FileInfo(path=locator, sha256=digest, size=len(body), mime=mime),
                source=source,
                rights=rights,
                technical=TechnicalInfo(status=TechnicalStatus.PENDING),
            )
            self._store.write_asset(asset)
            evidence: dict[str, object] = {
                "method": descriptor.mode,
                "provider": descriptor.provider,
                "provider_asset_id": candidate.source.provider_asset_id,
                "need_id": candidate.need_id,
                "candidate_id": candidate.candidate_id,
                "source_page": self._url_policy.redact(candidate.source.source_page),
                "requested_url": self._url_policy.redact(requested_url),
                "final_url": self._url_policy.redact(final_url),
                "redirect_count": redirect_count,
                "acquired_at": datetime.now(timezone.utc).isoformat(),
                "content_type": mime,
                "byte_count": len(body),
                "sha256": digest,
                "rights_status_at_acquisition": candidate.rights_hint.status.value,
            }
            if local_origin is not None:
                evidence["local_origin"] = local_origin
            self._store.write_acquisition_evidence(asset_id, evidence)
            return asset
        except Exception:
            self._store.discard_uncommitted_asset(asset_id)
            raise

    @staticmethod
    def _descriptor(candidate: SupplyCandidate) -> AcquireDescriptor:
        acquisition = candidate.acquisition
        if acquisition is None or not acquisition.locator:
            raise AcquisitionError("Candidate has no acquisition locator")
        provider = candidate.source.provider or ""
        if acquisition.mode == "local_file" and provider == "local":
            return AcquireDescriptor(acquisition.mode, provider, candidate.media_type.value,
                                     acquisition.locator, candidate.source.source_page, acquisition.media_format)
        if acquisition.mode == "provider_direct_url" and provider in _PROVIDER_DOMAINS:
            if candidate.availability is not Availability.DIRECT_DOWNLOADABLE:
                raise AcquisitionError("Candidate is not marked direct-downloadable")
            return AcquireDescriptor(acquisition.mode, provider, candidate.media_type.value,
                                     acquisition.locator, candidate.source.source_page, acquisition.media_format)
        raise AcquisitionError("Candidate acquisition mode is unsupported")

    def _rights_evidence(self, candidate: SupplyCandidate) -> tuple[RightsEvidence, ...]:
        hint = candidate.rights_hint
        source_page = self._url_policy.redact(candidate.source.source_page)
        license_url = self._url_policy.redact(hint.license_url)
        if hint.status is not RightsStatus.KNOWN or not source_page or not license_url or not hint.license_name:
            return ()
        return (
            RightsEvidence(
                kind="asset_provider_listing",
                reference=source_page,
                observed_at=datetime.now(timezone.utc),
                summary=f"Provider listing for {candidate.source.provider or 'unknown'} asset "
                        f"{candidate.source.provider_asset_id or candidate.candidate_id}.",
            ),
            RightsEvidence(
                kind="asset_provider_license_terms",
                reference=license_url,
                summary=f"Provider adapter maps the published {hint.license_name}; see usage_constraints for recorded restrictions.",
            ),
        )

    def _download(self, descriptor: AcquireDescriptor) -> tuple[bytes, str, str, int]:
        current = descriptor.locator
        seen: set[str] = set()
        for redirect_count in range(self._max_redirects + 1):
            if current in seen:
                raise AcquisitionError("Remote download redirect loop detected")
            seen.add(current)
            addresses = self._url_policy.validate(current, descriptor.provider)
            response = self._transport.get(
                current,
                headers={"Accept": self._accept_header(descriptor.media_type)},
                timeout=self._timeout,
                max_bytes=self._max_bytes,
                addresses=addresses,
            )
            if response.status_code in {301, 302, 303, 307, 308}:
                location = self._header(response.headers, "location")
                if not location or redirect_count >= self._max_redirects:
                    raise AcquisitionError("Remote download redirect is missing or exceeds limit")
                current = urljoin(current, location)
                continue
            if response.status_code != 200:
                raise AcquisitionError(f"Remote download failed with HTTP {response.status_code}")
            content_length = self._header(response.headers, "content-length")
            if content_length:
                try:
                    parsed_length = int(content_length)
                except ValueError as exc:
                    raise AcquisitionError("Remote response has an invalid content length") from exc
                if parsed_length > self._max_bytes:
                    raise AcquisitionError("Remote response exceeds the configured size limit")
            if len(response.body) > self._max_bytes:
                raise AcquisitionError("Remote response exceeds the configured size limit")
            mime = self._normalized_mime(self._header(response.headers, "content-type"))
            self._validate_media_type(mime, descriptor.media_type)
            if not response.body:
                raise AcquisitionError("Remote response body is empty")
            return response.body, mime, current, redirect_count
        raise AcquisitionError("Remote download redirect limit exceeded")

    def _read_local(self, locator: str, media_type: str) -> tuple[bytes, str, str]:
        path = Path(locator).expanduser()
        if path.is_symlink():
            raise AcquisitionError("Local source must not be a symlink")
        try:
            resolved = path.resolve(strict=True)
            root = next((root for root in self._local_roots if resolved.is_relative_to(root)), None)
        except OSError as exc:
            raise AcquisitionError("Local source is unavailable") from exc
        if root is None:
            raise AcquisitionError("Local source is outside configured acquisition roots")
        relative = resolved.relative_to(root)
        walk = root
        for part in relative.parts:
            walk = walk / part
            if walk.is_symlink():
                raise AcquisitionError("Local source path contains a symlink")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(resolved, flags)
            with os.fdopen(descriptor, "rb") as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    raise AcquisitionError("Local source must be a regular file")
                body = stream.read(self._max_bytes + 1)
        except OSError as exc:
            raise AcquisitionError("Local source could not be read") from exc
        if len(body) > self._max_bytes:
            raise AcquisitionError("Local source exceeds the configured size limit")
        mime = mimetypes.guess_type(resolved.name)[0]
        if not mime:
            raise AcquisitionError("Local source type is unknown")
        self._validate_media_type(mime, media_type)
        return body, mime, relative.as_posix()

    @staticmethod
    def _normalized_mime(value: str | None) -> str:
        mime = (value or "").split(";", 1)[0].strip().lower()
        if not re.fullmatch(r"[a-z0-9.+-]+/[a-z0-9.+-]+", mime):
            raise AcquisitionError("Remote response has no valid media content type")
        return mime

    @staticmethod
    def _validate_media_type(mime: str, media_type: str) -> None:
        expected = {"video": "video/", "image": "image/", "audio": "audio/"}.get(media_type)
        if not expected or not mime.startswith(expected):
            raise AcquisitionError("Acquired content type does not match candidate media type")

    @staticmethod
    def _extension(mime: str) -> str:
        if mime in _MIME_EXTENSIONS:
            return _MIME_EXTENSIONS[mime]
        extension = mimetypes.guess_extension(mime, strict=False)
        if not extension or not re.fullmatch(r"\.[A-Za-z0-9]{1,8}", extension):
            raise AcquisitionError("Acquired media type has no safe file extension")
        return extension

    @staticmethod
    def _accept_header(media_type: str) -> str:
        major = {"video": "video/*", "image": "image/*", "audio": "audio/*"}.get(media_type)
        if not major:
            raise AcquisitionError("Candidate media type is unsupported")
        return major

    @staticmethod
    def _header(headers: dict[str, str], name: str) -> str | None:
        return next((value for key, value in headers.items() if key.lower() == name.lower()), None)
