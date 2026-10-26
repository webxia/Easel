import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {runInNewContext} from 'node:vm';
import {test} from 'node:test';
const require=createRequire(new URL('../../web/frontend/package.json',import.meta.url));
const ts=require('typescript');
const React=require('react');
const {renderToStaticMarkup}=require('react-dom/server');
function render(view) {
  const exports={};
  const hooks={...React,useState:initial=>[initial===null?view:initial,()=>{}],
    useEffect:()=>{},useCallback:f=>f,useRef:current=>({current})};
  const source=readFileSync(new URL('../../web/frontend/src/components/VideoConversation.tsx',import.meta.url),'utf8');
  runInNewContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX}}).outputText,
    {exports,require:name=>name==='react'?hooks:name==='../lib/conversationApi'?{}:require(name)});
  return renderToStaticMarkup(React.createElement(exports.default,{sessionId:'test',onRestore:()=>{},onBound:()=>{},onBindingPending:()=>{}}));
}
test('production status is not appended below the conversation history',()=>{
  const html=render({context:{kind:'new_work'},result_messages:[],production_status:{state:'needs_decision',message:'制作已暂停。'}});
  assert.doesNotMatch(html,/role="status"|production-status|制作已暂停/);
});
