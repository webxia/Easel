import test from 'node:test';
import assert from 'node:assert/strict';
import {configuredParameters,outputDiagnostic,installDiagnostics} from '../../agents/plugins/easel-work/diagnostics.mjs';

test('diagnostics expose known numeric settings and counts, never bodies or keys', () => {
  const config={models:{providers:{minimax:{apiKey:'SECRET',models:[{id:'m',maxTokens:8192}]}}},
    agents:{defaults:{models:{'minimax/m':{params:{maxTokens:8192,extra_body:{reasoning_effort:'medium',thinking:{type:'adaptive'},private:'SECRET'}}}}}}};
  const params=configuredParameters(config,'easel-video','minimax','m');
  assert.equal(params.parameter_source,'configured_not_wire');assert.equal(params.max_tokens,8192);
  const result=outputDiagnostic({stopReason:'length',responseId:'PRIVATE-ID',content:[{type:'thinking',thinking:'PRIVATE REASONING'}],usage:{input:0,output:0,total:0,private:'SECRET'}});
  assert.equal(result.usage_status,'missing_or_zero');assert.equal(result.reasoning_chars,17);assert.equal(result.text_chars,0);
  assert.doesNotMatch(JSON.stringify({params,result}),/PRIVATE|SECRET/);
  assert.equal(outputDiagnostic({}, {input:5}).usage_status,'reported');
});
test('scoped native hooks retain terminal length even if llm_output never fires',async () => {
  const hooks={};const api={config:{},on:(name,fn)=>hooks[name]=fn};
  const finish=installDiagnostics(api,'easel-video');
  const ctx={agentId:'easel-video',runId:'run'};
  hooks.llm_input({provider:'fake',model:'m'},ctx);
  for(let n=0;n<12;n++)hooks.model_call_ended({durationMs:n,outcome:'completed',requestPayloadBytes:20},ctx);
  const d=finish({messages:[{role:'assistant',content:[],stopReason:'length',usage:{input:0}}]},ctx);
  assert.equal(d.stop_reason,'length');assert.equal(d.calls.length,8);
  assert.equal(d.usage_status,'missing_or_zero');
  assert.equal(finish({messages:[]},ctx).calls.length,0);
  hooks.model_call_ended({durationMs:3},{agentId:'other',runId:'foreign'});
  assert.equal(finish({messages:[]},{runId:'foreign'}).calls.length,0);
});
