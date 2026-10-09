"""Versioned CommonMark projection with exhaustive original-byte coverage.

Inline text is a review projection. Its location is the containing original
block; no normalized inline offset is presented as an original byte offset.
"""
from __future__ import annotations

import hashlib
import json
import re
from importlib.metadata import version
from pathlib import Path

EXTRACTOR = "script-markdown-blocks@1"
PARSER_VERSION = "4.0.0"
MAX_BYTES = 128 * 1024
MAX_UNITS = 1000
_DIRECTION = re.compile(
    r"^(?:画面|意图|镜头|第一人称|画幅|节奏|音轨|字幕策略|文字策略|"
    r"字幕与时间线细节|素材|肖像红线|素材红线|不写|禁止|约束|结构|总时长|语言)"
    r"\s*[：:]|^Beat\s+\d+\b", re.IGNORECASE,
)
_DIRECTION_HEADINGS = {"不写的内容", "备注", "制作约束", "镜头说明", "画面说明"}
_CLAIM_HEADINGS = {"旁白", "配音", "台词", "字幕文案", "落幅文字", "片尾文案", "屏幕文字"}
_OTHER_HEADINGS = {"脚本", "文案", "narration", "script"}
_SENTENCES = re.compile(r"(?<=[。！？!?])\s*|\n+")
_CONTAINERS = {"blockquote_open", "bullet_list_open", "ordered_list_open", "list_item_open"}
_INLINE_WRAPPERS = {"em_open", "em_close", "strong_open", "strong_close", "link_open", "link_close"}


def _parser():
    from markdown_it import MarkdownIt
    if version("markdown-it-py") != PARSER_VERSION:
        raise ValueError("Script Markdown parser version differs from the frozen profile")
    return MarkdownIt("commonmark", {"html": True, "linkify": False, "inline_definitions": True})


def parser_identity(parser=None) -> dict:
    import markdown_it
    parser = parser or _parser()
    package = Path(markdown_it.__file__).parent
    sources = {str(path.relative_to(package)): hashlib.sha256(path.read_bytes()).hexdigest()
               for path in sorted(package.rglob("*.py"))}
    return {"parser_sources_sha256": hashlib.sha256(json.dumps(sources, sort_keys=True).encode()).hexdigest(),
            "extractor_revision": EXTRACTOR, "package": "markdown-it-py",
            "version": PARSER_VERSION, "preset": "commonmark",
            "options": dict(parser.options), "active_rules": parser.get_active_rules(),
            "adapter_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


def _inline(children) -> str:
    if children is None:
        raise ValueError("Markdown inline content has no parsed children")
    values = []
    for child in children:
        if child.type in {"text", "code_inline", "html_inline"}:
            values.append(child.content)
        elif child.type in {"softbreak", "hardbreak"}:
            values.append("\n")
        elif child.type == "image":
            values.append(_inline(child.children))
        elif child.type not in _INLINE_WRAPPERS:
            raise ValueError("Unsupported Markdown inline token: " + child.type)
    return "".join(values)


def _has_inline_html(children):
    return any(child.type == "html_inline" or _has_inline_html(child.children) for child in children or [])


def _inline_metadata(children):
    for child in children or []:
        if child.type in {"link_open", "image"}:
            destination = child.attrs.get("href" if child.type == "link_open" else "src")
            if destination:
                yield "link_destination", destination, True, "reference_locator_not_a_spoken_assertion"
            if child.attrs.get("title"):
                yield "inline_title", child.attrs["title"], False, "inline_title_requires_review"
        if child.children:
            yield from _inline_metadata(child.children)


def extract_script(script: str) -> tuple[list[dict], list[dict], dict]:
    """Return review units, complete block coverage, and the actual parser identity."""
    try:
        raw = script.encode("utf-8")
    except UnicodeError as exc:
        raise ValueError("Markdown Script is not valid Unicode") from exc
    if not raw or len(raw) > MAX_BYTES or "\x00" in script:
        raise ValueError("Markdown Script invalid or exceeds review limit")
    # Match CommonMark's physical lines exactly. Python splitlines also splits
    # U+0085/U+2028/U+2029 and would misapply the parser's line maps.
    ends = [match.end() for match in re.finditer(r"\r\n|\r|\n", script)]
    if not ends or ends[-1] != len(script):
        ends.append(len(script))
    original_lines, offsets, cursor = [], [0], 0
    for end in ends:
        line = script[cursor:end]
        original_lines.append(line)
        offsets.append(offsets[-1] + len(line.encode("utf-8")))
        cursor = end
    covered = [False] * len(original_lines)
    digest = hashlib.sha256(raw).hexdigest()
    blocks, section = [], "unspecified"

    def add(kind, value, position, role, reason, *, structural=False, leaf=True):
        if position is None or len(position) != 2:
            raise ValueError("Markdown block has no source location")
        start, end = position
        if not (0 <= start < end <= len(original_lines)):
            raise ValueError("Markdown block has no valid source location")
        if leaf:
            for row in range(start, end):
                covered[row] = True
        blocks.append({"block_type": kind,
            "source_block_span": {"unit": "utf8-byte", "start": offsets[start], "end": offsets[end],
                                  "script_sha256": digest},
            "role": role, "content": value, "reason": reason,
            "disposition": "structural" if structural else "reviewed"})

    parser = _parser()
    tokens = parser.parse(script)
    for index, token in enumerate(tokens):
        if token.type in {"heading_open", "paragraph_open"}:
            if index + 1 >= len(tokens) or tokens[index + 1].type != "inline":
                raise ValueError("Unsupported Markdown block without inline children")
            value = _inline(tokens[index + 1].children)
            for kind, content, structural, reason in _inline_metadata(tokens[index + 1].children):
                add(kind, content, token.map, "structural" if structural else "unspecified",
                    reason, structural=structural)
            if token.type == "heading_open":
                name = value.strip()
                # Container-local labels cannot grant permission to outer prose.
                if token.level == 0:
                    section = ("direction" if name in _DIRECTION_HEADINGS
                               else "narration" if name in _CLAIM_HEADINGS else "unspecified")
                if name in _DIRECTION_HEADINGS | _CLAIM_HEADINGS | _OTHER_HEADINGS:
                    add("structural_heading", name, token.map, "structural",
                        "recognized_script_section", structural=True)
                else:
                    add("heading", value, token.map, "unspecified", "unknown_heading_requires_review")
            else:
                conservative = token.level > 0 or _has_inline_html(tokens[index + 1].children)
                add("paragraph", value, token.map, "unspecified" if conservative else section,
                    "nested_or_literal_html_requires_review" if conservative else "semantic_inline_projection")
        elif token.type in {"fence", "code_block", "html_block"}:
            value = token.content
            add(token.type, value, token.map, "unspecified",
                "literal_content_requires_review" if value.strip() else "empty_literal_block",
                structural=not value.strip())
        elif token.type == "definition":
            if token.map is None:
                raise ValueError("Markdown reference definition has no source location")
            add("reference_definition", "".join(original_lines[token.map[0]:token.map[1]]),
                token.map, "unspecified", "reference_definition_requires_review")
        elif token.type == "hr":
            add("separator", "", token.map, "structural", "thematic_break", structural=True)
        elif token.type in _CONTAINERS:
            add(token.type.removesuffix("_open"), "", token.map, "structural",
                "container_syntax_children_reviewed_separately", structural=True, leaf=False)
        elif token.type not in {"inline", "heading_close", "paragraph_close",
                                 "blockquote_close", "bullet_list_close", "ordered_list_close", "list_item_close"}:
            raise ValueError("Unsupported Markdown block token: " + token.type)

    # A container range never masks a missing leaf. Preserve any substantive
    # source the fixed parser did not project, including empty list markers.
    for number, line in enumerate(original_lines):
        if not covered[number]:
            blank = not line.strip()
            add("blank" if blank else "unparsed", line, (number, number + 1),
                "structural" if blank else "unspecified",
                "blank_line" if blank else "unprojected_source_requires_review", structural=blank)

    blocks.sort(key=lambda item: (item["source_block_span"]["start"],
                                  item["source_block_span"]["end"], item["block_type"]))
    units, coverage = [], []
    for number, block in enumerate(blocks, 1):
        info = {"block_id": f"block-{number:04d}",
                **{key: block[key] for key in ("block_type", "source_block_span", "role")}}
        parts = [] if block["disposition"] == "structural" else [
            piece.strip() for piece in _SENTENCES.split(block["content"]) if piece.strip()]
        if block["disposition"] == "reviewed" and not parts:
            raise ValueError("Substantive Markdown source has no review projection")
        coverage.append({**info, "disposition": block["disposition"], "reason": block["reason"],
                         "projected_text_sha256": hashlib.sha256(block["content"].encode("utf-8")).hexdigest(),
                         "review_unit_ordinals": list(range(len(parts)))})
        for ordinal, part in enumerate(parts):
            if len(part) > 4000:
                raise ValueError("Markdown Script review unit exceeds 4000 characters")
            # Literal code/HTML, definitions and unknown headings never acquire
            # creative-direction permission from a matching textual prefix.
            direction = block["block_type"] == "paragraph" and block["reason"] == "semantic_inline_projection" and (
                block["role"] == "direction" or block["role"] == "unspecified" and bool(_DIRECTION.match(part)))
            units.append({**info, "text": part, "unit_ordinal_in_block": ordinal,
                          "text_sha256": hashlib.sha256(part.encode("utf-8")).hexdigest(),
                          "extractor_revision": EXTRACTOR, "direction": direction})
            if len(units) > MAX_UNITS:
                raise ValueError("Markdown Script has too many review units")
    if not units:
        raise ValueError("Markdown Script contains no reviewable text")
    if not all(covered):
        raise ValueError("Markdown Script has unaccounted source lines")
    return units, coverage, parser_identity(parser)


def extract_units(script: str) -> tuple[list[dict], list[dict]]:
    units, coverage, _ = extract_script(script)
    return units, coverage
