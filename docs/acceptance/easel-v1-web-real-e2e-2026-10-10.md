
# Easel V1 Web 真实 E2E：方案、操作手册与执行记录（2026-10-10）

> **文档职责（2026-10-11 主方案正式批准）：本文件是唯一 E2E 历史及未来运行证据账本，不再拥有独立生产执行标准。** 新生产的 R1–R6、U0–U6 唯一标准已由用户批准，见 [`New-Only → Web E2E 统一主方案`](../architecture/web-backend-new-only-cutover-plan-2026-10-11.md) §8（`APPROVED_SINGLE_EXECUTION_STANDARD`）；具体 U2/U5/U6 执行、模型/Provider/Build、服务与费用仍待单独授权。本文件下方旧 Proposal @3、410、旧 Material 链路、E0–E3 手册均为当时的历史事实与证据，**不再作为未来可执行命令**；7 次失败 Attempt、24/24 次调用、15 份原始捕获、现金/UNKNOWN、SHA 保持原样。以后每轮新增真实执行信息**只在本文件顶部**登记，不在 Creator Task 重复写运行流水，不另建平行账本。**

## 2026-10-11 用户调整：允许新Creation，以首条完整MP4为终点

原 `cr_70af2a4443b541998f929541ef9f4b84` 的7个失败Attempt、24/24计数和15份原始回复**保持不变，作为回归与审计证据**。不再要求续跑原作品，也不追加原作品独立8次技术调用。此前为旧作品的+8特殊恢复写入但未验证的四文件变更已精确撤回，原先13个tracked修改保留；针对性Python编译和恢复专项8 PASS再次通过。当前 **E1 = FAIL/BLOCKED，未有MP4**，此记录不声称已真实复跑。

新恢复流程：对已有失败按共同原因分组 → 原始响应离线重放定位可通用的接口/合同/程序问题 → 一次系统性修正及失败/成功路径跨阶段集成验证 → 确认Web/Gateway实际加载的冻结版本 → 通过 Easel Web **新建一条 Creation**，从内容确认跑到Planning/Truth、Material/Rights、Native Authoring/Hypit Build/Export/Quality/人工 Review。任何新失败先核对同类回归覆盖，不盲目添加单例Prompt或叠加技术额度。每个阶段仍按PASS/FAIL/BLOCKED/NOT_TESTED留证。

所有新旧Creation的本轮新增现金支出共享原 **¥10** 总上限；不能证明套餐权益或单次最高现金风险则停止新增扣费调用。不扩大到E2/E3、充值、自动付费回退或公开发布。原文下方2026-10-11 13:30暂停记录仍是真实历史状态；后续任何新Web作品须另记 ID、模型/素材调用、费用、Rights、Build/MP4 SHA。



### 本次跨阶段离线验证及当前阻塞（2026-10-11）

- **Preparation/Structured Result：129 PASS**（`tests/test_creation_preparation.py` + `tests/test_openclaw_structured_result.py`）；Planning 当前格式/捕获 **26 PASS**；Material P0本地 E2E **3 PASS**；Native Authoring **16 PASS**；Native Export/人工Review准入专项 **2 PASS**。这些属于分段及内部模拟验证，不应求和宣称全链E2E。
- **完整 Planning 单套：TIMEOUT/NOT PASS**（`tests/test_semantic_planning.py`，600 秒，上次输出至78%）；不要将未完成回归计为通过。UI lint **0 errors/1既有warning**、Vite/TS构建和Python编译及`git diff --check`通过。
- **跨阶段Creator集成测试：FAIL**（`test_same_creator_mode_three_contents_reach_reviewable_first_cut`）。老夹具最初只识别退役的Script Truth回复；临时更换为现行 `truth-source-ref@1` 后能推进到 Material，但仍以旧观察结果模拟，进入 `observe_material` 后未产生合法当前 `material-observation-delta@1` receipts；临时模拟迁移尝试出现 `Material result evidence is missing or changed`，无法证明成功。**全部未通过的临时夹具改动已撤回**，未放宽真实Material/Rights门禁。新集成测试需用当前五pin的真正Owner+合法固定外部响应，完成从同一新Creation到导出/审片的连续状态验证。
- **真实Web：NOT_RUN**。本次已核Easel首页 HTTP 200，但浏览器控制入口未获得可执行准入，因而没有真实新建Creation、MiniMax文字提交、Provider素材生成或Hypit Build；不声称Web E2E通过。仅有上一轮真实作品/Attempt的失败证据。
- **阻塞类别：** `SYSTEMIC_PLANNING_RELIABILITY_UNPROVEN` + `FULL_CHAIN_CURRENT_PROTOCOL_REPLAY_FAIL` + `WEB_E2E_EXECUTION_UNAVAILABLE`；账户权益/供应商实时最高现金风险仍需E0准入，¥10是共享累计新增现金上限而非自动付款许可。下一次真实新作品的前提是当前协议的连续集成回归和Web执行通道均通过，否则停止而不是再加一个Prompt版本。

## 2026-10-11 持续通关 V2（取代 V1 四 Gate 执行顺序；历史记录原样保留）

**同一个任务，两种不同的成功：**调试 E2E 允许故障归类、修复及在身份/版本合法时从持久检查点恢复，只记工程进展；最终 E1 PASS 必须是冻结版本、独立全新 Creation 从 Easel Web 全程生产的真实 MP4（中文旁白+BGM、合法 Rights、Build/文件 SHA、Quality 和人工 Review）。本文件是唯一 E2E 执行/证据账本；Task 定义授权/范围，Current State 汇总状态，Roadmap 定执行顺序。不得把模拟集成测试或跨版本各段 PASS 拼成最终通过。

### 1. 审计后的关键优化

- **收窄旧 Gate A：**现有三内容回放的失败首先属于“待分类的旧 fixture/现行协议不兼容”，不能直接推断是全链产品 Bug；先从中选一个符合现行 Creative Mode、包含 required 视觉/旁白/BGM 的代表作品建立最薄连续集成（不是降低合同）。只替代付费模型/Provider 等不可控外部边界；内部 Owner、Material/Rights/Readiness、Hypit Native/Review 走真实实现。须含真实合法正例、关键非法拒绝例和断点冷恢复；历史三内容夹具全面迁移与 600 秒慢套件不作为首片全部前置，也不能通过 skip 旧测伪造新链成功。
- **P0-A 与 P0-B 并行：**不要先花几小时修夹具、才发现 Web 无法输入。WebCodex 工具不能控制浏览器应记 TOOL_ACCESS_BLOCKED，不是产品 WEB_UI_FAIL。可由用户在真正 Easel Web 页面执行业务点击并以界面状态/真实请求及产物取证；不能通过 API/CLI/数据库伪装 Web。HTTP 200 仅代表存活，必须核对实际表单输入、保存、确认结果。Provider/套餐/成本/权利证据不能等到付费提交后才查。
- **严格区分 Debug 与 Release：**调试阶段可以用版本化本地代码补好问题、合法恢复已有 checkpoint；每次变更保留原件和指纹，跨版本阶段成功只记“找到并突破了一个关口”。收敛后需要一个新 Creation、一个冻结并核对已加载的版本完整跑通，不能靠旧成功阶段拼接。
- **不要求先完成所有质量治理：**E2 的三个新主题、正式 Planning 6/6、耗时/质量优化均放在首片之后。优先确保一条符合冻结业务规格、Right/费用合法、能完整审阅的真实视频，不人为把 required Need 降为 optional，也不强制调用没有费用上界的 H3。

### 2. 执行矩阵（先完成 P0 关键准入，再逐个真实业务关口）

| 工作包 | 允许动作 | 出口标准与证据 |
|---|---|---|
| **P0-A：单作品薄切片** | 真实内部 Creation→Preparation→Planning/Truth→Material/Rights/MATERIAL_READY→Native Authoring→Hypit 本地 Check/Export→Quality/Review，使用一组合法固定外部响应，当前五项 pin 均可用。先查现有旧三内容 fixture，再复用高价值测试，避免新建重复测试体系。 | 一条内部连续成功路径 + 关键合同拒绝 + UNKNOWN 对账/冷恢复；记录模拟边界与版本，标 SOFTWARE_INTEGRATION_PASS 而非 E1 PASS。若现有老测试是测试债，明确标注，不用跳过它替代新证据。 |
| **P0-B：Web/运行/费用准入** | 与 A 并行，无需付费；实际验证 Web 页面操作路径和内容确认，核对 Web/Gateway/OpenClaw/Hypit 源码/配置及加载身份、Creator/Mode、MiniMax 身份/权益、Material Provider Rights、Hypit/素材单请求可能的最大现金风险、未结算操作。 | 产品 UI 可用/工具控制可用分别记账；保存相关源码和运行件 SHA、版本差异、调用/现金/权益/授权证据。Rights UNKNOWN 或费用上界不明仅阻止对应外部调用，不阻止离线修复。 |
| **P1：真实 Web Debug Run** | P0 的对应安全/合同条件满足后，选择一个合法、易观察但非玩具的 45–60 秒、9:16 中文旁白+BGM 主题，通过 Easel Web 新建 Creation，逐关执行 Planning/Truth→Material→Native Authoring→Hypit Build/Export→Review。一个真实回访只检验一个已修复错误家族；费用/调用预算和 UNKNOWN 状态仍逐调用核对。 | 每阶段状态 PASS/FAIL/BLOCKED/NOT_TESTED，Creation/Attempt、原始 SHA、请求/operation key、模型/素材账、Rights、Build/媒体证据。合法检查点允许 Debug 恢复；不得借新 Creation 清空旧账或跳过页面。 |
| **P2：通用根因闭环** | 当前最早失败关口：先保全完整原件、运行身份与远端执行状态，再定位真正 Owner，只修这一个通用故障类；用原始失败重放 + 合法正例 + 非法反例 + 关键跨阶段集成验证，确认实际加载新 fingerprint 后才继续有界真实调用。 | 错误家族 ID、真实失败原件/版本、根因、修复范围、可复验正反结果和未受损合同。不能靠一个新 Prompt 条款、吞掉 schema/语义拒绝、增加技术上限而直接判 FIXED。 |
| **P3：冻结版 Release E2E** | 工程缺陷修复收敛后，冻结源文件、协议、配置、运行安装件和 Web/Gateway/Hypit 实际加载摘要，创建独立全新 Creation，用普通 Easel Web 完整出片。禁止工程师修改已运行的代码/素材/数据库凑结果；合法 Creator 审批不算工程救火。 | 新作品的全部关口在同一 fingerprint 下真实通过：MP4 可播放与音轨、Rights、资金、Build ID 和输出 SHA、Quality、人工 Review。此时记 E1=PASS；后续 E2/E3 另行授权。 |

### P0-A 两项强制出口（从旧交接基线恢复的关键保障，不新增大规模前置）

**L1 历史七次真实 Planning 失败必须逐项处理，不是逐项放宽通过：**为 7 个 Attempt、15 份原始捕获建立一份紧凑的证据映射与原件回归（可复用本文件现有原件引用和既有测试，不另建平行表/Task）。逐项覆盖：`required dynamic_action` 被静图承接、role 超长、B 调用丢失、framing mode/ratio、B 引用对象形态、A-details 游离字段、BGM `tempo_bpm` 对象包装。记录原件 SHA/请求版本、责任层、预期行为（有界接受、可证语义等价 Normalize、局部修复、拒绝或 UNKNOWN 原操作对账）以及**真实回放或明确不可回放的证据**。不存在原始回复的外部异常只允许标 `NON_REPLAYABLE`，以固定故障注入验证责任边界，不能伪装成旧原文已经恢复。完成标准是七类风险都有正确且可重验的判定，**不是七份非法输出被全部接受**；历史真实 FAIL 不改写。

**L2 当前五 pin 的单作品本地真 MP4 必须产出：**固定合法模型/Provider 响应仅作为外部替身，真实内部 Creation/Planning/Truth/Material/Rights/MATERIAL_READY/Native Authoring 处理后，调用已安装 Hypit 的**本地 Check→Build→Export**；检查真实 MP4 非空、SHA、视频流、中文旁白音轨与 BGM 混音结果，并经过正式 Quality/Review。不得 Mock 渲染/导出、跳过 Rights 或直接写 READY。复用现有 `replay_vnext_native_hypit` 的本地能力但必须证明它对当前五 pin 真实连通；旧三主题测试全量迁移仍不作为首片前置。无本地真实 Build 时只能标 `L2=BLOCKED`，不能把 Check/模拟 Export 认作内部全链 PASS。

**进入 P1 的判断：**L1 七项有完成的处理/拒绝/不可回放证据，L2 至少一条代表作品真实本地 Hypit MP4/Review，P0-B 真实 Web UI/加载版本/模型 Rights 与逐调用预算准入成立。以上不要求做 32 次模型 Eval 或三主题稳定性；P1 首次真实模型调用才开始测结构接收率、语义通过情况、合法局部修复次数、总调用成本。若 P1 产生新类型错误，则按相同原件回归闭环补齐，而不是扩张 Prompt。
### P0-B 补充：Web 入口旧协议清理与准入证据（2026-10-11）

**原因：**ADR-005 完成的软件结果协议清理未覆盖全部 Web UI 与 Web API 生产入口。只清理 `Material/Truth/Quality` Writer 后，旧 `legacyDelivery` 前端自动恢复及独立 Authoring/Build/Export 按钮仍可触发与唯一 Delivery Owner 并行的生产路径；`web/app.py` 的聊天确认、Script Truth 审阅还留有非 managed → 旧 Preparation → 手工 Authoring 回退。**上述旧执行路径已按新作品唯一主线进行源码级切断，不仅仅是隐藏按钮。**

- **Web 前端：**`web/frontend/src/components/FilmOperatorPage.tsx` 的旧自动轮询/核价/导出、Provider 直接生成及高级面板手动调度按钮已删除；新作品主操作只在 managed Delivery 上出现，历史 Attempt 的高级面板改为只读证据。原明确的方案确认、必要人工 Truth/Material Rights/Match、费用确认、Quality/Review/最终选片仍在正规 Owner 下保留。`web/frontend/src/lib/api.ts` 的无人使用旧分阶段客户端操作函数已删除。
- **Web 服务端：**`web/app.py` 中旧 Handoff/Attempt、Authoring、Runtime/Check/Pricing/Build/Refresh/Reconcile/Export、MiniMax 直接素材生产的手动 POST 统一以 `410 Gone` 拒绝。正常确认只接受 `easel-creation-delivery@1`；旧 chat Preparation、Script Truth 后重启旧生产链均拒绝或只读。历史 GET 和已存在的原始运行证据保留，不删除或升级旧 Attempt；用户成本批准与显式人工复核仍可进行。
- **回归范围：**新增 `tests/test_web_newonly_routes.py` 测试旧 POST 拒绝、历史 GET 只读、旧 Chat 回退阻断、人工成本批准；旧的 `tests/test_creation_preparation.py` 相应断言迁移到“旧 Web 不再执行”。前端构建/lint 可证本地 JSX/类型有效；无完整浏览器控件实际点击时不得宣称 Web UI E2E PASS；正式服务进程若未重启并核验 SHA，不得宣称已加载修复。
- **验收界线：**本次只处理 Web 入口单线化，不表示 L1 七类真实 Planning 故障、L2 本地 Hypit MP4、P1 实时模型或 P3 真实成片已通过。旧 7 Attempt、24/24、15 Captures、Rights 与 ≤¥10 本轮现金账均保持不变，不主动部署触发付费工作。

### 3. 一个失败的处理决策（最多有界真实回访，禁止循环补丁）

1. **先检查远端是否已执行，绝不直接重试。** 保存最早失败关口、run/tool 原始回执 SHA、创建/尝试/操作 identity、协议与模型路由、Prompt revision、Gateway/Runtime 实际加载、费用/额度。PENDING/SUBMITTING/UNKNOWN 只能沿原 operation 观察/对账；不因重启、更换 Creation 或模型而重派。
2. **归类且区分测试债：**TEST_FIXTURE_STALE、EASEL_CONTRACT、WIRE_REPRESENTATION、MODEL_SEMANTIC、TRANSPORT_RUNTIME、MATERIAL_RIGHTS、HYPIT_BUILD、WEB_UI、COST_QUOTA。故障家族需包含责任层、阶段、字段/合同、原始证据；不同根因不混计。旧 fixture 问题不要改产品合同迎合它，生产 Bug 也不靠改 mock 掩盖。
3. **只修一类系统原因。** 纯机械表示仅在能证明保留语义、来源、许可、数量的情况下版本化 Normalize，保留 raw、派生 receipt；语义未覆盖/required 与 optional 冲突必须交已有 Owner 有界重新判断；Rights/来源/价格/身份不允许猜造。回归至少覆盖原始失败、合法成功和不应被接受的错误。
4. **修复后检查受影响完整链路。** 软件集成可使用合法固定外部响应，但真实内部 Owner 不可模拟直接 READY；测试 TIMEOUT 记 TIMEOUT，不可记 PASS。无需每次跑过所有历史慢测；真正影响到的生产合同/集成测试必须通过。重新核对工作区与实际运行指纹，才派一次新的真实诊断请求。
5. **熔断与暂停。** 同根因两次针对性修复仍失败→Main + 独立 Reviewer 复核问题所属边界、两个修复为何无效、下一个可离线证伪的假设，停止新增计额/付费请求；连续两轮真实诊断没有新业务关口、也没有被正反验证的通用缺陷收敛→暂停反复试跑，输出准确 BLOCKED 和唯一下一动作。出现未知账单、Rights UNKNOWN/RESTRICTED、未知 Build 状态、版本与证据不一致直接安全停止，不得更改合同绕过。

### 4. 衡量进度与跨窗口唯一检查点

- **业务最远关口**（只能用实际 Web + 同一 Creation/fingerprint 认领）：方案正式确认 → Planning/Truth → MATERIAL_READY（MaterialRequirement→ResolutionResult→BindingResult，业务合同不变）→ Native Authoring/Check → Hypit Build/Export → Quality/人工 Review。离线模拟进度独立标 SOFTWARE，绝不混入真实前沿。
- **缺陷燃尽**：实际故障家族的首次/复发次数、能否原件离线复现、是否有合法+非法回归，修复后是否在新版再次出现。Prompt 版本增长、Attempt/测试数量或 API 200 都不是通关。
- **成本与工程干预**：分别记录文字模型、素材、TTS、Hypit 请求次数、技术额度 used/limit、已发生现金、UNKNOWN/待结算、下一请求最大可证明现金风险、Creator 正常业务确认次数和工程手工修改次数。所有本轮新旧 Creation 新增现金共用 ≤¥10；旧原作品 7 Attempt、24/24、15 原件只读保留，新作品自身业务额度不得重置旧账。

每次执行后**只在本文件顶部**更新：RELEASE（HEAD+相关源码 diff/file hashes + 实际 Web/Gateway/Runtime 版本）、RUN（Debug/Release、Creation/Attempt）、REAL_FRONTIER、SOFTWARE_GATE、ERROR_FAMILY（Owner+证据）、FIX_AND_REPLAY（正反与跨阶段）、COST/RIGHTS/UNKNOWN、NEXT_SINGLE_ACTION。跨窗口先检查已有 Job/任务与 dirty diff；多个 Scout 可只读调查，但共享工作区只有一个 Main 具有写入责任。

**现阶段准确入口：**原三内容集成仍因旧 Truth/Material fixture FAIL，Planning 整套 TIMEOUT；新作品真实 Web 尚未执行；WebCodex 工具控制受阻需要与产品页面能力分别核实。下轮先执行 P0-A 当前五 pin 单作品薄切片，P0-B 并行无付费验证页面、运行版本、Rights 与费用。两个关键准入不足时不启动新的模型/媒体/Hypit 有价提交。

> **唯一归属：**[自主首版 Task](../tasks/creator-autonomous-first-cut-2026-09-30.md)；本文件合并用户 E0–E3 长方案与此前 S0–S3 Web 实操，不建立第二套 Task、Agent、状态机或生产链。历史证据不清理，当前状态见 [Current State](../02_CURRENT_STATE.md)。

## 2026-10-11 13:30 恢复验收记录（覆盖下方历史阶段结论）

**实际总状态：E1-S1 方案与 Preparation/Handoff 已真实通过；Planning = FAIL/BLOCKED；E1-S2 MATERIAL_READY、E1-S3 Hypit Build/Export/Quality/Review = NOT_TESTED。** 页面入口是 Easel Web，原 Creation 为 `cr_70af2a4443b541998f929541ef9f4b84`，已确认的片长 50 秒、9:16、简体中文、旁白+BGM；Creator「个人经营实践」、Creative Mode「清醒备忘录 · 视频 · v1.3」。没有新建另一个 Creation 或通过 CLI/API 跳过页面制作。

**真实运行核对（对账后不重试）：** 原 Creation 的 7 个 Attempt 均已冻结原件；Preparation 模型调用共享技术额度 `used=24/limit=24`（累计 24 次，22 次 `ok`、2 次 `error`），已用尽。最新 `fa_eb89de3f9300c1851378db0455157d40` 停在 `preparation=FAILED`、`delivery=failed`、`exhausted_operation=...:prepare`；根因仍是 Planning A/B 的模型结构或语义合同不合格，而不是素材供应商或 Hypit Build 故障。未出现本轮未结算 `pending/submitting/unknown` agent 调用；素材生成记录数 0、Build 提交数 0、MP4 产物 0，不能据此推断文字套餐实际现金扣款为零。

**七次原始证据：** 各 Attempt 的 `materials/recoveries/semantic-planning-vnext.json` 保留；本轮只读核验 7 份 journal、15 份原始模型捕获的 SHA 均匹配，无改写或清理。失败形态按顺序涉及静态图 required dynamic_action / 源义务；候选 role 超长；B 调用丢失；`framing` 非法组合；B 引用对象形态不合格；A-details 顶层散落字段；最后一次 @10 BGM `sound.tempo_bpm={"item":[60,90]}`（正式合同要求长度 2 的整数数组）。最新新请求版本 @11 已加“无明确 BPM 则省略，否则 `[60,90]`”的提示；旧 @10 A-details 提示 SHA 离线复核与原始 `request_sha256` 精确一致，新 @11 提示只做了新的有界说明，但**还没有新的真实模型调用或完成 Planning 证据**。

**代码/测试：** Git 基线 `615974e2a94bed80a3840ea9f7c9aabe602850b5`（本地与远程相同）；现有 13 个 tracked 修改在工作区、未提交/推送，包含 Web 恢复/确认预算修复、Planning 版本化提示、方案修订隔离及对应测试。专项测试 `tests/test_semantic_planning.py -k "versioned_review_batches or frozen_intake or new_b_quote_wire or vnext_query_fault"` = 6 PASS；`tests/test_creation_preparation.py -k "reopen or revision or failed_planning or preparing or budget"` = 8 PASS；`tests/test_creation_preparation.py tests/test_openclaw_structured_result.py` = 129 PASS；慢用例单独隔离 = 1 PASS；前端 oxlint 0 error（现有 1 warning）、TypeScript/Vite build PASS；`git diff --check` PASS。大范围 Planning 回归分别在 240s、110s 截止而**非整套 PASS**。`@11` 的提示修复仅离线验证，不声称模型真正改善。

**当前暂停门禁：** `PREPARE_CALL_LIMIT_EXHAUSTED`。¥10 新增现金授权仍有效，但属于货币边界，**不能自动替换独立的 24 次技术调用上限**。不得因用户说“继续”就清零 `call_budgets`、重新发送旧 Planning Request/UNKNOWN、改变历史 Attempt、创建第 8 个 Attempt 冒充已完成验收，或直接调用 Hypit 制片。本轮所有新增真实文本/媒体请求均已停止。只有在明确批准“为此原 Creation 在保留已用24次的前提下追加多少次模型调用”、并确认新增代码的业务/技术准入后，才可以使用 Easel Web 原「修改方案后继续」入口逐关口执行；新模型请求应保留新的操作键和原失败证据。若无需继续额外调用，可保持 FAIL/BLOCKED 并复盘，绝不虚报首片出片。

## 1. 最小执行方案

**目标：** 一位 Creator、一个现有 Director / Creative Mode、一个新主题，通过 **Easel Web `http://127.0.0.1:7860`** 产生真实可播放、可在 Easel 内审阅的 MP4。禁止以直调 Python、OpenClaw API、Hypit CLI Build 或改数据库凑出“Web E2E PASS”。

| 阶段 | 业务动作（都在 Easel Web） | 判定 |
|---|---|---|
| **E0 只读准入** | 版本、Web/Gateway、固定 Creator/Mode、Model/Provider/Right/费用及旧 PENDING/SUBMITTING/UNKNOWN 检查，不建新 Creation，不发模型请求 | 版本对齐且每个实际扣费请求的可证明最高新增现金风险在 ¥10 剩余额度内；否则停在明确阻塞 |
| **E1-S1 创作方案** | 新对话输入主题，讨论剧本/分镜/声音，Easel 正式确认，创建本轮唯一新 Creation/Attempt，真实 Planning A/B 和 Truth | 真实语义/原件合同合法、可冻结身份与来源 |
| **E1-S2 真实素材** | 作品页面处理图像、旁白、BGM 的正规来源、Match、Inspector、Rights / Readiness | 所有 required Need 都有合格资产，`MaterialBundle + MaterialReadiness = READY`，optional 缺失不自动阻断 |
| **E1-S3 出片审片** | Easel 原生 Authoring→Hypit Check/Plan/Pricing/批准→Build/Export→Quality→人工审片/选择 | 真实 MP4 可播放、音画齐全、输出 SHA/权限/成本可对账；人工接受与公开发布分开 |
| **E2 稳定性** | 同一冻结版本 3 个新主题、3 条独立 Creation | 3/3、零工程技术救火、零未知收费；**本轮不启动** |
| **E3 质量效率** | 主题、导演一致性、素材、声音、观感、实际现金和各阶段耗时 | 可先以均分 ≥3.5 / 单项 ≥3 作为候选标准，但**未真实审阅就记 NOT_TESTED**；**本轮不启动** |

主题候选：**《AI 时代，一个普通程序员的深夜》**。建议 9:16、45～60 秒、中文旁白与 BGM，人物为虚构，不能宣称 Creator 的真实个人经历。遵从冻结的当前 Mode，不为符合建议规格修改 Director 风格。E1 功能成功（真实片通过技术与内容审阅）与自主成功（无工程手改素材/Run/数据库）分别记账。普通用户方案/权益审批不算“工程救火”。

## 2. 严格按 Web 点击的执行手册

1. **E0：**浏览器访问 `http://127.0.0.1:7860/`，核对“网关已连接”；选择现有“个人经营实践”画像与“清醒备忘录 · 视频 · v1.3”风格；只读核对 Git SHA、Web/Gateway、Hypit、Provider/模型认证与套餐、各类素材可用性、旧的 UNKNOWN/执行中状态，以及现金风险。E0 不发送聊天、不创建 Creation。
2. **E1-S1：**在“对话”→“新对话”输入下面的主题/制作意图。**发送是实际模型请求，必须在 E0 的费用/权限门禁通过之后。**阅读 Easel 正式方案，经现有确认界面确认后，只生成**一个新的** Creation / Attempt，记录冻结内容、Creator/Mode 和 Planning/Truth 状态。
3. **E1-S2：**继续该 Creation 自身的视频制作卡片，查看 Need、素材候选、Rights、预览与成本；通过原生页面按钮获取或补足所需图像/声音。每次可能扣费前重新算现金风险。仅当所有 required Need 合格且页面/实际业务证据达到 `MATERIAL_READY` 才继续；Rights UNKNOWN / RESTRICTED 不能绕过。
4. **E1-S3：**页面推进 Native Authoring、Hypit Check、Plan/Pricing。**软件里的 USD `approved_budget_usd` 不是支付平台硬上限**；真实新增现金上界已证实后，使用页面原有确认操作最多一次 Build，再通过 Easel 页面 Export、系统 Quality 与人工 Review；保存输出 SHA、MP4 播放/音轨观察、是否入库，不发布。
5. **遇阻即停：**标记 `MODEL / CONTRACT / MATERIAL / AUTHORING / BUILD / RUNTIME / QUALITY`；保留可合法保存的原始模型/Provider 回执、外部 operation key、时间/费用、失败原因。已开始提交但结果 UNKNOWN 先对账，绝不盲目重派；不可通过直接运行内部函数或修改文件让 E2E 伪 PASS。代码/Runtime 实质变更后，旧版本的稳定性数据不得冒充同版 3/3。
6. **判定：**对每一关只记 `PASS / FAIL / BLOCKED / NOT_TESTED`；正常 Creator 批准与工程师手动修复分开计数；记录总墙钟/实际执行/等人确认时间；真实评分不得预填。

**E0 通过后才可发送的 Web 消息示例：**

> 请使用当前“个人经营实践”画像与“清醒备忘录 · 视频 · v1.3” Creative Mode，为主题《AI 时代，一个普通程序员的深夜》策划一条约 45～60 秒、9:16 的中文短视频，有中文旁白和 BGM。人物为虚构，不能声称是我的真实经历。先在 Easel 讨论具体故事、分镜、声音和素材方案，我确认后再启动生产；请保留已冻结的导演风格。只使用本次明确授权的素材和费用，累计新增现金不能超过 ¥10；不能证明费用上界时必须停下，不自动发布。

## 3. ¥10 预算与停止线（不继承旧 ¥30）

用户已授权 **本次 E1 单条新作品新增累计现金支出上限 = 人民币 ¥10.00**，不授权 E2、购买余额、充值、自动套餐升级、付费 fallback 或发布。报价、套餐/积分扣减、真实现金支出分开记录；人民币总支出上界应同时计入已发生、已占用/待结算、下个请求最大可能的现金成本。不能证明上界就 `BUDGET_NOT_PROVEN`，**不触发该外部请求**。USD 额度/估价不是硬限； UNKNOWN 不能记 ¥0；提交不确定先对账，不因为失败重启而清零。合法零新增现金的订阅权益也必须得到当前证据，不根据用户历史猜测。

## 4. 2026-10-10 实际 E0 结果（本轮执行现场）

| 已执行检查 | 实际证据 | 结果 |
|---|---|---|
| Git / Web / Hypit | `easel-studio` 与远程同 SHA `615974e2a94bed80a3840ea9f7c9aabe602850b5`；Gateway、Web 正常运行；Hypit 0.2.7 | PASS（环境基线） |
| **真实 Web UI** | 浏览器打开 `127.0.0.1:7860`，页面显示“网关已连接”；选择画像“个人经营实践”后，Creative Mode 显示“清醒备忘录 · 视频 · v1.3”；未创建 Creation 或发送模型消息 | PASS（E0 页面准备） |
| Core-video 就绪 | 21 项依赖综合 `NOT_READY`；`openclaw.model-auth` / `model-endpoint` = `NOT_VERIFIED`；1 份 Rights sidecar 是结构有效记录，但 `material.visual-source = CONTENT_EMPTY` | BLOCKED（不能直接认领真实制作已准备好） |
| Generation 配置 | 3 项依赖，`READY`，但不等于真实生成/收费/可用权益 | CONFIG_READY |
| 历史 Attempt 只读摘要 | 最多检查 200，实得 20 个 Creation、16 个 Hypit Attempt：11 `NOT_SUBMITTED`、4 `BUILD_COMPLETE`、1 `BUILD_FAILED`；未在这组中找到非终态/未知 Build。历史独立 Planning HTTP UNKNOWN 仍按封存证据保留 | PASS（仅上述样本范围） |
| Provider/现金上界 | 真实模型套餐/认证、新素材路线、Hypit Provider 可能扣费的有效上限，**仍缺可核证据**。不能将目录价或审批金额充当最大支出约束 | **BUDGET_NOT_PROVEN** |
| E1 创建、Planning、素材、Build、MP4 与审片 | E0 支出风险未准入前，没有发起实际模型请求，没有创建新 Creation | **NOT_TESTED** |

**额外 E0 费用核对：** 当前 OpenClaw 隔离配置默认模型为 MiniMax-M3（单次模型输出配置上限 8192 tokens），本地存在相关凭据配置，但这**不证明实际认证或套餐扣费身份**。官方 [MiniMax API 价格表](https://platform.minimax.io/docs/pricing/overview)公布 M3 令牌计价、image-01、TTS 和 H3 视频的公开目录价；这些不是当前账户的现金硬上限。尝试通过官方只读套餐余量入口核验当前密钥时出现网络 `URLError`，**没有取得账户权益/现金上限凭据**。首条优先评估具备实际 Rights 的免费 stock 或已批准素材；不要在未证明限额时触发按秒收费的 H3 视频生成，也不要因先前目录价很低而默认放行自动多轮模型调用。

**本轮统一结论：`E0 = BLOCKED_FOR_PAID_EXECUTION`，`E1 = NOT_TESTED`。** 此处停止的是**有现金风险的真实外部提交**，而不是倒退重新做 ADR-005 或 Planning 架构。下一动作只核实模型套餐的当前增量现金权益及素材/Build 可证明的上界；满足¥10和现有业务准入后，再在此方案下从一个新 Creation 继续。此 E0 结论不能冒充真实 MP4 E2E PASS，历史费用、FAIL/UNKNOWN 与预算原件未改。

## 5. 最新 E1-S1 真实 Easel Web 执行进度（2026-10-10，后续授权）

用户随后明确表示已购买 MiniMax 套餐，并授权先通过 Easel Web 使用模型；继续遵守单条 E1 新增现金预算 ¥10，不充值、不自动切换按量或发起无上界的媒体费用。本节**覆盖前述 E0 阻塞时点的“没有请求/未创建”历史状态**，不是重写早前检查记录。

- 已在 Easel Web 的同一对话中真实发送主题《AI 时代，一个普通程序员的深夜》及两轮补齐/规格整理要求，收到模型回应；自动建立单个 Creation `cr_70af2a4443b541998f929541ef9f4b84`，选定既有「个人经营实践」和「清醒备忘录 · 视频 · v1.3」。使用 Web 页面选择 50 秒、9:16、旁白与音乐、简体中文；最初回复因没有将纯旁白代码块与镜头说明分开，被正式方案解析拒绝。通过**同一 Web 对话**输出五个严格章节后，后端方案达到 `READY_FOR_CONFIRMATION`，有 `easel-video-proposal@3` 及有效 SHA，未新建第二 Creation。
- 正式点击「按这个方案制作」后，页面两次显示业务校验错误「已确认旁白缺少对应的技术身份和预算授权」。只读核实作品仍在 `PROPOSAL`、`confirmed_at` 为空、`delivery` 未创建、`Attempt` 数量 0。缺口是 v3 确认时预置旁白技术身份须随合法的素材生成授权一起写入，未触发 Planning、Provider 素材生成、Hypit Build 或 Export。不存在可以冒认的成功出片。
- 尝试通过 WebCodex 浏览器 UI 的 `set_value(10)` 写入页面的「本次自主素材生成总预算（人民币）」控件，但截图证实页面仍为空、React 控件值未实际保存；重复确认会得到相同拒绝，**已停止重复点击**。这是本次浏览器操作入口与页面控件的实际阻塞，不允许通过 Python 直接确认 Creation、写数据库或 API POST 绕过 Web。
- **最新状态：`E1-S1 = BLOCKED_AT_WEB_CONFIRMATION`，`E1-S2/S3 = NOT_TESTED`。** 下一操作仅需在 Easel Web 现有作品右侧把「本次自主素材生成总预算」实际输入 `10` 元，肉眼确认输入框显示 10，再点击「按这个方案制作」一次，并按 UI 的 Rights/文字使用范围及费用提示确认。完成后继续读取同一 Creation 的阶段投影和预算状态；不重发模型消息、不新建 Attempt、不购买额外套餐。
- 本轮有真实订阅模型交互，**未查询到可靠的账户现金扣款明细**，因此不得以模型回复成功冒称新增现金一定为 0 元；已知本轮没有主动执行媒体生成或 Hypit Build。
