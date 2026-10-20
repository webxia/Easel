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
test('ordinary main retains general tools and context even without Web entry binding',async()=>{
 const r=runtime();const old=globalThis.fetch;globalThis.fetch=()=>{throw Error('must not query')};
 try{
  assert.deepEqual(r.tools(ordinary).map(t=>t.name),['easel_pipeline']);
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

test('natural entry uses native identity, no arbitrary params, blocks tools after handoff',async()=>{
 const r=runtime(),old=globalThis.fetch,requests=[];
 globalThis.fetch=async(url,options)=>{requests.push(JSON.parse(options.body));return response({bound:true,entered:true,segment_id:'new'})};
 try{
  const tool=r.tools(ordinary)[0],params={mode:'enter',kind:'new_work',user_quote:'只讨论'};
  await assert.rejects(tool.execute('c',params),/not_bound/);
  await r.hooks.get('before_agent_run')({prompt:'host prompt'},ordinary);
  assert.equal(await r.hooks.get('before_tool_call')({toolName:'read'},ordinary),undefined);
  await r.hooks.get('before_tool_call')({toolName:'easel_pipeline',toolCallId:'c',params},ordinary);
  await assert.rejects(tool.execute('c',{...params,kind:'director_formation'}),/not_bound/);
  assert.equal((await tool.execute('c',params)).details.entered,true);
  assert.equal(requests[1].session_key,ordinary.sessionKey);
  assert.equal((await r.hooks.get('before_tool_call')({toolName:'exec'},ordinary)).block,true);
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
  await assert.rejects(r.tools(ordinary)[0].execute('parallel',params),/lost/);
  assert.equal((await r.hooks.get('before_tool_call')({toolName:'exec'},ordinary)).block,true);
  await r.hooks.get('agent_end')({},ordinary);
 }finally{globalThis.fetch=old;}
});
