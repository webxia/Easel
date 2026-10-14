# Easel Roadmap

> **当前有效进度（2026-10-14）：**已批准 New-Only U0–U6 唯一标准；**U2_CANDIDATE_READY（2026-10-12 原指纹）/ U3-S=PASS / U4=BLOCKED / U3-L 尚未正式取得 900 秒资格 / U5-U6 未执行 / RELEASE_NOT_AUTHORIZED**。当前 Git 已在 `990feb43` 本地提交，受测 U2 候选仍须重新核对加载指纹；这不是新的 U4/U5 验收或授权。
>
> **唯一业务下一动作：**在单独授权和安全条件满足后继续 **U4 无副作用 Web 页面、Runtime 同版、Rights/预算/UNKNOWN 准入**；成功后才能启动 U5 单条真实 Web Creation 短片 Debug。Planning 随 U5 Web Delivery 执行，独立十样本稳定性批次不构成 U5 额外前置。U3-L 可与合规短片 Debug 并行，U6 必须等待同版 U3-L PASS。实际阶段事实见[Current State](02_CURRENT_STATE.md)，原运行证据见[E2E 账本](acceptance/easel-v1-web-real-e2e-2026-10-10.md)。

## 当前已批准的唯一实施顺序（U2 候选不等于 Release）

依次执行：U0 → U1 → U2 → U3-S 与 U4 → U5（可并行 U3-L）→ U3-L 同版 PASS 后 U6。准入、授权及 STOP 条件只按[唯一 New-Only 主方案](architecture/web-backend-new-only-cutover-plan-2026-10-11.md)第 8 章，不在本页自设第二套标准。
## 2026-10-11 历史阶段安排（以下是旧阶段语境，不再独立调度）

此前 ADR-005、OpenClaw O1、P0-A/P0-B、P1/P2/P3 的阶段叙述现统一映射到[唯一 New-Only 第 8 章](architecture/web-backend-new-only-cutover-plan-2026-10-11.md) U0–U6。历史实施事实不改写，旧报错和原媒体仍在[E2E 账本](acceptance/easel-v1-web-real-e2e-2026-10-10.md)及整理前完整文档备份中；不要从旧阶段清单再启动 Planning 压力测试、重试原 Attempt 或恢复旧生产入口。U3-S 已通过软件阶段，U4 是尚未通过的真实 Web 前置，U3-L 为 U6 长片资格。
## 不可改变的边界

- 正式 V1 目标流：Creator/Director/Creative Mode → New-Only Proposal @4 正式确认 → Preparation/Handoff → Planning/Truth → Material V1.3 的 `MaterialPlan → Material Supply → MaterialBundle → MaterialReadiness → MATERIAL_READY` → Native Authoring/Check → Hypit Build/Export → Technical QC/System Quality READY → 人工 Review/Selection/Content Library；新生产不恢复旧 V0.1 执行合同，Creator/Director/Creative Mode、Rights、费用/UNKNOWN 边界不变，且不自动发布。**这是已批准目标，不是当前源码已经实现的声明。**
- 历史 R17 的 **9/9 `MATERIAL_READY`** 仅是旧作品素材恢复，不等于视频交付；广泛 BGM 能力留出/旧 R4 等 FAIL、UNKNOWN 和预算不重新计数。
- 原始规划路线、两窗口软件/BGM任务与连续出片的历史实施细节保存在 [唯一自主出片 Task](tasks/creator-autonomous-first-cut-2026-09-30.md)、[Planning 治理 Task](tasks/planning-material-boundary-matrix-2026-10-06.md)、[耗时/BGM总入口](tasks/creation-latency-2026-10-02.md)及各自 Acceptance；只按需读取。

## 稳定架构

- [正式 Creation + Hypit](decisions/ADR-001-creation-hypit-mainline.md)
- [Material Layer V1.3](architecture/material-layer-v1.3.md) 和 [ADR-004](decisions/ADR-004-material-layer-v1.3-baseline.md)
- [Agent 结果处理 ADR-005](decisions/ADR-005-agent-result-processing.md)
