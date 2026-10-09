"""Domain projections over one captured native Hypit document."""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .errors import HypitIntegrationError
from .native_source import Document, Element, Reference, parse_file
from .narration import _frames


def document(value):
    return value if isinstance(value, Document) else parse_file(value)


def linked(reference, node, output=None):
    if not isinstance(reference, Reference) or node is None:
        return False
    identity = node.literal("id")
    return bool(identity) and reference.path == identity + ("." + output if output else "")


def target(doc, reference, kind=None):
    node = doc.target(reference, required=True)
    if kind is not None and doc.kind(node) != kind:
        raise HypitIntegrationError("原生引用未连接到预期组件")
    return node


def timeline(doc):
    value = doc.one("@hypit/timeline-author", "Timeline")
    clock = target(doc, value.ref("clock"), ("@hypit/timeline-author", "Clock"))
    if not linked(value.ref("clock"), clock):
        raise HypitIntegrationError("Timeline 必须引用实际 Clock")
    try:
        rate = Fraction(clock.literal("frame-rate", "0"))
        if rate <= 0:
            raise ValueError()
        duration = _frames(value.literal("end", ""), rate)
    except (ValueError, ZeroDivisionError) as exc:
        raise HypitIntegrationError("时间线缺少可核验的正帧率与整帧时长") from exc
    return value, clock, rate, duration


def film(doc):
    value = doc.one("@hypit/film", "Film")
    if not any(linked(row.ref("composition"), value, "composition")
               for row in doc.find("@hypit/render-hyperframes", "Video")):
        raise HypitIntegrationError("实际 Film 未关联到原生视频输出")
    return value


def reachable(doc, start):
    seen = set()
    def visit(node):
        if node in seen:
            return
        seen.add(node)
        for child in node:
            visit(child)
        for value in node.attributes.values():
            if isinstance(value, Reference):
                dependency = doc.target(value)
                if dependency is not None:
                    visit(dependency)
                else:
                    doc.recipe(value)  # A missing typed source is never guessed.
    visit(start)
    return seen


@dataclass(frozen=True)
class AudioPlacement:
    media: Element
    normalize: Element
    track: Element
    items: tuple
    film_refs: tuple
    duck: Element | None
    timeline: Element
    clock: Element
    fps: Fraction
    duration_frames: int


def audio_placement(doc, admitted_src, *, allow_trusted_duck=False, independent=True):
    media = [row for row in doc.find("@hypit/media", "Audio") if row.literal("src") == admitted_src]
    if len(media) != 1:
        raise HypitIntegrationError("音频素材需要唯一的原生声明")
    media = media[0]
    normalizers = [row for row in doc.find("@hypit/media-pipeline", "Normalize")
                   if linked(row.ref("source"), media)]
    if len(normalizers) != 1:
        raise HypitIntegrationError("音频需要唯一的原素材 Normalize")
    normalize = normalizers[0]
    placements = []
    for track in doc.find("@hypit/audio-track", "Track"):
        items = tuple(row for row in track if doc.kind(row) == ("@hypit/audio-track", "Item"))
        selected = tuple(row for row in items if linked(row.ref("source"), normalize, "media"))
        if selected:
            if independent and len(items) != len(selected):
                raise HypitIntegrationError("声音不能与其他素材共用独立音轨")
            placements.append((track, selected))
    if len(placements) != 1:
        raise HypitIntegrationError("音频需要唯一的独立 AudioTrack")
    track, items = placements[0]
    program, clock, fps, duration = timeline(doc)
    movie = film(doc)
    if not (linked(track.ref("timeline"), program, "timeline")
            and linked(movie.ref("timeline"), program, "timeline")
            and linked(normalize.ref("clock"), clock)):
        raise HypitIntegrationError("声音、Normalize、Film 与时间线 Clock 不一致")
    ducks = [row for row in doc.find("@easel/audio-mix", "Duck")
             if linked(row.ref("source"), track, "audio")]
    duck = None
    refs = []
    for row in movie:
        if doc.kind(row) != ("@hypit/film", "Track"):
            continue
        if linked(row.ref("source"), track, "audio"):
            refs.append(row)
        elif any(linked(row.ref("source"), candidate, "audio") for candidate in ducks):
            if not allow_trusted_duck or len(ducks) != 1:
                raise HypitIntegrationError("当前声音路径包含未经准入的配乐处理")
            duck = ducks[0]
            refs.append(row)
    if len(refs) != 1:
        raise HypitIntegrationError("音频需要唯一 Film 引用，不能缺失或叠加")
    def depends_on_media(node, seen=None):
        if node is None:
            return False
        if node is media:
            return True
        seen = set() if seen is None else seen
        if node in seen:
            return False
        seen.add(node)
        return any(depends_on_media(doc.target(reference), seen) for reference in node.references())
    for row in movie:
        if doc.kind(row) == ("@hypit/film", "Track") and row not in refs:
            if depends_on_media(doc.target(row.ref("source"))):
                raise HypitIntegrationError("同一音频还经过另一条处理链进入 Film，不能叠加或猜测声音身份")
    return AudioPlacement(media, normalize, track, items, tuple(refs), duck,
                          program, clock, fps, duration)


def audio_tracks_for_source(doc, admitted_src):
    """All actual independent tracks for one admitted source; no declaration-only evidence."""
    return {audio_placement(doc, admitted_src, allow_trusted_duck=True).track.literal("id")}
