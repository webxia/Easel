"""Modality ownership of existing Need controls, shared by producer/consumers."""
from easel.materials.domain import MediaType, VoiceNeedSpec
from easel.materials.application.voice_delivery import validate_voice_delivery

VOICE_ALIASES = frozenset({'voice_pace_ratio', 'voice_pitch_semitones', 'voice_tone'})

PLANNING_CONSTRAINT_CONTRACT = (
    "\n〔Need 参数模态边界〕\n"
    "每条 constraints 只属于该 Need，不能把全片声音参数复制给所有 Need。"
    "只有 media_type=audio 且 modality_spec.kind=voice 的 Need 可含 voice_delivery 对象；"
    "对象仅含 pace_ratio（0.5～2）、pitch_semitones（-12～12整数）、"
    "tone（neutral/happy/sad/angry/afraid/disgusted/surprised或null），未指定项继承冻结Mode。"
    "image/video/bgm/sfx 禁止 voice_delivery。不要摊平或改名为 voice_pace_ratio、"
    "voice_pitch_semitones、voice_tone；这三个别名不是执行合同，任何Need均禁止。"
    "preferred_visual_details 仅用于image/video的非空软偏好，不用于Voice/BGM/SFX。"
    "检索过滤条件为字符串、数字或布尔值；现有结构化例外是合法Voice上的voice_delivery对象，"
    "以及search_query_variants_en对象（primary/alternate/relaxed三个不同的英文短查询，每项不超过100字符）。"
    "两个对象均非硬检索过滤，不要为通过标量检查拆散它们。其他未知结构化约束仍无效。"
    "按报错的具体Need与字段修正；保留其余有效字段、全部Need ID/类型/importance/必要表达，"
    "不删除或降低创作要求来通过校验。\n"
)


def validate_modality_constraints(needs):
    """Reject misplaced/renamed controls before deriving filters or defaults."""
    errors = []
    for need in needs:
        modality = getattr(need.modality_spec, 'kind', None) or need.media_type.value
        voice = need.media_type is MediaType.AUDIO and isinstance(need.modality_spec, VoiceNeedSpec)
        visual = need.media_type in {MediaType.IMAGE, MediaType.VIDEO}
        def error(key, reason):
            errors.append(f"Need {need.need_id!r} ({modality}) constraints.{key}: {reason}")
        for key in sorted(VOICE_ALIASES.intersection(need.constraints)):
            error(key, "非正式声音别名；声音参数只能使用 Voice Need 的 constraints.voice_delivery 对象，禁止摊平")
        if 'voice_delivery' in need.constraints:
            if not voice:
                error('voice_delivery', "仅属于 audio/voice Need，不能复制到视觉、BGM 或 SFX；不得改为标量绕过")
            else:
                try:
                    validate_voice_delivery(need.constraints['voice_delivery'])
                except ValueError as exc:
                    error('voice_delivery', str(exc))
        if 'preferred_visual_details' in need.constraints:
            value = need.constraints['preferred_visual_details']
            if not visual or not isinstance(value, str) or not value.strip():
                error('preferred_visual_details', "须为视觉 Need 的非空偏好说明")
    if errors:
        suffix = f"；另有 {len(errors)-12} 项" if len(errors) > 12 else ''
        raise ValueError('；'.join(errors[:12]) + suffix)
