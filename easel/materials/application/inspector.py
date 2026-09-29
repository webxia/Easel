"""Read-only technical fact inspection for acquired material bytes."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

from easel.materials.domain import (
    MaterialAsset,
    MediaType,
    TechnicalInfo,
    TechnicalStatus,
)
from easel.materials.store import AttemptMaterialStore


class TechnicalInspector:
    """Inspect local bytes without changing or normalizing them."""

    def __init__(
        self,
        store: AttemptMaterialStore,
        *,
        ffprobe: str | None = None,
        timeout: float = 30.0,
    ):
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self._store = store
        self._ffprobe = shutil.which("ffprobe") if ffprobe is None else ffprobe
        self._timeout = timeout

    def inspect(self, asset: MaterialAsset) -> MaterialAsset:
        try:
            path = self._store.resolve_asset_locator(asset.file.path)
            file_facts = self._file_facts(path)
            if file_facts["sha256"] != asset.file.sha256:
                raise _InspectionFailure("content_hash_mismatch")
            if file_facts["size_bytes"] != asset.file.size:
                raise _InspectionFailure("content_size_mismatch")
            if asset.media_type is MediaType.IMAGE:
                facts = self._inspect_image(path)
            elif asset.media_type in {MediaType.VIDEO, MediaType.AUDIO}:
                facts = self._inspect_av(path, asset.media_type)
            else:
                raise _InspectionFailure("unsupported_media_type")
            facts.update(file_facts)
            facts["mime"] = facts.get("mime") or asset.file.mime
            technical = TechnicalInfo(
                status=TechnicalStatus.PASSED,
                duration_seconds=facts.get("duration_seconds"),
                width=facts.get("width"),
                height=facts.get("height"),
                mime=facts.get("mime"),
                has_audio=facts.get("has_audio"),
                facts=facts,
            )
            return asset.model_copy(update={"technical": technical})
        except _InspectionFailure as exc:
            return self._failed(asset, exc.code)
        except Exception:
            return self._failed(asset, "inspection_failed")

    def inspect_and_persist(self, asset: MaterialAsset) -> MaterialAsset:
        inspected = self.inspect(asset)
        self._store.write_asset(inspected)
        return inspected

    @staticmethod
    def _file_facts(path: Path) -> dict[str, Any]:
        digest = hashlib.sha256()
        size = 0
        try:
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
                    size += len(chunk)
        except OSError as exc:
            raise _InspectionFailure("asset_unreadable") from exc
        if size <= 0:
            raise _InspectionFailure("empty_asset")
        return {"size_bytes": size, "sha256": digest.hexdigest()}

    @staticmethod
    def _inspect_image(path: Path) -> dict[str, Any]:
        try:
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                image_format = (image.format or "").upper()
                mime = (Image.MIME.get(image_format) or mimetypes.guess_type(path.name)[0] or "").lower()
                if image.width <= 0 or image.height <= 0 or not mime.startswith("image/"):
                    raise _InspectionFailure("invalid_image_facts")
                return {
                    "width": image.width,
                    "height": image.height,
                    "mime": mime,
                    "alpha": "A" in image.getbands() or "transparency" in image.info,
                    "format": image_format.lower(),
                    "has_audio": False,
                }
        except _InspectionFailure:
            raise
        except (OSError, ValueError, UnidentifiedImageError) as exc:
            raise _InspectionFailure("corrupt_or_unsupported_image") from exc

    def _inspect_av(self, path: Path, media_type: MediaType) -> dict[str, Any]:
        if not self._ffprobe:
            raise _InspectionFailure("ffprobe_unavailable")
        try:
            result = subprocess.run(
                [self._ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
                capture_output=True,
                text=True,
                timeout=self._timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise _InspectionFailure("ffprobe_timeout") from exc
        except OSError as exc:
            raise _InspectionFailure("ffprobe_unavailable") from exc
        if result.returncode != 0:
            raise _InspectionFailure("ffprobe_rejected_media")
        try:
            payload = json.loads(result.stdout)
        except (TypeError, json.JSONDecodeError) as exc:
            raise _InspectionFailure("ffprobe_invalid_json") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("streams"), list):
            raise _InspectionFailure("ffprobe_invalid_shape")
        streams = [stream for stream in payload["streams"] if isinstance(stream, dict)]
        video_streams = []
        for stream in streams:
            disposition = stream.get("disposition")
            attached_pic = disposition.get("attached_pic") == 1 if isinstance(disposition, dict) else False
            if stream.get("codec_type") == "video" and not attached_pic:
                video_streams.append(stream)
        audio_streams = [stream for stream in streams if stream.get("codec_type") == "audio"]
        format_info = payload.get("format") if isinstance(payload.get("format"), dict) else {}
        duration = self._positive_float(format_info.get("duration"))
        if media_type is MediaType.VIDEO:
            stream = video_streams[0] if video_streams else None
            if stream is None:
                raise _InspectionFailure("video_stream_missing")
            width = self._positive_int(stream.get("width"))
            height = self._positive_int(stream.get("height"))
            duration = duration or self._positive_float(stream.get("duration"))
            if width is None or height is None or duration is None:
                raise _InspectionFailure("video_facts_missing")
            rate = self._frame_rate(stream.get("avg_frame_rate"))
            if rate is None:
                rate = self._frame_rate(stream.get("r_frame_rate"))
            if rate is None:
                raise _InspectionFailure("video_frame_rate_missing")
            mime = self._container_mime(format_info.get("format_name"), media_type, path)
            return {
                "duration_seconds": duration,
                "width": width,
                "height": height,
                "fps": rate,
                "codec": self._optional_string(stream.get("codec_name")),
                "audio_codec": self._optional_string(audio_streams[0].get("codec_name")) if audio_streams else None,
                "has_audio": bool(audio_streams),
                "mime": mime,
            }
        stream = audio_streams[0] if audio_streams else None
        if stream is None:
            raise _InspectionFailure("audio_stream_missing")
        duration = duration or self._positive_float(stream.get("duration"))
        if duration is None:
            raise _InspectionFailure("audio_duration_missing")
        return {
            "duration_seconds": duration,
            "codec": self._optional_string(stream.get("codec_name")),
            "has_audio": True,
            "mime": self._container_mime(format_info.get("format_name"), media_type, path),
        }

    @classmethod
    def _container_mime(cls, format_name: object, media_type: MediaType, path: Path) -> str | None:
        names = {part.strip().lower() for part in format_name.split(",")} if isinstance(format_name, str) else set()
        if names & {"mov", "mp4", "m4a", "3gp", "3g2", "mj2"}:
            return "audio/mp4" if media_type is MediaType.AUDIO else "video/mp4"
        if "webm" in names:
            return "audio/webm" if media_type is MediaType.AUDIO else "video/webm"
        if "matroska" in names:
            return "audio/x-matroska" if media_type is MediaType.AUDIO else "video/x-matroska"
        if "avi" in names:
            return "video/x-msvideo"
        if "wav" in names or "wave" in names:
            return "audio/wav"
        if "mp3" in names:
            return "audio/mpeg"
        if "flac" in names:
            return "audio/flac"
        if "ogg" in names or "oga" in names:
            return "audio/ogg"
        if "aac" in names:
            return "audio/aac"
        return mimetypes.guess_type(path.name)[0]

    @staticmethod
    def _frame_rate(value: object) -> float | None:
        if not isinstance(value, str) or not value or value in {"0/0", "N/A"}:
            return None
        try:
            rate = float(Fraction(value))
        except (ValueError, ZeroDivisionError, OverflowError):
            return None
        return rate if rate > 0 else None

    @staticmethod
    def _positive_int(value: object) -> int | None:
        if isinstance(value, bool):
            return None
        try:
            number = int(value)
        except (TypeError, ValueError, OverflowError):
            return None
        return number if number > 0 else None

    @staticmethod
    def _positive_float(value: object) -> float | None:
        if isinstance(value, bool):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError):
            return None
        return number if number > 0 else None

    @staticmethod
    def _optional_string(value: object) -> str | None:
        return value.strip() if isinstance(value, str) and value.strip() else None

    @staticmethod
    def _failed(asset: MaterialAsset, code: str) -> MaterialAsset:
        facts = {
            "inspection_error": code,
            "declared_size_bytes": asset.file.size,
            "declared_sha256": asset.file.sha256,
            "declared_mime": asset.file.mime,
        }
        return asset.model_copy(update={
            "technical": TechnicalInfo(status=TechnicalStatus.FAILED, facts=facts),
        })


class _InspectionFailure(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code
