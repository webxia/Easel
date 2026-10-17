# S6-15 · Material Layer 现状审计与完善（S6-14 前置）

状态：**PARTIAL — G0/G1 完成；G2 核心软件已实施；G3 本地软件验收通过；G3 真实服务及 G4 未通过**。2026-10-17 用户进一步授权完整审计、架构选型与实现，取代上一轮仅建文档的范围。**当前唯一实施前置任务**；素材层完成验收后才恢复 S6-14 首次真实生产及完整范围验收。本卡任务 ID 是后续补充，不重新编号 01～14，不改变其历史完成记录与 S4 需求责任分配。

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
