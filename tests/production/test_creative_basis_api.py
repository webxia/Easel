"""CRE-01 four-source wiring through HTTP/worker/freeze; no live providers."""
import asyncio
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
from web.production_api import create_router
from easel.production.store import Store
from easel.production.service import WorkService
from easel.production.planning import PlanningTasks
from easel.production.operations import OperationService
from easel.production.worker import Worker
from .test_planning_runtime import Transport


def test_four_sources_reach_model_and_full_proposal_without_long_term_write(tmp_path):
    profile = {k: f'{k}的已确认内容' for k in ('identity', 'style', 'audience', 'platforms', 'preferences', 'memory')}
    folder = tmp_path / 'profiles' / 'person'; folder.mkdir(parents=True)
    for key, value in profile.items():
        (folder / (key + '.md')).write_text(value)
    store = Store(tmp_path / 'outputs/_production/production.sqlite3'); store.initialize()
    service = WorkService(store, outputs=tmp_path/'outputs', profiles=tmp_path/'profiles')
    # Existing, explicitly selected director fixture; no reference analysis or acceptance.
    director = {'schema_version':1, 'visual_style':'使用具体行动，不假称库存连续', 'storytelling':'保留未解问题'}
    with store.transaction() as conn:
        conn.execute("INSERT INTO directors(id,name,created_at,updated_at) VALUES ('d','导演','now','now')")
        conn.execute("INSERT INTO director_revisions(id,director_id,revision,style_json,evidence_json,style_confirmed,created_at) VALUES ('v','d',1,?,'[]',1,'now')", (json.dumps(director),))
    app = FastAPI(); app.include_router(create_router(lambda: service))
    client = TestClient(app)
    def post(path, payload, revision=None):
        response = client.post('/api/production'+path, json={'command_id':str(post.n), 'expected_revision':revision, 'payload':payload})
        post.n += 1
        assert response.status_code == 202, response.text
        return response.json()
    post.n = 1
    channel = post('/channels', {'name':'自省', 'profile_ref':'person', 'creative_basis':{'position':'一起辨认判断与事实','audience':'普通同龄人','themes':'日常自省'}})['id']
    settings = {'duration_seconds':20, 'aspect_ratio':'16:9','audio_mode':'silent', 'director_revision':'v', 'director_trial':True}
    work = post('/works', {'title':'问题', 'input_text':'吾日三省吾身，会不会变成自我审判？', 'profile_ref':'person','channel_id':channel,'settings':settings})['work_id']
    identity = {'provider':'direct-api','model':'fixture','mode':'structured'}
    post(f'/works/{work}/plans', {'services':[identity]}, 1)
    # Later configuration changes must not rewrite the enqueued creative basis.
    (folder/'memory.md').write_text('后来记忆')
    with store.transaction() as conn:
        conn.execute("UPDATE channels SET creative_basis_json=? WHERE id=?", (json.dumps({'position':'后来频道'}),channel))
    answer = {'title':'自省与判断','summary':'区分一次行为和对人的判决，结尾保留疑问', 'script':'事情没做好，就说明我不行吗？',
        'core_views':['拟议理解：把行为与身份判断分开'], 'facts':['来源：用户提供吾日三省吾身；尚未核对原文'],
        'scenes':[{'id':'s1','purpose':'呈现行为与判断的落差','visual':'拟议两份具体记录，不声称素材已经取得', 'narration':'事情没做好，就说明我不行吗？','duration_seconds':20}],
        'settings':{k:v for k,v in settings.items() if not k.startswith('director_')}}
    transport = Transport(answer)
    planning = PlanningTasks(service, OperationService(store), transport, identity, 'test')
    assert asyncio.run(Worker(store, {'plan':planning.plan}).run_once())
    result = client.get(f'/api/production/works/{work}').json()
    assert result['state'] == 'awaiting_confirmation', result['tasks']
    sent = json.loads(transport.requests[0][0][1]['content'][0]['text'])
    assert sent['profile'] == profile
    assert sent['director'] == director
    assert '一起辨认判断与事实' in sent['brief'] and '后来频道' not in sent['brief']
    assert '吾日三省吾身，会不会变成自我审判？' in sent['brief']
    plan = result['plans'][0]['plan']
    for field in ('summary','script','core_views','facts'):
        assert plan[field] == answer[field]
    assert plan['scenes'][0]['purpose'] == answer['scenes'][0]['purpose']
    assert json.loads(plan['profile_snapshot']['content']) == profile
    assert plan['conversation_basis']['channel_basis']['position'] == '一起辨认判断与事实'
    assert plan['director_revision_id'] == 'v' and not result['plans'][0]['confirmed_at']
    assert (folder/'memory.md').read_text() == '后来记忆'
    with store.connection() as conn:
        assert conn.execute('SELECT accepted_at FROM director_revisions').fetchone()[0] is None
        assert conn.execute('SELECT count(*) FROM artifacts').fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM operations').fetchone()[0] == 1
