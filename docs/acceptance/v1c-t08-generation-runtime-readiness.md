# V1C-T08 Generation Runtime Readiness Acceptance

Date: 2026-09-27
Status: SOFTWARE_ACCEPTED; real generation remains NOT_VERIFIED.

## Scope

Added `easel runtime generation-preflight [--json]`. It compiles disposable Image, Video, VoiceDesign, and Script-bound VoiceClone Run Sources through the existing `HypitMaterialGenerationGateway`, then records only Hypit `check`, `plan`, and `pricing` stage outcomes. Workspaces are temporary and removed. The command has no Build operation and cannot submit a generation request.

The preflight is opt-in and separate from ordinary profile readiness. Hypit remains the owner of Runtime, Endpoint, credential store, provider selection, and pricing. Easel prints no credential values or raw Hypit response/error payloads.

## Verification

| Capability | `check` | `plan` | `pricing` | Build | Current result |
|---|---|---|---|---|---|
| GPT Image `@hypit/gpt-image@1#gpt-image-2` | PASS | BLOCKED, 1 unresolved request | NOT_RUN | NOT_CALLED | `UNRESOLVED_RUNTIME_PROVIDER_ROUTE` |
| Seedance `@hypit/seedance@1#seedance-2-mini` | PASS | BLOCKED, 1 unresolved request | NOT_RUN | NOT_CALLED | `UNRESOLVED_RUNTIME_PROVIDER_ROUTE` |
| VoiceDesign `@hypit/mimo-speech@1#mimo-v2.5-tts-voicedesign` | PASS | BLOCKED, 1 unresolved request | NOT_RUN | NOT_CALLED | `UNRESOLVED_RUNTIME_PROVIDER_ROUTE` |
| Script-bound VoiceClone `@hypit/mimo-speech@1#mimo-v2.5-tts-voiceclone` | PASS | BLOCKED, 2 unresolved requests, including the composed VoiceDesign request | NOT_RUN | NOT_CALLED | `UNRESOLVED_RUNTIME_PROVIDER_ROUTE` |

Hypit CLI is `0.2.7`. `hypit doctor` passes for the configured local Runtime. The selected profile contains `hyperframes.local` and `media.local`, no generation bindings, and no `hypihub.default` Endpoint. `hypit auth status hypihub.default` cannot establish auth because that Endpoint is not declared. No inference, generation, pricing request, or Build was made during this preflight; pricing was intentionally skipped after each plan failed.

## Tests

- `.venv/bin/python -m pytest -q tests/test_runtime_generation_readiness.py tests/test_runtime_config.py tests/test_material_p2_07_hypit_generation_gateway.py` — **39 passed**.
- Fake Hypit contract tests cover successful check/plan/pricing for all routes, unresolved Plan blocking Pricing, missing Runtime config, Build never called, and secret-payload suppression.
- The Hypit auth readiness parser now reads the v0.2.7 Runtime Profile's `endpoints` array and `instance` fields instead of treating endpoints as a map.

## Remaining External Gate

The Hypit operator must select and declare an Endpoint that serves each desired capability, configure its Hypit-owned auth/entitlement, then rerun this preflight. Do not copy credentials to Easel `.env`. A successful preflight is only `READY_FOR_GENERATION_E2E`; a real paid generation result requires the separate product approval gate and T09 evidence.

No paid Build was run. No AI generation capability is REAL_WORLD_VERIFIED.
