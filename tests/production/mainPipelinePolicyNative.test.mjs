// Opt-in, installed policy implementation only. No Gateway, model, or user DB.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readdir} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
import {createWorkBridge,persistentToolDefinitions} from '../../agents/plugins/easel-work/tools.mjs';

test('installed OpenClaw filters coding plugin tools; bounded full admits them and preserves deny',
 {skip:!process.env.EASEL_OPENCLAW_DIST},async()=>{
  const dir=process.env.EASEL_OPENCLAW_DIST;
  const files=await readdir(dir);
  async function installed(prefix){
    const matches=files.filter(n=>n.startsWith(prefix+'-')&&n.endsWith('.mjs'));
    assert.equal(matches.length,1,'installed module must be unambiguous: '+prefix);
    return import(pathToFileURL(dir+'/'+matches[0]).href);
  }
  const {t:resolve}=await installed('conversation-capability-profile');
  const {r:policies,t:steps}=await installed('conversation-tool-policy-pipeline');
  const {t:apply}=await installed('tool-policy-pipeline');
  let factory;
  createWorkBridge({
    pluginConfig:{baseUrl:'http://127.0.0.1:12349',token:'offline-fixture-only-credential-123456',agentId:'main',protocolVersion:2},
    on(){},registerHook(){},registerHttpRoute(){},registerTool(fn){factory=fn;},
  });
  const names=persistentToolDefinitions.map(t=>t.name);
  function visible(profile,sessionKey){
    const config={agents:{entries:{main:{tools:{
      profile,allow:['read','exec',...names],deny:['exec','sessions_spawn'],
    }}}}};
    const capabilityProfile=resolve({config,agentId:'main',sessionKey,
      modelProvider:'fixture',modelId:'offline'});
    const tools=[{name:'read'},{name:'exec'},{name:'sessions_spawn'},
      ...factory({agentId:'main',sessionKey,sessionId:'fixture'})];
    return apply({tools,toolMeta:t=>names.includes(t.name)?{pluginId:'easel-work'}:undefined,
      warn(){},steps:steps({capabilityProfile,policies:policies({capabilityProfile})})
    }).map(t=>t.name);
  }
  assert.deepEqual(visible('coding','agent:main:fresh'),['read']);
  assert.deepEqual(visible('full','agent:main:fresh'),['read','easel_pipeline']);
  assert.deepEqual(new Set(visible('full','agent:main:easel-pipeline:fixture')),
    new Set(['read',...names]));
 });
