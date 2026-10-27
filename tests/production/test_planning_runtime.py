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
        if args[2].get('title') == 'DraftReview':
            return {'content': json.dumps({'verdict':'pass','findings':[]})}
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
    assert snap['state']=='awaiting_confirmation',snap['tasks'][0].get('error_json')
    assert len(snap['plans'])==1
    assert not snap['plans'][0]['confirmed_at']
    assert transport.calls==1
    from easel.production.expression_policy import RULES
    assert RULES["write"] in transport.requests[0][0][0]["content"]
    with service.store.connection() as conn:
        op=dict(conn.execute('SELECT * FROM operations').fetchone())
    assert op['kind']=='MODEL' and op['state']=='succeeded'
    assert not asyncio.run(worker.run_once())
    assert transport.calls==1


@pytest.mark.parametrize('changes_enabled',[False,True])
@pytest.mark.parametrize('field',['subtitles','voice'])
def test_partial_settings_compare_as_contract_values(tmp_path,changes_enabled,field):
    service,work,transport,worker=setup(tmp_path)
    # The entry API legitimately stores a partial subtitle patch. The model's
    # validated response expands its defaults; equivalent values must pass.
    with service.store.transaction() as conn:
        settings=json.loads(conn.execute('SELECT settings_json FROM works WHERE id=?',(work,)).fetchone()[0])
        settings[field]={'enabled':False} if field=='subtitles' else {'provider':'local','model':'offline','voice_id':'fixed','engine':'local'}
        conn.execute('UPDATE works SET settings_json=? WHERE id=?',(json.dumps(settings),work))
    transport.answer['settings'][field]={'enabled':changes_enabled} if field=='subtitles' else {**settings[field],'voice_id':'changed' if changes_enabled else 'fixed'}
    asyncio.run(worker.run_once())
    snapshot=service.snapshot(work)
    assert snapshot['state']==('needs_decision' if changes_enabled else 'awaiting_confirmation')
    if changes_enabled:
        assert json.loads(snapshot['tasks'][0]['error_json'])['code']=='plan_constraint_changed'
        assert snapshot['plans']==[]
    else:
        saved=snapshot['plans'][0]['plan']['settings'][field]
        assert (saved['enabled'] is False) if field=='subtitles' else (saved['voice_id']=='fixed' and saved['parameters']=={})


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
def test_replanning_uses_frozen_profile_identity_with_frozen_content(tmp_path,old_profile,monkeypatch):
    from .test_director_runtime import service_at,IDENTITY
    service=service_at(tmp_path)
    (service.profiles/'other').mkdir();(service.profiles/'other'/'identity.md').write_text('别的画像内容',encoding='utf8')
    values={'title':'版本依据','settings':{'duration_seconds':3,'aspect_ratio':'16:9','audio_mode':'silent'}}
    if old_profile:values['profile_ref']='selected'
    work=service.command('create',values,command_id='create')['work_id']
    original={'title':'旧方案','summary':'保持依据','script':'观点不变','scenes':[{'id':'s1','purpose':'表达','visual':'清楚画面'}],
        'settings':values['settings']}
    saved=service.command('plan',{'generate':False,'plan':original},command_id='original-plan',work_id=work,expected_revision=1)
    original_plan=service.snapshot(work)['plans'][0]['plan']
    original_snapshot=original_plan['profile_snapshot']
    from easel.production import expression_policy
    monkeypatch.setattr(expression_policy,'RULES',{**expression_policy.RULES,'core':'changed current defaults'})
    with service.store.transaction() as conn:
        # Simulate a work reassigned after retaining an old version. The next
        # planning task deliberately binds that version as its revision basis.
        other=service._profile(conn,'other')
        conn.execute('UPDATE works SET profile_ref=? WHERE id=?',(other,work))
        conn.execute('UPDATE plan_revisions SET confirmed_at=? WHERE work_id=?',('confirmed',work))
    (service.profiles/'selected'/'identity.md').write_text('当前文件已改动，不能覆盖旧版本事实',encoding='utf8')
    # Isolate the version-bound handler: public plan commands correctly reject
    # an unscoped replacement of an already-confirmed plan.
    with service.store.transaction() as conn:
        from easel.production.service import row
        bound=row(conn,'works',work)
        service._insert_grant(conn,bound,'planning',{'services':[IDENTITY]})
        service._run(conn,bound,'planning',payload={'creation_basis':service._basis(conn,bound)})
    with service.store.transaction() as conn:
        task=conn.execute('SELECT * FROM tasks').fetchone();payload=json.loads(task['payload_json']);payload['base_plan_revision']=1;payload['request']='新反馈：不使用图解，保留原身份与其他设置'
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
    assert {k:v for k,v in newest['conversation_basis'].items() if k!='creative_request'}==original_plan['conversation_basis']
    assert newest['conversation_basis']['creative_request']=='新反馈：不使用图解，保留原身份与其他设置'
    assert context.expression_policy==original_plan['conversation_basis']['expression_policy']
    model_context=json.loads(transport.requests[0][0][1]['content'][0]['text'])
    assert model_context['profile']==context.profile and '别的画像内容' not in json.dumps(model_context['profile'],ensure_ascii=False)


def test_fixed_voice_parameters_are_program_owned(tmp_path):
    service,work,transport,worker=setup(tmp_path)
    voice={'provider':'local','model':'offline','voice_id':'fixed','engine':'local','parameters':{'speed':1}}
    with service.store.transaction() as conn:
        settings=json.loads(conn.execute('SELECT settings_json FROM works WHERE id=?',(work,)).fetchone()[0])
        settings['voice']=voice
        conn.execute('UPDATE works SET settings_json=? WHERE id=?',(json.dumps(settings),work))
    transport.answer['settings']['voice']={**voice,'parameters':{'speed':1.4,'volume':1,'pitch':0}}
    asyncio.run(worker.run_once())
    snapshot=service.snapshot(work)
    assert snapshot['state']=='awaiting_confirmation'
    assert snapshot['plans'][0]['plan']['settings']['voice']==voice
    assert transport.calls==1


@pytest.mark.parametrize('field',['voice','duration_seconds','aspect_ratio','audio_mode','subtitles','visual'])
@pytest.mark.parametrize('audio_mode',['voice','mixed'])
def test_narration_revision_protects_frozen_choices(tmp_path,field,audio_mode):
    from easel.production.planning import VoiceReadyCreativePlan,validate_narration_revision
    service,work,transport,worker=setup(tmp_path)
    plan=VoiceReadyCreativePlan.model_validate(transport.answer)
    plan.settings.audio_mode=audio_mode
    base=plan.model_dump(mode='json')
    plan.scenes[0].narration='重新说清同一个意思。'
    validate_narration_revision(plan,base)
    altered=json.loads(json.dumps(base))
    if field=='visual':altered['scenes'][0]['visual']='不同画面'
    else:altered['settings'][field]='different'
    with pytest.raises(ValueError):validate_narration_revision(plan,altered)


def test_runtime_projects_real_generation_readiness(tmp_path,monkeypatch):
    from easel.production.runtime import create_runtime
    from easel.production import supply_tasks
    expected=[{'kind':'IMAGE','available':True,'readiness_note':'grant required'},
              {'kind':'VIDEO','available':False,'reason':'capability_unavailable'}]
    monkeypatch.setattr(supply_tasks,'supply_capabilities',lambda settings:expected)
    runtime=create_runtime(tmp_path)
    assert runtime.planning.execution_capabilities['generation']==expected
    assert 'grant' in runtime.planning.execution_capabilities['generation_authorization']


@pytest.mark.parametrize('updated_basis',[False,True])
def test_replan_carries_original_plan_and_explicit_changes_without_production(tmp_path,updated_basis):
    service,work,transport,worker=setup(tmp_path)
    asyncio.run(worker.run_once())
    if updated_basis:
        service.command('basis',{'input_text':'增加本轮明确表达要求'},work_id=work,
                        expected_revision=service.snapshot(work)['revision'],command_id='basis-before-replan')
        assert service.snapshot(work)['current_plan_revision'] is None
    with service.store.connection() as conn:
        from easel.production.service import row
        target=service.replanning_target(conn,row(conn,'works',work))
    snap=service.snapshot(work)
    service.command('plan',{'intent':'replan','request':'把开头改成具体动作，保留其他内容','replanning_target':target},
        work_id=work,expected_revision=snap['revision'],command_id='replan')
    asyncio.run(worker.run_once())
    request=transport.requests[-1][0]
    data=json.loads(request[1]['content'][0]['text'])
    assert data['plan']['script']==transport.answer['script']
    assert '本轮改稿要求' in data['brief']
    snap=service.snapshot(work)
    assert snap['state']=='awaiting_confirmation'
    assert len(snap['plans'])==2 and not snap['plans'][-1]['confirmed_at']
    assert all(t['kind']=='plan' for t in snap['tasks'])


def test_sparse_plan_correction_preserves_unchanged_fields_and_receipt_provenance(tmp_path):
    from easel.production.planning import CreativePlanChanges,merge_plan_changes,received_plan
    from easel.production.service import encode
    _,_,transport,_=setup(tmp_path)
    base=transport.answer
    changes=CreativePlanChanges.model_validate({'summary':'更清楚的摘要'})
    merged=merge_plan_changes(changes,base)
    assert merged.script==base['script'] and merged.scenes[0].visual==base['scenes'][0]['visual']
    op={'receipt_json':encode({'result':{'message':{'content':'```json\n{"summary":"更清楚的摘要"}\n```'}}}),
        'request_json':encode({'schema':{'title':'CreativePlanChanges'},'messages':[{},
            {'content':[{'type':'text','text':encode({'plan':base})}]}]})}
    assert received_plan(op)==merged
    with pytest.raises(ValueError):merge_plan_changes(CreativePlanChanges.model_validate({'scenes':[]}),base)
    with pytest.raises(ValueError):CreativePlanChanges.model_validate({'quota':999})


@pytest.mark.parametrize('fixed', [True, False])
def test_voice_drafts_review_explicit_requirements_before_freezing(tmp_path, fixed):
    service,work,transport,worker=setup(tmp_path)
    from easel.production.service import encode
    voice={'provider':'fixture','model':'speech','engine':'fixture','voice_id':'fixed'}
    settings={'schema_version':1,'audio_mode':'voice','voice':voice,'aspect_ratio':'16:9'}
    if fixed:settings['duration_seconds']=20
    with service.store.transaction() as conn:
        conn.execute('UPDATE works SET settings_json=?,input_text=? WHERE id=?',
            (encode(settings),'保留四条依据，但不要第一条第二条；不编造我的习惯；结尾不升华',work))
        # Rebuild the enqueued basis before running this synthetic fixture.
        from easel.production.service import row
        task=conn.execute('SELECT * FROM tasks WHERE work_id=?',(work,)).fetchone()
        payload=json.loads(task['payload_json']);payload['creation_basis']=service._basis(conn,row(conn,'works',work))
        conn.execute('UPDATE tasks SET payload_json=? WHERE id=?',(encode(payload),task['id']))
    transport.answer.update(script='我还不知道该选哪一条。',settings={k:v for k,v in {**settings,'duration_seconds':20}.items() if k!='schema_version'},
        scenes=[{'id':'s1','purpose':'留下问题','visual':'拟议动作','narration':'我还不知道该选哪一条。','duration_seconds':20}])
    assert asyncio.run(worker.run_once())
    snap=service.snapshot(work)
    assert snap['state']=='awaiting_confirmation',snap['tasks'][0].get('error_json')
    audits=[r for r in transport.requests if r[2]['title']=='DraftReview']
    assert len(audits)==1
    assert '不要第一条第二条' in audits[0][0][1]['content'][0]['text']
    assert len(snap['plans'])==1


def test_fixed_voice_review_failure_does_not_freeze_or_change_delivery(tmp_path):
    service,work,transport,worker=setup(tmp_path)
    from easel.production.service import encode,row
    voice={'provider':'fixture','model':'speech','engine':'fixture','voice_id':'fixed'}
    settings={'schema_version':1,'audio_mode':'voice','voice':voice,'aspect_ratio':'16:9','duration_seconds':20}
    with service.store.transaction() as conn:
        conn.execute('UPDATE works SET settings_json=? WHERE id=?',(encode(settings),work))
        task=conn.execute('SELECT * FROM tasks').fetchone();payload=json.loads(task['payload_json'])
        payload['creation_basis']=service._basis(conn,row(conn,'works',work))
        conn.execute('UPDATE tasks SET payload_json=? WHERE id=?',(encode(payload),task['id']))
    transport.answer.update(script='第一条。',settings={k:v for k,v in settings.items() if k!='schema_version'},scenes=[{'id':'s1','purpose':'讲述','visual':'拟议动作','narration':'第一条。','duration_seconds':20}])
    complete=transport.complete
    async def fail_review(messages,tools,schema):
        if schema['title']=='DraftReview':
            transport.calls+=1
            return {'content':encode({'verdict':'fail','findings':['原要求禁止编号，script仍为第一条']})}
        if schema['title']=='CreativePlanChanges':
            transport.calls+=1
            return {'content':'{}'}
        return await complete(messages,tools,schema)
    transport.complete=fail_review
    assert asyncio.run(worker.run_once())
    snap=service.snapshot(work)
    assert snap['state']=='needs_decision' and snap['plans']==[]
    assert json.loads(snap['tasks'][0]['error_json'])['code']=='draft_review_failed'
    assert service.store.get_work(work)['settings_json']==encode(settings)


@pytest.mark.parametrize('script',['【S1】保留这个问题。','这是另一份口播。'])
def test_generated_voice_script_must_match_spoken_scene_text(script):
    from pydantic import ValidationError
    from easel.production.planning import VoiceReadyCreativePlan
    with pytest.raises(ValidationError,match='script须与'):
        VoiceReadyCreativePlan.model_validate({'title':'问题','summary':'待确认','script':script,
            'settings':{'duration_seconds':20,'audio_mode':'voice','voice':{'provider':'fixture','model':'voice','engine':'fixture','voice_id':'fixed'}},
            'scenes':[{'id':'s1','purpose':'提问','visual':'动作','narration':'保留这个问题。','duration_seconds':20}]})


@pytest.mark.parametrize('audio_mode',['voice','mixed'])
def test_narration_delta_and_known_receipt_preserve_protected_fields(tmp_path,audio_mode):
    from easel.production.planning import NarrationPlanChanges,merge_narration_changes,received_plan,VoiceReadyCreativePlan
    from pydantic import ValidationError
    service,work,transport,worker=setup(tmp_path)
    base=transport.answer
    base['settings']['audio_mode']=audio_mode
    base['scenes'][0]['visual']='原画面；旧字幕“技术服务人。”；原分镜时间仅估计。'
    base=VoiceReadyCreativePlan.model_validate(base).model_dump(mode='json')
    change={'scenes':[{'id':'s1','narration':'技术也需要判断。'}]}
    delta=NarrationPlanChanges.model_validate(change)
    answer=merge_narration_changes(delta,base)
    assert answer.script=='技术也需要判断。'
    assert answer.scenes[0].visual==base['scenes'][0]['visual']
    assert answer.settings.audio_mode==audio_mode
    assert answer.scenes[0].purpose==base['scenes'][0]['purpose']
    operation={'request_json':json.dumps({'schema':NarrationPlanChanges.model_json_schema(),
        'messages':[{}, {'content':[{'type':'text','text':json.dumps({'plan':base})}]}]}),
        'receipt_json':json.dumps({'result':{'message':{'content':json.dumps(change)}}})}
    assert received_plan(operation)==answer
    for extra in ({'settings':base['settings']},{'explainer_boards':[]},
                  {'scenes':[{'id':'s1','narration':'改变。','visual':'不同画面'}]}):
        with pytest.raises(ValidationError):NarrationPlanChanges.model_validate(extra)
    for scenes in ([{'id':'unknown','narration':'改变。'}],
                   [{'id':'s1','narration':'改变。'},{'id':'s1','narration':'重复。'}]):
        with pytest.raises(ValueError,match='原场景身份'):
            merge_narration_changes(NarrationPlanChanges.model_validate({'scenes':scenes}),base)
    with pytest.raises(ValueError,match='script须'):
        merge_narration_changes(NarrationPlanChanges.model_validate({**change,'script':'不是这句话。'}),base)


@pytest.mark.parametrize('unresolved',[False,True])
def test_replan_review_and_correction_use_current_draft_metadata(tmp_path,unresolved):
    """A withdrawn sentence may remain in history, never as a candidate requirement."""
    from easel.production.service import encode,row
    service,work,transport,worker=setup(tmp_path)
    voice={'provider':'fixture','model':'speech','engine':'fixture','voice_id':'fixed'}
    settings={'schema_version':1,'audio_mode':'voice','voice':voice,'aspect_ratio':'16:9','duration_seconds':20}
    with service.store.transaction() as conn:
        conn.execute('UPDATE works SET settings_json=? WHERE id=?',(encode(settings),work))
        task=conn.execute('SELECT * FROM tasks').fetchone();payload=json.loads(task['payload_json'])
        payload['creation_basis']=service._basis(conn,row(conn,'works',work))
        conn.execute('UPDATE tasks SET payload_json=? WHERE id=?',(encode(payload),task['id']))
    old='录完后，他又拿不准。';new='可再往下想，做到哪里算完？'
    transport.answer.update(script=old,settings={k:v for k,v in settings.items() if k!='schema_version'},
        facts=['第二段为：'+old],constraints=['第二段必须为：'+old,'不得虚构我的经历'],
        scenes=[{'id':'s1','purpose':'提问','visual':'设备近景','duration_seconds':20,'narration':old}])
    asyncio.run(worker.run_once());baseline=service.snapshot(work)['plans'][0]['plan']
    with service.store.connection() as conn:
        target=service.replanning_target(conn,row(conn,'works',work))
    snap=service.snapshot(work)
    service.command('plan',{'intent':'replan','request':'撤回第二段，恢复为“'+new+'”，其余保留','replanning_target':target},
        work_id=work,expected_revision=snap['revision'],command_id='withdraw')
    transport.answer.update(script=new,facts=['第二段为：'+new],constraints=['第二段必须为：'+new,'不得虚构我的经历'],
        scenes=[{**transport.answer['scenes'][0],'narration':new}])
    complete=transport.complete;seen=[]
    async def review(messages,tools,schema):
        if schema['title'] in {'DraftReview','CreativePlanChanges'}:
            data=json.loads(messages[1]['content'][0]['text']);seen.append(schema['title'])
            assert data['facts']==data['plan']['facts']==['第二段为：'+new]
            assert data['prohibitions']==data['plan']['constraints']
            assert '不得虚构我的经历' in data['prohibitions']
            assert old in data['brief'] and '历史基线' in data['brief']
            assert baseline['facts']==['第二段为：'+old]
            if schema['title']=='CreativePlanChanges':
                return {'content':encode({'summary':'纠正后的摘要'})}
            fail=unresolved or seen.count('DraftReview')==1
            return {'content':encode({'verdict':'fail' if fail else 'pass',
                'findings':['当前稿有未解决的真实缺陷'] if fail else []})}
        return await complete(messages,tools,schema)
    transport.complete=review
    asyncio.run(worker.run_once());after=service.snapshot(work)
    assert after['state']==('needs_decision' if unresolved else 'awaiting_confirmation')
    assert len(after['plans'])==(1 if unresolved else 2)
    assert seen.count('CreativePlanChanges')==(2 if unresolved else 1)
    assert all(t['kind']=='plan' for t in after['tasks'])


@pytest.mark.parametrize('engine',['minimax-speech-v1','http-speech-v1'])
def test_draft_voice_execution_view_matches_native_wire_without_editing_plan(tmp_path, engine):
    from copy import deepcopy
    from easel.production.context import TaskContext
    from easel.production.planning import current_draft_context, VoiceReadyCreativePlan
    from easel.production.providers.minimax_speech import MiniMaxSpeechAdapter
    from types import SimpleNamespace
    _,_,transport,_=setup(tmp_path)
    transport.answer['settings'].update(audio_mode='mixed',voice={
        'provider':'fixture','model':'speech','engine':engine,'voice_id':'fixed',
        'parameters':{'speed':1.2,'emotion':'calm','subtitle_enable':True}})
    draft=VoiceReadyCreativePlan.model_validate(transport.answer)
    before=deepcopy(draft.model_dump(mode='json'))
    context=TaskContext('work','run','task',capabilities={'native_explainer_boards':True})
    view=current_draft_context(context,draft)
    assert draft.model_dump(mode='json')==before and view.plan==before
    assert context.capabilities=={'native_explainer_boards':True}
    if engine=='minimax-speech-v1':
        adapter=object.__new__(MiniMaxSpeechAdapter)
        adapter.config=SimpleNamespace(base_url='https://example.test/v1',response_format='wav')
        _,wire=adapter._wire_request({'text':'口播'},draft.settings.voice)
        contract=view.capabilities['voice_execution_contract']
        assert contract['effective_wire_voice_setting']==wire['voice_setting']
        assert contract['fixed_wire_parameters']=={'vol':1,'pitch':0}
        assert contract['supported_plan_parameters']==['emotion','speed','subtitle_enable']
        assert wire['voice_setting']['speed']==1.2 and wire['voice_setting']['emotion']=='calm'
        assert wire['subtitle_enable'] is True
        assert 'volume' not in view.plan['settings']['voice']['parameters']
        assert 'pitch' not in view.plan['settings']['voice']['parameters']
    else:
        assert 'voice_execution_contract' not in view.capabilities


@pytest.mark.parametrize('model,extra_emotions',[('speech-2.8-turbo',set()),('speech-2.6-turbo',{'fluent','whisper'})])
def test_native_voice_author_and_critic_get_adapter_contract_and_frozen_plan_parameters(tmp_path,model,extra_emotions):
    from easel.production.service import encode,row
    service,work,transport,worker=setup(tmp_path)
    voice={'provider':'fixture','model':model,'engine':'minimax-speech-v1','voice_id':'fixed','parameters':{'speed':1}}
    settings={'schema_version':1,'audio_mode':'mixed','voice':voice,'aspect_ratio':'16:9','duration_seconds':20}
    with service.store.transaction() as conn:
        conn.execute('UPDATE works SET settings_json=? WHERE id=?',(encode(settings),work))
        task=conn.execute('SELECT * FROM tasks').fetchone();payload=json.loads(task['payload_json'])
        payload['creation_basis']=service._basis(conn,row(conn,'works',work))
        conn.execute('UPDATE tasks SET payload_json=? WHERE id=?',(encode(payload),task['id']))
    transport.answer['settings']={k:v for k,v in settings.items() if k!='schema_version'}
    transport.answer['settings']['voice']={**voice,'parameters':{'speed':1,'volume':1,'pitch':0}}
    transport.answer['scenes'][0]['duration_seconds']=20
    complete=transport.complete
    async def verify_review(messages,tools,schema):
        data=json.loads(messages[1]['content'][0]['text'])
        contract=data['production_capabilities']['voice_execution_contract']
        assert set(contract['supported_emotions']) == {'happy','sad','angry','fearful','disgusted','surprised','calm'} | extra_emotions
        assert contract['effective_wire_voice_setting']=={'voice_id':'fixed','speed':1,'vol':1,'pitch':0}
        assert 'volume' not in contract['supported_plan_parameters']
        if schema['title']=='DraftReview':
            assert data['plan']['settings']['voice']==voice
            group_schema=data['production_capabilities']['narration_group_schema']
            assert group_schema['additionalProperties'] is False
            assert set(group_schema['properties'])=={'id','scene_ids','emotion'}
            assert group_schema['properties']['emotion']['default'] is None
            measurements=data['production_capabilities']['duration_execution_contract']['measurements']
            assert measurements['script_characters']==len('技术服务人。')
            assert measurements['scene_duration_seconds']==20
            assert measurements['pause_seconds']==0
        return await complete(messages,tools,schema)
    transport.complete=verify_review
    assert asyncio.run(worker.run_once())
    snap=service.snapshot(work)
    assert snap['state']=='awaiting_confirmation',snap['tasks'][0]['error_json']
    assert snap['plans'][0]['plan']['settings']['voice']==voice
    assert service.store.get_work(work)['settings_json']==encode(settings)
    assert transport.calls==2


def test_frozen_episode_source_reaches_downstream_without_task_request(tmp_path):
    from types import SimpleNamespace
    from easel.production.service import encode
    from easel.production.context import TaskContext
    service,work,transport,worker=setup(tmp_path)
    source=encode({'user_sources':[{'source_turn':'real-source','text':'撤销必要图解，只用纯实拍，保留整条旁白。'}],
                   'agent_request':'重做画面'})
    with service.store.transaction() as c:
        row=c.execute('SELECT * FROM tasks').fetchone();payload=json.loads(row['payload_json'])
        payload['request']=source
        payload['creation_basis']['conversation_brief']={'body':{'entries':[{'text':'旧方案要求必要图解'}]}}
        c.execute('UPDATE tasks SET payload_json=? WHERE id=?',(encode(payload),row['id']))
    assert asyncio.run(worker.run_once())
    plan=service.snapshot(work)['plans'][0]['plan']
    assert plan['conversation_basis']['creative_request']==source
    assert plan['conversation_basis']['conversation_brief']['body']['entries'][0]['text']=='旧方案要求必要图解'
    from easel.production.operations import OperationService
    planning=PlanningTasks(service,OperationService(service.store),None,{'provider':'direct-api','model':'fixture','mode':'structured'},'fixture-v1')
    ctx=SimpleNamespace(work_id=work,run_id='execution-run',task_id='quality-task',plan_revision=1,payload={})
    view=planning.context(ctx)
    assert source in view.brief
    assert view.plan['conversation_basis']['creative_request']==source
    data=view.creative_data()
    assert source in data['brief']
    assert 'creative_request' not in data['plan']['conversation_basis']
    assert view.plan['conversation_basis']['creative_request']==source  # Projection never mutates the snapshot.
    standalone=TaskContext('work','run','task',plan={'conversation_basis':{'creative_request':source}})
    assert standalone.creative_data()['plan']['conversation_basis']['creative_request']==source


@pytest.mark.parametrize('mode',['fixed','voice_driven'])
def test_current_candidate_review_receives_runtime_duration_semantics(tmp_path, mode):
    from copy import deepcopy
    from easel.production.context import TaskContext
    from easel.production.planning import current_draft_context,VoiceReadyCreativePlan
    from easel.production.narration import duration_execution_contract
    _,_,transport,_=setup(tmp_path)
    transport.answer['narration_policy']={'duration_mode':mode,'continuous':False}
    draft=VoiceReadyCreativePlan.model_validate(transport.answer)
    before=deepcopy(draft.model_dump(mode='json'));context=TaskContext('w','r','t')
    view=current_draft_context(context,draft)
    assert view.capabilities['duration_execution_contract']==duration_execution_contract(before)
    assert draft.model_dump(mode='json')==before and context.capabilities=={}
