"""Small, explicit domain contracts shared by API, model and execution adapters.

Model-authored plan content is separate from program-owned identity, grants and
execution records. Unknown fields are errors, not silently accepted authority.
"""
from __future__ import annotations

from enum import Enum
import hashlib
import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

SCHEMA_VERSION = 1
Identifier = Annotated[str, StringConstraints(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")]
Digest = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]


def canonical_json(value) -> str:
    """Stable JSON for command/plan fingerprints; rejects non-JSON floats."""
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def fingerprint(value) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class WorkState(str, Enum):
    DISCUSSING = "discussing"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    PRODUCING = "producing"
    NEEDS_DECISION = "needs_decision"
    PREVIEW_NEEDS_FIX = "preview_needs_fix"
    REVIEWABLE = "reviewable"
    CANCELLED = "cancelled"


class RunKind(str, Enum):
    PLANNING = "planning"
    PRODUCTION = "production"
    REVISION = "revision"


class RunState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_EXTERNAL = "waiting_external"
    NEEDS_DECISION = "needs_decision"
    PAUSED = "paused"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SUPERSEDED = "superseded"


class TaskState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_EXTERNAL = "waiting_external"
    RETRYABLE_FAILED = "retryable_failed"
    NEEDS_DECISION = "needs_decision"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OperationKind(str, Enum):
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    VOICE = "VOICE"
    MODEL = "MODEL"


class OperationState(str, Enum):
    RESERVED = "reserved"
    SENDING = "sending"
    SUBMITTED = "submitted"
    UNKNOWN = "unknown"
    SUCCEEDED = "succeeded"
    FAILED_AFTER_SUBMIT = "failed_after_submit"
    FAILED_BEFORE_SUBMIT = "failed_before_submit"
    CANCELLED = "cancelled"


class WorkCreate(Contract):
    title: str = Field(min_length=1, max_length=300)
    input_text: str = ""
    profile_ref: Identifier | None = None
    channel_id: Identifier | None = None


class ServicePermission(Contract):
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    mode: str = Field(min_length=1)


class GrantSpec(Contract):
    schema_version: Literal[1] = 1
    purpose: Literal["planning", "preview", "production"]
    plan_revision: int | None = Field(default=None, gt=0, strict=True)
    target_ref: str | None = None
    services: list[ServicePermission] = Field(min_length=1)
    allow_ai: bool = False
    image_limit: int = Field(default=0, ge=0, strict=True)
    video_limit: int = Field(default=0, ge=0, strict=True)

    @model_validator(mode="after")
    def purpose_limits(self):
        if self.purpose == "production" and self.plan_revision is None:
            raise ValueError("production authorization requires a plan revision")
        if self.purpose != "production" and (self.allow_ai or self.image_limit or self.video_limit):
            raise ValueError("planning/preview authorization cannot grant image/video generation")
        return self


class VoiceIdentity(Contract):
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    voice_id: str = Field(min_length=1)
    engine: str = ""
    parameters: dict[str, str | int | float | bool] = Field(default_factory=dict)


class SubtitleSettings(Contract):
    enabled: bool = True
    font: str = "sans-serif"
    size: int = Field(default=48, gt=0, le=1080, strict=True)
    color: str = "#FFFFFF"
    outline: str = "#000000"
    background: str = "transparent"
    position: Literal["top", "middle", "bottom"] = "bottom"


class VideoSettings(Contract):
    duration_seconds: float = Field(ge=1, le=900, allow_inf_nan=False)
    aspect_ratio: Literal["9:16", "16:9"] = "9:16"
    audio_mode: Literal["silent", "music", "voice", "mixed"]
    voice: VoiceIdentity | None = None
    subtitles: SubtitleSettings = Field(default_factory=SubtitleSettings)


class Scene(Contract):
    id: Identifier
    purpose: str = Field(min_length=1)
    visual: str = Field(min_length=1)
    narration: str = ""
    duration_seconds: float | None = Field(default=None, gt=0, le=900, allow_inf_nan=False)
    required_input_ids: list[Identifier] = Field(default_factory=list)


class ProfileSnapshot(Contract):
    profile_ref: Identifier
    content: str
    content_hash: Digest


class PlanDocument(Contract):
    schema_version: Literal[1] = 1
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    script: str = Field(min_length=1)
    scenes: list[Scene] = Field(min_length=1)
    settings: VideoSettings
    facts: list[str] = Field(default_factory=list)
    core_views: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    adaptation_permissions: list[str] = Field(default_factory=list)
    profile_snapshot: ProfileSnapshot | None = None
    director_revision_id: Identifier | None = None

    @model_validator(mode="after")
    def distinct_scenes(self):
        ids = [scene.id for scene in self.scenes]
        if len(ids) != len(set(ids)):
            raise ValueError("scene identifiers must be unique")
        return self


class InputSpec(Contract):
    kind: Literal["text", "image", "video", "audio", "document"]
    usage: Literal["must_use", "reference"]
    source_ref: str = Field(min_length=1)
    digest: Digest
    original_name: str = ""
    text_content: str = ""


class ArtifactSpec(Contract):
    kind: str = Field(min_length=1)
    storage_ref: str = Field(min_length=1)
    digest: Digest
    size_bytes: int = Field(ge=0, strict=True)
    media_type: str = "application/octet-stream"
    displayable: bool = False
    output_revision: int | None = Field(default=None, gt=0, strict=True)


class CommandEnvelope(Contract):
    command_id: Identifier
    expected_revision: int | None = Field(default=None, gt=0, strict=True)


class ErrorEnvelope(Contract):
    code: str
    user_message: str
    retryable: bool = False
    affected_ids: list[str] = Field(default_factory=list)
    operation_id: str | None = None
    requires_decision: bool = False
