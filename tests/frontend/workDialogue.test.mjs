import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { runInNewContext } from 'node:vm';
import { test } from 'node:test';
const require=createRequire(new URL('../../web/frontend/package.json',import.meta.url));
const ts=require('typescript');
const source=readFileSync(new URL('../../web/frontend/src/lib/workDialogue.ts',import.meta.url),'utf8');
const exports={};
runInNewContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,{exports});
const {workDialogue}=exports;
const base=()=>({active_run_id:'r',runs:[{id:'r',state:'running'}],tasks:[{id:'t',run_id:'r',kind:'plan',state:'running'}],pending_operations:[],plans:[],artifacts:[]});
test('background planning informs user without a new chat request',()=>{
 assert.match(workDialogue(base()).status,/整理完整方案/);
});
test('blocked task replaces waiting, malformed error is still visible, old run ignored',()=>{
 const w=base();w.tasks[0].state='needs_decision';w.tasks[0].error_json='broken';
 assert.match(workDialogue(w).status,/暂时停/);
 w.tasks[0].error_json=JSON.stringify({user_message:'授权缺失'});
 assert.match(workDialogue(w).status,/授权缺失/);
 w.tasks[0].run_id='old';assert.doesNotMatch(workDialogue(w).status,/授权缺失/);
});
test('UNKNOWN prevents optimistic continue message',()=>{
 const w=base();w.pending_operations=[{state:'unknown'}];
 assert.match(workDialogue(w).status,/不能重新派发/);
});
test('plan snapshot recovery is deterministic and uses current revision',()=>{
 const w=base();w.current_plan_revision=2;w.plans=[{revision:1},{revision:2,plan:{script:'完整脚本'}}];
 assert.equal(workDialogue(w).plan.revision,2);
 assert.equal(JSON.stringify(workDialogue(w)),JSON.stringify(workDialogue(structuredClone(w))));
});
test('render is hidden during quality, delivered once after completion, old outputs retained',()=>{
 const w=base();w.tasks[0].kind='quality';w.artifacts=[{id:'new',kind:'output',run_id:'r',output_revision:2},{id:'old',kind:'output',run_id:'old',output_revision:1}];
 assert.equal(workDialogue(w).outputs.length,1);
 w.runs[0].state='succeeded';w.tasks[0].state='succeeded';
 assert.equal(workDialogue(w).outputs.length,2);
 assert.equal(workDialogue(w).status,'');
 assert.equal(workDialogue(w,true).outputs.length,0);
});
