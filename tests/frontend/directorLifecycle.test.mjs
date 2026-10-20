import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { runInNewContext } from 'node:vm';
import test from 'node:test';
const require=createRequire(new URL('../../web/frontend/package.json',import.meta.url));
const ts=require('typescript');const exports={};
const source=readFileSync(new URL('../../web/frontend/src/lib/directorLifecycle.ts',import.meta.url),'utf8');
runInNewContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,{exports});
const {selectableDirectorVersions,directorEntrySelection,trialOutputs}=exports;
test('only confirmed styles enter trials; only accepted styles enter ordinary production',()=>{
 const directors=[{id:'active',versions:[{id:'draft'},{id:'trial',style_confirmed:true},{id:'accepted',style_confirmed:true,accepted_at:'now'}]},
 {id:'archived',archived:true,versions:[{id:'old',accepted_at:'then'}]}];
 assert.equal(selectableDirectorVersions(directors,false).map(v=>v.version.id).join(','),'accepted');
 assert.equal(selectableDirectorVersions(directors,true).map(v=>v.version.id).join(','),'trial,accepted');
});
test('new discussion carries the exact selected version and trial flag without changing acceptance',()=>{
 const directors=[{id:'active',versions:[{id:'draft'},{id:'trial',style_confirmed:true,accepted_at:null},{id:'accepted',style_confirmed:true,accepted_at:'now'}]},
 {id:'archived',archived:true,versions:[{id:'old',style_confirmed:true}]}];
 const before=JSON.stringify(directors);
 assert.deepEqual(JSON.parse(JSON.stringify(directorEntrySelection(directors,'trial'))),{director_revision:'trial',director_trial:true});
 assert.deepEqual(JSON.parse(JSON.stringify(directorEntrySelection(directors,'accepted'))),{director_revision:'accepted',director_trial:false});
 assert.deepEqual(JSON.parse(JSON.stringify(directorEntrySelection(directors,''))),{});
 for(const id of ['draft','old','missing'])assert.throws(()=>directorEntrySelection(directors,id),/尚未确认风格或已不可用/);
 assert.equal(JSON.stringify(directors),before);
});
test('director acceptance offers only quality-passed output from that exact frozen style version',()=>{
 const work={plans:[{revision:1,plan:{director_revision_id:'d1'}},{revision:2,plan:{director_revision_id:'d2'}}],
 runs:[{id:'r1',plan_revision:1},{id:'r2',plan_revision:2}],artifacts:[
 {id:'valid',kind:'output',quality_state:'passed',run_id:'r1'},
 {id:'failed',kind:'output',quality_state:'needs_fix',run_id:'r1'},
 {id:'foreign-style',kind:'output',quality_state:'passed',run_id:'r2'}]};
 assert.equal(trialOutputs(work,'d1').map(a=>a.id).join(','),'valid');
 assert.equal(trialOutputs(null,'d1').length,0);
});
