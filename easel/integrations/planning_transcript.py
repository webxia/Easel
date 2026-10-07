"""Read an original OpenClaw run without opening its writable lifecycle."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from easel.creation_delivery import DeliveryExecutionUncertain

SELECTOR = 'session-accessor.sqlite-transcript-store-BczH1lRJ.mjs'
# Pins the installed selector reviewed in S2; a Runtime change fails closed.
SELECTOR_SHA = '3530fa169bac8712ed16532adf0ffc118d1af19feb4a18a30284693f2618e325'
RUNTIME_PARTS = {
    SELECTOR: SELECTOR_SHA,
    'chat-message-content-CgaQZ9n2.mjs': '6f7c485c8433c56e295a4316a1565801bc71630533057a645b0cee6223f76df8',
    'startup-trace-DTSRmmXT.mjs': '5335bef4fc43c6d4746ad45785c75bb84107abb419bd0939ee0bb6d1b6cc8eca',
}


def runtime_location(prefix, env):
    if len(prefix) == 2 and Path(prefix[1]).name == 'openclaw.mjs':
        node, script = prefix
    elif len(prefix) == 1:
        executable = shutil.which(prefix[0], path=env.get('PATH'))
        script = str(Path(executable or prefix[0]).resolve())
        node = str(Path(script).resolve().parent.parents[2] / 'bin' / 'node')
    else:
        raise DeliveryExecutionUncertain('Planning Runtime入口不可核实，未创建新执行')
    root = Path(script).resolve().parent
    if not Path(node).is_file() or not (root / 'package.json').is_file():
        raise DeliveryExecutionUncertain('Planning Runtime安装身份不可核实')
    package = json.loads((root / 'package.json').read_text())
    if (package.get('version') != '2026.9.4' or any(
            not (root / 'dist' / name).is_file() or
            hashlib.sha256((root / 'dist' / name).read_bytes()).hexdigest() != digest
            for name, digest in RUNTIME_PARTS.items())):
        raise DeliveryExecutionUncertain('Planning Runtime版本或结果选择器已变化')
    return node, root


def read_original(prefix, profile, call, *, runner=subprocess.run, env=None):
    from easel.integrations.planning_result_contract import MAX_RESULT_BYTES
    environment = dict(os.environ if env is None else env)
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', profile):
        raise DeliveryExecutionUncertain('Planning网关profile身份无效')
    node, root = runtime_location(prefix, environment)
    params = {'agentId': call['agent_id'], 'sessionKey': call['session_key'],
              'sessionId': call['session_id'], 'runId': call['run_id'],
              'profile': profile, 'runtimeParts': RUNTIME_PARTS, 'maxResultBytes': MAX_RESULT_BYTES}
    try:
        result = runner([node, str(Path(__file__).with_suffix('.mjs')), str(root)],
            input=json.dumps(params), text=True, capture_output=True, timeout=20, env=environment)
        value = json.loads(result.stdout)
        if result.returncode or not isinstance(value, dict): raise ValueError('read failed')
    except (OSError, subprocess.TimeoutExpired, ValueError):
        raise DeliveryExecutionUncertain('Planning原始结果读取中断；保留同一run/session') from None
    return value
