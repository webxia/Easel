// Passive native-run metadata. Never persist prompts, reasoning, tool args or credentials.
import { createHash } from 'node:crypto';
const label = x => typeof x === 'string' && /^[A-Za-z0-9_.:/-]{1,128}$/.test(x) && !/^(sk-|Bearer)/i.test(x) ? x : undefined;
const number = x => typeof x === 'number' && Number.isFinite(x) && x >= 0 ? x : undefined;
export function configuredParameters(config, agentId, provider, model) {
  const defaults = config?.agents?.defaults ?? {};
  const entries = config?.agents?.list ?? config?.agents?.entries ?? [];
  const agent = Array.isArray(entries) ? entries.find(a => a.id === agentId) : entries[agentId];
  const ref = `${provider}/${model}`;
  const params = {...defaults.params, ...defaults.models?.[ref]?.params,
    ...agent?.models?.[ref]?.params, ...agent?.params};
  const extra = params.extra_body ?? params.extraBody ?? {};
  const definition = config?.models?.providers?.[provider]?.models?.find(m => m.id === model);
  const effort = extra.reasoning_effort ?? params.reasoningEffort;
  return {
    parameter_source: 'configured_not_wire', provider:label(provider), model:label(model),
    max_tokens: number(params.maxTokens ?? params.max_tokens ?? params.max_completion_tokens),
    model_max_tokens: number(definition?.maxTokens),
    reasoning_effort: ['off','none','low','medium','high','xhigh','max','adaptive'].includes(effort) ? effort : undefined,
    thinking: ['adaptive','disabled'].includes(extra.thinking?.type) ? extra.thinking.type : undefined,
  };
}
export function outputDiagnostic(message = {}, usage) {
  const blocks = Array.isArray(message.content) ? message.content : [];
  const count = (type, key) => blocks.filter(b => b.type === type).reduce((n,b) => n + (typeof b[key] === 'string' ? b[key].length : 0), 0);
  const rawUsage = usage ?? message.usage;
  const safeUsage = Object.fromEntries(['input','output','cacheRead','cacheWrite','total'].filter(k => number(rawUsage?.[k]) !== undefined).map(k => [k,rawUsage[k]]));
  const stop = ['stop','length','toolUse','error','aborted'].includes(message.stopReason) ? message.stopReason : undefined;
  const raw = ['stop','length','tool_calls','function_call','content_filter'].includes(message.easelProviderFinishReason) ? message.easelProviderFinishReason : undefined;
  return {stop_reason: stop, provider_finish_reason: raw,
    response_id_hash: typeof message.responseId === 'string' ? createHash('sha256').update(message.responseId).digest('hex') : undefined,
    text_chars: typeof message.content === 'string' ? message.content.length : count('text','text'),
    reasoning_chars: count('thinking','thinking'), tool_calls: blocks.filter(b => b.type === 'toolCall').length,
    usage: safeUsage,
    // OpenClaw initializes missing usage to zero. Never mistake those zeros for evidence.
    usage_status: Object.values(safeUsage).some(x => x > 0) ? 'reported' : 'missing_or_zero',
  };
}
export function installDiagnostics(api, agentId, selected = ctx => ctx.agentId === agentId) {
  const runs = new Map();
  const record = (event,ctx) => {
    if (!selected(ctx)) return;
    const id = ctx.runId ?? event.runId;
    if (!id) return;
    if (!runs.has(id)) runs.set(id,{calls:[]});
    return runs.get(id);
  };
  api.on('llm_input', (event,ctx) => {
    const r = record(event,ctx); if (!r) return;
    Object.assign(r,configuredParameters(api.config,agentId,event.provider,event.model));
  });
  api.on('model_call_ended', (event,ctx) => {
    const r = record(event,ctx); if (!r) return;
    r.calls.push({duration_ms:number(event.durationMs), request_bytes:number(event.requestPayloadBytes),
      response_bytes:number(event.responseStreamBytes), outcome:['completed','error'].includes(event.outcome) ? event.outcome : undefined});
    r.calls = r.calls.slice(-8);
  });
  api.on('llm_output', (event,ctx) => {
    const r = record(event,ctx); if (r) Object.assign(r,outputDiagnostic(event.lastAssistant,event.usage));
  });
  return (event,ctx) => {
    const id = ctx.runId ?? event.runId;
    const r = runs.get(id) ?? {calls:[]}; runs.delete(id);
    const last = [...(Array.isArray(event.messages) ? event.messages : [])].reverse().find(m => m?.role === 'assistant');
    if (last) Object.assign(r,outputDiagnostic(last));
    r.duration_ms=number(event.durationMs);
    return r;
  };
}
