"""Revision and evidence rules evaluated over Hypit's captured typed AST."""
from __future__ import annotations

import json
import math
import re
from fractions import Fraction

from .errors import HypitIntegrationError
from .native_source import Element, Reference, Text
from .native_graph import document, film, linked, reachable, target, timeline
from .narration import _frames


def _value(value):
    return ("reference", value.path) if isinstance(value, Reference) else ("literal", value)


def _canonical(doc, node, filtered=None):
    attrs, children = filtered(node) if filtered else (node.attributes, node.children)
    return (doc.kind(node), tuple(sorted((key, _value(value)) for key, value in attrs.items())),
            tuple(("text", child.value) if isinstance(child, Text) else _canonical(doc, child, filtered)
                  for child in children))


def _collect(doc, seeds, filtered=None):
    protected, visited = {}, set()
    def visit(node):
        if node in visited:
            return
        visited.add(node)
        key = node.literal("id") or "anonymous:" + str(list(doc.iter()).index(node))
        protected[key] = _canonical(doc, node, filtered)
        def references(element):
            attrs, children = filtered(element) if filtered else (element.attributes, element.children)
            for value in attrs.values():
                if not isinstance(value, Reference):
                    continue
                dependency = doc.target(value)
                if dependency is not None:
                    visit(dependency)
                else:
                    properties = doc.recipe(value)
                    protected["recipe:" + value.path] = json.dumps(
                        properties, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
            for child in children:
                if isinstance(child, Element):
                    references(child)
        references(node)
    for seed in seeds:
        visit(seed)
    return protected, visited


def _protected_graph(value):
    doc = document(value)
    seeds = [node for node in doc.elements if node.module in {
        "@hypit/audio-track", "@hypit/text", "@hypit/typography-track", "@easel/audio-mix"}]
    return _collect(doc, seeds)[0]


def assert_composition_preserves_sound_and_copy(base, authored):
    assert_quality_revision(base, authored, {"visual"})


def _quality_protected_dependencies(value):
    doc = document(value)
    seeds = [node for node in doc.elements if node.module in {
        "@hypit/audio-track", "@hypit/text", "@hypit/typography-track", "@easel/audio-mix"}]
    seeds += [node for node in doc.iter() if node.module == "@hypit/media-track"
              and ("source-audio" in node.attributes or node.local_name == "Sound")]
    return _collect(doc, seeds)[1]


def quality_protected_sources(base):
    doc = document(base)
    return {node.literal("src") for node in _quality_protected_dependencies(doc)
            if "src" in node.attributes}


def _sound_sensitive(doc):
    """Recipes that also determine source sound cannot be visual-only edits."""
    sensitive = set()
    for node in doc.iter():
        if node.module != "@hypit/media-track" or not (
                "source-audio" in node.attributes or node.local_name == "Sound"):
            continue
        anchor = node if "source-audio" in node.attributes else doc.parents[node]
        if "source-audio" in node.attributes:
            sensitive.update(node.iter())
        while anchor.module == "@hypit/media-track":
            sensitive.add(anchor)
            sensitive.update(child for child in anchor.iter() if child.local_name == "Handoff")
            if anchor not in doc.parents:
                break
            anchor = doc.parents[anchor]
    return sensitive


def _visual_roots(doc):
    movie = film(doc)
    roots = set()
    for row in movie:
        if doc.kind(row) != ("@hypit/film", "Track"):
            continue
        node = doc.target(row.ref("source"), required=True)
        if ((doc.kind(node) == ("@hypit/media-track", "Track") and linked(row.ref("source"), node, "visual"))
                or (doc.kind(node) == ("@hypit/typography-track", "Track") and linked(row.ref("source"), node, "track"))):
            roots.add(node)
    return roots


def _effective_appearance(doc, sample):
    owner = sample
    while "appearance" not in owner.attributes and owner in doc.parents:
        owner = doc.parents[owner]
    return owner.ref("appearance")


def _managed_caption(doc, node):
    if doc.kind(node) != ("@hypit/typography-track", "Area"):
        return False
    parent = doc.parents.get(node)
    identity = node.literal("id", "")
    suffix = identity.removeprefix("easel-caption-")
    if (parent is None or doc.kind(parent) != ("@hypit/typography-track", "Track")
            or parent.literal("id") != "easel-captions"
            or not identity.startswith("easel-caption-") or not suffix.isdigit()):
        return False
    content = doc.target(node.ref("content"))
    return (content is not None and doc.kind(content) == ("@hypit/text", "Value")
            and linked(node.ref("content"), content) and content.literal("id") == "easel-cue-" + suffix)


def assert_quality_revision(base, authored, allowed, *, replacements=None):
    if not allowed or not allowed <= {"visual", "visual_material", "captions", "audio"}:
        raise HypitIntegrationError("系统质量修正范围无效")
    if "visual_material" in allowed and "visual" not in allowed:
        raise HypitIntegrationError("系统视觉素材修正需要对应画面缺陷")
    base, authored = document(base), document(authored)
    if expression_uses(base) != expression_uses(authored):
        raise HypitIntegrationError("系统质量修正改变了未授权部分：必要表达承担项或时间窗")
    sound_copy_ids = {node.literal("id") for node in _quality_protected_dependencies(base)}

    def graph(doc):
        sound_sensitive = _sound_sensitive(doc)
        changed, extents = {}, {}
        if "visual_material" in allowed:
            for identity, node in doc.nodes.items():
                old = base.nodes.get(identity)
                if (old is None or identity in sound_copy_ids or doc.kind(node) != base.kind(old)
                        or doc.kind(node) not in {("@hypit/media", "Image"), ("@hypit/media", "Video")}
                        or old.literal("src") == node.literal("src")):
                    continue
                candidate = (replacements or {}).get(old.literal("src"), {}).get(node.literal("src"))
                if candidate and candidate.get("media_type") == node.local_name.lower():
                    changed[identity] = candidate
            for identity, node in doc.nodes.items():
                if doc.kind(node) != ("@hypit/spatial", "Extent") or identity in sound_copy_ids:
                    continue
                old = base.nodes.get(identity)
                users = [item for item in base.iter() if linked(item.ref("extent"), old)]
                kinds = {("@hypit/media-track", name) for name in ("Item", "Member", "Layer")}
                images = {base.target(item.ref("image")) for item in users if base.kind(item) in kinds}
                image_ids = {image.literal("id") for image in images if image is not None}
                if (old is None or not users or any(base.kind(item) not in kinds for item in users)
                        or None in images or not image_ids <= changed.keys()):
                    continue
                if all(node.literal("width") == str(changed[key]["width"])
                       and node.literal("height") == str(changed[key]["height"]) for key in image_ids):
                    extents[identity] = old

        def filtered(node):
            package, name = doc.kind(node)
            omitted = set()
            if "audio" in allowed and (package, name) == ("@hypit/audio-track", "Item"):
                omitted = {"gain", "fade-in", "fade-out"}
            if "captions" in allowed and _managed_caption(doc, node):
                omitted = {"placement", "style"}
            if "visual" in allowed and package == "@hypit/media-track":
                omitted = {"frame"} if node in sound_sensitive else {"frame", "appearance", "transition"}
            if "visual" in allowed and (package, name) == ("@hypit/film", "Film"):
                omitted = {"appearance"}
            children = tuple(child for child in node.children if not (
                isinstance(child, Element) and "visual" in allowed
                and node not in sound_sensitive and doc.kind(child) == ("@hypit/media-track", "Sampling")))
            attrs = {key: value for key, value in node.attributes.items() if key not in omitted}
            identity = node.literal("id")
            if identity in changed:
                attrs["src"] = base.nodes[identity].literal("src")
            if identity in extents:
                for dimension in ("width", "height"):
                    attrs[dimension] = extents[identity].literal(dimension)
            return attrs, children

        roots = {"@hypit/media", "@hypit/media-pipeline", "@hypit/timeline-author", "@hypit/text",
                 "@hypit/audio-track", "@hypit/media-track", "@hypit/film",
                 "@hypit/render-hyperframes", "@easel/audio-mix"}
        seeds = [node for node in doc.elements if node.module in roots or doc.kind(node) in {
            ("@hypit/spatial", "Canvas"), ("@hypit/typography-track", "Track")}]
        result = _collect(doc, seeds, filtered)[0]
        result["imports"] = tuple((row["kind"], row["from"], row.get("alias")) for row in doc.imports)
        return result
    if graph(base) != graph(authored):
        raise HypitIntegrationError("系统局部修正改变了脚本、素材身份、播放时序或未授权部分")


def _rate(doc, normalized):
    clock = target(doc, normalized.ref("clock"), ("@hypit/timeline-author", "Clock"))
    if not linked(normalized.ref("clock"), clock):
        raise HypitIntegrationError("取片范围必须引用实际 Normalize Clock")
    try:
        rate = Fraction(clock.literal("frame-rate", "0"))
        if rate <= 0:
            raise ValueError()
        return rate
    except (ValueError, ZeroDivisionError) as exc:
        raise HypitIntegrationError("取片帧率无效") from exc


def _trim(properties, total, *, paired=False):
    if paired and any(key not in properties for key in ("trim-start", "trim-end")):
        raise HypitIntegrationError("画面截取起止必须成对使用整数帧")
    start, end = properties.get("trim-start", 0), properties.get("trim-end", total)
    if type(start) is not int or type(end) is not int:
        raise HypitIntegrationError("取片起止必须使用当前 Clock 下的整数帧，不能用字符串或布尔值代替")
    return start, end


def assert_observed_video_uses(authored, assets):
    bounded = {row["src"]: row for row in assets if row.get("observed_video_uses")}
    if not bounded:
        return
    doc = document(authored)
    movie = film(doc)
    film_tracks = _visual_roots(doc)

    def uses_bounded_source(node, seen=None):
        if node is None:
            return False
        seen = set() if seen is None else seen
        if node in seen:
            return False
        seen.add(node)
        return node.literal("src") in bounded or any(
            uses_bounded_source(doc.target(ref), seen) for ref in node.references())

    for track in film_tracks:
        if track.module not in {"@hypit/media-track", "@hypit/audio-track", "@easel/audio-mix"} and uses_bounded_source(track):
            raise HypitIntegrationError("已观察视频区间需通过已核对的原生 media-track 使用")
    covered = set()
    for sample in doc.iter():
        if doc.kind(sample) not in {("@hypit/media-track", key) for key in ("Item", "Member", "Layer")}:
            continue
        item = sample
        while doc.kind(item) == ("@hypit/media-track", "Layer"):
            item = doc.parents[item]
        track = item
        while track in doc.parents and doc.kind(track) != ("@hypit/media-track", "Track"):
            track = doc.parents[track]
        if track not in film_tracks:
            continue
        if any(uses_bounded_source(doc.target(sample.ref(key))) for key in ("image", "surface")):
            raise HypitIntegrationError("观察区间的视频不能通过未核对的静帧或 Surface 变换绕过取片检查")
        normalized = doc.target(sample.ref("media"))
        if normalized is None or doc.kind(normalized) != ("@hypit/media-pipeline", "Normalize"):
            if uses_bounded_source(normalized):
                raise HypitIntegrationError("观察区间不能经过未核对的中间变换")
            continue
        if not linked(sample.ref("media"), normalized, "media"):
            raise HypitIntegrationError("观察区间必须使用 Normalize.media 输出")
        media = doc.target(normalized.ref("source"))
        if media is None or media.literal("src") not in bounded:
            if uses_bounded_source(media):
                raise HypitIntegrationError("观察区间必须直接使用原素材 Normalize")
            continue
        if not linked(normalized.ref("source"), media):
            raise HypitIntegrationError("观察区间 Normalize 必须连接原素材")
        asset = bounded[media.literal("src")]
        uses = [row for row in asset["observed_video_uses"]
                if item.literal("id", "").startswith(row["element_id_prefix"])]
        if len(uses) != 1:
            raise HypitIntegrationError("视频镜头必须使用提供的唯一场景标识前缀")
        rate = _rate(doc, normalized)
        owner = sample
        while "appearance" not in owner.attributes and owner in doc.parents:
            owner = doc.parents[owner]
        properties = doc.recipe(owner.ref("appearance"))
        duration = Fraction(str(asset["source_duration_seconds"]))
        total = math.floor(duration * rate + Fraction(1, 2))
        start, end = _trim(properties, total)
        left, right = (Fraction(str(value)) for value in uses[0]["source_interval_seconds"])
        first, limit = math.ceil(left * rate), total if right == duration else math.floor(right * rate)
        if not first <= start < end <= limit:
            raise HypitIntegrationError(
                f"实际取片越过已观察区间：场景 {uses[0]['need_id']}，镜头 {item.literal('id')}；"
                f"允许整数帧 {first} <= trim-start < trim-end <= {limit}，实际 {start} / {end}")
        covered.add(uses[0]["need_id"])
    required = {use["need_id"] for asset in bounded.values() for use in asset["observed_video_uses"] if use["required"]}
    if required - covered:
        raise HypitIntegrationError("必要视频场景尚未使用其已观察区间")


def assert_video_trim_ranges(authored, assets):
    doc = document(authored)
    for item in doc.iter():
        if doc.kind(item) not in {("@hypit/media-track", key) for key in ("Item", "Member", "Layer")}:
            continue
        appearance = _effective_appearance(doc, item)
        if appearance is None:
            continue
        properties = doc.recipe(appearance)
        if not any(key in properties for key in ("trim-start", "trim-end")):
            continue
        if item.ref("media") is None and any(child.local_name == "Layer" for child in item):
            continue  # Each actual Layer validates its own inherited recipe.
        normalized = target(doc, item.ref("media"), ("@hypit/media-pipeline", "Normalize"))
        if not linked(item.ref("media"), normalized, "media"):
            raise HypitIntegrationError("画面截取必须使用 Normalize.media 输出")
        video = target(doc, normalized.ref("source"), ("@hypit/media", "Video"))
        if not linked(normalized.ref("source"), video) or video.literal("src") not in assets:
            raise HypitIntegrationError("画面截取缺少已检查的原片时长")
        duration = Fraction(str(assets[video.literal("src")]))
        rate = _rate(doc, normalized)
        total = math.floor(duration * rate + Fraction(1, 2))
        start, end = _trim(properties, total, paired=True)
        if not 0 <= start < end <= total:
            raise HypitIntegrationError(f"画面截取 {start}～{end} 帧超出原片范围，Normalize 为 {rate} fps、{total} 帧")


def _expression_rows(doc):
    # Easel owns this comment contract. Only comments outside complete body
    # elements can carry it; an attribute or text literal cannot forge metadata.
    blocked = [doc.source.span(node.range) for node in doc.elements]
    rows = []
    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate property")
            result[key] = value
        return result
    for match in re.finditer(r"<!-- Easel expression: (.*?) -->", doc.source.text):
        offset = len(doc.source.text[:match.start()].encode("utf-8"))
        if any(span["start"] <= offset < span["end"] for span in blocked):
            continue
        try:
            row = json.loads(match[1], object_pairs_hook=object_pairs,
                             parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
        except ValueError as exc:
            raise HypitIntegrationError("必要表达编排记录不是有效的唯一键 JSON") from exc
        if (not isinstance(row, dict) or set(row) != {"need_id", "element_ids", "at_seconds", "end_seconds", "responsibility"}
                or not isinstance(row["need_id"], str) or not row["need_id"]
                or not isinstance(row["element_ids"], list) or not row["element_ids"]
                or any(not isinstance(value, str) or not value for value in row["element_ids"])
                or len(set(row["element_ids"])) != len(row["element_ids"])
                or row["responsibility"] not in {"material", "graphic", "combined"}
                or any(type(row[key]) not in (int, float) or not math.isfinite(row[key]) for key in ("at_seconds", "end_seconds"))
                or not 0 <= row["at_seconds"] < row["end_seconds"]):
            raise HypitIntegrationError("必要表达须明确 Need、实际元素、承担方式和有效时间窗")
        rows.append(row)
    return rows


def expression_uses(source, *, required_need_ids=None):
    doc = document(source)
    rows = _expression_rows(doc)
    if not rows and required_need_ids is None:
        return []
    if len({row["need_id"] for row in rows}) != len(rows):
        raise HypitIntegrationError("必要表达记录存在重复 Need")
    if required_need_ids is not None and {row["need_id"] for row in rows} != required_need_ids:
        raise HypitIntegrationError("必要表达编排未完整覆盖当前 required 视觉 Need")
    movie = film(doc)
    seen = {node for root in _visual_roots(doc) for node in root.iter()}
    program, _, fps, frames = timeline(doc)
    if not linked(movie.ref("timeline"), program, "timeline"):
        raise HypitIntegrationError("必要表达时间线与实际 Film 不一致")
    duration = float(frames / fps)
    for row in rows:
        if row["end_seconds"] > duration:
            raise HypitIntegrationError("必要表达时间窗越过实际 Timeline")
        nodes = [doc.nodes.get(identity) for identity in row["element_ids"]]
        if any(node is None or node not in seen for node in nodes):
            raise HypitIntegrationError(f"必要表达 {row['need_id']} 引用的元素未进入 Film")
        kinds = {("@hypit/media-track", "Item"), ("@hypit/media-track", "Member"), ("@hypit/typography-track", "Area")}
        if any(doc.kind(node) not in kinds for node in nodes):
            raise HypitIntegrationError("必要表达应绑定实际画面 Item/Member 或文字 Area")
        for node in nodes:
            if node.literal("during") == "program":
                left, right = 0., duration
            else:
                left = float(_frames(node.literal("at", "0f"), fps) / fps)
                if node.literal("for"):
                    right = left + float(_frames(node.literal("for"), fps) / fps)
                elif doc.kind(node) == ("@hypit/media-track", "Member"):
                    parent = doc.parents[node]
                    siblings = list(parent)
                    after = siblings[siblings.index(node) + 1:]
                    following = next((value for value in after if doc.kind(value) == ("@hypit/media-track", "Member")), None)
                    end = following.literal("at") if following is not None else parent.literal("until")
                    if end is None:
                        raise HypitIntegrationError("必要表达 Member 缺少可核对的结束窗")
                    right = float(_frames(end, fps) / fps)
                else:
                    raise HypitIntegrationError("必要表达元素需要明确 at/for 或 Member 窗口")
            if row["at_seconds"] < left - 1e-6 or row["end_seconds"] > right + 1e-6:
                raise HypitIntegrationError("必要表达记录与实际图层播放窗口不一致")
        if row["responsibility"] in {"graphic", "combined"} and not any(
                doc.kind(node) == ("@hypit/typography-track", "Area")
                and not node.literal("id", "").startswith("easel-caption-") for node in nodes):
            raise HypitIntegrationError("文字/图形表达需要实际独立文字 Area，普通旁白字幕不能代替")
    return rows
