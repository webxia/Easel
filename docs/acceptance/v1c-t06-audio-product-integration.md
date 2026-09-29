# V1C-T06 Audio Product Integration Acceptance

Date: 2026-09-27

> 历史范围说明：本文的 VoiceDesign/VoiceClone 与 Hypit Speech Build 记录是旧路线证据，不描述当前旁白生成链。当前预置音色 TTS 由 Material Layer 的 MiniMax Adapter 提供，Rights/Inspect/Bundle/Gate 后才交给 Hypit 制作；本文中的 BGM、Hypit 音轨及导出策略证据仍按各自代码边界参考。当前状态见 [02_CURRENT_STATE](../02_CURRENT_STATE.md)。

## Result

~~~text
SOFTWARE_ACCEPTED
REAL_WORLD_VERIFIED = NOT_VERIFIED
PAID_BUILD = NOT_RUN
~~~

This acceptance covers deterministic contracts and a local Hypit v0.2.7 static
check. It does not claim a live OpenClaw turn, authenticated Hypit Speech
execution, an audio Build, intelligible narration, audible/non-masking BGM, or
a final audio stream.

## Implemented Product Edges

- Creative Planning binds every required Voice Need to the exact persisted
  planning/SCRIPT.md SHA-256 and a provider-neutral VoiceIdentityRef.
  Easel computes the digest after the Script is frozen and rewrites the
  authoritative planning/MATERIAL_PLAN.json; the planner does not invent a
  digest or provider voice ID.
- Script-bound Voice generation revalidates Script reference and bytes at
  preparation, approval, submit, reconcile and collect boundaries. A stale
  Script blocks use/submission/collection. Read-only reconciliation remains
  available after edits to resolve an uncertain already-submitted operation.
- Hypit v0.2.7 @hypit/mimo-speech@1 is reused. Existing accepted voice
  reference assets use VoiceClone; a provider-neutral identity without an
  audio reference uses VoiceDesign from a short sample of the frozen Script,
  then VoiceClone for the complete frozen Script. The output is the narrated
  materialOutput.audio, not the intermediate voice reference. Request
  preparation remains check → plan → pricing; Build requires existing
  persistent approval and idempotent submission.
- BGM continues through the formal generic MaterialPlan →
  ProductMaterialSupply Library-first source routing and ordinary Rights
  Admission. Production makes the final BGM selection. The BGM integration test
  carries an attribution-required fixture through selection evidence.
- Required Voice/BGM Audio assets must be selected, byte/hash checked, declared
  as media:Audio, normalized with Hypit pipeline:Normalize, placed as audio:Item
  in an AudioTrack and included in the Film as a peer film:Track. Required
  narration and BGM must use distinct AudioTracks.
- The persisted Material audio policy makes Export require an audio stream
  whenever an audio Need is required or Production selects audio. Export
  continues to use Hypit's produced output and Easel's existing ffprobe
  inspection; Easel does not assemble or mix media.
- OpenClaw's Authoring task now includes the Hypit v0.2.7 AudioTrack contract
  inside its Attempt workspace; authoring no longer depends on reading files
  outside the restricted workspace. The contract explicitly states that
  Hypit does not automatically duck BGM.

## Verification

- Targeted tests: 68 passed before final regression sweep; final full-suite
  rerun is recorded in the V1 Closure Execution Status.
- Local Hypit 0.2.7 static check passed for:
  - a Script-bound VoiceDesign → VoiceClone Run targeting
    materialOutput.audio;
  - an audio-bearing Film with normalized BGM AudioTrack, explicit gain/fades,
    and Film inclusion.
- No Runtime auth, remote model, paid Generation Build, Provider request, or
  Product E2E was performed.

## Contract Review

- Reviewed locally installed Hypit v0.2.7 contracts:
  packages/mimo-speech/README.md, packages/audio-track/README.md,
  packages/film/README.md, packages/media-pipeline/README.md, and
  packages/run-markup/README.md.
- Adopted Hypit's separation between VoiceDesign reference and VoiceClone
  speech output; normalized audio input, independent AudioTracks, Film track
  inclusion, explicit gain/fades and Hypit-owned rendering/mix.
- Rejected treating a VoiceDesign reference as finished narration, automatic
  ducking assumptions, an Easel TTS engine, and legacy ffmpeg assembly.
- No external OSS implementation was copied or adopted.

## Remaining Real-World Evidence

- Hypit Speech binding/auth/entitlement and one approved Script-bound voice
  Build.
- A real Rights-admitted BGM Asset selected in a Web Attempt, with exact
  attribution retained through Export/Review.
- A new Web Authoring turn and Hypit check using both narration and BGM.
- A real final output verified by ffprobe and human listening for intelligible
  narration, audible non-masking BGM, fade behavior and clipping.

V1C-T06 is software accepted. V1 Release and Audio readiness remain
NOT_READY until their real runtime/product evidence and remaining tasks pass.
