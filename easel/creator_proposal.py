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


def parse_video_plan(response: str) -> dict | None:
    """Extract the visible, complete discussion draft; never infer missing copy."""
    import hashlib
    import json
    from easel.integrations.hypit.secrets import SecretRedactor

    if not response or len(response) > 32_000 or SecretRedactor.contains_secret(response):
        return None
    parts = re.split(r"(?m)^## (创作表达|文案|分镜与节奏|声音设计|制作规格)\s*$", response)
    sections = {}
    settings = None
    for index in range(1, len(parts), 2):
        heading, body = parts[index], parts[index + 1].strip()
        if heading == "制作规格":
            if settings is not None:
                return None
            settings = body
        if heading in PLAN_SECTIONS:
            key = PLAN_SECTIONS[heading]
            if key in sections or not body or body in {"待确认", "待补充", "待生成"}:
                return None
            sections[key] = body
    if set(sections) != set(PLAN_SECTIONS.values()):
        return None
    # Reject mixed narration/instructions before approval. No post-confirmation
    # normalization can safely guess which words the Creator approved to speak.
    if re.search(r"(?m)^\s*(?:#{1,6}\s*|[-*]\s*)?(?:\*\*)?(?:逐字旁白|旁白说明|屏幕(?:文字|说明|文案)|画面说明|字幕说明|朗读说明)", sections["script"]):
        return None
    payload = {"schema": "easel-video-proposal@1", **sections,
               "specs": proposal_specs([{"role": "assistant", "content": settings or ""}])["specs"]}
    if settings:
        payload["specification_notes"] = settings
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {**payload, "sha256": hashlib.sha256(encoded.encode()).hexdigest()}


def video_proposal_preview(work: dict, turns: list[dict]) -> dict:
    workflow = work.get("chat_workflow") or {}
    if not workflow.get("video_plan_required"):
        return proposal_specs(turns)
    plan = workflow.get("video_plan") or {}
    specs = plan.get("specs") or {key: None for key in SPEC_LABELS}
    missing = [label for key, label in SPEC_LABELS.items() if specs.get(key) is None]
    if not plan:
        missing.append("完整视频方案（文案、分镜与声音设计）")
    elif workflow.get("proposal_status") not in {"READY_FOR_CONFIRMATION", "CONFIRMED"} and not missing:
        missing.append("当前方案尚未完成更新")
    return {"specs": specs, "missing": missing}
