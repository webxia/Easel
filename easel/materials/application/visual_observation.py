"""Byte-bound, per-Need visual evidence for the existing Material matcher.

Video evidence describes sampled frames, never an assertion that every frame
has been watched. Qualification carries a source interval that Production must
bind to an actual native media use.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import math
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageOps

from easel.materials.domain import (
    IntelligenceStatus, MaterialAsset, MaterialNeed, MediaType,
    SemanticAnnotation, SemanticField, SemanticInference,
)

SCHEMA = "easel-visual-observation@2"
PREFIX = "easel-visual-v1:"
MAX_VISUAL_CANDIDATES = 9
GROUP_SCHEMA = 'easel-shared-visual-observation@1'
MAX_SHARED_NEEDS = 4
NOMINATION_REVISION = 'need-origin-single-batch-v5'
ASSESSMENT_REVISION = 'requirements-v1'
MAX_PRIMARY_VISUAL_CANDIDATES = 2
MAX_EXPLORATORY_VISUAL_CANDIDATES = 1


def requires_reassessment(need: MaterialNeed, report: dict, media_type: MediaType) -> bool:
    """Only identifiable obsolete preference/postproduction refusals are retried."""
    if 'requirements_contract' in report or report.get('verdict') not in {'partial', 'unsuitable'}:
        return False
    if report.get('failure_kind') in {'hard_constraint', 'content_mismatch', 'evidence_insufficient'}:
        return False
    reason = report.get('reason', '')
    return (report.get('failure_kind') in {'preference_only', 'postproduction_only', 'none'}
            or bool(need.constraints.get('preferred_visual_details') or need.constraints.get('preferred_style'))
            and bool(re.search(r'仅.*(?:色调|颜色|留白|景别|风格)|only.*(?:style|color|wide shot)', reason, re.I))
            or media_type is MediaType.IMAGE
            and bool(re.search(r'(?:无法|不能|缺少|没有).*(?:微推|镜头运动|景别切换)|(?:lacks|missing).*(?:camera movement|zoom)', reason, re.I)))


def pending_visual_reassessment(attempt: dict) -> bool:
    from easel.materials.store import AttemptMaterialStore
    rows = attempt.get('material_observation', {}).get('outcomes', [])
    if not rows:
        return False
    store = AttemptMaterialStore(attempt['workspace']['path'])
    needs = {n.need_id: n for n in store.read_plan().needs}
    assets = {a.asset_id: a for a in store.read_bundle().assets}
    for row in rows:
        need, asset = needs.get(row.get('need_id')), assets.get(row.get('asset_id'))
        identity = row.get('input_sha256', '')
        if (need is None or asset is None or row.get('need_sha256') != need_identity(need)
                or row.get('asset_sha256') != asset.file.sha256 or not isinstance(identity, str)
                or not re.fullmatch(r'[0-9a-f]{64}', identity)):
            continue
        path = store.materials_root / 'observations' / (identity + '.json')
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 128 * 1024:
            raise ValueError('当前素材观察证据缺失，先恢复报告')
        if requires_reassessment(need, json.loads(path.read_text()), asset.media_type):
            return True
    return False


def nominate_visual_candidates(need, assets, matcher, *, origin_ranks=None, allow_exploration=True):
    """Bound scene/asset associations, not eligibility or visual verdicts.

    Text is only a nomination hint. Keep one non-overlapping candidate for
    incomplete/multilingual metadata; no overlap at all gets a small exploration
    batch. The orchestrator freezes and advances batches within the total
    per-Need/pool budget before returning to bounded query recovery.
    """
    from easel.materials.application.rights import RightsAdmissionStatus, RightsService
    origin_ranks = origin_ranks or {}
    scores = {a.asset_id: matcher._soft_scores(need, a) for a in assets}
    ranked = sorted(assets, key=lambda a: (
        any(scoped_inference(need, a, i) for i in a.semantic.inferences) and observed_match(need, a) is not True,
        RightsService().evaluate(a, need, attribution=RightsService.attribution_condition_for(a)).status
        is RightsAdmissionStatus.BLOCKED,
        origin_ranks.get(a.asset_id, 100000),
        -(scores[a.asset_id][0].semantic or 0), -scores[a.asset_id][1], a.asset_id))
    related = [a for a in ranked if a.asset_id in origin_ranks or (scores[a.asset_id][0].semantic or 0) > 0]
    unexplained = [a for a in ranked if a not in related]
    selected = related[:MAX_PRIMARY_VISUAL_CANDIDATES]
    if allow_exploration and not selected:
        selected += unexplained[:MAX_EXPLORATORY_VISUAL_CANDIDATES]
    return [a.asset_id for a in selected]


def observation_for_need(manifest, need):
    """Share pixels while retaining the full, independent Need identity."""
    current = {**manifest, 'need': need.model_dump(mode='json'), 'need_sha256': need_identity(need)}
    current.pop('input_sha256')
    current['input_sha256'] = hashlib.sha256(json.dumps(current, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return current


def validate_shared_report(group: dict, asset: MaterialAsset, report: dict) -> dict:
    """One image input, independently validated evidence for each Need."""
    rows = report.get('reports')
    manifests = group['observations']
    digest = hashlib.sha256(json.dumps({k: v for k, v in group.items() if k != 'input_sha256'},
                                      sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    if (group.get('schema') != GROUP_SCHEMA or group.get('input_sha256') != digest
            or not 1 <= len(manifests) <= MAX_SHARED_NEEDS
            or len({m['need']['need_id'] for m in manifests}) != len(manifests)):
        raise ValueError('共享观察输入身份或场景数量无效')
    if (report.get('schema') != GROUP_SCHEMA or report.get('input_sha256') != group['input_sha256']
            or not isinstance(rows, dict) or set(rows) != {m['need']['need_id'] for m in manifests}):
        raise ValueError('共享观察必须逐场景覆盖，绑定同一组实际预览')
    for manifest in manifests:
        need = MaterialNeed.model_validate_json(json.dumps(manifest['need']))
        try:
            apply_observation(need, asset, manifest, rows[need.need_id])
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError(f'reports[{need.need_id}]: {exc}') from exc
    return rows


def observe_shared_asset(attempt, need, asset, manifest, attachments, candidate_needs, store, batch_key, executor,
                         *, covered_need_ids=()):
    """Freeze grouping before dispatch; resume the same group after partial writes.

    Individual valid reports remain the ordinary matching checkpoints. Grouping
    only shares the model call, never a matching verdict or Rights evidence.
    """
    key = hashlib.sha256((batch_key + ':' + asset.asset_id + ':' + asset.file.sha256).encode()).hexdigest()
    record_path = store.materials_root / 'observations' / f'shared-input-{key}.json'
    if record_path.is_symlink():
        raise ValueError('共享观察输入路径无效')
    if record_path.is_file():
        groups = json.loads(record_path.read_text(encoding='utf-8'))['groups']
    else:
        pending = []
        for other in candidate_needs:
            if other.need_id in covered_need_ids and other.need_id != need.need_id:
                continue
            current = observation_for_need(manifest, other)
            saved = store.materials_root / 'observations' / (current['input_sha256'] + '.json')
            try:
                read_observation_report(saved, other, asset, current)
            except (OSError, ValueError, TypeError, AttributeError):
                pending.append(current)
        groups = []
        for start in range(0, len(pending), MAX_SHARED_NEEDS):
            group = {'schema': GROUP_SCHEMA, 'observations': pending[start:start + MAX_SHARED_NEEDS]}
            group['input_sha256'] = hashlib.sha256(json.dumps(group, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            groups.append(group)
        store.write_observation_record('shared-input-' + key, {'groups': groups})
    group = next((g for g in groups if any(m['input_sha256'] == manifest['input_sha256'] for m in g['observations'])), None)
    if group is None:
        raise ValueError('当前场景不在已冻结的共享观察中，不能另起观察请求')
    # Reconstructed previews and Need identity must still match the saved group.
    expected = {n.need_id: n for n in candidate_needs}
    for item in group['observations']:
        raw_need = MaterialNeed.model_validate_json(json.dumps(item['need']))
        rebound = observation_for_need(manifest, raw_need)
        if (raw_need.need_id not in expected or expected[raw_need.need_id] != raw_need
                or item != rebound):
            raise ValueError('共享观察需求或预览已变化，不能沿用')
    path = store.materials_root / 'observations' / (group['input_sha256'] + '.json')
    if path.is_symlink():
        raise ValueError('共享观察报告路径无效')
    report = None
    if path.is_file() and path.stat().st_size <= 512 * 1024:
        try:
            report = json.loads(path.read_text(encoding='utf-8'))
            validate_shared_report(group, asset, report)
        except (OSError, ValueError, TypeError, AttributeError):
            report = None
    if report is None:
        report = executor(attempt, group, attachments)
        validate_shared_report(group, asset, report)
        store.write_observation_record(group['input_sha256'], report)
    # Group is durable before distributing individual reports; a crash here
    # resumes this group without another model call.
    for item in group['observations']:
        store.write_observation_record(item['input_sha256'], report['reports'][item['need']['need_id']])
    return report['reports'][need.need_id]


def read_observation_report(path: Path, need: MaterialNeed, asset: MaterialAsset, manifest: dict) -> dict:
    """Only a validated report is a reusable checkpoint, including on resume."""
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 128 * 1024:
        raise ValueError('素材观察报告缺失或路径无效或过大')
    report = json.loads(path.read_text(encoding='utf-8'))
    apply_observation(need, asset, manifest, report)
    return report


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
    if asset.media_type is MediaType.VIDEO and observed_interval(need, asset) is None:
        return False
    return any(scoped_inference(need, asset, i) and i.status is IntelligenceStatus.COMPLETE
               and any(a.field is SemanticField.CAPTION and a.evidence.endswith(":suitable")
                       and a.confidence is not None and a.confidence >= 0.75 for a in i.annotations)
               for i in scoped)


def visual_use_prefix(need: MaterialNeed) -> str:
    """A supplied native element ID prefix, not another production schema."""
    return 'easel-visual-' + need_identity(need)[:16] + '-'


def observed_interval(need: MaterialNeed, asset: MaterialAsset) -> tuple[float, float] | None:
    for inference in asset.semantic.inferences:
        if not scoped_inference(need, asset, inference) or inference.status is not IntelligenceStatus.COMPLETE:
            continue
        for annotation in inference.annotations:
            if annotation.field is not SemanticField.CAPTION or (annotation.confidence or 0) < .75:
                continue
            match = re.search(r':span=([0-9.eE+-]+),([0-9.eE+-]+):suitable$', annotation.evidence or '')
            if match:
                try:
                    start, end = float(match[1]), float(match[2])
                except ValueError:
                    continue
                duration = asset.technical.duration_seconds
                if duration and math.isfinite(start) and math.isfinite(end) and 0 <= start < end <= duration:
                    return start, end
    return None


def _sampled_interval(manifest: dict, rows: list[dict], verdict: str) -> tuple[float, float] | None:
    if manifest['media_type'] != 'video' or verdict not in {'suitable', 'partial'}:
        return None
    if verdict == 'suitable':
        return 0., manifest['duration_seconds']
    runs, start = [], None
    for index, row in enumerate(rows):
        if row['observed'] and row.get('meets_requirements', row['related']) is True:
            start = index if start is None else start
            if index > start:
                runs.append((manifest['frames'][start]['seek_seconds'], manifest['frames'][index]['seek_seconds']))
        else:
            start = None
    # Use actual sample positions; never extend beyond the related observations
    # or bridge an unrelated/unknown frame. A lone positive frame is not a span.
    return max(runs, key=lambda span: span[1] - span[0]) if runs else None


def _jpeg(raw: bytes, edge: int = 384) -> bytes:
    with Image.open(io.BytesIO(raw)) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        image.thumbnail((edge, edge))
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=65)
        return output.getvalue()


def prepare_observation(need: MaterialNeed, asset: MaterialAsset, path: Path, *,
                        preview_cache: dict | None = None) -> tuple[dict, list[dict]]:
    """Decode actual bytes locally, then send bounded images to the agent RPC."""
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    if digest.hexdigest() != asset.file.sha256 or size != asset.file.size:
        raise ValueError("素材字节已变化，不能沿用观察身份")
    # Cache only decoded pixels within one observation pass. Every use still
    # hashes the actual source, and every Need gets a separately bound manifest.
    preview_key = (SCHEMA, asset.file.sha256, asset.file.size,
                   asset.media_type.value, asset.technical.duration_seconds)
    cached = preview_cache.get(preview_key) if preview_cache is not None else None
    if cached is not None:
        frames = cached
    elif asset.media_type is MediaType.IMAGE:
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
    if preview_cache is not None and cached is None:
        if len(preview_cache) >= MAX_VISUAL_CANDIDATES:
            preview_cache.pop(next(iter(preview_cache)))
        preview_cache[preview_key] = frames
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
        raise ValueError("观察报告与当前场景、素材或预览不一致；"
                         f"schema 应为 {SCHEMA}，input_sha256 应为 {manifest.get('input_sha256')}，"
                         f"实际为 {report.get('input_sha256')}")
    if 'requirements_contract' in report:
        from easel.materials.application.visual_contract import assemble_report, digest
        contract = report['requirements_contract']
        if (not isinstance(contract, dict) or contract.get('need_sha256') != need_identity(need)
                or contract.get('source_data', {}).get('need') != need.model_dump(mode='json')):
            raise ValueError('逐项要求合同不属于当前 Need')
        rebuilt = assemble_report(manifest, contract, report.get('compact_results', []))
        if rebuilt != report or report.get('requirements_sha256') != digest(contract):
            raise ValueError('逐项要求、事实和正式适用结论不一致')
    verdict = report.get("verdict")
    if verdict not in {"suitable", "unsuitable", "partial", "uncertain"}:
        raise ValueError("观察报告缺少明确的适用结论")
    rows = report.get("frames")
    if (not isinstance(rows, list) or len(rows) != len(manifest["frames"])
            or any(not isinstance(r, dict) for r in rows)
            or [r.get("index") for r in rows] != list(range(len(rows)))):
        raise ValueError("观察报告必须逐张记录实际预览，不得省略未知项")
    for index, row in enumerate(rows):
        if type(row.get('index')) is not int:
            raise ValueError(f'frames[{index}].index 必须为整数帧编号')
        if type(row.get('observed')) is not bool:
            raise ValueError(f'frames[{index}].observed 必须为 JSON 布尔值 true/false')
        if 'related' not in row or row['related'] is not None and type(row['related']) is not bool:
            raise ValueError(f'frames[{index}].related 只能为 JSON true/false/null；partial 属于顶层 verdict，不是逐帧字段值')
        if not isinstance(row.get('description'), str) or not row['description'].strip():
            raise ValueError(f'frames[{index}].description 必须为非空的实际观察说明')
        if 'meets_requirements' in row and row['meets_requirements'] is not None and type(row['meets_requirements']) is not bool:
            raise ValueError('meets_requirements 只能为 JSON true/false/null')
        if row.get('meets_requirements') is True and (not row['observed'] or row['related'] is not True):
            raise ValueError('适用证据不能来自未观察或不相关画面')
    # Legacy reports use related as their combined applicability field. New
    # reports separate visible subject relevance from complete requirements.
    applicability = [r.get('meets_requirements', r['related']) for r in rows]
    if verdict == "suitable" and not all(r["observed"] and ok is True for r, ok in zip(rows, applicability)):
        raise ValueError("只有部分采样画面适合时，不能批准整项素材匹配")
    if verdict == "unsuitable" and not all(r["observed"] and ok is False for r, ok in zip(rows, applicability)):
        raise ValueError("不适合结论与逐帧证据矛盾：未观察或关联未知应保留 uncertain，部分相关应保留 partial")
    failure_kind = report.get('failure_kind')
    if failure_kind is not None and failure_kind not in {'content_mismatch', 'hard_constraint', 'evidence_insufficient', 'none'}:
        raise ValueError('一般偏好和后期镜头效果不能作为素材拒绝原因')
    if failure_kind == 'evidence_insufficient' and verdict != 'uncertain':
        raise ValueError('证据不足必须保留 uncertain')
    for key in ("caption", "style", "reason"):
        if not isinstance(report.get(key), str) or not report[key].strip() or len(report[key]) > 4000:
            raise ValueError("观察报告缺少画面、风格或判断依据")
    for key in ("logo_present", "visible_text_present"):
        if report.get(key) is not None and type(report[key]) is not bool:
            raise ValueError("标志及文字观察只能是真、假或未知")
    interval = _sampled_interval(manifest, rows, verdict)
    suffix = f'span={interval[0]},{interval[1]}:suitable' if interval else verdict
    evidence = observation_identity(need, asset) + manifest["input_sha256"] + ":" + suffix
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
        status=IntelligenceStatus.COMPLETE if verdict in {"suitable", "unsuitable"} or interval else IntelligenceStatus.PARTIAL,
        annotations=tuple(annotations), observed_at=datetime.now(timezone.utc))
    retained = tuple(i for i in asset.semantic.inferences if i.analyzer_id != inference.analyzer_id)
    return asset.model_copy(update={"semantic": asset.semantic.model_copy(update={
        "inferences": retained + (inference,), "intelligence_status": inference.status,
        "intelligence_error": None,
    })})
