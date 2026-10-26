import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { runInNewContext } from 'node:vm';
import { test } from 'node:test';

const require = createRequire(new URL('../../web/frontend/package.json', import.meta.url));
const ts = require('typescript');
const source = readFileSync(new URL('../../web/frontend/src/lib/store.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
});

function storage(initial = {}) {
  const entries = new Map(Object.entries(initial));
  return {
    getItem: key => entries.get(key) ?? null,
    setItem: (key, value) => entries.set(key, String(value)),
    removeItem: key => entries.delete(key),
  };
}

function load(initial) {
  const localStorage = storage(initial);
  const sessionStorage = storage({ easel_tab_session: 'original', 'easel_pending_turn:original': 'pending' });
  const exports = {};
  runInNewContext(outputText, { exports, localStorage, sessionStorage, Date, Math });
  return { exports, localStorage, sessionStorage };
}

test('loading without the obsolete reset marker preserves existing conversation history and recovery', () => {
  const original = [{ id: 'original', messages: [{ role: 'user', content: '历史对话' }], created: 1 }];
  const state = load({ easel_sessions: JSON.stringify(original), easel_active_session: 'original' });
  assert.equal(JSON.stringify(state.exports.loadSessions()), JSON.stringify(original));
  assert.equal(state.exports.loadActiveId(), 'original');
  assert.equal(state.sessionStorage.getItem('easel_tab_session'), 'original');
  assert.equal(state.sessionStorage.getItem('easel_pending_turn:original'), 'pending');
});

test('legacy conversation history migrates rather than being deleted on first load', () => {
  const original = [{ id: 'original', messages: [{ role: 'user', content: '迁移的历史' }], created: 1 }];
  const previous = ['post', 'craft'].join('');
  const state = load({
    [`${previous}_sessions`]: JSON.stringify(original),
    [`${previous}_active_session`]: 'original',
  });
  assert.equal(JSON.stringify(state.exports.loadSessions()), JSON.stringify(original));
  assert.equal(state.exports.loadActiveId(), 'original');
  assert.equal(state.localStorage.getItem('easel_sessions'), JSON.stringify(original));
  assert.equal(state.localStorage.getItem(`${previous}_sessions`), null);
});

function sharedTabs(initial) {
  const localStorage = storage({ easel_sessions: JSON.stringify(initial) });
  let queue = Promise.resolve();
  const navigator = { locks: { request(_name, apply) {
    const next = queue.then(apply); queue = next.catch(() => {}); return next;
  } } };
  const tab = () => {
    const exports = {};
    runInNewContext(outputText, { exports, localStorage, navigator, Date, Math });
    return exports;
  };
  return { first: tab(), second: tab(), localStorage };
}
const chat = (id, content = id) => ({ id, title: id, created: 1,
  messages: content ? [{role:'user',content}] : [] });

test('concurrent tabs preserve new conversations while another reply is saved', async () => {
  const { first, second } = sharedTabs([chat('a'),chat('b')]);
  const a = first.loadSessions(), b = second.loadSessions();
  const created = chat('new');
  b[1].messages.push({role:'assistant',content:'completed in another tab'});
  await Promise.all([
    first.saveSessions([created,...a],{create:['new']}),
    second.saveSessions(b,{update:{b:['messages']}}),
  ]);
  const saved = first.loadSessions();
  assert.equal(saved.find(s=>s.id==='new').messages[0].content,'new');
  assert.equal(saved.find(s=>s.id==='b').messages.at(-1).content,'completed in another tab');
  assert.equal(saved.find(s=>s.id==='a').messages[0].content,'a');
});

test('metadata edits do not roll back messages or bindings from a stale view', async () => {
  const { first, second } = sharedTabs([chat('a')]);
  const a=first.loadSessions(),b=second.loadSessions();
  a[0].messages.push({role:'assistant',content:'new reply'});a[0].videoSegmentId='bound';
  b[0].title='renamed';b[0].archived=true;
  await Promise.all([
    first.saveSessions(a,{update:{a:['messages','videoSegmentId']}}),
    second.saveSessions(b,{update:{a:['title','archived']}}),
  ]);
  const saved=first.loadSessions()[0];
  assert.equal(saved.messages.at(-1).content,'new reply');
  assert.equal(saved.videoSegmentId,'bound');assert.equal(saved.title,'renamed');assert.equal(saved.archived,true);
});

test('stale callbacks cannot resurrect deletion or remove an unrelated conversation', async () => {
  const { first, second } = sharedTabs([chat('a'),chat('b')]);
  const stale=second.loadSessions();stale[0].messages.push({role:'assistant',content:'late'});
  await first.saveSessions([chat('b')],{remove:['a']});
  await second.saveSessions(stale,{update:{a:['messages']}});
  assert.deepEqual(Array.from(first.loadSessions(),s=>s.id),['b']);
});

test('two active empty conversations survive and replayed creation does not erase messages', async () => {
  const { first, second } = sharedTabs([]);
  await Promise.all([first.saveSessions([chat('a','')],{create:['a']}),second.saveSessions([chat('b','')],{create:['b']})]);
  assert.equal(first.loadSessions().length,2);
  const a=first.loadSessions();a.find(s=>s.id==='a').messages.push({role:'user',content:'keep'});
  await first.saveSessions(a,{update:{a:['messages']}});
  await first.saveSessions([chat('a','')],{create:['a']});
  assert.equal(first.loadSessions().find(s=>s.id==='a').messages[0].content,'keep');
});
