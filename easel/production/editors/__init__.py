"""Editing backends used by production; importing this module performs no work."""
from .base import (AssetManifest, AudioClip, Caption, CheckResult, Crop, EditError,
                   EditProject, EditorAdapter, MediaAsset, RenderJob, RenderOutput,
                   Scene, assert_local_revision)


def __getattr__(name):
    # media.py imports base contracts; avoid a media -> package -> FFmpeg cycle.
    if name == "FFmpegEditor":
        from .ffmpeg import FFmpegEditor
        return FFmpegEditor
    raise AttributeError(name)


__all__ = ["FFmpegEditor", "AssetManifest", "AudioClip", "Caption", "CheckResult", "Crop",
           "EditError", "EditProject", "EditorAdapter", "MediaAsset", "RenderJob", "RenderOutput",
           "Scene", "assert_local_revision"]
