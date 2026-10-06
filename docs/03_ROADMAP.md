# Easel Roadmap

This document records workstream order, not task-level status. [`02_CURRENT_STATE.md`](02_CURRENT_STATE.md) is the only summary of current implementation, acceptance, and blockers. Use the [Document Router](DOCUMENT_INDEX.md) to load the right context for a Goal.

## 当前 Workstream 与下一步

当前唯一方案为[素材层可靠供给与耗时优化](tasks/creation-latency-2026-10-02.md) v0.6。同作品已按用户放宽BGM标准完成 **9 of 9 / R17 MATERIAL_READY / 工程恢复**，广泛声音能力留出仍FAILED，视频制作未启动。具体状态见[Current State](02_CURRENT_STATE.md)、[BGM Task](tasks/creation-bgm-readiness-2026-10-05.md)和[恢复验收](acceptance/creation-latency-v05-material-resume-2026-10-05.md)。

## 当前顺序

1. 原作品已按用户2026-10-06放宽BGM要求完成G1/G2受限恢复：9/9 MATERIAL_READY。v3/v4广泛能力留出FAILED及短人声漏检保留，不将通用声音能力标为通过；下一步汇合视频流程软件成果。
2. 视频阶段启动前完成分支整合和组合回归，重新核对实际加载版本、未知提交、冻结输入、预算与费用授权；原素材终点不自动升级为完整视频交付授权。Rights必要合同继续保持。
3. 后续视频验收以R17的9/9素材基线继续，记录工程介入和真实耗时；不能把此次报告复用耗时当作整链提速或自主完成。历史调用/费用不清零，旧作品预算不转授。
4. G2 MATERIAL_READY 后，G3 窄路线首版与 G4 三个新 Content 的重复交付另行启动；按真实能力和介入次数评估继续 Easel 或局部替换，不因方案完成自动进入 Authoring / Build / Quality，不创建第二制作链。离线OpenClaw补丁落盘不认领网关已加载。

## Existing Foundations

- Creation + Hypit is the official new video mainline: [ADR-001](decisions/ADR-001-creation-hypit-mainline.md).
- Material Layer V1.3 is the frozen architecture baseline: [V1.3](architecture/material-layer-v1.3.md) and [ADR-004](decisions/ADR-004-material-layer-v1.3-baseline.md).
- Current software acceptance, real-world evidence, and remaining blockers are recorded only in [`02_CURRENT_STATE.md`](02_CURRENT_STATE.md); do not infer them from this sequence or from the existence of a Task/Acceptance file.
