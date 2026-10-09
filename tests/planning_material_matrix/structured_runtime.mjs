// Isolated installed-runtime integration. Only the Provider fetch is replaced.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';

const [root, workspace, payloadPath, schemaPath] = process.argv.slice(2);
const native = name => import(pathToFileURL(path.join(root, name)));
const guard = await native('dist/easel-structured-result.mjs');
const {n: validateRpc} = await native('dist/src-7tzZ8j12.mjs');
const {createOpenAICompletionsTransportStreamFn} = await native('node_modules/@openclaw/ai/dist/transports.mjs');
const {t: configureHost} = await native('node_modules/@openclaw/ai/dist/host-B8YfDGd4.mjs');
const schema = JSON.parse(fs.readFileSync(schemaPath, 'utf8'));
const request = {version: guard.VERSION, name: guard.TOOL, schema,
  schemaSha256: guard.sha256(guard.canonical(schema))};
const rpc = {message: 'offline test', agentId: 'main', sessionId: 'offline-test',
  sessionKey: 'agent:main:offline-test', idempotencyKey: 'offline-test', easelStructuredResult: request};
assert.equal(validateRpc(rpc), true);
assert.equal(validateRpc({...rpc, easelStructuredResult: {...request, name: 'exec'}}), false);
assert.equal(validateRpc({...rpc, clientTools: []}), false);

const model = {id:'MiniMax-M3',provider:'minimax',api:'openai-completions',
  baseUrl:'https://offline.invalid/v1',reasoning:false,input:['text'],
  cost:{input:0,output:0,cacheRead:0,cacheWrite:0},contextWindow:200000,maxTokens:16000};
const context = {messages:[{role:'user',content:'offline semantic input',timestamp:0}],
  tools:[{name:guard.TOOL,description:'semantic candidate',parameters:schema}]};
let scenario, fetches = 0;
const fakeFetch = async (url, init) => {
  assert.equal(new URL(url).hostname,'offline.invalid');
  fetches++;
  const sent = JSON.parse(init.body);
  guard.validatePayload(sent, request);
  const chunks = [];
  for (let offset=0; offset<scenario.raw.length; offset+=16384) {
    const calls = [{index:0,id:'original-tool-id',type:'function',function:{
      name: scenario.wrongTool ? 'exec' : guard.TOOL, arguments:scenario.raw.slice(offset,offset+16384)}}];
    if (scenario.duplicate) calls.push({index:1,id:'second-tool-id',type:'function',
      function:{name:guard.TOOL,arguments:scenario.raw.slice(offset,offset+16384)}});
    chunks.push({id:'offline-response',choices:[{index:0,delta:{tool_calls:calls},finish_reason:null}]});
  }
  if (scenario.finish) chunks.push({id:'offline-response',choices:[{index:0,delta:{},finish_reason:scenario.finish}]});
  let cursor = 0;
  const body = new ReadableStream({pull(controller) {
    if (cursor < chunks.length) {
      controller.enqueue(new TextEncoder().encode('data: '+JSON.stringify(chunks[cursor++])+'\n\n'));
    } else if (scenario.lateError) {
      controller.error(new Error('offline transport failure after candidate'));
    } else {controller.enqueue(new TextEncoder().encode('data: [DONE]\n\n')); controller.close();}
  }});
  return new Response(body,{status:200,headers:{'content-type':'text/event-stream'}});
};
// No request can leave this process; the only external execution boundary is fake.
globalThis.fetch = fakeFetch;
configureHost({buildModelFetch:()=>fakeFetch});
const large = fs.readFileSync(payloadPath,'utf8');
const exact = large + ' '.repeat(guard.MAX_ARGUMENT_BYTES-Buffer.byteLength(large));
const rows = [];
const cases = [
  {name:'legal_large_A',raw:large,finish:'tool_calls',valid:true},
  {name:'exact_8MiB',raw:exact,finish:'tool_calls',valid:true},
  {name:'over_8MiB',raw:exact+' ',finish:'tool_calls',valid:false},
  {name:'duplicate_json_key',raw:'{"needs":[],"needs":[]}',finish:'tool_calls',valid:false},
  {name:'escaped_sensitive_key',raw:String.raw`{"api_\u006bey":"synthetic-value"}`,finish:'tool_calls',valid:false},
  {name:'wrong_tool',raw:large,wrongTool:true,finish:'tool_calls',valid:false},
  {name:'second_tool',raw:'{}',duplicate:true,finish:'tool_calls',valid:false},
  {name:'missing_finish',raw:'{}',valid:false},
  {name:'stop_with_complete_tool',raw:'{}',finish:'stop',valid:false},
  {name:'length_complete_JSON',raw:'{}',finish:'length',valid:false},
  {name:'late_stream_error',raw:'{}',finish:'tool_calls',lateError:true,valid:false},
];
for (scenario of cases) {
  const identity = {runId:scenario.name,sessionId:'offline-test',provider:model.provider,model:model.id};
  const bound = guard.bindAttempt(createOpenAICompletionsTransportStreamFn(),request,identity,
    path.join(workspace,'reservations'));
  const before = fetches;
  const events = [];
  const stream = bound(model,context,{apiKey:'offline-placeholder'});
  for await (const event of stream) events.push(event);
  const result = await stream.result();
  if (scenario.valid) {
    assert.equal(result.stopReason,'toolUse',scenario.name+': '+result.errorMessage);
    const call=result.content.find(block=>block.type==='toolCall');
    assert.equal(call.id,'original-tool-id');
    assert.equal(call.easelRawArguments,scenario.raw);
    assert.equal(result.easelStructuredResult.rawSha256,guard.sha256(scenario.raw));
  } else {
    assert.equal(result.stopReason,'error',scenario.name);
    assert.deepEqual(result.content,[]);
    assert.equal(events.length,1,'Rejected model output leaked partial events');
    const directory=path.join(workspace,'reservations');
    const file=path.join(directory,'rejection-'+guard.sha256(guard.canonical({
      runId:identity.runId,sessionId:identity.sessionId}))+'.json');
    if (!scenario.lateError && scenario.name!=='over_8MiB') {
      const diagnostic=JSON.parse(fs.readFileSync(file,'utf8'));
      assert.equal(diagnostic.runId,identity.runId);
      assert.equal(diagnostic.sessionId,identity.sessionId);
      assert.equal(diagnostic.schemaSha256,request.schemaSha256);
      if (scenario.finish==='stop' || scenario.finish==='length') {
        assert.equal(diagnostic.providerFinishValue,scenario.finish);
        assert.equal(diagnostic.category,'STRUCTURED_TERMINAL_REJECTED');
        // Native reducer discards the unfinished tool at a length terminal.
        assert.equal(diagnostic.toolCallCount,scenario.finish==='length'?0:1);
        assert.equal(diagnostic.uniqueExpectedTool,scenario.finish!=='length');
        assert.equal(diagnostic.rawArgumentBytes,scenario.finish==='length'?null:Buffer.byteLength(scenario.raw));
      }
      assert.equal(fs.readFileSync(file,'utf8').includes('synthetic-value'),false);
    } else assert.equal(fs.existsSync(file),false,'An earlier transport error became a candidate rejection');
  }
  assert.equal(fetches-before,1);
  const retry = bound(model,context,{apiKey:'offline-placeholder'});
  for await (const event of retry) assert.equal(event.type,'error');
  assert.equal((await retry.result()).stopReason,'error');
  assert.equal(fetches-before,1,'Runtime retry reached Provider fetch');
  if (!scenario.valid && !scenario.lateError && scenario.name!=='over_8MiB') {
    const file=path.join(workspace,'reservations','rejection-'+guard.sha256(guard.canonical({
      runId:identity.runId,sessionId:identity.sessionId}))+'.json');
    assert.equal(JSON.parse(fs.readFileSync(file,'utf8')).category,
      scenario.finish==='stop' || scenario.finish==='length' || scenario.wrongTool || scenario.duplicate || !scenario.finish
        ? 'STRUCTURED_TERMINAL_REJECTED'
        : scenario.name==='over_8MiB' ? 'STRUCTURED_CAPACITY_REJECTED' : 'STRUCTURED_STORAGE_REJECTED');
  }
  rows.push({case:scenario.name,result:'PASS',provider_fetches:1,
    raw_bytes:Buffer.byteLength(scenario.raw),accepted:scenario.valid});
}
process.stdout.write(JSON.stringify({kind:'installed-native-transport-integration',
  modules:['AgentParamsSchema','managed request builder','OpenAI SDK','native stream reducer',
    'protected stream','durable submission guard'],provider_boundary:'synthetic fetch',
  real_network_calls:0,rows},null,2)+'\n');
