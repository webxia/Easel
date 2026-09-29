from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "shared" / "scripts" / "xhs_publish.py"
SPEC = importlib.util.spec_from_file_location("xhs_publish_guards_test", SCRIPT)
assert SPEC and SPEC.loader
xhs_publish = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(xhs_publish)


class InputElement:
    def __init__(self, value: str):
        self.value = value

    def evaluate(self, _script):
        return "INPUT"

    def input_value(self):
        return self.value


class EditorElement:
    def __init__(self, value: str):
        self.value = value

    def evaluate(self, _script):
        return "DIV"

    def inner_text(self):
        return self.value


def test_written_title_must_match_exactly(monkeypatch):
    monkeypatch.setattr(xhs_publish, "_die", lambda message, code=1: (_ for _ in ()).throw(RuntimeError(message)))
    xhs_publish._require_field_text(InputElement("标题"), "标题", "标题", exact=True)
    with pytest.raises(RuntimeError, match="未被平台确认"):
        xhs_publish._require_field_text(InputElement(""), "标题", "标题", exact=True)


def test_written_content_must_be_readable_from_editor(monkeypatch):
    monkeypatch.setattr(xhs_publish, "_die", lambda message, code=1: (_ for _ in ()).throw(RuntimeError(message)))
    xhs_publish._require_field_text(EditorElement("第一段\n第二段"), "第一段\n第二段", "正文")
    with pytest.raises(RuntimeError, match="未被平台确认"):
        xhs_publish._require_field_text(EditorElement(""), "第一段", "正文")
