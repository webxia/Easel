"""Actual local five-modality media flow; semantic/HTTP services are scripted.

No real provider call, creator acceptance or real-production quality is claimed.
"""
import asyncio
import json
import shutil
import subprocess
import time
from pathlib import Path

import httpx
import pytest
from PIL import Image

from easel.materials.domain import CandidateSource, MediaType, RightsInfo, SemanticInfo
from easel.materials.library import LibraryVisibility, UseContext
from easel.materials.store import digest_file
from easel.production.contracts import canonical_json
from easel.production.materials import MaterialService
from easel.production.runtime import create_runtime
from easel.production.voice import VoiceHTTPAdapter
from easel.production.store import utc_now
from .test_voice_subtitles import wav_bytes
from .test_supply_tasks import RIGHTS


@pytest.mark.skipif(not shutil.which('ffmpeg') or not shutil.which('ffprobe'),reason='actual FFmpeg/ffprobe media flow unavailable')
def test_worker_image_video_bgm_native_voice_sfx_to_reviewable(tmp_path,monkeypatch):
    voice_config=[{'provider':'minimax','model':'fixture-speech','engine':'minimax-speech-v1',
        'base_url':'https://speech.invalid/v1','response_format':'wav',
        'voices':[{'voice_id':'fixed-voice','label':'Fixture fixed voice'}]}]
    (tmp_path/'.env').write_text('EASEL_DIRECT_API_BASE_URL=https://model.invalid/v1\nEASEL_DIRECT_API_MODEL=fixture\n'
        +'EASEL_VOICE_SERVICES_JSON='+json.dumps(voice_config)+'\n')
    calls=[]
    def speech_response(request):
        calls.append(json.loads(request.content))
        assert request.url.path=='/v1/t2a_v2'
        return httpx.Response(200,json={'base_resp':{'status_code':0},'data':{'status':2,'audio':wav_bytes().hex()}})
    init=VoiceHTTPAdapter.__init__
    def configured_http(self,*args,**kwargs):
        kwargs['transport']=httpx.MockTransport(speech_response)
        init(self,*args,**kwargs)
    monkeypatch.setattr(VoiceHTTPAdapter,'__init__',configured_http)

    class Model:
        capabilities=frozenset({'text','structured','tools','image','video','audio'})
        video_dialect='qwen-omni-video-url'
        quality_chunk_seconds=30
        schemas=[]
        async def complete(self,messages,tools,schema):
            self.schemas.append(schema['title'])
            data=json.loads(messages[1]['content'][0]['text'])
            if schema['title']=='MaterialIntent':
                return {'content':json.dumps({'visuals':[
                    {'scene_id':'s1','query':'blue image','media_types':['image']},
                    {'scene_id':'s2','query':'green video','media_types':['video']}],
                    'music_query':'calm music','sound_cues':[
                        {'cue_id':'door-cue','scene_id':'s2','query':'door','at':2,'duration':.1,'basis':'已确认开门声','required':True}]})}
            if schema['title']=='CreativeEdit':
                artifacts=data['artifacts']
                image=next(a for a in artifacts if a['kind']=='image')
                video=next(a for a in artifacts if a['kind']=='video')
                music=next(a for a in artifacts if a['metadata'].get('candidate_role')=='music')
                effect=next(a for a in artifacts if any(u.get('role')=='sfx' for u in a['metadata'].get('material_uses',[])))
                voices=sorted((a for a in artifacts if a['metadata'].get('role')=='voice'),key=lambda a:a['metadata']['segment_id'])
                assert len(voices)==2
                audio=[{'clip_id':'music','asset_id':music['asset_id'],'role':'music','at':0,'duration':3,'loop':True,'gain':.15},
                       {'clip_id':'door-cue','asset_id':effect['asset_id'],'role':'sfx','at':2,'duration':.1,'gain':.5}]
                audio += [{'clip_id':'voice'+str(i),'asset_id':a['asset_id'],'role':'voice','at':i*1.5,'duration':a['metadata']['duration']} for i,a in enumerate(voices)]
                return {'content':json.dumps({'scenes':[
                    {'scene_id':'s1','asset_id':image['asset_id'],'duration':1.5},
                    {'scene_id':'s2','asset_id':video['asset_id'],'duration':1.5}], 'audio':audio,'captions':[]})}
            return {'content':json.dumps({'verdict':'pass','factual_fidelity':'scripted fixture','style_consistency':'scripted fixture',
                'narrative_coherence':'scripted fixture','audiovisual_alignment':'scripted fixture','findings':[],'limitations':[]})}

    model=Model();model.schemas=[]
    runtime=create_runtime(tmp_path,transport=model)
    service=runtime.service
    work_id=service.command('create',{'title':'five-modalities'},command_id='create')['work_id']
    outputs=service.outputs
    image=outputs/'image.png';Image.new('RGB',(64,48),'blue').save(image)
    video=outputs/'video.mp4'
    subprocess.run([shutil.which('ffmpeg'),'-hide_banner','-loglevel','error','-y','-f','lavfi','-i',
        'color=c=green:s=64x48:r=24:d=2','-an','-c:v','libx264','-pix_fmt','yuv420p',str(video)],check=True,capture_output=True,timeout=30)
    with service.store.transaction() as writer:
        for id,kind,path in [('image-input','image',image),('video-input','video',video)]:
            writer.execute('INSERT INTO work_inputs(id,work_id,kind,usage,source_ref,digest,original_name,metadata_json,created_at) VALUES (?,?,?,\'must_use\',?,?,?,?,?)',
                (id,work_id,kind,path.name,digest_file(path),path.name,canonical_json({'schema_version':1,'source':{'rights':RIGHTS}}),utc_now()))
    materials=MaterialService(outputs/'_production/materials')
    for name,role,caption in [('bgm','music','calm music'),('effect','sfx','door click')]:
        path=outputs/(name+'.wav');path.write_bytes(wav_bytes())
        materials.ingest_input(source_root=outputs,relative_path=path.name,visibility=LibraryVisibility(),context=UseContext(work_id=work_id),
            media_type=MediaType.AUDIO,source=CandidateSource(kind='user_upload',provider='fixture',provider_asset_id=name),
            rights=RightsInfo.model_validate_json(canonical_json(RIGHTS)),semantic=SemanticInfo(caption=caption,attributes={'audio_roles':[role]}))
    plan={'title':'five modes','summary':'fixture only','script':'图片与视频，旁白和轻音乐，第二幕开门声。',
        'scenes':[{'id':'s1','purpose':'first','visual':'blue image','duration_seconds':1.5,'narration':'第一句。','required_input_ids':['image-input']},
                  {'id':'s2','purpose':'second','visual':'green video with a door click','duration_seconds':1.5,'narration':'第二句。','required_input_ids':['video-input']}],
        'settings':{'duration_seconds':3,'aspect_ratio':'16:9','audio_mode':'mixed','subtitles':{'enabled':False},
                    'voice':{'provider':'minimax','model':'fixture-speech','voice_id':'fixed-voice','engine':'minimax-speech-v1'}}}
    proposed=service.command('plan',{'generate':False,'plan':plan},command_id='plan',work_id=work_id,expected_revision=1)
    service.command('confirm',{'plan_revision':1,'plan_hash':proposed['plan_hash'],'services':[
        {'provider':'direct-api','model':'fixture','mode':'structured'},
        {'provider':'minimax','model':'fixture-speech','mode':'speech'}]},command_id='confirm',work_id=work_id,expected_revision=2)
    deadline=time.monotonic()+60
    try:
        while time.monotonic()<deadline:
            asyncio.run(runtime.worker.run_once())
            snap=service.snapshot(work_id)
            if snap['state']=='reviewable' or any(r['state'] in {'failed','needs_decision'} for r in snap['runs']):break
            time.sleep(.1)
        assert snap['state']=='reviewable',[(t['kind'],t['state'],t['error_json']) for t in snap['tasks']]
        assert snap['accepted_output_id'] is None
        assert len(calls)==2 and all(c['voice_setting']['voice_id']=='fixed-voice' for c in calls)
        assert model.schemas.count('MaterialIntent')==1 and model.schemas.count('CreativeEdit')==1
        assert snap['quota']['IMAGE']['used']==snap['quota']['VIDEO']['used']==0
        output=next(a for a in snap['artifacts'] if a['kind']=='output')
        path,_=service.artifact_path(output['id']);assert path.stat().st_size>1000
        with service.store.connection() as reader:
            project_ref=reader.execute("SELECT storage_ref FROM artifacts WHERE work_id=? AND kind='edit_project'",(work_id,)).fetchone()[0]
        project=json.loads((outputs/project_ref).read_text())
        assert {a['role'] for a in project['audio']}=={'voice','music','sfx'}
        assert any(a['clip_id']=='door-cue' and a['at']==2 for a in project['audio'])
    finally:runtime.stop()
