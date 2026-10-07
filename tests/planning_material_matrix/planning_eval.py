"""R4 evaluation-only stop boundary; no product changes or synthetic Gate.

The source fingerprint and this adapter must be frozen before real calls.
Python tracing executes the native orchestrator up to its Supply import, then
unwinds to the evaluation callback. It does not call or replace Supply.run.
"""
from __future__ import annotations

import ast
import asyncio
import hashlib
import inspect
import json
from pathlib import Path
import sys
import threading
from contextlib import contextmanager
import os
import shlex
import time

from easel import creation
from easel.creation_delivery import advance_creation, next_operation
from easel.integrations.material_layer import MaterialProductOrchestrator, PlanningIntegration


class EvalBoundaryReached(Exception):
    """Evaluation endpoint reached, never a product success/status."""


class EvalStateViolation(Exception):
    pass


class PlanningEvalBoundary:
    def __init__(self, before_stage=None):
        self.code = MaterialProductOrchestrator._run.__code__
        source, first = inspect.getsourcelines(MaterialProductOrchestrator._run)
        import textwrap
        tree = ast.parse(textwrap.dedent(''.join(source)))
        imports = [n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
                   and n.module == 'easel.integrations.material_supply']
        if len(imports) != 1:
            raise EvalStateViolation('Supply boundary changed; evaluation adapter needs review')
        self.stop_line = first + imports[0].lineno - 1
        self.supply_calls = 0
        self.state_violations = []
        self.cuts = []
        self.before_stage = before_stage
        self.phase_calls = []

    def trace(self, frame, event, arg):
        module = frame.f_globals.get('__name__', '')
        name = frame.f_code.co_name
        if event == 'call':
            if module == 'app' and name == '_run_timed_creation_agent':
                row = {k: frame.f_locals.get(k) for k in ('phase', 'attempt_id', 'session_id', 'timeout')}
                row['started_monotonic'] = time.monotonic()
                row['message_sha256'] = hashlib.sha256(frame.f_locals['message'].encode()).hexdigest()
                if self.before_stage:
                    self.before_stage(row)
                self.phase_calls.append(row)
            forbidden = (module.startswith(('easel.integrations.material_supply',
                         'easel.integrations.material_generation',
                         'easel.integrations.material_recovery'))
                         or module.startswith('easel.materials.providers')
                         and name in {'search', 'acquire', 'generate', 'synthesize'}
                         or module == 'easel.integrations.hypit.service' and name == '_cli')
            if forbidden:
                if module.startswith('easel.integrations.material_supply'):
                    self.supply_calls += 1
                self.state_violations.append(module + ':' + name)
                raise EvalStateViolation('Forbidden downstream entry: ' + module + ':' + name)
            return self.trace if frame.f_code is self.code else None
        if event == 'line' and frame.f_code is self.code and frame.f_lineno == self.stop_line:
            planning = frame.f_locals['planning']
            attempt = planning['attempt']
            # Native persist has already happened. Native load independently
            # rechecks manifest, frozen source, semantic checkpoint and sidecar.
            loaded = PlanningIntegration().load(attempt)
            if loaded['truth_ledger']['status'] != 'PASSED':
                raise EvalStateViolation('PLANNING_READY without PASSED Truth is not Eval success')
            if loaded['plan'] != planning['plan'] or loaded['plan'].context_refs != planning['plan'].context_refs:
                raise EvalStateViolation('Native reloaded Planning differs from the persisted contract')
            if attempt.get('material_gate', {}).get('status') == 'MATERIAL_READY':
                raise EvalStateViolation('Eval cannot reuse an existing material result')
            self.cuts.append({'attempt_id': attempt['attempt_id'],
                              'plan_id': loaded['plan'].plan_id,
                              'truth_status': loaded['truth_ledger']['status'],
                              'boundary_file': str(Path(self.code.co_filename).resolve()),
                              'boundary_line': self.stop_line,
                              'planning': loaded})
            raise EvalBoundaryReached()
        return self.trace

    @contextmanager
    def guarded(self):
        previous, previous_threads = sys.gettrace(), threading.gettrace()
        if previous or previous_threads:
            raise EvalStateViolation('Evaluation must run in its own process without another trace hook')
        sys.settrace(self.trace)
        threading.settrace(self.trace)
        native_to_thread = asyncio.to_thread
        async def traced_to_thread(function, /, *args, **kwargs):
            # An executor may reuse a thread whose trace was cleared when the
            # previous endpoint exception unwound. Reinstall for each native
            # to_thread invocation, retaining ContextVar propagation.
            def invoke():
                old = sys.gettrace()
                sys.settrace(self.trace)
                try:
                    return function(*args, **kwargs)
                finally:
                    sys.settrace(old)
            return await native_to_thread(invoke)
        asyncio.to_thread = traced_to_thread
        try:
            yield self
        finally:
            asyncio.to_thread = native_to_thread
            sys.settrace(previous)
            threading.settrace(previous_threads)

    async def advance(self, creation_id, web):
        async def execute(operation, work):
            if operation not in {'prepare', 'observe_agent'}:
                self.state_violations.append('Delivery:' + str(operation))
                raise EvalStateViolation('Eval forbids this Delivery operation')
            try:
                await web._execute_creation_delivery(operation, work)
            except EvalBoundaryReached:
                # Native Owner records a completed invocation. No Preparation,
                # Plan, Truth or Gate value is edited by the adapter.
                return
        before = len(self.cuts)
        with self.guarded():
            advanced = await advance_creation(creation_id, execute)
        current = creation.get_creation(creation_id)
        operation, status = next_operation(current)
        return {'owner_advanced': advanced, 'boundary_reached': len(self.cuts) > before,
                'native_next_operation': operation, 'native_delivery_status': status,
                'next_substage': 'MaterialProductOrchestrator Supply entry' if len(self.cuts) > before else None,
                'supply_calls': self.supply_calls, 'state_violations': list(self.state_violations)}


def confirm_sample(sample):
    """Normal Creation begin/save/confirm; independent controlled input."""
    proposal = sample['proposal']
    work = creation.create_creation(sample['theme'], profile='个人经营实践',
        creative_mode='clear_memo_video', route='hypit_video',
        origin={'type': 'chat', 'session_hash': hashlib.sha256(proposal.encode()).hexdigest()})
    turn = 'r4-proposal-' + sample['id']
    creation.begin_video_proposal(work['id'], turn)
    creation.save_video_proposal(work['id'], turn, proposal)
    plan = creation.get_creation(work['id'])['chat_workflow'].get('video_plan')
    if not plan or any(v is None for v in plan['specs'].values()):
        raise EvalStateViolation('Frozen sample is not a legal normal proposal: ' + sample['id'])
    transcript = json.dumps([{'role': 'user', 'content': sample['theme']},
                             {'role': 'assistant', 'content': proposal},
                             {'role': 'user', 'content': '确认此方案。只做 Planning Eval，不执行素材供给或制作。'}], ensure_ascii=False)
    return creation.confirm_chat_proposal(work['id'], 'r4-confirm-' + sample['id'],
        video_plan_sha256=plan['sha256'], production_specs=plan['specs'],
        delivery_proposal=transcript,
        proposal_sha256=hashlib.sha256(transcript.encode()).hexdigest())


@contextmanager
def isolated_process(root, web):
    """Same modules in a separate eval process/root, never production Owner.

    The model's normal read-only validate-draft command must see the same
    isolated Creation root as its caller. The evaluation-only sitecustomize
    applies that root to the validation child; no schema or semantic prompt is
    changed. This is storage routing, not an OS sandbox for the remote Agent.
    """
    from easel import creation_preparation
    root = Path(root).resolve()
    if root == creation.PROJECT_ROOT or creation.PROJECT_ROOT in root.parents:
        raise EvalStateViolation('Eval writable root must be outside the project')
    bootstrap = root / 'validator-bootstrap'
    bootstrap.mkdir(parents=True, exist_ok=True, mode=0o700)
    (bootstrap / 'sitecustomize.py').write_text(
        'import os\nfrom pathlib import Path\nfrom easel import creation\n'
        'r = Path(os.environ["EASEL_PLANNING_EVAL_ROOT"]).resolve()\n'
        'creation.OUTPUTS_DIR = r / "outputs"\n'
        'creation.CREATIONS_DIR = r / "outputs/_creations"\n'
        'os.environ["EASEL_HYPIT_HOME"] = str(r / "hypit")\n')
    (bootstrap / 'sitecustomize.py').chmod(0o600)
    original_dirs = creation.OUTPUTS_DIR, creation.CREATIONS_DIR
    old_home = os.environ.get('EASEL_HYPIT_HOME')
    native = web.preparation_agent_context
    def context(work, preparation):
        message = native(work, preparation)
        prefix = ('PYTHONPATH=' + shlex.quote(str(bootstrap) + os.pathsep + str(creation.PROJECT_ROOT))
                  + ' EASEL_PLANNING_EVAL_ROOT=' + shlex.quote(str(root)) + ' ')
        return message.replace('.venv/bin/python -m easel.creation_preparation --validate-draft ',
                               prefix + '.venv/bin/python -m easel.creation_preparation --validate-draft ')
    creation.OUTPUTS_DIR, creation.CREATIONS_DIR = root / 'outputs', root / 'outputs/_creations'
    os.environ['EASEL_HYPIT_HOME'] = str(root / 'hypit')
    web.preparation_agent_context = context
    try:
        yield
    finally:
        creation.OUTPUTS_DIR, creation.CREATIONS_DIR = original_dirs
        web.preparation_agent_context = native
        if old_home is None:
            os.environ.pop('EASEL_HYPIT_HOME', None)
        else:
            os.environ['EASEL_HYPIT_HOME'] = old_home
