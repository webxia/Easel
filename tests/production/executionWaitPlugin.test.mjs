import test from 'node:test';
import assert from 'node:assert/strict';
import { awaitExecution } from '../../agents/plugins/easel-work/tools.mjs';

test('native promise stays pending across stages; returns only final result', async () => {
  let phase='supply', settled=false, calls=0; const updates=[];
  const pending=awaitExecution(async path=>{assert.equal(path,'result');calls++;return phase==='quality-done'?{waiting:false,result:{execution_result:{run_state:'succeeded'}}}:{waiting:true,task:{kind:phase}};},{ticket:'bound'},{work_id:'w',run_id:'r'},undefined,v=>updates.push(v),{intervalMs:2}).then(r=>{settled=true;return r;});
  for (const stage of ['supply','tts','edit','render','quality','revise','render']) {
    phase=stage;await new Promise(r=>setTimeout(r,8));assert.equal(settled,false);
  }
  phase='quality-done';assert.equal((await pending).execution_result.run_state,'succeeded');
  assert.ok(calls>7 && updates.length>=7);
});

test('poll failure is wait interruption, never dispatch/retry or production failure', async () => {
  const calls=[];
  const result=await awaitExecution(async (path,body)=>{calls.push([path,body]);throw Error('offline');},{ticket:'bound'},{work_id:'w',run_id:'r'},undefined,undefined,{intervalMs:1});
  assert.equal(result.wait_interrupted,true);assert.equal(result.production_state,'unverified');
  assert.deepEqual(calls.map(x=>x[0]),['result','result']);assert.equal(calls[1][1].interrupted,true);
});

test('waiting deadline returns explicit interruption without changing production', async () => {
  const result=await awaitExecution(async (path,body)=>{assert.equal(body.interrupted,true);return {waiting:false,result:{wait_interrupted:true}};},{},{},undefined,undefined,{budgetMs:0});
  assert.equal(result.wait_interrupted,true);
});

test('native abort interrupts pending sleep without calling cancel or dispatch', async () => {
  const controller=new AbortController();let called=0;
  const pending=awaitExecution(async path=>{assert.equal(path,'result');called++;return {waiting:true};},{},{},controller.signal,undefined,{intervalMs:1000});
  await new Promise(r=>setTimeout(r,5));controller.abort();await assert.rejects(pending,{name:'AbortError'});assert.equal(called,1);
});

test('real progress in same stage emits native updates without fabricated idle heartbeats', async () => {
  const updates=[];let n=0;
  await awaitExecution(async()=> ++n===5 ? {waiting:false,result:{done:true}} : {waiting:true,task:{kind:'supply'},progress_seq:n<3?1:2},{},{},undefined,v=>updates.push(v),{intervalMs:1});
  assert.deepEqual(updates.map(v=>v.details.progress_seq),[1,2]);
});
