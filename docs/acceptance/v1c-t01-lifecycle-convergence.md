# V1C-T01 Acceptance — Creation and Attempt Lifecycle Convergence

Date: 2026-09-27

## Result

**SOFTWARE_ACCEPTED**. No new real-world product run was performed in this Task, so the revised projection remains `NOT_VERIFIED` on a new live Creation after this change.

## Changes

- Official `hypit_video` Creations now derive the coarse `Creation.status` from persisted Preparation, Material Gate, Hypit Attempt, review, and selection facts rather than legacy stage-only completion.
- A blocked Material Gate projects to Creation `not_ready` and Attempt `MATERIAL_NOT_READY`; it cannot appear as `READY_FOR_EXTERNAL_AUTHORING` in the Attempt summary.
- Creation is `ready` only when an approved Attempt output is selected and `READY_FOR_MANUAL_PUBLISH` is persisted. Revoking review returns the Creation to `producing` and clears stale selection through existing review logic.
- All Hypit Attempt mutation paths recompute the Attempt summary before persisting. Material integration now uses the shared locked Attempt update path, preserving Creation/Attempt atomicity and recording a lifecycle event.
- `select_film_attempt()` returns the Creation after the edit lock commits, rather than its stale in-lock snapshot.

## Test Evidence

Command:

```text
.venv/bin/python -m pytest -q tests/test_creation_preparation.py tests/test_hypit_integration.py tests/test_material_integration.py
```

Result: **58 passed**, 2 dependency deprecation warnings.

Coverage includes a required Need blocked by Material Gate, Attempt summary projection, full mocked Hypit Build → Export → Review → Selected Output projection, and revocation of a previously selected output.

## Architecture Check

- Creation and Attempt identities remain distinct.
- `Creation.status` is a coarse product summary; detailed execution remains on the Attempt.
- `READY_FOR_MANUAL_PUBLISH` remains a publication metadata state and does not imply automatic publishing.
- No Material V1.3 semantic or Hypit ownership change was made.

## Remaining Evidence

A new official real Web Creation after this change is still required to mark the changed lifecycle projection `REAL_WORLD_VERIFIED`. No paid Build or external call was used here.
