import type { Director, Work } from './productionApi';

export function selectableDirectorVersions(directors: Director[], trial: boolean) {
  return directors.filter(d => !d.archived).flatMap(d => d.versions
    .filter(v => v.accepted_at || (trial && v.style_confirmed))
    .map(version => ({ director: d, version })));
}

/** Choosing a confirmed draft starts a trial; it never accepts the director. */
export function directorEntrySelection(directors: Director[], revisionId: string) {
  if (!revisionId) return {};
  const selected = selectableDirectorVersions(directors, true).find(v => v.version.id === revisionId);
  if (!selected) throw new Error('所选导演版本尚未确认风格或已不可用，请重新选择');
  return { director_revision: revisionId, director_trial: !selected.version.accepted_at };
}

export function trialOutputs(work: Work | null, revisionId: string) {
  if (!work) return [];
  const plans = new Set(work.plans.filter(p => p.plan.director_revision_id === revisionId).map(p => p.revision));
  const runs = new Set(work.runs.filter(r => r.plan_revision && plans.has(r.plan_revision)).map(r => r.id));
  return work.artifacts.filter(a => a.kind === 'output' && (a.quality_state === 'passed' || a.manual_review_required) && a.run_id && runs.has(a.run_id));
}
