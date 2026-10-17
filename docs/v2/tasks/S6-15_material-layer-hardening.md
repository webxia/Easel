# S6-15 · Material Layer 现状审计与完善（S6-14 前置）
> **最新来源接入要求**：Unsplash 需完成合规的制作选材与资产入库；BGM/SFX 补足可合法自动使用的来源。见本卡末尾“新的来源完善决策”，新增部分尚未实施，不影响已有 G0/G1/G3 结论。
> **最新取舍覆盖**：用户随后明确“Unsplash 先不做，重点完善 BGM/SFX，并且不新增音频管理界面”。U1/U2 暂缓，不作为本次 G3 阻断；下文的历史需求保留事实。活动工作为 BGM/SFX 的公共音频来源、权益、自动供料及真实验收。

状态：**PARTIAL — G0/G1 已完成、G2 核心实现已接通、G3 本地软件通过；G4 已执行完整准入审查但决定 NO_GO / BLOCKED，真实下载、声线及最终 CI 证据仍待补齐**。2026-10-17 用户进一步授权完整审计、架构选型与实现，取代上一轮仅建文档的范围。**当前唯一实施前置任务**；素材层完成验收后才恢复 S6-14 首次真实生产及完整范围验收。本卡任务 ID 是后续补充，不重新编号 01～14，不改变其历史完成记录与 S4 需求责任分配。

- **基线**：工作树 `/Users/xgx/.codex/worktrees/s5-architecture/Easel`，`codex/s6-production`，盘点基线 HEAD `5a87887b3320fcceb9e4c643faea387e4184c25d`，接手 CLEAN；[PR #8](https://github.com/webxia/Easel/pull/8) 仍为 Draft。
- **关联需求**：V2-EXP-011/012/013/021/025/031/032/033；原主责仍为 S6-02/03/06/07/08/11，本卡只承担素材链收口、补强和集成验证。
- **合同依据**：[确认需求](../01_REQUIREMENTS.md)、[职责架构](../02_ARCHITECTURE.md)、[唯一可执行合同](../15_IMPLEMENTATION_DESIGN.md)、[S6-06](S6-06_materials-core.md)、[S6-07](S6-07_material-supply.md)、[S6-11](S6-11_creation-first-cut.md)、[迁入记录](../../../easel/materials/MIGRATION.md)、[运行配置](../16_RUNTIME_SETUP.md)。
- **执行范围**：本轮已获用户明确授权，按[审计](../17_MATERIAL_LAYER_AUDIT.md)和[架构](../18_MATERIAL_LAYER_ARCHITECTURE.md)开展内部实现、适用验证、文档和开发分支提交；保持公共合同与历史资产不变。真实付费调用仍需具名许可。
- **禁止事项**：不破坏/替换/并行新建 upstream Planning/Director/Creator/Work/Operation/Editor 协议；不自动迁旧数据库；不删除历史素材、Profile、Attempt、output；不自动合并/发布、实发付费调用，不凭凭证或猜测补 Rights/额度。

## 1. 现状基线（区分配置、实现与实测）

| 来源/能力 | 当前实现 | 本机配置/私有资产 | 已有证据 | 真实验收缺口 |
|---|---|---|---|---|
| V2 内容寻址素材库 | `MaterialLibraryCatalog`、`MaterialService`、Rights、技术检查、去重、作用域、引用保护；库内优先 | `outputs/_production/materials`；当次只读审计：2 条逻辑记录/同一 SHA/1 个 MP3 实体；旧 catalog 独立保留 | 离线供料/恢复测试通过，Rights 为 ATTRIBUTION_REQUIRED | 重复逻辑记录的身份原因、跨版本引用/GC、素材索引与 UI 管理能力需复核；**不先删除记录** |
| Pexels | 图片/视频自动 search → 受控下载/检查/入库 | Key 已安全配置于 V2 忽略的本机 `.env` | MockTransport + 软件主线 | 真正 API 返回、许可证条件、下载链、质量/选材表现 NOT_TESTED |
| Pixabay | 图片/视频自动供料；私有 24h 搜索缓存 | Key 已配置 | MockTransport、缓存/HTTP 错误负例 | 真 API、额度/401/429/大小/重定向、Rights/署名实际正确性 NOT_TESTED |
| Unsplash | **仅主动搜索/预览**，官方图片热链接及摄影师来源；没有自动供料 | Access Key 已配置 | Web/UI 接入和离线协议测试 | 选择 → 必需下载追踪 → Rights → 获取/入库 → 编辑/导出整链未接；不得直接从图片 URL 绕过要求 |
| 已审查公开来源 | 有限 JSON 清单、host/asset-specific Rights 校验，支持图片/视频/音频 | `EASEL_REVIEWED_PUBLIC_SOURCES_JSON` 未配置 | 离线正反例 | 无真实候选库，不等于通用互联网任意搜索；缺口需评估实际维护成本 |
| BGM | 库内优先，音频依赖及署名贯穿；外部仅能走已审查音频清单 | 仅 1 个物理 MP3，可复用但需署名 | 本机技术校验、跨画像/跨作品有条件检索 | 音乐语义相关性/试听、真实音频外部来源、最终 credits 导出仍需真实检查 |
| SFX | 素材模型存在音频/SFX Need 类型 | 当前没有专用外部音效 Provider/目录 | 模型及局部测试 | 按事件的音效搜寻、使用条件、编辑放置、复用缺整链证据 |
| MiniMax IMAGE | image-01 HTTP Adapter，统一 Operation 准入 | Key 有；无 `EASEL_GENERATION_RIGHTS_JSON` | Fake/MockTransport：发送身份、回执、UNKNOWN 不重发 | 实际生成权益、计次授权与真实输出 NOT_TESTED |
| MiniMax VIDEO | H3/H3-Max 异步提交、查询、下载适配 | 未显式设置 `EASEL_VIDEO_MODEL` 及 Rights | Fake/MockTransport | 不可用；需指定模型/权利/次数后才可实发 |
| VOICE | 独立声音服务及句段资产适配 | `EASEL_VOICE_SERVICES_JSON` 未配置 | 离线合成声音/字幕软件测试 | 真实自然音色/服务准入属于 S6-10/S6-14，不能用素材库完成代替 |
| 编辑/审片 | `SupplyTasks` 把候选登记为作品 artifacts，编辑读取具名 asset IDs，FFmpeg 本地可渲染 | 现有空作品库/测试资产 | 本地编码及模拟整链 | 真正外部素材全链、导演语义选择和真实视听质量未通过 |

上表是基于当前代码、`docs/v2` 证据及本机私有配置的**静态/本机观察**；服务可配置/适配器存在不等于真 API 通过。不得在版本变化后无条件继承。

## 2. 本任务必须回答的不足（P0→P1）

**P0-A｜边界与全链合同审计。** 从“已确认作品/方案 + 冻结 Creator 六维画像 + Director/Creative Mode + 权限和调用预算”追踪到 Material Need、候选、Rights、决策、素材引用、编辑/渲染和 credits。逐段写清**谁提供、谁拥有、谁消费、错误由谁处理**；列字段映射和现有测试/实测证据，核对缺失/冗余/歧义，而不是把 V1 旧协议直接迁回。素材层不能决定脚本、重写导演意图或自动改变已确认方案；不伪造模型看过/听过素材的事实。

**P0-B｜素材源覆盖与可用性。** 完成 Pexels/Pixabay 真实服务合同核验计划；判定 Unsplash 在其实际 API 政策下能否作为自动制作来源，若不满足使用政策就保持 preview-only 并给出等效合规替代；评估可维护的真实 BGM/SFX 来源（含 Rights/署名、合法可下载、配额、国内网络适配），不把 Pexels 当作音频源，不假定 Pixabay 视频能力等于 BGM/SFX 已接入。缺服务必须可观察返回 gap，不无限搜索或默认付费生成。

**P0-C｜素材入库/去重/生命周期。** 查明 1 个 SHA 对应 2 条记录是否代表不同 Rights/来源/授权/范围或同义重复；先不改旧数据，基于可验证身份定义复用/唯一键、幂等、合法升级、引用/安全回收及重复导入的稳定语义。需要兼容既有作品引用，严禁通过简单合并/删除记录、手工改库或扩大共享范围“修复”问题。独立处理新/旧库边界及内容寻址哈希冲突、文件变化。

**P0-D｜Rights 与素材决策证据。** 每个 Provider 的真实资产来源页、条款版本、限制、商业用途、可见人物/商标、署名和链接追踪有**素材专属证据**；明确候选不足、过期条款、版权不明、已选素材失效、强制素材被拒的行为。不能把“HTTP 下载成功”“Key 可用”“图片预览”当成许可；导演真正做语义取舍，程序固定资产身份/权限/预算/可恢复回执。

**P0-E｜恢复与不重复成本。** 验证：库内命中→零外部请求；已搜索候选→按合法缓存复用；多场景共享素材→不重复下载；下载已完成→不会重复登记/重复扣费；IMAGE/VIDEO 同 operation 重试/UNKNOWN 只能观察回执不能盲重发；取消/所有权变化后不产生后续外部副作用；失败保留已取得成果。变更不破坏现有 `OperationService` 或 worker 幂等。

**P1｜检索质量与可观察体验。** 语义匹配、类型/画幅/时长/质量/多样性、素材预览/选材/缺口及出处展示；本地音效/音乐查找、非网络环境退化、provider 失败原因分类、必要 credits 导出；明确哪些属于素材层，哪些必须由 Director/Editor/UI 现有拥有者负责，避免重复建模型或 UI 状态机。

## 3. 上下游冻结边界（必须逐条回查）

| 方向 | 已有权威/不可破坏约束 | 本卡允许的动作 |
|---|---|---|
| **上游：Creator/Director/Planning** | 六维画像就是唯一主人设；频道/导演已确认版本和单片冻结方案拥有事实、风格、素材用途与明确限制。计划确认与授权由作品命令/领域存储持有 | Material Layer **读取并执行**冻结约束，按 Need 找候选/返回缺口，不独立修改 Director、方案或画像 |
| **输入：作品/素材 Need** | 现有 `PlanDocument` + `work_inputs` → `SupplyTasks` → `MaterialNeed`/`NeedIntent`、重要性、作用域、必用/参考、Rights、预算；合同维护点 `15_IMPLEMENTATION_DESIGN.md` | 保持字段含义和已确认素材映射；新增 Provider 只能适配边界，不另建平行 Requirement 契约 |
| **内部：Provider/Store** | `ExternalCandidate`、`MaterialService`、`MaterialLibraryCatalog`、`RightsService`、`OperationService`；来源/许可/身份/可见性/引用必须验证 | 可以替换内部搜索/排序/缓存/Provider 实现，但不可扩权或把技术候选当已选用素材 |
| **输出：供料结果/制作** | 当前 `SupplyTasks` 合格候选、稳定 asset ID、作品 artifact/metadata/edges；传给 Edit 的 payload **仅 `schema_version` 与 `asset_ids`**，失格/缺口明确 `needs_decision` | 必须保证候选、绑定和素材版本可追溯；Editor 只消费符合契约的真实本地资产，不接收绕过 Rights 的远端链接 |
| **恢复：worker/操作** | `operation_id`、真实提交次数、预留/未知、持久回执、重启复用及不重发；调度状态属 Work/Graph，不由素材层再造 | 内部增强不改变准入计次、取消/恢复语义和已有成果保护 |
| **审阅/导出** | 视频技术检查和模型视听 QC 属 S6-11/14；Creator 具体版本接受属 S6-12；Rights、署名必须随实际使用素材传递至导出 | 只交付足以核验的素材引用与 credits 条件；不得自行标记 QC PASS 或代用户接受 |

**旧 V1 文档中 `MaterialRequirement → ResolutionResult → BindingResult → MATERIAL_READY` 可作为回查思想（需求→解决→绑定→就绪），但不能无决策恢复为新 V2 的第二套对外消息协议。** 逐环节用现有 V2 `MaterialNeed/ExternalCandidate/MaterialHandle/asset_ids` 与作品状态验证不变量；如确有无法表达的行为，先列变更提案、影响面和兼容测试，再经确认修改唯一权威合同，不能隐式改调用方。

## 4. 计划交付物与阶段闸门

1. **G0 事实冻结**：编制 `现有行为→源码入口→正/负例→缺口→风险优先级` 台账，厘清上述 P0/A-E 与 P1；每项注明代码已实现、配置存在、离线已验、真实未测。
2. **G1 责任与合同评审**：形成上游 Planning、Material、Director、Editor、Operation、QC 的责任矩阵和输入/输出字段对照；记录必须保持不变的既有合同，识别需确认的变更；不做假兼容。
3. **G2 最小完整实施包**：按 P0 顺序补齐缺失 Provider/本地复用/真实 BGM-SFX/选材/权益/可观察性等已证实缺口；各改动建立真实代码及正反例、留独立证据，按依赖推进；不为凑 PASS 改需求。
4. **G3 素材层完整验收**：覆盖不同媒体类型与场景、库优先/多源回退、参考与必用、Rights/署名/保护、去重/复用、失败/取消/恢复、UNKNOWN/计次、最终有效素材 → 编辑引用；涉及真实服务时需具名授权和有界实际请求，单独记录真实证据。
5. **G4 S6-14 回接**：完成 G0-G3 且 P0 无未解释的阻断缺陷，形成 `输入/输出/授权/引用/证据` 回查报告，将素材层就绪结论传递给 S6-14，再执行首次真实生产和完整范围验收。其他真实声音、视频模型、Creator 接受仍按 S6-14 原要求单独验收。

**门禁定义**：G0/G1 评审通过≠素材功能完成；代码/Mock PASS≠真实 Provider PASS；G3 若仍有阻断性未测则不得将 G4 标为 ready。真实费用和生成次数、旧数据迁移、主线合并/发布另按明确授权。

## 5. 本轮执行记录

- 历史记录：2026-10-17 初建本 Task 时仅处理文档；随后用户明确授权“审计→文档→架构/选型→实现”，本轮执行范围据此更新，不能继续按旧的 AUDIT_NOT_STARTED 交接。
- 审计基线：`09fd994525eeef7d5bcef5c34ae090f379d16fb7`，本轮未合入官方更新。事实与纠正见[审计](../17_MATERIAL_LAYER_AUDIT.md)，技术取舍及内部落点见[架构](../18_MATERIAL_LAYER_ARCHITECTURE.md)。公共Plan、Editor、Operation三个源文件保持基线SHA，供料输出仍只有schema_version/asset_ids。

| 阶段 | 当前结果 | 实际内容及边界 |
|---|---|---|
| G0 | COMPLETE | 五类素材逐环节源码审计、13项台账；纠正逻辑记录并非同义重复、record_usage已有合并，保留原件 |
| G1 | COMPLETE | 保留SQLite/LangGraph/FFmpeg；采用内部冻结意图、用途绑定、分阶段再准入、旁白专用分支；不新增公共方案或V1并行链 |
| G2 | CORE_IMPLEMENTED | 本轮核心修复已经进入代码，具体见下文；真实源库存/账户可用性和公共边界既有差异未被假报为解决 |
| G3 软件/本地媒体 | PASS（本轮受测范围） | 隔离库、真实合成媒体与MockTransport；实际worker五模态组合→FFmpeg→模拟完整视频QC→reviewable，无用户接受 |
| G3 真实供应/声音 | NOT_TESTED | 本轮实际Pexels/Pixabay/模型/TTS/生图/视频请求为0；真实音源库存、声线自然度和供应商失败恢复尚未验证 |
| G4 | BLOCKED | G3真实项没有证据，S6-14继续REAL_PRODUCTION_PAUSED，不自动恢复 |

### 已实施的软件修复

1. 冻结画像、Director和Plan进入一次任务私有MaterialIntent解释；带上下文摘要缓存及稳定模型调用namespace，避免意图解释与补料决定的ordinal回执冲突；静音且必用视觉已覆盖全部场景时不增加模型请求。
2. 图片/视频按导演检索意图供料；BGM与SFX使用原音频Need，SFX cue保留独立身份/时间/用途。必要音效缺源明确阻断，可选点缀没有素材时不升级为新的硬门槛。
3. 外部来源按本方案grant筛选，并在检索和下载前复验授权；无授权零请求，撤销后停止。Rights预查移到下载前；已登记且来源/实质许可一致的素材复用本地字节，不合并不同权益记录。
4. 合格候选筛选后再做最终top-k和内容去重，失格旧记录不挤占合法新版。artifact material_uses保存多个场景/事件，引用表复用既有need_ids合并实现并传入cue Need ID。
5. 在供料恢复、编辑输入、选中及渲染前核验具体材料记录的内容/来源/Rights/可见性/引用；实际工程依赖和导出署名只保留选中素材，未选候选保留而不伪称用于成片。
6. 新增显式minimax-speech-v1非流式JSON/hex适配，复用既有VOICE Operation、句段缓存与真实音频检查。错误响应保持failed_after_submit，未知结果不重发；通用二进制Speech协议保持兼容。
7. 能力目录与声音执行共用纯配置验证；reviewed_public有可授权的目录项；Pixabay修正q≤100及per_page≥3。

### 本轮实际验收证据（2026-10-17）

基线HEAD为上述09fd9945，以下验证绑定本轮提交前已经冻结的修改源码，提交后的确切SHA及CI另在PR #8记录。执行环境：本机macOS、隔离 `/tmp/easel-s6-worker-venv/bin/python`、已有FFmpeg/ffprobe；没有重跑全仓1600级历史回归，也没有用跳过掩盖真实服务缺失。

| 项目 | 实际结果 |
|---|---|
| `python -m pytest -q tests/production --junitxml=/tmp/easel-s6-15-production-final.xml` | **377 passed、3 skipped，29.46秒**；JUnit380项，0failure/0error |
| 新五模态完整组合用例 | 实际图片/视频/BGM/原生旁白HTTP模拟回执/SFX，经真实worker和FFmpeg生成3秒成片到reviewable；旁白2次MockTransport、IMAGE/VIDEO提交0，accepted_output_id为null |
| 三项跳过 | 两个Windows专属junction用例；900秒长编码opt-in用例。既有900秒本地历史证据不扩大为本轮五模态900秒实测 |
| 适用前端回归 | **80 passed、0 failed**，生产UI公开调用形状不变 |
| 文档路径 | **1289条路径 / 466份文档**通过；修改后按相同入口再次核验 |
| 外部合同 | `contracts.py`、`editors/base.py`、`operations.py`保持审计基线SHA；供料成功结果仍严格为schema_version/asset_ids |
| 历史资产/凭证 | 未改用户原素材、Profile、Attempt、旧DB、生产配置；真实Key仅本机原有忽略文件，禁止入Git |
| 真实供应商/自然音色/创作品质/Creator接受 | **NOT_TESTED**，本轮没有进行真实远端模型、声音或媒体生成/检索 |

回归中发现的失败已按责任修正并保留语义：原三个公开音源测试补齐明确的fixture方案授权；原生TTS失败断言使用既有failed_after_submit，不修改Operation状态；五模态验证读取实际edit_project文件而非误取metadata；静音零额外调用分支使用既有input_id，不改上游输入字段。最终上述回归已实际通过。

### 2026-10-17 · S6-15 新提交的跨平台 CI 失败归因及定向修复

提交 `867d471c` 的 GitHub CI [run 39002155466](https://github.com/webxia/Easel/actions/runs/39002155466) 已结束为 FAIL（macOS/前端/安装 Lint 等其余项通过）。Ubuntu：1 failed / 1583 passed / 70 skipped；Windows：2 failed / 1493 passed / 159 skipped。两者共同失败的 `test_selected_dependencies_exclude_unselected_candidates` 实际测试的是“只引用已选素材”，但前置媒体观察依赖 FFmpeg/ffprobe；CI 缺少相关媒体可执行文件，触发 `needs_decision`。**修复仅限该测试的观察输入替身**，保留真实生产 `observe_media` 和其他媒体验收的严格要求；显式缺少 FFmpeg/ffprobe 的环境下定向用例 1 passed。

Windows 另暴露 SQLite `catalog.db-shm` 并发消失时，`Path.resolve(strict=False)` 偶发返回同盘 `C:\\$Extend\\$Deleted\\<文件标识>`，被误判为逃逸。修复仅对**本目录已消失的 `catalog.db-shm/-wal/-journal`、同盘删除命名空间、指定文件标识结构**建立有界例外，前置路径逐组件 symlink/junction 检查仍有效；活文件、异盘、UNC、设备命名空间及普通文件仍拒绝。新增可跨平台执行的模拟正反测试，不放宽对素材任意路径的校验。

本机修复后测试：`tests/production` **383 passed、3 skipped**；跨平台路径/两个原 CI 用例 **25 passed、2 skipped**；无 FFmpeg/ffprobe 环境的“只选中依赖”**1 passed**；`git diff --check` 通过。三个 skipped 对应真实 Windows junction 两项与 900 秒 opt-in 一项。**上述只代表本机软件验证**；新提交的 Ubuntu/Windows CI 需要绑定新的精确 SHA 重新判读，不将旧 run FAIL 改写为 PASS。G3 真实服务仍 NOT_TESTED、G4 仍 BLOCKED、S6-14 继续暂停。

### 真实验收与剩余风险

- 本机仍只有此前具名MP3；本轮没有下载新音源或选用新模型/声线。BGM/SFX的软件供应链就绪不等于音乐/音效库存覆盖不同题材，也不证明语义选材正确。
- Unsplash维持主动preview-only：当前没有足够依据证明其热链接、署名、下载事件及非自动化要求能由本地自动制作路径完整满足，不能只补tracking便认定可用于FFmpeg。
- `Plan.Scene.id`最多128字符与现有Editor.scene_id最多96字符的边界差异保留并明确记录；未改变公共合同。内部投影不能新增更窄范围，测试不冒充此极端ID范围已渲染通过。
- 来源复用证明已经登记的同源同许可资产不再下载；不宣称覆盖“收到全部下载字节但尚未持久登记即断电”的所有恢复窗口。既有付费Operation UNKNOWN保护不变。
- **下一单一动作**：围绕G3确定实际素材源/候选及具名模型和固定声线的验证条件，得到所需明确调用许可后逐项真实验证；完成前不开放G4、不启动S6-14。不重新做G0，也不重复索取已允许复用的本机配置路径。
## 2026-10-17 · 新的来源完善决策（Unsplash + BGM/SFX）

用户明确要求：**Unsplash 要实现可用于视频制作的接入**，同时完善 BGM 与 SFX。此前 G0/G1 主体已完成，本节作为 S6-15 G2/G3 未闭合工作包的追加要求，不将现有 preview-only 误写为已完成。保持既有 `MaterialNeed → ExternalCandidate → Rights/Library → material_uses → schema_version/asset_ids` 和 Voice 专用路径，不更改公共 Plan/Editor/Operation schema，不恢复 V1 第二状态机。具体选型见[素材层架构](../18_MATERIAL_LAYER_ARCHITECTURE.md)新增“外部来源扩展”。

1. **U1 Unsplash 官方规则核对及方案准入**：官方 API 的 `photo.urls.*` 热链接用于 UI 展示；当用户将照片纳入作品等相当于下载的动作时，使用原始 `links.download_location` 并保持 `ixid` 等原查询参数，认证调用；摄影师、Unsplash 署名、源照片链接始终可达。必须复核 API Terms、商业使用、照片实际版权与人物/商标/限制，保存审查依据。仅补 download tracking **不等于**已获将 API 图片永久下载缓存并剪入 MP4 的完整许可。不能在缺证据时绕过现有 Rights。
2. **U2 来源选择交易与真实绑定**：以用户明确选定的 `photo.id` 为输入，由服务端依据官方 API 再取来源元数据及允许的 URL，不信任客户端 URL 或 Rights 声明；对选中用途建立可恢复的选择/跟踪记录，限制并发重复；一旦具备允许该使用方式的权利与下载条件，经现有受控下载器、技术核验、catalog、引用、Work artifact 和 Editor `asset_ids` 完成同链路交付。缺明确许可/无法跟踪/不符合 API 约束时返回可观察的 `needs_decision`，不得“自动供料成功”。离线 MockTransport 正反例必须覆盖跟踪/获取失败、取消、来源改变、追踪响应未知/重试、防 SSRF、重启/多次点击、署名导出。自动后台选材是否符合条款单独验证，不由手工选择扩权。
3. **A1 BGM（优先于新的生成服务）**：沿既有 audio/music Need，通过本地库及人工审查的 `reviewed_public` 有限真实曲目目录供料；建立每条音轨的官方来源页、具体 Rights 版本、商业传播和改编允许范围、必要署名，以及试听音频/正式音频身份。Director 决定主题、情绪、节奏与出现区间，程序校验媒体时长、loop、音量和授权；不将音效冒充配乐、不从 Pixabay 视频 API 假设音频音乐接口。目录证据不足应阻塞，而非随意网络抓取。后续可扩展已证实拥有商用 API/授权的音乐 Provider。
4. **A2 SFX（按 cue 搜索）**：复用现有 `MaterialIntent.sound_cues` 的 `cue_id/scene_id/at/duration/required` 与 `MaterialNeed(audio,sfx)`、`AudioClip(role=sfx)`。先支持经审核本地/公开音效目录，必要效果缺口阻塞、可选点缀允许省略；同一音效在不同 cue 可复用字节但用途绑定不混淆。Freesound API 具有搜索与预览接口；原始素材下载须 OAuth2，公开开发者文档指出 API 免费使用主要为非商业，商业应用须评估获得额外许可。**未获得相应凭证与适用授权前不视为已接入自动生产**。
5. **共同验收**：不同题材有实测真实合法的图片/BGM/SFX 候选；来源失效、授权撤销、许可变化后全部依赖重新判断；相同音频多场景只保留有界物理副本；selected-only 依赖和 export credits 正确；远端检索与音效取得不消耗 IMAGE/VIDEO 生成额度，付费模型统一走既有 Operation。用户未授权的真实 API/模型调用维持 NOT_TESTED，G4/S6-14 不开放。

官方依据（2026-10-17 查阅）：[Unsplash API 文档](https://unsplash.com/documentation)、[Unsplash API Guidelines](https://help.unsplash.com/en/articles/2511245-unsplash-api-guidelines)、[Triggering a Download](https://help.unsplash.com/en/articles/2511258-guideline-triggering-a-download)、[Unsplash API Terms](https://unsplash.com/api-terms)、[Freesound API](https://freesound.org/docs/api/overview.html)和[开发者 API 许可提示](https://freesound.org/help/developers/)。

**此新增工作包状态：DESIGNED / NOT_IMPLEMENTED**。此前 Unsplash 已实现的仅为主动预览；BGM/SFX 原实现与本机只有一份 MP3 的事实不变。下一步先确保 U1/U2 的合法使用路径及资格证据成立，再按明确合法来源增补 A1/A2，不为当前 G3/G4 补齐进度而伪造供料成功。
### 最新 A1/A2 实施记录（覆盖上文旧排程）

- **状态：BGM/SFX 自动来源 CORE_IMPLEMENTED / REAL_DOWNLOAD_BLOCKED**。新增 `easel/production/providers/wikimedia_audio.py`：`wikimedia_bgm`、`wikimedia_sfx` 分别限定 audio/music 与 audio/sfx，走同一个官方 Commons API，不需注册或凭证；配置 `EASEL_WIKIMEDIA_AUDIO_ENABLED=1` 且作品内明确授权后才搜索。内部分流及候选 audio_roles 检查阻止音乐和音效互换；沿用本地库、reviewed_public、Director 选择、Rights、录入和音频编辑时序。没有新增任何管理 UI、AI 音乐生成流程或公共合同。
- **Rights / 字节安全**：只接受 Commons 文件页明确声明的 CC0 1.0 或 CC BY 4.0，CC BY 强制署名；非商业、禁止演绎、相同方式共享等未经适配的许可不自动录用。识别真实 Commons `application/ogg` 音频容器，不放行未知二进制 MIME；下载字节的 SHA-1 必须匹配文件 API 原始 SHA-1，文件变化不能因相同标题进入库。受控下载、SSRF 拒绝、状态/引用/恢复不变。Commons 声明仍有真实性风险，必须保留来源页并遵守使用条件。
- **公开接口实测（非生成）**：使用不带凭证的 Commons Action API 对 `rain` / `piano` 查询，均能返回 3 条符合当前白名单的候选元数据。一次真实媒体获取尝试被本机 DNS/公网保护拦截：`upload.wikimedia.org` 被解析为 `198.18.x.x`，属于非公网基准测试网段。**没有放宽或绕开防 SSRF 守卫，也未把真实下载、入库或自然听感记 PASS。**
- **离线证据**：`tests/production/test_wikimedia_audio.py` 覆盖两类搜索、错误/伪造授权、非法域名、CC0 legacy deed、MIME 和 SHA-1、许可署名、源文件变化拒绝、BGM/SFX 身份隔离、真实合成 WAV 受控入库复用、能力目录和默认关闭配置；相关全链检查与原始 assets 保护单独记录。Freesound 尚未申请 API Key/OAuth2 和商业 API 许可，故不是完成能力。Unsplash 按最新决定保持 preview-only。
- **下一动作**：优先在正常公网 DNS 环境执行合法 Commons 音频下载→FFprobe→素材库→Editor 的真实闭环（并核对导出 credits），然后补足按不同作品主题选择 BGM/SFX 的听感证据；如需要更多音源并决定接 Freesound，须用户注册与核实商业 API 权限。G4 / S6-14 继续阻塞；不继续 U1/U2。

## 6. G4 正式执行记录与暂停（2026-10-17）

用户要求“完成 G4，完成后暂停”。已经按既定 G4 门禁完成上下游冻结合同 SHA 回查、五模态逐项证据评审、真实免费 Pexels/Pixabay（图片/视频各 3 条）与 Commons（rain/piano 各 3 条）候选检索、CI 失败原因定位及可移植测试修复。完整证据、P0 阻断项和准入结论唯一维护于 [G4 正式报告](../19_MATERIAL_LAYER_G4_ACCEPTANCE.md)。结论 **G4_REVIEW_COMPLETED / NO_GO**：真实媒体安全下载未通过，仍不可把 G3 本机 Mock 视为真实生产；AI 旁白、素材试听及新 SHA CI 门槛需各自闭合。此轮不重做 G0/G1，不放宽 Rights/DNS/Operation，不开展 S6-14。**收尾后暂停，不自动继续。**

2026-10-17 后续专项复验：按用户新授权，Wikimedia 音效因通用 User-Agent 导致的 HTTP 429 已通过源专属识别性 User-Agent 修正，真实 SFX OGG 30423 bytes/1.473923s 完成受控下载、SHA1/Rights/FFprobe/隔离库验收；Pixabay 视频以前诊断用 15MB 上限不代表正式下载能力，真实 MP4 18717171 bytes/30.08s 在原安全边界下入库合格。模型/TTS 仅具通用 Key、缺具名 Voice 服务和真实调用授权，未发送收费请求；Director 真实试听与 Creator 成片未测。完整清单见 [G4 结果](../19_MATERIAL_LAYER_G4_ACCEPTANCE.md)，G4 NO_GO、S6-14 PAUSED。
