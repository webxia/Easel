"""Conservative pre-freeze voice budget, not a substitute for actual TTS timing."""
from __future__ import annotations
from math import ceil
from .model_tasks import ModelTaskError


def reserve_narration_slots(plan: dict) -> dict:
    """Allocate model-authored scene slack before Creator confirms the plan.

    Each CJK character gets a conservative 0.22s plus 0.3s per scene.
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
        raise ModelTaskError('plan_scene_duration_invalid','模型分镜时长合计与已确认总时长不符')
    def reserved(text: str) -> float:
        if not text.strip():return 0.0
        # Chinese-first spoken narration; Latin words are less predictable.
        cjk=sum(1 for c in text if '\u3400' <= c <= '\u9fff')
        latin=sum(1 for c in text if c.isascii() and c.isalnum())
        return ceil((cjk/3.8 + latin/6.0 + 0.35)*30)/30
    floors=[reserved(s.get('narration',''))+sum(p['seconds'] for p in s.get('narration_pauses',[])) for s in scenes]
    if sum(floors)>duration+1e-6:
        raise ModelTaskError('plan_voice_budget_unavailable','旁白估算时长超过总片长，请压缩旁白或由Creator调整片长')
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
