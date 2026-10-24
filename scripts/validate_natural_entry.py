#!/usr/bin/env python3
"""Installed Gateway + real entry router, isolated fake model; no user runtime."""
import json
import sys
import tempfile
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from validate_video_conversation import fixture
from web.conversation_api import natural_entry


def configure(app, service, model, web):
    path = service.outputs.parent/'openclaw.json'
    config = json.loads(path.read_text())
    config['agents']['entries']['main']['tools'] = {'profile':'full', 'allow':['easel_pipeline','session_status']}
    path.write_text(json.dumps(config))
    message = 'A1_CASE=entry 只讨论，不制作'
    model.extra_cases['entry'] = ('easel_pipeline', {'mode':'enter','kind':'new_work','user_quote':message})
    return {'config':config, 'message':message}


def main():
    root = Path(tempfile.mkdtemp(prefix='easel-g1-native-'))/'fixture'
    with fixture(root, configure=configure) as f:
        cfg = f['config']; key = 'agent:main:entry-fixture'
        prompt = f['message']
        natural_entry.reserve('entry-fixture', 'client-uuid-ignored', 'turn', prompt, prompt, 'one')
        try:
            response = httpx.post(f"http://127.0.0.1:{cfg['gateway']['port']}/v1/chat/completions",
                headers={'Authorization':'Bearer '+cfg['gateway']['auth']['token'],
                         'x-openclaw-session-key':key, 'x-openclaw-session-id':'client-uuid-ignored'},
                json={'model':'openclaw/main','messages':[{'role':'user','content':prompt}]}, timeout=90)
            assert response.status_code == 200, response.text
            entry = natural_entry.turns[key]
            assert entry['native'] and entry['native'] != 'client-uuid-ignored'
            assert entry['result'] and entry['result']['entered'], response.text
            pending = entry['result']['pending']
            assert pending['context']['entry']['profile_name'] == 'one'
            assert any(m['role']=='tool' and 'entered' in str(m['content'])
                       for request in f['model'].requests for m in request['messages'])
            with f['service'].store.connection() as conn:
                for table in ('works','runs','tasks','operations','authorization_grants'):
                    assert conn.execute('SELECT count(*) FROM '+table).fetchone()[0] == 0
            # An active Web reservation with a mismatched prompt fails before model.
            before = len(f['model'].requests)
            natural_entry.reserve('entry-fixture', 'ignored', 'turn2', 'different prompt', prompt, 'one')
            blocked = httpx.post(f"http://127.0.0.1:{cfg['gateway']['port']}/v1/chat/completions",
                headers={'Authorization':'Bearer '+cfg['gateway']['auth']['token'], 'x-openclaw-session-key':key},
                json={'model':'openclaw/main','messages':[{'role':'user','content':prompt}]}, timeout=90)
            assert len(f['model'].requests) == before, blocked.text
            print(json.dumps({'status':'PASS','native_uuid_observed':True,'entry_tool_executed':True,
                'claim_failure_blocks_model':True,'production_rows':0,'paid_requests':0,'root':str(root)}))
        finally:
            natural_entry.release('entry-fixture', natural_entry.turns.get(key,{}).get('turn'))


if __name__ == '__main__':
    main()
