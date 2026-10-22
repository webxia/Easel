"""Actual-video semantic review with explicit coverage and durable call ordering."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Literal

from .inspection import native_video_requirements, prepare_video_chunks
from .model_tasks import ModelTaskError
from .editors import EditError
from .contracts import Contract
from pydantic import Field


class VisualPreviewReview(Contract):
    repair_scope: Literal['visual', 'protected_timing_or_content'] = Field(default='visual',
        description='visual可仅重剪画面修复；确需改AudioClip、旁白内容或字幕时码才选protected_timing_or_content，不因正常留白扩大范围')
    affected_scene_ids: list[str] = Field(default_factory=list, max_length=32,
        description='有必须修复问题的实际场景ID；未知则留空，不编造')
    suggestions: list[str] = Field(default_factory=list, max_length=16, description='非阻断的审美或表达建议；不能用于隐藏事实错误、明确要求冲突或已证实质量缺陷')
    verdict: str = Field(pattern='^(pass|fail|partial)$')
    observations: list[str] = Field(min_length=1, max_length=32)
    findings: list[str] = Field(max_length=32)
    limitations: list[str] = Field(max_length=16)


async def review_visual_preview(path, *, runner, context):
    """Actual stamped frames, explicitly narrower than full audiovisual QC."""
    from .inspection import observe_media
    blocks, required, evidence = await asyncio.to_thread(observe_media, path, include_audio=False, max_frames=24)
    answer = await runner.run(context,
        '独立复核实际导出的抽样画面，不是复述计划或素材元数据。逐项检查画面是否帮助理解旁白，'
        '主体、动作、物件的实际用途是否与解释相符，是否用表面关键词相近但含义不同的镜头冒充所需材料；'
        '检查字幕可读、构图、镜头联系和信息密度，长镜头需有实际动作或阅读价值。'
        '允许明确标注的示意与假设案例，不要求库存逐字重现非核心道具设想；不能把不相干画面当自由适配。'
        '以确认的visual意图为准：允许通用场景时，不因没有具体软件界面或品牌判失败；物件数量本身不证明其用途或质量。'
        '结合实际编辑时间依据核对讲述与画面，不能用草稿场景时长冒充实际旁白区间。'
        '静默和无字幕不自动构成缺陷，有动作、阅读或叙事用途的留白应保留。确有无用途长尾时说明依据；'
        '若仅重剪画面能解决，repair_scope=visual；若必须改受保护声音/字幕时码/文案才能解决，'
        'repair_scope=protected_timing_or_content，明确原因，并列affected_scene_ids；不要把问题派给权限不足的视觉修订。'
        'observations按实际时间描述看到了什么；findings只列必须修复且有画面依据的问题，并标时间/场景及违反的内容或明确要求；可选节奏、构图等审美优化放suggestions，不因建议返回fail。'
        '缺重要说明、误导性示意或关键动作不可见须明确指出，不因工程能导出就pass。'
        '本轮仅有离散画面，未听声音、未观察完整动作，limitations必须说明；'
        'verdict只表示本次视觉抽样，不是全片语义、电影感或Creator接受通过。',
        VisualPreviewReview, media=blocks, required=required | frozenset({'text'}), expression_role="review")
    status = 'fail' if answer.findings else answer.verdict
    return status, {'review': answer.model_dump(), 'evidence': evidence,
                    'scope': 'sampled_visual_only', 'audio_reviewed': False, 'full_av_reviewed': False}


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
                'findings 只列有证据的必须修复问题、受损要求及全片时间；可选审美优化放suggestions，不因建议返回fail；观察不足、采样漏掉关键动作或无法听到音轨时'
                '返回 partial 并说明 limitations。不得声称 Creator 已接受。',
                review_type, required=required, media=blocks, expression_role="review")
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
                'duration': evidence['duration'], 'coverage_complete': True}, ensure_ascii=False)},), expression_role="review")
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
