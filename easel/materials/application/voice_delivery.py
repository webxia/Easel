"""Supported, provider-neutral delivery controls on existing Voice Needs."""
from __future__ import annotations

import math
import hashlib
import unicodedata
import json
import re
from pathlib import Path


def _spoken(text: str) -> str:
    return ''.join(c for c in text if not c.isspace() and not unicodedata.category(c).startswith('P'))


def transcribe_local_voice(path: Path, model_path: Path, language: str | None) -> dict:
    """Existing faster-whisper dependency, offline and without script prompting.

    Keep recognizer timestamps; the older subtitle CLI interpolates long segments
    and therefore is not a source of measured alignment for Production.
    """
    from faster_whisper import WhisperModel
    from importlib.metadata import version
    model = WhisperModel(str(model_path), device='cpu', compute_type='int8', local_files_only=True)
    segments, info = model.transcribe(str(path), language=language, beam_size=5,
                                     word_timestamps=True, vad_filter=True,
                                     condition_on_previous_text=False)
    rows = [{'text': word.word, 'start_seconds': word.start, 'end_seconds': word.end,
             'probability': word.probability} for segment in segments for word in (segment.words or [])]
    return {'engine': 'faster-whisper', 'version': version('faster-whisper'),
            'language': info.language, 'words': rows}


LOCAL_ASR_FILES = ('model.bin', 'config.json', 'tokenizer.json')


def local_voice_model_path(config) -> Path:
    configured = config.get('EASEL_ASR_MODEL', '').strip()
    return Path(configured).expanduser() if configured else Path.home() / '.cache/easel-models/faster-whisper-small'


def read_local_voice(path: Path, language: str | None) -> dict:
    """Bound local recognition in a child process; never download or call TTS."""
    import subprocess
    import sys
    from easel.runtime_config import EaselRuntimeConfig
    model = local_voice_model_path(EaselRuntimeConfig.load())
    if not model.is_dir() or any(not (model / name).is_file() for name in LOCAL_ASR_FILES):
        raise ValueError('本地语音识别模型未就绪；已保留旁白，不会重新生成。请配置 EASEL_ASR_MODEL 本地模型目录')
    model_digest = hashlib.sha256()
    for name in LOCAL_ASR_FILES:
        with (model / name).open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                model_digest.update(chunk)
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
    report['model_sha256'] = model_digest.hexdigest()
    return report


def timing_from_recognition(script: str, asset, report: dict) -> dict:
    """Accept complete unprompted recognition, never interpolate or rewrite text."""
    words = report.get('words')
    if not isinstance(words, list) or not words or len(words) > 20000:
        raise ValueError('旁白识别没有有效时间依据；原音频已保留')
    positions = [i for i, c in enumerate(script) if _spoken(c)]
    offset, cues = 0, []
    for word in words:
        if not isinstance(word, dict) or not isinstance(word.get('text'), str):
            raise ValueError('旁白识别结果格式无效')
        text = _spoken(word['text'])
        confidence = word.get('probability')
        if (not text or type(confidence) not in (int, float) or not math.isfinite(confidence)
                or not .5 <= confidence <= 1 or offset + len(text) > len(positions)):
            raise ValueError('旁白识别有低置信或多余内容；不能猜测字幕时序')
        begin, end = positions[offset], positions[offset + len(text) - 1] + 1
        cues.append({'text': word['text'], 'start_character': begin, 'end_character': end,
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
        if index + 1 == len(cues) or re.search(r'[。！？.!?；;\n]', script[cue['start_character']:next_begin]):
            first = cues[start]
            sentences.append({'text': script[first['start_character']:cue['end_character']],
                              'start_character': first['start_character'], 'end_character': cue['end_character'],
                              'start_seconds': first['start_seconds'], 'end_seconds': cue['end_seconds']})
            start = index + 1
    timing = bind_voice_timing(script, asset, tuple(sentences))
    timing.update(source='local_asr', recognition_sha256=hashlib.sha256(
        json.dumps(report, sort_keys=True, ensure_ascii=False).encode()).hexdigest())
    return timing


def pending_voice_timing_recovery(plan, bundle, store, script: str) -> list[dict]:
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
        if (not isinstance(timing.get('cues'), list)
                or bind_voice_timing(script, asset, tuple(timing['cues']), timing.get('error'))['status'] != 'READY'):
            pending.append(record)
        elif timing.get('source') == 'local_asr' and _recognized_timing(record, need, asset, script) != timing:
            pending.append(record)
    return pending


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


def validate_voice_delivery(value: object) -> dict:
    if not isinstance(value, dict) or set(value) - set(DEFAULT_DELIVERY):
        raise ValueError("旁白执行要求仅支持 pace_ratio、pitch_semitones、tone")
    result = {**DEFAULT_DELIVERY, **value}
    pace, pitch, tone = result["pace_ratio"], result["pitch_semitones"], result["tone"]
    if type(pace) not in (int, float) or not math.isfinite(pace) or not 0.5 <= pace <= 2:
        raise ValueError("旁白语速倍率必须在 0.5 至 2 之间")
    if type(pitch) is not int or not -12 <= pitch <= 12:
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
