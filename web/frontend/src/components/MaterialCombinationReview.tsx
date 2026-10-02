import { combinationRows } from '../lib/materialCombination';
import { useState } from 'react';
import { materialAssetPreviewUrl } from '../lib/api';
import type { OperatorRecord } from '../lib/api';

const rec = (v: unknown): OperatorRecord => v && typeof v === 'object' && !Array.isArray(v) ? v as OperatorRecord : {};
const list = (v: unknown): unknown[] => Array.isArray(v) ? v : [];


interface Props {
  attemptId: string;
  rows: ReturnType<typeof combinationRows>;
  busy: boolean;
  onAccept: (reviews: OperatorRecord[]) => void;
}

export default function MaterialCombinationReview({ attemptId, rows, busy, onAccept }: Props) {
  const [choices, setChoices] = useState<Record<string, string>>({});
  const [observations, setObservations] = useState('');
  const [facts, setFacts] = useState<Record<string, boolean>>({});
  const selected = rows.map(({ need, candidates }) => {
    const asset = candidates.find(a => a.asset_id === choices[String(need.need_id)]) ?? candidates[0];
    const evidence = list(asset?.needs).map(rec).find(n => n.need_id === need.need_id) ?? {};
    const key = [need.need_id, asset?.asset_id, asset?.asset_sha256].join(':');
    return { need, asset, evidence, key };
  });
  const fact = (key: string, field: string, evidence: OperatorRecord) =>
    facts[key + field] ?? (typeof evidence[field] === 'boolean' ? evidence[field] as boolean : null);
  const missing = selected.some(({ asset, evidence, key }) => !asset
    || (rec(evidence.constraints).logo === false && fact(key, 'logo_present', evidence) === null)
    || (rec(evidence.constraints).text_in_frame === false && fact(key, 'visible_text_present', evidence) === null));
  if (!rows.length || rows.some(row => !row.candidates.length)) return null;
  return <details className="film-op-review-claim">
    <summary>已看过候选？一次接受当前画面、旁白与配乐</summary>
    <p>这是选材未满足预期时的可选取舍。请实际查看或试听下面每项；接受表示你认为这组素材适合当前方案，系统原检查结论仍保留。事实、使用权、技术可用性和费用继续独立核验。</p>
    {selected.map(({ need, asset, evidence, key }, index) => {
      const src = materialAssetPreviewUrl(attemptId, String(asset.asset_id), String(asset.asset_sha256));
      return <div key={String(need.need_id)} className="film-op-review-claim">
        <strong>{index + 1}. {String(need.description)}</strong>
        <label>所选素材<select className="field" value={String(asset.asset_id)} disabled={busy}
          onChange={e => { setChoices({ ...choices, [String(need.need_id)]: e.target.value }); setObservations(''); }}>
          {rows[index].candidates.map((a, i) => <option key={String(a.asset_id)} value={String(a.asset_id)}>候选 {i + 1} · {String(a.source_kind ?? '素材')}</option>)}
        </select></label>
        {asset.media_type === 'image' ? <img src={src} alt={String(need.description)} style={{ maxWidth: '100%', maxHeight: 240 }} />
          : asset.media_type === 'video' ? <video src={src} controls preload="metadata" style={{ maxWidth: '100%', maxHeight: 240 }} />
          : <audio src={src} controls preload="metadata" />}
        <p>{list(asset.system_observed_need_ids).includes(need.need_id) ? '系统已有本场景观察记录。' : '当前适配性仍需你的实际判断。'}
          {rec(asset.rights).status === 'UNKNOWN' && ' 使用权尚未确认，接受组合不会解决这项缺口。'}</p>
        {(['logo_present', 'visible_text_present'] as const).map(field => {
          const required = rec(evidence.constraints)[field === 'logo_present' ? 'logo' : 'text_in_frame'] === false;
          if (!required) return null;
          const value = fact(key, field, evidence);
          return <label key={field}>{field === 'logo_present' ? '画面是否含品牌标识' : '画面是否含文字'}
            <select className="field" disabled={busy} value={value === null ? '' : String(value)}
              onChange={e => setFacts({ ...facts, [key + field]: e.target.value === 'true' })}>
              <option value="" disabled>尚未确定，请核对</option><option value="false">没有</option><option value="true">有</option>
            </select>
          </label>;
        })}
      </div>;
    })}
    <label>整体取舍说明<textarea className="field" disabled={busy} value={observations}
      placeholder="写下实际看过、听过后的判断，以及你接受的差异。无需逐项重复填写。"
      onChange={e => setObservations(e.target.value)} /></label>
    <button className="btn btn-primary" disabled={busy || missing || observations.trim().length < 8}
      onClick={() => onAccept(selected.map(({ need, asset, evidence, key }) => ({
        needId: need.need_id, assetId: asset.asset_id, assetSha256: asset.asset_sha256,
        observedContent: observations.trim(), confirmReview: true,
        logoPresent: fact(key, 'logo_present', evidence),
        visibleTextPresent: fact(key, 'visible_text_present', evidence),
      })))}>我已查看和试听，接受这组素材并继续</button>
  </details>;
}
