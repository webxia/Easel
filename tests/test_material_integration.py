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
    _hypit_audio_tracks_for_source,
)
from easel.integrations import material_supply as material_supply_module
from easel.materials.application.assembly import MaterialBundleAssembler
from easel.materials.application.readiness import MaterialReadinessCalculator
from easel.materials.application.rights import RightsService
from easel.materials.application.compiler import NeedCompiler
from easel.materials.domain import (
    BgmNeedSpec,
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
def material_integration_env(tmp_path, monkeypatch):
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
    attempt = service.create_film_attempt(
        work["id"], package["handoff_id"], preparation_key="b" * 64,
        runtime_status="NOT_CONFIGURED",
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


def test_authoring_selection_uses_actual_svml_refs_and_frozen_revisions(material_integration_env):
    attempt = material_integration_env
    _planning(attempt)
    root = Path(attempt["workspace"]["path"])
    plan, asset, run, bundle, readiness, gaps = _contracts(attempt, root)
    attempt.update(MaterialGateIntegration().record(
        attempt, plan, bundle, run, readiness, gaps,
    )["attempt"])
    attempt.update(ProductionAuthoringIntegration().prepare(attempt)["attempt"])
    eligible = ProductionAuthoringIntegration().qualified_authoring_assets(attempt)
    assert [item["asset_id"] for item in eligible] == [asset.asset_id]
    assert eligible[0]["qualified_need_ids"] == ["need-main"]
    run_path = _record_authored_selection(attempt, asset, root)
    selection_path = root / "productions/easel-authoring/material-selection.json"
    malformed = json.loads(selection_path.read_text(encoding="utf-8"))
    malformed.pop("readiness_revision")
    malformed.pop("readiness_plan_revision")
    malformed.pop("readiness_bundle_revision")
    malformed["readiness_revisions"] = {
        "plan": readiness.plan_revision, "bundle": readiness.bundle_revision,
    }
    malformed["status"] = "selected"
    malformed["assets"].append({"asset_id": "asset-not-used"})
    selection_path.write_text(json.dumps(malformed), encoding="utf-8")

    ProductionAuthoringIntegration().record_selection_from_authored_svml(attempt)
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    assert selection["readiness_revision"] == readiness.bundle_revision
    assert selection["readiness_plan_revision"] == readiness.plan_revision
    assert "readiness_revisions" not in selection
    assert selection["status"] == "SELECTED"
    assert [item["asset_id"] for item in selection["assets"]] == [asset.asset_id]
    assert ProductionAuthoringIntegration().validate_authored_selection(
        attempt, run_path.relative_to(root).as_posix(),
    )["status"] == "READY"
    from easel.integrations.material_layer import copy_bound_validation_run, _hypit_run_markup
    validation = run_path.with_name(".validation.svrun")
    copy_bound_validation_run(run_path, validation)
    assert _hypit_run_markup(validation, root, attempt, plan, bundle, readiness) == run_path.read_text()
    identity = validation.with_suffix(".easel.json")
    bad_identity = json.loads(identity.read_text())
    bad_identity["attempt_id"] = "different-attempt"
    identity.write_text(json.dumps(bad_identity))
    with pytest.raises(MaterialIntegrationError, match="identity"):
        _hypit_run_markup(validation, root, attempt, plan, bundle, readiness)
    run_identity = run_path.with_suffix(".easel.json")
    run_identity.unlink()
    with pytest.raises(MaterialIntegrationError, match="身份记录"):
        copy_bound_validation_run(run_path, validation)


def test_selected_image_extent_uses_inspected_source_dimensions(material_integration_env):
    attempt = material_integration_env
    _planning(attempt)
    root = Path(attempt["workspace"]["path"])
    plan, asset, run, bundle, readiness, gaps = _contracts(attempt, root)
    attempt.update(MaterialGateIntegration().record(
        attempt, plan, bundle, run, readiness, gaps,
    )["attempt"])
    attempt.update(ProductionAuthoringIntegration().prepare(attempt)["attempt"])
    run_path = _record_authored_selection(attempt, asset, root)
    author = root / "productions/easel-authoring/authors/main.svml"
    original = author.read_text(encoding="utf-8")
    author.write_text(original + '<space:Extent id="picture" width="1080" height="1920"/>'
                      '<media-track:Item image={selected} extent={picture} frame={full}/>',
                      encoding="utf-8")
    with pytest.raises(MaterialIntegrationError, match="source dimensions"):
        ProductionAuthoringIntegration().validate_authored_selection(
            attempt, run_path.relative_to(root).as_posix(),
        )


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


def test_script_truth_review_blocks_supply_and_production_until_operator_accepts(material_integration_env, monkeypatch):
    import easel.integrations.material_supply as supply_module

    attempt = material_integration_env
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
        treatment="Treatment", script="This company grew 40 percent last year.", scenes="Scenes",
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
    replanned = PlanningIntegration().persist(attempt, pending["plan"], treatment="Treatment", script="This company grew 40 percent last year.", scenes="Scenes")
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


def test_selected_audio_must_be_normalized_on_distinct_film_tracks(material_integration_env):
    attempt = material_integration_env
    root = Path(attempt["workspace"]["path"])
    task_text = (root / "AUTHORING_TASK.md").read_text(encoding="utf-8")
    assert '<space:Canvas id="canvas" width="1080" height="1920"/>' in task_text
    assert "It accepts no children." in task_text
    assert "authors/recipes.svs" in task_text
    assert "appearance={recipes.media.still}" in task_text
    script = "假设只朗读已批准事实。\n"
    voice = MaterialNeed(
        need_id="voiceover", scope=NeedScope(type=NeedScopeType.GLOBAL, ref="program"),
        media_type=MediaType.AUDIO, role="voiceover", intent=NeedIntent(description="Narration"),
        importance=NeedImportance.REQUIRED,
        modality_spec=VoiceNeedSpec(identity=VoiceIdentityRef(
            source=VoiceIdentitySource.CREATOR_CONTEXT, reference="creator-voice",
        )),
    )
    bgm = MaterialNeed(
        need_id="bgm", scope=NeedScope(type=NeedScopeType.GLOBAL, ref="program"),
        media_type=MediaType.AUDIO, role="bgm", intent=NeedIntent(description="Quiet restrained music"),
        importance=NeedImportance.REQUIRED,
        modality_spec=BgmNeedSpec(mood="restrained", vocals_allowed=False),
    )
    plan = MaterialPlan(
        plan_id="audio-product-plan", creation_id=attempt["creation_id"],
        attempt_id=attempt["attempt_id"], needs=(voice, bgm),
    )
    planning = PlanningIntegration().persist(
        attempt, plan, treatment="# Treatment\n", script=script, scenes="# Scenes\n",
    )
    attempt, plan = planning["attempt"], planning["plan"]
    store = AttemptMaterialStore(root)
    assets = []
    for asset_id, need_id in (("voice-asset", voice.need_id), ("bgm-asset", bgm.need_id)):
        data = f"fixture:{asset_id}".encode()
        locator = store.write_asset_bytes(asset_id, "source.wav", data)
        asset = MaterialAsset(
            asset_id=asset_id, media_type=MediaType.AUDIO,
            file=FileInfo(path=locator, sha256=hashlib.sha256(data).hexdigest(),
                          size=len(data), mime="audio/wav"),
            source=CandidateSource(
                kind="fixture", provider="fixture", provider_asset_id=asset_id,
                **({"creator": "Fixture Composer", "source_page": "https://example.org/bgm/1"}
                   if asset_id == "bgm-asset" else {}),
            ),
            rights=RightsInfo(
                status=RightsStatus.ATTRIBUTION_REQUIRED if asset_id == "bgm-asset" else RightsStatus.KNOWN,
                license_name="Fixture Audio License",
                attribution_required=asset_id == "bgm-asset",
                attribution_text=("Music by Fixture Composer — https://example.org/bgm/1"
                                  if asset_id == "bgm-asset" else None),
                evidence=(RightsEvidence(kind="asset_license", reference=f"fixture://{asset_id}"),),
            ),
                technical=TechnicalInfo(status=TechnicalStatus.PASSED, duration_seconds=5, mime="audio/wav"),
                semantic=_observed_semantic("Narration" if need_id == voice.need_id else "Quiet restrained music"),
        )
        store.write_asset(asset)
        assets.append(asset)
    now = datetime.now(timezone.utc)
    run = SupplyRun(
        supply_run_id="audio-supply-run", plan_id=plan.plan_id, started_at=now,
        finished_at=now, provider_results=(), result_bundle_id="audio-bundle",
    )
    matches = tuple(MaterialMatch(
        need_id=need.need_id, asset_id=asset.asset_id, rank=1, score=1.0,
        reasons=("hard_filter=passed",), qualified=True,
    ) for need, asset in zip((voice, bgm), assets))
    bundle = MaterialBundleAssembler().assemble(
        plan, run, tuple(assets), matches, bundle_id="audio-bundle",
    )
    readiness, gaps = MaterialReadinessCalculator(store=store).calculate(plan, bundle)
    assert readiness.status.value == "READY" and not gaps
    recorded = MaterialGateIntegration().record(attempt, plan, bundle, run, readiness, gaps)
    attempt = recorded["attempt"]
    assert attempt["material_audio_policy"]["requires_audio"] is True
    prepared = ProductionAuthoringIntegration().prepare(attempt, selected_asset_ids=("voice-asset", "bgm-asset"))
    attempt = prepared["attempt"]
    author = root / "productions/easel-authoring/authors/main.svml"
    run_path = root / "productions/easel-authoring/runs/main.svrun"
    author.parent.mkdir(parents=True, exist_ok=True)
    run_path.parent.mkdir(parents=True, exist_ok=True)
    voice_src = store.hypit_source_path(assets[0], author.relative_to(root).as_posix())
    bgm_src = store.hypit_source_path(assets[1], author.relative_to(root).as_posix())
    author.write_text(
        '<?svml using="@hypit/markup@1"?>\n<svml>\n'
        '<import as="media" from="@hypit/media@1"/>\n'
        '<import as="pipeline" from="@hypit/media-pipeline@1"/>\n'
        '<import as="audio" from="@hypit/audio-track@1"/>\n'
        '<import as="film" from="@hypit/film@1"/>\n'
        '<time:Timeline id="speech" clock={clock} end="5s"/>\n'
        f'<media:Audio id="voiceSource" src="{voice_src}"/>\n'
        f'<media:Audio id="bgmSource" src="{bgm_src}"/>\n'
        '<pipeline:Normalize id="voiceNormalized" source={voiceSource} video="none" audio="default" span-authority="audio" clock={clock}/>'
        '<pipeline:Normalize id="bgmNormalized" source={bgmSource} video="none" audio="default" span-authority="audio" clock={clock}/>'
        '<audio:Track id="narrationTrack" timeline={speech.timeline}><audio:Item source={voiceNormalized.media} during="program"/></audio:Track>'
        '<audio:Track id="bgmTrack" timeline={speech.timeline}><audio:Item source={bgmNormalized.media} during="program" gain="0.25" fade-in="12f" fade-out="18f"/></audio:Track>'
        '<film:Film id="main" canvas={canvas} timeline={speech.timeline}>'
        '<film:Track source={narrationTrack.audio}/><film:Track source={bgmTrack.audio}/>'
        '</film:Film></svml>', encoding="utf-8",
    )
    run_path.parent.mkdir(parents=True, exist_ok=True)
    run_path.write_text(json.dumps({
        "schema": "easel-authoring-svrun@1", "creation_id": attempt["creation_id"],
        "attempt_id": attempt["attempt_id"], "plan_id": plan.plan_id,
        "plan_revision": readiness.plan_revision, "bundle_id": bundle.bundle_id,
        "bundle_revision": bundle.revision, "readiness_revision": bundle.revision,
        "authoring_source": "../authors/main.svml",
        "material_selection": "../material-selection.json", "status": "AUTHORING_READY",
        "publication_allowed": False,
        "build": {"enabled": False, "reason": "stops_before_hypit_build"},
    }), encoding="utf-8")
    result = ProductionAuthoringIntegration().validate_authored_selection(
        attempt, "productions/easel-authoring/runs/main.svrun",
    )
    assert result["attempt"]["production_authoring"]["selection_validation"]["audio_tracks"] == {
        "bgm": ["bgmTrack"], "voiceover": ["narrationTrack"],
    }
    assert result["attempt"]["production_authoring"]["selection_validation"]["attributions"][0]["asset_id"] == "bgm-asset"
    assert result["attempt"]["material_audio_policy"]["requires_audio"] is True
    assert _hypit_audio_tracks_for_source(author.read_text(), voice_src) == {"narrationTrack"}

    original_author = author.read_text(encoding="utf-8")
    author.write_text(
        original_author.replace('as="audio" from="@hypit/audio-track@1"',
                                'as="audio-track" from="@hypit/audio-track@1"')
        .replace('<audio:', '<audio-track:').replace('</audio:', '</audio-track:'),
        encoding="utf-8",
    )
    assert _hypit_audio_tracks_for_source(author.read_text(), voice_src) == {"narrationTrack"}
    ProductionAuthoringIntegration().validate_authored_selection(
        result["attempt"], "productions/easel-authoring/runs/main.svrun",
    )
    author.write_text(original_author, encoding="utf-8")

    author.write_text(author.read_text().replace(
        '<audio:Track id="bgmTrack" timeline={speech.timeline}><audio:Item source={bgmNormalized.media} during="program" gain="0.25" fade-in="12f" fade-out="18f"/></audio:Track>',
        '',
    ).replace('<film:Track source={bgmTrack.audio}/>', ''), encoding="utf-8")
    with pytest.raises(MaterialIntegrationError, match="not normalized, placed on an AudioTrack"):
        ProductionAuthoringIntegration().validate_authored_selection(
            result["attempt"], "productions/easel-authoring/runs/main.svrun",
        )

    # With real bound alignment, direct validation cannot accept an agent's
    # guessed subtitles; the same compiler used before static check fixes them.
    from easel.materials.application.voice_delivery import bind_voice_timing
    frozen_script = PlanningIntegration().load(result["attempt"])["script"]
    timing = bind_voice_timing(frozen_script, assets[0], ({
        "text": frozen_script, "start_character": 0, "end_character": len(frozen_script),
        "start_seconds": 0.2, "end_seconds": 4.8,
    },))
    assert timing["status"] == "READY"
    store.write_generation_record("fixture-alignment", {
        "schema": "easel-material-generation@1", "status": "COMPLETE",
        "asset_id": assets[0].asset_id, "asset_sha256": assets[0].file.sha256,
        "need_sha256": hashlib.sha256(plan.needs[0].to_json().encode()).hexdigest(),
        "voice_timing": timing,
    })
    source = original_author.replace('<time:Timeline', '<time:Clock id="clock" frame-rate="24"/><time:Timeline')
    source = source.replace('<film:Film',
        '<space:Frame id="easel-caption-frame"/>'
        '<typo:Style id="easel-caption-style"/>'
        '<typo:Track id="easel-captions" timeline={speech.timeline}/><film:Film')
    author.write_text(source, encoding="utf-8")
    integration = ProductionAuthoringIntegration()
    with pytest.raises(MaterialIntegrationError, match="可信音频时序不一致"):
        integration.validate_authored_selection(result["attempt"], "productions/easel-authoring/runs/main.svrun")
    compiled = integration.compile_narration(result["attempt"], source)
    author.write_text(compiled, encoding="utf-8")
    integration.validate_authored_selection(result["attempt"], "productions/easel-authoring/runs/main.svrun")
    assert 'at="5f" for="110f"' in compiled
    assert '<film:Track source={easel-duck-bgmTrack.audio}/>' in compiled
    assert (root / 'packages/audio-mix/activation.mjs').is_file()
    assert _hypit_audio_tracks_for_source(compiled, bgm_src) == {'bgmTrack'}
    _, _, _, fingerprint_files = service._authoring_file_hash(root, run_path)
    assert 'packages/audio-mix/envelope.mjs' in {entry['path'] for entry in fingerprint_files}
    # Tampering with the copied projection has no authority over the source.
    (root / "productions/easel-authoring/VOICE_TIMING.json").write_text('{"assets": []}')
    assert integration.compile_narration(result["attempt"], source) == compiled
    author.write_text(compiled.replace('for="120f"', 'for="1f"'), encoding="utf-8")
    with pytest.raises(MaterialIntegrationError, match="可信音频时序不一致"):
        integration.validate_authored_selection(result["attempt"], "productions/easel-authoring/runs/main.svrun")


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
    attempt = material_integration_env
    _planning(attempt)
    root = Path(attempt["workspace"]["path"])
    plan, asset, run, bundle, readiness, gaps = _contracts(attempt, root)
    attempt.update(MaterialGateIntegration().record(attempt, plan, bundle, run, readiness, gaps)["attempt"])
    prepared = ProductionAuthoringIntegration().prepare(attempt, selected_asset_ids=())
    assert prepared["status"] == "PENDING_SELECTION"
    started = service.begin_film_authoring(attempt["attempt_id"])
    assert started["authoring_status"] == "AUTHORING_RUNNING"
    run_file = _record_authored_selection(attempt, asset, root)
    completed = service.complete_film_authoring(attempt["attempt_id"], cli=type("CLI", (), {"check": lambda *_: {"ok": True}})())
    assert completed["authoring_status"] == "AUTHORING_READY"
    assert completed["execution_status"] == "BLOCKED"
    monkeypatch.setattr(
        material_supply_module, "product_provider_registry",
        lambda _roots: (_ for _ in ()).throw(AssertionError("ready checkpoint must not repeat Supply")),
    )
    resumed = MaterialProductOrchestrator().run_with_planning(
        completed, (), PlanningIntegration().load(completed),
    )
    assert resumed["status"] == "MATERIAL_READY"
    assert resumed["attempt"]["authoring_status"] == "AUTHORING_READY"


def test_failed_build_retries_from_verified_checkpoints_without_supply_or_submission(
    material_integration_env, tmp_path, monkeypatch,
):
    attempt = material_integration_env
    _planning(attempt)
    root = Path(attempt["workspace"]["path"])
    plan, asset, run, bundle, readiness, gaps = _contracts(attempt, root)
    attempt.update(MaterialGateIntegration().record(attempt, plan, bundle, run, readiness, gaps)["attempt"])
    observation_record = {"schema": "fixture-visual-report", "asset_sha256": asset.file.sha256}
    observation_path = AttemptMaterialStore(root).write_observation_record("fixture-report", observation_record)
    attempt.update(service.update_film_attempt(attempt["attempt_id"], event="fixture_observation",
        material_observation={"status": "COMPLETE", "plan_revision": readiness.plan_revision,
                              "bundle_revision": bundle.revision, "reports": [observation_path]}))
    attempt.update(ProductionAuthoringIntegration().prepare(attempt)["attempt"])
    service.begin_film_authoring(attempt["attempt_id"])
    _record_authored_selection(attempt, asset, root)

    class FailedBuildCLI:
        build_calls = 0

        def check(self, *_args):
            return {"format": "hypit.cli-check@1", "ok": True}

        def plan(self, *_args, **_kwargs):
            return {"format": "hypit.cli-plan@1", "ok": True}

        def pricing(self, *_args, **_kwargs):
            return {"format": "hypit.cli-pricing@1", "requestCount": 1, "groups": []}

        def build(self, *_args, **_kwargs):
            self.build_calls += 1
            return {"format": "hypit.cli-build@1", "build": {
                "id": "bld_retry_001", "work": {"outcome": "failed"},
            }}

        def status(self, _workspace, build_id, **_kwargs):
            return {"format": "hypit.cli-status@1", "build": {
                "id": build_id, "work": {"outcome": "failed"},
            }}

    cli = FailedBuildCLI()
    service.complete_film_authoring(attempt["attempt_id"], cli=cli)
    runtime = tmp_path / "hypit-runtime.json"
    runtime.write_text(json.dumps({
        "format": "hypit.runtime-local@1", "dataRoot": ".hypit/runtimes/local",
        "credentials": {}, "endpoints": {}, "bindings": {},
    }) + "\n", encoding="utf-8")
    service.resolve_film_attempt_runtime(attempt["attempt_id"], str(runtime))
    service.validate_film_attempt(attempt["attempt_id"],
                                  "productions/easel-authoring/runs/main.svrun", cli=cli)
    service.estimate_film_attempt(attempt["attempt_id"], cli=cli)
    service.approve_film_cost(attempt["attempt_id"], 1)
    failed = service.submit_film_build(attempt["attempt_id"], title="失败作品", cli=cli)
    assert failed["execution_status"] == "BUILD_FAILED"
    assert cli.build_calls == 1

    trim_check = service._assert_local_video_trim_ranges
    def reject_copied_invalid_range(item, authored=None):
        if item["attempt_id"] != attempt["attempt_id"]:
            raise HypitIntegrationError("画面截取超出原片范围")
    monkeypatch.setattr(service, "_assert_local_video_trim_ranges", reject_copied_invalid_range)
    blocked = service.retry_failed_film_build(attempt["attempt_id"], cli=cli)
    assert blocked["authoring_status"] == "AUTHORING_FAILED"
    assert blocked["retry_source"]["status"] == "AUTHORING_REPAIR_REQUIRED"
    assert blocked["execution_status"] == "NOT_SUBMITTED"
    assert cli.build_calls == 1
    assert service.retry_failed_film_build(attempt["attempt_id"], cli=cli)["attempt_id"] == blocked["attempt_id"]
    with pytest.raises(HypitIntegrationError, match="checkpoint 尚未验证完成"):
        service.validate_film_attempt(blocked["attempt_id"], "productions/easel-authoring/runs/main.svrun", cli=cli)
    monkeypatch.setattr(service, "_assert_local_video_trim_ranges", trim_check)
    service.begin_film_authoring(blocked["attempt_id"])
    retried = service.complete_film_authoring(blocked["attempt_id"], cli=cli)
    assert retried["retry_source"]["status"] == "READY"
    assert retried["attempt_id"] != attempt["attempt_id"]
    assert retried["authoring_status"] == "AUTHORING_READY"
    assert retried["material_gate"]["status"] == "MATERIAL_READY"
    assert retried["execution_status"] == "NOT_SUBMITTED"
    assert retried["cost"]["approved"] is False
    assert retried["plan"]["status"] == "pending"
    assert retried["retry_source"]["build_id"] == "bld_retry_001"
    retried_store = AttemptMaterialStore(Path(retried["workspace"]["path"]))
    assert json.loads((Path(retried["workspace"]["path"]) / observation_path).read_text()) == observation_record
    assert retried["material_observation"]["plan_revision"] == retried["material_gate"]["plan_revision"]
    assert retried["material_observation"]["bundle_revision"] == retried["material_gate"]["bundle_revision"]
    retried_bundle = retried_store.read_bundle()
    retried_supply = retried_store.read_supply_run(retried_bundle.supply_run_id)
    assert retried_supply.parent_run_id == run.supply_run_id
    assert retried_supply.provider_results == ()
    assert cli.build_calls == 1
    with pytest.raises(HypitIntegrationError, match="显式成本批准"):
        service.submit_film_build(retried["attempt_id"], title="尚未批准", cli=cli)
    assert cli.build_calls == 1
    assert service.retry_failed_film_build(attempt["attempt_id"], cli=cli)["attempt_id"] == retried["attempt_id"]
    assert len(service.list_film_attempts(attempt["creation_id"])) == 2
    assert service.get_film_attempt(attempt["attempt_id"])["execution_status"] == "BUILD_FAILED"

    service.update_film_attempt(retried["attempt_id"], event="test_checkpoint_not_ready",
                                retry_source={**retried["retry_source"], "status": "COPYING"})
    with pytest.raises(HypitIntegrationError, match="checkpoint 尚未验证完成"):
        service.validate_film_attempt(retried["attempt_id"],
                                      "productions/easel-authoring/runs/main.svrun", cli=cli)
    with pytest.raises(HypitIntegrationError, match="checkpoint 尚未验证完成"):
        service.submit_film_build(retried["attempt_id"], title="不应提交", cli=cli)
    service.update_film_attempt(retried["attempt_id"], event="test_checkpoint_restored",
                                retry_source=retried["retry_source"])
    assert cli.build_calls == 1

    def uncertain(_workspace, build_id, **_kwargs):
        return {"format": "hypit.cli-status@1", "build": {"id": build_id,
                "work": {"state": "working"}}}

    cli.status = uncertain
    with pytest.raises(HypitIntegrationError, match="禁止重复提交"):
        service.retry_failed_film_build(attempt["attempt_id"], cli=cli)

    # The same verified checkpoints support a distinct creative revision,
    # with output-bound feedback and a fresh, unapproved production operation.
    output_path = creation.OUTPUTS_DIR / "_creations" / attempt["creation_id"] / "attempts" / attempt["attempt_id"] / "final.mp4"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"deterministic reviewed output")
    output_hash = service._file_sha256(output_path)
    output = {"path": output_path.relative_to(creation.OUTPUTS_DIR).as_posix(),
              "sha256": output_hash, "metadata": {"duration_seconds": 15},
              "technical_qc": {"status": "pass", "output_name": "final.video", "sha256": output_hash}}
    service.update_film_attempt(attempt["attempt_id"], event="fixture_completed_output",
                                execution_status="BUILD_COMPLETE", outputs={"final.video": output})
    review = {"outputName": "final.video", "sha256": output_hash,
              "truth": {"status": "modify"}, "style": {"status": "modify"},
              "human": {"status": "rejected"},
              "feedback": [{"kind": "composition", "text": "开头构图更紧凑", "time_seconds": 2}]}
    with pytest.raises(HypitIntegrationError, match="时间点"):
        service.record_film_review(attempt["attempt_id"],
                                  {**review, "feedback": [{**review["feedback"][0], "time_seconds": 16}]})
    service.record_film_review(attempt["attempt_id"], review)
    with pytest.raises(HypitIntegrationError, match="绑定"):
        service.revise_film_output(attempt["attempt_id"], output_name="final.video", sha256="0" * 64, cli=cli)
    revision = service.revise_film_output(attempt["attempt_id"], output_name="final.video", sha256=output_hash, cli=cli)
    assert revision["attempt_id"] not in {attempt["attempt_id"], retried["attempt_id"]}
    assert revision["authoring_status"] == "READY_FOR_EXTERNAL_AUTHORING"
    assert revision["execution_status"] == "NOT_SUBMITTED"
    assert revision["cost"]["approved"] is False
    assert revision["plan"]["status"] == "pending"
    assert revision["outputs"] == {}
    assert revision["revision_feedback"]["feedback"] == review["feedback"]
    assert cli.build_calls == 1
    assert service.revise_film_output(attempt["attempt_id"], output_name="final.video", sha256=output_hash, cli=cli)["attempt_id"] == revision["attempt_id"]
    service.begin_film_authoring(revision["attempt_id"])
    revision_root = Path(revision["workspace"]["path"])
    _record_authored_selection(revision, asset, revision_root)
    service.complete_film_authoring(revision["attempt_id"], cli=cli)
    service.resolve_film_attempt_runtime(revision["attempt_id"], str(runtime))
    service.validate_film_attempt(revision["attempt_id"], "productions/easel-authoring/runs/main.svrun", cli=cli)
    service.estimate_film_attempt(revision["attempt_id"], cli=cli)
    with pytest.raises(HypitIntegrationError, match="显式成本批准"):
        service.submit_film_build(revision["attempt_id"], title="尚未批准修改", cli=cli)
    assert cli.build_calls == 1
    service.record_film_review(attempt["attempt_id"], {**review, "feedback": [{"kind": "general", "text": "改写脚本"}]})
    with pytest.raises(HypitIntegrationError, match="仅支持"):
        service.revise_film_output(attempt["attempt_id"], output_name="final.video", sha256=output_hash, cli=cli)

    # The system owns a separate reason for the same checkpoint fork. It must
    # not forge Creator rejection, reuse a paid approval or mutate the source.
    from easel.creation_delivery import SCHEMA
    quality = {'schema': 'easel-output-quality@1', 'status': 'REPAIR_REQUIRED',
               'binding': {'output_name': 'final.video', 'sha256': output_hash},
               'measurements': {'defects': [{'kind': 'near_black', 'reason': '开头主体接近全黑', 'time_seconds': 1.}]},
               'visual': [], 'frames': []}
    service.update_film_attempt(attempt['attempt_id'], event='fixture_machine_review',
                               review={'system': quality, 'human': {'status': 'pending'}})
    with creation.edit_creation(attempt['creation_id']) as current:
        current['delivery'] = {'schema': SCHEMA, 'recovering_quality_from': attempt['attempt_id'],
                               'quality_repairs': [attempt['attempt_id']]}
    repaired = service.repair_film_quality(attempt['attempt_id'], cli=cli)
    assert repaired['revision_feedback']['origin'] == 'system_quality'
    assert repaired['revision_feedback']['allowed_changes'] == ['visual']
    assert repaired['cost']['approved'] is False and repaired['plan']['status'] == 'pending'
    assert repaired['outputs'] == {} and repaired['execution_status'] == 'NOT_SUBMITTED'
    assert service.get_film_attempt(attempt['attempt_id'])['review']['human']['status'] == 'pending'
    assert service.repair_film_quality(attempt['attempt_id'], cli=cli)['attempt_id'] == repaired['attempt_id']
    assert cli.build_calls == 1


def test_int04_workspace_asset_uses_ordinary_hypit_media_route(material_integration_env):
    attempt = material_integration_env
    _planning(attempt)
    root = Path(attempt["workspace"]["path"])
    plan, asset, run, bundle, readiness, gaps = _contracts(attempt, root)
    attempt.update(MaterialGateIntegration().record(attempt, plan, bundle, run, readiness, gaps)["attempt"])
    attempt.update(ProductionAuthoringIntegration().prepare(
        attempt, selected_asset_ids=(),
    )["attempt"])
    run_path = root / "productions/easel-authoring/runs/main.svrun"
    run_path.parent.mkdir(parents=True, exist_ok=True)
    _record_authored_selection(attempt, asset, root)
    selected = json.loads((root / "productions/easel-authoring/material-selection.json").read_text(encoding="utf-8"))
    src = selected["assets"][0]["src"]
    assert not src.startswith("/") and "Candidate" not in src and "satisfy" not in src
    (root / "productions/easel-authoring/authors/main.svml").write_text(
        '<?svml using="@hypit/markup@1"?>\n<svml>\n'
        '<import as="time" from="@hypit/timeline-author@1"/>\n'
        '<import as="pipeline" from="@hypit/media-pipeline@1"/>\n'
        '<import as="media" from="@hypit/media@1"/>\n'
        '<time:Clock id="clock" frame-rate="30"/>\n'
        f'<media:Image id="source" src="{src}"/>\n'
        '<pipeline:StillVideo id="held" source={source} duration="1s" clock={clock}/>\n</svml>\n',
        encoding="utf-8",
    )
    fake_cli = type("CLI", (), {"check": lambda *_: {"ok": True}})()
    checked = MaterialHypitBridge().check(
        attempt, "productions/easel-authoring/runs/main.svrun", cli=fake_cli,
    )
    assert checked["status"] == "CHECKED"
    assert checked["check"]["ok"] is True
    run_path.write_text("<svrun><satisfy/></svrun>", encoding="utf-8")
    with pytest.raises(MaterialIntegrationError, match="legacy binding"):
        MaterialHypitBridge().check(attempt, "productions/easel-authoring/runs/main.svrun")
    with pytest.raises(MaterialIntegrationError, match="非法"):
        MaterialHypitBridge().check(attempt, "../outside.svrun")


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
    assert len(searches) == failed_searches + 2 and len(acquisitions) == 1
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
                         constraints={"preferred_style": "high contrast documentary"},
                         importance=NeedImportance.REQUIRED),
        ))
    original = plan.model_dump()
    planning = PlanningIntegration().persist(attempt, plan, treatment="两个具体观察，保留高对比时钟镜头。",
                                              script="假设站在夜班公交站。", scenes="公交站与时钟。")
    assert plan.model_dump() == original
    bound = planning["plan"]
    assert bound.needs[0].constraints["preferred_style"] == style
    assert bound.needs[1].constraints["preferred_style"] == "high contrast documentary"
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
    assert len(requests) == 2, [(row.get("failures"), row.get("skipped")) for row in result.routing_trace]
    assert requests[0].semantic_queries[0] == "bus stop " + style
    assert requests[1].semantic_queries[0] == "station clock high contrast documentary"
    assert preferences[0][1][0].preferred_values == (style,)
    assert preferences[1][1][0].preferred_values == ("high contrast documentary",)
    assert handoff.load_frozen_creative_mode(old)[0].get("voice_delivery") is None
    voice = MaterialNeed(need_id="narration", scope=NeedScope(type=NeedScopeType.GLOBAL, ref="program"),
        media_type=MediaType.AUDIO, role="旁白", intent=NeedIntent(description="平静的事后观察"),
        modality_spec=VoiceNeedSpec(identity=VoiceIdentityRef(source=VoiceIdentitySource.DIRECTOR_INTENT,
            reference="已批准的预置声音"), delivery_description="自然平静，稍加快以保持短句的连贯性"),
        constraints={"voice_delivery": {"pace_ratio": 1.05}}, importance=NeedImportance.REQUIRED)
    voice_plan = plan.model_copy(update={"needs": (voice,)})
    persisted_voice = PlanningIntegration().persist(attempt, voice_plan, treatment="自然讲述",
                                                   script="假设站在夜班公交站。", scenes="站台观察")
    assert persisted_voice["plan"].needs[0].constraints["voice_delivery"] == {
        "pace_ratio": 1.05, "pitch_semitones": 0, "tone": "neutral"}
    assert "preferred_style" not in persisted_voice["plan"].needs[0].constraints
    assert persisted_voice["plan"].needs[0].modality_spec.text_sha256 == hashlib.sha256("假设站在夜班公交站。".encode()).hexdigest()


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
    attempt = material_integration_env
    _planning(attempt)
    root = Path(attempt["workspace"]["path"])
    plan, asset, run, bundle, readiness, gaps = _contracts(attempt, root)
    attempt.update(MaterialGateIntegration().record(attempt, plan, bundle, run, readiness, gaps)["attempt"])
    attempt.update(ProductionAuthoringIntegration().prepare(attempt)["attempt"])
    service.begin_film_authoring(attempt["attempt_id"])
    _record_authored_selection(attempt, asset, root)
    asset_path = AttemptMaterialStore(root).resolve_asset_locator(asset.file.path)
    asset_path.write_bytes(b"tampered after admission")

    with pytest.raises(MaterialIntegrationError, match="MaterialReadiness 已失效"):
        ProductionAuthoringIntegration().validate_authored_selection(
            attempt, "productions/easel-authoring/runs/main.svrun",
        )
    runtime = tmp_path / "hypit-runtime.json"
    runtime.write_text(json.dumps({"format": "hypit.runtime-local@1", "dataRoot": ".hypit/runtimes/local",
                                   "credentials": {}, "endpoints": {}, "bindings": {}}), encoding="utf-8")
    service.resolve_film_attempt_runtime(attempt["attempt_id"], str(runtime))
    with pytest.raises(MaterialIntegrationError, match="MaterialReadiness 已失效"):
        service.submit_film_build(attempt["attempt_id"], title="must be blocked")


def test_selected_asset_must_be_referenced_by_actual_authored_svml(material_integration_env):
    attempt = material_integration_env
    _planning(attempt)
    root = Path(attempt["workspace"]["path"])
    plan, asset, run, bundle, readiness, gaps = _contracts(attempt, root)
    attempt.update(MaterialGateIntegration().record(attempt, plan, bundle, run, readiness, gaps)["attempt"])
    attempt.update(ProductionAuthoringIntegration().prepare(attempt)["attempt"])
    _record_authored_selection(attempt, asset, root)
    author = root / "productions/easel-authoring/authors/main.svml"
    author.write_text('<media:Image id="another" src="materials/assets/other/original.png"/>', encoding="utf-8")
    with pytest.raises(MaterialIntegrationError, match="SVML does not reference selected MaterialAsset"):
        ProductionAuthoringIntegration().validate_authored_selection(
            attempt, "productions/easel-authoring/runs/main.svrun",
        )


@pytest.mark.parametrize("extra, error", [
    ('<?svml using="@hypit/gpt-image@1"?>', "禁止在 SVML/SVRun 中生成媒体"),
    ('<media:Image id="unadmitted" src="../../../../other.png"/>', "media absent from the admitted"),
])
def test_production_rejects_generated_or_unadmitted_media_sources(material_integration_env, extra, error):
    attempt = material_integration_env
    _planning(attempt)
    root = Path(attempt["workspace"]["path"])
    plan, asset, run, bundle, readiness, gaps = _contracts(attempt, root)
    attempt.update(MaterialGateIntegration().record(attempt, plan, bundle, run, readiness, gaps)["attempt"])
    attempt.update(ProductionAuthoringIntegration().prepare(attempt)["attempt"])
    _record_authored_selection(attempt, asset, root)
    author = root / "productions/easel-authoring/authors/main.svml"
    author.write_text(author.read_text(encoding="utf-8") + "\n" + extra, encoding="utf-8")

    with pytest.raises(MaterialIntegrationError, match=error):
        ProductionAuthoringIntegration().validate_authored_selection(
            attempt, "productions/easel-authoring/runs/main.svrun",
        )


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
    _record_authored_selection(attempt, unmatched_asset, root)

    with pytest.raises(MaterialIntegrationError, match="Need ↔ Asset Match"):
        ProductionAuthoringIntegration().validate_authored_selection(
            attempt, "productions/easel-authoring/runs/main.svrun",
        )


def test_selection_is_bound_to_attempt_and_readiness_revisions(material_integration_env):
    attempt = material_integration_env
    _planning(attempt)
    root = Path(attempt["workspace"]["path"])
    plan, asset, run, bundle, readiness, gaps = _contracts(attempt, root)
    attempt.update(MaterialGateIntegration().record(attempt, plan, bundle, run, readiness, gaps)["attempt"])
    attempt.update(ProductionAuthoringIntegration().prepare(attempt)["attempt"])
    _record_authored_selection(attempt, asset, root)
    selection_path = root / "productions/easel-authoring/material-selection.json"
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    selection["attempt_id"] = "fa_" + "f" * 32
    selection_path.write_text(json.dumps(selection), encoding="utf-8")

    with pytest.raises(MaterialIntegrationError, match="current Plan/Bundle revision"):
        ProductionAuthoringIntegration().validate_authored_selection(
            attempt, "productions/easel-authoring/runs/main.svrun",
        )


def test_selection_manifest_mutation_after_authoring_is_blocked(material_integration_env):
    attempt = material_integration_env
    _planning(attempt)
    root = Path(attempt["workspace"]["path"])
    plan, asset, run, bundle, readiness, gaps = _contracts(attempt, root)
    attempt.update(MaterialGateIntegration().record(attempt, plan, bundle, run, readiness, gaps)["attempt"])
    attempt.update(ProductionAuthoringIntegration().prepare(attempt)["attempt"])
    run_path = _record_authored_selection(attempt, asset, root)
    validated = ProductionAuthoringIntegration().validate_authored_selection(
        attempt, run_path.relative_to(root).as_posix(),
    )
    attempt = validated["attempt"]
    selection_path = root / "productions/easel-authoring/material-selection.json"
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    selection["operator_note"] = "edited after validation"
    selection_path.write_text(json.dumps(selection), encoding="utf-8")

    with pytest.raises(MaterialIntegrationError, match="unsupported fields"):
        ProductionAuthoringIntegration().assert_selection_current(
            attempt, "productions/easel-authoring/runs/main.svrun",
        )


def test_easel_run_manifest_is_adapted_to_official_hypit_run_markup(material_integration_env):
    attempt = material_integration_env
    _planning(attempt)
    root = Path(attempt["workspace"]["path"])
    plan, asset, supply_run, bundle, readiness, gaps = _contracts(attempt, root)
    attempt.update(MaterialGateIntegration().record(
        attempt, plan, bundle, supply_run, readiness, gaps,
    )["attempt"])
    attempt.update(ProductionAuthoringIntegration().prepare(attempt)["attempt"])
    run_path = _record_authored_selection(attempt, asset, root)
    selection_path = root / "productions/easel-authoring/material-selection.json"
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    selection["status"] = "PRODUCTION_SELECTED"
    selection_path.write_text(json.dumps(selection), encoding="utf-8")
    author_path = root / "productions/easel-authoring/authors/main.svml"
    authored_body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svml xmlns:media="https://hypit.ai/svml/media">\n'
        f'<media:Image id="selected" src="{selection["assets"][0]["src"]}"/>\n'
        '</svml>\n'
    )
    author_path.write_text(authored_body, encoding="utf-8")
    run_path.write_text(json.dumps({
        "schema": "easel-authoring-svrun@1",
        "creation_id": attempt["creation_id"],
        "attempt_id": attempt["attempt_id"],
        "plan_id": plan.plan_id,
        "plan_revision": readiness.plan_revision,
        "bundle_id": bundle.bundle_id,
        "bundle_revision": bundle.revision,
        "readiness_revision": readiness.bundle_revision,
        "authoring_source": "../authors/main.svml",
        "material_selection": "../material-selection.json",
        "status": "AUTHORING_READY",
        "publication_allowed": False,
        "build": {"enabled": False, "reason": "stops_before_hypit_build"},
    }), encoding="utf-8")

    validated = ProductionAuthoringIntegration().validate_authored_selection(
        attempt, "productions/easel-authoring/runs/main.svrun",
    )
    run_text = run_path.read_text(encoding="utf-8")
    author_text = author_path.read_text(encoding="utf-8")
    assert json.loads(selection_path.read_text(encoding="utf-8"))["status"] == "SELECTED"
    assert run_text.startswith('<?svml using="@hypit/run-markup@1"?>')
    assert '<author source="../authors/main.svml"/>' in run_text
    assert '<target output="final.video"/>' in run_text
    assert author_text.startswith('<?svml using="@hypit/markup@1"?>\n<svml')
    assert authored_body.partition("?>")[2].lstrip() in author_text

    # A retry may serialize the same Agent-authored selection differently;
    # canonical semantic hashing must keep the verified selection idempotent.
    retry_selection = json.loads(selection_path.read_text(encoding="utf-8"))
    retry_selection["assets"].reverse()
    for selected_asset in retry_selection["assets"]:
        selected_asset["src"] = f"../../materials/assets/{selected_asset['asset_id']}/original.jpg"
        selected_asset.pop("qualified_need_ids", None)
    retry_selection["identity"] = {
        "creation_id": attempt["creation_id"],
        "attempt_id": attempt["attempt_id"],
        "handoff_id": attempt["handoff"]["handoff_id"],
    }
    retry_selection["revision"] = retry_selection["bundle_revision"]
    selection_path.write_text(json.dumps(retry_selection, ensure_ascii=False), encoding="utf-8")
    retried = ProductionAuthoringIntegration().validate_authored_selection(
        validated["attempt"], "productions/easel-authoring/runs/main.svrun",
    )
    assert retried["status"] == "READY"
    normalized = json.loads(selection_path.read_text(encoding="utf-8"))
    assert "identity" not in normalized and "revision" not in normalized
    assert [item["asset_id"] for item in normalized["assets"]] == [
        item["asset_id"] for item in retry_selection["assets"]
    ]
    assert all(item["src"].startswith("../../../materials/assets/") for item in normalized["assets"])


@pytest.mark.parametrize("alias", ["identity", "revision"])
def test_selection_retry_rejects_mismatched_redundant_identity_alias(material_integration_env, alias):
    attempt = material_integration_env
    _planning(attempt)
    root = Path(attempt["workspace"]["path"])
    plan, asset, _, bundle, readiness, gaps = _contracts(attempt, root)
    attempt.update(MaterialGateIntegration().record(attempt, plan, bundle, _, readiness, gaps)["attempt"])
    attempt.update(ProductionAuthoringIntegration().prepare(attempt)["attempt"])
    run_path = _record_authored_selection(attempt, asset, root)
    validated = ProductionAuthoringIntegration().validate_authored_selection(
        attempt, run_path.relative_to(root).as_posix(),
    )
    selection_path = root / "productions/easel-authoring/material-selection.json"
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    if alias == "identity":
        selection[alias] = {
            "creation_id": attempt["creation_id"],
            "attempt_id": attempt["attempt_id"],
            "handoff_id": "ho_" + "0" * 32,
        }
    else:
        selection[alias] = "sha256:" + "0" * 64
    selection_path.write_text(json.dumps(selection), encoding="utf-8")
    with pytest.raises(MaterialIntegrationError, match="alias does not match"):
        ProductionAuthoringIntegration().validate_authored_selection(
            validated["attempt"], run_path.relative_to(root).as_posix(),
        )


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
    _record_authored_selection(attempt, asset, root)
    result = ProductionAuthoringIntegration().validate_authored_selection(
        attempt, "productions/easel-authoring/runs/main.svrun",
    )
    persisted = result["attempt"]["production_authoring"]["selection_validation"]["attributions"]
    assert persisted == [{
        "asset_id": asset.asset_id, "creator": "Ada",
        "credit_text": f"Photo by Ada — {source_page}", "source_page": source_page,
        "destination": "export_credits", "rights_status": "ATTRIBUTION_REQUIRED",
        "evidence_references": ["fixture:license"],
    }]


@pytest.mark.parametrize(('interrupt_after_supply', 'automatic'), [(False, False), (True, False), (True, True)])
def test_material_recovery_preserves_generation_and_reconciles_without_resupply(
        material_integration_env, monkeypatch, interrupt_after_supply, automatic):
    from easel.integrations import material_recovery as recovery
    attempt = service.update_film_attempt(material_integration_env["attempt_id"],
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


@pytest.mark.parametrize(('second_verdict', 'known_rights', 'expected'), [
    ('unsuitable', True, 'MATERIAL_NOT_READY'),
    ('suitable', True, 'MATERIAL_READY'),
    ('suitable', False, 'MATERIAL_NOT_READY'),
])
def test_system_visual_observation_is_per_need_and_resumes_without_supply(
        material_integration_env, monkeypatch, second_verdict, known_rights, expected):
    import base64
    import io
    from easel.creation_delivery import DeliveryExecutionUncertain
    from easel.materials.application.matching import MaterialMatcher
    from easel.materials.application.visual_observation import SCHEMA, observed_match, prepare_observation
    import web.app as webapp

    attempt = material_integration_env
    root = Path(attempt['workspace']['path'])
    store = AttemptMaterialStore(root)
    plan, asset, run, _, _, _ = _contracts(attempt, root)
    first = plan.needs[0].model_copy(update={'constraints': {'preferred_style': 'quiet red', 'logo': False}})
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
    calls = []
    interrupted = False

    def observe(message, timeout, session_id, *, attachments):
        nonlocal interrupted
        manifest = json.loads(message.split("输入：", 1)[1].split("\n", 1)[0])
        assert '不请求 Provider/Hypit' in message
        need_id = manifest['need']['need_id']
        if need_id == second.need_id and not interrupted:
            interrupted = True
            raise DeliveryExecutionUncertain('same observation still running')
        calls.append(need_id)
        assert manifest['need']['constraints']['preferred_style'] == 'quiet red'
        assert manifest['asset_sha256'] == asset.file.sha256
        assert len(attachments) == 1
        raw = base64.b64decode(attachments[0]['content'])
        assert hashlib.sha256(raw).hexdigest() == manifest['frames'][0]['sha256']
        with Image.open(io.BytesIO(raw)) as decoded:
            assert decoded.getpixel((0, 0))[0] > 240  # actual bytes, not the provider title
        verdict = 'suitable' if need_id == first.need_id else second_verdict
        report = {'schema': SCHEMA, 'input_sha256': manifest['input_sha256'], 'verdict': verdict,
                'caption': 'A red field', 'style': 'quiet red', 'reason': 'Fixed fixture visual assessment',
                'logo_present': False, 'visible_text_present': False,
                'frames': [{'index': 0, 'observed': True, 'related': verdict == 'suitable', 'description': 'red field'}]}
        (root / 'materials/observations' / (manifest['input_sha256'] + '.json')).write_text(json.dumps(report))
        return ''

    monkeypatch.setattr(webapp, 'run_agent_sync', observe)
    with pytest.raises(DeliveryExecutionUncertain):
        MaterialProductOrchestrator().observe_visual_materials(attempt['attempt_id'], executor=webapp._observe_material_frames)
    result = MaterialProductOrchestrator().observe_visual_materials(attempt['attempt_id'], executor=webapp._observe_material_frames)
    assert calls == [first.need_id, second.need_id]
    assert result['material_status'] == expected
    assert result['attempt']['material_observation']['status'] == 'COMPLETE'
    observed = store.read_asset(asset.asset_id)
    assert observed.rights == asset.rights and observed.source == asset.source
    assert observed.semantic.caption == asset.semantic.caption
    assert len(observed.semantic.inferences) == 2
    assert observed_match(first, observed) is True
    assert observed_match(second, observed) is (second_verdict == 'suitable')
    # Exact-looking metadata cannot override the independent negative judgment.
    assert bool(MaterialMatcher().match(second, [observed]).matches) is (known_rights and second_verdict == 'suitable')
    changed = first.model_copy(update={'constraints': {'preferred_style': 'new style'}})
    assert observed_match(changed, observed) is False
    assert not MaterialMatcher().match(changed, [observed]).matches
    if expected == 'MATERIAL_READY':
        assert result['attempt']['production_authoring']['status'] == 'PENDING_SELECTION'
    candidates = MaterialProductOrchestrator().material_rights_candidates(attempt['attempt_id'])
    assert candidates[0]['semantic_reviewed_need_ids'] == []
    assert first.need_id in candidates[0]['system_observed_need_ids']
    # A changed source cannot inherit an observation or be silently regenerated.
    store.resolve_asset_locator(asset.file.path).write_bytes(b'changed')
    with pytest.raises(ValueError, match='素材字节'):
        prepare_observation(first, observed, store.resolve_asset_locator(asset.file.path))


@pytest.mark.parametrize('usable_index', [3, None])
def test_visual_replacement_stops_at_usable_choice_or_bound_and_reuses_saved_report(
        material_integration_env, monkeypatch, usable_index):
    import io
    from easel.materials.application.visual_observation import SCHEMA, MAX_VISUAL_CANDIDATES
    attempt = material_integration_env
    root = Path(attempt['workspace']['path'])
    store = AttemptMaterialStore(root)
    plan, original, run, _, _, _ = _contracts(attempt, root)
    assets = []
    for index in range(MAX_VISUAL_CANDIDATES + 1):
        raw = io.BytesIO()
        Image.new('RGB', (32, 24), (index * 20, 0, 0)).save(raw, format='PNG')
        data = raw.getvalue()
        asset_id = f'candidate-{index:02d}'
        locator = store.write_asset_bytes(asset_id, 'frame.png', data)
        asset = original.model_copy(update={'asset_id': asset_id,
            'file': FileInfo(path=locator, sha256=hashlib.sha256(data).hexdigest(), size=len(data), mime='image/png'),
            'semantic': SemanticInfo(caption=plan.needs[0].intent.description)})
        store.write_asset(asset)
        assets.append(asset)
    planning = PlanningIntegration().persist(attempt, plan, treatment='T', script='假设脚本内容。', scenes='S')
    plan = planning['plan']
    bundle = MaterialBundleAssembler().assemble(plan, run, tuple(assets), (), bundle_id='bundle-int-1')
    readiness, gaps = MaterialReadinessCalculator(store=store).calculate(plan, bundle)
    MaterialGateIntegration().record(planning['attempt'], plan, bundle, run, readiness, gaps)
    calls = []
    def observe(current, manifest, attachments):
        calls.append(manifest['asset_id'])
        good = manifest['asset_id'] == f'candidate-{usable_index:02d}' if usable_index is not None else False
        return {'schema': SCHEMA, 'input_sha256': manifest['input_sha256'],
            'verdict': 'suitable' if good else 'unsuitable', 'caption': 'fixture content',
            'style': 'fixture style', 'reason': 'fixture observation', 'logo_present': False,
            'visible_text_present': False,
            'frames': [{'index': 0, 'observed': True, 'related': good, 'description': 'actual colored frame'}]}
    write_asset = AttemptMaterialStore.write_asset
    interrupted = False
    def interrupt_record(self, asset):
        nonlocal interrupted
        if asset.asset_id == 'candidate-02' and asset.semantic.inferences and not interrupted:
            interrupted = True
            raise OSError('模拟报告已保存、Asset 尚未更新时中断')
        return write_asset(self, asset)
    monkeypatch.setattr(AttemptMaterialStore, 'write_asset', interrupt_record)
    monkeypatch.setattr(material_supply_module.ProductMaterialSupply, 'run',
                        lambda *a, **k: pytest.fail('existing candidates must not trigger a Provider'))
    with pytest.raises(OSError, match='模拟报告'):
        MaterialProductOrchestrator().observe_visual_materials(attempt['attempt_id'], executor=observe)
    result = MaterialProductOrchestrator().observe_visual_materials(attempt['attempt_id'], executor=observe)
    expected_count = usable_index + 1 if usable_index is not None else MAX_VISUAL_CANDIDATES
    assert calls == [a.asset_id for a in assets[:expected_count]]
    assert result['material_status'] == ('MATERIAL_READY' if usable_index is not None else 'MATERIAL_NOT_READY')
    MaterialProductOrchestrator().observe_visual_materials(attempt['attempt_id'], executor=observe)
    assert len(calls) == expected_count
    assert not store.read_asset(assets[-1].asset_id).semantic.inferences


@pytest.mark.parametrize('outcome', ['budget', 'uncertain', 'scope_changed', 'account_changed', 'video_resume'])
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

    attempt = material_integration_env
    is_video = outcome == 'video_resume'
    expected_cost = '1.650000' if is_video else '0.025000'
    plan = MaterialPlan(plan_id='commission-plan', creation_id=attempt['creation_id'], attempt_id=attempt['attempt_id'],
        needs=tuple(MaterialNeed(need_id=f'image-{i}', scope=NeedScope(type=NeedScopeType.SCENE, ref=f'scene-{i}'),
            media_type=MediaType.VIDEO if is_video else MediaType.IMAGE,
            role='主视觉', intent=NeedIntent(description=f'不同场景 {i}'),
            constraints={'allow_generation': True}, importance=NeedImportance.REQUIRED) for i in range(2)))
    planning = PlanningIntegration().persist(attempt, plan, treatment='纪实观察', script='假设场景。', scenes='两个不同场景')
    attempt.update(planning['attempt'])
    reviewed = PlanningIntegration().review_script(attempt, confirm_all_claims_reviewed=True,
        expected_script_sha256=planning['truth_ledger']['script_sha256'],
        expected_truth_packet_sha256=planning['truth_ledger']['truth_packet_sha256'])
    attempt.update(reviewed['attempt'])
    MaterialProductOrchestrator()._run(attempt, (), planning=PlanningIntegration().load(attempt))
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
        return ('## 图像\n单价：元/张\n| image-01 | 图片 | 0.025 |\n'
                '## 视频\n**视频生成-输出价格**\n| MiniMax-H3-Max | 480P | 按秒计费 | 0.33 元/秒 |\n')
    monkeypatch.setattr(minimax_pricing, 'read_public_contract', quote_document)
    proposal = '已确认的隔离委托'
    with creation.edit_creation(attempt['creation_id']) as work:
        work['origin'] = {'type': 'chat'}
        work['chat_workflow'] = {'proposal_status': 'READY_FOR_CONFIRMATION'}
    preview = commissioned.generation_budget_preview()
    budget = {'maxCostCny': 2 if is_video else 0.03, 'scopeSha256': preview['scope_sha256']}
    work = creation.confirm_chat_proposal(attempt['creation_id'], 'fixture-confirm',
        delivery_proposal=proposal, proposal_sha256=hashlib.sha256(proposal.encode()).hexdigest(), generation_budget=budget)
    # Replayed confirmation cannot increase or retrofit an authorization.
    with pytest.raises(creation.CreationError, match='扩大素材预算'):
        creation.confirm_chat_proposal(work['id'], 'replayed', delivery_proposal=proposal,
            proposal_sha256=hashlib.sha256(proposal.encode()).hexdigest(), generation_budget={**budget, 'maxCostCny': 1})
    with pytest.raises(creation.CreationError, match='后台交付者'):
        commissioned.generate_for_commission(attempt['attempt_id'])

    media = BytesIO()
    Image.new('RGB', (64, 64), 'teal').save(media, format='PNG')
    calls, dispatches = [], []
    class FakeImage:
        model = 'image-01'
        def __init__(self, *args, **kwargs):
            pass
        def generate(self, prompt, **kwargs):
            snapshot = creation.get_creation(work['id'])['delivery']
            reservation = list(snapshot['material_generations'].values())[0]
            assert reservation['status'] == 'reserved' and reservation['quote']['upper_estimate'] == '0.025000'
            calls.append(prompt)
            if outcome == 'uncertain':
                raise TimeoutError('fixture lost synchronous response')
            return MiniMaxImageResult(self.model, media.getvalue())
    monkeypatch.setattr(providers, 'MiniMaxImageAdapter', FakeImage)
    if is_video:
        from easel.materials.application import generation as video_generation
        class FakeVideo:
            model = 'MiniMax-H3-Max'
            waits = []
            def __init__(self, *args, **kwargs):
                pass
            def submit(self, prompt, **kwargs):
                record = list(creation.get_creation(work['id'])['delivery']['material_generations'].values())[0]
                assert record['status'] == 'reserved' and record['quote']['upper_estimate'] == expected_cost
                calls.append(prompt)
                return SimpleNamespace(task_id='fixture-paid-video')
            def wait(self, task_id):
                self.waits.append(task_id)
                if len(self.waits) == 1:
                    raise TimeoutError('fixture query failed after task identity was saved')
                return SimpleNamespace(task_id=task_id, video_url='https://fixture.invalid/not-downloaded.mp4')
        class LocalAcquirer:
            def __init__(self, store):
                self.store = store
            def acquire(self, candidate):
                body = b'fixture-only-video-intake'
                path = self.store.write_asset_bytes('fixture-video', 'original.mp4', body)
                asset = MaterialAsset(asset_id='fixture-video', media_type=MediaType.VIDEO,
                    file=FileInfo(path=path, sha256=hashlib.sha256(body).hexdigest(), size=len(body), mime='video/mp4'),
                    source=candidate.source, rights=RightsInfo(status=RightsStatus.UNKNOWN),
                    technical=TechnicalInfo(status=TechnicalStatus.PASSED, mime='video/mp4', duration_seconds=5))
                self.store.write_asset(asset)
                return asset
        monkeypatch.setattr(providers, 'MiniMaxVideoAdapter', FakeVideo)
        monkeypatch.setattr(video_generation, 'create_material_generation_acquirer', LocalAcquirer)
        monkeypatch.setattr(video_generation, 'TechnicalInspector', lambda store: SimpleNamespace(inspect_and_persist=lambda asset: asset))
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
            await asyncio.to_thread(commissioned.generate_for_commission, attempt['attempt_id'])
        elif operation == 'observe_material':
            latest = service.get_film_attempt(attempt['attempt_id'])['material_gate']
            service.update_film_attempt(attempt['attempt_id'], event='fixture_observation',
                material_observation={'status': 'COMPLETE', 'plan_revision': latest['plan_revision'], 'bundle_revision': latest['bundle_revision']})
        else:
            pytest.fail(operation)
    for _ in range(6):
        asyncio.run(advance_creation(work['id'], execute))
    current = creation.get_creation(work['id'])
    ledger = list(current['delivery']['material_generations'].values())
    assert sum(float(r['quote']['upper_estimate']) for r in ledger if r.get('quote')) == float(expected_cost)
    if outcome in {'scope_changed', 'account_changed'}:
        assert not calls and current['delivery']['status'] == 'failed'
    else:
        assert len(calls) == 1  # the second Need cannot exceed the remaining budget
        assert 'budget_exceeded' in {r['status'] for r in ledger}
        assert next_operation(current)[1] == ('material_submission_uncertain' if outcome == 'uncertain' else 'needs_generation_approval')
    store = AttemptMaterialStore(attempt['workspace']['path'])
    if outcome in {'budget', 'video_resume'}:
        assert dispatches[0] == dispatches[1]
        record = store.list_generation_records()[0]
        assert record['operator_confirmed_paid'] is False
        assert record['commission_authorization']['source'] == 'commission_budget'
        assert len(store.read_bundle().assets) == 1
        assert store.read_bundle().assets[0].rights.status is RightsStatus.UNKNOWN
    if is_video:
        assert FakeVideo.waits == ['fixture-paid-video', 'fixture-paid-video']
        assert len(quote_reads) == 2  # first submit + second Need; query retry is not a new purchase


def test_missing_voice_timing_recovers_from_saved_audio_without_rebuying(material_integration_env, monkeypatch):
    import asyncio
    from copy import deepcopy
    from types import SimpleNamespace
    from easel.creation_delivery import advance_creation, next_operation
    from easel.materials.application import voice_delivery

    attempt = material_integration_env
    script = '假设清晨。窗边很安静。'
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
        'modality': 'voice', 'attempt_id': attempt['attempt_id'], 'plan_id': plan.plan_id,
        'need_id': need.need_id, 'need_sha256': hashlib.sha256(need.to_json().encode()).hexdigest(),
        'input_sha256': hashlib.sha256(script.encode()).hexdigest(),
        'asset_id': asset.asset_id, 'asset_sha256': asset.file.sha256, 'asset_path': path, 'asset_bytes': len(body),
        'voice_timing': voice_delivery.bind_voice_timing(script, asset, (), 'provider_timing_missing_or_invalid')}
    store.write_generation_record('gen-voice', generation)
    with creation.edit_creation(attempt['creation_id']) as work:
        work['origin'] = {'type': 'chat'}
        work['chat_workflow'] = {'proposal_status': 'READY_FOR_CONFIRMATION'}
    work = creation.confirm_chat_proposal(attempt['creation_id'], 'fixture', delivery_proposal=script,
                                          proposal_sha256=hashlib.sha256(script.encode()).hexdigest())
    report = {'engine': 'fixture-asr', 'words': [
        {'text': '假设', 'start_seconds': .15, 'end_seconds': .7, 'probability': .95},
        {'text': '清晨。', 'start_seconds': .7, 'end_seconds': 1.5, 'probability': .9},
        {'text': '窗边', 'start_seconds': 2., 'end_seconds': 3., 'probability': .96},
        {'text': '很安静。', 'start_seconds': 3., 'end_seconds': 4.8, 'probability': .99}]}
    recognized = voice_delivery.timing_from_recognition(script, asset, report)
    assert [(r['start_seconds'], r['end_seconds']) for r in recognized['cues']] == [(.15, 1.5), (2., 4.8)]
    for invalid in ('mismatch', 'truncated', 'overlap', 'confidence'):
        bad = deepcopy(report)
        if invalid == 'mismatch': bad['words'][0]['text'] = '真的'
        if invalid == 'truncated': bad['words'].pop()
        if invalid == 'overlap': bad['words'][1]['start_seconds'] = .2
        if invalid == 'confidence': bad['words'][0]['probability'] = .2
        with pytest.raises(ValueError):
            voice_delivery.timing_from_recognition(script, asset, bad)
    calls = []
    def recognize(file, language):
        calls.append(file)
        assert file.read_bytes() == body and language is None
        return deepcopy(report)
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
    assert len(calls) == 1 and len(writes) == 2
    assert next_operation(creation.get_creation(work['id']))[0] != 'recover_voice_timing'
    recovered = store.read_generation_record('gen-voice')
    assert recovered['provider_voice_timing'] == generation['voice_timing']
    assert recovered['voice_timing']['source'] == 'local_asr'
    assert store.read_bundle() == bundle and store.read_asset('voice').rights.status is RightsStatus.UNKNOWN
    # Project timing independently from admission: ASR does not grant Rights or
    # a semantic match. Production consumes it only after ordinary qualification.
    from easel.materials.application.voice_delivery import authoring_voice_timings
    qualified = SimpleNamespace(assets=(asset,), matches=(MaterialMatch(
        need_id='voice', asset_id='voice', rank=1, score=1, qualified=True),))
    projected = authoring_voice_timings(plan, qualified, store, script)
    assert projected['assets'][0]['source'] == 'local_asr'
    assert ''.join(c['display_text'] for c in projected['assets'][0]['cues']) == script
    recovered['voice_recognition']['audio_sha256'] = '0' * 64
    write_record(store, 'gen-voice', recovered)
    assert authoring_voice_timings(plan, qualified, store, script)['unavailable_need_ids'] == ['voice']
