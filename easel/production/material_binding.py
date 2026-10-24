"""Recheck concrete material bindings at selection and render boundaries.

No authority is granted here. The material catalog and the frozen work plan
remain the source of truth; a different qualified candidate cannot stand in
for an invalid already-selected asset.
"""
from __future__ import annotations

import json
from .contracts import PlanDocument
from .model_tasks import ModelTaskError
from .materials import MaterialService
from easel.materials.domain import MaterialNeed, MediaType, NeedScope, NeedScopeType, NeedImportance, NeedIntent
from easel.materials.library import LibraryVisibility, UseContext


def validate_material_records(service, ctx, records):
    managed = [(r, json.loads(r['metadata_json'])) for r in records]
    managed = [(r, m) for r, m in managed if m.get('asset_ref')]
    if not managed:
        return
    with service.store.connection() as reader:
        row = reader.execute('SELECT payload_json FROM plan_revisions WHERE work_id=? AND revision=?',
                             (ctx.work_id, ctx.plan_revision)).fetchone()
    if row is None:
        raise ModelTaskError('material_binding_invalid', '素材引用缺少本次方案依据')
    plan = PlanDocument.model_validate_json(row[0])
    scope = LibraryVisibility(profile_ref=plan.profile_snapshot.profile_ref if plan.profile_snapshot else None)
    context = UseContext(work_id=ctx.work_id, constraints={'confirmed_constraints':plan.constraints,
        'aspect_ratio':plan.settings.aspect_ratio,'duration_seconds':plan.settings.duration_seconds})
    materials = MaterialService(service.outputs / '_production' / 'materials')
    for record, metadata in managed:
        try:
            current = materials.catalog.get(metadata['asset_ref'], scope=scope, context=context)
            if (current.asset.file.sha256 != record['digest'] or
                    current.asset.source.model_dump(mode='json') != metadata.get('source') or
                    current.asset.rights.model_dump(mode='json') != metadata.get('rights')):
                raise ValueError('bound material provenance changed')
            uses = materials.catalog.usage_for_asset(current.asset_ref, scope=scope, context=context)
            if not any(use.work_id == ctx.work_id and use.reference_id == record['id'] for use in uses):
                raise ValueError('bound material retention reference missing')
            needs = [MaterialNeed.model_validate_json(json.dumps(u['need']))
                     for u in metadata.get('material_uses', []) if u.get('need')]
            if not needs:
                needs = [MaterialNeed(need_id=record['id'],media_type=MediaType(record['kind']),role=metadata.get('candidate_role','visual'),
                    scope=NeedScope(type=NeedScopeType.GLOBAL,ref=ctx.work_id),importance=NeedImportance.REQUIRED,
                    intent=NeedIntent(description=plan.title))]
            for need in needs:
                result = materials.reuse.find_candidates(need,scope=scope,context=context,records=(current,))
                if not result.candidates:
                    raise ValueError('bound material no longer eligible')
            attribution = materials.resolve(current.asset_ref,visibility=scope,context=context).attribution
            expected = attribution.__dict__ if attribution else None
            if expected != metadata.get('attribution'):
                raise ValueError('bound attribution changed')
        except (OSError, ValueError, KeyError, TypeError):
            raise ModelTaskError('material_binding_invalid', '所选素材的内容、来源、使用权或引用已失效，不能用其他候选的可用状态替代') from None


def fit_sound_effects(audio, source_durations):
    """A cue is a placement window, not permission to play past a short sound."""
    result=[]
    for clip in audio:
        available=source_durations.get(clip.asset_id)
        if clip.role!='sfx' or clip.loop or available is None:
            result.append(clip);continue
        remaining=available-clip.source_start
        if remaining<=0:
            raise ModelTaskError('invalid_edit_project','音效取源起点超出实际素材')
        duration=min(clip.duration,remaining)
        scale=min(1, duration/(clip.fade_in+clip.fade_out)) if clip.fade_in+clip.fade_out else 1
        result.append(type(clip).model_validate({**clip.model_dump(),'duration':duration,
            'fade_in':clip.fade_in*scale,'fade_out':clip.fade_out*scale}))
    return result


def validate_audio_bindings(project, records):
    cues = {}
    by_id = {r['id']:json.loads(r['metadata_json']) for r in records}
    for record in records:
        metadata = by_id[record['id']]
        for use in metadata.get('material_uses', []):
            if use.get('role') != 'sfx':
                continue
            cue_id = use['cue_id']
            entry = cues.setdefault(cue_id, {'use':use,'assets':set()})
            identity = lambda v: {k:v.get(k) for k in ('cue_id','scene_id','at','duration','required')}
            if identity(entry['use']) != identity(use):
                raise ModelTaskError('sfx_binding_conflict','同一音效事件的冻结时序不一致')
            entry['assets'].add(record['id'])
    for clip in project.audio:
        meta = by_id.get(clip.asset_id, {})
        roles = {u.get('role') for u in meta.get('material_uses', []) if u.get('role') in {'music','sfx','voice'}}
        if meta.get('role') == 'voice':
            roles = {'voice'}
        if roles and clip.role not in roles:
            raise ModelTaskError('audio_role_changed','编辑器不能将已绑定的旁白、音乐或音效互相替换')
    for cue_id, entry in cues.items():
        use = entry['use']
        clips = [a for a in project.audio if a.clip_id == cue_id]
        if not clips and not use.get('required', True):
            continue
        if (len(clips) != 1 or clips[0].role != 'sfx' or clips[0].asset_id not in entry['assets']
                or clips[0].gain <= 0 or abs(clips[0].at-use['at']) > .02
                or clips[0].duration>use['duration']+.02):
            raise ModelTaskError('sfx_binding_missing','必要音效必须使用对应候选及事件ID，保留时间位置且不超过事件窗口')


def selected_asset_ids(project):
    return {s.asset_id for s in project.scenes} | {a.asset_id for a in project.audio} | {c.font_asset_id for c in project.captions}
