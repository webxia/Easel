# ADR-001 Creation + Hypit Mainline

Status: Accepted

## Context

Easel has existing topic-to-video Skills and a newer Creation + Hypit integration. Multiple paths being treated as equal mainlines makes ownership, state, and delivery expectations unclear.

## Decision

Creation + Hypit is the only new video-production mainline. `auto-short-video` and `video-production` remain legacy paths and do not receive new mainline architecture unless an explicitly scoped Task requires it.

## Consequences

New video work should attach to the Creation lifecycle and Hypit boundary. Legacy behavior remains available but must be labeled and evaluated separately; this decision does not claim that the mainline is fully end-to-end verified.
