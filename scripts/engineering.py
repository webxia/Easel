#!/usr/bin/env python3
"""Lightweight, offline-first Codex engineering loop for an approved Easel Task.

No product API, production deployment, browser creation, paid media generation or
Git publication is performed by this controller. Run state stays outside Git.
The Codex sandbox is an execution boundary; the Git diff check is an additional
detection mechanism, not a substitute for OS permissions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = re.compile(r"<!-- AI_CODING_CONTRACT\s*\n(.*?)\n-->", re.S)
DECISIONS = {"ALIGNED", "DONE", "NEEDS_DECISION", "BLOCKED"}
SCHEMA = Path(__file__).with_name("engineering_reply.schema.json")


class Stop(Exception):
    def __init__(self, status: str, reason: str, details: dict | None = None):
        super().__init__(reason)
        self.status, self.reason, self.details = status, reason, details or {}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_path(path: str) -> bool:
    if not isinstance(path, str) or not path or "\\" in path or path.startswith("/"):
        return False
    parts = PurePosixPath(path.rstrip("/")).parts
    return bool(parts) and all(x not in ("", ".", "..") for x in parts) and parts[0] not in (".git", "outputs", "assets", ".venv", ".openclaw")


def within(path: str, scope: list[str]) -> bool:
    return any(path == allowed.rstrip("/") or (
        allowed.endswith("/") and path.startswith(allowed)
    ) for allowed in scope)


def task_contract(root: Path, filename: str):
    file = (root / filename).resolve()
    if not file.is_file() or not file.is_relative_to(root.resolve()) or "templates" in file.relative_to(root).parts:
        raise Stop("NEEDS_DECISION", "Task must be an approved, non-template file inside this repository")
    raw = file.read_text(encoding="utf-8")
    matches = CONTRACT.findall(raw)
    if len(matches) != 1:
        raise Stop("NEEDS_DECISION", "Task requires exactly one AI_CODING_CONTRACT block")
    try:
        spec = json.loads(matches[0])
    except json.JSONDecodeError as exc:
        raise Stop("NEEDS_DECISION", f"Invalid Task contract: {exc}") from exc
    if not isinstance(spec, dict) or set(spec) - {"scope", "owned_dirty_paths", "checks", "max_cycles"}:
        raise Stop("NEEDS_DECISION", "Unknown Task contract fields")
    scope = spec.get("scope")
    checks = spec.get("checks")
    owned = spec.get("owned_dirty_paths", [])
    cycles = spec.get("max_cycles", 3)
    if (not isinstance(scope, list) or not scope or
        not all(safe_path(s) for s in scope) or
        not isinstance(owned, list) or not all(safe_path(s) and within(s, scope) for s in owned) or
        not isinstance(checks, list) or not checks or
        not all(isinstance(c, str) and (c in ("docs", "frontend", "offline-e2e") or
                (c.startswith("pytest:") and safe_path(c[7:]) and c[7:].startswith("tests/")))
                for c in checks) or
        not isinstance(cycles, int) or isinstance(cycles, bool) or not 1 <= cycles <= 6):
        raise Stop("NEEDS_DECISION", "Invalid scope, dirty ownership, checks or max_cycles in Task")
    if not any(k in raw for k in ("完成条件", "验收条件", "Acceptance")):
        raise Stop("NEEDS_DECISION", "Task must specify observable acceptance criteria")
    return file, raw, {"scope": scope, "checks": checks, "owned_dirty_paths": owned,
                       "max_cycles": cycles}


def git(root: Path, *args: str) -> str:
    p = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False)
    if p.returncode:
        raise Stop("BLOCKED", "Git inspection failed: " + p.stderr[-350:])
    return p.stdout.rstrip("\n")


def snapshot(root: Path):
    """Capture tracked/untracked Git-visible changes without shell-quoted filenames."""
    p = subprocess.run(["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
                       cwd=root, capture_output=True, check=False)
    if p.returncode:
        raise Stop("BLOCKED", "Git status failed: " + p.stderr.decode(errors="replace")[-350:])
    records = {}
    for entry in p.stdout.split(b"\0"):
        if not entry:
            continue
        if len(entry) < 4 or any(ch in entry[:2] for ch in (ord("R"), ord("C"))):
            raise Stop("BLOCKED", "Rename/copy or malformed Git status; inspect workspace first")
        path = entry[3:].decode("utf-8", errors="surrogateescape")
        if not safe_path(path):
            raise Stop("BLOCKED", "Unsupported Git path in workspace: " + repr(path))
        file = root / path
        if file.is_symlink():
            records[path] = "<symlink>:" + digest(os.readlink(file).encode())
        elif file.is_file():
            stat = file.stat()
            # Large pre-existing media must not be read in full on each cycle.
            records[path] = (digest(file.read_bytes()) if stat.st_size <= 8 * 1024 * 1024
                             else f"<large>:{stat.st_size}:{stat.st_mtime_ns}")
        else:
            records[path] = "<missing>"
    return records



def changed(before: dict, after: dict):
    return sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))


def state_root(root: Path, task: Path) -> Path:
    base = Path(os.environ.get("EASEL_AI_CODING_STATE_DIR",
                            str(Path.home() / ".local/share/easel/ai-coding"))).expanduser()
    key = digest(str(root.resolve()).encode() + b"\0" + str(task).encode())[:20]
    path = base / key
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def save(path: Path, data: dict):
    if path.name == "state.json":
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
    payload = json.dumps(data, ensure_ascii=False, indent=2).encode()
    tmp = path.with_suffix(".tmp")
    with tmp.open("wb") as f:
        os.chmod(tmp, 0o600)
        f.write(payload)
    tmp.replace(path)


def load_state(path: Path):
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def evidence(path: Path, body: str):
    with path.open("w", encoding="utf-8") as f:
        os.chmod(path, 0o600)
        f.write(body[-200000:])


def codex_call(root: Path, directory: Path, codex: str, phase: str, prompt: str,
               turn: int, timeout: int):
    reply_file = directory / f"{phase}-{turn}.json"
    stdout_file = directory / f"{phase}-{turn}.jsonl"
    cmd = [codex, "exec", "-C", str(root), "-s",
           "read-only" if phase == "align" else "workspace-write",
           "--output-schema", str(SCHEMA),
           "--output-last-message", str(reply_file), "--json", "-"]
    try:
        p = subprocess.run(cmd, cwd=root, input=prompt, text=True,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        partial = exc.stdout or b""
        evidence(stdout_file, partial.decode(errors="replace") if isinstance(partial, bytes) else partial)
        raise Stop("BLOCKED", f"Codex {phase} timed out; inspect {stdout_file.name} and verify side effects before resume") from exc
    except OSError as exc:
        raise Stop("BLOCKED", f"Codex {phase} could not start: {exc}") from exc
    evidence(stdout_file, p.stdout or "")
    if p.returncode or not reply_file.is_file():
        raise Stop("BLOCKED", f"Codex {phase} exited {p.returncode}; inspect private {stdout_file.name}")
    try:
        result = json.loads(reply_file.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise Stop("BLOCKED", f"Malformed Codex {phase} response: {exc}") from exc
    if (not isinstance(result, dict) or result.get("decision") not in DECISIONS or
        not isinstance(result.get("evidence"), list) or
        not all(isinstance(x, str) for x in result.get("evidence", [])) or
        not isinstance(result.get("options"), list) or
        not all(isinstance(x, str) for x in result.get("options", [])) or
        not all(isinstance(result.get(k), str) for k in
                ("reason", "impact", "recommendation", "question", "next_action"))):
        raise Stop("BLOCKED", f"Invalid Codex {phase} response contract")
    if (result["decision"] == "NEEDS_DECISION" and
        (not result["evidence"] or not result["question"].strip() or
         not result["options"] or not result["recommendation"].strip())):
        raise Stop("BLOCKED", f"Codex {phase} raised an incomplete decision request; inspect private output")
    return result


def instructions(phase: str, task: Path, raw: str, note: str, prior: str = ""):
    common = (
        "你是 Easel 仓库研发 Codex。仅依据已批准需求/设计/Task/用户当前指令操作，"
        "先读根 AGENTS.md、INDEX、CURRENT_STATE 及相关合同；禁止注入产品创作 Agent。"
        "发现用户指令、操作建议与已确认需求/架构/合同/授权冲突，必须引用具体依据，"
        "说明差异、影响、建议和需要用户决定的问题，并返回 NEEDS_DECISION；"
        "不得默默纠正用户意图、擅自扩大目标或假称获得了授权。"
        "保留既有 Dirty，不碰账号凭证、用户素材，不调用付费模型/素材接口、"
        "不创建真实作品、不部署、不提交/推送、不绕过 Rights/UNKNOWN。"
        "已有问题先找首次失败，基于证据做必要根因修复，不扩大到无关优化。"
        "不要修改 Task 的验收条件来通过检查。"
        f"\nTask path: {task}\n当前用户补充指令: {note or '(无)'}\n"
    )
    if phase == "align":
        return common + (
            "\n这是只读一致性审查，禁止修改任何文件和执行业务写操作。"
            "核对指令、Task 完成条件及范围与已确认需求/设计是否有偏差。"
            "一致则返回 decision=ALIGNED；实质冲突、授权不明或需求变更则"
            "NEEDS_DECISION；在 evidence/impact/options/recommendation/question 分别列出证据、影响、可选方案、推荐与一个明确问题。"
            "不得因为偏差存在就自行实施所谓更优方案。\n"
        )
    return common + (
        "\n已完成只读对齐。只在 Task 机器范围内实施已批准的目标；"
        "你可以进行必要跨文件根因修复，但必须与当前验收相关。"
        "必要时新增回归测试，保持断言和安全边界。"
        "不必自行运行全量 E2E；外层程序会执行 Task 的固定离线 checks 并回馈失败。"
        "发现新冲突或新的授权边界，返回 NEEDS_DECISION；"
        "无法取得新证据返回 BLOCKED；完成本轮相关实现返回 DONE。"
        f"\n上一轮验证反馈: {prior or '(无)'}\n"
    )


def commands(root: Path, check: str):
    python = str(root / ".venv/bin/python") if (root / ".venv/bin/python").is_file() else sys.executable
    if check.startswith("pytest:"):
        return [[python, "-m", "pytest", "-q", check[7:]]]
    if check == "docs":
        return [[python, f"scripts/{name}.py"] for name in
                ("validate_skills", "validate_skill_commands", "validate_document_paths")]
    if check == "frontend":
        return [["npm", "--prefix", "web/frontend", "run", "lint"],
                ["node", "--test", *[str(x.relative_to(root))
                      for x in sorted((root / "tests/frontend").glob("*.test.mjs"))]],
                ["npm", "--prefix", "web/frontend", "run", "build"]]
    if check == "offline-e2e":
        temp = tempfile.mkdtemp(prefix="easel-ai-coding-a5-")
        return [[python, "scripts/validate_conversation_a5.py", "--root", temp]]
    raise Stop("NEEDS_DECISION", f"Unknown check {check}")


def verify(root: Path, directory: Path, checks: list[str], timeout: int):
    results = []
    for kind in checks:
        for argv in commands(root, kind):
            try:
                p = subprocess.run(argv, cwd=root, text=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
                output = p.stdout or ""
                code = p.returncode
            except subprocess.TimeoutExpired as exc:
                partial = exc.stdout or b""
                output = (partial.decode(errors="replace") if isinstance(partial, bytes) else partial) + f"\nTimeout: {exc}"
                code = 125
            except OSError as exc:
                output, code = repr(exc), 125
            results.append({"check": kind, "argv": argv[:4], "exit_code": code,
                            "tail": output[-1800:]})
            if kind == "offline-e2e" and code == 0:
                shutil.rmtree(argv[-1], ignore_errors=True)
            if code:
                save(directory / "checks.json", {"results": results})
                return False, results
    save(directory / "checks.json", {"results": results})
    return True, results


def perform(args):
    root = Path(args.repo).resolve()
    if not (root / ".git").exists():
        raise Stop("BLOCKED", "Not a Git worktree root")
    task, raw, spec = task_contract(root, args.task)
    directory = state_root(root, task)
    record_file = directory / "state.json"
    previous = load_state(record_file)
    if args.action == "status":
        print(json.dumps({"task": str(task), "record": previous, "private_dir": str(directory)},
                         ensure_ascii=False, indent=2))
        return 0
    branch = git(root, "branch", "--show-current")
    head = git(root, "rev-parse", "HEAD")
    before = snapshot(root)
    if args.action == "verify":
        ok, results = verify(root, directory, spec["checks"], args.timeout)
        print(json.dumps({"status": "SOFTWARE_PASS" if ok else "FAIL", "results": results}, ensure_ascii=False))
        return 0 if ok else 1
    if args.action == "resume":
        if not previous or previous.get("status") == "SOFTWARE_PASS":
            raise Stop("NEEDS_DECISION", "No unfinished task run to resume")
        if (previous.get("task_sha256") != digest(raw.encode()) or
            previous.get("instruction_sha256") != digest(args.instruction.encode()) or
            previous.get("head") != head or previous.get("branch") != branch or
            previous.get("last_snapshot") != before):
            raise Stop("NEEDS_DECISION", "Task, baseline, or workspace changed since checkpoint; review before resume")
        if previous.get("status") == "NEEDS_DECISION":
            raise Stop("NEEDS_DECISION", "Unresolved user decision; revise approved Task first", previous.get("decision"))
        if previous.get("cycle", 0) >= spec["max_cycles"]:
            raise Stop("BLOCKED", "Task exhausted its approved engineering attempts; no automatic restart")
        origin = previous.get("baseline", {})
        own = set(changed(origin, before))
        if any(not within(path, spec["scope"]) for path in own):
            raise Stop("BLOCKED", "Previous run changed out-of-scope files; manual reconciliation required")
    else:
        own = set()
        if previous.get("task_sha256") == digest(raw.encode()) and previous.get("status") not in (None, "DRY_RUN"):
            raise Stop("NEEDS_DECISION", "This Task has an existing run; use resume, or obtain a revised approved Task")
    dirty_collision = sorted(k for k in before if within(k, spec["scope"]) and
                             k not in spec["owned_dirty_paths"] and k not in own)
    if dirty_collision:
        raise Stop("NEEDS_DECISION", "Scope overlaps existing Dirty; add specific owned_dirty_paths in approved Task: " + ", ".join(dirty_collision[:8]))
    data = {"task": str(task.relative_to(root)), "branch": branch, "head": head,
            "task_sha256": digest(raw.encode()),
            "instruction_sha256": digest(args.instruction.encode()), "status": "ALIGNING",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "cycle": previous.get("cycle", 0) if args.action == "resume" else 0,
            "checks": spec["checks"], "scope": spec["scope"],
            "baseline": previous.get("baseline", before) if args.action == "resume" else before,
            "last_snapshot": before}
    if args.action == "resume":
        data["last_failure"] = previous.get("last_failure", "")
        data["failure_fingerprint"] = previous.get("failure_fingerprint")
    if args.dry_run:
        data["status"] = "DRY_RUN"
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    lock = directory / "running.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise Stop("BLOCKED", "Task run lock exists; verify prior process/side effects before manual recovery") from exc
    try:
        with os.fdopen(fd, "w") as f:
            f.write(str(os.getpid()))
        save(record_file, data)
        try:
            alignment = codex_call(root, directory, args.codex_bin, "align",
                                   instructions("align", task, raw, args.instruction),
                                   0, args.timeout)
            if alignment["decision"] != "ALIGNED":
                raise Stop("NEEDS_DECISION" if alignment["decision"] == "NEEDS_DECISION" else "BLOCKED",
                           alignment["reason"], alignment)
            if git(root, "rev-parse", "HEAD") != head or snapshot(root) != before:
                raise Stop("BLOCKED", "Read-only alignment changed workspace; inspect before proceeding")
            prior = previous.get("last_failure", "") if args.action == "resume" else ""
            last_key = previous.get("failure_fingerprint") if args.action == "resume" else None
            first_cycle = previous.get("cycle", 0) + 1 if args.action == "resume" else 1
            for cycle in range(first_cycle, spec["max_cycles"] + 1):
                data["status"], data["cycle"] = "CODING", cycle
                save(record_file, data)
                decision = codex_call(root, directory, args.codex_bin, "code",
                                      instructions("code", task, raw, args.instruction, prior),
                                      cycle, args.timeout)
                if decision["decision"] != "DONE":
                    raise Stop("NEEDS_DECISION" if decision["decision"] == "NEEDS_DECISION" else "BLOCKED",
                               decision["reason"], decision)
                after = snapshot(root)
                unexpected = [p for p in changed(before, after) if not within(p, spec["scope"])]
                if unexpected or git(root, "rev-parse", "HEAD") != head:
                    raise Stop("BLOCKED", "Out-of-scope modification or HEAD changed; preserve evidence: " + ", ".join(unexpected[:12]))
                if digest(task.read_bytes()) != data["task_sha256"]:
                    raise Stop("NEEDS_DECISION", "Task acceptance/authorization changed while coding")
                data["status"] = "VERIFYING"
                save(record_file, data)
                ok, reports = verify(root, directory, spec["checks"], args.timeout)
                after_test = snapshot(root)
                unexpected = [p for p in changed(before, after_test) if not within(p, spec["scope"])]
                if unexpected:
                    raise Stop("BLOCKED", "Checks modified out-of-scope files: " + ", ".join(unexpected[:12]))
                if ok:
                    data.update(status="SOFTWARE_PASS", changed=changed(before, after_test),
                                note="Offline checks passed; REAL_E2E and CREATOR_ACCEPTED remain NOT_TESTED")
                    save(record_file, data)
                    print(json.dumps(data, ensure_ascii=False, indent=2))
                    return 0
                prior = json.dumps(reports[-1], ensure_ascii=False)
                # Ignore volatile test timings, but preserve error text and exact file state.
                signature = re.sub(r"\b\d+\.\d+s\b", "<elapsed>", prior)
                fingerprint = digest((signature + json.dumps(after_test, sort_keys=True)).encode())
                data["last_failure"] = prior
                data["failure_fingerprint"] = fingerprint
                data["last_snapshot"] = after_test
                save(record_file, data)
                if fingerprint == last_key:
                    raise Stop("BLOCKED", "Same failed evidence and file state; no progress from another code cycle")
                last_key = fingerprint
            raise Stop("BLOCKED", f"Reached bounded max_cycles={spec['max_cycles']}; preserve checkpoint and examine failure")
        except Stop as exc:
            data.update(status=exc.status, reason=exc.reason, decision=exc.details)
            try:
                data["last_snapshot"] = snapshot(root)
            except Stop:
                pass
            save(record_file, data)
            raise
    finally:
        lock.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description="Approved Task → Codex → offline regression evidence")
    parser.add_argument("action", choices=("status", "run", "resume", "verify"))
    parser.add_argument("--task", required=True, help="Existing approved Task Markdown relative to repo")
    parser.add_argument("--repo", default=str(ROOT))
    parser.add_argument("--instruction", default="", help="New user instruction checked against Task")
    parser.add_argument("--codex-bin", default="codex", help="Codex executable (test doubles supported)")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.timeout <= 3600:
        parser.error("--timeout must be 1..3600 seconds")
    try:
        return perform(args)
    except Stop as exc:
        print(json.dumps({"status": exc.status, "reason": exc.reason,
                          "evidence": exc.details.get("evidence", []),
                          "impact": exc.details.get("impact", ""),
                          "options": exc.details.get("options", []),
                          "recommendation": exc.details.get("recommendation", ""),
                          "question": exc.details.get("question", ""),
                          "next_action": exc.details.get("next_action", "")},
                         ensure_ascii=False, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
