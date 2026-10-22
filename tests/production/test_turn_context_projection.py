import copy

from tests.production.test_conversation import env, entry
from easel.conversation_bridge import PersistentWorkToolBridge


def test_turn_bootstrap_omits_historical_payloads_but_preserves_authority(env, monkeypatch):
    import easel.conversation_pipeline as pipeline
    service, conversations = env
    segment = entry(conversations, profile_ref='one')
    full = {
        'context': {'entry': {}, 'profile': {'identity': 'creator'}, 'sources': [],
                    'profile_save_target': {'files': {'memory': 'private'}}, 'brief': {}},
        'pending': [{'id': 'active', 'hash': 'hash', 'state': 'proposed', 'body': {'scope': 'resume'}},
                    {'id': 'old', 'state': 'applied', 'body': {'old': 'HISTORY' * 10000}}],
        'work': {'id': 'work', 'state': 'needs_decision', 'revision': 7,
                 'current_plan_revision': 1, 'plans': [{'revision': 1, 'plan_hash': 'frozen', 'plan': {'script': 'PLAN' * 10000}}],
                 'tasks': [{'id': 'edit', 'state': 'needs_decision', 'kind': 'edit', 'error_json': '{"code":"edit_duration_mismatch"}', 'result_json': 'RESULT' * 10000}],
                 'artifacts': [{'id': 'voice', 'metadata_json': 'MEDIA' * 10000}],
                 'pending_operations': [{'id': 'unknown', 'state': 'unknown'}]},
        'current_plan': {'plan': {'script': 'PLAN' * 10000}},
        'blockers': [{'unknown': True}], 'model_calls': {'status': 'unknown'},
    }
    before = copy.deepcopy(full)
    monkeypatch.setattr(pipeline, 'pending', lambda *args: full)
    result = PersistentWorkToolBridge(service).reserve(ui_session='ui', turn_id='first', segment_id=segment,
                                                       message='确认已有恢复提案', attachments=[])
    prompt = result['prompt']
    assert len(prompt) < 5000
    assert 'active' in prompt and 'frozen' in prompt and 'unknown' in prompt
    assert 'edit_duration_mismatch' in prompt and '确认已有恢复提案' in prompt
    assert 'HISTORY' not in prompt and 'RESULT' not in prompt and 'MEDIA' not in prompt
    assert full == before  # No mutation of authoritative pending/tool response.
    assert result['payload']['origin'] == 'user'
