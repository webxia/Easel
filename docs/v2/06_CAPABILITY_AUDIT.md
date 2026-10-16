# S1｜Easel 当前代码能力审计（仅现状）

> **范围声明**：本报告只说明仓库**当前已经存在的代码、流程和可验证事实**。用户明确说明**新需求尚未正式录入**；本轮不做新需求对照，不提出新的系统设计，不把过去的二开设想作为当前实现的评判标准。
> **核查日期**：2026-10-16；**被审计版本**：`easel-v2-rebuild@8eeafb6b9bf62b26e2077057cbebe45721f5d464`，官方原始基线 `4ffdc980`。
> **方法**：逐层查阅仓库源码、内置 Skill、前端组件、相关测试及官方随仓说明；执行静态/离线检查。**未调用真实模型、生成媒体、发布内容或改动生产配置。**
> **证据分级**：`源码存在` 说明查到了明确入口/逻辑；`文档声明` 说明 Skill/说明书提出了流程但并非本轮实测；`未核验` 不等于不存在或不可用。

## 1. Git 基线与源码范围

- 当前审计对象是实际运行的 V2 工作基线，不是已包含所有后续上游提交的“最新官方”。
- 开始 S1 前按 Git 规范执行 `fetch upstream` 和差异比较：相对 `8eeafb6b`，`upstream/main` 多 **22 条上游提交**（当时比较 `git rev-list --left-right --count HEAD...upstream/main = 3 22`），涉及 Agent 故障诊断、原生会话、取消/回放等。**未合并、未审计这 22 条更新的完整实现语义**；不得把它们写作当前 V2 已具备的能力。
- 读取范围：`easel/`、`web/app.py`、`web/frontend/src/`、`agents/workspace/`、`profiles/_template/`、`skills/builtin/` 相关技能、`skills/shared/scripts/` 主要工具与部分测试。大型内置 SDK 的所有子文件未逐一查阅。
- 没有改动业务源码；本报告是**版本固定的静态快照**，以后合并上游或修改核心模块，应重新核对相关结论。

## 2. 当前系统的实际结构

```text
React Web (App / Chat / Skills / Profile / Outputs / Publish ...)
  └── FastAPI: web/app.py
       ├── 对话通道 → 直连模型 API / OpenClaw / Codex / OpenCode / ACP
       ├── 画像管理 → easel/persona.py + profiles/<画像>/*.md
       ├── 技能列表 / 调用 → agents/workspace + skills/builtin
       ├── 媒体能力 → skills/shared/scripts (image / video / TTS / subtitle / mix ...)
       ├── 运行与产物 → outputs/<项目>/.easel.json + 文件/媒体接口
       └── 其它现有业务 → 账号、发布、统计、日历、想法等
```

| 模块 | 已确认的现有实现 | 主要源码入口 |
|---|---|---|
| CLI / 环境 | 命令行、环境检测、Gateway 与技能入口 | [CLI](../../easel/cli.py)、[doctor](../../easel/commands/doctor.py) |
| Web 服务 | [FastAPI](../../web/app.py) 为单一入口（约 **5479 行**）；AST 静态盘点约 **68 条 /api/** 路由，涉及对话、画像、媒体、Skill、账号与发布 | [web/app.py](../../web/app.py)（1182–1372、3171–3951、3954–4130） |
| Web 前端 | React 聊天、问答卡、文件附件、Profile 管理、内容库预览、账户、发布等现有页面 | [App.tsx](../../web/frontend/src/App.tsx)、[ChatPage](../../web/frontend/src/components/ChatPage.tsx)、[OutputsPage](../../web/frontend/src/components/OutputsPage.tsx) |
| 画像 / Profile | 多文件画像（identity/style/audience/platforms/preferences/memory）；Web/CLI 通过统一工具读取和关联当前会话 | [persona.py](../../easel/persona.py)（16–82、104–112）、[画像 API](../../web/app.py)（1292–1350）、[模板](../../profiles/_template/README.md) |
| Agent 底座 | 支持 API、OpenClaw、OpenCode、Codex、ACP；原生 ID 会话绑定、沙箱选项和权限申请 | [Adapter 契约](../../easel/harnesses/base.py)、[Codex 适配器](../../easel/harnesses/codex.py)、[配置/会话记录](../../easel/harnesses/store.py) |
| Agent 指令 | 共享 SOUL / AGENTS 文档，按引擎注入上下文；产品 Agent 通过说明选择 Skill | [产品 Agent 规则](../../agents/workspace/AGENTS.md)、[上下文组装](../../easel/harnesses/workspace.py)、[Prompt Stack](../prompt-stack.md) |
| 技能与媒体 | 技能入口文档、共享 Python 媒体处理脚本、图像/视频生成 Provider 适配、音频、字幕、合成 | [视频生成 Skill](../../skills/builtin/ai-video-gen/SKILL.md)、[模型注册表](../../skills/shared/scripts/model_registry.py)、[TTS](../../skills/shared/scripts/tts.py) |
| 产物/展示 | 按 `outputs/<项目>` 组织文件和 `.easel.json`；内容库读目录树、元信息、成品路径并提供媒体接口 | [manifest.py](../../skills/shared/scripts/manifest.py)（90–154）、[Web 产物接口](../../web/app.py)（1055–1128、3954–4022） |

这里“支持”是代码层实现/声明，**不是所有功能都在本次实机执行通过**。

## 3. 已存在的主要用户操作链

### 3.1 对话与 Agent 执行

1. 前端 [App.tsx](../../web/frontend/src/App.tsx) 保存/切换 Chat Session；[store.ts](../../web/frontend/src/lib/store.ts)（12–20、71–128）将对话展示状态放在浏览器 `localStorage`，并记录可恢复的 pendingTurnId。
2. `POST /api/chat/stream` 接收 message、persona、sessionId、turnId 和附件引用；[web/app.py](../../web/app.py)（2556–2567、3171–3229）决定运行底座，校验附件所属会话，形成 Agent 输入。
3. [persona.py](../../easel/persona.py) 将选中画像通过消息前缀注入；[harness workspace](../../easel/harnesses/workspace.py) 加载产品 Agent 文档（SOUL、AGENTS）及运行时项目根/工具路径；[Codex 适配器](../../easel/harnesses/codex.py) 走原生 app-server。
4. 对同一会话设置锁、绑定原生 Agent 会话；后端将一轮完整输出保存到 `outputs` 会话记录，提供 SSE 事件重放与 `/api/chat/last` 查询，避免浏览器断线就丢本轮回答。见 [web/app.py](../../web/app.py)（2866–2881、2928–3017、3108–3156）。
5. [权限适配器](../../easel/harnesses/permissions.py)（22–70）控制可自动批准的普通动作，超范围权限仍需用户确认。

**边界事实**：这是对话、Agent 原生会话和 SSE 的处理机制；不能仅凭这些函数证明某个视频生成 Provider 的任务具有相同的持久化/重试语义。

### 3.2 Skill 驱动的制作和产物归档

- `GET /api/skills` / `GET /api/skill/{name}` 返回技能列表和说明；`POST /api/skill`（[web/app.py](../../web/app.py) 3933–3951）通过当前 Agent 指令调用指定 Skill。仅 API 对话模式不直接执行需要本机工具的 Skill。
- [产品 Agent 规则](../../agents/workspace/AGENTS.md) 让执行者按任务需要读取内置 Skill；媒体具体操作由 [共享工具脚本](../../skills/shared/scripts/model_registry.py) 和各 Skill 的脚本承接。
- [manifest.py](../../skills/shared/scripts/manifest.py) 的步骤记录包含 layer、skill、status、outputs、upstream 和 summary，并原子写入项目元信息；[web/app.py](../../web/app.py) 则从输出目录读取项目卡、文件树、图片/视频/音频。
- 前端的 [OutputsPage](../../web/frontend/src/components/OutputsPage.tsx) 负责内容库的媒体查看、下载/删除等可见操作；它不是通用任务编排后台。

### 3.3 当前存在的两种不同视频流程

| 流程 | 既有输入 | 已定义/实现的步骤 | 输出/状态 |
|---|---|---|---|
| **auto-short-video** | 主题/文案；可选风格、时长、图像/配音/BGM | [Skill](../../skills/builtin/auto-short-video/SKILL.md)（14–75）指引 Agent 调脚本、配图/视频片段、TTS、字幕、BGM；[assemble.py](../../skills/builtin/auto-short-video/scripts/assemble.py)（292–445）以 FFmpeg 拼接 storyboard | `outputs/<项目>/final.mp4` 与中间素材；Skill 有画幅和付费请求前确认说明 |
| **video-production** | **已有的完整原片** | [Skill](../../skills/builtin/video-production/SKILL.md)（3–28、58–125）采用内置 video-pipeline-sdk，对原片摸底、转录、分场、设计、预览、渲染、质量门；[wrapper](../../skills/builtin/video-production/scripts/video_pipeline.py)（201–311）管理命令 | 有 start / pending / answer / resume / status；提供 Gate 报告、review-pack、两个人工检查点与 MP4 |

- 第一条是**从主题组织短视频**，编排逻辑主要写在 Skill 流程中；有真实的 [FFmpeg 合成器](../../skills/builtin/auto-short-video/scripts/assemble.py)，可选静态图片/Ken Burns 和视频片段。
- 第二条是**把现有原片后期包装**，它依赖自己的运行态、质量门和 SDK；文档明确使用 Remotion 依赖，不是同一条从主题出片的脚本。
- 这两条路径的输入、工作方法、运行状态及人工介入位置**不同**。当前代码中它们以各自 Skill 的方式存在；本轮没有真实运行，也没有证明哪条在实际环境下已完整出片。
- `easel/`、`web/`、`agents/`、`skills/` 的已检查执行代码内，**没有找到名为 Hypit 的实现或引用**（搜索排除了第三方 SDK vendor 的未读细节）。这里仅是源码检索结果，不涉及是否未来应该使用。

### 3.4 已有媒体 Provider、来源指引与安全机制

- [media registry](../../skills/shared/scripts/model_registry.py)（24–110）维护 image/video/music 等模型 Provider 的配置元数据；[ai_video.py](../../skills/shared/scripts/ai_video.py) 含多 Provider 的任务提交、轮询和视频下载；[ai_image.py](../../skills/shared/scripts/ai_image.py) 含 AI 图片调用实现。
- [auto-short-video Skill](../../skills/builtin/auto-short-video/SKILL.md) 的画面路径主要描述自带素材、AI 生图/生视频和图卡兜底。
- [版权风险 Skill](../../skills/builtin/skill-risk-scanner/SKILL.md) 及其 [版权参考](../../skills/builtin/skill-risk-scanner/references/copyright-guide.md) 提及 Unsplash/Pexels/Pixabay；本次未在相关媒体共享脚本中找到专用 Pexels/Pixabay 自动检索 Provider。不能把来源说明文档误写成图库搜索 API 已实现。
- [创作 Agent 规则](../../agents/workspace/AGENTS.md) 有付费动作确认与成品自检要求；[Codex 权限模块](../../easel/harnesses/permissions.py) 有可执行权限边界；风险 Skill 对素材版权风险可作定性分析。不同机制的执行范围不相同。
- [ai_video.py](../../skills/shared/scripts/ai_video.py) 中 `timeout=900` 是**等待媒体任务的超时秒数**，不能推导为某条视频可渲染 900 秒。

## 4. 当前工程特征和需要区分的事实

| 观察 | 源码依据 | 边界说明 |
|---|---|---|
| Web API 集中于单个 Python 文件 | [web/app.py](../../web/app.py) 文件长度约 5.5k 行，包含对话、配置、输出、账号、发布等 | 这是现有组织方式；本轮未评判是否需要拆分服务 |
| 对话展示状态与 Agent 原生状态分别保存 | [store.ts](../../web/frontend/src/lib/store.ts)、[harness store](../../easel/harnesses/store.py)、[web/app.py](../../web/app.py) | 浏览器切换/清空本地数据与删除原生会话不是同一操作 |
| 存在多种持久化数据 | `outputs/.easel.json`、[manifest.py](../../skills/shared/scripts/manifest.py)、会话快照、视频 SDK 运行态 | 这些是不同模块的状态，不能不经核查就视作统一任务账本 |
| 存在多个质量/风险检查位置 | [video-production](../../skills/builtin/video-production/SKILL.md)、[risk-scanner](../../skills/builtin/skill-risk-scanner/SKILL.md)、合成器的 FFmpeg/ffprobe 校验 | 检查点的触发条件和证据类型不同；本轮没有端到端审核实际作品 |
| 共享创作 Agent 文档从指定目录加载 | [workspace.py](../../easel/harnesses/workspace.py)（10–42）读取产品 `agents/workspace/*.md`；原生 Agent cwd 是项目根（[web/app.py](../../web/app.py) 2979–2986） | 是否额外发现根开发用 `AGENTS.md`，本轮**未调用真实 Agent 验证**，只确定现有静态组装逻辑 |

## 5. 可复核的代码证据和验证范围

**核心查阅入口**：`web/app.py`、`web/frontend/src/App.tsx`、`web/frontend/src/lib/store.ts`、`easel/persona.py`、`easel/harnesses/`、`agents/workspace/AGENTS.md`、两条视频 Skill 及其脚本、`skills/shared/scripts/model_registry.py`、`skills/shared/scripts/manifest.py`、`skills/shared/scripts/ai_video.py`。

**本地离线检查**：

- `python scripts/validate_document_paths.py`：文档链接与仓库路径检查 **PASS**。
- `python scripts/validate_skills.py`：**PASS**，114 项 Skill 与发布契约。
- `python scripts/validate_skill_commands.py`：**PASS**，306 条文档命令。
- `python -m pytest -q tests/test_document_paths.py tests/test_harness_workspace.py tests/test_persona_security.py tests/test_ai_video_env.py`：**41 PASS**，2 条非阻断依赖弃用警告。

**未核验**：真实 OpenClaw/Codex 模型回合、外部图像/视频 Provider、图库真实素材检索、用户账户发布、整片制作、人工审片、全部 Skill 的逐项执行、上游 22 个新提交的回归。代码/说明中的“可以”不能等同于本次实际运行成功。

## 6. 本轮结论与边界

**当前 Easel 是一个以 React Web、FastAPI、Profile、可切换 Agent 执行底座和 Skills 为中心的创作工作台。** 视频相关能力既包含从主题组织短片的 Skill+FFmpeg 路径，也包含原片包装+内置 SDK+质量门路径；现有内容库按项目文件和元信息展示产物，聊天有单轮断线恢复能力。

此结论仅描述**当前可见的架构与实现**，**没有使用任何尚未正式录入的新需求来比较“缺什么、该改什么”**。新需求正式录入后，应将这份“现状基线”作为独立输入，再开展需求差距分析；不要修改本审计的既有事实以迎合未来目标。

**下一步建议仅作为流程提示**：先审阅这份当前实现盘点，再决定何时录入新需求；上游 22 个提交的合并仍单独需要用户确认。
