"""Five-modality contracts and hardening: isolated stores, no real services."""
import asyncio
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from PIL import Image

from easel.materials.domain import CandidateSource, MediaType, SemanticInfo, RightsInfo, RightsStatus
from easel.materials.library import LibraryVisibility, UseContext
from easel.production.contracts import PlanDocument, canonical_json
from easel.production.context import TaskContext as CreativeContext
from easel.production.material_intent import MaterialIntent, FrozenIntentCompiler, check_intent
from easel.production.material_binding import validate_material_records, validate_audio_bindings, selected_asset_ids
from easel.production.materials import MaterialService
from easel.production.model_tasks import ModelTaskError
from easel.production.planning import PlanningTasks
from easel.production.supply_tasks import SupplyTasks
from easel.production.editors import EditProject, Scene, AudioClip
from .test_supply_tasks import env, input_media, plan_settings, RIGHTS
from .test_material_supply import need, Provider, Transport, downloader
from .test_voice_subtitles import speech, wav_bytes


def plan_of(ctx):
    with ctx.store.connection() as reader:
        return PlanDocument.model_validate_json(reader.execute('SELECT payload_json FROM plan_revisions WHERE work_id=? AND revision=?',
            (ctx.work_id,ctx.plan_revision)).fetchone()[0])


def material_intent(**extra):
    return MaterialIntent.model_validate({'visuals':[{'scene_id':'s1','query':'blue desk','media_types':['image']}],**extra})


def allow(env, *services):
    _,_,ctx,spec,_=env
    with ctx.store.transaction() as writer:
        writer.execute('UPDATE authorization_grants SET services_json=? WHERE id=?',(canonical_json(list(services)),spec['grant_id']))


def ingest(service, source, ctx, *, roles=None, caption='city', rights=RIGHTS):
    return service.ingest_input(source_root=source.parent,relative_path=source.name,
        visibility=LibraryVisibility(),context=UseContext(work_id=ctx.work_id),
        media_type=MediaType.AUDIO if source.suffix=='.wav' else MediaType.IMAGE,
        source=CandidateSource(kind='user_upload',provider='fixture',provider_asset_id=source.stem),
        rights=RightsInfo.model_validate_json(canonical_json(rights)),
        semantic=SemanticInfo(caption=caption,attributes={'audio_roles':roles} if roles else {}))


def test_eligibility_precedes_top_k_and_does_not_merge_rights_records(env):
    service,ops,ctx,_,source=env
    materials=MaterialService(service.outputs/'_production/materials')
    bad=ingest(materials,source,ctx,rights={'status':'UNKNOWN'})
    good=ingest(materials,source,ctx)
    result=materials.candidates(need(),visibility=LibraryVisibility(),context=UseContext(work_id=ctx.work_id),query='city',limit=1)
    assert [c.library_asset_id for c in result.candidates]==[good.asset_ref]
    assert bad.asset_ref!=good.asset_ref
    assert len(materials.catalog.list_scope(scope=LibraryVisibility(),context=UseContext(work_id=ctx.work_id)))==2
    assert len(list((materials.catalog.root/'objects').iterdir()))==1


def test_rights_preflight_prevents_download(env):
    from easel.materials.application.supply import MaterialSupply
    service,_,ctx,_,_=env
    materials=MaterialService(service.outputs/'_production/materials')
    provider=Provider(rights=RightsInfo(status=RightsStatus.UNKNOWN))
    transport=Transport()
    result=MaterialSupply(materials,providers=(provider,),downloaders={provider.provider_id:downloader(transport)}).supply(
        need(),visibility=LibraryVisibility(),context=UseContext(work_id=ctx.work_id),allowed_providers=(provider.provider_id,))
    assert not result.candidates and transport.calls==[]
    assert result.failures[0].reason=='required_need_rights_unknown'


def test_repeated_source_listing_reuses_bytes_but_not_different_rights(env):
    from easel.materials.application.supply import MaterialSupply
    from easel.production.providers.stock import ExternalCandidate
    from easel.materials.application.acquisition import DownloadResponse
    from .test_material_supply import png, evidence
    service,_,ctx,_,_=env
    materials=MaterialService(service.outputs/'_production/materials')
    class Source:
        provider_id='fixture-stock';allowed_hosts=('media.example',)
        rights=evidence()
        def search(self,query,**kwargs):
            return (ExternalCandidate('fixed-id',MediaType.IMAGE,'https://media.example/one.png',
                CandidateSource(kind='stock',provider=self.provider_id,provider_asset_id='fixed-id',source_page='https://media.example/one'),
                self.rights,SemanticInfo(caption='first description')),)
    provider=Source();transport=Transport([DownloadResponse(200,{'content-type':'image/png'},png()),DownloadResponse(200,{'content-type':'image/png'},png())])
    supplier=MaterialSupply(materials,providers=[provider],downloaders={provider.provider_id:downloader(transport)})
    scope=LibraryVisibility();context=UseContext(work_id=ctx.work_id)
    def request(query):
        wanted=need().model_copy(update={'intent':need().intent.model_copy(update={'description':query})})
        return supplier.supply(wanted,visibility=scope,context=context,allowed_providers=(provider.provider_id,))
    first=request('first')
    second=request('new query without local metadata match')
    assert len(first.candidates)==len(second.candidates)==1 and len(transport.calls)==1
    assert first.candidates[0].library_asset_id==second.candidates[0].library_asset_id
    provider.rights=provider.rights.model_copy(update={'license_name':'Different substantive license'})
    third=request('different unrelated query')
    assert len(third.candidates)==1 and len(transport.calls)==2
    assert third.candidates[0].library_asset_id!=first.candidates[0].library_asset_id


def test_provider_configuration_does_not_grant_remote_search(env):
    service,ops,ctx,_,_=env
    provider=Provider()
    supply=SupplyTasks(service,ops,external_providers=[provider],enforce_provider_grants=True)
    assert supply._allowed_providers('image',ctx)==()
    blocked=asyncio.run(supply.supply(ctx))
    assert blocked.state=='needs_decision' and provider.calls==0
    allow(env,{'provider':provider.provider_id,'model':'stock','mode':'search'})
    assert supply._allowed_providers('image',ctx)==(provider.provider_id,)
    with ctx.store.transaction() as writer:
        writer.execute('UPDATE authorization_grants SET revoked_at=? WHERE work_id=?',('2026-10-17T00:00:00Z',ctx.work_id))
    assert supply._allowed_providers('image',ctx)==()
    assert provider.calls==0


def test_silent_mandatory_visuals_do_not_add_an_unnecessary_model_call(env):
    input_media(env)
    service,ops,ctx,_,_=env
    planning=PlanningTasks(service,ops,None,None,None)
    compiler=FrozenIntentCompiler(planning)
    plan=plan_of(ctx)
    original=plan.model_dump_json()
    first,_=asyncio.run(compiler.prepare(ctx,plan))
    again,_=asyncio.run(compiler.prepare(ctx,plan))
    assert first==again and first.visuals[0].media_types==['image']
    assert first.sound_cues==[] and first.music_query is None
    assert plan.model_dump_json()==original
    with ctx.store.connection() as reader:
        assert reader.execute('SELECT COUNT(*) FROM operations').fetchone()[0]==0


def test_internal_projection_does_not_narrow_accepted_scene_identity_or_count():
    from easel.production.material_intent import fixed_visual_intent
    names=['long_scene_'+'x'*105]+[f's{i}' for i in range(129)]
    plan=PlanDocument.model_validate({'title':'long plan','summary':'fixture','script':'fixture',
        'scenes':[{'id':name,'purpose':'fixture','visual':'fixed image','required_input_ids':['input-one']} for name in names],
        'settings':{'duration_seconds':900,'audio_mode':'silent'}})
    context=SimpleNamespace(inputs=({'input_id':'input-one','kind':'image','usage':'must_use'},))
    intent=fixed_visual_intent(plan,context)
    check_intent(intent,plan)
    assert [v.scene_id for v in intent.visuals]==names


def test_director_intent_preserves_frozen_context_and_replays_without_another_call(env):
    service,ops,ctx,_,_=env
    identity={'provider':'direct-api','model':'fixture','mode':'structured'}
    allow(env,identity)
    plan=plan_of(ctx)
    original=plan.model_dump_json()
    creative=CreativeContext(ctx.work_id,ctx.run_id,ctx.task_id,profile_ref='fixed-profile',
        profile={'identity':'frozen-persona'},director={'visual':'restrained-blue'},plan=plan.model_dump(mode='json'))
    class Model:
        capabilities=frozenset({'text','structured'})
        calls=0
        async def complete(self,messages,tools,schema):
            self.calls+=1
            value=json.loads(messages[1]['content'][0]['text'])
            assert value['profile']['identity']=='frozen-persona'
            assert value['director']['visual']=='restrained-blue'
            return {'content':material_intent().model_dump_json()}
    model=Model();planning=PlanningTasks(service,ops,model,identity,'fixed')
    planning.context=lambda context:creative
    compiler=FrozenIntentCompiler(planning)
    first,_=asyncio.run(compiler.prepare(ctx,plan))
    second,_=asyncio.run(compiler.prepare(ctx,plan))
    assert first==second and model.calls==1 and plan.model_dump_json()==original
    # The original default operation namespace remains available, not ordinal1 of the new task.
    asyncio.run(planning.runner(ctx).run(creative,'fixture',MaterialIntent))
    with ctx.store.connection() as reader:
        ids={row[0] for row in reader.execute('SELECT id FROM operations WHERE task_id=?',(ctx.task_id,))}
    assert len(ids)==2 and hashlib.sha256(f'{ctx.task_id}:model:1'.encode()).hexdigest() in ids
    planning.context=lambda context:replace(creative,director={'visual':'changed'})
    with pytest.raises(ModelTaskError,match='冻结上下文'):
        asyncio.run(compiler.prepare(ctx,plan))
    assert model.calls==2


@pytest.mark.parametrize('changes',[
    {'visuals':[{'scene_id':'other','query':'q','media_types':['image']}]},
    {'sound_cues':[{'cue_id':'c','scene_id':'s1','query':'door','at':1,'duration':1,'basis':'door'}]},
    {'music_query':'music'},
])
def test_invalid_or_silent_intent_is_rejected(env,changes):
    plan=plan_of(env[2])
    data=material_intent().model_dump();data.update(changes)
    with pytest.raises(ModelTaskError):check_intent(MaterialIntent.model_validate(data),plan)


def test_sfx_two_events_share_bytes_but_retain_distinct_bindings(env):
    import shutil
    if not shutil.which('ffprobe'):pytest.skip('actual local audio inspection unavailable')
    input_media(env);plan_settings(env,audio_mode='music')
    service,ops,ctx,_,_=env
    materials=MaterialService(service.outputs/'_production/materials')
    music=service.outputs/'music.wav';music.write_bytes(wav_bytes())
    sfx=service.outputs/'effect.wav';sfx.write_bytes(wav_bytes())
    ingest(materials,music,ctx,roles=['music'],caption='music calm')
    ingest(materials,sfx,ctx,roles=['sfx'],caption='door click')
    cues=[{'cue_id':f'cue{i}','scene_id':'s1','query':'door','at':float(i),'duration':.1,'basis':'door action','required':True} for i in (1,2)]
    intent=material_intent(music_query='calm music',sound_cues=cues)
    class Compiler:
        async def prepare(self,context,plan):
            check_intent(intent,plan)
            return intent,CreativeContext(ctx.work_id,ctx.run_id,ctx.task_id,director={'audio':'restrained'})
    supply=SupplyTasks(service,ops,materials=materials,intent_compiler=Compiler())
    result=asyncio.run(supply.supply(ctx))
    assert result.state=='succeeded' and set(result.next_payload)=={'schema_version','asset_ids'}
    with ctx.store.connection() as reader:
        records=[dict(row) for row in reader.execute('SELECT * FROM artifacts')]
    effects=[r for r in records if any(u.get('role')=='sfx' for u in json.loads(r['metadata_json']).get('material_uses',[]))]
    assert len(effects)==1
    uses=json.loads(effects[0]['metadata_json'])['material_uses']
    assert {u['cue_id'] for u in uses}=={'cue1','cue2'}
    ref=json.loads(effects[0]['metadata_json'])['asset_ref']
    retained=materials.catalog.usage_for_asset(ref,scope=LibraryVisibility(),context=UseContext(work_id=ctx.work_id))
    assert any({'sfx:cue1','sfx:cue2'} <= set(u.need_ids) for u in retained)
    assert asyncio.run(supply.supply(ctx)).next_payload==result.next_payload
    image=next(r for r in records if r['kind']=='image')
    bgm=next(r for r in records if json.loads(r['metadata_json']).get('candidate_role')=='music')
    project=EditProject(work_id=ctx.work_id,plan_revision=ctx.plan_revision,revision=1,duration=90,audio_mode='music',
        scenes=(Scene(scene_id='s1',asset_id=image['id'],duration=90),),audio=(
            AudioClip(clip_id='bgm',asset_id=bgm['id'],role='music',at=0,duration=90,loop=True),
            *[AudioClip(clip_id=f'cue{i}',asset_id=effects[0]['id'],role='sfx',at=i,duration=.1) for i in (1,2)]))
    validate_audio_bindings(project,records)
    with pytest.raises(ModelTaskError,match='必要音效'):
        validate_audio_bindings(project.model_copy(update={'audio':project.audio[:-1]}),records)
    with pytest.raises(ModelTaskError,match='时间位置'):
        validate_audio_bindings(project.model_copy(update={'audio':(project.audio[0],project.audio[1].model_copy(update={'at':3}),project.audio[2])}),records)


def test_selected_material_revalidation_does_not_accept_a_changed_rights_record(env):
    input_media(env)
    service,ops,ctx,_,_=env
    supply=SupplyTasks(service,ops)
    assert asyncio.run(supply.supply(ctx)).state=='succeeded'
    with ctx.store.connection() as reader:
        records=[dict(row) for row in reader.execute('SELECT * FROM artifacts')]
    validate_material_records(service,ctx,records)
    ref=json.loads(records[0]['metadata_json'])['asset_ref']
    # Corrupt only isolated fixture metadata to prove the consumer does not trust an old ready flag.
    with supply.materials.catalog._connect() as writer:
        row=json.loads(writer.execute('SELECT record_json FROM library_assets WHERE library_asset_id=?',(ref,)).fetchone()[0])
        row['asset']['rights']['status']='RESTRICTED'
        writer.execute('UPDATE library_assets SET record_json=? WHERE library_asset_id=?',(json.dumps(row),ref))
    with pytest.raises(ModelTaskError,match='失效'):
        validate_material_records(service,ctx,records)


def test_selected_dependencies_exclude_unselected_candidates(env,monkeypatch):
    from easel.production.creation import CreationTasks
    from easel.production.artifacts import register_file
    service,ops,ctx,_,image=env
    second=service.outputs/'unused.png';Image.new('RGB',(32,24),'red').save(second)
    first=register_file(service,ctx,image,kind='image',media_type='image/png',metadata={'test':'synthetic'})
    unused=register_file(service,ctx,second,kind='image',media_type='image/png',metadata={'test':'synthetic','attribution':{'destination':'export_credits','credit_text':'unused credit','source_page':'https://example.org'}})
    identity={'provider':'direct-api','model':'fixture','mode':'structured'};allow(env,identity)
    class Model:
        capabilities=frozenset({'text','structured','image'})
        async def complete(self,messages,tools,schema):
            return {'content':json.dumps({'scenes':[{'scene_id':'s1','asset_id':first['id'],'duration':90}],'audio':[],'captions':[]})}
    planning=PlanningTasks(service,ops,Model(),identity,'fixture')
    # This test isolates selection/dependency semantics, not FFmpeg availability.
    # Real-media inspection has separate opt-in, capability-aware tests.
    monkeypatch.setattr('easel.production.creation.observe_media',
        lambda _path, **_kwargs: ((),frozenset({'image'}),{'fixture':'selection_only'}))
    creation=CreationTasks(service,planning,editor=SimpleNamespace(check=lambda *_:SimpleNamespace(valid=True)))
    result=asyncio.run(creation.edit(replace(ctx,payload={'asset_ids':[first['id'],unused['id']]})))
    assert result.state=='succeeded' and result.next_payload['asset_ids']==[first['id']]
    with ctx.store.connection() as reader:
        edges={r[0] for r in reader.execute('SELECT dependency_id FROM artifact_edges WHERE artifact_id=?',(result.next_payload['project_id'],))}
    assert edges=={first['id']}


@pytest.mark.parametrize('required',[True,False])
def test_missing_sfx_is_explicit_and_optional_cue_is_not_a_new_hard_gate(env,required):
    input_media(env);plan_settings(env,audio_mode='voice')
    service,ops,ctx,_,_=env
    intent=material_intent(sound_cues=[{'cue_id':'cue','scene_id':'s1','query':'door click','at':1,'duration':.1,'required':required,'basis':'door'}])
    class Compiler:
        async def prepare(self,ctx,plan):
            return intent,CreativeContext(ctx.work_id,ctx.run_id,ctx.task_id)
    result=asyncio.run(SupplyTasks(service,ops,intent_compiler=Compiler()).supply(ctx))
    if required:
        assert result.state=='needs_decision' and result.error.code=='sfx_material_gap'
    else:
        assert result.state=='succeeded'
    with ctx.store.connection() as reader:
        assert reader.execute("SELECT count(*) FROM artifacts WHERE kind='image'").fetchone()[0]==1
        assert reader.execute('SELECT count(*) FROM operations').fetchone()[0]==0


def test_stock_authorization_revoked_after_search_stops_before_download(env):
    service,ops,ctx,_,_=env
    provider=Provider();transport=Transport()
    allow(env,{'provider':provider.provider_id,'model':'stock','mode':'search'})
    original=provider.search
    def search(*args,**kwargs):
        candidates=original(*args,**kwargs)
        with ctx.store.transaction() as writer:
            writer.execute('UPDATE authorization_grants SET revoked_at=? WHERE work_id=?',('2026-10-17T00:00:00Z',ctx.work_id))
        return candidates
    provider.search=search
    task=SupplyTasks(service,ops,external_providers=[provider],enforce_provider_grants=True,
        downloaders={provider.provider_id:downloader(transport)})
    result=asyncio.run(task.supply(ctx))
    assert result.error.code=='permission_missing' and provider.calls==1 and transport.calls==[]


def test_capability_directory_uses_the_same_voice_validation_without_side_effects(tmp_path,monkeypatch):
    from easel.production import configuration
    settings={'EASEL_VOICE_SERVICES_JSON':json.dumps([{'provider':'speech','model':'fixed-model','engine':'minimax-speech-v1',
        'base_url':'https://speech.invalid/v1','api_key_env':'ABSENT_KEY','voices':[{'voice_id':'fixed','label':'fixed'}]}])}
    monkeypatch.setattr(configuration,'model_configuration',lambda root:(settings,None,None))
    result=configuration.capabilities(tmp_path)
    voice=next(item for item in result['services'] if item['provider']=='speech')
    assert voice['available'] is False
    assert list(tmp_path.iterdir())==[]


def test_minimax_native_tts_uses_fixed_voice_and_durable_cache(speech,tmp_path):
    from easel.production.voice import SpeechConfig,VoiceOption,VoiceService,VoiceBinding
    from easel.production.providers.minimax_speech import MiniMaxSpeechAdapter
    _,ops,binding,voice,_,_,_=speech
    voice=voice.model_copy(update={'engine':'minimax-speech-v1'})
    calls=[]
    def handler(request):
        calls.append(request)
        body=json.loads(request.content)
        assert request.url.path=='/v1/t2a_v2'
        assert body['voice_setting']['voice_id']=='fixed-a' and body['text']=='已确认旁白。'
        assert body['output_format']=='hex' and body['stream'] is False
        return httpx.Response(200,json={'base_resp':{'status_code':0},'data':{'status':2,'audio':wav_bytes().hex()}})
    config=SpeechConfig(provider=voice.provider,model=voice.model,engine=voice.engine,base_url='https://speech.invalid/v1',
        config_version='native-fixture',voices=(VoiceOption(voice,'same voice'),),mode='normal')
    adapter=MiniMaxSpeechAdapter(config,tmp_path/'native',transport=httpx.MockTransport(handler))
    service=VoiceService(ops,tmp_path/'native-cache',[adapter])
    first=service.synthesize(binding,identity=voice,text='已确认旁白。',segment_id='one')
    assert first['state']=='succeeded' and first['asset']['duration']==.2
    second=service.synthesize(VoiceBinding(**{**binding.__dict__,'operation_id':'other-scene'}),identity=voice,text='已确认旁白。',segment_id='two')
    assert second['reused'] and len(calls)==1
    assert all(q['used']==0 for q in ops.quota(binding.work_id).values())


@pytest.mark.parametrize('response',[
    {'base_resp':{'status_code':0},'data':{'status':2,'audio':'NOT-HEX'}},
    {'base_resp':{'status_code':1000},'data':None},
    {'base_resp':{'status_code':0},'data':{'status':1,'audio':'aaaa'}},
])
def test_native_tts_invalid_json_result_is_not_resent(speech,tmp_path,response):
    from easel.production.voice import SpeechConfig,VoiceOption,VoiceService
    from easel.production.providers.minimax_speech import MiniMaxSpeechAdapter
    _,ops,binding,voice,_,_,_=speech
    voice=voice.model_copy(update={'engine':'minimax-speech-v1'});calls=[]
    def handler(request):calls.append(1);return httpx.Response(200,json=response)
    config=SpeechConfig(provider=voice.provider,model=voice.model,engine=voice.engine,base_url='https://speech.invalid/v1',
        config_version='invalid-native',voices=(VoiceOption(voice,'fixed'),),mode='normal')
    adapter=MiniMaxSpeechAdapter(config,tmp_path/'native',transport=httpx.MockTransport(handler))
    service=VoiceService(ops,tmp_path/'native-cache',[adapter])
    result=service.synthesize(binding,identity=voice,text='句子。',segment_id='one')
    assert result['state']=='failed_after_submit'
    assert service.synthesize(binding,identity=voice,text='句子。',segment_id='one')['state']=='failed_after_submit'
    assert len(calls)==1
