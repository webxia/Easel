# Material Layer × Product End-to-End Architecture Drift Closure

Date: 2026-09-27
Type: current-code architecture drift audit + bounded software fixes
Architecture authority: frozen Material Layer V1.3 / ADR-004
Execution limit: no paid Generation Build; no complete Product E2E; no P3.

Summary: **28 areas audited; 23 actionable drift findings (11 HIGH, 12 MEDIUM); 5 bounded findings fixed in software; 18 unverified/remaining findings deferred.** Five areas had no material drift.

## Result Vocabulary

- **ARCHITECTURE TARGET**: defined by V1.3 or Easel Video Architecture.
- **SOFTWARE ACCEPTED**: deterministic implementation/test evidence exists.
- **CONNECTED**: a formal product call edge exists.
- **REAL_WORLD_VERIFIED**: an actual product run exercised the capability.
- **NOT_VERIFIED**: no corresponding live/paid or full modality evidence.

This acceptance does not promote fixtures or prior visual-only E2E evidence into audio or generated-material verification.

## Drift Matrix

| Area | V1.3 / Architecture Target | Current Code (2026-09-27) | Drift | Severity | Repair / status |
|---|---|---|---|---|---|
| Planning | Frozen Content + Creator + Director context produces Treatment/Script/Scenes/MaterialPlan | Web Preparation freezes refs/hashes; OpenClaw Planning persists those artifacts and validates MaterialPlan identity/context | None material | — | CONNECTED; prior local visual Web E2E only |
| MaterialPlan | Plan revision ties Needs to Attempt/context | Attempt store persists plan; readiness hashes full plan JSON | No stale-plan bypass found | — | SOFTWARE ACCEPTED |
| Need | Provider-neutral image/video/voice/BGM/SFX intent and constraints | `MaterialNeed` multimodal specs and provider-neutral refs | No structural drift found; not every modality has a product caller | MEDIUM | Modality product paths listed separately below |
| Continuity | Upstream owns identity; Material consumes `character:`, `voice:`, `location:`, `world:`, `object:`, `music-family:` | Router/matcher consumed some refs; generation preparation previously omitted them | Generation request/provenance did not preserve refs | HIGH | Fixed: request prompt basis and GenerationRecord/Asset lineage carry provider-neutral refs; cross-run adherence remains NOT_VERIFIED |
| Library | Scoped discovery/reuse candidate; revalidate bytes/Rights before Bundle | Search/semantic/reuse/advanced match and import validate scope/SHA; formal Web route calls Library first | Positive-hit real product run absent | MEDIUM | SOFTWARE ACCEPTED; REAL_WORLD_VERIFIED pending |
| Local | Source facts, acquisition, inspect, Rights Admission | Local provider; sidecar bound by content SHA; UNKNOWN blocks required Need | No Rights inference from directory/provider | — | SOFTWARE ACCEPTED; a Local visual route has prior real Web evidence |
| External Search | Provider-neutral candidates and provider isolation | Five provider adapters + normalized candidates; live search evidence exists | Search is not acquisition/Rights | MEDIUM | Explicitly retained; no blanket acquisition claim |
| Acquisition | Only declared acquisition capability materializes Asset | Local/Pexels/Pixabay eligible; Coverr/Unsplash/Openverse remain discovery-only | Some providers cannot enter Acquirer by design | MEDIUM | No unsupported acquisition added |
| SourceRouter | LIBRARY / LOCAL / EXTERNAL / GENERATIVE, Need-aware | Library-first router already handled eligible local/external; new GENERATIVE route is appended only for explicit `allow_generation` or supported Need identity/continuity and only for image/video/voice | Generation route was absent | HIGH | Fixed in software: bounded route evidence and one blocking Need preparation after Bundle/Gaps persist |
| GENERATIVE source | Need → GenerationIntent → Hypit → candidate/asset → normal gates | Hypit gateway + ProductMaterialGeneration; ordinary supply now prepares check/plan/pricing for one eligible blocking Need; explicit APIs still own approval/submit/reconcile/collect | No automatic paid Build; generated result needs re-supply/recompute | HIGH | Software call edge connected; no Build submission from supply; real generation NOT_VERIFIED |
| AI Image | Hypit generation candidate enters ordinary Asset lifecycle | GPT Image source compile/intake; generated output uses Attempt store, inspection and UNKNOWN Rights | Runtime binding/entitlement and paid output not verified | HIGH | SOFTWARE ACCEPTED; blocked until Rights facts admitted; BUILD_REQUIRED for real proof |
| AI Video | Hypit Seedance candidate enters ordinary Asset lifecycle | Seedance compile/intake; contract rejects unsupported Material references | Real runtime/capability unverified | HIGH | SOFTWARE ACCEPTED; BUILD_REQUIRED; no claim of generation continuity |
| Voice Candidate | Voice identity remains provider-neutral; candidate may enter MaterialBundle | Voice Need routes to Hypit VoiceDesign/VoiceClone; Clone requires reference+consent+frozen text; generated asset follows normal inspection/Rights path | VoiceDesign cannot prove stable voice identity across jobs | HIGH | Request refs now recorded; real identity continuity NOT_VERIFIED |
| Narration | Frozen Script → voice intent → Hypit Speech → Production narration track; production-native path may bypass Bundle | Script-bound text/hash contracts and generation Gateway exist; no automatic Web narration orchestrator/AudioTrack integration | Product call chain absent | HIGH | Deferred: requires dedicated Production Audio closure; not safe to claim connected here |
| BGM | Rights-backed candidate supply; Production chooses; Hypit owns timing/mix | Generic audio Need supply exists; dedicated BGM helper has no formal product caller; exact attribution propagation is software-wired | Product selection/AudioTrack/mix caller absent | HIGH | Deferred; no Hypit BGM generation claim |
| SFX | Candidate supply and event semantics; Hypit placement | Need/helper exists; no dedicated formal product caller; no rights-backed sample | Product path absent | MEDIUM | Not a V1 release blocker; later audio acceptance |
| Rights | Same factual admission for every source; UNKNOWN blocks required; generated is not automatically unrestricted | Readiness rechecks per-asset evidence, compatibility, technical pass, SHA; attribution-required facts need an exact export condition | No provider/license inference; real-world metadata chain not yet exercised | MEDIUM | Software supports conditional admission only when credit, creator, source page and asset Rights evidence validate |
| Attribution | Asset requirement follows selected Asset to Export/Review/publish-ready metadata | Production derives exact attribution from selected Bundle Assets; Export rechecks and stores it; Review and Selected Output retain it | No live selected attribution-required output verified | MEDIUM | Fixed in software; no credit is invented and publishing remains manual |
| Matching | Need ↔ Asset hard filters, semantic/director/continuity scores | Normal matcher + advanced Library matcher; Material Layer does not final-select | Model/fixture quality not live-validated | MEDIUM | SOFTWARE ACCEPTED; Production retains authority |
| Bundle | Candidate/source-neutral MaterialBundle and coverage | Assets/matches/coverage assembled; generation assets accepted on subsequent supply pass | Generated result is not immediately merged into existing Bundle | MEDIUM | Explicit resupply/recompute keeps lifecycle bounded and auditable |
| Readiness | Required Needs only; Rights/technical/Hard Filter gate | Recomputed from current Plan/Bundle/workspace bytes, Rights and revision | UNKNOWN or unadmitted generated output blocks as required | — | SOFTWARE ACCEPTED |
| Supplemental Supply | Explicit bounded subset/merge, no recursive retries | P0 supplemental helper is finite; router generation prepares one blocking Need | No automatic generation retry/loop | — | SOFTWARE ACCEPTED |
| Production Authoring | Final selection only from current admitted Bundle | Selection manifest, bundle/revision/hash and actual SVML/SVRun references revalidated | Audio authoring not wired | HIGH | Visual selection connected; audio deferred |
| Hypit Generation | Hypit owns model/runtime/provider/Plan/Pricing/Build/Result | Easel compiles supported Run Sources and uses Hypit CLI, persistent approval, idempotent submit/reconcile, result intake | Current Runtime plan/capability and real Build unverified | HIGH | Boundary MATCH; live capability NOT_VERIFIED |
| Hypit Production | Hypit owns normalization/timing/tracks/mix/composition/build | Visual path uses Hypit; audio primitive contract exists but no accepted Web voice+BGM production | Audio product integration absent | HIGH | Deferred; no Easel media engine added |
| Export | Exact Build output with content identity and required attribution metadata | Export rechecks Bundle attribution against selected Assets and attaches structured credit facts | No real attribution-required export verified | MEDIUM | Fixed in software; Rights facts are separate from the video content hash |
| Review | Review binds exact output, human approval and publication metadata | Review retains the Export attribution structure alongside technical/truth/style/human results | No real attribution-required review package verified | MEDIUM | Fixed in software; review copies validated attribution metadata |
| Selected Output | Selected hash-bound approved result, not publication | Selected Output retains attribution and `publish_automatically=false` | No real attribution-required selected output verified | MEDIUM | Fixed in software; manual publishing remains required |

## Bounded Repairs Completed

1. Added `SourceKind.GENERATIVE` to the existing router. It is emitted only for supported Image/Video/Voice Needs when policy explicitly permits generation or the Need carries a relevant identity/continuity contract. It follows existing eligible supply routes.
2. The formal `MaterialProductOrchestrator → ProductMaterialSupply` path now records this route. If a required Need remains blocked, it asks the existing `ProductMaterialGeneration` service to prepare one eligible Need. This invokes Hypit `check → plan → pricing`; it does not submit Build and leaves `MATERIAL_NOT_READY` intact.
3. Generation preparation remains idempotent by existing Attempt/Plan/Need state and preserves the existing persistent Approval, execution fingerprint, submit, and uncertain reconciliation APIs.
4. Provider-neutral continuity and voice identity references now enter the deterministic generation prompt basis and GenerationRecord/MaterialAsset lineage. This is request/provenance binding only; it is not proof that a remote model maintains identity across Contents.
5. Added/adjusted tests to isolate product supply fixtures from locally configured real Providers; test execution cannot silently turn into a live Provider request.
6. Attribution-required Rights facts pass readiness only when exact recorded creator/source/credit facts satisfy the export condition. Production selection, Export, Review and `READY_FOR_MANUAL_PUBLISH` preserve that structured data without inferring legal status or enabling automatic publication.

## Deferred High Drift

- Script-bound Narration → Production AudioTrack and BGM selection → Hypit mix are not automatically connected in the Web product path. Hypit v0.2.7 provides audio primitives, but code contracts/tests are not a product audio run.
- A real attribution-required Asset → Build → Export → Review → Selected Output run remains unverified; deterministic tests cover the admission and propagation boundaries.
- Real Image/Video/Voice generation requires a configured Hypit runtime/provider capability and a separately approved paid Build. No paid call was performed.
- Positive Library reuse, all eligible external acquisitions, and cross-Content identity consistency lack a new full Product E2E in this task.

## Test Evidence

- Targeted `.venv/bin/python -m pytest -q tests/test_material_routing.py tests/test_material_library_first.py tests/test_material_integration.py tests/test_material_readiness.py tests/test_material_rights.py tests/test_material_p2_06_generation_records.py tests/test_material_p2_07_hypit_generation_gateway.py tests/test_material_p2_08_multimodal_contracts.py tests/test_hypit_integration.py -k 'not sensitive_hypit_api_requires_operator_auth'`: **76 passed, 1 deselected**.
- Full `.venv/bin/python -m pytest -q` with project `.env` present: **467 passed, 5 skipped**. The credential-absence test uses an isolated empty RuntimeConfig root, so it does not depend on or expose local credentials.
- `.venv/bin/python -m compileall -q easel web`: PASS. `git diff --check`: PASS. No live Provider, paid generation, full Product E2E, or P3 work was run.

## Final Status

- Material Layer source-routing drift: **SOFTWARE FIXED / CONNECTED**.
- Continuity in generation requests and provenance: **SOFTWARE FIXED; cross-Content adherence NOT_VERIFIED**.
- Material Layer V1.3: **PARTIAL alignment** because Script Narration/BGM Production Audio and real generation continuity remain incomplete/unverified.
- Product integration: **PARTIAL**.
- Generated Source integration: **CONNECTED / SOFTWARE ACCEPTED; real-world NOT_VERIFIED**.
- Audio integration: **PARTIAL / NOT_CONNECTED for final narration+BGM product run**.
- Code ↔ docs: **PASS** after CURRENT_STATE, Roadmap, Architecture reference, Dependency Registry note, Task, Acceptance and Index synchronization; V1.3 semantics remain unchanged.

## Eight Architecture Questions

1. **Does Material Layer conform to V1.3?** Partially. Planning, frozen context, source-neutral asset intake, Rights/Readiness, Production selection and Hypit ownership match. Generated routing is now software-connected. Narration/BGM Production integration and real generation remain incomplete or unverified.
2. **Is AI Generation a formal Material Source again?** Yes at the software routing/preparation boundary: a Need-gated `GENERATIVE` route now follows eligible existing sources and reuses the Hypit gateway. A completed generated Asset still requires explicit approval/build, collect, ordinary Asset gates and a later Supply recompute. No real generation occurred.
3. **Does continuity flow through Need/Generation/Matching?** Provider-neutral continuity and voice identity refs flow from Need into routing, the generated request basis, GenerationRecord/Asset lineage, and existing matching contracts. This does not prove that a model preserves identity across Content; that remains NOT_VERIFIED.
4. **Do generated Assets use normal Rights/Bundle/Gate?** Yes in software. Generated output is inspected, provenance-recorded and defaults to Rights UNKNOWN; unknown Rights blocks required Needs. It joins MaterialBundle only through ordinary Supply/readiness recomputation.
5. **Are Voice Candidate and Script Narration boundaries preserved?** Yes. Voice Candidate is material; frozen Script-bound narration is production-native and need not pass through Bundle. The latter still lacks an automatic Web Authoring → Speech → AudioTrack path.
6. **Do Existing and Generated Material share one Supply contract?** Yes after generation output intake: both are Attempt-owned MaterialAssets, then share inspection, Rights, matching, Bundle and Readiness. Generation is not silently substituted into Production selection.
7. **What still needs real Providers or paid Build?** Hypit Image/Seedance/Voice capability and result intake, runtime voice identity consistency, new eligible Provider acquisitions, positive Library reuse, and an attribution-bearing real export/review need real or manual product evidence. No paid or live call ran here.
8. **Has Material Supply E2E been reached?** Existing Local visual supply has prior real Web Product E2E evidence. This task added SOFTWARE ACCEPTED generation preparation and attribution propagation, but no new complete Material Supply E2E for Generation/Audio; that broader condition is not met.
