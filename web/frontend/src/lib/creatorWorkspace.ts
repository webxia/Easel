// Read-only product projection. It never authorizes or starts production.
export type Snapshot = Record<string, unknown>;
export const asRecord = (value: unknown): Snapshot => value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Snapshot : {};
export type StageState = 'waiting' | 'running' | 'action-required' | 'failed' | 'completed';
export const stageLabels: Record<StageState, string> = { waiting: '等待', running: '进行中', 'action-required': '需处理', failed: '失败', completed: '完成' };
export function projectCreatorWorkspace(creation: Snapshot | null, attempt: Snapshot | null, truth: Snapshot | null, candidates: Snapshot[] = []) {
  const work = creation ?? {};
  const item = attempt ?? {};
  const preparation = asRecord(work.preparation);
  const workflow = asRecord(work.chat_workflow);
  const planning = asRecord(item.material_planning);
  const gate = asRecord(item.material_gate);
  const plan = asRecord(item.plan);
  const cost = asRecord(item.cost);
  const execution = item.execution_status;
  const selected = !!attempt && work.selected_attempt_id === item.attempt_id && !!work.selected_output_name;
  const output = Object.keys(asRecord(item.outputs)).length > 0;
  const proposal = workflow.proposal_status !== 'CONFIRMED' && !attempt && (!preparation.status || preparation.status === 'CREATED');
  const contentFailed = !planning.status && !output && !selected && preparation.status === 'FAILED';
  const materialFailed = !output && !selected && gate.status !== 'MATERIAL_READY' && preparation.status === 'MATERIAL_FAILED';
  const planningFailed = ['FAILED', 'PLANNING_FAILED'].includes(String(planning.status));
  const productionFailed = execution === 'BUILD_FAILED' || ['AUTHORING_FAILED', 'PLAN_FAILED'].includes(String(item.authoring_status));
  const claims = Array.isArray(truth?.claims) ? truth.claims.map(asRecord) : [];
  const facts = claims.filter(claim => claim.status === 'REVIEW_REQUIRED').length;
  const blockingIds = Array.isArray(gate.blocking_needs) ? gate.blocking_needs : [];
  const needs = blockingIds.length;
  const rightsTasks = candidates.filter(asset => ['UNKNOWN', 'RESTRICTED'].includes(String(asRecord(asset.rights).status))
    && Array.isArray(asset.needs) && asset.needs.some(need => blockingIds.includes(asRecord(need).need_id))).length;
  const materialTasks = Math.max(needs, rightsTasks + blockingIds.filter(needId => !candidates.some(asset => Array.isArray(asset.semantic_reviewed_need_ids) && asset.semantic_reviewed_need_ids.includes(needId)) && candidates.some(asset =>
    ['image', 'video'].includes(String(asset.media_type)) && Array.isArray(asset.needs)
    && asset.needs.some(need => asRecord(need).need_id === needId)
    && !(Array.isArray(asset.semantic_reviewed_need_ids) && asset.semantic_reviewed_need_ids.includes(needId)))).length);
  const fee = plan.status === 'ready' && cost.status === 'pricing_read' && execution === 'NOT_SUBMITTED';
  const blockedPreparation = !attempt && ['MATERIAL_NOT_READY', 'BLOCKED_CREATIVE_MODE_REQUIRED', 'BLOCKED_RUNTIME_INVALID', 'BLOCKED_RUNTIME_NOT_CONFIGURED'].includes(String(preparation.status));
  const pending = selected ? 0 : proposal || blockedPreparation ? 1 : facts + materialTasks + (fee ? 1 : 0) + (output ? 1 : 0);
  const failureStage = productionFailed ? '视频制作' : planningFailed ? '创作规划' : materialFailed ? '素材准备' : contentFailed ? '内容准备' : null;
  const state: StageState = selected ? 'completed' : failureStage ? 'failed' : pending ? 'action-required' : proposal ? 'waiting' : 'running';
  const timeline: { name: string; state: StageState }[] = [
    { name: '方案', state: proposal ? 'action-required' : 'completed' },
    { name: '内容准备', state: contentFailed ? 'failed' : facts ? 'action-required' : planning.status || output || selected ? 'completed' : proposal ? 'waiting' : 'running' },
    { name: '创作规划', state: planningFailed ? 'failed' : planning.status === 'PLANNING_READY' || output || selected ? 'completed' : planning.status ? 'running' : 'waiting' },
    { name: '素材准备', state: materialFailed ? 'failed' : gate.status === 'MATERIAL_READY' || output || selected ? 'completed' : needs ? 'action-required' : planning.status === 'PLANNING_READY' ? 'running' : 'waiting' },
    { name: '视频制作', state: productionFailed ? 'failed' : output || selected ? 'completed' : fee ? 'action-required' : gate.status === 'MATERIAL_READY' ? 'running' : 'waiting' },
    { name: '审片', state: selected ? 'completed' : output ? 'action-required' : 'waiting' },
    { name: '成片', state: selected ? 'completed' : 'waiting' },
  ];
  const reason = asRecord(item.last_error).message ?? preparation.last_error ?? preparation.error;
  return { proposal, selected, pending, state, timeline, failureStage, blockedPreparation,
    failureReason: typeof reason === 'string' ? reason : typeof asRecord(reason).message === 'string' ? String(asRecord(reason).message) : '当前阶段未完成，已保留最后可信结果。',
    updatedAt: item.updated_at ?? preparation.updated_at ?? work.updated_at,
    title: selected ? '最终成片已确认' : failureStage ? `${failureStage}遇到问题` : pending ? '需要你处理' : proposal ? '创作方案' : '正在准备作品',
  };
}
