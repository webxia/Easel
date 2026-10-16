import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { runInNewContext } from 'node:vm';
import { test } from 'node:test';

const require = createRequire(new URL('../../web/frontend/package.json', import.meta.url));
const ts = require('typescript');
const source = readFileSync(new URL('../../web/frontend/src/lib/productionSettings.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } });
const api = {};
runInNewContext(outputText, { exports: api, structuredClone });
const plain = value => JSON.parse(JSON.stringify(value));
const voice = { provider: 'fixed', model: 'one', engine: 'http-speech', voice_id: 'a', parameters: { speed: 1 } };
const settings = { duration_seconds: 90, audio_mode: 'mixed', aspect_ratio: '9:16', voice, subtitles: { ...api.defaultSubtitles } };

test('scope precedence snapshots whole voice identities and partial subtitle settings', () => {
  const profile = { voice, subtitles: { ...api.defaultSubtitles, size: 40 } };
  const channel = { voice: { ...voice, provider: 'other', voice_id: 'b' }, subtitles: { size: 60 } };
  const result = api.resolveSettings(profile, channel, { subtitles: { position: 'top' } });
  assert.equal(result.voice.provider, 'other'); assert.equal(result.voice.voice_id, 'b');
  assert.equal(result.subtitles.size, 60); assert.equal(result.subtitles.position, 'top');
  channel.voice.voice_id = 'changed'; assert.equal(result.voice.voice_id, 'b');
  assert.equal(api.resolveSettings(profile, {}, { voice: null }).voice, null);
});

test('unavailable fixed voice never silently falls back and explicit selection preserves captions', () => {
  const original = structuredClone(settings);
  const options = [{ identity: voice, available: false }, { identity: { ...voice, voice_id: 'b' }, available: true }];
  assert.throws(() => api.chooseVoice(settings, options, api.voiceKey(voice)), /不可用/);
  assert.deepEqual(settings, original);
  const changed = api.chooseVoice(settings, options, api.voiceKey(options[1].identity));
  assert.equal(changed.voice.voice_id, 'b'); assert.deepEqual(plain(changed.subtitles), plain(settings.subtitles));
});

test('save request carries exactly the selected scope and does not mutate earlier settings', () => {
  assert.throws(() => api.saveSettingsPayload('channel', settings, { channel: false, profile: true }), /频道/);
  const saved = api.saveSettingsPayload('work', settings, { channel: false, profile: false });
  assert.equal(saved.scope, 'work'); saved.settings.subtitles.size = 99;
  assert.equal(settings.subtitles.size, 48);
});

test('component exposes explicit preview/save actions and audio/video without autoplay', () => {
  const ui = readFileSync(new URL('../../web/frontend/src/components/ProductionSettings.tsx', import.meta.url), 'utf8');
  assert.match(ui, /onPreview\('voice', settings, text\)/); assert.match(ui, /onPreview\('subtitles', settings, text\)/);
  assert.match(ui, /onSave\(payload.scope, payload.settings\)/); assert.match(ui, /<audio controls src=/);
  assert.doesNotMatch(ui, /autoPlay|useEffect.*onPreview/);
});
