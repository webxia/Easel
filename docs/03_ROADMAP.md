# Easel Roadmap

This document records workstream order, not task-level status. [`02_CURRENT_STATE.md`](02_CURRENT_STATE.md) is the only summary of current implementation, acceptance, and blockers. Use the [Document Router](DOCUMENT_INDEX.md) to load the right context for a Goal.

## 当前 Workstream 与下一步

当前优先项为 [自主首版与 Director 全链执行唯一实施方案](tasks/creator-autonomous-first-cut-2026-09-30.md)。原始目标对齐、流程重审与代码追踪已完成，用户已批准按合并方案实施。本轮最小范围已完成确定性软件验收，仅改现有主链，未继续旧 Creation、调用付费 AI 或启动真实 Build/完整 E2E。下一步是用户另行启动的真人验收。

## 当前顺序

1. 复用已有后端推进、委托、Director、Material/Voice、Production、Quality 与跨内容回放基础；不从头重做。
2. 唯一 Task 已按 **C 镜头替代 → B 独立观察复用 → D 例外组合接受 → E 体验与全链局部回放** 完成软件收尾；正常路径不增加人审。
3. 软件/离线预检准备度为 READY_FOR_HUMAN_E2E；加载新代码、新建作品后的真实自主交付及跨内容风格效果由用户另行启动验收。
4. Library 等其他专项证据与 P3 不并入本轮。

历史素材恢复、Creator 工作区、E2E 前修复及 T19 是复用基线，不是并行当前任务。旧音画作品已审片入库但自主性 FAIL；最近未完成作品已删除，不恢复或重建。历史暂停/运行记录不覆盖当前实施授权。

## Existing Foundations

- Creation + Hypit is the official new video mainline: [ADR-001](decisions/ADR-001-creation-hypit-mainline.md).
- Material Layer V1.3 is the frozen architecture baseline: [V1.3](architecture/material-layer-v1.3.md) and [ADR-004](decisions/ADR-004-material-layer-v1.3-baseline.md).
- Current software acceptance, real-world evidence, and remaining blockers are recorded only in [`02_CURRENT_STATE.md`](02_CURRENT_STATE.md); do not infer them from this sequence or from the existence of a Task/Acceptance file.
