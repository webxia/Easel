"""Protect accepted sound and copy during composition-only authoring."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from easel.integrations.hypit.errors import HypitIntegrationError


def _protected_graph(source: Path) -> tuple:
    text = source.read_text(encoding="utf-8")
    # SVML uses typed, unquoted references and package-qualified element names.
    text = re.sub(r'=\{([^}]+)\}', lambda m: '="{' + m[1] + '}"', text)
    text = re.sub(r'(<\/?)([\w.-]+):([\w.-]+)', r'\1\2__\3', text)
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise HypitIntegrationError("局部修改产物无法读取；未改变已保留的成片") from exc
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
