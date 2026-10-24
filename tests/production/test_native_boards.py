import asyncio
from dataclasses import replace
from copy import deepcopy
import json
from pathlib import Path
from PIL import Image,ImageChops
from pydantic import ValidationError
import pytest
from easel.production.contracts import ExplainerBoard
from easel.production.boards import render_board,check_board_usage
from easel.production.editors import Scene
from easel.production.supply_tasks import SupplyTasks
from easel.production.material_binding import validate_material_records
from .test_supply_tasks import env
from .test_creative_captions import font


def data():
    return {'scene_id':'s1','title':'方法随条件变化','kind':'hypothetical',
        'cards':[{'id':str(i),'text':'项目'+str(i)} for i in range(1,7)],
        'columns':[{'id':'a','title':'条件甲'},{'id':'b','title':'条件乙'}],
        'states':[{'title':'初始分组','groups':{'a':['1','2','3'],'b':['4','5','6']}},
                  {'title':'条件变化后重新判断','groups':{'a':['1','3'],'b':['2','4','5','6']},'highlight_ids':['2']}]}


def test_state_can_change_visible_criteria_without_changing_card_identity(font,tmp_path):
    d=data();d['states'][1]['column_titles']={'a':'新条件甲','b':'新条件乙'}
    b=ExplainerBoard.model_validate(d)
    assert [c.text for c in b.cards]==[c['text'] for c in d['cards']]
    render_board(b,1,font_path=font,aspect_ratio='16:9',destination=tmp_path/'changed-criterion.png')
    d['states'][1]['column_titles']={'unknown':'虚构类别'}
    with pytest.raises(ValidationError):ExplainerBoard.model_validate(d)


@pytest.mark.parametrize('aspect,size',[('16:9',(1920,1080)),('9:16',(1080,1920))])
def test_real_rendered_states_show_changed_placement_and_preserve_disclosure(font,tmp_path,aspect,size):
    b=ExplainerBoard.model_validate(data())
    paths=[render_board(b,i,font_path=font,aspect_ratio=aspect,destination=tmp_path/f'{i}.png') for i in range(2)]
    a,c=[Image.open(p) for p in paths]
    assert a.size==c.size==size
    assert ImageChops.difference(a,c).getbbox() is not None
    # Permanent disclosure/count region doesn't disappear when card state changes.
    assert ImageChops.difference(a.crop((0,size[1]-70,size[0],size[1])),c.crop((0,size[1]-70,size[0],size[1]))).getbbox() is None


@pytest.mark.parametrize('change',['unknown','repeated','hidden','oversize'])
def test_board_references_are_checked_before_render(change):
    d=data()
    if change=='unknown':d['states'][0]['groups']['a'].append('foreign')
    if change=='repeated':d['states'][0]['groups']['a'].append('1')
    if change=='hidden':d['cards'].append({'id':'never-visible','text':'未展示'})
    if change=='oversize':d['states'][0]['groups']={'a':['1','2','3','4','5','6'],'b':[]}
    with pytest.raises(ValidationError):ExplainerBoard.model_validate(d)


def test_native_board_supply_has_authorship_rights_replays_and_uses_no_generation(env,font):
    service,ops,ctx,_,_=env
    with service.store.transaction() as writer:
        p=json.loads(writer.execute('SELECT payload_json FROM plan_revisions WHERE work_id=?',(ctx.work_id,)).fetchone()[0])
        p['explainer_boards']=[data()]
        work=ctx.store.get_work(ctx.work_id,connection=writer)
        saved=ctx.store.save_plan(ctx.work_id,p,expected_revision=work['revision'],connection=writer)
        revision=saved['revision']
        from easel.production.store import utc_now
        writer.execute('UPDATE plan_revisions SET confirmed_at=? WHERE work_id=? AND revision=?',(utc_now(),ctx.work_id,revision))
        writer.execute('UPDATE runs SET plan_revision=? WHERE id=?',(revision,ctx.run_id))
        writer.execute('UPDATE tasks SET plan_revision=? WHERE id=?',(revision,ctx.task_id))
        writer.execute('UPDATE authorization_grants SET plan_revision=? WHERE work_id=?',(revision,ctx.work_id))
    ctx=replace(ctx,plan_revision=revision)
    task=SupplyTasks(service,ops);task.board_fonts={'sans-serif':font}
    result=asyncio.run(task.supply(ctx))
    assert result.state=='succeeded',result.error
    assert result.next_kind=='edit' and len(result.result['asset_ids'])==2
    second=asyncio.run(task.supply(ctx));assert second.result==result.result
    with service.store.connection() as reader:
        records=[dict(r) for r in reader.execute('SELECT * FROM artifacts')]
        assert reader.execute('SELECT count(*) FROM operations').fetchone()[0]==0
    validate_material_records(service,ctx,records)
    assert all(json.loads(r['metadata_json'])['source']['kind']=='authored_graphic' for r in records)
    clips=[Scene(scene_id='s1-state'+str(i),asset_id=r['id'],duration=3) for i,r in enumerate(records)]
    check_board_usage(clips,records)
    # Framing is creative; frozen state coverage/order remain protected.
    detail=clips[0].model_copy(update={'scene_id':'conclusion','crop':clips[0].crop.model_copy(update={'width':.5})})
    check_board_usage([*clips,detail],records)
    from types import SimpleNamespace
    check_board_usage([detail,clips[1]],records,overlays=[SimpleNamespace(start=0,end=1)])
    with pytest.raises(ValueError):check_board_usage(clips[::-1],records)
    with pytest.raises(ValueError):check_board_usage(clips[:1],records)


def test_material_projection_can_reuse_board_states_across_narrative_scenes():
    from easel.production.contracts import PlanDocument
    from easel.production.material_intent import MaterialIntent,check_intent
    plan=PlanDocument.model_validate({'title':'t','summary':'s','script':'p',
        'settings':{'duration_seconds':6,'audio_mode':'silent'},
        'scenes':[{'id':id,'purpose':'解释','visual':'图解'} for id in ['s1','s2','s3']],
        'explainer_boards':[data()]})
    intent=MaterialIntent.model_validate({'visuals':[{'scene_id':id,'query':'native schematic','media_types':['image'],
        'board_id':'s1','board_state_indexes':indexes} for id,indexes in [('s1',[0]),('s2',[1]),('s3',[0,1])]]})
    check_intent(intent,plan)
    bad=intent.model_copy(deep=True);bad.visuals[1].board_state_indexes=[99]
    from easel.production.model_tasks import ModelTaskError
    with pytest.raises(ModelTaskError):check_intent(bad,plan)


def test_model_authored_boards_plan_to_real_render_without_external_art_or_paid_generation(tmp_path,font):
    import time
    from easel.production.store import Store
    from easel.production.service import WorkService
    from easel.production.operations import OperationService
    from easel.production.planning import PlanningTasks
    from easel.production.creation import CreationTasks
    from easel.production.worker import Worker
    from easel.production.material_intent import FrozenIntentCompiler
    store=Store(tmp_path/'outputs/db');store.initialize()
    service=WorkService(store,outputs=tmp_path/'outputs',profiles=tmp_path/'profiles')
    settings={'duration_seconds':6,'aspect_ratio':'16:9','audio_mode':'silent','subtitles':{'enabled':False}}
    class Model:
        capabilities=frozenset({'text','structured','image'})
        calls=[]
        async def complete(self,messages,tools,schema):
            self.calls.append(schema['title'])
            if schema['title']=='VoiceReadyCreativePlan':
                answer={'title':'条件与方法','summary':'比较两个状态','script':'概念示意，非真实资料',
                    'settings':settings,'scenes':[{'id':'s1','purpose':'解释','visual':'原生图解对照','duration_seconds':6}],
                    'explainer_boards':[data()]}
            else:
                evidence=json.loads(messages[1]['content'][0]['text'])
                visuals=sorted((a for a in evidence['artifacts'] if a['kind']=='image'),
                    key=lambda a:a['metadata']['material_uses'][0]['board_frame_index'])
                answer={'scenes':[{'scene_id':'s1-state'+str(i),'asset_id':a['asset_id'],'duration':3}
                                  for i,a in enumerate(visuals)],'audio':[],'captions':[]}
            return {'content':json.dumps(answer)}
    model=Model();identity={'provider':'direct-api','model':'fixture','mode':'structured'};ops=OperationService(store)
    planning=PlanningTasks(service,ops,model,identity,'fixture');planning.execution_capabilities['native_explainer_boards']=True
    supply=SupplyTasks(service,ops,planning=planning,intent_compiler=FrozenIntentCompiler(planning));supply.board_fonts={'sans-serif':font}
    creation=CreationTasks(service,planning,manual_review_only=True)
    worker=Worker(store,{'plan':planning.plan,'supply':supply.supply,'edit':creation.edit,
        'render':creation.render,'quality':creation.quality})
    work=service.command('create',{'title':'one idea','input_text':'条件变化后，方法还能用吗？','settings':settings},command_id='create')['work_id']
    service.command('plan',{'services':[identity]},command_id='plan',work_id=work,expected_revision=1)
    asyncio.run(worker.run_once());snap=service.snapshot(work);p=snap['plans'][0]
    assert p['plan']['explainer_boards'][0]['cards'][1]['text']=='项目2'
    service.command('confirm',{'plan_revision':1,'plan_hash':p['plan_hash'],'services':[identity]},
        command_id='confirm',work_id=work,expected_revision=snap['revision'])
    deadline=time.monotonic()+30
    while time.monotonic()<deadline:
        asyncio.run(worker.run_once());snap=service.snapshot(work)
        if snap['state'] in {'reviewable','needs_decision'}:break
        time.sleep(.05)
    assert snap['state']=='reviewable',[(t['kind'],t['state'],t['error_json']) for t in snap['tasks']]
    assert not snap['inputs'] and snap['accepted_output_id'] is None
    output=next(a for a in snap['artifacts'] if a['kind']=='output')
    path,_=service.artifact_path(output['id']);assert path.stat().st_size>1000
    with store.connection() as reader:
        assert reader.execute("SELECT count(*) FROM operations WHERE kind IN ('IMAGE','VIDEO','VOICE')").fetchone()[0]==0
    assert model.calls==['VoiceReadyCreativePlan','CreativeEdit']


@pytest.mark.parametrize('remains_invalid',[False,True])
def test_native_draft_audit_sees_real_board_pixels_before_freeze_and_speech(tmp_path,font,remains_invalid):
    from easel.production.store import Store
    from easel.production.service import WorkService
    from easel.production.operations import OperationService
    from easel.production.planning import PlanningTasks
    from easel.production.worker import Worker
    store=Store(tmp_path/'db');store.initialize();service=WorkService(store,outputs=tmp_path/'outputs',profiles=tmp_path/'profiles')
    voice={'provider':'fixture','model':'speech','engine':'fixture','voice_id':'fixed'}
    settings={'audio_mode':'voice','voice':voice,'aspect_ratio':'16:9'}
    work=service.command('create',{'title':'idea','input_text':'条件变化后，还会吗？','settings':settings},command_id='create')['work_id']
    identity={'provider':'direct-api','model':'fixture','mode':'structured'}
    service.command('plan',{'services':[identity]},work_id=work,expected_revision=1,command_id='plan')
    draft={'title':'变化','summary':'假设演示','script':'检查条件和边界',
        'settings':{**settings,'duration_seconds':20},'scenes':[{'id':'s1','purpose':'解释','visual':'图解状态变化',
        'duration_seconds':20,'narration':'假设条件变了，换个办法再试。','required_input_ids':[]}], 'explainer_boards':[data()]}
    class Model:
        capabilities=frozenset({'text','structured','image'})
        def __init__(self):self.calls=[];self.audits=0;self.authors=0
        async def complete(self,messages,tools,schema):
            self.calls.append(deepcopy(messages))
            if schema['title']=='DraftReview':
                self.audits+=1
                assert sum(b.get('type')=='image_url' for b in messages[1]['content'])==2
                fail=self.audits==1 or remains_invalid
                value={'verdict':'fail' if fail else 'pass','findings':['第二状态列标题无法容纳结果项'] if fail else [],
                    'observations':['实际草稿PNG两状态已观察'],'limitations':['未听声音、未选库存']}
            else:
                self.authors+=1;value=deepcopy(draft)
                if self.authors==2:
                    value['explainer_boards'][0]['states'][1]['column_titles']={'a':'修正标准甲','b':'修正标准乙'}
            return {'content':json.dumps(value)}
    model=Model();planning=PlanningTasks(service,OperationService(store),model,identity,'fixture')
    planning.board_fonts={'sans-serif':font};planning.execution_capabilities['native_explainer_boards']=True
    assert asyncio.run(Worker(store,{'plan':planning.plan}).run_once())
    snap=service.snapshot(work)
    assert len(model.calls)==(6 if remains_invalid else 4)
    manifests=list((service.outputs/'_production/plan-previews').rglob('manifest.json'));assert len(manifests)==2
    for manifest in manifests:
        entries=json.loads(manifest.read_text())['frames']
        assert all(e['caption_sample_bounds'][1]+e['caption_sample_bounds'][3]<1080-65 for e in entries)
        assert all(e['preview_sha256']!=e['sha256'] for e in entries)
    if remains_invalid:
        assert snap['state']=='needs_decision' and not snap['plans']
    else:
        assert snap['state']=='awaiting_confirmation'
        assert snap['plans'][0]['plan']['explainer_boards'][0]['states'][1]['column_titles']['a']=='修正标准甲'
    with store.connection() as c:
        assert c.execute("SELECT count(*) FROM operations WHERE kind!='MODEL'").fetchone()[0]==0


def test_board_contract_declares_identity_and_per_column_bounds_before_model_call():
    schema=ExplainerBoard.model_json_schema();groups=schema['$defs']['BoardState']['properties']['groups']
    assert next(iter(groups['patternProperties'].values()))['maxItems']==5 and 'id' in groups['description']
    bad=data();bad['states'][0]['groups']={'条件甲':['1','2','3'],'条件乙':['4','5','6']}
    with pytest.raises(ValidationError) as exc:ExplainerBoard.model_validate(bad)
    assert any(e['type']=='string_pattern_mismatch' for e in exc.value.errors())
    bad=data();bad['states'][0]['groups']={'a':['1','2','3','4','5','6'],'b':[]}
    with pytest.raises(ValidationError):ExplainerBoard.model_validate(bad)


def test_renderer_does_not_add_an_unrequested_step_order_to_classification(font,tmp_path,monkeypatch):
    from easel.production import boards
    original=boards._label;labels=[]
    def observed(draw,text,*args,**kwargs):
        labels.append(text);return original(draw,text,*args,**kwargs)
    monkeypatch.setattr(boards,'_label',observed)
    d=data();d['cards'][0]['text']='1. 显式步骤'
    b=ExplainerBoard.model_validate(d)
    path=render_board(b,0,font_path=font,aspect_ratio='16:9',destination=tmp_path/'literal.png')
    assert path.is_file() and '1. 显式步骤' in labels
    assert not any(str(i) in labels for i in range(1,7))
    assert any('6 条' in value and '2 组' in value for value in labels)


@pytest.mark.parametrize('aspect', ['16:9','9:16'])
def test_dense_board_keeps_subtitle_space_and_all_card_text(font,tmp_path,aspect):
    d=data()
    d['cards']=[{'id':str(i),'text':f'第{i}项：对照具体行动'} for i in range(1,11)]
    d['states']=[{'title':'两组行动对照','groups':{'a':[str(i) for i in range(1,6)],'b':[str(i) for i in range(6,11)]},'highlight_ids':['3']}]
    b=ExplainerBoard.model_validate(d)
    path=render_board(b,0,font_path=font,aspect_ratio=aspect,destination=tmp_path/'dense.png')
    image=Image.open(path)
    w,h=image.size
    # Reserved lower region is actually clear, not just described in a prompt.
    region=image.crop((0,int(h*.8),w,int(h*.93)))
    assert len(region.getcolors(region.width*region.height))==1
    assert [c.text for c in b.cards]==[c['text'] for c in d['cards']]
