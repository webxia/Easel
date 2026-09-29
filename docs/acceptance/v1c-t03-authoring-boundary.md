# V1C-T03 Acceptance — OpenClaw Authoring Capability Boundary

Date: 2026-09-27

## Result

**SOFTWARE ACCEPTED / REAL-WORLD VERIFICATION PENDING**. No OpenClaw model inference or Web Authoring turn was run.

## Evidence

- `web/app.py::_run_film_authoring()` dispatches `run_attempt_scoped_authoring()` instead of shared Agent `main`.
- `easel/integrations/openclaw_authoring.py` stages frozen inputs into a transient workspace, adds a random profile Agent with `minimal` plus the exact `read`/`write`/`edit` allowlist and `fs.workspaceOnly=true`, disables elevated access, and denies runtime/network/UI/media/plugin/session/agent groups.
- Easel promotes only three regular UTF-8 files from the isolated workspace: selection manifest, SVML author source, and SVRun. Symlink inputs/outputs fail closed. The normal `complete_film_authoring()` path then validates selection and invokes Hypit `check` outside the Agent.
- Tests assert tool allow/deny, workspace staging and message rebasing, no asset-byte copy, symlink rejection, output allowlist, transient config cleanup, and unchanged existing Hypit validation.
- OpenClaw 2026.9.4 accepted the generated per-agent config through `config patch` and `config validate` in an isolated temporary HOME. No live Easel OpenClaw profile was mutated for this contract check.

## Acceptance Check

Targeted tests: `.venv/bin/python -m pytest -q tests/test_openclaw_authoring_boundary.py tests/test_material_integration.py tests/test_hypit_integration.py` — 44 passed. `compileall` passed. No paid operation, Provider call, model inference, or real Web turn was run.

## Remaining Blocker

Remaining verification: run a named real Web Authoring turn to confirm OpenClaw Gateway reloads the transient policy before dispatch and the production model can author through the restricted file tools. This is a real-world verification gap, not a known software permission blocker. No claim of real-world verification is made.
