import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { runInNewContext } from 'node:vm';
const require=createRequire(new URL('../../web/frontend/package.json',import.meta.url));
const ts=require('typescript');
function runtime({context,failRead=false,failEnter=false}={}) {
  const calls=[];const exports={};
  const source=readFileSync(new URL('../../web/frontend/src/lib/conversationWorkflows.ts',import.meta.url),'utf8');
  runInNewContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,{
    exports,require:()=>({
      videoRequest:async(path)=>{calls.push({type:'view',path});if(failRead)throw Error('binding unavailable');return {context};},
      enterVideo:async(session,entry)=>{calls.push({type:'enter',session,entry:JSON.parse(JSON.stringify(entry))});if(failEnter)throw Error('上一轮待核实');return {segment_id:'segment-'+entry.kind};},
    }),
  });
  return {api:exports,calls};
}
test('all three chat pipelines bind the current UI without chat send, Work creation or catalog save',async()=>{
  const r=runtime();
  assert.deepEqual(Array.from(r.api.CONVERSATION_WORKFLOWS,w=>w.label),['视频创作','导演','频道']);
  for(const flow of r.api.CONVERSATION_WORKFLOWS){
    const binding=await r.api.enterConversationWorkflow({id:'current-chat',persona:'one'},flow.kind);
    assert.equal(binding.segment_id,'segment-'+flow.kind);
    assert.deepEqual(r.calls.at(-1),{type:'enter',session:'current-chat',entry:{kind:flow.kind,profile_ref:'one'}});
  }
  assert.equal(r.calls.length,3);
});
test('new video discussion retains selected channel/director but never binds the previous Work or output',async()=>{
  const r=runtime({context:{profile_ref:'actual-profile',channel_id:'channel',work_id:'previous',output_id:'A',settings:{director_revision:'d1',director_trial:true}}});
  await r.api.enterConversationWorkflow({id:'same-ui',persona:'other',videoSegmentId:'old'},'new_work');
  assert.deepEqual(r.calls,[{type:'view',path:'same-ui'},{type:'enter',session:'same-ui',entry:{kind:'new_work',profile_ref:'actual-profile',channel_id:'channel',director_revision:'d1',director_trial:true}}]);
});
test('channel creation clears the old target while director formation can stay in the selected channel',async()=>{
  const r=runtime({context:{profile_ref:'one',channel_id:'old-channel',settings:{director_revision:'old-director'}}});
  const session={id:'current',videoSegmentId:'bound'};
  await r.api.enterConversationWorkflow(session,'channel_create');
  assert.deepEqual(r.calls.at(-1).entry,{kind:'channel_create',profile_ref:'one'});
  await r.api.enterConversationWorkflow(session,'director_formation');
  assert.deepEqual(r.calls.at(-1).entry,{kind:'director_formation',profile_ref:'one',channel_id:'old-channel'});
});
test('explicit no-profile context does not borrow the UI profile on pipeline switching',async()=>{
  const r=runtime({context:{profile_ref:null}});
  await r.api.enterConversationWorkflow({id:'ui',persona:'other',videoSegmentId:'bound'},'channel_create');
  assert.deepEqual(r.calls.at(-1).entry,{kind:'channel_create'});
});
test('unavailable context stops before entry and a pending native turn rejects without a fallback',async()=>{
  const missing=runtime({failRead:true});
  await assert.rejects(missing.api.enterConversationWorkflow({id:'ui',videoSegmentId:'bound'},'new_work'),/binding unavailable/);
  assert.deepEqual(missing.calls,[{type:'view',path:'ui'}]);
  const pending=runtime({failEnter:true});
  await assert.rejects(pending.api.enterConversationWorkflow({id:'ui'},'director_formation'),/待核实/);
  assert.equal(pending.calls.length,1);assert.equal(pending.calls[0].type,'enter');
});
test('pipeline starters preserve the Creator draft and switching starters never stacks conflicting instructions',()=>{
  const r=runtime();const draft='本期主题：理解用户\n保留我的措辞和附件。';
  const first=r.api.workflowDraft('director_formation',draft);
  assert.ok(first.endsWith(draft));
  const second=r.api.workflowDraft('channel_create',first);
  assert.ok(second.endsWith(draft));assert.ok(!second.includes('我想用参考视频创建一个导演'));
  assert.equal(r.api.workflowDraft('channel_create',second),second);
  assert.equal(r.api.workflowDraft('new_work',''),r.api.CONVERSATION_WORKFLOWS[0].prompt);
});
test('switching away from generated edit prompts preserves only Creator input, never the old configuration task',()=>{
  const r=runtime();const user='请保留我自己补充的这句话。';
  for(const flow of Object.values(r.api.CONFIGURATION_PROMPTS)){
    const switched=r.api.workflowDraft('new_work',flow.edit+'\n\n'+user);
    assert.equal(switched,r.api.CONVERSATION_WORKFLOWS[0].prompt+'\n\n'+user);
    assert.equal(r.api.workflowDraft('director_formation',flow.edit),r.api.CONFIGURATION_PROMPTS.director_formation.create);
  }
});
