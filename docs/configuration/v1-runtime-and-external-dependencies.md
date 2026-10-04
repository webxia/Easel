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

### 临时网关环境的生命周期（2026-10-03）

OpenClaw 2026.9.4 的 MCP 环境默认按会话生命周期保留，`mcp.sessionIdleTtlMs` 未设置时为 0（不做空闲回收）。Easel 持续交付在已核实执行终态后通过正式 `sessions.abort` 的 key/agent + `clearQueued=true` 释放临时环境；会话历史和成功产物仍保留，释放中断先对账清理，不重复模型调用。

隔离 easel profile 可用 `openclaw --profile easel config set mcp.sessionIdleTtlMs 300000` 开启五分钟空闲回收兜底，该配置支持网关热加载。本机已设置，其他安装需自行核实；活跃 lease 不参与空闲回收，不以清空聊天历史或调高 256 上限代替生命周期管理。

### Voice 执行要求与时序（2026-10-01）

新的 clear_memo_video 1.2 在冻结 Mode 中提供 voice_delivery 默认值；Planning 可在现有 Need.constraints.voice_delivery 中按内容选择 pace_ratio、pitch_semitones、tone。它们不选择 Provider 或音色，预置音色仍来自上述运行配置。MiniMax adapter 将这些中立要求转为官方 speed/pitch/emotion 参数；不支持的参数在提交前拒绝，不通过自然语言描述假装已执行。

TTS 开启句级字幕，按[官方 HTTP 合同](https://platform.minimaxi.com/docs/api-reference/speech-t2a-http.md)消费流式终态完整音频与字幕。时序按冻结脚本和实际音频身份校验后进入既有编排工作区；缺失时保留音频与明确缺口，不自动重新生成。它不是听感验收或 Rights 证明。软件验证和未完成边界以 Current State 为准，未对真实账号调用新请求。

正常旁白内容核对及缺失时序恢复使用现有 `faster-whisper` 依赖。`EASEL_ASR_MODEL` 指向含 `model.bin`、`config.json`、`tokenizer.json` 的本地 CTranslate2 模型目录，未配置时查找 `~/.cache/easel-models/faster-whisper-small`。只使用本地模型，不自动下载、不请求 TTS；CPU/int8 子进程识别有 180 秒执行上限。`audio.voice-timing-recovery` 只检查依赖和文件，不声称识别效果已验证。新委托即使有有效 Provider 时序，也要独立识别实际旁白；缺少本地依赖时在委托 TTS 核价、占额和付费提交前停止，避免先买音频再发现无法检查。

生成旁白识别保留完整音频，关闭 VAD 静音裁切，避免弱词起音在预处理后降低置信度；不使用前文条件拼接，避免静音处幻觉。2026-10-02 同音频实测 small 存在低置信和错字，较强的本地 large-v3-turbo 配合完整音频消除了本次低置信，但仍有单字差异，不能宣称通用可用；具体证据及剩余阻碍见 Current State。模型须在本机明确配置，生产不自动下载或轮换模型。

识别不注入目标脚本，逐词文本与实际时间必须覆盖完整冻结原文；仅在本地 ASR 比较时用固定 `opencc-python-reimplemented==0.1.7` 的 `t2s` 接受标准简繁等价，不采用同音容错或地区词汇替换。原识别报告保留，字幕仍使用冻结原文，Provider alignment 保持严格原文校验；转换库也纳入运行预检。按原文标点合并成整句字幕，边界仍取实际识别的首尾词，不均分或猜测时长。成功识别先保存检查点，再登记按 Need/脚本/音频绑定的内容观察并重新计算原 Gate；有效 Provider 时序保持原值，只有缺失或无效时才用识别时序补齐。错字、漏字、低置信或重叠不会改写脚本或重新购买，进入已有有界恢复与阶段 Retry。本地识别是内容/时序证据，不是音色、情绪、配乐适配或版权证明；Unknown Rights 仍然阻断。 当本地识别存在具体文字差异且 Creator 已实际试听确认时，现有素材匹配复核接口可接收 `voiceRecognitionReview`（`recognition_sha256` 与指定 `character/text` 结论）。该例外绑定当前音频、脚本、Need 和原识别报告，仅确认所列字符，原 ASR 文字不修改；其他内容、置信度、完整覆盖和时间仍按同一合同验证。未确认的同音差异不能自动放行。

2026-10-05 用户决定仅用当前声音模型、不下载备用模型，并授权有限放宽：全部词≥0.5保持原路径；完整原文逐字一致、真实时间有效时，可接受最低词≥0.25、低于0.5的字符≤全文5%且最多3字、字符加权均值≥0.85的路径。原文本/概率/时间不改，统计和准入规则单独保存；错字/漏字/增字、极低分或广泛弱证据仍拒绝。规则改变只重算已保存primary识别，不重跑模型或TTS；新失败身份绑定规则，同条件失败复用。详情及未正式恢复边界见[原 Task §12.10.10](../tasks/creation-latency-2026-10-02.md#121010-当前声音模型的有限放宽用户已批准2026-10-05)。

既往独立证据接口保留兼容：`EASEL_ASR_SUPPLEMENT_MODEL`、`EASEL_ASR_SUPPLEMENT_CAPABILITY` 及固定正负样本资格脚本不构成当前生产配置要求；当前 Owner 不查找、下载或调用备用模型。已合法取得的历史补证仍按原音频/脚本/Need/实际配置及区间完整核验，不伪造新能力。模型文件和 readiness 均不能代替实际内容/权利准入。

### BGM 本地声学观察（2026-10-01）

安装可选依赖 `pip install '.[audio-observation]'`；`EASEL_MUSIC_MODEL` 指向本地 [MIT AST AudioSet 模型](https://huggingface.co/MIT/ast-finetuned-audioset-10-10-0.4593/tree/f826b80d28226b62986cc218e5cec390b1096902)目录，默认 `~/.cache/easel-models/ast-audioset`。固定 revision 为 `f826b80d28226b62986cc218e5cec390b1096902`，需要 `config.json`、`preprocessor_config.json` 和 `model.safetensors`；三个文件的 SHA-256 均由代码校验，不接受任意替换模型或远程代码。生产读取只使用本地文件，不自动下载。`audio.music-observation` readiness 检查依赖和文件摘要，不执行推理。

现有后台素材观察步骤对 1～300 秒配乐候选进行 16 kHz 单声道解码，以重叠 10 秒窗口覆盖尾部，子进程执行上限 240 秒。音乐与人声类使用多标签 sigmoid 分数；低人声分数本身不能证明可用，还要求各窗口都有较强音乐证据，弱证据、静音、噪声与疑似人声保留未知或不适用。当前路由阈值（Music ≥0.8、各人声类 ≤0.01；≥0.2 视为检出人声）是保守的工程策略，不是校准概率或“绝无歌词”的保证；真实歌曲覆盖、弱人声漏检和误拒率仍需独立验证。不能用该分类器证明音色情绪、音质、版权或完整人工听感。

有效报告绑定模型版本、实际音频 SHA 与窗口覆盖，缓存于原 Attempt observations，逐 Need 应用证据并走原 Rights/Match/Readiness；报告落盘后登记中断不重复推理。同一模型的未知报告保留，尝试其他候选，不通过重复观察凑出 PASS。乐器/曲风的实际分类标签优先于 Provider 标题用于软排序，情绪、能量及 tempo 尚可能依赖元数据；风格偏好不增加硬门禁。模型缺失时保留素材并报告运行依赖问题，不伪造试听结论。

需配乐的新委托在提交新的付费素材请求前也预检本地声学依赖；已有 Provider 任务/已接收素材继续按原对账与恢复路径处理，不因依赖预检再次购买。模型配置就绪仍不等于真实听感验证。
