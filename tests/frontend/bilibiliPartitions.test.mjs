import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {runInNewContext} from 'node:vm';
import test from 'node:test';
const require=createRequire(new URL('../../web/frontend/package.json',import.meta.url));
const ts=require('typescript'),React=require('react');
const {renderToStaticMarkup}=require('react-dom/server');
function load(path,mocks={}){
 const exports={};runInNewContext(ts.transpileModule(readFileSync(new URL('../../web/frontend/src/'+path,import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText,{exports,require:n=>n in mocks?mocks[n]:require(n)});return exports;
}
const lib=load('lib/bilibiliPartitions.ts',{'./publicationApi':{}});
const Picker=load('components/BilibiliPartition.tsx',{'../lib/bilibiliPartitions':lib}).default;
const catalog={groups:[{id:36,name:'知识',children:[{id:228,name:'人文历史',children:[]}]}],message:'来自B站当前投稿分区'};
test('human category path distinguishes parent, leaf and unknown without rewriting ID',()=>{
 assert.equal(lib.partitionLabel(catalog,228),'知识 / 人文历史');
 assert.equal(lib.partitionLabel(catalog,36),'知识（未细分）');
 assert.equal(lib.partitionLabel(catalog,9999),'原分区（编号 9999）');
});
test('grouped native picker preserves existing parent and unknown; readonly cannot refresh or edit',()=>{
 for(const value of [36,9999,228]){
  const tree=Picker({value,onChange:()=>{},catalog,refresh:()=>{}});
  const html=renderToStaticMarkup(tree);
  assert.match(html,/optgroup label="知识"/);assert.match(html,/人文历史/);
  assert.match(html,new RegExp(`value="${value}" selected=""`));
 }
 const html=renderToStaticMarkup(React.createElement(Picker,{value:228,catalog,disabled:true,onChange:()=>{},refresh:()=>{}}));
 assert.match(html,/disabled=""/);assert.doesNotMatch(html,/刷新分区|手动填写/);
});
