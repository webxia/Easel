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


def test_retired_revision_name_is_removed_from_bounded_policy():
    original={'profile':'full','allow':['read','easel_work_request_revision'],'deny':['exec']}
    result=main_pipeline_tools(original)
    assert 'easel_work_request_revision' not in result['allow']
    assert set(result['allow'])=={'read',*NATIVE_TOOLS}
    assert result['deny']==original['deny']
    assert original['allow']==['read','easel_work_request_revision']


def test_actual_product_prompt_carries_language_policy_through_both_native_entry_points():
    from easel.video_workspace import pipeline_system_prompt
    prompt = pipeline_system_prompt()
    assert '默认用自然、完整的中文交流' in prompt
    assert '工具调用前后的简短说明、异常解释和最终回复遵循同一语言' in prompt
    assert '技术术语、代码标识、专有名称和必要原文可保留英文' in prompt
    assert '用户明确要求其他语言时跟随' in prompt


def test_directory_display_rule_reaches_live_bootstrap_and_operation_guide_once():
    from easel.video_workspace import CATALOG_SELECTION_POLICY,DIALOGUE_POLICY,POLICY,pipeline_system_prompt
    for prompt in (DIALOGUE_POLICY,POLICY,pipeline_system_prompt()):
        assert prompt.count(CATALOG_SELECTION_POLICY)==1
        assert '每个真实版本ID只对应一个选项' in prompt
        assert '导演按display_label展示名称、版本和接受状态' in prompt
        assert '不能自行增加“试片版”选项' in prompt
        assert '历史回复也不能补充或覆盖当前目录' in prompt
