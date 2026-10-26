import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {runInNewContext} from 'node:vm';
import {test} from 'node:test';
const require=createRequire(new URL('../../web/frontend/package.json',import.meta.url));
const ts=require('typescript'),React=require('react');
const {renderToStaticMarkup}=require('react-dom/server');
function component(file,mocks={}) {
 const source=readFileSync(new URL('../../web/frontend/src/components/'+file,import.meta.url),'utf8');
 const exports={};
 runInNewContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,
   target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText,
   {exports,require:name=>name in mocks?mocks[name]:require(name)});
 return exports.default;
}
const Bubble=component('MessageBubble.tsx',{
 '../lib/publicationApi':{openPublicationDraft:()=>{},publicationIdFromHash:()=>undefined},
 '../lib/sanitize':{renderMarkdown:s=>s},
 '../lib/linkifyOutputs':{linkifyOutputs:s=>s,externalizeMediaLinks:s=>s},
 './icons':{IconCopy:()=>null,IconCheck:()=>null,IconRetry:()=>null},
 '../lib/artifacts':{extractArtifacts:html=>({html,artifacts:[],archives:[]})},
 './ArtifactGallery':{default:()=>null},
});
test('a partial result keeps its interruption details inside its own bubble',()=>{
 const html=renderToStaticMarkup(React.createElement(Bubble,{message:{role:'assistant',
   content:'制作',serverTurnId:'old',resultState:'ended',deliveryError:'length <script>bad()</script>'}}));
 assert.match(html,/制作/);assert.match(html,/这条结果回复未完整返回/);
 assert.match(html,/<details><summary>中断详情/);
 assert.match(html,/length &lt;script&gt;bad\(\)&lt;\/script&gt;/);
 assert.doesNotMatch(html,/role="alert"|<script>/);
 const latest=renderToStaticMarkup(React.createElement(Bubble,{message:{role:'assistant',content:'新视频'}}));
 assert.doesNotMatch(latest,/中断详情|未完整返回/);
});
test('old result errors never become a current global alert; request failures still do',()=>{
 function render(error='') {
   let state=0;
   const Panel=component('VideoConversation.tsx',{
     react:{...React,useState:()=>[state++===0?{context:{},result_messages:[{deliveryError:'OLD_LENGTH'}]}:error,()=>{}],
       useRef:v=>({current:v}),useEffect:()=>{},useCallback:f=>f},
     '../lib/conversationApi':{},
   });
   return renderToStaticMarkup(React.createElement(Panel,{sessionId:'s',onBound:()=>{},onRestore:()=>{},onBindingPending:()=>{}}));
 }
 assert.doesNotMatch(render(),/OLD_LENGTH|role="alert"/);
 assert.match(render('当前请求失败'),/role="alert">当前请求失败/);
});

test('video lifecycle panel never substitutes workflow buttons for dialogue',()=>{
 let state=0;
 const Panel=component('VideoConversation.tsx',{
  react:{...React,useState:()=>[state++===0?{context:{},work_id:'w',turns:[],result_messages:[],
   output_followup:{title:'第4版 · 接下来',actions:[{label:'改稿重制',prompt:'start'}]}}:'',()=>{}],
   useRef:v=>({current:v}),useEffect:()=>{},useCallback:f=>f},
  '../lib/conversationApi':{},
 });
 const html=renderToStaticMarkup(React.createElement(Panel,{sessionId:'s',onBound:()=>{},onRestore:()=>{},onBindingPending:()=>{}}));
 assert.doesNotMatch(html,/<button|video-followup|改稿重制|接下来/);
});
