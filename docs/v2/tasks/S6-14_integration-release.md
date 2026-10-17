# S6-14 · 首次真实生产与完整范围验收

状态：**PARTIAL / REAL_PRODUCTION_PAUSED**。软件与本地合成媒体验证通过；依用户 2026-10-17 最新决定，先执行 [S6-15 素材层审计与完善](S6-15_material-layer-hardening.md) 并通过 G4 回接门禁，再恢复本卡首次真实生产与完整验收；本卡既有证据与两段标准不变。真实服务/样本/授权在恢复执行时另行核实。

- **依赖**：第一段为 S6-01～11 实际就绪；第二段为 S6-01～13及首次真实闭环就绪。阶段对应见[任务包里程碑](S6_IMPLEMENTATION_PLAN.md#1-基线顺序与交付)。
- **用户最新排程门禁**：在原技术依赖之上，**两段实际执行均等待 S6-15 G0～G4 完成**；不删除或重跑本卡历史软件证据，不在素材层未就绪时启动真实生产。素材层 G4 不等于 S6-14 通过，Creator 接受必须由用户对具体版本明确选择。
- **需求主/协作覆盖**：V2-EXP-009, V2-EXP-018, V2-EXP-022, V2-EXP-023, V2-EXP-028, V2-EXP-029, V2-EXP-030。
- **目标与合同**：[可执行设计](../15_IMPLEMENTATION_DESIGN.md)；[任务包共同约定](S6_IMPLEMENTATION_PLAN.md#2-每张卡开始与完成的共同约定)。
- **预计落点**：tests/production/test_supported_matrix.py；.github/workflows/ci.yml；README/安装说明；具名运行证据（私有原件不入Git）。
- **执行分支建议**：`codex/s6-14-integration-release`。

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

## 执行记录（2026-10-17）

受测实现：`97ecc67b`，分支 `codex/s6-production`，从 `4525b09d` 接手；基础分批提交为 `e923332a`、`97199284`。[PR #8](https://github.com/webxia/Easel/pull/8) 为草稿，未合并、未发布。测试采用隔离虚拟环境、临时 SQLite/媒体根；没有调用真实付费服务，没有迁移 V1 运行数据。

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
