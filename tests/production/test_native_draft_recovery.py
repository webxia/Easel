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


@pytest.mark.parametrize('tamper',[None,'draft','unknown'])
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
            else:c.execute("UPDATE operations SET state='unknown',receipt_json=NULL WHERE id=?",(ops[1]['id'],))
    service.command('resume',{'decision_id':task['id']},work_id=work,expected_revision=before['revision'],command_id='resume')
    asyncio.run(Worker(store,{'plan':planning.plan}).run_once());after=service.snapshot(work)
    with store.connection() as c:
        assert c.execute('SELECT receipt_json FROM operations WHERE id=?',(ops[0]['id'],)).fetchone()[0]==original
        assert c.execute("SELECT count(*) FROM operations WHERE kind!='MODEL'").fetchone()[0]==0
    if tamper:
        assert after['state']=='needs_decision' and not after['plans'] and len(model.calls)==2
        error=json.loads(after['tasks'][0]['error_json'])
        assert error['code']==('result_unknown' if tamper=='unknown' else 'draft_provenance_missing')
    else:
        assert after['state']=='awaiting_confirmation' and after['plans'][0]['plan']['title']=='native-repaired'
        assert len(model.calls)==4 and model.authors==2
        from easel.production.expression_policy import RULES
        assert RULES["write"] in model.calls[-2][0]["content"]
        assert RULES["review"] in model.calls[-1][0]["content"]
        with store.connection() as c:
            payload=json.loads(c.execute('SELECT payload_json FROM tasks WHERE id=?',(task['id'],)).fetchone()[0])
            assert payload['native_draft_checkpoint']['draft']['title']=='native-repaired'
