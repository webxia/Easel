// Read-only product projection. It never authorizes or starts production.
export type Snapshot = Record<string, unknown>;
export const asRecord = (value: unknown): Snapshot => value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Snapshot : {};
export type StageState = 'waiting' | 'running' | 'action-required' | 'failed' | 'completed';
export const stageLabels: Record<StageState, string> = { waiting: '等待', running: '进行中', 'action-required': '需处理', failed: '失败', completed: '完成' };

export function creatorExecutionRecord(creation: Snapshot | null) {
  const work = creation ?? {};
  const delivery = asRecord(work.delivery);
  const timestamp = (value: unknown) => typeof value === 'number' ? value : typeof value === 'string' ? Date.parse(value) : NaN;
  const elapsed = (start: number, end: number) => {
    if (!Number.isFinite(start) || !Number.isFinite(end) || end < start) return '';
    const seconds = Math.floor((end - start) / 1000);
    return seconds < 60 ? `${seconds} 秒` : `${Math.floor(seconds / 60)} 分 ${seconds % 60} 秒`;
  };
  const entries: { at: number; message: string }[] = [];
  const confirmed = timestamp(delivery.confirmed_at);
  if (Number.isFinite(confirmed)) entries.push({ at: confirmed, message: '委托已确认，开始自主制作' });
  const calls = Object.values(asRecord(delivery.agent_calls)).map(asRecord)
    .filter(call => Number.isFinite(timestamp(call.created_at)))
    .sort((a, b) => timestamp(a.created_at) - timestamp(b.created_at));
  const pending: { label: string; elapsed: string; checkedAt: number }[] = [];
  calls.forEach((call, index) => {
    const start = timestamp(call.created_at);
    const label = `创作任务 ${index + 1}`;
    entries.push({ at: start, message: `${label}已登记${call.status === 'submitting' ? '，提交结果待核实' : ''}` });
    const end = timestamp(call.ended_at);
    if (['ok', 'error'].includes(String(call.status)) && Number.isFinite(end)) {
      entries.push({ at: end, message: `${label}${call.status === 'ok' ? '执行完成，后续仍需阶段校验' : '执行失败，保留已有结果'}（耗时 ${elapsed(start, end)}）` });
    } else if (['pending', 'submitting'].includes(String(call.status))) {
      const checkedAt = timestamp(call.observed_at);
      pending.push({ label, elapsed: elapsed(start, timestamp(work.updated_at)), checkedAt });
    }
  });
  // Only stable lifecycle transitions are history. A polling timestamp is not
  // a new production event, and raw model text/prompts never enter this view.
  const states: Record<string, string> = { planning: '进入内容准备与创作规划', producing: '进入视频制作', ready: '作品已就绪', failed: '制作遇到问题' };
  if (Array.isArray(work.history)) for (const item of work.history) {
    const row = asRecord(item);
    const at = timestamp(row.at);
    if (row.event === 'video_lifecycle_status_projected' && states[String(row.to)] && Number.isFinite(at)) {
      entries.push({ at, message: states[String(row.to)] });
    }
  }
  return { entries: entries.sort((a, b) => a.at - b.at).slice(-60), pending };
}
export function projectCreatorWorkspace(creation: Snapshot | null, attempt: Snapshot | null, truth: Snapshot | null, candidates: Snapshot[] = []) {
  const work = creation ?? {};
  const item = attempt ?? {};
  const preparation = asRecord(work.preparation);
  const workflow = asRecord(work.chat_workflow);
  const delivery = asRecord(work.delivery);
  const managed = delivery.schema === 'easel-creation-delivery@1';
  const repairing = managed && delivery.status !== 'failed';
  const planning = asRecord(item.material_planning);
  const gate = asRecord(item.material_gate);
  const plan = asRecord(item.plan);
  const cost = asRecord(item.cost);
  const execution = item.execution_status;
  const selected = !!attempt && work.selected_attempt_id === item.attempt_id && !!work.selected_output_name;
  const output = Object.keys(asRecord(item.outputs)).length > 0;
  const qualityPending = managed && output && !selected && delivery.status !== 'first_cut_ready';
  const proposal = workflow.proposal_status !== 'CONFIRMED' && !attempt && (!preparation.status || preparation.status === 'CREATED');
  const contentFailed = !repairing && !planning.status && !output && !selected && preparation.status === 'FAILED';
  const preparationFailed = !repairing && !output && !selected && gate.status !== 'MATERIAL_READY' && preparation.status === 'MATERIAL_FAILED';
  const planningFailed = ['FAILED', 'PLANNING_FAILED'].includes(String(planning.status)) || (preparationFailed && (preparation.failure_stage === 'planning' || (!preparation.failure_stage && !planning.status)));
  const materialFailed = preparationFailed && !planningFailed;
  const contentReady = !!preparation.handoff_id || !!preparation.snapshot_hashes;
  const productionFailed = (execution === 'BUILD_FAILED' && (!managed || ['failed', 'production_failed'].includes(String(delivery.status))))
    || (!repairing && ['AUTHORING_FAILED', 'PLAN_FAILED'].includes(String(item.authoring_status)));
  const claims = Array.isArray(truth?.claims) ? truth.claims.map(asRecord) : [];
  const facts = claims.filter(claim => claim.status === 'REVIEW_REQUIRED').length;
  const blockingIds = Array.isArray(gate.blocking_needs) ? gate.blocking_needs : [];
  const needs = blockingIds.length;
  const materialWorking = managed && gate.status === 'MATERIAL_NOT_READY'
    && ['observing_material', 'recovering_material', 'generating_material', 'observing_execution', 'execution_uncertain', 'observation_failed', 'retrying'].includes(String(delivery.status));
  const rightsTasks = candidates.filter(asset => ['UNKNOWN', 'RESTRICTED'].includes(String(asRecord(asset.rights).status))
    && Array.isArray(asset.needs) && asset.needs.some(need => blockingIds.includes(asRecord(need).need_id))).length;
  const materialTasks = materialWorking ? 0 : Math.max(needs, rightsTasks + blockingIds.filter(needId => !candidates.some(asset => Array.isArray(asset.semantic_reviewed_need_ids) && asset.semantic_reviewed_need_ids.includes(needId)) && candidates.some(asset =>
    ['image', 'video'].includes(String(asset.media_type)) && Array.isArray(asset.needs)
    && asset.needs.some(need => asRecord(need).need_id === needId)
    && !(Array.isArray(asset.semantic_reviewed_need_ids) && asset.semantic_reviewed_need_ids.includes(needId)))).length);
  const fee = plan.status === 'ready' && cost.status === 'pricing_read' && cost.approved !== true && execution === 'NOT_SUBMITTED'
    && (!managed || delivery.status === 'needs_cost_approval');
  const blockedPreparation = !attempt && ['MATERIAL_NOT_READY', 'BLOCKED_CREATIVE_MODE_REQUIRED', 'BLOCKED_RUNTIME_INVALID', 'BLOCKED_RUNTIME_NOT_CONFIGURED'].includes(String(preparation.status));
  const pending = selected ? 0 : proposal || blockedPreparation ? 1 : facts + materialTasks + (fee ? 1 : 0) + (output && !qualityPending ? 1 : 0);
  const failureStage = productionFailed ? '视频制作' : planningFailed ? '创作规划' : materialFailed ? '素材准备' : contentFailed ? '内容准备' : managed && delivery.status === 'failed' ? (/:(quality|repair_quality)$/.test(String(delivery.exhausted_operation)) ? '审片' : /:(observe_material|recover_material|finish_material_generation|generate_material|recover_voice_timing)$/.test(String(delivery.exhausted_operation)) ? '素材准备' : attempt ? '视频制作' : '内容准备') : null;
  const state: StageState = selected ? 'completed' : failureStage ? 'failed' : pending ? 'action-required' : proposal ? 'waiting' : 'running';
  const timeline: { name: string; state: StageState }[] = [
    { name: '方案', state: proposal ? 'action-required' : 'completed' },
    { name: '内容准备', state: contentFailed ? 'failed' : facts ? 'action-required' : contentReady || planning.status || output || selected ? 'completed' : proposal ? 'waiting' : 'running' },
    { name: '创作规划', state: planningFailed ? 'failed' : planning.status === 'PLANNING_READY' || output || selected ? 'completed' : planning.status || preparation.active_stage === 'planning' ? 'running' : 'waiting' },
    { name: '素材准备', state: materialFailed || failureStage === '素材准备' ? 'failed' : gate.status === 'MATERIAL_READY' || output || selected ? 'completed' : materialWorking ? 'running' : needs ? 'action-required' : planning.status === 'PLANNING_READY' ? 'running' : 'waiting' },
    { name: '视频制作', state: productionFailed ? 'failed' : output || selected ? 'completed' : fee ? 'action-required' : gate.status === 'MATERIAL_READY' ? 'running' : 'waiting' },
    { name: '审片', state: selected ? 'completed' : failureStage === '审片' ? 'failed' : qualityPending ? ['checking_quality', 'repairing_quality'].includes(String(delivery.status)) ? 'running' : 'waiting' : output ? 'action-required' : 'waiting' },
    { name: '成片', state: selected ? 'completed' : 'waiting' },
  ];
  const reason = delivery.last_error ?? asRecord(item.last_error).message ?? preparation.last_error ?? preparation.error;
  const rawReason = typeof reason === 'string' ? reason : typeof asRecord(reason).message === 'string' ? String(asRecord(reason).message) : '当前阶段未完成，已保留最后可信结果。';
  return { proposal, selected, pending, state, timeline, failureStage, blockedPreparation, materialWorking,
    failureReason: rawReason.includes('content.trim is outside') ? '镜头截取超出了原素材时长。已保留原成片、内容和素材；恢复会先修正该镜头截取并核验，重新合成仍需核价与批准。' : rawReason.startsWith('Creative Planning MaterialPlan Domain validation failed:') ? '创作规划的素材需求格式未通过核验。已保留内容与方案，重试会修正规划格式后重新核验。' : rawReason.startsWith('Hypit check 失败：') ? '视频编排文件未通过格式核验。已保留内容和素材，重试会修正编排并重新核验；通过后仍需核价与批准才能合成。' : rawReason,
    updatedAt: delivery.updated_at ?? item.updated_at ?? preparation.updated_at ?? work.updated_at,
    title: managed && delivery.status === 'observation_failed' ? '状态连接中断 · 显示最后可信结果' :
      managed && delivery.status === 'execution_uncertain' ? '执行结果待核实' :
      selected ? '最终成片已确认' : failureStage ? `${failureStage}遇到问题` : pending ? '需要你处理' : proposal ? '创作方案' :
      managed && delivery.status === 'checking_quality' ? '正在检查成片画面与声音' :
      managed && delivery.status === 'repairing_quality' ? '正在修正系统审片发现的局部问题' :
      managed && delivery.status === 'quality_repair_required' ? '系统审片发现待修正问题，成片已保留' :
      managed && delivery.status === 'quality_incomplete' ? '系统审片证据尚不完整，成片已保留' :
      managed && delivery.status === 'reconciling' ? '正在核对制作结果' : managed && delivery.status === 'producing' ? '正在合成视频' :
      managed && delivery.status === 'observing_execution' ? (preparation.active_stage === 'planning' && planning.status !== 'PLANNING_READY' ? '正在创作规划 · 等待当前任务完成' : !preparation.handoff_id ? '正在准备内容 · 等待当前任务完成' : '正在等待创作任务完成') :
      managed && delivery.status === 'generating_material' ? '正在委托预算内生成所需素材' :
      managed && delivery.status === 'observing_material' ? '正在按场景核对候选素材的实际画面' :
      managed && delivery.status === 'recovering_material' ? (delivery.operation === 'recover_voice_timing' ? '正在核对旁白是否完整，并补齐必要的字幕时序' : delivery.operation === 'finish_material_generation' ? '正在检查已保存的生成素材，无需重新生成' : '正在按原方案补充缺失素材') :
      managed && delivery.status === 'recovering_production' ? '正在复用已完成的内容和素材，恢复视频制作' :
      managed && delivery.status === 'exporting' ? '正在整理成片' : managed && delivery.status === 'authoring' ? '正在编排画面与声音' :
      managed && delivery.status === 'retrying' ? '正在恢复当前步骤' : preparation.active_stage === 'planning' && planning.status !== 'PLANNING_READY' ? '正在创作规划' : '正在准备作品',
  };
}
