# S6 · 运行配置与真实验收边界

> **HISTORICAL — 原阶段记录/研究，保留当时结论，不表示当前部署、授权或待办。** 当前入口见[主线导航](../../INDEX.md)。

本文记录已实现接入的配置合同。示例均为占位值，不含凭证，不表示已调用真实服务。代码读取项目 `.env` 与进程环境；环境值优先。新增实际模型/配音/生图/生视频调用仍需作品内的对应授权。

**当前正式部署核对（2026-10-20）**：本机长期主线 `easel-v2-rebuild` 的本轮有界修复（基于 `fb309910`，代码及文档随本次提交记录），按用户授权在空闲与一致性备份后重载既有 Web/Worker 与 Gateway；Web 7860 HTTP 200、backend.reload_required=false，受限 easel-work 插件协议2/9工具握手通过。插件配置直接加载仓库源码，无需另复制；内部工作桥仍为 claim/prepare/dispatch/result/end。27张表及89份画像/配置文件内容摘要部署前后一致，未新增生产 Operation。具名证据见 S6-14A 本轮部署补记；仅健康检查通过，未执行任何 E2E、真实恢复/制作或 Creator 审阅。

## 本地启动与体验

当前唯一开发/运行根为 `/Users/xgx/Projects/Easel`，服务为 `com.easel.web` / 7860，已有 `.venv`。下列仅供首次配置参考，已有服务运行时不再启动第二个 Web/worker；A2～A4最初只在隔离环境运行；A7正式部署状态见下节：

```sh
cd /Users/xgx/Projects/Easel
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[production]'
npm --prefix web/frontend ci
npm --prefix web/frontend run build
EASEL_PRODUCTION_ENABLED=1 .venv/bin/easel web --port 7860
```

Windows 首次配置时使用相应 `.venv\Scripts\python.exe` / `easel.exe`，PowerShell 先设置 `$env:EASEL_PRODUCTION_ENABLED="1"`。外部 `ffmpeg` 与 `ffprobe` 须在 PATH，字体须按下文明确配置。Web 已运行持久 worker，无须同时再启动 CLI worker。无 Web 时可运行 `easel production worker --root <项目绝对路径>`；`easel production status --root <项目绝对路径>` 为只读状态检查。

新前端的主创作入口位于对话笔菜单，视频创作、创建导演、创建频道三项并列；左侧独立视频创作菜单已移除，方案/进度/审片共用卡片。A2～A4源码与隔离验证完成，A7已受控部署正式桥及后端；不能仅通过刷新旧服务宣称完成验收。第五轮正式API自动成片、零人工恢复的证据保持独立；Creator尚未接受，自动语义QC仍未测，见[S6-14](../../project/tasks/S6-14_integration-release.md)。

新 V2 数据存于本项目 `outputs/_production` 和 `outputs/works`；首次启用创建新库，不读取 V1 历史运行库。停止 Web 后任务可由同库 worker 恢复；取消按钮才表示用户取消。不要手动删除这两个目录来解决失败。设置 `EASEL_PRODUCTION_ENABLED=0` 停用新入口，不卸载旧聊天能力。

### 2026-10-18 · A6仅前端本机展示（历史快照）

用户授权部署本次前端供实际查看，暂不调用付费服务。界面版本231b5993：本机7860直接从web/frontend/dist按请求提供文件，已核对HTTP200的index及JS/CSS字节与该版本构建一致；三个对话管线入口可见，侧栏独立视频创作项已移除。无需重启Web或Worker；浏览器只新建空聊天并打开笔菜单，未选择管线、发送聊天或提交制作/保存/接受动作。查看入口为[本机Easel](http://127.0.0.1:7860/)→新对话→笔按钮“看看能做什么”。

此处仅表示静态前端已生效：正式capabilities仍返回backend.reload_required=true；后端未重载，正式OpenClaw受限配置未部署，不能把可见菜单当作正式工具桥可用或完整创作验收。后端部署与真实调用继续独立授权。

## S6-14A受限视频对话配置合同

- Web需`EASEL_PRODUCTION_ENABLED=1`及协议2持久桥；设置独立`EASEL_WORK_BRIDGE_TOKEN`（至少24字符），仅插件可用，不授予confirm/grant/accept等普通API权限。
- 视频对话显式读取项目.env与进程环境（环境优先）的`EASEL_VIDEO_GATEWAY_URL`（`http://127.0.0.1:<实际Gateway端口>`）与`EASEL_VIDEO_GATEWAY_TOKEN`。不得把示例端口或其他环境凭证直接复制到正式运行；缺配置/插件或协议不符返回明确不可用，不切普通main或CLI。
- 原生插件`agents/plugins/easel-work`配置`protocolVersion=2`，内部Agent为`easel-video`，工具白名单严格为9个具名工具（包含 `easel_pipeline`）。HTTP目标`openclaw/easel-video`，原生session绑定来自可信钩子，不能用自造session-id请求头代替。
- `scripts/prepare_video_workspace.py --destination <全新目录> --patch-file <全新补丁文件>`只生成受审查的SOUL/产品规则及**待合并补丁**，不安装、不覆盖原配置、不启动服务。补丁里的凭证是占位值；合并时须保留原main配置、模型、plugins.allow及load.paths已有成员，不能直接整体覆盖数组或运行全量sync。A7只将审查后的增量合并到正式配置，未用全量sync覆盖main。
- 正式部署前需核实实际既有插件、自动记忆和工具策略合成结果，不能把隔离探针的无其他插件组合当成正式环境权限已验收。A7迁移4已在一致性备份后执行；后续部署仍须备份、重载唯一com.easel.web并核对`backend.reload_required=false`。不另启7870。
- 无Work时可持久保存频道/导演创建提议；频道保存不建空Work。参考视频分析/首版生产仍由原Worker和服务授权决定。模型只能提出长期变更，实际保存经展示具体提案后由下一真人回合 `answer` 确认，旧卡接口仅作独立兼容入口。
- 参考导入仅支持公开HTTPS视频直链、最多100MB；内网/保留地址、凭证URL及重定向越界拒绝。失败/UNKNOWN不自动重抓；平台网页、登录媒体和其他来源可改为本地上传，A7实际使用官方公开参考的本地Web上传；受控直链导入仍按上述限制执行。

离线验证命令：`.venv/bin/python scripts/validate_video_conversation.py --root <全新系统临时目录>`。该脚本使用临时原生Gateway、Web、SQLite和本地假模型，关闭子进程后输出脱敏结果；不读取项目.env、不启动生产Worker。`--serve`仅供隔离浏览器检查，用完停止其测试进程；不得当生产启动器。

### A7正式接入与自有管线

A7用户已授权正式配置合成与真实模型创作。当前easel-video受限工作区与协议2工具桥已安装到既有Easel Gateway，新增独立桥凭证、启用带认证的HTTP聊天端点；原main的模型/技能/工具配置保留。普通聊天HTTP探针与发送同步带Gateway认证，避免原入口因启用认证退化。配置、.env与SQLite已一致性备份到本机私有目录，正式库迁移4并重载唯一com.easel.web；加载状态仍以capabilities为准。

A7 当时的工具为8项；当前协议2已扩展至9项并通过正式握手。正式插件组合存在多注册实例，票据按端点/Agent/协议/凭证共享，并保持原生会话/调用身份匹配、单次消费与end撤销；未放宽模型授权或让其直接执行旧产线。自有管线与原片包装入口区分，受限作品聊天不展示通用技能。

导演参考可明确选择analysis_scope=visual，仅reference输入允许，提交真实抽样画面并记录音轨未分析；后续Planning遵守此参考范围。默认full仍提交实际音轨并校验模型audio能力。visual不等同于完整视听分析、逐帧理解或自动语义QC；必用素材不能降低观察范围，首版与导演接受仍由Creator审阅。真实结果及历史失败只维护在[S6-14A A7](../../project/tasks/S6-14A_conversation-integration.md)。

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
**主工作区代码版本检查（防旧 Worker）**：V2 仅由 `/Users/xgx/Projects/Easel` 的 `com.easel.web` 启动，修改任何 `easel/production/**/*.py` 后，进程内 Python 对象并不会自动热重载。正式 `GET http://127.0.0.1:7860/api/production/capabilities` 的 `backend.reload_required` 专门指示启动后有无生产源码变更；`true` 时，创建/规划/确认/恢复等新业务命令应返回 `503 / backend_reload_required`，不可继续用旧模型处理。应先核实数据库无在途调用，再执行 `launchctl kickstart -k gui/$(id -u)/com.easel.web` 重启唯一服务，直至 `backend.reload_required=false`。单独的 HTTP 200 不代表新代码已加载；取消及人工接受入口仍可用于已有作品恢复。此检测不对 `.env`、凭证、资产和文件渲染缓存作快照，修改配置仍按上述规则重启服务。

MiniMax M3.1 完整 Planning 可能超过 120 秒；`EASEL_PRODUCTION_MODEL_TIMEOUT_SECONDS` 默认 900 秒，合法区间 120～1800，且纳入模型配置摘要。超时仍按未知结果处理，不能因增加预算而重发原请求。

**首次后端试片与运行槽**：当创作模型只有真实 `text,image,structured` 能力、没有原生音频输入时，Edit 可对实际 FFmpeg 媒体进行有界音轨技术测量并附注 `technical_only_unverified`，以生成内部待审预览；它不能证明音乐合适、SFX 听感、音画同步。完整语义 QC 仍依下述有声视频协议，没有就保持 `not_tested / needs_decision`。模型写到 `required_features` 中的非 FFmpeg 能力/事实备注不当作已支持能力，改为持久未验证审片备注。启动 V2 Worker 前先核对端口与现有运行作业，一次只保留一个 Web/Worker 服务实例；停止请求必须实际进入终态，不要连续创建多项 `run_detached_process` 长驻 Job 占满 Runner 并发槽。

## 临时人工审核模式（S6-14 明确授权）

当前若只需先把真实视频交给 Creator 人工审核，可以在 V2 独立运行环境的 Git 忽略 `.env` 中设置 `EASEL_PRODUCTION_QC_MODE=manual` 并重启 **唯一 V2 Web/Worker**。默认 `full`；不配置时自动语义 QC 的严格门禁保持原行为。此开关暂时注释/绕过的是**最后自动音视频语义 QC Gate**，并未删除代码和检查合同，后续可把设置改回 `full` 并重启恢复。

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

声音协议必须显式配置，不能写 `auto` 猜路由。`http-speech-v1`（兼容既有名称 `speech-http-v1`）沿用 `/audio/speech`：POST model/input/voice/response_format，可选 speed/instructions，返回音频二进制，base_url不带该后缀。S6-15 新增 `minimax-speech-v1`：base_url明确到 `/v1`，适配器追加 `/t2a_v2`，非流式请求 text/voice_setting/audio_setting，读取有界 JSON/hex 音频；当前明确支持 wav/mp3/flac、速度0.5～2，不支持通用instructions。模型与voice_id必须真实配置，不自动选择或换声。两个协议共用原Operation/句段/回执/真实时长校验，未知结果不重发；异步URL响应与克隆注册API不能冒充上述协议。配置目录和执行共用静态校验，缺Key/未知engine不会仅因有voices数组就标可用。原生MiniMax目前只有MockTransport+真实合成音频的软件验证，不代表已向用户账户发送或已验证自然音色。

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

当前编辑器使用本机外部 `ffmpeg/ffprobe`，不自动安装、不随本任务分发二进制。支持范围、许可证和限制见 [ADR-S6-009](../../architecture/decisions/ADR-S6-009-local-editor.md)。所需编码器为 `libx264/aac`，程序检查必要滤镜；字体绘制用 Pillow，未要求 libass/drawtext。运行时缺少必要能力会返回明确错误。

本轮真实执行过 macOS arm64 的 FFmpeg 8.1 / Pillow 12.3.0 合成媒体测试，包括独立 900 秒用例。声音 HTTP 协议、持久任务、字幕预览与缓存使用 MockTransport 和合成 WAV，**未调用真实声音服务**；自然听感、说话人一致性、真实接缝/节奏及字幕语义对齐仍须真实作品验收。Ubuntu/Windows 及完整规格组合不据本机结果宣称通过。完整命令与结果见 [S6-09](../tasks/S6-09_editor-adapter.md)、[S6-10](../tasks/S6-10_voice-subtitles.md)。

## 素材、图片和视频生成

素材库是新的 V2 私有库：`outputs/_production/materials/`。正常运行只接收本次登记输入和受控下载，不自动扫描 V1 库或迁移旧生产数据库。2026-10-17 用户另行授权的**显式本地素材副本导入**见下节；它不导入旧运行状态。实际素材复制至作品 `assets/`，来源/许可/署名和稳定句柄进入作品引用；共享库提升需要明确复用许可。

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

代码迁入、协议原始来源、许可证与未测边界详见 [素材迁入记录](../../../../easel/materials/MIGRATION.md)。素材/HTTP 协议和真实本地视频检查通过离线 fixture 与 MockTransport；真实 Pexels/MiniMax 服务和生成质量 **NOT_TESTED**。


### 2026-10-17 · 用户授权的本机素材来源与配置复用

本轮用户明确允许把本机已配置服务接入 V2，并迁入经核验的本地素材副本。配置来源为历史工作树 `/Users/xgx/Projects/Easel/.env`，已将 Pexels、Pixabay、Unsplash、MiniMax 及现有 OpenAI 兼容模型的可映射项写入**当前 V2 工作树自身忽略的** `.env`，权限 `0600`；原配置不改，凭证不入代码、日志或 PR。没有因发现模型/Key 而授权调用；`EASEL_PRODUCTION_MODEL_CAPABILITIES` 暂为空，非流式 JSON、视频审片协议与实际声线均待真实验收；MiniMax 视频型号、生成 Rights 和声音目录未从历史配置臆造。

| 来源 | V2 当前行为与限制 |
| --- | --- |
| Pexels | 现有图片/视频检索适配器，按素材专属 Rights、域名/下载/技术校验准入 |
| Pixabay | 新增图片/视频检索适配器；API 搜索回执有界保存于 `outputs/_production/provider_cache/pixabay/`，24 小时内复用；POSIX 下缓存文件模式 0600（Windows 需依赖目录 ACL）；不以有 Key 代表真实服务已经验收 |
| Unsplash | Web「视频创作」页有主动参考图检索入口，后端 `POST /api/production/material-sources/unsplash/preview-search` 仅在明确操作时请求；返回官方图片热链接、摄影师及 Unsplash 署名链接，不下载、不自动加入制作候选。用户选择后的下载事件追踪/实物导入未接通，不冒充已支持 |
| MiniMax | 生图 `image-01` 可登记为配置身份，但没有真实 Rights 许可与每片调用次数前不可提交；生视频型号与额度未明确，因此维持不可用 |
| OpenAI 兼容模型 | 从已有 `OPENAI_BASE_URL/OPENAI_MODEL/OPENAI_API_KEY` 映射到 V2 `EASEL_DIRECT_API_*`，仅静态验证身份，不推断原端点具备多模态/视频审片能力 |

本机旧素材库目录存在历史 SQLite catalog，但没有直接在 V2 打开/升级它。旧本地素材根经只读盘点仅有 1 个 MP3 和素材、Rights JSON sidecars；按实际 SHA-256、来源、CC BY 4.0 署名证据及本机媒体技术检查，经**显式** `python -m scripts.import_local_materials --legacy-env /Users/xgx/Projects/Easel/.env --execute` 安全复制进 V2 内容寻址库。默认不带 `--execute` 时只做 dry-run；脚本不修改原素材或原 SQLite 库。导入的音频仅经用户本次复用授权设为 `owner_shared_import`；其他未明确许可的历史素材和用户上传不扩大作用域。重复执行不会重复拷贝有效字节。曾登记但署名不足的旧候选保留为被拒绝事实，修正后独立记录符合资格的版本，禁止以删除记录换 PASS。

本机实测：新 V2 目录下 Pexels、Pixabay 配置存在且自动供料适配器已装配；Unsplash 仅 preview，生成 Rights 可用计数为 0。唯一 MP3 在**有画像/无画像的不同作品**中均能被检索为 1 个合格候选，使用权状态 `CONDITIONAL`，制作/导出必须继续携带完整署名；不得把命中等于导演已听取选中。此轮远程检索与真实生图/生视频/配音/模型调用均为 0，真实生产和 Creator 接受仍 `NOT_TESTED`。

## S6-15：五类素材内部衔接

现有 PlanDocument 和 EditProject/AudioClip 外部结构不变。新的任务内部 MaterialIntent 从冻结画像/导演/计划解释短检索词、媒体类型、BGM意图及SFX事件；结果按上下文摘要持久化，重启不重新解释。图/视频仍使用Pexels/Pixabay；BGM/SFX走本地授权素材和已有reviewed_public音频清单，不存在隐含的Pixabay音频API。必要音效缺口返回needs_decision，可选点缀不升级为新的硬性确认环节。

外部供料须在本方案有效授权中选择 provider/model/mode：Pexels、Pixabay及reviewed_public均为 `model=stock,mode=search`；有配置不是授权，撤销后停止下一次检索/下载。既有本地合格资产可直接复用。Unsplash仍是单独主动预览，不自动供料。

作品素材metadata的material_uses区分视觉、音乐及事件音效用途；同一文件可关联多个cue而不覆盖。供料输出仍只有schema_version和asset_ids。编辑前/选中后/渲染前复验具体素材的来源、Rights、范围、字节与引用，工程/导出仅列真正选中的素材。详细架构见[素材层架构](../../architecture/materials.md)，真实服务及G4状态见[S6-15](../tasks/S6-15_material-layer-hardening.md)。

### BGM / SFX 免费音频来源（S6-15 增补）

本次**不新增音频管理界面**。在已实现的本地库优先 + `reviewed_public` 有限清单基础上，新增 `easel/production/providers/wikimedia_audio.py` 两个独立身份：`wikimedia_bgm` 与 `wikimedia_sfx`。由确认 Plan 的 Director MaterialIntent 给出音乐氛围或 cue 查询，Commons 官方 Action API 按 `File:` 音频检索；只处理带官方文件页、音频下载地址、文件 SHA-1 和文件页具体许可元数据的资产。严格仅接受声明为 **CC0 1.0 / CC BY 4.0** 的条目，且许可 URL 必须匹配 Creative Commons 官方域名及相应路径；CC BY 强制保存创作者、原文件页与完整导出署名。ND/NC/SA、未明许可、缺署名或非受信任域名一律不可用于制作。该判断记录的是 Commons 的具体文件页声明，并不代表独立核验创作者拥有全部权利。

下载仍必须经过既有公网 DNS、逐跳重定向、文件大小与 FFprobe 技术检查；Commons 的 `application/ogg` 仅对音频容器开放，**下载字节 SHA-1 也须与查询时的官方文件版本一致**。一旦网络返回私网/保留地址或实际下载不合法，保留音频缺口与原素材，不改为静音、错误用途或无许可 AI 生成。相同来源同许可文件经现有库和 Rights 机制复用，SFX 多事件继续沿用 cue 绑定。该搜索服务不计 IMAGE/VIDEO 生成次数，也不自行授予制作许可。

官方公共 API 不需要注册，但遵守 [Wikimedia API 访问政策](https://www.mediawiki.org/wiki/Wikimedia_APIs/Access_policy)、[2026 限流规则](https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits) 及内容文件页许可。本机公开 API 搜索已观察到雨声、钢琴各 3 个符合本实现白名单的候选；**真实音频下载未验收通过**：本次网络解析将 `upload.wikimedia.org` 映射到不允许的 `198.18.x.x` 地址，安全下载器按原协议拒绝，未规避公网地址守卫。相关离线 MockTransport、角色隔离、Rights、换版 SHA-1、OGG MIME 和素材库恢复证据见 [S6-15](../tasks/S6-15_material-layer-hardening.md)。

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

这里的 `coverage_complete` 表示提交的实际视频区间完整覆盖时间轴，**不等于已验证供应商内部逐帧采样或模型判断正确**。本轮仅用本地合成视频和 scripted/MockTransport 验证完整字节提交、尾部缺陷负例、声音/方言能力检查、缓存与操作身份；未调用真实视频理解服务，真实审片准确度、音色自然度和创作质量仍未验收。相关测试：`tests/production/test_quality.py`、`test_creation_flow.py`、`test_voice_settings_api.py`。

## S6-14A A5离线复现（不操作正式服务）

完整探针：`.venv/bin/python scripts/validate_conversation_a5.py --root /tmp/easel-a5-<new-id>`。必须使用全新系统临时目录；脚本创建实际Web、原生Gateway、临时库和Worker，以本地脚本模型/合成图片与音轨运行真实FFmpeg、技术QC、模拟审片和续作。聊天模型仅允许回环测试端口，执行模型为进程内脚本；不读取项目.env运行生产、不部署插件或修改正式库。模拟授权与接受只作用于临时库。

浏览器使用`--serve`；若检查代码后需要重启隔离fixture，先向该脚本的确切PID发送SIGINT，等待其finally关闭Gateway/Web，再用相同root加`--serve --resume-isolated`。只允许带隔离标记的临时根，沿用原临时端口、DB、上传、Profile、会话与原生运行段，生成新的测试凭证和工作区；不得将该选项用于正式数据。测试完成同样用SIGINT回收，不留下第二套常驻生产服务。

组合权限探针：`.venv/bin/python scripts/validate_video_conversation.py --root /tmp/easel-a5-bridge-<new-id> --memory-plugin`。该选项仅在临时配置启用原生memory-core并尝试其工具旁路；实际清单仍须严格8项。正式已安装插件/slash/自动记忆组合与真实模型的完整交互仍需受控部署验收；A5离线通过不授权安装、重载或付费。运行结果与截图见[S6-14A](../../project/tasks/S6-14A_conversation-integration.md)。


### A8局部修订与纯重新导出（2026-10-19）

原Web具体版本可勾选保留声音后提交局部反馈；缺口只补该Plan指定场景库存，不重新Planning/TTS。导出修复可使用版本卡“只重新导出此版本”，精确复用登记工程，不调用修订模型/素材/配音；既有语义失败或明确画面缺口不能通过重新导出绕过。QC沿用正式配置，本次仍manual_review_only，技术pass不表示自动语义pass。A8最终建议审阅原对话版本4，中间版保留；完整PCM与原版一致。部署仍先核查全库在途再重载唯一com.easel.web，backend.reload_required=false；不新建7870或修改Gateway配置。完整数据与限制见[S6-14A A8](../../project/tasks/S6-14A_conversation-integration.md)。


## 单 main 正式装配（2026-10-20，替代旧双Agent装配）

只保留main现役配置；原main工作区、模型/思考设置、技能和通用工具规则保留，只向其显式allow追加九个业务工具名。easel-work设置agentId=main、protocolVersion=2，开启allowConversationAccess及allowPromptInjection；其他插件不删除。插件按受控会话namespace限定回合，普通main看不到业务执行工具；管线执行前需要服务端认领、产品指令替换、九工具收窄和逐次票据核验。新管线使用main现有对话模型配置，不再使用退休easel-video的独立对话模型/思考覆盖；作品Planning/媒体Provider配置不改。旧Agent数据与配置快照保留，不为其建立迁移兼容路径。

部署须先核对所有生产任务、原生回合、普通聊天与Gateway活动为空；备份现有配置/数据库，再停用awei-creative与easel-video注册，原子更新插件配置并重载既有Web/Gateway。验收看agent_id=main、permission_policy=main-pipeline-v1、协议2/九工具、Web新鲜度和保护数据摘要。不能把普通HTTP200或任何400当成功，空消息探针只接受具名Missing user message错误。


## S7新增配置与运维边界（2026-10-23，尚未部署）

可选完整音视频审片单独配置 `EASEL_REVIEW_MODEL`、`EASEL_REVIEW_BASE_URL`、`EASEL_REVIEW_KEY`、`EASEL_REVIEW_CAPABILITIES`、`EASEL_REVIEW_VIDEO_DIALECT`、`EASEL_REVIEW_CHUNK_SECONDS`（缺省30）。不配置MODEL时使用现有审片服务；配置后不继承创作服务凭证/媒体能力。支持无需鉴权的本地服务，空KEY不会偷用创作Key。错误地址/模型配置阻断运行时初始化，按报错修正，不能静默回退。显式服务使用review-api身份，须通过正式制作服务清单授权；能力目录available只证明配置声明，verified_live=false，实际能力需真实样本验证。manual QC策略不会因填写该配置自动改为full。本轮未改本机.env或重启服务。

源码中的1080p-h264-2使用medium/CRF18，包含中间编码及最终字幕合成，缓存身份随规格变化；旧job不迁移。该候选本地对照更慢更小，不能据此断言更清晰；上线默认仍等真实横竖屏文字/运动样本。没有4K开关。

新增维护API只读统计及显式镜头缓存预览/清理，不安排定时删除。具体路由、锁、引用和UNKNOWN保护以[实施合同末节](../../architecture/contracts.md)为准；清理只运行过隔离测试。记忆索引401需在本机核实配置与影响，本轮不改密钥或启用新索引服务。备份、源素材、有效成片及未知回执不在镜头缓存清理范围。


### 2026-10-23审片能力核实与配置修正

主服务当前使用manual+visual-review，完整音视频不可用不等于该人工路径任务失败。capabilities.review现在显式投影configured_mode、active_scope、full_av_required、blocking，并另列visual_video；原available仍只表示完整音视频配置就绪，静态目录verified_live不冒充真实服务验收。

新增 `EASEL_PRODUCTION_VIDEO_DIALECT=minimax-video-url`，兼容标准video_url输入，不发送Qwen专用参数。纯视觉可用；有声音轨要求仍严格拒绝，不能通过手填audio绕过。现有MiniMax端点/Preview模型在一次真实合成视频探针正确识别画面、明确无法听音，因此本机只设置image,video，不修改manual模式或创作模型。音视频全审需另有经验证的服务/配置，不以抽帧、ASR或用户接受替代。调用证据及本机部署结果见[接口调试01](../../project/tasks/runs/2026-10-23-backend-api-01.md)。
