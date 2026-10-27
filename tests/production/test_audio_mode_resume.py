"""An authorized audio setting correction resumes the same stopped first edit."""
import json
import pytest
from easel.production.service import row,encode,now
from easel.production.errors import ProductionError
from tests.production.test_conversation import env
from tests.production.test_preoutput_replan import stopped


def stopped_edit(env):
    s,w,r=stopped(env)
    with s.store.transaction() as conn:
        t=conn.execute('SELECT id FROM tasks WHERE run_id=?',(r,)).fetchone()[0]
        conn.execute("UPDATE tasks SET kind='edit',error_json=? WHERE id=?",(encode({'code':'invalid_model_output'}),t))
        g=conn.execute('SELECT id FROM authorization_grants WHERE work_id=?',(w,)).fetchone()[0]
        conn.execute("INSERT INTO operations(id,work_id,run_id,task_id,grant_id,kind,state,provider,model,mode,config_version,request_key,input_hash,request_json,receipt_json,owner_epoch,created_at,updated_at) VALUES(?,?,?,?,?,'MODEL','succeeded','fixture','fixture','structured','v1','key','fingerprint',?,?,0,?,?)",
            ('op',w,r,t,g,encode({'schema':{'title':'CreativeEdit'},'messages':[]}),
             encode({'result':{'message':{'content':encode({'scenes':[],'audio':[]})}}}),now(),now()))
    return s,w,r,t


def test_local_revision_only_changes_mode_and_reuses_original_run(env):
    s,w,r,t=stopped_edit(env);before=s.snapshot(w);old=before['plans'][0]
    with s.store.connection() as conn:
        original_op=dict(conn.execute('SELECT * FROM operations WHERE id=?',('op',)).fetchone())
    result=s.command('resume',{'decision_id':t,'audio_mode':'voice'},command_id='audio-resume',
        work_id=w,expected_revision=before['revision'])
    after=s.snapshot(w)
    assert result['run_id']==r and len(after['runs'])==1
    assert after['plans'][-1]==old
    assert after['plans'][0]['confirmed_at']
    expected={**old['plan'],'settings':{**old['plan']['settings'],'audio_mode':'voice'}}
    assert after['plans'][0]['plan']==expected
    with s.store.connection() as conn:
        task=row(conn,'tasks',t);payload=json.loads(task['payload_json'])
        assert task['state']=='pending' and task['plan_revision']==2
        assert payload['reuse_existing_media_only'] is True
        assert payload['edit_recovery_source']=='op'
        assert dict(conn.execute('SELECT * FROM operations WHERE id=?',('op',)).fetchone())==original_op
        assert row(conn,'runs',r)['plan_revision']==2
    assert s.command('resume',{'decision_id':t,'audio_mode':'voice'},command_id='audio-resume',
        work_id=w,expected_revision=before['revision'])==result


@pytest.mark.parametrize('unsafe',['unknown','owner','output','another_task','changed_mode'])
def test_local_revision_refuses_unsafe_or_expanded_recovery(env,unsafe):
    from tests.production.test_store import insert_artifact
    s,w,r,t=stopped_edit(env)
    with s.store.transaction() as conn:
        if unsafe=='unknown':conn.execute("UPDATE operations SET state='unknown'")
        if unsafe=='owner':conn.execute("UPDATE runs SET owner_id='worker' WHERE id=?",(r,))
        if unsafe=='output':insert_artifact(conn,w,kind='output')
        if unsafe=='another_task':conn.execute("UPDATE tasks SET kind='supply' WHERE id=?",(t,))
    before=s.snapshot(w)
    with pytest.raises(ProductionError):
        s.command('resume',{'decision_id':t,'audio_mode':'music' if unsafe=='changed_mode' else 'voice'},
            command_id='unsafe',work_id=w,expected_revision=before['revision'])
    assert s.snapshot(w)==before


def test_local_revision_rolls_back_if_new_grant_fails(env,monkeypatch):
    s,w,r,t=stopped_edit(env);before=s.snapshot(w)
    def fail(*a,**kw):raise RuntimeError('injected grant failure')
    monkeypatch.setattr(s,'_insert_grant',fail)
    with pytest.raises(RuntimeError):s.command('resume',{'decision_id':t,'audio_mode':'voice'},
        command_id='rollback',work_id=w,expected_revision=before['revision'])
    assert s.snapshot(w)==before


def test_worker_rebases_known_response_without_repeating_supply_or_voice(tmp_path):
    import asyncio,wave
    from PIL import Image
    from easel.production.store import Store
    from easel.production.service import WorkService
    from easel.production.worker import Worker,TaskResult
    from easel.production.planning import PlanningTasks
    from easel.production.creation import CreationTasks
    from easel.production.operations import OperationService
    from easel.production.artifacts import register_file
    store=Store(tmp_path/'db');store.initialize()
    s=WorkService(store,outputs=tmp_path/'outputs',profiles=tmp_path/'profiles')
    image=tmp_path/'i.png';Image.new('RGB',(64,64),'blue').save(image)
    sound=tmp_path/'a.wav'
    with wave.open(str(sound),'wb') as f:
        f.setparams((1,2,8000,0,'NONE','not compressed'));f.writeframes(b'\0\0'*16000)
    assets={};calls=[]
    class Model:
        capabilities=frozenset({'text','structured','image'})
        async def complete(self,messages,tools,schema):
            data=json.loads(messages[1]['content'][0]['text']);calls.append(data)
            voice_only=data['plan']['settings']['audio_mode']=='voice'
            return {'content':encode({'scenes':[{'scene_id':'s','asset_id':assets['image'],'duration':2 if voice_only else 1.8}],
                'audio':[{'clip_id':'v','asset_id':assets['sound'],'role':'voice','at':0,'duration':2}]})}
    identity={'provider':'direct-api','model':'fixture','mode':'structured'}
    planning=PlanningTasks(s,OperationService(store),Model(),identity,'fixture')
    creation=CreationTasks(s,planning)
    async def supply(ctx):
        assert not assets,'supply must not repeat'
        assets['image']=register_file(s,ctx,image,kind='image',media_type='image/png',metadata={})['id']
        assets['sound']=register_file(s,ctx,sound,kind='audio',media_type='audio/wav',metadata={})['id']
        return TaskResult(next_kind='edit',next_payload={'asset_ids':list(assets.values())})
    w=s.command('create',{'title':'fixture'},command_id='create')['work_id']
    p=s.command('plan',{'generate':False,'plan':{'title':'fixture','summary':'fixture','script':'fixture',
        'constraints':['仅旁白和薄环境音'],'scenes':[{'id':'s','purpose':'fixture','visual':'blue'}],
        'settings':{'duration_seconds':2,'audio_mode':'mixed','subtitles':{'enabled':False}}}},
        command_id='plan',work_id=w,expected_revision=1)
    s.command('confirm',{**p,'services':[identity]},command_id='confirm',work_id=w,expected_revision=2)
    worker=Worker(store,{'supply':supply,'edit':creation.edit})
    asyncio.run(worker.run_once())
    before=s.snapshot(w);edit=next(t for t in before['tasks'] if t['kind']=='edit')
    assert edit['state']=='needs_decision' and 'mixed' in edit['error_json'] and '2.000000' in edit['error_json']
    original_calls=len(calls)
    s.command('resume',{'decision_id':edit['id'],'audio_mode':'voice'},command_id='resume',work_id=w,expected_revision=before['revision'])
    asyncio.run(worker.run_once())
    after=s.snapshot(w);edit=next(t for t in after['tasks'] if t['kind']=='edit')
    assert edit['state']=='succeeded',edit['error_json']
    assert len(calls)==original_calls+1
    assert calls[-1]['plan']['settings']['audio_mode']=='voice'
    assert after['plans'][-1]==before['plans'][0]
    assert len([t for t in after['tasks'] if t['kind']=='supply'])==1
