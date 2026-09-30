# Easel Current State

Last audited: 2026-09-30. This is the single summary of current implementation and verification status. Source and tests establish behavior; dated Acceptance documents provide evidence for named runs. `SOFTWARE_ACCEPTED` never implies `REAL_WORLD_VERIFIED`.

## Snapshot

| Area | Current status |
|---|---|
| Product | Official `ai-film` Web path is connected through Material Gate, Hypit authoring/execution, and Easel output review. Overall V1 remains **PARTIAL / NOT_READY**. |
| Material Layer | P0/INT/P1 supply contracts are software accepted. MiniMax Image/Video/preset-voice TTS and ordinary Gate are software connected; isolated Image, Video and Voice outputs passed technical inspection. Generated Rights remains unknown and Readiness is NOT_READY; full Creation/Production use is unverified. |
| Local visual Product E2E | **REAL_WORLD_VERIFIED** for one named Creation through human-approved Selected Output; it does not establish full V1 or multi-Content consistency. |
| External Material Product E2E | **REAL_WORLD_VERIFIED** for one standard-chat Creation through Pexels Search/Acquisition, MaterialReadiness `READY`, Production Authoring, Hypit Build, Export, Review and Selected Output. The [named Acceptance](acceptance/external-material-product-e2e-2026-09-29.md) records the initial MaterialReadiness stop; the same Creation was subsequently completed. |
| Runtime profiles | `generation` is **READY** (configuration only). `v1-release` is **NOT_READY**: model auth/endpoint and `audio.production` require live verification. Hypit 0.2.7 doctor, Runtime Worker and both local Programs are ready. |
| P3 | **NOT_STARTED**. |
| Test suite | Last completed full run: **482 passed, 5 skipped** on 2026-09-28. Latest Goal verification covers **158 targeted Truth/Preparation/Material/Hypit/Authoring tests** and deterministic frontend projection; frontend lint/build passed. Earlier isolated desktop/mobile browser evidence remains separate; a new full suite or live E2E run is not claimed. |

## Creator 作品工作区（2026-09-30 软件验收）

- Conversation 与 Work Canvas 分栏；窄屏“对话 / 作品”切换、待处理数量、稳定输入框和独立滚动面。作品从 Proposal 出现；作品状态从现有 Creation / Attempt 恢复，不依赖聊天中另发“继续”。七阶段进度由统一只读投影提供，默认收进“查看制作进度”。
- Proposal 卡与显式确认共用服务端字面规格解析；时长、明确画幅比例、音轨和语言缺失时留空。示例、问题、上限和歧义不补猜；未知规格要求通过对话补足。确认后保存同一组规格与原有对话哈希，Preparation 冻结前校验相同值，规格漂移阻断。旧 Creation 的已冻结输入未被迁移或修改。
- 无 Attempt 的准备失败直接显示失败原因、已保留结果和阶段 Retry。后续状态优先于旧 Preparation 失败；各类读取分别保留连接错误，失去连接显示最后可信状态。状态读取不会重新派发 Planning / Authoring / Provider。
- 事实、按场景的素材 Match、素材 Rights 与当前费用各有任务卡，继续使用原有正式门禁。观察按 Need 与 Asset SHA 隔离，切换后清空；已有来源、许可与证据预填。Match / Rights 使 Gate READY 后直接进入正式 Authoring API，不生成额外“继续”聊天回合。
- 成片播放器、当前技术检查、一次人工审片与 Selected Output / 内容库链保留。一般反馈和时间点反馈绑定当前输出与 SHA，时间点不得越过实际时长；不自动发布。
- 最小可执行修改为**构图与转场**：复用已验证的 Planning / Truth / Material checkpoint，以输出身份、反馈和 fingerprint 建立幂等新 Attempt，重新 Authoring、Plan / Pricing / 费用批准与最终审片。不重新供应素材，不复制旧费用批准，不自动提交 Build。脚本、规格、声音、字幕和素材替换明确提示需重新确认方案，不提供伪执行按钮。
- 高级信息默认折叠；移除聊天输入框中的重复制作确认及高级区重复审片播放器/批准入口。
- 验证：后端定向覆盖 110 项（109 passed / 1 deselected 的组合运行，显式确认 API 单独通过；后续 11 项关联回归通过），前端状态投影场景、隔离 Chromium 桌面/390px 窄屏场景通过。页面检查覆盖 Proposal、无 Attempt 失败、编排失败、素材任务、费用、可播放的确定性测试视频、输出绑定的时间点反馈及修改派发、运行状态与断连；全部接口拦截，未调用真实 Provider / Authoring / Build。lint/build、compileall、skill 合同与 diff check 通过。保留 AccountsPage 既有 Hook 警告及构建体积提示。
- **验证边界：** 未修改或继续当前 Creation，未执行付费 AI、真实 Build 或完整 E2E。真实 Creator 审片、修改结果与外部制作验收由 Creator 随后操作；软件测试不代表真实视频效果已验证。

## Creator E2E 前修复（上一轮修复基线）

本轮只修改代码、任务书、UI 和确定性验证；未继续当前 Creation，也未启动新的完整 E2E。当前人工 Creation 仍由 Creator 后续操作，Build 尚未提交。

- Material Match 对视觉 Need 要求当前素材的实际画面观察或按 Need 与 SHA 绑定的 Creator 核对。技术、Rights、语义与 hard constraint 每项都要成立；Readiness 重新核验 Match，不能把没有证据的重复素材当作覆盖。未核验素材保持 NOT_READY。
- 已完成 Material Gate 的 Preparation 恢复直接复用当前 checkpoint；生成素材 Rights 核对与视觉匹配核对只在本地重算，不再次进入 Provider Supply。
- Hypit 0.2.7 Task Book、Prompt 和 Retry 已按本机 Surface 收敛；Easel Run JSON 身份校验通过后才生成 native Run。隔离 Authoring 产物提升前执行本机 `hypit check`，失败产物不覆盖可信文件。静态图片与音轨各有一份本机 0.2.7 最小工程通过 `hypit check`；这不证明当前 Creation 的 Authoring 已完成。
- 已确认视频时长上限短于全部可用旁白时在 Authoring 前阻断；Authoring 产物在当前选定 Voice 与固定 Timeline 时长不符时阻断。图片 Item 的 Extent 按实际检查宽高核对，Canvas 仅表示画布。
- Creator 页面展示七阶段 Timeline、失败阶段与原因。Authoring/Plan 的 Retry 保留已完成的 Planning/Material checkpoint；已确认失败且可从 Hypit 核实的 Build 可新建同 Creation 的恢复 Attempt，重新绑定已验证的 Planning、Material、Script Truth 和 Authoring，新的 Plan/Pricing/费用批准仍是必要步骤。提交不确定时继续先对账，不允许重发 Build。技术 QC 继续自动校验文件、SHA、音视频流与完整解码；事实/风格 PASS 必须有当前成片的人审依据。
- Preparation 格式示例已移除 2.5 秒占位 beat；Agent 交付前可执行与冻结相同的只读四文件合同校验，重试携带原始脱敏诊断，聊天显示实际失败原因。当前 Creation 草稿未被修改或重试。
- 提案阶段继续使用现有新版 Proposal，已去除冲突的制作通用提醒；当前阶段不会自动填造 Creator 身份、规格或内部流程说明。
- **待真实验证：** Build 失败后的 checkpoint 恢复只有确定性软件回归，尚无真实失败 Build 试验；安全 AI 视觉预审没有已配置的分析器，异常视觉匹配目前由 Creator 按 Need 核对。上述能力不能以自动 PASS 或再次 Provider 请求代替。

## 本次 Creator 真实 E2E（2026-09-30，PARTIAL）

用户已明确启动一次普通 UI E2E，范围见 [具名验收记录](acceptance/creator-workspace-e2e-2026-09-30.md)。同一 Creation 完成 Proposal/冻结内容/规划/逐 Need 素材核对，Gate READY 后自动进入 Authoring。过程中暴露并修复了 Planning schema/检索合同、无 Profile 图库隔离、轮询重置确认、阶段误标、制作聊天泄漏和隔离 Authoring 契约缺漏。正式安装版 vocabulary 已接入隔离助手的只读合同输入，从同一失败阶段恢复后完成一个零第三方计费 Build、自动技术检查、一般时间点反馈、最终确认及内容库入库。成片为 12 秒、1080×1920、彻底静音；刷新/返回与选中输出 SHA 绑定验证通过。FUNCTIONAL/CORRECT/RECOVERABLE/CONTENT_LIBRARY=PASS，CREATOR_E2E=PARTIAL、CREATOR_VISIBLE/AUTONOMOUS=FAIL：本次曾泄漏内部制作回复，并依赖产品代码修复及服务重启，不能将修复后的结果当作完全自主验收。未手改真实产物/数据库/状态，未绕过审核或费用门禁。

## 本次 Creator 自主性与音画质量 E2E（2026-09-30，已入库；自主性 FAIL）

用户另行授权一个 36 秒、5 场景、真实旁白与 BGM 的 Creation，详见 [具名验收记录](acceptance/creator-audio-quality-e2e-2026-09-30.md)。一次 TTS 保留（31.932 秒），Creator 已确认旁白与 At Rest 配乐听感；实际 TTS 账单未核实。Material READY 后首次本地 Build 导出 36 秒、1080×1920、有音轨成片，技术 QC pass，CC BY credit 到达导出记录；第四场景开头近黑，未批准入库。局部修订先遇模型网关 502/400，再因错误帧率的截取越界使 Build 确定失败。安全诊断、合同索引、声音/字幕不变校验、基于准入原片/Normalize Clock 的截取范围检查已接入；失败 Build 恢复保留内容/素材，不合格编排停在 AUTHORING_REPAIR_REQUIRED，全检查通过才 READY，费用与审片仍重过。原生 Run 的隔离校验副本同时复制绑定身份记录，错配/缺失仍拒绝。83 项定向回归、lint/build/compileall/diff check 通过；实际普通恢复在提交前拦住越界，正常修复后完成 Build `bld_20260930T103231067Z_BF556E2071`。同一 Creation 三个阶段/修订 Attempt；最终修订版 36 秒、1080×1920、有音轨，SHA `2beb5b487123ee5fe2541190eaf3d995b91f6b212ad3731981485f066feb862f`。Creator 完整审阅后明确“成片可用，确认并保存内容库”，普通确认已绑定当前输出与 SHA；内容库文件字节核对一致，CC BY credit 保留，未发布。FUNCTIONAL/CORRECT/RECOVERABLE/CONTENT_LIBRARY 及基本内容/音画/节奏质量 PASS；风格一致性 PARTIAL（偏暗、字幕对比不足、未呈现前景虚化）。AUTONOMOUS/CREATOR_VISIBLE=FAIL，按本轮无工程救场标准 CREATOR_E2E=FAIL。用户已要求暂停；只补齐收尾记录，不启动另一轮 E2E。

当前旁白具有受保护的试听入口。Creator 已确认五句完整清晰、语速合适，并明确允许本次直接使用；通过普通素材复核保存使用声明及绑定当前脚本/音频的试听结论，Rights 为 KNOWN（限定本次作品），不代表第三方合同保证或公开发布批准。该旁白已不再阻断 Gate，生成记录仍只有一次。

[素材缺口恢复任务](tasks/creator-material-recovery-2026-09-30.md) 软件与同一 Creation 的阶段恢复已完成：来源修订只扩展明确选择的 BGM 来源，保留脚本/场景/旁白 Need 与冻结 Handoff；正式旧/新 Plan revision、父 SupplyRun、Bundle checkpoint 和请求身份记录，补充缺失素材。中断后对账完成的 Supply，重复请求复用结果。早期恢复保留原 7 个 Asset，集合增至 38 个；后续仅补缺失窗景，再经逐 Need 核对与独立配乐 Rights/署名复核，Material Gate READY，进入上述真实制作与最终入库。配乐试听、缺失署名事实和旁白试听结论都在普通作品区处理，未知许可不被 UI 合并放行。前一组合 127 passed；最终增量 Material/Compiler/Rights/敏感接口 52 passed（28 deselected），lint/build、compileall、技能合同和 diff check 通过。最终成片基本质量已由 Creator 审阅接受，但自主 E2E 因工程介入失败；完整运行与限制见同一份 [Acceptance](acceptance/creator-audio-quality-e2e-2026-09-30.md)。

## 当前 Goal：自主首版与 Director 全链执行

原始产品目标对齐、流程重审与 Director 实际执行链只读核对已完成。已确认两组根因：缺少持续自主交付首版的责任与执行闭环；Mode 在 Planning 中有体现，但 Material 风格参数未接全、Voice 朗读要求未进入实际请求、Production 未完整落实文稿、Quality 仍依赖人审。用户已批准将合并方案写入文档并设 Goal 实施，[同一任务](tasks/creator-autonomous-first-cut-2026-09-30.md) 已替换为唯一实施方案。

当前：Goal 保持 active，①委托与持续交付、②Director 决策传递 **PARTIAL**。已接通视觉素材的风格默认值与检索/排序、Truth 系统审阅及一次有界脚本修正；声音、实际素材观察、原生编排质量落实和③～⑥的完整闭环尚未完成，不能据此宣称“自主交付可看首版”或风格一致已实现。

- 新的结构化确认把方案原文、摘要与授权来源原子保存到同一 Creation；后端生命周期扫描仅接管带新委托记录的作品。旧 Creation 不迁移、不入队，旧确认重放也不会被接管。
- 后端从现有 Preparation/Attempt 状态推导下一项操作，复用准备、编排、Runtime、Plan、Pricing、提交、对账、状态查询和导出服务。页面对新委托只读轮询，不再用 useEffect 推进上述操作；处理正式 Truth/Material 决定后由后端观察证据继续。
- 独立 OS 执行锁覆盖同一作品的一次操作；并发调用不派发第二份任务，协程取消要等实际执行结束才释放锁。已知失败最多自动重试三次，持久计数不因重建执行器消失。Build 提交不确定只对账；状态查询失败与制作失败分开，继续保留最后可信结果。
- 按本机 Hypit 0.2.7 `packages/cli/src/output.ts` 的正式核价合同，全部请求确认为 resolved/local 才记录 0 美元。新委托自动批准仅此类无 Provider 费用的 Build，并保留当前 Plan/Pricing/fingerprint 与委托来源；未知/有费用结果仍需明确批准。删去前端 1 美元占位，未承诺 Provider 消费硬上限。
- **恢复增量（2026-10-01）：** 新委托的准备、Planning 与隔离 Authoring 调用在派发前保存请求摘要及网关运行身份，使用本机 OpenClaw 的 `gateway call agent` / `agent.wait` 正式接口；提交超时、查询超时和等待执行不触发第二次派发。对账要求同一网关 Profile、同一 runId，以及带结束时间且没有 yield 的终态。Creation 调用记录只保存身份/摘要/状态，不保存原始提示或模型回复。合同来源为本机安装包 `agent-via-gateway`、`gateway-cli`、`principal` 与 `chat-abort-ops` 源码：idempotencyKey 即 runId；不存在的运行也可能返回 timeout，因此 timeout 不能解释为执行不存在。
- 原隔离 Authoring 在调用退出时无条件删除临时 Agent/工作区，会破坏网关仍在进行的写文件。新委托在待核实时保留受限 Agent 和隔离输入/产物，对账结束后继续校验与提升；外层 Authoring checkpoint 提交后才清理。原派发指令保存在受限隔离区并按摘要校验，恢复优先接回最后一个未清理的编排回合，避免因阶段提示变化重新派发。完成文件可跨执行器重建恢复，无需再请求模型。旧普通调用继续使用原有清理行为。
- 导出先保存绑定当前 Build、输出名、署名、已通过技术检查的元数据与 SHA 的凭据，再发布和登记文件；Attempt 级导出锁串行化 API/后台请求。发布前、发布后、登记时中断都复用同一已验证字节，不再次执行 Hypit get；不同输出或文件 SHA 改变拒绝认领，最终人工审片保持 pending。
- **未闭环：** 老的未记录网关身份的调用、网关重启后查不到终态，以及“身份已保存但尚未提交”窗口仍保守停留在待核实，不凭猜测重发；这不等于所有外部故障已自动恢复。失败 Build 的有界自动恢复已接入下述现有服务；真实失败恢复效果仍待后续验收。导出后只到 `awaiting_quality`，未假装机器质量检查完成。委托内付费素材执行、Director 其余执行要求、Material/Voice、Production、Quality 与跨内容回放仍按②～⑥推进。
- **局部验证：** `test_creation_preparation`、`test_hypit_integration`、`test_chat_capability`、`test_openclaw_authoring_boundary`、`test_material_integration`、`test_runtime_config` 共 168 passed；覆盖浏览器请求结束后由后端恢复、跨进程锁/并发/取消、逐检查点重建执行器、不确定提交先对账、查询断连、重试上限、旧作品排除、零费用核价和批准失效后禁止 Build。状态投影检查及隔离 Chromium 桌面/窄屏检查通过，新增后台核价/导出/查询断连场景中页面没有生产写请求。lint/build、compileall、115 项技能合同与 diff check 通过，保留既有 Hook/体积提示。
- **有界 Build 恢复（2026-10-01）：** 后端复用 `retry_failed_film_build`，仍核对 Hypit 的确定失败、原提交 fingerprint、Planning/Truth/Material checkpoint；派发前保存来源 Attempt，目标复制中断后接续同一幂等副本，不把半成品交给普通 Preparation。每个委托最多自动恢复两次；已知复制失败沿用三次重试上限。新 Attempt 重过 Plan/Pricing，旧批准不继承；只有正式核价确认零 Provider 费用才可使用已有委托授权。UI 在后台恢复期间不再误报需要 Creator 重试，耗尽后保留明确阶段恢复入口。
- **Director 执行接线（2026-10-01）：** `clear_memo_video` 升至 1.1，增加一个对应现有软偏好语义的 `visual_material_style`，不设固定题材/故事/场景数。Planning 从当前 Attempt 的已验证 Handoff 读取并绑定到视觉 Need 的 `preferred_style`，具体镜头显式偏好优先；声音 Need 不套视觉规则，旧冻结快照不回填。素材供应改为使用 Planning 已登记的正式 Plan，修复继续消费绑定前模型草稿的问题（该问题也影响 Voice 脚本身份绑定）。同一偏好进入已有 Compiler 首条实际 Provider 查询和 Library AdvancedMatcher，四条检索提示不会再挤掉风格词；匹配仍依赖实际观察，风格偏好本身不提供语义或 Rights 证据。这尚未实现自动视觉观察、Voice/剪辑风格或成片质量检查。
- **Truth 系统审阅（2026-10-01）：** 新委托的 Planning 不再把全部非逐字表达默认交给 Creator。现有网关执行系统审阅，逐项区分有冻结来源的事实改写、非事实创作表达、系统自行引入且应修正的表述，以及委托真正必需的信息缺口。报告绑定当前 SCRIPT/Truth SHA，覆盖所有待判断句；事实改写必须引用可用冻结原文，缺失/不匹配/不可公开来源不能通过合同校验。外部 URL 本身与 model_inference 不作为证据正文。
- 系统审阅记为 `SYSTEM_REVIEWED`，与 `TRUTH_SUPPORTED`、`DELEGATE_REVIEWED`、`HUMAN_REVIEWED` 分开；现有账本、正式 Truth 状态及 Material Gate 消费该证据。机器语义判断不是确定性事实证明，也不代表 Creator 接受。引用合同验证只证明来源/身份/覆盖，语义是否正确仍取决于真实模型审阅，当前只有固定响应的局部回放，尚未验证真实判断质量。
- 系统新增的无依据表达先回到同一 Planning 修正，最多一个自动修正轮次；修正输入身份在派发前持久化，调用方中断后复用已写结果，不重新消耗一轮。再次失败记为准备失败，不显示为等待 Creator 给虚构事实背书；显式阶段 Retry 才打开新轮次。真正必需且无依据的表述保留具体缺口说明。UI 显示该说明，高级记录分开统计系统审阅，并保留判定原因/引用。顺带修复人工审核时间错误地取第一条自动分类记录的问题。
- **本批 Truth 验证：** `test_script_truth`、Preparation、Hypit、隔离 Authoring、完整 Material integration 共 **158 passed**；覆盖有依据改写、非事实表达、必需信息缺口、私密/错配/缺失来源拒绝、漏项/过期拒绝、修正后无需人工 Truth 确认进入素材阶段、修正中断恢复、有界失败及显式 Retry。Material Fixture 也隔离本机配置和外部 Provider，回放无网络或真实凭证依赖。状态投影、frontend lint/build、compileall、115 项技能合同、diff check 通过；保留既有依赖/Hook/体积提示，未跑全量测试或真实 E2E。
- **前一风格/恢复批次验证：** Preparation、Hypit、Compiler、基础/高级 Matching、隔离 Authoring，以及定向 Material 冻结风格与失败 Build 恢复共 **133 passed**。验证包含不同来源不可认领、旧/新 Mode 快照隔离、具体镜头偏好保留、正式检索/Library 输入、有界恢复、复制中断继续、重新核价与授权外阻断。Creator 状态投影、lint/build、compileall、115 项技能合同与 diff check 通过；只有既有 Hook/体积和测试依赖提示。未跑全量测试或真人 E2E。
- **2026-10-01 前一恢复批次验证：** Preparation、隔离 Authoring、Hypit 共 **103 passed**，包含一次派发后的超时/对账/身份错配、执行期间保留隔离工作区、完成后复用产物及三个导出中断点与哈希变更拒绝。frontend lint/build、compileall、115 项技能合同与 diff check 通过；只有既有 Hook/体积提示和两项测试依赖弃用提示。本次没有重跑页面 E2E 或全量测试。最初一轮 Preparation 测试暴露了继承本机配置后尝试外部检索的隔离缺口，已中止；Fixture 现固定临时配置、素材库和仅本地 Provider Registry，最终回归不依赖网络或真实凭证。
- 本轮没有修改或继续真实 Creation，没有调用付费 AI、真实 Build 或完整 E2E，没有重启生产服务。最终执行回放使用隔离数据和假执行器；未核实真实交付质量。`READY_FOR_HUMAN_E2E=NO`，旧具名运行及其失败结论保持不变。

## Official Product Path

```text
Web ai-film
→ proposal / explicit confirmation + hash-bound Production Brief
→ frozen Content + Creator Context + Creative Mode
→ OpenClaw Planning / MaterialPlan
→ Library-first / eligible supply / Material Gate
→ Rights facts + asset-level evidence / Material Gate（未知与冲突仍阻断）
→ Gate READY 后串行 Authoring / Hypit check
→ Runtime / Plan / Pricing / approval / Build
→ Export / one-pass final review + Selected Output（不发布）
```

Required Needs without current inspected, rights-admitted assets stop at `MATERIAL_NOT_READY`. A Local path or empty Local root does not bypass Planning or the Gate. Production owns final selection; Hypit owns production execution. Legacy `auto-short-video`, `video-production`, and shared media scripts are not the official Web mainline.

## Capability Status

| Capability | Status and evidence boundary |
|---|---|
| Creation / lifecycle | Software path is implemented; Creation read-time lifecycle projection, Attempt transitions and selection gates have deterministic regression coverage. A stale Preparation `MATERIAL_NOT_READY` no longer overrides a later selected, reviewed output in the read-time projection. |
| Planning / Truth | Planning freezes proposal, Content, Creator Context and Creative Mode. The explicitly confirmed chat transcript is now SHA-bound into a validated Production Brief and Planning context. The hash-bound claim ledger auto-classifies deterministic scene directions. New commissions execute source-bound semantic assessment and one bounded Planning rewrite before escalating genuine information gaps; `SYSTEM_REVIEWED` is distinct from verbatim source support, `DELEGATE_REVIEWED` and `HUMAN_REVIEWED`. Software contracts are verified; live semantic-review quality is not yet verified. Same-origin loopback review has no manually entered Operator Token. |
| Material sources | Library-first, Local, eligible external routing, Rights/inspection, matching, Bundle and Readiness are software connected. Pexels/Pixabay acquisitions carry mapped official license terms, material-page evidence and listed restrictions; where asset-specific third-party evidence is unknown, corresponding gates still block or request focused review. Generic SHA-bound review remains for unusual/generated/unknown Rights. One Local visual route and one Pexels external-acquisition route through MaterialReadiness are real-world verified. Positive Library reuse remains unverified. |
| AI Material Generation | **IMAGE / VIDEO / PRESET-VOICE TTS SOFTWARE CONNECTED; ALL THREE HAVE LIMITED ISOLATED LIVE EVIDENCE.** MiniMax adapters require per-request operator confirmation and enter ordinary Material intake/Gate. Completed generation is restored only for the current Attempt/Plan revision. The Operator UI now accepts hash-bound, operator-submitted Rights facts for current generated assets and recomputes the same Gate; it does not infer licenses. Unknown Rights blocks admission. Full Creation/Production use remains unverified. See [AI Material Workstream](workstreams/generated-material.md), [T09A](tasks/v1c-t09-minimax-video.md), and [Image/Voice smoke evidence](acceptance/minimax-image-speech-smoke-2026-09-28.md). |
| Continuity | Provider-neutral references and lineage are software connected; cross-Content adherence is unverified. |
| Rights / attribution | Hash-bound local Rights evidence gates required Needs. Pexels/Pixabay ordinary published licenses no longer default to UNKNOWN after valid acquisition; explicit commercial trademark conditions and other unverified identity restrictions are not auto-cleared. Attribution facts have a software propagation path; attribution-bearing real export is unverified. |
| Production / Hypit | Selection qualification, current revisions, bytes and SVML/SVRun references are software gated. Non-paid Authoring starts automatically once the confirmed Production Brief and Material Gate are ready. The Creator-facing production card now shows Chinese progress and one primary action; Runtime/check/plan/pricing/export use their existing formal APIs in the background, while engineering controls stay collapsed. The named External Material Creation completed one real Hypit Build; broader V1 lifecycle evidence remains separate. |
| Audio | BGM and accepted audio material can be authored into Hypit tracks in software. Material Layer connects preset-voice TTS using the frozen, truth-reviewed Script; one isolated real TTS output passed technical intake. It is not voice cloning. Final audio stream/listening, mix quality and real attribution-bearing output remain unverified. SFX is not a V1 Release gate. |
| Export / Review | Named Local visual and Pexels External Material runs completed export, review and Selected Output. Broader modality and release evidence remains pending. |
| Content Asset / Material Promotion | Formal approved Selected Output is copied into a Creator-visible Content Library project and linked back to Creation / Attempt / Build / output / SHA; four existing approved selections were reconciled idempotently. Attempt Material promotion is explicit and scope-bound; UNKNOWN / RESTRICTED Rights fail closed, while Rights, acquisition provenance, generation lineage and source Creation / Attempt are retained. Deterministic promotion → later Library reuse is verified; the current real Pexels Attempt asset is eligible but remains unpromoted until a Creator/Operator chooses it. See [acceptance](acceptance/content-asset-material-promotion-2026-09-29.md). |

## Named Evidence

- Local visual Web run: Creation `cr_0283a7adf4094e80bc0c59b58a68dc99`, Build `bld_20260924T135801492Z_4696AF96FC`; its Acceptance records the 15-second final video and human-approved Selected Output.
- External Material Web run: Creation `cr_fc46c0fd949a4beca0043be745b9458d`, Attempt `fa_c1e6b95191ce6b69be351d8a39cb1e81`; Pexels MaterialReadiness `READY`, Hypit Build `bld_20260928T162455494Z_A032509CF4`, 10-second 540×960 MP4, SHA-256 `59ad3d0d7ab60673ce7cc728283add9b0de892d2d5996ca4d4d1a7e4f0eb44b3`, Review approved and `final.video` selected. The stale Preparation snapshot remains as history; read-time Creation status now projects `ready` from the selected Attempt.
- Pexels, Pixabay, Coverr, Unsplash and Openverse have dated minimal search/normalization evidence. Discovery does not mean acquisition or Rights admission; Coverr, Unsplash and Openverse remain `DISCOVERY_ONLY`.
- Hypit v0.2.7 remains the locally invoked editing/rendering engine. The old `hypihub.default` endpoint and Hypit Image/Video/Voice generation bindings remain removed. MiniMax Image/Video/T2A are separate remote Material providers; API-key presence does not establish authentication or generated output.
- Latest six-profile readiness and dependency facts: [`configuration/v1-runtime-and-external-dependencies.md`](configuration/v1-runtime-and-external-dependencies.md).

## Closure Queue

- **T01–T08, T17, T18:** original scoped software evidence remains historical; Hypit generation portions of T06/T08 no longer define the official product route. Authenticated full-path re-verification remains pending.
- **T09 / AI Material Generation:** previous Hypit execution task is superseded. MiniMax Image, Video and preset-voice TTS implementation and isolated modality smoke evidence are tracked in [`v1c-t09-minimax-video.md`](tasks/v1c-t09-minimax-video.md); real Creation/Production use and Rights evidence remain separate open work.
- **Generated Material baseline:** current scope and gates are recorded in [`workstreams/generated-material.md`](workstreams/generated-material.md). Any billable generation requires per-request operator confirmation.
- **T10 external-acquisition branch:** one named Pexels Creation reached MaterialReadiness `READY` and later completed Production/Export/Review/Selection. **T11–T14 NOT_STARTED:** positive Library-reuse, attribution-bearing-output, Supplemental Supply and Continuity remain separate branches; do not batch these into T15.
- **T15 E2E PAUSED FOR REPAIR:** Creator reported the current Creation at `AUTHORING_FAILED`; no Build has been submitted for it. The current Goal repairs Hypit Authoring, Material Match, Progress, Review and Proposal software without resuming that Creation or running another full E2E. Earlier named Local/Pexels runs remain historical evidence for their exact outputs, not evidence that the revised semantic Match gate has been exercised live. Creator will continue the real E2E manually. See [repair task](tasks/creator-e2e-repair-2026-09-30.md), [T15](tasks/v1c-t15-e2e-readiness.md) and [T19](tasks/v1c-t19-low-friction-creation.md).
- **T16 NOT_STARTED:** multi-Content consistency validation remains separate from T15 and requires an explicit subsequent scope.
- These statuses describe Closure evidence work, not permission to start all tasks automatically. The next work is [T19](tasks/v1c-t19-low-friction-creation.md), then resume [T15](tasks/v1c-t15-e2e-readiness.md), as ordered in the [Roadmap](03_ROADMAP.md).

## Status Rules

- `SOFTWARE_ACCEPTED`: scoped code and deterministic acceptance passed; no live Product proof implied.
- `REAL_WORLD_VERIFIED`: only the named run, artifact, modality and scope were exercised.
- `NOT_VERIFIED`: evidence is missing; do not infer failure or readiness.
- `BLOCKED`: a concrete external/user prerequisite prevents the scoped run.
- Current status belongs here. Workstream/Task/Acceptance docs provide scope and evidence; older audits are historical snapshots.
- The latest test-suite count and duration are a dated measurement, not a target; see [`AGENTS.md`](../AGENTS.md) for risk-based test growth rules.
- The 2026-09-28 portfolio consolidation removed 12 low-value/redundant collected cases, combined BGM/SFX coverage under their shared audio-supply boundary, and collapsed common Markdown renderer smoke cases into one representative contract. It retained the distinct modality, Rights, lifecycle, security, and execution-gate risks. Test-file count changed from 57 to 56; most remaining cases protect distinct behavior.
