# Easel Roadmap

> **更新：2026-10-10。** 本文件仅负责执行顺序；实际代码、验收与阻塞以 [Current State](02_CURRENT_STATE.md) 为准。旧版按日期叠加的 G/R 批次顺序可从 Git `a6ed065d:docs/03_ROADMAP.md` 还原；历史失败/预算仍保留在各具名 Acceptance。

## 唯一视频主线与当前顺序

1. **已完成：ADR-005 新版协议单线化。** `easel-studio` 的五项默认 pin、Native Authoring/Check、Material/Rights/Quality 及旧 Writer 移除已完成软件发布；真实新作品 Build/E2E 另行验收。见 [CUT0–CUT6 Task](tasks/adr005-new-only-cutover-2026-10-10.md)。
2. **已完成软件与加载：Planning / OpenClaw 可靠性 O1。** SDK 异常安全分类和已固定 SHA 的 OpenClaw 2026.9.4 补丁已完成离线回归、正式安装升级及 Gateway/Web 重启健康验证。阶段感知的受限 HTTP 重试仍只在**隔离 Planning 评测代理**实现，发送后 `UNKNOWN` 和所有真实预算/回执不改写；尚未证明真实模型恢复效果。
3. **当前下一阶段（需另行模型/费用授权）：一条全新工程视频的完整主链验证（O2）。** 用新确认的 Creation，逐阶段检查 Planning 与独立语义、Truth、Material/Rights/Readiness、Native Authoring、Hypit Build、输出 SHA、Quality 和人工 Review/Selection。**每个作品自身的合同门槛不降低**，不以旧失败 Attempt 冒充新验收；本轮 O1 不自动放行真实 Provider。4. **再后：稳定性证明。** 完成原有独立资格 **6/6** 和同固定版 **3 个全新主题**的连续交付/工程介入统计，不把它们作为单条工程首片的总前置。未执行不得宣称 PASS。
5. **按实际阻塞处理（O3–O5）。** 已审核报价快照、机械回抄去重、BGM/Voice/质量细节只在该作品实际需要时最小修复；不另建生产链、不复制已有合同或平行矩阵。

## 不可改变的边界

- 正式流：Creation 确认 → Preparation/Handoff → Planning/Truth → MaterialRequirement/ResolutionResult/BindingResult/`MATERIAL_READY` → Native Authoring/Check → Hypit Build → Quality/人工 Review；Creator/Director/Creative Mode 与 Rights 的责任边界不变，不自动发布。
- 历史 R17 的 **9/9 `MATERIAL_READY`** 仅是旧作品素材恢复，不等于视频交付；广泛 BGM 能力留出/旧 R4 等 FAIL、UNKNOWN 和预算不重新计数。
- 原始规划路线、两窗口软件/BGM任务与连续出片的历史实施细节保存在 [唯一自主出片 Task](tasks/creator-autonomous-first-cut-2026-09-30.md)、[Planning 治理 Task](tasks/planning-material-boundary-matrix-2026-10-06.md)、[耗时/BGM总入口](tasks/creation-latency-2026-10-02.md)及各自 Acceptance；只按需读取。

## 稳定架构

- [正式 Creation + Hypit](decisions/ADR-001-creation-hypit-mainline.md)
- [Material Layer V1.3](architecture/material-layer-v1.3.md) 和 [ADR-004](decisions/ADR-004-material-layer-v1.3-baseline.md)
- [Agent 结果处理 ADR-005](decisions/ADR-005-agent-result-processing.md)
