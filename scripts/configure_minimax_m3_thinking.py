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


def configure(path: Path, *, apply: bool = False) -> dict:
    if path.is_symlink():
        raise ValueError('配置路径不能为符号链接')
    original = path.read_bytes()
    updated = configured_profile(json.loads(original))
    if updated == json.loads(original):
        return {'state': 'already_configured', 'model': 'minimax/MiniMax-M3', 'thinking': 'disabled'}
    if not apply:
        return {'state': 'configuration_required', 'model': 'minimax/MiniMax-M3', 'thinking': 'disabled'}
    backup = path.with_name(path.name + '.easel-minimax-thinking-original')
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
    return {'state': 'configured_on_disk', 'model': 'minimax/MiniMax-M3',
            'thinking': 'disabled', 'service_restarted': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    print(json.dumps(configure(args.config, apply=args.apply), ensure_ascii=False))
