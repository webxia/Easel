import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { runInNewContext } from 'node:vm';
import test from 'node:test';
const require = createRequire(new URL('../../web/frontend/package.json', import.meta.url));
const ts = require('typescript'), React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const root = new URL('../../web/frontend/src/', import.meta.url);

function load(path, mocks = {}, extra = {}) {
  const exports = {};
  runInNewContext(ts.transpileModule(readFileSync(new URL(path, root), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText, { exports, require: name => name in mocks ? mocks[name] : require(name), AbortController, ...extra });
  return exports;
}
const helpers = load('lib/contentLibrary.ts');
const output = (id, rev, rest = {}) => ({ id, kind: 'output', media_type: 'video/mp4', output_revision: rev, run_id: 'r' + rev, delivery: { can_publish: id === 'a', message: '此版实际检查信息' }, ...rest });
const work = () => ({ id: 'w', title: '测试作品', state: 'reviewable', accepted_output_id: 'a', current_plan_revision: 2,
  artifacts: [output('a', 1, { export_artifact_id: 'bundle-a', checks: [{ kind: 'technical', status: 'pass' }] }), output('b', 2)],
  runs: [{ id: 'r1', plan_revision: 1 }, { id: 'r2', plan_revision: 2 }],
  plans: [1, 2].map(revision => ({ revision, confirmed_at: 'now', plan: { summary: '方案' + revision, script: '逐字稿' + revision } })),
});

// Exercise the real component's handlers/effects without introducing a new test dependency.
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
  const component = load(file, { ...mocks, react: hooks }, extra).default;
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
const icons = new Proxy({}, { get: () => () => null });

function detail(value = work(), records = [], failRecords = false) {
  const calls = [], actions = [];
  const h = harness('components/LibraryWorkDetail.tsx', {
    '../lib/contentLibrary': helpers,
    '../lib/productionApi': { artifactURL: id => '/artifact/' + id, workLabels: { reviewable: '可审阅' }, productionRequest: async (path, options) => { calls.push({ path, options }); if (path.startsWith('publications')) { if (failRecords) throw new Error('offline'); return records; } return value; } },
    '../lib/publicationApi': { publicationStatus: p => p.state, openPublishSource: (...args) => actions.push(['source', ...args]), openPublicationDraft: id => actions.push(['open', id]) },
    './icons': icons,
  }, { item: { work_id: 'w', artifact_id: 'a' }, onBack() {}, onContinue: e => actions.push(['continue', e]), onDelete: e => actions.push(['delete', e]), deleting: false });
  return { h, calls, actions };
}

test('accepted selection, deleted selection fallback and version plans use exact run identity', () => {
  const w = work(); assert.equal(helpers.selectedLibraryOutput(w).id, 'a');
  assert.equal(helpers.selectedLibraryOutput(w, 'b').id, 'b');
  assert.equal(helpers.selectedLibraryOutput(w, 'gone').id, 'a');
  assert.equal(helpers.libraryVersionPlan(w, w.artifacts[0]).revision, 1);
  assert.equal(helpers.libraryVersionPlan(w, { ...w.artifacts[0], run_id: 'missing' }), undefined);
  assert.equal(helpers.selectedLibraryOutput({ ...w, artifacts: [] }), undefined);
});

test('related files omit internal projects, raw receipts and json even if displayable', () => {
  const w = work(); w.artifacts.push(...[
    ['voice', 'audio', 'audio/wav'], ['bundle', 'export_bundle', 'application/zip'], ['project', 'edit_project', 'application/json'], ['receipt', 'receipt', 'text/plain'], ['raw', 'debug', 'application/json'],
  ].map(([id, kind, media_type]) => ({ id, kind, media_type })));
  assert.deepEqual(Array.from(helpers.libraryRelatedFiles(w), a => a.id), ['voice', 'bundle']);
});

test('detail browsing and refresh perform only scoped reads, disposal aborts them', async () => {
  const { h, calls, actions } = detail(); await h.flush();
  assert.equal(calls.length, 2); assert.ok(calls.every(c => !c.options.method));
  assert.ok(h.html().includes('已接受成片')); assert.match(h.html(), /技术检查：通过/);
  assert.match(h.html(), /当前作品信息/); assert.equal(h.nodes(n => n.type === 'video').length, 1);
  h.click('刷新详情'); h.render(); await h.flush(); assert.equal(calls.length, 4);
  assert.ok(calls[0].options.signal.aborted); assert.equal(actions.length, 0);
  h.dispose(); assert.ok(calls.every(c => c.options.signal.aborted));
});

test('switching to B keeps B preview, download and continue identity without preparing', async () => {
  const { h, actions } = detail(); await h.flush();
  h.click('版本 2'); h.render();
  assert.equal(h.nodes(n => n.type === 'video')[0].props.src, '/artifact/b');
  assert.ok(h.nodes(n => n.type === 'a').some(n => n.props.download && n.props.href === '/artifact/b'));
  assert.doesNotMatch(h.html(), /准备发布<\/button>/);
  h.click('围绕此版本继续创作');
  assert.deepEqual(JSON.parse(JSON.stringify(actions)), [['continue', { work_id: 'w', output_id: 'b', kind: 'continue' }]]);
});

test('existing record opens original identity without preparing; no record navigates to platform selection only on click', async () => {
  const r = detail(work(), [{ id: 'pub', output_id: 'a', state: 'unknown' }]); await r.h.flush();
  assert.equal(r.actions.length, 0); r.h.click('查看发布草稿或记录'); assert.deepEqual(r.actions, [['open', 'pub']]);
  assert.doesNotMatch(r.h.html(), /准备发布<\/button>/);
  const fresh = detail(); await fresh.h.flush(); assert.equal(fresh.actions.length, 0);
  await fresh.h.click('准备发布'); assert.deepEqual(fresh.actions, [['source', 'w', 'a']]);
});

test('unreadable publication history never offers to prepare; no-output work can still continue', async () => {
  const failed = detail(work(), [], true); await failed.h.flush();
  assert.match(failed.h.html(), /发布记录读取失败/); assert.doesNotMatch(failed.h.html(), /准备发布<\/button>/);
  const empty = detail({ ...work(), artifacts: [], runs: [] }); await empty.h.flush();
  assert.match(empty.h.html(), /尚未生成视频/); empty.h.click('继续创作');
  assert.deepEqual(JSON.parse(JSON.stringify(empty.actions)), [['continue', { work_id: 'w', kind: 'continue' }]]);
});

function library({ roots = [], accepted = [], pending = [], fail = '', confirm = () => false, jumpPath } = {}) {
  const calls = [], actions = [];
  const h = harness('components/OutputsPage.tsx', {
    './LibraryWorkDetail': { default: () => null, __esModule: true }, './content-library.css': {},
    '../lib/productionApi': { artifactURL: id => '/artifact/' + id, workLabels: {}, productionRequest: async path => { calls.push(path); if (path.includes('deletion-preview')) return { expected_revision: 3, preview_hash: 'hash', outputs: [], will_cancel_run: false }; if (fail && path.includes(fail)) throw new Error('source offline'); return path.includes('unaccepted') ? pending : accepted; }, productionCommand: async (...args) => { actions.push(['deleteWork', ...args]); } },
    '../lib/api': { fetchOutputs: async () => { if (fail === 'files') throw new Error('offline'); return roots; }, fetchOutputContent: async path => ({ content: 'content:' + path }), mediaUrl: path => '/media/' + path, deleteOutput: async path => actions.push(['deleteFile', path]) },
    '../lib/sanitize': { renderMarkdown: s => s }, './icons': icons,
  }, { jumpPath, onContinue: e => actions.push(['continue', e]), onJumpHandled: () => actions.push(['jumpHandled']) }, { window: { confirm, alert() {} } });
  return { h, calls, actions };
}
const file = (name, kind = 'text') => ({ type: 'file', name, path: 'project/' + name, kind });
const project = { type: 'dir', name: 'project', path: 'project', children: [file('doc.md'), file('page.html'), file('image.png', 'image'), file('sound.wav', 'audio'), file('video.mp4', 'video'), { type: 'dir', name: 'nested', path: 'project/nested', children: [] }], meta: { title: '原生项目', deliverablePaths: ['project/doc.md'] } };

test('home uses one card per Work, no video controls, original files survive production failure', async () => {
  const r = library({ roots: [project], accepted: [{ work_id: 'w', title: '成片A', artifact_id: 'a', output_revision: 1, has_newer_preview: true }], pending: [{ work_id: 'draft', title: '尚未生成', artifact_id: null }] });
  await r.h.flush();
  assert.match(r.h.html(), /已接受作品|未接受创作|其他内容项目|有未接受版本/);
  assert.equal(r.h.nodes(n => n.type === 'video' && n.props.controls).length, 0);
  assert.equal(r.calls.length, 2); assert.equal(r.actions.length, 0);
  const broken = library({ roots: [project], fail: 'library' }); await broken.h.flush();
  assert.match(broken.h.html(), /原生项目/); assert.match(broken.h.html(), /source offline/);
});

test('original file jump, manifest split, HTML sandbox and media previews retain original routes', async () => {
  for (const [name, tag] of [['page.html', 'iframe'], ['image.png', 'img'], ['sound.wav', 'audio'], ['video.mp4', 'video'], ['doc.md', 'div']]) {
    const r = library({ roots: [project], jumpPath: 'project/' + name }); await r.h.flush(); await r.h.flush();
    assert.ok(r.actions.some(a => a[0] === 'jumpHandled'));
    assert.match(r.h.html(), /成品 · 1/);
    if (tag === 'iframe') { const iframe = r.h.nodes(n => n.type === 'iframe')[0]; assert.equal(iframe.props.sandbox, 'allow-scripts'); assert.equal(iframe.props.allow, 'clipboard-write'); }
    else if (tag !== 'div') assert.ok(r.h.nodes(n => n.type === tag).some(n => n.props.src === '/media/project/' + name));
    else assert.match(r.h.html(), /content:project\/doc.md/);
    assert.ok(!r.actions.some(a => a[0].startsWith('delete')));
  }
});

test('ordinary files keep their delete route; cancelling Work deletion writes nothing', async () => {
  const r = library({ roots: [project], confirm: () => true }); await r.h.flush();
  const del = r.h.nodes(n => n.type === 'button' && n.props.title === '删除')[0];
  await del.props.onClick({ stopPropagation() {} }); assert.deepEqual(r.actions, [['deleteFile', 'project']]);
  const w = library({ pending: [{ work_id: 'w', title: '预览', artifact_id: null }] }); await w.h.flush();
  await w.h.nodes(n => n.type === 'button' && n.props.title === '删除作品')[0].props.onClick({ stopPropagation() {} });
  await new Promise(resolve => setImmediate(resolve)); assert.equal(w.actions.length, 0);
  assert.ok(w.calls.includes('works/w/deletion-preview'));
});

test('confirmed Work deletion uses preview revision, never ordinary file deletion', async () => {
  const r = library({ pending: [{ work_id: 'w', title: '预览', artifact_id: null }], confirm: () => true });
  await r.h.flush();
  r.h.nodes(n => n.type === 'button' && n.props.title === '删除作品')[0].props.onClick({ stopPropagation() {} });
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(JSON.parse(JSON.stringify(r.actions)), [['deleteWork', 'works/w/delete', { preview_hash: 'hash' }, 3]]);
});

test('unmanifested folder, nested navigation, file filter and back retain original behavior', async () => {
  const r = library({ roots: [{ ...project, meta: undefined }] }); await r.h.flush();
  r.h.nodes(n => n.type === 'div' && n.props.className === 'card card-hover gcard')[0].props.onClick(); r.h.render();
  r.h.click('图片'); r.h.render();
  assert.match(r.h.html(), /image.png/); assert.doesNotMatch(r.h.html(), /doc.md/);
  r.h.nodes(n => n.type === 'div' && n.props.className === 'card card-hover gcard')[0].props.onClick(); r.h.render();
  assert.match(r.h.html(), /这个文件夹是空的/);
  r.h.click('返回上级'); r.h.render(); assert.match(r.h.html(), /doc.md/);
  assert.equal(r.actions.length, 0);
});

test('library styles are scoped and existing media picker keeps its original output source', () => {
  const css = readFileSync(new URL('components/content-library.css', root), 'utf8');
  assert.ok(css.split('\n').filter(s => s.trim()).every(s => s.startsWith('.content-library ')));
  const picker = readFileSync(new URL('components/PublicationCover.tsx', root), 'utf8');
  assert.match(picker, /fetchOutputs/);
});
