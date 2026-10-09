"""Literal proposal specifications shared by preview and explicit confirmation.

No model inference and no defaults: examples, questions and ambiguous values
remain empty. Preparation must freeze exactly the values shown on the card.
"""
from __future__ import annotations

import re

SPEC_LABELS = {"duration_seconds": "总时长", "aspect_ratio": "明确画幅比例", "audio_mode": "音轨方式", "language": "语言"}


def proposal_specs(turns: list[dict]) -> dict:
    values = {key: None for key in SPEC_LABELS}
    offered_ratios: dict[str, set[str]] = {}
    # The explicit action accepts the displayed discussion; later literal
    # settings supersede earlier ones. Unlabelled assistant examples are not settings.
    for turn in turns:
        content = turn.get("content", "")
        if not isinstance(content, str):
            continue
        assistant = turn.get("role") != "user"
        for line in content.splitlines():
            labelled = {field for label, field in (("时长", "duration_seconds"), ("画幅", "aspect_ratio"), ("比例", "aspect_ratio"),
                                                   ("音轨", "audio_mode"), ("声音", "audio_mode"), ("语言", "language"))
                        if re.search(r"(?:^|[；;])\s*(?:[-*•]\s*)?(?:\*\*)?(?:总)?" + label + r"(?:\*\*)?\s*[：:]", line)}
            if "待确认" in line or "尚未确认" in line:
                for field in labelled:
                    values[field] = None
                continue
            if any(word in line for word in ("示例", "例如", "比如", "？", "?")):
                continue
            for field in labelled:
                values[field] = None
            # An orientation alone is not an exact ratio. Resolve only an
            # explicit user selection of a ratio-labelled option already offered.
            if assistant:
                for ratio, orientation in re.findall(r"(9[:：]16|16[:：]9|1[:：]1|4[:：]5|4[:：]3|3[:：]4)\s*[（(]\s*(竖屏|横屏|方屏)\s*[）)]", line):
                    offered_ratios.setdefault(orientation, set()).add(ratio.replace('：', ':'))
            else:
                selection = re.fullmatch(r"\s*(?:选|选择|用|使用|就用)?\s*(竖屏|横屏|方屏)[。！!]?\s*", line)
                if selection:
                    choices = offered_ratios.get(selection[1], set())
                    values['aspect_ratio'] = next(iter(choices)) if len(choices) == 1 else None
            durations = set(re.findall(r"(?<![\d.])(\d{1,3})\s*秒", line))
            if durations and (not assistant or 'duration_seconds' in labelled):
                values["duration_seconds"] = int(next(iter(durations))) if len(durations) == 1 and not re.search(r"上限|最多|不超过|至少|最少|以内|不(?:要|是|用|能).*秒", line) else None
            ratios = set(re.findall(r"(?<!\d)(9:16|16:9|1:1|4:5|4:3|3:4)(?!\d)", line.replace("：", ":")))
            if ratios and (not assistant or 'aspect_ratio' in labelled):
                values["aspect_ratio"] = next(iter(ratios)) if len(ratios) == 1 and not re.search(r"不(?:要|是|用).*\d[:：]\d", line) else None
            audio = set()
            for pattern, value in ((r"静音|无声|不要声音|silent", "silent"), (r"只(?:要|用|有)?旁白|纯旁白|音轨\s*[：:]\s*voice", "voice"),
                                   (r"只(?:要|用|有)?音乐|纯音乐|音轨\s*[：:]\s*music", "music"), (r"旁白\s*(?:与|和|及|搭配|配合|加上?|[+＋])\s*[^，。；!?？\n]{0,24}?(?:背景(?:音)?乐|音乐|BGM|配乐)|音轨\s*[：:]\s*mixed", "mixed")):
                if re.search(pattern, line):
                    audio.add(value)
            if audio and (not assistant or 'audio_mode' in labelled):
                values["audio_mode"] = next(iter(audio)) if len(audio) == 1 and not re.search(r"不(?:要|是|用|能).*静音|不静音|(?:不要|不用|不加|不配|没有).*(?:音乐|背景乐|配乐|BGM)", line) else None
            languages = set()
            for pattern, value in ((r"简体中文|zh-CN", "zh-CN"), (r"繁体中文|zh-TW", "zh-TW"), (r"英语|英文|语言\s*[：:]\s*en\b", "en")):
                if re.search(pattern, line):
                    languages.add(value)
            if languages and (not assistant or 'language' in labelled):
                values["language"] = next(iter(languages)) if len(languages) == 1 and not re.search(r"不(?:要|是|用|使用).*(?:英语|英文|简体|繁体)", line) else None
    if values["duration_seconds"] is not None and not 1 <= values["duration_seconds"] <= 900:
        values["duration_seconds"] = None
    return {"specs": values, "missing": [SPEC_LABELS[key] for key, value in values.items() if value is None]}


PLAN_SECTIONS = {"创作表达": "treatment", "文案": "script", "分镜与节奏": "scenes", "声音设计": "sound"}


def _mixed_script(script: str) -> bool:
    # Labels are structural instructions, not arbitrary words in a spoken line.
    labels = r"(?:逐字旁白|旁白说明|屏幕(?:文字|说明|文案)|画面说明|字幕说明|朗读说明|说明|制作备注|配音说明)"
    return bool(re.search(r"(?m)^[ \t]*(?:#{1,6}[ \t]+|[-*][ \t]+)?(?:\*\*)?" + labels
                         + r"(?:\*\*)?(?:[ \t]*[：:]|[ \t]*[（(]|[ \t]*$)", script))


def _plan_payload(plan: dict) -> dict:
    keys = ('schema', 'treatment', 'script', 'scenes', 'sound', 'specs', 'specification_notes',
            'sound_source', 'voice_profile')
    return {key: plan[key] for key in keys if key in plan}


def validate_video_plan(plan: dict, *, require_current: bool = True) -> bool:
    import hashlib
    import json
    from easel.integrations.hypit.secrets import SecretRedactor
    if not isinstance(plan, dict) or plan.get('schema') not in ({'easel-video-proposal@2', 'easel-video-proposal@3'} if require_current
                                                              else {'easel-video-proposal@1', 'easel-video-proposal@2', 'easel-video-proposal@3'}):
        return False
    if any(not isinstance(plan.get(k), str) or not plan[k].strip() for k in PLAN_SECTIONS.values()):
        return False
    if not isinstance(plan.get('specs'), dict) or set(plan['specs']) != set(SPEC_LABELS):
        return False
    if require_current and (_mixed_script(plan['script']) or '\x00' in plan['script']):
        return False
    if SecretRedactor.contains_secret(plan):
        return False
    if plan['schema'] == 'easel-video-proposal@3':
        from easel.integrations.voice_identity import validate_profile, render_sound
        try:
            validate_profile(plan.get('voice_profile'))
            if (plan['specs']['audio_mode'] not in {'voice', 'mixed'}
                    or plan['specs']['language'] != plan['voice_profile']['language']
                    or not isinstance(plan.get('sound_source'), str) or not plan['sound_source'].strip()
                    or re.findall(r'(?m)^预置旁白：[ \t]*([^\r\n]+)$', plan['sound_source']) != [plan['voice_profile']['handle']]
                    or plan['sound'] != render_sound(plan['sound_source'], plan['voice_profile'])):
                return False
        except ValueError:
            return False
    elif 'voice_profile' in plan or 'sound_source' in plan:
        return False
    encoded = json.dumps(_plan_payload(plan), ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return plan.get('sha256') == hashlib.sha256(encoded.encode()).hexdigest()


def parse_video_plan(response: str, *, voice_profile=None, bind_preset=False) -> dict | None:
    """Parse a new proposal with a literal script container, without guessing prose."""
    import hashlib
    import json
    from easel.integrations.hypit.secrets import SecretRedactor
    if not isinstance(response, str) or not response or len(response) > 32_000 or SecretRedactor.contains_secret(response):
        return None
    sections, heading, lines, fenced = {}, None, [], False
    for line in response.splitlines(keepends=True):
        literal = line.rstrip('\r\n')
        match = re.fullmatch(r'## (创作表达|文案|分镜与节奏|声音设计|制作规格)[ \t]*', literal)
        if match and not fenced:
            if heading is not None:
                if heading in sections: return None
                sections[heading] = ''.join(lines)
            heading, lines = match[1], []
            continue
        if literal.startswith('```'):
            fenced = not fenced
        if heading is not None: lines.append(line)
    if fenced or heading is None or heading in sections: return None
    sections[heading] = ''.join(lines)
    if not set(PLAN_SECTIONS) <= set(sections): return None
    container = re.fullmatch(r'[ \t\r\n]*```text(?:\r\n|\n)([\s\S]*?)(?:\r\n|\n)```[ \t]*[ \t\r\n]*', sections['文案'])
    if container is None: return None
    script = container[1]
    if not script.strip() or '\x00' in script or re.search(r'(?m)^```', script) or _mixed_script(script): return None
    payload = {'schema': 'easel-video-proposal@2', **{key: sections[name].strip() for name, key in PLAN_SECTIONS.items()}}
    payload['script'] = script
    if any(not payload[k] or payload[k] in {'待确认', '待补充', '待生成'} for k in PLAN_SECTIONS.values()): return None
    settings = sections.get('制作规格', '').strip()
    payload['specs'] = proposal_specs([{'role': 'assistant', 'content': settings}])['specs']
    if bind_preset and payload['specs']['audio_mode'] in {'voice', 'mixed'}:
        from easel.integrations.voice_identity import validate_profile, render_sound
        try:
            validate_profile(voice_profile)
        except ValueError:
            return None
        choices = re.findall(r'(?m)^预置旁白：[ \t]*([^\r\n]+)$', payload['sound'])
        if choices != [voice_profile['handle']] or payload['specs']['language'] != voice_profile['language']:
            return None
        payload.update(schema='easel-video-proposal@3', voice_profile=voice_profile,
                       sound_source=payload['sound'], sound=render_sound(payload['sound'], voice_profile))
    if settings: payload['specification_notes'] = settings
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return {**payload, 'sha256': hashlib.sha256(encoded.encode()).hexdigest()}


def video_proposal_preview(work: dict, turns: list[dict]) -> dict:
    workflow = work.get("chat_workflow") or {}
    if not workflow.get("video_plan_required"):
        return proposal_specs(turns)
    plan = workflow.get("video_plan") or {}
    specs = plan.get("specs") or {key: None for key in SPEC_LABELS}
    missing = [label for key, label in SPEC_LABELS.items() if specs.get(key) is None]
    if not plan:
        missing.append("完整视频方案（文案、分镜与声音设计）")
    elif plan.get('schema') not in {'easel-video-proposal@2', 'easel-video-proposal@3'} and workflow.get('proposal_status') != 'CONFIRMED':
        missing.append('旧方案需要正常修订正文格式后再确认')
    elif workflow.get("proposal_status") not in {"READY_FOR_CONFIRMATION", "CONFIRMED"} and not missing:
        missing.append(workflow.get("proposal_error") or "当前方案尚未完成更新")
    return {"specs": specs, "missing": missing}
