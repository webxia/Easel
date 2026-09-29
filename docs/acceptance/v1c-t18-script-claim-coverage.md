# V1C-T18 Script Claim Coverage and Review Gate Acceptance

Date: 2026-09-28

## Result

```text
SOFTWARE_ACCEPTED
REAL_WORLD_VERIFIED = NOT_VERIFIED
PAID_CALLS = NONE
LIVE_PROVIDER_CALLS = NONE
P3 = NOT_STARTED
```

## Verified behavior

- `easel/integrations/script_truth.py` emits a versioned claim ledger bound to the exact frozen `SCRIPT.md` and Truth Packet bytes by SHA-256.
- Every non-empty sentence/line review unit is recorded. Only exact user-authored Truth Packet quotes are auto-classified `TRUTH_SUPPORTED`; only explicitly marked fiction is `FICTION_MARKED`. All other text is `REVIEW_REQUIRED`.
- Ledger validation rejects stale hashes, omitted/edited units, invalid automatic promotion, malformed review scope, and review evidence without a timezone-aware timestamp bound to both current hashes.
- The local operator must explicitly confirm review of every unresolved unit. The persisted result is `HUMAN_REVIEWED`, not source-backed truth.
- Creation Preparation stops before Material Supply while review is pending. The Web operator action records review and resumes the existing Preparation path. Production Authoring independently rejects an unresolved ledger.
- T06's frozen Script hash binding is unchanged; no TTS engine, semantic fact service, or new architecture boundary was introduced.

## Test evidence

```text
.venv/bin/python -m pytest -q \
  tests/test_script_truth.py \
  tests/test_material_integration.py \
  tests/test_creation_preparation.py \
  tests/test_material_p0_18_e2e.py \
  tests/test_material_p2_07_hypit_generation_gateway.py

74 passed
```

The API regression also verifies that the protected Script Truth endpoints reject stale hashes, persist an explicit operator disposition, and resume Preparation without passing the Material Gate.

Frontend typecheck and production build:

```text
cd web/frontend && npm run build
PASS (tsc -b + vite build)
```

## Review / limitations

- Review units are deterministic sentence/line segments, not machine-proven semantic propositions. The ledger guarantees text coverage and a human review gate; it does not establish that an assertion is true.
- `HUMAN_REVIEWED` records the local operator's explicit action. It is not legal, editorial, or external-source verification.
- Authenticated Web operation and a fresh Product E2E remain `NOT_VERIFIED`.
- No external OSS implementation was needed or adopted; no external reference supplied a semantic truth guarantee.

## Status

V1C-T18 software acceptance: `SOFTWARE_ACCEPTED`.
V1C-H05 software gate: `CLOSED_FOR_SOFTWARE / REAL_WORLD_PENDING`.
T15 remains gated on the broader branch evidence and current environment readiness.
