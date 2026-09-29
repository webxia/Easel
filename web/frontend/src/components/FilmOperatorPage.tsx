import { useCallback, useEffect, useRef, useState } from 'react';
import {
  approveFilmCost, cancelFilmBuild, createOperatorSession,
  estimateFilmAttempt, exportFilmOutput, fetchCreation, fetchFilmAttempt, fetchScriptTruth, generateMiniMaxMaterial, inspectFilmBuild, mediaUrl,
  fetchMaterialRightsCandidates, listFilmAttempts, reconcileFilmBuild, startFilmAuthoring,
  refreshFilmBuild, resolveFilmRuntime, reviewFilmOutput, reviewMaterialRights, reviewScriptTruth, selectFilmBuild, submitFilmBuild,
  fetchPromotableMaterials, promoteAttemptMaterial,
  validateFilmAttempt,
} from '../lib/api';
import type { OperatorRecord } from '../lib/api';

type JsonRecord = Record<string, unknown>;
const record = (value: unknown): JsonRecord =>
  value !== null && typeof value === 'object' && !Array.isArray(value) ? value as JsonRecord : {};
const text = (value: unknown, fallback = '—') => typeof value === 'string' && value ? value : fallback;
const json = (value: unknown) => JSON.stringify(value ?? null, null, 2);
const operationError = (error: unknown) => error instanceof Error ? error.message : '操作失败';

interface FilmOperatorPageProps {
  creationId: string;
  title: string;
}

export default function FilmOperatorPage({ creationId, title }: FilmOperatorPageProps) {
  const [creationSnapshot, setCreationSnapshot] = useState<OperatorRecord | null>(null);
  const [attempts, setAttempts] = useState<OperatorRecord[]>([]);
  const [attemptId, setAttemptId] = useState('');
  const [attempt, setAttempt] = useState<OperatorRecord | null>(null);
  const [scriptTruth, setScriptTruth] = useState<OperatorRecord | null>(null);
  const [scriptTruthConfirmed, setScriptTruthConfirmed] = useState(false);
  const [operatorSessionReady, setOperatorSessionReady] = useState(false);
  const [runPath, setRunPath] = useState('productions/easel-authoring/run.sv');
  const [budget, setBudget] = useState('');
  const [buildTitle, setBuildTitle] = useState('Easel Creation');
  const [buildIdInput, setBuildIdInput] = useState('');
  const [reconcileOutputName, setReconcileOutputName] = useState('');
  const [exportName, setExportName] = useState('final');
  const [reviewOutputName, setReviewOutputName] = useState('');
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [refreshVersion, setRefreshVersion] = useState(0);
  const [inspectResult, setInspectResult] = useState<unknown>(null);
  const [generationNeedId, setGenerationNeedId] = useState('');
  const [generationResult, setGenerationResult] = useState<unknown>(null);
  const [rightsCandidates, setRightsCandidates] = useState<OperatorRecord[]>([]);
  const [rightsAssetId, setRightsAssetId] = useState('');
  const [rightsStatus, setRightsStatus] = useState('UNKNOWN');
  const [rightsLicenseName, setRightsLicenseName] = useState('');
  const [rightsLicenseUrl, setRightsLicenseUrl] = useState('');
  const [rightsSourceCreator, setRightsSourceCreator] = useState('');
  const [rightsSourcePage, setRightsSourcePage] = useState('');
  const [rightsEvidenceKind, setRightsEvidenceKind] = useState('asset_license');
  const [rightsEvidenceReference, setRightsEvidenceReference] = useState('');
  const [rightsEvidenceSummary, setRightsEvidenceSummary] = useState('');
  const [rightsAttributionRequired, setRightsAttributionRequired] = useState(false);
  const [rightsAttributionText, setRightsAttributionText] = useState('');
  const [rightsUsageConstraints, setRightsUsageConstraints] = useState('');
  const [rightsConfirmed, setRightsConfirmed] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [attemptMaterials, setAttemptMaterials] = useState<OperatorRecord[]>([]);
  const [showAttemptMaterials, setShowAttemptMaterials] = useState(false);
  const preparationRun = useRef('');
  const exportRun = useRef('');
  const reconciliationRun = useRef('');
  const manualAttemptSelection = useRef(false);

  useEffect(() => {
    let cancelled = false;
    createOperatorSession().then(() => {
      if (!cancelled) setOperatorSessionReady(true);
    }).catch((reason: unknown) => {
      if (!cancelled) setError(operationError(reason));
    });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!creationId) { setCreationSnapshot(null); return; }
    let cancelled = false;
    fetchCreation(creationId).then((item) => {
      if (!cancelled) setCreationSnapshot(item as unknown as OperatorRecord);
    }).catch((reason: unknown) => { if (!cancelled) setError(operationError(reason)); });
    return () => { cancelled = true; };
  }, [creationId, refreshVersion]);

  useEffect(() => {
    if (!operatorSessionReady || !creationId) {
      setAttempts([]);
      setAttemptId('');
      setAttempt(null);
      return;
    }
    let cancelled = false;
    listFilmAttempts(creationId).then((items) => {
      if (cancelled) return;
      setAttempts(items);
      setAttemptId((current) => items.some((item) => item.attempt_id === current)
        ? current : text(items[0]?.attempt_id, ''));
    }).catch((reason: unknown) => {
      if (!cancelled) setError(operationError(reason));
    });
    return () => { cancelled = true; };
  }, [operatorSessionReady, creationId, refreshVersion]);

  useEffect(() => {
    if (!operatorSessionReady || !creationId || attemptId) return;
    const timer = window.setInterval(() => setRefreshVersion((version) => version + 1), 5000);
    return () => window.clearInterval(timer);
  }, [operatorSessionReady, creationId, attemptId]);

  useEffect(() => {
    if (!operatorSessionReady || !attemptId) {
      setAttempt(null);
      return;
    }
    let cancelled = false;
    fetchFilmAttempt(attemptId).then((item) => {
      if (cancelled) return;
      setAttempt(item);
      const authoring = record(item.authoring);
      const plan = record(item.plan);
      setRunPath(text(authoring.run_path, text(plan.run_path, 'productions/easel-authoring/run.sv')));
      const names = Object.keys(record(item.outputs));
      setReviewOutputName((current) => names.includes(current) ? current : names[0] || '');
    }).catch((reason: unknown) => { if (!cancelled) setError(operationError(reason)); });
    return () => { cancelled = true; };
  }, [operatorSessionReady, attemptId, refreshVersion]);

  useEffect(() => {
    if (!operatorSessionReady || !attemptId || !advancedOpen) { setRightsCandidates([]); return; }
    let cancelled = false;
    setRightsCandidates([]);
    fetchMaterialRightsCandidates(attemptId).then((items) => {
      if (!cancelled) {
        setRightsCandidates(items);
        setRightsAssetId((current) => items.some((item) => item.asset_id === current)
          ? current : text(items[0]?.asset_id, ''));
      }
    }).catch((reason: unknown) => { if (!cancelled) setError(operationError(reason)); });
    return () => { cancelled = true; };
  }, [operatorSessionReady, attemptId, refreshVersion, advancedOpen]);

  useEffect(() => {
    if (!operatorSessionReady || !attemptId) { setScriptTruth(null); return; }
    let cancelled = false;
    fetchScriptTruth(attemptId).then((ledger) => {
      if (!cancelled) {
        setScriptTruth(ledger);
        setScriptTruthConfirmed(false);
      }
    }).catch(() => { if (!cancelled) setScriptTruth(null); });
    return () => { cancelled = true; };
  }, [operatorSessionReady, attemptId, refreshVersion]);

  useEffect(() => {
    if (creationSnapshot?.selected_attempt_id === attemptId
        && typeof creationSnapshot?.selected_output_name === 'string') {
      setReviewOutputName(creationSnapshot.selected_output_name);
    }
  }, [creationSnapshot, attemptId]);

  useEffect(() => {
    if (!operatorSessionReady || !attemptId
        || creationSnapshot?.selected_attempt_id !== attemptId
        || typeof creationSnapshot?.selected_output_name !== 'string') {
      setAttemptMaterials([]);
      return;
    }
    let cancelled = false;
    fetchPromotableMaterials(attemptId).then((result) => {
      if (!cancelled) setAttemptMaterials(Array.isArray(result.materials) ? result.materials.map(record) : []);
    }).catch(() => { if (!cancelled) setAttemptMaterials([]); });
    return () => { cancelled = true; };
  }, [operatorSessionReady, attemptId, creationSnapshot, refreshVersion]);

  useEffect(() => {
    const selectedId = creationSnapshot?.selected_attempt_id;
    if (!manualAttemptSelection.current && typeof selectedId === 'string'
        && attempts.some((item) => item.attempt_id === selectedId)) setAttemptId(selectedId);
  }, [creationSnapshot, attempts]);

  const attemptStatus = record(attempt);
  const materialGate = record(attemptStatus.material_gate);
  const materialPlan = record(attemptStatus.material_planning);
  const blockingNeedIds = Array.isArray(materialGate.blocking_needs)
    ? materialGate.blocking_needs.filter((value): value is string => typeof value === 'string') : [];
  const scriptClaims = Array.isArray(scriptTruth?.claims) ? scriptTruth.claims.map(record) : [];
  const scriptReviewCounts = {
    sourceSupported: scriptClaims.filter((claim) => claim.status === 'TRUTH_SUPPORTED').length,
    autoReviewed: scriptClaims.filter((claim) => claim.status === 'AUTO_REVIEWED' || claim.status === 'FICTION_MARKED').length,
    delegated: scriptClaims.filter((claim) => claim.status === 'DELEGATE_REVIEWED').length,
    human: scriptClaims.filter((claim) => claim.status === 'HUMAN_REVIEWED').length,
    pending: scriptClaims.filter((claim) => claim.status === 'REVIEW_REQUIRED').length,
  };
  const plan = record(attemptStatus.plan);
  const cost = record(attemptStatus.cost);
  const build = record(attemptStatus.build);
  const outputs = record(attemptStatus.outputs);
  const outputNames = Object.keys(outputs);
  const selectedReviewOutput = record(outputs[reviewOutputName]);
  const selectedRightsCandidate = rightsCandidates.find((item) => item.asset_id === rightsAssetId);
  const brief = record(record(attemptStatus.production_request).production_brief);
  const selectedOutput = creationSnapshot?.selected_attempt_id === attemptId
    && typeof creationSnapshot?.selected_output_name === 'string';
  const allLocalNoCharge = Number(record(cost.pricing).requestCount) > 0
    && record(cost.pricing).requestCount === record(cost.pricing).noChargeRequestCount;
  const estimatedCost = typeof cost.estimated_usd === 'number' ? cost.estimated_usd : null;
  const canApproveCost = allLocalNoCharge || estimatedCost !== null;
  const declaredBudget = typeof cost.max_budget_usd === 'number' ? cost.max_budget_usd : null;
  const requestedBudget = allLocalNoCharge ? Math.min(1, declaredBudget ?? 1) : Number(budget);
  const budgetAllowed = requestedBudget > 0 && (declaredBudget === null || requestedBudget <= declaredBudget);
  const currentOutput = reviewOutputName && typeof selectedReviewOutput.path === 'string';
  const execution = text(attemptStatus.execution_status, 'NOT_SUBMITTED');
  const phase = selectedOutput ? 'done'
    : attemptStatus.review_status === 'APPROVED' ? 'selecting'
    : currentOutput ? 'review'
    : execution === 'BUILD_COMPLETE' ? 'exporting'
    : ['SUBMITTING', 'SUBMISSION_UNCERTAIN'].includes(execution) ? 'verifying'
    : ['SUBMITTING', 'SUBMISSION_UNCERTAIN', 'SUBMITTED', 'RUNNING', 'CANCEL_REQUESTED'].includes(execution) ? 'building'
    : execution === 'BUILD_FAILED' || ['AUTHORING_FAILED', 'PLAN_FAILED'].includes(text(attemptStatus.authoring_status)) ? 'failed'
    : scriptTruth?.status === 'REVIEW_REQUIRED' ? 'content-review'
    : materialGate.status === 'MATERIAL_NOT_READY' ? 'material'
    : plan.status === 'ready' && cost.status === 'pricing_read' && execution === 'NOT_SUBMITTED' ? 'ready'
    : materialGate.status === 'MATERIAL_READY' ? 'preparing' : 'planning';
  const phaseTitle: Record<string, string> = {
    done: '最终成片已确认', selecting: '成片已通过审核', review: '视频制作完成',
    exporting: '正在整理成片', verifying: '正在确认制作进度', building: '正在制作视频', failed: '视频制作遇到问题',
    'content-review': '请确认视频内容', material: '素材还需要确认',
    ready: '视频已准备好制作', preparing: '正在编排视频', planning: 'Easel 正在准备作品',
  };
  const phaseDescription: Record<string, string> = {
    done: '视频制作完成，已保存到内容库。',
    selecting: '审核已经通过，Easel 正在确认最终成片。',
    review: '请播放视频，满意后确认成片。',
    exporting: '合成已完成，Easel 正在生成可查看的视频。',
    verifying: 'Easel 正在核对本次制作结果，请不要重复开始制作。',
    building: 'Easel 正在合成画面和声音，完成后会自动准备成片。',
    failed: execution === 'BUILD_FAILED'
      ? '本次合成未完成。Easel 已保留作品和素材，请在对话中决定是否重新制作。'
      : 'Easel 已保留当前进度，可以重新整理后继续。',
    'content-review': '内容中有需要你确认的表述，确认后 Easel 会继续准备素材。',
    material: '当前素材还不能用于制作。你可以在对话中补充素材或调整画面要求；Easel 会继续核对使用条件。',
    ready: '内容和素材都已准备好。确认后 Easel 会开始制作视频。',
    preparing: '内容和素材已准备，Easel 正在安排画面与节奏。',
    planning: 'Easel 正在理解创作意图，整理内容和素材。',
  };
  const isBlocked = attemptStatus.execution_status === 'BLOCKED'
    || materialGate.status === 'MATERIAL_NOT_READY';
  const shouldAutoTrack = operatorSessionReady && !!attemptId && (
    attemptStatus.authoring_status === 'AUTHORING_RUNNING'
    || ['PENDING', 'READY_FOR_EXTERNAL_AUTHORING'].includes(text(attemptStatus.authoring_status))
    || ['SUBMITTING', 'SUBMISSION_UNCERTAIN', 'SUBMITTED', 'RUNNING', 'CANCEL_REQUESTED'].includes(text(attemptStatus.execution_status))
  );

  useEffect(() => {
    if (!shouldAutoTrack) return;
    let cancelled = false;
    let refreshing = false;
    const poll = async () => {
      if (cancelled || refreshing) return;
      refreshing = true;
      try {
        const current = attemptStatus.authoring_status === 'AUTHORING_RUNNING' || !build.build_id
          ? await fetchFilmAttempt(attemptId) : await refreshFilmBuild(attemptId);
        if (!cancelled) {
          setAttempt(current as unknown as OperatorRecord);
          try { setScriptTruth(await fetchScriptTruth(attemptId)); } catch { /* Planning may not have produced a script yet. */ }
        }
      } catch {
        // Keep the last known state; transient polling failures should not
        // interrupt the user's work or replace a useful error with noise.
      } finally {
        refreshing = false;
      }
    };
    const timer = window.setInterval(() => { void poll(); }, 5000);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [attemptId, shouldAutoTrack, attemptStatus.authoring_status, build.build_id]);

  useEffect(() => {
    if (!operatorSessionReady || !attemptId || execution !== 'SUBMISSION_UNCERTAIN'
        || reconciliationRun.current === attemptId) return;
    reconciliationRun.current = attemptId;
    void reconcileFilmBuild(attemptId).then((result) => {
      if (result.status === 'reconciled') setAttempt(record(result.attempt));
      else setError('制作结果仍在核对中；系统不会重复提交。可在高级信息中查看详情。');
    }).catch((reason: unknown) => setError(operationError(reason)));
  }, [operatorSessionReady, attemptId, execution]);

  // Preparation, validation and pricing are deterministic product work. They
  // stay behind their formal APIs, without asking the Creator to operate each step.
  useEffect(() => {
    if (!operatorSessionReady || !attemptId || !attempt
        || !['AUTHORING_READY', 'PLANNED'].includes(text(attempt.authoring_status))
        || !['NOT_SUBMITTED', 'BLOCKED'].includes(text(attempt.execution_status))
        || cost.status === 'pricing_read') return;
    const key = `${attemptId}:${text(record(attempt.authoring).authoring_sha256)}:${text(attempt.runtime_status)}:${text(plan.status)}:${text(cost.status)}`;
    if (preparationRun.current === key) return;
    preparationRun.current = key;
    let cancelled = false;
    const prepare = async () => {
      setBusy('准备制作');
      try {
        let current = attempt;
        if (current.runtime_status !== 'CONFIGURED') current = await resolveFilmRuntime(attemptId);
        if (record(current.plan).status !== 'ready') {
          const source = text(record(current.authoring).run_path, '');
          if (!source) throw new Error('缺少视频编排结果');
          current = await validateFilmAttempt(attemptId, source);
        }
        if (record(current.cost).status !== 'pricing_read') current = await estimateFilmAttempt(attemptId);
        if (!cancelled) { setAttempt(current); setError(''); }
      } catch (reason: unknown) {
        if (!cancelled) setError(operationError(reason));
      } finally {
        if (!cancelled) setBusy('');
      }
    };
    void prepare();
    return () => { cancelled = true; };
  }, [operatorSessionReady, attemptId, attempt, cost.status, plan.status]);

  useEffect(() => {
    if (!operatorSessionReady || !attemptId || execution !== 'BUILD_COMPLETE'
        || Object.keys(outputs).length > 0 || exportRun.current === attemptId) return;
    exportRun.current = attemptId;
    let cancelled = false;
    const exportCompletedBuild = async () => {
      setBusy('整理成片');
      try {
        const inspection = await inspectFilmBuild(attemptId);
        const candidates = record(inspection.build).outputs;
        const target = Array.isArray(candidates)
          ? candidates.map(record).find((item) => item.target === true && item.mediaType === 'video/mp4') : undefined;
        if (typeof target?.name !== 'string') throw new Error('制作结果中没有可导出的视频');
        const updated = await exportFilmOutput(attemptId, target.name);
        if (!cancelled) { setAttempt(updated); setReviewOutputName(target.name); setError(''); }
      } catch (reason: unknown) {
        if (!cancelled) setError(operationError(reason));
      } finally {
        if (!cancelled) setBusy('');
      }
    };
    void exportCompletedBuild();
    return () => { cancelled = true; };
  }, [operatorSessionReady, attemptId, execution, outputs]);

  const run = useCallback(async (label: string, action: () => Promise<unknown>) => {
    setBusy(label);
    setError('');
    setNotice('');
    try {
      await action();
      setNotice(({
        '开始制作': '视频制作已开始，Easel 会持续更新进度。',
        '确认内容': '内容已确认，Easel 会继续准备素材。',
        '确认成片': '已确认最终成片。',
        '确认最终成片': '已确认最终成片。',
        '重新整理视频': 'Easel 正在重新整理视频。',
        '重新检查视频方案': '视频方案已重新检查。',
      } as Record<string, string>)[label] || `${label}完成`);
      setRefreshVersion((version) => version + 1);
    } catch (reason: unknown) {
      setError(operationError(reason));
    } finally {
      setBusy('');
    }
  }, []);

  const outputsForSelect = outputNames.map((name) => ({ name, item: record(outputs[name]) }));
  const action = (label: string, fn: () => Promise<unknown>, className = 'btn', disabled = false) => (
    <button className={className} disabled={!operatorSessionReady || !attemptId || !!busy || disabled} onClick={() => void run(label, fn)}>
      {busy === label ? '处理中…' : label}
    </button>
  );

  return (
    <div className="film-operator-page">
      <h2 className="film-operator-title">视频制作</h2>
      {!operatorSessionReady && <p className="page-subtitle">正在连接作品，请稍候…</p>}
      {notice && <div className="film-op-message is-ok" role="status">{notice}</div>}
      {error && <div className="film-op-message is-error" role="alert">
        这一步暂时无法继续。Easel 已保留当前进度，你可以重试。
      </div>}

      {operatorSessionReady && !attemptId && <section className="card film-op-card film-op-creator">
        <h2>{['FAILED', 'MATERIAL_FAILED'].includes(text(record(creationSnapshot?.preparation).status))
          ? '内容准备遇到问题' : record(creationSnapshot?.preparation).status === 'MATERIAL_NOT_READY'
            ? '素材还未准备好' : '正在准备作品'}</h2>
        <p>{['FAILED', 'MATERIAL_FAILED', 'MATERIAL_NOT_READY'].includes(text(record(creationSnapshot?.preparation).status))
          ? '作品记录已保留。请在对话中补充素材或告诉 Easel 继续整理当前方案。'
          : 'Easel 会先整理内容与素材。准备好后，这里会显示下一步。'}</p>
        {['FAILED', 'MATERIAL_FAILED', 'MATERIAL_NOT_READY'].includes(text(record(creationSnapshot?.preparation).status)) && <button className="btn btn-primary" onClick={() => {
          document.querySelector<HTMLTextAreaElement>('.chat-input-area textarea')?.focus();
        }}>在对话中继续</button>}
      </section>}

      {operatorSessionReady && attemptId && attempt && <section className="card film-op-card film-op-creator">
        <div className="film-op-heading"><h2>{phaseTitle[phase]}</h2><span className="film-op-work-title" title={title}>{title}</span></div>
        <p>{phaseDescription[phase]}</p>
        {phase === 'done' && <div className="film-op-selected">
          <strong>✓ 已保存到内容库</strong>
          <span>本次使用素材：{attemptMaterials.filter((item) => item.used_in_creation === true).length} 项</span>
          {typeof record(creationSnapshot?.content_asset).path === 'string' && <a
            className="btn btn-sm" href={mediaUrl(String(record(creationSnapshot?.content_asset).path))}
            target="_blank" rel="noreferrer">打开成片</a>}
          {attemptMaterials.some((item) => item.used_in_creation === true) && <button
            className="btn btn-sm" onClick={() => setShowAttemptMaterials((value) => !value)}>
            {showAttemptMaterials ? '收起素材' : '查看素材'}
          </button>}
          {attemptMaterials.some((item) => item.used_in_creation === true && item.eligible !== true && item.promoted !== true)
            && <span>部分素材暂不符合复用条件</span>}
          {showAttemptMaterials && <div className="film-op-details">
            {attemptMaterials.filter((item) => item.used_in_creation === true).map((item) => <div
              className="film-op-selected" key={String(item.asset_id)}>
              <strong>{text(item.media_type)} · {text(item.provider, text(item.source_kind))}</strong>
              <span>{item.promoted === true ? '已保存为可复用素材' : item.eligible === true ? '可保存为可复用素材' : '暂不可保存为可复用素材'}</span>
              {item.eligible === true && item.promoted !== true && <button className="btn btn-sm" disabled={!!busy}
                onClick={() => {
                  if (!window.confirm('将这项素材保存到 Material Library，供此 Creator 以后复用？Rights 证据和来源信息会一并保留。')) return;
                  void run('保存可复用素材', async () => promoteAttemptMaterial(
                    attemptId, String(item.asset_id), String(item.sha256),
                  ));
                }}>保存可复用素材</button>}
              {item.eligible !== true && item.promoted !== true && <small>{text(item.ineligible_reason, '当前 Rights 或素材证据不符合长期复用要求')}</small>}
            </div>)}
          </div>}
        </div>}
        <div className="film-op-progress" aria-label="视频创作进度">
          <span className={phase === 'planning' || phase === 'content-review' ? 'is-current' : 'is-complete'}>内容</span>
          <span className={['planning', 'content-review', 'material'].includes(phase) ? 'is-current' : 'is-complete'}>素材</span>
          <span className={['preparing', 'ready', 'building', 'verifying', 'exporting', 'failed'].includes(phase) ? 'is-current' : ['review', 'selecting', 'done'].includes(phase) ? 'is-complete' : ''}>视频制作</span>
          <span className={['review', 'selecting'].includes(phase) ? 'is-current' : phase === 'done' ? 'is-complete' : ''}>成片</span>
        </div>
        {['ready', 'building', 'preparing'].includes(phase) && <div className="film-op-creator-facts">
          <span>内容已准备</span><span>素材已准备</span>
          {typeof brief.duration_seconds === 'number' && <span>预计时长：{brief.duration_seconds} 秒</span>}
          {typeof brief.aspect_ratio === 'string' && <span>画幅：{brief.aspect_ratio}</span>}
          {allLocalNoCharge && <span>本次制作无第三方计费请求</span>}
          {!allLocalNoCharge && estimatedCost !== null && <span>预计费用：${estimatedCost.toFixed(2)}</span>}
        </div>}
        {phase === 'ready' && <>
          {!canApproveCost && <p className="film-op-warning">费用尚无法确认，暂不能开始制作。可在高级信息中查看详情。</p>}
          {canApproveCost && !allLocalNoCharge && <label className="film-op-budget">本次同意的预算（美元）
            <input className="field" inputMode="decimal" value={budget} onChange={(event) => setBudget(event.target.value)} />
            {declaredBudget !== null && <small>本作品已约定最多 ${declaredBudget.toFixed(2)}。</small>}
            <small>该金额用于记录你的批准；服务商不保证自动限制实际费用。</small>
          </label>}
          <button className="btn btn-primary" disabled={!!busy || !canApproveCost || !budgetAllowed} onClick={() => {
            void run('开始制作', async () => {
              if (cost.approved !== true) await approveFilmCost(attemptId, requestedBudget);
              return submitFilmBuild(attemptId, text(creationSnapshot?.idea, 'Easel 视频'));
            });
          }}>开始制作</button>
        </>}
        {phase === 'building' && <p role="status">正在合成视频，完成后会自动生成预览。你可以离开此页面。</p>}
        {phase === 'failed' && ['AUTHORING_FAILED', 'PLAN_FAILED'].includes(text(attemptStatus.authoring_status)) && <button className="btn btn-primary" disabled={!!busy}
          onClick={() => {
            if (attemptStatus.authoring_status === 'AUTHORING_FAILED') void run('重新整理视频', () => startFilmAuthoring(attemptId));
            else void run('重新检查视频方案', async () => {
              const source = text(record(attemptStatus.authoring).run_path, '');
              if (!source) throw new Error('缺少视频编排结果');
              if (attemptStatus.runtime_status !== 'CONFIGURED') await resolveFilmRuntime(attemptId);
              await validateFilmAttempt(attemptId, source);
              return estimateFilmAttempt(attemptId);
            });
          }}>重新尝试</button>}
        {phase === 'failed' && !['AUTHORING_FAILED', 'PLAN_FAILED'].includes(text(attemptStatus.authoring_status)) && <p>本次制作未能完成。请在对话中告诉 Easel 是否重新制作。</p>}
        {phase === 'content-review' && <>
          {scriptClaims.filter((claim) => claim.status === 'REVIEW_REQUIRED').map((claim) =>
            <div className="film-op-review-claim" key={text(claim.claim_id)}>
              <strong>{text(claim.text)}</strong>
              {typeof claim.evidence_quote === 'string' && <small>参考依据：{claim.evidence_quote}</small>}
            </div>)}
          {typeof scriptTruth?.script === 'string' && <details><summary>查看完整内容</summary><pre>{scriptTruth.script}</pre></details>}
          <label className="film-op-confirm"><input type="checkbox" checked={scriptTruthConfirmed}
            onChange={(event) => setScriptTruthConfirmed(event.target.checked)} />我已核对待确认的表述与完整内容。</label>
          <button className="btn btn-primary" disabled={!!busy || !scriptTruthConfirmed || typeof scriptTruth?.script_sha256 !== 'string'
            || typeof scriptTruth?.truth_packet_sha256 !== 'string'} onClick={() => {
            void run('确认内容', () => reviewScriptTruth(attemptId, String(scriptTruth?.script_sha256), String(scriptTruth?.truth_packet_sha256)));
          }}>确认内容并继续</button>
        </>}
        {phase === 'material' && <button className="btn btn-primary" onClick={() => {
          document.querySelector<HTMLTextAreaElement>('.chat-input-area textarea')?.focus();
        }}>在对话中说明素材需求</button>}
        {phase === 'review' && <>
          {typeof selectedReviewOutput.path === 'string' && <video className="film-op-preview" controls preload="metadata" src={mediaUrl(selectedReviewOutput.path)}>
            浏览器不支持视频预览。
          </video>}
          <button className="btn btn-primary" disabled={!!busy || typeof selectedReviewOutput.sha256 !== 'string'} onClick={() => {
            void run('确认成片', async () => {
              await reviewFilmOutput(attemptId, {
                outputName: reviewOutputName, sha256: String(selectedReviewOutput.sha256),
                truth: { status: 'pass', notes: [] }, style: { status: 'pass', notes: [] },
                human: { status: 'approved' }, feedback: [],
              });
              return selectFilmBuild(creationId, attemptId, reviewOutputName);
            });
          }}>确认成片</button>
          <small>确认后，这支视频会成为作品的最终成片；不会自动发布。</small>
        </>}
        {phase === 'selecting' && <button className="btn btn-primary" disabled={!!busy} onClick={() => void run('确认最终成片', () => selectFilmBuild(creationId, attemptId, reviewOutputName))}>确认最终成片</button>}
        {phase === 'done' && typeof selectedReviewOutput.path === 'string' && <video className="film-op-preview" controls preload="metadata" src={mediaUrl(selectedReviewOutput.path)}>
          浏览器不支持视频预览。
        </video>}
        {(error || (phase === 'exporting' && !!busy)) && <button className="btn" disabled={!!busy} onClick={() => {
          preparationRun.current = ''; exportRun.current = ''; setError(''); setRefreshVersion((version) => version + 1);
        }}>重新检查进度</button>}
        {phase === 'done' && <p className="film-op-manual">想修改视频？在对话中告诉 Easel 你的想法。</p>}
      </section>}

      <details className="film-op-advanced" open={advancedOpen} onToggle={(event) => setAdvancedOpen(event.currentTarget.open)}>
        <summary>高级信息与操作</summary>
        {error && <div className="film-op-message is-error" role="status">{error}</div>}

      <section className="card film-op-card">
        <h2>当前作品与 Attempt</h2>
        <div className="film-op-grid">
          <div><span>Creation</span><strong>{text(creationSnapshot?.idea, creationId)} · {creationId}</strong></div>
          <label>Attempt
            <select className="field" value={attemptId} onChange={(event) => {
              manualAttemptSelection.current = true;
              setAttemptId(event.target.value);
            }} disabled={!operatorSessionReady}>
              <option value="">选择 Attempt</option>
              {attempts.map((item) => <option key={String(item.attempt_id)} value={String(item.attempt_id)}>
                #{String(item.attempt_number ?? '?')} · {String(item.status ?? 'UNKNOWN')} · {String(item.attempt_id)}
              </option>)}
            </select>
          </label>
          <div className="film-op-buttons">
            <span className={`badge ${operatorSessionReady ? 'badge-accent' : ''}`}>{operatorSessionReady ? '本机会话已连接' : '正在连接本机会话…'}</span>
            <button className="btn" disabled={!operatorSessionReady || !!busy} onClick={() => setRefreshVersion((version) => version + 1)}>刷新状态</button>
          </div>
        </div>
        <small>会话仅限本机同源浏览器，有效期 12 小时并由服务端保护；无需手动输入凭证。</small>
      </section>

      {operatorSessionReady && !attemptId ? <div className="card film-op-empty">此 Creation 尚无 Hypit Attempt。请先从正式 Creation 对话流程完成准备；操作台不会伪造 Handoff 或绕过准备链。</div> : null}

      {operatorSessionReady && attemptId && attempt && <>
        <section className="card film-op-card">
          <h2>Script / Truth Packet 审阅</h2>
          <p>审阅记录绑定当前 SCRIPT 与冻结 Truth Packet。创作指令由系统分类，来源支持、Codex 委托复核与人工复核分别留痕；只有尚未处理的事实主张会阻断流程，不会把复核记录伪装成来源事实。</p>
          <div className="film-op-grid">
            <div><span>状态</span><strong>{text(scriptTruth?.status, '不可用')}</strong></div>
            <div><span>待处理事实</span><strong>{scriptReviewCounts.pending}</strong></div>
            <div><span>已自动分类</span><strong>{scriptReviewCounts.autoReviewed}</strong></div>
            <div><span>来源支持</span><strong>{scriptReviewCounts.sourceSupported}</strong></div>
            <div><span>Codex 委托复核</span><strong>{scriptReviewCounts.delegated}</strong></div>
            <div><span>人工复核</span><strong>{scriptReviewCounts.human}</strong></div>
          </div>
          {typeof scriptTruth?.script === 'string' && <details><summary>查看完整 SCRIPT（{scriptTruth.script.length.toLocaleString()} 字符）</summary><pre>{scriptTruth.script}</pre></details>}
          {scriptTruth && <details><summary>查看完整逐句审阅记录（{scriptClaims.length} 条）</summary><pre>{json(scriptClaims.map((claim) => ({
            claim_id: claim.claim_id, text: claim.text, classification: claim.classification,
            status: claim.status, source_ref: claim.source_ref, evidence_quote: claim.evidence_quote,
          })))}</pre></details>}
          {scriptTruth?.status === 'REVIEW_REQUIRED' && <>
            <label className="film-op-confirm">
              <input type="checkbox" checked={scriptTruthConfirmed} onChange={(event) => setScriptTruthConfirmed(event.target.checked)} />
              我已逐句检查完整 SCRIPT 中所有待审内容，并对照冻结 Truth Packet 核实；该操作只记录人工审阅，不把内容伪装为自动来源支持。
            </label>
            <div className="film-op-actions">
              <button className="btn btn-primary" disabled={!operatorSessionReady || !!busy || !scriptTruthConfirmed
                || typeof scriptTruth.script_sha256 !== 'string' || typeof scriptTruth.truth_packet_sha256 !== 'string'} onClick={() => {
                void run('确认 Script Truth 人工审阅', () => reviewScriptTruth(
                  attemptId, String(scriptTruth.script_sha256), String(scriptTruth.truth_packet_sha256),
                ));
              }}>确认审阅并继续 Material Supply</button>
              <button className="btn" disabled={!operatorSessionReady || !!busy
                || typeof scriptTruth.script_sha256 !== 'string' || typeof scriptTruth.truth_packet_sha256 !== 'string'} onClick={() => {
                void run('记录 Codex 委托复核并继续 Material Supply', () => reviewScriptTruth(
                  attemptId, String(scriptTruth.script_sha256), String(scriptTruth.truth_packet_sha256), 'codex_delegate',
                ));
              }}>由已受委托的 Codex 复核并继续</button>
            </div>
          </>}
        </section>

        <section className="card film-op-card">
          <div className="film-op-heading"><h2>主链状态</h2><span className="badge badge-accent">{text(attemptStatus.status, 'UNKNOWN')}</span></div>
          {shouldAutoTrack && <p role="status">制作正在运行，页面每 5 秒自动跟踪状态；无需停留在这里盯进度。</p>}
          <div className="film-op-stats">
            <div><span>Preparation</span><strong>{text(attemptStatus.preparation_status)}</strong></div>
            <div><span>Material Gate</span><strong>{text(materialGate.status, 'NOT_RECORDED')}</strong></div>
            <div><span>Authoring</span><strong>{text(attemptStatus.authoring_status)}</strong></div>
            <div><span>Runtime</span><strong>{text(attemptStatus.runtime_status)}</strong></div>
            <div><span>Execution</span><strong>{text(attemptStatus.execution_status)}</strong></div>
            <div><span>Export / Review</span><strong>{text(attemptStatus.export_status)} / {text(attemptStatus.review_status)}</strong></div>
          </div>
          <div className="film-op-selected">
            <strong>Creation Selected Output</strong>
            <span>{text(record(creationSnapshot?.publication).status, '未选择')}</span>
            <span>{text(creationSnapshot?.selected_attempt_id)} / {text(creationSnapshot?.selected_output_name)}</span>
          </div>
          {isBlocked && <p className="film-op-warning">当前有门禁阻塞。页面会显示原因，但不能在此跳过 Material Readiness 或 Runtime 校验。</p>}
          {attemptStatus.last_error != null && <div><h3>最近错误</h3><pre>{json(attemptStatus.last_error)}</pre></div>}
          {attemptStatus.authoring_status === 'AUTHORING_FAILED' && materialGate.status === 'MATERIAL_READY'
            && action('在当前 Attempt 重试 Authoring', () => startFilmAuthoring(attemptId))}
          {attemptStatus.authoring_status === 'AUTHORING_RUNNING' && materialGate.status === 'MATERIAL_READY'
            && action('恢复当前非付费 Authoring', () => startFilmAuthoring(attemptId))}
          <div className="film-op-details">
            <details><summary>MaterialPlan</summary><pre>{json(materialPlan)}</pre></details>
            <details><summary>MaterialReadiness / Blocking Gaps</summary><pre>{json(materialGate)}</pre></details>
            <details><summary>Attempt 事件与完整状态</summary><pre>{json(attempt)}</pre></details>
          </div>
        </section>

        <section className="card film-op-card">
          <h2>AI 素材生成</h2>
          <p>Material Layer 可对符合生成策略的图片、视频和语音缺口调用 MiniMax。语音使用预置音色并绑定已审核脚本，不进行声音克隆。每次生成可能产生实际费用；生成素材先保留 Rights=UNKNOWN，必须通过普通 Material Gate 后才能交给 Hypit。</p>
          <div className="film-op-grid">
            <label>当前阻塞 Need
              <select className="field" value={generationNeedId} onChange={(event) => setGenerationNeedId(event.target.value)}>
                <option value="">选择一个阻塞 Need</option>
                {blockingNeedIds.map((needId) => <option value={needId} key={needId}>{needId}</option>)}
              </select>
            </label>
          </div>
          <div className="film-op-actions">
            <button className="btn btn-primary" disabled={!operatorSessionReady || !attemptId || !!busy
              || !generationNeedId || materialGate.status !== 'MATERIAL_NOT_READY'} onClick={() => {
              if (!window.confirm('将按所选 Material Need 调用 MiniMax 生成图片、视频或脚本语音，并保存到当前 Attempt。该 API 按平台价格计费，Easel 不提供消费上限。确认继续？')) return;
              const requestId = globalThis.crypto.randomUUID();
              void run('MiniMax 生成素材', async () => {
                const result = await generateMiniMaxMaterial(attemptId, generationNeedId, requestId);
                setGenerationResult(record(result).generation);
                setGenerationNeedId('');
                return result;
              });
            }}>确认费用并生成素材</button>
          </div>
          {generationResult !== null && <details open><summary>最近一次 MiniMax 生成记录</summary><pre>{json(generationResult)}</pre></details>}
        </section>

        <section className="card film-op-card">
          <h2>素材来源与 Rights 核验</h2>
          <p>这里只记录你提交的素材级来源与权利证据，不由 Easel 根据 Provider 推断许可。请按素材 SHA 对应的实际条款核对；证据不足时保留 UNKNOWN，Gate 会继续阻断。提交后只本地重算当前 Gate，不重新搜索或生成素材。</p>
          {rightsCandidates.length === 0 ? <p>当前 Plan/Bundle 中没有字节校验通过且技术检查通过的可核验素材。</p> : <>
            <label>待核素材
              <select className="field" value={rightsAssetId} onChange={(event) => setRightsAssetId(event.target.value)}>
                {rightsCandidates.map((item) => <option key={String(item.asset_id)} value={String(item.asset_id)}>
                  {String(item.provider ?? item.source_kind)} · {String(item.media_type)} · {String(item.asset_id)} · Rights {text(record(item.rights).status)}
                </option>)}
              </select>
            </label>
            {selectedRightsCandidate && <>
              <small>SHA-256：{text(selectedRightsCandidate.asset_sha256)} · Provider：{text(selectedRightsCandidate.provider)} · 来源页：{text(selectedRightsCandidate.source_page)} · 创作者：{text(selectedRightsCandidate.creator)}</small>
              <small>同类型 Plan Need（仅供核验上下文，实际匹配仍由 Gate 计算）：{json(selectedRightsCandidate.needs)}</small>
              <label>核验结论
                <select className="field" value={rightsStatus} onChange={(event) => setRightsStatus(event.target.value)}>
                  <option value="UNKNOWN">UNKNOWN：暂无法确认，继续阻断</option>
                  <option value="KNOWN">KNOWN：已核验许可与用途</option>
                  <option value="PUBLIC_DOMAIN">PUBLIC_DOMAIN：已核验公有领域依据</option>
                  <option value="ATTRIBUTION_REQUIRED">ATTRIBUTION_REQUIRED：可用但必须署名</option>
                  <option value="RESTRICTED">RESTRICTED：限制使用</option>
                </select>
              </label>
              <div className="film-op-grid">
                <label>License 名称<input className="field" value={rightsLicenseName} onChange={(event) => setRightsLicenseName(event.target.value)} /></label>
                <label>License URL<input className="field" value={rightsLicenseUrl} onChange={(event) => setRightsLicenseUrl(event.target.value)} /></label>
                <label>来源创作者<input className="field" value={rightsSourceCreator} onChange={(event) => setRightsSourceCreator(event.target.value)} /></label>
                <label>来源页面<input className="field" value={rightsSourcePage} onChange={(event) => setRightsSourcePage(event.target.value)} /></label>
                <label>证据类型<input className="field" value={rightsEvidenceKind} onChange={(event) => setRightsEvidenceKind(event.target.value)} /></label>
                <label>证据引用（URL/条款定位）<input className="field" value={rightsEvidenceReference} onChange={(event) => setRightsEvidenceReference(event.target.value)} /></label>
                <label>证据摘要<input className="field" value={rightsEvidenceSummary} onChange={(event) => setRightsEvidenceSummary(event.target.value)} /></label>
                <label>用途限制（每行一项）<textarea className="field" rows={2} value={rightsUsageConstraints} onChange={(event) => setRightsUsageConstraints(event.target.value)} /></label>
                <label className="film-op-confirm"><input type="checkbox" checked={rightsAttributionRequired} onChange={(event) => setRightsAttributionRequired(event.target.checked)} /> 该素材需要署名</label>
                <label>准确署名文本<input className="field" value={rightsAttributionText} onChange={(event) => setRightsAttributionText(event.target.value)} /></label>
              </div>
              <label className="film-op-confirm">
                <input type="checkbox" checked={rightsConfirmed} onChange={(event) => setRightsConfirmed(event.target.checked)} />
                我已按上述素材 SHA 核对证据与使用范围；这是我的事实录入，不是系统自动法律判断。
              </label>
              <button className="btn btn-primary" disabled={!operatorSessionReady || !!busy || !rightsConfirmed
                || !rightsEvidenceKind.trim() || !rightsEvidenceReference.trim() || !rightsEvidenceSummary.trim()} onClick={() => {
                void run('记录 Rights 并重算 Gate', () => reviewMaterialRights(attemptId, {
                  assetId: rightsAssetId,
                  assetSha256: selectedRightsCandidate.asset_sha256,
                  rights: {
                    status: rightsStatus,
                    license_name: rightsLicenseName.trim() || null,
                    license_url: rightsLicenseUrl.trim() || null,
                    attribution_required: rightsAttributionRequired || rightsStatus === 'ATTRIBUTION_REQUIRED',
                    attribution_text: rightsAttributionText.trim() || null,
                    usage_constraints: rightsUsageConstraints.split('\n').map((value) => value.trim()).filter(Boolean),
                    evidence: [{ kind: rightsEvidenceKind.trim(), reference: rightsEvidenceReference.trim(), summary: rightsEvidenceSummary.trim() }],
                  },
                  sourceCreator: rightsSourceCreator.trim() || null,
                  sourcePage: rightsSourcePage.trim() || null,
                  confirmReview: true,
                }));
              }}>记录核验事实并重算 Material Gate</button>
            </>}
          </>}
        </section>

        <section className="card film-op-card">
          <h2>Hypit Runtime / Plan / Pricing / Build</h2>
          <p>Hypit Pricing 未提供可验证的聚合总价时会显示 UNKNOWN。批准金额是操作员继续执行的授权记录，不是消费硬上限。</p>
          <label>Hypit Run 路径（相对 Attempt workspace）
            <input className="field" value={runPath} onChange={(event) => setRunPath(event.target.value)} />
          </label>
          <div className="film-op-actions">
            {action('解析服务端 Runtime', () => resolveFilmRuntime(attemptId), 'btn', attemptStatus.runtime_status === 'CONFIGURED')}
            {action('Hypit check + plan', () => validateFilmAttempt(attemptId, runPath.trim()), 'btn',
              !runPath.trim() || !['AUTHORING_READY', 'PLAN_FAILED'].includes(String(attemptStatus.authoring_status))
              || attemptStatus.execution_status !== 'NOT_SUBMITTED')}
            {action('读取 Pricing', () => estimateFilmAttempt(attemptId), 'btn',
              plan.status !== 'ready' || attemptStatus.execution_status !== 'NOT_SUBMITTED')}
          </div>
          <div className="film-op-grid">
            <label>Build 批准金额 USD<input className="field" inputMode="decimal" value={budget} onChange={(event) => setBudget(event.target.value)} /></label>
            <label>Build 标题<input className="field" value={buildTitle} onChange={(event) => setBuildTitle(event.target.value)} /></label>
          </div>
          <div className="film-op-actions">
            <button className="btn btn-primary" disabled={!operatorSessionReady || !!busy || !buildTitle.trim()
              || cost.status !== 'pricing_read' || plan.status !== 'ready'
              || attemptStatus.execution_status !== 'NOT_SUBMITTED' || !(Number(budget) > 0)} onClick={() => {
              if (!window.confirm('确认按当前 Plan/Pricing 提交 Hypit Build？该操作可能产生费用。填写的批准金额只是授权记录，不是服务商硬消费上限；服务器会复核 fingerprint 并阻止重复提交。')) return;
              void run('确认预算并提交 Hypit Build', async () => {
                if (cost.approved !== true) await approveFilmCost(attemptId, Number(budget));
                return submitFilmBuild(attemptId, buildTitle.trim());
              });
            }}>确认预算并生成视频</button>
            {action('刷新 Build 状态', () => refreshFilmBuild(attemptId), 'btn', !build.build_id)}
            {action('查看 Build 详情', async () => { setInspectResult(await inspectFilmBuild(attemptId)); }, 'btn', !build.build_id)}
            <button className="btn btn-danger" disabled={!operatorSessionReady || !!busy || !build.build_id
              || ['BUILD_COMPLETE', 'BUILD_FAILED', 'CANCELLED'].includes(String(attemptStatus.execution_status))} onClick={() => {
              if (!window.confirm('向 Hypit 请求取消当前 Build？')) return;
              void run('请求取消 Build', () => cancelFilmBuild(attemptId));
            }}>请求取消 Build</button>
          </div>
          {(attemptStatus.execution_status === 'SUBMITTING' || attemptStatus.execution_status === 'SUBMISSION_UNCERTAIN') && (
            <div className="film-op-reconcile">
              <h3>提交结果待对账</h3>
              <p>在对账明确前禁止重新提交 Build。</p>
              <div className="film-op-grid">
                <label>已知 Build ID（可选）<input className="field" value={buildIdInput} onChange={(event) => setBuildIdInput(event.target.value)} /></label>
                <label>Hypit Output 名称（可选）<input className="field" value={reconcileOutputName} onChange={(event) => setReconcileOutputName(event.target.value)} /></label>
              </div>
              {action('对账 Hypit Build', () => reconcileFilmBuild(attemptId, {
                ...(buildIdInput.trim() ? { buildId: buildIdInput.trim() } : {}),
                ...(reconcileOutputName.trim() ? { outputName: reconcileOutputName.trim() } : {}),
              }))}
            </div>
          )}
          <div className="film-op-grid film-op-details">
            <details><summary>Plan</summary><pre>{json(plan)}</pre></details>
            <details><summary>Pricing / Persistent Approval</summary><pre>{json(cost)}</pre></details>
            <details><summary>Build</summary><pre>{json(build)}</pre></details>
          </div>
          {inspectResult !== null && <details open><summary>Hypit Inspect</summary><pre>{json(inspectResult)}</pre></details>}
        </section>

        <section className="card film-op-card">
          <h2>Export / Review / Selected Output</h2>
          <div className="film-op-grid">
            <label>导出 Hypit Output 名称<input className="field" value={exportName} onChange={(event) => setExportName(event.target.value)} /></label>
            <label>Review 的已导出文件
              <select className="field" value={reviewOutputName} onChange={(event) => {
                setReviewOutputName(event.target.value);
              }}>
                <option value="">选择导出文件</option>
                {outputNames.map((name) => <option value={name} key={name}>{name}</option>)}
              </select>
            </label>
          </div>
          <div className="film-op-actions">
            {action('导出 Hypit Output', () => exportFilmOutput(attemptId, exportName.trim()), 'btn',
              attemptStatus.execution_status !== 'BUILD_COMPLETE' || !exportName.trim() || outputNames.includes(exportName.trim()))}
          </div>
          {reviewOutputName && typeof selectedReviewOutput.sha256 === 'string' && <p className="film-op-hash">Review SHA-256：{selectedReviewOutput.sha256}</p>}
          {typeof selectedReviewOutput.path === 'string' && (
            <video className="film-op-preview" controls preload="metadata" src={mediaUrl(selectedReviewOutput.path)}>
              浏览器不支持视频预览。
            </video>
          )}
          {selectedReviewOutput.attribution != null && <details><summary>该输出的 Attribution</summary><pre>{json(selectedReviewOutput.attribution)}</pre></details>}
          <div className="film-op-actions">
            <button className="btn btn-primary" disabled={!operatorSessionReady || !!busy || !creationId || !reviewOutputName
              || typeof selectedReviewOutput.sha256 !== 'string'} onClick={() => {
              void run('批准并选定成片', async () => {
                await reviewFilmOutput(attemptId, {
                  outputName: reviewOutputName,
                  sha256: String(selectedReviewOutput.sha256),
                  truth: { status: 'pass', notes: [] },
                  style: { status: 'pass', notes: [] },
                  human: { status: 'approved' },
                  feedback: [],
                });
                return selectFilmBuild(creationId, attemptId, reviewOutputName);
              });
            }}>我看过并批准，设为最终视频</button>
          </div>
          <p className="film-op-manual">一次批准同时记录内容边界、风格和成片审核，并选定当前 SHA；不会自动发布。</p>
          <div className="film-op-details">
            {outputsForSelect.map(({ name, item }) => <details key={name}><summary>{name} · {text(item.sha256)}</summary><pre>{json(item)}</pre></details>)}
          </div>
        </section>
      </>}
      </details>
    </div>
  );
}
