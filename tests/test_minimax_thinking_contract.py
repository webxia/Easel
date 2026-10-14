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


@pytest.mark.parametrize('effort', ['low', 'medium', 'max'])
def test_m31_explicit_migration_and_web_route_preserve_original_profile(tmp_path, monkeypatch, effort):
    from scripts.configure_minimax_m3_thinking import migrated_m31_profile
    from easel.openclaw_cmd import model_route
    from web import app as web
    config = {'models': {'providers': {'minimax': {'api': 'openai-completions',
        'baseUrl': 'https://api.minimax.cn/v1', 'apiKey': 'offline-secret-marker',
        'models': [{'id': 'MiniMax-M3', 'maxTokens': 8192}]}}},
        'agents': {'defaults': {'model': {'primary': 'minimax/MiniMax-M3', 'fallbacks': []},
            'thinkingDefault': 'off', 'models': {'minimax/MiniMax-M3': {
                'params': {'extra_body': {'thinking': {'type': 'disabled'}}}}}}}}
    path = tmp_path / 'profile.json'; path.write_text(json.dumps(config))
    original = path.read_bytes()
    preview = configure(path, reasoning_effort=effort, migrate_m31=True)
    assert preview['thinking'] == 'adaptive' and preview['reasoning_effort'] == effort
    assert path.read_bytes() == original and 'offline-secret-marker' not in json.dumps(preview)
    assert model_route('easel', config_path=path) == {'profile': 'easel', 'thinking': 'off'}
    configure(path, reasoning_effort=effort, migrate_m31=True, apply=True)  # Isolated fixture only.
    migrated = json.loads(path.read_text())
    assert migrated == migrated_m31_profile(config, reasoning_effort=effort)
    assert migrated['models']['providers']['minimax']['apiKey'] == 'offline-secret-marker'
    assert migrated['agents']['defaults']['models']['minimax/MiniMax-M3'] == config['agents']['defaults']['models']['minimax/MiniMax-M3']
    assert path.with_name('profile.json.easel-minimax-m31-original').read_bytes() == original
    assert configure(path, reasoning_effort=effort, migrate_m31=True, apply=True)['state'] == 'already_configured'
    with pytest.raises(ValueError, match='不切换模型'):
        configure(path)  # Legacy entry must still refuse the new model.
    monkeypatch.setenv('OPENCLAW_CONFIG_PATH', str(path))
    monkeypatch.setattr(web, 'THINKING_LEVEL', '')
    route = web._model_route()
    assert route['model'] == 'MiniMax-M3.1-Flash-Preview' and route['thinking'] == 'adaptive'
    assert migrated['agents']['defaults']['thinkingDefault'] == preview['web_thinking'] == 'adaptive'
    assert route['model_params']['reasoning_effort'] == effort
    assert ('configuration_policy' in route) is (effort != 'low')
    assert route['model_params']['max_tokens'] == preview['max_tokens'] == (32768 if effort == 'max' else 8192)
    for changed_limit in (8192, 16384, 32768, 65536):
        if changed_limit == preview['max_tokens']: continue
        changed = deepcopy(migrated)
        changed['agents']['defaults']['models']['minimax/MiniMax-M3.1-Flash-Preview']['params']['maxTokens'] = changed_limit
        path.write_text(json.dumps(changed))
        with pytest.raises(ValueError, match='未派发'): model_route('easel', config_path=path)
    path.write_text(json.dumps(migrated))
    assert 'offline-secret-marker' not in json.dumps(route)
    monkeypatch.setattr(web, '_heal_openclaw_session', lambda *_: pytest.fail('Invalid route touched history'))
    for invalid in ('off', 'none', 'disabled', 'low', 'high'):
        monkeypatch.setattr(web, 'THINKING_LEVEL', invalid)
        with pytest.raises(ValueError, match='未派发'):
            web.run_agent_sync('offline-invalid-route')
    for invalid in ('none', 'high', 'xhigh', 'invalid'):
        with pytest.raises(ValueError):
            migrated_m31_profile(config, reasoning_effort=invalid)
        changed = deepcopy(migrated)
        changed['agents']['defaults']['models']['minimax/MiniMax-M3.1-Flash-Preview']['params']['extra_body']['reasoning_effort'] = invalid
        path.write_text(json.dumps(changed))
        with pytest.raises(ValueError, match='未派发'):
            model_route('easel', config_path=path)
    with pytest.raises(ValueError, match='显式'):
        configure(path, reasoning_effort='medium')
    for field in ('thinking', 'reasoning_effort'):
        changed = deepcopy(migrated)
        changed['agents']['defaults']['models']['minimax/MiniMax-M3.1-Flash-Preview']['params']['extra_body'][field] = 'invalid'
        path.write_text(json.dumps(changed))
        with pytest.raises(ValueError, match='未派发'):
            model_route('easel', config_path=path)
    # Malformed optional containers cannot be treated as an admissible route.
    for keys in (('agents',), ('agents', 'defaults'), ('models', 'providers'),
                 ('models', 'providers', 'minimax', 'models'),
                 ('agents', 'defaults', 'models', 'minimax/MiniMax-M3.1-Flash-Preview', 'params')):
        changed = deepcopy(migrated)
        parent = changed
        for key in keys[:-1]: parent = parent[key]
        parent[keys[-1]] = None
        path.write_text(json.dumps(changed))
        with pytest.raises(ValueError): model_route('easel', config_path=path)
        with pytest.raises(ValueError): migrated_m31_profile(changed)
    path.unlink()
    with pytest.raises(ValueError, match='未派发'): model_route('easel', config_path=path)


def test_route_config_selection_follows_cli_profile_precedence(tmp_path):
    from easel.openclaw_cmd import _route_config_path
    home = tmp_path / 'home'
    base = {'HOME': str(home)}
    chosen = home / '.openclaw-easel' / 'openclaw.json'
    assert _route_config_path('easel', base) == chosen
    inherited = {**base, 'OPENCLAW_PROFILE': 'other',
                 'OPENCLAW_STATE_DIR': str(home / '.openclaw-other'),
                 'OPENCLAW_CONFIG_PATH': str(home / '.openclaw-other' / 'openclaw.json')}
    assert _route_config_path('easel', inherited) == chosen
    assert _route_config_path('easel', {**inherited, 'HOME': f' {home}/../home '}) == chosen
    custom = {**inherited, 'OPENCLAW_STATE_DIR': str(tmp_path / 'custom'),
              'OPENCLAW_CONFIG_PATH': str(tmp_path / 'explicit.json')}
    assert _route_config_path('easel', custom) == tmp_path / 'explicit.json'
    del custom['OPENCLAW_CONFIG_PATH']
    assert _route_config_path('easel', custom) == tmp_path / 'custom' / 'openclaw.json'
    for key in ('OPENCLAW_HOME', 'OPENCLAW_SERVICE_KIND'):
        with pytest.raises(ValueError, match='未派发'):
            _route_config_path('easel', {**inherited, key: 'unsupported-context'})


def test_history_heal_keeps_minimax_tool_replay_and_unknown_sources(tmp_path):
    from scripts.session_heal import sanitize_rows, sanitize_history_file
    rows = [{'type': 'message', 'message': {'role': 'assistant', 'provider': provider,
             'model': 'MiniMax-M3.1-Flash-Preview', 'content': [
                 {'type': 'thinking', 'thinking': 'offline-private-reasoning'},
                 {'type': 'toolCall', 'id': 'original-call', 'name': 'fixed', 'arguments': {}}]}}
            for provider in ('minimax', 'unknown')]
    rows += [{'type': 'message', 'message': {'role': 'toolResult',
              'toolCallId': 'original-call', 'content': [{'type': 'text', 'text': 'fixed-result'}]}}]
    original = deepcopy(rows)
    clean, stats = sanitize_rows(rows)
    assert clean == original and rows == original and stats == {'thinking_removed': 0, 'msgs_dropped': 0}
    path = tmp_path / 'history.jsonl'; path.write_text('\n'.join(json.dumps(r) for r in rows) + '\n')
    raw = path.read_bytes()
    assert not sanitize_history_file(path)['changed'] and path.read_bytes() == raw
    bedrock = {'type': 'message', 'message': {'role': 'assistant', 'provider': 'amazon-bedrock',
        'model': 'anthropic.claude-fixture', 'content': [
            {'type': 'thinking', 'thinking': 'broken'},
            {'type': 'thinking', 'thinking': 'signed', 'thinkingSignature': 'fixed-signature'},
            {'type': 'redacted_thinking', 'data': 'fixed'},
            {'type': 'toolCall', 'id': 'original-bedrock', 'name': 'fixed', 'arguments': {}}]}}
    before = deepcopy(bedrock)
    clean, stats = sanitize_rows([bedrock])
    assert bedrock == before and stats['thinking_removed'] == 1
    assert clean[0]['message']['content'] == before['message']['content'][1:]
