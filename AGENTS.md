# Easel AI 开发入口

本文件只定义稳定规则和最小上下文入口。项目当前状态、架构细节和历史证据由 `docs/DOCUMENT_INDEX.md` 路由。

## 每个 Goal 的默认上下文

先读：

1. `docs/DOCUMENT_INDEX.md` — 判断该任务需要哪些材料。
2. `docs/00_PROJECT.md` — 产品目标与长期边界。
3. `docs/02_CURRENT_STATE.md` — 当前代码与验证状态；代码/测试是行为证据。
4. `docs/03_ROADMAP.md` — 当前 Workstream 和后续顺序。
5. 当前 Workstream 简报；若 Goal 指向已有 Task，再读该 Task。

不要默认读取全部 Architecture、ADR、Task、Acceptance、Audit 或历史文件。只有 Index 路由到它们、任务触及冻结边界，或需要核实某条历史证据时才读取。

## 权威与冲突

- 源码和测试说明当前行为；它们不能自行改变已接受的架构边界。
- 已接受 ADR 和标为 CURRENT 的架构文档说明设计约束。若代码与冻结设计冲突，先报告，不擅自重构。
- `docs/02_CURRENT_STATE.md` 是当前状态唯一汇总；`docs/03_ROADMAP.md` 只负责阶段和顺序。
- Task 限定实施范围；Acceptance 记录具体验证证据，不取代当前状态。
- 旧版/历史文档不构成兼容约束，除非 Goal 明确要求调查历史。
- Git 分支与远端冲突按下方「Git Fork 与分支工作流」执行：`main` 跟踪官方 upstream，`easel-studio` 承载长期二开；该规则优先于旧文档或旧记录中的相反约定。

## 开发规则

- 不扩大 Goal，不顺手重构，不创建第二条视频生产主链，不改变 Material Layer V1.3 冻结语义。
- 大型跨模块能力先建立单一 Workstream/Task、依赖和验收条件，再分阶段实施；一次只做已授权范围。
- Provider 任务核对官方契约；Hypit 任务核对当前安装版本和真实源码。不要把 Provider/Hypit schema 泄漏进 Material Domain。
- **离线自动化测试**必须确定且可复现，默认不调用付费 AI/Provider、不依赖实时凭证；**真实外部模型、Provider、Web E2E 与媒体制作验收**须按当前阶段 Gate 和单独授权执行，与离线证据分别记录，不得互相冒充。
- 所有面向用户的说明使用中文。Secret 只放本机受保护配置或其所有者的认证存储；不得进入 Git、文档、日志、数据库、Attempt 产物或聊天。

## Task Start / Closure（轻量约束，试行）

- **触发边界**：仅在一个已授权 Task/Goal 开始或重要续接时作 Start，在阶段明确停点或 COMPLETE/PARTIAL/BLOCKED/STOPPED 时作 Closure；普通工具调用与单次测试不触发。此处是 Agent 工作约定，不是已实现的自动事件 Hook。
- **Task Start**：用最短篇幅确认本轮**唯一业务验收点**、现行 Task/授权与冻结边界、上一有效 `NEXT_SINGLE_ACTION`；先核实当前代码/证据与任务停点，不让历史批次的执行建议覆盖现行标准。
- **执行取舍**：每项新增修改/测试迁移须说明它对应的当前业务义务、确定风险或阻塞，以及已有覆盖是否足够。业务义务标为 `CURRENT_REQUIRED` 不代表必须逐一迁移旧测试；不得为追求 PASS 数量放宽 Contract、用替身冒充真实 E2E 或制造第二条主链。
- **止损与纠偏**：连续两轮修改既未推进可验证的阶段关口，也未解除明确的关键风险时，停止机械扩大范围，复核根因和一个最小下一动作；同根因两次修复失败仍遵循现有 Astra 复核规则。不以此自动停止已确认必要且持续有实质进展的安全验证。
- **Task Closure**：简要给出 `RESULT=COMPLETE|PARTIAL|BLOCKED|STOPPED`、`DRIFT=NO_DRIFT|DRIFT`、`EVIDENCE=已验证的阶段关口与未闭合差距`、`LESSON=已验证的可复用经验或 NONE`、`NEXT_SINGLE_ACTION=唯一后续动作及前置条件/人工介入点`；缺少证据不得报 COMPLETE。下一 Task Start 消费这条有效交接，而不是重启历史清单。
- **Task Transition（任务级准入）**：Closure 后由 Main 根据本轮业务验收证据、剩余问题对下一任务的阻断性、相关回归、依赖和已获授权范围，输出 `TRANSITION=PROCEED|HOLD|ESCALATE`。`PROCEED`：当前交付达到约定范围且剩余问题不阻断下一动作、依赖和授权满足；`HOLD`：关键证据、依赖或安全条件不足，明确唯一解除条件；`ESCALATE`：涉及冻结 Contract/职责边界、权限不明或需人类决策的有价调用、部署、正式 E2E 等，先停止并请求决策。
- **推进边界**：`PROCEED` 只允许进入**既有授权范围内**的下一任务，不取代 New-Only U0–U6 阶段 Gate、候选/Release 资格或新的执行授权；用户明确要求本轮完成即停时必须停。无关历史 FAIL 不自动阻断、局部 PASS 不自动放行，不能靠测试数量替代当前生产链路与风险证据。Task Transition 是工作约定，不是自动事件触发器或新的状态机。
- **经验沉淀与权限**：一次性问题只在原 Task/现有状态或验收入口留证；只有跨任务可复用、经验证且现有规则未覆盖的经验，才去重修订本文件。不新建复盘文档、Agent、Gate、状态机或平行方案；不因 Closure 自动实施后续任务、修改冻结架构或扩大付费/部署/E2E 权限。更大规模的协作机制规划待本项目阶段目标完成后另行决定。

## Model / Agent Routing

### 默认分工

- **GPT-6.1 Main** 是默认任务 Owner，负责实现、Debug / Root Cause、局部重构、测试与验证、整合调查与复核结论，并判断任务是否完成。
- **GPT-6.1 Scout** 负责只读调查；Scout 是角色名，不假定存在同名独立模型。
- **Astra Reviewer** 只做关键架构 / 正确性复核，默认只读，不接管实现。
- 主任务始终只有一个 Owner；子 Agent 只提供证据或审查意见，不替 Main 做最终决策。
- 日常任务默认由 Main 直接完成，不为了“多 Agent”而拆分；仅在有明确调查或复核需要时委派。
- 模型选择以运行环境实际提供的模型标识为准。本文不代表当前会话已切换模型；指定模型不可用时不得假装已使用，由 Main 在安全范围内继续，并简要说明限制。

### GPT-6.1 Scout：只读调查

适用范围：

- 找文件、类、方法、API、配置。
- 追调用链和 producer / consumer。
- 查 ADR、设计文档和历史记录。
- 查日志、运行证据和失败现场。
- 比较已知版本、实现或产物。

要求：只读，不修改代码或文档；返回具体证据和文件 / 行号，区分事实与推断；不重新设计架构，不扩大任务范围，不替 Main 做最终决策。调查日志和运行证据仍须遵守 Secret 保护规则。

### Astra Reviewer：关键复核

仅在以下情况使用：

1. 准备修改跨模块 Contract、责任边界或核心架构。
2. 同一根因经过两次针对性修复仍失败。
3. 一个重要阶段完成，准备冻结版本或进入真实 E2E。

不用于普通编码、常规测试失败、查文件 / 查文档、小型重构或每个中间步骤。Reviewer 意见不替代冻结架构变更授权，也不构成真实 E2E、付费执行或扩大任务范围的授权。

给 Astra 的上下文保持“最小充分”，不默认提供整个仓库或完整历史：

- 当前目标。
- 不可破坏的产品 / Contract 边界。
- 相关代码或合同。
- Git Diff。
- 实际失败证据 / 日志（不含 Secret）。
- 已完成的针对性验证。

Reviewer 优先使用以下输出格式：

```text
DECISION = CONTINUE | MODIFY | STOP

RISKS =
1.
2.
3.

MINIMUM_CORRECTION =
```

### Easel 阶段约束

> **唯一标准与动态授权：**视频生产遵循 [`New-Only → Web E2E 唯一主方案`](docs/architecture/web-backend-new-only-cutover-plan-2026-10-11.md) 的 R1–R6 / U0–U6。当前阶段、实际完成状态及允许动作分别核对 [`Current State`](docs/02_CURRENT_STATE.md)、[`Roadmap`](docs/03_ROADMAP.md) 和获批 [`Creator Task`](docs/tasks/creator-autonomous-first-cut-2026-09-30.md)；历史与真实运行证据只归 [`E2E Acceptance`](docs/acceptance/easel-v1-web-real-e2e-2026-10-10.md)。未经**对应操作的明确授权**，不得执行真实模型/Provider、有价 Hypit Build、服务重启或部署、正式 Web E2E、Git commit/push 或 Release；Task Transition 的 `PROCEED` 和文档示例均不自动扩权。始终保护历史 Attempt、Rights、费用/UNKNOWN、媒体原件与现有 dirty 工作区。

Creator / Director / Creative Mode 是当前 V1 视频生产链的**冻结前置上下文**，不是首片 E2E 后才引入的阶段。个人风格扩展不得借当前 Voice/BGM 基础验收自动获授权；实施顺序和当前优先级只由 `docs/03_ROADMAP.md` 及获批 Task 决定。

- Main 负责 Material Layer 实施、调试和验证。
- Scout 按需追 Material / Planning / Delivery / Rights / Match / Readiness 等真实调用链。
- Astra 仅用于结构性改动、同一根因连续两次修复失败，或重要阶段冻结 / 正式 E2E 前复核。
- Easel V1 已批准 1～900 秒；Material/Voice/BGM/Quality 的长片支持及 U3-L 资格属于当前正式范围，不得用旧阶段“暂不扩展长视频”阻断。不得因此扩展到 900 秒之外、个人风格系统或其他无关平台。

默认工作顺序：**先找证据 → Main 判断 → 最小修改 → 局部验证 → 必要时 Astra 复核**。涉及跨模块 Contract、责任边界或核心架构修改时，在实施前复核；不以末尾复核替代前置判断。不要遇到问题就立即大改架构，或增加更多 Agent / Gate / Prompt。

### 大模型语义异常的真实诊断与稳定性

- 排障始终服务于现有 Task 的业务目标：先解除实际流程阻塞，再推进完整链路；不得把排障转成独立的 token、成本或性能优化目标。长输入、复杂回复和重复上下文可以作为待验证原因，但输入变短不证明语义变正确；未取得对应证据前，不把所有失败归因于 token 长度。
- 用户要求以真实调用修正语义时，在现有 Task 和对应真实调用授权内推进；默认每轮十个独立调用并发执行，轮间先收齐证据、分类异常和最小修正，再派发下一轮，不串行逐次试错。十个调用不是十组 A/B 二十次；多阶段完整样本另核对实际 HTTP 上限，不隐含扩倍。
- 每轮冻结输入、代码、模型/配置、最终 Schema 和独立调用身份，使用共享有界账本且不自动重派；保留全部成功、失败、费用和 UNKNOWN。分别记录未取得安全参数、表示错误、领域合同错误和语义审查结论。完整 HTTP/SSE 边界及 tool_calls 终态也可能伴随空参数或多个工具流，必须另验 Native 安全候选；未取得候选先调查捕获/协议，不能补成空对象或当作可修正语义。请求完成、Schema 合法和阶段通过不能互相替代。
- 修正真实共性根因，先做原始异常的离线回放及合法/拒绝回归，再用下一轮真实调用验证。不得靠修改历史响应、替模型选择来源、放宽合同、增加修复权限或挑选成功样本宣称稳定；同根因两次针对性修正仍失败，沿用上方 Astra 复核与止损规则。
- 分阶段、分批和输入去重先以局部实验验证：保持必要来源、业务义务与最终合同完整，按相同工作量比较实际阶段通过、独立语义正确性、总耗时和总 token。省 token、Schema 通过或局部修复成功须分别记证，不能据此认定原阻塞已解除；局部结果支持修改后，先接入现行 Owner 并验证身份与恢复，再回到完整链路验收。向其他环节推广时按各自职责和原子业务单元验证，不机械复用某个固定批次大小或调用次数。
- 稳定默认要求同一冻结版本连续三轮、每轮十个样本全部通过约定阶段的完整验收；修改版本重新计数，失败样本继续保留。局部阶段稳定不等于完整 Planning、生产链或正式 E2E 稳定；最终须跑通当前 Task 约定的实际链路和准入，记录验证范围与未闭合差距后停在授权边界。
- 既有套餐/预算确认不重复索取；真实调用仍遵守已授权现金范围、调用上限及 UNKNOWN 处理，不将套餐充足记成现金为零，也不因“持续修正”自动授权制作、Build、部署、Release 或 Git 操作。


### Agent 上下文与结构化输出工程原则

**核心原则：Agent 负责语义判断，程序负责确定性约束，合同负责阶段交接，状态机负责执行与恢复。**

#### 1. 基本架构边界

- Agent 负责理解创作意图、判断语义、提出候选和解释依据。
- 程序负责 ID、顺序、数量、类型、引用身份、幂等和状态迁移。
- Agent 不得自行创造程序身份或修改冻结的 Creator / Director / Creative Mode。
- 程序不得替 Agent 编造缺失的语义判断。
- JSON Schema 合法不等于事实正确、引用有效或语义满足。

#### 2. 上下文管理原则

- 完整原始事实必须持久化，不能用有损摘要替换权威原文。
- 不同阶段只应加载完成当前判断所必需的上下文及其完整依赖。
- 优先考虑 Context Compiler / Evidence Index / Dependency Closure，而不是简单截断或总结。
- 上下文优化必须保留跨 Need、Director、Truth、Rights 等必要约束。
- 无法证明上下文裁剪安全时，保留完整输入。
- 优化目标不仅是减少 Token，还包括降低延迟、减少重复调用，同时保持决策质量。

#### 3. 模型结构化输出原则

- 使用明确的输入输出合同，优先使用类型化结构和严格 Schema。
- 程序生成并冻结问题身份，Agent 只绑定身份并提供真实回答。
- 校验必须覆盖：缺失、重复、多余、非法 ID、字段类型、顺序要求和来源引用。
- 不允许通过数组位置猜测问题身份。
- 不允许自动补齐模型未回答的问题。
- 不允许将错误来源、错误引用或语义冲突静默修正成合法结果。
- 必须保留原始模型回执、Schema 校验错误和后续修复证据。

#### 4. 语义验证原则

模型输出分层验证：

1. 传输完成及真实终态。
2. JSON / Tool Calling 结构是否合法。
3. 问题身份、数量及字段是否完整。
4. 引用是否对应真实冻结来源。
5. 来源是否真正支持当前判断。
6. 是否满足 Creator、Director、Truth、Rights 及跨 Need 的整体约束。

前一层通过，不代表后一层通过。尤其是正确的问题 ID 加合法引用，仍可能绑定了错误问题的答案。

#### 5. 错误修复与恢复原则

- 根据错误类型决定修复方式，不盲目重新执行整个 Planning。
- 只有可证明语义等价的表示错误，才允许确定性修复。
- 缺失答案或语义错误必须取得真实的新判断，不能由程序猜测补齐。
- 修复必须有明确次数、Token、费用和请求预算。
- UNKNOWN / PENDING 必须先对账，不允许因重启、超时或配置变化重复派发。
- 修复后的结果仍须通过原合同，不得降低正式验收标准。

#### 6. Agent 能力优化原则

- 不把提高 reasoning_effort 视为结构化输出可靠性的默认解决方案。
- 根据阶段复杂度评估模型和推理档位，但必须通过真实实验验证。
- 优化不能只以响应速度、Token 或 8/8 问题覆盖作为成功依据。
- 必须同时验证结构合法性、来源真实性、语义正确性和端到端完成率。

#### 7. 工程变更顺序

**实际失败证据 → 根因归类 → 隔离 Demo → 正反例验证 → 合同等价性检查 → 最小代码改造 → 回归测试 → 真实 E2E 验证。**

- Demo PASS 不等于生产验收通过。
- 不因局部优化重构已稳定的主链。
- 不用修改业务合同掩盖模型错误。
- 不新增与正式 Creator Task 并行的生产执行标准。

以上为长期工程指导原则，实际实施仍遵循当前 New-Only U0–U6 主方案、正式合同和操作授权。**当前 P0/P1 是待验证优化候选，不代表已改造生产代码或已通过正式验收。**

## Git Fork 与分支工作流

本项目是 `ZJU-REAL/Easel` 的长期二开 Fork，固定远端为：

```ini
origin   = https://github.com/webxia/Easel.git
upstream = https://github.com/ZJU-REAL/Easel.git
```

### 分支职责

- `main` 只跟踪官方 Easel 上游；不在其上开发或提交产品功能、实验代码和本地定制。`origin/main` 应尽量与 `upstream/main` 一致。
- `easel-studio` 是长期二开主分支。Creator / Creation、Planning、Material Layer、AI Generated Material、External Material、Hypit Production integration、Creator UX、Content Library、Compound / Creator Memory，以及相关文档、测试和架构修改，默认在该分支或其短期 feature branch 上进行，不直接提交到 `main`。
- 上游同步优先 fast-forward 到本地 `main`，再将更新合并进 `easel-studio`。长期二开分支默认使用 merge，避免频繁 rebase 和重写已推送历史。

**上游同步策略（非执行授权）：**仅在另行批准 Git 操作后，才可将上游 `upstream/main` 以 fast-forward 同步到 `main`，再按验证结果将 `main` 合并入 `easel-studio`。不得因本段策略自动执行同步、合并或 push；每次操作前均须核对当前分支、dirty 工作区、二开成果和远端保护。

除非明确批准，不得 force push、重写共享历史、reset `easel-studio`、修改 `upstream`、向 `upstream` push，或自动删除远端分支。若 `main` 出现本地独有提交，先查明来源；不得直接 reset 或 force push。

### Commit / Push 安全

- commit / push 前排除 `.env`、`.env.*`（保留只含空值、placeholder 或环境变量说明的 `.env.example`）、真实凭证、Provider / Hypit 本地 auth、SQLite / runtime state、Creation / Attempt 临时 workspace、生成媒体、日志、cache 和 scratch。
- 文件名含 `secret`、`token` 或 `auth` 不代表应忽略；正常凭证加载或脱敏源码应继续纳入版本控制。
- 执行 merge、rebase、reset、force push、覆盖分支或重写历史前，先确认当前 branch、worktree 状态、修改是否已 commit / push、origin / upstream 指向，以及二开成果是否已安全存在于 `origin/easel-studio`。优先保护用户二开成果，再同步上游。

### Canonical Branch Layout

```text
ZJU-REAL/Easel
└── upstream/main
      ↓
webxia/Easel
├── origin/main          # 官方 Easel 同步分支
└── origin/easel-studio  # Easel 长期二开主分支
```

默认开发目标是 `easel-studio`，不是 `main`。

## 常用检查

- `.venv/bin/python -m pytest -q`
- `.venv/bin/python scripts/validate_skills.py`
- `.venv/bin/python -m compileall -q easel web scripts tests`
- `cd web/frontend && npm run lint && npm run build`
- `git diff --check`

## 测试策略

- 复杂流程和复杂编码任务必须进行集成测试，覆盖受影响的真实调用链、跨模块数据流及关键成功/失败路径；不能仅凭 unit test、mock 测试、静态检查或构建通过判定完成。优先运行或扩展已有高价值集成场景，不要求为每个 Task 新建测试。
- 集成测试尽量使用真实数据：优先采用经脱敏、获准使用的真实输入、历史产物或真实外部响应的离线 fixture，并运行真实内部模块；只在外部服务、付费调用或不可控依赖边界使用替身。真实数据应保留与目标风险相关的结构、语义及异常特征，不得包含 Secret 或未获准保存的敏感内容。
- 确定性集成测试与真实外部/E2E 验收分开记录；真实数据回放不等于实时服务或完整产品链路已验证。实时凭证、付费 AI、真实制作及生产数据操作仍按已有授权范围执行。若集成测试因具体前置条件无法执行，必须说明阻塞原因、未验证范围与后续验证方式，不得宣称任务已完成验证。
- 测试按风险新增，不按 Task 数量配额新增；测试数量不是质量指标，风险覆盖才是。
- 优先顺序：Domain invariant → contract → integration boundary → high-risk regression → 必要的 unit test。
- 新测试必须保护新的风险、边界、contract 或历史回归点；优先扩展已有高价值测试，必要时参数化等价案例。
- 新 Task 或 Capability 必须获得与风险相称的验证；优先复用已有有效正反集成证据，不按 Task 数量机械新增测试，也不遗漏尚未覆盖的当前业务不变量、Contract 或高风险回归。已有更高价值证据替代后，可删除无独立风险价值的旧测试，不机械补回等价 case。
- 不重复覆盖已由更高价值测试有效保护的行为；不测试 getter、薄包装、字段透传或内部实现细节。
- 定期按 Domain invariant、contract boundary、integration scenario、high-risk regression 复核组合；优先保留能防止跨模块失效的证据，不以文件数或单次耗时设硬目标。
- Bug 修复只有在回归测试能证明风险且不与现有覆盖重复时才新增测试。
- Capability 可以在测试数量不增加的情况下完成；若一次改动新增多项测试，先检查冗余与层级重复。
- 保持核心 Domain、Material/Rights/Gate、revision/hash/identity、Production selection、Approval/fingerprint/idempotency/reconciliation、Lifecycle、Generated Material contracts 及关键 integration 边界的有效保护。
