from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from PIL import Image

from easel import creation, creative_mode
from easel.integrations.hypit import handoff, service
from easel.integrations.hypit.errors import HypitIntegrationError
from easel.integrations.material_layer import (
    MaterialGateIntegration,
    MaterialHypitBridge,
    MaterialIntegrationError,
    MaterialProductOrchestrator,
    PlanningIntegration,
    ProductionAuthoringIntegration,
)
from easel.integrations import material_supply as material_supply_module
from easel.materials.application.assembly import MaterialBundleAssembler
from easel.materials.application.readiness import MaterialReadinessCalculator
from easel.materials.application.rights import RightsService
from easel.materials.application.compiler import NeedCompiler
from easel.materials.domain import (
    BgmNeedSpec,
    SfxNeedSpec,
    CandidateSource,
    DurationHint,
    FileInfo,
    IntelligenceStatus,
    MaterialAsset,
    MaterialMatch,
    MaterialNeed,
    MaterialPlan,
    MediaType,
    NeedImportance,
    NeedIntent,
    NeedScope,
    NeedScopeType,
    RightsEvidence,
    RightsInfo,
    RightsStatus,
    SemanticInfo,
    SemanticAnnotation,
    SemanticField,
    SemanticInference,
    SupplyRun,
    SupplySourceResult,
    TechnicalInfo,
    TechnicalStatus,
    VoiceIdentityRef,
    VoiceIdentitySource,
    VoiceNeedSpec,
)
from easel.materials.store import AttemptMaterialStore
from easel.materials.providers import LocalProvider


def test_general_mode_library_scope_is_isolated_per_creation(material_integration_env):
    first = creation.create_creation("通用作品一", creative_mode="clear_memo_video")
    second = creation.create_creation("通用作品二", creative_mode="clear_memo_video")
    scope = material_supply_module.ProductMaterialSupply.scope_for_attempt
    a = scope({"creation_id": first["id"]})
    assert a == scope({"creation_id": first["id"]})
    assert a != scope({"creation_id": second["id"]})
    assert a != scope({"creation_id": material_integration_env["creation_id"]})


def _observed_semantic(description: str) -> SemanticInfo:
    return SemanticInfo(inferences=(SemanticInference(
        analyzer_id="fixture-observation", status=IntelligenceStatus.COMPLETE,
        annotations=(SemanticAnnotation(field=SemanticField.CAPTION, value=description,
                                        confidence=0.95, evidence="fixture media observation"),),
    ),))


@pytest.fixture
def material_integration_env(tmp_path, monkeypatch, request):
    from easel.runtime_config import EaselRuntimeConfig

    load_config = EaselRuntimeConfig.load
    monkeypatch.setattr(EaselRuntimeConfig, "load", classmethod(lambda cls: load_config(
        environ={"EASEL_MATERIAL_LIBRARY_ROOT": str(tmp_path / "material-library")},
        env_file=tmp_path / "absent.env")))

    def local_registry(roots):
        registry = material_supply_module.ProviderRegistry()
        if roots:
            registry.register(LocalProvider(tuple(roots)))
        return registry, ()

    monkeypatch.setattr(material_supply_module, "product_provider_registry", local_registry)
    outputs = tmp_path / "outputs"
    modes = tmp_path / "creative_modes"
    mode_dir = modes / "clear_memo_video"
    mode_dir.mkdir(parents=True)
    (mode_dir / "mode.json").write_text(json.dumps({
        "id": "clear_memo_video", "name": "清醒备忘录", "version": "1.0",
        "music_ducking": {"gain_ratio": 0.25, "attack_seconds": 0.12, "release_seconds": 0.45},
        "routes": ["douyin-video"],
    }), encoding="utf-8")
    for filename in ("director-treatment.md", "visual-bible.md", "audio-bible.md",
                     "editing-bible.md", "qc-rubric.md"):
        (mode_dir / filename).write_text(f"# {filename}\n", encoding="utf-8")
    monkeypatch.setattr(creation, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(creation, "CREATIONS_DIR", outputs / "_creations")
    monkeypatch.setattr(creative_mode, "CREATIVE_MODES_DIR", modes)
    monkeypatch.setattr(handoff, "CREATIVE_MODES_DIR", modes, raising=False)
    monkeypatch.setenv("EASEL_HYPIT_HOME", str(tmp_path / ".easel" / "hypit"))
    monkeypatch.setenv("EASEL_MATERIAL_LIBRARY_ROOT", str(tmp_path / "material-library"))
    work = creation.create_creation(
        "一个需要素材层的短视频", profile="测试", creative_mode="clear_memo_video",
        route="hypit_video",
    )
    package = service.create_creation_handoff(
        work["id"],
        content_core={"schema": "content-core@1", "question": work["idea"]},
        truth_packet={"schema": "easel-truth-packet@2", "claims": [], "personal_facts": [],
                      "first_person_allowed": [], "public_allowed": [], "forbidden_inventions": [],
                      "uncertainty_policy": {"plan_is_not_experience": True,
                                             "learning_is_not_proven_capability": True,
                                             "unknown_claims": "label_uncertain"}},
        creator_context={"schema": "easel-creator-context@1",
                         "identity": {"public_description": "测试创作者"}, "audience": "测试观众",
                         "voice": {"tone": "克制", "avoid": []}, "relevant_context": [],
                         "privacy_policy": {"do_not_infer_private_facts": True}},
        production_request={"media_type": "video", "orientation": "9:16", "language": "zh-CN",
                            "preferred_duration_seconds": {"min": 10, "max": 30}},
        max_budget_usd=5,
    )
    from easel.integrations import result_protocols as result_versions
    attempt = service.create_film_attempt(
        work["id"], package["handoff_id"], preparation_key="b" * 64,
        runtime_status="NOT_CONFIGURED",
        result_protocols={'schema': 'agent-result-protocols@1',
                          'profiles': {**result_versions.DEFAULT_PROFILES,
                                      **getattr(request, 'param', {})}},
    )
    return attempt


def _contracts(attempt: dict, root: Path):
    plan = MaterialPlan(
        plan_id="plan-int-1", creation_id=attempt["creation_id"], attempt_id=attempt["attempt_id"],
        needs=(MaterialNeed(
            need_id="need-main", scope=NeedScope(type=NeedScopeType.SCENE, ref="scene-1"),
            media_type=MediaType.IMAGE, role="主视觉", intent=NeedIntent(description="一张测试图片"),
            duration_hint=DurationHint(target_seconds=1), importance=NeedImportance.REQUIRED,
        ),),
    )
    data = b"\x89PNG\r\n\x1a\nfixture-material"
    digest = hashlib.sha256(data).hexdigest()
    store = AttemptMaterialStore(root)
    locator = store.write_asset_bytes("asset-main", "original.png", data)
    asset = MaterialAsset(
        asset_id="asset-main", media_type=MediaType.IMAGE,
        file=FileInfo(path=locator, sha256=digest, size=len(data), mime="image/png"),
        source=CandidateSource(kind="fixture", provider="fixture", provider_asset_id="fixture-1"),
        rights=RightsInfo(status=RightsStatus.KNOWN, license_name="Fixture License",
                           evidence=(RightsEvidence(kind="asset_license", reference="fixture://license"),)),
        technical=TechnicalInfo(status=TechnicalStatus.PASSED, width=1, height=1, mime="image/png"),
        semantic=_observed_semantic("一张测试图片"),
    )
    store.write_asset(asset)
    match = MaterialMatch(need_id="need-main", asset_id="asset-main", rank=1, score=1.0,
                          reasons=("hard_filter=passed",), qualified=True)
    run = SupplyRun(
        supply_run_id="run-int-1", plan_id=plan.plan_id,
        started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        finished_at=datetime(2026, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
        provider_results=(SupplySourceResult(source_id="fixture", status="COMPLETE", candidates_found=1,
                                             acquired_assets=1),),
        result_bundle_id="bundle-int-1",
    )
    bundle = MaterialBundleAssembler().assemble(plan, run, (asset,), (match,), bundle_id="bundle-int-1")
    readiness, gaps = MaterialReadinessCalculator(store=store).calculate(plan, bundle)
    return plan, asset, run, bundle, readiness, gaps


def _planning(attempt):
    result = PlanningIntegration().persist(
        attempt,
        MaterialPlan(plan_id="plan-int-1", creation_id=attempt["creation_id"], attempt_id=attempt["attempt_id"],
                     needs=(MaterialNeed(
                         need_id="need-main", scope=NeedScope(type=NeedScopeType.SCENE, ref="scene-1"),
                         media_type=MediaType.IMAGE, role="主视觉", intent=NeedIntent(description="一张测试图片"),
                         duration_hint=DurationHint(target_seconds=1),
                         importance=NeedImportance.REQUIRED),)),
        treatment="# Treatment\n", script="假设脚本内容。\n", scenes="# Scenes\n",
    )
    attempt.update(result["attempt"])
    return result


def test_protected_script_truth_status_includes_full_script_for_human_review(material_integration_env):
    from fastapi.testclient import TestClient
    from web.app import app, require_local_operator

    attempt = material_integration_env
    planning = _planning(attempt)
    app.dependency_overrides[require_local_operator] = lambda: None
    try:
        with TestClient(app) as client:
            response = client.get(f"/api/film-attempts/{attempt['attempt_id']}/script-truth")
    finally:
        app.dependency_overrides.pop(require_local_operator, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["script"] == "假设脚本内容。\n"
    assert payload["script_sha256"] == planning["truth_ledger"]["script_sha256"]
    assert payload["claims"] == planning["truth_ledger"]["claims"]


def test_audio_preview_requires_current_bundle_and_unchanged_bytes(material_integration_env):
    import io
    import wave
    from fastapi.testclient import TestClient
    from web.app import app, require_local_operator

    attempt = material_integration_env
    _planning(attempt)
    root = Path(attempt["workspace"]["path"])
    plan, asset, run, _, _, _ = _contracts(attempt, root)
    stream = io.BytesIO()
    with wave.open(stream, "wb") as audio:
        audio.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
        audio.writeframes(b"\0\0" * 800)
    payload = stream.getvalue()
    store = AttemptMaterialStore(root)
    locator = store.write_asset_bytes(asset.asset_id, "preview.wav", payload)
    asset = asset.model_copy(update={
        "media_type": MediaType.AUDIO,
        "file": FileInfo(path=locator, sha256=hashlib.sha256(payload).hexdigest(), size=len(payload), mime="audio/wav"),
    })
    store.write_asset(asset)
    bundle = MaterialBundleAssembler().assemble(plan, run, (asset,), (), bundle_id=run.result_bundle_id)
    readiness, gaps = MaterialReadinessCalculator(store=store).calculate(plan, bundle)
    MaterialGateIntegration().record(attempt, plan, bundle, run, readiness, gaps)
    url = f"/api/film-attempts/{attempt['attempt_id']}/material-assets/{asset.asset_id}/preview"
    app.dependency_overrides[require_local_operator] = lambda: None
    try:
        with TestClient(app) as client:
            response = client.get(url, params={"sha256": asset.file.sha256})
            assert response.status_code == 200
            assert response.headers["content-type"] == "audio/wav"
            assert response.headers["cache-control"] == "no-store"
            assert response.content == store.resolve_asset_locator(asset.file.path).read_bytes()
            assert client.get(url, params={"sha256": "0" * 64}).status_code == 404
            store.resolve_asset_locator(asset.file.path).write_bytes(b"changed bytes")
            assert client.get(url, params={"sha256": asset.file.sha256}).status_code == 409
    finally:
        app.dependency_overrides.pop(require_local_operator, None)


def _record_authored_selection(
    attempt, asset, root, *, author_relative="productions/easel-authoring/authors/main.svml",
    run_author_ref="../authors/main.svml",
):
    store = AttemptMaterialStore(root)
    author = root / author_relative
    run = root / "productions/easel-authoring/runs/main.svrun"
    author.parent.mkdir(parents=True, exist_ok=True)
    run.parent.mkdir(parents=True, exist_ok=True)
    src = store.hypit_source_path(asset, author.relative_to(root).as_posix())
    author.write_text(f'<media:Image id="selected" src="{src}"/>', encoding="utf-8")
    from easel.materials.domain import MaterialBundle
    bundle = MaterialBundle.from_json((root / "materials/bundle.json").read_text(encoding="utf-8"))
    readiness = json.loads((root / "materials/readiness.json").read_text(encoding="utf-8"))
    run.write_text(json.dumps({
        "schema": "easel-authoring-svrun@1", "creation_id": attempt["creation_id"],
        "attempt_id": attempt["attempt_id"], "plan_id": bundle.plan_id,
        "plan_revision": readiness["plan_revision"], "bundle_id": bundle.bundle_id,
        "bundle_revision": bundle.revision, "readiness_revision": bundle.revision,
        "authoring_source": run_author_ref, "material_selection": "../material-selection.json",
        "status": "AUTHORING_READY", "publication_allowed": False,
        "build": {"enabled": False, "reason": "stops_before_hypit_build"},
    }), encoding="utf-8")
    selection_path = root / "productions/easel-authoring/material-selection.json"
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    selection["assets"] = [{"asset_id": asset.asset_id, "media_type": asset.media_type.value,
                            "src": src, "mime": asset.file.mime, "sha256": asset.file.sha256}]
    selection["status"] = "SELECTED"
    selection_path.write_text(json.dumps(selection), encoding="utf-8")
    return run



def _native_stage(material_integration_env):
    """The real native Authoring Owner fixture, with deterministic local Check only."""
    from tests.test_native_authoring_publication import native_owner, CheckBoundary
    from easel.integrations.hypit import authoring_publication as publisher
    attempt, root = native_owner(material_integration_env)
    return attempt, root, publisher, CheckBoundary(root)



def _stage_native_selected_image(attempt, asset, root, *, need_id="need-main"):
    """Stage a typed one-image SVML using the existing frozen Material selection.

    This test-only Writer prepares model-owned input. The production native
    Publisher alone derives/validates/promotes it after Check.
    """
    from tests.test_native_authoring_publication import CheckBoundary
    from easel.integrations.hypit import authoring_publication as native
    _record_authored_selection(attempt, asset, root)
    selection = json.loads((root / native.SELECTION).read_text())
    src = selection["assets"][0]["src"]
    width, height = asset.technical.width or 1, asset.technical.height or 1
    author = root / native.AUTHOR
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
<time:Timeline id="program" clock={{clock}} end="1s"/>
<space:Canvas id="canvas" width="1080" height="1920"/>
<space:Frame id="full-frame" within={{canvas}} left="0px" top="0px" right="1080px" bottom="1920px"/>
<space:Extent id="image-size" width="{width}" height="{height}"/>
<media:Image id="selected" src="{src}"/>
<picture:Track id="pictures" canvas={{canvas}} timeline={{program.timeline}}>
  <Item id="scene-main" image={{selected}} extent={{image-size}} frame={{full-frame}} appearance={{recipes.media.frame}} at="0s" for="1s"/>
</picture:Track>
<film:Film id="movie" canvas={{canvas}} timeline={{program.timeline}} appearance={{recipes.film.memo}}>
  <Track source={{pictures.visual}}/>
</film:Film>
<render:Video id="final" composition={{movie.composition}} timeline={{program.timeline}}/>
</svml>
<!-- Easel expression: """ + json.dumps({
        "need_id": need_id, "element_ids": ["scene-main"],
        "at_seconds": 0, "end_seconds": 1, "responsibility": "material"
    }, ensure_ascii=False) + " -->\n")
    author.with_name("recipes.svs").write_text(
        '<?svml using="@hypit/svs@1"?>\n<sheet version="1">\n'
        'film.memo { background: #101820; }\n'
        'media.frame { stack-order: 0; }\n</sheet>\n')
    return native, CheckBoundary(root)


def test_authoring_selection_uses_actual_svml_refs_and_frozen_revisions(material_integration_env):
    attempt, root, native, cli = _native_stage(material_integration_env)
    selection = json.loads((root / native.SELECTION).read_bytes())
    assert selection["attempt_id"] == attempt["attempt_id"]
    assert selection["bundle_revision"] == attempt["material_gate"]["bundle_revision"]
    assert "../" in selection["assets"][0]["src"]
    ready = service.complete_film_authoring(attempt["attempt_id"], cli=cli)
    selection = json.loads((root / native.SELECTION).read_bytes())
    assert selection["assets"][0]["qualified_need_ids"] == ["need-main"]
    assert ready["authoring_status"] == "AUTHORING_READY" and len(cli.calls) == 1
    frozen = native._files(root)
    expected = {item["path"]: item["sha256"] for item in ready["authoring"]["files"]}
    assert frozen == expected, {"missing": sorted(set(expected)-set(frozen)),
                                "new": sorted(set(frozen)-set(expected)),
                                "mismatched": [key for key in frozen.keys() & expected.keys() if frozen[key] != expected[key]]}
    assert ProductionAuthoringIntegration().validate_authored_selection(ready, native.RUN)["attempt"] == ready
    assert native._files(root) == frozen
    manifest = json.loads((root / native.SIDECAR).read_bytes())
    manifest["attempt_id"] = "different-attempt"
    (root / native.SIDECAR).write_text(json.dumps(manifest))
    # The native Publisher rejects tampered bytes through its receipt-specific
    # error type, not the old general HypitIntegrationError.
    with pytest.raises(native.AuthoringPublicationError, match="file set changed"):
        ProductionAuthoringIntegration().validate_authored_selection(ready, native.RUN)
    assert service.get_film_attempt(ready["attempt_id"]) == ready


def test_selected_image_extent_uses_inspected_source_dimensions(material_integration_env):
    attempt, root, native, cli = _native_stage(material_integration_env)
    author = root / native.AUTHOR
    original = author.read_text()
    assert '<space:Extent id="image-size" width="1" height="1"/>' in original
    author.write_text(original.replace('id="image-size" width="1"', 'id="image-size" width="999"'))
    before = native._files(root)
    with pytest.raises(HypitIntegrationError, match="Extent|dimension"):
        service.complete_film_authoring(attempt["attempt_id"], cli=cli)
    assert native._files(root) == before and not cli.calls
    assert not service.get_film_attempt(attempt["attempt_id"]).get("pending_authoring_publication")


def test_int01_planning_persists_ready_manifest_and_rejects_empty(material_integration_env):
    attempt = material_integration_env
    result = _planning(attempt)
    root = Path(attempt["workspace"]["path"])
    assert result["status"] == "PLANNING_READY"
    assert (root / "materials/plan.json").is_file()
    manifest = json.loads((root / "planning/manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "PLANNING_READY"
    assert attempt["attempt_id"] == result["attempt"]["attempt_id"]
    with pytest.raises(MaterialIntegrationError, match="不能为空"):
        PlanningIntegration().persist(attempt, result["plan"], treatment="", script="x", scenes="x")


@pytest.mark.parametrize("material_integration_env", [{}, {"script_ledger": "easel-script-claim-ledger@3"}],
                         indirect=True, ids=["legacy", "markdown"])
def test_script_truth_review_blocks_supply_and_production_until_operator_accepts(material_integration_env, monkeypatch):
    import easel.integrations.material_supply as supply_module

    attempt = material_integration_env
    from easel.integrations import result_protocols
    markdown = result_protocols.selected(attempt, "script_ledger") is not None
    script = ("## 旁白\r\nThis company grew **40 percent** last year.\r\n" if markdown
              else "This company grew 40 percent last year.")
    refs = {key: value * 64 for key, value in zip(
        ("content_core_sha256", "truth_packet_sha256", "creator_context_sha256",
         "production_brief_sha256", "creative_mode_sha256"),
        ("a", "b", "c", "d"),
    )}
    pending = PlanningIntegration().persist(
        attempt, MaterialPlan(
            plan_id="truth-review-plan", creation_id=attempt["creation_id"], attempt_id=attempt["attempt_id"],
            context_refs=refs,
            needs=(MaterialNeed(
                need_id="need-main", scope=NeedScope(type=NeedScopeType.SCENE, ref="scene-1"),
                media_type=MediaType.IMAGE, role="visual", intent=NeedIntent(description="image"),
                importance=NeedImportance.REQUIRED,
            ),),
        ),
        treatment="Treatment", script=script, scenes="Scenes",
    )
    attempt = pending["attempt"]
    assert pending["truth_ledger"]["status"] == "REVIEW_REQUIRED"
    monkeypatch.setattr(
        supply_module, "product_provider_registry",
        lambda _roots: (_ for _ in ()).throw(AssertionError("Supply must not run before review")),
    )
    result = MaterialProductOrchestrator().run_with_planning(
        attempt, (), {**pending, "context_refs": refs},
    )
    assert result["status"] == "SCRIPT_TRUTH_REVIEW_REQUIRED"
    assert "material_gate" not in result["attempt"]
    with pytest.raises(MaterialIntegrationError, match="local-operator review"):
        ProductionAuthoringIntegration().prepare(attempt)

    ledger = pending["truth_ledger"]
    reviewed = PlanningIntegration().review_script(
        attempt,
        confirm_all_claims_reviewed=True,
        expected_script_sha256=ledger["script_sha256"],
        expected_truth_packet_sha256=ledger["truth_packet_sha256"],
    )
    attempt = reviewed["attempt"]
    assert reviewed["ledger"]["claims"][0]["status"] == "HUMAN_REVIEWED"
    if markdown:
        assert reviewed["ledger"]["coverage"] == ledger["coverage"]
        assert reviewed["ledger"]["parser_identity"] == ledger["parser_identity"]
    replanned = PlanningIntegration().persist(attempt, pending["plan"], treatment="Treatment", script=script, scenes="Scenes")
    assert replanned["truth_ledger"] == reviewed["ledger"]
    attempt = replanned["attempt"]
    monkeypatch.setattr(supply_module, "product_provider_registry",
                        lambda _roots: (supply_module.ProviderRegistry(), ()))
    loaded = PlanningIntegration().load(attempt)
    resumed = MaterialProductOrchestrator().run_with_planning(attempt, (), loaded)
    assert resumed["status"] == "MATERIAL_NOT_READY"
    assert resumed["attempt"]["material_gate"]["status"] == "MATERIAL_NOT_READY"
    changed = PlanningIntegration().persist(attempt, pending["plan"], treatment="Treatment", script="This company grew 50 percent last year.", scenes="Scenes")
    assert changed["truth_ledger"]["status"] == "REVIEW_REQUIRED"


def test_required_voice_need_is_bound_to_frozen_script_and_provider_neutral_identity(material_integration_env):
    attempt = material_integration_env
    script = "假设冻结旁白。\n"
    plan = MaterialPlan(
        plan_id="voice-plan", creation_id=attempt["creation_id"], attempt_id=attempt["attempt_id"],
        needs=(MaterialNeed(
            need_id="voiceover", scope=NeedScope(type=NeedScopeType.GLOBAL, ref="program"),
            media_type=MediaType.AUDIO, role="voiceover", intent=NeedIntent(description="Narration"),
            importance=NeedImportance.REQUIRED,
            modality_spec=VoiceNeedSpec(identity=VoiceIdentityRef(
                source=VoiceIdentitySource.CREATOR_CONTEXT, reference="creator-voice",
            )),
        ),),
    )
    result = PlanningIntegration().persist(
        attempt, plan, treatment="# Treatment\n", script=script, scenes="# Scenes\n",
    )
    need = result["plan"].needs[0]
    assert need.modality_spec.text_ref == "planning/SCRIPT.md"
    assert need.modality_spec.text_sha256 == hashlib.sha256(script.encode()).hexdigest()
    canonical_plan = json.loads((Path(attempt["workspace"]["path"]) / "planning/MATERIAL_PLAN.json").read_text())
    assert canonical_plan["needs"][0]["modality_spec"]["text_sha256"] == need.modality_spec.text_sha256


def test_required_voice_need_without_provider_neutral_identity_is_rejected(material_integration_env):
    attempt = material_integration_env
    plan = MaterialPlan(
        plan_id="voice-plan-no-identity", creation_id=attempt["creation_id"],
        attempt_id=attempt["attempt_id"],
        needs=(MaterialNeed(
            need_id="voiceover", scope=NeedScope(type=NeedScopeType.GLOBAL, ref="program"),
            media_type=MediaType.AUDIO, role="voiceover", intent=NeedIntent(description="Narration"),
            importance=NeedImportance.REQUIRED, modality_spec=VoiceNeedSpec(),
        ),),
    )
    with pytest.raises(MaterialIntegrationError, match="provider-neutral identity"):
        PlanningIntegration().persist(
            attempt, plan, treatment="# Treatment\n", script="假设脚本内容。",
            scenes="# Scenes\n",
        )


def test_selected_audio_must_be_normalized_on_distinct_film_tracks(material_integration_env, monkeypatch):
    from easel.integrations.hypit import native_source, native_graph
    from easel.integrations.hypit.errors import HypitIntegrationError
    attempt = material_integration_env
    root = Path(attempt["workspace"]["path"])
    task_text = (root / "AUTHORING_TASK.md").read_text(encoding="utf-8")
    assert '<space:Canvas id="canvas" width="1080" height="1920"/>' in task_text
    assert "authors/recipes.svs" in task_text
    path = root / "productions/easel-authoring/authors/main.svml"
    voice_src, bgm_src = "../../../materials/assets/voice/source.wav", "../../../materials/assets/music/source.wav"
    source = f"""<?svml using="@hypit/markup@1"?>
    <svml>
    <import as="time" from="@hypit/timeline-author@1"/>
    <import as="media" from="@hypit/media@1"/>
    <import as="pipeline" from="@hypit/media-pipeline@1"/>
    <import as="audio" from="@hypit/audio-track@1"/>
    <import as="space" from="@hypit/spatial@1"/>
    <import as="film" from="@hypit/film@1"/>
    <import as="render" from="@hypit/render-hyperframes@1"/>
    <time:Clock id="clock" frame-rate="24"/>
    <time:Timeline id="program" clock={{clock}} end="5s"/>
    <space:Canvas id="canvas" width="1080" height="1920"/>
    <media:Audio id="voice" src="{voice_src}"/>
    <media:Audio id="music" src="{bgm_src}"/>
    <pipeline:Normalize id="voiceN" source={{voice}} video="none" audio="default" span-authority="audio" clock={{clock}}/>
    <pipeline:Normalize id="musicN" source={{music}} video="none" audio="default" span-authority="audio" clock={{clock}}/>
    <audio:Track id="narrationTrack" timeline={{program.timeline}}>
      <Item source={{voiceN.media}} during="program"/>
    </audio:Track>
    <audio:Track id="bgmTrack" timeline={{program.timeline}}>
      <Item source={{musicN.media}} during="program" gain="0.25" fade-in="12f" fade-out="18f"/>
    </audio:Track>
    <film:Film id="movie" canvas={{canvas}} timeline={{program.timeline}}>
      <Track source={{narrationTrack.audio}}/><Track source={{bgmTrack.audio}}/>
    </film:Film>
    <render:Video id="final" composition={{movie.composition}} timeline={{program.timeline}}/>
    </svml>
    """
    from easel.integrations.hypit.native_source import parse_text
    doc = parse_text(source, path, workspace=root, require_support=False)
    assert native_graph.audio_tracks_for_source(doc, voice_src) == {"narrationTrack"}
    assert native_graph.audio_tracks_for_source(doc, bgm_src) == {"bgmTrack"}
    # Removing a Film reference makes the declared source unadmitted; two audio
    # Needs cannot share one apparent audio track or rely on a string match.
    unplaced = source.replace('<Track source={bgmTrack.audio}/>', '')
    doc_without_music = parse_text(unplaced, path, workspace=root, require_support=False)
    with pytest.raises(HypitIntegrationError, match="Film"):
        native_graph.audio_tracks_for_source(doc_without_music, bgm_src)
    # BGM file still exists as a declaration, but its actual Normalize/Track
    # source has been diverted to the voice media: it cannot pass Need selection.
    misrouted = source.replace('<Item source={musicN.media}', '<Item source={voiceN.media}')
    doc_misrouted = parse_text(misrouted, path, workspace=root, require_support=False)
    with pytest.raises(HypitIntegrationError):
        native_graph.audio_tracks_for_source(doc_misrouted, bgm_src)


def test_int02_gate_blocks_not_ready_and_accepts_current_ready(material_integration_env):
    attempt = material_integration_env
    _planning(attempt)
    root = Path(attempt["workspace"]["path"])
    plan, asset, run, bundle, readiness, gaps = _contracts(attempt, root)
    blocked_match = MaterialMatch(need_id="need-main", asset_id=asset.asset_id, rank=1,
                                  score=0.0, reasons=("hard_filter=failed",), qualified=False)
    blocked_bundle = MaterialBundleAssembler().assemble(
        plan, run, (asset,), (blocked_match,), bundle_id="bundle-int-blocked"
    )
    blocked_run = run.model_copy(update={"result_bundle_id": blocked_bundle.bundle_id})
    blocked_readiness, blocked_gaps = MaterialReadinessCalculator(
        store=AttemptMaterialStore(root)
    ).calculate(plan, blocked_bundle)
    blocked_result = MaterialGateIntegration().record(
        attempt, plan, blocked_bundle, blocked_run, blocked_readiness, blocked_gaps
    )
    attempt.update(blocked_result["attempt"])
    with pytest.raises(HypitIntegrationError, match="MATERIAL_READY"):
        service.begin_film_authoring(attempt["attempt_id"])
    assert (root / "materials/gaps.json").is_file()
    ready = MaterialReadinessCalculator(store=AttemptMaterialStore(root)).calculate(plan, bundle)
    updated = MaterialGateIntegration().record(attempt, plan, bundle, run, *ready)
    attempt.update(updated["attempt"])
    assert updated["status"] == "MATERIAL_READY"
    with pytest.raises(HypitIntegrationError, match="素材选择"):
        service.begin_film_authoring(attempt["attempt_id"])


def test_int03_explicit_selection_precedes_authoring_and_check_evidence(material_integration_env, monkeypatch):
    attempt, root, native, cli = _native_stage(material_integration_env)
    prepared = service.get_film_attempt(attempt["attempt_id"])
    assert prepared["production_authoring"]["status"] == "PENDING_SELECTION"
    assert prepared["material_gate"]["status"] == "MATERIAL_READY"
    ready = service.complete_film_authoring(attempt["attempt_id"], cli=cli)
    assert ready["production_authoring"]["status"] == "READY"
    assert ready["authoring_status"] == "AUTHORING_READY"
    assert ready["authoring"]["check"]["ok"] is True
    assert ready["authoring"]["native_publication"]["schema"] == native.SCHEMA
    assert len(cli.calls) == 1 and not ready.get("pending_authoring_publication")
    assert service.complete_film_authoring(attempt["attempt_id"], cli=cli) == ready
    assert len(cli.calls) == 1  # no duplicate static check, Agent, or provider


def test_failed_build_retries_from_verified_checkpoints_without_supply_or_submission(
    material_integration_env, tmp_path, monkeypatch,
):
    attempt, root, native, boundary = _native_stage(material_integration_env)
    ready = service.complete_film_authoring(attempt["attempt_id"], cli=boundary)
    assert ready["authoring_status"] == "AUTHORING_READY"
    assert ready["authoring"]["native_publication"]["schema"] == native.SCHEMA

    class OfflineFailedBuild:
        def __init__(self, local):
            self.local, self.build_calls = local, 0
        def check(self, workspace, source):
            # The owner still validates the real typed candidate at the fixed Check boundary.
            from easel.integrations.hypit.native_source import parse_file, parse_run
            parse_file(workspace / native.AUTHOR, workspace=workspace)
            _, run, _ = parse_run(source, workspace=workspace)
            assert run["targets"] == [{"output": "final.video"}]
            return {"format": "hypit.cli-check@1", "ok": True, "sourceKind": "run",
                    "run": native.RUN, "author": native.AUTHOR,
                    "frontend": "@hypit/run-markup@1", "targetCount": 1,
                    "targets": ["final.video"], "candidates": 0,
                    "satisfactions": 0, "historicalOutputCount": 0}
        def plan(self, *_args, **_kwargs):
            return {"format": "hypit.cli-plan@1", "ok": True}
        def pricing(self, *_args, **_kwargs):
            return {"format": "hypit.cli-pricing@1", "requestCount": 1, "groups": []}
        def build(self, *_args, **_kwargs):
            self.build_calls += 1
            return {"format": "hypit.cli-build@1",
                    "build": {"id": "bld_native_retry_001", "work": {"outcome": "failed"}}}
        def status(self, _workspace, build_id, **kwargs):
            return {"format": "hypit.cli-status@1",
                    "build": {"id": build_id, "work": {"outcome": "failed"}}}

    cli = OfflineFailedBuild(boundary)
    runtime = tmp_path / "offline-native-runtime.json"
    runtime.write_text(json.dumps({
        "format": "hypit.runtime-local@1", "dataRoot": ".offline-native-runtime",
        "credentials": {}, "endpoints": {}, "bindings": {},
    }) + "\n")
    service.resolve_film_attempt_runtime(attempt["attempt_id"], str(runtime))
    service.validate_film_attempt(attempt["attempt_id"], native.RUN, cli=cli)
    service.estimate_film_attempt(attempt["attempt_id"], cli=cli)
    service.approve_film_cost(attempt["attempt_id"], 1)
    failed = service.submit_film_build(attempt["attempt_id"], title="offline native build failure", cli=cli)
    assert failed["execution_status"] == "BUILD_FAILED" and cli.build_calls == 1
    child = service.retry_failed_film_build(attempt["attempt_id"], cli=cli)
    assert child["attempt_id"] != failed["attempt_id"]
    assert child["retry_source"]["attempt_id"] == failed["attempt_id"]
    assert child["retry_source"]["status"] == "READY"
    assert child["handoff"] == failed["handoff"] and child["result_protocols"] == failed["result_protocols"]
    assert child["cost"]["approved"] is False and child["execution_status"] == "NOT_SUBMITTED"
    assert cli.build_calls == 1 and not child.get("build", {}).get("build_id")
    MaterialGateIntegration().assert_ready(child)  # Frozen Need/Rights bytes remain admitted.
    assert service.retry_failed_film_build(attempt["attempt_id"], cli=cli)["attempt_id"] == child["attempt_id"]
    assert cli.build_calls == 1


def test_int04_workspace_asset_uses_ordinary_hypit_media_route(material_integration_env):
    attempt, root, native, cli = _native_stage(material_integration_env)
    selection = json.loads((root / native.SELECTION).read_bytes())
    src = selection["assets"][0]["src"]
    assert not src.startswith("/") and "Candidate" not in src and "satisfy" not in src
    from easel.integrations.hypit.native_source import parse_file
    document = parse_file(root / native.AUTHOR, workspace=root)
    assert {node.literal("src") for node in document.find("@hypit/media", "Image")} == {src}
    ready = service.complete_film_authoring(attempt["attempt_id"], cli=cli)
    assert ready["authoring_status"] == "AUTHORING_READY"
    assert len(cli.calls) == 1


def test_product_orchestrator_runs_local_supply_before_authoring(material_integration_env, tmp_path, monkeypatch):
    attempt = material_integration_env
    local_root = tmp_path / "local-materials"
    local_root.mkdir()
    Image.new("RGB", (720, 1280), (32, 48, 64)).save(local_root / "portrait.jpg")
    registry = material_supply_module.ProviderRegistry()
    registry.register(LocalProvider((local_root,)))
    monkeypatch.setattr(
        material_supply_module, "product_provider_registry", lambda _roots: (registry, ()),
    )
    plan = MaterialPlan(
        plan_id="plan-product-local", creation_id=attempt["creation_id"], attempt_id=attempt["attempt_id"],
        needs=(MaterialNeed(
            need_id="need-local", scope=NeedScope(type=NeedScopeType.SCENE, ref="scene-1"),
            media_type=MediaType.IMAGE, role="主视觉", intent=NeedIntent(description="竖屏人物肖像"),
            importance=NeedImportance.REQUIRED,
        ),),
    )
    planning = {"plan": plan, "context_refs": {}, "treatment": "T", "script": "假设脚本内容。", "scenes": "C"}
    result = MaterialProductOrchestrator().run_with_planning(attempt, (local_root,), planning)
    trace = json.loads((Path(attempt["workspace"]["path"]) / "materials/product-supply.json").read_text())
    assert trace["routing"][0]["library_search_called"] is True
    assert trace["routing"][0]["semantic_search_called"] is True
    assert trace["routing"][0]["reuse_candidates"] == 0
    assert trace["routing"][0]["attempted_sources"] == ["local"]
    assert result["status"] == "MATERIAL_NOT_READY"
    assert result["attempt"]["material_planning"]["status"] == "PLANNING_READY"
    assert result["attempt"]["material_gate"]["status"] == "MATERIAL_NOT_READY"
    assert "production_authoring" not in result["attempt"]
    assert result["supply"].bundle.assets
    assert all(asset.rights.status is RightsStatus.UNKNOWN for asset in result["supply"].bundle.assets)
    local_file = local_root / "portrait.jpg"
    source_digest = hashlib.sha256(local_file.read_bytes()).hexdigest()
    (local_root / "portrait.jpg.rights.json").write_text(json.dumps({
        "schema": "easel-local-rights@1", "asset_sha256": source_digest,
        "rights": {
            "status": "KNOWN", "license_name": "Reviewed fixture license",
            "evidence": [{"kind": "asset_license", "reference": "https://rights.example/portrait",
                          "summary": "Explicit per-asset license evidence for the fixture."}],
        },
    }), encoding="utf-8")
    candidate = LocalProvider((local_root,)).search(NeedCompiler().compile(plan.needs[0])).candidates[0]
    assert MaterialProductOrchestrator._local_rights_facts(
        candidate, result["supply"].bundle.assets[0], (local_root,),
    ).status is RightsStatus.KNOWN
    evidenced = MaterialProductOrchestrator().run_with_planning(attempt, (local_root,), planning)
    assert evidenced["status"] == "MATERIAL_NOT_READY", (
        evidenced["gate"]["readiness"].blocking_reasons,
        [match.model_dump() for match in evidenced["supply"].bundle.matches],
        [asset.rights.model_dump() for asset in evidenced["supply"].bundle.assets],
        [(item.status, item.failure_summary) for item in evidenced["supply"].supply_run.provider_results],
    )
    assert any(asset.rights.status is RightsStatus.KNOWN for asset in evidenced["supply"].bundle.assets)
    assert {asset.asset_id for asset in result["supply"].bundle.assets}.issubset(
        {asset.asset_id for asset in evidenced["supply"].bundle.assets})
    assert "production_authoring" not in evidenced["attempt"]
    assert (Path(attempt["workspace"]["path"]) / "materials/bundle.json").is_file()
    visual = next(asset for asset in evidenced["supply"].bundle.assets
                  if asset.rights.status is RightsStatus.KNOWN)
    reviewed = MaterialProductOrchestrator().review_material_match(
        attempt["attempt_id"], asset_id=visual.asset_id,
        expected_sha256=visual.file.sha256, need_id="need-local",
        observed_content="画面是一张竖屏人物肖像，主体和场景清楚",
        logo_present=None, visible_text_present=None, confirm_review=True,
    )
    assert reviewed["material_status"] == "MATERIAL_READY"
    assert reviewed["attempt"]["production_authoring"]["status"] == "PENDING_SELECTION"


def test_no_supply_cannot_bypass_gate(material_integration_env, monkeypatch):
    attempt = material_integration_env
    monkeypatch.setattr(
        material_supply_module, "product_provider_registry",
        lambda _roots: (material_supply_module.ProviderRegistry(), ()),
    )
    plan = MaterialPlan(
        plan_id="plan-no-supply", creation_id=attempt["creation_id"], attempt_id=attempt["attempt_id"],
        needs=(MaterialNeed(
            need_id="required-video", scope=NeedScope(type=NeedScopeType.SCENE, ref="scene-1"),
            media_type=MediaType.VIDEO, role="主镜头", intent=NeedIntent(description="河边行走视频"),
            importance=NeedImportance.REQUIRED,
        ),),
    )
    result = MaterialProductOrchestrator().run_with_planning(
        attempt, (), {"plan": plan, "context_refs": {}, "treatment": "T", "script": "假设脚本内容。", "scenes": "C"},
    )
    assert result["status"] == "MATERIAL_NOT_READY"
    assert result["attempt"]["material_gate"]["status"] == "MATERIAL_NOT_READY"
    assert "production_authoring" not in result["attempt"]


def test_supplement_reuses_completed_source_and_does_not_reacquire_known_candidate(
        material_integration_env, tmp_path, monkeypatch):
    from dataclasses import replace
    from easel.materials.application.acquisition import MaterialAcquirer
    from easel.materials.application.library_first import LibraryFirstSupplyService, ExternalSupplyFailure
    attempt = material_integration_env
    plan = _planning(attempt)['plan']
    store = AttemptMaterialStore(attempt['workspace']['path'])
    local = tmp_path / 'supply'
    local.mkdir()
    Image.new('RGB', (32, 32), 'blue').save(local / 'candidate.png')
    provider = LocalProvider((local,))
    registry = material_supply_module.ProviderRegistry()
    registry.register(provider)
    searches, acquisitions = [], []
    unavailable = True
    search, acquire = LocalProvider.search, MaterialAcquirer.acquire
    def counted_search(self, *a, **kw):
        from easel.materials.providers.errors import ProviderTemporaryError
        searches.append(1)
        if unavailable:
            raise ProviderTemporaryError('local', 'fixture temporary outage')
        return search(self, *a, **kw)
    def counted_acquire(self, candidate):
        acquisitions.append(candidate.source.provider_asset_id)
        return acquire(self, candidate)
    monkeypatch.setattr(LocalProvider, 'search', counted_search)
    monkeypatch.setattr(MaterialAcquirer, 'acquire', counted_acquire)
    supply_need = LibraryFirstSupplyService.supply_need
    def partial_route(self, *a, **kw):
        result = supply_need(self, *a, **kw)
        # Another route failing must not suppress new usable candidates or
        # prevent system observation of the successful route's actual media.
        return replace(result, failures=result.failures + (ExternalSupplyFailure('other', 'fixture outage'),)) if result.external_assets else result
    monkeypatch.setattr(LibraryFirstSupplyService, 'supply_need', partial_route)
    write_bundle = AttemptMaterialStore.write_bundle
    interrupted = False
    def interrupt_after_source(self, bundle):
        nonlocal interrupted
        if bundle.supply_run_id == 'supplement-fixture' and not interrupted:
            interrupted = True
            raise OSError('source complete; bundle not yet committed')
        return write_bundle(self, bundle)
    monkeypatch.setattr(AttemptMaterialStore, 'write_bundle', interrupt_after_source)
    supplier = material_supply_module.ProductMaterialSupply(registry=registry)
    args = {'local_roots': (local,), 'supply_run_id': 'supplement-fixture', 'bundle_id': 'fixture-bundle'}
    with pytest.raises(RuntimeError, match='素材来源请求未完成'):
        supplier.run(plan, attempt, **args)
    unavailable = False
    failed_searches = len(searches)
    assert failed_searches > 0 and not acquisitions
    with pytest.raises(OSError, match='source complete'):
        supplier.run(plan, attempt, **args)
    result = supplier.run(plan, attempt, **args)
    assert len(searches) == failed_searches + 1 and len(acquisitions) == 1
    attempt = MaterialGateIntegration().record(attempt, plan, result.bundle, result.supply_run,
                                               result.readiness, result.gaps)['attempt']
    repeated_candidate = supplier.run(plan, attempt, **{**args, 'supply_run_id': 'supplement-next'})
    assert len(searches) == failed_searches + 1 and len(acquisitions) == 1
    assert repeated_candidate.bundle.assets == result.bundle.assets == store.read_bundle().assets


def test_product_supply_records_need_gated_generation_without_hypit_request(
    material_integration_env, monkeypatch,
):
    attempt = material_integration_env
    registry = material_supply_module.ProviderRegistry()
    monkeypatch.setattr(
        material_supply_module, "product_provider_registry", lambda _roots: (registry, ()),
    )
    plan = MaterialPlan(
        plan_id="plan-generation-route", creation_id=attempt["creation_id"], attempt_id=attempt["attempt_id"],
        needs=(MaterialNeed(
            need_id="need-generated", scope=NeedScope(type=NeedScopeType.SCENE, ref="scene-1"),
            media_type=MediaType.IMAGE, role="illustration",
            intent=NeedIntent(description="a conceptual city illustration"),
            constraints={"allow_generation": True}, importance=NeedImportance.REQUIRED,
        ),),
    )
    result = MaterialProductOrchestrator().run_with_planning(
        attempt, (), {"plan": plan, "context_refs": {}, "treatment": "T", "script": "假设脚本内容。", "scenes": "C"},
    )
    trace = json.loads((Path(attempt["workspace"]["path"]) / "materials/product-supply.json").read_text())
    assert result["status"] == "MATERIAL_NOT_READY"
    assert result["supply"].generation_preparation["status"] == "MATERIAL_GENERATION_AVAILABLE"
    assert trace["routing"][0]["routes"][-1]["kind"] == "GENERATIVE"
    assert trace["generation_preparation"]["need_id"] == "need-generated"
    assert "production_authoring" not in result["attempt"]
    assert "material_generation_request" not in result["attempt"]
    generation_runs = Path(attempt["workspace"]["path"]) / "materials/generation-runs"
    assert not list(generation_runs.glob("*/result.json"))


def test_product_supply_rehydrates_current_completed_generation_after_rights_review(
    material_integration_env,
):
    attempt = material_integration_env
    root = Path(attempt["workspace"]["path"])
    store = AttemptMaterialStore(root)
    plan = MaterialPlan(
        plan_id="plan-persisted-generation", creation_id=attempt["creation_id"],
        attempt_id=attempt["attempt_id"], needs=(MaterialNeed(
            need_id="need-generated-image", scope=NeedScope(type=NeedScopeType.SCENE, ref="scene-1"),
            media_type=MediaType.IMAGE, role="主视觉", intent=NeedIntent(description="一张测试图片"),
            constraints={"allow_generation": True}, importance=NeedImportance.REQUIRED,
        ),),
    )
    payload = b"deterministic generated image fixture"
    digest = hashlib.sha256(payload).hexdigest()
    locator = store.write_asset_bytes("asset-persisted-generation", "original.png", payload)
    asset = MaterialAsset(
        asset_id="asset-persisted-generation", media_type=MediaType.IMAGE,
        file=FileInfo(path=locator, sha256=digest, size=len(payload), mime="image/png"),
        source=CandidateSource(kind="generative", provider="minimax", provider_asset_id="gen-test"),
        rights=RightsInfo(status=RightsStatus.UNKNOWN),
        technical=TechnicalInfo(status=TechnicalStatus.PASSED, width=100, height=100, mime="image/png"),
        semantic=_observed_semantic("一张测试图片"),
    )
    store.write_asset(asset)
    store.write_generation_record("gen-test", {
        "schema": "easel-material-generation@1", "generation_id": "gen-test",
        "attempt_id": attempt["attempt_id"], "plan_id": plan.plan_id,
        "plan_revision": MaterialReadinessCalculator.plan_revision(plan),
        "need_id": "need-generated-image", "status": "COMPLETE",
        "asset_id": asset.asset_id, "asset_path": locator,
        "asset_sha256": digest, "asset_bytes": len(payload),
    })
    registry = material_supply_module.ProviderRegistry()
    supply = material_supply_module.ProductMaterialSupply(registry=registry)

    first = supply.run(plan, attempt, local_roots=(), supply_run_id="supply-generated-unknown",
                       bundle_id="bundle-generated-unknown")
    assert [item.asset_id for item in first.bundle.assets] == [asset.asset_id]
    assert first.readiness.status.value == "NOT_READY"

    reviewed = RightsService(store).record(asset, RightsInfo(
        status=RightsStatus.KNOWN, license_name="已核验的生成素材使用条款",
        evidence=(RightsEvidence(kind="asset_license", reference="fixture://reviewed-terms"),),
    ))
    assert reviewed.rights.status is RightsStatus.KNOWN
    second = supply.run(plan, attempt, local_roots=(), supply_run_id="supply-generated-reviewed",
                        bundle_id="bundle-generated-reviewed")
    assert [item.asset_id for item in second.bundle.assets] == [asset.asset_id]
    assert second.readiness.status.value == "READY"
    stale_need = plan.needs[0].model_copy(update={
        "intent": NeedIntent(description="与原生成请求不同的新素材意图"),
    })
    stale_plan = plan.model_copy(update={"needs": (stale_need,)})
    stale = supply.run(stale_plan, attempt, local_roots=(), supply_run_id="supply-generated-stale",
                       bundle_id="bundle-generated-stale")
    assert asset.asset_id not in {item.asset_id for item in stale.bundle.assets}


def test_frozen_mode_style_reaches_provider_and_library_without_rewriting_content(
    material_integration_env, tmp_path, monkeypatch,
):
    from io import BytesIO
    import base64
    from easel.materials.domain import ImageNeedSpec
    old = material_integration_env
    actual_mode = json.loads((Path(__file__).resolve().parents[1]
                              / "creative_modes/clear_memo_video/mode.json").read_text())
    mode_path = creative_mode.CREATIVE_MODES_DIR / "clear_memo_video/mode.json"
    mode_path.write_text(json.dumps(actual_mode))
    work = creation.create_creation("观察夜间公交等待", profile="测试", creative_mode="clear_memo_video")
    previous = Path(old["workspace"]["path"]) / "handoff"
    package = service.create_creation_handoff(work["id"],
        content_core={"schema": "content-core@1", "question": work["idea"]},
        truth_packet=json.loads((previous / "truth-packet.json").read_text()),
        creator_context=json.loads((previous / "creator-context.json").read_text()),
        production_request={"media_type": "video", "orientation": "9:16", "language": "zh-CN"},
        max_budget_usd=5)
    attempt = service.create_film_attempt(work["id"], package["handoff_id"],
                                         preparation_key="c" * 64, runtime_status="NOT_CONFIGURED")
    mode, mode_hash = handoff.load_frozen_creative_mode(attempt)
    assert handoff.load_frozen_creative_mode(old)[0].get("visual_material_style") is None
    style = mode["visual_material_style"]
    plan = MaterialPlan(plan_id="plan-style", creation_id=work["id"], attempt_id=attempt["attempt_id"],
        context_refs={"creative_mode_sha256": mode_hash}, needs=(
            MaterialNeed(need_id="scene-bus", scope=NeedScope(type=NeedScopeType.SCENE, ref="bus"),
                         media_type=MediaType.IMAGE, role="主视觉", intent=NeedIntent(description="night bus stop"),
                         importance=NeedImportance.REQUIRED),
            MaterialNeed(need_id="scene-clock", scope=NeedScope(type=NeedScopeType.SCENE, ref="clock"),
                         media_type=MediaType.IMAGE, role="局部对照", intent=NeedIntent(description="station clock"),
                         constraints={"preferred_style": "high contrast documentary",
                                      "preferred_visual_details": "wide shot or a readable clock close-up"},
                         importance=NeedImportance.REQUIRED),
            MaterialNeed(need_id="scene-walk", scope=NeedScope(type=NeedScopeType.SCENE, ref="walk"),
                         media_type=MediaType.VIDEO, role="主视觉", intent=NeedIntent(description="walk beside the station"),
                         importance=NeedImportance.REQUIRED),
            MaterialNeed(need_id="scene-sign", scope=NeedScope(type=NeedScopeType.SCENE, ref="sign"),
                         media_type=MediaType.IMAGE, role="局部", intent=NeedIntent(description="station sign"),
                         modality_spec=ImageNeedSpec(visual_style='quiet monochrome'), importance=NeedImportance.REQUIRED),
        ))
    original = plan.model_dump()
    planning = PlanningIntegration().persist(attempt, plan, treatment="两个具体观察，保留高对比时钟镜头。",
                                              script="假设站在夜班公交站。", scenes="公交站与时钟。")
    assert plan.model_dump() == original
    bound = planning["plan"]
    assert bound.needs[0].constraints["preferred_style"] == style
    assert bound.needs[1].constraints["preferred_style"] == "high contrast documentary"
    assert bound.needs[2].constraints['preferred_style'] == style
    assert bound.needs[3].constraints['preferred_style'] == 'quiet monochrome'
    assert [need.intent for need in bound.needs] == [need.intent for need in plan.needs]
    # A later package edit never changes an already frozen production input.
    mode_path.write_text(json.dumps({**actual_mode, "visual_material_style": "unrelated glossy style"}))
    assert handoff.load_frozen_creative_mode(attempt)[0]["visual_material_style"] == style
    with pytest.raises(HypitIntegrationError, match="风格来源"):
        PlanningIntegration().persist(attempt, plan.model_copy(update={"context_refs": {}}),
                                      treatment="同一规划", script="假设站在夜班公交站。", scenes="同一场景")

    empty_root = tmp_path / "empty-local"
    empty_root.mkdir()
    provider = LocalProvider((empty_root,))
    search = provider.search
    requests = []

    def observed_search(intent, continuation=None):
        requests.append(intent)
        return search(intent, continuation)

    monkeypatch.setattr(provider, "search", observed_search)
    registry = material_supply_module.ProviderRegistry()
    registry.register(provider)
    preferences = []
    native_match = material_supply_module.AdvancedMaterialMatcher.match

    def observed_match(self, need, *args, **kwargs):
        preferences.append((need.need_id, kwargs["director_preferences"]))
        return native_match(self, need, *args, **kwargs)

    monkeypatch.setattr(material_supply_module.AdvancedMaterialMatcher, "match", observed_match)
    supply = material_supply_module.ProductMaterialSupply(registry=registry, library_root=tmp_path / "library")
    result = supply.run(bound, planning["attempt"], local_roots=(empty_root,), supply_run_id="style-supply",
                        bundle_id="style-bundle", search_terms={"scene-bus": ("bus stop", "bus", "station", "road")})
    assert result.readiness.status.value == "NOT_READY"  # preferences aren't observation or Rights evidence
    assert len(requests) == 4, [(row.get("failures"), row.get("skipped")) for row in result.routing_trace]
    assert "bus stop " + style in requests[0].semantic_queries
    assert requests[0].semantic_queries[0] == "bus stop"
    assert requests[1].semantic_queries[0] == "station clock"
    assert "station clock high contrast documentary" in requests[1].semantic_queries
    assert 'preferred_visual_details' not in requests[1].filters
    assert requests[1].ranking_hints['preferred_visual_details'] == bound.needs[1].constraints['preferred_visual_details']
    assert preferences[0][1][0].preferred_values == (style,)
    assert preferences[1][1][0].preferred_values == ("high contrast documentary",)
    # Exercise the real image/video HTTP adapters with deterministic transport.
    # Style must reach the actual generation request, not only retrieval metadata.
    from easel.materials.application.generation import MiniMaxVideoMaterialGeneration, GenerationRequestConflict
    from easel.materials.application.generation_modalities import MiniMaxImageSpeechGeneration
    from easel.materials.providers.minimax_video import MiniMaxVideoAdapter, MiniMaxVideoObservationPending
    from easel.materials.providers.minimax_image import MiniMaxImageAdapter
    from easel.materials.providers.http_support import HttpResponse
    image = BytesIO()
    Image.new('RGB', (64, 64), 'teal').save(image, format='PNG')
    generation_requests = []
    class Transport:
        def post(self, url, *, body, **kwargs):
            payload = json.loads(body)
            generation_requests.append(payload)
            result = ({'task_id': 'fixture-style-video'} if 'content' in payload else
                      {'data': {'image_base64': [base64.b64encode(image.getvalue()).decode()]}})
            return HttpResponse(200, {}, json.dumps(result).encode())
        def get(self, *args, **kwargs):
            raise TimeoutError('fixture ends at observed generation request; no live video')
    store = AttemptMaterialStore(attempt['workspace']['path'])
    transport = Transport()
    for need in bound.needs:
        request_id = 'style-' + need.need_id
        if need.media_type is MediaType.IMAGE:
            engine = MiniMaxImageSpeechGeneration(image_adapter=MiniMaxImageAdapter('fixture-key', transport=transport))
            first = engine.generate(bound, need, store, request_id=request_id, confirmed_paid=True)
            assert first.asset.rights.status is RightsStatus.UNKNOWN
            engine.generate(bound, need, store, request_id=request_id, confirmed_paid=True)
            prompt = generation_requests[-1]['prompt']
        else:
            engine = MiniMaxVideoMaterialGeneration(MiniMaxVideoAdapter('fixture-key', transport=transport))
            for _ in range(2):
                with pytest.raises(MiniMaxVideoObservationPending):
                    engine.generate(bound, need, store, request_id=request_id, confirmed_paid=True)
            prompt = generation_requests[-1]['content'][0]['text']
        expected_prompt = need.intent.description + '\nVisual style: ' + need.constraints['preferred_style']
        if need.constraints.get('preferred_visual_details'):
            expected_prompt += '\nOptional visual preferences (preserve the core subject): ' + need.constraints['preferred_visual_details']
        assert prompt == expected_prompt
        record = store.read_generation_record('gen-' + request_id)
        assert record.get('prompt_sha256', record.get('input_sha256')) == hashlib.sha256(prompt.encode()).hexdigest()
        changed = need.model_copy(update={'constraints': {**need.constraints, 'preferred_style': 'unrelated glossy style'}})
        changed_plan = bound.model_copy(update={'needs': tuple(changed if n.need_id == need.need_id else n for n in bound.needs)})
        with pytest.raises(GenerationRequestConflict):
            engine.generate(changed_plan, changed, store, request_id=request_id, confirmed_paid=True)
    assert len(generation_requests) == 4  # Resume and changed input cannot buy again.
    assert handoff.load_frozen_creative_mode(old)[0].get("voice_delivery") is None
    voice = MaterialNeed(need_id="narration", scope=NeedScope(type=NeedScopeType.GLOBAL, ref="program"),
        media_type=MediaType.AUDIO, role="旁白", intent=NeedIntent(description="平静的事后观察"),
        modality_spec=VoiceNeedSpec(identity=VoiceIdentityRef(source=VoiceIdentitySource.DIRECTOR_INTENT,
            reference="已批准的预置声音"), delivery_description="自然平静，稍加快以保持短句的连贯性"),
        constraints={"voice_delivery": {"pace_ratio": 1.05}}, importance=NeedImportance.REQUIRED)
    voice_plan = plan.model_copy(update={"needs": (voice,)})
    aliased_voice = voice.model_copy(update={'constraints': {'voice_tone': 'neutral'}})
    with pytest.raises(MaterialIntegrationError, match='constraints.voice_tone'):
        PlanningIntegration().persist(attempt, voice_plan.model_copy(update={'needs': (aliased_voice,)}),
                                      treatment='自然讲述', script='隔离无效输入', scenes='站台观察')
    persisted_voice = PlanningIntegration().persist(attempt, voice_plan, treatment="自然讲述",
                                                   script="假设站在夜班公交站。", scenes="站台观察")
    assert persisted_voice["plan"].needs[0].constraints["voice_delivery"] == {
        "pace_ratio": 1.05, "pitch_semitones": 0, "tone": "neutral"}
    assert "preferred_style" not in persisted_voice["plan"].needs[0].constraints
    assert persisted_voice["plan"].needs[0].modality_spec.text_sha256 == hashlib.sha256("假设站在夜班公交站。".encode()).hexdigest()
    voice_before = persisted_voice["plan"].to_json()
    voice_result = supply.run(persisted_voice["plan"], persisted_voice["attempt"],
        local_roots=(empty_root,), supply_run_id="voice-style-supply", bundle_id="voice-style-bundle")
    assert not voice_result.routing_trace[0]["failures"]
    assert all(request.need_id != 'narration' for request in requests)  # Script instructions aren't stock audio queries.
    assert voice_result.routing_trace[0]['attempted_sources'] == []
    assert persisted_voice["plan"].to_json() == voice_before
    assert voice_result.readiness.status.value == "NOT_READY"


def test_generation_preserves_bundle_then_rights_review_opens_production_gate(
    material_integration_env, monkeypatch,
):
    from easel.runtime_config import EaselRuntimeConfig

    attempt = material_integration_env
    root = Path(attempt["workspace"]["path"])
    plan = MaterialPlan(
        plan_id="plan-operator-rights", creation_id=attempt["creation_id"],
        attempt_id=attempt["attempt_id"], needs=(MaterialNeed(
            need_id="need-generated-review", scope=NeedScope(type=NeedScopeType.SCENE, ref="scene-1"),
            media_type=MediaType.IMAGE, role="主视觉", intent=NeedIntent(description="一张生成测试图片"),
            constraints={"allow_generation": True}, importance=NeedImportance.REQUIRED,
        ),),
    )
    planning = PlanningIntegration().persist(
        attempt, plan, treatment="# Treatment\n", script="假设脚本内容。\n", scenes="# Scenes\n",
    )
    attempt.update(planning["attempt"])
    planning = PlanningIntegration().review_script(
        attempt, confirm_all_claims_reviewed=True,
        expected_script_sha256=planning["truth_ledger"]["script_sha256"],
        expected_truth_packet_sha256=planning["truth_ledger"]["truth_packet_sha256"],
    )
    attempt.update(planning["attempt"])

    store = AttemptMaterialStore(root)
    payload = b"operator rights review deterministic image"
    digest = hashlib.sha256(payload).hexdigest()
    locator = store.write_asset_bytes("asset-operator-rights", "original.png", payload)
    asset = MaterialAsset(
        asset_id="asset-operator-rights", media_type=MediaType.IMAGE,
        file=FileInfo(path=locator, sha256=digest, size=len(payload), mime="image/png"),
        source=CandidateSource(kind="generative", provider="minimax", provider_asset_id="gen-rights"),
        rights=RightsInfo(status=RightsStatus.UNKNOWN),
        technical=TechnicalInfo(status=TechnicalStatus.PASSED, width=64, height=64, mime="image/png"),
        semantic=_observed_semantic("一张生成测试图片"),
    )
    store.write_asset(asset)
    store.write_generation_record("gen-rights", {
        "schema": "easel-material-generation@1", "generation_id": "gen-rights",
        "attempt_id": attempt["attempt_id"], "plan_id": plan.plan_id,
        "plan_revision": MaterialReadinessCalculator.plan_revision(plan),
        "need_id": "need-generated-review", "status": "COMPLETE",
        "asset_id": asset.asset_id, "asset_path": locator,
        "asset_sha256": digest, "asset_bytes": len(payload),
    })
    monkeypatch.setattr(
        material_supply_module, "product_provider_registry",
        lambda _roots: (material_supply_module.ProviderRegistry(), ()),
    )
    monkeypatch.setattr(EaselRuntimeConfig, "material_roots", lambda _self: ())

    orchestrator = MaterialProductOrchestrator()
    blocked = orchestrator._run(attempt, (), planning=PlanningIntegration().load(attempt))
    assert blocked["status"] == "MATERIAL_NOT_READY"
    assert [item["asset_id"] for item in orchestrator.generated_material_rights_candidates(attempt["attempt_id"])] == [asset.asset_id]

    with pytest.raises(MaterialIntegrationError, match="SHA-256 已变化"):
        orchestrator.review_generated_material_rights(
            attempt["attempt_id"], asset_id=asset.asset_id, expected_sha256="0" * 64,
            rights=RightsInfo(status=RightsStatus.KNOWN,
                              evidence=(RightsEvidence(kind="asset_license", reference="fixture://terms"),)),
            confirm_review=True,
        )

    def no_provider_lookup(_roots):
        raise AssertionError("Generation and Rights review must reuse the admitted Bundle without Supply")

    monkeypatch.setattr(material_supply_module, "product_provider_registry", no_provider_lookup)
    from types import SimpleNamespace
    from easel.integrations import material_layer

    before = store.read_bundle()
    request_id = "fixture-second-generation"
    generation_id = "gen-" + request_id
    added = asset.model_copy(update={
        "asset_id": "asset-" + hashlib.sha256(request_id.encode()).hexdigest()[:32],
        "source": asset.source.model_copy(update={"provider_asset_id": generation_id}),
    })
    added_locator = store.write_asset_bytes(added.asset_id, "original.png", payload)
    added = added.model_copy(update={"file": added.file.model_copy(update={"path": added_locator})})

    calls = []
    def generate_fixture(_self, frozen_plan, need, local_store, **_kwargs):
        calls.append('provider-result')
        local_store.write_generation_record(generation_id, {
            'schema': 'easel-material-generation@1', 'generation_id': generation_id,
            'attempt_id': frozen_plan.attempt_id, 'plan_id': frozen_plan.plan_id,
            'plan_revision': MaterialReadinessCalculator.plan_revision(frozen_plan),
            'need_id': need.need_id, 'need_sha256': hashlib.sha256(need.to_json().encode()).hexdigest(),
            'provider': 'minimax', 'modality': 'image', 'model': 'image-01',
            'status': 'RESULT_RECEIVED', 'received_asset': added.model_copy(update={
                'technical': TechnicalInfo(status=TechnicalStatus.PENDING)}).model_dump(mode='json'),
            'billing': {'status': 'UNKNOWN'}, 'operator_confirmed_paid': True,
        })
        raise OSError('fixture restart after receipt')

    with monkeypatch.context() as generation_patch:
        generation_patch.setattr(EaselRuntimeConfig, "load", lambda: SimpleNamespace(
            minimax=SimpleNamespace(api_key="fixture-key", image_model="image-01", base_url="https://api.minimax.cn"),
        ))
        generation_patch.setattr(material_layer.MiniMaxImageSpeechGeneration, "generate", generate_fixture)
        with pytest.raises(OSError, match='after receipt'):
            orchestrator.generate_minimax_asset(
                attempt["attempt_id"], need_id=plan.needs[0].need_id,
                request_id=request_id, confirmed_paid=True,
            )
    from easel.creation_delivery import next_operation, SCHEMA
    from easel.integrations.hypit.service import get_film_attempt
    from easel.materials.application import generation_modalities
    from easel.materials.application.generation_modalities import recoverable_generation_records

    def state():
        proposal = 'fixture approved'
        digest = hashlib.sha256(proposal.encode()).hexdigest()
        return {'chat_workflow': {'proposal_status': 'CONFIRMED', 'proposal_sha256': digest},
                'delivery': {'schema': SCHEMA, 'proposal': proposal, 'proposal_sha256': digest},
                'hypit_attempts': [get_film_attempt(attempt['attempt_id'])]}

    assert next_operation(state()) == ('finish_material_generation', 'recovering_material')
    frozen = store.read_plan()
    assert not recoverable_generation_records(frozen.model_copy(update={'plan_id': 'other'}), before, store)
    class LocalInspector:
        def __init__(self, local_store):
            self.store = local_store
        def inspect_and_persist(self, asset):
            calls.append('local-inspection')
            self.store.write_asset(added)
            return added
    def no_credentials():
        raise AssertionError('Local receipt recovery cannot load Provider credentials')
    with monkeypatch.context() as recovery_patch:
        recovery_patch.setattr(EaselRuntimeConfig, 'load', no_credentials)
        recovery_patch.setattr(generation_modalities, 'TechnicalInspector', LocalInspector)
        native_update = material_layer._update_attempt
        def lost_gate_write(*args, **kwargs):
            raise OSError('fixture interruption after Bundle commit')
        recovery_patch.setattr(material_layer, '_update_attempt', lost_gate_write)
        with pytest.raises(OSError, match='after Bundle commit'):
            orchestrator.resume_minimax_intake(attempt['attempt_id'])
        assert store.read_generation_record(generation_id)['status'] == 'COMPLETE'
        assert next_operation(state()) == ('finish_material_generation', 'recovering_material')
        recovery_patch.setattr(material_layer, '_update_attempt', native_update)
        result = orchestrator.resume_minimax_intake(attempt['attempt_id'])
    assert calls == ['provider-result', 'local-inspection']
    assert next_operation(state())[0] != 'finish_material_generation'
    after = store.read_bundle()
    assert after.bundle_id == before.bundle_id
    assert {item.asset_id for item in after.assets} == {asset.asset_id, added.asset_id}
    assert next(item for item in after.assets if item.asset_id == asset.asset_id) == asset
    assert store.read_supply_run(after.supply_run_id).parent_run_id == before.supply_run_id
    assert result["material_gate"]["status"] == "MATERIAL_NOT_READY"
    assert len(orchestrator.material_rights_candidates(attempt["attempt_id"])) == 2

    reviewed = orchestrator.review_generated_material_rights(
        attempt["attempt_id"], asset_id=asset.asset_id, expected_sha256=digest,
        rights=RightsInfo(
            status=RightsStatus.KNOWN, license_name="Fixture terms",
            evidence=(RightsEvidence(kind="asset_license", reference="fixture://terms",
                                     summary="Asset-bound fixture evidence reviewed by operator"),),
        ),
        confirm_review=True,
        source_creator="Fixture Creator",
        source_page="https://fixture.example/generated-asset",
    )
    assert reviewed["material_status"] == "MATERIAL_READY"
    assert reviewed["material_gate"]["status"] == "MATERIAL_READY"
    assert reviewed["production_authoring"]["status"] == "PENDING_SELECTION"
    persisted = AttemptMaterialStore(root).read_bundle()
    reviewed_asset = next(a for a in persisted.assets if a.asset_id == asset.asset_id)
    assert reviewed_asset.rights.status is RightsStatus.KNOWN
    assert reviewed_asset.source.creator == "Fixture Creator"
    assert reviewed_asset.source.source_page == "https://fixture.example/generated-asset"


def test_current_bundle_rights_review_admits_external_asset_without_repeating_supply(
    material_integration_env, monkeypatch,
):
    attempt = material_integration_env
    root = Path(attempt["workspace"]["path"])
    plan = MaterialPlan(
        plan_id="plan-external-rights-review", creation_id=attempt["creation_id"],
        attempt_id=attempt["attempt_id"], needs=(MaterialNeed(
            need_id="need-external-review", scope=NeedScope(type=NeedScopeType.SCENE, ref="scene-1"),
            media_type=MediaType.IMAGE, role="主视觉", intent=NeedIntent(description="一个可用于剪辑的主视觉素材"),
            importance=NeedImportance.REQUIRED,
        ),),
    )
    planning = PlanningIntegration().persist(
        attempt, plan, treatment="# Treatment\n", script="假设脚本内容。\n", scenes="# Scenes\n",
    )
    attempt.update(planning["attempt"])
    planning = PlanningIntegration().review_script(
        attempt, confirm_all_claims_reviewed=True,
        expected_script_sha256=planning["truth_ledger"]["script_sha256"],
        expected_truth_packet_sha256=planning["truth_ledger"]["truth_packet_sha256"],
    )
    attempt.update(planning["attempt"])

    store = AttemptMaterialStore(root)
    payload = b"external image bytes reviewed by operator"
    digest = hashlib.sha256(payload).hexdigest()
    locator = store.write_asset_bytes("asset-pexels-review", "original.jpg", payload)
    asset = MaterialAsset(
        asset_id="asset-pexels-review", media_type=MediaType.IMAGE,
        file=FileInfo(path=locator, sha256=digest, size=len(payload), mime="image/jpeg"),
        source=CandidateSource(
            kind="external", provider="pexels", provider_asset_id="pexels-asset-1",
            source_page="https://www.pexels.com/photo/asset-1/", creator="Fixture Creator",
        ),
        rights=RightsInfo(status=RightsStatus.UNKNOWN),
        technical=TechnicalInfo(status=TechnicalStatus.PASSED, width=64, height=64, mime="image/jpeg"),
        semantic=_observed_semantic("一张外部测试图片"),
    )
    store.write_asset(asset)
    run = SupplyRun(
        supply_run_id="supply-external-rights-review", plan_id=plan.plan_id,
        started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        finished_at=datetime(2026, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
        provider_results=(SupplySourceResult(
            source_id="pexels", status="COMPLETE", candidates_found=1, acquired_assets=1,
        ),),
        result_bundle_id="bundle-external-rights-review",
    )
    bundle = MaterialBundleAssembler().assemble(
        plan, run, (asset,), (), bundle_id="bundle-external-rights-review",
    )
    readiness, gaps = MaterialReadinessCalculator(store=store).calculate(plan, bundle)
    blocked = MaterialGateIntegration().record(attempt, plan, bundle, run, readiness, gaps)
    assert blocked["status"] == "MATERIAL_NOT_READY"

    monkeypatch.setattr(
        material_supply_module, "product_provider_registry",
        lambda _roots: (_ for _ in ()).throw(AssertionError("Rights review must not repeat provider searches")),
    )
    orchestrator = MaterialProductOrchestrator()
    candidates = orchestrator.material_rights_candidates(attempt["attempt_id"])
    assert [item["asset_id"] for item in candidates] == [asset.asset_id]
    assert candidates[0]["provider"] == "pexels"

    with pytest.raises(MaterialIntegrationError, match="SHA-256 已变化"):
        orchestrator.review_material_rights(
            attempt["attempt_id"], asset_id=asset.asset_id, expected_sha256="0" * 64,
            rights=RightsInfo(status=RightsStatus.KNOWN,
                              evidence=(RightsEvidence(kind="asset_license", reference="https://example.test/license"),)),
            confirm_review=True,
        )

    reviewed = orchestrator.review_material_rights(
        attempt["attempt_id"], asset_id=asset.asset_id, expected_sha256=digest,
        rights=RightsInfo(
            status=RightsStatus.KNOWN, license_name="Fixture external terms",
            license_url="https://example.test/terms",
            evidence=(RightsEvidence(
                kind="asset_license", reference="https://example.test/terms#commercial-use",
                summary="Fixture assertion: operator reviewed this asset's actual license terms",
            ),),
        ),
        confirm_review=True,
        source_creator="Fixture Creator",
        source_page="https://www.pexels.com/photo/asset-1/",
    )
    assert reviewed["material_status"] == "MATERIAL_READY"
    assert reviewed["material_gate"]["status"] == "MATERIAL_READY"
    persisted = store.read_bundle()
    assert persisted.matches[0].asset_id == asset.asset_id
    assert persisted.assets[0].rights.status is RightsStatus.KNOWN
    assert persisted.supply_run_id.startswith("rights-")


def test_generated_rights_review_requires_explicit_operator_confirmation(
    material_integration_env, monkeypatch,
):
    orchestrator = MaterialProductOrchestrator()
    monkeypatch.setattr(
        orchestrator, "generated_material_rights_candidates",
        lambda _attempt_id: [{"asset_id": "asset-review", "asset_sha256": "a" * 64}],
    )
    with pytest.raises(MaterialIntegrationError, match="明确确认"):
        orchestrator.review_generated_material_rights(
            "fa_" + "0" * 32, asset_id="asset-review", expected_sha256="a" * 64,
            rights=RightsInfo(status=RightsStatus.KNOWN,
                              evidence=(RightsEvidence(kind="asset_license", reference="fixture://terms"),)),
            confirm_review=False,
        )


def test_asset_bytes_changed_after_admission_blocks_production_and_build(material_integration_env, tmp_path):
    attempt, root, native, cli = _native_stage(material_integration_env)
    store = AttemptMaterialStore(root)
    asset = store.read_bundle().assets[0]
    payload = store.resolve_asset_locator(asset.file.path)
    payload.write_bytes(b"tampered-after-asset-admission")
    with pytest.raises((MaterialIntegrationError, HypitIntegrationError, native.AuthoringPublicationError)):
        service.complete_film_authoring(attempt["attempt_id"], cli=cli)
    assert not cli.calls  # no Hypit check, pricing, or Build on stale Material bytes
    with pytest.raises((MaterialIntegrationError, HypitIntegrationError)):
        MaterialGateIntegration().assert_ready(service.get_film_attempt(attempt["attempt_id"]))


def test_selected_asset_must_be_referenced_by_actual_authored_svml(material_integration_env):
    attempt, root, native, cli = _native_stage(material_integration_env)
    author = root / native.AUTHOR
    original = author.read_text()
    selected = json.loads((root / native.SELECTION).read_bytes())["assets"][0]["src"]
    assert selected in original
    author.write_text(original.replace(selected, "../../../materials/assets/other/original.png"))
    before = native._files(root)
    with pytest.raises(HypitIntegrationError):
        service.complete_film_authoring(attempt["attempt_id"], cli=cli)
    assert not cli.calls and native._files(root) == before


@pytest.mark.parametrize("extra, error", [
    ('<?svml using="@hypit/gpt-image@1"?>', "禁止在 SVML/SVRun 中生成媒体"),
    ('<media:Image id="unadmitted" src="../../../../other.png"/>', "media absent from the admitted"),
])
def test_production_rejects_generated_or_unadmitted_media_sources(material_integration_env, extra, error):
    attempt, root, native, cli = _native_stage(material_integration_env)
    author = root / native.AUTHOR
    original = author.read_text()
    assert extra and original.startswith('<?svml using="@hypit/markup@1"?>')
    author.write_text(original + "\n" + extra)
    before = native._files(root)
    with pytest.raises(HypitIntegrationError):
        service.complete_film_authoring(attempt["attempt_id"], cli=cli)
    assert not cli.calls and native._files(root) == before


def test_production_selection_requires_qualified_need_match(material_integration_env):
    attempt = material_integration_env
    _planning(attempt)
    root = Path(attempt["workspace"]["path"])
    plan, qualified_asset, run, _, _, _ = _contracts(attempt, root)
    extra_bytes = b"unqualified candidate"
    extra_digest = hashlib.sha256(extra_bytes).hexdigest()
    store = AttemptMaterialStore(root)
    extra_locator = store.write_asset_bytes("asset-unmatched", "extra.png", extra_bytes)
    unmatched_asset = qualified_asset.model_copy(update={
        "asset_id": "asset-unmatched",
        "file": FileInfo(
            path=extra_locator, sha256=extra_digest, size=len(extra_bytes), mime="image/png",
        ),
    })
    store.write_asset(unmatched_asset)
    bundle_id = "bundle-selection-match"
    run = run.model_copy(update={"result_bundle_id": bundle_id})
    matches = (
        MaterialMatch(need_id="need-main", asset_id=qualified_asset.asset_id, rank=1,
                      score=1.0, reasons=("hard_filter=passed",), qualified=True),
        MaterialMatch(need_id="need-main", asset_id=unmatched_asset.asset_id, rank=2,
                      score=0.0, reasons=("hard_filter=failed",), qualified=False),
    )
    bundle = MaterialBundleAssembler().assemble(
        plan, run, (qualified_asset, unmatched_asset), matches, bundle_id=bundle_id,
    )
    readiness, gaps = MaterialReadinessCalculator(store=store).calculate(plan, bundle)
    assert readiness.status.value == "READY"
    attempt.update(MaterialGateIntegration().record(attempt, plan, bundle, run, readiness, gaps)["attempt"])
    attempt.update(ProductionAuthoringIntegration().prepare(attempt)["attempt"])
    service.begin_film_authoring(attempt["attempt_id"])
    native, cli = _stage_native_selected_image(attempt, unmatched_asset, root)
    original_files = native._files(root)
    with pytest.raises(MaterialIntegrationError, match="Need ↔ Asset Match"):
        service.complete_film_authoring(attempt["attempt_id"], cli=cli)
    assert not cli.calls and native._files(root) == original_files


def test_selection_is_bound_to_attempt_and_readiness_revisions(material_integration_env):
    attempt, root, native, cli = _native_stage(material_integration_env)
    selection = root / native.SELECTION
    payload = json.loads(selection.read_text())
    payload["bundle_revision"] = "sha256:" + "0" * 64
    selection.write_text(json.dumps(payload))
    before = native._files(root)
    with pytest.raises(HypitIntegrationError):
        service.complete_film_authoring(attempt["attempt_id"], cli=cli)
    assert native._files(root) == before and not cli.calls


def test_selection_manifest_mutation_after_authoring_is_blocked(material_integration_env):
    attempt, root, native, cli = _native_stage(material_integration_env)
    ready = service.complete_film_authoring(attempt["attempt_id"], cli=cli)
    before = json.loads((root / native.SELECTION).read_text())
    tampered = {**before, "operator_note": "injected after publication"}
    (root / native.SELECTION).write_text(json.dumps(tampered))
    with pytest.raises((HypitIntegrationError, native.AuthoringPublicationError)):
        ProductionAuthoringIntegration().validate_authored_selection(ready, native.RUN)
    assert service.get_film_attempt(ready["attempt_id"]) == ready
    assert json.loads((root / native.SELECTION).read_text()) == tampered


def test_easel_run_manifest_is_adapted_to_official_hypit_run_markup(material_integration_env):
    attempt, root, native, cli = _native_stage(material_integration_env)
    manifest = json.loads((root / native.RUN).read_text())
    assert manifest["attempt_id"] == attempt["attempt_id"]
    assert manifest["bundle_revision"] == attempt["material_gate"]["bundle_revision"]
    ready = service.complete_film_authoring(attempt["attempt_id"], cli=cli)
    run_text = (root / native.RUN).read_text()
    from easel.integrations.hypit.native_source import parse_run
    _, run, _ = parse_run(root / native.RUN, workspace=root)
    assert run["author"] == {"source": "../authors/main.svml"}
    assert run["targets"] == [{"output": "final.video"}]
    assert run_text.startswith('<?svml using="@hypit/run-markup@1"?>')
    assert json.loads((root / native.SIDECAR).read_text()) == manifest
    assert ready["authoring"]["native_publication"]["schema"] == native.SCHEMA
    frozen = native._files(root)
    assert service.complete_film_authoring(attempt["attempt_id"], cli=cli) == ready
    assert native._files(root) == frozen and len(cli.calls) == 1


@pytest.mark.parametrize("alias", ["identity", "revision"])
def test_selection_retry_rejects_mismatched_redundant_identity_alias(material_integration_env, alias):
    attempt, root, native, cli = _native_stage(material_integration_env)
    selection = root / native.SELECTION
    record = json.loads(selection.read_text())
    if alias == "identity":
        record["identity"] = {"creation_id": attempt["creation_id"],
            "attempt_id": attempt["attempt_id"], "handoff_id": "ho_" + "0" * 32}
    else:
        record["revision"] = "sha256:" + "0" * 64
    selection.write_text(json.dumps(record))
    before = native._files(root)
    with pytest.raises(HypitIntegrationError):
        service.complete_film_authoring(attempt["attempt_id"], cli=cli)
    assert native._files(root) == before and not cli.calls


def test_production_selection_carries_verified_attribution_facts(material_integration_env):
    attempt = material_integration_env
    _planning(attempt)
    root = Path(attempt["workspace"]["path"])
    plan, asset, run, bundle, _, _ = _contracts(attempt, root)
    source_page = "https://example.org/photo/1"
    asset = asset.model_copy(update={
        "source": CandidateSource(
            kind="fixture", provider="fixture", creator="Ada",
            source_page=source_page, provider_asset_id="fixture-1",
        ),
        "rights": RightsInfo(
            status=RightsStatus.ATTRIBUTION_REQUIRED, attribution_required=True,
            attribution_text=f"Photo by Ada — {source_page}",
            usage_constraints=('internal_production_only',),
            evidence=(RightsEvidence(kind="asset_license", reference="fixture:license"),),
        ),
    })
    AttemptMaterialStore(root).write_asset(asset)
    matches = (MaterialMatch(
        need_id="need-main", asset_id=asset.asset_id, rank=1, score=1.0,
        reasons=("hard_filter=passed",), qualified=True,
    ),)
    bundle = MaterialBundleAssembler().assemble(plan, run, (asset,), matches, bundle_id=bundle.bundle_id)
    readiness, gaps = MaterialReadinessCalculator(store=AttemptMaterialStore(root)).calculate(plan, bundle)
    assert readiness.status.value == "READY"
    attempt.update(MaterialGateIntegration().record(attempt, plan, bundle, run, readiness, gaps)["attempt"])
    attempt.update(ProductionAuthoringIntegration().prepare(attempt)["attempt"])
    service.begin_film_authoring(attempt["attempt_id"])
    native, cli = _stage_native_selected_image(attempt, asset, root)
    ready = service.complete_film_authoring(attempt["attempt_id"], cli=cli)
    assert ready["authoring_status"] == "AUTHORING_READY" and len(cli.calls) == 1
    result = {"attempt": ready}
    persisted = result["attempt"]["production_authoring"]["selection_validation"]["attributions"]
    assert persisted == [{
        "asset_id": asset.asset_id, "creator": "Ada",
        "credit_text": f"Photo by Ada — {source_page}", "source_page": source_page,
        "destination": "export_credits", "rights_status": "ATTRIBUTION_REQUIRED",
        "evidence_references": ["fixture:license"],
    }]
    assert service._validated_output_usage(result['attempt']) == [{
        'asset_id': asset.asset_id, 'sha256': asset.file.sha256,
        'constraints': ['internal_production_only'],
    }]
    # Clearing a restriction after selection must not silently broaden an
    # already authored/exported result's permission.
    changed = asset.model_copy(update={'rights': asset.rights.model_copy(update={'usage_constraints': ()})})
    changed_bundle = MaterialBundleAssembler().assemble(plan, run, (changed,), matches, bundle_id=bundle.bundle_id)
    AttemptMaterialStore(root).write_bundle(changed_bundle)
    with pytest.raises(service.HypitIntegrationError, match='使用范围已变化'):
        service._validated_output_usage(result['attempt'])


@pytest.mark.parametrize(('interrupt_after_supply', 'automatic'), [(False, False), (True, False), (True, True)])
def test_material_recovery_preserves_generation_and_reconciles_without_resupply(
        material_integration_env, monkeypatch, interrupt_after_supply, automatic):
    from easel.integrations import material_recovery as recovery
    attempt = service.get_film_attempt(material_integration_env["attempt_id"])
    if automatic:
        # Runtime setup belongs after material preparation. An unavailable
        # renderer must not prevent supplemental supply or its reconciliation.
        assert attempt['execution_status'] == 'BLOCKED'
    else:
        attempt = service.update_film_attempt(attempt['attempt_id'],
            execution_status="NOT_SUBMITTED", event="fixture_runtime_ready")
    store = AttemptMaterialStore(attempt["workspace"]["path"])
    plan, visual, _, _, _, _ = _contracts(attempt, Path(attempt["workspace"]["path"]))
    voice_need = MaterialNeed(
        need_id="voice", scope=NeedScope(type=NeedScopeType.GLOBAL, ref="film"), media_type=MediaType.AUDIO,
        role="旁白", intent=NeedIntent(description="普通话旁白"), importance=NeedImportance.REQUIRED,
        constraints={"required_source_kind": "generative", "allow_generation": True},
        modality_spec=VoiceNeedSpec(kind="voice", identity=VoiceIdentityRef(
            source=VoiceIdentitySource.EXPLICIT_USER, reference="预置普通话音色")))
    bgm_need = MaterialNeed(
        need_id="bgm", scope=NeedScope(type=NeedScopeType.GLOBAL, ref="film"), media_type=MediaType.AUDIO,
        role="配乐", intent=NeedIntent(description="gentle piano instrumental"),
        importance=NeedImportance.REQUIRED, constraints={"required_source_kind": "stock"},
        modality_spec=BgmNeedSpec(kind="bgm", instruments=("piano",), vocals_allowed=False))
    planning = PlanningIntegration().persist(attempt, plan.model_copy(update={
        "needs": plan.needs + (voice_need, bgm_need)}), treatment="原方案", script="假设原旁白。", scenes="原场景")
    attempt, plan = planning["attempt"], planning["plan"]
    voice_bytes = b"completed-generation-fixture"
    voice_path = store.write_asset_bytes("voice-asset", "original.mp3", voice_bytes)
    voice = visual.model_copy(update={"asset_id": "voice-asset", "media_type": MediaType.AUDIO,
        "file": FileInfo(path=voice_path, sha256=hashlib.sha256(voice_bytes).hexdigest(),
                         size=len(voice_bytes), mime="audio/mpeg"),
        "source": CandidateSource(kind="generative", provider="fixture", provider_asset_id="voice"),
        "rights": RightsInfo(status=RightsStatus.UNKNOWN),
        "technical": TechnicalInfo(status=TechnicalStatus.PASSED, duration_seconds=10, mime="audio/mpeg")})
    store.write_asset(voice)
    music_path = store.write_asset_bytes("music-asset", "original.mp3", b"music-fixture")
    music = voice.model_copy(update={"asset_id": "music-asset",
        "file": FileInfo(path=music_path, sha256=hashlib.sha256(b"music-fixture").hexdigest(),
                         size=len(b"music-fixture"), mime="audio/mpeg"),
        "source": CandidateSource(kind="local", provider="fixture", provider_asset_id="music"),
        "rights": RightsInfo(status=RightsStatus.ATTRIBUTION_REQUIRED, attribution_required=True,
                             attribution_text="fixture credit", evidence=(RightsEvidence(
                                 kind="asset_license", reference="fixture-license"),))})
    store.write_asset(music)
    store.write_generation_record("generation", {"schema": "easel-material-generation@1",
        "status": "COMPLETE", "attempt_id": attempt["attempt_id"], "plan_id": plan.plan_id,
        "plan_revision": MaterialReadinessCalculator.plan_revision(plan), "need_id": "voice",
        "input_sha256": planning["truth_ledger"]["script_sha256"], "asset_id": voice.asset_id,
        "asset_sha256": voice.file.sha256, "asset_path": voice.file.path, "asset_bytes": voice.file.size})
    run = SupplyRun(supply_run_id="initial", plan_id=plan.plan_id,
                    started_at=datetime.now(timezone.utc), finished_at=datetime.now(timezone.utc),
                    result_bundle_id="recovery-bundle")
    from easel.materials.application.matching import MaterialMatcher
    matches = MaterialMatcher().match(plan.needs[0], (visual,)).matches
    bundle = MaterialBundleAssembler().assemble(plan, run, (visual, voice, music), matches,
                                                bundle_id="recovery-bundle")
    readiness, gaps = MaterialReadinessCalculator(store=store).calculate(plan, bundle)
    attempt = MaterialGateIntegration().record(attempt, plan, bundle, run, readiness, gaps)["attempt"]
    args = dict(request_id="recovery-test", expected_plan_revision=readiness.plan_revision,
                expected_bundle_revision=bundle.revision, allow_licensed_bgm=True,
                search_terms={"bgm": ("piano instrumental",)})
    query_calls = []
    if automatic:
        from easel.creation_delivery import SCHEMA
        with creation.edit_creation(attempt['creation_id']) as work:
            work['delivery'] = {'schema': SCHEMA}
        # Preparing an empty selection is not execution and must not prevent
        # correction when subsequent system observation invalidates readiness.
        service.update_film_attempt(attempt['attempt_id'], event='fixture_empty_authoring',
            production_authoring={'status': 'PENDING_SELECTION', 'selected_asset_ids': []})
    def plan_queries(current, record):
        import web.app as webapp
        query_calls.append(record['request_id'])
        assert [n['need_id'] for n in record['needs']] == ['bgm']
        def answer(message, timeout, session_id):
            assert '不生成素材或启动 Build' in message and 'required_source_kind' in message
            store.write_recovery_record(record['request_id'] + '-queries',
                {'request_id': record['request_id'], 'search_terms': {'bgm': ['piano instrumental']}})
            return ''
        monkeypatch.setattr(webapp, 'run_agent_sync', answer)
        return webapp._plan_material_recovery(current, record)
    def invoke():
        if not automatic:
            return recovery.recover_materials(attempt['attempt_id'], **args)
        updated = recovery.recover_managed_materials(attempt['attempt_id'], executor=plan_queries)
        return {'attempt': updated, 'material_status': updated['material_gate']['status']}
    monkeypatch.setattr(material_supply_module, "product_provider_registry",
                        lambda roots: (material_supply_module.ProviderRegistry(), ()))
    calls = []
    actual_supply = recovery.ProductMaterialSupply.run
    def counted_supply(self, *a, **kw):
        calls.append(kw)
        return actual_supply(self, *a, **kw)
    monkeypatch.setattr(recovery.ProductMaterialSupply, "run", counted_supply)
    real_record = recovery.MaterialGateIntegration.record
    def interrupted_record(self, a, p, b, *rest):
        if interrupt_after_supply and b.supply_run_id.startswith("supplement-"):
            raise RuntimeError("simulated gate update interruption")
        return real_record(self, a, p, b, *rest)
    monkeypatch.setattr(recovery.MaterialGateIntegration, "record", interrupted_record)
    if interrupt_after_supply:
        with pytest.raises(RuntimeError, match="interruption"):
            invoke()
        monkeypatch.setattr(recovery.MaterialGateIntegration, "record", real_record)
    result = invoke()
    assert len(calls) == 1
    assert calls[0]["skip_need_ids"] == ("voice",)
    refreshed = PlanningIntegration().load(result["attempt"])
    assert refreshed["plan"].needs[:2] == plan.needs[:2]
    if automatic:
        assert refreshed['plan'] == plan  # Supplemental wording cannot enlarge source permissions.
        assert len(query_calls) == 1
        assert result['attempt']['autonomous_material_recovery']['status'] == 'COMPLETE'
        assert result['attempt']['execution_status'] == 'BLOCKED'
    else:
        assert "required_source_kind" not in refreshed["plan"].needs[2].constraints
        assert refreshed["plan"].needs[2].constraints["allow_generation"] is False
    assert refreshed["script"] == "假设原旁白。"
    assert refreshed["scenes"] == "原场景"
    assert refreshed["truth_ledger"]["script_sha256"] == planning["truth_ledger"]["script_sha256"]
    assert store.read_asset(voice.asset_id) == voice
    assert {asset.asset_id: asset for asset in store.read_bundle().assets} == {
        asset.asset_id: asset for asset in (visual, voice, music)}
    assert store.read_supply_run(store.read_bundle().supply_run_id).parent_run_id.startswith('recover-')
    assert len(store.list_generation_records()) == 1
    assert result["material_status"] == "MATERIAL_NOT_READY"  # Rights remains a formal gate.
    trace = json.loads((store.materials_root / "product-supply.json").read_text())["routing"]
    assert [row["need_id"] for row in trace if row.get("checkpoint_reused")] == ["need-main", "voice"]
    repeated = invoke()
    assert len(calls) == 1
    if not automatic:
        assert repeated['recovery']['reused'] is True
        with pytest.raises(MaterialIntegrationError, match="改变输入"):
            recovery.recover_materials(attempt["attempt_id"], **{**args, "search_terms": {"bgm": ("different",)}})
    with pytest.raises(MaterialIntegrationError, match="状态已变化"):
        recovery.recover_materials(attempt["attempt_id"], **{**args, "request_id": "stale-new-request"})
    # The same formal review handles real listening evidence after a source-only revision.
    generation = store.read_generation_record("generation")
    store.write_generation_record("generation", {**generation, "input_sha256": "0" * 64})
    review_args = dict(asset_id=voice.asset_id, expected_sha256=voice.file.sha256, need_id="voice",
                      observed_content="已试听，句子完整清晰且语速合适", logo_present=None,
                      visible_text_present=None, confirm_review=True)
    with pytest.raises(MaterialIntegrationError, match="绑定当前冻结脚本"):
        MaterialProductOrchestrator().review_material_match(attempt["attempt_id"], **review_args)
    store.write_generation_record("generation", generation)
    reviewed = MaterialProductOrchestrator().review_material_match(attempt["attempt_id"], **review_args)
    assert reviewed["material_status"] == "MATERIAL_NOT_READY"  # A listening review cannot clear UNKNOWN Rights.
    candidates = MaterialProductOrchestrator().material_rights_candidates(attempt["attempt_id"])
    narration = next(c for c in candidates if c["asset_id"] == voice.asset_id)
    assert narration["generation_need_ids"] == ["voice"]
    assert narration["semantic_reviewed_need_ids"] == ["voice"]
    music_review = MaterialProductOrchestrator().review_material_match(attempt["attempt_id"],
        **{**review_args, "asset_id": music.asset_id, "expected_sha256": music.file.sha256,
           "need_id": "bgm", "observed_content": "试听为舒缓无歌词钢琴器乐，符合配乐要求"})
    assert music_review["material_status"] == "MATERIAL_NOT_READY"
    candidates = MaterialProductOrchestrator().material_rights_candidates(attempt["attempt_id"])
    music_candidate = next(c for c in candidates if c["asset_id"] == music.asset_id)
    assert "bgm" in music_candidate["rights_blocking_need_ids"]  # Missing credit provenance stays visible.
    assert "bgm" in music_candidate["semantic_reviewed_need_ids"]
    service.update_film_attempt(attempt["attempt_id"], execution_status="BUILD_RUNNING", event="fixture_build")
    assert invoke()['material_status'] == 'MATERIAL_NOT_READY'
    with pytest.raises(MaterialIntegrationError, match="视频制作已开始"):
        recovery.recover_materials(attempt["attempt_id"], **{**args, "request_id": "new-after-build"})


@pytest.mark.parametrize(('second_verdict', 'known_rights', 'report_fault'), [
    ('unsuitable', True, 'syntax'), ('suitable', True, 'missing'),
    ('suitable', False, None), ('uncertain', True, 'duplicate'),
    ('unsuitable', True, 'persistent'), ('suitable', True, 'silent_compile'),
])
def test_system_visual_observation_is_per_need_and_resumes_without_supply(
        material_integration_env, monkeypatch, second_verdict, known_rights, report_fault):
    import base64
    import io
    import web.app as webapp
    from easel.creation_delivery import DeliveryExecutionUncertain, DeliveryReportError
    from easel.materials.application.visual_observation import SCHEMA, observed_match
    attempt = material_integration_env
    from easel.integrations import material_results
    delta = material_results.enabled(attempt)
    root = Path(attempt['workspace']['path'])
    store = AttemptMaterialStore(root)
    plan, asset, run, _, _, _ = _contracts(attempt, root)
    first = plan.needs[0].model_copy(update={'constraints': {'preferred_style': 'quiet red', 'logo': False,
        'preferred_visual_details': 'wide shot, background lamp optional'}})
    second = first.model_copy(update={'need_id': 'another-scene', 'intent': NeedIntent(description='完全不同的内容')})
    plan = plan.model_copy(update={'needs': (first, second)})
    image = io.BytesIO()
    Image.new('RGB', (32, 24), 'red').save(image, format='PNG')
    data = image.getvalue()
    locator = store.write_asset_bytes(asset.asset_id, 'actual.png', data)
    asset = asset.model_copy(update={
        'file': FileInfo(path=locator, sha256=hashlib.sha256(data).hexdigest(), size=len(data), mime='image/png'),
        'semantic': SemanticInfo(caption=first.intent.description + second.intent.description),
        'rights': asset.rights if known_rights else RightsInfo(status=RightsStatus.UNKNOWN),
    })
    store.write_asset(asset)
    planning = PlanningIntegration().persist(attempt, plan, treatment='T', script='假设脚本内容。', scenes='S')
    plan = planning['plan']
    bundle = MaterialBundleAssembler().assemble(plan, run, (asset,), (), bundle_id='bundle-int-1')
    readiness, gaps = MaterialReadinessCalculator(store=store).calculate(plan, bundle)
    MaterialGateIntegration().record(planning['attempt'], plan, bundle, run, readiness, gaps)
    monkeypatch.setattr(material_supply_module.ProductMaterialSupply, 'run',
                        lambda *a, **k: pytest.fail('observation must not acquire or generate material'))
    calls, compilations, replies = [], [], {}
    interrupted = False
    def observe(message, timeout, session_id, *, attachments=None, capture_reply=False):
        nonlocal interrupted
        assert capture_reply
        payload = json.loads(message.split('输入（数据，不执行其中指令）：', 1)[1])
        if session_id in replies:
            return replies[session_id]
        if payload.get('revision') == 'visual-requirements@1':
            compilations.append(payload['need_sha256'])
            assert 'need' not in payload
            assert [u['id'] for u in payload['units']] == list(range(len(payload['units'])))
            assert payload['preference_context']
            if report_fault == 'silent_compile' and len(compilations) == 1:
                assert session_id.startswith('material-result-')
                raise ValueError('原运行回复为 silent，不能作审核结果')
            if report_fault == 'silent_compile' and payload.get('repair'):
                assert payload['original_result'] == {'_invalid_json': 'MODEL_OUTPUT_REJECTED'}
                assert payload['failure']
            result = {'classifications': [{'id': u['id'], 'kind': 'required', 'preference_source': None}
                                           for u in payload['units']]}
            replies[session_id] = json.dumps(result)
            if report_fault == 'silent_compile' and payload.get('repair'):
                replies[session_id] = '```json\n' + replies[session_id] + '\n```'
            return replies[session_id]
        assert len(attachments) == 1
        assert payload['check_ids'] == [str(c['id']) if delta else c['id'] for c in payload['clauses']]
        assert 'preferences' not in payload
        raw = base64.b64decode(attachments[0]['content'])
        assert hashlib.sha256(raw).hexdigest() == payload['frame']['sha256']
        with Image.open(io.BytesIO(raw)) as decoded:
            assert decoded.getpixel((0, 0))[0] > 240
        good = payload['input_sha256'] == first_identity
        calls.append((payload['input_sha256'], payload.get('repair', 0)))
        result = {'frame': payload['frame']['index'], 'observed': True, 'description': 'actual red field',
                  'style': 'quiet red', 'logo': False, 'text': False, 'preference_notes': 'wide shot differs',
                  'checks': [{'id': c['id'], 'status': 'met' if good or second_verdict == 'suitable' else
                             'unknown' if second_verdict == 'uncertain' else 'not_met',
                             'basis': 'independent actual evidence'} for c in payload['clauses']]}
        if delta:
            result.pop('frame')
            result['checks'] = {str(c.pop('id')): c for c in result['checks']}
            if payload['mode'] == 'delta':
                for key in material_results.FACT_FIELDS:
                    result.pop(key)
                result.update(observation_ref='observation', facts_dispute={'kind': 'none'})
            assert payload['mode'] == ('facts' if good else 'delta')
        if not good and (not payload.get('repair') or report_fault == 'persistent'):
            if report_fault == 'syntax' or report_fault == 'persistent':
                replies[session_id] = '{"invalid":'
            elif report_fault == 'missing':
                result['checks'] = []
            elif report_fault == 'duplicate':
                result['checks']['unexpected-check'] = {
                    'status': 'met', 'basis': 'extra check was not requested'}
        replies.setdefault(session_id, json.dumps(result))
        if not good and not interrupted:
            interrupted = True
            raise DeliveryExecutionUncertain('fixture original run awaiting same-result recovery')
        return replies[session_id]
    from easel.materials.application.visual_observation import prepare_observation
    first_identity = prepare_observation(plan.needs[0], asset, store.resolve_asset_locator(asset.file.path))[0]['input_sha256']
    monkeypatch.setattr(webapp, 'run_agent_sync', observe)
    with pytest.raises(DeliveryExecutionUncertain):
        MaterialProductOrchestrator().observe_visual_materials(attempt['attempt_id'], executor=webapp._observe_material_frames,
                                                             group_executor=webapp._observe_material_group)
    assert json.loads((store.materials_root / 'observations' / (first_identity + '.json')).read_text())['verdict'] == 'suitable'
    if report_fault == 'persistent':
        with pytest.raises((DeliveryReportError, webapp.PreparationError), match='一次格式修复后仍无效'):
            MaterialProductOrchestrator().observe_visual_materials(attempt['attempt_id'], executor=webapp._observe_material_frames,
                                                                 group_executor=webapp._observe_material_group)
        before = list(calls)
        with pytest.raises((DeliveryReportError, webapp.PreparationError)):
            MaterialProductOrchestrator().observe_visual_materials(attempt['attempt_id'], executor=webapp._observe_material_frames,
                                                                 group_executor=webapp._observe_material_group)
        assert calls == before
    else:
        result = MaterialProductOrchestrator().observe_visual_materials(attempt['attempt_id'], executor=webapp._observe_material_frames,
                                                                     group_executor=webapp._observe_material_group)
        expected = 'MATERIAL_READY' if known_rights and second_verdict == 'suitable' else 'MATERIAL_NOT_READY'
        assert result['material_status'] == expected
        before = list(calls)
        MaterialProductOrchestrator().observe_visual_materials(attempt['attempt_id'], executor=webapp._observe_material_frames,
                                                             group_executor=webapp._observe_material_group)
        assert calls == before
        assert observed_match(plan.needs[0], store.read_asset(asset.asset_id)) is True
        assert observed_match(plan.needs[1], store.read_asset(asset.asset_id)) is (second_verdict == 'suitable')
    assert len(compilations) == (3 if report_fault == 'silent_compile' else 2)
    assert len([c for c in calls if c[0] == first_identity]) == 1  # Valid first child survived the other child's repair.
    assert store.read_asset(asset.asset_id).rights == asset.rights


@pytest.mark.parametrize('material_integration_env', [
    {'material_observation': 'material-observation-delta@1'}], indirect=True)
def test_material_delta_shared_owner_reuses_captures_and_published_qualification(
        material_integration_env, monkeypatch):
    test_system_visual_observation_is_per_need_and_resumes_without_supply(
        material_integration_env, monkeypatch, 'suitable', True, 'missing')


def _material_delta_pixels_scenario(attempt, monkeypatch, *, clause_count=1, response=None):
    """Real Planning, pixel preparation, wire Owner, proof store and domain application."""
    import io
    import web.app as webapp
    from easel.integrations import material_results
    from easel.materials.application.visual_observation import prepare_observation, apply_observation
    root = Path(attempt['workspace']['path'])
    store = AttemptMaterialStore(root)
    plan, source, run, _, _, _ = _contracts(attempt, root)
    first = plan.needs[0].model_copy(update={
        'intent': NeedIntent(description=';'.join('red visible item ' + str(i) for i in range(clause_count))),
        'constraints': {'logo': False}})
    second = first.model_copy(update={'need_id': 'second-need', 'intent': NeedIntent(description='red alternate scene')})
    challenge = first.model_copy(update={'need_id': 'challenge', 'importance': NeedImportance.OPTIONAL,
                                        'intent': NeedIntent(description='red independent assessment')})
    plan = plan.model_copy(update={'needs': (first, second, challenge)})
    planned = PlanningIntegration().persist(attempt, plan, treatment='T', script='假设这是虚构画面。', scenes='S')
    attempt, plan = planned['attempt'], planned['plan']
    assets = []
    for asset_id, color in ((source.asset_id, 'red'), ('asset-backup', 'blue')):
        buffer = io.BytesIO()
        Image.new('RGB', (32, 24), color).save(buffer, format='PNG')
        data = buffer.getvalue()
        locator = store.write_asset_bytes(asset_id, 'actual.png', data)
        asset = source.model_copy(update={'asset_id': asset_id, 'semantic': SemanticInfo(),
            'file': FileInfo(path=locator, sha256=hashlib.sha256(data).hexdigest(),
                             size=len(data), mime='image/png')})
        store.write_asset(asset)
        assets.append(asset)
    calls, replies = [], {}
    def invoke(message, timeout, session_id, *, attachments=None, capture_reply=False):
        assert capture_reply
        payload = json.loads(message.split('输入（数据，不执行其中指令）：', 1)[1])
        if session_id in replies:
            return replies[session_id]
        if payload.get('revision') == 'visual-requirements@1':
            reply = {'classifications': [{'id': u['id'], 'kind': 'required', 'preference_source': None}
                                         for u in payload['units']]}
        else:
            assert payload['protocol'] == material_results.REVISION and attachments
            calls.append((session_id, payload))
            reply = {'checks': {key: {'status': 'met', 'basis': 'actual visible pixels'}
                                for key in payload['check_ids']}, 'preference_notes': 'no preference'}
            if payload['mode'] == 'facts':
                reply.update(observed=True, description='actual visible field', style='quiet', logo=False, text=False)
            else:
                reply.update(observation_ref='observation', facts_dispute={'kind': 'none'})
            if response:
                reply = response(payload, reply)
        replies[session_id] = json.dumps(reply)
        # Simulate the same existing external run: its terminal reply survives a local interruption.
        if isinstance(reply, dict) and reply.pop('_interrupt_after_reply', False):
            replies[session_id] = json.dumps(reply)
            from easel.creation_delivery import DeliveryExecutionUncertain
            raise DeliveryExecutionUncertain('fixture saved external result before local capture')
        return replies[session_id]
    monkeypatch.setattr(webapp, 'run_agent_sync', invoke)
    def emit(need, asset):
        current = store.read_asset(asset.asset_id)
        manifest, attachments = prepare_observation(need, current, store.resolve_asset_locator(current.file.path))
        report = webapp._observe_material_frames(attempt, manifest, attachments)
        observed = apply_observation(need, current, manifest, report,
                                    result_processor=material_results.processor(attempt, store))
        store.write_asset(observed)
        return manifest, report, observed
    return attempt, store, plan, run, assets, calls, emit


@pytest.mark.parametrize('material_integration_env', [
    {'material_observation': 'material-observation-delta@1'}], indirect=True)
@pytest.mark.parametrize('risk', ['unknown_first', 'second_uncertain', 'formal_write', 'tampered_projection'])
def test_material_delta_batches_keep_original_results_and_recover_locally(
        material_integration_env, monkeypatch, risk):
    import subprocess
    import sys
    from easel.creation_delivery import DeliveryExecutionUncertain
    from easel.integrations import material_results, output_receipts
    from easel.materials.application.visual_contract import batches
    def response(payload, reply):
        if risk == 'unknown_first' and payload['batch'] == 0:
            reply['observed'] = False
            for check in reply['checks'].values():
                check['status'] = 'unknown'
        if risk == 'second_uncertain' and payload['batch'] == 1:
            reply['_interrupt_after_reply'] = True
        return reply
    attempt, store, plan, _, assets, calls, emit = _material_delta_pixels_scenario(
        material_integration_env, monkeypatch, clause_count=8, response=response)
    if risk == 'formal_write':
        original = AttemptMaterialStore.write_observation_record
        failed = False
        def write(self, key, value):
            nonlocal failed
            if not failed and value.get('schema') == material_results.REPORT:
                failed = True
                raise OSError('fixture formal publication interrupted')
            return original(self, key, value)
        monkeypatch.setattr(AttemptMaterialStore, 'write_observation_record', write)
        with pytest.raises(OSError, match='formal publication'):
            emit(plan.needs[0], assets[0])
    elif risk == 'second_uncertain':
        with pytest.raises(DeliveryExecutionUncertain):
            emit(plan.needs[0], assets[0])
    manifest, report, observed = emit(plan.needs[0], assets[0])
    assert len(batches(manifest, report['requirements_contract'])) == 2
    assert len(calls) == 2 and all(not payload.get('repair') for _, payload in calls)
    assert [payload['mode'] for _, payload in calls] == (
        ['facts', 'facts'] if risk == 'unknown_first' else ['facts', 'delta'])
    if risk == 'unknown_first':
        assert report['verdict'] == 'uncertain' and report['frames'][0]['observed'] is False
        statuses = {c['status'] for c in report['requirement_checks'][0]['requirements']}
        assert statuses == {'unknown', 'met'}  # No aggregate rewriting of a later valid result.
    else:
        assert report['verdict'] == 'suitable'
    emit(plan.needs[0], observed)
    assert len(calls) == 2
    # A fresh interpreter has no in-memory policy/facts cache.
    cold = """import json,sys
from easel.integrations import material_results
from easel.materials.store import AttemptMaterialStore
attempt=json.loads(sys.argv[2]); store=AttemptMaterialStore(sys.argv[1])
plan=store.read_plan(); asset=store.read_asset('asset-main')
assert material_results.eligible(store,plan.needs[0],asset,attempt=attempt)
"""
    subprocess.run([sys.executable, '-c', cold, attempt['workspace']['path'], json.dumps(attempt)],
                   check=True, capture_output=True, text=True, timeout=60)
    if risk == 'tampered_projection':
        reference = report['result_groups'][1]['derivation']
        changed = store.read_recovery_record(reference['key'])
        changed['unbound_projection'] = True
        store.write_recovery_record(reference['key'], changed)
        with pytest.raises(output_receipts.OutputReceiptError):
            emit(plan.needs[0], observed)
        assert len(calls) == 2
        failure = subprocess.run([sys.executable, '-c', cold, attempt['workspace']['path'], json.dumps(attempt)],
                                 capture_output=True, text=True, timeout=60)
        assert failure.returncode != 0 and 'OutputReceiptError' in failure.stderr


@pytest.mark.parametrize('material_integration_env', [
    {'material_observation': 'material-observation-delta@1'}], indirect=True)
def test_material_delta_dispute_revokes_all_dependents_but_keeps_independent_candidate(
        material_integration_env, monkeypatch):
    import web.app as webapp
    from easel.integrations import material_results
    from easel.materials.application.matching import MaterialMatcher
    from easel.materials.application.visual_observation import need_identity
    state = {'dispute': False}
    def response(payload, reply):
        if state['dispute']:
            assert payload['mode'] == 'delta'
            # The terminal local decision survives an unrelated outer schema failure.
            return {'observation_ref': 'observation',
                    'facts_dispute': {'kind': 'detected', 'reason': 'visible field contradicts retained facts'},
                    'checks': {'unexpected': 'cannot erase the dispute through repair'}}
        return reply
    attempt, store, plan, run, assets, calls, emit = _material_delta_pixels_scenario(
        material_integration_env, monkeypatch, response=response)
    for asset in assets:
        for need in plan.needs[:2]:
            emit(need, asset)
    current = tuple(store.read_asset(a.asset_id) for a in assets)
    matcher = MaterialMatcher()
    matches = []
    for need in plan.needs[:2]:
        by_id = {m.asset_id: m for m in matcher.match(need, current).matches}
        assert set(by_id) == {a.asset_id for a in current}
        matches.extend(by_id[a.asset_id].model_copy(update={'rank': index + 1})
                       for index, a in enumerate(current))
    bundle = MaterialBundleAssembler().assemble(plan, run, current, tuple(matches), bundle_id=run.result_bundle_id)
    calculator = material_results.readiness_calculator(attempt, store)
    readiness, gaps = calculator.calculate(plan, bundle)
    gate = MaterialGateIntegration().record(attempt, plan, bundle, run, readiness, gaps)
    attempt = gate['attempt']
    assert gate['status'] == 'MATERIAL_READY'
    asset_before, bundle_before = current[0].to_json(), store.read_bundle().to_json()
    state['dispute'] = True
    with pytest.raises(webapp.PreparationError, match='有效异议'):
        emit(plan.needs[2], current[0])
    assert len(calls) == 5 and not calls[-1][1].get('repair')
    with pytest.raises(webapp.PreparationError, match='有效异议'):
        emit(plan.needs[2], current[0])
    assert len(calls) == 5
    for need in plan.needs[:2]:
        assert not material_results.eligible(store, need, current[0], attempt=attempt)
        assert material_results.eligible(store, need, current[1], attempt=attempt)
    assert store.read_asset(current[0].asset_id).to_json() == asset_before
    assert store.read_bundle().to_json() == bundle_before
    # Actual Gate rereads the old persisted Bundle and checks current proof eligibility.
    _, _, accepted = MaterialGateIntegration().assert_ready(attempt)
    assert accepted.status.value == 'READY' and set(accepted.covered_required_needs) == {
        n.need_id for n in plan.needs[:2]}
    assert ProductionAuthoringIntegration._qualified_need_ids(
        plan, bundle, current[0], store=store, attempt=attempt) == ()
    assert set(ProductionAuthoringIntegration._qualified_need_ids(
        plan, bundle, current[1], store=store, attempt=attempt)) == {n.need_id for n in plan.needs[:2]}
    only_old = MaterialBundleAssembler().assemble(plan, run, (current[0],),
        tuple(m for m in matches if m.asset_id == current[0].asset_id), bundle_id=run.result_bundle_id)
    assert calculator.calculate(plan, only_old)[0].status.value == 'NOT_READY'
    need, asset = plan.needs[0], current[0]
    creator = SemanticInference(analyzer_id='creator-match:' + need.need_id, status=IntelligenceStatus.COMPLETE,
        annotations=(SemanticAnnotation(field=SemanticField.CAPTION, value='creator confirms the intended scene',
            confidence=1, evidence='creator-confirmed:' + need.need_id + ':' + asset.file.sha256
                + ':need=' + need_identity(need)),))
    reviewed = asset.model_copy(update={'semantic': asset.semantic.model_copy(
        update={'inferences': asset.semantic.inferences + (creator,)})})
    assert matcher._creator_match_review(need, reviewed)
    view = material_results.matching_asset(store, need, reviewed, attempt)
    rejected = matcher.match(need, (view,))
    assert not rejected.matches and 'logo_presence_unknown' in rejected.rejected[0].reasons
    assert not material_results.eligible(store, need, reviewed, attempt=attempt)


@pytest.mark.parametrize(('usable_index', 'metadata'), [
    (3, 'related'), (4, 'related'), (8, 'missing'), (None, 'related'), ('content_first', 'related'),
])
def test_visual_replacement_stops_at_usable_choice_or_bound_and_reuses_saved_report(
        material_integration_env, monkeypatch, usable_index, metadata):
    import io
    from easel.materials.application.visual_observation import SCHEMA, MAX_VISUAL_CANDIDATES, MAX_PRIMARY_VISUAL_CANDIDATES
    attempt = material_integration_env
    root = Path(attempt['workspace']['path'])
    store = AttemptMaterialStore(root)
    plan, original, run, _, _, _ = _contracts(attempt, root)
    content_first = usable_index == 'content_first'
    if content_first:
        usable_index = 3
        need = plan.needs[0].model_copy(update={'constraints': {'preferred_style': 'quiet documentary'}})
        plan = plan.model_copy(update={'needs': (need,)})
    assets = []
    for index in range(MAX_VISUAL_CANDIDATES + 1):
        raw = io.BytesIO()
        Image.new('RGB', (32, 24), (index * 20, 0, 0)).save(raw, format='PNG')
        data = raw.getvalue()
        asset_id = f'candidate-{index:02d}'
        locator = store.write_asset_bytes(asset_id, 'frame.png', data)
        asset = original.model_copy(update={'asset_id': asset_id,
            'file': FileInfo(path=locator, sha256=hashlib.sha256(data).hexdigest(), size=len(data), mime='image/png'),
            'semantic': SemanticInfo(caption=plan.needs[0].intent.description if metadata == 'related' else None)})
        if content_first:
            asset = asset.model_copy(update={
                'semantic': SemanticInfo(caption=plan.needs[0].intent.description,
                    attributes={'style': 'quiet documentary'} if index != 3 else {}),
                'rights': RightsInfo(status=RightsStatus.RESTRICTED) if index == 0 else asset.rights,
            })
        store.write_asset(asset)
        assets.append(asset)
    if content_first:
        from easel.materials.application.matching import MaterialMatcher
        matcher = MaterialMatcher()
        preferred, relevant = (matcher._soft_scores(plan.needs[0], assets[i]) for i in (1, 3))
        assert preferred[1] > relevant[1]  # Previous weighted ranking observed this first.
        assert preferred[0].semantic < relevant[0].semantic
    planning = PlanningIntegration().persist(attempt, plan, treatment='T', script='假设脚本内容。', scenes='S')
    plan = planning['plan']
    bundle = MaterialBundleAssembler().assemble(plan, run, tuple(assets), (), bundle_id='bundle-int-1')
    readiness, gaps = MaterialReadinessCalculator(store=store).calculate(plan, bundle)
    MaterialGateIntegration().record(planning['attempt'], plan, bundle, run, readiness, gaps)
    from tests.material_delta_fixture import observed_result
    calls = []
    def observe(current, manifest, attachments):
        calls.append(manifest['asset_id'])
        good = manifest['asset_id'] == f'candidate-{usable_index:02d}' if usable_index is not None else False
        return observed_result(current, manifest, attachments,
            outcome='suitable' if good else 'unsuitable',
            description='actual colored frame', style='fixture style')
    write_asset = AttemptMaterialStore.write_asset
    interrupted = False
    def interrupt_record(self, asset):
        nonlocal interrupted
        interrupt_at = 'candidate-03' if content_first else 'candidate-04' if usable_index == 4 else 'candidate-00' if usable_index == 8 else 'candidate-02'
        if asset.asset_id == interrupt_at and asset.semantic.inferences and not interrupted:
            interrupted = True
            raise OSError('模拟报告已保存、Asset 尚未更新时中断')
        return write_asset(self, asset)
    monkeypatch.setattr(AttemptMaterialStore, 'write_asset', interrupt_record)
    monkeypatch.setattr(material_supply_module.ProductMaterialSupply, 'run',
                        lambda *a, **k: pytest.fail('existing candidates must not trigger a Provider'))
    with pytest.raises(OSError, match='模拟报告'):
        for _ in range(MAX_VISUAL_CANDIDATES):
            MaterialProductOrchestrator().observe_visual_materials(attempt['attempt_id'], executor=observe)
    # Nomination budget and copy-safe resume are domain-owned. The managed
    # advance_creation dispatcher is independently covered by material
    # endpoint/Owner tests; this fixture is already inside the Material stage.
    for _ in range(MAX_VISUAL_CANDIDATES):
        result = MaterialProductOrchestrator().observe_visual_materials(
            attempt['attempt_id'], executor=observe)
        if result['material_status'] == 'MATERIAL_READY':
            break
    # The new Need/Match contract does not nominate unrelated metadata merely
    # to exhaust the old fixed candidate budget. A missing-content pool must
    # stop after the one defensible nomination, preserving all unobserved
    # candidates and never interpreting the optional next slot as admission.
    expected_count = (1 if content_first or metadata == 'missing'
                      else usable_index + 1 if usable_index is not None else MAX_VISUAL_CANDIDATES)
    assert calls == (['candidate-03'] if content_first else [a.asset_id for a in assets[:expected_count]])
    assert result['material_status'] == ('MATERIAL_READY' if usable_index is not None and metadata != 'missing' else 'MATERIAL_NOT_READY')
    MaterialProductOrchestrator().observe_visual_materials(attempt['attempt_id'], executor=observe)
    assert len(calls) == expected_count
    assert not store.read_asset(assets[-1].asset_id).semantic.inferences
    observation = result['attempt']['material_observation']
    assert observation['nomination_revision'] == 'need-origin-single-batch-v5'
    expected_nominations = (1 if metadata == 'missing' else min(MAX_VISUAL_CANDIDATES,
        ((expected_count - 1) // MAX_PRIMARY_VISUAL_CANDIDATES + 1) * MAX_PRIMARY_VISUAL_CANDIDATES))
    assert observation['nominated_associations'] == expected_nominations
    assert len(observation['outcomes']) == expected_count
    progress = observation['candidate_progress'][plan.needs[0].need_id]
    assert progress['stop_reason'] == ('candidates_exhausted' if metadata == 'missing'
                                        else 'covered' if usable_index is not None
                                        else 'budget_exhausted')
    if metadata == 'missing':
        assert progress['remaining_unobserved'] == [a.asset_id for a in assets[1:]]
        assert not progress['next_candidates']
    elif usable_index is None:
        assert progress['remaining_unobserved'] == [assets[-1].asset_id]


@pytest.mark.parametrize('late_shared', [False, True])
def test_sparse_shared_observation_explores_unknown_metadata_and_skips_covered_scenes(
        material_integration_env, monkeypatch, late_shared):
    import io
    from easel.materials.application.visual_observation import SCHEMA, GROUP_SCHEMA
    attempt = material_integration_env
    root = Path(attempt['workspace']['path'])
    store = AttemptMaterialStore(root)
    plan, original, run, _, _, _ = _contracts(attempt, root)
    needs = tuple(plan.needs[0].model_copy(update={
        'need_id': f'scene-{i}', 'intent': NeedIntent(description=text),
    }) for i, text in enumerate(('keyboard typing', 'children blocks', '无标题画面')))
    plan = plan.model_copy(update={'needs': needs})
    assets = []
    for i in range(9):
        raw = io.BytesIO()
        Image.new('RGB', (32, 24), (i * 25, 0, 0)).save(raw, format='PNG')
        data = raw.getvalue()
        asset_id = f'candidate-{i:02d}'
        locator = store.write_asset_bytes(asset_id, 'frame.png', data)
        asset = original.model_copy(update={'asset_id': asset_id,
            'file': FileInfo(path=locator, sha256=hashlib.sha256(data).hexdigest(), size=len(data), mime='image/png'),
            'semantic': SemanticInfo(caption=('keyboard typing' if i < 3 else 'children blocks' if i < 6 else 'mountain snow'))})
        store.write_asset(asset)
        assets.append(asset)
    planning = PlanningIntegration().persist(attempt, plan, treatment='T', script='假设脚本内容。', scenes='S')
    plan = planning['plan']
    bundle = MaterialBundleAssembler().assemble(plan, run, tuple(assets), (), bundle_id='bundle-int-1')
    readiness, gaps = MaterialReadinessCalculator(store=store).calculate(plan, bundle)
    MaterialGateIntegration().record(planning['attempt'], plan, bundle, run, readiness, gaps)
    linked_index = 6 if late_shared else 0
    store.write_recovery_record('candidate-links', {'assets': {f'candidate-{linked_index:02d}': [
        {'need_id': n.need_id, 'need_sha256': hashlib.sha256(n.to_json().encode()).hexdigest(),
         'asset_sha256': assets[linked_index].file.sha256, 'rank': 0}
        for n in plan.needs if n.need_id in ({'scene-0', 'scene-2'} if late_shared else {'scene-2'})]}})
    from tests.material_delta_fixture import observed_result
    from easel.integrations import material_results
    groups, submitted, invocations = [], [], []

    def observe(current, group, attachments):
        groups.append([m['need']['need_id'] for m in group['observations']])
        submitted.append(group['input_sha256'])
        rows = {}
        for m in group['observations']:
            nid = m['need']['need_id']
            good = (m['asset_id'] == ('candidate-06' if late_shared else 'candidate-00') and nid in {'scene-0', 'scene-2'}
                    or m['asset_id'] == 'candidate-03' and nid == 'scene-1')
            rows[nid] = observed_result(current, m, attachments,
                outcome='suitable' if good else 'unsuitable',
                description='actual fixture frame', style='plain', invocations=invocations)
        return {'schema': GROUP_SCHEMA, 'input_sha256': group['input_sha256'], 'reports': rows}

    if late_shared:
        from easel.creation_delivery import DeliveryExecutionUncertain
        write = AttemptMaterialStore.write_observation_record
        interrupted = False
        def interrupt(self, identity, report):
            nonlocal interrupted
            if (report.get('schema') == material_results.REPORT and report.get('verdict') == 'suitable'
                    and not interrupted):
                interrupted = True
                raise DeliveryExecutionUncertain('fixture: second-round group saved before child distribution')
            return write(self, identity, report)
        monkeypatch.setattr(AttemptMaterialStore, 'write_observation_record', interrupt)
        with pytest.raises(DeliveryExecutionUncertain):
            MaterialProductOrchestrator().observe_visual_materials(attempt['attempt_id'],
                executor=lambda *_: pytest.fail('shared entry required'), group_executor=observe)
    result = MaterialProductOrchestrator().observe_visual_materials(attempt['attempt_id'],
        executor=lambda *_: pytest.fail('shared entry required'), group_executor=observe)
    for _ in range(9):
        if result['material_status'] == 'MATERIAL_READY':
            break
        result = MaterialProductOrchestrator().observe_visual_materials(attempt['attempt_id'],
            executor=lambda *_: pytest.fail('shared entry required'), group_executor=observe)
    assert result['material_status'] == 'MATERIAL_READY'
    if late_shared:
        assert submitted.count(submitted[0]) == 2  # Owner may replay the group after local interruption.
        assert len(invocations) == len(set(invocations))  # Captured Model calls do not repeat on retry.
        assert all('scene-1' not in group for group in groups[4:])  # Already covered in the first round.
        assert all(row['stop_reason'] == 'covered'
                   for row in result['attempt']['material_observation']['candidate_progress'].values())
    else:
        assert groups == [['scene-0', 'scene-2'], ['scene-1']]
        assert result['attempt']['material_observation']['nominated_associations'] == 5  # No unrelated 27-way cross-product.
    assert store.read_asset('candidate-06' if late_shared else 'candidate-00').semantic.inferences
    before = store.read_bundle()
    MaterialProductOrchestrator().observe_visual_materials(attempt['attempt_id'],
        executor=lambda *_: pytest.fail('completed evidence must be reused'), group_executor=observe)
    assert len(groups) == len(submitted)
    assert len(invocations) == len(set(invocations))
    assert store.read_bundle() == before


@pytest.mark.parametrize('outcome', ['budget', 'uncertain', 'scope_changed', 'account_changed', 'video_resume', 'video_failed', 'video_intake_resume', 'voice_preflight', 'terms_resume', 'image_ready', 'image_backlog', 'restricted_image', 'restricted_video', 'restricted_voice', 'restricted_music', 'modality_drift'])
def test_commission_generation_reserves_before_submit_and_survives_restart(material_integration_env, monkeypatch, outcome):
    import asyncio
    from io import BytesIO
    from types import SimpleNamespace
    from easel.creation_delivery import advance_creation, next_operation
    from easel.integrations import material_generation as commissioned
    from easel.runtime_config import EaselRuntimeConfig, MiniMaxRuntimeConfig
    from easel.materials.providers import minimax_pricing
    from easel.materials.providers.minimax_image import MiniMaxImageResult
    from easel.materials import providers
    from tests.test_creation_preparation import web

    attempt = material_integration_env
    is_video = outcome in {'video_resume', 'video_failed', 'video_intake_resume', 'restricted_video'}
    is_voice = outcome in {'voice_preflight', 'restricted_voice'}
    is_music = outcome == 'restricted_music'
    expected_cost = '1.650000' if is_video else '0.025000'
    plan = MaterialPlan(plan_id='commission-plan', creation_id=attempt['creation_id'], attempt_id=attempt['attempt_id'],
        needs=tuple(MaterialNeed(need_id=f'image-{i}', scope=NeedScope(
            type=NeedScopeType.EVENT if is_music and i == 1 else NeedScopeType.GLOBAL if is_voice or is_music else NeedScopeType.SCENE,
            ref=f'scene-{i}'),
            media_type=MediaType.AUDIO if is_voice or is_music else MediaType.VIDEO if is_video else MediaType.IMAGE,
            modality_spec=VoiceNeedSpec(identity=VoiceIdentityRef(source=VoiceIdentitySource.DIRECTOR_INTENT,
                reference='预置普通话')) if is_voice else (BgmNeedSpec() if i == 0 else SfxNeedSpec(event_description='雨声')) if is_music else None,
            role='主视觉', intent=NeedIntent(description=f'不同场景 {i}'),
            constraints={'allow_generation': True}, importance=NeedImportance.REQUIRED) for i in range(2)))
    planning = PlanningIntegration().persist(attempt, plan, treatment='纪实观察', script='假设场景。', scenes='两个不同场景')
    attempt.update(planning['attempt'])
    reviewed = PlanningIntegration().review_script(attempt, confirm_all_claims_reviewed=True,
        expected_script_sha256=planning['truth_ledger']['script_sha256'],
        expected_truth_packet_sha256=planning['truth_ledger']['truth_packet_sha256'])
    attempt.update(reviewed['attempt'])
    MaterialProductOrchestrator()._run(attempt, (), planning=PlanningIntegration().load(attempt))
    # A deterministic successful empty search establishes an actual shortage;
    # absence of configured providers alone must never license paid fallback.
    if not is_video and not is_voice and not is_music:
        evidence_path = AttemptMaterialStore(attempt['workspace']['path']).materials_root / 'product-supply.json'
        evidence = json.loads(evidence_path.read_text())
        for row in evidence['routing']:
            row.update(attempted_sources=['fixture-empty-search'], failures=[])
        evidence_path.write_text(json.dumps(evidence))
    attempt = service.get_film_attempt(attempt['attempt_id'])
    gate = attempt['material_gate']
    service.update_film_attempt(attempt['attempt_id'], event='fixture_only',
        autonomous_material_recovery={'status': 'COMPLETE'},
        material_observation={'status': 'COMPLETE', 'plan_revision': gate['plan_revision'], 'bundle_revision': gate['bundle_revision']})
    settings = MiniMaxRuntimeConfig(api_key='fixture-key')
    runtime = SimpleNamespace(minimax=settings)
    monkeypatch.setattr(EaselRuntimeConfig, 'load', lambda: runtime)
    quote_reads = []
    def quote_document(url):
        quote_reads.append(url)
        if url == minimax_pricing.TERMS_URL:
            if outcome == 'terms_resume' and quote_reads.count(url) == 1:
                raise minimax_pricing.GenerationQuoteReadFailed('协议页面暂时不可读')
            from tests.test_minimax_image_speech_generation import MINIMAX_TERMS_FIXTURE
            return MINIMAX_TERMS_FIXTURE
        return ('## 图像\n单价：元/张\n| image-01 | 图片 | 0.025 |\n'
                '## 视频\n**视频生成-输出价格**\n| MiniMax-H3-Max | 480P | 按秒计费 | 0.33 元/秒 |\n')
    monkeypatch.setattr(minimax_pricing, 'read_public_contract', quote_document)
    proposal = '已确认的隔离委托'
    with creation.edit_creation(attempt['creation_id']) as work:
        work['origin'] = {'type': 'chat'}
        work['chat_workflow'] = {'proposal_status': 'READY_FOR_CONFIRMATION'}
    preview = commissioned.generation_budget_preview()
    budget = {'maxCostCny': 2 if is_video else 0.06 if outcome == 'image_backlog' else 0.03, 'scopeSha256': preview['scope_sha256']}
    restricted = outcome.startswith('restricted_') or outcome == 'modality_drift'
    if restricted:
        budget['allowedModalities'] = ['voice', 'image']
    work = creation.confirm_chat_proposal(attempt['creation_id'], 'fixture-confirm',
        delivery_proposal=proposal, proposal_sha256=hashlib.sha256(proposal.encode()).hexdigest(), generation_budget=budget,
        input_use_statement_sha256=creation.input_use_preview()['statement_sha256'])
    if restricted:
        grant = work['delivery']['authorization']['material_generation']
        assert grant['allowed_modalities'] == ['image', 'voice']
        assert creation.confirm_chat_proposal(work['id'], 'same-replay', delivery_proposal=proposal,
            proposal_sha256=hashlib.sha256(proposal.encode()).hexdigest(),
            generation_budget={**budget, 'allowedModalities': ['image', 'voice']})['delivery'] == work['delivery']
        for changed in [None, ['image', 'video', 'voice'], [], ['voice', 'voice'], ['bgm']]:
            replay = {k: v for k, v in budget.items() if k != 'allowedModalities'}
            if changed is not None: replay['allowedModalities'] = changed
            with pytest.raises(creation.CreationError):
                creation.confirm_chat_proposal(work['id'], 'changed-replay', delivery_proposal=proposal,
                    proposal_sha256=hashlib.sha256(proposal.encode()).hexdigest(), generation_budget=replay)
        assert creation.get_creation(work['id'])['delivery'] == work['delivery']
    if outcome in {'restricted_video', 'restricted_music', 'modality_drift'}:
        from easel.creation_delivery import active_delivery
        from copy import deepcopy
        token = active_delivery.set(work['id'])
        try:
            if outcome in {'restricted_video', 'restricted_music'}:
                assert commissioned.pending_generated_need(work, attempt, plan) is None
                commissioned.generate_for_commission(attempt['attempt_id'])
                assert not quote_reads and not creation.get_creation(work['id'])['delivery'].get('material_generations')
            request_id = 'synthetic-restricted-receipt'
            receipt = {'status': 'reserved', 'attempt_id': attempt['attempt_id'], 'need_id': plan.needs[0].need_id,
                       'fingerprint': commissioned.commission_fingerprint(plan, '假设场景。', grant),
                       'quote': {'upper_estimate': '0.01'}}
            with creation.edit_creation(work['id']) as current:
                current['delivery'].setdefault('material_generations', {})[request_id] = receipt
                if outcome == 'modality_drift':
                    current['delivery']['authorization']['material_generation']['allowed_modalities'] = ['image']
            with pytest.raises(creation.CreationError, match='授权内'):
                commissioned.assert_commission_request(attempt, plan, '假设场景。', settings, request_id, plan.needs[0].need_id)
            if is_music:
                assert {need.modality_spec.kind for need in plan.needs} == {'bgm', 'sfx'}
                with creation.edit_creation(work['id']) as current:
                    current['delivery']['material_generations'][request_id]['need_id'] = plan.needs[1].need_id
                with pytest.raises(creation.CreationError, match='授权内'):
                    commissioned.assert_commission_request(attempt, plan, '假设场景。', settings, request_id, plan.needs[1].need_id)
            assert not quote_reads
            if outcome == 'restricted_video':
                assert all(n.importance.value == 'required' and n.media_type.value == 'video' for n in plan.needs)
            damaged = deepcopy(grant); del damaged['allowed_modalities']
            with pytest.raises(creation.CreationError): commissioned.authorized_generation_modalities(damaged)
        finally:
            active_delivery.reset(token)
        return
    if outcome in {'image_ready', 'image_backlog'}:
        from easel.creation_delivery import set_material_endpoint
        set_material_endpoint(work['id'])
        monkeypatch.setattr(ProductionAuthoringIntegration, 'prepare',
                            lambda *a, **kw: pytest.fail('material endpoint must not prepare Authoring'))
        from tests.test_minimax_image_speech_generation import MINIMAX_TERMS_FIXTURE
        monkeypatch.setattr(commissioned, 'MINIMAX_INTERNAL_TERMS_SHA256', minimax_pricing.usage_terms_evidence(quote_document)['sha256'])
    # Replayed confirmation cannot increase or retrofit an authorization.
    with pytest.raises(creation.CreationError, match='扩大素材预算'):
        creation.confirm_chat_proposal(work['id'], 'replayed', delivery_proposal=proposal,
            proposal_sha256=hashlib.sha256(proposal.encode()).hexdigest(), generation_budget={**budget, 'maxCostCny': 1})
    with pytest.raises(creation.CreationError, match='后台交付者'):
        commissioned.generate_for_commission(attempt['attempt_id'])
    if is_voice:
        from easel.creation_delivery import active_delivery
        runtime.get = lambda *args: str(Path(attempt['workspace']['path']) / 'absent-asr-model')
        monkeypatch.setattr(MaterialProductOrchestrator, 'generate_minimax_asset',
                            lambda *a, **kw: pytest.fail('missing observation must stop before paid TTS'))
        token = active_delivery.set(work['id'])
        try:
            with pytest.raises(ValueError, match='本地语音识别模型未就绪'):
                commissioned.generate_for_commission(attempt['attempt_id'])
                latest_gate = service.get_film_attempt(attempt['attempt_id'])['material_gate']
                service.update_film_attempt(attempt['attempt_id'], event='fixture_queued_receipt',
                    material_observation={'status': 'COMPLETE', 'plan_revision': latest_gate['plan_revision'],
                                          'bundle_revision': latest_gate['bundle_revision']})
        finally:
            active_delivery.reset(token)
        assert not quote_reads and not creation.get_creation(work['id'])['delivery'].get('material_generations')
        return

    media = BytesIO()
    Image.new('RGB', (64, 64), 'teal').save(media, format='PNG')
    calls, dispatches = [], []
    class FakeImage:
        model = 'image-01'
        def __init__(self, *args, **kwargs):
            pass
        def generate(self, prompt, **kwargs):
            snapshot = creation.get_creation(work['id'])['delivery']
            reservation = list(snapshot['material_generations'].values())[-1]
            assert reservation['status'] == 'reserved' and reservation['quote']['upper_estimate'] == '0.025000'
            calls.append(prompt)
            if outcome == 'uncertain':
                raise TimeoutError('fixture lost synchronous response')
            if outcome == 'image_backlog':
                raw = BytesIO()
                Image.new('RGB', (64, 64), (0, len(calls) * 70, 70)).save(raw, format='PNG')
                return MiniMaxImageResult(self.model, raw.getvalue())
            return MiniMaxImageResult(self.model, media.getvalue())
    monkeypatch.setattr(providers, 'MiniMaxImageAdapter', FakeImage)
    if is_video:
        from easel.materials.application import generation as video_generation
        from easel.materials.providers.minimax_video import MiniMaxVideoAdapter
        from easel.materials.providers.http_support import HttpResponse
        class FakeVideo(MiniMaxVideoAdapter):
            model = 'MiniMax-H3-Max'
            waits = []
            def __init__(self, *args, **kwargs):
                clock = [0.]
                def sleep(seconds):
                    clock[0] += seconds
                super().__init__('fixture-key', transport=self, timeout_seconds=1,
                                 poll_interval_seconds=1, monotonic=lambda: clock[0], sleep=sleep)
            def get(self, url, **kwargs):
                if outcome == 'video_failed':
                    return HttpResponse(200, {}, json.dumps({'task': {'id': 'fixture-paid-video', 'status': 'failed'}}).encode())
                if outcome != 'video_intake_resume' and len(self.waits) in (2, 4):
                    raise TimeoutError('fixture query connection interrupted')
                task = {'id': 'fixture-paid-video', 'status': 'succeeded' if outcome == 'video_intake_resume' else 'queued' if len(self.waits) == 1 else 'running' if len(self.waits) < 5 else 'succeeded',
                        'content': {'url': 'https://video-product.cdn.minimax.io/fixture.mp4'}}
                return HttpResponse(200, {}, json.dumps({'task': task}).encode())
            def submit(self, prompt, **kwargs):
                record = list(creation.get_creation(work['id'])['delivery']['material_generations'].values())[0]
                assert record['status'] == 'reserved' and record['quote']['upper_estimate'] == expected_cost
                calls.append(prompt)
                return SimpleNamespace(task_id='fixture-paid-video')
            def wait(self, task_id):
                self.waits.append(task_id)
                return super().wait(task_id)
        class LocalAcquirer:
            def __init__(self, store):
                self.store = store
            def acquire(self, candidate):
                body = b'fixture-only-video-intake'
                if outcome == 'video_resume':
                    import subprocess
                    fixture_video = Path(attempt['workspace']['path']) / 'fixture-video.mp4'
                    subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-f', 'lavfi',
                        '-i', 'color=c=teal:s=64x64:r=10:d=5', '-an', '-c:v', 'libx264',
                        str(fixture_video)], check=True, capture_output=True, timeout=20)
                    body = fixture_video.read_bytes()
                path = self.store.write_asset_bytes('fixture-video', 'original.mp4', body)
                asset = MaterialAsset(asset_id='fixture-video', media_type=MediaType.VIDEO,
                    file=FileInfo(path=path, sha256=hashlib.sha256(body).hexdigest(), size=len(body), mime='video/mp4'),
                    source=candidate.source, rights=RightsInfo(status=RightsStatus.UNKNOWN),
                    technical=TechnicalInfo(status=TechnicalStatus.PENDING if outcome == 'video_intake_resume' else TechnicalStatus.PASSED, mime='video/mp4', duration_seconds=5))
                self.store.write_asset(asset)
                return asset
        monkeypatch.setattr(providers, 'MiniMaxVideoAdapter', FakeVideo)
        monkeypatch.setattr(video_generation, 'create_material_generation_acquirer', LocalAcquirer)
        def inspected_fixture(store):
            def inspect_and_persist(asset):
                store.write_asset(asset)
                return asset
            return SimpleNamespace(inspect_and_persist=inspect_and_persist)
        monkeypatch.setattr(video_generation, 'TechnicalInspector', inspected_fixture)
        if outcome == 'video_intake_resume':
            from easel.materials.application import generation_modalities
            class Inspector:
                calls = 0
                def __init__(self, store): self.store = store
                def inspect_and_persist(self, asset):
                    type(self).calls += 1
                    if self.calls == 1:
                        raise OSError('fixture local inspector interrupted after video receipt')
                    checked = asset.model_copy(update={'technical': asset.technical.model_copy(update={'status': TechnicalStatus.PASSED})})
                    self.store.write_asset(checked)
                    return checked
            monkeypatch.setattr(video_generation, 'TechnicalInspector', Inspector)
            monkeypatch.setattr(generation_modalities, 'TechnicalInspector', Inspector)
    original = MaterialProductOrchestrator.generate_minimax_asset
    def interrupted(self, *args, **kwargs):
        dispatches.append(kwargs['request_id'])
        if len(dispatches) == 1 and outcome == 'budget':
            raise OSError('fixture restart after reservation, before submission')
        if outcome == 'scope_changed':
            runtime.minimax = MiniMaxRuntimeConfig(api_key='fixture-key', speech_voice_id='another-preset')
        elif outcome == 'account_changed':
            runtime.minimax = MiniMaxRuntimeConfig(api_key='fixture-other-key')
        return original(self, *args, **kwargs)
    monkeypatch.setattr(MaterialProductOrchestrator, 'generate_minimax_asset', interrupted)
    async def execute(operation, current):
        if operation == 'generate_material':
            await web._execute_creation_delivery(operation, current)
        elif operation == 'finish_material_generation':
            assert outcome == 'video_intake_resume'
            with monkeypatch.context() as isolated:
                isolated.setattr(EaselRuntimeConfig, 'load', lambda: pytest.fail('local receipt recovery cannot load Provider credentials'))
                await web._execute_creation_delivery(operation, current)
        elif operation == 'observe_material':
            if not is_video and not is_voice:
                from easel.materials.application.visual_observation import SCHEMA
                if outcome in {'image_ready', 'image_backlog'}:
                    # Old, unobserved stock remains in the pool after fallback;
                    # its sort order must not delay the newly paid asset intake.
                    intake_store = AttemptMaterialStore(attempt['workspace']['path'])
                    bundle = intake_store.read_bundle()
                    generated = next(a for a in bundle.assets if not a.semantic.inferences and a.source.kind == 'generative')
                    # Historical stock spending cannot strand a paid fallback.
                    budget_key = 'visual-budget-' + MaterialReadinessCalculator.plan_revision(
                        PlanningIntegration().load(service.get_film_attempt(attempt['attempt_id']))['plan'])
                    spent = [f'old-stock-{i}:sha' for i in range(23)]
                    if not intake_store.read_recovery_record(budget_key):
                        intake_store.write_recovery_record(budget_key, {'associations': {n.need_id: list(spent) for n in plan.needs}})
                    old_id = 'asset-000-old-stock' + ('-' + generated.asset_id if outcome == 'image_backlog' else '')
                    old_locator = intake_store.write_asset_bytes(old_id, 'fixture.png',
                        intake_store.resolve_asset_locator(generated.file.path).read_bytes())
                    old_stock = generated.model_copy(update={'asset_id': old_id,
                        'file': generated.file.model_copy(update={'path': old_locator}),
                        'source': generated.source.model_copy(update={
                            'kind': type(generated.source.kind)('stock'), 'provider': 'fixture-stock',
                            'provider_asset_id': 'unrelated-old'})})
                    intake_store.write_asset(old_stock)
                    intake_store.write_bundle(bundle.model_copy(update={'assets': (*bundle.assets, old_stock)}))
                from tests.material_delta_fixture import observed_result
                def rejected_scene(current, manifest, attachments):
                    if outcome in {'image_ready', 'image_backlog'}:
                        assert manifest['asset_id'] == generated.asset_id
                    return observed_result(current, manifest, attachments,
                        outcome='suitable' if outcome in {'image_ready', 'image_backlog'} else 'unsuitable',
                        description='actual teal field')
                MaterialProductOrchestrator().observe_visual_materials(attempt['attempt_id'], executor=rejected_scene)
                if outcome in {'image_ready', 'image_backlog'}:
                    spending = intake_store.read_recovery_record(budget_key)
                    nid = next(r['need_id'] for r in intake_store.list_generation_records() if r['asset_id'] == generated.asset_id)
                    assert spending['associations'][nid] == spent
                    assert spending['generated_intakes'][nid] == [generated.asset_id + ':' + generated.file.sha256]
                return
            latest = service.get_film_attempt(attempt['attempt_id'])['material_gate']
            service.update_film_attempt(attempt['attempt_id'], event='fixture_observation',
                material_observation={'status': 'COMPLETE', 'plan_revision': latest['plan_revision'], 'bundle_revision': latest['bundle_revision']})
        else:
            pytest.fail(operation)
    if outcome == 'image_backlog':
        from easel.creation_delivery import active_delivery
        token = active_delivery.set(work['id'])
        try:
            for _ in range(2):
                commissioned.generate_for_commission(attempt['attempt_id'])
        finally:
            active_delivery.reset(token)
    for step in range(10):
        asyncio.run(advance_creation(work['id'], execute))
        if outcome == 'terms_resume' and step == 0:
            assert not calls
            assert not creation.get_creation(work['id'])['delivery'].get('material_generations')
            assert not AttemptMaterialStore(attempt['workspace']['path']).list_generation_records()
        if outcome == 'video_resume' and step < 4:
            progress = creation.get_creation(work['id'])['delivery']
            assert progress['status'] == ('generating_material' if step % 2 == 0 else 'observation_failed')
            assert not progress.get('failures') and not progress.get('exhausted_operation')
            record = AttemptMaterialStore(attempt['workspace']['path']).list_generation_records()[0]
            assert record['status'] == 'RUNNING' and record['last_provider_status'] == ('queued' if step < 2 else 'running')
            assert len(calls) == 1 and len(quote_reads) == 2
            assert all(row['status'] == 'reserved' for row in progress['material_generations'].values())
    current = creation.get_creation(work['id'])
    ledger = list(current['delivery']['material_generations'].values())
    assert sum(float(r['quote']['upper_estimate']) for r in ledger if r.get('quote')) == float(expected_cost) * (2 if outcome == 'image_backlog' else 1)
    if outcome in {'image_ready', 'image_backlog'}:
        assert not current['delivery'].get('last_error'), current['delivery'].get('last_error')
        if outcome == 'image_backlog':
            assert len(calls) == 2 and {r['status'] for r in ledger} == {'complete'}
            assert next_operation(current) == (None, 'material_ready')
            spending = AttemptMaterialStore(attempt['workspace']['path']).read_recovery_record(
                'visual-budget-' + MaterialReadinessCalculator.plan_revision(
                    PlanningIntegration().load(service.get_film_attempt(attempt['attempt_id']))['plan']))
            assert all(entries == [f'old-stock-{i}:sha' for i in range(23)]
                       for entries in spending['associations'].values())
            return
        assert len(calls) == 1
        assert {r['status'] for r in ledger} == {'complete', 'budget_exceeded'}
        assert next_operation(current) == (None, 'needs_generation_approval')
        assert 'material_endpoint_result' not in current['delivery']
        assert current['status'] != 'ready' and not current.get('selected_output_name')
        admitted_assets = AttemptMaterialStore(attempt['workspace']['path']).read_bundle().assets
        assert next(a for a in admitted_assets if a.source.kind == 'generative').rights.status is RightsStatus.KNOWN
        old_stock = next(a for a in admitted_assets if a.asset_id == 'asset-000-old-stock')
        assert old_stock.rights.status is RightsStatus.UNKNOWN and not old_stock.semantic.inferences
        return
    if outcome in {'scope_changed', 'account_changed'}:
        assert not calls and current['delivery']['status'] == 'failed'
    elif outcome == 'video_failed':
        assert len(calls) == 1 and current['delivery']['status'] == 'failed'
        assert current['delivery']['failures'][attempt['attempt_id'] + ':generate_material'] == 3
        assert {r['status'] for r in ledger} == {'reserved'}
    else:
        assert len(calls) == 1  # the second Need cannot exceed the remaining budget
        assert 'budget_exceeded' in {r['status'] for r in ledger}
        assert next_operation(current)[1] == ('material_submission_uncertain' if outcome == 'uncertain' else 'needs_generation_approval')
    store = AttemptMaterialStore(attempt['workspace']['path'])
    if outcome in {'budget', 'video_resume', 'video_intake_resume', 'terms_resume'}:
        if outcome == 'terms_resume':
            assert len(dispatches) == 1  # Retrying the public read never dispatches a paid request.
        elif outcome != 'video_intake_resume':
            assert dispatches[0] == dispatches[1]
        else:
            assert len(dispatches) == 1 and Inspector.calls == 2
        record = store.list_generation_records()[0]
        assert record['operator_confirmed_paid'] is False
        assert record['commission_authorization']['source'] == 'commission_budget'
        assert len(store.read_bundle().assets) == 1
        assert store.read_bundle().assets[0].rights.status is RightsStatus.UNKNOWN
        asset = store.read_bundle().assets[0]
        terms = record['commission_authorization']['quote']['terms_evidence']
        assert terms['sha256'] == hashlib.sha256(terms['document'].encode()).hexdigest()
        assert asset.rights.evidence[0].reference.endswith(terms['sha256'])
        assert asset.rights.evidence[1].reference.endswith(asset.file.sha256)
        assert record['commission_authorization']['input_use']['creation_id'] == work['id']
        if outcome == 'video_resume':
            from copy import deepcopy
            from easel.creation_delivery import active_delivery
            from easel.materials.application.visual_observation import SCHEMA
            monkeypatch.setattr(commissioned, 'MINIMAX_INTERNAL_TERMS_SHA256', terms['sha256'])
            observed = []
            from tests.material_delta_fixture import observed_result
            def observe(current, manifest, attachments):
                observed.append(manifest['input_sha256'])
                assert attachments
                return observed_result(current, manifest, attachments,
                    outcome='suitable', description='均匀青绿色画面',
                    note='帧内容已核验')
            assert commissioned.commission_generated_rights(current, plan, plan.needs[0], asset,
                record, '假设场景。') is None  # Generation success cannot stand in for observation.
            MaterialProductOrchestrator().observe_visual_materials(attempt['attempt_id'], executor=observe)
            assert store.read_asset(asset.asset_id).rights.status is RightsStatus.UNKNOWN  # No owner authority.
            before_observations = len(observed)
            token = active_delivery.set(work['id'])
            try:
                admitted_result = MaterialProductOrchestrator().observe_visual_materials(attempt['attempt_id'], executor=observe)
            finally:
                active_delivery.reset(token)
            admitted = store.read_asset(asset.asset_id)
            assert admitted.rights.status is RightsStatus.KNOWN
            assert set(admitted.rights.usage_constraints) == {'internal_production_only', 'current_creation_only'}
            assert len(observed) == before_observations and len(calls) == 1
            assert admitted_result['material_status'] == 'MATERIAL_NOT_READY'
            assert plan.needs[1].need_id in admitted_result['attempt']['material_gate']['blocking_needs']
            unassessed = admitted.model_copy(update={'rights': asset.rights})
            assert commissioned.commission_generated_rights(current, plan, plan.needs[0], unassessed,
                record, '假设场景。') is not None
            for fault in ('old_declaration', 'prompt', 'model', 'restricted'):
                changed_work, changed_record, changed_asset = deepcopy(current), deepcopy(record), unassessed
                if fault == 'old_declaration':
                    declaration = changed_work['delivery']['authorization']['input_use']
                    declaration.update(creation.input_use_preview(version=1))
                    changed_record['commission_authorization']['input_use'] = deepcopy(declaration)
                elif fault == 'prompt':
                    changed_record['prompt_sha256' if is_video else 'input_sha256'] = '0' * 64
                elif fault == 'model':
                    changed_record['model'] = 'unsupported-model'
                else:
                    changed_asset = unassessed.model_copy(update={'rights': RightsInfo(status=RightsStatus.RESTRICTED)})
                assert commissioned.commission_generated_rights(changed_work, plan, plan.needs[0], changed_asset,
                    changed_record, '假设场景。') is None, fault
    if is_video:
        assert FakeVideo.waits == ['fixture-paid-video'] * (3 if outcome == 'video_failed' else 1 if outcome == 'video_intake_resume' else 5)
        assert len(quote_reads) == (2 if outcome == 'video_failed' else 4)  # Price/terms per initial Need, never on task observation.


@pytest.mark.parametrize('provider_timing', [False, True, 'bounded_cached'])
def test_missing_voice_timing_recovers_from_saved_audio_without_rebuying(material_integration_env, monkeypatch, provider_timing):
    import asyncio
    from copy import deepcopy
    from types import SimpleNamespace
    from easel.creation_delivery import advance_creation, next_operation
    from easel.materials.application import voice_delivery

    attempt = material_integration_env
    bounded_cached = provider_timing == 'bounded_cached'
    provider_timing = provider_timing is True
    script = '每天整理纸面上的重要记录。' * 8 if bounded_cached else '假设清晨。窗边很安静。'
    need = MaterialNeed(need_id='voice', scope=NeedScope(type=NeedScopeType.GLOBAL, ref='film'),
        media_type=MediaType.AUDIO, role='旁白', intent=NeedIntent(description='清晰平静的旁白'),
        importance=NeedImportance.REQUIRED, modality_spec=VoiceNeedSpec(identity=VoiceIdentityRef(
            source=VoiceIdentitySource.EXPLICIT_USER, reference='普通话预置音色')))
    plan = MaterialPlan(plan_id='voice-recovery', creation_id=attempt['creation_id'],
                        attempt_id=attempt['attempt_id'], needs=(need,))
    planning = PlanningIntegration().persist(attempt, plan, treatment='平静观察', script=script, scenes='两个场景')
    plan, attempt, need = planning['plan'], planning['attempt'], planning['plan'].needs[0]
    store = AttemptMaterialStore(attempt['workspace']['path'])
    body = b'isolated-saved-voice-fixture'
    path = store.write_asset_bytes('voice', 'original.mp3', body)
    asset = MaterialAsset(asset_id='voice', media_type=MediaType.AUDIO,
        file=FileInfo(path=path, sha256=hashlib.sha256(body).hexdigest(), size=len(body), mime='audio/mpeg'),
        source=CandidateSource(kind='generative', provider='minimax', provider_asset_id='gen-voice'),
        rights=RightsInfo(status=RightsStatus.UNKNOWN),
        technical=TechnicalInfo(status=TechnicalStatus.PASSED, duration_seconds=5, mime='audio/mpeg'))
    store.write_asset(asset)
    run = SupplyRun(supply_run_id='voice-recovery', plan_id=plan.plan_id,
        started_at=datetime.now(timezone.utc), finished_at=datetime.now(timezone.utc), result_bundle_id='bundle')
    bundle = MaterialBundleAssembler().assemble(plan, run, (asset,), (), bundle_id='bundle')
    readiness, gaps = MaterialReadinessCalculator(store=store).calculate(plan, bundle)
    MaterialGateIntegration().record(attempt, plan, bundle, run, readiness, gaps)
    generation = {'schema': 'easel-material-generation@1', 'generation_id': 'gen-voice', 'status': 'COMPLETE',
        'plan_revision': MaterialReadinessCalculator.plan_revision(plan),
        'modality': 'voice', 'attempt_id': attempt['attempt_id'], 'plan_id': plan.plan_id,
        'need_id': need.need_id, 'need_sha256': hashlib.sha256(need.to_json().encode()).hexdigest(),
        'input_sha256': hashlib.sha256(script.encode()).hexdigest(),
        'asset_id': asset.asset_id, 'asset_sha256': asset.file.sha256, 'asset_path': path, 'asset_bytes': len(body),
        'voice_timing': voice_delivery.bind_voice_timing(script, asset, (), 'provider_timing_missing_or_invalid')}
    if provider_timing:
        generation['voice_timing'] = voice_delivery.bind_voice_timing(script, asset, ({
            'text': script, 'start_character': 0, 'end_character': len(script),
            'start_seconds': .1, 'end_seconds': 4.9},))
    store.write_generation_record('gen-voice', generation)
    with creation.edit_creation(attempt['creation_id']) as work:
        work['origin'] = {'type': 'chat'}
        work['chat_workflow'] = {'proposal_status': 'READY_FOR_CONFIRMATION'}
    work = creation.confirm_chat_proposal(attempt['creation_id'], 'fixture', delivery_proposal=script,
                                          proposal_sha256=hashlib.sha256(script.encode()).hexdigest())
    report = {'engine': 'fixture-asr', 'words': [
        {'text': '假設', 'start_seconds': .15, 'end_seconds': .7, 'probability': .95},
        {'text': '清晨。', 'start_seconds': .7, 'end_seconds': 1.5, 'probability': .9},
        {'text': '窗邊', 'start_seconds': 2., 'end_seconds': 3., 'probability': .96},
        {'text': '很安靜。', 'start_seconds': 3., 'end_seconds': 4.8, 'probability': .99}]}
    if bounded_cached:
        characters = voice_delivery._spoken(script)
        report['words'] = [{'text': c, 'start_seconds': .15 + i * 4.6 / len(characters),
                            'end_seconds': .15 + (i + 1) * 4.6 / len(characters),
                            'probability': .282 if i == 0 else .97} for i, c in enumerate(characters)]
    original_report = deepcopy(report)
    recognized = voice_delivery.timing_from_recognition(script, asset, report)
    if not bounded_cached:
        assert [(r['start_seconds'], r['end_seconds']) for r in recognized['cues']] == [(.15, 1.5), (2., 4.8)]
    assert report == original_report  # Original ASR evidence must remain unchanged.
    if not bounded_cached:
        assert [c['text'] for c in recognized['cues']] == ['假设清晨', '窗边很安静']
        reverse_report = deepcopy(report)
        for word, text in zip(reverse_report['words'], ('假设', '清晨。', '窗边', '很安静。')):
            word['text'] = text
        reverse = voice_delivery.timing_from_recognition('假設清晨。窗邊很安靜。', asset, reverse_report)
        assert [c['text'] for c in reverse['cues']] == ['假設清晨', '窗邊很安靜']
    # Provider alignment keeps its strict text contract; normalization is ASR-only.
    assert voice_delivery.bind_voice_timing(script, asset, ({'text': '假設清晨。窗邊很安靜。',
        'start_character': 0, 'end_character': len(script), 'start_seconds': .15,
        'end_seconds': 4.8},))['status'] == 'INVALID'
    for invalid in (() if bounded_cached else ('mismatch', 'homophone', 'extra', 'truncated', 'overlap', 'confidence')):
        bad = deepcopy(report)
        if invalid == 'mismatch': bad['words'][0]['text'] = '真的'
        if invalid == 'homophone': bad['words'][0]['text'] = '假攝'
        if invalid == 'extra': bad['words'][-1]['text'] += '啊'
        if invalid == 'truncated': bad['words'].pop()
        if invalid == 'overlap': bad['words'][1]['start_seconds'] = .2
        if invalid == 'confidence': bad['words'][0]['probability'] = .2
        message = '本地旁白识别置信度不足' if invalid == 'confidence' else '脚本之外的多余内容' if invalid == 'extra' else None
        with pytest.raises(ValueError, match=message):
            voice_delivery.timing_from_recognition(script, asset, bad)
    calls = []
    def recognize(file, language):
        calls.append(file)
        assert file.read_bytes() == body and language is None
        return deepcopy(report)
    verification = {'model_sha256': 'a' * 64, 'rules': 'fixture-v1'}
    monkeypatch.setattr(voice_delivery, 'voice_verification_identity', lambda *a: dict(verification))
    monkeypatch.setattr(voice_delivery, 'read_local_voice', recognize)
    if bounded_cached:
        binding = {'audio_sha256': asset.file.sha256, 'script_sha256': hashlib.sha256(script.encode()).hexdigest(),
                   'need_sha256': hashlib.sha256(need.to_json().encode()).hexdigest()}
        cached = {**deepcopy(report), **binding, 'verification_config': verification}
        primary_key = 'voice-primary-' + hashlib.sha256(json.dumps({**binding, 'verification': verification}, sort_keys=True).encode()).hexdigest()
        store.write_recovery_record(primary_key, cached)
        old_key = 'voice-failure-voice-asr-' + voice_delivery.recognition_digest(
            {**binding, 'verification': verification, 'supplement': 'unconfigured_or_unverified'})
        old_failure = {'reason': 'fixture old 0.5 rejection', 'recognition_sha256': voice_delivery.recognition_digest(cached)}
        store.write_recovery_record(old_key, old_failure)
        monkeypatch.setattr(voice_delivery, 'read_local_voice', lambda *a: pytest.fail('reuse original recognition, no new ASR'))
        from easel.materials.application import voice_supplement
        monkeypatch.setattr(voice_supplement, 'configured_supplement', lambda: pytest.fail('no second model'))
    if provider_timing:
        wrong = deepcopy(report)
        wrong['words'][0]['text'] = '真的'
        monkeypatch.setattr(voice_delivery, 'read_local_voice', lambda *a: wrong)
        with pytest.raises(ValueError, match='旁白识别文字与冻结脚本不一致'):
            MaterialProductOrchestrator().recover_voice_timing(attempt['attempt_id'])
        assert store.read_generation_record('gen-voice') == generation
        assert store.read_asset('voice') == asset and store.read_bundle() == bundle
        observation_dir = Path(attempt['workspace']['path']) / 'materials/observations'
        rejected = list(observation_dir.glob('voice-asr-rejected-*.json'))
        assert len(rejected) == 1 and json.loads(rejected[0].read_text())['words'][0]['text'] == '真的'
        assert not list(observation_dir.glob('voice-asr-' + '?' * 64 + '.json'))
        monkeypatch.setattr(voice_delivery, 'read_local_voice', lambda *a: pytest.fail('same-condition failure must be cached'))
        with pytest.raises(MaterialIntegrationError, match='同一音频和验证配置'):
            MaterialProductOrchestrator().recover_voice_timing(attempt['attempt_id'])
        verification['model_sha256'] = 'b' * 64
        monkeypatch.setattr(voice_delivery, 'read_local_voice', recognize)
    monkeypatch.setattr(MaterialProductOrchestrator, 'generate_minimax_asset',
                        lambda *a, **kw: pytest.fail('recovery must never purchase new audio'))
    write_record = AttemptMaterialStore.write_generation_record
    writes = []
    def interrupt(store, generation_id, value):
        writes.append(generation_id)
        if len(writes) == 1:
            raise OSError('fixture crash after recognition checkpoint')
        return write_record(store, generation_id, value)
    monkeypatch.setattr(AttemptMaterialStore, 'write_generation_record', interrupt)
    async def execute(operation, current):
        assert operation == 'recover_voice_timing'
        await asyncio.to_thread(MaterialProductOrchestrator().recover_voice_timing, attempt['attempt_id'])
    assert next_operation(work)[0] == 'recover_voice_timing'
    asyncio.run(advance_creation(work['id'], execute))
    asyncio.run(advance_creation(work['id'], execute))
    assert len(calls) == (0 if bounded_cached else 1) and len(writes) == 2
    assert next_operation(creation.get_creation(work['id']))[0] != 'recover_voice_timing'
    recovered = store.read_generation_record('gen-voice')
    if bounded_cached:
        assert recovered['voice_recognition'] == cached
        assert store.read_recovery_record(old_key) == old_failure
        assert recovered['voice_timing']['confidence_acceptance']['minimum_word_probability'] == .282
    assert recovered['provider_voice_timing'] == generation['voice_timing']
    assert recovered['voice_timing']['source'] == ('provider_alignment' if provider_timing else 'local_asr')
    if provider_timing:
        assert recovered['voice_timing'] == generation['voice_timing']
    observed = store.read_asset('voice')
    assert store.read_bundle().assets == (observed,)
    assert observed.file == asset.file and observed.rights.status is RightsStatus.UNKNOWN
    assert voice_delivery.voice_content_observed(need, observed)
    from easel.materials.application.matching import MaterialMatcher
    assert not MaterialMatcher().match(need, (observed,)).matches  # ASR cannot grant Rights.
    admitted = observed.model_copy(update={'rights': RightsInfo(status=RightsStatus.KNOWN,
        license_name='Fixture License', evidence=(RightsEvidence(kind='asset_license', reference='fixture://voice'),))})
    assert MaterialMatcher().match(need, (admitted,)).matches[0].reasons[1] == 'system_voice_content=complete'
    for stale in (need.model_copy(update={'intent': NeedIntent(description='另一项声音要求')}),
                  need.model_copy(update={'modality_spec': need.modality_spec.model_copy(update={'text_sha256': '0' * 64})})):
        assert not MaterialMatcher().match(stale, (admitted,)).matches
    assert not voice_delivery.voice_content_observed(need, observed.model_copy(update={
        'file': observed.file.model_copy(update={'sha256': '0' * 64})}))
    # Provider alignment alone is not independently observed content.
    assert not voice_delivery.voice_content_observed(need, asset)
    from easel.materials.application.voice_delivery import authoring_voice_timings
    qualified = SimpleNamespace(assets=(asset,), matches=(MaterialMatch(
        need_id='voice', asset_id='voice', rank=1, score=1, qualified=True),))
    projected = authoring_voice_timings(plan, qualified, store, script)
    assert projected['assets'][0]['source'] == 'local_asr'
    assert len(projected['assets'][0]['cues']) > 1  # Already observed finer timing, no new ASR or TTS.
    assert ''.join(c['display_text'] for c in projected['assets'][0]['cues']) == script
    recovered['voice_recognition']['audio_sha256'] = '0' * 64
    write_record(store, 'gen-voice', recovered)
    if not provider_timing:
        assert authoring_voice_timings(plan, qualified, store, script)['unavailable_need_ids'] == ['voice']
    assert voice_delivery.pending_voice_timing_recovery(plan, store.read_bundle(), store, script, require_content=True)
    if provider_timing:
        # Formal listening review resolves only named ASR characters, keeping the
        # raw report and measured times. Generic captions cannot approve it.
        bad = {**deepcopy(report), 'audio_sha256': asset.file.sha256,
               'script_sha256': hashlib.sha256(script.encode()).hexdigest(),
               'need_sha256': hashlib.sha256(need.to_json().encode()).hexdigest()}
        bad['words'][0]['text'] = '真的'
        digest = voice_delivery.recognition_digest(bad)
        store.write_observation_record('voice-asr-rejected-' + digest, bad)
        request = dict(asset_id=asset.asset_id, expected_sha256=asset.file.sha256, need_id=need.need_id,
                       observed_content='已试听：前两个字是冻结原文假设，不是识别器输出的真的',
                       logo_present=None, visible_text_present=None, confirm_review=True)
        original = store.read_asset('voice')
        for invalid in ({'recognition_sha256': '0' * 64, 'corrections': [{'character': 0, 'text': '假'}]},
                        {'recognition_sha256': digest, 'corrections': [{'character': 0, 'text': '改'}]},
                        {'recognition_sha256': digest, 'corrections': [{'character': 0, 'text': '假'}]}):
            with pytest.raises((MaterialIntegrationError, ValueError)):
                MaterialProductOrchestrator().review_material_match(attempt['attempt_id'], **request,
                    voice_recognition_review=invalid)
            assert store.read_asset('voice') == original
        from fastapi.testclient import TestClient
        from web.app import app
        client = TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 50000),
                            headers={'Origin': 'http://127.0.0.1'})
        assert client.post('/api/operator/session').status_code == 200
        response = client.post(f"/api/film-attempts/{attempt['attempt_id']}/material-match/review-current", json={
            'assetId': asset.asset_id, 'assetSha256': asset.file.sha256, 'needId': need.need_id,
            'observedContent': request['observed_content'], 'confirmReview': True,
            'voiceRecognitionReview': {'recognition_sha256': digest,
                'corrections': [{'character': 0, 'text': '假'}, {'character': 1, 'text': '设'}]}})
        assert response.status_code == 200, response.text
        approved = store.read_asset('voice')
        assert voice_delivery.timing_from_recognition(script, approved, bad)['status'] == 'READY'
        assert store.read_asset('voice').rights.status is RightsStatus.UNKNOWN
        for key in ('audio_sha256', 'script_sha256', 'need_sha256'):
            changed = deepcopy(bad); changed[key] = '0' * 64
            with pytest.raises(ValueError):
                voice_delivery.timing_from_recognition(script, approved, changed)
        changed = deepcopy(bad); changed['words'][0]['probability'] = .2
        with pytest.raises(ValueError):
            voice_delivery.timing_from_recognition(script, approved, changed)
        failed = deepcopy(generation)
        write_record(store, 'gen-voice', failed)
        for checkpoint in observation_dir.glob('voice-asr-' + '?' * 64 + '.json'):
            checkpoint.unlink()
        monkeypatch.setattr(voice_delivery, 'read_local_voice', lambda *a: pytest.fail('approved report must be reused'))
        MaterialProductOrchestrator().recover_voice_timing(attempt['attempt_id'])
        reused = store.read_generation_record('gen-voice')['voice_recognition']
        assert voice_delivery.timing_from_recognition(script, approved, reused)['status'] == 'READY'
        assert not voice_delivery.pending_voice_timing_recovery(plan, store.read_bundle(), store, script, require_content=True)


@pytest.mark.parametrize('optional_shot', [False, True, 'audio', 'audio_used_visual'])
def test_visual_supply_continues_once_after_rejection_and_stops_as_system_gap(material_integration_env, monkeypatch, optional_shot):
    from easel.creation_delivery import SCHEMA, next_operation
    from easel.integrations import material_recovery as recovery
    attempt = material_integration_env
    planning = _planning(attempt)
    plan = planning['plan']
    if optional_shot is True:
        need = plan.needs[0].model_copy(update={'constraints': {'preferred_visual_details': '远景与背景灯光可取舍'}})
        plan = plan.model_copy(update={'needs': (need,)})
        PlanningIntegration().persist(attempt, plan, treatment='T', script='假设脚本内容。\n', scenes='S')
    if optional_shot == 'audio_used_visual':
        from easel.materials.domain import BgmNeedSpec
        bgm = plan.needs[0].model_copy(update={'need_id': 'bgm-used', 'media_type': MediaType.AUDIO,
            'constraints': {}, 'modality_spec': BgmNeedSpec(instruments=('piano',), vocals_allowed=False),
            'intent': NeedIntent(description='gentle piano instrumental')})
        plan = plan.model_copy(update={'needs': (*plan.needs, bgm)})
        PlanningIntegration().persist(attempt, plan, treatment='T', script='假设脚本内容。\n', scenes='S')
    if optional_shot == 'audio':
        from easel.materials.domain import BgmNeedSpec
        need = plan.needs[0].model_copy(update={'media_type': MediaType.AUDIO, 'constraints': {},
            'modality_spec': BgmNeedSpec(instruments=('piano',), vocals_allowed=False),
            'intent': NeedIntent(description='gentle piano instrumental')})
        plan = plan.model_copy(update={'needs': (need,)})
        PlanningIntegration().persist(attempt, plan, treatment='T', script='假设脚本内容。\n', scenes='S')
    store = AttemptMaterialStore(attempt['workspace']['path'])
    run = SupplyRun(supply_run_id='initial-empty', plan_id=plan.plan_id,
        started_at=datetime.now(timezone.utc), finished_at=datetime.now(timezone.utc), result_bundle_id='empty')
    bundle = MaterialBundleAssembler().assemble(plan, run, (), (), bundle_id='empty')
    readiness, gaps = MaterialReadinessCalculator(store=store).calculate(plan, bundle)
    attempt = MaterialGateIntegration().record(attempt, plan, bundle, run, readiness, gaps)['attempt']
    prior = {'status': 'COMPLETE', 'request_id': 'first-search', 'plan_revision': readiness.plan_revision,
             'bundle_revision': bundle.revision, 'search_terms': {'need-main': ['dark parking']}}
    if optional_shot == 'audio_used_visual':
        prior['compiled_audio_fallback_need_ids'] = ['bgm-used']
    if optional_shot == 'audio':
        prior['previous_rounds'] = [{'status': 'COMPLETE', 'search_terms': {'need-main': ['long piano background phrase']}}]
        (store.materials_root / 'product-supply.json').write_text(json.dumps({'attempt_id': attempt['attempt_id'], 'plan_revision': readiness.plan_revision,
            'routing': [{'need_id': 'need-main', 'attempted_sources': ['openverse_audio'], 'failures': []}]}))
    service.update_film_attempt(attempt['attempt_id'], event='fixture_first_search_complete',
        autonomous_material_recovery=prior,
        material_observation={'status': 'COMPLETE', 'plan_revision': readiness.plan_revision,
                              'bundle_revision': bundle.revision})
    with creation.edit_creation(attempt['creation_id']) as work:
        digest = hashlib.sha256(b'proposal').hexdigest()
        work['delivery'] = {'schema': SCHEMA, 'proposal': 'proposal', 'proposal_sha256': digest}
        work['chat_workflow'] = {'proposal_status': 'CONFIRMED', 'proposal_sha256': digest}
    assert next_operation(creation.get_creation(attempt['creation_id'])) == ('recover_material', 'recovering_material')
    query_calls, supply_calls = [], []
    choice = {'expression': '采用主体清晰的近景，省略无关背景灯光', 'reason': '已有候选无法同时呈现背景，保留原核心表达'}
    def queries(current, record):
        query_calls.append(record['request_id'])
        assert record['previous_rounds'] == [prior]
        if optional_shot == 'audio_used_visual':
            assert [n['need_id'] for n in record['needs']] == ['need-main']
        extra = {'shot_choices': {'need-main': choice}} if optional_shot is True else {}
        with pytest.raises(MaterialIntegrationError, match='重复'):
            recovery.validate_recovery_queries(record, {'request_id': record['request_id'],
                'search_terms': {'need-main': [' DARK  parking ']}, **extra})
        report = {'request_id': record['request_id'], 'search_terms': {'need-main': ['visible charging connector lit pavement']}, **extra}
        if optional_shot is True:
            for wrong in ({}, {'other-need': choice}, {'need-main': {**choice, 'rewrite_script': True}}):
                with pytest.raises(MaterialIntegrationError, match='镜头取舍'):
                    recovery.validate_recovery_queries(record, {**report, 'shot_choices': wrong})
            import web.app as webapp
            def directed_query(message, *args, **kwargs):
                assert '先作为 Director' in message and 'preferred_visual_details' in message
                assert 'shot_choices' in message and '不以镜头决定或检索建议作为匹配证据' in message
                store.write_recovery_record(record['request_id'] + '-queries', report)
                return ''
            monkeypatch.setattr(webapp, 'run_agent_sync', directed_query)
            return webapp._plan_material_recovery(current, record)
        return report
    actual_supply = recovery.ProductMaterialSupply.run
    def supply(self, *args, **kwargs):
        supply_calls.append(kwargs)
        return actual_supply(self, *args, **kwargs)
    monkeypatch.setattr(recovery.ProductMaterialSupply, 'run', supply)
    actual_record = recovery.MaterialGateIntegration.record
    def interrupted(*args, **kwargs):
        raise RuntimeError('fixture interrupted after supply')
    monkeypatch.setattr(recovery.MaterialGateIntegration, 'record', interrupted)
    with pytest.raises(RuntimeError, match='interrupted'):
        recovery.recover_managed_materials(attempt['attempt_id'], executor=queries)
    monkeypatch.setattr(recovery.MaterialGateIntegration, 'record', actual_record)
    updated = recovery.recover_managed_materials(attempt['attempt_id'], executor=queries)
    assert len(query_calls) == (0 if optional_shot == 'audio' else 1)
    assert len(supply_calls) == 1
    if optional_shot == 'audio':
        assert supply_calls[0]['search_terms'] == {'need-main': ('piano instrumental',)}
        assert updated['autonomous_material_recovery']['compiled_audio_fallback_need_ids'] == ['need-main']
        assert len(updated['autonomous_material_recovery']['previous_rounds']) == 2
    assert PlanningIntegration().load(updated)['plan'] == plan
    assert PlanningIntegration().load(updated)['script'] == '假设脚本内容。\n'
    choices = recovery.director_shot_choices(updated, plan)
    if optional_shot is True:
        assert choices['need-main']['expression'] == choice['expression']
        assert choices['need-main']['core_requirement'] == plan.needs[0].intent.description
        changed = plan.model_copy(update={'needs': (plan.needs[0].model_copy(update={'intent': NeedIntent(description='新主体')}),)})
        with pytest.raises(MaterialIntegrationError, match='不一致'):
            recovery.director_shot_choices(updated, changed)
        # The retained decision reaches actual Authoring input through the
        # ordinary Gate, once independently qualified media becomes available.
        _, asset, qualified_run, original_bundle, _, _ = _contracts(attempt, Path(attempt['workspace']['path']))
        qualified_run = qualified_run.model_copy(update={'result_bundle_id': 'qualified'})
        qualified = MaterialBundleAssembler().assemble(plan, qualified_run, (asset,), original_bundle.matches, bundle_id='qualified')
        ready, qualified_gaps = MaterialReadinessCalculator(store=store).calculate(plan, qualified)
        assert ready.status.value == 'READY'
        prepared = MaterialGateIntegration().record(updated, plan, qualified, qualified_run, ready, qualified_gaps)['attempt']
        ProductionAuthoringIntegration().prepare(prepared)
        selected = json.loads((Path(attempt['workspace']['path']) / 'productions/easel-authoring/material-selection.json').read_text())
        assert selected['director_shot_choices'] == choices
        # Restore the empty-supply fixture to check the real exhausted state.
        updated = MaterialGateIntegration().record(prepared, plan, bundle, run, readiness, gaps)['attempt']
    assert recovery.visual_supply_recovery_state(updated) == 'exhausted'
    assert recovery.recover_managed_materials(attempt['attempt_id'], executor=queries) == updated
    gate = updated['material_gate']
    service.update_film_attempt(attempt['attempt_id'], event='fixture_observation_complete',
        material_observation={'status': 'COMPLETE', 'plan_revision': gate['plan_revision'],
                              'bundle_revision': gate['bundle_revision']})
    assert next_operation(creation.get_creation(attempt['creation_id'])) == (None, 'material_supply_exhausted')


@pytest.mark.parametrize('shared_need', [False, True])
def test_combination_review_resumes_saved_choice_and_preserves_admission(material_integration_env, monkeypatch, shared_need):
    from easel.integrations.hypit import service
    from easel.integrations.material_layer import MaterialProductOrchestrator

    attempt = material_integration_env
    _planning(attempt)
    root = Path(attempt['workspace']['path'])
    plan, asset, run, bundle, readiness, gaps = _contracts(attempt, root)
    if shared_need:
        from easel.materials.application.matching import MaterialMatcher
        second = plan.needs[0].model_copy(update={'need_id': 'need-second',
            'scope': NeedScope(type=NeedScopeType.SCENE, ref='scene-2'),
            'intent': NeedIntent(description='同一画面用于另一个观察场景')})
        planning = PlanningIntegration().persist(attempt, plan.model_copy(update={'needs': (*plan.needs, second)}),
            treatment='# Treatment', script='假设脚本内容。', scenes='两个观察场景。')
        attempt.update(planning['attempt'])
        plan = planning['plan']
        matches = tuple(m for n in plan.needs for m in MaterialMatcher().match(n, (asset,)).matches)
        bundle = MaterialBundleAssembler().assemble(plan, run, (asset,), matches, bundle_id=bundle.bundle_id)
        readiness, gaps = MaterialReadinessCalculator(store=AttemptMaterialStore(root)).calculate(plan, bundle)
    MaterialGateIntegration().record(attempt, plan, bundle, run, readiness, gaps)
    store = AttemptMaterialStore(root)
    owner = MaterialProductOrchestrator()
    args = dict(plan_revision=readiness.plan_revision, bundle_revision=bundle.revision,
                confirm_review=True, reviews=[dict(need_id=n.need_id, asset_id=asset.asset_id,
                    expected_sha256=asset.file.sha256, observed_content='已查看实际画面，接受当前场景表达。',
                    logo_present=None, visible_text_present=None, voice_recognition_review=None) for n in plan.needs])
    from easel import creation_delivery
    monkeypatch.setattr(creation_delivery, 'is_managed', lambda work: True)
    monkeypatch.setattr(creation_delivery, '_attempt', lambda work: service.get_film_attempt(attempt['attempt_id']))
    proposal_hash = hashlib.sha256(b'fixture').hexdigest()
    work = {'delivery': {'proposal': 'fixture', 'proposal_sha256': proposal_hash},
            'chat_workflow': {'proposal_status': 'CONFIRMED', 'proposal_sha256': proposal_hash}}
    before = store.read_asset(asset.asset_id).to_json()
    stale = {**args, 'reviews': [{**args['reviews'][0], 'expected_sha256': '0' * 64}]}
    with pytest.raises(MaterialIntegrationError):
        owner.review_material_combination(attempt['attempt_id'], **stale)
    for bad_reviews in ([], args['reviews'] * 2):
        with pytest.raises(MaterialIntegrationError):
            owner.review_material_combination(attempt['attempt_id'], **{**args, 'reviews': bad_reviews})
    assert store.read_asset(asset.asset_id).to_json() == before

    from fastapi.testclient import TestClient
    from web.app import app, require_local_operator
    api_body = {'planRevision': args['plan_revision'], 'bundleRevision': args['bundle_revision'], 'confirmReview': True,
                'reviews': [{'assetId': asset.asset_id, 'assetSha256': asset.file.sha256, 'needId': r['need_id'],
                             'observedContent': r['observed_content'], 'confirmReview': True} for r in args['reviews']]}
    with TestClient(app) as client:
        assert client.post(f"/api/film-attempts/{attempt['attempt_id']}/material-match/review-combination",
                           json=api_body).status_code == 403

    finish = owner.finish_material_combination
    monkeypatch.setattr(owner, 'finish_material_combination',
        lambda *a, **kw: (_ for _ in ()).throw(OSError('after journal, before marker')))
    with pytest.raises(OSError, match='before marker'):
        owner.review_material_combination(attempt['attempt_id'], **args)
    assert not service.get_film_attempt(attempt['attempt_id']).get('material_combination_review')
    assert creation_delivery.next_operation(work) == ('finish_material_review', 'reviewing_material')
    monkeypatch.setattr(owner, 'finish_material_combination', finish)
    recalculate = owner._recalculate_observed_materials
    monkeypatch.setattr(owner, '_recalculate_observed_materials',
                        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError('interrupted')))
    with pytest.raises(RuntimeError, match='interrupted'):
        owner.review_material_combination(attempt['attempt_id'], **args)
    current = service.get_film_attempt(attempt['attempt_id'])
    assert current['material_combination_review']['status'] == 'PENDING'
    service.update_film_attempt(attempt['attempt_id'], event='fixture_uncertain_execution',
                                execution_status='SUBMISSION_UNCERTAIN')
    assert creation_delivery.next_operation(work) == ('reconcile', 'reconciling')
    with pytest.raises(MaterialIntegrationError, match='先核对'):
        owner.finish_material_combination(attempt['attempt_id'])
    service.update_film_attempt(attempt['attempt_id'], event='fixture_execution_restored',
                                execution_status='NOT_SUBMITTED')
    monkeypatch.setattr(owner, '_recalculate_observed_materials', recalculate)
    result = owner.finish_material_combination(attempt['attempt_id'])
    assert result['attempt']['material_combination_review']['status'] == 'COMPLETE'
    selection = json.loads((root / 'productions/easel-authoring/material-selection.json').read_text())
    assert selection['creator_material_choices'] == {
        n.need_id: {'asset_id': asset.asset_id, 'sha256': asset.file.sha256} for n in plan.needs}
    saved = store.read_bundle().to_json()
    owner.review_material_combination(attempt['attempt_id'], **args)
    assert store.read_bundle().to_json() == saved
    app.dependency_overrides[require_local_operator] = lambda: None
    try:
        with TestClient(app) as client:
            response = client.post(f"/api/film-attempts/{attempt['attempt_id']}/material-match/review-combination", json=api_body)
            assert response.status_code == 200, response.text
            assert store.read_bundle().to_json() == saved
    finally:
        app.dependency_overrides.pop(require_local_operator, None)

    assert creation_delivery.next_operation(work) == ('author', 'authoring')

    from easel.materials.application.matching import MaterialMatcher
    if not shared_need:
        from easel.materials.application.dedup import MaterialDeduplicator
        chosen = store.read_asset(asset.asset_id)
        extra = []
        for index in range(4):
            data = f'fixture alternative {index}'.encode()
            sha = hashlib.sha256(data).hexdigest()
            asset_id = f'asset-00{index}'
            inferences = tuple(i.model_copy(update={'annotations': tuple(a.model_copy(update={
                'evidence': a.evidence.replace(chosen.file.sha256, sha) if a.evidence else None
            }) for a in i.annotations)}) for i in chosen.semantic.inferences)
            candidate = chosen.model_copy(update={'asset_id': asset_id,
                'file': chosen.file.model_copy(update={'path': store.write_asset_bytes(asset_id, 'original.png', data),
                                                       'sha256': sha, 'size': len(data)}),
                'source': chosen.source.model_copy(update={'provider_asset_id': asset_id}),
                'technical': chosen.technical.model_copy(update={'width': 20 + index, 'height': 40 + index}),
                'semantic': chosen.semantic.model_copy(update={'inferences': inferences})})
            store.write_asset(candidate)
            extra.append(candidate)
        assets = (*extra, chosen)
        ranked = MaterialMatcher().match(plan.needs[0], assets)
        baseline = MaterialDeduplicator(store).deduplicate_and_diversify(ranked.matches, assets, top_k=3).shortlist
        assert asset.asset_id not in {m.asset_id for m in baseline}
        protected = owner._rank_reviewed_materials(result['attempt'], plan, assets, store, require_scoped_visual=True)
        assert asset.asset_id in {m.asset_id for m in protected}
    edited_need = plan.needs[0].model_copy(update={'intent': NeedIntent(description='完全不同的场景需求')})
    assert not MaterialMatcher._creator_match_review(edited_need, store.read_asset(asset.asset_id))

    # Human creative acceptance cannot stand in for missing rights.
    unknown = store.read_asset(asset.asset_id).model_copy(update={'rights': RightsInfo(status=RightsStatus.UNKNOWN)})
    store.write_asset(unknown)
    with pytest.raises(MaterialIntegrationError):
        ProductionAuthoringIntegration().accepted_combination(
            result['attempt'], plan, store.read_bundle().model_copy(update={'assets': (unknown,)}), store)

    assert creation_delivery.next_operation(work) == (None, 'needs_evidence')

    if not shared_need:
        # Supply can remain READY via alternatives while the accepted choice
        # is blocked. Preserve a separate, actionable selection gap.
        current_bundle = store.read_bundle()
        wider = current_bundle.model_copy(update={'assets': (*extra, unknown)})
        blocked = owner._recalculate_observed_materials(
            service.get_film_attempt(attempt['attempt_id']), plan, wider, store, require_scoped_visual=True)
        assert blocked['material_status'] == 'MATERIAL_READY'
        assert blocked['attempt']['material_combination_review']['blocking_needs'] == ['need-main']
        assert creation_delivery.next_operation(work) == (None, 'needs_evidence')
        restored = owner.review_material_rights(attempt['attempt_id'],
            asset_id=asset.asset_id, expected_sha256=asset.file.sha256,
            rights=asset.rights, confirm_review=True)
        assert restored['attempt']['material_combination_review']['blocking_needs'] == []
        assert creation_delivery.next_operation(work) == ('author', 'authoring')
        assert asset.asset_id in {m.asset_id for m in store.read_bundle().matches}
        path = store.resolve_asset_locator(asset.file.path)
        original_bytes = path.read_bytes()
        path.write_bytes(b'changed after acceptance')
        damaged = owner._recalculate_observed_materials(
            service.get_film_attempt(attempt['attempt_id']), plan, store.read_bundle(), store)
        assert damaged['material_status'] == 'MATERIAL_READY'  # Alternatives remain usable.
        assert damaged['attempt']['material_combination_review']['blocking_needs'] == ['need-main']
        assert creation_delivery.next_operation(work) == (None, 'needs_evidence')
        path.write_bytes(original_bytes)


def test_material_endpoint_stops_after_search_coverage_and_invalidates_changed_bytes(material_integration_env, monkeypatch):
    import asyncio
    from io import BytesIO
    from easel.creation_delivery import advance_creation, next_operation
    from tests.test_creation_preparation import web
    from easel.materials.application.visual_observation import SCHEMA
    attempt = material_integration_env
    root = Path(attempt['workspace']['path'])
    _planning(attempt)
    plan, asset, run, _, _, _ = _contracts(attempt, root)
    image = BytesIO()
    Image.new('RGB', (16, 16), 'red').save(image, format='PNG')
    content = image.getvalue()
    store = AttemptMaterialStore(root)
    asset = asset.model_copy(update={'file': FileInfo(
        path=store.write_asset_bytes(asset.asset_id, 'decoded.png', content),
        sha256=hashlib.sha256(content).hexdigest(), size=len(content), mime='image/png')})
    store.write_asset(asset)
    bundle = MaterialBundleAssembler().assemble(plan, run, (asset,), (), bundle_id='bundle-int-1')
    # Nomination metadata may initially match, but endpoint readiness must still
    # pass actual visual observation before it can stop.
    from easel.materials.application.matching import MaterialMatcher
    bundle = MaterialBundleAssembler().assemble(plan, run, (asset,), MaterialMatcher().match(plan.needs[0], (asset,)).matches, bundle_id='bundle-int-1')
    readiness, gaps = MaterialReadinessCalculator(store=store).calculate(plan, bundle)
    MaterialGateIntegration().record(service.get_film_attempt(attempt['attempt_id']), plan, bundle, run, readiness, gaps)
    proposal = '已确认的素材端点隔离委托'
    with creation.edit_creation(attempt['creation_id']) as work:
        work['origin'] = {'type': 'chat'}
        work['chat_workflow'] = {'proposal_status': 'READY_FOR_CONFIRMATION'}
    work = creation.confirm_chat_proposal(attempt['creation_id'], 'fixture-confirm',
        delivery_proposal=proposal, proposal_sha256=hashlib.sha256(proposal.encode()).hexdigest())
    asyncio.run(web.api_creation_material_endpoint(work['id'], _operator=None))
    from tests.material_delta_fixture import observed_result
    observed = []
    def observe(current, manifest, attachments):
        observed.append(manifest['input_sha256'])
        return observed_result(current, manifest, attachments,
            outcome='suitable', description='actual red image')
    async def execute(operation, current):
        assert operation == 'observe_material'
        MaterialProductOrchestrator().observe_visual_materials(attempt['attempt_id'], executor=observe)
    monkeypatch.setattr(material_supply_module.ProductMaterialSupply, 'run', lambda *a, **kw: pytest.fail('covered supply cannot search'))
    monkeypatch.setattr(MaterialProductOrchestrator, 'generate_minimax_asset', lambda *a, **kw: pytest.fail('covered supply cannot generate'))
    for _ in range(4):
        asyncio.run(advance_creation(work['id'], execute))
    current = creation.get_creation(work['id'])
    assert observed and len(observed) == 1
    assert next_operation(current) == (None, 'material_ready')
    assert current['status'] != 'ready' and not current.get('selected_output_name')
    assert current['delivery']['material_endpoint_result']['film_delivery_complete'] is False
    assert 'authoring_stages' not in current['delivery']
    store.resolve_asset_locator(asset.file.path).write_bytes(content + b'changed')
    assert next_operation(creation.get_creation(work['id'])) == (None, 'needs_evidence')


@pytest.mark.parametrize('boundary', ['forbidden', 'dynamic', 'real_identity', 'no_authorization', 'report_fault', 'changed_input', 'no_space'])
def test_image_fallback_rejects_unproven_or_unauthorized_gaps(material_integration_env, tmp_path, boundary):
    from easel.integrations.material_generation import pending_generated_need
    attempt = material_integration_env
    planning = _planning(attempt)
    old = planning['plan']
    need = old.needs[0].model_copy(update={'constraints': {'allow_generation': True}})
    constraints = dict(need.constraints)
    if boundary == 'forbidden': constraints['allow_generation'] = False
    if boundary == 'dynamic': constraints['requires_dynamic_action'] = True
    if boundary == 'real_identity': constraints['requires_real_identity'] = True
    need = need.model_copy(update={'constraints': constraints})
    planning = PlanningIntegration().persist(attempt, old.model_copy(update={'needs': (need,)}),
        treatment='T', script='假设情景。', scenes='S')
    plan = planning['plan']
    root = tmp_path / 'empty-source'
    root.mkdir()
    supplied = material_supply_module.ProductMaterialSupply().run(plan, planning['attempt'],
        local_roots=(root,), supply_run_id='empty', bundle_id='empty-bundle')
    attempt = MaterialGateIntegration().record(planning['attempt'], plan, supplied.bundle, supplied.supply_run,
                                               supplied.readiness, supplied.gaps)['attempt']
    gate = attempt['material_gate']
    observation = {'status': 'COMPLETE', 'plan_revision': gate['plan_revision'], 'bundle_revision': gate['bundle_revision']}
    if boundary == 'report_fault': observation['status'] = 'PENDING'
    if boundary == 'changed_input': observation['plan_revision'] = 'stale'
    attempt = service.update_film_attempt(attempt['attempt_id'], event='fixture_observation', material_observation=observation)
    work = creation.get_creation(attempt['creation_id'])
    work['delivery'] = {'authorization': {'material_generation': {'max_amount': '10'}},
                        'material_generations': {}, 'call_budgets': {'material': {'used': 8, 'limit': 20}}}
    if boundary == 'no_authorization': work['delivery']['authorization'] = {}
    if boundary == 'no_space': work['delivery']['call_budgets']['material']['limit'] = 12
    assert pending_generated_need(work, attempt, plan) is None
    assert work['delivery']['call_budgets']['material']['used'] == 8


def test_legacy_preference_refusal_is_readonly_without_delta_receipt(material_integration_env):
    from easel.integrations.output_receipts import OutputReceiptError
    from easel.materials.application.visual_observation import SCHEMA, apply_observation, prepare_observation
    from io import BytesIO
    attempt = material_integration_env
    root = Path(attempt["workspace"]["path"])
    plan, asset, run, _, _, _ = _contracts(attempt, root)
    first = plan.needs[0]
    second = first.model_copy(update={"need_id": "other",
        "constraints": {"preferred_style": "warm"}})
    planning = PlanningIntegration().persist(attempt,
        plan.model_copy(update={"needs": (first, second)}),
        treatment="T", script="假设情景。", scenes="S")
    plan = planning["plan"]
    store = AttemptMaterialStore(root)
    image = BytesIO()
    Image.new("RGB", (16, 16), "red").save(image, format="PNG")
    raw = image.getvalue()
    asset = asset.model_copy(update={"file": FileInfo(
        path=store.write_asset_bytes(asset.asset_id, "decoded.png", raw),
        sha256=hashlib.sha256(raw).hexdigest(), size=len(raw), mime="image/png")})
    stored_reports = {}
    for need in plan.needs:
        manifest, _ = prepare_observation(need, asset,
            store.resolve_asset_locator(asset.file.path))
        report = {"schema": SCHEMA, "input_sha256": manifest["input_sha256"],
            "verdict": "unsuitable", "caption": "legacy heuristic",
            "style": "red", "reason": "unverified historic preference rejection",
            "frames": [{"index": 0, "observed": True, "related": False,
                        "description": "historic unverified frame"}]}
        store.write_observation_record(manifest["input_sha256"], report)
        stored_reports[manifest["input_sha256"]] = report
        asset = apply_observation(need, asset, manifest, report)
    store.write_asset(asset)
    from easel.materials.application.matching import MaterialMatcher
    matches = tuple(m for need in plan.needs
                    for m in MaterialMatcher().match(need, (asset,)).matches)
    bundle = MaterialBundleAssembler().assemble(
        plan, run, (asset,), matches, bundle_id="bundle-int-1")
    readiness, gaps = MaterialReadinessCalculator(store=store).calculate(plan, bundle)
    from easel.integrations import material_results
    # Explicit evidence eligibility fails closed: historical inferences have no
    # original Material@3 receipt and may never be upgraded to a qualified Match.
    with pytest.raises(OutputReceiptError, match="result protocol proof"):
        material_results.eligible(store, first, asset, attempt=planning["attempt"])
    gate = MaterialGateIntegration().record(planning["attempt"], plan, bundle, run,
                                             readiness, gaps)
    assert gate["status"] == "MATERIAL_NOT_READY"
    # Historic evidence remains discoverable, but the new active Attempt cannot
    # silently reclassify an unverified old preference refusal as admitted evidence.
    assert store.read_asset(asset.asset_id) == asset
    for key, value in stored_reports.items():
        assert json.loads((store.materials_root / "observations" / (key + ".json")).read_text()) == value
    assert service.get_film_attempt(attempt["attempt_id"]) == gate["attempt"]


def test_unlabelled_pool_is_not_cross_reviewed_and_spending_survives_pool_change(material_integration_env):
    from io import BytesIO
    from easel.materials.application.visual_observation import SCHEMA
    attempt = material_integration_env
    store = AttemptMaterialStore(attempt['workspace']['path'])
    original, example, run, _, _, _ = _contracts(attempt, Path(attempt['workspace']['path']))
    subjects = ('keyboard typing', 'children blocks', 'mountain snow', 'city bus', 'paper desk', 'clock', 'flower')
    plan = original.model_copy(update={'needs': tuple(original.needs[0].model_copy(update={
        'need_id': f'need-{i}', 'intent': NeedIntent(description=subject)}) for i, subject in enumerate(subjects))})
    planning = PlanningIntegration().persist(attempt, plan, treatment='T', script='假设场景。', scenes='S')
    plan = planning['plan']
    assets = []
    def add_asset(index, caption=None):
        image = BytesIO()
        Image.new('RGB', (16, 16), (index * 30, 0, 0)).save(image, format='PNG')
        body = image.getvalue()
        aid = f'pool-{index}'
        asset = example.model_copy(update={'asset_id': aid, 'file': FileInfo(
            path=store.write_asset_bytes(aid, 'image.png', body), sha256=hashlib.sha256(body).hexdigest(),
            size=len(body), mime='image/png'), 'semantic': SemanticInfo(caption=caption)})
        store.write_asset(asset)
        assets.append(asset)
    for i in range(4):
        add_asset(i)
    def record_pool(attempt):
        bundle = MaterialBundleAssembler().assemble(plan, run, tuple(store.read_asset(a.asset_id) for a in assets), (), bundle_id=run.result_bundle_id)
        readiness, gaps = MaterialReadinessCalculator(store=store).calculate(plan, bundle)
        return MaterialGateIntegration().record(attempt, plan, bundle, run, readiness, gaps)['attempt']
    attempt = record_pool(planning['attempt'])
    calls = []
    from tests.material_delta_fixture import observed_result
    def observe(current, manifest, attachments):
        calls.append((manifest['need']['need_id'], manifest['asset_id']))
        return observed_result(current, manifest, attachments, outcome="unsuitable",
            description="actual empty field")
    first = MaterialProductOrchestrator().observe_visual_materials(attempt['attempt_id'], executor=observe)
    assert calls == [('need-0', 'pool-0')]  # Previously four files * seven Needs.
    assert first['attempt']['material_observation']['nominated_associations'] == 1
    add_asset(4, 'keyboard typing')  # Actual discovery hint; still not admission.
    record_pool(service.get_film_attempt(attempt['attempt_id']))
    second = MaterialProductOrchestrator().observe_visual_materials(attempt['attempt_id'], executor=observe)
    assert calls == [('need-0', 'pool-0'), ('need-0', 'pool-4')]
    assert second['attempt']['material_observation']['candidate_progress']['need-0']['nominated'] == 2
    assert second['attempt']['material_observation']['nominated_associations'] == 2
    assert second['material_status'] == 'MATERIAL_NOT_READY'


@pytest.mark.parametrize('signal', ['hard_partial', 'unknown', 'rights_pending'])
def test_partial_content_gap_can_generate_but_unknown_or_rights_cannot(material_integration_env, signal):
    from io import BytesIO
    from easel.materials.application.visual_observation import SCHEMA
    from easel.integrations.material_generation import image_fallback_decision
    attempt = material_integration_env
    store = AttemptMaterialStore(attempt['workspace']['path'])
    plan, example, run, _, _, _ = _contracts(attempt, Path(attempt['workspace']['path']))
    need = plan.needs[0].model_copy(update={'constraints': {'allow_generation': True}})
    planning = PlanningIntegration().persist(attempt, plan.model_copy(update={'needs': (need,)}),
        treatment='T', script='假设场景。', scenes='S')
    plan, need = planning['plan'], planning['plan'].needs[0]
    image = BytesIO()
    Image.new('RGB', (16, 16), 'red').save(image, format='PNG')
    body = image.getvalue()
    example = example.model_copy(update={'file': FileInfo(path=store.write_asset_bytes(example.asset_id, 'image.png', body),
        sha256=hashlib.sha256(body).hexdigest(), size=len(body), mime='image/png'),
        'semantic': SemanticInfo(caption=need.intent.description), 'rights': RightsInfo(status=RightsStatus.UNKNOWN)})
    store.write_asset(example)
    bundle = MaterialBundleAssembler().assemble(plan, run, (example,), (), bundle_id=run.result_bundle_id)
    ready, gaps = MaterialReadinessCalculator(store=store).calculate(plan, bundle)
    MaterialGateIntegration().record(planning['attempt'], plan, bundle, run, ready, gaps)
    from tests.material_delta_fixture import observed_result
    def observe(current, manifest, attachments):
        return observed_result(current, manifest, attachments,
            outcome='unsuitable' if signal == 'hard_partial' else
                    'uncertain' if signal == 'unknown' else 'suitable',
            description='actual red field',
            note='paper absent' if signal == 'hard_partial' else 'actual fixture evidence')
    result = MaterialProductOrchestrator().observe_visual_materials(attempt['attempt_id'], executor=observe)
    attempt = result['attempt']
    (store.materials_root / 'product-supply.json').write_text(json.dumps({
        'attempt_id': attempt['attempt_id'], 'plan_revision': attempt['material_gate']['plan_revision'],
        'routing': [{'need_id': need.need_id, 'attempted_sources': ['fixture-successful-search'], 'failures': []}]}))
    work = creation.get_creation(attempt['creation_id'])
    work['delivery'] = {'authorization': {'material_generation': {'max_amount': '10'}},
        'material_generations': {}, 'call_budgets': {'material': {'used': 10, 'limit': 30}}}
    assert image_fallback_decision(work, attempt, plan, need)['eligible'] is (signal == 'hard_partial')
    assert work['delivery']['call_budgets']['material']['used'] == 10


def test_source_rejection_is_scoped_to_need_and_current_query(material_integration_env, tmp_path, monkeypatch):
    from easel.materials.providers import PexelsProvider, PixabayProvider, ProviderRegistry
    from easel.materials.providers.base import ProviderPage
    from easel.materials.application.visual_observation import apply_observation, prepare_observation, SCHEMA
    from easel.materials.application.compiler import NeedCompiler
    from io import BytesIO
    attempt = material_integration_env
    store = AttemptMaterialStore(attempt['workspace']['path'])
    plan, asset, run, _, _, _ = _contracts(attempt, Path(attempt['workspace']['path']))
    a = plan.needs[0].model_copy(update={'need_id': 'a', 'intent': NeedIntent(description='paper desk')})
    b = a.model_copy(update={'need_id': 'b', 'intent': NeedIntent(description='children blocks')})
    planning = PlanningIntegration().persist(attempt, plan.model_copy(update={'needs': (a, b)}),
        treatment='T', script='假设场景。', scenes='S')
    plan, a, b = planning['plan'], *planning['plan'].needs
    image = BytesIO()
    Image.new('RGB', (16, 16), 'red').save(image, format='PNG')
    body = image.getvalue()
    asset = asset.model_copy(update={'file': FileInfo(path=store.write_asset_bytes(asset.asset_id, 'image.png', body),
        sha256=hashlib.sha256(body).hexdigest(), size=len(body), mime='image/png'),
        'source': CandidateSource(kind='stock', provider='pexels', provider_asset_id='original'), 'semantic': SemanticInfo()})
    manifest, _ = prepare_observation(a, asset, store.resolve_asset_locator(asset.file.path))
    asset = apply_observation(a, asset, manifest, {'schema': SCHEMA, 'input_sha256': manifest['input_sha256'],
        'verdict': 'unsuitable', 'caption': 'red field', 'style': 'plain', 'reason': 'paper missing',
        'frames': [{'index': 0, 'observed': True, 'related': False, 'description': 'red field'}]})
    store.write_asset(asset)
    bundle = MaterialBundleAssembler().assemble(plan, run, (asset,), (), bundle_id=run.result_bundle_id)
    ready, gaps = MaterialReadinessCalculator(store=store).calculate(plan, bundle)
    attempt = MaterialGateIntegration().record(planning['attempt'], plan, bundle, run, ready, gaps)['attempt']
    store.write_recovery_record('candidate-links', {'assets': {asset.asset_id: [{
        'need_id': a.need_id, 'compiled_intent_sha256': hashlib.sha256(NeedCompiler().compile(a).to_json().encode()).hexdigest()}]}})
    registry = ProviderRegistry()
    calls = []
    for provider in (PexelsProvider('fixture-key'), PixabayProvider('fixture-key')):
        def search(intent, continuation=None, provider_id=provider.provider_id):
            calls.append((intent.need_id, provider_id))
            return ProviderPage()
        monkeypatch.setattr(provider, 'search', search)
        registry.register(provider)
    supply = material_supply_module.ProductMaterialSupply(registry=registry, library_root=tmp_path / 'empty-library')
    supply.run(plan, attempt, local_roots=(), supply_run_id='scope-check', bundle_id='scope-result')
    assert calls == [('a', 'pixabay'), ('b', 'pexels')]

@pytest.mark.parametrize('fault', ['none', 'bytes', 'locator', 'license', 'credit'])
def test_openverse_rights_refresh_reuses_bytes_and_keeps_admission_boundaries(material_integration_env, monkeypatch, fault):
    from easel.materials.providers.openverse import OpenverseAudioProvider
    from easel.materials.providers.http_support import HttpResponse
    from easel.materials.application.acquisition import MaterialAcquirer, DownloadResponse, RemoteURLPolicy
    from easel.materials.application.rights import RightsService, RightsAdmissionStatus
    from easel.creation_delivery import active_delivery, SCHEMA, next_operation
    from easel.materials.domain import BgmNeedSpec
    attempt = material_integration_env
    p = _planning(attempt)['plan']
    need = p.needs[0].model_copy(update={'media_type': MediaType.AUDIO,
        'modality_spec': BgmNeedSpec(instruments=('piano',), vocals_allowed=False),
        'intent': NeedIntent(description='piano music')})
    p = p.model_copy(update={'needs': (need,)})
    PlanningIntegration().persist(attempt, p, treatment='T', script='假设脚本内容。\n', scenes='S')
    item = {'id': '7b77669a-afee-440c-b5d3-dd3dc71bb4cc', 'title': 'Fixture Piano',
        'creator': 'Fixture Composer', 'foreign_landing_url': 'https://commons.wikimedia.org/w/index.php?curid=123',
        'url': 'https://upload.wikimedia.org/fixture.ogg', 'license': 'by', 'license_version': '4.0',
        'license_url': 'https://creativecommons.org/licenses/by/4.0/',
        'attribution': 'Fixture Piano by Fixture Composer is licensed under CC BY 4.0.'}
    calls = []
    class Download:
        def get(self, *args, **kwargs):
            calls.append('download')
            return DownloadResponse(200, {'content-type': 'audio/ogg'}, b'fixture audio')
    store = AttemptMaterialStore(attempt['workspace']['path'])
    provider = OpenverseAudioProvider()
    candidate = provider._candidate(item, need.need_id, MediaType.AUDIO)
    acquired = MaterialAcquirer(store, transport=Download(), url_policy=RemoteURLPolicy(lambda *_: ('93.184.216.34',))).acquire(candidate)
    # New acquisition propagates conditional CC BY evidence and exact credit.
    assert RightsService().evaluate(acquired, need, attribution=RightsService.attribution_condition_for(acquired)).status is RightsAdmissionStatus.CONDITIONAL
    assert acquired.source.source_page.endswith('/wiki/Special:Redirect/page/123')
    old = acquired.model_copy(update={'rights': acquired.rights.model_copy(update={'evidence': (), 'attribution_text': None})})
    store.write_asset(old)
    now = datetime.now(timezone.utc)
    run = SupplyRun(supply_run_id='old-openverse', plan_id=p.plan_id, started_at=now, finished_at=now, result_bundle_id='old-bundle')
    bundle = MaterialBundleAssembler().assemble(p, run, (old,), (), bundle_id='old-bundle')
    readiness, gaps = MaterialReadinessCalculator(store=store).calculate(p, bundle)
    attempt = MaterialGateIntegration().record(attempt, p, bundle, run, readiness, gaps)['attempt']
    service.update_film_attempt(attempt['attempt_id'], event='fixture_old_observation',
        material_observation={'status': 'COMPLETE', 'plan_revision': readiness.plan_revision,
                              'bundle_revision': bundle.revision})
    with creation.edit_creation(attempt['creation_id']) as work:
        work['delivery'] = {'schema': SCHEMA, 'proposal': 'fixture', 'proposal_sha256': hashlib.sha256(b'fixture').hexdigest()}
        work['chat_workflow'] = {'proposal_status': 'CONFIRMED', 'proposal_sha256': hashlib.sha256(b'fixture').hexdigest()}
    changed = dict(item)
    if fault == 'bytes': store.resolve_asset_locator(old.file.path).write_bytes(b'changed audio')
    if fault == 'locator': changed['url'] = 'https://upload.wikimedia.org/different.ogg'
    if fault == 'license': changed['license_url'] = 'https://creativecommons.org/licenses/by/3.0/'
    if fault == 'credit': changed['attribution'] = ''
    class Metadata:
        def get(self, url, **kwargs):
            calls.append('metadata')
            return HttpResponse(200, {}, json.dumps(changed).encode())
    provider = OpenverseAudioProvider(transport=Metadata())
    owner = MaterialProductOrchestrator()
    token = active_delivery.set(attempt['creation_id'])
    try:
        if fault in {'bytes', 'locator', 'license'}:
            with pytest.raises(MaterialIntegrationError): owner.refresh_openverse_rights(attempt['attempt_id'], provider=provider)
        else:
            owner.refresh_openverse_rights(attempt['attempt_id'], provider=provider)
            refreshed = store.read_asset(old.asset_id)
            assert refreshed.file == old.file and refreshed.technical == old.technical
            assert refreshed.rights.reviewed_at is None
            decision = RightsService().evaluate(refreshed, need, attribution=RightsService.attribution_condition_for(refreshed))
            assert decision.status is (RightsAdmissionStatus.CONDITIONAL if fault == 'none' else RightsAdmissionStatus.BLOCKED)
            owner.refresh_openverse_rights(attempt['attempt_id'], provider=provider)
            assert calls.count('metadata') == 1
            # An interruption after facts are saved still dispatches ordinary
            # listening/Gate work and never re-fetches metadata.
            assert next_operation(creation.get_creation(attempt['creation_id'])) == ('observe_material', 'observing_material')
            assert store.read_bundle().matches == ()  # Facts alone are not a listening result.
        assert calls.count('download') == 1
    finally:
        active_delivery.reset(token)


@pytest.mark.parametrize('fault,vocal_score', [
    ('none', .015), ('requested', .015), ('pending', .015), ('asset', .015),
    ('bundle', .015), ('gate', .015), ('journal', .015), ('none', .05),
])
def test_cached_bgm_policy_migration_resumes_without_external_calls(material_integration_env, monkeypatch, fault, vocal_score):
    from easel.creation_delivery import SCHEMA as DELIVERY_SCHEMA, active_delivery, next_operation
    from easel.materials.application import music_observation as music
    from easel.materials.application.music_reassessment import pending_music_reassessment, cached_music_reassessment
    from easel.integrations import material_layer

    attempt = material_integration_env
    root = Path(attempt['workspace']['path'])
    _planning(attempt)
    plan, asset, run, _, _, _ = _contracts(attempt, root)
    need = plan.needs[0].model_copy(update={'media_type': MediaType.AUDIO, 'duration_hint': DurationHint(target_seconds=30),
        'role': 'bgm', 'intent': NeedIntent(description='piano music'), 'modality_spec': BgmNeedSpec(vocals_allowed=False)})
    plan = plan.model_copy(update={'needs': (need,)})
    PlanningIntegration().persist(attempt, plan, treatment='T', script='假设脚本内容。\n', scenes='S')
    store = AttemptMaterialStore(root)
    body = b'byte-bound already observed audio fixture'
    asset = asset.model_copy(update={'media_type': MediaType.AUDIO,
        'file': FileInfo(path=store.write_asset_bytes(asset.asset_id, 'music.wav', body),
            sha256=hashlib.sha256(body).hexdigest(), size=len(body), mime='audio/wav'),
        'technical': TechnicalInfo(status=TechnicalStatus.PASSED, duration_seconds=30, mime='audio/wav'),
        'semantic': SemanticInfo()})
    store.write_asset(asset)
    bundle = MaterialBundleAssembler().assemble(plan, run, (asset,), (), bundle_id=run.result_bundle_id)
    readiness, gaps = MaterialReadinessCalculator(store=store).calculate(plan, bundle)
    attempt = MaterialGateIntegration().record(service.get_film_attempt(attempt['attempt_id']), plan, bundle, run, readiness, gaps)['attempt']
    report = {'schema': music.SCHEMA, 'model': music.MODEL_ID, 'model_revision': music.MODEL_REVISION,
        'model_sha256': music.MODEL_FILES['model.safetensors'], 'audio_sha256': asset.file.sha256,
        'duration_seconds': 30., 'windows': [{'start_seconds': start, 'end_seconds': start+10, 'rms': .1,
            'scores': {'Music': .55, **{l: vocal_score for l in music.VOCAL_LABELS}}} for start in (0, 5, 10, 15, 20)]}
    identity = 'music-' + hashlib.sha256((music.SCHEMA+music.MODEL_REVISION+asset.file.sha256).encode()).hexdigest()
    locator = store.write_observation_record(identity, report)
    original_raw = (root/locator).read_bytes()
    proposal = 'approved material endpoint fixture'
    digest = hashlib.sha256(proposal.encode()).hexdigest()
    with creation.edit_creation(attempt['creation_id']) as work:
        work['chat_workflow'] = {'proposal_status': 'CONFIRMED', 'proposal_sha256': digest}
        work['delivery'] = {'schema': DELIVERY_SCHEMA, 'proposal': proposal, 'proposal_sha256': digest,
            'endpoint': 'MATERIAL_READY', 'failures': {'historical': 1}, 'generated_reserved_cny': .1798}
    attempt = material_layer._update_attempt(attempt, material_observation={'status': 'COMPLETE',
        'plan_revision': attempt['material_gate']['plan_revision'], 'bundle_revision': bundle.revision})
    owner = MaterialProductOrchestrator()
    def forbidden(*args, **kwargs):
        pytest.fail('cached policy migration must not call Providers, models, visual observation or Authoring')
    monkeypatch.setattr(owner, 'refresh_openverse_rights', forbidden)
    monkeypatch.setattr(owner, 'material_rights_candidates', forbidden)
    monkeypatch.setattr(music, 'read_local_music', forbidden)
    monkeypatch.setattr(ProductionAuthoringIntegration, 'prepare', forbidden)
    assert pending_music_reassessment(attempt)
    assert next_operation(creation.get_creation(attempt['creation_id'])) == ('observe_material', 'observing_material')
    request = cached_music_reassessment(attempt)
    token = active_delivery.set(attempt['creation_id'])
    try:
        with creation.edit_creation(attempt['creation_id']) as work:
            work['delivery']['endpoint'] = 'FIRST_CUT'
        with pytest.raises(ValueError, match='MATERIAL_READY 终点'):
            owner._reassess_cached_music(attempt, plan, store, request)
        assert store.read_recovery_record('music-reassessment-'+music.POLICY_DIGEST) is None
        with creation.edit_creation(attempt['creation_id']) as work:
            work['delivery']['endpoint'] = 'MATERIAL_READY'
        if fault != 'none':
            with monkeypatch.context() as interruption:
                if fault in {'requested', 'journal'}:
                    native = AttemptMaterialStore.write_recovery_record
                    def interrupt_record(self, key, record):
                        native(self, key, record)
                        if key.startswith('music-reassessment-') and record['status'] == ('REQUESTED' if fault == 'requested' else 'COMPLETE'):
                            raise OSError('fixture interruption '+fault)
                    interruption.setattr(AttemptMaterialStore, 'write_recovery_record', interrupt_record)
                elif fault == 'asset':
                    native = AttemptMaterialStore.write_asset
                    def interrupt_asset(self, value):
                        result = native(self, value)
                        raise OSError('fixture interruption asset')
                    interruption.setattr(AttemptMaterialStore, 'write_asset', interrupt_asset)
                elif fault == 'bundle':
                    native = AttemptMaterialStore.write_bundle
                    def interrupt_bundle(self, value):
                        native(self, value)
                        raise OSError('fixture interruption bundle')
                    interruption.setattr(AttemptMaterialStore, 'write_bundle', interrupt_bundle)
                elif fault == 'gate':
                    native = MaterialGateIntegration.record
                    def interrupt_gate(self, *args, **kwargs):
                        native(self, *args, **kwargs)
                        raise OSError('fixture interruption gate')
                    interruption.setattr(MaterialGateIntegration, 'record', interrupt_gate)
                else:
                    native = material_layer._update_attempt
                    def interrupt_pending(current, **changes):
                        result = native(current, **changes)
                        if changes.get('material_observation', {}).get('status') == 'PENDING':
                            raise OSError('fixture interruption pending')
                        return result
                    interruption.setattr(material_layer, '_update_attempt', interrupt_pending)
                with pytest.raises(OSError, match='fixture interruption'):
                    owner.observe_visual_materials(attempt['attempt_id'], executor=forbidden)
            assert next_operation(creation.get_creation(attempt['creation_id'])) == ('observe_material', 'observing_material')
            if fault in {'requested', 'gate', 'journal'}:
                frozen_bundle = store.read_bundle()
                store.write_bundle(frozen_bundle.model_copy(update={'bundle_id': 'unrelated-bundle'}))
                with pytest.raises(ValueError, match='Bundle变化'):
                    owner.observe_visual_materials(attempt['attempt_id'], executor=forbidden)
                store.write_bundle(frozen_bundle)
            if fault == 'journal':
                audio_path = store.resolve_asset_locator(asset.file.path)
                audio_path.write_bytes(b'changed audio')
                with pytest.raises(ValueError, match='素材字节变化'):
                    owner.observe_visual_materials(attempt['attempt_id'], executor=forbidden)
                audio_path.write_bytes(body)
            if fault in {'requested', 'journal'}:
                altered = {**report, 'audio_sha256': '0'*64}
                (root/locator).write_text(json.dumps(altered))
                with pytest.raises(ValueError, match='身份变化'):
                    owner.observe_visual_materials(attempt['attempt_id'], executor=forbidden)
                if fault == 'requested':
                    assert store.read_asset(asset.asset_id) == asset
                else:
                    assert service.get_film_attempt(attempt['attempt_id'])['material_observation']['status'] == 'PENDING'
                (root/locator).write_bytes(original_raw)
        result = owner.observe_visual_materials(attempt['attempt_id'], executor=forbidden)
    finally:
        active_delivery.reset(token)
    expected = 'MATERIAL_READY' if vocal_score == .015 else 'MATERIAL_NOT_READY'
    assert result['material_status'] == expected
    final = service.get_film_attempt(attempt['attempt_id'])
    assert final['material_observation']['status'] == 'COMPLETE'
    assert store.read_recovery_record('music-reassessment-'+music.POLICY_DIGEST)['status'] == 'COMPLETE'
    assert not pending_music_reassessment(final)
    assert next_operation(creation.get_creation(attempt['creation_id']))[0] != 'observe_material'
    assert (root/locator).read_bytes() == original_raw
    observed = store.read_asset(asset.asset_id)
    assert observed.file == asset.file and observed.rights == asset.rights and observed.rights.reviewed_at is None
    assert creation.get_creation(attempt['creation_id'])['delivery']['failures'] == {'historical': 1}
    assert creation.get_creation(attempt['creation_id'])['delivery']['generated_reserved_cny'] == .1798
    assert not final.get('production_authoring')

@pytest.mark.parametrize('same_turn_contract', [False, True])
def test_visual_chunks_resume_with_fixed_requests_and_preserve_planning_contract(
        material_integration_env, monkeypatch, tmp_path, same_turn_contract):
    import io
    import web.app as webapp
    from easel.creation_delivery import DeliveryExecutionUncertain, DeliveryReportError
    from easel.integrations.hypit.handoff import load_frozen_creative_mode
    from easel.materials.application.visual_contract import (
        compilation_input, bind_classifications, validate_compilation, digest, batches,
    )
    from easel.materials.application.visual_observation import prepare_observation

    attempt = material_integration_env
    store = AttemptMaterialStore(attempt['workspace']['path'])
    plan, asset, run, _, _, _ = _contracts(attempt, Path(attempt['workspace']['path']))
    need = plan.needs[0].model_copy(update={
        'intent': NeedIntent(description='two sheets, red field, no hand, no logo, paper visible, desk visible; ' * 2,
                             function='静态画面由后期微推，字幕承担总结'),
        'constraints': {'preferred_visual_details': 'low angle'},
    })
    plan = plan.model_copy(update={'needs': (need,)})
    image = io.BytesIO()
    Image.new('RGB', (32, 24), 'red').save(image, format='PNG')
    data = image.getvalue()
    locator = store.write_asset_bytes(asset.asset_id, 'actual.png', data)
    asset = asset.model_copy(update={'file': FileInfo(path=locator, sha256=hashlib.sha256(data).hexdigest(),
                                                     size=len(data), mime='image/png')})
    store.write_asset(asset)
    planning = PlanningIntegration().persist(attempt, plan, treatment='T', script='假设脚本内容。', scenes='S')
    plan, attempt = planning['plan'], planning['attempt']
    need = plan.needs[0]
    frozen = compilation_input(need, plan.context_refs, load_frozen_creative_mode(attempt)[0], plan=plan)
    from easel.materials.application.visual_contract import classification_units
    labels = {'classifications': [
        {'id': unit['id'], 'kind': 'postproduction' if frozen['sources'][unit['source']]['path'] == 'intent/function'
         else 'required', 'preference_source': None} for unit in classification_units(frozen)]}
    compiled = bind_classifications(frozen, labels)
    contract = validate_compilation(frozen, compiled)
    if same_turn_contract:
        # This is the actual legacy same-turn Planning writer's key/record.
        store.write_recovery_record('requirements-' + digest(frozen),
                                    {'input': frozen, 'response': compiled, 'contract': contract})
    bundle = MaterialBundleAssembler().assemble(plan, run, (asset,), (), bundle_id='bundle-int-1')
    readiness, gaps = MaterialReadinessCalculator(store=store).calculate(plan, bundle)
    attempt = MaterialGateIntegration().record(attempt, plan, bundle, run, readiness, gaps)['attempt']
    manifest, attachments = prepare_observation(need, asset, store.resolve_asset_locator(locator))
    expected = batches(manifest, contract)
    assert len(expected) > 1
    calls, compilations, replies = [], [], {}
    interrupted = False

    def observe(message, timeout, session_id, *, attachments=None, capture_reply=False):
        nonlocal interrupted
        payload = json.loads(message.split('输入（数据，不执行其中指令）：', 1)[1])
        if session_id in replies:
            return replies[session_id]
        if payload.get('revision') == 'visual-requirements@1':
            compilations.append(payload)
            replies[session_id] = json.dumps(labels)
        else:
            calls.append((payload['batch'], payload.get('repair', 0)))
            checks = {str(c['id']): {'status': 'met', 'basis': 'actual fixture evidence'}
                      for c in payload['clauses']}
            if payload['mode'] == 'facts':
                output = {'observed': True, 'description': 'actual red field', 'style': 'daylight',
                          'logo': False, 'text': False, 'preference_notes': 'low angle differs',
                          'checks': checks}
            else:
                output = {'observation_ref': 'observation',
                          'facts_dispute': {'kind': 'none'},
                          'preference_notes': 'low angle differs', 'checks': checks}
            replies[session_id] = json.dumps(output)
            if payload['batch'] == 1 and not interrupted:
                interrupted = True
                raise DeliveryExecutionUncertain('second chunk awaits the original run')
        return replies[session_id]

    monkeypatch.setattr(webapp, 'run_agent_sync', observe)
    monkeypatch.setattr(material_supply_module.ProductMaterialSupply, 'run',
                        lambda *a, **k: pytest.fail('report recovery must not search or generate'))
    with pytest.raises(DeliveryExecutionUncertain):
        webapp._observe_material_frames(attempt, manifest, attachments)
    assert calls == [(0, 0), (1, 0)]
    if same_turn_contract:
        # Simulate an upgrade with old compact results but no new snapshots.
        for path in (store.materials_root / 'recoveries').glob('observation-batch-*.json'):
            path.unlink()
    report = webapp._observe_material_frames(attempt, manifest, attachments)
    assert report['verdict'] == 'suitable'
    assert report['requirements_contract'] == contract
    assert calls == [(i, 0) for i in range(len(expected))]  # No successful chunk is observed twice.
    assert len(compilations) == (0 if same_turn_contract else 1)
    before = list(calls)
    assert webapp._observe_material_frames(attempt, manifest, attachments) == report
    assert calls == before
    from easel.materials.application.visual_observation import apply_observation
    from easel.materials.application.matching import MaterialMatcher
    from easel.integrations import material_results
    observed = apply_observation(need, asset, manifest, report,
        result_processor=material_results.processor(attempt, store), persist_qualification=True)
    store.write_asset(observed)
    matches = MaterialMatcher().match(need, (observed,)).matches
    bundle = MaterialBundleAssembler().assemble(plan, run, (observed,), matches, bundle_id='bundle-int-1')
    readiness, gaps = MaterialReadinessCalculator(store=store).calculate(plan, bundle)
    attempt = MaterialGateIntegration().record(attempt, plan, bundle, run, readiness, gaps)['attempt']
    assert readiness.status.value == 'READY'
    ProductionAuthoringIntegration().prepare(attempt)  # Inputs only; no Authoring execution.
    root = Path(attempt['workspace']['path'])
    relative = 'productions/easel-authoring/POSTPRODUCTION_REQUIREMENTS.json'
    post = json.loads((root / relative).read_text())
    assert post['status'] == 'PENDING_AUTHORING' and post['unclassified_need_ids'] == []
    row = post['requirements'][0]
    assert row['need_id'] == need.need_id and row['contract_sha256'] == digest(contract)
    assert row['clauses'] == [{'id': c['id'], 'path': 'intent/function', 'start': c['start'],
                               'end': c['end'], 'text': need.intent.function}
                              for c in contract['clauses'] if c['kind'] == 'postproduction']
    from easel.integrations.openclaw_authoring import (
        _stage_authoring_inputs, _assert_postproduction_input, postproduction_authoring_instruction,
        OpenClawAuthoringBoundaryError,
    )
    instruction = postproduction_authoring_instruction(root)
    staged = tmp_path / 'copied-authoring-inputs'
    _stage_authoring_inputs(root, staged)
    assert (staged / relative).read_bytes() == (root / relative).read_bytes()
    assert _assert_postproduction_input(staged, instruction) == hashlib.sha256((root / relative).read_bytes()).hexdigest()
    (staged / relative).write_text('{}')
    with pytest.raises(OpenClawAuthoringBoundaryError, match='已变化'):
        _assert_postproduction_input(staged, instruction)

    # Keep a valid old report while installing another structurally valid
    # Planning classification for the same frozen text. Neither direct cache
    # reuse nor an already-READY asset can mix these responsibilities.
    from copy import deepcopy
    changed = deepcopy(compiled)
    next(c for c in changed['clauses'] if c[3] == 'postproduction')[3] = 'required'
    changed_contract = validate_compilation(frozen, changed)
    store.write_recovery_record('requirements-' + digest(frozen),
                                {'input': frozen, 'response': changed, 'contract': changed_contract})
    for invoke in (
        lambda: webapp._observe_material_frames(attempt, manifest, attachments),
        lambda: MaterialProductOrchestrator().observe_visual_materials(
            attempt['attempt_id'], executor=webapp._observe_material_frames),
        lambda: ProductionAuthoringIntegration().prepare(attempt),
    ):
        with pytest.raises(DeliveryReportError, match='Planning 要求合同不一致'):
            invoke()
    assert json.loads((store.materials_root / 'observations' / (manifest['input_sha256'] + '.json')).read_text()) == report
    assert calls == before

    # A corrupt current Planning contract is a report fault, never permission
    # for another semantic classification or a new supply request.
    store.write_recovery_record('requirements-' + digest(frozen),
                                {'input': frozen, 'response': compiled, 'contract': {}})
    with pytest.raises(MaterialIntegrationError, match='要求合同无效'):
        ProductionAuthoringIntegration().prepare(attempt)
    with pytest.raises(DeliveryReportError, match='合同无效'):
        webapp._observe_material_frames(attempt, manifest, attachments)
    assert calls == before and len(compilations) == (0 if same_turn_contract else 1)
