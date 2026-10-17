"""Actual-video semantic review with explicit coverage and durable call ordering."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
from pathlib import Path

from .inspection import native_video_requirements, prepare_video_chunks
from .model_tasks import ModelTaskError
from .editors import EditError


@dataclass(frozen=True)
class VideoReviewResult:
    verdict: str
    findings: list[str]
    limitations: list[str]
    evidence: dict
    review: dict


async def review_full_video(path: Path, *, cache_root: Path, info: dict, transport,
                           runner, context, review_type, on_segment=None) -> VideoReviewResult:
    dialect, seconds, required = native_video_requirements(transport, audio=info['audio'])
    try:
        chunks, evidence = await asyncio.to_thread(prepare_video_chunks, path, cache_root=cache_root, seconds=seconds)
    except (EditError, OSError, ValueError) as exc:
        raise ModelTaskError('media_inspection_failed', '审片媒体不完整或已变化，原成片已保留') from exc
    evidence = {**evidence, 'dialect': dialect, 'required_capabilities': sorted(required),
                'reviewed_chunks': [], 'global_review_complete': False}
    reviews = []
    try:
        # One runner/RecordedModelTransport for every chunk and the final summary.
        # A fresh runner here would reuse operation ordinal 1 with a different request.
        for index, chunk in enumerate(chunks):
            blocks = await asyncio.to_thread(chunk.blocks)
            answer = await runner.run(context,
                f'分段审片 {index+1}/{len(chunks)}：本次仅审阅全片时间 {chunk.start:.6f}–{chunk.end:.6f} 秒的实际视频文件。'
                '视频音轨随文件提供（无声模式除外）。核对这段与方案对应的事实、观点、必用内容、导演风格、'
                '叙事、声音、字幕及音画同步。描述本段真实可见/可听内容及开头结尾以供跨段综合；'
                '不得用文件名、计划或字幕文本代替观看收听。不得将本段结果称为全片已通过。'
                'findings 只列必须修复的问题并标全片时间；观察不足、采样漏掉关键动作或无法听到音轨时'
                '返回 partial 并说明 limitations。不得声称 Creator 已接受。',
                review_type, required=required, media=blocks)
            data = {'start': chunk.start, 'end': chunk.end, 'review': answer.model_dump()}
            reviews.append(data)
            evidence['reviewed_chunks'].append({'start': chunk.start, 'end': chunk.end,
                                                'sha256': chunk.sha256, 'verdict': answer.verdict})
            if on_segment:
                on_segment(index+1, len(chunks), data)
        if len(reviews) != len(chunks) or not evidence['coverage_complete']:
            raise ModelTaskError('inspection_incomplete', '实际视频片段尚未全部审阅')
        # The full plan + every bounded review is present here. This is synthesis
        # of actual-media reviews, not another claim to have watched unseen video.
        summary = await runner.run(context,
            '全片综合审片：以下是已逐段提交实际视频及其声音的审阅结果，涵盖完整时间轴。'
            '综合核对完整方案、必用内容、事实观点、故事顺序、跨段衔接、声音字幕及稳定导演风格；'
            '本次根据分段观察综合，不能声称重新观看了未在本次附上的媒体。'
            '局部通过不代表全局通过；任一段缺陷或观察局限不得在汇总中抹去。'
            '不能确认完整一致性时返回 partial；findings 只列需要修复的问题并注明时间。',
            review_type, required=frozenset({'text','structured'}),
            media=({'type': 'text', 'text': json.dumps({'actual_video_segment_reviews': reviews,
                'duration': evidence['duration'], 'coverage_complete': True}, ensure_ascii=False)},))
        evidence['global_review_complete'] = True
    except ModelTaskError as exc:
        raise ModelTaskError(exc.code, exc.user_message,
                             diagnostic={**exc.diagnostic, 'evidence': evidence, 'reviews': reviews}) from exc
    all_reviews = [entry['review'] for entry in reviews] + [summary.model_dump()]
    findings = list(dict.fromkeys(item for review in all_reviews for item in review['findings']))
    limitations = list(dict.fromkeys(item for review in all_reviews for item in review['limitations']))
    if any(review['verdict']=='fail' for review in all_reviews) or findings:
        verdict = 'fail'
    elif any(review['verdict']=='partial' for review in all_reviews) or limitations:
        verdict = 'partial'
    else:
        verdict = 'pass'
    return VideoReviewResult(verdict, findings, limitations, evidence,
                             {'segments': reviews, 'global': summary.model_dump()})
