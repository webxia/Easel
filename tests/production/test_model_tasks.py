import asyncio
import json
import pytest
from pydantic import BaseModel, ConfigDict
from easel.production.context import TaskContext
from easel.production.model_tasks import ModelTaskRunner,ModelTaskError,HTTPModelTransport
from easel.production.tools import ScopedTool
import httpx


class Answer(BaseModel):
    model_config=ConfigDict(extra='forbid')
    summary:str


class Transport:
    capabilities=frozenset({'text','structured','tools'})
    def __init__(self,responses):self.responses=iter(responses);self.calls=[]
    async def complete(self,messages,tools,schema):
        self.calls.append(json.loads(json.dumps(messages)))
        return next(self.responses)


def run(responses,**kwargs):
    transport=Transport(responses);authorized=[]
    async def authorize(ctx):authorized.append(ctx.task_id)
    runner=ModelTaskRunner(transport,authorize,**kwargs)
    return runner,transport,authorized


def context(**extra):return TaskContext('w','r','t',brief='AI科普',**extra)


def test_explicit_context_without_workspace_or_other_profile():
    runner,transport,calls=run([{'content':'{"summary":"创作方案"}'}])
    result=asyncio.run(runner.run(context(),'plan',Answer))
    assert result.summary=='创作方案' and calls==['t']
    payload=transport.calls[0][1]['content'][0]['text']
    assert json.loads(payload)['profile']=={}
    assert 'AGENTS.md' not in payload and 'TURN_REMINDER' not in payload
    assert 'work_id' not in payload and 'owner_epoch' not in payload
    with pytest.raises(ValueError):context(profile={'memory':'他人经历'}).creative_data()


@pytest.mark.parametrize('bad',[{}, {'owner_epoch':5,'summary':'x'},{'summary':'x','artifact_id':'foreign'}])
def test_invalid_and_forged_authority_rejected(bad):
    runner,_,calls=run([{'content':json.dumps(bad)}],max_format_repairs=0)
    with pytest.raises(ModelTaskError,match='有效创作结果'):
        asyncio.run(runner.run(context(),'plan',Answer))
    assert len(calls)==1


def test_permission_checked_before_every_call_and_no_unbounded_repair():
    runner,_,calls=run([{'content':''},{'content':'broken'}])
    with pytest.raises(ModelTaskError):asyncio.run(runner.run(context(),'plan',Answer))
    assert len(calls)==2
    async def denied(ctx):raise ModelTaskError('permission_missing','缺少授权')
    runner.authorize=denied
    with pytest.raises(ModelTaskError,match='缺少授权'):
        asyncio.run(runner.run(context(),'plan',Answer))


def test_required_modalities_fail_without_call():
    runner,transport,_=run([])
    with pytest.raises(ModelTaskError,match='媒体'):
        asyncio.run(runner.run(context(),'inspect',Answer,required=frozenset({'video','audio'})))
    assert not transport.calls


class Args(BaseModel):
    asset_id:str


def test_actual_scoped_tool_dispatch_and_repeat_stops():
    invoked=[]
    async def inspect(args,ctx):invoked.append(args.asset_id);return {'evidence':'合法视频证据'}
    tool=ScopedTool('inspect_media','查看媒体',Args,inspect,('asset_id',))
    call={'id':'c1','function':{'name':'inspect_media','arguments':'{"asset_id":"a1"}'}}
    runner,_,_=run([{'tool_calls':[call]},{'content':'{"summary":"完成选择"}'}])
    assert asyncio.run(runner.run(context(allowed_handles=frozenset({'a1'})),'select',Answer,tools=(tool,))).summary=='完成选择'
    assert invoked==['a1']
    runner,_,_=run([{'tool_calls':[call]},{'tool_calls':[call]}])
    with pytest.raises(ModelTaskError):asyncio.run(runner.run(context(allowed_handles=frozenset({'a1'})),'select',Answer,tools=(tool,)))
    runner,_,_=run([{'tool_calls':[call]}])
    with pytest.raises(ModelTaskError):asyncio.run(runner.run(context(),'select',Answer,tools=(tool,)))


def test_http_adapter_uses_existing_config_no_redirect_or_tool_execution():
    requests=[]
    def handler(request):
        requests.append(request)
        return httpx.Response(200,json={'choices':[{'message':{'content':'{"summary":"ok"}'}}]})
    transport=HTTPModelTransport({'EASEL_DIRECT_API_BASE_URL':'https://gateway.example/v1','EASEL_DIRECT_API_MODEL':'configured-model','EASEL_DIRECT_API_KEY':'test-key'},transport=httpx.MockTransport(handler))
    async def authorize(ctx):pass
    assert asyncio.run(ModelTaskRunner(transport,authorize).run(context(),'plan',Answer)).summary=='ok'
    assert len(requests)==1
    assert requests[0].url.path=='/v1/chat/completions'
    assert json.loads(requests[0].content)['stream'] is False


def test_native_video_http_dialect_and_configuration_identity(tmp_path,monkeypatch):
    from easel.production.configuration import model_configuration
    settings={'EASEL_DIRECT_API_BASE_URL':'https://example.invalid/v1','EASEL_DIRECT_API_MODEL':'configured-omni',
              'EASEL_PRODUCTION_VIDEO_DIALECT':'qwen-omni-video-url','EASEL_PRODUCTION_MODEL_CAPABILITIES':'image,video,audio',
              'EASEL_PRODUCTION_QUALITY_CHUNK_SECONDS':'20'}
    requests=[]
    def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200,json={'choices':[{'message':{'content':'{"summary":"ok"}'}}]})
    transport=HTTPModelTransport(settings,capabilities=frozenset({'structured','video','audio'}),transport=httpx.MockTransport(respond))
    asyncio.run(transport.complete([{'role':'user','content':'review'}],[],{}))
    assert requests[0]['modalities']==['text'] and requests[0]['reasoning_effort']=='none'
    assert transport.video_dialect=='qwen-omni-video-url' and transport.quality_chunk_seconds=='20'
    monkeypatch.setattr('easel.production.configuration.read_settings',lambda _:dict(settings))
    first=model_configuration(tmp_path)[2]
    for key,value in [('EASEL_PRODUCTION_VIDEO_DIALECT','qwen-vl-video-url'),('EASEL_PRODUCTION_QUALITY_CHUNK_SECONDS','10'),('EASEL_PRODUCTION_MODEL_CAPABILITIES','image')]:
        previous=settings[key];settings[key]=value
        assert model_configuration(tmp_path)[2]!=first
        settings[key]=previous
