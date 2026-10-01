"""Commission-bound calls into the existing Material generation service."""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal, InvalidOperation

from easel import creation
from easel.runtime_config import EaselRuntimeConfig
from easel.materials.application.generation import MiniMaxVideoMaterialGeneration
from easel.materials.application.routing import MaterialSourceRouter
from easel.materials.providers.minimax_pricing import GenerationQuoteUnavailable, GenerationQuoteReadFailed, quote_generation
from easel.materials.providers.minimax_speech import MINIMAX_SPEECH_MODELS
from easel.materials.providers.minimax_video import MINIMAX_VIDEO_MODELS
from easel.materials.store import AttemptMaterialStore, GenerationRecordNotFound


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


def commission_generation_authorization(budget: dict | None) -> dict | None:
    if budget is None:
        return None
    try:
        if set(budget) != {'maxCostCny', 'scopeSha256'} or isinstance(budget['maxCostCny'], bool):
            raise ValueError
        amount = Decimal(str(budget['maxCostCny']))
        if not amount.is_finite() or not 0 < amount <= 1000 or amount.as_tuple().exponent < -2:
            raise ValueError
    except (InvalidOperation, ValueError, KeyError, TypeError) as exc:
        raise creation.CreationError('素材预算须为 0～1000 元之间的正数，最多两位小数') from exc
    preview = generation_budget_preview()
    if not preview.get('available') or budget['scopeSha256'] != preview.get('scope_sha256'):
        raise creation.CreationError('素材服务或音色配置已变化，请核对当前方案中的费用范围')
    return {'currency': 'CNY', 'max_amount': str(amount), 'scope': preview['scope'],
            'scope_sha256': preview['scope_sha256']}


def pending_generated_need(work, attempt, plan):
    authorization = work.get('delivery', {}).get('authorization', {}).get('material_generation')
    if not authorization:
        return None
    records = work['delivery'].get('material_generations', {})
    blocking = set(attempt.get('material_gate', {}).get('blocking_needs', []))
    # One initial generation per Need/draft. Unknown outcomes never open another
    # request id. Successful media with unresolved Rights are not regenerated.
    revision = hashlib.sha256(plan.to_json().encode()).hexdigest()
    retained = AttemptMaterialStore(attempt['workspace']['path']).list_generation_records()
    for need in plan.needs:
        if (need.need_id not in blocking or need.constraints.get('allow_generation') is False
                or not MaterialSourceRouter._generation_eligible(need)):
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
    authorization = work['delivery']['authorization']['material_generation']
    settings = EaselRuntimeConfig.load().minimax
    if (not settings.api_key or generation_scope(settings) != authorization['scope']
            or _scope_digest(settings, generation_scope(settings)) != authorization['scope_sha256']):
        raise GenerationQuoteUnavailable('素材服务或音色已偏离确认委托；未提交生成')
    modality = 'voice' if need.media_type.value == 'audio' else need.media_type.value
    fingerprint = _digest([planning['plan'].to_json(), planning['script'], authorization['scope']])
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
    if (not is_managed(work) or active_delivery.get() != work['id'] or not grant
            or receipt.get('status') != 'reserved' or receipt.get('attempt_id') != attempt['attempt_id']
            or receipt.get('need_id') != need_id
            or generation_scope(settings) != grant['scope']
            or _scope_digest(settings, generation_scope(settings)) != grant['scope_sha256']
            or receipt.get('fingerprint') != _digest([plan.to_json(), script, grant['scope']])):
        raise creation.CreationError('当前生成请求不在已核价的委托授权内')
    # Preserve the evidence available before submission. A later public-page
    # revision must not replace the agreement attached to an existing result.
    return {'creation_id': work['id'], 'request_id': request_id, 'source': 'commission_budget',
            'scope_sha256': grant['scope_sha256'], 'quote': receipt['quote'],
            'input_use': work['delivery']['authorization'].get('input_use')}
