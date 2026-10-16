# Planning Creative Authority & Decision Provenance｜New-Only 实施方案

> **当前状态：D0–D4 全部 SOFTWARE PASS / PLANNING_SOFTWARE_COMPLETE=PASS；Planning 专项已冻结、正式 U4 BLOCKED、U5/U6 未授权。§8.15–8.22 是当前受测软件合同与 Closure，旧 NO_CODE_IMPLEMENTATION 和历史 NEXT 不再有效。**
> **日期：2026-10-15** · **工作区：**`/Users/xgx/Projects/Easel` · **分支：**`easel-studio` · **审查起点 HEAD：**`d82bb60b`（非受测发布指纹）  
> **任务归属：**唯一 [Creator Task](creator-autonomous-first-cut-2026-09-30.md) 下的 Planning 子工作包；接续 [B Review P0 / R02–R08 证据](planning-b-review-p0-identity-binding-implementation-2026-10-14.md)。**不创建第二 Goal、Agent、状态机、视频主链或 U0–U6 之外的新正式 Gate。**  
> **权威：**[`00_PROJECT`](../00_PROJECT.md)、[`easel-video-architecture-v1`](../architecture/easel-video-architecture-v1.md)、[`material-layer-v1.3`](../architecture/material-layer-v1.3.md)、[`web-backend-new-only-cutover-plan`](../architecture/web-backend-new-only-cutover-plan-2026-10-11.md)。本文为待批准的实现蓝图，**不是**这些合同的当前生效修订，也不是生产/付费授权。

## 0. 目标、结论及不可突破的边界

**业务目标：**一个 Creator/Profile + 一个 Director/Creative Mode，在多个不同 Content 的独立 Creation 中保持可辨认的创作风格，同时允许每部作品有不同选题、观点、故事、镜头及素材。这里的“多个内容”是同一导演服务不同作品，不是把九个问题全部改判，也不是让不同作品套同一脚本/场景模板。

**已确认的缺口与待验证原因：**当前 Planning 已有来源资格校验、`director_realization` 和“合法具体化”的审查语义，并非完全禁止导演创作（`planning_authority.py:1–5,246–270`、`planning_semantic_review.py:169–188`）。已知缺口是候选条件的创作归因、B 的拒绝类别、局部修复及下游责任尚未形成本文拟议的逐项交接；R08 记录也只证明九条非 ACCEPT 仍阻断 Truth。合法 HOW 是否被误当作必须逐字蕴含的事实、A 是否把软偏好升成 Hard，需要逐条对照原来源和正反例验证，不能直接把全部失败定性为 B 误拒或 token 太长。

**按阶段划清导演职责：**确认前，Director 可以根据 Content 决定选题、论点、故事和表达，Creative Mode 不是固定写作公式；确认后，本工作包的 Planning 只细化已经确认的 Script/Scenes/Treatment/声音方案，不能静默重写它们。实质改变确认方案须回到既有修订/重新确认路径。此限制只作用于确认后的 Planning，不削减 Director 在讨论创作阶段的职责。依据：`00_PROJECT.md`、视频架构 §8–9/§51/“2026-10-01 已确认的视频方案边界”、`creative_modes/clear_memo_video/director-treatment.md`。

**采用方案：**`Bounded Delegation + Planning-local Decision Proof + Typed B Review + Verified Consumer`。保留 A-selection/A-details → B Review → 原共享 Repair → 原 Truth → MaterialPlan 的单 Owner 路径；冻结来源保持不可变。目标是 **自主创作的合法性和消费责任**，不是通过改判把 9 个真实历史错误全部包装成 ACCEPT。

**本期范围：**新增创作归因与 B 分类只覆盖现有 B 已审查的 image/video 候选、其后期/叙事条件、视觉必要性、视觉覆盖和相关未决报告。现行 B 不独立审查 Voice/BGM/SFX 的声音语义（`planning_semantic_review.questions()` 明确跳过非视觉）；声音方案、冻结 Voice 身份、音轨义务与 Truth 继续由各自原合同/消费者校验。本包不声称实现全模态导演审核；跨内容验收同时保护原音轨与整体风格上下文，不另建声音 Reviewer。

**必须保持：**
- Proposal @4、Creator Context、Creative Mode、确认 Script/Scenes/Treatment/音轨及 Truth Packet 原件与 SHA 均不可由 A/B 改写；Model 无权签发用户授权、身份、费用、素材 Rights 或 MATERIAL_READY。
- Material V1.3/ADR-004 的 `MaterialPlan/MaterialNeed → Supply/Bundle/Readiness` 正式输入输出不变，Material 不获得导演/剪辑权；Native Authoring、Hypit 和 Quality 仍各自拥有原责任。
- 原 `Condition.strength=required|preference`、`responsibility=material|postproduction|narrative`、`NeedProposal.necessity` 的**正式含义**不降级；新增的区分只在 Planning 的 A 候选、B 审核和 Proof 内表达。
- 唯一共享 Repair 预算、B question_id、`local-ref@2` Evidence Projection、Checkpoint SHA/终态捕获、UNKNOWN 不重派、原 Attempt 只读、正式 U0–U6 顺序与每次外部调用的授权不变。
- 不能用“模型可能理解”“存在某段 quote”“soft continuity score”替代独立语义证明、实际 Hard 消费或真实 Rights 准入。

## 1. 当前实现断点（以源码为准）

| 当前入口/符号 | 已具备 | 缺口和实施责任 |
|---|---|---|
| `planning_authority.load_inputs()/catalog()/validate_basis()` | 冻结 Handoff/Mode/Proposal 与 `upstream_obligation/director_realization/preference` 来源关系 | 已有来源资格≠某个导演选择获授权；需在现行 Planning 路径建立到每条 Condition 的可复核绑定，不能复用旧分类阶段自证 |
| `planning_input_view.SourceSelection` + `StagedProposal.selection_schema/details_contract()/assemble_batches_candidate()` | 来源映射、两阶段 A、固定 `slot_XXX`、头部与详情的冻结身份 | `A-details` 目前输出自然语言 Condition，没有同行的候选决策归因；`A-selection` 的 modality/necessity/continuity 是独立头部选择，不应丢失责任 |
| `planning_result_contract.Condition/NeedProposal` | `text/meaning/strength/responsibility` 等规划语义 | 无法区分确认事实与本次导演具体化；**不建议**直接给 MaterialNeed 增 authority 字段 |
| `planning_candidate_review.directory_for()/message_for()/_row()/semantic_targets()/evaluate()` | 有界视觉 B 问题、来源角色/quote 审验、合法具体化与供给待办判定、一次共享 Repair | 当前有 `execution_pending` 分流，但其他非 ACCEPT 缺少细分的可修责任类型；九例是否误拒须查证。不能把已有分流写成完全不存在，或把视觉审核宣称全模态审核 |
| `planning_wire.BIdentityProjection` + `planning_repair_evidence.RepairEvidenceProjection` | 显式 question_id、目标冻结短 Evidence Ref、无损 canonical 解码；R08 单次真实 Wire/Sources PASS | **保留，禁止在本工作包重做**；需验证新增 B 审查信息不破坏目标身份和原 Repair 消费 |
| `semantic_boundary_run.transport_identity()/run()/verify()` | 现有唯一 Journal @14/Checkpoint @14、冻结 scope/schema/call SHA、原回执冷验证 | 新 policy、A 决策绑定、B 审核与最终 Proof 必须一起冻结/冷重建；不能在已有执行中更换 policy |
| `semantic_boundary.project_proposal()` | `material+required → Need.intent.description`；`material+preference → preferred_visual_details`；其他 Condition → `intent.function`；保存 `proof.layouts` | 当前 `intent.function` 文本不自动构成 **postproduction Hard** 的实际执行证明；只允许经消费矩阵证实的承诺进入“已满足”结论 |
| `materials/application/matching.py` | `continuity_refs` 参与语义/导演/连续性加权匹配（连续性权重 0.20） | 分数不证明物理同一桌面、同一人物或已满足 Hard；不可将评分解释为硬保证 |
| `material_layer.py:798–825` → `hypit/workspace.py:179–184` → Native Authoring/Quality | 已有 source-bound `POSTPRODUCTION_REQUIREMENTS.json`，带 Plan/Attempt/Need/contract/原文片段，状态 `PENDING_AUTHORING`；Authoring 提示明确要求消费 | 复用此正式交接；`authoring_publication.validate_current()` 主要验证来源与发布身份，不等于逐条导演 Hard 的视觉履约。须核实实际消费能力，不能凭文件存在宣称已执行 |
| `truth_source_refs.py` | `supported_paraphrase / creative_expression / rewrite_required / unresolved` | 保持事实真伪边界；Director 创作自由不得进入“已证实事实”类别 |

**状态注意：**R02 原件、R05–R08 的隔离评测属于已发生证据；R08 的 7 个补丁与 9 个 B 批次引用验证 PASS，但余留 9 个非 ACCEPT，Truth 尚未准入。不能将 Schema/来源成功写成完整 Planning E2E。当前工作区已存在未提交的 P0 源码与测试，实施时应保留、对账，严禁覆盖或清理。

本文 R02 专指 P0 Task 的 `2026-10-14-real-minimax-p0-medium-s5-r02`（该记录为 14 次 HTTP），R08 指其后 `r08local20261015` 隔离 Repair；不与 Creator Task/Current State 保留的另一条 3 次 HTTP、A-details pending 的旧 `r02` 记录混用。历史结论按具名证据身份查证，本轮没有重跑或重判原模型回执。

## 2. 推荐的 Planning 内部最小合同

### 2.1 Delegation Envelope：程序推导，不由 A 签发

候选政策名：`planning-creative-delegation@1`。从本次已确认 Proposal、实际有效 Creator Context、冻结 Creative Mode/Mode Documents、Script/Scenes/Truth/用途与当前 Creation/Attempt 派生。字段**由程序生成并入冻结 `scope`**：

```json
{
  "policy": "planning-creative-delegation@1",
  "scope_ref": "<frozen-creation-and-attempt-context-hash>",
  "proposal_sha256": "<actual-confirmed-proposal-hash>",
  "creative_mode_sha256": "<actual-frozen-mode-hash>",
  "allowed": ["visual_composition", "shot_execution", "editing_expression", "bounded_visual_continuity", "aesthetic_choice"],
  "denied": ["change_confirmed_script_or_scenes", "invent_factual_claim_or_person_identity", "assert_rights_or_asset_available", "change_paid_or_publish_authority"],
  "boundary_refs": "<verified-snapshot-references>"
}
```

这是**本期视觉 Planning 的结构示意**，不是 Director 全部能力的白名单。实际字段由当前 `load_inputs`/`context_refs` 可得的不可伪造身份编译，不能使用字符串占位值写入产品。该确认后委托只允许将 HOW 具体化，不得声称 Creator 原始要求新增内容；需要新的用户决定时阻断并进入原产品的合法确认路径，而非自动新授权。**与额度、Provider 权限分离。**同一冻结 Mode 的通用规则可以跨作品复用，但 Envelope/Claim/Proof 绑定各自 Content/Proposal/Creation/Attempt，不能将上一部作品的水杯、桌面、人物或连续性选择写回 Mode 或迁入下一部作品。

### 2.2 Decision Claim（A 提议）与 Decision Proof（B/程序准入）严格分离

建议两层，不新增模型调用或独立 Agent：

- **A 的未授权候选声明 `DecisionClaim`**：`claimed_kind`（`confirmed_obligation|frozen_director_rule|director_local_choice|creative_preference`）、`creative_goal_ref`（已冻结 Scene/Mode 的枚举引用）、`reason`（简短创作取舍）、`claimed_strength`（必须与 Condition 实际 `strength` 一致）。这是模型提出的待审答案，**不是授权结果**。
- **程序及 B 的 `DecisionProof`（规划准入记录）**：由 `current Creation/Attempt + frozen input digests + need-slot/condition-index + Condition exact SHA + policy version + B question/reply SHA` 定位；记录 `authorized_kind`、实际 `basis`、`strength`、`responsibility`、`consumer_requirement`、`review_decision` 与 `issue_owner`。仅对本期视觉 Need 的 scope/modality/necessity/continuity 等 header 决策记录同等绑定；不得遗漏受影响的 Hard header，也不宣称未审音频获得了 B Proof。此记录证明本次规划选择通过了哪些审查，不是事实真值、Rights 或实际制作已完成的证明。
- `program_derived` 只允许应用程序根据冻结事实或已核实规则声明，不允许 A 自行选择。引用必须由程序编译合法枚举并按 scope 检查；`director_local_choice` 绑定授权的表达目标，不要求照抄不存在的“摄影手法原文”，也不允许将模型自述当成已确认事实。
- **坚持索引与身份分开：**模型不创建 Need ID、正式 SHA/path/operation；程序以原 A-selection + A-details 的 Slot/Condition 顺序定位，并持久化完整索引映射。任何条件删除、重排、文本、强度或责任更改都使旧 Proof 失效，须走原 B 审核/必要重查，不自动迁移。

**最小生产载体选择（待离线原型确认）：**让 `A-details` 的 **Wire-only 视觉** Condition 携带结构化 `claim`，而非直接修改 `MaterialNeed`、`NeedProposal` 的正式 JSON；先扩展 `StagedProposal.details_contract` 与对应 Encoder/Decoder，仅在校验 Slot/条件数量及 Claim 后抽出并存入现有 Owner state。Canonical A 仍是原 `SemanticProposal`，不能靠简单 `pop()` 洗掉未知字段。Header 待审行由程序绑定同一 A-selection 结果，模型实际理由来自原 `role/purpose` 或同次 A-details 中的有界声明；程序不从身份推断创作理由或授权类型。该设计**不增加第二次 A 请求**。先验证原始 Carrier 往返、最大容量和完整依赖；若比复用现有载体无明确收益，收缩新增字段，不能预先称其为已证实的最优方案。若要求改 `SemanticProposal`，须重新做合同影响评审。

**Repair 必须与 Claim 原子交接：**当前 `planning_semantic_review.patch_schema()/apply_patches()` 返回原 Condition/NeedProposal，尚无 Claim。新政策须让**同一次既有 Repair Wire** 对已授权的视觉条件、Header 或新增视觉 Need 返回变更值及相应新 Claim；Canonical 补丁仍保持原类型。程序严格校验后同步保存新旧映射，未变目标沿用原记录；受影响的 Claim/Proof 与 B 题目签名失效并进入原 recheck。仅 Claim、授权依据或政策变化，即使文本未变，也不能复用旧 ACCEPT。无法安全产生新 Claim、需要改越权路径或共享预算已耗尽时拒绝；不能由程序补理由或额外调用 A。冷恢复从原 A/Repair 字节复算全部绑定，不能继承已失效 Claim。

### 2.3 B 问题类型及审查输出

保留现有视觉问题的覆盖义务、8 问批次、原 `ACCEPT|CHALLENGE|UNRESOLVED` 以及显式 `question_id`。题数随合法候选/场景变化，不冻结为历史 72 题，也不隐式扩到声音审核。由程序为相关问题绑定适用的 `review_axes`；同一复合条件可同时涉及事实、委托和责任，不能只审一个轴便放行整个条件：

| `review_axis` | 应检查的含义 | 可以接受的依据 | 失格示例 |
|---|---|---|---|
| `confirmed_fidelity` | 已确认事实/动作/规格是否被保留且不冲突 | 真实确认来源与适用 Mode | 修改已确认 Script、将音轨模式改为静音 |
| `delegated_creative_validity` | 新 HOW 是否符合委托、能服务场景、强度是否合理 | 冻结目标/Mode + 独立导演理由；不要求逐字包含新手法 | 把“偏冷”谎称 Creator 明令或无合理性设为素材 Hard |
| `responsibility_enforcement` | Hard 究竟由 Material / Native Authoring / Quality 谁执行/验证 | 已证实的消费者能力及合法责任分类 | `intent.function` 文字=已完成剪辑 Hard；continuity score=物理同一 |
| `coverage_uncertainty` | 确认义务是否被覆盖，未知属于 Creator/Director/Material 谁 | 冻结完整候选与真实缺口 | 将未找到素材误写为 Creator 未授权；把新增同-source 假设当真义务 |

实施首选只为被该政策命中的 B 题型增加**有限枚举** `issue_code` 和 `issue_owner`（原 `decision` 不变）；由 `directory_for/batches/message_for` 冻结题目身份及可选范围，`_row` 严格核对 `decision × issue_code × issue_owner`。**不靠解析自由 reason 推断决定**，也不额外增加一轮 Reviewer。未受影响的问题保持原语义与输出形状；修改 `CandidateAnswer` / `patch_schema()` 须同时更新 BIdentityProjection、RepairEvidenceProjection 和原回复验证，不能让一个非法 B 结果靠新标签改判。

**业务分流只允许：**`creator_decision_required`（阻断、不能用原 Repair 自行确认）；`director_replan_needed`（明确 A 候选可修的强度/责任/越界问题，原一次 Repair）；`material_supply_pending`（已有合法 MaterialNeed，但素材/权利事实待下游确认；不得写 MATERIAL_READY）；`source_or_truth_violation`（拒绝或依既有可修范围处理）。D0 还须明确无问题结果的编码及合法组合：`ACCEPT` 表示本题规划审查通过，供给待办仅按现有完整 Need 覆盖与来源规则登记；`CHALLENGE/UNRESOLVED` 不能靠附上 pending 标签改判。资产的许可证据尚待供应与 Creator 是否授权某种用途/人物使用是两件事，后者缺失不得移交成普通供给待办。这些是 Planning 审核问题类别，**不等于新的 Creation 状态或 Material Domain 枚举**。

### 2.4 强度 × 责任 × 下游消费者矩阵

| 决策与强度 | 载体/消费者 | 可被证明什么 | 当前实施策略 |
|---|---|---|---|
| Creator Hard + `material` | 原 MaterialNeed `intent.description`/正式 `constraints` → Supply/Observation/Match/Readiness | 必需**原素材属性**可观察且准入 | 保持原合同与 Gate，不能降级 |
| Director Committed Hard + `material` | 同上，但 Proof 标注“本次 Director 承诺” | 必要源属性可被独立观察并最终匹配 | 只有 B 与实际观察能力均成立才允许 Hard；否则 A 应修正为偏好/合法其他责任或拒绝 |
| Creative Preference + `material` | 现有 `preferred_visual_details` / ranking hints | 导演倾向，不能作为硬满足证明 | 保留可替代、不触发虚假 MaterialGap |
| Director Hard + `postproduction` | Planning Proof → **正式 Native Authoring / 可观测的 Hypit AST 或 Quality 消费** | 可以观察的剪辑/镜头选择是否执行 | 必须在 D3 证明入口、验证规则及失败分类；仅写 `intent.function` **不等于 PASS** |
| Director Hard + cross-shot continuity | Planning 决策证据 → 正式已选资产关系/Authoring/Quality | 真实已验证的身份/连续性关系 | 现有 `continuity_refs` 是软评分，不能当 Hard；缺真实观测机制则拒绝 Hard 而保留合法视觉意图 |
| Narrative/Truth | 原 Script/Truth Packet → `truth_source_refs.py` | 事实/创作表达可独立分类且不能伪造来源 | 继续原 Truth，不由 Planning 代替“事实支持”审核 |

**高风险闭环规则：**在 D3 未核实具体消费者前，**不放行新的不可执行 Hard**。不能因为希望“先出片”，把 Hard 偷换为 preference；任何显式降级都应是新 A 候选、被 B 接受且保留旧候选历史的结果。也不能要求 Material 把高分匹配冒充同一实物保证。

**分清两个时点：**Planning 准入检查委托、义务与消费者**能力/责任合同**，可以保存“要求确定、实际执行待办”的 Plan/Proof；不要求此时已有 Asset/Build/Output/selected output SHA。素材观察、Native Authoring、Quality 及人工 Review 在原阶段产生**履约结果**，引用原 Plan/Proof 并绑定当时实际 Asset/Output SHA，不回写被冻结的 Planning Checkpoint。已有消费能力但尚未供应不等于不可执行 Hard；没有合法消费者且无法履约才是合同缺口。纯审美效果保留给原 Quality/Creator Review，不将所有风格偏好升级为程序可客观证明的硬约束。

## 3. D0–D4 实施顺序（同一子工作包，不新增生产 Gate）

每个 D 编号只是**同一 Planning 子工作包**的交付检查点，不是新的正式 U Gate。逐段修改、逐段验收，不并行改动所有生产层。

### D0｜合同边界、历史回归与跨内容验收表（代码改动前）

**前置：**本文架构边界获用户确认；如正式改变职责/冻结合同，应按 `AGENTS.md` 在实施前进行关键架构复核。无需真实模型。

1. 从 R02 原件读取九个 `question-0002/0004/0007/0034/0036/0041/0065/0066/0068` 的完整 A 条件、Mode Documents、B 决策及真实 source；保留 SHA。生成**独立验收矩阵的 fixture**，绝不改写原 response.json。
2. 冻结 Delegation Envelope 的可选 HOW、禁止 WHAT、合法 Hard 提升标准和 `enforcing_consumer` 列表；确保当前已确认 `Script/Scenes/Audio/Rights/Budget` 无隐式增权。
3. 明确 B 的 `issue_code/issue_owner` 枚举、合法状态组合和未知责任表；审美自由 ≠ 修改事实，Material 尚未供应 ≠ Planning 语义未知。
4. 对每个测试样本至少构造 **同一镜头的正反变体**：合法导演选择可以独立获得准入；越界、过强、错误消费者或虚构事实必须拒绝。
5. 在代码改造前盘点 D3 的既有消费者能力，把“能传递意图”“能客观核验”“能语义/人工审阅”“暂未支持”分别写入能力表；D1/D2 依据此表设计，不能先签发 Hard 再找消费者。这里只盘点和冻结期望，D3 才补必要接线与集成验证。

| 冻结例 | 必须通过的对照 | 必须拒绝的对照 |
|---|---|---|
| 0002/0004 | 为已确认水杯动作选择可观测的连贯呈现，并说明哪部分属剪辑 | 删除接触事实、禁止性编辑要求被伪装成原素材事实且无 Authoring 消费 |
| 0007 | 资产复用作为可选择的 Authoring 策略 | 假定跨场景使用同一授权来源已获用户批准 |
| 0034 | 保持**真正空桌面**，允许 Director 增加构图留白 | 用“基本归位但非空”替换确认的空桌面、用负空间覆盖事实冲突 |
| 0036 | 保留“窗光更明显”，允许局部色温取舍 | 将 Mode soft 低饱和自动升级为冷色调原素材硬要求 |
| 0041 | 收尾天色安静，导演选择柔和曝光偏好 | 将“明亮不刺眼”宣称用户 Required，或缺消费者却设不可替换 Hard |
| 0065/0066/0068 | 允许建立跨镜**视觉**连贯意图；Material 真实供应/Rights 未知被移交下游 | 假定同一物理桌面/人物/授权来源已被确认、重复报告在无验证情况下消失 |

**同一导演、不同内容的必需对照：**复用合法 Proposal @4、冻结有效 Creator Context 与同一套完整 Mode/导演规则，至少选三个不同主题（对齐视频架构 §51 的 3–5 主题目标，例如 AI 学习、工作实践、生活观察；用获准原文或明确标注的合成测试内容，不编造真实个人经历）。每个主题独立 Content/Proposal/Creation/Attempt，各自 Truth 及意图有独立期望，不复制 R02 镜头：

| 验收维度 | 必须通过 | 必须拒绝/区分 |
|---|---|---|
| 内容开放性与确认保真 | 主题、论点、叙事/镜头可以不同；确认后各自原文、声音方案与事实边界保留 | 把同一水杯/空桌面/场景顺序强加给所有作品；确认后改写观点或动作 |
| 同一导演的稳定表达 | 共同继承冻结叙事姿态、视觉语言、声音/字幕/节奏规则；对本题材作合法具体化 | 用某部作品的局部 choice 改写 Mode，或只对比 Mode SHA 就宣称风格稳定 |
| 条件强度与真实来源 | 每例独立判断确认义务、合理 HOW 与可替代偏好，不要求逐字存在新手法 | 凭真实 quote 放行不相关条件、把软风格升 Hard、创造人物/经历/Rights |
| 跨作品隔离 | 只复用通用 Mode/政策；Claim/Proof/Scene/source 均重新绑定本作品 | 将作品 A 的确认事实、许可、决策 Proof/已选资产关系当成作品 B 的授权 |
| 消费传递 | 已知要求交给原 Material/Authoring/Quality；供应待办正常保留 | 无 Asset/Output 就宣称完成，或要求先有最终视频才保存 Planning |

**D0 Done：**历史九例有 *授权、强度、责任、B 结果、消费者* 的独立正反期望，跨内容矩阵覆盖至少三个主题；不要求九例一律改判 ACCEPT。既有合同内的普通导演选择不逐项要求用户重新授权；只有真正改变冻结权责、确认内容或缺少必要用户决定时，才走对应批准/确认路径。此时完成的是验收设计，尚未证明跨作品成片风格稳定。

### D1｜A Decision Claim → 冻结 Planning Decision Proof

**影响代码（预定，不表示已经实现）：**

- `easel/integrations/planning_authority.py`：添加纯函数从实际 `load_inputs()`/`catalog()` 生成 `DelegationEnvelope` 与合法 Scene/Mode 锚点；沿用已有来源资格与 scope 规则，不让 A 产生路径/hash。禁止引用 `derived_preparation` 自证 Creator 新授权。
- `easel/integrations/planning_staged_proposal.py`：仅在 **新 A-details 的视觉 Wire** 中嵌入 Condition `claim`，保持现有 header/details 拆分、四-slot 批次、索引和严格 `additionalProperties=false`；严格校验并移除 wire 元数据后将**原 canonical Condition** 交 `SemanticProposal`，元数据同步写入冻结候选记录。D1 原型同时定义 §2.2 的 Repair Carrier，D2 才接入调度。恢复以原 A/Repair Tool 字节编译，不能从“已处理后的 canonical”伪造历史 Claim。
- `easel/integrations/planning_input_view.py`：复用 `SourceSelection` 的冻结 source handle、input-view SHA、真实 Mode/Creator 引用；产生程序拥有的 `need/condition` 位置与原始值 digest。
- 可新增一个 **Planning 专用**模块，例如 `easel/integrations/planning_creative_authority.py`：定义 `DelegationEnvelope`、`DecisionClaim`、`DecisionProof` 的最小类型、无副作用校验、身份摘要与合法关系；禁止新增 Workflow/Provider/Material Domain 对象。
- `easel/integrations/semantic_boundary_run.py`：A-selection 完成即冻结已有选择身份，A-details 真实原响应与 Claim 一并保存；`state.scope/transport/schema_bindings` 固定新 policy/version。A 只提交候选，Proof 要等 B 审核后才能成为 `ACCEPTED`；拒绝时不能发布/降级。

**硬性测试：**

1. 一条 Condition 的 `text/strength/responsibility/meaning` 和 `claim` 同批原样捕获；重复、缺失、未知字段或跨 slot 绑定均拒绝；同一 A 输入的正向 schema 编码/解码完全无损。
2. A 声称 `program_derived`、声称 Creator/Mode 未有的新授权、未注册 Scene 引用、`claim` 与强度相冲突时拒绝；一个合法 Director 手法不因缺少逐字原文而被程序机械否决，仍须进入 B 复核。
3. `A-selection` 的视觉必要性/连续性候选仍具备独立 Review 题目，不被 Condition-only Proof 漏掉；声音沿原合同验证，不伪造新 B 回执。
4. 对冻结上下文、Condition 顺序、具体文案、Claim、Mode SHA 和 Policy 的任意改变必须导致身份变化；B 问题/recheck 签名纳入这些依赖，旧 Claim/Proof 不可复用。验证同一次 Repair 的“替换值＋新 Claim”无损往返，以及遗漏/跨目标/沿用旧 Claim 的拒绝。
5. 完整 A-selection → A-details（三批或实际批数）→ Assembly 对当前合法 fixture 通过；不修改旧 Attempt，也不覆盖先前有效捕获。

**D1 Done：**本期每项视觉候选决策都能确定性定位到 `Need + Field/Condition`、Creator/Mode 冻结范围及待审 Claim/Header 行；当前 `SemanticProposal`/MaterialNeed 保持原正式字段，声音保持原责任。跨内容合法载体能往返，原始 A 与 Repair Carrier 都有完整可追溯绑定。新增字段的大小/容量须记录；真实响应耗时与模型适应性尚未验证，不能以离线 PASS 冒称可靠性提升。

### D2｜B 分类审查 + 一次 Repair 调度（不能以 Prompt 代替类型）

**影响代码：**

- `planning_candidate_review.directory_for()`：将 D1 的视觉决策/Proof 候选按现有 `visual_choices/complete_obligation/need_necessity/unresolved_classification/coverage` 生成带 `review_axes` 的冻结问题；不删覆盖义务、不靠 A 选择来源过滤问题。`planning_semantic_review.recheck()` 的完整问题签名必须含当前 Claim/政策/依赖绑定，防止仅元数据变化时错误复用旧 ACCEPT。
- `planning_candidate_review.batches()/message_context()/message_for()`：继续共享完整候选与冻结证据；在必要题型的 `response_schema` 中增加有界 `issue_code/issue_owner`，`decision` 仍唯一，原 `B Identity` 显式题目身份保持不变。对合法 creative choice 审“关联、委托、合理性”，对 fact 审“真实支持/不冲突”；区分来源有效与语义蕴含。
- `planning_candidate_review._row()/decode_answers()`：增加组合校验，`CHALLENGE/UNRESOLVED` 不允许直接被另一个泛化 reason 改成 ACCEPT；不可冒充 Materials/Creator 已批准。无消费者的 Hard 必须拒绝其强度/职责，不只是记录说明。
- `planning_candidate_review.semantic_targets()`：先**完整收集并分类**全部冻结 B 答案，不再把第一个 `UNRESOLVED` 当作所有情况的唯一错误；`creator_decision_required` 仍硬阻断，`material_supply_pending` 只能在已存在合法 Need 并且未知只是供应事实时移交，`director_replan_needed` 只进入原共享 Repair 的可修目标。任何分类错误 fail-closed。
- `planning_candidate_review.evaluate()`：保留原唯一 `fix()` 及 `repair_used`。在有效 B 结构具备的前提下再处理语义目标；若结构修复已耗尽额度且语义仍需修改，**明确拒绝**，不秘密添加第二笔修复、不强行改判。避免新增独立 Owner 或修改 OpenClaw 全局调用路由。
- `planning_candidate_review.patch_schema()/decode_patch_slots()/apply_patches()` 与 `planning_semantic_review` 的原补丁入口：落实 §2.2 的“替换值＋新 Claim”Carrier，仅对授权的候选目标变更，禁止修其他已接受答案、删除 confirmed condition、改变 Creator 已确认内容。当前 Need necessity 修复只允许有依据的 optional→required；本包不默认新增 required→optional 权限。Condition 强度/责任能否修正须逐目标符合原可修边界，不能以新增枚举扩权。对含 B support 的原修复目标继续使用 `RepairEvidenceProjection(local-ref@2)` 并做差分验证；Claim 不能伪装成 source/role 证据。

**高风险执行规则：**当前 `semantic_targets` 对非 ACCEPT 会中断或形成 Repair target，不能为了加速出片把所有 CHALLENGE 变为“Material pending”；Material pending 只表示**创作目标已确定但素材/权利事实未供应**，不是 Director 还没决定表达、或原始用户授权缺失。**一次 Repair 的含义始终是一次，结构与语义无法安全合并时维持失败**，下一新 Attempt 通过更好的 A Carrier 质量减少此情形，不把失败旧 run 复活。

**D2 Done：**九例分类正反变体及至少三个不同 Content 的规划矩阵通过；原 B 每批最多 8 题、来源/角色/quote、权威引用 `contains` 及 Repair 精确 target 仍成立。覆盖 Claim-only 变化触发重审、原 Repair 更新 Claim、预算耗尽和跨作品引用拒绝；原离线 `A→B→Truth` 合法 fixture 与原回执冷恢复通过。实际 B 仅覆盖视觉，声音与 Truth 的原 Gate 不因本包 PASS 被替代。

### D3｜复用消费者交接并验证能力（不修改 Material V1.3 Domain）

严格区分三种 Required：

1. **素材 Hard**：以现有 `semantic_boundary.project_proposal()` → `MaterialNeed.intent.description/constraints` → `planning_contract.bind_requirements()` → Material Observation/Matching/Readiness 验证；Rights UNKNOWN/RESTRICTED 仍 BLOCK，缺素材仍 `MATERIAL_NOT_READY`。偏好仍是偏好。
2. **剪辑/叙事要求**：复用 `intent.function` → 正式 requirements contract → `material_layer.py` 的 `POSTPRODUCTION_REQUIREMENTS.json(PENDING_AUTHORING)` → `hypit/workspace.py` → Native Authoring/Quality。对音轨、时间轴、Source 选择等客观条件核对实际程序检查；对审美/叙事效果使用原 Quality/Creator Review 的适用审阅证据，不能声称 Hypit check 已证明画面语义。合法导演意图可以待执行、待审阅；**不能客观自动证明不等于创意越权**。但要承诺 Hard，必须有明确的执行方、验收方式及失败处理；仅有 Prompt 或文件不足以宣称满足。`authoring_publication.validate_current()` 的身份/发布检查不能替代语义验收，不新增自行签发 READY 的路径。
3. **跨镜头连续性 Hard**：`continuity_refs` 只为候选排名/线索；同一素材 SHA/同一真实 identity/可靠画面观察以及实际 Authoring placement 必须按要求分别证明。若只能证明词汇重叠或评分相近，禁止标记物理连续 Hard 为满足；可用视觉连贯 soft preference，不改变用户声明的真 Hard。

**落实方式：**Planning `DecisionProof` 冻结 `enforcing_consumer`、`requirement_ref`、计划的验收方式及 `plan_id/attempt_id/context_refs`，此时执行结果仍待定。既有 Material/Authoring/Quality 回执在各自阶段引用该冻结身份并绑定实际资产/产物 SHA，人工 Selection 再绑定所选输出；不向原 `SEMANTIC_CHECKPOINT.json` 回填未来证据。新增映射优先进入已有 Proof/requirements/交接载体，若现有载体无法闭合，说明具体缺口再决定必要接口改动，不增平行 Proof 服务或制作 Owner。

**D3 Done：**Material 要求、后期要求、连续性三类均有具名的能力/交接证据；本期支持的类型以真实内部消费者的离线集成证明合法传递、正确拒绝与适用验收，暂不支持的 Hard 用明确阻断证明，**不强制为凑三个正例扩建视觉识别**。负例覆盖虚构 Rights、无真实 Match、无适用 Authoring/Quality 证据、仅 continuity 评分及跨 Attempt/Output SHA 篡改。另须证明“尚无资产/输出的合法 Plan 可保存并交接”，防止循环前置。Truth 保持独立，最终 Creator Review 不被替代。

### D4｜原 Owner 软件闭环与正式主线衔接

**前置：**D0–D3 完成、必要架构变更正式同意、新版本 Policy/Owner/消费者证据一致；没有从离线阶段自动取得付费/制作授权。

1. **先纯离线软件测试**：当前合法 Proposal @4 → Preparation/Handoff → 新 A-selection/A-details Claim → B 分类 → 一次 Shared Repair 或零 Repair → 原 Truth → MaterialPlan/Requirements/DecisionProof → PlanningIntegration.load/verify → 真实本地消费者。覆盖无 Repair、合法 Repair、B 原回执异常、UNKNOWN、冷加载、映射/Policy/Version/Mode/Condition/Consumer 篡改与换版拒绝。
2. **接回既有 U4/U5 主线**：离线软件回归完成后，按同版 U2/U3-S/U4 和对应授权，由唯一 Delivery Owner 推进合法 Web Creation。实际生产请求冻结新 Schema/Mode/模型/操作身份，不恢复旧失败 Attempt；记录完整 Planning/Truth/Plan 及后续链路首个真实阻塞。旧 Candidate 指纹不得复用为已更新版本资格。
3. **隔离模型实验仅按需**：若仍有具体且无法由现有证据判断的模型兼容/语义风险，可在已有对应授权内或单独获准后做新身份、有界的 MiniMax 实验，保留全部结果。**它不是 U4/U5 额外必经 Gate，也不是固定十样本前置。**不得把局部 Wire/来源 PASS 或独立 Eval 记作 Web E1。失败分层记录 `transport / wire / source / delegated_decision / semantic / downstream_consumer`。
4. **跨作品产品验收**：D0 的同 Creator/Mode、3–5 主题目标最终接回获授权的正式作品与 Creator 审阅，分别记录完整成片、内容差异和风格一致性。它是原产品成功标准的追踪，不要求首条 U5 Debug 前先做多部视频；本次文档评审与离线矩阵不冒充已出片或产品稳定。

**D4 软件 Done：**至少三个不同 Content 经原 Owner 的合法离线实例完成 A/B/Truth/Plan 保存与冷加载，保持同一 Creator/Mode 和各自内容；每个已准入 Hard 有具名消费合同，实际履约允许处于对应的后续待办阶段。事实伪造、Hard 越权、版权未知和无有效回执的负例正确拒绝。**真实链路与跨作品产品 Done 分别记证**，仍需原 U0–U6/产品验收和真实授权；软件 Done、一次模型 PASS 均不等于真实稳定或成片风格已验证。

## 4. 文件级实施清单与依赖约束

| 包 | 推荐改动位置 | 必须同步验证 | 禁止事项 |
|---|---|---|---|
| D0 | 本方案、现有 P0 Task 的 R02 冻结用例、已有合法 Proposal fixtures | 九例回归 + 同 Creator/Mode 至少三个 Content 的矩阵；消费者能力盘点 | 改历史原回执、固定所有作品模板、改正式状态或 Roadmap Gate |
| D1-1 | 新纯函数 `planning_creative_authority.py`、`planning_authority.py`、`planning_input_view.py` | 来源资格、scope/sha、真实 Mode、cross-slot 负例 | 新 Creator/Director DB、模型自签授权 |
| D1-2 | `planning_staged_proposal.py`、`semantic_boundary_run.view_a_message()/run()/verify()`、原 Repair Carrier | 视觉 A/Repair Claim、原始 Tool、Assembly、冷恢复；声音原合同保持 | 额外 A 模型调用、生成式填充缺失 Claim |
| D2-1 | `planning_candidate_review.directory_for()/batches()/message_for()/_row()` | 九例 B 分型、原 8 问批次和身份绑定 | 新 B Agent、降级 `quote`/角色/`contains` 校验 |
| D2-2 | `planning_candidate_review.semantic_targets()/evaluate()/patch_schema()`、`planning_semantic_review.recheck()/apply_patches()`、现有 Evidence Projection | 共享 Repair、新 Claim 与依赖签名、可修/不可修混合、预算耗尽及冷验证 | 隐式第二次 Repair，复用失效 Claim/ACCEPT，改写历史失败 |
| D3-1 | `semantic_boundary.project_proposal()`、现有 `proof.layouts`、`planning_contract.bind_requirements()` | Required/Preference 逐项等价及 Material Gate 拒绝 | 改 MaterialNeed Domain/V1.3，偏好分数冒充硬满足 |
| D3-2 | `material_layer.py` 既有后期要求交接、`hypit/workspace.py`、`hypit/authoring_publication.py`、`hypit/quality.py` 的必要读取与校验 | 待执行义务传递、适用的 SVML/Run/Output 验证、语义/风格审阅边界 | 平行 Authoring/Build Owner，回写 Planning 冻结 Proof，仅靠文字证明画面 |
| D4 | 原 Owner、`tests/test_semantic_planning.py`、`tests/test_material_integration.py`、`tests/test_creation_preparation.py` | Proposal @4→A→B→Repair→Truth→Plan/Checkpoint 与软件消费者 | 旧 Attempt 重新启动、擅自付费/Provider/Build/U5/U6 |

**范围控制：**优先复用现有 Planning/Proof/后期交接，确有必要时至多增加一个 Planning 纯函数模块；其他变化集中在现有函数边界。D3 若发现 Hard 没有适用消费者，则显式阻断，或在原修复权限内生成新的合法候选；不把新 VLM、多个 Agent、Material V1.3 改造作为默认前置，也不因审美不能程序证明就否定合法创意。阶段实施按当前工作区差异增量对账，保留所有已经存在的 P0 源码和测试。

## 5. 版本身份、存储与冷恢复

- **版本批准前：**本方案 `@1` 均为候选名。实现时冻结新 `creative_delegation_policy`、`decision_claim_policy`、`b_review_authority_policy` 及其 Hash；以当前真实 `VIEW_JOURNAL/VIEW_CHECKPOINT`、`transport_identity()` 与 `validate_transport()` 为准，新合同采用新版本/新 Attempt，**不能改变正在运行的旧身份**。
- **A 输入：**首次新请求前持久化当前 Proposal/Mode Context SHA、A-selection 身份、A-details 的政策与 Schema SHA。原请求、原始响应、视觉 Claim 一起绑定，不得把处理后的 Canonical 当作原始模型回执；跨 Content 只能共享通用规则，不能共享作品授权或 Proof。
- **B/Repair：**`question_id`、`review_axes/issue_code/issue_owner`、Decision Proof、原 B 回执与 `schema_bindings`、Repair Evidence Ref mapping SHA 一起冻结；原 Repair 回执中的新 Claim、替换值、新旧目标映射与 recheck 依赖签名同步保存。重新加载须复算完整绑定，不能从最新版 Prompt/Mode 组装旧 Proof，也不能在仅 Claim 改变时保留旧 ACCEPT。
- **Checkpoint：**`SEMANTIC_CHECKPOINT.json` 记录经过 B 准入的 Proof 与原回复身份；`semantic_boundary_run.verify()` 从 Handoff、A/B 原件复算后核对。`Input/Mode/Proposal/Condition/strength/role/Proof/policy/schema/mapping/reply SHA` 改动应拒绝。
- **下游：**规划阶段的 Hard 绑定 `plan_id/attempt_id/need_id`、正式消费者、验收方式与待办义务；**不包含尚不存在的最终 Output/Selection**。后续实际结果在既有 Material/Authoring/Quality/Review 回执中单向引用原 Proof/Plan 与当时实际 SHA，不回写冻结 Checkpoint，不让 Hypit Agent 重建导演授权。`pending` 可作为合法 Planning 交接状态，但不得被提升为 MATERIAL_READY/Quality READY。
- **失败与历史：**`PENDING/SUBMITTING/UNKNOWN` 原操作只对账、不自动重派；旧 R02/R05–R08 与原 Web Attempts 保留字节和 SHA，绝不迁移或补写业务成功状态。不为旧版构建新的并行生产兼容路径。

## 6. 验收判定与必须停止的条件

**允许进入下一包的共同条件：**

1. **D0**：九例 **9/9 有独立正反例**，并有同 Creator/Mode 的至少三个 Content 对照；合法导演选择不能因没有字面脚本证据而机械拒绝，确定的 Creator 事实冲突必须拒绝。Source/Mode/Scene 基础证据不可模型伪造，单片局部 choice 不变成下一片的规则。
2. **D1**：本期视觉 Slot/Condition 可定位到明确 Claim，视觉 Need header 没有漏审；音频原合同不冒充新 B 审核。Claim 不凭模型提供 ID 就能匹配原值。未涉及的新旧正式 MaterialPlan 等价，文本/强度/责任/Claim/Mode SHA/政策改变使旧 Proof 与相关 ACCEPT 失效。
3. **D2**：B 分类严格、所有非法事实、授权越界、不可消费 Hard 拒绝；正确区分 Creator 决策、Director 局部修正、Material 供应 pending。全部 Repair/重查都受**既有唯一共享预算**约束。
4. **D3**：所有本期准许进入 Plan 的 Hard 类型有正式消费者及适用验收方式；待供应/执行与“无消费者能力”分别记录。不能验证的已确认 Hard 仍阻断，不默默降级；纯审美交原 Quality/Creator Review，不伪装程序证明。缺能力类型可用明确 BLOCK 完成负例，**不强制**扩建视觉识别或重写 V1.3。Planning 保存不依赖未来产物，后续结果不反写原 Proof。
5. **D4**：跨内容合法离线实例的 A→B→Truth→Plan 保存/冷加载及交接通过；真实作品的生产/风格结果须另有原链路证据。独立 MiniMax 样本不是 U4/U5 附加前置，真实稳定性也不以 R08 一次 Wire PASS 或软件矩阵推定。

**立即 STOP 并上报的情形：**

- 实施需要修改已确认 Proposal @4 的 WHAT/Truth 真值、MaterialNeed 输入输出或新建并行 Director/Workflow Owner。
- 一个新增 Required 的执行责任、失败返回或真实消费边界仍不明确，却准备宣称其已满足。
- 要在历史失败 Attempt/R02/R08 回执上补写授权、模型语义或素材事实。
- 必须通过删除 confirmed 条件、隐式第二次 Repair/新付费、放松 Rights/Gate 才能使测试通过。
- 新 Claim/Proof 允许 A 自证其授权，或破坏原 Schema/Checkpoints/权威来源 `contains` / 冻结 ID 映射。

## 7. 评审决定、批准边界及下一动作

**本轮只评审并修正文档，未取得代码实施授权。** 后续从 D0 的历史/跨内容矩阵及既有消费者盘点开始，D1 原型验证 Claim/Repair 的必要性与往返后再接入 B；涉及冻结权责变更时按现有规则取得批准。文档评审、代码实施、真实模型和制作授权分别核对，不要求用户对既有合同内的每个普通导演选择反复证明授权。

| 维度 | 本轮评审结果 |
|---|---|
| 产品目标契合 | **修订后目标对齐，效果待验证**：确认前自主创作、确认后忠实细化；同 Creator/Mode 服务不同 Content；跨作品风格仍需实际成片证据 |
| 代码复用程度 | **CONDITIONAL**：原 `planning_authority`、A/B、SourceSelection、Proof、Owner/Checkpoint 可复用；A Claim Wire 与消费者需离线实证 |
| Material V1.3 兼容 | **CONDITIONAL**：正式 Domain 不变，不允许新增 Proof 逃逸消费与 Rights Gate |
| R02 九例 | **可归因、可建正反例**；历史结果不自动改判或冒充已修复 |
| 当前实施 | **NOT_STARTED**：本轮只有实施方案，没有实施代码、模型调用、正式 ADR 修改或运行状态推进 |
| 下一单一动作 | **待实施授权后执行 D0：冻结九例回归、跨 Content 双向期望和既有消费者能力表；本轮暂停** |

**2026-10-15 文档复核记录：**以当前 `easel-studio / d82bb60b07240a3dd0d776ec00a33c68f71cab50` 加现有 dirty 为只读代码依据；原稿未直接通过，Main 与独立 Astra 复核指出并修正：跨内容验收遗漏、根因表述过强、视觉/音频审核范围混淆、Repair 新 Claim 缺口、Planning/履约证据时序混用、已有后期交接漏列及独立实验前置风险。本记录只说明文档设计纠偏，不改变已接受 ADR、生产状态或 R02–R08 历史结果；未运行模型、制作或代码回归。

**修订版复核结论：`DOCUMENT_REVIEW_PASS`，Astra `DECISION=CONTINUE`。** 可用于后续实施准备；D0 的合法组合/能力表与 D1 Carrier 原型仍待执行，文档通过不表示产品通过或获准修改冻结架构。

```text
RESULT = COMPLETE（仅文档评审与修订）
DRIFT = NO_DRIFT
EVIDENCE = 需求/架构/现行代码交叉核对；修订版 Astra CONTINUE；仅本文件变化，其他 dirty 与 HEAD 保留；git diff --check PASS
LESSON = 同一导演须跨内容验收；规划准入与实际履约按阶段分别取证，局部回执通过不等于产品目标完成
NEXT_SINGLE_ACTION = 待实施授权后执行 D0 的历史/跨内容验收矩阵及消费者能力盘点
TRANSITION = HOLD（本轮文档范围已完成，暂停）
```

本方案属于唯一 Creator Task 的 Planning 内部子工作包；**不能**被视为另一个 Goal、U4/U5 的替代准入标准或真实模型/Provider/Hypit Build/Release 的执行授权。若需要修改 CURRENT 架构/ADR 的冻结权责，先取得相应批准，再按已批准的唯一标准推进。

## 8. D0｜2026-10-15 冻结验收矩阵与代码消费能力（本轮执行记录）

> **范围：D0 验收设计/离线盘点，不是 D1–D4 生产实现。** 分支 easel-studio，起点 HEAD d82bb60b；启动时已有 19 项 dirty，必须保留。R02 身份专指 2026-10-14-real-minimax-p0-medium-s5-r02；R08 为 r08local20261015。历史 B/Repair 结论不改写。九例原始 B 回执已逐项对照，部分 A 条件的**完整原文、强度、责任和 SHA 尚未逐项成功提取/独立冻结**，下表将已证实与待核查分开，不能冒充 D0 9/9 完整归档。

### 8.1 共同委托边界与事实来源

- 冻结 WHAT：Proposal @4 已确认的 Script / 7 Scenes / Treatment / 声音方案、Truth、Creator 身份、真实授权范围；例如 R02 分镜 2「手把水杯挪回杯垫、轻放」，SFX「嗒」；分镜 6「空桌面、台灯灭后的轮廓、窗光更明显」；分镜 7「桌面边缘与窗外安静的天色」。这些真实来源优先于新视觉取舍。
- Frozen HOW 规则：Mode/Director 可以约束表达语言，但不是全部实物和摄影参数的穷举合同。项目 clear_memo_video v1.3 示例的克制、低饱和、普通人观察立场属于风格，不自动蕴含「偏冷」「明亮不刺眼」「同一桌子/真人」等 Creator Required，也不冻结所有作品的题材/脚本。
- 确认前 Director 可决定题材、论点、结构和镜头；确认后只可在每一独立 Creation/Attempt 中细化已经确认的 WHY/HOW，不改 WHAT/Truth/声音、不得签发 Rights/素材存在/付费授权。软表达可记录 preference；导演自选 Hard 需要必要性、独立 B 判断和具名实际消费者，且只属于当片。
- 原 B 回执保存 CHALLENGE 8、UNRESOLVED 1；R08 7 个修复目标与这些九例不同。下述「可接受」均为下一次新 Attempt 的**条件性正例预期**，**不是重新解释或写入历史 ACCEPT**。原 R02 总 72 题在 R08 局部补丁之后 63 ACCEPT / 8 CHALLENGE / 1 UNRESOLVED，Truth 未准入。

### 8.2 R02 九例正反验收矩阵（逐题冻结 B 决定，不伪造 A 原文）

| QID / R02 B 实际判断与依据 | 已确认义务 → 合法导演空间 | 原 A 候选：已知强度/责任与核验缺口 | 新合同预期；必须接受 / 必须拒绝 | 后续责任 |
|---|---|---|---|---|
| **0002 CHALLENGE**；B 指出「动作跟合上一词同步」可追溯，但「全程不遮挡、不得剪辑跳过接触」是新增剪辑禁令（B-000，source-0000/context、source-0009/context） | 水杯实际移动与落下是确认动作；镜头连续可见属于 Director 拍摄/剪辑 HOW | 涉及禁止遮挡/剪掉接触的后期 Hard 候选；**准确 Condition.text/strength/responsibility/SHA 待原 A 完整核对** | **接受**：动作真实且可见，若导演确有必要的连续剪辑 Hard，绑定 Authoring 的可观测执行+Quality 帧证；**拒绝**：删去移动动作、伪称原文禁止淡出、把剪辑 Hard 当源片材料属性或仅靠 Prompt 宣称已满足 | Material 验真实动态动作；Authoring 组织镜头；Quality/Creator 审成片 |
| **0004 CHALLENGE**；B 指接触「嗒」成立，「不能淡出或用替身镜头」无已确认依据（B-000，source-0000/context、source-0002/context） | 轻放、杯底接触和 SFX「嗒」须保留；淡出/替镜取舍在导演 HOW 内 | 编辑禁令候选，含 postproduction 责任风险；**逐字 A 强度/责任待核** | **接受**：镜头与已确认声音事件一致，编辑方案可观察且不改变接触；**拒绝**：移除嗒声/真实接触、把「禁用替镜」定义为源资产 Hard 而无执行/失败验证 | Authoring 画面声音同步；Quality 技术/语义；Creator 取舍 |
| **0007 CHALLENGE**；B 说 7 个镜头独立连续，A 跨镜头复用选择无字面证明（B-000，source-0000/context） | 七场分镜与顺序不能改；复用同一可用资产是可选制作策略，不是相同授权源的事实 | **B 明确称该项为 preference**；实际 A responsibility/Condition SHA 待核 | **接受**：本片可选合法复用且对应镜头内容/权利独立满足；**拒绝**：把复用当 Creator Required、假定相同授权来源/同场景真实性、因不复用而错误判 Material 缺口 | Authoring selection，Material Rights/asset identity |
| **0034 CHALLENGE**；原文「空桌面」，A「物品基本归位」与之冲突，构图留白并非字面要求（B-004，source-0000/authority） | 真实空桌面 Hard；Director 可选负空间构图，不能替换事实 | A 复合视觉/素材候选含「基本归位」「同一类桌面」「中央留白」；**逐字强度与责任待核** | **接受**：原始画面确实空，另加合理留白 preference（若要 Hard 须消费者）；**拒绝**：「基本归位但仍有物品」取代空桌面、用负空间掩盖冲突/宣称同一物理桌面 | Material 观测真实画面；Authoring 构图；Quality 观察空桌面 |
| **0036 CHALLENGE**；「窗光更明显」有确认来源，「整体偏冷」不能由低饱和 Mode 推成硬条件（B-004，source-0000/authority） | 窗光相对更明显是确认义务；冷暖、饱和度是可具体化的美学 HOW | A 复合条件带冷色温选择；**不能在未读原 A 时断言两部分都是同一种 required/material** | **接受**：真实窗光保留，偏冷按可替代的导演 preference，或有必要/消费者证据的单片 Hard；**拒绝**：从 low saturation 推出 Creator 要求冷光 Hard，牺牲原窗光事实 | Material 观察窗光；Authoring 调色；Quality/Creator 审风格 |
| **0041 UNRESOLVED**；「安静天色」有证据，「明亮不刺眼」未确认 required（B-005，source-0000/context、source-0010/context） | 收尾桌面边缘与安静天空是确认目标；柔和曝光可为 Director 选择 | B 明确指出 **新增亮度 required 缺证**；该条件原始 responsibility/text/SHA 尚待核 | **接受**：收尾 WHAT 保留、曝光是合法 preference，或 Hard 有独立必要性与真实消费/审片机制；**拒绝**：A 自签 Creator 亮度 Required，无消费者能力却签发不可替换 Hard | Material 画面/曝光观测；Authoring 曝光安排；Quality/Creator 审读感 |
| **0065 CHALLENGE**；分镜 1/6/7 无同一实物桌面或授权源义务（B-008，source-0000/authority），related_needs=[] | 分镜画面各自为真，跨镜风格协调可选；不假设共享物理来源 | **unresolved_classification 报告，不是 Condition，strength/responsibility=N/A**；B 确认无合格关联 | **接受**：仅视觉连贯意图，合法 Need 分别供给/验 Rights；**拒绝**：同物理桌面/同 licensed source 当已确认 Hard，拿 continuity score 当实物身份证明 | Planning 重分类；Material Rights/观察；Authoring/Quality 连续性 |
| **0066 CHALLENGE**；分镜 2/5 没指定同一只手/同桌子、同授权来源（B-008，source-0000/authority），related_needs=[] | 现有两个手部动作各自需成立；镜头语言可以连贯 | **unresolved_classification，非 Condition，strength/responsibility=N/A** | **接受**：同类表现/构图/节奏的局部 soft 连贯性；**拒绝**：虚构人物身份、同一实物/已授权来源、未核实的跨镜硬关联 | Authoring 选取与镜头；Material 实源/权利；Quality/Creator |
| **0068 CHALLENGE**；重复对分镜 1、6/7 提「同一授权来源」前提（B-008，source-0000 与 source-0017/authority），related_needs=[] | 原画面及通用「收桌面」主题不推出相同素材许可 | **unresolved_classification，非 Condition，strength/responsibility=N/A** | **接受**：识别重复疑问并保留实际独立 Rights 待办；**拒绝**：靠报告去重删除真实义务、把未经验证的同源许可移交成「纯 Material pending」 | Planning 不得假去重；Material 按资产核 Rights；Creator 决定新增权利要求 |

**冻结完整性注记：**上表的 B decision/reason/引用来自 R02 保存的九批原始模型回复与现行 P0 Task 的逐例评审，未修改原件；但 A 原始 Condition 的完整逐字文本、逐条 strength/responsibility、固定 SHA 和与 question.target 的一一映射，本轮未完成可独立复核的提取。故九例的**语义正反期望已拟定**，D0-A 的 9/9 逐字段冻结验收**未达到**；不能将「候选可能如此」写为「原 A 确实如此」。需要在获准的原件只读取证路径补齐后才可宣称 D0-A 完成。

### 8.3 跨 Content 离线对照设计（3 个不同合成主题，非真实 Creation/成片）

共同固定：**同一 Creator 的 Profile 义务与 clear_memo_video v1.3 的 Mode/Director 文档**。冻结的克制第一人称观察、低饱和日常视觉、neutral voice/pace 0.95、克制 BGM，不能当成固定同样镜头/同样选题；Mode 合同的证据是 creative_modes/clear_memo_video/mode.json 和 director-treatment.md，**并非三部真实已确认的 Proposal SHA**。以下均为明确标注的**合成测试 Content**，绝不暗示 Creator 真有这些经历。

| 独立 Content | 自主 HOW 与不重复的内容 | 同一 Mode 应继承 | 该片必须保留的确认边界（将来各自冻结） | 必须拒绝的跨片/越权对照 |
|---|---|---|---|---|
| **C-A AI 学习**：一次模型答案很快，怎样分清理解与复述 | 主题可用屏幕旁的笔记、两次推敲、留一个开放问题；事实只能标「测试观察/待证想法」，不假造模型准确率 | 克制、日常细节引出问题；声音中性、配乐不压旁白 | 自己的示例笔记与每句事实/猜想分类；确认后不得加成功率结论/改声音方案 | 引入 R02 水杯、同桌实物身份/源图/DecisionProof，宣称它们本片已获授权 |
| **C-B 工作实践**：排查异常先确认事实链再下结论 | 屏幕日志抽象示意、时间线和排除步骤；不捏造真实公司的事故/业务数据 | 相同叙事姿态与低饱和基调，但镜头语言可换为界面与图表 | 演示为合成样本；Script/Scenes/音轨与 Truth 归此片，不得借用 A 的证据 | 复用 C-A 的 Claim/Proof、真实账号/客户日志、授权/License 或改写事故为个人经历 |
| **C-C 生活观察**：一段安静路程中的注意力变化 | 街景远镜、光影过渡和短停顿，可无固定三幕或 CTA；非用户真实家庭生活自述 | 克制情绪、生活材料、字幕与音乐不过度；不同视觉与声画节奏被允许 | 不虚构具体家庭/人物身份；每个画面陈述与旁白模式以本片确认版本为准 | 把 C-A/B 的场景、来源、人物身份、Rights、Truth 或成片 SHA 当当前合法资产 |

**未来离线断言（尚未执行）：**三部各有唯一 creation_id/attempt_id、Proposal @4 hash、script/scenes/sound/truth snapshot；共享的仅是实际选定且验证相同的 Mode 文档。每个 Claim 绑定当片 Scene/Condition 与 Policy，Proof 按该片 B receipt 派生。故允许风格一致且故事不同；拒绝复制前片 Scene ref、source catalog、Need/Condition、Proof、Rights、资产选中关系或 Output SHA。当前没有为三个合成题材造假用户确认、实际 Attempt 或视频；不能声称跨作品运行/审片 PASS。

### 8.4 拟议 B 分型与合法组合（**尚未实施的内部 Planning 合同**）

保留原 B 的 ACCEPT / CHALLENGE / UNRESOLVED。四个审核轴独立覆盖 confirmed_fidelity、delegated_creative_validity、responsibility_enforcement、coverage_uncertainty，来源身份/quote 合法不等于事实蕴含。候选分型建议如下，**不新建 Material Domain enum、Creation 状态或 Repair 预算**：

| 原 B decision | 拟议 issue_code / issue_owner | 合法动作 | 明确不合法 |
|---|---|---|---|
| ACCEPT | none / none | 规划本题通过；若已有合法完整 Need，素材供应 pending **作为独立下游 disposition** 记载，非把 Hard 判为已履约 | 同一 ACCEPT 携带 source_or_truth_violation、creator_decision_required、director_replan_needed；以 ACCEPT 自证 Rights |
| CHALLENGE | director_replan_needed / Planning | 已定位的 HOW 强度/职责/具体化错误，限原**一次共享 Repair** 与对应新 Claim、B recheck | 自动增 Repair；把明确错的 Required 静默变 preference |
| CHALLENGE | source_or_truth_violation / Planning→Truth | 假事实、错误真实来源/Role、冲突 confirmed WHAT，拒绝或在既有可修权内精确修复 | 合法 source.quote 即免语义审查；假来源交给 Material |
| CHALLENGE | creator_decision_required / Creator | 明确要改变确认内容/用途/身份，停下并走原产品重新确认 | Director/Material 代替 Creator 授权 |
| UNRESOLVED | creator_decision_required / Creator | 必需前提确实未知，保持阻断 | 无确认证据而自动默许 |
| UNRESOLVED | source_or_truth_violation / Planning→Truth | 事实真值/来源支持无法判定时不提交 Truth | 用 supply pending 掩盖真假未知 |
| ACCEPT（独立下游） | material_supply_pending / Material | **仅**已确定合法 Need、原始供给/许可/可用性未检查；保留 NOT_READY，待 Material 真实核验 | CHALLENGE/UNRESOLVED + material_supply_pending；需新增人物/授权决策却标仅供应 pending |

**需 D1/D2 确定的编码边界：**material_supply_pending 更适合作为已验合法 Need 的独立 disposition 而非与错误 issue_code 并列互斥的 B 问题错误；在实际 Schema 确定前不预称唯一实现。拒绝的 issue_code 未经新 Claim/B 审核不得回写旧结果。原 B 当前无 issue_code/issue_owner 字段，以上都是待实施准入规则而非现有程序 PASS。

### 8.5 当前消费者能力/风险矩阵（源码审计；尚未实施 D3）

| 当前代码入口 | 能传递意图 | 可程序核验 | 只能语义/人工审阅 | 当前不支持，必须阻断或待 D1–D3 补能力 |
|---|---|---|---|---|
| planning_authority.py load_inputs/catalog/validate_basis | 冻结 Scene/Mode/Creator 原文与候选来源关系 | Handoff/Mode/Production Brief/Voice/Confirmed SHA、source scope / primary eligibility | 是否真正授权了新增导演手法 | 尚无逐 Condition 的 Delegation/Claim/Proof；A 不得自签 |
| planning_staged_proposal.py | A-selection header 与 A-details 的固定 slot/Condition | Schema/slot/hash/完整性/顺序及 Assembly | 新 Condition 的必要性、导演理由 | 无视觉 wire-only Claim，也无同次 Repair 新 Claim 原子交接 |
| planning_candidate_review.py | 有界视觉 B 问题及完整冻结上下文 | 题目集合、8 问 batch、quote/role/相关 Need、有界 Repair（原逻辑）；unresolved 非 ACCEPT 会阻断 | HOW 合理性、真实语义覆盖、来源真正蕴含 | typed issue/owner、claim-dependent recheck 未实现；B 不审核完整声音语义 |
| semantic_boundary.py project_proposal | required material→intent.description、material preference→preferred_visual_details、非 material→intent.function、proof.layouts | MaterialNeed 合同结构/输入指纹与生成索引 | postproduction 创意执行效果 | function 文字不能证明一个剪辑 Hard 已执行；continuity refs 不能证明真人/实物一致 |
| semantic_boundary_run.py run/verify | 现有 A/B/Repair/Truth Owner、Journal/Checkpoint 与原回执 | 冻结 Policy/Schema/operation/reply SHA、冷加载/原 Wire 验证 | 不独立判断答案语义对错 | 新 Claim/Proof/policy/issue/消费者身份尚未冻结与重建 |
| planning_contract.py bind_requirements/verify_requirements | 视觉 Requirement 与最终 Need/Mode 合同 | plan/creation/attempt 来源、Need identity、requirements SHA/cache 完整性 | 子句是否被剪辑正确表现 | 缺 Director Hard 的下游可执行 Proof/履约结果 |
| material_layer.py | 正式 MaterialPlan→Supply/Bundle/Readiness；POSTPRODUCTION_REQUIREMENTS.json 包含 source-bound clause、plan/attempt/need/contract SHA，状态 PENDING_AUTHORING | 素材可观测属性、完整 Need、Rights/Source 绑定与 Gate，未供应不 READY | 观测不能推断导演美学结果 | **只交付后期义务**，不会自动剪辑；不能发布非 Material Hard 已履约 |
| hypit/workspace.py | Native Authoring 任务文字明确读取上述 JSON，保持 Script/Scenes 与冻结 Mode | workspace/契约文件交接 | Agent 实际选何种镜头/剪辑手法 | instruction ≠ AST 强制执行 ≠ Quality 通过 |
| hypit/authoring_publication.py validate_current | Native SVML + selection/Run/冻结资产绑定 | 发布 receipt/AST parser/文件集合 SHA、所用素材选择与当前版本 | 源画面叙事/导演含义 | 未逐 clause 核对「淡出禁令、空桌面、物理同一手」等 Hard |
| hypit/quality.py inspect_output/validate_visual_review | Output SHA 绑定帧级视觉/叙事/Creator/Mode/Truth 观察报告 | Build fingerprint、已观察帧、引用 need/frame、技术音画与回执一致性；unknown 不可冒充 pass | 实际画面含义、审美与物理连续性可由有证据的 Quality/Creator 判断 | 未内建所有新增导演 Hard 的自动物理身份识别与按 clause 保证 |
| materials/application/matching.py | continuity_refs 传入候选排序 | 对 lineage 引用或文本 token 命中作连续性比例，**权重仅 0.20** | 视觉连贯是否成立仍需作品审阅 | lexical/score 绝不是同一人物/同一物理桌面/同一 licensed source 的 Hard 证明 |

**阶段时序：**D1/D2 Planning 阶段最多确认「此 Required 合法、指定哪个可验证消费者、实际义务待执行」，无资产/Output 时可保存 Plan/Proof；Material/Rights、Authoring、Quality、Creator 在各自阶段按原冻结身份及实际素材/Output SHA 出履约证据，不能回写旧 Checkpoint。若没有能核验承诺 Hard 的消费者，明确 BLOCK 该 Hard，允许另一个新合法候选走原 B/Repair，**不**直接降级、修改 Material V1.3 或加第二条链。

### 8.6 D1 最小前置与本轮实证边界

1. **先闭合 D0 证据缺口：**从 R02 原件逐题只读冻结完整 A-details Condition 原文、strength、responsibility、meaning、question kind/target/slot、Mode Documents、B request/reply/source SHA 与 R08 作用范围；生成原件哈希清单，逐行校验本节 9 组正反断言与原 A 是否匹配，绝不修改原 response。当前这一项**未完成，阻断将 D0 报 COMPLETE**。
2. D1 的最小实现入口仅限既有 Planning：从实际 Handoff/确认方案/Mode 纯函数编译 Delegation Envelope 和合法 Scene/Mode ref；先做本期视觉 A-details **wire-only** Claim 与 A-selection header 决策身份的编码/解码/拒绝 Demo，并联设计同一 Repair Carrier 的「变更值+新 Claim」，保持 Canonical Proposal、Material V1.3、声音与唯一共享 Repair 无变化。
3. D1 需证明 scope/hash/condition 顺序、文本、强度、责任、Policy、Claim、Mode、B receipt 与消费者引用的身份链及冷验证；跨 Content/Attempt 的任何 source/Claim/Proof 互换应拒绝。只允许有证据的创意归因，不让 A 造 Creator 授权或机械哈希。
4. 源码检测已有关系字段与 PENDING_AUTHORING 交接可复用；D3 后必须实际核验 Hard 消费，不因 D0 讨论就修改 Native/Quality 或升级 Gate。若合法 Required 与冻结职责实际冲突，先架构复核/人类批准，**停在 D0**。

**D0 本轮验证记录：**已读取项目入口/当前方案/历史 P0 R02–R08 汇总、九条原 B 回执的 decision/reason/support；已核对源代码和 clear_memo_video 模式文件。选定无付费离线 B Identity/Repair Evidence 测试 **35 PASS**；其余 Material/Authoring 定向测试见本轮 Closure 结果。未调用 MiniMax/Provider/Hypit Build、未更改 Proposal、R02–R08 或正式 Domain；静态三 Content 矩阵并非已运行三部独立 Proposal@4/Attempt，九例逐字 A 冻结未完成。正式 **U4=BLOCKED / U5-U6=NOT_STARTED** 不变。

RESULT=PARTIAL（D0 九例预期/跨 Content 设计及消费者盘点形成；九例 A 原值逐字段与跨作品自动执行尚未证实）
DRIFT=NO_DRIFT（未修改冻结架构或生产链）
EVIDENCE=九例原始 B 决策 8 CHALLENGE + 1 UNRESOLVED、R08 整体 63/8/1；35 项本地既有回归 PASS；待补完整 A Condition/SHA 及三 Content 离线实际断言
NEXT_SINGLE_ACTION=在原件只读权限与安全路径允许时，完成 D0 九例 Condition/Question/Mode 原值 SHA 与正反验收的冻结；完成后 D1 才能以最小视觉 A Wire Claim+Repair Carrier 纯离线原型起步
TRANSITION=HOLD（本轮停于 D0，不进入 D1）

### 8.7 D0 最新验收收口（2026-10-15；覆盖本文件 §8.6 的上一轮 PARTIAL）

本轮只执行 D0。已从 R02 原始 Journal、A-selection、三批 A-details、B-000/004/005/008 原回复及其完整请求包逐题交叉复算；未修改原件或历史 B 标签。冻结原件：~/.local/share/easel/creator-task-evidence/2026-10-14-real-minimax-p0-medium-s5-r02；Journal SHA256=1a193231ad50dd3e763b42d6f67b38260c6cf48716df6e7433179ae3e9b1c4e4；Mode=clear_memo_video v1.3，冻结 Mode 上下文 SHA=sha256:c8b997c24bb021bcfe1edf3e811f0d2860bb1078b5e7bdb220f4bce2314477e0。六份冻结 Mode Documents 与原 mode.json 对应；真实确认 Script/Scenes/Treatment、声音和 Truth 边界不变。

**九例完整原 A 行、目标、强度/责任、SHA 与 B 判决（SHA 为原候选 canonical digest）：**

| QID / A 原始类型与 target | 原 A 原文（未改写） | 原 strength / responsibility / meaning | 候选 SHA256 与历史 B |
|---|---|---|---|
| 0002 / complete_obligation [0,1] | 动作在画面中全程可见，手与水杯不被遮挡、不以剪辑跳过接触过程 | required / material / dynamic_action | 4fe6ec03ec613a34b97a211a9453bb184edc617dbf408e0ca82a47fbe897e6c9 / CHALLENGE |
| 0004 / complete_obligation [0,3] | 杯底与杯垫接触的瞬间是真实可见的画面事实，不能用淡出或替身镜头代替 | required / material / dynamic_action | 6b0f61f5a529cdd23285320b94a433d058bf81dbeccdc3ec604b2cf7e49b49fa / CHALLENGE |
| 0007 / complete_obligation [0,6] | 该素材可用于整条片子中桌面物件归位的动作线，不必与其他镜头同机位同背景 | preference / material / observable | aa881fdfe14b6d14625e004fc1fa4f810f4ef4ae746884105b9531757bb5070d / CHALLENGE |
| 0034 / complete_obligation [5,0] | 源图为中景的同一类普通桌面静帧，桌面上物品已基本归位、无散乱堆放，中央留出大面积空白 | required / material / observable | ee68eda19971c528401a97e594abd055bc51d3b10ea33cedcb782e122ed6eb2d / CHALLENGE |
| 0036 / complete_obligation [5,2] | 源图中来自窗外的光更明显，是画面主要照明来源，整体偏冷、克制、低饱和度 | required / material / observable | 592612cd45c8f0ab11dde8ab1448e6b309f72dc118e29db9dd710302be3a5ede / CHALLENGE |
| 0041 / complete_obligation [6,0] | 源图为桌面边缘与窗外安静天色构成的收尾静帧，桌面只占画面一部分，天空为明亮但不刺眼的自然天色 | required / material / observable | 7fbbbeb265fb07ac93c05e1d861e4e82c333ad1e39ce04e2e6c11a1ceda888b1 / UNRESOLVED |
| 0065 / unresolved_classification [1] | 分镜1与分镜6/7需同一通用桌面场景，具体是否来自同一授权来源待 Material 阶段确认 | N/A（报告，非 Condition） | 0659ab41d92ed2381e6a2670a6d8eae508d386c3d879f5c4ea6425783ec079dd / CHALLENGE |
| 0066 / unresolved_classification [2] | 四个video素材的实际授权来源与同一只手/同一张桌面的连续性尚未核验，属Material阶段职责 | N/A（报告，非 Condition） | 30c03b8f8909a0bae955b8db8c1ba5c76b4d8a7fa141b5fc09c8698b09d97ec1 / CHALLENGE |
| 0068 / unresolved_classification [4] | 分镜1（slot_004）与分镜6/7（slot_005、slot_006）要求呈现代意连续的同一通用桌面场景，是否来自同一授权来源待 Material 阶段核验；本批按各自素材义务如实提出条件，未合并为单一资产。 | N/A（报告，非 Condition） | 56a5089cfe856e347cca88872cfa22aa15061cf21a9813e17ce10352f37b4122 / CHALLENGE |

**可复核原请求绑定：**0002/0004/0007 的原 B request SHA=51632c97adf3451dece2d282b0b627555f33d223826b02a8df77b157d68fdbc1，selected_source=event-5；0034/0036 为 8d926ecbc8cc880ec606e1b4cdbaaf8f40feacc3a6bc4c22d397646783fba094，event-9；0041 为 3ad11764fb03492a4f0cb2e1d9e439392be6f81a2d8261e67e90c93a6e020b22，event-10；0065/0066/0068 为 b01e362dd38f3bef4a73de76ac461b124c6aa24d40e2e5b0ff06a50701bd26f6，无 selected_source（未决报告独立审核）。B-000/004/005/008 原回执 SHA 分别为 ace6c88b8834899bcf7602384b80a76bf08bef9aaaf7db5a628c3318bcb24bdd、38246665c156a52f7b93b89122d9ee804bd03d0c8d94984b5aac69481f97eb3b、4f0b9750d05cdeac5c9f59c87a67ddaac54eb81f8d46c09031299bbf5b53e818、cce4af07df799602927f092f610cdfd8b3ae121d780b64557495e158b98d9718。测试直接验证每条原 B support 的 source/role/quote 资格以及所有原 A reply SHA；资格不是语义蕴含证明。

**对 §8.2 的修正与独立正反预期（均不重判历史）：**0002、0004 原 A 确实把后期禁剪/淡出与真实动作捆绑为 required/material；正例应拆开素材真实接触 Hard 与经过独立 B 判断、具名消费者核验的可执行后期义务，负例是把编辑禁令当 Material 可验证硬属性。0007 原 A 确实是 preference/material，软复用可为合法 Director 单片选择，不自动取得同素材授权、不自动把历史 B 改 ACCEPT。0034 原 required/material 的“基本归位”与 Creator 已确认“空桌面”直接冲突，必须拒绝，构图留白可以作为另行合理的 HOW。0036 原 required/material 将窗光真义务与“偏冷”额外硬取舍混写，必须在新候选中区分、经 B 核实必要性和消费者；不能凭 Mode 低饱和推出冷光必需。0041 原 required/material 的“明亮但不刺眼”不是已确认事实，可作为独立导演表达选项但不能未经验证冒充 Creator Hard。0065/0066/0068 都是原 A unresolved 报告，不是附带 strength 的 Condition；可保留 soft 视觉连贯和每个资产真实 Rights 待办，但同一物理桌面/人手/授权来源不能由 soft continuity 评分或素材供应待办自证；原 B 的三条 CHALLENGE 仍保留。这些正反例连同 §8.2 是后续 D1/D2 必须遵守的验收预期，不是已实施的独立语义 Reviewer。

**三 Content 离线实际执行：**在测试临时工作区复用现有合法 New-Only Proposal @4 Creation/Consent/Handoff 设施，分别构建 AI 学习、工作实践、生活观察三个合成 Content，生成 3 个不同 Creation、Attempt、Handoff、Proposal SHA、Script、Scenes、Content Core、Truth Packet；使用相同测试 Creator Context 和真实工程 clear_memo_video v1.3 六份冻结 Mode 文档。经真实 planning_authority.load_inputs/catalog 检验，互换 Script/Scenes、另一作品 Context/Truth、篡改 Mode、改写确认 Script 或音轨均拒绝；source catalog 输入 SHA 随作品变化。声音实验明确只覆盖三个作品的 silent 原方案，不声称 voice/mixed 的生产审查。跨片 Claim/Proof 唯一性有本次离线身份期望，但**D1 正式 DecisionClaim/DecisionProof 尚不存在**：实际生产层跨片 Claim/Proof 拒绝仍须 D1/D2 验证，不能把本轮软件前置断言当成生产 Proof PASS。

**消费者与阶段边界仍依 §8.5：**Material Source/Rights/Readiness、已存在的 POSTPRODUCTION_REQUIREMENTS.json(PENDING_AUTHORING)、Native Authoring、Quality/Creator 真实消费职责不变。continuity_refs 的 0.20 加权软评分绝不可当 Hard 同一身份/来源证明；缺正式消费者时新增 Hard 不能放行。不改 Material V1.3、Proposal @4、正式 New-Only U Gate；未发现需本轮擅改的冻结架构冲突。

**验证：**新 tests/test_planning_creative_authority_d0.py 的 9 个原始 A/B 冻结+篡改对照用例及 1 个包含 3 个真实独立合成 @4/Handoff/Attempt 正反测试，共 10 PASS；同当前 B Identity/Repair Evidence 测试合计 45 PASS。原 R02/R08 与 dirty 修改均未清理。D0 完成的是验收基线/当前可执行身份边界，不是 D1–D4 代码或 U4/U5 Gate。

RESULT=COMPLETE（仅 D0 原始证据、九例正反期望与三 Content 离线验收范围）
DRIFT=NO_DRIFT
EVIDENCE=9/9 R02 A/B/来源/Mode/SHA 同源验证，三 Content 独立 @4/Handoff/Attempt 正反软件断言，45 PASS；D1 Claim/Proof 真实载体与跨作品拒绝仍未实现、D3 Hard 消费未证明
NEXT_SINGLE_ACTION=D1 最小合法实施动作：先获得实施/冻结职责批准；再用现有 Handoff/Mode 编译视觉 Delegation Envelope，设计 A-details Wire-only Claim + 原 Shared Repair 同次 Claim 原子交接的最小离线正反原型，先不切生产
TRANSITION=HOLD（本轮 D0 完成即停，不自动进入 D1）

### 8.8 D1 最小离线原型 Closure（2026-10-15 · 本轮最新）

**阶段归属：唯一 Creator Task / Planning Creative Authority D1，交付范围仅为已获授权的无副作用原型。** 与 §8.7 已完成的 D0 证据接续，不新增 Goal、独立 Agent、状态机、生产 Gate 或第二条主线。本节标记 `D1_OFFLINE_PROTOTYPE_COMPLETE`，**不等于 D1 正式 Owner 集成 Done，更不等于 D2、U4/U5 通过。**

**代码与载体：**

- 新增 `easel/integrations/planning_creative_authority.py`：纯函数 `compile_envelope()` 只从现有 `planning_authority.load_inputs()` 对当前冻结 Handoff、Proposal @4、Mode 文档、Creator Context、Truth 与 Source Catalog 取身份，绑定 Creation/Attempt/Proposal SHA、Mode/上下文 SHA、source refs；`allow_missing_canonical=True` 仅用于合成 @4 测试在未落地 Planning 原件的准备阶段读取合法 Handoff，**不是生产放宽策略**。Allowed 是确认后的视觉 HOW（构图、镜头执行、剪辑、软连续性、审美），Denied 包含改变确认脚本/场景、编造真人或事实、假定 Rights/资产已存在、擅自变更付费/发布权限。
- `VisualClaimCarrier`：仅对现有 `StagedProposal.details_contract()` 的 image/video Condition 加 Wire-only `claim`，保留当前 header、slot 顺序、Condition 原字段及原 canonical `SemanticProposal`；音频 Condition Schema 完全不变。Claim 只有 `claimed_kind / creative_goal_ref / reason / claimed_strength`，禁止模型自签 `program_derived`；Claim 是 **A 的未审候选**，并非用户授权、Rights 或已通过的 B Proof。编码要求完整 Claim 覆盖，解码先严格检查 Schema、强度/来源 scope，再使用原 `StagedProposal.assemble()`，不允许清除未知字段后“洗白”成合法候选。
- `AtomicSharedRepairCarrier`：在**原有** `planning_candidate_review.patch_schema()/decode_patch_slots()/apply_patches()` 上，为本次 **visual complete_obligation** 目标增加同一 Wire 里的“替换 Condition＋新 Claim”。按原目标索引和冻结原候选/原 Claim/Envelope Hash 精确定位，只允许对已有目标交接，未变条件的 Claim 保留；修复后仅返回纯内存的 candidate＋updated_claims＋`PENDING_B_REVIEW`/recheck_required，**不持久化、不给出 ACCEPT、不能自动再次派发 Repair**。对其他 Header、coverage、necessity、audio、mixed-target 等现有共享 Repair 类型，本原型故意 fail-closed，留待获批的 D1/D2 全量合同方案处理，不能冒充整个 Repair 已升级。

**正反离线验证：**新增 `tests/test_planning_creative_authority_d1_prototype.py`，使用 D0 已建立的三主题合成 @4/独立 Handoff/Attempt 和工程内实际 `clear_memo_video v1.3`。覆盖同 Mode/不同 Content 独立 envelope 身份、跨片/Mode/Proposal 篡改拒绝、Claim 完整往返、原 canonical 完全无 Claim、非视觉 Schema 不变；Missing/重复/未知字段、非法 Claim 来源/强度/自签权限、丢失必要 Material 条件、跨 Target/跨 Attempt、仅修改 Claim 理由仍要求重新 B 审核。仅验证 Carrier 与身份失效规则，**未运行新 D1 的 B 独立语义审查、Proof 冷恢复或完整 Owner**。

**容量样例（合成单视觉 Slot，与真实模型负载不等价）：**原 `A-details` Schema 352,442 bytes；新增 Claim Wire Schema 390,794 bytes，增加 38,352 bytes；没有额外 A/B/Repair 请求。这是离线编译体积，不代表真实 MiniMax 响应 Token、耗时或成功率，正式切换前必须在 D1 完整 A/Repair 模型载体/容量中重新核实。

**恢复会话核验：**使用同一 Workflow Session `wc_sess_RFGiI4v4m7P6nWBV` 收口，无活动 Job。D1 原型 26 个测试 + D0 原证据 10 个 + 原 B Identity / Repair Evidence 35 个，在当前工作区同次定向运行 **71 PASS / 4.67s**；`python -m compileall` 两份新增 Python 文件 PASS、`git diff --check` PASS。起点/结束仍为 `easel-studio` / `d82bb60b`，工作区 22 项原有及本轮变更均保留；没调用真实 MiniMax、Provider、Hypit Build，也无 commit/push、部署、旧 Attempt 回写或清理。搜索生产 `easel` 导入/调用边界未发现对新原型模块的引用：**当前生产 Owner 尚未接入**。

**剩余合同责任/风险（下阶段，未授权执行）：**第一，`A-selection` 视觉 Header、`A-details` 全量分批、原 Shared Repair 的其他合法 target 与新增/删除视觉 Need 尚未设计完整归因；第二，A 自报 `confirmed_obligation/frozen_director_rule` 仍需由程序与 B 验证真实来源/委托，不能凭 Claim 声称已授权；第三，正式版本 Policy、原始 A/Repair Wire 同步保存、B question/recheck 依赖签名、最终 DecisionProof 的身份与 Journal/Checkpoint 冷验证尚未接入；第四，Material/Authoring/Quality 对 Hard 的真实消费合同尚属 D3，软 `continuity_refs` 不能证明物理同一。若正式接线需要变动冻结职责、Material V1.3 或已接受 ADR，须在实施前复核并取得相应批准。

```text
RESULT=COMPLETE（仅 D1 最小纯离线原型；生产 D1 尚未完成）
DRIFT=NO_DRIFT
EVIDENCE=原型 26 PASS + D0 10 PASS + B/Repair 35 PASS = 71 PASS；编译/diff PASS；原 A/Repair canonical 不变、声音 Schema 不变、无生产接线；缺全类型 Claim/Repair、B Proof/持久化/冷恢复、真实消费者验证
LESSON=先用视觉 Wire-only Claim 与原共享 Repair 的同槽原子回执证明身份与拒绝性质，再评估生产集成；A 声明不能自证授权
NEXT_SINGLE_ACTION=取得后续 D1 生产集成与必要架构复核授权后，先补齐视觉 Header 与各合法 Repair 类型的身份/Claim 原子映射和版本化冷验证的离线设计，再考虑接入原 Owner；不得隐式增加 Repair 预算
TRANSITION=HOLD（本轮离线原型到此停止，D2/生产 U4/U5 未准入）
### 8.9 D1 扩展离线验收：视觉 Header / Repair / 冷验证（2026-10-15，本轮最新）

**本轮仅完成 D1 扩展离线原型，不实施生产 Owner/D2。** 在同一个 `easel/integrations/planning_creative_authority.py` 中增加 `VisualHeaderClaimCarrier`、`ExtendedSharedRepairCarrier`、`freeze_offline_receipt()/verify_offline_receipt()`；测试位于 `tests/test_planning_creative_authority_d1_extended.py`。不修改 Material V1.3/ADR、正式 SemanticProposal、真实模型调用或已有 Repair 预算。

**视觉 A-selection Header：**对 image/video 的 scope、role、modality、necessity、continuity_choices，使用冻结 Envelope 与有界 Claim 原因/来源/必要性/连续性 SHA 形成单片待审记录；非视觉 Header 维持原 Schema。不允许模型声明 program_derived 或自行签发 Creator/Rights 授权。其身份包括 Policy、Scope、原 Schema、Wire Schema 和 Header/Claim 摘要；真实 B 对必要性/连续性仍须独立判断。

**原 Shared Repair 按 kind 审计：** `complete_obligation` 以原目标 Condition + 新 Claim 同槽交接；`visual_choices` 需完整视觉 Need + 新 Header Claim + 每条 Condition Claim，原校验禁止顺手改已接受 conditions/queries/necessity；`frozen_visual_coverage` 仅新增视觉 Need 及其全部 Claim，不能删旧义务；`confirmed_necessity` 仅接受原独立 B judgement 支持的 optional→required，更新 Header identity 为 program_derived_from_frozen_B_necessity，模型无授权签发权；`candidate_answer`、`confirmed_music_coverage`、其他 B/声音修复保持原 Schema，不新增导演权；视觉语义 `structural_leaf` 的 value-only 变更主动拒绝，需要完整 Claim 后才能实施。任意目标更改后仍返回 PENDING_B_REVIEW，禁止擅用旧 ACCEPT 或增加一次 Repair。

**版本/冷验证：**纯离线记录冻结原始 tool arguments JSON 字节、Codec Identity、Envelope Scope、解码结果 SHA 和政策版本；从隔离 JSON 文件重新读取后用重新构造的 Codec 与原合同验证，能拒绝改 Policy/Identity/Schema/Target/Claim、跨作品来源与篡改原字节，包括重算普通记录摘要的伪造 Claim。这里是测试级离线恢复，不是正式 semantic_boundary_run.verify() 的跨进程 Journal/Checkpoint 恢复。

**原 Owner 接入审计，结论 NOT_READY：** (1) 生产 A-selection 使用 PlanningInputView.SourceSelection 的 src_* opaque handle，而当前离线 Header 原型直接使用 canonical scene-*；需要额外 SourceSelection 可逆 Mapping SHA 与语义绑定回归。(2) 生产 A-details 以最多四个 Slot 分批，尚未验证多批原始 A reply/Claim 与全部合法 Repair target 的唯一 Checkpoint 身份、容量和恢复。(3) 现有 semantic_boundary_run.run()/verify()、Journal/Checkpoint 与 B recheck 签名尚未纳入新 Claim、Header、Repair Policy/原响应；不得用侧车元数据冒充 DecisionProof 或冷恢复。(4) D2 的独立 B 语义分类及 D3 的下游 Hard 真正消费仍缺实证；continuity_refs 软评分不能证明同一物理人物/资产。

**验证：**扩展 D1 36 PASS；连同前一阶段 D1 26、D0 10、B Identity/Repair Evidence 35 项同版联合离线回归合计 **107 PASS（10.09 秒）**。新增代码/测试 Python compileall、git diff --check PASS；工作区起始 `easel-studio/d82bb60b`，无真实 MiniMax/Provider/Hypit Build、无提交/部署/历史 Attempt 回写。无新冻结架构冲突；视觉语义 structural_leaf 在缺新 Claim 前保持 fail-closed。

RESULT=COMPLETE（仅本轮 D1 扩展离线验证，不代表生产 D1）
DRIFT=NO_DRIFT
EVIDENCE=视觉 Header/Condition/全视觉 Need 和程序派生 necessity 的 Claim/身份正反验证 + 离线冷验证；36 新增 PASS、联合 107 PASS；正式 SourceSelection/分批/Journal/DecisionProof 仍未接入
LESSON=Claim 身份必须与原 Header/Condition、Repair Target 和冻结输入联动；离线校验通过不等于 B 语义判定、Rights 或 Hard 消费通过
NEXT_SINGLE_ACTION=获得相应后续授权及必要架构复核后，先用真实 src_* SourceSelection 与四 Slot A-details 分批完成同一 Owner 的版本化冷校验离线集成，再评估接入现有生产 Owner
TRANSITION=HOLD（D1 扩展离线阶段收口，停止，不进入 D2/正式 U4/U5）
### 8.10 D1 真实 SourceSelection / 四 Slot / 正式冷恢复核验（2026-10-15，本轮最新）

**边界：**本轮由原 Creator Task 授权继续 D1 离线同源验证与生产 Owner 接线评估，不执行 Owner 修改、D2、外部模型、Provider 或媒体 Build。沿用 §8.7/8.8/8.9 的冻结上下文、合法 New-Only Proposal @4 和 clear_memo_video v1.3。

**真实 opaque 来源映射：**在现有 `easel/integrations/planning_creative_authority.py` 增加 `OpaqueHeaderBridge`，直接消费正式 `PlanningInputView.SourceSelection`（policy planning-source-selection@2）编译出来的 `src_*` handle，而不是自造映射。严格保留原 SourceSelection 的 closed `anyOf` 按 modality 分支、原 schema/identity，Header Claim 在 wire 使用 opaque handle，校验并还原 canonical scene/ref 后才由原 `VisualHeaderClaimCarrier` 生成 Claim 身份。SourceSelection 的 catalog/mapping/schema SHA、D1 Envelope、Header Claim Policy 均冻结；缺失/无效 handle、Claim scope 不符、未知字段、跨版本重放 fail-closed。新增 Scheme 仍是离线 overlay，不修改生产 A-selection 原 schema。

**四 Slot 分批：**新增 `BatchedVisualClaimCarrier`，使用正式 `StagedProposal.detail_batches()` 的固定 4-slot schema 与 batch identity；5 个视觉 Need 的测试生成 `A-details-000`（4）和 `A-details-001`（1）。每批需要原始闭合 schema/完整槽位，合并后通过原 `assemble_batches_candidate()` 与正式 SemanticProposal 校验比较，冻结 batch key/selection/Schema/原 reply digest/Claims digest。缺批、错槽、少 Claim、变 condition、换 selection/batch 身份及复制旧 checkpoint 均拒绝。模拟的是已确认静态输入的两批局部载体；不等同真实 MiniMax 原 response 时间稳定性或全部生产条件。

**正式 Journal/Checkpoint 冷恢复核验：**新增定向测试采用既有合法 `material_integration_env` 和 `_current_vnext_planning_executor()`，不调用真实模型，实跑当前原生 `semantic_boundary_run.run()` 软件路径。取真实 `semantic-planning-vnext` Journal 和 `planning/SEMANTIC_CHECKPOINT.json`，核对 `A-selection`/`A-details` 捕获 SHA、`schema_bindings`、`detail_binding`、`input_view_snapshot` 与从冻结输入重建的正式 `PlanningInputView`。再将新合成 Attempt 的完整工作区复制到独立临时目录，使用原生 `semantic_boundary_run.verify()` 冷恢复成功；仅在副本中篡改 checkpoint 的 frozen `creative_mode_sha256`，原生 verifier 正确拒绝。原始合成 Attempt、历史 R02–R08 与真实生产记录未回写。

**重要限制：**上述“正式冷恢复 PASS”证明的是**当前已上线的旧 Schema/Journal/Checkpoint** 的原生加载与篡改拒绝；D1 Header/Condition Claim 的新 Policy、签名、原始 A/Repair 的完整声明载体、独立 B recheck 依赖及最终 DecisionProof 尚未登记到现有 `semantic_boundary_run.run()/verify()`。D1 Claim 仅在独立离线 Carrier/快照上通过冷验证。因此不能宣称“D1 新 Claim 已在正式 Checkpoint 冷恢复”，也不能把这轮离线验证当 U4/U5 的生产准入。

**生产 Owner 接线评估：NOT_READY。** 可复用的接口已明确：SourceSelection.encode/decode 和 mapping SHA；StagedProposal 4-slot batch 身份、原 A 捕获 SHA；原 `VIEW_JOURNAL` 中 `schema_bindings/detail_binding/admissions/wire_originals/repair_used`；现有 native `verify()` 严格源重建。剩余必须经相关架构/实施授权后，在同一个 Owner 内无新请求地把 D1 Claim Policy/原始 A+Repair Wire + Header/Condition Identity 写入原 checkpoint/journal，并令冷恢复从冻结回执重新编译且 B question/recheck 依赖 Claim/Policy 变化失效；严禁凭 A Claim 自签 Creator/Rights 或绕过共享 Repair 预算。完成此项后，才有条件评估 D1 正式 Owner 集成和 D2 独立审核。

**实测与边界：**新增 `tests/test_planning_creative_authority_d1_source_batch.py` 共 **13 PASS**（含原 Owner 离线 Journal/Checkpoint 原生 verify 和复制/篡改负例）；与 §8.9 的 D1 扩展 36、原 D1 26、D0 10、B Identity/Repair 35 联合 **120 PASS（18.65 秒）**。Python compileall、git diff --check PASS；`easel-studio/d82bb60b` HEAD 未变，工作区原 23 项 dirty 全保留并新增本轮 1 个测试文件。未进行真实 MiniMax/Provider/Hypit Build、提交、部署、历史 Attempt 回写。

RESULT=PARTIAL（本轮 SourceSelection 与 4-slot 同源验证完成，当前正式 Journal/Checkpoint 原有合同冷恢复通过；D1 Claim 正式 Checkpoint 集成尚未完成）
DRIFT=NO_DRIFT
EVIDENCE=13 新增 PASS + 原 107 PASS=120 PASS；原生 run/verify + 冷复制篡改拒绝 PASS；新 D1 Claim 不在正式 Checkpoint，生产 Owner NOT_READY
LESSON=必须分开“旧原生 Journal 校验通过”和“新增 Claim 已实现正式冷恢复”，不能借 offline overlay 证明 Production Owner 准入
NEXT_SINGLE_ACTION=在取得明确 D1 生产 Owner 集成及必要架构复核授权后，将已验证的 SourceSelection/Header/Condition/Repair Claim 原始身份以同一事务接入现有 Journal/Checkpoint，补 B recheck 签名失效与官方 verify 的新 Policy 冷重建；不新增调用或 Repair 预算
TRANSITION=HOLD（停于 D1 离线，不进入生产 Owner/D2/U4/U5）
### 8.11 S1 MINIMUM_CORRECTION｜离线修正及生产接线准入复核（2026-10-15）

本轮按 S1 定向评审结论 MODIFY 执行，仅修改现有 `planning_creative_authority.py` 离线 Carrier，增加 `tests/test_planning_creative_authority_s1_corrections.py`；未修改正式 Planning Owner、Material V1.3、历史 Attempt 或 Shared Repair 调用额度。
**修正与再验证：**（1）原 ExtendedSharedRepairCarrier 两个 `frozen_visual_coverage` 同次追加时都复用旧 len(needs) 下标，导致第二条 Claim 覆盖第一条；现改为逐新增 Need 递增索引，并在原 `apply_patches` 后核对所有 Header/Condition SHA 与最终 Need/索引，`confirmed_necessity` 的 program-derived Header 在核对前更新。新反例证明两个 Need 产生两个 Header/Condition 独立 Claim。（2）增加纯 `bind_review_claims()`：对 `complete_obligation`、`visual_choices`、`need_necessity`、`frozen_visual_coverage` 和 `unresolved_classification` 的原问题对象依赖 Claim/Policy/Scope 摘要；现有原 `recheck()` 基于完整问题签名，在仅 Claim/Policy 变化时不能再复用旧 ACCEPT。该工具**尚未接到生产 B directory/recheck**，不是 D2 B 语义分类实现。（3）增加 `freeze_original_capture/verify_original_capture`：直接绑定原捕获 UTF-8 回执、原 SHA、Codec/Envelope/解码结果摘要，不以重新序列化的对象冒充原字节；离线篡改及版本错绑会拒绝。原生产 `planning_capture.capture()` 和 `semantic_boundary_run` 不修改。
**当前技术验证：** 新增 3 个正反断言，与之前 D0/D1/B-Repair 120 项联合 **123 PASS（19.51 秒）**。历史 R02–R08 模型判决仍然是原始 FAIL/CHALLENGE/UNRESOLVED，不为测试通过重新定性。无真实模型/Provider/Hypit Build、Git commit/push、部署/Runtime 切换。
**生产接线准入复核结论：NOT_READY（不得直接接线）。** 本轮修复了 S1 指出的两个离线逻辑缺陷，并给出原始字节校验函数，但 D1 新 Claim Policy 仍未按统一新 Attempt 身份正式纳入 `semantic_boundary_run.run()/verify()` 之 Journal/Checkpoint、真实 A/Repair Wire/原 B 问题与签名、原子持久化及冷重建。因此无法证明生产 B 的 Claim-only 变更也会强制 recheck，也无法宣称新 Claim 正式冷恢复通过。后续在冻结职责批准及单 Owner 设计复核后，在**仅新建合法 Attempt** 一次性完成同一 Journal 的事前 Policy 版本冻结、写前捕获及验证、B 签名/Proof 绑定、冷恢复/故障注入，保留既有 repair_used/UNKNOWN 防重派约束。旧 Attempt 保持只读，不提升已有历史候选。
RESULT=COMPLETE（S1 最小离线修正）；PRODUCTION_ADMISSION=NOT_READY
DRIFT=NO_DRIFT
EVIDENCE=3 新增专项 + 120 原离线 = 123 PASS；多追加 Need Claim 不覆盖、Claim-only 导致原 recheck 失效、原始字节回执身份篡改拒绝；正式 Owner 尚未接新 Policy/Proof
LESSON=新 D1 Policy 必须与 B 问题签名、唯一 Journal 与原始 Tool 字节同时登记，不能从纯离线 PASS 推定生产安全
NEXT_SINGLE_ACTION=先完成新 D1 Policy/Claim/Proof 对正式唯一 Owner/Journal/Checkpoint 的同版原子接入设计及审批，再授权单条新 Attempt 离线集成与正式 verify 冷重建；不得自动进入 D2
TRANSITION=HOLD
### 8.12 S1 同一 Need 混合 Repair Claim 保全修复（2026-10-15，最新 Closure）

本次仅修复 `visual_choices + confirmed_necessity` 同一 Need 的离线 Claim 保全。既有 `candidate_review.apply_patches()` 合法顺序为先 visual_choices（修改 Header，necessity 仍 optional），随后由冻结 B judgement 将 optional→required；现在保留与替换 Header 对应的待审 Director Claim 和其 `claim_header_sha256`，同时独立记录 `necessity_evidence`（frozen target SHA、program-derived 来源、recheck_required），最终 Header SHA 对准 required 的结果。二者分别身份化，不宣称旧 Claim 授权 necessity 提升。仅 necessity 的修复仍保留原测试要求 `claim=None`；反序先提升必要性再用旧 optional Header 覆盖，仍由原合同拒绝，禁止为修测试扩权。

`tests/test_planning_creative_authority_s1_corrections.py` 新增同 Need 混合正反校验，联合 D0/D1/B/Repair 离线 **126 PASS（19.66s）**。仅修改纯离线 `planning_creative_authority.py` 和现有测试；原 Owner `run/verify`、唯一 Journal/Checkpoint、Material V1.3、预算、历史 Attempt 未修改。生产 D1 Claim/Proof 接线和原生冷恢复仍未完成。

RESULT=COMPLETE（仅本次混合 Repair 离线修复）
DRIFT=NO_DRIFT
EVIDENCE=同 Need visual→necessity 保留 Director Claim + 独立程序派生证据，逆序拒绝，necessity-only 不新授权；联合 126 PASS
NEXT_SINGLE_ACTION=在获准的后续单 Owner 新版本实施中，将 D1 Claim/Review/Repair 与原始 Capture 统一纳入唯一 Journal/Checkpoint 并完成真实原生冷重建；实施前仍需生产接线准入复核
TRANSITION=HOLD

### 8.13 D1 接入唯一 New-Only Planning Owner｜受控软件集成 Closure（2026-10-15）

**范围与启用：**按用户明确授权，将 D1 Header/Condition Claim、原始回执重建、B recheck 依赖及 Checkpoint/Journal 冷恢复接入**现有唯一** `semantic_boundary_run.run()/verify()`，没有新建 Owner、Agent、模型调用阶段、Repair 预算或 Material Domain Contract。仅当**全新合法 Attempt** 的 Planning Context 显式冻结 `creative_claim_policy=planning-creative-owner@1` 时进入 D1 分支；未带该 Policy 的当前 New-Only 执行逻辑不变。**尚未将 D1 默认打开到所有 Web Creation，也没有部署/运行真实 MiniMax。**已有历史 Attempt/旧捕获不会自动升级、迁移或重派。

**同源实装：**A-selection 使用真正 `SourceSelection src_*` 对应的 `OpaqueHeaderBridge`，视觉 Header Claim 与原选择在同一 Tool 响应；A-details 使用正式四 Slot 分批的 `BatchedVisualClaimCarrier` 收集视觉 Condition Claim。现有 `planning_capture.capture()` 持久化原始请求、完整模型回复字节及 SHA；A 进入 B 之前通过 `verify_a_claim_origin()` 从当前 Attempt 原始 A-selection/A-details 回执重新生成 Header/Condition Claim，拒绝错绑/篡改。B 仍在原 `planning_candidate_review.evaluate()` 的同一审核调用与问题目录中，通过冻结 Scope、Policy、Header/Condition 依赖摘要，在原 `recheck()` 下令改变了依赖的 ACCEPT 失效。Shared Repair 仍在原唯一 `repair_used` 许可内；视觉 Target 的值＋新 Claim 同槽交接，必要性/音频/其他 Target 的原合同未被放宽。原 `SEMANTIC_CHECKPOINT.json` 与 Journal 冻结新 `creative_claims`；原生 `verify()` 从冻结 Handoff、原始 A/Repair/B 字节及 Policy 重建并对账，包括必要 B 重查结果与最终 Claim 状态。

**定向及联合软件实证：**新增 `tests/test_planning_creative_authority_owner_integration.py` 三个原生 Owner 用例：(1) 正常 A→B→Checkpoint、独立副本冷恢复及篡改 Claim 拒绝；(2) 真正 B CHALLENGE→唯一 Shared Repair→B-recheck→正式 verify，重入时原 request/reply/session SHA 不变，已修复 Claim 的 Journal 篡改被拒绝；(3) Checkpoint 写入中断后保持 `PERSIST_FAILED` 与原 `repair_used`，恢复时复用全部原调用而非重派。D0/D1/B/Repair **129 PASS（旧 126＋新 3）**；原当前 New-Only `tests/test_creation_preparation.py -k current_planning` **10 PASS，111 deselected**；AST/差异检查 PASS。测试仅以合法固定外部模型回执驱动真实内部软件 Owner，**不是**真实 MiniMax/Web E2E、D2 独立 issue 分类、D3 真实 Hard 消费、U4 Gate 或 Release 验收。

**限定结论：**`D1_CONTROLLED_OWNER_SOFTWARE_PASS`，接线已在同一 Owner 内实现且显式新 Attempt 可用，**默认生产启用/外部真实模型适应性尚未验收或批准**。历史和旧 Journal 保持只读，新运行的原 Tool/UNKNOWN/费用和 Rights 仍遵守上层准入。下一轮需对新 D1 受控源码进行独立正确性/架构复核，特别核查不同视觉 Repair Target、批次最大容量、受控 Policy 生效点、Checkpoint 原子性和各 B 问题的依赖闭包；之后再决定当前新 Web Creation 的默认启用及 D2 正式语义分类。U4=BLOCKED，U5/U6 未启动。

RESULT=COMPLETE（仅 D1 受控 New-Only Owner 软件接线与当前版本冷恢复验证）
DRIFT=NO_DRIFT
EVIDENCE=原生 Owner 3 PASS；联合 129 PASS；原 New-Only 回归 10 PASS；A 原始捕获、B/Repair/recheck、原生 Journal/Checkpoint 严格重建/篡改拒绝、PERSIST_FAILED 恢复与无重复 Repair
NEXT_SINGLE_ACTION=对新增 D1 受控单 Owner 接线做定向架构/正确性审核，并在审核与用户准入满足后另行决定新 Web Attempt 默认启用及 D2 语义审核；不自动触发真实模型/E2E
TRANSITION=HOLD（软件集成收口，U4 与真实生产 Gate 不变）

### 8.14 D1 正式 Preparation 首次执行 Policy 冻结｜New-Only 收口（2026-10-15）

**最终启用边界：**已将 `web/app.py` 的唯一正式 `_material_planning_executor` 标识为 `creative_claim_policy=planning-creative-owner@1`。正式 `creation_preparation.py` 只把该 Policy 交给 `create_film_attempt` 原子创建新的、合法 Proposal @4/New-Only Attempt；`hypit/service.py` 仅新建分支保存 `creative_claim_policy`，同 `preparation_key` 的已有 Attempt 原样复用；若已有记录没有同一 D1 Policy，则**在修改已有 Runtime/Profile 状态前拒绝升级**。Preparation 从 Attempt 的已冻结字段传入 Planning Context，在首次 Model dispatch 前登记现有 `planning_contract_version=3` 并复核 Policy。D1 一旦冻结，同 Attempt 恢复只能携原字段运行；没有补写老 Attempt、迁移旧协议或重派 UNKNOWN。使用的仍是唯一 `semantic-planning-vnext` Journal/Checkpoint 与原单次 `repair_used`。

**验证：**新增 `tests/test_creation_preparation.py` 两项业务测试：全新合法 New-Only Attempt 的 D1 Policy 在 executor 前写入且同 Key 恢复无新 Attempt；已有未冻结 D1 的 v3 Attempt 在正式 D1 executor 启用时被拒绝、不能再派发。专项 2 PASS；联合 `tests/test_planning_creative_authority_owner_integration.py`、D1/D0/B Identity/Repair、现行 Preparation current_planning 回归 **141 PASS，111 deselected（76.76s）**，覆盖原生 checkpoint/独立冷恢复/篡改拒绝、Repair 一次、写入中断恢复、B P0 UNKNOWN 不重复提交。AST 与 `git diff --check` PASS。仅固定回执的软件验证；未运行真实 MiniMax/Provider/Build/Web E2E，未部署、commit/push。旧 U2 受测指纹不适用于当前 dirty 工作区。

**范围结论：**D1 在**源码中的正式新 Attempt Preparation 路线**启用与首次身份冻结已完成；仍需同版实际 Web/Runtime Gate 与真实模型授权，不能把软件 PASS 冒称 U4/U5 或证明实际大模型稳定。D2 B 语义分类和 D3–D4 消费验收不在本轮范围。

RESULT=COMPLETE（D1 正式 Preparation 新 Attempt 首次 Policy 冻结及软件回归）
DRIFT=NO_DRIFT
EVIDENCE=2 新增正反测试；联合 141 PASS；正式入口冻结/已有 Attempt 拒绝升级；原生 D1 Journal/Checkpoint 冷恢复、单次 Repair、UNKNOWN/预算旧约束回归
LESSON=同 Preparation Key 可以复用旧 Attempt，D1 Policy 必须写入新建 Attempt，而不能在恢复时补写
NEXT_SINGLE_ACTION=对正式入口 Policy 冻结和 D1 Owner 做一次定向安全/正确性复核后，在 U4 现有准入与独立授权满足时继续新的真实 Web Attempt；不自动进入 D2 或重跑历史执行
TRANSITION=HOLD（当前软件工作包完成，U4=BLOCKED/U5-U6 未准入）






### 8.15 D1-FINAL｜实施前范围和验收冻结（2026-10-15）

**范围：**仅关闭新合法 New-Only Attempt 的 D1 身份链：首次创建时持久化 creative_claim_policy；PlanningContext、正式 Owner run、唯一 Journal/Checkpoint、原生 verify 必须与该 Attempt 身份一致。既有 A Claim / Shared Repair / B Recheck 已正确者不修改。历史/旧 Attempt 不兼容、迁移或重派。

**身份不变量：**[I1] 初次创建才能设置 D1，重复 Preparation Key 必须保持原身份；[I2] Attempt=Context=Owner Journal/Checkpoint，同 Attempt 冷恢复时继续一致；[I3] 通用更新不得增删改冻结字段，尤其无 D1 的既存 Attempt 不可升级；[I4] A/Repair 原始字节、SHA、Scope/Mode/Schema 及 B 依赖可冷重建；[I5] repair_used 仅一次，UNKNOWN 不自动重派；[I6] Claim 不创造 Creator、Rights、费用授权。下游 Build Retry/Quality Repair 仅核查安全拒绝，不在 D1 扩建复制/制作能力。

**冻结验收矩阵：**1 新 Attempt 首次冻结；2 同 Attempt 恢复不重派；3 已存在非 D1 拒绝升级；4 Attempt/PlanningContext 错配拒绝；5 Attempt/Journal/Checkpoint 错配拒绝；6 原 A/Repair/SHA/Scope/Mode/Schema 篡改拒绝；7 Claim-only 旧 B ACCEPT 失效；8 混合 Repair Claim 保留；9 Repair 预算一次；10 持久化中断原调用恢复；11 UNKNOWN 无可信终态不重派；12 Material V1.3、Truth、Rights、声音合同无回归。只增缺少的跨入口正反测试，固定外部回执的原 Owner 软件集成、冷恢复、故障注入证据与真实模型/正式 Web E2E 严格分开。

**修改白名单：**现有 hypit/service.py 的 Attempt 更新保护、web/app.py 正式 Owner 入口、semantic_boundary_run.py run/verify 与现有必要测试。不得新增 Agent/Owner/状态机/预算、D2 B 语义分型、DecisionProof 服务、D3 Hard 消费、D4 Build Retry 扩建。非阻断质量问题记归属而非追加 D1。

**结束：**同根因连续两次最小修复失败即止损；先冻结本矩阵，最小修复、定向验证、联合回归、一次终审、Closure。受测 HEAD + 工作区文件/hash/diff 指纹记录后，若全部通过写 D1_SOFTWARE=PASS 并停止开发，后续 U4/U5 按原 Gate 与单独授权；若未过只报唯一阻断根因。

### 8.16 D1-FINAL｜最终软件验收 Closure（2026-10-15）

**冻结矩阵及范围：**以 §8.15 的 6 项身份不变量、12 条固定矩阵作为唯一 D1-FINAL 准则。此次只修改原 Attempt 更新、正式 Owner、原生 verify 及现有测试。没有增加 B 语义分类、逐项 DecisionProof、Material V1.3、Build Retry 实现、第二个 Owner 或新增共享 Repair；不为历史 Attempt 提供兼容。

**实现与证明：**`hypit/service.py` 的共享 `_save_attempt()` 在回调执行前冻结原始 Policy 存在性与值，阻止返回新字典或原地修改的回调添加、删除、覆盖 creative_claim_policy；通用 `update_film_attempt()` 也提前拒绝；首次 `create_film_attempt()` 才可写入 D1。`web/app.py` 正式 Owner 首次入口与 `semantic_boundary_run.run()` 都强制 Attempt/PlanningContext Policy 相等；`semantic_boundary_run.verify()` 强制 Attempt/Checkpoint 所冻结 D1 Policy 相等。原始 A-selection/A-details、Header/Condition Claim、B Question/Shared Repair/Recheck、同一 Journal/Checkpoint 和 repair_used/UNKNOWN 原模型调用防重派沿用既有实现。独立隔离负例证实直接 Owner 错配、已存在非 D1 升级、共享更新/底层 Attempt mutation 与冷验证错配均 fail-closed。

**真正内部贯通：**新增合法 Proposal @4 / 新 D1 Attempt 固定回执软件测试，实际经过 Preparation → 原生 A/B → 同次 Shared Repair → B Recheck → Journal/Checkpoint → `PlanningIntegration.load()` 与 `semantic_boundary_run.verify()`，重入复用原 Attempt 与原 request/reply SHA。下游 Quality/Build Retry 只核对当前未拥有 D1 决策的复制路径不可据此认领新 Attempt，任何合法继承改造留 D4，未修改。

**最终证据（同一源码版本）：**`tests/test_planning_creative_authority_owner_integration.py`、D0/D1/S1、B Identity/Repair、Preparation current_planning，合计 **143 PASS / 0 FAIL / 111 deselected，89.67s**（固定外部回执，非真实模型）；新增正式 Preparation 贯通单测 **1 PASS（7.73s）**；原生冷恢复/故障注入、Claim/Mode/Scope/Schema 篡改拒绝、共享 Repair 一次与 B UNKNOWN 不重派按冻结矩阵回归。AST、`git diff --check` PASS。

**受测源码身份（变更记录非发布指纹）：**分支 `easel-studio`，HEAD `d82bb60b07240a3dd0d776ec00a33c68f71cab50`，受测当时 29 项未提交路径；追踪文件 pre-Closure diff SHA256 `d37981b496f447234a69ef1e5cf34141f0d95792f06ae33469ae8685fe3312d6`。源码 SHA256：web/app.py `b24fe0c7578e7e61e0a6e1522614b6ad9e4eba5ed899009885cdffcf1e269464`；creation_preparation.py `3ff528b5d1bc9d7b48758dd38080d3ca6054af503479eb5603d237194df6cd7f`；hypit/service.py `3ce8f5acb3ea5fed5d7f4037bc401c55d58d086676776895fc0a1c2307f6324b`；semantic_boundary_run.py `0e9c248e50738555fcb4f579831a384dc779232f628a6703dc3f0d1918da4bc7`；planning_creative_authority.py `73ebf6565230d733033bce7920860e4782af5d4e5142cb6a5cdcdd9ca368e7af`；Owner 集成测试 `9bf1292859fe7dea03af96f292d32b8ebfe083486d2e74dc140a74645e0eba23`；Preparation 测试 `779df670561c6b6990d7e52e67a9c904a3d3a509e1d9bd9596a61cb685098995`。Closure 文档更新发生于该软件受测基线之后；未 commit/push/部署。

**终审与责任边界：**D1 仅保证可追溯的导演 Claim、Policy/原始回执身份、B 审查依赖与唯一 Owner 冷恢复。D2 负责 B 语义分类和授权结论/正式逐项 Proof；D3 负责 Material/Authoring/Quality Hard 消费；D4 负责继承/Build Retry/完整制作联调。本轮没有证明真实 MiniMax 语义质量或视频 E2E，U4=BLOCKED，U5/U6 未准入。依当前固定 D1 软件合同，无进一步确认的阻断；D1 代码停止扩展。

RESULT=COMPLETE
D1_SOFTWARE=PASS
DRIFT=NO_DRIFT
EVIDENCE=固定12项矩阵；143 PASS/0 FAIL；完整 Preparation→Owner→冷验证；身份错配拒绝；原始单 Repair、UNKNOWN 无重派；受测源码 SHA
LESSON=任何启用 Policy 必须由 Attempt 一次写入并在所有进入/恢复边界同源校验，不能以分层测试 PASS 代替跨入口负例
NEXT_SINGLE_ACTION=回到现有 Creator Task 的 U4 真实 Web/Runtime/Rights/额度准入阻断核对，或经用户另行授权启动 D2；均不自动执行、不得重启 D1 循环补丁
TRANSITION=HOLD（D1 软件已完成，仅 U4/有价模型/Web E2E 仍受原 Gate 和独立授权约束）
### 8.17 D2｜B 类型化审核和 Planning-local Proof 实施冻结（2026-10-15）

**当前 D1-FINAL 是冻结前置，不重开。** D2 只处理原视觉 B 问题的四类审查轴：confirmed_fidelity、delegated_creative_validity、responsibility_enforcement、coverage_uncertainty；在原 B question、原一次 Repair 与原 Owner Journal/Checkpoint 之内完成来源依据、审核结果及实际问题责任。没有新 Agent、模型调用、Material Domain 对象或第二次 Repair。

**本轮冻结的判定合同：**问题必须有明确轴及实际 Claim 内容（单个摘要不足以判断导演意图）。B 输出仍以 ACCEPT/CHALLENGE/UNRESOLVED 为权威 decision，限定 issue_code ∈ {none, source_or_truth_violation, director_replan_needed, creator_decision_required, material_supply_pending}；issue_owner ∈ {none, director, creator, material, source_truth}。无问题只能是 ACCEPT+none+none；director_replan_needed 只能 CHALLENGE+director，在原合法 patch target 范围内执行一次 Repair；creator_decision_required 属不能自动修复的阻断；source_or_truth_violation 必须保留来源/Truth 原合同并视可修范围拒绝或 Repair；material_supply_pending 只有经核实已存在的 MaterialNeed 承担全部已确认义务，且未知仅来自下游素材/Rights 供应时允许作为执行待办，不得声称 Rights/MATERIAL_READY，也不能掩盖新 Creator 授权。新 Hard 必须有确定的消费者能力/责任合同，D3 尚未证明的执行结果不得伪造。

**DecisionProof 仍位于 Planning：**每个接受的视觉 Need Header/Condition 编译 (Attempt、Scope/Mode/Proposal、Need index/path、值 SHA、Claim、冻结 B question/reply 原文身份、审查轴/决定、责任/预期消费者)，与本次 Plan/Checkpoint 同事务保存，原始 B 非 ACCEPT 不得转成已授权 Proof，程序不得将 A Claim 视为 Creator 或 Rights 授权。Proof 冷恢复从原 A/B/Repair Wire 重建。不得增独立 Proof Service。

**完成条件：**九条历史 R02 类型化正反变体及同一 Creator/Mode 的三个独立 Content 通过原 B/Repair 身份与来源合同；Claim-only 变更触发原 recheck；合法 A→B→Truth/Plan 固定外部回执经过现有 Owner、原始 Journal/Checkpoint 冷验证；共享 Repair 一次、UNKNOWN 无重派，Voice/BGM/Truth/Rights/Material V1.3 不变。不以历史 R02 FAIL 变 ACCEPT 为目标；不要求真实 MiniMax 或正式 Web E2E。未达全部标准只能记 PARTIAL，不自动进入 D3。

### 8.18 D2｜类型化 B Review 与 Planning-local DecisionProof 软件收口（2026-10-15）

**冻结的交付边界：**在 §8.17 五种 issue_code/issue_owner、四个 review_axis、旧 ACCEPT/CHALLENGE/UNRESOLVED 与唯一 Repair 合同下，已接到原唯一 `planning_candidate_review` 和 `semantic_boundary_run.run()/verify()`。新合法 New-Only Attempt 首次创建同时冻结 D1 `creative_claim_policy=planning-creative-owner@1` 与 D2 `d2_review_policy=planning-d2-typed-b@1`，正式 `web/app.py` Planning executor 已声明二者；已执行 Attempt 不自动升级。Attempt 共享写入的两个 Policy 均不可更改，任一直接 Owner、Context、Checkpoint 身份错配拒绝，未增加 Agent/Workflow/有价调用阶段。

**真实内部软件接线：**新 `planning_d2_typed_review.py` 从 D1 `creative_dependency` 摘要对账后，将真实完整 Header/Condition Claim 与四审查轴加入原 B 问题；`planning_candidate_review.batches()` 仅在已冻结 D2 时编译有界 `issue_code/issue_owner` Schema 与 `decision` 合法组合，`_row` 仍走原 B Support/quote/role validator 并严格核对组合。`semantic_targets()` 将 `creator_decision_required`、`source_or_truth_violation` fail-closed，`director_replan_needed` 仅在原 Repair 合法 target 内消费唯一修复权限，`material_supply_pending` 只有原未决报告、现有相关候选与独立支持证据可被移交为供给待办，不能授予 MATERIAL_READY 或 Rights。原 `question_id` / B Identity / RepairEvidence / 原 Tool reply / UNKNOWN / 预算没有第二条执行路径。

**原生 Proof 与冷验证：**每个最终 `ACCEPT` 审查候选生成 Planning-local `d2_decision_proof`，记录 Attempt、冻结 Claim kinds/Scope、Header/Condition/Need target、候选/问题摘要、B 依据与 issue_owner、强度/责任、预期消费者、真实 B 各阶段原 reply SHA；下游实际履约一律为 PENDING_OR_NOT_APPLICABLE，Rights/MaterialReady 为 false。Proof 与唯一 Checkpoint 同一次写入，原生 `verify()` 复算 B/Repair/Claim 和原回复完整集合，篡改拒绝；D3 不回写已冻结的 Planning Proof。

**验收范围及实证：**历史 R02 九题按真实归档原 request/reply SHA 逐题核对原 8 CHALLENGE + 1 UNRESOLVED 不改判，再做合成合法/非法类型组合对照；三独立合成 Content 采用真实已确认 Proposal @4、相同 Mode 的冻结 Context/Claim，分别测试 D2 Proof 身份及跨作品错绑拒绝（**不是**三条真实模型或三条完整新 Owner 视频 E2E）。新合法隔离 Attempt 原生 Owner 的 0 Repair、一次 Shared Repair → B Recheck、Checkpoint/独立副本冷恢复与篡改拒绝，以及真实 Preparation→B/Proof→PlanningIntegration.load→同 Attempt 恢复均 PASS。合并既有 D0/D1/B Identity/Repair 与当前 Preparation 软件回归 **176 PASS、0 FAIL、105 deselected，111.63 秒**；AST 与 `git diff --check` PASS。全部外部模型回执为合法固定测试替身，不声称 MiniMax 真实 B 语义质量、Web E1、Rights/Build 已准入。

**受测源码身份：**`easel-studio`，HEAD `d82bb60b07240a3dd0d776ec00a33c68f71cab50`，本轮 32 个 dirty/untracked 路径保留；受测追踪差异 pre-Closure SHA256 `3431128978c8229207f316812788495963ce121bc9d6ef3c1820661d0d491397`。新增 D2 模块 SHA256 `89eb9f9718565392f733fa71696b77e04c269beff4da3d53ac613ee7d03f2def`、D2 typed test `0ba9523e944e171994c265ad08e39907c3bba38c57ae3427d703d4be4f8c132b`、D2 Owner test `c37264648afbe13b501605f3ad9ae506a8244da243103f5e4f98d255e9c615d7`、正式 Owner `07eb02b88d788872e5091749d7e8101186691e8b92b944a0ffb477bfeddba3fe`、Web `417625f23f5f5a5077416f7b499ccc9cee400eb0efa1d5656eea63eb79a06957`。本次记录为受测工作区代码内容，尚非提交/部署/发布指纹。

**阶段边界与转交：**D2 已完成定义内的视觉 B 类型化软件合同和本地 Proof；D1-FINAL 不重开。D3 独立核实 Material/Native Authoring/Quality 对不同 Hard 的消费者能力和真实履约方式；D4 再做三内容完整原 Owner 软件链以及 Build Retry/继承与出片软件交接。U4=BLOCKED、U5/U6 未进入；不得以 D2 的固定回执 PASS 增加或绕过任何正式 U Gate。未取得独立 Astra 审核，不宣称已发生。

RESULT=COMPLETE（仅 D2 Planning 软件合同）
D2_SOFTWARE=PASS
DRIFT=NO_DRIFT
EVIDENCE=R02九题真实原件与类型正反矩阵；三Content合成跨作品 Proof；原 Owner 0/1 Repair、B Recheck、Checkpoint cold verify、完整正式 Preparation；联合176 PASS / 0 FAIL
LESSON=真实 B Policy 必须在首次 Attempt 固定后同时进入原 Question/Schema/原回复/Proof/Checkpoint；不可把语义分类等同下游执行已履约
NEXT_SINGLE_ACTION=在现有唯一 Creator Task 内申请并实施 D3 消费者交接与 Hard 能力验证，先冻结 D3 范围；不重新打开 D1/D2 或自动进入真实模型/Web E2E
TRANSITION=HOLD（本轮 D2 软件完成；后续 D3 需按现有任务顺序另行执行，U4 仍 BLOCKED）

### 8.19 D3｜Hard 消费者合同冻结（2026-10-15，实施前）

**唯一范围：**D2 原始 Planning-local DecisionProof（仅审查批准，不证明履约）→ Material/Authoring/Quality 既有证据和职责。三种 Hard 分开验：素材 Hard 的原 `MaterialNeed.intent.description/constraints` → 既有 frozen requirements/Observation/Matching/Rights/Readiness；后期/叙事 Hard 的 `intent.function` → `POSTPRODUCTION_REQUIREMENTS.json(PENDING_AUTHORING)` → OpenClaw Authoring SHA、Native Authoring/当前 Output SHA/Quality 帧复核；跨镜连续性 `continuity_refs` 仅是软线索，强物理同一必须另有资产真实身份、可观察的画面和放置证据，否则停在 PENDING/UNVERIFIABLE，不能由评分或 Prompt 标记 PASS。

**D3 必须遵守：**Planning 阶段无 Asset、无 Build、无 Output 时允许存储和加载合法 Plan/Proof；不能反向要求 Materials READY 才允许 Planning。D3 只消费 frozen D2 Proof 与 `SEMANTIC_CHECKPOINT`、正式 Plan/requirements、Material/Authoring/Quality 已存在的合同，不修改 Material V1.3 Domain 或引入新 Reviewer、状态机、所有者、READY。Rights UNKNOWN/RESTRICTED 不获得 MaterialReady；没有 Match、素材或权益应由原 Gate 拒绝。`POSTPRODUCTION_REQUIREMENTS`/文本指令只能证明合同已传递，不能证明已执行；Quality 的 `Output SHA + execution fingerprint + cited actual frames` 才可能形成相应客观履约证据，审美最终由 Creator Review。

**完成矩阵：**① 合法 D2 的当前 Plan 可在空素材/空 Output 下保存、冷加载；② D2 Proof/Plan Need/Condition/原始 SHA 精确映射且跨 Attempt/Need/index/Scope/Mode/Output SHA 错绑拒绝；③ Material source-required + Rights UNKNOWN/无真实 Match/无 Bundle 正确阻断；④ postproduction required→带来源和合同 SHA 的 authoring 输入且 PENDING 不晋升；⑤ 无 Authoring/Quality 证据不能将 Hard 认领为已履约；⑥ Continuity soft 是候选线索，物理 Hard 无资产身份+placement+observed evidence 必须标 UNVERIFIABLE/阻断，不编造视觉识别器；⑦ 现行 Audio、Truth、Rights 和 Material V1.3 不回归。仅消费合法固定回执、真实内部测试；不触发 MiniMax/Provider/Hypit Build/Web E2E。D4 的三 Content 完整生产与 Build Retry 不在本轮。

**止损：**只处理验证暴露的合同缺口，独立的未来质量改进不升级为 D3 阻断。所有必需矩阵通过且原 Owner/Material/Authoring/Quality 原有测试通过后才写 D3_SOFTWARE=PASS，仍不冒称真实 Hard 已在某部片子完成。

### 8.20 D3｜Material / Authoring / Quality Hard 消费者合同最终软件 Closure（2026-10-15）

**实现与边界：**在原 `PlanningIntegration._load_contract()` 经原 `semantic_boundary_run.verify`、正式 requirements 与 Truth 验证后，针对已冻结 D2 的全新合法 Attempt，调用新增纯只读 `planning_d3_consumers.describe_consumers()`，使用原 Checkpoint `d2_decision_proof` + `proof.layouts` + 当前正式 MaterialPlan，严格定位 `need_id/candidate_index/condition_index/Condition SHA/strength/responsibility`；错 Attempt、原 Condition SHA、消费者身份、伪造 Rights/MaterialReady/Quality 完成状态一律拒绝。无新状态机/Agent/模型调用，Material V1.3 Domain、D1/D2、Rights/费用/Truth、原 Material Gate 均不改。产物是 Planning load 的只读 `consumer_contract`，不写回 Checkpoint、不自动发行 READY。

**三类消费者合同：**(1) Required/material 条件继续由 `MaterialNeed.intent.description/constraints` → `planning_contract.bind_requirements` → Material Observation/Matching/Rights/Readiness → `MaterialGateIntegration.assert_ready` 强制；D2 审核 PASS 不会令素材自动 READY，缺资产/Match/Rights 禁止 Authoring。(2) Required/postproduction/narrative 在 `MaterialNeed.intent.function` 有确切原文，履约主体标记 `authoring_quality_pending`；原 `ProductionAuthoringIntegration.prepare` 的 `POSTPRODUCTION_REQUIREMENTS.json` 带 Need/条款文本与 contract SHA 并保持 `PENDING_AUTHORING`，`openclaw_authoring` 用字节 SHA 拒绝修改，原 Native/Quality 继续用实际 Output/执行指纹与被观察画面判断；这些尚未执行时不能宣称履约。(3) 跨镜 `continuity_refs` 只为软候选匹配，D3 对真实/合成任何声明仅记录相关线索，`physical_identity_proven / placement_proven / observed_continuity_proven=false`，无三证即 `BLOCKED_UNVERIFIABLE`，不补建视觉识别和新 Quality Reviewer。可允许合法无 Asset/Output 的 Planning/Proof 正常保存与冷加载。

**验证：**新增 `tests/test_planning_d3_consumers.py` 共 **4 PASS**：真正合法新 D2/Proposal @4/原 Owner 与 PlanningIntegration.load 的 Material、Authoring Hard 映射/空资产允许；跨 Attempt、Condition SHA、消费者角色、冒称 READY/Quality 篡改拒绝；无素材/Output 原 Gate 拒绝；虚构连续性线索不会冒充硬履约。现行真实内部 consumer 正向/负向用例（`test_u2a_material_v13_current_supply_and_rights`、隔离 Authoring SHA 和允许文件、`test_system_quality_cannot_pass_unseen_or_stale_frames`、音频物理测量/裁剪拒绝）**同轮 PASS**。D0–D3/B/Repair/当前 Preparation + Consumer 精选联合 **185 PASS / 0 FAIL / 373 deselected，154.66s**，AST / `git diff --check` PASS。全部仅固定外部回复与离线软件，无真实 MiniMax、媒体 Build、Web E2E、Creator 真实审片。**特别保留独立旧夹具失败原件**：`tests/test_material_integration.py::test_visual_chunks_resume_with_fixed_requests_and_preserve_planning_contract[False]` 在 D3 前被原 v3 Planning.persist 准入拒绝（该次调用 4 PASS/1 FAIL，非本轮合格新 D2 路径）；未宽松改合同或冒称全部旧测试全绿。此旧夹具是否应迁移，归单独测试债，不作为 D3 新生产缺陷。

**受测源码身份：**`easel-studio` HEAD `d82bb60b07240a3dd0d776ec00a33c68f71cab50`，受测 35 条未提交/未跟踪路径；pre-Closure tracked diff SHA256 `935010d3096318450991d1335db42fba21182bbe43cb41fb853a353c4f16b334`。新增 `easel/integrations/planning_d3_consumers.py` SHA256 `1c7fb48f775ff3e7acfc03f605da7539ce8e5c3c13ef8866929bb2ab8c8e22a9`，既有 `easel/integrations/material_layer.py` SHA256 `ad06638f2d7b31fa56a74ddb0e31c48edef6f4c82c7bbab5fd2d2b522e1441d4`，新增 `tests/test_planning_d3_consumers.py` SHA256 `9e246b9c258df599aed36e7f8dd888b7a2cb88d33a0bcc4c223eb446d8fc3389`。只是受测脏工作区源文件指纹，不是正式发布指纹；未 Git commit/push、未部署。

**最终边界：**D3 证明 Hard 的来源约束、具名消费合同、哪些能力有原生验证入口、尚无履约时的 fail-closed；绝不证明跨镜物理同一/叙事艺术效果已经在真实视频中完成。真实资产、Native placement、System Quality、选片及所选 Output SHA 仍由对应消费者于原阶段取得。D4 必须另行验证三个不同 Content 原 Owner A/B/Truth/Plan/Proof/Hard 消费软件端到端与 Build Retry/Checkpoint 继承，不把 D4 回填 D3。

RESULT=COMPLETE（D3 软件消费者责任与未履约阻断合同）
D3_SOFTWARE=PASS
DRIFT=NO_DRIFT
EVIDENCE=4 新 D3 正反 + 原 Material/Authoring/Quality 真实内部测试；联合 185 PASS；旧视觉分批夹具 FAIL 单独保留；D3 不发行 READY
LESSON=Planning Proof 只签审查事实，原 Material/Authoring/Quality 以实际资产、Output 和观察证据签履约；软 continuity 不能代替物理身份
NEXT_SINGLE_ACTION=经明确授权启动现有 D4｜三 Content 原 Owner 全软件闭环与冷恢复，随后冻结整个 Planning 专项并回归 U4；不自动重开 D1–D3、旧历史或真实模型
TRANSITION=HOLD（D3 软件工作包完成，等待 D4 授权；U4=BLOCKED/U5-U6 未准入）

### 8.21 D4｜三 Content 原 Owner 软件闭环验收范围冻结（2026-10-15）

**唯一目标：**三个不同 Content、同一个 Creator/Creative Mode，各独立新 Proposal@4/Attempt，使用原生 Preparation/Owner 完成 A-selection/A-details、typed B Review、0/1 Shared Repair、Truth、Plan/Requirements/DecisionProof、D3 consumer_contract、原生 verify 与冷恢复。外部 Agent 回复全部为固定回执。D1–D3 不重开，不新增状态机、模型、Build、旧 Attempt 恢复。

**冻结七项验收：**[1]三作品 Creation/Attempt/内容/Truth/Proposal SHA 不同，Creator/Mode 冻结相同；[2]每条真实 Owner A/B/Truth 与原始捕获、Journal/Checkpoint、Plan/Requirement、Proof/消费者均闭合；[3]0/1 修复和同 Attempt 恢复不重派，不放宽 UNKNOWN；[4]跨作品 Scope/Mode/Condition/Consumer/原 B 回执、Output SHA/Rights/权限冒领 fail-closed；[5]尚无真实素材/Output 的合法 Plan 可保存冷加载，Material Gate 不虚假 READY；[6] Build Retry/Checkpoint 继承无权认领其他 Attempt 身份，实际媒体重制留现有 U4–U6；[7] Truth/Audio/Material V1.3 不回归。

**收口：**冻结一次矩阵→最小合法 fixed-reply fixture/必要产品修复→三条原生 Owner 贯通→联合回归→版本 SHA/Closure。绝不以 D0 的纯上下文隔离矩阵替代完整三 Owner。失败两次不循环扩张，记录唯一阻断与 PARTIAL。全部 PASS 方可标 PLANNING_SOFTWARE_COMPLETE；本轮无真实 MiniMax/Provider/Hypit Build/Web E2E、部署、commit/push，产品 Gate U4 仍 BLOCKED。

### 8.22 D4｜三 Content 原 Owner 软件闭环与 Planning 全专项冻结（2026-10-15）

**范围与实施事实：**严格按事前 §8.21 冻结矩阵，本轮新增且只新增 `tests/test_planning_d4_three_content.py` 软件联调用例，不改原 D1/D2/D3、Material V1.3、旧 Attempt、Result Pins、预算或视频生产路线。采用 D0 已确认的三个不同 Content（AI 学习、工作实践、生活观察），相同 Creator/Creative Mode 文档，每个 Content 独立合法 Proposal @4/Handoff、新建 Attempt，首次原子冻结 `creative_claim_policy=planning-creative-owner@1` 和 `d2_review_policy=planning-d2-typed-b@1` 并登记 Planning v3。

**每条真正的原 Owner 链：**各新 Attempt 使用固定外部模型回执运行真实 `_current_vnext_planning_executor` 原生 A-selection/A-details → D1 Header/Condition Claim → D2 typed B Review → 原 Truth source review → MaterialPlan + 原始 Requirements 生成，然后必须经正式 `PlanningIntegration.persist()` 将 Plan/Truth ledger、原生 Checkpoint/requirements 保存（没有手工造 Plan 文件），再由 `PlanningIntegration.load()` 完整验证 Truth、原 `semantic_boundary_run.verify()`、D2 DecisionProof、D3 Hard 消费待办。不同内容在各自冻结 Script/Scenes、Content/Truth/Proposal/Attempt 上独立，Creator/Mode 同源；跨 Attempt 身份与改变 Mode 的原生 verify 明确拒绝。对同一 Attempt 重新运行旧固定回执不增加/替换 A/B 的 request/reply SHA；未供应素材继续由 `MaterialGateIntegration.assert_ready` 拒绝，D3 合同保持 `PLANNING_HANDOFF_ONLY`。没有启动 Hypit Build/Provider、没有标记视频 READY。

**验收证据：**3 个新独立 Content 的完整 Owner + Persist/Truth/Requirements/Proof/Consumer + Native Verify/冷恢复软件用例 **3 PASS（19.57s）**。D0–D4、B Identity、Shared Repair、Material V1.3、Authoring/Quality 当前定向回归在同一源码版本 **188 PASS / 0 FAIL / 373 deselected，171.93s**。Python AST 和 `git diff --check` PASS。外部 Agent 回复全为固定替身，非真实 MiniMax/Web E1。原先旧 `test_visual_chunks_resume_with_fixed_requests_and_preserve_planning_contract[False]` 因不符合当前 New-Only v3 准入失败的证据继续单列为旧夹具测试债，未改写/放宽，也不冒称全项目测试全绿。

**当前受测版本身份：**`easel-studio`，HEAD `d82bb60b07240a3dd0d776ec00a33c68f71cab50`，D4 受测时 36 项未提交/未跟踪路径；pre-Closure tracked diff SHA256 `ecadbcbea1569824d8ad02fed1d58fa3af1f9e155359cff0b5a16e63544e1244`；新增 D4 测试 SHA256 `fc6a9e24fd2cce9fd3ad3c75e4acb92ab87aba360ca6a73316d626c1f05a3afd`；原 Owner `semantic_boundary_run.py` SHA256 `07eb02b88d788872e5091749d7e8101186691e8b92b944a0ffb477bfeddba3fe`，D2 typed 模块 SHA256 `89eb9f9718565392f733fa71696b77e04c269beff4da3d53ac613ee7d03f2def`，D3 consumers 模块 SHA256 `1c7fb48f775ff3e7acfc03f605da7539ce8e5c3c13ef8866929bb2ab8c8e22a9`。受测工作区不是 Release fingerprint，所有变更仍未 commit/push/部署。

**正式收口：**D0 合同边界、D1 原始 Claim/冻结恢复、D2 typed B/DecisionProof、D3 消费者责任与未履约阻断、D4 三 Content 原 Owner/Truth/Plan/Proof 软件贯通均按本软件矩阵通过。**Planning 专项从现在起停止继续开发和额外性能/十样本实验。** D4 并未构建真实 MP4 或验证模型的创作质量；Build Retry 对新 Attempt 的合法继承/真实制作仍按原 New-Only U5/U6 Gate 处理，不能因此冒领源 Attempt 权限或建立新的 U Gate。后续任何现实故障只在正式 U4/U5 首个实际失败关口按原权责定点定位，而非泛化重开 D1–D4。

RESULT=COMPLETE
D4_SOFTWARE=PASS
PLANNING_SOFTWARE_COMPLETE=PASS
DRIFT=NO_DRIFT
EVIDENCE=三独立 Content 原 Owner/Truth/Plan/Proof/D3/冷验证 3 PASS；同版联合 188 PASS/0 FAIL；错误 Attempt/Mode拒绝；原 UNKNOWN/Repair 边界回归；完整源码 SHA
NEXT_SINGLE_ACTION=立即回到现有唯一 Creator Task 的 U4 无副作用 Web/Runtime 同版、浏览器权限、Rights/技术额度及现金上界准入核对；U4 PASS 后须获得逐次授权才可在 U5 用新 Web Creation 做真实短片 Debug
TRANSITION=HOLD（Planning 软件任务已冻结，U4=BLOCKED、U5/U6 未准入、正式 Release 未授权）

### 8.23 Real M3.1 A-selection｜D1 来源身份与导演依据混用的根因及修订合同（2026-10-15）

**原始证据与根因（不改原件）：**真实 MiniMax M3.1 原 A-selection 回复 SHA256 `237817c9d3e1a746fb105513d6a04c1f9f3e38cef2ccf45ceb920a55c5da3951`，11 个 Need 中 7 个视觉 Need 的 `scope` 分别是 event-4 至 event-10 对应的独立 src_*，而 `header_claim.creative_goal_ref` 都引用合法的 `SCENES.md/whole_document` global src_*。前者是 **Need 的具体源事件/位置**，后者是 **A 声称 Director 取舍的冻结创作依据**。原 Wire Schema 的枚举允许后者选择 global，却在 Decode 隐式要求二者相等，旧 canonical Claim 也把依据强制为 Need.scope；encode 甚至覆盖模型选择的 creative_goal_ref。这是模型字段的业务语义与程序绑定身份混用、Schema/Decode 不同构，以及证据可能被静默改写的架构问题。

**本轮修订的不变量：**(1) Need.scope 必须在本模态 SourceSelection 冻结允许集合，严格编译为真实 Material Need 来源；(2) A.creative_goal_ref 可以引用另外一个**同一 Creation 冻结 Catalog 内、当前视觉模态合法**的依据（例如确认分镜全文/具体事件），Program 不推断它的意义或替它改写；(3) D1 Claim 记录须将 Program 拥有的 `need_source_ref=Need.scope` 与模型声称的 `Claim.creative_goal_ref` 分别冻结，均参加 Record/Question/Checkpoint SHA；(4) Claim 的 `claimed_kind/reason` 只是待审模型陈述，无论引用哪个合法来源，不直接获得 Creator/Mode/Rights 事实授权；B 的 confirmed_fidelity/delegated_creative_validity/source/strength/consumer 轴独立判定语义能否支持，不能用合法路径替代合法主张；(5) `OpaqueHeaderBridge`、canonical Header Carrier、视觉 Condition/Repair Claim、Prompt 必须同口径，以明确的版本/Identity 让旧 frozen Checkpoint 无法静默套用新规则；旧 A/B/Repair 回执原件只读。绝不删等式后默许任意伪造 handle 或补造 Claim。

**验收：**对原已保存的真实 A 回复做不改原文的离线重放，证明 Event Need + Global Creative Basis 可作为 A 的合法候选进入后续 B（不是自动 ACCEPT），覆盖未知 handle/跨作品/漏 Claim/篡改引用和受测代码 Schema Replay、冷验证拒绝；复用现有 D0–D4/Material/B/Repair 定向回归。同一根因若需正式增 Policy 只改现有唯一 Owner，不创第二条审查或有价入口。再进行真实模型复验须重新按原 Gateway/持久化 HTTP 预算与用户独立授权，旧失败运行不恢复、不重派。

### 8.24 Real M3.1 Root Cause Closure｜模型语义与程序拥有的身份分离（2026-10-15）

**根因已证实（不是提示词偶发问题）：** §8.23 的首层问题是 Need.scope（明确的 event 来源位置）与 A 的 creative_goal_ref（可指向 global 整篇冻结分镜的导演依据）在原 Schema 中均合法，但 decoder 隐藏地要求相等，旧 encode 还覆盖了模型提出的 global 依据。进一步不修改已存原始 MiniMax A 回复、以新 Canonical 编译重放时，出现第二项同根问题：原 Header Wire 竟要求 LLM 计算 `continuity_choices_sha256`，实际 MiniMax 为 7 个 `continuity_choices=[]` 都虚构了 `9f3c1d7a...`，真实程序 SHA256 应为 `4f53cda18c2b...`；`claimed_necessity` 同样只是对模型自己输出的 Need.necessity 的重复回填。固定离线回执人为写对了这两个字段，因此此前 D0–D4 188 PASS 未暴露真实模型适配性。

**根因级修正：**现有唯一 Owner 的视觉 A-selection/Repair model wire 只由模型输出 `claimed_kind / creative_goal_ref / reason`，Program 在同一原 A/Repair 回执校验后，从模型真实选定 Need 原文计算 `claimed_necessity=Need.necessity` 与 `continuity_choices_sha256=SHA256(Need.continuity_choices)`；不得将程序派生信息称为模型证据。需要来源 `Need.scope` 与导演依据 `Claim.creative_goal_ref` 分别由 `SourceSelection` 原 codec 绑定合法冻结 ref，双 ref 在 Header/Condition/Repair Claim Record 中留 `need_source_ref` 和原 `creative_goal_ref` 并纳入 SHA；原 B 类型化 Review 明确需要独立判断这些依据是否真的支持 frozen_director_rule/confirmed_obligation/Hard，D2 DecisionProof 保存两引用关系但不会自动授权 Rights/Creator/Material。相关 `view_a_message` 明确字段责任和范围，`OpaqueHeaderBridge.encode` 禁止把原依据静默改写成 Need.scope。现有 Source/Claim/Repair Policy 版本逐项提升 @2，旧 Attempt/Checkpoint 不会在新规则下静默重解释。未修改 Material V1.3、Truth、声学、费用/UNKNOWN、Agent/Owner 数量、MiniMax Profile 或 Runtime 11/11 guard。

**原证据与验证：**真正历史 `~/.local/share/easel/creator-task-evidence/2026-10-15-planning-m31-actual-owner-eval-r01/live` 的 A 原 raw SHA `237817c9d3e1a746fb105513d6a04c1f9f3e38cef2ccf45ceb920a55c5da3951` 保持不变、HTTP 预算仍 `BATCH_FAILED`，原五字段旧 Wire 在新 Schema 下仍明确拒绝，**未通过删除/修写原回执制造真实 PASS**。测试仅在内存中以新三字段 Wire 对照原模型陈述，7 个 `event-4…event-10` 与 global 创作依据仍各自保留，连续性摘要由 Program 正确算出；未知 src、模型伪造 claimed_necessity/SHA、变更 Policy 及 Claim Basis 引发重新 B Review 的正反测试 **3 PASS**。D1/Repair 定向 **81 PASS**，D0–D4、B、Repair、Material/Authoring/Quality 选定同版联合 **191 PASS / 0 FAIL / 373 deselected，171.05s**；AST、`git diff --check` PASS。不意味着新的实际 MiniMax A/B/Truth/Plan 已经通过，也不能覆盖先前真实 FAIL。

**受测源码身份（仅 dirty workspace，非 Release）：**`easel-studio` HEAD `d82bb60b07240a3dd0d776ec00a33c68f71cab50`，当次 39 个 dirty/untracked 路径；pre-Closure tracked diff SHA256 `d056a08e9e67bbfd076a9d56c3069f063a2d10e152f4b7e01d25d4857d950b19`。关键源码 SHA256：`planning_creative_authority.py` `814b26ed83a715e2333d447d7e2146745991d907e21d34846dd0032f8dd42a82`；`semantic_boundary_run.py` `e8f7b663bc5acdd225ca88fd84fcc32d651deb138686dfd44ded417ec6d35a69`；`planning_candidate_review.py` `6bc0fb2387e9ad21d6eb95be7fade8029363bbaccc8c104c6b3a1ea482e10890`；`planning_d2_typed_review.py` `ad4d91c190b89c68053e9024c5d77128a6cfea2bf2337e12acb7193253710c83`；新增 `test_planning_real_claim_basis_regression.py` `29de69018c70158a439778a264bb3b19b9f7a4668073af40fa075253a84907c8`。没有 commit/push、安装补丁覆盖、服务重启、外部模型/Provider/Hypit Build/Web E2E。

RESULT=COMPLETE（真实模型首次失败的根因审计及生产合同责任修正/离线验收）
SOFTWARE_REGRESSION=PASS（191 PASS / 0 FAIL），REAL_MODEL_RETEST=NOT_EXECUTED
DRIFT=NO_DRIFT（原始真实回复、Old Run/预算不变；新旧 Schema 显式隔离）
LESSON=Program 拥有身份与 SHA；A 只决定创作语义及其待审来源；B 才能承认依据与合法 Hard；Model-only 返回可在 Schema 中表达独立依据，但不能创造另一份 Need 源身份。
NEXT_SINGLE_ACTION=在单独获准的真实 MiniMax 额度/成本范围下，仍使用原持久化 R02 EvalGateway+EvalProviderProxy 的全新合法 Attempt 做一次 A/B/Truth/Plan/Proof 真实复验，固定源码/运行 Fingerprint、原操作持久化、0 重试；不恢复失败的 R01。
TRANSITION=HOLD（root fix 已完成，真实 MiniMax 全链仍待独立新回执。通过后按用户要求噪音清理→基线冻结→回 U4）

### 8.25｜A-details SourceSelection 模型侧 Codec 闭环：R03 真实模型验收 Closure（2026-10-15）

**方案 C 已实施并由真实模型证明有效：**现有 `BatchedVisualClaimCarrier` 接受且验证唯一 `SourceSelection` frozen codec（而非自造 source map），每个视觉 Condition Claim 的 `creative_goal_ref` 只向模型暴露本模态合法 `src_*`，程序按冻结映射恢复 canonical `event-*/global`，保留独立 `Need.scope` 与创作依据，不更改原 raw；`BATCH_CLAIM_POLICY` @2→@3，批次 identity 包含 bridge、source_mapping/schema SHA；同一 `semantic_boundary_run.run/verify` 及 B Claim/Proof 消费原映射。用上一真实 R02 A-details 的 18 个原始 `src_*` 回执离线投影正反 PASS；相关定向软件测试 **20 PASS**。

**R03 持久化真实 MiniMax 一次性证据：**新运行在 `~/.local/share/easel/creator-task-evidence/2026-10-15-planning-m31-actual-owner-eval-r03`，原旧 R02 成功的 Gateway/Proxy 控制器，固定源码/运行指纹、8 HTTP 上界/0 重试。实际 3/3 HTTPS 完整响应、0 Pending、总 84,609 tokens，A-selection PASS、A-details-000 PASS（之前 `creative_goal_ref` enum 故障解除），A-details-001 FAIL：混合了视觉 slot_004–006 与 BGM slot_007，MiniMax 给 7 条 BGM Condition 都填了额外 `claim`，但实际请求 Schema 中该字段不存在且 `additionalProperties=false`。原 Owner 完整拒绝、无 B/Truth/Plan/Proof；旧真实原文 SHA/预算不可变，见唯一 E2E 账本最新节。

**下一工程问题独立于来源 Codec：**BGM/视觉混合批次出现模型字段串扰，不能静默去掉非视觉 `claim`、让 Provider/MiniMax 接管程序权限，或仅靠放宽 additionalProperties 做 PASS。需明确当前原 Owner 的 A-details 模态独立 Schema/Review 结构及失败时的一次原共享 Repair 准入，在新的设计被正式证实前不自动新建 R04。D0–D4 191 PASS 是更早源码的定向软件基线；本轮只做了 20 项必要回归，不称全项目绿。原主线 U4 仍 BLOCKED。

RESULT=PARTIAL（本轮 Source Codec 实装与 R03 真实模型复验完毕；Planning 真实全链尚未 PASS）
DRIFT=NO_DRIFT（保留原 B/Truth/Rights/Material Authority 与旧实际回执）
NEXT_SINGLE_ACTION=审计现有混合视觉/BGM A-details Batch 的模态隔离或原共享 Repair 边界，再在用户授权下使用新独立持久真实 MiniMax Eval 验收。
TRANSITION=HOLD（R03 预算关闭；不能从 A PASS 推断完整模型/成片 PASS）

### 8.26｜已批准 A-details 视觉/音频家族分批 · R04 真实 MiniMax 验收 Closure（2026-10-15）

**软件改动：**`StagedProposal.detail_batches` 增设仅 New-Only D1 选用的 `modality_family=True`，将视觉 image/video 和非视觉 bgm/sfx 分开每批最多4个原 `slot_###`；保留原 absolute Need 序号、完整 Slot cover、可逆组装及独立 `planning-modality-family-detail-batches@1` Policy。原其他调用不指定时仍按 `planning-fixed-detail-batches@1`。`semantic_boundary_run` 唯一 Owner 的 `run/verify` 依同一个冻结 `scope.creative_authority` 重建相同 batch plan、原 batch key/请求/Schema SHA、独立模态 Prompt，`BatchedVisualClaimCarrier` @4 带回原 Claim codec/Proof；既有非法BGM `claim`仍 fail-closed，不得默默清洗。原 R03 真 Need `[4视觉,3视觉,4音频]` 正确分组；定向 D1/D2/D4/原消费者冷恢复 **20 PASS**。

**真实 R04：**使用原先真正能调用 MiniMax 的 R02 Gateway/HTTPS Proxy 和用户明确许可的新持久化隔离 Eval `~/.local/share/easel/creator-task-evidence/2026-10-15-planning-m31-actual-owner-eval-r04`，当前代码与原 runner 277项指纹固定，M3.1 adaptive/medium, max8 HTTP/0重试，离线原网关预检通过。实际 2/2 远端 HTTP完整回复，A-selection PASS，A-details-000 原模型回复含4个视觉slot和各 Condition Claim，但顶层缺少 Tool Schema **必填 `unresolved`**，原 Owner在第一条 `required` 失败后即停止，无任何 B/Truth/Plan/真实音频批次证据。A-selection sha `b255694ebe622a92e53812a8b25e157b5e9a4b880ed1839aaa951345a85a1367`、A-details-000 sha `f71667a925366a9247d31c88227d6c27a54ca4cbfd512792f360066965db1dc6`。R04总 tokens 55,889，现金结算未知，HTTP Budget=closed/BATCH_FAILED，旧R01–R03均未恢复/重派。详见唯一E2E账本最顶部。

`RESULT=PARTIAL / MODALITY_FAMILY_SOFTWARE=PASS / REAL_PLANNING=NOT_PASS / TRANSITION=HOLD`。
**唯一下一动作：**应从R04原 Tool Schema和完整原始回执分析 `unresolved` 缺失为何发生（模型生成约束、请求容量/修剪、strict transport或上下文结构）。不得把它当作空数组自动填入或重启本次 R04，避免隐性删除未知报告。待用户授权安全修复与下一轮新独立真实 MiniMax 验收；U4继续 BLOCKED。

### 8.27｜P0-A/B/C 受控恢复软件专项正式 Closure 与 SHA 冻结（2026-10-15）

**范围与版本：**用户本轮明确授权将结构化 LLM 输出从「严格拒绝」推进到「受控恢复」的 P0-A/B/C 软件收尾并冻结，不授权 P0-D 真实 MiniMax。沿既有唯一 `semantic_boundary_run` Planning Owner、SourceSelection/Canonical/D1 Claim/D2 DecisionProof/Cold Verify，不新增 Goal/Task/Agent/实施分支/第二状态机。该次冻结为**23 个明确源码与离线测试文件的字节快照**，不是全仓库 Git Release；`easel-studio` HEAD `d82bb60b07240a3dd0d776ec00a33c68f71cab50`、其余 42 项 dirty/untracked 不归入本次验收资格。

**P0-A｜严格准入与定界：**`output_admission.classify_details_wire` 保留原字段、原错、Schema 身份和 raw SHA；只有当 A-details 根对象恰好缺 `unresolved`，其余所有 Slots/视觉 Claim/来源引用严格合法时才产生 `BOUNDED_REPAIR` 候选，非法 handle、额外音频 Claim、未知字段、越权/结构错继续拒绝。补答 Schema 仅允许模型显式提交 `unresolved`，去除 Wire 的 default 注解，但不在程序内生成 `[]`，不改写原回执。

**P0-B｜真正共享最多3次：**同一 Attempt 的 `repair_ledger/repair_count` 在每次外部 Repair 前先写入，`repair-000..002` 由 A-details 缺字段、后续 A/B 局部及 B 后语义修复共享；第4次拒绝，同 identity 重读不再次占额。Repair 的 `retry_failed=False` 与旧 Agent 原 Run ID 对账保留，UNKNOWN/未验证终态只能观察、不能新派发。用户承认最多3次是**总上限**，不是每阶段各3次；`MAX_PLANNING_CALLS=72` 为原技术范围，不是模型费用授权。

**P0-C｜双回执/冷恢复：**原 `PlanningCapture` 保存原 Stage raw、schema/request/reply SHA；模型补答由独立 `repair-NNN` Capture 保存，确定性只组合明确目标值，原 Slots/Claim 保持；`wire_admissions/wire_repairs/repair_ledger` 进入原 Checkpoint，`semantic_boundary_run.verify` 从原+补答重建并复验 D1 Claim、D2 Proof、冻结身份及失败拒绝。Journal/Checkpoint `@15`，旧 `@14` 不自动迁移或恢复旧 FAIL；历史 R01–R04 原始 HTTP、SHA、closed Budget 没有改动或重试。

**软件验收：**最终定向单版 `wc_job_NB1RcIUV85nITqQG`：**47 PASS / 0 FAIL（81.82 秒）**，涵盖真实 R04 raw 缺字段的只读分类/显式模型补答替身、三次额度/第四次拒绝、UNKNOWN 防重派、A 结构补答后 B 语义 Repair、D1/D2/D3/D4 与 Cold Verify。Python AST 与 `git diff --check` PASS。以上是确定性软件事实，**不是** R05 真 MiniMax、收费、Web E2E 或完整 Planning 模型语义 PASS。

**冻结原件：**`~/.local/share/easel/creator-task-evidence/2026-10-15-planning-abc-software-freeze-r01/`；只读 `manifest.json` SHA256 `4ea6df0db39df39e0fe5579602ce833024f02900d728e64ebb0e1a52575d237e`，**23/23 源码和测试文件**保留逐字节 SHA，主 Owner `semantic_boundary_run.py` SHA256 `4e58378940bb50d24c6e3a647b17b06f43f1a9e3d38c2380e4c411a3a929ca2e`；后续任何涵盖文件变化均须重新验收才能更新软件冻结身份。R04 历史模型 A-selection/A-details 两条回复仍为 FAIL，原预算 `BATCH_FAILED` 且 closed，不允许恢复。

`RESULT=COMPLETE（仅 P0-A/B/C 软件受控恢复与本次23文件冻结）`
`DRIFT=NO_DRIFT（单Owner/Claim/Proof/Material/Rights边界保持；历史模型 FAIL 不重判）`
`EVIDENCE=47 PASS，AST/diff PASS，manifest SHA 已固定；P0-D REAL_MODEL=NOT_EXECUTED；Git Release=NOT_CREATED`
`LESSON=不可靠结构化输出先保留原文和身份，只对白名单的可证明局部错误以共享预算请求模型显式补答，再冷重建；绝不能用程序默认值覆盖语义`
`NEXT_SINGLE_ACTION=需单独授权 P0-D：在旧成功 R02 持久化 EvalGateway/Proxy 上建立全新、独立封顶预算的真实 MiniMax M3.1 Attempt，验证显式 A-details 补答→B→Truth→Proof；首个非可恢复失败停，绝不重放 R01–R04`
`TRANSITION=HOLD（按用户要求本轮 Closure 后停止；不自动调用模型或进入 U4/U5）`

### 8.28｜P0-D 真实 M3.1 验收 R05：工具调用无参数首阻断 Closure（2026-10-15）

**前提已核实：**P0-A/B/C §8.27 的23文件源码SHA及固定 manifest `4ea6df0db39df39e0fe5579602ce833024f02900d728e64ebb0e1a52575d237e`，R05真实运行前后均23/23匹配。使用旧R02正式真实可用的 `EvalGateway/EvalProviderProxy` 与原Owner/Checkpoint等待器；新独立R05证据 `~/.local/share/easel/creator-task-evidence/2026-10-15-planning-m31-actual-owner-eval-r05/`，该运行 manifest SHA `ddbb91ac1c22713cf85a1f9200bd5ac65bb9e37ad5ac9fa3e136aa1939e82586`、全部286/286 SHA匹配，M3.1 Flash Preview adaptive/medium，max16真实HTTP、全Attempt max3Repair、0retry，旧R01-R04仍封存。预检无远端调用，唯一live 3次HTTP全200/HTTP SSE结束；总80,197tokens。

**实际第一失败：**A-selection tool arguments完整，SHA `daa18f51c080510a7000a49ab1de0a98bfee90044628325625a1b2c556369206`、PASS；A-details-000 tool arguments完整，SHA `f0ff796c17b1183b72486b9de201c8f95655f600fa52369f990f027f7d62448a`、4视觉 Slot及 `unresolved` PASS；**A-details-001 第三次远端HTTP返回状态200、SSE_DONE，却 `provider_finish=stop`、`tool_calls`参数0bytes，完成推理输出但没有生成被强制请求的 `submit_semantic_plan` 结构化工具调用**。原代理 `argument_stream_state=INCOMPLETE`、`observation_reasons=ARGUMENT_STREAM_MISSING/TOOL_FINISH_OTHER`，本地 `A-details-001` Capture `TRANSPORT_FAILED`，native run error/released/terminal receipt，整体预算 `ENTRY_CAPTURE_UNAVAILABLE` 关闭，`pending_original_run=false`。严格按首个非可恢复错误停止，不自动补字段、不重派旧操作、没有B/Truth/Proof，也未发生共享Repair（0/3）。因此**这一失败不能解释为 Schema shape 不合格，也不能声称P0-A/B/C模型Repair已真测通过**。

`RESULT=PARTIAL; DRIFT=NO_DRIFT; P0ABC_SOFTWARE=FROZEN_PASS_47; P0D_REAL_MODEL=FAIL_NO_TOOL_ARGS_AT_A_DETAILS_001; B_TRUTH_PROOF=NOT_REACHED; REPAIR_REAL=0_OF_3; TRANSITION=HOLD`。

**NEXT_SINGLE_ACTION=先只读复盘已冻结R05第三次 SSE/Tool Choice、OpenClaw M3.1 structured-result provider_finish=stop无工具参数的端到端终止语义与合法恢复边界，给出有证据的修正方案；任何继续真实模型/R06/部署另获用户授权，禁止重新派发R05或将 R05 HTTP 3/3 写成 Tool 3/3。**后续最终 U4仍BLOCKED。

### 8.29｜Planning Controlled Loop V1 · 实施方案（2026-10-15，唯一 Creator Task 内）

**唯一业务目标：**只针对新合法 Attempt 的 A-details 批次增加 Observe → Classify → Reserve → New Operation → Strict Validate → Continue/Stop 的受控整阶段恢复。解决 R05 的 stop + 0 tool_calls / STRUCTURED_TERMINAL_REJECTED 和 R06 的已完整 Tool Arguments 但纯粹 creative_goal_ref 来源引用不存在。程序不自动改错的来源、不扩 Schema、不发明 Creator/Director 授权，不新增 Planner/Agent/工作流引擎，Material V1.3、Hypit、Web 不改变。R01–R06 全部原件仅只读保全。

**版本与冻结：**P0-A/B/C 软件冻结的23文件 SHA manifest 4ea6df0db39df39e0fe5579602ce833024f02900d728e64ebb0e1a52575d237e 保留为历史验收，任何新码改动须给新的源码/软件资格指纹。新协议显式分离 Journal@16/Checkpoint@16 与旧 @15；旧 Attempt 不迁移、禁止恢复失败操作。

**分类决策（纯函数，不直接调用模型）：**
- ACCEPT：原 Tool Arguments 和本次严格 Schema、来源、Claim 已合法。
- FIELD_REPAIR：只延用原根级 unresolved 明确补答白名单，Slots本身严格合法。
- STAGE_REGENERATE：① 原业务/Runtime/Agent Operation 有时间戳与同一 Run/Session/Schema 的终结身份、native structured rejection 中 provider finish=stop、native stop=stop、toolCallCount=0，全部核验且 runtime_release=released、无 Pending/UNKNOWN；或 ② 原模型结果的 JSON Tool Arguments 与对应 raw SHA 完整，只存在一个或多个视觉 Condition claim.creative_goal_ref 的 enum 引用错误，且所有其余 Schema 和语义结构均合法。这两种问题重新生成的是完整 A-details 批次，不是字段Patch；原 Candidate 不能被当 ACCEPT。
- WAIT：原提交/结果/Runtime Release 不确定、原生拒绝证据缺失/身份不能核验、HTTP UNKNOWN、业务状态尚未稳定；只观察原 Run，绝不能创建新Operation。
- STOP：范围外结构错误（音频claim、越权、额外slot、无来源、错误Schema/Director/Attempt）、输出截断、强制安全错误、预算耗尽等。R06非法 src_7fa913d7de0bf1af55e 不存在于34个冻结来源 handle，程序不能自行替换来源，必须重新请模型选择。

**执行与额度：**仅在 semantic_boundary_run.run 当前 A-details 批内调度；共享 reserve_repair_slot 仍是全 Attempt 唯一上限3，FIELD/B/语义/STAGE_REGENERATE合计3；同批最多2次Regenerate。每次重生先保存新repair-NNN预占与唯一 session，再创建不同 Runtime Run ID；原失败的call/rejection/raw永不覆盖、不改写旧模型结果、不同请求不重派旧Run/同一身份。恢复候选使用原冻结A-details完整Schema、SourceSelection/Need位置、Director/Mode、Batch identity，严格重新验证，只有有效候选可以组装并去B。对下游B/DecisionProof不得沿用依赖旧候选的结果；V1只在还未进入B的A-details批触发。

**持久证据/冷恢复：**独立 stage_regenerations 包含原阶段、原失败的类型与Run/Session/Rejection SHA、每代repair键及request/schema/reply SHA、冻结来源和最终effective回复身份。原缺回执的stage可保留reply=None，其不可更改的 native terminal 独立存证；原有局部补答证据保留且不得伪装整段原回复。Checkpoint必须同时记录失败原文或缺失事实与所有恢复代的raw；verify()从原reply或缺失+native terminal、各恢复代、有效reply独立重算D1 Claim/B Directory/D2 Proof，任何篡改或失配拒绝。版本提升禁止从旧 @15 恢复执行。

**最小改动：**新增纯分类模块 planning_stage_recovery.py；修改 openclaw_delivery / planning_transcript 只读终态证据采集；修改 planning_capture 安全接收异常而不重派；在 semantic_boundary_run Owner接入恢复循环、现有Ledger/独立完整A-details projection/重建，修改 creative.verify_a_claim_origin 和 verify 冷恢复检查，必要扩展修复证据表但不改 Material Domain/业务Schema。现有 planning_candidate_review 的局部修复计数仍受Owner上限约束。

**验收义务：**离线端到端：R05 stop无工具参数且确证终结→独立新Operation→合法完整A-details→B/D2/coldPASS；R06只非法src→下一代合法；非法src合并其他错停止；缺Tool但UNKNOWN/Pending/未释放/证据不完整不能重发；同批两次及全局第四次停止；crash前后请求不重复、不同Operation身份、防旧A/B/Proof继承；原源码输入/Schema/请求/失败证据、所有Claim及raw SHA篡改拒绝；原FIELD_REPAIR/语义/B定向回归持续PASS。没有真实MiniMax付费、媒体/Build/Web E2E或部署、commit/push的本轮授权。结束须保留实施中失败并给出Task Closure和下一唯一动作。

**实施顺序：**（1）本§冻结方案；（2）分类与可核证 native 终态；（3）Owner共享额度和新完整Stage操作；（4）Journal/Checkpoint和verify的双端冷恢复；（5）小范围正反软件集成+冻结版本审计。若不能证明原Run终态或完整冷验证，只报PARTIAL/BLOCKED，不将例外伪装成既有@15通过。

### 8.30｜Planning Controlled Loop V1 软件 Closure（2026-10-15）

**软件实施完成：**按§8.29在唯一 `semantic_boundary_run` Owner接入 A-details 受控阶段重新生成及原生终态观察、现有RepairLedger、D1/D2冷恢复；Journal `semantic-planning-checkpoint@16` / Checkpoint `semantic-planning-frozen@16`。严格只有确认终结并释放的 `stop+0tool_calls` 或其他完全合格、唯独 `creative_goal_ref` 引用不在冻结列表时允许整批新Operation；绝不代选来源、对 UNKNOWN 重派、升级旧@15或重试R01–R06。全Attempt所有Repair共3次、同A-details批最多2次整批Regenerate。原成功 A 批不重做；D1/B/D2/Proof/Cold Verify均按真实有效回执身份重新建证，不继承旧失败。

**验收：**离线原生集成与回归 Job `wc_job_hZycbaWZ6t7qBxRC` **53 PASS / 0 FAIL（95.75秒）**；另用旧R05的真实封存OpenClaw原生Rejected Tool终态只读核对，Run/Session匹配，`finish=stop`、`toolCallCount=0`，拒绝原件SHA `0dfd228fe8150a9440121fbbb7d0ff2715028ca7eac0d5b56146016bacbf6c2a`。Python AST/Node语法、`git diff --check` PASS。无新的付费LLM请求。本次封存**12个指定源码/测试文件**于 `~/.local/share/easel/creator-task-evidence/2026-10-15-planning-controlled-loop-v1-software-r01/`，manifest SHA256 `1bd11137372204ee202ce84adb12aa228e6170dfd00426ef284cf0c740a1378c`，现有源码与快照12/12一致。它是软件冻结，不是全Git Release；分支 `easel-studio`、HEAD `d82bb60b`、未commit/push/部署。原23文件@15软件历史基线仍可追溯，但已变化的源码不可假称其旧SHA不变。

`RESULT=COMPLETE（Loop V1软件）; DRIFT=NO_DRIFT; EVIDENCE=53PASS+12/12SHA+R05_NATIVE_READONLY_PASS; REAL_MINIMAX_LOOP=NOT_YET_VERIFIED; TRANSITION=PROCEED_TO_NEW_AUTHORIZED_REAL_PLANNING_DEBUG_ONLY`

**NEXT_SINGLE_ACTION=依本轮新增用户授权，使用新的合法独立真实MiniMax Attempt、独立有界预算验证A→B→Truth→Proof；区分语义/Loop/代码缺陷，失败核实后只做有证据的定点修复，任何新轮独立落证；素材、Build、Web制作及部署仍不授权。**

### 8.31｜R07/R08 接管与当前版本核验（2026-10-15，持续调试中）

**Task Start：**唯一业务验收点是全新Attempt首次真实A→B→Truth→D2 Proof→正式冷加载通过；用户最新持续执行指令及补充授权为跨新增Attempt累计30 HTTP、仅现有M Plan套餐、不充值/不转现金。原Attempt/Budget不恢复，原Owner、业务合同、Material V1.3及Gate不变；素材/Build/Web/部署/Git/新Agent不授权。历史§8.30 NEXT由本轮持续调度消费，不能继承旧@16/53PASS的源码资格。

**实际失败与原始证据：**R07的B-003原raw SHA `75679b771a49d11118f5f1284f89826f55ad2eb2df7954fe632d709a5c43ff91`含answers与support嵌套item包装；四个实际B批的问题/答案ID均完整一致，不是已证实的缺题或聚合错误。B-001/002独立字段错误保留，未被根表示问题掩盖。R08的A-details-001非法creative_goal_ref是模型来源选择错误，原Owner正确使用一次共享Repair；repair-000无工具终态经正式原生读取确证，随后旧隔离设施停止，未完整验收Loop。

**已有修改核对：**R07后已有B lossless规范化接线，B身份@2、Journal/Checkpoint@17，新增b_normalizations冷验证；旧12文件manifest中9/12一致，3文件差异是semantic_boundary_run及两份对应测试。planning_wire也有配套变更（不在旧12文件中）。R08所有冻结文件与接管源码匹配。接管本身不再次修改生产源码或模型提示词。当前Loop/B身份/共享Repair/D2 Owner/RepairEvidence定向离线51PASS/0FAIL（47.35秒），git diff --check PASS；这是当前范围的软件证据，不是全仓库或真实全链成功。

**设施层最小修正及验证范围：**只在新独立证据目录复用原EvalGateway/ProviderProxy/PlanningEvalBoundary；隔离Adapter不判断模型语义，只有原Owner可占Repair、创建新Operation。完整SSE stop且零工具参数的HTTP保留为真实失败，不作为未知HTTP；下一次submit前必须再次核验同Run/Session/Schema的原生拒绝及释放，Owner账本Repair≤3、单批Regenerate≤2。UNKNOWN、截断、预算closed继续拒绝。共享task-http持久化上限30且占额不可清零；设施原有首错停止不再抢先截断合法Owner恢复。无外网回放使用明确标记的R07历史raw加一条合成stop，绝不用于真实run。

逐次运行、身份、Token/现金UNKNOWN与原件SHA只记[唯一E2E账本](../acceptance/easel-v1-web-real-e2e-2026-10-10.md)，接管原件位于`~/.local/share/easel/creator-task-evidence/2026-10-15-planning-takeover-audit-r01/`。本段为进行中记录，尚非最终Closure，不宣称真实Planning PASS。

### 8.32｜R09跨批Repair定义冲突最小修复（2026-10-15，软件完成、真实目标继续）

R09真实71题9批B回执全部取得，派发共享Repair前出现确定性`Conflicting patch definitions`。真实请求Schema9/9一致回放发现16局部目标的Support/Support_001同名定义在不同批次含义不同；修复仅对冲突目标局部定义及引用闭包加命名空间，保留原来源、角色、quote及拒绝条件。没有改模型回答、提示词、业务Contract、职责或架构，原失败Attempt不恢复。原件回放、16目标独立编译等价/RepairEvidenceProjection及跨目标引用拒绝通过，现有Owner/D2冷验证等联合52PASS/0FAIL（46.71秒），git diff --check PASS。生产源文件及专门测试快照见`2026-10-15-planning-takeover-audit-r01/source-after-definition-fix/`，完整运行/费用只见唯一E2E账本。

`RESULT=COMPLETE（仅此软件修复）; REAL_PLANNING=NOT_PASS; DRIFT=NO_DRIFT; EVIDENCE=R09真实9批回放/16目标等价/52PASS; LESSON=B批内局部Schema定义名不具有跨批全局身份; NEXT_SINGLE_ACTION=按现有30HTTP/套餐授权以新R10真实复验，消耗跨Attempt累计; TRANSITION=PROCEED（仅既有授权Planning范围）`。本轮整体任务不因软件Closure停止，R10正在执行，不宣称冻结版本、正式Web E2E或模型稳定。

### 8.33｜本轮最终Closure（2026-10-15，R11停止，覆盖§8.31/8.32进行中NEXT）

`RESULT=BLOCKED; DRIFT=NO_DRIFT; SOFTWARE_LOOP=PASS（当前52项定向离线）; REAL_PLANNING=NOT_PASS; TRANSITION=ESCALATE`。

**EVIDENCE：**R07/R08只读原件对账12HTTP/472226 tokens、无Pending；R09真实13HTTP到71题B，跨批同名定义冲突由真实9批/16目标回放证明并最小修复，逐题合同等价及专门跨目标拒绝测试通过，当前52PASS/0FAIL（46.71秒）。R10真实1HTTP在A-selection拒绝BGM视觉Header越界，未改合同。R11真实15HTTP，A-selection与所有A-details通过；一次真实no-tool由唯一Owner/shared Repair1/3/新Operation恢复，75题10批B原回执齐全，但13个B局部目标的Repair正文1,136,224字节超过1MiB，正式容量guard在预占/派发前拒绝。四批上下文重复完整candidate_bindings/evidence/source_catalog，离线精确逆还原现行共享候选引用后已复现，未做截断或修改模型原文。B正式NOT_PASS、Truth/D2 Proof/完整Checkpoint/正式Cold Verify/PLANNING_ACCEPTED均未到达，绝不宣称全链或模型稳定。

本轮累计29/30新增真实HTTP、1948000 tokens；R07/R08既有12HTTP另列，不重开旧预算。全部原生Run已released、原HTTP均RESPONSE_COMPLETE，Pending/HTTP UNKNOWN=NONE；只使用现有M Plan套餐、不充值/无现金fallback，真实现金结算UNKNOWN。R11源码指纹`2295814d932766e50aeeee0fcec19a676bef0d1f2b8e0a558e1b559c0c633a4b`，最终304/304冻结文件SHA核对一致。唯一流水与原件SHA、各Attempt身份见[E2E最终Closure](../acceptance/easel-v1-web-real-e2e-2026-10-10.md)，私有接管证据`2026-10-15-planning-takeover-audit-r01/final-audit.json`。源码修改仅限跨批局部定义冲突修复及一项边界测试；隔离执行设施只复用原Gateway/Proxy/Boundary调度现有Owner，无第二Planning主链、模型提示词或业务合同改动，无生产服务/媒体/Git操作。

**REMAINING_GAP：**Repair请求超1MiB的无损表示尚未修复或真实验收；完整Planning未通过。当前所有Attempt Budget已关闭，累计额度仅余1次，不足新完整Attempt，故停止新调用，不以无完成可能的A-selection耗尽最后1次。当前停止是预算不足与真实链路缺口并存，不把普通软件Closure当作完成。

**LESSON：**批内局部Schema定义名不具有跨批全局身份，合并须保留每题引用闭包和准入；精确回放必须逆还原已有presentation引用才可测量真正的Owner输入，HTTP结束不能替代字段/语义或Planning通过。

**NEXT_SINGLE_ACTION：**用户明确新的累计HTTP/既有套餐消耗边界，足以覆盖一条新完整Attempt；后续仍在本Task先对Repair上下文做严格可逆去重、真实原件等价回放与Owner/冷恢复回归，再用新合法Attempt真实复验。不得重开旧Budget、重派历史Operation、提高请求上限、删除来源/义务或进入Material/Build/Web/U4。**本轮到此停止。**

### 8.34｜新增60 HTTP授权续接与Repair完整上下文去重（2026-10-15，执行中）

**Task Start：**消费§8.33交接，唯一业务验收点仍为全新合法Attempt首次完整Planning与正式冷恢复通过。用户明确新增60 HTTP、仅现有M Plan套餐，授权修复Repair过大→离线验证→新Attempt真实调试直到通过或额度用完，不放宽合同。旧R09–R11的29次消耗和旧余1次关闭状态完整保留；新的共享账本仅启用本次60次，绑定旧账本SHA及29次已消耗，最多累计消费89次，不重开旧账本或旧Attempt。单Attempt24HTTP/2400秒、单HTTP300秒、Planning共享Repair3/单批Regenerate2继续有效，UNKNOWN禁止重派。禁止新Agent/新Goal/平行Task/生产链、媒体/Build/Web/部署/Git等边界不变。

**根因与最小修复：**R11的13目标Repair在真实派发前超过1MiB；四个批次重复完整candidate_bindings/evidence/source_catalog。扩展既有planning_request_view，仅将这些字段中完全相同的大值去重为完整context_catalog+显式引用；每份原文保留一次，不截断、不摘要、不替模型判断。project内部必须restore后与完整原payload相等，冻结original/projected/tool Schema三类SHA；篡改内容、互换引用、错误Schema/stage和还原不等价均拒绝。输出工具Schema、SourceSelection/来源准入、D1/D2、1MiB上限、共享Repair数量完全不变。新presentation `planning-input-context-dedup@2`、Journal/Checkpoint @18，旧@17仅保留，不迁移或续派。

**离线证据：**原R11十批实际请求Schema、75题原生回执SHA重建/逆还原既有Question候选引用，沿正式Decoder→13冻结局部目标→patch_schema→RepairEvidenceProjection→repair_message，正文从1136224降至892500字节，仍受原1MiB guard；完整恢复严格相等，Tool Schema未变。当前B/Repair/Loop/D2Owner/冷恢复及输入引用正反回归54PASS/0FAIL（46.96秒），git diff --check PASS。新的全局60次预算经24+24+12三Attempt离线封顶与UNKNOWN拒绝测试；真实新增HTTP0（预检时）。私有证据`~/.local/share/easel/creator-task-evidence/2026-10-15-planning-repair-context-dedup-r02/`保存replay-result/software-verification/source及新task-http账本，不是第二任务或Planner。

**下一动作已在授权内执行：**全新R12，独立身份/冻结输入/Runtime/配置/Schema和源文件指纹 `ec9c93cb60522973e0c3d82124a4876c29a9fadff7be9395ce2230cb50101559`，目录`2026-10-15-planning-m31-controlled-loop-live-r12/`。真实结果见唯一E2E账本，不把54PASS或局部回放当全链成功；发生普通失败按原授权分析/必要最小修复/离线验证后继续新Attempt，首个完整PASS即停。


### 2026-10-16 用户暂停停点（覆盖此前 NEXT）

用户明确要求“先暂停”，已停止离线测试，不再派发 HTTP/新 Attempt。新增授权已用 16/60 HTTP（R12=1、R13=15），全部 RESPONSE_COMPLETE，无 Pending/UNKNOWN；剩余44次保留，须用户恢复后才执行。旧29/30账本保持关闭。

R13 `fa_91f768503236ec8cc8260239f0ce2323`：A-selection/A-details通过（原 Owner Repair 1/3），10批B原件已收齐；汇总 Repair 请求1,172,075字节，超过未变的1 MiB上限，在派发前严格拒绝。Truth、D2 Proof、Cold Verify及PLANNING_ACCEPTED未通过。

当前未完成修改：request_view @3 将重复 evidence_choices_by_target 完整表纳入原有无损上下文引用，journal @19；R13真实原件离线回放847,290字节、R11回放697,779字节，恢复原文严格相等，Tool Schema未变。最新回归因用户暂停中断，36 PASS/1 FAIL；FAIL为测试期望4个目录项、实际3个（待核实测试数据是否达到512字符去重阈值），不得记为验证完成，不得将当前版本用于真实派发。此前@2版本54 PASS不代表@3验证完成。未修改合同或容量，不新建Agent，无Git/制作/部署动作。

RESULT=PARTIAL；DRIFT=NO_DRIFT；EVIDENCE=真实调用16次全部终态、Repair容量离线回放通过但最新回归未完成；LESSON=相同目标证据选项表也是大请求重复来源；NEXT_SINGLE_ACTION=用户恢复后先核实并修复定向回归，再完成离线验证，之后才允许新Attempt；TRANSITION=HOLD（解除条件：用户明确恢复且当前修改离线回归通过）。


### 8.35｜Repair 请求容量离线排查闭合（2026-10-16，真实仍暂停）

**范围：**按用户新指令只排查Repair汇总过大并修复失败测试，不执行真实模型。本节覆盖暂停时“回归未完成”的软件状态，不改变任何历史Attempt结果。

**完整根因链：**1 MiB 是 Easel checked_message/capture 对 UTF-8消息正文的本地上限（非已证实的MiniMax服务限制，也不是含Tool Schema的整个HTTP包）。B单批可运行，多个失败批次汇入一次已有共享Repair时重复复制上下文。R09局部Schema命名冲突已在此前修复；R11批次表重复导致1136224字节，@2只去重candidate_bindings/evidence/source_catalog后892500字节。R13目标增至22，@2仍1172075字节；22份证据选项表只有2种内容，另外逐题D2/候选/创作依据也重复。只处理批次表不足，未证明模型结构错误由长度引起。

**本轮最终修改：**沿用既有request_view，在@3中对完全相同且达到原512字符阈值的evidence_choices_by_target，以及逐题candidate_context/coverage_candidates/creative_dependency/d2_review整值建立完整context_catalog引用。每题/目标身份及字段位置保留；不同值不合并，单份/小值不替换；仅共享原文存储，不能共享或推定审查结论。restore校验原始全文SHA、目录/引用完整性与实际Tool Schema；目标换绑、证据篡改拒绝。Journal与Checkpoint统一@19（暂停时Checkpoint仍@18，本轮已校正），旧Attempt不续派。工具合同、48目标上限、共享Repair次数、1MiB容量不变。

**失败测试修复：**原证据选项fixture仅440字符，未达512阈值，错误期望新增目录项。扩充正例到阈值之上并显式断言，保留小对象不去重、不同目标选项不合并及换绑拒绝；未通过改阈值或放宽断言掩盖失败。

**离线证据：**禁止socket联网的R11/R13原件回放，从实际请求Schema/raw SHA→原Decoder→冻结目标→正式RepairEvidenceProjection→repair_message，最终分别209218/325946字节，完整恢复相等；原payload SHA及Tool Schema SHA与先前重建一致。相关Owner/阶段恢复/B身份/D2/RepairEvidence/输入投影回归55PASS（47.46秒）；最后追加真实capture超限前不创建call、不dispatch断言，定向3PASS（1.02秒）。48个不同问题身份共享大依据的表示压力场景可完整还原并过原容量检查；独有内容超过1MiB及多字节越界严格拒绝。git diff --check PASS。证据：`~/.local/share/easel/creator-task-evidence/2026-10-15-planning-repair-context-dedup-r02/offline-final-verification.json`及source-offline-final源码快照。

**边界：**本修复闭合已知R11/R13重复膨胀及测试失败，不保证任意独有内容均小于1MiB；无法无损压至上限的输入仍须拒绝，不能据此截断、拆分新增Repair权限或扩大容量。未验证新表示下真实模型语义/Repair成功率，Truth/D2/Cold/完整Planning未通过。新增HTTP=0；新账本16/60、余44保持，真实执行仍需用户解除暂停。

RESULT=COMPLETE（仅本轮离线排查与修复）；DRIFT=NO_DRIFT；EVIDENCE=两份真实原件无损回放+55PASS+最终3PASS；LESSON=Repair容量检查必须覆盖跨批表、逐目标选项与逐题完整上下文三层重复，字符去重阈值与字节容量不可混用；NEXT_SINGLE_ACTION=等待用户明确恢复真实调用后，按剩余授权用新Attempt验证；TRANSITION=HOLD（真实暂停）。


### 8.36｜模型输出合同错误原件离线归因（2026-10-16，真实仍暂停）

**唯一范围：**用户要求以原始失败回执区分提示词、Schema、程序转换；能修先修并验证，合同调整仅给依据，禁止恢复真实调用。

**原件核验：**R09–R13实际HTTP请求SHA、原生reply/参数流SHA逐一核对，实际发送的Schema通过Draft202012检查。R09/R11/R13共29批225题，经原Decoder与原领域校验得到16/13/22共51个局部Repair目标。原始Wire直接不合格答案分别9/11/18共38；另13个通过结构校验但违反原引用/领域约束。所有29批decoded答案与原始按question_id映射的answer逐字段完全一致，当前这批错误不是转换时丢字段/换来源。原失败不改成PASS。

| 原始问题 | 证据归因 | 处理/合同结论 |
|---|---|---|
| R10 BGM额外header_claim | 模型原文已有，实际Schema正确拒绝；提示只说“视觉header_claim”，缺少明确音频排除说明 | 明确只有image/video可填、bgm/sfx连null/空对象也不得填；不开放音频视觉声明 |
| R12 src_37、R13 A-details三处不存在的creative_goal_ref | 原始模型选择不在实际enum；提示已有冻结来源选择要求；转换未创造句柄 | 不推测替换、不缩短ID、不放宽enum；既有有界恢复保留 |
| B题型串字段、漏issue_code/owner/related_needs/required_kinds | 原始已错；Schema按题型正确闭合；提示全局混述题型，缺逐题字段摘要，属于可消除歧义，不能离线证明因果 | 自动从同一工具Schema生成answer_shape_by_question的allowed/required/type，按question_id绑定；不复制语义答案、不放宽字段 |
| related_needs/required_kinds出现item包装或空字符串 | 模型原始表示错误，Schema数组正确，当前Decoder原样保留 | 明确数组直接JSON数组、空数组[]；暂不增加自动归一化权限，混有缺失判断/其他错误不能据此自动接受 |
| support缺quote或role/source分支不匹配 | 原始已错；Schema正确要求source/role/quote及逐题资格 | 明确三字段不可省略；R09/R13 source-0003值确实是文本9:16，失败是当前题不允许output_authority，不能误归因非文本quote |
| 精确quote不存在、required_kinds与候选模态不一致、缺独立authority | 13题通过Wire但领域拒绝：R09引用1/模态6，R11独立依据2，R13引用3/独立依据1 | 是真实引用/语义约束，不能靠放宽Schema修复；必须获得新的真实判断 |
| stop+零工具参数 | 无安全候选，不能判断是字段Schema或解码错误，更不能填空对象；离线不能唯一归因模型/Provider原因 | 保留原生终态核验和既有受控恢复，不增加重试或预算 |

**实施与验证：**仅修改提示表达与从Schema机械派生的字段摘要；未修改输出Schema、领域校验、修复权限。Journal/Checkpoint @20确保新提示身份；旧Attempt不续派。52项B身份/阶段恢复/D2/RepairEvidence集成回归PASS（47.74秒），容量/投影3项PASS；29批真实原件重新生成提示，字段表逐题等于原实际工具Schema，Schema SHA保持，正文最大349702字节。原件转换与领域拒绝回放通过，网络被禁止；无新HTTP。私有证据`~/.local/share/easel/creator-task-evidence/2026-10-16-output-contract-offline/verification.json`、audit/replay及source快照。

**合同判断：暂不需要放宽。**现有错误均有原始事实支持拒绝，未找到“有效业务答案被不一致Schema/转换误拒绝”的新证据。纯表示包装可以另做语义等价实验，但不应借此默认补字段、改引用或接受错误授权。提示改善效果尚未真实验证，不能声称模型输出合同错误已消失；完整Planning仍NOT_PASS。

RESULT=COMPLETE（本轮离线归因/可确认修复）；DRIFT=NO_DRIFT；EVIDENCE=29批225题/51目标原件回放、38结构错误+13领域错误、52+3回归PASS；LESSON=逐题Schema形状应从实际合同派生，结构合法仍须独立来源/领域校验；NEXT_SINGLE_ACTION=等待用户决定是否恢复真实调用，届时仅新Attempt按剩余44HTTP及现有套餐验证；TRANSITION=HOLD（真实暂停）。


### 8.37｜恢复真实Planning（2026-10-16，进行中）

用户明确解除真实调用暂停，按剩余44HTTP/仅现有套餐在新Attempt验证§8.35–8.36修复，直到首个完整Planning/冷验证PASS或额度/安全边界。原task-http仍16/60起步，旧29/30账本封存；不放宽合同，不恢复R13。全新R14源指纹`1035c4c5546ca901ffb69a303c0111bdca4e997a6b5b867a434c18ddec2612e3`，Journal/Checkpoint@20。此前52+3离线证据不代替真实全链。


### 8.38｜恢复44HTTP最终Closure（2026-10-16，预算耗尽即停）

**授权与结果：**消费用户“剩余44HTTP、仅现有套餐、新Attempt到全链PASS或额度用完、不放宽合同”。本轮R14–R19共44/44，原新增60HTTP账本累计60/60关闭；旧29/30关闭账本及未用1次未重开，R07/R08原12另列。首次完整Planning未通过，不能报成功或稳定。

| Attempt | HTTP | Repair | 首个实际终止原因 |
|---|---:|---:|---|
| R14 fa_8c691526c999185477ed4b55f2cd7dfc | 14 | 1/3 | A及9批B回执取得，5目标Repair真实派发/返回（171450字节）；D2对原模型source_or_truth_violation分类拒绝，两份报告实际描述资产许可待核验；原FAIL保留 |
| R15 fa_b8ec714ca5f28c158c46db6e3d0fd87c | 1 | 0/3 | A-selection多个Header创作依据写不存在的src_75 |
| R16 fa_90884d5795937301328d825527f20c38 | 2 | 0/3 | A-details来源ID拼错且缺根unresolved，不符合只错来源的恢复准入 |
| R17 fa_a5ff6f28b38fddb8b08f74728d25dda6 | 13 | 0/3 | A通过，B-008完整SSE stop/零工具参数，无安全候选；B没有A-details同类整批重生成授权，终态释放后停止 |
| R18 fa_3ca454a7a139494446ef8b86c3018415 | 7 | 3/3 | 连续4次no-tool，A000两次Regenerate/A001一次成功恢复；A002再no-tool时共享Repair耗尽，严格停止 |
| R19 fa_d5d436414fac955e1eb88d339d21b26a | 7 | 0/3 | A通过，B000–002取得；预算60/60后下一B操作被本地额度guard拒绝，无额外远端HTTP，原生error/released，无Pending |

**唯一新增软件澄清：**按既有方案§2.2/当前D2边界，提示明确区分“资产来源/许可证据待下游核验”与“Creator用途/人物授权缺失”。前者仅在合法候选已完整承接义务时可判material_supply_pending，报告保留，Rights UNKNOWN继续阻断实际使用；后者/新增创作决定/真实授权冲突仍必须阻断。未改任何输出Schema、领域校验、来源枚举、Repair权限或额度，不自动把模型CHALLENGE转ACCEPT。Journal/Checkpoint@21，75项原Owner/D2/Proof/Repair/身份回归PASS（48.07秒）。不是同根因两次失败后的架构重构；未创建新Agent。

**实际验证范围：**容量修复首次取得真实Repair派发与完整回传；该次5个局部结构错误通过原严格Repair进入D2检查，但语义类别仍阻断。此前离线容量/逐题Schema提示证据仍有效，不据一次结果认定稳定。R15–R19同@21逻辑版本，源码指纹因独立运行目录脚本路径不同分别冻结；全部manifest原件、HTTP请求SHA、参数流SHA/native raw与终态逐项核验。R14变更前两个源码SHA由已封存output-contract-offline/source快照还原核对；各次final-audit均核对312项冻结文件，不假称旧源码与当前相同。

**账本与费用：**恢复44次全部RESPONSE_COMPLETE/SSE_DONE，5次stop零工具保留为真实失败（不冒充安全模型结果）；全部原生操作released，无Pending/HTTP UNKNOWN。恢复期tokens=2442667（prompt2299198/completion143469）；新增60次tokens=3542834（prompt3340809/completion202025）。与前闭合29次合计89HTTP，若另计R07/R08原12则101HTTP。只用现有M Plan、不充值/无现金fallback；现金结算UNKNOWN，不能记0元。私有证据`2026-10-15-planning-repair-context-dedup-r02/final-resumed-audit.json`及R14–R19各final-audit，已关闭共享task-http账本；最新指纹`a9de5296ec905348712902b64ba1664b8bc7269a8fd392315f5b95d65597a205`。

RESULT=STOPPED；DRIFT=NO_DRIFT；SOFTWARE_LOOP=局部回归PASS（75），不是完整产品PASS；REAL_PLANNING=NOT_PASS；LATEST_A_SELECTION=PASS；LATEST_A_DETAILS=PASS；B_REVIEW=NOT_PASS；TRUTH/D2_PROOF/COLD_VERIFY=NOT_REACHED；PLANNING_ACCEPTED=NO。
EVIDENCE=44/44恢复调用全部终态/Released、真实Repair容量阻塞解除、语义及no-tool错误仍留原件；LESSON=无损输入去重解决容量，不自动解决安全候选产出与独立语义分类；NEXT_SINGLE_ACTION=停止真实调用，建议仅离线复盘本轮5次stop/零工具原始SSE与native工具请求/终态，任何后续实调先获新预算授权；TRANSITION=HOLD（预算已耗尽，不继续任何真实操作）。


### 8.39｜设计根因复核（2026-10-16，仅离线/只读运行证据）

用户要求核查持续失败是否来自设计。本轮没有真实模型调用、没有生产源码修改或合同调整。结论：已证明存在请求组装与上下文隔离缺陷，恢复/执行策略也放大了局部失败；尚不能把所有错误归结为一种模型原因或断言整个产品架构应推翻。

| 层次 | 已核查事实 | 判断及边界 |
|---|---|---|
| Repair输入组装 | R11/R13原正文1136224/1172075字节；完整可逆去重后209218/325946；R14真实Repair171450字节成功回传 | 重复上下文和跨批局部Schema命名冲突属于程序组装缺陷，不是业务合同过严。1MiB为本地message guard，不应误称MiniMax服务端上限。容量修复已验证，不能推导语义稳定 |
| 模型上下文隔离 | R18实际HTTP system约20081字节，带OpenClaw通用AGENTS/SOUL/IDENTITY/USER/BOOTSTRAP；包含首次询问称呼、人格初始化、群聊反应、工具和环境说明 | 专用Planning请求混入通用Agent职责是确定的隔离问题；是否造成零工具尚无对照证据，不能直接定因 |
| Wire/Schema负担 | 原29批225题中38原始结构错误、13领域错误，Decoder前后答案相同；R17 B实际tools序列化约59–63KB，user约127–333KB | 不是统一的程序转换丢字段。动态异构题型、来源/角色/引用/关联候选同时生成，形成较重交接负担；格式、引用和语义须分别测量，不能只加提示词或放宽校验 |
| Provider工具边界 | 已检实际请求指定submit_semantic_plan且parallel_tool_calls=false；5次完整stop零参数发生于R17一个B与R18四个A/Repair，completion2342–6104，低于8192上限；A输入约52–53KB | 不能统一解释为输入过长或输出耗尽。官方OpenAI兼容页确认adaptive/medium/max_completion_tokens用法；未由该页证明强制工具选择与strict约束生成保证。实际请求未带strict不能独立判成bug；Provider与适配器能力仍须最小实验区分 |
| 语义分类 | R14 B将资产许可待核验判成source_or_truth_violation，现行semantic_targets据此拒绝；已有规则区分供应待核验与Creator权限缺失 | 提示语义边界曾不清，已补澄清但未完整实证。安全拒绝应保留；不能把所有CHALLENGE当格式错误自动改成ACCEPT，连续性等独立质疑仍须判断 |
| 恢复和执行策略 | R17晚期B零工具即结束；R18 A阶段消耗完3次共享Repair；R19只有7HTTP余量仍发起新全链，最终预算耗尽 | 局部失败可令较长链全部失效；恢复预算混合传输候选与语义修复，阶段恢复不对称，需要设计审查。R19是预算终止而非模型错误；启动前未确保全链可行是执行策略问题。用户授权耗尽不代表必须消费明显不足的残余预算 |

官方契约核对：https://platform.minimax.io/docs/api-reference/text-openai-api 。本轮没有使用第三方博客推断支持能力。证据来自既有R14/R17/R18 requests与http-ledger、§8.36原件回放、§8.38最终审计；不更改历史回执或FAIL。

**最小后续顺序：**先在原Task完成专用Planning请求上下文隔离与Provider工具边界的离线设计/原件验证方案，明确程序身份绑定、完整依赖闭包与原业务合同等价；再评审分阶段恢复和预算准入。跨模块职责/恢复权限改变须按现行关键复核规则实施，不能借此次核查自动扩权。真实对照必须另获预算；优先验证单一边界，再有充足预算验证全链，停止用新完整Attempt充当所有局部问题的诊断工具。

RESULT=COMPLETE（限本轮根因核查，非修复/Planning完成）；DRIFT=NO_DRIFT；EVIDENCE=原请求上下文/Schema与终态核查+既有失败回放；LESSON=安全合同与模型交接设计须分开，拒绝正确不代表流程可用；NEXT_SINGLE_ACTION=仅离线准备专用Planning上下文隔离及工具边界最小验证方案；TRANSITION=HOLD（真实额度0，设计变更未实施）。


### 8.40｜Planning 专用输入隔离与恢复协议离线修复（2026-10-16）

**唯一验收点与边界：**按用户要求离线移除无关上下文、核查工具协议、理清局部恢复/预算准入，并评估合同简化；不增加语义提示词、不放宽业务合同、不执行真实模型。消费§8.39离线NEXT，不重开历史预算/Attempt，不安装生产Runtime、不重启服务、不进入素材/Build/Web/Git操作。

**已修复并验证：**

1. 原始输入隔离：实际R14/R17/R18共34份HTTP请求逐一核对，system均20081字节，user含29字节时间前缀及491–499字节运行尾注。离线仅以原Capture SHA验证完整原文位置，不在生产截取/猜测文本。新协议`easel-structured-result@2 / planning-original-input-only@1`在Python入口绑定原始message SHA；principal直接传原message给builtin，Native只构造单user原文、空system和唯一工具。onPayload及最终HTTP reservation均验原文SHA和唯一消息，重加system、改文、历史/图片块注入均拒绝。无新增语义提示说明，完整来源及实际工具Schema保持。
2. 身份与历史：contextPolicy/inputSha绑定session、reservation、candidate与拒绝证据；读取器与Delivery消费端核验输入身份。Journal/Checkpoint@22；v1与v2分别固定11/12项Runtime依赖。旧v1可读、不可由新版继续派发。真实安装仍v1，未加载v2时新派发会因pin不符拒绝；不是已部署生效。
3. 恢复协议版本：当前helper写`easel-structured-rejection@2`，原reader只认@1，已按所选冻结协议分别核验，v2还验固定storage分类与输入SHA；不接受任意版本。
4. 错误码保真：SDK清理不得抹掉本stream首个已验证固定拒绝码；拒绝后不能由后续done转PASS，取消仍aborted，未知执行错误仍generic，不持久化异常原文。
5. 框架隐式重派：真实内部离线集成发现`handleEmbeddedAssistantFailure`会在零工具错误后同Run内部重做3次。HTTP guard虽阻止额外HTTP，后续失败却覆盖最后transcript。新增该Runtime文件的固定pin，仅结构化请求在此分支交回Owner处理，保留原拒绝。原生零工具现为一次attempt/一次本地fixture HTTP，最终transcript和v2 rejection一致，现有A-details恢复资格可读取。普通Agent/Truth回归通过。此修复仅覆盖已定位assistant-failure分支，其他框架恢复仍由最终HTTP防重兜底，不宣称所有框架恢复分支已关闭。

**前置及收口复核：**按AGENTS使用只读Astra；其先要求原RPC输入绑定/最终fetch重验/历史pins分离，后发现拒绝记录版本不匹配，并复核固定拒绝码与assistant-failure最小修正。所有实现由Main完成；未将审查意见当成实调或安装授权。

**当前局部恢复设计（未增加权限）：**

| 失败层 | 当前行为与最小恢复原则 |
|---|---|
| Pending/UNKNOWN、身份/终态不确定 | 只对账原Operation，不创建新请求；HTTP结束不能替代Native安全候选 |
| 完整stop且零工具 | 原生终态、原拒绝、输入/Schema身份及released全符合才有恢复资格；当前仍只给已批准A-details，新Operation从冻结原输入重新判断，消耗原共享Repair；B/Selection不自动扩入 |
| 可证明等价表示错误 | 仅现有明确allowlist无损转换，保留原回执，转换后通过原Schema/领域校验；不做任意字段清洗 |
| 缺字段、错来源、混合Schema错误 | 不补答案、不改ID；已有合法局部补答/Repair才可取得新模型判断；R16混合错误仍不因本轮改动获整批再生成资格 |
| 语义CHALLENGE/UNRESOLVED | 只由原Owner修允许目标并复核受影响义务；Creator/Truth/授权缺口仍停止，不能自动改ACCEPT |

共享Repair仍3次、单A-details整批再生成仍2次；没有新增独立恢复配额或放宽预算。扩大B无候选恢复需要版本化原/新回执、有效答案绑定、Proof冷重放与严格否例，当前只明确设计，尚未实施。

**预算准入：已实现只读预检，最终共享派发接线未完成。**既有`EvalHttpBudget.completion_preflight`接收Owner冻结阶段工作量和Planning/Truth Repair预留，比较本Attempt及跨Attempt共享余额，关闭/截止/UNKNOWN/未冻结工作量/不足均HOLD；不改账本、不预约、不授权。7余量对14确定工作+4预留的例子离线拒绝，不能把这组fixture数字冒称每个Planning固定成本。B工作量未知时返回UNFROZEN_WORK，不能套历史平均13次。

后续最终调度须：在新Attempt前及各阶段冻结实际批次后重算剩余完整工作上界（含受影响B复核、Truth及已授权修复预留）；未冻结项显式保留未知。共享Owner需在最终派发/占额同锁核对冻结计划SHA、原预算余额、时间与未对账操作。阶段预检不能替代最终原子预约；不能因为余额还有7就启动已知无法完成的全链。现有共享任务账本及R14–R19控制器均已封存，本轮未改写或伪造新准入资格，因此R19型调度风险尚不能报已解除。

**工具官方契约核对：**MiniMax官方OpenAI接口和Tool Use文档支持tools、function.arguments及当前adaptive/medium/max_completion_tokens；多轮工具会话需完整回传assistant及reasoning，但本通道每次是独立阶段操作，并非删改同一工具会话历史。文档未给出所用端点强制tool_choice/strict约束生成必然成功的保证，不能把缺strict直接判为bug，也不能把HTTP/SSE完成视为工具结果。原Schema、指定submit_semantic_plan、parallel=false和严格终态检查保留；零工具继续拒绝。来源：https://platform.minimax.io/docs/api-reference/text-chat-openai 与 https://platform.minimax.io/docs/guides/text-m3-function-call 。

**合同可简化/可放宽评估（本轮未变更正式业务合同）：**

| 项目 | 结论与依据 |
|---|---|
| null/value等Wire包装 | 可研究新Wire直接JSON null/value；已有B quote原生标量先例。须双向等价、严格原Schema、版本隔离与字符串null拒绝，不是默补缺失字段 |
| 重复source+role与程序身份 | 可评估推广现有Repair evidence_ref式冻结组合绑定，减去可确定恢复的冗余；模型仍选择真实证据并判断支持关系，不能由程序替选来源 |
| 答案顺序、固定item包装 | 仅身份唯一完整后无损处理；现有B已按ID映射及有限allowlist处理，不能再把缺/重/多余ID归为可忽略顺序 |
| 不适用空字段 | 不一般化放宽；空字符串/null/[]/未回答并非天然等价。最多逐字段证明语义等价后做新投影；必需判断与显式unresolved不能自动补 |
| Need/问题数、引用长度、请求容量 | 属工程边界可重审，但当前失败不证明应提高；需完整容量/预算/来源义务回归，不能先增上限掩盖重复组装问题 |
| 问题覆盖、原来源引用、引用真实支持、Creator/Director/Truth/Rights | 当前证据不支持放宽。Planning阶段实际资产许可待供应已可pending；Creator权限缺失与来源不真实仍必须拦截 |

**验证证据：**原75项Owner/身份/受控恢复/D2/Repair回归加3项协议/预算测试共78 PASS；最终扩展Native/capture集成29 PASS及一项fixture缺agent_id修正后单测PASS，合计本组30项全部闭合。包含当前Owner A→B→Repair→B-recheck→Proof/冷验证与同Attempt恢复不重派，原始R18输入/实际Schema/回执在真实SDK本地Provider出口重放PASS，实际v1原件只读读取且数据库SHA不变，零工具原生回执及7种证据篡改拒绝，普通Truth及SDK异常路径。Python/Node语法和diff检查PASS。全部离线，本地fixture HTTP不计真实HTTP；模型可靠性未验证。

扩展历史检查保留3项不相容失败：旧diagnostic指令替换实验（当前view_a_message与@21 AST相同）、Proposal@3 fixture被当前@4拒绝、旧authority_runtime的Production Brief未绑定原件。未放宽合同或顺手迁移旧实验，不宣称全仓测试PASS。原件/源码SHA/测试记录：`~/.local/share/easel/creator-task-evidence/2026-10-16-planning-context-protocol-offline/`。共享60/60与旧29/30封存账本SHA均不变，新增真实HTTP=0。

RESULT=PARTIAL（输入隔离及已定位协议缺陷离线修复完成；预算最终接线/B恢复扩展未实施）；DRIFT=NO_DRIFT；EVIDENCE=78定向PASS+本组30项闭合+原件SDK重放/旧v1冷读，生产未加载/真实Planning仍NOT_PASS；LESSON=专用阶段必须绑定原RPC语义输入且阻断框架隐式重派，最终拒绝证据须端到端保真；NEXT_SINGLE_ACTION=仅离线将冻结剩余工作量的准入接入现有共享预算Owner最终占额处，先完成原子性/UNKNOWN/恢复身份设计，不重开封存账本；TRANSITION=HOLD（真实额度0，最终预算门槛尚未落地）。

### 8.40 后续｜预算 Owner 定位（2026-10-16）

按当前用户要求收窄为实际缺陷。只读核实：跨 Attempt 的 60 HTTP 共享占额 Owner 位于历史私有证据 `2026-10-15-planning-repair-context-dedup-r02/control.py`，`task_ledger()` 锁定 `task-http.lock`，`Budget.reserve()` 先登记共享 UNKNOWN，再调用仓库 `EvalHttpBudget.reserve()`。仓库 `completion_preflight()` 仅提供只读诊断，未被历史控制器用于派发；其共享账本快照和最终占额不在同一锁域。不能仅改预检就宣称已消除 R19 调度竞态。该控制器和账本均封存，本轮不修改、不复制重开。

**实际剩余问题：**未来获准的非历史 Attempt 调度需直接在现有共享 Owner 最终锁内做最小余额、截止、未结操作检查，与 reservation 身份绑定；开始完整 Attempt 前根据当前已知阶段估算余量，B 动态批次按阶段更新，不把估算误写为完成保证。不新增预算规划引擎/Gate，不扩展 B 恢复或调整正式 Wire Schema。此前输入隔离/协议修复沿用现有离线证据，不重复实施。本轮没有声称预算修复已接到生产；真实 Planning 仍 NOT_PASS。

