import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { runInNewContext } from 'node:vm';
import { test } from 'node:test';
const require=createRequire(new URL('../../web/frontend/package.json',import.meta.url));
const ts=require('typescript');const exports={};
const source=readFileSync(new URL('../../web/frontend/src/lib/taskReplies.ts',import.meta.url),'utf8');
runInNewContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,{exports});
const {mergeTaskReplies}=exports;
test('real assistant tokens replace the same durable turn without replacing user history',()=>{
 const messages=[{role:'user',content:'我的问题'}];
 let result=mergeTaskReplies(messages,[{role:'assistant',content:'方案',serverTurnId:'r',resultState:'active'}]);
 assert.equal(result.length,2);assert.equal(result[0],messages[0]);
 result=mergeTaskReplies(result,[{role:'assistant',content:'完整方案，是否确认？',serverTurnId:'r',resultState:'ended'}]);
 assert.equal(result.length,2);assert.match(result[1].content,/是否确认/);
 assert.equal(mergeTaskReplies(result,[result[1]]),result);
});
test('refresh and partial replies from two runs preserve one copy each; no fabricated user event',()=>{
 const replies=[{role:'assistant',content:'失败解释',serverTurnId:'r1',resultState:'ended'},{role:'assistant',content:'视频交付',serverTurnId:'r2',resultState:'ended'}];
 const first=mergeTaskReplies([],replies);
 assert.equal(mergeTaskReplies(first,replies),first);
 assert.equal(first.length,2);
 assert.equal(mergeTaskReplies(first,[{role:'user',content:'系统伪造用户确认',serverTurnId:'evil'}]),first);
});
test('an interruption arriving after partial text updates only its original reply',()=>{
 const partial={role:'assistant',content:'制作',serverTurnId:'r1',resultState:'ended'};
 const messages=[partial,{role:'user',content:'继续'},
   {role:'assistant',content:'视频已返回',serverTurnId:'r2',resultState:'ended'}];
 const error={...partial,deliveryError:'length'};
 const updated=mergeTaskReplies(messages,[error,messages[2]]);
 assert.equal(updated.length,3);assert.equal(updated[0].deliveryError,'length');
 assert.equal(updated[1],messages[1]);assert.equal(updated[2],messages[2]);
 assert.equal(mergeTaskReplies(updated,[error,messages[2]]),updated);
 const cleared=mergeTaskReplies(updated,[partial]);
 assert.equal(cleared[0].deliveryError,undefined);
});
test('late failure returns to its original chronological position and stays there',()=>{
 const messages=[{role:'user',content:'确认制作'}, {role:'assistant',content:'正在制作'},
   {role:'user',content:'继续制作',userTurnId:'u2'}, {role:'assistant',content:'收到'}];
 const failure={role:'assistant',content:'渲染失败',serverTurnId:'failure',resultState:'ended',beforeUserTurnId:'u2'};
 const result=mergeTaskReplies(messages,[failure]);
 assert.equal(result[2],failure);assert.equal(result[3],messages[2]);
 assert.equal(mergeTaskReplies(result,[failure]),result);
 const extra=[...result,{role:'user',content:'现在呢'}];
 assert.equal(mergeTaskReplies(extra,[failure]),extra);
});
test('existing local history uses the matching user occurrence, without duplicate failures',()=>{
 const failure={role:'assistant',content:'暂停',serverTurnId:'failure',resultState:'ended'};
 const messages=[{role:'user',content:'继续'}, {role:'assistant',content:'第一轮'},
   {role:'user',content:'继续'}, failure];
 const anchored={...failure,beforeUserMessage:'继续',beforeUserOccurrence:2};
 const result=mergeTaskReplies(messages,[anchored]);
 assert.equal(result[2],anchored);assert.equal(result[3],messages[2]);
 assert.equal(result.filter(m=>m.serverTurnId==='failure').length,1);
 assert.equal(mergeTaskReplies(result,[anchored]),result);
});
test('multiple results before the same user remain stable across polling',()=>{
 const user={role:'user',content:'继续',userTurnId:'u'};
 const a={role:'assistant',content:'A',serverTurnId:'a',beforeUserTurnId:'u'};
 const b={role:'assistant',content:'B',serverTurnId:'b',beforeUserTurnId:'u'};
 const result=mergeTaskReplies([user],[a,b]);
 assert.equal(result[0],a);assert.equal(result[1],b);assert.equal(result[2],user);
 assert.equal(mergeTaskReplies(result,[a,b]),result);
});

test('accepted-version action restores from polling without moving or duplicating messages',()=>{
 const first={role:'assistant',content:'已接受',serverTurnId:'accept',publicationSource:{work_id:'w',output_id:'o'}};
 const messages=mergeTaskReplies([],[first]);
 assert.equal(mergeTaskReplies(messages,[JSON.parse(JSON.stringify(first))]),messages);
 const changed={...first,publicationSource:{work_id:'w',output_id:'o2'}};
 assert.equal(mergeTaskReplies(messages,[changed])[0].publicationSource.output_id,'o2');
});
