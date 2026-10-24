"""Narration identity and measured playback policy, never script rewriting."""
from __future__ import annotations

from copy import deepcopy
from math import ceil
import json
from types import SimpleNamespace
from .contracts import fingerprint
from .voice import sentence_segments
from .model_tasks import ModelTaskError


def _literal_narration_segments(plan: dict, protected: set[str] | None = None) -> list[dict]:
    protected = protected or set()
    scenes = [s for s in plan['scenes'] if not protected.intersection(s.get('required_input_ids', []))]
    if not (plan.get('narration_policy') or {}).get('continuous'):
        return [{**part, 'segment_id': scene['id'] + '-' + part['segment_id'],
                 'scene_id': scene['id'], 'scene_ids': [scene['id']]}
                for scene in scenes for part in sentence_segments(scene.get('narration', ''))]
    groups, text, ids = [], '', []
    for scene in scenes:
        value = scene.get('narration', '').strip()
        if not value:
            continue
        if len(value) > 9500:
            raise ModelTaskError('narration_too_long', '连续旁白超过服务单段限制，请由创作模型分成完整段落')
        if text and len(text) + len(value) + 1 > 3000:
            groups.append((text, ids)); text, ids = '', []
        text = text + '\n' + value if text else value
        ids = [*ids, scene['id']]
    if text:
        groups.append((text, ids))
    return [{'segment_id': 'narration-' + fingerprint([text, ids])[:24], 'text': text,
             'text_hash': fingerprint(text), 'scene_ids': ids, 'scene_id': ids[0]}
            for text, ids in groups]


def narration_segments(plan, protected=None):
    segments=_literal_narration_segments(plan,protected)
    scenes={s['id']:s for s in plan['scenes']}
    if not any(s.get('narration_pauses') for s in scenes.values()):return segments
    if any(s.get('narration_pauses') for s in scenes.values()) and not (plan.get('narration_policy') or {}).get('continuous'):
        raise ModelTaskError('voice_prosody_requires_continuous','停顿控制需要连续口播，不能拆句后丢失控制位置')
    for segment in segments:
        pauses=[];cursor=0
        for sid in segment['scene_ids']:
            scene=scenes[sid];literal=scene.get('narration','').strip()
            if not literal:continue
            at=segment['text'].find(literal,cursor)
            if at<0:raise ModelTaskError('voice_prosody_invalid','口播位置无法映射')
            pauses.extend({'after':at+p['after'],'seconds':p['seconds']} for p in scene.get('narration_pauses',[]))
            cursor=at+len(literal)
        if pauses:segment['pauses']=pauses
    return segments


def measured_execution_plan(plan: dict, records: list[dict]) -> tuple[dict, dict | None]:
    """The opt-in runtime follows measured speech; the frozen draft stays intact."""
    policy = plan.get('narration_policy') or {}
    if policy.get('duration_mode') == 'fixed' and policy.get('continuous'):
        return plan, fixed_speech_timing(plan, records)
    if policy.get('duration_mode') != 'voice_driven':
        return plan, None
    meta = [json.loads(r['metadata_json']) for r in records]
    if any(m.get('original_audio') or any(u.get('role') == 'sfx' and u.get('timing_basis', 'absolute') != 'scene'
           for u in m.get('material_uses', [])) for m in meta):
        raise ModelTaskError('timed_audio_requires_fixed_duration', '有冻结时间音效的作品须明确时长，不能挤压原声或事件')
    voice = {m['segment_id']: m for m in meta if m.get('role') == 'voice'}
    segments = narration_segments(plan)
    if not segments or any(s['segment_id'] not in voice for s in segments):
        raise ModelTaskError('narration_timing_missing', '缺少完整旁白实测时间，不能猜测成片长度')
    cursor, schedule = .2, []
    for segment in segments:
        m = voice[segment['segment_id']]
        schedule.append({'segment_id': segment['segment_id'], 'at': cursor,
                         'duration': m['duration'], 'scene_ids': segment['scene_ids']})
        cursor += m['duration'] + .25
    duration = ceil((cursor - .25 + .8) * 30) / 30
    if duration > 900:
        raise ModelTaskError('narration_timing_exceeds_limit', '真实连续旁白超过本次视频时长范围')
    result = deepcopy(plan)
    result['settings']['duration_seconds'] = duration
    for scene in result['scenes']:
        scene['duration_seconds'] = None
    return result, {'mode': 'voice_driven', 'draft_duration': plan['settings']['duration_seconds'],
                    'duration': duration, 'voice_schedule': schedule,
                    'basis': 'actual complete voice assets; frozen draft and wording preserved'}


def check_voice_schedule(audio, records: list[dict], timing: dict | None) -> None:
    if not timing or timing.get('mode') == 'fixed':
        return
    by_segment = {json.loads(r['metadata_json']).get('segment_id'): r['id'] for r in records}
    for slot in timing['voice_schedule']:
        clips = [a for a in audio if a.asset_id == by_segment.get(slot['segment_id']) and a.role == 'voice']
        if len(clips) != 1 or abs(clips[0].at - slot['at']) > .05:
            raise ValueError('旁白必须遵守实测音轨的位置，不能为了凑片长插入多秒静默')
        clip = clips[0]
        if clip.source_start != 0 or abs(clip.duration - slot['duration']) > .05 or clip.gain <= 0:
            raise ValueError('连续旁白必须完整保留，不能截短、错用原片段或静音')
    expected = {by_segment.get(slot['segment_id']) for slot in timing['voice_schedule']}
    if any(a.role == 'voice' and a.asset_id not in expected for a in audio):
        raise ValueError('不能添加未确认的旁白音轨')


def aligned_captions(audio, records: list[dict]) -> list[dict] | None:
    """Literal complete captions: local acoustic estimates or provider anchors."""
    records = {r['id']: json.loads(r['metadata_json']) for r in records}
    captions = []
    for clip in sorted((a for a in audio if a.role == 'voice'), key=lambda a: a.at):
        metadata = records.get(clip.asset_id, {})
        timing = metadata.get('timing', {})
        local = timing.get('local_alignment', {})
        alignment = local if local.get('status') == 'received' else timing.get('provider_alignment', {})
        segments = alignment.get('segments', [])
        if alignment.get('status') != 'received' or not segments:
            return None
        normalize = lambda text: ''.join(text.split())
        if normalize(''.join(s['text'] for s in segments)) != normalize(metadata.get('narration_text', '')):
            return None
        for segment in segments:
            if segment['end'] > clip.duration + .1:
                return None
            captions.append({'text': segment['text'], 'start': clip.at + segment['start'],
                             'end': min(clip.at + clip.duration, clip.at + segment['end'])})
    return captions or None


def fixed_speech_timing(plan: dict, records: list[dict]) -> dict | None:
    """Measured anchors for editing, NOT a new silence or placement gate."""
    by_segment = {json.loads(r['metadata_json']).get('segment_id'): r for r in records}
    segments = narration_segments(plan)
    if not segments or any(s['segment_id'] not in by_segment for s in segments):
        return None
    total = sum(json.loads(by_segment[s['segment_id']]['metadata_json'])['duration'] for s in segments)
    duration = plan['settings']['duration_seconds']
    # Suggested placement only; fixed films may intentionally contain quiet scenes.
    gap = min(.25, max(0, duration-total) / (len(segments)+1))
    cursor = min(.2, gap)
    schedule, clips = [], []
    for segment in segments:
        record = by_segment[segment['segment_id']]
        seconds = json.loads(record['metadata_json'])['duration']
        schedule.append({'segment_id': segment['segment_id'], 'at': cursor,
                         'duration': seconds, 'scene_ids': segment['scene_ids']})
        clips.append(SimpleNamespace(asset_id=record['id'], role='voice', at=cursor, duration=seconds))
        cursor += seconds + gap
    captions = aligned_captions(clips, records)
    anchors = []
    if captions:
        normalize = lambda text: ''.join(text.split())
        spoken = ''.join(normalize(c['text']) for c in captions)
        expected = ''.join(normalize(s.get('narration', '')) for s in plan['scenes'])
        # Only whole aligned phrases within the exact scene text are anchors.
        # A phrase crossing a scene boundary cannot supply an invented cut time.
        if spoken == expected:
            offset = 0
            ranges = []
            for caption in captions:
                end = offset + len(normalize(caption['text']))
                ranges.append((offset, end, caption)); offset = end
            offset = 0
            for scene in plan['scenes']:
                end = offset + len(normalize(scene.get('narration', '')))
                parts = [c for a, b, c in ranges if offset <= a < b <= end]
                if parts:
                    anchors.append({'scene_id': scene['id'], 'start': parts[0]['start'],
                                    'end': parts[-1]['end'], 'basis': 'literal aligned phrases'})
                offset = end
    return {'mode': 'fixed', 'placement': 'advisory', 'duration': duration,
            'voice_schedule': schedule, 'aligned_captions': captions, 'scene_anchors': anchors,
            'unvoiced_seconds': max(0, duration-total),
            'basis': 'measured complete speech; keep confirmed duration; quiet visuals need narrative purpose'}


def project_timing_evidence(project, caption_roles=None) -> dict:
    """Existing project facts for visual review; does not claim to hear audio."""
    voice = [{'start': a.at, 'end': a.at+a.duration} for a in project.audio if a.role == 'voice']
    captions = [{'text': c.text, 'start': c.start, 'end': c.end,
                 'role': (caption_roles or {}).get(c.caption_id, 'unknown')}
                for c in project.captions]
    cursor, scenes = 0, []
    for scene in project.scenes:
        scenes.append({'scene_id': scene.scene_id, 'start': cursor,
                       'end': cursor+scene.duration, 'asset_id': scene.asset_id,
                       'source_start': scene.source_start})
        cursor += scene.duration-scene.transition_seconds
    return {'duration': project.duration, 'voice_intervals': voice, 'captions': captions,
            'scenes': scenes, 'unvoiced_tail_seconds': max(0, project.duration-max(
                (v['end'] for v in voice), default=project.duration)),
            'basis': 'edit timeline only; silence is not automatically a defect; audio not reviewed'}


ENDING_INSTRUCTION = (
    '收尾按真实完整旁白结束点设计：voice_driven沿用实测定长，fixed保留确认片长；'
    '不能把剩余时长默认变成无声空镜，也不能挪出同样长的空白片头。'
    '固定片长的无口播段须有明确的画面动作/阅读或可听音乐收束，说明用途；'
    'BGM增益是线性倍率，不能把0.1等固定数值当作合适音量。结合实测源mean/max dB、'
    '旁白与音乐的相对响度选择增益，增益造成的电平变化为20*log10(gain)。'
    '源音乐本就轻时再次大幅压低会近乎无声；留出混音峰值余量。'
    '淡出应服务结尾，在收尾最后短段完成，不把整段无口播时间都淡成听不见。'
    '这些是生成/剪辑依据，不是听审结果或新的通过门槛。'
)


def closing_mix_evidence(project, measurements):
    """Deterministic gain arithmetic for the editor, never a loudness verdict."""
    from math import isfinite, log10
    clips = []
    for clip in project.audio:
        measure = measurements.get(clip.asset_id, {})
        item = {'clip_id': clip.clip_id, 'role': clip.role, 'gain': clip.gain,
                'at': clip.at, 'end': clip.at + clip.duration,
                'fade_out_start': clip.at + clip.duration - clip.fade_out,
                'measurement': measure}
        for key in ('mean_volume_db', 'max_volume_db'):
            try:
                value = float(measure[key])
            except (KeyError, TypeError, ValueError):
                continue
            if isfinite(value) and clip.gain > 0:
                item['estimated_pre_fade_' + key] = round(value + 20 * log10(clip.gain), 2)
        clips.append(item)
    return {'timeline': project_timing_evidence(project), 'clips': clips,
            'basis': 'sampled source level plus clip gain; excludes fades and summation; not listening'}


def trim_confirmed_ending(project, duration):
    """Compile an explicitly confirmed shorter ending; never infer permission."""
    from math import isfinite
    from .editors import EditProject, EditError
    if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not isfinite(duration):
        raise EditError('收尾时长必须是有限秒数')
    if not 1 <= duration < project.duration or abs(duration*project.fps-round(duration*project.fps)) > 1e-5:
        raise EditError('收尾须短于原片且落在完整帧上')
    if any(c.end > duration for c in project.captions) or any(
            a.at+a.duration > duration for a in project.audio if a.role != 'music'):
        raise EditError('收尾不能截掉完整配音、音效或字幕')
    scenes = []
    for scene, start in zip(project.scenes, project.scene_starts()):
        if start >= duration:
            if scene.source_audio:
                raise EditError('不能移除原声镜头')
            continue
        seconds = min(scene.duration, duration-start)
        if seconds < scene.duration and scene.source_audio:
            raise EditError('不能截短原声镜头')
        scenes.append(scene.model_copy(update={'duration': seconds,
            'fade_out': min(scene.fade_out, max(0, seconds-scene.fade_in))}))
    audio = []
    for clip in project.audio:
        if clip.at >= duration:
            continue
        seconds = min(clip.duration, duration-clip.at)
        audio.append(clip.model_copy(update={'duration': seconds,
            'fade_out': min(clip.fade_out, max(0, seconds-clip.fade_in))}))
    return EditProject.model_validate({**project.model_dump(), 'revision': project.revision+1,
        'duration': duration, 'scenes': scenes, 'audio': audio})
