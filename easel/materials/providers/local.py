"""Safe local-file discovery adapter for configured Material roots."""

from __future__ import annotations

import hashlib
import mimetypes
import os
from pathlib import Path

from easel.materials.domain import (
    Availability,
    CandidateSource,
    MediaType,
    RetrievalIntent,
    SupplyCandidate,
)
from easel.materials.domain.models import AcquisitionInfo, PreviewInfo, RightsHint
from easel.materials.providers.base import ProviderPage
from easel.materials.providers.errors import ProviderNetworkError, ProviderUnsupportedError
from easel.materials.providers.models import (
    AccessMode,
    PaginationMode,
    ProviderCapability,
    ProviderContinuation,
    ProviderHealth,
    ProviderHealthStatus,
    ProviderInfo,
)


_MEDIA_EXTENSIONS: dict[MediaType, frozenset[str]] = {
    MediaType.IMAGE: frozenset({".avif", ".bmp", ".gif", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}),
    MediaType.VIDEO: frozenset({".avi", ".m4v", ".mkv", ".mov", ".mp4", ".mpeg", ".mpg", ".webm"}),
    MediaType.AUDIO: frozenset({".aac", ".aiff", ".flac", ".m4a", ".mp3", ".oga", ".ogg", ".opus", ".wav", ".wma"}),
}


class LocalProvider:
    """Enumerate supported files strictly beneath explicitly configured roots.

    This adapter performs filesystem discovery only. It does not probe codecs,
    decode media, copy files, or infer rights.
    """

    provider_id = "local"

    def __init__(self, roots: tuple[str | Path, ...] | list[str | Path], *, page_size: int = 50):
        if page_size < 1 or page_size > 500:
            raise ValueError("page_size must be between 1 and 500")
        normalized: list[Path] = []
        for root in roots:
            path = Path(root).expanduser().resolve(strict=True)
            if not path.is_dir():
                raise ValueError("LocalProvider roots must be directories")
            if path not in normalized:
                normalized.append(path)
        self._roots = tuple(normalized)
        self._page_size = page_size

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            provider_id=self.provider_id,
            display_name="Local Files",
            media_types=(MediaType.VIDEO, MediaType.IMAGE, MediaType.AUDIO),
            access_mode=AccessMode.LOCAL,
            capabilities=(
                ProviderCapability.SEARCH,
                ProviderCapability.PREVIEW,
                ProviderCapability.DIRECT_DOWNLOAD,
                ProviderCapability.PAGINATION,
                ProviderCapability.HEALTH_CHECK,
            ),
            pagination_mode=PaginationMode.OFFSET,
            auth_mode="filesystem permissions for configured roots",
            cache_policy="not cached; filesystem metadata is read on each search",
            attribution_policy="rights are not inferred from local file location",
            acquisition_policy="returns a local-file descriptor; acquisition is not performed",
        )

    def search(
        self,
        intent: RetrievalIntent,
        continuation: ProviderContinuation | None = None,
    ) -> ProviderPage:
        media_value = intent.filters.get("media_type")
        try:
            media_type = MediaType(media_value)
        except (TypeError, ValueError) as exc:
            raise ProviderUnsupportedError(self.provider_id, "Search requires a supported media_type") from exc

        offset = self._read_offset(continuation)
        paths = self._supported_files(media_type)
        page_paths = paths[offset : offset + self._page_size]
        candidates = tuple(self._candidate(path, intent.need_id, media_type) for path in page_paths)
        next_offset = offset + len(page_paths)
        next_page = None
        if next_offset < len(paths):
            next_page = ProviderContinuation(
                provider_id=self.provider_id,
                mode=PaginationMode.OFFSET,
                token=str(next_offset),
            )
        return ProviderPage(candidates=candidates, continuation=next_page)

    def health(self) -> ProviderHealth:
        unavailable = tuple(root for root in self._roots if not root.is_dir() or not os.access(root, os.R_OK))
        return ProviderHealth(
            provider_id=self.provider_id,
            status=ProviderHealthStatus.UNAVAILABLE if unavailable else ProviderHealthStatus.HEALTHY,
            degraded_reason="one or more configured roots are unavailable" if unavailable else None,
        )

    def _read_offset(self, continuation: ProviderContinuation | None) -> int:
        if continuation is None:
            return 0
        if continuation.provider_id != self.provider_id or continuation.mode != PaginationMode.OFFSET:
            raise ProviderUnsupportedError(self.provider_id, "Continuation does not belong to LocalProvider")
        try:
            offset = int(continuation.token)
        except ValueError as exc:
            raise ProviderUnsupportedError(self.provider_id, "Continuation offset is invalid") from exc
        if offset < 0:
            raise ProviderUnsupportedError(self.provider_id, "Continuation offset is invalid")
        return offset

    def _supported_files(self, media_type: MediaType) -> list[Path]:
        extensions = _MEDIA_EXTENSIONS[media_type]
        found: list[Path] = []
        for root in self._roots:
            if not root.is_dir() or not os.access(root, os.R_OK):
                raise ProviderNetworkError(self.provider_id, "A configured local root is unavailable")
            try:
                errors: list[OSError] = []
                for directory, dirnames, filenames in os.walk(
                    root,
                    followlinks=False,
                    onerror=errors.append,
                ):
                    current = Path(directory)
                    # Prune symlink directories and any path that resolves outside the root.
                    dirnames[:] = sorted(
                        name
                        for name in dirnames
                        if not (current / name).is_symlink()
                        and self._inside_root((current / name), root)
                    )
                    for filename in sorted(filenames):
                        path = current / filename
                        if path.is_symlink() or path.suffix.lower() not in extensions:
                            continue
                        if not self._inside_root(path, root) or not path.is_file():
                            continue
                        found.append(path)
                if errors:
                    raise errors[0]
            except OSError as exc:
                raise ProviderNetworkError(self.provider_id, "A configured local root could not be read") from exc
        return sorted(found, key=lambda path: str(path).casefold())

    @staticmethod
    def _inside_root(path: Path, root: Path) -> bool:
        try:
            path.resolve(strict=True).relative_to(root)
            return True
        except (OSError, ValueError):
            return False

    def _candidate(self, path: Path, need_id: str, media_type: MediaType) -> SupplyCandidate:
        try:
            stat = path.stat()
        except OSError as exc:
            raise ProviderNetworkError(self.provider_id, "A local file became unavailable during search") from exc
        identity = hashlib.sha256(os.fsencode(str(path))).hexdigest()
        mime, _ = mimetypes.guess_type(path.name)
        return SupplyCandidate(
            candidate_id=f"local:{identity}",
            need_id=need_id,
            media_type=media_type,
            source=CandidateSource(
                kind="local",
                provider=self.provider_id,
                provider_asset_id=identity,
            ),
            preview=PreviewInfo(locator=path.as_uri()),
            availability=Availability.RESOLVABLE,
            rights_hint=RightsHint(),
            metadata={
                "filename": path.name,
                "extension": path.suffix.lower(),
                "size_bytes": stat.st_size,
                "modified_at": stat.st_mtime,
                "mime_type": mime or "application/octet-stream",
            },
            acquisition=AcquisitionInfo(
                mode="local_file",
                locator=str(path),
                media_format=mime or path.suffix.lower().lstrip("."),
            ),
        )
