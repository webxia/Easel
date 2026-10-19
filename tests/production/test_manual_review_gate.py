"""S6-14 manual-only quality Gate: technical PASS remains mandatory.

This temporary policy completes the production run for a Creator review, but
does not claim an unperformed semantic QC succeeded or accept output as user.
"""
import asyncio
import json
import shutil
import time

import pytest
from PIL import Image

from easel.production.artifacts import register_file
from easel.production.creation import CreationTasks
from easel.production.errors import ProductionError
from easel.production.operations import OperationService
from easel.production.planning import PlanningTasks
from easel.production.service import WorkService
from easel.production.store import Store
from easel.production.worker import Worker, TaskResult


class OfflineEditorProposal:
    capabilities = frozenset({"text", "structured", "image", "tools"})
    calls = 0

    async def complete(self, messages, tools, schema):
        self.calls += 1
        assert schema["title"] == "CreativeEdit"  # never auto-run semantic QC
        evidence = json.loads(messages[1]["content"][0]["text"])
        return {"content": json.dumps({
            "scenes": [{"scene_id": "s1", "asset_id": evidence["artifacts"][0]["asset_id"], "duration": 1}],
            "audio": [], "captions": []
        })}


@pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
                    reason="real local encoding required")
def test_manual_only_finishes_run_without_faking_semantic_pass_or_creator_accept(tmp_path):
    store = Store(tmp_path/"outputs/_production/production.sqlite3")
    store.initialize()
    service = WorkService(store, outputs=tmp_path/"outputs", profiles=tmp_path/"profiles")
    model = OfflineEditorProposal()
    identity = {"provider": "direct-api", "model": "offline-model", "mode": "structured"}
    planning = PlanningTasks(service, OperationService(store), model, identity, "offline-identity")
    creation = CreationTasks(service, planning, manual_review_only=True)
    media = tmp_path/"image.png"
    Image.new("RGB", (400,300), "blue").save(media)

    async def supply(ctx):
        artifact = register_file(service, ctx, media, kind="image", media_type="image/png",
                                 metadata={"source": "offline-technical-test"})
        return TaskResult(next_kind="edit", next_payload={"asset_ids": [artifact["id"]]})

    worker = Worker(store, {"supply": supply, "edit": creation.edit,
                            "render": creation.render, "quality": creation.quality},
                    poll_interval=.01)
    work_id = service.command("create", {"title": "Manual review technical test"}, command_id="mr-create")["work_id"]
    plan = {"title": "one second", "summary": "technical-only release to human", "script": "fixture",
            "scenes": [{"id": "s1", "purpose": "local test", "visual": "blue", "narration": ""}],
            "settings": {"duration_seconds": 1, "aspect_ratio": "16:9", "audio_mode": "silent"}}
    staged = service.command("plan", {"generate": False, "plan": plan}, command_id="mr-plan",
                             work_id=work_id, expected_revision=1)
    service.command("confirm", {"plan_revision": 1, "plan_hash": staged["plan_hash"],
                                "services": [identity]}, command_id="mr-confirm", work_id=work_id,
                    expected_revision=2)
    deadline = time.monotonic()+40
    while time.monotonic()<deadline:
        asyncio.run(worker.run_once())
        snapshot = service.snapshot(work_id)
        if snapshot["runs"][-1]["state"] in {"succeeded","failed","needs_decision"}:
            break
        time.sleep(.1)

    assert snapshot["runs"][-1]["state"] == "succeeded"
    assert snapshot["state"] == "reviewable"
    assert snapshot["accepted_output_id"] is None
    assert model.calls == 1  # Edit, no fake semantic call
    assert [t["state"] for t in snapshot["tasks"]]==["succeeded"]*4
    output = next(a for a in snapshot["artifacts"] if a["kind"]=="output")
    assert output["quality_state"]=="needs_fix"  # never semantic PASS
    assert output["manual_review_required"] is True
    with store.connection() as conn:
        checks = [dict(x) for x in conn.execute(
            "SELECT check_kind,status,findings_json FROM quality_checks")]
    assert [x["check_kind"] for x in checks]==["technical","semantic"]
    assert [x["status"] for x in checks]==["pass","not_tested"]
    semantic=json.loads(checks[1]["findings_json"])
    assert semantic["mode"]=="manual_review_only"
    assert semantic["creator_acceptance"]=="still_required"
    with pytest.raises(ProductionError) as error:
        service.command("accept", {"output_id":output["id"]}, command_id="mr-no-ack",
                        work_id=work_id, expected_revision=snapshot["revision"])
    assert error.value.code=="manual_review_confirmation_required"
    assert service.snapshot(work_id)["accepted_output_id"] is None

    acceptance=service.command("accept", {"output_id":output["id"],
                "manual_review_confirmed":True}, command_id="mr-explicit-accept",
                work_id=work_id, expected_revision=snapshot["revision"])
    assert acceptance["output_id"]==output["id"]
    assert service.snapshot(work_id)["accepted_output_id"]==output["id"]
    with store.connection() as conn:
        value=conn.execute("SELECT source FROM acceptances WHERE output_id=?",(output["id"],)).fetchone()
    assert value[0]=="explicit_manual_review"


@pytest.mark.parametrize('failed_scope',['full_av','sampled_visual_only'])
@pytest.mark.parametrize('same_bytes_copy',[False,True])
def test_manual_review_gate_refuses_known_failed_semantic_evidence(tmp_path,failed_scope,same_bytes_copy):
    store=Store(tmp_path/"output/_production/production.sqlite3")
    store.initialize()
    service=WorkService(store,outputs=tmp_path/"output",profiles=tmp_path/"profiles")
    work_id=service.command("create",{"title":"Known fail"},command_id="known-create")["work_id"]
    with store.transaction() as conn:
        from easel.production.store import utc_now
        # The historical semantic failure is never overridden by a later
        # manual/not_tested record, even if the file identity is the same.
        conn.execute("""INSERT INTO artifacts(id,work_id,kind,storage_ref,digest,size_bytes,media_type,
                     displayable,output_revision,quality_state,created_at)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                     ("out",work_id,"output","works/test/artifacts/old.mp4","a"*64,1,
                      "video/mp4",1,1,"needs_fix",utc_now()))
        if same_bytes_copy:
            conn.execute("""INSERT INTO artifacts(id,work_id,kind,storage_ref,digest,size_bytes,media_type,
                         displayable,output_revision,quality_state,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                         ('copy',work_id,'output','works/test/artifacts/copy.mp4','a'*64,1,'video/mp4',1,2,'needs_fix',utc_now()))
        for i,kind,status,extra in [
            ("tech","technical","pass",{}),
            ("bad","semantic","fail",{"findings":["known quality failure"],"scope":failed_scope}),
            ("skip","semantic","not_tested",{"mode":"manual_review_only"})
        ]:
            conn.execute("""INSERT INTO quality_checks(id,artifact_id,artifact_digest,
                          check_kind,rule_version,status,findings_json,created_at)
                          VALUES (?,?,?,?,?,?,?,?)""",
                         (i,'copy' if same_bytes_copy and i=='bad' else 'out',"a"*64,kind,"production-1",status,
                          json.dumps(extra),utc_now()))
    snapshot=service.snapshot(work_id)
    artifact=next(a for a in snapshot["artifacts"] if a["id"]=="out")
    assert artifact["manual_review_required"] is False
    with pytest.raises(ProductionError) as exc:
        service.command("accept",{"output_id":"out","manual_review_confirmed":True},
                        command_id="cannot-ignore-semantic-fail",work_id=work_id,expected_revision=snapshot["revision"])
    assert exc.value.code=="quality_blocked"


@pytest.mark.skipif(not shutil.which('ffmpeg'), reason='real rendered frames required')
@pytest.mark.parametrize('findings', [['0.5秒的蓝色图不能承担要求的示意'], []])
def test_actual_visual_check_never_fakes_audio_and_routes_bounded_repair(tmp_path,findings):
    store=Store(tmp_path/'outputs/db');store.initialize()
    service=WorkService(store,outputs=tmp_path/'outputs',profiles=tmp_path/'profiles')
    class Model(OfflineEditorProposal):
        async def complete(self,messages,tools,schema):
            if schema['title']=='CreativeEdit':
                return await super().complete(messages,tools,schema)
            assert schema['title']=='VisualPreviewReview'
            assert any(b.get('type')=='image_url' for b in messages[1]['content'])
            assert not any(b.get('type')=='input_audio' for b in messages[1]['content'])
            return {'content':json.dumps({'verdict':'pass' if not findings else 'fail',
                'observations':['实际渲染画面0.5秒为蓝色'],'findings':findings,
                'limitations':['离散画面；未听音频，不能证明全片质量']})}
    identity={'provider':'direct-api','model':'fixture','mode':'structured'}
    planning=PlanningTasks(service,OperationService(store),Model(),identity,'fixture')
    creation=CreationTasks(service,planning,manual_review_only=True,visual_review=True)
    media=tmp_path/'blue.png';Image.new('RGB',(400,300),'blue').save(media)
    async def supply(ctx):
        a=register_file(service,ctx,media,kind='image',media_type='image/png',metadata={})
        return TaskResult(next_kind='edit',next_payload={'asset_ids':[a['id']]})
    worker=Worker(store,{'supply':supply,'edit':creation.edit,'render':creation.render,'quality':creation.quality})
    work=service.command('create',{'title':'visual check'},command_id='create')['work_id']
    plan={'title':'test','summary':'test','script':'test','scenes':[{'id':'s1','purpose':'test','visual':'blue'}],
          'settings':{'duration_seconds':1,'audio_mode':'silent','aspect_ratio':'16:9'},
          'narration_policy':{'continuous':False,'duration_mode':'fixed'}}
    saved=service.command('plan',{'generate':False,'plan':plan},command_id='plan',work_id=work,expected_revision=1)
    service.command('confirm',{'plan_revision':1,'plan_hash':saved['plan_hash'],'services':[identity]},
                    command_id='confirm',work_id=work,expected_revision=2)
    deadline=time.monotonic()+25
    while time.monotonic()<deadline:
        asyncio.run(worker.run_once());snap=service.snapshot(work)
        if any(t['kind']=='quality' and t['state']=='succeeded' for t in snap['tasks']):break
        time.sleep(.05)
    with store.connection() as conn:
        checked=conn.execute("SELECT status,findings_json FROM quality_checks WHERE rule_version='visual-preview-1'").fetchone()
        evidence=json.loads(checked['findings_json'])
        assert evidence['audio_reviewed'] is False and evidence['full_av_reviewed'] is False
    assert snap['accepted_output_id'] is None
    if findings:
        repair=next(t for t in snap['tasks'] if t['kind']=='revise')
        assert json.loads(repair['payload_json'])['preserve_audio'] is True
        assert json.loads(repair['payload_json'])['repair_round']==1
        assert checked['status']=='fail' and not any(a.get('manual_review_required') for a in snap['artifacts'])
    else:
        assert snap['state']=='reviewable' and checked['status']=='not_tested'
        with store.connection() as conn:
            assert conn.execute("SELECT status FROM quality_checks WHERE check_kind='semantic'").fetchone()[0]=='not_tested'
