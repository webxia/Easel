"""Synthetic input fidelity through the real planning worker and MODEL ledger.

These tests prove transport fidelity, not writing quality or audible naturalness.
"""
import asyncio
import json

from easel.production.catalog import CreativeCatalog
from easel.production.operations import OperationService
from easel.production.planning import PlanningTasks
from easel.production.service import WorkService, digest, encode, now, row
from easel.production.store import Store
from easel.production.worker import Worker
from .test_planning_runtime import Transport


PROFILE = {
    'identity': '我是修理旧收音机的业余爱好者，不是专业维修师。\n身份尾句。',
    'style': '保留犹豫与修正，不把猜测说成结论。\n表达尾句。',
    'audience': '面向没有电子基础、愿意耐心尝试的邻居。\n受众尾句。',
    'platforms': '只为本地社区记录过程，暂不承诺发布。\n平台尾句。',
    'preferences': '解释故障时先说观察，不虚构检测结果。\n偏好尾句。',
    'memory': '确认经历：只修好过一台；第二台仍未排除故障。\n记忆尾句。',
}
DIRECTOR = {'schema_version': 1, 'visual_style': '观察手部动作，允许空镜。',
            'storytelling': '围绕尚未解决的问题分享尝试，不制造胜利。',
            'sound': '解释时留理解空间，结尾保留环境声。'}
CHANNEL = {'position': '旧物修理中的判断过程', 'themes': '修理、观察与不知道',
           'audience': '愿意理解过程的初学者'}
ORIGINAL = '这次换了电池还是没声音。\n我只确认电池有电，还不知道哪里坏了。'
SOURCE = '请保留“还不知道”，不要写成我已修好；\n不要杜撰我测过电路。'
LATEST = '只把开头改成“电池换过了，还是没声音。”\n保留后半句的不确定性，不加成功总结。'
IDENTITY = {'provider': 'direct-api', 'model': 'fixture', 'mode': 'structured'}


def make_planning(tmp_path):
    profiles = tmp_path / 'profiles'
    selected = profiles / 'selected'
    selected.mkdir(parents=True)
    for name, value in PROFILE.items():
        (selected / (name + '.md')).write_text(value, encoding='utf8')
    store = Store(tmp_path / 'outputs' / '_production' / 'production.sqlite3')
    store.initialize()
    service = WorkService(store, outputs=tmp_path / 'outputs', profiles=profiles)
    channel = CreativeCatalog(service).command('channels', 'create', {
        'name': '合成测试频道', 'profile_ref': 'selected', 'creative_basis': CHANNEL,
    }, command_id='channel')['id']
    with store.transaction() as conn:
        stamp = now()
        conn.execute('INSERT INTO directors(id,name,created_at,updated_at) VALUES (?,?,?,?)',
                     ('fixture-director', '合成导演', stamp, stamp))
        conn.execute('INSERT INTO director_revisions(id,director_id,revision,style_json,style_confirmed,created_at) VALUES (?,?,1,?,1,?)',
                     ('fixture-director-v1', 'fixture-director', encode(DIRECTOR), stamp))
    settings = {'duration_seconds': 10, 'aspect_ratio': '16:9', 'audio_mode': 'silent',
                'director_revision': 'fixture-director-v1', 'director_trial': True}
    work = service.command('create', {'title': '纯合成写稿链路样本', 'input_text': ORIGINAL,
        'channel_id': channel, 'profile_ref': 'selected', 'settings': settings}, command_id='create')['work_id']
    brief = {'entries': [{'text': SOURCE, 'status': 'confirmed'}],
             'sources': [{'source_turn': 'synthetic-turn', 'text': SOURCE}]}
    with store.transaction() as conn:
        conn.execute('INSERT INTO work_briefs(work_id,revision,body_json,body_hash,created_at) VALUES (?,1,?,?,?)',
                     (work, encode(brief), digest(brief), now()))
    request = encode({'agent_request': '围绕尚未解决的故障写稿。',
                      'user_sources': [{'source_turn': 'synthetic-turn', 'text': SOURCE}]})
    service.command('plan', {'services': [IDENTITY], 'request': request}, work_id=work,
                    expected_revision=service.snapshot(work)['revision'], command_id='plan')
    answer = {'title': '未解决的故障', 'summary': '只讲已观察的结果', 'script': ORIGINAL,
              'scenes': [{'id': 's1', 'purpose': '留下真实问题', 'visual': '收音机与电池',
                          'narration': ORIGINAL, 'duration_seconds': 10}],
              'settings': {k: v for k, v in settings.items() if not k.startswith('director_')}}
    transport = Transport(answer)
    tasks = PlanningTasks(service, OperationService(store), transport, IDENTITY, 'fixture-writing-1')
    return service, work, transport, Worker(store, {'plan': tasks.plan}), selected, request


def recorded_requests(service, transport):
    with service.store.connection() as conn:
        records = [json.loads(r[0]) for r in conn.execute(
            "SELECT request_json FROM operations WHERE kind='MODEL' ORDER BY created_at")]
    assert len(records) == len(transport.requests)
    for record, actual in zip(records, transport.requests):
        # Compare durable bytes' parsed content with the final provider boundary.
        assert record == dict(zip(('messages', 'tools', 'schema'), actual))
    return [json.loads(r['messages'][1]['content'][0]['text']) for r in records]


def assert_basis(data, request):
    assert data['profile'] == PROFILE
    assert data['director'] == DIRECTOR
    assert ORIGINAL in data['brief']
    assert encode(CHANNEL) in data['brief']
    assert request in data['brief']
    assert encode({'entries': [{'text': SOURCE, 'status': 'confirmed'}],
                   'sources': [{'source_turn': 'synthetic-turn', 'text': SOURCE}]}) in data['brief']


def test_queued_writing_uses_exact_snapshot_not_later_profile_edits(tmp_path):
    service, work, transport, worker, selected, request = make_planning(tmp_path)
    # An edit after enqueue must not silently replace the authorized input snapshot.
    (selected / 'identity.md').write_text('后来的不同身份，不属于本次规划。', encoding='utf8')
    assert asyncio.run(worker.run_once())
    assert service.snapshot(work)['state'] == 'awaiting_confirmation'
    data, = recorded_requests(service, transport)
    assert_basis(data, request)
    assert '后来的不同身份' not in data['profile']['identity']
    frozen = service.snapshot(work)['plans'][0]['plan']
    assert json.loads(frozen['profile_snapshot']['content']) == PROFILE
    assert frozen['conversation_basis']['creative_request'] == request


def test_replan_transmits_latest_literal_feedback_and_complete_previous_plan(tmp_path):
    service, work, transport, worker, _, initial_request = make_planning(tmp_path)
    assert asyncio.run(worker.run_once())
    before = service.snapshot(work)['plans'][0]['plan']
    with service.store.connection() as conn:
        target = service.replanning_target(conn, row(conn, 'works', work))
    request = encode({'agent_request': '只调整开头，保持事实。',
                      'user_sources': [{'source_turn': 'synthetic-revision', 'text': LATEST}]})
    service.command('plan', {'intent': 'replan', 'request': request, 'replanning_target': target},
                    work_id=work, expected_revision=service.snapshot(work)['revision'], command_id='replan')
    assert asyncio.run(worker.run_once())
    first, revised = recorded_requests(service, transport)
    assert_basis(first, initial_request)
    assert_basis(revised, request)
    # Runtime strips only the separately supplied policy; every prior creative
    # fact, constraint, scene and literal feedback remains available for revision.
    expected = json.loads(encode(before))
    expected['conversation_basis'].pop('expression_policy')
    assert revised['plan'] == expected
    assert revised['plan']['conversation_basis']['creative_request'] == initial_request
    saved = service.snapshot(work)
    assert saved['state'] == 'awaiting_confirmation'
    plans = {item['revision']: item['plan'] for item in saved['plans']}
    assert plans[1] == before
    assert plans[2]['conversation_basis']['creative_request'] == request


def test_authoring_order_reaches_recorded_provider_request_without_changing_storage(tmp_path):
    from easel.production.contracts import PlanDocument
    service, work, transport, worker, _, _ = make_planning(tmp_path)
    assert asyncio.run(worker.run_once())
    with service.store.connection() as conn:
        operation = dict(conn.execute("SELECT * FROM operations WHERE kind='MODEL'").fetchone())
    request = json.loads(operation['request_json'])
    # Canonical ledger JSON sorts object keys. The embedded schema text retains
    # generation order, and must agree with the actual provider-side schema.
    embedded = json.loads(request['messages'][0]['content'].split('输出schema：', 1)[1])
    expected = ['facts', 'core_views', 'constraints', 'summary', 'script', 'scenes']
    assert list(embedded['properties'])[:6] == expected
    assert list(transport.requests[0][2]['properties'])[:6] == expected
    assert set(embedded['properties']) == set(PlanDocument.model_fields) - {
        'schema_version', 'profile_snapshot', 'director_revision_id', 'conversation_basis'}
    assert list(PlanDocument.model_fields)[:4] == ['schema_version', 'title', 'summary', 'script']
    # There is still one author call, no new polish/review stage for this fixture.
    assert transport.calls == 1
    assert service.snapshot(work)['plans'][0]['plan']['script'] == ORIGINAL


def test_existing_receipt_order_and_sparse_narration_response_remain_readable():
    from easel.production.planning import (
        NarrationPlanChanges, VoiceReadyCreativePlan, merge_narration_changes, received_plan,
    )
    # Deliberately use the previous author response order. Reading a successful
    # receipt must not demand that it was authored with the new schema order.
    old = {'title': '旧顺序合成稿', 'summary': '保留未解决的问题', 'script': ORIGINAL,
           'scenes': [{'id': 's1', 'purpose': '说明', 'visual': '收音机',
                       'narration': ORIGINAL, 'duration_seconds': 10}],
           'settings': {'duration_seconds': 10, 'aspect_ratio': '16:9', 'audio_mode': 'silent'},
           'facts': ['只确认电池有电。'], 'core_views': ['故障尚未确定。'],
           'constraints': ['不虚构测量。']}
    record = {'request_json': encode({'schema': {'title': 'VoiceReadyCreativePlan'}}),
              'receipt_json': encode({'result': {'message': {'content': json.dumps(old, ensure_ascii=False)}}})}
    assert received_plan(record) == VoiceReadyCreativePlan.model_validate(old)
    base = received_plan(record).model_dump(mode='json')
    changed = merge_narration_changes(NarrationPlanChanges.model_validate({
        'scenes': [{'id': 's1', 'narration': '电池换过了，还是没声音。'}],
    }), base).model_dump(mode='json')
    assert changed['script'] == '电池换过了，还是没声音。'
    assert changed['facts'] == base['facts']
    assert changed['core_views'] == base['core_views']
    assert changed['constraints'] == base['constraints']
    assert changed['settings'] == base['settings']
    assert changed['scenes'][0]['visual'] == base['scenes'][0]['visual']
    assert 'settings' not in NarrationPlanChanges.model_fields
