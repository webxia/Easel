import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import {pathToFileURL} from 'node:url';
import {spawnSync} from 'node:child_process';

// No live Gateway, model, credentials or real transcript. Runtime modules only.
const dist = process.argv[2];
const root = fs.mkdtempSync(path.join(os.tmpdir(), 'easel-transport-fixture-'));
process.env.OPENCLAW_STATE_DIR = root;
process.env.OPENCLAW_CONFIG_PATH = path.join(root, 'openclaw.json');
const config = {agents:{entries:{main:{}}},session:{maintenance:{mode:'warn'}}};
fs.writeFileSync(process.env.OPENCLAW_CONFIG_PATH, JSON.stringify(config));
const moduleAt = name => import(pathToFileURL(path.join(dist,name)).href);
const sdk = await moduleAt('plugin-sdk/session-store-runtime.js');
const {n: readRecent} = await moduleAt('session-transcript-readers-BZjuw2hz.mjs');
const {t: handlers} = await moduleAt('sessions-read-CmsoQhMB.mjs');
const {wt: buildSnapshot} = await moduleAt('openclaw-state-db-DoQEJuhr.mjs');
const transcript = await moduleAt('plugin-sdk/session-transcript-runtime.js');
const storePath = path.join(root,'agents','main','sessions','sessions.json');
const sessionKey = 'agent:main:easel-transport-fixture';
const sessionId = crypto.randomUUID();
const runId = 'easel-probe-'+crypto.randomUUID();
const scope = {agentId:'main',sessionId,sessionKey,storePath};
await sdk.upsertSessionEntry({agentId:'main',sessionKey,storePath,
  entry:{sessionId,updatedAt:Date.now()}});
const sha = s => crypto.createHash('sha256').update(s).digest('hex');
const rows=[];
for (const count of [8192,65536,262144,1048576,1600000]) {
  const text=JSON.stringify({kind:'synthetic-transport-envelope',text:'画面，声音。🖼️\n'.repeat(Math.ceil(count/20))});
  const appended=await transcript.appendSessionTranscriptMessageByIdentityStrict({...scope,
    message:{role:'assistant',content:[{type:'text',text}],stopReason:'stop',
      timestamp:Date.now(),__openclaw:{runId}}});
  assert.equal(appended.kind,'result');
  const raw=sdk.loadTranscriptEventsSync(scope);
  const stored=raw.filter(e=>e.type==='message').at(-1).message;
  assert.equal(stored.content[0].text,text);
  assert.equal(stored.stopReason,'stop');
  assert.equal(stored.__openclaw.runId,runId);
  const recent=await readRecent(scope,{maxMessages:200,maxLines:4020,allowResetArchiveFallback:true});
  const fromReader=recent.messages.at(-1);
  assert.equal(fromReader.content[0].text,text);
  let response;
  await handlers['sessions.get']({params:{sessionKey,agentId:'main',limit:200},client:null,
    context:{getRuntimeConfig:()=>config},respond:(ok,payload,error)=>{assert.ok(ok,String(error));response=payload;}});
  const fromGateway=response.messages.at(-1);
  assert.equal(fromGateway.content[0].text,text);
  assert.equal(fromGateway.stopReason,'stop');
  assert.equal(fromGateway.__openclaw.runId,runId);
  const snapshot=buildSnapshot({visibleText:text});
  assert.ok(snapshot.text.length<=4096);
  assert.notEqual(snapshot.text,text);
  const visible=await transcript.readVisibleSessionTranscriptMessageEntries(scope);
  assert.equal(visible.at(-1).message.content[0].text,text);
  rows.push({utf8_bytes:Buffer.byteLength(text),utf16_chars:text.length,
    stored_sha256:sha(stored.content[0].text),gateway_sha256:sha(fromGateway.content[0].text),
    byte_equal:true,snapshot_truncated:true,raw_events:raw.length,active_messages:recent.messages.length});
}
// A tool-call is persisted with full arguments; it is not a successful final reply.
const args={result:{text:'中文🖼️'.repeat(40000)}};
await transcript.appendSessionTranscriptMessageByIdentityStrict({...scope,message:{role:'assistant',content:[{
  type:'toolCall',id:'probe-tool',name:'synthetic_result',arguments:args}],
  stopReason:'toolUse',timestamp:Date.now(),__openclaw:{runId}}});
const raw=sdk.loadTranscriptEventsSync(scope);
assert.deepEqual(raw.filter(e=>e.type==='message').at(-1).message.content[0].arguments,args);
const underBudget=await transcript.readSessionTranscriptRawDelta({...scope,maxBytes:1024,maxEvents:1000});
assert.equal(underBudget.kind,'page');
assert.equal(underBudget.hasMore,true);
const all=await transcript.readSessionTranscriptRawDelta({...scope,maxBytes:16*1024*1024,maxEvents:1000});
assert.equal(all.kind,'page');
assert.equal(all.hasMore,false);
const wrongScope=await transcript.readSessionTranscriptRawDelta({...scope,sessionId:crypto.randomUUID(),cursor:all.cursor});
assert.equal(wrongScope.kind,'missing');
const first=await transcript.readSessionTranscriptVisibleMessageDelta({...scope,maxBytes:1024,maxMessages:1000});
assert.equal(first.kind,'page');
assert.equal(first.entries.length,0);
assert.ok(first.requiredBytes>1024);
let cursor, pages=0, entries=[];
do {
  const page=await transcript.readSessionTranscriptVisibleMessageDelta({...scope,
    ...(cursor ? {cursor} : {}),maxBytes:3*1024*1024,maxMessages:2});
  assert.equal(page.kind,'page');
  assert.ok(!page.requiredBytes);
  cursor=page.cursor;pages++;entries.push(...page.entries);
  if (!page.hasMore) break;
  assert.ok(pages<20);
} while (true);
assert.equal(entries.length,6);
const branchScope={...scope,sessionKey:'agent:main:easel-probe-branch',sessionId:crypto.randomUUID()};
await sdk.upsertSessionEntry({...branchScope,entry:{sessionId:branchScope.sessionId,updatedAt:Date.now()}});
const user=await transcript.appendSessionTranscriptMessageByIdentityStrict({...branchScope,
  message:{role:'user',content:[{type:'text',text:'synthetic branch fixture'}],timestamp:Date.now()}});
assert.equal(user.kind,'result');
await transcript.appendSessionTranscriptMessageByIdentityStrict({...branchScope,
  message:{role:'assistant',content:[{type:'text',text:'old branch'}],stopReason:'stop',__openclaw:{runId}}});
const prior=await transcript.readSessionTranscriptVisibleMessageDelta({...branchScope,maxBytes:100000,maxMessages:200});
const branch=await transcript.appendSessionTranscriptMessageByIdentityStrict({...branchScope,
  parentId:user.result.messageId,message:{role:'assistant',content:[{type:'text',text:'selected branch'}],
    stopReason:'stop',__openclaw:{runId}}});
assert.equal(branch.kind,'result');
const active=await transcript.readVisibleSessionTranscriptMessageEntries(branchScope);
assert.deepEqual(active.map(e=>e.message.content[0].text),['synthetic branch fixture','selected branch']);
const discontinuity=await transcript.readSessionTranscriptVisibleMessageDelta({...branchScope,cursor:prior.cursor});
// Branch replacement may invalidate the materialized projection before its
// rebuild; neither explicit reset nor unavailable is an acceptable result page.
assert.ok(['reset','unavailable'].includes(discontinuity.kind));
fs.writeFileSync(path.join(root,'recovery.json'),JSON.stringify({scope,expected:rows.at(-1).stored_sha256}));
const recover=spawnSync(process.execPath,[path.join(path.dirname(process.argv[1]),'recover.mjs'),dist,root],
  {encoding:'utf8',env:{PATH:process.env.PATH},timeout:30000});
assert.equal(recover.status,0,recover.stderr);
const recovery=JSON.parse(recover.stdout);
assert.equal(recovery.full_text_sha256,rows.at(-1).stored_sha256);
console.log(JSON.stringify({runtime:'2026.9.4',isolated:true,model_calls:0,
  scope:{sessionId,runId},rows,tool_arguments_bytes:Buffer.byteLength(JSON.stringify(args)),
  tool_arguments_equal:true,raw_delta:{hasMore:underBudget.hasMore,full_events:all.events.length,
    scope_mismatch:wrongScope.kind},visible_delta:{requiredBytes:first.requiredBytes,pages,
      entries:entries.length,branch_state:discontinuity.kind,branch_reason:discontinuity.reason},recovery,
  temporary_state_dir:root},null,2));
process.exit(0);
