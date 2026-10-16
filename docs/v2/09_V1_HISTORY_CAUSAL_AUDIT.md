# Easel V2｜S2 V1 完整历史、需求演进与深度归因报告

> **S2-A / S2-B / S2-C / S2-D：COMPLETE（历史文档与具名原件的有界复盘）**；日期：2026-10-16。
>
> 本报告完成的是**历史事实还原和成败归因**，不是旧 V1 的修复结果、S3 经验与本次需求正式定稿、S4 V2 需求批准或 S5 新架构冻结。仍有不能由档案确定的因果机制，明确列为待证。全面覆盖项目的主要需求、决策、架构、验收与变更脉络，不等于逐字节审核全部私有运行记录。
>
> **V1 Git 固定点**：`easel-studio@57c8e2ade21af9fb6abccdab3f7ba8e50132314f`；V2 当前 S1 业务代码事实点：`easel-v2-rebuild@8eeafb6b9bf62b26e2077057cbebe45721f5d464`；S2 工作分支单独保存本报告，历史分支及私有证据只读。
>
> **流程约束**：已获认可的先后顺序在 [S2–S5 研究/设计流程 PR #3](https://github.com/webxia/Easel/pull/3)；S1-A [PR #1](https://github.com/webxia/Easel/pull/1) 与 S1-B [PR #2](https://github.com/webxia/Easel/pull/2) 均属于各自业务基线的独立待合并报告。S2 研究报告不能绕过它们的审核，也不能静默将旧要求带入本次 V2。

## 0. 审计边界、来源和证据真实性

### 0.1 本轮实做了什么

1. 用 Git 比较 V1 与 V2 的共同祖先，按第一父历史审阅**130 个 V1 主线提交**及历史变更消息；与共同祖先 `406438c30835a67ad9a1daaab99bcf8f4024ec61` 相比，V1 **专属提交总数 131**（含一处非第一父历史）。
2. 对旧 Git 树的 **71 份 Markdown** 做分类与标题/状态覆盖：根层 12、architecture 3、decisions 3、tasks 15、acceptance 35、configuration 2、workstreams 1。浏览核心产品/架构/ADR/Task/验收原文并核查代表性源码/校验点。
3. 实际读取旧历史索引、22 项清单与 CSV，并用旧源码检查几个确定性缺陷；沿代表性真实 Creation、Material 和 Planning 运行重建前后因果，不将单个 Task 的“PASS”当成完整结果。
4. 从 APFS 独立 `raw-evidence` 快照**重新计算七份 final-audit.json 的 SHA-256**，与私有 `inventory/final-audit-shas.json` 全部一致；读取 R14–R19 的安全字段（run、结果、HTTP、token、Repair、终态）并与 V1 Git 内 E2E/Planning 账本交叉核对。
5. 整理先前的**正确业务约束、已证实成功、修复收益、失败机制、合法阻断、未验证部分**及旧报告 22 项缺陷之间的关系。没有运行旧 V1 生产、旧模型、媒体生成、费用对账修改或原数据回放。

**证据等级**：`FACT_DIRECT`（原件/源码/运行事实可核）；`CAUSE_SUPPORTED`（明确代码机制及前后对照，仍列适用范围）；`HYPOTHESIS`（存在竞争解释，尚无充分对照）；`INTEGRATION_GAP`（目标未取得端到端验收）；`CORRECT_BLOCK`（有效拒绝，不等于产品缺陷）。结论同时保留 `DESIGNED / IMPLEMENTED / SOFTWARE_PASS / REAL_RUN / CREATOR_ACCEPTED` 和 `FAIL / NOT_TESTED` 的区别。

### 0.2 归档保护与未验证范围

- V1 worktree：`/Users/xgx/Projects/Easel-V1-Archive`，只读 Git `easel-studio@57c8e2ad`；历史索引与快照：`/Users/xgx/Projects/Easel-V1-History`；完整 Git Bundle 在其 `inventory` 内。没有将私有证据或旧代码放入 V2 生产 Git。
- 私有归档索引记录 **215,318** 个运行证据文件、逻辑字节 **8,976,217,804**（约 **8.36 GiB**）。`archive-verification.json` 的文件数、类型、大小核验匹配；20 项 mtime 与索引不同。**不宣称全量逐文件 SHA-256 一致，也不宣称这些证据代表 215,318 次独立运行**。
- 七份 `final-audit.json` 重新哈希核验 `7/7 MATCH`：独立 takeover audit 一份；R14～R19 六份。R14–R19 均为 **FAIL**，不包含完整 Planning 成功。表中原始 Token 为 Provider 报告口径，不是现金或套餐实际扣费证明。
- 本报告没有重复调用 MiniMax/OpenClaw/Hypit、公开 Provider、真实浏览器或对历史数据做数据迁移。关于其他未逐份读取的日志，只按既有清单/文档注明证据边界。
- Git 分支专属时间线自 2026-09-29 起；部分验收文档记录了更早的 9 月 27～28 日运行，按当时具名记录纳入，但**没有证据证明更早全部研发史已由这 131 个专属提交覆盖**。

## 1. S2-A｜项目历史目标与需求演进

### 1.1 核心定位的稳定部分

V1 以 Creator 为中心的长期创作工作台为总目标，一期**仅聚焦视频**：一个 Creator/Profile、一个 Director/Creative Mode、变化的 Content，产出可辨认稳定风格、可追踪、可审阅的视频。Creator 表达谁、Content 表达什么、Director 决定怎样表达。这在 [项目目标](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/docs/00_PROJECT.md) 和 [视频架构](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/docs/architecture/easel-video-architecture-v1.md) 中均有明确记载。多 Director、非视频内容、长期知识复用和自动社媒运营是更长期方向，**不是当期必须完成的生产主线**。

旧文档特别指出：“Director 是产品概念，不必独立持久实体；领域概念不是每一个都要新建表”。这一点是当时的设计边界事实，不是宣称它已经获得跨版本实际效果验证。

### 1.2 历史需求谱系（HREQ：仅表示过去需求，不是新 V2 ID）

下表按旧工程文档中的确认层级重新归档；同一行可能既有历史确认的业务意图，也有后来版本化的实现策略。**S4 需重新确定哪些属于本次 V2；本表不代替用户本次批准。**

| 历史标识 | V1 当时要求/意图 | 需求状态和演进证据 | 实现与验收边界 |
|---|---|---|---|
| HREQ-01 | 以 Creator 身份/事实为稳定表达边界，Content 可变 | **历史稳定产品目标**；9/29 产品基线及架构 | 后期有实际单作品审阅，跨多题材一致性没有完整产品验收 |
| HREQ-02 | Director/Creative Mode 控制镜头语言、节奏、视觉、声音、风格，不强制独立实体 | **历史稳定设计原则**；9/29 Creative Mode 与视频架构，后续单模式冻结 | `creative_modes/clear_memo_video` 及执行投影存在；跨作品风格不能因文件存在宣称通过 |
| HREQ-03 | 从创作讨论到明确方案修改/版本确认，再进入制作 | **历史已采用的交互目标**；9/30 创作画布、10/01 `e2f42639` 正式加强完整 Script/Scenes/Sound 的确认 | 9/30 作品确认链真实存在；早期错误引导和状态误报亦发生 |
| HREQ-04 | Creator 确认后尽量自主产出可审阅首版，必要时局部修改，尽量不工程救场 | **明确目标修订**；9/30 `8e4ef2e9` 以自主首版反向审视流程，后续唯一 Creator Task | 9/30 成片获 Creator 接受，但工程介入令 AUTONOMOUS FAIL |
| HREQ-05 | 一部作品可有不同 Attempt，保留版本/状态/成果、允许有界恢复 | **历史架构/实施要求**；Creation 生命周期、10/01 多轮恢复改造 | 曾恢复真实 Build/素材；不代表所有恢复路线可靠 |
| HREQ-06 | 新视频主线由 Easel 拥有 Creation/Review，创作 Agent 负责创作，Hypit 拥有制作/渲染 | **历史已接受架构**；ADR-001 与 9/29 视频架构，10/11 更新为单一 New-Only/Delivery Owner | Hypit Native Build 与输出有真实证据；新入口全链仍未验收 |
| HREQ-07 | Material 供给须覆盖合法 Need，来源、Rights、技术检查、Match/Bundle 与 Readiness 可追溯 | **历史已接受边界**；Material V1.3 与 ADR-004，始于基线前的设计来源 | 9/29 外部视频 Need 真实 READY；10/05 后有受限 9/9 Ready；不等于新 Web 端到端 |
| HREQ-08 | Material 不得改写 Content/Director、抢管 Timeline/Build | **历史领域责任约束**；Material V1.3 与 ADR-004 | 正确职责划分曾被代码/测试验证；与 Creator Hard、导演实现承诺的交接仍有风险 |
| HREQ-09 | 真实语音、字幕、BGM 与音画制作；保留正确的 Rights/授权 | **长期视频需求，在 9/30 mixed 作品中出现** | 36 秒真实混音片成功但非无救场；Voice/BGM 局部证据与匹配问题持续出现 |
| HREQ-10 | 静音、纯音乐、旁白、旁白+BGM 四模式由同一 Proposal 表达，不默认降级 | **2026-10-11 明确用户批准的 V1 选择 A**；New-Only `1.1、`3.1 | Proposal @4 方案/软件改造存在；四模式同版真实 E2E 未验收 |
| HREQ-11 | Web 是 Creator 工作台，不应是内部工程调度台；用户只处理实质决策、授权和审阅 | **2026-10-11 明确用户批准的 V1 选择 B**；New-Only `1.1 | 旧 UI 曾泄露内部信息；新 UI/Delivery 软件进展不能冒充已实机验证 |
| HREQ-12 | V1 视频能力范围 1～900 秒，不能静默缩成 300 秒 | **2026-10-11 明确用户批准的 V1 选择 C**；New-Only `1.1、`3.5 | U3-S 50 秒软件视频；U3-L 长片/四模式未取得同版资格 |
| HREQ-13 | 用户事实、Truth、Rights、费用与不可逆操作不得由模型擅自授权 | **历史长期业务/安全边界**；9/29 初始目标、ADR-004、10/11 主方案 | 发生过正确 RIGHTS UNKNOWN 拒绝；不能因 E2E FAIL 认定应放宽 |
| HREQ-14 | 允许现有结果复用、局部修订，防止重复付费、UNKNOWN 重派与改写历史证据 | **历史实施与安全策略**；9/30–10/11 多轮恢复/ADR-005 | 同原 Operation 冷恢复有软件及部分真实证据；跨 Attempt 共享预算最终原子准入未完成 |
| HREQ-15 | 唯一 New-Only 生产协议，旧 Producer/Parser/Writer 退役，历史 Attempt 原件保留 | **2026-10-10～11 已批准的 V1 迁移方案**；ADR-001/005、New-Only U0–U6 | U2 候选和旧入口退役有软件证据；该方案是 V1 的过渡性实现选择，**不是 V2 要求保留旧合同** |
| HREQ-16 | 用真实可播放视频、Creator 审阅/接受和必要恢复衡量交付，而不是只看 Planning PASS | **历史业务验收标准在后期明确强化**；9/30 Creator E2E、10/11 New-Only `8 | 早期作品局部成功、U3-S 软件成功；最终 New-Only 真实 E1 仍未完成 |
| HREQ-17 | 对调用、Token、时间、人工负担和质量做有据可比的优化 | **历史阶段性优化方向**；10/02 耗时 Task、10/14 U7 backlog | U7 明确 **NOT_STARTED**；单题重复调用不能当作跨主题优化效果 |

**确认等级说明**：历史设计/ADR 批准不等于用户逐字段批准实现；Task 中写的次数/Schema、R 编号、B 审核批次、固定 Probe/PIN、旧 Provider 参数、临时预算阈值等，原则上是历史实现和验证策略，不能自动当作“历史业务需求”。10/11 A/B/C 及旧合同清理有明确文档化选择；它们仍只属于**当时 V1**。

### 1.3 从 Git 和真实验收还原的关键转折

| 日期/版本证据 | 核心演进 | 实际改变与效果 | 当时还未证明的能力 |
|---|---|---|---|
| 9/27～28 历史验收文档，9/29 `94135cf3` 初始 V1 专属提交 | 前期 Material V1.3、创作对象和 Creation+Hypit 职责进入 Creator 工作台基线 | 具备 Material 模态/Provider 软件与隔离生成冒烟；历史档案已有此前日期文件 | 隔离生成、素材就绪不等于真实成片 |
| 9/29 `94135cf3`；[外部素材 E2E](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/docs/acceptance/external-material-product-e2e-2026-09-29.md) | 真实 Pexels 视频 Need、Rights 和 MaterialReadiness | 一条 10 秒静音方案的 required 视频 Need **1/1 READY**，经历网络 DNS 校验改动与操作员视觉复核 | 尚未进入 Authoring/Build/Creator 审片 |
| 9/30 `d5c6ab51` ～ `23b42f05` | Creator Web 工作区、讨论/确认、旁白/BGM、修订/审片与入库 | 12 秒静音作品和 36 秒 mixed 作品曾打通正式用户路径，36 秒成片被明确接受；多次工程修复后才成功 | “无需程序员介入”仍失败，风格稳定性只有局部证据 |
| 9/30 `8e4ef2e9`、`da41721d` | 目标从局部功能推进改为“Creator 确认后自主首版” | 修正流程先后次序、强调跨内容和最小人工负担 | 尚缺可重复无人救场完整 E2E |
| 10/01 54 个第一父提交（示例 `6a265c85`、`3f1cd952`、`76789431`、`3c005db0`） | 声线参数、字幕、BGM、观察、恢复、系统 Quality、用户展示与连续执行的大量实现 | 出现正式质量/局部音轨/恢复能力与独立软件回归，亦增加多个消费与状态接点 | 多修复不等于同一稳定版本的真实生产通过 |
| 10/02 `50f48158`、`54df94c1`、`eb16c8bd` | Director 取舍、跨 Need 素材观察复用、局部组合选择 | 具体候选复用和恢复性增强；后续验收仍显示速度、匹配和人工成本不足 | 风格和真实供应跨内容稳定性 |
| 10/03～05 `964104fe`、`ad31091e`；v0.4/v0.5 Acceptance | 从制作质量/耗时问题深入素材观察、音频供应、Rights/恢复 | v0.5 既有作品 5/9→8/9，多次恢复保留成功图片/旁白，BGM CDN/署名/声学缺口显现 | 普通用户独立到 MATERIAL_READY 的可重复性 |
| 10/06 `43d2eb56` 与独立 Material E2E 三次 | 受限原作品通过一项 BGM 策略达 9/9；新作品连续验证 Planning/Truth | 旧 Attempt 一次局部策略下 `MATERIAL_READY` 成立；**三次新独立作品都未进入 Material Supply** | 新作品闭环、广泛 BGM 能力、正式制作 |
| 10/06～08 `55af28fb`、`99b3ca83`、`aa0ab42a` | 模态边界修正、Planning canonical 语义、Harness 捕获、A/B Review/Repair 重构 | 软件测试、矩阵、冷恢复明显加强；10/08 新真实 Development 首例即失败 | 模型真实 carrier 合规率、正式完整 Planning |
| 10/09～10 `82b66519`、`5e228e89`、`39ca8fcf`、`4d811058` | ADR-005 模型结果接收、Native Authoring、历史可执行协议退役 | 更明确地保留原回复、绑定程序身份、语法接收和业务准入分层；旧 Hypit 测试精准退役/当前风险回归有软件证据 | 真实模型 + Web + Material + Build 同版贯通 |
| 10/11～12 `ce6fa817` 之后的 U2/U3-S 验收 | 用户批准 New-Only 唯一标准：Proposal @4、Delivery Owner、四音轨、900s；实施一个当前候选 | U3-S 用合法固定外部回执得到 **50.000 秒** 本地 MP4，真实 Hypit/媒体/Quality/冷恢复 | U3-L/900s、真实 U4 Web/费用准入与 U5/U6 全链未完成 |
| 10/14～16 `990feb43`、`d82bb60b`、封存 `57c8e2ad` + 独立私有运行快照 | B Review/Planning 治理、MiniMax M3.1 有界真实调试、证据/预算与文档收敛，最终封存 | 多项结构/容量/工具终态/恢复问题获得定位，部分仅离线修复；R09–R19 仍 **0 完整 Planning PASS** | 不允许把专用 Planning 调试的局部成功当作新 Web 出片 |

**一个重要时序差异**：初始 [视频架构 `14/`20](https://github.com/webxia/Easel/blob/94135cf3afd83c36a5e4dcddbe2b409be4973657/docs/architecture/easel-video-architecture-v1.md) 描述 `Authoring → Material Resolution`；同初始基线内 [Material V1.3 `4A](https://github.com/webxia/Easel/blob/94135cf3afd83c36a5e4dcddbe2b409be4973657/docs/architecture/material-layer-v1.3.md) 则描述 `PLANNING_READY → Material Supply → MATERIAL_READY → Production Authoring → AUTHORING_READY`。这说明**旧权威文档的生产先后表达曾不完全一致**；10/11 New-Only 主方案明确采用 Material 先于 Native Production Authoring。不能仅因初始两个图不同就推断每次实际运行都出现双轨，需按受测源码和运行回执判断。

## 2. S2-B｜真实作品、素材与制作链路的双向证据

### 2.1 已有可确认的成功资产

| 具名案例/来源 | 已经真实证明 | 不能推出 |
|---|---|---|
| 9/28 [MiniMax Image/Voice](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/docs/acceptance/minimax-image-speech-smoke-2026-09-28.md)、[Video 冒烟](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/docs/acceptance/minimax-video-smoke-2026-09-28.md) | 隔离调用产出图/视频/声音并尝试进入素材流程 | 已在正式 Creation 的 Rights/Match/Build 闭环中成功 |
| 9/29 外部视频素材工作流 | 真实 Pexels 检索→获取/技术检查→Rights→Match→1/1 MaterialReadiness READY；修复过 VPN 合成 IP 误拒 | 每个图库/BGM 都稳定、Creator 作品完整 |
| 9/30 [Creator 工作区 E2E](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/docs/acceptance/creator-workspace-e2e-2026-09-30.md) | 12 秒静音作品经过正常 Web 入口、编排/成片/最终入库；错误修复的边界与回归有记录 | 全程无工程介入 |
| 9/30 [Creator 音画 E2E](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/docs/acceptance/creator-audio-quality-e2e-2026-09-30.md) | **36.0 秒**、1080×1920 H.264/AAC、实际 Creator 明确回复可用并保存，最终文件与 Selected Output SHA 匹配；不自动发布；失败 Build 可按证据恢复 | AUTONOMOUS PASS、整体风格完全达标；它明确记录 AUTONOMOUS=FAIL 和 STYLE_CONSISTENCY=PARTIAL |
| 10/05～06 [旧素材恢复](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/docs/acceptance/creation-latency-v05-material-resume-2026-10-05.md) | 保留已得到素材/声音与生成结果；10/06 R17 在**当前原作品定向音乐规则**下经 Rights/Match/Readiness 达到 required 9/9，无新的模型/Provider/生成调用 | 泛化音乐纯器乐分类可靠；新作品独立供给成功；旧 Attempt 视频 Build 已发生 |
| 10/12 [U3-S 本地连续集成](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/docs/acceptance/easel-v1-web-real-e2e-2026-10-10.md) | 一条 50.000 秒 H.264 1080×1920/AAC、本地 Hypit Check/Plan/Pricing/Build/Export、内部 Quality、拒绝与冷恢复，在固定外部合法回执下通过 | 真实 MiniMax Planning/Truth、外部素材、真实人工 Review 或 Web 自主 E1 成功 |
| 10/10 [Native 测试退役验收](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/docs/acceptance/adr005-hypit-native-legacy-test-retirement-2026-10-10.md) | 按固定旧 Blob 精准替换 20 个旧测试函数、保留有价值的旧正例与当前 Native 风险测试；当时 450 项软件回归 PASS | 自动消除真实生产的所有协议/模型问题 |

**重要的正确阻断也属于有效资产**：对来源伪造、权限缺失、Rights UNKNOWN、音频 SHA 不匹配、重复支付、UNKNOWN 未对账、非法 Need 及未确认 Build 的拒绝在具名边界上可能是正确行为。S2 评价的是拒绝对象与证据是否真实、是否允许合法补足，不以减少拒绝数量为成功标准。

### 2.2 反复失败时“真正执行到了哪里”

| 案例 | 当前版本真实执行到达 | 停止原因与分层 | 未执行的后续阶段 |
|---|---|---|---|
| 10/03 R3 / v0.4 | 有旧款真实 MP4 / 后续实际视觉观察尝试 | 内容/质量/效率/无需救场不达标；v0.4 `observe_material` 共享观察报告缺失/过大 | 不能从一次存在 MP4 推出可靠首片 |
| 10/04～05 v0.5 新作品/原作品续接 | Planning、部分真实图片/旁白/BGM 获取、生成结果复用 | 5/9→8/9 素材供应，CDN403、Rights 信息遗漏和声音识别/匹配问题并存；部分质量检查误判 | 原素材不足版本未到 Authoring/Build |
| 10/06 独立作品 #1 | Web 普通确认→Preparation→Planning 草稿 | 全部 7 视觉 Need 的要求以包装对象/混入音频 ID 提交，正式根合同拒绝；**没有进入 Material** | Supply/Rights/Authoring/Build 均未跑 |
| 10/06 独立作品 #2 | Web 确认→Preparation→多次 Planning 修复 | `voice_delivery` 被复制到视觉 Need；修复又把声音参数扁平散布于全部视觉 Need，形成原文覆盖缺口；同一 Attempt 累计 7 次结构修复 | Supply/Rights/Build 未跑 |
| 10/06 独立作品 #3 | Web 确认→Preparation→Planning 结构检查→Truth | 冻结“文案”连同元说明进入 `SCRIPT.md`，Truth 将制作说明判为 `rewrite_required`，确认稿不可静默改写，因而正确拒绝当前输入 | PLANNING_READY 未建立；0 素材查询/生成 |
| 10/08 vNext 开发评测 | 一个隔离新 Creation 的 Preparation/A 真模型调用 | 软件 196 项矩阵 PASS，但首个模型结果不符合语义 carrier，6 个计划样本只执行 1 个，且在 B/Truth 前停止 | 不能外推新架构已实机稳定 |
| 10/12 U3-S | 固定外部回执→真实本地完整媒体渲染/Quality/冷恢复 | **软件集成成功，但外部 Model/Provider/人工审片被替身替代** | U4/U5/U6 真实 Web 首片与 U3-L 正式长片 |
| 10/15～16 R09–R19 | 隔离真实 MiniMax Planning A/B/Repair 多批次 | 多种 Schema/源码引用/工具终态/预算/语义分类阻断；无一次完整 `PLANNING_ACCEPTED` | 正式 Truth/D2 Proof/Cold、Material、Build、Creator Review 均未以真实新作品全链验证 |

**不是单一模型错误：**10/06 三次独立作品的失败是三个不同合同/表达路径：包装形状、模态字段污染、确认稿与 Truth 输入切分。一次软件修复后新作品继续在别处失败，说明端到端边界不稳定，但不支持“所有 Material 或 Hypit 模块都坏了”。

### 2.3 完整新路线的最终证据边界

[旧 V1 Current State](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/docs/02_CURRENT_STATE.md) 的晚期事实：U2 是已建立但需要版本同一性的候选；U3-S 50 秒软件集成 PASS；U3-L 的接近 900 秒/四声音模式/长 BGM/完整语音与资源资格未正式通过；U4 Web/Rights/费用真实准入 BLOCKED；U5 未正式进入，U6 未执行，Release 未授权。**因此“曾有可接受 MP4”与“New-Only 自主主线 E1 成功”不能合并成一条结论。**

## 3. S2-C｜深入归因：从个别失败还原失效机制

### C01｜冻结创作委托保存完整 ≠ 消费者获得完整委托

- **实际机制**：`easel/creator_proposal.py:79–82` 保存了 `specification_notes`；但 `easel/integrations/planning_semantic_review.py:81–96` 构造 B 证据时取冻结 confirmed、`specs`、mode、Creator/Truth 等，没有把图库替代许可的具体备注作为等价消费约束；`planning_candidate_review.py:92–109` 只增加当前 audio 相关字段。归档 R14 原始请求指出 A/Repair 持有备注、B 批次缺少。
- **已支持的原因**：多阶段“投影输入”遗漏了用户在确认时允许的导演调整范围。它**可能放大**下游硬约束、不必要未决与误审，但未证明每一条 R14 B 未决均由此一因产生。
- **补充反例**：保存文本、SHA、Scope/ID 全部正确也不自动保证阶段需求完整；同理，删除所有审核并不是合理修正。
- **分类**：`FACT_DIRECT + CAUSE_SUPPORTED`（上下文遗漏）；“它直接造成全部 B 错答/零工具”=`HYPOTHESIS`。

### C02｜“原文位置”误当“镜头身份”，叠加审核机械展开

- **实际机制**：`planning_authority.py:115–127` 按 `SCENES.md` 的非空物理行建立 scene/segment/event alias；`planning_semantic_review.py:53–77`、`121–126` 继续以这些范围组织冻结视觉覆盖。R14 七个真实镜头在来源目录中出现 11 个“scene 行”。
- **后果**：不是单纯模型“理解差”，而是程序对同一文本的组织方式已经扩大和扭曲审查范围；同一 Need 上的多条件、来源和类别进一步展开出 67 道 B 题／9 批。R14 B 报告 **756,756 / 925,943** Token，约 81.7%，多批都重复给定大量共同证据。
- **边界**：67 问不等于 67 次 Provider 请求，不等于其中全部题毫无价值；哪些属于真正必须的语义保证，需逐条件看责任和消费者。
- **分类**：`FACT_DIRECT + CAUSE_SUPPORTED`（范围错误和审核成本）；“全部复杂度可删”=`HYPOTHESIS`。

### C03｜Creator 硬要求、导演实现承诺、可适配偏好和素材事实混淆

- **实际现象**：R14 曾将浅景深、傍晚光线等摄影表达提升为 `material+required`，又把“笔筒或笔搁”、非必需音乐点缀、后期调整等作为需升级的问题。现行 Planning Task `2.4 已明确区分 Creator Hard、Director committed、Creative Preference、postproduction 和真实素材 Need 的不同消费者。
- **可支持归因**：阶段曾允许模型将“怎样拍/怎样剪”的选择视作“原始媒体必须具备的属性”，并把已授权自由度当新用户决定，可能形成虚假 MaterialGap/审核负担。
- **必须保留的边界**：不能因此降低真正 Creator Hard、人物/内容授权、Truth、Rights 或合法 Source 资格。素材还未获取时的来源版权待核验，不等同“Creator 未授权某种用途”。
- **分类**：举例具有原件 `FACT_DIRECT`；“所有虚假硬条件皆由投影造成”仍为 `HYPOTHESIS`。

### C04｜模型端、Agent Runtime、工具协议和业务准入并非同一件事

- **实际发现**：10/08 vNext 软件 196 项矩阵 PASS，但首个真实 A carrier 不符；同月的专用 OpenClaw Runtime 能力审计表明普通 agent RPC 不暴露项目所需的任意动态工具约束，底层 builder 虽可表示特定工具、但工具参数缓冲有 **256,000 bytes** 上限；当时一个合法合成 A 容量样本约 1.33 MB，而实际 d01 只有 7,849 bytes，**不能倒算超限是 d01 失败原因**。
- **后期真实事实**：R17 B-008 与 R18 四次 A/Repair 总计 5 次 `HTTP 200/SSE 终态`、`finish=stop`，没有可接受的 Tool Arguments；输出 Token 也未达到当时 8,192 的输出上限。单独 HTTP 成功不代表模型产生合同结果。
- **隔离缺陷**：历史 R14/R17/R18 的专用 Planning 请求携带 OpenClaw 通用 `AGENTS/SOUL/IDENTITY/USER/BOOTSTRAP` 等约 20KB system 上下文；`8.40` 后来离线隔离并修复了已定位的运行时隐式失败重派分支，**实际生产未重新加载/全链验证**。
- **竞争性解释**：模型未遵从复杂 Schema、工具选择实现/Provider 兼容性、上下文污染、动态生成压力均可能贡献；没有实际最小对照证明哪一项单独导致零工具。
- **分类**：分别记录 `FACT_DIRECT` 与 `CAUSE_SUPPORTED` 的输入/协议问题；“某模型必然失败”或“换工具一定解决”=`HYPOTHESIS`。

### C05｜模型被要求回抄身份与复杂异构 Wire，Repair 又重复完整上下文

- **实际机制**：原设计一度要求模型同时负责语义选择、来源引用、role/quote、ID、Need 关系、字段形状。R09–R19 多次出现在 `src_*` 以外的错误 source ID、遗漏必填字段、异构 B 回答、quote 支持关系错误；原 29 批 225 道题离线核得 **51 个局部目标：38 表示结构、13 领域引用**。
- **确定性软件缺陷**：R09 有 9 批合法原回执，但全局 Repair schema 合并遇到跨批局部同名类型定义不一致；代码问题通过原件离线回放、局部名称/引用闭包重命名及 52 项回归修正。**这并非模型没生成 B、也不由重试模型解决**。
- **本地容量问题**：R11/R13 Repair 请求达 1,136,224 / 1,172,075 bytes，超过**本地** 1 MiB guard；去重后的可逆表示减至其限内，R14 171,450-byte 真实 Repair 成功派发和回传，证明**容量/重复组装**这一子问题改善。
- **未解决的部分**：R14 仍被后续领域语义分类拒绝；不能说“压缩/格式改造已经提高真实完整 Planning 成功率”。保留严格未知来源拒绝，减少程序可以确定的字段回抄属于当时提出、尚待总体效果验证的工程经验候选。
- **分类**：`FACT_DIRECT + CAUSE_SUPPORTED`（schema 合并、请求体过大）；真实语义完成率改善=`NOT_PROVEN`。

### C06｜恢复权限和预算 Owner 分层不明，使局部失败消耗整条链的机会

- **实际现象**：R11 有原生 `stop+0tool` 后经新 Operation 合法恢复的单点案例；R17 的 B-008 零工具没有相同准入；R18 的多次 no-tool 消耗 3 次共享 Repair，另一个局部工作无法继续。历史 SDK 的 `assistant-failure` 隐式恢复曾在同 Run 内重复并覆盖最后 transcript；外部 Owner 又有自己的 Repair/Regenerate 判定。
- **预算定位**：旧 `easel/creation.py:123–147` 负责 Creation 级文件锁/持久化，`creation_delivery.py:57–85、288–315` 管理 Delivery/Attempt 预算和执行互斥；而 R14–R19 实验共享跨 Attempt 的 `task-http.lock` Owner 在封存私有 `2026-10-15-planning-repair-context-dedup-r02/control.py` 中。后期 `completion_preflight` 是只读估算，未进入最终占额同一锁域。
- **R19 的精确定性**：原剩 7 HTTP 时仍启动一个不能证明完整完成的后继 Attempt，7 次之后本地 guard 拒绝下一 B。**没有证据证明第 61 次 HTTP 被发送，也不是现金超支。** 问题是整体剩余工作量与最终共享占额 Owner 的决策衔接，而不是“预算 guard 完全无效”。
- **边界**：多层状态的存在本身不证明故障；Creation、Attempt、Build、Provider 都有合法的不同生命周期。风险在同一操作的最终“是否可再次发送/谁拥有预算和恢复”没有唯一、可证明一致的权威。
- **分类**：R18/R19 恢复行为及预算缺口 `FACT_DIRECT + CAUSE_SUPPORTED`；“所有状态应合并为单一新数据库/内核”=`HYPOTHESIS / 未作 V2 决策`。

### C07｜Material 供应、Rights 证据、观察算法与 UI 状态可彼此脱节

- **真实供应缺口**：10/05 v0.5 从 5/9 恢复到 8/9；Openverse 音频获得 20 候选并不代表 20 个可下载。早期 Wikimedia CDN 前三项 HTTP403，补合规 User-Agent 后有一项正式获取成功；不能判定所有 403 都是 UA 的唯一根因。
- **正确拒绝与信息遗漏**：获取成功的 BGM 真实有 CC BY4.0/作者等来源事实，但 Adapter 没完整传播 `ATTRIBUTION_REQUIRED` 与可追溯来源，Rights 先正确阻断。恢复元数据后不会自动证明该音乐的“无歌词/听感”条件。
- **分类器泛化不足**：BGM v0.6 旧规则的 6 个器乐正例只通过 1 个、26 个风险负例误放 5 个；允许 5/6 正例通过的候选规则仍误放 5/26；附加 VAD 不能同时满足当时正负要求。**这只否定那组样本和规则下的自动声学保证，不证明原作品音频有声乐**。
- **局部正例与限制**：10/06 旧作品 R17 在用户明确放宽的**当前作品**规则下，保留 Rights/Match/Readiness 并达 9/9；其留出泛化校准仍 FAIL，且没有接着执行 Authoring/Build。
- **Voice/UI**：历史有旁白事实、SHA 和试听已存在，但缺语义审核证明导致提示再次生成的情况；错误应归于已验证资产的事实/状态投影与 UI 说明，不把生成能力等同审核结论。
- **分类**：供给/权限传播/声音匹配各有 `FACT_DIRECT`；“任何单一模型/Provider 足以解决全部素材问题”=`HYPOTHESIS`。

### C08｜验收和治理逐渐脱离普通用户闭环，历史迁移本身扩大成本

- **已实证的落差**：9/30 有 Creator 接受视频，但需要工程救场；10/06 三次独立 Material E2E 均未进 Supply；10/08 软件 196 PASS 但首个 Development FAIL；10/12 U3-S 本地 50 秒 MP4 成功，但模型/外部 Provider/人工审片为固定回执；R09–R19 再次出现高额模型调用却无完整 Planning。
- **编排/文档因素**：早期同时出现 `Authoring→Material` 与 `Planning→Material→Authoring` 时序表达；后期 Proposal @3/@4、旧 Producer/Writer/Parser、五 Pin、A/B/Truth、修复、不同 Role 和旧测试假设曾共同存在。10/10 ADR-005 和 10/11 New-Only 已尝试清理执行双轨，保留旧原件为只读证据。它们是**合理治理的一部分**，不能全部贴“无效复杂度”的标签。
- **因果范围**：大量联动修改增加维护与回归面可以从 130 个主线提交及事故回归追溯；但“测试数量多直接造成模型失败”没有因果证据。核心产品问题是软件正确性与真实完整作品之间存在反复未通过的接口。
- **分类**：完整 New-Only 真实 E2E 资格缺口=`INTEGRATION_GAP`；“所有严格测试都应删除/所有 Gate 都错”=没有证据。

### C09｜工程问题与业务安全阻断必须另立分界

- **正确阻断**：未明 Rights、Creator 不可变要求、真实来源不存在、实际音频/素材不符合安全或授权要求，不得因为未出片而直接降级；预算用尽后未继续额外 HTTP 也是正确的安全底线。
- **待解决的真正差异**：错误来源分类、事实投影遗漏、可调整导演行为误变用户审批、无法合法补料、误将软件内部进度作为 Creator 操作提示、已有合格产物无法恢复等。
- **判断**：历史 `CHALLENGE/UNRESOLVED/NOT_READY` 必须看“要求从哪里来、当前哪个阶段有能力确认、是否有合法替代”，不能靠将其全改为 PASS 证明架构合理。
- **分类**：`CORRECT_BLOCK` 与 `FAILURE_MECHANISM` 并存，逐案处理；本报告不作 V2 业务规则重定。

## 4. R09–R19 历史模型调用与根因对账

同一 45 秒桌面整理主题，共 11 次**非独立题材** Attempt，原报告及账本记录 **89 次完成 HTTP**，合计 **5,490,834 Provider 报告 Token**，完整 Planning 成功 **0**。这是这一题材的历史尝试事实，**不能当跨主题真实成功率的统计样本**。R07/R08 另有旧 12 次，总范围 R07–R19 为 101 次（不同已封存额度账本）。

| Attempt | 真实 HTTP | 当次主要停止原因（已归类） | 主要责任层 | 后来是否有子问题得到改善 |
|---|---:|---|---|---|
| R09 | 13 | 9 批 B 原回执到达；16 局部修复目标的同名动态 Schema 定义冲突 | **程序 Repair 汇编** | 同名引用闭包重新命名、离线 52 回归；原失败不追认成功 |
| R10 | 1 | BGM Need 带入仅视觉允许的 `header_claim` | **模型结构/模态输出** | 严格拒绝正确；后续新 Attempt 仍可能有不同错误 |
| R11 | 15 | A 与 10 批 B 到达，Repair 1,136,224 bytes 被本地 1MiB guard 拦截 | **程序上下文容量** | 后续可逆去重、R14 真实 Repair 派发证实子问题改善 |
| R12 | 1 | A-selection BGM scope 使用不存在的 `src_37` | **模型来源引用** | 未用模糊补全篡改原回复 |
| R13 | 15 | A/B 到达，Repair 1,172,075 bytes 再次超本地限额 | **程序上下文容量** | 后续离线表示修复并由 R14 验证发出 |
| R14 | 14 | 5 目标 Repair 成功回传；D2 将部分素材许可待供应归为 Source/Truth 权威问题 | **语义责任分类** | 后续提示澄清但无新完整 Planning PASS |
| R15 | 1 | 多个 Header 创作依据使用不存在的 `src_75` | **模型来源引用** | 原错误严格拒绝 |
| R16 | 2 | A-details 来源拼写错误且遗漏根 `unresolved` | **模型混合结构错误** | 不属于已授权的“仅来源错误”合法整批恢复 |
| R17 | 13 | B-008 SSE stop/无工具参数 | **工具/模型终态边界** | 原失败停止，离线 Runtime 规则后来局部修正；真实全链未复验 |
| R18 | 7 | 4 次零工具、共享 3 次 Repair 耗尽 | **工具终态与恢复策略** | 后期离线协议/身份/隐式重派修正，无生产级通过 |
| R19 | 7 | 共享总预算用尽，下一 B 在本地被拒；无第 61 次提交 | **调度剩余量准入** | 仅有只读预检，最终跨 Attempt Owner 未原子接入 |

**R14～R19 原始 JSON 实际哈希核验**：

| 原件 | 归档 SHA-256 前 16 位 | 哈希核验 | 原结果 |
|---|---|---|---|
| R14 `final-audit.json` | `775462b08f8c93c2` | MATCH | FAIL，14 HTTP，925,943 Token |
| R15 | `eba28ed99f91e3af` | MATCH | FAIL，1 HTTP，23,565 Token |
| R16 | `84376cbad82d89b` | MATCH | FAIL，2 HTTP，53,572 Token |
| R17 | `39fdf20c39e39849` | MATCH | FAIL，13 HTTP，936,133 Token |
| R18 | `6aa63be4c059f774` | MATCH | FAIL，7 HTTP，195,343 Token |
| R19 | `e49893142703cb8f` | MATCH | FAIL，7 HTTP，308,111 Token |

另有 takeover audit `25be11af3039bee3` 一份 MATCH。完整文件名与 SHA 在本地私有 `inventory/final-audit-shas.json`，不将原始模型提示/输出、机密字段或私有捕获复制入 Git。

R14–R19 六次共 44 HTTP / **2,442,667** 报告 Token，属于已关闭 60 HTTP 追加账本的后 44；最初 29 次的封存旧额与新 60 次的关系不应混成“可以重置重跑”的次数。实际现金结算 **UNKNOWN**，不能把套餐使用推为零成本。

## 5. 原 22 项问题逐条归因结论（不是 V2 修复工单）

原 `V1_SHORTCOMINGS.md` 标记 18 项“实证”、2 项“集成缺口”、2 项“架构风险”。本次保留原报告的历史等级，增加**因果是否证实、实际有效的修正范围、尚未解决什么**。`Cxx` 指本报告第 3 节机制，非新模块。

| 旧编号 | 事实/归因复核 | 对应因果簇 | 结论与剩余不确定性 |
|---|---|---|---|
| 01 | `FACT_DIRECT`；确认备注在 B 投影漏掉，代码与 R14 请求支持 | C01 | 漏投影确定；对 B 每项误判的直接贡献未逐题确定 |
| 02 | `FACT_DIRECT`；Markdown 物理行作为 scope，7 镜头成 11 范围 | C02 | 表示/身份混淆确定；不证明全部审核项都无效 |
| 03 | `FACT_DIRECT`；摄影实现/审美特征被作为源素材 hard | C03 | 责任/强度分类问题；真正 Hard 仍不得降级 |
| 04 | `FACT_DIRECT`；可授权导演选择被升级为 unresolved | C03 | 不必要升级实例存在；不能推为所有审核拒绝错误 |
| 05 | `FACT_DIRECT`；67 题/9 B 批和 Token 成本 | C02/C05 | 机械膨胀及重复上下文有证据；合理语义覆盖仍需区分 |
| 06 | `FACT_DIRECT`；五次已完成 HTTP 零 Tool Arguments | C04 | 发生原因在工具/模型/适配器间尚未单独定因 |
| 07 | `FACT_DIRECT`；通用 OpenClaw 初始化污染专用 Planning | C04 | 输入隔离缺陷确定；与零工具的因果连接仍是假设 |
| 08 | `FACT_DIRECT`；结构/来源混合错误有原件；模型职责过重有证据 | C05 | 字段回抄负担可归因，不能据此允许非法来源 |
| 09 | `CAUSE_SUPPORTED`；重复上下文使 R11/R13 超本地限额 | C05 | 去重后 R14 可真实派发 Repair；未改善完整语义验收 |
| 10 | `FACT_DIRECT`；不同技术/语义失败共用 Repair 额度且恢复资格不同 | C06 | 分类与预算策略影响后续继续资格，非所有停止均不合理 |
| 11 | `FACT_DIRECT`；最终共享 Owner 与只读预检分离，R19 余量不足 | C06 | 预算策略不完整；未发生超过总 60 HTTP 的发出 |
| 12 | `FACT_DIRECT`；SDK assistant-failure 隐式恢复覆盖 transcript | C06/C04 | 已有具名离线修正；未证明所有框架自动重试路径关闭 |
| 13 | `HYPOTHESIS/ARCH_RISK`；多处状态与锁存在 | C06 | “状态多”本身不是错误；跨不同 Owner 的一致性风险尚无统一全局失效证明 |
| 14 | `INTEGRATION_GAP`；New-Only 没有全程真实 Web 首片 | C08 | 目标未验收，不足以否定全部已成功子模块 |
| 15 | `FACT_DIRECT`；成片接受但工程介入/UI 泄漏 | C08 | 功能/成片正例与 AUTONOMOUS/CREATOR_VISIBLE 失败并存 |
| 16 | `FACT_DIRECT`；候选获取、CDN、Rights 证据缺口 | C07 | 部分 UA/署名子问题改善；所有来源可靠性未证实 |
| 17 | `FACT_DIRECT`；AST/VAD 校准正负例不可同时满足 | C07 | 特定配置/样本算法不够，不可推为 BGM 一律不合格 |
| 18 | `FACT_DIRECT`；Voice 已有事实、语义证据与 UI 不一致 | C07 | 丢的是资格/投影而非必然音频字节；重复生成不是唯一合理操作 |
| 19 | `INTEGRATION_GAP`；长片和四音轨未获得同版完整 E2E | C08 | 历史需求明确，V2 本次范围**尚未批准** |
| 20 | `FACT_DIRECT`；大量软件 PASS 与真实 E2E FAIL 同时存在 | C08 | 需识别证据层级差，不应以删测试或宽松 Gate 掩盖 |
| 21 | `HYPOTHESIS/ARCH_RISK`；冻结约束与可变导演方案边界不完全清楚 | C01/C03 | 历史有合法调整困难实例，但“局部修改必重规划”不是全局已证明规律 |
| 22 | `FACT_DIRECT`；迁移期间旧/新生产代码、协议和测试冲突 | C08 | ADR-005/New-Only 尝试清理，未证实全部运行时旧路径彻底失效或新链 E2E 已完成 |

**重要更正**：原 22 项是“值得研究的缺陷/缺口清单”，不是 22 个已证明独立根因，也不是统一的 P0 当前新系统缺陷。相同症状可能跨多个因果层，一个原因也可能放大多个后果。历史 P0/P1 严重度不随归档自动成为 V2 产品的优先级。

## 6. S2-D｜历史认知收口：哪些事实成立，哪些只是经验候选

### 6.1 已证实的正面历史资产（仅事实）

1. 以 Creator/Content/Director 区分表达身份、题材与风格，并允许单一 Creative Mode；这有历史产品/架构来源，但跨题材实际效果只部分验证。
2. 正式 Creation/Attempt、素材字节 SHA、合法 Rights、Selected Output 和 Creator Review 可以构成可追溯记录；历史真实成功样本证明局部链路成立。
3. Material 负责供给、Hypit 负责生产/时间线、Easel 负责产品/授权/Review 的边界在 Material V1.3/ADR 中清楚，部分路径和拒绝有实际执行/测试；**并不证明 V1 全部模块协作正确**。
4. 历史出现过真实视频、有效素材准入、保留正确旁白与局部质量修改、幂等 Build/冷恢复；成功要按其具名作品、版本和人工介入条件逐一引用。
5. 对 Rights UNKNOWN、不真实来源、非法 Schema、费用与 UNKNOWN 操作保守拒绝有合法安全意义；拒绝时若缺材料/需要决定，应向正确责任层升级，不应造假。
6. 后期开始区分原始模型结果、程序绑定、领域准入、修复和软件/真实验收；软件验证改善，但并未独立证明模型真实输出和 Creator 自主交付。

### 6.2 最主要的失败/放大关系（因果图，只表达有支持的部分）

**有证据支持的链式放大（各箭头不代表充分必要因果）：**

1. 已确认创作约束在部分消费者的投影遗漏，排版 scope 又被误用为业务身份。
2. 真实样本出现过多异构任务/Hard/未决，B 问题及重复证据规模扩大（R14 可量化）。
3. 非法引用、零工具结果、程序合并和容量拒绝以不同原因出现，并非单一故障。
4. 恢复资格与剩余预算约束限制后续继续执行（R17–R19），完整真实 Planning 未通过。
5. New-Only 真实 Web 自主首片最终仍未验收；这一步是整体结果，不能只归咎于 Planning 单因。
并行的另一条链是 **素材供给/音频/许可证据不全 → 合法 MaterialNotReady 或虚假导向 → 人工补救/重复提示**；它不能全部归入 Planning 模型失败。

以上是**带分叉的失效机制地图**，不是把前一节点当作后一节点的充分必要原因；零工具参数可能在任何复杂度阶段独立发生，R19 是预算停止而非模型输出错误。

### 6.3 已归档但不在 S2 宣布的技术结论

| 历史中出现的提案 | 现有证据可得出的结论 | 为什么此时不能锁定 |
|---|---|---|
| “唯一 ConfirmedCreativeSpec” | 冻结上下文在不同消费者间必须完整、正确传递 | 没证明一定需要此名称或一个大 JSON |
| Beat/Scene/Shot 类型 | 业务镜头身份不应由 Markdown 物理行替代 | 具体 Schema/颗粒度须由新需求与现有底座决定 |
| ModelGateway + Context Manager | 专用语义请求的上下文隔离与结果捕获有已证实缺陷和价值 | 没证明必须新服务/新 Agent/分层框架，也未真实对照工具可靠性 |
| 单一 Production Kernel | 外部副作用身份、预算和重派授权需要可解释一致性 | 不是要求合并所有 Creation/Attempt/Provider 状态，存储/事务方案未定 |
| 导演可适配候选素材 | 用户授权、导演实现与素材事实需清晰分离 | 是否需要重新 Planning/局部变更版本、由谁选择要对照本次需求 |
| “删全部 Gate、宽松 Schema 就能出片” | 历史没有支持证据；相反一些拒绝保护了真实事实/权益 | 追求模型 PASS 不能取消业务安全义务 |
| “模型换成通用 Codex 就会解决 V1” | 独立模型/工具能力与通用 Agent 输入串扰都值得评估 | 没有同题、同合同、同完整链的对照数据证明哪种方案可用 |

**S2 结束后的状态是“历史可追溯”，不是“保留/废弃决策完成”。** S3 应进一步抽象通用经验、历史需求含义、适用条件和反例；S4 再由用户确认本次产品范围；S5 才有权选择保留原则、复用当前官方实现、改造、重写、淘汰或延期。

## 7. 已完成的覆盖检查、遗留证据问题及 S3 交接

### 7.1 历史覆盖矩阵

| 领域 | S2 状态 | 主要证据 |
|---|---|---|
| 原始目标、范围、创作责任与历史确认 | COVERED | `00_PROJECT.md`、`CREATIVE_MODES.md`、视频架构、ADR-001/004、10/11 A/B/C |
| 需求版本/重大决定与 Git 演进 | COVERED | 130 个第一父提交、131 个专属提交、17 个 HREQ 历史条目、主要 Task/ADR |
| 端到端产品链路与成功资产 | COVERED | 9/29 外部 Material、9/30 12s/36s Creator、10/05–06 素材、10/12 U3-S |
| 独立真实失败、合法拒绝与未执行模块 | COVERED | 10/06 三轮 Material E2E、10/08 Dev Eval、10/15–16 Planning R 系列 |
| 模型/输入/Schema/工具/恢复/预算深入归因 | COVERED WITH OPEN HYPOTHESES | 历史 Planning `8.36–8.40、22 项旧清单与 7 项已验证原件 |
| 音频、权益、供应与 Creator 实际质量 | COVERED WITH LIMITS | v0.5 恢复、BGM 64 样本校准、旧 9/9 单作品、9/30 人工审片 |
| 整体工程流程/复杂度演变与不必要路径 | COVERED AS HISTORICAL FACTS | Git 历史、10/10 ADR-005、10/11 U0–U6、10/14 U7 讨论 |
| 全量原始媒体/每一私有请求内容逐份审计 | NOT DONE / NOT REQUIRED FOR THIS EVIDENCE-BOUNDED S2 | 215,318 文件索引、7 份哈希抽核；其余按具名问题使用历史验收 |

### 7.2 不应通过臆测填充的证据缺口

1. 历史原始讨论中部分要求的首次口头确认和需求变更原因，不一定都保存在本次可见 Git 文档；文档里的“用户批准”只证明有此记载，不能为无记录的字段补出处。
2. R14–R19 有 7/7 原始审计快照哈希核验，但没有重新逐字节审阅所有 Tool 请求、每一轮推理及 8.36 GiB 全量素材。对于复杂因果保留历史原件定位。
3. 零工具响应到底由 MiniMax 模型、OpenClaw 适配、系统提示污染或多因素造成，缺少独立受控对照。不能因后期离线修补了某一支路就推为完整生产修复。
4. 9/30 创作样本与 10/12 U3-S 是不同版本、不同边界，不能合并为“同版自主 Web E2E 成功”；用户要求的跨主题风格一致性无充分真实抽样。
5. V1 没有在同一正式新生产版本完成全部四音轨和 900 秒资格；不能提前给本次 V2 判定必须优先做或必须放弃。
6. 外部 Provider 权益、现金结算、全部 BGM 版权/署名与历史真实发布时间等仍受各次原本许可和记录限制；不得据 Token 或授权上限反推现金=0。
7. 旧源码中存在的不同状态/模块是否都导致生产竞态，需要区分“多域合法状态”与“共享操作 Owner 权威冲突”；只能在具名症状与原件下形成有边界归因。

### 7.3 S3 的唯一合法输入（尚未执行 S3）

- **HREQ-01～17** 的来源、历史确认层级和演进事实，用于后续提炼真正业务意图；**不自动录入 V2 正式 `01_REQUIREMENTS.md`**。
- **C01～C09** 的机制、正反证据、修复收益和未决因果，用于后续形成工程经验与适用条件；不把 `ModelGateway`/`Production Kernel` 当既定方案。
- **22 项问题对应表**，保留原旧编号供追溯，重新区分“真正代码缺陷 / 有效果的修复 / 业务合法阻断 / 集成未验收 / 架构风险”。
- **历史成功清单**与真实授权、Rights、用户自主性结果，在 S4 与新用户需求/当前 V2 源码事实汇编时作为事实参照。
- **尚需用户决定的问题**：当次视频/音轨/时长范围、稳定风格的可观察标准、Creator 中途权限、作品修改范围、素材与模型使用策略、预算/发布边界、非功能约束和实际体验验收。

**S2 完成判定**：历史项目目标与需求演进已覆盖；主要正反作品到达位置已还原；22 项旧问题有独立归因类别与证据边界；核心因果关系和竞争解释已写明；S3/S4/S5 均未被提前宣布完成。后续若发现新历史证据，可修订对应事实并保留版本差异，不需要续跑或修复 V1。

## 8. 核心证据路由与复核方法

所有历史 Git 链接均固定旧 commit，非当前 V2 文件的相对路径；私有原始模型与账本只给本机入口，不提供可公开下载的内容。

| 证据组 | 权威来源 |
|---|---|
| 历史产品/结构 | [00_PROJECT](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/docs/00_PROJECT.md)、[视频架构](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/docs/architecture/easel-video-architecture-v1.md)、[Material V1.3](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/docs/architecture/material-layer-v1.3.md)、[ADR-001](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/docs/decisions/ADR-001-creation-hypit-mainline.md)、[ADR-004](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/docs/decisions/ADR-004-material-layer-v1.3-baseline.md) |
| 运行结果处理/历史迁移 | [ADR-005](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/docs/decisions/ADR-005-agent-result-processing.md)、[New-Only U0–U6](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/docs/architecture/web-backend-new-only-cutover-plan-2026-10-11.md)、[精准退役验收](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/docs/acceptance/adr005-hypit-native-legacy-test-retirement-2026-10-10.md) |
| 真实历史 E2E | [9/29 外部素材](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/docs/acceptance/external-material-product-e2e-2026-09-29.md)、[9/30 Creator 工作区](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/docs/acceptance/creator-workspace-e2e-2026-09-30.md)、[9/30 音画审片](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/docs/acceptance/creator-audio-quality-e2e-2026-09-30.md)、[10/06 独立素材 1](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/docs/acceptance/material-independent-e2e-2026-10-06.md)、[2](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/docs/acceptance/material-independent-e2e-2-2026-10-06.md)、[3](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/docs/acceptance/material-independent-e2e-3-2026-10-06.md) |
| 供应/音频/质量 | [v0.5 材料恢复](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/docs/acceptance/creation-latency-v05-material-resume-2026-10-05.md)、[BGM 校准](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/docs/acceptance/creation-latency-v06-bgm-calibration-2026-10-05.md) |
| Planning 真模型/语义 | [10/08 vNext 真实 Development](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/docs/acceptance/planning-semantic-boundary-vnext-development-2026-10-08.md)、[模型 Carrier 能力审计](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/docs/acceptance/planning-a-structured-carrier-capability-2026-10-08.md)、[B Review 根因记录](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/docs/tasks/planning-b-review-p0-identity-binding-implementation-2026-10-14.md)、[D0–D4、R14～R19 与 `8.39–8.40 归因](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/docs/tasks/planning-creative-authority-implementation-plan-2026-10-15.md)、[唯一真实 E2E 账本](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/docs/acceptance/easel-v1-web-real-e2e-2026-10-10.md) |
| 完整历史私有基线 | `/Users/xgx/Projects/Easel-V1-History/V1_SHORTCOMINGS.md`；`inventory/V1_SHORTCOMINGS.csv`、`v1-docs.json`、`git-commits.tsv`、`final-audit-shas.json`、`archive-verification.json`、`evidence-snapshot-proof.json` 与 `raw-evidence` |
| 当前官方代码/质量事实 | [S1-A PR #1](https://github.com/webxia/Easel/pull/1) 与 [S1-B PR #2](https://github.com/webxia/Easel/pull/2)，均为单独待评审事实，不能和旧 V1 运行版本拼接 |

### 只读复核原则

- Git 历史观察可用 `git log --first-parent --reverse easel-studio`、`git show 57c8e2ad:<path>` 或 `git -C /Users/xgx/Projects/Easel-V1-Archive show HEAD:<path>`；绝不执行旧 Task 的恢复指令。
- 私有快照可按 `inventory/final-audit-shas.json` 的相对路径在 `raw-evidence` 中重新哈希；不回写原账、不泄漏密钥/原始私有内容。
- 每项真正的历史“PASS/FAIL”结论必须回到其原产品、Creation/Attempt、源码/运行指纹和日期。旧目录的“最新 NEXT”不再有指挥权。
## 9. V1 U7：全链路优化研究方向（历史候选，尚未实施）

**固定来源**：[V1 路线图 U7](https://github.com/webxia/Easel/blob/57c8e2ade21af9fb6abccdab3f7ba8e50132314f/docs/03_ROADMAP.md#L28-L46)；其原始状态明确为 `U7_BACKLOG / NOT_STARTED / NO_CODE_CHANGE`。它提出的是 **在 U0–U6 真实出片之后开展的效率、质量、成本、自动化、恢复性研究**，不是已执行的第七个 Gate，更不是已被验证的 V2 技术方案。

### 9.1 六类值得保留的历史优化问题

| 历史研究领域 | U7 曾提出的优化问题 | 本轮证据结论 |
|---|---|---|
| Creator / Director / Web Proposal | 交互轮次、重复确认、冻结信息、人工打断、跨题材风格 | 属体验观察计划；与 C01/C03/C08 关联，未测得全链优化结果 |
| Preparation / Planning / Truth | 重复上下文、分阶段合法性、Token、推理档位、模型路由、恢复 | C04/C05 有具名失败证据；U7 自身 **NOT_STARTED** |
| Material / Voice / BGM / Rights | 多 Need 复用、重复观察/供应、音频、版权事实、缓存失效 | C07 有正反例；U7 未形成整体基准或优化增益 |
| Native Authoring / Hypit | 选材交接、编排/Build 耗时、资源峰值、重复 Build、费用与 UNKNOWN | U3-S 仅软件集成证据；真实 Web 阶段耗时未由 U7 量测 |
| QC / Review / Content Library | 音画字幕/风格、局部修订、用户反馈次数、可恢复输出 | 9/30 单作品有人审成功；非 U7 优化实验 |
| 跨阶段量化 | p50/p95、总耗时、Provider HTTP、推理与输出 Token、费用、失败/恢复率、用户干预 | **研究方法候选**；需要多作品、同版样本，不能从同题 R09–R19 得出总体统计 |

### 9.2 Planning 推理强度和重复输入：假设不能误当结论

U7 原文认为当时 OpenClaw 的统一推理强度、B 与 A-details 重复携带大量冻结证据，并使用较高 `reasoning_effort`，**可能**增加延迟与消耗。它列出的 A-selection `medium`、A-details `low/medium`、B `medium`、Repair `low`、Truth `medium` 均为 **HYPOTHESIS / NOT_TESTED_BY_U7**；并无证据证明改用这些档位就会降低 UNKNOWN、解决零工具或通过真实 Planning。

U7 的可吸收方法是：固定输入、Git/Runtime/Schema、模型通道和输出上限，使用新的有效测试身份对照推理参数；单独控制思考档位与输出 Token 上限，记录阶段响应、语义合法性、端到端完成率、耗时与实际资源消耗。历史 `PENDING/UNKNOWN` 不得因为试验而重派，Creator/Director/Truth/来源/Rights 的语义义务不能为了缩短上下文而删减。

### 9.3 S2 能沉淀什么、留给后续什么

- **历史事实**：U7 曾要求对整个 Creator 视频制作链而非单点 Planning 做瓶颈诊断；当时没有启动 U7，也没有生成 p50/p95 性能报告或真实完整优化结论。
- **经验候选**：先建立真实作品和跨阶段计量，按影响排序选一个瓶颈，做有界对照；不要平均用力重构。区分阶段 Provider HTTP、Agent/RPC、Token、套餐占额、真实现金、重试、轮询与人为干预，不能相互替代。
- **已知正反证据的连接**：重复输入曾造成本地 Repair 超限，后续可逆去重让 R14 真实 Repair 派发；但这不证明按阶段降低推理强度会提高模型合法性或整体出片率。
- **后续责任**：S3 可提炼上述研究习惯与适用条件；S4 决定本次 V2 真正需要考核的质量/成本/效率指标；S5 再比较实现与可观测性方案。**不能从 U7 Backlog 直接生成 V2 开发 Task 或宣称优化已实现。**
