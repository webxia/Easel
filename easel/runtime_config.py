"""Secret-safe V1 runtime configuration and readiness reporting."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OPENCLAW_GATEWAY_URL = "http://127.0.0.1:18789/healthz"


class ReadinessStatus(str, Enum):
    READY = "READY"
    CONFIG_READY = "CONFIG_READY"
    CONTENT_AVAILABLE = "CONTENT_AVAILABLE"
    CONTENT_EMPTY = "CONTENT_EMPTY"
    MISSING_CONFIG = "MISSING_CONFIG"
    MISSING_CREDENTIAL = "MISSING_CREDENTIAL"
    AUTH_FAILED = "AUTH_FAILED"
    CONTRACT_FAILED = "CONTRACT_FAILED"
    NOT_CONNECTED = "NOT_CONNECTED"
    NOT_REQUIRED = "NOT_REQUIRED"
    NOT_VERIFIED = "NOT_VERIFIED"
    UNAVAILABLE = "UNAVAILABLE"
    LEGACY = "LEGACY"


@dataclass(frozen=True)
class OpenClawRuntimeConfig:
    profile: str
    gateway_url: str
    state_dir: Path = field(repr=False)


@dataclass(frozen=True)
class HypitRuntimeConfig:
    runtime_profile: str | None = field(repr=False)
    cli: str | None = None


@dataclass(frozen=True)
class MaterialRuntimeConfig:
    library_root: Path = field(repr=False)
    local_roots: tuple[str, ...] = field(repr=False)


@dataclass(frozen=True)
class GenerationRuntimeConfig:
    execution_owner: str = "Material Layer"
    requires_explicit_operator_action: bool = True


@dataclass(frozen=True)
class MiniMaxRuntimeConfig:
    api_key: str | None = field(default=None, repr=False)
    base_url: str = "https://api.minimax.cn"
    video_model: str = "MiniMax-H3-Max"
    image_model: str = "image-01"
    speech_model: str = "speech-2.8-hd"
    speech_voice_id: str = "male-qn-qingse"


@dataclass(frozen=True)
class ProvidersRuntimeConfig:
    credential_presence: Mapping[str, bool] = field(repr=False)


@dataclass(frozen=True)
class EaselRuntimeConfig:
    """Normalized config view. Secret values are private, excluded from repr and reports."""
    _values: Mapping[str, str] = field(repr=False, compare=False)
    _sources: Mapping[str, str] = field(repr=False, compare=False)
    env_file: Path = field(repr=False, compare=False)
    openclaw: OpenClawRuntimeConfig
    hypit: HypitRuntimeConfig
    material: MaterialRuntimeConfig
    generation: GenerationRuntimeConfig
    minimax: MiniMaxRuntimeConfig
    providers: ProvidersRuntimeConfig

    @classmethod
    def load(
        cls, *, environ: Mapping[str, str] | None = None,
        env_file: str | Path | None = None,
    ) -> "EaselRuntimeConfig":
        env = dict(os.environ if environ is None else environ)
        file_path = Path(env_file) if env_file else PROJECT_ROOT / ".env"
        file_values = _read_env_file(file_path)
        values: dict[str, str] = {}
        sources: dict[str, str] = {}
        for key, value in file_values.items():
            values[key], sources[key] = value, ".env"
        for key, value in env.items():
            if isinstance(value, str):
                values[key], sources[key] = value, "process environment"
        def configured(key: str) -> bool:
            value = values.get(key, "").strip().strip('"').strip("'")
            return _is_real_value(value)

        provider_keys = {
            "pexels": "PEXELS_API_KEY", "pixabay": "PIXABAY_API_KEY",
            "coverr": "COVERR_API_KEY", "unsplash": "UNSPLASH_ACCESS_KEY",
        }
        roots = tuple(item.strip() for item in values.get("EASEL_MATERIAL_LOCAL_ROOTS", "").split(os.pathsep) if item.strip())
        hypit_profile = values.get("EASEL_HYPIT_RUNTIME_PROFILE", "").strip().strip('"').strip("'") or None
        hypit_cli = values.get("HYPIT_BIN") or shutil.which("hypit")
        return cls(
            _values=values, _sources=sources, env_file=file_path,
            openclaw=OpenClawRuntimeConfig(
                profile="easel",
                gateway_url=OPENCLAW_GATEWAY_URL,
                state_dir=Path(values.get("EASEL_OPENCLAW_STATE_DIR", str(Path.home() / ".openclaw-easel"))).expanduser(),
            ),
            hypit=HypitRuntimeConfig(runtime_profile=hypit_profile, cli=hypit_cli),
            material=MaterialRuntimeConfig(
                library_root=Path(values.get("EASEL_MATERIAL_LIBRARY_ROOT", str(Path.home() / ".easel" / "material-library"))).expanduser(),
                local_roots=roots,
            ),
            generation=GenerationRuntimeConfig(),
            minimax=MiniMaxRuntimeConfig(
                api_key=(values.get("EASEL_MINIMAX_API_KEY") or values.get("MINIMAX_API_KEY") or "").strip() or None,
                base_url=values.get(
                    "EASEL_MINIMAX_BASE_URL",
                    values.get("EASEL_MINIMAX_VIDEO_BASE_URL", "https://api.minimax.cn"),
                ).strip(),
                video_model=values.get("EASEL_MINIMAX_VIDEO_MODEL", "MiniMax-H3-Max").strip(),
                image_model=values.get("EASEL_MINIMAX_IMAGE_MODEL", "image-01").strip(),
                speech_model=values.get("EASEL_MINIMAX_SPEECH_MODEL", "speech-2.8-hd").strip(),
                speech_voice_id=values.get("EASEL_MINIMAX_SPEECH_VOICE_ID", "male-qn-qingse").strip(),
            ),
            providers=ProvidersRuntimeConfig(credential_presence={
                **{name: configured(key) for name, key in provider_keys.items() if name != "openverse"},
                "openverse": configured("OPENVERSE_ACCESS_TOKEN") or (
                    configured("OPENVERSE_CLIENT_ID") and configured("OPENVERSE_CLIENT_SECRET")
                ),
            }),
        )

    def get(self, key: str, default: str = "") -> str:
        return self._values.get(key, default)

    def source(self, key: str) -> str:
        return self._sources.get(key, "not configured")

    def credential_configured(self, key: str) -> bool:
        return _is_real_value(self.get(key))

    def material_roots(self) -> tuple[str, ...]:
        return self.material.local_roots

    def startup_required_status(self) -> dict[str, str]:
        """Cheap startup check: configuration presence only, with no external calls."""
        profile_path = Path(self.hypit.runtime_profile).expanduser() if self.hypit.runtime_profile else None
        return {
            "Hypit Runtime Profile": (ReadinessStatus.READY.value if profile_path and profile_path.is_file()
                                      else ReadinessStatus.MISSING_CONFIG.value),
        }

    def readiness(self, *, profile: str = "core-video", probe_local: bool = True):
        """Compatibility entry point backed by the profile-based full registry."""
        from easel.runtime_dependencies import DependencyRegistry
        return list(DependencyRegistry(self).profile(profile, probe_local=probe_local).dependencies)


def _is_real_value(value: str) -> bool:
    value = value.strip().strip('"').strip("'")
    return bool(value) and not any(marker in value.upper() for marker in ("REPLACE_ME", "YOUR_", "<", ">"))


def _read_env_file(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return result
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.isidentifier():
            result[key] = value.strip().strip('"').strip("'")
    return result


def _http_ok(url: str) -> bool:
    try:
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=1.5) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError, TimeoutError):
        return False


def _hypit_doctor(binary: str, profile: Path) -> tuple[ReadinessStatus, str]:
    try:
        result = subprocess.run([binary, "doctor", "--runtime", str(profile), "--json"],
                                capture_output=True, text=True, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return ReadinessStatus.NOT_CONNECTED, "Hypit doctor 不可用或超时"
    payload = _json_output(result.stdout)
    if result.returncode == 0:
        return ReadinessStatus.READY, "Hypit doctor 通过"
    diagnostic = json.dumps(payload, ensure_ascii=False).lower() if payload else result.stderr.lower()
    if "credential" in diagnostic or "auth" in diagnostic or "runtime profile" in diagnostic:
        return ReadinessStatus.MISSING_CREDENTIAL, "Hypit doctor 报告 Runtime credential/configuration 未就绪"
    return ReadinessStatus.CONTRACT_FAILED, "Hypit doctor 未通过；详细输出未保留"


def _json_output(value: str):
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return None
