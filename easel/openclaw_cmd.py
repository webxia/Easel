"""Resolve how to invoke the openclaw CLI as an argv prefix.

Windows pitfall this solves: `openclaw` on PATH is a `.cmd` shim. Python's
CreateProcess cannot run it directly, and wrapping in cmd.exe /c breaks
messages containing newlines (cmd treats the rest of the line as a separate
command -> "your message got cut off" / silently truncated input). Running
`node openclaw.mjs` directly avoids both problems.

On Linux/macOS `openclaw` on PATH is a real executable (a symlink to
`openclaw.mjs` with a `#!/usr/bin/env node` shebang), so running it directly
is fine. The resolution below therefore prefers `node + openclaw.mjs` when it
can locate the script (robust everywhere, mandatory on Windows), and falls
back to the PATH `openclaw` executable rather than hard-failing.
"""

from __future__ import annotations

import shutil
import json
import os
import re
from functools import lru_cache
from pathlib import Path


def _route_config_path(profile: str, env: dict) -> Path:
    """Resolve the supported CLI profile environment; reject ambiguous selectors."""
    inherited = env.get('OPENCLAW_PROFILE', '').strip() or 'default'
    if any(not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}', p)
           for p in (profile, inherited)) or env.get('OPENCLAW_HOME', '').strip():
        raise ValueError('无法核实OpenClaw配置路径；未派发')
    home_value = next((env.get(k, '').strip() for k in ('HOME', 'USERPROFILE')
                       if env.get(k, '').strip() not in ('', 'null', 'undefined')), str(Path.home()))
    home = Path(os.path.abspath(home_value))
    def expand(value):
        value = value.strip()
        if value == '~' or value.startswith('~/'):
            value = str(home) + value[1:]
        return Path(os.path.abspath(value))
    def state(p):
        return home / ('.openclaw' if p.lower() == 'default' else f'.openclaw-{p}')
    previous, selected = state(inherited), state(profile)
    existing_state = env.get('OPENCLAW_STATE_DIR', '').strip()
    existing_config = env.get('OPENCLAW_CONFIG_PATH', '').strip()
    switching = previous != selected
    if switching and any(env.get(k) for k in (
            'OPENCLAW_SERVICE_KIND', 'OPENCLAW_SERVICE_MARKER', 'OPENCLAW_LAUNCHD_LABEL',
            'OPENCLAW_SYSTEMD_UNIT', 'OPENCLAW_WINDOWS_TASK_NAME')):
        raise ValueError('继承的服务配置选择器需要单独核验；未派发')
    switching_state = bool(existing_state and switching and expand(existing_state) == previous)
    selected_state = expand(existing_state) if existing_state and not switching_state else selected
    replace_config = (switching and (not existing_state or switching_state)
                      and existing_config and expand(existing_config) == previous / 'openclaw.json')
    return (expand(existing_config) if existing_config and not replace_config
            else selected_state / 'openclaw.json')


def model_route(profile: str, thinking: str = '', *, config_path: Path | None = None,
                environ: dict | None = None) -> dict:
    """Read the configured route, without credentials or changing live config.

    Runtime loading is separately verified before admitting a new candidate.
    Existing non-M3.1 routes keep their original identity and default behavior.
    """
    path = config_path or _route_config_path(profile, dict(os.environ) if environ is None else environ)
    try:
        config = json.loads(path.read_text())
        return _configured_model_route(config, profile, thinking)
    except (OSError, UnicodeError, json.JSONDecodeError, AttributeError, KeyError, TypeError):
        raise ValueError('OpenClaw配置不可读或必要结构无效；未派发') from None


def _configured_model_route(config: dict, profile: str, thinking: str) -> dict:
    defaults = config.get('agents', {}).get('defaults', {})
    selected = defaults.get('model', {})
    primary = selected.get('primary') if isinstance(selected, dict) else selected
    if not isinstance(primary, str) or not primary:
        raise ValueError('OpenClaw主模型缺失或无效；未派发')
    route = {'profile': profile, 'thinking': thinking or 'off'}
    target = 'minimax/MiniMax-M3.1-Flash-Preview'
    if primary != target:
        return route
    # OpenClaw's MiniMax level is adaptive; Provider effort is a separate field.
    level = thinking or 'adaptive'
    provider = config.get('models', {}).get('providers', {}).get('minimax', {})
    rows = [m for m in provider.get('models', []) if m.get('id') == target.split('/', 1)[1]]
    params = defaults.get('models', {}).get(target, {}).get('params', {})
    extra = params.get('extra_body', {})
    effort = extra.get('reasoning_effort')
    output_limit = 32768 if effort == 'max' else 8192
    if (not isinstance(selected, dict) or level != 'adaptive' or provider.get('api') != 'openai-completions'
            or provider.get('baseUrl') != 'https://api.minimax.cn/v1'
            or len(rows) != 1 or rows[0].get('reasoning') is not True
            or rows[0].get('maxTokens') != output_limit or params.get('maxTokens') != output_limit
            or extra.get('thinking') != {'type': 'adaptive'}
            or effort not in ('low', 'medium', 'max')
            or extra.get('reasoning_split') is False
            or selected.get('fallbacks', []) or defaults.get('thinkingDefault') != 'adaptive'):
        raise ValueError('M3.1路由未匹配候选adaptive及已核定的推理/输出上限组合；未派发')
    return {**route, 'thinking': level, 'provider': 'minimax',
            'model': rows[0]['id'], 'api': provider['api'], 'origin': provider['baseUrl'],
            'model_params': {'thinking': 'adaptive', 'reasoning_effort': effort, 'max_tokens': output_limit},
            **({'configuration_policy': f'minimax-m31-adaptive-{effort}-{output_limit}@1'} if effort != 'low' else {})}


@lru_cache(maxsize=1)
def openclaw_base_cmd() -> list[str]:
    """Return the argv prefix for invoking openclaw.

    Prefers ``[node, /path/to/openclaw.mjs]``; falls back to ``[openclaw]`` on
    PATH. Raises FileNotFoundError only when openclaw cannot be located at all.
    """
    node = shutil.which("node")
    oc = shutil.which("openclaw")

    # 1) PATH `openclaw` that resolves to the .mjs (Unix symlink, or a direct
    #    .mjs on PATH): run it through node explicitly.
    if oc and node:
        resolved = Path(oc).resolve()
        if resolved.suffix == ".mjs" and resolved.is_file():
            return [node, str(resolved)]

    # 2) Hunt for openclaw.mjs under the known npm global layouts.
    if node:
        node_dir = Path(node).resolve().parent
        candidates = [
            # Unix standard: <prefix>/bin/node -> <prefix>/lib/node_modules/...
            node_dir.parent / "lib" / "node_modules" / "openclaw" / "openclaw.mjs",
            # npm global prefix == node dir (zip / some nvm-style installs)
            node_dir / "node_modules" / "openclaw" / "openclaw.mjs",
            # Windows standard: npm global prefix == %APPDATA%/npm
            Path.home() / "AppData" / "Roaming" / "npm" / "node_modules" / "openclaw" / "openclaw.mjs",
        ]
        for cand in candidates:
            if cand.is_file():
                return [node, str(cand)]

    # 3) Fallback: run the PATH `openclaw` directly. On Unix this is a real
    #    executable and works. On Windows this is the `.cmd` shim (only reached
    #    when the .mjs truly can't be found) — still better than hard-failing.
    if oc:
        return [oc]

    raise FileNotFoundError(
        "openclaw CLI not found: no 'node'+openclaw.mjs and no 'openclaw' on PATH"
    )
