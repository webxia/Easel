"""Bounded recutting for native QC feedback, with frozen content/audio guards."""
import re
from .editors import EditError


def approved_overlay_texts(plan):
    return sorted({text for scene in plan.get('scenes', [])
                   for text in re.findall(r'[“「]([^”」\n]{1,100})[”」]', scene.get('visual', ''))})


def assert_visual_repair(base, revised, *, overlay_texts, protected_caption_style_ids=frozenset(), allow_retiming=False):
    if base.audio != revised.audio:
        raise EditError('局部画面修订改变了独立音轨；必须保留原配音、BGM和音效的位置、时长与增益')
    def source_audio_scenes(project):
        return [(s.scene_id, (s.asset_id,s.source_start,s.duration,s.source_gain,round(at,6)))
                for s,at in zip(project.scenes,project.scene_starts()) if s.source_audio]
    before,after=source_audio_scenes(base),source_audio_scenes(revised)
    if [v for _,v in before] != [v for _,v in after]:
        old=dict(before);new=dict(after)
        changed=[key for key in dict.fromkeys([*old,*new]) if old.get(key)!=new.get(key)]
        raise EditError('原声发生变化：'+','.join(changed)+'；须保留原素材、取源起点、时长、音量和时间线位置；裁切、适配和运动可单独修改')
    for field in ('work_id','plan_revision','width','height','duration','audio_mode','fps'):
        if getattr(base, field) != getattr(revised, field):
            raise EditError('视觉修复不能改变作品身份、规格或总时长')
    if abs(sum(s.duration-s.transition_seconds for s in revised.scenes) -
           sum(s.duration-s.transition_seconds for s in base.scenes)) > .04:
        raise EditError('视觉修复不能改变实际镜头净总长')
    old={s.scene_id:s for s in base.scenes}
    groups={s.scene_id:[] for s in base.scenes}
    order=[]
    for scene in revised.scenes:
        parent=scene.scene_id if scene.scene_id in old else re.sub(r'-cut[1-9][0-9]*$', '', scene.scene_id)
        if parent not in old:
            raise EditError('新镜头 '+scene.scene_id+' 必须属于已登记镜头；可用原ID或完整原ID-cut1等。原ID列表：'+','.join(old))
        groups[parent].append(scene)
        if not order or order[-1]!=parent:order.append(parent)
    if order != list(old):
        raise EditError('视觉修复不能删掉或重排已确认场景')
    for key, scenes in groups.items():
        duration=sum(s.duration-s.transition_seconds for s in scenes)
        if not allow_retiming and abs(duration-(old[key].duration-old[key].transition_seconds))>.04:
            raise EditError('原场景可拆镜，但净时长与声音位置必须保留')
    captions={c.caption_id:c for c in revised.captions}
    for before in base.captions:
        after=captions.get(before.caption_id)
        if not after or (after.text,after.start,after.end)!=(before.text,before.start,before.end):
            raise EditError('原旁白字幕的字句与时间不得修改')
        if before.caption_id in protected_caption_style_ids and before!=after:
            raise EditError('自动视觉修复不能改变已固定的旁白字幕样式、透明背景或位置')
    original_ids={c.caption_id for c in base.captions}
    if any(c.text not in overlay_texts for c in revised.captions if c.caption_id not in original_ids):
        raise EditError('补充解释字只能来自已确认方案的明确提示语')
