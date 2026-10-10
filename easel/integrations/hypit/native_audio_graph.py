"""Code-owned narration and music derivation using captured native source ranges."""
from __future__ import annotations

import html
import json
import re
from fractions import Fraction
from pathlib import Path

from .errors import HypitIntegrationError
from .native_source import Element, Text, parse_text
from .native_graph import audio_placement, document, linked
from .narration import BEGIN as VOICE_BEGIN, END as VOICE_END, _frames
from .music import BEGIN as MUSIC_BEGIN, END as MUSIC_END, music_envelope


def _range(text, start, end):
    return {"start": len(text[:start].encode("utf-16-le")) // 2,
            "end": len(text[:end].encode("utf-16-le")) // 2}


def _region(doc, begin, end, allowed):
    text = doc.source.text
    if begin not in text and end not in text:
        return None
    if text.count(begin) != 1 or text.count(end) != 1:
        raise HypitIntegrationError("程序编排区域必须有唯一、完整的开始和结束标记")
    start, finish = text.index(begin), text.index(end) + len(end)
    if finish <= start + len(begin):
        raise HypitIntegrationError("程序编排区域顺序错误")
    native = _range(text, start, finish)
    span = doc.source.span(native)
    for node in doc.elements:
        position = doc.source.span(node.range)
        overlaps = position["start"] < span["end"] and span["start"] < position["end"]
        if overlaps and (position["start"] < span["start"] or position["end"] > span["end"] or not allowed(node)):
            raise HypitIntegrationError("程序编排区域包含非本次派生拥有的元素，拒绝覆盖")
    return native


def _reparse(doc, source):
    return parse_text(source, doc.workspace / doc.source.name, workspace=doc.workspace,
                      identity=doc.identity, require_support=False)


def _attributes(node, allowed, label):
    if set(node.attributes) - allowed:
        raise HypitIntegrationError(label + "包含未支持的变换，不能静默删除")
    if any(isinstance(child, Element) or isinstance(child, Text) and child.value.strip() for child in node.children):
        raise HypitIntegrationError(label + "包含未支持的嵌套处理")


def compile_measured_narration(value, timings, asset_sources):
    doc = document(value)
    available = []
    for row in timings.get("assets", []):
        src = asset_sources.get(row["asset_id"])
        if src is None or row.get("status") != "READY":
            continue
        declarations = [node for node in doc.find("@hypit/media", "Audio") if node.literal("src") == src]
        if len(declarations) > 1:
            raise HypitIntegrationError("同一旁白素材声明重复")
        if declarations:
            available.append((row, src))
    if not available:
        return doc.source.text
    if len(available) != 1:
        raise HypitIntegrationError("当前句级编排只支持一条完整旁白")
    row, src = available[0]
    placement = audio_placement(doc, src)
    if len(placement.items) != 1:
        raise HypitIntegrationError("旁白不能重复播放")
    item = placement.items[0]
    if set(placement.track.attributes) - {"id", "timeline"}:
        raise HypitIntegrationError("旁白轨包含未支持的变换")
    _attributes(placement.normalize, {"id", "source", "video", "audio", "span-authority", "clock"}, "旁白 Normalize")
    _attributes(item, {"id", "source", "during", "at", "for", "playback", "gain", "fade-in", "fade-out"}, "完整旁白")
    if "during" in item.attributes and item.literal("during") != "program":
        raise HypitIntegrationError("旁白需使用明确的起点，不能猜测语义窗口")
    if "during" in item.attributes and any(key in item.attributes for key in ("at", "for")):
        raise HypitIntegrationError("旁白不能同时使用 during 与 at/for")
    offset = 0 if item.literal("during") == "program" else _frames(item.literal("at", "0s"), placement.fps)
    if item.literal("playback", "once") not in {"once", "once-start"}:
        raise HypitIntegrationError("完整旁白不能循环或拉伸播放")
    duration = Fraction(str(row["audio_duration_seconds"])) * placement.fps
    duration_frames = -(-duration.numerator // duration.denominator)
    if duration_frames + offset > placement.duration_frames:
        raise HypitIntegrationError("Timeline 不足以容纳完整旁白，不能截断声音")
    gain = item.literal("gain", "1")
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", gain) or not 0 < Fraction(gain) <= 2:
        raise HypitIntegrationError("旁白增益必须是可核对的正数，最大为 2")
    for identity, kind in (("easel-caption-style", ("@hypit/typography-track", "Style")),
                           ("easel-caption-frame", ("@hypit/spatial", "Frame"))):
        node = doc.nodes.get(identity)
        if node is None or doc.kind(node) != kind:
            raise HypitIntegrationError("请先创作字幕样式和安全区：" + identity)
    caption = doc.nodes.get("easel-captions")
    if caption is None or doc.kind(caption) != ("@hypit/typography-track", "Track"):
        raise HypitIntegrationError("缺少程序字幕预留 Track")
    program = placement.timeline.literal("id") + ".timeline"
    if set(caption.attributes) != {"id", "timeline"} or not linked(caption.ref("timeline"), placement.timeline, "timeline"):
        raise HypitIntegrationError("程序字幕 Track 包含未授权的属性或时间线")
    for child in caption.children:
        if isinstance(child, Text):
            if child.value.strip():
                raise HypitIntegrationError("程序字幕区域含非程序文本")
            continue
        identity = child.literal("id", "")
        match = re.fullmatch(r"easel-caption-([0-9]+)", identity)
        if (doc.kind(child) != ("@hypit/typography-track", "Area") or not match
                or set(child.attributes) != {"id", "content", "placement", "style", "at", "for"}
                or child.ref("content") is None or child.ref("content").path != "easel-cue-" + match[1]
                or child.ref("placement") is None or child.ref("placement").path != "easel-caption-frame"
                or child.ref("style") is None or child.ref("style").path != "easel-caption-style"
                or any(isinstance(part, Element) or isinstance(part, Text) and part.value.strip() for part in child.children)):
            raise HypitIntegrationError("程序字幕区域含非本次派生拥有的子元素")
        cue = doc.nodes.get("easel-cue-" + match[1])
        if cue is None or doc.kind(cue) != ("@hypit/text", "Value"):
            raise HypitIntegrationError("程序字幕区域的冻结原文引用不完整")
    track_name = placement.track.name
    item_name = doc.nested_name(placement.track, "Item")
    item_id = ' id="' + html.escape(item.literal("id"), quote=True) + '"' if item.literal("id") else ""
    voice = (f'<{track_name} id="{placement.track.literal("id")}" timeline={{{program}}}>\n'
             f'  <{item_name}{item_id} source={{{placement.normalize.literal("id")}.media}} '
             f'at="{offset}f" for="{duration_frames}f" playback="once" gain="{gain}" fade-in="0f" fade-out="0f"/>\n'
             f'</{track_name}>')
    normalizer = (f'<{placement.normalize.name} id="{placement.normalize.literal("id")}" '
                  f'source={{{placement.media.literal("id")}}} video="none" audio="default" '
                  f'span-authority="audio" clock={{{placement.clock.literal("id")}}}/>')
    copy_name = doc.name_for("@hypit/text", "Value")
    area_name = doc.nested_name(caption, "Area")
    definitions, areas, last_end = [], [], 0
    for index, cue in enumerate(row["cues"]):
        start = round(Fraction(str(cue["start_seconds"])) * placement.fps) + offset
        end = round(Fraction(str(cue["end_seconds"])) * placement.fps) + offset
        if start < last_end or end <= start or end > offset + duration_frames:
            raise HypitIntegrationError("句级字幕在当前帧时钟上无法完整、不重叠地表达")
        last_end = end
        definitions.append(f'<{copy_name} id="easel-cue-{index}">{html.escape(cue["display_text"], quote=False)}</{copy_name}>')
        areas.append(f'  <{area_name} id="easel-caption-{index}" content={{easel-cue-{index}}} '
                     f'placement={{easel-caption-frame}} style={{easel-caption-style}} at="{start}f" for="{end-start}f"/>')
    block = (VOICE_BEGIN + "\n" + "\n".join(definitions)
             + f'\n<{caption.name} id="easel-captions" timeline={{{program}}}>\n'
             + "\n".join(areas) + f"\n</{caption.name}>\n" + VOICE_END)
    region = _region(doc, VOICE_BEGIN, VOICE_END, lambda node:
        (doc.kind(node) == ("@hypit/text", "Value") and re.fullmatch(r"easel-cue-[0-9]+", node.literal("id", "")))
        or node is caption)
    changes = [(placement.track.range, voice), (placement.normalize.range, normalizer),
               (region or caption.range, block)]
    movie = doc.one("@hypit/film", "Film")
    references = [node for node in movie if doc.kind(node) == ("@hypit/film", "Track")
                  and linked(node.ref("source"), caption, "track")]
    if len(references) > 1:
        raise HypitIntegrationError("字幕轨重复进入 Film")
    if not references:
        if movie.self_closing:
            raise HypitIntegrationError("Film 缺少可用的结构化音轨容器")
        end = movie.opening_range["end"]
        changes.append(({"start": end, "end": end},
                        f'\n  <{doc.nested_name(movie, "Track")} source={{easel-captions.track}}/>'))
    source = doc.replaced(changes)
    # The input Document is already parsed under the installed parser identity.
    # Rechecking unchanged bytes is redundant on idempotent/cold validation,
    # but every actual generated change must still pass the native parser.
    if source != doc.source.text:
        _reparse(doc, source)
    return source


def compile_music_ducking(value, timings, sources, bgm_ids, policy):
    doc = document(value)
    if not policy or not bgm_ids:
        return doc.source.text
    audio_sources = {node.literal("src") for node in doc.find("@hypit/media", "Audio")}
    selected = [identity for identity in sorted(bgm_ids) if sources.get(identity) in audio_sources]
    if not selected:
        return doc.source.text
    voices = [row for row in timings.get("assets", [])
              if row.get("status") == "READY" and sources.get(row["asset_id"]) in audio_sources]
    if len(voices) != 1:
        raise HypitIntegrationError("配乐压低需要当前旁白的可信句级时序")
    voice = audio_placement(doc, sources[voices[0]["asset_id"]])
    if len(voice.items) != 1:
        raise HypitIntegrationError("配乐压低不能确定旁白的实际位置")
    item = voice.items[0]
    offset = 0 if item.literal("during") == "program" else float(_frames(item.literal("at", "0f"), voice.fps) / voice.fps)
    points = music_envelope(voices[0]["cues"], offset, float(voice.duration_frames / voice.fps), policy)
    encoded = html.escape(json.dumps(points, separators=(",", ":")), quote=True)
    imports = [entry for entry in doc.imports if entry["kind"] == "module" and entry["from"] == "@easel/audio-mix@1"]
    if imports:
        duck_name = doc.name_for("@easel/audio-mix", "Duck")
    else:
        if "easelmix" in doc.aliases or "easelmix:Duck" in doc.scope:
            raise HypitIntegrationError("程序配乐 import 的保留别名冲突")
        duck_name = "easelmix:Duck"
    placements = {}
    for identity in selected:
        placement = audio_placement(doc, sources[identity], allow_trusted_duck=True)
        placements[placement.track.literal("id")] = placement
    declarations, changes, allowed_ids = [], [], set()
    for track_id, placement in sorted(placements.items()):
        duck_id = "easel-duck-" + track_id
        old = doc.nodes.get(duck_id)
        if old is not None and (doc.kind(old) != ("@easel/audio-mix", "Duck")
                                or not linked(old.ref("source"), placement.track, "audio")):
            raise HypitIntegrationError("程序配乐组件保留标识被其他内容占用")
        if placement.duck is not None and placement.duck is not old:
            raise HypitIntegrationError("配乐包含非程序拥有的 Duck，不能重新解释")
        allowed_ids.add(duck_id)
        declarations.append(f'<{duck_name} id="{duck_id}" source={{{track_id}.audio}} points="{encoded}"/>')
        ref = placement.film_refs[0]
        changes.append((ref.attribute_ranges["source"], "{" + duck_id + ".audio}"))
    block = MUSIC_BEGIN + "\n" + "\n".join(declarations) + "\n" + MUSIC_END
    region = _region(doc, MUSIC_BEGIN, MUSIC_END,
                     lambda node: doc.kind(node) == ("@easel/audio-mix", "Duck") and node.literal("id") in allowed_ids)
    movie = doc.one("@hypit/film", "Film")
    if region is not None:
        changes.append((region, block))
    else:
        if any(identity in doc.nodes for identity in allowed_ids):
            raise HypitIntegrationError("程序配乐组件缺少完整来源区域")
        start = movie.range["start"]
        changes.append(({"start": start, "end": start}, block + "\n"))
    if not imports:
        end = doc.imports[-1]["range"]["end"]
        changes.append(({"start": end, "end": end}, '\n<import as="easelmix" from="@easel/audio-mix@1"/>'))
    source = doc.replaced(changes)
    # The input Document is already parsed under the installed parser identity.
    # Rechecking unchanged bytes is redundant on idempotent/cold validation,
    # but every actual generated change must still pass the native parser.
    if source != doc.source.text:
        _reparse(doc, source)
    return source
