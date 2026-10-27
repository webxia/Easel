import pytest
from easel.production.editors import EditProject, EditError
from easel.production.visual_repair import assert_visual_repair, approved_overlay_texts


def fixture():
    return EditProject(work_id='w',plan_revision=1,revision=1,width=1920,height=1080,duration=4,audio_mode='voice',
        scenes=[{'scene_id':'s1','asset_id':'old','duration':4}],
        audio=[{'clip_id':'v','asset_id':'voice','at':0,'duration':4,'role':'voice'}],
        captions=[{'caption_id':'c1','text':'旁白原句','start':0,'end':4,'font_asset_id':'font'}])


def test_local_overlay_removal_keeps_narration_audio_and_rejects_unknown_roles():
    from easel.production.revisions import RevisionProposal, merge_revision_changes
    from easel.production.editors import Caption, assert_local_revision
    base=fixture()
    overlay=Caption(caption_id='overlay',text='额外文字',start=1,end=3,font_asset_id='font',y=.2)
    base=base.model_copy(update={'captions':(*base.captions,overlay)})
    proposal=RevisionProposal(summary='删除额外文字',affected=['captions'],expands_scope=False,
        requires_new_generation=False,reason='保留旁白',changes={'remove_caption_ids':['overlay']})
    roles={'c1':'narration','overlay':'overlay'}
    edit=merge_revision_changes(proposal,base,caption_roles=roles)
    revised=base.model_copy(update={'captions':tuple(c for c in base.captions if c.caption_id!='overlay')})
    assert len(edit.captions)==1 and edit.captions[0].text=='旁白原句'
    assert edit.audio==list(base.audio) and edit.scenes==list(base.scenes)
    assert_local_revision(base,revised,allowed={'captions'},removable_caption_ids={'overlay'})
    with pytest.raises(EditError):assert_local_revision(base,revised,allowed={'visual'},removable_caption_ids={'overlay'})
    with pytest.raises(EditError):assert_local_revision(base,revised,allowed={'captions'})
    for ids,known in [(['c1'],roles),(['overlay'],{}),(['missing'],roles),(['overlay','overlay'],roles)]:
        bad=proposal.model_copy(update={'changes':proposal.changes.model_copy(update={'remove_caption_ids':ids})})
        with pytest.raises(ValueError,match='旁白'):merge_revision_changes(bad,base,caption_roles=known)
    altered=revised.model_copy(update={'captions':(revised.captions[0].model_copy(update={'text':'篡改'}),)})
    with pytest.raises(EditError):assert_local_revision(base,altered,allowed={'captions'},removable_caption_ids={'overlay'})


def test_missing_revision_role_metadata_uses_matching_persisted_proposal_only():
    import sqlite3,json
    from easel.production.revisions import stored_caption_roles
    conn=sqlite3.connect(':memory:');conn.row_factory=sqlite3.Row
    conn.execute('CREATE TABLE reviews(id TEXT, changes_json TEXT)')
    caption={**fixture().captions[0].model_dump(),'role':'overlay'}
    conn.execute('INSERT INTO reviews VALUES (?,?)',('r',json.dumps({'edit':{'captions':[caption]}})))
    record={'metadata_json':json.dumps({'review_id':'r'})}
    assert stored_caption_roles(conn,record,fixture())=={'c1':'overlay'}
    changed=fixture().model_copy(update={'captions':(fixture().captions[0].model_copy(update={'text':'不匹配'}),)})
    assert stored_caption_roles(conn,record,changed)=={}
    assert stored_caption_roles(conn,{'metadata_json':'{}'},fixture())=={}


def test_revision_cannot_reclassify_existing_narration_as_removable_overlay():
    from easel.production.revisions import revised_caption_roles
    from easel.production.creation import CreativeEdit
    base=fixture()
    data={k:v for k,v in base.model_dump().items() if k in CreativeEdit.model_fields}
    data['captions'][0]['role']='overlay'
    edit=CreativeEdit.model_validate(data)
    assert revised_caption_roles(base,edit,{'c1':'narration'})=={'c1':'narration'}
    assert revised_caption_roles(base,edit,{})=={'c1':'narration'}
    assert revised_caption_roles(base,edit,{'c1':'overlay'})=={'c1':'overlay'}


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


@pytest.mark.parametrize('suffix',['-cut','_'])
def test_revision_search_maps_only_existing_split_shots_to_plan(suffix):
    from easel.production.revisions import revision_plan_searches
    from easel.production.material_intent import VisualIntent
    from easel.production.model_tasks import ModelTaskError
    base=fixture().model_copy(update={'scenes':tuple(fixture().scenes[0].model_copy(update={'scene_id':s,'duration':2}) for s in ['s1'+suffix+'1','s1'+suffix+'2'])})
    plan={'scenes':[{'id':'s1'}]}
    search=VisualIntent(scene_id='s1'+suffix+'2',query='save document',media_types=['video'],options=2)
    result=revision_plan_searches(plan,base,[search])
    assert result==[{**search.model_dump(mode='json'),'scene_id':'s1'}]
    assert search.scene_id=='s1'+suffix+'2'
    assert revision_plan_searches(plan,base,[search.model_copy(update={'scene_id':'s1'})])==result
    for bad in ['s1'+suffix+'3','s1-extra','foreign'+suffix+'2','s1'+suffix+'0']:
        with pytest.raises(ModelTaskError):revision_plan_searches(plan,base,[search.model_copy(update={'scene_id':bad})])
    with pytest.raises(ModelTaskError):
        revision_plan_searches(plan,base,[search,search.model_copy(update={'scene_id':'s1'+suffix+'1','query':'another valid query'})])


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
                         ('source_audio',False)]:
        bad = revised.model_copy(update={'scenes':tuple(
            s.model_copy(update={field:value}) if s.scene_id=='s2' else s for s in revised.scenes)})
        with pytest.raises(EditError,match='原声发生变化'):
            assert_visual_repair(base,bad,overlay_texts=[],allow_retiming=True)
    moved = revised.model_copy(update={'scenes':tuple(
        s.model_copy(update={'duration':s.duration + (.2 if s.scene_id=='s1' else -.2)})
        if s.scene_id!='s2' else s for s in revised.scenes)})
    with pytest.raises(EditError,match='原声发生变化'):
        assert_visual_repair(base,moved,overlay_texts=[],allow_retiming=True)
    added = revised.model_copy(update={'scenes':tuple(
        s.model_copy(update={'source_audio':True}) if s.scene_id=='s3' else s for s in revised.scenes)})
    with pytest.raises(EditError,match='原声发生变化'):
        assert_visual_repair(base,added,overlay_texts=[],allow_retiming=True)


def test_source_audio_allows_visual_only_changes():
    base=fixture()
    base=base.model_copy(update={'scenes':(base.scenes[0].model_copy(update={'source_audio':True}),)})
    after=base.model_copy(update={'scenes':(base.scenes[0].model_copy(update={'fit':'contain','motion':'push_in','fade_out':.2}),)})
    assert_visual_repair(base,after,overlay_texts=[])


def test_local_changes_inherit_audio_and_unaffected_fields_and_compile_overlap():
    from easel.production.revisions import RevisionProposal, merge_revision_changes, compile_revision_edit
    base=fixture()
    proposal=RevisionProposal(summary='局部',affected=['visual'],expands_scope=False,requires_new_generation=False,reason='取景',
        changes={'scenes':[{'scene_id':'s1','scenes':[
            {'scene_id':'s1-cut1','asset_id':'old','duration':2},
            {'scene_id':'s1-cut2','asset_id':'new','duration':2,'transition':'dissolve','transition_seconds':.5}]}]})
    edit=compile_revision_edit(merge_revision_changes(proposal,base),base)
    from easel.production.creative_captions import edit_data
    assert edit.audio==list(base.audio) and edit_data(edit)['captions']==list(base.model_dump()['captions'])
    assert [s.duration for s in edit.scenes]==[2,2.5]
    assert compile_revision_edit(edit,base)==edit
    bad=edit.model_copy(update={'scenes':[s.model_copy(update={'duration':1}) for s in edit.scenes]})
    with pytest.raises(ValueError,match='差值'):compile_revision_edit(bad,base)
    proposal.changes.scenes[0].scene_id='foreign'
    with pytest.raises(ValueError,match='已登记'):merge_revision_changes(proposal,base)


def test_recovery_updates_instruction_without_changing_evidence_or_receipt():
    from easel.production.revisions import revision_recovery_messages
    original=[{'role':'system','content':'authority\n任务：返回完整时间线\n输出schema：old'},
              {'role':'user','content':'base'}, {'role':'tool','content':'observed'}]
    updated=revision_recovery_messages(original,'只修改局部changes')
    assert original[0]['content'].endswith('old')
    assert updated[1:]==original[1:]
    assert updated[0]['content'].startswith('authority\n任务：只修改局部changes')
    assert '返回完整时间线' not in updated[0]['content']
    assert 'RevisionChanges' in updated[0]['content']


@pytest.mark.parametrize('fps',[24,25,30])
def test_revision_compiles_with_original_frame_rate(fps):
    from easel.production.revisions import RevisionProposal,merge_revision_changes,compile_revision_edit
    from easel.production.creation import check_edit_source_bounds
    base=fixture().model_copy(update={'fps':fps})
    proposal=RevisionProposal(summary='局部',affected=['visual'],expands_scope=False,requires_new_generation=False,reason='分镜',
        changes={'scenes':[{'scene_id':'s1','scenes':[
            {'scene_id':'s1-cut1','asset_id':'old','duration':25/fps},
            {'scene_id':'s1-cut2','asset_id':'new','duration':4-25/fps}]}]})
    edit=compile_revision_edit(merge_revision_changes(proposal,base),base)
    check_edit_source_bounds(edit,{'old':25/fps,'new':4-25/fps},target_seconds=4,fps=fps)
    assert sum(s.duration for s in edit.scenes)==4


def test_visual_response_schema_excludes_full_edit_but_legacy_reader_keeps_it():
    from easel.production.revisions import VisualRevisionProposal,RevisionProposal
    from pydantic import ValidationError
    fields={'summary':'修画面','affected':['visual'],'expands_scope':False,'requires_new_generation':False,'reason':'裁切'}
    schema=VisualRevisionProposal.model_json_schema()
    assert schema['title']=='RevisionProposal' and 'edit' not in schema['properties']
    assert 'changes' in schema['required']
    old={**fields,'edit':{'scenes':[s.model_dump() for s in fixture().scenes]}}
    assert RevisionProposal.model_validate(old).edit
    with pytest.raises(ValidationError):VisualRevisionProposal.model_validate(old)
    assert VisualRevisionProposal.model_validate({**fields,'changes':{}}).changes.scenes==[]
