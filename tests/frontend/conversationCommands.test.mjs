import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { runInNewContext } from 'node:vm';
const require=createRequire(new URL('../../web/frontend/package.json',import.meta.url));
const ts=require('typescript');
function runtime() {
  const storage=new Map();let counter=0;const calls=[];const exports={};
  const localStorage={getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v)};
  const source=readFileSync(new URL('../../web/frontend/src/lib/conversationApi.ts',import.meta.url),'utf8');
  const load=()=>{const fresh={};runInNewContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,{exports:fresh,require:()=>({productionCommand:(...args)=>{calls.push(args);return Promise.resolve({});}}),localStorage,crypto:{randomUUID:()=>`command-${++counter}`},window:{location:{pathname:'/studio/index.html'}},fetch:async(url,options)=>{calls.push([url,JSON.parse(options.body)]);return {ok:true,json:async()=>({})};}});return fresh;};
  return {api:load(),reload:load,calls};
}
test('pending command identity survives reload, response loss, and target revision changes',async()=>{
  const r=runtime();await r.api.workCommand('w1',7,'outputs/o1/accept',{manual_review_confirmed:true});
  await r.reload().workCommand('w1',7,'outputs/o1/accept',{manual_review_confirmed:true});
  assert.equal(r.calls[0][4],r.calls[1][4]);
  await r.api.workCommand('w1',8,'outputs/o1/accept',{manual_review_confirmed:true});
  await r.api.workCommand('w2',7,'outputs/o1/accept',{manual_review_confirmed:true});
  assert.notEqual(r.calls[0][4],r.calls[2][4]);assert.notEqual(r.calls[0][4],r.calls[3][4]);
});
test('proposal confirmation and dismissal retain separate fixed identities with the exact displayed hash',async()=>{
  const r=runtime();const p={id:'p',body_hash:'content-v1'};
  await r.api.applyProposal('ui',p);await r.reload().applyProposal('ui',p);await r.api.applyProposal('ui',p,true);
  assert.equal(r.calls[0][1].command_id,r.calls[1][1].command_id);
  assert.notEqual(r.calls[0][1].command_id,r.calls[2][1].command_id);
  assert.equal(r.calls[0][1].hash,'content-v1');assert.equal(r.calls[2][1].dismiss,true);
  assert.ok(r.calls[0][0].startsWith('/studio/api/chat/video/'));
});
