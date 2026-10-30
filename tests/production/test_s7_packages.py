"""S7 contracts, source isolation and deterministic guards; no paid services."""
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from pydantic import ValidationError
from easel.production.contracts import Scene,VoiceIdentity
from easel.production.errors import ProductionError
from easel.production.prosody import compile_pauses
from easel.production.narration import narration_segments
from easel.production.configuration import review_configuration,review_readiness
from tests.production.test_conversation import env,entry,turn
from tests.production.test_conversation_pipeline import seed,pipe
from tests.production.test_voice_subtitles import speech


def voice():return VoiceIdentity(provider='minimax',model='speech-2.8-turbo',voice_id='fixed',engine='minimax-speech-v1')


def test_pauses_do_not_pollute_literal_text_or_subtitles():
    scene=Scene(id='s',purpose='explain',visual='example',narration='先看问题，再说原因。',narration_pauses=[{'after':5,'seconds':.3}])
    plan={'scenes':[scene.model_dump()],'narration_policy':{'continuous':True}}
    part=narration_segments(plan)[0]
    assert part['text']==scene.narration
    assert compile_pauses(part['text'],part['pauses'],voice())=='先看问题，<#0.3#>再说原因。'
    assert '<#' not in part['text'] and '<#' not in plan['scenes'][0]['narration']


@pytest.mark.parametrize('pauses',[[{'after':0,'seconds':.3}],[{'after':4,'seconds':.3}],[{'after':1,'seconds':2}],[{'after':1,'seconds':.2},{'after':1,'seconds':.3}]])
def test_invalid_pause_contract_rejected(pauses):
    with pytest.raises(ValidationError):Scene(id='s',purpose='x',visual='x',narration='正文示例',narration_pauses=pauses)


def test_pause_mapping_across_scenes_and_capability_guard():
    plan={'scenes':[{'id':'a','narration':'第一句。','narration_pauses':[{'after':2,'seconds':.2}]},
                    {'id':'b','narration':'第二句。','narration_pauses':[{'after':2,'seconds':.4}]}],
          'narration_policy':{'continuous':True}}
    part=narration_segments(plan)[0]
    assert [p['after'] for p in part['pauses']]==[2,7]
    with pytest.raises(ProductionError):compile_pauses(part['text'],part['pauses'],voice().model_copy(update={'model':'unsupported'}))
    assert compile_pauses('原文',[],voice())=='原文'


def test_review_model_is_explicit_separate_and_not_inherited():
    settings={'EASEL_DIRECT_API_MODEL':'writer','EASEL_DIRECT_API_KEY':'writer-secret','EASEL_DIRECT_API_BASE_URL':'https://writer.invalid/v1'}
    assert review_configuration(settings) is None
    review={**settings,'EASEL_REVIEW_MODEL':'reviewer','EASEL_REVIEW_BASE_URL':'https://review.invalid/v1','EASEL_REVIEW_KEY':'review-secret',
        'EASEL_REVIEW_CAPABILITIES':'video,audio','EASEL_REVIEW_VIDEO_DIALECT':'qwen-omni-video-url'}
    mapped,identity,version=review_configuration(review)
    assert identity=={'provider':'review-api','model':'reviewer','mode':'structured'}
    assert mapped['EASEL_DIRECT_API_KEY']=='review-secret' and settings['EASEL_DIRECT_API_MODEL']=='writer'
    assert review_readiness(mapped)['available'] and not review_readiness(mapped)['verified_live']
    assert not review_readiness({})['available']
    assert not review_readiness({**mapped,'EASEL_PRODUCTION_MODEL_CAPABILITIES':'video'})['available']


def test_no_profile_temporary_creation_uses_selected_director_without_channel(env):
    seed(env);service,conversations=env
    seg=entry(conversations,director_revision='v4',director_trial=True)
    bridge,identity,_=turn(service,conversations,seg,'创建临时视频')
    state=pipe(bridge,identity,'pending')
    assert not state['missing_choices']
    assert not state['context'].get('profile')
    result=pipe(bridge,identity,'draft',user_quote='创建临时视频',values={'title':'临时','input_text':'仅当前内容'})
    work=service.snapshot(result['work_id'])
    assert work['profile_ref'] is None and work['channel_id'] is None


def test_encoding_profile_is_part_of_export_contract():
    from easel.production.editors.ffmpeg import ENCODING,LocalRender
    renderer=object.__new__(LocalRender);renderer.engine={'encoding':ENCODING}
    args=renderer.encode()
    assert args[args.index('-preset')+1]=='medium' and args[args.index('-crf')+1]=='18'
    from easel.production.editors.base import RenderOutput
    assert 'encoding' in RenderOutput.model_fields


def test_board_revision_protects_literal_facts():
    import copy
    from easel.production.planning import validate_board_revision
    base={'settings':{'audio_mode':'voice'},'script':'原话','scenes':[{'id':'s','narration':'原话'}],
          'explainer_boards':[{'id':'b','cards':[{'id':'one','text':'真实'}],'states':[{'id':'first'}]}]}
    answer=copy.deepcopy(base);answer['explainer_boards'][0]['states']=[{'id':'reordered'}]
    wrapped=SimpleNamespace(model_dump=lambda **kwargs:answer)
    validate_board_revision(wrapped,base)
    answer['explainer_boards'][0]['cards'][0]['text']='编造'
    with pytest.raises(ValueError):validate_board_revision(wrapped,base)


def test_observation_rounding_reuses_actual_evidence_without_spending_budget():
    import asyncio
    from easel.production.edit_observation import ObservationBudget
    budget=ObservationBudget();budget.observed={'asset':[.333333]}
    before=budget.remaining
    result=asyncio.run(budget.observe('asset',Path('/not-read'),frame_times=[1/3]))
    assert result.evidence['frame_times']==[.333333]
    assert result.evidence['unobserved_times']==[] and budget.remaining==before


def test_render_cache_preview_protects_live_jobs_and_export(tmp_path,monkeypatch):
    import shutil
    if not shutil.which('ffmpeg'):pytest.skip('FFmpeg unavailable')
    from tests.production.test_creation_flow import test_confirm_to_real_render_to_reviewable_without_creator_acceptance as first_cut
    from easel.production.store import Store
    from easel.production.service import WorkService
    from easel.production.maintenance import render_cache,operating_summary
    from easel.production.editors.ffmpeg import _lock
    first_cut(tmp_path,full_video=True,recover_render=False,overlay_repair=False,inspect_image=False,monkeypatch=monkeypatch)
    service=WorkService(Store(tmp_path/'outputs/_production/production.sqlite3'),outputs=tmp_path/'outputs',profiles=tmp_path/'profiles')
    job=next(p for p in (service.outputs/'_production/renders').iterdir() if (p/'job.json').is_file())
    preview=render_cache(service,job.name)
    assert preview['files'] and preview['bytes']>0
    final=(job/'final.mp4').read_bytes()
    with service.store.transaction() as conn:
        operation=conn.execute('SELECT id,state FROM operations WHERE work_id=? LIMIT 1',(preview['work_id'],)).fetchone()
        conn.execute("UPDATE operations SET state='unknown' WHERE id=?",(operation['id'],))
    with pytest.raises(ProductionError,match='待核实'):render_cache(service,job.name)
    with service.store.transaction() as conn:
        conn.execute('UPDATE operations SET state=? WHERE id=?',(operation['state'],operation['id']))
    scenes=job/'scenes';scenes.rename(job/'held-scenes');scenes.symlink_to(job/'held-scenes',target_is_directory=True)
    with pytest.raises(ProductionError,match='符号链接'):render_cache(service,job.name)
    scenes.unlink();(job/'held-scenes').rename(scenes)
    with _lock(job/'execution.lock'):
        with pytest.raises(ProductionError):render_cache(service,job.name,preview_hash=preview['preview_hash'])
    with pytest.raises(ProductionError):render_cache(service,job.name,preview_hash='stale')
    result=render_cache(service,job.name,preview_hash=preview['preview_hash'])
    assert result['removed_bytes']==preview['bytes'] and (job/'final.mp4').read_bytes()==final
    assert (job/'project.json').exists() and (job/'output.json').exists()
    assert operating_summary(service)['usage_cost'] is None


def test_natural_web_entry_without_profile_has_no_implicit_grant(env):
    from web.conversation_api import NaturalEntry,EntryCall
    service,_=env
    gate=NaturalEntry();gate.reserve('ui','native','turn','prompt','讨论临时视频','')
    identity=dict(agent_id='main',session_key='agent:main:ui',session_id='native',run_id='run')
    gate.call(service,EntryCall(**identity,mode='claim',prompt='prompt'))
    result=gate.call(service,EntryCall(**identity,mode='enter',prompt='',kind='new_work',tool_call_id='call'))
    assert result['entered'] and 'director' in result['pending']['missing_choices']
    assert 'channel' not in result['pending']['missing_choices']
    with service.store.connection() as conn:
        for table in ('works','operations','authorization_grants'):
            assert conn.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]==0


def test_inline_provider_control_is_rejected_from_literal_narration():
    with pytest.raises(ValidationError):
        Scene(id='s',purpose='x',visual='x',narration='正文<#0.3#>示例')


def test_review_credentials_cannot_fall_back_to_writer():
    mapped,_,_=review_configuration({'EASEL_REVIEW_MODEL':'review','EASEL_REVIEW_BASE_URL':'https://review.invalid/v1',
                                    'EASEL_DIRECT_API_KEY':'writer-secret'})
    # Unauthenticated local services are legal, but cannot inherit another key.
    assert mapped['EASEL_DIRECT_API_KEY']==''


def test_prosody_wire_identity_reuse_and_literal_receipt(speech,tmp_path):
    import httpx
    from easel.production.voice import VoiceService,VoiceBinding,SpeechConfig,VoiceOption
    from easel.production.providers.minimax_speech import MiniMaxSpeechAdapter
    from tests.production.test_voice_subtitles import wav_bytes
    store,ops,binding,_,_,_,_=speech
    identity=voice()
    with store.transaction() as conn:
        conn.execute('UPDATE authorization_grants SET services_json=? WHERE work_id=?',
                     (json.dumps([{'provider':identity.provider,'model':identity.model,'mode':'normal'}]),binding.work_id))
    calls=[]
    def handler(req):
        calls.append(json.loads(req.content))
        return httpx.Response(200,json={'base_resp':{'status_code':0},'data':{'status':2,'audio':wav_bytes().hex()}})
    config=SpeechConfig(provider=identity.provider,model=identity.model,engine=identity.engine,
        base_url='https://speech.invalid/v1',config_version='prosody-test',voices=(VoiceOption(identity,'fixed'),),mode='normal')
    adapter=MiniMaxSpeechAdapter(config,tmp_path/'native',transport=httpx.MockTransport(handler))
    service=VoiceService(ops,tmp_path/'pauses',[adapter])
    def speak(operation,pauses):
        return service.synthesize(VoiceBinding(**{**binding.__dict__,'operation_id':operation}),identity=identity,
                                  text='先说，再解释。',segment_id=operation,pauses=pauses)
    first=speak('plain',[])
    paused=speak('paused',[{'after':3,'seconds':.3}])
    reused=speak('same-pause',[{'after':3,'seconds':.3}])
    assert first['state']==paused['state']=='succeeded'
    assert reused['reused'] and len(calls)==2
    assert calls[0]['text']=='先说，再解释。' and calls[1]['text']=='先说，<#0.3#>再解释。'
    assert paused['text']=='先说，再解释。' and paused['text_hash']==first['text_hash']


@pytest.mark.parametrize('mode,blocking,scope',[('manual',False,'manual_with_visual_samples'),('full',True,'full_audio_video')])
def test_review_status_separates_manual_policy_from_full_av_availability(tmp_path,mode,blocking,scope):
    from easel.production.configuration import capabilities
    (tmp_path/'.env').write_text('EASEL_PRODUCTION_QC_MODE='+mode+'\nEASEL_PRODUCTION_VISUAL_REVIEW=1\n')
    status=capabilities(tmp_path)['review']
    assert status['configured_mode']==mode and status['active_scope']==scope
    assert not status['available'] and status['blocking'] is blocking
    assert not status['verified_live']


def test_minimax_video_support_never_implies_audio_understanding():
    settings={'EASEL_PRODUCTION_VIDEO_DIALECT':'minimax-video-url','EASEL_PRODUCTION_MODEL_CAPABILITIES':'video'}
    assert review_readiness(settings,audio=False)['available']
    assert not review_readiness(settings,audio=True)['available']
    forged={**settings,'EASEL_PRODUCTION_MODEL_CAPABILITIES':'video,audio'}
    assert review_readiness(forged,audio=True)['reason']=='audio_video_protocol_unavailable'
