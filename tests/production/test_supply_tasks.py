"""Actual supply -> production DB boundary, isolated media and offline providers."""
import asyncio
import base64
from dataclasses import replace
import json
from types import SimpleNamespace

import httpx
from PIL import Image
import pytest

from easel.materials.domain import CandidateSource, MediaType, RightsInfo, SemanticInfo
from easel.production.contracts import canonical_json
from easel.production.errors import StaleRevision
from easel.production.operations import OperationService
from easel.production.providers.generation_http import MiniMaxImageProvider, MiniMaxVideoProvider
from easel.production.providers.stock import ExternalCandidate
from easel.production.service import WorkService
from easel.production.store import Store,utc_now
from easel.production.supply_tasks import SupplyTasks, SupplyDecision, configured_supply, supply_capabilities
from easel.production.worker import TaskContext
from .test_operations import owned_request


RIGHTS={'status':'KNOWN','license_name':'Fixture owned media',
        'evidence':[{'kind':'asset_owner_declaration','reference':'fixture:owner-explicit-permission'}]}


@pytest.fixture
def env(tmp_path):
    outputs=tmp_path/'outputs';outputs.mkdir()
    profiles=tmp_path/'profiles';profiles.mkdir()
    store=Store(outputs/'_production'/'production.sqlite3');store.initialize()
    spec=owned_request(store,limit=2)
    service=WorkService(store,outputs=outputs,profiles=profiles)
    operations=OperationService(store,clock=lambda:1000)
    ctx=TaskContext(store,spec['work_id'],spec['run_id'],spec['task_id'],'owner',1,1,'input',{'schema_version':1},lambda:1000)
    source=outputs/'sample.png';Image.new('RGB',(32,24),'blue').save(source)
    return [service,operations,ctx,spec,source]


def input_media(env,*,rights=RIGHTS,usage='must_use',id='input-one'):
    service,_,ctx,_,source=env
    from easel.materials.store import digest_file
    with ctx.store.transaction() as conn:
        conn.execute('''INSERT INTO work_inputs(id,work_id,kind,usage,source_ref,digest,original_name,metadata_json,created_at)
          VALUES(?,?,'image',?,'sample.png',?,'sample.png',?,?)''',(id,ctx.work_id,usage,digest_file(source),canonical_json({'schema_version':1,'source':{'rights':rights}}),utc_now()))
        record=conn.execute('SELECT payload_json FROM plan_revisions WHERE work_id=?',(ctx.work_id,)).fetchone()
        payload=json.loads(record[0]);payload['scenes'][0]['required_input_ids']=[id] if usage=='must_use' else []
        work=ctx.store.get_work(ctx.work_id,connection=conn)
        saved=ctx.store.save_plan(ctx.work_id,payload,expected_revision=work['revision'],connection=conn)
        revision=saved['revision']
        conn.execute('UPDATE plan_revisions SET confirmed_at=? WHERE work_id=? AND revision=?',(utc_now(),ctx.work_id,revision))
        conn.execute('UPDATE runs SET plan_revision=? WHERE id=?',(revision,ctx.run_id))
        conn.execute('UPDATE tasks SET plan_revision=? WHERE id=?',(revision,ctx.task_id))
        conn.execute('UPDATE authorization_grants SET plan_revision=? WHERE work_id=?',(revision,ctx.work_id))
    env[2]=replace(ctx,plan_revision=revision)


def run(handler,ctx):return asyncio.run(handler.supply(ctx))


def generation(env,*,fault=None,limit=2):
    service,ops,ctx,spec,source=env;calls=[]
    def receive(request):
        calls.append(request)
        if fault=='timeout':raise httpx.ReadTimeout('private provider detail')
        return httpx.Response(200,json={'base_resp':{'status_code':0},'data':{'image_base64':[base64.b64encode(source.read_bytes()).decode()]}})
    provider=MiniMaxImageProvider('fixture-secret',receipt_root=service.outputs/'_production'/'receipts',transport=httpx.MockTransport(receive))
    with ctx.store.transaction() as conn:
        conn.execute('UPDATE authorization_grants SET services_json=? WHERE id=?',(canonical_json([{'provider':provider.provider_id,'model':provider.model,'mode':provider.mode}]),spec['grant_id']))
        conn.execute('UPDATE works SET image_limit=? WHERE id=?',(limit,ctx.work_id))
    choice={'scene_id':'s1','kind':'IMAGE','prompt':'A literal blue desk'}
    ctx=replace(ctx,payload={'schema_version':1,'generation_requests':[choice]})
    task=SupplyTasks(service,ops,generation_providers={'IMAGE':provider},generation_rights={'IMAGE':RightsInfo.model_validate_json(canonical_json(RIGHTS))})
    return task,ctx,calls


def test_required_material_is_copied_registered_and_reused_without_acquisition(env,monkeypatch):
    input_media(env)
    service,ops,ctx,_,source=env
    task=SupplyTasks(service,ops)
    result=run(task,ctx)
    assert result.state=='succeeded' and result.next_kind=='edit'
    assert set(result.next_payload)=={'schema_version','asset_ids'}
    with ctx.store.connection() as conn:
        records=[dict(r) for r in conn.execute('SELECT * FROM artifacts')]
    assert len(records)==1 and records[0]['kind']=='image'
    record=records[0];metadata=json.loads(record['metadata_json'])
    assert metadata['input_id']=='input-one' and metadata['rights']['status']=='KNOWN'
    assert record['storage_ref'].startswith(f'works/{ctx.work_id}/assets/')
    assert (service.outputs/record['storage_ref']).read_bytes()==source.read_bytes()
    assert source.is_file()
    monkeypatch.setattr(task.materials,'ingest_input',lambda **kw:pytest.fail('must not reingest registered input'))
    again=run(task,ctx)
    assert again.next_payload==result.next_payload
    serialized=canonical_json(again.result)
    assert str(service.outputs) not in serialized and 'fixture-secret' not in serialized


def test_unknown_required_rights_never_replaced_or_generated(env):
    input_media(env,rights={'status':'UNKNOWN'})
    task,ctx,calls=generation(env)
    result=run(task,ctx)
    assert result.state=='needs_decision' and result.error.code=='required_material_unavailable'
    assert calls==[]
    with ctx.store.connection() as conn:assert conn.execute('SELECT COUNT(*) FROM artifacts').fetchone()[0]==0


def test_reference_only_input_not_given_to_editor(env):
    input_media(env,usage='reference')
    service,ops,ctx,_,_=env
    result=run(SupplyTasks(service,ops),ctx)
    assert result.error.code=='material_gap'
    with ctx.store.connection() as conn:assert conn.execute('SELECT COUNT(*) FROM artifacts').fetchone()[0]==0


def test_changed_registered_media_blocks_recovery(env):
    input_media(env);service,ops,ctx,_,_=env;task=SupplyTasks(service,ops)
    result=run(task,ctx)
    with ctx.store.connection() as conn:path=conn.execute('SELECT storage_ref FROM artifacts WHERE id=?',(result.result['asset_ids'][0],)).fetchone()[0]
    (service.outputs/path).write_bytes(b'changed')
    assert run(task,ctx).error.code=='material_changed'


def test_stale_owner_cannot_register_or_invoke(env):
    input_media(env);service,ops,ctx,_,_=env
    with ctx.store.transaction() as conn:conn.execute('UPDATE runs SET owner_epoch=2 WHERE id=?',(ctx.run_id,))
    with pytest.raises(StaleRevision):run(SupplyTasks(service,ops),ctx)
    with ctx.store.connection() as conn:assert conn.execute('SELECT COUNT(*) FROM artifacts').fetchone()[0]==0


def test_real_image_adapter_through_operations_and_artifacts_replays_once(env):
    task,ctx,calls=generation(env)
    first=run(task,ctx)
    assert first.state=='succeeded', first.error.as_dict() if first.error else first
    second=run(task,ctx)
    assert second.next_payload==first.next_payload and len(calls)==1
    assert task.operations.quota(ctx.work_id)['IMAGE']['used']==1
    with ctx.store.connection() as conn:
        artifact=conn.execute('SELECT * FROM artifacts').fetchone()
        metadata=json.loads(artifact['metadata_json'])
        assert artifact['operation_id'] and metadata['source']['kind']=='generated'
        assert any(e['kind']=='asset_generation_receipt' for e in metadata['rights']['evidence'])
        assert 'local_path' not in canonical_json(metadata) and 'fixture-secret' not in canonical_json(metadata)


def test_unknown_generation_is_observed_without_resubmit(env):
    task,ctx,calls=generation(env,fault='timeout')
    first=run(task,ctx);second=run(task,ctx)
    assert first.error.code==second.error.code=='result_unknown'
    assert len(calls)==1 and task.operations.quota(ctx.work_id)['IMAGE']['unknown']==1


def test_quota_or_missing_rights_cannot_send(env):
    task,ctx,calls=generation(env,limit=0)
    assert run(task,ctx).error.code=='quota_exhausted' and calls==[]
    task.generation_rights={}
    assert run(task,ctx).error.code=='rights_evidence_missing' and calls==[]


def test_stock_candidates_reach_edit_with_source_evidence(env):
    service,ops,ctx,_,source=env
    class Provider:
        provider_id='fixture-stock';allowed_hosts=('example.org',)
        def __init__(self):self.calls=[]
        def search(self,query,*,media_type,limit):
            self.calls.append(media_type)
            return [ExternalCandidate('stock',MediaType.IMAGE,'https://example.org/media.png',CandidateSource(kind='external',provider=self.provider_id,source_page='https://example.org/asset/1'),RightsInfo.model_validate_json(canonical_json(RIGHTS)),SemanticInfo(caption=query))] if media_type is MediaType.IMAGE else []
    class Downloader:
        def download(self,url,*,media_type):return SimpleNamespace(body=source.read_bytes(),mime='image/png')
    provider=Provider()
    task=SupplyTasks(service,ops,external_providers=[provider],downloaders={'fixture-stock':Downloader()})
    result=run(task,ctx)
    assert result.state=='succeeded'
    count=len(provider.calls)
    assert run(task,ctx).next_payload==result.next_payload and len(provider.calls)==count


def test_model_can_choose_generation_within_existing_authorization(env):
    task,ctx,calls=generation(env);ctx=replace(ctx,payload={'schema_version':1})
    from easel.production.context import TaskContext as CreativeContext
    class Runner:
        async def run(self,context,prompt,schema):
            assert 'scene_id' not in context.creative_data()  # execution context isn't silently editable
            return SupplyDecision(generation_requests=[{'scene_id':'s1','kind':'IMAGE','prompt':'An accurate blue desk'}])
    class Planning:
        def context(self,_):return CreativeContext(ctx.work_id,ctx.run_id,ctx.task_id)
        def runner(self,_):return Runner()
    task.planning=Planning()
    class EmptySource:
        provider_id='explicit-public-source';allowed_hosts=('example.org',)
        def search(self,*args,**kwargs):return []
    task.external_providers=(EmptySource(),)
    task.supplier.providers=task.external_providers
    result=run(task,ctx)
    assert result.state=='succeeded' and len(calls)==1
    with ctx.store.connection() as conn:payload=json.loads(conn.execute('SELECT payload_json FROM tasks WHERE id=?',(ctx.task_id,)).fetchone()[0])
    assert payload['supply_decision']['generation_requests'][0]['scene_id']=='s1'
    assert run(task,replace(ctx,payload=payload)).state=='succeeded' and len(calls)==1


def test_capability_configuration_never_implies_license_or_network(env):
    service,ops,_,_,_=env
    settings={'MINIMAX_API_KEY':'fixture-secret','EASEL_VIDEO_MODEL':'MiniMax-H3'}
    assert all(not r['available'] and r['reason']=='rights_evidence_missing' for r in supply_capabilities(settings))
    settings['EASEL_GENERATION_RIGHTS_JSON']=canonical_json({'schema_version':1,'IMAGE':RIGHTS,'VIDEO':RIGHTS})
    assert all(r['available'] for r in supply_capabilities(settings))
    task=configured_supply(service,ops,None,settings)
    assert set(task.generation_providers)=={'IMAGE','VIDEO'}
    assert 'fixture-secret' not in canonical_json(supply_capabilities(settings))
    assert supply_capabilities({})[0]['available'] is False


def test_video_submit_poll_download_through_real_inspection(env,monkeypatch):
    import shutil,subprocess
    ffmpeg,ffprobe=shutil.which('ffmpeg'),shutil.which('ffprobe')
    if not ffmpeg or not ffprobe:pytest.skip('FFmpeg/ffprobe unavailable; actual video inspection NOT_TESTED')
    service,ops,ctx,spec,_=env
    path=service.outputs/'clip.mp4'
    subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-y','-f','lavfi','-i','color=c=blue:s=64x48:r=5:d=4',
                    '-an','-c:v','libx264','-pix_fmt','yuv420p',str(path)],capture_output=True,check=True,timeout=30)
    calls=[]
    def respond(request):
        calls.append(request.method)
        if request.method=='POST':return httpx.Response(200,json={'task_id':'video-1'})
        return httpx.Response(200,json={'task':{'id':'video-1','model':'MiniMax-H3','status':'succeeded',
            'content':{'url':'https://cdn.hailuoai.com/video.mp4'},'duration':4,'resolution':'768P','ratio':'9:16'}})
    provider=MiniMaxVideoProvider('fixture-secret',model='MiniMax-H3',transport=httpx.MockTransport(respond))
    class Downloader:
        def download(self,url,*,media_type):
            assert media_type=='video'
            return SimpleNamespace(body=path.read_bytes(),mime='video/mp4')
    real_download=provider.download
    monkeypatch.setattr(provider,'download',lambda result:real_download(result,downloader=Downloader()))
    with ctx.store.transaction() as conn:
        conn.execute('UPDATE authorization_grants SET services_json=? WHERE id=?',(canonical_json([{'provider':provider.provider_id,'model':provider.model,'mode':provider.mode}]),spec['grant_id']))
    ctx=replace(ctx,payload={'schema_version':1,'generation_requests':[{'scene_id':'s1','kind':'VIDEO','prompt':'Blue desk','duration_seconds':4,'resolution':'768P'}]})
    task=SupplyTasks(service,ops,generation_providers={'VIDEO':provider},generation_rights={'VIDEO':RightsInfo.model_validate_json(canonical_json(RIGHTS))})
    first=run(task,ctx)
    assert first.state=='waiting_external' and calls==['POST']
    second=run(task,ctx)
    assert second.state=='succeeded',second.error.as_dict() if second.error else second
    third=run(task,ctx)
    assert third.next_payload==second.next_payload and calls==['POST','GET']
    assert ops.quota(ctx.work_id)['VIDEO']['used']==1
    with ctx.store.connection() as conn:assert conn.execute("SELECT COUNT(*) FROM artifacts WHERE kind='video'").fetchone()[0]==1


def test_generation_cannot_reference_other_scene(env):
    task,ctx,calls=generation(env)
    ctx=replace(ctx,payload={'schema_version':1,'generation_requests':[{'scene_id':'other-work-scene','kind':'IMAGE','prompt':'anything'}]})
    assert run(task,ctx).error.code=='invalid_generation_request' and calls==[]


def test_media_inspector_rejects_disguised_remote_playlist_before_fetch(env):
    import shutil
    if not shutil.which('ffprobe'):pytest.skip('real ffprobe unavailable')
    from easel.materials.library import LibraryVisibility,UseContext
    from easel.materials.domain import TechnicalStatus
    service,ops,ctx,_,_=env
    (service.outputs/'bad.mp4').write_text('#EXTM3U\n#EXT-X-TARGETDURATION:1\n#EXTINF:1,\nhttp://127.0.0.1:1/private.ts\n#EXT-X-ENDLIST\n')
    task=SupplyTasks(service,ops)
    handle=task.materials.ingest_input(source_root=service.outputs,relative_path='bad.mp4',
        visibility=LibraryVisibility(),context=UseContext(work_id=ctx.work_id),media_type=MediaType.VIDEO,
        source=CandidateSource(kind='user_upload'),rights=RightsInfo.model_validate_json(canonical_json(RIGHTS)))
    assert handle.asset.technical.status is TechnicalStatus.FAILED
    assert handle.asset.technical.facts['inspection_error']=='ffprobe_rejected_media'


def test_missing_external_source_is_not_misreported_as_exhausted_stock(env):
    task,ctx,calls=generation(env);ctx=replace(ctx,payload={'schema_version':1})
    class Planning:
        def context(self,ctx):pytest.fail('missing external configuration cannot silently downgrade to AI')
    task.planning=Planning()
    result=run(task,ctx)
    assert result.state=='needs_decision' and result.error.code=='capability_unavailable'
    assert '尚未配置' in result.error.user_message and calls==[]


def test_cancel_after_listing_stops_before_new_media_download(env):
    service,ops,ctx,_,source=env
    class Provider:
        provider_id='cancel-fixture';allowed_hosts=('example.org',)
        def search(self,*args,**kwargs):
            with ctx.store.transaction() as conn:conn.execute('UPDATE runs SET cancel_requested=1 WHERE id=?',(ctx.run_id,))
            return [ExternalCandidate('one',MediaType.IMAGE,'https://example.org/one.png',CandidateSource(kind='public'),RightsInfo.model_validate_json(canonical_json(RIGHTS)),SemanticInfo())]
    class Downloader:
        def download(self,*args,**kwargs):pytest.fail('cancelled task cannot start another download')
    task=SupplyTasks(service,ops,external_providers=[Provider()],downloaders={'cancel-fixture':Downloader()})
    with pytest.raises(StaleRevision):run(task,ctx)


def plan_settings(env, *, audio_mode='music', frozen_profile=None, current_profile=None):
    """Modify only isolated fixture state; no product confirmation is implied."""
    import hashlib
    _, _, ctx, _, _ = env
    with ctx.store.transaction() as conn:
        payload=json.loads(conn.execute('SELECT payload_json FROM plan_revisions WHERE work_id=? AND revision=?',
                                       (ctx.work_id,ctx.plan_revision)).fetchone()[0])
        payload['settings']['audio_mode']=audio_mode
        payload['profile_snapshot']=({'profile_ref':frozen_profile,'content':'Frozen creator facts',
            'content_hash':hashlib.sha256(b'Frozen creator facts').hexdigest()} if frozen_profile else None)
        for profile in {current_profile,frozen_profile}-{None}:
            conn.execute('INSERT OR IGNORE INTO profile_refs(id,name,created_at) VALUES(?,?,?)',(profile,profile,utc_now()))
        conn.execute('UPDATE works SET profile_ref=? WHERE id=?',(frozen_profile,ctx.work_id))
        work=ctx.store.get_work(ctx.work_id,connection=conn)
        saved=ctx.store.save_plan(ctx.work_id,payload,expected_revision=work['revision'],connection=conn)
        revision=saved['revision']
        conn.execute('UPDATE plan_revisions SET confirmed_at=? WHERE work_id=? AND revision=?',(utc_now(),ctx.work_id,revision))
        conn.execute('UPDATE runs SET plan_revision=? WHERE id=?',(revision,ctx.run_id))
        conn.execute('UPDATE tasks SET plan_revision=? WHERE id=?',(revision,ctx.task_id))
        conn.execute('UPDATE authorization_grants SET plan_revision=? WHERE work_id=?',(revision,ctx.work_id))
        conn.execute('UPDATE works SET profile_ref=? WHERE id=?',(current_profile,ctx.work_id))
    env[2]=replace(ctx,plan_revision=revision)
    return env[2]


def audio_bytes():
    import io, math, struct, wave
    target=io.BytesIO()
    with wave.open(target,'wb') as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(16000)
        wav.writeframes(b''.join(struct.pack('<h',int(6000*math.sin(2*math.pi*440*i/16000))) for i in range(16000)))
    return target.getvalue()


def reviewed_config(*, kinds=('image','audio'), rights=None):
    return {'schema_version':1,'allowed_hosts':['media.example'], 'candidates':[
        {'candidate_id':'reviewed-'+kind,'media_type':kind,'download_url':'https://media.example/'+kind,
         'source':{'kind':'public','provider':'reviewed_public','provider_asset_id':'source-'+kind,
                   'source_page':'https://media.example/asset/'+kind,'creator':'Fixture creator'},
         'rights':rights or RIGHTS,'semantic':{'caption':'Reviewed '+kind+' candidate'}} for kind in kinds]}


@pytest.mark.parametrize('audio_mode',['music','mixed'])
def test_theme_only_music_has_reviewed_audio_candidates_and_reuses_downloads(env,audio_mode):
    import shutil
    if not shutil.which('ffprobe'):pytest.skip('real ffprobe unavailable; audio admission NOT_TESTED')
    from easel.materials.application.acquisition import MediaDownloader,RemoteURLPolicy,DownloadResponse
    service,ops,ctx,_,source=env
    ctx=plan_settings(env,audio_mode=audio_mode)
    rights={**RIGHTS,'status':'ATTRIBUTION_REQUIRED','attribution_required':True,
            'attribution_text':'Fixture creator — audio candidate https://media.example/asset/audio'}
    config=reviewed_config();config['candidates'][1]['rights']=rights
    task=configured_supply(service,ops,None,{'EASEL_REVIEWED_PUBLIC_SOURCES_JSON':canonical_json(config)})
    calls=[]
    class Transport:
        def get(self,url,**kwargs):
            calls.append(url)
            assert kwargs['addresses']==('8.8.8.8',)
            body,mime=(audio_bytes(),'audio/wav') if url.endswith('/audio') else (source.read_bytes(),'image/png')
            return DownloadResponse(200,{'content-type':mime},body)
    task.supplier.downloaders['reviewed_public']=MediaDownloader(RemoteURLPolicy(('media.example',),resolver=lambda *_:('8.8.8.8',)),transport=Transport())
    first=run(task,ctx)
    assert first.state=='succeeded' and first.next_kind=='edit',first.error
    with ctx.store.connection() as conn:
        records=[dict(r) for r in conn.execute('SELECT * FROM artifacts')]
    assert {r['kind'] for r in records}=={'image','audio'}
    audio=next(r for r in records if r['kind']=='audio');metadata=json.loads(audio['metadata_json'])
    assert (service.outputs/audio['storage_ref']).read_bytes()==audio_bytes()
    assert metadata['candidate_role']=='music' and metadata['candidate_only']
    assert metadata['source']['provider']=='reviewed_public'
    assert metadata['attribution']['credit_text']==rights['attribution_text']
    assert metadata['rights']['evidence'] and metadata['technical']['has_audio']
    assert ops.quota(ctx.work_id)['IMAGE']['used']==ops.quota(ctx.work_id)['VIDEO']['used']==0
    assert run(task,ctx).next_payload==first.next_payload and len(calls)==2


def test_music_missing_source_preserves_visual_and_never_generates_music(env):
    input_media(env);plan_settings(env)
    service,ops,ctx,_,_=env
    task=configured_supply(service,ops,None,{'PEXELS_API_KEY':'fixture-key'})
    # Required image prevents Pexels lookup; Pexels has no audio capability.
    task.external_providers[0].search=lambda *a,**k:pytest.fail('Pexels cannot supply audio')
    result=run(task,ctx)
    assert result.state=='needs_decision' and result.error.code=='capability_unavailable'
    assert '音乐' in result.error.user_message
    with ctx.store.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM artifacts WHERE kind='image'").fetchone()[0]==1
        assert conn.execute('SELECT COUNT(*) FROM operations').fetchone()[0]==0


@pytest.mark.parametrize('audio_mode',['silent','voice'])
def test_modes_without_music_do_not_acquire_background_audio(env,audio_mode):
    input_media(env);plan_settings(env,audio_mode=audio_mode)
    service,ops,ctx,_,_=env
    task=configured_supply(service,ops,None,{'EASEL_REVIEWED_PUBLIC_SOURCES_JSON':canonical_json(reviewed_config(kinds=('audio',)))})
    task.external_providers[0].search=lambda *a,**k:pytest.fail('mode does not request music')
    assert run(task,ctx).state=='succeeded'


def test_corrupt_reviewed_audio_is_an_explicit_music_gap(env):
    import shutil
    if not shutil.which('ffprobe'):pytest.skip('real ffprobe unavailable')
    input_media(env);plan_settings(env)
    service,ops,ctx,_,_=env
    task=configured_supply(service,ops,None,{'EASEL_REVIEWED_PUBLIC_SOURCES_JSON':canonical_json(reviewed_config(kinds=('audio',)))})
    class Downloader:
        def download(self,*args,**kwargs):return SimpleNamespace(body=b'corrupt audio',mime='audio/wav')
    task.supplier.downloaders['reviewed_public']=Downloader()
    result=run(task,ctx)
    assert result.error.code=='music_material_gap'
    with ctx.store.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM artifacts WHERE kind='audio'").fetchone()[0]==0
        assert conn.execute('SELECT COUNT(*) FROM operations').fetchone()[0]==0


def test_library_audio_reused_without_external_configuration(env):
    import shutil
    if not shutil.which('ffprobe'):pytest.skip('real ffprobe unavailable')
    from easel.materials.library import LibraryVisibility,UseContext
    input_media(env);plan_settings(env)
    service,ops,ctx,_,_=env
    path=service.outputs/'music.wav';path.write_bytes(audio_bytes())
    task=SupplyTasks(service,ops)
    handle=task.materials.ingest_input(source_root=service.outputs,relative_path=path.name,visibility=LibraryVisibility(),
        context=UseContext(work_id=ctx.work_id),media_type=MediaType.AUDIO,source=CandidateSource(kind='user_upload'),
        rights=RightsInfo.model_validate_json(canonical_json(RIGHTS)),semantic=SemanticInfo(caption='背景音乐候选'))
    result=run(task,ctx)
    assert result.state=='succeeded'
    with ctx.store.connection() as conn:
        metadata=json.loads(conn.execute("SELECT metadata_json FROM artifacts WHERE kind='audio'").fetchone()[0])
    assert metadata['asset_ref']==handle.asset_ref


@pytest.mark.parametrize('frozen_profile',['original-profile',None])
def test_supply_uses_frozen_plan_profile_not_reassigned_work(env,frozen_profile):
    from easel.materials.library import LibraryVisibility,UseContext
    service,ops,ctx,_,source=env
    ctx=plan_settings(env,audio_mode='silent',frozen_profile=frozen_profile,current_profile='other-profile')
    task=SupplyTasks(service,ops)
    for profile,color in [('other-profile','red'),(frozen_profile,'blue')]:
        path=service.outputs/(color+'.png');Image.new('RGB',(32,24),color).save(path)
        task.materials.ingest_input(source_root=service.outputs,relative_path=path.name,visibility=LibraryVisibility(profile_ref=profile),
            context=UseContext(work_id=ctx.work_id),media_type=MediaType.IMAGE,source=CandidateSource(kind='user_upload'),
            rights=RightsInfo.model_validate_json(canonical_json(RIGHTS)),semantic=SemanticInfo(caption='桌面素材'))
    result=run(task,ctx)
    assert result.state=='succeeded'
    with ctx.store.connection() as conn:record=dict(conn.execute('SELECT * FROM artifacts').fetchone())
    assert json.loads(record['metadata_json'])['material_scope']['profile_ref']==frozen_profile
    assert Image.open(service.outputs/record['storage_ref']).getpixel((0,0))==(0,0,255)


@pytest.mark.parametrize('invalid',['unknown_rights','missing_asset_evidence','other_host','private_host','wildcard','missing_source','duplicate'])
def test_invalid_public_source_configuration_blocks_before_download(env,invalid):
    service,ops,ctx,_,_=env
    config=reviewed_config()
    if invalid=='unknown_rights':config['candidates'][0]['rights']={'status':'UNKNOWN'}
    if invalid=='missing_asset_evidence':config['candidates'][0]['rights']={**RIGHTS,'evidence':[{'kind':'site_terms','reference':'https://media.example/terms'}]}
    if invalid=='other_host':config['candidates'][0]['download_url']='https://unapproved.example/image'
    if invalid=='private_host':config['allowed_hosts']=['127.0.0.1']
    if invalid=='wildcard':config['allowed_hosts']=['*.example']
    if invalid=='missing_source':del config['candidates'][0]['source']['source_page']
    if invalid=='duplicate':config['candidates'].append(config['candidates'][0])
    task=configured_supply(service,ops,None,{'EASEL_REVIEWED_PUBLIC_SOURCES_JSON':canonical_json(config)})
    assert task.external_providers==()
    result=run(task,ctx)
    assert result.error.code=='source_configuration_invalid'
    with ctx.store.connection() as conn:assert conn.execute('SELECT COUNT(*) FROM artifacts').fetchone()[0]==0


def test_public_source_configuration_file_is_explicit_and_symlinks_rejected(env,tmp_path):
    service,ops,ctx,_,_=env
    path=tmp_path/'reviewed.json';path.write_text(canonical_json(reviewed_config()))
    assert len(configured_supply(service,ops,None,{'EASEL_REVIEWED_PUBLIC_SOURCES_JSON':str(path)}).external_providers)==1
    link=tmp_path/'link.json';link.symlink_to(path)
    assert run(configured_supply(service,ops,None,{'EASEL_REVIEWED_PUBLIC_SOURCES_JSON':str(link)}),ctx).error.code=='source_configuration_invalid'
