import test from 'node:test';
import assert from 'node:assert/strict';
import { createWorkBridge, toolDefinitions } from '../../agents/plugins/easel-work/tools.mjs';

function runtime(baseUrl = 'http://127.0.0.1:12345') {
  const hooks = new Map(); let factory; let route;
  createWorkBridge({
    pluginConfig: { baseUrl, token: 'test-only-credential-32-characters' },
    on(name, fn) { hooks.set(name, fn); },
    registerTool(fn) { factory = fn; },
    registerHttpRoute(value) { route = value; },
  });
  return { hooks, tools: ctx => factory(ctx), get route() { return route; } };
}
const ctx = { agentId:'easel-video', sessionKey:'agent:easel-video:one', sessionId:'native-one', runId:'run-one' };

test('plugin accepts only explicit loopback base; no arbitrary targets or redirects', () => {
  for (const url of ['https://provider.example', 'http://localhost:12345', 'http://127.0.0.1:12345/path', 'http://user:password@127.0.0.1:12345', 'http://127.0.0.1:12345?x=1']) {
    assert.throws(() => runtime(url));
  }
});

test('only three tools, strict business schemas; other agents receive none', () => {
  const r = runtime();
  assert.equal(r.tools({agentId:'main'}), null);
  assert.deepEqual(r.tools(ctx).map(t=>t.name), toolDefinitions.map(t=>t.name));
  for (const t of toolDefinitions) {
    assert.equal(t.parameters.additionalProperties, false);
    for (const name of ['command_id','work_id','turn_id','services','owner_epoch']) assert.equal(t.parameters.properties[name], undefined);
  }
  assert.equal(r.route.auth, 'gateway');
});

test('unavailable binding blocks before model; other agents are untouched', async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async () => { throw new Error('private failure'); };
  try {
    const r = runtime();
    const blocked = await r.hooks.get('before_agent_run')({prompt:'draft'},ctx);
    assert.equal(blocked.outcome,'block');
    assert.ok(!JSON.stringify(blocked).includes('private failure'));
    assert.equal(await r.hooks.get('before_agent_run')({prompt:'draft'}, {agentId:'main'}), undefined);
  } finally { globalThis.fetch = original; }
});

test('unknown tool blocked without forwarding; execute needs native hook association', async () => {
  const r = runtime();
  assert.equal((await r.hooks.get('before_tool_call')({toolName:'exec',toolCallId:'c'},ctx)).block,true);
  await assert.rejects(r.tools(ctx)[0].execute('missing',{}), /missing_native_call_binding/);
});

test('native identity, tool name and ticket forwarded separately from model params; close revokes calls', async () => {
  const original = globalThis.fetch; const requests = [];
  globalThis.fetch = async (url, options) => {
    requests.push({url, ...options, body:JSON.parse(options.body)});
    const data = url.endsWith('/prepare') ? {ticket:'ticket-owned-by-server-32-characters'} : {work_id:'bound-work'};
    return new Response(JSON.stringify(data), {status:200,headers:{'Content-Type':'application/json'}});
  };
  try {
    const r = runtime();
    const event = {toolName:'easel_work_context',toolCallId:'c1',params:{},runId:'untrusted-alternative'};
    await r.hooks.get('before_tool_call')(event,ctx);
    const result = await r.tools(ctx)[0].execute('c1',{});
    assert.equal(result.details.work_id,'bound-work');
    assert.equal(requests[1].body.run_id,'run-one');
    assert.equal(requests[1].body.session_key,ctx.sessionKey);
    assert.equal(requests[1].redirect,'error');
    assert.ok(!JSON.stringify(result).includes('credential'));
    await r.hooks.get('before_tool_call')({...event,toolCallId:'late'},ctx);
    await r.hooks.get('agent_end')({},ctx);
    await assert.rejects(r.tools(ctx)[0].execute('late',{}), /missing_native_call_binding/);
  } finally { globalThis.fetch = original; }
});

test('protocol 2 exposes eight bounded tools and retains independent lifecycle gates', () => {
  let factory, route;
  createWorkBridge({pluginConfig:{baseUrl:'http://127.0.0.1:12345',token:'test-credential-long-enough-32',protocolVersion:2},on(){},registerTool(fn){factory=fn;},registerHttpRoute(value){route=value;}});
  const tools=factory(ctx);
  assert.equal(tools.length,8);
  for(const tool of tools) assert.equal(tool.parameters.additionalProperties,false);
  for(const name of ['exec','accept','grant','publish','write','sessions_spawn'])assert.ok(!tools.some(t=>t.name===name));
  let status;route.handler({method:'GET'},{setHeader(){},end(text){status=JSON.parse(text);}});
  assert.equal(status.protocol,2);
  assert.equal(status.tools.length,8);
});
