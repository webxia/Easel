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
