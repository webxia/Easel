> **HISTORICAL — 文档整理前完整快照（2026-10-23）。不作为当前操作入口。**

# Easel V2 · 文档导航

状态：**CURRENT — V2 研发入口**。先读[当前状态](../../project/status.md)，核对活动工作树、分支和唯一下一事项；实施时再读[任务包共同约定](../../project/tasks/S6_IMPLEMENTATION_PLAN.md#2-每张卡开始与完成的共同约定)与当前任务卡。按需定位相关合同、源码和测试，不默认全文加载历史材料。

## 正式入口与维护职责

| 要回答的问题 | 唯一维护位置 |
|---|---|
| S6如何收口，S7全部任务怎样统一落地 | [统一实施规划§4～§10](../../project/tasks/S6_IMPLEMENTATION_PLAN.md#s6-closeout)：S6全部任务与遗留、17项候选归并、八个工作包、架构落点/复杂度/依赖/验收、开源与上游取舍；全部工作包软件交付与待验收边界见[实施§10.2](../../project/tasks/S6_IMPLEMENTATION_PLAN.md#s7-implementation)；独立E2E晚上继续，生产未恢复 |
| 产品目标是什么 | [愿景](../../product/overview.md) |
| 已确认的行为和验收要求是什么 | [S4 需求](../../product/requirements.md)：V2-EXP-001～034；确认不等于实现 |
| Easel 整体如何运行、后续二开从哪里入手 | [整体实现架构与二开导读](../../architecture/overview.md)：普通底座与 V2 全景、启动/会话/生产链路、数据权威、恢复与权限、模块及测试落点；基于 2026-10-23 HEAD＋Dirty 静态源码，不替代部署验收 |
| 模型、程序、用户分别负责什么 | [逻辑架构](../../architecture/domain.md)及[已接受的逻辑边界 ADR](../../architecture/decisions/ADR-S5-001-work-production-boundary.md) |
| 为什么推荐该技术，有什么替代和风险 | [技术选型](14_TECHNOLOGY_SELECTION.md)：推荐与条件未决项，不冒充全部已获批准 |
| Coding 应遵守哪些数据、状态、API 和执行规则 | [实施合同](../../architecture/contracts.md)：唯一实施合同；设计条款与已具名落地项分开，当前结果以Task/证据为准 |
| 本期通用去AI味如何结合导演 | [需求补充](../../product/requirements.md#natural-expression)、[架构职责](../../architecture/domain.md#41-通用自然表达与导演的结合2026-10-22)、[实施合同 §6.1](../../architecture/contracts.md#natural-expression-design)：单一通用规则源融入既有任务，保留导演差异与冻结依据；SOFTWARE_PASS（发布快照864 passed / 5 skipped），离线证据见合同 §6.1.7；DEPLOY_PASS；发布后[Codex E2E](../../project/tasks/runs/2026-10-22-web-e2e-05.md)已返回真实待修预览，Creator口播未接受；确定性修复生产回归871 passed / 5 skipped、前端105项PASS，视频清晰度整体留S7 |
| 如何回到 Easel 对话式视频创作、前后端怎样衔接 | [交互设计与图](20_CONVERSATIONAL_INTERACTION.md)：参考 Easel 管线、含 OpenClaw 插件/受限运行配置研究、[完成与回写闭环](20_CONVERSATIONAL_INTERACTION.md#10-创作结束后的闭环与回写2026-10-18补充设计)、[导演/频道入口与整条闭环](20_CONVERSATIONAL_INTERACTION.md#11-导演频道入口与统一创作闭环)、[创建流程](diagrams/s6-14a-creation-flows.svg)及[交互分镜](diagrams/s6-14a-interaction-storyboard.svg)的设计提案，整体文档审查见[§12](20_CONVERSATIONAL_INTERACTION.md#12-本次整体方案审查与修正2026-10-18)；[S6-14A](../../project/tasks/S6-14A_conversation-integration.md) 登记新增交互任务；A1隔离验证保留；A2～A4已实现并通过具名软件/隔离Web验证，A5完整隔离流程与28项离线判据通过；[A6对话内三条管线入口](20_CONVERSATIONAL_INTERACTION.md#15-对话管线区域的统一入口用户澄清)及6项隔离入口验证完成；A7正式桥接/schema4迁移及真实Web频道→导演→完整生产→同对话审片回写通过；A8已通过真实Web局部修复画面动作、字幕对比及跨镜头合成，完整音轨复用不变；源片清晰度/夜景氛围限度与Creator待审独立记录 |
| 任务顺序、依赖、覆盖关系与验收分工是什么 | [实施任务包](../../project/tasks/S6_IMPLEMENTATION_PLAN.md)及各卡；每张卡维护自身执行结果 |
| S6-15 素材层完善完成了什么 | [S6-15 结案任务](../tasks/S6-15_material-layer-hardening.md)：G0～G4 历史正反证据；**CLOSED/COMPLETE，不是当前开放前置** |
| 五类素材有哪些实证缺口、如何补齐 | [素材层审计](17_MATERIAL_LAYER_AUDIT.md)固定事实；[素材层架构与选型](../../architecture/materials.md)定义内部方案，执行结果仍在 S6-15 |
| G4 当时为何 NO_GO、如何回接 S6-14 | [G4 历史审查与判定](19_MATERIAL_LAYER_G4_ACCEPTANCE.md)：保留当时的 NO_GO 和恢复证据，不能当作当前 S6-14 未启动或仍暂停的状态 |
| S1～S7 如何划分 | [路线图](../../project/roadmap.md)；任务卡编号不等于阶段编号 |
| 正在做什么、全部任务如何归类、从哪个版本接手 | [当前状态](../../project/status.md)；统一任务/待办/历史/候选边界，主画像映射仅留本机 |
| 如何配置并体验新视频制作 | [S6 运行配置](16_RUNTIME_SETUP.md)：启动、服务协议、字体和真实验收边界 |
| 如何运行检查、交接和操作 Git | [工程说明](../../development/engineering.md)、[官方 README](../../../../README.md)、[贡献指南](../../../../CONTRIBUTING.md) |
| 开发、调试、Bug 修复如何统一运行及为何这样设计 | **现行执行**：[统一开发规范](../../development/engineering.md)、[调试/E2E 规范](../../development/testing.md)、[Task 模板](../../development/templates/TASK.md)；**唯一设计依据**：[已批准整合基线](../research/development-debugging-task-integration-2026-10-23.md)。Bug 在原 Task 按开发规范修复并返回原验收，不依赖外部控制器 |
| 真实 Web E2E、调试 Gate 和 UNKNOWN 边界在哪里 | [现行 Web E2E 规范](../../development/testing.md)：G0～G6、真实业务恢复、调试与固定版本独立验收；当前具体范围以实施任务包为准 |

产品内创作 Agent 使用[创作指令](../../../../agents/workspace/AGENTS.md)，仓库根 `AGENTS.md` 约束研发任务。实际指令加载边界须通过运行证据核验，不能仅凭目录分开宣称隔离完成。

**当前状态唯一入口**：[当前状态](../../project/status.md)维护最新授权、部署与停止点；[S6-14A](../../project/tasks/S6-14A_conversation-integration.md#natural-expression-implementation)维护本期实现和验证证据。历史轮次保留原判定，不根据旧“待部署/下一步”自动重派任务。

## 按需查阅的依据

- [差距与复用清单](11_REQUIREMENT_GAP_MAP.md)：官方 Easel 沿用、V1 适配迁入与新增依据。
- [90 秒完整案例](13_PRODUCTION_WALKTHROUGH.md)：已认可的输入/输出、模型决策与失败衔接；纸面推演不等于真实运行。
- [主线研究](12_PRODUCTION_FLOW_RESEARCH.md)：官方资料、固定源码证据与早期实验设想，不定义当前排程。
- [T01～T08 测试来源](../tasks/S5_VALIDATION_PLAN.md)：保留场景和判据；实施分工以任务包为准，不是选型前置。
- [S5 Task](../tasks/S5_ARCHITECTURE.md)：本次评估、文档整理与验证证据；历史执行范围不限制后续已授权任务。
- [Task 模板](../../development/templates/TASK.md) / [ADR 模板](../../development/templates/ADR.md)：仅在需要跨会话交接或重大设计决定时使用，不预建空记录。

## 冲突与证据

产品行为以已确认需求和用户最新明确决定为准；长期职责以已接受设计为准；本次操作范围来自用户授权及活动 Task。源码、测试和运行产物只证明对应版本的实际行为，不能静默改写需求或授权。发现冲突先记录要求、证据与影响，再修实现或明确修订决定。

同一规则只在上表指定位置维护，其他文档链接引用。当前状态只汇总具名证据；历史过程留在 Task/PR/Git。软件检查、真实生产、自主完成和 Creator 接受分别记录，不能互相代替。
