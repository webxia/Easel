from __future__ import annotations

from pathlib import Path

import pytest

from easel.materials.domain import Availability, MediaType, RetrievalIntent, RightsStatus
from easel.materials.providers import (
    PaginationMode,
    ProviderContinuation,
    ProviderUnsupportedError,
)
from easel.materials.providers.local import LocalProvider


def intent(media_type: MediaType) -> RetrievalIntent:
    return RetrievalIntent(
        need_id="need-local",
        semantic_queries=("local footage",),
        filters={"media_type": media_type.value},
    )


def test_local_provider_normalizes_supported_media_and_stable_identity(tmp_path: Path) -> None:
    root = tmp_path / "library"
    root.mkdir()
    (root / "clip.MP4").write_bytes(b"video fixture")
    (root / "still.webp").write_bytes(b"image fixture")
    (root / "voice.wav").write_bytes(b"audio fixture")
    (root / "notes.txt").write_text("not media", encoding="utf-8")

    provider = LocalProvider([root])
    first = provider.search(intent(MediaType.VIDEO))
    again = provider.search(intent(MediaType.VIDEO))
    candidate = first.candidates[0]

    assert candidate == again.candidates[0]
    assert candidate.media_type is MediaType.VIDEO
    assert candidate.need_id == "need-local"
    assert candidate.availability is Availability.RESOLVABLE
    assert candidate.rights_hint.status is RightsStatus.UNKNOWN
    assert candidate.source.provider == "local"
    assert candidate.metadata["filename"] == "clip.MP4"
    assert candidate.metadata["mime_type"] == "video/mp4"
    assert candidate.acquisition.mode == "local_file"
    assert Path(candidate.acquisition.locator) == root / "clip.MP4"

    assert provider.search(intent(MediaType.IMAGE)).candidates[0].metadata["filename"] == "still.webp"
    assert provider.search(intent(MediaType.AUDIO)).candidates[0].metadata["filename"] == "voice.wav"


def test_local_provider_paginates_deterministically(tmp_path: Path) -> None:
    root = tmp_path / "library"
    root.mkdir()
    for name in ("c.mp4", "a.mp4", "b.mp4"):
        (root / name).write_bytes(name.encode())

    provider = LocalProvider([root], page_size=2)
    first = provider.search(intent(MediaType.VIDEO))

    assert [item.metadata["filename"] for item in first.candidates] == ["a.mp4", "b.mp4"]
    assert first.continuation.mode is PaginationMode.OFFSET
    second = provider.search(intent(MediaType.VIDEO), first.continuation)
    assert [item.metadata["filename"] for item in second.candidates] == ["c.mp4"]
    assert second.continuation is None


def test_local_provider_excludes_files_outside_root_and_symlinks(tmp_path: Path) -> None:
    root = tmp_path / "library"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (outside / "escape.mp4").write_bytes(b"external")
    (root / "inside.mp4").write_bytes(b"inside")
    try:
        (root / "linked.mp4").symlink_to(outside / "escape.mp4")
        (root / "linked-dir").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks are not available on this platform")

    result = LocalProvider([root]).search(intent(MediaType.VIDEO))

    assert [candidate.metadata["filename"] for candidate in result.candidates] == ["inside.mp4"]


def test_local_provider_rejects_foreign_continuation_before_search(tmp_path: Path) -> None:
    root = tmp_path / "library"
    root.mkdir()
    provider = LocalProvider([root])

    with pytest.raises(ProviderUnsupportedError, match="Continuation"):
        provider.search(
            intent(MediaType.VIDEO),
            ProviderContinuation(provider_id="other", mode=PaginationMode.OFFSET, token="0"),
        )
