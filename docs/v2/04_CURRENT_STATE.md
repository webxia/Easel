# Easel V2 · 当前状态

> 最后核实：2026-10-18。本文仅记录**当前事实、唯一主线和下一动作**；历史失败与完整运行回执保留在 [S6-14](tasks/S6-14_integration-release.md)，不得以早期 G4 NO_GO 或过期「暂停」记录覆盖现状。

## 当前结论

**S6-14 · PARTIAL（真实视频已跑通；一次无人工恢复的自主直通及 Creator 接受仍未通过）。** S6-01～13 的软件视频主链已接通；[S6-15 素材层完善](tasks/S6-15_material-layer-hardening.md) 已 **CLOSED / COMPLETE**，不再重开为当前前置任务。

已通过正式后端 API、MiniMax M3.1 创作与固定声音、真实素材 Rights 供给、Director 选材和 FFmpeg 产出 **3 部独立 45 秒、1080×1920 H.264/AAC 视频**。各自的 Production Run 均为 `succeeded`、作品 `reviewable`，技术 QC `pass`。这些成功包含研发修复与人工 `/resume`，**不是零卡点自主 E2E PASS**。已按用户决定临时启用 `EASEL_PRODUCTION_QC_MODE=manual`：自动音视频语义 QC 实际 `not_tested`，输出仍保留 `quality_state=needs_fix`，三部作品均未由 Creator 接受，也没有自动发布。

## 唯一执行入口

- **工作区**：`/Users/xgx/Projects/Easel`；当前开发分支 `easel-v2-main-workspace`（盘点前基线 `7ca6806d`，实际 HEAD 以 `git rev-parse HEAD` 为准）；隔离旧工作树只作历史参考，不再运行。
- **服务**：<http://127.0.0.1:7860/>；唯一主工作区 LaunchAgent `com.easel.web`。最近实际检查 `GET /api/production/capabilities` 为 HTTP 200，`backend.reload_required=false`。任何生产源码更改后须先核实并重启，不得让旧 Worker 处理新命令。
- **Git 审查**：[PR #8](https://github.com/webxia/Easel/pull/8) 仍为 Draft，指向历史 `codex/s6-production` 分支，**未包括主工作区 `easel-v2-main-workspace` 最新修复**。后续单独评审分支/PR 汇合方案；未经用户确认不合并上游或受保护分支。
- **真实调用边界**：MiniMax 创作/配音 + 合法外部素材；禁用 `qwen3.8`、不以 DeepSeek 替代；`UNKNOWN` 不盲重发，模型/媒体/用户确认分层记录。

## 已核实的真实作品

| Work ID | 结果 | 当前人工审核 |
|---|---|---|
| `1bc5f5fa797047dabd6e00654ee3675a` | 第一次真实成片；经历 Planning/供料/剪辑研发协助 | `reviewable`；未接受 |
| `f8040a6d153c419aaf1045eadc61bc63` | 第二次实际 API E2E；首次卡在 `voice_timing_exceeds_plan`，修订后完成 | `reviewable`；未接受 |
| `59a27d8fb2f54be0a43507e2f78b9a02` | 第三次实际 API E2E；首次卡在 `invalid_edit`，后端重载并正式恢复完成 | `reviewable`；未接受 |

主工作区最近生产模块软件回归 **460 passed、3 skipped、0 failed**；前端、真实 MP4、技术 QC 和持久回执的结论必须分别读取对应证据，不把软件 PASS 冒充创作品质验收。

## 唯一下一任务

**P0：S6-14 第四轮全新作品、固定代码版本的一次直通 E2E**。启动前冻结 HEAD、授权、输入和观测条件；用正式后端 API 从 Planning → Supply/真实 TTS → Director Edit → FFmpeg Render → 技术 QC → `reviewable`。必须 **0 次 `needs_decision`、0 次人工 `/resume`、0 次运行中研发补丁、0 次重复未知付费请求**，并核实片长、声画轨道、SHA、Rights/credits 和实际回执；不自动执行 Creator 接受或发布。若出现问题，保留该轮 FAIL，修复后另建样本，不回填一次通过。

后续再处理 Creator 对现有三片的真实审片/接受、MiniMax 耗时与成本分析、Git/PR 统一入口；跨题材、画幅、声音、时长等完整矩阵归 [S7](03_ROADMAP.md)。**本次清理阶段不启动新 E2E。**

## 权威参考

- [S6-14 实际运行与正反证据](tasks/S6-14_integration-release.md)
- [S6 任务依赖与验收口径](tasks/S6_IMPLEMENTATION_PLAN.md)
- [V2 需求](01_REQUIREMENTS.md) · [架构](02_ARCHITECTURE.md) · [运行配置](16_RUNTIME_SETUP.md)
- [S6-15 结案和历史 G4 归因](tasks/S6-15_material-layer-hardening.md) · [G4 旧阶段判定](19_MATERIAL_LAYER_G4_ACCEPTANCE.md)
