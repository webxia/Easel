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
