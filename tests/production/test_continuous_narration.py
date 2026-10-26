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
    fixed, timing = measured_execution_plan(p, [record(p)])
    assert fixed == p and timing['placement'] == 'advisory'
    assert timing['duration'] == 105


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


@pytest.mark.parametrize('explicit_duration', [False, True])
@pytest.mark.parametrize('audio_mode', ['voice', 'mixed'])
@pytest.mark.parametrize('review_verdict',['pass','fail'])
def test_autonomous_worker_reviews_draft_and_freezes_measured_policy(tmp_path,review_verdict,audio_mode,explicit_duration):
    from easel.production.store import Store
    from easel.production.service import WorkService
    from easel.production.operations import OperationService
    from easel.production.planning import PlanningTasks
    from easel.production.worker import Worker
    store = Store(tmp_path / 'db'); store.initialize()
    service = WorkService(store, outputs=tmp_path / 'outputs', profiles=tmp_path / 'profiles')
    voice = {'provider': 'fixture', 'model': 'speech', 'engine': 'fixture', 'voice_id': 'fixed'}
    settings = {'audio_mode': audio_mode, 'voice': voice, 'aspect_ratio': '16:9'}
    if explicit_duration:
        settings['duration_seconds'] = 20
    work = service.command('create', {'title': 'autonomous', 'input_text': '做完等于学会吗？',
                                      'settings': settings}, command_id='create')['work_id']
    identity = {'provider': 'direct-api', 'model': 'fixture', 'mode': 'structured'}
    service.command('plan', {'services': [identity]}, command_id='plan', work_id=work, expected_revision=1)
    answer = {'title': '学习', 'summary': '一个假设例子，长度随完整旁白', 'script': '假设换一个条件，你还能自己解释吗？',
              'narration_policy': {'continuous': True, 'duration_mode': 'voice_driven'},
              'settings': {**settings, 'duration_seconds': 20},
              'scenes': [{'id': 's1', 'purpose': '解释', 'visual': '翻阅笔记', 'duration_seconds': 20,
                          'narration': '假设换一个条件，你还能自己解释吗？', 'required_input_ids': []}]}
    class Transport:
        capabilities = frozenset({'text', 'structured'})
        def __init__(self): self.calls = []
        async def complete(self, messages, tools, schema):
            self.calls.append(deepcopy(messages))
            value = {'verdict':review_verdict,'findings':[],'observations':['fixture text review'],'suggestions':['可选表达优化'],'limitations':['尚未生成素材，效果未知']} if schema['title']=='DraftReview' else answer
            return {'content': json.dumps(value)}
    transport = Transport()
    planning = PlanningTasks(service, OperationService(store), transport, identity, 'fixture')
    worker = Worker(store, {'plan': planning.plan})
    assert asyncio.run(worker.run_once())
    snap = service.snapshot(work)
    assert snap['state'] == 'awaiting_confirmation' and len(transport.calls) == 2
    assert snap['plans'][0]['plan']['narration_policy'] == {'continuous': True, 'duration_mode': 'fixed' if explicit_duration else 'voice_driven'}
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


def test_actual_native_subtitle_cdn_is_admitted_without_credentials(tmp_path):
    identity = VoiceIdentity(provider='minimax', model='speech-2.8-turbo', engine='minimax-speech-v1', voice_id='fixed')
    config = SpeechConfig(provider=identity.provider, model=identity.model, engine=identity.engine,
        base_url='https://speech.invalid/v1', config_version='cdn', voices=(VoiceOption(identity, 'fixed'),))
    calls=[]
    def handler(req):
        calls.append(req)
        assert req.method=='GET' and 'authorization' not in req.headers
        return httpx.Response(200,json=[{'text':'原句。','time_begin':0,'time_end':1200}])
    adapter=MiniMaxSpeechAdapter(config,tmp_path,transport=httpx.MockTransport(handler))
    host='minimax-algeng-chat-tts.oss-cn-wulanchabu.aliyuncs.com'
    assert adapter._alignment('https://'+host+'/sub')['status']=='received'
    assert adapter._alignment('https://'+host+'.evil.example/sub')['status']=='unavailable'
    assert len(calls)==1


def test_local_alignment_groups_original_tokens_and_reports_estimates(tmp_path,monkeypatch):
    import faster_whisper, faster_whisper.audio
    import numpy as np
    from easel.production.speech_alignment import align_confirmed_speech
    calls=[]
    class Local:
        def __init__(self,name,**kw):
            calls.append(kw);assert name=='base' and kw['local_files_only'] is True
            from tokenizers import Tokenizer, models
            self.hf_tokenizer=Tokenizer(models.WordLevel({'<unk>':0},unk_token='<unk>'))
            self.model=SimpleNamespace(is_multilingual=True)
        def feature_extractor(self,audio):return np.zeros((80,100))
        def encode(self,features):return features
        def find_alignment(self,*a):
            return [[{'word':'原句','start':0,'end':.7},{'word':'，','start':.7,'end':.8},
                     {'word':'不改','start':.8,'end':1.2},{'word':'。','start':1.2,'end':1.3}]]
    monkeypatch.setattr(faster_whisper,'WhisperModel',Local)
    monkeypatch.setattr(faster_whisper.audio,'decode_audio',lambda *a,**kw:np.zeros(32000))
    monkeypatch.setattr('faster_whisper.tokenizer.Tokenizer',lambda *a,**kw:SimpleNamespace(encode=lambda text:[1]))
    path=tmp_path/'audio';path.write_bytes(b'unchanged')
    provider={'status':'received','segments':[{'text':'原句，不改。','start':.2,'end':1.8}]}
    result=align_confirmed_speech(path,'原句，不改。',provider,model_name='base',cache=tmp_path/'cache')
    assert result['status']=='received' and result['precision']=='estimated'
    assert len(result['segments'])==2
    assert ''.join(s['text'] for s in result['segments'])=='原句，不改。'
    assert result['segments'][0]['start']==pytest.approx(.2)
    assert path.read_bytes()==b'unchanged'
    assert align_confirmed_speech(path,'原句，不改。',provider,model_name='base',cache=tmp_path/'cache')==result
    assert len(calls)==1
    assert align_confirmed_speech(path,'其他文字',provider,model_name='base',cache=tmp_path/'cache')['status']=='unavailable'
    p=sample(); local={**result,'segments':[{'text':narration_segments(p)[0]['text'],'start':.4,'end':4}]}
    r=record(p,alignment={'status':'received','segments':[{'text':narration_segments(p)[0]['text'],'start':0,'end':8}]})
    meta=json.loads(r['metadata_json']);meta['timing']['local_alignment']=local;r['metadata_json']=json.dumps(meta)
    assert aligned_captions([clip()],[r])[0]['start']==pytest.approx(.6)


def test_draft_auditor_cannot_approve_changed_fixed_voice(tmp_path):
    from easel.production.store import Store
    from easel.production.service import WorkService
    from easel.production.operations import OperationService
    from easel.production.planning import PlanningTasks
    from easel.production.worker import Worker
    store=Store(tmp_path/'db');store.initialize();service=WorkService(store,outputs=tmp_path/'outputs',profiles=tmp_path/'profiles')
    voice={'provider':'fixture','model':'speech','engine':'fixture','voice_id':'fixed'}
    settings={'audio_mode':'voice','voice':voice,'aspect_ratio':'16:9'}
    work=service.command('create',{'title':'idea','input_text':'一个问题','settings':settings},command_id='create')['work_id']
    model_id={'provider':'direct-api','model':'fixture','mode':'structured'}
    service.command('plan',{'services':[model_id]},work_id=work,expected_revision=1,command_id='plan')
    answer={'title':'问题','summary':'假设例子','script':'先看条件，再一起解释。','settings':{**settings,'duration_seconds':20},
        'scenes':[{'id':'s1','purpose':'解释','visual':'真实场景','duration_seconds':20,'narration':'先看条件，再一起解释。'}]}
    class Model:
        capabilities=frozenset({'text','structured'})
        authors=0
        async def complete(self,messages,tools,schema):
            if schema['title']=='DraftReview':return {'content':json.dumps({'verdict':'pass'})}
            self.authors+=1;value=deepcopy(answer)
            if self.authors==1:value['settings']['voice']={**voice,'voice_id':'unrequested'}
            return {'content':json.dumps(value)}
    model=Model();planning=PlanningTasks(service,OperationService(store),model,model_id,'fixture')
    asyncio.run(Worker(store,{'plan':planning.plan}).run_once());snap=service.snapshot(work)
    assert snap['state']=='awaiting_confirmation' and model.authors==2
    assert snap['plans'][0]['plan']['settings']['voice']['voice_id']=='fixed'


def test_confirmed_ending_trims_tail_not_speech_or_caption():
    from easel.production.editors import EditProject, Scene, AudioClip, Caption, EditError
    from easel.production.narration import trim_confirmed_ending
    p=EditProject(work_id='w',plan_revision=1,revision=3,duration=30,audio_mode='mixed',
        scenes=(Scene(scene_id='s',asset_id='v',duration=30,fade_out=.6),),
        audio=(AudioClip(clip_id='voice',asset_id='a',role='voice',at=.2,duration=24.984),
               AudioClip(clip_id='bgm',asset_id='b',role='music',at=0,duration=30,gain=.22,fade_out=1.2)),
        captions=(Caption(caption_id='c',font_asset_id='f',text='结尾',start=21,end=25.25),))
    r=trim_confirmed_ending(p,26)
    assert r.duration==26 and r.scenes[-1].duration==26
    assert r.audio[0]==p.audio[0] and r.captions==p.captions
    assert r.audio[1].duration==26 and r.audio[1].gain==.22
    assert p.duration==30 and r.revision==4
    for bad in (25,30,31,True,float('nan'),26.01):
        with pytest.raises(EditError):trim_confirmed_ending(p,bad)


def test_confirmed_ending_accounts_for_overlap_and_protects_source_audio():
    from easel.production.editors import EditProject, Scene, EditError
    from easel.production.narration import trim_confirmed_ending
    p=EditProject(work_id='w',plan_revision=1,revision=1,duration=30,
        scenes=(Scene(scene_id='a',asset_id='v',duration=21),
                Scene(scene_id='b',asset_id='z',duration=9.4,transition='dissolve',transition_seconds=.4)))
    r=trim_confirmed_ending(p,26)
    assert r.scenes[-1].duration==pytest.approx(5.4)
    assert r.scenes[0]==p.scenes[0]
    protected=p.model_copy(update={'scenes':(p.scenes[0],p.scenes[1].model_copy(update={'source_audio':True}))})
    with pytest.raises(EditError):trim_confirmed_ending(protected,26)


@pytest.mark.parametrize('audio_mode', ['voice', 'mixed'])
def test_scene_effects_follow_natural_duration_but_absolute_events_are_protected(audio_mode):
    p = sample()
    p['settings']['audio_mode'] = audio_mode
    effect = {'id': 'effect', 'metadata_json': json.dumps({'material_uses': [
        {'role': 'sfx', 'cue_id': 'click', 'scene_id': 's2', 'at': 95,
         'duration': 1, 'timing_basis': 'scene'}]})}
    before = deepcopy(effect)
    measured, timing = measured_execution_plan(p, [record(p), effect])
    assert timing['duration'] < 95 and measured['settings']['audio_mode'] == audio_mode
    assert effect == before
    absolute = deepcopy(effect)
    meta = json.loads(absolute['metadata_json'])
    meta['material_uses'][0].pop('timing_basis')
    absolute['metadata_json'] = json.dumps(meta)
    from easel.production.model_tasks import ModelTaskError
    with pytest.raises(ModelTaskError, match='冻结时间音效'):
        measured_execution_plan(p, [record(p), absolute])
    with pytest.raises(ModelTaskError):
        measured_execution_plan(p, [record(p), {'metadata_json': json.dumps({'original_audio': True})}])


@pytest.mark.parametrize('mode',['fixed','voice_driven'])
def test_duration_review_contract_agrees_with_actual_execution(mode):
    from easel.production.narration import duration_execution_contract
    p=sample();p['narration_policy']['duration_mode']=mode;before=deepcopy(p)
    contract=duration_execution_contract(p)
    executed,timing=measured_execution_plan(p,[record(p)])
    assert p==before and contract['duration_seconds_required'] is True
    assert contract['draft_duration_seconds']==105
    if mode=='voice_driven':
        assert contract['duration_seconds_meaning']=='planning_estimate'
        assert contract['execution_basis']=='complete_measured_speech'
        assert executed['settings']['duration_seconds']==timing['duration']!=105
    else:
        assert contract['duration_seconds_meaning']=='fixed_duration'
        assert contract['execution_basis']=='confirmed_duration'
        assert executed['settings']['duration_seconds']==timing['duration']==105
