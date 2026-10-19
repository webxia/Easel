"""Regressions from a real autonomous film: broken prosody, dead air, SD stock."""
import asyncio
from copy import deepcopy
import io
import json
from types import SimpleNamespace

import httpx
import pytest
from pydantic import BaseModel

from easel.production.context import TaskContext
from easel.production.model_tasks import ModelTaskRunner
from easel.production.narration import narration_segments, measured_execution_plan, check_voice_schedule, aligned_captions
from easel.production.voice import sentence_segments, SpeechConfig, VoiceOption
from easel.production.contracts import VoiceIdentity
from easel.production.providers.minimax_speech import MiniMaxSpeechAdapter
from easel.production.providers.stock import PexelsStockProvider
from easel.materials.domain import MediaType
from .test_voice_subtitles import wav_bytes
from .test_voice_subtitles import speech


def sample():
    return {'settings': {'duration_seconds': 105}, 'scenes': [
        {'id': 's1', 'narration': 'AI做完了。真的会了吗？', 'duration_seconds': 50},
        {'id': 's2', 'narration': '换个条件，自己试一次。', 'duration_seconds': 55}],
        'narration_policy': {'continuous': True, 'duration_mode': 'voice_driven'}}


def record(plan, duration=51.827126, alignment=None):
    s = narration_segments(plan)[0]
    return {'id': 'voice-a', 'metadata_json': json.dumps({
        'role': 'voice', 'segment_id': s['segment_id'], 'duration': duration,
        'narration_text': s['text'], 'timing': {'provider_alignment': alignment or {}}})}


def clip(**kw):
    return SimpleNamespace(**{'asset_id': 'voice-a', 'role': 'voice', 'at': .2,
                             'duration': 51.827126, 'source_start': 0, 'gain': 1, **kw})


def test_continuous_text_preserved_and_legacy_ids_not_migrated():
    p = sample()
    group = narration_segments(p)
    assert len(group) == 1 and group[0]['text'] == 'AI做完了。真的会了吗？\n换个条件，自己试一次。'
    assert group[0]['scene_ids'] == ['s1', 's2']
    p.pop('narration_policy')
    assert [s['segment_id'] for s in narration_segments(p)] == [
        scene['id'] + '-' + part['segment_id'] for scene in p['scenes']
        for part in sentence_segments(scene['narration'])]
    p['scenes'][0]['required_input_ids'] = ['protected-original']
    assert all(s['scene_id'] == 's2' for s in narration_segments(p, {'protected-original'}))


def test_actual_speech_drives_opt_in_duration_without_mutating_frozen_plan():
    p = sample(); before = deepcopy(p)
    measured, receipt = measured_execution_plan(p, [record(p)])
    assert measured['settings']['duration_seconds'] == pytest.approx(52.833333333)
    assert p == before and receipt['draft_duration'] == 105
    assert all(s['duration_seconds'] is None for s in measured['scenes'])
    check_voice_schedule([clip()], [record(p)], receipt)
    for bad in [clip(at=8), clip(duration=30), clip(gain=0), clip(source_start=1)]:
        with pytest.raises(ValueError):
            check_voice_schedule([bad], [record(p)], receipt)
    p['narration_policy']['duration_mode'] = 'fixed'
    assert measured_execution_plan(p, [record(p)]) == (p, None)


def test_provider_captions_need_complete_literal_text_and_real_timing():
    p = sample(); text = narration_segments(p)[0]['text']
    aligned = {'status': 'received', 'segments': [{'text': text, 'start': .1, 'end': 5}]}
    assert aligned_captions([clip()], [record(p, alignment=aligned)])[0]['start'] == pytest.approx(.3)
    aligned['segments'][0]['text'] = '模型臆造字幕'
    assert aligned_captions([clip()], [record(p, alignment=aligned)]) is None
    assert aligned_captions([clip()], [record(p)]) is None


def test_unknown_input_list_repairs_inside_same_native_model_task():
    class Scene(BaseModel):
        required_input_ids: list[str]
    class Transport:
        capabilities = frozenset({'text', 'structured'})
        def __init__(self): self.calls = []
        async def complete(self, messages, *args):
            self.calls.append(deepcopy(messages))
            return {'content': json.dumps({'required_input_ids': ['brief'] if len(self.calls) == 1 else []})}
    t = Transport()
    async def authorized(_): pass
    result = asyncio.run(ModelTaskRunner(t, authorized).run(TaskContext('w', 'r', 't'), 'plan', Scene))
    assert result.required_input_ids == [] and len(t.calls) == 2
    assert 'required_input_ids' in t.calls[1][-1]['content']


def test_autonomous_worker_reviews_draft_and_freezes_measured_policy(tmp_path):
    from easel.production.store import Store
    from easel.production.service import WorkService
    from easel.production.operations import OperationService
    from easel.production.planning import PlanningTasks
    from easel.production.worker import Worker
    store = Store(tmp_path / 'db'); store.initialize()
    service = WorkService(store, outputs=tmp_path / 'outputs', profiles=tmp_path / 'profiles')
    voice = {'provider': 'fixture', 'model': 'speech', 'engine': 'fixture', 'voice_id': 'fixed'}
    settings = {'audio_mode': 'voice', 'voice': voice, 'aspect_ratio': '16:9'}
    work = service.command('create', {'title': 'autonomous', 'input_text': '做完等于学会吗？',
                                      'settings': settings}, command_id='create')['work_id']
    identity = {'provider': 'direct-api', 'model': 'fixture', 'mode': 'structured'}
    service.command('plan', {'services': [identity]}, command_id='plan', work_id=work, expected_revision=1)
    answer = {'title': '学习', 'summary': '一个假设例子', 'script': '说明逻辑',
              'settings': {**settings, 'duration_seconds': 20},
              'scenes': [{'id': 's1', 'purpose': '解释', 'visual': '翻阅笔记', 'duration_seconds': 20,
                          'narration': '假设换一个条件，你还能自己解释吗？', 'required_input_ids': []}]}
    class Transport:
        capabilities = frozenset({'text', 'structured'})
        def __init__(self): self.calls = []
        async def complete(self, messages, *args):
            self.calls.append(deepcopy(messages))
            return {'content': json.dumps(answer)}
    transport = Transport()
    planning = PlanningTasks(service, OperationService(store), transport, identity, 'fixture')
    worker = Worker(store, {'plan': planning.plan})
    assert asyncio.run(worker.run_once())
    snap = service.snapshot(work)
    assert snap['state'] == 'awaiting_confirmation' and len(transport.calls) == 2
    assert snap['plans'][0]['plan']['narration_policy'] == {'continuous': True, 'duration_mode': 'voice_driven'}
    context = json.loads(transport.calls[1][1]['content'][0]['text'])
    assert context['plan']['scenes'][0]['narration'] == answer['scenes'][0]['narration']
    assert context['production_capabilities']['unavailable']
    with store.connection() as conn:
        assert conn.execute("SELECT count(*) FROM operations WHERE state='succeeded'").fetchone()[0] == 2


@pytest.mark.parametrize('url', ['https://evil.example/subtitle', 'https://minimax.chat:invalid/file', 'https://[invalid/file'])
def test_subtitle_failure_preserves_received_audio_without_retry(tmp_path, url):
    identity = VoiceIdentity(provider='minimax', model='speech-2.8-turbo', engine='minimax-speech-v1',
                             voice_id='fixed', parameters={'subtitle_enable': True})
    config = SpeechConfig(provider=identity.provider, model=identity.model, engine=identity.engine,
        base_url='https://speech.invalid/v1', config_version='test', voices=(VoiceOption(identity, 'fixed'),))
    calls = []
    adapter = MiniMaxSpeechAdapter(config, tmp_path, transport=httpx.MockTransport(lambda req: calls.append(req)))
    response = httpx.Response(200, json={'base_resp': {'status_code': 0},
        'data': {'status': 2, 'audio': wav_bytes().hex(), 'subtitle_file': url}})
    stream = io.BytesIO()
    alignment = adapter._write_audio(response, stream)
    assert stream.getvalue() == wav_bytes() and alignment['status'] == 'unavailable' and calls == []


def test_native_subtitle_wire_and_millisecond_alignment(tmp_path):
    identity = VoiceIdentity(provider='minimax', model='speech-2.8-turbo', engine='minimax-speech-v1',
                             voice_id='fixed', parameters={'subtitle_enable': True})
    config = SpeechConfig(provider=identity.provider, model=identity.model, engine=identity.engine,
        base_url='https://speech.invalid/v1', config_version='test', voices=(VoiceOption(identity, 'fixed'),))
    def handler(req):
        assert req.method == 'GET' and 'authorization' not in req.headers
        return httpx.Response(200, json=[{'text': '一句话。', 'time_begin': 100, 'time_end': 1500}])
    adapter = MiniMaxSpeechAdapter(config, tmp_path, transport=httpx.MockTransport(handler))
    request = adapter.request(identity=identity, text='一句话。', segment_id='one')
    assert adapter._wire_request(request, identity)[1]['subtitle_enable'] is True
    assert adapter._alignment('https://cdn.minimax.chat/subtitle')['segments'] == [
        {'text': '一句话。', 'start': .1, 'end': 1.5}]
    from easel.production.errors import ProductionError
    with pytest.raises(ProductionError):
        adapter.option(identity.model_copy(update={'parameters': {'emotion': 'whisper'}}))


def test_subtitle_policy_reconciliation_reuses_paid_audio_without_exposing_signed_locator(speech,tmp_path):
    from easel.production.voice import VoiceService,VoiceBinding
    _,ops,binding,identity,_,_,_=speech
    identity=identity.model_copy(update={'engine':'minimax-speech-v1','parameters':{'subtitle_enable':True}})
    config=SpeechConfig(provider=identity.provider,model=identity.model,engine=identity.engine,
        base_url='https://speech.invalid/v1',config_version='subtitle-reconcile',voices=(VoiceOption(identity,'fixed'),),mode='normal')
    calls=[]
    def handler(req):
        calls.append(req.method)
        if req.method=='POST':return httpx.Response(200,json={'base_resp':{'status_code':0},
            'data':{'status':2,'audio':wav_bytes().hex(),'subtitle_file':'https://cdn.reviewed.example/subtitle?signed=private'}})
        assert 'authorization' not in req.headers
        return httpx.Response(200,json=[{'text':'原句。','time_begin':0,'time_end':200}])
    adapter=MiniMaxSpeechAdapter(config,tmp_path/'native',transport=httpx.MockTransport(handler))
    service=VoiceService(ops,tmp_path/'cache',[adapter])
    first=service.synthesize(binding,identity=identity,text='原句。',segment_id='one')
    assert first['state']=='succeeded' and calls==['POST']
    assert 'signed=' not in json.dumps(first)
    adapter.subtitle_hosts=(*adapter.subtitle_hosts,'cdn.reviewed.example')
    second=service.synthesize(VoiceBinding(**{**binding.__dict__,'operation_id':'another-location'}),
        identity=identity,text='原句。',segment_id='two')
    assert second['reused'] and calls==['POST','GET']
    assert second['asset']['sha256']==first['asset']['sha256']
    assert second['asset']['alignment']['status']=='received'
    assert 'signed=' not in json.dumps(second)


def test_stock_search_prefers_full_hd_over_first_sd_or_unnecessary_4k():
    def handler(req):
        return httpx.Response(200, json={'videos': [{'id': 1, 'url': 'https://www.pexels.com/video/1/',
            'user': {'name': 'Artist'}, 'video_files': [
                {'file_type': 'video/mp4', 'width': w, 'height': h,
                 'link': 'https://videos.pexels.com/' + name + '.mp4'}
                for w, h, name in [(640, 360, 'sd'), (3840, 2160, '4k'), (1920, 1080, 'hd')]]}]})
    provider = PexelsStockProvider('fixture', transport=httpx.MockTransport(handler))
    result = provider.search('learning', media_type=MediaType.VIDEO, limit=1)
    assert result[0].download_url == 'https://videos.pexels.com/hd.mp4'
