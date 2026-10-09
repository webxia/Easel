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
- 测试必须确定，不调用付费 AI、不依赖实时凭证；真实外部验收单独记录。
- 所有面向用户的说明使用中文。Secret 只放本机受保护配置或其所有者的认证存储；不得进入 Git、文档、日志、数据库、Attempt 产物或聊天。

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

当前工作优先级：

```text
Material Layer 稳定
→ MATERIAL_READY
→ 完整视频 E2E 稳定出片
→ Creator 定位
→ 个人音色 / 拍摄语言 / BGM / 转场
```

此处只约束工作方向；具体阶段、实现状态和执行范围仍以 `docs/02_CURRENT_STATE.md`、`docs/03_ROADMAP.md` 及获批 Task 为准，不因上述顺序自动启动后续阶段。后置的个人风格能力不排除当前 Task 已要求的 BGM 素材供给与准入。

- Main 负责 Material Layer 实施、调试和验证。
- Scout 按需追 Material / Planning / Delivery / Rights / Match / Readiness 等真实调用链。
- Astra 仅用于结构性改动、同一根因连续两次修复失败，或重要阶段冻结 / 正式 E2E 前复核。
- 不因当前问题扩展到长视频、个人风格系统或无关平台建设。

默认工作顺序：**先找证据 → Main 判断 → 最小修改 → 局部验证 → 必要时 Astra 复核**。涉及跨模块 Contract、责任边界或核心架构修改时，在实施前复核；不以末尾复核替代前置判断。不要遇到问题就立即大改架构，或增加更多 Agent / Gate / Prompt。

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

标准同步流程：

```bash
git fetch upstream
git switch main
git merge --ff-only upstream/main
git push origin main

git switch easel-studio
git merge main
# 解决冲突并完成必要验证后
git push origin easel-studio
```

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
- 新 Task 和新 Capability 默认不增加测试；不要求“一 Task 一测试”或“一模块一文件”。完成替代性更高的场景后，可删除已无独立风险价值的旧测试，不机械补回等价 case。
- 不重复覆盖已由更高价值测试有效保护的行为；不测试 getter、薄包装、字段透传或内部实现细节。
- 定期按 Domain invariant、contract boundary、integration scenario、high-risk regression 复核组合；优先保留能防止跨模块失效的证据，不以文件数或单次耗时设硬目标。
- Bug 修复只有在回归测试能证明风险且不与现有覆盖重复时才新增测试。
- Capability 可以在测试数量不增加的情况下完成；若一次改动新增多项测试，先检查冗余与层级重复。
- 保持核心 Domain、Material/Rights/Gate、revision/hash/identity、Production selection、Approval/fingerprint/idempotency/reconciliation、Lifecycle、Generated Material contracts 及关键 integration 边界的有效保护。
