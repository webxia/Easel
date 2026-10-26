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
 {exports,require:()=>({productionRequest:async(...args)=>{calls.push(args);return {id:'draft1'};}}),window:{history:{replaceState:()=>{}},dispatchEvent:e=>events.push(e)},CustomEvent:class {constructor(type,options){this.type=type;this.detail=options.detail;}}});
test('generic publication entry opens exact accepted source without selecting a platform or preparing',async()=>{
 calls=[];events=[];await exports.openPublication('work','output2');
 assert.equal(calls.length,0);assert.equal(events[0].type,'easel:publish-source');
 assert.deepEqual(JSON.parse(JSON.stringify(events[0].detail)),{work_id:'work',output_id:'output2'});
});
test('pending moderation and unknown are not public success',()=>{
 assert.match(exports.publicationStatus({state:'draft',attempts:[]}),/尚未投稿/);
 assert.match(exports.publicationStatus({attempts:[{state:'sending',receipt:{}}]}),/正在执行投稿/);
 assert.match(exports.publicationStatus({attempts:[{state:'unknown',receipt:{}}]}),/不会重复/);
 assert.equal(exports.publicationStatus({attempts:[{state:'verified',receipt:{matched:{status:'pending'}}}]}),'平台已核实：pending');
});

test('conversation draft navigation restores exact identity without preparing or submitting',()=>{
 calls=[];events=[];exports.openPublicationDraft('pub_123');
 assert.equal(calls.length,0);assert.equal(events[0].detail,'pub_123');
 assert.equal(exports.publicationIdFromHash('#publication=pub_123'),'pub_123');
 assert.equal(exports.publicationIdFromHash('#publication=../other'),undefined);
 assert.equal(exports.publicationIdFromHash('#publication=pub_123&submit=true'),undefined);
});

test('upload and remote confirmation are distinct and legacy missing receipts remain explicit',()=>{
 assert.match(exports.publicationGuidance({attempts:[{state:'sending',receipt:{}}]}),/尚未确认文件上传和投稿成功/);
 assert.match(exports.publicationGuidance({attempts:[{state:'unknown',receipt:{}}]}),/缺少上传工具退出回执/);
 assert.match(exports.publicationGuidance({attempts:[{state:'unknown',receipt:{execution:{returncode:0}}}]}),/平台结果尚未确认/);
});

test('explicit publication deep link wins over restored video chat on refresh',()=>{
 assert.equal(exports.sessionRestorePage('#publication=pub_123',true),'publish');
 assert.equal(exports.sessionRestorePage('',true),'chat');
 assert.equal(exports.sessionRestorePage('',false),undefined);
 assert.equal(exports.sessionRestorePage('#publication=../invalid',true),'chat');
});

test('leaving publication clears its route without creating a draft or changing chat identity',()=>{
 const app=readFileSync(new URL('../../web/frontend/src/App.tsx',import.meta.url),'utf8');
 const parsed=ts.createSourceFile('App.tsx',app,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);let declaration;
 function find(node){if(ts.isVariableDeclaration(node)&&node.name.getText(parsed)==='navigate')declaration=node;ts.forEachChild(node,find);}
 find(parsed);assert.ok(declaration);
 const code=ts.transpileModule(`const ${declaration.getText(parsed)}; navigate;`,{compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText;
 let page,route;
 const navigate=runInNewContext(code,{publicationIdFromHash:exports.publicationIdFromHash,setCurrentPage:value=>page=value,window:{location:{hash:'#publication=pub_123',pathname:'/',search:''},history:{replaceState:(_a,_b,value)=>route=value}}});
 navigate('chat');assert.equal(page,'chat');assert.equal(route,'/');
});

 test('execution stage explains upload failure without claiming a post',()=>{
  const text=exports.publicationExecutionText({returncode:1,timed_out:false,last_stage:'pre_upload',error_kinds:['tls_error','certificate_expired']});
  assert.match(text,/文件上传准备/);assert.match(text,/证书已过期/);assert.doesNotMatch(text,/投稿成功/);
  assert.equal(exports.publicationExecutionText({returncode:1,timed_out:false,error_kinds:['secret raw data']}),'');
 });

test('platform accepted receipt is distinct from unknown upload and public success',()=>{
 const value={attempts:[{state:'unknown',receipt:{execution:{returncode:0,remote_id:'BV1abcDEF234'}}}]};
 assert.equal(exports.publicationStatus(value),'已提交B站 · 平台状态待核实');
 assert.match(exports.publicationGuidance(value),/B站已返回稿件编号/);
});
