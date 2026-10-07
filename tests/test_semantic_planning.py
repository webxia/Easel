"""Independent semantic oracle and native Planning v3 integration regressions."""
from pathlib import Path
import json
import pytest
from easel.materials.domain import MaterialPlan
from easel.materials.application.visual_contract import planning_contracts

FIXTURE = Path(__file__).parent / 'fixtures/planning-semantic-contract-2026-10-07'


def test_real_fourth_failure_replays_before_any_supply():
    plan = MaterialPlan.model_validate_json((FIXTURE / 'MATERIAL_PLAN.json').read_text())
    raw = json.loads((FIXTURE / 'MATERIAL_REQUIREMENTS.json').read_text())
    with pytest.raises(ValueError, match='原文路径无效'):
        planning_contracts(plan, {}, raw)
    repair = json.loads((FIXTURE / 'repair.json').read_text())
    assert 'needs.9.modality_spec.voice:value_error' in repair['message']
    assert 'constraints/subtitle_overlay_only' not in repair['message']


def semantic_draft():
    # Independent fixed input and expected labels, never derived with sources_for.
    return {'schema': 'semantic-planning-draft@1', 'needs': [{
        'scope': {'type': 'scene', 'ref': 'scene-1'}, 'role': 'visual',
        'intent': {'description': '两张白纸放在桌上。', 'function': '让观众先看问题。'},
        'importance': 'required', 'modality_spec': {'kind': 'image'},
        'constraints': {'preferred_visual_details': '暖光。'},
        'queries': ['white paper desk', 'two sheets table', 'paper documents room']} ]}


def test_semantic_draft_compiles_identity_and_lossless_independent_contract():
    from easel.integrations.semantic_planning import compile_draft, classification_batches, assemble_requirements
    refs = {'creative_mode_sha256': 'm'}
    plan = compile_draft(semantic_draft(), creation_id='synthetic', attempt_id='synthetic-a',
                         refs=refs, mode={}, script='先看问题。', allowed_refs={'scene': {'scene-1'}})
    assert plan.needs[0].intent.description == '两张白纸放在桌上。'
    assert plan.needs[0].importance.value == 'required'
    batches = classification_batches(plan, {})
    response = {'classifications': [{'id': 0, 'kind': 'required', 'preference_source': None},
                                   {'id': 1, 'kind': 'postproduction', 'preference_source': None}]}
    result = assemble_requirements(plan, {}, [response])
    rows = result[plan.needs[0].need_id]['clauses']
    assert [(r['path'], r['text'], r['kind']) for r in rows] == [
        ('intent/description', '两张白纸放在桌上。', 'required'),
        ('intent/function', '让观众先看问题。', 'postproduction'),
        ('constraints/preferred_visual_details', '暖光。', 'preference')]
    assert len(batches) == 1


from tests.test_creation_preparation import prep_env


def test_semantic_product_owner_reaches_first_supply_and_observation(prep_env, tmp_path, monkeypatch):
    from tests.planning_material_matrix.cases import test_26_semantic_owner_supply
    from tests.planning_material_matrix.conftest import Trace
    from tests.test_creation_preparation import web
    monkeypatch.setattr(web, '_hypit_runtime_profile', lambda: None)
    test_26_semantic_owner_supply(prep_env, tmp_path, monkeypatch, Trace())

from copy import deepcopy
from tests.test_material_integration import material_integration_env
from easel.integrations.semantic_planning import (
    compile_draft, classification_batches, assemble_requirements, SemanticPlanningError,
    run_semantic_planning, read_file, write_file, encode, verify_semantic_checkpoint,
)


def compile_input(draft=None, **extra):
    return compile_draft(draft or semantic_draft(),creation_id='synthetic',attempt_id='synthetic-a',
        refs={'creative_mode_sha256':'m'},mode={},script='先看问题。',
        allowed_refs={'scene':{'scene-1'}, 'event':{'event-1'}},**extra)


@pytest.mark.parametrize('variant', ['derived_id','wrong_modality','voice_text','unknown_scope','duplicate_json',
                                    'bad_query','query_copy','missing_required','voice_on_visual'])
def test_semantic_transport_rejects_independent_bad_inputs(variant):
    d=semantic_draft();n=d['needs'][0]
    if variant=='derived_id':n['need_id']='invented'
    elif variant=='wrong_modality':n['modality_spec']['kind']='unknown'
    elif variant=='voice_text':
        n['modality_spec']={'kind':'voice','identity':{'source':'explicit_user','reference':'中性旁白'},'text_ref':'planning/SCRIPT.md'}
    elif variant=='unknown_scope':n['scope']['ref']='not-confirmed'
    elif variant=='duplicate_json':d='{"schema":"semantic-planning-draft@1","needs":[],"needs":[]}'
    elif variant=='bad_query':n['queries']=['paper','paper','paper']
    elif variant=='query_copy':n['constraints']['search_query_en']='paper'
    elif variant=='missing_required':n['importance']='optional'
    elif variant=='voice_on_visual':n['constraints']['voice_delivery']={'tone':'neutral'}
    with pytest.raises(SemanticPlanningError):compile_input(d)


def labels():
    return {'classifications':[{'id':0,'kind':'required','preference_source':None},
                              {'id':1,'kind':'postproduction','preference_source':None}]}


@pytest.mark.parametrize('variant',['unknown','missing','duplicate','preference','unresolved','empty_required','metadata'])
def test_classification_binding_rejects_independent_relational_errors(variant):
    response=labels()
    if variant=='unknown':response['classifications'][0]['id']=99
    elif variant=='missing':response['classifications'].pop()
    elif variant=='duplicate':response['classifications'][1]['id']=0
    elif variant=='preference':response['classifications'][0].update(kind='preference',preference_source=99)
    elif variant=='unresolved':response['classifications'][0]['kind']='unresolved'
    elif variant=='empty_required':response['classifications'][0]['kind']='postproduction'
    elif variant=='metadata':response['queries']=['invented','query','copy']
    with pytest.raises(SemanticPlanningError):assemble_requirements(compile_input(),{},[response])


def test_semantic_identity_key_order_crlf_and_required_source_action_protection():
    d=semantic_draft();a=compile_input(d)
    reordered=json.loads(json.dumps(d,sort_keys=True));assert compile_input(reordered)==a
    changed=deepcopy(d);changed['needs'][0]['intent']['description']='两张白纸放在桌上。\r\n没有标志。'
    b=compile_input(changed);assert b.plan_id!=a.plan_id and b.needs[0].need_id!=a.needs[0].need_id
    units=classification_batches(b,{})[0]['units']
    assert ''.join(u['text'] for u in units if u['source']==0)=='两张白纸放在桌上。\r\n没有标志。'
    d['needs'][0]['constraints']['requires_dynamic_action']=True
    with pytest.raises(SemanticPlanningError):assemble_requirements(compile_input(d),{},[labels()])


def test_semantic_multibatch_merges_whole_need_and_optional_without_dropping_units():
    d=semantic_draft();d['needs'][0]['intent']={'description':'纸。'*38,'function':'后期字幕。'}
    optional=deepcopy(d['needs'][0]);optional.update(importance='optional',intent={'description':'杯子。茶。'})
    d['needs'].append(optional)
    plan=compile_input(d);batches=classification_batches(plan,{})
    assert [len(b['units']) for b in batches]==[40,1]
    responses=[{'classifications':[{'id':u['id'],'kind':'postproduction' if u['text']=='后期字幕。' else 'required',
                 'preference_source':None} for u in b['units']]} for b in batches]
    result=assemble_requirements(plan,{},responses)
    assert len(result)==2 and len(result[plan.needs[0].need_id]['clauses'])==40
    with pytest.raises(SemanticPlanningError):assemble_requirements(plan,{},responses[:1])


@pytest.fixture
def semantic_runtime(material_integration_env, tmp_path, monkeypatch):
    from easel.integrations.hypit.handoff import load_frozen_creative_mode
    from easel.integrations.hypit import service
    monkeypatch.setenv('HOME',str(tmp_path/'isolated-home'))
    attempt=service.update_film_attempt(material_integration_env['attempt_id'],event='test_v3',planning_contract_version=3)
    mode,mode_hash=load_frozen_creative_mode(attempt)
    canonical={'SCRIPT.md':'先看问题。\r\n再做决定。','SCENES.md':'桌上的两张白纸。','TREATMENT.md':'暂停观察。'}
    root=Path(attempt['workspace']['path'])
    for name,text in canonical.items():write_file(root,name,text.encode())
    context={'context_refs':{'creative_mode_sha256':mode_hash},'creator_context':{}}
    calls=[]
    def execute(stage,message,session):
        calls.append({'stage':stage,'session':session,'message':message})
        if message.startswith('〔Easel Semantic Planning V3〕'):name='SEMANTIC_PLAN.json';out=semantic_draft()
        elif message.startswith('〔Easel Planning V3 单元分类〕'):
            name='CLASSIFICATIONS-000.json';data=json.loads(message.splitlines()[-1])
            assert [u['text'] for u in data['units']]==['两张白纸放在桌上。','让观众先看问题。']
            out=labels()
        else:
            data=json.loads(message.splitlines()[-1]);name=data['targets'][0]
            out=semantic_draft() if name=='SEMANTIC_PLAN.json' else {'batches':[{'index':0,**labels()}]}
        (root/'planning'/name).write_bytes(encode(out))
    def run(dispatch=None):return run_semantic_planning(attempt,context,canonical,mode,
                     {'profile':'fixture-only','thinking':'off','timeout':60},dispatch or execute)
    return {'attempt':attempt,'root':root,'mode':mode,'canonical':canonical,'context':context,
            'calls':calls,'execute':execute,'run':run}


def test_native_semantic_checkpoint_persistence_reentry_and_tamper(semantic_runtime):
    from easel.integrations.material_layer import PlanningIntegration, MaterialIntegrationError
    rt=semantic_runtime;result=rt['run']();assert len(rt['calls'])==2
    expected=result['plan'];assert rt['run']()['plan']==expected and len(rt['calls'])==2
    saved=PlanningIntegration().persist(rt['attempt'],**{k:result[k] for k in ('plan','script','scenes','treatment')})
    assert saved['manifest']['schema']=='easel-material-planning@3'
    assert PlanningIntegration().load(saved['attempt'])['plan']==expected
    for name in ('SEMANTIC_PLAN.json','SEMANTIC_CHECKPOINT.json'):
        raw=read_file(rt['root'],name);(rt['root']/'planning'/name).write_bytes(raw+b' ')
        with pytest.raises(MaterialIntegrationError):PlanningIntegration().load(saved['attempt'])
        (rt['root']/'planning'/name).write_bytes(raw)
    assert len(rt['calls'])==2


@pytest.mark.parametrize('stage',['A','B'])
def test_native_semantic_shared_repair_once_and_repeat_uses_original_request(semantic_runtime,stage):
    rt=semantic_runtime
    def dispatch(s,message,session):
        rt['execute'](s,message,session)
        if s=='planning' and (stage=='A' and message.startswith('〔Easel Semantic') or stage=='B' and '单元分类' in message):
            name='SEMANTIC_PLAN.json' if stage=='A' else 'CLASSIFICATIONS-000.json'
            data=semantic_draft() if stage=='A' else labels()
            if stage=='A':data['invented_id']='not-allowed'
            else:data['classifications'][0]['id']=99
            (rt['root']/'planning'/name).write_bytes(encode(data))
    first=rt['run'](dispatch);assert len(rt['calls'])==3
    assert [c['stage'] for c in rt['calls']].count('structure_repair')==1
    assert rt['run'](dispatch)['plan']==first['plan'] and len(rt['calls'])==3


def test_native_semantic_a_repair_then_b_error_does_not_buy_second_repair(semantic_runtime):
    rt=semantic_runtime
    def dispatch(s,message,session):
        rt['execute'](s,message,session)
        if message.startswith('〔Easel Semantic'):
            d=semantic_draft();d['unknown']='field';(rt['root']/'planning/SEMANTIC_PLAN.json').write_bytes(encode(d))
        elif '单元分类' in message:
            d=labels();d['classifications'].pop();(rt['root']/'planning/CLASSIFICATIONS-000.json').write_bytes(encode(d))
    for _ in range(2):
        with pytest.raises(SemanticPlanningError,match='额度已用完'):rt['run'](dispatch)
    assert len(rt['calls'])==3
    assert not (rt['root']/'planning/MATERIAL_PLAN.json').exists()


def test_native_semantic_unknown_execution_recovers_same_stage_and_snapshot_change_stops(semantic_runtime):
    from easel.creation_delivery import DeliveryExecutionUncertain
    rt=semantic_runtime;pending=[True]
    def dispatch(s,message,session):
        if pending[0] and '单元分类' in message:
            pending[0]=False
            rt['calls'].append({'stage':s,'session':session,'message':message})
            raise DeliveryExecutionUncertain('fixture unknown')
        rt['execute'](s,message,session)
    with pytest.raises(DeliveryExecutionUncertain):rt['run'](dispatch)
    assert not (rt['root']/'planning/MATERIAL_PLAN.json').exists()
    result=rt['run'](dispatch)
    assert rt['calls'][1]['session']==rt['calls'][2]['session']
    assert result['plan'].needs[0].importance.value=='required'
    rt['canonical']['SCRIPT.md']+='改字。'
    with pytest.raises(SemanticPlanningError,match='输入、版本'):rt['run'](dispatch)
    assert len(rt['calls'])==3


@pytest.mark.parametrize('field', ['intent','importance','constraints','modality_spec','queries','duration_hint'])
def test_native_repair_cannot_change_valid_semantics_on_first_or_resumed_run(semantic_runtime,field):
    rt=semantic_runtime
    original=semantic_draft();original['unknown']='transport-error'
    original['needs'][0]['duration_hint']={'target_seconds':3}
    repaired=deepcopy(original);repaired.pop('unknown')
    changes={'intent':{'description':'一张纸。'},'importance':'optional','constraints':{},
             'modality_spec':{'kind':'video'},'queries':['cup table','glass room','mug counter'],
             'duration_hint':{'target_seconds':2}}
    repaired['needs'][0][field]=changes[field]
    def dispatch(s,message,session):
        rt['calls'].append({'stage':s,'session':session})
        assert '单元分类' not in message
        (rt['root']/'planning/SEMANTIC_PLAN.json').write_bytes(encode(repaired if s=='structure_repair' else original))
    for _ in range(2):
        with pytest.raises(SemanticPlanningError,match='有效需求语义'):rt['run'](dispatch)
    assert len(rt['calls'])==2 and not (rt['root']/'planning/MATERIAL_PLAN.json').exists()


def test_native_repair_can_correct_invalid_importance_without_changing_valid_intent(semantic_runtime):
    rt=semantic_runtime
    def dispatch(s,message,session):
        rt['execute'](s,message,session)
        if message.startswith('〔Easel Semantic'):
            d=semantic_draft();d['needs'][0]['importance']='requird'
            (rt['root']/'planning/SEMANTIC_PLAN.json').write_bytes(encode(d))
    assert rt['run'](dispatch)['plan'].needs[0].importance.value=='required'
    rt['run'](dispatch);assert len(rt['calls'])==3


def audio_draft():
    d={'schema':'semantic-planning-draft@1','needs':[]}
    for kind in ('voice','bgm','sfx'):
        spec={'kind':kind}
        if kind=='voice':spec['identity']={'source':'creator_context','reference':'creator_context.voice'}
        if kind=='sfx':spec['event_description']='杯子落桌声。'
        d['needs'].append({'scope':{'type':'event' if kind=='sfx' else 'global',
                                  'ref':'event-1' if kind=='sfx' else 'global'},'role':kind,
            'intent':{'description':{'voice':'克制讲述。','bgm':'轻音乐。','sfx':'杯子落桌声。'}[kind]},
            'importance':'required','modality_spec':spec})
    return d


def test_native_pure_audio_and_mixed_plan_keep_all_modalities_and_voice_byte_binding(semantic_runtime):
    from easel.integrations.material_layer import PlanningIntegration
    import hashlib
    rt=semantic_runtime;rt['context']['creator_context']={'voice':{'tone':'克制'}}
    draft=audio_draft()
    def dispatch(s,message,session):
        rt['calls'].append({'stage':s,'session':session})
        assert '单元分类' not in message
        (rt['root']/'planning/SEMANTIC_PLAN.json').write_bytes(encode(draft))
    result=rt['run'](dispatch);plan=result['plan']
    assert [n.modality_spec.kind for n in plan.needs]==['voice','bgm','sfx']
    voice=plan.needs[0].modality_spec
    assert voice.text_ref=='planning/SCRIPT.md' and voice.text_sha256==hashlib.sha256(rt['canonical']['SCRIPT.md'].encode()).hexdigest()
    assert json.loads(read_file(rt['root'],'MATERIAL_REQUIREMENTS.json'))=={}
    saved=PlanningIntegration().persist(rt['attempt'],**{k:result[k] for k in ('plan','script','scenes','treatment')})
    assert PlanningIntegration().load(saved['attempt'])['plan']==plan
    rt['run'](dispatch);assert len(rt['calls'])==1
    mixed=semantic_draft();mixed['needs'].extend(draft['needs'])
    mixedplan=compile_draft(mixed,creation_id='synthetic',attempt_id='synthetic-a',refs={},mode={},script='克制讲述。',
        allowed_refs={'scene':{'scene-1'},'event':{'event-1'},'global':{'global'},'voice':{'creator_context.voice':{'source':'creator_context'}}})
    assert len(mixedplan.needs)==4 and len(assemble_requirements(mixedplan,{},[labels()]))==1
    bad=deepcopy(mixed);bad['needs'][1]['modality_spec']['identity']['reference']='invented provider voice'
    with pytest.raises(SemanticPlanningError,match='实际存在'):
        compile_draft(bad,creation_id='synthetic',attempt_id='synthetic-a',refs={},mode={},script='克制讲述。',
            allowed_refs={'scene':{'scene-1'},'event':{'event-1'},'global':{'global'},'voice':{'creator_context.voice':{'source':'creator_context'}}})


def test_native_classifier_tamper_freezes_failure_and_partial_outputs_never_commit(semantic_runtime):
    rt=semantic_runtime
    def dispatch(s,message,session):
        rt['execute'](s,message,session)
        if '单元分类' in message:
            d=semantic_draft();d['needs'][0]['importance']='optional'
            (rt['root']/'planning/SEMANTIC_PLAN.json').write_bytes(encode(d))
    with pytest.raises(SemanticPlanningError,match='分类阶段改写'):rt['run'](dispatch)
    with pytest.raises(SemanticPlanningError,match='有效语义草稿原件变化'):rt['run'](dispatch)
    assert len(rt['calls'])==2 and not (rt['root']/'planning/MATERIAL_PLAN.json').exists()


def test_native_semantic_checkpoint_copy_binds_new_attempt_without_replanning(semantic_runtime):
    from easel.integrations.hypit import service
    from easel.integrations.material_layer import PlanningIntegration,MaterialIntegrationError
    rt=semantic_runtime;result=rt['run']()
    saved=PlanningIntegration().persist(rt['attempt'],**{k:result[k] for k in ('plan','script','scenes','treatment')})
    source=PlanningIntegration().load(saved['attempt']);original=source['plan']
    target=service.create_film_attempt(original.creation_id,saved['attempt']['handoff']['handoff_id'],
                                      preparation_key='c'*64,runtime_status='NOT_CONFIGURED')
    target=service.update_film_attempt(target['attempt_id'],event='test_copy_v3',planning_contract_version=3)
    targetroot=Path(target['workspace']['path'])
    for name in ('MATERIAL_REQUIREMENTS.json','SEMANTIC_PLAN.json','SEMANTIC_CHECKPOINT.json'):
        service._copy_retry_checkpoint_file(rt['root'],targetroot,Path('planning')/name)
    copied=original.model_copy(update={'attempt_id':target['attempt_id'],'plan_id':'copied-plan'})
    origin={'creation_id':original.creation_id,'attempt_id':original.attempt_id,'plan_id':original.plan_id}
    persisted=PlanningIntegration().persist(target,copied,script=result['script'],scenes=result['scenes'],
        treatment=result['treatment'],requirements_source={**source['requirements'],'origin':origin})
    assert PlanningIntegration().load(persisted['attempt'])['plan']==copied
    assert len(rt['calls'])==2
    bad={**source['requirements'],'origin':{**origin,'attempt_id':'unrelated'}}
    with pytest.raises(MaterialIntegrationError):
        PlanningIntegration().persist(target,copied,script=result['script'],scenes=result['scenes'],
            treatment=result['treatment'],requirements_source=bad)


def test_native_multibatch_repairs_only_affected_batch_and_keeps_successful_response(semantic_runtime):
    rt=semantic_runtime;d=semantic_draft()
    d['needs'][0]['intent']={'description':'纸。'*38,'function':'后期字幕。'}
    optional=deepcopy(d['needs'][0]);optional.update(importance='optional',intent={'description':'杯子。茶。'})
    d['needs'].append(optional)
    def correct(batch):return {'classifications':[{'id':u['id'],
        'kind':'postproduction' if u['text']=='后期字幕。' else 'required','preference_source':None} for u in batch['units']]}
    def dispatch(s,message,session):
        rt['calls'].append({'stage':s,'session':session,'message':message})
        data=json.loads(message.splitlines()[-1])
        if message.startswith('〔Easel Semantic'):name='SEMANTIC_PLAN.json';out=d
        elif '单元分类' in message:
            index=0 if session.endswith('B0') else 1;name=f'CLASSIFICATIONS-{index:03}.json';out=correct(data)
            if index==1:out['classifications'][0]['id']=99
        else:
            assert [b['index'] for b in data['context']['batches']]==[1]
            name='CLASSIFICATIONS-REPAIR.json';out={'batches':[{'index':1,**correct(data['context']['batches'][0])}]}
        (rt['root']/'planning'/name).write_bytes(encode(out))
    result=rt['run'](dispatch);assert len(result['plan'].needs)==2
    raw=read_file(rt['root'],'CLASSIFICATIONS-000.json')
    rt['run'](dispatch)
    assert len(rt['calls'])==4 and read_file(rt['root'],'CLASSIFICATIONS-000.json')==raw


@pytest.mark.parametrize('outcome',['timeout','release_pending'])
def test_native_v3_gateway_adapter_recovers_original_run_without_resubmission(semantic_runtime,outcome):
    import subprocess
    from easel import creation
    from easel.creation_delivery import active_delivery, DeliveryExecutionUncertain
    from easel.integrations.openclaw_delivery import run_delivery_agent
    rt=semantic_runtime;cid=rt['attempt']['creation_id']
    with creation.edit_creation(cid) as work:work['delivery']={'agent_calls':{},'last_operation':'prepare'}
    methods=[];run_id=None;terminal=False;released=False;pending_message=None;pending_session=None
    def rpc(command,**kwargs):
        nonlocal run_id,released,pending_message,pending_session
        method=command[command.index('call')+1];params=json.loads(command[command.index('--params')+1]);methods.append(method)
        if method=='agent':
            if '单元分类' not in params['message']:
                rt['execute']('planning',params['message'],params['sessionKey'])
                return subprocess.CompletedProcess(command,0,json.dumps({'runId':params['idempotencyKey'],'status':'ok','endedAt':1000}),'')
            run_id=params['idempotencyKey'];pending_message=params['message'];pending_session=params['sessionKey']
            if outcome=='timeout':raise subprocess.TimeoutExpired(command,20)
            rt['execute']('planning',pending_message,pending_session)
            return subprocess.CompletedProcess(command,0,json.dumps({'runId':run_id,'status':'ok','endedAt':1000}),'')
        if method=='agent.wait':
            assert params=={'runId':run_id,'timeoutMs':0}
            if terminal:rt['execute']('planning',pending_message,pending_session)
            return subprocess.CompletedProcess(command,0,json.dumps({'runId':run_id,'status':'ok' if terminal else 'pending',
                                                                     'endedAt':1000 if terminal else None}),'')
        assert method=='sessions.abort'
        if outcome=='release_pending' and pending_session==params['key'] and not released:
            released=True;raise subprocess.TimeoutExpired(command,20)
        return subprocess.CompletedProcess(command,0,json.dumps({'ok':True,'status':'no-active-run'}),'')
    def dispatch(stage,message,session):
        cmd=['openclaw','--profile','fixture-only','agent','--agent','main','--session-key','agent:main:'+session,
             '--thinking','off','--timeout','60','--message',message]
        return run_delivery_agent(cmd,runner=rpc,retry_failed=False)
    token=active_delivery.set(cid)
    try:
        with pytest.raises((DeliveryExecutionUncertain,subprocess.TimeoutExpired)):rt['run'](dispatch)
        stored=creation.get_creation(cid)['delivery']['agent_calls']
        old={k:(v['run_id'],v['request_sha256']) for k,v in stored.items()}
        if outcome=='timeout':
            with pytest.raises(DeliveryExecutionUncertain):rt['run'](dispatch)
            terminal=True
        result=rt['run'](dispatch);rt['run'](dispatch)
        stored=creation.get_creation(cid)['delivery']['agent_calls']
        assert old=={k:(v['run_id'],v['request_sha256']) for k,v in stored.items()}
        assert methods.count('agent')==2 and all(v['runtime_release']=='released' for v in stored.values())
        assert result['plan'].needs[0].intent.description=='两张白纸放在桌上。'
    finally:active_delivery.reset(token)


@pytest.mark.parametrize('legacy',['ok','error','release_pending','artifact','repair'])
def test_native_preparation_does_not_upgrade_existing_legacy_planning(prep_env,monkeypatch,legacy):
    from tests.test_creation_preparation import _prepare_creation,creation,service,prep
    from easel.creator_proposal import parse_video_plan
    from tests.test_model_output_contracts import proposal
    from easel.materials.store import AttemptMaterialStore
    work=prep_env['work'];result=_prepare_creation(work['id'],runtime_profile=None)
    attempt=service.get_film_attempt(result['attempt_id'])
    service.update_film_attempt(attempt['attempt_id'],event='test_legacy_uncommitted',
                                planning_contract_version=None,material_planning={})
    root=Path(attempt['workspace']['path'])
    for name in ('MATERIAL_PLAN.json','MATERIAL_REQUIREMENTS.json'):
        (root/'planning'/name).unlink(missing_ok=True)
    with creation.edit_creation(work['id']) as current:
        current['preparation']['status']='MATERIAL_FAILED'
        current['delivery']={'video_plan':parse_video_plan(proposal('先看问题。')),'agent_calls':{}}
        if legacy in {'ok','error','release_pending'}:
            current['delivery']['agent_calls']['original']={'status':'error' if legacy=='error' else 'ok',
                'session_key':'agent:main:material-planning-'+attempt['attempt_id'],
                'runtime_release':'pending' if legacy=='release_pending' else 'released'}
    if legacy=='artifact':(root/'planning/MATERIAL_PLAN.json').write_bytes(b'{}')
    if legacy=='repair':AttemptMaterialStore(root).write_recovery_record('planning-structure-repair-original',{'status':'failed'})
    seen=[]
    def observe_only(a,context):
        seen.append(a.get('planning_contract_version'))
        raise prep.PreparationError('fixture stopped before legacy dispatch')
    observe_only.planning_contract_version=3
    with pytest.raises(prep.PreparationError,match='fixture stopped'):
        _prepare_creation(work['id'],runtime_profile=None,planning_executor=observe_only)
    assert seen==[None] and service.get_film_attempt(attempt['attempt_id']).get('planning_contract_version') is None


def test_native_repair_protects_valid_child_while_fixing_invalid_sibling(semantic_runtime):
    rt=semantic_runtime
    original=semantic_draft();original['needs'][0]['intent']['function']=123
    def dispatch(s,message,session):
        rt['calls'].append({'stage':s,'session':session})
        result=deepcopy(original)
        if s=='structure_repair':
            result['needs'][0]['intent']={'description':'一张纸。','function':'让观众先看问题。'}
        (rt['root']/'planning/SEMANTIC_PLAN.json').write_bytes(encode(result))
    for _ in range(2):
        with pytest.raises(SemanticPlanningError,match='intent.description'):rt['run'](dispatch)
    assert len(rt['calls'])==2


def test_native_repair_can_remove_misplaced_audio_control_and_preserve_visual(semantic_runtime):
    rt=semantic_runtime
    def dispatch(s,message,session):
        rt['execute'](s,message,session)
        if message.startswith('〔Easel Semantic'):
            d=semantic_draft();d['needs'][0]['constraints']['voice_delivery']={'tone':'neutral'}
            (rt['root']/'planning/SEMANTIC_PLAN.json').write_bytes(encode(d))
    result=rt['run'](dispatch);assert result['plan'].needs[0].intent.description=='两张白纸放在桌上。'
    rt['run'](dispatch);assert len(rt['calls'])==3


def test_repair_preserves_optional_model_and_voice_delivery_valid_children():
    from easel.integrations.semantic_planning import _preserve_repair_semantics
    d=semantic_draft();d['needs'][0]['duration_hint']={'target_seconds':3,'unknown':'transport'}
    fixed=deepcopy(d);fixed['needs'][0]['duration_hint']={'target_seconds':3}
    _preserve_repair_semantics(encode(d),encode(fixed))
    bad=deepcopy(fixed);bad['needs'][0]['duration_hint']['target_seconds']=1
    with pytest.raises(SemanticPlanningError,match='target_seconds'):_preserve_repair_semantics(encode(d),encode(bad))
    d=audio_draft();d['needs'][0]['constraints']={'voice_delivery':{'tone':'neutral','pace_ratio':1.05,'unknown':1}}
    fixed=deepcopy(d);fixed['needs'][0]['constraints']['voice_delivery'].pop('unknown')
    _preserve_repair_semantics(encode(d),encode(fixed))
    for key,value in [('tone','happy'),('pace_ratio',1.1)]:
        bad=deepcopy(fixed);bad['needs'][0]['constraints']['voice_delivery'][key]=value
        with pytest.raises(SemanticPlanningError,match=key):_preserve_repair_semantics(encode(d),encode(bad))
    d=semantic_draft();d['policy']={'strategy':'bulk_first'}
    fixed=deepcopy(d);fixed['policy']['strategy']='changed'
    with pytest.raises(SemanticPlanningError,match='策略'):_preserve_repair_semantics(encode(d),encode(fixed))


@pytest.mark.parametrize('variant',['optional_duration','voice_parameter'])
def test_native_repair_valid_children_remain_protected_after_reentry(semantic_runtime,variant):
    rt=semantic_runtime;original=semantic_draft()
    if variant=='optional_duration':
        original['needs'][0]['duration_hint']={'target_seconds':3,'unknown':'transport'}
        repaired=deepcopy(original);repaired['needs'][0]['duration_hint']={'target_seconds':1}
        location='target_seconds'
    else:
        rt['context']['creator_context']={'voice':{'tone':'克制'}}
        original=audio_draft();original['needs']=original['needs'][:1]
        original['needs'][0]['constraints']={'voice_delivery':{'tone':'sad','pace_ratio':3}}
        repaired=deepcopy(original);repaired['needs'][0]['constraints']['voice_delivery']={'tone':'happy','pace_ratio':1}
        location='voice_delivery.tone'
    def dispatch(s,message,session):
        rt['calls'].append({'stage':s,'session':session})
        assert '单元分类' not in message
        (rt['root']/'planning/SEMANTIC_PLAN.json').write_bytes(encode(repaired if s=='structure_repair' else original))
    for _ in range(2):
        with pytest.raises(SemanticPlanningError,match=location):rt['run'](dispatch)
    assert len(rt['calls'])==2 and not (rt['root']/'planning/MATERIAL_PLAN.json').exists()
