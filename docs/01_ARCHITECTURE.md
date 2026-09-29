# Easel Architecture Router

This page names architecture authority. It intentionally contains no duplicated implementation status; see [`02_CURRENT_STATE.md`](02_CURRENT_STATE.md).

## Authorities

| Concern | Authority | Status / use |
|---|---|---|
| Product purpose | [`00_PROJECT.md`](00_PROJECT.md) | Stable product intent and owner boundaries. |
| Video target | [`architecture/easel-video-architecture-v1.md`](architecture/easel-video-architecture-v1.md) | CURRENT target architecture; not implementation proof. Its Material details are superseded by V1.3. |
| New video mainline | [`decisions/ADR-001-creation-hypit-mainline.md`](decisions/ADR-001-creation-hypit-mainline.md) | Accepted: Creation + Hypit is the only new video mainline. |
| Material Layer | [`architecture/material-layer-v1.3.md`](architecture/material-layer-v1.3.md) + [`ADR-004`](decisions/ADR-004-material-layer-v1.3-baseline.md) | Sole current, frozen Material architecture authority. |
| Current implementation path | [`02_CURRENT_STATE.md`](02_CURRENT_STATE.md) + source/tests | Current behavior and verification evidence; not target architecture. |

## Ownership Summary

| Owner | Responsibility |
|---|---|
| Easel | Product workflow, Creation/Attempt state, frozen Creator/Content/Creative Mode context, approval and review. |
| OpenClaw | Creative Planning and Production Authoring within Easel's workflow. |
| Material Layer | Need-driven supply, provenance, inspection, Rights admission, matching and bundle/readiness facts. |
| Hypit | Production contract, Runtime, Plan/Pricing, Build and result. |
| Providers | External stock sources are consumed under Material Layer; future AI generation providers also belong to Material adapters, not Hypit Production. |

## Conflict Rule

Source and tests establish what the current code does, not what the architecture permits. Accepted ADRs and frozen architecture establish design boundaries. If the two disagree, record the deviation and stop before implementing a boundary change. Consult [`DOCUMENT_INDEX.md`](DOCUMENT_INDEX.md) for task-specific architecture and historical evidence.
