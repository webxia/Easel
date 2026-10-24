# 运行配置与验收边界

状态：**当前主线配置指南**。以下配置示例不是运行授权，不证明已部署或真实能力通过。项目.env与进程环境按代码读取，环境优先；密钥只留本机忽略配置。当前服务、部署SHA、Dirty和实际验证只在[状态](../project/status.md)及运行记录维护。

## 装配与启动

安装与基础启动沿用[官方README](../../../README.md)。从实际仓库根、项目虚拟环境执行；生产依赖使用production extra，前端按项目脚本构建。启用EASEL_PRODUCTION_ENABLED=1后Web装配持久Worker；已有Web时不另起第二个Worker。关闭入口不删除生产库、outputs、Profile或历史回执。

受控对话使用现役main，easel-work的agentId=main、protocolVersion=2、permission_policy=main-pipeline-v1及九个具名业务工具。使用显式EASEL_VIDEO_GATEWAY_URL、EASEL_VIDEO_GATEWAY_TOKEN与独立EASEL_WORK_BRIDGE_TOKEN；缺配置/插件/握手失败须明确不可用，不切CLI绕过。旧easel-video双Agent部署步骤已归档，不能再照抄安装。

保留main原工作区、模型和普通工具配置；插件在受控namespace内注入产品指令、收窄工具并核对逐次票据。不能通过文件分开放置宣称根开发指令已隔离。配置合成不得覆盖原plugins成员或私人配置；具体生成器选项先核对当前源码和--help。首次安装、重载、迁移及真实调用按任务授权执行。

## 创作模型

使用既有 direct API 配置合同，模型仅收到本任务显式上下文与受控工具结果：

```dotenv
EASEL_DIRECT_API_BASE_URL=https://your-compatible-service.invalid/v1
EASEL_DIRECT_API_MODEL=your-model
EASEL_DIRECT_API_KEY=your-private-key
EASEL_PRODUCTION_MODEL_CAPABILITIES=image,video,audio
```

仅填写服务实际支持的能力；配置不构成真实调用授权。模型须支持非流式 `/chat/completions`、JSON 输出；需要公开事实工具时还须支持 tools。图片、音频和视频输入协议不同，不能用名称猜测兼容。有声成片完整审查还须配置下文的实际视频协议。没有视频能力时仍可保存已有产物并展示阻塞原因，但不能标记完整质量通过。凭证放在本机环境或忽略的 `.env`，不要提交、截图或粘贴到对话。

模型、素材供应和声音运行配置在 worker 启动时读取。修改服务、模型能力、协议或字体后，正常停止并重启 V2 Web/worker；界面目录更新不代表旧进程已切换。已有操作仍绑定原配置与授权，不会因重启自动重发未知结果或换服务。
生产源码新鲜度仅检查 production Python 文件集合、mtime_ns和size；不覆盖Web、插件、前端或配置，不能用reload_required=false证明整套部署一致。重载前按实际授权核对在途与UNKNOWN、备份与唯一进程；指南不授予重启权限。

MiniMax M3.1 完整 Planning 可能超过 120 秒；`EASEL_PRODUCTION_MODEL_TIMEOUT_SECONDS` 默认 900 秒，合法区间 120～1800，且纳入模型配置摘要。超时仍按未知结果处理，不能因增加预算而重发原请求。

**首次后端试片与运行槽**：当创作模型只有真实 `text,image,structured` 能力、没有原生音频输入时，Edit 可对实际 FFmpeg 媒体进行有界音轨技术测量并附注 `technical_only_unverified`，以生成内部待审预览；它不能证明音乐合适、SFX 听感、音画同步。完整语义 QC 仍依下述有声视频协议，没有就保持 `not_tested / needs_decision`。模型写到 `required_features` 中的非 FFmpeg 能力/事实备注不当作已支持能力，改为持久未验证审片备注。启动 V2 Worker 前先核对端口与现有运行作业，一次只保留一个 Web/Worker 服务实例；停止请求必须实际进入终态，不要连续创建多项 `run_detached_process` 长驻 Job 占满 Runner 并发槽。

## 临时人工审核模式（须有本次授权）

当前若只需先把真实视频交给 Creator 人工审核，可以在 生产运行环境的 Git 忽略 `.env` 中设置 `EASEL_PRODUCTION_QC_MODE=manual` 并重启 **唯一 Web/Worker**。默认 `full`；不配置时自动语义 QC 的严格门禁保持原行为。此开关暂时注释/绕过的是**最后自动音视频语义 QC Gate**，并未删除代码和检查合同，后续可把设置改回 `full` 并重启恢复。

仅当实际 FFprobe 视频与音轨技术检查通过、同一成片没有历史 `semantic=fail/partial` 时，任务方可直接 `succeeded`、Run `succeeded`、Work `reviewable`，并记录审计证据 `quality_checks.semantic=not_tested / mode=manual_review_only`。输出本身仍保留 `quality_state=needs_fix`，**不会谎称语义检查通过**。前端明确显示「技术检查通过 · 待人工审核」，必须由 Creator 完整观看音画后确认，提交 `manual_review_confirmed=true` 才可能人工接受；后端和迁移后的 SQLite trigger 均要求实际技术 PASS、未出现明确语义失败以及正式 Run 完成，任何接口调用都不能代替 Creator 本人的接受动作。人工接受独立记录为 `explicit_manual_review`，不会把语义 QC 的 `not_tested` 改成 `pass`。该输出不因人工跳过自动门禁而变成可自动批准的 Director 试片。

本模式不允许略过 Rights、素材、Planning、Creator 明确设置、真实配音、FFmpeg 渲染、文件摘要、技术 QC 或人工确认；不允许自动发布。禁用开关后，新运行恢复严格 QC；已存在的人工审阅证据不被重新解释成自动通过。

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

声音协议必须显式配置，不能写 `auto` 猜路由。`http-speech-v1`（兼容既有名称 `speech-http-v1`）沿用 `/audio/speech`：POST model/input/voice/response_format，可选 speed/instructions，返回音频二进制，base_url不带该后缀。S6-15 新增 `minimax-speech-v1`：base_url明确到 `/v1`，适配器追加 `/t2a_v2`，非流式请求 text/voice_setting/audio_setting，读取有界 JSON/hex 音频；当前明确支持 wav/mp3/flac、速度0.5～2，不支持通用instructions。模型与voice_id必须真实配置，不自动选择或换声。两个协议共用原Operation/句段/回执/真实时长校验，未知结果不重发；异步URL响应与克隆注册API不能冒充上述协议。配置目录和执行共用静态校验，缺Key/未知engine不会仅因有voices数组就标可用。MockTransport与合成音频只证明软件协议；账户真实调用及自然音色验证分别查具名运行记录，不能沿用早期“仅mock”结论判断当前能力。

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

当前编辑器使用本机外部 `ffmpeg/ffprobe`，不自动安装、不随本任务分发二进制。支持范围、许可证和限制见 [ADR-S6-009](../architecture/decisions/ADR-S6-009-local-editor.md)。所需编码器为 `libx264/aac`，程序检查必要滤镜；字体绘制用 Pillow，未要求 libass/drawtext。运行时缺少必要能力会返回明确错误。

早期S6-09/S6-10记录曾在 macOS arm64 实际执行 的 FFmpeg 8.1 / Pillow 12.3.0 合成媒体测试，包括独立 900 秒用例。声音 HTTP 协议、持久任务、字幕预览与缓存使用 MockTransport 和合成 WAV，**该轮未调用真实声音服务**；不能据此认定后续轮次也未调用。自然听感、说话人一致性、真实接缝/节奏及字幕语义对齐仍须真实作品验收。Ubuntu/Windows 及完整规格组合不据本机结果宣称通过。完整命令与结果见 [S6-09](../history/tasks/S6-09_editor-adapter.md)、[S6-10](../history/tasks/S6-10_voice-subtitles.md)。

## 素材、图片和视频生成

素材库是新的 V2 私有库：`outputs/_production/materials/`。正常运行只接收本次登记输入和受控下载，不自动扫描 V1 库或迁移旧生产数据库。历史显式本地素材副本导入见[原配置记录](../history/v2/16_RUNTIME_SETUP.md)，该授权不自动适用于新导入，也不导入旧运行状态。实际素材复制至作品 `assets/`，来源/许可/署名和稳定句柄进入作品引用；共享库提升需要明确复用许可。

| 配置项 | 含义 |
| --- | --- |
| `PEXELS_API_KEY` | Pexels 图片、视频检索；缺失时不假装已检索。公开来源 URL 也必须有素材专属 Rights 证据 |
| `PIXABAY_API_KEY` | Pixabay 图片/视频检索；有界 API 搜索响应在 V2 私有 `provider_cache/pixabay` 下缓存 24 小时，配置身份不代表远端已验证 |
| `UNSPLASH_ACCESS_KEY` | Unsplash 仅显式预览检索，不自动下载/供应制作资产；预览需热链接与摄影师/平台署名，尚未实现选中时下载追踪 |
| `EASEL_WIKIMEDIA_AUDIO_ENABLED=1` | 显式启用 Wikimedia Commons 公共 API 的音乐/音效来源，无账户/API Key；分别登记 `wikimedia_bgm`、`wikimedia_sfx`，都需作品内按 `model=stock,mode=search` 具名授权；默认 `0` 停用。官方搜索与文件元数据检索只用明确 User-Agent，不抓取页面 |
| `EASEL_MATERIAL_HTTP_PROXY` | 可选安全代理，如 `http://127.0.0.1:7897`；只允许 loopback HTTP CONNECT，经受信任 HTTPS DoH 获得真实公网 IP 再连接已验证数字 IP，保持源域名 TLS SNI/证书与原下载安全边界；不影响模型或 TTS；未配置则使用原直连 |
| `EASEL_REVIEWED_PUBLIC_SOURCES_JSON` | 显式审查的图片、视频、音频来源清单，JSON 文本或绝对本地 JSON 文件路径，最多 256 KiB；格式见下文，不把任意 URL 当作可用素材 |
| `MINIMAX_API_KEY` | MiniMax 生成凭证；仅配置不代表可发送 |
| `EASEL_IMAGE_MODEL` | 当前支持 `image-01`，省略时只声明该适配器默认型号 |
| `EASEL_VIDEO_MODEL` | 须显式选择 `MiniMax-H3` 或 `MiniMax-H3-Max`，无静默型号替代 |
| `EASEL_GENERATION_RIGHTS_JSON` | JSON 文本或绝对本地 JSON 文件路径，最多 256 KiB；顶层为 `schema_version:1`，`IMAGE`/`VIDEO` 为实际 `RightsInfo`，登记已核实的服务条款、适用用途及限制；不能用有 key 代替依据，也不表示账户额度或本作品调用已授权 |

RightsInfo 至少要有已核实状态、许可名称（KNOWN 时）、来源证据；限制与署名要求须照实填写。每个 `evidence` 包含 `kind`、`reference`，可有带时区的 `observed_at`、`summary`。未知、受限、缺证据的生成模态不标可用，不在文档里提供可直接复制为授权的虚假许可。成功生成后才登记真实的素材回执证据。

对话及能力列表将缺项解释为“生成素材使用许可依据未登记或无效”，机器码仍为`rights_evidence_missing`；与Key/型号缺失分别提示。许可登记就绪只代表本地准入配置就绪，不代表远端账户调用资格或额度已验证。`reason_message`供界面/对话说明，`readiness_note`保留这一区分，`usage_constraints`传递已登记的创作用途边界；其审美/语义与第三方权利判断仍由创作Agent和Creator审阅负责，不能宣称自由文字限制已全部由程序自动执法。

2026-10-19核对开放平台[用户协议](https://platform.minimax.cn/protocol/user-agreement)第9.5、1.7、6.2～6.4条，以及[付费协议](https://platform.minimax.cn/protocol/paid-agreement)（2026-08-18生效）。可按合法输入、人工核查、AI标识前提登记具体输出用途的依据；这不是无条件商用、独占著作权或第三方无侵权担保。付费资格与输出使用依据分别登记；成功生成后仍追加真实asset_generation_receipt。当前本机登记仅覆盖IMAGE，具体用户用途/配置路径/来源快照与hash留本机忽略目录，不把个人信息或许可文件写入Git。登记不触发请求、不改变任何已有作品授权，未核实的VIDEO继续不可用。

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

代码迁入、协议原始来源、许可证与未测边界详见 [素材迁入记录](../../../easel/materials/MIGRATION.md)。素材/HTTP 协议和真实本地视频检查通过离线 fixture 与 MockTransport；真实 Pexels/MiniMax 服务和生成质量 **NOT_TESTED**。


## 五类素材内部衔接

现有 PlanDocument 和 EditProject/AudioClip 外部结构不变。新的任务内部 MaterialIntent 从冻结画像/导演/计划解释短检索词、媒体类型、BGM意图及SFX事件；结果按上下文摘要持久化，重启不重新解释。图/视频仍使用Pexels/Pixabay；BGM/SFX走本地授权素材和已有reviewed_public音频清单，不存在隐含的Pixabay音频API。必要音效缺口返回needs_decision，可选点缀不升级为新的硬性确认环节。

外部供料须在本方案有效授权中选择 provider/model/mode：Pexels、Pixabay及reviewed_public均为 `model=stock,mode=search`；有配置不是授权，撤销后停止下一次检索/下载。既有本地合格资产可直接复用。Unsplash仍是单独主动预览，不自动供料。

作品素材metadata的material_uses区分视觉、音乐及事件音效用途；同一文件可关联多个cue而不覆盖。供料输出仍只有schema_version和asset_ids。编辑前/选中后/渲染前复验具体素材的来源、Rights、范围、字节与引用，工程/导出仅列真正选中的素材。详细架构见[素材层架构](../architecture/materials.md)，真实服务及G4状态见[S6-15](../history/tasks/S6-15_material-layer-hardening.md)。

### BGM / SFX 免费音频来源

本次**不新增音频管理界面**。在已实现的本地库优先 + `reviewed_public` 有限清单基础上，新增 `easel/production/providers/wikimedia_audio.py` 两个独立身份：`wikimedia_bgm` 与 `wikimedia_sfx`。由确认 Plan 的 Director MaterialIntent 给出音乐氛围或 cue 查询，Commons 官方 Action API 按 `File:` 音频检索；只处理带官方文件页、音频下载地址、文件 SHA-1 和文件页具体许可元数据的资产。严格仅接受声明为 **CC0 1.0 / CC BY 4.0** 的条目，且许可 URL 必须匹配 Creative Commons 官方域名及相应路径；CC BY 强制保存创作者、原文件页与完整导出署名。ND/NC/SA、未明许可、缺署名或非受信任域名一律不可用于制作。该判断记录的是 Commons 的具体文件页声明，并不代表独立核验创作者拥有全部权利。

下载仍必须经过既有公网 DNS、逐跳重定向、文件大小与 FFprobe 技术检查；Commons 的 `application/ogg` 仅对音频容器开放，**下载字节 SHA-1 也须与查询时的官方文件版本一致**。一旦网络返回私网/保留地址或实际下载不合法，保留音频缺口与原素材，不改为静音、错误用途或无许可 AI 生成。相同来源同许可文件经现有库和 Rights 机制复用，SFX 多事件继续沿用 cue 绑定。该搜索服务不计 IMAGE/VIDEO 生成次数，也不自行授予制作许可。

官方公共 API 不需要注册，但遵守 [Wikimedia API 访问政策](https://www.mediawiki.org/wiki/Wikimedia_APIs/Access_policy)、[2026 限流规则](https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits) 及内容文件页许可。本机公开 API 搜索已观察到雨声、钢琴各 3 个符合本实现白名单的候选；**真实音频下载未验收通过**：本次网络解析将 `upload.wikimedia.org` 映射到不允许的 `198.18.x.x` 地址，安全下载器按原协议拒绝，未规避公网地址守卫。相关离线 MockTransport、角色隔离、Rights、换版 SHA-1、OGG MIME 和素材库恢复证据见 [S6-15](../history/tasks/S6-15_material-layer-hardening.md)。

Freesound 暂不接入：官方要求开发者申请 API Key，原始文件下载需要 OAuth2，商业应用还需 API 商业使用授权。用户将来明确选择后再注册/核权，不通过爬网页、猜测密钥或预览文件绕过官方要求。Mixkit 当前仅作为人工核实许可后导入本地库的候选，不声称有正式自动下载 API。

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

这里的 `coverage_complete` 表示提交的实际视频区间完整覆盖时间轴，**不等于已验证供应商内部逐帧采样或模型判断正确**。该协议早期软件验证仅用本地合成视频和 scripted/MockTransport 验证完整字节提交、尾部缺陷负例、声音/方言能力检查、缓存与操作身份；该轮未调用真实视频理解服务；当前真实审片准确度、音色自然度和创作质量须按最新具名运行记录判断。相关测试：`tests/production/test_quality.py`、`test_creation_flow.py`、`test_voice_settings_api.py`。

## 独立审片与维护配置

可选完整音视频审片单独配置 `EASEL_REVIEW_MODEL`、`EASEL_REVIEW_BASE_URL`、`EASEL_REVIEW_KEY`、`EASEL_REVIEW_CAPABILITIES`、`EASEL_REVIEW_VIDEO_DIALECT`、`EASEL_REVIEW_CHUNK_SECONDS`（缺省30）。不配置MODEL时使用现有审片服务；配置后不继承创作服务凭证/媒体能力。支持无需鉴权的本地服务，空KEY不会偷用创作Key。错误地址/模型配置阻断运行时初始化，按报错修正，不能静默回退。显式服务使用review-api身份，须通过正式制作服务清单授权；能力目录available只证明配置声明，verified_live=false，实际能力需真实样本验证。manual QC策略不会因填写该配置自动改为full。部署结果见当前状态。

源码中的1080p-h264-2使用medium/CRF18，包含中间编码及最终字幕合成，缓存身份随规格变化；旧job不迁移。该候选本地对照更慢更小，不能据此断言更清晰；上线默认仍等真实横竖屏文字/运动样本。没有4K开关。

新增维护API只读统计及显式镜头缓存预览/清理，不安排定时删除。具体路由、锁、引用和UNKNOWN保护以[实施合同末节](../architecture/contracts.md)为准；清理只运行过隔离测试。记忆索引401需在本机核实配置与影响，不得依据本配置说明擅自改密钥或启用新索引服务。备份、源素材、有效成片及未知回执不在镜头缓存清理范围。



视频视觉协议minimax-video-url不代表音轨可听。能力目录的configured_mode/active_scope/full_av_required/blocking与visual_video区分当前策略和完整音视频能力；available或verified_live=false不能当作真实全审通过。

历史安装/部署命令和各轮探针结果保留在[运行配置原文](runtime-setup.md)，仅供追溯。


## 可选本地SFX语义补充

复用原MaterialSupply、素材目录和SQLite索引；原有效候选足够时不调用模型，仅SFX不足分支可补充。原候选顺序、外部授权回退、必用引用、音效角色及BGM讲话保护保持。覆盖和实测限制见[SFX-01实施记录](../project/tasks/SFX-01_local-audio-search.md)，未承诺所有中文表达命中或实际听音。

可选依赖为`pip install '.[semantic]'`（固定sentence-transformers版本）；模型须预先在本机准备，维护时核对官方revision及文件摘要。运行入口不下载、不启动远程推理或自动重建。当前适配器只接本地BAAI/bge-m3 dense编码器；模型目录应包含官方配置/权重及`easel-model-identity.json`，内容为model_id、revision、dimensions=1024，具体已验revision见任务记录。

本机忽略的.env使用`EASEL_SFX_SEMANTIC_ENABLED=1`、`EASEL_SFX_EMBEDDING_PATH=<本地模型目录绝对路径>`及`EASEL_SFX_SEMANTIC_MIN_SCORE=<该模型实测标定值>`。当前版本实测值0.712只适用于本次固定BGE-M3/标题投影，不应套用其他模型。缺配置、依赖或模型时沿原检索/外部回退，不增加确认步骤；启用配置后仍需正常重启worker加载。设enabled=0即可关闭补充，不删除索引或媒体。模型首次需要时懒加载并复用；本机实测峰值约2.08GiB，部署前应考虑这一资源占用。

显式维护沿原索引API，保留已有业务记录与许可：

```bash
python scripts/index_sfx_materials.py --library outputs/_production/materials --model-path /absolute/model-directory
```

脚本要求已有V2目录，先备份派生索引，再按原可见范围分页更新SFX、跳过新鲜记录；可传owner/profile限定既有范围。共享素材按原scope保存，不复制到每个频道。不同模型/投影版本不得混用，变更后需显式刷新。原目录、音效、配音和作品引用不属于索引重建或回退的删除范围。
