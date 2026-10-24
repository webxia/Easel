import type { ProductionArtifact, Work } from './productionApi';

export interface LibraryWork {
  work_id: string; title: string; state?: string; revision?: number; updated_at?: string;
  artifact_id: string | null; output_revision: number | null; accepted_output_id?: string | null;
  latest_artifact_id?: string | null; latest_output_revision?: number | null; has_newer_preview?: boolean;
}

export function libraryOutputs(work: Work): ProductionArtifact[] {
  return work.artifacts.filter(a => a.kind === 'output' && a.output_revision != null)
    .sort((a, b) => (b.output_revision || 0) - (a.output_revision || 0));
}

export function selectedLibraryOutput(work: Work, selected?: string): ProductionArtifact | undefined {
  const outputs = libraryOutputs(work);
  return outputs.find(a => a.id === selected) || outputs.find(a => a.id === work.accepted_output_id) || outputs[0];
}

export function libraryVersionPlan(work: Work, output?: ProductionArtifact) {
  if (!output?.run_id) return undefined;
  const run = work.runs.find(r => r.id === output.run_id);
  return work.plans.find(p => p.revision === run?.plan_revision);
}

/** Only user-facing media/documents, never a raw listing of production internals. */
export function libraryRelatedFiles(work: Work): ProductionArtifact[] {
  return work.artifacts.filter(a => a.kind !== 'output' && !['edit_project', 'checkpoint', 'receipt'].includes(a.kind) &&
    (/^(image|video|audio)\//.test(a.media_type) ||
      ['text/plain', 'text/markdown', 'application/pdf'].includes(a.media_type) || a.kind === 'export_bundle'));
}
