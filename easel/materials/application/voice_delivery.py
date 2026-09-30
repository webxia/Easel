"""Supported, provider-neutral delivery controls on existing Voice Needs."""
from __future__ import annotations

import math
import hashlib
import unicodedata

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

    def spoken(text):
        return "".join(c for c in text if not c.isspace() and not unicodedata.category(c).startswith("P"))

    last_time, last_character = 0.0, 0
    try:
        for cue in cues:
            start, end = cue["start_seconds"], cue["end_seconds"]
            begin, finish = cue["start_character"], cue["end_character"]
            if (any(type(t) not in (int, float) or not math.isfinite(t) for t in (start, end))
                    or not last_time <= start < end <= asset.technical.duration_seconds + 0.1
                    or type(begin) is not int or type(finish) is not int
                    or not last_character <= begin < finish <= len(script)
                    or spoken(script[last_character:begin])
                    or not isinstance(cue["text"], str) or not spoken(cue["text"])
                    or spoken(cue["text"]) != spoken(script[begin:finish])):
                raise ValueError("alignment does not cover frozen speech")
            last_time, last_character = end, finish
        if spoken(script[last_character:]):
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
                    rows.append({"need_id": need.need_id, **current})
                    found = True
                    break
        if not found:
            unavailable.append(need.need_id)
    return {"schema": "easel-production-voice-timing@1", "assets": rows, "unavailable_need_ids": unavailable}
