import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {runInNewContext} from 'node:vm';
import test from 'node:test';
const require=createRequire(new URL('../../web/frontend/package.json',import.meta.url));
const ts=require('typescript'),React=require('react');
const source=readFileSync(new URL('../../web/frontend/src/components/PublicationCover.tsx',import.meta.url),'utf8');
const candidate={digest:'exact-image',width:1200,height:700};
function mount({state='draft',mode=null,preview=null}={}){
 let index=0;const states=[mode,[],preview,0],changes=[],calls=[];
 const exports={};
 runInNewContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText,{exports,require:name=>
 name==='react'?{...React,useState:()=>{const i=index++;return [states[i],v=>states[i]=v];},useRef:()=>({current:null})}:
 name==='../lib/api'?{fetchOutputs:async()=>[],mediaUrl:p=>'/media/'+p}:
 name==='../lib/productionApi'?{artifactURL:id=>'/artifact/'+id}:
 name==='../lib/publicationApi'?{publicationCoverURL:(id,hash)=>'/cover/'+hash,publicationCall:async(...args)=>{calls.push(args);return candidate;}}:require(name)});
 const tree=exports.default({draft:{id:'draft1',revision:3,output_id:'accepted2',state},disabled:false,onChange:v=>changes.push(v),run:async f=>f()});
 const nodes=[];function walk(n){if(!n)return;if(Array.isArray(n)){n.forEach(walk);return;}if(typeof n==='object'){nodes.push(n);walk(n.props?.children);}}walk(tree);
 return {nodes,changes,calls,states};
}
test('cover preview only selects bytes on explicit use and does not submit',()=>{
 const x=mount({preview:candidate});assert.equal(x.changes.length,0);
 assert.ok(x.nodes.some(n=>n.type==='img'&&n.props.src==='/cover/exact-image'));
 x.nodes.find(n=>n.type==='button'&&n.props.children==='使用这张封面').props.onClick();
 assert.equal(x.changes[0],candidate);assert.equal(x.calls.length,0);
});
test('frame picker requests a local candidate for exact accepted output, no upload',async()=>{
 const x=mount({mode:'frame'});
 assert.equal(x.nodes.find(n=>n.type==='video').props.src,'/artifact/accepted2');
 await x.nodes.find(n=>n.type==='button'&&n.props.children==='截取当前画面并预览').props.onClick();
 await new Promise(resolve=>setImmediate(resolve));
 assert.equal(x.calls[0][0],'/draft1/covers');assert.equal(x.calls[0][1].revision,3);
 assert.equal(x.changes.length,0);assert.equal(x.states[2],candidate);
});
test('submitted publication exposes no cover modification controls',()=>{
 const x=mount({state:'submitted'});assert.equal(x.nodes.filter(n=>n.type==='button'||n.type==='input').length,0);
});
