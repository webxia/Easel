"""Read-only observation of already admitted candidates inside the edit loop."""
import asyncio
from pydantic import Field
from typing import Annotated
from .contracts import Contract
from .inspection import observe_media
from .tools import MediaToolResult, ScopedTool


class InspectCandidate(Contract):
    asset_id: str
    frame_times: list[Annotated[float, Field(ge=0, allow_inf_nan=False)]] = Field(min_length=1, max_length=8,
        description='源视频内要查看的实际秒数，最多8帧；不得超出源片长度')


def edit_observation_tools(paths, observed=None):
    # Paths come from validated artifact_file, never from the model.
    async def inspect(args, context):
        if args.asset_id not in paths:
            raise ValueError('Only current admitted visual candidates may be observed')
        blocks, required, evidence = await asyncio.to_thread(observe_media,
            paths[args.asset_id], frame_times=tuple(args.frame_times), include_audio=False)
        if observed is not None:
            observed.setdefault(args.asset_id, []).extend(evidence['frame_times'])
        label = {'type':'text','text':'复查素材 '+args.asset_id+'；仅抽样实际画面，未听声音、未观察完整动作。'}
        return MediaToolResult({'asset_id':args.asset_id, **evidence}, (label, *blocks), required)
    return (ScopedTool('inspect_media',
        '复查本次已准入候选的指定时间画面，用于核对实际动作与切点；只读，不搜索、不生成、不改工程。',
        InspectCandidate, inspect, ('asset_id',)),)


class VisualSelection(Contract):
    scene_id: str
    asset_id: str
    observed_times: list[Annotated[float, Field(ge=0, allow_inf_nan=False)]] = Field(default_factory=list, max_length=8)
    observation: str = Field(min_length=1, max_length=1200,
        description='只描述选用区间实际看见的动作/结果；不要复述方案当作画面事实。')
    uncertainty: str = Field(default='', max_length=600,
        description='抽样不能证明完整动作时如实说明；这不是新的审美否决条件。')


VISUAL_EVIDENCE_INSTRUCTION = (
    '对承担关键动作或结论的镜头，用visual_evidence关联scene_id、asset_id、实际observed_times和所见事实；'
    '只引用已收到且落在本次选用区间内的时间，不把片尾动作算到片头。'
    '分别描述看见的动作和是否看见完成结果；翻阅文件不等于收好文件。'
    '抽样不确定写uncertainty；空镜/气氛镜头不强制动作证据，不逐字追求非核心道具。'
    '明确缺少本片核心动作时使用已有缺素材分支，不编造已经完成。'
)


def check_visual_evidence(edit, observed):
    """Validate claimed references, not visual truth or artistic quality."""
    for evidence in edit.visual_evidence:
        selected = [s for s in edit.scenes if s.scene_id == evidence.scene_id and s.asset_id == evidence.asset_id]
        if not selected:
            raise ValueError('画面依据必须引用本次实际选用的镜头和素材')
        for at in evidence.observed_times:
            if not any(abs(at-t) <= .002 for t in observed.get(evidence.asset_id, []) if t is not None):
                raise ValueError('画面依据时间未被实际观察；可使用inspect_media或如实说明不确定')
            if not any(s.source_start-.002 <= at <= s.source_start+s.duration+.002 for s in selected):
                raise ValueError('观察时间不在本次选用片段内，不能用其他区间证明关键动作')
