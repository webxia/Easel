# Easel Roadmap

This document records workstream order, not task-level status. [`02_CURRENT_STATE.md`](02_CURRENT_STATE.md) is the only summary of current implementation, acceptance, and blockers. Use the [Document Router](DOCUMENT_INDEX.md) to load the right context for a Goal.

## 当前 Workstream 与下一步

当前唯一方案为[素材层可靠供给与耗时优化](tasks/creation-latency-2026-10-02.md) v0.5，软件范围已完成。真实新作品验收已执行并以 **PARTIAL / 4 of 9 / AUTONOMOUS=NO** 停止；历史 v0.4 FAILED 保持。具体输入、版本、调用及阻塞以 [Current State](02_CURRENT_STATE.md) 和[本轮运行记录](acceptance/creation-latency-v05-material-e2e-2026-10-04.md)为准。

## 当前顺序

1. [原 Task §12.10](tasks/creation-latency-2026-10-02.md#1210-v05-实测追因与解决方案)已获软件实施批准；可靠要求/报告和音频适配、逐 Need 单批供料及累计边界已汇合并通过确定性验证。用户取消备用声音模型，当前模型有限放宽规则见 §12.10.10；不再等待资源批准。仍复用 A1/A2/A3/B1/B2，不新建平行 Task。下一步为有限真实报告/声音能力门 → 前置通过后另行允许同作品素材恢复；当前未加载服务或运行作品，不重跑对话与有效规划。
2. 继续真实素材验收须先核对实际加载版本、活动运行与未知提交、冻结输入、当前作品授权和累计剩余额度。当前停止状态不构成自动恢复指令；离线 OpenClaw 补丁落盘不等于运行中已加载。
3. 素材验收沿原 Delivery Owner 的持久 `MATERIAL_READY` 终点；全部 required 正式覆盖后停止。生成成功不能替代准入，恢复不能清零累计额度或重复购买。旧作品预算不得转授新作品。
4. 完整视频 Authoring / Build / Quality 及跨内容真实效果后置，需另行启动。素材齐备不等于整片完成，不创建第二制作链。

## Existing Foundations

- Creation + Hypit is the official new video mainline: [ADR-001](decisions/ADR-001-creation-hypit-mainline.md).
- Material Layer V1.3 is the frozen architecture baseline: [V1.3](architecture/material-layer-v1.3.md) and [ADR-004](decisions/ADR-004-material-layer-v1.3-baseline.md).
- Current software acceptance, real-world evidence, and remaining blockers are recorded only in [`02_CURRENT_STATE.md`](02_CURRENT_STATE.md); do not infer them from this sequence or from the existence of a Task/Acceptance file.
