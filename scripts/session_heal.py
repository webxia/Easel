#!/usr/bin/env python3
"""仅修复明确的旧Bedrock assistant无签名thinking块。

MiniMax工具续接需要原思考历史；来源不明、其他Provider、带签名或redacted块均保留。
不按当前默认模型猜测历史消息来源，不手工清洗Planning Harness transcript。

用法：
    session_heal.py <history.jsonl> [--dry-run] [--backup]
    session_heal.py --dir <sessions_dir> [--session-id ID] [--dry-run] [--backup]
    session_heal.py --selftest
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from copy import deepcopy
from pathlib import Path

_THINKING_TYPES = {"thinking"}


def sanitize_rows(rows: list[dict]) -> tuple[list[dict], dict]:
    """纯函数：清洗一组已解析的历史条目，返回 (新条目, 统计)。"""
    out: list[dict] = []
    thinking_removed = 0
    msgs_dropped = 0
    for r in rows:
        if not (isinstance(r, dict) and r.get("type") == "message"):
            out.append(r)
            continue
        msg = r.get("message")
        if (not isinstance(msg, dict) or msg.get('role') != 'assistant'
                or msg.get('provider') != 'amazon-bedrock'
                or 'anthropic.claude' not in str(msg.get('model', ''))):
            out.append(r)
            continue
        r = deepcopy(r)
        msg = r['message']
        content = msg.get("content") if isinstance(msg, dict) else None
        if isinstance(content, list):
            kept = []
            for b in content:
                if (isinstance(b, dict) and b.get("type") in _THINKING_TYPES
                        and not b.get('signature') and not b.get('thinkingSignature')):
                    thinking_removed += 1
                    continue
                kept.append(b)
            if not kept:
                msgs_dropped += 1          # content 变空 → 丢掉整条（空消息非法）
                continue
            msg["content"] = kept
        elif content == [] or content is None:
            msgs_dropped += 1
            continue
        out.append(r)
    return out, {"thinking_removed": thinking_removed, "msgs_dropped": msgs_dropped}


def sanitize_history_file(path: Path, dry_run: bool = False, backup: bool = False) -> dict:
    """清洗单个 .jsonl 历史文件。返回统计（changed=是否有改动）。best-effort：坏行原样保留。"""
    if not path.is_file():
        return {"path": str(path), "error": "not found", "changed": False}
    raw = path.read_text(encoding="utf-8").splitlines()
    rows: list = []
    bad_lines: list[str] = []
    for line in raw:
        s = line.strip()
        if not s:
            continue
        try:
            rows.append(json.loads(s))
        except Exception:
            bad_lines.append(line)      # 非法 JSON 行：原样留着，不动
    clean, stats = sanitize_rows(rows)
    changed = stats["thinking_removed"] > 0 or stats["msgs_dropped"] > 0
    stats.update({"path": str(path), "lines_in": len(rows), "lines_out": len(clean),
                  "bad_lines": len(bad_lines), "changed": changed})
    if changed and not dry_run:
        if backup:
            bak = path.with_suffix(path.suffix + ".bak")
            if not bak.exists():
                bak.write_text("\n".join(raw) + "\n", encoding="utf-8")
                stats["backup"] = str(bak)
        # 原子写：临时文件 + 替换
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".heal-", suffix=".jsonl")
        os.close(fd)
        Path(tmp).write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in clean)
            + ("".join(l + "\n" for l in bad_lines) if bad_lines else ""),
            encoding="utf-8")
        os.replace(tmp, path)
    return stats


def heal_dir(sessions_dir: Path, session_id: str | None, dry_run: bool, backup: bool) -> list[dict]:
    """清洗某个 sessions 目录下的历史文件。session_id 指定则只清那一个；否则清所有
    非 trajectory 的 `<uuid>.jsonl`。"""
    results = []
    if session_id:
        files = [sessions_dir / f"{session_id}.jsonl"]
    else:
        files = [p for p in sessions_dir.glob("*.jsonl") if not p.name.endswith(".trajectory.jsonl")]
    for f in files:
        results.append(sanitize_history_file(f, dry_run, backup))
    return results


def _selftest() -> int:
    ok = True

    def chk(name, cond):
        nonlocal ok
        print(f"[{'PASS' if cond else 'FAIL'}] {name}")
        ok = ok and cond

    rows = [
        {"type": "session"},
        {"type": "model_change", "modelId": "x"},
        {"type": "message", "message": {"role": "user", "content": [{"type": "text", "text": "hi"}]}},
        {"type": "message", "message": {"role": "assistant", "content": [
            {"type": "thinking", "thinking": "hmm"}, {"type": "text", "text": "answer"}]}},
        {"type": "message", "message": {"role": "assistant", "content": []}},            # 空 → 丢
        {"type": "message", "message": {"role": "assistant", "content": [
            {"type": "thinking", "thinking": "only"}]}},                                  # 仅thinking → 变空丢
        {"type": "message", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": "t1", "name": "x", "input": {}}]}},               # 保留 tool_use
    ]
    for row in rows:
        if row.get('message', {}).get('role') == 'assistant':
            row['message'].update(provider='amazon-bedrock', model='anthropic.claude-fixture')
    clean, st = sanitize_rows(rows)
    chk("thinking 全删", st["thinking_removed"] == 2)
    chk("空/仅thinking 消息丢 2 条", st["msgs_dropped"] == 2)
    chk("非message 条目保留", sum(1 for r in clean if r.get("type") != "message") == 2)
    chk("assistant 文本保留", any(r.get("type") == "message" and any(
        b.get("type") == "text" for b in r["message"]["content"]) for r in clean))
    chk("tool_use 保留", any(r.get("type") == "message" and any(
        b.get("type") == "tool_use" for b in r["message"]["content"]) for r in clean))
    chk("清洗后无 thinking 块", not any(
        r.get("type") == "message" and isinstance(r["message"].get("content"), list)
        and any(b.get("type") in _THINKING_TYPES for b in r["message"]["content"]) for r in clean))
    chk("清洗后无空 content", not any(
        r.get("type") == "message" and r["message"].get("content") == [] for r in clean))

    # 文件级 + 幂等
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "s.jsonl"
        p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
        s1 = sanitize_history_file(p, backup=True)
        chk("文件清洗 changed", s1["changed"])
        chk("备份已建", Path(s1.get("backup", "")).is_file())
        s2 = sanitize_history_file(p)          # 再跑一次应无改动（幂等）
        chk("幂等：二次无改动", not s2["changed"])

    print("✅ selftest 通过" if ok else "❌ selftest 失败")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="清洗 OpenClaw 会话历史（去无签名 thinking 块 + 空消息）")
    ap.add_argument("file", nargs="?", help="单个 history .jsonl 路径")
    ap.add_argument("--dir", help="sessions 目录")
    ap.add_argument("--session-id", help="只清该 session id（配合 --dir）")
    ap.add_argument("--dry-run", action="store_true", help="只报告不写")
    ap.add_argument("--backup", action="store_true", help="首次改动前备份为 .bak")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return _selftest()
    if a.file:
        r = sanitize_history_file(Path(a.file).expanduser(), a.dry_run, a.backup)
        print(json.dumps(r, ensure_ascii=False))
        return 0
    if a.dir:
        for r in heal_dir(Path(a.dir).expanduser(), a.session_id, a.dry_run, a.backup):
            print(json.dumps(r, ensure_ascii=False))
        return 0
    ap.error("需要 file 或 --dir（或 --selftest）")
    return 2


if __name__ == "__main__":
    sys.exit(main())
