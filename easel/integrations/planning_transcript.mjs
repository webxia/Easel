// Installed-runtime adapter. No model, credential, config or writable DB opens.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {pathToFileURL} from 'node:url';

const params=JSON.parse(fs.readFileSync(0,'utf8'));
const root=process.argv[2];
const SELECTOR='session-accessor.sqlite-transcript-store-BczH1lRJ.mjs';
const answer=value=>{process.stdout.write(JSON.stringify(value));};
try {
  const pkg=JSON.parse(fs.readFileSync(path.join(root,'package.json'),'utf8'));
  const selectorPath=path.join(root,'dist',SELECTOR);
  if (pkg.version!=='2026.9.4' || !params.runtimeParts || Object.entries(params.runtimeParts).some(([name,sha])=>
      path.basename(name)!==name || crypto.createHash('sha256').update(fs.readFileSync(path.join(root,'dist',name)))
        .digest('hex')!==sha)) throw Error('runtime identity');
  if (!/^[a-z0-9_-]+$/.test(params.agentId) || !params.sessionId || !params.runId ||
      params.sessionKey?.split(':').slice(0,2).join(':')!==`agent:${params.agentId}`) throw Error('scope');
  if (!/^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(params.profile)) throw Error('profile');
  // Reuse the actual CLI projection: custom state/config/home stay authoritative.
  const {r: applyCliProfileEnv}=await import(pathToFileURL(path.join(root,'dist',
    'startup-trace-DTSRmmXT.mjs')).href);
  applyCliProfileEnv({profile:params.profile,env:process.env});
  const {s: resolvePhase}=await import(pathToFileURL(path.join(root,'dist',
    'chat-message-content-CgaQZ9n2.mjs')).href);
  const {withOpenClawAgentDatabaseReadOnly}=await import(pathToFileURL(path.join(root,
    'dist/plugin-sdk/sqlite-runtime.js')).href);
  // Pure canonical selector is version/hash pinned because it is not SDK-exported.
  const {X: selectVisible}=await import(pathToFileURL(selectorPath).href);
  const result=withOpenClawAgentDatabaseReadOnly(database=>{
    const db=database.db;
    db.exec('BEGIN');
    try {
      const size=db.prepare('SELECT COUNT(*) AS n, COALESCE(SUM(LENGTH(CAST(event_json AS BLOB))),0) AS bytes FROM transcript_events WHERE session_id=?')
        .get(params.sessionId);
      if (size.n>4096 || size.bytes>32*1024*1024) return {state:'TRANSCRIPT_TOO_LARGE'};
      const events=db.prepare('SELECT event_json FROM transcript_events WHERE session_id=? ORDER BY seq')
        .all(params.sessionId).map(row=>JSON.parse(row.event_json));
      const header=events.find(e=>e.type==='session');
      if (!header || header.id!==params.sessionId) return {state:'MISSING'};
      const matching=selectVisible(events).filter(row=>row.event?.type==='message' &&
        row.event.message?.role==='assistant' && row.event.message?.__openclaw?.runId===params.runId);
      const last=matching.at(-1);
      if (!last) return {state:'MISSING'};
      const message=last.event.message;
      const content=message.content;
      if (!Array.isArray(content)) return {state:'INVALID'};
      // Tool arguments and thinking are never interpreted as an assistant result.
      if (content.some(block=>['toolCall','toolUse','functionCall'].includes(block?.type)))
        return {state:'NONTERMINAL'};
      if (resolvePhase(message)==='commentary' || content.some(block=>
          resolvePhase({role:'assistant',content:[block]})==='commentary'))
        return {state:'NONTERMINAL'};
      const blocks=content.filter(block=>block?.type==='text');
      if (blocks.some(block=>typeof block.text!=='string')) return {state:'INVALID'};
      const text=blocks.map(block=>block.text).join('');
      if (Buffer.byteLength(text)>params.maxResultBytes) return {state:'RESULT_TOO_LARGE'};
      return {state:'FOUND',sessionId:params.sessionId,runId:params.runId,
        messageId:last.event.id,sequence:last.seq,stopReason:message.stopReason,
        text,sha256:crypto.createHash('sha256').update(text).digest('hex'),
        bytes:Buffer.byteLength(text),runtimeVersion:pkg.version};
    } finally {db.exec('ROLLBACK');}
  },{agentId:params.agentId,env:process.env},{throwOnMissingTable:true});
  answer(result.found?result.value:{state:'MISSING'});
} catch {
  // Avoid raw SQLite/Runtime exception strings or message content in diagnostics.
  answer({state:'UNAVAILABLE'});
}
