# V1C-T04 Acceptance — Pricing Uncertainty and Approval Semantics

Date: 2026-09-27

## Result

**SOFTWARE_ACCEPTED**. No live Hypit Pricing or paid Build was run. Real-world verification of the changed persistence/approval presentation remains `NOT_VERIFIED`.

## Hypit v0.2.7 Contract

The installed CLI reports v0.2.7. Its `packages/cli/src/output.ts` `PricingOutput` for `hypit.cli-pricing@1` contains the Run, request counts, no-charge request count and Provider pricing groups. It does not expose a verifiable aggregate total. Easel therefore preserves the redacted Provider payload, leaves `estimated_usd` null and `total.status=unknown`, and says the operator-approved amount is not a hard cap enforced by Hypit or a Provider.

## Approval Binding

- Successful Plan and Pricing responses are canonicalized and hashed as JSON contracts.
- Persistent operator approval records the source/runtime execution fingerprint plus the exact Plan and Pricing response hashes.
- Approval fails closed when stored Plan/Pricing evidence changes.
- Build rechecks all three bindings under the Attempt persistence lock before creating the idempotent submission operation. A stale contract invalidates approval and results in no Build call.
- Hypit pricing is not recalculated or summed by Easel.

## Test Evidence

Command:

```text
.venv/bin/python -m pytest -q tests/test_hypit_integration.py
```

Result: **27 passed**, 2 dependency deprecation warnings.

Fixture cases include an aggregate-like response field, provider components, empty details and malformed total-like data. In every case the total remains unknown. Additional regressions mutate Plan or Pricing after approval and verify the Build adapter is not called.

## Limitations

Software acceptance does not establish a real quote, enforceable spend ceiling, provider invoice amount or live Build. No paid operation was performed.
