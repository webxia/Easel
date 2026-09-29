# V1C-T09A：Material Layer MiniMax 多模态生成

状态：**Task COMPLETE（Image / Video / Voice 软件集成及隔离冒烟）；真实 Creation/Production 使用和 Rights 证明不属于本 Task 完成声明**。代码验收见 [Image/Voice 软件验收](../acceptance/minimax-image-speech-software-2026-09-28.md)，[Image/Voice 冒烟记录](../acceptance/minimax-image-speech-smoke-2026-09-28.md)和[Video 冒烟验收](../acceptance/minimax-video-smoke-2026-09-28.md)。

## 范围

- 仅支持符合 SourceRouter 生成策略的阻塞 Image、Video、Voice Need。
- Image：MiniMax Image-01 文生图；不支持参考图输入时明确拒绝。
- Video：MiniMax Video V2 异步生成。
- Voice：MiniMax T2A 基于已通过 truth review、hash-bound 的 `planning/SCRIPT.md` 合成预置音色，仅限 Global Voice Need；不做真人声音克隆或 Scene 文本切片。
- 每次有费用的生成由本机操作员逐次确认。
- 绑定 Attempt、Plan revision、Need、request ID；同一 request ID 不得重复提交付费操作。
- 输出进入 Attempt Material Store，保存模型、任务/请求、参数、输入 SHA、输出 SHA/MIME、检查与计费状态事实。
- 生成结果进入原有 Inspect、Rights、Match、Bundle、Readiness。Rights 未知时 required Need 必须继续阻塞。
- 本 Task 不自动启动 Hypit Authoring、Pricing 或 Build。

## 验收

1. 确定性测试覆盖三种模态的 Provider 契约、输入绑定、重复 request ID 和费用确认门。
2. 具名真实验收逐模态记录 Provider 输出、输出字节与技术检查；Image、Video、Voice 均有隔离输出证据。
3. 确认 Asset source/model/task/hash 可追溯，Rights=UNKNOWN 时 Material Gate 为 NOT_READY。
4. 三种模态的生成均不自动启动 Hypit；生成结果只有通过普通 Rights/Material Gate 后才能进入 Production 选材。

真实调用会产生 MiniMax 账单，按量价格以 [官方定价](https://platform.minimaxi.com/docs/guides/pricing-paygo) 为准。官方契约：[Image-01](https://platform.minimaxi.com/docs/guides/image-generation)、[T2A HTTP](https://platform.minimaxi.com/docs/api-reference/speech-t2a-http)、[Video V2](https://platform.minimaxi.com/docs/api-reference/video-generation-v2-create)。
