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
    # Guard HTTP TestClient lifespans from dispatching current real commissions.
    # Only tests explicitly driving Delivery may execute a local fake boundary.
    from tests.test_creation_preparation import web as direct_web
    from web import app as package_web
    async def disabled_background_worker(stop, _execute):
        await stop.wait()
    monkeypatch.setattr(direct_web, 'serve_delivery', disabled_background_worker)
    monkeypatch.setattr(package_web, 'serve_delivery', disabled_background_worker)
    # Real New-Only Creation/Consent, not a manually entitled historical record.
    from tests.test_creation_preparation import _confirm_current_video_plan
    work = creation.create_creation(
        "一个需要素材层的短视频", profile="测试", creative_mode="clear_memo_video",
        route="hypit_video", origin={"type": "chat", "session_hash": hashlib.sha256(
            b"u2a-material-positive-test").hexdigest()},
    )
    work = _confirm_current_video_plan(work, turn_id="material-confirm")
    from easel.creation_preparation import _canonical_bytes, _sha256
    brief = {
        'schema': 'easel-production-brief@1', 'language': 'zh-CN',
        'duration_seconds': 15, 'aspect_ratio': '9:16', 'audio_mode': 'silent',
        'beats': [], 'text_overlays': [], 'visual_constraints': [],
        'material_sources': [], 'ai_generation_allowed': False,
        'publication_allowed': False,
    }
    brief_sha256 = _sha256(_canonical_bytes(brief))
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
                            "production_brief": brief,
                            "production_brief_sha256": brief_sha256,
                            "video_plan": work["delivery"]["video_plan"],
                            "confirmed_proposal_sha256": work["chat_workflow"]["proposal_sha256"]},
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
    attempt = service.update_film_attempt(
        attempt["attempt_id"], event="planning_contract_registered",
        planning_contract_version=3)
    from easel.creation_delivery import is_managed
    assert is_managed(creation.get_creation(work["id"]))
    assert attempt["planning_contract_version"] == 3
    return attempt



def test_u2a_material_fixture_is_authorized_newonly_v3_commission(material_integration_env):
    """All downstream Material tests begin with a real @4 consent and five pins."""
    from easel.creation_delivery import is_managed
    from easel.integrations.result_protocols import inherited, current
    attempt = material_integration_env
    work = creation.get_creation(attempt['creation_id'])
    assert is_managed(work)
    assert attempt['planning_contract_version'] == 3
    assert inherited(attempt) == current()
    assert work['delivery']['video_plan']['schema'] == 'easel-video-proposal@4'
    assert work['delivery']['authorization']['input_use']['schema'] == 'easel-input-use@3'
    _, manifest, _ = handoff.resolve_handoff(work['id'], attempt['handoff']['handoff_id'])
    assert manifest['production_request']['video_plan'] == work['delivery']['video_plan']



def test_u2a_material_v13_current_supply_and_rights(material_integration_env, tmp_path):
    """Real v3/vNext Planning to local Rights/Readiness, no paid external calls."""
    from tests.test_creation_preparation import _current_vnext_planning_executor
    from PIL import ImageDraw

    attempt = material_integration_env
    root = Path(attempt['workspace']['path'])
    _, manifest, _ = handoff.resolve_handoff(
        attempt['creation_id'], attempt['handoff']['handoff_id'])
    handoff_root = root / 'handoff'
    inputs = {key: json.loads((handoff_root / value['path']).read_text(encoding='utf-8'))
              for key, value in (('content_core', manifest['content']['content_core']),
                                 ('truth_packet', manifest['content']['truth_packet']),
                                 ('creator_context', manifest['creator_context']))}
    refs = {
        'content_core_sha256': manifest['content']['content_core']['hash'],
        'truth_packet_sha256': manifest['content']['truth_packet']['hash'],
        'creator_context_sha256': manifest['creator_context']['hash'],
        'production_brief_sha256': manifest['production_request']['production_brief_sha256'],
        'creative_mode_sha256': manifest['creative_mode']['hash']}
    planning = _current_vnext_planning_executor(attempt, {**inputs, 'context_refs': refs})
    assert planning['plan'].context_refs == refs
    # P0 B-only identity must survive the real frozen checkpoint boundary.
    from easel.integrations.planning_wire import B_IDENTITY_POLICY
    from easel.materials.store import AttemptMaterialStore
    checkpoint = AttemptMaterialStore(root).read_recovery_record('semantic-planning-vnext')
    assert checkpoint['b_identity_policy'] == B_IDENTITY_POLICY
    b_keys = [key for key in checkpoint['calls'] if key.startswith('B-')]
    assert b_keys and all(checkpoint['schema_bindings'][key]['b_identity_policy'] == B_IDENTITY_POLICY
                          for key in b_keys)
    assert all(set(json.loads(checkpoint['calls'][key]['reply'])) == {'answers'} for key in b_keys)


    local_root = tmp_path / 'self-created-media'
    local_root.mkdir()
    source = local_root / 'two-white-papers.jpg'
    image = Image.new('RGB', (720, 1280), color=(95, 76, 57))
    draw = ImageDraw.Draw(image)
    draw.rectangle((72, 310, 316, 765), fill=(248, 248, 245))
    draw.rectangle((380, 330, 660, 790), fill=(249, 248, 245))
    image.save(source)
    source.with_name(source.name + '.rights.json').write_text(json.dumps({
        'schema': 'easel-local-rights@1',
        'asset_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'rights': {'status': 'KNOWN', 'license_name': 'Self-created fixture',
                   'evidence': [{'kind': 'asset_license',
                                 'reference': 'https://rights.example/u2a-fixture',
                                 'summary': 'Offline synthetic image, no external source.'}]}},
        ensure_ascii=False), encoding='utf-8')
    supplied = MaterialProductOrchestrator().run_with_planning(
        attempt, (local_root,), planning)
    assert supplied['planning']['manifest']['schema'] == 'easel-material-planning@3'
    assert supplied['planning']['truth_ledger']['status'] == 'PASSED'
    assert supplied['status'] == 'MATERIAL_NOT_READY'
    asset = next(a for a in supplied['supply'].bundle.assets
                 if a.rights.status.value == 'KNOWN')
    reviewed = MaterialProductOrchestrator().review_material_match(
        attempt['attempt_id'], asset_id=asset.asset_id,
        expected_sha256=asset.file.sha256,
        need_id=supplied['planning']['plan'].needs[0].need_id,
        observed_content='桌面上有两张清晰完整的白色纸张，背景为棕色桌面，没有文字。',
        logo_present=None, visible_text_present=None, confirm_review=True)
    assert reviewed['material_status'] == 'MATERIAL_READY'
    current_attempt = service.get_film_attempt(attempt['attempt_id'])
    plan, _, readiness = MaterialGateIntegration().assert_ready(current_attempt)
    assert plan == supplied['planning']['plan'] and readiness.status.value == 'READY'
    assert current_attempt['build']['operation'] is None
    resumed = MaterialProductOrchestrator().run_with_planning(
        current_attempt, (local_root,), PlanningIntegration().load(current_attempt))
    assert resumed['status'] == 'MATERIAL_READY'
    store = AttemptMaterialStore(root)
    original = store.resolve_asset_locator(asset.file.path)
    original.write_bytes(original.read_bytes() + b'changed-source')
    with pytest.raises(MaterialIntegrationError):
        MaterialGateIntegration().assert_ready(service.get_film_attempt(attempt['attempt_id']))



def test_u2a_historical_manual_plan_does_not_launder_current_commission(
        material_integration_env):
    """A valid @4 Creation cannot authorize an unpinned old file Writer."""
    attempt = material_integration_env
    before = creation._creation_path(attempt['creation_id']).read_bytes()
    root = Path(attempt['workspace']['path'])
    assert not (root / 'planning/manifest.json').exists()
    with pytest.raises(MaterialIntegrationError, match='旧 Planning/非当前委托只读'):
        _legacy_manual_planning(attempt)
    assert creation._creation_path(attempt['creation_id']).read_bytes() == before
    assert not (root / 'planning/manifest.json').exists()
    assert service.get_film_attempt(attempt['attempt_id'])['build']['operation'] is None


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


def _legacy_manual_planning(attempt):
    """Only used to prove that a hand-written old Plan is not admitted."""
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


def _planning(attempt):
    """Current official vNext Owner, with only model responses fixed offline.

    No manually seeded Need, MaterialPlan, review ledger, Result Pin or READY.
    """
    from tests.test_creation_preparation import _current_vnext_planning_executor
    from easel.integrations.hypit import service
    root = Path(attempt["workspace"]["path"])
    if (root / "planning/manifest.json").exists():
        loaded = PlanningIntegration().load(service.get_film_attempt(attempt["attempt_id"]))
        attempt.update(loaded["attempt"])
        return {**loaded, "status": loaded["manifest"]["status"]}
    _, manifest, _ = handoff.resolve_handoff(
        attempt["creation_id"], attempt["handoff"]["handoff_id"])
    source_root = root / "handoff"
    documents = {key: json.loads((source_root / ref["path"]).read_text(encoding="utf-8"))
                 for key, ref in (
                     ("content_core", manifest["content"]["content_core"]),
                     ("truth_packet", manifest["content"]["truth_packet"]),
                     ("creator_context", manifest["creator_context"]))}
    refs = {
        "content_core_sha256": manifest["content"]["content_core"]["hash"],
        "truth_packet_sha256": manifest["content"]["truth_packet"]["hash"],
        "creator_context_sha256": manifest["creator_context"]["hash"],
        "production_brief_sha256": manifest["production_request"]["production_brief_sha256"],
        "creative_mode_sha256": manifest["creative_mode"]["hash"],
    }
    planned = _current_vnext_planning_executor(attempt, {**documents, "context_refs": refs})
    persisted = PlanningIntegration().persist(
        attempt, planned["plan"], treatment=planned["treatment"],
        script=planned["script"], scenes=planned["scenes"],
        script_assessment=planned.get("script_assessment"),
        voice_identity_assessment=planned.get("voice_identity_assessment"))
    attempt.update(persisted["attempt"])
    cold = PlanningIntegration().load(service.get_film_attempt(attempt["attempt_id"]))
    assert cold["plan"] == persisted["plan"]  # No test-created READY checkpoint.
    return {**cold, "status": persisted["status"]}




def _current_budgeted_visual_fixture(material_integration_env, monkeypatch, ai_allowed, *, max_cost=.03, allowed=('image',), two_scenes=False):
    """Current @4/Consent@3/five pins; no legacy manual Plan or paid Provider."""
    from dataclasses import replace
    from easel.runtime_config import EaselRuntimeConfig, MiniMaxRuntimeConfig
    from easel.integrations import material_generation as paid
    from easel.creation_preparation import _canonical_bytes, _sha256
    from easel.integrations import result_protocols as versions
    from tests.test_creation_preparation import VIDEO_PROPOSAL

    baseline = EaselRuntimeConfig.load()
    settings = MiniMaxRuntimeConfig(api_key="offline-fixture-key")
    empty_stock = Path(material_integration_env["workspace"]["path"]) / "empty-image-stock"
    empty_stock.mkdir(exist_ok=True)
    frozen_config = replace(baseline, minimax=settings,
        material=replace(baseline.material, local_roots=(str(empty_stock),)))
    monkeypatch.setattr(EaselRuntimeConfig, "load",
                        classmethod(lambda cls, **kwargs: frozen_config))
    work = creation.create_creation(
        "有明确预算和冻结许可的视觉素材测试", profile=None,
        creative_mode="clear_memo_video", route="hypit_video",
        origin={"type": "chat", "session_hash": hashlib.sha256(
            f"u2a-paid-brief-{ai_allowed}".encode()).hexdigest()})
    turn = "explicit-budget-approval"
    # The frozen author-facing proposal records the content permission in
    # words; a positive Brief is not silently inferred from a cost ceiling.
    permission = ("明确允许真实检索缺口以获批预算生成静态补位图像。"
                  if ai_allowed else "明确禁止生成图像，必须使用已有授权来源。")
    proposal = VIDEO_PROPOSAL.replace(
        "从日常选择的变化切入，不把结论当成普遍规律。不露脸。",
        "从日常选择的变化切入，不把结论当成普遍规律。不露脸。\n" + permission)
    if two_scenes:
        proposal = proposal.replace(
            '0–15 秒：桌面两张白纸，呈现后期叠加的屏幕文案「先看问题，再做决定。」。',
            '0–7 秒：桌面两张白纸，呈现后期叠加的屏幕文案「先看问题，再做决定。」。'
            '\n7–15 秒：桌面一本蓝色封面笔记本。')
    creation.begin_video_proposal(work["id"], turn)
    draft = creation.save_video_proposal(work["id"], turn, proposal)
    plan = draft["chat_workflow"]["video_plan"]
    assert plan["schema"] == "easel-video-proposal@4"
    transcript = json.dumps([{"role": "assistant", "content": proposal}],
                            ensure_ascii=False, separators=(",", ":"))
    consent = creation.input_use_preview(plan=plan)
    scope = paid.generation_budget_preview()
    assert scope["available"] and "offline-fixture-key" not in json.dumps(scope)
    grant = {"maxCostCny": max_cost, "scopeSha256": scope["scope_sha256"],
             "allowedModalities": list(allowed)}
    unconfirmed = creation._creation_path(work["id"]).read_bytes()
    with pytest.raises(creation.CreationError, match="素材服务或音色配置已变化"):
        creation.confirm_chat_proposal(
            work["id"], turn, delivery_proposal=transcript,
            proposal_sha256=hashlib.sha256(transcript.encode()).hexdigest(),
            video_plan_sha256=plan["sha256"], production_specs=plan["specs"],
            input_use_statement_sha256=consent["statement_sha256"],
            generation_budget={**grant, "scopeSha256": "0"*64})
    assert creation._creation_path(work["id"]).read_bytes() == unconfirmed
    work = creation.confirm_chat_proposal(
        work["id"], turn, delivery_proposal=transcript,
        proposal_sha256=hashlib.sha256(transcript.encode()).hexdigest(),
        video_plan_sha256=plan["sha256"], production_specs=plan["specs"],
        input_use_statement_sha256=consent["statement_sha256"],
        generation_budget=grant)
    authorization = work["delivery"]["authorization"]
    assert authorization["input_use"]["schema"] == "easel-input-use@3"
    assert authorization["material_generation"]["allowed_modalities"] == sorted(allowed)
    assert authorization["material_generation"]["max_amount"] == str(max_cost)
    assert paid.authorized_generation_modalities(authorization["material_generation"]) == set(allowed)
    with pytest.raises(creation.CreationError, match="不能通过重放|扩大素材预算"):
        creation.confirm_chat_proposal(
            work["id"], "increase-budget",
            delivery_proposal=transcript,
            proposal_sha256=hashlib.sha256(transcript.encode()).hexdigest(),
            generation_budget={**grant, "allowedModalities": ["image", "video"]})

    # Freeze a genuine Preparation snapshot, not a hand-written Handoff. The
    # paid fallback must be able to verify the original content permission.
    from easel import creation_preparation as preparation
    from tests.test_creation_preparation import write_drafts, _current_vnext_planning_executor
    claim = preparation.claim_chat_preparation(work["id"], "paid-fixture-session", turn)
    paths = preparation.preparation_paths(work["id"], claim["operation_key"])
    write_drafts(work, paths["draft"])
    brief_path = paths["draft"] / "production-brief.json"
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["ai_generation_allowed"] = ai_allowed
    brief_path.write_text(json.dumps(brief, ensure_ascii=False), encoding="utf-8")
    prepared = preparation.prepare_creation_for_hypit(
        work["id"], runtime_profile=None, planning_executor=_current_vnext_planning_executor)
    attempt = service.get_film_attempt(prepared["attempt_id"])
    current = PlanningIntegration().load(attempt)
    assert creation.get_creation(work["id"])["preparation"]["snapshot_hashes"]
    brief_hash = creation.get_creation(work["id"])["preparation"]["snapshot_hashes"]["production_brief"]
    assert current["truth_ledger"]["status"] == "PASSED"
    assert current["plan"].context_refs["production_brief_sha256"] == brief_hash
    visual = [n for n in current["plan"].needs if n.media_type is MediaType.IMAGE]
    assert len(visual) == (2 if two_scenes else 1)
    assert all(n.constraints.get("allow_generation") is ai_allowed for n in visual)
    assert work["delivery"]["video_plan"]["specs"]["audio_mode"] == "silent"
    assert service.get_film_attempt(attempt["attempt_id"])["build"]["operation"] is None
    assert not creation.get_creation(work["id"])["delivery"].get("material_generations")
    return work, attempt, current, settings


@pytest.mark.parametrize("ai_allowed", [False, True], ids=["brief-forbids", "brief-allows"])
def test_u2a_current_budgeted_visual_commission_binds_frozen_brief(
        material_integration_env, monkeypatch, ai_allowed):
    work, attempt, current, settings = _current_budgeted_visual_fixture(
        material_integration_env, monkeypatch, ai_allowed)
    assert current["plan"].needs[0].constraints["allow_generation"] is ai_allowed
    if not ai_allowed:
        from easel.materials.application.routing import MaterialSourceRouter
        from easel.materials.domain import ContinuityRef
        # A character continuity hint is not stronger than the frozen ban.
        prohibited = current["plan"].needs[0].model_copy(update={
            "continuity_refs": (ContinuityRef(kind="character", ref="frozen-id"),)})
        assert not MaterialSourceRouter._generation_eligible(prohibited)
    assert service.get_film_attempt(attempt["attempt_id"])["build"]["operation"] is None


@pytest.mark.parametrize('risk', [
    'unfinished_observation', 'changed_bundle_revision',
    'material_call_space_exhausted', 'no_generation_grant',
])
def test_u2a_current_image_fallback_fail_closed_before_any_paid_request(
        material_integration_env, monkeypatch, risk):
    """#20 retained V1 risks only: real @4/vNext/Brief + zero-stock observation.

    No legacy Planning.persist/Delivery forgery; only post-frozen local copies
    are altered to exercise stale facts / exhausted call-room / absent grant.
    Image preference, dynamic video and source-identity policy have dedicated
    existing tests; they are not reconstructed here as illegal Plans.
    """
    from copy import deepcopy
    from easel.integrations import material_generation as paid
    from easel.materials.providers import minimax_pricing
    from easel.creation_delivery import is_managed
    work, attempt, planning, _ = _current_budgeted_visual_fixture(
        material_integration_env, monkeypatch, True)
    no_stock=lambda *_: pytest.fail('no local pixels exist; do not query model')
    MaterialProductOrchestrator().observe_visual_materials(
        attempt['attempt_id'],executor=no_stock)
    work=creation.get_creation(work['id'])
    attempt=service.get_film_attempt(attempt['attempt_id'])
    plan=planning['plan']
    need=next(n for n in plan.needs if n.media_type is MediaType.IMAGE)
    assert is_managed(work)
    eligible=paid.image_fallback_decision(work,attempt,plan,need)
    assert eligible['eligible'], eligible
    assert paid.pending_generated_need(work,attempt,plan)[0].need_id==need.need_id
    immutable=(
        creation._creation_path(work['id']).read_bytes(),
        service.get_film_attempt(attempt['attempt_id']),
        AttemptMaterialStore(attempt['workspace']['path']).read_bundle())
    changed_work, changed_attempt=deepcopy(work),deepcopy(attempt)
    if risk=='unfinished_observation':
        changed_attempt['material_observation']['status']='PENDING'
    elif risk=='changed_bundle_revision':
        changed_attempt['material_observation']['bundle_revision']='0'*64
    elif risk=='material_call_space_exhausted':
        # Pure, ephemeral NextOperation budget projection; do not mutate the
        # stored commission or grant new currency authority to the fixture.
        changed_work['delivery'].setdefault('call_budgets', {})['material'] = {
            'used': 8, 'limit': 9}
    else:
        changed_work['delivery']['authorization']['material_generation']=None
    if risk=='no_generation_grant':
        # Material content gap and a monetary/authorization grant are distinct.
        assert paid.image_fallback_decision(changed_work,changed_attempt,plan,need)['eligible']
    else:
        decision=paid.image_fallback_decision(changed_work,changed_attempt,plan,need)
        assert not decision['eligible'],(risk,decision)
        assert decision['reason']
    monkeypatch.setattr(minimax_pricing,'read_public_contract',
        lambda *_: pytest.fail('no quote/Provider call permitted for invalid inputs'))
    assert paid.pending_generated_need(changed_work,changed_attempt,plan) is None
    assert creation._creation_path(work['id']).read_bytes()==immutable[0]
    assert service.get_film_attempt(attempt['attempt_id'])==immutable[1]
    assert AttemptMaterialStore(attempt['workspace']['path']).read_bundle()==immutable[2]
    assert not creation.get_creation(work['id'])['delivery'].get('material_generations')
    assert not AttemptMaterialStore(attempt['workspace']['path']).list_generation_records()
    assert attempt['build']['operation'] is None


@pytest.mark.parametrize('usable_second', [True, False], ids=['second-source-usable', 'all-sources-rejected'])
@pytest.mark.parametrize('fault_after_first', [False, True], ids=['ordinary-owner', 'cold-resume-after-first-capture'])
def test_u2a_current_visual_candidate_owner_stops_at_usable_or_evidence_exhaustion(
        material_integration_env, monkeypatch, usable_second, fault_after_first):
    """#13 current safety: search results are candidates, never matches by caption.

    Three real locally encoded images, an @4/vNext frozen Need and normal
    Material Gate. The offline *pixel verdict only* is simulated. The Owner
    preserves each bounded result and stops once a qualified source exists,
    without looking at unrelated stock or replaying prior model decisions.
    """
    from io import BytesIO
    from PIL import ImageDraw
    from easel.creation_delivery import set_material_endpoint
    from tests.material_delta_fixture import observed_result

    work, attempt, planning, _ = _current_budgeted_visual_fixture(
        material_integration_env, monkeypatch, False)
    set_material_endpoint(work['id'])
    plan=planning['plan']
    need=next(n for n in plan.needs if n.media_type is MediaType.IMAGE)
    store=AttemptMaterialStore(attempt['workspace']['path'])
    before=store.read_bundle()
    assets=[]
    for idx in range(3):
        pic=Image.new('RGB',(720,1280),(55 + idx*28,76,101))
        draw=ImageDraw.Draw(pic)
        if idx==1:
            draw.rectangle((94,230,305,760),fill=(245,245,242))
            draw.rectangle((389,245,633,792),fill=(250,250,247))
        else:
            draw.ellipse((74,230,620,870),fill=(212,44 + idx*30,46))
        buf=BytesIO();pic.save(buf,format='PNG')
        payload=buf.getvalue()
        aid=f'candidate-vnext-{idx}'
        locator=store.write_asset_bytes(aid,'original.png',payload)
        asset=MaterialAsset(
            asset_id=aid,media_type=MediaType.IMAGE,
            file=FileInfo(path=locator,sha256=hashlib.sha256(payload).hexdigest(),
                size=len(payload),mime='image/png'),
            source=CandidateSource(kind='local',provider='offline-fixture',provider_asset_id=aid),
            rights=RightsInfo(status=RightsStatus.KNOWN,
                license_name='Local original pixels for isolated software tests',
                evidence=(RightsEvidence(kind='asset_license',
                    reference=f'fixture://local-pixels/{aid}'),)),
            technical=TechnicalInfo(status=TechnicalStatus.PASSED,
                width=720,height=1280,mime='image/png'),
            semantic=SemanticInfo(caption=need.intent.description))
        store.write_asset(asset)
        assets.append(asset)
    now=datetime.now(timezone.utc)
    run=SupplyRun(supply_run_id='current-candidates-'+attempt['attempt_id'][-17:],
        plan_id=plan.plan_id,parent_run_id=before.supply_run_id,
        started_at=now,finished_at=now,result_bundle_id=before.bundle_id)
    bundle=MaterialBundleAssembler().assemble(
        plan,run,tuple(assets),(),bundle_id=before.bundle_id)
    from easel.integrations import material_results
    readiness,gaps=material_results.readiness_calculator(attempt,store).calculate(plan,bundle)
    attempt=MaterialGateIntegration().record(attempt,plan,bundle,run,readiness,gaps)['attempt']
    assert attempt['material_gate']['status']=='MATERIAL_NOT_READY'
    asked=[]
    source_bytes={a.asset_id: store.resolve_asset_locator(a.file.path).read_bytes() for a in assets}
    source_rights={a.asset_id: a.rights for a in assets}
    original_consent=creation.get_creation(work['id'])['delivery']['authorization']
    def pixels(current,manifest,attachments):
        key=manifest['asset_id']
        assert key in {a.asset_id for a in assets}
        if fault_after_first and key==assets[0].asset_id and key in asked:
            pytest.fail('cold replay may not call the model again for saved first receipt')
        asked.append(key)
        return observed_result(current,manifest,attachments,
            outcome='suitable' if usable_second and key==assets[1].asset_id else 'unsuitable',
            description='two white papers' if key==assets[1].asset_id else 'one large red shape')
    owner=MaterialProductOrchestrator()
    first_receipt_bytes=None
    if fault_after_first:
        # The receipt is durably stored by the real delta producer before
        # the Owner writes the first scoped inference into the Asset. Interrupt
        # *after* that Asset write, before outcomes and visual-done journal.
        write_asset=AttemptMaterialStore.write_asset
        crashed=[]
        def write_then_interrupt(self, value):
            result=write_asset(self,value)
            if (value.asset_id==assets[0].asset_id and value.semantic.inferences
                    and not crashed):
                crashed.append(value.asset_id)
                raise OSError('offline crash after first persisted pixel evidence')
            return result
        with monkeypatch.context() as fault:
            fault.setattr(AttemptMaterialStore,'write_asset',write_then_interrupt)
            with pytest.raises(OSError,match='after first persisted pixel evidence'):
                owner.observe_visual_materials(attempt['attempt_id'],executor=pixels)
        assert crashed==[assets[0].asset_id]
        assert asked==[assets[0].asset_id]
        assert store.read_asset(assets[0].asset_id).semantic.inferences
        from easel.materials.application.visual_observation import prepare_observation
        first_manifest,_=prepare_observation(
            need,assets[0],store.resolve_asset_locator(assets[0].file.path))
        first_receipt=store.materials_root / 'observations' / (first_manifest['input_sha256']+'.json')
        assert first_receipt.is_file()
        first_receipt_bytes=first_receipt.read_bytes()
        assert first_receipt_bytes
        # The cold Owner must reuse the same saved input/result and expense
        # ledger; never rerun the original model or rewrite the asset bytes.
        assert not creation.get_creation(work['id'])['delivery'].get('material_generations')
        owner=MaterialProductOrchestrator()
    last=None
    for _ in range(5):
        last=owner.observe_visual_materials(attempt['attempt_id'],executor=pixels)
        if last['material_status']=='MATERIAL_READY':
            break
        progress=last['attempt']['material_observation']['candidate_progress'][need.need_id]
        if not usable_second and len(asked)<len(assets):
            assert progress['next_candidates'], (
                'a distinct, unobserved candidate must not disappear merely '
                'because the previous candidate had a hard content mismatch',progress)
        if not progress['next_candidates']:
            break
    assert last is not None
    assert asked[:2]==[a.asset_id for a in assets[:2]],asked
    assert len(asked)==len(set(asked)) and len(asked)<=3,asked
    assert last['material_status']==('MATERIAL_READY' if usable_second else 'MATERIAL_NOT_READY')
    if usable_second:
        assert assets[2].asset_id not in asked
    completed=list(asked)
    latest=owner.observe_visual_materials(attempt['attempt_id'],
        executor=lambda *_: pytest.fail('no budgeted candidate needs fresh pixel review'))
    assert latest['material_status']==last['material_status']
    assert asked==completed
    if fault_after_first:
        assert first_receipt.read_bytes()==first_receipt_bytes
    assert {a.asset_id for a in store.read_bundle().assets}=={a.asset_id for a in assets}
    for source in assets:
        recorded=store.read_asset(source.asset_id)
        assert recorded.file==source.file
        assert recorded.rights==source_rights[source.asset_id]
        assert store.resolve_asset_locator(recorded.file.path).read_bytes()==source_bytes[source.asset_id]
        assert hashlib.sha256(source_bytes[source.asset_id]).hexdigest()==source.file.sha256
    assert creation.get_creation(work['id'])['delivery']['authorization']==original_consent
    assert not creation.get_creation(work['id'])['delivery'].get('material_generations')
    assert not store.list_generation_records()
    assert PlanningIntegration().load(service.get_film_attempt(attempt['attempt_id']))['plan']==plan
    assert service.get_film_attempt(attempt['attempt_id'])['build']['operation'] is None
    assert not service.get_film_attempt(attempt['attempt_id']).get('production_authoring')


def test_u2a_current_image_gap_requires_real_search_and_observation(
        material_integration_env, monkeypatch):
    from easel.integrations import material_generation as paid
    work, attempt, planning, _ = _current_budgeted_visual_fixture(
        material_integration_env, monkeypatch, True)
    need = planning["plan"].needs[0]
    work = creation.get_creation(work["id"])
    first = paid.image_fallback_decision(work, attempt, planning["plan"], need)
    assert first["eligible"] is False and "素材观察" in first["reason"]
    def no_pixel_observation(*_):
        pytest.fail("No stock candidate exists; no paid visual observation")
    MaterialProductOrchestrator().observe_visual_materials(
        attempt["attempt_id"], executor=no_pixel_observation)
    attempt = service.get_film_attempt(attempt["attempt_id"])
    result = paid.image_fallback_decision(
        creation.get_creation(work["id"]), attempt, planning["plan"], need)
    assert result["eligible"] is True, result
    selected = paid.pending_generated_need(
        creation.get_creation(work["id"]), attempt, planning["plan"])
    assert selected is not None and selected[0].need_id == need.need_id
    assert not creation.get_creation(work["id"])["delivery"].get("material_generations")


@pytest.mark.parametrize("outcome", [
    "budget_exceeded", "submission_unknown", "scope_changed", "received_no_rebuy",
])
def test_u2a_current_visual_commission_reservation_unknown_and_no_rebuy(
        material_integration_env, monkeypatch, outcome):
    """Delivery/Planning/Gate/quote are real; only price URLs and paid adapter are fixed."""
    from dataclasses import replace
    from io import BytesIO
    from easel.creation_delivery import active_delivery
    from easel.integrations import material_generation as commissioned
    from easel.materials.providers import minimax_pricing
    from easel.materials import providers
    from easel.materials.providers.minimax_image import MiniMaxImageResult
    from easel.runtime_config import EaselRuntimeConfig, MiniMaxRuntimeConfig
    from tests.test_minimax_image_speech_generation import MINIMAX_TERMS_FIXTURE

    max_cost = .01 if outcome == "budget_exceeded" else .03
    work, attempt, planning, settings = _current_budgeted_visual_fixture(
        material_integration_env, monkeypatch, True, max_cost=max_cost)
    def no_stock_pixels(*_):
        pytest.fail("No stock found, therefore no real visual LLM may be called")
    MaterialProductOrchestrator().observe_visual_materials(
        attempt["attempt_id"], executor=no_stock_pixels)
    attempt = service.get_film_attempt(attempt["attempt_id"])
    work = creation.get_creation(work["id"])
    need = planning["plan"].needs[0]
    assert commissioned.image_fallback_decision(
        work, attempt, planning["plan"], need)["eligible"] is True
    _, request_id = commissioned.pending_generated_need(
        work, attempt, planning["plan"])

    terms_reads = []
    def offline_public_quote(url):
        terms_reads.append(url)
        if url == minimax_pricing.TERMS_URL:
            return MINIMAX_TERMS_FIXTURE
        return ("## 图像\n单价：元/张\n| image-01 | 图片 | 0.025 |\n"
                "## 视频\n**视频生成-输出价格**\n| MiniMax-H3-Max | 480P | 按秒计费 | 0.33 元/秒 |\n")
    monkeypatch.setattr(minimax_pricing, "read_public_contract", offline_public_quote)

    image_data = BytesIO()
    Image.new("RGB", (64, 64), "teal").save(image_data, format="PNG")
    model_calls = []
    class FixedImageProvider:
        model = "image-01"
        def __init__(self, *args, **kwargs):
            pass
        def generate(self, prompt, **kwargs):
            entry = creation.get_creation(work["id"])["delivery"]["material_generations"][request_id]
            assert entry["status"] == "reserved"
            assert entry["quote"]["upper_estimate"] == "0.025000"
            model_calls.append(prompt)
            if outcome == "submission_unknown":
                raise TimeoutError("fixture response lost after possible paid submit")
            return MiniMaxImageResult(self.model, image_data.getvalue())
    monkeypatch.setattr(providers, "MiniMaxImageAdapter", FixedImageProvider)

    if outcome == "scope_changed":
        baseline = EaselRuntimeConfig.load()
        monkeypatch.setattr(EaselRuntimeConfig, "load", classmethod(
            lambda cls, **kwargs: replace(baseline,
                minimax=MiniMaxRuntimeConfig(api_key="different-offline-fixture-key"))))
    with pytest.raises(creation.CreationError, match="后台交付者"):
        commissioned.generate_for_commission(attempt["attempt_id"])
    token = active_delivery.set(work["id"])
    try:
        if outcome == "scope_changed":
            with pytest.raises(commissioned.GenerationQuoteUnavailable, match="偏离"):
                commissioned.generate_for_commission(attempt["attempt_id"])
        else:
            commissioned.generate_for_commission(attempt["attempt_id"])
            commissioned.generate_for_commission(attempt["attempt_id"])
    finally:
        active_delivery.reset(token)

    record = creation.get_creation(work["id"])["delivery"].get("material_generations", {})
    if outcome == "scope_changed":
        assert not record and not model_calls and not terms_reads
    elif outcome == "budget_exceeded":
        assert list(record.values())[0]["status"] == "budget_exceeded"
        assert not model_calls and len(terms_reads) >= 1
    elif outcome == "submission_unknown":
        assert len(model_calls) == 1
        assert list(record.values())[0]["status"] == "uncertain"
        assert commissioned.pending_generated_need(
            creation.get_creation(work["id"]),
            service.get_film_attempt(attempt["attempt_id"]), planning["plan"]) is None
    else:
        assert len(model_calls) == 1
        assert list(record.values())[0]["status"] == "complete"
        stored = AttemptMaterialStore(attempt["workspace"]["path"]).list_generation_records()
        assert len(stored) == 1 and stored[0]["status"] == "COMPLETE"
    assert service.get_film_attempt(attempt["attempt_id"])["build"]["operation"] is None



@pytest.mark.parametrize('kind', ['reserved_restart', 'terms_unavailable_then_readable'])
def test_u2a_current_image_unsubmitted_reservation_reuses_request_and_terms(
        material_integration_env, monkeypatch, kind):
    """#15 No charge on quote read failure or crash BEFORE Provider submit."""
    from easel.integrations import material_generation as paid
    from easel.creation_delivery import active_delivery
    from easel.materials.providers import minimax_pricing
    from easel.materials import providers
    from easel.materials.providers.minimax_image import MiniMaxImageResult
    from tests.test_minimax_image_speech_generation import MINIMAX_TERMS_FIXTURE
    from io import BytesIO
    work, attempt, planning, settings = _current_budgeted_visual_fixture(
        material_integration_env, monkeypatch, True)
    def no_stock(*_): pytest.fail('no fixture visual stock to inspect')
    MaterialProductOrchestrator().observe_visual_materials(
        attempt['attempt_id'], executor=no_stock)
    attempt = service.get_film_attempt(attempt['attempt_id'])
    need, request = paid.pending_generated_need(
        creation.get_creation(work['id']), attempt, planning['plan'])
    reads = []
    def fixed_quote(url):
        reads.append(url)
        if url == minimax_pricing.TERMS_URL:
            if kind == 'terms_unavailable_then_readable' and reads.count(url) == 1:
                raise minimax_pricing.GenerationQuoteReadFailed('offline agreement page unavailable')
            return MINIMAX_TERMS_FIXTURE
        return ('## 图像\n单价：元/张\n| image-01 | 图片 | 0.025 |\n'
                '## 视频\n**视频生成-输出价格**\n'
                '| MiniMax-H3-Max | 480P | 按秒计费 | 0.33 元/秒 |')
    monkeypatch.setattr(minimax_pricing,'read_public_contract',fixed_quote)
    png = BytesIO()
    Image.new('RGB',(64,64),'teal').save(png,format='PNG')
    charged_calls = []
    class OfflineImage:
        def __init__(self, key, **kwargs):
            assert key == 'offline-fixture-key'
            self.model=kwargs['model']
        def generate(self, prompt, *, aspect_ratio):
            assert aspect_ratio == (need.modality_spec.aspect_ratio or '16:9')
            charged_calls.append(prompt)
            return MiniMaxImageResult(self.model,png.getvalue())
    monkeypatch.setattr(providers,'MiniMaxImageAdapter',OfflineImage)
    original_dispatch = MaterialProductOrchestrator.generate_minimax_asset
    aborted = []
    if kind == 'reserved_restart':
        def before_submit_restart(self, *args, **kwargs):
            if not aborted:
                aborted.append(kwargs['request_id'])
                assert kwargs['request_id']==request
                ledger=creation.get_creation(work['id'])['delivery']['material_generations']
                assert ledger[request]['status']=='reserved'
                raise OSError('offline crash before provider submit')
            return original_dispatch(self, *args, **kwargs)
        monkeypatch.setattr(MaterialProductOrchestrator,'generate_minimax_asset',before_submit_restart)
    token=active_delivery.set(work['id'])
    try:
        if kind == 'reserved_restart':
            from easel.materials.store import GenerationRecordNotFound
            # The Owner surfaces the missing GenerationRecord after the
            # pre-submit crash; it may safely retry the same reserved request.
            with pytest.raises((OSError, GenerationRecordNotFound)):
                paid.generate_for_commission(attempt['attempt_id'])
            receipt=creation.get_creation(work['id'])['delivery']['material_generations'][request]
            assert receipt['status']=='reserved'
        else:
            with pytest.raises(minimax_pricing.GenerationQuoteReadFailed):
                paid.generate_for_commission(attempt['attempt_id'])
            assert not creation.get_creation(work['id'])['delivery'].get('material_generations')
        assert not AttemptMaterialStore(attempt['workspace']['path']).list_generation_records()
        assert not charged_calls
        paid.generate_for_commission(attempt['attempt_id'])
        paid.generate_for_commission(attempt['attempt_id'])
    finally:
        active_delivery.reset(token)
    ledger=creation.get_creation(work['id'])['delivery']['material_generations']
    assert set(ledger)=={request} and ledger[request]['status']=='complete'
    assert len(charged_calls)==1
    assert len(aborted)==(1 if kind=='reserved_restart' else 0)
    assert reads.count(minimax_pricing.TERMS_URL)==2
    retained=AttemptMaterialStore(attempt['workspace']['path']).list_generation_records()
    assert len(retained)==1 and retained[0]['status']=='COMPLETE'
    assert retained[0]['need_id']==need.need_id
    assert service.get_film_attempt(attempt['attempt_id'])['build']['operation'] is None


@pytest.mark.parametrize('disabled', ['image', 'video', 'music'])
def test_u2a_current_frozen_modality_not_paid_without_matching_budget(
        material_integration_env, monkeypatch, disabled):
    """#15 Frozen Need permission and separate modality budget must both agree."""
    from easel.integrations import material_generation as paid
    from easel.creation_delivery import active_delivery
    from easel.materials.providers import minimax_pricing
    if disabled == 'image':
        work, attempt, planning, _ = _current_budgeted_visual_fixture(
            material_integration_env, monkeypatch, True, allowed=('video',))
        need = planning['plan'].needs[0]
        assert need.media_type is MediaType.IMAGE
    elif disabled == 'video':
        work, attempt, planning, _ = _u2a_current_video_budgeted_fixture(
            material_integration_env, monkeypatch, allowed=('image',))
        need = planning['plan'].needs[0]
        assert need.media_type is MediaType.VIDEO
    else:
        work, attempt, planning, need = _u2a_current_music_attempt(
            material_integration_env, 15)
        assert need.modality_spec.kind == 'bgm'
    events = []
    monkeypatch.setattr(minimax_pricing, 'read_public_contract',
                        lambda *_: events.append('quote') or pytest.fail('unauthorized quote'))
    assert paid.pending_generated_need(
        creation.get_creation(work['id']), attempt, planning['plan']) is None
    token = active_delivery.set(work['id'])
    try:
        paid.generate_for_commission(attempt['attempt_id'])
    finally:
        active_delivery.reset(token)
    assert not events
    assert not creation.get_creation(work['id'])['delivery'].get('material_generations')
    assert not AttemptMaterialStore(attempt['workspace']['path']).list_generation_records()
    assert service.get_film_attempt(attempt['attempt_id'])['build']['operation'] is None


def test_u2a_current_voice_preflight_requires_local_asr_before_paid_submit(
        material_integration_env, monkeypatch):
    from easel.integrations import material_generation as paid
    from easel.creation_delivery import active_delivery
    from easel.materials.application import voice_delivery
    from easel.materials.providers import minimax_pricing
    work, attempt, planning, need, settings = _u2a_current_voice_attempt(
        material_integration_env, monkeypatch)
    calls = []
    def no_local_model():
        calls.append('local-asr')
        raise ValueError('本地语音识别模型未就绪；原委托仍可核对')
    monkeypatch.setattr(voice_delivery, 'require_local_voice_model', no_local_model)
    monkeypatch.setattr(minimax_pricing,'read_public_contract',
                        lambda *_: pytest.fail('do not quote a voice that cannot be checked'))
    token=active_delivery.set(work['id'])
    try:
        with pytest.raises(ValueError, match='本地语音识别模型未就绪'):
            paid.generate_for_commission(attempt['attempt_id'])
    finally:
        active_delivery.reset(token)
    assert calls == ['local-asr']
    assert not creation.get_creation(work['id'])['delivery'].get('material_generations')
    assert not AttemptMaterialStore(attempt['workspace']['path']).list_generation_records()
    assert service.get_film_attempt(attempt['attempt_id'])['build']['operation'] is None


def test_u2a_current_confirmed_voice_rejects_revoked_modality_without_charges(
        material_integration_env, monkeypatch):
    """#15: voice commission without current Voice budget cannot reach paid TTS."""
    from easel.integrations import material_generation as paid
    from easel.creation_delivery import active_delivery
    from easel.materials.providers import minimax_pricing
    from easel.integrations import voice_identity
    work, attempt, planning, need, settings = _u2a_current_voice_attempt(
        material_integration_env, monkeypatch)
    assert need.modality_spec.kind=='voice'
    baseline = creation.get_creation(work['id'])
    original = baseline['delivery']['authorization']['material_generation'].copy()
    with creation.edit_creation(work['id']) as mutated:
        mutated['delivery']['authorization']['material_generation']['allowed_modalities'] = ['image']
    quote_calls = []
    monkeypatch.setattr(minimax_pricing, 'read_public_contract',
        lambda *_: quote_calls.append(1) or pytest.fail('revoked Voice never quotes'))
    assert paid.pending_generated_need(
        creation.get_creation(work['id']), attempt, planning['plan']) is None
    with pytest.raises(ValueError, match='预算授权'):
        voice_identity.require_binding(creation.get_creation(work['id']),
                                       planning['plan'],planning['script'])
    token = active_delivery.set(work['id'])
    try:
        with pytest.raises((creation.CreationError, MaterialIntegrationError), match='后台交付者|旁白身份Truth恢复合同无效'):
            paid.generate_for_commission(attempt['attempt_id'])
    finally:
        active_delivery.reset(token)
    assert not quote_calls
    assert not creation.get_creation(work['id'])['delivery'].get('material_generations')
    assert not AttemptMaterialStore(attempt['workspace']['path']).list_generation_records()
    assert service.get_film_attempt(attempt['attempt_id'])['build']['operation'] is None
    with creation.edit_creation(work['id']) as restored:
        restored['delivery']['authorization']['material_generation'] = original
    assert voice_identity.require_binding(creation.get_creation(work['id']),
                                          planning['plan'],planning['script'])


@pytest.mark.parametrize('drift', ['account_key', 'voice_scope', 'modality_permission'])
def test_u2a_current_video_reserved_request_rejects_config_or_grant_drift(
        material_integration_env, monkeypatch, drift):
    """#15: after a real reservation, the executor rechecks frozen consent.

    No Video Adapter may submit even once if account/voice config or the
    stored authorized modality has changed at the pre-submit boundary.
    """
    from dataclasses import replace
    from easel.integrations import material_generation as paid
    from easel.creation_delivery import active_delivery
    from easel.runtime_config import EaselRuntimeConfig, MiniMaxRuntimeConfig
    from easel.materials.providers import minimax_pricing
    from tests.test_minimax_image_speech_generation import MINIMAX_TERMS_FIXTURE
    from easel.materials.store import GenerationRecordNotFound
    work, attempt, planning, settings = _u2a_current_video_budgeted_fixture(
        material_integration_env, monkeypatch)
    need = next(n for n in planning['plan'].needs if n.media_type is MediaType.VIDEO)
    pending = paid.pending_generated_need(
        creation.get_creation(work['id']), attempt, planning['plan'])
    request_id = pending[1]
    quotes = []
    def quote(url):
        quotes.append(url)
        if url == minimax_pricing.TERMS_URL:
            return MINIMAX_TERMS_FIXTURE
        return ('## 图像\n单价：元/张\n| image-01 | 图片 | 0.025 |\n'
                '## 视频\n**视频生成-输出价格**\n'
                '| MiniMax-H3-Max | 480P | 按秒计费 | 0.33 元/秒 |')
    monkeypatch.setattr(minimax_pricing,'read_public_contract',quote)
    incoming = []
    native = MaterialProductOrchestrator.generate_minimax_asset
    def intercept(self, attempt_id, **kwargs):
        assert kwargs['request_id'] == request_id
        ledger=creation.get_creation(work['id'])['delivery']['material_generations']
        assert ledger[request_id]['status']=='reserved'
        incoming.append(kwargs)
        if drift == 'modality_permission':
            with creation.edit_creation(work['id']) as mutated:
                mutated['delivery']['authorization']['material_generation']['allowed_modalities']=['image']
            effective_settings = settings
        else:
            effective_settings=replace(settings,
                api_key='altered-account-key' if drift == 'account_key' else settings.api_key,
                speech_voice_id='unverified-new-voice' if drift == 'voice_scope' else settings.speech_voice_id)
        with pytest.raises(creation.CreationError,match='授权内'):
            paid.assert_commission_request(
                attempt, planning['plan'], planning['script'], effective_settings,
                request_id, need.need_id)
        raise OSError('offline refused before Video Adapter')
    monkeypatch.setattr(MaterialProductOrchestrator,'generate_minimax_asset',intercept)
    token=active_delivery.set(work['id'])
    try:
        with pytest.raises((OSError,GenerationRecordNotFound)):
            paid.generate_for_commission(attempt['attempt_id'])
    finally:
        active_delivery.reset(token)
    assert len(incoming)==1
    assert quotes.count(minimax_pricing.TERMS_URL)==1
    assert creation.get_creation(work['id'])['delivery']['material_generations'][request_id]['status']=='reserved'
    assert not AttemptMaterialStore(attempt['workspace']['path']).list_generation_records()
    assert service.get_film_attempt(attempt['attempt_id'])['build']['operation'] is None
    assert not service.get_film_attempt(attempt['attempt_id']).get('production_authoring')


def _assert_u2a_current_generated_image_rights_and_backlog(
        material_integration_env, monkeypatch, *, backlogged=False, material_only=True,
        validate_signed_consent=False):
    """#04/#15: a fake paid receipt never makes Rights or media Ready by itself."""
    from io import BytesIO
    from PIL import ImageDraw
    from easel.creation_delivery import active_delivery, set_material_endpoint, next_operation
    from easel.integrations import material_generation as paid
    from easel.materials.providers import minimax_pricing
    from easel.materials import providers
    from easel.materials.providers.minimax_image import MiniMaxImageResult
    from tests.material_delta_fixture import observed_result
    from tests.test_minimax_image_speech_generation import MINIMAX_TERMS_FIXTURE
    work, attempt, planning, _ = _current_budgeted_visual_fixture(
        material_integration_env, monkeypatch, True)
    if material_only:
        set_material_endpoint(work['id'])
    def no_stock(*_):
        pytest.fail('empty stock has no image to classify')
    owner = MaterialProductOrchestrator()
    owner.observe_visual_materials(attempt['attempt_id'], executor=no_stock)
    attempt = service.get_film_attempt(attempt['attempt_id'])
    def quote(url):
        if url == minimax_pricing.TERMS_URL: return MINIMAX_TERMS_FIXTURE
        return ('## 图像\n单价：元/张\n| image-01 | 图片 | 0.025 |\n'
                '## 视频\n**视频生成-输出价格**\n'
                '| MiniMax-H3-Max | 480P | 按秒计费 | 0.33 元/秒 |')
    monkeypatch.setattr(minimax_pricing,'read_public_contract',quote)
    picture=Image.new('RGB',(720,1280),(90,75,57))
    draw=ImageDraw.Draw(picture)
    draw.rectangle((80,310,326,765),fill=(253,253,251))
    draw.rectangle((389,330,654,791),fill=(249,249,246))
    body=BytesIO(); picture.save(body,format='PNG')
    submissions=[]
    class NoNetworkImage:
        def __init__(self, api_key, **kwargs):
            assert api_key=='offline-fixture-key'
            self.model=kwargs['model']
        def generate(self, prompt, *, aspect_ratio):
            assert aspect_ratio in {'16:9','9:16'}
            submissions.append(prompt)
            return MiniMaxImageResult(self.model,body.getvalue())
    monkeypatch.setattr(providers,'MiniMaxImageAdapter',NoNetworkImage)
    token=active_delivery.set(work['id'])
    try:
        paid.generate_for_commission(attempt['attempt_id'])
        paid.generate_for_commission(attempt['attempt_id'])
    finally:
        active_delivery.reset(token)
    assert len(submissions)==1
    store=AttemptMaterialStore(attempt['workspace']['path'])
    generated=store.list_generation_records()
    assert len(generated)==1
    record=generated[0]
    asset=store.read_asset(record['asset_id'])
    assert asset.rights.status is RightsStatus.UNKNOWN
    assert asset.file.sha256==hashlib.sha256(body.getvalue()).hexdigest()
    assert service.get_film_attempt(attempt['attempt_id'])['material_gate']['status']=='MATERIAL_NOT_READY'
    if backlogged:
        # Unobserved stock from a previous supply cannot consume the
        # generated-intake slot or make this Need buy another image.
        from easel.integrations import material_results
        previous = store.read_bundle()
        old_id = 'asset-000-unreviewed-stock'
        old_locator = store.write_asset_bytes(old_id, 'stock.png', body.getvalue())
        old_stock = asset.model_copy(update={
            'asset_id': old_id,
            'file': asset.file.model_copy(update={'path': old_locator}),
            'source': CandidateSource(kind='stock', provider='fixture-unreviewed-stock',
                provider_asset_id='archived-candidate'),
            'semantic': SemanticInfo(),
            'rights': RightsInfo(status=RightsStatus.UNKNOWN)})
        store.write_asset(old_stock)
        now = datetime.now(timezone.utc)
        historical_supply = SupplyRun(supply_run_id='u2a-backlog-'+attempt['attempt_id'][-16:],
            plan_id=planning['plan'].plan_id, parent_run_id=previous.supply_run_id,
            started_at=now, finished_at=now, result_bundle_id=previous.bundle_id)
        combined = MaterialBundleAssembler().assemble(
            planning['plan'], historical_supply, (*previous.assets, old_stock),
            previous.matches, bundle_id=previous.bundle_id)
        readiness, gaps = material_results.readiness_calculator(
            attempt, store).calculate(planning['plan'], combined)
        MaterialGateIntegration().record(
            service.get_film_attempt(attempt['attempt_id']),planning['plan'],
            combined,historical_supply,readiness,gaps)
        from easel.materials.application.readiness import MaterialReadinessCalculator
        key = 'visual-budget-' + MaterialReadinessCalculator.plan_revision(planning['plan'])
        spent = [f'prior-stock-{i}:sha256' for i in range(23)]
        store.write_recovery_record(key,{
            'associations': {planning['plan'].needs[0].need_id: list(spent)}})
        assert not paid.pending_generated_need(
            creation.get_creation(work['id']),
            service.get_film_attempt(attempt['attempt_id']), planning['plan'])
    def fixed_visual_observation(current, manifest, attachments):
        assert manifest['asset_id']==asset.asset_id
        return observed_result(current, manifest, attachments,
            outcome='suitable',description='two white papers on brown desk')
    # Generated-intake priority is an Owner-only privilege; a manual
    # observation outside active delivery cannot claim a paid commission.
    token = active_delivery.set(work['id'])
    try:
        result=owner.observe_visual_materials(
            attempt['attempt_id'],executor=fixed_visual_observation)
    finally:
        active_delivery.reset(token)
    assert result['material_status']=='MATERIAL_NOT_READY'
    assert store.read_asset(asset.asset_id).rights.status is RightsStatus.UNKNOWN
    assert next_operation(creation.get_creation(work['id']))[0] != 'generate_material'
    if validate_signed_consent:
        from copy import deepcopy
        from easel.creation_delivery import is_managed
        assert is_managed(creation.get_creation(work['id']))
        proposal=creation.get_creation(work['id'])['delivery']['video_plan']
        consent=creation.get_creation(work['id'])['delivery']['authorization']['input_use']
        assert consent['schema']=='easel-input-use@3'
        assert consent['video_plan_sha256']==proposal['sha256']
        assert consent['script_sha256']==hashlib.sha256(proposal['script'].encode()).hexdigest()
        assert 'text_to_visual_generation' in consent['operations']
        assert record['billing']['status']=='UNKNOWN'  # settled charge still unknown, reservation bounded
        # The official terms version in this isolated test is an offline fixture,
        # never a verified live legal source or a permission to publish.
        agreed=record['commission_authorization']['quote']['terms_evidence']
        assert hashlib.sha256(agreed['document'].encode()).hexdigest()==agreed['sha256']
        monkeypatch.setattr(paid,'MINIMAX_INTERNAL_TERMS_SHA256',agreed['sha256'])
        work_now=creation.get_creation(work['id'])
        retained=store.read_asset(asset.asset_id)
        assert retained.rights.status is RightsStatus.UNKNOWN
        def claim(work_copy=work_now, record_copy=record, candidate=retained,
                  source_need=planning['plan'].needs[0], source_script=planning['script']):
            return paid.commission_generated_rights(
                work_copy, planning['plan'], source_need, candidate, record_copy, source_script)
        claimed=claim()
        assert claimed is not None, 'current signed Consent @3 must be validated by the Rights consumer'
        assert claimed.status is RightsStatus.KNOWN
        assert set(claimed.usage_constraints)=={'internal_production_only','current_creation_only'}
        assert any(e.kind=='asset_commission_use' for e in claimed.evidence)
        assert store.read_asset(asset.asset_id).rights.status is RightsStatus.UNKNOWN
        assert service.get_film_attempt(attempt['attempt_id'])['material_gate']['status']=='MATERIAL_NOT_READY'
        for mutation in ('no_consent','legacy_consent','altered_script','lost_image_operation',
                         'other_creation','unsettled_request','changed_asset_sha',
                         'changed_need','changed_quote'):
            wrong_work=deepcopy(work_now)
            wrong_record=deepcopy(record)
            wrong_asset=retained
            wrong_need=planning['plan'].needs[0]
            if mutation=='no_consent':
                wrong_work['delivery']['authorization']['input_use']=None
            elif mutation=='legacy_consent':
                wrong_work['delivery']['authorization']['input_use']['schema']='easel-input-use@2'
            elif mutation=='altered_script':
                wrong_work['delivery']['authorization']['input_use']['script_sha256']='0'*64
            elif mutation=='lost_image_operation':
                wrong_work['delivery']['authorization']['input_use']['operations'].remove('text_to_visual_generation')
            elif mutation=='other_creation':
                wrong_work['id']='another-creation'
            elif mutation=='unsettled_request':
                key=wrong_record['commission_authorization']['request_id']
                wrong_work['delivery']['material_generations'][key]['status']='uncertain'
            elif mutation=='changed_asset_sha':
                wrong_asset=retained.model_copy(update={
                    'file':retained.file.model_copy(update={'sha256':'0'*64})})
            elif mutation=='changed_need':
                wrong_need=planning['plan'].needs[0].model_copy(update={'role':'unapproved-change'})
            else:
                key=wrong_record['commission_authorization']['request_id']
                wrong_work['delivery']['material_generations'][key]['quote']={}
            assert claim(wrong_work,wrong_record,wrong_asset,wrong_need) is None,mutation
    review = owner.review_material_rights if material_only else owner.review_generated_material_rights
    with pytest.raises(MaterialIntegrationError):
        review(
            attempt['attempt_id'], asset_id=asset.asset_id,
            expected_sha256='0'*64,
            rights=RightsInfo(status=RightsStatus.KNOWN,
                evidence=(RightsEvidence(kind='asset_license',
                    reference='fixture://self-created-paper-image'),)),
            confirm_review=True)
    reviewed=review(
        attempt['attempt_id'], asset_id=asset.asset_id,
        expected_sha256=asset.file.sha256,
        rights=RightsInfo(status=RightsStatus.KNOWN,
            license_name='Offline self-produced pixel fixture',
            evidence=(RightsEvidence(kind='asset_license',
                reference='fixture://self-created-paper-image',
                summary='Test operator owns the image pixels; no external license inferred'),)),
        confirm_review=True)
    assert reviewed['material_status']=='MATERIAL_READY'
    assert store.read_asset(asset.asset_id).file==asset.file
    assert store.read_asset(asset.asset_id).rights.reviewed_at is not None
    # Rights changes the Bundle/Readiness revision. The Owner must reconcile
    # the existing visual evidence under that new Gate, without a second LLM.
    assert next_operation(creation.get_creation(work['id']))[0] == 'observe_material'
    reused = owner.observe_visual_materials(attempt['attempt_id'],
        executor=lambda *_: pytest.fail('pixel result is already saved'))
    assert reused['material_status'] == 'MATERIAL_READY'
    if material_only:
        assert next_operation(creation.get_creation(work['id']))==(None,'material_ready')
        assert not service.get_film_attempt(attempt['attempt_id']).get('production_authoring')
    else:
        assert reviewed['production_authoring']['status'] == 'PENDING_SELECTION'
        assert service.get_film_attempt(attempt['attempt_id'])['production_authoring']['status'] == 'PENDING_SELECTION'
    assert service.get_film_attempt(attempt['attempt_id'])['build']['operation'] is None
    if backlogged:
        assert store.read_asset(old_id).rights.status is RightsStatus.UNKNOWN
        assert not store.read_asset(old_id).semantic.inferences
        assert store.read_recovery_record(key)['associations'][planning['plan'].needs[0].need_id] == spent
        assert store.read_recovery_record(key)['generated_intakes'][planning['plan'].needs[0].need_id] == [
            asset.asset_id + ':' + asset.file.sha256]


def test_u2a_current_generated_image_needs_observation_and_explicit_rights_review(
        material_integration_env, monkeypatch):
    _assert_u2a_current_generated_image_rights_and_backlog(
        material_integration_env, monkeypatch)


def test_u2a_signed_consent_image_commission_rights_is_narrow_not_a_ready_gate(
        material_integration_env, monkeypatch):
    _assert_u2a_current_generated_image_rights_and_backlog(
        material_integration_env, monkeypatch, validate_signed_consent=True)


def test_u2a_current_generated_image_rights_opens_normal_authoring_selection(
        material_integration_env, monkeypatch):
    _assert_u2a_current_generated_image_rights_and_backlog(
        material_integration_env, monkeypatch, material_only=False)


def test_u2a_current_generated_image_is_not_stranded_by_stock_backlog(
        material_integration_env, monkeypatch):
    _assert_u2a_current_generated_image_rights_and_backlog(
        material_integration_env, monkeypatch, backlogged=True)


def test_u2a_current_two_visual_needs_from_confirmed_distinct_scenes(
        material_integration_env, monkeypatch):
    work, attempt, current, _ = _current_budgeted_visual_fixture(
        material_integration_env, monkeypatch, True, max_cost=.06, two_scenes=True)
    needs = [n for n in current['plan'].needs if n.media_type is MediaType.IMAGE]
    assert len(needs) == 2
    assert {n.scope.ref for n in needs} == {'scene-1','scene-2'}
    assert {n.need_id for n in needs} <= set(attempt['material_gate']['blocking_needs'])
    assert not creation.get_creation(work['id'])['delivery'].get('material_generations')


def test_u2a_current_two_image_commissions_share_budget_without_rebuy_or_cross_need(
        material_integration_env, monkeypatch):
    """Two independently frozen scene Needs, exactly two paid-intake receipts.

    Both image bytes are drawn locally and the external model/price responses
    are fixed test data, not actual provider execution or pixel inference.
    """
    from io import BytesIO
    from PIL import ImageDraw
    from easel.creation_delivery import active_delivery
    from easel.integrations import material_generation as paid
    from easel.materials.providers import minimax_pricing
    from easel.materials import providers
    from easel.materials.providers.minimax_image import MiniMaxImageResult
    from tests.material_delta_fixture import observed_result
    from tests.test_minimax_image_speech_generation import MINIMAX_TERMS_FIXTURE

    work, attempt, planning, _ = _current_budgeted_visual_fixture(
        material_integration_env, monkeypatch, True, max_cost=.06, two_scenes=True)
    plan = planning['plan']
    needs = [n for n in plan.needs if n.media_type is MediaType.IMAGE]
    assert len(needs) == 2
    def empty_search_only(*_):
        pytest.fail('empty stock pool cannot invoke image observation')
    owner = MaterialProductOrchestrator()
    owner.observe_visual_materials(attempt['attempt_id'], executor=empty_search_only)
    attempt = service.get_film_attempt(attempt['attempt_id'])
    first = paid.pending_generated_need(
        creation.get_creation(work['id']), attempt, plan)
    assert first is not None and first[0].need_id == needs[0].need_id
    quote_reads=[]
    def quote(url):
        quote_reads.append(url)
        if url == minimax_pricing.TERMS_URL: return MINIMAX_TERMS_FIXTURE
        return ('## 图像\n单价：元/张\n| image-01 | 图片 | 0.025 |\n'
                '## 视频\n**视频生成-输出价格**\n'
                '| MiniMax-H3-Max | 480P | 按秒计费 | 0.33 元/秒 |')
    monkeypatch.setattr(minimax_pricing,'read_public_contract',quote)
    generated=[]
    class OfflineTwoImages:
        def __init__(self, key, **kwargs):
            assert key=='offline-fixture-key'
            self.model=kwargs['model']
        def generate(self,prompt,**kwargs):
            index=len(generated)
            assert index < 2, 'no third billable image may be submitted'
            picture=Image.new('RGB',(720,1280),(90,75,57))
            canvas=ImageDraw.Draw(picture)
            if index == 0:
                canvas.rectangle((80,310,326,765),fill=(253,253,251))
                canvas.rectangle((389,330,654,791),fill=(249,249,246))
            else:
                canvas.rectangle((140,300,600,800),fill=(60,100,190))
            buf=BytesIO(); picture.save(buf,format='PNG')
            generated.append((prompt,buf.getvalue()))
            return MiniMaxImageResult(self.model,buf.getvalue())
    monkeypatch.setattr(providers,'MiniMaxImageAdapter',OfflineTwoImages)
    token=active_delivery.set(work['id'])
    try:
        paid.generate_for_commission(attempt['attempt_id'])
        assert len(generated)==1
        # A new Material revision requires its real observation before the
        # second Need is authorized to use the remaining common budget.
        paid.generate_for_commission(attempt['attempt_id'])
        assert len(generated)==1
        store=AttemptMaterialStore(attempt['workspace']['path'])
        first_record=store.list_generation_records()[0]
        assert first_record['need_id'] == needs[0].need_id
        def inspect_first(current, manifest, attachments):
            assert manifest['asset_id']==first_record['asset_id']
            assert manifest['need']['need_id'] == needs[0].need_id
            return observed_result(current,manifest,attachments,outcome='suitable',
                description='two sheets of white paper on a brown tabletop')
        owner.observe_visual_materials(attempt['attempt_id'],executor=inspect_first)
        next_attempt=service.get_film_attempt(attempt['attempt_id'])
        selected=paid.pending_generated_need(
            creation.get_creation(work['id']), next_attempt,plan)
        assert selected is not None and selected[0].need_id == needs[1].need_id
        paid.generate_for_commission(attempt['attempt_id'])
        paid.generate_for_commission(attempt['attempt_id'])
    finally:
        active_delivery.reset(token)
    store=AttemptMaterialStore(attempt['workspace']['path'])
    records=store.list_generation_records()
    assert len(records)==2 and len(generated)==2
    assert {r['need_id'] for r in records} == {n.need_id for n in needs}
    assert all(r['status']=='COMPLETE' for r in records)
    assert len({r['asset_id'] for r in records}) == 2
    budget=creation.get_creation(work['id'])['delivery']['material_generations']
    assert len(budget)==2
    assert {r['status'] for r in budget.values()} == {'complete'}
    assert sum(float(r['quote']['upper_estimate']) for r in budget.values()) == .05
    assert all(r['rights_status']=='UNKNOWN' for r in records)
    records_by_need={r['need_id']:r for r in records}
    for index, need in enumerate(needs):
        assert store.read_asset(records_by_need[need.need_id]['asset_id']).file.sha256 == (
            hashlib.sha256(generated[index][1]).hexdigest())
    assert all(store.read_asset(r['asset_id']).rights.status is RightsStatus.UNKNOWN for r in records)
    assert quote_reads.count(minimax_pricing.TERMS_URL)==2
    assert service.get_film_attempt(attempt['attempt_id'])['material_gate']['status']=='MATERIAL_NOT_READY'
    assert service.get_film_attempt(attempt['attempt_id'])['build']['operation'] is None


def _u2a_current_shared_visual_asset(material_integration_env, monkeypatch, *, known_rights=True, material_only=True):
    """Current two-scene frozen Plan and a real owned-image SHA/Bundle/Gate."""
    from io import BytesIO
    from PIL import ImageDraw
    from easel.creation_delivery import set_material_endpoint
    work, attempt, planning, _ = _current_budgeted_visual_fixture(
        material_integration_env, monkeypatch, True, max_cost=.06, two_scenes=True)
    if material_only:
        set_material_endpoint(work['id'])
    store = AttemptMaterialStore(attempt['workspace']['path'])
    previous = store.read_bundle()
    picture=Image.new('RGB',(720,1280),(90,75,57))
    canvas=ImageDraw.Draw(picture)
    canvas.rectangle((60,170,288,740), fill=(249,249,246))
    canvas.rectangle((325,200,542,760), fill=(247,247,245))
    canvas.rectangle((190,825,600,1110), fill=(43,87,170))
    image=BytesIO(); picture.save(image,format='PNG')
    data=image.getvalue()
    identity='two-white-pages-and-blue-notebook'
    locator=store.write_asset_bytes(identity,'original.png',data)
    asset=MaterialAsset(
        asset_id=identity, media_type=MediaType.IMAGE,
        file=FileInfo(path=locator, sha256=hashlib.sha256(data).hexdigest(),
                      size=len(data),mime='image/png'),
        source=CandidateSource(kind='local',provider='fixture-self-produced',
                               provider_asset_id=identity),
        rights=RightsInfo(status=RightsStatus.KNOWN,
            license_name='Self-produced local test-image-only fixture',
            evidence=(RightsEvidence(kind='asset_license',
                reference='fixture://self-produced/two-scenes'),)) if known_rights
            else RightsInfo(status=RightsStatus.UNKNOWN),
        technical=TechnicalInfo(status=TechnicalStatus.PASSED,
            width=720,height=1280,mime='image/png'),
        semantic=SemanticInfo(caption='桌面两张白纸和一本蓝色封面笔记本'))
    store.write_asset(asset)
    now=datetime.now(timezone.utc)
    run=SupplyRun(supply_run_id='current-shared-visual-'+attempt['attempt_id'][-12:],
        plan_id=planning['plan'].plan_id,parent_run_id=previous.supply_run_id,
        started_at=now,finished_at=now,result_bundle_id=previous.bundle_id)
    bundle=MaterialBundleAssembler().assemble(
        planning['plan'],run,(asset,),(),bundle_id=previous.bundle_id)
    from easel.integrations import material_results
    readiness, gaps=material_results.readiness_calculator(attempt,store).calculate(
        planning['plan'],bundle)
    attempt=MaterialGateIntegration().record(
        attempt,planning['plan'],bundle,run,readiness,gaps)['attempt']
    assert attempt['material_gate']['status']=='MATERIAL_NOT_READY'
    assert len([n for n in planning['plan'].needs if n.media_type is MediaType.IMAGE])==2
    return work, attempt, planning, store, asset


@pytest.mark.parametrize('failure_point', [
    'self_gate_committed', 'self_bundle_only', 'foreign_gate_replaced',
    'after_complete_marker_interruption', 'foreign_after_complete',
    'normal_delivery_after_own_gate',
])
def test_u2a_current_combination_replay_distinguishes_own_commit_from_foreign_revision(
        material_integration_env, monkeypatch, failure_point):
    """#18: a reviewed Bundle may evolve *because of this same saved decision*.

    The same @4/Consent@3/vNext/Material@3 real offline pixel+Rights fixture
    must resume its own committed Bundle, but not replay after another
    independent Gate changed Match/Source. Never force a source revision == now.
    """
    from tests.material_delta_fixture import observed_result
    from easel.materials.application.assembly import MaterialBundleAssembler

    material_only = failure_point != 'normal_delivery_after_own_gate'
    work, attempt, planning, store, asset = _u2a_current_shared_visual_asset(
        material_integration_env, monkeypatch, material_only=material_only)
    plan=planning['plan']
    owner=MaterialProductOrchestrator()
    def observe(current, manifest, media):
        return observed_result(current, manifest, media,
            outcome='suitable',description='two white note pages beside a blue notebook')
    observed=owner.observe_visual_materials(
        attempt['attempt_id'], executor=observe, group_executor=observe)
    assert observed['material_status']=='MATERIAL_READY'
    ready_attempt=service.get_film_attempt(attempt['attempt_id'])
    before=store.read_bundle()
    original_bytes=store.resolve_asset_locator(asset.file.path).read_bytes()
    original_rights=store.read_asset(asset.asset_id).rights
    frozen_script=PlanningIntegration().load(ready_attempt)['script']
    original_grant=creation.get_creation(work['id'])['delivery']['authorization']
    source_run=store.read_supply_run(before.supply_run_id)
    assert source_run.result_bundle_id==before.bundle_id
    if material_only:
        assert not ready_attempt.get('production_authoring')
    else:
        assert ready_attempt['production_authoring']['status']=='PENDING_SELECTION'
    request=dict(plan_revision=ready_attempt['material_gate']['plan_revision'],
        bundle_revision=before.revision,confirm_review=True,
        reviews=[dict(need_id=n.need_id,asset_id=asset.asset_id,
            expected_sha256=asset.file.sha256,
            observed_content='已逐场景确认两张白纸和蓝色封面笔记本与画面要求一致。',
            logo_present=False,visible_text_present=False)
            for n in plan.needs])
    assert len(request['reviews'])==2

    # A valid frozen Plan is not permission to accept a stale or partial
    # human selection. All refusals occur before the PENDING journal exists.
    from copy import deepcopy
    invalid_requests=[
        {**request,'plan_revision':'0'*64},
        {**request,'bundle_revision':'0'*64},
        {**request,'reviews':request['reviews'][:1]},
        {**request,'reviews':request['reviews']*2},
        {**request,'confirm_review':False},
    ]
    wrong_sha=deepcopy(request)
    wrong_sha['reviews'][0]['expected_sha256']='0'*64
    invalid_requests.append(wrong_sha)
    wrong_asset=deepcopy(request)
    wrong_asset['reviews'][0]['asset_id']='outside-frozen-bundle'
    invalid_requests.append(wrong_asset)
    for wrong in invalid_requests:
        with pytest.raises(MaterialIntegrationError):
            owner.review_material_combination(attempt['attempt_id'],**wrong)
        assert owner.pending_combination_request(ready_attempt) is None
        assert store.read_bundle()==before
        assert store.read_asset(asset.asset_id).rights==original_rights

    with monkeypatch.context() as interrupted:
        if failure_point in {'after_complete_marker_interruption', 'foreign_after_complete'}:
            from easel.integrations import material_layer as integration
            native_update=integration._update_attempt
            def after_journal_before_final_marker(current,**fields):
                if fields.get('material_combination_review',{}).get('status')=='COMPLETE':
                    raise OSError('fixture interruption after own COMPLETE journal before marker')
                return native_update(current,**fields)
            interrupted.setattr(integration,'_update_attempt',after_journal_before_final_marker)
        elif failure_point=='self_bundle_only':
            native=AttemptMaterialStore.write_supply_run
            def after_bundle_before_run(self, run):
                if run.supply_run_id.startswith('match-'):
                    raise OSError('fixture interruption after own Bundle before SupplyRun')
                return native(self,run)
            interrupted.setattr(AttemptMaterialStore,'write_supply_run',
                after_bundle_before_run)
        else:
            native=AttemptMaterialStore.write_recovery_record
            def after_gate_before_complete(self,key,value):
                if key.startswith('combination-') and value.get('status')=='COMPLETE':
                    raise OSError('fixture interruption after own Gate before completion')
                return native(self,key,value)
            interrupted.setattr(AttemptMaterialStore,'write_recovery_record',
                after_gate_before_complete)
        with pytest.raises(OSError,match='fixture interruption after own'):
            owner.review_material_combination(attempt['attempt_id'],**request)
    pending_id=owner.pending_combination_request(service.get_film_attempt(attempt['attempt_id']))
    assert pending_id
    journal=store.read_recovery_record(pending_id)
    assert journal['status']==('COMPLETE' if failure_point in {
        'after_complete_marker_interruption','foreign_after_complete'} else 'PENDING')
    assert journal['plan_revision']==request['plan_revision']
    assert journal['source_run']==source_run.model_dump(mode='json')
    assert journal['result_run'] is not None and journal['result_bundle'] is not None
    own=store.read_bundle()
    assert own.revision!=before.revision
    assert own.bundle_id==before.bundle_id
    assert {a.asset_id for a in own.assets}=={a.asset_id for a in before.assets}
    assert store.read_asset(asset.asset_id).rights==original_rights
    assert store.resolve_asset_locator(asset.file.path).read_bytes()==original_bytes
    assert PlanningIntegration().load(service.get_film_attempt(attempt['attempt_id']))['plan']==plan
    assert creation.get_creation(work['id'])['delivery']['authorization']==original_grant
    committed_run=(store.read_supply_run(own.supply_run_id)
        if failure_point!='self_bundle_only' else None)
    if failure_point in {'foreign_gate_replaced','foreign_after_complete'}:
        # A genuinely different Material Gate (not a replay of the acceptance)
        # changes only Match+SupplyRun; keep all Asset IDs and SHA the same.
        at=service.get_film_attempt(attempt['attempt_id'])
        external_run=SupplyRun(
            supply_run_id='independent-source-'+at['attempt_id'][-18:],
            plan_id=plan.plan_id,parent_run_id=own.supply_run_id,
            started_at=datetime.now(timezone.utc),finished_at=datetime.now(timezone.utc),
            result_bundle_id=own.bundle_id)
        alternative=MaterialBundleAssembler().assemble(
            plan,external_run,own.assets,(),bundle_id=own.bundle_id)
        assert {a.file.sha256 for a in alternative.assets}=={a.file.sha256 for a in own.assets}
        from easel.integrations import material_results
        readiness,gaps=material_results.readiness_calculator(at,store).calculate(
            plan,alternative)
        changed=MaterialGateIntegration().record(
            at,plan,alternative,external_run,readiness,gaps)
        assert changed['attempt']['material_gate']['status']=='MATERIAL_NOT_READY'
        snapshot=(store.read_bundle().to_json(),store.read_supply_run(external_run.supply_run_id).to_json(),
                  service.get_film_attempt(attempt['attempt_id'])['material_gate'],
                  store.read_asset(asset.asset_id).to_json())
        with pytest.raises(MaterialIntegrationError,match='组合|Bundle|匹配|来源|审阅'):
            MaterialProductOrchestrator().finish_material_combination(
                attempt['attempt_id'])
        assert store.read_bundle().to_json()==snapshot[0]
        assert store.read_supply_run(external_run.supply_run_id).to_json()==snapshot[1]
        assert service.get_film_attempt(attempt['attempt_id'])['material_gate']==snapshot[2]
        assert store.read_asset(asset.asset_id).to_json()==snapshot[3]
        assert store.read_recovery_record(pending_id)['status']==journal['status']
    else:
        restored=MaterialProductOrchestrator().finish_material_combination(
            attempt['attempt_id'])
        assert restored['material_status']=='MATERIAL_READY'
        assert restored['attempt']['material_combination_review']['status']=='COMPLETE'
        committed_journal=store.read_recovery_record(pending_id)
        assert committed_journal['status']=='COMPLETE'
        assert committed_journal['source_run']==source_run.model_dump(mode='json')
        assert committed_journal['result_bundle']==own.model_dump(mode='json')
        assert committed_journal['result_run']==store.read_supply_run(own.supply_run_id).model_dump(mode='json')
        assert store.read_bundle().revision==own.revision
        assert store.read_bundle().supply_run_id==own.supply_run_id
        if committed_run is not None:
            assert store.read_supply_run(own.supply_run_id)==committed_run
        from easel.creation_delivery import next_operation
        current=service.get_film_attempt(attempt['attempt_id'])
        if material_only:
            assert not current.get('production_authoring'), (
                'Material-only endpoint never starts Hypit Authoring')
            assert next_operation(creation.get_creation(work['id']))[1]=='material_ready'
        else:
            assert current['production_authoring']['status']=='PENDING_SELECTION'
        assert current['build']['operation'] is None
        assert PlanningIntegration().load(current)['script']==frozen_script
        again=MaterialProductOrchestrator().finish_material_combination(
            attempt['attempt_id'],request_id=pending_id)
        assert again['attempt']['material_gate']==current['material_gate']
    assert store.read_asset(asset.asset_id).rights==original_rights
    assert store.resolve_asset_locator(asset.file.path).read_bytes()==original_bytes
    assert not store.list_generation_records()
    assert service.get_film_attempt(attempt['attempt_id'])['build']['operation'] is None


def test_u2a_current_combination_acceptance_never_upgrades_unknown_rights(
        material_integration_env, monkeypatch):
    """A Creator's preferred composition is not a Material Rights grant."""
    from tests.material_delta_fixture import observed_result
    work, attempt, planning, store, asset = _u2a_current_shared_visual_asset(
        material_integration_env, monkeypatch, known_rights=False)
    owner=MaterialProductOrchestrator()
    def observe(current, manifest, media):
        return observed_result(current,manifest,media,
            outcome='suitable', description='two white note sheets and blue notebook')
    observed=owner.observe_visual_materials(
        attempt['attempt_id'],executor=observe,group_executor=observe)
    assert observed['material_status']=='MATERIAL_NOT_READY'
    frozen=store.read_bundle()
    creation_before=creation.get_creation(work['id'])['delivery']['authorization']
    attempt=service.get_film_attempt(attempt['attempt_id'])
    result=owner.review_material_combination(
        attempt['attempt_id'],plan_revision=attempt['material_gate']['plan_revision'],
        bundle_revision=frozen.revision,confirm_review=True,
        reviews=[dict(need_id=need.need_id,asset_id=asset.asset_id,
            expected_sha256=asset.file.sha256,
            observed_content='已确认真实画面符合当前场景，但尚未确认使用权。',
            logo_present=False,visible_text_present=False)
            for need in planning['plan'].needs])
    assert result['material_status']=='MATERIAL_NOT_READY'
    assert store.read_asset(asset.asset_id).rights.status is RightsStatus.UNKNOWN
    assert service.get_film_attempt(attempt['attempt_id'])['material_gate']['status']=='MATERIAL_NOT_READY'
    assert not service.get_film_attempt(attempt['attempt_id']).get('production_authoring')
    assert not service.get_film_attempt(attempt['attempt_id'])['build']['operation']
    assert creation.get_creation(work['id'])['delivery']['authorization']==creation_before
    assert store.read_bundle().plan_id==frozen.plan_id
    assert store.resolve_asset_locator(asset.file.path).stat().st_size==asset.file.size


def test_u2a_current_vnext_video_multiframe_delta_receipt_replay_and_tamper(
        material_integration_env, monkeypatch):
    """A real current @4 frozen *video* Need supplies multiple sampled frames.

    Unlike old custom Planning, its two+ Material batches come from the actual
    source media time axis, not new clauses inserted after confirmation.
    """
    import subprocess
    import sys
    from easel.creation_delivery import set_material_endpoint
    from easel.materials.application.visual_observation import prepare_observation
    from easel.materials.application.visual_contract import (
        compilation_input, read_requirements_contract, batches)
    from easel.integrations.hypit.handoff import load_frozen_creative_mode

    work, attempt, planning, _ = _u2a_current_video_budgeted_fixture(
        material_integration_env, monkeypatch)
    set_material_endpoint(work['id'])
    plan=planning['plan']
    need=next(n for n in plan.needs if n.media_type is MediaType.VIDEO)
    assert need.constraints.get('requires_dynamic_action') is True
    root=Path(attempt['workspace']['path'])
    store=AttemptMaterialStore(root)
    source=store.read_bundle()
    mp4=root / 'offline-five-seconds-portrait.mp4'
    subprocess.run(['ffmpeg','-v','error','-nostdin','-y','-f','lavfi',
        '-i','testsrc2=s=180x320:r=10:d=5','-an','-c:v','libx264',
        '-pix_fmt','yuv420p',str(mp4)],
        capture_output=True,check=True,timeout=45)
    data=mp4.read_bytes()
    asset_id='self-produced-motion-video'
    locator=store.write_asset_bytes(asset_id,'original.mp4',data)
    asset=MaterialAsset(
        asset_id=asset_id, media_type=MediaType.VIDEO,
        file=FileInfo(path=locator,sha256=hashlib.sha256(data).hexdigest(),
                      size=len(data),mime='video/mp4'),
        source=CandidateSource(kind='local',provider='fixture-self-produced',
                               provider_asset_id=asset_id),
        rights=RightsInfo(status=RightsStatus.KNOWN,
            license_name='Offline self-produced video-pixels fixture',
            evidence=(RightsEvidence(kind='asset_license',
                reference='fixture://self-produced/video-five-seconds'),)),
        technical=TechnicalInfo(status=TechnicalStatus.PASSED,
            width=180,height=320,duration_seconds=5,mime='video/mp4'),
        semantic=SemanticInfo(caption='dynamic pattern for contract verification'))
    store.write_asset(asset)
    now=datetime.now(timezone.utc)
    run=SupplyRun(supply_run_id='motion-fixture-'+attempt['attempt_id'][-20:],
        plan_id=plan.plan_id,parent_run_id=source.supply_run_id,
        started_at=now,finished_at=now,result_bundle_id=source.bundle_id)
    bundle=MaterialBundleAssembler().assemble(plan,run,(asset,),(),bundle_id=source.bundle_id)
    from easel.integrations import material_results
    readiness,gaps=material_results.readiness_calculator(attempt,store).calculate(plan,bundle)
    attempt=MaterialGateIntegration().record(
        attempt,plan,bundle,run,readiness,gaps)['attempt']
    assert attempt['material_gate']['status']=='MATERIAL_NOT_READY'
    manifest, attachments=prepare_observation(
        need,asset,store.resolve_asset_locator(asset.file.path))
    mode=load_frozen_creative_mode(attempt)[0]
    frozen=compilation_input(need,plan.context_refs,mode,plan=plan)
    contract=read_requirements_contract(store,frozen)
    assert contract is not None
    windows=batches(manifest,contract)
    assert len(manifest['frames'])>=2
    assert len(windows)>=2
    assert len(attachments)>=2
    assert {x['frame']['index'] for x in windows} == {
        x['index'] for x in manifest['frames']}
    assert store.resolve_asset_locator(asset.file.path).read_bytes()==data
    assert store.read_plan() == plan
    assert not creation.get_creation(work['id'])['delivery'].get('material_generations')
    assert not attempt['build']['operation']

    # The real Delta owner records one facts result plus independently
    # source-bound delta answers for every additional sampled video frame.
    from easel.integrations import output_receipts as receipts
    from tests.material_delta_fixture import observed_result
    from easel.creation_delivery import active_delivery
    from easel.materials.application.visual_observation import read_observation_report
    import subprocess as child_process

    actual_model_calls=[]
    def offline_observe(current, item, media):
        assert item['need']['need_id']==need.need_id
        assert item['asset_sha256']==asset.file.sha256
        assert len(media)==len(manifest['frames'])
        return observed_result(current,item,media,outcome='suitable',
            description='offline video fixture pixels (not a real inference)',
            invocations=actual_model_calls)
    owner=MaterialProductOrchestrator()
    original_capture=receipts.capture_result
    interrupted=[]
    def capture_then_fail(*args,**kwargs):
        receipt=original_capture(*args,**kwargs)
        if not interrupted:
            interrupted.append(receipt['key'])
            raise OSError('offline after first video-frame capture')
        return receipt
    token=active_delivery.set(work['id'])
    try:
        with monkeypatch.context() as local:
            local.setattr(receipts,'capture_result',capture_then_fail)
            with pytest.raises(OSError,match='after first video-frame capture'):
                owner.observe_visual_materials(attempt['attempt_id'], executor=offline_observe)
        assert len(actual_model_calls)==1
        assert not store.read_asset(asset.asset_id).semantic.inferences
        for _ in range(3):
            owner.observe_visual_materials(attempt['attempt_id'],
                executor=offline_observe)
            report_path=store.materials_root / 'observations' / (manifest['input_sha256']+'.json')
            if report_path.is_file(): break
        assert report_path.is_file()
        report=read_observation_report(
            report_path,need,store.read_asset(asset.asset_id),manifest,
            result_processor=material_results.processor(attempt,store))
        assert report['schema']==material_results.REPORT
        assert len(report['result_groups'])==len(windows)
        # Distinct video frames cannot borrow other frames' visible facts.
        # The Delta consumer correctly uses a separate facts capture per SHA;
        # only multiple clause groups *within one frame* use delta mode.
        assert all(r.get('observed') is True for r in report['wire_results'])
        assert len({frame['sha256'] for frame in manifest['frames']})>=2
        assert len(actual_model_calls)==len(windows), (
            'first video frame must reuse its exact originally captured answer')
        material_results.verify_report(store,manifest,report)
        store.write_recovery_record('current-vnext-video-delta-evidence',{
            'manifest':manifest,'report':report})
        cold_script=(
            "import sys,socket; from easel.materials.store import AttemptMaterialStore; "
            "from easel.integrations import material_results; "
            "socket.socket.connect=lambda *a,**k: (_ for _ in ()).throw(AssertionError('network forbidden')); "
            "s=AttemptMaterialStore(sys.argv[1]); r=s.read_recovery_record('current-vnext-video-delta-evidence'); "
            "assert material_results.verify_report(s,r['manifest'],r['report'])==r['report']; "
            "print('CURRENT_VNEXT_VIDEO_DELTA_COLD_PASS')"
        )
        cold=child_process.run(
            [sys.executable,'-c',cold_script,str(root)],
            capture_output=True,text=True,timeout=35)
        assert cold.returncode==0, cold.stderr[:600]
        assert 'CURRENT_VNEXT_VIDEO_DELTA_COLD_PASS' in cold.stdout
        assert len(actual_model_calls)==len(windows)
        assert store.read_asset(asset.asset_id).file==asset.file
        assert store.resolve_asset_locator(asset.file.path).read_bytes()==data
        assert PlanningIntegration().load(service.get_film_attempt(attempt['attempt_id']))['plan']==plan
        assert not service.get_film_attempt(attempt['attempt_id'])['build']['operation']
        ref=report['result_groups'][1]['derivation']
        original=store.read_recovery_record(ref['key'])
        store.write_recovery_record(ref['key'],
            {**original,'unbound_extra_projection':'reject-on-cold-replay'})
        from easel.integrations import output_receipts as proof
        with pytest.raises(proof.OutputReceiptError):
            material_results.verify_report(store,manifest,report)
        broken=child_process.run(
            [sys.executable,'-c',cold_script,str(root)],
            capture_output=True,text=True,timeout=35)
        assert broken.returncode!=0 and 'OutputReceiptError' in broken.stderr
        assert len(actual_model_calls)==len(windows)
        assert not service.get_film_attempt(attempt['attempt_id'])['build']['operation']
    finally:
        active_delivery.reset(token)


def test_u2a_current_shared_local_pixel_observation_is_per_need(
        material_integration_env, monkeypatch):
    from tests.material_delta_fixture import observed_result
    from easel.materials.application.visual_observation import observed_match
    work, attempt, planning, store, asset=_u2a_current_shared_visual_asset(
        material_integration_env, monkeypatch)
    seen=[]
    def per_need(current,manifest,attachments):
        seen.append(manifest['need']['need_id'])
        assert manifest['asset_id']==asset.asset_id
        return observed_result(current,manifest,attachments,
            outcome='suitable',description='two white sheets next to a blue notebook')
    def shared(current,group,attachments):
        for item in group['observations']:
            seen.append(item['need']['need_id'])
            assert item['asset_id']==asset.asset_id
        return observed_result(current,group,attachments,
            outcome='suitable',description='two white sheets next to a blue notebook')
    result=MaterialProductOrchestrator().observe_visual_materials(
        attempt['attempt_id'],executor=per_need,group_executor=shared)
    ids={n.need_id for n in planning['plan'].needs}
    assert ids <= set(seen)
    assert result['material_status']=='MATERIAL_READY'
    assert all(observed_match(n,store.read_asset(asset.asset_id)) is True
               for n in planning['plan'].needs)
    assert {r['need_id'] for r in result['attempt']['material_observation']['outcomes']} == ids
    assert service.get_film_attempt(attempt['attempt_id'])['build']['operation'] is None
    assert not service.get_film_attempt(attempt['attempt_id']).get('production_authoring')


def test_u2a_current_material_delta_dispute_revokes_shared_facts_but_preserves_independent_gate(
        material_integration_env, monkeypatch):
    """P0-A: current @4/@3/vNext two-Need real PNG Gate; disputed facts are not Rights or Authority.

    One image's published facts are shared across Need-bound reports. A separate
    image has independently captured facts, so a durable Delta dispute must
    invalidate only the former; no model re-purchase, Gate mutation, or forged READY.
    """
    from io import BytesIO
    from PIL import ImageDraw
    from easel.integrations import material_results
    from easel.materials.application.visual_observation import (
        prepare_observation, apply_observation, observed_match)
    from easel.materials.application.visual_contract import (
        compilation_input, read_requirements_contract)
    from easel.integrations.hypit.handoff import load_frozen_creative_mode
    from tests.material_delta_fixture import observed_result
    from tests.test_material_result_delta import _owner, _answer

    work, attempt, planning, store, source = _u2a_current_shared_visual_asset(
        material_integration_env, monkeypatch)
    plan=planning['plan']
    needs=list(plan.needs)
    original_source=store.resolve_asset_locator(source.file.path).read_bytes()
    original_bundle=store.read_bundle()
    picture=Image.new('RGB',(720,1280),(44,70,94))
    canvas=ImageDraw.Draw(picture)
    canvas.rectangle((45,180,288,870), fill=(248,250,247))
    canvas.rectangle((343,175,668,882), fill=(250,250,249))
    buf=BytesIO(); picture.save(buf,format='PNG')
    bytes_backup=buf.getvalue()
    backup_id='independent-scene-evidence'
    locator=store.write_asset_bytes(backup_id,'original.png',bytes_backup)
    backup=source.model_copy(update={
        'asset_id':backup_id,
        'file':source.file.model_copy(update={
            'path':locator,'sha256':hashlib.sha256(bytes_backup).hexdigest(),
            'size':len(bytes_backup)}),
        'source':source.source.model_copy(update={'provider_asset_id':backup_id}),
        'semantic':SemanticInfo(caption='two white pages on the desk')})
    store.write_asset(backup)
    now=datetime.now(timezone.utc)
    supply=SupplyRun(
        supply_run_id='two-independent-facts-'+attempt['attempt_id'][-15:],
        plan_id=plan.plan_id,parent_run_id=original_bundle.supply_run_id,
        started_at=now,finished_at=now,result_bundle_id=original_bundle.bundle_id)
    bundle=MaterialBundleAssembler().assemble(
        plan,supply,(source,backup),(),bundle_id=original_bundle.bundle_id)
    ready,gaps=material_results.readiness_calculator(attempt,store).calculate(plan,bundle)
    attempt=MaterialGateIntegration().record(attempt,plan,bundle,supply,ready,gaps)['attempt']
    assert attempt['material_gate']['status']=='MATERIAL_NOT_READY'
    observed_invocations=[]
    def publish(need,item):
        current=store.read_asset(item.asset_id)
        manifest,attachments=prepare_observation(
            need,current,store.resolve_asset_locator(current.file.path))
        report=observed_result(attempt,manifest,attachments,
            outcome='suitable',description='two separate pages seen',
            invocations=observed_invocations)
        assert material_results.verify_report(store,manifest,report)==report
        reviewed=apply_observation(need,current,manifest,report,
            result_processor=material_results.processor(attempt,store))
        store.write_asset(reviewed)
        return manifest,report
    primary_manifest,primary_report=publish(needs[0],source)
    for need in needs:
        publish(need,backup)
    first=store.read_asset(source.asset_id)
    second=store.read_asset(backup.asset_id)
    assert observed_match(needs[0],first) is True
    assert all(observed_match(n,second) is True for n in needs)
    assert all(material_results.eligible(store,n,second,attempt=attempt,allow_creator=False)
               for n in needs)
    original_capture=primary_report['result_groups'][0]['capture_key']
    original_capture_record=store.read_recovery_record(original_capture)
    assert original_capture_record and isinstance(original_capture_record,dict)
    assert material_results.eligible(store,needs[0],first,attempt=attempt,allow_creator=False)
    result=MaterialProductOrchestrator._recalculate_observed_materials(
        service.get_film_attempt(attempt['attempt_id']),plan,store.read_bundle(),store,
        require_scoped_visual=True)
    assert result['material_status']=='MATERIAL_READY'
    at=service.get_film_attempt(attempt['attempt_id'])
    current_bundle=store.read_bundle()
    assert {m.asset_id for m in current_bundle.matches if m.qualified}=={
        source.asset_id,backup.asset_id}
    original_creation=creation._creation_path(work['id']).read_bytes()

    challenge=store.read_asset(source.asset_id)
    manifest,attachments=prepare_observation(
        needs[1],challenge,store.resolve_asset_locator(challenge.file.path))
    mode,_=load_frozen_creative_mode(at)
    contract=read_requirements_contract(store,
        compilation_input(needs[1],plan.context_refs,mode,plan=plan))
    assert contract is not None
    pin,invoke,called=_owner(store,lambda payload:_answer(payload,dispute=True))
    from easel.integrations.material_results import MaterialFactsDisputed
    with pytest.raises(MaterialFactsDisputed):
        material_results.observe(at,manifest,contract,attachments,
            pin=pin,invoke=invoke)
    assert len(called)==1 and called[0][0]=='delta',(
        'only shared original pixel facts, not the independent backup, may be disputed',called)
    before_calls=list(called)
    with pytest.raises(MaterialFactsDisputed):
        material_results.observe(at,manifest,contract,attachments,pin=pin,invoke=invoke)
    assert called==before_calls, 'valid discrepancy must not trigger model repair or rebuy'
    assert store.read_recovery_record(original_capture)==original_capture_record
    with pytest.raises(MaterialFactsDisputed):
        material_results.verify_report(store,primary_manifest,primary_report)
    # A separate local interpreter confirms that a cold Owner reads the same
    # durable dispute, never silently restoring formerly qualified facts.
    import subprocess,sys
    cold_script=(
        "import json,socket,sys; from easel.materials.store import AttemptMaterialStore; "
        "from easel.integrations import material_results; "
        "socket.socket.connect=lambda *a,**k: (_ for _ in ()).throw(AssertionError('network forbidden')); "
        "store=AttemptMaterialStore(sys.argv[1]); plan=store.read_plan(); "
        "a={'creation_id':plan.creation_id,'attempt_id':plan.attempt_id,'result_protocols':json.loads(sys.argv[2])}; "
        "assert not material_results.eligible(store,plan.needs[0],store.read_asset(sys.argv[3]),attempt=a,allow_creator=False); "
        "assert all(material_results.eligible(store,n,store.read_asset(sys.argv[4]),attempt=a,allow_creator=False) for n in plan.needs); "
        "print('CURRENT_DELTA_COLD_GATED')"
    )
    cold=subprocess.run([sys.executable,'-c',cold_script,str(store.attempt_root),
        json.dumps(at['result_protocols']),source.asset_id,backup.asset_id],
        capture_output=True,text=True,timeout=35)
    assert cold.returncode==0,cold.stderr[:900]
    assert 'CURRENT_DELTA_COLD_GATED' in cold.stdout
    assert not material_results.eligible(store,needs[0],store.read_asset(source.asset_id),
        attempt=at,allow_creator=False)
    assert all(material_results.eligible(store,n,store.read_asset(backup.asset_id),
        attempt=at,allow_creator=False) for n in needs)
    assert MaterialGateIntegration().assert_ready(
        service.get_film_attempt(attempt['attempt_id']))[2].status.value=='READY'
    assert ProductionAuthoringIntegration._qualified_need_ids(
        plan,current_bundle,store.read_asset(source.asset_id),store=store,attempt=at)==()
    assert set(ProductionAuthoringIntegration._qualified_need_ids(
        plan,current_bundle,store.read_asset(backup.asset_id),store=store,attempt=at))=={
            n.need_id for n in needs}
    filtered=MaterialBundleAssembler().assemble(
        plan,supply,(store.read_asset(source.asset_id),),
        tuple(m for m in current_bundle.matches if m.asset_id==source.asset_id),
        bundle_id=current_bundle.bundle_id)
    unqualified,_=material_results.readiness_calculator(at,store).calculate(plan,filtered)
    assert unqualified.status.value=='NOT_READY'
    assert store.read_bundle()==current_bundle
    assert creation._creation_path(work['id']).read_bytes()==original_creation
    assert store.resolve_asset_locator(source.file.path).read_bytes()==original_source
    assert store.resolve_asset_locator(backup.file.path).read_bytes()==bytes_backup
    assert store.read_asset(source.asset_id).rights==source.rights
    assert store.read_asset(backup.asset_id).rights==backup.rights
    assert not store.list_generation_records()
    assert not at['build']['operation']
    assert not at.get('production_authoring')


@pytest.mark.parametrize('interrupt_first', [False, True],
    ids=['ordinary-bounded-pool','cold-replay-saved-first-capture'])
def test_u2a_current_sparse_unlabelled_pool_and_late_source_preserves_need_budgets(
        material_integration_env, monkeypatch, interrupt_first):
    """P0-B: real two-scene frozen Plan, no-label pool, late actual local PNG.

    Unknown metadata is never a permission to review the Need x entire pool,
    or to reset a previous Need/Source association on another SupplyRun.
    """
    from io import BytesIO
    from PIL import ImageDraw
    from tests.material_delta_fixture import observed_result
    from easel.creation_delivery import DeliveryExecutionUncertain
    from easel.materials.application.visual_observation import need_identity

    work,attempt,planning,store,source=_u2a_current_shared_visual_asset(
        material_integration_env,monkeypatch)
    plan=planning['plan']
    needs=list(plan.needs)
    old_bundle=store.read_bundle()
    source=source.model_copy(update={'semantic':SemanticInfo()})
    store.write_asset(source)
    candidates=[source]
    original_bytes={source.asset_id:store.resolve_asset_locator(source.file.path).read_bytes()}
    def local_candidate(index,caption=None):
        pic=Image.new('RGB',(720,1280),(70+index*13,60,90))
        ImageDraw.Draw(pic).ellipse((35+index*8,270,600,910),fill=(198,44+index*14,65))
        buffer=BytesIO();pic.save(buffer,format='PNG')
        data=buffer.getvalue()
        key=f'unlabelled-scene-{index}'
        path=store.write_asset_bytes(key,'original.png',data)
        asset=source.model_copy(update={
            'asset_id':key,'file':source.file.model_copy(update={
                'path':path,'sha256':hashlib.sha256(data).hexdigest(),'size':len(data)}),
            'source':source.source.model_copy(update={'provider_asset_id':key}),
            'semantic':SemanticInfo(caption=caption)})
        store.write_asset(asset)
        original_bytes[key]=data
        return asset
    for idx in range(1,4):
        candidates.append(local_candidate(idx))
    def record_pool(current,rows,identity):
        run=SupplyRun(supply_run_id=identity,plan_id=plan.plan_id,
            parent_run_id=old_bundle.supply_run_id,
            started_at=datetime.now(timezone.utc),finished_at=datetime.now(timezone.utc),
            result_bundle_id=old_bundle.bundle_id)
        bundle=MaterialBundleAssembler().assemble(plan,run,tuple(rows),(),
            bundle_id=old_bundle.bundle_id)
        from easel.integrations import material_results
        readiness,gaps=material_results.readiness_calculator(current,store).calculate(plan,bundle)
        return MaterialGateIntegration().record(current,plan,bundle,run,readiness,gaps)['attempt']
    attempt=record_pool(attempt,candidates,'unlabelled-source-'+attempt['attempt_id'][-17:])
    assert attempt['material_gate']['status']=='MATERIAL_NOT_READY'
    observed_calls,model_calls=[],[]
    failed=[]
    def pixels(current,manifest,attachments):
        observed_calls.append((manifest['need']['need_id'],manifest['asset_id'],
                               manifest['input_sha256']))
        report=observed_result(current,manifest,attachments,
            outcome=('suitable' if (manifest['asset_id']=='unlabelled-scene-4'
                and manifest['need']['need_id']==needs[1].need_id) else 'unsuitable'),
            description='actual desk sheets evidence',invocations=model_calls)
        if interrupt_first and not failed:
            failed.append(observed_calls[-1])
            raise DeliveryExecutionUncertain('one terminal report captured before Owner journal')
        return report
    owner=MaterialProductOrchestrator()
    if interrupt_first:
        with pytest.raises(DeliveryExecutionUncertain):
            owner.observe_visual_materials(attempt['attempt_id'],executor=pixels)
        assert len(failed)==1 and model_calls
        first_model_session=model_calls[0]
        owner=MaterialProductOrchestrator()
    first=owner.observe_visual_materials(attempt['attempt_id'],executor=pixels)
    assert first['material_status']=='MATERIAL_NOT_READY'
    assert len({(a,b) for a,b,_ in observed_calls})<=len(needs),observed_calls
    assert len(model_calls)==len(set(model_calls)), 'no duplicate provider/model submission'
    if interrupt_first:
        assert model_calls.count(first_model_session)==1
    ledger_key='visual-budget-'+MaterialReadinessCalculator.plan_revision(plan)
    first_ledger=store.read_recovery_record(ledger_key)
    assert first_ledger
    first_associations={k:tuple(v) for k,v in first_ledger['associations'].items()}
    assert sum(len(v) for v in first_associations.values())<=len(needs)
    saved_original=list(model_calls)
    saved_pairs=set((a,b) for a,b,_ in observed_calls)
    late=local_candidate(4,needs[1].intent.description)
    candidates.append(late)
    latest=record_pool(service.get_film_attempt(attempt['attempt_id']),
                       candidates,'late-actual-source-'+attempt['attempt_id'][-17:])
    assert latest['material_gate']['status']=='MATERIAL_NOT_READY'
    second=MaterialProductOrchestrator().observe_visual_materials(
        attempt['attempt_id'],executor=pixels)
    new_pairs={(a,b) for a,b,_ in observed_calls} - saved_pairs
    assert new_pairs=={(need.need_id,late.asset_id) for need in needs},{
        'observed_pairs':new_pairs,'all_calls':observed_calls,
        'gate':second['material_status']}
    # The same labelled hint can nominate both Need associations; each must
    # consume its own pixel verdict. Negative Need0 is not accepted via Need1.
    assert len([a for a,b,_ in observed_calls if b==late.asset_id])==2
    assert second['material_status']=='MATERIAL_NOT_READY'
    assert len(model_calls)==len(set(model_calls))
    assert model_calls[:len(saved_original)]==saved_original
    ledger=store.read_recovery_record(ledger_key)
    assert all(set(values)<=set(ledger['associations'].get(need_id,()))
               for need_id,values in first_associations.items())
    assert sum(len(v) for v in ledger['associations'].values())<=2*len(needs)
    assert second['attempt']['material_observation']['nominated_associations']<=2*len(needs)
    after=list(observed_calls)
    MaterialProductOrchestrator().observe_visual_materials(
        attempt['attempt_id'],executor=lambda *_: pytest.fail('all original slots already proven'))
    assert observed_calls==after
    assert len(model_calls)==len(set(model_calls))
    for current in candidates:
        stable=store.read_asset(current.asset_id)
        assert stable.file==current.file and stable.rights==current.rights
        assert store.resolve_asset_locator(current.file.path).read_bytes()==original_bytes[current.asset_id]
        assert hashlib.sha256(original_bytes[current.asset_id]).hexdigest()==current.file.sha256
    assert not store.list_generation_records()
    assert service.get_film_attempt(attempt['attempt_id'])['build']['operation'] is None
    assert not service.get_film_attempt(attempt['attempt_id']).get('production_authoring')
    assert PlanningIntegration().load(service.get_film_attempt(attempt['attempt_id']))['plan']==plan


def test_u2a_current_director_style_and_selected_asset_rights_are_independent_of_ready_gate(
        material_integration_env, monkeypatch):
    """P0-C New-Only: frozen Director preference is soft; accepted Asset is not bypassable.

    Two real local PNGs each independently match two frozen scene Needs. Another
    good Asset keeps the global Material Gate READY after the accepted Asset
    loses Rights, yet the Creator-selected source cannot enter Native Selection.
    """
    from io import BytesIO
    from PIL import ImageDraw
    from easel.integrations.hypit.handoff import load_frozen_creative_mode
    from easel.materials.application.generation import visual_generation_prompt
    from easel.materials.application.visual_observation import (
        prepare_observation,apply_observation)
    from easel.integrations import material_results
    from tests.material_delta_fixture import observed_result
    from tests import test_semantic_planning as fixed_semantics
    from copy import deepcopy

    style='muted documentary daylight'
    detail='优先用桌面自然光下的两张白纸近景，保持人物不露脸。'
    mode_path=creative_mode.CREATIVE_MODES_DIR/'clear_memo_video/mode.json'
    baseline=json.loads(mode_path.read_text(encoding='utf-8'))
    mode_path.write_text(json.dumps(
        {**baseline,'visual_material_style':style},ensure_ascii=False))
    original_semantic=fixed_semantics.vnext_proposal
    def confirmed_director_preference():
        draft=deepcopy(original_semantic())
        draft['needs'][0]['conditions'].append({
            'text':detail,'strength':'preference','responsibility':'material'})
        return draft
    monkeypatch.setattr(fixed_semantics,'vnext_proposal',confirmed_director_preference)
    work,attempt,planning,store,chosen=_u2a_current_shared_visual_asset(
        material_integration_env,monkeypatch,material_only=False)
    plan=planning['plan']
    mode,mode_hash=load_frozen_creative_mode(attempt)
    assert mode['visual_material_style']==style
    assert plan.context_refs['creative_mode_sha256']==mode_hash
    assert all(n.constraints['preferred_style']==style for n in plan.needs)
    assert plan.needs[0].constraints['preferred_visual_details']==detail
    assert detail not in plan.needs[0].intent.description
    compiler=NeedCompiler.for_plan(plan)
    compiled=compiler.compile(plan.needs[0])
    assert 'preferred_style' not in compiled.filters
    assert 'preferred_visual_details' not in compiled.filters
    assert compiled.ranking_hints['preferred_visual_details']==detail
    prompt=visual_generation_prompt(plan.needs[0])
    assert plan.needs[0].intent.description in prompt and style in prompt and detail in prompt
    mode_path.write_text(json.dumps({**baseline,'visual_material_style':'irrelevant glossy style'}))
    assert load_frozen_creative_mode(attempt)[0]['visual_material_style']==style
    assert PlanningIntegration().load(attempt)['plan']==plan

    before=store.read_bundle()
    buf=BytesIO()
    image=Image.new('RGB',(720,1280),(50,69,87))
    draw=ImageDraw.Draw(image)
    draw.rectangle((35,155,313,805),fill=(248,248,245))
    draw.rectangle((345,155,675,805),fill=(251,249,245))
    image.save(buf,format='PNG')
    bytes_good=buf.getvalue()
    id_good='current-independent-authoring-source'
    path=store.write_asset_bytes(id_good,'original.png',bytes_good)
    good=chosen.model_copy(update={
        'asset_id':id_good,
        'file':chosen.file.model_copy(update={'path':path,
            'sha256':hashlib.sha256(bytes_good).hexdigest(),'size':len(bytes_good)}),
        'source':chosen.source.model_copy(update={'provider_asset_id':id_good}),
        'semantic':SemanticInfo(caption='two pages and a blue notebook')})
    store.write_asset(good)
    run=SupplyRun(supply_run_id='style-ready-'+attempt['attempt_id'][-19:],
        plan_id=plan.plan_id,parent_run_id=before.supply_run_id,
        started_at=datetime.now(timezone.utc),finished_at=datetime.now(timezone.utc),
        result_bundle_id=before.bundle_id)
    initial=MaterialBundleAssembler().assemble(
        plan,run,(chosen,good),(),bundle_id=before.bundle_id)
    calc=material_results.readiness_calculator(attempt,store)
    assessment,gaps=calc.calculate(plan,initial)
    attempt=MaterialGateIntegration().record(attempt,plan,initial,run,assessment,gaps)['attempt']
    source_bytes=store.resolve_asset_locator(chosen.file.path).read_bytes()
    for asset in (chosen,good):
        for need in plan.needs:
            current=store.read_asset(asset.asset_id)
            manifest,attachments=prepare_observation(
                need,current,store.resolve_asset_locator(current.file.path))
            report=observed_result(attempt,manifest,attachments,
                outcome='suitable',description='two white pages visibly next to a notebook')
            store.write_asset(apply_observation(need,current,manifest,report,
                result_processor=material_results.processor(attempt,store)))
    owner=MaterialProductOrchestrator()
    updated=owner._recalculate_observed_materials(
        service.get_film_attempt(attempt['attempt_id']),plan,store.read_bundle(),
        store,require_scoped_visual=True)
    assert updated['material_status']=='MATERIAL_READY'
    current=service.get_film_attempt(attempt['attempt_id'])
    assert current['production_authoring']['status']=='PENDING_SELECTION'
    current_bundle=store.read_bundle()
    choices={n.need_id: {'asset_id':chosen.asset_id,'sha256':chosen.file.sha256}
             for n in plan.needs}
    args={'plan_revision':current['material_gate']['plan_revision'],
          'bundle_revision':current_bundle.revision,'confirm_review':True,
          'reviews':[{'need_id':n.need_id,'asset_id':chosen.asset_id,
                      'expected_sha256':chosen.file.sha256,
                      'observed_content':'两张白纸与蓝色笔记本在当前场景中均清晰可见。',
                      'logo_present':False,'visible_text_present':False}
                     for n in plan.needs]}
    selected=owner.review_material_combination(attempt['attempt_id'],**args)
    assert selected['material_status']=='MATERIAL_READY'
    current=service.get_film_attempt(attempt['attempt_id'])
    selection_path=store.attempt_root/'productions/easel-authoring/material-selection.json'
    admitted=json.loads(selection_path.read_text())
    assert admitted['creator_material_choices']==choices
    assert ProductionAuthoringIntegration.accepted_combination(
        current,plan,store.read_bundle(),store)==choices
    chosen_rights=store.read_asset(chosen.asset_id).rights
    backup_rights=store.read_asset(good.asset_id).rights

    # Simulate an externally discovered rights revocation in this *isolated*
    # current Attempt. The real Gate recomputes; no user grant is added.
    selected_now=store.read_asset(chosen.asset_id)
    store.write_asset(selected_now.model_copy(update={
        'rights':RightsInfo(status=RightsStatus.UNKNOWN)}))
    rechecked=owner._recalculate_observed_materials(
        service.get_film_attempt(attempt['attempt_id']),plan,store.read_bundle(),
        store,require_scoped_visual=True)
    assert rechecked['material_status']=='MATERIAL_READY',(
        'independent source must keep each Need covered')
    current=service.get_film_attempt(attempt['attempt_id'])
    assert MaterialGateIntegration().assert_ready(current)[2].status.value=='READY'
    assert current['material_combination_review']['blocking_needs']==[n.need_id for n in plan.needs]
    assert all(n.need_id in ProductionAuthoringIntegration._qualified_need_ids(
        plan,store.read_bundle(),store.read_asset(good.asset_id),store=store,attempt=current)
        for n in plan.needs)
    with pytest.raises(MaterialIntegrationError,match='权利|匹配|已接受'):
        ProductionAuthoringIntegration.accepted_combination(current,plan,store.read_bundle(),store)
    with pytest.raises(MaterialIntegrationError,match='权利|匹配|已接受'):
        ProductionAuthoringIntegration().prepare(current)
    # The old selection is preserved for evidence, but not re-authorized.
    assert json.loads(selection_path.read_text())['creator_material_choices']==choices
    assert store.read_asset(chosen.asset_id).rights.status is RightsStatus.UNKNOWN
    assert store.read_asset(good.asset_id).rights==backup_rights
    assert store.resolve_asset_locator(chosen.file.path).read_bytes()==source_bytes
    assert store.resolve_asset_locator(good.file.path).read_bytes()==bytes_good
    assert PlanningIntegration().load(current)['plan']==plan
    assert current['build']['operation'] is None
    assert not store.list_generation_records()


def test_u2a_current_frozen_director_shot_choice_reaches_normal_authoring(
        material_integration_env, monkeypatch):
    """P0-C: optional Director shot choice crosses current Recovery -> Selection.

    Only the external recovery search wording is offline; the confirmed @4
    Proposal, vNext frozen Need, real Supply checkpoint and Native selection
    projection all belong to the current Creation/Attempt Owners.
    """
    from copy import deepcopy
    from tests import test_semantic_planning as semantic_fixture
    from tests.material_delta_fixture import observed_result
    from easel.integrations import material_recovery as recovery
    from easel.integrations.hypit.handoff import load_frozen_creative_mode
    preferred='优先用中近景看清两张白纸，必要时保持桌面留白。'
    mode_path=creative_mode.CREATIVE_MODES_DIR/'clear_memo_video/mode.json'
    mode=json.loads(mode_path.read_text())
    mode_path.write_text(json.dumps({
        **mode,'visual_material_style':'soft low-key documentary'}))
    native_proposal=semantic_fixture.vnext_proposal
    def frozen_choice_proposal():
        proposal=deepcopy(native_proposal())
        proposal['needs'][0]['conditions'].append({
            'text':preferred,'strength':'preference','responsibility':'material'})
        return proposal
    monkeypatch.setattr(semantic_fixture,'vnext_proposal',frozen_choice_proposal)
    work,attempt,planning,store,asset=_u2a_current_shared_visual_asset(
        material_integration_env,monkeypatch,material_only=False)
    plan=planning['plan']
    assert plan.needs[0].constraints['preferred_visual_details']==preferred
    assert load_frozen_creative_mode(attempt)[0]['visual_material_style']=='soft low-key documentary'
    model_requests=[]
    def only_offline_recovery(current,record):
        model_requests.append(record['request_id'])
        assert record['shot_choice_need_ids']==[plan.needs[0].need_id]
        return {'request_id':record['request_id'],
                'search_terms':{n['need_id']: ['two distinct white papers on desktop'
                    if n['need_id']==plan.needs[0].need_id else 'blue desk notebook photograph']
                    for n in record['needs']},
                'shot_choices':{plan.needs[0].need_id:{
                    'expression':'优先保留冻结两张白纸主体，镜头近景按素材能力调整。',
                    'reason':'仅在柔和画面偏好中调整构图，不改变核心主体。'}}}
    saved=recovery.recover_managed_materials(attempt['attempt_id'],
                                            executor=only_offline_recovery)
    assert model_requests and saved['autonomous_material_recovery']['status']=='COMPLETE'
    decisions=recovery.director_shot_choices(saved,plan)
    assert list(decisions)==[plan.needs[0].need_id]
    assert decisions[plan.needs[0].need_id]['optional_details']==preferred
    assert decisions[plan.needs[0].need_id]['core_requirement']==plan.needs[0].intent.description
    assert PlanningIntegration().load(saved)['plan']==plan
    assert any(a.asset_id==asset.asset_id for a in store.read_bundle().assets)

    calls=[]
    def pixels(current,manifest,attachments):
        if 'observations' in manifest:
            calls.extend((item['need']['need_id'],item['asset_id'])
                         for item in manifest['observations'])
        else:
            calls.append((manifest['need']['need_id'],manifest['asset_id']))
        return observed_result(current,manifest,attachments,
            outcome='suitable',description='two white pages and blue notebook')
    latest=MaterialProductOrchestrator().observe_visual_materials(
        attempt['attempt_id'],executor=pixels,group_executor=pixels)
    assert latest['material_status']=='MATERIAL_READY'
    state=service.get_film_attempt(attempt['attempt_id'])
    assert state['production_authoring']['status']=='PENDING_SELECTION'
    selection=json.loads((store.attempt_root/'productions/easel-authoring/material-selection.json').read_text())
    assert selection['director_shot_choices']==decisions
    assert selection['director_shot_choices'][plan.needs[0].need_id]['core_requirement']==plan.needs[0].intent.description
    assert PlanningIntegration().load(state)['plan']==plan
    assert store.read_asset(asset.asset_id).rights==asset.rights
    assert state['build']['operation'] is None
    assert not store.list_generation_records()


@pytest.mark.parametrize('legacy_stage', ['director_plan','storyboard','assets','assemble','qc'])
def test_u2a_current_video_old_stage_writer_cannot_bypass_newonly(
        material_integration_env, monkeypatch, legacy_stage):
    """R1: real @4/Consent@3/vNext; old video stages cannot write Creation.

    A *real* isolated artifact proves the old Writer is rejected even when it
    could otherwise pass its file check. An invalid path is separately tested
    to verify the retired-route rejection takes precedence.
    """
    work,attempt,planning,_=_current_budgeted_visual_fixture(
        material_integration_env,monkeypatch,False)
    assert planning['manifest']['schema']=='easel-material-planning@3'
    current=creation.get_creation(work['id'])
    assert current['stages']['content_core']['status']=='completed'
    # Preparation and Handoff already wrote content_core using the legitimate
    # signed frozen snapshot; this proof is not re-created by a test Writer.
    frozen_content=current['stages']['content_core'].copy()
    probe=creation.OUTPUTS_DIR/work['workspace']/'retired-stage-probe.txt'
    probe.write_bytes(b'original local test bytes; not a Hypit production artifact')
    relative=probe.relative_to(creation.OUTPUTS_DIR).as_posix()
    creation_bytes=creation._creation_path(work['id']).read_bytes()
    attempt_before=service.get_film_attempt(attempt['attempt_id'])
    for status in ('in_progress','completed','blocked'):
        inputs=(relative,'will-not-exist') if status=='completed' else (None,)
        for path in inputs:
            kwargs=({'artifacts':[path]} if path else {})
            if legacy_stage=='qc' and status=='completed':
                kwargs['decision']='ready'
            with pytest.raises(creation.CreationError,match='旧视频阶段 Writer 已退役'):
                creation.record_stage(work['id'],legacy_stage,status,**kwargs)
            assert creation._creation_path(work['id']).read_bytes()==creation_bytes
            assert creation.get_creation(work['id'])['stages']['content_core']==frozen_content
            assert probe.read_bytes()==b'original local test bytes; not a Hypit production artifact'
    # Context, too, must not expose the retired stage-specific Producer for
    # current video even when content_core is already completed.
    with pytest.raises(creation.CreationError,match='旧视频阶段 Context 已退役'):
        creation.stage_context(work['id'],'director_plan')
    assert creation._creation_path(work['id']).read_bytes()==creation_bytes
    assert service.get_film_attempt(attempt['attempt_id'])==attempt_before
    assert attempt_before['build']['operation'] is None


@pytest.mark.parametrize('verdict,known_rights,fault', [
    ('unsuitable', True, 'syntax'),
    ('suitable', True, 'missing'),
    ('suitable', False, None),
    ('uncertain', True, 'duplicate'),
    ('unsuitable', True, 'persistent'),
    ('suitable', True, 'silent_compile'),
])
def test_u2a_current_two_scene_observation_reuses_first_evidence_after_fault(
        material_integration_env, monkeypatch, verdict, known_rights, fault):
    """Current #09: frozen per-Need pixel result, interrupted shared report & Gate.

    External classifications and frame judgments are deterministic wire-test
    replies, not assertions of image-model accuracy. This checks the real
    source-bound output receipt and Owner/Gate semantics.
    """
    from easel.creation_delivery import DeliveryExecutionUncertain
    from easel.materials.application.visual_observation import (
        GROUP_SCHEMA, observed_match)
    from tests.material_delta_fixture import observed_result

    work, attempt, planning, store, asset = _u2a_current_shared_visual_asset(
        material_integration_env, monkeypatch, known_rights=known_rights)
    needs=[n for n in planning['plan'].needs if n.media_type is MediaType.IMAGE]
    first,second=needs
    delivered, invoked=[], []
    fault_once=[False]
    def process_one(current, item, attachments):
        nid=item['need']['need_id']
        assert nid in {first.need_id,second.need_id}
        assert item['asset_id']==asset.asset_id
        outcome='suitable' if nid==first.need_id else verdict
        report=observed_result(current,item,attachments,
            outcome=outcome, description='two white papers beside blue notebook',
            invocations=invoked)
        delivered.append((nid,item['input_sha256']))
        return report
    def observer(current, manifest, attachments):
        if manifest.get('schema') == GROUP_SCHEMA:
            if fault == 'persistent':
                # Never return a valid child report in the deterministically
                # broken case: recovery must not silently invent one.
                return {'schema':GROUP_SCHEMA,
                    'input_sha256':manifest['input_sha256'],'reports':{}}
            reports={}
            for item in manifest['observations']:
                # The frozen group can survive partial local child persistence.
                reports[item['need']['need_id']]=process_one(current,item,attachments)
            if not fault_once[0] and fault is not None:
                fault_once[0]=True
                if fault == 'missing':
                    return {'schema':GROUP_SCHEMA,
                        'input_sha256':manifest['input_sha256'],'reports':{
                            first.need_id:reports[first.need_id]}}
                if fault == 'duplicate':
                    return {'schema':GROUP_SCHEMA,
                        'input_sha256':manifest['input_sha256'],
                        'reports':{**reports,'invalid-other-need':reports[first.need_id]}}
                if fault == 'syntax':
                    return {'invalid':'truncated-model-group'}
                # Current frozen vNext Planning does not recompile requirements.
                # Silence is a report-level refusal, not permission to replace
                # an approved Need or reinterpret its source requirements.
                if fault == 'silent_compile':
                    return None
            if fault is None and not fault_once[0]:
                fault_once[0]=True
                raise DeliveryExecutionUncertain('offline pending group after saved child')
            return {'schema':GROUP_SCHEMA,
                'input_sha256':manifest['input_sha256'],'reports':reports}
        return process_one(current,manifest,attachments)

    owner=MaterialProductOrchestrator()
    first_before=store.read_asset(asset.asset_id)
    assert first_before.rights.status == (RightsStatus.KNOWN if known_rights else RightsStatus.UNKNOWN)
    if fault is None:
        with pytest.raises(DeliveryExecutionUncertain):
            owner.observe_visual_materials(
                attempt['attempt_id'], executor=observer, group_executor=observer)
    elif fault is not None:
        with pytest.raises((ValueError,TypeError,MaterialIntegrationError)):
            owner.observe_visual_materials(
                attempt['attempt_id'],executor=observer,group_executor=observer)
    # No failure may write a fabricated qualified bundle or erase original SHA/Rights.
    assert store.read_asset(asset.asset_id).file == asset.file
    assert store.read_asset(asset.asset_id).rights == asset.rights
    result = None
    if fault == 'persistent':
        with pytest.raises((ValueError,TypeError,MaterialIntegrationError)):
            owner.observe_visual_materials(
                attempt['attempt_id'],executor=observer,group_executor=observer)
        assert service.get_film_attempt(attempt['attempt_id'])['material_gate']['status']=='MATERIAL_NOT_READY'
        return
    for _ in range(3):
        result=owner.observe_visual_materials(
            attempt['attempt_id'], executor=observer,group_executor=observer)
        if result['material_status']=='MATERIAL_READY':
            break
    assert result is not None
    expected='MATERIAL_READY' if known_rights and verdict=='suitable' else 'MATERIAL_NOT_READY'
    assert result['material_status']==expected
    assert observed_match(first,store.read_asset(asset.asset_id)) is True
    assert observed_match(second,store.read_asset(asset.asset_id)) is (verdict=='suitable')
    before_calls=len(invoked)
    owner.observe_visual_materials(attempt['attempt_id'],
        executor=observer,group_executor=observer)
    assert len(invoked)==before_calls
    assert not service.get_film_attempt(attempt['attempt_id'])['build']['operation']


@pytest.mark.parametrize('crash_after', ['received_bytes', 'bundle_commit'])
def test_u2a_current_image_paid_receipt_and_gate_cold_resume_uses_original_bundle(
        material_integration_env, monkeypatch, crash_after):
    """#04 closure: one real @4 paid-image receipt, cold replay and Rights Gate.

    Only the MiniMax HTTP image response and pricing documents are fake.
    An opaque completed byte receipt survives each crash. The Owner resumes
    the original Need and Bundle without loading credentials or paying again.
    """
    from io import BytesIO
    from PIL import ImageDraw
    from easel.creation_delivery import active_delivery
    from easel.integrations import material_generation as paid, material_layer
    from easel.materials.application import generation_modalities
    from easel.materials.providers import minimax_pricing
    from easel.materials import providers
    from easel.materials.providers.minimax_image import MiniMaxImageResult
    from easel.runtime_config import EaselRuntimeConfig
    from tests.test_minimax_image_speech_generation import MINIMAX_TERMS_FIXTURE
    from tests.material_delta_fixture import observed_result

    work, attempt, planning, _ = _current_budgeted_visual_fixture(
        material_integration_env, monkeypatch, True)
    original = PlanningIntegration().load(attempt)['plan']
    assert original == planning['plan']
    owner = MaterialProductOrchestrator()
    owner.observe_visual_materials(attempt['attempt_id'],
        executor=lambda *_: pytest.fail('there is no stock to review'))
    attempt = service.get_film_attempt(attempt['attempt_id'])
    store = AttemptMaterialStore(attempt['workspace']['path'])
    frozen_bundle = store.read_bundle()
    frozen_gate = dict(attempt['material_gate'])
    need, request = paid.pending_generated_need(
        creation.get_creation(work['id']), attempt, original)
    assert need.need_id == original.needs[0].need_id
    assert frozen_gate['bundle_revision'] == frozen_bundle.revision

    picture = Image.new('RGB',(720,1280),(80,92,105))
    brush = ImageDraw.Draw(picture)
    brush.rectangle((60,220,308,844),fill=(248,247,244))
    brush.rectangle((391,248,665,871),fill=(246,248,248))
    output=BytesIO(); picture.save(output,format='PNG')
    pixel_bytes=output.getvalue()
    calls=[]
    class PaidBoundaryIsFixture:
        def __init__(self,key,**kwargs):
            assert key=='offline-fixture-key'
            self.model=kwargs['model']
        def generate(self,prompt,*,aspect_ratio):
            ledger=creation.get_creation(work['id'])['delivery']['material_generations']
            assert ledger[request]['status']=='reserved'
            calls.append(prompt)
            assert len(calls)==1, 'generation cannot reissue'
            return MiniMaxImageResult(self.model,pixel_bytes)
    monkeypatch.setattr(providers,'MiniMaxImageAdapter',PaidBoundaryIsFixture)
    def price(url):
        if url == minimax_pricing.TERMS_URL:
            return MINIMAX_TERMS_FIXTURE
        return ('## 图像\n单价：元/张\n| image-01 | 图片 | 0.025 |\n'
            '## 视频\n**视频生成-输出价格**\n'
            '| MiniMax-H3-Max | 480P | 按秒计费 | 0.33 元/秒 |\n')
    monkeypatch.setattr(minimax_pricing,'read_public_contract',price)
    monkeypatch.setattr(material_supply_module.ProductMaterialSupply,'run',
        lambda *_args,**_kw: pytest.fail('already supplied; no source re-search'))
    token=active_delivery.set(work['id'])
    try:
        with monkeypatch.context() as damaged:
            if crash_after=='received_bytes':
                inspector=generation_modalities.TechnicalInspector
                damaged.setattr(inspector,'inspect_and_persist',
                    lambda *_: (_ for _ in ()).throw(OSError('fixture failed after received image bytes')))
                match='received image bytes'
            else:
                damaged.setattr(material_layer,'_update_attempt',
                    lambda *_a,**_kw: (_ for _ in ()).throw(OSError('fixture failed after Bundle committed')))
                match='Bundle committed'
            with pytest.raises(OSError,match=match):
                paid.generate_for_commission(attempt['attempt_id'])
        saved=store.read_generation_record('gen-'+request)
        assert saved['received_asset']['file']['sha256']==hashlib.sha256(pixel_bytes).hexdigest()
        assert saved['status'] == ('RESULT_INTAKE_FAILED' if crash_after=='received_bytes' else 'COMPLETE')
        assert len(calls)==1
        assert store.read_bundle().bundle_id==frozen_bundle.bundle_id
        if crash_after=='received_bytes':
            assert store.read_bundle()==frozen_bundle
        with monkeypatch.context() as offline:
            offline.setattr(EaselRuntimeConfig,'load',classmethod(
                lambda cls,**_kw: pytest.fail('resumed intake may not load provider config')))
            resumed=owner.resume_minimax_intake(attempt['attempt_id'])
        assert resumed['material_gate']['status']=='MATERIAL_NOT_READY'
        assert resumed['generation']['asset_sha256']==hashlib.sha256(pixel_bytes).hexdigest()
        latest=store.read_generation_record('gen-'+request)
        assert latest['status']=='COMPLETE'
        bundle=store.read_bundle()
        assert bundle.plan_id == original.plan_id
        assert bundle.bundle_id == frozen_bundle.bundle_id
        assert store.read_supply_run(bundle.supply_run_id).parent_run_id == frozen_bundle.supply_run_id
        assert {a.asset_id for a in frozen_bundle.assets} <= {a.asset_id for a in bundle.assets}
        for old in frozen_bundle.assets:
            assert store.read_asset(old.asset_id)==old
        asset=store.read_asset(latest['asset_id'])
        assert asset.file.sha256==hashlib.sha256(pixel_bytes).hexdigest()
        assert store.resolve_asset_locator(asset.file.path).read_bytes()==pixel_bytes
        assert asset.source.provider=='minimax' and asset.source.provider_asset_id=='gen-'+request
        assert asset.rights.status is RightsStatus.UNKNOWN
        assert latest['billing']['status']=='UNKNOWN'
        assert PlanningIntegration().load(service.get_film_attempt(attempt['attempt_id']))['plan']==original
        assert len(calls)==1
        assert not service.get_film_attempt(attempt['attempt_id'])['build']['operation']
        results=owner.generated_material_rights_candidates(attempt['attempt_id'])
        assert [v['asset_id'] for v in results] == [asset.asset_id]

        def observe(current,manifest,attachments):
            assert manifest['asset_id']==asset.asset_id
            return observed_result(current,manifest,attachments,
                outcome='suitable',description='two white sheets on a desk')
        owner.observe_visual_materials(attempt['attempt_id'],executor=observe)
        assert store.read_asset(asset.asset_id).rights.status is RightsStatus.UNKNOWN
        with pytest.raises(MaterialIntegrationError,match='SHA-256'):
            owner.review_generated_material_rights(
                attempt['attempt_id'],asset_id=asset.asset_id,
                expected_sha256='0'*64,
                rights=RightsInfo(status=RightsStatus.KNOWN,
                    evidence=(RightsEvidence(kind='asset_license',reference='fixture://own-image'),)),
                confirm_review=True)
        reviewed=owner.review_generated_material_rights(
            attempt['attempt_id'],asset_id=asset.asset_id,
            expected_sha256=asset.file.sha256, confirm_review=True,
            rights=RightsInfo(status=RightsStatus.KNOWN,
                license_name='Self-produced PNG offline test only',
                evidence=(RightsEvidence(kind='asset_license',
                    reference='fixture://own-image',summary='Test-owned synthetic pixels'),)),
            source_creator='Fixture-Pixel-Owner',
            source_page='https://fixture.example/local-image')
        assert reviewed['material_status']=='MATERIAL_READY'
        assert reviewed['production_authoring']['status']=='PENDING_SELECTION'
        retained=store.read_asset(asset.asset_id)
        assert retained.file==asset.file and retained.source.creator=='Fixture-Pixel-Owner'
        assert retained.source.source_page=='https://fixture.example/local-image'
        assert retained.rights.status is RightsStatus.KNOWN
        assert len(calls)==1
        assert not service.get_film_attempt(attempt['attempt_id'])['build']['operation']
    finally:
        active_delivery.reset(token)


def _u2a_current_video_budgeted_fixture(material_integration_env, monkeypatch, *,
                                        allowed=("video",), max_cost=2):
    """Freeze a 5s dynamic-action Need under @4; no hand-built Plan/authorization."""
    from dataclasses import replace
    from easel.runtime_config import EaselRuntimeConfig, MiniMaxRuntimeConfig
    from easel.integrations import material_generation as paid
    from easel import creation_preparation as preparation
    from tests.test_creation_preparation import (
        VIDEO_PROPOSAL, write_drafts, _current_vnext_planning_executor)

    original = EaselRuntimeConfig.load()
    settings = MiniMaxRuntimeConfig(api_key="offline-fixture-key")
    local_empty = Path(material_integration_env["workspace"]["path"]) / 'empty-moving-shot'
    local_empty.mkdir(exist_ok=True)
    runtime = replace(original, minimax=settings,
        material=replace(original.material, local_roots=(str(local_empty),)))
    monkeypatch.setattr(EaselRuntimeConfig, 'load',
                        classmethod(lambda cls, **kwargs: runtime))
    proposal = VIDEO_PROPOSAL.replace(
        "0–15 秒：桌面两张白纸，呈现后期叠加的屏幕文案「先看问题，再做决定。」。",
        "0–5 秒：镜头从桌面右侧连续平移到左侧，两张白纸始终清晰可见；"
        "后期叠加屏幕文案「先看问题，再做决定。」。")
    proposal = proposal.replace('时长：15 秒','时长：5 秒').replace(
        '不露脸。', '不露脸。已同意缺少合法运动镜头时按预算生成一个 5 秒纯视觉运动镜头。')
    work = creation.create_creation(
        "明确预算的真实桌面平移镜头", profile=None,
        creative_mode="clear_memo_video", route="hypit_video",
        origin={"type":"chat","session_hash":hashlib.sha256(
            ("video-generation-" + ','.join(allowed)).encode()).hexdigest()})
    turn = 'video-five-seconds-consent'
    creation.begin_video_proposal(work['id'], turn)
    staged = creation.save_video_proposal(work['id'], turn, proposal)
    plan = staged['chat_workflow']['video_plan']
    assert plan['schema'] == 'easel-video-proposal@4'
    assert plan['specs']['duration_seconds'] == 5
    scope = paid.generation_budget_preview()
    assert scope['available']
    budget = {'maxCostCny': max_cost, 'scopeSha256':scope['scope_sha256'],
              'allowedModalities':list(allowed)}
    transcript = json.dumps([{'role':'assistant','content': proposal}],
                            ensure_ascii=False, separators=(',',':'))
    work = creation.confirm_chat_proposal(
        work['id'], turn, delivery_proposal=transcript,
        proposal_sha256=hashlib.sha256(transcript.encode()).hexdigest(),
        production_specs=plan['specs'], video_plan_sha256=plan['sha256'],
        generation_budget=budget,
        input_use_statement_sha256=creation.input_use_preview(plan=plan)['statement_sha256'])
    assert work['delivery']['authorization']['material_generation']['allowed_modalities'] == sorted(allowed)
    claim = preparation.claim_chat_preparation(work['id'], 'video-motion-fixture-session',turn)
    paths = preparation.preparation_paths(work['id'],claim['operation_key'])
    write_drafts(work, paths['draft'])
    brief_file = paths['draft'] / 'production-brief.json'
    brief = json.loads(brief_file.read_text(encoding='utf-8'))
    brief.update(duration_seconds=5, ai_generation_allowed=True)
    brief_file.write_text(json.dumps(brief,ensure_ascii=False),encoding='utf-8')
    prepared = preparation.prepare_creation_for_hypit(
        work['id'],runtime_profile=None,planning_executor=_current_vnext_planning_executor)
    attempt = service.get_film_attempt(prepared['attempt_id'])
    current = PlanningIntegration().load(attempt)
    assert current['truth_ledger']['status'] == 'PASSED'
    visual = [n for n in current['plan'].needs if n.media_type is MediaType.VIDEO]
    assert len(visual) == 1, [(n.role,n.media_type) for n in current['plan'].needs]
    assert visual[0].constraints.get('allow_generation') is True
    assert visual[0].constraints.get('requires_dynamic_action') is True
    assert not any(n.media_type is MediaType.IMAGE for n in current['plan'].needs)
    assert attempt['material_gate']['status']=='MATERIAL_NOT_READY'
    assert attempt['build']['operation'] is None
    return work, attempt, current, settings


def test_u2a_current_video_commission_freezes_dynamic_visual_and_budget(
        material_integration_env, monkeypatch):
    work, attempt, current, settings = _u2a_current_video_budgeted_fixture(
        material_integration_env, monkeypatch)
    from easel.integrations import material_generation as paid
    need, request = paid.pending_generated_need(
        creation.get_creation(work['id']), attempt, current['plan'])
    assert need.media_type is MediaType.VIDEO
    assert need.duration_hint is not None
    assert request.startswith('delivery-')
    assert not creation.get_creation(work['id'])['delivery'].get('material_generations')



@pytest.mark.parametrize('outcome', [
    'pending_then_received', 'task_failed', 'intake_crash',
    'submission_unknown',
])
def test_u2a_current_video_generation_reservation_task_recovery_no_repurchase(
        material_integration_env, monkeypatch, outcome):
    """Real vNext Video Need + current cost/Owner; fake paid adapter and CDN only.

    Executable FFmpeg output is local and SHA-bound. Nothing here calls the
    paid Provider, models, Hypit Build or real media rights providers.
    """
    from easel.integrations import material_generation as commissioned
    from easel.materials.providers import minimax_pricing
    from easel.materials import providers
    from easel.materials.providers.minimax_video import (
        MiniMaxVideoError, MiniMaxVideoObservationPending, MiniMaxVideoTask)
    from easel.materials.application import generation as video_generation
    from easel.materials.application import generation_modalities
    from easel.creation_delivery import active_delivery, DeliveryObservationPending
    from tests.test_minimax_image_speech_generation import MINIMAX_TERMS_FIXTURE
    import subprocess

    work, attempt, planning, settings = _u2a_current_video_budgeted_fixture(
        material_integration_env, monkeypatch)
    need = next(n for n in planning['plan'].needs if n.media_type is MediaType.VIDEO)
    request = commissioned.pending_generated_need(
        creation.get_creation(work['id']),attempt, planning['plan'])[1]
    quote_calls = []
    def official_contract_fixture(url):
        quote_calls.append(url)
        if url == minimax_pricing.TERMS_URL:
            return MINIMAX_TERMS_FIXTURE
        return ('## 图像\n单价：元/张\n| image-01 | 图片 | 0.025 |\n'
                '## 视频\n**视频生成-输出价格**\n'
                '| MiniMax-H3-Max | 480P | 按秒计费 | 0.33 元/秒 |\n')
    monkeypatch.setattr(minimax_pricing, 'read_public_contract', official_contract_fixture)

    owner_events, poll_calls, upload_calls = [], [], []
    task_id = 'fixture-video-paid-task'
    class FixedVideoAdapter:
        def __init__(self, key, **kwargs):
            assert key == 'offline-fixture-key'
            self.model = kwargs['model']
        def submit(self, prompt, *, duration_seconds, resolution, ratio):
            receipt = creation.get_creation(work['id'])['delivery']['material_generations'][request]
            assert receipt['status'] == 'reserved'
            assert receipt['quote']['upper_estimate'] == '1.650000'
            assert (duration_seconds, resolution, ratio) == (5, '480P', '9:16')
            owner_events.append(prompt)
            if outcome == 'submission_unknown':
                raise MiniMaxVideoError('offline submit connection lost', submission_uncertain=True)
            return MiniMaxVideoTask(task_id, self.model, 'queued')
        def wait(self, submitted_id):
            assert submitted_id == task_id
            poll_calls.append(submitted_id)
            if outcome == 'pending_then_received' and len(poll_calls) == 1:
                raise MiniMaxVideoObservationPending('offline queued', task_status='queued')
            if outcome == 'task_failed':
                raise MiniMaxVideoError('offline video task failed')
            return MiniMaxVideoTask(task_id, self.model,'succeeded',
                video_url='https://cdn.hailuoai.com/fixture-video.mp4',duration_seconds=5)

    video_path = Path(attempt['workspace']['path'])/'five-second-portrait-clip.mp4'
    subprocess.run(['ffmpeg','-v','error','-nostdin','-y','-f','lavfi',
        '-i','color=c=teal:s=90x160:r=10:d=5','-an','-c:v','libx264',
        str(video_path)],capture_output=True, check=True,timeout=35)
    pixels = video_path.read_bytes()
    assert pixels and len(pixels) > 300
    class OfflineAcquirer:
        def __init__(self, store):
            self.store = store
        def acquire(self, candidate):
            upload_calls.append(candidate.acquisition.locator)
            assert candidate.need_id == need.need_id
            assert candidate.source.provider == 'minimax'
            asset_id = 'asset-' + hashlib.sha256(request.encode()).hexdigest()[:32]
            path = self.store.write_asset_bytes(asset_id,'original.mp4',pixels)
            asset = MaterialAsset(asset_id=asset_id, media_type=MediaType.VIDEO,
                file=FileInfo(path=path, sha256=hashlib.sha256(pixels).hexdigest(),
                              size=len(pixels), mime='video/mp4'),
                source=candidate.source, rights=RightsInfo(status=RightsStatus.UNKNOWN),
                technical=TechnicalInfo(status=TechnicalStatus.PENDING))
            self.store.write_asset(asset)
            return asset

    monkeypatch.setattr(providers,'MiniMaxVideoAdapter',FixedVideoAdapter)
    monkeypatch.setattr(video_generation,'create_material_generation_acquirer',OfflineAcquirer)

    if outcome == 'intake_crash':
        native = video_generation.TechnicalInspector
        class CrashOnceInspector(native):
            touches = 0
            def inspect_and_persist(self, asset):
                type(self).touches += 1
                if self.touches == 1:
                    raise OSError('offline inspector interrupted after receipt')
                return super().inspect_and_persist(asset)
        monkeypatch.setattr(video_generation,'TechnicalInspector',CrashOnceInspector)
    with pytest.raises(creation.CreationError, match='后台交付者'):
        commissioned.generate_for_commission(attempt['attempt_id'])
    token = active_delivery.set(work['id'])
    try:
        if outcome == 'pending_then_received':
            with pytest.raises(DeliveryObservationPending):
                commissioned.generate_for_commission(attempt['attempt_id'])
            before = AttemptMaterialStore(attempt['workspace']['path']).list_generation_records()[0]
            assert before['status']=='RUNNING' and before['task_id']==task_id
            assert len(owner_events)==1 and len(poll_calls)==1 and not upload_calls
            commissioned.generate_for_commission(attempt['attempt_id'])
            commissioned.generate_for_commission(attempt['attempt_id'])
        elif outcome == 'task_failed':
            for _ in range(2):
                with pytest.raises(MiniMaxVideoError, match='failed'):
                    commissioned.generate_for_commission(attempt['attempt_id'])
        elif outcome == 'submission_unknown':
            commissioned.generate_for_commission(attempt['attempt_id'])
            commissioned.generate_for_commission(attempt['attempt_id'])
        else:
            with pytest.raises(OSError, match='inspector interrupted'):
                commissioned.generate_for_commission(attempt['attempt_id'])
            receipt = AttemptMaterialStore(attempt['workspace']['path']).list_generation_records()[0]
            assert receipt['status']=='RESULT_INTAKE_FAILED' and receipt['received_asset']
            # Offline-only intake: never read credentials or poll the Provider.
            with monkeypatch.context() as disallowed:
                from easel.runtime_config import EaselRuntimeConfig
                disallowed.setattr(EaselRuntimeConfig,'load',classmethod(
                    lambda cls, **kwargs: pytest.fail('cold receipt must not reload credentials')))
                MaterialProductOrchestrator().resume_minimax_intake(attempt['attempt_id'])
    finally:
        active_delivery.reset(token)
    saved = creation.get_creation(work['id'])
    receipt = saved['delivery'].get('material_generations',{}).get(request,{})
    records = AttemptMaterialStore(attempt['workspace']['path']).list_generation_records()
    assert len(records)==1
    stored = records[0]
    assert len(owner_events)==1
    assert len(poll_calls)==(2 if outcome in {'pending_then_received','task_failed'} else
                             1 if outcome == 'intake_crash' else 0)
    if outcome == 'submission_unknown':
        assert stored['status']=='SUBMISSION_UNCERTAIN' and receipt['status']=='uncertain'
        assert not upload_calls
    elif outcome == 'task_failed':
        assert stored['status']=='RESULT_FAILED' and stored['task_id']==task_id
        assert receipt['status']=='reserved' and not upload_calls
    else:
        assert stored['status']=='COMPLETE'
        assert stored['task_id']==task_id
        assert len(upload_calls)==1
        asset = AttemptMaterialStore(attempt['workspace']['path']).read_asset(stored['asset_id'])
        assert asset.file.sha256 == hashlib.sha256(pixels).hexdigest()
        assert asset.rights.status is RightsStatus.UNKNOWN
        assert asset.technical.status is TechnicalStatus.PASSED
        assert asset.source.provider_asset_id == task_id
        assert service.get_film_attempt(attempt['attempt_id'])['material_gate']['status']=='MATERIAL_NOT_READY'
    assert len(quote_calls)==2
    assert service.get_film_attempt(attempt['attempt_id'])['build']['operation'] is None
    assert not service.get_film_attempt(attempt['attempt_id']).get('production_authoring')


@pytest.mark.parametrize('tamper_source', [False, True], ids=['valid-source-rights-unknown', 'source-sha-tampered'])
def test_u2a_current_rights_only_visual_gap_cannot_research_or_generate(
        material_integration_env, monkeypatch, tamper_source):
    """#17 negative: complete pixel suitability without asset Rights is NOT a supply shortage.

    Both Needs and the original offline PNG belong to a genuine frozen
    Proposal@4/Consent@3/vNext Attempt. Real Material@3 captured visual
    suitability, but the local self-produced fixture has explicitly UNKNOWN
    Rights. Reopening source search cannot grant those missing rights.
    """
    from easel.integrations import material_recovery as recovery
    from easel.materials.application.visual_observation import observed_match
    from tests.material_delta_fixture import observed_result
    work, attempt, planning, store, asset = _u2a_current_shared_visual_asset(
        material_integration_env, monkeypatch, known_rights=False)
    def observed_pixels(current,manifest,attachments):
        return observed_result(current,manifest,attachments,
            outcome='suitable',description='two white paper sheets next to blue notebook')
    owner=MaterialProductOrchestrator()
    owner.observe_visual_materials(attempt['attempt_id'],
        executor=observed_pixels,group_executor=observed_pixels)
    latest=service.get_film_attempt(attempt['attempt_id'])
    recorded=store.read_asset(asset.asset_id)
    assert recorded.rights.status is RightsStatus.UNKNOWN
    assert all(observed_match(n,recorded) is True for n in planning['plan'].needs)
    assert latest['material_observation']['status']=='COMPLETE'
    assert latest['material_gate']['status']=='MATERIAL_NOT_READY'
    frozen_gate=latest['material_gate'].copy()
    frozen_bytes=store.resolve_asset_locator(recorded.file.path).read_bytes()
    frozen_bundle=store.read_bundle()
    frozen_creator=creation.get_creation(work['id'])
    def no_provider(*_a,**_kw):
        pytest.fail('Rights-only shortage cannot trigger supplemental Provider or model')
    monkeypatch.setattr(recovery.ProductMaterialSupply,'run',no_provider)
    monkeypatch.setattr(MaterialProductOrchestrator,'generate_minimax_asset',no_provider)
    location=store.resolve_asset_locator(recorded.file.path)
    if tamper_source:
        location.write_bytes(frozen_bytes+b'changed')
    try:
        if tamper_source:
            with pytest.raises(MaterialIntegrationError,match='素材字节|Rights 证据变化'):
                recovery.recover_managed_materials(
                    attempt['attempt_id'],executor=no_provider)
        else:
            refreshed=recovery.recover_managed_materials(
                attempt['attempt_id'],executor=no_provider)
            assert refreshed['material_gate']==frozen_gate
    finally:
        if tamper_source:
            location.write_bytes(frozen_bytes)
    assert service.get_film_attempt(attempt['attempt_id'])['material_gate']==frozen_gate
    assert store.read_asset(asset.asset_id)==recorded
    assert store.read_bundle()==frozen_bundle
    assert store.resolve_asset_locator(recorded.file.path).read_bytes()==frozen_bytes
    assert creation.get_creation(work['id'])==frozen_creator
    assert not store.list_generation_records()
    current=service.get_film_attempt(attempt['attempt_id'])
    assert not current.get('production_authoring')
    assert not current['build']['operation']


def test_u2a_current_autonomous_material_two_waves_reuse_committed_supply(
        material_integration_env, monkeypatch):
    """#17 New-Only: a proven gap, bounded supplemental waves, cold Gate replay.

    A real @4/Consent@3/Brief/vNext Need stays frozen. The sole external
    Provider registry is empty (explicit offline outage fixture); this proves
    safe idempotence/exhaustion, not actual search recall or selected quality.
    """
    from easel.integrations import material_recovery as recovery
    from easel.creation_delivery import active_delivery, is_managed, set_material_endpoint
    from easel.materials.application.readiness import MaterialReadinessCalculator
    work, attempt, planning, _ = _current_budgeted_visual_fixture(
        material_integration_env, monkeypatch, False)
    set_material_endpoint(work['id'])
    assert is_managed(creation.get_creation(work['id']))
    frozen_plan=planning['plan']
    frozen_script=planning['script']
    store=AttemptMaterialStore(attempt['workspace']['path'])
    MaterialProductOrchestrator().observe_visual_materials(
        attempt['attempt_id'],
        executor=lambda *_: pytest.fail('No stock was discovered; no pixel model call'))
    attempt=service.get_film_attempt(attempt['attempt_id'])
    original_bundle=store.read_bundle()
    assert not original_bundle.assets
    assert attempt['material_gate']['status']=='MATERIAL_NOT_READY'
    assert attempt['material_observation']['status']=='COMPLETE'
    frozen_creation=creation.get_creation(work['id'])
    original_auth=frozen_creation['delivery']['authorization']
    original_snapshots=frozen_creation['preparation']['snapshot_hashes']

    # The actual ProductSupply/Owner checkpoint code executes, but provider
    # discovery is empty; neither remote lookup nor paid fallback can occur.
    monkeypatch.setattr(material_supply_module,'product_provider_registry',
        lambda roots: (material_supply_module.ProviderRegistry(), ()))
    monkeypatch.setattr(MaterialProductOrchestrator,'generate_minimax_asset',
        lambda *_a,**_k: pytest.fail('No paid generation on supplemental search'))
    supplied=[]
    native_supply=recovery.ProductMaterialSupply.run
    def counted_supply(self,*args,**kwargs):
        supplied.append(kwargs['supply_run_id'])
        return native_supply(self,*args,**kwargs)
    monkeypatch.setattr(recovery.ProductMaterialSupply,'run',counted_supply)
    query_calls=[]
    def frozen_queries(current,request):
        query_calls.append(request['request_id'])
        round_n=len(query_calls)
        proposal={'request_id':request['request_id'],
            'search_terms':{need['need_id']:[
                f'overhead source material white paper no text variation {round_n}']
                for need in request['needs']}}
        if request.get('shot_choice_need_ids'):
            proposal['shot_choices']={nid:{
                'expression':'先保持冻结主体与自然景别','reason':'保留当前作品的纸面主体'}
                for nid in request['shot_choice_need_ids']}
        return proposal

    token=active_delivery.set(work['id'])
    try:
        crashed=[]
        native_gate=recovery.MaterialGateIntegration.record
        with monkeypatch.context() as transient:
            def interrupt_after_committed_source(self,current,plan,bundle,*a,**k):
                if bundle.supply_run_id.startswith('supplement-') and not crashed:
                    crashed.append(bundle.supply_run_id)
                    raise OSError('offline Gate interruption after Source commit')
                return native_gate(self,current,plan,bundle,*a,**k)
            transient.setattr(recovery.MaterialGateIntegration,'record',interrupt_after_committed_source)
            with pytest.raises(OSError,match='after Source commit'):
                recovery.recover_managed_materials(
                    attempt['attempt_id'],executor=frozen_queries)
        assert len(crashed)==1 and len(supplied)==1
        paused=service.get_film_attempt(attempt['attempt_id'])
        first_committed=store.read_bundle()
        assert first_committed.supply_run_id==crashed[0]
        assert first_committed.assets==original_bundle.assets
        first_query_calls=list(query_calls)
        # Reload via a fresh Owner entry. Original committed Supply/run is
        # reconciled, so neither the same search nor original model dispatch
        # is reissued.
        first=recovery.recover_managed_materials(
            attempt['attempt_id'],executor=frozen_queries)
        assert len(supplied)==1
        assert query_calls==first_query_calls
        assert first['material_gate']['status']=='MATERIAL_NOT_READY'
        assert recovery.visual_supply_recovery_state(first)=='available'
        assert store.read_bundle().plan_id==frozen_plan.plan_id
        second=recovery.recover_managed_materials(
            attempt['attempt_id'],executor=frozen_queries)
        assert len(supplied)==2
        assert len(set(supplied))==2
        assert second['material_gate']['status']=='MATERIAL_NOT_READY'
        assert recovery.visual_supply_recovery_state(second)=='exhausted'
        repeat=recovery.recover_managed_materials(
            attempt['attempt_id'],executor=lambda *_: pytest.fail('recovery budget is exhausted'))
        assert repeat==second
        assert len(supplied)==2
    finally:
        active_delivery.reset(token)
    for state in [paused,first,second]:
        assert state['build']['operation'] is None
        assert not state.get('production_authoring')
    latest=service.get_film_attempt(attempt['attempt_id'])
    saved=creation.get_creation(work['id'])
    assert saved['delivery']['authorization']==original_auth
    assert saved['preparation']['snapshot_hashes']==original_snapshots
    assert not saved['delivery'].get('material_generations')
    assert not store.list_generation_records()
    assert store.read_plan()==frozen_plan
    assert PlanningIntegration().load(latest)['script']==frozen_script
    assert store.read_bundle().assets==original_bundle.assets
    assert latest['material_gate']['status']=='MATERIAL_NOT_READY'
    assert latest['material_gate']['blocking_needs']
    assert len(latest['autonomous_material_recovery'].get('previous_rounds',[]))==1
    assert len(supplied)==2


def _assert_u2a_current_material_recovery_retains_generated_voice(
        material_integration_env, monkeypatch, interrupt_after_supply, automatic):
    """#08: current @4 Voice grant/actual frozen vNext Plan, no old hand Plan.

    Only the paid speech adapter is faked. ProductMaterialSupply.run is real
    but empty, and its one completed supplement must survive a Gate crash.
    """
    from easel.integrations import material_recovery as recovery
    from easel.creation_delivery import active_delivery
    work, attempt, planning, need, store, record, calls = _u2a_voice_saved_commission(
        material_integration_env, monkeypatch, provider_timing=False)
    old_plan = planning['plan']
    visual = next(n for n in old_plan.needs if n.media_type is MediaType.IMAGE)
    old_script = planning['script']
    original_asset = store.read_asset(record['asset_id'])
    original_bytes = store.resolve_asset_locator(original_asset.file.path).read_bytes()
    original_bundle = store.read_bundle()
    original_gate = attempt['material_gate']
    args = {'request_id':'u2a-current-recovery',
            'expected_plan_revision':original_gate['plan_revision'],
            'expected_bundle_revision':original_gate['bundle_revision'],
            'allow_licensed_bgm':False,
            'search_terms':{visual.need_id:('two white note pages overhead',)}}
    assert need.need_id in original_gate['blocking_needs']
    assert visual.need_id in original_gate['blocking_needs']
    assert any(a.asset_id == original_asset.asset_id for a in original_bundle.assets)
    assert record['input_sha256'] == hashlib.sha256(old_script.encode()).hexdigest()
    def registry(roots):
        return material_supply_module.ProviderRegistry(), ()
    monkeypatch.setattr(material_supply_module, 'product_provider_registry', registry)
    supplier_calls = []
    native_run = recovery.ProductMaterialSupply.run
    def counted_supply(self, *args, **kwargs):
        supplier_calls.append({'skip':kwargs.get('skip_need_ids'),
                               'search':kwargs.get('search_terms')})
        return native_run(self, *args, **kwargs)
    monkeypatch.setattr(recovery.ProductMaterialSupply, 'run', counted_supply)
    def closed_model(*args, **kwargs):
        pytest.fail('No external model, provider or TTS during material recovery')
    monkeypatch.setattr(MaterialProductOrchestrator, 'generate_minimax_asset', closed_model)
    query_calls = []
    def offline_recovery_queries(current_attempt, current_record):
        assert current_record['status'] == 'PLANNING'
        assert [n['need_id'] for n in current_record['needs']] == [visual.need_id]
        query_calls.append(current_record['request_id'])
        return {'request_id':current_record['request_id'],
                'search_terms':{visual.need_id:['two white note pages overhead']}}
    def invoke():
        if automatic:
            updated = recovery.recover_managed_materials(
                attempt['attempt_id'], executor=offline_recovery_queries)
            return {'attempt':updated,'material_status':updated['material_gate']['status']}
        return recovery.recover_materials(attempt['attempt_id'], **args)
    token = active_delivery.set(work['id'])
    try:
        with monkeypatch.context() as isolated:
            if interrupt_after_supply:
                original_record_gate = recovery.MaterialGateIntegration.record
                def crash_at_supplement_gate(self, current, source_plan, bundle, *others):
                    if bundle.supply_run_id.startswith('supplement-'):
                        raise RuntimeError('fixture crash after supplement')
                    return original_record_gate(self, current, source_plan, bundle, *others)
                isolated.setattr(recovery.MaterialGateIntegration, 'record', crash_at_supplement_gate)
                with pytest.raises(RuntimeError, match='crash after supplement'):
                    invoke()
        final = invoke()
    finally:
        active_delivery.reset(token)
    latest = service.get_film_attempt(attempt['attempt_id'])
    assert len(supplier_calls) == 1, supplier_calls
    assert supplier_calls[0]['skip'] == (need.need_id,)
    assert len(query_calls) == (1 if automatic else 0)
    assert latest['material_gate']['status']=='MATERIAL_NOT_READY'
    assert PlanningIntegration().load(latest)['plan'] == old_plan
    assert PlanningIntegration().load(latest)['script'] == old_script
    assert store.read_asset(original_asset.asset_id) == original_asset
    assert store.resolve_asset_locator(original_asset.file.path).read_bytes() == original_bytes
    assert store.read_generation_record(record['generation_id']) == record
    assert all(a.asset_id == original_asset.asset_id for a in store.read_bundle().assets
               if a.media_type is MediaType.AUDIO)
    assert not latest.get('production_authoring')
    assert not latest['build']['operation']
    assert len(calls)==1
    if not automatic:
        repeated = recovery.recover_materials(attempt['attempt_id'], **args)
        assert repeated['recovery']['status'] == 'COMPLETE'
        assert repeated['recovery']['reused'] is True
        assert len(supplier_calls) == 1
        with pytest.raises(MaterialIntegrationError, match='改变输入'):
            recovery.recover_materials(attempt['attempt_id'],
                **{**args,'search_terms':{visual.need_id:('unrelated footage',)}})
        with pytest.raises(MaterialIntegrationError, match='素材状态已变化'):
            recovery.recover_materials(attempt['attempt_id'],
                **{**args,'request_id':'another-after-supply'})
    assert PlanningIntegration().load(service.get_film_attempt(attempt['attempt_id']))['plan'] == old_plan


@pytest.mark.parametrize(('interrupt_after_supply','automatic'), [
    (False, False), (True, False), (True, True),
])
def test_u2a_current_generation_material_recovery_retains_voice_without_resupply(
        material_integration_env, monkeypatch, interrupt_after_supply, automatic):
    _assert_u2a_current_material_recovery_retains_generated_voice(
        material_integration_env, monkeypatch, interrupt_after_supply, automatic)


def test_u2a_newonly_material_recovery_cannot_loosen_frozen_bgm_license(
        material_integration_env):
    """New-Only confirmed BGM source kind is never edited by an old recovery toggle."""
    from easel.integrations import material_recovery as recovery
    work, attempt, planning, bgm = _u2a_current_music_attempt(material_integration_env, 15)
    store = AttemptMaterialStore(attempt['workspace']['path'])
    root = Path(attempt['workspace']['path'])
    refs = {name:(root/name).read_bytes() for name in (
        'planning/MATERIAL_PLAN.json','planning/manifest.json',
        'planning/SCRIPT.md','planning/MATERIAL_REQUIREMENTS.json')}
    old_attempt = service.get_film_attempt(attempt['attempt_id'])
    old_creator = creation.get_creation(work['id'])
    before = store.read_bundle()
    kwargs = {'request_id':'unapproved-bgm-source-relaxation',
        'expected_plan_revision':old_attempt['material_gate']['plan_revision'],
        'expected_bundle_revision':old_attempt['material_gate']['bundle_revision'],
        'allow_licensed_bgm':True,
        'search_terms':{bgm.need_id:('piano gentle instrumental',)}}
    with pytest.raises(MaterialIntegrationError, match='冻结 vNext 素材Need不能'):
        recovery.recover_materials(attempt['attempt_id'], **kwargs)
    assert store.read_recovery_record(kwargs['request_id']) is None
    assert store.read_plan() == planning['plan']
    assert store.read_bundle() == before
    assert service.get_film_attempt(attempt['attempt_id']) == old_attempt
    assert creation.get_creation(work['id']) == old_creator
    assert {name:(root/name).read_bytes() for name in refs} == refs
    assert not old_attempt.get('production_authoring') and not old_attempt['build']['operation']


def _u2a_current_music_attempt(material_integration_env, duration):
    """Build one legitimate New-Only music Creation, vNext Plan, and real Gate."""
    from tests.test_creation_preparation import (
        VIDEO_PROPOSAL, _confirm_current_video_plan,
        write_drafts, _current_vnext_planning_executor,
    )
    from easel import creation_preparation as preparation

    proposal = (VIDEO_PROPOSAL
        .replace("无旁白，无音乐。", "无旁白，纯音乐。使用轻柔无歌词的钢琴背景音乐。")
        .replace("音轨：静音", "音轨：纯音乐")
        .replace("时长：15 秒", f"时长：{duration} 秒")
        .replace("0–15 秒", f"0–{duration} 秒"))
    work = creation.create_creation(
        f"纯音乐长视频 {duration} 秒", profile=None, creative_mode="clear_memo_video",
        route="hypit_video",
        origin={"type":"chat","session_hash":hashlib.sha256(
            f"music-{duration}-newonly-fixture".encode()).hexdigest()})
    work = _confirm_current_video_plan(work, turn_id="music-confirm", proposal=proposal)
    assert work["delivery"]["video_plan"]["specs"]["audio_mode"] == "music"
    assert work["delivery"]["authorization"]["material_generation"] is None
    assert "preset_voice_synthesis" not in work["delivery"]["authorization"]["input_use"]["operations"]
    claim = preparation.claim_chat_preparation(work["id"], "music-fixture-session", "music-prepare")
    paths = preparation.preparation_paths(work["id"], claim["operation_key"])
    write_drafts(work, paths["draft"])
    brief_file = paths["draft"] / "production-brief.json"
    brief = json.loads(brief_file.read_text(encoding="utf-8"))
    brief.update(duration_seconds=duration, audio_mode="music", ai_generation_allowed=False)
    brief_file.write_text(json.dumps(brief, ensure_ascii=False), encoding="utf-8")
    prepared = preparation.prepare_creation_for_hypit(
        work["id"], runtime_profile=None, planning_executor=_current_vnext_planning_executor)
    attempt = service.get_film_attempt(prepared["attempt_id"])
    planned = PlanningIntegration().load(attempt)
    bgms = [n for n in planned["plan"].needs
            if getattr(n.modality_spec, "kind", None) == "bgm"]
    assert len(bgms) == 1 and bgms[0].importance is NeedImportance.REQUIRED
    assert bgms[0].media_type is MediaType.AUDIO
    assert bgms[0].constraints["required_source_kind"] == "stock"
    assert bgms[0].constraints["allow_generation"] is False
    assert not any(getattr(n.modality_spec,"kind",None) == "voice"
                   for n in planned["plan"].needs)
    assert attempt["material_gate"]["status"] == "MATERIAL_NOT_READY"
    assert bgms[0].need_id in attempt["material_gate"]["blocking_needs"]
    assert attempt["build"]["operation"] is None
    assert not creation.get_creation(work["id"])["delivery"].get("material_generations")
    return work, attempt, planned, bgms[0]


@pytest.mark.parametrize("duration", [15, 301, 900])
def test_u2a_current_music_commission_freezes_required_bgm_without_purchase(
        material_integration_env, duration):
    work, attempt, planned, bgm = _u2a_current_music_attempt(material_integration_env, duration)
    assert planned["plan"].needs[-1] == bgm
    assert attempt["build"]["operation"] is None



def _u2a_cached_bgm_fixture(material_integration_env, *, duration, vocal_score, openverse_item=None):
    """A legal @4 music Attempt with real WAV bytes and an offline old-policy report.

    The report is model-fixture evidence, NOT evidence of actual acoustic quality;
    the application Owner/Gate/rights and byte preservation remain real.
    """
    import io
    import math
    import wave
    from PIL import ImageDraw
    from easel.creation_delivery import set_material_endpoint
    from easel.materials.application import music_observation as music
    from easel.materials.application.music_reassessment import cached_music_reassessment
    from easel.materials.application.assembly import MaterialBundleAssembler
    from easel.integrations import material_results

    work, attempt, planning, bgm = _u2a_current_music_attempt(material_integration_env, duration)
    set_material_endpoint(work['id'])
    attempt = service.get_film_attempt(attempt['attempt_id'])
    store = AttemptMaterialStore(attempt['workspace']['path'])
    root = Path(attempt['workspace']['path'])
    frozen_plan = planning['plan']
    previous = store.read_bundle()
    # Complete local PCM evidence, not a mislabeled image or invented SHA.
    one_second = b''.join(int(3000 * math.sin(i * 2 * math.pi * 440 / 8000)).to_bytes(
        2, 'little', signed=True) for i in range(8000))
    sound = io.BytesIO()
    with wave.open(sound, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        for _ in range(duration):
            wav.writeframes(one_second)
    audio_bytes = sound.getvalue()
    identity = f'offline-bgm-{duration}'
    if openverse_item is not None:
        # A real OpenverseAudioProvider candidate and real Acquirer create the
        # original immutable audio and acquisition ledger. Only HTTP is fake.
        from easel.materials.providers.openverse import OpenverseAudioProvider
        from easel.materials.application.acquisition import (
            MaterialAcquirer, DownloadResponse, RemoteURLPolicy)
        candidate = OpenverseAudioProvider()._candidate(
            openverse_item, bgm.need_id, MediaType.AUDIO)
        assert candidate.source.provider == 'openverse_audio'
        assert candidate.acquisition is not None
        class OfflineDownload:
            def get(self, *_args, **_kwargs):
                return DownloadResponse(200, {'content-type': 'audio/wav'}, audio_bytes)
        acquired = MaterialAcquirer(
            store, transport=OfflineDownload(),
            url_policy=RemoteURLPolicy(lambda *_: ('93.184.216.34',))).acquire(candidate)
        assert acquired.file.sha256 == hashlib.sha256(audio_bytes).hexdigest()
        # Emulate the pre-existing item whose metadata was not saved, not a
        # newly authorized source. The original acquisition proof stays intact.
        audio_asset = acquired.model_copy(update={
            'rights': acquired.rights.model_copy(update={
                'evidence': (), 'attribution_text': None}),
            'technical': TechnicalInfo(status=TechnicalStatus.PASSED,
                duration_seconds=duration, mime='audio/wav'),
            'semantic': SemanticInfo()})
        assert audio_asset.rights.status == RightsStatus.ATTRIBUTION_REQUIRED
    else:
        locator = store.write_asset_bytes(identity, 'original.wav', audio_bytes)
        audio_asset = MaterialAsset(
            asset_id=identity, media_type=MediaType.AUDIO,
            file=FileInfo(path=locator, sha256=hashlib.sha256(audio_bytes).hexdigest(),
                          size=len(audio_bytes), mime='audio/wav'),
            source=CandidateSource(kind='stock', provider='fixture-stock-catalog',
                                   provider_asset_id=identity),
            rights=RightsInfo(status=RightsStatus.KNOWN,
                license_name='Fixture self-produced audio: test-only internal usage',
                evidence=(RightsEvidence(kind='asset_license',
                          reference='fixture://license/self-produced-audio'),)),
            technical=TechnicalInfo(status=TechnicalStatus.PASSED,
                duration_seconds=duration, mime='audio/wav'),
            semantic=SemanticInfo(),
        )
    store.write_asset(audio_asset)
    # The current video still needs a real visual Match. Approve a genuine
    # locally drawn and SHA-bound image through the ordinary human review Owner
    # before assessing whether cached BGM is the *last* blocking Need.
    picture = Image.new('RGB', (720, 1280), (95, 76, 57))
    canvas = ImageDraw.Draw(picture)
    canvas.rectangle((72, 310, 316, 765), fill=(248, 248, 245))
    canvas.rectangle((380, 330, 660, 790), fill=(249, 248, 245))
    bitmap = io.BytesIO()
    picture.save(bitmap, format='PNG')
    image_bytes = bitmap.getvalue()
    image_id = 'offline-two-white-papers'
    image_locator = store.write_asset_bytes(image_id, 'original.png', image_bytes)
    visual_need = next(n for n in frozen_plan.needs if n.media_type is MediaType.IMAGE)
    visual = MaterialAsset(
        asset_id=image_id, media_type=MediaType.IMAGE,
        file=FileInfo(path=image_locator, sha256=hashlib.sha256(image_bytes).hexdigest(),
                      size=len(image_bytes), mime='image/png'),
        source=CandidateSource(kind='local', provider='fixture-local',
                               provider_asset_id=image_id),
        rights=RightsInfo(status=RightsStatus.KNOWN,
            license_name='Self-created fixture two-white-papers',
            evidence=(RightsEvidence(kind='asset_license',
                       reference='fixture://license/self-created-image'),)),
        technical=TechnicalInfo(status=TechnicalStatus.PASSED,
            width=720, height=1280, mime='image/png'),
        semantic=SemanticInfo())
    store.write_asset(visual)
    now = datetime.now(timezone.utc)
    run = SupplyRun(supply_run_id=f'current-bgm-catalog-{duration}', plan_id=frozen_plan.plan_id,
                    parent_run_id=previous.supply_run_id,
                    started_at=now, finished_at=now, result_bundle_id=previous.bundle_id)
    assembled = MaterialBundleAssembler().assemble(
        frozen_plan, run, (*previous.assets, visual, audio_asset), previous.matches,
        bundle_id=previous.bundle_id)
    readiness, gaps = material_results.readiness_calculator(attempt, store).calculate(
        frozen_plan, assembled)
    attempt = MaterialGateIntegration().record(
        attempt, frozen_plan, assembled, run, readiness, gaps)['attempt']
    reviewed = MaterialProductOrchestrator().review_material_match(
        attempt['attempt_id'], asset_id=visual.asset_id, need_id=visual_need.need_id,
        expected_sha256=visual.file.sha256,
        observed_content='桌面上两张清晰完整的白色纸张，背景为棕色桌面，没有文字。',
        logo_present=None, visible_text_present=None, confirm_review=True)
    assert reviewed['material_status'] == 'MATERIAL_NOT_READY'
    attempt = service.get_film_attempt(attempt['attempt_id'])
    assert bgm.need_id in attempt['material_gate']['blocking_needs']
    assert visual_need.need_id not in attempt['material_gate']['blocking_needs']
    # Current Owner completes this cycle without pretending BGM was observed.
    # After that legitimate checkpoint, a prior cached BGM report can be replayed.
    def no_external_model(*_):
        pytest.fail('Current visual is human-reviewed; no model invoked by cache test')
    MaterialProductOrchestrator().observe_visual_materials(
        attempt['attempt_id'], executor=no_external_model)
    attempt = service.get_film_attempt(attempt['attempt_id'])
    assert attempt['material_observation']['status'] == 'COMPLETE'
    if openverse_item is not None:
        assert MaterialProductOrchestrator.pending_openverse_rights_refresh(attempt)
        assert not store.list_generation_records()
        return work, attempt, frozen_plan, bgm, audio_asset, store, None, None
    starts = sorted(set(range(0, duration - 9, 5)) | {duration - 10})
    report = {
        'schema': music.SCHEMA, 'model': music.MODEL_ID,
        'model_revision': music.MODEL_REVISION,
        'model_sha256': music.MODEL_FILES['model.safetensors'],
        'audio_sha256': audio_asset.file.sha256, 'duration_seconds': float(duration),
        'windows': [{'start_seconds': start, 'end_seconds': start + 10,
                     'rms': .1, 'scores': {'Music': .55, **{
                         label: vocal_score for label in music.VOCAL_LABELS}}}
                    for start in starts],
    }
    key = 'music-' + hashlib.sha256((
        music.SCHEMA + music.MODEL_REVISION + audio_asset.file.sha256).encode()).hexdigest()
    report_locator = store.write_observation_record(key, report)
    original_report = (root / report_locator).read_bytes()
    assert cached_music_reassessment(attempt) is not None
    assert not store.list_generation_records()
    return work, attempt, frozen_plan, bgm, audio_asset, store, report_locator, original_report


def _assert_u2a_cached_bgm_reassessment(
        material_integration_env, monkeypatch, duration, vocal_score):
    from easel.creation_delivery import active_delivery, next_operation
    from easel.materials.application import music_observation as music
    from easel.materials.application.music_reassessment import (
        cached_music_reassessment, pending_music_reassessment)

    (work, attempt, plan, bgm, audio_asset, store,
     report_locator, original_report) = _u2a_cached_bgm_fixture(
         material_integration_env, duration=duration, vocal_score=vocal_score)
    # Reassessment MUST be a local, same-attempt recovery; no new searches,
    # acoustic model, Authoring or charged operations.
    owner = MaterialProductOrchestrator()
    def forbid(*args, **kwargs):
        pytest.fail('A cached music report must not call Provider or model')
    monkeypatch.setattr(owner, 'refresh_openverse_rights', forbid)
    monkeypatch.setattr(owner, 'material_rights_candidates', forbid)
    monkeypatch.setattr(music, 'read_local_music', forbid)
    monkeypatch.setattr(ProductionAuthoringIntegration, 'prepare', forbid)
    assert next_operation(creation.get_creation(work['id']))[0] == 'observe_material'
    token = active_delivery.set(work['id'])
    try:
        result = owner.observe_visual_materials(attempt['attempt_id'], executor=forbid)
    finally:
        active_delivery.reset(token)
    latest = service.get_film_attempt(attempt['attempt_id'])
    assert latest['material_observation']['status'] == 'COMPLETE'
    assert not pending_music_reassessment(latest)
    assert store.read_recovery_record('music-reassessment-'+music.POLICY_DIGEST)['status'] == 'COMPLETE'
    if vocal_score == .015:
        assert bgm.need_id not in latest['material_gate']['blocking_needs']
    else:
        assert bgm.need_id in latest['material_gate']['blocking_needs']
    expected = 'MATERIAL_READY' if vocal_score == .015 else 'MATERIAL_NOT_READY'
    assert result['material_status'] == latest['material_gate']['status'] == expected
    assert next_operation(creation.get_creation(work['id']))[0] != 'observe_material'
    assert (Path(attempt['workspace']['path']) / report_locator).read_bytes() == original_report
    remaining = store.read_asset(audio_asset.asset_id)
    assert remaining.file == audio_asset.file
    assert remaining.rights == audio_asset.rights
    assert not store.list_generation_records()
    assert not creation.get_creation(work['id'])['delivery'].get('material_generations')
    assert latest['build']['operation'] is None


@pytest.mark.parametrize('duration,vocal_score', [
    (15, .015), (15, .05), (301, .015), (301, .05), (900, .015),
], ids=['15-instrumental', '15-unknown', '301-instrumental', '301-unknown', '900-instrumental'])
def test_u2a_current_cached_bgm_reassessment_retains_sha_rights_and_long_tail(
        material_integration_env, monkeypatch, duration, vocal_score):
    _assert_u2a_cached_bgm_reassessment(material_integration_env, monkeypatch, duration, vocal_score)


def _assert_u2a_cached_bgm_recovery(
        material_integration_env, monkeypatch, fault):
    """Current @4 Owner replays the SAME frozen request after a local crash."""
    from easel.creation_delivery import active_delivery
    from easel.integrations import material_layer
    from easel.materials.application import music_observation as music
    from easel.materials.application.music_reassessment import pending_music_reassessment

    (work, attempt, plan, bgm, asset, store,
     report_path, original_report) = _u2a_cached_bgm_fixture(
        material_integration_env, duration=15, vocal_score=.015)
    work_before = creation.get_creation(work['id'])
    rights_before = store.read_asset(asset.asset_id).rights
    bytes_before = store.resolve_asset_locator(asset.file.path).read_bytes()
    owner = MaterialProductOrchestrator()
    def forbidden(*args, **kwargs):
        pytest.fail('A cached report cannot re-search, regenerate, or re-observe paid media')
    monkeypatch.setattr(owner, 'refresh_openverse_rights', forbidden)
    monkeypatch.setattr(owner, 'material_rights_candidates', forbidden)
    monkeypatch.setattr(music, 'read_local_music', forbidden)
    monkeypatch.setattr(ProductionAuthoringIntegration, 'prepare', forbidden)
    token = active_delivery.set(work['id'])
    try:
        with monkeypatch.context() as interruption:
            if fault in {'requested', 'journal'}:
                original_write = AttemptMaterialStore.write_recovery_record
                stop_at = 'REQUESTED' if fault == 'requested' else 'COMPLETE'
                def write_and_interrupt(self, key, record):
                    original_write(self, key, record)
                    if key.startswith('music-reassessment-') and record['status'] == stop_at:
                        raise OSError('fixture interruption after ' + stop_at)
                interruption.setattr(AttemptMaterialStore, 'write_recovery_record', write_and_interrupt)
            elif fault == 'asset':
                original_write = AttemptMaterialStore.write_asset
                def write_and_interrupt(self, value):
                    original_write(self, value)
                    raise OSError('fixture interruption after asset')
                interruption.setattr(AttemptMaterialStore, 'write_asset', write_and_interrupt)
            elif fault == 'bundle':
                original_write = AttemptMaterialStore.write_bundle
                def write_and_interrupt(self, value):
                    original_write(self, value)
                    raise OSError('fixture interruption after bundle')
                interruption.setattr(AttemptMaterialStore, 'write_bundle', write_and_interrupt)
            elif fault == 'gate':
                original_record = MaterialGateIntegration.record
                def record_and_interrupt(self, *args, **kwargs):
                    original_record(self, *args, **kwargs)
                    raise OSError('fixture interruption after gate')
                interruption.setattr(MaterialGateIntegration, 'record', record_and_interrupt)
            else:
                original_update = material_layer._update_attempt
                def update_and_interrupt(current, **changes):
                    updated = original_update(current, **changes)
                    if changes.get('material_observation', {}).get('status') == 'PENDING':
                        raise OSError('fixture interruption after pending')
                    return updated
                interruption.setattr(material_layer, '_update_attempt', update_and_interrupt)
            with pytest.raises(OSError, match='fixture interruption'):
                owner.observe_visual_materials(attempt['attempt_id'], executor=forbidden)
        # Cold re-entry consumes only the checkpoint and cached local report.
        assert pending_music_reassessment(service.get_film_attempt(attempt['attempt_id']))
        resumed = owner.observe_visual_materials(attempt['attempt_id'], executor=forbidden)
    finally:
        active_delivery.reset(token)
    latest = service.get_film_attempt(attempt['attempt_id'])
    assert latest['material_observation']['status'] == 'COMPLETE'
    assert bgm.need_id not in latest['material_gate']['blocking_needs']
    assert resumed['material_status'] == latest['material_gate']['status'] == 'MATERIAL_READY'
    assert store.read_recovery_record('music-reassessment-'+music.POLICY_DIGEST)['status'] == 'COMPLETE'
    assert (Path(attempt['workspace']['path']) / report_path).read_bytes() == original_report
    assert store.resolve_asset_locator(asset.file.path).read_bytes() == bytes_before
    assert store.read_asset(asset.asset_id).rights == rights_before
    saved = creation.get_creation(work['id'])
    assert saved['delivery']['authorization'] == work_before['delivery']['authorization']
    assert not saved['delivery'].get('material_generations')
    assert not store.list_generation_records()
    assert latest['build']['operation'] is None


@pytest.mark.parametrize('fault', ['requested', 'pending', 'asset', 'bundle', 'gate', 'journal'])
def test_u2a_current_cached_bgm_recovers_each_durable_checkpoint_without_replay(
        material_integration_env, monkeypatch, fault):
    _assert_u2a_cached_bgm_recovery(material_integration_env, monkeypatch, fault)


@pytest.mark.parametrize('tamper', ['original_bytes', 'raw_report', 'bundle', 'rights'])
def test_u2a_current_cached_bgm_refuses_changed_original_or_evidence_then_recovers(
        material_integration_env, monkeypatch, tamper):
    """Unknown checkpoint remains blocked; restoring isolated source permits cold resume."""
    from easel.creation_delivery import active_delivery
    from easel.materials.application import music_observation as music

    (work, attempt, plan, bgm, asset, store,
     report_path, original_report) = _u2a_cached_bgm_fixture(
        material_integration_env, duration=15, vocal_score=.015)
    raw_audio = store.resolve_asset_locator(asset.file.path).read_bytes()
    preserved_bundle = store.read_bundle()
    path = Path(attempt['workspace']['path']) / report_path
    owner = MaterialProductOrchestrator()
    def forbidden(*args, **kwargs):
        pytest.fail('Cached BGM recovery must not call a source or model')
    monkeypatch.setattr(owner, 'refresh_openverse_rights', forbidden)
    monkeypatch.setattr(owner, 'material_rights_candidates', forbidden)
    monkeypatch.setattr(music, 'read_local_music', forbidden)
    monkeypatch.setattr(ProductionAuthoringIntegration, 'prepare', forbidden)

    token = active_delivery.set(work['id'])
    try:
        with monkeypatch.context() as interruption:
            native = AttemptMaterialStore.write_recovery_record
            def interrupt_requested(self, key, record):
                native(self, key, record)
                if key.startswith('music-reassessment-') and record['status'] == 'REQUESTED':
                    raise OSError('fixture interruption after requested')
            interruption.setattr(AttemptMaterialStore, 'write_recovery_record', interrupt_requested)
            with pytest.raises(OSError, match='after requested'):
                owner.observe_visual_materials(attempt['attempt_id'], executor=forbidden)
        if tamper == 'original_bytes':
            store.resolve_asset_locator(asset.file.path).write_bytes(raw_audio + b'changed')
        elif tamper == 'raw_report':
            invalid = json.loads(original_report)
            invalid['audio_sha256'] = '0'*64
            path.write_text(json.dumps(invalid), encoding='utf-8')
        elif tamper == 'bundle':
            store.write_bundle(preserved_bundle.model_copy(update={'bundle_id': 'foreign-bundle'}))
        else:
            existing = store.read_asset(asset.asset_id)
            store.write_asset(existing.model_copy(update={'rights': RightsInfo(status=RightsStatus.UNKNOWN)}))
        with pytest.raises((MaterialIntegrationError, ValueError)):
            owner.observe_visual_materials(attempt['attempt_id'], executor=forbidden)
        if tamper == 'original_bytes':
            store.resolve_asset_locator(asset.file.path).write_bytes(raw_audio)
        elif tamper == 'raw_report':
            path.write_bytes(original_report)
        elif tamper == 'bundle':
            store.write_bundle(preserved_bundle)
        else:
            store.write_asset(asset)
        recovered = owner.observe_visual_materials(attempt['attempt_id'], executor=forbidden)
    finally:
        active_delivery.reset(token)
    latest = service.get_film_attempt(attempt['attempt_id'])
    assert recovered['material_status'] == latest['material_gate']['status'] == 'MATERIAL_READY'
    assert bgm.need_id not in latest['material_gate']['blocking_needs']
    assert latest['material_observation']['status'] == 'COMPLETE'
    assert path.read_bytes() == original_report
    assert store.resolve_asset_locator(asset.file.path).read_bytes() == raw_audio
    assert store.read_asset(asset.asset_id).rights == asset.rights
    assert not store.list_generation_records()
    assert latest['build']['operation'] is None


def _u2a_current_voice_attempt(material_integration_env, monkeypatch, *, script_override=None):
    """Only public @4 voice enrollment and frozen vNext production ownership."""
    from dataclasses import replace
    from easel.runtime_config import EaselRuntimeConfig, MiniMaxRuntimeConfig
    from easel.integrations import material_generation as commissioned
    from easel.integrations import voice_identity as voice
    from easel import creation_preparation as preparation
    from tests.test_creation_preparation import (
        VIDEO_PROPOSAL, write_drafts, _current_vnext_planning_executor)

    baseline = EaselRuntimeConfig.load()
    settings = MiniMaxRuntimeConfig(api_key="offline-fixture-key")
    monkeypatch.setattr(EaselRuntimeConfig, "load", classmethod(
        lambda cls, **kwargs: replace(baseline, minimax=settings)))
    sound = ('预置旁白：' + voice.HANDLE
             + '\n按冻结 SCRIPT 逐字朗读，无音乐，不臆测未核实的听感。')
    proposal = VIDEO_PROPOSAL.replace("无旁白，无音乐。", sound).replace(
        "音轨：静音", "音轨：纯旁白")
    if script_override is not None:
        proposal = proposal.replace(
            "```text\n先看问题，再做决定。\n```",
            "```text\n" + script_override + "\n```")
    work = creation.create_creation(
        "明确预置身份的旁白", profile=None, creative_mode="clear_memo_video",
        route="hypit_video", origin={"type": "chat", "session_hash":
            hashlib.sha256(b"u2a-voice-current").hexdigest()})
    turn = "voice-explicit-approval"
    creation.begin_video_proposal(work["id"], turn, preset_contract=True,
        voice_profile_offer=voice.verified_profile())
    saved = creation.save_video_proposal(work["id"], turn, proposal)
    plan = saved["chat_workflow"]["video_plan"]
    assert plan["schema"] == "easel-video-proposal@4"
    assert plan["specs"]["audio_mode"] == "voice"
    if script_override is not None:
        assert plan["script"] == script_override
    transcript = json.dumps([{"role":"assistant","content":proposal}], ensure_ascii=False)
    scope = commissioned.generation_budget_preview()
    assert scope["available"] and scope["scope"]["speech_voice_id"] == settings.speech_voice_id
    grant = {"maxCostCny": 1, "scopeSha256": scope["scope_sha256"],
             "allowedModalities": ["voice"]}
    confirmed = creation.confirm_chat_proposal(
        work["id"], turn, delivery_proposal=transcript,
        proposal_sha256=hashlib.sha256(transcript.encode()).hexdigest(),
        production_specs=plan["specs"], video_plan_sha256=plan["sha256"],
        generation_budget=grant,
        input_use_statement_sha256=creation.input_use_preview(plan=plan)["statement_sha256"])
    binding = voice.require_binding(confirmed)
    assert binding["script_sha256"] == hashlib.sha256(plan["script"].encode()).hexdigest()
    assert confirmed["delivery"]["authorization"]["material_generation"]["allowed_modalities"] == ["voice"]

    claim = preparation.claim_chat_preparation(work["id"], "voice-fixture-session", turn)
    paths = preparation.preparation_paths(work["id"], claim["operation_key"])
    write_drafts(confirmed, paths["draft"])
    brief_file = paths["draft"] / "production-brief.json"
    brief = json.loads(brief_file.read_text(encoding="utf-8"))
    brief["audio_mode"] = "voice"
    brief_file.write_text(json.dumps(brief, ensure_ascii=False), encoding="utf-8")
    prepared = preparation.prepare_creation_for_hypit(
        work["id"], runtime_profile=None, planning_executor=_current_vnext_planning_executor)
    attempt = service.get_film_attempt(prepared["attempt_id"])
    planned = PlanningIntegration().load(attempt)
    from easel.materials.domain import VoiceIdentitySource
    voices = [n for n in planned["plan"].needs
              if getattr(n.modality_spec,"kind",None) == "voice"]
    assert len(voices) == 1
    need = voices[0]
    assert need.importance is NeedImportance.REQUIRED
    assert need.modality_spec.identity.source is VoiceIdentitySource.EXPLICIT_USER
    assert need.modality_spec.identity.reference == voice.REFERENCE
    assert need.modality_spec.text_sha256 == binding["script_sha256"]
    assert voice.require_binding(creation.get_creation(work["id"]),
                                 planned["plan"], planned["script"]) == binding
    assert attempt["material_gate"]["status"] == "MATERIAL_NOT_READY"
    assert attempt["build"]["operation"] is None
    assert not creation.get_creation(work["id"])["delivery"].get("material_generations")
    return work, attempt, planned, need, settings


def test_u2a_current_voice_proposal_binds_full_frozen_script_without_paid_tts(
        material_integration_env, monkeypatch):
    work, attempt, planned, need, settings = _u2a_current_voice_attempt(
        material_integration_env, monkeypatch)
    assert need.modality_spec.text_sha256 == hashlib.sha256(planned['script'].encode()).hexdigest()
    assert attempt['build']['operation'] is None


def test_u2a_long_voice_script_is_frozen_in_current_source(
        material_integration_env, monkeypatch):
    script = '每天整理纸面上的重要记录。' * 8
    work, attempt, planning, need, _ = _u2a_current_voice_attempt(
        material_integration_env, monkeypatch, script_override=script)
    assert planning['script'] == script
    assert need.modality_spec.text_sha256 == hashlib.sha256(script.encode()).hexdigest()
    assert attempt['build']['operation'] is None


def _u2a_voice_saved_commission(material_integration_env, monkeypatch, *, provider_timing, script_override=None):
    """Only MiniMax's paid HTTP boundary is fake; reservation/intake/Plan are real.

    MP3 is real offline ffmpeg audio with a tone, NOT real narration. The ASR
    transcript in later tests is a deterministic wire fixture and cannot prove
    that the audio really contains the words of the frozen SCRIPT.
    """
    import subprocess
    from easel.integrations import material_generation as commissioned
    from easel.materials.application import voice_delivery
    from easel.materials.providers import minimax_pricing
    from easel.materials import providers
    from easel.materials.providers.minimax_speech import MiniMaxSpeechResult
    from easel.creation_delivery import active_delivery, next_operation
    from tests.test_minimax_image_speech_generation import MINIMAX_TERMS_FIXTURE

    work, attempt, planning, need, settings = _u2a_current_voice_attempt(
        material_integration_env, monkeypatch, script_override=script_override)
    from easel.integrations.voice_identity import require_binding
    frozen = creation.get_creation(work['id'])
    assert require_binding(frozen, planning['plan'], planning['script'])
    assert planning['truth_ledger']['status'] == 'PASSED'
    assert commissioned.pending_generated_need(
        frozen, attempt, planning['plan'])[0].need_id == need.need_id

    # Real locally encoded bytes allow the real ffprobe TechnicalInspector.
    mp3 = subprocess.run([
        'ffmpeg', '-v', 'error', '-nostdin', '-f', 'lavfi',
        '-i', 'sine=frequency=440:duration=3', '-c:a', 'libmp3lame',
        '-b:a', '64k', '-f', 'mp3', 'pipe:1',
    ], capture_output=True, check=True, timeout=25).stdout
    assert mp3.startswith(b'ID3') and len(mp3) > 2000
    calls = []
    class OfflineSpeechAdapter:
        def __init__(self, _api_key, **args):
            assert _api_key == 'offline-fixture-key'
            self.model = args['model']
            self.voice_id = args['voice_id']
        def generate(self, text, **controls):
            latest = creation.get_creation(work['id'])['delivery']
            key = commissioned.pending_generated_need(
                creation.get_creation(work['id']), service.get_film_attempt(
                    attempt['attempt_id']), planning['plan'])[1]
            assert latest['material_generations'][key]['status'] == 'reserved'
            assert text == planning['script']
            assert controls == need.constraints.get('voice_delivery')
            calls.append(text)
            segments = (({'text': text, 'start_character': 0, 'end_character': len(text),
                          'start_seconds': .1, 'end_seconds': 2.9},)
                        if provider_timing else ())
            return MiniMaxSpeechResult(
                self.model, self.voice_id, mp3, 'mp3', segments,
                None if provider_timing else 'provider_timing_missing_or_invalid')

    def quote_fixture(url):
        if url == minimax_pricing.TERMS_URL:
            return MINIMAX_TERMS_FIXTURE
        if url == minimax_pricing.VOICE_URL:
            return '| 1 | 中文 | `male-qn-qingse` | 青年 |\n'
        return ('## 语音\n单价：元/万字符\n1 个汉字算 2 个字符\n'
                '| 同步 T2A | speech-2.8-hd | 说明 | 3.50 |\n'
                '## 图像\n单价：元/张\n| image-01 | 图片 | 0.025 |\n'
                '## 视频\n**视频生成-输出价格**\n'
                '| MiniMax-H3-Max | 480P | 按秒计费 | 0.33 元/秒 |\n'
                '| 1 | 中文 | `male-qn-qingse` | 青年 |\n')
    monkeypatch.setattr(minimax_pricing, 'read_public_contract', quote_fixture)
    monkeypatch.setattr(providers, 'MiniMaxSpeechAdapter', OfflineSpeechAdapter)
    # Only a bounded local-ASR dependency check is replaced. No remote model.
    monkeypatch.setattr(voice_delivery, 'require_local_voice_model',
                        lambda *args, **kwargs: Path(attempt['workspace']['path']))
    def forbidden_provider(*args, **kwargs):
        pytest.fail('Voice recovery may not re-enter a paid provider')
    token = active_delivery.set(work['id'])
    try:
        commissioned.generate_for_commission(attempt['attempt_id'])
        # No second purchase even if Gate remains blocked on Voice Rights/ASR.
        commissioned.generate_for_commission(attempt['attempt_id'])
    finally:
        active_delivery.reset(token)
    assert calls == [planning['script']], creation.get_creation(work['id'])['delivery'].get('material_generations')
    current = service.get_film_attempt(attempt['attempt_id'])
    store = AttemptMaterialStore(current['workspace']['path'])
    records = [r for r in store.list_generation_records() if r.get('modality') == 'voice']
    assert len(records) == 1
    record = records[0]
    assert record['status'] == 'COMPLETE'
    assert record['operator_confirmed_paid'] is False
    assert record['commission_authorization']['source'] == 'commission_budget'
    assert record['need_id'] == need.need_id
    assert record['input_sha256'] == hashlib.sha256(planning['script'].encode()).hexdigest()
    assert record['asset_id'] in {a.asset_id for a in store.read_bundle().assets}
    assert store.read_asset(record['asset_id']).technical.status is TechnicalStatus.PASSED
    assert next_operation(creation.get_creation(work['id']))[0] == 'recover_voice_timing'
    assert current['build']['operation'] is None
    return work, current, planning, need, store, record, calls


@pytest.mark.parametrize('provider_timing', [False, True], ids=['timing-missing','timing-received'])
def test_u2a_current_voice_commission_saves_paid_boundary_result_without_rebuy(
        material_integration_env, monkeypatch, provider_timing):
    work, attempt, planning, need, store, record, calls = _u2a_voice_saved_commission(
        material_integration_env, monkeypatch, provider_timing=provider_timing)
    assert record['voice_timing']['status'] == ('READY' if provider_timing else 'UNAVAILABLE')
    assert record['billing']['status'] == 'UNKNOWN'
    assert store.read_asset(record['asset_id']).rights.status is RightsStatus.UNKNOWN
    assert len(calls) == 1
    assert not attempt.get('production_authoring')


def _assert_u2a_voice_cold_recovery(
        material_integration_env, monkeypatch, timing_case, *, audit_signed_consent=False):
    """Current #16: durable commission receipt, local ASR, crash and no new TTS.

    The real MP3 is a sine-tone test file. Words are fixed ASR *wire* responses,
    never proof that the waveform contains speech or the right voice identity.
    """
    from easel.materials.application import voice_delivery
    from easel.creation_delivery import next_operation
    from easel.materials.application.matching import MaterialMatcher

    long_script = '每天整理纸面上的重要记录。' * 8 if timing_case == 'bounded_cached' else None
    (work, attempt, planning, need, store, original_record,
     tts_calls) = _u2a_voice_saved_commission(
         material_integration_env, monkeypatch, provider_timing=(timing_case == 'provider'),
         script_override=long_script)
    from copy import deepcopy
    from types import SimpleNamespace
    current = store.read_asset(original_record['asset_id'])
    saved_audio_bytes = store.resolve_asset_locator(current.file.path).read_bytes()
    saved_authorization = deepcopy(creation.get_creation(work['id'])['delivery']['authorization'])
    script = planning['script']
    chars = voice_delivery._spoken(script)
    assert chars and script == creation.get_creation(work['id'])['delivery']['video_plan']['script']
    asr_calls = []
    local_report = {
        'engine': 'offline-fixed-wire', 'words': [
            {'text': character, 'start_seconds': round(.1 + index * 2.7/len(chars), 6),
             'end_seconds': round(.1 + (index + 1) * 2.7/len(chars), 6),
             'probability': (.282 if index == 0 and timing_case == 'bounded_cached' else .97)}
            for index, character in enumerate(chars)],
    }
    verification = {
        'model_sha256': 'a'*64, 'engine': 'offline-fixed-wire',
        'version': 'fixture-1', 'language': None,
        'parameters': {'local_only': True}, 'rules': 'fixture-cold-recovery@1',
    }
    monkeypatch.setattr(voice_delivery, 'voice_verification_identity', lambda *_: dict(verification))
    def local_asr(file_path, language):
        assert file_path.read_bytes() == saved_audio_bytes and language is None
        asr_calls.append(file_path)
        return deepcopy(local_report)
    monkeypatch.setattr(voice_delivery, 'read_local_voice', local_asr)
    monkeypatch.setattr(MaterialProductOrchestrator, 'generate_minimax_asset',
                        lambda *args, **kwargs: pytest.fail('recovery must not repurchase TTS'))
    assert next_operation(creation.get_creation(work['id']))[0] == 'recover_voice_timing'

    owner = MaterialProductOrchestrator()
    original_write = AttemptMaterialStore.write_generation_record
    checkpoint_writes = []
    with monkeypatch.context() as isolated:
        def crash_after_audio_recognition(self, generation_id, record):
            if (record.get('voice_recognition') is not None and
                    generation_id == original_record['generation_id'] and not checkpoint_writes):
                checkpoint_writes.append(generation_id)
                raise OSError('offline crash after ASR checkpoint')
            return original_write(self, generation_id, record)
        isolated.setattr(AttemptMaterialStore, 'write_generation_record',
                         crash_after_audio_recognition)
        with pytest.raises(OSError, match='after ASR checkpoint'):
            owner.recover_voice_timing(attempt['attempt_id'])
    assert len(asr_calls) == 1
    assert store.read_generation_record(original_record['generation_id']) == original_record
    assert store.read_asset(current.asset_id).file == current.file
    assert store.resolve_asset_locator(current.file.path).read_bytes() == saved_audio_bytes
    # Exact same audio, SCRIPT SHA and ASR config resume from the saved report.
    monkeypatch.setattr(voice_delivery, 'read_local_voice',
                        lambda *_: pytest.fail('the same local ASR must not run twice'))
    MaterialProductOrchestrator().recover_voice_timing(attempt['attempt_id'])
    finalized = store.read_generation_record(original_record['generation_id'])
    latest = service.get_film_attempt(attempt['attempt_id'])
    observed = store.read_asset(current.asset_id)
    assert finalized['status'] == 'COMPLETE'
    assert finalized['operator_confirmed_paid'] is False
    assert finalized['commission_authorization'] == original_record['commission_authorization']
    assert finalized['voice_timing']['status'] == 'READY'
    assert finalized['voice_timing']['source'] == (
        'provider_alignment' if timing_case == 'provider' else 'local_asr')
    if timing_case == 'bounded_cached':
        assert finalized['voice_timing']['confidence_acceptance']['minimum_word_probability'] == .282
    assert finalized['voice_recognition']['words'] == local_report['words']
    assert voice_delivery.voice_content_observed(need, observed)
    assert observed.file == current.file and observed.rights.status is RightsStatus.UNKNOWN
    assert store.resolve_asset_locator(observed.file.path).read_bytes() == saved_audio_bytes
    assert not MaterialMatcher().match(need, (observed,)).matches  # ASR does not grant Rights.
    assert len(tts_calls) == 1 and len(asr_calls) == 1
    assert next_operation(creation.get_creation(work['id']))[0] != 'recover_voice_timing'
    assert creation.get_creation(work['id'])['delivery']['authorization'] == saved_authorization
    assert latest['build']['operation'] is None and not latest.get('production_authoring')


    if audit_signed_consent:
        from easel.integrations import material_generation as commissioned
        from tests.test_minimax_image_speech_generation import MINIMAX_TERMS_FIXTURE
        from easel.integrations.voice_identity import covered_asset_evidence, require_binding
        from easel.materials.application.readiness import MaterialReadinessCalculator
        from copy import deepcopy
        work_now=creation.get_creation(work['id'])
        declaration=work_now['delivery']['authorization']['input_use']
        assert declaration['schema']=='easel-input-use@3'
        assert declaration['audio_mode']=='voice'
        assert 'preset_voice_synthesis' in declaration['operations']
        assert 'text_to_visual_generation' in declaration['operations']
        assert require_binding(work_now,planning['plan'],script)
        assert finalized['billing']['status']=='UNKNOWN'  # actual settlement not inferred from an approved cap
        # Terms are test-only agreed sample bytes; never a statement about the
        # external live service terms or actual quality of the sine-tone MP3.
        agreed=finalized['commission_authorization']['quote']['terms_evidence']
        assert hashlib.sha256(agreed['document'].encode()).hexdigest()==agreed['sha256']
        monkeypatch.setattr(commissioned,'MINIMAX_INTERNAL_TERMS_SHA256',agreed['sha256'])
        baseline=store.read_asset(observed.asset_id)
        assert baseline.rights.status is RightsStatus.UNKNOWN
        def claim(w=work_now,r=finalized,a=baseline,n=need,text=script):
            return commissioned.commission_generated_rights(w,planning['plan'],n,a,r,text)
        evidence=claim()
        assert evidence is not None, 'valid signed Consent @3 must be consumed by Voice Rights'
        assert evidence.status is RightsStatus.KNOWN
        assert set(evidence.usage_constraints)=={'internal_production_only','current_creation_only'}
        assert any(row.kind=='asset_commission_use' for row in evidence.evidence)
        # Reconstructing a possible internal-use claim is not publishing it,
        # and fake ASR is never sufficient to declare the output ready.
        assert store.read_asset(observed.asset_id).rights.status is RightsStatus.UNKNOWN
        assert service.get_film_attempt(attempt['attempt_id'])['material_gate']['status']=='MATERIAL_NOT_READY'
        for fault in ('no_consent','legacy_consent','no_voice_op','wrong_script','wrong_need',
                      'wrong_asset','wrong_voice','unsettled_request','terms_drift','wrong_binding'):
            w,r,a,n,text=deepcopy(work_now),deepcopy(finalized),baseline,need,script
            if fault=='no_consent': w['delivery']['authorization']['input_use']=None
            elif fault=='legacy_consent': w['delivery']['authorization']['input_use']['schema']='easel-input-use@1'
            elif fault=='no_voice_op': w['delivery']['authorization']['input_use']['operations'].remove('preset_voice_synthesis')
            elif fault=='wrong_script': text='未确认的另一份SCRIPT'
            elif fault=='wrong_need': n=need.model_copy(update={'role':'changed-voice-need'})
            elif fault=='wrong_asset': a=baseline.model_copy(update={
                'file':baseline.file.model_copy(update={'sha256':'0'*64})})
            elif fault=='wrong_voice': r['voice_id']='unknown-new-voice'
            elif fault=='unsettled_request':
                key=r['commission_authorization']['request_id']
                w['delivery']['material_generations'][key]['status']='uncertain'
            elif fault=='terms_drift':
                r['commission_authorization']['quote']['terms_evidence']['document']+='new terms'
                w['delivery']['material_generations'][r['commission_authorization']['request_id']]['quote']=deepcopy(r['commission_authorization']['quote'])
            else: r['commission_authorization']['voice_binding_sha256']='0'*64
            assert claim(w,r,a,n,text) is None, fault
        evidence_view=covered_asset_evidence(
            work_now,planning['plan'],store.read_bundle(),store,script,
            checkpoint={'report': {'fixture':'not-an-operator-approval'},'chain':[]})
        assert evidence_view is not None and not evidence_view['approved']
        assert MaterialReadinessCalculator(store=store).calculate(
            planning['plan'],store.read_bundle())[0].status.value=='NOT_READY'


        # Re-enter the actual Material Owner after offline ASR. Its application
        # of the narrow source-bound claim is tested separately from the
        # still-missing visual material and from actual speech quality.
        from easel.creation_delivery import active_delivery
        owner_token=active_delivery.set(work['id'])
        try:
            resumed=MaterialProductOrchestrator().observe_visual_materials(
                attempt['attempt_id'],
                executor=lambda *_: pytest.fail('no available visual stock or external model'))
        finally:
            active_delivery.reset(owner_token)
        admitted=store.read_asset(observed.asset_id)
        assert admitted.rights == evidence
        assert admitted.file == observed.file
        latest_gate=service.get_film_attempt(attempt['attempt_id'])['material_gate']
        assert latest_gate['status']=='MATERIAL_NOT_READY'
        assert any(n.media_type is MediaType.IMAGE and n.need_id in latest_gate['blocking_needs']
                   for n in planning['plan'].needs)
        assert latest_gate['voice_identity_evidence']['binding_sha256'] == require_binding(
            creation.get_creation(work['id']),planning['plan'],script)['binding_sha256']
        assert latest_gate['voice_identity_evidence']['approved']
        assert latest_gate['voice_identity_evidence']['approved'][0]['asset_sha256']==admitted.file.sha256
        assert len(tts_calls)==len(asr_calls)==1
        assert service.get_film_attempt(attempt['attempt_id'])['build']['operation'] is None

def test_u2a_voice_signed_consent_rights_requires_frozen_asr_and_internal_scope(
        material_integration_env, monkeypatch):
    _assert_u2a_voice_cold_recovery(
        material_integration_env, monkeypatch, 'provider', audit_signed_consent=True)


@pytest.mark.parametrize('timing_case', ['missing', 'provider', 'bounded_cached'])
def test_u2a_current_voice_cold_recovery_preserves_paid_receipt_and_script(
        material_integration_env, monkeypatch, timing_case):
    _assert_u2a_voice_cold_recovery(material_integration_env, monkeypatch, timing_case)


def test_u2a_voice_current_invalid_asr_is_cached_without_rebuy(
        material_integration_env, monkeypatch):
    """Wrong words may never be silently reclassified as voice content."""
    from easel.materials.application import voice_delivery
    from easel.creation_delivery import next_operation
    (work, attempt, planning, need, store, original_record,
     tts_calls) = _u2a_voice_saved_commission(
        material_integration_env, monkeypatch, provider_timing=True)
    recorded_bytes = store.resolve_asset_locator(
        store.read_asset(original_record['asset_id']).file.path).read_bytes()
    verify = {'model_sha256': 'b'*64, 'engine': 'offline-wire', 'rules': 'fixture-invalid-voice'}
    monkeypatch.setattr(voice_delivery, 'voice_verification_identity', lambda *_: dict(verify))
    calls = []
    def invalid_asr(file, language):
        calls.append(file)
        assert file.read_bytes() == recorded_bytes and language is None
        return {'engine': 'offline-wire', 'words': [
            {'text': '错误语音', 'start_seconds': .1,
             'end_seconds': 2.9, 'probability': .99}]}
    monkeypatch.setattr(voice_delivery, 'read_local_voice', invalid_asr)
    monkeypatch.setattr(MaterialProductOrchestrator, 'generate_minimax_asset',
                        lambda *_args, **_kw: pytest.fail('TTS must not be purchased again'))
    with pytest.raises(ValueError, match='旁白识别文字与冻结脚本不一致'):
        MaterialProductOrchestrator().recover_voice_timing(attempt['attempt_id'])
    assert len(calls) == 1
    assert store.read_generation_record(original_record['generation_id']) == original_record
    assert store.read_asset(original_record['asset_id']).rights.status is RightsStatus.UNKNOWN
    assert next_operation(creation.get_creation(work['id'])) == (None, 'needs_audio_verification')
    monkeypatch.setattr(voice_delivery, 'read_local_voice',
                        lambda *_: pytest.fail('deterministic rejection cannot rerun ASR'))
    with pytest.raises(MaterialIntegrationError, match='同一音频和验证配置'):
        MaterialProductOrchestrator().recover_voice_timing(attempt['attempt_id'])
    assert len(tts_calls) == len(calls) == 1
    assert service.get_film_attempt(attempt['attempt_id'])['build']['operation'] is None
    assert store.resolve_asset_locator(
        store.read_asset(original_record['asset_id']).file.path).read_bytes() == recorded_bytes


def test_u2a_voice_current_recovery_rejects_modified_original_bytes(
        material_integration_env, monkeypatch):
    from easel.materials.application import voice_delivery
    (work, attempt, planning, need, store, record,
     tts_calls) = _u2a_voice_saved_commission(
        material_integration_env, monkeypatch, provider_timing=False)
    asset = store.read_asset(record['asset_id'])
    location = store.resolve_asset_locator(asset.file.path)
    original_bytes = location.read_bytes()
    asr_calls = []
    monkeypatch.setattr(voice_delivery, 'voice_verification_identity',
                        lambda *_: {'model_sha256': 'a'*64, 'rules': 'byte-bound'})
    monkeypatch.setattr(voice_delivery, 'read_local_voice',
                        lambda *_args: asr_calls.append(1))
    location.write_bytes(original_bytes + b'changed')
    with pytest.raises(MaterialIntegrationError, match='旁白字节已变化'):
        MaterialProductOrchestrator().recover_voice_timing(attempt['attempt_id'])
    assert not asr_calls
    assert store.read_generation_record(record['generation_id']) == record
    assert store.read_asset(asset.asset_id) == asset
    assert len(tts_calls) == 1
    assert service.get_film_attempt(attempt['attempt_id'])['build']['operation'] is None
    # Isolated test source restored; the stored identity is not retroactively rewritten.
    location.write_bytes(original_bytes)
    assert hashlib.sha256(location.read_bytes()).hexdigest() == asset.file.sha256


@pytest.mark.parametrize('fault', [
    'mismatch', 'extra', 'truncated', 'overlap', 'confidence', 'identity',
])
def test_u2a_current_voice_asr_must_match_full_frozen_script_and_byte_identity(
        material_integration_env, monkeypatch, fault):
    """Pure interpretation of fixed ASR wire; uses a real @4 issued Voice Need."""
    from copy import deepcopy
    from easel.materials.application import voice_delivery
    (work, attempt, planning, need, store, original_record,
     tts_calls) = _u2a_voice_saved_commission(
         material_integration_env, monkeypatch, provider_timing=False)
    asset = store.read_asset(original_record['asset_id'])
    script = planning['script']
    chars = voice_delivery._spoken(script)
    report = {
        'engine': 'offline-ASR-wire',
        'audio_sha256': asset.file.sha256,
        'script_sha256': hashlib.sha256(script.encode()).hexdigest(),
        'need_sha256': hashlib.sha256(need.to_json().encode()).hexdigest(),
        'words': [{
            'text': c,
            'start_seconds': round(.1 + i * 2.7 / len(chars), 6),
            'end_seconds': round(.1 + (i + 1) * 2.7 / len(chars), 6),
            'probability': .98} for i, c in enumerate(chars)],
    }
    accepted = voice_delivery.timing_from_recognition(script, asset, report)
    assert accepted['status'] == 'READY'
    assert len(accepted['cues']) >= 1
    assert not voice_delivery.voice_content_observed(need, asset)
    bad = deepcopy(report)
    if fault == 'mismatch':
        bad['words'][0]['text'] = '错'
    elif fault == 'extra':
        bad['words'][-1]['text'] += '啊'
    elif fault == 'truncated':
        bad['words'].pop()
    elif fault == 'overlap':
        bad['words'][1]['start_seconds'] = .1
    elif fault == 'confidence':
        bad['words'][0]['probability'] = .2
    else:
        bad['audio_sha256'] = '0'*64
    with pytest.raises(ValueError):
        if fault == 'identity':
            voice_delivery.apply_voice_content(need, asset, script, bad)
        else:
            voice_delivery.timing_from_recognition(script, asset, bad)
    assert store.read_asset(asset.asset_id) == asset
    assert store.read_generation_record(original_record['generation_id']) == original_record
    assert len(tts_calls) == 1
    assert service.get_film_attempt(attempt['attempt_id'])['build']['operation'] is None


def test_u2a_current_voice_operator_correction_cannot_bypass_script_or_rights(
        material_integration_env, monkeypatch):
    """A simulated explicit operator receipt is scoped to the rejected ASR SHA.

    This exercises reviewer admission, NOT a claim that a real person listened
    to our offline sine-tone audio fixture.
    """
    from copy import deepcopy
    from easel.materials.application import voice_delivery
    (work, attempt, planning, need, store, record,
     tts_calls) = _u2a_voice_saved_commission(
        material_integration_env, monkeypatch, provider_timing=True)
    script = planning['script']
    asset = store.read_asset(record['asset_id'])
    chars = voice_delivery._spoken(script)
    wrong_words = [
        {'text': '真的', 'start_seconds': .1, 'end_seconds': .6, 'probability': .98},
        *[{'text': c, 'start_seconds': round(.6 + i * 2.1/(len(chars)-2), 6),
           'end_seconds': round(.6 + (i + 1) * 2.1/(len(chars)-2), 6),
           'probability': .98} for i, c in enumerate(chars[2:])],
    ]
    monkeypatch.setattr(voice_delivery, 'voice_verification_identity',
                        lambda *_: {'model_sha256': 'a'*64, 'rules': 'operator-fixture'})
    monkeypatch.setattr(voice_delivery, 'read_local_voice',
                        lambda *_: {'engine': 'offline-wire', 'words': deepcopy(wrong_words)})
    with pytest.raises(ValueError, match='旁白识别文字与冻结脚本不一致'):
        MaterialProductOrchestrator().recover_voice_timing(attempt['attempt_id'])
    stored = list((Path(attempt['workspace']['path']) / 'materials/observations')
                  .glob('voice-asr-rejected-*.json'))
    assert len(stored) == 1
    rejected = json.loads(stored[0].read_text())
    digest = voice_delivery.recognition_digest(rejected)
    assert stored[0].stem == 'voice-asr-rejected-' + digest
    assert rejected['audio_sha256'] == asset.file.sha256
    assert rejected['script_sha256'] == hashlib.sha256(script.encode()).hexdigest()
    request = {
        'asset_id': asset.asset_id, 'need_id': need.need_id,
        'expected_sha256': asset.file.sha256,
        'observed_content': '隔离操作员确认：ASR 首两字应与已冻结 SCRIPT 完全一致。',
        'logo_present': None, 'visible_text_present': None, 'confirm_review': True,
    }
    reviewed_before = store.read_asset(asset.asset_id)
    wrong_corrections = (
        {'recognition_sha256': '0'*64, 'corrections': [
            {'character': 0, 'text': chars[0]}, {'character': 1, 'text': chars[1]}]},
        {'recognition_sha256': digest, 'corrections': [
            {'character': 0, 'text': '错'}, {'character': 1, 'text': chars[1]}]},
        {'recognition_sha256': digest, 'corrections': [
            {'character': 0, 'text': chars[0]}]},
    )
    for bad in wrong_corrections:
        with pytest.raises((MaterialIntegrationError, ValueError)):
            MaterialProductOrchestrator().review_material_match(
                attempt['attempt_id'], **request, voice_recognition_review=bad)
        assert store.read_asset(asset.asset_id) == reviewed_before

    response = MaterialProductOrchestrator().review_material_match(
        attempt['attempt_id'], **request, voice_recognition_review={
            'recognition_sha256': digest,
            'corrections': [{'character': 0, 'text': chars[0]},
                            {'character': 1, 'text': chars[1]}],
        })
    inspected = store.read_asset(asset.asset_id)
    assert voice_delivery.timing_from_recognition(script, inspected, rejected)['status'] == 'READY'
    assert inspected.file == asset.file and inspected.rights.status is RightsStatus.UNKNOWN
    assert response['material_status'] == 'MATERIAL_NOT_READY'
    assert need.need_id in service.get_film_attempt(attempt['attempt_id'])['material_gate']['blocking_needs']
    assert len(tts_calls) == 1
    assert service.get_film_attempt(attempt['attempt_id'])['build']['operation'] is None


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
    assert payload["script"] == creation.get_creation(attempt['creation_id'])['delivery']['video_plan']['script']
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
    frozen_need = PlanningIntegration().load(service.get_film_attempt(attempt["attempt_id"]))["plan"].needs[0].need_id
    assert selection["assets"][0]["qualified_need_ids"] == [frozen_need]
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
    assert '<space:Extent id="image-size" width="720" height="1280"/>' in original
    author.write_text(original.replace('id="image-size" width="720"', 'id="image-size" width="999"'))
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


def test_required_voice_need_is_bound_to_frozen_script_and_provider_neutral_identity(
        material_integration_env):
    """Pure current compiler invariant; not permission to inject Voice into silent V1.

    The actual voice/mixed commissioned end-to-end chain needs its own frozen
    Proposal @4. This unit proves SCRIPT SHA/identity binding and rejects the
    old unpinned direct Production persist path.
    """
    from easel.integrations.semantic_planning import apply_defaults
    attempt = material_integration_env
    script = "假设冻结旁白。\n"
    plan = MaterialPlan(
        plan_id="voice-plan", creation_id=attempt["creation_id"], attempt_id=attempt["attempt_id"],
        needs=(MaterialNeed(
            need_id="voiceover", scope=NeedScope(type=NeedScopeType.GLOBAL, ref="program"),
            media_type=MediaType.AUDIO, role="voiceover",
            intent=NeedIntent(description="Narration"),
            importance=NeedImportance.REQUIRED,
            modality_spec=VoiceNeedSpec(identity=VoiceIdentityRef(
                source=VoiceIdentitySource.CREATOR_CONTEXT, reference="creator-voice")),
        ),))
    mode, _ = handoff.load_frozen_creative_mode(attempt)
    original = plan.to_json()
    bound = apply_defaults(plan, mode, script)
    need = bound.needs[0]
    assert need.modality_spec.identity == plan.needs[0].modality_spec.identity
    assert need.modality_spec.text_ref == "planning/SCRIPT.md"
    assert need.modality_spec.text_sha256 == hashlib.sha256(script.encode()).hexdigest()
    assert plan.to_json() == original  # Canonical defaults do not modify input.
    root = Path(attempt["workspace"]["path"])
    creation_before = creation._creation_path(attempt["creation_id"]).read_bytes()
    attempt_before = service.get_film_attempt(attempt["attempt_id"])
    with pytest.raises(MaterialIntegrationError, match="旧 Planning/非当前委托只读"):
        PlanningIntegration().persist(
            attempt, bound, treatment="# Treatment\n", script=script,
            scenes="# Scenes\n")
    assert not (root / "planning/manifest.json").exists()
    assert creation._creation_path(attempt["creation_id"]).read_bytes() == creation_before
    assert service.get_film_attempt(attempt["attempt_id"]) == attempt_before




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


def test_int02_gate_blocks_not_ready_and_accepts_current_ready(material_integration_env, tmp_path):
    """Only a current observed Need+Asset+Rights match may open authoring."""
    from PIL import ImageDraw
    attempt = material_integration_env
    planning = _planning(attempt)
    local_root = tmp_path / 'self-created-gate-source'
    local_root.mkdir()
    image_path = local_root / 'two-white-papers.jpg'
    pic = Image.new('RGB', (720, 1280), (95, 76, 57))
    draw = ImageDraw.Draw(pic)
    draw.rectangle((72, 310, 316, 765), fill=(248, 248, 245))
    draw.rectangle((380, 330, 660, 790), fill=(249, 248, 245))
    pic.save(image_path)
    image_path.with_name(image_path.name + '.rights.json').write_text(
        json.dumps({'schema': 'easel-local-rights@1',
            'asset_sha256': hashlib.sha256(image_path.read_bytes()).hexdigest(),
            'rights': {'status': 'KNOWN', 'license_name': 'Fixture self-created media',
                'evidence': [{'kind': 'asset_license',
                              'reference': 'https://rights.example/current-gate',
                              'summary': 'Local two-paper image made by the test.'}]}},
            ensure_ascii=False), encoding='utf-8')
    pending = MaterialProductOrchestrator().run_with_planning(
        attempt, (local_root,), planning)
    assert pending['status'] == 'MATERIAL_NOT_READY'
    assert pending['attempt']['material_gate']['status'] == 'MATERIAL_NOT_READY'
    assert not pending['attempt'].get('production_authoring')
    with pytest.raises(HypitIntegrationError, match='MATERIAL_READY'):
        service.begin_film_authoring(attempt['attempt_id'])
    assert (Path(attempt['workspace']['path']) / 'materials/gaps.json').is_file()
    asset = next(asset for asset in pending['supply'].bundle.assets
                 if asset.rights.status is RightsStatus.KNOWN)
    reviewed = MaterialProductOrchestrator().review_material_match(
        attempt['attempt_id'], asset_id=asset.asset_id,
        expected_sha256=asset.file.sha256,
        need_id=planning['plan'].needs[0].need_id,
        observed_content='桌面上有两张清晰完整的白色纸张，背景为棕色桌面，没有文字。',
        logo_present=None, visible_text_present=None, confirm_review=True)
    assert reviewed['material_status'] == 'MATERIAL_READY'
    current_attempt = service.get_film_attempt(attempt['attempt_id'])
    _, _, readiness = MaterialGateIntegration().assert_ready(current_attempt)
    assert readiness.status.value == 'READY'
    assert current_attempt['build']['operation'] is None
    # Authoring may begin to choose admitted media, but not Build or export.
    claimed = service.begin_film_authoring(attempt['attempt_id'])
    assert claimed['authoring_status'] == 'AUTHORING_RUNNING'
    assert claimed['production_authoring']['status'] == 'PENDING_SELECTION'
    assert claimed['build']['operation'] is None



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
    from PIL import ImageDraw
    picture = Image.new("RGB", (720, 1280), (95, 76, 57))
    shapes = ImageDraw.Draw(picture)
    shapes.rectangle((72, 310, 316, 765), fill=(248, 248, 245))
    shapes.rectangle((380, 330, 660, 790), fill=(249, 248, 245))
    picture.save(local_root / "portrait.jpg")
    registry = material_supply_module.ProviderRegistry()
    registry.register(LocalProvider((local_root,)))
    monkeypatch.setattr(
        material_supply_module, "product_provider_registry", lambda _roots: (registry, ()),
    )
    # Obtain current Need/Plan from the frozen vNext Owner, not from a test Writer.
    planning = _planning(attempt)
    plan = planning['plan']
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
    # Rights evidence changes the admitted Asset identity; the original
    # unresolved source remains readable and its bytes are never rewritten.
    store = AttemptMaterialStore(Path(attempt['workspace']['path']))
    first_asset = result['supply'].bundle.assets[0]
    assert store.read_asset(first_asset.asset_id).file.sha256 == first_asset.file.sha256
    visual_source_sha = hashlib.sha256(local_file.read_bytes()).hexdigest()
    assert first_asset.file.sha256 == visual_source_sha
    assert all(a.file.sha256 == visual_source_sha for a in evidenced['supply'].bundle.assets)
    assert "production_authoring" not in evidenced["attempt"]
    assert (Path(attempt["workspace"]["path"]) / "materials/bundle.json").is_file()
    visual = next(asset for asset in evidenced["supply"].bundle.assets
                  if asset.rights.status is RightsStatus.KNOWN)
    reviewed = MaterialProductOrchestrator().review_material_match(
        attempt["attempt_id"], asset_id=visual.asset_id,
        expected_sha256=visual.file.sha256, need_id=plan.needs[0].need_id,
        observed_content="桌面上有两张白色纸张，背景为棕色桌面，没有文字。",
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
    # A required frozen vNext visual Need with zero Providers must stay blocked.
    planning = _planning(attempt)
    result = MaterialProductOrchestrator().run_with_planning(attempt, (), planning)
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
    # Isolated routing-domain test: no Writing/Production entitlement is
    # inferred from a manually assembled plan or a theoretical generation route.
    result = material_supply_module.ProductMaterialSupply(registry=registry).run(
        plan, attempt, local_roots=(), supply_run_id='u2a-generation-route',
        bundle_id='u2a-generation-bundle')
    trace = json.loads((Path(attempt["workspace"]["path"]) / "materials/product-supply.json").read_text())
    assert result.readiness.status.value == 'NOT_READY'
    assert result.generation_preparation['status'] == 'MATERIAL_GENERATION_AVAILABLE'
    assert trace['routing'][0]['routes'][-1]['kind'] == 'GENERATIVE'
    assert trace['generation_preparation']['need_id'] == 'need-generated'
    assert 'production_authoring' not in attempt
    assert 'material_generation_request' not in attempt
    # Product integration is intentionally stricter than routing analysis.
    with pytest.raises(MaterialIntegrationError, match='旧 Planning/非当前委托只读'):
        MaterialProductOrchestrator().run_with_planning(attempt, (), {
            'plan': plan, 'context_refs': {}, 'treatment': 'T',
            'script': '假设脚本内容。', 'scenes': 'C'})
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
        material_integration_env, monkeypatch):
    """CURRENT_REQUIRED #04: real current @4 generation, Rights, Gate, Authoring.

    Former implementation wrote invalid synthetic Planning, a non-image byte
    stream labeled PNG and a manually claimed GENERATION receipt. The new
    owner-specific test uses real PNG bytes and original MiniMax offline adapter
    receipts, with independent Rights review and native selection admission.
    Receipt-intake cold recovery remains separately covered by CURRENT #15/#08.
    """
    return test_u2a_current_generated_image_rights_opens_normal_authoring_selection(
        material_integration_env, monkeypatch)


def test_current_bundle_rights_review_admits_external_asset_without_repeating_supply(
    material_integration_env, monkeypatch,
):
    attempt = material_integration_env
    root = Path(attempt["workspace"]["path"])
    # Retain the frozen vNext Need and Truth ledger; never invent a new Plan ID
    # or re-persist a legacy manual plan under a lawful @4 commission.
    planning = _planning(attempt)
    plan = planning["plan"]
    assert len(plan.needs) == 1
    assert plan.needs[0].media_type is MediaType.IMAGE
    assert planning["truth_ledger"]["status"] == "PASSED"
    store = AttemptMaterialStore(root)
    # Real local JPEG bytes, not a byte-string disguised as a stock image.
    # The example Pexels provenance is synthetic and is never fetched.
    from io import BytesIO
    from PIL import ImageDraw

    image = Image.new("RGB", (720, 1280), (95, 76, 57))
    drawing = ImageDraw.Draw(image)
    drawing.rectangle((72, 310, 316, 765), fill=(248, 248, 245))
    drawing.rectangle((380, 330, 660, 790), fill=(249, 248, 245))
    encoded = BytesIO()
    image.save(encoded, format="JPEG")
    payload = encoded.getvalue()
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
        technical=TechnicalInfo(status=TechnicalStatus.PASSED, width=720, height=1280, mime="image/jpeg"),
        semantic=_observed_semantic("桌面上有两张清晰完整的白色纸张，背景为棕色桌面，没有文字。"),
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
    assert native._files(root) == before and not cli.calls


def test_production_selection_requires_qualified_need_match(material_integration_env):
    """Current vNext Bundle must reject an ineligible Need-to-Asset selection.

    Test the qualification predicate on a hypothetical unqualified Asset while
    keeping the real frozen Bundle unchanged. Production must still reject an
    unadmitted selected ID before any media Build.
    """
    from tests.test_native_authoring_publication import native_owner
    attempt, root = native_owner(material_integration_env)
    plan, bundle, readiness = MaterialGateIntegration().assert_ready(attempt)
    assert readiness.status.value == 'READY'
    store = AttemptMaterialStore(root)
    current_asset = bundle.assets[0]
    payload = store.resolve_asset_locator(current_asset.file.path).read_bytes()
    bad_id = 'asset-unmatched'
    bad_locator = store.write_asset_bytes(bad_id, 'unmatched.jpg', payload)
    unmatched_asset = current_asset.model_copy(update={
        'asset_id': bad_id,
        'file': current_asset.file.model_copy(update={
            'path': bad_locator, 'sha256': hashlib.sha256(payload).hexdigest(),
            'size': len(payload)}),
    })
    store.write_asset(unmatched_asset)
    unqualified = MaterialMatch(
        need_id=plan.needs[0].need_id, asset_id=bad_id, rank=2,
        score=0.0, reasons=('hard_filter=failed',), qualified=False)
    hypothetical = bundle.model_copy(update={
        'assets': (*bundle.assets, unmatched_asset),
        'matches': (*bundle.matches, unqualified),
    })
    assert not ProductionAuthoringIntegration._qualified_need_ids(
        plan, hypothetical, unmatched_asset, store=store, attempt=attempt)

    before = service.get_film_attempt(attempt['attempt_id'])
    with pytest.raises(MaterialIntegrationError, match='不在 MaterialBundle'):
        ProductionAuthoringIntegration().prepare(attempt, selected_asset_ids=(bad_id,))
    assert service.get_film_attempt(attempt['attempt_id']) == before
    assert before['build']['operation'] is None


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
    """Current @4/vNext -> Rights -> observed Match -> Native Check -> export usage.

    The credit is supplied by a local test operator as an explicit source fact,
    not generated by the LLM or attached to an obsolete synthetic Plan.
    """
    from tests.test_native_authoring_publication import native_owner, CheckBoundary

    source_page = "https://rights.example/self-created-attribution-image"
    credit = f"Photo by Ada — {source_page}"
    rights = RightsInfo(
        status=RightsStatus.ATTRIBUTION_REQUIRED, attribution_required=True,
        attribution_text=credit,
        usage_constraints=('internal_production_only',),
        evidence=(RightsEvidence(kind="asset_license", reference="fixture:license"),),
    )
    attempt, root = native_owner(material_integration_env, rights_review={
        "rights": rights, "creator": "Ada", "source_page": source_page,
    })
    store = AttemptMaterialStore(root)
    frozen = PlanningIntegration().load(attempt)
    assert frozen['plan'].plan_id == store.read_bundle().plan_id
    bundle = store.read_bundle()
    assert len(bundle.assets) == 1
    asset = bundle.assets[0]
    assert asset.rights.status is RightsStatus.ATTRIBUTION_REQUIRED
    assert asset.source.creator == "Ada" and asset.source.source_page == source_page
    assert attempt['material_gate']['status'] == 'MATERIAL_READY'
    cli = CheckBoundary(root)
    ready = service.complete_film_authoring(attempt["attempt_id"], cli=cli)
    assert ready["authoring_status"] == "AUTHORING_READY" and len(cli.calls) == 1
    assert ready['build']['operation'] is None
    persisted = ready["production_authoring"]["selection_validation"]["attributions"]
    assert persisted == [{
        "asset_id": asset.asset_id, "creator": "Ada",
        "credit_text": credit, "source_page": source_page,
        "destination": "export_credits", "rights_status": "ATTRIBUTION_REQUIRED",
        "evidence_references": ["fixture:license"],
    }]
    assert service._validated_output_usage(ready) == [{
        'asset_id': asset.asset_id, 'sha256': asset.file.sha256,
        'constraints': ['internal_production_only'],
    }]
    # A later "relaxed" license cannot broaden an already-validated export.
    changed = asset.model_copy(update={
        'rights': asset.rights.model_copy(update={'usage_constraints': ()})})
    run = store.read_supply_run(bundle.supply_run_id)
    changed_bundle = MaterialBundleAssembler().assemble(
        frozen['plan'], run, (changed,), bundle.matches, bundle_id=bundle.bundle_id)
    store.write_bundle(changed_bundle)
    with pytest.raises(service.HypitIntegrationError, match='使用范围已变化'):
        service._validated_output_usage(ready)


@pytest.mark.parametrize(('interrupt_after_supply', 'automatic'), [
    (False, False), (True, False), (True, True),
])
def test_material_recovery_preserves_generation_and_reconciles_without_resupply(
        material_integration_env, monkeypatch, interrupt_after_supply, automatic):
    """Migrate CURRENT_REQUIRED #08 to real @4/vNext + paid Voice receipt.

    The frozen voice identity, full Script and generated WAV/MP3 SHA must remain
    unchanged while the current Owner performs exactly one supplemental supply.
    """
    _assert_u2a_current_material_recovery_retains_generated_voice(
        material_integration_env, monkeypatch, interrupt_after_supply, automatic)


@pytest.mark.parametrize(('second_verdict', 'known_rights', 'report_fault'), [
    ('unsuitable', True, 'syntax'), ('suitable', True, 'missing'),
    ('suitable', False, None), ('uncertain', True, 'duplicate'),
    ('unsuitable', True, 'persistent'), ('suitable', True, 'silent_compile'),
])
def test_system_visual_observation_is_per_need_and_resumes_without_supply(
        material_integration_env, monkeypatch, second_verdict, known_rights, report_fault):
    """CURRENT_REQUIRED #09: original six cases through genuine frozen two scenes.

    The old body fabricated two Need IDs and called Planning.persist on an
    unsupported non-vNext Plan. This invokes the matching current Owner and
    shared report validators using real captured PNG and per-Need delta proofs.
    'silent_compile' now tests a silent shared material reply: the approved
    vNext requirements are immutable, not dynamically compiled by this Owner.
    """
    return test_u2a_current_two_scene_observation_reuses_first_evidence_after_fault(
        material_integration_env, monkeypatch, second_verdict, known_rights, report_fault)


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
@pytest.mark.parametrize('risk', [
    'unknown_first', 'second_uncertain', 'formal_write', 'tampered_projection',
])
def test_material_delta_batches_keep_original_results_and_recover_locally(
        material_integration_env, monkeypatch, tmp_path, risk):
    """CURRENT_REQUIRED #11: exact receipt/origin proof, not legacy Planning.

    Pure-domain multi-batch capture/unknown/tamper is the real Material@3
    consumer. Current vNext Need and Product Owner sharing are separately
    verified by #09 and #10 frozen-two-scene tests above.
    """
    from tests.test_material_result_delta import (
        test_current_material_delta_multi_batch_checkpoint_replay_and_tamper,
    )
    from easel.integrations import material_results
    assert material_results.enabled(material_integration_env)
    return test_current_material_delta_multi_batch_checkpoint_replay_and_tamper(
        tmp_path, monkeypatch, risk)


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


@pytest.mark.parametrize('outcome', [
    'budget', 'uncertain', 'scope_changed', 'account_changed',
    'video_resume', 'video_failed', 'video_intake_resume',
    'voice_preflight', 'terms_resume', 'image_ready', 'image_backlog',
    'restricted_image', 'restricted_video', 'restricted_voice',
    'restricted_music', 'modality_drift',
])
def test_commission_generation_reserves_before_submit_and_survives_restart(
        material_integration_env, monkeypatch, outcome):
    """CURRENT_REQUIRED #15. Each original case executes its New-Only proof.

    The old body forged an independently chosen MaterialPlan, overwrote chat
    confirmation/Delivery and thereby bypassed frozen Owner authority. These
    are not skipped or merely passed: each legacy invariant is re-executed
    through genuine @4 / Consent@3 / frozen Brief / vNext Planning and Gate.
    External image/video/TTS/price/ASR boundaries use explicit offline fakes.
    """
    image_reservations = {
        'budget': 'budget_exceeded',
        'uncertain': 'submission_unknown',
        'scope_changed': 'scope_changed',
    }
    if outcome in image_reservations:
        return test_u2a_current_visual_commission_reservation_unknown_and_no_rebuy(
            material_integration_env, monkeypatch, image_reservations[outcome])

    video_receipts = {
        'video_resume': 'pending_then_received',
        'video_failed': 'task_failed',
        'video_intake_resume': 'intake_crash',
    }
    if outcome in video_receipts:
        return test_u2a_current_video_generation_reservation_task_recovery_no_repurchase(
            material_integration_env, monkeypatch, video_receipts[outcome])

    drift = {'account_changed': 'account_key',
             'modality_drift': 'modality_permission'}
    if outcome in drift:
        return test_u2a_current_video_reserved_request_rejects_config_or_grant_drift(
            material_integration_env, monkeypatch, drift[outcome])

    if outcome == 'voice_preflight':
        return test_u2a_current_voice_preflight_requires_local_asr_before_paid_submit(
            material_integration_env, monkeypatch)
    if outcome == 'terms_resume':
        return test_u2a_current_image_unsubmitted_reservation_reuses_request_and_terms(
            material_integration_env, monkeypatch, 'terms_unavailable_then_readable')
    if outcome == 'image_ready':
        # Ordinary commissioned Delivery must admit Native selection after
        # independently verified Rights, not stop at the MATERIAL_READY-only endpoint.
        return test_u2a_current_generated_image_rights_opens_normal_authoring_selection(
            material_integration_env, monkeypatch)
    if outcome == 'image_backlog':
        return test_u2a_current_two_image_commissions_share_budget_without_rebuy_or_cross_need(
            material_integration_env, monkeypatch)
    if outcome in {'restricted_image', 'restricted_video', 'restricted_music'}:
        disabled = outcome.removeprefix('restricted_')
        return test_u2a_current_frozen_modality_not_paid_without_matching_budget(
            material_integration_env, monkeypatch, disabled)
    if outcome == 'restricted_voice':
        return test_u2a_current_confirmed_voice_rejects_revoked_modality_without_charges(
            material_integration_env, monkeypatch)
    raise AssertionError('Unmigrated CURRENT_REQUIRED #15 case: '+outcome)


@pytest.mark.parametrize('provider_timing', [False, True, 'bounded_cached'])
def test_missing_voice_timing_recovers_from_saved_audio_without_rebuying(
        material_integration_env, monkeypatch, provider_timing):
    """CURRENT_REQUIRED #16, migrated from invalid legacy hand-made Planning.

    Real @4 + signed Voice grant + production generation receipt + offline ASR
    checkpoint + current Owner cold replay. Negative audio/script/corrections
    are independently exercised above; synthetic audio is not proof of speech.
    """
    mode = ('bounded_cached' if provider_timing == 'bounded_cached' else
            'provider' if provider_timing is True else 'missing')
    _assert_u2a_voice_cold_recovery(material_integration_env, monkeypatch, mode)


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
    # Stay inside the already-confirmed @4 Creation and its frozen vNext Plan.
    # Endpoint authorization must not rewrite a Chat proposal or its digest.
    planning = _planning(attempt)
    plan = planning['plan']
    _, asset, legacy_run, _, _, _ = _contracts(attempt, root)
    run = legacy_run.model_copy(update={'plan_id': plan.plan_id})
    from PIL import ImageDraw
    image = Image.new('RGB', (720, 1280), (95, 76, 57))
    drawing = ImageDraw.Draw(image)
    drawing.rectangle((72, 310, 316, 765), fill=(248, 248, 245))
    drawing.rectangle((380, 330, 660, 790), fill=(249, 248, 245))
    encoded = BytesIO()
    image.save(encoded, format='PNG')
    content = encoded.getvalue()
    store = AttemptMaterialStore(root)
    asset = asset.model_copy(update={
        'file': FileInfo(path=store.write_asset_bytes(asset.asset_id, 'decoded.png', content),
                         sha256=hashlib.sha256(content).hexdigest(), size=len(content), mime='image/png'),
        'technical': TechnicalInfo(status=TechnicalStatus.PASSED, width=720, height=1280, mime='image/png'),
        'semantic': SemanticInfo(),
        'source': CandidateSource(kind='local', provider='fixture-local',
                                  provider_asset_id='self-created-two-white-papers'),
        'rights': RightsInfo(status=RightsStatus.KNOWN, license_name='Self-created offline fixture',
            evidence=(RightsEvidence(kind='asset_license', reference='https://rights.example/endpoint-fixture'),)),
    })
    store.write_asset(asset)
    from easel.materials.application.matching import MaterialMatcher
    initial_matches = MaterialMatcher().match(plan.needs[0], (asset,)).matches
    bundle = MaterialBundleAssembler().assemble(plan, run, (asset,), initial_matches,
                                                 bundle_id=run.result_bundle_id)
    readiness, gaps = MaterialReadinessCalculator(store=store).calculate(plan, bundle)
    MaterialGateIntegration().record(service.get_film_attempt(attempt['attempt_id']),
                                     plan, bundle, run, readiness, gaps)
    work = creation.get_creation(attempt['creation_id'])
    confirmed_bytes = creation._creation_path(work['id']).read_bytes()
    asyncio.run(web.api_creation_material_endpoint(work['id'], _operator=None))
    assert creation.get_creation(work['id'])['chat_workflow']['proposal_sha256'] == work['chat_workflow']['proposal_sha256']
    assert confirmed_bytes != creation._creation_path(work['id']).read_bytes()  # Only endpoint state changed.
    from tests.material_delta_fixture import observed_result
    observed = []
    def observe(current, manifest, attachments):
        observed.append(manifest['input_sha256'])
        return observed_result(current, manifest, attachments,
            outcome='suitable', description='actual two white papers on a brown desk')
    async def execute(operation, current):
        assert operation == 'observe_material'
        try:
            MaterialProductOrchestrator().observe_visual_materials(attempt['attempt_id'], executor=observe)
        except Exception as exc:
            pytest.fail(f'Current Material Observer failed before checkpoint: {exc!r}')
    monkeypatch.setattr(material_supply_module.ProductMaterialSupply, 'run', lambda *a, **kw: pytest.fail('covered supply cannot search'))
    monkeypatch.setattr(MaterialProductOrchestrator, 'generate_minimax_asset', lambda *a, **kw: pytest.fail('covered supply cannot generate'))
    for _ in range(4):
        asyncio.run(advance_creation(work['id'], execute))
    current = creation.get_creation(work['id'])
    latest = service.get_film_attempt(attempt['attempt_id'])
    assert observed and len(observed) == 1, {
        'next': next_operation(current),
        'gate': latest.get('material_gate'),
        'observation': latest.get('material_observation'),
        'matches': [m.model_dump(mode='json') for m in store.read_bundle().matches],
        'readiness': json.loads((root / 'materials/readiness.json').read_text()),
        'observations': observed,
    }
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
    """An old image heuristic cannot become a current Material@3 qualification.

    Synthetic historic bytes are retained inside the isolated Attempt workspace;
    there is no Planning write, Provider call, Rights upgrade or material READY.
    """
    from easel.integrations.output_receipts import OutputReceiptError
    from easel.integrations import material_results
    from easel.materials.application.visual_observation import PREFIX, need_identity

    attempt = material_integration_env
    current = _planning(attempt)
    need = current['plan'].needs[0]
    root = Path(attempt['workspace']['path'])
    store = AttemptMaterialStore(root)
    _, historic_asset, _, _, _, _ = _contracts(attempt, root)
    old_inference = SemanticInference(
        analyzer_id=PREFIX + need_identity(need),
        status=IntelligenceStatus.COMPLETE,
        annotations=(SemanticAnnotation(
            field=SemanticField.CAPTION, value='old preference heuristic',
            confidence=0.95, evidence='historic unverified pixels'),),
    )
    historic_asset = historic_asset.model_copy(update={
        'semantic': SemanticInfo(inferences=(old_inference,))})
    store.write_asset(historic_asset)
    old_record = {'schema': 'legacy-observation@1',
                  'verdict': 'unsuitable', 'caption': 'old preference heuristic',
                  'reason': 'no frozen Material@3 receipt'}
    locator = store.write_observation_record('f' * 64, old_record)
    report_before = (root / locator).read_bytes()
    asset_before = store.read_asset(historic_asset.asset_id).to_json()
    attempt_before = service.get_film_attempt(attempt['attempt_id'])
    creation_before = creation._creation_path(attempt['creation_id']).read_bytes()

    with pytest.raises(OutputReceiptError, match='result protocol proof'):
        material_results.eligible(store, need, historic_asset, attempt=attempt)
    with pytest.raises(OutputReceiptError, match='result protocol proof'):
        material_results.eligible(store, need, historic_asset, attempt=attempt)

    assert (root / locator).read_bytes() == report_before
    assert store.read_asset(historic_asset.asset_id).to_json() == asset_before
    assert service.get_film_attempt(attempt['attempt_id']) == attempt_before
    assert creation._creation_path(attempt['creation_id']).read_bytes() == creation_before




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
    # Only exercise the pure Material Supply/Need routing algorithm here.
    # A custom Plan does not acquire New-Only production qualification.
    plan = plan.model_copy(update={'needs': (a, b)})
    a, b = plan.needs
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
    from easel.materials.application.visual_observation import scoped_inference
    assert any(scoped_inference(a, asset, inference) and any(
        (annotation.evidence or '').endswith(':unsuitable')
        for annotation in inference.annotations)
        for inference in asset.semantic.inferences), asset.semantic.model_dump()
    # Supply-domain fixture only: retain this rejected candidate in an
    # isolated Bundle. No Production Gate or frozen vNext qualification claimed.
    store.write_plan(plan)
    checkpoint = MaterialBundleAssembler().assemble(
        plan, run.model_copy(update={'plan_id': plan.plan_id}),
        (asset,), (), bundle_id=run.result_bundle_id)
    store.write_bundle(checkpoint)
    # Negative-only domain checkpoint: NOT_READY, never registered as a
    # current production admission or passed to Delivery/Authoring.
    domain_attempt = {**attempt, 'material_gate': {
        'status': 'MATERIAL_NOT_READY',
        'plan_revision': MaterialReadinessCalculator.plan_revision(plan),
        'bundle_id': checkpoint.bundle_id, 'bundle_revision': checkpoint.revision}}
    store.write_recovery_record('candidate-links', {'assets': {asset.asset_id: [{
        'need_id': a.need_id, 'compiled_intent_sha256': hashlib.sha256(NeedCompiler.for_plan(plan).compile(a).to_json().encode()).hexdigest()}]}})
    registry = ProviderRegistry()
    calls = []
    for provider in (PexelsProvider('fixture-key'), PixabayProvider('fixture-key')):
        def search(intent, continuation=None, provider_id=provider.provider_id):
            calls.append((intent.need_id, provider_id))
            return ProviderPage()
        monkeypatch.setattr(provider, 'search', search)
        registry.register(provider)
    supply = material_supply_module.ProductMaterialSupply(registry=registry, library_root=tmp_path / 'empty-library')
    supply.run(plan, domain_attempt, local_roots=(), supply_run_id='scope-check', bundle_id='scope-result')
    assert 'material_gate' not in service.get_film_attempt(attempt['attempt_id'])
    assert calls == [('a', 'pixabay'), ('b', 'pexels')]

@pytest.mark.parametrize('fault', ['none', 'bytes', 'locator', 'license', 'credit'])
def test_openverse_rights_refresh_reuses_bytes_and_keeps_admission_boundaries(
        material_integration_env, monkeypatch, fault):
    """CURRENT_REQUIRED #25: current @4 music commission, not fabricated Delivery.

    Openverse item GET and initial WAV download use exact offline transports.
    The registered Material Owner, RightsService, Gate and journals remain real.
    """
    from easel.materials.providers.openverse import OpenverseAudioProvider
    from easel.materials.providers.http_support import HttpResponse
    from easel.materials.application.rights import RightsService, RightsAdmissionStatus
    from easel.creation_delivery import active_delivery, next_operation

    item = {
        'id': '7b77669a-afee-440c-b5d3-dd3dc71bb4cc',
        'title': 'Fixture Piano', 'creator': 'Fixture Composer',
        'foreign_landing_url': 'https://commons.wikimedia.org/w/index.php?curid=123',
        'url': 'https://upload.wikimedia.org/fixture.ogg',
        'license': 'by', 'license_version': '4.0',
        'license_url': 'https://creativecommons.org/licenses/by/4.0/',
        'attribution': 'Fixture Piano by Fixture Composer is licensed under CC BY 4.0.',
    }
    (work, attempt, plan, need, old, store, _, _) = _u2a_cached_bgm_fixture(
        material_integration_env, duration=15, vocal_score=.015,
        openverse_item=item)
    from easel.integrations import material_layer
    assert PlanningIntegration().load(attempt)['plan'] == plan
    assert work['delivery']['video_plan']['schema'] == 'easel-video-proposal@4'
    assert creation.get_creation(work['id'])['delivery']['authorization']['input_use']['schema'] == 'easel-input-use@3'
    assert old.source.provider == 'openverse_audio'
    assert not old.rights.evidence and old.rights.reviewed_at is None
    assert need.need_id in attempt['material_gate']['blocking_needs']
    acquisition = json.loads((store.materials_root / 'assets' / old.asset_id / 'acquisition.json').read_text())
    assert acquisition['sha256'] == old.file.sha256 and acquisition['need_id'] == need.need_id
    original_audio = store.resolve_asset_locator(old.file.path).read_bytes()
    original_gate = attempt['material_gate']
    recorded_authorization = creation.get_creation(work['id'])['delivery']['authorization']
    changes = dict(item)
    if fault == 'bytes':
        store.resolve_asset_locator(old.file.path).write_bytes(original_audio + b'tampered')
    if fault == 'locator':
        changes['url'] = 'https://upload.wikimedia.org/other.ogg'
    if fault == 'license':
        changes['license_url'] = 'https://creativecommons.org/licenses/by/3.0/'
    if fault == 'credit':
        changes['attribution'] = ''

    requests = []
    class OfflineMetadata:
        def get(self, url, **kwargs):
            requests.append(('metadata', url))
            return HttpResponse(200, {}, json.dumps(changes).encode())
    provider = OpenverseAudioProvider(transport=OfflineMetadata())
    owner = MaterialProductOrchestrator()
    def forbidden(*_args, **_kwargs):
        pytest.fail('Openverse fact-only refresh must not search, download, synthesize or Author')
    monkeypatch.setattr(ProductionAuthoringIntegration, 'prepare', forbidden)
    with pytest.raises(MaterialIntegrationError, match='当前委托Owner'):
        owner.refresh_openverse_rights(attempt['attempt_id'], provider=provider)
    token = active_delivery.set(work['id'])
    try:
        if fault in {'bytes', 'locator', 'license'}:
            with pytest.raises(MaterialIntegrationError):
                owner.refresh_openverse_rights(attempt['attempt_id'], provider=provider)
            assert store.read_asset(old.asset_id) == old
            assert service.get_film_attempt(attempt['attempt_id'])['material_gate'] == original_gate
            if fault == 'bytes':
                assert not requests
                store.resolve_asset_locator(old.file.path).write_bytes(original_audio)
            else:
                assert len(requests) == 1
        else:
            owner.refresh_openverse_rights(attempt['attempt_id'], provider=provider)
            refreshed = store.read_asset(old.asset_id)
            assert refreshed.file == old.file and refreshed.technical == old.technical
            assert refreshed.source.provider_asset_id == old.source.provider_asset_id
            assert refreshed.rights.reviewed_at is None
            assert refreshed.rights.evidence and refreshed.rights.status == old.rights.status
            decision = RightsService().evaluate(
                refreshed, need,
                attribution=RightsService.attribution_condition_for(refreshed))
            assert decision.status == (
                RightsAdmissionStatus.CONDITIONAL if fault == 'none'
                else RightsAdmissionStatus.BLOCKED)
            owner.refresh_openverse_rights(attempt['attempt_id'], provider=provider)
            assert len(requests) == 1
            assert next_operation(creation.get_creation(work['id']))[0] == 'observe_material'
            assert need.need_id in service.get_film_attempt(attempt['attempt_id'])['material_gate']['blocking_needs']
            assert service.get_film_attempt(attempt['attempt_id'])['material_observation']['status'] == 'PENDING'
        assert store.resolve_asset_locator(old.file.path).read_bytes() == original_audio
        assert store.read_asset(old.asset_id).file.sha256 == old.file.sha256
        assert creation.get_creation(work['id'])['delivery']['authorization'] == recorded_authorization
        assert not creation.get_creation(work['id'])['delivery'].get('material_generations')
        assert not store.list_generation_records()
        assert service.get_film_attempt(attempt['attempt_id'])['build']['operation'] is None
    finally:
        active_delivery.reset(token)

@pytest.mark.parametrize('fault,vocal_score', [
    ('none', .015), ('requested', .015), ('pending', .015), ('asset', .015),
    ('bundle', .015), ('gate', .015), ('journal', .015), ('none', .05),
])
def test_cached_bgm_policy_migration_resumes_without_external_calls(
        material_integration_env, monkeypatch, fault, vocal_score):
    """Migrated CURRENT_REQUIRED #26, not a legacy Writer/Delivery replay.

    All eight historical risk scenarios now use the actual Proposal @4,
    frozen vNext music Need, SHA-bound source bytes and the current Owner.
    Detailed tamper cases are also independently tested above.
    """
    if fault == 'none':
        _assert_u2a_cached_bgm_reassessment(
            material_integration_env, monkeypatch, 15, vocal_score)
    else:
        assert vocal_score == .015
        _assert_u2a_cached_bgm_recovery(material_integration_env, monkeypatch, fault)


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


def test_newonly_repair_evidence_checkpoint_cold_verify_and_tamper(material_integration_env):
    """Legal current @4 -> Owner B repair -> Truth -> cold verify, no Provider."""
    from copy import deepcopy
    from easel.integrations import semantic_boundary_run as boundary
    from easel.integrations.planning_repair_evidence import POLICY as EVIDENCE_POLICY
    from easel.integrations.hypit.handoff import load_frozen_creative_mode
    from easel.integrations.hypit import handoff
    from easel.materials.store import AttemptMaterialStore
    from tests.test_creation_preparation import _current_vnext_planning_executor
    attempt = material_integration_env
    root = Path(attempt['workspace']['path'])
    _, manifest, _ = handoff.resolve_handoff(attempt['creation_id'], attempt['handoff']['handoff_id'])
    hr = root / 'handoff'
    inputs = {key: json.loads((hr / value['path']).read_text(encoding='utf-8'))
              for key, value in (('content_core', manifest['content']['content_core']),
                                 ('truth_packet', manifest['content']['truth_packet']),
                                 ('creator_context', manifest['creator_context']))}
    refs = {'content_core_sha256': manifest['content']['content_core']['hash'],
            'truth_packet_sha256': manifest['content']['truth_packet']['hash'],
            'creator_context_sha256': manifest['creator_context']['hash'],
            'production_brief_sha256': manifest['production_request']['production_brief_sha256'],
            'creative_mode_sha256': manifest['creative_mode']['hash']}
    outcome = _current_vnext_planning_executor(attempt, {**inputs, 'context_refs': refs}, repair_probe=True)
    assert outcome['plan'].context_refs == refs
    store = AttemptMaterialStore(root)
    journal = store.read_recovery_record(boundary.STATE_KEY)
    assert journal['repair_used'] and 'repair' in journal['calls']
    assert journal['repair_evidence_policy'] == EVIDENCE_POLICY
    assert journal['schema_bindings']['repair']['repair_evidence_policy'] == EVIDENCE_POLICY
    reply = json.loads(journal['calls']['repair']['reply'])
    assert reply and all('evidence_ref' in item for value in reply.values() for item in value.get('support', []))
    checkpoint_path = root / 'planning/SEMANTIC_CHECKPOINT.json'
    frozen = checkpoint_path.read_bytes()
    checkpoint = json.loads(frozen)
    assert checkpoint['repair_evidence_policy'] == EVIDENCE_POLICY
    mode = load_frozen_creative_mode(attempt)[0]
    canonical = {name: (root / 'planning' / name).read_text()
                 for name in ('SCRIPT.md', 'SCENES.md', 'TREATMENT.md')}
    def cold_verify():
        return boundary.verify(root, outcome['plan'], mode, canonical['SCRIPT.md'], attempt=attempt)
    cold_verify()
    for fault in ('version', 'schema_binding', 'mapping_identity', 'evidence_ref', 'receipt_hash'):
        modified = deepcopy(checkpoint)
        if fault == 'version': modified['repair_evidence_policy'] = 'wrong-version@9'
        elif fault == 'schema_binding':
            modified['schema_bindings']['repair']['wire_schema_sha256'] = '0' * 64
        elif fault == 'mapping_identity':
            modified['schema_bindings']['repair']['frozen_mapping_sha256'] = '0' * 64
        elif fault == 'evidence_ref':
            content = json.loads(modified['wire_originals']['repair'])
            content[next(iter(content))]['support'][0]['evidence_ref'] = 'ev_unbound'
            modified['wire_originals']['repair'] = json.dumps(content)
        else: modified['capture']['repair']['reply_sha256'] = '0' * 64
        checkpoint_path.write_text(json.dumps(modified, ensure_ascii=False))
        try:
            with pytest.raises(ValueError): cold_verify()
        finally:
            checkpoint_path.write_bytes(frozen)
    cold_verify()
