# Easel 文档路由器

本索引负责告诉读者“下一步读什么”，不是所有文档的平铺清单。默认上下文应短；历史材料按需打开。

## 默认上下文

每个 Capability Goal 通常只读以下内容：

1. 根目录 [`AGENTS.md`](../AGENTS.md) — 协作、读取与安全规则。
2. [`00_PROJECT.md`](00_PROJECT.md) — 稳定产品目标和职责边界。
3. [`02_CURRENT_STATE.md`](02_CURRENT_STATE.md) — 当前唯一状态汇总。
4. [`03_ROADMAP.md`](03_ROADMAP.md) — 阶段顺序和当前 Workstream。
5. 当前 Workstream 简报；已批准的具体 Task 再读对应 Task 文档。

通常无需默认读取 `01_ARCHITECTURE.md`、完整架构、ADR、Task 清单、Acceptance 或 Audit。

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
| Creation 人工负担/制作闭环 | 默认上下文 + [`自主首版唯一实施 Task`](tasks/creator-autonomous-first-cut-2026-09-30.md) | 关联源码、测试；[`T19`](tasks/v1c-t19-low-friction-creation.md) 仅作为已并入的历史基线。 |
| Runtime / 外部依赖 / 凭证 | 默认上下文 | [`configuration/v1-runtime-and-external-dependencies.md`](configuration/v1-runtime-and-external-dependencies.md) 和所选能力的 readiness Acceptance；严禁读取或输出 secret。 |
| 真实产品/E2E 验证 | 默认上下文 + [T15](tasks/v1c-t15-e2e-readiness.md) | 只读该条具名 Acceptance、实际 Attempt/Build 证据及所需当前契约。 |
| 文档历史、旧设计或审计追因 | 默认上下文 | 使用下方 Historical 路由；明确说明它是历史证据。 |

## 架构入口

- **当前视频目标架构：** [`architecture/easel-video-architecture-v1.md`](architecture/easel-video-architecture-v1.md)。
- **当前 Material Layer 唯一冻结架构：** [`architecture/material-layer-v1.3.md`](architecture/material-layer-v1.3.md)，由 ADR-004 采纳。
- **正式 Creation + Hypit 边界：** [`decisions/ADR-001-creation-hypit-mainline.md`](decisions/ADR-001-creation-hypit-mainline.md)。
- **当前代码路径：** 以源码、测试和 [`02_CURRENT_STATE.md`](02_CURRENT_STATE.md) 为准。
- 其他架构说明已删除；需要新增设计时先更新当前架构入口或创建 ADR，不再堆积独立审计快照。

## Workstreams 与模板

- 当前唯一实施方案：[`tasks/creator-autonomous-first-cut-2026-09-30.md`](tasks/creator-autonomous-first-cut-2026-09-30.md)。用户已批准实施自主首版与 Director 全链执行；已有六段主链基础复用；C 镜头替代、B 观察复用、D 例外组合接受及 E 体验/全链局部回放已完成确定性软件收尾；现阶段等待用户另行启动真人验收。
- 历史已完成的素材阶段恢复：[`tasks/creator-material-recovery-2026-09-30.md`](tasks/creator-material-recovery-2026-09-30.md)。
- 历史工作区软件验收：[`tasks/creator-workspace-2026-09-30.md`](tasks/creator-workspace-2026-09-30.md)。

- 当前能力边界：[`workstreams/generated-material.md`](workstreams/generated-material.md)。MiniMax 图片、视频和预置音色语音生成均已接入代码；生成素材的 Creation/Production 闭环仍需单独验收。
- 当前 E2E Task：[`tasks/v1c-t15-e2e-readiness.md`](tasks/v1c-t15-e2e-readiness.md)。
- 已并入唯一 Task 的低打扰历史基线：[`tasks/v1c-t19-low-friction-creation.md`](tasks/v1c-t19-low-friction-creation.md)。
- 历史 Creator E2E 前修复基线：[`tasks/creator-e2e-repair-2026-09-30.md`](tasks/creator-e2e-repair-2026-09-30.md)。
- 已完成的 Material 基础能力不再保留单独 Workstream 文档。
- 新 Workstream 先在 `03_ROADMAP.md` 中登记，确认确有独立上下文后再新增文件。

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
