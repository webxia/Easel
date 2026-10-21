import test from 'node:test';
import assert from 'node:assert/strict';
import {createWorkBridge,persistentToolDefinitions} from '../../agents/plugins/easel-work/tools.mjs';
const ctx={agentId:'main',sessionKey:'agent:main:easel-pipeline:segment',sessionId:'native',runId:'run'};
const ordinary={...ctx,sessionKey:'agent:main:ordinary',runId:'ordinary'};
function runtime(){
 const hooks=new Map();let factory,route;
 createWorkBridge({pluginConfig:{baseUrl:'http://127.0.0.1:12349',token:'fixture-only-long-credential-123456',agentId:'main',protocolVersion:2},
  on:(n,f)=>hooks.set(n,f),registerTool:f=>factory=f,registerHttpRoute:r=>route=r});
 return {hooks,tools:factory,route};
}
const response=data=>new Response(JSON.stringify(data),{status:200});
test('native tool factory without runId dispatches only the hook-bound entry call',async()=>{
 const r=runtime(),old=globalThis.fetch,requests=[];
 const {runId,...factoryCtx}=ordinary;
 const params={mode:'enter',kind:'new_work'};
 globalThis.fetch=async(url,options)=>{requests.push(JSON.parse(options.body));return response({bound:true,entered:true,segment_id:'new',pending:{}})};
 try{
  const tool=r.tools(factoryCtx)[0];
  assert.deepEqual(tool.parameters.required,['mode','kind']);
  assert.equal(tool.parameters.properties.user_quote,undefined);
  await r.hooks.get('before_agent_run')({prompt:'host prompt'},ordinary);
  await r.hooks.get('before_tool_call')({toolName:'easel_pipeline',toolCallId:'native-call',params},ordinary);
  await assert.rejects(r.tools({...factoryCtx,sessionId:'other'})[0].execute('native-call',params),/not_bound/);
  await assert.rejects(tool.execute('wrong-call',params),/not_bound/);
  await assert.rejects(tool.execute('native-call',{...params,user_quote:'forged'}),/not_bound/);
  assert.equal((await tool.execute('native-call',params)).details.entered,true);
  assert.equal(requests[1].run_id,runId);
  await assert.rejects(tool.execute('native-call',params),/not_bound/);
  await r.hooks.get('agent_end')({},ordinary);
  await assert.rejects(tool.execute('native-call',params),/not_bound/);
 }finally{globalThis.fetch=old;}
});

test('ended native entry preparation cannot execute in a later turn',async()=>{
 const r=runtime(),old=globalThis.fetch;
 const {runId,...factoryCtx}=ordinary;
 const params={mode:'enter',kind:'new_work',user_quote:'只讨论'};
 globalThis.fetch=async()=>response({bound:true});
 try{
  await r.hooks.get('before_agent_run')({prompt:'p'},ordinary);
  await r.hooks.get('before_tool_call')({toolName:'easel_pipeline',toolCallId:'stale',params},ordinary);
  await r.hooks.get('agent_end')({},ordinary);
  await r.hooks.get('before_agent_run')({prompt:'p'},{...ordinary,runId:'next'});
  await assert.rejects(r.tools(factoryCtx)[0].execute('stale',params),/not_bound/);
 }finally{globalThis.fetch=old;}
});
test('ordinary main retains general tools and context even without Web entry binding',async()=>{
 const r=runtime();const old=globalThis.fetch;globalThis.fetch=async()=>response({bound:false});
 try{
  assert.deepEqual(r.tools(ordinary).map(t=>t.name),['easel_pipeline']);
  assert.equal(await r.hooks.get('before_prompt_build')({prompt:'chat'},ordinary),undefined);
  assert.equal(await r.hooks.get('before_agent_run')({prompt:'chat'},ordinary),undefined);
  assert.equal(await r.hooks.get('before_tool_call')({toolName:'exec'},ordinary),undefined);
  await r.hooks.get('agent_end')({},ordinary);
 }finally{globalThis.fetch=old;}
});
test('pipeline prompt is scoped, tools narrowed, native preparation mandatory',async()=>{
 const r=runtime(),old=globalThis.fetch;const requests=[];
 globalThis.fetch=async(url,options)=>{requests.push(url);return response(url.endsWith('/claim')?{bound:true,system_prompt:'PRODUCT ONLY',permission_policy:'main-pipeline-v1'}:{ticket:'server-owned-long-ticket-123456'})};
 try{
  assert.equal((await r.hooks.get('before_agent_run')({prompt:'request'},ctx)).outcome,'block');
  const p=await r.hooks.get('before_prompt_build')({prompt:'request'},ctx);
  assert.equal(p.systemPrompt,'PRODUCT ONLY');assert.deepEqual(p.toolsAllow,persistentToolDefinitions.map(t=>t.name));
  assert.equal(await r.hooks.get('before_agent_run')({prompt:'request'},ctx),undefined);
  assert.equal((await r.hooks.get('before_tool_call')({toolName:'exec'},ctx)).block,true);
  assert.equal((await r.hooks.get('before_tool_call')({toolName:'minimax-media__text_to_image'},ctx)).block,true);
  assert.equal((await r.hooks.get('before_agent_run')({prompt:'changed'},ctx)).outcome,'block');
  assert.equal((await r.hooks.get('before_agent_run')({prompt:'request'},{...ctx,runId:'other'})).outcome,'block');
  await r.hooks.get('agent_end')({},ctx);
  assert.equal((await r.hooks.get('before_agent_run')({prompt:'request'},ctx)).outcome,'block');
 }finally{globalThis.fetch=old;}
});
test('failed claim never falls through to general main',async()=>{
 const r=runtime(),old=globalThis.fetch;globalThis.fetch=async()=>{throw Error('offline')};
 try{
  const p=await r.hooks.get('before_prompt_build')({prompt:'request'},ctx);assert.deepEqual(p.toolsAllow,[]);
  assert.equal((await r.hooks.get('before_agent_run')({prompt:'request'},ctx)).outcome,'block');
  assert.equal((await r.hooks.get('before_tool_call')({toolName:'easel_pipeline'},ctx)).block,true);
 }finally{globalThis.fetch=old;}
});

test('concurrent ordinary and pipeline calls do not share restrictions or tickets',async()=>{
 const r=runtime(),old=globalThis.fetch;
 globalThis.fetch=async(url)=>response(url.endsWith('/claim')?{bound:true,system_prompt:'PRODUCT ONLY',permission_policy:'main-pipeline-v1'}:url.endsWith('/prepare')?{ticket:'server-owned-long-ticket-123456'}:{read:true});
 try{
  await r.hooks.get('before_prompt_build')({prompt:'request'},ctx);
  assert.equal(await r.hooks.get('before_tool_call')({toolName:'exec'},ordinary),undefined);
  const other={...ctx,sessionKey:'agent:main:easel-pipeline:other',sessionId:'other',runId:'other'};
  assert.equal((await r.hooks.get('before_tool_call')({toolName:'easel_work_context'},other)).block,true);
  await r.hooks.get('before_tool_call')({toolName:'easel_work_context',toolCallId:'c',params:{}},ctx);
  await assert.rejects(r.tools(other)[0].execute('c',{}),/missing_native_call_binding/);
  await r.hooks.get('agent_end')({},ctx);
  await assert.rejects(r.tools(ctx)[0].execute('c',{}),/missing_native_call_binding/);
 }finally{globalThis.fetch=old;}
});

test('natural entry uses native identity, no arbitrary params, blocks tools after handoff',async()=>{
 const r=runtime(),old=globalThis.fetch,requests=[];
 globalThis.fetch=async(url,options)=>{requests.push(JSON.parse(options.body));return response({bound:true,entered:true,segment_id:'new',pending:{context:{}}})};
 try{
  const tool=r.tools(ordinary)[0],params={mode:'enter',kind:'new_work',user_quote:'只讨论'};
  await assert.rejects(tool.execute('c',params),/not_bound/);
  await r.hooks.get('before_agent_run')({prompt:'host prompt'},ordinary);
  assert.equal(await r.hooks.get('before_tool_call')({toolName:'read'},ordinary),undefined);
  await r.hooks.get('before_tool_call')({toolName:'easel_pipeline',toolCallId:'c',params},ordinary);
  await assert.rejects(tool.execute('c',{...params,kind:'director_formation'}),/not_bound/);
  assert.equal((await tool.execute('c',params)).details.entered,true);
  assert.equal(requests[1].session_key,ordinary.sessionKey);
  assert.equal((await r.hooks.get('before_tool_call')({toolName:'exec'},ordinary)).blockReason,'easel_pipeline_entered_finish_turn');
  await assert.rejects(tool.execute('c',params),/not_bound/);
  assert.equal(await r.hooks.get('before_tool_call')({toolName:'exec'},{...ordinary,runId:'unrelated'}),undefined);
  await r.hooks.get('agent_end')({},ordinary);
  await assert.rejects(tool.execute('c',params),/not_bound/);
 }finally{globalThis.fetch=old;}
});

test('entry preparation blocks parallel general calls before dispatch, including lost receipt',async()=>{
 const r=runtime(),old=globalThis.fetch;
 globalThis.fetch=async(url,options)=>{if(JSON.parse(options.body).mode==='enter')throw Error('lost');return response({bound:true})};
 try{
  await r.hooks.get('before_agent_run')({prompt:'p'},ordinary);
  const params={mode:'enter',kind:'channel_create',user_quote:'讨论频道'};
  await r.hooks.get('before_tool_call')({toolName:'easel_pipeline',toolCallId:'parallel',params},ordinary);
  assert.equal((await r.hooks.get('before_tool_call')({toolName:'exec'},ordinary)).block,true);
  await assert.rejects(r.tools(ordinary)[0].execute('parallel',params),/easel_entry_failed_finish_turn: entry_result_unknown/);
  assert.equal((await r.hooks.get('before_tool_call')({toolName:'exec'},ordinary)).block,true);
  await r.hooks.get('agent_end')({},ordinary);
 }finally{globalThis.fetch=old;}
});

test('claim error blocks run and tools; explicit non-Web response retains ordinary abilities',async()=>{
 const r=runtime(),old=globalThis.fetch;
 try{
  globalThis.fetch=async()=>new Response(JSON.stringify({error:{code:'binding_mismatch'}}),{status:409});
  assert.equal((await r.hooks.get('before_agent_run')({prompt:'p'},ordinary)).outcome,'block');
  assert.equal((await r.hooks.get('before_tool_call')({toolName:'exec'},ordinary)).block,true);
  await r.hooks.get('agent_end')({},ordinary);
  globalThis.fetch=async()=>response({bound:false});
  assert.equal(await r.hooks.get('before_agent_run')({prompt:'p'},ordinary),undefined);
  assert.equal(await r.hooks.get('before_tool_call')({toolName:'read'},ordinary),undefined);
  assert.equal((await r.hooks.get('before_tool_call')({toolName:'easel_pipeline',toolCallId:'c',params:{mode:'enter'}},ordinary)).block,true);
  assert.equal((await r.hooks.get('before_tool_call')({toolName:'exec'},ordinary)).block,true);
  await r.hooks.get('agent_end')({},ordinary);
 }finally{globalThis.fetch=old;}
});

for (const [name, reply, code] of [
 ['HTTP rejection', () => new Response(JSON.stringify({error:{code:'invalid_input',user_message:'exact quote required'}}),{status:400}), 'invalid_input'],
 ['identity rejection', () => new Response(JSON.stringify({error:{code:'binding_mismatch'}}),{status:409}), 'binding_mismatch'],
 ['server failure', () => new Response(JSON.stringify({error:{code:'internal_error'}}),{status:500}), 'internal_error'],
 ['lost receipt', () => {throw Error('private transport detail');}, 'entry_result_unknown'],
 ['timeout', () => {throw new DOMException('timeout','TimeoutError');}, 'entry_result_unknown'],
 ['abort', () => {throw new DOMException('aborted','AbortError');}, 'entry_result_unknown'],
 ['invalid JSON', () => new Response('not JSON'), 'entry_result_unknown'],
 ['negative receipt', () => response({entered:false}), 'invalid_entry_receipt'],
 ['missing pending', () => response({entered:true,segment_id:'s'}), 'invalid_entry_receipt'],
 ['missing segment', () => response({entered:true,pending:{}}), 'invalid_entry_receipt'],
]) test(`natural entry ${name} has a terminal error and never redispatches or opens tools`,async()=>{
 const r=runtime(), old=globalThis.fetch;
 let dispatches=0;
 globalThis.fetch=async(url,options)=>{
  if(JSON.parse(options.body).mode==='claim')return response({bound:true});
  dispatches++;return reply();
 };
 try {
  await r.hooks.get('before_agent_run')({prompt:'p'},ordinary);
  const params={mode:'enter',kind:'new_work',user_quote:'讨论'}, tool=r.tools(ordinary)[0];
  await r.hooks.get('before_tool_call')({toolName:'easel_pipeline',toolCallId:'c',params},ordinary);
  let terminal;
  await assert.rejects(tool.execute('c',params),error=>{
   terminal=error.message;
   assert.ok(terminal.startsWith(`easel_entry_failed_finish_turn: ${code}。`));
   assert.match(terminal,/不得声称已读取画像/);
   assert.match(terminal,/不能据此认定未创建讨论上下文/);
   assert.doesNotMatch(terminal,/private transport detail/);
   assert.ok(error.cause);return true;
  });
  for(const toolName of ['read','exec','easel_work_context','easel_pipeline']){
   assert.deepEqual(await r.hooks.get('before_tool_call')({toolName,toolCallId:'retry',params},ordinary),{block:true,blockReason:terminal});
  }
  for(const id of ['c','retry'])await assert.rejects(tool.execute(id,params),{message:terminal});
  assert.equal(dispatches,1);
 } finally {await r.hooks.get('agent_end')({},ordinary);globalThis.fetch=old;}
});

test('in-flight entry blocks duplicate execution and transitions only on valid success receipt',async()=>{
 const r=runtime(),old=globalThis.fetch;
 let resolveEntry,dispatches=0;
 globalThis.fetch=async(url,options)=>{
  if(JSON.parse(options.body).mode==='claim')return response({bound:true});
  if(JSON.parse(options.body).mode==='end')return response({ended:true});
  dispatches++;return new Promise(resolve=>{resolveEntry=resolve;});
 };
 try {
  await r.hooks.get('before_agent_run')({prompt:'p'},ordinary);
  const params={mode:'enter',kind:'new_work',user_quote:'讨论'},tool=r.tools(ordinary)[0];
  await r.hooks.get('before_tool_call')({toolName:'easel_pipeline',toolCallId:'c',params},ordinary);
  const execution=tool.execute('c',params);
  for(const toolName of ['read','easel_pipeline'])assert.match((await r.hooks.get('before_tool_call')({toolName,toolCallId:'retry',params},ordinary)).blockReason,/^easel_entry_pending_finish_turn/);
  await assert.rejects(tool.execute('c',params),/not_bound/);
  const receipt={entered:true,segment_id:'s',pending:{context:{profile:{identity:'fixture'}}},instruction:'finish'};
  resolveEntry(response(receipt));
  assert.deepEqual((await execution).details,receipt);
  for(const toolName of ['read','easel_pipeline'])assert.equal((await r.hooks.get('before_tool_call')({toolName},ordinary)).blockReason,'easel_pipeline_entered_finish_turn');
  await assert.rejects(tool.execute('c',params),/not_bound/);
  assert.equal(dispatches,1);
 } finally {await r.hooks.get('agent_end')({},ordinary);globalThis.fetch=old;}
});
