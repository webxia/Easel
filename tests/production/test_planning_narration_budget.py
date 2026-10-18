"""Voice-only narration is checked and model-repaired BEFORE plan freezing."""
import asyncio
import json

import pytest
from pydantic import ValidationError

from easel.production.context import TaskContext
from easel.production.model_tasks import ModelTaskRunner, ModelTaskError
from easel.production.planning import CreativePlan, VoiceReadyCreativePlan
from easel.production.voice_budget import reserve_narration_slots


def plan(narration: str):
    return {
        'title': '从想法到作品',
        'summary': '真实尝试和留痕',
        'script': '安静现实主义短章，保持文字、画面与BGM风格',
        'settings': {
            'duration_seconds': 45, 'aspect_ratio': '9:16', 'audio_mode': 'mixed',
            'voice': {
                'provider': 'minimax', 'model': 'speech-2.8-hd',
                'voice_id': 'male-qn-qingse',
            },
        },
        'scenes': [
            {'id': 's01', 'purpose': '开场', 'visual': '城市', 'duration_seconds': 9,
             'narration': narration, 'required_input_ids': []},
            {'id': 's02', 'purpose': '记录', 'visual': '记录过程', 'duration_seconds': 36,
             'narration': '把一次真实尝试留下来。', 'required_input_ids': []},
        ],
        'facts': [], 'core_views': [], 'constraints': [],
        'adaptation_permissions': [],
    }


class Responses:
    capabilities = frozenset({'text','structured'})
    def __init__(self, values):
        self.values=iter(values)
        self.calls=[]
    async def complete(self, messages, tools, schema):
        self.calls.append(json.loads(json.dumps(messages,ensure_ascii=False)))
        return {'content':json.dumps(next(self.values),ensure_ascii=False)}


def test_planning_rejects_timestamps_and_direction_without_changing_original_contract():
    broken=plan('00:00.8–00:04.5：很多想法，先停在计划里。句前后保留停顿。')
    assert CreativePlan.model_validate(broken)
    with pytest.raises(ValidationError,match='narration'):
        VoiceReadyCreativePlan.model_validate(broken)
    clean=plan('很多想法，先停在计划里。')
    candidate=VoiceReadyCreativePlan.model_validate(clean)
    assert reserve_narration_slots(candidate.model_dump(mode='json'))['settings']['duration_seconds']==45


def test_budget_rejects_unrealistic_spoken_text_before_tts():
    impossible=plan('反复写计划却不做实际尝试。'*110)
    with pytest.raises(ValidationError,match='plan_voice_budget_unavailable'):
        VoiceReadyCreativePlan.model_validate(impossible)


def test_model_repairs_spoken_narration_from_precise_feedback_automatically():
    broken=plan('00:00.8–00:04.5：很多想法，先停在计划里。句前后保留停顿。')
    good=plan('很多想法，先停在计划里。')
    transport=Responses([broken,good])
    calls=[]
    async def authorized(ctx):
        calls.append(ctx.task_id)
    runner=ModelTaskRunner(transport,authorized,max_format_repairs=2)
    answer=asyncio.run(runner.run(
        TaskContext('work','run','task',brief='真实视频创作'),
        '提出创作方案，旁白只含要朗读的文字',VoiceReadyCreativePlan))
    assert answer.scenes[0].narration==good['scenes'][0]['narration']
    assert calls==['task','task']
    assert len(transport.calls)==2
    last=transport.calls[-1][-1]['content']
    assert '旁白窗口' in last and 'narration' in last
    assert 'value_error' in last


def test_model_correction_is_bounded_if_narration_remains_invalid():
    broken=plan('00:00.8–00:04.5：旁白窗口：很多想法。')
    transport=Responses([broken,broken,broken])
    async def authorized(ctx):pass
    with pytest.raises(ModelTaskError) as exc:
        asyncio.run(ModelTaskRunner(transport,authorized,max_format_repairs=2).run(
            TaskContext('w','r','t'), 'plan',VoiceReadyCreativePlan))
    assert exc.value.code=='invalid_model_output'
    assert len(transport.calls)==3


def test_silent_scene_not_subject_to_spoken_voice_budget():
    sample=plan('00:00.8–00:04.5：无声视频中的可见文字')
    sample['settings']['audio_mode']='silent'
    sample['settings']['voice']=None
    assert VoiceReadyCreativePlan.model_validate(sample)
