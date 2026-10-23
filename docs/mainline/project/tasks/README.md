# 活动任务与运行证据

当前唯一执行事项以[状态](../status.md)顶部为准，不由目录名或旧卡中的“下一步”推断。

- [统一任务包](S6_IMPLEMENTATION_PLAN.md)：S6收口来源、S7工作包、依赖与覆盖；保留原编号。
- [S6-14](S6-14_integration-release.md)与[S6-14A](S6-14A_conversation-integration.md)：父任务、实现及具名验证记录。
- [运行记录](runs/)：保留所有轮次与原FAIL，不因整理修改业务判定；规则单独见[E2E规范](../../development/testing.md)。
- [已结案/前期任务](../../history/tasks/)：仅历史追溯，不自动重开。

新任务按[任务衔接](../../development/task-handoff.md)和[原Task模板](../../development/templates/TASK.md)执行。当前代码Bug优先在原活动Task内承接，修复后继续父任务剩余验收。

## V3 同步

- [V3-SYNC-01 · 官方更新同步](V3-SYNC-01_upstream-integration.md)：V3 分支整合与离线检查，不改变 V2 生产任务。

## 待评审父任务

- [PUB-01 · 成片交付引导、确认与发布衔接](PUB-01_acceptance-publication.md)：已授权首批B站开发及离线验收；不部署、不付费或真实投稿。独立任务分支，不替换停止制作断点。


## 已登记的后续顺序

1. [PUB-01 · 成片交付引导、确认与发布衔接](PUB-01_acceptance-publication.md)：现有前序任务。
2. [CTX-01 · 上下文超预算后的发送前压缩](CTX-01_context-compaction.md)：用户指定排在PUB-01之后；[方案](../../architecture/context-compaction-proposal.md)首批Easel侧去重与官方压缩接入已实现并完成离线验收；父功能PARTIAL，关联既有失败及证据见父任务。未部署、未真实压缩、不修改OpenClaw、不升级、不恢复制作。

排序不代表自动开工；当前生产停止决定和各卡授权边界保持有效。
