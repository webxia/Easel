import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {runInNewContext} from 'node:vm';
import test from 'node:test';
const require=createRequire(new URL('../../web/frontend/package.json',import.meta.url));
const ts=require('typescript');
const path=new URL('../../web/frontend/src/lib/publicationApi.ts',import.meta.url);
const exports={};let calls=[];let events=[];
runInNewContext(ts.transpileModule(readFileSync(path,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,
 {exports,require:()=>({productionRequest:async(...args)=>{calls.push(args);return {id:'draft1'};}}),window:{dispatchEvent:e=>events.push(e)},CustomEvent:class {constructor(type,options){this.type=type;this.detail=options.detail;}}});
test('prepare navigates to the exact persisted draft, never submits or accepts',async()=>{
 calls=[];events=[];await exports.openPublication('work','output2');
 assert.equal(calls.length,1);assert.equal(calls[0][0],'publications/prepare');
 assert.deepEqual(JSON.parse(calls[0][1].body),{work_id:'work',output_id:'output2'});
 assert.equal(events[0].detail,'draft1');
});
test('pending moderation and unknown are not public success',()=>{
 assert.match(exports.publicationStatus({state:'draft',attempts:[]}),/尚未投稿/);
 assert.match(exports.publicationStatus({attempts:[{state:'sending',receipt:{}}]}),/待核实/);
 assert.match(exports.publicationStatus({attempts:[{state:'unknown',receipt:{}}]}),/不会重复/);
 assert.equal(exports.publicationStatus({attempts:[{state:'verified',receipt:{matched:{status:'pending'}}}]}),'平台已核实：pending');
});
