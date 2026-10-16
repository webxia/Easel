from pathlib import Path
import os,json,hashlib,uuid,importlib.util,sys,time,re,subprocess
"""S5-C isolated Repair experiment; never resumes an existing Attempt.

No real execution by import. `--check` does read-only frozen input/schema
preflight. `--live --authorize-one-request --run-id <fresh>` is a separate
operator-approved action; at most one HTTP, no retries, and no Supply/Build.
An existing run ID is rejected, never resumed or overwritten.
"""
import argparse
from pathlib import Path
import os, sys, json, hashlib

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

parser=argparse.ArgumentParser(description='S5-C frozen Repair preflight or single approved model request')
parser.add_argument('--check', action='store_true')
parser.add_argument('--live', action='store_true')
parser.add_argument('--authorize-one-request', action='store_true')
parser.add_argument('--run-id', default=None)
args=parser.parse_args()
if args.check == args.live or (args.live and not args.authorize_one_request) or (args.live and (not args.run_id or not args.run_id.startswith('r') or not args.run_id[1:].isalnum())):
    parser.error('select --check or explicitly authorized --live with a fresh --run-id')
if args.check:
    from easel.integrations import planning_candidate_review as review, planning_wire as wire
    from easel.integrations.planning_structured import request_for
    import glob
    base=Path.home()/'.local/share/easel/creator-task-evidence'
    source=base/'2026-10-14-real-minimax-p0-medium-s5-r02'
    journal_path=next((source/'live/eval-runtime/hypit/workspaces').glob('*/*/materials/recoveries/semantic-planning-vnext.json'))
    journal=json.loads(journal_path.read_text())
    frozen=[p for p in (source/'live/requests').glob('*.json') if any('单次局部修复' in str(m.get('content','')) for m in json.loads(p.read_text())['messages'])]
    assert len(frozen)==1 and len(journal['repair']['targets'])==7
    schema=wire.project(review.patch_schema(journal['repair']['targets'],slots=True),'repair',atomic_framing=True).schema
    assert json.loads(frozen[0].read_text())['tools'][0]['function']['parameters']==schema
    print(json.dumps({'status':'CHECK_PASS','target_count':7,'schema_sha256':request_for(schema)['schemaSha256'],
        'source_journal_sha256':hashlib.sha256(journal_path.read_bytes()).hexdigest(),
        'max_http':1,'retry':0,'real_model_called':False},ensure_ascii=False))
    sys.exit(0)

os.umask(0o077)
base=Path.home()/'.local/share/easel/creator-task-evidence'
src=base/'2026-10-14-real-minimax-p0-medium-s5-r02'
out=base/('2026-10-14-real-minimax-p0-medium-s5c-once-' + args.run_id)
if out.exists():raise RuntimeError('S5-C identity already exists; not retrying')
out.mkdir(mode=0o700)
M=json.loads((src/'manifest.json').read_text());jpath=next((src/'live/eval-runtime/hypit/workspaces').glob('*/*/materials/recoveries/semantic-planning-vnext.json'));J=json.loads(jpath.read_text());
requestfile=None
for f in (src/'live/requests').glob('*.json'):
 d=json.loads(f.read_text());
 if any('单次局部修复' in str(m.get('content','')) for m in d['messages']):
  if requestfile:raise RuntimeError('ambiguous repair request')
  requestfile=f
assert requestfile
original=json.loads(requestfile.read_text());user=original['messages'][-1]['content']
anchor='candidate_answer只修该条响应并提供真实冻结引用；其他已接受答案不可变。'
addition=('candidate_answer的每项support必须同时提交source、role、quote三个字段，不能省略quote。'
'当source对应可引用的文本原文时，quote必须是该source的非空连续原文字符串；'
'当source对应非文本原件时，quote必须显式填写JSON null（不是字符串null），不可漏字段。'
'source必须从本目标冻结候选中选择，role与source必须满足同一Schema分支，'
'不要复制其他目标的source或把不合法引用放进修复结果。')
assert user.count(anchor)==1 and addition not in user
user=user.replace(anchor,anchor+addition)
# strip old volatile time preamble for the independent isolated request
user=re.sub(r'^\[[^\n]+\]\s*','',user,count=1)
from easel.integrations import planning_wire as wire,planning_candidate_review as review
from easel.integrations.planning_structured import request_for
schema=wire.project(review.patch_schema(J['repair']['targets'],slots=True),'repair',atomic_framing=True).schema
assert original['tools'][0]['function']['parameters']==schema
tool=request_for(schema)
from easel.integrations.semantic_boundary_run import repair_quote_null_guidance
null_guidance=repair_quote_null_guidance(schema)
assert len(null_guidance)==7 and 'source-0089' in null_guidance['target-0000']
user += ('\n冻结的非文本来源说明 quote_null_source_ids_by_target：'
         + json.dumps(null_guidance,ensure_ascii=False,sort_keys=True,separators=(',',':'))
         + '\n以上 source 的 support.quote 必须为 JSON null，不能是文本、版本号或省略字段。')
manifest={'schema':'s5c-real-single-repair@1','source_journal_sha256':hashlib.sha256(jpath.read_bytes()).hexdigest(),
 'source_request_sha256':hashlib.sha256(requestfile.read_bytes()).hexdigest(),
 'frozen_repair_sha256':J['calls']['repair']['reply_sha256'],
 'tool_schema_sha256':tool['schemaSha256'],'model':'MiniMax-M3.1-Flash-Preview',
 'thinking':'adaptive','reasoning_effort':'medium','maxTokens':8192,'max_http':1,'retry':0,
 'user_prompt_sha256':hashlib.sha256(user.encode()).hexdigest()}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False));
spec=importlib.util.spec_from_file_location('s5c_harness',src/'gateway_harness.py');H=importlib.util.module_from_spec(spec);spec.loader.exec_module(H)
budget=H.EvalHttpBudget(out/'http-ledger',hashlib.sha256((out/'manifest.json').read_bytes()).hexdigest(),limit=1,seconds=1500)
key_path=Path.home()/'.openclaw-easel/openclaw.json'
key=json.loads(key_path.read_text())['models']['providers']['minimax']['apiKey']
proxy=None; gateway=None;result={'result':'NOT_RUN','real_http_max':1}
try:
 proxy=H.EvalProviderProxy(budget,'https://api.minimax.cn/v1/chat/completions',M['model_row']['id'],key,offline=False,
     expected_model_params={'model':M['model_row']['id'],'thinking_mode':'adaptive','reasoning_effort':'medium','max_tokens':None,'max_completion_tokens':8192}).start()
 # Monotonic limit must exist before the proxy handles the first Provider POST.
 proxy.deadline=time.monotonic()+900
 gateway=H.EvalGateway(Path(M['runtime']),out/'gateway',M['node'],proxy,M['model_row'],M['model_params']).start()
 run='easel-'+uuid.uuid4().hex;sid=str(uuid.uuid4());session='agent:main:s5c-'+uuid.uuid4().hex
 proxy.request_identity={'cell':1,'run_id':run,'session_id':sid}
 req={'message':user,'agentId':'main','sessionKey':session,'sessionId':sid,'thinking':'adaptive',
      'timeout':900,'deliver':False,'easelStructuredResult':tool,'idempotencyKey':run}
 (out/'identity.json').write_text(json.dumps({'run_id':run,'session_id':sid,'session_key':session,'schemaSha256':tool['schemaSha256']}))
 response=gateway.rpc('agent',req)
 status=response.get('status');elapsed=time.monotonic();end=elapsed+900
 while status not in ('ok','error') and time.monotonic()<end:
  time.sleep(2)
  response=gateway.rpc('agent.wait',{'runId':run,'timeoutMs':0});status=response.get('status')
 result.update(gateway_status=status,terminal_receipt=bool(response.get('terminalReceipt')),stop_reason=response.get('stopReason'))
 if status=='ok':
  from easel.integrations.planning_transcript import read_original
  c={'reply_contract':'planning-result-v3','agent_id':'main','session_key':session,'session_id':sid,'run_id':run,
     'structured_result':{k:tool[k] for k in ('version','name','schemaSha256')}}
  receipt=read_original([M['node'],str(Path(M['runtime'])/'openclaw.mjs')],'m31-planning-eval',c,env=gateway.env)
  result.update(receipt_state=receipt.get('state'),receipt_meta={k:receipt.get(k) for k in ('stopReason','providerFinishReason','schemaSha256','bytes','toolName')})
  if receipt.get('state')=='FOUND':
   (out/'response.json').write_text(receipt['text']);(out/'response.json').chmod(0o600)
   raw=json.loads(receipt['text']);codec=wire.project(review.patch_schema(J['repair']['targets'],slots=True),'repair',atomic_framing=True)
   errors=codec.errors(raw)
   result.update(wire_errors=errors,root_keys=list(raw),response_sha256=hashlib.sha256(receipt['text'].encode()).hexdigest())
   if not errors:
    canonical=codec.decode_valid(raw);result['result']='WIRE_PASS_DOMAIN_NOT_YET_VERIFIED'
   else:result['result']='WIRE_FAIL'
  else:result['result']='RECEIPT_NOT_FOUND'
 else:result['result']='GATEWAY_NOT_OK'
except Exception as e:
 result.update(result='ERROR',error_type=type(e).__name__,error=str(e)[:250])
finally:
 if gateway: gateway.stop()
 if proxy:proxy.stop()
 budget.close('BATCH_COMPLETE' if result['result']=='WIRE_PASS_DOMAIN_NOT_YET_VERIFIED' else 'BATCH_FAILED')
 led=json.loads(budget.path.read_text());result['http']=[{'number':x['number'],'state':x['state'],'argument_stream_state':x.get('argument_stream_state')} for x in led['requests']]
 (out/'result.json').write_text(json.dumps(result,indent=2,ensure_ascii=False));print(json.dumps(result,ensure_ascii=False))
