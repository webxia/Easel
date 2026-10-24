import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {runInNewContext} from 'node:vm';
import test from 'node:test';
const require=createRequire(new URL('../../web/frontend/package.json',import.meta.url));
const ts=require('typescript'),React=require('react');
const {renderToStaticMarkup}=require('react-dom/server');
const content={title:'测试片',body:'正文',tags:['思考'],tid:36,copyright:1,credits:'CC BY credit',source:'',action:'submit',account:{name:'测试账号',uid:'123'}};
const draft={id:'d',output_id:'o',output_revision:2,revision:1,state:'submitted',content,attempts:[{id:'a',state:'unknown',receipt:{reason:'平台尚未匹配'}}]};
function render(value=draft,confirming=false){
 const states=[[value],value,value.content,'',false,typeof confirming==='string'?confirming:confirming?'submit':null];let index=0;
 const source=readFileSync(new URL('../../web/frontend/src/components/AcceptedPublication.tsx',import.meta.url),'utf8');
 const exports={};
 runInNewContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText,
 {exports,require:name=>name==='react'?{...React,useState:()=>[states[index++],()=>{}],useEffect:()=>{}}:
 name==='../lib/productionApi'?{artifactURL:id=>'/media/'+id}:
 name==='./BilibiliPartition'?{__esModule:true,default:()=>null}:
 name==='../lib/bilibiliPartitions'?{useBilibiliPartitions:()=>({catalog:{groups:[]},refresh:()=>{}}),partitionLabel:()=> '知识'}:
 name==='./PublicationCover'?{__esModule:true,default:()=>null}:
 name==='../lib/publicationApi'?{publicationCoverURL:(id,digest)=>'/cover/'+digest,publicationExecutionText:()=>'',publicationStatus:()=>value.attempts.length?'投稿结果待核实':'草稿',publicationGuidance:()=>value.attempts.length?'上传和投稿均未确认':'请核对后投稿'}:
 name==='./icons'?{IconPublish:()=>null,IconRefresh:()=>null}:require(name)});
 return renderToStaticMarkup(React.createElement(exports.default,{selectedId:'d'}));
}
test('unknown shows a readable original record and only reconciliation, never another submit',()=>{
 const html=render();
 assert.match(html,/publish-editor/);assert.match(html,/publish-previews/);
 assert.match(html,/上传和投稿均未确认/);assert.match(html,/没有保存上传工具退出回执/);
 assert.match(html,/仅核实原投稿结果/);assert.match(html,/B站稿件管理/);
 assert.doesNotMatch(html,/查看最终确认并投稿|读取实际登录账号|取消草稿/);
 assert.match(html,/readonly=""/i);assert.match(html,/CC BY credit/);
});
test('final confirmation uses the existing Easel modal with exact version and target',()=>{
 const html=render({...draft,state:'draft',attempts:[]},true);
 assert.match(html,/role="dialog"/);assert.match(html,/aria-modal="true"/);
 assert.match(html,/确认向B站投稿/);assert.match(html,/测试账号/);assert.match(html,/成片版本 2/);
 assert.match(html,/返回修改/);assert.match(html,/确认投稿/);
 assert.match(html,/素材署名/);
});

test('verified absence recovery is explicit and does not itself submit media',()=>{
 const html=render(draft,'resolve');
 assert.match(html,/确认本片未投稿/);assert.match(html,/全部稿件、进行中、未通过和草稿/);
 assert.match(html,/不会立即上传/);assert.match(html,/确认未投稿，恢复原草稿/);
 assert.doesNotMatch(html,/>确认投稿</);
});

test('platform receipt ID removes absent-recovery action while keeping reconciliation',()=>{
 const value={...draft,attempts:[{id:'a',state:'unknown',receipt:{execution:{returncode:0,timed_out:false,remote_id:'BV1abcDEF234'}}}]};
 const html=render(value);assert.match(html,/仅核实原投稿结果/);assert.doesNotMatch(html,/已核实未投稿，重新准备/);
});

 test('final confirmation previews exact saved cover',()=>{
 const html=render({...draft,state:'draft',attempts:[],content:{...content,cover:{digest:'saved-image',width:1200,height:700}}},true);
 assert.match(html,/本次投稿确认封面/);assert.match(html,/src="\/cover\/saved-image"/);
 });
