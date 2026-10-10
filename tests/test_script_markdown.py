"""Explicit v3 extractor checks; old Script ledger is not silently migrated."""
import hashlib
import json

import pytest

from easel.integrations.script_markdown import extract_units
from easel.integrations.script_truth import (
    ScriptTruthError, create_script_claim_ledger, validate_script_claim_ledger,
)


def _truth(tmp_path, quote="我在团队做过这个项目。"):
    path = tmp_path / "truth-packet.json"
    path.write_text(json.dumps({
        "schema": "easel-truth-packet@2",
        "claims": [{"source": "user_statement", "claim": quote, "source_quote": quote}],
        "personal_facts": [],
    }, ensure_ascii=False))
    return path


def test_markdown_blocks_are_byte_bound_and_all_substantive_lines_accounted(tmp_path):
    script = ("## 旁白\r\n我在团队做过这个项目。🌱\r\n"
              "- 第二句话。\r\n> 第三句话。\r\n"
              "## 未经证实的增长数字\r\n"
              "~~~text\r\n它声称去年增长了20%。\r\n~~~\r\n"
              "[source]: https://example.test/reference\r\n")
    units, coverage = extract_units(script)
    texts = [row["text"] for row in units]
    assert any("我在团队做过这个项目。" in line for line in texts)
    assert any("未经证实的增长数字" in line for line in texts)
    assert any("增长了20%" in line for line in texts)
    assert any("example.test" in line for line in texts)
    assert coverage and all(row["disposition"] in {"reviewed", "structural"} for row in coverage)
    raw = script.encode("utf-8")
    for row in units:
        ref = row["source_block_span"]
        assert ref["script_sha256"] == hashlib.sha256(raw).hexdigest()
        assert raw[ref["start"]:ref["end"]]
        assert row["text_sha256"] == hashlib.sha256(row["text"].encode()).hexdigest()
    assert any(row["block_type"] == "fence" for row in units)
    assert any(row["role"] == "unspecified" for row in units)
    ledger = create_script_claim_ledger(script, _truth(tmp_path), revision="easel-script-claim-ledger@3")
    assert ledger["schema"] == "easel-script-claim-ledger@3"
    assert any(row["status"] == "TRUTH_SUPPORTED" for row in ledger["claims"])
    assert any("🌱" in row["text"] and row["status"] == "REVIEW_REQUIRED" for row in ledger["claims"])
    assert validate_script_claim_ledger(script, _truth(tmp_path), ledger) == ledger


def test_v3_unknown_headings_and_code_are_not_auto_accepted(tmp_path):
    script = "## 公司销售额突破100万\n- 我们的业绩很好。\n~~~text\n业绩已翻番。\n~~~"
    ledger = create_script_claim_ledger(script, _truth(tmp_path), revision="easel-script-claim-ledger@3")
    assert all(row["status"] == "REVIEW_REQUIRED" for row in ledger["claims"])
    assert any("销售额突破" in row["text"] for row in ledger["claims"])
    assert any("业绩已翻番" in row["text"] for row in ledger["claims"])

    for source in (
        '> ## 制作约束\n> 仅供拍摄参考。\n\n外层的增长断言尚未核实。',
        '- ## 制作约束\n  画面：这个未核实的断言来自列表。\n\n外层的增长断言尚未核实。',
        '## 镜头说明\n<div>\n公司增长20%。\n</div>',
        '## 镜头说明\n画面：<b>公司增长20%。</b>',
        '## 镜头说明\n~~~text\n画面：公司增长20%。\n~~~',
    ):
        guarded = create_script_claim_ledger(source, _truth(tmp_path), revision="easel-script-claim-ledger@3")
        assert all(row['status'] == 'REVIEW_REQUIRED' for row in guarded['claims'])


def test_v3_spans_and_schema_cannot_be_relabelled_as_legacy(tmp_path):
    path = _truth(tmp_path)
    script = "## 旁白\n我在团队做过这个项目。"
    v3 = create_script_claim_ledger(script, path, revision="easel-script-claim-ledger@3")
    assert v3["claims"][0]["status"] == "TRUTH_SUPPORTED"
    assert validate_script_claim_ledger(script, path, v3) == v3
    tampered = json.loads(json.dumps(v3))
    tampered["claims"][0]["source_block_span"]["start"] += 1
    from easel.integrations.script_truth import _canonical_digest
    tampered["ledger_sha256"] = _canonical_digest(tampered)
    with pytest.raises(ScriptTruthError):
        validate_script_claim_ledger(script, path, tampered)
    for changed in ('schema', 'parser', 'coverage', 'mapping'):
        altered = json.loads(json.dumps(v3))
        if changed == 'schema':
            altered['schema'] = 'easel-script-claim-ledger@2'
        elif changed == 'parser':
            altered['parser_identity']['version'] = 'other'
        elif changed == 'coverage':
            altered['coverage'].pop(0)
        else:
            altered['coverage'][-1]['review_unit_ordinals'] = []
        altered['ledger_sha256'] = _canonical_digest(altered)
        with pytest.raises(ScriptTruthError):
            validate_script_claim_ledger(script, path, altered)
    # No legacy producer remains: defaults always use complete Markdown @3.
    assert create_script_claim_ledger(script, path)["schema"] == "easel-script-claim-ledger@3"
    with pytest.raises(ScriptTruthError, match="revision"):
        create_script_claim_ledger(script, path, revision="easel-script-claim-ledger@2")


def test_v3_rejects_unmapped_or_oversized_blocks(tmp_path):
    with pytest.raises((ValueError, ScriptTruthError)):
        create_script_claim_ledger("## 制作约束\n" + "x" * 4100, _truth(tmp_path),
                                   revision="easel-script-claim-ledger@3")


def test_v3_inline_projection_preserves_locations_and_every_reference_definition(tmp_path):
    source = ('## **旁白**\r\n[主体 &amp; 细节][r]。🌱\r'
              '- 重复正文。\n  - 重复正文。\r\n'
              '> ![画面 *名称*](fixture.png "待核实的图片标题")\r\n\r\n'
              '| 结果 | 待核实 |\n| --- | --- |\n\n'
              '[r]: /first "原始引用"\r\n[r]: /second "重复引用"\n'
              '甲\u2028乙\u0085丙。\r\n')
    units, coverage = extract_units(source)
    text = [unit['text'] for unit in units]
    assert '主体 & 细节。' in text and '画面 名称' in text
    assert '待核实的图片标题' in text
    repeated = [unit for unit in units if unit['text'] == '重复正文。']
    assert len(repeated) == 2 and repeated[0]['source_block_span'] != repeated[1]['source_block_span']
    assert len([row for row in coverage if row['block_type'] == 'reference_definition']) == 2
    assert any('甲\u2028乙\u0085丙。' == unit['text'] for unit in units)
    raw = source.encode()
    for unit in units:
        span = unit['source_block_span']
        raw[span['start']:span['end']].decode('utf-8')
    tail = next(unit for unit in units if unit['text'].startswith('甲'))
    assert raw[tail['source_block_span']['start']:tail['source_block_span']['end']] == '甲\u2028乙\u0085丙。\r\n'.encode()
    ledger = create_script_claim_ledger(source, _truth(tmp_path), revision='easel-script-claim-ledger@3')
    assert ledger['coverage'] == coverage and ledger['parser_identity']['version'] == '4.0.0'
    assert ledger['parser_identity']['options']['inline_definitions'] is True
    assert 'table' not in ledger['parser_identity']['active_rules']['block']
    assert any(row['reason'] == 'reference_locator_not_a_spoken_assertion' for row in coverage)
    assert all(row['reason'] for row in coverage)
    assert validate_script_claim_ledger(source, _truth(tmp_path), ledger) == ledger


@pytest.mark.parametrize('source', ['', '## 旁白\n', '\x00', '字' * 45000, '短句。\n' * 1001])
def test_v3_fixed_capacity_and_empty_projection(source, tmp_path):
    with pytest.raises((ValueError, ScriptTruthError)):
        create_script_claim_ledger(source, _truth(tmp_path), revision='easel-script-claim-ledger@3')

