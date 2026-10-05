from copy import deepcopy
import json
import stat

import pytest

from scripts.configure_minimax_m3_thinking import configure, configured_profile


def test_m3_native_switch_preserves_auth_budget_and_other_model_contracts(tmp_path):
    config = {'models': {'providers': {'minimax': {'api': 'openai-completions',
        'apiKey': 'not-a-real-credential', 'models': [{'id': 'MiniMax-M3', 'maxTokens': 8192}]}}},
        'agents': {'defaults': {'model': {'primary': 'minimax/MiniMax-M3'}, 'thinkingDefault': 'off',
            'models': {'other/model': {'params': {'maxTokens': 17}},
                       'minimax/MiniMax-M3': {'params': {'extra_body': {'reasoning_split': True}}}}}}}
    path = tmp_path / 'profile.json'
    path.write_text(json.dumps(config))
    before = path.read_bytes()
    assert configure(path)['state'] == 'configuration_required'
    assert path.read_bytes() == before
    assert configure(path, apply=True)['state'] == 'configured_on_disk'
    updated = json.loads(path.read_text())
    assert updated['agents']['defaults']['models']['minimax/MiniMax-M3']['params']['extra_body']['thinking'] == {'type': 'disabled'}
    del updated['agents']['defaults']['models']['minimax/MiniMax-M3']['params']['extra_body']['thinking']
    assert updated == config
    backup = path.with_name(path.name + '.easel-minimax-thinking-original')
    assert backup.read_bytes() == before
    assert stat.S_IMODE(path.stat().st_mode) == stat.S_IMODE(backup.stat().st_mode) == 0o600
    saved = path.read_bytes()
    assert configure(path, apply=True)['state'] == 'already_configured'
    assert path.read_bytes() == saved
    for model in ('minimax/MiniMax-M3.1-Flash-Preview', 'minimax/MiniMax-M2.7', 'other/MiniMax-M3'):
        changed = deepcopy(config)
        changed['agents']['defaults']['model']['primary'] = model
        with pytest.raises(ValueError, match='不切换模型'):
            configured_profile(changed)
    wrong_route = deepcopy(config)
    wrong_route['models']['providers']['minimax']['api'] = 'anthropic-messages'
    with pytest.raises(ValueError, match='兼容通道'):
        configured_profile(wrong_route)
    path.write_text(json.dumps(config))
    backup.write_text('{}')
    with pytest.raises(ValueError, match='备份'):
        configure(path, apply=True)
    assert json.loads(path.read_text()) == config
