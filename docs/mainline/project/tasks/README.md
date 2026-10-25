# 活动任务与运行证据

当前唯一执行事项以[状态](../status.md)顶部为准，不由目录名或旧卡中的“下一步”推断。

- [统一任务包](S6_IMPLEMENTATION_PLAN.md)：S6收口来源、S7工作包、依赖与覆盖；保留原编号。
- [S6-14](S6-14_integration-release.md)与[S6-14A](S6-14A_conversation-integration.md)：父任务、实现及具名验证记录。
- [运行记录](runs/)：保留所有轮次与原FAIL，不因整理修改业务判定；规则单独见[E2E规范](../../development/testing.md)。
- [已结案/前期任务](../../history/tasks/)：仅历史追溯，不自动重开。

新任务按[任务衔接](../../development/task-handoff.md)和[原Task模板](../../development/templates/TASK.md)执行。当前代码Bug优先在原活动Task内承接，修复后继续父任务剩余验收。

## 本轮实施交付

- [LIB-01 · 内容库交付物与 Easel 原生交互收敛](LIB-01_content-library-consistency.md)：本轮收窄范围COMPLETE，离线回归、部署及Web定向复验通过，功能提交ce08475c已推送；不替换PUB-01生产断点。

## 父任务与剩余验收

- [PUB-01 · 成片交付引导、确认与发布衔接](PUB-01_acceptance-publication.md)：本轮原发布中心多平台成片/封面接线已实现、部署并通过不投稿的Web验证；实际各平台上传与封面效果未测，父任务PARTIAL。沿easel-v2-rebuild保留增量及生产断点。


## 已登记的后续顺序

1. [PUB-01 · 成片交付引导、确认与发布衔接](PUB-01_acceptance-publication.md)：现有前序任务。
2. [CTX-01 · 上下文超预算后的发送前压缩](CTX-01_context-compaction.md)：用户指定排在PUB-01之后；[方案](../../architecture/context-compaction-proposal.md)首批Easel侧去重与官方压缩接入已实现并完成离线验收；父功能PARTIAL，关联既有失败及证据见父任务。未部署、未真实压缩、不修改OpenClaw、不升级、不恢复制作。

排序不代表自动开工；当前生产停止决定和各卡授权边界保持有效。

- [SFX-01 · 本地音效检索与导入](SFX-01_local-audio-search.md)：独立修复与素材追加，不恢复视频制作。

## 待评审方案

- [CRE-01 · V2.1版本主任务](CRE-01_creative-context-expression.md)：[完整版本规划](../../architecture/creative-context-expression-proposal.md)；2026-10-25已授权从最新V2创建easel-v2.1-rebuild集中实施，完成后统一调试。已按最新授权清理旧执行分支、核对补齐，最终统一离线2536通过/16跳过；历史API19次真实调用，本轮真实Web已导出含BGM/必需音效的成片，技术及视觉抽样通过、原对话连续播放通过；已按授权快进合并V2/统一部署并复验。完整听感、语义和Creator接受仍人工待审，历史生产断点保留。
