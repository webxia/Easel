# MiniMax Image / Voice 隔离冒烟

日期：2026-09-28
状态：**Image / Voice REAL_WORLD_VERIFIED（仅限隔离生成与 Material intake）**

## 结果

- Voice 经操作员授权提交一次；Image 首次响应无法入库后，经新授权再提交一次。未对同一请求重试。运行目录：`outputs/_material-minimax-image-speech-smoke/attempt-minimax-multimodal-smoke-20260928`、`outputs/_material-minimax-image-speech-smoke/attempt-minimax-image-retest-20260928`。
- `speech-2.8-hd` / `male-qn-qingse`：生成音频已写入 Attempt，MP3 49,524 bytes，时长 2.94 秒，SHA-256 `f6ca8a955a3079cc68906468a7038a475052a17188cffa2eca0126c6779719d4`；技术检查 `PASSED`，Rights `UNKNOWN`。
- `image-01`：首次响应的 `image_base64` 为官方契约定义的数组，旧适配器只接受字符串，记录为 `RESULT_INTAKE_FAILED`。修正后新请求成功入库：JPEG 159,952 bytes、720×1280，SHA-256 `816d09de8a076f151abaf6774d8da9c1568c7e9650f78d7f1be68bd8ef1dce47`；技术检查 `PASSED`，Rights `UNKNOWN`。
- Image 与 Voice 均经普通 Matcher 因 `rights_blocked:required_need_rights_unknown` 被拒绝；普通 Material Gate 为 `NOT_READY`，没有将素材交给 Production/Hypit。
- 三次请求按官方费率估算约 ¥0.055（两次 Image-01 + 13 个旁白字符）；这是潜在费用估算而非实扣账单，首次图片响应是否计费未知，最终以 MiniMax 账单为准。
- 不记录密钥、提示词或旁白原文；没有启动 Hypit。

官方依据：[Image-01 文生图契约](https://platform.minimax.cn/docs/guides/image-generation)、[T2A HTTP](https://platform.minimaxi.com/docs/api-reference/speech-t2a-http)、[按量定价](https://platform.minimaxi.com/docs/guides/pricing-paygo)。

此记录证明隔离 Image / Voice 输出和 Attempt 技术检查；不证明 Rights 获准、真实 Creation/Production 可用或最终声音质量。
