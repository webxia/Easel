"""Local media operations with explicit file identities and no network input."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path, PurePosixPath

from PIL import Image, ImageDraw, ImageFont

from .editors.base import Caption, EditError

# Refuse playlists/manifests disguised with a media extension: the file protocol
# alone would still let those demuxers open files outside the registered asset.
MEDIA_FORMATS = "mov,matroska,webm,wav,mp3,aac,flac,ogg,image2,png_pipe,jpeg_pipe,webp_pipe"


def file_sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def stage_work_media(outputs: Path, work_id: str, source: Path) -> Path:
    """Content-addressed copy in the existing work artifact serving boundary."""
    if not re.fullmatch(r"[A-Za-z0-9_-]+", work_id) or source.is_symlink() or not source.is_file():
        raise EditError("invalid work media reference")
    folder = outputs
    for part in ("works", work_id, "artifacts"):
        folder = folder / part
        if folder.is_symlink():
            raise EditError("work media directory cannot be a symlink")
        folder.mkdir(parents=True, exist_ok=True)
    digest = file_sha256(source)
    target = folder / (digest + source.suffix.lower())
    if target.is_symlink():
        raise EditError("work media cannot use a symlink")
    if target.is_file():
        if file_sha256(target) != digest:
            raise EditError("existing work media identity changed")
        return target
    fd, temporary = tempfile.mkstemp(prefix=".media-", dir=folder)
    os.close(fd)
    try:
        shutil.copyfile(source, temporary)
        if file_sha256(Path(temporary)) != digest:
            raise EditError("source media changed while copying")
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return target


def local_path(root: Path, locator: str) -> Path:
    root = Path(root)
    relative = PurePosixPath(locator)
    if (not locator or "\\" in locator or ":" in locator or relative.is_absolute()
            or any(p in {"", ".", ".."} for p in locator.split("/"))):
        raise EditError("media locator must be a canonical relative file path")
    if root.is_symlink() or not root.is_dir():
        raise EditError("media root must be an existing non-symlink directory")
    path = root
    for part in relative.parts:
        path = path / part
        if path.is_symlink():
            raise EditError("media symlinks are not allowed")
    if not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
        raise EditError("media asset is unavailable")
    return path


def process_environment(home: Path) -> dict[str, str]:
    # Tools need no provider credentials, proxies, Python hooks or user config.
    home.mkdir(parents=True, exist_ok=True)
    env = {"PATH": os.defpath, "HOME": str(home), "USERPROFILE": str(home),
           "TMPDIR": str(home), "TEMP": str(home), "TMP": str(home), "LANG": "C.UTF-8"}
    for key in ("SYSTEMROOT", "WINDIR"):
        if key in os.environ:
            env[key] = os.environ[key]
    return env


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, allow_nan=False, sort_keys=True)
            stream.flush(); os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def probe_media(path: Path, *, ffprobe: str = "ffprobe", home: Path | None = None) -> dict:
    """Probe only a caller-validated local file; disable network protocols."""
    if not path.is_file() or path.is_symlink():
        raise EditError("media file is unavailable")
    executable = shutil.which(ffprobe)
    if not executable:
        raise EditError("ffprobe is unavailable", code="capability_unavailable")
    with tempfile.TemporaryDirectory(prefix="easel-probe-") as temp:
        result = subprocess.run(
            [executable, "-v", "error", "-protocol_whitelist", "file,pipe", "-format_whitelist", MEDIA_FORMATS, "-show_streams",
             "-show_format", "-of", "json", str(path.resolve())],
            capture_output=True, timeout=30, env=process_environment(home or Path(temp)))
    if result.returncode or len(result.stdout) > 2 * 1024 * 1024:
        raise EditError("local media could not be probed")
    try:
        data = json.loads(result.stdout)
        streams = data.get("streams", [])
        video = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
        duration = float(data.get("format", {}).get("duration") or (video or audio or {}).get("duration") or 0)
        return {"duration": duration, "width": (video or {}).get("width", 0),
                "height": (video or {}).get("height", 0), "video": video is not None,
                "audio": audio is not None, "streams": streams}
    except (ValueError, TypeError, KeyError) as exc:
        raise EditError("invalid local media probe result") from exc


def caption_image(caption: Caption, font_path: Path, *, width: int, height: int,
                  destination: Path) -> Path:
    """Render literal text, not ASS/filter expressions; refuse overflow rather than shrink."""
    font = ImageFont.truetype(str(font_path), caption.size)
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    available = int(width * caption.max_width) - 2 * (caption.outline + 12)
    lines: list[str] = []
    for paragraph in caption.text.split("\n"):
        current = ""
        for char in paragraph:
            if current and draw.textlength(current + char, font=font) > available:
                lines.append(current); current = ""
            current += char
        lines.append(current)
    text = "\n".join(lines)
    box = draw.multiline_textbbox((0, 0), text, font=font, spacing=caption.size // 5,
                                  stroke_width=caption.outline, align="center")
    w, h = box[2] - box[0], box[3] - box[1]
    left, top = round(width * caption.x - w / 2), round(height * caption.y - h / 2)
    if left < 0 or top < 0 or left + w > width or top + h > height:
        raise EditError("caption exceeds the frame; adjust its explicit size or position")
    if caption.background:
        draw.rounded_rectangle((left - 10, top - 8, left + w + 10, top + h + 8), radius=8,
                               fill=caption.background)
    draw.multiline_text((left - box[0], top - box[1]), text, font=font, fill=caption.color,
                        spacing=caption.size // 5, stroke_width=caption.outline,
                        stroke_fill=caption.outline_color, align="center")
    destination.parent.mkdir(parents=True, exist_ok=True)
    layer.save(destination, format="PNG")
    return destination
