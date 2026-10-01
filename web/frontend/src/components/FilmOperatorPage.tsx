import { useCallback, useEffect, useRef, useState } from 'react';
import {
  approveFilmCost, cancelFilmBuild, createOperatorSession, reviseFilmOutput, previewCreatorProposal,
  estimateFilmAttempt, exportFilmOutput, fetchCreation, fetchFilmAttempt, fetchScriptTruth, generateMiniMaxMaterial, inspectFilmBuild, mediaUrl,
  fetchMaterialRightsCandidates, listFilmAttempts, reconcileFilmBuild, startFilmAuthoring,
  refreshFilmBuild, resolveFilmRuntime, retryFailedFilmBuild, reviewFilmOutput, reviewMaterialRights, reviewScriptTruth, selectFilmBuild, submitFilmBuild,
  fetchPromotableMaterials, promoteAttemptMaterial,
  materialAssetPreviewUrl, reviewMaterialMatch, recoverFilmMaterials,
  validateFilmAttempt, retryCreationDelivery,
} from '../lib/api';
import { projectCreatorWorkspace, stageLabels } from '../lib/creatorWorkspace';
import type { ChatMessage } from '../lib/store';
import type { OperatorRecord, GenerationBudget } from '../lib/api';

type JsonRecord = Record<string, unknown>;
const record = (value: unknown): JsonRecord =>
  value !== null && typeof value === 'object' && !Array.isArray(value) ? value as JsonRecord : {};
const text = (value: unknown, fallback = '—') => typeof value === 'string' && value ? value : fallback;
const json = (value: unknown) => JSON.stringify(value ?? null, null, 2);
const operationError = (error: unknown) => error instanceof Error ? error.message : '操作失败';

interface FilmOperatorPageProps {
  creationId: string;
  title: string;
  onContinuePreparation: () => void;
  continuationBusy: boolean;
  proposalPhase?: boolean;
  proposalReady?: boolean;
  proposalMessages?: ChatMessage[];
  onConfirmProduction?: (budget?: GenerationBudget) => void;
  progressOpen?: boolean;
  onProjection?: (value: { title: string; pending: number }) => void;
  onOpenConversation?: () => void;
}

export default function FilmOperatorPage({ creationId, title, onContinuePreparation, continuationBusy, proposalPhase = false, proposalReady = false, proposalMessages = [], onConfirmProduction, progressOpen = false, onProjection, onOpenConversation }: FilmOperatorPageProps) {
  const [materialSearchTerms, setMaterialSearchTerms] = useState<Record<string, string>>({});
  const materialRecoveryRequest = useRef<{ id: string; payload: string } | null>(null);
  const [proposalPreview, setProposalPreview] = useState<OperatorRecord | null>(null);
  const [generationCeiling, setGenerationCeiling] = useState('');
  useEffect(() => { setGenerationCeiling(''); }, [creationId]);
  const [proposalPreviewError, setProposalPreviewError] = useState('');
  const [previewContext, setPreviewContext] = useState('');
  const proposalContext = JSON.stringify(proposalMessages.slice(-48).map(({ role, content }) => ({ role, content })));
  useEffect(() => {
    if (!proposalPhase) return;
    let cancelled = false; setProposalPreview(null);
    previewCreatorProposal(creationId, JSON.parse(proposalContext))
      .then(value => { if (!cancelled) { setProposalPreview(value); setPreviewContext(proposalContext); setProposalPreviewError(''); } })
      .catch((reason: unknown) => { if (!cancelled) setProposalPreviewError(operationError(reason)); });
    return () => { cancelled = true; };
  }, [creationId, proposalPhase, proposalContext]);
  const generationOffer = record(proposalPreview?.generation_budget);
  const generationScope = record(generationOffer.scope);
  const generationAmount = Number(generationCeiling);
  const invalidGenerationBudget = generationCeiling !== '' && (!Number.isFinite(generationAmount) || generationAmount <= 0 || generationAmount > 1000 || !/^\d+(\.\d{1,2})?$/.test(generationCeiling) || !generationOffer.available);
  const proposalSpecifications = record(proposalPreview?.specs);
  const proposalMissing = Array.isArray(proposalPreview?.missing) ? proposalPreview.missing : [];
  const [creationSnapshot, setCreationSnapshot] = useState<OperatorRecord | null>(null);
  const [attempts, setAttempts] = useState<OperatorRecord[]>([]);
  const [attemptId, setAttemptId] = useState('');
  useEffect(() => { materialRecoveryRequest.current = null; setMaterialSearchTerms({}); }, [attemptId]);
  const [attempt, setAttempt] = useState<OperatorRecord | null>(null);
  const [scriptTruth, setScriptTruth] = useState<OperatorRecord | null>(null);
  const [scriptTruthConfirmed, setScriptTruthConfirmed] = useState(false);
  const [finalReviewConfirmed, setFinalReviewConfirmed] = useState(false);
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
  const [creationConnectionError, setCreationConnectionError] = useState('');
  const [attemptConnectionError, setConnectionError] = useState('');
  const [attemptListError, setAttemptListError] = useState('');
  const connectionError = creationConnectionError || attemptConnectionError || attemptListError;
  const [lastSynced, setLastSynced] = useState('');
  const [feedbackText, setFeedbackText] = useState('');
  const [feedbackTime, setFeedbackTime] = useState('');
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [feedbackKind, setFeedbackKind] = useState('general');
  const [notice, setNotice] = useState('');
  const [refreshVersion, setRefreshVersion] = useState(0);
  const [inspectResult, setInspectResult] = useState<unknown>(null);
  const [generationNeedId, setGenerationNeedId] = useState('');
  const [generationResult, setGenerationResult] = useState<unknown>(null);
  const [rightsCandidates, setRightsCandidates] = useState<OperatorRecord[]>([]);
  const [rightsCandidatesLoaded, setRightsCandidatesLoaded] = useState(false);
  const [voiceRightsDecision, setVoiceRightsDecision] = useState('UNKNOWN');
  const [voiceTermsName, setVoiceTermsName] = useState('');
  const [voiceEvidenceReference, setVoiceEvidenceReference] = useState('');
  const [voiceEvidenceSummary, setVoiceEvidenceSummary] = useState('');
  const [voiceCredit, setVoiceCredit] = useState('');
  const [voiceCreator, setVoiceCreator] = useState('');
  const [voiceSourcePage, setVoiceSourcePage] = useState('');
  const [voiceRestrictions, setVoiceRestrictions] = useState('');
  const [voiceRightsConfirmed, setVoiceRightsConfirmed] = useState(false);
  const [visualAssetId, setVisualAssetId] = useState('');
  const [visualNeedId, setVisualNeedId] = useState('');
  const [visualObservation, setVisualObservation] = useState('');
  const [visualLogo, setVisualLogo] = useState('unknown');
  const [visualText, setVisualText] = useState('unknown');
  const [visualConfirmed, setVisualConfirmed] = useState(false);
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
  const preparationInFlight = useRef('');
  const pageAlive = useRef(true);
  const activeAttempt = useRef(attemptId);
  activeAttempt.current = attemptId;
  useEffect(() => { pageAlive.current = true; return () => { pageAlive.current = false; }; }, []);
  const exportRun = useRef('');
  const exportInFlight = useRef('');
  const reconciliationRun = useRef('');
  const manualAttemptSelection = useRef(false);
  const advancedRef = useRef<HTMLDetailsElement>(null);

  const reviewOutputSha = record(record(attempt?.outputs)[reviewOutputName]).sha256;
  useEffect(() => { setFinalReviewConfirmed(false); }, [attemptId, reviewOutputName, reviewOutputSha]);
  useEffect(() => { setScriptTruthConfirmed(false); }, [attemptId, scriptTruth?.script_sha256, scriptTruth?.truth_packet_sha256]);

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
      if (!cancelled) { setCreationSnapshot(item as unknown as OperatorRecord); setCreationConnectionError(''); setLastSynced(new Date().toLocaleString('zh-CN')); }
    }).catch((reason: unknown) => { if (!cancelled) setCreationConnectionError(operationError(reason)); });
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
      setAttempts(items); setAttemptListError('');
      setAttemptId((current) => items.some((item) => item.attempt_id === current)
        ? current : text(items[0]?.attempt_id, ''));
    }).catch((reason: unknown) => {
      if (!cancelled) setAttemptListError(operationError(reason));
    });
    return () => { cancelled = true; };
  }, [operatorSessionReady, creationId, refreshVersion]);

  useEffect(() => {
    if (!operatorSessionReady || !creationId) return;
    const timer = window.setInterval(() => setRefreshVersion((version) => version + 1), 5000);
    return () => window.clearInterval(timer);
  }, [operatorSessionReady, creationId]);

  useEffect(() => {
    if (!operatorSessionReady || !attemptId) {
      setAttempt(null);
      return;
    }
    let cancelled = false;
    fetchFilmAttempt(attemptId).then((item) => {
      if (cancelled) return;
      setAttempt(item); setConnectionError(''); setLastSynced(new Date().toLocaleString('zh-CN'));
      const authoring = record(item.authoring);
      const plan = record(item.plan);
      setRunPath(text(authoring.run_path, text(plan.run_path, 'productions/easel-authoring/run.sv')));
      const names = Object.keys(record(item.outputs));
      setReviewOutputName((current) => names.includes(current) ? current : names[0] || '');
    }).catch((reason: unknown) => { if (!cancelled) setConnectionError(operationError(reason)); });
    return () => { cancelled = true; };
  }, [operatorSessionReady, attemptId, refreshVersion]);

  const savedProposalStatus = record(creationSnapshot?.chat_workflow).proposal_status;
  const delivery = record(creationSnapshot?.delivery);
  const backendDelivery = delivery.schema === 'easel-creation-delivery@1';
  const generationGrant = record(record(delivery.authorization).material_generation);
  const heldGenerationCost = Object.values(record(delivery.material_generations)).map(record).reduce((sum, item) => sum + Number(record(item.quote).upper_estimate ?? 0), 0);
  const legacyDelivery = creationSnapshot !== null && !backendDelivery;
  const showingProposal = attemptId ? false : typeof savedProposalStatus === 'string'
    ? savedProposalStatus !== 'CONFIRMED' : proposalPhase;
  const currentProposalText = [...proposalMessages].reverse().find(message => message.role === 'assistant')?.content;
  const rightsGateStatus = record(record(attempt).material_gate).status;
  const rightsBundleRevision = record(record(attempt).material_gate).bundle_revision;
  useEffect(() => {
    if (!operatorSessionReady || !attemptId || (!advancedOpen && rightsGateStatus !== 'MATERIAL_NOT_READY')) {
      setRightsCandidates([]);
      setRightsCandidatesLoaded(false);
      return;
    }
    let cancelled = false;
    fetchMaterialRightsCandidates(attemptId).then((items) => {
      if (!cancelled) {
        setRightsCandidates(items);
        setRightsCandidatesLoaded(true);
        setRightsAssetId((current) => items.some((item) => item.asset_id === current)
          ? current : text(items.find((item) => item.media_type === 'audio' && item.provider === 'minimax'
            && record(item.rights).status === 'UNKNOWN')?.asset_id, text(items[0]?.asset_id, '')));
      }
    }).catch((reason: unknown) => { if (!cancelled) setError(operationError(reason)); });
    return () => { cancelled = true; };
  }, [operatorSessionReady, attemptId, refreshVersion, advancedOpen,
    rightsGateStatus, rightsBundleRevision]);

  useEffect(() => {
    if (!operatorSessionReady || !attemptId) { setScriptTruth(null); return; }
    let cancelled = false;
    fetchScriptTruth(attemptId).then((ledger) => {
      if (!cancelled) {
        setScriptTruth(ledger);
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
  const preparationStatus = text(record(creationSnapshot?.preparation).status, '');
  const materialPlan = record(attemptStatus.material_planning);
  const blockingNeedIds = Array.isArray(materialGate.blocking_needs)
    ? materialGate.blocking_needs.filter((value): value is string => typeof value === 'string') : [];
  const pendingVoiceNeed = Array.isArray(scriptTruth?.material_needs)
    ? scriptTruth.material_needs.map(record).find(need => blockingNeedIds.includes(text(need.need_id))
      && need.media_type === 'audio' && need.modality_kind === 'voice' && need.generation_allowed === true)
    : undefined;
  const missingSupplyNeeds = Array.isArray(scriptTruth?.material_needs)
    ? scriptTruth.material_needs.map(record).filter(need => blockingNeedIds.includes(text(need.need_id))
      && need.need_id !== pendingVoiceNeed?.need_id
      && !rightsCandidates.some(asset => asset.media_type === need.media_type
        && (!need.required_source_kind || asset.source_kind === need.required_source_kind)
        && (!need.forbidden_source_kind || asset.source_kind !== need.forbidden_source_kind)
        && Array.isArray(asset.needs) && asset.needs.some(value => record(value).need_id === need.need_id)))
    : [];
  const scriptClaims = Array.isArray(scriptTruth?.claims) ? scriptTruth.claims.map(record) : [];
  const scriptReviewCounts = {
    sourceSupported: scriptClaims.filter((claim) => claim.status === 'TRUTH_SUPPORTED').length,
    autoReviewed: scriptClaims.filter((claim) => claim.status === 'AUTO_REVIEWED' || claim.status === 'FICTION_MARKED').length,
    delegated: scriptClaims.filter((claim) => claim.status === 'DELEGATE_REVIEWED').length,
    system: scriptClaims.filter((claim) => claim.status === 'SYSTEM_REVIEWED').length,
    human: scriptClaims.filter((claim) => claim.status === 'HUMAN_REVIEWED').length,
    pending: scriptClaims.filter((claim) => claim.status === 'REVIEW_REQUIRED').length,
  };
  const plan = record(attemptStatus.plan);
  const cost = record(attemptStatus.cost);
  const build = record(attemptStatus.build);
  const outputs = record(attemptStatus.outputs);
  const outputNames = Object.keys(outputs);
  const selectedReviewOutput = record(outputs[reviewOutputName]);
  const rawSystemReview = record(record(attempt?.review).system);
  const systemReview = record(rawSystemReview.binding).sha256 === selectedReviewOutput.sha256
    && record(rawSystemReview.binding).output_name === reviewOutputName ? rawSystemReview : {};
  const rightsReviewCandidates = rightsCandidates.filter(item =>
    ['UNKNOWN', 'RESTRICTED'].includes(text(record(item.rights).status))
    || (Array.isArray(item.rights_blocking_need_ids) && item.rights_blocking_need_ids.some(id => blockingNeedIds.includes(text(id)))));
  const selectedRightsCandidate = rightsReviewCandidates.find(item => item.asset_id === rightsAssetId) ?? rightsReviewCandidates[0];
  const pendingVoiceCandidate = rightsCandidates.find((item) => item.media_type === 'audio'
    && item.provider === 'minimax' && record(item.rights).status === 'UNKNOWN');
  const voiceRightsPending = !!pendingVoiceCandidate;
  const existingVoiceCandidate = rightsCandidates.find(item => item.media_type === 'audio'
    && Array.isArray(item.generation_need_ids) && item.generation_need_ids.includes(pendingVoiceNeed?.need_id));
  const [voiceListeningObservation, setVoiceListeningObservation] = useState('');
  const pendingMusicNeed = Array.isArray(scriptTruth?.material_needs)
    ? scriptTruth.material_needs.map(record).find(need => need.modality_kind === 'bgm'
      && blockingNeedIds.includes(text(need.need_id))) : undefined;
  const musicCandidates = rightsCandidates.filter(asset => asset.media_type === 'audio'
    && asset.source_kind !== 'generative'
    && (!pendingMusicNeed?.required_source_kind || asset.source_kind === pendingMusicNeed.required_source_kind)
    && (!pendingMusicNeed?.forbidden_source_kind || asset.source_kind !== pendingMusicNeed.forbidden_source_kind));
  const [musicAssetId, setMusicAssetId] = useState('');
  const [musicObservation, setMusicObservation] = useState('');
  const selectedMusic = musicCandidates.find(asset => asset.asset_id === musicAssetId) ?? musicCandidates[0];
  const musicIdentity = `${selectedMusic?.asset_id}:${selectedMusic?.asset_sha256}:${pendingMusicNeed?.need_id}`;
  useEffect(() => { setMusicObservation(''); }, [musicIdentity]);
  const visualPool = rightsCandidates.filter(item => ['image', 'video'].includes(String(item.media_type)));
  const selectedVisualNeeds = Array.from(new Map(visualPool.flatMap(item => Array.isArray(item.needs) ? item.needs.map(record) : [])
    .filter(need => blockingNeedIds.includes(text(need.need_id)) && !visualPool.some(asset =>
      [asset.semantic_reviewed_need_ids, asset.system_observed_need_ids].some(ids => Array.isArray(ids) && ids.includes(need.need_id))))
    .map(need => [text(need.need_id), need])).values());
  const selectedVisualNeed = selectedVisualNeeds.find(item => item.need_id === visualNeedId) ?? selectedVisualNeeds[0];
  const visualCandidates = visualPool.filter(item => Array.isArray(item.needs)
    && item.needs.some(need => record(need).need_id === selectedVisualNeed?.need_id));
  const selectedVisual = visualCandidates.find(item => item.asset_id === visualAssetId) ?? visualCandidates[0];
  const selectedVisualConstraints = record(selectedVisualNeed?.constraints);
  const visualIdentity = `${selectedVisual?.asset_id}:${selectedVisual?.asset_sha256}:${selectedVisualNeed?.need_id}`;
  useEffect(() => {
    setVisualObservation(''); setVisualLogo('unknown'); setVisualText('unknown'); setVisualConfirmed(false);
  }, [visualIdentity]);
  const rightsSnapshot = JSON.stringify(selectedRightsCandidate ?? {});
  useEffect(() => {
    const candidate = record(JSON.parse(rightsSnapshot));
    const rights = record(candidate.rights);
    setRightsStatus(text(rights.status, 'UNKNOWN')); setRightsLicenseName(text(rights.license_name, ''));
    setRightsLicenseUrl(text(rights.license_url, '')); setRightsSourceCreator(text(candidate.creator, ''));
    setRightsSourcePage(text(candidate.source_page, ''));
    setRightsAttributionRequired(rights.attribution_required === true); setRightsAttributionText(text(rights.attribution_text, ''));
    setRightsUsageConstraints(Array.isArray(rights.usage_constraints) ? rights.usage_constraints.join('\n') : '');
    const evidence = Array.isArray(rights.evidence) ? record(rights.evidence[0]) : {};
    setRightsEvidenceKind(text(evidence.kind, 'asset_license')); setRightsEvidenceReference(text(evidence.reference, ''));
    setRightsEvidenceSummary(text(evidence.summary, '')); setRightsConfirmed(false);
  }, [rightsSnapshot]);
  const visualReviewReady = !!selectedVisual && !!selectedVisualNeed && visualObservation.trim().length >= 8
    && visualConfirmed && (selectedVisualConstraints.logo !== false || visualLogo !== 'unknown')
    && (selectedVisualConstraints.text_in_frame !== false || visualText !== 'unknown');
  const voiceAttributionRequired = voiceRightsDecision === 'ATTRIBUTION_REQUIRED';
  const voiceReviewReady = !!pendingVoiceCandidate && voiceRightsConfirmed
    && voiceRightsDecision !== 'UNKNOWN' && !!voiceEvidenceReference.trim() && !!voiceEvidenceSummary.trim()
    && (!['KNOWN', 'ATTRIBUTION_REQUIRED'].includes(voiceRightsDecision) || !!voiceTermsName.trim())
    && (!voiceAttributionRequired || (!!voiceCredit.trim() && !!voiceCreator.trim() && !!voiceSourcePage.trim()));
  const brief = record(record(attemptStatus.production_request).production_brief);
  const selectedOutput = creationSnapshot?.selected_attempt_id === attemptId
    && typeof creationSnapshot?.selected_output_name === 'string';
  const allLocalNoCharge = cost.estimated_usd === 0 && record(cost.total).status === 'known';
  const estimatedCost = typeof cost.estimated_usd === 'number' ? cost.estimated_usd : null;
  const canApproveCost = allLocalNoCharge || estimatedCost !== null;
  const declaredBudget = typeof cost.max_budget_usd === 'number' ? cost.max_budget_usd : null;
  const requestedBudget = allLocalNoCharge ? 0 : Number(budget);
  const budgetAllowed = (requestedBudget > 0 || allLocalNoCharge) && (declaredBudget === null || requestedBudget <= declaredBudget);
  const currentOutput = reviewOutputName && typeof selectedReviewOutput.path === 'string';
  const execution = text(attemptStatus.execution_status, 'NOT_SUBMITTED');
  const projection = projectCreatorWorkspace(creationSnapshot, attempt, scriptTruth, rightsCandidates);
  const phase = selectedOutput ? 'done'
    : attemptStatus.review_status === 'APPROVED' ? 'selecting'
    : projection.failureStage && projection.failureStage !== '内容准备' ? 'failed'
    : currentOutput ? 'review'
    : execution === 'BUILD_COMPLETE' ? 'exporting'
    : ['SUBMITTING', 'SUBMISSION_UNCERTAIN'].includes(execution) ? 'verifying'
    : ['SUBMITTING', 'SUBMISSION_UNCERTAIN', 'SUBMITTED', 'RUNNING', 'CANCEL_REQUESTED'].includes(execution) ? 'building'
    : scriptTruth?.status === 'REVIEW_REQUIRED' ? 'content-review'
    : materialGate.status === 'MATERIAL_NOT_READY' ? 'material'
    : projection.failureStage === '内容准备' ? 'preparation-failed'
    : plan.status === 'ready' && cost.status === 'pricing_read' && execution === 'NOT_SUBMITTED' ? 'ready'
    : materialGate.status === 'MATERIAL_READY' ? 'preparing' : 'planning';
  const phaseTitle: Record<string, string> = {
    done: '最终成片已确认', selecting: '成片已通过审核', review: '视频制作完成',
    exporting: '正在整理成片', verifying: '正在确认制作进度', building: '正在制作视频', failed: projection.title,
    'content-review': '请确认视频内容', material: '素材还需要确认', 'preparation-failed': '内容准备遇到问题',
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
    material: '当前素材还不能用于制作。请先处理下方列出的素材缺口。',
    'preparation-failed': '准备过程暂时中断，作品和已完成的内容已保留。',
    ready: '内容和素材都已准备好。确认后 Easel 会开始制作视频。',
    preparing: '内容和素材已准备，Easel 正在安排画面与节奏。',
    planning: 'Easel 正在理解创作意图，整理内容和素材。',
  };
  const timelineSteps = projection.timeline;
  const timelineStateLabel = stageLabels;
  useEffect(() => { onProjection?.({ title: connectionError ? '连接中断 · 显示最后状态' : projection.title, pending: projection.pending }); },
    [onProjection, projection.title, projection.pending, connectionError]);
  const isBlocked = attemptStatus.execution_status === 'BLOCKED'
    || materialGate.status === 'MATERIAL_NOT_READY';
  const shouldAutoTrack = operatorSessionReady && !!attemptId && (
    attemptStatus.authoring_status === 'AUTHORING_RUNNING'
    || ['PENDING', 'READY_FOR_EXTERNAL_AUTHORING'].includes(text(attemptStatus.authoring_status))
    || ['SUBMITTING', 'SUBMISSION_UNCERTAIN', 'SUBMITTED', 'RUNNING', 'CANCEL_REQUESTED'].includes(text(attemptStatus.execution_status))
  );

  useEffect(() => {
    if (!legacyDelivery || !shouldAutoTrack) return;
    let cancelled = false;
    let refreshing = false;
    const poll = async () => {
      if (cancelled || refreshing) return;
      refreshing = true;
      try {
        const current = attemptStatus.authoring_status === 'AUTHORING_RUNNING' || !build.build_id
          ? await fetchFilmAttempt(attemptId) : await refreshFilmBuild(attemptId);
        if (!cancelled) {
          setAttempt(current as unknown as OperatorRecord); setConnectionError(''); setLastSynced(new Date().toLocaleString('zh-CN'));
          try { setScriptTruth(await fetchScriptTruth(attemptId)); } catch { /* Planning may not have produced a script yet. */ }
        }
      } catch (reason: unknown) {
        if (!cancelled) setConnectionError(operationError(reason));
      } finally {
        refreshing = false;
      }
    };
    const timer = window.setInterval(() => { void poll(); }, 5000);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [legacyDelivery, attemptId, shouldAutoTrack, attemptStatus.authoring_status, build.build_id]);

  useEffect(() => {
    if (!legacyDelivery || !operatorSessionReady || !attemptId || execution !== 'SUBMISSION_UNCERTAIN'
        || reconciliationRun.current === attemptId) return;
    reconciliationRun.current = attemptId;
    void reconcileFilmBuild(attemptId).then((result) => {
      if (result.status === 'reconciled') setAttempt(record(result.attempt));
      else setError('制作结果仍在核对中；系统不会重复提交。可在高级信息中查看详情。');
    }).catch((reason: unknown) => setError(operationError(reason)));
  }, [legacyDelivery, operatorSessionReady, attemptId, execution]);

  // Preparation, validation and pricing are deterministic product work. They
  // stay behind their formal APIs, without asking the Creator to operate each step.
  useEffect(() => {
    if (!legacyDelivery || showingProposal || !operatorSessionReady || !attemptId || !attempt
        || !['AUTHORING_READY', 'PLANNED'].includes(text(attempt.authoring_status))
        || !['NOT_SUBMITTED', 'BLOCKED'].includes(text(attempt.execution_status))
        || cost.status === 'pricing_read') return;
    const key = `${attemptId}:${text(record(attempt.authoring).authoring_sha256)}:${text(attempt.runtime_status)}:${text(plan.status)}:${text(cost.status)}`;
    if (preparationRun.current === key || preparationInFlight.current === attemptId) return;
    preparationInFlight.current = attemptId;
    preparationRun.current = key;
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
        if (pageAlive.current && activeAttempt.current === attemptId) { setAttempt(current); setError(''); }
      } catch (reason: unknown) {
        if (pageAlive.current && activeAttempt.current === attemptId) setError(operationError(reason));
      } finally {
        preparationInFlight.current = '';
        if (pageAlive.current && activeAttempt.current === attemptId) setBusy('');
      }
    };
    void prepare();
  }, [legacyDelivery, showingProposal, operatorSessionReady, attemptId, attempt, cost.status, plan.status]);

  useEffect(() => {
    if (!legacyDelivery || !operatorSessionReady || !attemptId || execution !== 'BUILD_COMPLETE'
        || Object.keys(outputs).length > 0 || exportRun.current === attemptId || exportInFlight.current === attemptId) return;
    exportRun.current = attemptId; exportInFlight.current = attemptId;
    const exportCompletedBuild = async () => {
      setBusy('整理成片');
      try {
        const inspection = await inspectFilmBuild(attemptId);
        const candidates = record(inspection.build).outputs;
        const target = Array.isArray(candidates)
          ? candidates.map(record).find((item) => item.target === true && item.mediaType === 'video/mp4') : undefined;
        if (typeof target?.name !== 'string') throw new Error('制作结果中没有可导出的视频');
        const updated = await exportFilmOutput(attemptId, target.name);
        if (pageAlive.current && activeAttempt.current === attemptId) { setAttempt(updated); setReviewOutputName(target.name); setError(''); }
      } catch (reason: unknown) {
        if (pageAlive.current && activeAttempt.current === attemptId) setError(operationError(reason));
      } finally {
        exportInFlight.current = '';
        if (pageAlive.current && activeAttempt.current === attemptId) setBusy('');
      }
    };
    void exportCompletedBuild();
  }, [legacyDelivery, operatorSessionReady, attemptId, execution, outputs]);

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
        '恢复视频制作': '已恢复规划、素材和视频编排；新一次制作仍需确认费用。',
      } as Record<string, string>)[label] || `${label}完成`);
      setRefreshVersion((version) => version + 1);
    } catch (reason: unknown) {
      setError(operationError(reason));
    } finally {
      setBusy('');
    }
  }, []);

  const generateForNeed = (needId: string) => {
    if (!window.confirm('将调用 MiniMax 为当前作品生成所需素材。该 API 按平台价格计费，Easel 不提供消费上限。确认继续？')) return;
    const requestId = globalThis.crypto.randomUUID();
    void run('生成素材', async () => {
      const result = await generateMiniMaxMaterial(attemptId, needId, requestId);
      setGenerationResult(record(result).generation);
      setRightsAssetId(text(record(record(result).generation).asset_id, ''));
      setGenerationNeedId('');
      return result;
    });
  };

  const submitVoiceRightsReview = () => {
    if (!pendingVoiceCandidate || !voiceReviewReady) return;
    void run('复核旁白使用权', async () => {
      const result = await reviewMaterialRights(attemptId, {
        assetId: pendingVoiceCandidate.asset_id,
        assetSha256: pendingVoiceCandidate.asset_sha256,
        rights: {
          status: voiceRightsDecision,
          license_name: voiceTermsName.trim() || null,
          license_url: voiceEvidenceReference.trim().startsWith('https://') ? voiceEvidenceReference.trim() : null,
          attribution_required: voiceAttributionRequired,
          attribution_text: voiceAttributionRequired ? voiceCredit.trim() : null,
          usage_constraints: voiceRestrictions.split('\n').map((value) => value.trim()).filter(Boolean),
          evidence: [{ kind: 'asset_license', reference: voiceEvidenceReference.trim(), summary: voiceEvidenceSummary.trim() }],
        },
        sourceCreator: voiceAttributionRequired ? voiceCreator.trim() : null,
        sourcePage: voiceAttributionRequired ? voiceSourcePage.trim() : null,
        confirmReview: true,
      });
      if (record(result).material_status === 'MATERIAL_READY') await startFilmAuthoring(attemptId);
      return result;
    });
  };

  const submitVisualReview = () => {
    if (!selectedVisual || !selectedVisualNeed || !visualReviewReady) return;
    void run('核对画面匹配', async () => {
      const result = await reviewMaterialMatch(attemptId, {
        assetId: selectedVisual.asset_id, assetSha256: selectedVisual.asset_sha256,
        needId: selectedVisualNeed.need_id, observedContent: visualObservation.trim(),
        logoPresent: visualLogo === 'unknown' ? null : visualLogo === 'yes',
        visibleTextPresent: visualText === 'unknown' ? null : visualText === 'yes',
        confirmReview: true,
      });
      setVisualObservation(''); setVisualConfirmed(false);
      if (record(result).material_status === 'MATERIAL_READY') await startFilmAuthoring(attemptId);
      return result;
    });
  };

  const outputsForSelect = outputNames.map((name) => ({ name, item: record(outputs[name]) }));
  const action = (label: string, fn: () => Promise<unknown>, className = 'btn', disabled = false) => (
    <button className={className} disabled={!operatorSessionReady || !attemptId || !!busy || disabled} onClick={() => void run(label, fn)}>
      {busy === label ? '处理中…' : label}
    </button>
  );

  return (
    <div className="film-operator-page">
      {connectionError && <div className="film-op-message is-error" role="status">
        状态更新失败，显示最后一次可信状态。当前是否仍在制作尚未确认。
        <button className="btn btn-sm" onClick={() => setRefreshVersion(version => version + 1)}>重新连接</button>
      </div>}
      {lastSynced && <small>最近状态读取：{lastSynced}</small>}
      {backendDelivery && generationGrant.currency === 'CNY' && <p>自主素材生成额度：已占用 ¥{heldGenerationCost.toFixed(4)} / ¥{String(generationGrant.max_amount)}（按核价保留额度，非实际账单）。</p>}
      {progressOpen && <div className="film-op-progress" aria-label="创作阶段进度">
        {timelineSteps.map(step => <div className={`film-op-progress-step is-${step.state}`} key={step.name}>
          <strong>{step.name}</strong><small>{timelineStateLabel[step.state]}</small>
        </div>)}
      </div>}
      {showingProposal && <section className="card film-op-card film-op-creator">
        <h2>当前创作方案</h2>
        <dl className="creator-proposal-facts">
          <dt>核心表达</dt><dd className="creator-proposal-turn">{currentProposalText || text(creationSnapshot?.idea, title)}</dd>
          <dt>创作方式</dt><dd>{text(creationSnapshot?.creative_mode, '尚未确认，请在对话中确定创作方式')}</dd>
          <dt>本次确认的规格</dt><dd>
            总时长：{proposalSpecifications.duration_seconds == null ? '—' : `${proposalSpecifications.duration_seconds} 秒`}<br />
            画幅：{text(proposalSpecifications.aspect_ratio)}<br />
            音轨：{({ silent: '静音', voice: '旁白', music: '音乐', mixed: '旁白与音乐' } as Record<string, string>)[String(proposalSpecifications.audio_mode)] ?? '—'}<br />
            语言：{({ 'zh-CN': '简体中文', 'zh-TW': '繁体中文', en: '英语' } as Record<string, string>)[String(proposalSpecifications.language)] ?? '—'}
          </dd>
          <dt>创作边界</dt><dd>确认后由 Easel 持续制作，可离开页面。无服务商费用的合成自动执行；如设置下方预算，方案允许的素材生成在核价和额度内自动执行。其他费用、无法核价或超额时再请你处理。不自动发布。</dd>
          <dt>待确认信息</dt><dd>{proposalPreviewError || (!proposalPreview ? '正在核对方案…' : proposalMissing.length ? proposalMissing.join('、') + '；请在对话中明确这些规格。' : '规格已明确，确认后会冻结相同输入。')}</dd>
        </dl>
        {generationOffer.available === true && <div className="film-op-review-claim">
          <label>本次自主素材生成总预算（人民币，可留空）
            <input className="field" type="number" inputMode="decimal" min="0.01" max="1000" step="0.01" value={generationCeiling} onChange={event => setGenerationCeiling(event.target.value)} placeholder="留空则付费生成另行确认" />
          </label>
          <small>允许 MiniMax 为方案需要的图片、视频和预置旁白生成素材；已有素材优先。旁白音色：{text(generationScope.speech_voice_id)}。图片：{text(generationScope.image_model)}；视频：{text(generationScope.video_model)}；旁白：{text(generationScope.speech_model)}。</small>
          <p>每次提交前核对公开单价，累计预计费用不超过此额度；这是 Easel 的执行额度，不是服务商账户扣费硬上限。未核实结果保留额度且不重复购买。使用权仍按实际证据判断。</p>
          {invalidGenerationBudget && <p role="alert">请填写最多两位小数、0～1000 元之间的正预算。</p>}
        </div>}
        <details><summary>查看本次确认的对话依据</summary>
          {proposalMessages.slice(-48).map((message, index) => <p className="creator-proposal-turn" key={index}><strong>{message.role === 'user' ? '你' : 'Easel'}：</strong>{message.content}</p>)}
        </details>
        <p>可在左侧对话中修改方向，确认后进入内容准备。</p>
        <button className="btn btn-primary" disabled={!proposalReady || continuationBusy || !proposalPreview || proposalMissing.length > 0 || !!proposalPreviewError || previewContext !== proposalContext || invalidGenerationBudget} onClick={() => onConfirmProduction?.(generationCeiling ? { maxCostCny: generationAmount, scopeSha256: String(generationOffer.scope_sha256) } : undefined)}>按这个方案制作</button>
      </section>}
      {backendDelivery && Object.values(record(delivery.material_generations)).map(record).filter(item => item.attempt_id === attemptId && ['budget_exceeded', 'quote_unavailable', 'uncertain'].includes(String(item.status))).map(item => <div className="film-op-message is-error" role="status" key={String(item.need_id)}>
        {text(item.reason, '素材生成尚需处理，已保留现有结果。')}
      </div>)}
      {!operatorSessionReady && <p className="page-subtitle">正在连接作品，请稍候…</p>}
      {notice && <div className="film-op-message is-ok" role="status">{notice}</div>}
      {backendDelivery && delivery.status === 'failed' && <section className="card film-op-card" role="alert">
        <h3>制作暂时中断</h3><p>{text(delivery.last_error, '当前步骤未完成')}</p>
        <p>已保留完成的内容和素材。重试只恢复当前步骤；不会重复提交结果未确定的制作，授权外费用会另行确认。</p>
        <button className="btn btn-primary" disabled={!!busy} onClick={() => void run('恢复制作', () => retryCreationDelivery(creationId))}>重试当前步骤</button>
      </section>}
      {error && <div className="film-op-message is-error" role="alert">
        这一步暂时无法继续。{error}
      </div>}

      {backendDelivery && ['execution_uncertain', 'observation_failed'].includes(text(delivery.status)) && <p role="status">
        {delivery.status === 'execution_uncertain' ? '上一次执行是否结束尚未核实。已保留结果，当前不会重复派发。' : '暂时无法取得制作进度，显示最后可信结果；Easel 会继续查询。'}
      </p>}
      {!showingProposal && operatorSessionReady && !attemptId && delivery.status !== 'failed' && <section className="card film-op-card film-op-creator">
        <h2>{projection.title}</h2>
        {projection.failureStage ? <>
          <p>失败阶段：{projection.failureStage}</p><p>{projection.failureReason}</p>
          <p>作品方案与已有准备结果已保留；重试从当前内容准备记录恢复，尚未提交视频制作。付费步骤仍需另行批准。</p>
          <button className="btn btn-primary" disabled={continuationBusy} onClick={onContinuePreparation}>重试内容准备</button>
        </> : projection.blockedPreparation ? <><p>准备阶段需要处理：{projection.failureReason}</p><p>当前作品与已有内容已保留；补齐创作方式、素材或制作环境后，从准备阶段恢复。费用仍需单独批准。</p><button className="btn" disabled={continuationBusy} onClick={onContinuePreparation}>重新检查内容准备</button></> : <p>{connectionError ? '连接恢复后才能确认最新进度。' : '正在整理已确认的内容与创作边界；暂时没有可展示的阶段成果。'}</p>}
      </section>}

      {operatorSessionReady && attemptId && attempt && <section className="card film-op-card film-op-creator">
        <div className="film-op-heading"><h2>{backendDelivery ? projection.title : phaseTitle[phase]}</h2><span className="film-op-work-title" title={title}>{title}</span></div>
        <p>{connectionError || delivery.status === 'observation_failed' ? '以下为最后可信制作状态，实时进度尚未确认。' : backendDelivery && !['review', 'done'].includes(phase) ? projection.title : phaseDescription[phase]}</p>
        {projection.pending > 0 && <p>当前待处理 {projection.pending} 项；优先处理下方事项。</p>}
        {projection.updatedAt != null && <small>作品状态更新时间：{String(projection.updatedAt)}</small>}
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
        {!currentOutput && typeof scriptTruth?.script === 'string' && <details className="film-op-stage-result"><summary>已形成的阶段成果：脚本</summary><p style={{ whiteSpace: 'pre-wrap' }}>{scriptTruth.script}</p></details>}
        {!currentOutput && ['planning', 'preparing', 'building'].includes(phase) && <small>
          {connectionError || ['observation_failed', 'execution_uncertain'].includes(text(delivery.status))
            ? '最后可信结果中还没有视频预览，当前执行状态尚未确认。' : '尚未生成视频预览；当前正在整理内容、编排或合成。'}
        </small>}
        {phase === 'failed' && <div className="film-op-message is-error" role="alert">
          <strong>失败阶段：{projection.failureStage ?? '视频制作'}</strong><p>{projection.failureReason}</p>
          <p>已保留：当前方案与已经通过核验的阶段成果。重试只恢复当前失败阶段；视频重新合成需重新核价与批准。</p>
        </div>}
        {['ready', 'building', 'preparing'].includes(phase) && <div className="film-op-creator-facts">
          <span>内容已准备</span><span>素材已准备</span>
          {typeof brief.duration_seconds === 'number' && <span>预计时长：{brief.duration_seconds} 秒</span>}
          {typeof brief.aspect_ratio === 'string' && <span>画幅：{brief.aspect_ratio}</span>}
          {allLocalNoCharge && <span>本次制作无第三方计费请求</span>}
          {!allLocalNoCharge && estimatedCost !== null && <span>预计费用：${estimatedCost.toFixed(2)}</span>}
        </div>}
        {phase === 'ready' && (!backendDelivery || delivery.status === 'needs_cost_approval') && <div className="film-op-review-claim"><h3>任务：确认本次制作费用</h3><p>已有证据：当前视频方案已通过校验，费用来自本次核价；批准后才提交制作。</p>
          {!canApproveCost && <p className="film-op-warning">费用尚无法确认，暂不能开始制作。可在高级信息中查看详情。</p>}
          {canApproveCost && !allLocalNoCharge && <label className="film-op-budget">本次同意的预算（美元）
            <input className="field" inputMode="decimal" value={budget} onChange={(event) => setBudget(event.target.value)} />
            {declaredBudget !== null && <small>本作品已约定最多 ${declaredBudget.toFixed(2)}。</small>}
            <small>该金额用于记录你的批准；服务商不保证自动限制实际费用。</small>
          </label>}
          <button className="btn btn-primary" disabled={!!busy || !canApproveCost || !budgetAllowed} onClick={() => {
            void run('开始制作', async () => {
              if (cost.approved !== true) await approveFilmCost(attemptId, requestedBudget);
              if (!backendDelivery) return submitFilmBuild(attemptId, text(creationSnapshot?.idea, 'Easel 视频'));
            });
          }}>同意本次费用并制作</button>
        </div>}
        {!backendDelivery && attemptStatus.authoring_status === 'AUTHORING_RUNNING' && <button className="btn btn-sm" disabled={!!busy} onClick={() => void run('恢复当前视频编排', () => startFilmAuthoring(attemptId))}>检查并恢复视频编排</button>}
        {phase === 'building' && delivery.status !== 'observation_failed' && <p role="status">正在合成视频，完成后会自动生成预览。你可以离开此页面。</p>}
        {!backendDelivery && phase === 'failed' && ['创作规划', '素材准备'].includes(projection.failureStage ?? '') && <button className="btn btn-primary" disabled={continuationBusy || !!busy} onClick={onContinuePreparation}>重试{projection.failureStage}</button>}
        {!backendDelivery && phase === 'failed' && ['AUTHORING_FAILED', 'PLAN_FAILED'].includes(text(attemptStatus.authoring_status)) && <button className="btn btn-primary" disabled={!!busy}
          onClick={() => {
            if (attemptStatus.authoring_status === 'AUTHORING_FAILED') void run('重新整理视频', () => startFilmAuthoring(attemptId));
            else void run('重新检查视频方案', async () => {
              const source = text(record(attemptStatus.authoring).run_path, '');
              if (!source) throw new Error('缺少视频编排结果');
              if (attemptStatus.runtime_status !== 'CONFIGURED') await resolveFilmRuntime(attemptId);
              await validateFilmAttempt(attemptId, source);
              return estimateFilmAttempt(attemptId);
            });
          }}>{attemptStatus.authoring_status === 'AUTHORING_FAILED' ? '重试视频编排' : '重试制作校验'}</button>}
        {phase === 'failed' && execution === 'BUILD_FAILED' && <>
          <p>本次合成已确定失败。可以复用已核验的内容、素材和编排；恢复不会调用素材 Provider 或提交新的 Build。之后如需再次合成，你需要重新确认费用。</p>
          <button className="btn btn-primary" disabled={!!busy} onClick={() => {
            void run('恢复视频制作', async () => {
              const next = await retryFailedFilmBuild(attemptId);
              setAttemptId(text(next.attempt_id));
              setAttempt(next);
              return next;
            });
          }}>从视频制作阶段恢复</button>
        </>}
        {phase === 'failed' && execution !== 'BUILD_FAILED' && !['AUTHORING_FAILED', 'PLAN_FAILED'].includes(text(attemptStatus.authoring_status)) && <p>本次制作未能完成。请查看失败原因后重试当前阶段。</p>}
        {phase === 'content-review' && <div className="film-op-review-claim"><h3>任务：核对事实表达</h3><p>这些表述尚缺可靠来源或人工判断，确认仅记录你的审阅，不转为来源事实。</p>
          {scriptClaims.filter((claim) => claim.status === 'REVIEW_REQUIRED').map((claim) =>
            <div className="film-op-review-claim" key={text(claim.claim_id)}>
              <strong>{text(claim.text)}</strong>
              {typeof record(record(claim.review).decision).reason === 'string' && <small>尚需处理：{text(record(record(claim.review).decision).reason)}</small>}
              {typeof claim.evidence_quote === 'string' && <small>参考依据：{claim.evidence_quote}</small>}
            </div>)}
          {typeof scriptTruth?.script === 'string' && <details><summary>查看完整内容</summary><pre>{scriptTruth.script}</pre></details>}
          <label className="film-op-confirm"><input type="checkbox" checked={scriptTruthConfirmed}
            onChange={(event) => setScriptTruthConfirmed(event.target.checked)} />我已核对待确认的表述与完整内容。</label>
          <button className="btn btn-primary" disabled={!!busy || !scriptTruthConfirmed || typeof scriptTruth?.script_sha256 !== 'string'
            || typeof scriptTruth?.truth_packet_sha256 !== 'string'} onClick={() => {
            void run('确认内容', () => reviewScriptTruth(attemptId, String(scriptTruth?.script_sha256), String(scriptTruth?.truth_packet_sha256)));
          }}>确认内容并继续</button>
          <details><summary>委托助手审阅</summary><p>仅在你已明确委托助手核对时使用，记录为委托复核，不记为本人审阅或来源事实。</p>
            <button className="btn" disabled={!!busy || !scriptTruthConfirmed || typeof scriptTruth?.script_sha256 !== 'string'
              || typeof scriptTruth?.truth_packet_sha256 !== 'string'} onClick={() => {
                void run('记录委托复核', () => reviewScriptTruth(attemptId, String(scriptTruth?.script_sha256), String(scriptTruth?.truth_packet_sha256), 'codex_delegate'));
              }}>记录委托复核并继续</button>
          </details>
        </div>}
        {phase === 'preparation-failed' && <p>{projection.failureReason}。已保留方案和成功阶段；将从当前准备记录恢复。付费操作仍需另行批准。</p>}
        {phase === 'preparation-failed' && <button className="btn btn-primary"
          disabled={continuationBusy || !!busy} onClick={onContinuePreparation}>重新准备素材</button>}
        {phase === 'material' && !projection.materialWorking && rightsCandidatesLoaded && missingSupplyNeeds.length > 0 && <div className="film-op-review-claim">
          <h3>任务：补充符合方案的素材</h3><p>这些需求尚无类型与来源都符合方案的候选，暂时不能进入视频制作。使用权复核不会改变素材来源。</p>
          {missingSupplyNeeds.map(need => <p key={text(need.need_id)}>
            {need.modality_kind === 'bgm' ? '配乐要求：无歌词器乐，音色与节奏须符合已确认的创作规划。' : `素材要求：${text(need.description)}。`}
            {need.required_source_kind === 'stock' && '当前方案要求图库素材；本地或开放许可索引素材不能替代。'}
            尚未确定：合适素材、可用性与使用权。</p>)}
          <p>可在下方调整检索提示，并允许配乐使用有明确授权的本地或开放许可素材。脚本、场景、旁白和画面要求保留；使用权与匹配仍须通过检查，不会生成素材或提交付费制作。</p>
          <button className="btn" onClick={onOpenConversation}>在对话中讨论素材</button>
        </div>}
        {phase === 'material' && rightsCandidatesLoaded && blockingNeedIds.length > 0 && <details className="film-op-review-claim">
          <summary>补充检索缺失素材</summary>
          <p>已保留素材和旁白。仅查找尚未覆盖的需求；配乐可使用有明确授权的本地或开放许可来源，仍核验使用权和匹配。本操作不生成音频、不改变脚本或场景、不提交制作费用。</p>
          {Array.isArray(scriptTruth?.material_needs) && scriptTruth.material_needs.map(record)
            .filter(need => blockingNeedIds.includes(text(need.need_id)) && need.modality_kind !== 'voice')
            .map((need, index) => <label key={text(need.need_id)}>
              {need.modality_kind === 'bgm' ? '配乐检索关键词' : `镜头素材 ${index + 1} 检索关键词`}
              <input className="field" value={materialSearchTerms[text(need.need_id)] ?? ''} maxLength={120}
                placeholder="可选：用简短关键词描述主体，如 window leaves"
                onChange={event => setMaterialSearchTerms(prev => ({...prev, [text(need.need_id)]: event.target.value}))} />
            </label>)}
          <button className="btn btn-primary" disabled={!!busy || continuationBusy || !operatorSessionReady}
            onClick={() => {
              const payload = {expectedPlanRevision: text(materialPlan.plan_revision),
                expectedBundleRevision: text(materialGate.bundle_revision), allowLicensedBgm: true,
                searchTerms: Object.fromEntries(Object.entries(materialSearchTerms)
                  .filter(([, value]) => value.trim()).map(([key, value]) => [key, [value.trim()]]))};
              const pendingKey = `easel-material-recovery-${attemptId}`;
              const saved = sessionStorage.getItem(pendingKey);
              if (!materialRecoveryRequest.current && saved) {
                try { materialRecoveryRequest.current = JSON.parse(saved); }
                catch { setError('素材恢复请求记录损坏，请先核对制作记录；未重新提交。'); return; }
              }
              if (!materialRecoveryRequest.current) {
                materialRecoveryRequest.current = {id: globalThis.crypto.randomUUID(), payload: JSON.stringify(payload)};
                sessionStorage.setItem(pendingKey, JSON.stringify(materialRecoveryRequest.current));
              }
              const requestId = materialRecoveryRequest.current.id;
              const boundPayload = JSON.parse(materialRecoveryRequest.current.payload);
              void run('补充素材', async () => {
                const result = await recoverFilmMaterials(attemptId, {...boundPayload, requestId});
                setAttempt(record(result.attempt));
                materialRecoveryRequest.current = null;
                sessionStorage.removeItem(pendingKey);
              });
            }}>{busy === '补充素材' ? '正在检索并检查缺失素材…' : '保留已有结果并补充素材'}</button>
        </details>}
        {phase === 'material' && !projection.materialWorking && pendingVoiceNeed && <div className="film-op-review-claim">
          <h3>任务：准备整片旁白</h3>
          <p>{existingVoiceCandidate && !voiceRightsPending
            ? '已有旁白已保留；请记录实际试听结论，完成当前脚本与音频的匹配核对。'
            : voiceRightsPending || generationResult !== null
            ? '当前事项：核对刚生成旁白的使用权。其他素材事项仍按各场景分别处理。'
            : '当前缺少整片旁白音频。可以按已确认的脚本生成旁白；生成前会再次确认费用。'}</p>
          {!rightsCandidatesLoaded && generationResult === null
            ? <p>正在核对已有素材…</p>
            : existingVoiceCandidate && !voiceRightsPending
            ? <div>
                <audio controls preload="metadata" aria-label="试听当前旁白"
                  src={materialAssetPreviewUrl(attemptId, text(existingVoiceCandidate.asset_id), text(existingVoiceCandidate.asset_sha256))} />
                <p>系统已有证据：当前脚本对应的生成记录与音频字节已核对。只需记录句子完整性、清晰度与语速的实际试听结论。</p>
                <label>旁白试听结论<textarea className="field" value={voiceListeningObservation}
                  onChange={event => setVoiceListeningObservation(event.target.value)} /></label>
                <button className="btn btn-primary" disabled={!!busy || voiceListeningObservation.trim().length < 8}
                  onClick={() => void run('记录旁白试听', async () => {
                    const result = await reviewMaterialMatch(attemptId, {
                      assetId: existingVoiceCandidate.asset_id, assetSha256: existingVoiceCandidate.asset_sha256,
                      needId: pendingVoiceNeed?.need_id, observedContent: voiceListeningObservation,
                      logoPresent: null, visibleTextPresent: null, confirmReview: true,
                    });
                    setAttempt(record(result.attempt));
                  })}>记录试听结论并使用已有旁白</button>
              </div>
            : voiceRightsPending || generationResult !== null
            ? pendingVoiceCandidate && <div className="film-op-review-claim film-op-voice-review">
                <strong>确认这条旁白能否用于当前视频</strong>
                <audio controls preload="metadata" aria-label="试听当前旁白"
                  src={materialAssetPreviewUrl(attemptId, text(pendingVoiceCandidate.asset_id), text(pendingVoiceCandidate.asset_sha256))} />
                <p>请查看你与 MiniMax 适用的服务条款或合同：生成音频能否用于本视频、是否需要署名、有没有用途限制。成片完成后还会让你播放审核。</p>
                <small>已有证据：生成旁白已完成技术检查；适用许可与用途仍需核对。</small>
                <label>核对结论
                  <select className="field" value={voiceRightsDecision} onChange={(event) => setVoiceRightsDecision(event.target.value)}>
                    <option value="UNKNOWN">还不能确认，暂不继续</option>
                    <option value="KNOWN">允许用于当前视频，无需署名</option>
                    <option value="ATTRIBUTION_REQUIRED">允许使用，但需要署名</option>
                    <option value="RESTRICTED">当前用途不被允许</option>
                  </select>
                </label>
                {voiceRightsDecision !== 'UNKNOWN' && <>
                  {voiceRightsDecision !== 'RESTRICTED' && <label>条款或合同名称
                    <input className="field" value={voiceTermsName} onChange={(event) => setVoiceTermsName(event.target.value)} />
                  </label>}
                  <label>依据链接或合同定位
                    <input className="field" value={voiceEvidenceReference} onChange={(event) => setVoiceEvidenceReference(event.target.value)}
                      placeholder="官方条款链接，或可追溯的合同章节" />
                  </label>
                  <label>相关条款说明
                    <textarea className="field" rows={2} value={voiceEvidenceSummary} onChange={(event) => setVoiceEvidenceSummary(event.target.value)}
                      placeholder="写明你核对到的使用、署名或限制条件" />
                  </label>
                  {voiceAttributionRequired && <>
                    <label>准确署名文字<input className="field" value={voiceCredit} onChange={(event) => setVoiceCredit(event.target.value)} /></label>
                    <label>应署名的创作者<input className="field" value={voiceCreator} onChange={(event) => setVoiceCreator(event.target.value)} /></label>
                    <label>署名对应的来源页<input className="field" value={voiceSourcePage} onChange={(event) => setVoiceSourcePage(event.target.value)} placeholder="https://…" /></label>
                    <small>署名文字需包含创作者名称和来源页；来源页使用公开的 HTTPS 链接。</small>
                  </>}
                  <label>其他使用限制（如有，每行一项）
                    <textarea className="field" rows={2} value={voiceRestrictions} onChange={(event) => setVoiceRestrictions(event.target.value)} />
                  </label>
                  <label className="film-op-confirm"><input type="checkbox" checked={voiceRightsConfirmed}
                    onChange={(event) => setVoiceRightsConfirmed(event.target.checked)} />
                    我已核对上述依据适用于这条生成旁白和当前视频用途。
                  </label>
                  <button className="btn btn-primary" disabled={!operatorSessionReady || !!busy || continuationBusy || !voiceReviewReady}
                    onClick={submitVoiceRightsReview}>{busy === '复核旁白使用权' ? '正在记录…' : '提交这 1 项复核'}</button>
                </>}
              </div>
            : <><p>已有证据：当前脚本已通过内容审阅，将使用预置普通话音色，不克隆声音。尚未确定：生成音频的时长、声音效果和使用权。</p>
              <p>本次会向现有 MiniMax 账号提交一次语音生成请求，可能计费。当前没有可核实的预估价格，需按平台价格确认；Easel 不提供消费硬上限。生成后仍需核对使用权，不能直接进入成片。</p>
              <button className="btn btn-primary" disabled={!!busy || !operatorSessionReady}
                onClick={() => generateForNeed(text(pendingVoiceNeed.need_id))}>
                {busy === '生成素材' ? '正在生成旁白…' : '生成旁白素材'}
              </button></>}
        </div>}
        {phase === 'material' && !projection.materialWorking && pendingMusicNeed && selectedMusic && <div className="film-op-review-claim">
          <h3>任务：核对配乐</h3>
          <p>要求：{text(pendingMusicNeed.description)}。只记录实际试听依据；使用权与署名条件另行检查。</p>
          <label>配乐候选<select className="field" value={text(selectedMusic.asset_id)}
            onChange={event => setMusicAssetId(event.target.value)}>
            {musicCandidates.map((asset, index) => <option value={text(asset.asset_id)} key={text(asset.asset_id)}>配乐 {index + 1}</option>)}
          </select></label>
          <audio controls preload="metadata" aria-label="试听配乐候选"
            src={materialAssetPreviewUrl(attemptId, text(selectedMusic.asset_id), text(selectedMusic.asset_sha256))} />
          <label>配乐试听依据<textarea className="field" value={musicObservation}
            placeholder="记录是否有歌词、主要乐器和节奏是否符合方案"
            onChange={event => setMusicObservation(event.target.value)} /></label>
          <button className="btn btn-primary" disabled={!!busy || !operatorSessionReady || musicObservation.trim().length < 8}
            onClick={() => void run('记录配乐试听', async () => {
              const result = await reviewMaterialMatch(attemptId, {
                assetId: selectedMusic.asset_id, assetSha256: selectedMusic.asset_sha256,
                needId: pendingMusicNeed.need_id, observedContent: musicObservation,
                logoPresent: null, visibleTextPresent: null, confirmReview: true,
              });
              setAttempt(record(result.attempt));
            })}>记录这一项配乐核对</button>
        </div>}
        {phase === 'material' && !projection.materialWorking && visualCandidates.length > 0 && <div className="film-op-review-claim">
          <strong>核对画面是否真的符合场景</strong>
          <p>请查看素材预览，只确认你实际看见的内容。每个场景都单独核对；未确认的画面不会算作已覆盖。</p>
          <label>对应场景
            <select className="field" value={text(selectedVisualNeed?.need_id, '')}
              onChange={(event) => { setVisualNeedId(event.target.value); setVisualAssetId(''); setVisualConfirmed(false); }}>
              {selectedVisualNeeds.map((need) => <option value={text(need.need_id)} key={text(need.need_id)}>
                {text(need.description)}</option>)}
            </select>
          </label>
          <label>素材
            <select className="field" value={text(selectedVisual?.asset_id, '')}
              onChange={(event) => { setVisualAssetId(event.target.value); setVisualConfirmed(false); }}>
              {visualCandidates.map((item) => <option value={text(item.asset_id)} key={text(item.asset_id)}>
                候选 {visualCandidates.indexOf(item) + 1} · {text(item.provider, '本地素材')}</option>)}
            </select>
          </label>
          {selectedVisual && (selectedVisual.media_type === 'video'
            ? <video className="film-op-preview" controls preload="metadata" src={materialAssetPreviewUrl(attemptId, text(selectedVisual.asset_id), text(selectedVisual.asset_sha256))} />
            : <img className="film-op-visual-preview" alt="待核对素材原图" src={materialAssetPreviewUrl(attemptId, text(selectedVisual.asset_id), text(selectedVisual.asset_sha256))} />)}
          <p>场景要求：{text(selectedVisualNeed?.description)}</p><p>已有证据：素材已通过技术检查。尚未确定：画面是否符合当前场景、是否满足下列限制。</p>
          <label>实际看到的画面依据
            <textarea className="field" rows={2} value={visualObservation}
              onChange={(event) => setVisualObservation(event.target.value)}
              placeholder="写出画面主体、动作和环境，以及它如何对应当前场景" />
          </label>
          {selectedVisualConstraints.logo === false && <label>画面里有 logo 吗？
            <select className="field" value={visualLogo} onChange={(event) => setVisualLogo(event.target.value)}>
              <option value="unknown">尚未确认</option><option value="yes">有，拒绝这段素材</option><option value="no">没有</option>
            </select>
          </label>}
          {selectedVisualConstraints.text_in_frame === false && <label>画面里有文字吗？
            <select className="field" value={visualText} onChange={(event) => setVisualText(event.target.value)}>
              <option value="unknown">尚未确认</option><option value="yes">有，拒绝这段素材</option><option value="no">没有</option>
            </select>
          </label>}
          <label className="film-op-confirm"><input type="checkbox" checked={visualConfirmed}
            onChange={(event) => setVisualConfirmed(event.target.checked)} />我已核对这段素材与所选场景，记录基于实际预览。</label>
          <button className="btn btn-primary" disabled={!visualReviewReady || !!busy} onClick={submitVisualReview}>
            提交这一组画面核对</button>
        </div>}
        {phase === 'material' && !projection.materialWorking && !voiceRightsPending && rightsReviewCandidates.length > 0 && <>
        <section className="card film-op-card">
          <h3>任务：核对素材使用权</h3>
          {voiceRightsPending && <p>当前待复核：刚生成的 MiniMax 旁白音频。请核对该素材对应的使用条款和证据。</p>}
          <p>这里只记录你提交的素材级来源与权利证据，不由 Easel 根据 Provider 推断许可。请按当前素材对应的实际条款核对；证据不足时保留 UNKNOWN，Gate 会继续阻断。提交后只本地重算当前 Gate，不重新搜索或生成素材。</p>
          {rightsCandidates.length === 0 ? <p>当前 Plan/Bundle 中没有字节校验通过且技术检查通过的可核验素材。</p> : <>
            <label>待核素材
              <select className="field" value={text(selectedRightsCandidate?.asset_id, '')} onChange={(event) => setRightsAssetId(event.target.value)}>
                {rightsReviewCandidates.map((item) => <option key={String(item.asset_id)} value={String(item.asset_id)}>
                  素材 {rightsReviewCandidates.indexOf(item) + 1} · {text(item.provider, '本地')} · {record(item.rights).status === 'UNKNOWN' ? '使用权待确认' : '查看使用权'}
                </option>)}
              </select>
            </label>
            {selectedRightsCandidate && <>
              <small>已有证据：来源页 {text(selectedRightsCandidate.source_page)} · 创作者 {text(selectedRightsCandidate.creator)}</small>
              <p>尚未确定：许可是否适用于当前场景与用途。素材画面匹配仍需独立核对。</p>
              <label>核验结论
                <select className="field" value={rightsStatus} onChange={(event) => setRightsStatus(event.target.value)}>
                  <option value="UNKNOWN">暂无法确认，继续阻断</option>
                  <option value="KNOWN">已核验许可与用途</option>
                  <option value="PUBLIC_DOMAIN">已核验公有领域依据</option>
                  <option value="ATTRIBUTION_REQUIRED">可用但必须署名</option>
                  <option value="RESTRICTED">限制使用</option>
                </select>
              </label>
              <div className="film-op-grid">
                <label>许可名称<input className="field" value={rightsLicenseName} onChange={(event) => setRightsLicenseName(event.target.value)} /></label>
                <label>许可链接<input className="field" value={rightsLicenseUrl} onChange={(event) => setRightsLicenseUrl(event.target.value)} /></label>
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
                我已按当前素材核对证据与使用范围；这是我的事实录入，不是系统自动法律判断。
              </label>
              <button className="btn btn-primary" disabled={!operatorSessionReady || !!busy || !rightsConfirmed
                || !rightsEvidenceKind.trim() || !rightsEvidenceReference.trim() || !rightsEvidenceSummary.trim()} onClick={() => {
                void run('记录素材权利证据', async () => { const result = await reviewMaterialRights(attemptId, {
                  assetId: selectedRightsCandidate.asset_id,
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
                }); if (record(result).material_status === 'MATERIAL_READY') await startFilmAuthoring(attemptId); return result; });
              }}>记录核验事实并继续</button>
            </>}
          </>}
        </section>

        </>}
        {phase === 'preparing' && preparationStatus !== 'PRODUCTION_PREPARED'
          && attemptStatus.authoring_status === 'READY_FOR_EXTERNAL_AUTHORING'
          && <button className="btn btn-primary" disabled={continuationBusy || !!busy}
            onClick={onContinuePreparation}>继续编排视频</button>}
        {phase === 'review' && <>
          {typeof selectedReviewOutput.path === 'string' && <video className="film-op-preview" controls preload="metadata" src={mediaUrl(selectedReviewOutput.path)}>
            浏览器不支持视频预览。
          </video>}
          <label className="film-op-confirm"><input type="checkbox" checked={finalReviewConfirmed}
            onChange={(event) => setFinalReviewConfirmed(event.target.checked)} />
            我已播放并核对成片的事实表达、创作风格和声画效果。
          </label>
          <button className="btn btn-primary" disabled={!!busy || !finalReviewConfirmed || typeof selectedReviewOutput.sha256 !== 'string'} onClick={() => {
            void run('确认成片', async () => {
              await reviewFilmOutput(attemptId, {
                outputName: reviewOutputName, sha256: String(selectedReviewOutput.sha256),
                truth: { status: 'pass', notes: ['Creator 已播放并核对当前 SHA 对应成片的事实表达。'] },
                style: { status: 'pass', notes: ['Creator 已播放并核对当前 SHA 对应成片的创作风格。'] },
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
        {['review', 'done'].includes(phase) && <>
          <p>自动检查：{systemReview.status === 'READY' ? '画面采样与声音信号检查通过，首版可供审阅；最终取舍仍由你决定。'
            : systemReview.status === 'REPAIR_REQUIRED' ? '发现待修正问题，当前视频已保留，系统修复尚未完成。'
              : systemReview.status === 'INCOMPLETE' ? '部分检查证据不足，尚不能确认首版质量。'
                : backendDelivery ? delivery.status === 'checking_quality' ? 'Easel 正在核对当前成片。' : '系统检查尚未完成，当前是已导出的预览。'
                  : record(selectedReviewOutput.technical_qc).status === 'pass' ? '文件完整性、音视频流与解码检查通过；请播放核对内容与声画效果。' : '当前输出检查结果尚不可用。'}</p>
          {Array.isArray(record(systemReview.measurements).defects) && (record(systemReview.measurements).defects as unknown[]).slice(0, 5).map((defect, index) =>
            <p key={`quality-${index}`}>{text(record(defect).time_seconds)} 秒：{text(record(defect).reason)}</p>)}
          {Array.isArray(systemReview.visual) && (systemReview.visual as unknown[]).flatMap(batch => Object.values(record(record(batch).checks)))
            .filter(check => record(check).status !== 'pass').slice(0, 3).map((check, index) => <p key={`visual-quality-${index}`}>{text(record(check).reason)}</p>)}
          <button className="btn" onClick={() => setFeedbackOpen(value => !value)}>提出修改</button>
          {feedbackOpen && <div className="film-op-review-claim">
            <h3>成片修改反馈</h3>
            <p>反馈绑定当前视频。支持在已有素材、脚本、场景顺序、总时长和声音不变的前提下调整构图与转场；字幕、素材替换、内容与规格修改请在对话中重新确认方案。调整后会重新核价，费用批准后才合成。</p>
            <label>修改类型<select className="field" value={feedbackKind} onChange={event => setFeedbackKind(event.target.value)}>
              <option value="general">一般反馈（保存并讨论）</option><option value="composition">构图与转场（可执行）</option>
            </select></label>
            <label>希望调整什么<textarea className="field" value={feedbackText} onChange={event => setFeedbackText(event.target.value)} /></label>
            <label>时间点（可选，秒）<input className="field" type="number" min="0" step="0.1" value={feedbackTime} onChange={event => setFeedbackTime(event.target.value)} /></label>
            <button className="btn btn-primary" disabled={!!busy || !feedbackText.trim() || (feedbackTime !== '' && (!Number.isFinite(Number(feedbackTime)) || Number(feedbackTime) < 0))}
              onClick={() => void run('保存修改反馈', async () => {
                const saved = await reviewFilmOutput(attemptId, { outputName: reviewOutputName, sha256: selectedReviewOutput.sha256,
                  truth: { status: 'modify' }, style: { status: 'modify' }, human: { status: 'rejected' },
                  feedback: [...(Array.isArray(record(attemptStatus.review).feedback) ? record(attemptStatus.review).feedback as unknown[] : []), { kind: feedbackKind, text: feedbackText.trim(), ...(feedbackTime === '' ? {} : { time_seconds: Number(feedbackTime) }) }],
                });
                setAttempt(saved); setFeedbackText(''); setFeedbackTime(''); setFeedbackOpen(false);
                return saved;
              })}>保存反馈，退回审片</button>
          </div>}
          {Array.isArray(record(attemptStatus.review).feedback) && (record(attemptStatus.review).feedback as unknown[]).length > 0 && <div className="film-op-review-claim">
            <strong>已保存的修改意见</strong>
            {(record(attemptStatus.review).feedback as unknown[]).map((entry, index) => <p key={index}>
              {typeof record(entry).time_seconds === 'number' ? `${record(entry).time_seconds} 秒：` : ''}{text(record(entry).text)}
            </p>)}
            {(record(attemptStatus.review).feedback as unknown[]).every(entry => record(entry).kind === 'composition') && <>
              <p>影响范围：视频编排与合成；复用已核验内容和素材，不重新请求素材 Provider。新成片仍需重新审片与确认。</p>
              <button className="btn btn-primary" disabled={!!busy || connectionError !== ''} onClick={() => void run('按反馈调整构图与转场', async () => {
                const next = await reviseFilmOutput(attemptId, reviewOutputName, String(selectedReviewOutput.sha256));
                setAttemptId(text(next.attempt_id)); setAttempt(next);
                return startFilmAuthoring(String(next.attempt_id));
              })}>按反馈调整构图与转场</button>
            </>}
          </div>}
        </>}
      </section>}

      <details ref={advancedRef} className="film-op-advanced" open={advancedOpen} onToggle={(event) => setAdvancedOpen(event.currentTarget.open)}>
        <summary>制作记录 / 高级信息</summary>
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
            <div><span>系统语义审阅</span><strong>{scriptReviewCounts.system}</strong></div>
            <div><span>Codex 委托复核</span><strong>{scriptReviewCounts.delegated}</strong></div>
            <div><span>人工复核</span><strong>{scriptReviewCounts.human}</strong></div>
          </div>
          {typeof scriptTruth?.script === 'string' && <details><summary>查看完整 SCRIPT（{scriptTruth.script.length.toLocaleString()} 字符）</summary><pre>{scriptTruth.script}</pre></details>}
          {scriptTruth && <details><summary>查看完整逐句审阅记录（{scriptClaims.length} 条）</summary><pre>{json(scriptClaims.map((claim) => ({
            claim_id: claim.claim_id, text: claim.text, classification: claim.classification,
            status: claim.status, source_ref: claim.source_ref, evidence_quote: claim.evidence_quote, review: claim.review,
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
              || !generationNeedId || materialGate.status !== 'MATERIAL_NOT_READY'}
              onClick={() => generateForNeed(generationNeedId)}>确认费用并生成素材</button>
          </div>
          {generationResult !== null && <details open><summary>最近一次 MiniMax 生成记录</summary><pre>{json(generationResult)}</pre></details>}
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
          {selectedReviewOutput.attribution != null && <details><summary>该输出的 Attribution</summary><pre>{json(selectedReviewOutput.attribution)}</pre></details>}
          <p>成片确认与修改反馈请使用上方审片卡；此处仅保留导出与追溯记录。</p>
          <div className="film-op-details">
            {outputsForSelect.map(({ name, item }) => <details key={name}><summary>{name} · {text(item.sha256)}</summary><pre>{json(item)}</pre></details>)}
          </div>
        </section>
      </>}
      </details>
    </div>
  );
}
