# Easel V1 New-Only → Web E2E 统一实施与验收标准（唯一已批准主方案）

> **状态：APPROVED_SINGLE_EXECUTION_STANDARD / IMPLEMENTATION_NOT_AUTHORIZED / PAUSED。2026-10-11 用户明确批准为 Easel V1 唯一主实施与验收标准；不再是候选方案。此前独立审核 DECISION=MODIFY 的三项 §8 修正已吸收，本次批准是用户决策，不伪称独立 Reviewer 再次给出 CONTINUE。V1 最长 900 秒、四种音轨及 R1–R6 不变；代码、ADR、部署、模型/媒体与真实 E2E 均未获本次执行授权。**
> **日期：2026-10-11。范围：Easel V1 的 Creation + Hypit 视频新生产主链。**
> **依据：**根目录 `AGENTS.md`、[`Easel 视频架构`](easel-video-architecture-v1.md)、[`Material Layer V1.3`](material-layer-v1.3.md)、[`ADR-001`](../decisions/ADR-001-creation-hypit-mainline.md)、[`ADR-004`](../decisions/ADR-004-material-layer-v1.3-baseline.md)、[`ADR-005`](../decisions/ADR-005-agent-result-processing.md)、当前源码和唯一 [`Current State`](../02_CURRENT_STATE.md)。
> **本文件是唯一已批准的未来实施与验收主方案（目标合同 R1–R6、U0–U6 执行顺序和完成标准）。批准的是“以此为准”，不是“已经实施”：当前实现、运行资格及正式冻结 ADR 的冲突仍须在另获 U2 授权后按 §5 解决；历史验收原件不改。**

## 1. 本次不可妥协的要求

1. **后端彻底 New-Only。** 产品视频执行中只能存在一套可调用的 Proposal、Planning、Agent 结果、Material、Authoring、Hypit、Quality 契约和唯一 Delivery Owner；不保留旧 Producer、旧 Writer、旧 Parser、旧 Compiler Policy 选择、双态迁移适配器、旧恢复重派或回退开关。返回 `410` 但旧实现仍留在后端，不算完成。
2. **Web 与后端共用正式行为。** Web 以服务端冻结合同、Delivery 状态和当前可执行的人类决策为准；不以局部 Attempt 字段组合出第二套进度状态机；不绕过 Rights、费用、Quality 和 Output SHA。旧视频制作按钮与旧客户端 API 物理删除，而非只隐藏。
3. **高价值测试优先。** 优先扩展已有受影响的合同/连续集成/真实 UI 场景；最少样例覆盖最大跨阶段风险。不得为每个接口、getter、常量或普通字段透传新增单元测试。删除只验证退役行为的旧测试，保留能保护真实领域不变量的回归。
4. **历史数据保全不等于历史协议保留。** 历史 Creation/Attempt、原始模型回复、receipt、SHA、费用、原请求和 UNKNOWN 状态保持字节不变；只允许通用只读证据归档/原件下载，绝不通过旧协议解释器重新产生业务 READY 或发起模型/Provider/Build。旧作品不能升级为新 Attempt；另建合法新 Creation 才能进入正式生产。
5. **不扩展业务范围。** Material Layer V1.3 的 MaterialPlan → Material Supply → MaterialBundle → MaterialReadiness → MATERIAL_READY、Director/Creative Mode 冻结、Human Rights/Cost/Review、Hypit 媒体准入不放松；禁止恢复旧 V0.1 的 ResolutionResult/BindingResult 执行语义（冻结 V1.3 §4A/§65）；不启动第二条生产链、不自动发布、不产生未经授权的外部付费操作。


### 1.1 已批准的产品选择（2026-10-11；A/B/C 均已确定，不再征询）

**A = 四种声音模式保留、统一单一 Proposal 版本（用户已批准）。** V1 同时支持静音 silent、纯音乐 music、纯旁白 voice、旁白+BGM mixed，不因废除旧协议而削减正常模式。统一正式 Proposal（目标版本 easel-video-proposal@4；**设计字段已完成 Main 自审，JSON Schema 尚未实施/注册**），按 audio_mode 条件绑定：静音不生成或强制要求音轨；纯音乐仅要求已确认 BGM；纯旁白必须满足冻结 Voice 身份与脚本；混音按已确认方案同时满足 Voice 和 BGM。不得把 required 降为 optional，不能强迫静音/纯音乐伪造 VoiceProfile；含旁白模式的预置音色、语言与权益须严格绑定。新作品不能再通过 @2/@3 分叉生产，前端创建/确认/恢复与后端校验必须完全相同。

**B = Web 是 Creator 工作台，不是视频工程调度台（用户已批准）。** Web 保留：创作讨论/方案修改与确认、提供素材线索、Truth/Rights/素材组合审核、有可靠上界的费用授权、播放/反馈/拒绝/批准成片、最终选片及历史只读查看。Web 不直接分派或重启 Preparation、Planning、Provider、Authoring、Hypit Check/Build/Export；所有生产阶段及合法恢复只由 Delivery Owner 执行。人工决策写入当前 Domain/Delivery 检查点，由 Owner 决定下一操作；不创建 Web 第二状态机或隐式预算授权。

**C = V1 时长最长 900 秒（用户 2026-10-11 已批准）。** 四种声音模式均在 1～900 秒设计范围内，不在本次方案中自行缩减到 300 秒。超过 300 秒仍须有真实、可复核的媒体检查与资源/耗时准入，不能用关掉 Quality、限制到前 300 秒采样、自动缩短或跳过用户确认来凑合；源码扩容、正式发布和任何有价调用都未因这个产品决定而获得实施授权。

**授权边界：**A（四音轨单 Proposal）、B（Web Creator / Delivery 单 Owner）、C（最长 900 秒）和彻底删除旧协议是已确认的产品决策。用户认可 Main 自审可以作为方案审查，但后续独立审计 MODIFY 及其 R1–R6 修订仍待新窗口复核；产品批准不等于授权修改正式 ADR、生产代码、运行配置、发布或任何真实模型/Provider/Build，后续实施须另行授权。

## 2. 当前源码审计：为何还不是彻底单线化

| 范围 / 代码证据 | 当前事实 | 硬切换目标 |
|---|---|---|
| `easel/integrations/result_protocols.py:12-50` | 新 Attempt 已强制五项 pin，拒绝旧/部分结果 | 保持严格唯一标准，不更换此处已验证的五项 pin |
| `easel/creation_preparation.py:732-754` | `planning_contract_version` 仍允许 `2/3`，有缺省版本及旧证据降级选择 | 删除 v2 注册/选择与旧运行续跑，所有新作品明确绑定唯一现行 Planning |
| `web/app.py:3009-3035` | `_material_planning_executor` 中 v3 与文件型旧 Producer 并行 | 删除旧 Producer 整段实现，不只是 `if` 屏蔽；新作品只调用现行 Semantic Planning |
| `easel/integrations/semantic_planning.py:28-83` | Compiler `@1`～`@7` 及多套 review target 仍受 policy 参数选择 | 保留选定正式语义策略，删除退役策略、注册表、降级默认与对应测试 |
| `easel/integrations/semantic_boundary_run.py:237-257` | 旧 journal/policy 与新版择一路径共存 | 新执行只有一类受支持 checkpoint/policy；历史 journal 只存档、不可恢复派发 |
| `easel/integrations/material_layer.py:398-425`、`output_receipts.py` | Planning manifest v1/v2/v3 和 legacy receipt policy 存在恢复判定 | 当前领域读取器只接收当前合同；删除旧业务 parser/恢复策略，原始证据用与生产解耦的只读归档访问 |
| `easel/creator_proposal.py:85-163`、`easel/creation.py:484-510` | 提案 `@2` 和 `@3` 仍可在新业务产生：无预置旁白先生成 `@2`，预置旁白绑定后生成 `@3` | 设计一个同时覆盖静音、仅 BGM、旁白、旁白+BGM 的统一当前 Proposal 合同；新业务不再生成 `@2/@3` 双版本 |
| `web/frontend/src/App.tsx:68-73` | Web 旧会话恢复仅接受 Proposal `@3` | Web 使用同一个 Proposal 类型与服务端版本/身份校验；非当前协议旧会话仅打开归档视图，不参与重新确认 |
| `web/app.py:1278-1659`、`web/frontend/src/lib/api.ts` | 旧直接 Handoff/Attempt/Authoring/Build/Export 路由多数现以 `410` 阻断；人类审批接口仍存在 | 最终删除退役 POST 路由/处理函数及前端调用，保留当前有效的确认、Rights、费用、Review、选择与只读查询 |
| `FilmOperatorPage.tsx:387-401, 982-991`、`hypit/service.py:2131-2223, 2280-2333` | Web 可按已导出文件进入人工确认；服务端 Review/Selection 缺少同一 Output 的当前 System Quality READY 硬准入 | 由后端统一检查 System Quality、技术 QC、SHA、人工批准和 Content Library 选择；Web 在真正可审阅时才开放最终批准 |
| `FilmOperatorPage.tsx:743-763`、`material_recovery.py:483-489` | Web 默认 `allowLicensedBgm=true`，后端可删除 BGM `required_source_kind=stock` | 普通补料不能修改冻结来源硬约束；确需改变则重新明确确认版本化上游方案，绝非 Material 自动放宽 |
| `hypit/service.py:1395-1409`、`FilmOperatorPage.tsx:381-386, 662-675` | Provider 收费情况 `estimated_usd=None` 时不能证明聚合上限，UI 可能卡在审批 | 明确不可证费用的 `BLOCKED` 和合法下一动作；零 Provider 费用/可证强上界的批准可继续，不以用户金额冒充 Provider 硬上限 |
| `hypit/service.py` 中 Hypit-only 旧 Attempt 兼容、`easel/creation.py:649+` 旧 Stage Writer 等 | 存在与正式视频主链职责接近的遗留接口 | 对所有视频调用方做可达性矩阵；未被合法新主链引用的旧视频写入器物理删除；无关非视频/第三方库行为不借机改造 |


| `web/app.py:685-691,4448-4458`、`skills/openclaw/{auto-short-video,video-production}/`、`web/frontend/src/lib/capabilityMenu.ts:269+` | `/api/skill`、普通 Chat/Skill 与旧视频 Producer 脚本可能绕过 Delivery | **R1** 删除旧视频 Skill 执行与所有调用通路，保留无关正常 Skill |
| `web/app.py:4492-4550`、`easel/creation.py:36-39`、`hypit/service.py:2226-2277` | 通用 DELETE 未保护 `outputs/_creations`；Selection Cleanup 遍历各 Attempt 并删除媒体 | **R2** 必要原件与 Content Library 成片受保护；仅清证明无引用的缓存 |
| `easel/creation_delivery.py:96-97,187-198,237-256,695-711`、`easel/content_assets.py:290-319` | Delivery 以 schema 判定 managed，后台扫描和 reconcile 可能写历史作品 | **R3** Preparation 前/Attempt 后分阶段强准入，覆盖自动/内部/CLI 写入 |
| `hypit/service.py:1945-1986`、`hypit/quality.py:165-168` | 静音未强制无音轨；Proposal 1～900 秒与 Quality 最大 300 秒冲突 | **R4** 四模式端到端音轨检测及未受支持时长显式阻断 |
| `hypit/service.py:2131-2333`、`easel/content_assets.py:183-211,290-319` | Review、Select、注册与 reconcile 尚未共享 System Quality READY 硬门 | **R5** 所有正式成片写入/发布出口统一 Final Admission |
| `semantic_planning.py:28-83`、`semantic_boundary_run.py:25-49,514-531`、`openclaw_delivery.py:231-248` | 多版 Compiler、Checkpoint/Journal、Reply Contract 可被选择 | **R6** 冻结唯一新生产 Policy、Checkpoint、Wire、Compiler、Consumer |

**证据边界：**上述是审查当前 dirty worktree 的静态源码结论，不是所有分支的动态可达性证明。此前 129 项针对性回归和前端 Build 不能证明当前 Web 已加载、正向 Delivery 到 MP4 已通，不能认定本方案已完成。

## 3. 切换后唯一的契约与业务 Owner

| 链路阶段 | 唯一正式契约 / Owner | Web 唯一允许的职责 |
|---|---|---|
| Proposal / Confirm | **目标唯一 `easel-video-proposal@4`**（设计见 §3.1，源码 Schema 待实现）；Creation 保存 SHA、四种声音模式与有条件的预置旁白身份 | 展示、讨论、修改、明确确认当前完整方案；合法静音/纯音乐/旁白/混音均可用，不保留 `@2/@3` 双 Producer |
| Delivery | `easel-creation-delivery@1`；Creator 的唯一持久工作流 Owner | 读取服务端状态、需要用户介入的事项、已有证据及历史记录；不调度具体生产步骤 |
| Planning / Truth | 固定 **唯一现行 Semantic Planning vNext 策略**（受当前冻结源码确认），身份与引用由程序绑定；Truth `truth-source-ref@1`、Script Ledger `easel-script-claim-ledger@3` | 只展示事实缺口、原件与明确审核入口，不重派 Planning，也不伪造来源 |
| Material / Rights | Material V1.3 Domain/Owner；Observation `material-observation-delta@1`；`MATERIAL_READY` 仍由领域 Gate 计算 | 必要的 Rights/Match/组合确认及对已批准范围的补料建议；无权修改冻结 Need/来源硬约束或直接调用 Provider |
| Native Authoring / Hypit | `easel-hypit-source@1`；Delivery 调用正式 OpenClaw 与 Hypit Check/Plan/Pricing/Build/Export | 只读状态与产物；保留具备强约束的费用批准和明确取消，不直接 Authoring/Build/Export |
| Quality / Final Review | `quality-review-delta@1`；系统 Quality READY + 当前输出 SHA/技术 QC + Creator 真正审核 + Selection / Content Library | READY 以前可预览并提交反馈，但不能批准正式成片；确认按钮只能对应已批准的当前文件 |
| 历史作品 | **通用不可变原件归档**；非旧业务协议运行器 | 只读查看元数据/原件 SHA/调用账和下载原始证据；不调用历史 Parser、Writer、Domain READY 或执行操作 |

**Proposal 版本说明：**用户已经批准 A（四种模式、单一新版本）；`@4` 的方案设计经 Main 自审认可，但尚未在运行代码中登记，不等于生产上线。不能放宽原 @3 的预置 Voice 义务却沿用 @3 编号；正式切换后 Web/后端生产统一采用 @4，旧 @2/@3 仅归档只读。

**Web 状态原则：**不另外造一套前端状态机。后端可在现有 Creation/Delivery 读取接口返回纯派生的 `allowed_actions` 与 `blocking_reason`（不新增持久状态）；Web 根据服务端当前身份、阶段、SHA 和授权渲染按钮，不能用 `currentOutput` 等局部信号推断可完成。


### 3.1 单一 Proposal 的目标合同（自审修正）

**新生产唯一 Proposal = easel-video-proposal@4（目标设计；尚未写入源码）。** 沿用既有四段明确内容 treatment、script、scenes、sound（均为非空字符串；script 是作品文字事实，不代表静音/音乐模式也需要朗读），以及 specs 对象：duration_seconds 为已获用户批准的 1～900 秒明确整数（目标协议；现行 Quality 只支持 ≤300 秒，正式支持 301～900 前必须完成 §3.5 扩容并以当前能力 fail-closed）、aspect_ratio 与 language 为现行合法枚举、audio_mode 仅有 silent/music/voice/mixed；可选 specification_notes。所有字段必须由已确认的文字/选项产生，不使用模型猜测隐式默认值；附加字段、未确定设置、伪造身份与不一致的 digest 均拒绝。新业务不再按模式切换 Proposal 版本。

| audio_mode | 必需且允许的音轨 | Voice 身份 | 必须拒绝的降级 |
|---|---|---|---|
| silent | 不产生 Voice、BGM 或其他音轨；script 仍可承载文本/字幕意图 | 不允许 voice_profile、sound_source 或 Voice Need | 不得默认补声音 |
| music | 已确认的 required BGM Need，不含 Voice | 不允许 Voice 绑定字段或 Voice Need | 不得无授权省略 BGM 或补旁白 |
| voice | 一个与已确认 SCRIPT 全文对应的 required Voice Need，不含 BGM | voice_profile 和 sound_source 必需，必须匹配当前已验证的 V1 预置身份、语种与朗读内容 | 不得因权益/素材不齐退化为无声 |
| mixed | required Voice + required BGM，按实际确认的音轨分别验证 | 同 voice | 不得将任一 required Need 变 optional |

本轮不扩展新的 Provider 音色选择；voice_profile 只能是当前已核实的正式音色身份，Provider Voice ID 仍停留在 Provider Adapter。sound_source 保留未加工的原始声音设计，展示 sound 由现行受信任渲染规则派生并重新核验。voice/mixed 还需要独立的 TTS/素材额度、用途和 Rights 许可；缺任一证据即 BLOCKED，而非私自改模式。除明确批准的其他音效外不暗加音轨；silent 必须始终无声。

**Hash 和确认一致性：**从 schema、四段正文、完整 specs、可选 specification_notes、仅 voice/mixed 才存在的 voice_profile/sound_source 组成白名单 payload，按与现行后端一致的确定性 JSON 序列化（ensure_ascii=False、sort_keys=True、紧凑分隔符）计算 video_plan.sha256；revision、updated_at 仅为元数据，不参与哈希。分别持久绑定当前 Creator/Mode 快照、聊天上下文 SHA、Proposal SHA、文字使用授权摘要、付费/媒体授权作用域及确认时间；一切实际动作由后端重校验绑定与身份。浏览器丢会话后只能按原 session_hash + Creation ID + 当前 @4 和有效 SHA 恢复同一作品，不能把旧 @2/@3 自动升级或带入新委托。

**文字用途授权必须按模式收敛：**现行 easel-input-use@2 对无旁白作品也显示预置旁白合成授权（easel/creation.py:437-456），这是当前设计遗漏。建议统一新委托声明为 easel-input-use@3，并把提案音轨模式、plan SHA、文字来源与操作范围纳入声明摘要。silent/music 不包含旁白合成权限；voice/mixed 才在明确选择、合法身份、预算和权益均满足时允许旁白合成。文字改写、生图/视频用途需要相应明确范围；文字使用权不等于实际收费请求可提交。旧声明与已确认旧 Proposal 只作为原件保存，不成为新生产授权。

### 3.2 Web / Delivery 的动作边界（唯一状态源）

Delivery 是唯一生产 Owner；不新建 Web 状态机。Web 读取服务器从当前 Creation / Delivery 派生的 allowed_actions、blocking_reason、active_attempt_id 及 Proposal/Plan/Bundle/Output SHA 等身份（投影不持久化、不构成授权）；**每一个写入 POST 必须在原 Domain/Delivery 层重新校验身份、修订、SHA、Rights、费用、幂等和锁，过时就拒绝，绝不相信缓存的按钮状态。**

| 服务端当前证据 | Web 允许的人类意图 | 唯一执行 Owner |
|---|---|---|
| 当前 @4 Proposal 待确认 | 确认、修改或重开方案 | Creation 冻结委托，Delivery 自动决定 Preparation |
| Truth 需人类核对 | 基于原件审阅事实 | Truth Owner 记录；Delivery 决定下一步 |
| Material 缺 Rights/Match/候选 | Rights、Match、组合确认；提交补充素材线索 | Material Domain 验证；实际检索/生成/恢复只有 Delivery 调度。Web 旧 materials/recover 直接执行口必须删除 |
| 明确报价与可验证的本次现金最高风险 | 批准与报价/Plan 指纹绑定的本次金额 | Delivery 重验后才能 Build；上界不明则阻断 |
| 当前失败且原运行已知确定终态 | 向 Delivery 申请恢复当前检查点，不指定底层步骤 | Delivery 按原调用账和重试上限判定，绝不由 Web 直接重派 |
| PENDING/SUBMITTING/UNKNOWN/Quality 运行中 | 只读观察、必要的明确停止意图 | 原请求对账，绝不因刷新/切换会话而再次提交 |
| 已导出 MP4，System Quality 尚未 READY | 预览、拒绝、反馈 | 保存反馈但不能 Approved/Selection |
| 同一 Output SHA 绑定的 Technical QC、System Quality READY、Rights 已核实 | 人工批准、拒绝、反馈、确认最终选片 | 后端再次校验才允许 Selection / Content Library |
| 历史退役 Attempt/Proposal | 查看原件和费用/运行证据 | 仅静态读取；所有业务写入禁止 |

保留审阅、Rights、费用、反馈等正当人工接口，不保留 Web 手工 Handoff、Attempt、Author、Build、Export、Provider、直接 Material 恢复路由；取消制作如需保留也仅写入 Creator 停止意图，由 Delivery 在真实远端执行状态许可时处理。不存在服务端无法理解但由前端自行推进的 READY。


### 3.3 R1/R3：生产入口闭包与分阶段新协议准入

**彻底 New-Only 的证明基于所有真实入口，不是文件名搜索。** 覆盖 React Creator、`/` 缺构建时旧静态首页 fallback、`/static/`、`/onepage`、`/api/skill`、普通 Chat→OpenClaw Skill、各可执行视频 Producer Skill（至少 `auto-short-video`、`video-production` 及 scripts；其他 `layer: produce` 视频 Skill 也逐项检查）、CLI `record`/Stage Writer、旧 Hypit-only/API POST、Material Recover 直接路由、内部函数、Delivery 自动扫描/冷恢复、Content Library 注册/reconcile/发布/删除。**旧视频 Producer、脚本与可执行注册需物理移除，不能只隐藏菜单或永久返回 410。** 无关非视频 Skill、当前可复用 Provider 底层工具及安装中的 Hypit 语法库应保留；但不得编排第二条 Easel V1 视频主线。所有入口需做生产者→消费者/文件副作用闭包，再以高价值入口验证。

`is_managed()` 仅匹配 `delivery.schema` **不足以证明新作品资格**。统一使用服务端生产资格校验，不另造工作流：

| 阶段 | 必要身份与准入 | 不可做的事 |
|---|---|---|
| **Preparation 前、Attempt 尚未创建** | 正式新 V1 Creation + Creator/Creative Mode 冻结身份、Proposal @4 有效 SHA、真实确认/委托/本次协议身份、已批准用途与预算作用域、Owner 锁和幂等请求 | 不能因为没有 Attempt 就阻止合法首次 Preparation；旧 @2/@3、旧 Creation 不得回填或自动升级 |
| **Attempt 创建后** | 上述委托 + 同属 Creation 的有效 Attempt/原 Run 身份、固定上下游 refs/SHA、**五项当前 Result Pin**、当前状态和费用/Rights 资格；所有写入重验 | 不能只看 Delivery Schema 或客户端按钮；后台扫描、retry、HTTP、内部函数、CLI、Review/Selection、reconcile 都不可越过 |
| **历史 PENDING/SUBMITTING/UNKNOWN** | 固定原 operation/run 身份，仅非业务解释地读取终态/证据，账单与调用占用不变 | 不能解析旧业务结果、重派模型/Build、注册 READY、迁移 pin、释放未知成本或借观察触发删除 |

新委托协议身份只能在首次正式确认时冻结，不由时间戳推断，也不追认旧作品。后台 `enrolled_creation_ids/next_operation/serve_delivery` 在执行前核实当前资格；历史只读观察与新生产权限物理隔离。通用函数调用方同样受保护，不能只在 API 做门禁。

### 3.4 R2：不可变历史证据与删除/清理边界

必须保留完整可复核原件：原请求与模型回执、失败/UNKNOWN 证据、调用身份、费用、SHA、Rights/来源证明、被任何历史 Attempt 依赖的音视频/图像字节和最终已选/入库成片。**只有 JSON/SHA 而被引用素材已删，不算保全。** 不要求永久保留一切临时缓存。

- `DELETE /api/output/{path}` 不得触及 `outputs/_creations/**`、其父级或派生保护路径，也不得删除已登记/正在登记的 Content Library 成片、manifest 或原始 Attempt 视频；需核对路径遍历、目录递归、symlink 与任何其他可写文件管理入口。保留正常非受保护用户产物的文件管理，不新增历史协议适配层。
- `_cleanup_completed_materials` 不能因为选中某个 Attempt 就遍历删掉其他 Attempt 的必要媒体。删除前通过 Planning/MaterialBundle、Rights、Failure、Quality、Review、历史引用与当前选片索引做依赖检查；引用情况不明则保留。只允许可证明未引用、非原件、可安全重建的中间缓存按清单删除，并记录实际删项。
- `register_selected_output` / `reconcile_selected_outputs` 只允许对当前合格新生产进行幂等业务补登记；旧记录只读。历史证据保留原位置、原 SHA、原状态和原账单，不创建会执行旧 Parser/Writer 的兼容归档系统。预备实施时先保护 dirty/untracked 工作区和审计原件。

### 3.5 R4：四种声音模式贯穿最终 MP4

同一冻结 `audio_mode` 从 Proposal→Planning→required Need→Material/Rights→Native Authoring→Hypit Export/ffprobe→Technical QC→System Quality→人工审片保持一致。复用 `hypit/quality.py` 现有 Voice 信号检查与 BGM 采样校验，不新增音频框架；**信号保真不是 ASR，也不能代替 SCRIPT/Truth 和人耳审阅**。

| 模式 | Planning / Authoring 必需条件 | MP4 / System Quality 准入 |
|---|---|---|
| `silent` | 不创建 Voice/BGM Need，也不编排音频轨 | **不允许存在任何音频流**；`require_audio=False` 不等于静音通过 |
| `music` | required BGM，禁止 Voice，Rights 与来源 SHA 绑定 | 必有音频流，当前 BGM 信号/时段可验证；不可验证为 INCOMPLETE |
| `voice` | required Voice，对应完整 SCRIPT、预置身份和授权，无 BGM | 必有音频流，当前 Voice 信号可辨；来源文本、身份和人工语义审阅独立验证 |
| `mixed` | required Voice+BGM，分别符合 frozen Need 和 Rights | 有音频流且两项信号都可验证；混音遮蔽/证据不足不能放宽 required |

**已确认产品范围（2026-10-11）：V1 视频正式支持 1～900 秒，最长 15 分钟。** 这是用户确定的范围，不再以 300 秒替代，也不需重新询问时长选择。`duration_seconds` 必须是 1～900 的明确整数；`901` 秒以上或未明确时长一律不能确认生产。**当前源码尚未达到 900 秒**：`easel/integrations/hypit/quality.py:165-168` 仍只接受 ≤300 秒，在扩容、同版验证和加载前，系统应 fail-closed 明确阻止超过当前真实验收能力的有价制作，绝不把“目标支持 900”伪装为“已实现支持 900”。正式硬切换要覆盖并验收 301～900，而不是永久阻断。

**Quality/Technical QC 扩容必须真实闭环：**逐一排查并消除与 300 秒绑定的代码、资料及配置硬限制，包括 `quality.py` 中多个音频/Voice/BGM 的 `-t 300` 截断、`_decode` 固定 60 秒子进程超时、`service.py` 的 `ffprobe` 30 秒和全媒体解码 120 秒超时、各种音频/视频全量读取的内存与响应容量；依据实际处理阶段和媒体规模设置可证明的有界资源/时限，不盲目把全部常数改为 900 或取消超时。优先复用现有检查算法并采用流式/分块/有界采样及证据汇总，保证音频参考与输出时间轴、fade/ducking、Source SHA、输出时长与冻结 SCRIPT/scene 能正确对齐，检查覆盖**片头、片中和 900 秒附近片尾**，不能只验前 300 秒、只看一个音频流或让结果因抽样不足被当作 PASS。音效、Rights、Output SHA 与费用/UNKNOWN 准入照旧。

**完整上线验收：**在明确授权的无付费本地内部集成中覆盖 300 秒边界、至少一个 **301～900 秒的正向真实 MP4/Quality 端到端样本（优先 900 秒含音轨）**，并对 900 秒最大值及 >900 秒拒绝做定向合同验证。检查长视频解码、检测耗时、峰值内存、临时文件占用、超时/失败分类与冷恢复幂等；资源无法证明受控、任何 required Voice/BGM 不可验证或实际媒体验收失败则维持 BLOCKED/INCOMPLETE，不降级 PASS。四音轨模式继续复用既有 Quality 能力，测试只覆盖代表性长片+参数化风险，而非四类各做一条 900 秒昂贵测试。



### 3.5.1 R4-P0：Material BGM 的 301～900 秒源文件准入

**900 秒支持必须贯穿 Material Supply / Readiness，不能只改最终 Quality。** 已核源码：`easel/materials/application/music_observation.py:68-73,111-145` 限制解码 `-t 301`、有效 PCM ≤300 秒、观察报告时长 ≤300 秒、窗口数 ≤61；`easel/materials/application/music_reassessment.py:54-59` 和 `easel/integrations/material_layer.py:2649-2675` 的 BGM 候选上限为 300 秒；`easel/materials/application/matching.py:104-108` 需要合格 Music Observation。上述入口须一致支持合法 **301～900 秒 BGM 原始素材**的观察、重评、Match 与 MATERIAL_READY，继续保留原 Need/Source SHA/Rights/冻结来源约束；不能将长素材长度悄悄截成 300 秒，不能以 Creator 审核或短 BGM 循环绕过必要的原件观察。

复用现有 `music_observation` 模型与 `MaterialMatcher`，对 10 秒窗口/5 秒步进、音乐覆盖率、未知时段、首尾连续覆盖等原判定规则做按**实际素材时长**的有界校验；61 窗限制、本地 FFmpeg 60 秒及观察子进程 240 秒超时、报告 2 MB 上限要根据资源实测做受控扩容/分批，不得简单删限或把不完整样本认定为整段 PASS。若观察契约语义改变，应冻结唯一现行策略/摘要并保存既有报告原件为历史只读，绝不恢复旧执行双轨。

**证据不能混淆：**短 BGM 按 Creator 冻结方案合法循环至 900 秒，能够证明该作品的音轨编排，却**不能证明一条 301～900 秒的长 BGM 源文件本身可通过 Music Observation/Reassessment/Match**。

### 3.5.2 R4-P1：长 Voice/TTS/ASR 的执行约束

`easel/materials/application/voice_delivery.py:85-107` 当前本地全量识别/Word Timing 子进程超时 180 秒，`easel/integrations/material_layer.py:1467-1485` 用识别结果绑定完整 SCRIPT 与音频时序；`easel/materials/providers/minimax_speech.py:63-92` 的 TTS 单次输入限 10,000 字符，HTTP 超时 120 秒。后续须对合法最长 900 秒的含 Voice 作品核实**完整 SCRIPT、预置 Voice 身份、源音频 SHA、字词时间轴和片尾覆盖**，并实测本地 ASR 的有界耗时/内存/输出容量、Provider 的长度及超时/权益边界；不能因这些固定值就假定 900 秒必然失败或必然成功。

超出单次 TTS 合同的输入，必须在有价执行前明确阻断；若确有必要分段，须由唯一 Delivery 以冻结 SCRIPT/段落顺序、每段请求 SHA、预算上限、音色身份和实际产物时序确定性绑定，不得静默删改或换声音，不引入第二生产 Owner。**TTS 已提交后超时/网络或返回结果不确定＝原请求 UNKNOWN、费用/次数占用保留、不自动重发**；本地 ASR 可在原音频完整时仅重做不收费的观察，不能因观察失败重新生成/收费。完整字词时序无法核实则 BLOCKED/INCOMPLETE，不得宣称 MATERIAL_READY。

### 3.5.3 R4-P1：900 秒 MP4 时长硬上限、全片采样与视觉覆盖

`easel/integrations/hypit/service.py:2040-2048` 对 Handoff 时长允许 `maximum+0.5` 容差。该容差只能用于**非产品上界的期望时长/编码误差判定**，不能使**实际 MP4 超过 900 秒**仍取得 READY；需用 FFprobe 容器与各轨道可核证的有效时长设定单一最大边界，`duration ≤900`、`>900` 必须拒绝，不能自动截断或丢弃尾部以掩盖超限。

`hypit/quality.py:165-193` 的 `fps=2` 全片低分辨率分析必须同时校核声明时长、应有采样时点/帧数、实际首/中/尾时间覆盖及解码终点，不能只以 `len(raw) % frame_size == 0` 认为整片完整。`hypit/quality.py:599-603` 的语义代表帧取样，不能因已有 ≥5 帧却全部集中在前段就不补尾段；**必含片头/中段/接近真实片尾的代表帧**，再与 Voice cues、表达义务合并去重并沿用现有有界分批机制，不增加逐帧模型审片。Voice/BGM 当前源信号也必须核对接近片尾的合法区间；技术全片覆盖与语义代表性分别留存证据。

900 秒 16 kHz 单声道 float32 音频原始约 57.6 MB，多个参考轨和浮点中间数组会显著增加峰值内存。须采用受控分块/有界采样和完整时间覆盖记录，验收内存、耗时与资源上界；超时、数据缺段、无法证实尾部或 PCM/视频容量溢出，均 fail-closed，不可降低 Quality/Rights/UNKNOWN 门禁。

### 3.6 R5：全部正式成片出口的统一 Final Admission

复用现有服务端 Quality/Technical QC/Rights/Output SHA 校验，以**一个确定性、无新持久状态的 Final Admission**在业务更新现场反复验证，而不是增加一套 Review 状态机。强制作用于人工 `APPROVE`、`select_film_attempt`、Content Library `register_selected_output`、`reconcile_selected_outputs`、正式资产/manifest 有效性检查和所有手动发布准入。

同一个当前 Creation/Attempt/Build/Output SHA 必须满足：冻结计划与素材版本有效；Technical QC PASS；**System Quality READY** 绑定原媒体字节；相关 Material Usage、Rights/Attribution/来源准入有证据；实质性 Truth/Style 和 Human Review APPROVED 绑定同一视频。人工批准前只执行不含 Human 状态的技术/系统准入核验；正式 Selection、入库与发布另加当次 Human APPROVED 校验，避免“批准操作必须已经批准”的循环条件。Quality 未 READY 可播放、拒绝与提交反馈，不能写成已批准。入库≠获得发布授权，发布权仍单独检查。全部写入口在锁/事务内重新验证，旧 Attempt 不得通过 reconcile 补写，Web 的 phase/allowed_actions 非权限凭据。

### 3.7 R6：唯一新 Planning 版本矩阵

**本轮核实的新任务目标值**：`semantic_boundary.POLICY = planning-semantic-boundary@1`；`semantic_planning.POLICY = semantic-planning-compiler@7`；`semantic_boundary_run.STATE_KEY = semantic-planning-vnext`，新记录 `VIEW_JOURNAL = semantic-planning-checkpoint@9`、冻结 `VIEW_CHECKPOINT = semantic-planning-frozen@9`；`planning_structured.CONTRACT = planning-result-v3`、`VERSION = easel-structured-result@1`，Wire codec 为 `planning-xml-wire@1`，实际 schema SHA/Runtime fingerprint 由冻结输入/代码计算而不是以字符串猜测。消费者是程序绑定来源、ID、hash 后由当前 V1.3 MaterialPlan/Need 领域验收，结果产物用五项新 pin。

现存 `semantic-planning-compiler@1～@6`、旧 checkpoint/journal、`planning-result-v1/v2`、文件型 Planning Producer 与 legacy receipt/manifest 可执行策略均需按调用闭包精确退役；不能留下默认回落到 @6 或让旧 journal 重派。新 Attempt 初次委托即固定 Producer/Compiler/Checkpoint/Wire/结果消费者身份，冷恢复不能改版。部署前对照 `semantic_boundary_run.py:514-533` 的真实默认路径、A/B 输入视图、Structured Request Schema SHA 和当前 Runtime patch 全量 fingerprint 定点复核；发现新组合不成立时先回审方案，**不选旧版本兜底**。

## 4. 后续实施顺序（仅方案，未授权执行）：单一受测版本硬切换

> 本节 A–D 是**技术改造工作包**，其生效先后、与真实 E2E 的关系和完成判定统一服从 §8 的 U0–U6；不得把 A–D 当成另一套平行实施流程。

### A. 切换前只读基线与入口/证据闭包

- 固定 `easel-studio` HEAD、dirty diff、未跟踪方案、实际 Web/Gateway/Hypit/Skill 配置及服务加载指纹；保护用户现有变更。将 `outputs/_creations`、库中已注册成片、各 Attempt 原件/媒体引用/费用及运行 UNKNOWN 逐类列入不可丢失清单，禁止 checkout/reset/clean 破坏证据。
- 按 §3.3 建立 **React + 旧 static/onepage + /api/skill + 普通 Chat + 视频 Producer Skill/脚本 + CLI/Stage + 旧 API/内部直接函数 + Delivery 自动扫描 + Material recover + Quality/Selection/Content Library/reconcile/发布/删除** 的入口与副作用矩阵。逐入口标明允许的人类动作、只能由 Delivery 执行的生产动作、遗留调用的物理删除目标和被引用证据；不能因为代码无 legacy 字样就宣称闭包。
- 原 PENDING/SUBMITTING/UNKNOWN 只按原操作身份观察和对账，安全终态未知则冻结原件、调用和预算，不跨版本重派；原 7 Attempt/24 次调用/15 捕获和共享新增现金 ≤¥10 不重置。记录 **用户已确认的 V1 最长 900 秒**，将 301～900 秒 Quality/媒体/资源扩容列为 New-Only 发布的必备工作；未实施前保持当前真实能力范围的 fail-closed，不私自放宽原运行门禁。

### B. 后端单一协议、执行准入与证据门禁

- 对新生产只保留 Proposal @4 + 当前五项 Result Pin + §3.7 的唯一 Planning Executor/Compiler @7/Journal/Checkpoint @9/Wire/Consumer；逐调用方**物理移除**旧 Planning Producer、@1～@6 编译/旧结果执行选择、旧 Stage Writer/CLI、旧 Hypit-only 生产和退役视频 Skill Producer/脚本注册，不以 410、Disabled Flag 或兼容适配器永久残留。无关的合法非视频/工具能力保持原职责。
- 按 §3.3 在 Creation 的 **Preparation 前**（无 Attempt）与 **Attempt 后**（固定五 pin）使用同一现行生产资格，不把 `is_managed()=delivery.schema` 当充分条件；`enrolled_creation_ids`、`next_operation`、`serve_delivery`、重试、HTTP/CLI/内部函数、Review/Selection/reconcile 的写入/恢复均遵守。旧 UNKNOWN 观察与生产分离。
- 按 §3.4 加固 `DELETE /api/output/{path}` 对 `_creations` 和注册库成片的绝对保护，以及一切等价文件写入口；`_cleanup_completed_materials` 先依据原件引用核验，不能删除其他 Attempt 的必要媒体，仅释放被证明无引用的可重建缓存。
- R4 按 §3.5–§3.5.3 **从上游 Material 到最终 Quality 统一支持 301～900 秒**：BGM 源文件 Music Observation/Reassessment/Match 及 61 窗/300 秒限制、Voice/TTS/ASR 的 10,000 字符与 120/180 秒有界执行、未知远端请求冻结；下游技术采样与语义代表帧覆盖片头/中/末，MP4 实际时长硬上限 ≤900 秒。不得只把 Quality 的 300 改为 900、拿短 BGM 循环代替长音源验收、仅增超时或跳过 Rights/完整时序。按 §3.6 以同一 Final Admission 保护 Human APPROVE、Selection、Content Library 注册/reconcile、发布出口，READY 前可反馈/拒绝而不能正式批准。
- Material 恢复不能放宽冻结 `required_source_kind` / Need / Director/Creative Mode、Rights 和 Source SHA；实际供给仍经 Delivery 的当前操作资格调度。费用上界、UNKNOWN、扣费/提交幂等仍以原始合同为准。

### C. Web 按同一合同接线并同步发布（与 B 不产生可用双轨过渡版）

- 创建/预览/确认/修订/冷恢复只接受当前 @4、时长 1～900 秒及对应 input-use 授权，展示四种合法模式、真实阻塞原因、有效费用范围；**正式同版验收后 301～900 必须能合法确认/制作，>900 必须拒绝**。在质量检查尚未扩容并加载前，超过现行真实能力的请求应显式 BLOCKED，不能先付费后发现 Quality 无法验收。历史旧 Proposal/Attempt 仅只读，不迁移或继承授权。
- 仅呈现服务端 Delivery 派生 `allowed_actions`、`blocking_reason` 和当前 Output SHA，撤销前端独立 phase 对 READY/可批准的判定。保留 Truth、Rights/Match、组合选择、费用批准、播放、反馈/拒绝、合格成片批准与选片；Web 不直接启动 Skill、Material Recover、Preparation、Planning、Provider、Authoring、Build、Export。
- 消除 React 和旧静态页/onepage 对已退役视频 POST 的访问或静态入口可见性；发布时如 React 构建缺失，不能 fallback 到仍能启动旧视频 Skill/Producer 的旧页面。后端、Web 构建、Skill 注册表与 OpenClaw/Hypit Runtime **一套可追溯的受测 fingerprint**；切换出错时停止新制作并修复当前版本，不恢复旧协议双轨。

### D. 最小高价值验收与冻结（本轮不执行）

- 一条真实 **当前五 pin** 的新 Creation（在合法无 Attempt 时可 Preparation）沿 Delivery → Planning/Truth → Material/Rights/MATERIAL_READY → Native Authoring → 本地 Hypit Check/Build/Export → Technical QC/System Quality READY → Human Review → Selection → Content Library 连续内链，核对真实 MP4 SHA、Voice+BGM 信号；外部模型和有价 Provider 只在固定合法替身下验证，真实调用另行授权。
- 复用现有**一组四模式参数化正反验证**：silent 无音频流，music BGM 可核，voice 绑定 SCRIPT/音色，mixed Voice+BGM 均有证据。至少一条**接近 900 秒的无付费 mixed MP4 内链**核对 Output SHA、尾部音画、实际时长 ≤900 秒、耗时/内存上界；相同样本或最少一条定向补验，必须证明**真实 301～900 秒 BGM 源文件**通过 Observation→Reassessment/Match→MATERIAL_READY，合法长 Voice 能完成脚本/ASR/时序和 TTS UNKNOWN 防重派。短 BGM 循环不能充当长源验收；覆盖 300/900/901 秒边界与视觉首中末段，不按字段拆成大量单测。
- 少量关键负例集中验证：旧视频 Skill/Chat/CLI/API/后台自动恢复不能执行；历史原件及 Content Library 成片不能被通用 DELETE/Selection Cleanup 删除；旧 Attempt 任何补登记/Review/Select 均拒绝；Quality 非 READY 时 APPROVE/Selection/入库/发布拒绝；Material 冻结来源、Rights、可证费用上界和 UNKNOWN 原请求不被突破。
- 校验 Python compile、前端 lint/build、必要合同/集成回归、文件/证据 SHA 与 Git 差异，再用真实浏览器和受测服务加载指纹核对正向操作（无自动付费）。`HTTP 200`、旧入口变 404 或分模块用例 PASS 不等于真实 E2E；未经授权不做有价媒体或新 Creation 实时 E2E。


## 5. ADR 冲突与实施前评审

- 当前 **ADR-005 §2.2** 仍写「旧请求按原版本恢复」；**ADR-001** 还描述 legacy 视频行为可继续存在。这与用户本次的 **不保留旧视频协议及双轨** 决定存在显式冲突，不能在文档中悄悄假装已调整。
- 独立审计于 2026-10-11 给出 **MODIFY**，其设计修正已吸收；用户后来正式批准本统一标准。**当前已仅对 Current State、Roadmap、Creator Task 和 E2E 账本完成主标准/历史证据导航纠正**，V1.3 新生产链路不再用旧 V0.1 当正式目标。正式 **ADR-005 §2.2「旧请求按原版本恢复」与 ADR-001「旧视频路径仍可用」** 仍然存在决策层冲突，需在另获 U2 实施和 ADR 变更授权后定点修订，绝不通过用户批准主方案便宣称已修正式 ADR；ADR-004 / Material V1.3 冻结不变，历史原件与既成事实不重写。
- **本方案自用户 2026-10-11 明确批准后已是唯一正式实施与验收主标准**，不再是待审候选；它本身**不是已接受 ADR 的修订记录，也不等于已批准代码实施 Task 或 U2/U5/U6 执行**。文档导航已做最小前向对齐；实际工程修改仅在另获授权后归入唯一 Creator Task，不开平行技术方案或 Task。


### 5.1 历史第一轮架构预审（MODIFY，已由 §5.2 修订和覆盖）

**当时执行：**Main 根据当前源码、ADR-001/004/005 和原方案进行了第一轮只读审查，结论为 MODIFY，保留以下问题以便追溯修正依据。这不是独立 Astra Reviewer 意见；**当时用户撤回了子 Agent 审查；但之后用户另开窗口取得独立审计 MODIFY，当前判定以 §5.3 为准**。原有已接受 ADR 与 Material V1.3 不因预审而改变。

**历史 Main PRE-REVIEW DECISION = MODIFY；当时经 §3.1/§3.2/§5.2 修订，但后续独立审计仍发现 R1–R6，现以 §5.3 最新状态为准。**

**RISKS：**
1. **单版本 Proposal 的条件语义尚未冻结。** 当前后端 @2 仍可生成静音/纯音乐计划，@3 绑定预置旁白。如果只换版本号，不定义四种 audio_mode 的条件字段、Voice/BGM Need、语言、来源文本、授权与 SHA 计算，将会制造新的前后端不一致。需要确定唯一新版字段集，不能把 @3 的必需 Voice 条件原样套给 silent/music。
2. **物理删除旧协议与历史 UNKNOWN 的安全冲突。** ADR-005 §2.2 目前允许旧请求按原版本恢复；用户现在要求禁用和删除旧生产实现。应区分「不运行旧 Writer/Parser/Policy、不重新提交」与「按原 operation id 不解读业务内容地只读观察终态」；无法安全核实的旧活动请求保持冻结和原始账，不清理、不重派、不标成功。通用原件读取不能变相复制旧协议解释器。
3. **人工行为与正式就绪必须由后端闭合。** Web 可对未完成 Quality 的视频预览和给反馈，但不能将 Quality 未 READY 的成片批准/选片。服务端应核对同一 Output 的 SHA、技术 QC、System Quality READY、Rights、人工 Review 与冻结方案；补料不得放宽 required_source_kind，费用与 UNKNOWN 也不因页面确认而放松。
4. **New-Only 不能误伤基础工具或四种合法创作模式。** 删除范围是 Easel V1 旧视频可执行生产合同、生产适配和 fallback，不包括安装 Hypit 的当前本地语法、通用安全解析器、静态历史文件、无关平台。精确删除生产分支，避免顺手重构 Material V1.3 和 Domain。
5. **必须统一受测发布与动作身份。** 可从现有 Delivery 快照派生 allowed_actions / blocking_reason，但这是服务端只读投影，不新增持久状态机；所有人工 POST 必须再次检查 creation/attempt、版本、修订 SHA、权限、计价和有效状态，不信任前端旧按钮或缓存。New-Only 切换前须核对旧 PENDING/UNKNOWN，不部署新旧 Web/Backend 混合版。

**MINIMUM_CORRECTION（复核阶段的设计修正，不是实施命令）：**
- **R1 统一 Proposal 合同：**写清四个 audio_mode 的条件验证、Creator/Mode 冻结输入、声音身份来源、Rights/费用、SHA 与确认/恢复语义；推荐新 @4（仅候选版本号）。单版本下允许不同业务模式，但不能容纳旧版本 Writer。
- **R2 旧执行代码可达性闭包：**从 Web、Chat、CLI、Delivery Worker、自恢复、Hypit/Material/Quality 等所有生产入口，逐项对账旧 Producer、Compiler Policy、Parser/Receipt、路由/Writer、测试引用；明确物理删除与不可变历史原件读取的非执行边界。
- **R3 单一 Owner 的 Web 契约：**服务器端授权动作和阻塞原因成为权威，Web 只提交 Creator 决策；错版、过时/失效、未知收费和未知提交必须拒绝；没有独立 Build/Provider 等按钮。
- **R4 核心门禁：**Quality READY + 同一媒体 SHA/Technical QC + Rights + Creator Review 后才能 Selection；Material 恢复不放宽冻结来源约束。
- **R5 验收与发布：**一条含视觉/Voice/BGM 的现行五 pin、真实内部 Owner、本地 Hypit MP4 完整集成 + 一种不同音轨模式 + 关键反例和 UNKNOWN 冷恢复；复用测试、清理旧测试，不按接口数量增单元测试。Web 与后端按同一受测 Fingerprint 发布，不允许双轨过渡。

**原拟独立 Reviewer 输入包（已取消执行，仅作历史上下文）**：用户确认 A/B、ADR-001/004/005、关键 Proposal/Planning/Delivery/Quality/Material 源码。**用户已明确撤回子 Agent 审查，未启动任何独立模型审查运行。最终结论仅为 §5.2 的 Main 正式自审，不得声称 Astra 独立审查通过。**

**历史预审的收口条件已调整**：独立 Reviewer 项因用户撤销而取消；Proposal 目标合同和 Web/Delivery 行为由 §3.1/§3.2 和 §5.2 完成 Main 方案自审。ADR-001/005 的正式修订与旧代码可达性核对仍是以后获准实施前的必要工作；本轮不动生产代码。


### 5.2 历史 Main 自审结论（当时 REVIEW_PASS，已被 §5.3 独立审计 MODIFY 覆盖）

**审查身份：**用户撤回独立子 Agent 请求，要求 Main 自己再次审核，成功即可算复核通过。此处为 Main 的**正式自审**，不是独立 Astra 或第二模型的审查意见；没有启动子 Agent 审查任务、后台模型或媒体操作。§5.1 的 MODIFY 是更早的预审；本节当时判为 PASS，现已被 §5.3 后续独立 MODIFY 覆盖。

**历史判定（不再有效）：DECISION = CONTINUE / Main 自审 REVIEW_PASS；不得用作本次修订后的外部复核结论。**

**已消除的方案级问题：**
1. **Material 合同纠错**：原方案把旧 V0.1 的 ResolutionResult / BindingResult 误列为冻结 V1.3；已修订为 MaterialPlan → Material Supply → MaterialBundle → MaterialReadiness → MATERIAL_READY，遵守 material-layer-v1.3.md:300-311、3145，未恢复旧 Hypit Binding。
2. **四模式统一 Proposal**：§3.1 已明确单一目标版本、完整字段/散列、silent/music/voice/mixed 四条音轨矩阵及必需 Voice/BGM Need、预置身份与源文字；同步处理仅含旁白时的授权，避免静音/纯音乐被默认授予 TTS。
3. **Web/Delivery 人工责任清晰**：§3.2 将 Creator 决策与真正生产分离；Web 补料线索不能直接调用生产恢复；所有写入仍由服务端重新鉴权和核验身份。
4. **历史/旧协议删除不损证据**：旧 Producer/Writer/Parser/Policy/Route 在目标代码中物理删除；历史记录不做自动迁移，UNKNOWN 只允许原 operation 身份的非业务解释终态观察，禁止旧请求重发、升级或预算清零。
5. **最终就绪严格闭合**：系统 Quality READY、真实 Technical QC、当前 Output SHA、Rights、人工 Review 必须一致才可选片；Material V1.3 冻结来源硬约束不得被补料弱化；费用无证上界不得发起请求。
6. **最小验收与发布一致性**：一条代表性的五 pin 当前内部主链经真实本地 Hypit 产出 MP4（Voice+BGM）加另一音轨模式创建/恢复与最重要的失败/UNKNOWN 回归；Web/后端只发布同一受测指纹，不堆重复单元测试。

**风险已转化为后续实施前置，并非复核失败：**
- 当前受理的 ADR-001 仍允许旧业务路径、ADR-005 §2.2 仍允许旧请求旧版本恢复；两者必须在未来获得实施许可后先作定点修订。ADR-004 / Material V1.3 不能被本案改写。
- @4 与 input-use@3 是**本方案复核通过的目标合同**，并非当前运行中已注册的协议或已通过的软件测试；后续开发必须按字段、输入身份、来源、费用与状态实现验证，并追溯剩余旧代码全部实际调用链。
- 方案 REVIEW_PASS 不代表生产代码 New-Only 已完成、真实 Web 可用、正式 E2E 或付费请求获得授权。本轮没有运行产出 MP4 的集成测试。

**当时的历史 MINIMUM_CORRECTION 判定（已被 §5.3 覆盖）：当时自审认为风险已收口；后续独立审计补充 R1–R6。该时点 300/900 秒仍待确认，但用户随后已确定 V1 最长 900 秒（见 §1.1 C、§3.5）。** 对后续工程可能发现的 ADR/Domain 新冲突仍须暂停并另行复审，不得用已通过的方案掩盖未知风险。

**PAUSE：按用户明确指令，复核通过后立即暂停，不创建或派发子 Agent，不改生产代码、正式 ADR、Task，不部署或调用模型/Provider/Build。**


### 5.3 后续独立审计 MODIFY 与本次 R1–R6 方案修订（2026-10-11）

用户提供的新窗口《Easel V1 Web ↔ Backend New-Only 独立架构审计报告》结论为 **DECISION = MODIFY**，明确否定此前 Main `REVIEW_PASS` 可作为直接实施批准。因此 §5.1/§5.2 仅为历史审查记录，**本节覆盖其当前判定**；不冒充独立 Reviewer 已重新认可本次修改。

| 外部审计修正 | 本次已写入的设计/执行/验收边界 | 当前实施事实 |
|---|---|---|
| R1 全旧生产入口 | §2 源码证据、§3.3 旧 Skill/Chat/CLI/静态页/旧 API 全入口清单、§4/§6 | 仅方案，旧代码未删除 |
| R2 历史证据删除与 Cleanup | §3.4 原件/引用字节、`_creations` DELETE 保护、库成片和有界缓存清理 | 原件保护尚未实施 |
| R3 历史自动恢复与写入 | §3.3 **Preparation 前允许合法新 Creation 无 Attempt**、Attempt 后五 pin/委托资格，覆盖扫描/CLI/reconcile | 原有 `is_managed()` 行为未改 |
| R4 四声音模式和 900 秒上限 | §1.1 C、§3.5.1–3.5.3 已补充 Material 长 BGM 源文件 Observation/Reassessment/Match、完整 Voice/TTS/ASR/UNKNOWN、MP4 实际 ≤900 秒、全片采样与代表帧覆盖的实施验收 | **第二次独立审计 R4=MODIFY；方案补充完成，代码/媒体验证及复核仍未实施** |
| R5 最终出口一致性 | §3.6 分层 Review 技术准入与 Human 终审，Selection/注册/reconcile/发布共用当前 Final Admission | 未实施 |
| R6 唯一版本和当前文档 | §3.7 Planning @7/Checkpoint @9/Result v3/Wire/Consumer 固定；§5 ADR 与 Current State/Roadmap V0.1 冲突列后续修订 | 旧策略及正式文档尚未修改 |

**该轮历史审计状态（当时）= REVISION_COMPLETE / TARGETED_REVIEW_PENDING / PAUSED。** 当时的 R1–R6 方案修正尚未获得独立复核 PASS，亦未证明生产代码 New-Only 或真实 E2E 成功；用户其后又完成 R4 补充和第8章执行边界修正并**正式批准主标准**，当前生效的**方案身份**以本文顶部、§8.1 和 §8.7 的 `APPROVED_SINGLE_EXECUTION_STANDARD` 为准。900 秒 Quality、预算与历史证据安全仍需实际实施验收，正式 ADR-001/005 的冲突也仍待单独授权处理。


### 5.4 第二次独立定点审核：五项 PASS，R4-only MODIFY（2026-10-11）

用户新窗口对 278 行修订方案的独立复核结论为 **DECISION = MODIFY**：**R1/R2/R3/R5/R6 均 PASS，不再重开；仅 R4 缺上游 Material 长 BGM（P0）、完整 Voice/TTS/ASR（P1）、MP4 时长/技术及视觉覆盖（P1）**。该报告指出的源代码硬限制已按 §3.5.1–3.5.3 对照确认。本次以本方案**最小定点修改**响应，实施顺序 §4B、验收 §4D/§6 已同步，不引入音乐新审核器、旧协议兼容层或新工作流。原外部报告保持原状。

**该轮历史状态（当时）：R4_DOCUMENT_PATCHED / TARGETED_REVIEW_PENDING / PAUSED。** 第二轮 Reviewer 当时未对修正后方案给出新 `CONTINUE`，这项事实保留；后来第8章三项执行边界已按独立审计吸收，并于 2026-10-11 由用户**明确采纳为唯一正式主实施标准**（参见 §8.1/§8.7）。用户批准并不伪造新 Reviewer PASS，也不证明当前代码已支持 301～900 秒；未另获实施授权前，正式 ADR、源码、服务、模型/媒体与 E2E 继续暂停。

## 6. 验收判定与不可接受的替代结果

| 验收维度 | 完成判定 | 不可视为完成的替代 |
|---|---|---|
| **R1 完全 New-Only 入口** | Web/Chat/Skill/CLI/内部函数/Delivery/Material/旧静态页全部不能调度旧视频 Producer；源码物理删除旧可执行代码而保留无关正常能力 | 只隐藏按钮、`410`、开关停用、保留旧 Skill 一键出片 |
| **R2 历史原件保护** | `_creations` 和库成片受删除保护，必要原始媒体和 Rights 引用在选片清理中不丢失，UNKNOWN 原账/字节不变 | 只保留 JSON/SHA，实际来源字节被清理；对旧 Attempt 执行业务补录 |
| **R3 分阶段准入** | 新 Creation 无 Attempt 可以经正式委托创建首次 Preparation；Attempt 后必须有现行五 pin/身份，后台扫描和 CLI/人工写入口全部复用强准入 | 只比较旧 `delivery.schema`，或把未创建 Attempt 的新作品误挡 |
| **R4 四声音模式与时长** | V1 1～900 秒；真实 **301～900 秒 BGM 源文件**经 Music Observation/Reassessment/Match/Readiness；长 Voice/TTS/ASR 全脚本时序与 UNKNOWN 账本合规；silent 无音轨、mixed 双声音、整片 MP4 **实际 ≤900 秒**与首/中/尾技术及语义采样均有证据 | 只用短 BGM 循环充当长源验收、忽略 Material/Voice 限制、仅检前 300 秒、已有五帧便漏掉尾段或通过 +0.5 秒容差放行 >900 秒 |
| **R5 最终成片门禁** | 当前 Output/SHA、Technical QC PASS、System Quality READY、Rights 与 Human Review 绑定；Review/Selection/入库/reconcile/发布均复核相应阶段资格 | Web `currentOutput` 触发正式批准、未 READY 却选片、旧作品 reconcile 入库 |
| **R6 唯一 Planning 和发布** | 当前 Compiler @7 + Semantic Boundary @1 + 新 Checkpoint/Journal @9 + Result v3/Wire/Consumer/Runtime 指纹固定；Web/Backend/Skill/Gateway/Hypit 同版，旧 Producer 不可达 | 旧 journal 触发恢复、新旧策略 fallback、缺 React 构建后回旧网页、混版服务运行 |
| **精简且有效的集成验证** | 一条新混音 MP4 内链、四模式参数化、最少关键风险负例/冷恢复，当前失败真实原件保持原样；外部收费单独授权 | 机械单测数量累积、拼凑模块 PASS 冒充真实产品或无授权付费 |


## 7. 本轮范围与当前停点

- 此次仅产出**单份审计与改造方案**。未删除/修改旧协议代码、未创建实施 Task、未修改 Current State 或 Roadmap、未更改正式 ADR/配置、未触发真实模型、媒体/Provider/Build 或浏览器 E2E。
- 当前共享 Git 工作区已有多项未提交代码与历史原件；实施前先确认唯一 Main 写权限并逐文件对账。此前 Web 新入口 129 PASS、前端构建通过是阶段证据，不是本 New-Only 硬切换验收。
- **主方案已获用户正式批准：`APPROVED_SINGLE_EXECUTION_STANDARD / IMPLEMENTATION_NOT_AUTHORIZED / PAUSED`。** 第8章三项审计 MODIFY 修正已吸收；R1–R6 和四音轨、900 秒目标不变；U4 无副作用、U2 候选版不向普通用户开放、U3-S 可支持受控短片 Debug、U3-L 是 U6 Release 硬前置。批准不等于新的 Reviewer `CONTINUE`，也不等于源码 New-Only、E2E 或正式发布已完成。后续代码/ADR/运行与付费仍待用户另外授权。


## 8. New-Only → 真实 Web E2E 的唯一正式实施与验收标准（用户已批准）

### 8.1 文档唯一性、权限与历史边界

**本节是用户已批准的 Easel V1 唯一正式实施顺序与验收标准，不是候选草案。** 本文 §1–§6 规定 New-Only 目标合同、旧代码物理删除范围和技术验收；§8 U0–U6 负责全部未来执行放行。旧 E2E V2 的 E0–E3/P0–P3 及 Task 中的历史执行顺序不得并行指挥新生产；历史原件和运行事实仍可查。此前独立审核 `MODIFY` 提出的 U4 无副作用、U2 候选/Release 隔离、900 秒资格时机三项均已纳入本方案；**用户于 2026-10-11 明确作出正式采纳决定**，故标准状态为 `APPROVED_SINGLE_EXECUTION_STANDARD`，不是独立审核的新一轮 `CONTINUE` 结论。**标准批准不自动授权**源码/ADR/Task 实施改动、服务启动与部署、模型/Provider/Build、真实 E2E、发布或额外支出。U0 只读现场准备可在另行委托后进行，U2 及冻结 ADR 变更、U5/U6 外部调用均须得到相应明确许可；目前 `IMPLEMENTATION_NOT_AUTHORIZED / PAUSED`。

| 文档/记录 | 合并后的唯一职责 | 禁止的误用 |
|---|---|---|
| **本文** `docs/architecture/web-backend-new-only-cutover-plan-2026-10-11.md` | **唯一已批准主实施与验收标准**：New-Only 契约、R1–R6、U0–U6、失败处置与产品验收 | 把标准批准误认成已更新正式 ADR、代码已上线或用户授予模型/有价 E2E 执行许可 |
| `docs/tasks/creator-autonomous-first-cut-2026-09-30.md` | **唯一既有实施 Task**：Owner、已获授权范围与完成记账；通过审查后以最小导航/冲突修订引用本文 | 再建一份 New-Only Task、把旧 Task 中的旧协议当最新事实 |
| `docs/acceptance/easel-v1-web-real-e2e-2026-10-10.md` | **唯一 E2E 运行/历史证据账本**：旧 7 Attempt、24/24、15 原始捕获及后续每次运行事实，历史段落保留 | 把账本中旧 Proposal @3、410、旧 Material V0.1 或 E0–E3 手册当第二份实施标准 |
| `docs/02_CURRENT_STATE.md` / `docs/03_ROADMAP.md` | 唯一当前状态摘要 / 执行顺序路由；**仅获授权后**消除已识别 V0.1 描述并指向经批准的本文 | 把已写方案当已部署代码、把历史 PASS 当当前验收 |
| ADR-001/004/005 与冻结 Material V1.3 | 生效架构/领域决策；按 §5 在实施前定点解决 ADR-001/005 冲突，ADR-004 与 V1.3 冻结不变 | 借整合回写旧 BindingResult 或保留旧 Producer 兼容层 |

**合并规则**：迁移旧 E2E 的**未来执行约束**到本节，不删、不覆盖历史 Acceptance 的 dated RUN/FAIL/UNKNOWN、原始材料、费用或 SHA；同一规则以后仅在本节维护。验收账本只能新增带日期/运行身份的事实，不再独立改变未来生产契约。已有 Task 不改变历史授权边界，新文档和本轮讨论都不自动授权实际调用。

### 8.2 唯一目标：一个可发布前审阅的真实视频 + 900 秒能力资格

**产品 V1**：`Creation + Hypit` 是唯一视频主线，Creator/Director/Creative Mode 冻结，Proposal 仅 `easel-video-proposal@4`；四模式 `silent/music/voice/mixed`，可确认时长 **1～900 秒**，Material V1.3 的 `MaterialPlan → Material Supply → MaterialBundle → MaterialReadiness → MATERIAL_READY`、五项当前 pin、Delivery 唯一执行权与服务端 Final Admission 不变。禁止旧 Skill/Chat/CLI/Hypit-only/Web 直接制作，禁止保留旧协议回退。

**首片 E1（真实产品验收）**：优先一位现有 Creator + 一个现有 Creative Mode，用一个**全新** Creation 从 Easel Web 讨论并确认明确的约 **45～60 秒 / 9:16 / 中文 Voice+BGM** 视频，完成真实 Planning/Truth → Material/Rights/Readiness → Native Authoring → Hypit Check/Plan/Pricing/Build/Export → Technical QC / System Quality `READY` → 人工 Review/最终 Selection → Content Library；验证可播放 MP4、当前 Output SHA、两类音轨、Right/费用与真实操作来源。不自动发布。Creator 正常内容、Rights 与明确费用决定是合法业务行为，不计工程手改。

**900 秒产品能力资格与首次短片 Debug 是两个不同验收层次。** U3 的无付费软件验证分为 `U3-S`（L1+L2：一条当前五 pin 的 45～60 秒 mixed 真实本地 MP4，关键来源/权利/费用/UNKNOWN 拒绝与冷恢复）和 `U3-L`（§3.5.1–3.5.3 完整 900 秒资格：接近 900 秒的真实本地有声 MP4、301～900 秒 BGM **源文件**的 Material Observation/Match/Readiness、完整 Voice/ASR/时间轴、片头/中/尾画面与声音证据、峰值资源、实际 `≤900` 边界及四模式少量参数化验证）。短 BGM 循环不证明长源准入。**`U3-S=PASS` 加 U4 安全预检和逐次外部调用授权即可准入受控 U5 短片 Debug；`U3-L=PASS` 必须在 U6 正式 Release/E1 PASS 前完成，且与最终拟冻结源码和运行指纹一致。** 在 U3-L 未验证前，超过当前真实 Quality 验证能力的请求必须 fail-closed，不得宣称 900 秒已经正式可用。U5 Debug 任意进展不代表 E1 PASS，900 秒内部 PASS 亦不代表真实 Web E1 PASS；不能为赶首片将 V1 上限降低到 300 秒。

### 8.3 唯一 Gate 序列：架构切换先于全新真实 E2E

| Gate | 执行范围（仅在前置获批后） | 完成/阻断证据 |
|---|---|---|
| **U0｜现场保护与授权盘点** | 只读固定 `easel-studio` HEAD/dirty/untracked、Web/Gateway/Hypit/Skill 身份，保护所有历史 Creation/Attempt、原始响应/媒体、Rights/SHA、计数与账单；确认当前 Job/Owner。 | 原旧作品 7 Attempt、Preparation 24/24、15 Captures **原值保全**；任何 `PENDING/SUBMITTING/UNKNOWN` 仅按原 operation 被动核实，不重派、不释放占额。没有新有价请求。 |
| **U1｜唯一标准批准（已完成，实施授权仍待）** | 2026-10-11 用户已采纳整合后的 R1–R6、U0–U6 主方案，吸收最新 `MODIFY` 审核的三项 §8 边界修正；ADR-001/005 与 Current State/Roadmap/Task 的受控对齐清单仍为以后实施前置。 | **`STANDARD_APPROVAL=PASS / APPROVED_SINGLE_EXECUTION_STANDARD`** 只说明唯一标准成立；`IMPLEMENTATION_NOT_AUTHORIZED / PAUSED` 仍约束 U2/U5/U6。正式 ADR 与代码修改、部署、付费及真实 E2E 须分别获得后续权限，不把本阶段记录为软件 PASS 或 Reviewer 复核 CONTINUE。 |
| **U2｜唯一 New-Only 候选实现（非正式 Release）** | 在另获实施授权后，按 §3–§4 物理删除旧 Producer/Writer/Parser/Policy/Skill/CLI/旧 POST 与旧恢复分支，保护历史；统一 Proposal @4、唯一 Planning/五 pin、分阶段新生产准入、Material V1.3、Web `allowed_actions`、Final Admission 与四模式/1～900 秒目标合同。候选版本只能在**隔离或限制访问的单协议验证环境**进行软件与受控 Debug；尚未验证的长片操作保持 fail-closed，不允许调用旧路径作为回退。 | 单一候选源码/构建/配置指纹可追溯，旧视频生产入口不可达，当前短片相关的安全拒绝、Rights/现金/UNKNOWN 门禁可证；**U2 完成只算 `CANDIDATE_READY`，不能认作正式部署、普通用户可用或 E1 PASS**。长片资格可在 U3-L 后验证；未达成前绝不声称 900 秒已就绪。 |
| **U3｜P0-A 无付费软件连续集成（短片准入与长片资格分别记证）** | **L1**：7 次旧失败/15 捕获只读归类与原合同的正反/故障回归，无法合法回放标 `NON_REPLAYABLE`。**L2**：当前五 pin、合法固定外部回执、真实内部 Owner → Material/Rights → 本地 Hypit Check→Build→Export 的 **45～60 秒中文 mixed MP4**，附当前 Output SHA、System Quality/Review 及必要拒绝、冷恢复。另以 §3.5.1–3.5.3 及四模式参数化进行 **900 秒内部资格 U3-L**，可在 U5 受控短片 Debug 期间继续完善。 | **`U3-S=PASS`**：L1/L2、短片必要 Rights/费用/状态/UNKNOWN 安全准入和当前单协议内链证明完成；配合 U4 才可申请 U5。**`U3-L=PASS`**：同一拟冻结版最长 900 秒实际媒体、长 BGM 原件、Voice/ASR、首中末证据/资源、四模式与 >900 拒绝全部通过，是 **U6 Release 硬前置**。二者只是 U3 验收的两个证据维度，不是新状态机/Gate；U3-S 不能冒充完整 V1 资格。 |
| **U4｜P0-B 无副作用 Web/Runtime/现金与 Rights 预检（可与 U3 并行）** | **只读检查**实际页面、现有 Proposal/Creation 状态、按钮和阻塞展示、后端/React/旧静态入口/Gateway/OpenClaw/Hypit/Skill 的加载指纹，以及模型套餐、Rights、技术额度、现金可证上界和未决操作。需要验证“填写→确认”的 UI 行为，仅在隔离测试环境以受控替身/禁用执行 Worker、禁止真实模型/Provider 的方式验证。**实际 Easel Web 不得点击正式 `confirm_production`、新建生产委托或执行有副作用的业务确认**：该操作会写 Delivery `pending` 并可能自动开始 Preparation，必须等 U5 授权。 | 页面读取/禁用态/阻塞原因、隔离 UI 合同及加载/预算/Rights 证据可重复，且**本 Gate 没有新正式 Delivery/Attempt 或真实模型/费用副作用**。WebCodex 控制故障与产品 UI 故障分别记证；只读预检绝不认定“真实 Web 已确认”。原新增现金共享 ≤¥10 和技术次数仍需逐请求核算。 |
| **U5｜P1/P2 受控真实 Web Debug ↔ 一类根因闭环** | **仅在 U2 单协议候选基线已受控加载、`U3-S=PASS`、U4 无副作用预检通过、逐请求 Rights/额度/现金及真实调用授权有效之后**，在限制访问的 Easel Web 使用**全新 Creation**首次提交正式 `confirm_production`，允许其后由唯一 Delivery 自动 Preparation；每次只处理最早的 FAIL/BLOCKED，以原始证据/身份/费用对账、离线合法正反例和当前内链回归闭合一类共性根因，必要时受控更新候选版本。旧 Attempt 不续跑/重派。**`U3-L` 的 900 秒内部资格可以与本阶段不相关的 45～60 秒 Debug 并行完成**；未验证的 >300 秒请求一直 fail-closed，不能在此冒充已获得长片可用资格。 | 每轮只记真实最远关口、Run/Creation/Attempt、原始 SHA、费用/UNKNOWN、修复与 fingerprint；两轮相同根因无效或进度不前即暂停。**U5 Debug 无论走到哪个关口都不能认作 E1 PASS，也不使候选版对普通用户开放。** |
| **U6｜P3 全资格通过后的同版冻结 Release E2E** | 先确认 **`U3-L=PASS` 且资格证据与最终拟冻结源码/配置/Runtime 指纹一致**，全部 New-Only R1–R6、四模式及最长 900 秒能力可用，U3-S/U4 已通过、Rights/现金/技术额度可证；随后在**受控候选 Web**冻结并核对同版 fingerprint，创建**独立新 Creation**，通过真实 Web Creator 确认→Delivery 唯一生产→Hypit Build/MP4→System Quality READY→人工 Review/Selection/Content Library。不得通过 API/CLI/DB 伪造 Web，通过 Debug 旧阶段拼接放行，或自动发布。 | **仅在**同版新作品真实 MP4、Output SHA、中文 Voice+BGM、Rights/费用/Quality/人审/选片全部通过且 900 秒长片资格仍与该版本一致时，才可记 **`E1=PASS` 和 `RELEASE_ACCEPTED`**；之后开放正式生产仍需单独发布/运行授权。U2/U3/U4/U5 任何阶段不得称已正式 Release；其他产品路径不启用旧协议双轨。 |

**依赖、候选与正式发布边界（不新增 U7）**：U0/U1 先行；U2 仅在明确实施许可后准备**唯一 New-Only 候选**，只能在隔离/限访环境加载验证，绝不向普通用户开放未经认证的正式生产。U3 中 `U3-S` 的 L1+L2、短片关键拒绝与 U4 **只读**预检可并行验收；符合这两项且获得实际模型/预算授权时，U5 可提前进行受控 45～60 秒 Debug。`U3-L` 的 301～900 秒全资格可以在 U5 期间并行验证，但 **U6 必须等待同一拟冻结指纹下完整的 U3-L PASS**；最终发布前要求 Web、Backend、Skill、Gateway、Hypit 同一受测版本。生产环境任何新旧混合可调用状态、未经验证的长片 READY 或用旧协议恢复均不可接受。每段只能按实际证据记 `PASS / FAIL / BLOCKED / NOT_TESTED`，U3-S/U3-L 不作为额外状态机。

### 8.4 费用、次数、历史数据与恢复绝对边界

- **历史旧作品绝对保全**：原 `cr_70af2a4443b541998f929541ef9f4b84` 的 7 个失败 Attempt、24/24 次 Preparation、15 原始捕获与实际费用/UNKNOWN 不清理、不迁移、不继续生产。L1 的旧原件只作非执行审计材料；不能为“通过”而宽松解析或添旧 Writer。
- **共有现金上限**：此前单次 E1 记录的累计新增实际现金授权 **≤¥10（原新旧作品共同约束）**不因创建新 Creation 刷新。实账 = 已发生 + 占用/待结算 + 下一请求可证明最高风险；估价、美元 `approved_budget_usd`、未知套餐权益并非 Provider 强制上限。**新一轮执行须再次确认剩余授权/权益及用户实际调用许可**；未知即 `BUDGET_NOT_PROVEN` 停止，不靠“订阅用户”推断免费。
- **独立技术调用限额**：原作品的 24/24 不能由币种预算替代或重置；全新 Creation 应按当前正式 Delivery/Provider 策略建立新身份和独立可证合法额度，不能默认继承旧作品失败运行资格、旧确认或未结算 Run。不得为让 E1 通过提高原作品额度或创立第 8 个历史 Attempt。
- **远端与可重试性**：`PENDING/SUBMITTING/UNKNOWN` 先对账原 operation；不可证明未提交就不重派、不清零费用。只在当前新协议合法 checkpoint 与 Owner 资格成立时作有界诊断恢复；旧请求完全只读。Rights `UNKNOWN/RESTRICTED`、无法证实成本上界、版本混用或质量不可验则 `BLOCKED`。
- **不授权行为**：本草案/用户讨论不是付费模型/素材/TTS/Hypit、有价长片、充值、自动发布、重启或 E2/E3 资格批的执行授权。

### 8.5 唯一结果证据与冲突修订清单

未来执行**只在既有** `docs/acceptance/easel-v1-web-real-e2e-2026-10-10.md` 顶部按实际发生顺序追加单次真实证据，不另建同名验收文件：`RUN_ID/GOAL`、`GATE(U0–U6)`、`RUN_MODE(SOFTWARE/DEBUG/RELEASE)`、`Creation/Attempt/Operation`、`RELEASE_FINGERPRINT`、`REAL_FRONTIER`、`RESULT`、`RAW_EVIDENCE_SHA`、`RIGHTS/CASH/TECH_LIMIT/UNKNOWN`、`FIX_AND_REPLAY`、`NEXT_SINGLE_ACTION`。真实 MP4 同时登记 Build ID、文件与音轨、System Quality、人工 Review/Selection；**只记录实际发生，测试 PASS 不冒充媒体或真钱事实**。

**本次用户批准后，仅对现有 Creator Task、Current State、Roadmap、DOCUMENT_INDEX 和历史 E2E 账本做了主方案身份/导航对齐**，旧日期的实际历史记录、原始输出、费用及失败结论保持原样；旧 `MaterialRequirement/ResolutionResult/BindingResult`、永久 `410`、Proposal @3、旧恢复等表述不能再承担未来新生产的规范职责。**Creator Task 仍是唯一 Owner/实施范围与授权入口，但不再维护第二份运行日志**；每次 `RUN/REAL_FRONTIER/RESULT/SHA/CASH/UNKNOWN/NEXT_SINGLE_ACTION` 只进 `docs/acceptance/easel-v1-web-real-e2e-2026-10-10.md`，Current State 仅汇总当前有证据的实现状态，Roadmap 只路由 U0–U6 阶段。**正式 ADR-001/005 仍与新目标有冲突**，须在单独批准的 U2 工作开始前按 §5 定点修订；ADR-004/Material V1.3 冻结不动，不因为主方案生效而宣称代码已迁移。

**合并草案的最终审核清单**：唯一规范与历史账本职责无歧义；R1–R6（特别 R4 长 BGM/Voice/900s）没有遗漏；U0–U6 先后/并行可执行；旧 E2E 合法人工操作未误删；用户已批准的 1～900 秒与四模式仍保留；两层额度和未知扣费不会因新作品重置；L1 旧原件不要求旧 Parser；L2 实体 MP4 与 U6 真 Web E1 不混淆；无第二 Task/状态机/文档指令；没有未经审核即改 ADR、服务或实施。审核结论 `CONTINUE | MODIFY | STOP`，按 `MODIFY` 只定点修订，不直接启动。

**技术落地设计的承载方式（不新建第二份技术方案）**：本文 §3–§4 已含架构与技术改造目标、实施工作包和完成条件。后续**仅在 U2 实施获单独授权后**，由唯一 Creator Task 形成可执行的精简代码级清单：旧入口/Producer→Consumer 删除映射、Proposal @4/Web API/Delivery 状态与 SHA 字段变更、Material/Voice/BGM/900 秒 Quality 的受影响函数与保护性检查、历史文件与 UNKNOWN/资金保护、受测运行组合及最少正反集成验证。每项包含文件、动作、依赖、验收和安全停止条件；不复制本文合同、不再建完整技术设计书或平行 Task。若实施发现当前冻结 ADR/领域设计无法覆盖的真实冲突，先按 §5 定点审查而非擅自开新架构。

### 8.6 后续阶段（首片之后，均另行授权）

此前 E2（同版三个独立新主题 3/3）、E3（质量/时延/成本评分）及独立 6/6 正式 Planning 资格批，**均不属于 U0–U6 首片 E1 的通用前置**；未来需明确另行授权，继续使用现有 Creator Task 与 E2E 证据账本，不开新生产路线。本轮合并不改变这些历史阶段的状态。

### 8.7 本轮合并停点

**APPROVED_SINGLE_EXECUTION_STANDARD / IMPLEMENTATION_NOT_AUTHORIZED / PAUSED。** 2026-10-11 用户明确把本文定为 Easel V1 **唯一正式主要方案**；独立审核 `MODIFY` 的三项 §8 修正已落实，但无新 Reviewer `CONTINUE`，也不能把批准误记为真实代码完成。本文 §8 U0–U6 正式成为未来唯一执行标准；本次只进行必要的文档状态/路由同步，历史运行账与原始文件不改。**未获得 U2 代码/正式 ADR/服务部署许可，也未获得 U5/U6 的模型、Provider、Hypit 或真实 Web E2E 执行授权。** 不在本轮启动测试/服务/付费操作或 Git 提交，保持 PAUSED。
