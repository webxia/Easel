"""Product Planning sidecar binding; standalone Material contracts stay independent."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from easel.materials.domain import MaterialNeed, MediaType
from easel.materials.application.visual_contract import (
    planning_contracts, compilation_input, read_planning_requirements, normalize_planning_requirements,
)
from easel.materials.store import AttemptMaterialStore


def requirements_bytes(root: Path) -> bytes:
    path = root / 'planning/MATERIAL_REQUIREMENTS.json'
    if (path.is_symlink() or path.parent.is_symlink() or not path.is_file()
            or path.stat().st_size > 256 * 1024):
        raise ValueError('Planning要求文件缺失、路径或容量无效')
    return path.read_bytes()


def bind_requirements(plan, mode, raw: bytes, source_needs=None, origin=None):
    visual = {n.need_id: n for n in plan.needs if n.media_type in {MediaType.IMAGE, MediaType.VIDEO}}
    sources = source_needs if source_needs is not None else {k: n.model_dump(mode='json') for k, n in visual.items()}
    if not isinstance(sources, dict) or set(sources) != set(visual):
        raise ValueError('Planning要求来源Need身份不完整')
    originals = {key: MaterialNeed.model_validate_json(json.dumps(value)) for key, value in sources.items()}
    if any(n.need_id != key for key, n in originals.items()): raise ValueError('Planning要求来源Need身份错误')
    original_plan = plan.model_copy(update={'needs': tuple(originals.get(n.need_id, n) for n in plan.needs)})
    response = read_planning_requirements(raw.decode('utf-8'))
    if origin is not None:
        if (not isinstance(origin, dict) or set(origin) != {'plan_id', 'creation_id', 'attempt_id'}
                or any(not isinstance(value, str) or not value for value in origin.values())
                or origin['creation_id'] != plan.creation_id):
            raise ValueError('Planning要求副本来源身份无效')
        # Only a frozen checkpoint copy uses a source identity. Validate its
        # wrapper there before rebinding equivalent clauses to the new Attempt.
        response = normalize_planning_requirements(original_plan.model_copy(update=origin), response)
    derived = dict(planning_contracts(original_plan, mode, response))
    # JSON persistence can reorder object keys. Validate the derived Need itself
    # first, then bind indices/cache to the actual persisted final representation.
    if {record['input']['need']['need_id']: record['input']['need'] for record in derived.values()} != {
            key: need.model_dump(mode='json') for key, need in visual.items()}:
        raise ValueError('Planning要求来源不能导出最终Need')
    records = dict(planning_contracts(plan, mode, response))
    keys = {}
    for key, record in records.items():
        # Match by the entire final input, not a transport ID or counted span.
        matches = [n.need_id for n in visual.values() if compilation_input(n, plan.context_refs, mode) == record['input']]
        if len(matches) != 1: raise ValueError('Planning要求与最终Need/Mode身份不一致')
        keys[matches[0]] = key
    if set(keys) != set(visual): raise ValueError('Planning要求未完整覆盖最终视觉Need')
    return {'path': 'planning/MATERIAL_REQUIREMENTS.json', 'sha256': hashlib.sha256(raw).hexdigest(),
            'source_needs': sources, 'cache_keys': keys, **({'origin': origin} if origin is not None else {})}, records


def verify_requirements(attempt, plan, manifest, mode):
    root = Path(attempt['workspace']['path'])
    stored = manifest.get('requirements')
    if not isinstance(stored, dict) or stored.get('path') != 'planning/MATERIAL_REQUIREMENTS.json':
        raise ValueError('Planning要求冻结记录缺失')
    raw = requirements_bytes(root)
    actual, records = bind_requirements(plan, mode, raw, stored.get('source_needs'), stored.get('origin'))
    if actual != stored: raise ValueError('Planning要求文件或身份摘要不一致')
    store = AttemptMaterialStore(root)
    # Validate every record before rebuilding any missing derived record.
    missing = []
    for key, record in records.items():
        cached = store.read_recovery_record(key)
        if cached is None: missing.append((key, record))
        elif cached != record: raise ValueError('Planning要求合同cache损坏，不能回落或覆盖')
    for key, record in missing: store.write_recovery_record(key, record)
