"""CRE-01: synthetic lossless views and durable request compatibility; no providers."""
import asyncio
from copy import deepcopy
from dataclasses import replace
import json

import pytest

from easel.production.context import TaskContext
from easel.production.expression_policy import snapshot, _digest
from .test_model_tasks import run, Answer


def fixture_context():
    profile = {key: key + '明确偏好' for key in ('identity', 'style', 'audience', 'platforms', 'preferences', 'memory')}
    constraints = {'director': {'narrative': '保留真实矛盾' * 100}, 'confirmed_constraints': ['不移植他人经历' * 50],
                   'plan_hash': 'frozen-plan', 'duration_seconds': 180}
    uses = [
        {'role': 'visual', 'scene_id': 's1', 'board_id': 'board', 'board_frame_index': 2, 'board_scene_ids': ['s1', 's3']},
        {'role': 'sfx', 'scene_id': 's1', 'cue_id': 'door', 'at': 3, 'duration': 1, 'timing_basis': 'absolute'},
        {'role': 'sfx', 'scene_id': 's2', 'cue_id': 'paper', 'at': 6, 'duration': 2, 'timing_basis': 'scene'},
    ]
    artifacts = []
    for i, use in enumerate(uses):
        use['need'] = {'need_id': str(i), 'constraints': deepcopy(constraints), 'intent': {'description': '具体用途'}}
        artifacts.append({'asset_id': f'a{i}', 'kind': 'image' if i == 0 else 'audio', 'metadata': {
            'use_constraints': deepcopy(constraints), 'material_uses': [use],
            'rights': {'status': 'unknown' if i == 2 else 'known', 'usage_constraints': ['仅用于指定场景']},
            'candidate_role': 'sfx', 'candidate_only': True, 'attribution': f'credit-{i}',
            'observation': {'audio_listened': False}, 'original_audio': {'protected': True},
            'timing': {'local_alignment': {'status': 'received'}, 'duration': 4},
            'future_field': {'must_keep': i}}})
    return TaskContext('work', 'run', 'task', profile_ref='author', profile=profile,
        director=deepcopy(constraints['director']), plan={'script': '仅在条件成立时有效', 'profile_snapshot': {'profile_ref': 'author', 'content': json.dumps(profile), 'content_hash': 'original'}},
        artifacts=tuple(artifacts), allowed_handles=frozenset(a['asset_id'] for a in artifacts),
        expression_policy=snapshot(), editor_view=True)


def expand(view, original_content):
    data = deepcopy(view)
    shared = data.pop('task_view')['shared_constraints']
    for artifact in data['artifacts']:
        meta = artifact['metadata']
        slots = [(meta, 'use_constraints')] + [(u['need'], 'constraints') for u in meta['material_uses']]
        for parent, key in slots:
            if set(parent[key]) == {'task_view_ref'}:
                parent[key] = deepcopy(shared[parent[key]['task_view_ref']])
    def resolve(value):
        if isinstance(value, dict):
            if value == {'context_ref': '/director'}:
                return deepcopy(data['director'])
            return {k: resolve(v) for k, v in value.items()}
        if isinstance(value, (tuple, list)):
            return type(value)(resolve(v) for v in value)
        return value
    data = resolve(data)
    saved = data['plan']['profile_snapshot']
    if saved.pop('content_ref', None):
        saved['content'] = original_content
    return data


def test_roundtrip_preserves_scoped_boards_audio_rights_and_unknown_fields():
    ctx = fixture_context()
    original = deepcopy(ctx.creative_data())
    fingerprint = ctx.fingerprint
    view = ctx.model_data()
    assert expand(view, ctx.plan['profile_snapshot']['content']) == original
    assert ctx.creative_data() == original and ctx.fingerprint == fingerprint
    assert view == ctx.model_data()
    assert len(json.dumps(view, ensure_ascii=False)) < len(json.dumps(original, ensure_ascii=False))
    assert view['task_view']['source_characters'] == len(json.dumps(original, ensure_ascii=False))
    assert len(view['task_view']['shared_constraints']) == 1
    for index in range(3):
        assert view['artifacts'][index]['metadata']['material_uses'][0]['timing_basis' if index else 'board_frame_index'] == original['artifacts'][index]['metadata']['material_uses'][0]['timing_basis' if index else 'board_frame_index']


def test_similar_but_different_material_restriction_is_not_folded():
    ctx = fixture_context()
    ctx.artifacts[1]['metadata']['use_constraints']['audio_restriction'] = '禁止使用原声'
    view = ctx.model_data()
    assert view['artifacts'][1]['metadata']['use_constraints']['audio_restriction'] == '禁止使用原声'
    assert expand(view, ctx.plan['profile_snapshot']['content']) == ctx.creative_data()


def test_different_profile_snapshot_is_not_replaced_with_current_profile():
    ctx = fixture_context()
    ctx.plan['profile_snapshot']['content'] = '{"identity":"另一版本"}'
    assert ctx.model_data()['plan']['profile_snapshot'] == ctx.plan['profile_snapshot']


def test_nonediting_context_and_identity_remain_unprojected():
    ctx = fixture_context()
    assert replace(ctx, editor_view=False).model_data() == ctx.creative_data()
    assert ctx.fingerprint == replace(ctx, editor_view=False).fingerprint


def test_runner_sends_view_but_authorizes_original_context_and_handles():
    ctx = fixture_context()
    runner, transport, authorized = run([{'content': '{"summary":"ok"}'}])
    asyncio.run(runner.run(ctx, 'edit', Answer, expression_role='visual'))
    sent = json.loads(transport.calls[0][1]['content'][0]['text'])
    assert sent['task_view']['version'] == 'editor-context-2'
    assert sent['allowed_handles'] == sorted(ctx.allowed_handles)
    assert authorized == ['task']
    assert expand(sent, ctx.plan['profile_snapshot']['content']) == json.loads(json.dumps(ctx.creative_data()))


def test_invalid_saved_policy_cannot_enable_view():
    ctx = fixture_context()
    ctx.expression_policy['rules']['core'] = 'tampered'
    from easel.production.errors import ProductionError
    with pytest.raises(ProductionError):
        ctx.model_data()


@pytest.mark.parametrize('unknown', [False, True])
def test_current_editor_operation_replays_or_waits_without_resending(tmp_path, unknown):
    from types import SimpleNamespace
    from easel.production.operations import OperationService
    from easel.production.store import Store
    from easel.production.model_operations import RecordedModelTransport
    from easel.production.model_tasks import ModelTaskRunner, ModelTaskError
    from .test_operations import owned_request
    store = Store(tmp_path / 'offline.sqlite'); store.initialize()
    spec = owned_request(store, kind='MODEL')
    ops = OperationService(store, clock=lambda: 1000)
    binding = SimpleNamespace(**{k: spec[k] for k in ('work_id', 'run_id', 'task_id', 'owner_epoch')}, plan_revision=1)
    identity = {k: spec[k] for k in ('provider', 'model', 'mode')}
    context = replace(fixture_context(), work_id=spec['work_id'], run_id=spec['run_id'],
                      task_id=spec['task_id'], editor_view=True)
    class Provider:
        capabilities = frozenset({'text', 'structured'})
        calls = 0
        async def complete(self, messages, tools, schema):
            self.calls += 1
            if unknown:
                raise TimeoutError('synthetic interruption')
            return {'content': '{"summary":"saved"}'}
    provider = Provider()
    async def authorize(ctx):
        pass
    def execute(ctx):
        transport = RecordedModelTransport(provider, ops, binding, identity, 'fixture-1')
        return asyncio.run(ModelTaskRunner(transport, authorize).run(ctx, 'edit', Answer, expression_role='visual'))
    if unknown:
        with pytest.raises(TimeoutError): execute(context)
    else:
        assert execute(context).summary == 'saved'
    with store.connection() as conn:
        before = dict(conn.execute('SELECT * FROM operations').fetchone())
    if unknown:
        with pytest.raises(ModelTaskError) as caught: execute(context)
        assert caught.value.code == 'result_unknown'
    else:
        assert execute(context).summary == 'saved'
    with store.connection() as conn:
        after = dict(conn.execute('SELECT * FROM operations').fetchone())
    assert provider.calls == 1
    assert before == after


def test_director_reference_only_deduplicates_equal_known_constraints():
    ctx = fixture_context()
    ctx.artifacts[1]['metadata']['use_constraints']['director']['narrative'] = '不同版本必须保留'
    ctx.artifacts[2]['metadata']['future_director'] = deepcopy(ctx.director)
    view = ctx.model_data()
    assert view['artifacts'][1]['metadata']['use_constraints']['director']['narrative'] == '不同版本必须保留'
    assert view['artifacts'][2]['metadata']['future_director'] == ctx.director
    assert next(iter(view['task_view']['shared_constraints'].values()))['director'] == {'context_ref': '/director'}
    assert expand(view, ctx.plan['profile_snapshot']['content']) == ctx.creative_data()


@pytest.mark.parametrize('version', ['natural-expression-2', 'natural-expression-3', 'future-version'])
def test_unsupported_policy_stops_before_model_authorization(version):
    from easel.production.errors import ProductionError
    ctx = fixture_context()
    ctx.expression_policy['version'] = version
    ctx.expression_policy['digest'] = _digest(version, ctx.expression_policy['rules'])
    runner, transport, authorized = run([])
    with pytest.raises(ProductionError) as caught:
        asyncio.run(runner.run(ctx, 'edit', Answer, expression_role='visual'))
    assert caught.value.code == 'expression_policy_unsupported'
    assert transport.calls == [] and authorized == []
