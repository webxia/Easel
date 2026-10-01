import assert from 'node:assert/strict';
import { creatorExecutionRecord, projectCreatorWorkspace as project } from '../src/lib/creatorWorkspace.ts';
const confirmed = { chat_workflow: { proposal_status: 'CONFIRMED' } };
const progressWork = { ...confirmed, updated_at: '2026-10-01T12:42:04Z',
  preparation: { status: 'HANDOFF_READY', handoff_id: 'h', active_stage: 'planning' },
  delivery: { schema: 'easel-creation-delivery@1', status: 'observing_execution',
    confirmed_at: '2026-10-01T12:37:14Z', proposal: 'private-prompt', agent_calls: {
      one: { status: 'ok', created_at: '2026-10-01T12:37:16Z', ended_at: Date.parse('2026-10-01T12:41:41Z'), rawText: 'private-prompt' },
      two: { status: 'pending', created_at: '2026-10-01T12:41:45Z', observed_at: '2026-10-01T12:42:04Z' },
      invalid: { status: 'ok', created_at: 'invalid', ended_at: 0 },
    } } };
const progress = creatorExecutionRecord(progressWork);
assert.equal(progress.entries.length, 4);
assert.match(progress.entries[2].message, /4 分 25 秒/);
assert.equal(progress.pending[0].elapsed, '19 秒');
assert.equal(progress.pending[0].checkedAt, Date.parse('2026-10-01T12:42:04Z'));
assert.ok(!JSON.stringify(progress).includes('private-prompt'));
assert.deepEqual(creatorExecutionRecord(null), { entries: [], pending: [] });
assert.match(project(progressWork, null, null).title, /正在创作规划/);
assert.match(project({ ...progressWork, delivery: { ...progressWork.delivery, status: 'observation_failed' } }, null, null).title, /连接中断/);
// More polls update the waiting observation, not the production event history.
const nextPoll = structuredClone(progressWork);
nextPoll.updated_at = nextPoll.delivery.agent_calls.two.observed_at = '2026-10-01T12:42:09Z';
assert.deepEqual(creatorExecutionRecord(nextPoll).entries, progress.entries);
const proposal = project({ chat_workflow: { proposal_status: 'READY_FOR_CONFIRMATION' } }, null, null);
assert.equal(proposal.title, '需要你处理');
assert.equal(proposal.proposal, true);
assert.equal(proposal.pending, 1);
const early = project({ ...confirmed, preparation: { status: 'FAILED', last_error: '内容时长不一致' } }, null, null);
assert.equal(early.failureStage, '内容准备');
assert.equal(early.failureReason, '内容时长不一致');
const selected = project({ ...confirmed, selected_attempt_id: 'a', selected_output_name: 'final', preparation: { status: 'FAILED' } }, { attempt_id: 'a', outputs: { final: {} }, review_status: 'APPROVED' }, null);
assert.equal(selected.state, 'completed');
assert.equal(selected.failureStage, null);
assert.ok(selected.timeline.every(stage => stage.state === 'completed'));
const waitingFee = project(confirmed, { attempt_id: 'a', execution_status: 'NOT_SUBMITTED', plan: { status: 'ready' }, cost: { status: 'pricing_read' }, material_gate: { status: 'MATERIAL_READY' }, material_planning: { status: 'PLANNING_READY' } }, null);
assert.equal(waitingFee.pending, 1);
assert.equal(waitingFee.timeline[4].state, 'action-required');
const uncertain = project(confirmed, { execution_status: 'SUBMISSION_UNCERTAIN', material_gate: { status: 'MATERIAL_READY' } }, null);
assert.equal(uncertain.failureStage, null);
const resumed = project({ ...confirmed, preparation: { status: 'FAILED' } }, { material_planning: { status: 'PLANNING_READY' }, material_gate: { status: 'MATERIAL_NOT_READY', blocking_needs: ['scene-1', 'scene-2'] } }, { claims: [{ status: 'REVIEW_REQUIRED' }] });
assert.equal(resumed.failureStage, null);
assert.equal(resumed.pending, 3);
assert.equal(resumed.timeline[1].state, 'action-required');
assert.equal(resumed.timeline[3].state, 'action-required');
for (const failure_stage of [undefined, 'planning']) {
  const failedPlanning = project({ ...confirmed, preparation: { status: 'MATERIAL_FAILED', handoff_id: 'h', failure_stage } }, {}, null);
  assert.equal(failedPlanning.failureStage, '创作规划');
  assert.equal(failedPlanning.timeline[1].state, 'completed');
  assert.equal(failedPlanning.timeline[2].state, 'failed');
  assert.equal(failedPlanning.timeline[3].state, 'waiting');
}
const failedAuthoring = project(confirmed, { authoring_status: 'AUTHORING_FAILED', last_error: { message: 'Hypit check 失败：time:Timeline does not accept duration.' } }, null);
assert.equal(failedAuthoring.failureStage, '视频制作');
assert.match(failedAuthoring.failureReason, /编排文件未通过格式核验/);
assert.ok(!failedAuthoring.failureReason.includes('Timeline'));
const delivery = { schema: 'easel-creation-delivery@1', status: 'checking_cost' };
const priced = { execution_status: 'NOT_SUBMITTED', plan: { status: 'ready' }, cost: { status: 'pricing_read' }, material_gate: { status: 'MATERIAL_READY' } };
assert.equal(project({ ...confirmed, delivery }, priced, null).pending, 0);
assert.equal(project({ ...confirmed, delivery: { ...delivery, status: 'needs_cost_approval' } }, priced, null).pending, 1);
const repairing = project({ ...confirmed, delivery: { ...delivery, status: 'retrying' } }, { authoring_status: 'AUTHORING_FAILED' }, null);
assert.equal(repairing.failureStage, null);
assert.equal(repairing.title, '正在恢复当前步骤');
const retryingBuild = project({ ...confirmed, delivery: { ...delivery, status: 'recovering_production' } }, { execution_status: 'BUILD_FAILED' }, null);
assert.equal(retryingBuild.failureStage, null);
assert.match(retryingBuild.title, /复用已完成的内容和素材/);
assert.equal(project({ ...confirmed, delivery: { ...delivery, status: 'production_failed' } }, { execution_status: 'BUILD_FAILED' }, null).failureStage, '视频制作');
const disconnected = project({ ...confirmed, delivery: { ...delivery, status: 'observation_failed' } }, { execution_status: 'RUNNING' }, null);
assert.equal(disconnected.failureStage, null);
assert.match(disconnected.title, /状态连接中断/);
console.log('Creator projection: proposal, early failure, selected output, cost, uncertain submission, resumed gates passed');

const observingMaterial = project({ ...confirmed, delivery: { ...delivery, status: 'observing_material' } },
  { material_planning: { status: 'PLANNING_READY' }, material_gate: { status: 'MATERIAL_NOT_READY', blocking_needs: ['scene-1'] } }, null);
assert.equal(observingMaterial.pending, 0);
assert.equal(observingMaterial.materialWorking, true);
assert.equal(observingMaterial.timeline[3].state, 'running');
assert.match(observingMaterial.title, /核对候选素材的实际画面/);
const supplementingMaterial = project({ ...confirmed, delivery: { ...delivery, status: 'recovering_material' } },
  { material_gate: { status: 'MATERIAL_NOT_READY', blocking_needs: ['scene-1'] } }, null);
assert.equal(supplementingMaterial.pending, 0);
assert.match(supplementingMaterial.title, /补充缺失素材/);
const observationFailure = project({ ...confirmed, delivery: { ...delivery, status: 'failed', exhausted_operation: 'a:observe_material' } },
  { material_gate: { status: 'MATERIAL_NOT_READY', blocking_needs: ['scene-1'] } }, null);
assert.equal(observationFailure.failureStage, '素材准备');
const localIntake = project({ ...confirmed, delivery: { ...delivery, status: 'recovering_material', operation: 'finish_material_generation' } },
  { material_gate: { status: 'MATERIAL_NOT_READY', blocking_needs: ['voice'] } }, null);
assert.equal(localIntake.pending, 0);
assert.match(localIntake.title, /已保存.*无需重新生成/);
assert.equal(project({ ...confirmed, delivery: { ...delivery, status: 'failed', exhausted_operation: 'a:finish_material_generation' } }, {}, null).failureStage, '素材准备');
const exported = { execution_status: 'BUILD_COMPLETE', outputs: { final: { sha256: 'fixture' } } };
const checkingQuality = project({ ...confirmed, delivery: { ...delivery, status: 'checking_quality' } }, exported, null);
assert.equal(checkingQuality.pending, 0);
assert.equal(checkingQuality.timeline[5].state, 'running');
assert.match(checkingQuality.title, /检查成片画面与声音/);
assert.equal(project({ ...confirmed, delivery: { ...delivery, status: 'first_cut_ready' } }, exported, null).pending, 1);
assert.match(project({ ...confirmed, delivery: { ...delivery, status: 'quality_incomplete' } }, exported, null).title, /证据尚不完整/);
const repairingQuality = project({ ...confirmed, delivery: { ...delivery, status: 'repairing_quality' } }, exported, null);
assert.equal(repairingQuality.pending, 0);
assert.equal(repairingQuality.timeline[5].state, 'running');
assert.match(repairingQuality.title, /正在修正系统审片/);
assert.equal(project({ ...confirmed, delivery: { ...delivery, status: 'failed', exhausted_operation: 'a:repair_quality' } }, exported, null).failureStage, '审片');
