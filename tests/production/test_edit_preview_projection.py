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
