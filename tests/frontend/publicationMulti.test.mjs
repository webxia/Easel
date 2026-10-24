import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {runInNewContext} from 'node:vm';
import test from 'node:test';
const require=createRequire(new URL('../../web/frontend/package.json',import.meta.url));
const ts=require('typescript'),React=require('react');
const {renderToStaticMarkup}=require('react-dom/server');
const root=new URL('../../web/frontend/src/',import.meta.url);
function load(path, mocks = {}, extra = {}) {
  const exports = {};
  runInNewContext(ts.transpileModule(readFileSync(new URL(path, root), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText, { exports, require: name => name in mocks ? mocks[name] : require(name), AbortController, ...extra });
  return exports;
}
function harness(file, mocks, props, extra = {}) {
  let states = [], index = 0, deps = [], effects = [], cleanups = [];
  const hooks = { ...React,
    useState(initial) { const i = index++; if (!(i in states)) states[i] = typeof initial === 'function' ? initial() : initial; return [states[i], value => { states[i] = typeof value === 'function' ? value(states[i]) : value; }]; },
    useEffect(fn, values) { const i = index++; if (!deps[i] || values.some((v, n) => !Object.is(v, deps[i][n]))) { deps[i] = values; effects.push(() => { cleanups[i]?.(); cleanups[i] = fn(); }); } },
    useMemo(fn) { return fn(); }, useCallback(fn) { return fn; },
    useRef(value) { const [ref] = this.useState({ current: value }); return ref; },
  };
  // useRef is imported unbound by transpiled code.
  hooks.useRef = value => { const [ref] = hooks.useState({ current: value }); return ref; };
  const component = load(file, { ...mocks, react: hooks }, extra)[extra.componentExport||'default'];
  let tree;
  const render = () => { index = 0; tree = component(props); return tree; };
  const flush = async () => { for (const effect of effects.splice(0)) effect(); await new Promise(resolve => setImmediate(resolve)); render(); };
  const walk = (predicate, node) => {
    if (Array.isArray(node)) return node.flatMap(n => walk(predicate, n));
    if (!node || typeof node !== 'object') return [];
    return [...(predicate(node) ? [node] : []), ...(node.props?.children !== undefined ? walk(predicate, node.props.children) : [])];
  };
  const nodes = predicate => walk(predicate, tree);
  const html = () => renderToStaticMarkup(tree);
  const click = label => { const button = nodes(n => n.type === 'button' && renderToStaticMarkup(n).includes(label))[0]; assert.ok(button, label); return button.props.onClick(); };
  render();
  return { render, flush, nodes, html, click, dispose: () => cleanups.forEach(fn => fn?.()) };
}

const icons=new Proxy({}, {get:()=>()=>null});
function page(source,rows=[]){
 const actions=[],storage=new Map([['file','preserved']]);
 const record={id:'draft',platform:'douyin',output_id:'out',state:'draft',revision:1,confirmation_hash:'hash',content:{title:'片名',body:'正文',credits:'署名',tags:[],account:null,cover:null},attempts:[]};
 const h=harness('components/PublishPage.tsx',{
  './BilibiliPartition':()=>null,'../lib/bilibiliPartitions':{useBilibiliPartitions:()=>({catalog:{groups:[]},refresh:()=>{}}),partitionLabel:(_,id)=>`分区${id}`},'./AcceptedPublication':()=>null,'./PublicationCover':()=>null,'./icons':icons,
  '../lib/api':{fetchAccounts:async()=>[],fetchOutputs:async()=>[{type:'directory',children:Array.from({length:45},(_,i)=>({type:'file',kind:'image',name:'image'+i,path:'p/'+i+'.png'}))}],mediaUrl:p=>'/media/'+p,publishNow:async()=>actions.push(['submit'])},
  '../lib/store':{loadPublishDraft:()=>({title:'文件标题',body:'文件正文',tags:'tag',overrides:{},platforms:['douyin']}),savePublishDraft:d=>storage.set('file',d)},
  '../lib/productionApi':{artifactURL:id=>'/artifact/'+id,productionRequest:async()=>[{work_id:'work',artifact_id:'out',title:'成片',output_revision:2}]},
  '../lib/publicationApi':{openPublishSource:(...args)=>actions.push(['source',...args]),fileCoverURL:id=>'/cover/'+id,publicationStatus:()=> '未投稿',publicationCall:async(path,body,method)=>{actions.push([path,body,method]);return method==='GET'?(path.startsWith('?')?rows:rows.find(r=>path===`/${r.id}`)||[]):path.endsWith('/submit')?{...rows.find(r=>path===`/${r.id}/submit`),state:'submitted',attempts:[{state:'unknown',receipt:{}}]}:method==='PUT'?{...structuredClone(record),content:body.content,revision:2}:structuredClone(record);}},
  '../lib/sanitize':{renderMarkdown:s=>s},
 },{persona:'',source},{componentExport:'FilePublishPage',localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v)},window:{confirm:()=>true},setTimeout,clearTimeout,setInterval,clearInterval,structuredClone});
 return {h,actions,storage};
}
test('one original media picker includes accepted outputs and files beyond forty; browsing has no prepare',async()=>{
 const {h,actions}=page();await h.flush();h.click('选择媒体');h.render();
 assert.match(h.html(),/image44/);assert.match(h.html(),/成片.*版本 2/);
 h.click('成片 · 版本');assert.deepEqual(actions,[['source','work','out']]);
 h.dispose();
});
test('opening accepted media preserves file draft and only prepares after explicit platform edit',async()=>{
 const {h,actions,storage}=page({work_id:'work',output_id:'out'});await h.flush();
 assert.equal(storage.get('file'),'preserved');assert.ok(storage.has('easel_publish_work_work_out'));
 assert.equal(actions.filter(a=>a[0]==='/prepare').length,0);
 h.click('小红书');h.render();await h.click('准备此平台草稿');await h.flush();
 assert.equal(actions.filter(a=>a[0]==='/prepare').length,1);
 assert.equal(actions.at(-1)[1].platform,'douyin');
 assert.equal(actions.filter(a=>String(a[0]).includes('/submit')).length,0);h.dispose();
});
test('final confirm is separate from execution and preserves selected file list',async()=>{
 const {h,actions}=page();await h.flush();await h.click('一键发布');h.render();
 assert.match(h.html(),/确认本次发布/);assert.match(h.html(),/尚未选择/);
 assert.equal(actions.length,0);h.click('返回修改');h.render();assert.doesNotMatch(h.html(),/id="multi-publish-confirm"/);h.dispose();
});

test('changed platform draft must be saved before final confirmation; saving does not submit',async()=>{
 const {h,actions}=page({work_id:'work',output_id:'out'});await h.flush();h.click('小红书');h.render();
 await h.click('准备此平台草稿');await h.flush();
 assert.match(h.html(),/有平台稿件尚未保存/);
 assert.equal(h.nodes(n=>n.type==='button'&&renderToStaticMarkup(n).includes('一键发布'))[0].props.disabled,true);
 await h.click('保存此平台草稿');await h.flush();
 assert.doesNotMatch(h.html(),/有平台稿件尚未保存/);
 assert.equal(actions.filter(a=>String(a[0]).includes('/submit')).length,0);h.dispose();
});

test('one confirmation skips an already submitted platform and never retries an unknown platform',async()=>{
 const content={title:'t',body:'b',credits:'c',tags:['tag'],account:{platform:'douyin',uid:'123',name:'test'},cover:null};
 const rows=[{id:'dy',platform:'douyin',output_id:'out',revision:2,output_revision:1,state:'draft',confirmation_hash:'hash',content,attempts:[]},
 {id:'bili',platform:'bilibili',output_id:'out',revision:4,output_revision:1,state:'submitted',confirmation_hash:'old',content,attempts:[{state:'verified',receipt:{}}]}];
 const {h,actions}=page({work_id:'work',output_id:'out'},rows);await h.flush();h.click('小红书');h.render();h.click('B站');h.render();
 h.click('一键发布');h.render();assert.match(h.html(),/保留原记录，不重复投稿/);
 await h.click('确认发布');await h.flush();
 assert.deepEqual(actions.filter(a=>String(a[0]).endsWith('/submit')).map(a=>a[0]),['/dy/submit']);
 h.click('一键发布');h.render();assert.equal(h.nodes(n=>n.type==='button'&&renderToStaticMarkup(n).includes('确认发布'))[0].props.disabled,true);
 assert.equal(actions.filter(a=>String(a[0]).endsWith('/submit')).length,1);h.dispose();
});

test('file category choice persists and appears in final confirmation by name',async()=>{
 const {h,storage,actions}=page();await h.flush();h.click('B站');h.render();
 const picker=h.nodes(n=>typeof n.type==='function'&&n.props.value===36&&n.props.catalog)[0];
 assert.ok(picker);picker.props.onChange(228);h.render();await h.flush();
 assert.equal(storage.get('file').bilibiliTid,228);
 await h.click('一键发布');h.render();assert.match(h.html(),/分区：分区228/);
 assert.equal(actions.filter(a=>a[0]==='submit').length,0);h.dispose();
});
