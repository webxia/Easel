# V1 运行依赖

当前状态以 [`02_CURRENT_STATE.md`](../02_CURRENT_STATE.md) 和实际命令结果为准。本文件只记录配置边界；完整依赖清单由 `easel runtime dependencies --json` 读取代码中的 Registry，不在文档复制静态大表。

## 正式生产链

| 能力 | 负责人 | 配置或前置条件 |
|---|---|---|
| Planning / Authoring | Easel + OpenClaw | 隔离 Gateway、可用模型认证和端点 |
| Library / Local / 外部素材 | Material Layer | 各来源的本机配置、逐素材 Rights evidence；搜索成功不代表素材已准入 |
| AI 素材生成 | Material Layer | MiniMax Image-01、Video V2、预置音色 T2A adapters 已接入；每次云端调用须在明确授权内（委托预算或单次确认） |
| 剪辑与成片 | Hypit 本地 CLI | `HYPIT_BIN` 或 PATH、本机 Runtime Profile；Hypit check / plan / pricing / Build 只用于 Production |
| Operator 操作 | Easel | 本机同源浏览器会话自动建立；付费生成须在明确授权范围内，Hypit Build 仍需持久审批 |

Hypit Runtime Profile 中的 `media.local`、`hyperframes.local` 支持现有本地媒体/渲染链。此前的 HypiHub endpoint 和 Image/Video/Voice 生成绑定已从 Easel-selected profile 移除；Hypit auth store 未改动。这些生成绑定不是当前产品依赖，缺少它们不会阻塞已有素材的 Hypit 剪辑。旧 `easel runtime generation-preflight` 不再是正式命令。

## 检查

```text
easel runtime dependencies --json --no-probe
easel runtime readiness --profile core-video --json --no-probe
easel runtime readiness --profile generation --json --no-probe
```

`generation` Profile 的 `material.ai-generation` 会检查 MiniMax 凭证/model 配置并报告 `CONFIG_READY`；这只代表本机配置存在，不代表认证、真实生成或 Gate 通过。新作品可在方案确认时授权素材生成预算；后端每次提交前核价并占额，未知或授权外费用另行处理。运行时 readiness 不调用模型、不提交 Build，也不证明逐素材 Rights 或真实成片。Secret 只保存在本机受保护配置中，不写入文档、日志或 Attempt 产物。

MiniMax 配置：优先使用 `EASEL_MINIMAX_API_KEY`，兼容读取已有 `MINIMAX_API_KEY`；共享 API host 仅接受官方 HTTPS 地址。可选 `EASEL_MINIMAX_VIDEO_MODEL`、`EASEL_MINIMAX_IMAGE_MODEL=image-01`、`EASEL_MINIMAX_SPEECH_MODEL=speech-2.8-hd` 和 `EASEL_MINIMAX_SPEECH_VOICE_ID`。TTS 使用冻结且通过 truth review 的脚本与预置音色，不执行声音克隆。真实 Provider 验收按模态分别记录，见 [T09A](../tasks/v1c-t09-minimax-video.md)、[Image-01](https://platform.minimaxi.com/docs/guides/image-generation) 和 [T2A HTTP](https://platform.minimaxi.com/docs/api-reference/speech-t2a-http)。

### Voice 执行要求与时序（2026-10-01）

新的 clear_memo_video 1.2 在冻结 Mode 中提供 voice_delivery 默认值；Planning 可在现有 Need.constraints.voice_delivery 中按内容选择 pace_ratio、pitch_semitones、tone。它们不选择 Provider 或音色，预置音色仍来自上述运行配置。MiniMax adapter 将这些中立要求转为官方 speed/pitch/emotion 参数；不支持的参数在提交前拒绝，不通过自然语言描述假装已执行。

TTS 开启句级字幕，按[官方 HTTP 合同](https://platform.minimaxi.com/docs/api-reference/speech-t2a-http.md)消费流式终态完整音频与字幕。时序按冻结脚本和实际音频身份校验后进入既有编排工作区；缺失时保留音频与明确缺口，不自动重新生成。它不是听感验收或 Rights 证明。软件验证和未完成边界以 Current State 为准，未对真实账号调用新请求。

正常旁白内容核对及缺失时序恢复使用现有 `faster-whisper` 依赖。`EASEL_ASR_MODEL` 指向含 `model.bin`、`config.json`、`tokenizer.json` 的本地 CTranslate2 模型目录，未配置时查找 `~/.cache/easel-models/faster-whisper-small`。只使用本地模型，不自动下载、不请求 TTS；CPU/int8 子进程识别有 180 秒执行上限。`audio.voice-timing-recovery` 只检查依赖和文件，不声称识别效果已验证。新委托即使有有效 Provider 时序，也要独立识别实际旁白；缺少本地依赖时在委托 TTS 核价、占额和付费提交前停止，避免先买音频再发现无法检查。

识别不注入目标脚本，逐词文本与实际时间必须覆盖完整冻结原文；按原文标点合并成整句字幕，边界仍取实际识别的首尾词，不均分或猜测时长。成功识别先保存检查点，再登记按 Need/脚本/音频绑定的内容观察并重新计算原 Gate；有效 Provider 时序保持原值，只有缺失或无效时才用识别时序补齐。错字、漏字、低置信或重叠不会改写脚本或重新购买，进入已有有界恢复与阶段 Retry。本地识别是内容/时序证据，不是音色、情绪、配乐适配或版权证明；Unknown Rights 仍然阻断。
