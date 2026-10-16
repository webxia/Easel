import type { Director, Work } from './productionApi';

export function selectableDirectorVersions(directors: Director[], trial: boolean) {
  return directors.filter(d => !d.archived).flatMap(d => d.versions
    .filter(v => v.accepted_at || (trial && v.style_confirmed))
    .map(version => ({ director: d, version })));
}

export function trialOutputs(work: Work | null, revisionId: string) {
  if (!work) return [];
  const plans = new Set(work.plans.filter(p => p.plan.director_revision_id === revisionId).map(p => p.revision));
  const runs = new Set(work.runs.filter(r => r.plan_revision && plans.has(r.plan_revision)).map(r => r.id));
  return work.artifacts.filter(a => a.kind === 'output' && a.quality_state === 'passed' && a.run_id && runs.has(a.run_id));
}
