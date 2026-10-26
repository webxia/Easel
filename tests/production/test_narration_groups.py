"""Confirmed semantic groups: transport/cache/timing correctness, not listening QA."""
import asyncio
from copy import deepcopy
import json
import io
import wave
from types import SimpleNamespace

import httpx
import pytest
from pydantic import ValidationError

from easel.production.contracts import NarrationPolicy, PlanDocument, VoiceIdentity, fingerprint
from easel.production.errors import ProductionError
from easel.production.model_tasks import ModelTaskError
from easel.production.narration import (
    aligned_captions, measured_execution_plan, narration_segments, validate_narration_execution,
)
from easel.production.operations import OperationService
from easel.production.planning import CreativePlan, NarrationPlanChanges, VoiceReadyCreativePlan, merge_narration_changes
from easel.production.providers.minimax_speech import MiniMaxSpeechAdapter
from easel.production.store import Store
from easel.production.voice import (
    SpeechConfig, VoiceOption, VoiceService, effective_segment_voice, prepare_voice_segments,
)
from .test_operations import owned_request
from .test_voice_subtitles import wav_bytes


def voice(**parameters):
    return VoiceIdentity(provider='fixture', model='speech-2.8-turbo', engine='minimax-speech-v1',
                         voice_id='fixed', parameters=parameters)


def plan():
    scenes = [{'id': f's{i}', 'purpose': '解释', 'visual': '工作台', 'narration': text}
              for i, text in enumerate(['先看看问题。', '再解释原因。', '最后留个问题。'], 1)]
    return {'title': '分组测试', 'summary': '事实保持', 'script': '\n'.join(s['narration'] for s in scenes),
            'scenes': scenes, 'settings': {'duration_seconds': 30, 'audio_mode': 'mixed', 'voice': voice(speed=1).model_dump()},
            'narration_policy': {'continuous': True, 'duration_mode': 'voice_driven', 'groups': [
                {'id': 'opening', 'scene_ids': ['s1', 's2'], 'emotion': 'calm'},
                {'id': 'ending', 'scene_ids': ['s3']}]}}


def test_default_policy_and_legacy_segments_are_unchanged():
    assert NarrationPolicy().model_dump() == {'continuous': True, 'duration_mode': 'fixed'}
    value = plan()
    del value['narration_policy']['groups']
    segment = narration_segments(value)[0]
    ids = ['s1', 's2', 's3']
    assert segment['segment_id'] == 'narration-' + fingerprint([value['script'], ids])[:24]
    assert segment['text'] == value['script'] and 'emotion' not in segment
    saved = PlanDocument.model_validate(value).model_dump(mode='json')
    assert 'groups' not in saved['narration_policy']
    assert PlanDocument.model_validate(saved).model_dump(mode='json') == saved


def test_group_identity_is_stable_and_pauses_map_across_scenes():
    value = plan()
    value['scenes'][0]['narration_pauses'] = [{'after': 2, 'seconds': .2}]
    value['scenes'][1]['narration_pauses'] = [{'after': 2, 'seconds': .3}]
    original = narration_segments(value)
    assert original[0]['segment_id'] == 'narration-group-opening'
    assert original[0]['text'] == '先看看问题。\n再解释原因。'
    assert original[0]['pauses'] == [{'after': 2, 'seconds': .2}, {'after': 9, 'seconds': .3}]
    value['scenes'][0]['narration'] = '先把问题看清。'
    revised = narration_segments(value)
    assert revised[0]['segment_id'] == original[0]['segment_id']
    assert revised[0]['text_hash'] != original[0]['text_hash'] and revised[1] == original[1]


@pytest.mark.parametrize('groups', [
    [{'id': 'a', 'scene_ids': ['s1', 's2']}],
    [{'id': 'a', 'scene_ids': ['s1', 's1', 's2', 's3']}],
    [{'id': 'a', 'scene_ids': ['s2', 's1', 's3']}],
    [{'id': 'a', 'scene_ids': ['s1']}, {'id': 'a', 'scene_ids': ['s2', 's3']}],
    [{'id': 'a', 'scene_ids': ['s1', 's2', 'missing']}],
])
def test_groups_must_cover_spoken_scenes_once_in_order(groups):
    value = plan(); value['narration_policy']['groups'] = groups
    for contract in (PlanDocument, VoiceReadyCreativePlan):
        with pytest.raises(ValidationError):
            contract.model_validate(value)


def test_groups_require_continuous_voice_and_cannot_cross_original_audio():
    value = plan(); value['narration_policy']['continuous'] = False
    with pytest.raises(ValidationError):
        PlanDocument.model_validate(value)
    value = plan()
    value['scenes'].insert(1, {'id': 'original', 'purpose': '原声', 'visual': '现场', 'narration': '',
                             'required_input_ids': ['recording']})
    with pytest.raises(ModelTaskError, match='受保护原声'):
        narration_segments(value, {'recording'})


def test_group_limit_does_not_silently_split_and_wire_tags_count():
    value = plan(); value['scenes'][0]['narration'] = '字' * 4000
    assert len(narration_segments(value)) == 2  # 3000 is advice for explicit groups.
    value['scenes'][0]['narration'] = '字' * 10000
    with pytest.raises(ModelTaskError, match='10000'):
        narration_segments(value)
    value['scenes'][0]['narration'] = '字' * 9991  # plus newline + six-character s2 = 9998
    value['scenes'][0]['narration_pauses'] = [{'after': 2, 'seconds': .2}]
    with pytest.raises(ModelTaskError, match='停顿标签'):
        validate_narration_execution(value)


def test_native_9999_boundary_and_generic_limit_are_not_conflated(tmp_path):
    value = plan()
    value['scenes'] = [value['scenes'][0]]
    value['narration_policy']['groups'] = [{'id': 'only', 'scene_ids': ['s1']}]
    fixed = voice()
    config = SpeechConfig(provider=fixed.provider, model=fixed.model, engine=fixed.engine,
        base_url='https://speech.invalid/v1', config_version='fixture', voices=(VoiceOption(fixed, 'fixed'),))
    adapter = MiniMaxSpeechAdapter(config, tmp_path / 'native')
    value['scenes'][0]['narration'] = '字' * 9999
    assert len(validate_narration_execution(value)[0]['text']) == 9999
    adapter.request(identity=fixed, text=value['scenes'][0]['narration'], segment_id='only')
    value['scenes'][0]['narration'] += '字'
    with pytest.raises(ModelTaskError):validate_narration_execution(value)
    with pytest.raises(ProductionError):adapter.request(identity=fixed, text=value['scenes'][0]['narration'], segment_id='only')
    value['settings']['voice']['engine'] = 'speech-http-v1'
    assert len(validate_narration_execution(value)[0]['text']) == 10000


def test_combined_pause_limit_checked_before_confirmation():
    value = plan()
    value['scenes'] = [{'id': f's{i}', 'purpose': '解释', 'visual': '桌面', 'narration': '先看问题，再说原因。',
                       'narration_pauses': [{'after': j, 'seconds': .1} for j in (1, 2, 3, 4)]} for i in range(9)]
    value['script'] = '\n'.join(s['narration'] for s in value['scenes'])
    value['narration_policy'].pop('groups')
    with pytest.raises(ValidationError, match='有界'):
        VoiceReadyCreativePlan.model_validate(value)
    value['narration_policy']['groups'] = [
        {'id': 'a', 'scene_ids': [f's{i}' for i in range(5)]},
        {'id': 'b', 'scene_ids': [f's{i}' for i in range(5, 9)]}]
    assert len(VoiceReadyCreativePlan.model_validate(value).narration_policy.groups) == 2


def test_group_expression_preserves_voice_identity_and_explicit_settings():
    fixed = voice(speed=1, subtitle_enable=True)
    effective = effective_segment_voice(fixed, {'emotion': 'calm'})
    assert effective.model_dump(exclude={'parameters'}) == fixed.model_dump(exclude={'parameters'})
    assert effective.parameters == {'speed': 1, 'subtitle_enable': True, 'emotion': 'calm'}
    assert fixed.parameters == {'speed': 1, 'subtitle_enable': True}
    assert effective_segment_voice(fixed, {}) is fixed
    with pytest.raises(ProductionError, match='冲突'):
        effective_segment_voice(voice(emotion='happy'), {'emotion': 'calm'})
    with pytest.raises(ProductionError, match='不支持'):
        effective_segment_voice(fixed, {'emotion': 'whisper'})
    assert effective_segment_voice(fixed.model_copy(update={'model': 'speech-2.6-turbo'}),
                                   {'emotion': 'whisper'}).parameters['emotion'] == 'whisper'


def test_narration_delta_only_changes_existing_group_expression():
    base = CreativePlan.model_validate(plan()).model_dump(mode='json')
    policy = deepcopy(base['narration_policy']); policy['groups'][0]['emotion'] = 'happy'
    result = merge_narration_changes(NarrationPlanChanges.model_validate({'narration_policy': policy}), base)
    assert result.narration_policy.groups[0].emotion == 'happy'
    assert result.settings.model_dump() == base['settings']
    policy['groups'] = [{'id': 'all', 'scene_ids': ['s1', 's2', 's3']}]
    with pytest.raises(ValueError, match='重新分组'):
        merge_narration_changes(NarrationPlanChanges.model_validate({'narration_policy': policy}), base)


def test_worker_freezes_groups_in_confirmable_plan(tmp_path):
    from easel.production.planning import PlanningTasks
    from easel.production.service import WorkService
    from easel.production.worker import Worker
    from .test_planning_runtime import Transport
    store = Store(tmp_path / 'outputs' / 'production.sqlite3'); store.initialize()
    service = WorkService(store, outputs=tmp_path / 'outputs', profiles=tmp_path / 'profiles')
    answer = plan()
    work = service.command('create', {'title': answer['title'], 'input_text': '只说明同一个问题',
        'settings': answer['settings']}, command_id='create')['work_id']
    model = {'provider': 'direct-api', 'model': 'fixture', 'mode': 'structured'}
    service.command('plan', {'services': [model]}, work_id=work, expected_revision=1, command_id='plan')
    transport = Transport(answer)
    planning = PlanningTasks(service, OperationService(store), transport, model, 'fixture-v1')
    asyncio.run(Worker(store, {'plan': planning.plan}).run_once())
    snapshot = service.snapshot(work)
    assert snapshot['state'] == 'awaiting_confirmation', snapshot['tasks'][0]['error_json']
    frozen = snapshot['plans'][0]['plan']
    assert frozen['narration_policy']['groups'][0] == answer['narration_policy']['groups'][0]
    assert frozen['narration_policy']['groups'][1]['scene_ids'] == ['s3']
    assert frozen['settings']['voice'] == answer['settings']['voice']
    assert not snapshot['plans'][0]['confirmed_at']


def service_env(tmp_path, *, timeout=False, aligned=False):
    store = Store(tmp_path / 'production.sqlite3'); store.initialize()
    spec = owned_request(store, kind='VOICE', limit=0)
    with store.transaction() as conn:
        conn.execute('UPDATE authorization_grants SET services_json=? WHERE id=?',
                     (json.dumps([{'provider': 'fixture', 'model': 'speech-2.8-turbo', 'mode': 'normal'}]), spec['grant_id']))
    ops = OperationService(store, clock=lambda: 1000)
    calls = []
    timings = {}
    def transport(request):
        if request.method == 'GET':
            return httpx.Response(200, json=timings[str(request.url)])
        calls.append(json.loads(request.content))
        if timeout:
            raise httpx.ReadTimeout('fixture timeout')
        data = {'status': 2, 'audio': wav_bytes().hex()}
        if aligned:
            factor = 2 if '改过' in calls[-1]['text'] else 1
            with wave.open(io.BytesIO(wav_bytes()), 'rb') as original:
                buffer = io.BytesIO()
                with wave.open(buffer, 'wb') as output:
                    output.setparams(original.getparams())
                    output.writeframes(original.readframes(original.getnframes()) * factor)
            data['audio'] = buffer.getvalue().hex()
            data['subtitle_file'] = f'https://cdn.minimax.chat/alignment/{len(calls)}'
            timings[data['subtitle_file']] = [{'text': calls[-1]['text'], 'time_begin': 0, 'time_end': 200 * factor}]
        return httpx.Response(200, json={'base_resp': {'status_code': 0}, 'data': data})
    fixed = voice(**({'speed': 1, 'subtitle_enable': True} if aligned else {'speed': 1}))
    config = SpeechConfig(provider=fixed.provider, model=fixed.model, engine=fixed.engine,
        base_url='https://speech.invalid/v1', config_version='fixture', mode='normal',
        voices=(VoiceOption(fixed, 'fixed', speed_range=(.5, 2)),))
    adapter = MiniMaxSpeechAdapter(config, tmp_path / 'receipts', transport=httpx.MockTransport(transport))
    service = VoiceService(ops, tmp_path / 'cache', [adapter])
    ctx = SimpleNamespace(**{key: spec[key] for key in ('work_id', 'run_id', 'task_id', 'owner_epoch')},
                          store=store, transaction=store.transaction, assert_current=lambda: None)
    return service, ctx, spec['grant_id'], fixed, calls


def test_voice_tasks_new_task_records_exclude_old_groups_and_retime_cached_audio(tmp_path):
    from easel.production.voice_tasks import VoiceTasks
    service, ctx, grant, fixed, calls = service_env(tmp_path, aligned=True)
    ctx.plan_revision = 1
    tasks = VoiceTasks(SimpleNamespace(store=ctx.store, outputs=tmp_path), lambda: service, settings_provider=lambda: {})
    value = plan(); value['settings']['voice'] = fixed.model_dump()
    value['settings']['subtitles'] = {'enabled': False}
    first_ids, outcome = asyncio.run(tasks.prepare_assets(ctx, value, []))
    assert outcome is None and len(calls) == 2
    with ctx.store.connection() as conn:
        first = [dict(conn.execute('SELECT * FROM artifacts WHERE id=?', (id,)).fetchone()) for id in first_ids]
    _, first_timing = measured_execution_plan(value, first)
    # A new production task inherits selected library media, never old TTS
    # handles (the supply boundary filters for asset_ref). Seed offline media.
    with ctx.store.transaction() as conn:
        for identifier, metadata in [('music', {'role': 'music', 'duration': 2}),
                ('sfx', {'role': 'sfx', 'duration': .2, 'material_uses': [{'role': 'sfx', 'timing_basis': 'scene', 'scene_id': 's3'}]})]:
            record = {**first[0], 'id': identifier, 'operation_id': None,
                      'metadata_json': json.dumps({'schema_version': 1, **metadata})}
            conn.execute('INSERT INTO artifacts (' + ','.join(record) + ') VALUES (' + ','.join('?' for _ in record) + ')', tuple(record.values()))
        previous = dict(conn.execute('SELECT * FROM tasks WHERE id=?', (ctx.task_id,)).fetchone())
        previous['id'] = 'new-edit-task'
        conn.execute('INSERT INTO tasks (' + ','.join(previous) + ') VALUES (' + ','.join('?' for _ in previous) + ')', tuple(previous.values()))
    ctx.task_id = 'new-edit-task'
    value['scenes'][0]['narration'] = '这是改过的第一段。'
    ids, outcome = asyncio.run(tasks.prepare_assets(ctx, value, ['music', 'sfx']))
    assert outcome is None and len(calls) == 3
    assert not set(ids).intersection(first_ids)
    with ctx.store.connection() as conn:
        records = [dict(conn.execute('SELECT * FROM artifacts WHERE id=?', (id,)).fetchone()) for id in ids]
    voices = [r for r in records if json.loads(r['metadata_json']).get('role') == 'voice']
    assert len(voices) == 2
    assert {json.loads(r['metadata_json'])['segment_id'] for r in voices} == {'narration-group-opening', 'narration-group-ending'}
    assert voices[1]['digest'] == first[1]['digest'] and voices[1]['operation_id'] == first[1]['operation_id']
    assert voices[0]['operation_id'] != first[0]['operation_id']
    _, timing = measured_execution_plan(value, records)
    clips = [SimpleNamespace(asset_id=r['id'], role='voice', at=s['at'], duration=s['duration'])
             for r, s in zip(voices, timing['voice_schedule'])]
    captions = aligned_captions(clips, records)
    assert captions[1]['start'] == pytest.approx(first_timing['voice_schedule'][1]['at'] + .2)
    assert [r['id'] for r in records[:2]] == ['music', 'sfx']
    assert all(json.loads(r['metadata_json']).get('role') != 'voice' for r in records[:2])


def test_real_cache_and_transport_reuse_only_unchanged_group(tmp_path):
    service, ctx, grant, fixed, calls = service_env(tmp_path)
    value = plan()
    def produce():
        return asyncio.run(prepare_voice_segments(ctx, service=service, outputs=tmp_path, identity=fixed,
                           grant_id=grant, segments=narration_segments(value)))
    first = produce()
    assert first['state'] == 'succeeded' and len(calls) == 2
    assert calls[0]['voice_setting'] == {'voice_id': 'fixed', 'speed': 1, 'vol': 1, 'pitch': 0, 'emotion': 'calm'}
    assert 'emotion' not in calls[1]['voice_setting']
    value['scenes'][0]['narration'] = '把问题再看清一点。'
    second = produce()
    assert second['state'] == 'succeeded' and len(calls) == 3
    assert not second['segments'][0]['reused'] and second['segments'][1]['reused']
    assert second['segments'][1]['asset'] == first['segments'][1]['asset']
    value['narration_policy']['groups'][0]['emotion'] = 'happy'
    third = produce()
    assert third['state'] == 'succeeded' and len(calls) == 4
    assert calls[-1]['voice_setting']['emotion'] == 'happy'
    assert third['segments'][1]['asset'] == first['segments'][1]['asset']
    assert fixed.parameters == {'speed': 1}


def test_unknown_group_is_not_resent_or_skipped(tmp_path):
    service, ctx, grant, fixed, calls = service_env(tmp_path, timeout=True)
    for _ in range(2):
        result = asyncio.run(prepare_voice_segments(ctx, service=service, outputs=tmp_path, identity=fixed,
                             grant_id=grant, segments=narration_segments(plan())))
        assert result['state'] == 'unknown' and result['segments'] == []
    assert len(calls) == 1


def test_revised_group_durations_move_subtitles_without_touching_music_or_sources():
    value = plan(); segments = narration_segments(value)
    def records(durations):
        return [{'id': s['segment_id'], 'metadata_json': json.dumps({'role': 'voice', 'segment_id': s['segment_id'],
                 'duration': duration, 'narration_text': s['text'], 'timing': {'provider_alignment': {
                 'status': 'received', 'segments': [{'text': s['text'], 'start': 0, 'end': duration}]}}})}
                for s, duration in zip(segments, durations)] + [
                    {'id': 'music', 'metadata_json': json.dumps({'role': 'music', 'duration': 30})},
                    {'id': 'sfx', 'metadata_json': json.dumps({'role': 'sfx', 'duration': 1,
                     'material_uses': [{'role': 'sfx', 'timing_basis': 'scene', 'scene_id': 's3'}]})}]
    before = deepcopy(value); assets = records([4, 2]); original_assets = deepcopy(assets)
    _, timing = measured_execution_plan(value, assets)
    revised = records([6, 2]); _, later = measured_execution_plan(value, revised)
    clips = [SimpleNamespace(asset_id=s['segment_id'], role='voice', at=s['at'], duration=s['duration'])
             for s in later['voice_schedule']]
    captions = aligned_captions(clips, revised)
    assert later['voice_schedule'][1]['at'] == timing['voice_schedule'][1]['at'] + 2
    assert captions[1]['start'] == later['voice_schedule'][1]['at']
    assert value == before and assets == original_assets and revised[-2:] == assets[-2:]
