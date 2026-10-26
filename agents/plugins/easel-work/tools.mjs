// Native OpenClaw integration. No production orchestration or provider credentials.
import { createHash } from 'node:crypto';
import { installDiagnostics } from './diagnostics.mjs';
import { setTimeout as delay } from 'node:timers/promises';

// OpenClaw can load tool factories and lifecycle hooks through separate plugin
// registrations. Keep native tickets in one process registry, scoped to the
// exact endpoint/agent/protocol/credential; no identity comes from model params.
const registryKey = Symbol.for('easel.workBridge.nativeCalls.v1');
const registries = globalThis[registryKey] ??= new Map();
export const toolDefinitions = [
  {
    name: 'easel_work_context', description: 'Read the currently bound work and selected creative context.',
    parameters: { type: 'object', properties: {}, additionalProperties: false },
  },
  {
    name: 'easel_work_create_draft', description: 'Create one draft only when the user explicitly requests a video.',
    parameters: { type: 'object', properties: { title: { type: 'string', minLength: 1, maxLength: 200 }, input_text: { type: 'string', minLength: 1, maxLength: 100000 } }, required: ['title', 'input_text'], additionalProperties: false },
  },
  {
    name: 'easel_work_request_plan', description: 'Propose the full video production plan ONLY. Never use for reference analysis. To analyse a reference, use easel_work_propose kind=director_formation with values {name, reference_input_ids}; answering that proposal schedules analysis. Does not authorize paid services.',
    parameters: { type: 'object', properties: { request: { type: 'string', minLength: 1, maxLength: 100000 } }, required: ['request'], additionalProperties: false },
  },
];


// Grant requests may omit services for planning: the host resolves the current
// model and paused task before presenting the proposal, never after consent.
const pipelineValuesSchema = {
  type: 'object',
  description: 'Action-specific values. For bind, use kind, channel_id, director_revision (the exact revision ID, never director_id or a numeric version), and director_trial together for the targets already selected in user sources. For grant purpose=planning, send only {"purpose":"planning"}; the server returns exact services and the paused decision_id. Present returned values.payload and values.summary before asking for consent. Never wrap services in item, or copy label/available fields.',
  properties: {
    kind: { type: 'string', enum: ['new_work','channel_create','director_formation','revise','continue'], description: 'Existing conversation pipeline, not a production stage.' },
    channel_id: { type: 'string', description: 'Selected channel ID from pending.channels; preserve an already selected channel.' },
    director_revision: { type: 'string', description: 'Selected director VERSION ID from pending.directors[].id, matched by director name and revision number. Do not send director_id, director, label, or a numeric version.' },
    director_trial: { type: 'boolean', description: 'true for a style-confirmed version without accepted_at, when the user selected it as a trial.' },
    work_id: { type: 'string', description: 'Existing current work only when continuing it; never copy another work.' },
    output_id: { type: 'string', description: 'Existing output for preview, revision or acceptance, from current work.' },
    output_revision: { type: 'integer', minimum: 1, description: 'preview only: actual rendered output revision; omit both selectors for latest output.' },
    draft_id: { type: 'string', description: 'Existing publication draft ID from the actual preparation receipt.' },
    revision: { type: 'integer', minimum: 1, description: 'Current publication draft revision for publication_save.' },
    changes: { type: 'object', description: 'publication_save only: title/body/tags/tid/copyright/source changes explicitly requested by the user. No account, credits or upload action.' },
    title: { type: 'string', description: 'Draft title.' },
    input_text: { type: 'string', description: 'Draft content or basis input; preserve user facts.' },
    request: { type: 'string', description: 'Plan request; not the finished plan.' },
    intent: { type: 'string', enum: ['replan'], description: 'offer action=plan for an explicit rewrite of an existing plan: put intent here in values, with request; user_quote remains at the ROOT.' },
    duration_seconds: {type:'number',minimum:1,maximum:900,description:'For plan: explicitly requested fixed film length. For revise: explicitly confirmed shorter ending, preserving complete speech and captions; requires preserve_audio=false because music is trimmed. Show the new duration in the proposal before confirmation. Omit otherwise.'},
    settings: { type: 'object', description: 'Only the typed delta actually requested by the user, never copy all settings. basis is for unconfirmed work. For a safely stopped pre-output mixed plan, plan may use exactly {audio_mode:"voice"}: no BGM or optional SFX, all other content protected; show the returned scope and costs before confirmation.' },
    restore_cancelled: {type:'boolean',description:'For plan audio-only recovery of a cancelled work: true only when the user explicitly requests restoring this work; a later human answer must confirm the displayed proposal.'},
    plan_revision: { type: 'integer', minimum: 1, description: 'Current plan revision number from pending.work.' },
    plan_hash: { type: 'string', minLength: 64, maxLength: 64, description: 'Exact full current plan_hash from pending.work.plans, never abbreviate.' },
    allow_ai: { type: 'boolean' },
    image_limit: { type: 'integer', minimum: 0 },
    video_limit: { type: 'integer', minimum: 0 },
    feedback: { type: 'string' },
    preserve_audio: { type: 'boolean' },
    review_id: { type: 'string' },
    change_hash: { type: 'string', minLength: 64, maxLength: 64 },
    manual_review_confirmed: { type: 'boolean', description: 'Only true when the user explicitly states a complete review.' },
    revision_id: { type: 'string', description: 'Exact director revision ID for director_style/director_accept/channel_director.' },
    trial_artifact_id: { type: 'string' },
    attachment_id: { type: 'string' },
    usage: { type: 'string', enum: ['reference','must_use'] },
    original_audio: { type: 'boolean' },
    interval: { type: 'object', properties: {start:{type:'number'},end:{type:'number'}}, required:['start','end'], additionalProperties:false },
    rights_confirmed: { type: 'boolean' },
    target_ref: { type: 'string' },
    purpose: { type: 'string', enum: ['planning', 'preview', 'production'] },
    services: { type: 'array', items: {
      type: 'object', properties: { provider: { type: 'string', minLength: 1 }, model: { type: 'string', minLength: 1 }, mode: { type: 'string', minLength: 1 } },
      required: ['provider', 'model', 'mode'], additionalProperties: false,
    } },
    decision_id: { type: 'string', description: 'Exact paused task returned by server; do not invent. Planning grants bind it automatically at offer time.' },
  },
  additionalProperties: true,
};

// The persistent pipeline has one draft/plan route. The protocol-1 proposal
// adapters sound like immediate creation, but only stage an extra question.
export const persistentToolDefinitions = [toolDefinitions[0],
  {name:'easel_pipeline',description:'Easel pipeline pending/answer/resume adapter. pending reads real choices, proposals, plans and progress. To view an existing film use mode=preview with values {output_id} or {output_revision}, or {} for latest. This is read-only, returns playback_url, current-version checks and preview_text, and requires no confirmation. Never use revise/plan to retrieve a playback link. bind takes values {kind,channel_id,director_revision,director_trial} using exact IDs from pending; include all targets already explicitly selected in user sources. When queued=true finish this native turn; the host automatically continues after verified handoff. Do not ask the user to say continue. already_bound=true is a no-op: continue in this turn, without asking users to repeat existing choices. bind/draft/answer require ROOT user_quote copied verbatim from the current human message, not source_refs or values.user_quote. draft creates a local draft with values {title,input_text}; no settings or source_refs inside values. offer stages an exact operation and user-visible summary; answer applies a previously shown proposal using this turn user_quote. Its arguments are ROOT fields: {mode:"answer",proposal_id,hash,user_quote,dismiss}; do not put these inside values. values belongs to bind/draft/offer. Never infer authorization from praise; ask if unclear. For a known failed first plan with no valid Plan, read pending.failed_planning_replan and offer plan with its decision_id; show returned scope and costs and wait for a NEW human answer. Never cancel the whole work to clear this failure. For UNKNOWN planning, read pending.model_calls; only offer replan_after_unknown using its decision_id. Show the server summary including duplicate charges, then wait for a NEW human answer. Never use resume to resend UNKNOWN. No arbitrary commands.',parameters:{type:'object',properties:{mode:{type:'string',enum:['pending','preview','bind','draft','offer','answer']},action:{type:'string',enum:['input','plan','confirm','grant','resume','cancel','replan_after_unknown','basis','revise','confirm_revision','accept','publication_prepare','publication_save','director_style','director_accept','channel_director']},values:pipelineValuesSchema,summary:{type:'string'},user_quote:{type:'string',description:'Exact text from the CURRENT human message, never an assistant reply or task event.'},proposal_id:{type:'string',minLength:32,maxLength:32,pattern:'^[a-f0-9]{32}$',description:'Full opaque ID copied exactly from pending.pending[].id. Never use a shortened display prefix, ellipsis, draft ID or invented ID. Read pending again if uncertain; do not create a replacement proposal just to fix this argument.'},hash:{type:'string',minLength:64,maxLength:64,pattern:'^[a-f0-9]{64}$',description:'Full 64-character hash copied exactly from the SAME pending proposal. Not plan_hash, body text, or an abbreviation.'},dismiss:{type:'boolean',description:'REQUIRED for answer: true declines/cancels ONLY this proposal; false explicitly approves the displayed operation. Never omit this decision. A cancellation request uses true, never action=cancel (which cancels the work).'}},required:['mode'],allOf:[{if:{properties:{mode:{const:'answer'}},required:['mode']},then:{required:['dismiss']}},{if:{properties:{mode:{enum:['bind','draft','answer']}},required:['mode']},then:{required:['user_quote']}}],additionalProperties:false}},
  { name:'easel_work_input_evidence', description:'Read scoped input metadata. Media is unanalysed unless actual analysis evidence exists.', parameters:{type:'object',properties:{input_ids:{type:'array',items:{type:'string'},maxItems:100}},additionalProperties:false} },
  { name:'easel_work_register_inputs', description:'Register a current turn upload handle as reference or must-use. Does not grant rights or original audio permission.', parameters:{type:'object',properties:{attachment_id:{type:'string'},usage:{type:'string',enum:['reference','must_use']}},required:['attachment_id'],additionalProperties:false} },
  { name:'easel_work_update_brief', description:'Save genuine changes to creative requirements BEFORE proposing planning/production. This invalidates an existing unconfirmed plan. Never call after offer confirm; user approval or service clarification does not require rewriting the brief. user_requirement must quote visible user text verbatim; summaries are suggestions. No production.', parameters:{type:'object',properties:{entries:{type:'array',minItems:1,maxItems:100,items:{type:'object',properties:{kind:{type:'string',enum:['user_requirement','suggestion','unresolved']},text:{type:'string'},source_refs:{type:'array',items:{type:'string'}}},required:['kind','text','source_refs'],additionalProperties:false}}},required:['entries'],additionalProperties:false} },
  { name:'easel_work_request_revision', description:'Propose revision of the selected output only. User answers the proposal in conversation before any work is scheduled.', parameters:{type:'object',properties:{feedback:{type:'string',minLength:1,maxLength:10000},protected:{type:'array',items:{type:'string'}},interval:{type:['object','null']}},required:['feedback'],additionalProperties:false} },
  { name:'easel_work_propose', description:'Propose channel creation/defaults, director formation/style or 1–3 reusable Profile preferences. Candidate only; never saves targets. Bind sources to visible user turn refs.', parameters:{type:'object',properties:{kind:{type:'string',enum:['channel_create','channel_defaults','director_formation','profile','director_revision']},values:{type:'object',description:'director_revision: ONLY style and base_revision; omit name and base_director_id because selected director identity comes from the server. director_formation: name, reference_input_ids and optional analysis_scope.',properties:{name:{type:'string'},analysis_scope:{type:'string',enum:['full','visual'],description:'full observes reference audio and images; visual explicitly observes images/story only, reference audio remains unanalysed.'},reference_input_ids:{type:'array',minItems:1,uniqueItems:true,items:{type:'string'}},creative_basis:{type:'object',properties:{position:{type:'string'},themes:{type:'string'},audience:{type:'string'}},additionalProperties:false},settings:{type:'object'},base_director_id:{type:'string'},base_revision:{type:'integer'},style:{type:'object',properties:{schema_version:{type:'integer',enum:[1]},visual_style:{type:'string'},storytelling:{type:'string'},rhythm:{type:'string'},sound:{type:'string'},typography:{type:'string'},invariants:{type:'array',items:{type:'string'}},freedom:{type:'array',items:{type:'string'}},evidence_notes:{type:'array',items:{type:'string'}}},additionalProperties:false},file:{type:'string',enum:['style','preferences','memory']},before_hash:{type:'string'},after:{type:'string'},entries:{type:'array',items:{type:'string'}}},additionalProperties:false},source_refs:{type:'array',minItems:1,items:{type:'string'}}},required:['kind','values','source_refs'],additionalProperties:false} },
];

export function createWorkBridge(api) {
  const { baseUrl, token, agentId = 'main', protocolVersion = 2 } = api.pluginConfig ?? {};
  const scopedMain = agentId === 'main' && protocolVersion === 2;
  const inPipeline = ctx => ctx.agentId === agentId && (!scopedMain || (typeof ctx.sessionKey === 'string' && ctx.sessionKey.startsWith('agent:main:easel-pipeline:')));
  const definitions = protocolVersion === 2 ? persistentToolDefinitions : toolDefinitions;
  const url = new URL(baseUrl);
  if (url.protocol !== 'http:' || url.hostname !== '127.0.0.1' || !url.port || url.pathname !== '/' || url.search || url.hash || url.username || url.password || !token || token.length < 24) {
    throw new Error('Easel bridge requires an explicit loopback endpoint and service credential');
  }
  api.registerHttpRoute({
    path: '/plugins/easel-work/status', auth: 'gateway', match: 'exact',
    handler(req, res) {
      if (req.method !== 'GET') { res.statusCode = 405; res.end(); return; }
      res.setHeader('Content-Type', 'application/json');
      res.end(JSON.stringify({ protocol: protocolVersion, agent_id: agentId, permission_policy: scopedMain ? 'main-pipeline-v1' : undefined, bootstrap_policy: scopedMain ? 'product-bootstrap-v1' : undefined, natural_entry: scopedMain, automatic_handoff: scopedMain, host_owned_entry_input: scopedMain, tools: definitions.map(t => t.name) }));
    },
  });
  const scope = createHash('sha256').update(JSON.stringify([baseUrl, agentId, protocolVersion, token])).digest('hex');
  const calls = registries.get(scope) ?? new Map();
  registries.set(scope, calls);
  const entries = registries.get(scope + ':entries') ?? new Map();
  registries.set(scope + ':entries', entries);
  const prepared = registries.get(scope + ':prepared') ?? new Map();
  registries.set(scope + ':prepared', prepared);
  const bootstraps = registries.get(scope + ':bootstrap') ?? new Map();
  registries.set(scope + ':bootstrap', bootstraps);
  const runKey = ctx => JSON.stringify([ctx.sessionKey, ctx.sessionId, ctx.runId]);
  const hash = text => createHash('sha256').update(text).digest('hex');
  const names = new Set(definitions.map(t => t.name));
  const identity = (ctx, event = {}) => ({ agent_id: ctx.agentId, session_key: ctx.sessionKey, session_id: ctx.sessionId, run_id: ctx.runId ?? event.runId });
  const key = (ctx, id, name) => `${ctx.sessionKey}\0${ctx.sessionId}\0${name}\0${id}`;
  async function send(path, body, signal) {
    const response = await fetch(`${url.origin}/api/chat/work-tools/${path}`, {
      method: 'POST', redirect: 'error', signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(5000)]) : AbortSignal.timeout(5000),
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }, body: JSON.stringify(body),
    });
    const result = await response.json();
    if (!response.ok) {
      const code = result?.error?.code ?? 'work_bridge_unavailable';
      const hint = ['invalid_input','invalid_source','work_not_bound','not_found','plan_revision_required','revision_required','revision_target_missing','revision_review_missing','stale_revision','binding_mismatch','confirmation_required'].includes(code) ? result?.error?.user_message : undefined;
      const error = new Error(code + (typeof hint === 'string' ? ': ' + hint : ''));
      // Only structured bridge codes may be echoed by the natural-entry gate.
      error.bridgeCode = typeof code === 'string' && /^[a-z][a-z0-9_]{0,79}$/.test(code) ? code : 'work_bridge_unavailable';
      throw error;
    }
    return result;
  }
  if (scopedMain) {
    if (typeof api.registerHook !== 'function') throw new Error('Easel pipeline requires native bootstrap filtering');
    api.registerHook('agent:bootstrap', async event => {
      const ctx=event.context;
      if (!ctx || !inPipeline({...ctx,agentId:ctx.agentId ?? 'main'})) return;
      const original=ctx.bootstrapFiles ?? [];
      const source=original.find(file=>file.name==='AGENTS.md');
      // Remove general memory/personality BEFORE native context compilation.
      // On failure the native pre-model gate below also blocks this turn.
      ctx.bootstrapFiles=[];
      bootstraps.set(ctx.sessionKey,{sessionId:ctx.sessionId,ready:false});
      try {
        const value=await send('bootstrap',{agent_id:agentId,session_key:ctx.sessionKey,session_id:ctx.sessionId ?? null});
        if (value.bootstrap_policy!=='product-bootstrap-v1' || typeof value.system_prompt!=='string' || !value.system_prompt.trim()) throw new Error('missing product bootstrap');
        ctx.bootstrapFiles=[{name:'AGENTS.md',path:source?.path ?? `${ctx.workspaceDir}/AGENTS.md`,missing:false,content:value.system_prompt}];
        bootstraps.set(ctx.sessionKey,{sessionId:ctx.sessionId,ready:true});
      } catch { /* No fallback to global workspace files. */ }
    },{name:'easel-pipeline-bootstrap'});
  }
  if (scopedMain) api.on('before_prompt_build', async (event, ctx) => {
    if (!inPipeline(ctx)) return;
    const previous = prepared.get(runKey(ctx));
    prepared.delete(runKey(ctx));
    try {
      const bootstrap=bootstraps.get(ctx.sessionKey);
      if (!bootstrap?.ready || (bootstrap.sessionId && bootstrap.sessionId!==ctx.sessionId)) throw new Error('product bootstrap unavailable');
      if (!ctx.runId || !ctx.sessionId) throw new Error('missing native identity');
      // A native mid-turn compaction retries with a continuation prompt. Reclaim
      // the original authenticated turn, never adopt that text as new user intent.
      const claimPrompt = previous?.retryPending ? previous.claimPrompt : event.prompt;
      const value = await send('claim', {...identity(ctx), prompt:claimPrompt});
      if (!value.bound || value.permission_policy !== 'main-pipeline-v1' || typeof value.system_prompt !== 'string' || !value.system_prompt.trim()) throw new Error('missing scoped policy');
      prepared.set(runKey(ctx), {promptHash:hash(event.prompt), claimPrompt, retryPending:false});
      return {systemPrompt:value.system_prompt, toolsAllow:[...names]};
    } catch {
      // The input gate below blocks model execution, not merely tool visibility.
      return {systemPrompt:'受控管线未就绪，停止本轮。', toolsAllow:[]};
    }
  });
  api.on('before_agent_run', async (event, ctx) => {
    if (!inPipeline(ctx)) {
      if (scopedMain && ctx.agentId === 'main') {
        entries.delete(runKey(ctx));
        try {
          const result = await send('entry', {...identity(ctx), mode:'claim', prompt:event.prompt});
          if (result.bound) entries.set(runKey(ctx), {entered:false});
        } catch {
          entries.set(runKey(ctx), {failed:true});
          return {outcome:'block', reason:'easel_entry_binding_unavailable', message:'创作入口会话校验失败，本轮已停止，未开始制作。'};
        }
      }
      return;
    }
    if (scopedMain) {
      if (prepared.get(runKey(ctx))?.promptHash !== hash(event.prompt)) return {outcome:'block', reason:'easel_pipeline_not_prepared', message:'管线权限未就绪，本轮未执行。'};
      return;
    }
    try {
      await send('claim', { ...identity(ctx, event), prompt: event.prompt });
    } catch {
      return { outcome: 'block', reason: 'easel_work_binding_unavailable', message: '作品会话未就绪，本轮未调用模型或制作服务。' };
    }
  });
  api.on('before_tool_call', async (event, ctx) => {
    if (!inPipeline(ctx)) {
      if (!scopedMain || ctx.agentId !== 'main') return;
      const entry=entries.get(runKey(ctx));
      if (entry?.terminalError) return {block:true,blockReason:entry.terminalError};
      if (entry?.failed) return {block:true,blockReason:'easel_entry_binding_unavailable'};
      if (entry?.entered) return {block:true, blockReason:'easel_pipeline_entered_finish_turn'};
      if (entry?.pending) return {block:true, blockReason:'easel_entry_pending_finish_turn: 入口调用尚未取得成功回执；本轮停止其他工具调用，不重派入口，不尝试读取画像。'};
      if (event.toolName === 'easel_pipeline') {
        if (!entry || event.params?.mode !== 'enter' || !(event.toolCallId ?? ctx.toolCallId)) {
          entries.set(runKey(ctx), {failed:true});
          return {block:true,blockReason:'easel_entry_not_bound'};
        }
        entry.pending=true;
        entry.call=event.toolCallId ?? ctx.toolCallId;
        entry.params=JSON.stringify(event.params);
        // Tool factories have session identity but no runId in OpenClaw.
        // Carry only the identity authenticated by this native hook to execute.
        calls.set(key(ctx, entry.call, event.toolName), {...identity(ctx, event), entry});
      }
      return;
    }
    if (scopedMain && !prepared.has(runKey(ctx))) return {block:true, blockReason:'easel_pipeline_not_prepared'};
    if (!names.has(event.toolName)) return { block: true, blockReason: 'easel_work_tool_not_allowed' };
    try {
      const result = await send('prepare', { ...identity(ctx, event), tool_call_id: event.toolCallId ?? ctx.toolCallId, tool: event.toolName, params: event.params }, ctx.abortSignal);
      calls.set(key(ctx, event.toolCallId ?? ctx.toolCallId, event.toolName), { ...identity(ctx, event), ticket: result.ticket });
    } catch {
      return { block: true, blockReason: 'easel_work_tool_binding_rejected' };
    }
  });
  const finishDiagnostic = protocolVersion === 2 ? installDiagnostics(api, agentId, inPipeline) : null;
  api.on('agent_end', async (event, ctx) => {
    const entry = entries.get(runKey(ctx));
    if (scopedMain && ctx.agentId === 'main' && !inPipeline(ctx) && entry?.entered) {
      await send('entry', {...identity(ctx,event), mode:'end', prompt:''});
    }
    // OpenClaw emits agent_end for an internal attempt before its official
    // overflow compaction/retry. That is not the end of the Easel turn.
    const lastAssistant = Array.isArray(event.messages) ? event.messages.findLast(m => m?.role === 'assistant') : undefined;
    const overflowError = event.error || (lastAssistant?.stopReason === 'error' ? lastAssistant.errorMessage : '');
    const retryingOverflow = /^(?:Context overflow:|prompt too large for the model)/i.test(overflowError || '');
    if (scopedMain && inPipeline(ctx) && prepared.has(runKey(ctx)) && retryingOverflow) {
      prepared.get(runKey(ctx)).retryPending = true;
      for (const [id, call] of calls) if (call.run_id === ctx.runId && call.session_key === ctx.sessionKey && call.session_id === ctx.sessionId) calls.delete(id);
      return;
    }
    entries.delete(runKey(ctx));
    const bound = identity(ctx, event);
    for (const [id, call] of calls) if (call.run_id === bound.run_id && call.session_key === bound.session_key && call.session_id === bound.session_id) calls.delete(id);
    if (!inPipeline(ctx)) return;
    prepared.delete(runKey(ctx));
    // If delivery fails the reservation remains occupied. Never release it on a guessed timeout.
    await send('end', {...bound, ...(finishDiagnostic ? {diagnostic:finishDiagnostic(event,ctx)} : {})});
  });
  api.registerTool(ctx => {
    if (!inPipeline(ctx)) {
      if (!scopedMain || ctx.agentId !== 'main') return null;
      return [{name:'easel_pipeline',label:'进入创作讨论管线',
        description:'当用户要讨论、创建或修改视频、频道或导演时，先进入现有受控管线，再读取创作资料；不要走旧技能的shell制作链。这里只切换讨论上下文，不创建作品、不确认方案、不授权或执行付费服务。普通闲聊和其他任务不调用。返回真实候选后说明并询问缺项，原生回合结束后宿主自动续接，无需用户回复继续、点击或重复主题。',
        parameters:{type:'object',properties:{mode:{type:'string',enum:['enter']},kind:{type:'string',enum:['new_work','channel_create','director_formation']},},required:['mode','kind'],additionalProperties:false},
        async execute(id,params,signal){
          const call=calls.get(key(ctx,id,'easel_pipeline'));
          const entry=call?.entry ?? (ctx.runId ? entries.get(runKey(ctx)) : undefined);
          if (entry?.terminalError) throw Error(entry.terminalError);
          if (!call || entries.get(JSON.stringify([call.session_key,call.session_id,call.run_id])) !== entry ||
              (ctx.runId && ctx.runId !== call.run_id)) throw Error('easel_entry_not_bound');
          if (!entry || entry.entered || entry.dispatched || entry.call !== id || entry.params !== JSON.stringify(params)) throw Error('easel_entry_not_bound');
          // Once dispatched, a lost receipt must not fall back to unrestricted tools.
          entry.dispatched=true;
          try {
            const {entry:_,...bound}=call;
            const result=await send('entry',{...params,...bound,prompt:'',tool_call_id:id},signal);
            if (result?.entered !== true || typeof result.segment_id !== 'string' || !result.segment_id.trim() ||
                !result.pending || typeof result.pending !== 'object' || Array.isArray(result.pending)) {
              throw Object.assign(new Error('invalid_entry_receipt'), {bridgeCode:'invalid_entry_receipt'});
            }
            entry.entered=true;
            return {content:[{type:'text',text:JSON.stringify(result)}],details:result};
          } catch (error) {
            entry.terminalError=`easel_entry_failed_finish_turn: ${error?.bridgeCode ?? 'entry_result_unknown'}。创作入口调用失败或未取得有效成功回执，本轮工具调用已停止。不得声称已读取画像或继续尝试读取，不得退回通用工具或重派入口。向用户说明错误并结束本轮；入口是否已提交需核对，不能据此认定未创建讨论上下文。`;
            throw new Error(entry.terminalError, {cause:error});
          } finally {
            entry.pending=false;
          }
        }}];
    }
    return definitions.map(definition => ({
      ...definition, label: definition.name,
      async execute(toolCallId, params, signal, onUpdate) {
        const call = calls.get(key(ctx, toolCallId, definition.name));
        if (!call) throw new Error('easel_work_missing_native_call_binding');
        try {
          const request = { ...call, tool_call_id: toolCallId, tool: definition.name, params };
          let details = await send('dispatch', request, signal);
          // dispatch has committed and released SQLite before this promise waits.
          // No model-supplied run ID and no resubmission on poll/network failure.
          if (protocolVersion === 2 && details.work_id && details.run_id) {
            details = await awaitExecution(send, request, details, signal, onUpdate);
          }
          return { content: [{ type: 'text', text: JSON.stringify(details) }], details };
        } finally { calls.delete(key(ctx, toolCallId, definition.name)); }
      },
    }));
  }, { names: [...names] });
}

// Native execution remains pending, not a detached result job. Short HTTP reads
// release all DB resources between polls; the native run's own abort still wins.
export async function awaitExecution(send, request, receipt, signal, onUpdate, {intervalMs=1000, budgetMs=300000}={}) {
  const deadline=Date.now()+budgetMs;
  let previous;
  try {
    while (true) {
      signal?.throwIfAborted();
      const value=await send('result', {...request, interrupted:Date.now()>=deadline}, signal);
      if (!value.waiting) return value.result;
      const progress=JSON.stringify(value);
      if (progress!==previous) {
        previous=progress;
        onUpdate?.({content:[{type:'text',text:'正在等待本次执行结果'}],details:value});
      }
      await delay(intervalMs,undefined,{signal});
    }
  } catch (error) {
    if (signal?.aborted) throw error;
    try { await send('result',{...request,interrupted:true},signal); } catch { /* UNKNOWN stays durable. */ }
    return {...receipt,wait_interrupted:true,production_state:'unverified',
      message:'等待连接中断，不代表生产失败。原任务及UNKNOWN保留，不自动重发；不能声称任务完成或承诺远端自动核实。'};
  }
}
