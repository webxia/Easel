# V1 运行依赖

当前状态以 [`02_CURRENT_STATE.md`](../02_CURRENT_STATE.md) 和实际命令结果为准。本文件只记录配置边界；完整依赖清单由 `easel runtime dependencies --json` 读取代码中的 Registry，不在文档复制静态大表。

## 正式生产链

| 能力 | 负责人 | 配置或前置条件 |
|---|---|---|
| Planning / Authoring | Easel + OpenClaw | 隔离 Gateway、可用模型认证和端点 |
| Library / Local / 外部素材 | Material Layer | 各来源的本机配置、逐素材 Rights evidence；搜索成功不代表素材已准入 |
| AI 素材生成 | Material Layer | MiniMax Image-01、Video V2、预置音色 T2A adapters 已接入；每次云端调用须操作员确认 |
| 剪辑与成片 | Hypit 本地 CLI | `HYPIT_BIN` 或 PATH、本机 Runtime Profile；Hypit check / plan / pricing / Build 只用于 Production |
| Operator 操作 | Easel | 本机同源浏览器会话自动建立；付费生成仍需逐次确认，Hypit Build 仍需持久审批 |

Hypit Runtime Profile 中的 `media.local`、`hyperframes.local` 支持现有本地媒体/渲染链。此前的 HypiHub endpoint 和 Image/Video/Voice 生成绑定已从 Easel-selected profile 移除；Hypit auth store 未改动。这些生成绑定不是当前产品依赖，缺少它们不会阻塞已有素材的 Hypit 剪辑。旧 `easel runtime generation-preflight` 不再是正式命令。

## 检查

```text
easel runtime dependencies --json --no-probe
easel runtime readiness --profile core-video --json --no-probe
easel runtime readiness --profile generation --json --no-probe
```

`generation` Profile 的 `material.ai-generation` 会检查 MiniMax 凭证/model 配置并报告 `CONFIG_READY`；这只代表本机配置存在，不代表认证、真实生成或 Gate 通过。Web 操作台每次提交前会要求确认潜在费用。运行时 readiness 不调用模型、不提交 Build，也不证明逐素材 Rights 或真实成片。Secret 只保存在本机受保护配置中，不写入文档、日志或 Attempt 产物。

MiniMax 配置：优先使用 `EASEL_MINIMAX_API_KEY`，兼容读取已有 `MINIMAX_API_KEY`；共享 API host 仅接受官方 HTTPS 地址。可选 `EASEL_MINIMAX_VIDEO_MODEL`、`EASEL_MINIMAX_IMAGE_MODEL=image-01`、`EASEL_MINIMAX_SPEECH_MODEL=speech-2.8-hd` 和 `EASEL_MINIMAX_SPEECH_VOICE_ID`。TTS 使用冻结且通过 truth review 的脚本与预置音色，不执行声音克隆。真实 Provider 验收按模态分别记录，见 [T09A](../tasks/v1c-t09-minimax-video.md)、[Image-01](https://platform.minimaxi.com/docs/guides/image-generation) 和 [T2A HTTP](https://platform.minimaxi.com/docs/api-reference/speech-t2a-http)。
