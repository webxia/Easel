import { createRequire } from 'node:module';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { spawnSync } from 'node:child_process';
const fixtureDir = mkdtempSync(`${tmpdir()}/easel-workspace-fixture-`);
const fixtureVideo = `${fixtureDir}/preview.mp4`;
const encoded = spawnSync(process.env.FFMPEG_BIN || 'ffmpeg', ['-v', 'error', '-f', 'lavfi', '-i', 'color=c=0x778899:s=360x640:r=10:d=15', '-an', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', fixtureVideo]);
assert.equal(encoded.status, 0, encoded.stderr?.toString());
const videoBytes = readFileSync(fixtureVideo);
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const browser = await chromium.launch({ headless: true });
const base = process.env.WORKSPACE_FIXTURE_URL || 'http://127.0.0.1:5199/tests/workspace-fixture.html';
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, locale: 'zh-CN', timezoneId: 'Asia/Shanghai' });
let scenario = 'proposal'; let disconnected = false; const mutations = []; let feedback = []; let revisionStarted = false; const outputHash = 'sha256:' + 'a'.repeat(64);
await page.route('**/api/**', async route => {
  const request = route.request(); const rawPath = new URL(request.url()).pathname; const path = rawPath.slice(rawPath.indexOf('/api/'));
  if (request.method() !== 'GET' && path !== '/api/operator/session' && !path.endsWith('/proposal-preview')) mutations.push(path);
  if (disconnected && path.includes('creations/')) return route.abort();
  if (path.startsWith('/api/media/')) return route.fulfill({ contentType: 'video/mp4', body: videoBytes });
  if (path.endsWith('/preview')) return route.fulfill({ contentType: 'image/png', body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j9WQAAAAASUVORK5CYII=', 'base64') });
  let result = {};
  const proposal = scenario === 'proposal';
  const attempt = { attempt_id: 'fixture-attempt', authoring_status: scenario === 'failed' ? 'AUTHORING_FAILED' : 'AUTHORING_RUNNING',
    execution_status: 'NOT_SUBMITTED', material_planning: { status: 'PLANNING_READY' }, material_gate: { status: 'MATERIAL_READY' },
    updated_at: '2026-09-30T10:00:00Z', last_error: { message: '镜头时长与已确认时长不一致' } };
  if (scenario === 'material') { attempt.authoring_status = 'PENDING'; attempt.material_gate = { status: 'MATERIAL_NOT_READY', blocking_needs: ['scene-1', 'scene-2'] }; }
  if (scenario === 'cost') { attempt.authoring_status = 'AUTHORING_READY'; attempt.plan = { status: 'ready' }; attempt.cost = { status: 'pricing_read', estimated_usd: 0.8 }; }
  if (scenario === 'review') { attempt.execution_status = 'BUILD_COMPLETE'; attempt.authoring_status = 'AUTHORING_READY'; attempt.outputs = { final: { path: 'fixture-final.mp4', sha256: outputHash, technical_qc: { status: 'pass' }, metadata: { duration_seconds: 15 } } }; attempt.review = { feedback }; }
  if (path === '/api/operator/session') result = { authenticated: true };
  else if (path === '/api/upload/limits') result = { max_mb: 50 };
  else if (path === '/api/creations/fixture-creation') result = { id: 'fixture-creation', idea: '雨后城市的平静', creative_mode: '观察式短片', chat_workflow: { proposal_status: proposal ? 'READY_FOR_CONFIRMATION' : 'CONFIRMED' },
    preparation: scenario === 'early-failure' ? { status: 'FAILED', last_error: '内容节拍合计与总时长不一致' } : {} };
  else if (path.endsWith('/proposal-preview')) result = { specs: { duration_seconds: 15, aspect_ratio: '9:16', audio_mode: 'silent', language: 'zh-CN' }, missing: [] };
  else if (path.endsWith('/film-attempts')) result = proposal || scenario === 'early-failure' ? [] : revisionStarted ? [{ ...attempt, attempt_id: 'fixture-revision', outputs: {}, authoring_status: 'AUTHORING_RUNNING', execution_status: 'NOT_SUBMITTED' }, attempt] : [attempt];
  else if (path === '/api/film-attempts/fixture-attempt') result = attempt;
  else if (path.endsWith('/material-rights/candidates')) result = [];
  else if (path.endsWith('/material-rights/review-candidates')) result = [{ asset_id: 'image-1', asset_sha256: 'b'.repeat(64), media_type: 'image', provider: 'fixture', source_page: 'https://example.com/photo', creator: '示例摄影师', rights: { status: 'UNKNOWN' }, semantic_reviewed_need_ids: [], needs: [{ need_id: 'scene-1', description: '雨后的街道', constraints: { logo: false } }, { need_id: 'scene-2', description: '湿润的路面', constraints: { text_in_frame: false } }] }];
  else if (path.endsWith('/revise')) { assert.equal(request.postDataJSON().sha256, outputHash); revisionStarted = true; result = { ...attempt, attempt_id: 'fixture-revision', outputs: {}, authoring_status: 'READY_FOR_EXTERNAL_AUTHORING', execution_status: 'NOT_SUBMITTED' }; }
  else if (path === '/api/film-attempts/fixture-revision' || path === '/api/film-attempts/fixture-revision/author') result = { ...attempt, attempt_id: 'fixture-revision', outputs: {}, authoring_status: 'AUTHORING_RUNNING', execution_status: 'NOT_SUBMITTED' };
  else if (path.endsWith('/review')) { const body = request.postDataJSON(); assert.equal(body.sha256, outputHash); assert.equal(body.feedback[0].time_seconds, 2); feedback = body.feedback; result = { ...attempt, review: { feedback } }; }
  else if (path.endsWith('/script-truth')) result = { status: 'PASSED', claims: [] };
  else return route.abort();
  await route.fulfill({ json: result });
});
const errors = []; page.on('pageerror', error => errors.push(error.message));
try {
  for (const state of ['proposal', 'early-failure', 'failed', 'material', 'cost', 'review', 'running']) {
    scenario = state; revisionStarted = false;
    await page.goto(`${base}?scenario=${state}`);
    const canvas = page.getByRole('complementary', { name: '作品画布' });
    await canvas.waitFor();
    await page.getByText('做一支雨后城市短片，15 秒，9:16，静音，简体中文。', { exact: true }).waitFor();
    if (state === 'proposal') await page.getByRole('button', { name: '按这个方案制作' }).waitFor();
    if (state === 'early-failure') await page.getByRole('button', { name: '重试内容准备' }).waitFor();
    if (state === 'material') await page.getByText('核对画面是否真的符合场景', { exact: true }).waitFor();
    if (state === 'cost') await page.getByRole('button', { name: '同意本次费用并制作' }).waitFor();
    if (state === 'review') {
      await page.getByRole('button', { name: '提出修改' }).click();
      await page.getByLabel('修改类型').selectOption('composition');
      await page.locator('.film-op-creator video').evaluate(video => video.readyState >= 1 ? undefined : new Promise(resolve => video.addEventListener('loadedmetadata', resolve, { once: true })));
      assert.equal(await page.locator('.film-op-creator video').evaluate(video => video.duration), 15);
      await page.getByLabel('希望调整什么').fill('开头构图更紧凑');
      await page.getByLabel('时间点（可选，秒）').fill('2');
      await page.getByRole('button', { name: '保存反馈，退回审片' }).click();
      await page.getByText('2 秒：开头构图更紧凑', { exact: true }).waitFor();
    }
    if (state === 'failed') await page.getByRole('button', { name: '重试视频编排' }).waitFor();
    const dimensions = await page.evaluate(() => {
      const chat = document.querySelector('.creator-conversation').getBoundingClientRect();
      const canvas = document.querySelector('.creator-work-canvas').getBoundingClientRect();
      const composer = document.querySelector('.chat-input-area').getBoundingClientRect();
      return { separated: chat.right <= canvas.left + 1, composerFits: composer.bottom <= innerHeight + 1, overflow: document.documentElement.scrollWidth > innerWidth };
    });
    assert.ok(dimensions.separated && dimensions.composerFits && !dimensions.overflow, JSON.stringify(dimensions));
    await page.getByRole('button', { name: '查看制作进度' }).click();
    await canvas.getByLabel('创作阶段进度').waitFor();
    await page.setViewportSize({ width: 390, height: 844 });
    await page.getByRole('button', { name: /^对话$/ }).click();
    assert.equal(await canvas.isVisible(), false);
    await page.getByRole('button', { name: /^作品/ }).click();
    assert.equal(await canvas.isVisible(), true);
    assert.equal(await page.locator('.creator-conversation').isVisible(), false);
    await page.screenshot({ path: `/tmp/easel-workspace-${state}-mobile.png` });
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.waitForTimeout(300);

    await page.screenshot({ path: `/tmp/easel-workspace-${state}-desktop.png` });
    if (state === 'review') {
      await page.getByRole('button', { name: '按反馈调整构图与转场' }).click();
      await page.getByText('按反馈调整构图与转场完成', { exact: true }).waitFor();
    }
  }
  disconnected = true;
  await page.waitForTimeout(5500);
  await page.getByText('状态更新失败，显示最后一次可信状态。当前是否仍在制作尚未确认。').waitFor();
  assert.deepEqual(mutations, ['/api/film-attempts/fixture-attempt/review', '/api/film-attempts/fixture-attempt/revise', '/api/film-attempts/fixture-revision/author']);
  assert.deepEqual(errors, []);
  console.log('Workspace browser checks passed: desktop/mobile, proposal, no-attempt failure, authoring failure, material tasks, cost, output-bound timed feedback, running, disconnection; no build or Provider mutations.');
} finally { await browser.close(); rmSync(fixtureDir, { recursive: true, force: true }); }
