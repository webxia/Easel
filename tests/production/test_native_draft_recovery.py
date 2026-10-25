"""A failed pre-freeze native draft is recoverable without an outside script."""
import asyncio,json
from copy import deepcopy
import pytest
from easel.production.store import Store
from easel.production.service import WorkService,encode,digest
from easel.production.operations import OperationService
from easel.production.planning import PlanningTasks,VoiceReadyCreativePlan,DraftReview
from easel.production.worker import Worker,TaskResult
from easel.production.errors import ProductionError


@pytest.mark.parametrize('tamper',[None,'draft','unknown','legacy_exhausted','previous_voice_view'])
def test_known_native_draft_recovery_preserves_receipt_and_never_adopts_external_copy(tmp_path,tamper):
    store=Store(tmp_path/'db');store.initialize();service=WorkService(store,outputs=tmp_path/'outputs',profiles=tmp_path/'profiles')
    voice={'provider':'fixture','model':'speech','engine':'fixture','voice_id':'fixed'}
    settings={'audio_mode':'voice','voice':voice,'aspect_ratio':'16:9'}
    work=service.command('create',{'title':'one idea','input_text':'学会了吗？','settings':settings},command_id='create')['work_id']
    identity={'provider':'direct-api','model':'fixture','mode':'structured'}
    service.command('plan',{'services':[identity]},work_id=work,expected_revision=1,command_id='plan')
    draft={'title':'native-old','summary':'假设例子','script':'换一个条件，自己再试一次。',
           'settings':{**settings,'duration_seconds':20},'scenes':[{'id':'s1','purpose':'解释','visual':'真实场景',
           'duration_seconds':20,'narration':'换一个条件，自己再试一次。','required_input_ids':[]}]}
    class Model:
        capabilities=frozenset({'text','structured'})
        def __init__(self):self.calls=[];self.authors=0;self.reviews=0
        async def complete(self,messages,tools,schema):
            self.calls.append(deepcopy(messages))
            if schema['title']=='DraftReview':
                self.reviews+=1
                answer={'verdict':'fail' if self.reviews==1 else 'pass','findings':['需要具体例子'] if self.reviews==1 else []}
            else:
                self.authors+=1;answer=deepcopy(draft)
                if self.authors>1:
                    context=json.loads(messages[1]['content'][0]['text']);assert context['plan']['title']=='native-old'
                    answer['title']='native-repaired'
            return {'content':json.dumps(answer)}
    model=Model();planning=PlanningTasks(service,OperationService(store),model,identity,'fixture')
    async def checkpoint_handler(ctx):
        context=planning.context(ctx)
        author=planning.runner(ctx)
        candidate=await author.run(context,'native draft',VoiceReadyCreativePlan)
        review=await planning.runner(ctx,namespace='draft-audit-v3-0').run(context,'native review',DraftReview)
        planning._store_draft(ctx,candidate,planning._native_operation(ctx,author),0,[review.model_dump(mode='json')],review)
        return TaskResult(state='needs_decision',work_state='needs_decision',error=ProductionError('draft_review_failed','草稿未通过'))
    asyncio.run(Worker(store,{'plan':checkpoint_handler}).run_once());before=service.snapshot(work)
    assert before['state']=='needs_decision' and len(model.calls)==2
    task=before['tasks'][0]
    with store.connection() as c:
        ops=[dict(r) for r in c.execute('SELECT * FROM operations WHERE task_id=? ORDER BY created_at',(task['id'],))]
    original=ops[0]['receipt_json']
    if tamper:
        with store.transaction() as c:
            if tamper=='draft':
                forged=VoiceReadyCreativePlan.model_validate(draft).model_dump(mode='json');forged['title']='operator-copy'
                payload=json.loads(c.execute('SELECT payload_json FROM tasks WHERE id=?',(task['id'],)).fetchone()[0])
                payload['native_draft_checkpoint']={'producer_task_id':task['id'],'draft':forged,'draft_hash':digest(forged),
                    'source_operation_id':ops[0]['id'],'correction_round':1,'history':[],'review':None}
                c.execute('UPDATE tasks SET payload_json=? WHERE id=?',(encode(payload),task['id']))
            elif tamper=='unknown':c.execute("UPDATE operations SET state='unknown',receipt_json=NULL WHERE id=?",(ops[1]['id'],))
            else:
                payload=json.loads(c.execute('SELECT payload_json FROM tasks WHERE id=?',(task['id'],)).fetchone()[0])
                checkpoint=payload['native_draft_checkpoint']
                checkpoint.pop('review_context_version')
                if tamper=='previous_voice_view':checkpoint['review_context_version']='current-draft-1'
                checkpoint['correction_round']=2
                c.execute('UPDATE tasks SET payload_json=? WHERE id=?',(encode(payload),task['id']))
    service.command('resume',{'decision_id':task['id']},work_id=work,expected_revision=before['revision'],command_id='resume')
    asyncio.run(Worker(store,{'plan':planning.plan}).run_once());after=service.snapshot(work)
    with store.connection() as c:
        assert c.execute('SELECT receipt_json FROM operations WHERE id=?',(ops[0]['id'],)).fetchone()[0]==original
        assert c.execute("SELECT count(*) FROM operations WHERE kind!='MODEL'").fetchone()[0]==0
    if tamper in {'draft','unknown'}:
        assert after['state']=='needs_decision' and not after['plans'] and len(model.calls)==2
        error=json.loads(after['tasks'][0]['error_json'])
        assert error['code']==('result_unknown' if tamper=='unknown' else 'draft_provenance_missing')
    elif tamper in {'legacy_exhausted','previous_voice_view'}:
        assert after['state']=='awaiting_confirmation'
        assert after['plans'][0]['plan']['title']=='native-old'
        assert len(model.calls)==3 and model.authors==1 and model.reviews==2
        with store.connection() as c:
            payload=json.loads(c.execute('SELECT payload_json FROM tasks WHERE id=?',(task['id'],)).fetchone()[0])
            assert payload['native_draft_checkpoint']['correction_round']==2
            for op in ops:
                saved=dict(c.execute('SELECT * FROM operations WHERE id=?',(op['id'],)).fetchone())
                assert saved['request_json']==op['request_json'] and saved['receipt_json']==op['receipt_json']
    else:
        assert after['state']=='awaiting_confirmation' and after['plans'][0]['plan']['title']=='native-repaired'
        assert len(model.calls)==4 and model.authors==2
        from easel.production.expression_policy import RULES
        assert RULES["write"] in model.calls[-2][0]["content"]
        assert RULES["review"] in model.calls[-1][0]["content"]
        with store.connection() as c:
            payload=json.loads(c.execute('SELECT payload_json FROM tasks WHERE id=?',(task['id'],)).fetchone()[0])
            assert payload['native_draft_checkpoint']['draft']['title']=='native-repaired'


@pytest.mark.parametrize('tamper',[None,'parameters','identity','script','unknown'])
def test_normalized_voice_draft_recovery_preserves_actual_provenance(tmp_path,tamper):
    from easel.production.planning import preserve_selected_voice_parameters
    from tests.production.test_planning_runtime import setup
    service,work,transport,_=setup(tmp_path)
    voice={'provider':'fixture','model':'speech','engine':'minimax-speech-v1','voice_id':'fixed','parameters':{'speed':1}}
    settings={'schema_version':1,'audio_mode':'mixed','voice':voice,'aspect_ratio':'16:9','duration_seconds':3}
    with service.store.transaction() as c:
        c.execute('UPDATE works SET settings_json=? WHERE id=?',(encode(settings),work))
    transport.answer['settings']={k:v for k,v in settings.items() if k!='schema_version'}
    transport.answer['settings']['voice']={**voice,'parameters':{'speed':1.4,'volume':1,'pitch':0}}
    planning=PlanningTasks(service,OperationService(service.store),transport,{'provider':'direct-api','model':'fixture','mode':'structured'},'fixture-v1')
    async def save_old_view(ctx):
        author=planning.runner(ctx)
        candidate=await author.run(planning.context(ctx),'native draft',VoiceReadyCreativePlan)
        preserve_selected_voice_parameters(candidate,voice)
        await planning.runner(ctx,namespace='draft-audit-v4-2').run(planning.context(ctx),'old view audit',DraftReview)
        planning._store_draft(ctx,candidate,planning._native_operation(ctx,author),2,[],DraftReview(verdict='fail',findings=['缺少volume/pitch']))
        with ctx.transaction() as c:
            p=json.loads(c.execute('SELECT payload_json FROM tasks WHERE id=?',(ctx.task_id,)).fetchone()[0])
            p['native_draft_checkpoint']['review_context_version']='current-draft-1'
            c.execute('UPDATE tasks SET payload_json=? WHERE id=?',(encode(p),ctx.task_id))
        return TaskResult(state='needs_decision',work_state='needs_decision',error=ProductionError('draft_review_failed','旧视图'))
    asyncio.run(Worker(service.store,{'plan':save_old_view}).run_once())
    before=service.snapshot(work);task=before['tasks'][0]
    with service.store.connection() as c:
        op=dict(c.execute('SELECT * FROM operations').fetchone())
    if tamper:
        with service.store.transaction() as c:
            p=json.loads(c.execute('SELECT payload_json FROM tasks WHERE id=?',(task['id'],)).fetchone()[0])
            cp=p['native_draft_checkpoint']
            if tamper=='unknown':c.execute("UPDATE operations SET state='unknown' WHERE id=?",(op['id'],))
            else:
                if tamper=='parameters':cp['draft']['settings']['voice']['parameters']={'speed':1.9}
                elif tamper=='identity':cp['draft']['settings']['voice']['voice_id']='forged'
                else:
                    cp['draft']['script']='外部替换。';cp['draft']['scenes'][0]['narration']='外部替换。'
                cp['draft_hash']=digest(cp['draft'])
                c.execute('UPDATE tasks SET payload_json=? WHERE id=?',(encode(p),task['id']))
    service.command('resume',{'decision_id':task['id']},work_id=work,expected_revision=before['revision'],command_id='resume-normalized')
    asyncio.run(Worker(service.store,{'plan':planning.plan}).run_once())
    after=service.snapshot(work)
    with service.store.connection() as c:
        saved=dict(c.execute('SELECT * FROM operations WHERE id=?',(op['id'],)).fetchone())
        assert saved['request_json']==op['request_json'] and saved['receipt_json']==op['receipt_json']
        cp=json.loads(c.execute('SELECT payload_json FROM tasks WHERE id=?',(task['id'],)).fetchone()[0])['native_draft_checkpoint']
        assert cp['correction_round']==2
    if tamper:
        assert after['state']=='needs_decision' and not after['plans']
        assert transport.calls==2
        assert json.loads(after['tasks'][0]['error_json'])['code']==('result_unknown' if tamper=='unknown' else 'draft_provenance_missing')
    else:
        assert after['state']=='awaiting_confirmation',after['tasks'][0]['error_json']
        assert transport.calls==3
        assert after['plans'][0]['plan']['settings']['voice']==voice
