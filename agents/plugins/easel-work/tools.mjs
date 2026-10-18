// Native OpenClaw integration. No production orchestration or provider credentials.
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
    name: 'easel_work_request_plan', description: 'Request formal planning for the bound work only when explicitly requested. Does not authorize paid services.',
    parameters: { type: 'object', properties: { request: { type: 'string', minLength: 1, maxLength: 100000 } }, required: ['request'], additionalProperties: false },
  },
];

export function createWorkBridge(api) {
  const { baseUrl, token, agentId = 'easel-video' } = api.pluginConfig ?? {};
  const url = new URL(baseUrl);
  if (url.protocol !== 'http:' || url.hostname !== '127.0.0.1' || !url.port || url.pathname !== '/' || url.search || url.hash || url.username || url.password || !token || token.length < 24) {
    throw new Error('Easel bridge requires an explicit loopback endpoint and service credential');
  }
  api.registerHttpRoute({
    path: '/plugins/easel-work/status', auth: 'gateway', match: 'exact',
    handler(req, res) {
      if (req.method !== 'GET') { res.statusCode = 405; res.end(); return; }
      res.setHeader('Content-Type', 'application/json');
      res.end(JSON.stringify({ protocol: 1, agent_id: agentId, tools: toolDefinitions.map(t => t.name) }));
    },
  });
  const calls = new Map();
  const names = new Set(toolDefinitions.map(t => t.name));
  const identity = (ctx, event = {}) => ({ agent_id: ctx.agentId, session_key: ctx.sessionKey, session_id: ctx.sessionId, run_id: ctx.runId ?? event.runId });
  const key = (ctx, id, name) => `${ctx.sessionKey}\0${ctx.sessionId}\0${name}\0${id}`;
  async function send(path, body, signal) {
    const response = await fetch(`${url.origin}/api/chat/work-tools/${path}`, {
      method: 'POST', redirect: 'error', signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(5000)]) : AbortSignal.timeout(5000),
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }, body: JSON.stringify(body),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result?.error?.code ?? 'work_bridge_unavailable');
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
    return toolDefinitions.map(definition => ({
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
