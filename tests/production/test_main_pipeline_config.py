from copy import deepcopy

import pytest

from easel.conversation_bridge import NATIVE_TOOLS
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
    assert set(result['allow']) == set(original['allow']) | set(NATIVE_TOOLS)
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


def test_bound_dialogue_system_separates_operation_manual_without_dropping_safety():
    from easel.video_workspace import pipeline_system_prompt,DIALOGUE_POLICY,POLICY
    prompt=pipeline_system_prompt()
    assert DIALOGUE_POLICY in prompt and POLICY not in prompt
    assert len(DIALOGUE_POLICY)<len(POLICY)//2
    # Primary execution boundaries remain unconditional, even before a full read.
    for boundary in ['UNKNOWN','下一真人回合','完整逐字稿','Rights','不自动投稿','不能编造用户亲历',
                     '新建方案','draft→保存依据→plan','成功持久化的Plan','不冒充正式方案','offer action=confirm','不新建提案供取消']:
        assert boundary in prompt
