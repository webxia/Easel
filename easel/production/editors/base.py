"""Public editing contracts; asset paths are supplied by the application, not a model."""
from __future__ import annotations

from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator


def check_audio_delivery(audio_mode, scenes, audio):
    """One delivery contract, shared by proposal repair and final compilation."""
    voice = any(a.role == "voice" for a in audio) or any(s.source_audio for s in scenes)
    music = any(a.role == "music" for a in audio)
    if audio_mode == "silent" and (audio or voice):
        raise ValueError("silent delivery cannot contain audio")
    if audio_mode == "voice" and (not voice or music):
        raise ValueError("voice delivery needs voice/source sound and no music")
    if audio_mode == "music" and (not music or voice):
        raise ValueError("music delivery needs music and no voice/source sound")
    if audio_mode == "mixed" and not (voice and music):
        raise ValueError('声音模式mixed要求同时有旁白/原声与音乐；环境音或音效不等于音乐。当前剪辑缺少相应音轨；若已确认要求不允许音乐，须先局部修订方案为voice，不能擅自添加BGM。')


class EditError(ValueError):
    def __init__(self, message: str, code: str = "invalid_edit_project"):
        super().__init__(message)
        self.code = code


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class MediaAsset(Contract):
    locator: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    kind: Literal["video", "image", "audio", "font"]


class AssetManifest(Contract):
    # Application-owned root. Never expose this field as a model tool argument.
    root: Path
    assets: dict[str, MediaAsset]


class Crop(Contract):
    x: float = Field(default=0, ge=0, lt=1)
    y: float = Field(default=0, ge=0, lt=1)
    width: float = Field(default=1, gt=0, le=1)
    height: float = Field(default=1, gt=0, le=1)

    @model_validator(mode="after")
    def inside(self):
        if self.x + self.width > 1.000001 or self.y + self.height > 1.000001:
            raise ValueError("crop must stay within the source frame")
        return self


class Frame(Contract):
    """Normalized destination rectangle, independent of source cropping."""
    x: float = Field(default=0, ge=0, lt=1)
    y: float = Field(default=0, ge=0, lt=1)
    width: float = Field(default=1, gt=0, le=1)
    height: float = Field(default=1, gt=0, le=1)

    @model_validator(mode="after")
    def inside(self):
        if self.x + self.width > 1.000001 or self.y + self.height > 1.000001:
            raise ValueError("frame must stay within the output canvas")
        return self


class Scene(Contract):
    scene_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,95}$")
    asset_id: str
    duration: float = Field(gt=0, le=900)
    source_start: float = Field(default=0, ge=0)
    crop: Crop = Field(default_factory=Crop)
    frame: Frame = Field(default_factory=Frame, description="目标画布归一化矩形，默认全屏；fit在此区域内生效，外部黑底。需整图避让字幕时缩小frame并用contain，保持crop完整及motion=none，不把图表裁成分段。")
    fit: Literal["cover", "contain"] = "cover"
    source_audio: bool = False
    source_gain: float = Field(default=1, ge=0, le=4)
    motion: Literal["none", "push_in", "pull_out"] = "none"
    fade_in: float = Field(default=0, ge=0, le=10)
    fade_out: float = Field(default=0, ge=0, le=10)
    transition: Literal["cut", "dissolve"] = "cut"
    transition_seconds: float = Field(default=0, ge=0, le=10)

    @model_validator(mode="after")
    def timing(self):
        if self.fade_in + self.fade_out > self.duration:
            raise ValueError("scene fades exceed its duration")
        if (self.transition == "cut") != (self.transition_seconds == 0):
            raise ValueError("a dissolve requires an explicit positive overlap")
        if self.transition_seconds >= self.duration:
            raise ValueError("transition overlap must be shorter than the scene")
        return self


class AudioClip(Contract):
    clip_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,95}$")
    asset_id: str
    role: Literal["voice", "music", "sfx"]
    at: float = Field(ge=0)
    duration: float = Field(gt=0, le=900)
    source_start: float = Field(default=0, ge=0)
    gain: float = Field(default=1, ge=0, le=4)
    fade_in: float = Field(default=0, ge=0)
    fade_out: float = Field(default=0, ge=0)
    loop: bool = False

    @model_validator(mode="after")
    def timing(self):
        if self.fade_in + self.fade_out > self.duration:
            raise ValueError("audio fades exceed duration")
        if self.role == "voice" and self.loop:
            raise ValueError("voice cannot be looped")
        return self


class Caption(Contract):
    caption_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,95}$")
    text: str = Field(min_length=1, max_length=2000)
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    font_asset_id: str
    size: int = Field(default=56, ge=1, le=1080)
    color: str = Field(default="#FFFFFF", pattern=r"^#[0-9A-Fa-f]{6}$")
    outline_color: str = Field(default="#000000", pattern=r"^#[0-9A-Fa-f]{6}$")
    outline: int = Field(default=2, ge=0, le=20)
    background: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{8}$")
    x: float = Field(default=0.5, ge=0, le=1, description="文字块中心的横向比例，不是左边界；须为文字宽度留出空间")
    y: float = Field(default=0.88, ge=0, le=1, description="文字块中心的纵向比例，不是上边界")
    max_width: float = Field(default=0.9, gt=0, le=1)

    @model_validator(mode="after")
    def timing(self):
        if self.end <= self.start:
            raise ValueError("caption end must follow its start")
        return self


def check_timeline_identities(scenes, audio, captions):
    for entries, key in ((scenes, 'scene_id'), (audio, 'clip_id'), (captions, 'caption_id')):
        ids=[getattr(entry,key) for entry in entries]
        if len(ids)!=len(set(ids)):
            raise ValueError(key+'必须在时间线上唯一；拆分镜头保留方案场景前缀并使用-cut1/-cut2等唯一后缀，同步visual_evidence引用，不改画面、时长或旁白')


class EditProject(Contract):
    schema_version: Literal[1] = 1
    editor: Literal["ffmpeg-timeline-v1"] = "ffmpeg-timeline-v1"
    work_id: str = Field(min_length=1, max_length=128)
    plan_revision: int = Field(ge=1)
    revision: int = Field(ge=1)
    width: Literal[1080, 1920] = 1080
    height: Literal[1080, 1920] = 1920
    fps: Literal[24, 25, 30] = 30
    duration: float = Field(ge=1, le=900)
    audio_mode: Literal["silent", "music", "voice", "mixed"] = "silent"
    scenes: tuple[Scene, ...] = Field(min_length=1, max_length=1000)
    audio: tuple[AudioClip, ...] = ()
    captions: tuple[Caption, ...] = ()
    required_features: tuple[str, ...] = ()

    @model_validator(mode="after")
    def timeline(self):
        if (self.width, self.height) not in {(1080, 1920), (1920, 1080)}:
            raise ValueError("supported delivery sizes are 1080x1920 and 1920x1080")
        if self.scenes[0].transition_seconds:
            raise ValueError("the first scene cannot transition from an absent scene")
        for previous, current in zip(self.scenes, self.scenes[1:]):
            if current.transition_seconds >= previous.duration:
                raise ValueError("transition must fit the preceding scene")
        total = sum(s.duration - s.transition_seconds for s in self.scenes)
        if abs(total - self.duration) > 0.5 / self.fps:
            raise ValueError("scene durations and overlaps must equal the confirmed duration")
        for duration in [self.duration, *[s.duration for s in self.scenes],
                         *[s.transition_seconds for s in self.scenes]]:
            if abs(duration * self.fps - round(duration * self.fps)) > 1e-5:
                raise ValueError("visual timing must align to an output frame")
        check_timeline_identities(self.scenes,self.audio,self.captions)
        if any(a.at + a.duration > self.duration + 1e-6 for a in self.audio):
            raise ValueError("audio lies outside the confirmed duration")
        if any(c.end > self.duration for c in self.captions):
            raise ValueError("caption lies outside the confirmed duration")
        check_audio_delivery(self.audio_mode, self.scenes, self.audio)
        return self

    def scene_starts(self) -> tuple[float, ...]:
        starts, cursor = [], 0.0
        for scene in self.scenes:
            cursor -= scene.transition_seconds
            starts.append(cursor)
            cursor += scene.duration
        return tuple(starts)


class CheckResult(Contract):
    valid: bool
    code: str | None = None
    diagnostics: tuple[str, ...] = ()
    engine_version: str = ""


class RenderJob(Contract):
    job_id: str
    project_hash: str
    status: Literal["queued", "running", "completed", "failed", "cancelled", "interrupted"]
    stage: str = "queued"
    completed_steps: int = 0
    total_steps: int = 0
    updated_at: str
    error: str | None = None


class RenderOutput(Contract):
    job_id: str
    project_hash: str
    project_path: Path
    video_path: Path
    sha256: str
    duration: float
    width: int
    height: int
    audio_present: bool
    engine_version: str
    encoding: dict = Field(default_factory=dict)
    caption_base_path: Path | None = None
    caption_base_sha256: str | None = None


class EditorAdapter(Protocol):
    def capabilities(self) -> dict: ...
    def check(self, project: EditProject, manifest: AssetManifest) -> CheckResult: ...
    def build(self, project: EditProject, manifest: AssetManifest, *, job_id: str) -> RenderJob: ...
    def observe(self, job_id: str) -> RenderJob: ...
    def cancel(self, job_id: str) -> RenderJob: ...
    def collect(self, job_id: str) -> RenderOutput: ...


def assert_local_revision(base: EditProject, revised: EditProject, *, allowed: set[str], removable_caption_ids=frozenset()) -> None:
    """Program-side protection, independent of a model's claim about its edit."""
    if not allowed or not allowed <= {"visual", "captions", "audio"}:
        raise EditError("unknown local revision scope")
    before = base.model_dump(mode="json")
    after = revised.model_dump(mode="json")
    before.pop("revision"); after.pop("revision")
    if "captions" in allowed:
        remaining={c['caption_id'] for c in after['captions']}
        before['captions']=[c for c in before['captions'] if c['caption_id'] not in removable_caption_ids or c['caption_id'] in remaining]
        # Caption styling is local; adding/rewording/removing text needs a new plan.
        for document in (before, after):
            document["captions"] = [{k: c[k] for k in ("caption_id", "text", "start", "end")}
                                    for c in document["captions"]]
    if "visual" in allowed:
        for document in (before, after):
            for scene in document["scenes"]:
                for key in ("crop", "frame", "fit", "motion", "fade_in", "fade_out"):
                    scene.pop(key)
    if "audio" in allowed:
        # A quality adjustment may change levels/fades, not speech identity/timing.
        for document in (before, after):
            for clip in document["audio"]:
                for key in ("gain", "fade_in", "fade_out"):
                    clip.pop(key)
            for scene in document["scenes"]:
                scene.pop("source_gain")
    if before != after:
        raise EditError("local revision changes protected content, timing, or media")
