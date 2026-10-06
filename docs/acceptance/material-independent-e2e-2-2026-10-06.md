# 第二次独立真实 Material E2E（2026-10-06）

状态：**FAIL / Planning 自动失败停止 / 未进入 Material Supply**。新作品 `cr_223021d92de643f0a35faea2907de7ed`，Attempt `fa_d5e99b227faa224b82f5347174850a1b`。只验收到 MATERIAL_READY；没有进入 Production Authoring、Build、视频 Quality 或发布。第一次独立验收 `cr_94b5d27f5fb140de85981cecba009a9d` 的 FAIL 和原始证据保持，不恢复、不倒算。

## 固定版本与安全加载

- 分支 `easel-studio`，软件修复提交 `c9cb4b9cad69d0d82c0d300a49fdbfa8107eb2c4`。提交仅包含 Planning 合同修复、相关确定性回归、原始 fixture 与第一轮验收的后续软件说明；既有其他文档修改保留，未一并提交，未 push。
- 生产源码集合 SHA `de23d0567944e543015f17bd7c425886bb0ed1d0f864ca9efb1fb1aebd4cfdfa`，范围为预登记的 `easel/**/*.py` 和 `web/app.py`。确认前及终态 `git status -- easel web scripts tests` 为空；逐文件 SHA 与预登记一致。
- 按 AGENTS.md，Astra 在正式 E2E 前只读复核 `CONTINUE`：正式终点须在方案确认前设置，新 Creation 不带历史恢复标记；MATERIAL_READY 的普通 Delivery 分支阻止后续 Authoring/Build，自动生成选择跳过视频、BGM/SFX 不进入生成采购。此复核不是实际 E2E 成功证明。
- 预检现有 14 个 Creation 均无活动操作或未知非终态生成，实际 `delivery.lock` 可用；Gateway active=0、queued=0，全部 671 个任务已终结。没有未知任务需要中断。
- 通过现有 launchd 服务安全重载 Web/Gateway，未改运行配置或安装模块，Hypit 未重启。Web PID `39338`、Gateway PID `39348`，均启动于北京时间 `20:04:10`；Web cwd 为本仓库。加载核对时间 `2026-10-06T12:04:24.870468+00:00`。
- Gateway 实际版本 `2026.9.4`，已有安装模块 SHA `654bb2d9753e0a354320a70bdb96a120e9d5c0780e3d76f0e69bf08f4e2dd6d6`。终态 PID 和启动时间不变，无运行中重载。

## 正常入口、独立授权与确认

- 用户在本线程独立授权新作品最多 ¥10，仅 MiniMax 图片及现有预置音色旁白，排除 AI 视频、AI 音乐和 Build；未转授第一次预算。
- 使用正常 Web 新对话、`个人经营实践` 画像及 `清醒备忘录 · 视频 · v1.3`。主题与第一轮相同，为“把待办清单缩减为今天最重要的一件事”，约45秒、9:16，原逐字完整旁白、真实器乐 BGM、纸笔桌面示意、独立简体文字和“一项突出，其他仍留、未删除”的必要表达均保留；不要求同一桌面/手/清单连续性或可读指定中文，不以环境音代替 BGM。
- 第一条正常对话于北京时间 `20:05:51.343` 提交。前两次属于普通方案讨论，没有触发正式整片视频入口、没有 Creation、Preparation 或 Planning；第三次明确“制作一条完整短视频”后正常建立新 Creation，创建于 `20:09:47`。确认前正常讨论修正模型擅加的生图数量上限、BGM 来源限制和每镜头突出项要求，未手造 MaterialPlan/Need 或复制历史素材。
- `20:13:36` 通过正式同源本机 Operator Session 与 `/api/creations/{id}/delivery/material-endpoint` 绑定 MATERIAL_READY；回读未确认、无 Attempt。没有绕过认证，没有暴露会话凭证，没有直接改数据库。
- 在正式画布填写预算 `10`，点击“按这个方案制作”，于 `20:13:57` 正常确认。视频方案 SHA `96e94dcf86bc3a09d9636ffafea873896d6f5663c2e85be5823427346c9e9f0f`，整体确认 SHA `92e195253177666d52a3a350b556a9047be6cf8303f4722011eb2921abf3633c`。独立预算、输入使用声明、Creation/确认方案和终点由正式流程登记。
- 预置音色 `male-qn-qingse`、图片 `image-01`、旁白 `speech-2.8-hd`；通用预算 scope 中仍含视频模型字段，但本轮确认 Brief 明确排除视频，MATERIAL_READY 路径的自动选择也跳过视频。未人工调用任何生成接口。

## 自主运行与自动终态

- 原 Delivery Owner 自主执行 Preparation，于 `20:17:30` 冻结 Content Core、Truth Packet、Creator Context、Production Brief，并建立新 Attempt。随后自主进入真实 Planning，确认的 SCRIPT/SCENES/TREATMENT 由正常程序提供并保持字节/内容约定。
- 本轮真实初始 Plan 为 10 Need：7 image、3 audio；9 required（7视觉+旁白+BGM）、1 optional（纸笔动作音效）。后续由系统既有修复流程处理，最终 ID 和 importance 未改变。未使用第一轮 Plan/Need、素材或审核结论。
- 初始与最终要求文件均以全部 7 个视觉 Need ID 为根键，没有包装数组或 audio ID 混入。这证明本轮未再出现第一轮的根结构错误；不代表条款合同已经完整通过。
- 系统依次处理了 Voice Domain 字段、`voice_delivery` 不能作为标量检索过滤器、audio 使用 `preferred_visual_details`、偏好引用和原文路径错误。所有修复任务均由现有程序派发；本轮没有修改代码、增加重试策略、人工 Retry、手写补证或放行。
- 自动停点为北京时间 **20:30:02**（`2026-10-06T12:30:02+00:00`）。Delivery `status=failed`、`operation=null`，`fa_d5e99b227faa224b82f5347174850a1b:prepare` 累计 3 次失败后耗尽，最终错误为 **`Planning 要求合同无效：原文要求未完整覆盖`**。Preparation 投影为 MATERIAL_FAILED；此前 HANDOFF_READY 的冻结成果仍保留。
- 正式 MaterialPlan/Planning completion 未建立，Material 目录不存在。搜索、获取、观察、生图、TTS、BGM 供给及 Rights/Match/Readiness 全部未运行，没有 MATERIAL_READY 或 endpoint result。草稿准入0/9只作为未供给的参考，不冒充正式覆盖/Readiness。

## 终态只读诊断

系统在 `easel-55175b83faff4d5db8ee4a3c54764ee6` 的声音检索修复中，将 `voice_delivery` 改成标量字段，并把 `voice_pace_ratio=0.95`、`voice_pitch_semitones=0`、`voice_tone="neutral"` 写到了**全部 7 个视觉 Need**。这些声音参数误入视觉职责范围。

最终 `MATERIAL_REQUIREMENTS.json` 每项包含4条正确引用：intent description、function、明确视觉偏好及 modality visual_style。`sources_for()` 则读取5条字符串源，额外的 `constraints/voice_tone` 为 `neutral`；七项均未引用该源。现有严格校验因此正确拒绝未完整覆盖，而没有静默丢弃该字段或将 required 放宽。

这是本轮新的 producer/声音检索修复边界问题，不能把第一次根对象/缓存修复的确定性回归成功扩大为自主生产成功。终态诊断只读取正式产物和脱敏 transcript，对比结果另存，**没有回写 Plan/Need/要求文件，没有改 validator、consumer、审核或冻结输入，没有继续开发或恢复运行**。

最终原件 SHA：

- `planning/MATERIAL_PLAN.json`：`eacacfca9ed6a8d68f470f48c5812b0c32960cbb4bcce39174561f649432fd8f`
- `planning/MATERIAL_REQUIREMENTS.json`：`d6b6a7a6880a151c45bd9e6b94dc23faf4b6e1f8c5549d1253ccad9c406061f5`

## 完整证据与终态对账

原失败工作区：`/Users/xgx/.easel/hypit/workspaces/cr_223021d92de643f0a35faea2907de7ed/fa_d5e99b227faa224b82f5347174850a1b`。正式 Creation JSON 和所有原产物不删除、不手改。

本机脱敏归档：`/Users/xgx/Library/Application Support/Easel/acceptance/material-independent-2-2026-10-06`。包含预检/加载、入口/确认/授权、连续时间线、Preparation draft/snapshot、全部本轮 workspace 文本/JSON、原字节 SHA、观察到的 Planning 版本、4项正常 UI turn 日志（3次模型方案请求及1次确认 ACK）、3个具名 Gateway transcript session、9项任务记录、只读缺项诊断、声音参数修复证据、失败画布截图和最终机器对账。文件权限600、根目录700；凭证、认证配置、未脱敏原始服务日志不进入归档/Git。

- 11份 handoff 文件 SHA 与最初 Preparation 基线一致；4个正式 snapshot SHA 与冻结记录逐项一致，3个 handoff 副本字节一致，Production Brief 与冻结快照相同；3份确认 Planning 文本内容保持原确认方案。
- 生产源码 SHA/commit 不变；预登记14个旧 Creation JSON SHA全部不变，包括第一次 FAIL。没有修改任何运行数据、报告或审查结论。
- 9个 Delivery Agent 均 `ok/released`，9个网关任务已终态；单个 Agent 成功收尾不等于整个 Planning/Delivery 成功。Gateway 最终683任务全部终态，active=0、queued=0，较预检新增12项与3方案+9Delivery外层请求吻合；执行锁可用，无未知采购。
- Authoring 仅为初始化 `pending` / READY_FOR_EXTERNAL_AUTHORING，任务文件存在不代表派发；实际 execution=NOT_SUBMITTED、build=not_submitted、outputs={}，没有 Authoring、Build 或 Quality 任务。

## 时间、调用、费用与最终九项

- 新 Creation 创建 `20:09:47` → 自动停止 `20:30:02`：**20分15秒（1215秒）**。
- 正式确认 `20:13:57` → 自动停止：**16分05秒（965秒）**，包含所有系统自动修复与观察。
- 第一条正常方案讨论 → 停止：24分10.657秒；本 Goal 建立 → 停止28分13秒，额外包含固定版本/预检/加载。终态后只读导出与文档工作另计，不当作自主运行耗时。
- 正常方案 Agent 3次；Delivery Agent 9次（Preparation1、初始Planning1、既有系统Planning修复7），Prepare计量9/24，计量原标签均为initial，未修改预算分类。观察/轮询不算模型派发；模型内部HTTP/续段次数UNKNOWN。
- 素材 Provider 适配、生成核价/提交均0；无本次生成采购，生成占额¥0/独立授权¥10。模型与总实际账单UNKNOWN，网关usage零占位不是实际费用为零的证据。
- AUTONOMOUS_EXECUTION=YES只指正式确认后全程现有系统执行、无工程救场；AUTONOMOUS_DELIVERY=NO，因为未自主到达正式终点。预运行安全加载、正式接口设终点及确认前正常对话另列，不算运行中工程干预。

```text
MATERIAL_E2E = FAIL
AUTONOMOUS_EXECUTION = YES
AUTONOMOUS_DELIVERY = NO
REQUIRED_COVERAGE = 未建立正式覆盖（未进入供给；草稿0/9）
ELAPSED_TIME = 20分15秒（正式确认后16分05秒）
CALLS = 方案Agent3；Delivery Agent9；素材Provider/生成0；模型内部API次数未知
COST = 生成占额¥0/¥10；模型及总实际账单未知
ENGINEERING_INTERVENTION = 0
BLOCKERS = 声音参数误入视觉Need，Planning原文要求未完整覆盖；系统3次失败后自动停止。
```

本次仅验证固定版本，未继续修复、恢复或启动第三轮验收。第一次和第二次 FAIL 均保持；全部脱敏记录与正式失败现场保留。


## 后续软件根因复核与修复（2026-10-06）

用户随后要求优先查根因、写方案并设目标。此阶段与上述独立验收隔离，原FAIL不改算。进一步版本证据确认：最初已在全部10个Need复制voice_delivery，合法Voice对象编译原本受支持；scalar报错来自非Voice副本。repair的scalar-only提示导致3个别名继续污染，最终视觉原文覆盖拒绝。同时，异步重入未持久限制“单次”结构修复，错误变动产生新请求，累计7次。

已完成[独立软件修复目标](../tasks/planning-modality-contract-2026-10-06.md)：共享模态校验及producer/repair一致规则，错误在视觉/TTS消费前拒绝；持久单次修复身份、pending/timeout复用、known-error不重派。合法合同与Material V1.3不变，不归一化或修改实际失败Need。全量731 passed/5 skipped、115技能合同、compileall/diff通过，Astra CONTINUE。

复核原workspace18项文件和14个旧Creation哈希无变化，第二轮仍failed且operation为空；Web/Gateway进程及启动时间未变。软件修改未提交加载，不恢复本轮、不调用真实模型或Provider、不启动新E2E。回归副本原SHA及测试对照说明见`tests/fixtures/planning-modality-contract-2026-10-06/README.md`。
