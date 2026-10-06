"""Opt-in boundary matrix: isolated runtime and evidence, never a live E2E."""
from __future__ import annotations
import builtins
import hashlib
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'web'))


def pytest_addoption(parser):
    parser.addoption('--matrix-output', default=None)


class Trace:
    def __init__(self):
        self.expected = ''
        self.basis = ''
        self.events = []
        self.gaps = []
        self.blocked = []

    def define(self, expected, basis):
        self.expected, self.basis = expected, basis

    def note(self, label, value):
        self.events.append({'label': label, 'actual': value})

    def gap(self, description, actual):
        self.gaps.append({'description': description, 'actual': actual})


@pytest.fixture
def trace(request):
    evidence = Trace()
    request.node.matrix_trace = evidence
    yield evidence


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch, trace):
    # No network/child processes/real runtime configuration. Overrides in cases
    # are explicit fixture adapters; product modules otherwise remain native.
    from easel import creation, creative_mode
    from easel.runtime_config import EaselRuntimeConfig
    from easel.integrations.hypit import service
    import app as web
    native_load = EaselRuntimeConfig.load
    def config(cls, *args, environ=None, env_file=None, **kwargs):
        values = {'EASEL_MATERIAL_LIBRARY_ROOT': str(tmp_path / 'library')}
        values.update(environ or {})
        return native_load(environ=values, env_file=tmp_path / 'absent.env')
    monkeypatch.setattr(EaselRuntimeConfig, 'load', classmethod(config))
    monkeypatch.setattr(creation, 'OUTPUTS_DIR', tmp_path / 'outputs')
    monkeypatch.setattr(creation, 'CREATIONS_DIR', tmp_path / 'outputs/_creations')
    monkeypatch.setenv('EASEL_HYPIT_HOME', str(tmp_path / 'hypit'))
    monkeypatch.setattr(service, 'workspace_root', lambda: tmp_path / 'hypit')
    monkeypatch.delenv('EASEL_MATERIAL_LOCAL_ROOTS', raising=False)
    monkeypatch.setattr(web, '_hypit_runtime_profile', lambda: None)

    def forbidden(kind):
        def stop(*args, **kwargs):
            trace.blocked.append(kind)
            raise AssertionError('matrix isolation forbids ' + kind)
        return stop
    monkeypatch.setattr(socket.socket, 'connect', forbidden('network connect'))
    monkeypatch.setattr(socket, 'create_connection', forbidden('network connection'))
    monkeypatch.setattr(subprocess, 'Popen', forbidden('external process'))
    monkeypatch.setattr(web, 'run_agent_sync', forbidden('unmocked Gateway/model'))
    monkeypatch.setattr(service, '_cli', forbidden('Hypit CLI'))

    # Prevent accidental live-state reads/writes, including credential paths.
    native_builtin, native_io = builtins.open, io.open
    def guarded(native):
        def open_file(file, *args, **kwargs):
            if isinstance(file, (str, os.PathLike)):
                p = Path(file).absolute()
                if not p.is_relative_to(tmp_path):
                    sensitive = (p.is_relative_to(ROOT / 'outputs') or
                        any(part == '.easel' or part.startswith('.openclaw') for part in p.parts) or
                        p.name == '.env' or p.name.startswith('.env.') and p.name != '.env.example')
                    if sensitive:
                        trace.blocked.append('protected runtime/config path')
                        raise AssertionError('matrix isolation forbids live runtime/config file')
            return native(file, *args, **kwargs)
        return open_file
    monkeypatch.setattr(builtins, 'open', guarded(native_builtin))
    monkeypatch.setattr(io, 'open', guarded(native_io))
    yield
    assert not trace.blocked, 'An unexpected external/live-state operation was attempted'


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    rows = getattr(item.config, '_matrix_results', None)
    if rows is None:
        rows = item.config._matrix_results = {}
    row = rows.setdefault(item.nodeid, {'nodeid': item.nodeid, 'duration_seconds': 0., 'phases': {}})
    row['duration_seconds'] += report.duration
    row['phases'][report.when] = report.outcome
    if report.failed:
        row.setdefault('errors', []).append(str(report.longrepr))
    evidence = getattr(item, 'matrix_trace', None)
    if evidence:
        row.update(expected=evidence.expected, basis=evidence.basis, actual=evidence.events,
                   contract_gaps=evidence.gaps, forbidden_attempts=evidence.blocked)


def pytest_sessionfinish(session, exitstatus):
    output = session.config.getoption('--matrix-output')
    if not output:
        return
    rows = list(getattr(session.config, '_matrix_results', {}).values())
    for row in rows:
        phases = row['phases']
        row['result'] = ('FAIL' if 'failed' in phases.values() else
                         'NOT_EXECUTED' if phases.get('call') != 'passed' else
                         'CONTRACT_GAP' if row.get('contract_gaps') else 'PASS')
    from easel.integrations.hypit.secrets import SecretRedactor
    result = {'schema': 'easel-planning-material-matrix@1', 'pytest_exit_status': int(exitstatus),
              'case_count': len(rows), 'counts': {s: sum(r['result'] == s for r in rows)
                  for s in ('PASS', 'FAIL', 'CONTRACT_GAP', 'NOT_EXECUTED')}, 'cases': rows}
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(SecretRedactor.redact_text(json.dumps(result, ensure_ascii=False, indent=2)) + '\n')
