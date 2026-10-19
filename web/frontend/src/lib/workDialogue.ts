import type { Work } from './productionApi';

/** A projection of durable business records, never an instruction to dispatch work. */
export function workDialogue(work: Work, referenceOnly = false) {
  const run = work.runs.find(r => r.id === work.active_run_id);
  const tasks = work.tasks.filter(t => t.run_id === run?.id);
  const blocked = tasks.find(t => ['needs_decision','failed','retryable_failed'].includes(t.state));
  const active = !!run && ['pending','running','waiting_external'].includes(run.state);
  let status = '';
  let reply = '';
  if (work.pending_operations?.some(o => o.state === 'unknown')) {
    status = '外部请求的结果仍待核实，当前不能重新派发。我会在这里显示核实后的状态。';
    reply = '请核实当前外部请求，说明已完成部分和下一步，不要重发。';
  } else if (blocked || (run && ['needs_decision','paused','failed'].includes(run.state))) {
    let reason = '当前步骤未完成，需要核实原因。';
    try { reason = JSON.parse(blocked?.error_json || '{}').user_message || reason; } catch { /* Missing diagnostics must not hide a blocked task. */ }
    status = `制作暂时停在这里：${reason}\n\n已有成果会保留。请直接在对话中讨论下一步；不会自动重做。`;
    reply = '请说明当前阻断、已经完成的部分，以及继续原任务需要我决定的具体事项。';
  } else if (active) {
    const task = tasks.find(t => ['running','waiting_external'].includes(t.state)) || tasks.find(t => t.state === 'pending');
    const names: Record<string,string> = {plan:'整理完整方案',analyze_director:'分析参考',supply:'准备素材',edit:'剪辑视频',render:'合成视频',quality:'检查成片',revise:'局部修订',voice_preview:'生成试听'};
    status = `正在${names[task?.kind || ''] || '处理已确认的任务'}。任务会在后台继续，完成结果或需要你决定的事项会自动显示在这段对话中，无需反复询问。`;
  } else if (run?.state === 'cancelled' || work.state === 'cancelled') {
    status = '后续制作已取消，已有成果仍保留。';
  }
  const plan = referenceOnly ? undefined : work.plans.find(p => p.revision === work.current_plan_revision);
  // A render artifact is not yet a delivery. Keep unfinished current-run outputs private
  // until checking finishes or the run stops with a reviewable failure.
  const outputs = referenceOnly ? [] : work.artifacts.filter(a => a.kind === 'output' && !(active && a.run_id === run?.id))
    .sort((a,b) => (b.output_revision || 0) - (a.output_revision || 0));
  return { status, reply, plan, outputs };
}
