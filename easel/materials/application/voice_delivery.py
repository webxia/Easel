"""Supported, provider-neutral delivery controls on existing Voice Needs."""
from __future__ import annotations

import math
import hashlib
import unicodedata
import json
import re
from functools import lru_cache
from pathlib import Path


def _spoken(text: str) -> str:
    return ''.join(c for c in text if not c.isspace() and not unicodedata.category(c).startswith('P'))


@lru_cache(maxsize=1)
def _asr_script_converter():
    from opencc import OpenCC
    # Standard character conversion only, without regional vocabulary or phonetics.
    return OpenCC('t2s')


def transcribe_local_voice(path: Path, model_path: Path, language: str | None) -> dict:
    """Existing faster-whisper dependency, offline and without script prompting.

    Keep recognizer timestamps; the older subtitle CLI interpolates long segments
    and therefore is not a source of measured alignment for Production.
    """
    from faster_whisper import WhisperModel
    from importlib.metadata import version
    model = WhisperModel(str(model_path), device='cpu', compute_type='int8', local_files_only=True)
    # Inspect the complete generated narration. VAD cuts can remove quiet word
    # onsets and make otherwise clear words appear low-confidence. Keep real
    # silence and recognizer timestamps; do not splice speech before alignment.
    segments, info = model.transcribe(str(path), language=language, beam_size=5,
                                     word_timestamps=True, vad_filter=False,
                                     condition_on_previous_text=False)
    rows = [{'text': word.word, 'start_seconds': word.start, 'end_seconds': word.end,
             'probability': word.probability} for segment in segments for word in (segment.words or [])]
    return {'engine': 'faster-whisper', 'version': version('faster-whisper'),
            'language': info.language, 'words': rows}


LOCAL_ASR_FILES = ('model.bin', 'config.json', 'tokenizer.json')


def local_voice_model_path(config) -> Path:
    configured = config.get('EASEL_ASR_MODEL', '').strip()
    return Path(configured).expanduser() if configured else Path.home() / '.cache/easel-models/faster-whisper-small'


def require_local_voice_model(config=None) -> Path:
    from importlib.util import find_spec
    from easel.runtime_config import EaselRuntimeConfig
    model = local_voice_model_path(config or EaselRuntimeConfig.load())
    if (not model.is_dir() or any(not (model / name).is_file() for name in LOCAL_ASR_FILES)
            or any(find_spec(name) is None for name in ('faster_whisper', 'opencc'))):
        raise ValueError('本地语音识别模型未就绪；未提交新的 TTS，已有旁白保留。请配置 EASEL_ASR_MODEL 本地模型目录')
    return model


@lru_cache(maxsize=4)
def _model_digest(files):
    digest = hashlib.sha256()
    for name, size, modified in files:
        with Path(name).open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
    return digest.hexdigest()


def voice_verification_identity(language=None, model=None):
    from importlib.metadata import version
    model = model or require_local_voice_model()
    files = tuple((str(model / name), (model / name).stat().st_size, (model / name).stat().st_mtime_ns)
                  for name in LOCAL_ASR_FILES)
    return {'model_sha256': _model_digest(files), 'engine': 'faster-whisper',
            'version': version('faster-whisper'), 'language': language,
            'parameters': {'device': 'cpu', 'compute_type': 'int8', 'beam_size': 5,
                           'word_timestamps': True, 'vad_filter': False, 'condition_on_previous_text': False},
            'rules': 'complete-voice-and-independent-interval@2'}


def read_local_voice(path: Path, language: str | None, *, model_path: Path | None = None) -> dict:
    """Bound local recognition in a child process; never download or call TTS."""
    import subprocess
    import sys
    model = require_local_voice_model({'EASEL_ASR_MODEL': str(model_path)}) if model_path else require_local_voice_model()
    identity = voice_verification_identity(language, model)
    code = ('import json,sys; from pathlib import Path; '
            'from easel.materials.application.voice_delivery import transcribe_local_voice; '
            'print(json.dumps(transcribe_local_voice(Path(sys.argv[1]), Path(sys.argv[2]), '
            'sys.argv[3] or None), ensure_ascii=False))')
    try:
        result = subprocess.run([sys.executable, '-c', code, str(path), str(model.resolve()), language or ''],
                                capture_output=True, timeout=180, check=True)
        if len(result.stdout) > 2_000_000:
            raise ValueError('本地语音识别结果过大，未认领时序')
        report = json.loads(result.stdout)
    except (subprocess.SubprocessError, OSError, json.JSONDecodeError) as exc:
        raise ValueError('本地语音识别未完成；原旁白已保留，只重试识别') from exc
    if not isinstance(report, dict):
        raise ValueError('本地语音识别结果格式无效；原旁白已保留')
    report['model_sha256'] = identity['model_sha256']
    report['verification_config'] = identity
    return report


VOICE_ASR_REVIEW_PREFIX = 'creator-voice-asr-review-v1:'

# The single configured recognizer remains unchanged. This is an admission
# policy, not a fabricated/calibrated probability or a new recognition run.
VOICE_CONFIDENCE_POLICY = {
    'revision': 'bounded-voice-confidence@1', 'word_floor': .25,
    'low_character_fraction': .05, 'low_character_cap': 3,
    'character_weighted_mean_floor': .85,
}


def bounded_voice_confidence(script, asset, report):
    """Permit sparse uncertainty only after complete exact text/time checking."""
    low = recognition_uncertain_positions(script, asset, report)
    rows = report['words']
    lengths = [len(_spoken(row['text'])) for row in rows]
    total = sum(lengths)
    count = sum(lengths[index] for index in low)
    minimum = min(row['probability'] for row in rows)
    mean = math.fsum(row['probability'] * length for row, length in zip(rows, lengths)) / total
    limit = min(VOICE_CONFIDENCE_POLICY['low_character_cap'],
                math.floor(total * VOICE_CONFIDENCE_POLICY['low_character_fraction']))
    if (not low or minimum < VOICE_CONFIDENCE_POLICY['word_floor'] or count > limit
            or mean < VOICE_CONFIDENCE_POLICY['character_weighted_mean_floor']):
        raise ValueError('本地旁白识别置信度不足；有限放宽仍要求最低词分数≥0.25、'
                         '低于0.5的字符不超过全文5%且最多3字、按字符加权均值≥0.85；'
                         '原报告和音频保留，未重复识别或TTS')
    return {'policy': dict(VOICE_CONFIDENCE_POLICY), 'minimum_word_probability': minimum,
            'character_weighted_mean': mean, 'low_confidence_characters': count,
            'spoken_characters': total}


def recognition_digest(report: dict) -> str:
    return hashlib.sha256(json.dumps(report, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _reviewed_character(script: str, asset, report: dict, position: int) -> bool:
    from easel.materials.domain import IntelligenceStatus, SemanticField
    if (report.get('audio_sha256') != asset.file.sha256
            or report.get('script_sha256') != hashlib.sha256(script.encode()).hexdigest()
            or not re.fullmatch(r'[0-9a-f]{64}', str(report.get('need_sha256', '')))):
        return False
    prefix = (VOICE_ASR_REVIEW_PREFIX + report['need_sha256'] + ':' + asset.file.sha256
              + ':' + report['script_sha256'] + ':' + recognition_digest(report) + ':')
    return any(i.analyzer_id.startswith(VOICE_ASR_REVIEW_PREFIX) and i.status is IntelligenceStatus.COMPLETE
        and any(a.field is SemanticField.CAPTION and a.value == script[position]
                and a.evidence == prefix + str(position) and a.confidence == 1.0
                for a in i.annotations) for i in asset.semantic.inferences)


def timing_from_recognition(script: str, asset, report: dict) -> dict:
    """Accept complete unprompted recognition, never interpolate or rewrite text."""
    words = report.get('words')
    if not isinstance(words, list) or not words or len(words) > 20000:
        raise ValueError('旁白识别没有有效时间依据；原音频已保留')
    positions = [i for i, c in enumerate(script) if _spoken(c)]
    offset, cues, relaxed = 0, [], None
    for word_index, word in enumerate(words):
        if not isinstance(word, dict) or not isinstance(word.get('text'), str):
            raise ValueError('旁白识别结果格式无效')
        text = _spoken(word['text'])
        confidence = word.get('probability')
        if not text:
            raise ValueError('旁白识别包含无有效文字的条目；原音频已保留')
        if type(confidence) not in (int, float) or not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError('旁白识别置信度格式无效；原音频已保留')
        if confidence < .5:
            if report.get('supplements'):
                # Retain already valid independent historical evidence. The
                # current Owner never downloads or invokes a second model.
                from easel.materials.application.voice_supplement import verify_interval
                proofs = [p for p in report['supplements'] if p.get('word_index') == word_index]
                if len(proofs) != 1 or not verify_interval(script, asset, report, word_index, proofs[0]):
                    raise ValueError('本地旁白识别置信度不足，历史局部声音证据不完整')
            elif relaxed is None:
                relaxed = bounded_voice_confidence(script, asset, report)
        if offset + len(text) > len(positions):
            raise ValueError('旁白识别包含脚本之外的多余内容；原音频已保留，不能猜测字幕时序')
        begin, end = positions[offset], positions[offset + len(text) - 1] + 1
        expected = _spoken(script[begin:end])
        if text != expected:
            convert = _asr_script_converter().convert
            actual, wanted = convert(text), convert(expected)
            reviewed = (len(actual) == len(wanted) == len(text) == len(expected) and all(a == b or _reviewed_character(
                script, asset, report, positions[offset + index])
                for index, (a, b) in enumerate(zip(actual, wanted))))
            if actual != wanted and not reviewed:
                raise ValueError(f'旁白识别文字与冻结脚本不一致（第 {offset + 1} 个有效字符：'
                                 f'识别“{text[:40]}”，脚本“{expected[:40]}”）；'
                                 '这不能单独证明原音频读错；原音频已保留，未重购或改写')
        # Display and character offsets always come from the frozen script. Keep
        # raw recognition intact below (including its hash), with measured times.
        cues.append({'text': script[begin:end], 'start_character': begin, 'end_character': end,
                     'start_seconds': word.get('start_seconds'), 'end_seconds': word.get('end_seconds')})
        offset += len(text)
    timing = bind_voice_timing(script, asset, tuple(cues))
    if offset != len(positions) or timing['status'] != 'READY':
        raise ValueError('识别内容或时间与完整冻结旁白不一致；原音频已保留，未重购或改写')
    # The compiler displays sentences. Group recognized words using frozen
    # punctuation, while keeping only measured word starts/ends as boundaries.
    sentences, start = [], 0
    for index, cue in enumerate(cues):
        next_begin = cues[index + 1]['start_character'] if index + 1 < len(cues) else len(script)
        span = script[cues[start]['start_character']:next_begin]
        # Reading groups end only on measured recognition word boundaries;
        # punctuation or a long phrase does not fabricate new speech times.
        if (index + 1 == len(cues) or re.search(r'[。！？.!?；;\n]', script[cue['start_character']:next_begin])
                or len(span) >= 24 or (len(span) >= 12 and re.search(r'[，,:：]', script[cue['end_character']:next_begin]))):
            first = cues[start]
            sentences.append({'text': script[first['start_character']:cue['end_character']],
                              'start_character': first['start_character'], 'end_character': cue['end_character'],
                              'start_seconds': first['start_seconds'], 'end_seconds': cue['end_seconds']})
            start = index + 1
    timing = bind_voice_timing(script, asset, tuple(sentences))
    timing.update(source='local_asr', recognition_sha256=hashlib.sha256(
        json.dumps(report, sort_keys=True, ensure_ascii=False).encode()).hexdigest())
    if relaxed is not None:
        timing['confidence_acceptance'] = relaxed
    return timing


def pending_voice_timing_recovery(plan, bundle, store, script: str, *, require_content: bool = False) -> list[dict]:
    assets = {a.asset_id: a for a in bundle.assets}
    needs = {n.need_id: n for n in plan.needs if getattr(n.modality_spec, 'kind', None) == 'voice'}
    pending = []
    for record in store.list_generation_records():
        need, asset = needs.get(record.get('need_id')), assets.get(record.get('asset_id'))
        if (need is None or asset is None or record.get('schema') != 'easel-material-generation@1'
                or record.get('status') != 'COMPLETE' or record.get('modality') != 'voice'
                or record.get('attempt_id') != plan.attempt_id or record.get('plan_id') != plan.plan_id
                or record.get('input_sha256') != hashlib.sha256(script.encode()).hexdigest()
                or record.get('need_sha256') != hashlib.sha256(need.to_json().encode()).hexdigest()
                or record.get('asset_sha256') != asset.file.sha256):
            continue
        timing = record.get('voice_timing') or {}
        if require_content and (_recognized_timing(record, need, asset, script) is None
                                or not voice_content_observed(need, asset)):
            pending.append(record)
        elif (not isinstance(timing.get('cues'), list)
                or bind_voice_timing(script, asset, tuple(timing['cues']), timing.get('error'))['status'] != 'READY'):
            pending.append(record)
        elif timing.get('source') == 'local_asr' and _recognized_timing(record, need, asset, script) != timing:
            pending.append(record)
    return pending


VOICE_CONTENT_PREFIX = 'easel-voice-content-v1:'


def _voice_content_binding(need, asset) -> str:
    return (VOICE_CONTENT_PREFIX + hashlib.sha256(need.to_json().encode()).hexdigest()
            + ':' + asset.file.sha256 + ':' + str(need.modality_spec.text_sha256) + ':')


def voice_content_observed(need, asset) -> bool:
    """Script completeness evidence, not speaker identity or listening approval."""
    from easel.materials.domain import IntelligenceStatus, SemanticField
    if getattr(need.modality_spec, 'kind', None) != 'voice' or not need.modality_spec.text_sha256:
        return False
    binding = _voice_content_binding(need, asset)
    return any(i.analyzer_id == VOICE_CONTENT_PREFIX + need.need_id
        and i.status is IntelligenceStatus.COMPLETE and any(
            a.field is SemanticField.CAPTION and a.evidence and a.evidence.startswith(binding)
            and re.fullmatch(r'[0-9a-f]{64}:complete(?::independent|:bounded-confidence-v1)?', a.evidence[len(binding):])
            and isinstance(a.value, str) and hashlib.sha256(a.value.encode()).hexdigest() == need.modality_spec.text_sha256
            and (a.confidence is not None and a.confidence >= .5
                 or a.confidence is None and a.evidence.endswith(':complete:independent')
                 or a.confidence is not None and VOICE_CONFIDENCE_POLICY['word_floor'] <= a.confidence < .5
                    and a.evidence.endswith(':complete:bounded-confidence-v1')) for a in i.annotations)
        for i in asset.semantic.inferences)


def apply_voice_content(need, asset, script: str, report: dict):
    from datetime import datetime, timezone
    from easel.materials.domain import IntelligenceStatus, SemanticAnnotation, SemanticField, SemanticInference
    if (getattr(need.modality_spec, 'kind', None) != 'voice'
            or need.modality_spec.text_sha256 != hashlib.sha256(script.encode()).hexdigest()
            or report.get('audio_sha256') != asset.file.sha256
            or report.get('script_sha256') != need.modality_spec.text_sha256
            or report.get('need_sha256') != hashlib.sha256(need.to_json().encode()).hexdigest()):
        raise ValueError('旁白观察与当前音频、脚本或 Need 不一致')
    timing = timing_from_recognition(script, asset, report)
    inference = SemanticInference(analyzer_id=VOICE_CONTENT_PREFIX + need.need_id,
        status=IntelligenceStatus.COMPLETE, observed_at=datetime.now(timezone.utc),
        annotations=(SemanticAnnotation(field=SemanticField.CAPTION, value=script,
            confidence=None if report.get('supplements') else min(w['probability'] for w in report['words']),
            evidence=_voice_content_binding(need, asset) + timing['recognition_sha256'] + ':complete'
                + (':independent' if report.get('supplements') else ':bounded-confidence-v1'
                   if timing.get('confidence_acceptance') else '')),))
    retained = tuple(i for i in asset.semantic.inferences if i.analyzer_id != inference.analyzer_id)
    return asset.model_copy(update={'semantic': asset.semantic.model_copy(update={'inferences': retained + (inference,)})})


def _recognized_timing(record, need, asset, script):
    report = record.get('voice_recognition')
    if (not isinstance(report, dict) or report.get('audio_sha256') != asset.file.sha256
            or report.get('script_sha256') != hashlib.sha256(script.encode()).hexdigest()
            or report.get('need_sha256') != hashlib.sha256(need.to_json().encode()).hexdigest()):
        return None
    try:
        return timing_from_recognition(script, asset, report)
    except ValueError:
        return None

TONES = frozenset({"neutral", "happy", "sad", "angry", "afraid", "disgusted", "surprised"})
DEFAULT_DELIVERY = {"pace_ratio": 1.0, "pitch_semitones": 0, "tone": None}
PACE_RANGE = (0.5, 2)
PITCH_RANGE = (-12, 12)


def voice_delivery_schema():
    """Publish the same controls/ranges used by the existing consumer."""
    return {'type':'object', 'additionalProperties':False, 'properties':{
        'pace_ratio':{'type':'number','minimum':PACE_RANGE[0],'maximum':PACE_RANGE[1]},
        'pitch_semitones':{'type':'integer','minimum':PITCH_RANGE[0],'maximum':PITCH_RANGE[1]},
        'tone':{'enum':[None,*sorted(TONES)]}}}


def validate_voice_delivery(value: object) -> dict:
    if not isinstance(value, dict) or set(value) - set(DEFAULT_DELIVERY):
        raise ValueError("旁白执行要求仅支持 pace_ratio、pitch_semitones、tone")
    result = {**DEFAULT_DELIVERY, **value}
    pace, pitch, tone = result["pace_ratio"], result["pitch_semitones"], result["tone"]
    if type(pace) not in (int, float) or not math.isfinite(pace) or not PACE_RANGE[0] <= pace <= PACE_RANGE[1]:
        raise ValueError("旁白语速倍率必须在 0.5 至 2 之间")
    if type(pitch) is not int or not PITCH_RANGE[0] <= pitch <= PITCH_RANGE[1]:
        raise ValueError("旁白音高调整必须为 -12 至 12 的整数半音")
    if tone is not None and (not isinstance(tone, str) or tone not in TONES):
        raise ValueError("当前旁白执行器不支持该情绪要求")
    return result


def bind_voice_timing(script: str, asset, cues: tuple[dict, ...], error: str | None = None) -> dict:
    """Check provider alignment against input text and inspected audio duration.

    This proves a usable timing contract, not ASR accuracy or listening quality.
    """
    result = {"schema": "easel-voice-timing@1", "source": "provider_alignment",
              "script_sha256": hashlib.sha256(script.encode()).hexdigest(),
              "asset_id": asset.asset_id, "audio_sha256": asset.file.sha256,
              "audio_duration_seconds": asset.technical.duration_seconds,
              "status": "UNAVAILABLE", "cues": list(cues), "error": error}
    if error or not cues or asset.technical.duration_seconds is None:
        result["error"] = error or "alignment_or_duration_missing"
        return result

    last_time, last_character = 0.0, 0
    try:
        for cue in cues:
            start, end = cue["start_seconds"], cue["end_seconds"]
            begin, finish = cue["start_character"], cue["end_character"]
            if (any(type(t) not in (int, float) or not math.isfinite(t) for t in (start, end))
                    or not last_time <= start < end <= asset.technical.duration_seconds + 0.1
                    or type(begin) is not int or type(finish) is not int
                    or not last_character <= begin < finish <= len(script)
                    or _spoken(script[last_character:begin])
                    or not isinstance(cue["text"], str) or not _spoken(cue["text"])
                    or _spoken(cue["text"]) != _spoken(script[begin:finish])):
                raise ValueError("alignment does not cover frozen speech")
            last_time, last_character = end, finish
        if _spoken(script[last_character:]):
            raise ValueError("alignment does not cover complete speech")
    except (KeyError, TypeError, ValueError):
        result.update(status="INVALID", error="alignment_text_or_time_mismatch")
        return result
    result.update(status="READY", error=None)
    return result


def authoring_voice_timings(plan, bundle, store, script: str) -> dict:
    """Project only timing belonging to current, admitted voice candidates."""
    records = store.list_generation_records()
    rows, unavailable = [], []
    for need in plan.needs:
        if getattr(need.modality_spec, "kind", None) != "voice":
            continue
        matched = {m.asset_id for m in bundle.matches if m.qualified and m.need_id == need.need_id}
        found = False
        for asset in bundle.assets:
            if asset.asset_id not in matched:
                continue
            for record in records:
                timing = record.get("voice_timing")
                if (record.get("schema") != "easel-material-generation@1" or record.get("status") != "COMPLETE"
                        or record.get("asset_id") != asset.asset_id or record.get("asset_sha256") != asset.file.sha256
                        or record.get("need_sha256") != hashlib.sha256(need.to_json().encode()).hexdigest()
                        or not isinstance(timing, dict) or timing.get("schema") != "easel-voice-timing@1"
                        or timing.get("audio_sha256") != asset.file.sha256
                        or timing.get("script_sha256") != hashlib.sha256(script.encode()).hexdigest()):
                    continue
                if not isinstance(timing.get("cues"), list):
                    continue
                current = bind_voice_timing(script, asset, tuple(timing["cues"]), timing.get("error"))
                if current["status"] == "READY":
                    if timing.get('source') == 'local_asr':
                        checked = _recognized_timing(record, need, asset, script)
                        if checked != timing:
                            continue
                        current = checked
                    recognized = _recognized_timing(record, need, asset, script)
                    if recognized and len(recognized['cues']) > len(current['cues']):
                        # Reuse already verified full-audio content observation;
                        # retain provider timing in its original record.
                        current = recognized
                    # Only punctuation/whitespace may lie between validated
                    # ranges. Keep every source character exactly once, with
                    # trailing punctuation on the preceding sentence.
                    current["cues"] = [
                        {**cue, "display_text": script[
                            0 if i == 0 else cue["start_character"]:
                            current["cues"][i + 1]["start_character"]
                            if i + 1 < len(current["cues"]) else len(script)
                        ]}
                        for i, cue in enumerate(current["cues"])
                    ]
                    rows.append({"need_id": need.need_id, **current})
                    found = True
                    break
        if not found:
            unavailable.append(need.need_id)
    return {"schema": "easel-production-voice-timing@1", "assets": rows, "unavailable_need_ids": unavailable}


def voice_recovery_identity(binding, verification):
    # Admission changes invalidate an old failure, not the recognizer cache.
    # The primary identity remains the same so original observations are reused.
    return 'voice-asr-' + recognition_digest({**binding, 'verification': verification,
                                            'confidence_policy': VOICE_CONFIDENCE_POLICY})


def recognition_uncertain_positions(script, asset, report):
    """Check full content/time shape before spending on isolated uncertainty.

    This returns positions only, never an accepted timing or modified confidence.
    Independent evidence must still pass the normal voice admission below.
    """
    rows = report.get('words')
    if not isinstance(rows, list) or not rows or len(rows) > 20000:
        raise ValueError('完整声音证据无效，不能直接转局部补证')
    actual, last, low = [], 0., []
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or not isinstance(row.get('text'), str) or not _spoken(row['text']):
            raise ValueError('完整声音证据条目无效')
        p, begin, end = row.get('probability'), row.get('start_seconds'), row.get('end_seconds')
        if (any(type(v) not in (int, float) or not math.isfinite(v) for v in (p, begin, end))
                or not 0 <= p <= 1 or not last <= begin < end <= asset.technical.duration_seconds + .1):
            raise ValueError('完整声音概率或实测时间无效')
        actual.append(_spoken(row['text']))
        last = end
        if p < .5:
            low.append(index)
    convert = _asr_script_converter().convert
    if convert(''.join(actual)) != convert(_spoken(script)):
        raise ValueError('完整声音内容仍有错配/增删缺口，不能把它当作单纯低置信补证')
    return low
