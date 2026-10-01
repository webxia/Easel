"""Protect accepted sound and copy during composition-only authoring."""

from __future__ import annotations

import re
import math
import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path

from easel.integrations.hypit.errors import HypitIntegrationError


def _markup(source: Path):
    text = source.read_text(encoding="utf-8")
    # SVML uses typed, unquoted references and package-qualified element names.
    text = re.sub(r'=\{([^}]+)\}', lambda m: '="{' + m[1] + '}"', text)
    text = re.sub(r'(<\/?)([\w.-]+):([\w.-]+)', r'\1\2__\3', text)
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise HypitIntegrationError("局部修改产物无法读取；未改变已保留的成片") from exc
    return root


def _protected_graph(source: Path) -> tuple:
    root = _markup(source)
    packages = {e.get("as"): e.get("from", "").split("@")[1]
                for e in root.findall("import") if e.get("from", "").startswith("@hypit/")}
    nodes = {e.get("id"): e for e in root.iter() if e.get("id")}

    def kind(e):
        prefix, _, name = e.tag.partition("__")
        return packages.get(prefix, prefix), name

    def canonical(e):
        return (kind(e), tuple(sorted(e.attrib.items())), (e.text or "").strip(),
                tuple(canonical(c) for c in e))

    # Sound includes its source, normalization and timeline dependencies. Copy
    # includes text, placement and schedule. Visual media items remain editable.
    seeds = [e for e in root if kind(e)[0] in {
        "hypit/audio-track", "hypit/text", "hypit/typography-track",
    }]
    protected = {}

    def visit(e):
        key = e.get("id") or repr(kind(e))
        if key in protected:
            return
        protected[key] = canonical(e)
        for child in e.iter():
            for value in child.attrib.values():
                for ref in re.findall(r'\{([\w-]+)(?:\.[\w.-]+)?\}', value):
                    if ref in nodes:
                        visit(nodes[ref])

    for seed in seeds:
        visit(seed)
    return tuple(sorted(protected.items()))


def assert_composition_preserves_sound_and_copy(base: Path, authored: Path) -> None:
    """Fail closed before promotion; changing IDs is not a composition edit."""
    if _protected_graph(base) != _protected_graph(authored):
        raise HypitIntegrationError(
            "局部画面修改改变了已确认的声音、字幕或时序；请保留原组件及引用，"
            "只修改反馈涉及的画面取景与转场，不重写其他内容"
        )


def assert_quality_revision(base: Path, authored: Path, allowed: set[str]) -> None:
    """Open only the defective presentation layer; protect source and timing."""
    if not allowed or not allowed <= {'visual', 'captions', 'audio'}:
        raise HypitIntegrationError('系统质量修正范围无效')

    def graph(path: Path):
        root = _markup(path)
        packages = {e.get('as'): e.get('from', '').rsplit('@', 1)[0] for e in root.findall('import')}
        sheets = {e.get('as'): e.get('source') for e in root.findall('import') if e.get('source')}
        nodes = {e.get('id'): e for e in root.iter() if e.get('id')}
        protected = {'imports': tuple(sorted(tuple(sorted(e.attrib.items())) for e in root.findall('import')))}

        def kind(e):
            prefix, _, name = e.tag.partition('__')
            return packages.get(prefix, prefix), name

        def filtered(e):
            package, name = kind(e)
            omitted = set()
            if 'audio' in allowed and (package, name) == ('@hypit/audio-track', 'Item'):
                omitted = {'gain', 'fade-in', 'fade-out'}
            if 'captions' in allowed and (package, name) == ('@hypit/typography-track', 'Area'):
                omitted = {'placement', 'style'}
            if 'visual' in allowed and package == '@hypit/media-track':
                omitted = {'frame', 'appearance', 'transition'}
            if 'visual' in allowed and (package, name) == ('@hypit/film', 'Film'):
                omitted = {'appearance'}
            children = [c for c in e if not ('visual' in allowed and kind(c) == ('@hypit/media-track', 'Sampling'))]
            return {k: v for k, v in e.attrib.items() if k not in omitted}, children

        def canonical(e):
            attrs, children = filtered(e)
            return kind(e), tuple(sorted(attrs.items())), (e.text or '').strip(), tuple(canonical(c) for c in children)

        def visit(e):
            key = e.get('id') or repr(kind(e))
            if key in protected:
                return
            protected[key] = canonical(e)

            def references(item):
                attrs, children = filtered(item)
                for value in attrs.values():
                    for ref in re.findall(r'\{([\w.-]+)\}', value):
                        identity = next((key for key in sorted(nodes, key=len, reverse=True)
                                         if ref == key or ref.startswith(key + '.')), None)
                        node = nodes.get(identity)
                        if node is not None:
                            visit(node)
                            continue
                        alias, _, selector = ref.partition('.')
                        if alias in sheets:
                            sheet = path.parent / sheets[alias]
                            if sheet.is_symlink() or sheet.resolve().parent != path.parent.resolve():
                                raise HypitIntegrationError('局部修正样式引用越界')
                            body = re.search(r'(?<![\w.-])' + re.escape(selector) + r'\s*\{([^{}]*)\}', sheet.read_text())
                            if body is None:
                                raise HypitIntegrationError('受保护样式无法核对；保留原样式声明')
                            protected['recipe:' + ref] = re.sub(r'\s+', ' ', body[1]).strip()
                for child in children:
                    references(child)

            references(e)

        roots = {'@hypit/media', '@hypit/media-pipeline', '@hypit/timeline-author', '@hypit/text',
                 '@hypit/audio-track', '@hypit/media-track', '@hypit/film', '@hypit/render-hyperframes', '@easel/audio-mix'}
        for element in root:
            package, name = kind(element)
            if package in roots or (package, name) in {('@hypit/spatial', 'Canvas'), ('@hypit/typography-track', 'Track')}:
                visit(element)
        return protected

    if graph(base) != graph(authored):
        raise HypitIntegrationError('系统局部修正改变了脚本、素材身份、播放时序或未授权部分；只修正审片指出的表现层缺陷')


def assert_video_trim_ranges(authored: Path, assets: dict[str, float]) -> None:
    """Preflight literal media-track trims against the admitted video duration.

    Hypit 0.2.7 NormalizationPlan rounds video span * target Clock rate; trims
    index that normalized source, not the original codec rate or the Film end.
    Hypit still owns static validation and exact execution-time media admission.
    """
    root = _markup(authored)
    aliases = {e.get("as"): e.get("from", "").split("@")[1]
               for e in root.findall("import") if e.get("from", "").startswith("@hypit/")}
    nodes = {e.get("id"): e for e in root.iter() if e.get("id")}
    sheets = {e.get("as"): e.get("source") for e in root.findall("import") if e.get("source")}

    def kind(e):
        prefix, _, name = e.tag.partition("__")
        return aliases.get(prefix), name

    def reference(value):
        match = re.fullmatch(r'\{([\w-]+)(?:\.[\w.-]+)?\}', value or "")
        return nodes.get(match[1]) if match else None

    for item in root.iter():
        if kind(item) != ("hypit/media-track", "Item"):
            continue
        recipe = re.fullmatch(r'\{([\w-]+)\.([\w.-]+)\}', item.get("appearance", ""))
        if not recipe or recipe[1] not in sheets:
            continue
        sheet = authored.parent / sheets[recipe[1]]
        if sheet.is_symlink() or sheet.resolve().parent != authored.parent.resolve():
            raise HypitIntegrationError("画面截取样式必须来自当前已核验的本地编排文件")
        rules = re.findall(r'([\w.-]+)\s*\{([^}]+)\}', sheet.read_text(encoding="utf-8"))
        properties = {key.strip(): value.strip() for selector, body in rules if selector == recipe[2]
                      for key, value in re.findall(r'([\w-]+)\s*:\s*([^;]+);?', body)}
        if not any(key in properties for key in ("trim-start", "trim-end")):
            continue
        try:
            start, end = (int(properties[key]) for key in ("trim-start", "trim-end"))
        except (KeyError, ValueError) as exc:
            raise HypitIntegrationError("画面截取起止必须成对使用整数帧；请按当前 Clock 换算") from exc
        normalized = reference(item.get("media"))
        if normalized is None or kind(normalized) != ("hypit/media-pipeline", "Normalize"):
            raise HypitIntegrationError("画面截取缺少可核验的标准化视频来源")
        video = reference(normalized.get("source"))
        clock = reference(normalized.get("clock"))
        if video is None or clock is None or video.get("src") not in assets:
            raise HypitIntegrationError("画面截取缺少已检查的原片时长或 Clock")
        try:
            rate = float(Fraction(clock.get("frame-rate", "")))
            duration = assets[video.get("src")]
            frames = math.floor(duration * rate + 0.5)
        except (ValueError, ZeroDivisionError, OverflowError) as exc:
            raise HypitIntegrationError("画面截取的时长或帧率无法核验") from exc
        if not (math.isfinite(rate) and rate > 0 and 0 <= start < end <= frames):
            raise HypitIntegrationError(
                f"画面截取 {start}～{end} 帧超出原片范围（约 {duration:g} 秒，"
                f"标准化帧率 {rate:g} fps，{frames} 帧）。"
                "秒转帧必须使用该 Normalize 的 Clock；只修正此镜头截取，保留声音、字幕和素材"
            )
