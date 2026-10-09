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
| Creation 人工负担/制作闭环 | 默认上下文 + [`自主首版唯一实施 Task`](tasks/creator-autonomous-first-cut-2026-09-30.md) | 关联源码、测试；[`T19`](tasks/v1c-t19-low-friction-creation.md) 仅作为已并入的历史基线。 |
| 创作耗时/性能 | 默认上下文 + [`创作耗时优化`](tasks/creation-latency-2026-10-02.md) | Delivery Owner、素材供应/观察、编排及审片；以阶段计时与实际调用次数验证，真实端到端时延单独验收。 |
| Runtime / 外部依赖 / 凭证 | 默认上下文 | [`configuration/v1-runtime-and-external-dependencies.md`](configuration/v1-runtime-and-external-dependencies.md) 和所选能力的 readiness Acceptance；严禁读取或输出 secret。 |
| MiniMax M Plan Explore 迁移 | [接入改动清单](configuration/minimax-m-plan-explore-migration-2026-10-06.md) | 待实施方案，包含文字模型、思考回放、媒体套餐及旧作品授权；不代表配置已加载或真实验收通过。 |
| 真实产品/E2E 验证 | 默认上下文 + [T15](tasks/v1c-t15-e2e-readiness.md) | T15 只作历史验收基线；当前范围读取唯一自主首版 Task，再读该条具名 Acceptance、实际 Attempt/Build 证据及所需当前契约。 |
| 文档历史、旧设计或审计追因 | 默认上下文 | 使用下方 Historical 路由；明确说明它是历史证据。 |

## 架构入口

- **当前视频目标架构：** [`architecture/easel-video-architecture-v1.md`](architecture/easel-video-architecture-v1.md)。
- **当前 Material Layer 唯一冻结架构：** [`architecture/material-layer-v1.3.md`](architecture/material-layer-v1.3.md)，由 ADR-004 采纳。
- **正式 Creation + Hypit 边界：** [`decisions/ADR-001-creation-hypit-mainline.md`](decisions/ADR-001-creation-hypit-mainline.md)。
- **Agent 结果处理与产物交接：** [ADR-005](decisions/ADR-005-agent-result-processing.md)。本轮具名显式 profile 已实施并通过软件验收；实际范围、独立审查和默认 rollout/B 迁移等后续工作见第 27.6 节与 Current State，不增加首条工程视频前置。
- **当前代码路径：** 以源码、测试和 [`02_CURRENT_STATE.md`](02_CURRENT_STATE.md) 为准。
- 其他架构说明已删除；需要新增设计时先更新当前架构入口或创建 ADR，不再堆积独立审计快照。

## Workstreams 与模板

- 当前连续Goal：[自主首版唯一 Task — 三个新主题连续自主视频交付](tasks/creator-autonomous-first-cut-2026-09-30.md#连续自主出片-goal2026-10-08-用户追加授权进行中)。用户已授权必要修复、Runtime接入及真实新作品验证；累计¥30限图片/预置旁白，文字仅套餐。先补Planning接入再走唯一Delivery完整视频链，最终同固定版3作品零工程介入；旧批次FAIL及范围记录保留，具体状态看Current State。

- Planning vNext 当前获批实施入口：[Planning Semantic Boundary vNext](tasks/planning-semantic-boundary-vnext-2026-10-07.md)。冻结设计及一次 Astra CONTINUE，连续执行 S1–S5 与最多两轮有界 Development Eval；沿用既有矩阵及验收入口，Formal R4 保持 PAUSED，禁止 Supply/媒体生成/TTS/Build。设计 PASS 不代表软件或真实评测 PASS。
- 当前优先：[模型输出可靠性统一治理实施方案](tasks/planning-material-boundary-matrix-2026-10-06.md)。沿用原Task，复用25行矩阵，同时治理确认至Material入口并解决F1/G1/G2；A–D软件合同25 PASS及现场保护FAIL保留；R0–R3单一语义源已实施，run-017为53 PASS/全量787 PASS，R0–R3已固定99b3并加载，R4首项因评测器异步观察分类缺口FAIL停止，Planning尚未启动；评测工具异步前置回归新增66PASS/4FAIL，发现首次内存/冻结重载键序造成原A请求不稳定，Astra STOP；新真实批未启动。后续a7f7稳定请求软件70PASS/805PASS并另批真实执行；batch02首项A policy类型错、repair目标缺少绝对绑定而FAIL，31项未执行，Astra STOP。输出目标修复63da1b00经72PASS/810PASS后新batch03仍首项FAIL，真实repair正确写入，但A Schema/constraints/continuity与Compiler不一致，31项未执行，Astra STOP。A输入对齐b819d287已固定加载（80矩阵PASS/818全量PASS），batch04首次A/B/Truth合同通过但独立后期语义FAIL，后31项停止；引用关系修正59bd7d85经88矩阵PASS/826全量PASS后，batch05首项合同PASS但叙事义务wrongkind语义FAIL/STOP、31未执行；同一Task§13.12/13.13审核对象说明修正经96矩阵PASS/834全量PASS后固定0b176a2a并安全加载，batch06首项因素材属性与后期用途混合wrongkind语义FAIL/STOP，31未执行；§13.15/13.16关系治理经103矩阵PASS/841全量PASS后固定7685953c安全加载，batch07前2PASS/第3结构合同FAIL/STOP、后29未执行；§13.18/13.19完整B/repair输出Schema修复后batch08首项结构合法但持续unresolved正式FAIL；§13.21/13.22只明确源条件与成片使用的审核对象，保留function粒度与旧版本，经115矩阵/853全量PASS，固定加载后batch09首项正式合同PASS，但新增屏幕/手部无来源hard而独立语义FAIL/STOP；同一Task§13.25–13.28完成@7来源资格/control统一治理，run042135PASS/873全量PASS并AstraCONTINUE，固定3be0ff94/sourcebf527、安全加载后另起32项batch10真实Eval，最新成绩查CurrentState；全部旧FAIL保留，Smoke/E2E后置。[唯一验收](acceptance/planning-material-boundary-matrix-2026-10-06.md)保留原22 PASS/1 FAIL/2 GAP及后续完整结果，不重建平行治理与测试体系。
- 第二轮已完成的软件修复：[Planning 声音参数与视觉合同边界](tasks/planning-modality-contract-2026-10-06.md)；不恢复失败作品，也不凭旧软件结论自动启动真实E2E。
- 当前 Workstream 总入口：[素材层可靠供给与耗时优化：总顺序与汇合](tasks/creation-latency-2026-10-02.md)。按用户要求分为两个独立执行目标，使用独立 worktree；真实视频仍在 MATERIAL_READY 和软件整合之后启动。
- BGM 窗口实施入口：[BGM 验证与原作品 MATERIAL_READY](tasks/creation-bgm-readiness-2026-10-05.md)。G0 首轮及一项辅助比较未通过（[能力证据](acceptance/creation-latency-v06-bgm-calibration-2026-10-05.md)），先重新验证声音路径，再按条件执行 G1/G2。
- 视频窗口实施入口：[视频制作流程的软件优化](tasks/creation-video-flow-software-2026-10-05.md)。并行核对和修复具名剩余软件缺口，不执行真实网关、素材采购、Authoring 或 Build。
- 已完成的具名故障修复：[`创作临时网关环境释放`](tasks/creation-runtime-release-2026-10-03.md)，处理已确认终态后的 MCP 释放与中断接续，并按用户要求删除失败作品数据；不构成三步耗时方案实施批准。
- 按需查阅的历史归档：[已完成实施与历史证据](tasks/creation-latency-completed-2026-10-05.md)。保存 v0.4/v0.5 软件实施、失败与 PARTIAL 运行记录、已完成的 GitHub 调研及取舍；不作为当前待办或启动授权。具名真实证据仍见原 Acceptance，历史结果不改写。
- 自主首版验收基线：[`tasks/creator-autonomous-first-cut-2026-09-30.md`](tasks/creator-autonomous-first-cut-2026-09-30.md)。用户已批准实施自主首版与 Director 全链执行；已有六段主链基础复用；C 镜头替代、B 观察复用、D 例外组合接受及 E 体验/全链局部回放已完成确定性软件收尾；现阶段等待用户另行启动真人验收。
- 历史已完成的素材阶段恢复：[`tasks/creator-material-recovery-2026-09-30.md`](tasks/creator-material-recovery-2026-09-30.md)。
- 历史工作区软件及真实验收：[`acceptance/creator-workspace-e2e-2026-09-30.md`](acceptance/creator-workspace-e2e-2026-09-30.md)，前置软件摘要已合并，不保留独立完成任务入口。

- 当前能力边界：[`workstreams/generated-material.md`](workstreams/generated-material.md)。MiniMax 图片、视频和预置音色语音生成均已接入代码；生成素材的 Creation/Production 闭环仍需单独验收。
- 历史 E2E 验收基线（当前真人验收范围以唯一自主首版 Task 为准）：[`tasks/v1c-t15-e2e-readiness.md`](tasks/v1c-t15-e2e-readiness.md)。
- 已并入唯一 Task 的低打扰历史基线：[`tasks/v1c-t19-low-friction-creation.md`](tasks/v1c-t19-low-friction-creation.md)。
- 历史 Creator E2E 前修复基线：[`tasks/creator-e2e-repair-2026-09-30.md`](tasks/creator-e2e-repair-2026-09-30.md)。
- 已完成的 Material 基础能力不再保留单独 Workstream 文档。
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
