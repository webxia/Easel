"""Deterministic conservative narration preflight using prior real MiniMax TTS evidence."""
import copy
import json
import sqlite3
from pathlib import Path
import pytest
from easel.production.model_tasks import ModelTaskError
from easel.production.voice_budget import reserve_narration_slots


def test_voice_budget_catches_first_real_tts_overrun_without_modifying_creator_duration():
    root=Path(__file__).parents[2]
    db=root/'outputs/_production/production.sqlite3'
    if not db.exists():pytest.skip('real model output only available in E2E runtime')
    conn=sqlite3.connect('file:'+str(db)+'?mode=ro',uri=True)
    row=conn.execute('SELECT payload_json FROM plan_revisions WHERE work_id=? AND revision=1',
                     ('f8040a6d153c419aaf1045eadc61bc63',)).fetchone()
    if not row:pytest.skip('real Plan not available')
    plan=json.loads(row[0])
    revised=reserve_narration_slots(plan)
    assert revised['scenes'][0]['duration_seconds'] >= 6.653
    assert abs(sum(s['duration_seconds'] for s in revised['scenes'])-45)<1e-8
    assert [s['narration'] for s in revised['scenes']]==[s['narration'] for s in plan['scenes']]
    assert plan['scenes'][0]['duration_seconds']==6
    assert revised['settings']==plan['settings']


def test_budget_fits_underallocated_scene_and_is_idempotent():
    scene=lambda id,narration,duration:dict(id=id,narration=narration,duration_seconds=duration,purpose='test',visual='shot',required_input_ids=[])
    p={'settings':{'duration_seconds':15,'audio_mode':'mixed'},'scenes':[
        scene('a','我有一些想法需要真正执行并保存下来',3),
        scene('b','一些简短的话',6),
        scene('c','今天继续',6)]}
    revised=reserve_narration_slots(p)
    assert revised['scenes'][0]['duration_seconds']>3
    assert sum(s['duration_seconds'] for s in revised['scenes'])==15
    assert reserve_narration_slots(revised)==revised
    assert p['scenes'][0]['duration_seconds']==3


def test_budget_fails_before_paid_voice_call_when_impossible():
    p={'settings':{'duration_seconds':5,'audio_mode':'voice'},'scenes':[{'id':'first','duration_seconds':5,'narration':'真实配音时间不可以随便缩短'*5}]}
    with pytest.raises(ModelTaskError) as exc:reserve_narration_slots(p)
    assert exc.value.code=='plan_voice_budget_unavailable'


def test_budget_does_not_touch_silent_creative_plan():
    p={'settings':{'duration_seconds':4,'audio_mode':'silent'},'scenes':[{'duration_seconds':4,'narration':'非常多的话'*50}]}
    assert reserve_narration_slots(p)==p
