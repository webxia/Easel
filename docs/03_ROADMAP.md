# Easel Roadmap

This document records workstream order, not task-level status. [`02_CURRENT_STATE.md`](02_CURRENT_STATE.md) is the only summary of current implementation, acceptance, and blockers. Use the [Document Router](DOCUMENT_INDEX.md) to load the right context for a Goal.

## Next Active Workstream

[Creator 素材缺口恢复](tasks/creator-material-recovery-2026-09-30.md) 及同一音画作品的阶段恢复已完成，最终修订版经 Creator 审片入库，未发布。因工程介入，本轮自主 E2E 为 FAIL；用户已暂停后续工作，本次仅补齐文档并提交推送。下一次无工程救场验收需另行授权，不新增作品或重复付费。

[Creator 作品工作区体验优化](tasks/creator-workspace-2026-09-30.md) 的软件实现与确定性验收已完成，沿用 [Creator E2E 前修复](tasks/creator-e2e-repair-2026-09-30.md) 和 [T19](tasks/v1c-t19-low-friction-creation.md) 基线。用户随后明确启动了 [T15](tasks/v1c-t15-e2e-readiness.md) 的一次普通 UI 真实验收；本次已完成成片与入库，但因工程干预记为 PARTIAL。根因修复与具名运行结果见 Current State 的验收链接；下一次无工程救场验证需用户单独启动，不自动创建第二个作品。Generated Material 的既有边界与待验收项见 [Workstream](workstreams/generated-material.md)。

## Workstream Order

1. **Low-friction Creation review (T19)** — preserve the confirmed Production Brief and consolidate true human decisions.
2. **E2E preparation / V1 Product E2E (T15)** — align and verify the complete official chain; begin real testing only when the recorded prerequisites are satisfied.
3. **Product evidence branches** — select the relevant external acquisition, positive Library reuse, attribution, Supplemental Supply, or Continuity capability according to the user goal and prerequisites. These are separate branches, not an automatic batch.
4. **P3** — consider only after an explicit new request.

## Existing Foundations

- Creation + Hypit is the official new video mainline: [ADR-001](decisions/ADR-001-creation-hypit-mainline.md).
- Material Layer V1.3 is the frozen architecture baseline: [V1.3](architecture/material-layer-v1.3.md) and [ADR-004](decisions/ADR-004-material-layer-v1.3-baseline.md).
- Current software acceptance, real-world evidence, and remaining blockers are recorded only in [`02_CURRENT_STATE.md`](02_CURRENT_STATE.md); do not infer them from this sequence or from the existence of a Task/Acceptance file.
