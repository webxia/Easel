import test from 'node:test';
import assert from 'node:assert/strict';
import {createWorkBridge,persistentToolDefinitions} from '../../agents/plugins/easel-work/tools.mjs';
const ctx={agentId:'main',sessionKey:'agent:main:easel-pipeline:segment',sessionId:'native',runId:'run'};
const ordinary={...ctx,sessionKey:'agent:main:ordinary',runId:'ordinary'};
function runtime(automaticBootstrap=true){
 const hooks=new Map(),nativeHooks=new Map();let factory,route;
 createWorkBridge({pluginConfig:{baseUrl:'http://127.0.0.1:12349',token:'fixture-only-long-credential-123456',agentId:'main',protocolVersion:2},
  on:(n,f)=>hooks.set(n,f),registerHook:(n,f)=>nativeHooks.set(n,f),registerTool:f=>factory=f,registerHttpRoute:r=>route=r});
 const rawPrompt=hooks.get('before_prompt_build');
 if(automaticBootstrap) hooks.set('before_prompt_build',async(event,context)=>{
  if(context.sessionKey?.startsWith('agent:main:easel-pipeline:')){
   const old=globalThis.fetch;
   try{
    globalThis.fetch=async()=>response({bootstrap_policy:'product-bootstrap-v1',system_prompt:'PRODUCT ONLY'});
    await nativeHooks.get('agent:bootstrap')({context:{...context,workspaceDir:'/fixture',bootstrapFiles:[]}});
   }finally{globalThis.fetch=old;}
  }
  return rawPrompt(event,context);
 });
 return {hooks,nativeHooks,rawPrompt,tools:factory,route};
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

test('official overflow retry reclaims original turn despite continuation prompt; only final end closes it',async()=>{
 const r=runtime(),old=globalThis.fetch,requests=[];
 const initial='用户要求修改方案';const continuation='Continue from the current transcript after compaction.';
 globalThis.fetch=async(url,options)=>{const body=JSON.parse(options.body);requests.push({url,body});
  if(url.endsWith('/claim')){assert.equal(body.prompt,initial);return response({bound:true,permission_policy:'main-pipeline-v1',system_prompt:'PRODUCT ONLY'});}
  return response(url.endsWith('/prepare')?{ticket:'server-owned-long-ticket-123456'}:{ended:true});
 };
 try{
  await r.hooks.get('before_prompt_build')({prompt:initial},ctx);
  await r.hooks.get('before_tool_call')({toolName:'easel_pipeline',toolCallId:'before-overflow',params:{mode:'pending'}},ctx);
  await r.hooks.get('agent_end')({success:false,error:'Context overflow: prompt too large for the model (mid-turn precheck).'},ctx);
  assert.equal(requests.filter(x=>x.url.endsWith('/end')).length,0);
  await assert.rejects(r.tools(ctx).find(t=>t.name==='easel_pipeline').execute('before-overflow',{mode:'pending'}),/missing_native_call_binding/);
  const policy=await r.hooks.get('before_prompt_build')({prompt:continuation},ctx);
  assert.equal(policy.systemPrompt,'PRODUCT ONLY');
  assert.equal(await r.hooks.get('before_agent_run')({prompt:continuation},ctx),undefined);
  assert.equal((await r.hooks.get('before_tool_call')({toolName:'exec'},ctx)).block,true);
  assert.equal((await r.hooks.get('before_agent_run')({prompt:continuation},{...ctx,runId:'different'})).outcome,'block');
  assert.equal(requests.filter(x=>x.url.endsWith('/claim')).length,2);
  await r.hooks.get('agent_end')({success:true,messages:[]},ctx);
  assert.equal(requests.filter(x=>x.url.endsWith('/end')).length,1);
  assert.equal((await r.hooks.get('before_agent_run')({prompt:continuation},ctx)).outcome,'block');
 }finally{globalThis.fetch=old;}
});

test('overflow retry still checks server revocation; ordinary failure and quoted overflow do not keep turn active',async()=>{
 const r=runtime(),old=globalThis.fetch;let deny=false;const calls=[];
 globalThis.fetch=async(url)=>{calls.push(url);if(deny&&url.endsWith('/claim'))return new Response(JSON.stringify({error:{code:'binding_mismatch',user_message:'会话已撤销'}}),{status:403});return response({bound:true,permission_policy:'main-pipeline-v1',system_prompt:'ONLY'});};
 try{
  await r.hooks.get('before_prompt_build')({prompt:'first'},ctx);
  await r.hooks.get('agent_end')({messages:[{role:'assistant',stopReason:'error',errorMessage:'Context overflow: prompt too large for the model'}]},ctx);
  deny=true;
  assert.deepEqual((await r.hooks.get('before_prompt_build')({prompt:'continue'},ctx)).toolsAllow,[]);
  assert.equal((await r.hooks.get('before_agent_run')({prompt:'continue'},ctx)).outcome,'block');
  deny=false;await r.hooks.get('before_prompt_build')({prompt:'first'},ctx);
  await r.hooks.get('agent_end')({success:false,error:'network unavailable',messages:[{role:'user',content:'Context overflow:'}]},ctx);
  assert.equal(calls.filter(x=>x.endsWith('/end')).length,1);
  assert.equal((await r.hooks.get('before_agent_run')({prompt:'first'},ctx)).outcome,'block');
 }finally{globalThis.fetch=old;}
});

test('specific missing revision target reaches the model instead of an ambiguous not_found',async()=>{
 const r=runtime(),old=globalThis.fetch;
 globalThis.fetch=async(url)=>url.endsWith('/claim')?response({bound:true,permission_policy:'main-pipeline-v1',system_prompt:'ONLY'}):url.endsWith('/prepare')?response({ticket:'server-owned-long-ticket-123456'}):new Response(JSON.stringify({error:{code:'plan_revision_required',user_message:'当前为未确认方案，使用plan和intent=replan，不要重复确认'}}),{status:409});
 try{
  await r.hooks.get('before_prompt_build')({prompt:'request'},ctx);
  const params={mode:'offer',action:'revise',values:{feedback:'改口播'}};
  await r.hooks.get('before_tool_call')({toolName:'easel_pipeline',toolCallId:'bad-revise',params},ctx);
  await assert.rejects(r.tools(ctx).find(t=>t.name==='easel_pipeline').execute('bad-revise',params),/plan_revision_required:.*未确认方案.*不要重复确认/);
 }finally{globalThis.fetch=old;}
});

test('native bootstrap replaces global instruction files only for a pipeline',async()=>{
 const r=runtime(false),old=globalThis.fetch,requests=[];
 globalThis.fetch=async(url,options)=>{requests.push({url,body:JSON.parse(options.body)});return response({bootstrap_policy:'product-bootstrap-v1',system_prompt:'PRODUCT ONLY'});};
 try{
  const original=[{name:'AGENTS.md',path:'/fixture/AGENTS.md',content:'GENERAL'},
   {name:'SOUL.md',path:'/fixture/SOUL.md',content:'OLD OPTIONS'},
   {name:'MEMORY.md',path:'/fixture/MEMORY.md',content:'OTHER ACCOUNT'}];
  const general={context:{...ordinary,workspaceDir:'/fixture',bootstrapFiles:structuredClone(original)}};
  await r.nativeHooks.get('agent:bootstrap')(general);
  assert.deepEqual(general.context.bootstrapFiles,original);assert.equal(requests.length,0);
  const scoped={context:{...ctx,workspaceDir:'/fixture',bootstrapFiles:structuredClone(original)}};
  await r.nativeHooks.get('agent:bootstrap')(scoped);
  assert.deepEqual(scoped.context.bootstrapFiles,[{name:'AGENTS.md',path:'/fixture/AGENTS.md',missing:false,content:'PRODUCT ONLY'}]);
  assert.deepEqual(original.map(x=>x.content),['GENERAL','OLD OPTIONS','OTHER ACCOUNT']);
  assert.ok(requests[0].url.endsWith('/bootstrap'));
  assert.deepEqual(requests[0].body,{agent_id:'main',session_key:ctx.sessionKey,session_id:ctx.sessionId});
 }finally{globalThis.fetch=old;}
});

test('missing or failed bootstrap blocks model and never restores global memory',async()=>{
 const r=runtime(false),old=globalThis.fetch;
 globalThis.fetch=async()=>{throw Error('offline')};
 try{
  const fresh={...ctx,sessionKey:ctx.sessionKey+'-cold',sessionId:'cold',runId:'cold'};
  assert.deepEqual((await r.rawPrompt({prompt:'request'},fresh)).toolsAllow,[]);
  const event={context:{...fresh,workspaceDir:'/fixture',bootstrapFiles:[{name:'MEMORY.md',content:'PRIVATE'}]}};
  await r.nativeHooks.get('agent:bootstrap')(event);
  assert.deepEqual(event.context.bootstrapFiles,[]);
  assert.deepEqual((await r.rawPrompt({prompt:'request'},fresh)).toolsAllow,[]);
  assert.equal((await r.hooks.get('before_agent_run')({prompt:'request'},fresh)).outcome,'block');
 }finally{globalThis.fetch=old;}
});


test('confirmed-film route hint survives native dispatch but private server failures do not',async()=>{
 const r=runtime(),old=globalThis.fetch;let code='revision_required';
 const hint='已有确认方案；不要更新brief，请绑定成片走scope=narration修订';
 globalThis.fetch=async(url)=>{
  if(url.endsWith('/claim'))return response({bound:true,system_prompt:'PRODUCT ONLY',permission_policy:'main-pipeline-v1'});
  if(url.endsWith('/prepare'))return response({ticket:'server-native-ticket-32-characters'});
  return new Response(JSON.stringify({error:{code,user_message:hint,private:'private-provider-details'}}),{status:409});
 };
 try{
  await r.hooks.get('before_prompt_build')({prompt:'只改最后一句'},ctx);
  const params={entries:[{kind:'user_requirement',text:'只改最后一句',source_refs:['fixture-turn']}]};
  const event={toolName:'easel_work_update_brief',toolCallId:'route-hint',params};
  await r.hooks.get('before_tool_call')(event,ctx);
  const tool=r.tools(ctx).find(t=>t.name==='easel_work_update_brief');
  await assert.rejects(tool.execute(event.toolCallId,params),error=>error.bridgeCode===code && error.message===code+': '+hint);
  code='internal_error';await r.hooks.get('before_tool_call')({...event,toolCallId:'private'},ctx);
  await assert.rejects(tool.execute('private',params),error=>error.message===code);
 }finally{globalThis.fetch=old;}
});

test('native precheck success at tool boundary retains turn but requires authenticated rebuild',async()=>{
 const r=runtime(),old=globalThis.fetch,requests=[];let deny=false;
 const initial='查看已保存的方案，不启动制作';
 globalThis.fetch=async(url,options)=>{
  const body=JSON.parse(options.body);requests.push({url,body});
  if(url.endsWith('/claim')){
   assert.equal(body.prompt,initial);
   if(deny)return new Response(JSON.stringify({error:{code:'binding_mismatch',user_message:'已撤销'}}),{status:403});
   return response({bound:true,permission_policy:'main-pipeline-v1',system_prompt:'PRODUCT ONLY'});
  }
  return response(url.endsWith('/prepare')?{ticket:'server-owned-long-ticket-123456'}:{ended:true});
 };
 const boundary={success:true,messages:[{role:'assistant',stopReason:'toolUse',content:[]},{role:'toolResult',content:[]}]};
 try{
  await r.hooks.get('before_prompt_build')({prompt:initial},ctx);
  await r.hooks.get('before_tool_call')({toolName:'easel_pipeline',toolCallId:'old-ticket',params:{mode:'pending'}},ctx);
  // Exact installed native precheck shape: no event.error or assistant error.
  await r.hooks.get('agent_end')(boundary,ctx);
  assert.equal(requests.filter(x=>x.url.endsWith('/end')).length,0);
  await assert.rejects(r.tools(ctx).find(t=>t.name==='easel_pipeline').execute('old-ticket',{mode:'pending'}),/missing_native_call_binding/);
  assert.equal((await r.hooks.get('before_agent_run')({prompt:initial},ctx)).outcome,'block');
  const continuation='Continue from the current transcript after precheck.';
  assert.equal((await r.hooks.get('before_prompt_build')({prompt:continuation},ctx)).systemPrompt,'PRODUCT ONLY');
  assert.equal(await r.hooks.get('before_agent_run')({prompt:continuation},ctx),undefined);
  assert.equal((await r.hooks.get('before_agent_run')({prompt:continuation},{...ctx,runId:'foreign'})).outcome,'block');
  await r.hooks.get('agent_end')(boundary,ctx);deny=true;
  assert.deepEqual((await r.hooks.get('before_prompt_build')({prompt:'retry again'},ctx)).toolsAllow,[]);
  assert.equal((await r.hooks.get('before_agent_run')({prompt:'retry again'},ctx)).outcome,'block');
 }finally{globalThis.fetch=old;}
});

test('tool boundary failure, abort and final assistant still end exactly once',async()=>{
 for(const ending of [
  {success:false,error:'network unavailable',messages:[{role:'assistant',stopReason:'toolUse'},{role:'toolResult'}]},
  {success:false,messages:[{role:'assistant',stopReason:'toolUse'},{role:'toolResult'}]},
  {success:true,messages:[{role:'assistant',stopReason:'toolUse'},{role:'toolResult'},{role:'assistant',stopReason:'stop',content:[]}]},
  {success:true,messages:[{role:'user',content:'Context overflow:'}]},
 ]){
  const r=runtime(),old=globalThis.fetch,requests=[];
  globalThis.fetch=async(url)=>{requests.push(url);return response({bound:true,permission_policy:'main-pipeline-v1',system_prompt:'ONLY'});};
  try{
   await r.hooks.get('before_prompt_build')({prompt:'view'},ctx);
   await r.hooks.get('agent_end')(ending,ctx);
   assert.equal(requests.filter(x=>x.endsWith('/end')).length,1);
   assert.equal((await r.hooks.get('before_agent_run')({prompt:'view'},ctx)).outcome,'block');
  }finally{globalThis.fetch=old;}
 }
});

test('acceptance rejection retains the exact safe service reason rather than a bare code',async()=>{
 for(const [code,message] of [
  ['quality_blocked','源制作仍在执行，不能接受；自动内容fail本身不禁止完整人工审片后接受'],
  ['manual_review_confirmation_required','请完整审阅画面声音字幕同步并确认全部通过'],
 ]){
  const r=runtime(),old=globalThis.fetch;
  globalThis.fetch=async(url)=>url.endsWith('/claim')?response({bound:true,permission_policy:'main-pipeline-v1',system_prompt:'ONLY'}):url.endsWith('/prepare')?response({ticket:'server-owned-long-ticket-123456'}):new Response(JSON.stringify({error:{code,user_message:message}}),{status:422});
  try{
   await r.hooks.get('before_prompt_build')({prompt:'接受此版'},ctx);
   const params={mode:'offer',action:'accept',values:{output_id:'out'}};
   await r.hooks.get('before_tool_call')({toolName:'easel_pipeline',toolCallId:'accept',params},ctx);
   await assert.rejects(r.tools(ctx).find(t=>t.name==='easel_pipeline').execute('accept',params),error=>error.message===code+': '+message);
  }finally{globalThis.fetch=old;}
 }
});
