> 冻结设计：2026-10-07，来自本 Task 前序完整设计与一次 Astra 只读复核。
>
> PLANNING_VNEXT_DESIGN = PASS；CURRENT_R4 = PAUSED；HISTORICAL_R4_RESULT = FAIL；ASTRA = CONTINUE；READY_FOR_IMPLEMENTATION = YES。
>
> 设计 PASS ≠ 软件实现完成 ≠ Development Eval PASS ≠ Formal R4 PASS。
> 下文完整保留设计当时的范围、停止条件和授权状态；其中“本轮不实施／未授权真实执行”是设计阶段的历史状态。
> 后续连续实施按用户 2026-10-07 授权执行 S1–S5 与有界 Development Eval，正式 R4、Supply、媒体生成、TTS、Build 禁止。

# Planning Semantic Boundary vNext 设计报告

## 1. 结论与适用范围

```ini
PLANNING_VNEXT_DESIGN = PASS
CURRENT_R4 = PAUSED
HISTORICAL_R4_RESULT = FAIL
ASTRA = CONTINUE
READY_FOR_IMPLEMENTATION = YES
```

这里的 PASS 表示设计完成并通过架构复核；`READY_FOR_IMPLEMENTATION` 仅表示具备进入后续获批软件实施的设计条件，不代表软件已经实现、模型可靠性已证明或真实评测已获准启动。

本版优先收敛：

```text
SemanticPlanningDraft / MaterialNeed
→ Classification Input
→ Formal Contract Projection
```

目标是建立以下责任链：

```text
冻结事实只有一个权威
→ A 提出真正需要语义判断的创意候选
→ B 复核候选与冻结要求的关系
→ 程序生成唯一正式合同
```

主要闭合视觉语义复核及合同投影边界。Voice、BGM、SFX 纳入事实和投影设计，但保留现有音频执行路径及未验证范围；不把本版视觉治理扩大为全部声音语义已闭合。

## 2. 设计依据

固定调查版本：

```ini
COMMIT = 3be0ff946c29c8871a8f34de015c8b3944316ac7
PRODUCTION_SOURCE_SHA = bf527ce1b565409817a5c21e0dc8029e6ca3ad73681bd619493fc4bd17be9caf
PLANNING_CONTRACT_CLOSURE = FAIL
REAL_BATCHES = 10
REAL_SAMPLE_EXECUTIONS = 12
HELD_OUT_EXECUTED = 0
CURRENT_R4_READY = NO
```

关键行为依据：

- [Semantic Planning](/Users/xgx/Projects/Easel/easel/integrations/semantic_planning.py:93)：A 仍输出混合 `constraints`，B 分类后生成正式合同。
- [来源资格与 controls](/Users/xgx/Projects/Easel/easel/integrations/planning_authority.py:175)：程序生成路径和值，模型仍需协调其依据关系。
- [视觉合同](/Users/xgx/Projects/Easel/easel/materials/application/visual_contract.py:247)：分类结果最终形成 required、preference、postproduction、unresolved 条款。
- [结果捕获](/Users/xgx/Projects/Easel/easel/integrations/openclaw_delivery.py:74)：现有捕获检查终态、截断及 3,000 个 UTF-16 单元容量。
- [正式持久化](/Users/xgx/Projects/Easel/easel/integrations/material_layer.py:271)：已有身份、冻结输入、Requirements、Truth 与恢复校验。
- [batch10 原结论](/Users/xgx/Projects/Easel/docs/acceptance/fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch10-actual-run-summary.json)：B 初始资格拒绝，repair 截断，正式产物未形成。

现有 135 项矩阵与 873 项常规测试证明了具名软件行为，不能证明真实模型可靠性。历史 FAIL 保持。

## 3. Canonical Fact Model

### 3.1 定义

这是 Planning 应用层的事实与投影约定，不新增产品实体、通用语义本体或第二套 Truth 账本。

一个事实必须明确：

```text
它约束哪个对象
→ 属于哪个 scope
→ 表达什么含义
→ 有多强
→ 由谁负责该含义
→ 当前值及真实出处
```

ID、path、offset、hash 和投影关系由程序维护。

相同字符串不代表相同事实。例如：

```text
成片比例 9:16
源素材原生比例 9:16

成片时长 15 秒
静图展示 15 秒
源视频最少 15 秒
```

这些必须分别处理。

### 3.2 事实表

| Fact | Canonical Authority | Canonical Value | Provenance | Program-derived projections | Needs LLM? |
|---|---|---|---|---|---|
| 成片比例 | 已确认规格 | 例如 `9:16` | 冻结规格原字段 | 输出上下文、相关技术参数 | 否 |
| 源素材比例 | 明确源要求；否则 Planning 候选 | 原生比例要求或不限制 | 源要求原文／经复核候选 | `modality_spec.aspect_ratio` 等必要表示 | 仅判断是否需要约束源素材 |
| 源素材模态 | 明确源要求；否则 Planning 候选 | image/video/voice/bgm/sfx | 冻结场景／经复核候选 | `media_type`、模态结构 | 真正存在表达选择时需要 |
| 成片声音模式 | 已确认声音方案 | silent、narration 等 | 冻结声音方案 | 现有声音规划条件 | 不重新解释已明确值 |
| 成片总时长 | 已确认规格 | 总时长 | 冻结规格 | 成片上下文 | 否 |
| 展示／使用时长 | 冻结场景或 Planning 表达候选 | 某素材如何使用 | 场景原文／候选用途 | 用途证据、现有表达上下文 | 未明确时需要 |
| 源素材时长 | 明确源动作或素材条件 | 源视频／音频长度要求 | 对应源条件 | 合法 `duration_hint`／检索条件 | 不能从总片长自动推出 |
| Mode 风格 | 冻结 Creative Mode | 风格及既定强度 | 实际 Mode 原件 | 现有软风格表示 | 不重新定义其强度 |
| 本作品资产风格 | Planning 候选或明确 Creator 要求 | 一份风格意图 | 原要求／经复核候选 | 软提示或 required 条款 | 需要判断具体化及必要性 |
| Narration 内容 | 冻结且经过 Truth 的 SCRIPT | 原文字节 | SCRIPT 原件 | Voice `text_ref`／SHA | 不允许重新写正文 |
| Voice 身份／音色 | 合法冻结身份与选择范围 | 已有合法选项 | Creator／Director／授权原件 | 身份、引用、Consent 绑定 | 可选择表达方式，不能创造身份或同意 |
| Voice 表达 | Mode 与 Planning 候选 | 语气、速度等意图 | Mode／声音意图 | 已支持的 delivery 参数 | 语义选择需要 |
| BGM | 冻结声音方案与 Planning 候选 | 情绪、乐器、能量、人声要求 | 声音原件／候选 | BGM typed fields、查询提示 | 创作判断需要 |
| SFX | 冻结事件与 Planning 候选 | 声事件及声音特征 | 场景／事件原文 | SFX typed fields | 未明确的表达需要 |
| 字幕／叠字 | 冻结 SCRIPT、SCENES、TREATMENT | 后期文字义务 | 原件 | 现有后期证据 | 不制造背景素材采购需求 |
| 源素材无字／有字 | 明确源条件或候选 | 原素材可观察属性 | 对应原文／经复核候选 | 正式素材条款 | 与字幕义务分别判断 |
| 动态动作 | 冻结动作或 Planning 候选 | 源视频真实发生的动作 | 场景／候选 | 源动作条款、必要模态 | 不能用后期效果替代 |
| Need 必要性 | 显式冻结要求或 Planning 候选 | required/optional | 上游要求／经复核候选 | `Need.importance` | 未明确时需要 |
| 素材条件强度 | 对应原要求或候选 | 必需条件／偏好 | 该条件出处 | required/preference 条款 | 有歧义时需要 |
| 后期／叙事责任 | 冻结表达及 Planning 候选 | 编辑义务／作者义务 | SCENES、TREATMENT、Truth 等 | 既有后期条款和检查点证据 | 归属有歧义时需要 |
| Creator 明确要求 | Creator 确认原件 | 原要求 | 精确原件绑定 | 相关事实与义务投影 | 只能解释含义，不能改写权威 |
| Creative Mode 约束 | 冻结 Mode | 既定表达边界及强度 | Mode 原件 | 适用范围、默认投影 | 具体应用可能需要 |
| Preparation 派生产物 | 已有来源及实际派生过程 | 派生上下文 | 原输入与派生记录 | Planning 上下文 | 不升级为 Creator 新要求 |

### 3.3 `9:16`、`image`、`style` 的关闭方式

**`9:16`**

A 不再同时维护 `constraints.aspect_ratio` 与 `modality_spec.aspect_ratio`。已确认成片比例直接读取；源素材是否必须原生竖幅另行判断。只有该判断成立，程序才生成相应源比例字段。

**`image`**

A 最多提出一次真实模态选择。程序派生 `media_type`。`silent` 只说明声音模式，不能证明素材必须是 image。

**`style`**

一份风格意图拥有一个值和一个强度。必要的兼容表示由程序生成。Mode 软风格不能因为进入另一路径就变成 hard。

显式硬风格要求通过 required 素材条款承接；现有软风格字段不能代替其必要性。

## 4. A Responsibility Contract

### A MUST output

- 实际素材目标与创作意图。
- 素材承担的叙事角色。
- scope 的语义选择。
- 真正存在选择空间的素材模态。
- Need 必要性候选。
- 完整素材条件，以及其必要性／偏好候选。
- 素材条件与用途、后期、叙事责任的分别表达。
- 无法确定的语义问题。

已经明确冻结的事实通过程序提供的受控引用承接，A 不再重复填写其技术值。

### A MAY output

- 检索短语的语义候选。
- 审美、构图和声音表达意图。
- 从真实候选中选择的连续性目标。
- 服务既定表达目标的合法创意具体化，例如新物件或新的素材实现选择。

这些都是 Planning 候选，不自动成为 Creator 新要求。

### A MUST NOT output

- 同一事实的技术别名。
- Need ID、正式 source ID、path、offset、hash。
- revision、cache identity、sidecar 和 manifest 字段。
- 实际程序 operation 关系。
- 正式文件路径、文件写入任务。
- 预算、授权、Rights 结论或状态推进。
- 由模型任意定义的执行策略。

### 是否保留自由 `constraints`？

**新 A 草稿不直接输出当前这种混合自由字典。**

原因是其中同时混有语义要求、检索控制、软偏好、模态重复值和执行参数，消费者又可能将未知标量直接当作 filter。

替代设计为有限的语义承载：

```text
素材条件
用途／责任
偏好
真实模态选择
查询语义
声音表达
```

素材条件可以包含自然语言，但不能通过任意 key 自动获得执行控制权。程序只把已定义、经过必要复核的含义映射到正式字段；未知含义保留为未决，不能丢弃或猜测。

MaterialNeed 正式合同仍可以保留 `constraints`，其内容由程序编译产生。

## 5. B 是否保留

### 三种方案比较

| Dimension | Option 1：当前式 classifier | Option 2：有界语义 reviewer | Option 3：只处理 unresolved |
|---|---|---|---|
| 语义权威清晰度 | A、B 重复解释 | 冻结事实、候选、复核分明 | 清晰，但依赖未决识别 |
| 重复解释 | 高 | 审核已有语义提议 | 低 |
| 模型任务复杂度 | 分类与机械协调混合 | 聚焦支持关系、归属与覆盖 | 较低 |
| Payload | 全目录、units、controls、Schema | 完整问题及相关冻结语境 | 通常较少 |
| Repair locality | 容易整批重答 | 定位具体义务／问题 | 局部 |
| 确定性责任 | 部分仍交给模型 | 程序负责 | 程序负责 |
| 迁移成本 | 低，但保留主要根因 | 中等，集中于 Planning 边界 | 中等，另需可靠未决检测 |
| 对当前合同风险 | 继续累积兼容复杂度 | 可保持正式合同 | 可能漏掉自信错误 |

**推荐 Option 2。**

Option 3 无法覆盖 A 自信但错误的输出。batch09 已说明：输出合法、自信、引用可用，并不意味着新增硬条件语义成立。

### B 的唯一职责

审核：

1. A 是否忠实承接冻结含义。
2. 新具体化是否服务既定目标。
3. 新 required 是否获得真实语义支持。
4. 原素材条件、后期用途及作者责任是否正确区分。
5. 是否遗漏冻结义务。

B 不生成另一份 Plan，不重新切割 A 的正式序列化字符串，也不协调 path、alias、operation 或全局 source ID。

B 返回有界复核结果：

```text
ACCEPT
CHALLENGE
UNRESOLVED
```

并附本题证据选择及简短理由。程序据此核对合同条件，决定是否接受。

“独立复核”指证据不依赖 A 自证，不表示两次模型判断具有统计独立性。

### 复核覆盖

本版必须覆盖：

- 视觉候选新增或改变的语义义务。
- 必要性、偏好及模态判断。
- 每个视觉 scope 对冻结义务的完整承接。

不能只审 A 自报的 unresolved。

纯音频保持现有路径及 B=0；不新增音频 Gate，也不宣称声音语义已因此得到可靠验证。

## 6. Bounded Semantic Question

每道题包含以下概念信息，不在本轮定义代码类：

| 内容 | 责任 |
|---|---|
| 本题关联身份 | 程序生成、核对 |
| 当前对象、scope 和义务 | 来自唯一候选 |
| A 提议的含义、强度、责任 | 明确待复核项 |
| 相关完整冻结语境 | 程序构造 |
| 本题可用证据 | 程序预绑定真实出处 |
| 可回答的语义决策 | 有限范围 |
| 简短证据选择和理由 | B 输出 |

### 模型必须看到什么

- 当前义务完整语义。
- 适用场景的完整原文。
- 会影响理解的相邻表达、用途和否定条件。
- 适用的全局限制。
- 有关的 Creator／Truth 边界。
- Mode 的合法表达范围。

完整性复核所需上下文不能由 A 自己选择，否则遗漏可能同时从候选和证据中消失。

### 程序先处理什么

- 实际来源身份与 scope 资格。
- 已知字段资格。
- 原值与投影的一致性。
- 实际默认或派生关系。
- path、alias、hash、offset。
- 问题与结果的对应关系。

模型可以选择本题局部证据标签，但不填写正式来源路径或协调全目录编号。

### 上下文不足时

返回明确的 `INSUFFICIENT_CONTEXT`／unresolved。

不得以相关性裁剪为理由删除否定、上位限制或完整语义。只允许在原有额度和预先固定调用范围内处理；无法完整承载则停止。

### batch10 before／after

**Before**

```text
约 88KB B 输入
10 units
10 controls
56 sources
逐项重复资格 Schema

repair 约 142KB
```

**After 的责任变化**

| 内容 | 处理方式 |
|---|---|
| 成片 9:16、15 秒、silent | 程序读取冻结规格 |
| image 与 media_type 的一致性 | 程序派生 |
| 源素材是否必须竖幅 | 仅在真正有歧义时提语义问题 |
| 两张白纸及原素材无字条件 | 完整义务复核 |
| 原图留白属性与后期叠字用途 | 有界语义问题 |
| 低饱和风格 | 单一软风格事实及具体化复核 |
| 禁手／禁屏等新增条件 | 核验实际支持，不能由候选自证 |
| 各 alias 的 source/path 资格 | 不进入模型任务 |

示意问题：

```text
对象：scene 的背景源素材

完整场景证据：
两张白纸、原素材文字条件、后期叠字用途及适用表达边界。

候选义务：
A 提议原图具有留白，并说明用于后期叠字。

复核：
该条件约束原图属性还是编辑结果？
必要性是否成立？
是否遗漏或新增了其他硬条件？
```

不承诺缩到某个 KB 数字。实施必须测量完整输入、输出及 repair 的真实容量。

## 7. Source／Provenance Boundary

| Program owns | Model owns |
|---|---|
| 来源真实身份 | 语义蕴含 |
| path、offset、hash | 创作相关性 |
| scope 的机械适用性 | 歧义范围解释 |
| 已知字段资格 | 是否支持源素材要求 |
| operation 目标及实际值 | 合法创意具体化 |
| 精确原件绑定 | 非明确要求的必要性判断 |

例如：

```text
source5.value == 9:16
```

程序可以证明这个等式。

但：

```text
成片 9:16 是否要求源素材原生 9:16
```

可能仍需语义判断。

程序不能以合法引用代替语义支持，也不能通过默认记录把派生值改称 Creator 明令。

因此：

- Preparation 派生上下文不独立创造 Creator 义务。
- 隐私事实不机械推出“禁止出现手部”。
- Mode 软偏好不升级 required。
- A 候选不成为自己的上游证据。
- B 结果必须绑定实际候选、冻结上下文和政策版本。

## 8. Classification Model

### 历史证据是否证明四分类表达能力不足？

**尚未证明。**

batch04–10 直接证明了输入碎片化、职责混杂、强度冲突和语义误判。不能仅凭这些错误断言四个枚举必须废除。

### 推荐设计

应用层分别表达：

```text
义务强度
责任对象
```

certainty 作为处理结果：resolved 或 unresolved。不建立三个维度的通用领域本体。

Need 的 required／optional 继续使用现有合同。

| 已明确的语义 | 正式投影 |
|---|---|
| 必需原素材条件 | required |
| 原素材软偏好 | preference |
| 编辑／叙事义务 | postproduction |
| 无法安全确定 | unresolved，阻断 |

必要后期义务投影为 postproduction 时，检查点继续保存其真实责任和强度；它不会因此变成可忽略事项。

optional Need 也可以拥有必须满足的源条件。“是否必须供应该 Need”与“候选是否满足该 Need”分别处理。

B 审核这些语义提议；程序生成正式四分类，不让 B 对程序再次序列化的字符串重新分类。

若一种含义无法无损映射到现有合同，保持拒绝或单独评审，不能强转为 preference/postproduction 来通过。

## 9. Artifact Delivery

### 目标链路

```text
LLM 返回完整结构化结果
→ Harness 按原 run 捕获
→ 程序检查结果完整性
→ 程序持久化
→ 程序生成正式合同
```

正式文件不再依赖 Agent 主动调用文件工具。

### 结果类别

这些是应用层观察与诊断类别，不新增 Delivery 状态机。

| 类别 | 含义 |
|---|---|
| MODEL_COMPLETED | 模型终态已确认，进入结果核验 |
| MODEL_TRUNCATED | 原运行明确截断 |
| MODEL_NO_RESULT | 已终态但无完整结果 |
| TRANSPORT_FAILED | 传输／观察失败，执行终态可能仍未知 |
| STRUCTURED_OUTPUT_INVALID | 捕获完整，但结构不合法 |
| PERSIST_FAILED | 完整结果已取得，本地保存失败 |
| CONTRACT_REJECTED | 结构合法，合同条件不成立 |
| ACCEPTED | 结果与相应合同检查成立 |

`MODEL_COMPLETED` 不等于 `ACCEPTED`。

### 当前 OpenClaw 能力约束

当前代码的结果捕获绑定 `material-result-v1`，应用捕获容量为 3,000 个 UTF-16 单元，Planning 尚未使用这一路径。

所以不能直接打开 `capture_reply=True` 就宣称问题已解决。

设计要求：

- Planning 使用独立的内部回复合同，复用原 Gateway 和原 run 对账。
- 从正式终态接口取得回复和 stopReason。
- 不从 thinking、默认 workspace 或非正式日志猜测 JSON。
- A 按完整 scope 语义组、B 按完整问题组事前有界分块。
- 每块必须能够完整返回；不得截半个义务或半段 JSON。
- 输入字节、输入 token、输出 token 和返回捕获容量分别核对。
- 单个完整语义组无法承载时，软件入场条件不成立。

本轮不调整容量或 Runtime。若未来必须扩展受控传输能力，单独评审。

### 持久化与 checkpoint

1. 派发前保留当前请求身份、范围、版本和额度。
2. 捕获原 run 的完整结果和终态。
3. 结果安全检查后，由 Harness 保存允许留存的回复及摘要。
4. 相应结构、语义和绑定检查通过后，形成局部接受检查点。
5. 全部必要 scope 通过后，程序生成 Plan、Requirements。
6. 按既有原子保存、恢复和 Manifest 发表约定完成正式持久化。

含 Secret 的结果停止处理，只保存安全诊断类别及必要摘要，不写入 Attempt、日志或文档。

磁盘保存失败后，可以从已完整捕获的同一结果继续本地保存；不能再发一次模型。

## 10. Repair Boundary

### 三个范围

| 范围 | 内容 |
|---|---|
| IMMUTABLE | 冻结原件、已接受语义、必要性、身份、授权、预算、Consent、已接受复核结果 |
| REPAIRABLE | 明确局部范围内的结构错误、未接受语义、错误的本题证据选择或复核答案 |
| REJECT_ONLY | 上游真实不一致、权限冲突、无法无损局部修复、额度耗尽 |

| 问题 | 处理 |
|---|---|
| Schema error | 一次共享额度内修指定字段，保护合法语义 |
| Semantic error | 仅修未接受部分；改变后的义务必须再次独立复核 |
| Transport unknown | 观察原 run，不创建新执行 |
| Truncation | 标记 MODEL_TRUNCATED，停止本次评测；不作为 semantic repair |
| Missing formal artifact | 有完整捕获结果则由程序恢复保存 |
| No captured result | MODEL_NO_RESULT，不能从其他目录补文件 |
| Source mismatch | 真实来源不匹配则拒绝；局部证据选择错误才可能修 |

修复输入限定为：

```text
已接受且不可变的语义
＋具体问题
＋有界可修改部分
＋必要冻结证据
```

不重新生成整个对象。

沿用当前整次 Planning 共享一次模型 repair 上限，不因分块、重启或问题数量刷新。

如果 A 语义被修补，必要的 B 重审必须明确计入预先固定的调用、时间和费用上限；上限不足则拒绝，不能豁免复核或暗中加调用。

## 11. Formal Contract Compatibility

| 合同／职责 | 设计处理 |
|---|---|
| MaterialPlan | 保持正式结构和职责 |
| MaterialNeed@1 | 保持；字段改由程序投影 |
| Requirements | 保持正式条款形式和 source/path/text 对齐 |
| Manifest | 保持正式结构与当前产物完整性含义 |
| Truth | 保持真实性审核职责及冻结 SCRIPT |
| Delivery | 保持状态机、原 run 身份及对账 |
| Rights／Match／Readiness | 保持准入语义 |
| Hypit | 保持后期及制作职责 |

### 必须变化的内部合同

- A 草稿。
- B 输入和复核回复。
- Planning capture 协议。
- 内部语义检查点及 compiler policy。
- 相应 request、revision、hash 和 cache identity。

这些必须独立版本化。现有 persist/load 对新版本明确分支，不能用旧版本降级接受缺失证据。

旧冻结记录按原版本精确恢复；旧 pending 先按原身份核对终态。不迁移历史 Plan，不把新版解释套到旧产物上。

### 已确认的消费路径风险

当前 [NeedCompiler](/Users/xgx/Projects/Easel/easel/materials/application/compiler.py:50) 会将 `preferred_style` 放入 filters，而其他路径将风格视为 soft。源码证明了表示角色不一致；尚不能据此断言所有 Provider 都实际硬执行该字段。

新政策必须闭合这条投影：

- 必要兼容 alias 由程序派生。
- 所有表示指向同一事实和强度。
- 软表示不能进入有效硬约束。
- 保留现有软匹配意义。

必要时做最小消费者边界适配，不改变 Provider、Matcher 阈值或准入标准。若无法隔离新版本、必须改变旧已验证行为，停止该项并单独评审。

因此可以保持外部合同，但不能承诺所有下游源码完全不动。

## 12. batch01–10 映射

| Batch | Root Cause | vNext prevention／detection | Still possible? |
|---|---|---|---|
| 01 | Harness 把异步观察误判失败 | 保留原观察修正；不属于本次核心语义改造 | NOT_ADDRESSED：原回归保护 |
| 02 | policy 类型错、repair 错目录 | 策略由程序负责，Harness 唯一持久化 | PREVENTED_BY_DESIGN |
| 03 | 自由 constraints 与消费者冲突、unknown continuity | 收回自由执行字典、程序绑定真实候选 | PREVENTED_BY_DESIGN；语义错仍可能 |
| 04 | 引用／后期原文被切碎后重新分类 | 保留完整义务，不从正式字符串重新造题 | 碎片缺陷 PREVENTED；归属 STILL_MODEL_RISK |
| 05 | 作者叙事禁令被当作素材条件 | A 分开责任，B 审核实际归属 | DETECTED_MORE_CLEANLY／STILL_MODEL_RISK |
| 06 | 留白源属性与叠字用途误归后期 | 分开条件与目的，完整关系复核 | STILL_MODEL_RISK |
| 07 | 非法 kind、repair wrapper 错误 | 轻量固定回复合同、程序绑定 | DETECTED_MORE_CLEANLY |
| 08 | 合法结构持续 unresolved | 局部完整问题与明确不足证据停点 | STILL_MODEL_RISK |
| 09 | 无依据禁屏／禁手变 hard | 单一强度、机械资格保护、支持关系复核 | 机械越界可阻止；错误具体化仍是模型风险 |
| 10 | alias／强度重复、资格协调、repair 截断 | 程序投影与资格计算、明确返回完整性 | 重复协调 PREVENTED；截断 DETECTED_MORE_CLEANLY |

本设计不保证历史语义错误永不再现，也不证明 payload 是 batch10 截断的唯一原因。

## 13. Development Eval Entry Gate

### 软件入场条件

必须具备具名证据：

- 确定性测试通过。
- 真实内部调用链集成通过。
- 十批历史现场及既有 fixture 指纹不变。
- 每项事实与正式字段有明确唯一权威和双向追踪。
- 无已知重复语义权威。
- 没有隐藏的合同缺口或必测未执行。
- A、B、repair 的输入和输出容量均已验证。
- artifact capture、截断、无结果、保存失败明确区分。
- scope 完整性、部分分块失败和崩溃恢复已覆盖。
- 新旧版本恢复与 pending 身份已验证。
- 独立 Expected 保留，不能用模型答案或首个合法 source 自动填写。
- 项目检查及固定版本复核完成。

核心集成：

```text
正常确认
→ Owner / Preparation
→ A capture
→ B review
→ Truth
→ persist / load
→ Material Supply 前切点
```

外部边界使用替身，内部模块使用真实实现。

### Dev Eval 建议固定限制

| 项目 | 设计上限 |
|---|---|
| 样本 | 3 个开发主题，各 2 次，全新执行 |
| 总执行数 | 最多 6 次 |
| 总模型提交 | 最多 32 次，包含 Prep、分块、Truth、repair、必要重审 |
| 总墙钟 | 最多 60 分钟 |
| 单样本 | 最多 8 分钟 |
| 素材外部执行 | 禁止 |
| 费用 | 另行绑定可核实范围；禁止未经授权的现金／回退 |
| 留出样本 | 不使用 |

首次合同 FAIL、独立语义 FAIL、unknown、结果缺失、工程介入或上限耗尽，立即停止整批新增派发。

超时不能当作执行已终止；原 run 未知时继续对账，不能补发。

修改软件后先回到离线证据和软件验收，再另行固定版本与评测范围。不能自动重新启动一批 32 项。

六次开发通过也不证明稳定通过率。正式 R4、Smoke、E2E 各自保留独立入口审查。本轮不授权启动任何一个。

## 14. 范围控制

### MUST CHANGE

- Canonical facts 与程序投影的单源约定。
- A 的混合结构与确定性重复字段。
- B 的机械协调任务和正式字符串再解释。
- 完整 scope 语义覆盖检查。
- Harness capture 与程序唯一持久化。
- 局部 repair、版本身份和恢复绑定。
- 对应真实内部集成及独立语义预期。

### SHOULD CHANGE

- Payload、返回容量、调用量的可解释记录。
- 重复 Schema 和无必要机械目录传输。
- 局部诊断和证据展示。
- 必要软 alias 的消费者对齐；存在有效硬化冲突时升级为 MUST。

### DO NOT CHANGE

- Creation lifecycle。
- Delivery state machine。
- Truth 整体职责。
- Material V1.3。
- Provider adapters。
- Material Supply 编排。
- Rights、Match、Readiness 标准。
- Hypit Runtime、Build、Quality。
- 历史失败结论及产物。

不新增 Agent Framework、Domain、公开路由或第二生产链。

## 15. Current vs vNext

```mermaid
flowchart TB
  subgraph Current
    C1["冻结上下文"] --> C2["A：语义、技术值与 alias"]
    C2 --> C3["MaterialNeed / units / controls / 全来源目录"]
    C3 --> C4["B：分类、支持关系与机械协调"]
    C4 --> C5["Agent 写结果文件"]
    C5 --> C6["程序编译与正式持久化"]
  end

  subgraph vNext
    N1["冻结上下文"] --> N2["程序事实绑定与已知投影"]
    N2 --> N3["A：单一语义候选"]
    N3 --> N4["B：有界支持关系与完整覆盖复核"]
    N1 --> N4
    N4 --> N5["Harness 捕获完整结果"]
    N5 --> N6["程序编译 Plan / Requirements"]
    N6 --> N7["既有 Truth / persist / load / Delivery 条件"]
  end
```

图中的程序事实绑定、问题构造和捕获均属于现有 Planning 应用层，不新增运行平台。

## 16. 迁移批次

沿用一个 Task、一个矩阵执行器和一个验收入口。建议五批，本轮不实施。

| 批次 | Goal／changed boundary | Unchanged contracts | Verification | Rollback point |
|---|---|---|---|---|
| S1 | 固定事实、投影与历史预期 | 当前生产行为、历史产物 | 单源清单、真实失败回放、独立预期 | 尚无生产切换 |
| S2 | Harness capture、程序持久化、明确失败类别 | 原 run 对账、Material 回复协议 | 完整／截断／无结果／保存中断集成 | 停止新版新请求；保留原 run |
| S3 | 新 A 草稿和程序正式投影 | MaterialNeed 正式结构、冻结上下文 | 别名、模态、比例、时长、软硬及声音绑定 | 关闭新版本入口，不重解释已冻结记录 |
| S4 | B 有界复核、覆盖与 repair | 正式四分类、一次共享额度、Truth职责 | batch04–10 语义反例、新旧恢复、局部修复 | 停止新版；pending 保持原版本 |
| S5 | 组合软件验收与后续 Dev Gate | Supply／E2E 后置 | 完整调用链、项目检查、指纹、冻结复核 | 软件未达标不放行真实阶段 |

回滚不能将新版 pending 请求或检查点交给旧政策继续，也不能覆盖历史 FAIL。服务加载另行启动。

## 17. Astra 一次复核

```ini
ASTRA = CONTINUE
```

复核结论：

1. 明确减少了模型维护的确定性关系。
2. Creator、Mode、Planning 候选、复核与程序绑定的权威清楚。
3. 降低了 A→B 的重复解释。
4. 设计上保持 Material／Delivery 边界。
5. 当前没有明显过度设计。
6. 具备进入后续获批软件实施的设计条件。

保留两项实施停点：

- 完整语义超过容量时，不能删减、截断或追加调用来通过。
- 软 alias 若必须改变旧已验证行为，先单独评审。

该结论不放行真实评测或部署。

## 18. 最终状态

```ini
PLANNING_VNEXT_DESIGN = PASS
CURRENT_R4 = PAUSED

PRIMARY_BOUNDARY =
SemanticPlanningDraft / MaterialNeed
→ Bounded Semantic Review
→ Formal Contract Projection

CANONICAL_FACT_MODEL =
对象、scope、含义、强度及真实权威明确；程序维护投影

A_RESPONSIBILITY =
提出单一语义计划和真实创意选择

B_RESPONSIBILITY =
复核支持关系、责任、强度及冻结义务覆盖

A_TO_B_REINTERPRETATION =
CURRENT: 正式表示再次切分分类，并协调机械关系
TARGET: 审核明确语义候选，程序派生正式表示

SOURCE_PROVENANCE_BOUNDARY =
程序证明真实绑定与资格；模型判断语义支持

CLASSIFICATION_MODEL =
应用层区分强度与责任；正式四分类保持

ARTIFACT_DELIVERY =
Harness 捕获；程序唯一持久化

REPAIR_BOUNDARY =
局部可变域；一次共享额度；截断不算语义修复

FORMAL_CONTRACT_COMPATIBILITY =
保持外部合同；内部版本化；必要消费者适配明确评审

BATCH01_10_COVERAGE =
机械缺陷预防、交付失败明确检测、语义风险保留评测

DEVELOPMENT_EVAL_GATE =
软件与容量闭合后，另行授权有界开发评测

MUST_CHANGE =
单源事实、A/B职责、capture、投影、恢复与对应集成

SHOULD_CHANGE =
传输冗余、容量记录、局部诊断及必要软别名对齐

DO_NOT_CHANGE =
Creation / Delivery / Truth整体 / Material V1.3 /
Provider / Supply / Hypit / Build / Quality

IMPLEMENTATION_PHASES =
S1事实与基线 → S2交付 → S3 A与投影 → S4 B与修复 → S5组合验收

ASTRA = CONTINUE
READY_FOR_IMPLEMENTATION = YES
REAL_EXECUTION_AUTHORIZED = NO
```

## 19. 八个明确回答

1. **是否保留两阶段 Planning？**
   保留，推荐 A＋有界 B。只审核 unresolved 无法发现自信错误。

2. **A、B 各自唯一职责是什么？**
   A 提出语义计划；B 审核其对冻结要求的忠实承接、合法具体化及覆盖。

3. **哪些确定性字段从模型输出删除？**
   技术 alias、重复已知值、正式 ID/path/hash/offset、operation、sidecar、revision/cache、文件处理和执行策略。

4. **哪些 provenance 关系由程序预计算？**
   来源身份、精确原件绑定、scope 机械资格、字段资格、实际派生及目标关系。语义蕴含继续交给复核。

5. **四分类是否修改？**
   外部保持。内部明确强度与责任，避免把 required、后期和 unresolved 混为同一问题。

6. **Artifact delivery 如何收回 Harness？**
   从原 run 正式终态捕获完整结构结果，明确容量与截断，再由程序保存、编译和生成正式产物。

7. **能否保持 Material V1.3／Delivery／Truth 外部合同？**
   可以。内部协议版本化；必要消费者适配不能偷偷改变旧行为。

8. **最小可行改造是什么？**
   在现有 Planning 边界完成单源投影、A 收窄、B 有界复核和 Harness 持久化，并用真实内部集成与独立语义预期证明其行为。

**本轮设计与复核完成，停止。R4 保持暂停，未启动 batch11。**

## 20. 连续实施状态（2026-10-07）

授权来源：本轮用户附件，连续 S1–S5、一次最终 Astra diff 复核、有界 Development Eval；每轮最多6样本/32模型提交/60分钟/单样本8分钟，最多两轮/12样本/64提交/120分钟。同根因跨两版重复则停止。Formal R4/Supply/媒体生成/TTS/Build禁止，不push、不升级Runtime。仅已购文字套餐，无现金/余额/超额/付费fallback；真实阶段重新核实可证路由。

- Step0：完整设计原文落盘，窄commit c5d282c8；仅新增本Task与索引单行，未提交其它用户修改。
- S1：Planning局部事实绑定与单一投影实现；139矩阵PASS（run-019）、139语义回归PASS，257正式现场/117历史fixture保持。成片与源比例、时长、静音与模态分别保护。只证明确定性投影，不代表产品新版已接入。首次新增测试装饰器收集错误已修正并重跑；未影响生产或历史成绩。
- S2–S5：NOT_EXECUTED。Development Eval：NOT_EXECUTED；R4 PAUSED/FAIL。
- 完整git diff --check的两项EOF空行来自既有用户Task/Acceptance修改，本任务选定路径diff检查通过；不清理无关改动。

### S2 Gate

Planning内部reply_contract=planning-result-v1复用原Gateway运行；Material默认协议/hash保持。原终态length在空JSON前标记MODEL_TRUNCATED，无结果、结构错误和本地保存失败明确区分；完整回复先进入原请求/检查点，保存重试不重派。现安装2026.9.4的run-wait与terminal snapshot源码确认接口存在、服务端4096 UTF16上限；Planning保持3000保守上限，未升级Runtime。

6项真实内部Gateway适配器+Harness集成PASS；矩阵run-020 145PASS，Planning/Preparation/Material相关回归318PASS，257现场/117fixture保持。外部RPC固定替身，不证明真实模型可用；S2极小真实diagnostic可选，本阶段未调用，后续Dev记录真实capture。首次测试替身未模拟accepted异步及release终态，经校正后完整重跑；未放宽生产约束。S3–S5未执行。
