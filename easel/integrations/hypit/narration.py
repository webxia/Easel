"""Lower measured sentence timing into the existing native Hypit author file.

Only narration placement and the reserved caption track are code-owned. The
Director still authors picture, caption Style/Frame and the narration start.
This does not invent word timing or another production representation.
"""
from __future__ import annotations

import html
import re
from fractions import Fraction

BEGIN = "<!-- Easel measured narration: begin -->"
END = "<!-- Easel measured narration: end -->"
_ATTR = re.compile(r'([\w-]+)\s*=\s*("[^"]*"|\'[^\']*\'|\{[\w.-]+\})')


def _attrs(tag: str) -> dict[str, str]:
    values = {}
    for match in _ATTR.finditer(tag):
        if match[1] in values:
            raise ValueError("原生编排属性重复，不能确定旁白时序")
        raw = match[2]
        values[match[1]] = raw if raw.startswith("{") else html.unescape(raw[1:-1])
    return values


def _one(pattern: str, source: str, label: str):
    matches = list(re.finditer(pattern, source, re.DOTALL))
    if len(matches) != 1:
        raise ValueError(f"句级时序需要唯一的{label}")
    return matches[0]


def _frames(value: str, fps: Fraction) -> int:
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)(ms|s|f)", value)
    if not match:
        raise ValueError("旁白位置和时长必须使用可核对的秒、毫秒或帧")
    count = Fraction(match[1]) * (fps / 1000 if match[2] == "ms" else fps if match[2] == "s" else 1)
    if count.denominator != 1:
        raise ValueError("旁白位置和 Timeline 长度必须落在当前帧时钟上")
    return int(count)


def compile_measured_narration(source: str, timings: dict, asset_sources: dict[str, str]) -> str:
    """Idempotently fill the reserved native track from verified input evidence."""
    available = []
    for row in timings.get("assets", []):
        src = asset_sources.get(row["asset_id"])
        if src is None or row.get("status") != "READY":
            continue
        matches = [m for m in re.finditer(r'<media:Audio\b[^>]*\/?>', source)
                   if _attrs(m[0]).get("src") == src]
        if len(matches) > 1:
            raise ValueError("同一旁白素材声明重复，不能确定实际播放身份")
        if matches:
            available.append((row, _attrs(matches[0][0])))
    if not available:
        return source  # Legacy/missing timing is not silently manufactured.
    if len(available) != 1:
        raise ValueError("当前句级编排只支持一条完整旁白，不能混用候选的时间")
    row, media = available[0]
    timeline_match = _one(r'<time:Timeline\b[^>]*\/?>', source, "Timeline")
    timeline = _attrs(timeline_match[0])
    clocks = [m for m in re.finditer(r'<time:Clock\b[^>]*\/?>', source)
              if "{" + _attrs(m[0]).get("id", "") + "}" == timeline.get("clock")]
    if len(clocks) != 1:
        raise ValueError("句级编排缺少 Timeline 对应的帧时钟")
    fps = Fraction(_attrs(clocks[0][0]).get("frame-rate", "0"))
    if fps <= 0:
        raise ValueError("旁白帧时钟无效")
    timeline_ref = "{" + timeline["id"] + ".timeline}"
    film = _one(r'<film:Film\b[^>]*>', source, "Film")
    if _attrs(film[0]).get("timeline") != timeline_ref:
        raise ValueError("成片与旁白时钟不一致")
    normalizers = [m for m in re.finditer(r'<pipeline:Normalize\b[^>]*\/?>', source)
                   if _attrs(m[0]).get("source") == "{" + media["id"] + "}"]
    if len(normalizers) != 1:
        raise ValueError("旁白需要唯一的原素材 Normalize，不能猜测额外处理后的时序")
    normalized = _attrs(normalizers[0][0])
    media_ref = "{" + normalized["id"] + ".media}"
    tracks = [m for m in re.finditer(r'<audio:Track\b[^>]*>.*?</audio:Track>', source, re.DOTALL)
              if any(_attrs(i[0]).get("source") == media_ref for i in re.finditer(r'<audio:Item\b[^>]*\/?>', m[0]))]
    if len(tracks) != 1:
        raise ValueError("旁白需要独立的原生 AudioTrack")
    track = tracks[0]
    track_attrs = _attrs(track[0].split(">", 1)[0])
    items = list(re.finditer(r'<audio:Item\b[^>]*\/?>', track[0]))
    if len(items) != 1 or track_attrs.get("timeline") != timeline_ref:
        raise ValueError("旁白不能与配乐共用音轨或重复播放")
    item = _attrs(items[0][0])
    if "during" in item and item["during"] != "program":
        raise ValueError("旁白需使用明确的起点，不能猜测语义窗口的偏移")
    offset = 0 if item.get("during") == "program" else _frames(item.get("at", "0s"), fps)
    if any(key in item for key in ("trim-start", "trim-end", "start", "end", "until", "min-rate", "max-rate")):
        raise ValueError("完整旁白不能被局部截取或重定时；请保留原音频后使用句级时序")
    if item.get("playback", "once") not in ("once", "once-start"):
        raise ValueError("完整旁白不能循环或拉伸播放")
    duration = Fraction(str(row["audio_duration_seconds"])) * fps
    duration_frames = -(-duration.numerator // duration.denominator)
    if duration_frames + offset > _frames(timeline.get("end", ""), fps):
        raise ValueError("Timeline 不足以容纳完整旁白；需调整镜头时长，不能截断声音")
    if not re.search(r'<film:Track\b[^>]*\bsource=\{' + re.escape(track_attrs["id"]) + r'\.audio\}', source):
        raise ValueError("旁白音轨未进入 Film")
    gain = item.get("gain", "1")
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", gain) or not 0 < Fraction(gain) <= 2:
        raise ValueError("旁白增益必须是可核对的正数，最大为 2")
    native_voice = (f'<audio:Track id="{track_attrs["id"]}" timeline={timeline_ref}>\n'
                    f'  <audio:Item source={media_ref} at="{offset}f" for="{duration_frames}f" '
                    f'playback="once" gain="{gain}" fade-in="0f" fade-out="0f"/>\n</audio:Track>')
    source = source[:track.start()] + native_voice + source[track.end():]
    normalized_tag = (f'<pipeline:Normalize id="{normalized["id"]}" source={{{media["id"]}}} '
                      f'video="none" audio="default" span-authority="audio" clock={timeline["clock"]}/>')
    source = source.replace(normalizers[0][0], normalized_tag, 1)
    for tag, identity in (("typo:Style", "easel-caption-style"), ("space:Frame", "easel-caption-frame")):
        if sum(_attrs(m[0]).get("id") == identity for m in re.finditer("<" + tag + r'\b[^>]*\/?>', source)) != 1:
            raise ValueError(f"请先创作字幕样式和安全区：缺少 {identity}")
    definitions, areas = [], []
    last_end = 0
    for i, cue in enumerate(row["cues"]):
        start = round(Fraction(str(cue["start_seconds"])) * fps) + offset
        end = round(Fraction(str(cue["end_seconds"])) * fps) + offset
        if start < last_end or end <= start or end > offset + duration_frames:
            raise ValueError("句级字幕在当前帧时钟上无法完整、不重叠地表达")
        last_end = end
        # Reuse the frozen source text verbatim. Provider-normalized spelling
        # and punctuation are timing evidence, not editorial permission.
        text = html.escape(cue["display_text"], quote=False)
        definitions.append(f'<copy:Value id="easel-cue-{i}">{text}</copy:Value>')
        areas.append(f'  <typo:Area id="easel-caption-{i}" content={{easel-cue-{i}}} '
                     f'placement={{easel-caption-frame}} style={{easel-caption-style}} at="{start}f" for="{end-start}f"/>')
    block = (BEGIN + "\n" + "\n".join(definitions)
             + f'\n<typo:Track id="easel-captions" timeline={timeline_ref}>\n'
             + "\n".join(areas) + "\n</typo:Track>\n" + END)
    if BEGIN in source or END in source:
        existing = _one(re.escape(BEGIN) + r'.*?' + re.escape(END), source, "自动字幕区域")
    else:
        existing = _one(r'<typo:Track\b(?=[^>]*\bid="easel-captions")[^>]*(?:/>|>.*?</typo:Track>)',
                        source, "easel-captions 字幕轨")
    source = source[:existing.start()] + block + source[existing.end():]
    film_ref = '<film:Track source={easel-captions.track}/>'
    refs = re.findall(r'<film:Track\b[^>]*\bsource=\{easel-captions\.track\}[^>]*/>', source)
    if not refs:
        film = _one(r'<film:Film\b[^>]*>', source, "Film")
        source = source[:film.end()] + "\n  " + film_ref + source[film.end():]
    elif len(refs) > 1:
        raise ValueError("字幕轨重复进入 Film")
    return source
