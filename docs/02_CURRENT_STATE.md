# Easel Current State

Last audited: 2026-09-29. This is the single summary of current implementation and verification status. Source and tests establish behavior; dated Acceptance documents provide evidence for named runs. `SOFTWARE_ACCEPTED` never implies `REAL_WORLD_VERIFIED`.

## Snapshot

| Area | Current status |
|---|---|
| Product | Official `ai-film` Web path is connected through Material Gate, Hypit authoring/execution, and Easel output review. Overall V1 remains **PARTIAL / NOT_READY**. |
| Material Layer | P0/INT/P1 supply contracts are software accepted. MiniMax Image/Video/preset-voice TTS and ordinary Gate are software connected; isolated Image, Video and Voice outputs passed technical inspection. Generated Rights remains unknown and Readiness is NOT_READY; full Creation/Production use is unverified. |
| Local visual Product E2E | **REAL_WORLD_VERIFIED** for one named Creation through human-approved Selected Output; it does not establish full V1 or multi-Content consistency. |
| External Material Product E2E | **REAL_WORLD_VERIFIED** for one standard-chat Creation through Pexels Search/Acquisition, MaterialReadiness `READY`, Production Authoring, Hypit Build, Export, Review and Selected Output. The [named Acceptance](acceptance/external-material-product-e2e-2026-09-29.md) records the initial MaterialReadiness stop; the same Creation was subsequently completed. |
| Runtime profiles | `generation` is **READY** (configuration only). `v1-release` is **NOT_READY**: model auth/endpoint and `audio.production` require live verification. Hypit 0.2.7 doctor, Runtime Worker and both local Programs are ready. |
| P3 | **NOT_STARTED**. |
| Test suite | Last full run: **482 passed, 5 skipped** on 2026-09-28, before the VPN DNS acquisition fix. The 2026-09-29 external-material change passed 62 targeted tests; a new full suite run has not been claimed. |

## Official Product Path

```text
Web ai-film
→ proposal / explicit confirmation + hash-bound Production Brief
→ frozen Content + Creator Context + Creative Mode
→ OpenClaw Planning / MaterialPlan
→ Library-first / eligible supply / Material Gate
→ Rights facts + asset-level evidence / Material Gate（未知与冲突仍阻断）
→ Gate READY 后串行 Authoring / Hypit check
→ Runtime / Plan / Pricing / approval / Build
→ Export / one-pass final review + Selected Output（不发布）
```

Required Needs without current inspected, rights-admitted assets stop at `MATERIAL_NOT_READY`. A Local path or empty Local root does not bypass Planning or the Gate. Production owns final selection; Hypit owns production execution. Legacy `auto-short-video`, `video-production`, and shared media scripts are not the official Web mainline.

## Capability Status

| Capability | Status and evidence boundary |
|---|---|
| Creation / lifecycle | Software path is implemented; Creation read-time lifecycle projection, Attempt transitions and selection gates have deterministic regression coverage. A stale Preparation `MATERIAL_NOT_READY` no longer overrides a later selected, reviewed output in the read-time projection. |
| Planning / Truth | Planning freezes proposal, Content, Creator Context and Creative Mode. The explicitly confirmed chat transcript is now SHA-bound into a validated Production Brief and Planning context. The hash-bound claim ledger auto-classifies deterministic scene directions while factual claims retain distinct source review. Reviewer identity distinguishes `DELEGATE_REVIEWED` from `HUMAN_REVIEWED`. Same-origin loopback review has no manually entered Operator Token. |
| Material sources | Library-first, Local, eligible external routing, Rights/inspection, matching, Bundle and Readiness are software connected. Pexels/Pixabay acquisitions carry mapped official license terms, material-page evidence and listed restrictions; where asset-specific third-party evidence is unknown, corresponding gates still block or request focused review. Generic SHA-bound review remains for unusual/generated/unknown Rights. One Local visual route and one Pexels external-acquisition route through MaterialReadiness are real-world verified. Positive Library reuse remains unverified. |
| AI Material Generation | **IMAGE / VIDEO / PRESET-VOICE TTS SOFTWARE CONNECTED; ALL THREE HAVE LIMITED ISOLATED LIVE EVIDENCE.** MiniMax adapters require per-request operator confirmation and enter ordinary Material intake/Gate. Completed generation is restored only for the current Attempt/Plan revision. The Operator UI now accepts hash-bound, operator-submitted Rights facts for current generated assets and recomputes the same Gate; it does not infer licenses. Unknown Rights blocks admission. Full Creation/Production use remains unverified. See [AI Material Workstream](workstreams/generated-material.md), [T09A](tasks/v1c-t09-minimax-video.md), and [Image/Voice smoke evidence](acceptance/minimax-image-speech-smoke-2026-09-28.md). |
| Continuity | Provider-neutral references and lineage are software connected; cross-Content adherence is unverified. |
| Rights / attribution | Hash-bound local Rights evidence gates required Needs. Pexels/Pixabay ordinary published licenses no longer default to UNKNOWN after valid acquisition; explicit commercial trademark conditions and other unverified identity restrictions are not auto-cleared. Attribution facts have a software propagation path; attribution-bearing real export is unverified. |
| Production / Hypit | Selection qualification, current revisions, bytes and SVML/SVRun references are software gated. Non-paid Authoring starts automatically once the confirmed Production Brief and Material Gate are ready. The Creator-facing production card now shows Chinese progress and one primary action; Runtime/check/plan/pricing/export use their existing formal APIs in the background, while engineering controls stay collapsed. The named External Material Creation completed one real Hypit Build; broader V1 lifecycle evidence remains separate. |
| Audio | BGM and accepted audio material can be authored into Hypit tracks in software. Material Layer connects preset-voice TTS using the frozen, truth-reviewed Script; one isolated real TTS output passed technical intake. It is not voice cloning. Final audio stream/listening, mix quality and real attribution-bearing output remain unverified. SFX is not a V1 Release gate. |
| Export / Review | Named Local visual and Pexels External Material runs completed export, review and Selected Output. Broader modality and release evidence remains pending. |
| Content Asset / Material Promotion | Formal approved Selected Output is copied into a Creator-visible Content Library project and linked back to Creation / Attempt / Build / output / SHA; four existing approved selections were reconciled idempotently. Attempt Material promotion is explicit and scope-bound; UNKNOWN / RESTRICTED Rights fail closed, while Rights, acquisition provenance, generation lineage and source Creation / Attempt are retained. Deterministic promotion → later Library reuse is verified; the current real Pexels Attempt asset is eligible but remains unpromoted until a Creator/Operator chooses it. See [acceptance](acceptance/content-asset-material-promotion-2026-09-29.md). |

## Named Evidence

- Local visual Web run: Creation `cr_0283a7adf4094e80bc0c59b58a68dc99`, Build `bld_20260924T135801492Z_4696AF96FC`; its Acceptance records the 15-second final video and human-approved Selected Output.
- External Material Web run: Creation `cr_fc46c0fd949a4beca0043be745b9458d`, Attempt `fa_c1e6b95191ce6b69be351d8a39cb1e81`; Pexels MaterialReadiness `READY`, Hypit Build `bld_20260928T162455494Z_A032509CF4`, 10-second 540×960 MP4, SHA-256 `59ad3d0d7ab60673ce7cc728283add9b0de892d2d5996ca4d4d1a7e4f0eb44b3`, Review approved and `final.video` selected. The stale Preparation snapshot remains as history; read-time Creation status now projects `ready` from the selected Attempt.
- Pexels, Pixabay, Coverr, Unsplash and Openverse have dated minimal search/normalization evidence. Discovery does not mean acquisition or Rights admission; Coverr, Unsplash and Openverse remain `DISCOVERY_ONLY`.
- Hypit v0.2.7 remains the locally invoked editing/rendering engine. The old `hypihub.default` endpoint and Hypit Image/Video/Voice generation bindings remain removed. MiniMax Image/Video/T2A are separate remote Material providers; API-key presence does not establish authentication or generated output.
- Latest six-profile readiness and dependency facts: [`configuration/v1-runtime-and-external-dependencies.md`](configuration/v1-runtime-and-external-dependencies.md).

## Closure Queue

- **T01–T08, T17, T18:** original scoped software evidence remains historical; Hypit generation portions of T06/T08 no longer define the official product route. Authenticated full-path re-verification remains pending.
- **T09 / AI Material Generation:** previous Hypit execution task is superseded. MiniMax Image, Video and preset-voice TTS implementation and isolated modality smoke evidence are tracked in [`v1c-t09-minimax-video.md`](tasks/v1c-t09-minimax-video.md); real Creation/Production use and Rights evidence remain separate open work.
- **Generated Material baseline:** current scope and gates are recorded in [`workstreams/generated-material.md`](workstreams/generated-material.md). Any billable generation requires per-request operator confirmation.
- **T10 external-acquisition branch:** one named Pexels Creation reached MaterialReadiness `READY` and later completed Production/Export/Review/Selection. **T11–T14 NOT_STARTED:** positive Library-reuse, attribution-bearing-output, Supplemental Supply and Continuity remain separate branches; do not batch these into T15.
- **T15 E2E IN_PROGRESS:** the first frozen Creation/Handoff predates the new hash-bound `ProductionBrief` contract and cannot be silently rewritten. The fresh standard-chat Creation passed Preparation, Script/Truth review and Material Gate. Initial Hypit `MARKUP_ROOT_ATTRIBUTE` failures drove generated-task refresh; later retries exposed harmless selection serialization differences (derived Need IDs, matching redundant identity aliases, and asset order), now normalized only after frozen identity, asset SHA/source and qualified Match are verified. A server restart had left a durable `AUTHORING_RUNNING` state without an in-process task; the Operator now exposes an idempotent recovery action, and this Attempt has been resumed. The latest local `hypit check` found that `Timeline.clock` needs a typed `{clock}` reference, not a string; both generated task guidance and retry guidance now state this installed-v0.2.7 contract. The corrected retry is running; no current Hypit check result or three-source E2E completion is claimed. Full suite: 482 passed / 5 skipped; compile, skills validation, frontend lint/build, and diff check pass. No paid generation or Build has been run in this task slice. Hypit Runtime is prepared; `v1-release` still awaits model auth/endpoint and real audio Build verification. See [T15](tasks/v1c-t15-e2e-readiness.md) and [T19](tasks/v1c-t19-low-friction-creation.md).
- **T16 NOT_STARTED:** multi-Content consistency validation remains separate from T15 and requires an explicit subsequent scope.
- These statuses describe Closure evidence work, not permission to start all tasks automatically. The next work is [T19](tasks/v1c-t19-low-friction-creation.md), then resume [T15](tasks/v1c-t15-e2e-readiness.md), as ordered in the [Roadmap](03_ROADMAP.md).

## Status Rules

- `SOFTWARE_ACCEPTED`: scoped code and deterministic acceptance passed; no live Product proof implied.
- `REAL_WORLD_VERIFIED`: only the named run, artifact, modality and scope were exercised.
- `NOT_VERIFIED`: evidence is missing; do not infer failure or readiness.
- `BLOCKED`: a concrete external/user prerequisite prevents the scoped run.
- Current status belongs here. Workstream/Task/Acceptance docs provide scope and evidence; older audits are historical snapshots.
- The latest test-suite count and duration are a dated measurement, not a target; see [`AGENTS.md`](../AGENTS.md) for risk-based test growth rules.
- The 2026-09-28 portfolio consolidation removed 12 low-value/redundant collected cases, combined BGM/SFX coverage under their shared audio-supply boundary, and collapsed common Markdown renderer smoke cases into one representative contract. It retained the distinct modality, Rights, lifecycle, security, and execution-gate risks. Test-file count changed from 57 to 56; most remaining cases protect distinct behavior.
