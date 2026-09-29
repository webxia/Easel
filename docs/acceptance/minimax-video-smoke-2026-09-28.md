# MiniMax Video 真实冒烟验收

日期：2026-09-28
状态：**REAL_WORLD_VERIFIED（仅限 MiniMax Video 生成与 Material intake 冒烟）**

## 结果

- 这条 Video 真实运行当时的定向软件回归为 **66 passed**。后续三模态集成的当前全量测试和 Image/Voice 软件证据见 [Image/Voice 软件验收](minimax-image-speech-software-2026-09-28.md)。
- Provider / 模型：MiniMax Video V2 / `MiniMax-H3-Max`，480P，9:16。
- 生成任务：`446568756810140`；使用同一 task 查询并恢复下载，没有重复提交生成任务。
- 返回计量：MiniMax 报告 output 为 5 秒；按当前官方 480P 价格 ¥0.33/秒估算约 **¥1.65**。这是费率估算，不是账单实扣金额；最终以 MiniMax 账单为准。
- Attempt 内文件：`outputs/_material-minimax-smoke/attempt-minimax-smoke-436c5d56d7f7/materials/assets/asset-7b8a8172a81c414fb0f0c707926b5fb7/original.mp4`。
- 文件检查：`video/mp4`，2,095,159 bytes，SHA-256 `b7fa281e120cc5c5d5a4f9b630edfc1c8a34bf76a0fa85634187fdd90dda2166`；ffprobe 技术检查通过，观测时长 5.184 秒。
- Material 状态：生成来源、模型、task、SHA 与 Attempt 记录可追溯；Rights 为 `UNKNOWN`，required Need `need-video-smoke` 的 Readiness 为 `NOT_READY`，原因是 `required_need_rights_unknown`。
- Hypit：未启动 Authoring 或 Build；生成成功没有绕过正常准入。

## 边界

这是隔离冒烟 Attempt，不是现有 Creation 的产品级端到端验收。它证明当前 MiniMax 视频适配器能完成提交、异步查询、受限下载、字节持久化和技术检查；不证明权利许可、生产选材、Hypit 剪辑或最终成片。当前输出不得因技术检查通过而被当作已准入素材使用。

本机解析该 MiniMax OSS 结果域名时返回非公网地址；下载器拒绝了该地址，并通过仅针对官方 MiniMax 输出域名的 HTTPS DNS-over-HTTPS 解析、全局 IP 校验、IP pinning 与 TLS 主机名校验恢复同一 task 的下载。没有关闭 SSRF 防护。

官方依据：[MiniMax 按量计费](https://platform.minimaxi.com/docs/guides/pricing-paygo)、[视频生成接口](https://platform.minimaxi.com/docs/api-reference/video-generation-v2-create)。不在此记录生成提示词原文、API 密钥或其他凭证。
