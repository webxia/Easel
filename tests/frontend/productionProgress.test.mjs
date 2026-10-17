import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { runInNewContext } from 'node:vm';
import { test } from 'node:test';
const require = createRequire(new URL('../../web/frontend/package.json', import.meta.url));
const ts = require('typescript');
const source=readFileSync(new URL('../../web/frontend/src/lib/productionApi.ts',import.meta.url),'utf8');
const {outputText}=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}});
const exports={};const requests=[];
runInNewContext(outputText,{exports,window:{location:{pathname:'/studio/'}},crypto:{randomUUID:()=> 'stable-id'},fetch:async(url,options)=>{requests.push({url,options});return {ok:true,json:async()=>({work_id:'w'})};}});
const {newerSnapshot,productionCommand,productionURL,artifactURL}=exports;
test('late snapshots cannot replace selected work or roll back its progress',()=>{
 const current={id:'a',cursor:5};
 assert.equal(newerSnapshot(current,{id:'b',cursor:9},'a'),current);
 assert.equal(newerSnapshot(current,{id:'a',cursor:4},'a'),current);
 const latest={id:'a',cursor:6};assert.equal(newerSnapshot(current,latest,'a'),latest);
});
test('command retries keep command identity and expected revision in the envelope',async()=>{
 await productionCommand('works/w/cancel',{},7,'POST','retry-key');
 await productionCommand('works/w/cancel',{},7,'POST','retry-key');
 assert.equal(requests.at(-1).options.body,requests.at(-2).options.body);
 assert.equal(JSON.parse(requests.at(-1).options.body).expected_revision,7);
 assert.equal(JSON.parse(requests.at(-1).options.body).command_id,'retry-key');
});
test('artifact access uses registered identity and deployment base path',()=>{
 assert.equal(productionURL('works'),'/studio/api/production/works');
 assert.equal(artifactURL('a/b'),'/studio/api/production/artifacts/a%2Fb/content');
});
