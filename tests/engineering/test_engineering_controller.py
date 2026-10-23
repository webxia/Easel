"""The engineering controller is tested with a fake Codex and disposable Git repo.

No real Codex model, Easel business runtime, provider or browser is started.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "engineering.py"
FAKE = r"""#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys
args = sys.argv[1:]
root = Path(args[args.index('-C') + 1])
out = Path(args[args.index('--output-last-message') + 1])
read_only = args[args.index('-s') + 1] == 'read-only'
mode = os.environ.get('FAKE_SCENARIO', 'pass')
prompt = sys.stdin.read()
decision = 'ALIGNED' if read_only else 'DONE'
if read_only and mode in ('conflict', 'incomplete_conflict'):
    decision = 'NEEDS_DECISION'
elif not read_only:
    if mode == 'pass':
        (root / 'src/feature.txt').write_text('fixed\n')
    if mode == 'partial':
        (root / 'src/feature.txt').write_text('partial\n')
        decision = 'BLOCKED'  # One attempt produced a partial fix, then stopped for evidence.
    if mode == 'outside':
        (root / 'unrelated.txt').write_text('should not happen\n')
    if mode == 'task_change':
        (root / 'task.md').write_text('changed acceptance\n')
out.write_text(json.dumps({'decision': decision,
    'reason': 'User instruction conflicts with accepted requirement' if decision == 'NEEDS_DECISION' else 'Observed',
    'evidence': ['test fixture only'], 'impact': 'May change the accepted contract',
    'options': [] if mode == 'incomplete_conflict' else ['Keep original acceptance', 'Propose a revised Task'],
    'recommendation': 'Keep original acceptance',
    'question': 'Which behavior should win?',
    'next_action': 'Ask user' if decision == 'NEEDS_DECISION' else 'Verify'}))
print(json.dumps({'type':'event','message':'fixture only'}))
"""


def cmd(root, state, *args, scenario="pass"):
    env = {**os.environ, "FAKE_SCENARIO": scenario,
           "EASEL_AI_CODING_STATE_DIR": str(state)}
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args, "--repo", str(root),
         "--task", "task.md", "--codex-bin", str(root / "fake_codex.py"),
         "--timeout", "20"],
        cwd=root, env=env, text=True, capture_output=True, timeout=60,
    )


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".gitignore").write_text("__pycache__/\n.pytest_cache/\n")
    (root / "src").mkdir()
    (root / "tests").mkdir()
    (root / "src/feature.txt").write_text("broken\n")
    (root / "tests/test_feature.py").write_text(
        "from pathlib import Path\n"
        "def test_feature():\n"
        "    assert Path('src/feature.txt').read_text() == 'fixed\\n'\n"
    )
    fake = root / "fake_codex.py"
    fake.write_text(FAKE)
    fake.chmod(0o755)
    contract = {"scope": ["src/"], "owned_dirty_paths": [],
                "checks": ["pytest:tests/test_feature.py"], "max_cycles": 2}
    (root / "task.md").write_text(
        "# Current approved Task\n- 验收条件：特性恢复到正确结果。\n"
        "<!-- AI_CODING_CONTRACT\n"
        + json.dumps(contract) + "\n-->\n"
    )
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "fixture@example.invalid"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Fixture"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=root, check=True)
    return root, tmp_path / "private"


def test_single_approval_success_and_private_evidence(project):
    root, state = project
    response = cmd(root, state, "run")
    assert response.returncode == 0, response.stderr
    assert json.loads(response.stdout)["status"] == "SOFTWARE_PASS"
    assert (root / "src/feature.txt").read_text() == "fixed\n"
    assert not (root / "unrelated.txt").exists()
    folders = list(state.iterdir())
    assert len(folders) == 1
    assert (folders[0] / "align-0.jsonl").is_file()
    assert (folders[0] / "checks.json").is_file()
    assert json.loads(cmd(root, state, "status").stdout)["record"]["status"] == "SOFTWARE_PASS"


def test_instruction_conflict_stops_before_modification(project):
    root, state = project
    response = cmd(root, state, "run", "--instruction", "忽略已确认需求", scenario="conflict")
    assert response.returncode == 2
    assert json.loads(response.stderr)["status"] == "NEEDS_DECISION"
    assert (root / "src/feature.txt").read_text() == "broken\n"
    record = json.loads(cmd(root, state, "status").stdout)["record"]
    assert record["status"] == "NEEDS_DECISION"


def test_existing_dirty_requires_explicit_task_ownership(project):
    root, state = project
    (root / "src/feature.txt").write_text("preexisting dirty\n")
    response = cmd(root, state, "run")
    assert response.returncode == 2
    assert json.loads(response.stderr)["status"] == "NEEDS_DECISION"
    assert (root / "src/feature.txt").read_text() == "preexisting dirty\n"


def test_out_of_scope_change_is_blocked_not_hidden(project):
    root, state = project
    response = cmd(root, state, "run", scenario="outside")
    assert response.returncode == 2
    assert json.loads(response.stderr)["status"] == "BLOCKED"
    assert (root / "unrelated.txt").exists()
    assert (root / "src/feature.txt").read_text() == "broken\n"


def test_no_progress_cannot_loop_indefinitely(project):
    root, state = project
    response = cmd(root, state, "run", scenario="no_change")
    assert response.returncode == 2
    assert json.loads(response.stderr)["status"] == "BLOCKED"
    record = json.loads(cmd(root, state, "status").stdout)["record"]
    assert record["cycle"] == 2
    assert record["status"] == "BLOCKED"


def test_malformed_or_unsafe_task_contract_fails_closed(project):
    root, state = project
    contract = {"scope": ["../secrets/"], "checks": ["pytest:tests/test_feature.py"]}
    (root / "task.md").write_text(
        "- 验收条件：ok\n<!-- AI_CODING_CONTRACT\n" + json.dumps(contract) + "\n-->\n"
    )
    response = cmd(root, state, "run")
    assert response.returncode == 2
    assert json.loads(response.stderr)["status"] == "NEEDS_DECISION"



def test_resume_after_software_pass_is_not_new_task_authorization(project):
    # Running an already-passed task must not be treated as new authorization.
    root, state = project
    assert cmd(root, state, "run").returncode == 0
    response = cmd(root, state, "resume")
    assert response.returncode == 2
    assert json.loads(response.stderr)["status"] == "NEEDS_DECISION"


def test_unicode_untracked_unrelated_paths_are_preserved(project):
    root, state = project
    personal = root / "未跟踪资料.txt"
    personal.write_text("用户既有信息\n")
    response = cmd(root, state, "run")
    assert response.returncode == 0, response.stderr
    assert personal.read_text() == "用户既有信息\n"


def test_resume_uses_previous_owned_partial_changes(project):
    root, state = project
    first = cmd(root, state, "run", scenario="partial")
    assert first.returncode == 2
    assert json.loads(first.stderr)["status"] == "BLOCKED"
    assert (root / "src/feature.txt").read_text() == "partial\n"
    second = cmd(root, state, "resume", scenario="pass")
    assert second.returncode == 0, second.stderr
    assert json.loads(second.stdout)["status"] == "SOFTWARE_PASS"


def test_conflict_output_preserves_user_decision_question(project):
    root, state = project
    reply = cmd(root, state, "run", scenario="conflict")
    output = json.loads(reply.stderr)
    assert reply.returncode == 2
    assert output["question"] == "Which behavior should win?"
    assert output["evidence"] == ["test fixture only"]
    assert output["impact"] == "May change the accepted contract"
    assert len(output["options"]) == 2
    assert output["recommendation"] == "Keep original acceptance"


def test_preexisting_symlink_outside_scope_is_not_modified(project):
    root, state = project
    link = root / "existing-media-link"
    link.symlink_to(root / "src/feature.txt")
    response = cmd(root, state, "run")
    assert response.returncode == 0, response.stderr
    assert link.is_symlink()
    assert link.resolve() == (root / "src/feature.txt")


def test_preexisting_large_file_does_not_prevent_task(project):
    root, state = project
    large = root / "historical-preview.bin"
    with large.open("wb") as f:
        f.truncate(9 * 1024 * 1024)
    response = cmd(root, state, "run")
    assert response.returncode == 0, response.stderr
    assert large.stat().st_size == 9 * 1024 * 1024



def test_incomplete_conflict_report_blocks_without_coding(project):
    root, state = project
    result = cmd(root, state, "run", scenario="incomplete_conflict")
    assert result.returncode == 2
    assert json.loads(result.stderr)["status"] == "BLOCKED"
    assert (root / "src/feature.txt").read_text() == "broken\n"



def test_resume_cannot_bypass_total_attempt_budget(project):
    root, state = project
    first = cmd(root, state, "run", scenario="no_change")
    assert first.returncode == 2
    assert json.loads(first.stderr)["status"] == "BLOCKED"
    before = (root / "src/feature.txt").read_text()
    resumed = cmd(root, state, "resume", scenario="pass")
    restarted = cmd(root, state, "run", scenario="pass")
    assert resumed.returncode == restarted.returncode == 2
    assert json.loads(resumed.stderr)["status"] == "BLOCKED"
    assert json.loads(restarted.stderr)["status"] == "NEEDS_DECISION"
    assert (root / "src/feature.txt").read_text() == before


def test_resume_requires_same_user_instruction(project):
    root, state = project
    first = cmd(root, state, "run", "--instruction", "保持现有合同", scenario="partial")
    assert first.returncode == 2
    changed = cmd(root, state, "resume", "--instruction", "改变合同", scenario="pass")
    assert changed.returncode == 2
    assert json.loads(changed.stderr)["status"] == "NEEDS_DECISION"
    assert (root / "src/feature.txt").read_text() == "partial\n"
    correct = cmd(root, state, "resume", "--instruction", "保持现有合同", scenario="pass")
    assert correct.returncode == 0, correct.stderr


def test_dry_run_does_not_start_codex_or_write_checkpoint(project):
    root, state = project
    response = cmd(root, state, "run", "--dry-run")
    assert response.returncode == 0, response.stderr
    assert json.loads(response.stdout)["status"] == "DRY_RUN"
    assert (root / "src/feature.txt").read_text() == "broken\n"
    assert not list(state.rglob("state.json"))
