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


class NarrationPolicy(Contract):
    """New-draft opt-in; historical plans retain fixed sentence playback."""
    continuous: bool = True
    duration_mode: Literal['fixed', 'voice_driven'] = 'fixed'


class BoardCard(Contract):
    id: Identifier
    text: str = Field(min_length=1,max_length=16)


class BoardColumn(Contract):
    id: Identifier
    title: str = Field(min_length=1,max_length=10)


class BoardState(Contract):
    title: str = Field(min_length=1,max_length=40)
    groups: dict[Identifier,Annotated[list[Identifier],Field(max_length=5)]] = Field(min_length=1,max_length=4,
        description='键必须是本图解columns中每一个id，不能用列title；即使该列暂时为空也填id:[]。值为cards的id列表，不是卡片text；每列最多5张卡。')
    highlight_ids: list[Identifier] = Field(default_factory=list,max_length=12,
        description='只能引用本状态groups实际可见的卡片id，不能用卡片文字')
    column_titles: dict[Identifier,Annotated[str,Field(min_length=1,max_length=10)]] = Field(default_factory=dict,max_length=4,
        description='可选：仅为本状态改列名称；键仍为已定义columns.id，值为新的显示名称，不增删列。')


class ExplainerBoard(Contract):
    """Model-authored, explicitly schematic cards; no arbitrary executable markup."""
    scene_id: Identifier
    title: str = Field(min_length=1,max_length=24)
    kind: Literal['conceptual','hypothetical']
    cards: list[BoardCard] = Field(min_length=1,max_length=12)
    columns: list[BoardColumn] = Field(min_length=1,max_length=4)
    states: list[BoardState] = Field(min_length=1,max_length=4)

    @model_validator(mode='after')
    def references(self):
        labels=[self.title,*[c.text for c in self.cards],*[c.title for c in self.columns],*[s.title for s in self.states]]
        if any(not value.strip() or '\n' in value or '\r' in value for value in labels):
            raise ValueError('图解文字须为非空单行短语，不嵌入排版指令')
        cards={c.id for c in self.cards};columns={c.id for c in self.columns};seen=set()
        if len(cards)!=len(self.cards) or len(columns)!=len(self.columns):
            raise ValueError('图解卡片与类别ID不得重复')
        for state in self.states:
            if (not set(state.column_titles)<=columns or any(not t.strip() or len(t)>10 or '\n' in t or '\r' in t for t in state.column_titles.values())):
                raise ValueError('状态只能重命名已有类别，类别名须为不超过10字的单行短语')
            if set(state.groups)!=columns or any(len(v)>5 for v in state.groups.values()):
                raise ValueError('groups键必须逐一使用columns.id（不是title）：'+','.join(sorted(columns))+'；空类别也保留id:[]，每列最多5张卡')
            visible=[c for values in state.groups.values() for c in values]
            if not visible or len(visible)!=len(set(visible)) or not set(visible)<=cards:
                raise ValueError('状态须使用真实卡片ID，不重复、不虚构')
            if not set(state.highlight_ids)<=set(visible):
                raise ValueError('只能强调实际可见卡片')
            seen.update(visible)
        if seen!=cards:raise ValueError('所有定义的卡片须至少在一个状态中展示')
        return self


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
    conversation_basis: dict | None = None
    profile_snapshot: ProfileSnapshot | None = None
    director_revision_id: Identifier | None = None
    narration_policy: NarrationPolicy | None = None
    explainer_boards: list[ExplainerBoard] = Field(default_factory=list,max_length=8)

    @model_validator(mode="after")
    def distinct_scenes(self):
        ids = [scene.id for scene in self.scenes]
        if len(ids) != len(set(ids)):
            raise ValueError("scene identifiers must be unique")
        board_ids=[b.scene_id for b in self.explainer_boards]
        if len(board_ids)!=len(set(board_ids)) or not set(board_ids)<=set(ids):
            raise ValueError('图解须绑定真实场景，每场景最多一组')
        if self.explainer_boards and self.settings.subtitles.enabled and self.settings.subtitles.position!='bottom':
            raise ValueError('本地图解当前只为底部字幕预留安全区，不得覆盖已有顶部/居中字幕')
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
