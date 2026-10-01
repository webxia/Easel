"""Byte-bound, per-Need visual evidence for the existing Material matcher.

Video evidence describes sampled frames, never an assertion that every frame
has been watched. Partial usable segments stay unqualified until authoring can
bind the selected source interval to them.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import math
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageOps

from easel.materials.domain import (
    IntelligenceStatus, MaterialAsset, MaterialNeed, MediaType,
    SemanticAnnotation, SemanticField, SemanticInference,
)

SCHEMA = "easel-visual-observation@1"
PREFIX = "easel-visual-v1:"
MAX_VISUAL_CANDIDATES = 9


def need_identity(need: MaterialNeed) -> str:
    return hashlib.sha256(json.dumps(need.model_dump(mode="json"), sort_keys=True,
                                    ensure_ascii=False).encode()).hexdigest()


def observation_identity(need: MaterialNeed, asset: MaterialAsset) -> str:
    return f"{PREFIX}{need_identity(need)}:{asset.file.sha256}:"


def scoped_inference(need: MaterialNeed, asset: MaterialAsset, inference: SemanticInference,
                     input_sha256: str | None = None) -> bool:
    expected = observation_identity(need, asset) + (input_sha256 + ":" if input_sha256 else "")
    return (inference.analyzer_id == PREFIX + need_identity(need)
            and bool(inference.annotations)
            and all(a.evidence and a.evidence.startswith(expected)
                    for a in inference.annotations))


def observed_match(need: MaterialNeed, asset: MaterialAsset) -> bool | None:
    """None means no scoped observation; False must not fall through to tags."""
    scoped = [i for i in asset.semantic.inferences if i.analyzer_id.startswith(PREFIX)]
    if not scoped:
        return None
    return any(scoped_inference(need, asset, i) and i.status is IntelligenceStatus.COMPLETE
               and any(a.field is SemanticField.CAPTION and a.evidence.endswith(":suitable")
                       and a.confidence is not None and a.confidence >= 0.75 for a in i.annotations)
               for i in scoped)


def _jpeg(raw: bytes, edge: int = 384) -> bytes:
    with Image.open(io.BytesIO(raw)) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        image.thumbnail((edge, edge))
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=65)
        return output.getvalue()


def prepare_observation(need: MaterialNeed, asset: MaterialAsset, path: Path) -> tuple[dict, list[dict]]:
    """Decode actual bytes locally, then send bounded images to the agent RPC."""
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    if digest.hexdigest() != asset.file.sha256 or size != asset.file.size:
        raise ValueError("素材字节已变化，不能沿用观察身份")
    if asset.media_type is MediaType.IMAGE:
        frames = [(None, _jpeg(path.read_bytes()))]
    elif asset.media_type is MediaType.VIDEO:
        duration = asset.technical.duration_seconds
        if duration is None or not math.isfinite(duration) or duration <= 0:
            raise ValueError("视频尚无可信时长，不能采样观察")
        end = max(0.0, duration - min(0.1, duration / 10))
        frames = []
        for t in sorted({round(end * n / 4, 6) for n in range(5)}):
            try:
                result = subprocess.run([
                    "ffmpeg", "-v", "error", "-nostdin", "-protocol_whitelist", "file,pipe",
                    "-ss", str(t), "-i", str(path),
                    "-frames:v", "1", "-vf", "scale=384:384:force_original_aspect_ratio=decrease",
                    "-f", "image2pipe", "-vcodec", "mjpeg", "pipe:1",
                ], capture_output=True, timeout=30, check=True)
            except subprocess.TimeoutExpired as exc:
                # subprocess.run has already killed/reaped this local decoder;
                # unlike a gateway timeout, this is a known, retryable failure.
                raise ValueError("本地素材预览解码超时；原素材已保留") from exc
            frames.append((t, _jpeg(result.stdout)))
    else:
        raise ValueError("视觉观察仅接受图像或视频")
    for edge in (384, 256, 192):
        if edge < 384:
            frames = [(t, _jpeg(raw, edge)) for t, raw in frames]
        attachments = [{"type": "image", "mimeType": "image/jpeg", "fileName": f"frame-{i}.jpg",
                        "content": base64.b64encode(raw).decode("ascii")}
                       for i, (_, raw) in enumerate(frames)]
        if sum(len(a["content"]) for a in attachments) <= 80_000:
            break
    # gateway call transports JSON through argv; fail before dispatch rather
    # than truncate observations or exceed the OS argument limit.
    if sum(len(a["content"]) for a in attachments) > 80_000:
        raise ValueError("素材预览超过本地观察传输上限，未提交分析")
    manifest = {"schema": SCHEMA, "need": need.model_dump(mode="json"),
                "need_sha256": need_identity(need), "asset_id": asset.asset_id,
                "asset_sha256": asset.file.sha256, "media_type": asset.media_type.value,
                "duration_seconds": asset.technical.duration_seconds,
                "coverage": "still_image" if asset.media_type is MediaType.IMAGE else "sampled_frames",
                "frames": [{"index": i, "seek_seconds": t, "sha256": hashlib.sha256(raw).hexdigest()}
                           for i, (t, raw) in enumerate(frames)]}
    manifest["input_sha256"] = hashlib.sha256(json.dumps(manifest, sort_keys=True,
                                                        ensure_ascii=False).encode()).hexdigest()
    return manifest, attachments


def apply_observation(need: MaterialNeed, asset: MaterialAsset, manifest: dict, report: dict) -> MaterialAsset:
    """Validate identity and coverage; keep Rights and Provider facts untouched."""
    if (manifest.get("need_sha256") != need_identity(need)
            or manifest.get("asset_sha256") != asset.file.sha256
            or manifest.get("asset_id") != asset.asset_id
            or report.get("schema") != SCHEMA
            or report.get("input_sha256") != manifest.get("input_sha256")):
        raise ValueError("观察报告与当前场景、素材或预览不一致")
    verdict = report.get("verdict")
    if verdict not in {"suitable", "unsuitable", "partial", "uncertain"}:
        raise ValueError("观察报告缺少明确的适用结论")
    rows = report.get("frames")
    if (not isinstance(rows, list) or len(rows) != len(manifest["frames"])
            or [r.get("index") for r in rows if isinstance(r, dict)] != list(range(len(rows)))
            or any(type(r.get("observed")) is not bool
                   or r.get("related") is not None and type(r.get("related")) is not bool
                   or not isinstance(r.get("description"), str) or not r["description"].strip() for r in rows)):
        raise ValueError("观察报告必须逐张记录实际预览，不得省略未知项")
    if verdict == "suitable" and not all(r["observed"] and r["related"] is True for r in rows):
        raise ValueError("只有部分采样画面适合时，不能批准整项素材匹配")
    for key in ("caption", "style", "reason"):
        if not isinstance(report.get(key), str) or not report[key].strip() or len(report[key]) > 4000:
            raise ValueError("观察报告缺少画面、风格或判断依据")
    for key in ("logo_present", "visible_text_present"):
        if report.get(key) is not None and type(report[key]) is not bool:
            raise ValueError("标志及文字观察只能是真、假或未知")
    evidence = observation_identity(need, asset) + manifest["input_sha256"] + ":" + verdict
    annotations = [SemanticAnnotation(field=field, value=report[key], confidence=0.8, evidence=evidence)
                   for field, key in ((SemanticField.CAPTION, "caption"), (SemanticField.STYLE, "style"))]
    # Sparse video samples cannot establish absence throughout the file.
    # Positive sightings can reject it; still images can establish absence.
    for key, field in (("logo_present", SemanticField.LOGO),
                       ("visible_text_present", SemanticField.VISIBLE_TEXT)):
        value = report.get(key)
        if (all(r["observed"] for r in rows) and value is not None
                and (asset.media_type is MediaType.IMAGE or value is True)):
            annotations.append(SemanticAnnotation(field=field,
                value=value if field is SemanticField.LOGO else (("visible text",) if value else ()),
                confidence=0.8, evidence=evidence))
    inference = SemanticInference(analyzer_id=PREFIX + need_identity(need),
        status=IntelligenceStatus.COMPLETE if verdict in {"suitable", "unsuitable"} else IntelligenceStatus.PARTIAL,
        annotations=tuple(annotations), observed_at=datetime.now(timezone.utc))
    retained = tuple(i for i in asset.semantic.inferences if i.analyzer_id != inference.analyzer_id)
    return asset.model_copy(update={"semantic": asset.semantic.model_copy(update={
        "inferences": retained + (inference,), "intelligence_status": inference.status,
        "intelligence_error": None,
    })})
