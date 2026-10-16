"""Contracts reject invented authority and invalid production combinations."""
import pytest
from pydantic import ValidationError

from easel.production.contracts import (
    ArtifactSpec, CommandEnvelope, GrantSpec, PlanDocument, VideoSettings,
    WorkCreate, canonical_json, fingerprint,
)


def plan_payload():
    return {"title": "少一点准备", "summary": "一次写作经历", "script": "关掉工具，开始写第一段。",
            "scenes": [{"id": "scene_1", "purpose": "交代经历", "visual": "用户提供的桌面画面"}],
            "settings": {"duration_seconds": 90, "audio_mode": "silent"}}


def test_no_profile_is_a_valid_work():
    assert WorkCreate(title="临时作品").profile_ref is None


@pytest.mark.parametrize("field,value", [("owner_epoch", 10), ("accepted", True), ("image_limit", 999)])
def test_model_plan_cannot_smuggle_program_authority(field, value):
    with pytest.raises(ValidationError):
        PlanDocument.model_validate({**plan_payload(), field: value})


def test_plan_rejects_unknown_fields_nested_and_repeated_scene_ids():
    payload = plan_payload()
    payload["scenes"][0]["grant_id"] = "some-grant"
    with pytest.raises(ValidationError):
        PlanDocument.model_validate(payload)
    payload = plan_payload()
    payload["scenes"] *= 2
    with pytest.raises(ValidationError):
        PlanDocument.model_validate(payload)


@pytest.mark.parametrize("duration", [0, 901, float("inf"), float("nan")])
def test_duration_limits(duration):
    with pytest.raises(ValidationError):
        VideoSettings(duration_seconds=duration, audio_mode="silent")


@pytest.mark.parametrize("purpose", ["planning", "preview"])
def test_preproduction_service_permission_cannot_expand_image_video(purpose):
    permission = {"purpose": purpose, "services": [{"provider": "local", "model": "model", "mode": "text"}]}
    assert GrantSpec.model_validate(permission).image_limit == 0
    for change in ({"allow_ai": True}, {"image_limit": 1}, {"video_limit": 1}):
        with pytest.raises(ValidationError):
            GrantSpec.model_validate({**permission, **change})


def test_production_grant_requires_specific_plan_and_service_mode():
    payload = {"purpose": "production", "services": [{"provider": "test", "model": "image", "mode": "standard"}]}
    with pytest.raises(ValidationError):
        GrantSpec.model_validate(payload)
    assert GrantSpec.model_validate({**payload, "plan_revision": 2, "image_limit": 2}).plan_revision == 2
    with pytest.raises(ValidationError):
        GrantSpec.model_validate({**payload, "plan_revision": 2, "image_limit": True})


def test_command_identifiers_cannot_be_filesystem_paths():
    with pytest.raises(ValidationError):
        CommandEnvelope(command_id="../../other")


def test_fingerprints_are_stable_and_do_not_accept_non_json():
    assert fingerprint({"b": 2, "a": 1}) == fingerprint({"a": 1, "b": 2})
    assert fingerprint({"a": 1}) != fingerprint({"a": "1"})
    with pytest.raises(ValueError):
        canonical_json({"value": float("nan")})


def test_artifact_requires_actual_digest_and_nonnegative_size():
    with pytest.raises(ValidationError):
        ArtifactSpec(kind="video", storage_ref="work/video.mp4", digest="claimed-good", size_bytes=-1)
