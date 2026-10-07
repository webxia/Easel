import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {pathToFileURL} from 'node:url';
const [dist,root]=process.argv.slice(2);
process.env.OPENCLAW_STATE_DIR=root;
process.env.OPENCLAW_CONFIG_PATH=path.join(root,'openclaw.json');
const {scope}=JSON.parse(fs.readFileSync(path.join(root,'recovery.json'),'utf8'));
const {readVisibleSessionTranscriptMessageEntries}=await import(pathToFileURL(path.join(dist,
  'plugin-sdk/session-transcript-runtime.js')).href);
const entries=await readVisibleSessionTranscriptMessageEntries(scope);
const terminal=entries.filter(e=>e.message.stopReason==='stop').at(-1).message;
console.log(JSON.stringify({fresh_process:true,exact_session_id:scope.sessionId,
  run_id:terminal.__openclaw.runId,full_text_sha256:crypto.createHash('sha256').update(
    terminal.content[0].text).digest('hex'),entries:entries.length}));
process.exit(0);
