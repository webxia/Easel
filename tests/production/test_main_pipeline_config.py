from copy import deepcopy

import pytest

from easel.conversation_bridge import TOOLS
from easel.video_workspace import main_pipeline_tools


def test_main_policy_is_bounded_and_preserves_restrictions():
    original = {
        'profile': 'coding', 'allow': ['read', 'exec', 'easel_pipeline'],
        'deny': ['exec', 'sessions_spawn'],
        'byProvider': {'example': {'deny': ['write']}},
        'exec': {'security': 'deny'},
    }
    before = deepcopy(original)
    result = main_pipeline_tools(original)
    assert original == before
    assert result['profile'] == 'full'
    assert set(result['allow']) == set(original['allow']) | set(TOOLS)
    assert len(result['allow']) == len(set(result['allow']))
    for key in ('deny', 'byProvider', 'exec'):
        assert result[key] == original[key]
    assert main_pipeline_tools(result) == result


@pytest.mark.parametrize('policy', [
    {}, {'allow': []}, {'allow': ['*']}, {'allow': ['easel_*']},
    {'allow': ['group:runtime']}, {'allow': ['read'], 'alsoAllow': ['write']},
])
def test_unbounded_or_ambiguous_policy_requires_review(policy):
    with pytest.raises(ValueError):
        main_pipeline_tools(policy)
