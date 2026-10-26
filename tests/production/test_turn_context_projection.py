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
        'work': {'id': 'work', 'state': 'needs_decision', 'revision': 7, 'active_run_id':'run',
                 'current_plan_revision': 1, 'plans': [{'revision': 1, 'plan_hash': 'frozen', 'plan': {'script': 'PLAN' * 10000}}],
                 'tasks': [{'id': 'edit', 'run_id':'run', 'state': 'needs_decision', 'kind': 'edit', 'error_json': '{"code":"edit_duration_mismatch"}', 'result_json': 'RESULT' * 10000}],
                 'artifacts': [{'id': 'voice', 'kind': 'narration', 'metadata_json': 'MEDIA' * 10000}],
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


def test_current_run_projection_hides_retired_errors_without_losing_current_risk():
    from easel.conversation_pipeline import turn_context
    full={'context':{'entry':{'handoff':{'messages':['OLD-HANDOFF']},
        'frozen_basis':{'expression_policy':{'rules':'WORKER-ONLY'},'conversation_brief':{'fact':'原要求'},'channel_basis':{'position':'面向谁'}}},
        'profile':{'identity':'我是谁'},'brief':{'fact':'本轮纠正'},'sources':[{'ref':'source','text':'原话','attachments':[]} ]},
        'pending':[], 'current_plan':{'revision':7,'plan_hash':'exact','plan':{'script':'FULL-DRAFT'}},
        'work':{'active_run_id':'current','plans':[],
            'runs':[{'id':'old','state':'failed'},{'id':'current','kind':'planning','state':'needs_decision'}],
            'tasks':[{'id':'old-task','run_id':'old','error_json':'OLD-FAIL'},
                     {'id':'current-task','run_id':'current','kind':'plan','state':'needs_decision','error_json':'CURRENT-UNKNOWN'}],
            'reviews':[{'id':'old-review','run_id':'old','changes_json':'OLD-FAIL'}],
            'progress':[{'run_id':'old','detail':'OLD-PROGRESS'}],
            'artifacts':[{'id':'film1','kind':'output','output_revision':1,'playback_url':'/first'},
                         {'id':'film3','kind':'output','output_revision':3,'playback_url':'/third'}],
            'pending_operations':[{'id':'uncertain','state':'unknown'}]},
        'blockers':[{'unknown':True,'choices':[]}],
        'model_calls':{'diagnostics':[{'outcome':'timeout','operation_id':'uncertain'}],
                       'recovery':{'can_offer':False,'old_result':'UNKNOWN'}}}
    before=copy.deepcopy(full);view=turn_context(full)
    text=str(view)
    assert all(x not in text for x in ['OLD-FAIL','OLD-PROGRESS','WORKER-ONLY','FULL-DRAFT'])
    assert 'OLD-HANDOFF' in text  # Human requirements survive initial binding.
    assert 'CURRENT-UNKNOWN' in text and 'uncertain' in text
    assert view['context']['entry']['frozen_basis']['conversation_brief']=={'fact':'原要求'}
    assert view['context']['brief']=={'fact':'本轮纠正'}
    assert [x['playback_url'] for x in view['work']['artifacts']]==['/first','/third']
    assert view['current_plan']=={'revision':7,'plan_hash':'exact'}
    assert full==before
    full['blockers']=[];full['model_calls']={'diagnostics':[{'outcome':'succeeded'}],'recovery':None}
    assert turn_context(full)['model_calls']['diagnostics']==[]
