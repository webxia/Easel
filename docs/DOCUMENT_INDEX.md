# Easel 文档路由器

本索引负责告诉读者“下一步读什么”，不是所有文档的平铺清单。默认上下文应短；历史材料按需打开。

## 默认上下文

每个 Capability Goal 通常只读以下内容：

1. 根目录 [`AGENTS.md`](../AGENTS.md) — 协作、读取与安全规则。
2. [`00_PROJECT.md`](00_PROJECT.md) — 稳定产品目标和职责边界。
3. [`02_CURRENT_STATE.md`](02_CURRENT_STATE.md) — 当前唯一状态汇总。
4. [`03_ROADMAP.md`](03_ROADMAP.md) — 阶段顺序和当前 Workstream。
5. 当前 Workstream 简报；已批准的具体 Task 再读对应 Task 文档。

通常无需默认读取 完整架构、ADR、Task 清单、Acceptance 或 Audit。

## 文档权威与冲突顺序

| 问题 | 权威来源 | 说明 |
|---|---|---|
| 当前产品目标 | [`00_PROJECT.md`](00_PROJECT.md) | 稳定意图，不是实现声明。 |
| 架构边界 | 已接受 ADR + 标记 CURRENT 的架构文档 | 源码不能默默重定义边界。冻结边界变更须明确授权。 |
| 当前实现行为 | 当前源码 + 对应测试 | 代码与架构冲突时记录偏差并停止越界实现。 |
| 当前实现/验证状态 | [`02_CURRENT_STATE.md`](02_CURRENT_STATE.md) | 唯一汇总；状态要有源码或具名验收证据。 |
| 工作顺序 | [`03_ROADMAP.md`](03_ROADMAP.md) | 不替代 Task，也不是代码事实。 |
| 本次实现范围 | 获批 Workstream/Task | 只约束本次工作。 |
| 一次运行的结果 | 相关 Acceptance | 有日期、有范围；旧结果不会自动成为当前 readiness。 |
| 历史方案/审计判断 | Historical/Audit 文档 | 调查历史时按需读取；不作为当前设计或实现状态。 |

同级冲突时优先看较新的当前源码/验证，再看 `02_CURRENT_STATE.md`；设计冲突仍以冻结 ADR/架构为准，并把实际偏差报告出来。不要将“文件存在”“Task COMPLETE”或 fixture 测试通过等同于真实产品验证。

## 按任务路由

| Goal 类型 | 从这里开始 | 仅在需要时追加读取 |
|---|---|---|
| 普通产品/代码 Capability | 默认上下文 + 当前 Workstream 简报 | 该 Goal 的 Task、相关源码和测试。 |
| 创建/视频主链、Preparation、OpenClaw、Hypit | 默认上下文 | [`architecture/easel-video-architecture-v1.md`](architecture/easel-video-architecture-v1.md)、[`decisions/ADR-001-creation-hypit-mainline.md`](decisions/ADR-001-creation-hypit-mainline.md)；触及冻结决策时读对应 ADR。 |
| Material Layer / Provider / Matching / Library | 默认上下文 | 冻结契约 [`architecture/material-layer-v1.3.md`](architecture/material-layer-v1.3.md) 和 [`decisions/ADR-004-material-layer-v1.3-baseline.md`](decisions/ADR-004-material-layer-v1.3-baseline.md)。具体实现以源码和测试为准。 |
| AI 素材生成 | 默认上下文 + [`workstreams/generated-material.md`](workstreams/generated-material.md) | MiniMax Image / Video / preset-voice TTS adapters；范围与验收见对应 Task。 |
| Creation 人工负担/制作闭环 | 默认上下文 + [`自主首版唯一实施 Task`](tasks/creator-autonomous-first-cut-2026-09-30.md) | 关联源码、测试；已并入的低打扰历史方案请查 Git 历史（原 T19），不再保留独立 Task。 |
| 创作耗时/性能 | 默认上下文 + [`创作耗时优化`](tasks/creation-latency-2026-10-02.md) | Delivery Owner、素材供应/观察、编排及审片；以阶段计时与实际调用次数验证，真实端到端时延单独验收。 |
| Runtime / 外部依赖 / 凭证 | 默认上下文 | [`configuration/v1-runtime-and-external-dependencies.md`](configuration/v1-runtime-and-external-dependencies.md) 和所选能力的 readiness Acceptance；严禁读取或输出 secret。 |
| MiniMax M Plan Explore 迁移 | [接入改动清单](configuration/minimax-m-plan-explore-migration-2026-10-06.md) | 待实施方案，包含文字模型、思考回放、媒体套餐及旧作品授权；不代表配置已加载或真实验收通过。 |
| 真实产品/E2E 验证 | 默认上下文 + [T15](tasks/v1c-t15-e2e-readiness.md) | T15 只作历史验收基线；当前范围读取唯一自主首版 Task，再读该条具名 Acceptance、实际 Attempt/Build 证据及所需当前契约。 |
| 文档历史、旧设计或审计追因 | 默认上下文 | 使用下方 Historical 路由；明确说明它是历史证据。 |

## 架构入口

- **当前视频目标架构：** [`architecture/easel-video-architecture-v1.md`](architecture/easel-video-architecture-v1.md)。
- **当前 Material Layer 唯一冻结架构：** [`architecture/material-layer-v1.3.md`](architecture/material-layer-v1.3.md)，由 ADR-004 采纳。
- **正式 Creation + Hypit 边界：** [`decisions/ADR-001-creation-hypit-mainline.md`](decisions/ADR-001-creation-hypit-mainline.md)。
- **Agent 结果处理与产物交接：** [ADR-005](decisions/ADR-005-agent-result-processing.md)；新版五项 pin 已成为唯一新 Attempt 软件主链，旧 Writer 删除及 CUT6 已提交并推送；历史 Attempt 只读，实际新视频媒体 E2E 与 B SourceUnit 迁移仍是独立后续工作。交付证据看 [CUT0–CUT6](tasks/adr005-new-only-cutover-2026-10-10.md)。
- **当前代码路径：** 以源码、测试和 [`02_CURRENT_STATE.md`](02_CURRENT_STATE.md) 为准。
- 其他架构说明已删除；需要新增设计时先更新当前架构入口或创建 ADR，不再堆积独立审计快照。

## 当前 Workstreams 与历史路由

- **当前视频交付**：[自主首版唯一实施 Task](tasks/creator-autonomous-first-cut-2026-09-30.md)。O1 可靠性已完成软件实现、离线测试与受控 Gateway/Web 加载；下一阶段需另行授权，沿唯一 Creation + Hypit 主链制作一条新作品，再做 6/6 及三个新主题的稳定性验收，预算和外部模型权限不自动扩大。- **Planning/模型输出可靠性**：[原合同治理 Task](tasks/planning-material-boundary-matrix-2026-10-06.md)；[Planning Semantic Boundary vNext](tasks/planning-semantic-boundary-vnext-2026-10-07.md) 保留独立冻结语义边界，旧失败按其 Acceptance 查，不把工程样本当正式资格。
- **Material/BGM/视频性能**：[素材与耗时总入口](tasks/creation-latency-2026-10-02.md)、[BGM Task](tasks/creation-bgm-readiness-2026-10-05.md)、[视频流程软件 Task](tasks/creation-video-flow-software-2026-10-05.md)。历史旧作品 R17 的素材恢复不代表完整新视频通过。
- **生成素材**：[Generated Material Workstream](workstreams/generated-material.md)。真实 Provider、TTS、媒体生成和发布都需要原任务明确权限；代码已接入不等于端到端验收通过。
- **保留的历史材料**：[Planning 声音合同修复](tasks/planning-modality-contract-2026-10-06.md)、[运行环境恢复](tasks/creation-runtime-release-2026-10-03.md)、[已完成的素材历史](tasks/creation-latency-completed-2026-10-05.md)、[旧 Creator 验收](acceptance/creator-workspace-e2e-2026-09-30.md)、[T15 历史 E2E 基线](tasks/v1c-t15-e2e-readiness.md)。已并入主 Task 的低打扰 T19、Creator E2E 前修复文档仅从 Git 历史检索，不恢复并列 Task。
- **已完成的新协议清理**：[ADR-005 CUT0–CUT6](tasks/adr005-new-only-cutover-2026-10-10.md) 与 [历史 Hypit 测试精确退役](acceptance/adr005-hypit-native-legacy-test-retirement-2026-10-10.md)。当前不应再按旧版本 Writer 执行。
- 本索引不复制历次模型 Eval 批次及资格结果；具体有效状态看 [Current State](02_CURRENT_STATE.md)，旧执行原件只看日期/版本绑定的 Acceptance。新 Workstream 先在 Roadmap 中确认必要性，再建立文件。
- 新 Workstream 先在 `03_ROADMAP.md` 中登记，确认确有独立上下文后再新增文件。

## 保留与清理规则

- 保留冻结架构/ADR、运行配置、接口规范、当前 Task，以及能定位真实资产、失败、费用或独立合同风险的验收证据。历史验收日期与失败结论不改写。
- 删除仅重复路由、已被替代的空计划、无独立行为证据的文档整理快照；完成任务的独有证据先合并到对应既有验收，再删除任务入口。
- 中文与英文用户指南、上游致谢和维护规范仍有独立读者或维护用途，不因未被本索引默认加载而删除。
- 清理同步修正文档引用；不复制新的平行方案或历史汇总。

## Historical / Acceptance / Audit

- `docs/acceptance/` 保留具名运行、fixture 验收、Provider smoke 和产品 E2E 证据。按能力与日期选择最新相关记录；旧记录用于还原当时事实，不能覆盖新证据。
- 历史审计、旧 ADR、旧 Task、重复验收快照已从工作区移除；Git 历史仍可追溯已提交内容。
- 新状态只更新 `02_CURRENT_STATE.md`；一次运行确需保留证据时，只新增一份具名 Acceptance，不复制整套 Task/Closure 文档。

## 普通 Capability Goal 的最小启动集

```text
AGENTS.md
DOCUMENT_INDEX.md
00_PROJECT.md
02_CURRENT_STATE.md
03_ROADMAP.md
当前 Workstream 简报
本次 Task（仅当 Goal 已指定/获批）
```
