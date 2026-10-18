"""Frame-exact model edit projection: no unverified feature claims."""
import pytest
from easel.production.creation import CreativeEdit,align_editor_frames,project_editor_features
from easel.production.model_tasks import ModelTaskError


def test_model_cut_lengths_are_snapped_within_half_frame():
    proposal=CreativeEdit(scenes=[
        {'scene_id':'opening','asset_id':'actual-a','duration':7.105},
        {'scene_id':'detail','asset_id':'actual-b','duration':1.395},
    ],required_features=['video','exact_total_duration_8_5_seconds',
                         'creator_review_required_not_published'])
    precise=align_editor_frames(proposal)
    assert [round(s.duration,4) for s in precise.scenes]==[7.1,1.4]
    assert sum(s.duration-s.transition_seconds for s in precise.scenes)==8.5
    normalized,notes=project_editor_features(precise)
    assert normalized.required_features==['video']
    assert notes==['exact_total_duration_8_5_seconds','creator_review_required_not_published']
    assert proposal.scenes[0].duration==7.105  # original model answer retained


def test_frame_rounding_that_changes_total_is_blocked():
    answer=CreativeEdit(scenes=[
        {'scene_id':'first','asset_id':'actual-a','duration':0.021},
        {'scene_id':'second','asset_id':'actual-b','duration':0.021},
    ])
    with pytest.raises(ModelTaskError) as error:
        align_editor_frames(answer)
    assert error.value.code=='edit_frame_alignment_conflict'


def test_unbounded_unrecognized_editor_requirements_are_rejected():
    proposal=CreativeEdit(scenes=[{'scene_id':'s','asset_id':'video','duration':1}],
                          required_features=['new_feature_'+('a'*601)])
    with pytest.raises(ModelTaskError) as error:
        project_editor_features(proposal)
    assert error.value.code=='invalid_editor_features'

def test_overlapping_transitions_are_compensated_without_erasing_dissolves():
    from easel.production.creation import compensate_edit_overlap
    from easel.production.editors.base import EditProject
    answer=CreativeEdit(scenes=[
        {'scene_id':'a','asset_id':'real-a','duration':7,'transition':'cut','transition_seconds':0},
        {'scene_id':'b','asset_id':'real-b','duration':8,'transition':'dissolve','transition_seconds':.4},
    ])
    normalized=compensate_edit_overlap(align_editor_frames(answer),target_seconds=15)
    assert normalized.scenes[1].transition=='dissolve'
    assert abs(normalized.scenes[1].duration-8.4)<1e-8
    project=EditProject(work_id='w',plan_revision=1,revision=1,width=1080,height=1920,
                        duration=15,audio_mode='silent',**normalized.model_dump())
    assert abs(sum(s.duration-s.transition_seconds for s in project.scenes)-15)<1e-8


def test_invalid_model_timeline_cannot_be_covered_up_by_transition_compensation():
    from easel.production.creation import compensate_edit_overlap
    answer=CreativeEdit(scenes=[{'scene_id':'a','asset_id':'real-a','duration':10,'transition':'cut'}])
    with pytest.raises(ModelTaskError) as error:
        compensate_edit_overlap(answer,target_seconds=15)
    assert error.value.code=='edit_duration_mismatch'
