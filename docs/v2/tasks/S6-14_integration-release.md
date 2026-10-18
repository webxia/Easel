# S6-14 · 首次真实生产与完整范围验收

状态：**PARTIAL / 第五轮 REAL_API_PRODUCTION_PASS / ZERO_MANUAL_RECOVERY_PASS / CREATOR_REVIEW_PENDING。** 自动音视频语义 QC 保持 NOT_TESTED，A7独立真实Web生产已通过，质量问题与Creator接受仍待审阅，S7矩阵未执行。S6-15 已 CLOSED/COMPLETE；历史失败保留。本次完成第五轮只读验收归档，并新增 [S6-14A 对话式创作接入](S6-14A_conversation-integration.md)：设计已获准推进 A1，隔离原生工具桥验证通过；A2～A4源码接入已完成，A5完整隔离交互与28项离线判据通过；A7已独立完成正式部署与真实模型Web生产；详见子任务最新记录。
- **依赖**：第一段为 S6-01～11 实际就绪；第二段为 S6-01～13及首次真实闭环就绪。阶段对应见[任务包里程碑](S6_IMPLEMENTATION_PLAN.md#1-基线顺序与交付)。
- **当前排程**：第五轮 API 自主到人工审核已通过，Creator 审片独立待反馈；S6-14A 的 A1～A6研发/隔离验收及A7已授权正式部署/真实Web生产已完成，下一步Creator审片与按具体意见修订。不自动启动第六轮付费 E2E，不以 API 成功代替对话体验验收。
- **需求主/协作覆盖**：V2-EXP-009, V2-EXP-018, V2-EXP-022, V2-EXP-023, V2-EXP-028, V2-EXP-029, V2-EXP-030。
- **目标与合同**：[可执行设计](../15_IMPLEMENTATION_DESIGN.md)；[任务包共同约定](S6_IMPLEMENTATION_PLAN.md#2-每张卡开始与完成的共同约定)。
- **现有实现及验证落点**：`easel/production/`、`tests/production/`、正式后端 API 与 [运行配置](../16_RUNTIME_SETUP.md)；精确软件/真实/人工证据按本卡后续记录读取。
- **当前开发入口**：`/Users/xgx/Projects/Easel` / `easel-v2-main-workspace`；第五轮生产源码基线 `406e523c035fe8da0f1435f4d813defa63653692`，后续A7已实施正式接入，当前 HEAD 以 Git 为准。[旧 PR #8](https://github.com/webxia/Easel/pull/8) 仍为历史分支 Draft，不自动合并。

## 第一段：S6 首次真实生产与审阅

1. S6-01～11 接通后，固定版本、样本、模型/服务、Rights、授权与次数，用已支持输入及本次明确风格从 Web 完整方案确认走到真实素材、制作、自检和可审阅首版。当前许可未包含的服务调用保持未测，不自动补授权。
2. 对照实际步骤、进度、产物与调用记录；关页重开，验证一次可控失败/恢复。危险的重复付费窗口使用替身，不为试验破坏资产或额外收费。
3. 记录真实完整媒体、用户实际审阅、耗时、调用、失败与人工干预。没有研发改代码/改状态/手工补素材救火才可记自主通过；用户未实际接受时接受项不得记通过。
4. 本段可以先于完整频道/导演管理执行，但只证明上述范围。外部审阅记录不等于 S6-12 产品内接受保存、局部修订或完整 T08 已实现；S6-12/13 继续按依赖推进。

**本段通过标准**：真实可审阅作品与版本、Rights/授权/次数、恢复正反证据和 Creator 审阅记录可核对，软件/真实生产/自主/接受分列。该证据用于路线图 S6→S7；任何缺项如实保留，不用静态测试替代真实闭环。

## 第二段：S7 完整范围、质量与发布准入

以下保留全范围验收要求，依赖 S6-12/13 接通，不因第一段通过而省略。

### 实施步骤

1. 软件矩阵覆盖1/90/900秒、四声音、两画幅、三输入及组合、无画像、原声保护、取消/恢复、进度和局部修改；明确实际组合，不能一项存在即全笛卡尔积PASS。
2. Python3.10/3.12与已有Ubuntu/Windows/macOS相关CI运行受测约束、worker/本地媒体冒烟；真实媒体依赖缺失不得skip后宣称支持全部平台。
3. 授权服务/模型/样本/次数事前具名；真实Web首版、局部修改、内容库接受、同导演跨题材与音色自然度记录。生产试验未授权时只完成软件部分，不自动调用。
4. 记录同版本耗时、实际调用、失败与人工干预；软件/真实生产/自主完成/Creator接受分开。研发救火后可调试但自主项FAIL保留。
5. 安装升级/启用开关、备份与停用策略回归，不迁历史库；全关键现有功能保持可用；合并主线或发布另按授权。

### 通过标准与负例

全部软件必测项通过且对应版本明确；真实样片没有未声明手工修复；失败样本保留；语义/音色标准事先确定；未实际接受不记Creator通过。只有相应证据完备才开放能力，不静默缩减正式范围。

## 验证入口（本卡实现相应文件后执行）

两段均按实际覆盖记录命令和结果；下列为完整范围回归入口，不能以软件通过替代真实样片。通用执行规则见任务包。

```bash
python scripts/validate_skills.py
python scripts/validate_skill_commands.py
python scripts/validate_document_paths.py
python -m pytest
node --test tests/frontend/*.test.mjs
npm --prefix web/frontend run lint
npm --prefix web/frontend run build
```

交付要求：按两段及能力范围分列软件/真实/自主/接受报告；任一段未完成时整体 PARTIAL。上线、合并、发布不由测试通过自动授权。

## 历次执行记录（自 2026-10-17 起，按时间顺序）

**2026-10-17 软件实施初始快照（历史，不代表当前状态）**：受测实现 `97ecc67b`，分支 `codex/s6-production`，从 `4525b09d` 接手；基础分批提交 `e923332a`、`97199284`。该时点仅做软件/本地媒体验证、真实付费服务未测；其后同一 Task 已记录真实 MiniMax、素材、TTS、三部 MP4、人工 QC 与恢复证据，最终结论以文末最新记录和 [当前状态](../04_CURRENT_STATE.md) 为准。旧 PR #8 保持 Draft，未合并或发布。

| 层次 | 第一段：首次真实闭环 | 第二段：完整范围 |
|---|---|---|
| 软件实现/离线集成 | PASS：实际 API、持久任务、供料/声音协议、FFmpeg、自检、修订/接受均接通 | PASS：下述软件矩阵；不替代所有真实样片组合 |
| 本地实际媒体 | PASS：合成画面/音轨的真实编码、播放与版本保留 | PARTIAL：两画幅、四声音、90/900秒等具名用例；不是全部排列组合 |
| 真实模型/配音/媒体供应服务 | NOT_TESTED | NOT_TESTED |
| 真实自主完成/质量与效率 | NOT_TESTED | NOT_TESTED |
| Creator 真实审阅/接受具体成片 | NOT_TESTED | NOT_TESTED |

### 软件检查

在 macOS arm64 / Python 3.12 / FFmpeg 8.1 / Pillow 12.3.0 执行：

```bash
/tmp/easel-s6-worker-venv/bin/python -m pytest -q -ra --junitxml=/tmp/easel-s6-final-junit.xml
node --test tests/frontend/*.test.mjs
npm --prefix web/frontend run lint
npm --prefix web/frontend run build
python scripts/validate_skills.py
python scripts/validate_skill_commands.py
python scripts/validate_document_paths.py
```

- 最终全库：**1591 passed、12 skipped、1 warning，77.41秒**。JUnit共1603项，0失败/0错误；包括最后新增的 `test_fork_exact_output_copies_reference_without_old_authority`。
- 12跳过：Bun未安装5项、OpenClaw实装2项、本机无PowerShell4项、900秒编码默认opt-in 1项（另已实际运行，见下文）。既有 `doctor.py` 的 `python_multipart` 弃用提示1条。
- 前端 **80 passed**；lint退出0（既有 `linkifyOutputs.ts` 无用转义提示），构建通过（单包超过500kB提示）。没有通过降低规则或删测试制造PASS。
- 114项Skill和309条文档命令校验通过；路径校验在最终文档更新后再次执行。CI证据按PR的精确提交读取，不把基础提交结果套用到新业务。
- 本地逐项证据：`/tmp/easel-s6-final-junit.xml`、`/tmp/easel-s6-full-pytest-final.log`；这些临时文件不提交到仓库。可用上述命令重现，路径不是交付依赖。

基础 `97199284` 的 [CI run](https://github.com/webxia/Easel/actions/runs/38936316306) 实际结果：Ubuntu1332 passed/8 skipped、Windows1241/99，三平台×Python3.10/3.12持久层各66 passed。新业务CI应以 [PR #8 检查](https://github.com/webxia/Easel/pull/8/checks) 所绑定SHA为准；最终结果同步在PR验证说明，不继承旧SHA结论。

### 本地媒体和界面证据

- `test_creation_flow`：真实图片→FFmpeg可播放成片→技术检查→实际视频文件分段送入脚本化模型→全片综合→reviewable；未自动接受。image-only模型实际链路保持needs_decision，不能完整通过。
- `test_quality`：完整时间轴/音轨、分段与综合判定、尾段缺陷、局部失败不可被汇总抹去、缓存复用、一个runner连续持久调用身份；低帧率尾帧回归另覆盖1fps/10fps。媒体提交覆盖不证明远端模型内部逐帧处理或语义判断准确。
- `test_revision_pipeline`：实际首版→明确接受旧版→自然语言画面调整→重新编码与自检→明确接受新版；旧版字节和原接受选择保持到用户主动切换。扩大范围转新版planning而非死循环；新作复制指定旧版为参考，不复制授权。
- `test_supported_matrix`：24项设置组合校验和一次实际90秒1920×1080/24fps渲染；不是24种组合都实际编码。
- 900秒独立真实编码：`EASEL_RUN_LONG_MEDIA=1 ... -m pytest -q tests/production/test_render_local.py::test_900_second_boundary_real_encode`，**1 passed /38.85秒**；1920×1080/24fps/无声合成静态图输入。两画幅/四声音/字幕/修改保留音频的具体证据见 [S6-09](S6-09_editor-adapter.md)、[S6-10](S6-10_voice-subtitles.md)。未扩大为900秒真实模型自主创作通过。
- 浏览器隔离根 `/tmp/easel-s6-ui-verification` 实测创建作品、缺配置原因、进度连接及重启后恢复入口/零生成次数；截图 `/tmp/easel-s6-ui-verification.png`。测试服务已停止，不占用户生产端口或生产库。

### 尚需用户提供的真实验收条件

已集中询问：可复用本机配置文件路径（不粘贴密钥）、允许模型/配音/素材服务、创作主题与参考/原片样本路径、IMAGE和VIDEO各允许的实际提交次数（可为0）。活动工作树没有这些明确配置与授权组合，因此没有发送真实调用。配音不占两类次数，但不能自动视为已授权。

拿到条件后先执行第一段：真实主题→方案→确认→自主首版→实际审片，并记录错误恢复、调用/耗时及Creator反馈；再按本卡既定完整矩阵执行第二段。不得用本次离线PASS关闭真实未测项。启动与配置见 [运行配置](../16_RUNTIME_SETUP.md)。

### 2026-10-17 · 本机启停与备份接续证据（HEAD `3c8fa4d2`）

- 精确工作树 `/Users/xgx/.codex/worktrees/s5-architecture/Easel`，`codex/s6-production`，接手时 `CLEAN`，与 `origin/codex/s6-production` 同步；PR #8 仍为草稿，`upstream/main` 仍为 `b29d0d72`，未合入。
- 仅检查服务配置**是否存在/配置项名称**，未输出或复制凭证。活动工作树无 `.env`、`.env.local` 或 `config/.env`，Runner 进程无生产配置；历史工作树有部分素材服务配置，但没有具名的本次真实调用授权。不能因为存在 Key 就准入。
- 在本活动树使用已有隔离 Python 和真实本机 Web/worker 执行端口 7870 启停：`EASEL_PRODUCTION_ENABLED=0` 时 `/api/production/capabilities`、`/api/production/works` 均为 HTTP 503，且没有创建 V2 数据库；设置为 `1` 后两接口均为 HTTP 200。试验进程已停止，未重启既有生产服务。
- 首次启用在本活动树新建 `outputs/_production/production.sqlite3`，保留该资产、不做删除清理。随后检查 `works`、`runs`、`operations`、`authorization_grants`、`artifacts` 均为 **0**；CLI `easel production status --root` 返回空任务列表；以 SQLite Online Backup 创建临时备份，`integrity_check=ok` 且 schema 版本和作品数一致，临时备份随测试目录回收。
- 本轮 **IMAGE=0 次、VIDEO=0 次、真实模型/配音/外部素材服务调用=0 次**。这是新增的**本机软件运行/启停/备份**证据；没有新增任何真实自主成片、音色自然度、跨题材稳定性或 Creator 接受证据，第一段和第二段相关格子仍为 `NOT_TESTED`。没有重新执行既有全量回归或 CI 真实安装。
- 后续继续按本卡两段顺序，具名配置、样片和 IMAGE/VIDEO 许可缺失时不发送付费请求，不把离线样片算作真实生产。

### 2026-10-17 · 本机服务配置/素材授权迁入（S6-14 接续）

用户本次明确授权复用本机既有配置，并安全迁入已有多个素材来源和本地素材副本。旧 `/Users/xgx/Projects/Easel/.env` 只读检查并复制可映射项到 V2 自身 Git-ignore 的 `.env`（0600），绝不提交/输出密钥；保留原配置与旧素材/SQLite 数据库。Pexels 继续原适配、Pixabay 新增图/视频 API 检索及 24h 私有缓存、Unsplash 只提供显式预览检索（署名与热链接，选中下载追踪尚未实现）；MiniMax 与直连模型只完成配置身份对齐，不推定视频、音频/声音协议与生成权益。

旧本地素材目录实际仅找到一个 MP3 + 对应来源/权益 JSON。使用独立显式脚本以文件 SHA-256、CC BY 4.0 素材专属证据、来源及署名、真实音频技术检测校验后复制到 V2 内容寻址库，赋予本次授权的 owner-wide 复用；原件未动，不读取或迁移 V1 生产状态。原登记中缺完整归属链接的候选保持被拒，重新归档具备完整信用链的候选，避免以删除历史记录换通过。无画像和另一画像上下文均证实 1 个合格音频候选（`CONDITIONAL`，出口须署名），不代表导演已试听或该 BGM 已用于成片。

离线 MockTransport 供应/素材库/声音规则继续走针对性回归；本轮 **远程模型、配音、Pexels、Pixabay、Unsplash、IMAGE、VIDEO 实际请求均为 0**。本机配置迁入与真实供料/真实自主成片/自然声音/Creator 接受属不同证据层次，后者维持 `NOT_TESTED`。继续要求明确本次创作主题和样本、具名实际服务授权以及 IMAGE、VIDEO 各可提交次数；不重复要求用户给已有本机配置路径。

验证补充（真实本机、无外部调用）：在当前提交前工作树以隔离 Python 执行受影响模块专项测试 **139 passed、2 skipped**，随后运行完整 `tests/production` 两轮，最终含供应商 HTTP 429 负例的确定版本 **355 passed、3 skipped**（跳过不计真实平台通过）；Unsplash preview-only 路由、Pixabay MockTransport 图片/视频/24 小时缓存、owner-wide 作用域与本地样片权利校验均包含其中。实际启动端口 7870 后，`GET /api/production/capabilities` 返回 Pexels/Pixabay 可用且自动供应、Unsplash 可预览但不自动供料、IMAGE/VIDEO 生成 Rights 均不可用；`GET /works` 正常，随后停止测试服务。新增 Web「视频创作」上的 Unsplash 主动预览入口，不自动检索或下载；前端 80 passed、lint 0 error（既有无用转义 1 warning）、build 成功（既有产物大小告警）。文档路径检查 1258 条路径 / 463 文档通过。所有结果仅证明这次改动的本机软件范围，未增加真实远端 Provider / 真实制作或 Creator 接受证据。

### CI 发现的修复

整批 CI 已推动两项修复：精简设置矩阵补上项目声明的 Pillow 依赖；Windows SQLite 边车文件并发消失时的扩展盘符路径比较修复，并新增真实 junction 和跨命名空间负例。后者本机专项44 passed/2 Windows专属skip，详见 [S6-06](S6-06_materials-core.md)。上文1591是整链基础版本的本地全库结果，未把新增用例计入；最终提交的跨平台完整结果以 PR 验证说明及绑定SHA的CI日志为准。

### 2026-10-17 · S6-14 第一段真实 Web 接手与准入核验（本轮）

- **工作树/版本**：`/Users/xgx/.codex/worktrees/s5-architecture/Easel`，分支 `codex/s6-production`，接手 `HEAD 29bfe583710af47f9ba6338c9650574362fdd4c0`，工作区 clean，`origin/codex/s6-production` ahead/behind 均 0；PR #8 保持 Draft。按根 `AGENTS.md` 及本卡权威合同核对；用户已关闭 S6-15，不重新启动 G0～G4。
- **实际服务/Web**：既有 7860 端口服务属于历史 `/Users/xgx/Projects/Easel` 工作树，V2 `/api/production/capabilities` 返回 404；未干扰该服务。使用本 V2 工作树已有隔离 Python 在独立端口 **7870** 启用 `EASEL_PRODUCTION_ENABLED=1` Web/Worker，`GET /api/production/capabilities`、`/works`、`/directors`、`/channels`、`/voice-options` 均返回 HTTP 200。浏览器真实进入「视频创作」，确认作品表单、画像/频道/导演选择、时长、画幅和四声音模式可见；这属于正式入口准入，不是完整 E2E。
- **现有作品基线**：V2 `outputs/_production/production.sqlite3` 只读核对，`works`、`directors`、`director_revisions`、`channels`、`plan_revisions`、`authorization_grants`、`runs`、`operations`、`artifacts`、`reviews` 均 **0 条**，浏览器也没有已确认作品/导演可复用。此活动树 `profiles/` 仅有 `_template`；旧工作树有用户画像目录，但本轮没有获得迁入具体画像、选择它或替用户创建导演/作品的决定，因此没有复制或创建替代作品。
- **配置与服务身份（不披露凭证）**：本 V2 忽略的 `.env` 权限 0600，`direct-api / deepseek-v4-flash / structured` 被运行时列为已配置，但 `EASEL_PRODUCTION_MODEL_CAPABILITIES` 当前为空，未完成真实多模态/整片视频 QC 能力验证。Pexels、Pixabay、Wikimedia BGM/SFX 在服务目录可用，Unsplash 仍仅 preview-only；MiniMax `speech-2.8-hd / male-qn-qingse` 声线目录可用且固定，需作品级真实授权才能在生产中使用。MiniMax 生图因生成 Rights 证据缺失不可用，生视频因型号未配置不可用；不能用已配置 Key 代替调用授权或 Rights。服务目录可用不等于本作品真实远端调用成功。
- **当前唯一阻断**：没有 Creator 确认的具体主题/可选六维画像及导演参考视频/已确认导演版本，没有作品级 planning / stock / voice 授权及 IMAGE/VIDEO 次数，且实际模型音视频能力和完整 QC 仍待具名验证。下一步须先从正式 Web 选定合法作品输入与导演形成/确认，持久化 planning 授权，展示并确认完整 Plan 后，按已授权服务和次数推进 Material→Director Selection→Voice→Editor/FFmpeg→全片 QC→可审阅版本；不得绕过方案确认、付费边界或 Creator 接受。
- **本轮分层结果**：软件/Web/API 准入 **PASS**；真实本作品模型调用、外部素材供料、MiniMax TTS、IMAGE/VIDEO 提交 **均 0 次（NOT_TESTED）**；可审阅 MP4、完整技术/语义 QC、无人手工救火的自主闭环与 Creator 审片/接受 **NOT_TESTED**。无用户作品状态修改，无旧资料删除、发布、合并或授权扩张。首次 E2E 仍为 **PARTIAL / WAITING_CREATOR_INPUT_AND_NAMED_AUTHORIZATION**；S6-15 保持 CLOSED/COMPLETE。

### 2026-10-17 · S6-14 首部真实后端试片 / 尚待完整音画 QC（最新记录）

- **唯一作品与冻结上下文**：原 Work `1bc5f5fa797047dabd6e00654ee3675a`《首部电影短章｜把想法变成作品》，`个人经营实践` 六维画像、Director `Human Cinema` Revision 2。冻结正式 Plan Revision **2**：9:16、**45 秒**、mixed、MiniMax `speech-2.8-hd / male-qn-qingse`。Plan 1 因模型自行将按需环境音解释为 8 项必需 SFX 而保留失败；通过正式版本 API 将可选音效明确化后继续同一 Work，不修改原始历史回执。
- **真实模型及定向恢复**：使用 `MiniMax-M3.1-Flash-Preview` / M Plan 订阅 Key；原第一次 Planning `unknown` 记录保留，不盲发原请求。新的模型 Planning 两次返回有效完整内容但场景多余 `title/type`，本轮只经**人工辅助字段整理**录入正式合法 Plan，不记自主 Planning 通过。Material Intent 因 `unresolved` 预判、长中文 SFX 检索词和超长 `music_query` 先后阻断；修复职责边界、英文短词提示与具体 schema 路径反馈，使用持久回执原请求重放及受限新轮次恢复，不放宽 Rights / 序列身份 / 许可要求。记录一次真实后端端口 7870 的正式 `/confirm` 和 `/resume`，供料最终 **succeeded**。
- **真实素材与声音**：本作品累计登记 **24 视频、12 音频、1 字体**资产，其中正式 Edit 消费从库中筛选的候选；真实 MiniMax TTS 在相同生产 Run 中完成 **7 次 VOICE succeeded**，没有重新请求已成功回执；累计使用的真实候选遵守作用域/来源/Rights/署名，未触发 IMAGE 或 VIDEO 模型生成（限额均 0）。MiniMax M3.1 文本/画面模型不声明 `input_audio`；在 Director Edit 阶段以真实视频抽帧加有界 FFprobe/FFmpeg 编码、时长、音量证据生成**技术预览**，并明确记录 `audio_observation=technical_only_unverified`，没有声称模型听过声音。该行为不代替音频语义选择与用户听感判断。
- **合同与渲染**：编辑模型返回 9 镜头、12 音轨条目、7 字幕条目；原始成功 MODEL 回执未改写。对 7.105/1.395 秒两个片段分别按 30fps 作不超半帧归帧，整体保持 45.000 秒并通过严格 `EditProject` 检查。模型把 12 条事实约束/审片备注误用成 `required_features`，已区分真正的 FFmpeg 技术能力与**未验证备注**，后者保留在私有 `edit_project` metadata 中，不算功能已经完成。Editor 实际技术预检查、真实 FFmpeg 编码、保留素材署名的导出包均成功。
- **输出与质量边界（唯一首版，不是人工拼接）**：`output_id=9cc0cd5d088b47ada3262022f5b51c35`，输出 Revision 1，数据库记录字节数 **44,556,502**，哈希与现存 MP4 文件一致；实际 FFprobe **45.000000 秒、1080×1920、H.264 视频 + AAC 48kHz 双声道音轨**。真实 `/api/production/artifacts/{output_id}/content` 范围下载 HTTP **206** 且 `video/mp4`，`export_bundle=026f59776edc4eef869fff3ca53db2eb` 包含署名并返回 `application/zip`。 `supply/edit/render` 均 **succeeded**，实际 `quality_checks.technical=pass`，但 `quality_checks.semantic=not_tested / video_protocol_unavailable`，`quality_state=needs_fix`，Work `needs_decision`。**不能据此声称真实完整视听 QC、Creator 接受、无人研发辅助自主出片 PASS；S6-14 保持 PARTIAL**。用户可先用现有本机 V2 MP4 预览反馈，正式接受只能在合法质量闭环和具体版本明确审阅后操作。
- **执行环境与回归**：旧 7860 仍属 V1 工作树，未操作。曾因同 Session 多次运行 `run_detached_process` 长驻 Web 而占满 Runner 4/4 并发槽，停止请求被接受但未及时进入 terminal；后改用**一个持久 Session Shell + 唯一 7870 Web 进程**执行后端真实 API，不再额外创建 WebCodex detached 作业。原积压 Job 的 supervisor 终态与 Runner 控制面根因仍待独立治理。受测代码包括 MiniMax 响应分类/等待上限、精确 JSON 错误修复与回执重放、Material Intent 供料职责、FFmpeg 音轨技术观察、严格镜头归帧及编辑能力分层。相关生产测试与文档路径检查见本卡后续验证；结果不得冒充视频语义测试。
- **最新验证台账**：修正镜头归帧、非 FFmpeg 能力备注分层、无音频模型的真实声轨技术测量后，在本机真实 Python 3.12/FFmpeg 环境重新执行 `python -m pytest -q tests/production --disable-warnings --maxfail=1`，结果 **449 passed / 3 skipped / 0 failed（28.19 秒）**；`git diff --check` 无空白错误。当前 3 份修改的 S6-14/状态/运行说明文档共 **33** 条路径引用逐文件校验 0 失败。全量文档扫描另发现 **4** 处错误，全部来自其他未跟踪 `docs/research/director-style-architecture-2026-10-17/` 研究资料的缺失链接；没有更改、移除或纳入本次提交，不把全局校验记录为 PASS。

### 2026-10-17 · S6-14 QC 模型排除约束与本地音频取证

- **用户最新显式约束**：当前 S6-14 完整音视频语义 QC **不得使用 `qwen3.8`**。一度为该型号准备了独立 QC 适配器和测试，但用户纠正后，在任何真实 Qwen 调用及 Git 提交前已精确撤回；当前 `codex/s6-production@f07b8256` 保留 MiniMax 主链，不包含该次 Qwen 专用改动。旧文档关于 Qwen 协议的技术参考不构成本作品的服务选择、授权或验收依据。
- **MiniMax 能力边界**：官方 `MiniMax-M3` 的 Chat Completions 支持实际图像、视频 `video_url` 输入，但其官方说明明确不支持原生音频输入；当前 M3.1 Flash 主创作模型不可因声称多模态而冒充音轨理解。下一步候选是 MiniMax 视频真实观察 + 本地独立音频证据交叉核对，不能把转写/音量等技术结果冒称已听取音乐、音效或完整音画同步。官方协议：https://platform.minimax.io/docs/api-reference/text-openai-api 。
- **新实测的音频证据（不占远端服务额度）**：在原始已登记 45 秒成片上运行 Mac 本地现有 Whisper Base 中文 ASR，实际产生 **14 段**识别，首段从 **0.00s** 开始，末段在 **44.44s** 结束。合并识别文本与已确认 Plan Revision 2 逐场景 `narration` 对比，去除空格、常见标点及英文大小写后字符相似度 **0.952**，个别技术词存在识别偏差。这一结果仅证实旁白音轨可识别及其大体内容，**不能代替专业声音听感、BGM 风格、音效对应或全片声画语义 QC**；识别详情仅保存在 Git 忽略的 `outputs/_production/av_qc_local/`，不提交音频/转写。
- **当前状态未改**：原作品、Plan 2、已完成的 Supply/Edit/Render、45.000 秒 MP4、技术 QC PASS 和原始 Operation/历史资产均未修改；业务 `quality_checks.semantic=not_tested`、Work `needs_decision`，Creator 尚未接受。后续若使用 MiniMax M3 视频审片，仍必须具名授权、真实载荷、持久回执，并对听觉证据不足保持 `partial/not_tested`，不得虚报 `passed`。

### 2026-10-17 · S6-14 临时关闭最终自动语义 Gate → 首片交付人工审核（当前）

- **用户明确决策**：先注释/跳过最后自动 QC Gate，以已生成的真实作品交付人工审阅；仍不使用 `qwen3.8`、不更换 MiniMax 创作链、不重新发起 Planning/TTS/素材或视频生成。实现为受控、可逆的 `EASEL_PRODUCTION_QC_MODE=manual`（默认 `full`）而不是删除正式审片实现或伪造语义 PASS。
- **严格界限**：本次独立 7870 V2 后端技术 QC 对原 MP4 再次 `pass`；新增 `quality_checks.semantic=not_tested`，其中 `mode=manual_review_only`、`reason=creator_requested_temporary_bypass`。旧技术/语义记录原样保留；任何已知 `semantic=fail/partial` 不可直接人工绕过。人工审阅专用作品输出仍记录 `quality_state=needs_fix`，避免误标完整语义质量通过。只有 Web Creator 明确人工完整审核、填写 `manual_review_confirmed=true` 才能接受，SQLite 正式迁移 3 同步收紧受限接受条件；缺此确认的真实 HTTP 接口返回 **422 / manual_review_confirmation_required**，且 `accepted_output_id` 仍为空。
- **恢复与现状（真实接口）**：已对数据库先行作事务一致备份 `outputs/_production/backups/production_pre_s614_manual_review_20261017.sqlite3`（Git 忽略，0600，quick_check PASS）；原 `7870` V2 独立重启，数据库 schema v3 完成，能力与 Work API 都 HTTP 200。由正式 `/api/production/works/1bc5f5fa797047dabd6e00654ee3675a/resume` 恢复原 Run `25864ab3e88a438693fe146998f35651`，获得 HTTP **202**。实际最终状态：`supply/edit/render/quality` **全部 `succeeded`**，Run **`succeeded`**、Work **`reviewable`**、Plan Revision 2、原 output ID `9cc0cd5d088b47ada3262022f5b51c35`，没有生成替代作品或接受成片。
- **阶段结论**：真实首片已可供人工完整看画面、声音、字幕、音乐及声画同步；软件执行链与真实 FFmpeg 产物就绪。**自动语义 QC 未执行，Creator 尚未接受，电影质感与完整自主出片仍未验收**。此处“成功”仅指生产工作流到人工审阅的交接完成。旧 7860 及其他研究目录未触碰。恢复自动审片需将 V2 `.env` 的 `EASEL_PRODUCTION_QC_MODE` 改回 `full` 并重新启动唯一 V2 服务；不会替现有作品补写假审片回执。

### 2026-10-17 · 新建独立真实 E2E 重测：API 全链成片，首次零卡点未通过

- **目的/范围**：验证单次从正式 API 创建到 `reviewable` 的真实 MiniMax 自动视频链路，非软件 Mock，不复用首片 EditProject，不偷换回执。验证 Work `f8040a6d153c419aaf1045eadc61bc63`《E2E全链真实直通验收｜把想法变成作品｜20261017》，同一六维画像 + Human Cinema 导演 Revision 2、9:16/45秒/mixed固定MiniMax旁白/BGM，生成配额均0，语义 QC 暂按用户确认的 manual 模式。旧作品和初始 Run 均保持。
- **第一轮真实结果**：经 `POST /works` 创建、`POST /plans` MiniMax M3.1 首次生成合法 CreativePlan Revision 1（6 场、总 45 秒、无开发者整理 JSON）、正式 `POST /plans/1/confirm`，真实 `supply=succeeded`，但 `edit=needs_decision / voice_timing_exceeds_plan`。真实 MiniMax TTS 7 句约 38.23 秒，第一场 `6.653s > 6.000s`，虽然全片旁白能容纳，局部镜头不足。**该 E2E 严格零卡点结果 FAIL**；不能把后续修复后成功倒写成一次顺畅成功。
- **合同化修复与再次生产**：使用正式 `/cancel` 结束有卡点生产 Run，保留原 TTS 和资产；经 `/plans` 建 Plan Revision 2，只将场景1从6秒改为7秒、场景2从7秒改为6秒，总时长、旁白、音色和其他内容保持不变；明确记录实际 TTS 时长依据，再次正式 `/plans/2/confirm`。第二条 production Run `5f0947bbf802428c8918d991f7d6d477` 最终 `supply/edit/render/quality` **全部 succeeded**，Work **reviewable**，没有再次人工恢复任务；对第一次冻结 Planning 的真实语音安全裕量仍需产品层改造和全新直通复验。
- **真实第二首版结果**：`output_id=76ca9b8f243c45f3b2eca9ed8b344606`，Revision 1，文件存在、SHA-256 与持久化登记一致、FFprobe **45.000000秒、1080×1920、H.264视频+AAC音轨**，52,250,838 bytes。`quality_checks.technical=pass`；`quality_checks.semantic=not_tested / manual_review_only`，输出实际 `quality_state=needs_fix` 但可人工审阅，`accepted_output_id=NULL`，没有自动发布。新作品仍需 Creator 完整人工观看并明确接受具体版本。
- **下一项真实收敛**：在冻结 Planning 前增加可测试的旁白时长安全余量/场景容纳检查，不以字符数直接冒称真实 TTS 时长；无音轨成品前的精确时长需要实测或保守留白，TTS 真实结果仍为最终权威且不足必须合法调节方案。实施后重新创建**新作品**跑第三轮零干预 E2E 验收，不能把第二轮补救称为完整自主成功。

### 2026-10-17 · 主工作区稳定性修复与第三次直通准备

- 唯一开发和运行根目录 `/Users/xgx/Projects/Easel`、分支 `easel-v2-main-workspace`，LaunchAgent `com.easel.web` 运行主端口 7860。原主工作区 `.venv` 因未安装 `langgraph`、`langgraph-checkpoint-sqlite` 无法执行真实 Worker，现按 `pyproject.toml` production pinned versions 补齐依赖；不再依赖 `/tmp` 隔离 Python。
- 新增 `voice_budget.reserve_narration_slots`：仅在**模型自动生成的 Planning 草稿冻结前**运行，按中文/英文字符保守估算最低配音时间，在原有场景间以30fps时间基重分配时长；始终保留冻结作品的总时长、场景身份/顺序、旁白原文及固定 MiniMax 声线。总预算或场景可用余量不足时在 Planning 阶段返回 `plan_voice_budget_unavailable`，不在真实 TTS 发送后才失败。用户手工提交的确认方案不在此处自动改变；真实 MiniMax TTS 返回时长仍是唯一最终依据，必要时明确改版。
- 历史真实失败样本 Plan Revision 1：`s01_context` 6秒、MiniMax TTS真实6.653秒；经预冻结预算分配为6.9秒，总45秒不变。保守估算不保证所有语速/情绪/停顿，必须由新真实 E2E 独立验收。
- 主 `.venv` 全量 `tests/production` 回归 **455 passed / 3 skipped**，旧版 7860 服务数据和既有两部 MP4 均保留；未触发模型调试复发调用。新真实 API 首次零干预验收仍需以运行回执为准。

### 2026-10-18 · 第三轮真实 Run 接续闭环及防旧进程再犯

- **根因已证实**：主工作区 LaunchAgent `com.easel.web` 的应用进程于 2026-10-17 21:59 启动，而 `creation.py` 转场重叠补偿代码在 22:20 才修改。旧 Python 进程没有热重载，普通 `/api/production/capabilities` 仍返回 HTTP 200，因此 2026-10-18 00:16 的原 `/resume` 仍调用旧版 `EditProject` 计算逻辑并再次报 `invalid_edit`；不是新的模型响应失败，且不能把 HTTP 200 当成代码已经更新的证据。
- **精确恢复动作**：确认没有其他活动 Run 后，通过 `launchctl kickstart -k gui/$(id -u)/com.easel.web` 重启 **唯一主工作区 7860 服务**，核实新进程启动时间为 2026-10-18 08:23:45（晚于补丁时间）；主 API 均 HTTP 200。随后使用正式 `POST /api/production/works/59a27d8fb2f54be0a43507e2f78b9a02/resume`，保持原 `Run=97a924711a374a74a879c88417291f45`、已冻结 Plan、资产和 Operation 身份；未重发已成功 MiniMax Editor 模型请求或 6 条已成功的 VOICE 请求。
- **真实最终结果**：同一 Run 的 `supply/edit/render/quality` 全部 `succeeded`，`Run=succeeded`、`Work=reviewable`。新输出 `output_id=653519d1574c45c7bc937e5316ff359a`，**45.000000 秒，1080×1920、H.264 + AAC 48 kHz，32,475,817 字节**，实际 SHA-256 与数据库完全一致；导出 ZIP 包含 `video.mp4` 和 `credits.txt`。质量检查真实为 `technical=pass`、`semantic=not_tested / manual_review_only`；Creator `accepted_output_id=NULL`，并未自动接收或发布。该轮曾经历 Edit 阻断及恢复，**不能宣称第三轮从零无卡点 PASS**。
- **代码级防复发**：新增生产源码启动时的文件版本快照 `runtime_readiness.py`；`GET /api/production/capabilities` 暴露非敏感 `backend.reload_required`，源码在进程启动后变更则置 `true`，新的创作/确认/恢复等命令以 `503 / backend_reload_required` 明确拒绝旧代码处理；取消运行和用户接受入口保留，避免锁死已建作品。重启唯一主进程后变为 `false`。这不改变任何持久化 MODEL、VOICE、素材、Rights、Creator 接受或 QC 合同；不允许凭绿灯跳过真实检查。
- **下一验收线**：全量软件回归与新运行时防复发检查必须通过；下一次在代码不变的主工作区新建 Work，独立完成 Planning、TTS、供料、Edit、Render、技术 QC，期间 **零 `needs_decision`/手工 `/resume`** 才可记「首次无干预直通」；人工审片仍须 Creator 明确接受。
- **真实防旧进程验收**：主工作区服务按 LaunchAgent 重启后，`GET /api/production/capabilities` 返回 `backend.reload_required=false`；仅变更 `creation.py` 文件时间戳（不更改内容）后返回 `true`。此时实际 `POST /api/production/works` 被 **HTTP 503 / backend_reload_required** 拒绝，数据库作品数始终为 4，未发生额外生产或付费调用。再启动同一主服务后 `reload_required=false`。新增 `test_runtime_readiness.py`、`test_edit_preview_projection.py` 的相应测试，全量 `tests/production` **460 passed / 3 skipped / 0 failed**，没有把模拟检查冒充真正的 MiniMax E2E。

### 2026-10-18 · 第四轮首次零人工 API E2E / FAIL，Planning 口播字段治理

- **冻结运行样本**：主工作区 `easel-v2-main-workspace@c0dce522`、7860、MiniMax M3.1 M Plan、正式固定画像/Director、45秒9:16/mixed；全新 Work `18a20ed1fe9241168fd13c16648c1742`、Planning Run `6db937a4a383417dbdd780e95072f908`。使用正式 `POST /works` 和 `POST /plans`；原始两轮 MODEL 操作均真实 `succeeded`，没有 UNKNOWN 或重复付费发送原请求。
- **本轮首次零人工结论：FAIL**。Worker 在 CreativePlan 严格 JSON 模型验证后执行冻结前声轨预算门禁时返回 `plan_voice_budget_unavailable`，Work/Task 为 `needs_decision`，未创建 Plan Revision、未执行 TTS/Supply/Render。模型把 `旁白窗口 00:00.8–00:04.5：…`、语速/换气/停顿等**导演说明**塞进 `Scene.narration`，即使第二轮自动模型格式修复仍保留时间标记；保守预算把这些非口播字数作为实际朗读，导致总长45秒无法分配。这是 schema 字段语义失守，不是音频实际超时。原始 MODEL 回执和失败 Task 保留，不借人工调整把本次改为PASS。
- **生产逻辑收敛（用于下一新 Work）**：新增仅适用于**模型新生 Planning 草稿**的 `VoiceReadyCreativePlan` 校验器，拒绝时间码和导演备注出现在 `narration`；在模型结果入库前同步执行确定性声轨时长预算检查。发生违规时在 bounded format repair 中反馈字段级中文错误说明，允许最多 **2轮修正、3次模型响应**，输出仍须满足冻结 Creator 设置、总时长及原有 PlanDocument 严格合同。人工提交的原 Plan 合同、历史模型 Operation 和 Rights 均未改变；不可把自动格式修复说成0模型重试。修复后的新独立 Work 才可以检验零**人工**恢复，不抹掉第四轮 FAIL。
- **离线验证**：新增 `test_planning_narration_budget.py`，实际模拟回执覆盖时间戳注释拒绝、真实口播恢复、预算超额、最多3次模型尝试、静音模式豁免；相关专项27 passed，主工作区 `tests/production` **465 passed / 3 skipped**。第五轮启动前须固定并提交此版本、核对 `backend.reload_required=false`，不能在第五轮中途修代码或调用 `/resume`。

### 2026-10-18 · 第五轮成功基线只读核验与验收归档

**结论：REAL_API_PRODUCTION_PASS / ZERO_MANUAL_RECOVERY_PASS / CREATOR_REVIEW_PENDING。** 第四轮零人工直通 FAIL 保留；本轮使用独立 Work，在固定生产代码 `406e523c` 上自动到达人工审阅。该结论只针对正式 API 路径、当前输入和 manual QC 模式，不代表完整 Web 对话体验、自动语义 QC 或电影质感通过。

| 对象 | 已核实事实 |
|---|---|
| Work | `9b9ed8da98e4437e89618ceee1cb7731`；API/SQLite 均 `reviewable`；revision 6；accepted_output_id=NULL |
| Planning Run | `3e749e3626824cdc8af0477c1b66e22e`；succeeded；plan Task succeeded；产生且仅产生 Plan Revision 1 |
| Production Run | `15768e8affc24f23af23faea69e7d942`；succeeded；supply/edit/render/quality 四个 Task 均 succeeded |
| Output | `f06e9604f6134039b5c22ae1303df323`；输出版本1；quality_state=needs_fix（人工审核模式的如实标记） |
| MODEL / VOICE | 4 MODEL + 7 VOICE，全部 succeeded、均有 submitted_at 与持久成功回执；IMAGE/VIDEO 各0 |
| QC | 同一成片 digest 上 technical=pass；semantic=not_tested，mode=manual_review_only；acceptances表无本片接受记录 |

**证据方法**：正式 GET capabilities/Work/媒体 Range；SQLite URI `mode=ro` 加 `PRAGMA query_only=ON`，读取 runs/tasks/operations/plan_revisions/events/artifacts/artifact_edges/quality_checks/acceptances；对已登记本地文件运行 SHA-256、FFprobe 和 ZIP 内容核对。仅输出聚合状态及必要验收标识，不将原始模型消息、用户素材、凭证或私人回执复制入 Git。

- **模型自动修复与无人工恢复**：4次 MODEL 分别为 Planning 两次（首次响应后附格式修复反馈）、Material Intent 一次、Director Edit 一次。Planning 自动修复一次不等于0模型重试，但属于0人工恢复。11个 Operation 的 request_key 无重复，同 task/kind/input_hash 组合也无重复；全部终态成功，UNKNOWN/发送中/未决操作均0。事件中命令只有 `create / plan / confirm` 各一次；`resume / cancel / revise / grant / accept` 均无，needs_decision/failed事件均0。17次 `task_waiting_external` 是后台正常等待/观察，不是人工恢复；不能把22次task_started误记成22次模型请求。
- **人工改动边界**：本轮只读现场没有修改代码、Plan或数据库。第五轮运行中0人工修改代码/数据库/Plan由上一窗口交接声明，且与单一Plan版本、无恢复/改版命令、当前生产源码仍为406e523c相符；SQLite业务事件不能独立证明操作系统层从未有人手工改文件，不虚构额外审计覆盖。
- **实际成片**：FFprobe **45.000000秒，1080×1920，H.264 + AAC 48kHz双声道**；文件大小 **51,940,170 bytes**；实算 SHA-256 与登记及QC引用一致，为 `7690b7dc45e6215e88f18f7b791476b096372ebadde54fdbbabbacc918d79904`。正式内容接口 Range 响应 **206 / video/mp4**，Content-Range 总长与文件一致。
- **实际素材与导出**：EditProject 引用16项资产：7视频、1外部音乐、7条生成旁白、1字体；引用文件逐项SHA一致。7视频登记 Rights=KNOWN 且有source；所选音乐 Rights=ATTRIBUTION_REQUIRED，credit_text与source_page均出现在导出 credits.txt；7条VOICE成功回执与音频资产相连，字体保留登记摘要。ZIP包含 video.mp4 和 credits.txt。未用本次检查宣称独立完成供应商版权法律核验或听感审片。
- **时间（Asia/Shanghai）**：Planning约12:21:37～12:24:39；方案确认/Production开始12:25:48，Run成功12:31:24。确认到成功约336.4秒，仅此样本，不设全局时延目标。
- **软件及运行环境**：生产模块最近已有软件证据为 `406e523c` 的 **465 passed / 3 skipped / 0 failed**（本次文档轮未重跑）。当前正式 capabilities HTTP200 且 **backend.reload_required=false**；未重启唯一主服务，不运行7870旧工作区。

Creator 人工审片入口：[播放第五轮视频](http://127.0.0.1:7860/api/production/artifacts/f06e9604f6134039b5c22ae1303df323/content)。待用户评价故事与导演风格、画面/内容匹配、中文旁白与字幕、BGM/音效、节奏及电影质感；没有用户明确接受不写 CREATOR_ACCEPTED、不调用接受接口、不发布。

### 2026-10-18 · 新增 S6-14A 交互设计任务与本轮工程收口

用户要求优先设计前后端对话交互，并补充参考 Easel 管线。已登记 [S6-14A](S6-14A_conversation-integration.md)，形成[交互文档](../20_CONVERSATIONAL_INTERACTION.md)、独立SVG总览、Easel管线映射图、时序图和状态图；[实施合同 §9](../15_IMPLEMENTATION_DESIGN.md#9-s6-14a-对话接入增量提案待评审未实现)集中记录拟新增接口/上下文/卡片合同。设计状态为待评审、实现未开始，不能以文档交付宣称前端改造完成。

本次只改权威文档、任务卡与图；保护所有既有未跟踪资料和生产证据。本轮10份相关Markdown的183条路径引用检查0错误，git diff --check通过；SVG通过XML解析并经渲染目视检查，附PNG预览。全库路径扫描仍发现原未跟踪research目录的4处既有坏链接（共1356条引用），没有修改无关研究文件，故不记全库检查PASS。生产源码未变，本轮不重复跑生产回归。未启动新创作、模型/媒体调用、业务迁移、服务重启或Creator接受。下一步为评审 S6-14A，人工审片可同时进行；S7和Git/PR汇合仍为后续事项。

### 2026-10-18 · S6-14A 接入研究与具体方案补充

按用户“先研究、补充文档并形成交互图”的指令，完成 OpenClaw 本机版本/原生插件/路由/工具策略研究；推荐内部受限视频运行配置 + 原生作品工具插件 + Web 薄转发，复用现有生产后端。已更新[交互设计](../20_CONVERSATIONAL_INTERACTION.md)、[实施合同 §9](../15_IMPLEMENTATION_DESIGN.md#9-s6-14a-对话接入增量提案待评审未实现)、[接入图](../diagrams/s6-14a-conversation-flow.svg)和[六步交互分镜](../diagrams/s6-14a-interaction-storyboard.svg)，具体研究/验证记录只维护在 [S6-14A](S6-14A_conversation-integration.md)。推荐可行性有文档/源码依据，组合接入与实际权限仍 NOT_TESTED；未改业务代码/配置、未发起生产。第五轮结果与 Creator 审阅状态保持原记录。

### 2026-10-18 · S6-14A A1 隔离工具桥验证

用户授权仅推进 A1。独立临时 OpenClaw + 假聊天模型 + 临时 WorkService 的原生工具桥/权限/会话绑定验证通过；记录与软件检查见 [S6-14A](S6-14A_conversation-integration.md)。正式 Web 未挂载、主服务/配置未重启修改、付费调用0；第五轮作品/回执/人工接受不变。S6-14整体仍 PARTIAL，下一事项为 A2 持久绑定与创作依据，不以 A1 替代 Web/真实生产验收。

### 2026-10-18 · 创作完成后的闭环设计补充

用户要求结合Easel原设计理清完成与回写；已在[S6-14A](S6-14A_conversation-integration.md)及其交互/实施合同补充产物登记→审片接受→内容库复用、明确长期保存、可选发布复盘的分工和现有接入缺口。仅文档/图，本轮没有执行接受、画像/频道/导演写入、发布、数据抓取或新增模型调用。A1的隔离通过与第五轮真实结果均保持原范围，整体S6-14仍PARTIAL。


### 2026-10-18 · 频道/导演入口贯通设计

已补齐[S6-14A交互设计§11](../20_CONVERSATIONAL_INTERACTION.md#11-导演频道入口与统一创作闭环)与[入口闭环图](../diagrams/s6-14a-entry-loop.svg)，将频道默认、导演版本复用/参考形成与同一对话、审片、明确回写及下一作串联；UI19～UI25记录后续验收。频道语义依据和fork设置沿用尚需A2适配；首版兼试片的独立接受及QC资格仍待A4验证。仅文档完善，无正式运行/付费/接受/发布，A1与第五轮证据范围不变，S6-14仍PARTIAL。


### 2026-10-18 · 创建交互与整体方案文档审查完成

按用户“补齐创建流程、审查全部方案、修改后停止”的要求，已完善[频道/导演创建](../20_CONVERSATIONAL_INTERACTION.md#11-导演频道入口与统一创作闭环)和[创建流程图](../diagrams/s6-14a-creation-flows.svg)，[整体审查结论](../20_CONVERSATIONAL_INTERACTION.md#12-本次整体方案审查与修正2026-10-18)明确已修正文档问题及尚未实施的接入缺口。记录与检查见[S6-14A](S6-14A_conversation-integration.md)，UI26～UI28待执行。仅文档/图，无代码、正式环境或真实业务变更；A1/第五轮范围不变，S6-14仍PARTIAL。本轮收口后停止，A2不自动启动。


### 2026-10-18 · S6-14A A2～A4研发完成

用户新授权完成A2～A4；已实现持久OpenClaw/创作依据、对话卡片/目录入口，以及审片/独立接受/明确回写/续作闭环。软件检查、实际隔离Web/OpenClaw与浏览器证据只维护在[S6-14A](S6-14A_conversation-integration.md)。A2～A4为IMPLEMENTED / SOFTWARE_PASS，A5完整交互验收未开始；无正式插件安装、服务重启、正式库迁移、付费生产或第五轮接受。S6-14保持PARTIAL，既有第五轮真实证据不被本轮软件结果替代。

### 2026-10-18 · S6-14A A5离线完整交互验收

按用户新授权执行完整隔离流程与UI01～UI28，直接修复发现的问题。实际Web/原生OpenClaw/WorkService/Worker/本地FFmpeg完成首版、指定版本修订、独立接受、明确回写及内容库续接；28项离线判据通过，逐项映射/截图/源码摘要见[S6-14A](S6-14A_conversation-integration.md)。本轮所有模型答案为本地脚本，媒体为合成测试素材；未改正式环境或发起付费调用。第五轮接受仍待Creator，S6-14整体仍PARTIAL，自动语义QC仍NOT_TESTED；不能将隔离测试中的模拟接受写成真实Creator接受。


### 2026-10-18 · S6-14A A7真实Web生产收口

独立新样本通过实际Web频道创建→参考形成视觉导演→完整方案确认→真实库存/TTS/剪辑/渲染→技术QC→同对话审片卡回写；详细数据、失败修复、费用未披露及质量问题只维护在[S6-14A A7](S6-14A_conversation-integration.md)。原第五轮、历史UNKNOWN与所有备份中生产记录逐行未变。A7经历工程调试及Web字体改版，不借用第五轮零人工恢复标签；自动语义QC仍NOT_TESTED，Creator未接受，S6-14保持PARTIAL，S6-15不重开，S7不自动启动。
