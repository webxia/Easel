"""Real local version revision/export lifecycle; model decisions remain scripted."""
import asyncio
import json
import shutil
import time
import pytest
from tests.production.test_creation_flow import test_confirm_to_real_render_to_reviewable_without_creator_acceptance as _first_cut, ScriptedModel
from easel.production.store import Store
from easel.production.service import WorkService
from easel.production.worker import Worker
from easel.production.operations import OperationService
from easel.production.planning import PlanningTasks
from easel.production.creation import CreationTasks
from easel.production.revisions import RevisionTasks


class RevisionModel(ScriptedModel):
    async def complete(self,messages,tools,schema):
        if schema['title']=='RevisionProposal':
            self.calls.append(messages)
            context=json.loads(messages[1]['content'][0]['text'])
            base=context['artifacts'][0]['base_edit']
            edit={key:base[key] for key in ('scenes','audio','captions','required_features')}
            edit['scenes'][0]['motion']='push_in'
            return {'content':json.dumps({'summary':'只增加缓慢推近','affected':['visual'],'expands_scope':False,
                'requires_new_generation':False,'reason':'现有画面内调整','edit':edit})}
        return await super().complete(messages,tools,schema)


@pytest.mark.skipif(not shutil.which('ffmpeg'),reason='FFmpeg unavailable')
def test_local_revision_keeps_accepted_version_then_explicitly_switches(tmp_path):
    _first_cut(tmp_path,True)
    store=Store(tmp_path/'outputs/_production/production.sqlite3')
    service=WorkService(store,outputs=tmp_path/'outputs',profiles=tmp_path/'profiles')
    work=service.list_works()['items'][0]['id'];snap=service.snapshot(work)
    first=next(a for a in snap['artifacts'] if a['kind']=='output')
    first_path,_=service.artifact_path(first['id']);first_bytes=first_path.read_bytes()
    service.command('accept',{'output_id':first['id']},command_id='accept-old',work_id=work,expected_revision=snap['revision'])
    snap=service.snapshot(work)
    service.command('revise',{'output_id':first['id'],'feedback':'只增加缓慢推近，其他不变'},command_id='revision',work_id=work,expected_revision=snap['revision'])
    model=RevisionModel();model.calls=[]
    planning=PlanningTasks(service,OperationService(store),model,{'provider':'direct-api','model':'offline-scripted','mode':'structured'},'offline')
    creation=CreationTasks(service,planning)
    worker=Worker(store,{'revise':RevisionTasks(service,planning,creation).revise,'render':creation.render,'quality':creation.quality},poll_interval=.01)
    deadline=time.monotonic()+35
    while time.monotonic()<deadline:
        asyncio.run(worker.run_once());snap=service.snapshot(work)
        active=next((r for r in snap['runs'] if r['id']==snap['active_run_id']),None)
        if active is None or active['state'] in {'succeeded','failed','needs_decision'}:break
        time.sleep(.1)
    assert snap['state']=='reviewable',[(t['kind'],t['error_json']) for t in snap['tasks']]
    outputs=[a for a in snap['artifacts'] if a['kind']=='output']
    assert len(outputs)==2 and snap['accepted_output_id']==first['id']
    assert first_path.read_bytes()==first_bytes
    assert any(block.get('type')=='image_url' for block in model.calls[0][1]['content'])
    second=next(a for a in outputs if a['id']!=first['id'])
    service.command('accept',{'output_id':second['id']},command_id='accept-new',work_id=work,expected_revision=snap['revision'])
    assert service.snapshot(work)['accepted_output_id']==second['id']
