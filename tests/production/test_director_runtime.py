"""Real catalog/handler/worker paths with synthetic local AV, never a live model."""
import asyncio
import base64
import hashlib
from io import BytesIO
import json
from pathlib import Path
import shutil
import subprocess

from PIL import Image
import pytest

from easel.production.catalog import CreativeCatalog
from easel.production.errors import ProductionError
from easel.production.operations import OperationService
from easel.production.planning import PlanningTasks
from easel.production.service import WorkService
from easel.production.store import Store
from easel.production.worker import Worker
from .test_planning_runtime import Transport

IDENTITY={'provider':'direct-api','model':'fixture','mode':'structured'}
ANALYSIS={'visual_style':'以不同颜色主体的固定机位画面形成对照',
          'storytelling':'围绕内容建立对比，结尾方式保持开放', 'rhythm':'随信息密度改变节奏',
          'sound':'保留有意义的原声，音乐不能覆盖表达', 'typography':'少量清楚字幕',
          'invariants':['构图清楚','风格保留，不复制人物经历'],
          'freedom':['题材与结构按内容变化'],'evidence_notes':['已观察两个不同画面和完整合成音轨']}


@pytest.fixture(scope='module')
def clips(tmp_path_factory):
    ffmpeg=shutil.which('ffmpeg')
    if not ffmpeg or not shutil.which('ffprobe'):pytest.skip('real FFmpeg/ffprobe unavailable; media binding NOT_TESTED')
    root=tmp_path_factory.mktemp('director-reference-clips')
    paths=[]
    for color,frequency in [('red',440),('blue',880)]:
        path=root/(color+'.mp4')
        subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-y','-f','lavfi','-i',f'color=c={color}:s=96x64:r=10:d=1',
            '-f','lavfi','-i',f'sine=frequency={frequency}:sample_rate=16000:duration=1',
            '-c:v','libx264','-preset','ultrafast','-pix_fmt','yuv420p','-c:a','aac','-shortest',str(path)],check=True,capture_output=True,timeout=30)
        paths.append(path)
    return paths


def service_at(root):
    profiles=root/'profiles';(profiles/'selected').mkdir(parents=True)
    (profiles/'selected'/'identity.md').write_text('我是一名正在学习金融和科技的创作者。',encoding='utf8')
    store=Store(root/'outputs'/'_production'/'production.sqlite3');store.initialize()
    return WorkService(store,outputs=root/'outputs',profiles=profiles)


def add_media(service,work,path,*,name=None,usage='reference',session='test-reference-session'):
    scope=hashlib.sha256(session.encode()).hexdigest()[:20]
    locator=f'_inbox/{scope}/fixture/{name or path.name}'
    target=service.outputs/locator;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
    attachment={'id':hashlib.sha256((scope+'\0'+locator).encode()).hexdigest()[:24],'path':locator}
    result=service.command('input',{'session_id':session,'attachment':attachment,'usage':usage},
        command_id='input-'+hashlib.sha256(locator.encode()).hexdigest(),work_id=work,
        expected_revision=service.store.get_work(work)['revision'])
    return result['input_id'],target


def director_setup(tmp_path,clips,*,authorized=True,audio=True,answer=None,analysis_scope="full"):
    service=service_at(tmp_path)
    work=service.command('create',{'title':'风格参考拆解','profile_ref':'selected','session_id':'test-reference-session'},command_id='create')['work_id']
    # The misleading file names are intentionally not the actual media contents.
    inputs=[add_media(service,work,path,name='另一位创作者经历-'+str(i)+'.mp4') for i,path in enumerate(clips)]
    catalog=CreativeCatalog(service)
    created=catalog.command('directors','create',{'name':'保持构图与叙事自由','work_id':work,
        'work_revision':service.store.get_work(work)['revision'],'reference_input_ids':[i[0] for i in inputs],'analysis_scope':analysis_scope},command_id='director-create')
    if authorized:service.command('grant',{'purpose':'planning','services':[IDENTITY],'target_ref':created['run_id']},
        command_id='grant',work_id=work,expected_revision=service.store.get_work(work)['revision'])
    transport=Transport(answer or ANALYSIS)
    if audio:transport.capabilities=transport.capabilities|{'audio'}
    planning=PlanningTasks(service,OperationService(service.store),transport,IDENTITY,'fixture-v1')
    worker=Worker(service.store,{'analyze_director':planning.analyze_director})
    return service,work,inputs,catalog,created,transport,planning,worker


def claim_context(worker):
    lease=worker.claim_next();assert lease
    task=worker._next(lease);assert task
    return worker._start(lease,task['id'],task['kind'])


def test_director_handler_binds_two_actual_videos_audio_and_reference_evidence(tmp_path,clips):
    service,work,inputs,catalog,created,transport,planning,worker=director_setup(tmp_path,clips)
    assert asyncio.run(worker.run_once()) and transport.calls==1
    versions=catalog.list('directors')[0]['versions'];assert len(versions)==1
    version=versions[0]
    assert [e['input_id'] for e in version['evidence']]==[i[0] for i in inputs]
    assert all(e['frame_times'] and e['audio_observed'] for e in version['evidence'])
    assert [e['digest'] for e in version['evidence']]==[service._file_hash(p) for _,p in inputs]
    assert not version['accepted_at'] and not version['style_confirmed']
    messages=transport.requests[0][0]
    from easel.production.expression_policy import RULES
    assert RULES['core'] not in messages[0]['content']
    content=messages[1]['content']
    data=json.loads(content[0]['text'])
    assert data['profile']['identity']=='我是一名正在学习金融和科技的创作者。'
    assert '另一位创作者经历' not in json.dumps(data['profile'],ensure_ascii=False)
    assert '不要将参考中的人物事实变成主人设' in messages[0]['content']
    markers=[block['text'] for block in content if block['type']=='text' and '导演参考输入句柄' in block['text']]
    assert len(markers)==2 and all(any(id in text for text in markers) for id,_ in inputs)
    colors=[]
    for block in content:
        if block['type']=='image_url':
            raw=base64.b64decode(block['image_url']['url'].split(',',1)[1])
            with Image.open(BytesIO(raw)) as image:colors.append(image.convert('RGB').getpixel((image.width//2,image.height//2)))
    assert any(r>200 and b<30 for r,g,b in colors) and any(b>200 and r<30 for r,g,b in colors)
    audio=[base64.b64decode(b['input_audio']['data']) for b in content if b['type']=='input_audio']
    assert len(audio)==2 and all(a.startswith(b'RIFF') for a in audio) and audio[0]!=audio[1]
    # Style extraction does not mutate the existing six-dimensional identity.
    assert (service.profiles/'selected'/'identity.md').read_text(encoding='utf8')==data['profile']['identity']


def test_director_domain_commit_survives_crash_before_worker_finish(tmp_path,clips):
    service,work,inputs,catalog,created,transport,planning,worker=director_setup(tmp_path,clips)
    ctx=claim_context(worker)
    first=asyncio.run(planning.analyze_director(ctx));assert first.state=='succeeded'
    with service.store.connection() as conn:
        task=conn.execute('SELECT * FROM tasks WHERE id=?',(ctx.task_id,)).fetchone()
        assert task['state']=='running' and json.loads(task['payload_json'])['business_result']==first.result
    # Re-entering with an old in-memory context must also read committed state.
    assert asyncio.run(planning.analyze_director(ctx)).result==first.result
    with service.store.transaction() as conn:conn.execute('UPDATE runs SET lease_expires_at=0 WHERE id=?',(ctx.run_id,))
    fresh_service=WorkService(Store(service.store.path),outputs=service.outputs,profiles=service.profiles)
    fresh_planning=PlanningTasks(fresh_service,OperationService(fresh_service.store),transport,IDENTITY,'fixture-v1')
    recovered=Worker(fresh_service.store,{'analyze_director':fresh_planning.analyze_director},owner_id='restarted-worker')
    assert asyncio.run(recovered.run_once())
    assert transport.calls==1
    versions=CreativeCatalog(fresh_service).list('directors')[0]['versions']
    assert len(versions)==1 and versions[0]['id']==first.result['director_revision_id']
    assert fresh_service.snapshot(work)['tasks'][0]['state']=='succeeded'
    with fresh_service.store.connection() as conn:assert conn.execute('SELECT COUNT(*) FROM operations').fetchone()[0]==1


@pytest.mark.parametrize('condition,code',[('tampered','reference_changed'),('no_audio','capability_unavailable'),('unauthorized','permission_missing')])
def test_director_never_claims_analysis_without_real_media_and_permission(tmp_path,clips,condition,code):
    values=director_setup(tmp_path,clips,authorized=condition!='unauthorized',audio=condition!='no_audio')
    service,work,inputs,catalog,created,transport,planning,worker=values
    if condition=='tampered':inputs[0][1].write_bytes(b'changed reference')
    asyncio.run(worker.run_once())
    tasks=service.snapshot(work)['tasks']
    assert tasks[0]['state']=='needs_decision' and json.loads(tasks[0]['error_json'])['code']==code
    assert transport.calls==0 and not catalog.list('directors')[0]['versions']


@pytest.mark.parametrize('refs',[[], 'a-string', ['same','same'],[{}]])
def test_catalog_rejects_empty_duplicate_or_untyped_reference_lists(tmp_path,refs):
    service=service_at(tmp_path)
    work=service.command('create',{'title':'test'},command_id='create')['work_id']
    with pytest.raises(ProductionError) as error:
        CreativeCatalog(service).command('directors','create',{'name':'director','work_id':work,'work_revision':1,'reference_input_ids':refs},command_id='invalid')
    assert error.value.code=='invalid_input'
    with service.store.connection() as conn:
        assert conn.execute('SELECT COUNT(*) FROM directors').fetchone()[0]==0
        assert conn.execute('SELECT COUNT(*) FROM runs').fetchone()[0]==0


def test_handler_rejects_empty_reference_even_if_bad_task_was_persisted(tmp_path,clips):
    service,work,_,catalog,_,transport,planning,worker=director_setup(tmp_path,clips)
    with service.store.transaction() as conn:
        task=conn.execute('SELECT * FROM tasks').fetchone();payload=json.loads(task['payload_json']);payload['reference_input_ids']=[]
        conn.execute('UPDATE tasks SET payload_json=? WHERE id=?',(json.dumps(payload),task['id']))
    asyncio.run(worker.run_once())
    assert json.loads(service.snapshot(work)['tasks'][0]['error_json'])['code']=='invalid_reference' and transport.calls==0
    assert not catalog.list('directors')[0]['versions']


def test_model_cannot_add_personal_profile_fields_to_director_result(tmp_path,clips):
    bad={**ANALYSIS,'profile':{'memory':'把参考人物经历写成我的经历'}}
    service,work,_,catalog,_,transport,planning,worker=director_setup(tmp_path,clips,answer=bad)
    asyncio.run(worker.run_once())
    assert json.loads(service.snapshot(work)['tasks'][0]['error_json'])['code']=='invalid_model_output'
    assert not catalog.list('directors')[0]['versions'] and transport.calls==2
    assert '参考人物经历' not in (service.profiles/'selected'/'identity.md').read_text(encoding='utf8')



def test_explicit_visual_director_scope_uses_real_frames_without_claiming_reference_audio(tmp_path,clips):
    service,work,inputs,catalog,created,transport,planning,worker=director_setup(tmp_path,clips,audio=False,analysis_scope='visual')
    before=[service._file_hash(path) for _,path in inputs]
    assert asyncio.run(worker.run_once())
    version=catalog.list('directors')[0]['versions'][0]
    assert all(e['analysis_scope']=='visual' and not e['audio_observed'] and e['audio_semantics']=='not_tested' for e in version['evidence'])
    assert '参考音轨未分析' in version['style']['sound']
    content=transport.requests[0][0][1]['content']
    assert any(b['type']=='image_url' for b in content)
    assert not any(b['type']=='input_audio' for b in content)
    from types import SimpleNamespace
    blocks,required=asyncio.run(planning.observe_inputs(SimpleNamespace(work_id=work)))
    assert 'audio' not in required and not any(b['type']=='input_audio' for b in blocks)
    assert [service._file_hash(path) for _,path in inputs]==before


def test_visual_scope_cannot_remove_observation_from_must_use_input(tmp_path,clips):
    service=service_at(tmp_path)
    work=service.command('create',{'title':'must use','session_id':'test-reference-session'},command_id='create')['work_id']
    ref,_=add_media(service,work,clips[0],usage='must_use')
    with pytest.raises(ProductionError,match='必用素材'):
        CreativeCatalog(service).command('directors','create',{'name':'director','work_id':work,'work_revision':service.store.get_work(work)['revision'],'reference_input_ids':[ref],'analysis_scope':'visual'},command_id='invalid-scope')
    assert not service.snapshot(work)['runs']
