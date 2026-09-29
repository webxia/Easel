# V1C-T02 Acceptance — Need-to-Selection Qualification Integrity

Date: 2026-09-27

## Result

**SOFTWARE_ACCEPTED**. The deterministic selection gates pass. No new real Web Creation or paid Hypit operation was run, so real-world verification remains `NOT_VERIFIED`.

## Behavior Accepted

- Production may choose among supplied assets, but every selected asset must have a current qualified Need↔Asset match, passed technical inspection, and admitted Rights for the matched Need.
- The selection manifest is bound to Creation, Attempt, current MaterialPlan, Bundle, readiness revisions, and the actual SVML author source.
- Validation checks actual bytes against the admitted SHA-256 and size, media type/MIME, relative workspace locator, SVML reference, and absence of unselected Bundle assets in the authored source.
- The server derives `qualified_need_ids`; agent-authored qualification assertions are not accepted as authority.
- After successful validation, the manifest digest and selected asset IDs are persisted. Subsequent Hypit check/build validation rejects a changed manifest, Asset bytes, stale revisions, or selection mismatch.
- The authoring default follows the formal OpenClaw path: `productions/easel-authoring/authors/main.svml`.

## Test Evidence

Command:

```text
.venv/bin/python -m pytest -q tests/test_material_integration.py tests/test_creation_preparation.py tests/test_hypit_integration.py
```

Result: **61 passed**, 2 dependency deprecation warnings.

Coverage includes valid selection, an Asset with no qualified match, wrong Attempt/revisions, selection-manifest mutation after validation, Bundle membership, asset byte/hash verification, SVML source references, and Hypit integration preconditions.

## Hypit Contract Review

The installed Hypit CLI reports v0.2.7. Its installed distribution declares ordinary `media:Image`, `media:Video`, and `media:Audio` resources with workspace-relative `src`; Run compilation resolves its declared author source relative to the Run. Hypit's separate `build-record` resolution remains outside the ordinary MaterialAsset route. Easel continues to own Material qualification and Attempt asset evidence; Hypit continues to own Production execution.

## Limitations

This is software acceptance only. The changed selection gates have not yet been re-verified in a new real Web Creation. No external Provider, paid generation, Hypit Plan/Pricing/Build, or P3 activity was performed.
