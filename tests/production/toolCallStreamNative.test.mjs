// E2E-05 synthetic boundary probe. Imports installed code read-only; never opens
// a transport, Gateway, database or model. This is NOT a runtime diagnostic hook.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readdir} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';

const dir=process.env.EASEL_OPENCLAW_AI_DIST;
const enabled={skip:!dir};
async function native() {
  const names=(await readdir(dir)).filter(n=>/^openai-completions-stream-.*\.mjs$/.test(n));
  assert.equal(names.length,1,'ambiguous installed stream module');
  const module=await import(pathToFileURL(`${dir}/${names[0]}`).href);
  assert.equal(typeof module.t,'function');
  return module.t;
}
const delta=(index,name,args)=>({index,id:`fixture-${index}`,type:'function',function:{name,arguments:args}});
const chunk=(calls,finish=null)=>({choices:[{delta:{tool_calls:calls},finish_reason:finish}]});
const model={id:'offline',provider:'fixture',api:'openai-completions',baseUrl:'https://fixture.invalid',reasoning:false,
  cost:{input:0,output:0,cacheRead:0,cacheWrite:0}};
// Whitelist-only, ephemeral structural snapshot of synthetic data. No body,
// argument hash, exception text, tool name or native identifier is exported.
function shape(block) {
  const raw=block.partialArgs;
  let json='absent';
  if(typeof raw==='string') {
    if(!raw.trim()) json='empty';
    else try {const v=JSON.parse(raw);json=v===null?'null':Array.isArray(v)?'array':typeof v;}
    catch {json='invalid';}
  }
  return {name_present:typeof block.name==='string'&&!!block.name.trim(),
    name_syntax:typeof block.name==='string'&&/^[A-Za-z0-9_-]{1,64}$/.test(block.name),json};
}
async function probe(chunks,{fail=false,mode='direct'}={}) {
  const processStream=await native();
  const output={role:'assistant',content:[],stopReason:'stop',usage:{input:0,output:0,cacheRead:0,cacheWrite:0,totalTokens:0,cost:{input:0,output:0,cacheRead:0,cacheWrite:0,total:0}}};
  const evidence={wire_fragments:0,wire_calls:[],assembly:[],terminal:'pending',error:false};
  const byIndex=new Map();
  async function* input() {
    for(const c of chunks) {
      evidence.wire_fragments++;
      for(const d of c.choices[0].delta.tool_calls??[]) {
        const b=byIndex.get(d.index)??{name:'',partialArgs:''};
        if(d.function.name)b.name=d.function.name;
        b.partialArgs+=d.function.arguments??'';byIndex.set(d.index,b);
      }
      yield c;
    }
    evidence.wire_calls=[...byIndex.values()].map(shape);
    if(fail)throw new Error('fixture-private-transport-error');
  }
  // Snapshot immediately: native event.partial is mutable and loses rejected
  // blocks at finalization. Keeping the event reference would destroy evidence.
  try {
    await processStream(input(),output,model,{push(event){
      if(event.type==='toolcall_delta')evidence.assembly=event.partial.content.filter(b=>b.type==='toolCall').map(shape);
    }},{mode,provisionalCommentaryTags:new Map()});
    evidence.terminal=output.stopReason;
  } catch {evidence.error=true;evidence.terminal='thrown';}
  // Simulated dispatcher boundary, not a claim of full Gateway integration.
  const dispatched=evidence.error||output.stopReason!=='toolUse'?0:output.content.filter(b=>b.type==='toolCall').length;
  return {output,evidence,dispatched};
}

for(const [label,name,args,expected] of [
  ['valid single','easel_pipeline','{}',1],
  ['empty name','','{}',0],
  ['empty args','easel_pipeline','',0],
  ['truncated JSON','easel_pipeline','{"mode":',0],
  ['null JSON','easel_pipeline','null',0],
  ['array JSON','easel_pipeline','[]',0],
  ['number JSON','easel_pipeline','42',0],
]) test(`native stream ${label}`,enabled,async()=>{
  const r=await probe([chunk([delta(0,name,args)]),chunk([],'tool_calls')]);
  assert.equal(r.dispatched,expected);
  assert.equal(r.evidence.terminal,expected?'toolUse':'error');
  if(!expected){assert.equal(r.output.content.filter(b=>b.type==='toolCall').length,0);assert.equal(r.output.errorMessage,'Provider returned an incomplete or malformed tool call');}
});
test('native host mode preserves split args and rejects malformed terminal',enabled,async()=>{
  const valid=await probe([chunk([delta(0,'easel_pipeline','{')]),chunk([delta(0,undefined,'}')]),chunk([],'tool_calls')],{mode:'host'});
  assert.equal(valid.dispatched,1);assert.deepEqual(valid.output.content[0].arguments,{});
  const invalid=await probe([chunk([delta(0,'easel_pipeline','{"x":')]),chunk([],'tool_calls')],{mode:'host'});
  assert.equal(invalid.dispatched,0);assert.equal(invalid.evidence.terminal,'error');
  assert.equal(invalid.evidence.wire_calls[0].json,'invalid');
  assert.equal(invalid.evidence.assembly[0].json,'invalid');
});
test('native interleaved multiple calls preserve split argument streams',enabled,async()=>{
  const r=await probe([chunk([delta(0,'easel_pipeline','{"mode":'),delta(1,'easel_work_context','{')]),
    chunk([delta(1,undefined,'}'),delta(0,undefined,'"pending"}')]),chunk([],'tool_calls')]);
  assert.equal(r.dispatched,2);
  assert.deepEqual(r.output.content.map(b=>b.arguments),[{mode:'pending'},{}]);
  assert.deepEqual(r.evidence.wire_calls,r.evidence.assembly);
  assert.equal(r.evidence.wire_fragments,3);
});
test('native malformed member rejects whole batch before dispatch',enabled,async()=>{
  const r=await probe([chunk([delta(0,'easel_pipeline','{}'),delta(1,'easel_work_context','{"x":')]),chunk([],'tool_calls')]);
  assert.equal(r.dispatched,0);assert.equal(r.evidence.terminal,'error');
  assert.equal(r.evidence.wire_calls[1].json,'invalid');
  assert.equal(r.evidence.assembly[1].json,'invalid');
});
test('native upstream iterator failure propagates without dispatch',enabled,async()=>{
  const r=await probe([chunk([delta(0,'easel_pipeline','{}')])],{fail:true});
  assert.equal(r.evidence.error,true);assert.equal(r.dispatched,0);
});
test('native missing finish reason throws without dispatch',enabled,async()=>{
  const r=await probe([chunk([delta(0,'easel_pipeline','{}')])]);
  assert.equal(r.evidence.terminal,'thrown');assert.equal(r.dispatched,0);
});
test('synthetic dual-boundary snapshot survives removal and emits no content',enabled,async()=>{
  const secret='Bearer fixture-private-key private-prompt media-original';
  const r=await probe([chunk([delta(0,secret,JSON.stringify({secret}).slice(0,-1))]),chunk([],'tool_calls')]);
  assert.equal(r.dispatched,0);assert.equal(r.evidence.wire_calls[0].json,'invalid');
  assert.equal(r.evidence.assembly[0].name_syntax,false);
  const serialized=JSON.stringify(r.evidence);
  for(const value of [secret,'Bearer','private-prompt','media-original','fixture-private-key'])assert.ok(!serialized.includes(value));
  assert.ok(!serialized.includes(createHash('sha256').update(secret).digest('hex')));
});
