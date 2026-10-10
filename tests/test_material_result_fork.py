"""Actual Material delta checkpoint fork and nested evidence ancestry."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from easel import creation
from easel.integrations.hypit import service
from easel.integrations import material_results, output_receipts
from easel.integrations.material_layer import PlanningIntegration, MaterialGateIntegration, ProductionAuthoringIntegration
from easel.materials.application.assembly import MaterialBundleAssembler
from easel.materials.application.matching import MaterialMatcher
from easel.materials.application.visual_observation import prepare_observation, apply_observation
from easel.materials.store import AttemptMaterialStore
from tests.test_material_integration import material_integration_env, _material_delta_pixels_scenario, _record_authored_selection
from tests.test_hypit_integration import create_test_handoff


@pytest.mark.parametrize("material_integration_env", [
    {"material_observation": "material-observation-delta@1"},
], indirect=True)
def test_material_delta_real_fork_preserves_proof_and_rejects_nested_parent_drift(
        material_integration_env, tmp_path, monkeypatch):
    import web.app as webapp
    attempt, store, plan, run, assets, calls, emit = _material_delta_pixels_scenario(
        material_integration_env, monkeypatch, clause_count=8)
    emit(plan.needs[0], assets[0])
    emit(plan.needs[1], assets[0])
    current = store.read_asset(assets[0].asset_id)
    assert [payload["mode"] for _, payload in calls] == ["facts", "delta", "delta"]
    matches = tuple(next(match for match in MaterialMatcher().match(need, (current,)).matches
                         if match.asset_id == current.asset_id) for need in plan.needs[:2])
    bundle = MaterialBundleAssembler().assemble(plan, run, (current,), matches, bundle_id=run.result_bundle_id)
    readiness, gaps = material_results.readiness_calculator(attempt, store).calculate(plan, bundle)
    gate = MaterialGateIntegration().record(attempt, plan, bundle, run, readiness, gaps)
    attempt = gate["attempt"]
    assert gate["status"] == "MATERIAL_READY"
    attempt = ProductionAuthoringIntegration().prepare(attempt, selected_asset_ids=[current.asset_id])["attempt"]
    attempt = service.begin_film_authoring(attempt["attempt_id"])
    root = Path(attempt["workspace"]["path"])
    _record_authored_selection(attempt, current, root)
    author = root / "productions/easel-authoring/authors/main.svml"
    selection = json.loads((root / "productions/easel-authoring/material-selection.json").read_bytes())
    selected_src = selection["assets"][0]["src"]
    # Unlike the removed string-Writer route, native Authoring must have a
    # complete typed SVML source and explicit on-timeline Need expression.
    author.write_text(f"""<?svml using="@hypit/markup@1"?>
<svml>
<import as="time" from="@hypit/timeline-author@1"/>
<import as="media" from="@hypit/media@1"/>
<import as="picture" from="@hypit/media-track@1"/>
<import as="space" from="@hypit/spatial@1"/>
<import as="film" from="@hypit/film@1"/>
<import as="render" from="@hypit/render-hyperframes@1"/>
<import as="recipes" source="./recipes.svs"/>
<time:Clock id="clock" frame-rate="24"/>
<time:Timeline id="program" clock={{clock}} end="2s"/>
<space:Canvas id="canvas" width="1080" height="1920"/>
<space:Frame id="full-frame" within={{canvas}} left="0px" top="0px" right="1080px" bottom="1920px"/>
<space:Extent id="image-size" width="{current.technical.width}" height="{current.technical.height}"/>
<media:Image id="selected" src="{selected_src}"/>
<picture:Track id="pictures" canvas={{canvas}} timeline={{program.timeline}}>
  <Item id="scene-first" image={{selected}} extent={{image-size}} frame={{full-frame}} appearance={{recipes.media.frame}} at="0s" for="1s"/>
  <Item id="scene-second" image={{selected}} extent={{image-size}} frame={{full-frame}} appearance={{recipes.media.frame}} at="1s" for="1s"/>
</picture:Track>
<film:Film id="movie" canvas={{canvas}} timeline={{program.timeline}} appearance={{recipes.film.memo}}>
  <Track source={{pictures.visual}}/>
</film:Film>
<render:Video id="final" composition={{movie.composition}} timeline={{program.timeline}}/>
</svml>
""" + "".join("<!-- Easel expression: " + json.dumps({
        "need_id": need_id, "element_ids": [element_id],
        "at_seconds": begin, "end_seconds": begin + 1,
        "responsibility": "material",
    }, ensure_ascii=False) + " -->\n" for need_id, element_id, begin in (
        (plan.needs[0].need_id, "scene-first", 0),
        (plan.needs[1].need_id, "scene-second", 1),
    )))
    author.with_name("recipes.svs").write_text(
        '<?svml using="@hypit/svs@1"?>\n<sheet version="1">\n'
        'film.memo { background: #101820; }\nmedia.frame { stack-order: 0; }\n'
        '</sheet>\n')

    class FailedBuildCLI:
        def __init__(self):
            self.build_calls = 0
        def check(self, workspace, source):
            from easel.integrations.hypit.native_source import parse_file, parse_run
            from easel.integrations.hypit import authoring_publication
            assert source == workspace / authoring_publication.RUN
            parse_file(workspace / authoring_publication.AUTHOR, workspace=workspace)
            _, run, _ = parse_run(source, workspace=workspace)
            assert run["targets"] == [{"output": "final.video"}]
            return {"format": "hypit.cli-check@1", "ok": True, "sourceKind": "run",
                    "run": authoring_publication.RUN,
                    "author": authoring_publication.AUTHOR,
                    "frontend": "@hypit/run-markup@1", "targetCount": 1,
                    "targets": ["final.video"], "candidates": 0,
                    "satisfactions": 0, "historicalOutputCount": 0}
        def plan(self, *args, **kwargs):
            return {"format": "hypit.cli-plan@1", "ok": True}
        def pricing(self, *args, **kwargs):
            return {"format": "hypit.cli-pricing@1", "requestCount": 1, "groups": []}
        def build(self, *args, **kwargs):
            self.build_calls += 1
            return {"format": "hypit.cli-build@1",
                    "build": {"id": "bld_material_delta_001", "work": {"outcome": "failed"}}}
        def status(self, workspace, build_id, **kwargs):
            return {"format": "hypit.cli-status@1", "build": {"id": build_id, "work": {"outcome": "failed"}}}

    cli = FailedBuildCLI()
    service.complete_film_authoring(attempt["attempt_id"], cli=cli)
    runtime = tmp_path / "material-delta-runtime.json"
    runtime.write_text(json.dumps({"format": "hypit.runtime-local@1", "dataRoot": ".fixture-material-delta-runtime",
                                   "credentials": {}, "endpoints": {}, "bindings": {}}) + "\n")
    service.resolve_film_attempt_runtime(attempt["attempt_id"], str(runtime))
    service.validate_film_attempt(attempt["attempt_id"], "productions/easel-authoring/runs/main.svrun", cli=cli)
    service.estimate_film_attempt(attempt["attempt_id"], cli=cli)
    service.approve_film_cost(attempt["attempt_id"], 1)
    failed = service.submit_film_build(attempt["attempt_id"], title="offline material delta fixture", cli=cli)
    assert failed["execution_status"] == "BUILD_FAILED" and cli.build_calls == 1

    parent_id, observation_count = failed["attempt_id"], len(calls)
    child = service.retry_failed_film_build(parent_id, cli=cli)
    assert child["attempt_id"] != parent_id and child["retry_source"]["attempt_id"] == parent_id
    assert child["retry_source"]["status"] == "READY"
    assert child["result_protocols"] == failed["result_protocols"] and child["handoff"] == failed["handoff"]
    assert child["execution_status"] == "NOT_SUBMITTED" and child["cost"]["approved"] is False
    assert len(calls) == observation_count and cli.build_calls == 1
    child_store = AttemptMaterialStore(child["workspace"]["path"])
    child_plan = PlanningIntegration().load(child)["plan"]
    MaterialGateIntegration().assert_ready(child)
    inherited = child_store.read_asset(current.asset_id)
    for need in child_plan.needs[:2]:
        assert material_results.eligible(child_store, need, inherited, attempt=child)
    assert service.retry_failed_film_build(parent_id, cli=cli)["attempt_id"] == child["attempt_id"]
    assert len(calls) == observation_count

    # An independent second failed Build must form a *third* Attempt, without
    # redispatching the original facts, model, Provider or charged media.
    child_id = child["attempt_id"]
    service.validate_film_attempt(child_id, "productions/easel-authoring/runs/main.svrun", cli=cli)
    service.estimate_film_attempt(child_id, cli=cli)
    service.approve_film_cost(child_id, 1)
    child_failed = service.submit_film_build(
        child_id, title="offline second Material checkpoint failure", cli=cli)
    assert child_failed["execution_status"] == "BUILD_FAILED" and cli.build_calls == 2
    grandchild = service.retry_failed_film_build(child_id, cli=cli)
    assert grandchild["attempt_id"] not in {parent_id, child_id}
    assert grandchild["retry_source"]["attempt_id"] == child_id
    assert grandchild["retry_source"]["status"] == "READY"
    assert grandchild["result_protocols"] == child["result_protocols"] == failed["result_protocols"]
    assert grandchild["handoff"] == failed["handoff"]
    assert grandchild["execution_status"] == "NOT_SUBMITTED"
    assert grandchild["cost"]["approved"] is False
    grandchild_store = AttemptMaterialStore(grandchild["workspace"]["path"])
    grandchild_plan = PlanningIntegration().load(grandchild)["plan"]
    MaterialGateIntegration().assert_ready(grandchild)
    inherited_twice = grandchild_store.read_asset(current.asset_id)
    for need in grandchild_plan.needs[:2]:
        assert material_results.eligible(grandchild_store, need, inherited_twice,
                                         attempt=grandchild)
    assert service.retry_failed_film_build(child_id, cli=cli)["attempt_id"] == grandchild["attempt_id"]
    assert len(calls) == observation_count and cli.build_calls == 2

    challenge = child_plan.needs[2]
    manifest, attachments = prepare_observation(challenge, inherited, child_store.resolve_asset_locator(inherited.file.path))
    report = webapp._observe_material_frames(child, manifest, attachments)
    observed = apply_observation(challenge, inherited, manifest, report,
                                 result_processor=material_results.processor(child, child_store))
    assert len(calls) == observation_count + 1 and calls[-1][1]["mode"] == "delta"
    assert not calls[-1][1].get("repair") and len(report["result_groups"]) == 1
    request = child_store.read_recovery_record(report["result_groups"][0]["request"]["key"])
    assert request["input"]["attempt_id"] == child["attempt_id"] and request["facts_ref"] is not None
    facts = child_store.read_recovery_record(request["facts_ref"]["key"])
    facts_request = child_store.read_recovery_record(facts["origin"]["request"]["key"])
    assert facts_request["input"]["attempt_id"] == parent_id
    processor = material_results.processor(child, child_store)
    assert processor.verify(manifest, report) == report
    assert material_results.eligible(child_store, challenge, observed, attempt=child)
    finished_calls = len(calls)

    parent = service.get_film_attempt(parent_id)

    def corrupt_fixture_parent(**changes):
        # Controlled test-only on-disk corruption bypasses the production
        # read-only mutation guard. The child must reject altered ancestors.
        with creation.edit_creation(parent["creation_id"]) as persisted:
            item = next(row for row in persisted["hypit_attempts"]
                        if row["attempt_id"] == parent_id)
            item.update(deepcopy(changes))

    original_protocols = deepcopy(parent["result_protocols"])
    try:
        corrupt_fixture_parent(result_protocols={
            "schema": "agent-result-protocols@1", "profiles": {}})
        with pytest.raises(output_receipts.OutputReceiptError):
            processor.verify(manifest, report)
        with pytest.raises(output_receipts.OutputReceiptError):
            material_results.eligible(child_store, challenge, observed, attempt=child)
    finally:
        corrupt_fixture_parent(result_protocols=original_protocols)
    assert processor.verify(manifest, report) == report and len(calls) == finished_calls

    other_package = create_test_handoff(creation.get_creation(parent["creation_id"]))
    other = service.create_film_attempt(parent["creation_id"], other_package["handoff_id"],
                                       preparation_key="c" * 64, runtime_status="NOT_CONFIGURED",
                                       result_protocols=deepcopy(original_protocols))
    assert other["handoff"] != parent["handoff"]
    original_handoff = deepcopy(parent["handoff"])
    try:
        corrupt_fixture_parent(handoff=other["handoff"])
        with pytest.raises(output_receipts.OutputReceiptError):
            processor.verify(manifest, report)
    finally:
        corrupt_fixture_parent(handoff=original_handoff)
    assert processor.verify(manifest, report) == report
    assert material_results.eligible(child_store, challenge, observed, attempt=child)
    MaterialGateIntegration().assert_ready(child)
    assert len(calls) == finished_calls and cli.build_calls == 2
