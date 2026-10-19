"""Single composition root for web and standalone production workers."""
from __future__ import annotations
from dataclasses import dataclass, field
import asyncio
import json
import logging
from pathlib import Path
from .configuration import model_configuration
from .store import Store
from .service import WorkService
from .operations import OperationService
from .model_tasks import HTTPModelTransport
from .planning import PlanningTasks
from .creation import CreationTasks
from .worker import Worker


@dataclass
class ProductionRuntime:
    service: WorkService
    worker: Worker
    planning: PlanningTasks
    creation: CreationTasks
    _maintenance_stop: asyncio.Event = field(default_factory=asyncio.Event, repr=False)
    _cancel_cursor: str = field(default='', repr=False)

    async def maintenance_once(self):
        """Reconcile explicit cancels and deletion queues independently of claims."""
        from .deletion import DeletionService
        from .editors import EditError
        with self.service.store.connection() as reader:
            cancelled = [dict(row) for row in reader.execute("""SELECT t.id,t.work_id,t.run_id,t.result_json
                FROM tasks t JOIN runs r ON r.id=t.run_id WHERE t.kind='render' AND r.cancel_requested=1
                AND COALESCE(json_extract(t.result_json,'$.render_cancel_state'),'') NOT IN ('completed','cancelled','failed')
                AND t.id>? ORDER BY t.id LIMIT 100""", (self._cancel_cursor,))]
        self._cancel_cursor = cancelled[-1]['id'] if cancelled else ''
        for task in cancelled:
            try:
                job = await asyncio.to_thread(self.creation.editor.observe, task['id'])
                if job.status not in {'completed','failed','cancelled'}:
                    job = await asyncio.to_thread(self.creation.editor.cancel, task['id'])
                output = await asyncio.to_thread(self.creation.editor.collect, task['id']) if job.status == 'completed' else None
                self._save_cancelled_render(task, job, output)
            except (EditError, FileNotFoundError):
                # A cancelled handler may still be returning from local build in
                # another thread. Do not mark it done before its job can be seen.
                continue
        return await asyncio.to_thread(DeletionService(self.service.store, outputs=self.service.outputs).reconcile_cleanup)

    def _save_cancelled_render(self, task, job, output):
        from .contracts import canonical_json
        from .store import new_id, utc_now
        from .media import file_sha256
        with self.service.store.transaction() as writer:
            current = writer.execute("SELECT t.*,r.cancel_requested FROM tasks t JOIN runs r ON r.id=t.run_id WHERE t.id=?", (task['id'],)).fetchone()
            if current is None or not current['cancel_requested']:
                return
            result = json.loads(current['result_json'] or '{}')
            if result.get('render_cancel_state') == job.status:
                return
            receipt = {'job_id': job.job_id, 'status': job.status}
            if output:
                # This is a late receipt, never a new reviewable version. Original
                # render bytes remain under the private root even after deletion.
                path = output.video_path
                root = self.service.outputs / '_production' / 'renders' / task['id']
                if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()) or file_sha256(path) != output.sha256:
                    raise EditError('late render receipt identity changed')
                existing = writer.execute("SELECT id FROM artifacts WHERE run_id=? AND kind='render_receipt' AND json_extract(metadata_json,'$.source_task_id')=?", (task['run_id'],task['id'])).fetchone()
                artifact_id = existing[0] if existing else new_id('receipt')
                if not existing:
                    writer.execute("""INSERT INTO artifacts(id,work_id,run_id,kind,storage_ref,digest,size_bytes,
                        media_type,displayable,metadata_json,created_at) VALUES(?,?,?,'render_receipt',?,?,?,'video/mp4',0,?,?)""",
                        (artifact_id,task['work_id'],task['run_id'],path.relative_to(self.service.outputs).as_posix(),output.sha256,path.stat().st_size,
                         canonical_json({'schema_version':1,'source_task_id':task['id'],'render_job_id':job.job_id,'cancelled_result':True}),utc_now()))
                receipt['artifact_id'] = artifact_id
            result.update(render_cancel_state=job.status, render_receipt=receipt)
            writer.execute('UPDATE tasks SET result_json=?,revision=revision+1,updated_at=? WHERE id=?', (canonical_json(result),utc_now(),task['id']))
            self.service.store.append_event(writer,task['work_id'],'render_preserved' if output else 'render_cancel_observed',receipt,run_id=task['run_id'])

    async def _maintain(self):
        while not self._maintenance_stop.is_set():
            try:
                await self.maintenance_once()
            except Exception:
                logging.getLogger(__name__).warning('Production maintenance deferred; durable queue retained')
            try:
                await asyncio.wait_for(self._maintenance_stop.wait(), timeout=2)
            except asyncio.TimeoutError:
                pass

    async def run_forever(self):
        maintenance = asyncio.create_task(self._maintain())
        try:
            await self.worker.run_forever()
        finally:
            self._maintenance_stop.set()
            await maintenance

    def stop(self):
        self._maintenance_stop.set()
        self.worker.stop()


def create_runtime(root: Path, *, service=None, transport=None, handlers=None):
    root=Path(root).resolve()
    if service is None:
        store=Store(root/'outputs'/'_production'/'production.sqlite3');store.initialize()
        service=WorkService(store,outputs=root/'outputs',profiles=root/'profiles')
    settings,identity,version=model_configuration(root)
    if transport is None and identity:
        capabilities=frozenset({'text','structured','tools'}|{part.strip() for part in settings.get('EASEL_PRODUCTION_MODEL_CAPABILITIES','image').split(',') if part.strip()})
        transport=HTTPModelTransport(settings,capabilities=capabilities)
    operations=OperationService(service.store)
    planning=PlanningTasks(service,operations,transport,identity,version)
    from .public_facts import public_fact_tools, public_fact_capabilities
    planning.tool_factory=lambda ctx:public_fact_tools(settings,ctx,outputs=service.outputs)
    planning.execution_capabilities['public_fact_search'] = public_fact_capabilities(settings)[0]['available']
    from .voice import configured_voice_service,voice_preview_handler
    from .voice_tasks import VoiceTasks
    voice_provider=lambda:configured_voice_service(operations,root=service.outputs/'_production'/'voice',settings=settings)
    voice_tasks=VoiceTasks(service,voice_provider,settings_provider=lambda:settings)
    # S6-14 temporary policy: skip automatic semantic Gate only when the
    # operator explicitly opts in. Default remains the full AV quality Gate.
    manual_review_only = settings.get('EASEL_PRODUCTION_QC_MODE','full').strip() == 'manual'
    creation=CreationTasks(service,planning,voice_tasks=voice_tasks,
                           manual_review_only=manual_review_only,
                           visual_review=settings.get('EASEL_PRODUCTION_VISUAL_REVIEW','').strip()=='1')
    mapping={'plan':planning.plan,'analyze_director':planning.analyze_director,
             'edit':creation.edit,'render':creation.render,'quality':creation.quality}
    # Concrete adapters are composed here; no fallback mock providers are installed.
    from .supply_tasks import configured_supply
    supply=configured_supply(service,operations,planning,settings)
    planning.execution_capabilities['native_explainer_boards']=bool(supply.board_fonts)
    if supply.board_fonts:
        planning.execution_capabilities['visuals'].append('native explainer_boards: literal cards/columns and before-after states with highlighted cards; local rendered diagrams')
    mapping['supply']=supply.supply
    mapping['voice_preview']=voice_preview_handler(voice_provider,outputs=service.outputs)
    from .revisions import RevisionTasks
    mapping['revise']=RevisionTasks(service,planning,creation,supply=supply).revise
    mapping.update(handlers or {})
    worker=Worker(service.store,mapping)
    return ProductionRuntime(service,worker,planning,creation)
