import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {runInNewContext} from 'node:vm';
const require=createRequire(new URL('../../web/frontend/package.json',import.meta.url));
const ts=require('typescript');
const exports={};
runInNewContext(ts.transpileModule(readFileSync(new URL('../../web/frontend/src/lib/chatScroll.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,{exports});
const {ChatScrollTracker}=exports;
test('reading an earlier confirmation card survives reply tokens and repeated status updates',()=>{
  const tracker=new ChatScrollTracker();
  assert.equal(tracker.followUpdate('chat',3),true);
  tracker.onScroll(200,3000,700);
  for(let i=0;i<100;i++)assert.equal(tracker.followUpdate('chat',3),false);
  // A final assistant message changes the transcript, not the number of user turns.
  assert.equal(tracker.followUpdate('chat',3),false);
  tracker.onScroll(2300,3000,700);
  assert.equal(tracker.followUpdate('chat',3),true);
});
test('sending a new user message or switching conversations resumes following',()=>{
  const tracker=new ChatScrollTracker();tracker.followUpdate('one',4);
  tracker.onScroll(0,5000,700);
  assert.equal(tracker.followUpdate('one',5),true);
  tracker.onScroll(0,5000,700);
  assert.equal(tracker.followUpdate('two',1),true);
});
