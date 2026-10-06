"""Deterministic tests must never write the shared production runtime."""
from pathlib import Path
import builtins
import io
import os
import pytest


@pytest.fixture(autouse=True)
def protect_real_runtime_writes(monkeypatch):
    roots = (Path(__file__).resolve().parents[1] / 'outputs', Path.home() / '.easel/hypit')

    def check(path):
        if not isinstance(path, (str, bytes, os.PathLike)):
            return
        target = Path(os.fsdecode(path)).absolute()
        if any(target == root or target.is_relative_to(root) for root in roots):
            raise AssertionError('测试禁止写入真实 Creation 或 Attempt runtime；必须使用隔离工作区')

    def guarded_open(native):
        def open_file(file, mode='r', *args, **kwargs):
            if any(flag in mode for flag in 'wa+x'):
                check(file)
            return native(file, mode, *args, **kwargs)
        return open_file

    native_open = os.open
    def open_fd(path, flags, *args, **kwargs):
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC):
            check(path)
        return native_open(path, flags, *args, **kwargs)

    def guarded_move(native):
        def move(source, target, *args, **kwargs):
            check(source); check(target)
            return native(source, target, *args, **kwargs)
        return move

    monkeypatch.setattr(builtins, 'open', guarded_open(builtins.open))
    monkeypatch.setattr(io, 'open', guarded_open(io.open))
    monkeypatch.setattr(os, 'open', open_fd)
    monkeypatch.setattr(os, 'replace', guarded_move(os.replace))
    monkeypatch.setattr(os, 'rename', guarded_move(os.rename))
