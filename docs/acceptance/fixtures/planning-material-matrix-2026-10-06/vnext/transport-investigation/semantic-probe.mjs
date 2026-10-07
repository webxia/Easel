import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {pathToFileURL} from 'node:url';

// Execute only installed Runtime modules and the actual Easel read-only bridge.
const [runtimeRoot, bridge, payloadDir, runtimePartsJson] = process.argv.slice(2);
const stateDir=fs.mkdtempSync(path.join(os.tmpdir(),'easel-vnext-legal-'));
process.env.OPENCLAW_STATE_DIR=stateDir;
process.env.OPENCLAW_CONFIG_PATH=path.join(stateDir,'openclaw.json');
fs.writeFileSync(process.env.OPENCLAW_CONFIG_PATH,JSON.stringify({agents:{entries:{main:{}}}}));
const moduleAt = name=>import(pathToFileURL(path.join(runtimeRoot,'dist',name)).href);
const {upsertSessionEntry}=await moduleAt('plugin-sdk/session-store-runtime.js');
const {appendSessionTranscriptMessageByIdentityStrict}=await moduleAt('plugin-sdk/session-transcript-runtime.js');
const storePath=path.join(stateDir,'agents/main/sessions/sessions.json');
const rows=[];
let lastScope;
const hash=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
for (const kind of ['A','B','REPAIR']) {
  const original=fs.readFileSync(path.join(payloadDir,kind+'-legal.json'),'utf8');
  const scope={agentId:'main',sessionId:crypto.randomUUID(),sessionKey:'agent:main:easel-legal-'+kind,storePath};
  const runId='easel-probe-'+crypto.randomUUID();
  await upsertSessionEntry({...scope,entry:{sessionId:scope.sessionId,updatedAt:Date.now()}});
  for (const [stopReason,text] of [['error','{"partial":true}'],['length','{"partial":'],['stop',original]]) {
    const result=await appendSessionTranscriptMessageByIdentityStrict({...scope,
      message:{role:'assistant',content:[{type:'text',text}],stopReason,__openclaw:{runId}}});
    assert.equal(result.kind,'result');
  }
  const dbFile=path.join(stateDir,'agents/main/agent/openclaw-agent.sqlite');
  const stateHashes=()=>Object.fromEntries([dbFile,dbFile+'-wal'].filter(p=>fs.existsSync(p))
    .map(p=>[p,hash(fs.readFileSync(p))]));
  const before=stateHashes();
  const params={...scope,runId,profile:'fixture',runtimeParts:JSON.parse(runtimePartsJson),maxResultBytes:8*1024*1024};
  const child=spawnSync(process.execPath,[bridge,runtimeRoot],{input:JSON.stringify(params),
    encoding:'utf8',env:{PATH:process.env.PATH,OPENCLAW_STATE_DIR:stateDir,OPENCLAW_CONFIG_PATH:process.env.OPENCLAW_CONFIG_PATH},timeout:20000,maxBuffer:32*1024*1024});
  assert.equal(child.status,0,child.stderr);
  const captured=JSON.parse(child.stdout);
  assert.equal(captured.state,'FOUND');
  assert.equal(captured.text,original);
  assert.equal(captured.sha256,hash(Buffer.from(original)));
  assert.equal(captured.runId,runId);
  assert.equal(captured.sessionId,scope.sessionId);
  assert.equal(captured.stopReason,'stop');
  assert.deepEqual(stateHashes(),before,'read-only bridge changed SQLite/WAL');
  lastScope={...scope,runId};
  rows.push({kind,bytes:Buffer.byteLength(original),sha256:captured.sha256,
    original_equal:true,readonly_database_unchanged:true,fresh_process:true,
    prior_error_length_ignored:true,messageId:captured.messageId});
}
const guards=[];
for (const [kind,message,expected] of [
  ['commentary_signature',{role:'assistant',content:[{type:'text',text:'{}',textSignature:JSON.stringify({v:1,phase:'commentary'})}],stopReason:'stop'},'NONTERMINAL'],
  ['mixed_phase',{role:'assistant',phase:'final_answer',content:[{type:'text',text:'{}',textSignature:JSON.stringify({v:1,phase:'commentary'})},{type:'text',text:'{}',textSignature:JSON.stringify({v:1,phase:'final_answer'})}],stopReason:'stop'},'NONTERMINAL'],
  ['tool_arguments',{role:'assistant',content:[{type:'toolCall',id:'call',name:'capture',arguments:{value:'{}'}}],stopReason:'toolUse'},'NONTERMINAL'],
]) {
  await appendSessionTranscriptMessageByIdentityStrict({...lastScope,message:{...message,__openclaw:{runId:lastScope.runId}}});
  const params={...lastScope,profile:'fixture',runtimeParts:JSON.parse(runtimePartsJson),maxResultBytes:8*1024*1024};
  const child=spawnSync(process.execPath,[bridge,runtimeRoot],{input:JSON.stringify(params),encoding:'utf8',
    env:{PATH:process.env.PATH,OPENCLAW_STATE_DIR:stateDir,OPENCLAW_CONFIG_PATH:process.env.OPENCLAW_CONFIG_PATH},timeout:20000});
  assert.equal(JSON.parse(child.stdout).state,expected);
  guards.push({kind,state:expected,pass:true});
}
console.log(JSON.stringify({guards,custom_state_profile_preserved:true,runtime:'2026.9.4',model_calls:0,isolated:true,rows},null,2));
process.exit(0);
