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
  if (!params.structured) throw Error('structured request required');
  let structuredGuard;
  {
    if (!params.structuredParts || Object.entries(params.structuredParts).some(([name,sha])=>
        path.isAbsolute(name) || name.split('/').includes('..') ||
        crypto.createHash('sha256').update(fs.readFileSync(path.join(root,name))).digest('hex')!==sha))
      throw Error('structured runtime identity');
    structuredGuard=await import(pathToFileURL(path.join(root,'dist/easel-structured-result.mjs')).href);
    if (params.structured.version!==structuredGuard.VERSION || params.structured.name!==structuredGuard.TOOL)
      throw Error('structured request version');
  }
  if (!/^[a-z0-9_-]+$/.test(params.agentId) || !params.sessionId || !params.runId ||
      params.sessionKey?.split(':').slice(0,2).join(':')!==`agent:${params.agentId}`) throw Error('scope');
  if (!/^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(params.profile)) throw Error('profile');
  // Reuse the actual CLI projection: custom state/config/home stay authoritative.
  const {r: applyCliProfileEnv}=await import(pathToFileURL(path.join(root,'dist',
    'startup-trace-DTSRmmXT.mjs')).href);
  applyCliProfileEnv({profile:params.profile,env:process.env});
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
      if (size.n>4096 || size.bytes>128*1024*1024) return {state:'TRANSCRIPT_TOO_LARGE'};
      const events=db.prepare('SELECT event_json FROM transcript_events WHERE session_id=? ORDER BY seq')
        .all(params.sessionId).map(row=>JSON.parse(row.event_json));
      const header=events.find(e=>e.type==='session');
      if (!header || header.id!==params.sessionId) return {state:'MISSING'};
      const matching=selectVisible(events).filter(row=>row.event?.type==='message' &&
        row.event.message?.role==='assistant' && row.event.message?.__openclaw?.runId===params.runId);
      const last=matching.at(-1);
      if (!last) return {state:'MISSING'};
      const message=last.event.message;
      if (params.inspectTerminalNoTool === true) {
        // A native rejected terminal is not a successful model reply.
        // Require the actual last original Run transcript, not a caller flag.
        if (message.stopReason !== 'error' ||
            message.errorMessage !== 'STRUCTURED_TERMINAL_REJECTED' ||
            !Array.isArray(message.content) ||
            message.content.some(block=>block?.type==='toolCall'))
          return {state:'NOT_ELIGIBLE'};
        return {state:'NATIVE_REJECTED_NO_TOOL', sessionId:params.sessionId,
          runId:params.runId, messageId:last.event.id};
      }
      const content=message.content;
      if (!Array.isArray(content)) return {state:'INVALID'};
      {
        // Active transcript event identity deduplicates stored event replay;
        // distinct model calls or changed messages can never share an acceptance.
        const unique=new Map();
        for (const row of matching) {
          const id=row.event.id;
          const encoded=JSON.stringify(row.event.message);
          if (!id || unique.has(id) && unique.get(id)!==encoded) return {state:'TOOL_REJECTED'};
          unique.set(id,encoded);
        }
        const messages=[...unique.values()].map(value=>JSON.parse(value));
        const calls=messages.flatMap(value=>(value.content??[]).filter(block=>block.type==='toolCall'));
        if (calls.length!==1 || messages.at(-1).stopReason!=='toolUse' ||
            !content.some(block=>block.type==='toolCall') ||
            messages.some(value=>['error','aborted','length'].includes(value.stopReason))) return {state:'TOOL_REJECTED'};
        const evidence=message.easelStructuredResult;
        const call=calls[0];
        const text=call.easelRawArguments;
        if (typeof text!=='string' || Buffer.byteLength(text)>params.maxResultBytes)
          return {state:'RESULT_TOO_LARGE'};
        if (!evidence || evidence.version!==params.structured.version ||
            evidence.schemaSha256!==params.structured.schemaSha256 ||
            params.structured.version==='easel-structured-result@2' &&
              (evidence.contextPolicy!==params.structured.contextPolicy ||
               evidence.inputSha256!==params.structured.inputSha256) ||
            evidence.toolCallId!==call.id || call.name!==params.structured.name ||
            evidence.providerFinishReason!=='tool_calls' || message.easelProviderFinishReason!=='tool_calls' ||
            evidence.rawSha256!==crypto.createHash('sha256').update(text).digest('hex') ||
            evidence.rawBytes!==Buffer.byteLength(text)) return {state:'TOOL_REJECTED'};
        try {
          if (structuredGuard.canonical(structuredGuard.safeArguments(text))!==structuredGuard.canonical(call.arguments))
            return {state:'TOOL_REJECTED'};
        } catch {return {state:'TOOL_REJECTED'};}
        return {state:'FOUND',sessionId:params.sessionId,runId:params.runId,
          messageId:last.event.id,sequence:last.seq,stopReason:message.stopReason,
          text,sha256:evidence.rawSha256,bytes:evidence.rawBytes,runtimeVersion:pkg.version,
          toolName:call.name,toolCallId:call.id,schemaSha256:evidence.schemaSha256,
          ...(params.structured.version==='easel-structured-result@2' ? {
            contextPolicy:evidence.contextPolicy,inputSha256:evidence.inputSha256} : {}),
          providerFinishReason:evidence.providerFinishReason};
      }
    } finally {db.exec('ROLLBACK');}
  },{agentId:params.agentId,env:process.env},{throwOnMissingTable:true});
  if (params.inspectTerminalNoTool === true) {
    const transcript=result.found?result.value:{state:'MISSING'};
    if (transcript.state !== 'NATIVE_REJECTED_NO_TOOL')
      {answer({state:'UNAVAILABLE'});}
    else {
      try {
        // Native OpenClaw itself writes this scoped rejection before sanitizing
        // the agent error event. Inspect it read-only under the pinned profile.
        const state=process.env.OPENCLAW_STATE_DIR;
        if (!state || !path.isAbsolute(state)) throw Error('state directory');
        const identity=structuredGuard.canonical({runId:params.runId,sessionId:params.sessionId});
        const key=crypto.createHash('sha256').update(identity).digest('hex');
        const file=path.join(state,'easel-structured-requests','rejection-'+key+'.json');
        const stat=fs.lstatSync(file);
        if (!stat.isFile() || stat.isSymbolicLink() || stat.size > 4096 ||
            (stat.mode & 0o077)!==0) throw Error('rejection file');
        const bytes=fs.readFileSync(file);
        const row=JSON.parse(bytes.toString('utf8'));
        const current = params.structured.version === 'easel-structured-result@2';
        if (row.version !== (current ? 'easel-structured-rejection@2' : 'easel-structured-rejection@1') ||
            current && (row.storageReason !== 'UNKNOWN' || row.storageStage !== 'UNKNOWN' ||
              row.contextPolicy !== params.structured.contextPolicy || row.inputSha256 !== params.structured.inputSha256) ||
            row.runId !== params.runId || row.sessionId !== params.sessionId ||
            row.schemaSha256 !== params.structured.schemaSha256 ||
            row.category !== 'STRUCTURED_TERMINAL_REJECTED' ||
            row.providerFinishShape !== 'string' || row.providerFinishValue !== 'stop' ||
            row.nativeStopShape !== 'string' || row.nativeStopValue !== 'stop' ||
            row.toolCallCount !== 0 || row.uniqueExpectedTool !== false ||
            row.idPresent !== false || row.rawArgumentsShape !== 'missing' ||
            row.rawArgumentBytes !== null ||
            row.provider !== 'minimax' || typeof row.model !== 'string' ||
            !row.model.startsWith('MiniMax-M3.1-'))
          throw Error('rejection provenance');
        answer({state:'CONFIRMED_TERMINAL_NO_TOOL',sessionId:params.sessionId,
          runId:params.runId,model:row.model,provider:row.provider,
          schemaSha256:row.schemaSha256,providerFinish:'stop',nativeStop:'stop',
          category:row.category,toolCallCount:row.toolCallCount,
          nativeEvidenceSha256:crypto.createHash('sha256').update(bytes).digest('hex'),
          transcriptMessageId:transcript.messageId});
      } catch {
        answer({state:'UNAVAILABLE'});  // No native proof, no new operation.
      }
    }
  } else answer(result.found?result.value:{state:'MISSING'});

} catch {
  // Avoid raw SQLite/Runtime exception strings or message content in diagnostics.
  answer({state:'UNAVAILABLE'});
}
