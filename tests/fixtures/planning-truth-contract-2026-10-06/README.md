# 第三轮确认稿 / Truth 边界 fixture

来源：第三次独立 Material E2E `cr_7e2e84a687d9493095ff371425d7e930` / `fa_f0ff6daa752e339819a677b2d893a6fc`。实际运行仍为 FAIL，未进入 Material Supply；本目录不是修复后的生产输入。

`manifest.json` 列出每项 SHA 与来源。SCRIPT、SCENES、TREATMENT、MaterialPlan、视觉要求、Truth Packet 和系统审阅报告复制原现场字节，已与原受保护脱敏归档 original_sha256 逐项核对。proposal.md 是原归档 delivery.proposal 的最后一个 assistant 内容字段原文；confirmed-video-plan.json 是原 delivery.video_plan 的 JSON 序列化副本。没有人工删除说明、改写旁白、修正 Need、补审核结论或扩大授权。

矩阵有三种不同用途：

- 回放正常 `parse_video_plan`，证明 `**说明**` 段被纳入 script 而未在确认前拒绝。
- 回放原 Truth 报告，证明它绑定原脚本、不能认领改字脚本，并触发真实冻结确认稿保护。
- 在隔离目录显式构造缺失 sidecar、全 optional 等反例，核对消费者行为。派生变体不回写本目录，也不复用真实 Creation。

原报告被模型分为 creative_expression、rewrite_required、unresolved；这里仅验证报告身份和系统消费路径，不把模型语义判断当作正确分类答案，不将报告回放冒充新的真实审阅。

所有 JSON/文本已脱敏检查，不含凭证、auth 或生成媒体。完整真实验收证据见 `docs/acceptance/material-independent-e2e-3-2026-10-06.md`。
