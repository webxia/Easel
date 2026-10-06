"""Bounded migration of existing BGM evidence; never observes new media."""
from __future__ import annotations

import hashlib
import json
import re

from easel.materials.application.music_observation import (
    MODEL_REVISION, SCHEMA, assess_music, music_observed,
)


def cached_music_reassessment(attempt):
    from easel.materials.application.music_observation import POLICY_DIGEST
    from easel.materials.domain import MediaType
    from easel.materials.store import AttemptMaterialStore
    from easel.materials.application.matching import MaterialMatcher
    from easel.materials.application.readiness import MaterialReadinessCalculator
    from easel.materials.application.rights import RightsService, RightsAdmissionStatus
    from easel.materials.application.voice_delivery import voice_content_observed

    gate = attempt.get('material_gate', {})
    if not gate.get('bundle_revision') or not attempt.get('workspace', {}).get('path'):
        return None
    store = AttemptMaterialStore(attempt['workspace']['path'])
    request_id = 'music-reassessment-' + POLICY_DIGEST
    journal = store.read_recovery_record(request_id)
    if journal:
        if journal.get('policy_digest') != POLICY_DIGEST:
            raise ValueError('配乐重评策略身份不一致')
        if journal.get('status') == 'REQUESTED':
            return {'request_id': request_id, 'journal': journal}
        if (journal.get('status') == 'COMPLETE'
                and attempt.get('material_observation', {}).get('status') == 'PENDING'
                and attempt['material_observation'].get('music_reassessment_key') == request_id):
            return {'request_id': request_id, 'journal': journal}
        if journal.get('status') != 'COMPLETE':
            raise ValueError('配乐重评恢复状态无效')
        return None  # One migration batch per policy/Attempt; ordinary supply remains separate.
    from easel import creation
    if (gate.get('status') != 'MATERIAL_NOT_READY'
            or attempt.get('material_observation', {}).get('status') != 'COMPLETE'
            or creation.get_creation(attempt['creation_id']).get('delivery', {}).get('endpoint') != 'MATERIAL_READY'):
        return None
    plan, bundle = store.read_plan(), store.read_bundle()
    if (MaterialReadinessCalculator.plan_revision(plan) != gate['plan_revision']
            or bundle.revision != gate['bundle_revision'] or bundle.plan_id != plan.plan_id):
        raise ValueError('配乐重评 Plan/Bundle 身份不一致')
    assets = tuple(store.read_asset(a.asset_id) for a in bundle.assets)
    voice_ids = {r.get('asset_id') for r in store.list_generation_records() if r.get('modality') == 'voice'}
    voice_ids.update(a.asset_id for a in assets for n in plan.needs
                     if getattr(n.modality_spec, 'kind', None) == 'voice' and voice_content_observed(n, a))
    blocking = set(gate.get('blocking_needs', []))
    matcher, pairs = MaterialMatcher(), []
    for need in sorted(plan.needs, key=lambda n: n.need_id):
        if need.need_id not in blocking or getattr(need.modality_spec, 'kind', None) != 'bgm':
            continue
        candidates = [a for a in assets if a.media_type is MediaType.AUDIO and a.asset_id not in voice_ids
                      and a.technical.duration_seconds is not None and 1 <= a.technical.duration_seconds <= 300]
        candidates.sort(key=lambda a: (-matcher._soft_scores(need, a)[1], a.asset_id))
        for asset in candidates[:9]:
            if music_observed(need, asset) is not None:
                continue  # A current-policy unknown is a completed assessment, not a retry.
            if RightsService().evaluate(asset, need, attribution=RightsService.attribution_condition_for(asset)).status not in {
                    RightsAdmissionStatus.ADMITTED, RightsAdmissionStatus.CONDITIONAL}:
                continue
            identity = 'music-' + hashlib.sha256((SCHEMA + MODEL_REVISION + asset.file.sha256).encode()).hexdigest()
            locator = f'materials/observations/{identity}.json'
            lexical = store.attempt_root / locator
            if not lexical.exists() and not lexical.is_symlink():
                continue  # This migration is only for already observed bytes.
            report = read_cached_music_report(store, locator)
            assess_music(asset, report)
            pairs.append({'need_id': need.need_id, 'need_sha256': hashlib.sha256(need.to_json().encode()).hexdigest(),
                          'asset_id': asset.asset_id, 'audio_sha256': asset.file.sha256,
                          'report_locator': locator, 'raw_digest': report_digest(report)})
    return {'request_id': request_id, 'pairs': pairs[:9]} if pairs else None


def report_digest(report):
    return hashlib.sha256(json.dumps(report, sort_keys=True).encode()).hexdigest()


def read_cached_music_report(store, locator):
    if not re.fullmatch(r'materials/observations/music-[0-9a-f]{64}\.json', locator):
        raise ValueError('配乐原始观察路径无效')
    path = store.attempt_root / locator
    if any(p.is_symlink() for p in (store.attempt_root, store.materials_root, path.parent, path)):
        raise ValueError('配乐原始观察路径无效')
    path.resolve(strict=True).relative_to(store.materials_root)
    if not path.is_file() or path.stat().st_size > 2_000_000:
        raise ValueError('配乐原始观察缺失或过大；保留素材，不转为新观察')
    return json.loads(path.read_text())


def pending_music_reassessment(attempt):
    return cached_music_reassessment(attempt) is not None
