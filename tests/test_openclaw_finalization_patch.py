"""Replay the installed gateway decision, without loading OpenClaw or any model."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from scripts.patch_openclaw_finalization import patched_source, patch_installation

FIXTURE = Path(__file__).parent / 'fixtures/openclaw-settled-finalization-2026.9.4.js'


def decision(source, stop_reason):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node required for the OpenClaw JavaScript decision replay')
    harness = '''
const resolveCurrentAttemptAssistant = a => a.currentAttemptAssistant;
// Prior read/exec batch is settled, but current assistant can be truncated.
const resolveSettledToolBatchEvidence = () => ({assistant:{stopReason:'toolUse'},
 allToolsProvenSettled:true, failedToolNames:new Set(),hasUnsettledToolError:false,intentionalTermination:false});
const hasAcceptedSessionSpawn = () => false;
const hasOnlySilentAssistantReply = () => false;
const hasAsyncActivity = () => false;
const hasCompletedMessagingToolDeliveryEvidence = () => false;
const shouldApplyNonVisibleTurnRetryGuard = () => true;
const classifyAssistantTurn = () => ({emptyResponse:true});
const SETTLED_TOOL_TERMINAL_CONTINUATION_INSTRUCTION = 'TOOL_DISABLED_FINALIZATION';
const TOOL_FAILURE_INSTRUCTION = 'failed';
'''
    params = {'allowEmptyStopContinuation': True, 'payloadCount': 0,
              'attempt': {'terminal': {'kind': 'completed'}, 'currentAttemptAssistant': {'stopReason': stop_reason},
                          'toolMetas': [{}], 'itemLifecycle': {'startedCount': 1, 'completedCount': 1, 'activeCount': 0}}}
    result = subprocess.run([node, '-e', harness + source + '\nconsole.log(JSON.stringify(resolveSettledToolTerminalContinuationInstruction(' + json.dumps(params) + ')));'],
                            capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def test_truncated_execution_does_not_enter_tool_disabled_finalization():
    original = FIXTURE.read_text()
    assert decision(original, 'length') == 'TOOL_DISABLED_FINALIZATION'  # actual bug
    patched = patched_source(original)
    assert decision(patched, 'length') is None
    for finished in ('stop', 'toolUse'):
        assert decision(patched, finished) == decision(original, finished)
    assert patched_source(patched) == patched


def test_patch_is_version_gated_offline_and_keeps_original(tmp_path):
    (tmp_path / 'dist').mkdir()
    (tmp_path / 'package.json').write_text('{"version":"2026.9.4"}')
    target = tmp_path / 'dist/builtin-openclaw-fixture.mjs'
    original = FIXTURE.read_text()
    target.write_text(original)
    assert patch_installation(tmp_path)['state'] == 'patch_required'
    assert target.read_text() == original
    assert patch_installation(tmp_path, apply=True)['state'] == 'patched_on_disk'
    assert target.with_name(target.name + '.easel-finalization-original').read_text() == original
    assert patch_installation(tmp_path, apply=True)['state'] == 'already_patched'
    (tmp_path / 'package.json').write_text('{"version":"future"}')
    with pytest.raises(ValueError, match='2026.9.4'):
        patch_installation(tmp_path, apply=True)
    with pytest.raises(ValueError, match='Unsupported'):
        patched_source('unknown source')
