# Easel Material Layer End-to-End Architecture V1.3

> **Status:** APPROVED / DEVELOPMENT BASELINE
> **Purpose:** 在现有 Easel + OpenClaw + Hypit 架构不推翻的前提下，补齐“Director Intent → Material Supply → Hypit Production → Final Video”的完整链路。
> **Scope:** 一期只解决素材供应及其与上下游的衔接。二期“参考/爆款视频分析 → Director / Video Template”只保留扩展点，不进入本期实现。
> **Source:** 基于 V1.2、Hypit v0.2.7 源码审计、当前 Easel 真实流程审计，以及 MoneyPrinterTurbo、FootageFlow、Media Buddy、stockmedia-sdk、Pexels/Pixabay/Unsplash/Mixkit 等真实实现与官方规则校准。
> **Authority Note:** 旧 Material Layer V0.1 / 旧 ADR 中的素材层设计仅视为历史探索，不作为 V1.3 的兼容约束或架构权威；V1.3 直接以当前 Easel 事实、Hypit v0.2.7 能力与本轮设计共识为准。
> **Implementation Status Note:** V1.3 remains semantically frozen. Dynamic implementation and real-world verification status is tracked in [`docs/02_CURRENT_STATE.md`](../02_CURRENT_STATE.md); this baseline does not claim software acceptance is a Product E2E result.

---

# 1. 一期核心问题

当前 Easel 已经拥有：

```text
Creator
Content
Director / Creative Mode
OpenClaw Authoring
Hypit Production
Build / Review
```

真正缺失的不是 Production Engine，而是：

```text
Director Intent
      ↓
“需要什么素材？”
      ↓
“去哪里找？”
      ↓
“哪些素材真正可用？”
      ↓
“哪些素材最适合当前 Director / Scene？”
      ↓
“把什么素材交给 Hypit Production？”
```

因此一期要补的是：

```text
MaterialPlan
→ Material Layer
→ MaterialBundle
```

它是 Creative Planning 与 Hypit Production 之间的素材供应桥梁。

---

# 2. 一期完整主链

V1.3 正式把一期主链收敛为四个阶段：

```text
Content
+
Creator Context
+
Director / Creative Mode
        │
        ▼
┌──────────────────────────────┐
│ Stage A — Creative Planning  │
│                              │
│ TREATMENT                    │
│ SCRIPT                       │
│ SCENES                       │
│ MaterialPlan                 │
└──────────────┬───────────────┘
               │
               ▼
        PLANNING_READY
               │
               ▼
┌──────────────────────────────┐
│ Stage B — Material Supply    │
│                              │
│ Need → Search → Candidate    │
│ → Acquire → Inspect          │
│ → Rights → Enrich → Match    │
│ → Bundle                     │
└──────────────┬───────────────┘
               │
               ▼
          MaterialBundle
               │
               ▼
        MaterialReadiness
          │           │
          │           └── NOT_READY
          │                    ↓
          │             MaterialGap /
          │             Supplemental Supply
          │
          └── READY
               ↓
        MATERIAL_READY
               │
               ▼
┌──────────────────────────────┐
│ Stage C — Production Authoring│
│ OpenClaw + Hypit semantics   │
│                              │
│ final asset selection        │
│ media admission              │
│ normalize intent             │
│ trim / timing                │
│ visual/audio tracks          │
│ captions / transitions       │
│ timeline / composition       │
└──────────────┬───────────────┘
               │
               ▼
           SVML / SVRun
               │
               ▼
           hypit check
               │
               ▼
        AUTHORING_READY
               │
               ▼
┌──────────────────────────────┐
│ Stage D — Execution          │
│ Runtime / Plan / Pricing     │
│ Approval / Build             │
└──────────────┬───────────────┘
               │
               ▼
            Build Result
               │
               ▼
       Export / QC / Review
               │
               ▼
    Selected Approved Output
```

四个状态语义必须保持单一：

```text
PLANNING_READY
= SCRIPT / SCENES / MaterialPlan 已形成并通过结构校验

MATERIAL_READY
= 所有 blocking MaterialNeed 已满足供应与准入要求

AUTHORING_READY
= 最终 SVML / SVRun 已形成并通过 hypit check

Build Result / Selected Output
= Hypit 执行与 Easel Review 后的生产事实
```

禁止把：

```text
AUTHORING_READY
```

同时解释为“MaterialPlan 已存在”或“素材已经准备完成”。

---

# 3. 四个 Owner

## 3.1 Easel Product / Workflow

拥有：

```text
Creator / Profile
Content / Truth
Director / Creative Mode
Creation / Attempt
Confirmation
Material orchestration
Build orchestration
Review
Selected Output
```

## 3.2 OpenClaw Creative Authoring

拥有：

```text
Story
Narrative
Scene intent
Material intent
Hypit Production authoring
```

OpenClaw 可以在不同阶段工作，但 V1 不把它拆成两个新的产品域。

## 3.3 Material Layer

拥有：

```text
Material need supply
External / local discovery
Provider orchestration
Acquisition
Provenance
Rights facts
Technical inspection
Material intelligence
Need matching
Bundle preparation
```

Material Layer 是供应系统。

## 3.4 Hypit

一期定位：

> **Production Engine**

拥有：

```text
typed production graph
media admission
media normalization
semantic timeline
trim / retime
visual track
audio track
caption
transition
composition
runtime
plan
pricing integration
build
result
```

Material Layer 不复制这些能力。

---

# 4. Material Layer 的正式边界

输入：

```text
MaterialPlan
+
Frozen Creator Context reference
+
Frozen Creative Mode reference
+
Script / Scene references
```

输出：

```text
MaterialBundle
```

Material Layer 终点就是 MaterialBundle。

---

# 4A. Workflow Lifecycle

Material Layer 是 Domain + Supply System，但是否允许继续 Production 属于 Easel Workflow。

V1.3 使用最小生命周期：

```text
PLANNING_READY
↓
MATERIAL_SUPPLY
↓
MaterialReadiness
├── NOT_READY
│   ↓
│   MaterialGap / Supplemental Supply
│
└── READY
    ↓
MATERIAL_READY
↓
PRODUCTION_AUTHORING
↓
hypit check
↓
AUTHORING_READY
```

不引入复杂 Event Sourcing、Round State Machine 或第二套 Workflow Engine。

`MATERIAL_READY` 只是 Workflow Gate：

```text
MaterialBundle
+
MaterialReadiness policy
→ READY / NOT_READY
```

它不是旧 V0.1 的 Binding Contract，也不要求 Material Layer 生成 Hypit Candidate / satisfy。

---

# 4B. MaterialReadiness

定义：

> **MaterialReadiness = 对当前 MaterialBundle 是否足以进入 Production Authoring 的确定性判定。**

建议最小结构：

```text
MaterialReadiness
├── plan_id
├── bundle_id
├── status
├── required_needs
├── covered_required_needs
├── blocking_needs[]
└── blocking_reasons[]
```

状态只需要：

```text
READY
NOT_READY
```

## Ready Rule

对每个：

```text
importance = required
```

的 MaterialNeed，必须至少存在 1 个 qualified MaterialMatch，并且对应 MaterialAsset：

```text
locator / file 可访问
Technical Inspector 通过
Hard Filter 通过
Rights Admission 通过
```

满足：

```text
所有 required Need 均 covered
→ READY
→ MATERIAL_READY
```

否则：

```text
→ NOT_READY
→ blocking_needs[]
→ MaterialGap[]
```

`desired_options` 不是 Ready Gate：

```text
desired_options = 3
qualified_assets = 1
```

只要唯一候选满足 required Need 的所有准入条件，仍可判定：

```text
covered = true
```

## Partial Bundle 与 Ready 的关系

两者必须分开：

```text
MaterialBundle.coverage
= 供应事实

MaterialReadiness
= Workflow Gate
```

例如：

```text
Need A required → covered
Need B required → covered
Need C optional → uncovered
```

MaterialBundle 可以是 partial，但：

```text
MaterialReadiness = READY
```

---

# 4C. Rights Admission Policy

RightsInfo 负责记录事实，Rights Admission Policy 负责判断“当前用途能否进入 Production”。

P0 默认保守策略：

```text
PUBLIC_DOMAIN
→ ALLOW

KNOWN + usage compatible
→ ALLOW

ATTRIBUTION_REQUIRED
→ 只有当前 Production / Export 能满足 attribution 要求时 ALLOW

UNKNOWN
→ BLOCK required Need

RESTRICTED
→ BLOCK
```

这不是法律判断，而是 Easel 的自动化准入策略。

Rights evidence 必须保留在 MaterialAsset / sidecar 中。

未来可以增加：

```text
manual override
organization policy
distribution-specific policy
```

但不进入 P0。

---

# 5. Material Layer 不做什么

明确禁止：

```text
修改 Content
修改 Script
重新定义 Director
决定最终 Timeline
决定 Track placement
决定最终 Trim
决定 Fade / Ducking
生产最终 Composition
直接拥有 Hypit Candidate / satisfy contract
决定 Build 是否可以开始
```

这些属于 Production / Workflow。

---

# 6. 上游：Creative Planning → MaterialPlan

## 6.1 Planning 不是完整 Production

一期需要区分两个概念：

```text
Creative Planning
≠
Final Hypit Production Authoring
```

Planning 只需要回答：

```text
这一条视频讲什么？
有哪些 Scene？
每个 Scene 的表达目标是什么？
需要哪些素材？
素材承担什么叙事功能？
```

它不要求此时已经知道真实素材文件。

## 6.2 MaterialPlan

定义：

> **MaterialPlan = 当前 Creation / Attempt 对整条视频素材需求的结构化计划。**

```text
MaterialPlan
├── plan_id
├── creation_id
├── attempt_id
├── context_refs
├── policy
└── needs[]
```

示例：

```json
{
  "plan_id": "mp-001",
  "creation_id": "creation-001",
  "attempt_id": "attempt-001",
  "context_refs": {
    "creator_context": "handoff/creator-context.json",
    "creative_mode": "handoff/creative-mode/",
    "script": "productions/SCRIPT.md",
    "scenes": "productions/SCENES.md"
  },
  "policy": {
    "strategy": "bulk_first"
  },
  "needs": []
}
```

MaterialPlan 只引用冻结上下文，不复制 Director。

---

# 7. MaterialNeed

定义：

> **MaterialNeed = 一项明确的创作素材需求。**

推荐最小结构：

```text
MaterialNeed
├── need_id
├── scope
├── media_type
├── role
├── intent
├── duration_hint
├── constraints
├── continuity_refs
├── importance
└── desired_options
```

示例：

```json
{
  "need_id": "scene03-visual-main",
  "scope": {
    "type": "scene",
    "ref": "scene-03"
  },
  "media_type": "video",
  "role": "primary_visual",
  "intent": {
    "description": "夜晚，一个程序员独自在办公室面对电脑工作",
    "function": "establish_environment"
  },
  "duration_hint": {
    "target_seconds": 4
  },
  "constraints": {
    "orientation": "portrait",
    "text_in_frame": false,
    "logo": false
  },
  "continuity_refs": [],
  "importance": "required",
  "desired_options": 3
}
```

---

# 8. MaterialNeed 的关键语义

MaterialNeed 表达：

```text
WHAT MATERIAL IS NEEDED
```

而不是：

```text
HOW TO IMPLEMENT IT
```

因此禁止包含：

```text
Pexels
Pixabay
search_query
provider model
download URL
generation prompt
Hypit Candidate
LogicalOutput
Track
Fragment
satisfy
Timeline
```

---

# 9. Need 的 scope

V1 支持：

```text
global
scene
segment
event
```

例如：

```json
{
  "scope": {
    "type": "scene",
    "ref": "scene-03"
  }
}
```

或者：

```json
{
  "scope": {
    "type": "global",
    "ref": "video"
  }
}
```

V1 不要求 MaterialNeed 使用 Hypit Script anchor。

上游 Scene / Script reference 足够。

未来 Production Authoring 可自行映射到 Hypit Segment / Selection / Moment。

---

# 10. Continuity

V1 使用轻量 continuity refs：

```text
character:creator-avatar
voice:creator-main
location:office-a
world:future-city
object:phone-a
music-family:reflective-tech
```

原则：

> Material Layer consumes identity; it does not create identity.

---

# 11. Material Layer 内部完整链路

```text
MaterialPlan
    │
    ▼
Plan Validation
    │
    ▼
NeedCompiler
    │
    ├── RetrievalIntent
    └── GenerationIntent（当 SourceRouter 选择 GENERATIVE 时）
    │
    ▼
SourceRouter
    │
    ├── LOCAL / REFERENCES
    ├── MATERIAL_LIBRARY
    ├── EXTERNAL_DISCOVERY
    └── GENERATIVE_SOURCE
    │
    ▼
Source Adapters / Gateways
    │
    ├── Discovery Provider Registry
    │      ├── Pexels
    │      ├── Pixabay
    │      ├── Coverr / Unsplash / Openverse ...
    │      └── discovery-only sources
    │
    ├── Material Library Search
    │
    └── Material AI Generation Adapter（下一阶段）
           ├── Image
           ├── Video
           ├── Voice / TTS
           └── Future Music / Audio
    │
    ▼
SupplyCandidate
    │
    ├── availability
    ├── rights evidence
    ├── source metadata
    └── acquisition descriptor
    │
    ▼
Metadata Filter / Provider-aware Pre-Rank / Dedup
    │
    ▼
Top-N Acquire / Materialize
    │
    ▼
MaterialAsset
    │
    ├── Technical Inspect
    ├── Provenance
    ├── Rights
    ├── Semantic Enrichment
    └── Usage / Lineage
    │
    ▼
Hard Filter
    │
    ▼
Soft Match
    │
    ▼
Diversity / Bundle Consistency
    │
    ▼
MaterialBundle
    │
    ├── optional promote → Material Library
    └── downstream → Hypit Production Authoring
```

核心原则：

```text
External Provider != Generative Runtime
```

- Pexels / Pixabay / Unsplash 等是素材发现与获取来源。
- AI 图片 / 视频 / Voice 是生成来源。
- AI 生成属于 Material Supply。模型执行由素材层下的可替换生成 Adapter 承担；Material Domain 保持 provider-neutral。Hypit 只消费已准入素材并负责剪辑、合成与成片渲染。

---

# 12. Step 1 — Plan Validation

MaterialService 首先校验：

```text
plan_id
attempt_id
need_id unique
scope valid
media_type valid
required context refs exist
constraints structurally valid
```

这里不做创意判断。

---

# 13. Step 2 — NeedCompiler

定义：

> **NeedCompiler 把 MaterialNeed 编译为“检索意图”，但不改变 MaterialNeed。**

P0 只负责：

```text
MaterialNeed
+
Creator Context
+
Creative Mode
→ RetrievalIntent
```

不负责任何最终 Production。

---

# 14. RetrievalIntent

`RetrievalIntent` 是 Material Layer 内部模型，不进入上游 Contract。

```text
RetrievalIntent
├── need_id
├── semantic_queries[]
├── filters
├── negative_terms[]
├── ranking_hints
└── query_context
```

示例：

```json
{
  "need_id": "scene03-visual-main",
  "semantic_queries": [
    "programmer working alone office at night",
    "developer coding late night dark office",
    "software engineer computer office night"
  ],
  "filters": {
    "media_type": "video",
    "orientation": "portrait",
    "min_duration": 4
  },
  "negative_terms": ["logo", "presentation"],
  "ranking_hints": {
    "prefer_environment": "office",
    "prefer_action": "coding"
  }
}
```

NeedCompiler 应按 Need / Scene 生成 2~4 个查询变体，而不是把整条视频压缩成少量全局关键词。

这是从 MoneyPrinterTurbo 的 Script → Search Terms 实践进一步收敛出的 Easel 版本：Easel 已经有 Scene/Need，因此应保留叙事位置与素材需求之间的对应关系。

当 SourceRouter 选择生成来源时，另产生 `GenerationIntent`：

```text
GenerationIntent
├── need_id
├── creative_intent_ref
├── modality
├── prompt_material
├── references[]
├── hard_constraints
└── alternatives_requested
```

`GenerationIntent` 仍然是 Material Layer 的供应意图，不携带 Hypit Candidate / Track / Timeline。

---

# 15. NeedCompiler 的 AI 边界

NeedCompiler 可以使用 LLM / embedding 做：

```text
semantic expansion
synonym expansion
query variants
English query translation
visual vocabulary normalization
negative-term expansion
retrieval hint generation
```

但不能改写：

```text
scene meaning
director intent
required identity
hard constraints
truth / factual claims
```

对于 AI 生成，它只能把已存在的创作意图编译为 `GenerationIntent`，不能自行创造新的 Director 风格。

因此：

```text
Director 决定 HOW
Authoring 决定 WHAT
NeedCompiler 决定 HOW TO SEARCH / HOW TO EXPRESS SUPPLY INTENT
```

---

# 16. Step 3 — SourceRouter

SourceRouter 回答：

> **这个 MaterialNeed 应优先通过哪一类来源满足？**

统一来源类型：

```text
LOCAL
MATERIAL_LIBRARY
EXTERNAL_DISCOVERY
GENERATIVE
HISTORICAL（后续）
```

推荐默认优先级不是全局固定，而是按 Need / role / continuity 决定。例如：

```text
明确用户参考素材
→ LOCAL first

普通现实 B-roll
→ MATERIAL_LIBRARY → EXTERNAL_DISCOVERY

高连续性角色 / 世界观镜头
→ MATERIAL_LIBRARY → GENERATIVE

抽象视觉 / 无法稳定 stock 检索
→ GENERATIVE

Voice identity 强约束
→ existing/library voice → generative voice
```

SourceRouter 不决定具体 Provider API 参数，不改写创作意图。

P0 实现只启用：

```text
LOCAL
EXTERNAL_DISCOVERY
```

但 Domain 从 V1.2 开始正式承载：

```text
MATERIAL_LIBRARY
GENERATIVE
```

---

# 17. P0 Source Strategy

P0 的目标是证明“真实素材供应链”成立，而不是覆盖所有来源。

```text
Need
├── explicit Local / Reference
└── External Discovery
    ├── Pexels
    └── Pixabay
```

P0 仍然要求 Provider 模型从第一天支持：

```text
真实 capability 声明
真实 access mode
真实 pagination/continuation
真实 download availability
真实 rights evidence
真实 quota/cache policy
```

这样后续扩 Coverr、Unsplash、Openverse、Mixkit、Videvo 时不需要重构 Provider Core。

---

# 18. Provider Registry

Provider Registry 不只是“Provider 名称 → client”。

它必须注册真实 Provider 能力：

```text
ProviderInfo
├── provider_id
├── display_name
├── media_types[]
├── access_mode
├── capabilities[]
├── pagination_mode
├── auth_mode
├── quota_policy
├── cache_policy
├── attribution_policy
└── acquisition_policy
```

## AccessMode

```text
OFFICIAL_API
PUBLIC_API
DIRECT_SEARCH
DISCOVERY_ONLY
LOCAL
```

禁止假设所有来源都支持 direct download。

## ProviderCapability

```text
SEARCH
PREVIEW
DETAIL
RIGHTS_METADATA
ATTRIBUTION_METADATA
DIRECT_DOWNLOAD
DOWNLOAD_TRACKING
PAGINATION
HEALTH_CHECK
```

## Pagination / Continuation

统一业务层只认：

```text
ProviderContinuation
```

内部可承载：

```text
page
offset
token
cursor
next_url
```

不强迫所有 Provider 共用 `page` 参数。

## Provider Health / Quota

```text
ProviderHealth
├── status
├── last_success_at
├── last_error
├── quota_remaining
├── retry_after
└── degraded_reason
```

单 Provider 的 429 / missing key / temporary block 只能停止该 Provider，不阻断其他来源。

## P0 Providers

```text
PexelsProvider
PixabayProvider
LocalProvider
```

## 后续 Providers

```text
Coverr
Unsplash
Openverse
Mixkit
Videvo
更多来源
```

其中 `DISCOVERY_ONLY` Provider 允许只返回官方 source page，不要求下载能力。

---

# 19. Provider Adapter Contract

Discovery Provider 概念接口：

```text
info() -> ProviderInfo
search(intent, continuation?) -> ProviderPage
lookup(provider_asset_id) -> ProviderAssetDetail?
resolve(candidate) -> AcquireDescriptor?
health() -> ProviderHealth
```

`ProviderPage`：

```text
ProviderPage
├── candidates[]
└── continuation?
```

Provider 内部处理：

```text
authentication
API schema
pagination / continuation
rate limit
bounded retry
provider-specific errors
raw metadata mapping
provider-specific rights fields
cache requirements
```

业务层只接收标准化对象。

工程约束参考 FootageFlow + stockmedia-sdk：

```text
每个 Provider 必须有固定 fixture
解析测试
错误案例
离线 self-test（可行时）
quota / attribution / cache / download restriction 文档
```

不得通过 CAPTCHA 绕过、Cookie 窃取、DRM 绕过或高风险 scraping 去“补齐” Provider 能力。

---

# 20. Provider Failure Isolation

Provider 必须独立失败：

```text
Pexels  → OK
Pixabay → 429 / retry-after
Local   → OK
```

MaterialService 仍继续聚合可用结果。

失败分类至少：

```text
AUTH
RATE_LIMIT
TEMPORARY
NETWORK
INVALID_RESPONSE
UNSUPPORTED
RIGHTS_UNAVAILABLE
DOWNLOAD_UNAVAILABLE
```

SupplyRun 保留 Provider 失败记录，但单一 Provider 失败不等于 Need 失败。

当所有可行来源都无法满足 Need 时，Coverage 才进入：

```text
partial / uncovered
```

---

# 21. Step 4 — SupplyCandidate

定义：

> **SupplyCandidate = 已被发现、标准化，但还没有成为 Easel 可用 MaterialAsset 的候选。**

```text
SupplyCandidate
├── candidate_id
├── need_id?
├── media_type
├── source
├── preview
├── availability
├── rights_hint
├── metadata
├── acquisition
└── provider_payload_ref
```

`availability`：

```text
DISCOVERED
PREVIEWABLE
RESOLVABLE
DIRECT_DOWNLOADABLE
GENERATABLE
UNAVAILABLE
```

这解决一个重要现实问题：

```text
搜索得到
!=
可以自动下载
```

示例：

```json
{
  "candidate_id": "cand-001",
  "media_type": "video",
  "source": {
    "kind": "stock",
    "provider": "pexels",
    "provider_asset_id": "12345",
    "source_page": "..."
  },
  "availability": "DIRECT_DOWNLOADABLE",
  "preview": {"url": "..."},
  "metadata": {
    "duration": 8.2,
    "width": 1080,
    "height": 1920
  }
}
```

Discovery-only 结果可以留在候选池供人工查看，但不会进入自动 Acquisition 队列。

---

# 22. Candidate != MaterialAsset

必须保持：

```text
SupplyCandidate
= 可能使用

MaterialAsset
= Easel 已经真正取得并验证
```

Provider 搜索结果不能直接成为 MaterialAsset。

---

# 23. Step 5 — Candidate Pre-Filter

下载/生成前先做廉价过滤：

```text
media type
availability
orientation
provider duration
resolution
obvious duplicate
rights metadata availability
source policy
```

例如：

```text
100 remote candidates
→ 20 metadata-qualified
→ 8~12 pre-ranked
→ Top-N acquire / materialize
```

注意：Rights metadata 缺失不等于自动淘汰，除非当前 Rights Policy 明确禁止 UNKNOWN。

---

# 24. Step 6 — Pre-Rank

Pre-Rank 只基于廉价信号：

```text
matched query
provider relevance
available provider metadata
resolution
orientation
duration
rights confidence
source preference
previous usage penalty
```

必须是 **provider-aware** 的。

不同 Provider 暴露的 title/tags/description 不同：

```text
有字段 → 使用
没有字段 → 保持 unknown
```

不得为统一评分模型伪造不存在的 metadata。

深度语义匹配放在 Acquire 后的 Asset Intelligence / Soft Match。

---

# 25. Step 7 — Acquisition

Acquisition 不直接消费 Provider 原始 URL，而消费标准化：

```text
AcquireDescriptor
├── mode
├── url?
├── tracking_url?
├── required_headers?
├── expires_at?
├── expected_media_type
├── cache_policy
└── provider_policy
```

`mode`：

```text
DIRECT_DOWNLOAD
HOTLINK_REFERENCE
LOCAL_STAGE
GENERATED_OUTPUT
MANUAL_SOURCE_PAGE
```

P0：

```text
Stock Candidate
→ resolve AcquireDescriptor
→ RemoteURLPolicy
→ download / stage

Local Candidate
→ validate / stage
```

后续 AI：

```text
GenerationIntent
→ Material AI Generation Adapter（下一阶段）
→ generated candidate / output bytes
→ MaterialAsset
```

## RemoteURLPolicy

所有远程 URL 统一校验：

```text
HTTPS required when applicable
reject embedded username/password
reject localhost / private-network targets
signed URL 与 public source_page 分离
敏感 query 不写入 provenance/export
tracking URL 与 media URL 分离
```

这样吸收 MoneyPrinterTurbo / FootageFlow 对 signed URL、credential redaction、URL safety 的真实经验。

---

# 26. MaterialAsset

定义：

> **MaterialAsset = Easel 当前 Attempt 已经真正拥有、可定位、可验证、可分析的一份素材。**

```text
MaterialAsset
├── asset_id
├── media_type
├── file
├── source
├── rights
├── technical
├── semantic
└── lineage
```

---

# 27. MaterialAsset — file

```json
{
  "file": {
    "path": "materials/assets/asset-001/original.mp4",
    "sha256": "...",
    "size": 18293482,
    "mime": "video/mp4"
  }
}
```

P0 只要求 workspace file。

`hypit_output` 暂不进入 MaterialAsset V1 P0。

---

# 28. MaterialAsset — source / provenance

Stock：

```json
{
  "source": {
    "kind": "stock",
    "provider": "pexels",
    "provider_asset_id": "12345",
    "source_page": "...",
    "creator": "..."
  }
}
```

Local：

```json
{
  "source": {
    "kind": "local",
    "origin": "references/reference-01.mp4"
  }
}
```

Library：

```json
{
  "source": {
    "kind": "library",
    "library_asset_id": "lib-001",
    "original_source_ref": "asset-source-001"
  }
}
```

Generated：

```json
{
  "source": {
    "kind": "generated",
    "engine": "hypit",
    "build_id": "bld_xxx",
    "output": "scene03.generated-video",
    "generation_model": "..."
  }
}
```

Generated Asset 仍必须保留 provider/model/terms evidence；“AI 生成”不等于自动拥有无限使用权。

---

# 29. Source Sidecar

每个 Workspace MaterialAsset：

```text
asset-001/
├── original.mp4
├── source.json
└── analysis.json
```

`source.json` 至少：

```text
source kind
provider / engine
provider_asset_id / build-output address
source_page
creator
matched query
downloaded/generated_at
license / rights evidence
attribution metadata
```

不得保存：

```text
API key
access token
embedded credentials
unredacted signed secret
```

对生成素材，额外保留：

```text
model
request hash / generation ref
reference asset ids
build id
output name
terms evidence
```

---

# 30. Step 8 — Technical Inspector

Material Layer 负责“资产事实检查”。

Video：

```text
duration
width
height
fps
codec
has_audio
mime
file size
```

Image：

```text
width
height
mime
alpha
```

这些是素材事实，不是 Production Normalize。

重要边界：

```text
Technical Inspect
≠
Hypit Normalize
```

Material Layer 可以读媒体事实。

最终 Production normalization 仍归 Hypit。

---

# 31. Step 9 — Rights

`RightsInfo`：

```text
RightsInfo
├── status
├── license_name
├── license_url
├── attribution_required
├── attribution_text
├── usage_constraints[]
├── evidence[]
└── reviewed_at?
```

状态：

```text
KNOWN
ATTRIBUTION_REQUIRED
PUBLIC_DOMAIN
UNKNOWN
RESTRICTED
```

`usage_constraints` 用于承载真实资产级限制，例如：

```text
commercial_use_unknown
editorial_only
no_redistribution_as_stock
attribution_required
api_display_attribution
provider_download_tracking_required
```

原则：

```text
Provider != License
Search Success != Permission
Download Success != Permission
Generated != Automatically Unrestricted
UNKNOWN != FREE
```

Rights 必须以具体 Asset 的 Provider/Model evidence 为准，不根据 Provider 名字统一推断。

Material Layer 记录事实和 evidence；最终法律判断仍不由 LLM 自动完成。

---

# 32. Step 10 — Asset Intelligence

Asset Intelligence 把“文件”升级为“可检索、可匹配的素材”。

Video / Image：

```text
caption
tags
objects
people_count
environment
action
shot_type
camera / motion hints
visible_text
logo
style descriptors
color / lighting hints
```

Audio：

```text
duration
speech/music/sfx classification
language
ASR (when speech)
tempo / energy (when music)
event class (when SFX)
loudness facts
```

来源优先级：

```text
Provider facts
+ deterministic inspector
+ AI/VLM/ASR enrichment
```

AI enrichment 只能补充和推断，不静默覆盖 provider-supplied facts。

V1.2 建议：

```text
P0 → basic metadata + minimal semantic caption/tags
P1 → VLM/embedding enrichment
P2 → multimodal enrichment / continuity evidence
P3 → performance-aware metadata and reuse learning
```

---

# 33. Enrichment 原则

Provider metadata 是事实来源之一。

AI enrichment：

```text
补充
推断
评分
```

不能静默覆盖真实 Provider facts。

---

# 34. Step 11 — Hard Filter

获取后再次做确定性 Gate：

```text
file valid
media type
duration
orientation
resolution
rights policy
forbidden text
forbidden logo
explicit identity requirements
```

Hard Filter 不通过：

```text
Asset 保留在 supply-run 记录
但不进入 qualified matches
```

---

# 35. Step 12 — Soft Match

对通过 Hard Filter 的 Asset：

```text
Semantic Match
Director Match
Continuity Match
Quality
```

示例：

```json
{
  "semantic": 0.92,
  "director": 0.86,
  "continuity": 1.0,
  "quality": 0.82
}
```

---

# 36. MaterialMatch

MaterialMatch 把：

```text
Need
↔
Asset
```

分离。

```json
{
  "need_id": "scene03-visual-main",
  "asset_id": "asset-001",
  "rank": 1,
  "scores": {
    "semantic": 0.92,
    "director": 0.86,
    "continuity": 1.0,
    "quality": 0.82
  },
  "reasons": [
    "matches night office environment",
    "portrait framing",
    "no visible logo"
  ]
}
```

一个 Asset 可以 Match 多个 Need。

---

# 37. Material Layer 不做最终 Editorial Selection

Material Layer 可以：

```text
筛掉不能用的
排序
保留 Top-K
```

但不能决定：

```text
最终成片一定使用 asset-001
```

最终选择属于 Production Authoring。

---

# 38. Step 13 — Dedup / Diversity

Dedup：

```text
provider + provider_asset_id
normalized source URL
normalized download URL
SHA-256
metadata similarity
```

Diversity：

```text
不要给同一 Need 返回 3 个几乎一样的镜头
```

因此：

```text
Top-K
≠
单纯 Score 前 K
```

需要轻量多样性控制。

---

# 39. Bundle Consistency

Bundle Consistency 分阶段实现。

P0：

```text
per-need match
basic dedup
basic diversity
```

P1：

```text
visual style consistency
location/world consistency
recent-use repetition penalty
```

P2：

```text
character/reference consistency
AI-generated + stock mixed-style consistency
voice/music-family consistency
```

P3：

```text
cross-video Creator consistency
performance-informed reuse policy
advanced global VLM evaluation
```

Consistency 只能验证现有 Director / continuity refs，不能创造新风格。

---

# 40. MaterialBundle

定义：

> **MaterialBundle = 当前 Attempt 已准备好的 MaterialAsset，以及 Need ↔ Asset 的匹配与覆盖关系。**

```text
MaterialBundle
├── bundle_id
├── plan_id
├── supply_run_id
├── assets[]
├── matches[]
└── coverage[]
```

---

# 41. Coverage

```json
{
  "need_id": "scene03-visual-main",
  "status": "covered",
  "qualified_assets": 3
}
```

状态：

```text
covered
partial
uncovered
```

MaterialService 可以成功返回：

```text
PARTIAL MaterialBundle
```

不要求整片所有 Need 都成功才返回。

---

# 42. SupplyRun

SupplyRun 是一次供应执行的审计记录。

只需要：

```text
supply_run_id
plan_id
started_at
finished_at
provider_results
failures
result_bundle_id
```

不建立复杂 Round State Machine。

---

# 43. Bulk-first

默认：

```text
whole-video MaterialPlan
→ one bulk supply
→ initial MaterialBundle
```

理由：

```text
能同时看全片
能减少重复搜索
能做去重
能做多样性
为后续 consistency 留空间
```

---

# 44. 补料闭环

补料分成两类。

## A. Readiness Blocking Gap

Material Supply 完成后：

```text
MaterialReadiness = NOT_READY
```

必须输出 blocking MaterialGap：

```text
required Need uncovered
rights blocked
technical invalid
all candidates fail hard filter
```

此时不进入 Production Authoring。

## B. Editorial Gap

即使：

```text
MaterialReadiness = READY
```

Production Authoring 仍可能发现：

```text
当前 Top-K 编辑上不合适
镜头语义虽然匹配但节奏不可用
需要不同视觉
需要更高质量版本
```

可以显式输出：

```text
MaterialGap
```

例如：

```json
{
  "need_id": "scene06-visual-main",
  "reason": "qualified_options_not_suitable",
  "request": "more_options"
}
```

MaterialGap 不改变原 Need。

P0/P1 默认：

```text
显式补料
不自动递归
不无限循环
```

---

# 45. Supplemental Supply

```text
MaterialGap[]
↓
MaterialService.supply_subset(...)
↓
new SupplyRun
↓
new assets / matches
↓
merge MaterialBundle
```

V1 只需要：

```text
supply_run_id
parent_run_id
```

不做复杂轮次状态机。

合并规则：

```text
已存在 MaterialAsset
→ 按 content identity / sha256 去重并保留

新 SupplyRun
→ 追加新 Asset / Match / Coverage evidence

已有 ranked candidates
→ 不因补料而自动删除

Production 已明确选择的 Asset
→ 补料过程不自动替换

MaterialBundle
→ 生成新 bundle revision / updated_at evidence
```

停止规则 P0/P1 保持简单：

```text
由 Workflow / 用户显式触发下一次补料
不自动无限 retry
```

P2/P3 再考虑：

```text
max rounds
cost budget
quality threshold
automatic supplement policy
```

## 45.1 Material Library — 持久化素材库

Material Library 不是新的素材实体体系。

> **Material Library = 可跨 Attempt 复用的持久化 MaterialAsset Catalog。**

关系：

```text
External / Local / Generated
↓
Attempt MaterialAsset
↓
optional Promote
↓
Material Library
↓
future MaterialNeed
↓
Library Search
↓
SupplyCandidate / MaterialAsset reuse
```

Library 至少保存：

```text
library_asset_id
content identity / sha256
physical locator
original provenance
rights
technical metadata
semantic metadata
embedding/search index
usage history
creator/director compatibility evidence
created_at / last_used_at
```

Material Library 的目标不是“囤文件”，而是：

```text
优先复用已经理解过的素材
减少重复下载 / 重复 VLM 成本
减少同一素材在近期视频中的重复出现
保留历史 provenance / rights / usage
```

P1 开始实现。

### Promote Policy

进入 Library 前至少满足：

```text
file/material locator valid
sha256/content identity known
source/provenance present
rights state preserved
technical inspection complete
```

语义 enrichment 可以后补。

### Library Search

```text
metadata search
semantic embedding search
rights filter
media type / duration / orientation filter
usage-history penalty
continuity refs
```

默认 SourceRouter 可逐步演进为：

```text
explicit local/reference
→ Material Library
→ External Providers
→ Generative Sources
```

但具体顺序仍由 Need 类型和策略决定。

---

# 46. 下游：MaterialBundle → Hypit Production

MaterialBundle 不直接生成 Hypit Binding。

正确关系：

```text
SCRIPT
+
SCENES
+
Creative Mode
+
MaterialBundle
+
MaterialReadiness = READY
        ↓
OpenClaw Hypit Production Authoring
        ↓
SVML / SVRun
```

MaterialReadiness 只决定能否进入 Production Authoring，不决定最终选材。

---

# 47. Production Authoring 做什么

Production Authoring 负责：

```text
最终选择哪个 Asset
Asset 用于哪个 production role
如何进入 Hypit Source
是否 Normalize
Trim
Timing
Track placement
Caption
BGM / SFX placement
Transition
Composition
```

这就是 Material Layer 的终点与 Hypit Production 的起点。

如果 READY 后，Production Authoring 仍发现 Top-K 在真实编辑语境中不适合，可以显式返回：

```text
MaterialGap
```

再触发 Supplemental Supply。

P0 不自动递归补料，不建立无限循环。

---

# 48. MaterialAsset → Hypit Workspace Bridge

V1.3 正式定义素材进入 Hypit 的路径边界。

## 48.1 Attempt-owned workspace

所有进入 Production Authoring 的普通素材必须先成为 Attempt workspace 内可定位资产：

```text
attempt-workspace/
└── materials/
    └── assets/
        └── asset-001/
            └── original.mp4
```

MaterialAsset 对外暴露的是 workspace-owned locator，而不是任意外部路径。

## 48.2 Path Rule

Production Authoring 只允许引用：

```text
Attempt workspace 内
project-relative
canonicalized
validated
```

的素材路径。

禁止：

```text
任意绝对路径
用户 Home 路径
/tmp 临时文件
未经 stage 的 Provider remote URL
不受 workspace 管理的外部文件
```

## 48.3 Bridge

普通素材典型路径：

```text
MaterialAsset.workspace_path
↓
OpenClaw Production Authoring
↓
Hypit media:Video / media:Image / media:Audio
↓
BlobArtifact
↓
pipeline:Normalize when needed
↓
SynchronizedMedia
↓
MediaTrack / AudioTrack / other components
↓
Composition
```

Material Layer 不负责写 Hypit graph。

## 48.4 Local / External Asset

Local / External Provider 素材在进入 Production 前：

```text
discover / validate
↓
stage into AttemptMaterialStore
↓
MaterialAsset
↓
workspace-relative locator
```

## 48.5 Historical Hypit Result

未来 Hypit Build Result reuse 仍通过：

```text
build-record
Candidate
satisfy
```

进入 Production。

只有当历史 Output 需要进入 Material Library / 新 Need 检索时，才注册为 MaterialAsset；不要求先复制到 workspace file。

---

# 49. Candidate / satisfy 的定位

Hypit 的：

```text
Candidate
satisfy
build-record
```

保留给：

```text
替换 Author 默认 production route
复用历史 Build Output
显式选择已经接受的生成结果
```

它不是所有 MaterialAsset 的强制接入方式。

因此：

```text
MaterialBundle
!=
Hypit Candidate Bundle
```

---

# 50. Hypit Build Result Reuse

Hypit Build Result reuse 属于 Production Integration 的后续能力，但 V1.2 明确预留和 Material Layer 的交点。

Production-native reuse：

```text
Previous Build Output
↓
build-record
↓
Candidate
↓
satisfy
↓
new Build
```

Material Layer 不需要把所有 Build Result 都注册成 MaterialAsset。

只有当某个 Hypit 输出需要：

```text
作为未来 Need 的候选
跨 Attempt 进入 Material Library
参与新的素材检索 / 匹配
```

才可以显式注册为：

```text
MaterialAsset(source.kind = generated, build_id + output)
```

这保持：

```text
Hypit Result Repository = production execution truth
Material Library = reusable material catalog
```

两者不重复存储职责。

---

# 51. AI Generation 的位置

AI 素材生成属于 Material Supply。MiniMax Image、Video 和预置音色 TTS adapters 均通过远程 API 接入；逐模态真实生成验收与动态状态见 [Current State](../02_CURRENT_STATE.md) 和 [Generated Material Workstream](../workstreams/generated-material.md)。这些 Provider 选择不改变本节定义的 Material ownership、Rights 或 Readiness 语义。

## Candidate-style Generation — 属于 Material Supply

适合：

```text
生成 3 张可选插画
生成 2 个 B-roll 候选视频
生成多个 voice candidate
生成可复用的背景/器物/环境素材
```

链路：

```text
MaterialNeed
↓
SourceRouter = GENERATIVE
↓
GenerationIntent
↓
Material AI Generation Adapter
↓
Selected Material Adapter execution / result (MiniMax remote video API in the first integration)
↓
Generated Output
↓
MaterialAsset
↓
Rights / Inspect / Enrich / Match
↓
MaterialBundle
```

Material Layer 决定：

```text
是否需要 generative source
需要几个 alternatives
生成结果是否满足 Need
哪些进入 Bundle
```

生成 Adapter 决定：

```text
具体模型调用与参数
本地运行时和资源需求
执行结果及错误事实
```

Material Layer 通过可替换 Adapter 调用生成能力，并保存生成意图、输出、成本与 Rights 证据。生成结果必须通过普通的 Inspect / Rights / Match / Bundle / Readiness。Hypit 不参与素材生成请求。

冻结 Script 对应的旁白、特定镜头或声音，也先形成 Material Need 与可审核的生成结果，再由 Production Authoring 选用。Hypit 的 Timeline / Track / Composition / Build 仅用于已准入媒体的剪辑成片。

---

# 52. Voice / BGM / SFX

V1.2 正式支持多模态 Material Domain：

```text
video
image
audio.voice
audio.music
audio.sfx
```

但分阶段接入。

## Voice

候选来源：

```text
Local / Library voice reference
Generated voice / TTS via Material AI Generation Adapter（下一阶段）
```

Voice 与旁白的生成结果进入 MaterialBundle，经 Rights 与技术准入后由 Production Authoring 放入音轨。

## BGM

来源：

```text
Material Library
Provider / discovery source
Future generated music
```

Material Layer 只负责：

```text
发现
rights
energy/mood/tempo/intelligence
Need matching
```

最终：

```text
placement
window
fade
gain
ducking
```

仍归 Hypit Production。

## SFX

同理：

```text
search / library / generated
→ MaterialAsset
→ Match event need
```

实际 event placement 归 Hypit Timeline / AudioTrack。

---

# 53. Workspace

Attempt Workspace：

```text
attempt-workspace/
├── handoff/
├── references/
├── productions/
│   ├── TREATMENT.md
│   ├── SCRIPT.md
│   └── SCENES.md
├── runs/
└── materials/
    ├── plan.json
    ├── bundle.json
    ├── assets/
    │   └── asset-001/
    │       ├── original.mp4
    │       ├── source.json
    │       └── analysis.json
    └── supply-runs/
        └── supply-001/
            ├── request.json
            ├── candidates.json
            ├── failures.json
            └── result.json
```

Persistent Material Library 不放进单个 Attempt：

```text
creator-workspace/
└── material-library/
    ├── catalog.db / index
    ├── objects/
    ├── metadata/
    └── embeddings/
```

具体物理存储形式可后续调整，但 Domain 必须保持：

```text
AttemptMaterialStore != MaterialLibrary
```

---

# 54. 模块边界

建议：

```text
easel/materials/

domain/
    models.py
    rights.py
    capabilities.py

application/
    service.py
    compiler.py
    router.py
    matcher.py
    bundle.py
    promotion.py

providers/
    base.py
    registry.py
    pexels.py
    pixabay.py
    local.py
    coverr.py          # later
    unsplash.py        # later
    openverse.py       # later

sources/
    library.py
    generative.py

infrastructure/
    acquisition.py
    url_policy.py
    inspect.py
    intelligence.py
    storage.py
    dedup.py
    embeddings.py      # later

library/
    catalog.py
    search.py
    usage.py
```

Hypit bridge 不放进 Material Core：

```text
easel/hypit/
    material_bridge.py
    generation_gateway.py
```

或者由现有 Authoring/Hypit integration 承担。

依赖原则：

```text
Material Domain
不得 import Hypit concrete types
```

只有 Integration/Gateway 层可以同时理解两边模型。

---

# 55. MaterialService

核心 API：

```text
MaterialService.supply(plan) -> MaterialBundle
```

补料：

```text
MaterialService.supply_subset(plan, need_ids, parent_bundle)
→ MaterialBundle
```

后续 Library：

```text
MaterialService.promote(asset_ids) -> LibraryPromotionResult
MaterialService.search_library(intent) -> SupplyCandidate[]
```

后续 AI：

```text
MaterialService.generate(need / generation_intent)
→ SupplyCandidate[] / MaterialAsset[]
```

外部调用仍建议优先通过 `supply()` 统一编排，避免上层直接感知 Provider 或生成后端。

---

# 56. 依赖方向

严格保持：

```text
Creator / Director / Authoring
          ↓
     Material Domain
          ↓
    Provider Adapters
```

Material Domain 不能 import Hypit。

Hypit Integration 可以同时读取：

```text
MaterialBundle
+
Hypit contracts
```

即：

```text
Material Core
       ↓
Integration Layer
       ↓
Hypit
```

不能反向：

```text
MaterialNeed
← Hypit LogicalOutput
```

---

# 57. 从当前实现迁移

当前实际链：

```text
OpenClaw Authoring
→ TREATMENT / SCRIPT / SCENES / SVML / SVRun
→ hypit check
→ AUTHORING_READY
→ Runtime / Plan / Build
```

Material Layer 当前未接入。

V1.3 不要求一次推翻现有链路。

---

# 58. Migration Stage A — Material P0 Standalone

先不改正式主链：

```text
hand-written MaterialPlan
↓
MaterialService
↓
Pexels / Pixabay / Local
↓
MaterialBundle
↓
MaterialReadiness
```

验证：

```text
Material Domain
Provider
Acquisition
Rights
Matching
Bundle
Readiness
```

---

# 59. Migration Stage B — 接 Planning 上游

OpenClaw 增加 Planning 输出：

```text
TREATMENT.md
SCRIPT.md
SCENES.md
materials/plan.json
```

此阶段可以暂时继续生成旧的：

```text
SVML / SVRun
```

用于兼容当前主链，但它们不代表最终目标形态。

新增逻辑状态语义：

```text
PLANNING_READY
```

只表示 Planning artifacts 完整。

---

# 60. Migration Stage C — 接 Material Gate

在 Planning 后插入：

```text
MaterialService.supply(plan)
↓
MaterialBundle
↓
MaterialReadiness
```

如果：

```text
NOT_READY
```

停止进入正式 Production Authoring，输出 blocking gaps。

如果：

```text
READY
```

进入：

```text
MATERIAL_READY
```

---

# 61. Migration Stage D — 接 Production Authoring

MaterialBundle READY 后：

```text
SCRIPT
+
SCENES
+
Creative Mode
+
MaterialBundle
↓
OpenClaw Production Authoring
↓
final SVML / SVRun
↓
hypit check
↓
AUTHORING_READY
```

此时逐步删除“在真实素材存在前就把最终 production 写死”的旧假设。

最终目标：

```text
Creative Planning
→ PLANNING_READY
→ Material Supply
→ MATERIAL_READY
→ Production Authoring
→ AUTHORING_READY
→ Plan / Pricing / Build
```

是否保留提前生成的 SVML skeleton：

```text
由真实开发验证决定
```

不作为 Architecture 强制要求。

---

# 62. P0 开发范围

V1.2 不再只有 P0；采用 P0 → P1 → P2 → P3 渐进实现。

## P0 — Core Supply Foundation / 真实视觉素材闭环

目标：证明 Material Domain 与真实 Provider 工作。

必须完成：

```text
MaterialPlan / MaterialNeed
ProviderInfo / Capability / AccessMode
ProviderContinuation
CandidateAvailability
AcquireDescriptor
NeedCompiler / RetrievalIntent
SourceRouter
Provider Registry
Pexels
Pixabay
Local
SupplyCandidate
Provider-aware pre-filter / pre-rank
RemoteURLPolicy
download / acquisition
MaterialAsset
source sidecar
Technical Inspector
RightsInfo + Evidence + usage_constraints
basic semantic enrichment
Hard Filter
basic Soft Match
Dedup / basic Diversity
MaterialBundle / Coverage
MaterialReadiness
Rights Admission Policy
MaterialGap (blocking only)
SupplyRun
AttemptMaterialStore
workspace-relative Material locator contract
```

不要求：

```text
Material Library
AI generation
BGM/SFX full automation
advanced VLM consistency
```

## P1 — Material Library + Intelligence + Provider Expansion

目标：从“每次重新找素材”升级到“可复用素材系统”。

```text
Persistent Material Library
Promote / reuse
metadata + embedding search
usage history
recent-use repetition penalty
VLM enrichment
better semantic / Director Match
bundle visual consistency
Coverr
Unsplash
Openverse
更多稳定 API Provider
provider health / quota visibility
smarter cache
```

注意 Unsplash 等 Provider 必须遵守其 API-specific hotlink / download tracking / attribution policy，而不是按统一 Download 逻辑处理。

## P2 — Multimodal + AI Generative Supply

目标：视觉 stock 不足时，素材层可以通过 AI 与音频来源补齐。

```text
GenerationIntent
Material AI Generation Adapter
AI Image candidate generation
AI Video candidate generation
Voice / TTS candidate generation
Generated MaterialAsset provenance
model / provider terms evidence
BGM discovery
SFX discovery
Music/SFX semantic intelligence
audio MaterialNeed / MaterialAsset / Match
Mixkit / other discovery-only sources where safe
AI + stock mixed bundle consistency
```

其中：

```text
candidate-style generation → Material Layer
生成结果 → 普通 Material Gate → Hypit Production
```

## P3 — Production Reuse + Advanced Optimization

目标：形成真正长期可复用的 Creator 素材系统。

```text
Hypit Build Result → optional MaterialAsset registration
build-record / Candidate / satisfy reuse integration
Historical source routing
advanced supplemental loop
cross-video usage history
Creator-level material preferences
performance-informed reuse / avoid policy
advanced bundle consistency
cost-aware / quality-aware source routing
provider quality telemetry
library cleanup / retention / dedup maintenance
```

P3 仍不把 Timeline / Composition ownership 移给 Material Layer。

---

# 63. P0 明确不做

这里改为“阶段边界”，避免把后续能力误解为永久不做。

## P0 不做

```text
Material Library runtime
AI image/video/voice generation
BGM/SFX full automation
legacy Material Binding contract
Hypit Candidate mapping
Build Result reuse
advanced bundle VLM consistency
event sourcing
complex workflow state machine
```

## P1 不做

```text
把具体模型 runtime 或 provider schema 放进 Material Domain
复杂 Production binding
production-native AI generation ownership
```

## P2 不做

```text
让 Material Layer 决定 Timeline
让 AI 生成结果绕过 rights/provenance/inspect/match
把 Hypit Result Repository 复制成 Material DB
```

## 所有阶段都不做

```text
Material Layer 成为 Director
Material Layer 成为 Editor
Provider schema 泄漏进 Domain
根据 Provider 名字猜 license
高风险 scraping / DRM / CAPTCHA / credential bypass
```

---

# 64. P0 Acceptance

## P0 Acceptance

输入：

```text
one realistic multi-need MaterialPlan
```

真实执行：

```text
Pexels + Pixabay + Local
```

必须证明：

```text
1. 多 Need 批量供应
2. Provider 可部分失败
3. Provider capability / continuation 真实生效
4. discovery 与 direct download 可区分
5. 不下载全部 Candidate
6. Remote URL 经过安全策略
7. 下载资产有 sha256 / source sidecar
8. Rights UNKNOWN 不伪装为 FREE
9. rights evidence / usage constraints 可保存
10. Hard Filter 与 Soft Match 分离
11. 每 Need 有 ranked alternatives
12. Bundle 可 partial
13. required Need 缺失时 MaterialReadiness = NOT_READY
14. Rights UNKNOWN/RESTRICTED 能阻断 required Need
15. optional Need 缺失不必阻断 MATERIAL_READY
16. desired_options 不作为强制 Gate
17. MaterialAsset 使用 Attempt workspace-relative locator
18. 不产生 Timeline / Track / legacy Hypit Binding
19. READY Bundle 可供下游 Production Authoring 读取
```

## P1 Acceptance

```text
1. Attempt asset 可 Promote 到 Material Library
2. 新 Need 可先命中 Library 再访问外部 Provider
3. 同一 Asset 不重复保存/重复分析
4. 支持 embedding/semantic search
5. usage history 能降低近期重复素材
6. 新 Provider 不要求修改 Material Domain
```

## P2 Acceptance

```text
1. 一个 Need 可以在 Stock 不足时路由到 GENERATIVE
2. 下一阶段 AI Image/Video 至少一种真实通过 Material-owned Adapter 生成
3. 生成结果进入 MaterialAsset / Rights / Inspect / Match 同一链路
4. Voice/TTS 或 BGM/SFX 至少一条多模态链路可跑通
5. 所有生成结果都必须经过普通 Material 准入后才能进入 Production
```

## P3 Acceptance

```text
1. 可显式注册一个 Hypit Build Output 为可复用 MaterialAsset
2. Historical/Library/External/Generative 可共同路由
3. 补料与复用不会破坏 provenance
4. SourceRouter 可考虑 cost / quality / prior usage
5. 跨视频复用仍保持 Creator/Director 边界
```

---

# 65. 防偏移检查

每个后续任务都问：

```text
1. 这是不是素材供应问题？
2. 这是不是 Production 问题？
3. 有没有让 Material Layer 改 Director？
4. 有没有让 Material Layer 决定 Timeline？
5. 有没有让 Provider schema 泄漏进 Domain？
6. 有没有把 Hypit type 塞进 MaterialNeed / MaterialAsset？
7. 有没有为了未来能力提前复杂化 P0？
```

如果 3~7 任一为 YES：

```text
暂停实现
回到本 Baseline
```

另外：

```text
旧 Material Layer V0.1 / 旧 ADR
= historical reference only
≠ V1.3 compatibility requirement
```

任何新实现都不得为了兼容旧 BindingResult / ResolutionResult / MATERIAL_READY 语义而破坏 V1.3 Core Domain。

---

# 66. 二期扩展点

未来：

```text
Reference / Viral Video
↓
Analysis / Reverse Engineering
↓
Narrative Pattern
Shot Language
Rhythm
Caption Pattern
Music Pattern
Transition Pattern
↓
Director / Video Template
↓
Director Library
```

然后重新进入一期：

```text
Director
+
New Content
→ MaterialPlan
→ Material Layer
→ Hypit Production
```

二期不改变一期 Material Core。

---


# V1.3 Change Log

相对 V1.2：

```text
KEEP
- MaterialPlan / MaterialNeed / SupplyCandidate / MaterialAsset / MaterialMatch / MaterialBundle
- Provider capability / acquisition / rights / material library / AI / P0-P3 roadmap
- Hypit = Production Engine
- Material Core 不依赖 Hypit 类型

ADD
- PLANNING_READY / MATERIAL_READY / AUTHORING_READY 单一语义
- MaterialReadiness
- Rights Admission Policy
- blocking MaterialGap
- workspace-relative MaterialAsset → Hypit bridge
- supplemental merge / stop rules

REMOVE AS CONSTRAINT
- 旧 V0.1 Material Binding contract
- 旧 ADR 的素材层兼容要求
```

V1.3 is the frozen Material Layer Development Baseline and defines target architecture; current implementation status is tracked in `docs/02_CURRENT_STATE.md` and scoped Tasks are indexed in `docs/DOCUMENT_INDEX.md`.

---

# Appendix A. Provider / Website Capability Matrix

| Source | Media | Access | Search | Direct Acquire | Rights / Attribution | V1.2 Phase |
|---|---|---|---|---|---|---|
| Pexels | Image / Video | Official API | Yes | Yes, policy-aware | Preserve provider/source metadata | P0 |
| Pixabay | Image / Video | Official API | Yes | Yes, cache/mass-download policy-aware | Preserve item/provider evidence | P0 |
| Local | Image / Video / Audio | Local | N/A | Local stage | User/local provenance | P0 |
| Coverr | Video | API / provider-specific | Yes | Capability-dependent | Asset evidence | P1 |
| Unsplash | Image | Official API | Yes | Special hotlink + download tracking semantics | API attribution requirements | P1 |
| Openverse | Image / Audio | Public API | Yes | Asset-specific | Strong license metadata orientation | P1 |
| Mixkit | Video / Music / SFX | Website / limited discovery | Limited | Do not assume | Item-type specific licenses | P2 |
| Videvo | Video / Audio | Website / limited discovery | Limited | Do not assume | Asset/license-specific | P2 |
| Material Library | All | Local catalog | Yes | Reuse | Preserve original rights | P1 |
| Material AI Generation Adapter | Image / Video / Voice / future audio | Local model service | N/A | Generated candidate | Preserve model/provider terms evidence | Next phase |

原则：

```text
Provider capability 以当前官方能力和真实实现为准。
没有稳定 API / download 权限时，宁可 discovery-only，也不做脆弱 scraping。
```

---

# Appendix B. OSS Reference → Easel Mapping

## MoneyPrinterTurbo

吸收：

```text
Script → search terms
stock source integration
source metadata
search caching
stock / generated material conceptual unification
```

Easel 改进：

```text
不用整片全局关键词替代 MaterialNeed
不让 Material Layer 自己完成最终剪辑
```

Reference: https://github.com/harry0703/MoneyPrinterTurbo

## FootageFlow

重点吸收：

```text
ProviderInfo / real capability declaration
ProviderContinuation
failure isolation
rights states
source sidecars
unknown stays unknown
discovery-only providers
URL safety
fixed provider fixtures
project/library workflow
dedup priority
```

Reference:
- https://github.com/xcslys99/FootageFlow
- https://github.com/xcslys99/FootageFlow/blob/main/DEVELOPMENT.md
- https://github.com/xcslys99/FootageFlow/blob/main/docs/RIGHTS_AND_ATTRIBUTION.md

## Media Buddy

重点吸收：

```text
local library
provider metadata preservation
AI caption / tags / object understanding
post-acquisition enrichment
```

Reference: https://github.com/aivrar/mediabuddy

## stockmedia-sdk

重点吸收：

```text
typed provider adapters
validation
pagination
retry
rate-limit handling
typed exceptions
```

Reference: https://github.com/difyz9/stockmedia_sdk

## pexels-media

重点吸收：

```text
natural intent
→ search parameters / filters
→ normalized result
```

Reference: https://github.com/wengxiaoxiong/pexels-media

---

# Appendix C. Official Provider Rules That Affect Architecture

架构必须显式承载 Provider-specific policy，而不是把它们压扁成一个统一下载接口。

Examples:

```text
Pexels / Pixabay
→ quota / cache / API-specific behavior

Unsplash
→ hotlink + download tracking + attribution requirements

Mixkit
→ item type can map to different license classes
```

这些差异进入：

```text
ProviderInfo
AcquireDescriptor
RightsInfo
Source sidecar
```

而不是泄漏到 MaterialNeed。

---

# 67. 最终一句话

> **Easel Material Layer 是 Creative Planning 与 Hypit Production 之间的多来源、多模态素材供应系统。**

完整链路：

```text
Director Intent
↓
MaterialPlan
↓
SourceRouter
├── Local / References
├── Material Library
├── External Discovery Providers
└── AI Generative Sources
↓
Discover / Generate
↓
Candidate
↓
Acquire / Materialize
↓
MaterialAsset
↓
Rights / Technical / Intelligence / Match
↓
MaterialBundle
↓
Hypit Production Authoring
↓
Timeline / Composition / Build
↓
Final Video
```

分阶段：

```text
P0 → 真实 Stock / Local 闭环
P1 → Material Library + Intelligence + 更多 Provider
P2 → Multimodal + AI Generative Supply
P3 → Hypit Result Reuse + Advanced Optimization
```

核心边界不变：

```text
Material Layer = HOW TO SUPPLY
Hypit = HOW TO PRODUCE
```

V1.2 的目标不是一次实现所有功能，而是让核心模型从第一天就能承载后续 Provider、素材库、AI 与复用能力，同时让每个阶段都可以独立验收。

---
