# S6 · 运行配置与真实验收边界

本文记录已实现接入的配置合同。示例均为占位值，不含凭证，不表示已调用真实服务。代码读取项目 `.env` 与进程环境；环境值优先。新增实际模型/配音/生图/生视频调用仍需作品内的对应授权。

## 本地启动与体验

在当前开发工作树执行；使用单独虚拟环境，不覆盖其他工作树的环境或运行数据：

```sh
cd /Users/xgx/.codex/worktrees/s5-architecture/Easel
python3 -m venv .venv-s6
.venv-s6/bin/python -m pip install -e '.[production]'
npm --prefix web/frontend ci
npm --prefix web/frontend run build
EASEL_PRODUCTION_ENABLED=1 .venv-s6/bin/easel web --port 7860
```

Windows 使用 `.venv-s6\Scripts\python.exe` / `easel.exe`，PowerShell 先设置 `$env:EASEL_PRODUCTION_ENABLED="1"`。外部 `ffmpeg` 与 `ffprobe` 须在 PATH，字体须按下文明确配置。Web 已运行持久 worker，无须同时再启动 CLI worker。无 Web 时可运行 `easel production worker --root <项目绝对路径>`；`easel production status --root <项目绝对路径>` 为只读状态检查。

访问 `http://127.0.0.1:7860` →「视频制作」。创建作品并选用已有六维画像（可不选）、频道/导演，登记本次主题和素材，检查声音/字幕，选择服务授权并请求完整方案。确认方案及生图/生视频次数后，制作任务自动推进；工作台显示每步产物、错误和恢复入口。审阅具体输出版本，可自然语言局部修改、对比版本，明确接受后才进入内容库。未配置服务时可以浏览和创建作品，但不能生成真实方案或把缺失服务当作通过。

新 V2 数据存于本项目 `outputs/_production` 和 `outputs/works`；首次启用创建新库，不读取 V1 历史运行库。停止 Web 后任务可由同库 worker 恢复；取消按钮才表示用户取消。不要手动删除这两个目录来解决失败。设置 `EASEL_PRODUCTION_ENABLED=0` 停用新入口，不卸载旧聊天能力。

## 创作模型

使用既有 direct API 配置合同，模型仅收到本任务显式上下文与受控工具结果：

```dotenv
EASEL_DIRECT_API_BASE_URL=https://your-compatible-service.invalid/v1
EASEL_DIRECT_API_MODEL=your-model
EASEL_DIRECT_API_KEY=your-private-key
EASEL_PRODUCTION_MODEL_CAPABILITIES=image,video,audio
```

仅填写服务实际支持的能力；配置不构成真实调用授权。模型须支持非流式 `/chat/completions`、JSON 输出；需要公开事实工具时还须支持 tools。图片、音频和视频输入协议不同，不能用名称猜测兼容。有声成片完整审查还须配置下文的实际视频协议。没有视频能力时仍可保存已有产物并展示阻塞原因，但不能标记完整质量通过。凭证放在本机环境或忽略的 `.env`，不要提交、截图或粘贴到对话。

## 固定声音服务

`EASEL_VOICE_SERVICES_JSON` 是具名 HTTP 声音服务数组。未设置时声音列表为空，不从通用 TTS Key、其他画像或 `auto` 引擎猜选声音。

```json
[
  {
    "provider": "my-speech-service",
    "model": "configured-speech-model",
    "engine": "http-speech-v1",
    "base_url": "https://speech.example.invalid/v1",
    "api_key_env": "MY_SPEECH_API_KEY",
    "mode": "speech",
    "response_format": "wav",
    "voices": [
      {
        "voice_id": "configured-voice-id",
        "label": "自然讲述",
        "tags": ["学习", "科技"],
        "languages": ["zh"],
        "speed_range": [0.75, 1.5],
        "instructions_supported": false
      }
    ]
  }
]
```

将上述 JSON 压成一行赋给该环境变量；`MY_SPEECH_API_KEY` 另设为实际凭证，不能把凭证放进 JSON、Git 或截图。若 `api_key_env` 指向的值缺失，目录保留原音色身份并标不可用。无需鉴权的自托管服务可省略 `api_key_env`。

当前适配器只实现仓库既有的 `/audio/speech` 合同：POST `model/input/voice/response_format`，可选 `speed/instructions`，响应为音频二进制。`base_url` 不包含 `/audio/speech`；它由适配器追加。不能把不兼容的异步服务、JSON URL 响应、克隆注册 API 配成此适配器后宣称可用。`engine` 是显式固定的实现身份，不能写 `auto` 来期待自动路由。参数能力必须与所选服务真实支持一致；不支持 `instructions` 就不显示或提交情绪表达字段。

`provider/model/voice_id/engine/parameters` 一起固定。授权三元组为 `provider/model/mode`；试听创建独立 `preview` 授权与 `voice_preview` 任务，制作使用当前已确认方案的 `production` 授权。VOICE 不占生图/生视频次数，但仍记录操作及实际请求；超时结果未知时只核实本地已持久化回执，不自动重发，也不宣称服务提供远端幂等查询。用户明确选择“重新生成试听（新增调用）”才创建新的生成意图。

同一作品的同文、同音色、同参数、同配置可复用已有音频。句段资产保存真实时长与文本摘要，重复句共享已付费音频字节但有各自编辑句柄。原声指定的场景保留原声，不由此接口改写或重配；实际旁白长于已确认时段时保留结果并请求调整，不能截断、加速或缩短片子。

实现入口：`voice.configured_voice_service`、`VoiceService.synthesize`、`voice_preview_handler`、`voice_tasks.VoiceTasks.prepare_assets`。HTTP 接口在 `web/production_settings_api.py`；任务只保存引用，媒体归档到 `outputs/works/<work_id>/artifacts`。

## 字幕字体、预览与保存范围

`EASEL_SUBTITLE_FONTS_JSON` 是字体名称到**本机真实字体文件**的映射，例如：

```json
{"My Sans":"/absolute/path/to/licensed-font.ttf"}
```

路径由本机配置提供，支持 `.ttf/.otf/.ttc`；不下载字体，不默认替换为系统字体。应选用覆盖作品文字的合法字体。作品固定的 `subtitles.font` 必须匹配映射中的名称；若使用合同默认的 `sans-serif`，须显式配置该名称的实际字体文件。字体摘要写入素材资产，后续导出只使用已固定的文件。

字幕支持开关、字体、字号、颜色、描边、背景、顶部/中间/底部；字号按最终输出像素，范围 1～1080，实际放不下时明确失败，不暗中缩小。预览与导出共用 `caption_from_settings/caption_image`，既有成片的字幕预览使用对应渲染记录内的**无字幕合成底片**，不会把新字幕叠在旧烤录字幕上。尚无工程时可选择本片原始画面预览，接口返回实际尺寸，不能把原始构图预览称作已完成最终剪辑。

`GET /api/production/works/<id>/settings` 返回作品、频道、画像设置与各自摘要。只有明确选择保存范围才更新该范围；频道/画像保存须带读取时的 `expected_settings_hash`，冲突后刷新，不静默覆盖他处修改。历史方案保持快照；更改默认不是授权，也不修改已生成音轨。声音试听、字幕预览、保存设置是独立动作，调整控件本身不发收费请求。

## 本地编辑器与证据

当前编辑器使用本机外部 `ffmpeg/ffprobe`，不自动安装、不随本任务分发二进制。支持范围、许可证和限制见 [ADR-S6-009](decisions/ADR-S6-009-local-editor.md)。所需编码器为 `libx264/aac`，程序检查必要滤镜；字体绘制用 Pillow，未要求 libass/drawtext。运行时缺少必要能力会返回明确错误。

本轮真实执行过 macOS arm64 的 FFmpeg 8.1 / Pillow 12.3.0 合成媒体测试，包括独立 900 秒用例。声音 HTTP 协议、持久任务、字幕预览与缓存使用 MockTransport 和合成 WAV，**未调用真实声音服务**；自然听感、说话人一致性、真实接缝/节奏及字幕语义对齐仍须真实作品验收。Ubuntu/Windows 及完整规格组合不据本机结果宣称通过。完整命令与结果见 [S6-09](tasks/S6-09_editor-adapter.md)、[S6-10](tasks/S6-10_voice-subtitles.md)。

## 素材、图片和视频生成

素材库是新的 V2 私有库：`outputs/_production/materials/`。只接收当前登记输入和受控下载，不扫描 V1 库或自动迁移历史数据。实际素材复制至作品 `assets/`，来源/许可/署名和稳定句柄进入作品引用；共享库提升需要明确复用许可。

| 配置项 | 含义 |
| --- | --- |
| `PEXELS_API_KEY` | Pexels 图片、视频检索；缺失时不假装已检索。公开来源 URL 也必须有素材专属 Rights 证据 |
| `EASEL_REVIEWED_PUBLIC_SOURCES_JSON` | 显式审查的图片、视频、音频来源清单，JSON 文本或绝对本地 JSON 文件路径，最多 256 KiB；格式见下文，不把任意 URL 当作可用素材 |
| `MINIMAX_API_KEY` | MiniMax 生成凭证；仅配置不代表可发送 |
| `EASEL_IMAGE_MODEL` | 当前支持 `image-01`，省略时只声明该适配器默认型号 |
| `EASEL_VIDEO_MODEL` | 须显式选择 `MiniMax-H3` 或 `MiniMax-H3-Max`，无静默型号替代 |
| `EASEL_GENERATION_RIGHTS_JSON` | JSON 文本或绝对本地 JSON 文件路径，最多 256 KiB；顶层为 `schema_version:1`，`IMAGE`/`VIDEO` 为实际 `RightsInfo`，不能用有 key 代替许可证据 |

RightsInfo 至少要有已核实状态、许可名称（KNOWN 时）、来源证据；限制与署名要求须照实填写。每个 `evidence` 包含 `kind`、`reference`，可有带时区的 `observed_at`、`summary`。未知、受限、缺证据的生成模态不标可用，不在文档里提供可直接复制为授权的虚假许可。成功生成后才登记真实的素材回执证据。

每次图片/视频发送仍检查已确认方案、本次服务/模型/模式授权和剩余次数。生视频需明确时长、画幅和分辨率：H3 为 4～15 秒及 768P/2K，H3-Max 为 5～15 秒及 480P/768P。片长 1～900 秒与单次生成片段时长是不同设置，由已确认方案组织素材和剪辑。

供料返回候选，由导演做语义选择；检索循环不调用收费生成。缺外部配置且库不足会明确阻塞，不把配置缺口说成检索失败；用户已明确选择的生成请求仍可按其授权执行。已实际尝试外部来源后的缺口可由已授权创作模型提出补料请求，程序固定服务身份、校验额度与 Rights，并在发送前保存决定。已登记素材恢复时复用；已提交/未知操作只查询，回执无法核实时明确需要处理，不自动重发。

`music` / `mixed` 的音乐供料先读取已确认方案画像作用域内的合格音频，再尝试已配置的公开音频来源；Pexels 不支持音频，不能用有 Pexels key 代替音乐来源。音频的 `candidate_role=music` 只表示本次候选用途，导演仍须实际听取并判断是否适用，程序不把文件名或来源描述当作已听过的结论。音乐素材不足时返回 `needs_decision`，保留已取得画面；不切成静音、不生成 AI 音乐。旁白继续使用独立的声音配置和授权。恢复复用同一次任务已登记音频，不重复下载；素材库作用域来自方案的冻结画像快照，不随作品后续更换画像而切换。

已审查公开来源清单是运营者明确配置的有限候选集合，**没有自动爬站或任意 URL 搜索能力**。配置须填写真实证据，不附带内置许可。格式如下（字段说明，不是可以直接发送的示例授权）：

| 位置 | 必填内容与限制 |
| --- | --- |
| 顶层 | `schema_version: 1`、`allowed_hosts`、`candidates`；未知字段拒绝 |
| `allowed_hosts` | 1～32 个明确小写 DNS 域名；不接受协议/路径、通配符、IP 字面量或本地域名；可访问该域名及子域名 |
| 每项候选 | 不重复的 `candidate_id`、`media_type`（`image`/`video`/`audio`）、HTTPS `download_url`、`source`、`rights`；可有 `semantic`；最多 80 项 |
| `source` | `kind` 为 `public` 或 `external`，`provider` 固定 `reviewed_public`，真实 `provider_asset_id`、`source_page`、`creator`；来源页和下载域名均须属于 allowlist |
| `rights` | 实际 `RightsInfo`，状态为 `KNOWN`、`PUBLIC_DOMAIN` 或 `ATTRIBUTION_REQUIRED`，至少一条 `kind` 以 `asset_` 开头的素材专属证据；KNOWN 须有许可名称；需署名时填写 `attribution_required:true` 和完整原文 `attribution_text`（含创作者及来源页） |
| `semantic` | 可记录来源提供的 `caption`、`tags`、`attributes`；它们是候选描述，不是模型已验证的媒体事实 |

配置文件路径及其父目录不接受符号链接。配置构造阶段不联网；缺配置与错误配置分别明确提示，错误配置不发送下载。下载继续使用公共 IP 解析校验和固定地址连接，每次重定向重新检查 host/IP，限制体积与跳转次数，并以实际文件检查拒绝损坏媒体。来源配置不免除 Rights 的实际用途限制、完整署名传递与作品引用保护。

`tests/production/test_supply_tasks.py` 已用实际合成 WAV、图片和隔离传输验证主题输入的 music/mixed 候选、库内音频复用、恢复不重取、署名传递、缺来源/损坏音频/无许可/非法 host 阻断，以及历史方案的画像作用域隔离；这些是软件证据，不代表音乐审美或真实公开来源端到端验收。

代码迁入、协议原始来源、许可证与未测边界详见 [素材迁入记录](../../easel/materials/MIGRATION.md)。素材/HTTP 协议和真实本地视频检查通过离线 fixture 与 MockTransport；真实 Pexels/MiniMax 服务和生成质量 **NOT_TESTED**。

## 公共事实检索

主线未发现可直接复用的实际 websearch 实现，因此当前提供具名 Brave HTTP 适配器；不使用开发 Agent 的浏览器、联网工具或账号。

- `EASEL_PUBLIC_FACTS_PROVIDER=brave` 显式开启该工具；`BRAVE_SEARCH_API_KEY` 为服务凭证。
- 本次规划/制作任务还须授权 `provider=brave`、`model=web-search`、`mode=search`。检索调用可能消耗供应商额度，但不计作 IMAGE/VIDEO，也不冒充 MODEL 操作。
- 固定请求官方搜索端点，每次最多 10 条，不跟随重定向或抓取任意返回 URL。缺配置、缺授权、服务失败明确返回不可用，不编造查证过程。
- 结果保存 URL、观察日期及服务提供的发布日期；公共事实证据 artifact 可恢复复用。发送前持久记录查询意图，成功响应先保留私有回执；响应丢失时不自动重复可能收费的查询。搜索摘要标为 `partial`，未读原文不声称全文核实，不能作为个人经历证据。

协议依据：[Brave Web Search 官方文档](https://api-dashboard.search.brave.com/app/documentation/web-search/get-started)，2026-10-17 核对。`tests/production/test_public_facts.py` 的授权、缓存、来源日期、URL/重定向和脱敏负例已通过；真实 Brave 调用 **NOT_TESTED**。

## 完整审片模型协议

创作参考的少量抽帧不能作为全片质量通过依据。`quality` 任务现在必须逐段提交实际视频文件，随后对所有分段观察做全片综合；仅图片能力、只返回脚本评价或未配置协议时，保留已渲染成片并进入 `needs_decision`。

| 配置项 | 当前实现 |
| --- | --- |
| `EASEL_PRODUCTION_MODEL_CAPABILITIES` | 有声成片需明确包含 `video,audio`；无声成片需 `video`。原创作任务仍按实际需要声明 `image` 等能力。该配置是服务能力声明，不会给不支持的模型增加能力 |
| `EASEL_PRODUCTION_VIDEO_DIALECT=qwen-omni-video-url` | Chat Completions 的 `video_url.url` 提交 MP4 Data URI，音轨留在视频文件内；请求文本 JSON 输出。当前非流式调用需支持 `modalities=["text"]`、`reasoning_effort="none"`、`response_format=json_object` 的服务/模型 |
| `EASEL_PRODUCTION_VIDEO_DIALECT=qwen-vl-video-url` | 同样提交实际视频文件，仅适用于无声成片；不能用于有声作品的完整审片，即使另填了 `audio` 能力也不绕过该限制 |
| `EASEL_PRODUCTION_QUALITY_CHUNK_SECONDS` | 默认 30 秒，允许 1～60 秒。相邻段保留最多 1 秒的重叠，涵盖切点；编码后的 Base64 接近 10 MB 时继续缩短片段，不通过降分辨率、丢帧或去音轨满足限制 |

默认协议为空，不能因服务号称“兼容 OpenAI”就假定 `video_url` 可用。[Qwen Chat Completions 参数](https://www.alibabacloud.com/help/en/model-studio/qwen-api-via-openai-chat-completions) 区分 VL 的画面理解与 Omni 的音画理解；[Qwen-Omni 官方说明](https://www.alibabacloud.com/help/en/model-studio/qwen-omni) 给出本地视频 Base64、输入限制和 `qwen3.8-omni-flash` 非流式 JSON 示例（2026-10-17 核对）。这只证明所述协议具有接入依据；旧 Omni 仅流式的型号不能直接套用当前非流式适配器。切换端点、模型、能力、方言或分段配置会改变模型配置摘要，不能串用原调用回执。

审片副本采用原分辨率、原帧率 H.264 CRF18 和 AAC 192k 编码，原交付成片不变；副本保存于作品 `inspection/` 目录。先完成区间、实际时长、画面/声音和文件摘要校验，再发模型请求。缓存用于重启后复用完全相同的请求字节，缓存变化不能自动重建后复用旧回执。每段记录开始/结束时间、SHA-256 和审阅结论；可观察事件提供已完成段数和本段范围。所有分段及全局语义综合均通过且没有局限，才标记 `passed`；任何未审完、片尾缺陷、局部失败、跨段冲突或观察不足都不会被汇总中的一次“通过”抹去。

这里的 `coverage_complete` 表示提交的实际视频区间完整覆盖时间轴，**不等于已验证供应商内部逐帧采样或模型判断正确**。本轮仅用本地合成视频和 scripted/MockTransport 验证完整字节提交、尾部缺陷负例、声音/方言能力检查、缓存与操作身份；未调用真实视频理解服务，真实审片准确度、音色自然度和创作质量仍未验收。相关测试：`tests/production/test_quality.py`、`test_creation_flow.py`、`test_voice_settings_api.py`。
