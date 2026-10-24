import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { runInNewContext } from 'node:vm';
import { test } from 'node:test';
const require = createRequire(new URL('../../web/frontend/package.json', import.meta.url));
const ts = require('typescript');
const source = readFileSync(new URL('../../web/frontend/src/lib/store.ts', import.meta.url), 'utf8');
const parsed = ts.createSourceFile('store.ts', source, ts.ScriptTarget.Latest, true);
const fn = parsed.statements.find(n => ts.isFunctionDeclaration(n) && n.name.text === 'titleIntent');
const code = ts.transpileModule(fn.getText(parsed) + '\ntitleIntent;', {compilerOptions: {target: ts.ScriptTarget.ES2022}}).outputText;
const intent = runInNewContext(code);
test('negated publishing does not rename creation as publishing', () => {
  for (const text of ['制作视频，不要发布', '不要上传抖音，做一个视频', '先制作，暂不投稿', '不发布，只查看视频']) {
    assert.notEqual(intent(text), 'publish');
  }
  assert.equal(intent('发布视频到抖音'), 'publish');
  assert.equal(intent('不要发布到抖音，发布到B站'), 'publish');
});
