"""Opt-in test of the installed native runtime, always with isolated local fakes."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.skipif(os.environ.get('EASEL_RUN_OPENCLAW_A1') != '1',
                    reason='Opt-in installed OpenClaw integration; never uses real providers')
def test_native_openclaw_work_bridge_with_isolated_fakes(tmp_path):
    root = Path(__file__).resolve().parents[2]
    probe = tmp_path/'probe'
    completed = subprocess.run([sys.executable, str(root/'scripts/validate_openclaw_work_bridge.py'),
                                '--root', str(probe)], cwd=root, capture_output=True, text=True, timeout=180)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    result = json.loads((probe/'result.json').read_text())
    assert result['status'] == 'PASS' and result['child_gateway_stopped']
    assert result['paid_requests'] == 0 and not result['production_runtime_used']
    assert result['planning_runs'] == 1 and result['command_count'] == 2
    assert len(result['checks']) >= 14
