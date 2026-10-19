// Native OpenClaw integration. No production orchestration or provider credentials.
import { createHash } from 'node:crypto';

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


export const persistentToolDefinitions = [...toolDefinitions,
  {name:'easel_pipeline',description:'Easel pipeline pending/answer/resume adapter. pending reads real choices, proposals, plans and progress. bind queues a user-selected pipeline/target until this turn ends (then stop). draft creates a local draft from explicit user intent. offer stages an exact operation and user-visible summary; answer applies a previously shown proposal using this turn user_quote. Never infer authorization from praise; ask if unclear. No arbitrary commands.',parameters:{type:'object',properties:{mode:{type:'string',enum:['pending','bind','draft','offer','answer']},action:{type:'string',enum:['plan','confirm','grant','resume','cancel','basis','revise','confirm_revision','accept','director_style','director_accept','channel_director']},values:{type:'object'},summary:{type:'string'},user_quote:{type:'string'},proposal_id:{type:'string'},hash:{type:'string'},dismiss:{type:'boolean'}},required:['mode'],additionalProperties:false}},
  { name:'easel_work_input_evidence', description:'Read scoped input metadata. Media is unanalysed unless actual analysis evidence exists.', parameters:{type:'object',properties:{input_ids:{type:'array',items:{type:'string'},maxItems:100}},additionalProperties:false} },
  { name:'easel_work_register_inputs', description:'Register a current turn upload handle as reference or must-use. Does not grant rights or original audio permission.', parameters:{type:'object',properties:{attachment_id:{type:'string'},usage:{type:'string',enum:['reference','must_use']}},required:['attachment_id'],additionalProperties:false} },
  { name:'easel_work_update_brief', description:'Save sourced discussion. user_requirement must quote visible user text verbatim; summaries are suggestions. No production.', parameters:{type:'object',properties:{entries:{type:'array',minItems:1,maxItems:100,items:{type:'object',properties:{kind:{type:'string',enum:['user_requirement','suggestion','unresolved']},text:{type:'string'},source_refs:{type:'array',items:{type:'string'}}},required:['kind','text','source_refs'],additionalProperties:false}}},required:['entries'],additionalProperties:false} },
  { name:'easel_work_request_revision', description:'Propose revision of the selected output only. User answers the proposal in conversation before any work is scheduled.', parameters:{type:'object',properties:{feedback:{type:'string',minLength:1,maxLength:10000},protected:{type:'array',items:{type:'string'}},interval:{type:['object','null']}},required:['feedback'],additionalProperties:false} },
  { name:'easel_work_propose', description:'Propose channel creation/defaults, director formation/style or 1–3 reusable Profile preferences. Candidate only; never saves targets. Bind sources to visible user turn refs.', parameters:{type:'object',properties:{kind:{type:'string',enum:['channel_create','channel_defaults','director_formation','profile','director_revision']},values:{type:'object',description:'director_revision: ONLY style and base_revision; omit name and base_director_id because selected director identity comes from the server. director_formation: name, reference_input_ids and optional analysis_scope.',properties:{name:{type:'string'},analysis_scope:{type:'string',enum:['full','visual'],description:'full observes reference audio and images; visual explicitly observes images/story only, reference audio remains unanalysed.'},reference_input_ids:{type:'array',minItems:1,uniqueItems:true,items:{type:'string'}},creative_basis:{type:'object',properties:{position:{type:'string'},themes:{type:'string'},audience:{type:'string'}},additionalProperties:false},settings:{type:'object'},base_director_id:{type:'string'},base_revision:{type:'integer'},style:{type:'object',properties:{schema_version:{type:'integer',enum:[1]},visual_style:{type:'string'},storytelling:{type:'string'},rhythm:{type:'string'},sound:{type:'string'},typography:{type:'string'},invariants:{type:'array',items:{type:'string'}},freedom:{type:'array',items:{type:'string'}},evidence_notes:{type:'array',items:{type:'string'}}},additionalProperties:false},file:{type:'string',enum:['style','preferences','memory']},before_hash:{type:'string'},after:{type:'string'},entries:{type:'array',items:{type:'string'}}},additionalProperties:false},source_refs:{type:'array',minItems:1,items:{type:'string'}}},required:['kind','values','source_refs'],additionalProperties:false} },
];

export function createWorkBridge(api) {
  const { baseUrl, token, agentId = 'easel-video', protocolVersion = 1 } = api.pluginConfig ?? {};
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
      res.end(JSON.stringify({ protocol: protocolVersion, agent_id: agentId, tools: definitions.map(t => t.name) }));
    },
  });
  const scope = createHash('sha256').update(JSON.stringify([baseUrl, agentId, protocolVersion, token])).digest('hex');
  const calls = registries.get(scope) ?? new Map();
  registries.set(scope, calls);
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
      const hint = ['invalid_input','invalid_source','work_not_bound'].includes(code) ? result?.error?.user_message : undefined;
      throw new Error(code + (typeof hint === 'string' ? ': ' + hint : ''));
    }
    return result;
  }
  api.on('before_agent_run', async (event, ctx) => {
    if (ctx.agentId !== agentId) return;
    try {
      await send('claim', { ...identity(ctx, event), prompt: event.prompt });
    } catch {
      return { outcome: 'block', reason: 'easel_work_binding_unavailable', message: '作品会话未就绪，本轮未调用模型或制作服务。' };
    }
  });
  api.on('before_tool_call', async (event, ctx) => {
    if (ctx.agentId !== agentId) return;
    if (!names.has(event.toolName)) return { block: true, blockReason: 'easel_work_tool_not_allowed' };
    try {
      const result = await send('prepare', { ...identity(ctx, event), tool_call_id: event.toolCallId ?? ctx.toolCallId, tool: event.toolName, params: event.params }, ctx.abortSignal);
      calls.set(key(ctx, event.toolCallId ?? ctx.toolCallId, event.toolName), { ...identity(ctx, event), ticket: result.ticket });
    } catch {
      return { block: true, blockReason: 'easel_work_tool_binding_rejected' };
    }
  });
  api.on('agent_end', async (event, ctx) => {
    if (ctx.agentId !== agentId) return;
    const bound = identity(ctx, event);
    for (const [id, call] of calls) if (call.run_id === bound.run_id) calls.delete(id);
    // If delivery fails the reservation remains occupied. Never release it on a guessed timeout.
    await send('end', bound);
  });
  api.registerTool(ctx => {
    if (ctx.agentId !== agentId) return null;
    return definitions.map(definition => ({
      ...definition, label: definition.name,
      async execute(toolCallId, params, signal) {
        const call = calls.get(key(ctx, toolCallId, definition.name));
        if (!call) throw new Error('easel_work_missing_native_call_binding');
        try {
          const details = await send('dispatch', { ...call, tool_call_id: toolCallId, tool: definition.name, params }, signal);
          return { content: [{ type: 'text', text: JSON.stringify(details) }], details };
        } finally { calls.delete(key(ctx, toolCallId, definition.name)); }
      },
    }));
  }, { names: [...names] });
}
