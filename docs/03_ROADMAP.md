# Easel Roadmap

This document records workstream order, not task-level status. [`02_CURRENT_STATE.md`](02_CURRENT_STATE.md) is the only summary of current implementation, acceptance, and blockers. Use the [Document Router](DOCUMENT_INDEX.md) to load the right context for a Goal.

## 当前 Workstream 与下一步

当前唯一方案为[素材层可靠供给与耗时优化](tasks/creation-latency-2026-10-02.md) v0.5。软件验证通过后，2026-10-05同作品真实恢复为 **FAILED / 5 of 9 / 未自主完成**，R1/R2监护停止，R3自动达到报告失败上限；历史v0.5的4/9与v0.4 FAILED不改写。具体状态以[Current State](02_CURRENT_STATE.md)和[恢复验收记录](acceptance/creation-latency-v05-material-resume-2026-10-05.md)为准。

## 当前顺序

1. 按[原Task §12.11](tasks/creation-latency-2026-10-02.md#1211-2026-10-05-同作品素材恢复失败收口待修复未扩链路)先解决待重评与可执行集合/累计额度不一致导致的空观察循环，并排除已知旁白误入BGM观察。仍复用A1/A2/A3/B1/B2，无新Task或素材主链；用户已批准，调度与旁白用途修复及绑定生成准入补充已完成确定性验证，R3已达到真实报告失败上限，仍5/9；后续先定位视觉输出截断并验证有限报告能力，当前不再retry。
2. 组合确定性回归通过后，复核实际加载版本、未知提交、冻结输入、原作品累计授权及剩余额度，再沿原正式素材入口真实复验。用户已取消备用声音模型，旁白现规则已正式通过；BGM规则和Rights不放宽。当前停止状态不授权盲目重试。
3. 独立素材验收终点仍为全部required正式覆盖且MATERIAL_READY，必须验证自主完成及实际齐备耗时；空调用减少或提前停止不算交付成功。生成结果须普通准入，历史调用/费用不清零，旧作品预算不转授。
4. Authoring / Build / Quality及完整视频验收继续后置，不创建第二制作链。离线OpenClaw补丁落盘不认领网关已加载。

## Existing Foundations

- Creation + Hypit is the official new video mainline: [ADR-001](decisions/ADR-001-creation-hypit-mainline.md).
- Material Layer V1.3 is the frozen architecture baseline: [V1.3](architecture/material-layer-v1.3.md) and [ADR-004](decisions/ADR-004-material-layer-v1.3-baseline.md).
- Current software acceptance, real-world evidence, and remaining blockers are recorded only in [`02_CURRENT_STATE.md`](02_CURRENT_STATE.md); do not infer them from this sequence or from the existence of a Task/Acceptance file.
