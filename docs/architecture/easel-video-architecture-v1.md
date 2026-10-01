# Easel Video Architecture V1.1

> **Document Status:** CURRENT
> **Architecture Status:** TARGET / DESIGNED
> **Implementation Status:** See [`docs/02_CURRENT_STATE.md`](../02_CURRENT_STATE.md)
> **Scope:** Video creation only
> **Official New Video Mainline:** Creation + Hypit
>
> This document defines the agreed target architecture for Easel's current video direction.
> It incorporates the verified local-reality audit and intentionally avoids forcing unnecessary entity or storage refactors.
>
> This document is an authoritative **Target Architecture baseline**, not proof that every capability is implemented.
>
> **Material Layer Authority:** V1.3 is the APPROVED / DEVELOPMENT BASELINE. Dynamic implementation and verification status is maintained in [`docs/02_CURRENT_STATE.md`](../02_CURRENT_STATE.md). All Material Layer design details in this V1.1 document are superseded by [Material Layer V1.3](material-layer-v1.3.md); the broader Easel video target and non-material boundaries remain current.

---

# 1. Project Positioning

Easel is a long-term AI creative workspace centered on the **Creator**.

Its long-term purpose is:

> Maintain a stable Creator Identity and Director System so changing content can continuously become coherent, traceable, reviewable creative work.

The current development focus is intentionally narrower:

> **Video creation first.**

The first-stage objective is:

> **One Creator / Profile + one Director / Creative Mode + many different Content inputs → consistently produce videos with a recognizable and stable creative style.**

The current system should optimize for this goal before expanding into knowledge flywheels, multiple directors, text production, publishing, or broader social-media operations.

---

# 2. Current Strategic Goal

The immediate objective is to turn the Creator's:

```text
learning
practice
investment thinking
work experience
personal reflection
life insight
```

into repeatable video creation.

The current Phase 1 loop is:

```text
Idea / Learning / Reflection
        ↓
      Content
        ↓
     Creation
        ↓
 Video Production
        ↓
 Stable Video Output
```

Future evolution may become:

```text
Phase 2
Learning / Practice / Reflection
↓
Reusable Knowledge
↓
Content
↓
Video
↓
Reflection
↓
Learning Flywheel

Phase 3
One Creator
↓
Multiple Stable Directors
↓
Multiple Video Series / Styles
```

But V1 only focuses on **Phase 1**.

---

# 3. Core Product Principle

The current product relationship is:

```text
Creator / Profile
        +
Director / Creative Mode
        +
      Content
        ↓
      Creation
        ↓
 Stable Video Output
```

The core meaning is:

```text
Creator
= Who is expressing

Content
= What is being expressed

Director
= How it is expressed
```

For V1:

```text
Creator = stable
Director = stable
Content = changes
```

The expected result is:

> Different topics still feel like they were created by the same person under the same directing system.

Consistency should primarily appear in:

```text
narrative voice
information density
opening structure
visual language
material preference
voice
typography
pacing
transitions
music / sound tone
overall emotional and directing style
```

The goal is not identical videos.

The goal is:

> Content changes while Creator identity and directing language remain recognizable.

---

# 4. Core Domain Concepts

The current video architecture uses these core concepts:

```text
Creator
Profile
Content
Director
Creative Mode
Creation
Attempt
Material
Video Output
```

Important:

> Not every domain concept must become a dedicated persistent entity in V1.

V1 should prefer the smallest implementation that preserves correct semantics, reproducibility, and lifecycle boundaries.

---

# 5. Creator

A **Creator** is the long-lived creative subject.

Conceptually, Creator is the owner of:

```text
identity
experience
creative preferences
views
creative history
```

For current V1:

> **Creator is a product/domain concept and does not require a separate Creator database entity or CRUD model.**

The current executable representation may remain:

```text
Profile
+
Creator Context
```

until multi-Creator use cases actually require stronger entity modeling.

---

# 6. Profile and Effective Creator Context

A **Profile** is Easel's stored understanding of the Creator.

It may include:

```text
background
areas of interest
target audience
expression habits
language style
creative preferences
constraints
things to avoid
```

However, the V1 reproducibility requirement is not:

> "Copy the entire Profile file into every Creation."

The real requirement is:

> **Freeze the effective Creator Context actually used by this Creation.**

A Creation should preserve enough information to reproduce the Creator context used at production time.

Recommended provenance:

```text
profile identity / name
profile version or hash when available
effective Creator Context snapshot
source/provenance information
```

If the effective Creator Context is already frozen and validated, a redundant full-file snapshot is not mandatory.

---

# 7. Content

**Content** answers:

> What is this video trying to express?

Typical sources:

```text
AI learning
investment reflection
work experience
personal insight
life reflection
direct topic input
```

For V1:

> **Content is a domain concept, but does not need to become a separate persistent entity.**

The current implementation may represent the frozen content boundary through structures such as:

```text
Content Core
Truth Packet
Preparation artifacts
Handoff artifacts
```

provided they are validated, frozen, and traceable.

---

# 8. Director

A **Director** is a stable system of creative judgment.

It controls:

```text
narrative approach
pacing
shot language
visual taste
emotion
sound direction
subtitle system
transitions
material preference
information density
opening style
ending style
```

For V1:

> **Director is a product/domain concept and does not require a separate Director entity.**

The current executable directing system may be expressed through:

```text
Creative Mode
+
Authoring rules
+
Authoring prompt / skill
+
AI authoring execution
```

The requirement is not "create Director CRUD."

The requirement is:

> Make the directing behavior stable, versionable enough, and reproducible.

---

# 9. Creative Mode

A **Creative Mode** is the main executable configuration of a Director.

Conceptually:

```text
Director
   ↓
Creative Mode
├── narrative rules
├── visual rules
├── pacing rules
├── typography rules
├── material policy
├── audio direction
├── editing rules
└── constraints
```

Current V1 focus:

```text
one Creator
+
one primary Director
+
one primary Creative Mode
```

Creative Mode should remain snapshot/hash protected for a Creation / Attempt.

This capability already aligns well with the target architecture and should be preserved rather than redesigned.

---

# 10. Creation

A **Creation** is one long-lived video creation instance.

It represents:

```text
Creator Context
+
Content
+
Director / Creative Mode
+
Video Intent
```

Creation belongs to Easel.

Creation owns:

```text
high-level product lifecycle
user confirmation
production identity
final review outcome
final selected output
```

Creation does not need to own low-level Hypit timeline data.

---

# 11. Attempt

An **Attempt** is one concrete production attempt for a Creation.

Conceptually:

```text
Creation
├── Attempt 1
├── Attempt 2
└── Attempt 3
```

The semantic distinction between Creation and Attempt is mandatory.

However:

> **V1 does not require Attempt to be moved into a separate database table or storage system solely for architectural purity.**

The current embedded storage model can remain if it already provides:

```text
Attempt ID
Attempt number
isolated workspace
Attempt state
Attempt artifacts
Attempt build/review evidence
```

Physical storage separation should only be introduced when real concurrency, scale, transaction, locking, or query needs justify it.

---

# 12. Material

Material is a concrete media resource used to satisfy a resource requirement declared during Authoring.

Examples:

```text
stock video
generated video
image
voice
music
sound effect
local media
```

Material must not redefine directing intent.

Its purpose is:

> satisfy an already-declared media need.

---

# 13. Video Output

A **Video Output** is a produced video artifact associated with an Attempt.

The final selected video should remain traceable to:

```text
Creation ID
Attempt ID
Creator Context snapshot
Creative Mode snapshot/hash
Material Manifest
Build Result
Technical validation
Review result
selected output
final MP4
```

A dedicated `final_output_id` field is optional in V1 if the current combination of:

```text
selected output name
path
sha256
Attempt ID
```

already provides stable identity.

The semantic requirement matters more than the field name.

---

# 14. Official New Video Mainline

The official new video production mainline is:

```text
Content Input
↓
Easel Proposal
↓
User Confirmation
↓
Creation Preparation
↓
Handoff
↓
Hypit Attempt
↓
Authoring Stage
↓
Material Resolution
↓
MATERIAL_READY
↓
Hypit Runtime / Plan / Approval
↓
Hypit Build
↓
Export / Technical QC
↓
Creative Review
↓
Selected Approved Output
↓
Creation READY
```

This is the target production line for all new official video work.

---

# 15. Current Local Reality of the Mainline

> This section is the source architecture's local-audit snapshot, not a substitute for current implementation evidence. For the repository's maintained status, use [`docs/02_CURRENT_STATE.md`](../02_CURRENT_STATE.md) and verify against source.

The verified current local architecture already contains most of the skeleton:

```text
ai-film
↓
Creation(route=hypit_video)
↓
Proposal discussion
↓
User confirmation
↓
Preparation
↓
Content Core / Truth Packet / Creator Context
↓
snapshot / Handoff
↓
Hypit Attempt / isolated workspace
↓
OpenClaw main Agent + hypit-authoring Skill
↓
Treatment / Script / Scenes / SVML / SVRun
↓
hypit check
↓
AUTHORING_READY
↓
[Material Resolution missing]
↓
Runtime resolve
↓
validate/check + plan
↓
pricing + authorization verification
↓
Hypit Build
↓
refresh/reconcile
↓
temporary export
↓
ffprobe + full decode + hash
↓
Review
↓
Attempt/output selection
↓
READY_FOR_MANUAL_PUBLISH
```

This means:

> The target architecture is not a greenfield redesign.

The main structural gap is the missing Material stage and final lifecycle unification.

---

# 16. Authoring Stage

The term **Authoring Stage** is intentionally used instead of implying that Hypit Runtime itself performs all AI authoring.

The Authoring Stage means:

> Generate a valid Hypit production structure that expresses the intended video.

Current executor:

```text
Easel orchestration
↓
OpenClaw main Agent
↓
hypit-authoring Skill
↓
writes Hypit production files
↓
Hypit CLI check
```

This is valid and compatible with the target architecture.

The target ownership is:

```text
Easel
= workflow owner

OpenClaw
= AI authoring executor

Hypit
= production contract + validation + runtime + build
```

The target does **not** require moving AI authoring execution out of OpenClaw.

---

# 17. Authoring Outputs

The Authoring Stage may produce:

```text
Treatment
Script
Scenes
SVML
SVRun
Track / Timeline definitions
Resource Slots / Material Requirements
```

Hypit production structure owns:

```text
scene structure
shot intent
timing
track structure
timeline
visual placement
audio placement
typography placement
resource slots
```

Critical rule:

> Decide how the video should be made before deciding where the material comes from.

---

# 18. Material Requirement Contract

The Authoring Stage must expose **machine-readable material requirements**.

The architecture does not mandate a specific file name such as:

```text
materials.json
```

A valid implementation may use:

```text
SVRun resource slots
structured Scene requirements
a dedicated manifest
another Hypit-native resource structure
```

provided the contract is:

```text
machine-readable
validatable
stable
bindable to a Hypit resource/output slot
```

The semantic contract is:

```text
Authoring
→
Material Layer
```

and must express:

> what resource is required

not:

> which provider must satisfy it.

---

# 19. Material Requirement Example

Conceptually:

```json
{
  "requirement_id": "scene-03-primary",
  "scene_id": "scene-03",
  "hypit_output": "scene03_primary_video",
  "media_type": "video",
  "role": "primary_visual",
  "semantic": {
    "subject": "programmer",
    "action": "working alone",
    "environment": "office at night",
    "mood": "quiet and restrained"
  },
  "visual": {
    "orientation": "vertical",
    "shot": "medium",
    "motion": "subtle",
    "realism": "realistic"
  },
  "duration_seconds": 4,
  "constraints": {
    "identity_required": false,
    "logo_allowed": false,
    "text_in_frame_allowed": false
  }
}
```

The exact schema may adapt to Hypit's native resource model.

---

> **Historical Material Layer Sections:** The V0.1 material-specific content from this section onward is retained as historical context. V1.3 supersedes its requirements, status semantics, and Hypit Binding assumptions; use the V1.3 baseline for current design.

# 20. Material Layer

The Material Layer is the largest current missing production capability.

Target flow:

```text
AUTHORING_READY
↓
Material Requirements
↓
Material Resolution
↓
Candidate Selection
↓
Material Snapshot
↓
Hypit Binding
↓
MATERIAL_READY
↓
Runtime / Plan / Build
```

---

# 21. Material Layer Responsibilities

The Material Layer owns:

```text
provider routing
search
generation
local retrieval
candidate normalization
technical validation
license / provenance capture
semantic analysis
visual analysis
ranking
selection
download / generation
hashing
material storage
Attempt-local snapshot
Hypit binding
```

Target architecture:

```text
Material Requirement
+
Material Policy
↓
Resolver
↓
Providers
↓
Candidate Pool
↓
Technical Filter
↓
Semantic / Visual Analysis
↓
Ranking
↓
Selected Material
↓
Material Store
↓
Attempt Snapshot
↓
Hypit Binding
```

---

# 22. Material Layer Non-Responsibilities

The Material Layer must not:

```text
rewrite Content
rewrite Script
change Treatment
change Scene structure
change Director intent
change timing for convenience
change transitions
change timeline
change track structure
```

Material availability must not become the Director.

---

# 23. Material Policy

Material Requirement answers:

> What does this production need?

Material Policy answers:

> How does this Creator / Creative Mode prefer to satisfy that need?

Material Policy belongs on the Easel / Creative Mode side.

Examples:

```text
prefer real footage
prefer reusable local material
avoid generic AI-looking visuals
allow generated video for unique scenes
avoid visible logos
avoid random stock faces for identity-critical scenes
```

---

# 24. Providers

Providers are replaceable capability suppliers.

Examples:

```text
Pexels
Pixabay
MiniMax
future local/media/generative providers
```

Providers do not own:

```text
Creation
Creator
Director
Attempt lifecycle
main workflow
```

They expose capabilities such as:

```text
video.search
image.search
asset.fetch
video.generate
speech.generate
```

The current legacy media/provider scripts may be reused as implementation references or adapters, but they do not count as the new Material Layer until they participate in the official Attempt flow.

---

# 25. Material Store and Provenance

The Material Layer should preserve:

```text
material_id
sha256
provider
provider_asset_id
source_url
author
license
license_url
attribution_required
search_query
downloaded_at
media_type
width
height
duration
size
caption
tags
```

Free material must not be treated as automatically copyright-free.

Source and rights metadata must remain traceable.

---

# 26. Attempt Material Snapshot

Build must operate on fixed Attempt-local inputs.

Selected material should be snapshotted into the Attempt workspace before Build.

Conceptually:

```text
Attempt workspace
└── productions/
    └── production/
        ├── assets/
        └── materials/
            └── manifest.json
```

The exact path may follow current Hypit workspace conventions.

The architectural requirement is:

> Build must not rely on live mutable global material references.

---

# 27. Material Binding

Material Binding is the bridge:

```text
Selected Material
→
Attempt Asset
→
Hypit Resource Slot
→
Run Candidate
```

The Binder satisfies resource slots.

It must not rewrite authored structure.

---

# 28. System Module Boundaries

The current video architecture has five major roles:

```text
Easel
OpenClaw
Hypit
Material Layer
Providers
```

---

# 29. Easel

Easel is the product and workflow owner.

It owns:

```text
Profile / effective Creator Context
Content boundary
Creative Mode
Creation
Attempt identity
user confirmation
high-level lifecycle
review orchestration
final selected output
publication readiness
```

Easel answers:

> What are we making, under which creative context, and what is the verified lifecycle state?

---

# 30. OpenClaw

OpenClaw is an intelligent execution runtime.

In the current video mainline it validly acts as the **Authoring executor**.

It may:

```text
generate proposal content
interpret Creator / Creative Mode context
write Hypit authoring artifacts through Skills
perform intelligent structured tasks
```

It must not independently choose the official production architecture.

The prohibited pattern is:

```text
OpenClaw decides:
Hypit today
legacy auto-short-video tomorrow
direct FFmpeg another time
```

The official `ai-film` route must remain governed by Easel's Creation workflow.

---

# 31. Hypit

Hypit owns the video production contract and runtime.

It owns or validates:

```text
Treatment / Script / Scenes structure
SVML
SVRun
resource/output slots
Track
Timeline
runtime resolution
validation
plan
pricing
build
result
```

Hypit does not need to own AI authoring execution itself.

Current correct relationship:

```text
OpenClaw
writes Hypit-native production artifacts

Hypit
validates and executes them
```

---

# 32. Material Layer

Material Layer owns resource satisfaction.

It answers:

> Which concrete media asset satisfies this declared production requirement?

It owns:

```text
provider routing
candidate lifecycle
analysis
selection
provenance
material storage
Attempt snapshot
binding
```

It does not own directing authority.

---

# 33. Providers

Providers supply capabilities.

They are implementation details beneath Material Layer.

They do not own product state.

---

# 34. Creation Lifecycle

Creation owns the high-level product lifecycle.

Target semantic states:

```text
DRAFT
PREPARING
IN_PRODUCTION
IN_REVIEW
READY
FAILED
ARCHIVED
```

Exact enum names may differ from current code during migration.

The semantic requirement is more important than naming.

---

# 35. Creation READY

This is a critical target rule.

`Creation.READY` must mean:

> A real selected video output exists and the selected Attempt has passed the required production and review gates.

It must not mean:

```text
old stage QC completed
authoring completed
a file happened to be generated
publication flag was set without final review
```

Current code contains conflicting readiness semantics and must eventually converge.

---

# 36. Publication State Is Separate

Publication readiness is not the same as Creation readiness.

Example:

```text
Creation READY
= video production is complete and approved

READY_FOR_MANUAL_PUBLISH
= approved final video is allowed to move into publishing workflow
```

These states should not substitute for each other.

---

# 37. Attempt Lifecycle

Target Attempt semantics:

```text
CREATED

AUTHORING
AUTHORING_READY

MATERIAL_RESOLVING
MATERIAL_READY

BUILD_PLANNING
BUILD_APPROVAL_REQUIRED
BUILDING
BUILT

TECH_QC
TECH_QC_PASSED

CREATIVE_REVIEW
APPROVED

BLOCKED
FAILED
REJECTED
CANCELLED
```

The exact current enum structure may be mapped rather than rewritten wholesale.

---

# 38. AUTHORING_READY

Means:

> Authoring artifacts are structurally valid and Hypit check passes.

It does not mean:

```text
material ready
build complete
video complete
Creation ready
```

---

# 39. MATERIAL_READY

Means:

> All required media resources are concretely satisfied and bound.

Evidence should include:

```text
required slots are satisfied
selected media files exist
hashes match
media can be read
license/policy is accepted
Attempt-local snapshot exists
Hypit resource binding exists
Hypit validation/check passes
```

This is a mandatory Build gate.

---

# 40. Build

Current Hypit Build infrastructure already provides useful aligned capabilities:

```text
runtime resolution
validation/check
plan
pricing
authorization verification
fingerprint protection
build execution
result reconciliation
```

These should be preserved.

2026-09-30 经用户批准的 [V1 最小改造方案](../tasks/creator-autonomous-first-cut-2026-09-30.md) 调整授权交互：新委托可以覆盖后续经正式核价核实的零 Provider 费用合成。每次执行仍记录当前 Plan/Pricing/fingerprint 绑定的批准与委托来源；未知价格和未获授权的付费请求不得自动提交。批准语义保留，逐次人工点击不再是零费用 Build 的必要条件。实施程度以 Current State 为准。

Material readiness should be inserted before Build rather than redesigning Build.

---

# 41. Technical QC

Current export infrastructure already contains meaningful Technical QC primitives such as:

```text
temporary export
ffprobe
full decode
hash
artifact registration
```

Target architecture should reuse and formalize these capabilities.

Do not build a second parallel QC system unless a concrete gap exists.

---

# 42. Creative Review

Creative Review answers:

> Is this the intended video?

Review may include:

```text
content correctness
Creator consistency
Director / Creative Mode consistency
material coherence
voice consistency
subtitle quality
pacing
visual defects
overall style drift
```

Current Review/output-selection infrastructure should be preserved and aligned into the final lifecycle.

---

# 43. Evidence-Based State

Stored state alone is not sufficient.

Principle:

```text
Stored State
+
Artifact / Validation Evidence
=
Effective State
```

Examples:

```text
AUTHORING_READY
→ Hypit authoring artifacts + check evidence

MATERIAL_READY
→ material manifest + files + hashes + binding + check

BUILT
→ Build result evidence

TECH_QC_PASSED
→ verified output

APPROVED
→ review decision tied to exact output hash
```

---

# 44. Mandatory Gates

Target production gates:

```text
CONFIRMATION_GATE
AUTHORING_GATE
MATERIAL_GATE
BUILD_APPROVAL_GATE
TECH_QC_GATE
CREATIVE_REVIEW_GATE
```

Current code already implements several of these.

The main missing mandatory gate is:

```text
MATERIAL_GATE
```

---

# 45. Legacy Boundary

Legacy video systems may remain callable for compatibility, testing, or explicit historical use.

This does not automatically violate the architecture.

The actual rule is:

> **Legacy paths must not be part of the official new `ai-film` / Creation + Hypit mainline.**

Therefore V1 does not require immediate deletion of:

```text
auto-short-video
video-production
legacy FFmpeg / media scripts
/api/skill explicit calls
```

provided:

```text
ai-film never silently routes into them
they do not own new lifecycle state
they do not receive new core architecture responsibilities
```

Legacy removal is not a V1 prerequisite.

---

# 46. Data / Concept Ownership

| Concept | Owner / Current Interpretation |
|---|---|
| Creator concept | Easel product domain |
| Profile | Easel |
| Effective Creator Context | Easel / Creation Preparation |
| Content boundary | Easel |
| Creative Mode | Easel |
| Director concept | Easel product domain |
| Creation | Easel |
| Attempt identity / high-level lifecycle | Easel |
| AI Authoring execution | OpenClaw current executor |
| Hypit production contract | Hypit |
| Treatment / Script / Scenes | Authoring output in Hypit-native production |
| SVML / SVRun | Hypit production model |
| Resource Slots / Material Requirements | Hypit-native authoring contract |
| Material Candidate | Material Layer |
| Material provenance / license | Material Layer |
| Material Store | Material Layer |
| Attempt material snapshot | Material Layer / Attempt workspace |
| Material → Hypit binding | Material Layer → Hypit |
| Runtime / Plan / Pricing | Hypit |
| Build | Hypit |
| Build Result | Hypit |
| Technical output verification | Easel/Hypit integration layer |
| Creative Review | Easel |
| Final selected output | Easel |
| Publication readiness | Easel publishing state |

---

# 47. Current Reality vs Target

The current architecture should be understood as:

```text
ARCHITECTURAL SKELETON
= largely aligned

COMPLETE VIDEO V1
= not yet complete
```

Already aligned:

```text
ai-film → hypit_video routing
Proposal / Confirmation Gate
Creation Preparation
Content Core / Truth / Creator Context freeze
Creative Mode snapshot/hash
Creation / Attempt semantic separation
Hypit workspace isolation
OpenClaw authoring execution
Hypit check
Runtime / Plan / Pricing / Approval
Build infrastructure
Export verification
Review tied to output/hash
Attempt/output selection
```

Partially aligned:

```text
Creator/Profile reproducibility
Director/Creative Mode reproducibility
Creation lifecycle
Attempt persistence model
final selected output semantics
full user-facing Build/Review flow
```

Missing:

```text
machine-readable Material Requirements
Material Resolver
Provider-neutral candidate model
Material Store for official mainline
provenance/license manifest
Attempt material snapshot
Hypit material binding
MATERIAL_READY Gate
```

Conflicting:

```text
legacy Creation.ready semantics
Hypit production lifecycle and old stage lifecycle coexist
publication readiness and production readiness are not fully unified
```

Legacy:

```text
auto-short-video
video-production
old media scripts
asset-manager output indexing
standalone provider integrations
```

---

# 48. V1 Priority

## P0 — Blocks the first complete video V1

### P0-1 Material Layer V1.3 Baseline

Material Layer Architecture: APPROVED / DEVELOPMENT BASELINE (V1.3). Current implementation and verification status is maintained in [`docs/02_CURRENT_STATE.md`](../02_CURRENT_STATE.md). The current design authority is [Material Layer V1.3](material-layer-v1.3.md). Earlier V0.1 Material Requirement, Binding, and Phase 1 task details in this document are historical and superseded.

### P0-2 Final lifecycle convergence

Unify:

```text
old Creation.ready
Attempt review state
selected output
publication readiness
```

Target:

```text
APPROVED Attempt
+
selected verified output
↓
Creation READY
```

### P0-3 Product-level full production flow

The user must be able to complete the official flow through the product:

```text
confirm
→ authoring
→ material
→ build
→ technical validation
→ review
→ select final video
```

Backend APIs alone are not sufficient for product V1.

---

# 49. P1 — Reproducibility and consistency

### P1-1 Creator Context reproducibility

Ensure the effective Creator Context used for the Creation is frozen and traceable.

Do not create a Creator entity unless needed.

### P1-2 Director reproducibility

Stabilize:

```text
Creative Mode
+
Authoring contract
+
Authoring execution behavior
```

Do not create a Director entity unless needed.

### P1-3 Legacy containment

Official `ai-film` must remain on Creation + Hypit.

Explicit legacy calls may remain.

---

# 50. P2 — Engineering evolution

Not required for first video V1:

```text
dedicated Creator entity
dedicated Director entity
dedicated Content entity
Attempt moved to separate database/table
dedicated final_output_id entity
complete Legacy removal
large-scale multi-agent runtime
```

These should only be implemented when real requirements justify them.

---

# 51. V1 Success Criteria

The first Easel video stage is successful when:

> One Creator / Profile + one Director / Creative Mode + multiple different Content inputs can repeatedly produce complete videos with stable creative identity through the official Creation + Hypit mainline.

Test with 3–5 different subjects:

```text
AI learning
investment reflection
work experience
personal growth
life reflection
```

Keep fixed:

```text
same effective Creator Context
same Creative Mode
same directing system
```

Verify:

```text
complete MP4 produced
official path is Creation + Hypit
Material Resolution is automatic
no manual file patch is required
Build only occurs after MATERIAL_READY
technical output is verified
review is tied to exact output
final selected Attempt/output is traceable
Creation final state is trustworthy
voice remains stable
visual language remains stable
pacing remains stable
videos feel like one Creator / one Director system
```

---

# 52. Explicit V1 Non-Goals

The following remain outside current scope:

```text
Knowledge Flywheel implementation
Knowledge Graph
Vector knowledge system
multiple Directors
text/article production
image-post production
podcast production
automatic publishing
platform attribution analytics
large social-media operations expansion
dozens of providers
full DAM platform
multi-agent orchestration redesign
complete Legacy rewrite
Creator CRUD platform
Director CRUD platform
```

---

# 53. Source-of-Truth Structure

Recommended project documentation hierarchy:

```text
docs/00_PROJECT.md
→ stable project goal

docs/01_ARCHITECTURE.md
→ current + target architecture overview

docs/architecture/easel-video-architecture-v1.md
→ authoritative video target architecture

docs/architecture/material-layer-v1.3.md
→ detailed Material Layer architecture

docs/02_CURRENT_STATE.md
→ verified local repository reality

docs/03_ROADMAP.md
→ phased implementation plan

docs/tasks/v1c-t09-generated-material-real-product-branch.md
→ current blocked execution task

docs/decisions/
→ frozen architecture decisions
```

Target and Current must remain separate.

---

# 54. Locked Architecture Decisions

## Decision 1 — Video first

Current development focus is video production.

## Decision 2 — One Creator, one Director first

First prove:

```text
one Creator
+
one Director
+
different Content
→
stable video style
```

## Decision 3 — Creation + Hypit is the official new video mainline

Legacy paths may exist but do not receive new core architecture ownership.

## Decision 4 — Easel owns the workflow

Creation lifecycle and production gating belong to Easel.

## Decision 5 — OpenClaw is the current AI Authoring executor

OpenClaw may author Hypit-native production files.

It does not own the official workflow.

## Decision 6 — Hypit owns the production contract and runtime

Hypit validates and executes the authored production.

## Decision 7 — Authoring precedes material selection

Creative intent is defined first.

Materials satisfy that intent afterward.

## Decision 8 — Material Layer is not a Director

Material availability must not rewrite authored intent.

## Decision 9 — Providers are replaceable capabilities

Provider choice must not define the mainline.

## Decision 10 — Creation and Attempt are semantically separate

Physical storage separation is not required for V1.

## Decision 11 — Domain concept does not imply dedicated entity

Creator, Director, and Content do not require standalone persistence models in V1.

## Decision 12 — State must be evidence-based

Important states must be backed by artifacts and validation.

## Decision 13 — Production readiness and publication readiness are different

Creation READY and READY_FOR_MANUAL_PUBLISH are separate semantics.

## Decision 14 — Final readiness requires approved exact output

A selected Attempt/output must pass required validation and review before Creation becomes READY.

---

# 55. Material Layer Architecture Alignment

Material Layer V1.3 is APPROVED / DEVELOPMENT BASELINE and is the sole current Material Layer architecture authority. Current implementation and verification status is maintained in [`docs/02_CURRENT_STATE.md`](../02_CURRENT_STATE.md). See [Material Layer V1.3](material-layer-v1.3.md) for the frozen design; task scope is routed through [DOCUMENT_INDEX](../DOCUMENT_INDEX.md).

All earlier V0.1 input/output, binding, and internal-architecture statements elsewhere in this document are historical and superseded; they are not compatibility constraints.

---

# 56. Final Summary

The target Easel video architecture is:

```text
One Creator / Effective Creator Context
+
One Director / Creative Mode
+
Different Content
↓
Creation
↓
Confirmation / Preparation
↓
Attempt
↓
OpenClaw Authoring Executor
↓
Hypit-native Production
↓
Material Resolution
↓
MATERIAL_READY
↓
Hypit Runtime / Build
↓
Technical QC
↓
Creative Review
↓
Selected Approved Output
↓
Creation READY
```

The current repository already contains much of the production skeleton.

The primary remaining V1 gaps are:

```text
1. Material Layer
2. Final Creation lifecycle convergence
3. Complete product-level Build / Review / final selection flow
```

The correct next step is therefore:

> **Preserve the aligned skeleton, complete Material Layer architecture alignment before implementation, then unify final readiness semantics and complete the real end-to-end product loop.**


## 2026-10-01 已确认的视频方案边界

Creator 在对话阶段讨论并修改具体文案、分镜节奏、声音设计及规格。Creation 保存完整方案版本，画布展示同一数据；确认制作绑定当前版本。确认后 Preparation 整理事实与上下文，Planning 复用确认的文案/分镜/声音设计并细化 MaterialPlan；不再把“只有方向”当成完整视频方案，也不重新创作已确认文字。Material、Production 与 Hypit 仍沿用现有职责，不新增主链或 Director 模块。真实事实/权利/费用语义不变，需要实质改写确认方案时不能静默执行。旧的已确认 Creation 保留原冻结输入，不自动迁移。
