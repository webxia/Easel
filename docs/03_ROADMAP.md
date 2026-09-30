# Easel Roadmap

This document records workstream order, not task-level status. [`02_CURRENT_STATE.md`](02_CURRENT_STATE.md) is the only summary of current implementation, acceptance, and blockers. Use the [Document Router](DOCUMENT_INDEX.md) to load the right context for a Goal.

## Next Active Workstream

当前优先项为 [自主首版与 Director 全链执行唯一实施方案](tasks/creator-autonomous-first-cut-2026-09-30.md)。原始目标对齐、流程重审与代码追踪已完成，用户已批准按合并方案实施。仅改现有主链，先局部验证，不继续旧 Creation，不调用付费 AI，不启动真实 Build 或完整 E2E。

[Creator 素材缺口恢复](tasks/creator-material-recovery-2026-09-30.md) 及同一音画作品的阶段恢复已完成，最终修订版经 Creator 审片入库，未发布。因工程介入，本轮自主 E2E 为 FAIL；用户已暂停后续工作，本次仅补齐文档并提交推送。下一次无工程救场验收需另行授权，不新增作品或重复付费。

[Creator 作品工作区体验优化](tasks/creator-workspace-2026-09-30.md) 的软件实现与确定性验收已完成，沿用 [Creator E2E 前修复](tasks/creator-e2e-repair-2026-09-30.md) 和 [T19](tasks/v1c-t19-low-friction-creation.md) 基线。用户随后明确启动了 [T15](tasks/v1c-t15-e2e-readiness.md) 的一次普通 UI 真实验收；本次已完成成片与入库，但因工程干预记为 PARTIAL。根因修复与具名运行结果见 Current State 的验收链接；下一次无工程救场验证需用户单独启动，不自动创建第二个作品。Generated Material 的既有边界与待验收项见 [Workstream](workstreams/generated-material.md)。

## Workstream Order

1. **自主首版与 Director 全链执行** — ①委托与持续交付 → ②Director 决策传递 → ③Material/Voice → ④Production → ⑤Quality/局部修复 → ⑥同 Creator/Mode 的跨内容局部回放；T19 的适用要求并入本轮，不作为并列路线。
2. **V1 真人验收准备 / T15** — 上述局部证据成立后评估 readiness，真实 E2E 等用户启动，既有作品不自动恢复。
3. **Product evidence branches** — select the relevant external acquisition, positive Library reuse, attribution, Supplemental Supply, or Continuity capability according to the user goal and prerequisites. These are separate branches, not an automatic batch.
4. **P3** — consider only after an explicit new request.

## Existing Foundations

- Creation + Hypit is the official new video mainline: [ADR-001](decisions/ADR-001-creation-hypit-mainline.md).
- Material Layer V1.3 is the frozen architecture baseline: [V1.3](architecture/material-layer-v1.3.md) and [ADR-004](decisions/ADR-004-material-layer-v1.3-baseline.md).
- Current software acceptance, real-world evidence, and remaining blockers are recorded only in [`02_CURRENT_STATE.md`](02_CURRENT_STATE.md); do not infer them from this sequence or from the existence of a Task/Acceptance file.
