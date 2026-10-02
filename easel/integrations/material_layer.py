"""Easel-owned integration boundary between Material Layer and Hypit Authoring."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from easel import creation
from easel.integrations.hypit.cli import HypitCLI
from easel.integrations.hypit.errors import HypitIntegrationError
from easel.materials.application.readiness import MaterialReadinessCalculator
from easel.materials.application.rights import RightsAdmissionStatus, RightsService
from easel.materials.application.standalone import StandaloneMaterialFlow
from easel.materials.application.acquisition import MaterialAcquirer
from easel.materials.application.generation import MiniMaxVideoMaterialGeneration
from easel.materials.application.generation_modalities import MiniMaxImageSpeechGeneration
from easel.materials.application.routing import MaterialSourceRouter
from easel.materials.domain import (
    MaterialBundle,
    MaterialGap,
    MaterialAsset,
    MaterialNeed,
    MaterialPlan,
    MaterialReadiness,
    MediaType,
    NeedImportance,
    NeedIntent,
    NeedScope,
    NeedScopeType,
    RightsEvidence,
    RightsInfo,
    RightsStatus,
    ReadinessStatus,
    TechnicalStatus,
    SupplyRun,
)
from easel.materials.providers import LocalProvider, ProviderRegistry
from easel.materials.store import AttemptMaterialStore, AttemptMaterialStoreError
from easel.integrations.script_truth import (
    ScriptTruthError,
    apply_operator_script_review,
    apply_system_script_review,
    create_script_claim_ledger,
    validate_script_claim_ledger,
)


class MaterialIntegrationError(HypitIntegrationError):
    """Raised when a Material lifecycle gate or bridge contract is invalid."""


def _assert_production_only_sources(run_text: str, authored_text: str) -> None:
    """Reject model-generation components in the formal Hypit editing path."""
    generation_packages = re.compile(
        r'@hypit/(?:gpt-image|seedance|mimo-speech|(?:[^"\s/]*(?:generate|generation|text-to-image|text-to-video)[^"\s/]*))@',
        re.IGNORECASE,
    )
    if generation_packages.search(run_text) or generation_packages.search(authored_text):
        raise MaterialIntegrationError("正式 Hypit Production 只能剪辑已准入素材，禁止在 SVML/SVRun 中生成媒体")


def copy_bound_validation_run(authored: Path, validation: Path) -> None:
    """Copy a native Run together with its identity, for the normal validator.

    This does not admit either file: _hypit_run_markup still checks all current
    identities before Hypit is called. JSON manifests need no companion input.
    """
    if authored.is_symlink() or not authored.is_file():
        raise MaterialIntegrationError("编排运行文件必须为当前普通文件")
    if (validation.parent.resolve() != authored.parent.resolve()
            or validation.resolve() == authored.resolve()
            or validation.is_symlink() or validation.with_suffix(".easel.json").is_symlink()):
        raise MaterialIntegrationError("编排校验副本路径无效")
    raw = authored.read_bytes()
    if raw.lstrip().startswith(b'<?svml using='):
        identity = authored.with_suffix(".easel.json")
        if identity.is_symlink() or not identity.is_file():
            raise MaterialIntegrationError("原生编排运行文件缺少当前身份记录")
        validation.with_suffix(".easel.json").write_bytes(identity.read_bytes())
    validation.write_bytes(raw)


def _hypit_run_markup(run_source: Path, root: Path, attempt: dict[str, Any],
                     plan: MaterialPlan, bundle: MaterialBundle,
                     readiness: MaterialReadiness) -> str:
    """Translate the bounded Easel authoring manifest into Hypit's installed Run markup.

    The model-authored JSON carries Easel identity, not Hypit syntax. Adapt that
    manifest deterministically, then let Hypit's own check validate the source.
    Native Run markup is generated only after the Easel identity manifest is
    validated; accepting model-authored markup here would bypass that binding.
    """
    raw = run_source.read_text(encoding="utf-8")
    identity_source = run_source.with_suffix(".easel.json")
    native = raw.lstrip().startswith("<?svml using=")
    if native:
        if not identity_source.is_file():
            raise MaterialIntegrationError("Native Hypit Run lacks the bound Easel identity manifest")
        raw = identity_source.read_text(encoding="utf-8")
    try:
        manifest = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MaterialIntegrationError("Easel Run manifest must be JSON with frozen identity") from exc
    expected = {
        "schema": "easel-authoring-svrun@1",
        "creation_id": attempt.get("creation_id"),
        "attempt_id": attempt.get("attempt_id"),
        "plan_id": plan.plan_id,
        "plan_revision": readiness.plan_revision,
        "bundle_id": bundle.bundle_id,
        "bundle_revision": bundle.revision,
        "readiness_revision": readiness.bundle_revision,
        "authoring_source": "../authors/main.svml",
        "material_selection": "../material-selection.json",
        "status": "AUTHORING_READY",
        "publication_allowed": False,
    }
    if not isinstance(manifest, dict) or any(manifest.get(key) != value for key, value in expected.items()):
        raise MaterialIntegrationError("Easel Run manifest identity or no-publication boundary is invalid")
    build = manifest.get("build")
    if not isinstance(build, dict) or build.get("enabled") is not False:
        raise MaterialIntegrationError("Easel Run manifest must stop before Hypit Build")
    author_path = (run_source.parent / manifest["authoring_source"]).resolve()
    if root not in author_path.parents or not author_path.is_file() or _has_symlink_components(
        root, run_source.parent / manifest["authoring_source"],
    ):
        raise MaterialIntegrationError("SVRun author source is missing or outside the Attempt workspace")
    markup = (
        '<?svml using="@hypit/run-markup@1"?>\n'
        '<svrun version="1">\n'
        '  <author source="../authors/main.svml"/>\n'
        '  <target output="final.video"/>\n'
        '</svrun>\n'
    )
    if native:
        if run_source.read_text(encoding="utf-8") != markup:
            raise MaterialIntegrationError("Hypit Run differs from the validated Easel identity manifest")
    else:
        identity_source.write_text(raw, encoding="utf-8")
        run_source.write_text(markup, encoding="utf-8")
    return markup


def _ensure_hypit_svml_header(author_source: Path) -> str:
    """Add Hypit's required source declaration without changing authored markup."""
    authored = author_source.read_text(encoding="utf-8")
    if authored.startswith('<?svml using="@hypit/markup@1"?>'):
        return authored
    xml_declaration = re.match(r"\s*<\?xml\s+[^?]*\?>\s*", authored)
    if xml_declaration is None or not re.match(r"<svml(?:\s|>)", authored[xml_declaration.end():]):
        return authored
    normalized = '<?svml using="@hypit/markup@1"?>\n' + authored[xml_declaration.end():]
    author_source.write_text(normalized, encoding="utf-8")
    return normalized


def _workspace(attempt: dict[str, Any]) -> Path:
    value = attempt.get("workspace", {}).get("path")
    if not isinstance(value, str) or not Path(value).is_absolute():
        raise MaterialIntegrationError("Attempt 缺少绝对 Hypit workspace")
    path = Path(value).resolve()
    if not path.is_dir():
        raise MaterialIntegrationError("Attempt Hypit workspace 不存在")
    return path


def _write_text(root: Path, relative: str, value: str) -> Path:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise MaterialIntegrationError(f"Planning artifact {relative} 不能为空")
    lexical_path = root / relative
    if _has_symlink_components(root, lexical_path):
        raise MaterialIntegrationError("Planning artifact path must not contain symlinks")
    path = lexical_path.resolve()
    if root not in path.parents or path.suffix not in {".md", ".json"}:
        raise MaterialIntegrationError("Planning artifact path is unsafe")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    return path


def _has_symlink_components(root: Path, path: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return True
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


def _update_attempt(attempt: dict[str, Any], **fields: Any) -> dict[str, Any]:
    attempt_id = attempt.get("attempt_id")
    if not isinstance(attempt.get("creation_id"), str) or not isinstance(attempt_id, str):
        raise MaterialIntegrationError("Attempt identity is invalid")
    from easel.integrations.hypit.service import update_film_attempt

    saved = update_film_attempt(attempt_id, event="material_lifecycle_updated", **fields)
    return dict(saved)


def _hypit_audio_tracks_for_source(authoring: str, expected_src: str) -> set[str]:
    """Find AudioTracks that place one selected asset and are included in a Film.

    This intentionally validates the reviewed Hypit v0.2.7 authoring shape rather
    than treating a bare media:Audio declaration as production use.
    """
    declarations = re.finditer(
        r'<media:Audio\b(?=[^>]*\bid="([A-Za-z_][\w.-]*)")'
        r'(?=[^>]*\bsrc="([^"]+)")[^>]*/?>', authoring,
    )
    media_ids = [match.group(1) for match in declarations if match.group(2) == expected_src]
    if not media_ids:
        return set()
    normalized_ids: set[str] = set()
    for media_id in media_ids:
        for match in re.finditer(r'<pipeline:Normalize\b([^>]*)/?>', authoring):
            attrs = match.group(1)
            id_match = re.search(r'\bid="([A-Za-z_][\w.-]*)"', attrs)
            source_match = re.search(r'\bsource=\{([A-Za-z_][\w.-]*)\}', attrs)
            audio_match = re.search(r'\baudio="([^"]+)"', attrs)
            if (id_match and source_match and source_match.group(1) == media_id
                    and audio_match and audio_match.group(1) != "none"):
                normalized_ids.add(id_match.group(1))
    if not normalized_ids:
        return set()
    audio_import = re.search(
        r'<import\b(?=[^>]*\bas="([A-Za-z_][\w.-]*)")'
        r'(?=[^>]*\bfrom="@hypit/audio-track@1")[^>]*/?>', authoring,
    )
    if not audio_import:
        return set()
    audio_prefix = re.escape(audio_import.group(1))
    track_ids: set[str] = set()
    for track_match in re.finditer(
        rf'<{audio_prefix}:Track\b([^>]*)>(.*?)</{audio_prefix}:Track\s*>', authoring, re.DOTALL,
    ):
        attrs, body = track_match.group(1), track_match.group(2)
        id_match = re.search(r'\bid="([A-Za-z_][\w.-]*)"', attrs)
        if not id_match:
            continue
        if not any(re.search(
            rf'<{audio_prefix}:Item\b[^>]*\bsource=\{{{re.escape(normalized_id)}\.media\}}', body,
        ) for normalized_id in normalized_ids):
            continue
        track_id = id_match.group(1)
        audible_ids = {track_id}
        if '<import as="easelmix" from="@easel/audio-mix@1"/>' in authoring:
            audible_ids.update(re.findall(
                r'<easelmix:Duck\b(?=[^>]*\bid="([A-Za-z_][\w.-]*)")'
                + r'(?=[^>]*\bsource=\{' + re.escape(track_id) + r'\.audio\})[^>]*/>', authoring))
        if any(re.search(
            rf'<film:Film\b[^>]*>.*?<film:Track\b[^>]*\bsource=\{{{re.escape(identity)}\.audio\}}',
            authoring, re.DOTALL,
        ) for identity in audible_ids):
            track_ids.add(track_id)
    return track_ids


class PlanningIntegration:
    """Persist structured planning outputs and the exact MaterialPlan inputs."""

    def persist(
        self,
        attempt: dict[str, Any],
        plan: MaterialPlan,
        *,
        treatment: str,
        script: str,
        scenes: str,
        script_assessment: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if plan.creation_id != attempt.get("creation_id") or plan.attempt_id != attempt.get("attempt_id"):
            raise MaterialIntegrationError("MaterialPlan identity does not match Attempt")
        for name, value in (("TREATMENT.md", treatment), ("SCRIPT.md", script), ("SCENES.md", scenes)):
            if not isinstance(value, str) or not value.strip() or "\x00" in value:
                raise MaterialIntegrationError(f"Planning artifact {name} 不能为空")
        script_digest = hashlib.sha256(script.encode("utf-8")).hexdigest()
        from easel.integrations.hypit.handoff import load_frozen_creative_mode
        mode, mode_hash = load_frozen_creative_mode(attempt)
        style = mode.get("visual_material_style")
        voice_delivery = mode.get("voice_delivery")
        if (style or voice_delivery) and plan.context_refs.get("creative_mode_sha256") != mode_hash:
            raise MaterialIntegrationError("Planning 风格来源与冻结 Creative Mode 不一致")
        bound_needs = []
        for need in plan.needs:
            spec = need.modality_spec
            scene_style = getattr(spec, 'visual_style', None) or style
            if (scene_style and need.media_type in {MediaType.IMAGE, MediaType.VIDEO}
                    and not need.constraints.get("preferred_style")):
                # A soft default on existing Need semantics; no subject,
                # narrative, source restriction or readiness rule is invented.
                need = need.model_copy(update={"constraints": {**need.constraints, "preferred_style": scene_style}})
            if getattr(spec, "kind", None) == "voice":
                from easel.materials.application.voice_delivery import validate_voice_delivery
                controls = need.constraints.get("voice_delivery", {})
                if not isinstance(controls, dict):
                    raise MaterialIntegrationError("Voice Need 的 voice_delivery 必须为参数对象")
                if voice_delivery or controls:
                    controls = validate_voice_delivery({**(voice_delivery or {}), **controls})
                    need = need.model_copy(update={"constraints": {**need.constraints, "voice_delivery": controls}})
            if (need.importance is NeedImportance.REQUIRED and need.media_type is MediaType.AUDIO
                    and getattr(spec, "kind", None) == "voice"):
                if spec.identity is None or spec.text_ref not in {None, "planning/SCRIPT.md"}:
                    raise MaterialIntegrationError(
                        "Required Voice Need must declare provider-neutral identity and reference the frozen SCRIPT"
                    )
                spec = spec.model_copy(update={
                    "text_ref": "planning/SCRIPT.md", "text_sha256": script_digest,
                })
                need = need.model_copy(update={"modality_spec": spec})
            bound_needs.append(need)
        plan = plan.model_copy(update={"needs": tuple(bound_needs)})
        root = _workspace(attempt)
        truth_path = root / "handoff" / "truth-packet.json"
        try:
            review = create_script_claim_ledger(script, truth_path)
            if script_assessment is not None:
                review = apply_system_script_review(script, truth_path, review, script_assessment)
        except ScriptTruthError as exc:
            raise MaterialIntegrationError(str(exc)) from exc
        review_path = root / "planning" / "script-claims.json"
        if _has_symlink_components(root, review_path):
            raise MaterialIntegrationError("Script claim ledger path must not contain symlinks")
        if review_path.is_file():
            try:
                existing_review = validate_script_claim_ledger(script, truth_path, json.loads(review_path.read_text(encoding="utf-8")))
                if existing_review["status"] == "PASSED" or script_assessment is None:
                    review = existing_review
            except (OSError, ValueError, ScriptTruthError):
                pass  # Changed script/truth must receive a fresh review ledger.
        review_path.parent.mkdir(parents=True, exist_ok=True)
        review_path.write_text(json.dumps(review, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        store = AttemptMaterialStore(root)
        plan_locator = store.write_plan(plan)
        plan_artifact = root / "planning" / "MATERIAL_PLAN.json"
        if _has_symlink_components(root, plan_artifact):
            raise MaterialIntegrationError("MaterialPlan artifact path must not contain symlinks")
        plan_artifact.write_text(plan.model_dump_json(indent=2) + "\n", encoding="utf-8")
        artifact_paths = {
            "treatment": _write_text(root, "planning/TREATMENT.md", treatment),
            "script": _write_text(root, "planning/SCRIPT.md", script),
            "scenes": _write_text(root, "planning/SCENES.md", scenes),
        }
        plan_revision = MaterialReadinessCalculator.plan_revision(plan)
        manifest = {
            "schema": "easel-material-planning@1",
            "status": "PLANNING_READY",
            "plan_id": plan.plan_id,
            "plan_revision": plan_revision,
            "plan_locator": plan_locator,
            "artifacts": {
                key: {
                    "path": path.relative_to(root).as_posix(),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
                for key, path in artifact_paths.items()
            },
        }
        manifest_path = root / "planning" / "manifest.json"
        if _has_symlink_components(root, manifest_path):
            raise MaterialIntegrationError("Planning manifest path must not contain symlinks")
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        updated = _update_attempt(
            attempt,
            material_planning={
                "status": "PLANNING_READY",
                "plan_id": plan.plan_id,
                "plan_revision": plan_revision,
                "manifest": "planning/manifest.json",
                "truth_review_status": review["status"],
                "truth_ledger_locator": "planning/script-claims.json",
                "truth_ledger_sha256": review["ledger_sha256"],
                "script_sha256": review["script_sha256"],
                "truth_packet_sha256": review["truth_packet_sha256"],
                "truth_claim_count": len(review["claims"]),
            },
        )
        return {"status": "PLANNING_READY", "plan": plan, "manifest": manifest,
                "truth_ledger": review, "attempt": updated}

    def load(self, attempt: dict[str, Any]) -> dict[str, Any]:
        """Load persisted Planning artifacts and verify their recorded digests."""
        root = _workspace(attempt)
        store = AttemptMaterialStore(root)
        try:
            plan = store.read_plan()
            manifest_path = root / "planning" / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise MaterialIntegrationError("Persisted Creative Planning evidence is unavailable") from exc
        if (not isinstance(manifest, dict)
                or plan.creation_id != attempt.get("creation_id") or plan.attempt_id != attempt.get("attempt_id")
                or manifest.get("status") != "PLANNING_READY"
                or manifest.get("plan_id") != plan.plan_id
                or manifest.get("plan_revision") != MaterialReadinessCalculator.plan_revision(plan)):
            raise MaterialIntegrationError("Persisted Creative Planning identity or revision is stale")
        artifacts: dict[str, str] = {}
        for key in ("treatment", "script", "scenes"):
            item = manifest.get("artifacts", {}).get(key)
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                raise MaterialIntegrationError("Persisted Planning manifest is incomplete")
            lexical_path = root / item["path"]
            if lexical_path.is_symlink():
                raise MaterialIntegrationError("Persisted Planning artifact path is invalid")
            path = lexical_path.resolve()
            if root not in path.parents or not path.is_file():
                raise MaterialIntegrationError("Persisted Planning artifact path is invalid")
            content = path.read_text(encoding="utf-8")
            if hashlib.sha256(path.read_bytes()).hexdigest() != item.get("sha256"):
                raise MaterialIntegrationError("Persisted Planning artifact digest is stale")
            artifacts[key] = content
        review_path = root / "planning" / "script-claims.json"
        if _has_symlink_components(root, review_path) or not review_path.is_file():
            raise MaterialIntegrationError("Persisted Script claim ledger is unavailable")
        try:
            ledger = json.loads(review_path.read_text(encoding="utf-8"))
            ledger = validate_script_claim_ledger(artifacts["script"], root / "handoff" / "truth-packet.json", ledger)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise MaterialIntegrationError("Persisted Script claim ledger is invalid or stale") from exc
        stored = attempt.get("material_planning", {})
        if (stored.get("truth_review_status") != ledger.get("status")
                or stored.get("truth_ledger_sha256") != ledger.get("ledger_sha256")
                or stored.get("script_sha256") != ledger.get("script_sha256")
                or stored.get("truth_packet_sha256") != ledger.get("truth_packet_sha256")):
            raise MaterialIntegrationError("Attempt Script review record does not match persisted claim ledger")
        return {"plan": plan, **artifacts, "context_refs": plan.context_refs,
                "truth_ledger": ledger, "attempt": attempt}

    def review_script(
        self,
        attempt: dict[str, Any],
        *,
        confirm_all_claims_reviewed: bool,
        expected_script_sha256: str,
        expected_truth_packet_sha256: str,
        reviewer: str = "local_operator",
    ) -> dict[str, Any]:
        """Record an explicit review without upgrading it to source-backed truth."""
        root = _workspace(attempt)
        script_path = root / "planning" / "SCRIPT.md"
        truth_path = root / "handoff" / "truth-packet.json"
        ledger_path = root / "planning" / "script-claims.json"
        for path in (script_path, truth_path, ledger_path):
            if _has_symlink_components(root, path) or not path.is_file():
                raise MaterialIntegrationError("Script/Truth review artifacts are unavailable or unsafe")
        try:
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
            updated_ledger = apply_operator_script_review(
                script_path.read_text(encoding="utf-8"), truth_path, ledger,
                confirm_all_claims_reviewed=confirm_all_claims_reviewed,
                expected_script_sha256=expected_script_sha256,
                expected_truth_packet_sha256=expected_truth_packet_sha256,
                reviewer=reviewer,
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise MaterialIntegrationError(str(exc)) from exc
        ledger_path.write_text(
            json.dumps(updated_ledger, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        material_planning = dict(attempt.get("material_planning", {}))
        material_planning.update({
            "truth_review_status": updated_ledger["status"],
            "truth_ledger_sha256": updated_ledger["ledger_sha256"],
            "truth_claim_count": len(updated_ledger["claims"]),
            "truth_reviewed_at": max((row["review"]["reviewed_at"] for row in updated_ledger["claims"]
                                      if isinstance(row.get("review"), dict)
                                      and row["review"].get("reviewer") == reviewer
                                      and isinstance(row["review"].get("reviewed_at"), str)), default=None),
        })
        updated_attempt = _update_attempt(
            attempt, material_planning=material_planning,
        )
        return {"status": updated_ledger["status"], "ledger": updated_ledger, "attempt": updated_attempt}


class MaterialGateIntegration:
    """Persist and enforce the current MaterialReadiness evidence."""

    def _require_planning(self, attempt: dict[str, Any]) -> None:
        if attempt.get("material_planning", {}).get("status") != "PLANNING_READY":
            raise MaterialIntegrationError("Production 前必须先达到 PLANNING_READY")

    def record(
        self,
        attempt: dict[str, Any],
        plan: MaterialPlan,
        bundle: MaterialBundle,
        run: SupplyRun,
        readiness: MaterialReadiness,
        gaps: tuple[MaterialGap, ...] | list[MaterialGap],
    ) -> dict[str, Any]:
        self._require_planning(attempt)
        root = _workspace(attempt)
        store = AttemptMaterialStore(root)
        if plan.plan_id != bundle.plan_id or plan.plan_id != run.plan_id:
            raise MaterialIntegrationError("Plan/Bundle/SupplyRun identity mismatch")
        if run.result_bundle_id is not None and run.result_bundle_id != bundle.bundle_id:
            raise MaterialIntegrationError("SupplyRun.result_bundle_id does not match MaterialBundle")
        if readiness.plan_id != plan.plan_id or readiness.bundle_id != bundle.bundle_id:
            raise MaterialIntegrationError("MaterialReadiness identity mismatch")
        calculator = MaterialReadinessCalculator(store=store)
        current, current_gaps = calculator.calculate(plan, bundle)
        if current != readiness or tuple(gaps) != current_gaps:
            raise MaterialIntegrationError("MaterialReadiness evidence is stale")
        store.write_bundle(bundle)
        store.write_supply_run(run)
        readiness_path = root / "materials" / "readiness.json"
        readiness_path.write_text(readiness.to_json() + "\n", encoding="utf-8")
        gaps_path = root / "materials" / "gaps.json"
        gaps_path.write_text(
            json.dumps([gap.model_dump(mode="json") for gap in current_gaps],
                       ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        status = "MATERIAL_READY" if readiness.status is ReadinessStatus.READY else "MATERIAL_NOT_READY"
        updated = _update_attempt(
            attempt,
            material_gate={
                "status": status,
                "plan_id": plan.plan_id,
                "bundle_id": bundle.bundle_id,
                "plan_revision": readiness.plan_revision,
                "bundle_revision": readiness.bundle_revision,
                "readiness_locator": "materials/readiness.json",
                "gaps_locator": "materials/gaps.json",
                "blocking_needs": list(readiness.blocking_needs),
            },
            material_audio_policy={
                "requires_audio": any(
                    need.importance is NeedImportance.REQUIRED and need.media_type is MediaType.AUDIO
                    for need in plan.needs
                ),
                "required_audio_need_ids": [
                    need.need_id for need in plan.needs
                    if need.importance is NeedImportance.REQUIRED and need.media_type is MediaType.AUDIO
                ],
                "required_voice_need_ids": [
                    need.need_id for need in plan.needs
                    if need.importance is NeedImportance.REQUIRED and need.media_type is MediaType.AUDIO
                    and getattr(need.modality_spec, "kind", None) == "voice"
                ],
                "required_bgm_need_ids": [
                    need.need_id for need in plan.needs
                    if need.importance is NeedImportance.REQUIRED and need.media_type is MediaType.AUDIO
                    and getattr(need.modality_spec, "kind", None) == "bgm"
                ],
            },
        )
        return {"status": status, "readiness": readiness, "gaps": current_gaps, "attempt": updated}

    def assert_ready(self, attempt: dict[str, Any]) -> tuple[MaterialPlan, MaterialBundle, MaterialReadiness]:
        self._require_planning(attempt)
        gate = attempt.get("material_gate", {})
        if gate.get("status") != "MATERIAL_READY":
            raise MaterialIntegrationError("当前素材未达到 MATERIAL_READY")
        root = _workspace(attempt)
        store = AttemptMaterialStore(root)
        try:
            plan = store.read_plan()
            bundle = store.read_bundle()
        except Exception as exc:
            raise MaterialIntegrationError("Material Plan/Bundle evidence is unavailable") from exc
        readiness, gaps = MaterialReadinessCalculator(store=store).calculate(plan, bundle)
        if readiness.status is not ReadinessStatus.READY or gaps:
            raise MaterialIntegrationError("MaterialReadiness 已失效；禁止进入 Production Authoring")
        if gate.get("bundle_revision") != bundle.revision or gate.get("plan_revision") != readiness.plan_revision:
            raise MaterialIntegrationError("MaterialReadiness revision is stale")
        return plan, bundle, readiness


class ProductionAuthoringIntegration:
    """Expose Bundle facts to authoring while requiring explicit asset selection."""

    def __init__(self, gate: MaterialGateIntegration | None = None):
        self.gate = gate or MaterialGateIntegration()

    @staticmethod
    def accepted_combination(attempt, plan, bundle, store) -> dict:
        """Read the saved Creator choice without treating it as admission."""
        marker = attempt.get('material_combination_review', {})
        if not marker.get('request_id'):
            return {}
        journal = store.read_recovery_record(marker['request_id'])
        if not journal or journal['plan_revision'] != MaterialReadinessCalculator.plan_revision(plan):
            raise MaterialIntegrationError('已接受的素材组合与当前方案不一致')
        choices = journal['choices']
        assets = {a.asset_id: a for a in bundle.assets}
        for need_id, choice in choices.items():
            asset = store.read_asset(choice['asset_id']) if choice['asset_id'] in assets else None
            if (asset is None or asset.file.sha256 != choice['sha256']
                    or need_id not in ProductionAuthoringIntegration._qualified_need_ids(plan, bundle, asset)):
                raise MaterialIntegrationError('已接受的素材仍须满足当前权利、技术和匹配要求')
        return choices

    def qualified_authoring_assets(self, attempt: dict[str, Any]) -> list[dict[str, Any]]:
        """List only assets that can satisfy a current Need in this Attempt."""
        from easel.materials.application.visual_observation import observed_interval, visual_use_prefix
        plan, bundle, _ = self.gate.assert_ready(attempt)
        store = AttemptMaterialStore(_workspace(attempt))
        authoring_source = "productions/easel-authoring/authors/main.svml"
        return [
            {
                "asset_id": asset.asset_id,
                "media_type": asset.media_type.value,
                "src": store.hypit_source_path(asset, authoring_source),
                "mime": asset.file.mime,
                "sha256": asset.file.sha256,
                "qualified_need_ids": list(need_ids),
                **({'source_duration_seconds': asset.technical.duration_seconds,
                    'observed_video_uses': [
                        {'need_id': need.need_id, 'element_id_prefix': visual_use_prefix(need),
                         'source_interval_seconds': list(interval), 'required': need.importance is NeedImportance.REQUIRED}
                        for need in plan.needs if need.need_id in need_ids
                        and (interval := observed_interval(need, asset)) is not None
                    ]} if asset.media_type is MediaType.VIDEO else {}),
            }
            for asset in bundle.assets
            if (need_ids := self._qualified_need_ids(plan, bundle, asset))
        ]

    def record_selection_from_authored_svml(self, attempt: dict[str, Any]) -> dict[str, Any]:
        """Record Production's actual media references using Easel-owned identity fields."""
        _, bundle, _ = self.gate.assert_ready(attempt)
        root = _workspace(attempt)
        authoring_source = "productions/easel-authoring/authors/main.svml"
        source_path = root / authoring_source
        if _has_symlink_components(root, source_path) or not source_path.is_file():
            raise MaterialIntegrationError("Production Authoring source is unavailable")
        authored_text = source_path.read_text(encoding="utf-8")
        declared_sources = list(dict.fromkeys(re.findall(
            r'<(?:[A-Za-z_][\w.-]*:)?(?:Image|Video|Audio)\b[^>]*\bsrc="([^"]+)"',
            authored_text,
        )))
        store = AttemptMaterialStore(root)
        assets_by_source = {
            store.hypit_source_path(asset, authoring_source): asset.asset_id
            for asset in bundle.assets
        }
        if not declared_sources or any(src not in assets_by_source for src in declared_sources):
            raise MaterialIntegrationError("SVML references media absent from the current MaterialBundle")
        selected_ids = tuple(assets_by_source[src] for src in declared_sources)
        qualified_ids = {item["asset_id"] for item in self.qualified_authoring_assets(attempt)}
        unqualified = [asset_id for asset_id in selected_ids if asset_id not in qualified_ids]
        if unqualified:
            raise MaterialIntegrationError(
                "SVML references Asset without a qualified Need/Match: " + ", ".join(unqualified)
            )
        return self.prepare(attempt, selected_asset_ids=selected_ids, authoring_source=authoring_source)

    def prepare(
        self,
        attempt: dict[str, Any],
        *,
        selected_asset_ids: tuple[str, ...] | list[str] = (),
        authoring_source: str = "productions/easel-authoring/authors/main.svml",
    ) -> dict[str, Any]:
        planning = PlanningIntegration().load(attempt)
        if planning["truth_ledger"]["status"] != "PASSED":
            raise MaterialIntegrationError("Script claims require local-operator review before Production Authoring")
        plan, bundle, readiness = self.gate.assert_ready(attempt)
        duration_limit = attempt.get("production_request", {}).get("preferred_duration_seconds", {}).get("max")
        if isinstance(duration_limit, (int, float)) and duration_limit > 0:
            voice_need_ids = {need.need_id for need in plan.needs
                              if need.modality_spec is not None and need.modality_spec.kind == "voice"}
            selected_voice_ids = {match.asset_id for match in bundle.matches
                                  if match.qualified and match.need_id in voice_need_ids}
            voice_durations = [asset.technical.duration_seconds for asset in bundle.assets
                               if asset.asset_id in selected_voice_ids
                               and asset.technical.duration_seconds is not None]
            if voice_durations and min(voice_durations) > duration_limit + 0.25:
                raise MaterialIntegrationError(
                    f"旁白时长至少 {min(voice_durations):.3f}s，超过已确认视频上限 "
                    f"{duration_limit:.3f}s；请调整脚本/旁白或重新确认时长，禁止静默截断"
                )
        selected = tuple(dict.fromkeys(selected_asset_ids))
        assets = {asset.asset_id: asset for asset in bundle.assets}
        if any(asset_id not in assets for asset_id in selected):
            raise MaterialIntegrationError("Production 选择了不在 MaterialBundle 中的素材")
        root = _workspace(attempt)
        store = AttemptMaterialStore(root)
        records = []
        for asset_id in selected:
            asset = assets[asset_id]
            need_ids = self._qualified_need_ids(plan, bundle, asset)
            if not need_ids:
                raise MaterialIntegrationError("Production 选择的素材没有当前合格 Need ↔ Asset Match")
            source = store.hypit_source_path(asset, authoring_source)
            records.append({
                "asset_id": asset.asset_id,
                "media_type": asset.media_type.value,
                "src": source,
                "mime": asset.file.mime,
                "sha256": asset.file.sha256,
                "qualified_need_ids": list(need_ids),
            })
        output_dir = root / "productions" / "easel-authoring"
        if _has_symlink_components(root, output_dir):
            raise MaterialIntegrationError("Production Authoring directory must not contain symlinks")
        output_dir.mkdir(parents=True, exist_ok=True)
        from easel.materials.application.voice_delivery import authoring_voice_timings
        _write_text(root, "productions/easel-authoring/VOICE_TIMING.json", json.dumps(
            authoring_voice_timings(plan, bundle, store, planning["script"]), ensure_ascii=False,
        ))
        selection = {
            "schema": "easel-production-material-selection@1",
            "creation_id": attempt["creation_id"],
            "attempt_id": attempt["attempt_id"],
            "plan_id": plan.plan_id,
            "plan_revision": readiness.plan_revision,
            "bundle_id": bundle.bundle_id,
            "bundle_revision": bundle.revision,
            "readiness_revision": readiness.bundle_revision,
            "readiness_plan_revision": readiness.plan_revision,
            "readiness_bundle_revision": readiness.bundle_revision,
            "authoring_source": authoring_source,
            "assets": records,
            "status": "PENDING_PRODUCTION_SELECTION" if not selected else "SELECTED",
        }
        from easel.integrations.material_recovery import director_shot_choices
        choices = director_shot_choices(attempt, plan)
        if choices:
            selection['director_shot_choices'] = choices
        accepted = self.accepted_combination(attempt, plan, bundle, store)
        if accepted:
            selection['creator_material_choices'] = accepted
        (output_dir / "material-selection.json").write_text(
            json.dumps(selection, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
        (output_dir / "MATERIAL_BUNDLE.json").write_text(bundle.to_json() + "\n", encoding="utf-8")
        for name in ("SCRIPT.md", "SCENES.md", "TREATMENT.md"):
            source = root / "planning" / name
            if _has_symlink_components(root, source) or not source.is_file():
                raise MaterialIntegrationError(f"缺少 Planning artifact: {name}")
            shutil.copyfile(source, output_dir / name)
        updated = _update_attempt(
            attempt,
            production_authoring={
                "status": "PENDING_SELECTION" if not selected else "SELECTION_RECORDED",
                "selection_locator": "productions/easel-authoring/material-selection.json",
                "selected_asset_ids": list(selected),
                "bundle_revision": bundle.revision,
            },
        )
        return {"status": updated["production_authoring"]["status"], "selection": selection, "attempt": updated}

    def compile_narration(self, attempt: dict[str, Any], source: str,
                          author_path: str = "productions/easel-authoring/authors/main.svml") -> str:
        """Compile from the current admitted evidence, never the agent's copy."""
        from easel.integrations.hypit.narration import compile_measured_narration
        from easel.integrations.hypit.music import compile_music_ducking
        from easel.integrations.hypit.handoff import load_frozen_creative_mode
        from easel.materials.application.voice_delivery import authoring_voice_timings

        plan, bundle, _ = self.gate.assert_ready(attempt)
        store = AttemptMaterialStore(_workspace(attempt))
        if not any(getattr(need.modality_spec, 'kind', None) == 'voice' for need in plan.needs):
            return source
        if not any(record.get("voice_timing") for record in store.list_generation_records()):
            return source
        planning = PlanningIntegration().load(attempt)
        timings = authoring_voice_timings(plan, bundle, store, planning["script"])
        sources = {asset.asset_id: store.hypit_source_path(asset, author_path) for asset in bundle.assets}
        try:
            source = compile_measured_narration(source, timings, sources)
            mode, _ = load_frozen_creative_mode(attempt)
            bgm_needs = {n.need_id for n in plan.needs if getattr(n.modality_spec, 'kind', None) == 'bgm'}
            bgm_ids = {m.asset_id for m in bundle.matches if m.qualified and m.need_id in bgm_needs}
            return compile_music_ducking(source, timings, sources, bgm_ids, mode.get('music_ducking'))
        except (ValueError, KeyError) as exc:
            raise MaterialIntegrationError(f"旁白原生编排需要修正：{exc}") from exc

    def validate_authored_selection(self, attempt: dict[str, Any], run_path: str) -> dict[str, Any]:
        """Bind Production's explicit selection to real workspace bytes and SVML references."""
        plan, bundle, readiness = self.gate.assert_ready(attempt)
        root = _workspace(attempt)
        store = AttemptMaterialStore(root)
        run = Path(run_path)
        if run.is_absolute() or ".." in run.parts:
            raise MaterialIntegrationError("Hypit Run path must stay inside the Attempt workspace")
        run_lexical = root / run
        if _has_symlink_components(root, run_lexical):
            raise MaterialIntegrationError("Hypit Run path must not contain symlinks")
        run_source = run_lexical.resolve()
        if root not in run_source.parents or not run_source.is_file():
            raise MaterialIntegrationError("Hypit Run is missing or outside the Attempt workspace")
        run_text = _hypit_run_markup(run_source, root, attempt, plan, bundle, readiness)
        author_match = re.search(r'<author\b[^>]*\bsource="([^"]+)"', run_text)
        if author_match is None:
            raise MaterialIntegrationError("SVRun must identify its authored SVML source")
        authored_ref = Path(author_match.group(1))
        authored_lexical = run_source.parent / authored_ref
        authored_source = authored_lexical.resolve()
        if (authored_ref.is_absolute() or root not in authored_source.parents
                or _has_symlink_components(root, authored_lexical) or not authored_source.is_file()):
            raise MaterialIntegrationError("SVRun author source is missing or outside the Attempt workspace")
        authored_text = _ensure_hypit_svml_header(authored_source)
        _assert_production_only_sources(run_text, authored_text)
        from easel.integrations.hypit.revision import assert_observed_video_uses
        assert_observed_video_uses(authored_source, self.qualified_authoring_assets(attempt))
        if self.compile_narration(attempt, authored_text, str(authored_source.relative_to(root))) != authored_text:
            raise MaterialIntegrationError("原生旁白/字幕与当前可信音频时序不一致，请重新完成编排")
        if '@easel/audio-mix@1' in authored_text:
            from easel.integrations.hypit.music import install_music_component
            try:
                install_music_component(root)
            except ValueError as exc:
                raise MaterialIntegrationError(str(exc)) from exc

        selection_path = root / "productions" / "easel-authoring" / "material-selection.json"
        if _has_symlink_components(root, selection_path):
            raise MaterialIntegrationError("Production selection manifest path must not contain symlinks")
        try:
            selection_bytes = selection_path.read_bytes()
            selection = json.loads(selection_bytes.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MaterialIntegrationError("Production material selection evidence is unavailable") from exc
        if not isinstance(selection, dict):
            raise MaterialIntegrationError("Production material selection evidence is invalid")
        if isinstance(selection, dict) and selection.get("status") == "PRODUCTION_SELECTED":
            selection["status"] = "SELECTED"
        # OpenClaw versions may append redundant identity aliases. Accept only
        # these two known aliases when they exactly repeat frozen Easel facts;
        # never let arbitrary metadata perturb an otherwise identical retry.
        expected_identity = {
            "creation_id": attempt.get("creation_id"),
            "attempt_id": attempt.get("attempt_id"),
            "handoff_id": attempt.get("handoff", {}).get("handoff_id"),
        }
        if "identity" in selection:
            if selection["identity"] != expected_identity:
                raise MaterialIntegrationError("Production selection identity alias does not match the current Creation/Attempt/Handoff")
            selection.pop("identity")
        if "revision" in selection:
            if selection["revision"] != bundle.revision:
                raise MaterialIntegrationError("Production selection revision alias does not match the current MaterialBundle")
            selection.pop("revision")
        from easel.integrations.material_recovery import director_shot_choices
        # These are server-owned authoring inputs, not model-owned selection.
        for key, expected in (
            ('director_shot_choices', director_shot_choices(attempt, plan)),
            ('creator_material_choices', self.accepted_combination(attempt, plan, bundle, store)),
        ):
            if key in selection and selection.pop(key) != expected:
                raise MaterialIntegrationError('Production 改写了已保存的导演或 Creator 决定')
        allowed_selection_fields = {
            "schema", "creation_id", "attempt_id", "plan_id", "plan_revision",
            "bundle_id", "bundle_revision", "readiness_revision",
            "readiness_plan_revision", "readiness_bundle_revision",
            "authoring_source", "assets", "status",
        }
        if set(selection) - allowed_selection_fields:
            raise MaterialIntegrationError("Production selection contains unsupported fields")
        # Hash semantic selection content in one canonical representation so an
        # Agent's harmless JSON key order/whitespace changes do not invalidate a
        # previously verified selection on an idempotent Authoring retry.
        selection_bytes = (
            json.dumps(selection, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        ).encode("utf-8")
        selection_path.write_bytes(selection_bytes)
        previous_authoring = attempt.get("production_authoring")
        if not isinstance(previous_authoring, dict):
            previous_authoring = {}
        if (not isinstance(selection, dict)
                or selection.get("schema") != "easel-production-material-selection@1"
                or selection.get("status") != "SELECTED"
                or selection.get("creation_id") != attempt.get("creation_id")
                or selection.get("attempt_id") != attempt.get("attempt_id")
                or selection.get("plan_id") != plan.plan_id
                or selection.get("plan_revision") != readiness.plan_revision
                or selection.get("bundle_id") != bundle.bundle_id
                or selection.get("bundle_revision") != bundle.revision
                or selection.get("readiness_revision") != readiness.bundle_revision
                or selection.get("readiness_plan_revision") != readiness.plan_revision
                or selection.get("readiness_bundle_revision") != readiness.bundle_revision
                or selection.get("authoring_source") != authored_source.relative_to(root).as_posix()):
            raise MaterialIntegrationError("Production selection does not belong to the current Plan/Bundle revision")
        records = selection.get("assets")
        if not isinstance(records, list) or not records:
            raise MaterialIntegrationError("Production Authoring must explicitly select at least one bundled Asset")
        allowed_asset_fields = {"asset_id", "media_type", "src", "mime", "sha256", "qualified_need_ids"}
        if any(not isinstance(item, dict) or set(item) - allowed_asset_fields for item in records):
            raise MaterialIntegrationError("Production selection contains unsupported Asset fields")
        assets = {asset.asset_id: asset for asset in bundle.assets}
        if len({item.get("asset_id") for item in records if isinstance(item, dict)}) != len(records):
            raise MaterialIntegrationError("Production selection contains duplicate or malformed Asset records")
        declared_media_sources = {
            value for value in re.findall(
                r'<(?:[A-Za-z_][\w.-]*:)?(?:Image|Video|Audio)\b[^>]*\bsrc="([^"]+)"',
                authored_text,
            )
        }
        selected_ids: list[str] = []
        checked: list[dict[str, str]] = []
        attributions: list[dict[str, Any]] = []
        normalized_records: list[dict[str, Any]] = []
        audio_tracks_by_need: dict[str, set[str]] = {}
        for item in records:
            if not isinstance(item, dict):
                raise MaterialIntegrationError("Production selection Asset record is invalid")
            asset_id = item.get("asset_id")
            asset = assets.get(asset_id) if isinstance(asset_id, str) else None
            if asset is None:
                raise MaterialIntegrationError("Production selected an Asset outside the current MaterialBundle")
            actual_path = store.resolve_asset_locator(asset.file.path)
            digest = hashlib.sha256(actual_path.read_bytes()).hexdigest()
            if digest != asset.file.sha256 or actual_path.stat().st_size != asset.file.size:
                raise MaterialIntegrationError(f"Selected MaterialAsset bytes changed after admission: {asset_id}")
            expected_src = store.hypit_source_path(asset, authored_source.relative_to(root).as_posix())
            if item.get("sha256") != digest:
                raise MaterialIntegrationError("Production selection hash does not match admitted Asset")
            if expected_src not in declared_media_sources:
                raise MaterialIntegrationError(f"SVML does not reference selected MaterialAsset: {asset_id}")
            if asset.media_type is MediaType.IMAGE:
                image_ids = re.findall(
                    r'<media:Image\b(?=[^>]*\bid="([A-Za-z_][\w.-]*)")'
                    + r'(?=[^>]*\bsrc="' + re.escape(expected_src) + r'")[^>]*/?>',
                    authored_text,
                )
                for image_id in image_ids:
                    for extent_id in re.findall(
                        r'<media-track:Item\b(?=[^>]*\bimage=\{' + re.escape(image_id)
                        + r'\})(?=[^>]*\bextent=\{([A-Za-z_][\w.-]*)\})[^>]*>',
                        authored_text,
                    ):
                        declaration = re.search(
                            r'<space:Extent\b(?=[^>]*\bid="' + re.escape(extent_id)
                            + r'")(?=[^>]*\bwidth="([0-9]+)")(?=[^>]*\bheight="([0-9]+)")[^>]*/?>',
                            authored_text,
                        )
                        if (declaration is None or asset.technical.width is None
                                or asset.technical.height is None
                                or (int(declaration.group(1)), int(declaration.group(2)))
                                != (asset.technical.width, asset.technical.height)):
                            raise MaterialIntegrationError(
                                f"Image Extent must use inspected source dimensions: {asset_id}"
                            )
            if item.get("media_type") != asset.media_type.value or item.get("mime") != asset.file.mime:
                raise MaterialIntegrationError("Production selection media contract does not match admitted Asset")
            qualified_need_ids = self._qualified_need_ids(plan, bundle, asset)
            if not qualified_need_ids:
                raise MaterialIntegrationError("Production 选择的素材没有当前合格 Need ↔ Asset Match")
            declared_need_ids = item.get("qualified_need_ids")
            if declared_need_ids is not None and declared_need_ids != list(qualified_need_ids):
                raise MaterialIntegrationError("Production selection Need/Match evidence is stale")
            selected_ids.append(asset_id)
            checked.append({"asset_id": asset_id, "sha256": digest, "src": expected_src,
                            "usage_constraints": list(asset.rights.usage_constraints)})
            normalized_records.append({
                **item,
                "src": expected_src,
                "qualified_need_ids": list(qualified_need_ids),
            })
            if asset.media_type is MediaType.AUDIO:
                track_ids = _hypit_audio_tracks_for_source(authored_text, expected_src)
                if not track_ids:
                    raise MaterialIntegrationError(
                        f"SVML selected audio Asset is not normalized, placed on an AudioTrack, and included in Film: {asset_id}"
                    )
                for need_id in qualified_need_ids:
                    audio_tracks_by_need.setdefault(need_id, set()).update(track_ids)
            condition = RightsService.attribution_condition_for(asset)
            attribution_required = (
                asset.rights.attribution_required
                or asset.rights.status.value == "ATTRIBUTION_REQUIRED"
                or "attribution_required" in asset.rights.usage_constraints
            )
            if attribution_required:
                if condition is None:
                    raise MaterialIntegrationError(
                        f"Selected MaterialAsset lacks verifiable attribution facts: {asset_id}"
                    )
                if not any(
                    RightsService().evaluate(asset, need, attribution=condition).status
                    is RightsAdmissionStatus.CONDITIONAL
                    for need in plan.needs if need.need_id in qualified_need_ids
                ):
                    raise MaterialIntegrationError(
                        f"Selected MaterialAsset attribution does not satisfy a matched Need: {asset_id}"
                    )
                attributions.append({
                    "asset_id": asset.asset_id,
                    "creator": asset.source.creator,
                    "credit_text": condition.credit_text,
                    "source_page": condition.source_page,
                    "destination": condition.destination,
                    "rights_status": asset.rights.status.value,
                    "evidence_references": [item.reference for item in asset.rights.evidence],
                })

        required_audio_needs = [
            need for need in plan.needs
            if need.importance is NeedImportance.REQUIRED and need.media_type is MediaType.AUDIO
        ]
        for need in required_audio_needs:
            if not audio_tracks_by_need.get(need.need_id):
                raise MaterialIntegrationError(
                    f"Required audio Need is absent from Production selection/AudioTrack: {need.need_id}"
                )
        voice_needs = [need for need in required_audio_needs
                       if getattr(need.modality_spec, "kind", None) == "voice"]
        bgm_needs = [need for need in required_audio_needs
                     if getattr(need.modality_spec, "kind", None) == "bgm"]
        voice_track_ids = set().union(*(audio_tracks_by_need[need.need_id] for need in voice_needs)) if voice_needs else set()
        bgm_track_ids = set().union(*(audio_tracks_by_need[need.need_id] for need in bgm_needs)) if bgm_needs else set()
        if voice_track_ids & bgm_track_ids:
            raise MaterialIntegrationError("Required narration and BGM must use separate Hypit AudioTracks")
        if voice_needs:
            timeline_ends = [float(value) for value in re.findall(
                r'<time:Timeline\b[^>]*\bend="([0-9]+(?:\.[0-9]+)?)s"', authored_text,
            )]
            if len(timeline_ends) != 1:
                raise MaterialIntegrationError(
                    "旁白需要一个可核验的固定 Timeline end 秒数，禁止无法核对的静默截断"
                )
            timeline_end = timeline_ends[0]
            for item in records:
                asset = assets[item["asset_id"]]
                if (asset.media_type is MediaType.AUDIO
                        and any(need_id in {need.need_id for need in voice_needs}
                                for need_id in self._qualified_need_ids(plan, bundle, asset))
                        and (asset.technical.duration_seconds is None
                             or asset.technical.duration_seconds > timeline_end + 0.25)):
                    raise MaterialIntegrationError(
                        f"旁白时长与 Timeline {timeline_end:.3f}s 不一致；禁止静默截断"
                    )

        accepted = self.accepted_combination(attempt, plan, bundle, store)
        if any(choice['asset_id'] not in selected_ids for choice in accepted.values()):
            raise MaterialIntegrationError('Production 未使用 Creator 已接受的完整素材组合')
        selected_sources = {item["src"] for item in checked}
        unselected_sources = declared_media_sources - selected_sources
        if unselected_sources:
            raise MaterialIntegrationError("SVML references media absent from the admitted Production selection")
        if (previous_authoring.get("status") == "READY"
                and set(previous_authoring.get("selected_asset_ids", [])) != set(selected_ids)):
            raise MaterialIntegrationError("Production selection Asset set changed after authoring validation")

        selection["assets"] = normalized_records
        selection["status"] = "SELECTED"
        normalized_selection_bytes = (
            json.dumps(selection, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        ).encode("utf-8")
        selection_digest = hashlib.sha256(normalized_selection_bytes).hexdigest()
        if (previous_authoring.get("status") == "READY"
                and previous_authoring.get("selection_sha256") != selection_digest):
            previous_checked = previous_authoring.get("selection_validation", {}).get("assets", [])
            current_checked_by_id = {item["asset_id"]: item for item in checked}
            previous_checked_by_id = {
                item.get("asset_id"): item for item in previous_checked if isinstance(item, dict)
            }
            if current_checked_by_id != previous_checked_by_id:
                raise MaterialIntegrationError("Production selection changed after authoring validation")
        selection_path.write_bytes(normalized_selection_bytes)

        updated = _update_attempt(
            attempt,
            production_authoring={
                **attempt.get("production_authoring", {}),
                "status": "READY",
                "selected_asset_ids": selected_ids,
                "bundle_revision": bundle.revision,
                "selection_sha256": selection_digest,
                "selection_validation": {
                    "run_path": run_source.relative_to(root).as_posix(),
                    "authoring_source": authored_source.relative_to(root).as_posix(),
                    "assets": checked,
                    "attributions": attributions,
                    "audio_tracks": {
                        need_id: sorted(track_ids)
                        for need_id, track_ids in sorted(audio_tracks_by_need.items())
                    },
                },
            },
            material_audio_policy={
                **attempt.get("material_audio_policy", {}),
                "requires_audio": bool(required_audio_needs or any(
                    item.get("media_type") == MediaType.AUDIO.value for item in normalized_records
                )),
                "selected_audio_asset_ids": [
                    item["asset_id"] for item in normalized_records
                    if item.get("media_type") == MediaType.AUDIO.value
                ],
            },
        )
        return {"status": "READY", "attempt": updated, "selected_asset_ids": tuple(selected_ids),
                "readiness": readiness}

    @staticmethod
    def _qualified_need_ids(
        plan: MaterialPlan, bundle: MaterialBundle, asset: MaterialAsset,
    ) -> tuple[str, ...]:
        if asset.technical.status is not TechnicalStatus.PASSED:
            return ()
        from easel.materials.application.matching import MaterialMatcher
        rights = RightsService()
        need_by_id = {need.need_id: need for need in plan.needs}
        qualified: set[str] = set()
        for match in bundle.matches:
            if (match.asset_id != asset.asset_id or not match.qualified
                    or "hard_filter=passed" not in match.reasons):
                continue
            need = need_by_id.get(match.need_id)
            if need is None or need.media_type is not asset.media_type:
                continue
            # READY proves at least one candidate per required Need, not every
            # persisted match. Recheck the actual selected candidate, including
            # optional Needs and byte-/Need-scoped observation evidence.
            if MaterialMatcher(rights).match(need, (asset,)).matches:
                qualified.add(need.need_id)
        return tuple(sorted(qualified))

    def assert_selection_current(self, attempt: dict[str, Any], run_path: str) -> dict[str, Any]:
        """Revalidate Build inputs against the admitted asset digest and explicit selection."""
        validated = self.validate_authored_selection(attempt, run_path)
        return validated["attempt"]


class MaterialHypitBridge:
    """Validate an authored Run through Hypit's ordinary media route."""

    def check(self, attempt: dict[str, Any], run_path: str, *, cli: HypitCLI | None = None) -> dict[str, Any]:
        root = _workspace(attempt)
        run = Path(run_path)
        lexical_source = root / run
        source = lexical_source.resolve()
        if (run.is_absolute() or ".." in run.parts or _has_symlink_components(root, lexical_source)
                or root not in source.parents or not source.is_file()):
            raise MaterialIntegrationError("Hypit Run 路径非法或不存在")
        # This acceptance boundary covers ordinary workspace media. Explicit
        # Candidate/satisfy or build-record routes are separate Hypit use cases
        # and must not silently become the MaterialAsset integration path.
        run_text = source.read_text(encoding="utf-8")
        if any(token in run_text for token in ("satisfy", "build-record")):
            raise MaterialIntegrationError("普通 MaterialAsset 禁止使用 Hypit legacy binding")
        ProductionAuthoringIntegration().assert_selection_current(attempt, run_path)
        result = (cli or HypitCLI()).check(root, source)
        if result.get("ok") is not True:
            raise MaterialIntegrationError("Hypit check 未通过")
        updated = _update_attempt(
            attempt,
            material_bridge={"status": "CHECKED", "run_path": run_path, "check": result},
        )
        return {"status": "CHECKED", "check": result, "attempt": updated}


class MaterialProductOrchestrator:
    """Connect Creation Preparation to the already implemented P0 flow.

    This is deliberately a thin product boundary. It consumes Director-owned
    Planning built from frozen Creation inputs, runs configured Local supply,
    reads only hash-bound per-asset Rights evidence, records the Material Gate,
    and prepares an empty Production-owned selection for Authoring to make.
    Provider credentials and Hypit production remain outside this class.
    """

    def run(self, attempt: dict[str, Any], local_roots: tuple[str | Path, ...]) -> dict[str, Any]:
        return self._run(attempt, local_roots, planning=None)

    def run_with_planning(
        self,
        attempt: dict[str, Any],
        local_roots: tuple[str | Path, ...],
        planning: dict[str, Any],
    ) -> dict[str, Any]:
        return self._run(attempt, local_roots, planning=planning)

    def generate_minimax_asset(
        self,
        attempt_id: str,
        *,
        need_id: str,
        request_id: str,
        confirmed_paid: bool,
        commission_request: str | None = None,
    ) -> dict[str, Any]:
        """Generate one explicitly approved blocking Need, then re-run its Material Gate."""
        from easel.integrations.hypit.service import get_film_attempt
        from easel.runtime_config import EaselRuntimeConfig
        from easel.materials.providers import (
            MiniMaxImageAdapter, MiniMaxSpeechAdapter, MiniMaxVideoAdapter,
        )

        attempt = get_film_attempt(attempt_id)
        planning = PlanningIntegration().load(attempt)
        if planning["truth_ledger"].get("status") != "PASSED":
            raise MaterialIntegrationError("Script Truth must be reviewed before Material generation")
        plan: MaterialPlan = planning["plan"]
        if (plan.creation_id != attempt.get("creation_id")
                or plan.attempt_id != attempt.get("attempt_id")):
            raise MaterialIntegrationError("MaterialPlan identity does not match the selected Attempt")
        gate = attempt.get("material_gate", {})
        if gate.get("status") != "MATERIAL_NOT_READY" or need_id not in gate.get("blocking_needs", []):
            raise MaterialIntegrationError("MiniMax may only serve a currently blocking Material Need")
        need = next((item for item in plan.needs if item.need_id == need_id), None)
        if need is None or not MaterialSourceRouter._generation_eligible(need):
            raise MaterialIntegrationError("This Need is not eligible for a generation source under Material policy")
        store = AttemptMaterialStore(_workspace(attempt))
        checkpoint = store.read_bundle()
        if (checkpoint.plan_id != plan.plan_id
                or gate.get("plan_revision") != MaterialReadinessCalculator.plan_revision(plan)
                or gate.get("bundle_id") != checkpoint.bundle_id
                or gate.get("bundle_revision") != checkpoint.revision):
            raise MaterialIntegrationError("生成前素材状态已变化，请先重新检查进度")
        config = EaselRuntimeConfig.load()
        settings = config.minimax
        if not settings.api_key:
            raise MaterialIntegrationError("MiniMax API key is not configured")
        approval = None
        if commission_request is not None:
            from easel.integrations.material_generation import assert_commission_request
            if request_id != commission_request:
                raise MaterialIntegrationError('生成请求与委托费用记录不一致')
            approval = assert_commission_request(attempt, plan, planning['script'], settings, request_id, need_id)
        if need.media_type is MediaType.VIDEO:
            generated = MiniMaxVideoMaterialGeneration(MiniMaxVideoAdapter(
                settings.api_key, model=settings.video_model, base_url=settings.base_url,
            )).generate(plan, need, store, request_id=request_id, confirmed_paid=confirmed_paid, approval=approval)
            model = settings.video_model
        elif need.media_type is MediaType.IMAGE:
            generated = MiniMaxImageSpeechGeneration(
                image_adapter=MiniMaxImageAdapter(
                    settings.api_key, model=settings.image_model, base_url=settings.base_url,
                ),
            ).generate(plan, need, store, request_id=request_id, confirmed_paid=confirmed_paid, approval=approval)
            model = settings.image_model
        elif need.media_type is MediaType.AUDIO and getattr(need.modality_spec, "kind", None) == "voice":
            generated = MiniMaxImageSpeechGeneration(
                speech_adapter=MiniMaxSpeechAdapter(
                    settings.api_key, model=settings.speech_model, voice_id=settings.speech_voice_id,
                    base_url=settings.base_url,
                ),
            ).generate(
                plan, need, store, request_id=request_id, confirmed_paid=confirmed_paid,
                speech_text=planning["script"], approval=approval,
            )
            model = settings.speech_model
        else:
            raise MaterialIntegrationError("MiniMax supports blocking Image, Video and script-bound Voice Needs only")

        return self._record_generated_asset(attempt, plan, store, checkpoint, generated, request_id, model)

    def resume_minimax_intake(self, attempt_id: str) -> dict[str, Any]:
        """Resume received bytes into the existing Bundle without Provider access."""
        from easel.integrations.hypit.service import get_film_attempt
        from easel.materials.application.generation_modalities import recoverable_generation_records

        attempt = get_film_attempt(attempt_id)
        planning = PlanningIntegration().load(attempt)
        if planning["truth_ledger"].get("status") != "PASSED":
            raise MaterialIntegrationError("Script Truth must be reviewed before Material recovery")
        plan = planning["plan"]
        store = AttemptMaterialStore(_workspace(attempt))
        checkpoint = store.read_bundle()
        records = recoverable_generation_records(plan, checkpoint, store,
                                                 gate_revision=attempt.get("material_gate", {}).get("bundle_revision"))
        if not records:
            raise MaterialIntegrationError("没有可接续的已保存生成结果；未请求 Provider")
        record = records[0]
        generated = MiniMaxImageSpeechGeneration().resume_received(
            store, record["generation_id"], speech_text=planning["script"] if record["modality"] == "voice" else None,
        )
        return self._record_generated_asset(attempt, plan, store, checkpoint, generated,
                                            record["generation_id"].removeprefix("gen-"), record["model"])

    def recover_voice_timing(self, attempt_id: str) -> None:
        """Verify retained narration independently; repair timing only if missing."""
        from easel.integrations.hypit.service import get_film_attempt
        from easel.materials.application.voice_delivery import (
            pending_voice_timing_recovery, read_local_voice, timing_from_recognition,
            bind_voice_timing, apply_voice_content, voice_content_observed, recognition_digest,
        )
        attempt = get_film_attempt(attempt_id)
        planning = PlanningIntegration().load(attempt)
        plan, script = planning['plan'], planning['script']
        store = AttemptMaterialStore(_workspace(attempt))
        bundle = store.read_bundle()
        pending = pending_voice_timing_recovery(plan, bundle, store, script, require_content=True)
        if not pending:
            return
        record = pending[0]
        with store.generation_lock(record['generation_id']):
            if store.read_generation_record(record['generation_id']) != record:
                raise MaterialIntegrationError('旁白记录已变化，请重新检查进度')
            asset = store.read_asset(record['asset_id'])
            path = store.resolve_asset_locator(asset.file.path)
            if (asset.file.sha256 != record['asset_sha256'] or asset.file.path != record.get('asset_path')
                    or asset.file.size != record.get('asset_bytes') or path.stat().st_size != asset.file.size
                    or hashlib.sha256(path.read_bytes()).hexdigest() != asset.file.sha256):
                raise MaterialIntegrationError('旁白字节已变化，不能恢复旧时序')
            need = next(n for n in plan.needs if n.need_id == record['need_id'])
            binding = {'audio_sha256': asset.file.sha256, 'script_sha256': hashlib.sha256(script.encode()).hexdigest(),
                       'need_sha256': hashlib.sha256(need.to_json().encode()).hexdigest()}
            identity = 'voice-asr-' + hashlib.sha256(json.dumps(binding, sort_keys=True).encode()).hexdigest()
            report_path = _workspace(attempt) / 'materials/observations' / (identity + '.json')
            if _has_symlink_components(_workspace(attempt), report_path):
                raise MaterialIntegrationError('旁白识别结果路径无效')
            if report_path.is_file():
                report = json.loads(report_path.read_text())
                if any(report.get(key) != value for key, value in binding.items()):
                    raise MaterialIntegrationError('旁白识别结果身份不一致')
            else:
                report = None
                for rejected_path in sorted((_workspace(attempt) / 'materials/observations').glob('voice-asr-rejected-*.json')):
                    if _has_symlink_components(_workspace(attempt), rejected_path):
                        continue
                    candidate = json.loads(rejected_path.read_text())
                    if rejected_path.stem != 'voice-asr-rejected-' + recognition_digest(candidate):
                        continue
                    if any(candidate.get(key) != value for key, value in binding.items()):
                        continue
                    try:
                        timing_from_recognition(script, asset, candidate)
                    except ValueError:
                        continue
                    report = candidate
                    break
                if report is None:
                    report = {**read_local_voice(path, None), **binding}
                # Only a valid recognition is a reusable checkpoint. A failed
                # guess must not poison Retry after local model repair.
                try:
                    timing_from_recognition(script, asset, report)
                except ValueError:
                    rejected_sha = hashlib.sha256(json.dumps(report, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
                    store.write_observation_record('voice-asr-rejected-' + rejected_sha, report)
                    raise
                store.write_observation_record(identity, report)
            timing = timing_from_recognition(script, asset, report)
            current = PlanningIntegration().load(get_film_attempt(attempt_id))
            if (current['plan'] != plan or current['script'] != script or store.read_bundle() != bundle
                    or hashlib.sha256(path.read_bytes()).hexdigest() != asset.file.sha256):
                raise MaterialIntegrationError('识别期间旁白输入已变化；保留结果，未认领旧时序')
            record.setdefault('provider_voice_timing', record.get('voice_timing'))
            existing = record.get('voice_timing') or {}
            if (existing.get('source') != 'provider_alignment'
                    or bind_voice_timing(script, asset, tuple(existing.get('cues', [])), existing.get('error'))['status'] != 'READY'):
                record['voice_timing'] = timing
            record['voice_recognition'] = report
            store.write_generation_record(record['generation_id'], record)
            if not voice_content_observed(need, asset):
                store.write_asset(apply_voice_content(need, asset, script, report))
            self._recalculate_observed_materials(attempt, plan, bundle, store)

    def _record_generated_asset(self, attempt, plan, store, checkpoint, generated, request_id, model):
        from easel.integrations.hypit.service import get_film_attempt
        attempt_id = attempt["attempt_id"]
        # Generation adds one Asset to the trusted Bundle. It must not search
        # Providers again or replace already acquired / reviewed supply facts.
        from easel.materials.application.assembly import MaterialBundleAssembler
        from easel.materials.application.dedup import MaterialDeduplicator
        from easel.materials.application.matching import MaterialMatcher

        attempt = get_film_attempt(attempt_id)
        current = store.read_bundle()
        intake = generated.record.get("bundle_intake") or {}
        resuming_registration = (intake.get("after_revision") == checkpoint.revision
                                 and intake.get("before_revision") == attempt.get("material_gate", {}).get("bundle_revision"))
        if (current != checkpoint
                or (attempt.get("material_gate", {}).get("bundle_revision") != checkpoint.revision
                    and not resuming_registration)
                or attempt.get("material_gate", {}).get("plan_revision")
                != MaterialReadinessCalculator.plan_revision(plan)):
            raise MaterialIntegrationError("素材已生成并保留，但素材状态已变化；请重新检查进度，不要重复生成")
        if resuming_registration:
            if not any(a.asset_id == generated.asset.asset_id and a.file == generated.asset.file for a in checkpoint.assets):
                raise MaterialIntegrationError("已保存素材与待恢复的 Bundle 不一致")
            bundle = checkpoint
            run = SupplyRun.model_validate_json(json.dumps(intake["supply_run"]))
        else:
            assets_by_id = {asset.asset_id: store.read_asset(asset.asset_id) for asset in checkpoint.assets}
            if any(assets_by_id[asset.asset_id] != asset for asset in checkpoint.assets):
                raise MaterialIntegrationError("素材已生成并保留，但已有素材记录已变化；请重新检查进度，不要重复生成")
            assets_by_id[generated.asset.asset_id] = store.read_asset(generated.asset.asset_id)
            assets = tuple(assets_by_id.values())
            matcher = MaterialMatcher()
            deduplicator = MaterialDeduplicator(store)
            matches = []
            for current_need in plan.needs:
                ranked = matcher.match(current_need, assets)
                matches.extend(deduplicator.deduplicate_and_diversify(
                    ranked.matches, assets, top_k=3,
                ).shortlist)
            suffix = hashlib.sha256(request_id.encode("utf-8")).hexdigest()[:16]
            now = datetime.now(timezone.utc)
            run = SupplyRun(
                supply_run_id=f"supply-gen-{suffix}", plan_id=plan.plan_id,
                parent_run_id=checkpoint.supply_run_id,
                started_at=now, finished_at=now, result_bundle_id=checkpoint.bundle_id,
            )
            bundle = MaterialBundleAssembler().assemble(
                plan, run, assets, tuple(matches), bundle_id=checkpoint.bundle_id,
            )
            generated.record["bundle_intake"] = {
                "before_revision": checkpoint.revision, "after_revision": bundle.revision,
                "supply_run": run.model_dump(mode="json"),
            }
            store.write_generation_record(generated.generation_id, generated.record)
        readiness, gaps = MaterialReadinessCalculator(store=store).calculate(plan, bundle)
        updated_gate = MaterialGateIntegration().record(
            attempt, plan, bundle, run, readiness, gaps,
        )
        return {
            "generation": {
                "generation_id": generated.generation_id,
                "request_id": generated.generation_id,
                "task_id": generated.task_id if generated.record.get("modality", "video") == "video" else None,
                "provider": "minimax",
                "modality": generated.record.get("modality", "video"),
                "model": model,
                "asset_id": generated.asset.asset_id,
                "asset_sha256": generated.asset.file.sha256,
                "asset_mime": generated.asset.file.mime,
                "technical_status": generated.asset.technical.status.value,
                "rights_status": generated.asset.rights.status.value,
                "billing": generated.record["billing"],
                "provider_usage": generated.record.get("provider_usage", {}),
                "input_sha256": generated.record.get("input_sha256", generated.record.get("prompt_sha256")),
                "operator_confirmed_paid": generated.record.get("operator_confirmed_paid", True),
                "voice_id": generated.record.get("voice_id"),
            },
            "material_gate": {
                "status": updated_gate["status"],
                "readiness": updated_gate["readiness"].model_dump(mode="json"),
                "gaps": [gap.model_dump(mode="json") for gap in updated_gate["gaps"]],
            },
            "attempt": updated_gate["attempt"],
        }

    def generate_minimax_video(
        self,
        attempt_id: str,
        *,
        need_id: str,
        request_id: str,
        confirmed_paid: bool,
    ) -> dict[str, Any]:
        """Compatibility entry point for callers of the original Video-only route."""
        return self.generate_minimax_asset(
            attempt_id, need_id=need_id, request_id=request_id, confirmed_paid=confirmed_paid,
        )

    def generated_material_rights_candidates(self, attempt_id: str) -> list[dict[str, Any]]:
        """Expose only current, complete MiniMax Assets for factual operator review."""
        from easel.integrations.hypit.service import get_film_attempt

        attempt = get_film_attempt(attempt_id)
        if attempt.get("material_planning", {}).get("status") != "PLANNING_READY":
            return []
        planning = PlanningIntegration().load(attempt)
        plan: MaterialPlan = planning["plan"]
        store = AttemptMaterialStore(_workspace(attempt))
        try:
            bundle = store.read_bundle()
        except AttemptMaterialStoreError:
            return []
        if bundle.plan_id != plan.plan_id:
            raise MaterialIntegrationError("Material Bundle does not match the current Plan")
        needs = {need.need_id: need for need in plan.needs}
        records: dict[str, dict[str, object]] = {}
        for record in store.list_generation_records():
            if (record.get("schema") == "easel-material-generation@1"
                    and record.get("status") == "COMPLETE"
                    and record.get("attempt_id") == attempt_id
                    and record.get("plan_id") == plan.plan_id
                    and record.get("plan_revision") == MaterialReadinessCalculator.plan_revision(plan)):
                asset_id = record.get("asset_id")
                if isinstance(asset_id, str):
                    records[asset_id] = record
        candidates = []
        for asset in bundle.assets:
            record = records.get(asset.asset_id)
            need_id = record.get("need_id") if record else None
            need = needs.get(need_id) if isinstance(need_id, str) else None
            if (record is None or need is None or asset.source.kind != "generative"
                    or asset.source.provider != "minimax" or asset.media_type is not need.media_type
                    or record.get("asset_path") != asset.file.path
                    or record.get("asset_sha256") != asset.file.sha256
                    or record.get("asset_bytes") != asset.file.size
                    or asset.technical.status is not TechnicalStatus.PASSED):
                continue
            try:
                path = store.resolve_asset_locator(asset.file.path)
                digest = hashlib.sha256()
                size = 0
                with path.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                        size += len(chunk)
            except (AttemptMaterialStoreError, OSError):
                continue
            if digest.hexdigest() != asset.file.sha256 or size != asset.file.size:
                continue
            candidates.append({
                "asset_id": asset.asset_id,
                "asset_sha256": asset.file.sha256,
                "media_type": asset.media_type.value,
                "need_id": need.need_id,
                "need_description": need.intent.description,
                "generation_id": record.get("generation_id"),
                "rights": asset.rights.model_dump(mode="json"),
                "technical": asset.technical.model_dump(mode="json"),
                "reviewed": asset.rights.reviewed_at is not None,
            })
        return candidates

    def material_rights_candidates(self, attempt_id: str) -> list[dict[str, Any]]:
        """List byte-verified assets in the current Plan/Bundle for factual Rights review."""
        from easel.integrations.hypit.service import get_film_attempt
        from easel.materials.application.matching import MaterialMatcher
        from easel.materials.application.visual_observation import observed_match
        from easel.materials.application.voice_delivery import voice_content_observed
        from easel.materials.domain import SemanticField

        def presence(asset, need, field):
            evidence = MaterialMatcher._annotations(asset, field, need)
            return any(MaterialMatcher._is_present(item.value) for item in evidence) if evidence else None

        attempt = get_film_attempt(attempt_id)
        if attempt.get("material_planning", {}).get("status") != "PLANNING_READY":
            return []
        planning = PlanningIntegration().load(attempt)
        plan: MaterialPlan = planning["plan"]
        store = AttemptMaterialStore(_workspace(attempt))
        try:
            bundle = store.read_bundle()
        except AttemptMaterialStoreError:
            return []
        gate = attempt.get("material_gate", {})
        if (bundle.plan_id != plan.plan_id
                or gate.get("bundle_id") != bundle.bundle_id
                or gate.get("bundle_revision") != bundle.revision):
            raise MaterialIntegrationError("Material Rights candidates require the current Plan and Gate Bundle")
        needs_by_media = {
            media_type: [need for need in plan.needs if need.media_type is media_type]
            for media_type in {need.media_type for need in plan.needs}
        }
        candidates: list[dict[str, Any]] = []
        for asset in bundle.assets:
            compatible_needs = needs_by_media.get(asset.media_type, [])
            if not compatible_needs or asset.technical.status is not TechnicalStatus.PASSED:
                continue
            try:
                path = store.resolve_asset_locator(asset.file.path)
                digest = hashlib.sha256()
                size = 0
                with path.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                        size += len(chunk)
            except (AttemptMaterialStoreError, OSError):
                continue
            if digest.hexdigest() != asset.file.sha256 or size != asset.file.size:
                continue
            candidates.append({
                "asset_id": asset.asset_id,
                "asset_sha256": asset.file.sha256,
                "media_type": asset.media_type.value,
                "provider": asset.source.provider,
                "source_kind": asset.source.kind,
                "source_page": asset.source.source_page,
                "creator": asset.source.creator,
                "needs": [{
                    "need_id": need.need_id,
                    "description": need.intent.description,
                    "constraints": {key: need.constraints[key] for key in ("logo", "text_in_frame")
                                    if key in need.constraints},
                    "logo_present": presence(asset, need, SemanticField.LOGO),
                    "visible_text_present": presence(asset, need, SemanticField.VISIBLE_TEXT),
                } for need in compatible_needs],
                "rights": asset.rights.model_dump(mode="json"),
                "rights_blocking_need_ids": [need.need_id for need in compatible_needs
                    if RightsService().evaluate(asset, need,
                        attribution=RightsService.attribution_condition_for(asset)).status
                    is RightsAdmissionStatus.BLOCKED],
                "generation_need_ids": [need.need_id for need in compatible_needs
                    if getattr(need.modality_spec, "kind", None) == "voice"
                    and self._bound_voice_generation(attempt, plan, need, asset, store)],
                "semantic_reviewed_need_ids": [need.need_id for need in compatible_needs
                    if MaterialMatcher._creator_match_review(need, asset)],
                "system_observed_need_ids": [need.need_id for need in compatible_needs
                    if observed_match(need, asset) is True or voice_content_observed(need, asset)],
                "reviewed": asset.rights.reviewed_at is not None,
            })
        return candidates

    @staticmethod
    def _bound_voice_generation(attempt, plan, need, asset, store) -> bool:
        """Keep narration review bound to its frozen script and unchanged Need."""
        current_revision = MaterialReadinessCalculator.plan_revision(plan)
        for record in store.list_generation_records():
            if (record.get("schema") != "easel-material-generation@1"
                    or record.get("status") != "COMPLETE"
                    or record.get("attempt_id") != attempt["attempt_id"]
                    or record.get("plan_id") != plan.plan_id or record.get("need_id") != need.need_id
                    or record.get("input_sha256") != need.modality_spec.text_sha256
                    or record.get("asset_id") != asset.asset_id
                    or record.get("asset_sha256") != asset.file.sha256
                    or record.get("asset_path") != asset.file.path
                    or record.get("asset_bytes") != asset.file.size
                    or asset.source.kind != "generative"):
                continue
            if record.get("plan_revision") == current_revision:
                return True
            recovery_ref = attempt.get("material_recovery", {})
            recovery_id = recovery_ref.get("request_id")
            recovery = store.read_recovery_record(recovery_id) if recovery_id else None
            if (recovery and recovery.get("status") == "COMPLETE"
                    and recovery.get("target_plan_revision") == current_revision):
                previous = MaterialPlan.model_validate_json(json.dumps(recovery["source_plan"]))
                if (MaterialReadinessCalculator.plan_revision(previous) == record.get("plan_revision")
                        and next((n for n in previous.needs if n.need_id == need.need_id), None) == need):
                    return True
        return False

    def review_material_match(self, attempt_id: str, **review) -> dict[str, Any]:
        attempt, plan, bundle, store, asset = self._prepare_material_match_review(attempt_id, **review)
        store.write_asset(asset)
        return self._recalculate_observed_materials(attempt, plan, bundle, store)

    def _prepare_material_match_review(
        self, attempt_id: str, *, asset_id: str, expected_sha256: str,
        need_id: str, observed_content: str, logo_present: bool | None,
        visible_text_present: bool | None, confirm_review: bool,
        voice_recognition_review: dict | None = None,
    ) -> tuple:
        """Bind a Creator observation to one visual or script-bound narration Asset."""
        from easel.integrations.hypit.service import get_film_attempt
        from easel.materials.application.intelligence import IntelligenceStatus
        from easel.materials.domain import SemanticAnnotation, SemanticField, SemanticInference

        if confirm_review is not True or not isinstance(observed_content, str) or len(observed_content.strip()) < 8:
            raise MaterialIntegrationError("素材匹配复核需要具体观察或试听结论和明确确认")
        attempt = get_film_attempt(attempt_id)
        planning = PlanningIntegration().load(attempt)
        plan: MaterialPlan = planning["plan"]
        need = next((item for item in plan.needs if item.need_id == need_id), None)
        if need is None or (need.media_type not in {MediaType.IMAGE, MediaType.VIDEO}
                            and getattr(need.modality_spec, "kind", None) not in {"voice", "bgm"}):
            raise MaterialIntegrationError("素材匹配复核仅接受当前视觉、旁白或配乐 Need")
        candidates = self.material_rights_candidates(attempt_id)
        candidate = next((item for item in candidates if item["asset_id"] == asset_id
                          and item["asset_sha256"] == expected_sha256), None)
        if candidate is None:
            raise MaterialIntegrationError("视觉匹配复核仅接受当前 Bundle 中字节校验通过的素材")
        if need.constraints.get("logo") is False and logo_present is None:
            raise MaterialIntegrationError("no-logo 约束需要明确的画面核对结论")
        if need.constraints.get("text_in_frame") is False and visible_text_present is None:
            raise MaterialIntegrationError("画面文字约束需要明确的画面核对结论")

        store = AttemptMaterialStore(_workspace(attempt))
        bundle = store.read_bundle()
        asset = store.read_asset(asset_id)
        if asset.file.sha256 != expected_sha256:
            raise MaterialIntegrationError("素材 SHA-256 已变化，请刷新后重新核验")
        if getattr(need.modality_spec, "kind", None) == "voice" and not self._bound_voice_generation(
                attempt, plan, need, asset, store):
            raise MaterialIntegrationError("旁白必须绑定当前冻结脚本、生成记录与未改变的素材需求")
        evidence = f"creator-confirmed:{need_id}:{expected_sha256}"
        annotations = [SemanticAnnotation(
            field=SemanticField.CAPTION, value=observed_content.strip(),
            evidence=evidence, confidence=1.0,
        )]
        if logo_present is not None:
            annotations.append(SemanticAnnotation(field=SemanticField.LOGO, value=logo_present,
                                                  evidence=evidence, confidence=1.0))
        if visible_text_present is not None:
            annotations.append(SemanticAnnotation(field=SemanticField.VISIBLE_TEXT,
                                                  value=("visible text" if visible_text_present else ()),
                                                  evidence=evidence, confidence=1.0))
        inference = SemanticInference(
            analyzer_id=f"creator-match:{need_id}", status=IntelligenceStatus.COMPLETE,
            annotations=tuple(annotations), observed_at=datetime.now(timezone.utc),
        )
        retained = tuple(item for item in asset.semantic.inferences if item.analyzer_id != inference.analyzer_id)
        reviewed_asset = asset.model_copy(update={
            "semantic": asset.semantic.model_copy(update={"inferences": retained + (inference,)}),
        })
        if voice_recognition_review is not None:
            from easel.materials.application.voice_delivery import (
                VOICE_ASR_REVIEW_PREFIX, recognition_digest, timing_from_recognition)
            digest = voice_recognition_review.get('recognition_sha256')
            corrections = voice_recognition_review.get('corrections')
            if (getattr(need.modality_spec, 'kind', None) != 'voice'
                    or not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest)
                    or not isinstance(corrections, list) or not 1 <= len(corrections) <= 20):
                raise MaterialIntegrationError('旁白识别复核需要当前报告身份与具体字符结论')
            report_path = _workspace(attempt) / 'materials/observations' / ('voice-asr-rejected-' + digest + '.json')
            if _has_symlink_components(_workspace(attempt), report_path) or not report_path.is_file():
                raise MaterialIntegrationError('待复核旁白识别报告不存在或路径无效')
            report = json.loads(report_path.read_text())
            binding = {'audio_sha256': asset.file.sha256,
                       'script_sha256': hashlib.sha256(planning['script'].encode()).hexdigest(),
                       'need_sha256': hashlib.sha256(need.to_json().encode()).hexdigest()}
            if recognition_digest(report) != digest or any(report.get(k) != v for k, v in binding.items()):
                raise MaterialIntegrationError('旁白识别复核与当前音频、脚本或 Need 不一致')
            character_reviews, seen = [], set()
            for correction in corrections:
                position = correction.get('character') if isinstance(correction, dict) else None
                text = correction.get('text') if isinstance(correction, dict) else None
                if (type(position) is not int or position in seen or not 0 <= position < len(planning['script'])
                        or text != planning['script'][position] or not text.strip()):
                    raise MaterialIntegrationError('旁白识别复核只接受冻结脚本中的独立字符，不改写脚本')
                seen.add(position)
                evidence = (VOICE_ASR_REVIEW_PREFIX + binding['need_sha256'] + ':' + binding['audio_sha256']
                            + ':' + binding['script_sha256'] + ':' + digest + ':' + str(position))
                character_reviews.append(SemanticInference(
                    analyzer_id=VOICE_ASR_REVIEW_PREFIX + need_id + ':' + str(position),
                    status=IntelligenceStatus.COMPLETE,
                    annotations=(SemanticAnnotation(field=SemanticField.CAPTION, value=text,
                        evidence=evidence, confidence=1.0),), observed_at=datetime.now(timezone.utc)))
            review_ids = {i.analyzer_id for i in character_reviews}
            retained_reviews = tuple(i for i in reviewed_asset.semantic.inferences if i.analyzer_id not in review_ids)
            reviewed_asset = reviewed_asset.model_copy(update={'semantic': reviewed_asset.semantic.model_copy(
                update={'inferences': retained_reviews + tuple(character_reviews)})})
            # Human review covers named characters only. Confidence, completeness,
            # actual time bounds and every other character still have to pass.
            timing_from_recognition(planning['script'], reviewed_asset, report)
        return attempt, plan, bundle, store, reviewed_asset

    def review_material_combination(self, attempt_id: str, *, plan_revision: str, bundle_revision: str,
                                   reviews: list[dict], confirm_review: bool) -> dict:
        """Preflight the entire choice before persisting any human evidence."""
        from easel.integrations.material_recovery import _production_started
        from easel.integrations.hypit.service import get_film_attempt
        from easel.materials.application.visual_observation import need_identity
        attempt = get_film_attempt(attempt_id)
        store = AttemptMaterialStore(_workspace(attempt))
        payload = {'plan_revision': plan_revision, 'bundle_revision': bundle_revision,
                   'reviews': reviews, 'confirm_review': confirm_review}
        request_id = 'combination-' + hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        prior = store.read_recovery_record(request_id)
        if prior is not None:
            return self.finish_material_combination(attempt_id, request_id=request_id)
        if attempt.get('material_combination_review', {}).get('status') == 'PENDING':
            raise MaterialIntegrationError('上一组素材接受正在保存，请等待状态更新')
        if confirm_review is not True or not reviews or _production_started(attempt):
            raise MaterialIntegrationError('只可在编排开始前明确接受当前素材组合')
        planning = PlanningIntegration().load(attempt)
        if planning['truth_ledger']['status'] != 'PASSED':
            raise MaterialIntegrationError('仍有未解决的内容事实事项，素材组合接受不能替代事实核验')
        plan, bundle = planning['plan'], store.read_bundle()
        if (MaterialReadinessCalculator.plan_revision(plan) != plan_revision
                or bundle.revision != bundle_revision
                or attempt.get('material_gate', {}).get('bundle_revision') != bundle_revision):
            raise MaterialIntegrationError('方案或素材组合已更新，请刷新后重新核对')
        ids = [r.get('need_id') for r in reviews]
        supported = {n.need_id: n for n in plan.needs if n.media_type in {MediaType.IMAGE, MediaType.VIDEO}
                     or getattr(n.modality_spec, 'kind', None) in {'voice', 'bgm'}}
        required = {key for key, n in supported.items() if n.importance is NeedImportance.REQUIRED}
        if len(set(ids)) != len(ids) or not required.issubset(ids) or set(ids) - set(supported):
            raise MaterialIntegrationError('组合须覆盖每个必需画面、旁白和配乐，各场景只能选一项')
        staged = {}
        for review in reviews:
            if review.get('voice_recognition_review') is not None:
                raise MaterialIntegrationError('指定字符的旁白识别复核须保留原独立证据入口')
            _, _, _, _, reviewed = self._prepare_material_match_review(attempt_id, **review, confirm_review=True)
            need = supported[review['need_id']]
            if reviewed.media_type is not need.media_type:
                raise MaterialIntegrationError('所选素材类型与当前场景不一致')
            # The formal Creator evidence is scoped to the full Need as well
            # as bytes; later edits cannot inherit this combination decision.
            inference = next(i for i in reviewed.semantic.inferences if i.analyzer_id == 'creator-match:' + need.need_id)
            inference = inference.model_copy(update={'annotations': tuple(a.model_copy(update={
                'evidence': a.evidence + ':need=' + need_identity(need)}) for a in inference.annotations)})
            base = staged.get(reviewed.asset_id, store.read_asset(reviewed.asset_id))
            inferences = tuple(i for i in base.semantic.inferences if i.analyzer_id != inference.analyzer_id) + (inference,)
            staged[reviewed.asset_id] = base.model_copy(update={'semantic': base.semantic.model_copy(update={'inferences': inferences})})
        journal = {'status': 'PENDING', 'plan_revision': plan_revision,
                   'choices': {r['need_id']: {'asset_id': r['asset_id'], 'sha256': r['expected_sha256']} for r in reviews},
                   'bundle': bundle.model_dump(mode='json'),
                   'original_assets': {a.asset_id: store.read_asset(a.asset_id).model_dump(mode='json') for a in bundle.assets},
                   'reviewed_assets': {key: a.model_dump(mode='json') for key, a in staged.items()}}
        store.write_recovery_record(request_id, journal)
        return self.finish_material_combination(attempt_id, request_id=request_id)

    def finish_material_combination(self, attempt_id: str, *, request_id: str | None = None) -> dict:
        """Finish the same saved human decision; never prompt or buy again."""
        from easel.integrations.hypit.service import get_film_attempt
        attempt = get_film_attempt(attempt_id)
        request_id = request_id or attempt.get('material_combination_review', {}).get('request_id')
        store = AttemptMaterialStore(_workspace(attempt))
        journal = store.read_recovery_record(request_id) if request_id else None
        if not journal:
            raise MaterialIntegrationError('素材组合接受检查点缺失')
        if journal['status'] == 'COMPLETE':
            if attempt.get('material_combination_review') == {'status': 'PENDING', 'request_id': request_id}:
                attempt = _update_attempt(attempt, material_combination_review={'status': 'COMPLETE', 'request_id': request_id})
            return {'material_status': attempt.get('material_gate', {}).get('status'), 'attempt': attempt}
        plan = PlanningIntegration().load(attempt)['plan']
        if MaterialReadinessCalculator.plan_revision(plan) != journal['plan_revision']:
            raise MaterialIntegrationError('组合接受期间方案变化，不能沿用旧决定')
        bundle = MaterialBundle.model_validate_json(json.dumps(journal['bundle']))
        if {a.asset_id for a in store.read_bundle().assets} != set(journal['original_assets']):
            raise MaterialIntegrationError('组合接受期间候选集合变化，请重新核对')
        for asset_id, original in journal['original_assets'].items():
            current = store.read_asset(asset_id)
            target = journal['reviewed_assets'].get(asset_id, original)
            if current.model_dump(mode='json') not in (original, target):
                raise MaterialIntegrationError('组合接受期间素材证据变化，未覆盖新记录')
            path = store.resolve_asset_locator(current.file.path)
            if path.stat().st_size != current.file.size or hashlib.sha256(path.read_bytes()).hexdigest() != current.file.sha256:
                raise MaterialIntegrationError('组合接受期间素材字节变化，不能继续')
        attempt = _update_attempt(attempt, material_combination_review={'status': 'PENDING', 'request_id': request_id})
        for raw in journal['reviewed_assets'].values():
            store.write_asset(MaterialAsset.model_validate_json(json.dumps(raw)))
        result = self._recalculate_observed_materials(attempt, plan, bundle, store, require_scoped_visual=True)
        store.write_recovery_record(request_id, {**journal, 'status': 'COMPLETE'})
        result['attempt'] = _update_attempt(result['attempt'],
            material_combination_review={'status': 'COMPLETE', 'request_id': request_id})
        return result

    @staticmethod
    def _recalculate_observed_materials(attempt, plan, bundle, store, *, require_scoped_visual=False) -> dict[str, Any]:
        """Re-rank existing bytes; observation is never another supply request."""
        from easel.materials.application.assembly import MaterialBundleAssembler
        from easel.materials.application.dedup import MaterialDeduplicator
        from easel.materials.application.matching import MaterialMatcher
        from easel.materials.application.visual_observation import observed_match

        old_run = store.read_supply_run(bundle.supply_run_id)
        assets = tuple(store.read_asset(item.asset_id) for item in bundle.assets)
        matcher = MaterialMatcher()
        deduplicator = MaterialDeduplicator(store)
        matches = []
        marker = attempt.get('material_combination_review', {})
        journal = store.read_recovery_record(marker['request_id']) if marker.get('request_id') else None
        choices = journal['choices'] if journal and journal['plan_revision'] == MaterialReadinessCalculator.plan_revision(plan) else {}
        for current_need in plan.needs:
            eligible = assets
            if require_scoped_visual and current_need.media_type in {MediaType.IMAGE, MediaType.VIDEO}:
                eligible = tuple(a for a in assets if observed_match(current_need, a) is True
                                 or matcher._creator_match_review(current_need, a))
            ranked = matcher.match(current_need, eligible)
            shortlist = list(deduplicator.deduplicate_and_diversify(
                ranked.matches, assets, top_k=3,
            ).shortlist)
            chosen = choices.get(current_need.need_id, {}).get('asset_id')
            chosen_match = next((m for m in ranked.matches if m.asset_id == chosen), None)
            if chosen_match and not any(m.asset_id == chosen for m in shortlist):
                shortlist = shortlist[:2] + [chosen_match]
            matches.extend(shortlist)
        digest = hashlib.sha256("\n".join(asset.to_json() for asset in assets).encode()).hexdigest()[:16]
        now = datetime.now(timezone.utc)
        reviewed_run = SupplyRun(
            supply_run_id=f"match-{bundle.supply_run_id[-40:]}-{digest}",
            plan_id=plan.plan_id, parent_run_id=old_run.supply_run_id,
            started_at=now, finished_at=now, result_bundle_id=bundle.bundle_id,
        )
        revised_bundle = MaterialBundleAssembler().assemble(
            plan, reviewed_run, assets, tuple(matches), bundle_id=bundle.bundle_id,
        )
        readiness, gaps = MaterialReadinessCalculator(store=store).calculate(plan, revised_bundle)
        gate = MaterialGateIntegration().record(
            attempt, plan, revised_bundle, reviewed_run, readiness, gaps,
        )
        accepted_qualified = all(any(m.need_id == need_id and m.asset_id == c['asset_id'] and m.qualified
                                    for m in revised_bundle.matches) for need_id, c in choices.items())
        authoring = (ProductionAuthoringIntegration().prepare(gate["attempt"], selected_asset_ids=())
                     if readiness.status is ReadinessStatus.READY and accepted_qualified else None)
        updated = authoring["attempt"] if authoring else gate["attempt"]
        return {"material_status": gate["status"], "attempt": updated,
                "readiness": readiness.model_dump(mode="json")}

    def observe_visual_materials(self, attempt_id: str, *, executor, group_executor=None) -> dict[str, Any]:
        """Observe current candidates and admit evidenced commissioned usage."""
        from easel.integrations.hypit.service import get_film_attempt
        from easel.materials.application.matching import MaterialMatcher
        from easel.materials.application.visual_observation import (
            MAX_VISUAL_CANDIDATES, apply_observation, observed_match, prepare_observation, scoped_inference,
            read_observation_report, observe_shared_asset,
        )

        attempt = get_film_attempt(attempt_id)
        planning = PlanningIntegration().load(attempt)
        plan = planning['plan']
        store = AttemptMaterialStore(_workspace(attempt))
        bundle = store.read_bundle()
        candidates = self.material_rights_candidates(attempt_id)
        verified = {c["asset_id"] for c in candidates}
        revision = attempt.get('revision_feedback', {})
        visual_repair = (revision.get('origin') == 'system_quality'
                         and 'visual_material' in revision.get('allowed_changes', []))
        excluded = {}
        if visual_repair:
            from easel.integrations.hypit.service import _execution_fingerprint
            from easel.integrations.hypit.revision import quality_protected_sources
            source = get_film_attempt(attempt['retry_source']['attempt_id'])
            if (source['creation_id'] != attempt['creation_id']
                    or PlanningIntegration().load(source)['plan'].needs != plan.needs
                    or _execution_fingerprint(source)['sha256'] != attempt['retry_source']['fingerprint']):
                raise MaterialIntegrationError('原成片或素材需求已变化，不能沿用修复观察')
            protected = quality_protected_sources(_workspace(source) / 'productions/easel-authoring/authors/main.svml')
            selected_ids = set(source['production_authoring']['selected_asset_ids'])
            for candidate in ProductionAuthoringIntegration().qualified_authoring_assets(source):
                if (candidate['asset_id'] in selected_ids and candidate['media_type'] in {'image', 'video'}
                        and candidate['src'] not in protected):
                    for need_id in candidate['qualified_need_ids']:
                        excluded.setdefault(need_id, set()).add(candidate['asset_id'])
        from easel.creation_delivery import active_delivery
        from easel.integrations.material_generation import commission_generated_rights
        generated_records = {}
        work = None
        needs = {n.need_id: n for n in plan.needs}
        if active_delivery.get() == attempt['creation_id']:
            work = creation.get_creation(attempt['creation_id'])
            generated_records = {r['asset_id']: r for r in store.list_generation_records()
                if isinstance(r.get('generation_id'), str)
                and r.get('asset_id') in verified and r.get('need_id') in needs}

        def admit_generated(asset_id):
            record = generated_records.get(asset_id)
            if record is None:
                return
            with store.generation_lock(record['generation_id']):
                if store.read_generation_record(record['generation_id']) != record:
                    raise MaterialIntegrationError('生成素材证据已变化，请重新核对')
                asset = store.read_asset(asset_id)
                rights = commission_generated_rights(work, plan, needs[record['need_id']], asset, record, planning['script'])
                if rights is not None:
                    if store.read_asset(asset.asset_id) != asset:
                        raise MaterialIntegrationError('生成素材证据已变化，未覆盖新记录')
                    RightsService(store).record(asset, rights)

        for asset_id in generated_records:
            admit_generated(asset_id)
        matcher = MaterialMatcher()
        # Keep the saved batch identity: upgrades must not reshuffle work that
        # already dispatched. Only newly nominated batches use this ranking.
        batch_key = hashlib.sha256(("ranked-v2\n" + MaterialReadinessCalculator.plan_revision(plan) + "\n"
            + "\n".join(sorted(a.asset_id + ":" + a.file.sha256 for a in bundle.assets))
            + ('\nalternatives:' + revision['quality_report_sha256'] if visual_repair else '')).encode()).hexdigest()
        batch_relative = f"materials/observations/batch-{batch_key}.json"
        batch_path = _workspace(attempt) / batch_relative
        if _has_symlink_components(_workspace(attempt), batch_path):
            raise MaterialIntegrationError("素材观察路径无效")
        if batch_path.is_file():
            pairs = json.loads(batch_path.read_text())
        else:
            pairs = {}
            for need in plan.needs:
                if (need.media_type not in {MediaType.IMAGE, MediaType.VIDEO}
                        or (visual_repair and need.need_id not in excluded)):
                    continue
                assets = [a for a in bundle.assets if a.asset_id in verified and a.media_type is need.media_type
                          and a.asset_id not in excluded.get(need.need_id, ())
                          and a.technical.status is TechnicalStatus.PASSED
                          and a.rights.status is not RightsStatus.RESTRICTED]
                scores = {a.asset_id: matcher._soft_scores(need, a) for a in assets}
                assets.sort(key=lambda a: (
                    any(scoped_inference(need, a, i) for i in a.semantic.inferences) and observed_match(need, a) is not True,
                    RightsService().evaluate(a, need, attribution=RightsService.attribution_condition_for(a)).status
                    is RightsAdmissionStatus.BLOCKED,
                    -(scores[a.asset_id][0].semantic or 0),
                    -scores[a.asset_id][1], a.asset_id))
                pairs[need.need_id] = [a.asset_id for a in assets[:MAX_VISUAL_CANDIDATES]]
            # Freeze nominated candidates before the first model dispatch.
            # New evidence must not reshuffle a resumed batch into more calls.
            store.write_observation_record(f"batch-{batch_key}", pairs)
        reports = []
        for need in plan.needs:
            if need.media_type not in {MediaType.IMAGE, MediaType.VIDEO}:
                continue
            selected = pairs.get(need.need_id, [])
            if (not isinstance(selected, list) or len(selected) > MAX_VISUAL_CANDIDATES or len(set(selected)) != len(selected)
                    or any(a not in verified for a in selected)):
                raise MaterialIntegrationError("当前素材字节与已保存的观察候选不一致")
            for asset_id in selected:
                # Readiness needs a usable choice, not exhaustive review of the
                # whole pool. Preserve independent evidence for each Need.
                usable = tuple(store.read_asset(a.asset_id) for a in bundle.assets
                               if a.asset_id in verified and a.asset_id not in excluded.get(need.need_id, ()))
                usable = tuple(a for a in usable if observed_match(need, a) is True
                               or matcher._creator_match_review(need, a))
                if matcher.match(need, usable).matches:
                    break
                asset = store.read_asset(asset_id)
                if matcher._creator_match_review(need, asset):
                    continue
                path = store.resolve_asset_locator(asset.file.path)
                manifest, attachments = prepare_observation(need, asset, path)
                relative = f"materials/observations/{manifest['input_sha256']}.json"
                report_path = _workspace(attempt) / relative
                if _has_symlink_components(_workspace(attempt), report_path):
                    raise MaterialIntegrationError("素材观察路径无效")
                report = None
                if report_path.is_file():
                    try:
                        report = read_observation_report(report_path, need, asset, manifest)
                    except (OSError, ValueError, TypeError, AttributeError):
                        # A completed model run may have written invalid JSON or
                        # stale evidence. Resume its bounded report repair below.
                        pass
                if report is None:
                    # Pending gateway calls escape to the durable owner. Never
                    # turn an uncertain model run into a failed observation.
                    if group_executor is not None:
                        # Use frozen nominations, not each scene's evolving
                        # readiness: otherwise a resumed group changes identity.
                        shared_needs = [n for n in plan.needs if asset_id in pairs.get(n.need_id, [])]
                        report = observe_shared_asset(attempt, need, asset, manifest, attachments,
                            shared_needs, store, batch_key, group_executor)
                    else:
                        report = executor(attempt, manifest, attachments)
                    store.write_observation_record(manifest["input_sha256"], report)
                current = store.read_asset(asset.asset_id)
                if current.file != asset.file:
                    raise MaterialIntegrationError("素材在观察期间发生变化，不能登记旧证据")
                observed = apply_observation(need, current, manifest, report)
                # Reusing valid evidence must not manufacture a new timestamp
                # and bundle revision at every owner restart.
                if not any(scoped_inference(need, current, i, manifest["input_sha256"])
                           for i in current.semantic.inferences):
                    store.write_asset(observed)
                store.write_observation_record(manifest["input_sha256"] + ".input", manifest)
                admit_generated(asset_id)
                reports.append(relative)
        current_attempt = get_film_attempt(attempt_id)
        if active_delivery.get() == attempt['creation_id']:
            from easel.materials.application.music_observation import (
                MODEL_REVISION, SCHEMA as MUSIC_SCHEMA, apply_music_observation, read_local_music, file_digest,
            )
            for need in plan.needs:
                if getattr(need.modality_spec, 'kind', None) != 'bgm':
                    continue
                candidates = [a for a in bundle.assets if a.asset_id in verified and a.media_type is MediaType.AUDIO
                              and a.technical.duration_seconds is not None and 1 <= a.technical.duration_seconds <= 300]
                candidates.sort(key=lambda a: (-matcher._soft_scores(need, a)[1], a.asset_id))
                for candidate in candidates[:MAX_VISUAL_CANDIDATES]:
                    available = tuple(store.read_asset(a.asset_id) for a in candidates)
                    if matcher.match(need, available).matches:
                        break
                    asset = store.read_asset(candidate.asset_id)
                    identity = 'music-' + hashlib.sha256((MUSIC_SCHEMA + MODEL_REVISION + asset.file.sha256).encode()).hexdigest()
                    report_path = _workspace(attempt) / 'materials/observations' / (identity + '.json')
                    if _has_symlink_components(_workspace(attempt), report_path):
                        raise MaterialIntegrationError('配乐观察路径无效')
                    path = store.resolve_asset_locator(asset.file.path)
                    if report_path.is_file():
                        report = json.loads(report_path.read_text())
                    else:
                        report = read_local_music(path)
                        apply_music_observation(need, asset, report)
                        store.write_observation_record(identity, report)
                    if store.read_asset(asset.asset_id).file != asset.file or file_digest(path) != asset.file.sha256:
                        raise MaterialIntegrationError('配乐观察期间素材已变化，未使用旧结论')
                    observed = apply_music_observation(need, asset, report)
                    # A saved report survives a crash before Asset/Bundle registration.
                    if asset.semantic.inferences != observed.semantic.inferences:
                        store.write_asset(observed)
        current_plan = PlanningIntegration().load(current_attempt)["plan"]
        if current_plan != plan or store.read_bundle() != bundle:
            raise MaterialIntegrationError("素材观察期间方案或候选发生变化；保留证据并重新核对")
        result = self._recalculate_observed_materials(current_attempt, plan, bundle, store,
                                                    require_scoped_visual=True)
        result["attempt"] = _update_attempt(result["attempt"], material_observation={
            "status": "COMPLETE", "plan_revision": result["attempt"]["material_gate"]["plan_revision"],
            "bundle_revision": result["attempt"]["material_gate"]["bundle_revision"],
            "reports": reports, "updated_at": creation._now(),
            **({'quality_report_sha256': revision['quality_report_sha256']} if visual_repair else {}),
        })
        return result

    def review_material_rights(
        self,
        attempt_id: str,
        *,
        asset_id: str,
        expected_sha256: str,
        rights: RightsInfo,
        confirm_review: bool,
        source_creator: str | None = None,
        source_page: str | None = None,
    ) -> dict[str, Any]:
        """Record operator-supplied rights facts and locally recompute the ordinary Gate."""
        from easel.integrations.hypit.service import get_film_attempt

        if confirm_review is not True:
            raise MaterialIntegrationError("必须明确确认已核验该素材的权利来源和证据")
        if not rights.evidence:
            raise MaterialIntegrationError("Rights review 必须提供至少一条可追溯证据")
        attempt = get_film_attempt(attempt_id)
        planning = PlanningIntegration().load(attempt)
        candidates = self.material_rights_candidates(attempt_id)
        candidate = next((item for item in candidates if item["asset_id"] == asset_id), None)
        if candidate is None:
            raise MaterialIntegrationError("Rights review 仅接受当前 Plan/Gate Bundle 中字节校验通过的素材")
        if candidate["asset_sha256"] != expected_sha256:
            raise MaterialIntegrationError("素材 SHA-256 已变化，请刷新后重新核验")

        store = AttemptMaterialStore(_workspace(attempt))
        plan: MaterialPlan = planning["plan"]
        bundle = store.read_bundle()
        old_run = store.read_supply_run(bundle.supply_run_id)
        current_asset = store.read_asset(asset_id)
        if current_asset.file.sha256 != expected_sha256:
            raise MaterialIntegrationError("素材 SHA-256 已变化，请刷新后重新核验")
        reviewed_rights = rights.model_copy(update={"reviewed_at": datetime.now(timezone.utc)})
        try:
            RightsService(store).record(
                current_asset, reviewed_rights, source_creator=source_creator, source_page=source_page,
            )
        except (AttemptMaterialStoreError, OSError, ValueError) as exc:
            raise MaterialIntegrationError(f"Rights evidence could not be safely recorded: {exc}") from exc

        assets = tuple(store.read_asset(item.asset_id) for item in bundle.assets)
        from easel.materials.application.assembly import MaterialBundleAssembler
        from easel.materials.application.dedup import MaterialDeduplicator
        from easel.materials.application.matching import MaterialMatcher

        matches = []
        matcher = MaterialMatcher()
        deduplicator = MaterialDeduplicator(store)
        for need in plan.needs:
            ranked = matcher.match(need, assets)
            matches.extend(deduplicator.deduplicate_and_diversify(
                ranked.matches, assets, top_k=3,
            ).shortlist)

        review_digest = hashlib.sha256(
            (asset_id + "\0" + expected_sha256 + "\0" + reviewed_rights.to_json()).encode("utf-8")
        ).hexdigest()[:16]
        run_id = f"rights-{bundle.supply_run_id[-40:]}-{review_digest}"
        reviewed_run = SupplyRun(
            supply_run_id=run_id,
            plan_id=plan.plan_id,
            parent_run_id=old_run.supply_run_id,
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            result_bundle_id=bundle.bundle_id,
        )
        revised_bundle = MaterialBundleAssembler().assemble(
            plan, reviewed_run, assets, tuple(matches), bundle_id=bundle.bundle_id,
        )
        readiness, gaps = MaterialReadinessCalculator(store=store).calculate(plan, revised_bundle)
        gate = MaterialGateIntegration().record(
            attempt, plan, revised_bundle, reviewed_run, readiness, gaps,
        )
        authoring = None
        if readiness.status is ReadinessStatus.READY:
            authoring = ProductionAuthoringIntegration().prepare(
                gate["attempt"], selected_asset_ids=(),
            )
        updated_attempt = authoring["attempt"] if authoring else gate["attempt"]
        return {
            "asset_id": asset_id,
            "asset_sha256": expected_sha256,
            "rights": store.read_asset(asset_id).rights.model_dump(mode="json"),
            "material_status": gate["status"],
            "material_gate": {
                "status": gate["status"],
                "readiness": readiness.model_dump(mode="json"),
                "gaps": [gap.model_dump(mode="json") for gap in gaps],
            },
            "production_authoring": updated_attempt.get("production_authoring"),
            "attempt": updated_attempt,
        }

    def review_generated_material_rights(
        self,
        attempt_id: str,
        *,
        asset_id: str,
        expected_sha256: str,
        rights: RightsInfo,
        confirm_review: bool,
        source_creator: str | None = None,
        source_page: str | None = None,
    ) -> dict[str, Any]:
        """Review a current generation record without re-running Material Supply."""

        if confirm_review is not True:
            raise MaterialIntegrationError("必须明确确认已核验该素材的权利来源和证据")
        if not rights.evidence:
            raise MaterialIntegrationError("Rights review 必须提供至少一条可追溯证据")
        candidates = self.generated_material_rights_candidates(attempt_id)
        candidate = next((item for item in candidates if item["asset_id"] == asset_id), None)
        if candidate is None:
            raise MaterialIntegrationError("Rights review 仅接受当前 Bundle 中匹配现行 Plan 的 MiniMax 生成素材")
        if candidate["asset_sha256"] != expected_sha256:
            raise MaterialIntegrationError("素材 SHA-256 已变化，请刷新后重新核验")
        return self.review_material_rights(
            attempt_id, asset_id=asset_id, expected_sha256=expected_sha256,
            rights=rights, confirm_review=confirm_review,
            source_creator=source_creator, source_page=source_page,
        )

    def _run(
        self,
        attempt: dict[str, Any],
        local_roots: tuple[str | Path, ...],
        *,
        planning: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if planning is None:
            raise MaterialIntegrationError("正式 Material 生命周期必须提供冻结输入生成的 Creative Planning 结果")
        root = _workspace(attempt)
        plan_data = planning.get("plan")
        plan = plan_data if isinstance(plan_data, MaterialPlan) else MaterialPlan.model_validate(plan_data)
        if plan.creation_id != attempt.get("creation_id") or plan.attempt_id != attempt.get("attempt_id"):
            raise MaterialIntegrationError("Creative Planning MaterialPlan identity does not match Attempt")
        expected_refs = planning.get("context_refs")
        if not isinstance(expected_refs, dict) or plan.context_refs != expected_refs:
            raise MaterialIntegrationError("MaterialPlan does not identify all frozen Planning inputs")
        if isinstance(planning.get("truth_ledger"), dict):
            planning = PlanningIntegration().load(attempt)
            if planning["plan"].plan_id != plan.plan_id:
                raise MaterialIntegrationError("Loaded Planning identity changed before Material Supply")
        else:
            planning = PlanningIntegration().persist(
                attempt,
                plan,
                treatment=planning.get("treatment", ""),
                script=planning.get("script", ""),
                scenes=planning.get("scenes", ""),
                script_assessment=planning.get("script_assessment"),
            )
        attempt = planning["attempt"]
        # Persist binds execution defaults and Voice text identity. Supply must
        # consume that canonical Plan, not the pre-binding model response.
        plan = planning["plan"]
        if planning["truth_ledger"]["status"] != "PASSED":
            return {
                "planning": planning,
                "status": "SCRIPT_TRUTH_REVIEW_REQUIRED",
                "attempt": attempt,
            }
        if attempt.get("material_gate", {}).get("status") == "MATERIAL_READY":
            current_plan, _, current_readiness = MaterialGateIntegration().assert_ready(attempt)
            if current_plan != plan:
                raise MaterialIntegrationError("已完成的 Material checkpoint 与当前 Planning 不一致")
            if attempt.get("production_authoring", {}).get("status") not in {
                "PENDING_SELECTION", "SELECTION_RECORDED", "READY",
            }:
                attempt = ProductionAuthoringIntegration().prepare(
                    attempt, selected_asset_ids=(),
                )["attempt"]
            return {"planning": planning, "status": "MATERIAL_READY",
                    "gate": {"status": "MATERIAL_READY", "readiness": current_readiness,
                             "gaps": ()}, "attempt": attempt}
        from easel.integrations.material_supply import ProductMaterialSupply

        flow = ProductMaterialSupply(
            rights_facts=lambda candidate, asset: self._local_rights_facts(candidate, asset, local_roots),
        )
        suffix = attempt["attempt_id"][-20:]
        supply = flow.run(
            plan, attempt, local_roots=local_roots,
            supply_run_id=f"supply-{suffix}", bundle_id=f"bundle-{suffix}", top_n=3,
        )
        gate = MaterialGateIntegration().record(
            attempt, plan, supply.bundle, supply.supply_run, supply.readiness, supply.gaps,
        )
        attempt = gate["attempt"]
        result: dict[str, Any] = {
            "planning": planning,
            "supply": supply,
            "gate": gate,
            "status": gate["status"],
            "attempt": attempt,
        }
        if supply.readiness.status is not ReadinessStatus.READY:
            return result
        authoring = ProductionAuthoringIntegration().prepare(
            attempt, selected_asset_ids=(),
        )
        result["authoring"] = authoring
        result["attempt"] = authoring["attempt"]
        return result

    @staticmethod
    def _local_rights_facts(candidate: Any, asset: MaterialAsset,
                            roots: tuple[str | Path, ...]) -> RightsInfo | None:
        """Read only explicit, hash-bound Local rights evidence; never infer from location/provider."""
        acquisition = getattr(candidate, "acquisition", None)
        source = getattr(candidate, "source", None)
        if (getattr(source, "provider", None) != "local"
                or getattr(acquisition, "mode", None) != "local_file"
                or not isinstance(getattr(acquisition, "locator", None), str)):
            return None
        source_path = Path(acquisition.locator).expanduser()
        try:
            source_path = source_path.resolve(strict=True)
        except OSError as exc:
            raise MaterialIntegrationError("Local rights evidence source is unavailable") from exc
        permitted_roots = []
        for raw_root in roots:
            try:
                permitted_roots.append(Path(raw_root).expanduser().resolve(strict=True))
            except OSError:
                continue
        if not any(source_path.is_relative_to(root) for root in permitted_roots):
            raise MaterialIntegrationError("Local rights evidence source is outside configured roots")
        sidecar = source_path.with_name(source_path.name + ".rights.json")
        if sidecar.is_symlink():
            raise MaterialIntegrationError("Local per-asset rights sidecar must not be a symlink")
        if not sidecar.exists():
            return None
        if not sidecar.is_file() or sidecar.stat().st_size > 64 * 1024:
            raise MaterialIntegrationError("Local per-asset rights sidecar is unsafe or oversized")
        try:
            payload = json.loads(sidecar.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MaterialIntegrationError("Local per-asset rights sidecar is invalid") from exc
        if (not isinstance(payload, dict) or payload.get("schema") != "easel-local-rights@1"
                or payload.get("asset_sha256") != asset.file.sha256
                or not isinstance(payload.get("rights"), dict)):
            raise MaterialIntegrationError("Local rights sidecar does not bind the acquired Asset bytes")
        try:
            rights = RightsInfo.model_validate_json(
                json.dumps(payload["rights"], ensure_ascii=False, sort_keys=True),
            )
        except ValueError as exc:
            raise MaterialIntegrationError("Local rights facts do not match the RightsInfo contract") from exc
        if rights.status in {RightsStatus.KNOWN, RightsStatus.PUBLIC_DOMAIN,
                             RightsStatus.ATTRIBUTION_REQUIRED} and not rights.evidence:
            raise MaterialIntegrationError("Local positive Rights status requires per-Asset evidence")
        return rights
