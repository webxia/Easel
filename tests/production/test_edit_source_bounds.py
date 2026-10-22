"""Source time bounds are feedback, never silent looping or trimming."""
import pytest
from easel.production.creation import CreativeEdit, check_edit_source_bounds


def edit(duration=6.4,start=11.3,transition='cut',overlap=0):
    return CreativeEdit(scenes=[{'scene_id':'tail','asset_id':'video','duration':duration,
        'source_start':start,'transition':transition,'transition_seconds':overlap}])


def test_overrun_reports_scene_and_actual_bound_without_mutating_edit():
    value=edit();before=value.model_dump()
    with pytest.raises(ValueError,match='tail.*17.36'):
        check_edit_source_bounds(value,{'video':17.36},target_seconds=6.4)
    assert value.model_dump()==before
    check_edit_source_bounds(edit(start=10.9),{'video':17.36},target_seconds=6.4)


def test_transition_compilation_is_included_and_still_image_not_bounded():
    value=CreativeEdit(scenes=[{'scene_id':'first','asset_id':'still','duration':2},
        {'scene_id':'tail','asset_id':'video','duration':3,'source_start':0,
         'transition':'dissolve','transition_seconds':.5}])
    with pytest.raises(ValueError,match='tail'):
        check_edit_source_bounds(value,{'video':3.1},target_seconds=5)
    check_edit_source_bounds(value,{'video':3.5},target_seconds=5)


def test_existing_bounded_runner_corrects_source_range():
    import asyncio,json
    from easel.production.model_tasks import ModelTaskRunner
    from easel.production.context import TaskContext
    class Transport:
        capabilities=frozenset({'text','structured'})
        calls=0
        async def complete(self,messages,tools,schema):
            self.calls+=1
            if self.calls==2:assert '17.36' in messages[-1]['content']
            return {'content':edit(start=11.3 if self.calls==1 else 10.9).model_dump_json()}
    async def authorize(ctx):pass
    transport=Transport()
    answer=asyncio.run(ModelTaskRunner(transport,authorize,max_format_repairs=2).run(
        TaskContext('w','r','t',allowed_handles=frozenset({'video'})),'edit',CreativeEdit,
        validate_result=lambda x:check_edit_source_bounds(x,{'video':17.36},target_seconds=6.4)))
    assert transport.calls==2 and answer.scenes[0].source_start==10.9


def test_new_edit_contract_does_not_bypass_legacy_unknown():
    import asyncio
    from types import SimpleNamespace
    from easel.production.creation import CreationTasks
    # Read-only preflight can be tested with a tiny isolated operations view.
    import sqlite3
    from contextlib import nullcontext
    conn=sqlite3.connect(':memory:');conn.execute('CREATE TABLE operations(task_id,state)')
    conn.execute("INSERT INTO operations VALUES ('old-task','unknown')")
    service=SimpleNamespace(store=SimpleNamespace(connection=lambda:nullcontext(conn)))
    def forbidden(ctx):raise AssertionError('must not reach model or voice')
    result=asyncio.run(CreationTasks(service,SimpleNamespace(context=forbidden),editor=object()).edit(SimpleNamespace(task_id='old-task')))
    assert result.error.code=='result_unknown'


def test_confirmed_recovery_repairs_received_edit_without_author_call():
    import asyncio
    from easel.production.model_tasks import ModelTaskRunner, ModelTaskError
    from easel.production.context import TaskContext
    value=CreativeEdit(scenes=[{'scene_id':'head','asset_id':'still','duration':2},
        {'scene_id':'tail','asset_id':'video','duration':5,'source_start':7.9,
         'transition':'dissolve','transition_seconds':.4}])
    class Transport:
        capabilities=frozenset({'text','structured'})
        calls=0
        async def complete(self,messages,tools,schema):
            self.calls+=1
            assert '5.400' in messages[-1]['content'] and '7.840' in messages[-1]['content']
            fixed=value.model_copy(update={'scenes':[value.scenes[0],value.scenes[1].model_copy(update={'source_start':7.8})]})
            return {'content':fixed.model_dump_json()}
    async def authorize(ctx):pass
    transport=Transport()
    answer=asyncio.run(ModelTaskRunner(transport,authorize,max_format_repairs=2).run(
        TaskContext('w','r','t',allowed_handles=frozenset({'video','still'})),'edit',CreativeEdit,
        recovery=([{'role':'system','content':'original contract'}],{'content':value.model_dump_json()}),
        validate_result=lambda x:check_edit_source_bounds(x,{'video':13.24},target_seconds=7)))
    assert transport.calls==1 and answer.scenes[-1].source_start==7.8


def test_recovery_does_not_expand_bounded_repair_limit():
    import asyncio
    from easel.production.model_tasks import ModelTaskRunner, ModelTaskError
    from easel.production.context import TaskContext
    class Transport:
        capabilities=frozenset({'text','structured'})
        calls=0
        async def complete(self,*args):
            self.calls+=1
            return {'content':edit().model_dump_json()}
    async def authorize(ctx):pass
    transport=Transport()
    with pytest.raises(ModelTaskError):
        asyncio.run(ModelTaskRunner(transport,authorize,max_format_repairs=2).run(
            TaskContext('w','r','t',allowed_handles=frozenset({'video'})),'edit',CreativeEdit,
            recovery=([{'role':'system','content':'contract'}],{'content':edit().model_dump_json()}),
            validate_result=lambda x:check_edit_source_bounds(x,{'video':17.36},target_seconds=6.4)))
    assert transport.calls==2


@pytest.mark.parametrize('unknown',[False,True])
def test_explicit_resume_pins_known_source_and_preserves_unknown(tmp_path,unknown):
    import json
    from tests.production.test_operations import owned_request
    from easel.production.store import Store
    from easel.production.operations import OperationService
    from easel.production.providers.base import ProviderResult
    from easel.production.service import WorkService,row
    from easel.production.errors import ProductionError
    store=Store(tmp_path/'db.sqlite');store.initialize()
    ops=OperationService(store,clock=lambda:1000)
    spec=owned_request(store,kind='MODEL')
    spec['request']={'schema':{'title':'CreativeEdit'},'messages':[]}
    ops.reserve(**spec);ops.mark_sending(spec['operation_id'],1)
    if unknown:ops.mark_unknown(spec['operation_id'])
    else:ops.receive(spec['operation_id'],ProviderResult('succeeded',result={'message':{'content':edit().model_dump_json()}}))
    service=WorkService(store,outputs=tmp_path,profiles=tmp_path/'profiles')
    with store.transaction() as conn:
        conn.execute("UPDATE tasks SET kind='edit',state='needs_decision',error_json=?",(json.dumps({'code':'invalid_model_output'}),))
        conn.execute("UPDATE runs SET state='needs_decision'")
    if unknown:
        with pytest.raises(ProductionError):
            with store.transaction() as conn:service._resume(conn,row(conn,'works',spec['work_id']),{'decision_id':spec['task_id']})
        assert ops.get(spec['operation_id'])['state']=='unknown'
    else:
        with store.transaction() as conn:service._resume(conn,row(conn,'works',spec['work_id']),{'decision_id':spec['task_id']})
        with store.connection() as conn:
            task=row(conn,'tasks',spec['task_id'])
            assert json.loads(task['payload_json'])['edit_recovery_source']==spec['operation_id']
            assert task['state']=='pending'
        assert ops.get(spec['operation_id'])['state']=='succeeded'


def test_timeline_identity_contract_is_actionable_before_project_submission():
    from easel.production.editors.base import check_timeline_identities
    value=CreativeEdit(scenes=[{'scene_id':'s1','asset_id':'video','duration':2},
                               {'scene_id':'s1','asset_id':'video','duration':2}])
    with pytest.raises(ValueError,match='scene_id.*-cut1'):
        check_timeline_identities(value.scenes,[],[])
    corrected=[value.scenes[0],value.scenes[1].model_copy(update={'scene_id':'s1-cut2'})]
    check_timeline_identities(corrected,[],[])
