"""Bounded Creator-authorized source revision and supplemental supply."""

from __future__ import annotations

import fcntl
import hashlib
import json
from datetime import datetime, timezone

from easel.integrations.hypit.service import get_film_attempt, update_film_attempt
from easel.integrations.material_layer import (
    MaterialGateIntegration, MaterialIntegrationError, MaterialProductOrchestrator,
    PlanningIntegration, ProductionAuthoringIntegration,
)
from easel.integrations.material_supply import ProductMaterialSupply
from easel.materials.application.assembly import MaterialBundleAssembler
from easel.materials.application.compiler import NeedCompiler
from easel.materials.application.dedup import MaterialDeduplicator
from easel.materials.application.matching import MaterialMatcher
from easel.materials.application.readiness import MaterialReadinessCalculator
from easel.materials.domain import MaterialBundle, MaterialPlan, ReadinessStatus, SupplyRun
from easel.materials.store import AttemptMaterialStore
from easel.runtime_config import EaselRuntimeConfig


def _production_started(attempt: dict) -> bool:
    authoring = attempt.get('production_authoring') or {}
    return bool(authoring and (authoring.get('status') != 'PENDING_SELECTION'
                               or authoring.get('selected_asset_ids'))
                or attempt.get('authoring_status') not in {None, 'PENDING', 'READY_FOR_EXTERNAL_AUTHORING'})


def repair_managed_planning(attempt_id: str, *, executor) -> dict:
    """Repair writing in the existing fork, then rematch retained media.

    The owner serializes this operation. Cache the validated model result
    before updating any checkpoints, so interrupted persistence never causes
    another rewrite, supply request or purchase.
    """
    from easel import creation
    from easel.creation_delivery import active_delivery, is_managed
    from easel.integrations.hypit.service import _execution_fingerprint, _file_sha256, _output_path
    from easel.integrations.hypit.quality import repair_request

    attempt = get_film_attempt(attempt_id)
    work = creation.get_creation(attempt['creation_id'])
    record = attempt.get('planning_repair', {})
    request = record.get('request', {})
    source = get_film_attempt(attempt.get('retry_source', {}).get('attempt_id', ''))
    if (not is_managed(work) or active_delivery.get() != work['id']
            or work.get('selected_output_name') or source['creation_id'] != work['id']
            or source['attempt_id'] not in work['delivery'].get('quality_repairs', [])
            or 'planning' not in request.get('allowed_changes', [])
            or repair_request(source) != request
            or _execution_fingerprint(source)['sha256'] != attempt['retry_source']['fingerprint']
            or _file_sha256(_output_path(source, source['outputs'][request['output_name']])) != request['sha256']):
        raise MaterialIntegrationError('内容修正必须由当前委托 Owner 执行，并绑定未变化的原成片与审片证据')
    if record.get('status') == 'COMPLETE':
        return attempt
    if _production_started(attempt) or attempt.get('execution_status') != 'NOT_SUBMITTED':
        raise MaterialIntegrationError('内容修正尚未完成，不能覆盖已开始的制作')
    original = PlanningIntegration().load(source)
    old_plan, old_bundle, _ = MaterialGateIntegration().assert_ready(source)
    store = AttemptMaterialStore(attempt['workspace']['path'])
    cache_key = 'planning-' + request['quality_report_sha256'][:32]
    cached = store.read_recovery_record(cache_key)
    if cached is None:
        result = executor(attempt, {'context_refs': old_plan.context_refs, 'quality_repair': request})
        cached = {key: result.get(key) for key in ('treatment', 'script', 'scenes', 'script_assessment')}
        cached['plan'] = result['plan'].model_dump(mode='json')
        cached['request'] = request
    plan = MaterialPlan.model_validate_json(json.dumps(cached['plan']))
    if (cached.get('request') != request or plan.creation_id != work['id']
            or plan.attempt_id != attempt_id or plan.plan_id != f"plan-{attempt_id[-20:]}"
            or plan.context_refs != old_plan.context_refs or plan.policy != old_plan.policy
            or tuple(n.need_id for n in plan.needs) != tuple(n.need_id for n in old_plan.needs)):
        raise MaterialIntegrationError('内容修正不能改变委托依据、素材策略或需求身份')
    for old, new in zip(old_plan.needs, plan.needs):
        # V1 rewrites words/scene order/visual intent, not the commission's
        # source policy, voice identity or technical scope. Persist alone
        # binds a changed Script to Voice; the model cannot loosen it.
        visual = old.media_type.value in {'image', 'video'}
        if (old.model_copy(update={'intent': new.intent}) if visual else old) != new:
            raise MaterialIntegrationError('内容修正仅可调整需求表达，不得改变用途、来源约束或声音身份')
        NeedCompiler().compile(new)
    if any(not isinstance(cached.get(key), str) or not cached[key].strip()
           for key in ('treatment', 'script', 'scenes')):
        raise MaterialIntegrationError('内容修正缺少完整规划稿')
    if all(cached[key] == original[key] for key in ('treatment', 'script', 'scenes')) and plan.needs == old_plan.needs:
        raise MaterialIntegrationError('系统内容修正没有形成任何实际修改')
    store.write_recovery_record(cache_key, cached)
    persisted = PlanningIntegration().persist(attempt, plan, treatment=cached['treatment'],
        script=cached['script'], scenes=cached['scenes'], script_assessment=cached.get('script_assessment'))
    attempt, plan = persisted['attempt'], persisted['plan']
    if persisted['truth_ledger']['status'] != 'PASSED':
        return update_film_attempt(attempt_id, event='planning_repair_truth_required',
            planning_repair={**record, 'status': 'TRUTH_REQUIRED'})
    for asset in old_bundle.assets:
        path = store.resolve_asset_locator(asset.file.path)
        if path.stat().st_size != asset.file.size or _file_sha256(path) != 'sha256:' + asset.file.sha256:
            raise MaterialIntegrationError('保留素材的字节或证据已变化，不能复用')
        if store.read_asset(asset.asset_id) != asset:
            raise MaterialIntegrationError('保留素材记录与原 Bundle 不一致：' + asset.asset_id)
    accepted = ProductionAuthoringIntegration.accepted_combination(
        source, old_plan, old_bundle, AttemptMaterialStore(source['workspace']['path']))
    old_needs = {n.need_id: n for n in old_plan.needs}
    retained = {n.need_id: accepted[n.need_id] for n in plan.needs
                if n.need_id in accepted and n == old_needs.get(n.need_id)}
    marker = {}
    if retained:
        revision = MaterialReadinessCalculator.plan_revision(plan)
        request_id = 'combination-' + hashlib.sha256(
            json.dumps({'plan_revision': revision, 'choices': retained}, sort_keys=True).encode()).hexdigest()
        store.write_recovery_record(request_id, {'status': 'COMPLETE', 'plan_revision': revision,
            'choices': retained, 'inherited_from': source['attempt_id']})
        marker = {'status': 'COMPLETE', 'request_id': request_id}
    attempt = update_film_attempt(attempt_id, event='planning_repair_material_choices_rebound',
                                 material_combination_review=marker)
    matches = MaterialProductOrchestrator._rank_reviewed_materials(attempt, plan, old_bundle.assets, store)
    now = datetime.now(timezone.utc)
    run = SupplyRun(supply_run_id='planning-' + attempt_id[-20:], plan_id=plan.plan_id,
        parent_run_id=old_bundle.supply_run_id, started_at=now, finished_at=now,
        result_bundle_id='bundle-' + attempt_id[-20:])
    bundle = MaterialBundleAssembler().assemble(plan, run, old_bundle.assets, tuple(matches),
                                               bundle_id=run.result_bundle_id)
    readiness, gaps = MaterialReadinessCalculator(store=store).calculate(plan, bundle)
    attempt = MaterialGateIntegration().record(attempt, plan, bundle, run, readiness, gaps)['attempt']
    # Changed Needs invalidate their scoped observation automatically. The
    # regular owner now observes, supplements and (only if needed) requotes.
    if readiness.status is ReadinessStatus.READY:
        attempt = ProductionAuthoringIntegration().prepare(attempt, selected_asset_ids=())['attempt']
    return update_film_attempt(attempt_id, event='planning_repair_completed',
        planning_repair={**record, 'status': 'COMPLETE',
                         'plan_revision': readiness.plan_revision,
                         'script_sha256': persisted['truth_ledger']['script_sha256']},
        material_observation={}, preparation_status='PRODUCTION_PREPARED'
            if readiness.status is ReadinessStatus.READY else 'MATERIAL_NOT_READY')


def visual_supply_recovery_state(attempt: dict) -> str | None:
    """A bounded second search is system work, not a Creator evidence task."""
    record = attempt.get('autonomous_material_recovery') or {}
    gate = attempt.get('material_gate') or {}
    if (record.get('status') != 'COMPLETE' or record.get('quality_report_sha256')
            or gate.get('status') != 'MATERIAL_NOT_READY'
            or record.get('plan_revision') != gate.get('plan_revision')):
        return None
    from easel.materials.application.visual_observation import observed_match
    store = AttemptMaterialStore(attempt['workspace']['path'])
    plan, bundle = store.read_plan(), store.read_bundle()
    missing = [n for n in plan.needs if n.need_id in gate.get('blocking_needs', [])
               and n.media_type.value in {'image', 'video'}]
    if not missing:
        return None
    outcomes = attempt.get('material_observation', {}).get('outcomes', [])
    eligible = []
    for need in missing:
        if any(observed_match(need, asset) is True for asset in bundle.assets):
            continue  # A Rights gap in this Need doesn't block other Needs.
        rows = [r for r in outcomes if r.get('need_id') == need.need_id]
        hard_missing = any(r.get('verdict') == 'unsuitable' or r.get('failure_kind') in {'content_mismatch', 'hard_constraint'} for r in rows)
        if any(r.get('verdict') == 'uncertain' for r in rows) and not hard_missing:
            continue
        eligible.append(need)
    if not eligible:
        return None
    return 'available' if len(record.get('previous_rounds', [])) < 1 else 'exhausted'


def recover_managed_materials(attempt_id: str, *, executor) -> dict:
    """Bounded commissioned supplemental searches; preserve Need, Rights and Voice."""
    from easel import creation
    from easel.creation_delivery import active_delivery, is_managed
    attempt = get_film_attempt(attempt_id)
    if not is_managed(creation.get_creation(attempt['creation_id'])):
        raise MaterialIntegrationError('自动补料只适用于明确委托持续交付的新作品')
    store = AttemptMaterialStore(attempt['workspace']['path'])
    planning = PlanningIntegration().load(attempt)
    record = attempt.get('autonomous_material_recovery')
    revision = attempt.get('revision_feedback', {})
    if ((record or {}).get('quality_report_sha256')
            or (revision.get('origin') == 'system_quality' and 'visual_material' in revision.get('allowed_changes', []))):
        if active_delivery.get() != attempt['creation_id']:
            raise MaterialIntegrationError('额外视觉补料只能由当前委托 Owner 执行')
    previous_rounds = []
    if record and record.get('status') in {'COMPLETE', 'NOT_APPLICABLE'}:
        if visual_supply_recovery_state(attempt) != 'available':
            return attempt
        previous_rounds = record.get('previous_rounds', []) + [
            {key: value for key, value in record.items() if key != 'previous_rounds'}]
        record = None
    if record is None:
        gate = attempt.get('material_gate', {})
        revision = attempt.get('revision_feedback', {})
        quality = (revision.get('origin') == 'system_quality'
                   and 'visual_material' in revision.get('allowed_changes', []))
        if (gate.get('status') != ('MATERIAL_READY' if quality else 'MATERIAL_NOT_READY')
                or planning['truth_ledger']['status'] != 'PASSED'):
            raise MaterialIntegrationError('自动补料需要当前素材缺口和有效的内容依据')
        if quality:
            from easel.integrations.hypit.service import quality_visual_replacement_gaps
            need_ids = quality_visual_replacement_gaps(attempt)
        else:
            need_ids = gate['blocking_needs']
            uncertain = {r['need_id'] for r in attempt.get('material_observation', {}).get('outcomes', [])
                         if r.get('verdict') == 'uncertain'}
            hard_missing = {r['need_id'] for r in attempt.get('material_observation', {}).get('outcomes', [])
                            if r.get('verdict') == 'unsuitable' or r.get('failure_kind') in {'content_mismatch', 'hard_constraint'}}
            need_ids = [nid for nid in need_ids if nid not in uncertain or nid in hard_missing]
        needs = [n.model_dump(mode='json') for n in planning['plan'].needs
                 if n.need_id in need_ids and getattr(n.modality_spec, 'kind', None) != 'voice']
        identity = hashlib.sha256((attempt_id + gate['plan_revision'] + gate['bundle_revision']
                                   + (f':round-{len(previous_rounds) + 1}' if previous_rounds else '')).encode()).hexdigest()
        record = {'status': 'PLANNING' if needs else 'NOT_APPLICABLE', 'request_id': 'auto-' + identity[:32],
                  'plan_revision': gate['plan_revision'], 'bundle_revision': gate['bundle_revision'], 'needs': needs,
                  'shot_choice_need_ids': [n['need_id'] for n in needs
                      if n['media_type'] in {'image', 'video'} and n['constraints'].get('preferred_visual_details')],
                  **({'previous_rounds': previous_rounds} if previous_rounds else {}),
                  **({'quality_report_sha256': revision['quality_report_sha256']} if quality else {})}
        attempt = update_film_attempt(attempt_id, event='automatic_material_recovery_started',
                                      autonomous_material_recovery=record)
        if not needs:
            return attempt  # Voice generation has its own paid and identity contracts.
    if record['status'] == 'PLANNING':
        if (attempt['material_gate']['plan_revision'] != record['plan_revision']
                or attempt['material_gate']['bundle_revision'] != record['bundle_revision']):
            raise MaterialIntegrationError('补料期间素材依据已变化，原结果已保留')
        request_id = record['request_id'] + '-queries'
        cached = store.read_recovery_record(request_id)
        if cached is None and not record.get('quality_report_sha256'):
            # Use compiled alternatives first. Only a new/uncovered reason
            # requires another model-authored recovery plan.
            prepared = {}
            for raw in record['needs']:
                need = next(n for n in planning['plan'].needs if n.need_id == raw['need_id'])
                variants = need.constraints.get('search_query_variants_en', {})
                alternatives = [variants[k] for k in ('alternate', 'relaxed') if variants.get(k)]
                if not alternatives:
                    for path in sorted((store.materials_root / 'recoveries').glob('requirements-*.json')):
                        if path.is_symlink():
                            raise MaterialIntegrationError('要求合同路径无效')
                        contract = json.loads(path.read_text()).get('contract', {})
                        from easel.materials.application.visual_observation import need_identity
                        if contract.get('need_sha256') == need_identity(need) and contract.get('queries'):
                            alternatives = contract['queries'][1:]
                            break
                tried = {q.casefold() for r in record.get('previous_rounds', [])
                         for q in r.get('search_terms', {}).get(need.need_id, [])}
                primary = need.constraints.get('search_query_en', '')
                alternatives = [q for q in alternatives if q.casefold() not in tried and q != primary]
                if alternatives:
                    prepared[need.need_id] = alternatives[:1]
            if set(prepared) == {n['need_id'] for n in record['needs']} and prepared:
                record = {**record, 'shot_choice_need_ids': []}
                cached = {'request_id': record['request_id'], 'search_terms': prepared}
                attempt = update_film_attempt(attempt_id, event='compiled_queries_reused', autonomous_material_recovery=record)
        if cached is None:
            cached = executor(attempt, record)
            validate_recovery_queries(record, cached)
            store.write_recovery_record(request_id, cached)
        validate_recovery_queries(record, cached)
        record = {**record, 'status': 'SUPPLYING', 'search_terms': cached['search_terms'],
                  **({'shot_choices': cached['shot_choices']} if record.get('shot_choice_need_ids') else {})}
        attempt = update_film_attempt(attempt_id, event='automatic_material_recovery_queries_ready',
                                      autonomous_material_recovery=record)
    result = recover_materials(attempt_id, request_id=record['request_id'],
        expected_plan_revision=record['plan_revision'], expected_bundle_revision=record['bundle_revision'],
        allow_licensed_bgm=False, search_terms={key: tuple(value) for key, value in record['search_terms'].items()},
        quality_report_sha256=record.get('quality_report_sha256'))
    return update_film_attempt(attempt_id, event='automatic_material_recovery_completed',
        autonomous_material_recovery={**record, 'status': 'COMPLETE',
                                     'result_bundle_revision': result['attempt']['material_gate']['bundle_revision']})


def validate_recovery_queries(record: dict, report: dict) -> None:
    """Delegate optional shot details, never mutation of the frozen Need."""
    from easel.materials.domain import MaterialNeed
    terms = report.get('search_terms')
    shot_ids = record.get('shot_choice_need_ids', [])
    keys = {'request_id', 'search_terms'} | ({'shot_choices'} if shot_ids else set())
    if (set(report) != keys or report.get('request_id') != record['request_id'] or not isinstance(terms, dict)
            or set(terms) != {n['need_id'] for n in record['needs']}):
        raise MaterialIntegrationError('补料检索建议必须覆盖当前缺口并绑定当前请求')
    if shot_ids:
        choices = report.get('shot_choices')
        if not isinstance(choices, dict) or set(choices) != set(shot_ids):
            raise MaterialIntegrationError('镜头取舍须覆盖当前可替代视觉需求')
        for choice in choices.values():
            if (not isinstance(choice, dict) or set(choice) != {'expression', 'reason'}
                    or any(not isinstance(v, str) or not v.strip() or len(v) > 1200 for v in choice.values())):
                raise MaterialIntegrationError('镜头取舍须说明替代表达及依据，不能改写核心需求')
    for raw in record['needs']:
        value = terms[raw['need_id']]
        if not isinstance(value, list) or not value or any(not isinstance(v, str) for v in value):
            raise MaterialIntegrationError('补料检索建议须为短语列表')
        used = {' '.join(term.casefold().split()) for previous in record.get('previous_rounds', [])
                for term in previous.get('search_terms', {}).get(raw['need_id'], [])}
        if any(' '.join(term.casefold().split()) in used for term in value):
            raise MaterialIntegrationError('补料检索建议重复了已尝试的短语，须根据观察证据调整')
        need = MaterialNeed.model_validate_json(json.dumps(raw))
        compiled = NeedCompiler(search_terms={raw['need_id']: tuple(value)}).compile(need)
        if need.constraints.get('search_query_en'):
            query = compiled.semantic_queries[0]
            if (query != NeedCompiler._normalize(value[0]) or len(query) > 100
                    or query.casefold() == NeedCompiler._normalize(need.constraints['search_query_en']).casefold()):
                raise MaterialIntegrationError('补料须提供实质变化的英文优先短查询，不能回退到原主查询')


def director_shot_choices(attempt: dict, plan: MaterialPlan) -> dict:
    """Project completed directing decisions without rewriting the Plan.

    SUPPLYING is included because supply prepares Authoring before its caller
    marks the same recovery COMPLETE. Evidence remains tied to the whole Plan.
    """
    current = attempt.get('autonomous_material_recovery') or {}
    result = {}
    revision = MaterialReadinessCalculator.plan_revision(plan)
    needs = {n.need_id: n.model_dump(mode='json') for n in plan.needs}
    inherited = attempt.get('director_shot_checkpoint') or {}
    if inherited.get('plan_revision') == revision:
        for need_id, choice in inherited['choices'].items():
            if (need_id not in needs or choice.get('core_requirement') != needs[need_id]['intent']['description']
                    or choice.get('optional_details') != needs[need_id]['constraints'].get('preferred_visual_details')):
                raise MaterialIntegrationError('恢复镜头取舍与当前核心要求不一致')
        result.update(inherited['choices'])
    for record in [*current.get('previous_rounds', []), current]:
        if not record.get('shot_choices') or record.get('status') not in {'SUPPLYING', 'COMPLETE'}:
            continue
        if record.get('plan_revision') != revision or any(needs.get(n['need_id']) != n for n in record['needs']):
            raise MaterialIntegrationError('镜头取舍与当前素材规划不一致，不能沿用')
        report = {'request_id': record['request_id'], 'search_terms': record['search_terms'],
                  'shot_choices': record['shot_choices']}
        validate_recovery_queries(record, report)
        for need_id, choice in record['shot_choices'].items():
            result[need_id] = {**choice, 'request_id': record['request_id'],
                               'core_requirement': needs[need_id]['intent']['description'],
                               'optional_details': needs[need_id]['constraints']['preferred_visual_details']}
    return result


def recover_materials(attempt_id: str, *, request_id: str, expected_plan_revision: str,
                      expected_bundle_revision: str, allow_licensed_bgm: bool,
                      search_terms: dict[str, tuple[str, ...]], quality_report_sha256: str | None = None) -> dict:
    """Preserve content and acquired facts; never generate or submit production."""
    attempt = get_film_attempt(attempt_id)
    store = AttemptMaterialStore(attempt["workspace"]["path"])
    # The store validates the request locator before using it for a lock.
    store.read_recovery_record(request_id)
    lock_path = store.materials_root / "recovery.lock"
    if lock_path.is_symlink():
        raise MaterialIntegrationError("素材恢复锁路径无效")
    with lock_path.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        return _recover_locked(attempt_id, store, request_id, expected_plan_revision,
                               expected_bundle_revision, allow_licensed_bgm, search_terms, quality_report_sha256)


def _recover_locked(attempt_id, store, request_id, expected_plan_revision,
                    expected_bundle_revision, allow_licensed_bgm, search_terms, quality_report_sha256=None):
    attempt = get_film_attempt(attempt_id)
    if quality_report_sha256 is not None:
        from easel import creation
        from easel.creation_delivery import active_delivery, is_managed
        from easel.integrations.hypit.service import _execution_fingerprint
        revision = attempt.get('revision_feedback', {})
        if (active_delivery.get() != attempt['creation_id'] or not is_managed(creation.get_creation(attempt['creation_id']))
                or revision.get('origin') != 'system_quality' or 'visual_material' not in revision.get('allowed_changes', [])
                or revision.get('quality_report_sha256') != quality_report_sha256 or allow_licensed_bgm):
            raise MaterialIntegrationError('额外视觉补料必须由当前委托 Owner 绑定系统审片执行')
        original = get_film_attempt(attempt['retry_source']['attempt_id'])
        if (original['creation_id'] != attempt['creation_id']
                or _execution_fingerprint(original)['sha256'] != attempt['retry_source']['fingerprint']
                or PlanningIntegration().load(original)['plan'].needs != PlanningIntegration().load(attempt)['plan'].needs):
            raise MaterialIntegrationError('原成片依据已变化，不能继续该次视觉补料')
    fingerprint = hashlib.sha256(json.dumps({
        "attempt_id": attempt_id, "plan_revision": expected_plan_revision,
        "bundle_revision": expected_bundle_revision, "allow_licensed_bgm": allow_licensed_bgm,
        "search_terms": search_terms,
        **({'quality_report_sha256': quality_report_sha256} if quality_report_sha256 is not None else {}),
    }, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    record = store.read_recovery_record(request_id)
    planning = PlanningIntegration().load(attempt)
    if record:
        if record.get("fingerprint") != fingerprint:
            raise MaterialIntegrationError("相同素材恢复请求不能改变输入")
        if MaterialReadinessCalculator.plan_revision(planning["plan"]) not in {
                expected_plan_revision, record["target_plan_revision"]}:
            raise MaterialIntegrationError("素材方案已变化，请刷新后重新处理")
        if record["status"] == "COMPLETE":
            return {"attempt": attempt, "material_status": attempt["material_gate"]["status"],
                    "recovery": {"status": "COMPLETE", "reused": True}}
        if (attempt.get("execution_status") not in {"NOT_SUBMITTED", "BLOCKED"}
                or attempt.get("cost", {}).get("approved")
                or _production_started(attempt) or attempt.get("outputs")):
            raise MaterialIntegrationError("视频制作已开始，不能覆盖素材规划；请使用当前阶段恢复或成片修改")
        source_plan = MaterialPlan.model_validate_json(json.dumps(record["source_plan"]))
        source_bundle = MaterialBundle.model_validate_json(json.dumps(record["source_bundle"]))
    else:
        # Missing/invalid Runtime blocks rendering, not material preparation.
        if (attempt.get("execution_status") not in {"NOT_SUBMITTED", "BLOCKED"}
                or attempt.get("cost", {}).get("approved")
                or _production_started(attempt) or attempt.get("outputs")):
            raise MaterialIntegrationError("视频制作已开始，不能覆盖素材规划；请使用当前阶段恢复或成片修改")
        source_plan = planning["plan"]
        source_bundle = store.read_bundle()
        gate = attempt.get("material_gate", {})
        if (gate.get("status") != ("MATERIAL_READY" if quality_report_sha256 else "MATERIAL_NOT_READY")
                or MaterialReadinessCalculator.plan_revision(source_plan) != expected_plan_revision
                or source_bundle.revision != expected_bundle_revision
                or gate.get("plan_revision") != expected_plan_revision
                or gate.get("bundle_revision") != expected_bundle_revision
                or gate.get("bundle_id") != source_bundle.bundle_id):
            raise MaterialIntegrationError("素材状态已变化，请刷新；不会重新检索或改写旧状态")
        allowed = set(gate.get("blocking_needs", []))
        if quality_report_sha256:
            from easel.integrations.hypit.service import quality_visual_replacement_gaps
            observed = attempt.get('material_observation', {})
            if (observed.get('quality_report_sha256') != quality_report_sha256
                    or observed.get('status') != 'COMPLETE' or observed.get('bundle_revision') != expected_bundle_revision
                    or observed.get('plan_revision') != expected_plan_revision):
                raise MaterialIntegrationError('补料前应先观察当前已有视觉候选')
            allowed = quality_visual_replacement_gaps(attempt)
        if set(search_terms) - allowed:
            raise MaterialIntegrationError("只能为当前缺口或已核实的视觉备选需求补充检索提示")
        record = {"schema": "easel-material-recovery@1", "status": "PREPARED",
                  "fingerprint": fingerprint, "attempt_id": attempt_id,
                  "created_at": datetime.now(timezone.utc).isoformat(),
                  "source_plan": source_plan.model_dump(mode="json"),
                  "source_bundle": source_bundle.model_dump(mode="json"),
                  "script_sha256": planning["truth_ledger"]["script_sha256"],
                  "allow_licensed_bgm": allow_licensed_bgm, "search_terms": search_terms}
    if planning["truth_ledger"]["script_sha256"] != record["script_sha256"]:
        raise MaterialIntegrationError("脚本已变化，不能复用本次旁白与内容审阅")
    needs = []
    for need in source_plan.needs:
        if need.need_id in search_terms and getattr(need.modality_spec, "kind", None) == "voice":
            raise MaterialIntegrationError("素材恢复不会检索或重新生成已冻结的旁白")
        if (allow_licensed_bgm and getattr(need.modality_spec, "kind", None) == "bgm"
                and need.constraints.get("required_source_kind") == "stock"):
            constraints = dict(need.constraints)
            del constraints["required_source_kind"]
            constraints["allow_generation"] = False
            need = need.model_copy(update={"constraints": constraints})
        NeedCompiler(search_terms=search_terms).compile(need)
        needs.append(need)
    target_plan = source_plan.model_copy(update={"needs": tuple(needs)})
    record["target_plan_revision"] = MaterialReadinessCalculator.plan_revision(target_plan)
    for asset in source_bundle.assets:
        persisted = store.read_asset(asset.asset_id)
        path = store.resolve_asset_locator(asset.file.path)
        if (persisted != asset or path.stat().st_size != asset.file.size
                or hashlib.sha256(path.read_bytes()).hexdigest() != asset.file.sha256):
            raise MaterialIntegrationError("已保留素材的字节或证据变化，拒绝覆盖")
    store.write_recovery_record(request_id, record)
    if record["status"] == "PREPARED":
        planning = PlanningIntegration().persist(
            attempt, target_plan, treatment=planning["treatment"],
            script=planning["script"], scenes=planning["scenes"],
        )
        attempt = planning["attempt"]
        now = datetime.now(timezone.utc)
        run = SupplyRun(supply_run_id=f"recover-{request_id}", plan_id=target_plan.plan_id,
                        parent_run_id=source_bundle.supply_run_id, started_at=now, finished_at=now,
                        result_bundle_id=source_bundle.bundle_id)
        matches = []
        for need in target_plan.needs:
            ranked = MaterialMatcher().match(need, source_bundle.assets)
            matches.extend(MaterialDeduplicator(store).deduplicate_and_diversify(
                ranked.matches, source_bundle.assets, top_k=3).shortlist)
        bundle = MaterialBundleAssembler().assemble(
            target_plan, run, source_bundle.assets, tuple(matches), bundle_id=source_bundle.bundle_id)
        readiness, gaps = MaterialReadinessCalculator(store=store).calculate(target_plan, bundle)
        attempt = MaterialGateIntegration().record(attempt, target_plan, bundle, run, readiness, gaps)["attempt"]
        record["status"] = "CHECKPOINT_READY"
        store.write_recovery_record(request_id, record)
    # A valid old generation is retained only for an exactly unchanged Need.
    retained = {asset.asset_id: asset for asset in source_bundle.assets}
    skip_need_ids = tuple(need.need_id for need in source_plan.needs
        if getattr(need.modality_spec, "kind", None) == "voice"
        and any(item.get("status") == "COMPLETE" and item.get("asset_id") in retained
                and item.get("schema") == "easel-material-generation@1"
                and item.get("attempt_id") == attempt_id
                and item.get("plan_id") == source_plan.plan_id
                and item.get("asset_sha256") == retained[item["asset_id"]].file.sha256
                and item.get("asset_path") == retained[item["asset_id"]].file.path
                and item.get("asset_bytes") == retained[item["asset_id"]].file.size
                and item.get("need_id") == need.need_id
                and item.get("plan_revision") == expected_plan_revision
                and item.get("input_sha256") == getattr(need.modality_spec, "text_sha256", None)
                for item in store.list_generation_records()))
    if quality_report_sha256:
        skip_need_ids = tuple(n.need_id for n in source_plan.needs if n.need_id not in search_terms)
    # Reconcile a completed Supply checkpoint before contacting Providers again.
    final_bundle = store.read_bundle()
    final_run_id = f"supplement-{request_id}"
    if final_bundle.supply_run_id == final_run_id:
        final_run = store.read_supply_run(final_run_id)
        if (final_run.plan_id != target_plan.plan_id or not final_run.finished_at
                or final_run.result_bundle_id != final_bundle.bundle_id):
            raise MaterialIntegrationError("素材补充提交结果不一致，不能重复检索")
        for asset in final_bundle.assets:
            path = store.resolve_asset_locator(asset.file.path)
            if (store.read_asset(asset.asset_id) != asset or path.stat().st_size != asset.file.size
                    or hashlib.sha256(path.read_bytes()).hexdigest() != asset.file.sha256):
                raise MaterialIntegrationError("素材补充结果证据变化，请刷新核对")
        readiness, gaps = MaterialReadinessCalculator(store=store).calculate(target_plan, final_bundle)
    else:
        roots = EaselRuntimeConfig.load().material_roots()
        supplied = ProductMaterialSupply(rights_facts=lambda candidate, asset:
            MaterialProductOrchestrator._local_rights_facts(candidate, asset, roots)).run(
                target_plan, attempt, local_roots=roots, supply_run_id=final_run_id,
                bundle_id=source_bundle.bundle_id, search_terms=search_terms, skip_need_ids=skip_need_ids,
                additional_visual_need_ids=tuple(search_terms) if quality_report_sha256 else ())
        final_bundle, final_run, readiness, gaps = (
            supplied.bundle, supplied.supply_run, supplied.readiness, supplied.gaps)
    gate = MaterialGateIntegration().record(attempt, target_plan, final_bundle, final_run, readiness, gaps)
    attempt = gate["attempt"]
    record["status"] = "COMPLETE"
    record["result_bundle_revision"] = final_bundle.revision
    store.write_recovery_record(request_id, record)
    attempt = update_film_attempt(attempt_id, event="material_recovery_completed",
        material_recovery={"request_id": request_id, "status": "COMPLETE",
                           "source_plan_revision": expected_plan_revision,
                           "plan_revision": record["target_plan_revision"]})
    if readiness.status is ReadinessStatus.READY:
        attempt = ProductionAuthoringIntegration().prepare(attempt, selected_asset_ids=())["attempt"]
    return {"attempt": attempt, "material_status": gate["status"],
            "recovery": {"status": "COMPLETE", "reused": False}}
