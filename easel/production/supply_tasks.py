"""Fenced material supply for a confirmed production plan.

The director chooses semantic adaptations. This handler only discovers qualified
candidates, preserves required inputs, and submits explicitly chosen generation
through the durable OperationService boundary.
"""
from __future__ import annotations

import asyncio
from dataclasses import replace
import json
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError

from easel.materials.application.supply import MaterialSupply, MaterialSupplyResult
from easel.materials.domain import (CandidateSource, MaterialNeed, MediaType, NeedIntent,
    NeedScope, NeedScopeType, NeedImportance, RightsInfo, RightsStatus, RightsEvidence, SemanticInfo)
from easel.materials.library import LibraryVisibility, UseContext
from easel.materials.store import MaterialFileStore, MaterialStoreError, digest_file
from .contracts import Contract, PlanDocument, canonical_json, fingerprint
from .errors import ProductionError, StaleRevision
from .materials import MaterialService
from .model_tasks import ModelTaskError
from .store import utc_now
from .providers.base import ProviderResult
from .worker import TaskResult


class GenerationChoice(Contract):
    scene_id: str = Field(min_length=1)
    kind: Literal['IMAGE', 'VIDEO']
    prompt: str = Field(min_length=1, max_length=1500)
    duration_seconds: int | None = Field(default=None, ge=1, le=15)
    resolution: str | None = None


class SupplyDecision(Contract):
    generation_requests: list[GenerationChoice] = Field(default_factory=list, max_length=100)
    unresolved_scene_ids: list[str] = Field(default_factory=list)
    explanation: str = ''


class SupplyTasks:
    def __init__(self, service, operations, *, planning=None, materials=None,
                 external_providers=(), downloaders=None, generation_providers=None,
                 generation_rights=None, config_version='production-1', source_configuration_error=None,
                 intent_compiler=None, enforce_provider_grants=False):
        self.service, self.operations, self.planning = service, operations, planning
        self.materials = materials or MaterialService(service.outputs / '_production' / 'materials')
        self.external_providers = tuple(external_providers)
        self.supplier = MaterialSupply(self.materials, providers=self.external_providers, downloaders=downloaders)
        self.generation_providers = dict(generation_providers or {})
        self.generation_rights = dict(generation_rights or {})
        self.config_version = config_version
        self.source_configuration_error = source_configuration_error
        self.intent_compiler = intent_compiler
        self.enforce_provider_grants = enforce_provider_grants
        self.board_fonts = {}

    def _board_assets(self,ctx,plan,records,scope,context,intent=None):
        if not plan.explainer_boards:return
        from .boards import render_board, VERSION
        from .media import file_sha256
        font=self.board_fonts.get(plan.settings.subtitles.font)
        if font is None:
            raise ProductionError('font_unavailable','本地图解需要本片已配置的真实字体，不擅自下载或替换字体',requires_decision=True)
        for board in plan.explainer_boards:
            for index in range(len(board.states)):
                if any(any(u.get('board_id')==board.scene_id and u.get('board_frame_index')==index
                    for u in json.loads(r['metadata_json']).get('material_uses',[])) for r in records):continue
                ctx.assert_current()
                key=fingerprint([VERSION,board.model_dump(mode='json'),index,file_sha256(font),plan.settings.aspect_ratio])
                folder=self.service.outputs/'_production'/'boards'/ctx.task_id
                path=render_board(board,index,font_path=font,aspect_ratio=plan.settings.aspect_ratio,destination=folder/(key+'.png'))
                rights=RightsInfo(status=RightsStatus.KNOWN,license_name='Work-authored schematic; no external imagery',
                    evidence=(RightsEvidence(kind='asset_authorship_record',reference='work:'+ctx.work_id+':plan:'+str(ctx.plan_revision)+':'+key,
                        summary='Local deterministic layout of frozen schematic text; text provenance retained in confirmed plan; no external imagery'),))
                handle=self.materials.ingest_input(source_root=folder,relative_path=path.name,visibility=scope,context=context,
                    media_type=MediaType.IMAGE,source=CandidateSource(kind='authored_graphic',provider=VERSION,provider_asset_id=key),
                    rights=rights,semantic=SemanticInfo(caption=board.title+' / '+board.states[index].title,
                        attributes={'schematic':True,'kind':board.kind,'board_frame_index':index}))
                need=self._need(board.scene_id,board.title,'image',context=context)
                scene_ids=([v.scene_id for v in intent.visuals if v.board_id==board.scene_id and index in v.board_state_indexes]
                    if intent is not None else [board.scene_id])
                records.append(self._register(ctx,handle,scope=scope,context=context,scene_ids=scene_ids,
                    material_use={'need_id':need.need_id,'role':'visual','scene_id':board.scene_id,'need':need.model_dump(mode='json'),
                        'board_id':board.scene_id,'board_frame_index':index,'board_scene_ids':scene_ids,'required':True}))

    def _allowed_providers(self, kind, ctx=None):
        providers = [p for p in self.external_providers
                     if MediaType(kind) in getattr(p, 'media_types', frozenset(MediaType))]
        if not self.enforce_provider_grants:
            return tuple(p.provider_id for p in providers)
        if ctx is None:
            return ()
        ctx.assert_current()
        with ctx.store.connection() as reader:
            grants = reader.execute("SELECT services_json FROM authorization_grants WHERE work_id=? AND purpose='production' AND plan_revision=? AND revoked_at IS NULL", (ctx.work_id, ctx.plan_revision)).fetchall()
        allowed = [identity for grant in grants for identity in json.loads(grant[0])]
        return tuple(p.provider_id for p in providers if
            {'provider': p.provider_id, 'model': 'stock', 'mode': 'search'} in allowed)

    def _check_provider(self, ctx, kind, provider_id):
        ctx.assert_current()
        if self.enforce_provider_grants and provider_id not in self._allowed_providers(kind,ctx):
            raise ProductionError('permission_missing','本次素材来源授权已撤销，未发送后续检索或下载',requires_decision=True)

    @staticmethod
    def _need(scene_id, visual, kind, *, context=None, options=1):
        return MaterialNeed(need_id=scene_id + ':' + kind, media_type=MediaType(kind), role='visual' if kind != 'audio' else 'audio',
            scope=NeedScope(type=NeedScopeType.SCENE, ref=scene_id), importance=NeedImportance.REQUIRED,
            intent=NeedIntent(description=visual), desired_options=options,
            constraints=dict(context.constraints) if context is not None else {})

    @staticmethod
    def _blocked(code, message, *, ids=(), operation_id=None, result=None):
        return TaskResult(state='needs_decision', work_state='needs_decision', result=result or {},
            error=ProductionError(code, message, affected_ids=list(ids), operation_id=operation_id, requires_decision=True))

    def _snapshot(self, ctx):
        ctx.assert_current()
        with ctx.store.connection() as conn:
            work = dict(conn.execute('SELECT * FROM works WHERE id=?', (ctx.work_id,)).fetchone())
            plan = conn.execute('SELECT * FROM plan_revisions WHERE work_id=? AND revision=?', (ctx.work_id, ctx.plan_revision)).fetchone()
            if not plan or not plan['confirmed_at']:
                raise ProductionError('plan_unconfirmed', '先确认本次完整创作方案', requires_decision=True)
            from .expression_policy import validate
            validate((json.loads(plan['payload_json']).get('conversation_basis') or {}).get('expression_policy'))
            inputs = [dict(r) for r in conn.execute('SELECT * FROM work_inputs WHERE work_id=?', (ctx.work_id,))]
            records = [dict(r) for r in conn.execute("SELECT * FROM artifacts WHERE work_id=? AND deleted_at IS NULL AND json_extract(metadata_json,'$.supply_task_id')=? ORDER BY created_at,id", (ctx.work_id, ctx.task_id))]
        for record in records:
            path = MaterialFileStore(self.service.outputs).resolve_asset_locator(record['storage_ref'])
            if digest_file(path) != record['digest']:
                raise ProductionError('material_changed', '本次已登记素材发生变化，请核实后继续', affected_ids=[record['id']], requires_decision=True)
        from .material_binding import validate_material_records
        validate_material_records(self.service,ctx,records)
        return work, PlanDocument.model_validate_json(plan['payload_json']), inputs, records

    def _register(self, ctx, handle, *, scope, context, scene_ids, input_id=None, operation_id=None, candidate_role=None, material_use=None):
        """Keep a durable library reference before copying and fenced DB registration.

        Cross-database failure may leave a conservative retained reference; it
        cannot release bytes that an in-flight operation might still consume.
        """
        identity = fingerprint([ctx.work_id, ctx.task_id, handle.asset_ref, input_id, operation_id])
        artifact_id = 'material_' + identity[:32]
        self.materials.catalog.record_usage(handle.asset_ref, scope=scope, context=context,
            reference_id=artifact_id, need_ids=tuple(sorted(set(scene_ids) | ({material_use['need_id']} if material_use else set()))),
            attribution=handle.attribution.__dict__ if handle.attribution else None)
        suffix = {'image/png': '.png', 'image/jpeg': '.jpg', 'image/webp': '.webp',
                  'video/mp4': '.mp4', 'audio/mpeg': '.mp3', 'audio/wav': '.wav',
                  'audio/ogg': '.ogg', 'audio/flac': '.flac'}.get(handle.asset.file.mime, handle.local_path.suffix)
        locator = f'works/{ctx.work_id}/assets/{handle.digest}{suffix}'
        MaterialFileStore(self.service.outputs).stage_object(handle.local_path, locator, handle.digest, handle.asset.file.size)
        metadata = {'schema_version': 1, **handle.artifact_metadata(), 'supply_task_id': ctx.task_id,
                    'scene_ids': list(scene_ids), 'input_id': input_id, 'candidate_only': input_id is None,
                    'material_scope': scope.model_dump(mode='json'), 'use_constraints': context.constraints,
            'material_uses': [material_use] if material_use else []}
        if candidate_role:
            # A requested use, not a claim that the director has heard or chosen it.
            metadata['candidate_role'] = candidate_role
        if material_use and material_use.get('board_id'):
            metadata['candidate_only']=False
        with ctx.transaction() as conn:
            staged=MaterialFileStore(self.service.outputs).resolve_asset_locator(locator)
            if digest_file(staged)!=handle.digest:
                raise MaterialStoreError('Material changed before artifact registration')
            previous = conn.execute('SELECT * FROM artifacts WHERE id=?', (artifact_id,)).fetchone()
            if previous:
                old = json.loads(previous['metadata_json'])
                metadata['scene_ids'] = sorted(set(old.get('scene_ids', [])) | set(scene_ids))
                uses = old.get('material_uses', [])
                if material_use and material_use not in uses:
                    uses = [*uses, material_use]
                metadata['material_uses'] = uses
                # Keep the old scalar for older consumers; a multi-use object
                # no longer loses its music binding when also used as SFX.
                if old.get('candidate_role'):
                    metadata['candidate_role'] = old['candidate_role']
                conn.execute('UPDATE artifacts SET metadata_json=? WHERE id=?', (canonical_json(metadata), artifact_id))
            else:
                conn.execute('''INSERT INTO artifacts(id,work_id,run_id,operation_id,kind,storage_ref,digest,size_bytes,media_type,displayable,metadata_json,created_at)
                    VALUES(?,?,?,?,?,?,?,?,?,1,?,?)''', (artifact_id,ctx.work_id,ctx.run_id,operation_id,handle.asset.media_type.value,
                    locator,handle.digest,handle.asset.file.size,handle.asset.file.mime,canonical_json(metadata),utc_now()))
                ctx.store.append_event(conn,ctx.work_id,'material_ready',{'artifact_id':artifact_id,'kind':handle.asset.media_type.value,'input_id':input_id},run_id=ctx.run_id)
            # Material assets are leaves. Edit/output handlers add edges to these
            # exact IDs; a source input is not an artifact ID and cannot be forged
            # into an artifact edge.
            return dict(conn.execute('SELECT * FROM artifacts WHERE id=?', (artifact_id,)).fetchone())

    def _acquire(self, ctx, plan, inputs, records, scope, context, intent=None, *, excluded_asset_refs=()):
        # A frozen explanation belongs to its own scene, not generic stock for
        # another scene that happens to share a keyword.
        board_refs=[json.loads(r['metadata_json']).get('asset_ref') for r in records
            if any(u.get('board_id') for u in json.loads(r['metadata_json']).get('material_uses',[]))]
        excluded_asset_refs=tuple(dict.fromkeys([*excluded_asset_refs,*[ref for ref in board_refs if ref]]))
        scenes = {s.id: s for s in plan.scenes}
        mapped = {json.loads(r['metadata_json']).get('input_id'): r for r in records}
        for item in inputs:
            if item['usage'] != 'must_use' or item['kind'] not in {'image','video','audio'}:
                continue
            if item['id'] in mapped:
                continue
            metadata = json.loads(item['metadata_json'])
            rights_value = metadata.get('source', {}).get('rights') or {'status':'UNKNOWN'}
            rights = RightsInfo.model_validate_json(canonical_json(rights_value))
            scene_ids = [s.id for s in plan.scenes if item['id'] in s.required_input_ids]
            if not scene_ids:
                raise ProductionError('required_input_unmapped','已确认方案未说明必用素材对应的场景',affected_ids=[item['id']],requires_decision=True)
            handle = self.materials.ingest_input(source_root=self.service.outputs, relative_path=item['source_ref'],
                visibility=scope, context=context, media_type=MediaType(item['kind']),
                source=CandidateSource(kind='user_upload', provider_asset_id=item['id']),rights=rights,
                semantic=SemanticInfo(caption=item['original_name'] or None),expected_sha256=item['digest'])
            need = self._need(scene_ids[0],scenes[scene_ids[0]].visual,item['kind'],context=context)
            found = self.materials.reuse.find_candidates(need,scope=scope,context=context,
                records=(self.materials.catalog.get(handle.asset_ref,scope=scope,context=context),))
            if not found.candidates:
                raise ProductionError('required_material_unavailable','必用素材的文件、技术检查或使用权未满足；请补充依据，不会自动替换',affected_ids=[item['id']],requires_decision=True)
            records.append(self._register(ctx,handle,scope=scope,context=context,scene_ids=scene_ids,input_id=item['id']))
        gaps = []
        with ctx.store.connection() as conn:
            saved=json.loads(conn.execute('SELECT payload_json FROM tasks WHERE id=?',(ctx.task_id,)).fetchone()[0])
        planned_generation={c['scene_id'] for c in saved.get('supply_decision',{}).get('generation_requests',[])}
        for scene in plan.scenes:
            # These are qualified choices, not a claim that a model has accepted
            # their semantic fitness. edit receives candidates and decides use.
            present = [r for r in records if r['kind'] in {'image','video'} and scene.id in json.loads(r['metadata_json']).get('scene_ids',[])]
            if present:
                continue
            if scene.id in planned_generation:
                gaps.append(scene.id)
                continue
            visual = next((v for v in intent.visuals if v.scene_id == scene.id), None) if intent else None
            for kind in (visual.media_types if visual else ('image','video')):
                ctx.assert_current()
                need = self._need(scene.id,visual.query if visual else scene.visual,kind,
                                  context=context,options=visual.options if visual else 1)
                if plan.narration_policy is not None:
                    need = need.model_copy(update={'constraints': {**need.constraints, 'min_short_edge': 1080}})
                answer = self.supplier.supply(need,visibility=scope,context=context,
                    excluded_asset_refs=excluded_asset_refs,
                    allowed_providers=tuple(p for p in self._allowed_providers(kind,ctx)
                        if not need.intent.description.strip().lower().startswith(('https://','http://')) or p=='pexels'),check_current=ctx.assert_current,
                    check_provider=lambda provider_id:self._check_provider(ctx,kind,provider_id))
                with ctx.transaction() as conn:
                    ctx.store.append_event(conn,ctx.work_id,'material_search_completed',
                        {'scene_id':scene.id,'kind':kind,'candidate_count':len(answer.candidates),
                         'sources':list(answer.attempted_sources),'failures':[{'source':f.source,'code':f.reason} for f in answer.failures]},run_id=ctx.run_id)
                for candidate in answer.candidates:
                    handle = self.materials.resolve(candidate.library_asset_id,visibility=scope,context=context)
                    record = self._register(ctx,handle,scope=scope,context=context,scene_ids=[scene.id],
                        material_use={'need_id':need.need_id,'role':'visual','scene_id':scene.id,'need':need.model_dump(mode='json')})
                    if not any(r['id']==record['id'] for r in records):records.append(record)
                    else:records[:] = [record if r['id']==record['id'] else r for r in records]
                if answer.candidates and plan.narration_policy is not None:
                    # media_types are alternatives, not a requirement to fill
                    # every type even after the preferred footage is supplied.
                    break
            if not any(r['kind'] in {'image','video'} and scene.id in json.loads(r['metadata_json']).get('scene_ids',[]) for r in records):
                gaps.append(scene.id)
        return records,gaps

    def _acquire_music(self, ctx, plan, records, scope, context, intent=None):
        if plan.settings.audio_mode not in {'music', 'mixed'}:
            return
        if any(r['kind'] == 'audio' and json.loads(r['metadata_json']).get('candidate_role') == 'music' for r in records):
            return
        need = MaterialNeed(need_id='work-music', media_type=MediaType.AUDIO, role='music',
            scope=NeedScope(type=NeedScopeType.GLOBAL, ref=ctx.work_id), importance=NeedImportance.REQUIRED,
            intent=NeedIntent(description='为已确认作品选择背景音乐候选：' + plan.title + '。' + plan.summary +
                              '。已确认约束：' + canonical_json(plan.constraints), function='background_music'))
        if intent and intent.music_query:
            need = need.model_copy(update={'intent':NeedIntent(description=intent.music_query,function='background_music'),
                                          'constraints':dict(context.constraints)})
        allowed = self._allowed_providers('audio',ctx)
        # Metadata search cannot establish that a track fits a mood or that
        # speech is music. Offer bounded qualified library audio to the director;
        # only actual listening/edit judgement can accept its intended use.
        prior = self.materials.candidates(need, visibility=scope, context=context, limit=8)
        answer = (MaterialSupplyResult(prior.candidates[:8], (), (), ()) if prior.candidates else
                  self.supplier.supply(need, visibility=scope, context=context,
                                       allowed_providers=allowed, check_current=ctx.assert_current,
                                       check_provider=lambda provider_id:self._check_provider(ctx,'audio',provider_id)))
        with ctx.transaction() as conn:
            ctx.store.append_event(conn, ctx.work_id, 'material_search_completed',
                {'kind': 'audio', 'role': 'music', 'candidate_count': len(answer.candidates),
                 'sources': list(answer.attempted_sources),
                 'failures': [{'source': f.source, 'code': f.reason} for f in answer.failures]}, run_id=ctx.run_id)
        for candidate in answer.candidates:
            handle = self.materials.resolve(candidate.library_asset_id, visibility=scope, context=context)
            record = self._register(ctx, handle, scope=scope, context=context,
                                    scene_ids=[s.id for s in plan.scenes], candidate_role='music',
                                    material_use={'need_id':need.need_id,'role':'music','need':need.model_dump(mode='json')})
            if not any(r['id'] == record['id'] for r in records):
                records.append(record)
        if not answer.candidates:
            if not allowed:
                raise ProductionError('capability_unavailable',
                    '本方案需要音乐，库内尚无合格音频，且未配置有使用权依据的外部音频来源；请提供音乐或配置已审查公开来源，不会改成静音或生成 AI 音乐', requires_decision=True)
            raise ProductionError('music_material_gap',
                '已尝试音乐素材库和已审查公开来源，但未取得可供导演选择的合格音频；请补充素材或使用权依据，保留已取得成果', requires_decision=True)

    def _acquire_sfx(self, ctx, plan, records, scope, context, intent):
        for cue in intent.sound_cues:
            if any(use.get('cue_id') == cue.cue_id for record in records
                   for use in json.loads(record['metadata_json']).get('material_uses', [])):
                continue
            need = MaterialNeed(need_id='sfx:'+cue.cue_id,media_type=MediaType.AUDIO,role='sfx',
                scope=NeedScope(type=NeedScopeType.EVENT,ref=cue.cue_id),
                importance=NeedImportance.REQUIRED if cue.required else NeedImportance.OPTIONAL,
                intent=NeedIntent(description=cue.query,function=cue.basis),constraints=dict(context.constraints))
            answer = self.supplier.supply(need,visibility=scope,context=context,
                allowed_providers=self._allowed_providers('audio',ctx),check_current=ctx.assert_current,
                check_provider=lambda provider_id:self._check_provider(ctx,'audio',provider_id))
            use={'need_id':need.need_id,'role':'sfx','cue_id':cue.cue_id,'scene_id':cue.scene_id,
                 'at':cue.at,'duration':cue.duration,'required':cue.required,'basis':cue.basis,
                 'need':need.model_dump(mode='json')}
            for candidate in answer.candidates:
                handle=self.materials.resolve(candidate.library_asset_id,visibility=scope,context=context)
                record=self._register(ctx,handle,scope=scope,context=context,scene_ids=[cue.scene_id],
                                      candidate_role='sfx',material_use=use)
                if any(r['id']==record['id'] for r in records):
                    records[:]=[record if r['id']==record['id'] else r for r in records]
                else:records.append(record)
            with ctx.transaction() as writer:
                ctx.store.append_event(writer,ctx.work_id,'material_search_completed',
                    {'kind':'audio','role':'sfx','cue_id':cue.cue_id,'candidate_count':len(answer.candidates),
                     'sources':list(answer.attempted_sources),'required':cue.required},run_id=ctx.run_id)
            if not answer.candidates and cue.required:
                raise ProductionError('sfx_material_gap','已确认所需音效缺少合法素材，保留已有成果，不会静默省略',
                                      affected_ids=[cue.cue_id],requires_decision=True)

    def _grant(self, ctx, adapter):
        identity = {'provider':adapter.provider_id,'model':adapter.model,'mode':adapter.mode}
        with ctx.store.connection() as conn:
            grants = conn.execute("SELECT * FROM authorization_grants WHERE work_id=? AND purpose='production' AND plan_revision=? AND revoked_at IS NULL AND allow_ai=1 ORDER BY created_at DESC",(ctx.work_id,ctx.plan_revision)).fetchall()
        for grant in grants:
            if identity in json.loads(grant['services_json']):return grant['id']
        raise ProductionError('permission_missing','本次方案尚未授权此生成服务、模型和模式',requires_decision=True)

    async def _decision(self, ctx, plan, records, gaps):
        with ctx.store.connection() as conn:
            payload=json.loads(conn.execute('SELECT payload_json FROM tasks WHERE id=?',(ctx.task_id,)).fetchone()[0])
        cached = payload.get('supply_decision',ctx.payload.get('supply_decision'))
        if cached is not None:return SupplyDecision.model_validate(cached)
        if ctx.payload.get('generation_requests') is not None:
            answer = SupplyDecision(generation_requests=ctx.payload['generation_requests'])
        elif self.planning is not None and gaps:
            if not (self._allowed_providers('image',ctx) or self._allowed_providers('video',ctx)):
                raise ProductionError('capability_unavailable','库内素材不足，外部图库或公开来源尚未配置；请先配置外部来源，或明确选择本次 AI 生成',affected_ids=gaps,requires_decision=True)
            capabilities=[]
            for kind,adapter in self.generation_providers.items():
                if not getattr(adapter,'available',True):continue
                try:self._grant(ctx,adapter)
                except ProductionError:continue
                rights=self.generation_rights.get(kind)
                if rights and rights.status in {RightsStatus.KNOWN,RightsStatus.PUBLIC_DOMAIN} and rights.evidence and (rights.status is not RightsStatus.KNOWN or rights.license_name):
                    capability={'kind':kind,'model':adapter.model,'mode':adapter.mode}
                    if kind=='VIDEO' and adapter.model in {'MiniMax-H3','MiniMax-H3-Max'}:
                        capability.update(duration_range=[4 if adapter.model=='MiniMax-H3' else 5,15],
                            resolutions=['768P','2K'] if adapter.model=='MiniMax-H3' else ['480P','768P'])
                    capabilities.append(capability)
            if not capabilities:
                raise ProductionError('material_gap','外部与库内素材不足，且尚无本次获授权且使用权明确的 AI 补料服务',affected_ids=gaps,requires_decision=True)
            context=self.planning.context(ctx)
            context=replace(context,artifacts=tuple({'asset_id':r['id'],'kind':r['kind'],'metadata':json.loads(r['metadata_json'])} for r in records),
                allowed_handles=context.allowed_handles|frozenset(r['id'] for r in records))
            answer=await self.planning.runner(ctx).run(context,
                '已先尝试素材库与外部来源。仅针对这些缺口场景提出 AI 补料创作请求：'+canonical_json(gaps)+
                '。可用生成能力：'+canonical_json(capabilities)+'。不得改写已确认事实、观点、必用素材或风格；需要实质变更的场景放入 unresolved_scene_ids。VIDEO 必须明确时长与分辨率，IMAGE 不设置视频参数。',SupplyDecision, expression_role="visual")
        else:
            answer=SupplyDecision(unresolved_scene_ids=gaps)
        # Persist semantic intent before any media generation. Restarts reuse it.
        with ctx.transaction() as conn:
            payload=json.loads(conn.execute('SELECT payload_json FROM tasks WHERE id=?',(ctx.task_id,)).fetchone()[0])
            payload['supply_decision']=answer.model_dump(mode='json')
            conn.execute('UPDATE tasks SET payload_json=?,updated_at=? WHERE id=?',(canonical_json(payload),utc_now(),ctx.task_id))
        return answer

    def _generate(self,ctx,plan,choice,scope,context,records):
        if choice.scene_id not in {s.id for s in plan.scenes}:
            raise ProductionError('invalid_generation_request','补料引用了本方案以外的场景',requires_decision=True)
        adapter=self.generation_providers.get(choice.kind)
        if adapter is None or not getattr(adapter,'available',True):
            raise ProductionError('capability_unavailable','所选生成模态尚未配置可用服务',requires_decision=True)
        rights=self.generation_rights.get(choice.kind)
        if rights is None or rights.status not in {RightsStatus.KNOWN,RightsStatus.PUBLIC_DOMAIN} or not rights.evidence or (rights.status is RightsStatus.KNOWN and not rights.license_name):
            raise ProductionError('rights_evidence_missing','生成素材使用许可依据未登记或无效；这不是 API Key 或套餐额度错误，请先核实适用条款与用途',requires_decision=True)
        operation_id='supply_'+fingerprint([ctx.task_id,choice.model_dump(mode='json')])[:32]
        existing=next((r for r in records if r['operation_id']==operation_id),None)
        if existing:return existing,None
        request={'prompt':choice.prompt,'aspect_ratio':plan.settings.aspect_ratio}
        if choice.kind=='VIDEO':request.update(duration_seconds=choice.duration_seconds,resolution=choice.resolution)
        elif choice.duration_seconds is not None or choice.resolution is not None:
            raise ProductionError('invalid_generation_request','生图请求不能包含生视频参数',requires_decision=True)
        try:operation=self.operations.get(operation_id)
        except ProductionError as exc:
            if exc.code!='not_found':raise
            operation=self.operations.reserve(operation_id=operation_id,work_id=ctx.work_id,run_id=ctx.run_id,task_id=ctx.task_id,
                grant_id=self._grant(ctx,adapter),kind=choice.kind,provider=adapter.provider_id,model=adapter.model,mode=adapter.mode,
                config_version=self.config_version,request=request,owner_epoch=ctx.owner_epoch)
        ctx.assert_current()
        if operation['state']=='reserved':operation=self.operations.submit(operation_id,adapter,owner_epoch=ctx.owner_epoch)
        elif operation['state'] in {'sending','submitted','unknown'}:operation=self.operations.observe(operation_id,adapter)
        if operation['state'] in {'sending','submitted'}:
            return None,TaskResult(state='waiting_external',result={'operation_ids':[operation_id]})
        if operation['state']=='unknown':
            return None,self._blocked('result_unknown','生成结果尚无法核实；已保留此次调用，不会重新提交',operation_id=operation_id)
        if operation['state']!='succeeded':
            return None,self._blocked('generation_failed','本次生成未成功；已有回执和计次已保留',operation_id=operation_id)
        result=operation['receipt']['result']
        evidence=RightsEvidence(kind='asset_generation_receipt',reference='operation:'+operation_id)
        asset_rights=rights.model_copy(update={'evidence':(*rights.evidence,evidence)})
        source=CandidateSource(kind='generated',provider=adapter.provider_id,provider_asset_id=operation.get('provider_task_id') or operation_id)
        if choice.kind=='IMAGE':
            # The trusted adapter's private receipt path is never sent to the UI.
            path=Path(result['local_path'])
            handle=self.materials.ingest_input(source_root=path.parent,relative_path=path.name,visibility=scope,context=context,
                media_type=MediaType.IMAGE,source=source,rights=asset_rights,expected_sha256=result['sha256'])
        else:
            downloaded=adapter.download(ProviderResult('succeeded',task_id=operation.get('provider_task_id'),result=result))
            handle=self.materials.ingest_downloaded(downloaded,visibility=scope,context=context,media_type=MediaType.VIDEO,source=source,rights=asset_rights)
        need=self._need(choice.scene_id,choice.prompt,choice.kind.lower())
        checked=self.materials.reuse.find_candidates(need,scope=scope,context=context,records=(self.materials.catalog.get(handle.asset_ref,scope=scope,context=context),))
        if not checked.candidates:
            raise ProductionError('generated_material_unavailable','生成回执已保留，但素材技术检查或使用权尚不满足',requires_decision=True,operation_id=operation_id)
        return self._register(ctx,handle,scope=scope,context=context,scene_ids=[choice.scene_id],operation_id=operation_id),None

    async def supply(self,ctx):
        try:
            work,plan,inputs,records=await asyncio.to_thread(self._snapshot,ctx)
            if self.source_configuration_error:
                return self._blocked('source_configuration_invalid', self.source_configuration_error)
            scope=LibraryVisibility(profile_ref=plan.profile_snapshot.profile_ref if plan.profile_snapshot else None)
            intent, creative = (await self.intent_compiler.prepare(ctx,plan)) if self.intent_compiler else (None,None)
            context=UseContext(work_id=ctx.work_id,constraints={
                'plan_hash':fingerprint(plan), 'confirmed_constraints':plan.constraints,
                'aspect_ratio':plan.settings.aspect_ratio, 'duration_seconds':plan.settings.duration_seconds,
                **({'director':creative.director,'creator_context_hash':creative.fingerprint} if creative else {})})
            await asyncio.to_thread(self._board_assets,ctx,plan,records,scope,context,intent)
            records,gaps=await asyncio.to_thread(self._acquire,ctx,plan,inputs,records,scope,context,intent)
            await asyncio.to_thread(self._acquire_music,ctx,plan,records,scope,context,intent)
            if intent:
                await asyncio.to_thread(self._acquire_sfx,ctx,plan,records,scope,context,intent)
            decision=await self._decision(ctx,plan,records,gaps)
            if set(decision.unresolved_scene_ids) & set(gaps):
                return self._blocked('material_gap','场景素材仍有缺口或需要修改已确认方案，请明确本次调整',ids=decision.unresolved_scene_ids)
            for choice in decision.generation_requests:
                record,pending=await asyncio.to_thread(self._generate,ctx,plan,choice,scope,context,records)
                if pending:return pending
                if not any(r['id']==record['id'] for r in records):records.append(record)
            missing=[s.id for s in plan.scenes if not any(r['kind'] in {'image','video'} and s.id in json.loads(r['metadata_json']).get('scene_ids',[]) for r in records)]
            if missing:return self._blocked('material_gap','缺少可供导演选择的合格场景素材',ids=missing)
            ids=list(dict.fromkeys(r['id'] for r in records))
            return TaskResult(result={'asset_ids':ids},next_kind='edit',next_payload={'schema_version':1,'asset_ids':ids})
        except StaleRevision:
            raise
        except ProductionError as exc:
            return TaskResult(state='needs_decision',work_state='needs_decision',error=exc)
        except ModelTaskError as exc:
            return self._blocked(exc.code,exc.user_message)
        except (MaterialStoreError,ValidationError,ValueError,OSError,KeyError):
            return self._blocked('material_invalid','素材文件、来源或使用权记录无效，请核实后继续')

    def revision_visuals(self,ctx,searches):
        """Use existing fenced stock acquisition for specified revision scenes only.

        No intent recompilation, generation decision, voice preparation or new
        Plan. Persist each search result so resume cannot redo a completed one.
        """
        from .material_intent import VisualIntent, MaterialIntent
        _,plan,_,records=self._snapshot(ctx)
        if self.source_configuration_error:
            raise ProductionError('source_configuration_invalid',self.source_configuration_error,requires_decision=True)
        searches=[VisualIntent.model_validate(s) for s in searches]
        ids=[s.scene_id for s in searches]
        if len(ids)>4 or len(ids)!=len(set(ids)) or not set(ids)<={s.id for s in plan.scenes}:
            raise ModelTaskError('invalid_revision_search','局部补料只能引用本方案不重复的场景，单次最多4场')
        scope=LibraryVisibility(profile_ref=plan.profile_snapshot.profile_ref if plan.profile_snapshot else None)
        context=UseContext(work_id=ctx.work_id,constraints={'plan_hash':fingerprint(plan),
            'confirmed_constraints':plan.constraints,'aspect_ratio':plan.settings.aspect_ratio,
            'duration_seconds':plan.settings.duration_seconds})
        for search in searches:
            ctx.assert_current()
            key=fingerprint(search)
            with ctx.store.connection() as conn:
                payload=json.loads(conn.execute('SELECT payload_json FROM tasks WHERE id=?',(ctx.task_id,)).fetchone()[0])
            if key in payload.get('revision_search_results',{}):continue
            with ctx.store.connection() as conn:
                excluded=tuple(json.loads(row['metadata_json']).get('asset_ref') for row in
                    conn.execute('SELECT id,metadata_json FROM artifacts WHERE work_id=?',(ctx.work_id,))
                    if row['id'] in payload.get('revision_asset_ids',payload.get('asset_ids',[])) and json.loads(row['metadata_json']).get('asset_ref'))
            # Existing candidates were actually observed and found unsuitable
            # before the director requests this bounded replacement search.
            scene_plan=plan.model_copy(update={'scenes':[s for s in plan.scenes if s.id==search.scene_id]})
            current=[r for r in records if search.scene_id in json.loads(r['metadata_json']).get('scene_ids',[])]
            acquired,gaps=self._acquire(ctx,scene_plan,[],current,scope,context,MaterialIntent(visuals=[search]),excluded_asset_refs=excluded)
            records.extend(r for r in acquired if r['id'] not in {v['id'] for v in records})
            with ctx.transaction() as conn:
                payload=json.loads(conn.execute('SELECT payload_json FROM tasks WHERE id=?',(ctx.task_id,)).fetchone()[0])
                payload.setdefault('revision_search_results',{})[key]={'scene_id':search.scene_id,
                    'asset_ids':[r['id'] for r in acquired],'gap':bool(gaps)}
                conn.execute('UPDATE tasks SET payload_json=? WHERE id=?',(canonical_json(payload),ctx.task_id))
        return [r['id'] for r in records]


def _configured_rights(settings):
    """Explicit operator-supplied license evidence; never a credential default.

    EASEL_GENERATION_RIGHTS_JSON is JSON, or an absolute local JSON file path.
    It contains schema_version=1 and IMAGE/VIDEO RightsInfo objects. The actual
    asset receipt evidence is appended only after successful generation.
    """
    raw=settings.get('EASEL_GENERATION_RIGHTS_JSON','').strip()
    if not raw:return {}
    try:
        if not raw.startswith('{'):
            path=Path(raw)
            if not path.is_absolute() or path.is_symlink() or path.stat().st_size>256*1024:return {}
            raw=path.read_text(encoding='utf-8')
        if len(raw)>256*1024:return {}
        value=json.loads(raw)
        if value.get('schema_version')!=1 or set(value)-{'schema_version','IMAGE','VIDEO'}:return {}
        return {kind:RightsInfo.model_validate_json(canonical_json(value[kind])) for kind in ('IMAGE','VIDEO') if kind in value}
    except (OSError,ValueError,TypeError,ValidationError):return {}


def supply_capabilities(settings):
    """Public identities and readiness only, without keys or license documents."""
    rights=_configured_rights(settings)
    key=bool(settings.get('MINIMAX_API_KEY','').strip())
    image_model=settings.get('EASEL_IMAGE_MODEL','image-01').strip()
    video_model=settings.get('EASEL_VIDEO_MODEL','').strip()
    result=[]
    for kind,model,valid in [('IMAGE',image_model,image_model=='image-01'),('VIDEO',video_model,video_model in {'MiniMax-H3','MiniMax-H3-Max'})]:
        evidence=rights.get(kind)
        licensed=bool(evidence and evidence.status in {RightsStatus.KNOWN,RightsStatus.PUBLIC_DOMAIN} and evidence.evidence and
                      (evidence.status is not RightsStatus.KNOWN or evidence.license_name))
        reason=None if key and valid and licensed else 'capability_unavailable' if not key or not valid else 'rights_evidence_missing'
        message=('生成素材使用许可依据未登记或无效；不是 API Key 或套餐额度错误' if reason=='rights_evidence_missing' else
                 '缺少 API Key 或尚未配置支持的模型' if reason else None)
        result.append({'provider':'minimax','model':model,'mode':'text_to_image' if kind=='IMAGE' else 'text_to_video',
            'kind':kind,'label':('生图' if kind=='IMAGE' else '生视频')+' · '+(model or '未配置模型'),
            'available':bool(key and valid and licensed),
            'reason':reason,'reason_message':message,
            'readiness_note':'本地配置就绪；账户调用资格及额度未经本次远端验证，使用仍需本作品授权' if not reason else None,
            'usage_constraints':list(evidence.usage_constraints) if licensed else []})
    return result


def configured_supply(service,operations,planning,settings):
    """Compose genuine adapters without making a request or granting consent."""
    from .providers.stock import PexelsStockProvider, ReviewedPublicSources
    from .providers.pixabay import PixabayStockProvider
    from .providers.wikimedia_audio import WikimediaAudioProvider
    from .material_intent import FrozenIntentCompiler
    from .providers.generation_http import MiniMaxImageProvider, MiniMaxVideoProvider
    providers=[]
    proxy_url=settings.get('EASEL_MATERIAL_HTTP_PROXY','').strip() or None
    if settings.get('PEXELS_API_KEY','').strip():providers.append(PexelsStockProvider(settings['PEXELS_API_KEY'],proxy_url=proxy_url))
    if settings.get('PIXABAY_API_KEY','').strip():
        providers.append(PixabayStockProvider(settings['PIXABAY_API_KEY'],proxy_url=proxy_url,
            cache_root=service.outputs/'_production'/'provider_cache'/'pixabay'))
    # Read-only Commons public metadata requires no account. Enabled only by
    # an explicit config flag; each actual production query additionally needs
    # the existing per-work stock/search grant.
    if settings.get('EASEL_WIKIMEDIA_AUDIO_ENABLED', '0').strip() == '1':
        providers.extend((WikimediaAudioProvider('music',proxy_url=proxy_url), WikimediaAudioProvider('sfx',proxy_url=proxy_url)))
    source_error=None
    raw=settings.get('EASEL_REVIEWED_PUBLIC_SOURCES_JSON','').strip()
    if raw:
        try:
            if not raw.startswith('{'):
                path=Path(raw)
                if not path.is_absolute() or any(p.is_symlink() for p in (path,*path.parents)) or path.stat().st_size>256*1024:
                    raise ValueError('Invalid reviewed source configuration path')
                raw=path.read_text(encoding='utf-8')
            if len(raw.encode('utf-8'))>256*1024:
                raise ValueError('Reviewed source configuration exceeds limit')
            providers.append(ReviewedPublicSources.from_json(raw))
        except (OSError,ValueError,TypeError,ValidationError):
            source_error='已审查公开来源配置无效：请核对明确域名、素材来源、许可及资产专属证据；未发送下载请求'
    downloaders = None
    proxy_url = settings.get('EASEL_MATERIAL_HTTP_PROXY', '').strip()
    if proxy_url:
        from easel.materials.application.proxy import PublicDNSOverProxy, ProxyPinnedHttpsTransport
        from easel.materials.application.acquisition import MediaDownloader, RemoteURLPolicy
        resolver=PublicDNSOverProxy(proxy_url)
        transport=ProxyPinnedHttpsTransport(proxy_url)
        downloaders={provider.provider_id: MediaDownloader(
            RemoteURLPolicy(provider.allowed_hosts, resolver=resolver),transport=transport,
            user_agent=getattr(provider,'download_user_agent','Easel/2 material acquisition'))
            for provider in providers}
    generations={}
    if settings.get('MINIMAX_API_KEY','').strip():
        key=settings['MINIMAX_API_KEY']
        image=settings.get('EASEL_IMAGE_MODEL','image-01').strip()
        video=settings.get('EASEL_VIDEO_MODEL','').strip()
        if image=='image-01':generations['IMAGE']=MiniMaxImageProvider(key,model=image,receipt_root=service.outputs/'_production'/'provider_receipts'/'minimax-image')
        if video in {'MiniMax-H3','MiniMax-H3-Max'}:generations['VIDEO']=MiniMaxVideoProvider(key,model=video)
    # Hash public identities and policy configuration, never print credentials.
    version=fingerprint({'services':[(kind,p.provider_id,p.model,p.mode) for kind,p in generations.items()],
        'rights':{k:v.model_dump(mode='json') for k,v in _configured_rights(settings).items()}})
    task=SupplyTasks(service,operations,planning=planning,external_providers=providers,downloaders=downloaders,generation_providers=generations,
                       generation_rights=_configured_rights(settings),config_version=version,source_configuration_error=source_error,
                       enforce_provider_grants=True,
                       intent_compiler=FrozenIntentCompiler(planning) if planning is not None else None)
    from .subtitles import configured_fonts
    task.board_fonts=configured_fonts(settings)
    return task
