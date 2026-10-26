"""Conservative pre-freeze voice budget, not a substitute for actual TTS timing."""
from __future__ import annotations
from math import ceil
from .model_tasks import ModelTaskError


def reserve_narration_slots(plan: dict) -> dict:
    """Allocate model-authored scene slack before Creator confirms the plan.

    Reserve CJK at 3.8 chars/s, ASCII alphanumerics at 6 chars/s,
    plus 0.35s per spoken scene and explicit pauses, rounded to 30fps.
    No text, scene ordering, total film duration, or voice identity changes.
    Cannot silently modify an explicitly creator-frozen plan; call only when
    registering a newly generated draft.
    """
    settings=plan['settings']
    if settings['audio_mode'] not in {'voice','mixed'}:
        return plan
    # A natural-duration estimate is not a contract to fit or pad speech.
    if (plan.get('narration_policy') or {}).get('duration_mode') == 'voice_driven':
        return plan
    scenes=plan['scenes']
    if not scenes or any(s.get('duration_seconds') is None for s in scenes):
        return plan
    duration=float(settings['duration_seconds'])
    original=[float(s['duration_seconds']) for s in scenes]
    if abs(sum(original)-duration)>0.03:
        raise ModelTaskError('plan_scene_duration_invalid',f'模型分镜时长合计{sum(original):.3f}秒，与已确认总时长{duration:.3f}秒不符；请同步分镜时长，不能更改总片长')
    def reserved(text: str) -> float:
        if not text.strip():return 0.0
        # Chinese-first spoken narration; Latin words are less predictable.
        cjk=sum(1 for c in text if '\u3400' <= c <= '\u9fff')
        latin=sum(1 for c in text if c.isascii() and c.isalnum())
        return ceil((cjk/3.8 + latin/6.0 + 0.35)*30)/30
    floors=[reserved(s.get('narration',''))+sum(p['seconds'] for p in s.get('narration_pauses',[])) for s in scenes]
    if sum(floors)>duration+1e-6:
        pauses=sum(sum(p['seconds'] for p in s.get('narration_pauses',[])) for s in scenes)
        raise ModelTaskError('plan_voice_budget_unavailable',
            f'旁白预留估算合计{sum(floors):.3f}秒（正文及逐场余量{sum(floors)-pauses:.3f}秒，'
            f'显式停顿{pauses:.3f}秒），超过固定总片长{duration:.3f}秒约{sum(floors)-duration:.3f}秒。'
            '这是3.8汉字/秒、6个ASCII字母数字/秒、每个有声场景0.35秒及30fps归帧的预留估算，不是配音实测。'
            '请在已确认字数、固定首尾、自然停顿和语速内调整；无法同时满足时报告冲突，由Creator决定，不得自行删减到字数下限以下或改变片长/语速')
    result=original[:]
    for i in range(len(result)):
        shortage=max(0.0,floors[i]-result[i])
        if shortage<=0:continue
        donors=[j for j in range(len(result)) if j!=i and result[j]>floors[j]+1e-6]
        for j in sorted(donors,key=lambda j:result[j]-floors[j],reverse=True):
            take=min(shortage,result[j]-floors[j])
            result[j]-=take
            result[i]+=take
            shortage-=take
            if shortage<=1e-6:break
        if shortage>1e-6:raise ModelTaskError('plan_voice_budget_unavailable','场景旁白没有足够的镜头时间余量')
    # Preserve exact 30fps timebase and total; small round-off is restored
    # exclusively in a scene with room above its narration floor.
    ticks=[round(value*30) for value in result]
    desired=round(duration*30)
    discrepancy=desired-sum(ticks)
    if discrepancy:
        eligible=[i for i in range(len(ticks)) if ticks[i]/30 > floors[i]+abs(discrepancy)/30]
        if not eligible:raise ModelTaskError('plan_voice_budget_unavailable','场景时长无法按30fps精确排布')
        ticks[eligible[0]]+=discrepancy
    if any(t/30+1e-8<minimum for t,minimum in zip(ticks,floors)):
        raise ModelTaskError('plan_voice_budget_unavailable','旁白预算归帧后不足')
    revised=[dict(scene,duration_seconds=t/30) for scene,t in zip(scenes,ticks)]
    return {**plan,'scenes':revised}
