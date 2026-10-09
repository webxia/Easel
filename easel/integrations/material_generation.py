"""Commission-bound calls into the existing Material generation service."""
from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal, InvalidOperation

from easel import creation
from easel.runtime_config import EaselRuntimeConfig
from easel.materials.application.generation import MiniMaxVideoMaterialGeneration
from easel.materials.application.routing import MaterialSourceRouter
from easel.materials.providers.minimax_pricing import GenerationQuoteUnavailable, GenerationQuoteReadFailed, quote_generation
from easel.materials.providers.minimax_speech import MINIMAX_SPEECH_MODELS
from easel.materials.providers.minimax_video import MINIMAX_VIDEO_MODELS
from easel.materials.store import AttemptMaterialStore, GenerationRecordNotFound


# Reviewed 2026-10-01: clauses 6.2/6.3/9.5 allow conditional use of output,
# not ownership or unrestricted publication. Clause 1.7 governs distribution.
# Another agreement version requires a fresh policy review, never fuzzy text matching.
MINIMAX_INTERNAL_TERMS_SHA256 = '90d05ccc1dbf8404cbc40cfb096698ceec2bc894440ac507cd048ecb9a896ae0'


def commission_generated_rights(work, plan, need, asset, record, script):
    """Known, limited internal use from combined facts; no blanket AI license."""
    from easel.creation_delivery import is_managed
    from easel.materials.domain import RightsEvidence, RightsStatus, TechnicalStatus, MediaType
    from easel.materials.application.voice_delivery import voice_content_observed, timing_from_recognition
    from easel.materials.application.visual_observation import observed_match
    from easel.materials.application.generation import visual_generation_prompt
    from easel.materials.providers.minimax_pricing import TERMS_URL, VOICE_URL
    modality = record.get('modality')
    is_voice = modality == 'voice'
    if (modality not in {'voice', 'image', 'video'}
            or not is_managed(work) or work['id'] != plan.creation_id or need not in plan.needs
            or asset.rights.status is not RightsStatus.UNKNOWN
            or asset.rights.reviewed_at is not None or asset.rights.usage_constraints
            or asset.technical.status is not TechnicalStatus.PASSED
            or asset.source.kind != 'generative' or asset.source.provider != 'minimax'):
        return None
    if is_voice:
        if (getattr(need.modality_spec, 'kind', None) != 'voice'
                or hashlib.sha256(script.encode()).hexdigest() != need.modality_spec.text_sha256
                or not voice_content_observed(need, asset)):
            return None
        input_digest, input_key = need.modality_spec.text_sha256, 'input_sha256'
    elif (need.media_type is not {'image': MediaType.IMAGE, 'video': MediaType.VIDEO}[modality]
            or asset.media_type is not need.media_type or observed_match(need, asset) is not True):
        return None
    else:
        input_digest = hashlib.sha256(visual_generation_prompt(need).encode()).hexdigest()
        input_key = 'prompt_sha256' if modality == 'video' else 'input_sha256'
    authorization = work['delivery'].get('authorization', {})
    declaration = authorization.get('input_use') or {}
    version = {'easel-input-use@1': 1, 'easel-input-use@2': 2}.get(declaration.get('schema'))
    if version is None or (not is_voice and version < 2):
        return None
    expected = creation.input_use_preview(version=version)
    if (any(declaration.get(key) != value for key, value in expected.items())
            or declaration.get('creation_id') != work['id']
            or declaration.get('proposal_sha256') != work['delivery'].get('proposal_sha256')
            or declaration.get('confirmed_at') != work['delivery'].get('confirmed_at')
            or declaration.get('confirmed_by_turn') != work['delivery'].get('confirmed_by_turn')):
        return None
    approval = record.get('commission_authorization') or {}
    grant = authorization.get('material_generation') or {}
    scope = grant.get('scope', {})
    receipt = work['delivery'].get('material_generations', {}).get(approval.get('request_id'), {})
    quote = approval.get('quote') or {}
    terms = quote.get('terms_evidence') or {}
    document = terms.get('document')
    if (approval.get('source') != 'commission_budget' or approval.get('creation_id') != work['id']
            or approval.get('input_use') != declaration
            or not grant.get('scope_sha256') or approval.get('scope_sha256') != grant['scope_sha256']
            or receipt.get('status') != 'complete' or receipt.get('quote') != quote
            or receipt.get('asset_id') != asset.asset_id or receipt.get('attempt_id') != plan.attempt_id
            or receipt.get('need_id') != need.need_id
            or terms.get('url') != TERMS_URL or not isinstance(document, str)
            or terms.get('sha256') != MINIMAX_INTERNAL_TERMS_SHA256
            or hashlib.sha256(document.encode()).hexdigest() != terms.get('sha256')
            or scope.get('api_origin') not in {'https://api.minimax.cn', 'https://api.minimaxi.com'}
            or scope.get('provider') != 'minimax' or quote.get('provider') != 'minimax'
            or quote.get('model') != record.get('model')):
        return None
    if is_voice and (record.get('model') not in MINIMAX_SPEECH_MODELS
            or record.get('model') != scope.get('speech_model')
            or not record.get('voice_id') or record['voice_id'] != scope.get('speech_voice_id')
            or not any(e.get('url') == VOICE_URL and len(e.get('sha256', '')) == 64 for e in quote.get('evidence', []))):
        return None
    if is_voice:
        from easel.integrations.voice_identity import require_binding
        try:
            binding = require_binding(work, plan, script)
        except ValueError:
            return None
        if binding is not None and approval.get('voice_binding_sha256') != binding['binding_sha256']:
            return None
    if not is_voice and (record.get('model') != scope.get(modality + '_model')
            or record.get('model') not in ({'image-01'} if modality == 'image' else MINIMAX_VIDEO_MODELS)):
        return None
    provider_identity = record.get('task_id') if modality == 'video' else record.get('generation_id')
    if (record.get('schema') != 'easel-material-generation@1' or record.get('status') != 'COMPLETE'
            or record.get('provider') != 'minimax'
            or record.get('generation_id') != 'gen-' + str(approval.get('request_id'))
            or not provider_identity or asset.source.provider_asset_id != provider_identity
            or record.get('attempt_id') != plan.attempt_id or record.get('plan_id') != plan.plan_id
            or record.get('plan_revision') != hashlib.sha256(plan.to_json().encode()).hexdigest()
            or record.get('need_id') != need.need_id
            or record.get('need_sha256') != hashlib.sha256(need.to_json().encode()).hexdigest()
            or record.get(input_key) != input_digest
            or (record.get('asset_id'), record.get('asset_sha256'), record.get('asset_path'), record.get('asset_bytes'))
               != (asset.asset_id, asset.file.sha256, asset.file.path, asset.file.size)):
        return None
    if is_voice:
        report = record.get('voice_recognition') or {}
        # The persisted recognition must be the same evidence applied to this Need.
        if (report.get('audio_sha256') != asset.file.sha256
            or report.get('script_sha256') != need.modality_spec.text_sha256
            or report.get('need_sha256') != record['need_sha256']):
            return None
        try:
            timing_from_recognition(script, asset, report)
        except ValueError:
            return None
    return asset.rights.model_copy(update={
        'status': RightsStatus.KNOWN,
        'license_name': '输入授权与生成服务条款（限本作品内部制作）', 'license_url': TERMS_URL,
        'usage_constraints': ('internal_production_only', 'current_creation_only'),
        'evidence': asset.rights.evidence + (RightsEvidence(kind='asset_commission_use',
            reference=(f"creation:{work['id']}:generation:{record['generation_id']}:sha256:{asset.file.sha256}"
                       f" terms-sha256:{terms['sha256']}"),
            summary='已确认的本作品输入用途、请求时协议与实际素材观察；不授予公开发布或跨作品复用'),),
    })


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def generation_scope(settings) -> dict:
    if (settings.base_url.rstrip('/') not in {'https://api.minimax.cn', 'https://api.minimaxi.com'}
            or settings.image_model != 'image-01' or settings.video_model not in MINIMAX_VIDEO_MODELS
            or settings.speech_model not in MINIMAX_SPEECH_MODELS):
        raise GenerationQuoteUnavailable('当前素材服务配置不在已核实的人民币核价范围内')
    scope = {'provider': 'minimax', 'api_origin': settings.base_url.rstrip('/'),
             'image_model': settings.image_model, 'video_model': settings.video_model,
             'speech_model': settings.speech_model, 'speech_voice_id': settings.speech_voice_id}
    from easel.integrations.hypit.secrets import SecretRedactor
    if SecretRedactor.contains_secret(json.dumps(scope)):
        raise GenerationQuoteUnavailable('素材服务配置含疑似凭证，不能作为委托内容展示')
    return scope


def generation_budget_preview() -> dict:
    settings = EaselRuntimeConfig.load().minimax
    try:
        scope = generation_scope(settings)
        return {'available': bool(settings.api_key), 'scope': scope, 'scope_sha256': _scope_digest(settings, scope),
                'currency': 'CNY'}
    except GenerationQuoteUnavailable as exc:
        return {'available': False, 'reason': str(exc)}


def _scope_digest(settings, scope) -> str:
    # Bind account configuration without persisting or exposing credential bytes.
    return _digest([scope, hashlib.sha256((settings.api_key or '').encode()).hexdigest()])


GENERATION_MODALITIES = frozenset({'image', 'video', 'voice'})
MODALITY_AUTHORIZATION = 'material-generation-budget@2'


def requested_generation_modalities(budget):
    if 'allowedModalities' not in budget:
        return GENERATION_MODALITIES
    value = budget['allowedModalities']
    if (not isinstance(value, list) or not value or any(type(item) is not str for item in value)
            or len(set(value)) != len(value) or not set(value) <= GENERATION_MODALITIES):
        raise creation.CreationError('素材生成范围须为不重复的图片、视频、预置旁白类别')
    return frozenset(value)


def authorized_generation_modalities(grant):
    if 'authorization_contract' not in grant and 'allowed_modalities' not in grant:
        return GENERATION_MODALITIES  # Preserve genuinely legacy authorizations.
    if grant.get('authorization_contract') != MODALITY_AUTHORIZATION or 'allowed_modalities' not in grant:
        raise creation.CreationError('素材生成范围授权记录不完整，不能扩大执行')
    return requested_generation_modalities({'allowedModalities': grant['allowed_modalities']})


def generation_need_modality(need):
    # Audio media is not automatically speech: BGM/SFX cannot spend a voice grant.
    if need.media_type.value == 'audio':
        return 'voice' if getattr(need.modality_spec, 'kind', None) == 'voice' else None
    return need.media_type.value if need.media_type.value in {'image', 'video'} else None


def commission_fingerprint(plan, script, grant):
    values = [plan.to_json(), script, grant['scope']]
    modalities = authorized_generation_modalities(grant)
    if 'authorization_contract' in grant:
        values.append({'authorization_contract': MODALITY_AUTHORIZATION,
                       'allowed_modalities': sorted(modalities)})
    return _digest(values)


def commission_generation_authorization(budget: dict | None) -> dict | None:
    if budget is None:
        return None
    try:
        if set(budget) not in ({'maxCostCny', 'scopeSha256'}, {'maxCostCny', 'scopeSha256', 'allowedModalities'}) or isinstance(budget['maxCostCny'], bool):
            raise ValueError
        amount = Decimal(str(budget['maxCostCny']))
        if not amount.is_finite() or not 0 < amount <= 1000 or amount.as_tuple().exponent < -2:
            raise ValueError
    except (InvalidOperation, ValueError, KeyError, TypeError) as exc:
        raise creation.CreationError('素材预算须为 0～1000 元之间的正数，最多两位小数') from exc
    modalities = requested_generation_modalities(budget)
    preview = generation_budget_preview()
    if not preview.get('available') or budget['scopeSha256'] != preview.get('scope_sha256'):
        raise creation.CreationError('素材服务或音色配置已变化，请核对当前方案中的费用范围')
    return {'currency': 'CNY', 'max_amount': str(amount), 'scope': preview['scope'],
            'scope_sha256': preview['scope_sha256'],
            **({'authorization_contract': MODALITY_AUTHORIZATION, 'allowed_modalities': sorted(modalities)}
               if 'allowedModalities' in budget else {})}


def pending_generated_need(work, attempt, plan):
    authorization = work.get('delivery', {}).get('authorization', {}).get('material_generation')
    if not authorization:
        return None
    allowed = authorized_generation_modalities(authorization)
    records = work['delivery'].get('material_generations', {})
    blocking = set(attempt.get('material_gate', {}).get('blocking_needs', []))
    # One initial generation per Need/draft. Unknown outcomes never open another
    # request id. Successful media with unresolved Rights are not regenerated.
    revision = hashlib.sha256(plan.to_json().encode()).hexdigest()
    retained = AttemptMaterialStore(attempt['workspace']['path']).list_generation_records()
    for need in plan.needs:
        if (generation_need_modality(need) not in allowed
                or need.need_id not in blocking or need.constraints.get('allow_generation') is False
                or not MaterialSourceRouter._generation_eligible(need)):
            continue
        if need.media_type.value in {'image', 'video'}:
            # This fallback only buys static images. An explicitly requested
            # video generation keeps its existing route outside this strategy.
            if need.media_type.value == 'video':
                if work['delivery'].get('endpoint') == 'MATERIAL_READY':
                    continue
            elif not image_fallback_decision(work, attempt, plan, need)['eligible']:
                continue
        key = 'delivery-' + _digest([plan.attempt_id, revision, need.need_id])[:32]
        if any(r.get('need_id') == need.need_id and r.get('status') == 'uncertain' for r in records.values()):
            continue
        if any(r.get('need_id') == need.need_id and r.get('generation_id') != 'gen-' + key
               and (r.get('plan_revision') == revision or r.get('status') in {'GENERATING', 'SUBMITTING', 'SUBMISSION_UNCERTAIN'})
               for r in retained):
            continue  # Retain an existing explicit generation, including its unknown outcome.
        prior = records.get(key)
        if prior is None or prior.get('status') == 'reserved':
            return need, key
    return None


def image_fallback_decision(work, attempt, plan, need) -> dict:
    """A shortage is established by valid supply/observation, never report failure."""
    from easel.materials.application.readiness import MaterialReadinessCalculator
    from easel.materials.application.visual_observation import need_identity
    from easel.materials.application.matching import MaterialMatcher
    from easel.creation_preparation import _load_snapshot, preparation_paths
    from easel.materials.domain import MediaType
    result = {'eligible': False, 'need_id': need.need_id, 'reason': '未证明允许且适用于静态图的真实缺口'}
    if (need.media_type is not MediaType.IMAGE or need.constraints.get('allow_generation') is not True
            or any(need.constraints.get(k) is True for k in ('requires_real_evidence', 'requires_real_identity', 'requires_dynamic_action'))
            or need.constraints.get('required_identity_refs')
            or need.constraints.get('required_source_kind') in {'stock', 'local'}):
        return result
    preparation = work.get('preparation', {})
    if preparation.get('snapshot_hashes'):
        if not preparation_paths(work['id'], preparation['operation_key'])['snapshot'].is_dir():
            return {**result, 'reason': '冻结内容许可文件缺失，不能重新制造授权'}
        snapshot = _load_snapshot(work, preparation)
        if (snapshot['hashes']['production_brief'] != plan.context_refs.get('production_brief_sha256')
                or snapshot['bundle']['production_brief']['ai_generation_allowed'] is not True):
            return {**result, 'reason': '冻结 Brief 未允许生成或许可来源不匹配'}
    elif plan.context_refs.get('production_brief_sha256'):
        return {**result, 'reason': '缺少可核对的冻结内容许可'}
    gate, observation = attempt.get('material_gate', {}), attempt.get('material_observation', {})
    if (need.need_id not in gate.get('blocking_needs', [])
            or gate.get('plan_revision') != MaterialReadinessCalculator.plan_revision(plan)
            or observation.get('status') != 'COMPLETE'
            or observation.get('plan_revision') != gate.get('plan_revision')
            or observation.get('bundle_revision') != gate.get('bundle_revision')):
        return {**result, 'reason': '素材观察未完成或依据已变化；报告故障不触发生图'}
    store = AttemptMaterialStore(attempt['workspace']['path'])
    bundle = store.read_bundle()
    if bundle.revision != gate.get('bundle_revision'):
        return result
    matcher = MaterialMatcher()
    if matcher.match(need, bundle.assets).matches:
        return {**result, 'reason': '已有合格覆盖'}
    outcomes = {r['asset_id']: r for r in observation.get('outcomes', [])
                if r.get('need_id') == need.need_id and r.get('need_sha256') == need_identity(need)}
    from easel.materials.application.visual_observation import observed_match
    pool = [a for a in bundle.assets if a.media_type is need.media_type]
    candidates = [a for a in pool if a.asset_id in outcomes or observed_match(need, a) is True]
    unobserved = [a for a in pool if a not in candidates]
    progress = observation.get('candidate_progress', {}).get(need.need_id, {})
    if progress.get('next_candidates') and progress.get('stop_reason') == 'batch_complete':
        return {**result, 'reason': '仍有更有依据的未观察候选，应先接续小批'}
    valid_rejections = 0
    for asset in candidates:
        row = outcomes.get(asset.asset_id, {})
        if row.get('asset_sha256') != asset.file.sha256:
            return {**result, 'reason': '观察身份失效，不能触发生图'}
        from easel.materials.application.visual_observation import read_observation_report
        identity = row.get('input_sha256', '')
        if not isinstance(identity, str) or not re.fullmatch(r'[0-9a-f]{64}', identity):
            return result
        input_path = store.materials_root / 'observations' / (identity + '.input.json')
        try:
            if input_path.is_symlink():
                return result
            manifest = json.loads(input_path.read_text())
            report = read_observation_report(store.materials_root / 'observations' / (identity + '.json'), need, asset, manifest)
            path = store.resolve_asset_locator(asset.file.path)
            if hashlib.sha256(path.read_bytes()).hexdigest() != asset.file.sha256:
                return result
            if report['verdict'] == 'suitable':
                return {**result, 'reason': '内容合适但准入缺证，先处理权利或技术条件'}
            if report['verdict'] == 'unsuitable' or (report['verdict'] == 'partial'
                    and report.get('failure_kind') in {'content_mismatch', 'hard_constraint'}
                    and any(f.get('meets_requirements') is False for f in report['frames'])):
                valid_rejections += 1
        except (ValueError, OSError, TypeError, AttributeError):
            return {**result, 'reason': '有效负面报告缺失或失效，不能触发生图'}
    path = store.materials_root / 'product-supply.json'
    if path.is_symlink() or not path.is_file():
        return {**result, 'reason': '尚无 Library-first / 检索证据'}
    evidence = json.loads(path.read_text())
    trace = next((r for r in evidence.get('routing', []) if r.get('need_id') == need.need_id), {})
    if (evidence.get('attempt_id') != attempt['attempt_id']
            or evidence.get('plan_revision') != gate.get('plan_revision') or not trace.get('attempted_sources')
            or trace.get('failures')):
        return {**result, 'reason': '检索未执行或调用故障，不能当作召回不足'}
    if candidates and not valid_rejections:
        return {**result, 'reason': '只有缺证或未知，不能当作真实召回失败'}
    budget = work['delivery'].get('call_budgets', {}).get('material')
    # Reserve verification room for every remaining permitted image gap.
    remaining_generation_needs = [n for n in plan.needs if n.need_id in gate.get('blocking_needs', [])
        and n.media_type is MediaType.IMAGE and n.constraints.get('allow_generation') is True]
    reserve = 7 * max(1, len(remaining_generation_needs))
    if budget and budget['limit'] - budget['used'] < reserve:
        return {**result, 'reason': '累计调用空间不足以生成并验证', 'reserved_calls': reserve}
    return {**result, 'eligible': True, 'reason': '相关有界检索无可用覆盖；静态图许可成立，仅补当前缺口',
            'reserved_calls': reserve, 'remaining_calls': budget['limit'] - budget['used'] if budget else None,
            'rejected_associations': len(candidates), 'remaining_low_yield_candidates': len(unobserved),
            'generation_elapsed_estimate': 'unknown'}


def generate_for_commission(attempt_id: str) -> None:
    from easel.creation_delivery import active_delivery, is_managed
    from easel.integrations.hypit.service import get_film_attempt
    from easel.integrations.material_layer import PlanningIntegration, MaterialProductOrchestrator

    attempt = get_film_attempt(attempt_id)
    work = creation.get_creation(attempt['creation_id'])
    if not is_managed(work) or active_delivery.get() != work['id']:
        raise creation.CreationError('委托内生成只能由当前作品的后台交付者执行')
    planning = PlanningIntegration().load(attempt)
    if planning['truth_ledger'].get('status') != 'PASSED':
        raise creation.CreationError('事实审阅尚未完成，未提交生成')
    choice = pending_generated_need(work, attempt, planning['plan'])
    if not choice:
        return
    need, request_id = choice
    if need.media_type.value == 'image':
        with creation.edit_creation(work['id']) as current:
            current['delivery'].setdefault('material_supply_decisions', []).append(
                {**image_fallback_decision(work, attempt, planning['plan'], need),
                 'request_id': request_id, 'created_at': creation._now()})
    authorization = work['delivery']['authorization']['material_generation']
    settings = EaselRuntimeConfig.load().minimax
    if (not settings.api_key or generation_scope(settings) != authorization['scope']
            or _scope_digest(settings, generation_scope(settings)) != authorization['scope_sha256']):
        raise GenerationQuoteUnavailable('素材服务或音色已偏离确认委托；未提交生成')
    modality = generation_need_modality(need)
    if modality not in authorized_generation_modalities(authorization):
        raise creation.CreationError('该素材生成类别不在当前委托授权内')
    fingerprint = commission_fingerprint(planning['plan'], planning['script'], authorization)
    store = AttemptMaterialStore(attempt['workspace']['path'])
    prior = work['delivery'].get('material_generations', {}).get(request_id)
    if prior is not None and prior.get('fingerprint') != fingerprint:
        raise creation.CreationError('已占用预算的请求输入已变化，不能认领原批准')
    try:
        execution = store.read_generation_record('gen-' + request_id)
    except GenerationRecordNotFound:
        execution = None
    # A fresh submit is quoted again even after a restart. A retained task/result
    # uses its original reservation and never buys a second generation.
    if execution is None:
        from easel.creation_delivery import active_delivery, reserve_delivery_call
        if active_delivery.get() == work['id']:
            with creation.edit_creation(work['id']) as current:
                reserve_delivery_call(current, category='generation_quote', stage_override='material', need_count=len(planning['plan'].needs))
        if any(getattr(n.modality_spec, 'kind', None) == 'bgm' for n in planning['plan'].needs):
            from easel.materials.application.music_observation import require_local_music_model
            require_local_music_model()  # Check known delivery dependencies before any new paid material.
        if modality == 'voice':
            from easel.materials.application.voice_delivery import require_local_voice_model
            require_local_voice_model()  # Do not buy audio we already know cannot be checked.
        try:
            quote = quote_generation(settings, modality=modality, text=planning['script'] if modality == 'voice' else '',
                seconds=MiniMaxVideoMaterialGeneration._duration(need) if modality == 'video' else 0,
                resolution=('480P' if settings.video_model == 'MiniMax-H3-Max' else '768P') if modality == 'video' else '')
        except GenerationQuoteReadFailed:
            raise  # The existing owner retries this read before asking for help.
        except GenerationQuoteUnavailable as exc:
            with creation.edit_creation(work['id']) as current:
                current['delivery'].setdefault('material_generations', {})[request_id] = {
                    'status': 'quote_unavailable', 'need_id': need.need_id, 'attempt_id': attempt_id, 'reason': str(exc)}
            return
        with creation.edit_creation(work['id']) as current:
            ledger = current['delivery'].setdefault('material_generations', {})
            held = sum((Decimal(r['quote']['upper_estimate']) for key, r in ledger.items()
                        if key != request_id and r.get('quote')), Decimal(0))
            if held + Decimal(quote['upper_estimate']) > Decimal(authorization['max_amount']):
                ledger[request_id] = {'status': 'budget_exceeded', 'need_id': need.need_id,
                                      'attempt_id': attempt_id, 'reason': '所需生成费用超出委托剩余额度；未提交生成'}
                return
            if active_delivery.get() == work['id']:
                reserve_delivery_call(current, category='generation_submit', stage_override='material', need_count=len(planning['plan'].needs))
            ledger[request_id] = {'status': 'reserved', 'attempt_id': attempt_id, 'need_id': need.need_id,
                                 'fingerprint': fingerprint, 'quote': quote, 'reserved_at': creation._now()}
    elif execution.get('status') in {'GENERATING', 'SUBMITTING', 'SUBMISSION_UNCERTAIN'}:
        with creation.edit_creation(work['id']) as current:
            current['delivery']['material_generations'][request_id].update(
                status='uncertain', reason='生成请求结果尚未核实，费用额度继续保留；不会重复提交')
        return
    # The generation service commits its own request before Provider submission.
    # Reuse the same id after restart; GENERATED/uncertain is never resubmitted.
    try:
        result = MaterialProductOrchestrator().generate_minimax_asset(
            attempt_id, need_id=need.need_id, request_id=request_id, confirmed_paid=True,
            commission_request=request_id,
        )
    except Exception as exc:
        try:
            record = store.read_generation_record('gen-' + request_id)
        except GenerationRecordNotFound:
            raise  # No Provider submission record: normal bounded local retry.
        received = record.get('status') in {'COMPLETE', 'RESULT_RECEIVED', 'RESULT_INTAKE_FAILED'} and (
            record.get('received_asset') or record.get('asset_id'))
        if (record.get('modality') == 'video' and record.get('status') in {'RUNNING', 'RESULT_FAILED'}
                and record.get('task_id')):
            from easel.materials.providers.minimax_video import MiniMaxVideoObservationPending
            if isinstance(exc, MiniMaxVideoObservationPending):
                from easel.creation_delivery import DeliveryObservationPending
                raise DeliveryObservationPending(str(exc), disconnected=exc.task_status is None) from exc
            raise  # Keep the reservation; next call observes the same Provider task.
        with creation.edit_creation(work['id']) as current:
            current['delivery']['material_generations'][request_id].update(
                status='received' if received else 'uncertain',
                reason=None if received else '生成结果尚未核实，费用额度继续保留；不会重复提交')
        if not received:
            return
        raise
    with creation.edit_creation(work['id']) as current:
        current['delivery']['material_generations'][request_id].update(
            status='complete', asset_id=result['generation']['asset_id'], completed_at=creation._now())


def assert_commission_request(attempt, plan, script, settings, request_id, need_id):
    """Recheck the real executor's current inputs against the reserved quote."""
    from easel.creation_delivery import active_delivery, is_managed
    work = creation.get_creation(attempt['creation_id'])
    grant = work.get('delivery', {}).get('authorization', {}).get('material_generation')
    receipt = work.get('delivery', {}).get('material_generations', {}).get(request_id, {})
    need = next((item for item in plan.needs if item.need_id == need_id), None)
    if (not is_managed(work) or active_delivery.get() != work['id'] or not grant
            or receipt.get('status') != 'reserved' or receipt.get('attempt_id') != attempt['attempt_id']
            or receipt.get('need_id') != need_id or need is None
            or generation_need_modality(need) not in authorized_generation_modalities(grant)
            or generation_scope(settings) != grant['scope']
            or _scope_digest(settings, generation_scope(settings)) != grant['scope_sha256']
            or receipt.get('fingerprint') != commission_fingerprint(plan, script, grant)):
        raise creation.CreationError('当前生成请求不在已核价的委托授权内')
    from easel.integrations.voice_identity import require_binding
    try:
        binding = require_binding(work, plan, script)
    except ValueError as exc:
        raise creation.CreationError(str(exc)) from exc
    # Preserve the evidence available before submission. A later public-page
    # revision must not replace the agreement attached to an existing result.
    return {'creation_id': work['id'], 'request_id': request_id, 'source': 'commission_budget',
            'scope_sha256': grant['scope_sha256'], 'quote': receipt['quote'],
            'input_use': work['delivery']['authorization'].get('input_use'),
            **({'voice_binding_sha256': binding['binding_sha256']}
               if binding is not None and generation_need_modality(need) == 'voice' else {})}
