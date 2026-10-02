import type { OperatorRecord } from './api';
const rec = (v: unknown): OperatorRecord => v && typeof v === 'object' && !Array.isArray(v) ? v as OperatorRecord : {};
const list = (v: unknown): unknown[] => Array.isArray(v) ? v : [];
export function combinationRows(needs: unknown, candidates: OperatorRecord[]) {
  return list(needs).map(rec).filter(n => n.importance === 'required'
    && (['image', 'video'].includes(String(n.media_type)) || ['voice', 'bgm'].includes(String(n.modality_kind))))
    .map(need => ({ need, candidates: candidates.filter(asset =>
      asset.media_type === need.media_type
      && rec(asset.rights).status !== 'RESTRICTED'
      && list(asset.needs).some(n => rec(n).need_id === need.need_id)
      && (!need.required_source_kind || asset.source_kind === need.required_source_kind)
      && (!need.forbidden_source_kind || asset.source_kind !== need.forbidden_source_kind)
      && (need.modality_kind !== 'voice' || list(asset.generation_need_ids).includes(need.need_id))
      && (need.modality_kind !== 'bgm' || !list(asset.generation_need_ids).length))
      .sort((a, b) => score(b, need.need_id) - score(a, need.need_id)) }));
}


function score(asset: OperatorRecord, needId: unknown) {
  return (['KNOWN', 'PUBLIC_DOMAIN', 'ATTRIBUTION_REQUIRED'].includes(String(rec(asset.rights).status)) ? 4 : 0)
    + (list(asset.semantic_reviewed_need_ids).includes(needId) ? 2 : 0)
    + (list(asset.system_observed_need_ids).includes(needId) ? 1 : 0);
}
