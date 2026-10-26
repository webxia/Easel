"""MiniMax pause protocol guards, not a claim about perceived naturalness."""
from copy import deepcopy
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from easel.production.contracts import Scene, VoiceIdentity, fingerprint
from easel.production.errors import ProductionError
from easel.production.planning import (
    CreativePlan, NarrationPlanChanges, VoiceReadyCreativePlan, merge_narration_changes,
)
from easel.production.prosody import VERSION, compile_pauses
from easel.production.voice import VoiceBinding, VoiceService


def voice():
    return VoiceIdentity(provider='minimax', model='speech-2.8-turbo',
                         engine='minimax-speech-v1', voice_id='fixed')


def draft(seconds):
    text = '先看问题，再说原因。'
    return {'title': '测试', 'summary': '同一事实', 'script': text,
            'scenes': [{'id': 'scene', 'purpose': '解释', 'visual': '普通工作台',
                        'narration': text, 'narration_pauses': [{'after': 5, 'seconds': seconds}]}],
            'settings': {'audio_mode': 'voice', 'duration_seconds': 20,
                         'voice': voice().model_dump()},
            'narration_policy': {'continuous': True, 'duration_mode': 'voice_driven'}}


@pytest.mark.parametrize('seconds,wire', [(.05, '.05'), (.1, '.1'), (.12, '.12'), (.29, '.29'), (1, '1')])
def test_legal_pause_wire_and_identity_unchanged(seconds, wire):
    value = draft(seconds)
    before = deepcopy(value)
    parsed = VoiceReadyCreativePlan.model_validate(value)
    text = parsed.scenes[0].narration
    pauses = value['scenes'][0]['narration_pauses']
    expected = '先看问题，<#' + ('0' if wire.startswith('.') else '') + wire + '#>再说原因。'
    assert compile_pauses(text, pauses, voice()) == expected
    assert value == before
    assert VERSION == 'minimax-pauses-1'


@pytest.mark.parametrize('seconds', [.123, .051, .999, .1 + .2])
def test_generated_draft_and_send_reject_precision_without_rounding(seconds):
    value = draft(seconds)
    before = deepcopy(value)
    with pytest.raises(ValidationError, match='最多两位小数'):
        VoiceReadyCreativePlan.model_validate(value)
    scene = value['scenes'][0]
    with pytest.raises(ProductionError, match='最多两位小数'):
        compile_pauses(scene['narration'], scene['narration_pauses'], voice())
    assert value == before


def test_historical_plan_still_readable_and_byte_equivalent():
    # Persisted CreativePlan/Scene contracts are not migrated or normalized.
    value = draft(.123)
    parsed = CreativePlan.model_validate(value)
    saved = parsed.model_dump(mode='json')
    assert Scene.model_validate(saved['scenes'][0]).narration_pauses[0].seconds == .123
    assert fingerprint(CreativePlan.model_validate(saved).model_dump(mode='json')) == fingerprint(saved)
    assert compile_pauses('原文保持。', [], voice()) == '原文保持。'


def test_narration_revision_validates_new_pause_before_freeze():
    base = CreativePlan.model_validate(draft(.2)).model_dump(mode='json')
    before = deepcopy(base)
    delta = NarrationPlanChanges.model_validate({'scenes': [
        {'id': 'scene', 'narration_pauses': [{'after': 5, 'seconds': .123}]}]})
    with pytest.raises(ValidationError, match='最多两位小数'):
        merge_narration_changes(delta, base)
    assert base == before


def test_invalid_precision_stops_before_operation_reservation_or_transport(tmp_path):
    # Exercise the real synthesis entry; no fake audio or paid request is used.
    service = VoiceService(SimpleNamespace(), tmp_path / 'cache', [])
    service._adapter = lambda *args, **kwargs: SimpleNamespace()
    binding = VoiceBinding('operation', 'work', 'run', 'task', 'grant', 1)
    with pytest.raises(ProductionError, match='最多两位小数'):
        service.synthesize(binding, identity=voice(), text='先看问题，再说原因。',
                           segment_id='scene', pauses=[{'after': 5, 'seconds': .123}])
    assert list((tmp_path / 'cache').iterdir()) == []
