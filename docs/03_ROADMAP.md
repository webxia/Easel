# Easel Roadmap

This document records workstream order, not task-level status. [`02_CURRENT_STATE.md`](02_CURRENT_STATE.md) is the only summary of current implementation, acceptance, and blockers. Use the [Document Router](DOCUMENT_INDEX.md) to load the right context for a Goal.

## 当前 Workstream 与下一步

2026-10-08 用户新授权优先顺序：按[自主首版唯一 Task 的连续出片 Goal](tasks/creator-autonomous-first-cut-2026-09-30.md#连续自主出片-goal2026-10-08-用户追加授权进行中)，证据确认的 Planning Runtime 接入修复与组合软件验证 → 固定版本与真实 Planning/Material 入口验证 → 同一 Delivery 完整首版验证 → 同固定版本三个独立新主题连续出片。保留历史失败，开发运行与正式验收分离，累计预算约束覆盖全部运行。以下旧批次顺序与原件作为历史依据保留，不将旧作品恢复冒认为新验收。

当前唯一方案为[素材层可靠供给与耗时优化：后续任务](tasks/creation-latency-2026-10-02.md) v0.6；作为共同总入口；按用户要求拆为 [BGM 执行 Task](tasks/creation-bgm-readiness-2026-10-05.md) 和 [视频流程软件 Task](tasks/creation-video-flow-software-2026-10-05.md)，各自独立 worktree。软件调查/优化可并行，真实制作仍按 G0–G4 的条件推进。已完成事项另存历史归档。同作品已按用户放宽BGM标准完成 **9 of 9 / R17 MATERIAL_READY / 工程恢复**，广泛声音能力留出仍FAILED，视频制作未启动；既有失败与历史4/9、v0.4 FAILED不改写。具体状态以[Current State](02_CURRENT_STATE.md)和[恢复验收记录](acceptance/creation-latency-v05-material-resume-2026-10-05.md)为准。

## 当前顺序

2026-10-07新失败后，优先按[原Task的R批治理及最新§13方案](tasks/planning-material-boundary-matrix-2026-10-06.md)执行：真实fixture与独立语义预期 → 程序派生合同/审核对象治理 → 完整集成与固定版本 → 全新32项真实Planning Eval → Material Smoke → 独立Material E2E。历次实际FAIL及原门槛保持；软件通过不放行真实阶段，状态与具体证据见Current State和唯一验收。不建立平行矩阵，不恢复旧失败计分，保留Creator/Director/Material/Hypit职责；Smoke/E2E仍后置。

用户2026-10-06最新顺序：[模型输出可靠性统一治理](tasks/planning-material-boundary-matrix-2026-10-06.md)复用已完成矩阵 → 补齐不回归基线与统一合同评审 → 同轮解决F1/G1/G2 → 组合软件回归 → 后续真实模型评测及独立Material Smoke → 完整独立Material E2E到MATERIAL_READY → 再汇合视频链路。A–D软件合同已通过，但现场保护审计FAIL，无例外整体验收不通过；事故处置以保留例外关闭；已另行固定commit55af28fb并加载Web/Gateway，加载前置检查PASS。E批真实评测仍另行启动。不重新建立平行矩阵。三轮FAIL保留，新真实作品预算另行绑定。软件证据与真实验收分别记录。

第二轮[Planning 模态边界修复](tasks/planning-modality-contract-2026-10-06.md)及第三轮真实验收属于已发生的前置证据，不自动跳过本次矩阵顺序。以下原作品/视频汇合顺序保留为后置计划，不能据此插队进入Authoring/Build/Quality。

视频流程软件 Task 可与以下 BGM 顺序并行执行源码核对和确定性软件验证；两边提交整合后再启动真实视频阶段。原作品和服务的实际操作只有 BGM 目标一个 Owner。

1. 原作品已按用户2026-10-06放宽BGM要求完成G1/G2受限恢复：9/9 MATERIAL_READY。v3/v4广泛能力留出FAILED及短人声漏检保留，不将通用声音能力标为通过；下一步汇合视频流程软件成果。
2. 视频阶段启动前完成分支整合和组合回归，重新核对实际加载版本、未知提交、冻结输入、预算与费用授权；原素材终点不自动升级为完整视频交付授权。Rights必要合同继续保持。
3. 后续视频验收以R17的9/9素材基线继续，记录工程介入和真实耗时；不能把此次报告复用耗时当作整链提速或自主完成。历史调用/费用不清零，旧作品预算不转授。
4. G2 MATERIAL_READY 后，G3 窄路线首版与 G4 三个新 Content 的重复交付另行启动；按真实能力和介入次数评估继续 Easel 或局部替换，不因方案完成自动进入 Authoring / Build / Quality，不创建第二制作链。离线OpenClaw补丁落盘不认领网关已加载。

## Existing Foundations

- Creation + Hypit is the official new video mainline: [ADR-001](decisions/ADR-001-creation-hypit-mainline.md).
- Material Layer V1.3 is the frozen architecture baseline: [V1.3](architecture/material-layer-v1.3.md) and [ADR-004](decisions/ADR-004-material-layer-v1.3-baseline.md).
- Current software acceptance, real-world evidence, and remaining blockers are recorded only in [`02_CURRENT_STATE.md`](02_CURRENT_STATE.md); do not infer them from this sequence or from the existence of a Task/Acceptance file.
