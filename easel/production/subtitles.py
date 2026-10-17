"""Subtitle settings compiled to the same literal caption layer used by export."""
from __future__ import annotations

import re
import shutil
import json
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

from .contracts import SubtitleSettings, fingerprint
from .editors.base import AssetManifest, Caption, EditError
from .media import MEDIA_FORMATS, caption_image, file_sha256, local_path, probe_media, process_environment


def configured_fonts(settings: dict[str, str]) -> dict[str, Path]:
    """Only configured font aliases; no download or system-font substitution."""
    raw = settings.get("EASEL_SUBTITLE_FONTS_JSON", "")
    if raw:
        try:
            configured = json.loads(raw)
            if not isinstance(configured, dict) or len(configured) > 30:
                raise ValueError
            return {name: Path(path) for name, path in configured.items()
                    if isinstance(name, str) and isinstance(path, str) and Path(path).is_file() and not Path(path).is_symlink()}
        except (ValueError, TypeError):
            raise EditError("font configuration is invalid", code="font_unavailable") from None
    return {}


def stage_fonts(paths: dict[str, Path], *, outputs: Path) -> tuple[dict[str, str], dict]:
    from .editors.base import MediaAsset
    mapping, assets = {}, {}
    directory = outputs / "_production" / "fonts"
    directory.mkdir(parents=True, exist_ok=True)
    for name, path in paths.items():
        if path.is_symlink() or not path.is_file() or path.suffix.lower() not in {".ttf", ".otf", ".ttc"}:
            raise EditError("selected configured font is unavailable", code="font_unavailable")
        digest = file_sha256(path)
        target = directory / (digest + path.suffix.lower())
        if target.is_symlink():
            raise EditError("font staging cannot use a symlink")
        if not target.is_file() or file_sha256(target) != digest:
            shutil.copyfile(path, target)
        key = "font_" + digest[:32]
        mapping[name] = key
        assets[key] = MediaAsset(locator=target.relative_to(outputs).as_posix(), sha256=digest, kind="font")
    return mapping, assets


def caption_from_settings(settings: SubtitleSettings, *, caption_id: str, text: str,
                          start: float, end: float, fonts: dict[str, str]) -> Caption | None:
    if not settings.enabled:
        return None
    if settings.font not in fonts:
        raise EditError("the selected font is not configured", code="font_unavailable")
    if not re.fullmatch(r"#[a-fA-F0-9]{6}", settings.color):
        raise EditError("subtitle color must be a six-digit hex color")
    outline = settings.outline != "transparent"
    if outline and not re.fullmatch(r"#[a-fA-F0-9]{6}", settings.outline):
        raise EditError("subtitle outline must be transparent or a six-digit hex color")
    background = settings.background
    if background == "transparent":
        background = None
    elif re.fullmatch(r"#[a-fA-F0-9]{6}", background):
        background += "CC"
    elif not re.fullmatch(r"#[a-fA-F0-9]{8}", background):
        raise EditError("subtitle background must be transparent or a hex color")
    return Caption(caption_id=caption_id, text=text, start=start, end=end,
                   font_asset_id=fonts[settings.font], size=settings.size, color=settings.color,
                   outline_color=settings.outline if outline else "#000000", outline=2 if outline else 0,
                   background=background, y={"top": .12, "middle": .5, "bottom": .88}[settings.position])


class SubtitleService:
    def __init__(self, root: Path, *, ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe"):
        self.root = Path(root)
        self.ffmpeg, self.ffprobe = shutil.which(ffmpeg) or ffmpeg, shutil.which(ffprobe) or ffprobe
        self.root.mkdir(parents=True, exist_ok=True)

    def preview(self, *, manifest: AssetManifest, frame_asset_id: str, at: float,
                settings: SubtitleSettings, text: str, fonts: dict[str, str]) -> dict:
        """Overlay a real supplied frame/export, never substitute an invented scene.

        For exact output placement callers pass the current composition/export
        frame. Source-video previews retain source dimensions and identify them.
        """
        if frame_asset_id not in manifest.assets or at < 0:
            raise EditError("preview frame is unavailable")
        asset = manifest.assets[frame_asset_id]
        if asset.kind not in {"image", "video"}:
            raise EditError("subtitle preview needs an image or video")
        path = local_path(manifest.root, asset.locator)
        if file_sha256(path) != asset.sha256:
            raise EditError("preview frame identity changed")
        metadata = probe_media(path, ffprobe=self.ffprobe)
        if asset.kind == "video" and at >= metadata["duration"]:
            raise EditError("preview time exceeds the supplied video")
        caption = caption_from_settings(settings, caption_id="preview", text=text, start=0, end=1, fonts=fonts)
        font_path = None
        font_digest = None
        if caption:
            font = manifest.assets.get(caption.font_asset_id)
            if not font or font.kind != "font":
                raise EditError("the selected font is unavailable", code="font_unavailable")
            font_path = local_path(manifest.root, font.locator)
            font_digest = file_sha256(font_path)
            if font_digest != font.sha256:
                raise EditError("the selected font identity changed")
        key = fingerprint({"asset": asset.model_dump(), "at": at, "settings": settings.model_dump(),
                           "text": text, "font": font_digest, "renderer": "caption-image-1"})
        output = self.root / f"{key}.png"
        reused = output.is_file()
        if not reused:
            with tempfile.TemporaryDirectory(prefix="subtitle-", dir=self.root) as temp:
                folder = Path(temp)
                frame = folder / "frame.png"
                if asset.kind == "image":
                    with Image.open(path) as source:
                        source.convert("RGBA").save(frame)
                else:
                    result = subprocess.run([self.ffmpeg, "-nostdin", "-v", "error", "-protocol_whitelist",
                        "file,pipe", "-format_whitelist", MEDIA_FORMATS, "-ss", str(at), "-i", str(path),
                        "-frames:v", "1", "-threads", "1", str(frame)], capture_output=True, timeout=30,
                        env=process_environment(folder / "home"))
                    if result.returncode:
                        raise EditError("could not extract the real preview frame")
                with Image.open(frame) as source:
                    image = source.convert("RGBA")
                if caption:
                    overlay = caption_image(caption, font_path, width=image.width, height=image.height,
                                            destination=folder / "caption.png")
                    with Image.open(overlay) as layer:
                        image.alpha_composite(layer)
                image.save(folder / "preview.png")
                (folder / "preview.png").replace(output)
        with Image.open(output) as result_image:
            width, height = result_image.size
        return {"path": str(output), "sha256": file_sha256(output), "width": width, "height": height,
                "frame_asset_id": frame_asset_id, "at": at, "settings": settings.model_dump(), "reused": reused}
