"""Explicitly approved Material-owned generated-asset intake."""

from __future__ import annotations

import hashlib
import ipaddress
import math
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from collections.abc import Callable
from urllib.parse import urlencode
from urllib.request import urlopen

from easel.materials.application.acquisition import MaterialAcquirer, RemoteURLPolicy
from easel.materials.application.inspector import TechnicalInspector
from easel.materials.domain import (
    AcquisitionInfo,
    Availability,
    MaterialAsset,
    MaterialNeed,
    MaterialPlan,
    MediaType,
    PreviewInfo,
    RightsEvidence,
    RightsStatus,
    SupplyCandidate,
)
from easel.materials.providers.minimax_video import MiniMaxVideoAdapter, MiniMaxVideoError, MiniMaxVideoObservationPending, is_minimax_media_host
from easel.materials.store import (
    AttemptMaterialStore,
    GenerationRecordNotFound,
)


def retain_generation_rights_evidence(asset: MaterialAsset, record: dict) -> MaterialAsset:
    """Carry request-time facts into the Asset without inventing permission."""
    terms = (record.get('commission_authorization') or {}).get('quote', {}).get('terms_evidence')
    if not terms:
        return asset  # Existing/manual generation has no captured agreement.
    from easel.materials.providers.minimax_pricing import TERMS_URL
    document = terms.get('document')
    if (terms.get('url') != TERMS_URL or not isinstance(document, str)
            or hashlib.sha256(document.encode()).hexdigest() != terms.get('sha256')):
        raise GenerationRequestConflict('生成协议证据身份不一致，不能关联到素材')
    evidence = (
        RightsEvidence(kind='provider_terms', reference=TERMS_URL + '#sha256=' + terms['sha256'],
                       observed_at=datetime.fromisoformat(terms['observed_at']),
                       summary='请求前保存的服务协议；不代表已取得全部输出权利'),
        RightsEvidence(kind='asset_generation_provenance',
                       reference=f"generation:{record['generation_id']}:asset:{asset.asset_id}:sha256:{asset.file.sha256}",
                       summary='当前生成请求与实际接收字节的对应关系；不替代许可核验'),
    )
    return asset.model_copy(update={'rights': asset.rights.model_copy(update={
        'evidence': asset.rights.evidence + tuple(e for e in evidence if e not in asset.rights.evidence)})})


def create_material_generation_acquirer(store: AttemptMaterialStore) -> MaterialAcquirer:
    return MaterialAcquirer(store, url_policy=RemoteURLPolicy(resolver=_resolve_generation_host))


def _resolve_generation_host(host: str, port: int) -> tuple[str, ...]:
    """Use normal DNS first; if this host is sinkholed locally, resolve via HTTPS DNS.

    The resulting public IPs are still pinned by PinnedHttpsTransport and the
    HTTPS certificate is checked against the original provider hostname.
    """
    try:
        local = RemoteURLPolicy._resolve(host, port)
    except OSError:
        local = ()
    if local and all(ipaddress.ip_address(item).is_global for item in local):
        return local

    if not is_minimax_media_host(host):
        raise OSError("No public address for non-provider output host")

    query = urlencode({"name": host.lower().rstrip('.'), "type": "A"})
    try:
        with urlopen("https://dns.google/resolve?" + query, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise OSError("Public DNS-over-HTTPS lookup failed") from exc
    if not isinstance(payload, dict) or payload.get("Status") != 0:
        raise OSError("Public DNS-over-HTTPS returned an invalid response")
    answers = payload.get("Answer", [])
    addresses = tuple(dict.fromkeys(
        item["data"] for item in answers
        if isinstance(item, dict) and item.get("type") == 1 and isinstance(item.get("data"), str)
    )) if isinstance(answers, list) else ()
    if not addresses or any(not ipaddress.ip_address(item).is_global for item in addresses):
        raise OSError("Public DNS-over-HTTPS did not return only global addresses")
    return addresses


class GenerationApprovalRequired(ValueError):
    """The caller has not explicitly approved a potentially billable request."""


class GenerationRequestConflict(ValueError):
    """The request id already has persisted execution state."""


def visual_generation_prompt(need: MaterialNeed) -> str:
    """Use the same effective scene style as retrieval and matching.

    Planning resolves Mode defaults and scene overrides into preferred_style.
    Unbound standalone Image Needs retain their existing visual_style fallback.
    """
    if need.media_type not in {MediaType.IMAGE, MediaType.VIDEO}:
        raise ValueError('视觉生成只支持图片或视频 Need')
    style = need.constraints.get('preferred_style') or getattr(need.modality_spec, 'visual_style', None)
    if style is not None and not isinstance(style, str):
        raise ValueError('视觉风格须为已规划的文字要求，未提交生成')
    prompt = need.intent.description.strip()
    if not prompt:
        raise ValueError('视觉素材需要明确内容描述，未提交生成')
    if style and style.strip():
        prompt += '\nVisual style: ' + style.strip()
    limit = 1500 if need.media_type is MediaType.IMAGE else 7000
    if len(prompt) > limit:
        raise ValueError(f'视觉素材描述与风格合计超过 {limit} 字符，需先精简规划；未提交生成')
    return prompt


@dataclass(frozen=True)
class GeneratedMaterialResult:
    generation_id: str
    task_id: str
    asset: MaterialAsset
    record: dict[str, object]


class MiniMaxVideoMaterialGeneration:
    """Turn one video Need into an Attempt-local, inspected MaterialAsset."""

    def __init__(
        self,
        adapter: MiniMaxVideoAdapter,
        *,
        acquirer_factory: Callable[[AttemptMaterialStore], MaterialAcquirer] | None = None,
    ):
        self._adapter = adapter
        self._acquirer_factory = acquirer_factory or create_material_generation_acquirer

    def generate(
        self,
        plan: MaterialPlan,
        need: MaterialNeed,
        store: AttemptMaterialStore,
        *,
        request_id: str,
        confirmed_paid: bool,
        approval: dict | None = None,
    ) -> GeneratedMaterialResult:
        with store.generation_lock(f"gen-{request_id}"):
            return self._generate(plan, need, store, request_id=request_id,
                                  confirmed_paid=confirmed_paid, approval=approval)

    def _generate(
        self, plan: MaterialPlan, need: MaterialNeed, store: AttemptMaterialStore, *,
        request_id: str, confirmed_paid: bool, approval: dict | None,
    ) -> GeneratedMaterialResult:
        if not confirmed_paid:
            raise GenerationApprovalRequired("Explicit approval for possible MiniMax charges is required")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}", request_id):
            raise ValueError("Generation request id is invalid")
        if need not in plan.needs:
            raise ValueError("Generation Need must belong to the supplied MaterialPlan")
        if need.media_type is not MediaType.VIDEO:
            raise ValueError("MiniMax video generation requires a video Need")
        if need.modality_spec is not None and need.modality_spec.kind != "video":
            raise ValueError("MiniMax video generation cannot serve this Need modality")

        generation_id = f"gen-{request_id}"
        try:
            previous = store.read_generation_record(generation_id)
        except GenerationRecordNotFound:
            previous = None

        prompt = visual_generation_prompt(need)
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        duration = self._duration(need)
        ratio = self._ratio(need)
        model = self._adapter.model
        plan_revision = hashlib.sha256(plan.to_json().encode("utf-8")).hexdigest()
        resolution = "480P" if model == "MiniMax-H3-Max" else "768P"
        started = datetime.now(timezone.utc)
        record: dict[str, object] = {
            "schema": "easel-material-generation@1",
            "generation_id": generation_id,
            "attempt_id": plan.attempt_id,
            "plan_id": plan.plan_id,
            "plan_revision": plan_revision,
            "need_id": need.need_id,
            "need_sha256": hashlib.sha256(need.to_json().encode()).hexdigest(),
            "provider": "minimax",
            "model": model,
            "modality": "video",
            "prompt_sha256": prompt_hash,
            "duration_seconds_requested": duration,
            "resolution": resolution,
            "ratio": ratio,
            "status": "SUBMITTING",
            "started_at": started.isoformat(),
            "operator_confirmed_paid": approval is None,
            **({'commission_authorization': approval} if approval else {}),
            **({"operator_confirmed_at": started.isoformat()} if approval is None else {}),
            "billing": {
                "status": "UNKNOWN",
                "may_be_billable": True,
                "pricing_reference": "https://platform.minimaxi.com/docs/guides/pricing-paygo",
            },
        }
        resume_task_id: str | None = None
        if previous is not None:
            fingerprint_fields = (
                "attempt_id", "plan_id", "plan_revision", "need_id", "model",
                "prompt_sha256", "duration_seconds_requested", "resolution", "ratio",
            )
            if any(previous.get(field) != record.get(field) for field in fingerprint_fields):
                raise GenerationRequestConflict("Generation request id is already bound to different input")
            if previous.get('status') in {'RESULT_RECEIVED', 'RESULT_INTAKE_FAILED'}:
                from easel.materials.application.generation_modalities import MiniMaxImageSpeechGeneration
                # The generation lock is already held. Reuse the existing local
                # receipt verifier; no query, download or credentials required.
                return MiniMaxImageSpeechGeneration()._resume_received(store, previous)
            if previous.get("status") == "COMPLETE" and isinstance(previous.get("asset_id"), str):
                asset = store.read_asset(str(previous["asset_id"]))
                path = store.resolve_asset_locator(asset.file.path)
                if path.stat().st_size != asset.file.size or hashlib.sha256(path.read_bytes()).hexdigest() != asset.file.sha256:
                    raise GenerationRequestConflict("Persisted generated Asset bytes are stale")
                return GeneratedMaterialResult(
                    generation_id, str(previous.get("task_id", "")), asset, previous,
                )
            if (previous.get("status") in {"RUNNING", "RESULT_FAILED"}
                    and isinstance(previous.get("task_id"), str)):
                resume_task_id = str(previous["task_id"])
                record = dict(previous)
                record.update({"status": "RUNNING", "resumed_at": started.isoformat()})
                store.write_generation_record(generation_id, record)
            else:
                raise GenerationRequestConflict(
                    f"Generation request already has state ({previous.get('status', 'unknown')}); inspect it before starting another request"
                )
        else:
            store.write_generation_record(generation_id, record)

        if resume_task_id is None:
            try:
                submitted = self._adapter.submit(
                    prompt,
                    duration_seconds=duration,
                    resolution=resolution,
                    ratio=ratio,
                )
            except MiniMaxVideoError as exc:
                record.update({
                    "status": "SUBMISSION_UNCERTAIN" if exc.submission_uncertain else "SUBMIT_FAILED",
                    "error_code": "provider_submit_uncertain" if exc.submission_uncertain else "provider_submit_rejected",
                })
                store.write_generation_record(generation_id, record)
                raise exc
            task_id = submitted.task_id
            record.update({"status": "RUNNING", "task_id": task_id})
            store.write_generation_record(generation_id, record)
        else:
            task_id = resume_task_id

        try:
            completed = self._adapter.wait(task_id)
            if not completed.video_url:
                raise MiniMaxVideoError("MiniMax task completed without a result URL")
            candidate = SupplyCandidate(
                candidate_id=generation_id,
                need_id=need.need_id,
                media_type=MediaType.VIDEO,
                source={
                    "kind": "generative",
                    "provider": "minimax",
                    "provider_asset_id": completed.task_id,
                    "source_page": "https://platform.minimaxi.com/docs/api-reference/video-generation-v2-create",
                },
                preview=PreviewInfo(url=completed.video_url),
                availability=Availability.DIRECT_DOWNLOADABLE,
                acquisition=AcquisitionInfo(
                    mode="provider_direct_url",
                    locator=completed.video_url,
                    media_format="video/mp4",
                ),
            )
            acquired = self._acquirer_factory(store).acquire(candidate)
            record.update(status='RESULT_RECEIVED', received_asset=acquired.model_dump(mode='json'),
                          received_at=datetime.now(timezone.utc).isoformat(),
                          provider_usage=dict(getattr(completed, 'usage', {}) or {}))
            store.write_generation_record(generation_id, record)
            acquired = retain_generation_rights_evidence(acquired, record)
            asset = TechnicalInspector(store).inspect_and_persist(acquired)
            if asset.technical.status.value != 'PASSED':
                raise ValueError('已保存视频素材，本地技术检查尚未通过；只重试检查，不重新生成')
            record.update({
                "status": "COMPLETE",
                "task_id": completed.task_id,
                "asset_id": asset.asset_id,
                "asset_path": asset.file.path,
                "asset_sha256": asset.file.sha256,
                "asset_bytes": asset.file.size,
                "asset_mime": asset.file.mime,
                "technical_status": asset.technical.status.value,
                "rights_status": asset.rights.status.value,
                "duration_seconds_observed": asset.technical.duration_seconds,
                "provider_usage": dict(getattr(completed, "usage", {}) or {}),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            })
            store.write_generation_record(generation_id, record)
            return GeneratedMaterialResult(generation_id, completed.task_id, asset, record)
        except MiniMaxVideoObservationPending as exc:
            record.update(status="RUNNING", task_id=task_id,
                          error_code="provider_task_pending" if exc.task_status else "provider_observation_unavailable",
                          updated_at=datetime.now(timezone.utc).isoformat())
            if exc.task_status:
                record['last_provider_status'] = exc.task_status
            store.write_generation_record(generation_id, record)
            raise
        except Exception as exc:
            record.update({
                "status": "RESULT_INTAKE_FAILED" if record.get('received_asset') else "RESULT_FAILED",
                "error_code": type(exc).__name__ if isinstance(exc, (MiniMaxVideoError, ValueError)) else "material_intake_failed",
                "task_id": task_id,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            store.write_generation_record(generation_id, record)
            raise

    @staticmethod
    def _duration(need: MaterialNeed) -> int:
        requested = need.duration_hint.target_seconds if need.duration_hint else 5
        for key in ("target_duration_seconds", "duration_seconds"):
            value = need.constraints.get(key)
            if isinstance(value, (float, int)) and not isinstance(value, bool) and value > 0:
                requested = float(value)
                break
        return min(15, max(5, math.ceil(requested)))

    @staticmethod
    def _ratio(need: MaterialNeed) -> str:
        if need.modality_spec is not None and need.modality_spec.kind == "video":
            aspect = need.modality_spec.aspect_ratio
            if aspect in {"9:16", "16:9", "1:1", "4:3", "3:4", "21:9"}:
                return aspect
        orientation = need.constraints.get("orientation")
        return {"portrait": "9:16", "square": "1:1"}.get(orientation, "16:9")


__all__ = [
    "GeneratedMaterialResult",
    "GenerationApprovalRequired",
    "GenerationRequestConflict",
    "MiniMaxVideoMaterialGeneration",
]
