"""Pure settings resolution; persistence and revision checks belong to the service."""
from __future__ import annotations

from copy import deepcopy
from typing import Literal

from .contracts import SubtitleSettings, VideoSettings, VoiceIdentity
from .errors import ProductionError

SettingsScope = Literal["work", "channel", "profile"]
_KEYS = {"duration_seconds", "aspect_ratio", "audio_mode", "voice", "subtitles"}


def merge_creation_settings(*layers: dict) -> dict:
    """Merge already-validated creation layers, preserving subtitle field choices.

    Voice and director versions are indivisible identities. Used both before a
    conversation creates a Work and by the authoritative Work creation path.
    """
    result = {}
    for values in layers:
        patch = deepcopy(values)
        if "subtitles" in patch:
            patch["subtitles"] = {**result.get("subtitles", {}), **patch["subtitles"]}
        result.update(patch)
    return result


def settings_origins(*, profile=None, channel=None, work=None) -> dict:
    """Field provenance for already-validated layers, without inventing defaults."""
    origins = {}
    for scope, values in (("profile", profile), ("channel", channel), ("work", work)):
        for key, value in (values or {}).items():
            if key == "schema_version":
                continue
            if key == "subtitles":
                for field in value:
                    origins[f"subtitles.{field}"] = scope
            else:
                origins[key] = scope
    return origins


def recorded_settings_source(context: dict) -> dict:
    """Legacy resolved 'explicit' bags are not evidence of per-field choices."""
    source = context.get('settings_source') or {}
    return deepcopy(source) if 'origins' in source else {}


def validate_settings_patch(settings: dict) -> dict:
    """Validate partial defaults without inventing missing per-work choices."""
    if not isinstance(settings, dict) or set(settings) - _KEYS:
        raise ProductionError("invalid_settings", "设置包含不支持的字段")
    data = deepcopy(settings)
    if "voice" in data and data["voice"] is not None:
        voice = VoiceIdentity.model_validate(data["voice"])
        if not voice.engine:
            raise ProductionError("voice_identity_incomplete", "固定声音需要明确的服务、模型、音色与引擎")
        data["voice"] = voice.model_dump(mode="json")
    if "subtitles" in data:
        SubtitleSettings.model_validate(data["subtitles"])
    VideoSettings.model_validate({"duration_seconds": 90, "audio_mode": "silent", **data})
    return data


def resolve_settings(*, work: dict | None = None, channel: dict | None = None,
                     profile: dict | None = None) -> dict:
    """Snapshot work > channel > profile. Voice identity is an indivisible choice.

    Explicit work.voice=None clears inheritance. Subtitle fields can be layered;
    neither this function nor changing a default mutates an earlier snapshot.
    """
    result: dict = {}
    for scope, values in (("profile", profile), ("channel", channel), ("work", work)):
        patch = validate_settings_patch(values or {})
        for key, value in patch.items():
            if key == "subtitles":
                result[key] = {**result.get(key, {}), **deepcopy(value)}
            else:
                result[key] = deepcopy(value)
    return {"settings": result, "origins": settings_origins(profile=profile, channel=channel, work=work)}


def settings_save_request(*, scope: SettingsScope, settings: dict,
                          channel_id: str | None = None, profile_ref: str | None = None) -> dict:
    """Return exactly the requested save scope; the caller owns its transaction."""
    if scope not in {"work", "channel", "profile"}:
        raise ProductionError("invalid_settings_scope", "请选择本片、频道或画像")
    if scope == "channel" and not channel_id:
        raise ProductionError("channel_required", "本作品尚未选择频道")
    if scope == "profile" and not profile_ref:
        raise ProductionError("profile_required", "本作品尚未选择画像")
    return {"scope": scope, "settings": validate_settings_patch(settings),
            "target_ref": channel_id if scope == "channel" else profile_ref if scope == "profile" else None}
