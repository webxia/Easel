from types import SimpleNamespace
import pytest
from easel.production.edit_observation import VisualSelection, check_visual_evidence

@pytest.mark.parametrize('status',['conflicting','missing_core_action'])
def test_explicit_mismatch_requires_existing_gap_path(status):
    e=VisualSelection(scene_id='scene',asset_id='asset',observation='Observed content differs',match_status=status)
    edit=SimpleNamespace(visual_evidence=[e],unresolved_scene_ids=[],scenes=[SimpleNamespace(scene_id='scene',asset_id='asset')])
    with pytest.raises(ValueError,match='不匹配'):check_visual_evidence(edit,{})
    edit.unresolved_scene_ids=['other']
    with pytest.raises(ValueError,match='不匹配'):check_visual_evidence(edit,{})
    edit.unresolved_scene_ids=['scene']
    check_visual_evidence(edit,{})
    edit.unresolved_scene_ids=[]
    check_visual_evidence(edit,{},pending_materials=True)

@pytest.mark.parametrize('status',['matched','illustrative','unverified'])
def test_illustration_and_sampling_uncertainty_are_not_new_gates(status):
    e=VisualSelection(scene_id='scene',asset_id='asset',observation='Atmosphere',match_status=status,uncertainty='Small text unreadable')
    edit=SimpleNamespace(visual_evidence=[e],unresolved_scene_ids=[],scenes=[SimpleNamespace(scene_id='scene',asset_id='asset')])
    check_visual_evidence(edit,{})
