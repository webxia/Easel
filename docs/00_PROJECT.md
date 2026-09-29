# Easel Project

## Product Purpose

Easel is a long-term, Creator-centered AI creative workspace. It turns a Creator's ideas, learning, practice, and lived experience into traceable and reviewable creative work.

## Current Product Goal

The current development focus is video. The first objective is:

> **One Creator / Profile + one Director / Creative Mode + different Content inputs → stable videos with a recognizable, consistent creative style.**

Creator identity and directing language should remain recognizable while each work's subject, point of view, and story remain open. This is a product goal, not a claim that the full production loop is already implemented; see [Current State](02_CURRENT_STATE.md).

## Official New Video Mainline

`Creation + Hypit` is the only official new video-production mainline:

```text
Web Creation / explicit confirmation
-> Preparation / frozen Content + Creator Context + Creative Mode
-> Creative Planning / MaterialPlan
-> Material Supply / MaterialReadiness Gate
-> Production Authoring / Hypit Authoring
-> Hypit Runtime / Plan / Pricing / Approval / Build
-> Easel review / export / selected output
```

Material Resolution is connected in software. A required Need without an accessible, inspected, rights-admitted asset stops at `MATERIAL_NOT_READY`; this does not by itself claim real-world Product E2E verification. See [Current State](02_CURRENT_STATE.md).

## Core Principles

- Creator identity and truth boundaries are stable; Content and story remain open.
- The Director decides what and how to express. Creative Mode constrains the work's expressive language, not its subject or story.
- A Creation is a traceable work instance, not an Agent or a fixed production template.
- Completion requires a real artifact and the evidence required by its route.
- Paid execution, publication, and other external side effects remain behind explicit gates.
- Domain concepts such as Creator, Director, and Content do not by themselves require dedicated V1 entities or tables.

## Responsibility Boundaries

| Owner | Responsibility |
|---|---|
| Easel | Creator/Profile and effective context, Content truth boundary, Creation/Attempt workflow, confirmation, review, selected output, export/readiness |
| OpenClaw | Current AI Authoring executor for the Easel-owned workflow; does not choose or own the official route |
| Hypit | Local film production contract, media admission, editing/timeline/audio/composition, validation, production Runtime/Plan/Pricing/Build, and final film result; no AI material generation |
| Material Layer | MaterialPlan-driven discovery, acquisition and AI asset generation, inspection, provenance, rights admission, matching, and MaterialBundle supply; no directing, timeline, or production authority |
| Providers | Replaceable capabilities below the Material Layer; not owners of Creation or workflow state |

## Long-Term Directions Outside Current V1

Knowledge Flywheel, multiple Directors, text/image-post outputs, and broader publishing or social-media operations may be considered later. They are not current implemented capabilities or current V1 work.

## Success Criteria

- A work can be traced from user input through Creation, Attempts, artifacts, and review.
- The official flow preserves Creator truth boundaries and a reproducible Creative Mode snapshot.
- Material Resolution satisfies declared needs without rewriting the authored intent.
- Build, technical QC, creative review, selected output, Creation readiness, and publication readiness remain distinct and evidence-based.
- Project documentation lets future work recover goals, architecture, current implementation, and constraints without relying on chat history.
