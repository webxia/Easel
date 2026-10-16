# Easel V2 · 当前状态

> **S5 代码复核、架构完善与 AI Coding 任务拆解完成；S6 业务实现尚未开始。** 2026-10-16。

- S4 [需求](01_REQUIREMENTS.md) V2-EXP-001～034 与[差距清单](11_REQUIREMENT_GAP_MAP.md)保持定稿。六维画像就是主人设；一画像多频道，频道与导演多对多。制作过程可观察已纳入024。
- 用户已认可主线、模型/程序职责和[案例衔接](13_PRODUCTION_WALKTHROUGH.md)。[ADR-S5-001](decisions/ADR-S5-001-work-production-boundary.md)仅接受逻辑边界，不扩大为所有技术选型或运行能力已获确认。
- 本轮按用户要求再次对照业务主线 `8eeafb6b`、S5工作起点 `d25b8f83` 和只读V1 `57c8e2ad`；主线与S5的easel/web/skills/tests无业务差异。V1私有历史只用于问题定位，原始日志/配置/画像/素材未入Git。
- [技术建议](14_TECHNOLOGY_SELECTION.md)：沿用React/FastAPI，本机worker + LangGraph有界编排，SQLite + 媒体文件，任务化模型与受控工具，HTTP/SSE事务事件。V1素材M01～M05适配迁入；旧Creation/Delivery/Attempt、阶段预算与历史数据不整体迁入。
- Hypit保留为有条件的编辑/渲染候选；V1机器绑定parser不可直接迁入。S6-09负责具体引擎、版本、许可与能力矩阵决定，FFmpeg/Remotion是明确替代方向。其缺口只影响相应依赖，不阻止其他模块开工。
- [可执行设计](15_IMPLEMENTATION_DESIGN.md)已明确模块/数据/API/状态合同，以及确认前规划、发送时执行所有权、未知结果、服务模式权限、真实视听检查、固定音色、局部修订、双重接受和删除引用。旧读取/删除入口的绕过风险已分派给S6-02，尚未修改代码。
- [S6实施任务包](tasks/S6_IMPLEMENTATION_PLAN.md)含14张卡：每张有依赖、落点、步骤、正反例、命令、交接与未测边界；34项需求各有主责任。原T01～T08映射到相应实施验收，不再作为选型前置。全部S6卡NOT_STARTED，V01～V11针对新主线仍NOT_TESTED。
- [官方资料与研究](12_PRODUCTION_FLOW_RESEARCH.md)已核查；本轮无依赖安装、业务代码改动、服务重启、真实模型/媒体调用或数据迁移。案例仍是纸面推演，不是实际生产授权或验收结果。
- S5工作分支 `codex/s5-architecture` 基于S4 `201bfc04`。本轮核查S4 PR #6和S5草稿PR #7均OPEN；#7基于S4分支。旧提交 `d25b8f83` 必需CI成功、真实安装跳过，不能当作本轮新提交结果；新提交结果以PR具名SHA为准。
- S5阶段开始已Fetch上游 `b29d0d72`，相对V2为3/24，未合入。S6启动时按工程规则再次Fetch/Diff/报告，不自行合入；已确认阶段顺序见INDEX固定流程链接。

验证证据见[S5 Task](tasks/S5_ARCHITECTURE.md)：文档路径、10项文档测试、34/34主责任映射、14卡依赖无环及既有回归入口存在性核验。它们证明实施文档可接手，不证明视频生产已经跑通。

**NEXT_SINGLE_ACTION：后续启动业务实施时执行[S6-01：领域合同、事务存储与迁移](tasks/S6-01_domain-store.md)。从包含本设计的提交开工，沿既定需求和合同实现，不重新访谈或先跑八项验证。**
