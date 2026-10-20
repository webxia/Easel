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
test('ordinary main retains tools and context, no work bridge requests',async()=>{
 const r=runtime();const old=globalThis.fetch;globalThis.fetch=()=>{throw Error('must not query')};
 try{
  assert.equal(r.tools(ordinary),null);
  assert.equal(await r.hooks.get('before_prompt_build')({prompt:'chat'},ordinary),undefined);
  assert.equal(await r.hooks.get('before_agent_run')({prompt:'chat'},ordinary),undefined);
  assert.equal(await r.hooks.get('before_tool_call')({toolName:'exec'},ordinary),undefined);
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
