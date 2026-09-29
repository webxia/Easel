"""Validated, provider-neutral Material Layer contracts.

These models describe supply intent, assets, matches, and audit evidence. They
intentionally contain no Hypit types, provider response models, or production
placement decisions.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from enum import Enum
from typing import Any, Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ContractModel(BaseModel):
    """Base contract with strict validation and deterministic JSON helpers."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    @classmethod
    def from_json(cls, value: str) -> Any:
        return cls.model_validate_json(value)

    def to_json(self) -> str:
        return json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )


class MediaType(str, Enum):
    VIDEO = "video"
    IMAGE = "image"
    AUDIO = "audio"


class NeedImportance(str, Enum):
    REQUIRED = "required"
    OPTIONAL = "optional"


class NeedScopeType(str, Enum):
    GLOBAL = "global"
    SCENE = "scene"
    SEGMENT = "segment"
    EVENT = "event"


class Availability(str, Enum):
    DISCOVERED = "DISCOVERED"
    PREVIEWABLE = "PREVIEWABLE"
    RESOLVABLE = "RESOLVABLE"
    DIRECT_DOWNLOADABLE = "DIRECT_DOWNLOADABLE"
    GENERATABLE = "GENERATABLE"
    UNAVAILABLE = "UNAVAILABLE"


class RightsStatus(str, Enum):
    KNOWN = "KNOWN"
    ATTRIBUTION_REQUIRED = "ATTRIBUTION_REQUIRED"
    PUBLIC_DOMAIN = "PUBLIC_DOMAIN"
    UNKNOWN = "UNKNOWN"
    RESTRICTED = "RESTRICTED"


class TechnicalStatus(str, Enum):
    PENDING = "PENDING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class IntelligenceStatus(str, Enum):
    NOT_RUN = "NOT_RUN"
    DISABLED = "DISABLED"
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class SemanticField(str, Enum):
    CAPTION = "caption"
    TAGS = "tags"
    OBJECTS = "objects"
    PEOPLE_COUNT = "people_count"
    ENVIRONMENT = "environment"
    ACTION = "action"
    SHOT_TYPE = "shot_type"
    CAMERA_MOTION = "camera_motion"
    VISIBLE_TEXT = "visible_text"
    LOGO = "logo"
    STYLE = "style"
    COLOR = "color"
    LIGHTING = "lighting"


class CoverageStatus(str, Enum):
    COVERED = "covered"
    PARTIAL = "partial"
    UNCOVERED = "uncovered"


class ReadinessStatus(str, Enum):
    READY = "READY"
    NOT_READY = "NOT_READY"


class NeedScope(ContractModel):
    type: NeedScopeType
    ref: str = Field(min_length=1)


class NeedIntent(ContractModel):
    description: str = Field(min_length=1)
    function: str | None = None


class DurationHint(ContractModel):
    target_seconds: float = Field(gt=0)


class ImageNeedSpec(ContractModel):
    kind: Literal["image"] = "image"
    aspect_ratio: str | None = None
    visual_style: str | None = None
    reference_asset_ids: tuple[str, ...] = ()


class VideoNeedSpec(ContractModel):
    kind: Literal["video"] = "video"
    aspect_ratio: str | None = None
    resolution: str | None = None
    generate_audio: bool = False
    reference_asset_ids: tuple[str, ...] = ()


class VoiceIdentitySource(str, Enum):
    CREATOR_CONTEXT = "creator_context"
    DIRECTOR_INTENT = "director_intent"
    EXPLICIT_USER = "explicit_user"


class VoiceIdentityRef(ContractModel):
    source: VoiceIdentitySource
    reference: str = Field(min_length=1)
    reference_asset_ids: tuple[str, ...] = ()
    consent_ref: str | None = None


class VoiceNeedSpec(ContractModel):
    kind: Literal["voice"] = "voice"
    identity: VoiceIdentityRef | None = None
    delivery_description: str | None = None
    text_ref: str | None = None
    text_sha256: str | None = None

    @field_validator("text_sha256")
    @classmethod
    def normalize_text_digest(cls, value: str | None) -> str | None:
        if value is not None and not re.fullmatch(r"[a-fA-F0-9]{64}", value):
            raise ValueError("text_sha256 must be a SHA-256 hex digest")
        return value.lower() if value is not None else None

    @model_validator(mode="after")
    def text_reference_pair(self) -> VoiceNeedSpec:
        if (self.text_ref is None) != (self.text_sha256 is None):
            raise ValueError("voice text_ref and text_sha256 must be provided together")
        return self


class BgmNeedSpec(ContractModel):
    kind: Literal["bgm"] = "bgm"
    mood: str | None = None
    genre: str | None = None
    instruments: tuple[str, ...] = ()
    vocals_allowed: bool = False
    energy: str | None = None
    tempo_bpm: tuple[int, int] | None = None

    @model_validator(mode="after")
    def valid_tempo(self) -> BgmNeedSpec:
        if self.tempo_bpm is not None and (self.tempo_bpm[0] <= 0 or self.tempo_bpm[0] > self.tempo_bpm[1]):
            raise ValueError("tempo_bpm must be a positive ascending range")
        return self


class SfxNeedSpec(ContractModel):
    kind: Literal["sfx"] = "sfx"
    event_description: str = Field(min_length=1)
    sound_character: str | None = None
    intensity: str | None = None
    environment: str | None = None


MultimodalNeedSpec = Annotated[
    ImageNeedSpec | VideoNeedSpec | VoiceNeedSpec | BgmNeedSpec | SfxNeedSpec,
    Field(discriminator="kind"),
]


class ContinuityRef(ContractModel):
    """A stable upstream identity consumed by matching, not created here."""

    kind: str = Field(min_length=1)
    ref: str = Field(min_length=1)


class MaterialNeed(ContractModel):
    need_id: str = Field(min_length=1)
    scope: NeedScope
    media_type: MediaType
    role: str = Field(min_length=1)
    intent: NeedIntent
    duration_hint: DurationHint | None = None
    constraints: dict[str, Any] = Field(default_factory=dict)
    continuity_refs: tuple[ContinuityRef, ...] = ()
    importance: NeedImportance
    desired_options: int = Field(default=1, ge=1)
    contract_version: Literal["material_need@1"] = "material_need@1"
    modality_spec: MultimodalNeedSpec | None = None

    @field_validator("continuity_refs")
    @classmethod
    def unique_continuity_refs(cls, refs: tuple[ContinuityRef, ...]) -> tuple[ContinuityRef, ...]:
        keys = [(ref.kind, ref.ref) for ref in refs]
        if len(keys) != len(set(keys)):
            raise ValueError("continuity_refs must not contain duplicate references")
        return refs

    @model_validator(mode="after")
    def modality_matches_media_type(self) -> MaterialNeed:
        if self.modality_spec is None:
            return self
        kind_to_media = {"image": MediaType.IMAGE, "video": MediaType.VIDEO,
                         "voice": MediaType.AUDIO, "bgm": MediaType.AUDIO, "sfx": MediaType.AUDIO}
        if kind_to_media[self.modality_spec.kind] is not self.media_type:
            raise ValueError("modality_spec kind does not match media_type")
        if self.modality_spec.kind == "sfx" and self.scope.type is not NeedScopeType.EVENT:
            raise ValueError("SFX Need must use event scope")
        return self


class MaterialPlan(ContractModel):
    plan_id: str = Field(min_length=1)
    creation_id: str = Field(min_length=1)
    attempt_id: str = Field(min_length=1)
    context_refs: dict[str, str] = Field(default_factory=dict)
    policy: dict[str, str] = Field(default_factory=lambda: {"strategy": "bulk_first"})
    needs: tuple[MaterialNeed, ...] = ()

    @field_validator("context_refs")
    @classmethod
    def valid_context_refs(cls, refs: dict[str, str]) -> dict[str, str]:
        if any(not key or not value for key, value in refs.items()):
            raise ValueError("context_refs keys and values must be non-empty")
        return refs

    @model_validator(mode="after")
    def unique_need_ids(self) -> MaterialPlan:
        ids = [need.need_id for need in self.needs]
        if len(ids) != len(set(ids)):
            raise ValueError("MaterialPlan need_id values must be unique")
        return self


class RetrievalIntent(ContractModel):
    """Internal search intent compiled from a Need; never a provider query schema."""

    need_id: str = Field(min_length=1)
    semantic_queries: tuple[str, ...] = Field(min_length=1)
    filters: dict[str, str | int | float | bool] = Field(default_factory=dict)
    negative_terms: tuple[str, ...] = ()
    ranking_hints: dict[str, str | int | float | bool] = Field(default_factory=dict)
    query_context: dict[str, str] = Field(default_factory=dict)

    @field_validator("semantic_queries")
    @classmethod
    def nonempty_queries(cls, queries: tuple[str, ...]) -> tuple[str, ...]:
        if any(not query.strip() for query in queries):
            raise ValueError("semantic_queries must not contain blank queries")
        return queries


class CandidateSource(ContractModel):
    kind: str = Field(min_length=1)
    provider: str | None = None
    provider_asset_id: str | None = None
    source_page: str | None = None
    creator: str | None = None


class PreviewInfo(ContractModel):
    url: str | None = None
    locator: str | None = None

    @model_validator(mode="after")
    def has_preview_reference(self) -> PreviewInfo:
        if not self.url and not self.locator:
            raise ValueError("preview requires url or locator")
        return self


class RightsHint(ContractModel):
    status: RightsStatus = RightsStatus.UNKNOWN
    license_name: str | None = None
    license_url: str | None = None
    attribution_required: bool | None = None
    usage_constraints: tuple[str, ...] = ()


class AcquisitionInfo(ContractModel):
    """Provider-neutral acquisition descriptor; execution belongs elsewhere."""

    mode: str = Field(min_length=1)
    locator: str | None = None
    media_format: str | None = None


class SupplyCandidate(ContractModel):
    candidate_id: str = Field(min_length=1)
    need_id: str | None = None
    media_type: MediaType
    source: CandidateSource
    preview: PreviewInfo | None = None
    availability: Availability
    rights_hint: RightsHint = Field(default_factory=RightsHint)
    metadata: dict[str, Any] = Field(default_factory=dict)
    acquisition: AcquisitionInfo | None = None
    provider_payload_ref: str | None = None


class FileInfo(ContractModel):
    path: str = Field(min_length=1)
    sha256: str
    size: int = Field(ge=0)
    mime: str = Field(min_length=1)

    @field_validator("path")
    @classmethod
    def workspace_relative_path(cls, value: str) -> str:
        # P0 MaterialAsset files are workspace-relative, never arbitrary paths.
        if value.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", value):
            raise ValueError("file.path must be workspace-relative")
        parts = value.replace("\\", "/").split("/")
        if ".." in parts or any(part in ("", ".") for part in parts):
            raise ValueError("file.path must be a normalized relative path")
        return value

    @field_validator("sha256")
    @classmethod
    def valid_sha256(cls, value: str) -> str:
        if not re.fullmatch(r"[0-9a-f]{64}", value):
            raise ValueError("sha256 must be 64 lowercase hexadecimal characters")
        return value


class RightsEvidence(ContractModel):
    kind: str = Field(min_length=1)
    reference: str = Field(min_length=1)
    observed_at: datetime | None = None
    summary: str | None = None

    @field_validator("observed_at")
    @classmethod
    def timezone_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("observed_at must include a timezone")
        return value


class RightsInfo(ContractModel):
    status: RightsStatus
    license_name: str | None = None
    license_url: str | None = None
    attribution_required: bool = False
    attribution_text: str | None = None
    usage_constraints: tuple[str, ...] = ()
    evidence: tuple[RightsEvidence, ...] = ()
    reviewed_at: datetime | None = None

    @field_validator("reviewed_at")
    @classmethod
    def reviewed_timezone_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("reviewed_at must include a timezone")
        return value


class TechnicalInfo(ContractModel):
    status: TechnicalStatus = TechnicalStatus.PENDING
    duration_seconds: float | None = Field(default=None, gt=0)
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    mime: str | None = None
    has_audio: bool | None = None
    facts: dict[str, Any] = Field(default_factory=dict)


class SemanticInfo(ContractModel):
    """Preserve existing/source semantic fields separately from analyzer inferences.

    `caption`, `tags`, and `attributes` may contain normalized source facts.
    Analyzer output belongs only in `inferences` and must not overwrite them.
    """

    caption: str | None = None
    tags: tuple[str, ...] = ()
    attributes: dict[str, Any] = Field(default_factory=dict)
    intelligence_status: IntelligenceStatus = IntelligenceStatus.NOT_RUN
    intelligence_error: str | None = None
    inferences: tuple["SemanticInference", ...] = ()

    @model_validator(mode="after")
    def unique_analyzers(self) -> SemanticInfo:
        analyzer_ids = [item.analyzer_id for item in self.inferences]
        if len(analyzer_ids) != len(set(analyzer_ids)):
            raise ValueError("SemanticInfo inferences must have unique analyzer_id values")
        return self


class SemanticAnnotation(ContractModel):
    field: SemanticField
    value: str | tuple[str, ...] | int | float | bool
    confidence: float | None = Field(default=None, ge=0, le=1)
    evidence: str | None = None

    @model_validator(mode="after")
    def validate_value_for_field(self) -> SemanticAnnotation:
        if self.field is SemanticField.PEOPLE_COUNT:
            if isinstance(self.value, bool) or not isinstance(self.value, int) or self.value < 0:
                raise ValueError("people_count annotation must be a non-negative integer")
        elif self.field is SemanticField.LOGO:
            if not isinstance(self.value, (bool, str, tuple)):
                raise ValueError("logo annotation must be a boolean or label")
        elif self.field in {SemanticField.TAGS, SemanticField.OBJECTS, SemanticField.VISIBLE_TEXT}:
            if not isinstance(self.value, (str, tuple)):
                raise ValueError(f"{self.field.value} annotation must be text or a tuple of text")
            if isinstance(self.value, tuple) and any(not isinstance(item, str) or not item.strip() for item in self.value):
                raise ValueError(f"{self.field.value} annotation contains an invalid item")
        elif not isinstance(self.value, str):
            raise ValueError(f"{self.field.value} annotation must be text")
        return self


class SemanticInference(ContractModel):
    analyzer_id: str = Field(min_length=1)
    model_version: str | None = None
    status: IntelligenceStatus
    annotations: tuple[SemanticAnnotation, ...] = ()
    error_code: str | None = None
    observed_at: datetime | None = None

    @model_validator(mode="after")
    def validate_result_state(self) -> SemanticInference:
        if self.status not in {IntelligenceStatus.COMPLETE, IntelligenceStatus.PARTIAL, IntelligenceStatus.FAILED}:
            raise ValueError("inference status must describe an analyzer result")
        if self.status is IntelligenceStatus.FAILED and not self.error_code:
            raise ValueError("failed inference requires error_code")
        if self.status is not IntelligenceStatus.FAILED and self.error_code:
            raise ValueError("successful inference must not carry error_code")
        fields = [item.field for item in self.annotations]
        if len(fields) != len(set(fields)):
            raise ValueError("inference fields must be unique")
        if self.model_version is not None and not self.model_version.strip():
            raise ValueError("model_version must not be blank")
        if self.observed_at is not None and self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must include a timezone")
        return self


class LineageInfo(ContractModel):
    parent_asset_ids: tuple[str, ...] = ()
    references: tuple[str, ...] = ()

    @field_validator("parent_asset_ids")
    @classmethod
    def unique_parents(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not value for value in values) or len(values) != len(set(values)):
            raise ValueError("parent_asset_ids must be non-empty and unique")
        return values


class MaterialAsset(ContractModel):
    asset_id: str = Field(min_length=1)
    media_type: MediaType
    file: FileInfo
    source: CandidateSource
    rights: RightsInfo
    technical: TechnicalInfo = Field(default_factory=TechnicalInfo)
    semantic: SemanticInfo = Field(default_factory=SemanticInfo)
    lineage: LineageInfo = Field(default_factory=LineageInfo)


class MatchScores(ContractModel):
    semantic: float | None = Field(default=None, ge=0, le=1)
    director: float | None = Field(default=None, ge=0, le=1)
    continuity: float | None = Field(default=None, ge=0, le=1)
    quality: float | None = Field(default=None, ge=0, le=1)


class MaterialMatch(ContractModel):
    need_id: str = Field(min_length=1)
    asset_id: str = Field(min_length=1)
    rank: int = Field(ge=1)
    score: float | None = Field(default=None, ge=0, le=1)
    scores: MatchScores = Field(default_factory=MatchScores)
    reasons: tuple[str, ...] = ()
    qualified: bool = False


class Coverage(ContractModel):
    need_id: str = Field(min_length=1)
    status: CoverageStatus
    qualified_assets: int = Field(ge=0)

    @model_validator(mode="after")
    def count_matches_status(self) -> Coverage:
        if self.status == CoverageStatus.UNCOVERED and self.qualified_assets != 0:
            raise ValueError("uncovered coverage cannot have qualified assets")
        if self.status == CoverageStatus.COVERED and self.qualified_assets < 1:
            raise ValueError("covered coverage requires at least one qualified asset")
        if self.status == CoverageStatus.PARTIAL and self.qualified_assets < 1:
            raise ValueError("partial coverage requires at least one qualified asset")
        return self


class MaterialBundle(ContractModel):
    bundle_id: str = Field(min_length=1)
    plan_id: str = Field(min_length=1)
    supply_run_id: str = Field(min_length=1)
    revision: str | None = None
    assets: tuple[MaterialAsset, ...] = ()
    matches: tuple[MaterialMatch, ...] = ()
    coverage: tuple[Coverage, ...] = ()

    @model_validator(mode="after")
    def validate_references_and_ids(self) -> MaterialBundle:
        asset_ids = [asset.asset_id for asset in self.assets]
        if len(asset_ids) != len(set(asset_ids)):
            raise ValueError("MaterialBundle asset_id values must be unique")
        coverage_ids = [item.need_id for item in self.coverage]
        if len(coverage_ids) != len(set(coverage_ids)):
            raise ValueError("MaterialBundle coverage need_id values must be unique")
        assets = set(asset_ids)
        coverage_by_need = {item.need_id: item for item in self.coverage}
        match_pairs: set[tuple[str, str]] = set()
        for match in self.matches:
            if match.asset_id not in assets:
                raise ValueError(f"MaterialMatch references unknown asset_id: {match.asset_id}")
            if match.need_id not in coverage_by_need:
                raise ValueError(f"MaterialMatch references unknown need_id: {match.need_id}")
            pair = (match.need_id, match.asset_id)
            if pair in match_pairs:
                raise ValueError("MaterialBundle must not contain duplicate Need/Asset matches")
            match_pairs.add(pair)
        qualified_counts: dict[str, int] = {}
        for match in self.matches:
            if match.qualified:
                qualified_counts[match.need_id] = qualified_counts.get(match.need_id, 0) + 1
        for item in self.coverage:
            if item.qualified_assets != qualified_counts.get(item.need_id, 0):
                raise ValueError("Coverage.qualified_assets must match qualified MaterialMatch records")
        return self


class MaterialGap(ContractModel):
    need_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    request: str | None = None
    blocking: bool = True


class MaterialReadiness(ContractModel):
    plan_id: str = Field(min_length=1)
    bundle_id: str = Field(min_length=1)
    status: ReadinessStatus
    required_needs: tuple[str, ...] = ()
    covered_required_needs: tuple[str, ...] = ()
    blocking_needs: tuple[str, ...] = ()
    blocking_reasons: tuple[str, ...] = ()
    plan_revision: str | None = None
    bundle_revision: str | None = None

    @model_validator(mode="after")
    def validate_gate_evidence(self) -> MaterialReadiness:
        for name, values in (
            ("required_needs", self.required_needs),
            ("covered_required_needs", self.covered_required_needs),
            ("blocking_needs", self.blocking_needs),
        ):
            if any(not value for value in values) or len(values) != len(set(values)):
                raise ValueError(f"{name} must contain unique non-empty IDs")
        required = set(self.required_needs)
        covered = set(self.covered_required_needs)
        blocking = set(self.blocking_needs)
        if not covered <= required or not blocking <= required:
            raise ValueError("readiness Need references must be in required_needs")
        if covered & blocking:
            raise ValueError("a required Need cannot be both covered and blocking")
        if self.status == ReadinessStatus.READY and (covered != required or blocking or self.blocking_reasons):
            raise ValueError("READY requires all required Needs covered and no blockers")
        if self.status == ReadinessStatus.NOT_READY and not blocking:
            raise ValueError("NOT_READY requires at least one blocking Need")
        return self


class SupplySourceResult(ContractModel):
    """Normalized source-level outcome; no Provider-specific response schema."""

    source_id: str = Field(min_length=1)
    status: str = Field(min_length=1)
    candidates_found: int = Field(default=0, ge=0)
    acquired_assets: int = Field(default=0, ge=0)
    failure_summary: str | None = None


class SupplyRun(ContractModel):
    supply_run_id: str = Field(min_length=1)
    plan_id: str = Field(min_length=1)
    parent_run_id: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
    provider_results: tuple[SupplySourceResult, ...] = ()
    failures: tuple[str, ...] = ()
    result_bundle_id: str | None = None

    @model_validator(mode="after")
    def valid_interval_and_sources(self) -> SupplyRun:
        if self.started_at.utcoffset() is None:
            raise ValueError("started_at must include a timezone")
        if self.finished_at is not None:
            if self.finished_at.utcoffset() is None:
                raise ValueError("finished_at must include a timezone")
            if self.finished_at < self.started_at:
                raise ValueError("finished_at cannot be earlier than started_at")
        source_ids = [item.source_id for item in self.provider_results]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("SupplyRun source_ids must be unique")
        return self
