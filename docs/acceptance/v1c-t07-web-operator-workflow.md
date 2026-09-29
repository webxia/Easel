# V1C-T07 Web Operator Workflow Acceptance

Date: 2026-09-27

> 历史范围说明：本文记录的 Hypit Generation prepare/submit/reconcile/collect 页面边界已被 Material Layer 的 MiniMax 生成入口取代，不代表当前 UI/API 链。Creation、Hypit Production 审批/Build/导出/审片链的证据仍可参考；当前状态见 [02_CURRENT_STATE](../02_CURRENT_STATE.md)。

## Result

~~~text
SOFTWARE_ACCEPTED
REAL_WORLD_VERIFIED = NOT_VERIFIED
PAID_BUILD = NOT_RUN
~~~

T07 adds a first-party operator page to the existing Easel Web application. It
uses existing Creation and Hypit Attempt APIs; it does not create an alternate
workflow or replace server-side authorization and execution gates.

## Connected UI Operations

- Select an existing Creation and load its Attempts with the existing local
  Operator bearer API. Creation and Attempt state, MaterialPlan, Material
  Readiness/blocking gaps, errors, generation status, Plan/Pricing/approval,
  Build, Export, Review, attribution and Selected Output status are visible.
- Runtime resolution, Hypit check+plan, pricing, persistent cost approval,
  Build submit/status/inspect/cancel/reconciliation, output export and review,
  and Selected Output all call the corresponding existing FastAPI endpoints.
- Historical T07 version: Generation prepare, approval/submit, reconciliation
  and collection called the then-existing Hypit Generation endpoints. This
  route is superseded and is not the current MiniMax Material UI contract.
- Run controls are presented from persisted Attempt state. Back-end checks
  remain authoritative; stale, blocked, unauthorized or invalid transitions
  surface the API error. Unknown pricing is presented with the existing
  no-hard-spend-cap warning.
- Exported videos can be previewed before review. Changing the selected output
  resets the local review controls. Selection is available only after the
  Attempt reports an approved Review; the page states that selection does not
  publish.
- Operator Token is held only in component memory and sent as an Authorization
  header. It is not written to browser storage, URL, or application data.
- A Creation without an Attempt directs the operator back to the official
  Creation preparation flow; the page does not fabricate a Handoff or Attempt.

## Verification

- `.venv/bin/python -m pytest tests/test_hypit_integration.py -q`: 28 passed.
  The operator-auth test covers the list/read, Generation, Runtime, validation,
  pricing, approval, build/reconciliation, export/review and select endpoints;
  missing token is rejected and an invalid token receives 401.
- `.venv/bin/python -m pytest -q`: 485 passed, 5 skipped.
- `npm run build` in `web/frontend`: TypeScript compilation and Vite production
  build passed.
- Local Web smoke: the FastAPI-served production frontend returned HTTP 200,
  loaded its JS/CSS bundles, and rendered the new “视频制作” navigation entry.
  No protected operator action was submitted from the browser.
- No Generation submission, Provider request, Plan/Pricing execution, Hypit
  Build, Export, Review, or publish action was triggered by this acceptance.

## Contract Review

- Reviewed the current Easel React request helper and Creation/Attempt API
  contracts, FastAPI operator endpoints, and the Hypit service transition and
  response fields used by those endpoints.
- Adopted the existing API and status model, bearer authorization, persisted
  approval/reconciliation, and backend-owned state transitions.
- Rejected a frontend-owned workflow/state machine, browser-persisted Operator
  credential, direct Hypit CLI path, automatic approval, and automatic publish.
- No external OSS implementation or code was copied; the change is an Easel UI
  over existing contracts.

## Remaining Evidence

- A named browser session still needs to operate the UI across an authenticated
  Attempt, including blocked/denied actions, with a real configured Operator.
- Real OpenClaw, Runtime/model capability, Build, Export, Review and Selected
  Output remain separate runtime/product validations. This acceptance does not
  promote any of them to `REAL_WORLD_VERIFIED`.

V1C-T07 is software accepted. The full V1 Product E2E and V1 Release remain
`NOT_READY`; V1C-T08 is the next software task.
