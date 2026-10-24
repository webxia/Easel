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
    changed_style=revised.model_copy(update={'captions':tuple(c.model_copy(update={'background':'#000000CC'}) if c.caption_id=='c1' else c for c in revised.captions)})
    with pytest.raises(EditError,match='透明背景'):
        assert_visual_repair(base,changed_style,overlay_texts=approved,protected_caption_style_ids={'c1'})
    for change in ['audio','scene','caption','new_text']:
        bad=revised.model_dump()
        if change=='audio':bad['audio'][0]['gain']=.5
        if change=='scene':bad['scenes'][0]['scene_id']='foreign-cut1'
        if change=='caption':bad['captions'][0]['text']='篡改原句'
        if change=='new_text':bad['captions'][1]['text']='未经确认的新观点'
        with pytest.raises(EditError):
            assert_visual_repair(base,EditProject.model_validate(bad),overlay_texts=approved)


def test_revision_search_maps_only_existing_split_shots_to_plan():
    from easel.production.revisions import revision_plan_searches
    from easel.production.material_intent import VisualIntent
    from easel.production.model_tasks import ModelTaskError
    base=fixture().model_copy(update={'scenes':tuple(fixture().scenes[0].model_copy(update={'scene_id':s,'duration':2}) for s in ['s1-cut1','s1-cut2'])})
    plan={'scenes':[{'id':'s1'}]}
    search=VisualIntent(scene_id='s1-cut2',query='save document',media_types=['video'],options=2)
    result=revision_plan_searches(plan,base,[search])
    assert result==[{**search.model_dump(mode='json'),'scene_id':'s1'}]
    assert search.scene_id=='s1-cut2'
    assert revision_plan_searches(plan,base,[search.model_copy(update={'scene_id':'s1'})])==result
    for bad in ['s1-cut3','s1-extra','foreign-cut2','s1-cut0']:
        with pytest.raises(ModelTaskError):revision_plan_searches(plan,base,[search.model_copy(update={'scene_id':bad})])
    with pytest.raises(ModelTaskError):
        revision_plan_searches(plan,base,[search,search.model_copy(update={'scene_id':'s1-cut1'})])


def test_split_shot_error_identifies_actual_registered_parent():
    base=fixture().model_copy(update={'scenes':(fixture().scenes[0].model_copy(update={'scene_id':'s1_a'}),)})
    bad=base.model_copy(update={'scenes':(base.scenes[0].model_copy(update={'scene_id':'s1-cut1'}),)})
    with pytest.raises(EditError,match='s1_a'):
        assert_visual_repair(base,bad,overlay_texts=[])
    good=base.model_copy(update={'scenes':(base.scenes[0].model_copy(update={'scene_id':'s1_a-cut1'}),)})
    assert_visual_repair(base,good,overlay_texts=[])


def test_visual_repair_preserves_unchanged_source_audio_and_its_timeline_position():
    data = fixture().model_dump()
    data['scenes'] = [
        {'scene_id':'s1','asset_id':'a','duration':1},
        {'scene_id':'s2','asset_id':'street','duration':2,'source_audio':True,'source_gain':.35},
        {'scene_id':'s3','asset_id':'b','duration':1}]
    base = EditProject.model_validate(data)
    revised = base.model_copy(update={'scenes':tuple(
        s.model_copy(update={'asset_id':'replacement'}) if s.scene_id=='s3' else s for s in base.scenes)})
    assert_visual_repair(base,revised,overlay_texts=[],allow_retiming=True)
    for field, value in [('asset_id','other'),('source_start',.1),('source_gain',.5),
                         ('source_audio',False),('fade_out',.2)]:
        bad = revised.model_copy(update={'scenes':tuple(
            s.model_copy(update={field:value}) if s.scene_id=='s2' else s for s in revised.scenes)})
        with pytest.raises(EditError,match='完整音轨'):
            assert_visual_repair(base,bad,overlay_texts=[],allow_retiming=True)
    moved = revised.model_copy(update={'scenes':tuple(
        s.model_copy(update={'duration':s.duration + (.2 if s.scene_id=='s1' else -.2)})
        if s.scene_id!='s2' else s for s in revised.scenes)})
    with pytest.raises(EditError,match='完整音轨'):
        assert_visual_repair(base,moved,overlay_texts=[],allow_retiming=True)
    added = revised.model_copy(update={'scenes':tuple(
        s.model_copy(update={'source_audio':True}) if s.scene_id=='s3' else s for s in revised.scenes)})
    with pytest.raises(EditError,match='完整音轨'):
        assert_visual_repair(base,added,overlay_texts=[],allow_retiming=True)
