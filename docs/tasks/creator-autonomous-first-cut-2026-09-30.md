# Easel V1 自主首版与 Director 全链执行：唯一实施 Task

状态：2026-10-02 本轮最小范围 **SOFTWARE_ACCEPTED / READY_FOR_HUMAN_E2E**。本文保留唯一实施范围、责任与验收条件；不将软件回放等同真实自主交付或跨内容风格验收。历史方案与授权通过 Git 追溯，完成证据唯一汇总在 [Current State](../02_CURRENT_STATE.md)。

## 当前目标与已有基础

### ADR-005 软件实施（2026-10-09 用户授权，本轮软件验收完成）

**2026-10-10 用户明确决策：**后续新建 Attempt 默认启用 ADR-005 五个新版结果协议（Truth source-ref、Material delta、Markdown ledger@3、Quality delta、Hypit native source）；旧 Attempt 和显式旧 pin 继续冻结旧协议。过渡的 Hypit SVRun-only Writer 不进入默认链，也不允许双 Writer 并行。已确认相关定向 25 PASS、native Authoring/旧 journal 组合41 PASS；真实新作品成片前**不删除旧实现**，不将此配置切换当作已经生产启用或媒体 Build 验收。最新状态见 Current State。


本轮按 `AGENTS.md` 在最新 dirty checkout 上实施 [ADR-005](../decisions/ADR-005-agent-result-processing.md)，归入本 Task 的 O4/O5。Main 修改和整合，Scout 只读调查，跨合同方案和阶段收口由独立 Astra Reviewer 复核。下表只认领显式 profile 软件范围；证据汇总见 [Current State](../02_CURRENT_STATE.md)，准确命令、Job、46 文件摘要和最终审查见[具名验收记录](../acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/adr005-result-processing-software-2026-10-09.json)。

| 单元 | 实施范围与依赖 | 验收与状态 |
|---|---|---|
| U0 基线 | 最新源码、实际安装包、旧协议与既有失败；按事实修订 ADR | 已完成；保留 A-details 诊断改动与历史根因 UNKNOWN，不扩大真实调用预算 |
| U1 结果接收 | 复用 admission/receipts；分开结果拒绝、本地完整性错误及可重建派生 | 软件验收完成；原请求、原件、完整派生、存储失败恢复和旧规则保留 |
| U2a Truth 来源引用 | 独立/联合 producer → 来源 handle → 完整报告 → persist/load/fork/cold | 软件验收完成；新旧 ledger、voice review 和两代 fork 有实际 Owner 验证。B SourceUnit/candidate correction 未迁移 |
| U2b Material 增量 | 派发前固定 logical group facts/checks 或 delta；请求/资格/争议/assembly/apply/cold | 软件验收完成；共享事实、负面结果、成功批次后中断、嵌套父证据实际 fork、异议撤销和独立候选均有验证 |
| U2c Quality 增量 | 只补未决 delta；原件/正式报告分存，程序合并且不覆盖已决 | 软件验收完成；实际 MP4/多轮 Owner、saved/pending/Delivery/Director、observed=False/异议和 native Authoring→Quality 均有验证 |
| U3 Hypit/文件交接 | 实际 Hypit 0.2.7 语法/typed 图；原 Authoring Owner 隔离候选、intent、CAS 与恢复 | 软件验收完成；实际本地 static check、冷进程、managed stage 零新增 Agent、真实 fork、外来 writer、最终 CAS、CLI 本地错误分流已验证。两 Hypit Writer 互斥 |
| U4 Markdown/ledger | 固定 markdown-it-py 4.0.0 与 ledger@3；原字节/coverage/Truth/Planning 冷重建 | 软件验收完成；中文/混合 Markdown、CRLF/CR/LF、引用/代码/表格保守覆盖、operator revision/hash、两代 fork 均已验证，旧 @2 保留 |
| 收口 | 受影响实际内部集成、受测快照、独立审查、文档与交接 | 最终 Astra **DECISION=CONTINUE**；两处构造保护落盘后原生子集通过，46 个具名文件在回归前后一致。其他窗口早先未取得 Reviewer 的记录为历史 |

**本轮验证边界：** 实际内部 Owner/stores、纯原生 parser、本地静态 check 和媒体测量已执行，外部模型/Provider/Build 使用确定性替身。各组有重叠，不把测试数相加为功能数。工作树仍未提交，受测摘要不等于 release；无真实模型/Provider/Hypit Build/真实 E2E、服务重启/部署或 Git commit/push。封存 HTTP 池和历史 FAIL/UNKNOWN 保持。

**后续独立工作：** `DEFAULT_PROFILES = {}`，新协议显式 pin，历史 Attempt 原版本恢复。默认 rollout 前另做交叉验收和切换；五 profile 同一默认链、B SourceUnit/candidate correction 及真实模型视频验收不在本轮完成声明内，也不增加为首片前置。

**最新代码对方案的修正：** Material 现有 facts key 已含完整 frame（index、seek、JPEG SHA）；真正缺口是 policy/contract/route/资格，以及恢复时动态 prior 导致请求 identity 漂移。Quality resolved_frames 包含 observed=False，必须冻结。Truth 需覆盖联合 producer、material_recovery 与 voice review identity。Hypit 原生 structured parser 与完整 raw frontend 明确分开；发表 journal 应放在现有 fingerprint 排除的 `.easel`，并由阶段 identity 绑定。

**U2b 实施校正：** facts scope 改为独立、固定的可见事实子合同摘要（字段/上限、事实 prompt revision、visual contract revision）加完整采样/附件及派发前 route 核验，允许不同 Need 复用同份实际画面事实；每组 request/derivation/qualification 仍固定自己的完整 Need 合同。事实字段不承载 Need 偏好或动态动作判定；合法异议撤销所有实际引用该 fact ref 的 Need×Asset 系统资格。Creator 内容确认保留，但失效系统 LOGO/TEXT/视频区间不会进入 Matcher；原始报告、Asset 与 Bundle revision 不改。不同 Creation/Handoff、协议或未授权祖先的嵌套事实/异议仍是本地完整性错误。Quality 的 Build 后 receipts 也必须放 `.easel`，避免审片保存本身改变已提交工程 fingerprint。

### 连续自主出片 Goal（2026-10-08 用户追加授权，进行中）

#### 本窗口收窄执行：离线诊断修补已验证，历史精确根因仍未知（2026-10-09，已停止）

沿原 Session `wc_sess_TVqbfxf7Z6k74Oz_`、原唯一 Task 续接 `wc_msg_UVtrp6bJO-z26lNi`；没有新建 Goal、开发 Session、Task、工作树或生产链。用户本轮仅授权“精确根因离线复现与最小修复 + 受影响集成测试”，不授权工程首片、三主题验收或新真实模型请求。O1/O2、自动配额移除及三项机械约束简化保持既有实施。

本轮结论是 **DIAGNOSTICS_VERIFIED_HISTORICAL_ROOT_CAUSE_UNKNOWN**。已完成诊断能力的最小修补和受影响验证；历史故障精确复现及对应修复未完成，因此本轮原定精确根因阶段不标完成，连续自主出片 Goal 仍进行中。当前停止原因是已检查的持久化证据缺少历史 A-details 参数原文及具体 SDK/Runtime 错误，而非本窗口再次遭到平台访问拒绝。

原 Job `wc_job_a4moxdKR6BxULVLY` 已 failed/exit2、第二批首例 FAIL/实际 HTTP2。原 A-details run `easel-4583ce810be04841b33b0709cc3ac7b7` 已 error/released；Creation `cr_974075895e364878b9be34d0479ecd9d` / Attempt `fa_4eec26c13c336dd79518d330204b4759`。原参数传输19653字节、HTTP200/RESPONSE_COMPLETE/tool_calls 已核对，但候选未捕获，CAPTURE_PENDING 只是持久化标签。由原 journal 重建 input view、selection admission、details/wire 绑定及实际 HTTP Schema 全部一致（Schema SHA `40d9caadca47a85ef32f425d5ebeee00e27b1e9bc78ba7b5765bdf8246a83411`）；这不等于已还原原回复或证实 JSON/SDK/语义通过。原日志、SDK transcript/trajectory、guard 与 capture 通道未提供可恢复的原文及具体异常，历史根因仍 UNKNOWN，B/repair/Truth/Supply未进入、语义 NOT_REVIEWED、无视频。

修补仅涉及 helper 的首个 error/aborted 诊断保留、Runtime 兼容脚本在 SDK 清理前保留受限类别/形状，以及匹配的新 helper/transport 身份 pin；复用 `rejection@1`、身份绑定、RESERVED 和重复提交保护。未知字段、异常及语义失败没有被忽略或改成 PASS，原候选不改、repair 不扩大。兼容补丁只在新离线副本 `/tmp/easel-structured-runtime-offline-rootcause-20261009T132535Z` 应用；原 Runtime 未改、服务未重启。新源码 pin 对旧 Runtime fail closed，未认领在线加载完成。

| 验证 | 实际 Job 与终态 | 结论范围 |
|---|---|---|
| 未修版本的两项诊断对照 | `wc_job_Wt1le4C-KRrn1uYz`，exit1，2 FAIL，7.89秒 | 首个诊断缺失可确定性重现；原生 SDK missing-finish 对照不是历史 tool_calls 故障原件 |
| 修补后受影响集成组合 | `wc_job_wPmg85ctH0otMP6I`，exit0，29 PASS/0 FAIL/0 skip，80.39秒 | 实际内部 Gateway/transport/SDK/helper/reader 拒绝链及正常 Owner/Planning/Truth/persist/load；外部边界共6次本地替身 HTTP，无真实 Provider 调用 |

相关源码/测试14文件的测试前后摘要 `f995591c70a5560c1460274c18e472a251b2421d35c93537a9e4c41f136d6b7a` 一致；branch `easel-studio` / HEAD `d5bd227c2b6750ae18cea06ebcf4f9f89350899b`，本轮修改未提交。原失败证据17文件及原 Runtime 11个固定文件字节保持；只读 SQLite 访问新增空 agent WAL/SHM 协调文件，原 DB/已有 WAL 未变。测试覆盖相关成功/拒绝、首件保留、身份与旧格式、重复提交、敏感文本排除和保存失败；未机械重跑全量，不冒称真实模型稳定性或视频 E2E 通过。

原证据根目录仍为 `/Users/xgx/Library/Application Support/Easel/acceptance/autonomous-first-cut-2026-10-08/output-admission-continuation-80http-v1/batch-02-engineering`；本轮私有证据在同 acceptance 根下 `offline-root-cause-20261009T132535Z`。 [具名验证记录](../acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-sdk-error-diagnostics-offline-2026-10-09.json)保存精确命令、Job、逐文件摘要、原件核验和停止边界；结果同步到 Current State 和原 Session 检查点。

父池 actual_http=3（首批1、第二批2）、remaining_batches=0、closed=true、dispatch_blocked=true、BATCH_SLOTS_EXHAUSTED 已核实且不修改；80HTTP未用满不产生第三批授权。账单 UNKNOWN 不记零，旧¥30媒体上限不是本轮授权。本轮新增真实模型、主动配额、媒体、TTS、Authoring、Build均0；无部署、重启、commit、push或发布。已停止，不恢复旧失败作品，不启动工程首片或三个主题稳定性验收；下方 O1/O2 及后续序列保留为原历史授权和实施记录，本窗口不继续执行。

#### 流程审计优化 v1：先工程首片，再稳定性验收（2026-10-09，用户批准方案与执行）

授权依据：用户在流程审计后要求“根据这次审计 创建优化方案，然后进行执行”。沿原唯一Task与Creation→Planning/Truth→Material/Rights/Readiness→Authoring→本地Hypit→Quality主链，不新增生产模式。基线HEAD `d5bd227c`、生产source `90ab1935`。已完成的quota移除、intake@6查询条数、visual@2结果重排/空备注不重复实施。

| 单元 | 改动与验收 | 顺序 |
|---|---|---|
| O1 网络故障可解释、可恢复 | 在隔离文字评测代理增加版本化、无正文/凭证的连接/TLS/请求发送/响应/本地交付/账本保存证据。仅已证明业务请求未开始发送且属暂时连接故障，允许同逻辑请求最多一次重试；每个尝试重新占用原HTTP总池、重新核原授权与时间，不退款、不增加模型repair。证书、认证、额度不足不自动重试。发送开始后的故障保持UNKNOWN；完整响应后的本地失败不得误报未完成上游。真实HTTP边界和外部替身集成覆盖这些分支。旧协议不自动启用。 | 当前先做 |
| O2 工程首片与资格批分离 | 工程首片只要求该新作品自身的完整Planning/独立语义、Truth、Rights、Readiness、Build、输出绑定Quality成立，不再把另外五个主题重复样本或正式R4整批通过当作首片前置。先取得可审阅输出并保留实际缺陷；工程介入逐项记录，绝不认领零介入/稳定PASS。原6例资格与同版3主题连续自主验收仍保留独立身份和评分，未执行就是未执行。执行器只复用原Planning边界支持单样本工程检查，不把隔离假媒体凭证载体直接当生产作品。 | O1后 |
| O3 已审查报价证据复用 | 仅在素材阶段实际被公开文档读取阻塞时，增加型号/区域/规格/协议版本/有效期绑定的已审查快照；过期/缺失/冲突仍停，预算和Rights不删。不现场每张素材重复抓完整文档。 | 按实际阻塞 |
| O4 消除机械回抄 | Preparation固定主题/规格、Truth/SVRun身份、Material同帧事实、Quality已决结果优先交程序生成/合并；不改变创作语义和已确认合同。按发生阻塞的阶段逐项实施和复核，不同时改四层。 | 非首片总前置 |
| O5 后置优化与稳定验证 | B答复修复和A语义修复的分配、来源片段引用、检索语言、方案外壳、ASR局部歧义、Quality严重度暂列backlog；不自动增加一次共享repair，不把软偏好当硬错，也不以相似度/忽略字段伪造通过。首片之后按同一固定版本验证3个新主题零工程介入。 | 首片后或明确blocker |

O1实现边界：只从当前连接实例的实际调用顺序证明未发送；不能仅根据TimeoutError类、0回复字节或后来一次TLS错误推断旧POST未发送。HTTPS CONNECT代理协商不算模型业务POST；证据不能取得时保守UNKNOWN。传输诊断只保存枚举阶段、白名单异常类别、整数errno、调用/响应计数及摘要，不保存异常原文、URL认证、请求头或内容。连接重试只在新manifest显式绑定策略后启用，正式输出结构/语义仍按原规则。预算耗尽、未知或本地持久化失败时没有自动重发路径。

O2预算：继承`output-admission-continuation-80http-v1`，原第一批FAIL与占额不改；本授权不增加两个批次/80HTTP/5400秒的总池，不回收已封存批剩余份额。剩余一个40HTTP/2700秒槽可用于具名工程Planning检查，而不是宣称完成6/6资格。完整生产仍使用原媒体累计¥30与文字授权，禁止余额/现金/积分购买/付费回退，不自动发布。

历史UNKNOWN不能按新诊断倒算。只有核实原请求是隔离的纯候选提交、无采购/文件修改工具、原Gateway run已终态释放且无可恢复结果时，才可另记“放弃结果恢复、保留未知账单和原占额”的受限工程续接决定；原账本/FAIL保持封存，新的独立身份占用剩余槽，不重发或改写旧run。无法证实上述边界，仍停止相关真实派发，不妨碍离线优化。

前置窄复核：Owner在原契约内执行；本轮独立MCP Reviewer目录为空，未取得Astra独立意见，不冒称通过。不改Provider API/Runtime版本/TLS验证/生产服务配置；不推送、不发布。重要范围变化或安全/预算边界不足时保存检查点并停止相关执行。验收按已证明风险列证据，不按测试数量认领成片。

#### 本地提交与服务重启（2026-10-09，用户明确授权）

已提交103个选定文件，代码commit `82b66519fa12379d4ef7d2fd477c58f57d67eddf`，生产SHA90ab1935/223文件保持原软件验收身份；批量历史运行输出不入本次提交、不删除。前端构建通过。原LaunchAgent重启Web/Gateway后PID22399/22325、HTTP200/Gateway live；初次bootstrap exit5保留，观察已卸载后同入口恢复成功。日志/原始流已受保护归档，旧Creation和封存账本不变。此授权只含本地commit及重启，不扩展真实批次、模型/Runtime升级、push或发布；UPSTREAM_UNKNOWN仍待另行对账。证据见Current State及 `autonomous-commit-restart-2026-10-09.json`，无需再提交已完成源码或再次重启。

#### 三项机械约束简化实施（2026-10-09，用户批准）

**实施收尾：SOFTWARE_VALIDATED。** 断线后先确认六文件仍为原partial，未重复撤回；已完成上述producer至consumer的版本传递、缓存和冷恢复。最终相关回归168PASS/0FAIL/0skip（Job `wc_job_rau70u9oykDBj0vX`，822.24秒），原生生命周期1PASS/38.27秒（Job `wc_job_ktVJZcoiSk3o457P`，5次本地替身HTTP）。新0/1/2/3条完整Planning/Truth/冷verify、旧intake5共享repair/冷verify、同ID乱序/空备注、缺项重复错帧错误类型篡改拒绝和真实旧fixture消费者均在覆盖内。原件保留，规范结果按版本重算，不将not_met/unknown改为met。当前source `90ab1935538ab3044c61ae1889392cfc42ae39ebfd26d3a78dc03ea1b1fb0272`/223文件，工作树未提交；302保护/142fixture/5封存账本一致。[具名验收](../acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-advisory-validation-2026-10-09.json)。此前53/20测试有重叠不累计，外部模型均fixture，不认领真实Planning或MP4。无新增真实派发/配额查询/媒体/Build/部署/commit/push/publish，独立Reviewer不可用；原UNKNOWN和剩余预算保持，本单元已完成无需再实施。

用户明确选择：检索提示不强制凑数、带ID审核结果程序重排、偏好备注允许为空。本轮仅实现这三项和必要producer/consumer、恢复、回归；不启动真实模型/媒体/Build或解除既有UNKNOWN，不新建Goal、不部署推送发布。

Owner前置窄复核：CONTINUE；独立MCP Reviewer目录仍为空，未取得独立Astra意见。新intake@6的视觉queries允许0～3条，保留短语类型/长度/英文/唯一性和模态边界，不凑词、删词、截词、自动翻译。使用已有检索字段无损传递1/2条，3条旧包装仍合法，检索提示不变成硬条件。新plan显式绑定visual-requirements@2；旧intake/plan与缓存保持原规则。

新视觉审核合同按同帧完整唯一整数ID集合重排classification/checks；缺失、重复、未知、错误类型/错帧仍拒绝，原始响应保留，重建规范结果不改status/basis，不重排分镜、Need或原文时序。preference_notes允许空字符串（仍需字段且为字符串），不伪造偏好满足；description/style及必要项实际依据保持原校验。规范化/空备注不授予Rights/READY。新输入、缓存、报告记录和冷加载必须使用同一版本并验证原件与规范结果。优先复用既有Planning→Truth、Material校验/重载及恢复场景；变更不把软件通过当真实出片。

#### 移除自动配额查询与非必要校验盘点（2026-10-09，用户追加）

用户要求“把这个去掉吧”，并追加“检查还有哪些非必要校验”。自动配额操作已移除：`planning_eval_run.py`原quota_check改为check_authorized_route，去除网络请求、读取失败与25%阈值阻断，保留本地已授权模型/route/无fallback/credential_fingerprint检查。原指纹文件沿用但不要求新配额快照；未知余额/账单不记零。本次不授权重开封存批、增加预算或重派UNKNOWN；以后默认不自动进行quota预检或收尾查询。无部署/提交/推送/发布。

验证：真实内部runner在quota未知或历史余额0时可完成隔离Planning/Truth边界，urlopen替身禁止一切配额请求；凭证/route/缺key/fallback变化仍拒绝；原始请求观察无新准入/派发，HTTP上限与UNKNOWN/时间边界保留。15PASS（Job wc_job_lX7GgRTtpYIq9O2S/6.18秒）+开发边界4PASS/0.44秒，范围不重叠，非全量回归。原生产e5cb1c59/223文件未改，本次只有执行器和两个相关测试文件变更。

非必要校验定向盘点（仅方案，不等于这些项已放宽）：

| 优先级 | 当前机械约束与证据 | 建议与保留边界 |
|---|---|---|
| 优先 | Planning queries只接受0或3条且ASCII；Material visual_contract/query_hints重复限制。离线0/3接受、1/2拒绝。 | 允许数量按需、去重提示；英文要求归具体检索Provider适配。先证明完整业务约束不只藏在提示里，保留原提示/检索预算/匹配；不能仅删除字段或只改上游。 |
| 优先 | visual_contract.validate_result要求checks ID列表与输入次序完全相同；反序但内容不变被拒绝。 | 校验同帧完整集合、唯一性、ID与类型后按程序顺序规范化。缺项/重复/错帧/未知ID不放行；不重排分镜/Need或有创作时序的数组。 |
| 优先 | preference_notes必须非空，空字符串使整份Material观察失败；现有verdict计算不使用该字段。 | 允许无备注，不伪造“已满足偏好”；已存在的偏好要求与观测记录保留，实际视觉/必要项/授权仍核验。 |
| 后续窄设计 | assemble_report将同帧各分组description/style字符串不相同直接视为事实冲突。 | 全帧共性观察只产生一次/程序引用，组内只答各自要求；不能选择第一条掩盖真实矛盾，不引入通用清洗或为此现在重做Material。 |
| 后续窄设计 | Support.quote字符上限512，513即拒绝；此上限参与48问题/16来源总容量证明。 | 不把512当语义真伪，但不能简单删上限或裁引文。评估程序绑定来源片段/引用锚点替代模型重复抄写；保留来源有效性、语义支持、完整性与总字节上限。 |

已收敛的不重复治理：contains精确回显及完整围栏已有admission；Readiness已只以required Need形成阻塞，optional素材缺失不要求补成required。重复键、损坏JSON、缺必要义务、wrong modality/来源、Rights、冻结正文/身份、账本、不可对账副作用、真实输出Quality仍是硬边界；不以“校验严格”整体删除。后续先做前三项小范围方案复核与兼容测试，其余不追加为出片前置条件。本轮所有盘点为当前代码+合成离线反例，不是历史失败率或真实成片收益估计。

私有证据：`Library/Application Support/Easel/acceptance/autonomous-first-cut-2026-10-08/remove-automatic-quota-20261009T082246Z`，两份JUnit、修改前文件与nonessential-validation-audit.json；没有改历史原件/评分。本Task其余历史“实时quota必须”表述在后续新执行上由本次用户决策取代，不能据此改写旧协议/旧报告。

#### 新授权首批收尾：上游响应UNKNOWN停止（2026-10-09）

本轮已沿批准顺序完成第一单元原生、第二单元消费者软件及验证，随后分配新池首批并真实运行；不是停在实施方案。六载体首例Job `wc_job_fyWdm7hui8zUqGV3` FAIL/1HTTP/71.890秒，后五例不提交。manifest015cf7d6，source e5cb1c59；原run已error/released，但Provider正文0字节、finish缺失、HTTP账本UNKNOWN；本地proxy产生502，具体上游异常未留存。后续配额GET TLS握手超时，不能将余额或账单当0。首批与原件封存，父池保留第二批授权但停止派发，不能用剩余额度绕过未对账原请求。[具名结果](../acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-output-admission-qualification-batch01-2026-10-09.json)。本批未进入候选规范化/B/Truth，不能归类为新语义失败。没有新媒体、Build、部署、commit/push/publish，正式视频0/3。既有普通研发授权保留；当前要求是对账/网络边界，不重新实施第二单元或清洗空结果。

#### 第二单元软件收尾（2026-10-09）

现有Material/Truth消费者已接统一policy/凭据，具体范围及当前证据见[第二单元收尾](../acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-output-consumers-2026-10-09.json)。当前source e5cb1c59/223文件；49项当前组合PASS，原生1PASS/5本地HTTP，冷恢复/策略丢失/原件与候选篡改/合法拒绝/旧缓存与旧执行覆盖。之前76项广泛运行非最终源码，不合并计数；旧失败记录保留。请求实际会话追加确定性policy摘要，仅用于新的执行，旧pending不换会话。Receipt完整性/存储错误停止本地恢复，不要求模型重写；受保护文件与fixture保持。软件通过不等于真实Planning成功；新增两批授权已写入私有具名authorization，尚未开始真实提交，下一步实时预检与按整批40HTTP/2700秒上界预占新池（不回收失败批剩余额度），达到资格后按原主链推进。

#### 统一接收续接：原生补验与第二单元实施（2026-10-09，用户明确授权）

本轮用户明确续接原Goal，并新增最多两个独立Planning资格批：每批原3主题各2次、最多40实际文字HTTP/2700秒；两批合计80HTTP/5400秒，所有诊断/框架重试/A/B/repair/Truth及独立语义核对入同一新池，跨回合不刷新。新池具名为`output-admission-continuation-80http-v1`，旧批/旧池继续封存；媒体原累计¥30含占额/未结清不变，不允许现金/余额/积分购买/付费回退。不额外取得部署、推送或发布权限。

第一单元原生补验已实际完成：Job `wc_job_iXNoGXBamw2SCsKX`，1 PASS/35.39秒，新输出位于原implementation目录`native-resume-20261009`。只经原run_process正常入口执行；本次调用获准，不是改入口绕过。222源码/2测试及302保护/142fixture预检匹配，原生回复均本地替身，未产生真实模型调用。不再重做intake@5或旧67项。

第二单元Owner前置窄复核=CONTINUE；独立MCP Reviewer目录仍为空，不冒称独立批准。实施仅在既有Material compact与Truth文件读取点接入stage-output-receipts@1：每个原逻辑请求在派发前冻结接收policy/输入/会话绑定，已存在旧缓存或旧会话执行按旧规则，不换请求重派；新结果复用原Delivery终态/身份验证后才保存安全raw、候选和确定性接收凭据。Material只沿用完整json围栏规则；Truth保持strict JSON及既有先验证后排除冗余审阅规则，不用语法整理改变CONFLICT/UNRESOLVED。已捕获结果的本地保存失败只重建，不产生新请求。规范化/解析通过不是领域准入，实际Material/Truth/Quality的原校验仍全部执行。凭据、请求参数或原件不匹配拒绝而非回退；queries回退/模型/Runtime/下游语义不改。先完成关联成功、拒绝、旧缓存、旧执行、持久化恢复及篡改测试，再固定实际源码与新池执行资格。

#### 统一接收第一单元：已实现并通过相关软件回归，原生验证受阻（2026-10-09）

`intake@5`/`model-output-admission@1`已接共享接收接口、A-selection精准contains回显规则、独立raw/normalized、凭据在details前持久化、details双重绑定及冷verify；保留@4及以前的消息和恢复规则。正式BGM/来源/语义准入、512引文上限和共享一次repair不变。合法冗余使用NORMALIZE、不发模型请求；未知extra/限制/冲突/缺字段/非法引用仍拒绝或走既有有界修复。完整文本围栏/strict profile已登记和验证，Material/Truth生产消费者的第二单元迁移尚未实施；queries回退未启用。

最终具名组合Job `wc_job_8RjVLzueHKjdljuS`：67 PASS/0 FAIL/0 skip，pytest 271.64秒；真实内部确认/Preparation/Planning/B/repair/Truth/load、正常化/冷恢复/篡改/旧协议及相关Material/fork/Rights路径。外部模型均替身，不能认领真实成功率。两轮测试22PASS/2FAIL、46PASS/1FAIL原JUnit保留；修正的是中断测试继续方式，未削弱Owner未知执行保护。原2071字节contains原件离线规范化后原Schema通过、7details槽位可构造，原@4请求逐字匹配；不回写旧批或计为正式成功。

当前source `8f4743d0afdc5c22ad73c29157a7ca71f4d60fe6c389c66e1fb5407f4e73d0f4`/222生产文件，HEAD df0d3a30/dirty，最终源码和测试围栏一致；302保护/142fixture与封存账本未变。原生Gateway测试调用被平台安全检查拦截，无Job/无结果，未改路或重试；相关测试函数已写但不声称执行。独立Reviewer仍不可用。状态`FIRST_UNIT_SOFTWARE_VALIDATED_NATIVE_VALIDATION_BLOCKED`，不是整项目发布或完整Planning资格。[具名实施证据](../acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-output-admission-implementation-2026-10-09.json)。本轮新增真实模型/媒体/Build0、未部署/提交/推送/发布、视频0/3；下一入口是当前单元原生验证缺口，不重新实施或跳过原有真实资格门槛。

#### 统一接收方案实施（2026-10-09，用户批准）

用户明确要求“按照方案进行实现”。本轮先闭合第一交付单元：共享的确定性接收接口、A-selection精确contains回显规则、原件与规范化凭据、details绑定及恢复/verify；同时登记完整JSON围栏/严格JSON渠道的政策供第二单元复用，不擅自切换旧Material缓存或Truth正式协议。可选queries降级仍未授权启用。全程为软件实现与离线验证，真实批次/媒体/服务预算不新增或重开。

实施前Owner窄复核：CONTINUE。独立MCP Reviewer目录为空，未取得独立Astra意见；不以Owner代称独立批准。主要风险是删除真实限制、原始/规范化身份混用、凭据落盘中断后重复派发以及旧协议漂移。新intake@5显式绑定model-output-admission@1规则目录；仅完全重复的bgm/required回显且外层合法才规范化，其余extra仍拒绝。raw由原Owner完成终态/工具身份与安全捕获，接收凭据通过原capture session/request/SHA引用该唯一执行，不伪造或另建run/tool_call。规范化不能授予状态/预算/素材READY。落盘凭据先于details；恢复从原件重算，正式verify同时检查原件、规范化载荷和动作；@4及更旧仅重放原规则。

#### 模型结果统一接收方案：无损规范化与语义修复分离（2026-10-09，设计草案）

**状态与边界：** 用户要求盘点“一律拒绝但可整理”的问题并统一设计。本轮完成来源审计与设计，未实施生产修改、未启动新真实批；不是放宽正式合同、重开预算或独立Reviewer批准。沿用本唯一Task，不建立另一套Workflow/Agent。最终目标仍是正常Creation至可审阅MP4；先落Planning接收边界，不以全阶段改造阻塞成片。基线source `1dccfb0f1c3a68602a45b4f28240f2eec818e070828a43f6db38d4fa820b630d`，221生产文件，HEAD df0d3a30/dirty。

##### 一、数量与证据

按独立Creation和原始run去重，重点检查9个近期具名资格批首例：8例调用过模型，1例在模型调用前被评测器误拦。按第一阻塞点分为7例输出合同问题、2例实现/评测问题。7例中，**仅1例已证明可无损规范化解除首结构阻塞，另6例不能只靠过滤**。不是全项目缺陷比例、真实成功率或可救回成片数；一份回复可以同时有多个错误。

| 批次 | 原问题与本轮判断 |
|---|---|
| qualification-candidate | 冷导入被误认为实际Supply；0模型调用，工具问题，不是过滤回复。 |
| qualification-cold-v2 | 根部10个额外字段包含声音/查询等内容，且仅一幅视觉候选；不能一律删extra。 |
| qualification-m27-v1 | 重复程序旁白、缺unresolved、多项模态/查询违规，不是纯包装。 |
| qualification-staged-v2 | shape对布尔Schema调用get导致实现异常；候选另有未知引用及声音/未决问题。 |
| qualification-source-view-v1 | 六幅图queries格式/数量错误，同时缺必要BGM；仅处理查询不能使整例通过。 |
| qualification-intake-v1 | 未知scope与程序Voice被列成BGM；不能猜引用或删业务内容。 |
| qualification-intake-v2 | slots为损坏字符串、缺unresolved，另有必要性/未决问题；不支持通用二次JSON解析。 |
| p3-qualification-2026-10-09 | 引文超长、来源/关联错误、零视觉候选和错误覆盖；裁quote不能修复语义。 |
| relational-qualification-2026-10-09 | needs[6].contains精确重复当前数组规则及外层bgm/required；唯一Schema错误。仅内存去除后原Schema通过、可构造7个details槽位，原件/成绩未改；A-details/B/Truth仍未验。 |

另复核旧R4十批具名汇总（12次样本执行，含2次通过及未进入Planning的失败），不并入上表。补充vNext围栏例：剥开完整fenced JSON仍有18条条件超过12、非法scope/continuity、图像时长和8条未决，不能称整例可清洗救回。[审计与证据口径](../acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-output-admission-audit-design-2026-10-09.json)。

##### 二、复用已有能力，不再增加一套结果分类

`easel/output_contract.py:8-33`已有ACCEPT/NORMALIZE/BOUNDED_REPAIR/REJECT，复用。已核实五处局部机制：

1. `visual_contract.py:58-119`：核包装身份后，将visual_requirements列表转canonical map；仅已知音频行从视觉投影排除；有注册路径别名、空值和精确原文引号回绑。末尾从明确soft来源补条款是**程序派生**，不能复制成通用补字段normalize。
2. `planning_wire.py:1-18,58-95`：可逆wire codec，不把字符串null变成JSON null。
3. `planning_input_view.py:39-67`：冻结source映射、已知空continuity由程序解码，不推理补义务。
4. `web/app.py:2913-2947`：Material compact-result剥离完整JSON围栏；不代表Planning工具结果可以回退assistant prose。
5. `script_truth.py:203-237`：额外审阅先验证与确定性结论兼容，再只投影需审阅claim；不覆盖原证据。

Planning A-selection在shape处将额外字段和必填缺失统一拒绝，早于repair；Preparation也用字段集合等值检查。问题是接收政策与审计不统一，不是整个项目完全没有规范化。统一的是原则、分类和记录，不是一个吞掉所有字段的宽松解析器。

##### 三、统一流水线

```text
核原run/工具/产物身份和完整终态
→ 大小、编码、敏感内容与存储安全检查
→ 按通道严格解析完整载荷
→ 注册的可逆codec / 无损规范化
→ 候选结构、引用、业务不变量
→ 原语义审核 / 共享有界修复 / 受影响重审
→ 严格正式合同编译与原有Gate
```

raw、normalized candidate、formal artifact分开保存和绑定，不覆盖原件。敏感内容仍按现有策略禁止持久化，不因保留证据进入Git/日志/Attempt。围栏兼容必须在内存识别整个容器、检查解码后所有字段，再决定安全存储；不能先删敏感extra再检查。重复键、非有限数、截断、多对象和歧义不能成为成功候选；UNKNOWN仍按原请求对账，不重发。

| 结果 | 判据 |
|---|---|
| ACCEPT | 原始载荷符合当前阶段要求；不等于后续语义/素材/视频已通过。 |
| NORMALIZE | 命中预登记确定性等价规则，合法业务字段不变，规范化后满足本阶段接收条件；原不合规和动作均记录。 |
| BOUNDED_REPAIR | 需要模型理解/重填，错误可精确定位；保留合法兄弟字段，沿用原共享额度。 |
| REJECT | 无法无损恢复、未知extra可能有语义、身份/引用/授权冲突、非法终态或修复耗尽；记录具体类别，不统一叫JSON错误。 |

规范化后仍有错误，最终应REPAIR/REJECT，normalization只作为轨迹事件。不得因为发生一次NORMALIZE就把整例计成功。

##### 四、首版白名单与禁区

| 规则族 | 允许的边界 | 禁止 |
|---|---|---|
| 已知Schema回显 | 首条仅A-selection候选级contains：当前Schema确有BGM存在规则；extra恰为modality=bgm/necessity=required；外层合法且一致，无其它子项。 | 按名字删所有contains；忽略未知extra；删包含restriction/授权/否定/冲突的对象。 |
| 完整容器 | 仅明确允许文本/文件JSON的stage；整个返回为一个闭合json fence，外侧仅空白，严格解析全部内容。 | 捞第一段花括号、补截断、多个对象选一个、工具缺结果时退回普通文本。 |
| 注册表示 | 复用null/value、source映射、identity-bound wrapper和有证据的阶段内别名。 | 任意二次JSON解析、空值互换、字符串false强转bool、猜scope或补必填字段。 |
| 有依据冗余投影 | 先核身份、完整schema及与已有结论兼容，如Truth额外审阅。 | 删除未知claim、重复Need、冲突结论或Quality缺陷。 |
| 程序派生 | 独立归类为compiler derivation，仅从冻结权威值生成程序字段。 | 将真实语义补全、正文改写或模型repair冒作NORMALIZE。 |

JSON对象键顺序/外侧空白通常已由解析处理；数组顺序、正文、引文、数值单位、modality、necessity、scope、授权、预算和拒绝结论不因整理被改写。quote超长不能简单取前512字符，可能损失限定/否定；应精确反馈并定向修复。

**可选queries另行评审：** 当前允许空queries，非空时要求三个英文短语；compiler不把discovery wording当硬过滤且有description/role查询候选（`compiler.py:60-88`）。可以设计“非权威提示不可用不阻断创作”，但它会改变检索行为，不是已证明无损normalize。须先证明提示不承载唯一要求、原Need/偏好保留、无提示下检索/预算/匹配路径仍成立；保留原提示及不可用原因，不冒认模型提供了正确英文。首版不自动启用此回退。

##### 五、凭据、版本与恢复

复用OutputDecision和journal，接收凭据绑定stage、原run/tool_call/Attempt/request、冻结输入SHA、实际wire/canonical schema SHA、adapter/normalization policy及规则目录SHA、raw SHA、normalized SHA、应用规则/精确path/旧值摘要和剩余错误。不复制敏感原件。

同raw/input/schema/policy必须同结果，N(N(x))=N(x)；规则有固定顺序、次数和容量上限，冲突拒绝，不能循环尝试到PASS。已有合法业务字段不变；unknown未处理不能放行。新策略仅新请求启用；@4/@3及更旧消息/Schema/失败和恢复不静默升级。

A-selection凭据必须在A-details前持久化，details同时绑定raw和normalized身份。保存失败仅从已捕获raw重建本地凭据，不重发模型。冷恢复/正式verify按原策略重算动作与结果，不只信normalized=true；候选变化使相关已接受判断失效，沿原重审。policy进入request/cache/manifest lineage，不刷新repair或重开旧FAIL。

模型侧Schema可与正式准入Schema区分，但简化仅是具名producer投影，正式端仍完整检查必需BGM等规则；不把删模型约束当解决。本次先落有证据的入站规范化；是否隐藏contains只在后续单变量对照中判断，不同时换格式/Runtime。

##### 六、接收边界地图：统一设计，不并行重写九个模块

| 边界 | 方案 |
|---|---|
| Creator proposal | 保留章节/冻结SCRIPT权威，不能全局strip或改写正文。 |
| Preparation | 接统一诊断；topic/事实/授权错不能用正确值覆盖后放行。 |
| Planning A-selection/details | 首交付落点：raw→白名单normalize→严格检查→details绑定→恢复verify一次闭合。 |
| Planning B/repair | 复用wire；引文、必要性、来源关系和未决不靠清洗，精确修复且不增次数。 |
| 旧requirements | 标明codec/normalize/compiler区别，保持旧恢复，不作为新候选的万能转换器。 |
| Material观察 | 保留已有fence规则，绑定接收policy及raw/normalized；无效报告不等于素材不匹配。 |
| Truth | 保留合法CONFLICT/UNRESOLVED拒绝，不因外层格式问题要求改成MATCH。 |
| Production Authoring | 文件白名单、SVML/SVS/SVRun独立语法与授权；只共享身份/诊断原则，不套通用JSON清洗。 |
| Quality | 输出SHA/帧/声音证据仍绑定；规范化不改状态或删除缺陷。 |

##### 七、交付顺序及验收

**第一交付单元：** 原Task内一次实现统一接收接口、A-selection精确contains规则、凭据、details绑定、错误分类、恢复verify；不是只在入口pop一个字段。实施前窄合同复核。本草案本身不是独立批准，也不新增服务或真实调用授权。

**软件证明：** 原2071字节样本只用于独立fixture，不回写旧批。正例证明规范化后能形成details并走现有审核；负例覆盖冲突值/额外限制/未知extra/重复键/损坏JSON/slots字符串/缺字段/未知引用/quote超长/义务遗漏/错误关联。后者仍拒绝或走原repair。证明合法候选不变、幂等、raw不变、未授权path不可改、凭据中断恢复不重发、旧版本不升级、冷verify同结果；优先扩展现有集成，不按条目数量新建测试文件。

**第二交付单元：** 将已证明的Material fence、Truth冗余投影和codec登记为分阶段政策并统一诊断/凭据；不为了统一重构全部下游。可选hint回退需另有完整性与检索证明。

**真实与成片：** 新固定版本在明确未封存的预算内验证完整Planning，分别记录raw schema通过、normalize次数/规则、规范化后通过、repair和独立语义/最终合同成功。首无需模型repair不能掩盖原始错误。历史封批/费用不重开；资格达原Task门槛后立即Material→Authoring→Hypit→Quality→MP4，不再横向堆规则。当前没有新真实调用或成片。

**结论：** 同时纠正“一律拒绝”和“任意过滤”。现在有证据支持的首个规范化机会是contains；不能宣称九例都可清洗成功，不能把候选Schema通过冒充真实语义或出片。

#### 关系审核资格首例终态与访问阻塞（2026-10-09）

新批首例已实际执行：Job `wc_job_MC1TtZ_P5MLVuUHA` exit2，stdout明确`index=0/result=FAIL/actual_http=1`，后五例未派发。本次读原结果/账本/journal/捕获候选的诊断被平台安全检查拦截，未重试或改路。根因及远端release尚未知，不凭旧失败模式猜测，也不宣称已完成最终对账。独立manifest SHA `4b292773032177adca8bc2eae3add6d7d54e2cf2d7bc4828b1c70dbfa8e562d7`；私有目录`relational-qualification-2026-10-09`。软件source固定1dccfb0f，生产本轮无修改。保留原请求，只允许先恢复原终态/账本读取再决定诊断修复；失败不重开、不使用剩余次数继续此批。此时缺的是平台允许执行，不是再次粘贴用户授权。[断点记录](../acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-relational-real-qualification-2026-10-09.json)。

#### 关系审核版本真实资格：连续推进续接（2026-10-09）

用户要求“你继续按照目标推进，不用每次都询问”。本次按刚完成软件收尾后的下一步，续用最近明确的单新资格批边界执行：原3主题×2，共6例，40次实际文字HTTP、首笔提交起2700秒，所有A/B/repair/重审/Truth及框架重试均入账；仅原已购文字套餐及固定隔离M2.7/65536/adaptive。此次只启动一个新批，既有失败资格批、80HTTP池与节点对照池仍封存；不把无需逐项询问解释为无限费用或自动增加批数。

固定source `1dccfb0f1c3a68602a45b4f28240f2eec818e070828a43f6db38d4fa820b630d`、intake@4/review@2；新清单和身份，不复用旧候选或旧批余额。每例合同后独立核对冻结义务，首FAIL/UNKNOWN封批、原结果不改；普通可定位软件缺陷可以继续离线修复，不自动重开同批或刷新真实调用额度。真实Planning止于Supply入口，不运行媒体、TTS、Build；6/6后按原Task前置条件进入成片链。独立Reviewer不可用的限制保留，Owner复核不冒认独立批准。禁止部署、推送、发布或扩大媒体累计授权。

#### 关系审核续接验收收尾（2026-10-09）

本次完成前节所约定的intake@4/review@2软件修复及B消息无损去重。原断线Job72 PASS/1 FAIL已取回；测试补齐@2必要性重审的精确期望，旧版期望不变。新组合30 PASS、原生Gateway/SDK生命周期1 PASS/5回环HTTP、Planning/Truth/Material7 PASS；计数与旧回归重叠，不冒认单次全量全绿。旧@3四阶段真实请求SHA逐字重建一致；原结果、失败与账本不改。七slot/56题消息在相同指令对照下555762→391086字节，全部候选/来源/响应Schema及逐题语义值可还原，没有真实错误率结论。

生产source `1dccfb0f1c3a68602a45b4f28240f2eec818e070828a43f6db38d4fa820b630d`（221文件，dirty清单非新commit），当前验证后围栏一致；302保护/142fixture和绑定的封存账本匹配。所有本轮Job已终态，无新增真实模型/媒体/Build，无部署/提交/推送/发布，成片0/3。状态`RELATIONAL_REVIEW_SOFTWARE_VALIDATED_REAL_QUALIFICATION_PENDING`；独立Reviewer不可用，Owner复核不能冒认独立批准。[具名证据](../acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-relational-review-2026-10-09.json)。下一步为独立授权的新真实Planning资格；本节不追加调用额度，不重开旧批、不重复实施P3。

#### 重复故障收敛：候选关系证明与可执行反馈（2026-10-09，用户授权离线修复）

本轮承接用户“深度思考、降低问题出现频率并继续修复”，不重开已封存资格批。当前source基线49b69172，221生产文件、302保护文件与142 fixture已留存核对。独立MCP Reviewer仍为空；下面是Owner实施前窄复核，不冒认Astra意见或模型成功率。

**根因假设与已确认缺口：** A收到详细的预置Voice/BGM责任，却没有同等明确的视觉Need责任，最新原件将Need与最终asset混同；B原协议可以仅靠原文引用声明覆盖，没有返回候选承担关系；未决只校验handle存在，无法拒绝“声明视觉待办却只关联BGM”的类型矛盾；candidate_answer修复丢弃具体校验错误，导致quote超长重复发生。前者是待真实复验的任务设计假设，后三者有代码/原件依据，不能把新拒绝能力冒作真实错误频率下降。

**实施范围：** 新请求使用confirmed-planning-intake@4、planning-candidate-review@2。保留@3及更旧请求的精确消息/Schema/恢复。A-details表示、512字符引用上限、共享一次repair、Material/Truth和Runtime不变。A明确提出所有需外部供给的视觉/声音Need，仅已确认程序Voice例外；程序只编译身份并解析实际asset，不暗中补视觉候选。

B沿原批次增加最小关系字段：视觉覆盖必须区分covered/no_material_obligation/missing/unknown；covered须关联现有image/video候选，来源文本不是候选。无素材义务须显式判断，不能强迫每行文本生成素材。未决ACCEPT须声明原报告所需类别visual/voice/bgm/sfx，并由关联候选的实际类别完整承接；这检查类型一致性，不将模型分类当作不可错的语义事实，独立oracle仍必需。关联变动使旧复核失效，不扩大模态/授权。修复反馈保留字段路径、约束、实际长度/缺字段及来源错误，原件不裁剪；不增加次数或整对象重写。

**验收：** 先用无视觉却ACCEPT、视觉报告关联BGM、980/1060字符引用及缺字段反例证明原缺口；再验证明确匹配的外部替身可完成新A/B/一次修复/重审/编译/verify，旧@3请求与原失败SHA不变；正确的no_material_obligation保留，跨字段矛盾仍拒绝。复用既有集成、原生Gateway替身与冷恢复，不改失败成绩。软件完成后记录已消除的确定性缺口与仍未验证的真实发生率；新真实调用另有有界授权前不执行。本轮不发布/部署/push。

Owner DECISION=CONTINUE（限上述同主链候选关系和反馈修复）。主要风险是模型仍会误判no_material_obligation或required_kinds、增加答复负担、旧协议漂移；以明确字段语义、固定枚举、保留完整来源、受影响重审、原消息逐字重建和独立验收隔离控制。不承诺本轮软件改动保证成片。

**关系审核续接（2026-10-09）：** 原断线Job `wc_job_nRjMif4V1-gEiRlG`已取回72 PASS/1 FAIL；唯一失败为测试仅识别review@1而未要求review@2重审necessity，现保留旧版精确断言并补齐新策略。原FAIL/JUnit不改。原计划中消息去重现限于新且未真实派发的intake@4/review@2：B请求的逐题coverage_candidates/candidate_context改为同名共享candidate_bindings的index/SHA引用，完整候选、全部来源、问题、响应Schema及内部重审依据均保留；序列化前验证引用与原值一致，往返测试逐项恢复相等。此举减少重复传输，不裁剪语义、不改判据/调用额度，不宣称真实错误率已下降。实现后进行相关集成、原生和旧请求重建，冻结前后source与历史清单核验；真实批次仍封存，不新开。

#### P3完整真实资格执行结果（2026-10-09，失败封存）

本次获授权新单批已实际执行并封存：1/6执行，0PASS/1FAIL/5未执行；4实际文字HTTP，A-selection/details、B及原一次repair均完整返回，4原run释放。source `49b691720f2a2086773aa6d28df61cac2fff9dfe66aaa7c970a6b51da1e18ff3`保持，真实样本293.964秒，报告214263 tokens，无素材/Build/新MP4。直接失败是repair引用1060字符超过512；A遗漏六幅视觉、B无候选仍判覆盖完整及图片未决绑定BGM构成独立原始语义反例。正式语义评分未进入，禁止手动修原件计分。4参数流摘要与捕获一致；不是已确认的传输故障。后5例不派发，不把未用40HTTP移入第二批。[证据](../acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-p3-real-qualification-2026-10-09.json)。

私有新账本位于`p3-qualification-2026-10-09/actual-http/http-budget.json`，closed；manifest SHA `251a92063ad1f873cb05e9069a98dea46bee13383120ccd86ee61c2744842f1a`。四原run及唯一Job `wc_job_jsEJX8ikRlwLMi4U`已终态，原Session可直接续接。下项是使用现有原件处理A候选职责与B覆盖/绑定判断，不新增格式实验；引用过长不能通过裁剪、放宽或整对象再生成掩盖。本次不启动第二新批，不变更累计媒体授权，源码及302/142历史均保持。

#### P3完整真实Planning资格：用户明确授权（2026-10-09）

用户明确回复“继续按照方案进行推进，授权”，确认上一轮拟议单新批：原3个开发主题各独立执行2次，共6例；本批实际文字HTTP总上限40次、首笔提交起累计2700秒（包括逐项独立语义审核）。仅原已购套餐与固定隔离MiniMax-M2.7/65536/adaptive、既有Runtime；框架重试、A-selection/details、B、共享repair/重审、Truth全部计入同账本，无现金/余额/积分购买或付费回退。此授权不重开旧两批80HTTP池或4HTTP节点诊断，不改变媒体累计预算，不授权推送发布。

沿用软件核验source `49b691720f2a2086773aa6d28df61cac2fff9dfe66aaa7c970a6b51da1e18ff3`；派发前刷新源文件/原任务终态及套餐；独立新清单、账本、Creation/Attempt/request identity。正常冻结确认及既有Preparation回放入口后从全新A生成，执行完整Planning/Truth至正式合同可进入Material，随后评测器在Supply入口之前停止。本批不得执行Supply/Provider/生成/TTS/Build，也不把隔离回放称为正常生产出片。独立语义逐例对照原预期，首FAIL封批；不现场改生产后混算、不重复未知执行、不静默启动第二新批。P3原始结构与单repair边界不变，独立Astra未取得的限制继续保留。6/6达成后再按原Task审查后续成片前置条件。

#### P3发布前核验完成与下一真实资格范围（2026-10-09，旧记录保留）

本轮不再修改P3生产代码，按已有实施范围完成软件发布前核验：source `49b691720f2a2086773aa6d28df61cac2fff9dfe66aaa7c970a6b51da1e18ff3`（221文件，dirty清单，非新commit），前后指纹一致；302保护/142fixture和封存旧预算均一致。当前源码相关收尾31 PASS，原319/2与15补验不混算。真实原七slot上下文的56问题分批构造与空环境RPC容量检查通过，未作模型语义评判；实际派发要以真实运行env检查为准。独立Astra未取得，本次Owner复核不冒认独立批准。[发布前证据](../acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-p3-release-preflight-2026-10-09.json)。

下一阶段沿原唯一Task，从全新A-selection/details执行B/必要单次repair/重审/Truth，并逐项独立语义复核；不复用旧坏header，不绕过正式Material边界，不将节点诊断当资格。拟议单新批3原主题×2、40实际文字HTTP/2700秒，全部框架重试和各阶段入账，仅已购文字套餐无现金回退。**这只是待用户明确确认的新范围，不是本次“继续”的追加额度。** 旧两批和节点池封存不变，剩余数字不能自动移用。新批需派发前实际版本、身份、pending/submitting/unknown及套餐预检；失败封批不改原件。6/6完整资格成立后才沿既有授权/门槛进Material与视频主链。

#### P3 语义纠错闭合：本轮实施合同（2026-10-09 用户批准落盘并实现）

**本轮实施终态：** P3生产实现和本轮离线验证完成。组合18 PASS；相关完整两模块首轮319 PASS/2 FAIL（321项），两失败是测试期望需覆盖新增正式重校验及必要性重审，原FAIL保留。仅调整测试、保留且加强原拒绝/来源规则断言，补验15 PASS覆盖两失败及共享路径；生产代码未再改动，不冒认一次321全绿。原生Gateway/SDK P3联合纠错生命周期1 PASS/5次回环HTTP，未调用真实模型。7个源码/测试快照围栏均匹配；全生产SHA及历史全清单发布核验尚待，本轮baseline读取被平台拦截未绕过，独立Reviewer不可用。[具名收尾](../acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-p3-semantic-correction-2026-10-09.json)。下一步是获准的发布前核验及新具名真实资格；旧批/额度保持封存，不重复实施、不自动开真实批、不部署。

目标：在原Creation/Delivery/Planning主链完成“可审核候选→来源绑定审核→一次定向修复→重审→正式准入→冷恢复/verify”。保留原A-selection/A-details表示及Runtime，浅层实验不接入，不改变Material V1.3、Truth、授权、Rights、供应和Build边界。本轮为离线软件实施，不重新分配已封存两批/80HTTP池或4HTTP节点诊断，不新增真实模型调用、媒体费用、服务加载、推送或发布。

**版本与责任：** 新执行使用`confirmed-planning-intake@3`及`planning-candidate-review@1`；@1/@2和未标记旧请求按原消息、Schema、错误与修复协议恢复。原始A/捕获内容不改，正式ID仍由程序生成。候选允许携带类型合法的未决报告；正式`parse_proposal`仍拒绝未解决的意图，不能用候选对象绕过正式出口。结构损坏、未知引用、身份、容量或安全问题不送语义审核。

**必要性：** 在原B批次中加入独立`need_necessity`判断，不让整体`visual_choices`获得任意升降级权限。只有对optional的明确CHALLENGE且有核实的冻结原文/Director authority引用，才生成绑定原Need摘要、原值和来源的`confirmed_necessity`目标；value只能是required。ACCEPT保持原值，UNRESOLVED停止；required降级不在本次许可内。已有结构化音乐/预置旁白义务继续由原机制承担，不把评测oracle送入生产、不按关键词把全部视觉升required。引用可验证只证明存在/资格，蕴含仍由B判断。

**未决分类：** 原B同时逐条判断未决报告是否完整地属于“已有候选承接的待供给执行”，并返回现有候选handle绑定和冻结依据。ACCEPT只表示执行待办，不授予素材、预算或Rights；真实创作冲突、授权不明、含未承接要求、无法绑定或证据不足保留阻塞。完整原报告、原值SHA、分类和相关Need留在checkpoint；只有所有报告均被独立接受且相应Need仍在最终计划时，程序才编译出无创作未决的正式投影。不是清空原件，不新增第二待办/供应链，不扩张声音审美审核。

**共享修复：** 类型安全且不参与视觉义务判断的queries错误可原样保留在只读候选中，与B的必要性/条件/覆盖错误、确认BGM缺项汇总用一次原repair；该候选不能直接编译。无法安全送审的其他结构叶子先用原repair，后续若仍需修复按已耗尽拒绝；不加次数。B的单条响应格式错误也只能使用同一repair。所有未被目标授权的字段保持；重审所有受影响问题与覆盖，未决分类依赖相关Need语义，变化必须使旧判断失效。

**实现与验证：** 优先用一个Planning-local纠错辅助模块复用原invoke/capture、B、repair、write和Material加载，不新建Workflow。执行与verify共用确定性问题/目标重建逻辑，verify只能读取原捕获，不能派发。新策略进入请求、缓存、checkpoint；删除/替换标记或篡改原值/来源/分类/repair即拒绝。先复现原两缺口，再验证联合query+necessity+未决、真实冲突、可选保持、假依据、越权补丁、已耗尽、持久化失败/冷进程恢复、旧@2逐字恢复及损坏结构拒绝；软件证据与真实成片分开。

**续接Owner实现复核：** 原值/来源摘要的定向目标由程序重建；执行与verify复用同一评价逻辑，verify的callback仅读取原capture；正式project再次调用严格parse，候选未决只能在完整分类留痕后投影。新增的原类型反例已证实并修复非查询字段被Pydantic自动转换的漏洞；受影响Need、义务、覆盖与未决分类重审，以及未影响可选Need保留，已由joint场景断言。原生P3生命周期1 PASS，五次回环替身HTTP经过既有Gateway/SDK和捕获后完成一次联合修复；不代表真实模型语义通过。独立Reviewer当前仍无可用入口，最终范围声明须包含该限制。

**实施前Owner复核：** DECISION=CONTINUE（限上述显式纠错权限）。风险是误将未知授权归为执行待办、宽头部修复覆盖无关语义、查询校验的候选例外流入正式投影、以及新规则污染旧恢复；分别由来源/候选完整绑定、精确目标及原值摘要、正式重校验和版本化重建保护。当前`mcp_tool list`为空，独立Astra不可用；此为Owner的前置合同复核，非独立Astra批准。最终仍须实际集成/恢复证据，不能由本节认领实施完成。

#### 节点对照结果与P3接续决策（2026-10-09）

本轮已完成授权内真实诊断与观测器最小修复：2/4格实际提交，原表示4613字节Schema PASS但首格pre-SDK摘要缺失；浅层首格原生error/released且仅有通用STRUCTURED_EXECUTION_FAILED，后2格停止。新测量子清单只续原未执行cell，绑定父账本原SHA及同900秒绝对截止，总计2HTTP/47240报告tokens；原两批及本诊断父/子账本全部封存，无未知未释放原run。[证据](../acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-planning-node-contrast-2026-10-09.json)。

P2表示选择：**保留原生产表示，不接入ShallowDetailsExperiment，不继续扩大Runtime修改。** 原格式能够在这个真实节点输出合法对象，但不能外推重复可靠性。浅层没有优越性证据；观测器问题是测量实现缺口，不是Planning正式合同缺陷。首格缺失摘要不补写，浅层Runtime根因不足不虚报。

P3仍按原方案独立处理且尚未实施：necessity-only修复必须有独立判断、冻结来源及原值绑定，仅改被挑战字段并重审受影响义务；未决报告先逐项判定真实意图冲突或明确的待供给执行，保留原文本/判据，不简单清空。不得批量把optional升required，不能将本诊断复用的旧坏header认领为新生成语义成功。跨模块修复权限先按AGENTS前置复核，原共享repair与旧版本恢复保护不变。下一开发目标是完成该窄纠错边界，不再从结构传输全盘重做；新真实模型执行不由本结果自动授权。

#### 首格测量缺口修正与剩余cell（2026-10-09）

原4HTTP对照首格实际使用1次文字HTTP，原run成功/released；API HTTP完整结束并返回tool_calls，但无已识别的SSE [DONE]，新增观测器仅认可该标记，未保存参数流SHA，按原规则停止且原诊断账本closed。不是参数SHA不一致；从原run只读恢复的4613字节结果slots为object、顶层齐全且实际Schema PASS，但上游SHA缺失仍UNKNOWN，不补造、不覆盖首格。

仅修测试/评测观测器：HTTP读取自然EOF且各工具choice已tool_calls时，可结束接收字节摘要；缺finish、半帧、冲突和finish后新增参数仍不输出完整摘要。它不改变Runtime终态、安全及正式Schema准入。测试修前失败/修后相关2 PASS。首格和旧budget保持封存。

原新增授权是累计4HTTP/900秒，而非增加新批次额度。完成上述本地修正后，只执行原预冻结尚未提交的3格（shallow/shallow/original），使用测量v2子清单绑定父清单、首格账本SHA及原first_reserved_at+900绝对截止；上游3HTTP上限与累计4HTTP双重核验，原池不重开，原槽位不重跑。若剩余时间/审批/未知执行不满足则不提交。此为已定位观测问题修复后的同额度续接，不把首格缺证据改成成功，不混算成正式Planning验收。

#### 节点结构对照授权与执行（2026-10-09 用户确认“按方案继续”）

用户已确认上一轮明确请求：新增最多4次实际文字HTTP、累计900秒，仅原已购套餐，同隔离MiniMax-M2.7/65536/adaptive及既有Runtime。使用独立`planning-node-contrast-2026-10-09`清单和EvalHttpBudget（4/900），不重置旧两批80HTTP池，不产生媒体/Build/发布授权。

固定最新失败原A-selection、冻结来源、实际A-details Schema和原消息；对照顺序为original、shallow、shallow、original，各两次独立新身份。shallow只使用已离线验证的test-only ShallowDetailsExperiment，移除slots外层容器并增加对应表示说明，不调整内容、required、未决项或语义判据。不将原失败候选清洗后作为控制，不改生产Planning。调用原Web计时Agent/原Delivery身份与隔离Gateway，全部文字请求穿过同一个4HTTP总账；SDK重试也占额且同一cell仅允许一次实际提交。

这是节点诊断而非正式Development：完整终态与参数保真成立时，Schema拒绝作为对照观察保留，可继续下一预冻结cell，不认领产品成功；传输UNKNOWN、参数摘要缺失/不一致、非成功终态、安全错误、配额不足或总额度/900秒上限则停止后续提交。每cell记录Provider入口参数流SHA、SDK/Easel捕获SHA、结构结果及独立语义风险；不保存敏感请求内容、不打印认证。新增流摘要只证明API返回至捕获的一致性，不证明云端具体解析器或模型原生token。

实施前Owner窄复核：只新增隔离诊断编排，复用已验证模块；在本地替身中先验证冻结清单/单次提交/闭合账本和参数SHA。独立Astra此前不可用，不冒认其意见；此次不放宽正式修复权限，不启用第二生产链。原始表示通过则不因实验存在而自动切换；任何生产接入按原P2/P3的语义与恢复条件执行。

#### 本方案已执行结果与下一关（2026-10-09）

P0已核对：原两批均FAILED_SEALED，总池仍STOP_BATCH_COUNT_EXHAUSTED；没有重置账本。P1已通过现有原生Gateway→SDK→Easel捕获/组装实际离线回放：6次本地替身HTTP，包括真实7-slot Schema正确控制、未改失败原件、60/150分片，以及7680字节正确原表示/7670字节浅层等价表示，逐字SHA一致。最早保存的SDK easelRawArguments已包含string型slots，SHA与Easel原件相同；未保存旧上游SSE，不能把云端具体解析器归因写成事实。正式生产源码/Runtime未变。

P2本轮只改现有测试/评测模块：增加不保留参数正文的分流SHA证据，支持本地分片回放，并提供test-only `ShallowDetailsExperiment`（只把确定槽位从slots下展开到工具顶层，原字段Schema/绑定/容量/未决项保留；非法原件不能通过encode）。新合同测试及原实际HTTP预算/阶段化合同回归4 PASS，无新增真实模型调用；浅层表示尚未用于正式Planning，不宣称其真实效果优于原表示。

P3已离线确认两个原合同限制，未将它们当普通Bug直接放宽：非空unresolved在B前被拒；visual_choices必须保持necessity，已有回归也明确禁止整体头部升降级。拟定窄修复方向：单列来源绑定的必要性判断/字段修复，且重审全部受影响问题；对未决报告先区分真实意图冲突与下游未执行，保留原报告及判断证据，真实未决继续拒绝。不得清空unresolved或把所有image升required，不增加共享repair。上述涉及纠错权限，需按AGENTS前置复核后实施，当前不冒认可用。独立Astra当前未提供，Owner意见不当作独立批准。

下一步不再盲开完整批：先就现有实际A-details和浅层等价形式做具名节点对照，建议最多4实际文字HTTP/900秒（待用户明确新增授权，不复用旧池），保持原模型/Runtime/上下文，记录pre-SDK与capture的SHA、完整性、结构/语义各自结果。原表示正确则不切换；只能根据对照和实际语义纠错证据选择最小实现。节点成功后仍须原Planning资格与真实Material→Authoring→Hypit→Quality→MP4，不能将离线音视频测试冒认目标成片。[本轮证据](../acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-planning-boundary-replay-2026-10-09.json)。

#### Planning 边界定位至成片：执行方案（2026-10-09 用户要求落盘并执行）

目标仍是同一Creation/Delivery主链交付可审阅MP4，继而同版三个不同主题自主出片；不以软件PASS代替成片。基线为`intake@2` source `e6c7e125…9972b8`、HEAD `df0d3a30`的未提交工作树。本次授权执行此前讨论的方案与必要离线研发；不自动重置已封存的两批/80HTTP总池，不假定已经获得新的真实诊断批授权。

| 步骤 | 实际工作 | 完成条件与不能认领的内容 |
|---|---|---|
| P0 现场冻结 | 核原Session/Job、现有源码摘要、封批账本及原件；原样保留所有历史FAIL | 无未知执行才新增工作；常驻进程与历史协作消息不作为并行写入证据 |
| P1 结构边界定位 | 核本次A-details实际Schema、最早保存的参数与终态、SDK/Runtime和Easel捕获；用真实Schema构建正确控制组及未修改失败参数，离线通过现有原生接收链 | 分清正确JSON对象是否被中间层破坏、外层arguments字符串与内层slots字符串；参数原文未保存的位置标UNKNOWN，字节数相同不等于SHA相同；不得将SGLang行为当作MiniMax云端证据 |
| P2 最小修复及可修复性 | 仅修P1证实的实现缺陷；把容器/必填字段/局部叶子/语义/传输终态分开诊断，保留拒绝；检查repair前置位置 | 正确控制组无损，失败原件仍拒绝且错误定位明确；不能静默JSON二次解码、补顶层字段或整对象重生冒认局部repair。需要更换carrier或Runtime则先窄设计复核 |
| P3 确认义务与未决边界 | 独立复现necessity被挑战却不允许修、unresolved在B前拒绝的路径；核来源与现有正式语义 | 明确结构化确认义务程序继承、自然语言由独立语义判断；不得把所有visual升required。针对被独立挑战字段的修复必须绑定原值、来源和重审，共用原额度；真实未决仍不得发布正式合同，未供应不等于意图未决；如安全修复需超出原合同，先给出最小变更决策，不偷偷放宽 |
| P4 节点真实诊断及Planning资格 | P1–P3证据闭合后，提出独立小规模真实节点诊断清单，再按原Task进入Development资格 | 原两批保持关闭；新调用须另行明确额度和窗口，节点通过不等于Planning通过。保留同模型/Runtime，无静默付费或模型回退 |
| P5 第一条视频及复现 | 资格门满足后，现有Material/Rights/Readiness→Authoring→已核实免费Hypit→Quality→MP4，原预算足额才执行 | 路径真实存在、解码可播放、required与音画字幕符合、质量报告绑定实际字节；第一条交Creator审阅，同版三个主题零工程介入另行计分；禁止自动发布 |

执行约束：当前回合先执行P0–P3中有证据且在授权内的工作，不再反复开全项目审计；复用不受影响的有效软件证据，修改覆盖范围后重跑相应验证。跨模块责任或修复权限变化先做前置复核；独立Astra不可用时记录Owner复核及限制，不能伪造意见。按阶段记录实际状态、源码/测试身份与下一步，不以计划表代替执行。

开源参考只用于方法：Pydantic AI Output区分Tool/Native/Prompted与validator；Instructor区分输出校验反馈与网络重试；SGLang `minimax_m2.py`对象解析失败回退字符串是排查线索，不是云端实现证明。参考地址：`https://ai.pydantic.dev/output/`、`https://python.useinstructor.com/concepts/reask_validation/`、`https://github.com/sgl-project/sglang/blob/main/python/sglang/srt/function_call/minimax_m2.py`。本方案不引入这些框架或建立第二条调用链。

#### 当前可恢复停止点：新增两批已用尽

原新增池`continuous-development-80http-v1`已记录`STOP_BATCH_COUNT_EXHAUSTED`；allocation1/2均首例真实FAIL永久封存，总3实际HTTP/67292报告tokens，无第三批授权。当前`intake@2`source `e6c7e125…9972b8`及77 PASS代码保留未提交，原@1精确恢复已验证；最新真实阻塞为A-details的slots字符串/顶层缺项，同时有视觉required降级与素材未供应误作unresolved。两项独立风险未解决，B/Truth未进入，0/3视频。三个原run释放、真实Job终止，真实原件和历史保护不变；末次全局状态刷新平台拒绝，不绕过、不虚报完成。当前Session检查点与[最终汇总](../acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-intake-continuous-final.json)是下一次续接入口；只读诊断先于任何新执行授权，不重跑封批样本。

#### allocation1失败后的窄输入呈现修复（实施前判断）

新池第一批`401514a0…c9f8d`在source `f7d3ddc8…558a`首例153.776657秒/1实际HTTP后永久FAIL；模型把声音program_reference.span的[830,2051]拼成非法scope，同时将程序旁白误列成第二BGM。原enum拒绝正确；不修改原件、不把非法引用规范化成合法引用，不把来源存在当语义支持。实际信息提供方式可能诱发范围/来源混淆，这是待真实验证的假设。

获授权第二批之前只调整A消息呈现：新`confirmed-planning-intake@2`由程序将已冻结sound/sound_source引用展开成原文字串，既有输入视图快照/来源映射不变；提供真实global使用范围handle，明确scope不等于原文证据位置，程序旁白不得换成其他模态重复提交。模型仍拥有完整音乐意图和候选选择；不增加B音频职责，不自动补Need，不放宽scope/repair/容量/下游合同。`@1`及无标记旧请求必须逐字重建原消息，并保持原恢复行为；新policy进入现有transport身份。实施前Owner只读复核限定以上差异；独立Astra接口不可用，不认领其意见。测试必须证明冻结声音逐字呈现、快照不改、输出schema不变、旧真实消息SHA仍匹配、新旧verify与共享repair保持。只在新固定源码的软件证据成立后分配最后一个批次。

#### 本轮执行停点：已接入，尚未验证（2026-10-08）

新intake标记已进入semantic_boundary_run的请求/恢复/正式verify，queries字段定位、JSON化patch和必要BGM缺项共用一次原repair；扩展了现有组合测试。执行定向验证及初始化私有总账的run_script被平台安全检查拦截，未取得Job或退出结果；原14PASS不能覆盖当前改动。只保留IMPLEMENTED_UNVERIFIED，不加载服务、不启动真实批。平台允许后先核执行记录再验证；不得换入口绕过此拦截。新80HTTP池未发生真实调用，不能声称私有池已成功创建；原授权仍有效，旧批全部保持关闭。

#### 连续开发新增有界授权（2026-10-08，本会话用户明确授权）

普通可定位缺陷不再结束整个研发Goal，但真实失败批仍立即永久封存。新增文字开发池最多2个独立批次、累计80实际HTTP/5400秒；每批仍40HTTP/2700秒、原三主题各两次，含所有诊断、A-selection/details、B、Truth、repair及重审。使用私有`continuous-development-80http-v1`单一总账，每批预分配40HTTP/2700秒且绑定唯一manifest，不能因Session/版本/清单变化刷新。历史`dd184d52…9d3d11`等关闭账本不重开、不移分。仅原已购文字套餐，无现金/余额/积分/付费回退；媒体原累计¥30含历史占额不变，免费本地Hypit须核实，不发布。

同Session的另一续接执行链已在`wc_msg_ak2BBbrZoOmRiV5N`明确暂停并交接中间代码，本轮为唯一生产写入与真实派发Owner。查询字段+JSON补丁序列化已有中间14PASS；后续新增intake policy尚未接入/验证，不能沿用该14PASS宣称新版本通过。本轮先完成新旧协议与共享修复闭合，验证后才消耗上述新池。

#### 当前续接：query错误叶子定位及声音覆盖核对（2026-10-08）

**实施前窄边界裁决：** 新请求采用`confirmed-planning-intake@1`，进入既有transport/request/checkpoint身份；@9无此标记及更旧请求保持原消息、Schema及修复判定，不升级旧pending/FAIL。queries合法集合及正式Material合同不变；新policy才启用字段级错误定位。局部patch输出按JSON模式序列化，避免tuple被后续JSON Schema误拒。

确认方案specs.audio_mode的`mixed`/`music`是已存在的明确音乐义务（不从自然语言或Preparation默认值推断），新A-selection工具Schema以contains提示至少一个required BGM；scope仍是使用范围，不冒认SCENES是声音唯一出处。若A漏交BGM，程序只产生一个有界缺项target，由同一原共享repair提交新BGM候选；若唯一BGM被降optional，只允许改necessity；多个optional归属不清则拒绝。与queries的已定位错误一起使用一次原repair，禁止分阶段刷新次数。程序不生成曲风/条件/音轨、不静默插入正式Need，不改B的视觉职责；后续原独立oracle及Material准入仍须通过。

只读风险复核：必要音乐presence不是声音语义全部通过；旧历史必须精确回放，新策略与旧策略均测试；任何音轨来自Preparation推测、删合法候选、刷新修复或循环复跑旧批均不允许。当前连接没有独立Astra调用入口，本次为当前Owner的前置只读合同复核，不能标为独立Astra意见；按AGENTS的不可用模型说明在上述最小范围继续。原件与既有失败记录保留，真实批仍须新固定及软件证据。

用户要求继续原Goal直到流畅出片，继承既有预算、停止条件和单主链；上一`dd184d52…9d3d11`真实批保持FAIL/closed。首先只修复已证实的实现缺口：将既有queries约束从Need级校验移到queries字段校验，合法集合、输出Schema、原件、其他字段及共享一次repair不变。先以失败反例证明旧代码无法给出字段target，再验证真实内部capture→A组装→局部repair→B→正式compile/verify及恢复。未知或跨字段语义错误仍拒绝，不能删query或自行翻译绕过模型修复。

必要BGM遗漏单独核对：现有B明确只做视觉审核，不能声称它会补声音。继续前必须区分确认音轨方式、A候选责任、全局scope与声音原文支持关系；不直接向成品补BGM、不放宽required、不重开旧批。生产/测试变更后使用新固定source及有效证据，范围外或同根因停止条件仍有效；本条不是新真实批成功或无界费用授权。

#### @9真实资格首例停止（2026-10-08）

本次恢复授权下，新清单`dd184d5246cd2a1e7c8e1b45670a90a509b753ca459c265d1f67ea64169d3d11`在source `cc5587a4…4f4e`只执行第0例：132.958秒、A-selection/A-details各1实际文字HTTP，原run均ok/released。selection结构合法；details六个视觉query均为一中一英两条，未满足现有三条英文合同。canonical错误提升至Need根，现有结构修复定位器拒绝为不可局部修复；repair/B/Truth均0。另观察到selection缺少冻结所需BGM，不将其混同运输故障。批BATCH_FAILED永久关闭，后五例未执行。[脱敏结果](../acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-source-view-real-failure.json)。

本次触发原首失败停止条件；不继续派发、不重开清单、不改正式原件或删需求。下一技术焦点是既有query错误叶子定位/有界修复，以及独立必要BGM覆盖，而不是再改Gateway容量或重建主架构。软件1034PASS/5skip、矩阵276PASS证据保留；真实生产能力未通过，正式视频0/3。当前生产源码、服务、旧失败及累计费用账本不变。

#### @9交接恢复与软件收尾（2026-10-08）

用户明确由当前WebCodex会话恢复原Goal；继承原预算、失败封存、必要审批和停止条件，不扩架构，不推送/发布。生产source `cc5587a4…4f4e` 与220文件归档完全一致。复用run-053矩阵276 PASS、排序后4 PASS及六例冷进程6/6（30本地替身HTTP）；仅补缺失全量回归，1034 PASS/5既有skip，0失败。运行后源码、65个Python测试文件、302保护现场及142fixture不变。[汇总](../acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-source-view-software.json)。

当前为SOFTWARE_ACCEPTED_REAL_UNPROVEN。下一步使用本交接建议的新固定@9资格批：复用原三个开发主题及独立oracle，最多40实际文字HTTP/2700秒、仅原套餐、首合同/语义FAIL或UNKNOWN停止；不得重开旧批或隐式续期。当前尚无新真实调用，线上仍未加载@9，正式视频0/3。软件全绿不自动认领真实成功。

#### @9接入与持久化顺序回归（2026-10-08，验证中）

同一Planning状态机已接入可逆输入视图；新原件与SEMANTIC_INPUT_VIEW快照进入正式verify及冻结复制，新旧Schema/消息按版本分派。10项新旧恢复/重放PASS，本地原生Gateway五次HTTP PASS。Astra代码只读CONTINUE完成软件验收，尚非真实能力结论。

组合测试首次29 FAIL/26 PASS：旧外部fixture尚用payload.catalog；适配后正常match/fork两例仍FAIL，确认是JSON sort_keys改变catalog.voice引用顺序导致lineage身份失配。程序改为确定性scope/Voice遍历，测试新增持久JSON顺序往返不变；同两条真实内部链及完整回建4 PASS。初始失败保留，不更改准入期望。冷进程初次Provider夹具误取完整用户消息最后一行为JSON，1本地HTTP失败；改用已解析context，保留原JUnit再执行。没有真实模型调用或线上变更。

下一步完成已启动的完整矩阵、常规回归及三主题各两次独立冷进程回放；记录最终源码、调用身份、复制/修复与现场对账，经阶段复核再冻结真实清单。Goal最终0/3视频仍未完成。

#### 完整输入视图离线验证通过，@9软件接入开始（2026-10-08）

此前样例的完整来源回建缺口已补齐：从视图与明确的程序lineage恢复inputs/catalog，再调用真实authority.catalog核99条来源的原文、SHA、资格、scope、重复数量和顺序；引用路径为JSON key/index数组，正文区间明确UTF-8字节，原authority span保持Python字符。实际Voice目录条件生成，无绑定Voice不注入；独立原文无法精确引用时保留原值。真实@3、另一份合法@2/非空continuity/无bound Voice、Unicode/CRLF重复行及独立错误文本保护，2PASS/0.54秒，compileall/范围diff通过。初次负例逆序单元素未产生变化，测试失败保留，修正造例不改合同。[完整离线证据](../acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-source-view-roundtrip.json)。

Astra前置CONTINUE有限@9软件实施，尚未接入生产或真实试跑。实施约束：新journal/checkpoint/input-view/codec身份；每次从冻结inputs/catalog重建快照并核对，快照不能自证权威；details同时绑定原selection字节、canonical候选、opaque header及view/map身份；B沿用原语义题但机械核来源映射；verify和冻结复制覆盖新程序视图；@8及以前原消息/Schema/修复额度精确不变。必验新旧恢复、未知/错映射和快照篡改拒绝、共享一次repair、正常Owner/Truth到Supply切点；不扩大框架、Gate或Material职责。

#### 输入合同根因核查与有限离线设计（2026-10-08）

**本轮没有生产修改、服务加载或新增真实调用。** 原@8首例FAIL保持；当前source仍`199fba42…01eaa`（包含上一轮布尔Schema异常修正），302旧现场对账保持，正式视频0/3。

精确重建原A-selection消息45785字节，SHA`059086512763c6ddfc7776033f553ad46b56eb72e4380845fd77f777a3c799be`与journal一致；工具Schema也与原Gateway身份一致。不是错版本、请求漂移或缺失终态。根因分层如下：

| 观察 | 已证实的输入风险 | 尚不能认领的结论 |
|---|---|---|
| 必要BGM被降optional | 确认声音要求与Mode的“BGM is optional”同包呈现；mode_defaults已有preference资格，但A只见原文，没有统一资格视图 | 不能断言Mode是唯一因果；不能把整个audio-bible降级或删除该句 |
| 六镜头候选选scene-1至6 | source_catalog按27非空物理行建立三套同号scene/event/segment；scene-6实际为第二镜标题 | 不能用正则猜六镜边界或自动合并原文；模型仍需选择来源kind和义务 |
| 空continuity填segment/global | Schema确为items:false，模型跨目录误选；要求模型填写唯一合法空值是多余结构维护 | 新codec可以省略真空目录字段并补[]，不能清洗历史非空结果 |
| sidecar/声音文件未决 | plan/script/sound_source哈希多处重复；sound_source实际是声音方案文本摘要，模型误认为声音文件 | 输入已明确程序拥有这些字段，不能说程序要求模型补文件 |
| 字幕/旁白伪装image | 无相应素材授权；请求真实包含“程序Voice不得重复”和“字幕后期不建立image”的规则 | 仍是独立语义判断失败，表示整理不会自动解决 |

**已做离线样例，而非又一次生产Prompt补丁。** test-only `SourceSelectionExperiment`保持原kind＋原文位置一对一opaque映射，global及全部三类合法范围不变；空continuity才省字段，非空目录保留原选择。82个位置/类型往返、旧坏selection拒绝、unknown/旧handle/跨catalog/注入continuity拒绝及非空目录保护1PASS。首次人工对照漏kind被原Schema正确拒绝，失败JUnit保留后修正fixture，不改合同。

实际输入样例把SCENES按带换行的原始物理行呈现，proposal五处重复正文以精确UTF-8区间引用；Mode/Preparation/Truth等原值全部保留，程序binding另存私有lineage。99条现有资格按origin/path/relations/primary/span合并为25组，**仅这些分组字段展开一致，尚不等同完整authority catalog无损**。初稿逐条资格导致54.5KB，保留但不采用；第二样例JSON31.9KB，原值是45.8KB完整请求，两者计量对象不同，不宣称模型压缩收益。样例、原件和JUnit在本机受保护`source-view-offline-v2`，脱敏[设计记录](../acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-source-view-design.json)。

**下一实施细节（先离线完成）：**

1. 定义引用路径语法及offset单位。旧authority span为Python字符区间，新正文引用为UTF-8字节区间，显式区分，程序转换时核原文，不能混用。
2. 实现确定性解析与完整回建；逐条核原值/文本、SHA、资格、scope关联、重复数量及顺序。找不到完全相同正文时保留独立原文，不模糊匹配、不丢弃。
3. Voice引用从实际catalog生成，不硬编码两个条目；补另一合法proposal、非空continuity、无绑定Voice、Unicode与不同换行样例。
4. 完成后再复核生产接入设计。若接入，采用独立新journal/checkpoint及input-view/codec policy，@8及之前精确恢复；新请求、details binding、B来源题、verify核同一映射。不得把新的handle反写历史Plan或冻结原文。
5. 模态、必要性、责任、叙事分段及自然语言冲突仍属模型语义判断。已确认要求高于默认值的规则不等于程序能裁决任意文本。保持原B/Truth、共享repair、Material V1.3及正式准入。

Astra结论CONTINUE只允许继续完整离线设计；当前没有生产接入批准或模型收益证据，不启动真实试跑。Goal的预算与持续实施授权保持，不再以费用重复确认代替技术决策。最终完成标准仍是同固定版本三个全新主题自主MP4/正式素材覆盖与Quality，不能以本样例替代。

#### 两阶段真实首例FAIL与离线异常修正（2026-10-08）

清单`970ccb4e…6464f`已实际执行：首例27.749秒、1实际文字HTTP，A-selection原run ok/released、完整1732字节，随后诊断shape在JSON Schema `items:false`上调用`.get()`而抛AttributeError。批永久FAIL/closed，后五例未执行，details/B/repair/Truth及Supply/媒体/Build均0；原selection、请求/账本及完整隔离现场保留。[真实失败记录](../acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-staged-real-failure.json)。

模型原件还有独立语义问题：无连续性目录却填写segment/global、必要BGM降optional、字幕/旁白伪装image、下游文件/sidecar未绑定被记成Planning未决。因此不是只修程序异常就解决；A两阶段的真实可靠性仍未成立，不继续下一批、不恢复本批计分。

Astra只读CONTINUE最小异常修复，真实路线STOP。已按原件先复现1FAIL，再令诊断shape显式处理布尔Schema而保留原值；正式严格校验及原共享一次repair不变。codec/两阶段恢复身份9PASS，真实内部selection→details→一次其他叶子repair→严格拒绝及重入零新增1PASS；compileall/范围diff通过。未重跑无关全量；此局部软件通过不能改写旧source验收或真实FAIL。[修复记录](../acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-staged-bool-software.json)。

本轮新增媒体费用0，Goal保守占额仍¥15/¥30；文字18268 reported tokens、实际账单UNKNOWN，套餐检查窗口99%/周97%。正式视频仍0/3，未加载服务。目标未完成；后续需离线验证真实请求上下文与语义任务分工，不能在没有新证据时再开真实批。

#### 两阶段独立真实批固定（2026-10-08）

沿用用户持续执行Goal及“额度按照推荐的授权，无需再次确认”，本批绑定新清单`970ccb4e2e97118965e9c6cc5bb760809d373acc84cb1e9af9b052f64bb6464f`，source `a2a18186…71bfc`、@8及原隔离Runtime，最终8份执行工具、三个冻结开发主题各两次和独立语义判据。仍限40实际文字HTTP/2700秒、只用套餐，首FAIL/UNKNOWN封批，不复用历史失败额度、不增加媒体占额，不启动线上Supply。全部通过后再按原Goal推进服务及完整视频。调用前核对实际套餐、旧任务与固定指纹；本段不是成功声明。

准备时草稿把journal标签误写成planning-semantic-run@8，零HTTP即停，保留原件并以PREPARATION_SUPERSEDED_ZERO_HTTP关闭；正式清单使用源码真实标签semantic-planning-checkpoint@8，准入、样本、预算和源码不变。旧模型批FAIL不变。

#### A两阶段软件实现与组合验收（2026-10-08，离线通过）

新Planning默认已接入journal/checkpoint @8：selection安全捕获后持久化details身份，按程序固定slot收取详情，再交原canonical/B/一次共享repair；旧@7及以下保留原请求与合同。原selection/details各存一份，assembly单独命名；verify重建两阶段Schema、请求摘要/session和组装结果，再重放原repair。冻结复制携带三份对应产物。没有新增HTTP路由、Runtime框架、第二条生产主链或Material准入放宽；没有加载服务或启动真实调用。

三崩溃切点、UNKNOWN原身份恢复、结构/语义修复及重入通过；原件、assembly、binding与请求身份篡改拒绝。正常入口→Owner→Planning→Truth和声音/冻结复制保护49 PASS/397.44秒；原生Gateway/Harness两阶段及B/repair/recheck 5本地HTTP，1 PASS/30.26秒。完整run-052矩阵276 PASS，302受保护现场/139历史fixture/生产及测试源码对账保持；全量1029 PASS/5既有skip，629.82秒，115技能/compileall及本次范围diff通过。全树两处历史Markdown EOF空行仍保留。[软件证据](../acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-staged-software.json)。

初次广泛回归32 FAIL/254 PASS，原因为固定外部响应仍只识别旧单A入口；保留失败JUnit，更新测试响应为两阶段，没有更改准入期望。旧@7矩阵显式建立旧journal；新两阶段、Owner及原生Gateway测试使用实际fresh默认。当前生产source `a2a1818627b816fd030b1c74ae3cc56515d5b454ee1cd72729b49b423db71bfc`，HEAD仍`df0d3a30`，未提交、未加载。复核CONTINUE限于离线收尾，不能认领真实模型收益。

最后复用原资格执行器，六例各新进程的Planning/Truth本地回放6/6 PASS，408.98秒、30本地Provider HTTP；完成后重入0新发，账本BATCH_COMPLETE关闭。矩阵完成后仅更新该执行器的本地Provider固定响应以识别新两阶段，生产和已执行矩阵内容未改变；新工具指纹、请求记录、账本及JUnit单独归档，不冒称与矩阵工具快照相同。首次冷测试选错单主题输入清单，0HTTP拒绝；保留失败记录，改用既有三主题输入重跑，无门槛修改。

**预算口径修正：** 下文设计阶段的18→24、36→42是将Truth视为单一逻辑提交的估算，不能称为实际HTTP上界。本次六例实测每例两次A、一次B、Truth写报告/终结两次HTTP，合计30；有repair或更多B时另增。实际次数由Proxy账本逐次占额，包括Truth及其修复。原40HTTP是硬停止上限，不是完成六例的保证；没有提高额度、重新打开历史批次或启动新真实清单。本轮新增真实费用0，媒体全Goal保守占额仍¥15/¥30，正式视频0/3。最终阶段复核后才能制定新的真实运行清单，离线通过不证明模型语义改善。

**最终复核：Astra CONTINUE。** 本阶段为SOFTWARE_ACCEPTED_REAL_UNPROVEN，source与完整源码快照已私有归档；可准备绑定@8 source、Runtime、最终工具、输入、模型参数、独立语义判据及停止规则的新清单。全量5项skip均为缺bun的既有微信发布测试，本阶段必验项无skip。没有服务加载或真实调用，不恢复旧批计分，不因软件通过宣称稳定出片完成。

#### A 两阶段候选：有限离线设计与后续实现边界（2026-10-08）

**当前只有测试原型，生产未接入，模型可靠性未验证。** M3、M2.7原批FAIL/closed保持，不复用剩余额度、不再次询问同项费用授权。目标仍为同固定版三个新作品自主出片，当前0/3。

候选设计把A的单次联立输出拆成两个已有Planning请求：selection提出scope、role、modality、necessity、continuity及unresolved；程序按原顺序生成固定slot和对应模态的details Schema；details只填条件、用途与该模态适用字段。程序无损组装现有canonical，接原B、全Planning共享一次repair、Truth与Material消费者。selection仅是候选，不是语义批准；不得由程序挑模态、删Need、翻译或补造query、清理真实坏A。scope仍是冻结物理行，不能冒认已修复叙事分段。Creator/Director、Material V1.3、Hypit及准入职责保持。

**离线证据：** 复用原union矩阵的109项合法完整往返，包含模态、默认值、重复及顺序，经公开XML参考parser后canonical一致；原135行矩阵保持。新增14项身份/槽位/跨模态/原修复域/历史FAIL保护；现有真实内部Planning集成分别验证B header修复与selection结构叶子修复，各仍只有一次共享repair，不重跑候选。最终5 PASS/17.70秒，0外部调用；不是两请求生命周期或模型能力PASS。[具名证据](../acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-staged-producer-design.json)。初版比较诊断对象与补默认值后对象导致的测试FAIL及原JUnit保留；修正断言比较未修字段，不更改生产实现。

严格身份与业务诊断分开：缺/多/重复slot、header注入、跨候选或Schema错配直接拒绝；可安全组装的错误业务叶子交原structural targets，正式接受与修复后仍完整校验。原visual_choices允许image→video等受限header修复，但**necessity升级一直禁止**，本设计不扩大其权限。两份unresolved合并保留，不能借拆分删除；总容量仍受原合同限制。

**Astra初审MODIFY的诊断缺口已修订；最终CONTINUE，仅限软件实施，不能据此启动真实批次。** 生产接入必须完成以下持久化及验证，并执行真实内部离线集成：

1. 在原journal/checkpoint增加版本，沿用一个状态机和capture。旧@7及以下按原请求、Schema和额度精确恢复；新版本不能认领旧pending。
2. selection原run成功、released、安全捕获且持久化后，才可派生details。details身份绑定scope、原selection字节SHA、候选SHA、codec/Schema/Runtime；先持久化后提交。selection语义尚未批准，不能因receipt限制原B合法修复。
3. 必验三个崩溃切点：selection已捕获而details尚未登记；details已登记而未提交；details已提交但终态未知。恢复必须核对原身份，不能补发、刷新额度或重做selection。未知终态不推进。
4. verify从两份原始安全捕获重新生成slot/Schema并组装，再重放现有repair/B复核；不能用派生assembly或lineage取代原件。两阶段schema错误和原始字节分别保留，不能把程序组装结果标成模型原始A。
5. 新请求仍受30次Planning技术上限和实际HTTP账本双重限制。B前上限预估由`1 + B批数 + 1 + 最大重审批数`改为`2 + B批数 + 1 + 最大重审批数`，不扩大上限。未知/修复失败沿原停止语义，禁止第二套repair。

**代价与未解决风险：** 每Planning增加一次原始提交。每例一轮B且无修复、含Truth时，六例最低18→24次；若每例一次共享repair、一次B重审、一次Truth修复，六例36→42次，超过旧40次批次上限，不能照搬旧清单。测试目录16个image时selection Schema886B、details33865B，保守紧凑结果上限约0.21/2.76MB；这是该目录/模态的容量测量，不是所有目录或实际模型输出能力证明。错scope、错必要性、后期混素材、错误query和遗漏义务仍可能发生；拆分只是减少同次重复字段及跨模态选择，不保证语义正确。

下一步仅完成以上版本化机制及离线恢复/旧合同回归，再作阶段复核。未实施前不加载服务、不冻结新的真实清单、不认领MATERIAL_READY或视频成功；文字套餐及媒体累计¥30授权保持，无新增费用授权请求。

#### ec14批最终FAIL与套餐内候选接入核验（2026-10-08）

**M2.7批最终执行结果：FAIL/STOP。** 用户授权后按原清单执行，首例48.619秒/1实际HTTP，HTTP200/tool_calls、native ok/released，完整7893字节。15个Need包括6重复Voice、6视觉、1BGM和2纯后期Image；wire23处错误，原正式消费者报“A fault cannot be localized without replacing valid semantics”。既有修复合同不允许删除Voice、重写所有query、搬移声音字段或把后期要求伪造为素材义务。B/repair/Truth0，后五例未执行并永久封批；所有素材/制作操作0，不能挪用剩余额度继续试错。

完整失败现场、账本、原工具参数及Schema保留；永久fixture `autonomous-m27-qualification-A-*`，已有回归扩展后1PASS/0.55秒。生产source、302旧现场及冻结工具一致；媒体新增0，占额仍¥15/¥30，文字报告22449 tokens/实际账单UNKNOWN，结束套餐99%/周97%。[失败记录](../acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-m27-qualification-real-failure.json)。

**有限输入矛盾审计已结束：** 同scope重建A正文SHA `bb56a38882e198de5f92eb30e4ee1adc13459cb690175bfc99280b6c9cd02d32`与实际journal一致；其中明确禁止重复Voice，实际工具Schema也排除voice。冻结分镜把文案/字幕/动作/镜头运动混排，模型逐镜展开并复制整句，不能据此获得改变职责的授权。SQLite只查询复制的DB/WAL/SHM：原会话8事件，唯一工具submit_semantic_plan，无读Skill调用；持久技能目录7073字符/22项，不含Hypit或Voice/MaterialNeed指令。实际systemPromptReport保存长度20165及hash，无全文，故精确系统prompt冲突仍UNKNOWN；通用身份/记忆bootstrap噪音是事实，但没有证据证明其导致这些错误。

**后续决策：** Astra STOP当前真实验证路线，没有已证实的最小生产补丁。本批授权与执行已完成为FAIL，不再以费用确认或模型轮换开启下一批。若继续开发，应在本Task内先提出A任务粒度/程序与模型分工的架构方案，明确如何减少单次互相约束的语义判断、保持完整冻结义务及独立验证、代价/调用上限及旧请求恢复；这是待评审的路线，不是已实施修复，也不能预先承诺成功。Material V1.3、Creator/Director/Hypit职责、required/Rights/Match/Readiness及¥30预算保持。正式自主视频0/3，Goal未完成。

**新批执行授权：** 用户“额度按照推荐的授权，无需再次确认”确认`7b9b15b6…36088`对应的M2.7六例、最多40实际文字HTTP/2700秒、仅原套餐、首FAIL/UNKNOWN封批。授权已持久绑定；启动对账406记录/11旧Owner无未决或活动、Gateway空闲、套餐99%/周97%，固定版本及302现场保持。执行这一批不再重复询问；不重开ec14，不将费用批准解释为放宽语义准入或扩大媒体预算。

**离线最终结果：** M2.7原生A/B/repair/recheck四请求PASS；六例完整冷进程回放6/6 PASS（24本地HTTP/299.32秒），旧@1 M3六例6/6 PASS（24本地HTTP/297.58秒），完成后重入0新发；5项保护PASS（18.58秒），compileall和范围diff PASS。首次测试传错清单造成零调用setup FAIL保留；全树两处无关旧文档EOF空行不改。最终JUnit及具名记录均已归档，Astra最终CONTINUE；本地替身不证明真实语义成功。

**新冻结清单：** `7b9b15b61939883300e74ad3f73149ee9be8d85eb04b3ac915c67322a6336088`，私有目录`qualification-m27-v1`。实际模型HTTP0、六载体已冻结、8份工具源码归档；production source仍`d24bec…9384`。旧ec14仍FAIL/closed/1HTTP，不复用额度。新真实批尚待一次明确授权；同批40HTTP/2700秒，三主题各两次完整Planning，首FAIL/UNKNOWN永久封批，不进入Supply/媒体/Build。授权后先重新对账套餐、未知任务及源码/Runtime/工具/输入，再用以下命令从下标0开始；每例正式合同及独立语义PASS才可进入下一个下标，不自动shell循环。

```bash
.venv/bin/python tests/planning_material_matrix/planning_eval_run.py \
  --qualification-manifest '/Users/xgx/Library/Application Support/Easel/acceptance/autonomous-first-cut-2026-10-08/qualification-m27-v1/manifest.json' \
  --directory '/Users/xgx/Library/Application Support/Easel/acceptance/autonomous-first-cut-2026-10-08/qualification-m27-v1' \
  --fixed-commit df0d3a302ef59c6a5751f44be034fcc82a592f18 \
  --fixed-source d24bec047798d3b1f9a80abc05235f1c02f99504fb864a0a820931faf2fb9384 \
  --one 0
```

完整证据见[候选准备记录](../acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-m27-qualification-prepared.json)。

第0例1实际HTTP/84.333秒后正式FAIL并永久封批，后五例未执行。实际M3参数131072/adaptive，完整tool2229字节但10额外顶层字段、缺五个视觉场景和正式BGM Need；不是length，也不是可局部修复的表示差异。原run已释放，B/repair/Truth及所有素材/制作调用0，工程介入0。原件新增永久fixture，已有结构保护测试扩展后1PASS；生产source`d24bec…9384`及302现场不变。Astra STOP同配置真实重试；不补需求、不移动根item、不扩大repair。[最终证据](../acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-qualification-real-failure.json)。

下一步只离线核验一个有公开契约依据的替代能力，不进行在线模型网格：官方Token Plan说明包含M2.7，实际模型元数据200；M3.1 Flash Preview所查元数据404，暂不选用。官方OpenAPI对非M3模型推荐输出65536、上限204800，M2.7上下文204800，M2.x thinking不能关闭；明确选择`MiniMax-M2.7`、`max_completion_tokens=65536`、`thinking=adaptive`作为隔离候选。参数支持来自官方合同，不能由本地替身成功宣称服务端或语义能力成立。

经Astra只读CONTINUE，仅扩展现有qualification执行器的新版本清单（旧@1保持），冻结该候选与原线上基线分别记录；最终HTTP核模型、参数、纯文本输入及禁止fallback，model进入独立manifest与隔离请求身份。复用实际Gateway、Harness、正式消费者和原冷进程六例集成；补A/B/共享repair/普通Truth以及不支持图像的零提交拒绝。生产配置、Prompt、Schema、Material/Quality视觉模型和业务准入不改。历史失败原件及完整合法对照保留。

离线通过后形成准确新清单、命令和费用/隔离检查，再请求一次新候选批授权；不挪用已封批的剩余40HTTP额度。首次真实候选仍需完整合同与独立语义双PASS，六例均通过才继续原已授权追加开发1件及正式3件。若候选失败停止该批，不能预先声称“换模型已解决”。当前正式0/3，Goal未完成，媒体累计保守占额¥15/¥30。

若候选六例真实通过，正式服务仍须先完成纯文本Planning阶段的具名模型路由、模型身份与恢复回归、Astra复核和已有授权内的安全加载，才创建追加开发作品。隔离候选成功不能自动把线上默认模型整体改成M2.7；已有Material/Quality视觉能力不转移到text-only模型。当前不提前实施该生产切换。

#### 修正版独立批已获授权（2026-10-08）

用户明确回复“授权并且执行目标”，批准清单`ec14e915584da8fbf74dbac31d580396dfaea08605609115e58805c5f185de99`对应的六例固定批，沿用40实际HTTP/2700秒、仅原文字套餐、首失败或UNKNOWN永久关闭。旧批`843fe2b4`保持FAIL/closed/0HTTP；费用范围与后续追加开发1件/正式3件授权不变。本次先实时启动对账，再逐例原Owner执行及独立oracle核查，不恢复旧计分。

#### 冷启动修正已完成，新的固定批次待授权（2026-10-08）

修复后实际分进程六例全部PASS（304.78秒、24本地HTTP），冻库与每个下标均新解释器，包含最终重入0新发；原修复前FAIL/JUnit永久保留。5项保护PASS（16.94秒），纯授权读取可用而generation_budget_preview等禁止入口仍体前拒绝。compileall、范围diff及Astra最终CONTINUE；生产source仍`d24bec…9384`，302保护文件不变，未重启服务或调用真实模型。

新的独立清单为 **`ec14e915584da8fbf74dbac31d580396dfaea08605609115e58805c5f185de99`**，私有目录`qualification-cold-v2`。已零调用冻结六个新隔离载体，只有评测器工具指纹变化；样本、期望、模型131072/adaptive、40HTTP/2700秒、六例完整A/B/Truth、停止点与失败封存规则不变。旧`qualification-candidate`保持0HTTP/FAIL/closed，不移入新账本、不恢复计分。

新批授权后使用下方命令模板的两个路径，将`qualification-candidate`均替换为`qualification-cold-v2`；commit/source和逐例oracle检查不变。当前未获得这个新固定批的授权，不发起真实请求。[软件与前后对照证据](../acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-qualification-cold-start-software.json)。整个视频目标仍未完成，正式0/3；软件结果不能替代模型和真实完整视频验收。

#### 六例批实际失败与最小离线修正（2026-10-08）

本批`843fe2b4…8992e4`第0例实际执行FAIL/closed，0.607秒、实际HTTP0、无agent call、后五例未执行。故障在评测器首次导入`material_generation`，不是模型输出，也没有真实素材操作。原manifest、工具源码、run和空账本永久保留；不重开、不倒算。

因果证据：原六例测试在单一Python进程冻结及执行，使授权模块预热。改为冻结、每次`--one`及完成后重入分别新解释器，原代码在7.68秒精确复现相同`<module>`违规和0HTTP。修复仅在Boundary初始化时先加载已有两个纯授权读取函数，当前模块顶层仅导入/定义/常量，不执行Provider。实际trace禁止条件保持；`generation_budget_preview`仍在函数体前被阻断。此修复不能无条件扩展到有顶层副作用的新模块。

Astra同意该最小评测器修正，要求实际冷进程六例与反向保护完成后重新冻结工具指纹；旧失败保留，新独立批不能沿用关闭的授权。软件回放不证明模型语义能力。

#### 新独立能力批授权（2026-10-08）

用户明确回复“授权 继续执行目标”，批准前述清单`843fe2b4…8992e4`对应的一批六例、最多40实际文字HTTP/2700秒、仅已购套餐、首FAIL永久关闭；六例通过后继续已有追加开发1件与三个正式视频范围，不逐阶段重复询问。旧四格FAIL与账本关闭保持。

启动前一次临时预检工具把凭证SHA经通用脱敏函数写成遮盖值，导致身份比对拒绝，模型调用0；直接内存核对确认实际凭证未变，官方套餐窗口99%/周97%。已保留预检错误并按既有受保护指纹方式写入；生产、执行器和清单均未修改，不认领为真实运行失败或通过。

#### 下一独立 Planning 能力批：实施细节（2026-10-08，离线准备完成、待新批授权）

本节承接 P3/P4，不另建 Task、不重开旧四格。@7已经采用更小的“B显式绑定所选原文”方案；下文较早的opaque目录提案不列为当前待实施项。A目录歧义是否仍导致真实错误，由本批具名结果判断，不能把新增说明当作已证实的语义修复。

**本批目的：** 验证固定候选能否在完整 A→原独立B/共享repair→Truth→正式Planning加载→Supply前切点成立。保留三个主题各两次的六例门槛，不以A合法或单例成功替代。软件链使用原Owner和原合同，测试执行器只在原Supply进口停止；不改正式报告。

| 项目 | 冻结选择与边界 |
|---|---|
| 模型 | 原MiniMax-M3、原套餐凭证绑定；不更换模型、端点或付费回退 |
| 参数 | 隔离model row的maxTokens与请求max_completion_tokens均131072；thinking=adaptive；其余原参数保留。采用官方建议的单一有限候选，不做在线调参网格 |
| 运行保护 | 所有A/B/repair/普通Truth最终HTTP核验模型、thinking及两个token别名；实际不符零提交。真实Provider终态length仍失败，不接纳截断 |
| 样本 | 沿用已冻结的出门物品、阅读笔记、散步准备三个开发主题，分别两次全新隔离载体。第一项来源为真实Preparation原件，其余两项为明确标注的人工派生对照；不是三次真实Preparation验收 |
| 总上限 | 新账本最多40次实际文字HTTP、首占额起2700秒。含所有框架尝试、B分批、共享repair、普通Truth工具循环；不续期、不回收UNKNOWN |
| 时间边界 | 沿用当前生产调用超时、每例最多600秒观察及Proxy现有300秒读取超时；不临时放宽以换取通过。2700秒也包含逐例独立语义核对时间 |
| 计分 | 每例正式合同和独立冻结语义oracle均PASS才能下一例；第六例之前绝不BATCH_COMPLETE。任何失败/未知封批，不使用剩余额度另起重试 |
| 独立语义 | 逐冻结场景检查遗漏、source绑定、required/optional、后期/源职责、重复Voice、必要BGM、无凭据hard及授权。评测记录不回写正式B/Truth，不能替系统放行 |
| 隔离 | 不改线上配置、不重启服务、不创建生产作品、不搜索/采购/生图/TTS/Build；旧Plan/Need/审核报告不复用 |
| 后续 | 六例均真实PASS后才恢复原已授权追加开发1件，再固定同版三个不同主题正式全链验收；既有媒体总额¥30及历史占额继续，不逐阶段另问 |

**实现入口：** 原`tests/planning_material_matrix/planning_eval_run.py`新增`--qualification-manifest`选择同一执行函数。新schema为`planning-qualification-eval@1`、probes为空；六个下标0–5全部为完整Planning。`model_rows/model_params`保存当前线上只读基线，`candidate`保存明确的隔离差异。清单同时绑定HEAD、生产SHA、Runtime、执行器、冻结输入和302份历史现场。不给`--one`只冻结、零请求；给予`--one N`执行一个固定下标。旧contrast/convergence清单和关闭的账本保持原义。

**启动边界：** 本节只准备可审查的新批次；上一四格已因真实终态失败永久关闭，不能把未用格或旧40次额度转授。新批次须有具名范围授权。授权前完成实际原生Gateway离线回放、参数漂移零提交、UNKNOWN不重发、首失败封批、六例计分及Astra冻结复核。软件证据、运行清单与准确命令准备好后只询问这一次新批次授权；不能把软件替身成功写成模型成功。

**实际准备结果：** 完整六例原生Gateway/本地Provider集成PASS，24次本地HTTP、305.82秒；三个主题各两次独立身份，真实Owner/A/B/Truth/持久加载及Supply前切点，重复执行零提交，六例后才关闭。普通Truth及参数/别名漂移、首例语义FAIL不可改分等5项PASS（19.74秒）；候选131072/adaptive下原生A/repair/B/recheck与旧四格回归2项PASS（53.81秒）。compileall、范围diff及Astra最终CONTINUE。生产source保持`d24bec…9384`，302保护文件保持；未重复运行不受影响的全量软件或前端检查。固定外部答案不证明真实语义能力。

新私有目录为`~/Library/Application Support/Easel/acceptance/autonomous-first-cut-2026-10-08/qualification-candidate`；manifest SHA **`843fe2b4a4bd4836b62d333c2c570ecc9fc86198158cad15eac01d3b368992e4`**。已正常冻结六个隔离载体，实际HTTP账本0，未建生产作品、未加载服务、旧批FAIL/closed保持。脱敏[准备记录](../acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-qualification-prepared.json)；JUnit与原生报告保存在同级`qualification-offline`。

授权并完成实时套餐/空闲对账后，唯一运行命令模板为：

```bash
.venv/bin/python tests/planning_material_matrix/planning_eval_run.py \
  --qualification-manifest '/Users/xgx/Library/Application Support/Easel/acceptance/autonomous-first-cut-2026-10-08/qualification-candidate/manifest.json' \
  --directory '/Users/xgx/Library/Application Support/Easel/acceptance/autonomous-first-cut-2026-10-08/qualification-candidate' \
  --fixed-commit df0d3a302ef59c6a5751f44be034fcc82a592f18 \
  --fixed-source d24bec047798d3b1f9a80abc05235f1c02f99504fb864a0a820931faf2fb9384 \
  --one 0
```

仅当前一项正式合同及独立oracle PASS后，依次执行1–5；不把此模板当作允许绕过语义核对的shell循环。启动核对有任何未知请求、套餐不可证、冻结漂移即零新发停止。独立记录使用原`record_convergence_review`入口，不能修正式产物。

本节不承诺131072能解决所有问题。若这一次有界能力批仍失败，保留分类与原件，停止相同配置的真实重试；继续目标须基于新证据及实际可用的套餐能力，不以修改门槛、删除义务或人工救场取得视频验收。

#### 本次执行结论与后续最小修正（2026-10-08，四格批 FAIL/STOP）

整体方案 P0–P5 已先落盘，再实际执行 P1/P2。P1 保护测试5PASS、实际原生四格runner集成1PASS、独立原生参数/捕获4格PASS；Astra冻结前CONTINUE。固定清单 `7960e8f1a8cc8956ebab4f57f599f0e5358f987e1a3b08409ef0750991533b57`、生产source `b04cc840…57353`，线上服务未重启。

| 固定单元 | 原生运行 / 合同 / 独立语义 | 实际结果 |
|---|---|---|
| current / disabled | ok、released，原参数2948字节；额外顶层item及image源时长4.2违反合同；只有一个视觉Need，缺少其余视觉及BGM | OBSERVED_CONTRACT_REJECT，176.165秒 |
| union / disabled | ok、released，5333字节；wire Schema通过，但unresolved使正式消费者拒绝；旁白伪装image、BGM降optional、目录scope错绑，不能靠去掉unresolved放行 | OBSERVED_CONTRACT_REJECT，25.908秒 |
| current / adaptive | HTTP200、Provider length，completion8192、工具参数0；原run error并released | FAIL/STOP，109.161秒 |
| union / adaptive | 因前项终态失败，按冻结规则禁止补格 | NOT_EXECUTED |

共3次真实HTTP；从首个占额到失败记录340.518秒；Provider报告prompt60711/completion17935/total78646 tokens。仅套餐，实际账单UNKNOWN；生产Creation、Supply、生成、TTS、Build均0，媒体新增费用0、正式视频0/3。本批无工程介入，全部原请求已释放、账本永久关闭。四格不是完整执行或产品PASS。302保护文件未变，旧FAIL保持。[脱敏结果](../acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-four-cell-diagnostic.json)。原清单/运行/账本/10份冻结工具源码保留于本机受保护的`four-cell-diagnostic`目录。

##### 根因结论：不能归为单一“模型不准”或“8192”

1. **当前生产模型任务存在语义可靠性缺口。** current输出有真实结构错误；union虽通过wire，仍不满足冻结意图。降低Schema门槛、删Voice或删除unresolved不能修复遗漏/降级。三格只是具名反例，不证明模型永远不能完成。
2. **本次adaptive存在明确输出预算耗尽。** length+8192+无工具参数成立。此前只观察`max_tokens=None`不能推导“没有输出上限”：日志遗漏了新字段。同版本原生离线回放证明实际发送`max_completion_tokens=8192`，但不能冒称原真实payload已补获。官方接口确认thinking计入生成预算，M3推荐131072、上限524288；这是接口能力，不证明当前任务所需预算或套餐余额。
3. **模型侧来源目录存在系统性表达歧义。** source_catalog把27个非空行复制成scene/segment/event共81个编号，另加global；真实稿是六个分镜。cell1把scene-1…6理解为六镜，而当前消费者绑定到六行。机械ID存在不能证明语义绑定正确。B仍逐原行+global检查，不能为了减少题目删除义务。
4. **诊断遗漏新参数别名，已经离线修正。** 同时记录两个token字段的存在性/类型/值，拒绝冲突、类型错误与冻结值漂移；未重新写旧日志。现有测试扩展后5PASS，实际原生runner集成1PASS，验证发送并记录8192；本次新增真实模型调用0。`reasoning_delta_bytes=0`也仅说明专用字段计数为0，官方允许M3把think放在content，不证明没有推理。

##### P3 最小实施定案：B 原文绑定 @7（离线实现完成）

有限四例样例已显示实际信息增益：当前 B visual_choices 只有 scope 字符串，而新输入可直接看到所选原文；错绑 scene-2 指向开场，正确 scene-7 指向钥匙托盘，scene-6 标题可结合完整正文审核，global 不伪造局部范围。81旧别名逐字节绑定，28 coverage题及完整evidence保持。该样例只证明信息保真，不是模型判断PASS。

Astra前置CONTINUE后将此前“重设计A目录”收窄为**仅新B输入补来源绑定**：A Schema/目录及Material scope语义均保持；新journal/checkpoint@7与transport `literal-scope-review@1`选择策略，@6及更早保持原路径，未知组合拒绝。每个visual_choices/complete_obligation增加程序从冻结目录派生的kind、handle、原文、UTF-8位置、行号及文档SHA；完整上下文和coverage不变。不能以全文别处的相似内容替错绑背书，也不能机械拒绝标题/跨行来源。复用原B、题目签名、recheck、repair及verify；verify重新派生，不相信保存hash。没有新增Gate或调用额度。

验收复用既有runtime/Owner连续集成：@7绑定与篡改拒绝、旧@6问题/消息/请求和恢复保持、局部修复重审、不增加额度；固定B响应只作为外部替身，不认领真实模型语义通过。另已原生离线证明：只把请求设32768但model row仍8192会夹紧为8192，两者都32768才实际发送32768；32K只是有限配置对照，不是已选真实预算或线上改动。真实批保持关闭。

##### 最终软件核验（固定版，2026-10-08）

@7已实现；global通过`evidence_id=0/document_path=SCENES.md`引用批内完整原文，附文档SHA和整篇UTF-8区间，不在每题重复全文；构造及verify重派生并核对冻结catalog。长文22.5万字节＋8条global条件仍完整通过请求容量检查，新增开销小于12KB。旁白旧合法scope未新增限制，A、Material合同和供料策略未改。

最终工作树source `d24bec047798d3b1f9a80abc05235f1c02f99504fb864a0a820931faf2fb9384`，HEAD仍`df0d3a30`、未提交、未加载。run-051 **269PASS**，常规最终 **1019PASS/5既有skip/2弃用warning**，115技能/compileall/范围diff通过；302正式文件、135fixture、生产及执行器前后指纹一致。全量JUnit与来源配置/原生证据永久保存于本机`source-bound-software`目录。run-050虽测试269PASS，但检查过程中落实global容量修订导致源码/测试工具指纹变化，故保留为中间无效验收；其现场与fixture保持，不替换最终run-051。

Astra最终CONTINUE，未新增代码修改要求；同source原生最终两项已PASS（33.20秒），见[软件摘要](../acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-source-binding-software.json)。软件修复解决参数观测遗漏和B缺少明确选中原文信息，不解决或伪造真实模型的合同/语义判断。原真实批3HTTP/FAIL/closed不变，套餐复查窗口99%/周97%，实际现金账单UNKNOWN，新增媒体费用0。后续真实验证仍必须是新固定批，不能补本轮第四格。

##### 下一项可执行方案与准入条件

**先完成两个离线决策，不继续真实试错：**

- **输出配置：** 以官方`max_completion_tokens`为真实出口核验字段；候选预算必须显式给出有限值，同时与模型目录及每次调用参数一致。先用原生Gateway的本机Provider验证参数完整到达、旧配置不变、length继续拒绝、重启不重发。不得把模型推荐128K自动当成费用授权或把增大预算当成业务修复。新真实验证必须使用新冻结清单，不能复用本失败批。
- **来源目录：** 对新执行提出具名版本化producer映射：以冻结字节中的客观文本单元作为单一目录，使用不暗示分镜序号的opaque source handle；程序保留原文、顺序、来源hash和正式映射。不得通过词面猜测分镜、合并义务、改冻结原文。先查producer/consumer/缓存/恢复，明确旧版本及pending原义不变；跨模块最小实现须Astra前置复核。若无法无损表达合法范围，明确合同缺口而非上线。

两个离线结论共同确定下一候选；不默认采用union、不更换模型或套餐、不提高repair额度。下一个真实批次须具名限定参数/调用量/时间/终止条件；先完整A→独立B→Truth及语义保真，才恢复原追加开发1件和正式3件。任何真实批内工程修改仍记FAIL并封存。

官方依据（2026-10-08实读）：[OpenAI兼容接口](https://platform.minimaxi.com/docs/api-reference/text-openai-api.md)、[正式OpenAPI](https://platform.minimaxi.com/docs/api-reference/text/api/openapi-chat-openai.json)。本机保留原文及SHA；OpenClaw实际发送对照位于`token-payload-offline/result.json`。Astra本次后续意见CONTINUE仅离线调查及诊断修正，不授权新真实调用。

最终目标未完成；尚不能宣称Planning恢复、MATERIAL_READY或稳定出片。P3/P4/P5不被测试替身或文字诊断代替。

#### 本次整体方案与实施细节（用户确认后连续执行，2026-10-08）

用户先明确授权固定四组诊断，随后要求“先整体梳理给出方案，然后确定实施细节，写出文档，然后执行”。本节是本次统一执行入口；后文“待授权”的历史表述不再否定已授权的四格诊断。最终目标仍是正常入口、同一 Delivery、零工程救场的三个独立自主视频，不以四次调用、文档完成或软件测试数量替代。

**当前基线：** 生产工作树 source `b04cc840189874cdd5d9e29b103af24cd1737948bc53de287866fee76b857353`，HEAD `df0d3a302ef59c6a5751f44be034fcc82a592f18`，分支 `easel-studio`。HEAD 尚未包含工作树全部改动。隔离候选 Runtime `0759643a…4d7e6`；在线 Web/Gateway 仍是旧版本，不能冒认已加载候选。三件旧开发 FAIL、上一诊断批首项 FAIL、正式0/3保留。本次开始时模型调用0、无新生产作品。

**根因分层：** 最近一次的直接原因是模型返回了完整但不合法的业务参数；transport 无损不等于业务正确。程序已经收回 ID/路径/hash 等确定性职责，当前瓶颈是模型能否正确选择语义及遵守其输出合同。Schema 复杂度、推理关闭、模型本身能力都是待区分因素；不能统一把历史所有失败归因于某一个字段，也不能预先认定重写 Schema 就会解决。

| 顺序 | 实施内容 | 产物及必须达到的状态 |
|---|---|---|
| P0 整理与冻结 | 本节方案、授权/费用/历史现场对账；收尾被打断的测试执行器修改 | 明确原件、新实验、生产三者位置；无遗留本轮请求；修改只在测试代码/文档 |
| P1 执行器保护 | 复用原 runner、Budget、Proxy、Gateway；每格一次、总4/900秒、最终payload核验、完整终态分类；原生离线集成 | 第5次/同格重发/未知后新发/身份更换/参数漂移被阻断，disabled/adaptive确实经原生栈发送；不靠mock内部模块冒认 |
| P2 固定四格真实诊断 | 同冻结输入，current/union × disabled/adaptive；每格新诊断身份；无repair | 保存原run、Schema/输入SHA、完整参数SHA、逐格transport/contract/语义评测结果；业务拒绝可继续预定单元，其他异常整批停止 |
| P3 证据决定最小方案 | 根据P2具名观察及历史证据，确定配置修正、producer适配或模型能力选型中的一条；跨模块变化先Astra | 明确可解决的缺陷与仍未知项；无证据不改生产、不默认上线union；软件实现后真实内部链及既有保护回归 |
| P4 Planning能力验证 | 候选版本固定后，按原完整A/B/Truth及Supply前切点验证多主题语义保真 | 成立的是正式合同与独立语义，不只是A JSON；新真实批另有固定清单/边界，不重开已封存批。当前四格授权不是无限评测额度 |
| P5 完整开发与正式验收 | 原已授权追加开发1件→同固定版本三个主题正式作品；正常入口、同一Delivery继续到Hypit/Quality | 每件可播放MP4、required100%、正式Rights/Match/Readiness、输出SHA绑定Quality、工程介入0；不得发布 |

实施按表推进，前一步证据不成立不能跨过。P2只是探索性对照：每格一次不能证明因果、普遍失败或稳定率；通过只形成候选线索。若四组均无可用样本，封存并停止调Prompt/参数的真实试错，后续只做套餐内替代能力调查与具体接入设计；没有满足授权费用条件的能力时报告真正阻断，不假称全链完成。

##### 已确定的代码与运行细节

- **唯一入口：** `tests/planning_material_matrix/planning_eval_run.py --contrast-manifest <冻结清单> --directory <新私有目录>`；不带 `--one` 仅创建4个隔离测试载体，不发送模型请求。`--one 0..3` 各执行一次预定单元。production Creation 数始终为0，不能把隔离载体列为开发或正式出片。
- **批次身份：** 新 manifest SHA 绑定生产source、HEAD、候选Runtime、模型配置、旧冻结输入原字节、两份Schema、工具源码与完整四格清单。旧账本只读保留。每次发送前重新校验指纹，任何漂移停止，不能更新清单后续跑。
- **两种表示：** current 使用既有 FrameProjection；union 使用仅实验用 ProducerUnionExperiment。二者解码后都通过原 canonical / SemanticProposal / catalog 校验。Condition原三字段、局部repair粒度及正式Material语义保持；实验没有repair调用。
- **任务一致性：** 创作任务、冻结来源、语义义务一致；union只同步工具Schema、transport摘要与必要机械输出说明，记录完整差异。不能混用旧内嵌Schema或把新语义要求藏进说明。
- **参数变量：** 原 `MiniMax-M3`、同API/工具/采样设置、`reasoning=False` model row及其他参数保持；仅隔离模型参数 `extra_body.thinking.type` 按单元设为 `disabled`/`adaptive`。不写线上配置。最终HTTP必须核到预定thinking与Schema；payload存在adaptive只证明参数发送，不证明模型实际进行了推理，另记录响应reasoning的安全计数（如可得）。
- **发送保护：** EvalHttpBudget已有 `limit`/`seconds` 参数，本批4/900进入持久身份。每格通过预定请求序号在同一文件锁内占额，换session/重启/框架重试均不能刷新。最终Proxy只允许原模型、原唯一tool、原tool_choice、关闭parallel、原Schema和预定thinking；UNKNOWN不释放。
- **结果分类：** 只有原native run `ok`、`released`、完整v3捕获及身份核验成立，才分类为 OBSERVED_CONTRACT_ACCEPT/REJECT。JSON不完整、终态失败、参数错配、费用不可证、超时或未释放等记整批FAIL/STOP；拒绝原件保留，不清洗成合法结果。
- **零副作用：** 本批不调用Owner自动推进，不搜索/采购/生成/TTS/Build，不写正式报告。语义核查为独立诊断记录，不能转作正式B/Truth/Quality。
- **费用：** 本诊断仅已有文字套餐，现金/余额/超额/付费回退禁止；提交前官方额度与同凭证绑定核验。媒体本Goal累计¥30不变，历史保守占额¥15，已授权追加开发¥3与正式各¥4保持。失败/UNKNOWN不回收占额，不因“必须全部跑通”扩权。
- **验证范围：** 先运行受影响测试与真实原生Gateway离线集成，补每格身份与截止线的高风险场景；生产未变不重复全量pytest/前端build。若P3改生产，再按变更范围完成实际内部集成、必要项目检查及冻结前Astra。
- **服务加载：** P2只启动隔离Gateway，不动线上服务。进入P5前准确备份实际raw-stream及全部现场、核当前无unknown/pending/submitting/活动旧任务，核准固定source及Runtime，再按已有授权加载并验证真实进程。

##### 最终交付与完成判断

同一Task与Current State记录：执行清单/指纹、JUnit、逐格原件与分类、根因/未知项、最终选择及最小差异、真实Planning与视频验收记录、费用和未覆盖义务。测试替身MP4仍只算软件证据。若尚无三个具名自主视频，Goal不得COMPLETE；必要时如实保留FAIL并说明缺少哪一项能力或授权，不能把“代码已改完”写成“问题已解决”。

本节方案与细节已先落盘；随后才执行P1验证/P2实测。Astra已允许有限执行器实施，启动前仍须根据实际离线证据复核，避免把设计意见当成测试结果。


**收敛方案执行授权（2026-10-08，本次最新）：** 用户要求“设定完整目标一次性执行完毕，这次必须完成，你要想尽一切办法”，确认下述经源码复核修订的完整范围：两个离线交付物→一批最多40次实际文字HTTP/45分钟的4探针及6例Planning评测→最多追加1件完整开发→同固定版本3个不同主题正式自主视频验收。原3件开发FAIL、正式0/3与全部费用/现场保留，不用正式名额探索故障。媒体历史保守占额¥15，新增开发¥3、正式各¥4，总额仍¥30；文字只用已购套餐，禁止现金/积分/超额/付费回退，Hypit仅核实免费本地构建，不发布。此次是一次完整授权，必要修复、隔离验证、固定与安全加载不再逐阶段询问；批次内冻结，失败永久关闭该真实批次，同根因累计停止规则保持。必要替代接入须有证据、先复核，不能放宽业务准入或预算。当前开始离线实施，尚无本轮新增真实调用或作品。

**本轮实施结果：软件成果完成，真实批A首项FAIL/STOP，Goal未完成。** run-049269PASS、常规1013PASS/5既有skip、HTTP/Authoring22PASS、原生Gateway9PASS、实际本地免费Hypit MP4软件场景PASS；Astra启动前CONTINUE。Node空格路径零提交预检原件保留，测试工具file URI修复及空格路径原生验证PASS后新冻结v2。授权真实正常A采用开发3原冻结语义输入，source b04cc840…857353/Runtime0759643a…4d7e6，163.506秒、1 HTTP、0重发、原run ok/released、完整参数13987字节。返回含禁止的6 Voice、82处非法meaning=allowed及声音字段混用，完整Schema拒绝，工程介入0；Astra STOP。本批其余9项未执行并永久关闭，新增开发/正式三个视频均未启动。不借未用调用额续跑第二批，不删除Voice/默改meaning/扩repair。已完成有限公开parser归因，合法对照未产生这些具体异常，尚无经证实的最小生产修复。302现场/133历史fixture/193开发原件精确保持，新负例2fixture永久保留，针对结构保护3PASS。媒体占额仍¥15/¥30，新媒体费用0；文字26283 reported tokens/实际账单未知。详情与后续有证据的替代接入要求见Current State；“稳定自主出片”不得标COMPLETE。

**2026-10-08 最新统一执行授权：** 用户明确允许必要修复、固定版本、现场备份、服务加载及正常新作品的 Planning/Material/Authoring/免费本地 Hypit Build/Quality。旧两轮 Development 上限不再作为本Goal阶段审批条件，旧FAIL/账本原件不动。此次新开发作品最多3个，打通后同一固定版本另起3个不同主题正式验收；工程介入立即封存该作品FAIL，同根因两次针对修复仍失败则停止真实重试。累计¥30图片/预置旁白、文字仅套餐、Build仅核实免费、不发布。不逐阶段审批。被打断的一次Planning-only追加执行器修改已原样归档并撤回，不将它扩为另一条主链；继续使用正常Web入口与现有Delivery Owner。

本节是当前执行范围。用户要求实施并验证稳定出片，无需人工救场；后文旧软件批次的“不启动真实制作”限制保留为历史范围，不限制本节已授权的新作品验证。沿用本 Task、唯一 Delivery Owner 和既有矩阵；Planning vNext Task 继续保存该子阶段的合同及历史失败。

**完成条件：** 同一固定代码与 Runtime 版本，至少三个不同正常主题的全新 Creation 连续自主到达 `first_cut_ready`，各有真实可播放 MP4、实际输出 SHA 绑定的系统 Quality、100% required coverage、成立的 Rights/Match/Readiness，固定运行期间工程介入为零。三个内容是最低重复性证据，不能声称任意主题均稳定。Creator 最终选择、人工接受和发布不属于自动验收终点。

用户预算：本 Goal 图片和预置旁白**累计最多 ¥30**，失败消耗也计入；文字仅使用已购套餐，禁止现金/API余额/超额计费/付费回退。旧作品预算不转授，不增加 AI 视频或付费音乐授权。各新 Creation 按当时剩余额度正常绑定授权，提交前核对整个 Goal 的已用与在途占额。Hypit 仅在原 pricing 合同证明全部 resolved/local/noCharge 时按已有委托执行免费 Build；收费请求停止在原费用门。

执行顺序与停止条件：

1. 修复已证实的 Planning carrier 接入缺口；先完成下述设计复核、隔离 Runtime 软件验证、原矩阵和相关完整回归，再固定软件与 Runtime 指纹。
2. 真实 Planning Development 先验证完整工具结果及独立语义，再由新 Creation 的正式 Owner 到达 Material Supply/Observation，验证 required 素材正式准入。软件通过不能替代这些真实结果。
3. 沿同一 Owner 继续 Authoring→Hypit→导出→Quality；优先复用现有跨内容集成与有界恢复。只修实际阻塞，禁止顺手重构 Provider、Material Domain 或另建执行主链。
4. 开发通过后另起三个独立正式作品，固定版本连续验收。某作品需工程修改/手工素材/证据/结论补写即封存 FAIL，离线修复后用新固定版、新作品重新验收，旧 FAIL 永不重计。
5. 同根因两次针对性修复仍失败时返回离线证据及 Astra 复核；禁止无限实际模型试错。每轮调用、耗时、共享 repair 和费用累计账本均保留；UNKNOWN 只核对原请求，不新发。

#### 完整开发3 FAIL 与真实重试停止（2026-10-08）

第三个正常入口新作品 `cr_645dc02aa63a49b785753916e9d028c4` / `fa_fcda420330b2c182c5c360b51b6b257c` 在最终联合版本source e2451702…85da52、Runtime12b0d561…6c19c5上运行。确认至失败385.548秒；Preparation209.610秒成功，A162.291秒后原生结构化终态拒绝。A只提交一次，三次框架尝试及三次本地重入没有重发；两原run已终态并释放，B/repair/Truth/Supply/媒体/Authoring/Build/Quality均0、工程介入0。Preparation会话16个assistant响应、22个工具调用，真实HTTP计数/usage/账单未知。原件、精确原始流、durable guard、会话及25条持久轨迹已私有封存；287旧现场、34个旧失败Attempt文件、132个既有fixture和生产source保持，仅正常新Creation会话绑定追加。费用保守占额¥15/¥30，实际媒体费用0。

明确停止：开发3/3全部FAIL，正式验收0/3，MP4零。没有第四个开发作品授权，不用正式名额进行故障探索。当前无unknown/pending/submitting，Gateway active/lost/audit0；不恢复或重计三件FAIL。

首个真实错误为`STRUCTURED_TERMINAL_REJECTED`，最终会话被后续框架尝试覆盖为`STRUCTURED_EXECUTION_FAILED`。保护层未持久保留原provider finish reason、native stop reason或工具调用形态，无法从现有证据确认“无工具调用/截断/终态转换”中的具体分支。8192是当前配置输出参数，不是本次已证实的截断原因；不得为通过而扩大容量或接受无完整终态。此问题不证明原子画幅/Voice修复失效，也不能把笼统的“Planning又失败”当作已证实的同一根因。[具名失败记录](../acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-full-development3-failure.json)。

下一步仅离线：前置Astra复核最小拒绝诊断设计，在唯一carrier保留与原run/session/schema关联的封闭安全元数据及首个拒绝分类；不保存未经安全校验的文本/arguments，不改ACCEPT条件、repair额度、请求身份或状态机。复用原生transport与Gateway集成证明拒绝详情在重试/重启后仍可追溯、只一次Provider提交，合法结果不变，秘密内容不落盘。软件通过也不能反算开发3或宣称完整视频通过；新真实作品仍需明确增加开发额度。

离线诊断收尾：Astra前置及最终CONTINUE。`easel-structured-rejection@1`在candidateEvidence抛出前保存已核验scope身份与封闭终态值、消息/参数形态、调用数量、预期工具/ID存在布尔及字符串字节数；不保存工具名/ID/正文/arguments自由值。私有目录和文件校验、完整临时写/fsync后hardlink不可覆盖发布；残缺或写失败为诊断不可用，原拒绝不变，后错/并发不能替换首错或改RESERVED。接受谓词、repair额度和生产状态流均未改。当前只修复诊断可用性，不能宣称真实Planning blocker解决。

相关58项pytest、11个实际原生transport场景、3个隔离Gateway拒绝场景及A/B/共享repair→persist/verify连续集成通过；115skills、compileall、Node语法与范围diff通过，未为报告重跑全量。原生length会丢弃unfinished tool，较早SDK容量错误还未到完整候选，二者不能重建原arguments；两个初始测试期望FAIL及/tmp路径别名预检FAIL均保留。候选source `ba3426f0…79f6a2`、Runtime `0759643a…4d7e6`；原helper `b1d10de4…990036`白名单与隔离原件备份保持。新补丁只在隔离安装验证，当前生产Runtime仍为 `12b0d561…6c19c5`，没有加载、重启、真实调用或第四个作品。287旧现场、34个旧FAIL文件、132既有fixture与46个开发3封存文件保持，仅新增真实终态metadata fixture。[诊断软件记录](../acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-rejection-diagnostics-software.json)。

#### 当前根因与可执行收敛方案：先判定 Planning 接入能力（2026-10-08）

**目标保持三个全新主题自主出片；本轮完成的是根因调查与有判别力的离线实验，不认领修复成功。** 用户要求参考网上解决方案并执行。Main 已检查实际 A 原件、完整合同、原请求终态、当前 producer/consumer、公开 parser，并查阅三份一手资料。没有把此前各轮不同失败统一倒算为同一原因。

##### 已确认原因与仍需验证的假设

| 层次 | 证据与判断 | 对策 |
|---|---|---|
| 本次直接失败 | 完整 A 的 6 个 Voice、82 个非法 meaning 及音频字段混用违反当前合同；tool_calls/toolUse/原 run 成功不等于参数合法 | 保留原件和拒绝；不删 Voice、不猜 meaning、不扩大 repair |
| 当前系统瓶颈 | ID/路径/hash/sidecar 已由程序派生，但模态选择、义务强度、责任与动作意义仍需要语义判断；现用模型接入未证明能可靠完成这个任务 | 对实际模型能力做有限对照，不能继续重复建设已有编译器 |
| 验证方法缺口 | 离线集成能证明“合法响应可进入下游、非法响应会拦截”，不能证明真实模型经常产生合法且保真的响应 | 软件安全、模型合同合法性、独立语义保真、完整 E2E 分别计分 |
| Schema 复杂度 | 当前 Need 共享跨模态字段与 allOf 条件；可能增加模型负担，但没有对照证明它是唯一或主要原因 | 先测候选表示的安全性，再按同输入同模型对照，不先上线 |
| 推理参数 | 现实际配置关闭 thinking；官方允许关闭，也支持 adaptive。复杂语义任务是否受影响尚未知 | 作为独立变量；不把“开推理”当成已经验证的补丁 |
| 历史开发3终态 | 原 Provider 内容/终态缺失，具体原因仍 UNKNOWN | 维持历史 UNKNOWN，新的成功或失败均不能反推旧原因 |

**不能把全部问题归因于“集成测试数量不足”。** 当前回归确实保护了拒绝错误和内部流转；缺的是实际接入的任务能力证据。增加几百个同类 fixture、放宽 Schema 或安装输出框架，都不能代替该证据。

##### 网上方案核对与采用边界

检索日期 2026-10-08；GitHub commit API 命中速率限制，记录页面 URL/访问日期，不伪造 commit pin。

- [MiniMax 官方 Provider Verifier §09](https://github.com/MiniMax-AI/MiniMax-Provider-Verifier/blob/main/m3_format_check/docs/m3_text_cases.md)：当前将 M3 的 `response_format=json_object` 测试标为不支持。该证据不等于穷尽所有接口，但不足以把客户端 `strict:true` 当成已获服务端强制保证。当前实际返回违约也直接说明该运行没有满足业务 Schema 的保证。
- [MiniMax 官方 OpenAI 兼容接口](https://platform.minimax.io/docs/api-reference/text-openai-api)：M3 支持 adaptive/disabled；这是允许配置的事实，不是开启推理必然提升本任务质量的证据。
- [Pydantic AI 官方 Output](https://pydantic.dev/docs/ai/core-concepts/output/)：多个输出类型可以注册成独立工具来降低单工具复杂度。借鉴“缩小模型填写界面、业务校验独立”的思想；单工具 union 并不等于它的多工具实现，不能借其名义宣称成功。不新增框架或多个生产工具生命周期。
- [SGLang 官方 Structured Outputs](https://docs.sglang.io/docs/advanced_features/structured_outputs)：JSON/语法约束由推理服务实现，提供 XGrammar 等后端。客户端 Pydantic/JSON Schema 校验无法为远端接口补上受约束解码。当前没有核实可用的本地硬件、订阅路由或费用，故不擅自部署大模型或切付费 API。

##### 已执行：有限离线表示实验

复用现有测试入口和公开模板/parser。实验代码仅在 `tests/planning_material_matrix/producer_experiment.py`，生产和真实 Eval 均不引用它，没有新版本默认切换。

1. 初始实验将 Condition 合为 12 种 semantic_kind，101 个合法分支对照通过。但未知标签会改变原三字段的局部 repair 可定位范围；Main 按 Astra 复核将其排除生产候选，不用一次原型 PASS 覆盖合同变化。
2. 最终候选保留原 Condition 三字段，只按 image/video/voice/bgm/sfx 提供各自字段；program-owned Voice 时没有 Voice 分支。规范化等价以当前完整 canonical + Pydantic 合法集合为准，先验证再省略确定缺省值，绝不从非法输入删除字段。
3. 已实际执行 **135 项有限检查 PASS**：合法模态/条件组合、混合列表、顺序和重复项、Unicode、null/缺省/字符串 null、跨模态污染、目录外 scope、漏 required source、现有 meaning 单叶修复及历史完整 A 继续拒绝。公开 parser 回放只证明该公开实现，不证明线上 parser 版本相同；有限样本不是对无限文本空间的数学证明。
4. Schema 总体并未缩小：小目录对照无程序 Voice 时 8432→12326 字节，有程序 Voice 时 8424→10474 字节。它减少单分支无关字段，却增加完整 Schema 大小。因此**没有足够证据将 union 默认上线，更不能声称模型成功率提升**。
5. 实验报告、逐行 Expected/Actual、JUnit 存于 [producer-union-experiment.json](../acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/producer-union-experiment.json) 与同目录 XML。原始 semantic_kind 原型仅留在本机 `/tmp/easel-typed-producer-audit/` 供审计，未成为生产或正式 fixture。

Astra 前置结论 MODIFY，生产候选复核 STOP 的对象是“未经模型收益证据就接入生产”，不是禁止继续调查。Main 采纳：本轮不修改生产合同/Prompt、无服务重启、无真实调用。生产 source 仍 `b04cc840189874cdd5d9e29b103af24cd1737948bc53de287866fee76b857353`；302 正式文件、133 原 fixture、193 旧开发记录逐字节核对保持。

##### 唯一建议的下一步：固定四组能力对照，随后一次决定路线

这是**待新批次授权、待补齐执行器边界验证的诊断实验**，不是已启动的 E2E，也不是重新打开上一失败批次。已向用户询问一次批次授权；不能将未答复当同意。整批最多 **4 次实际文字 HTTP / 从首请求起15分钟**，仅已购套餐，现金/余额/超额/付费回退禁止。生产新作品、素材搜索/生成、TTS、Build、发布均为0。时间上限到达仅核对在途，不补发或释放占额。

| 固定单元 | Producer Schema | 推理配置 |
|---|---|---|
| 1 | 当前实际合同 | disabled |
| 2 | 保留 Condition 的模态 union 实验合同 | disabled |
| 3 | 当前实际合同 | adaptive |
| 4 | 同一 union 实验合同 | adaptive |

- 四组使用同一开发3冻结输入原字节、同一模型/原生 Runtime、工具、采样参数及相同容量条件。创作任务、冻结来源与语义义务一致；只有所选 Schema 必然关联的机械输出说明、内嵌 Schema 及其身份摘要允许同步变化，并逐项记录差异。不得同时发送旧形状说明和新工具合同。每组新请求身份；预先冻结两份 Schema、解码器、输入、固定义务判据及变量矩阵。actual payload 必须证明变量确实发送；不从配置名称推断。
- 复用既有 EvalHttpBudget/ProviderProxy/Gateway/捕获/配额检查。实施时需让预算身份承载4/900的更小边界，在最终 HTTP 出口验证实际 Schema 与 thinking；离线证明第5次不发送、重启不清零、未知不重发、时间不刷新。原40/2700封存账本保持。
- 此阶段只测 A 生成能力。每组仅一原请求，**无 repair/重试/修改 Prompt**。结果分为完整有效合同、完整但合同拒绝、transport/费用/隔离异常；不触发 Delivery，不人工补正式证据。合同拒绝是预期实验观察，可以继续预先冻结的其他单元；任何费用、隔离、未知终态或参数偏离立即停整批。这一与正式批“首个业务 FAIL 即停”的差异必须在新批授权中明确，不能暗中改旧停止规则。
- 独立冻结语义判据核对 required 义务、软硬等级、来源归属、程序 Voice、声音与视觉职责；这是**评测记录**，不是正式 B/Truth 或产品报告。结构合法但语义错误仍不算可用。每格仅一例，只提供具名样本的探索性证据；模型随机性可能解释差异，不能从一次失败认定整条路线普遍不可用，也不能据一次成功确认因果改善或稳定率。
- 四组均未出现可用的具名样本：封存实验，停止继续修改当前候选/参数；这不证明模型普遍不可用，但本轮没有取得继续投入该候选的依据。下一项可评审方向为 Planning 模型能力选型。先核实套餐内替代能力；没有合格套餐路线则明确提出新的模型/费用选择，由用户决定，不能绕过仅套餐限制。
- 通过的具名样本只让其路线获得进入后续复核的候选资格，不自动实施或取得下一批授权。后续复核须明确需要的重复/留出证据，才能决定最小配置/接入实现及完整内部集成。union 最终获选才做新 producer 版本与旧 @6/pending 恢复隔离；若仅推理配置获选，不实施 union。不得为了“已经写了实验代码”强行上线。
- 随后仍需原约定的多主题 A→独立B→Truth→允许 Supply 的真实 Planning Eval，才到新增完整开发与三个正式自主视频。四格实验通过本身不授予 MATERIAL_READY、出片或稳定性结论。

末次文档复核的两项 MODIFY 已落实：Schema 相关机械文字同步且记录差异；每格一次只作探索性证据，不作因果或普遍失败判断。

这条路线把下一次真实调用限定为**为接入选择提供证据的对照实验**，避免继续用全链 E2E 探索字段错误。不能承诺四次就能让模型合格，但可以保证本轮不会无期限改代码再重跑。

#### 收敛方案：真实接入能力先闭合，再回到完整自主视频（2026-10-08，待实施）

本节回应用户“推进困难，需要切实可行方案”。本轮只调查、制定方案和只读复核；不修改生产代码、不加载服务、不调用真实模型、不新增作品。原稳定自主出片 Goal 未完成且保持 BLOCKED，三个开发 FAIL、费用及现场原件保持。本方案不能自动追加真实执行额度。

上述“本轮仅调查/BLOCKED/待授权”为方案制定时点。用户随后已确认完整执行，当前按本Task顶部的新授权进入离线实施，不抹除此前状态或失败。

**源码可行性复核更新：方向可行，现有执行器尚不能原样执行本方案。** 用户追加要求核实实际可行性后，Main与Astra只读核对确认以下缺口。此前方案CONTINUE仅认可约束，不是现成能力证明；本次复核为MODIFY，以下修订和两个离线交付物是启动前置条件。

| 承诺与现有实现的差距 | 具体源码证据 | 必须完成的最小修正 |
|---|---|---|
| 40次HTTP上限尚不存在 | `planning_eval.py::trace`只在Python `_rpc(agent)`观察；`planning_eval_run.py::reserve_development_request`按phase计数；Runtime `reserveSubmission`只在`easelStructuredResult`请求启用 | 在隔离Runtime的共同最后发送边界实现本批所有文字HTTP原子计数；覆盖Truth/框架续轮/报告修复，保留原structured单次身份守卫 |
| 原runner不是冻结Preparation直接评测 | `planning_eval_run.py::main`先`confirm_sample`建立隔离Creation，再从`prepare`推进；`planning_eval.py::isolated_process`也明确路由隔离存储 | 在同一runner增加具名冻结Preparation回放模式，隔离Creation/Attempt如实标为测试载体；不操作生产作品，不启动真实Preparation |
| 既有三主题测试不覆盖最新合同到真实渲染 | `test_creator_content_replay.py::test_same_creator_mode_three_contents_reach_reviewable_first_cut`直接写旧MaterialPlan；真实Hypit仅可选check，视频由ffmpeg合成后交给RendererFixture | 扩展已有连续场景，以proposal@3/vNext@6及程序Voice通过实际Owner、Gate与真实本地Hypit工程构建，再核输出绑定Quality |

**最近两个离线交付物：** ① 可执行的隔离评测入口：冻结Preparation回放、共同HTTP/时间守卫、安全的早期终态诊断，具名证明无绕过、无旧身份冒认；② 一个新版合同经真实内部模块到实际本地Hypit MP4和输出绑定Quality的连续场景，外部模型/媒体调用仍为固定响应。沿用现有文件与执行器，不新建平台。二者完成前不启动40次文字批次，也不再把1012个已有PASS视为这两个新缺口已经通过。

回放模式只能复制经过核验的冻结输入，并保存原出处/原字节hash/新测试身份映射；不得复制旧成功状态、Plan、审核报告或Gate冒充本次执行。若来源与新身份无法合法衔接，明确记录该离线缺口，不能默认改成真实Preparation、扩大调用数或手写正式产物。该评测不验证新主题的实时Preparation，真实正常入口仍由后续完整开发作品验证。

**判断：** 当前明确的工程问题是验证层次脱节：离线证明了“替身返回指定结果时能够运输、校验和恢复”，却未证明实际模型能在实际 Schema 和输出预算下稳定产生该结果。三个完整开发作品又都在 Planning 停止，未获得 Material 或视频证据。继续增加通用测试数量或再重复建设已经实施的确定性编译器，不能闭合这个缺口。第三次具体根因仍 UNKNOWN，不能提前认定为截断、模型不支持工具或 OpenClaw 错误。

**唯一目标仍是正常新作品自主成片。** 调整验证方法，不改 Creator/Director 决策、独立 B/Truth 复核、Material V1.3、唯一 Delivery/Hypit 主链、required/Rights/Match/Readiness 或预算。复用本 Task、现有执行器、矩阵及故障 fixture，不再启动一轮漫长 R4，也不建立第二个生产协议或工作流。

##### 1. 先闭合实际接入与容量证据（离线）

Owner 对当前源码、安装版 OpenClaw、实际 payload 和官方模型合同形成一张可核查的对照表：实际模型/订阅权益、API、thinking、max_tokens、工具选择、完整 wire Schema、Provider 终态→SDK 终态映射、原始参数捕获/持久化/恢复、重试与费用身份。已有 MiniMax 迁移文档是待实施方案，不证明当前账户已具备新模型权益，也不证明旧 M3 不可用；不默认升级 OpenClaw 或换模型。

容量分开记录：当前配置输出 8192、实际发送值和可核实 usage；结果载体8MiB；请求1MiB；转义/会话开销。这些数值互不等价。合法 SemanticProposal 上限16个Need、每Need12个条件、每条件2000字符，已经说明“传输能容纳”不等于“单次模型能生成”；需测量正常样本、较大合法样本和 A/B/repair 各自预算，而非把上下文1M或载体8MiB当输出能力。

补齐诊断断点：现有补丁只记录 SDK 完整消息；在必要的最早 Provider/SDK 边界保留封闭终态枚举、请求参数与 Schema 摘要、分片/参数字节计数和生命周期阶段，并与原请求绑定。不得保存未经安全校验的正文、arguments、自由错误或认证信息，不改变成功谓词。证明 reducer 丢弃 unfinished tool、早期失败、后续重试和重启仍能定位首个拒绝阶段；诊断缺失只能报告 UNKNOWN。

输出：接入对照表、预算测量表、已确认缺陷/未知项、最小差异及现有集成回归证据。涉及跨模块协议或模型配置变更先 Astra 复核；只修有证据的缺口，不顺手迁移媒体接入。此步完成才准备一次新的有界文字验证。

##### 2. 有界真实文字验证：协议探针 → Planning 评测

这是待授权的独立验证批次，不创建生产 Creation；隔离Creation/Attempt仅作为评测载体，不占用正式作品名额、不恢复失败作品、不搜索/生成素材、不TTS/Build。复用经上述修正的隔离执行器、已封存冻结输入和完整应用层 A/B/repair/Truth 消费者；仅使用已证明属于本次授权的文字套餐，禁止现金、积分/余额、超额计费及付费回退。若权益无法证明则不发送。禁止直接以旧runner的阶段计数、默认旧版本或正常Preparation入口启动本批。

启动前冻结 source/Runtime/模型路由/thinking/实际输出参数、四个探针、六次评测输入及独立语义判据。任何代码、Prompt、模型、参数或期望调整都关闭该批，不能边运行边修改。

建议整批硬上限：**40次实际 Provider HTTP 提交、45分钟**，不是40个RPC；范围覆盖本批全部模型请求，含Truth、框架续轮、报告修复及结构化提交。执行器在共同最终发送边界原子计数并拒绝越额，不建立新生产账本，不能仅复用覆盖structured carrier的守卫而漏掉Truth。先离线验证计数/未知恢复及不可绕过性；不能落实实际提交上限则不启动。45分钟从首次实际发送起算，到期禁止新提交；任一上限到达但未完成全部样本即未通过，不保证上限内必能完成。超时有在途时只核对原请求，不视为取消、不释放占额、不补发、不认领通过。

先做4个真实协议探针：正常A、较大合法A、完整B、可定位共享repair，各使用完整实际阶段Schema与正常任务，不用小玩具Schema代替生产合同。第一请求占用正常A名额，优先采用开发3的冻结语义输入和实际Schema，以全新诊断身份执行，记录复用输入与新身份；它不是第五个探针，也不是恢复开发3。确认原终态、单次提交、完整参数、正式校验及持久读回一致。任一探针失败立即停整批并分类，不继续用另外三个探针探索更多错误；如原参数非法，记真实模型合同失败，不人为改参数制造PASS。

探针全部通过后，在同一固定版本上做**3个正常输入 × 2次独立执行**的 Planning 评测。输入优先取脱敏真实冻结原件及明确标记的合法派生样本，覆盖视觉+预置旁白+BGM、混合表达和较多视觉义务；冻结期望义务与来源，不修改真实作品。运行真实A→独立B→确定性投影→Truth→正式持久化/Delivery决策，停在允许 MATERIAL_SUPPLY 的判定，不实际供料。保留当前共享一次语义repair和已有报告格式repair，不增加预算。样本缺少适用合法原件则先补离线样本，不在真实批次临时改期望。

通过条件：6/6最终合同、独立语义复核及Truth成立；无required遗漏/升级、来源伪造、身份或状态越界；修复额度未刷新、未知未重发；实际次数/耗时可对账。首次通过率、repair率及成功率分别报告，合法内容误拒和任何未解决项不得隐藏。六例仅证明该具名范围，不宣称任意主题稳定。完整结果或副作用保护失败立即封存并停止，不把失败批次变成在线开发环境。

按证据选择一项最小修复：

| 已证实结果 | 修复方向 | 禁止做法 |
|---|---|---|
| `length`或输出预算不足 | 核实实际参数、模型允许输出及thinking占用；必要时评审按冻结scope有界分批、程序完整合并与遗漏检查 | 截断内容、减少required、无限增token或自动续写 |
| Provider完整终态与SDK映射冲突 | 对照官方API和安装源码修正明确的适配错误，保持完整终态/唯一调用/恢复语义 | 仅因看到部分JSON或工具就放行 |
| Schema能力或工具选择不满足 | 最小可复现真实请求与官方合同对照；在现有OpenClaw内评审受支持接入/模型选择并核套餐 | 转付费、绕过OpenClaw另造主链、推测strict解码 |
| 结构合法但创作语义/审核失败 | 从冻结义务与真实A/B定位责任或模型能力；保留拒绝，复核是否需要调整语义任务表达 | 为当前主题加词面白名单、人工补正式判断、扩大repair |

**任一失败即不可恢复地关闭本真实批次。** 随后可离线调查/修复，但不得沿用该批授权再次探针或续跑评测；后续真实批次须另有明确授权。同一根因两次针对性修复仍失败按原停止条件交 Astra，停止该接入路径的真实重试；这是更严格的累计停止规则，不是两次自动重试许可。提出有证据的替代方案和影响范围，不能继续换Prompt碰碰运气。不同根因也不能借分类重置整批调用/时间额度。

##### 3. 在完整作品前检查下游连续性（离线）

与第一步独立部分可并行调查，由同一Owner整合。扩展现有高价值连续场景：正常提案/确认→Preparation→Planning/Truth→Material Supply/Observation→正式Gate→Authoring→本地Hypit→输出绑定Quality。内部模块、身份、持久化和状态推进用真的；仅外部模型/Provider/付费执行边界替身。用当前proposal@3/vNext@6运行，不能退回旧Planning来取得通过。Hypit须先核实安装版本与实际源码，按原plan/pricing证明全部本地免费，然后由原build/export链生成该工程的实际MP4；仅check、手工ffmpeg视频或RendererFixture都不算真实构建PASS。无法免费实际执行时明确记录阻断，不扩大迁移范围。

优先检查尚未走过的新合同接缝：程序Voice与素材授权/旁白时序、素材完成后的Owner推进、同Creation checkpoint继承与Rights、Authoring读取正式绑定、Build终态/输出文件、Quality与当前MP4 SHA、恢复不得重复采购/TTS/Build。不枚举无关能力，不更改素材门槛。复用已有fixture与测试；实际缺口闭合后做一次组合回归及必要项目检查，不为每次报告重跑全量。

##### 4. 最后恢复完整视频验收

前置条件：步骤1、2、3具名证据通过且范围内无FAIL/合同缺口/未执行；Astra冻结复核；固定代码、依赖和Runtime指纹；准确备份实际raw-stream及现场；实时无unknown/pending/submitting/活动旧任务，费用余量及配置一致。正式能力未知不阻塞只读调查，但不得被软件PASS覆盖。

当前开发3/3已用尽，因此需要**一次明确的新增开发额度及上述文字批次授权**，不是逐阶段审批。建议先追加最多1个全新完整开发作品，沿正常入口同一Delivery连续到MP4/Quality；任何工程介入或不可自主恢复的失败立即封存，停止真实执行。不得从三个正式验收名额扣故障探索，也不得退款/重授旧作品未用预算。媒体累计保守已授上限¥15/¥30，剩余最多¥15；预算不足时停止，不默认扩大。

新增开发作品启动前固定媒体子预算表，建议默认如下，四件合计¥15，加历史保守占额¥15不超过总¥30。此为待确认分配方案，不是已经授予新作品的授权：

| 新作品用途 | 单件媒体授权上限 |
|---|---|
| 追加完整开发1件 | ¥3 |
| 正式主题1 | ¥4 |
| 正式主题2 | ¥4 |
| 正式主题3 | ¥4 |

确认前保守占用整份子预算，失败、未知和未用额度均不回收。正常核价发现单件不足则按原费用门停止，不减少required、不从其他作品挪预算、不自动扩大授权；不得承诺该预算必能完成全部作品。

新增开发作品全链通过后，按原Goal在同一固定版本另起3个不同主题正式作品连续验收；所有在途及历史占额计入。每件必须可播放MP4、required100%、正式Rights/Match/Readiness、输出绑定Quality、工程介入0。仅Planning评测或MATERIAL_READY均不能关闭稳定出片Goal，不发布。

##### 5. 交付与管理

Main负责收敛和实施；Astra只复核关键变化，不新增常驻Agent。每步只交付本Task下的证据/差异、具名PASS/FAIL/UNKNOWN、实际调用和费用、下一步启动条件。步骤1/3是软件调查与修复；步骤2是有界真实文字证据；步骤4才是端到端交付。以关闭已确认风险和成片结果衡量进展，测试数量、载体容量和版本冻结次数不作为进度。

时间安排是工作批次而非成功承诺：先一个离线收敛批次，交付清单后实施最小修复；文字验证最多45分钟；随后至多一个新增开发作品。若任一步超出范围或失败就回到具名证据，不再连续数小时运行真实批次。正式三个作品的耗时须根据第一次全链实测估计，目前没有可靠数据，不能承诺当天稳定出片。

Astra首轮方案复核：初次MODIFY的批次永久关闭、全部HTTP共同计数/起算点、四件媒体具体分配三项落实后给出CONTINUE。随后用户要求核实源码可执行性，第二轮复核为MODIFY，要求前述两个离线交付物及真实隔离Creation/旧回放证据的准确说明；本次已修订方案，交付物尚未实施。保留风险：40次/45分钟不保证完成六例，¥3/¥4不保证满足实际素材需求，Dev3根因仍UNKNOWN。方案复核不是真实验收或执行授权。

本轮仅核对和修订方案；两个离线交付物可沿用原Goal的必要软件修复授权推进，不因本文再增加阶段审批。新的真实文字批次及开发作品超出已耗尽的运行额度，仍须明确追加授权；“无论用什么办法”不自动扩大费用或抹除原停止条件。

#### 完整开发1 FAIL 与 XML wire 投影（2026-10-08，离线实施）

完整开发第1/3作品从正常确认完成至Delivery终态147.578秒，Preparation成功但A22137字节正式结构拒绝；3次本地重入复用原A，无B/repair/Truth/Supply/生成/Build。工程介入0、占额¥5、确认媒体费用0；完整原件及账本私有封存，新增永久真实fixture。首次确认前正文混排拒绝与正常修订也保留，不能将修订作为冻结后救场。自主视频仍0/3。

根因证据：官方MiniMax-M3 Jinja模板把数组写为item标签，公开SGLang M3 parser依赖直接type/properties而不解$ref。对同一合法image+BGM样本执行这些原始公开实现，原Schema产生与真实现场相同包装，等价展开后还原canonical；这证明参考实现的确定性机制，**不证明在线Provider采用该实现**。当前真实A还有动作/image、后期-only Need、字幕错误模态、BGM/SFX混杂和unresolved，历史FAIL不由投影恢复。Preparation虚构占位来源与逐行scope/镜头语义错位分别保留调查，不把它们合并成传输Bug。

经Astra前置MODIFY修订并取得CONTINUE，最小实现限定如下：

- Canonical SemanticProposal、支持合同、Material V1.3及required/Rights/Match/Readiness不变。应用层生成新wire Schema：有限本地$ref展开，sibling/allOf约束完整保留，仅补逻辑蕴含的容器/标量type提示。
- 必填nullable使用严格二选对象 `{"null":true}` 或 `{"value":非null原值}`；可选字段按已有默认保持。字面量字符串`"null"`不转null。非法分支/未知形状直接拒绝；涉及移动字段的跨字段谓词若未支持，构造请求即拒绝，不删除约束继续。
- 新journal/checkpoint@5绑定stage、codec policy、canonical/wire SHA；原A/B/repair原始字节不改，诊断与派生另存，verify从原wire重放。@4/@3/@2保留原Schema、Runtime身份与repair额度；旧pending只核对原请求，不重解释为新wire。
- 完整wire校验失败留存封闭诊断；严格解码只解除可证明等价的编码，不改非法enum/业务叶值。诊断候选只进原有可定位共享一次repair；不能进入B或正式接受。修复回复完整wire→codec→canonical校验，无repair ACCEPT同样完整通过，独立语义审核仍必需。
- 复用既有矩阵/原生Gateway回放。必须验证公开原parser跨模态数组/boolean/number/引用/可空值往返、ref sibling约束、非法null对象、旧恢复、身份篡改、repair后persist/load/verify及真实失败持续拒绝。完整软件/最终复核通过后，按剩余新作品授权加载并验证开发2/3，不重启失败作品。

只增加普通JSON Schema校验库（已在测试环境使用），不增加运行时工作流框架、公开路由或第二条状态机；原有请求/额度/费用防线不变。

软件收尾：run-043矩阵230PASS，全量973PASS/5既有skip，原生Gateway→Harness→persist/verify五场景5PASS，115技能/compileall/范围diff通过，272现场/130fixture保持。冻结复核中的enum/not排除null反例已闭合；完整原节点判定null合法性，strict decode与修复/recheck重新验证完整canonical。run-042 fixture FAIL保留，新增公开源码改为原字节.py.txt以排除compileall生成缓存，原来源SHA不变。固定工作树source6f28fbd7…50c5a及独立pyproject/dependency版本，Runtime仍12b0d561…6c19c5；未冒认HEAD含未提交工作。Astra最终CONTINUE，现场空闲/套餐/精确原始流备份及新进程版本检查通过，Web8440/Gateway8438已加载固定代码；Runtime未修改。开发2/3从正常Web发起新方案请求，真实开发1与原两轮FAIL均不变。[具名软件记录](../acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-wire-software.json)。

#### 完整开发2 FAIL 与联合语义合同调查（2026-10-08，真实重试停止）

开发2从正常方案确认至正式终态678.473秒，Preparation/A各1原RPC并释放；A8545字节的conditions/queries数组与boolean正常，原XML包装问题未复现。六个image的match_output/native_ratio联合选择不合法，原共享repair不能无损定位整Need故障；两项声音资源unresolved仍正式阻断。B/repair/Truth/Supply/媒体/Authoring/Build/Quality均0、工程介入0，无MP4。原失败不恢复；[原件摘要](../acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-full-development2-failure.json)及永久A/replay-input fixture已保存，累计媒体占额¥10/¥30、确认媒体费用0，自主首版仍0/3。

Astra STOP要求先完成同一Task的联合离线方案，不用最后一个开发作品逐条试Prompt。画幅候选方案为单个原子选择unconstrained/match_output/native(ratio)，只能确定性投影，旧非法A持续拒绝。声音目录是语义身份；具体BGM asset在Material后绑，旁白Runtime preset必须证明符合冻结意图。已核实当前配置male-qn-qingse与本次已确认女声要求不能直接相容，现有链没有正式resolver。optional SFX仅后期淡入与全局风格image是潜在语义风险，尚未进入正式B；不能冒认已被审核或自行删除。下一步统一根因/权威输入/程序派生/正式消费者表与前置复核，然后离线实现和历史反向保护；新实测保持停止，Goal仍ACTIVE。

#### 联合离线修复实施方案（2026-10-08，同一Task）

目标仍是完整自主视频；不启动第三个开发作品，不重计两件FAIL。联合方案复用现有矩阵/Owner，分两个离线子步骤，组合验收后才能固定加载并真实验证。Astra已对两子步骤分别给出离线CONTINUE；最终组合冻结尚未完成，不以局部通过替代完整验收。

| 风险 | 权威输入与合同 | 模型选择 | 程序职责与正式消费者 |
|---|---|---|---|
| 重复画幅字段 | 原合法unconstrained/match_output/native(ratio)集合 | 一个完整画幅choice | 新@6 producer framing原子表示，双射投影旧canonical；完整校验、B、正式Material投影不变 |
| 素材与后期混淆 | 每个正式Need必须有material+required源义务；SFX使用event scope | 完整条件语义及职责 | 仅把已有编译规则前置Schema；纯后期SFX正式拒绝，global image仍独立B审核 |
| 语义目录与供应资源混淆 | voice引用是冻结创作身份；BGM具体file/Rights尚未产生 | 保留旁白/音乐意图、必要性及合法来源 | 程序提供阶段职责metadata；不删除或忽略unresolved，不猜曲目或身份 |
| 声音意图与技术执行断裂 | 当前官方preset表行中文/青涩青年音色，非已确认女声 | 新正常方案仅在已核实能力中提出明确身份选择，原表达保留 | preview与方案hash冻结中性handle/官方label/language；确认、核价、请求、恢复及输出认领核同一binding。Provider ID仅执行层。冲突必须正常修订，不能靠字段优先级覆盖正文 |

第一子步骤：保留SemanticProposal与Material V1.3；@6 journal/checkpoint及stage Schema身份，@5旧wire/@4/@3/@2原消息/Schema/额度恢复。framing只在明确Need Schema位置转换；非法或模糊choice直接拒绝，旧非法split组合不归一为成功。视觉header局部repair输出也用原子choice，条件/queries/必要性与其他已接受语义不变；仍共享一次repair。职责metadata仅影响新版本输入。

声音子步骤不得增加自动preset resolver、声音B审核或默认旁白：只有已确认需要旁白、且明确确认了可执行身份的新方案可得binding。ASR仅作全文/时序证据；官方preset标签与实际输出ID仅证明该明确身份绑定，不冒认性别、音域、温暖听感的独立听审。确认冻结待审选择；确认后的既有Truth执行必须独立核对完整sound与官方profile、实际执行控制，在采购前给出MATCH/CONFLICT/UNRESOLVED。不能删除文字、猜gender、调整用户意图或按“新字段优先”放行；确认后冲突即失败，不能改写冻结稿救场。

第二子步骤联合合同（Astra前置CONTINUE，2026-10-08）：

- 新预置旁白方案为`easel-video-proposal@3`。正常提案只提供当前已核实的中性handle、官方名称/语言/来源及可执行控制；原sound原文与程序渲染的展示都进入方案hash。未知handle拒绝，不替换；静音/音乐及有效旧@2保持原合同。
- 确认原子冻结Plan/profile/完整SCRIPT/技术授权scope摘要及Creation身份。Provider preset ID保留在执行授权，不进入Material Domain；无有效scope或旁白授权不生成新binding。
- 显式voice/mixed且有效profile和完整SCRIPT才由程序派生唯一required Voice。新A只生成其他模态，预留1个Need容量；A重复Voice必须拒绝，不合并或删除。原unresolved不自动清除。派生Need和来源进入正式Plan身份及检查点重算。
- 同一个既有Truth阶段处理脚本与独立`voice-identity-review@1`项；SCRIPT零待审或旧PASSED不能跳过新项。报告绑定Plan、原sound、profile、技术scope、完整SCRIPT及正式Voice Need，MATCH才可进入Supply；有效CONFLICT/UNRESOLVED不触发改判。沿用一次报告格式修复，不增加语义重试。
- Planning持久化/恢复、核价前、正式提交及Rights认领重新核完整binding、Need、SCRIPT、实际preset和资产身份；旧记录不迁移、不取得新binding。官方证据缺少的硬性身份或表达能力保持UNRESOLVED。
- 先离线执行正常提案→确认→Preparation/Handoff→Planning→Truth→Supply入口与提交/Rights反向保护，联合软件通过和冻结复核后才考虑最后一个新开发作品；不将此次CONTINUE当真实验收通过。

验收复用原矩阵，含两件真实FAIL原件、合法画幅集合/独立native ratio、XML完整往返、header repair及persist/verify、旧@5原身份恢复、Schema/目录/来源篡改、纯后期SFX拒绝与合法全局视觉反例。声音另需正常新方案→确认→原核价/请求→输出认领连续回放、配置/handle/方案漂移拒绝、旧作品不补binding、相反身份不静默接受、无旁白不造Voice。全部组合软件及Astra最终复核完成后，才决定使用最后一个开发作品，随后同固定版本3个正式主题连续出片。报告测试定义错误与产品缺陷分别保存；不重复报告触发全量重跑。

联合收尾补充（2026-10-08，离线实施中）：

最终联合软件与加载结果：run-048矩阵269PASS/0FAIL/0GAP/0未执行，常规1012PASS/5既有skip、原生Gateway/Harness完整7PASS、115技能/compileall/范围diff通过；287现场/132fixture及两个真实FAIL额外34文件不变。全仓diff两处已有历史文档EOF空行保留，不能冒认全仓PASS。Astra最终CONTINUE，固定工作树source e2451702…85da52（HEAD df0d3a30…不含未提交修复）；实际raw-stream停服后138728字节精确备份，Web21631/Gateway21609于11:43:30新启动并核HTTP200/源码/依赖/Runtime一致。加载前357作品/10旧Owner/外部Gateway全部空闲，无unknown/pending/submitting，套餐98%/周97%。媒体保守占额¥10/¥30。此次装载预检首次因脱敏器将文件名secrets.py的源码摘要误脱敏而拒绝，源码/现场无变化；只修正私有checksum清单序列化并保留预检FAIL，不改生产。下一步按剩余额度正常新建唯一开发3，不重计旧FAIL。

- Truth先安全解析并锁定独立voice合法决定，再核外层及SCRIPT格式。合法CONFLICT/UNRESOLVED即终止，即使缺script或外层多字段也不修为MATCH；合法MATCH在一次格式修复中不可改判。新增原矩阵反例及UTF-8修正。
- Astra前置CONTINUE允许沿既有同Creation checkpoint fork继承原语义证据：`voice-identity-checkpoint@1`只记录源/目标完整Plan摘要、原报告摘要、源Attempt及提交fingerprint，不重写MATCH、生成记录或费用receipt。完整Plan只排除plan_id/attempt_id比较；SCRIPT、Truth ledger、Mode/方案/Need/controls与Planning origin必须保持。显式visited拒绝环/断链/跨作品。
- SCRIPT ledger在persist前原字节复制并正式校验；load对可信链迭代核验原报告、源Gate及fingerprint。当前批准资产必须有与可信原来源相同的记录和真实字节，使用原Plan重验既有Rights认领，不放宽原身份规则、不重TTS。该遍历同时供当前Gate核验使用，COPYING不得提前进入生产。
- 组合初次run-046为251PASS/7FAIL（另7 teardown ERROR），原因是测试隔离器挡住合成媒体的本地ffmpeg；未按产品FAIL计算但完整FAIL现场保留。只对现有preset/material行允许临时目录内的固定lavfi合成与ffprobe检查，加入file/pipe协议白名单，其余进程/网络/实时配置仍阻止。初次常规回归1000PASS/1FAIL/5既有skip为两处缺UTF-8，原JUnit保留。后续组合验收尚待执行。
- 一次早期隔离测试替身只替换submodule，包导出仍使用真实Speech adapter，曾以fixture-key尝试网络并得到不确定结果。无真实凭证或真实作品使用；随后双入口固定替身并加入确定性测试公网urlopen阻断。不能声称该早期测试从未尝试外部请求。

#### 当前阻塞与最小 Runtime 接入设计（实施前复核草案）

证据为 [固定 Runtime 能力审计](../acceptance/planning-a-structured-carrier-capability-2026-10-08.md)。普通 agent RPC 无动态工具入口、原生工具参数 256000 字节不能承载现有合法 A 容量样本；历史 d01 仅 7849 字节且无损，它的结构与语义错误仍须独立解决。新 Goal 授权必要 Runtime 改动，原固定 Runtime 审计 STOP 结论保留。

- 在现有 `agent` RPC 增加受限、版本化的 `easelStructuredResult` 请求，只有固定提交工具名、完整 Schema 和 Schema 摘要；复用 client-tools、原 run/session/idempotencyKey、原终态及只读 transcript。不得开启额外 HTTP 路由或直接绕过 OpenClaw 调 Provider。
- Schema 由现有 SemanticProposal 派生并绑定本次冻结目录：scope/continuity/voice 的合法选择由程序枚举；模态互斥及现有 frame/source_seconds 条件在 Schema 中表达。不能裁减当前合法集合、降低 required 或把结构合法当语义正确。B 与共享一次 repair 保持独立审核职责。
- Runtime 仅向模型暴露这一提交工具，固定 tool choice、关闭并行工具；最末请求边界再次验证工具集合与 schema 身份。非法目标不能执行内置工具。客户端工具只提交候选，不写正式 Planning 文件或推动 Easel 状态。
- 本协议单个完整 arguments 上限沿用现有 8MiB envelope；无协议请求维持原容量。原生 reducer 保留原始 UTF-8 arguments、原 tool-call ID、完成原因；不可用重新 JSON.stringify 的对象冒认原文。只有完整工具结束及原 run 成功终态同时成立才接受；length/error/aborted/缺终态均不得推进。
- 通过原 transcript 活动分支与原 run 捕获所有目标调用；重放按消息/调用身份去重，实际多次目标调用拒绝。捕获时核对完整字节/hash及只读恢复，后续错误不能被较早的正确候选覆盖。重复键、非有限数和敏感内容在正式持久化前拒绝；解析后仍完整校验并进入 B/Truth。
- 禁止 Runtime 隐式工具纠错新增模型预算。每个结构化阶段请求最多一次实际模型提交；在原请求身份下持久记录提交占额，SDK 自动重试和框架重试不能增加提交。网络未知不刷新占额；规划阶段仍只有原共享 repair。需要核验真实 transport 的最后请求边界，不能仅凭 RPC 数作费用依据。
- 新 carrier/policy/schema/runtime 指纹进入原冻结身份；旧 pending/旧 checkpoint 按原版本恢复，不迁移、不默默改用新协议。不对旧 Creation 自动重入。
- 采用仓库内版本与文件 SHA 钉定的兼容补丁及原件备份，先在隔离安装副本验证，未知版本/部分补丁/源漂移 fail closed。正式加载前确认无活动/unknown/pending，停服后精确备份真实 raw-stream 路径，再加载并对账实际进程和版本。

实施前 Astra 需核查 RPC→实际 payload→原生 stream→客户端工具终态→持久 transcript→Easel capture 的连续性、重试费用边界及旧版本保护。具体插入点与返回语义以实际安装 OpenClaw 2026.9.4 为准，不宣称尚未验证的 MiniMax strict/schema 能力。

2026-10-08 Astra 前置结论 `MODIFY` 已接受，以下为实施合同，不需要新增用户授权：

1. 新协议成功谓词同时要求原 run `ok`、provider `finish_reason=tool_calls`、assistant `stopReason=toolUse`、Runtime `stopReason=tool_calls`，active 分支恰好一个指定调用及原参数完整结束。旧协议成功白名单不扩展；后续错误/缺终态/多调用/未知工具拒绝，不合成工具结果或启动续轮。
2. 原始字节特指解码后的 arguments 字符串 UTF-8，不是 HTTP wire bytes。敏感/重复键/非有限数检查在 Runtime 首次 transcript/raw-stream/诊断持久化之前完成；未通过仅保存分类。合法内容按原字符串及 SHA 保存。实现须阻止未核验流分片先写入日志，而不是只在 Easel 读取时补查。
3. 原请求身份下 `UNSPENT→RESERVED` 原子且 durable 后才能进入实际发送；占额写失败则不发送，预留后崩溃/网络未知保持 UNKNOWN，永不自动返还。最后 payload 核对实际完整 schema SHA、唯一工具、固定选择与 parallel=false；所有 SDK/框架重试、fallback、压缩和并发恢复经过同一额度防线。安装版 SDK 已有 `maxRetries:0`，复用并验证，不重复实现；框架重试仍须独立保护。
4. 分别测量 arguments 的8MiB、整个 RPC 的1MiB输入预算、转义后 transcript 与 reader 容量，不假设当前32MiB session上限足够。原生存储可能同时写 raw/解析对象及工具结果，完整恢复测试必须计入这些开销；超限明确拒绝，禁止裁剪或回退。Schema 摘要绑定实际发送对象，Provider拒绝时不自动移除关键约束。

隔离实现进度：`scripts/patch_openclaw_structured_result.py`按5个安装文件SHA钉定，默认dry-run；只对`/tmp`完整安装副本应用。支持组件在实际fetch前durable占额，另按原session绑定协议/原run，防止原生重启恢复丢选项后重新执行；普通未绑定会话行为保持。完整native transport10场景、隔离Gateway8MiB持久/恢复均PASS，真实外部0。旧完整文本协议保持，新`planning-result-v3`调用适配已实现；新Planning默认已接入@3 journal/frozen checkpoint，固定完整schema/Runtime身份并进入正式Plan identity；旧@2 pending/冻结记录按原文本协议恢复，A之外的B和共享单次repair保持。22入口风险集成、201矩阵、943全量/5既有skip通过；最终host补丁与转义容量回归尚在完成，不认领正式服务已加载。

第一次隔离只读检查暴露SQLite `mode=ro`新建SHM/空WAL的文件差异，严格全目录相等断言失败记录保留。新检查仍保存所有差异并要求数据库/既有WAL原字节保持，只允许只读连接的共享锁文件与新空WAL；不使用会忽略活动WAL的immutable模式来掩盖变化。[开发修正记录](../acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-development-corrections.json)。

冻结前Astra复核又确认HTTP层重定向及debug capture位于原保护之外，已在隔离副本补新协议专属maxRedirects=0/capture=false及原生debug fetch解包，普通协议不变。原生Gateway同源307/308各一次POST；debug开关实际启用后合成敏感候选未落盘。转义8MiB测试暴露原SSE16MiB缓冲不足，保留FAIL；新协议wire上限64MiB、arguments仍8MiB，完整转义8MiB原tool ID/SHA恢复PASS。最终run-036矩阵201PASS、全量943PASS/5既有skip；Astra CONTINUE。固定工作树生产215文件SHA761d28ae…dc6d34d；未commit/push，HEAD不冒认包含这些改动。

#### 首轮真实 Development 失败与下一次最小修复（2026-10-08）

固定source761d28ae…dc6d34d及已加载Runtime下，d01全新隔离作品63.909秒FAIL；Preparation、A工具、B文本三原RPC均终态并释放，工程介入0，Supply/媒体/Build0。A原工具参数1548字节完整捕获；B原件3256字节，程序题目0–9、答复0–6/8/9，仅缺7，无unknown。禁止给该轮补答案、删条件或恢复计分。当前first_cut_ready仍0/3。

只读Scout及Astra确认：漏题之外，B把成片9:16规格当native源画幅直接授权，并把derived Preparation的无人约束称为SCENES原句；brief中不存在其所称visual_preference字段。仅让B返回完整ID不能闭合这些问题。Astra前置MODIFY要求载体与可核验支持分别修复，合法引用仍不等于语义蕴含。

下一批复用已有Harness工具通道、B问题目录、共享单次repair和正式发布边界：

- B/recheck使用程序生成的必填键槽位，模型仅填写decision/support/reason；程序按确切键恢复question identity。缺键、未知键、重复键均拒绝，不根据返回顺序猜测、不补默认答案。repair同样用固定目标槽位及各槽完整类型，程序恢复patch target。
- 支持目录从冻结B evidence确定性展开。每项保留原origin、程序生成path、原值及hash；模型只选择现有handle，并对字符串提供确切quote及支持角色，不再自行维护source_path。不存在的handle、路径对象或引用原文不匹配，不能形成准入支持。保持完整原件/完整问题，不把引用片段替代审核上下文。
- 支持角色至少区分authority与context。derived_preparation只能作context；confirmed_spec的final_output事实不能作为native源属性或素材硬限制的authority。postproduction条件可引用相应output事实；原文确实独立要求native比例的合法来源必须保留。具体判断仍归B，不按词面同值禁止全部native选择。
- ACCEPT须有独立合格authority支持并通过原完整义务判断；支持存在仅证明来源/资格，不证明整条蕴含。“静态桌面图，无人物、无动作”不拆删，单一真引用不得机械放行复合含义。不明确时B给CHALLENGE/UNRESOLVED，交既有共享repair；程序不替B写判断或删A。
- 新支持合同、阶段Schema、资格规则进入新journal/checkpoint及cache身份；旧@2/@3请求/冻结记录按各自协议恢复，不给旧轮刷新额度。当前round1维持FAIL，下一轮必须在整个离线矩阵和前置复核闭合后另起。

先保存真实原件并完成修前对照：漏题；完整答案仍错误源/成片归因；伪造字段/原句；derived单独扩权；合法独立native要求；合法继承与软偏好；复合义务仍需完整语义判断；旧pending/reentry/共享额度。该批不更改Provider、Rights/Match/Readiness或素材required门槛，不增加词面语义Gate。若新支持合同后仍出现错误蕴含，封存真实FAIL，复核模型审核能力，不继续以当前样本的Prompt/规则补丁取得PASS。

本批软件完成：新@4固定B/repair槽位、完整冻结支持目录与资格、原文引用、旧@2/@3恢复保护。Astra发现并闭合旧@3在新Runtime首次提交的身份缺口；冻结Runtime期望到达实际派发边界，无原call且不匹配则在额度与RPC之前拒绝，已有原run允许只读对账。阶段工具描述只对B/repair调整，A原描述保持；补丁仅接受具名旧SHA升级，旧原件保留。

run-038为221PASS，全量959PASS/5既有skip，115技能/compileall/范围diff通过；257现场/122fixture及测试工具指纹保持。原生隔离Gateway的B和repair分别无损读回，原run终态ok、原tool ID/字节SHA一致、每请求仅一次Provider替身；真实费用0。Astra最终CONTINUE。固定source73e63a66…544ea6（HEAD df0d3a30，未提交），安全加载完成后才按同一Development累计账本启动round2；不恢复round1或重置预算。软件证据见carrier-audit/autonomous-support-*及run-038。

#### round2失败后的载体职责修正（仅离线，真实额度已耗尽）

round2真实FAIL保留。2600字节A原始工具参数完整、安全，但conditions/queries形状错误，触发原生工具参数validator的纠错续轮；单次提交保护正确阻止第二Provider请求，原run最终error。原生Gateway既有测试未覆盖“安全完整但业务Schema非法”生命周期，此为确认的软件测试缺口。

Astra前置CONTINUE：唯一structured clientTool本地参数合同改为`{type:object, additionalProperties:true}`，不增包装、不改原始参数。实际Provider payload继续使用完整业务Schema/hash；safeArguments、唯一调用、原tool ID/hash与原run终态成功均保持。业务合法性只由Harness校验，无法定位的结构错误允许正式REJECT，不能为使用repair整批重写。普通工具参数校验不变。错误诊断只传递可信本地封闭分类，不保存Provider异常全文，不改变UNKNOWN/费用占额。

必须实际回放：原round2非法A→一次Provider替身→候选成功运输终态→Harness拒绝；可定位错误→原共享一次repair成功/仍失败；普通工具仍拒绝非法参数。更新Runtime/源码身份，旧@3/@4只读恢复或原身份首次提交约束保持。两轮Development已停止，不用本离线修订扩真实额度。另已确认在完整视频启动前，需要正式授权入口执行“仅图片/预置旁白”的程序限制；当前单Creation预算不能单独约束AI视频，不以自然语言替代费用防线。

本修订软件已完成：真实原件修前/修后Gateway对照及Harness拒绝，连续原生3场景PASS，普通工具保护PASS；run-039224PASS、全量962PASS/5既有skip、115技能/compileall/范围diff、Astra CONTINUE。新sourcebbf3e615…9c9c0a2，仅离线未加载。旧@4固定Runtime digest明确保留，不把其重写为新版本；旧新提交需原Runtime，否则在RPC前拒绝。generic错误分类未细化，作为诊断限制保留，不推测异常包装类型。

#### 图片与预置旁白预算保护（2026-10-08，仅离线实施）

已获用户累计 ¥30 授权及 Astra 前置/实现 `CONTINUE`。复用正常方案确认的 `generationBudget`，允许可选 `allowedModalities`，本 Goal 固定为 `image, voice`；非空、无重复、合法子集才可接受。新授权持久化 `material-generation-budget@2` 与规范化子集，进入既有请求 fingerprint；旧无字段记录保留旧合同和指纹，不迁移。重放确认不能省略受限字段或扩权，列表顺序变化可接受。

生成选择、核价前与最终执行边界核对实际 Need 模态；BGM/SFX 不是 voice，即使存在构造的 receipt 也不能提交。Provider、账户、音色 scope 及原占额/不确定恢复语义保持。前端仅补请求类型，不增加执行流程。既有真实内部生成集成扩展图片、旁白、视频拒绝、BGM/SFX 拒绝和授权指纹漂移；针对性 16 PASS，原测试过程中两个 SFX fixture 构造错误修正为合法事件 Need，不修改产品合同，保留具名失败 JUnit。最终 run-040 矩阵224PASS、全量967PASS/5既有skip、115技能/compileall/范围diff及前端lint/build通过，Astra CONTINUE；source `4d1a5510…356c68`，257现场/123fixture保持。软件证据为 `carrier-audit/autonomous-budget-software.json`；未提交、未加载、未新增真实调用。

跨 Creation 采用本 Goal 验收账本的保守顺序分配：每次正常确认前持久占用整份子预算，全部已授予上限之和不得超过 ¥30；失败、未知和未用额度均不回收，不按当前已花费金额重复授予剩余总额。确认结果未知时只核对原 Creation，不转授新作品。不建立第二套生产预算服务；此为本 Goal 的外部执行约束，不声称产品已有通用跨作品预算功能。

真实 Development 两轮仍耗尽；已向用户提出一次追加验证（1 个新作品、仅 Planning/Truth、最多 8 阶段提交/8 分钟、文字仅套餐、任何 FAIL 即停、无媒体采购），尚未得到答复，不将 ¥30 媒体授权解释为追加 Development 额度。

#### 必须取得的软件及真实证据

扩展既有矩阵/集成执行器，使用真实内部模块，仅 Provider 网络边界替身。覆盖合法 A/B 大载荷与 8MiB 边界、Unicode 分片、完整但非法 JSON/Schema、未知或重复工具、length/缺 finish/error、重放/中断/持久失败、原请求恢复、不重复模型提交、旧协议隔离、模型输出不得改 required/冻结源。原生 Runtime 与产品消费者的组合通过后再运行项目 pytest、技能校验、compileall、diff；前端若有改动另跑 lint/build。

真实每作品记录阶段耗时、实际模型/Provider/生成/旁白/Build调用及恢复次数、费用占额与实际费用可核实性、最终素材覆盖和视频/音轨/时长/SHA、Quality依据与工程介入。只有3个固定版本的完整独立作品均满足条件才关闭 Goal。当前尚未开始这些新作品，不能用旧软件 PASS 或旧工程跑通认领完成。

### 提案收敛根因修复（2026-10-02 用户追加授权）

E2E 发现完整文案/分镜仍将时长、画幅、音轨写为待确认，保存逻辑却标记可确认，画布只禁用制作按钮。最小修复：Director 在尊重用户明确要求的前提下提出可执行推荐规格，标明推荐及依据；只有完整方案和规格才可确认。缺项通过原对话补齐推荐或一次选择提交，读取失败提供重试；页面与实际冻结使用同一保存版本，不猜默认值、不绕过预算/权利/最终确认。复用原提案与聊天，不新建流程。不修改或启动当前 Creation、不调用付费 AI、不重启制作服务；采用局部合同/页面 Fixture 验证。

1. Creator 确认委托后，Easel 自主交付基本可看的首版；正常路径无需 Creator 或工程人员逐阶段推进。
2. 同一 Creator + Director / Creative Mode + 不同 Content，导演判断贯穿 Planning、Material、Voice、Production 和 Quality，主题与叙事保持开放。

已具备后端 Delivery Owner、委托与费用核验、Director 参数传递、素材/声音观察、真实旁白时序、原生字幕/混音、系统审片及有界恢复、三内容局部回放。复用这些基础，不将旧根因再次列为从零实施事项。原始目标仍未取得真实自主交付与跨内容风格一致性验收。

## 本轮唯一任务清单（软件范围已完成）

| 顺序 | 任务与最小范围 | 完成条件 |
|---|---|---|
| A，已验证 | 核心要求/软偏好分离、内容优先预选；不把风格差异统一判 partial | 保留现有合同与回归，不将 A 等同完整镜头替代 |
| C，已验证；依赖 A | Director 根据已观察失败选择可替代镜头表达，复用有界补料；决定随现有记录进入编排与审片 | 核心/硬要求不变；替代表达真实进入检索、选用和质量上下文；耗尽明确停下；未知提交不重发 |
| B，已验证；依赖 A | 同素材一次输入、各 Need 独立观察判断；按真实帧、需求和版本复用 | 独立结论与 Rights 不串用；输入变化失效；中断不重复派发；局部调用计数减少 |
| D，已验证；依赖 A | 例外时一次接受当前所选画面、BGM、旁白并自动继续 | 当前版本/逐 Need/字节绑定，陈旧选择拒绝；自动报告与人审取舍分开；不绕过事实、权利、费用、技术可用性 |
| E，已验证；依赖 C/B/D | 现有画布与执行记录收尾；扩展已有三内容回放到 Production/Quality | 正常路径无中途确认；进展、保留结果、停止原因真实；无重复 Provider；不同内容保留同 Mode 执行依据 |

已按 **C → B → D → E** 收尾，未新建 Workflow 或 Task。每批遵循根因→最小修复→风险对应局部验证后提交推送；现有三内容回放覆盖原生编排、系统 Quality 与新决定消费。下一步只有用户另行启动的真人验收，不自动运行完整 E2E。

不纳入本轮：新 Director 模块、第二 Production Domain、重做 Material/Hypit、全局 UI 重设计、盲目更换模型、无限重试、默认并发。精细音色情绪评分和扩大音乐校准集后移；真实 ASR 仍可能出现同音误识别，不能将人工字符复核能力记为完全自动解决。D 是例外减负入口，不是正常制作新增必经审批。

## 已确认方案与 Director 内部取舍

确认前在原对话中讨论并持久化文案、分镜节奏、声音设计和规格；确认绑定当前版本。确认后的 SCRIPT/SCENES 原稿保留，用户明确核心、事实、身份、禁止事项、规格和声音身份不得自动改变。

Director 可以对明确标为可取舍的景别、背景细节和色调作内部决定；保存在现有制作记录并提供给后续编排/审片，不覆盖确认原稿，不把“与初始示意镜头不同”直接等同不合格。Material 只核验实际适配，不自行改写意图。需要实质修改确认稿时才返回对话确认。

旧 Need 未区分软硬要求时不自动降级。此前仅准备/规划失败可修改同规格方案的恢复入口继续复用；它不授予素材/生产已开始后的通用重编权限。

## 当前执行边界

不修改、恢复或重建已删除 Creation，也不推进其他现有作品；不调用付费 AI，不启动真实 Build、完整 E2E或以重启服务触发制作。固定输入与隔离 Fixture 验证，不依赖真实凭证。目标管理器的暂停状态属于应用运行状态，不写入产品任务完成条件；不得通过虚报旧 Goal 完成来创建新 Goal。

## 3. 最小责任边界与完成条件

| 现有归属 | 必须承担的责任 | 完成条件 |
|---|---|---|
| Easel / Creation Workflow | 唯一 Delivery Owner，持有委托、推进、处理缺口与失败 | 当前输出通过首版质量检查并可审阅，或有证据说明无法履约；用户接受独立于中间制作完成 |
| 现有 Planning + Production Authoring | 连续的 Director 判断，把内容与 Mode 转成选材、声音、节奏、字幕和剪辑决定 | 决定落实到实际原生工程；只有文稿不算完成 |
| Truth | 保护真实事实、身份与表达边界，区分事实、观点、假设 | 影响交付的真实主张有依据或得到合适处理；普通改写不默认逐句人审 |
| Material / Voice | 提供实际观察过、权利条件成立、适合表达的素材与语音 | 必需素材可用于具体剪辑，声音身份、实际时长和必要时序明确 |
| Hypit Production | 执行明确的音画、时间线与合成安排 | 候选视频身份正确且可播放；不补猜导演意图 |
| 现有 QC / Review | 系统先检查可看性与明显 Mode 偏离；Creator 最终取舍 | 检查绑定实际输出，关键缺陷解决；人审接受单独留证 |
| Recovery | Delivery Owner 调用的内部恢复能力 | 从可信结果继续，不重做成功工作，不重复不确定提交 |

不新增 Director 模块、第二套 Workflow、第二套 Production Domain；责任名称不对应新服务或新阶段。复用当前状态和持久记录，页面展示只读投影。

## 4. 委托、授权与恢复

- 确认冻结意图、事实边界、Mode、规格和费用权限；内部选材、镜头和剪辑草案可在范围内版本化调整。实质改变委托才再次确认。
- 本作品文字使用声明随同一次方案确认单独留证，绑定声明版本/范围、作品与方案；不把费用批准、普通聊天或旧确认当作该声明。它只记录 Creator 的输入授权来源，不替代 Provider 输出许可、第三方权利或发布条件。
- 新声明明确包含按委托以文字生成图片/视频、改写、预置旁白与剪辑；旧声明只保留原范围，不因升级自动扩权。生成素材的内部使用由当前输入授权、请求时已审核协议版本、模型/请求/实际资产身份及素材观察共同认领，不能由“生成成功”或费用批准直接推导。沿用正式 Rights/Match/Readiness；缺证或已有不利权利条件不覆盖，入库和公开发布仍分开。
- 正常选材、补料、技术重试、格式修复与基础质量检查由系统执行。只有必要且系统无法处理的事实/权利问题、实质意图变化、授权外费用等才升级 Creator。
- 持续推进、执行身份、检查点、重试与费用记录附着现有 Creation/Attempt，复用现有原子写入/锁/幂等/对账；刷新、关页、服务重启后恢复。
- 成功步骤复用有效证据；提交不确定先对账。恢复不能自动重复购买、复制过期批准或无限重试。
- 确认前说明允许操作、费用依据和执行边界。已有授权内不重复询问，零第三方费用不虚构正预算。本地预算不是 Provider 硬上限；无法判断是否在授权内时停止提交。
- 逐次付费批准、零费用确认和显式补料策略涉及的现有 ADR/Task 条款随对应实现一并修订，记录授权来源；不绕过正式 Rights、Match、Readiness、身份或费用语义。
- 旧 Creation 不迁移、不自动入队、不因启动新代码恢复运行。自主委托只作用于明确带有新委托记录的作品；本轮测试全部使用隔离 Fixture。

## 5. 已建立的能力边界与复用基础（不是重新开发清单）

| 改造项 | 最小改动 | 复用 |
|---|---|---|
| 持续交付 | 页面推进迁后端，持久化执行、检查点和恢复 | Preparation、MaterialProductOrchestrator、Authoring/Hypit API、现有存储 |
| Director 执行要求 | 当前 Mode 中 V1 支持的少量要求落到 Need、运行参数、原生编排与检查，保留来源和适用范围 | Creator Context、Mode、Treatment、MaterialNeed、组件/recipe |
| Material | 接通已有模式检索词、导演偏好和适用风格匹配；实际观察主体、区间、光线、运动、限制；有界替换/补料 | Compiler、Matching、Intelligence/enrichment、Library、supply_subset、Rights/Readiness |
| Voice | 可支持朗读要求进入实际请求；绑定已批准音色和参数；真实音频检查与逐句时序 | VoiceNeedSpec、TTS adapter、生成记录、音频素材/hash |
| Production | 给 Authoring 受控素材观察/必要预览/可用区间/语音时序；代码处理身份、路径、时钟等确定性内容，模型负责创作安排 | 隔离 Authoring、Run 转换器、vocabulary、SVML/SVS、局部修改保护 |
| Quality / Recovery | 实际输出检查，定位缺陷，在委托/费用边界内局部修复，只重查受影响部分 | 技术 QC、Review、输出绑定、反馈、恢复/修订 |

先覆盖现有 clear_memo_video，不建立通用风格 DSL 或多 Director 平台。声音、选材和剪辑参数可随内容变化，风格规则的适用范围不能被硬编码成固定视频。

## 6. 持续遵守的低打扰规则

| 当前机制 | 处置 |
|---|---|
| 页面 useEffect 推进制作 | 删除推进职责，页面只读状态/提交必要决定 |
| 正常路径逐 Need 人工匹配、重复试听声明、额外继续按钮 | 系统检查与后端推进替代；人工入口仅真实例外 |
| 非逐字脚本默认全面人审 | 按真实事实风险处理，不以普通改写触发审批 |
| 逐次生成/零费用 Build 重复确认 | 合并到明确委托；保留逐次执行与费用核验记录 |
| 模型填写已知身份/技术字段、猜语法 | 移入现有代码适配和组件辅助 |
| 同一可信输入重复昂贵检查 | 按输入身份及检查版本复用，变化后失效 |
| Stage / Attempt / Runtime / SHA 操作入口 | 必要语义内部保留，退出正常 Creator 路径 |
| style pass 混同机器检查和用户接受 | 分清证据，不用人审证明系统已执行 Mode |
| 风格一致性作为后续补强 | 取消，纳入本轮 V1 完成条件 |

## 7. 全链验收覆盖（已有回放上增补，不从第①步重做）

以下是全链依赖与验收覆盖；本轮完成状态以顶部任务表及 Current State 的最终证据为准。每项遵循 root cause → minimal fix → targeted verification。优先扩展既有高价值测试，不要求新增测试文件或数量。

| 步骤 | 实施 | Replay / Contract / Fixture 验证 |
|---|---|---|
| ① 委托与持续交付 | 后端唯一推进者、授权、派发、恢复、停止条件；内部调整与实质变更分开 | 假执行器验证关页、重启、重复/并发事件、提交超时；不丢任务、不重提、不越授权，不动旧作品 |
| ② Director 决策传递 | 在现有 Planning/Need/Authoring 落实执行要求；修正 Truth 默认阻断；固定有效 Creator/Mode 上下文 | 同 Mode 不同 Content 保留开放叙事；风格要求进入真实执行输入，内部调整不重复确认，越界停止 |
| ③ Material / Voice | 风格偏好、观察、排除/替换/补料、朗读参数、音频时序 | 标题相符但画面不符、主体晚出现、风格不符、权利缺失、旁白过长；验证实际请求与时序合同，已有音频不再生成 |
| ④ Production | 根据素材区间与音频时序原生编排，确定性技术辅助、字幕与混音 | 已存 Planning/Bundle 局部回放及本机静态合同；时序、取片、配乐变化、局部修改不漂移声音/文字；不提交真实 Build |
| ⑤ Quality / 修复 | 实际输出检查、缺陷定位、有界局部修复 | 既有/确定性短媒体：近黑主体、低对比字幕、旁白截断、BGM 过强、内容错配；检出关键问题、只修相关部分、不无限循环 |
| ⑥ 跨内容回放 | 同 Creator/Mode 的 3～5 个不同主题串接局部能力 | 固定执行结果和观察证据验证风格贯穿且内容/叙事不同；恢复不改风格、不重复 Provider |

① 完成不等于产品完成，不能只自动串联旧链路。⑤ 和⑥完成后才评估真人验收准备度。

## 8. 首版质量边界

- 内容符合委托，没有未经支持的身份或事实表达。
- 实际使用区间呈现所需主体，裁切和字幕不破坏可读性。
- 旁白完整，字幕有实际语音时序依据，BGM 不明显压住旁白。
- 关键音画与剪辑符合当前 Mode，避免明显重复、空转或风格偏离。
- 确定性指标用确定性检查；内容/素材关联和必要风格判断用实际媒体观察。软偏好允许记录偏差，不把所有审美变成强制门禁。
- 分析能力缺失不以人工已确认填补，不伪造自动 PASS；Fixture 通过不能宣称真实感知效果已验证。
- 首版可审阅与用户接受/Selected Output 分开；最终确认仍绑定当前输出并保存内容库，不自动发布。
- 接受和入库不等于取得发布许可。实际选用素材的使用范围随导出、审片和内容库保存；仅限内部制作的成片仍可被接受与保存，发布时继续遵守原有使用范围和最终审片要求。

## 9. 执行边界与交付

本 Goal 已获实现授权。保持 Creation/Preparation/Planning/Material/Hypit/Review/Selected Output 主链，不改变 Material Layer V1.3 的素材/权利/匹配/准入语义，不大规模重构，不顺带扩展修改类型。

本轮不修改或继续当前 Creation，不调用付费 AI，不启动真实 Build 或完整 E2E，不重载服务去推进现有作品。Provider 改动核对官方契约；Hypit 改动核对本机版本与源码。所有测试确定、隔离、不依赖真实凭证。

必要局部验证通过后完成相关 lint/build/compile 检查；检查 Secret、runtime、产物排除后按用户已授权要求提交并推送 origin/easel-studio。不得推 upstream、force push 或改写共享历史。

完成报告区分已实现、局部证据与真实验证缺口，使用 FIXED / PARTIAL / REMAINING / TESTS / READY_FOR_HUMAN_E2E。真实 E2E 由用户随后启动；不得把局部回放等同真人成片验收。

## 成片入库后的素材清理（2026-10-02 用户追加授权）

Creator 最终确认且成片成功注册内容库后，清理该 Creation 全部 Attempt 的 materials/assets 中媒体及非 JSON 附件，以及 materials 与 references 下的音画预览与素材副本。成功、失败及未选用素材均适用；保留方案、资产/观察/权利/费用 JSON 记录、制作工程及成片。只删除作品拥有的本地副本，不删除共享素材库或用户原始文件。

Selection 与入库先持久保存，再执行清理；清理失败记录 PENDING，重复确认可幂等接续，不能让清理失败丢失已确认成片。拒绝链接路径，清理与制作共用 Creation 执行锁。素材删除后旧片不能直接复用原素材修改；后续修改必须重新取得素材并遵守原费用边界。本次不扫描清理既有真实作品，不重载服务或推进生产。
