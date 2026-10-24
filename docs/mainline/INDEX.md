# Easel 当前主线文档

这是我们二开新增文档的唯一入口。**“主线”指当前二开产品与代码基线，不是把 Git 切到官方 main。** 长期分支仍为 easel-v2-rebuild；官方文档保留原路径，本次未改。V2-EXP、S6/S7、Task、ADR 编号继续作为稳定追踪标识，不再作为整套文档的版本入口。

先读[当前状态](project/status.md)，确认 HEAD、Dirty、实际部署、用户授权和当前任务，再按需要阅读下表。当前源码包括未提交改动；代码存在、软件通过、已部署、真实生产通过和 Creator 接受必须分别取证。

| 分类 | 唯一维护内容 | 入口 |
|---|---|---|
| 产品 | 定位、已确认行为、用户旅程 | [定位](product/overview.md) · [需求](product/requirements.md) · [交互](product/interaction.md) |
| 架构 | 实际源码装配、逻辑职责、实施合同、素材边界、长期决定 | [实现全景与二开导读](architecture/overview.md) · [领域职责](architecture/domain.md) · [合同](architecture/contracts.md) · [素材](architecture/materials.md) · [ADR](architecture/decisions/) |
| 使用配置 | 当前运行配置、服务能力与验收边界 | [运行指南](guides/runtime-setup.md) |
| 开发规范 | 开发/Bug统一流程、Git、安全、调试与交接 | [工程规范](development/engineering.md) · [E2E调试](development/testing.md) · [任务衔接](development/task-handoff.md) · [模板](development/templates/) |
| 项目执行 | 当前断点、候选、依赖、具体任务与运行证据 | [状态](project/status.md) · [候选池](project/backlog.md) · [路线图](project/roadmap.md) · [活动任务](project/tasks/README.md) |
| 历史 | 早期研究、阶段设计、已结案任务及整理前快照 | [历史索引](history/INDEX.md) |

需求定义预期，逻辑架构定义职责，合同定义接口和不变量；实现导读描述具名源码快照，运行记录证明具体部署与效果。发现冲突须列出依据和影响，不能以现有代码偷偷改需求，也不能把设计当作已实现。

当前状态只汇总事实；候选池只登记非当期事项；任务包维护依赖和覆盖；Task记录实施；每轮E2E保留首次失败和唯一断点。历史文件不再接受新规则、当前状态或新授权。旧 docs/v2 路径仅作兼容跳转，图片副本只用于保留外部旧引用。

官方资料：[README](../../README.md) · [贡献指南](../../CONTRIBUTING.md) · [Harness](../agent-harnesses.md) · [Prompt栈](../prompt-stack.md) · [技能规范](../SKILL-SPEC.md)。产品创作指令仍在[原工作区](../../agents/workspace/AGENTS.md)，开发规则在[仓库根](../../AGENTS.md)；文件分开不证明运行时加载已隔离。

本轮整理范围、经验保留和检查结果：[迁移审核记录](history/documentation-reorganization-2026-10-23.md)。

<!-- 旧路径章节锚点兼容；现行正文以本页内容为准。 -->
<a id="easel-v2--文档导航"></a>
<a id="冲突与证据"></a>
<a id="按需查阅的依据"></a>
<a id="正式入口与维护职责"></a>

## 本轮实施与验收

- [LIB-01 · 内容库交付物与原生交互收敛](project/tasks/LIB-01_content-library-consistency.md)：代码、离线回归、部署与Web定向复验通过；保留原生文件项目、生产恢复和PUB-01链路，收口按任务记录。

## 待审阅的新需求方案

- [成片确认到发布](architecture/publication-proposal.md)：优先复用原发布能力，列明现状、补齐范围、版本/账号/确认与平台回执；首批B站已授权开发；由[父任务PUB-01](project/tasks/PUB-01_acceptance-publication.md)记录实现、离线验收与后续真实复验；本轮真实B站投稿已获授权并实际提交，平台审核中；公开结果按父任务继续核实。


- [上下文超预算后的发送前压缩](architecture/context-compaction-proposal.md)：任务[CTX-01](project/tasks/CTX-01_context-compaction.md)首批Easel去重与官方压缩接入已实现，新增32项离线用例通过；关联回归有1项开工前已存在的失败，详见父任务。仅覆盖有效历史压力，未承诺当前请求实时预检；已部署并开始Web新片复验，无压力路径及一个真实压力触发官方压缩后原请求完成的样本已验证；不修改OpenClaw、不升级。

- [自然定长与图解呈现衔接](architecture/natural-duration-board-proposal.md)：2026-10-24长尾BGM与图解裁切问题的根因方案；区分已有时长修复、基础图解排版及旧片修订；基础排版已获实施与部署授权，不做复杂动态图解，验收归入PUB-01本轮增量。
