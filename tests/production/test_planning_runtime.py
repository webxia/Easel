"""Offline protocol tests exercise real worker, ledger and immutable plan persistence."""
import asyncio
import json
import uuid
import pytest
from easel.production.store import Store
from easel.production.service import WorkService
from easel.production.worker import Worker
from easel.production.operations import OperationService
from easel.production.planning import PlanningTasks


class Transport:
    capabilities=frozenset({'text','structured','image','tools'})
    def __init__(self,answer,fail=False):
        self.answer,self.calls,self.fail=answer,0,fail
        self.requests=[]
    async def complete(self,*args):
        self.calls+=1
        self.requests.append(json.loads(json.dumps(args)))
        if self.fail:raise TimeoutError('no receipt')
        return {'content':json.dumps(self.answer)}


def setup(tmp_path,fail=False):
    store=Store(tmp_path/'outputs/_production/production.sqlite3');store.initialize()
    service=WorkService(store,outputs=tmp_path/'outputs',profiles=tmp_path/'profiles')
    settings={'duration_seconds':3,'aspect_ratio':'16:9','audio_mode':'silent'}
    work=service.command('create',{'title':'实际规划','input_text':'科技应用','settings':settings},command_id='create')['work_id']
    identity={'provider':'direct-api','model':'fixture','mode':'structured'}
    service.command('plan',{'services':[identity]},work_id=work,expected_revision=1,command_id='plan')
    answer={'title':'科技应用','summary':'一项具体例子','script':'技术服务人。','scenes':[{'id':'s1','purpose':'解释','visual':'科技画面','narration':'技术服务人。','duration_seconds':3,'required_input_ids':[]}],'settings':settings}
    transport=Transport(answer,fail)
    planning=PlanningTasks(service,OperationService(store),transport,identity,'fixture-v1')
    worker=Worker(store,{'plan':planning.plan})
    return service,work,transport,worker


def test_worker_creates_proposal_and_records_model_receipt(tmp_path):
    service,id,transport,worker=setup(tmp_path)
    assert asyncio.run(worker.run_once())
    snap=service.snapshot(id)
    assert snap['state']=='awaiting_confirmation',snap['tasks']
    assert len(snap['plans'])==1
    assert not snap['plans'][0]['confirmed_at']
    assert transport.calls==1
    with service.store.connection() as conn:
        op=dict(conn.execute('SELECT * FROM operations').fetchone())
    assert op['kind']=='MODEL' and op['state']=='succeeded'
    assert not asyncio.run(worker.run_once())
    assert transport.calls==1


def test_uncertain_model_call_is_not_reissued_on_resume(tmp_path):
    service,id,transport,worker=setup(tmp_path,True)
    asyncio.run(worker.run_once())
    with service.store.connection() as conn:op=dict(conn.execute('SELECT * FROM operations').fetchone())
    assert op['state']=='unknown'
    # Retry the leased task via worker recovery; intent identity and request remain unchanged.
    for _ in range(4):asyncio.run(worker.run_once())
    assert transport.calls==1
    assert not service.snapshot(id)['plans']


def planning_media_setup(tmp_path,*,authorize=True,image_capability=True):
    from PIL import Image
    from .test_director_runtime import service_at,add_media,IDENTITY
    service=service_at(tmp_path)
    work=service.command('create',{'title':'用户素材规划','session_id':'test-reference-session','profile_ref':'selected',
        'settings':{'duration_seconds':3,'aspect_ratio':'16:9','audio_mode':'silent'}},command_id='create')['work_id']
    source=tmp_path/'source.png';Image.new('RGB',(96,64),'red').save(source)
    input_id,path=add_media(service,work,source,name='误导名称-blue.png',usage='must_use')
    answer={'title':'基于真实红色图片','summary':'使用登记图片','script':'保持本次观点',
        'scenes':[{'id':'s1','purpose':'展示','visual':'红色素材','required_input_ids':[input_id]}],
        'settings':{'duration_seconds':3,'aspect_ratio':'16:9','audio_mode':'silent'}}
    transport=Transport(answer)
    if not image_capability:transport.capabilities=transport.capabilities-{'image'}
    service.command('plan',{'services':[IDENTITY] if authorize else []},command_id='plan',work_id=work,
        expected_revision=service.store.get_work(work)['revision'])
    planning=PlanningTasks(service,OperationService(service.store),transport,IDENTITY,'fixture-v1')
    worker=Worker(service.store,{'plan':planning.plan})
    return service,work,input_id,path,transport,planning,worker


def test_planning_observes_real_image_and_required_input_binding(tmp_path):
    import base64,shutil
    from io import BytesIO
    from PIL import Image
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):pytest.skip('FFmpeg/ffprobe unavailable')
    service,work,input_id,path,transport,planning,worker=planning_media_setup(tmp_path)
    asyncio.run(worker.run_once())
    snap=service.snapshot(work)
    assert len(snap['plans'])==1 and snap['plans'][0]['plan']['scenes'][0]['required_input_ids']==[input_id]
    content=transport.requests[0][0][1]['content']
    markers=[b['text'] for b in content if b['type']=='text']
    assert any(input_id in text and 'must_use' in text for text in markers)
    images=[b for b in content if b['type']=='image_url'];assert images
    image=Image.open(BytesIO(base64.b64decode(images[0]['image_url']['url'].split(',',1)[1])))
    red,green,blue=image.convert('RGB').getpixel((image.width//2,image.height//2))
    assert red>200 and blue<30  # data is red even though the filename claims blue
    with service.store.connection() as conn:
        assert conn.execute('SELECT COUNT(*) FROM operations').fetchone()[0]==1
    assert not snap['plans'][0]['confirmed_at']


@pytest.mark.parametrize('case,code',[('tampered','input_changed'),('no_image','capability_unavailable'),('unauthorized','permission_missing')])
def test_planning_blocks_unobserved_or_unauthorized_media(tmp_path,case,code):
    import shutil
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):pytest.skip('FFmpeg/ffprobe unavailable')
    service,work,input_id,path,transport,planning,worker=planning_media_setup(tmp_path,authorize=case!='unauthorized',image_capability=case!='no_image')
    if case=='tampered':path.write_bytes(b'changed')
    asyncio.run(worker.run_once())
    snap=service.snapshot(work)
    assert json.loads(snap['tasks'][0]['error_json'])['code']==code
    assert snap['tasks'][0]['state']=='needs_decision' and transport.calls==0 and not snap['plans']


def test_planning_commit_before_worker_finish_reuses_proposal_after_restart(tmp_path):
    from .test_director_runtime import claim_context,IDENTITY
    service,work,transport,worker=setup(tmp_path)
    planning=worker.handlers['plan'].__self__
    ctx=claim_context(worker)
    # A controlled tool can persist extra evidence during a model round.
    with service.store.transaction() as conn:
        payload=json.loads(conn.execute('SELECT payload_json FROM tasks WHERE id=?',(ctx.task_id,)).fetchone()[0])
        payload['evidence_receipt']={'retained':True}
        conn.execute('UPDATE tasks SET payload_json=? WHERE id=?',(json.dumps(payload),ctx.task_id))
    first=asyncio.run(planning.plan(ctx));assert first.state=='succeeded'
    with service.store.connection() as conn:
        task=conn.execute('SELECT * FROM tasks WHERE id=?',(ctx.task_id,)).fetchone()
        saved=json.loads(task['payload_json'])
        assert saved['business_result']==first.result and saved['evidence_receipt']['retained']
        assert task['state']=='running'
    assert asyncio.run(planning.plan(ctx)).result==first.result
    with service.store.transaction() as conn:conn.execute('UPDATE runs SET lease_expires_at=0 WHERE id=?',(ctx.run_id,))
    fresh=WorkService(Store(service.store.path),outputs=service.outputs,profiles=service.profiles)
    tasks=PlanningTasks(fresh,OperationService(fresh.store),transport,IDENTITY,'fixture-v1')
    restart=Worker(fresh.store,{'plan':tasks.plan},owner_id='restart')
    assert asyncio.run(restart.run_once())
    assert len(fresh.snapshot(work)['plans'])==1 and transport.calls==1


@pytest.mark.parametrize('old_profile',[True,False])
def test_replanning_uses_frozen_profile_identity_with_frozen_content(tmp_path,old_profile):
    from .test_director_runtime import service_at,IDENTITY
    service=service_at(tmp_path)
    (service.profiles/'other').mkdir();(service.profiles/'other'/'identity.md').write_text('别的画像内容',encoding='utf8')
    values={'title':'版本依据','settings':{'duration_seconds':3,'aspect_ratio':'16:9','audio_mode':'silent'}}
    if old_profile:values['profile_ref']='selected'
    work=service.command('create',values,command_id='create')['work_id']
    original={'title':'旧方案','summary':'保持依据','script':'观点不变','scenes':[{'id':'s1','purpose':'表达','visual':'清楚画面'}],
        'settings':values['settings']}
    saved=service.command('plan',{'generate':False,'plan':original},command_id='original-plan',work_id=work,expected_revision=1)
    original_snapshot=service.snapshot(work)['plans'][0]['plan']['profile_snapshot']
    with service.store.transaction() as conn:
        # Simulate a work reassigned after retaining an old version. The next
        # planning task deliberately binds that version as its revision basis.
        other=service._profile(conn,'other')
        conn.execute('UPDATE works SET profile_ref=? WHERE id=?',(other,work))
        conn.execute('UPDATE plan_revisions SET confirmed_at=? WHERE work_id=?',('confirmed',work))
    (service.profiles/'selected'/'identity.md').write_text('当前文件已改动，不能覆盖旧版本事实',encoding='utf8')
    service.command('plan',{'services':[IDENTITY]},command_id='replan',work_id=work,expected_revision=service.store.get_work(work)['revision'])
    with service.store.transaction() as conn:
        task=conn.execute('SELECT * FROM tasks').fetchone();payload=json.loads(task['payload_json']);payload['base_plan_revision']=1
        conn.execute('UPDATE tasks SET payload_json=? WHERE id=?',(json.dumps(payload),task['id']))
    transport=Transport(original)
    planning=PlanningTasks(service,OperationService(service.store),transport,IDENTITY,'fixture-v1')
    worker=Worker(service.store,{'plan':planning.plan})
    from .test_director_runtime import claim_context
    ctx=claim_context(worker)
    context=planning.context(ctx)
    assert context.profile_ref==(original_snapshot['profile_ref'] if original_snapshot else None)
    assert context.profile==(json.loads(original_snapshot['content']) if original_snapshot else {})
    result=asyncio.run(planning.plan(ctx));assert result.state=='succeeded'
    newest=service.snapshot(work)['plans'][0]['plan']
    assert newest['profile_snapshot']==original_snapshot
    model_context=json.loads(transport.requests[0][0][1]['content'][0]['text'])
    assert model_context['profile']==context.profile and '别的画像内容' not in json.dumps(model_context['profile'],ensure_ascii=False)
