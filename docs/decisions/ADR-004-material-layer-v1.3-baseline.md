# ADR-004 Material Layer V1.3 Development Baseline

Status: Accepted

2026-09-28 clarification authorized by the user: AI asset generation belongs to Material Layer; Hypit is the local video editing and rendering engine. The older Hypit Generation Gateway route in V1.3 is superseded by this clarification. AI generation implementation is a later phase.

2026-09-28 implementation clarification: MiniMax Video Generation V2 was the first remote Material AI generation adapter; the current integration also covers Image-01 and preset-voice T2A. Each potentially billable request requires operator confirmation. This adds replaceable Provider adapters without changing frozen Material Layer ownership, Rights, or Readiness semantics. Current code and live-evidence status are tracked in [`02_CURRENT_STATE.md`](../02_CURRENT_STATE.md) and the generated-material Workstream.

## Context

The previous V0.1 material-layer proposal coupled resolution to Hypit Binding and an older MATERIAL_READY contract. The V1.3 architecture was audited against current Easel code and Hypit v0.2.7 and approved as the development baseline. Easel currently has no connected Material Layer implementation.

## Decision

Adopt [Material Layer V1.3](../architecture/material-layer-v1.3.md) as the sole current Material Layer architecture authority.

- Material Layer owns MaterialPlan-driven supply, AI asset generation, provenance, rights facts/admission, technical inspection, matching, and MaterialBundle. Concrete model runtimes sit behind Material adapters.
- Hypit Production owns media admission contracts, normalization, final production authoring semantics, timeline/track placement, composition, editing/rendering runtime, plan, pricing, build, and final film result. It does not execute Material AI generation.
- The lifecycle gates are distinct: PLANNING_READY validates SCRIPT/SCENES/MaterialPlan; MATERIAL_READY validates current qualified supply for required Needs; AUTHORING_READY means final SVML/SVRun passes hypit check.
- Ordinary Attempt-local media enters Hypit through supported media contracts; the old universal Hypit Binding model is not restored.
- V0.1 Material Layer documents, material-specific ADRs, and Phase 1 tasks are superseded historical records and are not compatibility constraints.
- Work starts with P0 Standalone. Product Integration follows accepted standalone evidence; P1/P2/P3 remain planned until separately started.

## Consequences

- V1.3 and its scoped tasks are the current design and implementation authority.
- This architecture decision does not itself assert implementation or real-world acceptance; consult current state and named Acceptance evidence for those claims.
- P0 must not create Timeline, Track, final placement, normalization, or Build behavior.
- Historical V0.1 records remain available for context but must be classified as LEGACY / SUPERSEDED.
