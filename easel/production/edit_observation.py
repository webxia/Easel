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


def edit_observation_tools(paths):
    # Paths come from validated artifact_file, never from the model.
    async def inspect(args, context):
        if args.asset_id not in paths:
            raise ValueError('Only current admitted visual candidates may be observed')
        blocks, required, evidence = await asyncio.to_thread(observe_media,
            paths[args.asset_id], frame_times=tuple(args.frame_times), include_audio=False)
        label = {'type':'text','text':'复查素材 '+args.asset_id+'；仅抽样实际画面，未听声音、未观察完整动作。'}
        return MediaToolResult({'asset_id':args.asset_id, **evidence}, (label, *blocks), required)
    return (ScopedTool('inspect_media',
        '复查本次已准入候选的指定时间画面，用于核对实际动作与切点；只读，不搜索、不生成、不改工程。',
        InspectCandidate, inspect, ('asset_id',)),)
