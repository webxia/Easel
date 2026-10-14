# ADR-001 Creation + Hypit Mainline

Status: Accepted

2026-10-11 用户批准定点修订：与[唯一 New-Only → Web E2E 主方案](../architecture/web-backend-new-only-cutover-plan-2026-10-11.md)对齐。本次只修订正式决策，不表示代码、安装 Skill 或运行服务已完成切换；实施授权与 U1 收尾见[唯一 Creator Task](../tasks/creator-autonomous-first-cut-2026-09-30.md)。

## Context

Easel has existing topic-to-video Skills and a newer Creation + Hypit integration. Multiple paths being treated as equal mainlines makes ownership, state, and delivery expectations unclear.

## Decision

Creation + Hypit 是唯一正式视频生产主线，Delivery 是唯一生产执行 Owner。Web、Chat、CLI、Skill 和内部入口均不得编排第二条视频生产链。

`auto-short-video`、`video-production` 及其他旧视频 Producer、Writer、Parser、Skill、执行协议和恢复分支须物理退役，不得继续参与新视频生产，不以 410、条件分支、feature flag 或兼容适配器保留可执行双轨。当前主链所需的通用底层工具与 Hypit 原生语法能力不因名称相似而退役。

历史 Creation/Attempt 只保留不可变原件和只读观察，不升级、恢复或重新解释旧业务结果。历史 UNKNOWN 仅可按原 Operation 身份进行非业务解释的终态观察与费用对账；不得重派模型、Provider 或 Build，不重复扣费，不清零预算或释放未知占额。

## Consequences

新视频工作必须归入 Creation 生命周期和 Hypit 职责边界，按唯一主方案 R1–R6、U0–U6 实施和验收。ADR-004、Material Layer V1.3、Director 权限、Rights、费用及现有状态机边界不变；原件、媒体、SHA、失败和历史账单保全不等于保留旧执行能力。

本决策不声称代码已完成 New-Only、900 秒能力已验证或主链已完整 E2E 通过。U2 编码、运行配置、部署/重启、真实调用和发布仍须分别获得明确授权。
