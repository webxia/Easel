# S6-14 · 首次真实生产与完整范围验收

状态：**PARTIAL**。软件与本地合成媒体验证通过；真实生产等待具名服务/样本/授权。第一段通过而第二段未完成时为 PARTIAL；两段结果分别记录。

- **依赖**：第一段为 S6-01～11 实际就绪；第二段为 S6-01～13及首次真实闭环就绪。阶段对应见[任务包里程碑](S6_IMPLEMENTATION_PLAN.md#1-基线顺序与交付)。
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
