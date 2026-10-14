"""Set the native MiniMax-M3 OpenAI thinking switch; never change models or budgets.

Official contract: https://platform.minimaxi.com/docs/api-reference/text-openai-api
OpenClaw's generic --thinking off does not supply this provider field.
The configuration and its backup stay in the protected local profile, never Git.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile


def configured_profile(config: dict) -> dict:
    model = 'minimax/MiniMax-M3'
    defaults = config.get('agents', {}).get('defaults', {})
    if defaults.get('model', {}).get('primary') != model:
        raise ValueError('只支持当前主模型为 minimax/MiniMax-M3 的配置，不切换模型')
    provider = config.get('models', {}).get('providers', {}).get('minimax', {})
    if (provider.get('api') != 'openai-completions'
            or not any(row.get('id') == 'MiniMax-M3' for row in provider.get('models', []))):
        raise ValueError('当前 MiniMax-M3 不是已核实的 OpenAI 兼容通道')
    updated = deepcopy(config)
    params = updated['agents']['defaults'].setdefault('models', {}).setdefault(model, {}).setdefault('params', {})
    extra = params.setdefault('extra_body', {})
    if not isinstance(extra, dict):
        raise ValueError('extra_body 必须为对象；未修改配置')
    extra['thinking'] = {'type': 'disabled'}
    return updated


def migrated_m31_profile(config: dict, *, reasoning_effort: str = 'low') -> dict:
    """Explicit migration candidate; the original M3 entry still rejects M3.1."""
    try:
        return _migrated_m31_profile(config, reasoning_effort=reasoning_effort)
    except (AttributeError, KeyError, TypeError):
        raise ValueError('M3.1迁移配置的必要结构无效；未修改配置') from None


def _migrated_m31_profile(config: dict, *, reasoning_effort: str) -> dict:
    if reasoning_effort not in ('low', 'medium', 'max'):
        raise ValueError('未核定的M3.1推理候选；未修改配置')
    output_limit = 32768 if reasoning_effort == 'max' else 8192
    target = 'minimax/MiniMax-M3.1-Flash-Preview'
    defaults = config.get('agents', {}).get('defaults', {})
    primary = defaults.get('model', {}).get('primary')
    if primary not in {'minimax/MiniMax-M3', target}:
        raise ValueError('仅允许明确迁移现有MiniMax文字路由')
    provider = config.get('models', {}).get('providers', {}).get('minimax', {})
    if provider.get('api') != 'openai-completions' or provider.get('baseUrl') != 'https://api.minimax.cn/v1':
        raise ValueError('迁移仅适用于已核实的国内OpenAI兼容通道')
    updated = deepcopy(config)
    defaults = updated['agents']['defaults']
    defaults['model'] = {'primary': target, 'fallbacks': []}
    defaults['thinkingDefault'] = 'adaptive'
    models = updated['models']['providers']['minimax']['models']
    rows = [r for r in models if r.get('id') == target.split('/', 1)[1]]
    if len(rows) > 1:
        raise ValueError('M3.1模型目录重复；未修改配置')
    if rows:
        row = rows[0]
    else:
        row = {'id': target.split('/', 1)[1]}
        models.append(row)
    row.update(name='MiniMax M3.1 Flash Preview', reasoning=True, input=['text', 'image'],
               contextWindow=1000000, maxTokens=output_limit)
    params = defaults.setdefault('models', {}).setdefault(target, {}).setdefault('params', {})
    extra = params.setdefault('extra_body', {})
    if not isinstance(extra, dict):
        raise ValueError('extra_body必须为对象；未修改配置')
    params['maxTokens'] = output_limit
    extra.update(thinking={'type': 'adaptive'}, reasoning_effort=reasoning_effort)
    if extra.get('reasoning_split') is False:
        extra['reasoning_split'] = True
    return updated


def configure(path: Path, *, apply: bool = False, migrate_m31: bool = False,
              reasoning_effort: str = 'low') -> dict:
    if not migrate_m31 and reasoning_effort != 'low':
        raise ValueError('推理档位仅适用于显式M3.1迁移')
    if path.is_symlink():
        raise ValueError('配置路径不能为符号链接')
    original = path.read_bytes()
    updated = (migrated_m31_profile(json.loads(original), reasoning_effort=reasoning_effort)
               if migrate_m31 else configured_profile(json.loads(original)))
    report = {'model': 'minimax/MiniMax-M3.1-Flash-Preview' if migrate_m31 else 'minimax/MiniMax-M3',
              'thinking': 'adaptive' if migrate_m31 else 'disabled',
              **({'reasoning_effort': reasoning_effort, 'max_tokens': 32768 if reasoning_effort == 'max' else 8192,
                   'web_thinking': 'adaptive'} if migrate_m31 else {})}
    if updated == json.loads(original):
        return {'state': 'already_configured', **report}
    if not apply:
        return {'state': 'configuration_required', **report}
    backup = path.with_name(path.name + ('.easel-minimax-m31-original' if migrate_m31 else '.easel-minimax-thinking-original'))
    if backup.is_symlink() or backup.exists() and backup.read_bytes() != original:
        raise ValueError('原备份与当前配置不同；未覆盖配置或备份')
    if not backup.exists():
        fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as f:
            f.write(original)
    os.chmod(backup, 0o600)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.easel-minimax-thinking-')
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(updated, f, ensure_ascii=False, indent=2)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        if path.read_bytes() != original:
            raise ValueError('配置在修复期间变化；未覆盖新内容')
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return {'state': 'configured_on_disk', **report, 'service_restarted': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', type=Path)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--migrate-m31', action='store_true', help='显式准备M3.1 adaptive/low迁移；默认只读预览')
    parser.add_argument('--reasoning-effort', choices=('low', 'medium', 'max'), default='low',
                        help='仅显式M3.1候选；low/medium固定8192，max固定32768；不扩调用上限')
    args = parser.parse_args()
    print(json.dumps(configure(args.config, apply=args.apply, migrate_m31=args.migrate_m31,
                               reasoning_effort=args.reasoning_effort), ensure_ascii=False))
