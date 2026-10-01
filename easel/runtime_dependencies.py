"""Full Easel dependency registry and profile-based, secret-safe readiness."""
from __future__ import annotations

import json
import hashlib
import ipaddress
import mimetypes
import os
import re
import shutil
import sqlite3
import subprocess
import urllib.error
import urllib.request
from urllib.parse import urlsplit
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Any

from easel.runtime_config import EaselRuntimeConfig, PROJECT_ROOT, ReadinessStatus


class ReadinessProfile(str, Enum):
    CORE_VIDEO = "core-video"
    V1_RELEASE = "v1-release"
    GENERATION = "generation"
    PROVIDER_FULL = "provider-full"
    AUDIO = "audio"
    FULL_SYSTEM = "full-system"


@dataclass(frozen=True)
class DependencySpec:
    id: str
    category: str
    purpose: str
    owner: str
    called_by: str
    formal_web_path: bool
    legacy: bool
    config_keys: tuple[str, ...]
    credential_owner: str
    credential_type: str
    config_source: str
    local_dependency: str
    external_dependency: str
    capabilities: tuple[str, ...]
    required_by_profiles: tuple[str, ...]
    readiness_check: str
    notes: str = ""

    def as_dict(self, status: ReadinessStatus, detail: str) -> dict[str, Any]:
        return {
            "id": self.id, "category": self.category, "purpose": self.purpose,
            "owner": self.owner, "called_by": self.called_by,
            "formal_web_path": self.formal_web_path, "legacy": self.legacy,
            "config_keys": list(self.config_keys), "credential_owner": self.credential_owner,
            "credential_type": self.credential_type, "config_source": self.config_source,
            "local_dependency": self.local_dependency,
            "external_dependency": self.external_dependency,
            "capabilities": list(self.capabilities),
            "required_by_profiles": list(self.required_by_profiles),
            "readiness_check": self.readiness_check,
            "current_status": status.value, "detail": detail, "notes": self.notes,
        }


def _spec(id: str, category: str, purpose: str, owner: str, called_by: str,
          *, formal: bool = True, legacy: bool = False, keys: tuple[str, ...] = (),
          credential_owner: str = "None", credential_type: str = "None",
          source: str = "Code default / local filesystem", local: str = "",
          external: str = "", caps: tuple[str, ...] = (), profiles: tuple[str, ...] = (),
          check: str = "static", notes: str = "") -> DependencySpec:
    memberships = list(profiles)
    if formal and not legacy and "full-system" not in memberships:
        memberships.append("full-system")
    return DependencySpec(id, category, purpose, owner, called_by, formal, legacy, keys,
                          credential_owner, credential_type, source, local, external, caps,
                          tuple(memberships), check, notes)


# This catalog intentionally includes dependencies outside the Web mainline.
DEPENDENCY_REGISTRY: tuple[DependencySpec, ...] = (
    _spec("openclaw.gateway", "agent", "Web Planning / Production Authoring agent gateway", "Easel workflow / OpenClaw runtime", "web/app.py; scripts/gateway.sh", source="OpenClaw isolated easel profile; gateway default loopback endpoint", local="openclaw executable; ~/.openclaw-easel; 127.0.0.1:18789", external="Local HTTP Gateway", caps=("planning", "production-authoring"), profiles=("core-video", "audio"), check="openclaw-health", notes="Gateway script does not consume EASEL_GATEWAY_HOST/PORT; health check is not model-auth verification."),
    _spec("openclaw.isolated-profile", "agent", "Isolated Easel OpenClaw configuration/state", "OpenClaw", "scripts/gateway.sh; setup.sh; openclaw/openclaw.json5", source="openclaw --profile easel; ~/.openclaw-easel/openclaw.json", local="openclaw/ profile and state directory", caps=("isolated-agent-config",), profiles=("core-video", "audio"), check="profile-files"),
    _spec("openclaw.question-bridge", "agent-integration", "Custom Web UI bridge for OpenClaw ask_user questions", "Easel / OpenClaw", "easel/gateway_questions.py", keys=("EASEL_OPENCLAW_STATE_DIR", "EASEL_GATEWAY_HOST", "EASEL_GATEWAY_PORT"), source="process environment; defaults ~/.openclaw-easel and 127.0.0.1:18789", local="OpenClaw profile SQLite pairing/state; local Gateway WebSocket", caps=("ask_user question list/resolve",), profiles=(), check="question-bridge", notes="Only these question-bridge settings are overridable; Gateway process/profile remains owned by scripts/setup.sh and scripts/gateway.sh."),
    _spec("openclaw.model-auth", "agent-credential", "Authentication for the configured OpenClaw model provider", "OpenClaw credential/profile owner", "OpenClaw Gateway", keys=("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "EASEL_LLM_API_KEY", "OPENAI_API_KEY", "OPENAI_MAAS_API_KEY"), credential_owner="OpenClaw profile/process environment", credential_type="Provider API token", source="OpenClaw profile + gateway process environment; Easel .env is not automatically injected", external="Configured LLM provider", caps=("planning-llm", "authoring-llm"), profiles=("core-video", "audio"), check="model-auth", notes="Presence is not authentication or model-call verification."),
    _spec("openclaw.model-endpoint", "agent", "Configured model/provider endpoint and model id", "OpenClaw", "openclaw/openclaw.json5; scripts/setup.sh; scripts/openai_maas_adapter.py", keys=("CLAUDE_MODEL", "ANTHROPIC_BASE_URL", "EASEL_LLM_BASE_URL", "EASEL_LLM_API_KEY_HEADER", "EASEL_LLM_ANTHROPIC_VERSION", "OPENAI_BASE_URL", "OPENAI_MODEL", "OPENAI_MAAS_ENDPOINT", "OPENAI_MAAS_MODEL", "OPENAI_MAAS_ADAPTER_PORT"), credential_owner="Provider / OpenClaw", credential_type="Endpoint plus provider credential", source="OpenClaw profile; setup-generated config; environment", external="Anthropic-compatible / OpenAI-compatible model endpoint", caps=("LLM inference",), profiles=("core-video", "audio"), check="llm-endpoint", notes="Does not submit a model prompt."),
    _spec("openclaw.maas-adapter", "agent", "Optional OpenAI-compatible local adapter", "Easel adapter process / remote endpoint owner", "scripts/openai_maas_adapter.py; scripts/gateway.sh", keys=("OPENAI_MAAS_API_KEY", "OPENAI_MAAS_ENDPOINT", "OPENAI_MAAS_MODEL", "OPENAI_MAAS_API_KEY_HEADER", "OPENAI_MAAS_ADAPTER_PORT"), credential_owner="Configured MaaS endpoint owner", credential_type="API key", source="process environment / .env consumed by gateway.sh", local="Python adapter on localhost:18791", external="Configured OpenAI-compatible endpoint", caps=("LLM endpoint adaptation",), profiles=(), check="adapter-config", notes="Optional if OpenClaw uses a direct provider."),
    _spec("hypit.cli", "production", "Hypit command line contract", "Hypit", "easel/integrations/hypit/cli.py", keys=("HYPIT_BIN",), source="HYPIT_BIN, PATH, ~/.local/bin/hypit", local="Hypit CLI", caps=("check", "plan", "pricing", "build", "inspect", "get"), profiles=("core-video", "audio"), check="hypit-version"),
    _spec("hypit.version", "production", "Supported Hypit contract version", "Hypit", "easel/integrations/hypit/", local="Hypit CLI package", caps=("v0.2.7 contract",), profiles=("core-video", "audio"), check="hypit-version"),
    _spec("hypit.runtime-profile", "production-config", "Runtime configuration for production operations", "Hypit Runtime", "easel/integrations/hypit/service.py", keys=("EASEL_HYPIT_RUNTIME_PROFILE",), credential_owner="Hypit", credential_type="Runtime provider auth references", source="process environment > project .env", local="Hypit Runtime profile file", caps=("check", "plan", "pricing", "build"), profiles=("core-video", "audio"), check="hypit-runtime"),
    _spec("hypit.runtime-auth", "production-credential", "Provider credentials referenced by Hypit Runtime", "Hypit auth store", "Hypit CLI/runtime", credential_owner="Hypit", credential_type="Hypit-owned auth entries", source="Hypit auth store; not Easel environment", local="Hypit credential store", caps=("runtime provider execution",), profiles=("core-video", "audio"), check="hypit-doctor", notes="Easel never reads credential values."),
    _spec("easel.operator", "execution-safety", "Same-origin loopback browser session for operator actions", "Easel", "web/app.py:create_operator_session; require_local_operator", credential_type="Short-lived HttpOnly browser session", source="Easel Web session endpoint", local="127.0.0.1 Web service", caps=("review", "rights", "pricing", "approval", "build"), profiles=("core-video", "generation", "audio"), check="operator-session", notes="Session is issued automatically to the same-origin loopback UI; paid generation, Build approval and explicit human review gates remain."),
    _spec("easel.approval-gate", "execution-safety", "Persistent approval, execution fingerprint, idempotent submit and reconciliation", "Easel + Hypit execution service", "easel/integrations/hypit/service.py; web/app.py", local="Attempt execution state / Hypit Build records", caps=("approval", "fingerprint", "idempotent build", "reconciliation"), profiles=("core-video", "generation", "audio"), check="approval-store", notes="Readiness checks storage path only, not approval or Build execution."),
    _spec("material.library-storage", "material-storage", "Material Library catalog and object storage configuration", "Easel Material Library", "easel/materials/library.py; material supply", keys=("EASEL_MATERIAL_LIBRARY_ROOT",), source="process environment > project .env; default ~/.easel/material-library", local="SQLite catalog.db + objects/", caps=("library search", "promotion", "reuse"), profiles=(), check="library-storage"),
    _spec("material.library-content", "material-content", "Material Library content availability", "Easel Material Library", "ProductMaterialSupply / Library routing", keys=("EASEL_MATERIAL_LIBRARY_ROOT",), local="catalog.db records", caps=("structured search", "semantic search", "reuse candidate"), profiles=(), check="library-content"),
    _spec("material.local-roots", "material-source", "Configured local asset roots", "Easel Material Layer", "LocalProvider / Creation preparation", keys=("EASEL_MATERIAL_LOCAL_ROOTS",), source="process environment > project .env", local="Configured directories", caps=("local discovery", "acquisition"), profiles=(), check="local-roots"),
    _spec("material.workspace-store", "material-storage", "Attempt-owned workspace and relative locators", "Easel Material Layer", "AttemptMaterialStore / Creation preparation", local="outputs / Creation Attempt workspace", caps=("workspace-owned assets", "sidecars"), profiles=("core-video",), check="workspace-storage"),
    _spec("material.rights-evidence", "rights", "Per-asset rights facts and admission evidence", "Easel Material Layer / operator", "RightsService / Material Gate", local="hash-bound .rights.json sidecar / provider evidence", caps=("rights admission",), profiles=("core-video", "v1-release", "audio"), check="rights-evidence", notes="No rights inferred from path or provider identity."),
    _spec("material.visual-source", "material-source", "At least one rights-documented visual source is available for per-Need admission", "Easel Material Layer", "MaterialReadiness / Product Supply", keys=("EASEL_MATERIAL_LOCAL_ROOTS", "EASEL_MATERIAL_LIBRARY_ROOT"), local="Rights-documented Library/Local visual assets", caps=("visual supply",), profiles=("core-video",), check="visual-source", notes="Presence is only a readiness hint; actual Need matching and asset admission still run per Attempt."),
    _spec("material.asset-sidecar", "material-storage", "Hash-bound asset technical/provenance/rights sidecars", "Easel Material Layer", "AttemptMaterialStore / Material admission", local="Attempt workspace sidecars", caps=("identity", "provenance", "rights facts"), profiles=("core-video",), check="workspace-storage"),
    _spec("provider.local", "material-provider", "Local filesystem material discovery", "Easel Material Layer", "product_provider_registry / LocalProvider", keys=("EASEL_MATERIAL_LOCAL_ROOTS",), local="Local roots", caps=("image", "video", "audio", "acquisition"), profiles=("provider-full",), check="local-provider"),
    _spec("provider.pexels", "material-provider", "Pexels material discovery and authorized acquisition", "Easel Material Layer / Pexels", "product_provider_registry / PexelsProvider", keys=("PEXELS_API_KEY",), credential_owner="Pexels", credential_type="API key", source="process environment > project .env", external="Pexels API", caps=("search", "pagination", "acquisition"), profiles=("provider-full",), check="provider-credential"),
    _spec("provider.pixabay", "material-provider", "Pixabay material discovery and authorized acquisition", "Easel Material Layer / Pixabay", "product_provider_registry / PixabayProvider", keys=("PIXABAY_API_KEY",), credential_owner="Pixabay", credential_type="API key", source="process environment > project .env", external="Pixabay API", caps=("search", "pagination", "acquisition"), profiles=("provider-full",), check="provider-credential"),
    _spec("provider.coverr", "material-provider", "Coverr material discovery/acquisition within adapter contract", "Easel Material Layer / Coverr", "product_provider_registry / CoverrProvider", keys=("COVERR_API_KEY",), credential_owner="Coverr", credential_type="API key", source="process environment > project .env", external="Coverr API", caps=("search", "discovery"), profiles=("provider-full",), check="provider-credential"),
    _spec("provider.unsplash", "material-provider", "Unsplash discovery/acquisition within adapter contract", "Easel Material Layer / Unsplash", "product_provider_registry / UnsplashProvider", keys=("UNSPLASH_ACCESS_KEY",), credential_owner="Unsplash", credential_type="Access key", source="process environment > project .env", external="Unsplash API", caps=("search", "discovery"), profiles=("provider-full",), check="provider-credential"),
    _spec("provider.openverse", "material-provider", "Openverse discovery-only route", "Easel Material Layer / Openverse", "product_provider_registry / OpenverseProvider", keys=("OPENVERSE_CLIENT_ID", "OPENVERSE_CLIENT_SECRET", "OPENVERSE_ACCESS_TOKEN"), credential_owner="Openverse", credential_type="OAuth2 client credential pair (primary); optional static Bearer compatibility fallback", source="process environment > project .env; OAuth access tokens are held in process memory and refreshed automatically", external="Openverse API", caps=("search", "discovery-only"), profiles=("provider-full",), check="openverse-provider", notes="Static OPENVERSE_ACCESS_TOKEN is optional compatibility configuration, not a requirement. DISCOVERY_ONLY is not acquired/usable MaterialAsset."),
    _spec("material.ai-generation", "material-generation", "Material-owned AI image, video and voice supply", "Easel Material Layer", "MiniMax adapters / explicit Material Generation action", keys=("EASEL_MINIMAX_API_KEY", "MINIMAX_API_KEY"), credential_owner="MiniMax", credential_type="API key", source="process environment > project .env; secret value never reported", external="MiniMax image-01, Video Generation V2, and T2A APIs", caps=("image generation", "video generation", "preset-voice TTS", "Attempt-local output", "inspection", "Rights gate"), profiles=("generation",), check="minimax-generation", notes="Each billable modality requires explicit authorization, including a scoped commission budget; readiness checks config only and does not make a provider call."),
    _spec("audio.narration", "audio-capability", "Script-bound preset-voice narration supply", "Easel Material Layer", "MiniMax T2A adapter; Production Authoring consumes admitted audio", keys=("EASEL_MINIMAX_API_KEY", "MINIMAX_API_KEY"), credential_owner="MiniMax", credential_type="API key", source="process environment > project .env; secret value never reported", external="MiniMax T2A HTTP API", caps=("preset-voice narration", "frozen Script SHA binding", "ordinary Rights/Material Gate"), profiles=("v1-release", "audio"), check="minimax-generation", notes="Preset voices only; no voice cloning. Each paid request must be within explicit authorization; Hypit only edits admitted audio."),
    _spec("audio.voice-timing-recovery", "audio-capability", "从已保存旁白恢复缺失时序", "Easel Material Layer", "MaterialProductOrchestrator.recover_voice_timing", keys=("EASEL_ASR_MODEL",), local="faster-whisper 与本地模型目录", caps=("本地识别", "冻结脚本完整核对", "句级时序恢复"), check="local-asr", notes="仅缺少有效时序时使用；不自动下载模型或调用 TTS。目录检查不是识别准确性或听感验收；不作为已有有效 Provider 时序的前置门禁。"),
    _spec("audio.bgm", "audio-source", "Rights-backed background music supply", "Material Layer + Production Authoring", "ProductMaterialSupply Library-first Need routing; Production Authoring selects the admitted Asset", local="Library/Local/eligible provider asset sources", caps=("BGM search", "rights admission"), profiles=("v1-release", "audio"), check="bgm-source", notes="Material supplies/admit candidates; Production authors use; Hypit owns timing, AudioTrack and mix."),
    _spec("audio.sfx", "audio-source", "Sound-effects supply", "Material Layer + Production Authoring", "ProductMaterialSupply Library-first Need routing; Production Authoring selects the admitted Asset", local="Library/Local/eligible provider asset sources", caps=("SFX search", "rights admission"), profiles=("audio",), check="sfx-source", notes="Not a V1_RELEASE blocker; dedicated SFX helper is not a formal Web caller."),
    _spec("audio.production", "production", "Hypit audio track/mix/encode capability in formal product path", "Hypit Production Engine", "ProductionAuthoringIntegration validates SVML/SVRun audio references; Hypit CLI check/build/export", local="Hypit CLI / Runtime", caps=("speech", "audio track", "mix", "encode"), profiles=("v1-release", "audio"), check="not-verified", notes="Software contracts require normalized selected audio on AudioTracks and an output audio stream; live Runtime execution, audible mix and clipping/listening verification remain unverified."),
    _spec("audio.rights-source", "rights", "Rights evidence for BGM/SFX assets", "Easel Material Layer / operator", "RightsService / Material Gate", local="Per-asset rights sidecar / verified provider evidence", caps=("audio rights admission",), profiles=("v1-release", "audio"), check="rights-evidence"),
    _spec("toolchain.python", "local-toolchain", "Python application runtime", "Easel", "Easel CLI / Web", local="Python >=3.10 plus project dependencies", caps=("Web", "CLI", "materials", "Hypit integration"), profiles=("core-video",), check="python-runtime"),
    _spec("toolchain.web-python-packages", "local-packages", "Direct Python packages required by the formal Web/Material/Hypit integration", "Easel", "pyproject.toml; Web; runtime_dependencies", local="fastapi, uvicorn, sse-starlette, pydantic, python-multipart, websocket-client, cryptography, Pillow", caps=("Web service", "request validation", "Gateway question bridge", "image inspection"), profiles=("core-video",), check="python-dists:fastapi,uvicorn,sse-starlette,pydantic,python-multipart,websocket-client,cryptography,Pillow"),
    _spec("toolchain.ffmpeg", "local-toolchain", "Media decode/encode/export validation", "Easel + Hypit runtime", "easel/integrations/hypit/service.py", local="ffmpeg executable", caps=("decode verification", "audio/video export QC"), profiles=("core-video", "v1-release", "audio"), check="executable:ffmpeg"),
    _spec("toolchain.ffprobe", "local-toolchain", "Media metadata / stream validation", "Easel + Hypit runtime", "easel/materials/application/inspector.py; Hypit service", local="ffprobe executable", caps=("duration", "codec", "stream", "sha/technical inspection"), profiles=("core-video",), check="executable:ffprobe"),
    _spec("toolchain.image-inspection", "local-toolchain", "Image metadata and dimensions inspection", "Easel Material Layer", "technical inspector / Pillow", local="Pillow package", caps=("image dimensions", "mime inspection"), profiles=("core-video",), check="python-module:PIL"),
    _spec("toolchain.openclaw", "local-toolchain", "OpenClaw CLI for isolated gateway", "OpenClaw", "scripts/gateway.sh; easel/cli.py", local="openclaw executable", caps=("gateway lifecycle",), profiles=("core-video",), check="executable:openclaw"),
    _spec("toolchain.node", "local-toolchain", "Node.js runtime required by OpenClaw Gateway", "OpenClaw", "OpenClaw CLI / scripts/setup.sh", local="node executable", caps=("OpenClaw gateway runtime",), profiles=("core-video",), check="executable:node"),
    # Explicit inventory for maintained legacy paths; they are visible but do not gate formal profiles.
    _spec("legacy.auto-short-video", "legacy-pipeline", "Legacy auto-short-video Skill path", "OpenClaw legacy Skill", "skills/openclaw/auto-short-video", formal=False, legacy=True, keys=("VOICE_PROVIDER", "VIDEO_PROVIDER", "MUSIC_PROVIDER"), local="ffmpeg and shared media scripts", caps=("legacy video assembly",), check="legacy", notes="LEGACY; NOT_ON_FORMAL_WEB_PATH."),
    _spec("legacy.video-production", "legacy-pipeline", "Legacy video-production Skill path", "OpenClaw legacy Skill", "skills/openclaw/video-production", formal=False, legacy=True, keys=("VOICE_PROVIDER", "VIDEO_PROVIDER", "MUSIC_PROVIDER"), local="ffmpeg and shared media scripts", caps=("legacy production",), check="legacy", notes="LEGACY; NOT_ON_FORMAL_WEB_PATH."),
    _spec("legacy.image-generation", "legacy-generation", "Standalone legacy image generation providers", "Shared media scripts", "skills/shared/scripts/ai_image.py; skills/shared/scripts/model_registry.py", formal=False, legacy=True, keys=("IMG_API_KEY", "IMG_BASE_URL", "IMG_MODEL", "IMG_API_KEY_HEADER", "IMG_API_VERSION", "IMG_NO_PROXY", "OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_API_BASE", "API_KEY", "BASE_URL"), credential_owner="Selected legacy provider", credential_type="Provider API key", source=".env/process environment; model_registry aliases", external="OpenAI-compatible/apimart/XHS MaaS image endpoint", caps=("legacy image generation",), check="legacy", notes="Not connected to Material AI generation."),
    _spec("legacy.video-generation", "legacy-generation", "Standalone legacy video providers incl. Seedance aliases", "Shared media scripts", "skills/shared/scripts/ai_video.py; skills/shared/scripts/model_registry.py", formal=False, legacy=True, keys=("VIDEO_PROVIDER", "VIDEO_CAPABILITIES_JSON", "DASHSCOPE_API_KEY", "DASHSCOPE_KEY", "ALIYUN_API_KEY", "DASHSCOPE_VIDEO_MODEL", "DASHSCOPE_MODEL", "DASHSCOPE_BASE_URL", "ARK_API_KEY", "VOLCENGINE_API_KEY", "VOLC_ARK_API_KEY", "ARK_MODEL", "ARK_BASE_URL", "KLING_ACCESS_KEY", "KLING_SECRET_KEY", "KLING_BASE_URL", "VIDEO_API_KEY", "VIDEO_BASE_URL", "VIDEO_MODEL", "VIDEO_MODEL_NAME", "OPENAI_API_KEY", "API_KEY", "OPENAI_BASE_URL", "BASE_URL", "XHS_MAAS_API_KEY", "XHS_MAAS_VIDEO_BASE", "XHS_MAAS_T2V_MODEL", "XHS_MAAS_I2V_MODEL", "XHS_MAAS_RESOLUTION", "AGNES_API_KEY", "AGNES_BASE_URL", "AGNES_POLL_BASE", "AGNES_MODEL", "AGNES_SIZE"), credential_owner="Selected legacy provider", credential_type="Provider API key / access-secret pair", source=".env/process environment; model_registry aliases", external="DashScope / Volcengine Ark Seedance / Kling / OpenAI-compatible / XHS MaaS / Agnes", caps=("legacy video generation",), check="legacy", notes="Not on formal Hypit generation path."),
    _spec("legacy.voice-tts", "legacy-audio", "Legacy TTS and voice-clone scripts", "Shared media scripts", "skills/shared/scripts/tts.py; voice_clone.py; multivoice.py; model_registry.py", formal=False, legacy=True, keys=("VOICE_PROVIDER", "VOICE_NARRATOR_VOICE_ID", "DASHSCOPE_API_KEY", "DASHSCOPE_KEY", "ALIYUN_API_KEY", "DASHSCOPE_TTS_MODEL", "DASHSCOPE_BASE_URL", "MINIMAX_API_KEY", "MINIMAX_GROUP_ID", "MINIMAX_MODEL", "MINIMAX_BASE_URL", "FISH_API_KEY", "FISH_BASE_URL", "VOICE_API_KEY", "VOICE_BASE_URL", "VOICE_MODEL", "VOICE_INSTRUCT_MODE", "VOICE_INSTRUCT_DELIM", "OPENAI_API_KEY", "API_KEY", "OPENAI_BASE_URL", "GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENAI_API_KEY", "GEMINI_TTS_MODEL", "GEMINI_VOICE", "GEMINI_BASE_URL", "GEMINI_TTS_RATE"), credential_owner="Selected legacy provider", credential_type="Provider API key / provider-specific identifiers", source=".env/process environment; model_registry aliases", external="DashScope / MiniMax / Fish Audio / Gemini / OpenAI-compatible", caps=("legacy TTS", "voice clone"), check="legacy", notes="Not connected to formal Web narration."),
    _spec("legacy.bgm", "legacy-audio", "Legacy generated BGM scripts", "Shared media scripts", "skills/shared/scripts/ai_music.py; skills/shared/scripts/model_registry.py", formal=False, legacy=True, keys=("MUSIC_PROVIDER", "DASHSCOPE_API_KEY", "DASHSCOPE_KEY", "ALIYUN_API_KEY", "DASHSCOPE_MUSIC_MODEL", "DASHSCOPE_MODEL", "DASHSCOPE_BASE_URL", "MUSIC_API_KEY", "SUNO_API_KEY", "API_KEY", "MUSIC_BASE_URL", "SUNO_BASE_URL", "BASE_URL", "MUSIC_MODEL"), credential_owner="Selected legacy provider", credential_type="Provider API key", source=".env/process environment; model_registry aliases", external="DashScope / Suno-compatible", caps=("legacy BGM generation",), check="legacy"),
    _spec("legacy.shared-ffmpeg", "legacy-toolchain", "Legacy media scripts and FFmpeg workflows", "Shared media scripts", "skills/shared/scripts; skills/openclaw/*", formal=False, legacy=True, local="ffmpeg / ffprobe / Python media packages", caps=("legacy editing", "legacy QC"), check="legacy"),
    _spec("legacy.python-packages", "legacy-toolchain", "Python packages used by media generation, publishing and analysis capabilities outside the formal video path", "Easel legacy skills", "pyproject.toml and legacy skills", formal=False, legacy=True, local="opencv-python, numpy, pandas, matplotlib, librosa, faster-whisper, edge-tts, playwright, rembg, biliup, segno, jieba, snownlp, markdown", caps=("legacy audio/video/image processing", "legacy publishing", "analytics"), check="legacy", notes="Current package manifest includes optional/legacy features; individually installed as project runtime dependencies."),
    _spec("legacy.xhs-publisher", "legacy-social", "XHS browser publishing and BitBrowser integration", "Legacy XHS publisher", "skills/shared/scripts/xhs_publish.py; web publish UI", formal=False, legacy=True, keys=("XHS_BROWSER_BACKEND", "XHS_BITBROWSER_ACCOUNT", "BITBROWSER_API_URL"), credential_owner="Local browser profile / BitBrowser", credential_type="Browser session and local browser API", source="project .env / process environment", local="Playwright Chromium or BitBrowser local service", external="XHS platform", caps=("Legacy social publishing",), check="legacy", notes="Not part of the new video-generation mainline."),
)


# Dated, secret-safe live smoke evidence. Runtime readiness does not repeat
# external calls; these entries describe the latest checked Provider contract.
_PROVIDER_LIVE_SMOKE_EVIDENCE = {
    "provider.pexels": "AUTH_VERIFIED; SEARCH_VERIFIED; REAL_WORLD_VERIFIED (2026-09-26, HTTP 200, 20 normalized candidates).",
    "provider.pixabay": "AUTH_VERIFIED; SEARCH_VERIFIED; REAL_WORLD_VERIFIED (2026-09-26, HTTP 200, 20 normalized candidates; official key query auth and shared User-Agent).",
    "provider.coverr": "AUTH_VERIFIED; SEARCH_VERIFIED; REAL_WORLD_VERIFIED (2026-09-26, HTTP 200, 20 normalized candidates).",
    "provider.unsplash": "AUTH_VERIFIED; SEARCH_VERIFIED; REAL_WORLD_VERIFIED (2026-09-26, HTTP 200, 20 normalized candidates).",
}

# V1_RELEASE is explicitly CORE_VIDEO plus its release-only audio additions.
DEPENDENCY_REGISTRY = tuple(
    replace(spec, required_by_profiles=tuple(dict.fromkeys(
        (*spec.required_by_profiles, "v1-release")
    ))) if "core-video" in spec.required_by_profiles and "v1-release" not in spec.required_by_profiles else spec
    for spec in DEPENDENCY_REGISTRY
)

@dataclass(frozen=True)
class DependencyResult:
    spec: DependencySpec
    status: ReadinessStatus
    detail: str

    @property
    def dependency(self) -> str:  # compatibility with the initial readiness CLI
        return self.spec.id

    def as_dict(self) -> dict[str, Any]:
        return self.spec.as_dict(self.status, self.detail)


@dataclass(frozen=True)
class ProfileResult:
    profile: ReadinessProfile
    status: str
    dependencies: tuple[DependencyResult, ...]
    blockers: tuple[DependencyResult, ...]
    legacy: tuple[DependencyResult, ...]

    def as_dict(self) -> dict[str, Any]:
        return {"profile": self.profile.value, "status": self.status,
                "dependencies": [row.as_dict() for row in self.dependencies],
                "blockers": [row.as_dict() for row in self.blockers],
                "legacy": [row.as_dict() for row in self.legacy]}


class DependencyRegistry:
    def __init__(self, config: EaselRuntimeConfig | None = None):
        self.config = config or EaselRuntimeConfig.load()
        self.specs = DEPENDENCY_REGISTRY

    def inventory(self, *, probe_local: bool = True) -> tuple[DependencyResult, ...]:
        return tuple(self._evaluate(spec, probe_local=probe_local) for spec in self.specs)

    def profile(self, profile: ReadinessProfile | str, *, probe_local: bool = True) -> ProfileResult:
        selected = profile if isinstance(profile, ReadinessProfile) else ReadinessProfile(profile)
        inventory = self.inventory(probe_local=probe_local)
        required = tuple(row for row in inventory if selected.value in row.spec.required_by_profiles)
        legacy = tuple(row for row in inventory if row.spec.legacy)
        good = {ReadinessStatus.READY, ReadinessStatus.CONFIG_READY, ReadinessStatus.CONTENT_AVAILABLE,
                ReadinessStatus.NOT_REQUIRED}
        blockers = tuple(row for row in required if row.status not in good)
        return ProfileResult(selected, "READY" if not blockers else "NOT_READY", required, blockers, legacy)

    def _evaluate(self, spec: DependencySpec, *, probe_local: bool) -> DependencyResult:
        if spec.legacy:
            return DependencyResult(spec, ReadinessStatus.LEGACY, "保留的 Legacy 依赖；不属于正式 Profile gate。")
        check = spec.readiness_check
        cfg = self.config
        if check == "static":
            return DependencyResult(spec, ReadinessStatus.CONFIG_READY, "目录项已登记；不要求外部调用。")
        if check == "openclaw-health":
            if probe_local and not _is_loopback_url(cfg.openclaw.gateway_url):
                return DependencyResult(spec, ReadinessStatus.NOT_CONNECTED,
                                        "Gateway health probe 仅允许回环地址；已跳过非本机 endpoint。")
            ok = _http_ok(cfg.openclaw.gateway_url) if probe_local else False
            return DependencyResult(spec, ReadinessStatus.READY if ok else ReadinessStatus.NOT_CONNECTED,
                                    "隔离 Gateway healthz 可达；未调用模型。" if ok else "本地 Gateway healthz 不可达/未探测。")
        if check == "profile-files":
            paths = [cfg.openclaw.state_dir / "openclaw.json", PROJECT_ROOT / "openclaw" / "workspace" / "AGENTS.md"]
            ok = all(path.is_file() for path in paths)
            return DependencyResult(spec, ReadinessStatus.CONFIG_READY if ok else ReadinessStatus.MISSING_CONFIG,
                                    "隔离 Easel Profile 配置与 Workspace 指令存在。" if ok else "隔离 Easel Profile 配置或 Workspace 指令缺失。")
        if check == "question-bridge":
            db = cfg.openclaw.state_dir / "state" / "openclaw.sqlite"
            host = cfg.get("EASEL_GATEWAY_HOST", "127.0.0.1")
            port = cfg.get("EASEL_GATEWAY_PORT", "18789")
            if not db.is_file():
                return DependencyResult(spec, ReadinessStatus.MISSING_CONFIG, "OpenClaw question bridge profile database 不存在。")
            try:
                int(port)
            except ValueError:
                return DependencyResult(spec, ReadinessStatus.CONTRACT_FAILED, "EASEL_GATEWAY_PORT 必须为整数。")
            status = ReadinessStatus.CONFIG_READY if host in {"127.0.0.1", "localhost", "::1"} else ReadinessStatus.NOT_VERIFIED
            return DependencyResult(spec, status, "问答桥本地配置存在；WebSocket RPC 未执行。" if status is ReadinessStatus.CONFIG_READY else "Gateway host 非回环地址，问答桥未连接验证。")
        if check in {"model-auth", "llm-endpoint"}:
            return DependencyResult(spec, ReadinessStatus.NOT_VERIFIED,
                                    "模型认证/endpoint 未通过模型请求验证；secret 不读取或输出。")
        if check == "adapter-config":
            configured = cfg.credential_configured("OPENAI_MAAS_API_KEY") and bool(cfg.get("OPENAI_MAAS_ENDPOINT"))
            return DependencyResult(spec, ReadinessStatus.CONFIG_READY if configured else ReadinessStatus.NOT_REQUIRED,
                                    "可选 adapter 配置存在。" if configured else "未配置 MaaS adapter；直接模型 endpoint 可独立使用。")
        if check == "hypit-version":
            binary = cfg.get("HYPIT_BIN") or shutil.which("hypit") or str(Path.home() / ".local/bin/hypit")
            if not Path(binary).exists() and shutil.which(binary) is None:
                return DependencyResult(spec, ReadinessStatus.NOT_CONNECTED, "Hypit CLI 不可用。")
            try:
                result = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=5, check=False)
            except (OSError, subprocess.TimeoutExpired):
                return DependencyResult(spec, ReadinessStatus.NOT_CONNECTED, "Hypit CLI version check 不可用。")
            match = re.search(r"\b(\d+\.\d+\.\d+)\b", result.stdout + " " + result.stderr)
            status = (ReadinessStatus.CONFIG_READY if result.returncode == 0 and match and match.group(1) == "0.2.7"
                      else ReadinessStatus.CONTRACT_FAILED)
            # Do not retain raw CLI output: it can contain local paths or configuration.
            if result.returncode != 0:
                detail = "Hypit version 命令失败；原始输出已丢弃。"
            elif not match:
                detail = "Hypit CLI 可执行，但无法识别版本号；原始输出已隐藏。"
                status = ReadinessStatus.NOT_VERIFIED
            elif match.group(1) != "0.2.7":
                detail = "Hypit CLI 版本与登记的 v0.2.7 契约不一致；原始输出已隐藏。"
            else:
                detail = "Hypit CLI 版本符合 v0.2.7 契约。"
            return DependencyResult(spec, status, detail)
        if check == "hypit-runtime":
            path = Path(cfg.hypit.runtime_profile).expanduser() if cfg.hypit.runtime_profile else None
            if not path:
                return DependencyResult(spec, ReadinessStatus.MISSING_CONFIG, "EASEL_HYPIT_RUNTIME_PROFILE 未配置。")
            if not path.is_file():
                return DependencyResult(spec, ReadinessStatus.MISSING_CONFIG, "Runtime profile 文件不存在。")
            return DependencyResult(spec, ReadinessStatus.CONFIG_READY, "Runtime profile 文件存在；Hypit doctor 另行检查。")
        if check == "hypit-doctor":
            path = Path(cfg.hypit.runtime_profile).expanduser() if cfg.hypit.runtime_profile else None
            binary = cfg.get("HYPIT_BIN") or shutil.which("hypit")
            if not path or not path.is_file():
                return DependencyResult(spec, ReadinessStatus.MISSING_CONFIG, "Hypit Runtime profile 未就绪。")
            if not binary:
                return DependencyResult(spec, ReadinessStatus.NOT_CONNECTED, "Hypit CLI 不可用。")
            from easel.runtime_config import _hypit_doctor
            status, detail = _hypit_doctor(binary, path)
            return DependencyResult(spec, status, detail)
        if check == "operator-session":
            return DependencyResult(
                spec, ReadinessStatus.NOT_REQUIRED,
                "本机同源浏览器会话按需建立；无需配置或手动输入 Operator 凭证。",
            )
        if check == "approval-store":
            roots = [PROJECT_ROOT / "outputs", Path.home() / ".easel" / "film-attempts"]
            present = any(path.exists() and os.access(path, os.W_OK) for path in roots)
            return DependencyResult(spec, ReadinessStatus.CONFIG_READY if present else ReadinessStatus.MISSING_CONFIG,
                                    "至少一个正式 Attempt/Output 持久化根可写。" if present else "未发现可写 Attempt/Output 持久化根。")
        if check == "library-storage":
            root = cfg.material.library_root
            if root.is_symlink() or (root / "catalog.db").is_symlink() or (root / "objects").is_symlink():
                return DependencyResult(spec, ReadinessStatus.CONTRACT_FAILED, "Library root/database/objects 不允许是符号链接。")
            if root.exists() and root.is_dir() and os.access(root, os.W_OK):
                return DependencyResult(spec, ReadinessStatus.CONFIG_READY, "Library 目录可写；内容状态单独报告。")
            return DependencyResult(spec, ReadinessStatus.MISSING_CONFIG, "Library root 不存在或不可写。")
        if check == "library-content":
            db = cfg.material.library_root / "catalog.db"
            if db.is_symlink():
                return DependencyResult(spec, ReadinessStatus.CONTRACT_FAILED, "Library catalog 数据库不允许是符号链接。")
            if not db.is_file():
                return DependencyResult(spec, ReadinessStatus.CONTENT_EMPTY, "Library catalog 尚无数据库/Asset。")
            try:
                connection = sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True, timeout=1)
                count = connection.execute("SELECT COUNT(*) FROM library_assets").fetchone()[0]
                connection.close()
            except (sqlite3.Error, OSError):
                return DependencyResult(spec, ReadinessStatus.CONTRACT_FAILED, "Library catalog schema 无法只读检查。")
            return DependencyResult(spec, ReadinessStatus.CONTENT_AVAILABLE if count else ReadinessStatus.CONTENT_EMPTY,
                                    f"Library catalog 中有 {count} 个 Asset。" if count else "Library catalog 为空。")
        if check == "local-roots":
            roots = cfg.material.local_roots
            found = bool(roots) and all(Path(root).expanduser().is_dir() for root in roots)
            status = ReadinessStatus.CONFIG_READY if found else ReadinessStatus.MISSING_CONFIG
            return DependencyResult(spec, status, f"检查了 {len(roots)} 个配置 root；路径不输出。" if found else "没有全部可用的 Local root。")
        if check == "workspace-storage":
            path = PROJECT_ROOT / "outputs"
            ok = path.exists() and path.is_dir() and os.access(path, os.W_OK)
            return DependencyResult(spec, ReadinessStatus.CONFIG_READY if ok else ReadinessStatus.MISSING_CONFIG,
                                    "Attempt workspace 根可写。" if ok else "Attempt workspace 根缺失或不可写。")
        if check == "rights-evidence":
            count = _rights_evidence_count(cfg.material.local_roots, cfg.material.library_root)
            return DependencyResult(spec, ReadinessStatus.CONTENT_AVAILABLE if count else ReadinessStatus.CONTENT_EMPTY,
                                    f"发现 {count} 个结构有效的 Rights sidecar；仍须逐 Asset 做 admission。" if count else "未发现可验证的 Rights sidecar；不按目录或 Provider 推断。")
        if check == "provider-credential":
            key = spec.config_keys[0]
            if not cfg.credential_configured(key):
                return DependencyResult(spec, ReadinessStatus.MISSING_CREDENTIAL, f"{key} 未配置。")
            evidence = _PROVIDER_LIVE_SMOKE_EVIDENCE.get(spec.id)
            if evidence:
                return DependencyResult(
                    spec,
                    ReadinessStatus.CONFIG_READY,
                    f"{evidence} Readiness 不触发网络请求；素材获取与 Rights Admission 仍单独处理。",
                )
            return DependencyResult(spec, ReadinessStatus.NOT_VERIFIED, "凭证存在；尚无日期化真实 Provider smoke 记录。")
        if check == "openverse-provider":
            has_client_id = cfg.credential_configured("OPENVERSE_CLIENT_ID")
            has_client_secret = cfg.credential_configured("OPENVERSE_CLIENT_SECRET")
            if has_client_id != has_client_secret:
                return DependencyResult(
                    spec, ReadinessStatus.CONTRACT_FAILED,
                    "Openverse OAuth client ID 与 client secret 必须成对配置。",
                )
            if has_client_id and has_client_secret:
                status = ReadinessStatus.CONFIG_READY
                detail = (
                    "AUTH_VERIFIED; SEARCH_VERIFIED; REAL_WORLD_VERIFIED（2026-09-26 OAuth token + image search，20 个 normalized candidates）。"
                    "OAuth client pair 为主认证；access token 在进程内自动获取、缓存和刷新。"
                    "capability=DISCOVERY_ONLY；本 readiness 不发起网络请求，素材获取与 Rights Admission 仍需单独验证。"
                )
            elif cfg.credential_configured("OPENVERSE_ACCESS_TOKEN"):
                status = ReadinessStatus.NOT_VERIFIED
                detail = (
                    "仅配置了兼容静态 Bearer token；未执行本次 OAuth live verification，且静态 token 不会自动刷新。"
                    "建议配置 OAuth client pair。capability=DISCOVERY_ONLY。"
                )
            else:
                status = ReadinessStatus.MISSING_CREDENTIAL
                detail = "需要 OPENVERSE_CLIENT_ID 与 OPENVERSE_CLIENT_SECRET；OPENVERSE_ACCESS_TOKEN 仅为可选兼容配置。"
            return DependencyResult(spec, status, detail)
        if check == "local-provider":
            roots = cfg.material.local_roots
            return DependencyResult(spec, ReadinessStatus.CONFIG_READY if roots and all(Path(r).is_dir() for r in roots) else ReadinessStatus.MISSING_CONFIG,
                                    "LocalProvider roots 可用。" if roots and all(Path(r).is_dir() for r in roots) else "LocalProvider 没有可用的 roots。")
        if check in {"bgm-source", "sfx-source"}:
            kinds = {"background-music", "bgm", "music"} if check == "bgm-source" else {
                "sound-effect", "sound-effects", "sfx",
            }
            count = _rights_evidence_count(cfg.material.local_roots, cfg.material.library_root, {"audio"}, kinds)
            return DependencyResult(spec, ReadinessStatus.CONTENT_AVAILABLE if count else ReadinessStatus.CONTENT_EMPTY,
                                    f"本地 Rights sidecar 样本数：{count}；素材 suitability 仍按 Need 判断。")
        if check == "visual-source":
            count = _rights_evidence_count(cfg.material.local_roots, cfg.material.library_root, {"image", "video"})
            return DependencyResult(spec, ReadinessStatus.CONTENT_AVAILABLE if count else ReadinessStatus.CONTENT_EMPTY,
                                    f"发现 {count} 个含逐 Asset Rights evidence 的样本；实际使用仍需 Need-specific admission。" if count else "尚无可检查的 Rights-backed Library/Local visual asset。")
        if check == "not-connected":
            return DependencyResult(spec, ReadinessStatus.NOT_CONNECTED, "当前正式 Web 产品链没有连接该 capability。")
        if check == "local-asr":
            from importlib.util import find_spec
            from easel.materials.application.voice_delivery import LOCAL_ASR_FILES, local_voice_model_path
            model = local_voice_model_path(cfg)
            available = find_spec('faster_whisper') is not None and all((model / name).is_file() for name in LOCAL_ASR_FILES)
            return DependencyResult(spec, ReadinessStatus.CONFIG_READY if available else ReadinessStatus.MISSING_CONFIG,
                                    "本地识别依赖与模型文件存在；未加载模型或验证准确性。" if available else
                                    "本地识别依赖或模型目录未就绪；可配置 EASEL_ASR_MODEL。已有有效旁白时序不受影响。")
        if check == "minimax-generation":
            if not (cfg.credential_configured("EASEL_MINIMAX_API_KEY")
                    or cfg.credential_configured("MINIMAX_API_KEY")):
                return DependencyResult(spec, ReadinessStatus.MISSING_CREDENTIAL, "MiniMax API key 未配置；secret 值不会读取或输出。")
            if (cfg.minimax.video_model not in {"MiniMax-H3", "MiniMax-H3-Max"}
                    or cfg.minimax.image_model != "image-01"
                    or cfg.minimax.speech_model not in {"speech-2.8-hd", "speech-2.8-turbo", "speech-2.6-hd", "speech-2.6-turbo"}):
                return DependencyResult(spec, ReadinessStatus.CONTRACT_FAILED, "MiniMax 模型配置不受当前 Adapters 支持。")
            return DependencyResult(spec, ReadinessStatus.CONFIG_READY, "MiniMax 图片、视频和预置音色 TTS Adapter 与凭证配置存在；Readiness 不发起模型请求，真实性能与生成结果需单独验收。")
        if check == "not-verified":
            return DependencyResult(
                spec, ReadinessStatus.NOT_VERIFIED,
                "正式 Web 软件调用边已接通并有确定性验收；当前 Runtime capability 与真实产品输出尚未验证。",
            )
        if check.startswith("executable:"):
            name = check.split(":", 1)[1]
            path = shutil.which(name)
            return DependencyResult(spec, ReadinessStatus.CONFIG_READY if path else ReadinessStatus.UNAVAILABLE,
                                    f"{name} 可执行文件可用。" if path else f"{name} 未安装/不在 PATH。")
        if check.startswith("python-module:"):
            import importlib.util
            name = check.split(":", 1)[1]
            return DependencyResult(spec, ReadinessStatus.CONFIG_READY if importlib.util.find_spec(name) else ReadinessStatus.UNAVAILABLE,
                                    f"Python 模块 {name} 可导入。" if importlib.util.find_spec(name) else f"Python 模块 {name} 不可用。")
        if check.startswith("python-dists:"):
            from importlib import metadata
            names = check.split(":", 1)[1].split(",")
            missing = [name for name in names if _distribution_version(metadata, name) is None]
            return DependencyResult(spec, ReadinessStatus.UNAVAILABLE if missing else ReadinessStatus.CONFIG_READY,
                                    "缺少项目运行依赖：" + ", ".join(missing) if missing else "正式 Web/Material Python distribution 均已安装。")
        if check == "python-runtime":
            import sys
            ok = sys.version_info >= (3, 10)
            return DependencyResult(spec, ReadinessStatus.CONFIG_READY if ok else ReadinessStatus.UNAVAILABLE,
                                    f"Python {sys.version_info.major}.{sys.version_info.minor}。")
        return DependencyResult(spec, ReadinessStatus.NOT_VERIFIED, "未配置专用无费用 readiness probe。")


def _http_ok(url: str) -> bool:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"Accept": "application/json"}), timeout=1.5) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError, TimeoutError):
        return False


def _is_loopback_url(url: str) -> bool:
    try:
        host = urlsplit(url).hostname
        if host == "localhost":
            return True
        return bool(host and ipaddress.ip_address(host).is_loopback)
    except ValueError:
        return False


def _distribution_version(metadata_module, name: str) -> str | None:
    try:
        return metadata_module.version(name)
    except metadata_module.PackageNotFoundError:
        return None


def _rights_evidence_count(
    roots: tuple[str, ...], library_root: Path, media_types: set[str] | None = None,
    source_kinds: set[str] | None = None,
) -> int:
    """Count admitted-evidence MaterialAssets and hash-bound local Rights sidecars."""
    from easel.materials.domain import MaterialAsset, RightsInfo, RightsStatus

    assets: list[dict[str, Any]] = []
    scan_roots = [Path(root_text).expanduser() for root_text in roots]
    scan_roots.append(PROJECT_ROOT / "outputs")
    for root in scan_roots:
        if root.is_symlink() or not root.is_dir():
            continue
        try:
            paths = list(root.rglob("asset.json"))[:500]
        except OSError:
            continue
        for path in paths:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(data, dict):
                assets.append(data)
    db = library_root / "catalog.db"
    if not library_root.is_symlink() and not db.is_symlink() and db.is_file():
        try:
            connection = sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True, timeout=1)
            assets.extend(json.loads(row[0]) for row in connection.execute("SELECT asset_json FROM library_assets"))
            connection.close()
        except (sqlite3.Error, OSError, json.JSONDecodeError):
            pass
    seen: set[str] = set()
    valid = 0
    for raw in assets:
        try:
            asset = MaterialAsset.model_validate(raw)
        except (TypeError, ValueError):
            continue
        if asset.file.sha256 in seen or (media_types and asset.media_type.value not in media_types):
            continue
        seen.add(asset.file.sha256)
        rights = asset.rights
        if rights.status in {RightsStatus.PUBLIC_DOMAIN, RightsStatus.KNOWN, RightsStatus.ATTRIBUTION_REQUIRED} and any(
            item.kind.casefold().startswith("asset_") and item.reference for item in rights.evidence
        ):
            if source_kinds:
                semantic = asset.semantic
                role_facts = [*semantic.tags, *(str(value) for value in semantic.attributes.values())]
                normalized = {value.strip().casefold().replace("_", "-") for value in role_facts if value.strip()}
                if not normalized.intersection(source_kinds):
                    continue
            valid += 1

    # Local source folders may hold the original bytes and their documented
    # hash-bound sidecar before promotion into an Attempt or Library record.
    # Count those facts only after validating the sibling bytes and evidence;
    # never infer Rights or media role from a directory name.
    for root in scan_roots:
        if root.is_symlink() or not root.is_dir():
            continue
        try:
            sidecars = list(root.rglob("*.rights.json"))[:500]
        except OSError:
            continue
        for sidecar in sidecars:
            try:
                if sidecar.is_symlink() or sidecar.stat().st_size > 64 * 1024:
                    continue
            except OSError:
                continue
            media_path = Path(str(sidecar)[:-len(".rights.json")])
            if media_path.is_symlink() or not media_path.is_file():
                continue
            mime, _ = mimetypes.guess_type(media_path.name)
            family = mime.split("/", 1)[0] if mime and "/" in mime else None
            if media_types and family not in media_types:
                continue
            try:
                facts = json.loads(sidecar.read_text(encoding="utf-8"))
                expected = facts.get("asset_sha256")
                rights = facts.get("rights")
                if (facts.get("schema") != "easel-local-rights@1"
                        or not isinstance(rights, dict) or not isinstance(expected, str)):
                    continue
                rights_info = RightsInfo.model_validate_json(json.dumps(rights))
                if rights_info.status not in {
                    RightsStatus.PUBLIC_DOMAIN, RightsStatus.KNOWN, RightsStatus.ATTRIBUTION_REQUIRED,
                }:
                    continue
                if not any(item.kind.casefold().startswith("asset_") and item.reference for item in rights_info.evidence):
                    continue
                if rights_info.status is RightsStatus.KNOWN and not rights_info.license_name:
                    continue
                if rights_info.status is RightsStatus.ATTRIBUTION_REQUIRED and not (
                    rights_info.attribution_required and rights_info.attribution_text
                ):
                    continue
                if hashlib.sha256(media_path.read_bytes()).hexdigest() != expected:
                    continue
                if source_kinds:
                    source_paths = (
                        media_path.with_name(media_path.name + ".source.json"),
                        media_path.parent / "source.json",
                    )
                    source_facts = None
                    for source_path in source_paths:
                        try:
                            candidate_facts = json.loads(source_path.read_text(encoding="utf-8"))
                        except (OSError, json.JSONDecodeError):
                            continue
                        if candidate_facts.get("file") == media_path.name:
                            source_facts = candidate_facts
                            break
                    if source_facts is None:
                        continue
                    kind = str(source_facts.get("kind", "")).strip().casefold().replace("_", "-")
                    if kind not in source_kinds:
                        continue
                if expected not in seen:
                    seen.add(expected)
                    valid += 1
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                continue
    return valid
