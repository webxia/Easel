import json
import asyncio
from types import SimpleNamespace
import pytest
from easel.production.creation import CreationTasks, CreativeEdit
from easel.production.material_intent import MaterialIntent
from easel.production.model_tasks import ModelTaskError


def test_initial_gap_reuses_bounded_stock_and_keeps_existing_assets():
    calls=[]
    intent=MaterialIntent(visuals=[{'scene_id':'s1','query':'bookmark webpage','media_types':['video'],'options':2}])
    class Runner:
        async def run(self,context,instruction,schema,**kw):
            assert schema is MaterialIntent
            kw['validate_result'](intent)
            return intent
    class Supply:
        def revision_visuals(self,ctx,searches):
            calls.append(searches)
            return ['new-video']
    creation=CreationTasks(None,SimpleNamespace(runner=lambda *a,**kw:Runner()),editor=object(),supply=Supply())
    answer=CreativeEdit(scenes=[{'scene_id':'s1','asset_id':'old','duration':5}],unresolved_scene_ids=['s1'])
    context=SimpleNamespace(plan={'scenes':[{'id':'s1'}]})
    result=asyncio.run(creation.supplement_visuals(object(),context,answer,['old','voice']))
    assert result==['old','voice','new-video'] and len(calls)==1


@pytest.mark.parametrize('intent',[
    MaterialIntent(visuals=[{'scene_id':'other','query':'other','media_types':['video']}]),
    MaterialIntent(visuals=[],music_query='music'),
    MaterialIntent(visuals=[]),
])
def test_supplement_cannot_expand_scope(intent):
    class Runner:
        async def run(self,context,instruction,schema,**kw):
            kw['validate_result'](intent)
            return intent
    creation=CreationTasks(None,SimpleNamespace(runner=lambda *a,**kw:Runner()),editor=object(),supply=object())
    answer=CreativeEdit(scenes=[{'scene_id':'s1','asset_id':'old','duration':5}],unresolved_scene_ids=['s1'])
    with pytest.raises(ValueError):
        asyncio.run(creation.supplement_visuals(object(),SimpleNamespace(plan={'scenes':[{'id':'s1'}]}),answer,['old']))


def test_no_supply_or_unknown_scene_stays_blocked():
    creation=CreationTasks(None,None,editor=object())
    answer=CreativeEdit(scenes=[{'scene_id':'s1','asset_id':'old','duration':5}],unresolved_scene_ids=['s1'])
    with pytest.raises(ModelTaskError,match='s1'):
        asyncio.run(creation.supplement_visuals(object(),SimpleNamespace(plan={'scenes':[{'id':'s1'}]}),answer,['old']))


def test_edit_stops_after_one_stock_pass_without_render_or_voice(monkeypatch):
    import sqlite3
    from contextlib import nullcontext
    from easel.production.context import TaskContext
    db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row;db.execute('CREATE TABLE operations(task_id,state)')
    db.execute('CREATE TABLE tasks(id,payload_json)')
    db.execute("INSERT INTO tasks VALUES('t',?)",(json.dumps({'asset_ids':['old']}),))
    service=SimpleNamespace(store=SimpleNamespace(connection=lambda:nullcontext(db)))
    namespaces=[];supplies=[]
    answer=CreativeEdit(scenes=[{'scene_id':'s1','asset_id':'old','duration':1}],unresolved_scene_ids=['s1'])
    class Runner:
        async def run(self,*args,**kwargs):return answer
    def runner(ctx,**kw):
        namespaces.append(kw['namespace']);return Runner()
    context=TaskContext('w','r','t',plan={'scenes':[{'id':'s1'}],
        'settings':{'duration_seconds':1,'aspect_ratio':'16:9','audio_mode':'silent'}})
    creation=CreationTasks(service,SimpleNamespace(context=lambda ctx:context,runner=runner,transport=None),editor=object(),supply=object())
    creation.assets=lambda ctx,ids:([],SimpleNamespace(assets={'old':None}))
    async def supplement(ctx,context,answer,ids):
        supplies.append(ids);return [*ids,'new']
    creation.supplement_visuals=supplement
    monkeypatch.setattr('easel.production.narration.measured_execution_plan',lambda p,r:(p,None))
    result=asyncio.run(creation.edit(SimpleNamespace(task_id='t',payload={'asset_ids':['old']},transaction=lambda:nullcontext(db))))
    assert result.state=='needs_decision' and result.error.code=='visual_material_gap'
    assert 's1' in result.error.user_message and len(supplies)==1
    assert namespaces==['edit-source-bounds-v1','edit-stock-selection-v1']
    assert json.loads(db.execute("SELECT payload_json FROM tasks WHERE id='t'").fetchone()[0])['asset_ids']==['old','new']
