# Easel V2 · 文档导航

状态：**CURRENT — V2 研发入口**。先读[当前状态](04_CURRENT_STATE.md)，核对活动工作树、分支和唯一下一事项；实施时再读[任务包共同约定](tasks/S6_IMPLEMENTATION_PLAN.md#2-每张卡开始与完成的共同约定)与当前任务卡。按需定位相关合同、源码和测试，不默认全文加载历史材料。

## 正式入口与维护职责

| 要回答的问题 | 唯一维护位置 |
|---|---|
| 产品目标是什么 | [愿景](00_VISION.md) |
| 已确认的行为和验收要求是什么 | [S4 需求](01_REQUIREMENTS.md)：V2-EXP-001～034；确认不等于实现 |
| 模型、程序、用户分别负责什么 | [逻辑架构](02_ARCHITECTURE.md)及[已接受的逻辑边界 ADR](decisions/ADR-S5-001-work-production-boundary.md) |
| 为什么推荐该技术，有什么替代和风险 | [技术选型](14_TECHNOLOGY_SELECTION.md)：推荐与条件未决项，不冒充全部已获批准 |
| Coding 应遵守哪些数据、状态、API 和执行规则 | [实施合同](15_IMPLEMENTATION_DESIGN.md)：待实现的唯一合同，不是现有能力声明 |
| 如何回到 Easel 对话式视频创作、前后端怎样衔接 | [交互设计与图](20_CONVERSATIONAL_INTERACTION.md)：参考 Easel 管线、含 OpenClaw 插件/受限运行配置研究、[完成与回写闭环](20_CONVERSATIONAL_INTERACTION.md#10-创作结束后的闭环与回写2026-10-18补充设计)、[导演/频道入口与整条闭环](20_CONVERSATIONAL_INTERACTION.md#11-导演频道入口与统一创作闭环)、[创建流程](diagrams/s6-14a-creation-flows.svg)及[交互分镜](diagrams/s6-14a-interaction-storyboard.svg)的设计提案，整体文档审查见[§12](20_CONVERSATIONAL_INTERACTION.md#12-本次整体方案审查与修正2026-10-18)；[S6-14A](tasks/S6-14A_conversation-integration.md) 登记新增交互任务；A1隔离验证保留；A2～A4已实现并通过具名软件/隔离Web验证，A5完整隔离流程与28项离线判据通过；正式部署与真实模型/媒体验收未执行 |
| 任务顺序、依赖、覆盖关系与验收分工是什么 | [实施任务包](tasks/S6_IMPLEMENTATION_PLAN.md)及各卡；每张卡维护自身执行结果 |
| S6-15 素材层完善完成了什么 | [S6-15 结案任务](tasks/S6-15_material-layer-hardening.md)：G0～G4 历史正反证据；**CLOSED/COMPLETE，不是当前开放前置** |
| 五类素材有哪些实证缺口、如何补齐 | [素材层审计](17_MATERIAL_LAYER_AUDIT.md)固定事实；[素材层架构与选型](18_MATERIAL_LAYER_ARCHITECTURE.md)定义内部方案，执行结果仍在 S6-15 |
| G4 当时为何 NO_GO、如何回接 S6-14 | [G4 历史审查与判定](19_MATERIAL_LAYER_G4_ACCEPTANCE.md)：保留当时的 NO_GO 和恢复证据，不能当作当前 S6-14 未启动或仍暂停的状态 |
| S1～S7 如何划分 | [路线图](03_ROADMAP.md)；任务卡编号不等于阶段编号 |
| 正在做什么，从哪个版本接手 | [当前状态](04_CURRENT_STATE.md)；只汇总并指向证据 |
| 如何配置并体验新视频制作 | [S6 运行配置](16_RUNTIME_SETUP.md)：启动、服务协议、字体和真实验收边界 |
| 如何运行检查、交接和操作 Git | [工程说明](05_ENGINEERING.md)、[官方 README](../../README.md)、[贡献指南](../../CONTRIBUTING.md) |

产品内创作 Agent 使用[创作指令](../../agents/workspace/AGENTS.md)，仓库根 `AGENTS.md` 约束研发任务。实际指令加载边界须通过运行证据核验，不能仅凭目录分开宣称隔离完成。

## 按需查阅的依据

- [差距与复用清单](11_REQUIREMENT_GAP_MAP.md)：官方 Easel 沿用、V1 适配迁入与新增依据。
- [90 秒完整案例](13_PRODUCTION_WALKTHROUGH.md)：已认可的输入/输出、模型决策与失败衔接；纸面推演不等于真实运行。
- [主线研究](12_PRODUCTION_FLOW_RESEARCH.md)：官方资料、固定源码证据与早期实验设想，不定义当前排程。
- [T01～T08 测试来源](tasks/S5_VALIDATION_PLAN.md)：保留场景和判据；实施分工以任务包为准，不是选型前置。
- [S5 Task](tasks/S5_ARCHITECTURE.md)：本次评估、文档整理与验证证据；历史执行范围不限制后续已授权任务。
- [Task 模板](templates/TASK.md) / [ADR 模板](templates/ADR.md)：仅在需要跨会话交接或重大设计决定时使用，不预建空记录。

## 冲突与证据

产品行为以已确认需求和用户最新明确决定为准；长期职责以已接受设计为准；本次操作范围来自用户授权及活动 Task。源码、测试和运行产物只证明对应版本的实际行为，不能静默改写需求或授权。发现冲突先记录要求、证据与影响，再修实现或明确修订决定。

同一规则只在上表指定位置维护，其他文档链接引用。当前状态只汇总具名证据；历史过程留在 Task/PR/Git。软件检查、真实生产、自主完成和 Creator 接受分别记录，不能互相代替。
