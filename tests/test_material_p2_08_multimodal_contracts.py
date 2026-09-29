from __future__ import annotations

import json
import pytest
from pydantic import ValidationError

from easel.materials.domain import (
    BgmNeedSpec, ImageNeedSpec, MaterialNeed, MediaType, NeedImportance,
    NeedIntent, NeedScope, NeedScopeType, SfxNeedSpec, VideoNeedSpec,
    VoiceIdentityRef, VoiceIdentitySource, VoiceNeedSpec,
)


def make_need(media_type, role, spec=None, *, scope=NeedScopeType.SCENE):
    return MaterialNeed(
        need_id="need-1", scope=NeedScope(type=scope, ref="ref-1"),
        media_type=media_type, role=role, intent=NeedIntent(description="intent"),
        importance=NeedImportance.REQUIRED, modality_spec=spec,
    )


def test_legacy_need_without_multimodal_spec_still_loads():
    payload = {
        "need_id": "legacy", "scope": {"type": "scene", "ref": "scene"},
        "media_type": "video", "role": "b_roll", "intent": {"description": "train"},
        "importance": "required",
    }
    assert MaterialNeed.model_validate_json(json.dumps(payload)).modality_spec is None


@pytest.mark.parametrize("need", [
    make_need(MediaType.IMAGE, "image", ImageNeedSpec(aspect_ratio="9:16")),
    make_need(MediaType.VIDEO, "video", VideoNeedSpec(aspect_ratio="9:16", generate_audio=False)),
    make_need(MediaType.AUDIO, "voice", VoiceNeedSpec(identity=VoiceIdentityRef(
        source=VoiceIdentitySource.CREATOR_CONTEXT, reference="creator.voice_profile"))),
    make_need(MediaType.AUDIO, "bgm", BgmNeedSpec(mood="warm", vocals_allowed=False)),
    make_need(MediaType.AUDIO, "sfx", SfxNeedSpec(event_description="door closes"), scope=NeedScopeType.EVENT),
])
def test_multimodal_need_contract_round_trip(need):
    assert MaterialNeed.model_validate_json(need.to_json()) == need


def test_modality_media_mismatch_and_sfx_without_event_scope_are_rejected():
    with pytest.raises(ValidationError):
        make_need(MediaType.VIDEO, "image", ImageNeedSpec())
    with pytest.raises(ValidationError):
        make_need(MediaType.AUDIO, "sfx", SfxNeedSpec(event_description="impact"))


def test_voice_text_reference_requires_sha256_pair():
    with pytest.raises(ValidationError):
        VoiceNeedSpec(text_ref="stable-script")
