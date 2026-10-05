# Easel Roadmap

This document records workstream order, not task-level status. [`02_CURRENT_STATE.md`](02_CURRENT_STATE.md) is the only summary of current implementation, acceptance, and blockers. Use the [Document Router](DOCUMENT_INDEX.md) to load the right context for a Goal.

## 当前 Workstream 与下一步

当前唯一方案为[素材层可靠供给与耗时优化](tasks/creation-latency-2026-10-02.md) v0.5。软件验证通过后，同作品恢复最新为 **8 of 9 / R16 PARTIAL / 音频验证未确认 / 未自主完成**，只缺BGM；既有失败与历史4/9、v0.4 FAILED不改写。具体状态以[Current State](02_CURRENT_STATE.md)和[恢复验收记录](acceptance/creation-latency-v05-material-resume-2026-10-05.md)为准。

## 当前顺序

1. 按原Task §12.11–§12.12收敛调度、旁白用途、已购补位准入及报告合同。当前修复确定性通过并经Astra复核，七视觉及旁白已有真实合格；BGM已取得真实音频并完成许可/署名事实恢复，R16普通音乐报告unknown；当前需解决音乐性验证证据，不能放行或无变化重试。只复用A1/A2/A3/B1/B2，不另建Task或素材链。
2. 组合确定性回归通过后，复核实际加载版本、未知提交、冻结输入、原作品累计授权及剩余额度，再沿原正式素材入口真实复验。用户已取消备用声音模型，旁白现规则已正式通过；BGM规则和Rights不放宽。当前停止状态不授权盲目重试。
3. 独立素材验收终点仍为全部required正式覆盖且MATERIAL_READY，必须验证自主完成及实际齐备耗时；空调用减少或提前停止不算交付成功。生成结果须普通准入，历史调用/费用不清零，旧作品预算不转授。
4. Authoring / Build / Quality及完整视频验收继续后置，不创建第二制作链。离线OpenClaw补丁落盘不认领网关已加载。

## Existing Foundations

- Creation + Hypit is the official new video mainline: [ADR-001](decisions/ADR-001-creation-hypit-mainline.md).
- Material Layer V1.3 is the frozen architecture baseline: [V1.3](architecture/material-layer-v1.3.md) and [ADR-004](decisions/ADR-004-material-layer-v1.3-baseline.md).
- Current software acceptance, real-world evidence, and remaining blockers are recorded only in [`02_CURRENT_STATE.md`](02_CURRENT_STATE.md); do not infer them from this sequence or from the existence of a Task/Acceptance file.
