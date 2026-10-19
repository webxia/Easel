import pytest
from easel.production.editors import EditProject, EditError
from easel.production.visual_repair import assert_visual_repair, approved_overlay_texts


def fixture():
    return EditProject(work_id='w',plan_revision=1,revision=1,width=1920,height=1080,duration=4,audio_mode='voice',
        scenes=[{'scene_id':'s1','asset_id':'old','duration':4}],
        audio=[{'clip_id':'v','asset_id':'voice','at':0,'duration':4,'role':'voice'}],
        captions=[{'caption_id':'c1','text':'旁白原句','start':0,'end':4,'font_asset_id':'font'}])


def test_native_recut_preserves_voice_group_time_and_approved_overlay_only():
    base=fixture()
    data=base.model_dump();data['revision']=2
    data['scenes']=[{'scene_id':'s1-cut1','asset_id':'a','duration':2},
                    {'scene_id':'s1-cut2','asset_id':'b','duration':2}]
    data['captions']=list(data['captions'])+[{'caption_id':'title','text':'做完不等于学会','start':0,'end':2,'font_asset_id':'font','y':.2}]
    revised=EditProject.model_validate(data)
    approved=approved_overlay_texts({'scenes':[{'visual':'上方显示“做完不等于学会”'}]})
    assert_visual_repair(base,revised,overlay_texts=approved)
    for change in ['audio','scene','caption','new_text']:
        bad=revised.model_dump()
        if change=='audio':bad['audio'][0]['gain']=.5
        if change=='scene':bad['scenes'][0]['scene_id']='foreign-cut1'
        if change=='caption':bad['captions'][0]['text']='篡改原句'
        if change=='new_text':bad['captions'][1]['text']='未经确认的新观点'
        with pytest.raises(EditError):
            assert_visual_repair(base,EditProject.model_validate(bad),overlay_texts=approved)
