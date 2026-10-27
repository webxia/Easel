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


@pytest.mark.skipif(os.environ.get('EASEL_RUN_OPENCLAW_A1') != '1',
                    reason='Opt-in installed OpenClaw integration; never uses real providers')
def test_native_pipeline_bootstrap_claim_tool_and_end_without_business_writes(tmp_path,monkeypatch):
    import uuid
    import httpx
    root=Path(__file__).resolve().parents[2]
    monkeypatch.syspath_prepend(str(root/'scripts'))
    from validate_video_conversation import fixture
    from validate_openclaw_work_bridge import wait_for
    from easel.conversation import ConversationService
    with fixture(tmp_path/'native-pipeline') as f:
        f['model'].extra_cases['read']=('easel_pipeline',{'mode':'pending'})
        c=ConversationService(f['service'])
        with httpx.Client(base_url=f['url'],timeout=90,trust_env=False) as client:
            response=client.post('/api/chat/video/probe/enter',json={'command_id':'enter','entry':{'profile_ref':'one'}})
            response.raise_for_status();segment=response.json()['segment_id']
            for case in ['discuss','read']:
                turn=uuid.uuid4().hex
                response=client.post('/api/chat/stream',json={'sessionId':'probe','turnId':turn,'videoSegmentId':segment,
                    'message':'A1_CASE='+case,'interaction_mode':'video'})
                assert 'event: done' in response.text,response.text
                wait_for(lambda: c.view('probe')['turns'][-1]['state']=='ended',10)
        requests=f['model'].requests
        assert len(requests)==3  # One discussion + a read tool/response, no hidden retry.
        for request in requests:
            wire=json.dumps(request,ensure_ascii=False)
            assert '默认用自然、完整的中文交流' in wire
            from easel.video_workspace import CATALOG_SELECTION_POLICY
            assert CATALOG_SELECTION_POLICY in wire
            assert 'MAIN_ONLY_FORBIDDEN_SENTINEL' not in wire
            assert 'DEV_ONLY_FORBIDDEN_SENTINEL' not in wire
        with f['service'].store.connection() as conn:
            assert conn.execute('SELECT count(*) FROM works').fetchone()[0]==0
            assert conn.execute('SELECT count(*) FROM operations').fetchone()[0]==0
            turns=conn.execute('SELECT state,payload_json FROM conversation_turns').fetchall()
        assert len(turns)==2 and all(r['state']=='ended' for r in turns)
        assert all(json.loads(r['payload_json']).get('model_diagnostic') for r in turns)
        assert len(c.view('probe')['messages'])==4
