import asyncio
import json
import pytest
from pydantic import BaseModel, ConfigDict, Field
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




@pytest.mark.parametrize('status,payload,expected', [
    (400, {'base_resp': {'status_code': 1008}}, 'provider_http_error'),
    (200, {'choices': []}, 'provider_response_invalid'),
    (200, {'choices': [{'finish_reason': 'length', 'message': {'content': '{}'}}]}, 'model_output_truncated'),
    (200, {'choices': [{'finish_reason': 'content_filter', 'message': {'content': '{}'}}]}, 'model_finish_unexpected'),
])
def test_model_http_failure_classification(status,payload,expected):
    settings={'EASEL_DIRECT_API_BASE_URL':'https://gateway.example/v1',
              'EASEL_DIRECT_API_MODEL':'MiniMax-M3.1-Flash-Preview','EASEL_DIRECT_API_KEY':'test-key'}
    transport=HTTPModelTransport(settings,transport=httpx.MockTransport(lambda _:httpx.Response(status,json=payload)))
    with pytest.raises(ModelTaskError) as error:
        asyncio.run(transport.complete([{'role':'user','content':'hello'}],[],{}))
    assert error.value.code == expected

def test_minimax_reasoning_content_retained_separately():
    settings={'EASEL_DIRECT_API_BASE_URL':'https://gateway.example/v1',
              'EASEL_DIRECT_API_MODEL':'MiniMax-M3.1-Flash-Preview','EASEL_DIRECT_API_KEY':'test-key'}
    def handler(req):
        assert json.loads(req.content)['model']=='MiniMax-M3.1-Flash-Preview'
        return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{
            'role':'assistant','reasoning_content':'thinking','content':'{"summary":"ok"}'}}]})
    message=asyncio.run(HTTPModelTransport(settings,transport=httpx.MockTransport(handler)).complete([{'role':'user','content':'hello'}],[],{}))
    assert json.loads(message['content']) == {'summary':'ok'}
    assert message['reasoning_content']=='thinking'


def test_long_minimax_planning_timeout_is_bounded_and_configured():
    settings={'EASEL_DIRECT_API_BASE_URL':'https://gateway.example/v1',
              'EASEL_DIRECT_API_MODEL':'MiniMax-M3.1-Flash-Preview','EASEL_DIRECT_API_KEY':'test-key'}
    def handler(req):
        assert req.extensions['timeout']['read']==900
        assert req.extensions['timeout']['connect']==20
        return httpx.Response(200,json={'choices':[{'message':{'content':'{"summary":"ok"}'}}]})
    transport=HTTPModelTransport(settings,transport=httpx.MockTransport(handler))
    assert transport.timeout_seconds==900
    assert asyncio.run(transport.complete([{'role':'user','content':'hello'}],[],{}))['content']=='{"summary":"ok"}'
    configured=HTTPModelTransport({**settings,'EASEL_PRODUCTION_MODEL_TIMEOUT_SECONDS':'1200'},
                                  transport=httpx.MockTransport(handler))
    assert configured.timeout_seconds==1200
    for invalid in ('119','1801','nan',''):
        with pytest.raises(ModelTaskError) as error:
            HTTPModelTransport({**settings,'EASEL_PRODUCTION_MODEL_TIMEOUT_SECONDS':invalid})
        assert error.value.code=='model_timeout_invalid'


def test_schema_specific_errors_guide_bounded_third_repair_without_relaxing_contract():
    responses=[
        {'content':'{"summary":"one","title":"extra"}'},
        {'content':'{"summary":"two","title":"extra"}'},
        {'content':'{"summary":"valid"}'},
    ]
    runner,transport,authorized=run(responses,max_format_repairs=2)
    result=asyncio.run(runner.run(context(),'material_intent',Answer))
    assert result.summary=='valid' and len(transport.calls)==3 and len(authorized)==3
    for call in transport.calls[1:]:
        feedback=call[-1]['content']
        assert 'title' in feedback and 'extra_forbidden' in feedback


def test_legacy_replay_preserves_first_repair_request_then_uses_specific_feedback():
    responses=[{'content':'{"summary":"a","title":"unexpected"}'},
               {'content':'{"summary":"b","title":"unexpected"}'},
               {'content':'{"summary":"valid"}'}]
    runner,transport,_=run(responses,max_format_repairs=2,legacy_first_repair=True)
    answer=asyncio.run(runner.run(context(),'material_intent',Answer))
    assert answer.summary=='valid'
    assert len(transport.calls)==3
    assert transport.calls[1][-1]['content']==('上次结果无效。严格按schema输出JSON；'
                                               '不要包含执行权限字段或不存在的媒体引用。')
    assert 'title (extra_forbidden)' in transport.calls[2][-1]['content']

def test_long_field_feedback_names_path_and_violation():
    class ShortQuery(BaseModel):
        model_config=ConfigDict(extra='forbid')
        music_query:str=Field(max_length=10)
    runner,transport,_=run([
        {'content':'{"music_query":"this query is too long"}'},
        {'content':'{"music_query":"room tone"}'}])
    result=asyncio.run(runner.run(context(),'material_intent',ShortQuery))
    assert result.music_query=='room tone'
    assert 'music_query' in transport.calls[1][-1]['content']
    assert 'string_too_long' in transport.calls[1][-1]['content']

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
    for key,value in [('EASEL_PRODUCTION_VIDEO_DIALECT','qwen-vl-video-url'),('EASEL_PRODUCTION_QUALITY_CHUNK_SECONDS','10'),('EASEL_PRODUCTION_MODEL_CAPABILITIES','image'),('EASEL_PRODUCTION_MODEL_TIMEOUT_SECONDS','1200')]:
        previous=settings.get(key);settings[key]=value
        assert model_configuration(tmp_path)[2]!=first
        if previous is None: settings.pop(key)
        else: settings[key]=previous


def test_oversized_tool_batch_corrected_without_partial_execution():
    invoked=[]
    async def inspect(args,ctx):
        invoked.append(args.asset_id)
        return {'observed':True}
    tool=ScopedTool('inspect_media','inspect',Args,inspect,('asset_id',))
    calls=[{'id':f'c{i}','function':{'name':'inspect_media','arguments':json.dumps({'asset_id':f'a{i}'})}} for i in range(9)]
    runner,transport,auth=run([{'tool_calls':calls},{'tool_calls':calls[:1]},{'content':'{"summary":"done"}'}])
    asyncio.run(runner.run(context(allowed_handles=frozenset(f'a{i}' for i in range(9))),'revise',Answer,tools=(tool,)))
    assert invoked==['a0'] and len(auth)==3
    rejected=[m for m in transport.calls[1] if m['role']=='tool']
    assert len(rejected)==9 and all(json.loads(m['content'])['executed'] is False for m in rejected)
    runner,_,auth=run([{'tool_calls':calls},{'tool_calls':calls}])
    with pytest.raises(ModelTaskError,match='拆批'):
        asyncio.run(runner.run(context(),'revise',Answer,tools=(tool,)))
    assert len(auth)==2 and invoked==['a0']
