"""Offline acoustic evidence for BGM; model scores are not listening approval."""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

SCHEMA = 'easel-music-observation@1'
PREFIX = 'easel-music-v1:'
MODEL_ID = 'MIT/ast-finetuned-audioset-10-10-0.4593'
MODEL_REVISION = 'f826b80d28226b62986cc218e5cec390b1096902'
MODEL_FILES = {
    'config.json': 'a93d525511d77e8ecc933d09674b85099815bbbb417c228a4edd655e252fb9ff',
    'preprocessor_config.json': '8d04ba5a9c6fca5d39d0de2b1fd05ecf79deb589fbba279728bbebac39934231',
    'model.safetensors': 'ae0c1e2ad4e1381d851fa9bf298ba13ebc9c5a914cdee2dbe427a6583869924d',
}
VOCAL_LABELS = frozenset({'Speech', 'Male speech, man speaking', 'Female speech, woman speaking',
    'Child speech, kid speaking', 'Speech synthesizer', 'Singing', 'Chant', 'Male singing',
    'Female singing', 'Child singing', 'Synthetic singing', 'Rapping', 'Humming',
    'Hubbub, speech noise, speech babble', 'Vocal music', 'Choir', 'A capella',
    'Yodeling', 'Mantra'})
POLICY = {
    'revision': 'bgm-practical@4',
    'vocal_labels': sorted(VOCAL_LABELS),
    'music_min': .5, 'music_floor': .2,
    'music_coverage_min': .9, 'music_unknown_max_seconds': 5.,
    'instrumental_vocal_max': .02,
    'vocal_detected_min': .2, 'tag_min': .2, 'silence_rms_min': .0001,
}
POLICY_DIGEST = hashlib.sha256(json.dumps(POLICY, sort_keys=True).encode()).hexdigest()


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def require_local_music_model(config=None) -> Path:
    from importlib.util import find_spec
    from easel.runtime_config import EaselRuntimeConfig
    config = config or EaselRuntimeConfig.load()
    configured = config.get('EASEL_MUSIC_MODEL', '').strip()
    root = Path(configured).expanduser() if configured else Path.home() / '.cache/easel-models/ast-audioset'
    if any(find_spec(name) is None for name in ('torch', 'transformers')):
        raise ValueError('本地配乐观察依赖未就绪；请安装 Easel audio-observation 可选依赖，原素材保留')
    if any(not (root / name).is_file() or file_digest(root / name) != digest for name, digest in MODEL_FILES.items()):
        raise ValueError('本地配乐观察模型缺失或版本不符；请配置 EASEL_MUSIC_MODEL，原素材保留')
    return root


def classify_music(path: Path, model_path: Path) -> dict:
    """Score overlapping ten-second windows, including the complete tail.

    No online model fetch, arbitrary model code, expected text or Need enters
    inference. The official AudioSet model is multi-label: use sigmoid logits.
    """
    if any(file_digest(model_path / name) != digest for name, digest in MODEL_FILES.items()):
        raise ValueError('配乐观察模型文件已变化')
    import numpy as np
    import torch
    from transformers import ASTFeatureExtractor, ASTForAudioClassification
    decoded = subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-protocol_whitelist', 'file,pipe',
        '-i', str(path), '-vn', '-ac', '1', '-ar', '16000', '-t', '301', '-f', 'f32le', 'pipe:1'],
        capture_output=True, check=True, timeout=60)
    pcm = np.frombuffer(decoded.stdout, dtype='<f4')
    if not 16000 <= len(pcm) <= 300 * 16000 or not np.isfinite(pcm).all():
        raise ValueError('配乐观察支持 1～300 秒的有效音频')
    extractor = ASTFeatureExtractor.from_pretrained(str(model_path), local_files_only=True)
    model = ASTForAudioClassification.from_pretrained(str(model_path), local_files_only=True, use_safetensors=True).eval()
    labels = {int(k): v for k, v in model.config.id2label.items()}
    if not VOCAL_LABELS <= set(labels.values()) or 'Music' not in labels.values():
        raise ValueError('配乐观察模型标签不符合已核实契约')
    width, step = 10 * 16000, 5 * 16000
    starts = sorted(set(range(0, max(1, len(pcm) - width + 1), step)) | {max(0, len(pcm) - width)})
    windows = []
    with torch.inference_mode():
        for start in starts:
            samples = pcm[start:start + width]
            inputs = extractor(samples.copy(), sampling_rate=16000, return_tensors='pt')
            scores = model(**inputs).logits.sigmoid()[0].tolist()
            windows.append({'start_seconds': start / 16000, 'end_seconds': (start + len(samples)) / 16000,
                'rms': float(np.sqrt(np.mean(samples.astype(float) ** 2))),
                'scores': {labels[i]: round(float(score), 6) for i, score in enumerate(scores)}})
    return {'schema': SCHEMA, 'model': MODEL_ID, 'model_revision': MODEL_REVISION,
            'model_sha256': MODEL_FILES['model.safetensors'], 'audio_sha256': file_digest(path),
            'duration_seconds': len(pcm) / 16000, 'windows': windows,
            'scope': 'overlapping waveform classification; scores are not calibrated probabilities or human listening'}


def read_local_music(path: Path) -> dict:
    model = require_local_music_model()
    code = ('import json,sys; from pathlib import Path; '
            'from easel.materials.application.music_observation import classify_music; '
            'print(json.dumps(classify_music(Path(sys.argv[1]),Path(sys.argv[2]))))')
    try:
        result = subprocess.run([sys.executable, '-c', code, str(path), str(model.resolve())],
                                capture_output=True, timeout=240, check=True)
        if len(result.stdout) > 2_000_000:
            raise ValueError('配乐观察报告过大')
        return json.loads(result.stdout)
    except (subprocess.SubprocessError, OSError, json.JSONDecodeError) as exc:
        raise ValueError('本地配乐观察未完成；原素材保留，只重试观察') from exc


def assess_music(asset, report: dict) -> tuple[str, list[str]]:
    """Conservative routing evidence, not a guarantee that no vocal exists."""
    duration = asset.technical.duration_seconds
    if (not isinstance(report, dict)
            or report.get('schema') != SCHEMA or report.get('model') != MODEL_ID
            or report.get('model_revision') != MODEL_REVISION
            or report.get('model_sha256') != MODEL_FILES['model.safetensors']
            or report.get('audio_sha256') != asset.file.sha256
            or type(duration) not in (int, float) or not 1 <= duration <= 300 or not math.isfinite(duration)
            or type(report.get('duration_seconds')) not in (int, float)
            or not 1 <= report['duration_seconds'] <= 300
            or not math.isfinite(report['duration_seconds'])
            or abs(report['duration_seconds'] - duration) > .15):
        raise ValueError('配乐观察身份或覆盖范围不一致')
    windows = report.get('windows')
    if not isinstance(windows, list) or not 1 <= len(windows) <= 61:
        raise ValueError('配乐观察缺少有界声音窗口')
    end, music, vocals, tags = 0., [], [], set()
    for row in windows:
        if not isinstance(row, dict):
            raise ValueError('配乐观察窗口、分类分数或连续覆盖无效')
        start, stop, scores, rms = (row.get(k) for k in ('start_seconds', 'end_seconds', 'scores', 'rms'))
        if (any(type(v) not in (int, float) or not math.isfinite(v) for v in (start, stop, rms))
                or not 0 <= start <= end + .01 or not end < stop <= duration + .15
                or not .5 <= stop - start <= 10.01 or rms < 0
                or not isinstance(scores, dict) or not VOCAL_LABELS | {'Music'} <= scores.keys()
                or any(not isinstance(label, str) or not label for label in scores)
                or any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in scores.values())):
            raise ValueError('配乐观察窗口、分类分数或连续覆盖无效')
        end = stop
        music.append(scores['Music'] if rms >= POLICY['silence_rms_min'] else 0.)
        vocals.append(max(scores[label] for label in VOCAL_LABELS))
        tags.update(label for label, score in scores.items() if score >= POLICY['tag_min'])
    if abs(end - duration) > .15:
        raise ValueError('配乐观察未覆盖尾部')
    # A low vocal score alone never qualifies silence, noise or weak music.
    verdict = ('vocals_detected' if max(vocals) >= POLICY['vocal_detected_min'] else
               'instrumental_music' if music_supported(report)
               and max(vocals) <= POLICY['instrumental_vocal_max'] else 'unknown')
    return verdict, sorted(tags)


def music_supported(report: dict) -> bool:
    """Integrate validated real time once; overlapping windows add no votes.

    Brief uncertain musical transitions may pass. Silence or a clearly
    non-musical window remains a veto, even at either edge of the track.
    """
    duration = report['duration_seconds']
    windows = report['windows']
    if any(w['rms'] < POLICY['silence_rms_min']
           or w['scores']['Music'] < POLICY['music_floor'] for w in windows):
        return False
    cuts = sorted({0., duration, *(w['start_seconds'] for w in windows),
                   *(min(duration, w['end_seconds']) for w in windows)})
    supported, uncertain, longest = 0., 0., 0.
    for start, stop in zip(cuts, cuts[1:]):
        covering = [w for w in windows if w['start_seconds'] <= start
                    and w['end_seconds'] >= stop]
        if not covering:
            return False
        if all(w['scores']['Music'] >= POLICY['music_min'] for w in covering):
            supported += stop - start
            uncertain = 0.
        else:
            uncertain += stop - start
            longest = max(longest, uncertain)
    return (supported / duration >= POLICY['music_coverage_min']
            and longest <= POLICY['music_unknown_max_seconds'])


def binding(need, asset) -> str:
    return PREFIX + POLICY_DIGEST + ':' + hashlib.sha256(need.to_json().encode()).hexdigest() + ':' + asset.file.sha256 + ':'


def analyzer_id(need) -> str:
    return PREFIX + POLICY_DIGEST + ':' + need.need_id


def music_observed(need, asset) -> bool | None:
    if getattr(need.modality_spec, 'kind', None) != 'bgm':
        return None
    from easel.materials.domain import SemanticField, IntelligenceStatus
    values = [a.value for i in asset.semantic.inferences if i.analyzer_id == analyzer_id(need)
              for a in i.annotations if a.field is SemanticField.CAPTION
              and a.evidence and a.evidence.startswith(binding(need, asset))
              and len(a.evidence.removeprefix(binding(need, asset))) == 64
              and i.status in {IntelligenceStatus.COMPLETE, IntelligenceStatus.PARTIAL}]
    if not values:
        return None
    return any(v == 'instrumental_music' or (v == 'vocal_music' and need.modality_spec.vocals_allowed) for v in values)


def apply_music_observation(need, asset, report):
    from easel.materials.domain import IntelligenceStatus, SemanticAnnotation, SemanticField, SemanticInference
    if getattr(need.modality_spec, 'kind', None) != 'bgm':
        raise ValueError('当前声音观察仅适用于 BGM')
    verdict, tags = assess_music(asset, report)
    if verdict == 'vocals_detected' and music_supported(report):
        verdict = 'vocal_music'
    digest = hashlib.sha256(json.dumps(report, sort_keys=True).encode()).hexdigest()
    evidence = binding(need, asset) + digest
    if any(i.analyzer_id == analyzer_id(need) and i.annotations
           and all(a.evidence == evidence for a in i.annotations) for i in asset.semantic.inferences):
        return asset
    inference = SemanticInference(analyzer_id=analyzer_id(need),
        status=IntelligenceStatus.PARTIAL if verdict == 'unknown' else IntelligenceStatus.COMPLETE,
        annotations=(SemanticAnnotation(field=SemanticField.CAPTION, value=verdict, evidence=evidence),
                     SemanticAnnotation(field=SemanticField.TAGS, value=tuple(tags), evidence=evidence)))
    return asset.model_copy(update={'semantic': asset.semantic.model_copy(update={
        'inferences': tuple(i for i in asset.semantic.inferences if i.analyzer_id != inference.analyzer_id) + (inference,),
        'intelligence_status': inference.status, 'intelligence_error': None})})
