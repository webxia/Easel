import asyncio
import json
import subprocess
import pytest
from pydantic import BaseModel
from easel.production.context import TaskContext
from easel.production.model_tasks import ModelTaskRunner, ModelTaskError
from easel.production.edit_observation import edit_observation_tools
from easel.production.quality import VisualPreviewReview, review_visual_preview
from easel.production.visual_repair import assert_visual_repair
from easel.production.editors import EditProject, EditError

class Answer(BaseModel):
    summary: str


def test_editor_tool_returns_actual_selected_frames_and_enforces_scope(tmp_path):
    path=tmp_path/'candidate.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=64x64:rate=10:duration=2','-y',str(path)],check=True)
    tools=edit_observation_tools({'a':path})
    ctx=TaskContext('w','r','t',allowed_handles=frozenset({'a','other'}))
    class Transport:
        capabilities=frozenset({'text','structured','tools','image'})
        calls=0
        async def complete(self,messages,definitions,schema):
            self.calls+=1
            if self.calls==1:
                return {'tool_calls':[{'id':'c','function':{'name':'inspect_media','arguments':json.dumps({'asset_id':'a','frame_times':[.2,1.4]})}}]}
            evidence=json.loads(messages[-2]['content'])
            assert evidence['frame_times']==[.2,1.4] and not evidence['audio_observed']
            assert len([b for b in messages[-1]['content'] if b['type']=='image_url'])==2
            return {'content':'{"summary":"observed"}'}
    calls=[]
    async def authorize(ctx):calls.append(ctx.task_id)
    assert asyncio.run(ModelTaskRunner(Transport(),authorize).run(ctx,'edit',Answer,tools=tools)).summary=='observed'
    assert len(calls)==2
    for args in [{'asset_id':'other','frame_times':[0]}, {'asset_id':'a','frame_times':[3]},
                 {'asset_id':'a','frame_times':[float('nan')]}, {'asset_id':'a','frame_times':[0],'path':'/etc/passwd'}]:
        with pytest.raises(ValueError):asyncio.run(tools[0].invoke(args,ctx))


def test_advice_is_not_a_quality_failure_but_evidence_is(monkeypatch):
    monkeypatch.setattr('easel.production.inspection.observe_media',lambda *a,**kw: ((),frozenset(),{}))
    class Runner:
        async def run(self,*a,**kw):return self.answer
    runner=Runner()
    for findings,expected in [([], 'pass'), (['0秒核心证据被遮挡'], 'fail')]:
        runner.answer=VisualPreviewReview(verdict='pass', observations=['构图可读'], findings=findings,
            suggestions=['可以更早切近景'], limitations=['仅抽帧，未听声音'])
        status,data=asyncio.run(review_visual_preview(None,runner=runner,context=None))
        assert status==expected and data['review']['suggestions']
        assert not data['audio_reviewed']


def test_automatic_retiming_keeps_story_voice_and_subtitles():
    base=EditProject(work_id='w',plan_revision=1,revision=1,width=1920,height=1080,duration=4,audio_mode='voice',
        scenes=[{'scene_id':'s1','asset_id':'a','duration':2},{'scene_id':'s2','asset_id':'b','duration':2}],
        audio=[{'clip_id':'v','asset_id':'voice','at':0,'duration':4,'role':'voice'}],captions=[])
    data=base.model_dump();data['scenes'][0]['duration']=1;data['scenes'][1]['duration']=3
    revised=EditProject.model_validate(data)
    with pytest.raises(EditError):assert_visual_repair(base,revised,overlay_texts=[])
    assert_visual_repair(base,revised,overlay_texts=[],allow_retiming=True)
    for field in ['order','audio','identity','duration']:
        bad=revised.model_dump()
        if field=='order':bad['scenes']=tuple(reversed(bad['scenes']))
        elif field=='audio':bad['audio'][0]['gain']=.2
        elif field=='duration':bad['scenes'][0]['duration']=1.5
        else:bad['work_id']='other'
        with pytest.raises((EditError,ValueError)):assert_visual_repair(base,EditProject.model_validate(bad),overlay_texts=[],allow_retiming=True)
