# Easel Current State

## 2026-10-10 CUT5 用户验收：完成，不再要求独立 Reviewer

用户于 2026-10-10 明确表示“**不需要审计了，算是完成了**”。这是对独立模型 Reviewer 门禁的**明确豁免**，不是声称 Astra 或其他审查者执行了评审；既有 Reviewer TODO `wc_msg_6OXw8ajbrXGmLYlD` 已记录以用户豁免为理由关闭，未获得独立审查意见。

CUT5 软件验收依据保持：正常 `easel-studio` 工作区，20 套当前新旧联合测试 `wc_job_qM8Yz2eOpg4F7phv` **450 PASS / 0 FAIL**、旧 Hypit 保留套件 **24 PASS / 0 FAIL**、20 个旧实现函数与25条参数化失败项逐一对应 Native 保护且原 Git Blob 保留；前端 lint/build、115项Skills、Python compileall、Git diff --check 均PASS。真实外部模型/Provider/Hypit Build/E2E未执行，也没有因此宣称实际成功出片。CUT5 应标记为 **COMPLETED（独立 Reviewer：user-waived，非 review-passed）**。

剩余 **CUT6**：按已冻结的 CUT5 代码/文档集合，核对用户主仓库中未提交的并行 Planning、历史测试证据及未跟踪文件的 Git 边界；只提交当前 Goal 所有权明确的文件，校验源 SHA、提交结果与 `origin/easel-studio`，然后按原计划非强推。**截至本次记录，CUT6 尚未开始，未 commit/push。** 不能把用户豁免解释为强推、自动覆盖其他分支或删除历史记录的授权。



## 2026-10-10 CUT5 Revision 19 续接：旧 Hypit 回归正式收口，独立 Reviewer 待验

**当前开发位置：** `/Users/xgx/Projects/Easel`，`easel-studio`；本地 HEAD 与 `origin/easel-studio` 仍 `bb01aede`，未 commit/push。Goal `wc_goal_yYpFxgMopd9MlccK` Revision 19 的 CUT0–CUT4 已完成、CUT5 仍在验收，CUT6 不启动。未调用真实 AI/Provider/Hypit Build 或清理历史 Attempt、FAIL/UNKNOWN、预算/素材原件。

**旧 Hypit 用例的正式代码收口已经完成。** `tests/test_hypit_integration.py` 原 Git Blob SHA-256 `8d0daae461ec11265a3c6600487a3e555acdc16344069ff52e3ea432bc05ae58`（`bb01aede:tests/test_hypit_integration.py`），旧版 49 collected：24 PASS / 25 FAIL。20 个失败旧函数（合计 25 个参数化用例）全部逐个映射到已执行的 Native/Domain 等价风险测试，且仅精确退役了这些已经不应执行的字符串 SVRun、旧 Writer、partial-pin/旧 Quality profile 假设；**不是整文件删除、批量 skip 或 xfail**。剩余 24 个仍有效的旧 Handoff/Browser 鉴权/CLI 凭证、Narration/BGM、Material Attribution、Quality Guard、冷恢复检查原样保留，当前 `pytest -q tests/test_hypit_integration.py` **24 PASS / 0 FAIL**。完整的原函数、后继用例与责任边界映射存档在 [Acceptance: ADR005 Hypit 历史用例退役](acceptance/adr005-hypit-native-legacy-test-retirement-2026-10-10.md)，Git 原件可恢复。独立只读 AST 映射交叉检查：原 SHA 一致、精确 20 个退役函数全部列在清单、无缺失/多余条目、所有后继测试函数确实存在，**MAPPING_AUDIT_PASS=True**。

**本次同一主仓库的新旧合并回归：** `wc_job_qM8Yz2eOpg4F7phv`，20 个当前测试文件一起执行，**450 PASS / 0 FAIL / 492.85秒**（2 个依赖库弃用 warning）。新增并通过本地四种异常定价数据（假总价等）及真实 Hypit CLI 子进程 stderr 脱敏的 **5 PASS**（`wc_job_YmoDuyHez1Ku784Y`）、真实 FFmpeg 黑帧与旁白识别 **1 PASS**、人工 Review 撤销后已选片状态/原始输出保留 **1 PASS**（`wc_job_RPkmIED43HFjjS46`），均已由这次20套统一回归复核。此前 Revision19 的自动零费用委托确认锁内CAS、Build撤销授权及两代Attempt cleanup 恢复也包含在当次统一回归中。

**独立复核必须明确区分于软件 PASS。** WebCodex 当前 Mac Runner 的 `coding_agent_providers=[]`，原生 Plugin/MCP Provider 均为空，本机无可调用的 Ollama/本地 Reviewer 或独立静态扫描引擎，**本次没有实际执行 Astra/另一独立模型 Reviewer**。已将高优先级待审任务 `wc_msg_6OXw8ajbrXGmLYlD` 留在原 WebCodex Session（`wc_sess_1XU2MaYBfR1GL9Z9`），审查范围为 Creation 委托→费用批准→同一 Creation 锁内 Build `SUBMITTING` 意图的 CAS/撤销、授权种类篡改/竞态、旧测试逐项退休映射、Material/Rights/回执原件证据。没有 ACK、没有独立 Reviewer 决策，故不能声称此门禁完成，`CUT5=IN_PROGRESS / INDEPENDENT_REVIEW_PENDING`、`CUT6=PENDING`。固定原件与测试已具备可给独立 Reviewer 的最小充分证据；只读人工/静态自检不冒充独立审查。



## 2026-10-10 CUT5 Revision 18 续接：自动零费用委托与多 Attempt 清理最终审计

**审计决策：CUT5 = IN_PROGRESS / NOT_READY_FOR_CUT6。** 两项优先阻塞已按真实新版 Native 软件边界完成并取得通过证据，但旧 Hypit 测试红项尚未完成正式迁移/退役，也未做独立 Reviewer 冻结复核；不把软件核心通过等同于全仓库测试或真实付费视频 E2E 通过。

### 高风险修复、Owner 与数据边界

1. **真实缺陷与修复：自动零费用委托批准后撤销未阻止外部 Build**。修改前 `tests/test_native_build_admission_recovery.py` 的正常委托 **1 PASS**，撤销确认、停止委托、撤销零费用授权、改写确认文本、修改确认时间 **5 FAIL**：原 `submit_film_build` 只核费用快照，没有重新读取冻结确认。修复于 `easel/integrations/hypit/service.py`：`_confirmed_commission_authorization` 验证 Creation `chat_workflow` 与 `delivery` 一致的完整 Proposal SHA、Confirmed 状态/时间、未停止状态、零费用授权；`_save_attempt(..., include_creation=True)` 允许在**同一个 Creation 文件锁**内同时消费 Attempt 和当前委托身份。批准操作在锁内再次比对 preflight 的 grant；Build 在写 `SUBMITTING` 意图前将当前 grant 与 `cost.commission_authorization` 固定身份比对，并重新确认真正的 `pricing_has_no_provider_charge`。不一致则记录 `commission_authorization_revoked_before_build`、将费用批准作废并阻止外部 CLI。显式运营者批准仍遵守原独立流程，旧协议版本拒绝仍优先。修复后委托正常 + 五种撤销 **6 PASS / 0 FAIL / 34.42秒**（`wc_job_MekSAkx0xSOZgB5f`）。另新增“预检查后、锁内批准前撤销”CAS 竞态负例 **1 PASS / 4.54秒**，并包含在下列完整新版安全套件中。测试只模拟 CLI 边界，**没有真实收费 Build**。
2. **多 Attempt 清理：** 使用真实 Creation/Native Authoring/Export/Review/Content Library 创建两个不同 Attempt，一项设为历史 `BUILD_FAILED`。Content Library 归档失败时不允许清理；媒体树出现 symlink 与另一个 Attempt 的 I/O 删除异常时，两条清理状态 `PENDING` 并保留原件；修复故障后再次选片使状态转 `COMPLETE`，只释放已归档的 Attempt-owned 临时媒体，保留各 Attempt JSON 证据、元数据、失败状态、导出原件和外部文件，且重复选片不重复累计删除、不重复注册内容资产、不自动发布。**1 PASS / 6.47秒**（`wc_job_V53cEHxUY57hPhjw`）。全部是临时测试目录，未接触用户历史真实 Creation/Attempt。
3. **同版全链验证：** 19 个正式新版测试文件的单次 `pytest -q` **421 PASS / 0 FAIL / 470.28秒**（`wc_job_uBXBK-oXXmC5Mxf7`，2 个 Starlette/AnyIO 依赖弃用警告）；包含首次委托缺陷修复及多 Attempt 恢复。单独 `tests/test_native_build_admission_recovery.py` 在新增 CAS 测试后完整重跑 **28 PASS / 0 FAIL / 154.20秒**（`wc_job_kNEME5-cTr35CPpp`），前者未包含后追加的 CAS 用例，不累加为同次 422 PASS。
4. **构建/契约/静态：** `web/frontend` Lint 和 Vite Build 成功（lint 0 error、原有 React Hook `openCred` 依赖提示 1 条；构建有 chunk 大于 500KB 提示）。`scripts/validate_skills.py` **115 Skills/Publisher 合同 PASS**，Python `compileall`、`git diff --check` PASS，生产 `easel/`、`web/` Python 无旧 `hypit_run_promotion`、Script Ledger @2、Compact @4、旧 Markup Writer 引用。正式主仓库 `/Users/xgx/Projects/Easel` 仍是 `easel-studio`，本地 HEAD 与 `origin/easel-studio` 都为 `bb01aede668462dce706eeecd8a7737033c25854`，工作树未提交；**37 个修改或新增 Python 文件**内容集合 SHA-256=`23a5e9d6227e0bbdd421f6586762c676f2cd31c3ed6f5f21e02b1d9f4b845fc7`。本轮经测核心 `service.py` SHA-256=`8990d598437a80f720d0840eddb9c113cb1a7100732bfbd6b8309aebb96a95a0`。该摘要仅是当前未提交工作树冻结标记，不冒充 Git commit SHA。

### 旧 Hypit 历史套件 25 个失败的风险映射

`tests/test_hypit_integration.py` 在当前主仓库重新执行仍 **24 PASS / 25 FAIL**；失败主要由已删除的字符串 SVRun、过渡 Writer、旧/部分协议 pin 导致，并非全部新功能失败。**不 skip/xfail、不删除整组旧测试**，按如下风险建立可审查的映射：

| 旧红项领域（数量） | 新版 Native/Domain 对应风险与覆盖 | 结论 |
|---|---|---|
| Clock/Caption 文字与 Timeline 规范化（2） | `test_hypit_native_source`、`test_hypit_native_semantics` 的 typed AST/引用与文本原件验证 | 核心替代通过，旧字符串格式断言待退役 |
| 旧 Authoring Writer/静态 Check（1） | `test_native_authoring_publication`、Owner Recovery、实际安装 Grammar/Check | 新 Owner 通过，旧 Writer 不再恢复 |
| 两种完整 Lifecycle/跨 output Review（3） | 新版 Export→Review→Select→Content Library/署名/Rights 与两 Attempt 恢复测试 | 主要准入/输出身份通过，旧状态投影附带断言待逐条确认 |
| 音频必需的导出门禁（1） | 真实 FFmpeg 生成可解码、无音轨 MP4 的 Export 拒绝；真实 Native Quality MP4 | 通过 |
| 价格为 UNKNOWN/异常 Quote 的四种输入（4） | 当前 Native pricing UNKNOWN/零预算拒绝、Pricing SHA/Plan SHA、伪报价不构成强预算上限 | 主要合同通过；旧特定 `total` 字段四种输入还需单例对账 |
| 自动零费用确认（1） | 上述真实 `confirm_chat_proposal`、冻结 SHA 与批准前/Build 前再校验、撤销与 CAS 负例 | 真实问题已修复并通过 |
| 定价/Plan 漂移（2） | Native pricing、Plan 签名变化撤销批准 | 通过 |
| 失败 Export、UNKNOWN Submit、并发、指纹、提交后重 Validate、Operation 对账、非零失败 JSON（7） | Native 导出三处崩溃冷恢复、唯一 Intent/CAS、失败状态、对账、禁重提/禁重验 | 通过 |
| Handoff 哈希篡改与 CLI Secret stderr（2） | Native Handoff SHA 提前拒绝、服务 `last_error` Secret 脱敏负例 | 主要保护通过；旧完整 CLI stderr 形态仍需细化对应 |
| 旧/Delta 完整系统审片的音轨与黑帧（2） | Native Quality Owner 对实际 MP4/Delta 回执/缓存，以及 Voice/BGM 声学缺陷指标 | 主干通过，旧“黑帧 + 旁白”同场景组合需审计保留价值 |

**剩余正式门禁**：对上述“待退役/部分覆盖”的旧断言提供逐项证据并保留有独立风险的场景；完成独立 Reviewer 对此次跨模块“Creation 委托→Build 持久意图”授权边界和大量旧协议删除 Diff 的冻结复核；决定项目整体历史兼容测试清理策略。此前没有全仓库 `pytest` 无红项证据，旧套件真实红项保留。CUT5 不能因 421 PASS 提前冒充 Completed；CUT6 的精确 Git commit/非强推继续 Pending。历史 Attempt、真实媒体、FAIL/UNKNOWN、预算记录和主仓库其他并行修改/未跟踪验收数据均未清理。



## 2026-10-10 CUT5 正常主仓库持续验收（未提交、未发布）

用户已明确授权以当前 CUT5 代码覆盖正常开发仓库。**当前开发/执行位置固定为 `/Users/xgx/Projects/Easel` 的 `easel-studio`**，非 `main`；CUT5 原隔离工作树仅作历史来源。覆盖前主仓库的二进制 Git patch、全部被覆盖文件原件与清单已保存在 `/tmp/easel-main-before-cut5-overlay-j0ogqu8o`，原主仓库未涉及的 Planning 并行改动和历史 Run/FAIL/UNKNOWN/费用证据不清理。当前本地 HEAD 与 `origin/easel-studio` 均为 `bb01aede`，没有提交、合并或推送。

**核心主链与风险回归（当前主仓库实际执行）：**
- 完整当前协议集合 19 个测试文件：`wc_job_XWJmqoKKos3Zo7AV` **413 PASS / 0 FAIL / 455.02 秒**，仅 2 条依赖库弃用警告。覆盖 Creation/Preparation、Truth Source-Ref/Markdown、Material/Need/Rights/Readiness、Native Authoring/Check/Intent/冷恢复、两代 Fork、Quality Delta/本地 MP4、现版 Build 价格和授权、安全提交、Export 回执、Review 与选片。此单次执行开始时尚未增加下一条独立音频指标测试，不把额外测试算入413项。
- 新版 Export/Review 兼容替代：`wc_job_-sRHDcg7zLq6FfZh` **9 PASS / 49.79秒**，验证非法导出清理、在 link 前/后/receipt registration 三处模拟崩溃、字节/Hash 冷恢复、不重复调用外部get、不同输出 SHA 审片隔离、Content Library 来源及禁止自动发布。
- 新增费用/运行边界：UNKNOWN 总价不能当作零费用、价格/Plan/Runtime 指纹变化不能沿用批准、并发只提交一次、未知 Build 意图不二次提交、失败状态结构化持久化、错误凭证脱敏、冻结 Handoff Truth 篡改时 Native Domain 提前拒绝。真实 Rights 为 `internal_production_only` 且要求署名的 Asset，经 Gate→Native Authoring→Export→Review→Selection 后仍被标记 `RIGHTS_REVIEW_REQUIRED`，Content Library 不允许公开发布；本地 FFmpeg 生成的真实无音轨 MP4 在音频必需策略下被 Export 拒绝并清理临时文件，分别有独立 PASS。
- `tests/test_native_quality_owner.py` 最新单独 **2 PASS / 6.46秒**：已发布 Native 来源对应本地真实编码 MP4 + Quality Delta 原回执的复用，以及语音截断/遮蔽/静音/削波、BGM 与 Voice 区分的测量。后者是 413 组合启动之后独立增加并执行的测试，未冒充同轮综合结果。
- 前端 `web/frontend` 已利用主仓库现有 `node_modules` 成功执行 `npm run lint && npm run build`（lint 0 error、1 条现存 `AccountsPage.tsx` useCallback 依赖 warning；构建成功但有 chunk >500kB 警告）。Python `compileall`、`git diff --check` PASS，`scripts/validate_skills.py` 为 **115 Skills/Publisher 合同 PASS**。生产 `easel/` 与 `web/` Python 无旧 `hypit_run_promotion`、Script Ledger @2、compact @4、过渡 Authoring Writer 入口文字命中。

**旧版 Hypit 测试逐类归属与当前缺口：** 主仓库的 `tests/test_hypit_integration.py` 仍为 **24 PASS / 25 FAIL**；其 25 个失败主要因老字符串 SVRun、过渡 Authoring Writer 和已拒绝的部分旧协议 pin。已由新版可执行的原生合同覆盖：Clock/AST 输入→`test_hypit_native_source.py`/原生静态 Check；Producer/Publish→`test_native_authoring_publication.py`/Owner Recovery；报价/指纹/并发/UNKNOWN→`test_native_build_admission_recovery.py`；Export 原子落盘、Review/选片 SHA/资产归属、Rights→同一原生测试；Voice/BGM 异常和真实 MP4→`test_native_quality_owner.py`；旧 Attempt 写入/执行拒绝→`test_result_protocol_defaults.py`。

**未彻底迁移的独立历史风险**：零费用**自动委托**的 `use_commission=True` 确认摘要/授权重核对（已有明确 Operator 零费用门禁，但不等价于受托自动批准）；多个 Attempt 成片选定后的残留素材清理在 symlink/归档失败条件下的持久重入；旧 Hypit 原测试的剩余断言需要逐条退役或迁移，不能直接 skip/xfail 或批量删除。旧套件仍然红，因此不宣称项目全量 `pytest` 已全绿。真实付费模型/Provider/Hypit Build/媒体生产的外部 E2E 尚不在本次离线授权内，不得凭离线结果声称出片验收。

**阶段门禁**：CUT0–CUT4 `completed`，CUT5 **`in_progress`（核心新协议软件集成门禁通过，但仍有上述风险和旧测试收口）**，CUT6 `pending`。未经 CUT5 正式全量收口，不执行 commit/push、不恢复过渡代码、不覆盖历史证据。



## 2026-10-10 CUT5 Mac 重连断点恢复：同版本 397 PASS（隔离工作树，未发布）

Mac WebCodex Runner 恢复在线；Goal `wc_goal_yYpFxgMopd9MlccK` Revision 15 的原 Session 与 detached 工作树 `/Users/xgx/Projects/Easel/.tmp/easel-newonly-bb01aede` 均保持，HEAD 与 `origin/easel-studio` 同为 `bb01aede`。未发现遗失或运行中的待接管 Job。上次断线前 `tests/test_creation_preparation.py` 已写入的五项协议 pin 修改仍在，断线命令本身未产生重测终态；本轮从此断点直接执行。

**本轮同一执行的正式软件证据**：`wc_job_himrD5vuW0jrgObE`，`pytest -q` 对 19 个具名套件（Creation/Preparation、Truth/Source-Ref、Material/Need/Rights/Readiness、Native Authoring/Check/恢复、Quality Delta/本地 MP4、Build 原生准入/成本/并发/未知提交、Fork、旧 Attempt 禁止恢复），**397 PASS / 0 FAIL，348.17 秒，2 条第三方弃用 warning**。非真实 AI、无真实 Provider、无 Hypit Build/Export 付费。单独 `tests/test_creation_preparation.py` **99 PASS / 6.53 秒**（`wc_job_zxz5j6vQeuR1estl`），新 `tests/test_native_build_admission_recovery.py` **4 PASS / 22.11 秒**（`wc_job_EvXDZwt7aNYxE0ti`），都包含于上述397项，不累计。

恢复中迁移了原 Creation 测试的新版 pin、Material facts/delta 观察与完整输入/回执、旧 Compact Cache/Run 的只读拒绝、Delivery 无重复派发和 Native 音频旧字符串修复入口。移除一个已被 `test_quality_local_repair_is_limited_to_one_retry`、`test_quality_web_owner_uses_real_result_store_and_original_proof` 及 `test_native_published_source_reaches_real_quality_delta_owner` 高价值实测覆盖的过时 Quality 完整报告草稿测试；并未放宽生产合同。额外 Build 合同证明成本总价 UNKNOWN 不得零预算批准、变更已批准 Plan/Runtime 撤销授权、并发只提交一次、未知提交通过原 marker 对账；所有真实内部状态机配 CLI 离线替身。

**静态/卫生证据**：`compileall -q easel web scripts tests` PASS、`git diff --check` PASS、`scripts/validate_skills.py` 显示 115 Skills/Publisher 合同符合；生产 `easel/` + `web/` Python 未命中旧 `hypit_run_promotion`、Script Ledger @2、Material Compact @4、旧 markup Writer 入口。测试后 29 个 dirty/新增 Python 文件聚合 SHA-256 为 `50ed72397252356a58fdb053cf2fd2aee8914b0962d1428df2d1903492861f73`。记录作为一次只读冻结快照，不是 Git commit。前端 `web/frontend/node_modules` 缺失，未下载依赖或宣称完成 `npm lint/build`。

**CUT5 仍为 IN_PROGRESS**：旧 `tests/test_hypit_integration.py` 曾记录 **24 PASS / 25 FAIL**（旧 SVRun / Producer/Writer/API 假设），必须按风险映射到 Native 保护或迁移，而非批量 skip。重点是 Output Export 失败/落盘恢复、人工 Review/选片与素材授权归属、部分价格/计划漂移及秘密脱敏等高价值合同，以及 CUT5 正式 Reviewer/综合冻结审计。上述397项不包含整个旧 Hypit 套件，也不代表真实模型、完整视频 E2E 或真实收费 Build 已验收。旧失败原件保留，后续须复查未覆盖的真实高风险断言。

**发布控制**：CUT0–CUT4 completed；CUT5 in_progress；CUT6 pending。没有 commit、merge、push；`origin/easel-studio`、主仓库并行 dirty、历史 Attempt/FAIL/UNKNOWN/成本原件未改。



## 2026-10-10 CUT5 首轮内部全链集成回归（离线，尚未发布）

依据 Goal `wc_goal_yYpFxgMopd9MlccK` 已将 CUT4 完成并启动 CUT5。首组同源码验证 `wc_job_IQIMxmL_FGLd-lme` **44 PASS / 1 FAIL，140.03 秒**；失败并非 Native Quality 绕过，而是旧 `test_delivery_quality_repair_resumes_one_checkpoint_and_stops_at_budget` 的合成状态机 Attempt 缺少新的五项不可变 `result_protocols` pin，生产在 `quality_results.verify_current_review` 处按预期拒绝。保留原失败。

仅在 `tests/test_creation_preparation.py` 迁移此**纯 Delivery 恢复/预算状态机**场景：源、目标合成 Attempt 都带完整当前五项 pin；将缺少真实 MP4/原始 Quality Receipt 的合成验证前提显式隔离，只考察恢复次数上限、幂等与未继承费用批准。**生产质量/素材准入校验未修改**；真实本地 MP4、发布指纹和增量审片原件由 `tests/test_native_quality_owner.py` 使用真实内部模块单独保护。定向用例 **1 PASS / 0.70 秒**。

同一修改后、同一组合无红项重跑 `wc_job_IP7Rh44atIOjsdSs`：**45 PASS / 0 FAIL，139.49 秒**。覆盖 Creation/Handoff 确认、Truth Source-Ref 原始回执及无网冷恢复、Retry/并发幂等、Material Fork、Native Authoring 的局部发表/Intent 重入/冷恢复与 Check、实际本地 MP4 的 Quality Delta、旧协议/伪造 Need-Run 拒绝以及 Delivery Quality Repair 状态机。所有测试仅用本地素材与外部边界替身，未发出真实 AI/Provider 调用、Hypit Build 或生产执行。

**CUT5 = IN_PROGRESS，不代表全部完成。** 仍需扩展风险矩阵和最终同版本冻结审计，必要时进行独立 Reviewer 检查；此前旧失败与当前通过分开存档。CUT6 commit/merge/push 未执行，`origin/easel-studio` 与 detached 隔离基线仍为 `bb01aede`；历史 Attempt、媒体/费用、UNKNOWN/FAIL、主仓库并行 dirty 工作均未覆盖。



## 2026-10-10 CUT4 尾部负例补齐及 CUT5 启动门槛

原 352 例 Planning 扩展运行 `wc_job_EL5MfjAXEFGzJaJx` 在第 346 例 `material_fork_report` 处 -x 停止（345 PASS/1 FAIL，另 11 deselected，未执行尾部六例）；该报告篡改负例此前已在 `wc_job_UaYIF98Dj3dSeM9B` **1 PASS**。本轮按原收集顺序仅补尾部六项，不重跑先前345项：
- `wc_job_iHZP4CL-e2elpCBA`：`material_fork_plan/record/fingerprint/creation/cycle/copy` 全部真实执行，**3 PASS / 3 FAIL，637.93 秒**，失败均为旧断言不接收新版完整性错误，并非篡改被放行。
- `wc_job_Jl5IR2hsUIgzOPGO`：仅对三个原失败项采用精确错误分类后重跑，**3 PASS / 0 FAIL，264.16 秒**。Plan 篡改的 Native Domain 拒绝仍携带 MaterialIntegrationError cause；跨 Creation 和循环 Retry 严格拒绝对应 Truth Source-Ref 的 OutputReceiptError。其余三个第一次已有 PASS，因而六个风险全部有真实通过证据。
- 仅调整 `tests/test_semantic_planning.py` 的风险对应异常断言，**没有放宽生产校验**。此前优化后的同例双 Fork **1 PASS / 199.67 秒**、核心协议 128 PASS、R4/Source-Ref 38 PASS、Material 全套 111 PASS 仍有效。Python compileall、git diff --check PASS；生产 `easel/` 与 `web/` 下未发现旧 `hypit_run_promotion`、Script Ledger @2、旧 compact @4、过渡 Authoring Writer 入口引用。
- **CUT4 开发与定向合同验收满足，转 CUT5 内部综合验收**。必须区分不同 Job/源码切片：尚未获得新优化后完整 352 例**单次**全部通过的证据，不能将分批结果当作一个 352 PASS。CUT5 需验证 Creation/Handoff→Planning/Truth→Material/Rights/Readiness→Native Authoring/Check→Quality/Review、旧 Attempt 拒绝、Retry/CAS、Intent 与跨进程冷恢复。CUT6 commit/push 仍禁止至 CUT5 完整通过；历史 FAIL/UNKNOWN、原 Attempt 和主工作区保持不变。



## 2026-10-10 CUT4 本轮最新结果：双 Fork 性能与负例审计（隔离，未提交）

上次 Planning 扩展 Job `wc_job_EL5MfjAXEFGzJaJx` 已确认 **345 PASS / 1 FAIL / 11 deselected，851.41 秒**，使用 `-x` 遇到首例失败后未继续余项。失败是 `material_fork_report` 故意篡改 Voice 原件被 Native Authoring 指纹拒绝（`AuthoringPublicationError`，属于本地完整性错误），旧测试只接收 `ValueError/MaterialIntegrationError`；定向迁移测试的拒绝分类，不放松生产行为，得到 **1 PASS / 106.77 秒**（`wc_job_UaYIF98Dj3dSeM9B`）。

实测性能剖析：一次单例内部 `Planning._load_contract` 138 次、自身耗时约 87.8 秒；其中 `SemanticBoundary.verify` 140 次、约 85.1 秒自身耗时。进一步发现 `StagedProposal` Schema 构建 565 次、50.65 秒，`wire.project` 849 次、24.87 秒。为此仅在 Voice/Fork 同一同步只读调用链内复用**完整 JSON Schema 内容和阶段**匹配的纯编译对象；ContextVar 作用域结束立即清空，其他独立操作仍从原件重新验证。不会缓存模型结果、原文、Material/Rights/Readiness 合格结论、指纹、付费授权或跨操作状态。

相同的 `test_markdown_source_ref_persist_and_two_forks_preserve_full_coverage`，优化前 **1 PASS / 301.58 秒**（`wc_job_qf_ZkUGaanMwKp38`），优化后 **1 PASS / 199.67 秒**（`wc_job_0MLMLTkqMg6TUZqq`），单次对比减少 **101.91 秒（约 34%）**；尚不能据此声明统计稳定加速。优化后新增的同版离线证据：核心新协议/负例/缓存安全 **128 PASS / 72.30 秒**（`wc_job_A_RFZDno8PMIcdGm`），Planning R4/Source-Ref **38 PASS / 83.11 秒**（`wc_job_n0EAYlEW5fgttdWt`），Material 完整 **111 PASS / 96.45 秒**（`wc_job_RtamogkNcVVm5GUN`，2 个第三方弃用警告）；集合有重叠不可累加独立功能数。

**状态仍为 CUT4 IN_PROGRESS**：352 项扩展 Planning 运行在首个负例停止，尾部未运行用例仍需补验，CUT5/CUT6 未完成。没有真实模型/Provider/媒体/Hypit Build、旧 Attempt 变更、Commit 或 Push；主仓库与历史费用/UNKNOWN/FAIL 原件保持。生产代码仍只在授权隔离 worktree `/Users/xgx/Projects/Easel/.tmp/easel-newonly-bb01aede`。

2026-10-10 CUT4 隔离续接（未提交/推送）：旧版 Markdown Source-Ref 双 Fork 长链 575 秒超时，诊断指向 Planning.load / Voice checkpoint / 执行指纹 / Native Authoring domain / MaterialGate 重复校验。原工作树中的指纹单次只读缓存与历史目录扫描裁剪已通过专项 6 PASS；该长链本轮取得 **1 PASS / 301.58 秒**（Job `wc_job_qf_ZkUGaanMwKp38`），虽解除超时阻塞，仍有性能成本。其他同版离线回归：核心新协议 **127 PASS / 73.43 秒**、Source-Ref 拒绝 **8 PASS / 34.06 秒**、Material 全套 **111 PASS / 96.55 秒**、原生 Authoring 五套 **41 PASS / 122.64 秒**、R4 Planning 边界 **30 PASS / 49.32 秒**；详见本轮 Task。完整 Planning 扩展及 CUT5 仍待最终验收。原隔离工作树已迁到 `/Users/xgx/Projects/Easel/.tmp/easel-newonly-bb01aede`，主仓库历史状态和费用原件未改。

## 2026-10-10：新版协议单线化（隔离实现中，未验证/未推送）

依据用户明确要求，源自 origin/easel-studio 的 bb01aede 建立独立工作树实施新协议唯一生产路径；原 dirty 开发工作区和历史 Attempt 原件未改动。已将新建/重试结果协议收窄为 Truth source-ref、Material delta、Markdown ledger@3、Quality delta、Hypit native source 五项；拒绝空/部分/旧协议执行；移除过渡 SVRun-only Writer、旧 Authoring、旧 Material full-frame/Quality full-report 派发。详细清单与边界参见 [新版单线化唯一新任务](tasks/adr005-new-only-cutover-2026-10-10.md)。

**证据等级**：此前的 Material 111 PASS 是改造前的 bb01aede 基线。隔离开发目前删除/调整多个旧 Writer/consumer，源代码与测试有大幅变动；生产模块导入、200 个 Python 文件 AST 语法扫描、Python compileall 和 git diff --check 通过。新版五项协议已由不可变常量约束，错误修改默认映射也不得重新打开旧协议。**新版组合回归 121 PASS（同一运行、旧 Attempt 全入口拒绝后）**；原生 Authoring 五套在最终保护改动后 **41 PASS**；新增 7 项 native 原件/Need/Run 篡改负例也全部 PASS，早期 Material 迁移阶段曾 **71 PASS / 40 FAIL**，后续迁移后本轮完整回归已 **111 PASS / 0 FAIL**。旧 Planning/Authoring 迁移仍待继续；详细失败分类和证据见本轮 Task；当前 Material、Truth/Quality 核心与 Native Authoring 已有新代码实际通过证据；完整 Planning 集和 CUT5 尚未验收，不沿用改造前的 111 PASS 冒充当前结果。代码仅在隔离工作树，没有 Git commit/push，不代表整体软件验收或成片完成。旧 Attempt 只读保留，不能无证据升格或重复 Provider/Build。


## 2026-10-10 历史阶段：新 Attempt 默认启用与旧兼容（已被后续单线化授权覆盖）

用户已明确要求**从新创建的 Attempt 默认使用新版协议**，先以实际成片验证，完成后才删旧实现。`easel/integrations/result_protocols.py` 的 `DEFAULT_PROFILES` 已设为固定映射：`truth-source-ref@1`、`material-observation-delta@1`、`easel-script-claim-ledger@3`、`quality-review-delta@1`、`easel-hypit-source@1`。**不包含**过渡 `hypit-run-promotion@1`。新建 Attempt 若未显式指定 `result_protocols`，创建时复制并持久化当前默认版本；明确指定旧版本和已有历史 Attempt 的 pin 不受默认值影响，Retry 继承原 Attempt 版本；同一 Attempt 禁止两套 Authoring Writer 同时启用。默认配置的启用是**源码默认策略切换**，不是已部署服务热重载，不证明真实模型/Provider/Build 能完成成片。

验证：`tests/test_result_protocol_defaults.py` + `tests/test_authoring_publication.py` **25 PASS**；`tests/test_result_protocol_defaults.py` + native Authoring + 旧 journal 组合 **41 PASS / 41.35 秒**（Job `wc_job_dLEZ4X0QzPfc6Wpb`，均为内部离线集成，不调用真实付费资源）。删除旧代码属于**首次真实新作品成片成功之后的后续单独动作**；不能现在删除旧版或修改历史 Attempt 恢复格式。本节为本次提交范围说明，下方 ADR-005 显式 profile 软件验收记录是之前的阶段基线。



## 2026-10-09 UTC：ADR-005 显式协议软件实施与最终验收完成

在原 Goal `wc_goal_kaovu_gxSvF9cEjC`、Session `wc_sess_90Fh0Hg3TUl_XbNs` 和唯一自主首版 Task 的 O4/O5 下完成本轮软件范围。U1、Truth source-ref、Material/Quality delta、Hypit 原生解析/Authoring 交接及 Markdown ledger@3 已接入实际 Owner 和保存/缓存/冷恢复链。[ADR-005](decisions/ADR-005-agent-result-processing.md) 已按最新代码修订；[具名验收记录](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/adr005-result-processing-software-2026-10-09.json)保存命令、逐文件摘要、Job、审查与范围。

| 本轮直接观察的回归 | 终态 | 范围与版本关系 |
|---|---|---|
| `wc_job_J-sZqXQht6UTrt2y` | 107 PASS，257.06 秒，exit 0 | 原生 parser/typed graph、Authoring/managed/cold/CAS/fork、Quality、旧 journal/CLI/有限修复，含实际安装本地 static check；随后另补两处 native CLI 构造保护 |
| `wc_job_XyTXDYXot_2JSU8G` | 66 PASS，160.24 秒，exit 0 | Truth/Planning/source-ref、Material delta/资格/嵌套父证据 fork、实际 MP4 Quality、混合 Markdown 两代 fork、operator hash/revision/旧协议；这些实现未再改动 |
| `wc_job_hXz4h8kVrcv5ipKd` | 40 PASS，113.17 秒，exit 0 | 最后两处构造保护后的原生子集：complete/validate 本地恢复、严格 CLI、publication/冷进程/CAS、managed/实际 fork、native Quality 和 legacy 有界修复 |

套件有重叠，不合计为不同功能数。最终子集前后 46 个具名源码/测试/AGENTS/依赖声明完全相同，aggregate SHA256 为 `4658bb35aa5f34552d87c8c9cb92a92b4dad9b98f5f50c7daf9530137d66625e`；核对时间 `2026-10-09T17:18:51.458657+00:00` 与 `2026-10-09T17:21:22.546169+00:00`。仍为 `easel-studio` / HEAD `d5bd227c2b6750ae18cea06ebcf4f9f89350899b` 的 dirty 工作树，没有提交、推送或把整个仓库认领为冻结 release。

**独立审查已取得：** Astra Reviewer `/root/adr005_implementation_review` 对实际 publication revision `3172512921752053`、service revision `3172512921752054` 给出 **DECISION = CONTINUE**，显式 pin 范围内无剩余源码阻断项。CLI 构造取得在本地错误 context 内，实际 check 在外，既保护恢复又保留已知源码诊断的有限修复；40 项终态补齐落盘后的行为条件。下方其他窗口“Reviewer 不可调用/NOT_OBTAINED”为当时现场，当前以本条实际审查为准。

**解决的关键失效路径：** 原回复与程序派生分别持久化；Truth 引用由程序还原；Material 固定原 logical group 后复用独立 facts/撤销实际依赖资格；Quality 保留已决及 observed=False；Markdown 按 CommonMark 和原字节 coverage 审核。Hypit 的 Material/Revision/音频/表达/Quality 共享 typed 图，原 Authoring Owner 先验隔离候选再持久发表；IO/冷恢复不再次派 Agent。回归覆盖 validate 曾覆盖 native authoring 回执的问题及修正，不放松 parser 身份来掩盖证据丢失。

**保留范围：** `DEFAULT_PROFILES={}`；新 profile 显式选择，原 Attempt 按 pin 恢复。窄版 `hypit_run_promotion@1` 保留为历史显式子链，与 `hypit_source@1` 互斥。默认 rollout、五 profile 同一默认链、B SourceUnit/candidate correction 和更广 Hypit Surface 为后续独立工作。CLI_ERROR/未经纯度核实的 TYPE_REFINEMENT_REJECTED 来源不明确时保留本地诊断，不匹配错误文字猜修复。

已执行实际安装 Hypit 纯 parser/本地 static check、实际 PNG/4 秒 MP4 测量和真实内部调用链；没有真实模型/Provider/Hypit Build/视频 E2E，没有服务重启/部署。历史 `DIAGNOSTICS_VERIFIED_HISTORICAL_ROOT_CAUSE_UNKNOWN`、A-details 原 FAIL/缺失原件、`output-admission-continuation-80http-v1` 的实际 HTTP3、remaining_batches=0、closed/dispatch_blocked、BATCH_SLOTS_EXHAUSTED 及账单 UNKNOWN 保持。ADR-005 软件 Goal 收口不表示“稳定自主出片”的真实验收 Goal 已完成。

## 2026-10-10：ADR-005 FINAL 受控软件回归完成，独立 Reviewer/正式冻结待定（另一窗口阶段历史）

本节保留原窗口、原日期和当时证据；后续接线、复核和本轮软件收口见上方最新条目，历史 FAIL、拦截与 NOT_OBTAINED 不改为通过。

原 Goal `wc_goal_kaovu_gxSvF9cEjC`、原 Session `wc_sess_90Fh0Hg3TUl_XbNs`、同一自主首版 Task。仍是 dirty `easel-studio` / HEAD `d5bd227c`，未冻结 release。按 AGENTS.md 的重要阶段要求，FINAL 只验软件合同，不包含真实模型/Provider、Hypit Build、媒体或第一条视频交付。

**最新受影响集成回归真实通过**：双 Authoring Writer 互斥及 legacy journal定向 **21 PASS**；原生 Authoring 的 Retry/子 Attempt/冷恢复用例 **3 PASS**（Job `wc_job_87fG9osVI9NvtJOD`，25.19秒，曾失败两次的测试现为通过；旧FAIL证据不删除）；Material + Quality + Script Markdown + native Hypit 原生解析跨域集 **29 PASS**（Job `wc_job_PjXSWy2Xvu6tDwaq`，18.80秒）；旧 Script Truth 与 Material 视觉合同回归 **81 PASS**；原生Authoring及legacy静态 Owner **17 PASS**（Job `wc_job_N0HSRBSTUeoVtTEP`，44.55秒）；另一份 Authoring/journal/原生/测试组合 **87 PASS**（Job `wc_job_RbPp_a_jLK1S55ro`，82.41秒）。这些套件有重叠，不机械加总。相关源码 `git diff --check` PASS。旧 Output 及 Protocol 默认 profile 均未打开。

**快照身份**：最后一次只读核心 Python/Native SHA256 记录：`hypit/authoring_publication.py=386b6639e3bd3e05…`、`hypit/native_source.py=333384256b6137fb…`、`hypit/native_parser.mjs=b762423216fa2b45…`、`hypit/service.py=7e1ad3efcc95bc11…`、`result_protocols.py=74edd36f5cdd5e8d…`。这只是动态 dirty 工作区 SHA，不是已提交冻结的 Git tree；多窗口继续写入后不能自动把旧测试归给新版本。

**目前未满足的正式收口条件**：AGENTS.md 第57–87行规定的重要阶段需 Astra 独立 Reviewer 输出 `DECISION=CONTINUE|MODIFY|STOP`；当前 WebCodex Runner 插件注册清单为空、Runner MCP server 清单为空，尚无实际 Astra 复核结果。普通自检不可冒充独立 Reviewer。另 `finish_coding_task` 审核记录为非clean dirty worktree，多个历史未跟踪产物，不能不经Owner确认删除。正式冻结/合并/提交亦未获允许。**故 FINAL 软件综合测试验证完成，但正式独立复核与冻结/归档仍未完成，Goal 应继续 ACTIVE，不得标整体完成。**


**本窗口额外 FINAL 验证（2026-10-10）**：实际一组组合回归 `tests/test_authoring_publication.py`、`test_native_authoring_publication.py`、`test_native_authoring_owner_recovery.py`、`test_hypit_native_source.py`、`test_material_result_delta.py`、`test_quality_result_delta.py`、`test_script_markdown.py`、`test_script_truth.py` 共 **87 PASS / 82.41秒**（Job `wc_job_RbPp_a_jLK1S55ro`）；Material冻结合同、Truth来源冷重建、Quality实测补充 **73 PASS / 17.55秒**（Job `wc_job_rAE6qbDBtnmsJJvK`）；Markdown Source-Ref→Truth→两代 Material fork **1 PASS / 105.92秒**（Job `wc_job_HWU-3i4E7KoRIOqU`）。数据集重叠，绝不累加为“161项不同功能”。测试前后22个关键源/测试文件按路径名+SHA256排序聚合的 `manifest_sha256=e3cfe2feb05f1034654904633df2571e2186865afa5a594d63ad34060a05fcd9` **完全相同**，Git HEAD仍为`d5bd227c2b6750ae18cea06ebcf4f9f89350899b`，仅证明本次受测文件未漂移，不能代替干净Release。Git `diff --check` PASS。

**给 Astra Reviewer 的最小独立复核输入（尚未执行）**：读 `AGENTS.md`、`docs/decisions/ADR-005-agent-result-processing.md`、本 CurrentState、原唯一 Task，限本次冻结测试对应的差异和上述SHA。只读审查：(1) capture/admission/derivation/source-ref/Markdown冷恢复没有假事实/重复请求；(2) Material V1.3、Rights、Need/Match/Readiness、Quality旧已决`observed=False`没有被放宽；(3) Hypit native AST/SVRun/SVS、单一Authoring Owner、两个profile互斥、Intent提前持久化、外来文件/中断/Retry parser身份闭环；(4) 现有FAIL/UNKNOWN和媒体调用预算保持。输出严格为 `DECISION = CONTINUE | MODIFY | STOP`、`RISKS`、`MINIMUM_CORRECTION`，不授权源代码改写/真实AI/Provider/媒体Build。当前无Astra可用Provider，因此 **DECISION = NOT_OBTAINED**；不得将本记录或 Main 自检称为Astra意见。

## 2026-10-10：ADR-005 U3 原生 Hypit/Authoring 软件阶段验收（FINAL 仍待）

在原 Goal `wc_goal_kaovu_gxSvF9cEjC` 和唯一自主首版 Task 下继续，未新建视频生产主线。最新 opt-in `hypit_source=easel-hypit-source@1` 已连接 `complete_film_authoring` 的正式 Owner：冻结 Planning/Truth、Director/Creator、Material V1.3/Rights/Readiness、Hypit 原生 SVML/SVRun/SVS、复合型 typed refs/源码位置、隔离候选静态检查、持久 Intent、有序文件发表、最后 Attempt READY 注册；所有 Provider/Build/Runtime 仍在原边界外。未设置任何新默认 profile（`result_protocols.DEFAULT_PROFILES={}`）。

**本轮当前代码实测**：`tests/test_native_authoring_publication.py` **16 PASS / 41.01 秒**（Job `wc_job_Z1D1FYvTgpBmpBJN`），含真实安装 Hypit 0.2.7 的本地 `hypit check` 静态检查 1 PASS（无 Runtime/Build，另有独立单项 1 PASS/2.47 秒）、候选原件/发表回执、部分首尾提交中断后不重调用模型/CLI、真实全新 Python 进程无网络冷恢复1 PASS/2.99秒、外来文件漂移/候选污染拒绝、并发仅一份结果、局部校验读IO恢复及失败不提前 READY。独立原生 AST/SVS/typed-ref 测试 8 PASS，首次联合 U3 parser+Authoring 回归 **21 PASS/47.38 秒**（Job `wc_job_0hhSV_Lu9hb7kcKW`，执行时还未增加最终两个测试），旧 legacy Authoring/机器可判定Run修复 **2 PASS**。其他历史重复套件不得机械加总。

先前较窄的 `hypit_run_promotion@1` 保留为显式兼容子链；新增 `result_protocols.validate` 校验，不允许同一 Attempt 同时 pin 它和 `hypit_source@1` 两套 Authoring Writer。专属 `tests/test_authoring_publication.py` 综合测试启动曾被平台安全检查阻断，**本次未取得新增互斥回归的实际 PASS**；需在 FINAL 受允许时补证或在独立审查中保留为明确缺口，不可虚构验收。

**U3结论**：完整原生路径已达到阶段性软件实施和定向验收，允许把 Goal 中 U3 标为“completed（software stage）”，不等于已部署、默认开启、真实模型视频交付。FINAL 仍需按 AGENTS.md 做 Astra 重要阶段独立架构/正确性复核，核对最终源码版本、跨单元组合回归、协议互斥与旧版冷重放；正式发布或开启 profile 均不在本轮授权内。当前 `easel-studio` / HEAD `d5bd227c` 的脏工作树及其他窗口文件、历史 FAIL/UNKNOWN、实际费用和预算未修改；无 Git commit/push、真实 Provider/Build 或服务重启。

**新增 FINAL 现场**：另一窗口跨 Retry 复测 Job `wc_job_U6vFg0QaaiMogPjX` 首轮 1 PASS / 1 FAIL；`before_intent` 故障注入在父 Attempt 的 `validate_film_attempt` 阶段先被触发，没有进入预期子 Authoring 交接阶段。尚不能将这一测试视为恢复合同失败或已修复；保留为 FINAL 需核对的独立测试现场，不覆盖其他窗口实现。

**FINAL 进一步现场与源码指纹**：跨 Retry 测试 Job `wc_job_NX-w5_ecUwO_xTPy` 为 1 PASS / 1 FAIL（exit 1）。失败点是 `_execution_fingerprint()` 严格比较 **当前 installed parser identity** 和已发表 `native_publication.parser`，返回 `Native parser differs from the published Authoring identity`。可能涉及并行源码更动、测试阶段切换或回执不一致；**精确根因未证实，禁止放松 parser hash 绑定**。当前工作树精确文件 SHA256（非仓库提交/未冻结）摘录：`hypit/authoring_publication.py=61512d0d269bf19f…`、`hypit/native_source.py=93856a8c4c960783…`、`hypit/native_parser.mjs=b762423216fa2b45…`、`hypit/service.py=e578133dfb960937…`、`result_protocols.py=74edd36f5cdd5e8d…`，HEAD=`d5bd227c2b6750ae18cea06ebcf4f9f89350899b`。受测文件若变化需按新SHA重新跑相关验证；不得把动态工作树当作冻结Release。最终跨模块 pytest 合并调用曾被平台安全检查阻断，没有获得 PASS。


## 2026-10-10：ADR-005 U3 受控 SVRun 发表子链真实接入（部分完成）

沿原唯一 Task 和 Goal wc_goal_kaovu_gxSvF9cEjC（Session wc_sess_90Fh0Hg3TUl_XbNs）继续；当前 dirty easel-studio / HEAD d5bd227c，其他窗口未提交代码和历史证据保持。没有新建 Goal，也没有在当前运行服务启用新协议。

**本次实质改动**：result_protocols 增加显式且默认关闭的 hypit_run_promotion=hypit-run-promotion@1。只对已经通过 Easel Creation/Attempt、Plan/Bundle/Readiness、authoring_source 路径及禁止 Build 身份检查的 Run 清单启用。_hypit_run_markup() 将原 JSON sidecar 与程序确定性的 native main.svrun 按一个有界 publication 意图执行：先在 .easel/authoring-publications 保存原件/候选/hash 证明，再发表固定文件；可恢复自己的部分写入，外来修改拒绝。native 文件再次消费必须存在当次原发表 journal，不得对已完成的 native 文件临时创建一份证明。未 pin 新 profile 的旧 Attempt、hypit check、Material Rights/Gate、选片和 Build 责任保持。

**证据**：tests/test_authoring_publication.py 及旧 test_authoring_is_runtime_independent_and_static_check_only 当前共21 PASS、0 FAIL，包含中断续写、外来更改、敏感内容/坏JSON、旧profile、冻结身份、journal丢失拒绝。真实内部 Creation/Handoff→Planning/Truth→Material→Authoring→失败后fork 新 profile 集成1 PASS/98.29秒（Job wc_job_GLqrTJsZaOlsp4Eu），只有外部服务为确定性替身，不调用真实模型或Hypit Build。这证明的是 SVRun 子链软件闭合，不是 ADR-005 E2E 或视频交付。

**U3 新增原生候选与合流约束（最新只读核对）**：同一工作区已出现 `hypit/native_source.py`、`native_parser.mjs`、`native_revision.py`、`native_audio_graph.py`、`authoring_publication.py`；`result_protocols` 另注册显式 `hypit_source=easel-hypit-source@1`，`complete_film_authoring` 在该 profile 下分流至隔离候选→原生语法解析→Hypit静态 check→Attempt发表意图及有序恢复，复用原服务 Owner 与未授权 Build 边界。实际 Hypit 原生 AST/typed引用/来源位置测试 Job wc_job_XYcjoSouuWtDcBlY 为8 PASS/6.49秒，连同 Quality 的 Job wc_job_qlnES7i7x5nWkRCH 为14 PASS/15.39秒；此前1 FAIL/7 PASS 的诊断记录保留。当前缺少 **完整 native Authoring 文件发表/重启恢复的实测终态**，其代码仍为候选。原 `hypit_run_promotion@1` 是已验证的窄路径，不应与更完整的 `hypit_source@1` 同时按生产路径激活；后续必须先证明完整路径、确定单一Owner和版本继承关系，再决定是否合并/退役窄实现，不能形成两套并行主生产线。

**未完成/冻结边界**：原生AST已有局部真实测试，不能继续称仅源码能力；但完整 SVML、selection、SVRun、SVS/SVS recipe、受保护音轨、Rights和跨文件发表仍须原 Authoring Owner 的完整真实内部集成与独立复核（含中途失败、冷恢复、文件外来更改及受测版本冻结）。任何安全检查拦截都不以替换执行路径绕过。U3/FINAL均不标完成。全部新profile默认关闭，保留Git工作树、预算、旧FAIL/UNKNOWN，不重启、commit或push。


## 2026-10-09：ADR-005 Agent 结果处理软件实施分单元进度（未整体完成）

本次沿原唯一自主首版 Task 的 O4/O5 和 ADR-005 实施，持久 Goal 为 wc_goal_kaovu_gxSvF9cEjC，接续 WebCodex Session wc_sess_90Fh0Hg3TUl_XbNs；不是新的视频生产链。当前 Checkout 为 easel-studio / HEAD d5bd227c，工作树包含其他窗口未提交改动，所有目标仍需在最终版本上重跑受影响集成。U0、U1、U2a 已登记软件阶段通过，现有 Receipt、Truth source-ref 和旧版本继续使用原合同；38项、独立/联合场景与源码冷恢复已在原 Task 保留证据，不能与有重叠的28/25项机械相加。

**U4 Markdown**：已完成明确版本的初步端到端接入。项目依赖新增 markdown-it-py>=3,<5，本地已验证；script_markdown.py 实现原文UTF-8块区间、CommonMark结构、未知标题/围栏/列表/引文保守覆盖和未解释行的完整检查；script_truth.py 新增 easel-script-claim-ledger@3，旧@2默认保留。新Attempt经显式结果profile选择后，Truth独立/联合、Planning persist/load、source-ref出处与冷回放使用冻结的对应版本。相关 Markdown/旧ledger 22 PASS、联合新旧 source-ref 共30 PASS、真实内部Preparation→Planning→Truth→Material两个新增选择2 PASS；未更改默认 profile（仍空），不冒充真实模型语义通过。额外跨流程Markdown Source-Ref→Truth→两代Material fork已有最新单项1 PASS（Job wc_job_CfadeC90qETC9s83，105.45秒；曾经失败的原Job仍保留历史），完整组合与实施代码复核仍属最终验收。

**U2b Material**：阶段性软件验收已补齐。已接入 facts/checks delta、原件凭据、事实资格/争议持久化、程序完整报告、Web Owner与Matching/Readiness临时证据视图。当前视觉合同及Material Owner测试68 PASS（含直接 Web Owner→官方观察→缓存复用5 PASS）；共享Owner/批次恢复/异议/独立候选的既有集成补验6 PASS（Job wc_job_gzqX0vY9vE_mfv7t），旧23 PASS与Astra CONTINUE均保留但不跨重叠集机械累计。原冻结V1.3、Rights、UNKNOWN与缓存身份不放宽，默认profile仍关闭；最终组合与受测源码封存在 FINAL。
**U2c Quality**：最新 `quality_results.py` 现已接通 Web Owner、Quality inspect、saved/pending、Delivery 状态与 repair_request，保留真实MP4输出、观察轮次及冻结Director/修复边界。独立新协议源头、历史 observed=False、两轮 delta、合法事实异议、原件冷进程、修复额度与 Web consumer 共6项定向测试通过（本窗口）；另一窗口既有实际 MP4 多轮 Owner 集成 2 PASS（Job wc_job_xpX0cjtwgmvgEST6，15.40秒，已核对终态）。早期 2 PASS/3 FAIL 对应旧接口与测试未适配的状态，不代表当前版本依然失败。Astra 对应跨模块合同前置复核为 CONTINUE；仍需最终整组回归，默认 profile 保持关闭。
**U3 Hypit**：本轮新增的非生产 `hypit/publication.py` 意图/原件/部分成功续写工具已有14项离线测试PASS，新增路径正规化、外来写入者中途改写拒绝、UTF-8/JSON完整性/敏感内容拒绝；现有 `complete_film_authoring` 旧路径静态校验1 PASS，时钟引用规范化的原字节（CR/CRLF/Unicode）保留与旧测试2 PASS。发表模块仍未连接正式Authoring，因此不具备生产准入权；已安装Hypit0.2.7原生AST入口直接探针被平台安全检查拦截，禁止换入口绕过，SVML/SVRun/SVS AST迁移尚未完成。**U3仍为IN_PROGRESS，不能标为完成**。

**FINAL风险/边界**：Markdown source-ref→Truth→两代fork原失败单项已复跑1 PASS（Job wc_job_CfadeC90qETC9s83，105.45秒；旧 wc_job_D4f028MglqIFUY-a 的36 PASS/1 FAIL保留历史）；更大组合pytest调用本轮被平台安全检查拦截，未形成可证实的综合回归。默认新profile仍为空，用户冻结预算与历史FAIL/UNKNOWN不变；未发起真实模型、Provider、媒体或Hypit Build，不重启/部署/commit/push。不将部分软件验收、既有静态check或AST源码能力等同实片交付。



## 2026-10-09：A-details 离线诊断修补已验证，历史精确根因未确认（本轮停止）

通过原 WebCodex Session `wc_sess_TVqbfxf7Z6k74Oz_` 从检查点 `wc_msg_UVtrp6bJO-z26lNi` 续接原唯一 Task；本轮范围限于原件离线诊断、最小修补与受影响集成测试。当前状态 **DIAGNOSTICS_VERIFIED_HISTORICAL_ROOT_CAUSE_UNKNOWN**：诊断能力修补子项已验证，历史故障精确复现及修复未完成，原“稳定自主出片”Goal 仍进行中。此次正常权限读取已成功，不再把前窗口访问拦截写作当前阻塞。

原 Job `wc_job_a4moxdKR6BxULVLY` 已 failed/exit2；第二批首例 FAIL、2 次实际 HTTP。A-selection 与 A-details 均 HTTP200 / RESPONSE_COMPLETE / tool_calls，参数流分别1706/19653字节；原 A-details run `easel-4583ce810be04841b33b0709cc3ac7b7` 已 error/released，保存的 CAPTURE_PENDING 不表示仍在执行。原请求的 input view、selection admission、details/wire 绑定与实际 HTTP Schema 已由原 journal 离线重建一致；Schema SHA `40d9caadca47a85ef32f425d5ebeee00e27b1e9bc78ba7b5765bdf8246a83411`。已检查的代理、原 run 日志、SDK transcript/trajectory、请求 guard 与 capture 持久化通道未保存可恢复的 A-details 参数原文或具体底层异常，不能据完整传输认定 JSON、SDK 或语义成功，也不能断言原失败是 missing finish、TLS 或 Schema 问题。

最小修补在现有 `rejection@1` 机制中保留首个 error/aborted 诊断，并在 SDK 清理未完成 tool call 前保存受限类别和形状信息；不保存异常正文/堆栈，不改变候选合同或接收终态。仓库兼容补丁仅应用到新离线副本 `/tmp/easel-structured-runtime-offline-rootcause-20261009T132535Z`；原 Runtime 11 个固定文件未变，无升级或服务重启。仓库新 helper/transport 身份 pin 对旧 Runtime 会 fail closed；本条不表示运行中服务已加载修补。

修补前确定性诊断对照 Job `wc_job_Wt1le4C-KRrn1uYz`：2 FAIL/7.89秒；修补后受影响组合 Job `wc_job_wPmg85ctH0otMP6I`：29 PASS、0 FAIL/0 skip、80.39秒，已取得终态并核对 JUnit。包含真实内部 Gateway→transport→SDK→helper→reader 拒绝链，以及既有正常 Owner/Planning/Truth/persist/load 生命周期；仅外部 Provider 使用确定性回复，共6次本地替身 HTTP。missing-finish 用例为诊断缺口对照，并非原故障重放。测试前后14个具名源码/测试文件摘要 `f995591c70a5560c1460274c18e472a251b2421d35c93537a9e4c41f136d6b7a` 不变，branch `easel-studio` / HEAD `d5bd227c2b6750ae18cea06ebcf4f9f89350899b`，修改未提交。

[具名离线证据](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-sdk-error-diagnostics-offline-2026-10-09.json)保存命令、Job、逐文件摘要和限制；私有证据目录 `offline-root-cause-20261009T132535Z` 保存修补前后 JUnit、Schema 重建及原件保护核验。17份原证据的字节摘要保持；只读 SQLite 访问产生了新的空 agent WAL/SHM 协调文件，原数据库和原已有 WAL 字节保持。已有修改及另观察到的 ADR-005/索引文档改动均保留，不从 dirty 状态推断并发来源。

原池 `output-admission-continuation-80http-v1` 仍实际 HTTP3（1+2）、两个批次槽位已用、remaining_batches=0、closed/dispatch_blocked=true、BATCH_SLOTS_EXHAUSTED；未改账本或重开。账单 UNKNOWN 保持，本轮新增真实模型/配额/媒体/Authoring/Build均0，¥30旧媒体上限不构成本轮授权。原 FAIL、NOT_REVIEWED 与视频0保持。本轮止于历史证据不足；不继续工程首片或三主题验收，不标记原 Goal 完成。下方为此前时点。

## 2026-10-09：按用户授权本地提交代码并完成服务重启

代码提交 `82b66519fa12379d4ef7d2fd477c58f57d67eddf`，分支 easel-studio，103个明确选择的源码/测试/夹具/当前文档文件；1190个批量历史运行输出原样留在工作区，未推送。生产223文件SHA仍为 `90ab1935538ab3044c61ae1889392cfc42ae39ebfd26d3a78dc03ea1b1fb0272`，与此前168项相关回归及原生1项的冻结源码/测试一致；本轮未重跑该整组，另完成前端tsc/Vite build及本地静态资源HTTP验证。

通过原LaunchAgent重启：ai.openclaw.easel PID21609→22325，com.easel.web PID21631→22399；Gateway18789 /healthz为200且ok=true，Web7860首页和/api/status为200且gateway=true。首次bootout后立即bootstrap返回exit5；确认服务已卸载且端口无监听后，经同一正常入口重新bootstrap成功，保留失败记录。原流记录及两份服务日志已在受保护目录精确备份。模型/Runtime/服务配置未更换，Runtime仍2026.9.4；无进程内源码SHA端点，加载证据为新PID/启动时间/原执行路径/已提交源码核对，不冒充进程内证明。

Gateway任务总数621前后未增、active/lost/audit均0；20份Creation元数据、302保护文件、142fixture和5份封存账本不变。原UPSTREAM_UNKNOWN、剩余授权和历史FAIL保持，不发起新模型/配额/素材/Build/发布，也不认领真实Planning或成片通过。[提交与重启记录](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-commit-restart-2026-10-09.json)。

## 2026-10-09：三项机械约束简化完成，相关回归与原生生命周期通过

已完成获批三项：新`intake@6`视觉queries允许0～3条，1/2条由已有标量检索字段无损承载，不补词/删词；英文、长度、唯一性和模态限制保留。新Plan固定`visual-requirements@2`，完整唯一整数ID的classification/checks由程序对齐，空字符串preference_notes允许，无需占位评价。原始compact_results不改，另记可重算规范化摘要；缺项/重复/未知ID/错帧/额外字段/必要依据不足仍拒绝，not_met/unknown不会变成通过。旧intake5与visual1、缓存、原请求保持旧规则。

断线前六个Planning文件核对仍等于partial快照，未重复撤回，保留其成果完成下游。当前source `90ab1935538ab3044c61ae1889392cfc42ae39ebfd26d3a78dc03ea1b1fb0272`/223生产文件（本范围10生产文件变化，HEADdf0d3a30 dirty未提交）。最终相关回归Job `wc_job_rau70u9oykDBj0vX`：168PASS/0FAIL/0skip，822.24秒；当前原生Job `wc_job_ktVJZcoiSk3o457P`：1PASS/38.27秒、5次本地替身HTTP。此前53与20项通过与最终集重叠，不相加；全部外部回复为确定性fixture，不证明实际模型成功率或完整视频。

[具名验收](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-advisory-validation-2026-10-09.json)，私有证据`advisory-validation-20261009T090924Z`含前后快照、两份中间JUnit、最终JUnit、原生报告与源码围栏。源码及测试身份一致，302保护/142fixture/5封存账本保持，语法与范围diff通过。独立Reviewer未取得，不冒称独立批准。无新真实模型/配额/媒体/Build、无部署/提交/推送/发布或MP4；原上游UNKNOWN与未分配授权不改。本单元不再需要重做，真实派发仍先处理原请求未对账阻塞。以下是历史时点。

## 2026-10-09：按用户要求移除自动配额查询，完成非必要校验定向盘点

评测执行器已删除远程quota GET、余额读取失败阻断与25%余量门槛；执行前/逐HTTP/阶段入口改为`check_authorized_route`，仅本地核对既定模型、接口、无fallback与原凭证指纹。旧`subscription-quota-readonly.json`只复用已授权credential_fingerprint，不需要新余额快照；返回NOT_QUERIED，不伪造零账单。Planning/Material/Hypit生产代码未改。相关真实内部runner/恢复/本地HTTP预算回归15PASS，加开发额度边界4PASS；模型回复均替身，无真实模型或配额网络请求。

用户追加要求检查过严校验。定向检查Planning与Material，合成离线对照确认：queries空列表可接受而1/2条拒绝；Material空preference_notes拒绝；完整唯一ID的checks仅顺序改变也拒绝，按ID无损恢复原序后通过。另发现多组同帧description/style逐字相等、B引文512字符截断边界值得替代设计；前者不能简单取第一条掩盖真实矛盾，后者仍有总容量与来源完整性约束。除配额操作外本轮仅盘点，未放宽正式合同、未启用query回退或新增规范化。优先级与证据在原Task的新章节。

本轮19项定向测试不代表全量或真实Planning资格；已有UNKNOWN请求、失败批、父池及剩余授权不修改、不重发。证据保存在私有`remove-automatic-quota-20261009T082246Z`（原件备份、两份JUnit、nonessential-validation-audit.json）。执行器/测试变化使旧真实批工具摘要不再适用于新执行，不能改写旧manifest。下方网络/余额失败为历史现场，不再是自动查配额的理由。

## 2026-10-09：统一接收新资格首例上游响应未知，保留软件结果并停止真实派发

新授权池`output-admission-continuation-80http-v1`已分配第一批（每批40HTTP/2700秒、总2批80HTTP/5400秒），原三主题六载体冻结后真实首例FAIL，后五例未提交。固定source e5cb1c59/223文件；Job `wc_job_fyWdm7hui8zUqGV3` exit2，样本71.890秒、HTTP提交尝试1。未收到任何上游正文/参数/usage/终态：response_bytes=0，账本UNKNOWN/UPSTREAM_UNKNOWN；本地Eval proxy约65秒后返回自身502类别，不能说MiniMax服务器返回502。原Gateway run `easel-6d9cdc9712fe4ec3831117746320db38`已error/released，原结果读取TOOL_REJECTED；模型候选、admission、A-details/B/Truth均未进入，不是已证实的contains或语义回归。[真实结果](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-output-admission-qualification-batch01-2026-10-09.json)。

随后只读quota GET实际TLS握手超时（Job `wc_job_u6KbSyIZw8Ews4xH`），故末次余额及现金账单UNKNOWN；首次预检100/97不能当末次余额。该网络错误不证明POST失败在相同层。现有proxy异常分支未保留具体异常类/远端request id，尚不能证明Provider未接受，原HTTPUNKNOWN不改零消耗。第一批closed、父池dispatch_blocked=UNRECONCILED_UPSTREAM_REQUEST，第二批未分配，剩余授权保留，不重发原样本。

当前源码/302保护/142fixture及绑定旧账本均核验不变。第一单元原生补验与第二单元软件49PASS+原生1PASS保持，但不等于真实Planning可靠；无新媒体/Build、未部署/提交/推送/发布、视频0/3。下一步先原请求及网络证据对账，不盲改规划语义、不通过新Key/Session/批号重提。下方为软件与先前状态。

## 2026-10-09：原生补验通过，Material/Truth接收凭据完成相关软件验证

原受阻的第一单元原生验证经正常原入口获准执行：1PASS/35.39秒。第二单元已在既有Material compact/Truth文件消费点接入`stage-output-receipts@1`：新请求事前固定policy，实际会话身份绑定policy；已有旧缓存/原会话保留旧策略。Material仅沿用完整json围栏，Truth保留strict JSON及合法CONFLICT/UNRESOLVED；raw/候选/凭据独立，保存失败本地重建，凭据损坏不触发模型格式重试；逐原指令保存Truth报告，后次repair文件不能顶替前次原件。冗余claim仍先经原领域检查后记录投影，不改变语义/预算/素材Gate，queries回退未启用。

当前固定工作树source `e5cb1c593e1d743e81c64c0c38f7144c2fac26b7f4712a7f3f34e101975d81aa`/223文件，HEADdf0d3a30。当前组合49PASS/79.13秒，当前原生1PASS/36.44秒（5本地替身HTTP）；源码/测试围栏、302保护/142fixture和范围diff一致。早期广泛运行76PASS但中途源码完善，保留为诊断，不转授当前版本。首次17场景16PASS/1FAIL为legacy测试缺delivery容器，修正后已包含于当前49项。[具名收尾](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-output-consumers-2026-10-09.json)。独立Reviewer仍不可用，Owner复核不等于独立批准。

本条时点真实模型/媒体/Build新增0、未加载线上/提交/推送/发布、视频0/3。用户本轮新授权`output-admission-continuation-80http-v1`两批总80HTTP/5400秒、每批40/2700、各六例；旧池封存。下一步在实时对账与套餐核验后分配首新批，不重复软件实施。下方原生受阻为历史状态。

## 2026-10-09：统一接收第一单元实施及相关软件验证通过，原生验证受平台拦截

已新增`easel/output_admission.py`并接Planning新intake@5：安全完整解析后只规范化明确注册、外层合法且与当前BGM规则完全相同的contains回显；不忽略任意extra，不删真实条件。raw、normalized及正式产物分离；接收凭据在A-details前持久化，details绑定原始/规范化摘要和规则，冷verify从原件重建并拒绝凭据、动作、载荷或policy篡改。原@4及以前保持旧协议；共享repair次数和正式语义准入不变。

最终组合67 PASS/0 FAIL/0 skip（Job `wc_job_8RjVLzueHKjdljuS`，pytest271.64秒），覆盖规则正反例、正常Owner至Planning/Truth/load、联合repair、中断恢复、冷进程、旧协议及相关Material/fork/Rights。外部回复均fixture；前两轮22/2与46/1保留，修复了测试的checkpoint续接及原终态观测模拟，不绕过生产UNKNOWN保护。原2071字节样本离线可NORMALIZE并构造7槽位，旧请求精确重建，原件和旧失败不改分。原生Gateway新测试调用被平台安全检查拦截，无新Job/无结果，未重试/改路；不能把已写测试当作原生通过。

source `8f4743d0afdc5c22ad73c29157a7ca71f4d60fe6c389c66e1fb5407f4e73d0f4`（222生产文件，HEADdf0d3a30 dirty未提交）及两测试文件围栏一致；302保护/142fixture和绑定封存账本均保持。[具名实施结果](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-output-admission-implementation-2026-10-09.json)。状态`FIRST_UNIT_SOFTWARE_VALIDATED_NATIVE_VALIDATION_BLOCKED`，独立Reviewer未取得。第二单元Material/Truth消费者凭据迁移未实施，完整fence/strict profile仅注册测试，queries回退未启用。本轮新真实模型/媒体/Build0、未加载服务/提交/推送/发布、视频0/3。下一步保留现有实现补齐获准的原生验证，再按原计划推进，不重开历史批次。下方为此前时点。

## 2026-10-09：接收问题盘点与统一规范化设计完成，未实施生产变更

按用户要求完成审计与统一设计，方案写入原自主首版Task的“模型结果统一接收方案”章节。重点核对9个具名资格批独立首例（8例有模型run、1例调用前工具误拦）：7例首阻塞属输出合同，2例属实现/评测；7例中仅最新contains已证明可无损解除首结构阻塞，另6例不能只过滤。另复核旧R4十批12次样本汇总及vNext围栏反例；不是全项目失败率或可救回成片比例。

本轮重新用最新2071字节A-selection原件作内存对照：唯一Schema错误是needs[6].contains，精确重复当前数组BGM规则与外层bgm/required；副本去该字段后原Schema通过、可构造7个details槽位。原件/旧FAIL未改，A-details/B/Truth未执行。已确认至少五处有可逆codec/有依据投影；方案复用四分类，分清安全raw、normalized、formal，未知extra与真实语义/身份/授权错误不能静默过滤；可选queries回退单独证明，不冒作无损normalize。

source仍`1dccfb0f1c3a68602a45b4f28240f2eec818e070828a43f6db38d4fa820b630d`/221文件，302保护/142fixture匹配。本轮仅设计/审计文档和私有摘要，无生产改动、新模型/素材/Build或部署提交推送发布；DRAFT_NOT_IMPLEMENTED，不是独立批准或Planning资格，视频0/3。[审计证据](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-output-admission-audit-design-2026-10-09.json)。下方“根因未知/访问阻塞”为历史时点，后续正常读取已定位contains，不再作为当前根因未知。

## 2026-10-09：关系审核版本已真实执行首例，FAIL后详情读取受平台拦截

承接用户“继续按目标推进，不用每次询问”，按原单新批6例/40实际HTTP/2700秒界限建立`relational-qualification-2026-10-09`，source `1dccfb0f1c3a68602a45b4f28240f2eec818e070828a43f6db38d4fa820b630d`、intake@4/review@2、隔离M2.7未变。派发前221源/302保护/142fixture匹配，125历史隔离Creation无待对账请求，Gateway active/lost/audit0，套餐99/97。

唯一真实Job `wc_job_MC1TtZ_P5MLVuUHA`已exit2，执行器报告首例FAIL、actual_http=1；后五例没有派发。读取原运行结果、账本、journal与候选详情的诊断被平台拦截：`因 OpenAI 无法确定请求的安全状态，已拦截此工具调用。` 未取得执行结果，未换入口/拆分/重试绕过。不能据A-selection的早期pending快照推断最终根因，也不能认领远端原run已释放、封账及末次历史指纹已核验；这些均待原执行对账。[具名断点](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-relational-real-qualification-2026-10-09.json)。

本轮未修改生产源码，未派发媒体/Build、未加载服务或提交推送发布，无新MP4。原Goal继续保留，但当前相关操作停止于平台访问阻塞；恢复时读取原Job/run/账本，不重跑首例、不启动剩余项或擅自新批，不盲改代码。下方为此前时点。

## 2026-10-09：关系审核修复与无损输入去重完成离线验收，真实资格未重开

新候选为`confirmed-planning-intake@4`/`planning-candidate-review@2`：A明确语义Need与实际asset职责；B视觉覆盖须有实际视觉候选承担关系，未决类别与相关Need模态一致；修复反馈保留具体字段/长度/来源错误，512字符及共享一次repair不变。新策略按原文物理行排序，保留旧@3及以前的恢复。续接取回原Job72 PASS/1 FAIL，唯一测试期望未识别@2必要性重审，已修正且原FAIL留存；不重派旧Job、不冒认一次73全绿。

本轮B消息去重仅改变请求投影：逐题coverage_candidates/candidate_context引用同请求共享candidate_bindings，全文候选、全部来源、响应Schema及内部canonical/recheck均保留并校验引用。原七slot/56题同指令离线对照555762→391086字节，减少29.63%；逐题全部值可还原。不是语义裁剪，也不是实际token/费用或真实错误率降低的测量。当前组合30 PASS、原生生命周期1 PASS/5回环替身HTTP、Planning/Truth/Material相关7 PASS，语法与范围diff通过；外部语义回复仅fixture。旧@3实际四阶段请求逐字SHA重建相等，原件不改。[具名收尾](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-relational-review-2026-10-09.json)。

当前221生产文件source `1dccfb0f1c3a68602a45b4f28240f2eec818e070828a43f6db38d4fa820b630d`已记录，后续原生/下游验证围栏至收尾不变；HEAD仍df0d3a30、dirty未提交。302保护/142fixture及本轮绑定的封存资格账本SHA一致。独立Reviewer仍不可用，只有Owner窄复核。所有本轮Job已取终态；新增真实模型/媒体/Build0、未加载服务/提交/推送/发布、视频0/3。下一步是这个固定候选的新有界真实Planning资格，须独立授权；旧批与余额不重开，不再重做本次修复或格式实验。下方保留此前时点。

## 2026-10-09：P3完整真实资格首例FAIL，B及一次修复已执行，批次封存

用户已明确授权新单批6例/40实际文字HTTP/2700秒。按source `49b691720f2a2086773aa6d28df61cac2fff9dfe66aaa7c970a6b51da1e18ff3`及原隔离M2.7候选实际运行第1例；新A-selection/details、B、共享repair各1次，4实际HTTP/214263报告tokens，样本293.964秒。第一例FAIL后封存，后5例未提交，B重审/Truth/Supply/Build未进入。[本轮具名结果](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-p3-real-qualification-2026-10-09.json)。

直接拒绝为repair `target-0000/support/0/quote` 1060字符超过512上限（原B引用980字符）。同时有独立语义反例：A仅提出1个BGM、0视觉候选，却声称图片候选由程序补列；B原始32题均写ACCEPT（12题未通过本地答复校验，并非32题正式通过），global覆盖把来源分镜存在冒作候选已覆盖。未决分类缺related_needs；修复虽补候选handle，却连图片报告也绑定唯一BGM。引用长度放宽或手工裁剪不足以解决这些问题；原候选/回复不改，不认领正式语义通过。

本次4条参数流SHA均与SDK/Easel捕获一致，4原run均ok/released，未观察到传输丢失或截断。新账本closed，旧两池保持封存；收尾Gateway active/lost/audit均0，套餐前后整百分比99%/97%不等于无消耗，实际现金账单UNKNOWN。221生产文件、302保护和142fixture前后逐项一致；本轮未改生产/Runtime、未加载服务或commit/push/publish，新增媒体/Build0、视频0/3。下一步依据本次原件离线定位A视觉承接与B错误放行，不重复封批或仅修引用长度就认领稳定。下方保留此前时点。

## 2026-10-09：P3软件发布前核验通过，待新增真实Planning资格范围

本次正常读取原P3基线成功，未更换入口绕过限制。302份受保护文件、142份历史fixture逐字SHA一致，旧80HTTP总账及节点对照终态报告保持封存不变。当前221个生产文件已固定工作树清单，source `49b691720f2a2086773aa6d28df61cac2fff9dfe66aaa7c970a6b51da1e18ff3`，HEAD仍`df0d3a30`且未提交；不是把旧e6c7基线转授P3。测试前后全source一致，本轮没有新生产代码改动。

绑定该源码的相关收尾回归31 PASS/0 FAIL/0 skip（59.15秒），覆盖P3、语义投影、阶段化/旧版本/冷恢复及Planning/Truth。旧319 PASS/2 FAIL及后续15 PASS保持历史原貌，不声称一次全量全绿。补查原真实七槽位上下文，生成56题、48+8两批；消息245960/137580字节，纯离线RPC容量检查在空环境下为428918/190200字节（本机ARG_MAX1048576），隔离Runtime指纹匹配。此项不代表实际模型已接受请求或语义已通过，真实派发仍须核对实际env/配额/未知请求。原候选optional和4条未决均未被修改或计成功。

Owner范围复核和源码/证据核验完成，独立Reviewer意见未取得。状态为`SOFTWARE_PREFLIGHT_PASS_REAL_SCOPE_REQUIRED`；原真实池不重开。本次新真实模型/媒体/Build0、未加载服务/commit/push/publish，正式视频0/3。下一步只做获明确额度的新六例完整Planning资格，不再重复P3或格式实验。建议单新批3主题×2、最多40实际文字HTTP/2700秒，仅套餐，尚未授权、未建真实Attempt或占额。[具名发布前证据](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-p3-release-preflight-2026-10-09.json)。

## 2026-10-09：P3实现及离线验证完成，发布前核验与真实资格尚待执行

`confirmed-planning-intake@3`/`planning-candidate-review@1`已实现候选/正式准入分离、冻结来源绑定的optional→required定向纠错、未决/待供给分类、一次共享repair、受影响重审及执行/verify重建。原A-details、Runtime、Material/Truth主链不变。断线原Job11 PASS/1 FAIL已取回；冷进程测试JSON加载修正后1 PASS。续审发现字符串`"false"`可能先转成bool后被接受，反例先FAIL，现于规范化前校验原始非queries合同，未放宽准入。

组合18 PASS；两个相关完整模块首轮319 PASS/2 FAIL（321项），两失败为严格正式出口新增拒绝顺序和P3必要性重审后的旧测试期望。保留原FAIL；测试分开证明optional-only及缺素材义务均拒绝，并让新P3重审必要性、旧协议保留原问题集合。生产代码未再修改，受影响路径补验15 PASS/0 FAIL；未机械重跑全部，不能声称一次321 PASS。原生P3生命周期1 PASS，5次回环替身HTTP经过原Gateway/SDK，完成联合修复/重审/落盘/verify；外部语义仅固定测试回复。语法及范围diff检查通过。[具名软件证据](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-p3-semantic-correction-2026-10-09.json)。

最终7个源码/测试文件的read_revision全文件快照围栏核对通过；生产SHA尚未重新冻结，不把旧e6c7基线当当前P3版本。本轮P3 baseline元数据读取被平台拦截，未换入口重做，历史全清单未重新指纹对账。独立Astra仍不可用，Owner复核不冒认独立批准。本轮全部Job已获终态，无新增真实模型/媒体/Build，旧池不重开；未加载服务/提交/推送/发布，正式视频0/3。下一步为发布前核验与新具名真实Planning资格，不重新实施P3、不重跑旧失败批。下方保留此前时点。

## 2026-10-09：节点真实对照已执行，保留原表示；浅层首格原生失败停止

用户已确认新增4实际文字HTTP/900秒的节点对照。实际执行原表示1格、浅层1格，共2HTTP/Provider报告47240 tokens；浅层非成功终态后停止，后2格未提交。最后执行收尾距首个真实HTTP475.598秒，未重置原绝对截止或4HTTP总量；旧两批80HTTP池原SHA保持封存。本轮不是完整Development或成片验收。[具名结果](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-planning-node-contrast-2026-10-09.json)。

原表示A-details原run为ok/released；4613字节、slots为object、顶层完整、实际Schema PASS。新观测器此前依赖SSE [DONE]而在HTTP自然EOF/tool_calls时未导出摘要，首格按缺证据停止；原结果随后只读恢复，上游SHA仍记UNKNOWN，不补造或覆盖原测量。仅修评测器区分HTTP EOF与[DONE]并验证缺终态/半帧/冲突/终态后参数仍不完整，相关2 PASS；父账本封存，剩余3预冻结cell用新测量子清单绑定父SHA与同绝对截止，未重复首格。

浅层首格HTTP200/tool_calls、上游44783参数字节/1213片段摘要可用，但原生run error/released，原件读取为TOOL_REJECTED，仅保留STRUCTURED_EXECUTION_FAILED，具体云端或SDK原因仍UNKNOWN。不得将其归结成Schema失败或据此接入生产。当前决策：保留原A-details表示，浅层实验不接入；原表示单样本结构通过不代表可靠或语义通过。P3 necessity来源绑定纠错及未决/待供给分类仍未实施，旧selection中六个optional与两项unresolved没有被自动改正。

生产source仍`e6c7e125…9972b8`，220源码/302保护/142fixture不变，未改Runtime/模型、未加载服务、无commit/push/publish。两原run均released，新增媒体/Build0、正式视频0/3，实际现金账单UNKNOWN、原媒体占额¥15/累计¥30。以下为此前时点。

## 2026-10-09：边界方案已落盘，原生离线定位完成；真实诊断待新增额度

原Task已登记P0–P5执行方案。本轮没有继续补Prompt或改生产解码：原生SDK保存的A-details参数SHA与Easel原件一致，slots已是string；相同实际7-slot Schema的正确控制、未改坏原件、分片以及更大正确载荷共6个本地原生回放，捕获SHA一致，坏原件仍拒绝。旧Provider原SSE未保留，云端内部归因仍UNKNOWN。新评测证据只增加逐工具参数摘要，不存正文，不改变正式准入。

已在test-only producer实验中实现浅层等价表示，并验证不丢槽位/未决项、不改字段Schema、不接纳非法原件；相关合同回归4 PASS，尚未用于生产或真实模型。必要性修复和unresolved前置拒绝限制已离线复现；不能只修结构后宣称语义稳定。生产source仍`e6c7e125…9972b8`，220源码/302保护/142历史fixture保持，未换Runtime/模型、未加载服务、未推送/发布。本轮新增真实文字/媒体/Build均0，视频仍0/3。原两批总池仍关闭，下一步最多4次节点真实对照/900秒的建议额度需明确批准。[具名证据](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-planning-boundary-replay-2026-10-09.json)。

## 本轮连续开发停止：两批均封存，批次数授权已耗尽，尚未出片

当前source`e6c7e125ab66dc103a3f4fde6a986ce580ab5e174a14cb8812a550391c9972b8`，HEAD仍`df0d3a30`且工作树未提交。@1受影响回归304 PASS（含26定向），@2输入呈现/版本/恢复77 PASS；软件证据不转授真实能力。两批分别首例FAIL，后五例均未执行，总3实际文字HTTP/Provider报告67292 tokens；真实样本墙钟合计290秒（不含开发和软件测试），总账计295.238秒。已到2批上限，未满80HTTP不授权第三批。[具名终态汇总](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-intake-continuous-final.json)。

第二批@2的A-selection引用合法、BGM为1个且未重复旁白，但六个视觉候选全部optional，并把未采购素材列为unresolved；A-details将slots交成字符串，顶层缺unresolved，字符串内部亦非单个合法JSON。结构入口拒绝，B/Truth/repair未进入，不认领正式语义评分。没有手工解码/补项/升级required后认领PASS。来源问题没有在此例复现不代表长期稳定。

三个原run均ok/released，两项真实Job均exit2，原账本永久closed、保留FAIL，新增媒体/Build0，正式视频0/3。220生产文件自冻结不变、302保护现场/142fixture不变；线上未加载、无commit/push/publish。末次全局Gateway/配额刷新遭平台安全拦截，无新结果；最后成功预检0活动/0丢失/0审计、套餐99%/97%仅作此前时点。真实现金账单UNKNOWN，媒体占额仍¥15/累计¥30。后续应先用原件定位嵌套结构转字符串发生层，再独立处理required/未决语义；不得自动重开批次。

## 连续推进：第一真实批封存，声音输入呈现@2通过针对性验证

原新增池allocation1在source`f7d3ddc8…558a`首例FAIL：1真实HTTP/153.776657秒，A-selection完整但scope=`src_830-2051`不在允许集合；其数字与声音原文引用区间一致，另将程序旁白误作BGM。原run已释放、批永久关闭，后五例不执行。未进入details/B/Truth/Supply/Build，不把候选BGM存在认领成语义通过。

继续最小修复后，新`confirmed-planning-intake@2`在source`e6c7e125ab66dc103a3f4fde6a986ce580ab5e174a14cb8812a550391c9972b8`上77 PASS/0 FAIL/0 skip（172.987秒）。程序向A展开冻结声音原文并区分使用scope与出处区间；旧@1真实请求SHA逐字重建，原输入视图快照、输出Schema和非法scope拒绝不变。模型效果尚待第二独立真实批。具名证据[声音输入呈现软件](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-intake-audio-view-software.json)。新增池已用1/2批、实际1HTTP，剩余仅最后一批40HTTP/2700秒；媒体原占额不变，仍0/3视频，线上未加载。

## 连续开发续接：intake组合软件验证通过，准备独立真实资格批

本次原入口执行已获准，未绕过平台限制。`confirmed-planning-intake@1`在source `f7d3ddc805a089218ffa6e3f3b163d6b017e44b7fc49b233a043d8386479558a`上定向26 PASS（44.435秒），两个受影响模块完整回归304 PASS/0 FAIL/0 skip（688.871秒）；26包含于304，不相加。compileall及范围diff检查通过；源码/测试、302保护文件及142fixture运行后不变。旧1034全量不转授本版本。原失败只读重放精确产生6查询leaf和1确认BGM缺项target，无原件改写、无模型调用。[具名软件证据](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-intake-software.json)。

原80HTTP/5400秒/2批私有总账已独占建立，当前0分配。独立Astra接口未提供，记录当前Owner的代码/证据复核，不冒认独立意见。下一步同原主题/oracle及隔离M2.7候选，固定新清单并实时对账后仅执行第0例。线上未加载，新真实调用/媒体/Build仍0，视频0/3。下方平台阻塞及未验证是此前时点。

## 连续开发：query/BGM入口修复已接入，验证启动受平台安全拦截（2026-10-08）

用户已新增授权后续最多2个文字批、累计80实际HTTP/5400秒，每批40HTTP/2700秒；旧批永久FAIL，媒体累计¥30含历史占额不变。同Session另一续接已明确暂停并交接，本轮继续其query字段定位和JSON化补丁。当前`confirmed-planning-intake@1`已接入新请求的transport、selection Schema、消息、共享一次repair和verify；未标记@9及旧版本保留原入口策略。确认specs.music/mixed要求BGM，缺项由模型在同一次repair提交，程序不生成曲风/轨道/授权；B仍只复核视觉。

新增/扩展现有tests/test_semantic_planning.py的查询字段及确认音乐组合回归、旧行为和标记剥除保护。此前14PASS仅是中间代码，当前完整改动尚未跑完验证。尝试初始化新增私有总账并运行定向pytest的run_script被OpenAI安全检查拦截，未返回Job或执行结果；不得换工具绕过，不认领测试启动/通过或账本已建立。新真实文字批次、媒体、Build均未启动；0/3视频。当前为IMPLEMENTED_UNVERIFIED / PLATFORM_EXECUTION_BLOCKED，生产服务未加载，无commit/push/publish。

接续点：在平台允许执行后，先核被拦调用是否有任何执行记录，再完成原Task的私有总账绑定和组合定向验证；不重跑旧真实批、不复用历史成绩。用户授权已落盘，不重复申请同项预算；最终源码摘要和阶段通过证据尚待执行验证建立。

## @9真实资格首例FAIL，按原规则封批停止（2026-10-08）

接管完成缺失的软件收尾后，在同一source `cc5587a4…4f4e` 上固定新清单`dd184d52…9d3d11`并只执行第0例。沿用原隔离M2.7/65536/adaptive、三主题各两次、40实际HTTP/2700秒、文字仅套餐；线上默认模型与服务未改。**132.958秒、2次实际HTTP后FAIL/closed，后五例未执行。** A-selection完整799字节，wire合法，产生6个image候选；A-details完整6940字节，但每个视觉slot给出一条中文和一条英文query，违反现有三条不同英文词合同。

对未修改原件的离线复现显示：wire已定位六处query的pattern及数量错误；canonical的model_validator将错误挂在Need根，`structural_targets`因路径不足三层拒绝局部修复，最终报“A fault cannot be localized without replacing valid semantics”。repair未调用。A候选另无必需BGM；这是与查询结构独立的覆盖风险，B/Truth/正式独立语义评分均未进入，不能声称只修query就全链成立。[具名失败证据](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-source-view-real-failure.json)。

两个原run均HTTP200/tool_calls、ok/released，无观察到的截断或传输丢失；收尾Gateway active/lost/audit0，无新pending/unknown。源码220、保护302、fixture142及工具摘要保持。套餐窗口100%→99%、周97%→97%，Provider报告41467 tokens，实际账单UNKNOWN；新增媒体/Build0，原¥15/¥30占额不变。当前仅文档和独立诊断落盘，未修改生产代码、未加载服务、未推送/发布。Goal仍0/3；本批不得恢复或以剩余额度重试。下方“尚未启动”是此前软件收尾时点。

## 接管收尾：@9 软件验收已闭合，真实资格尚未启动（2026-10-08）

用户已明确恢复原稳定自主出片 Goal。接管核对 production source `cc5587a4f6379e541cdec442808166d2041369ea6e320d892fedf4e3e2bb4f4e`，220 生产文件、302 保护现场和142 fixture的集合与摘要完全一致。复用同源码run-053矩阵276 PASS，以及排序修复后4 PASS、六例冷进程回放6/6和30本地替身HTTP。只补缺失全量回归：**1034 passed / 5 existing skips，0失败，723.599秒**；65个Python测试文件及生产/保护/fixture运行后不变。

已补齐[具名软件汇总](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-source-view-software.json)与[交接收尾](acceptance/planning-input-view-handoff-2026-10-08.md)。接管复核为当前助手对@9源码与证据的核对，未冒称另行调用Astra。状态为 `SOFTWARE_ACCEPTED_REAL_UNPROVEN`；未修改生产代码、未提交/推送、未加载Web/Gateway、未调用真实模型/媒体/Build，正式视频仍0/3。下一步按原Task冻结一个独立@9真实资格批及实时预检；旧批FAIL/closed和累计费用账本不重开、不清零。下方“验证中”是此前时点。

## 当前实施：@9可逆输入视图已接入，组合验证进行中（2026-10-08）

经Astra前置CONTINUE，新Planning输入视图已接入同一两阶段流程，原文、来源资格及独立B职责保持；程序负责opaque来源映射、空目录表示、快照和details身份绑定。@8及以前按原合同恢复，不迁移旧产物。完整来源回建已覆盖99条来源的值/SHA/资格/scope/数量/顺序及Unicode、独立原文、非空continuity、无bound Voice路径，之前“尚未完整回建”是历史时点。

请求恢复与原件篡改10 PASS；本地原生Gateway两阶段5 HTTP/1 PASS。集成首次29 FAIL/26 PASS含旧外部夹具读取旧消息；夹具适配后暴露实际键顺序缺陷：JSON持久化排序改变Voice引用lineage摘要，合法恢复被拒绝。现已固定scope/Voice引用遍历顺序，并加入sort_keys持久化不变断言；正常Planning/Truth、冻结复制及完整来源4 PASS/93.61秒。初始失败JUnit保留，未改准入标准。完整矩阵、常规回归和六例冷进程回放进行中，尚未冻结验收。

新增真实调用0、未加载服务、历史FAIL不变，正式视频0/3。用户费用及持续实施授权保持：媒体Goal累计最多¥30、保守占额¥15，文字仅已购套餐；不重复询问同项授权。后续以本次组合证据与固定source复核决定真实验证，不把软件通过当成语义收益。

## 最新进展：输入合同风险已精确定位，离线视图样例完成（2026-10-08）

原@8消息与工具Schema精确重建且身份一致。已证实同包存在确认BGM要求与Mode optional默认、27物理行被三套scene/event/segment编号呈现、空continuity仍让模型填写，以及多处程序哈希上下文；这些与实际错选吻合，但全部语义错误的因果仍未被反事实验证。字幕/旁白作为image违背了原请求已有规则，不能靠删掉提示冲突认领解决。

按Astra MODIFY先做test-only引用codec和实际输入样例：82个kind/位置往返及错误映射保护1PASS，历史坏selection保持拒绝；原文与Mode不删改、默认资格不扩大。第二样例31.9KB，非生产、非模型收益证明；99条资格仅分组字段一致，完整source SHA/scope/order回建待补。Astra CONTINUE完整离线设计，接入新版本/恢复映射前仍需复核。细节及待办见[唯一Task](tasks/creator-autonomous-first-cut-2026-09-30.md#输入合同根因核查与有限离线设计2026-10-08)和[样例记录](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-source-view-design.json)。

生产source仍199fba42…01eaa、302保护文件不变；旧真实批FAIL/closed，新增真实HTTP0，未加载服务，正式视频0/3，目标未完成。

## 最新真实两阶段Planning：首例FAIL，停止真实重试（2026-10-08）

@8新批`970ccb4e…6464f`首例27.749秒/1实际文字HTTP，A-selection完整1732字节且原run成功释放，但非法非空continuity在程序shape的布尔Schema处理上触发AttributeError；details/B/repair/Truth/Supply未进入，后五例未执行，批永久FAIL/closed。原件另有必要BGM降optional、字幕/旁白作为image及下游资源未决问题，两阶段设计的真实收益仍未证实。[失败证据](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-staged-real-failure.json)。

Astra CONTINUE仅最小异常修复、真实路线STOP。布尔Schema形状检查现保留原坏值交原诊断与严格校验；修前原件1FAIL，修后codec/恢复9PASS＋连续内部修复后拒绝/重入1PASS，compileall/范围diffPASS。没有新增repair、删Need或改原结果；302旧现场保持。[局部软件证据](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-staged-bool-software.json)。未加载服务、未新增媒体费用；媒体占额¥15/¥30，正式视频0/3，Goal未完成。以下a2源完整软件验收保留为修复前版本证据，不代表当前补丁已跑全量或真实成功。

## A两阶段已接入代码，组合及冷进程软件验收通过（2026-10-08）

fresh Planning采用@8，两份模型原件与程序assembly分开持久化、重建及验证，旧@7以下按原合同恢复；共享repair及Material语义不变。三崩溃切点、UNKNOWN恢复、篡改和正常Owner/Truth/声音/冻结复制49 PASS；原生Gateway五个本地HTTP通过。run-052完整矩阵276 PASS且302现场/139fixture保持；全量1029 PASS/5既有skip，115技能/compileall/范围diff通过。初次旧外部fixture未适配产生的32 FAIL保留，修订只涉及固定响应表示。[证据](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-staged-software.json)。

生产source已固定为`a2a1818627b816fd030b1c74ae3cc56515d5b454ee1cd72729b49b423db71bfc`并归档完整源码清单，HEAD仍df0d3a30，未提交、未加载服务。六例各新进程原生Planning/Truth回放6/6 PASS，408.98秒、30本地HTTP，重入0新发并封批；首次测试清单选错造成0HTTP拒绝，失败保留后用既有正确输入重跑。Truth逻辑调用对应多次HTTP，原“42次”估算不是HTTP上界，仍由实际Proxy账本硬限制。Astra最终CONTINUE，软件验收状态SOFTWARE_ACCEPTED_REAL_UNPROVEN，可准备新的独立真实清单；不认领模型效果。真实模型/素材/Build新增0，正式视频0/3，Goal未完成；下方原型未接入为先前时点。

## A两阶段候选完成有限离线设计，尚未接入生产（2026-10-08）

已在[原Task](tasks/creator-autonomous-first-cut-2026-09-30.md#a-两阶段候选有限离线设计与后续实现边界2026-10-08)记录selection→程序固定slot→模态details→原canonical/B/共享repair的候选方案。复用109项合法往返、原135行矩阵，14项新增设计边界和两条真实内部修复集成；最终5 PASS/17.70秒，历史失败保持，原型测试中一次默认值比较错误的JUnit保留。生产source复核仍`d24bec047798d3b1f9a80abc05235f1c02f99504fb864a0a820931faf2fb9384`，没有生产实现、服务加载或真实模型调用。[证据](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-staged-producer-design.json)。

Astra初审要求区分身份拒绝和局部业务诊断；修订及现有集成通过后，最终CONTINUE仅限软件实施。版本化两请求恢复及原件重放仍为必验项，真实两请求生命周期尚未实现。每Planning增加一次请求，六例在一次B/共享repair/重审/Truth修复情况下42次，不能照搬已关闭的40次清单。模型语义改善尚无证据；M3/M2.7批保持FAIL/closed，Supply/生成/Build新增0、正式视频0/3、Goal未完成。下一步限于Task所列机制的离线软件实现与复核，既有费用授权不重复询问。

## M2.7 真实首例 FAIL，当前真实验证路线停止（2026-10-08）

已执行用户授权的`7b9b15b6…36088`批次：48.619秒、1实际文字HTTP，实际模型M2.7/65536/adaptive，HTTP200/tool_calls、原run ok/released，完整7893字节参数。15个Need含6个禁止的重复Voice、6个视觉Need、1个BGM及2个纯后期Image；23处wire错误，另有把镜头运动/混音复制为素材条件及scope错绑。正式A拒绝且不可安全局部修复，B/repair/Truth均0，后五例未执行，批永久FAIL/closed。未进入Supply、生成或Build，工程介入0、正式视频0/3。[具名结果](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-m27-qualification-real-failure.json)。

原件已新增永久fixture，现有结构负例回归1PASS/0.55秒。生产source仍`d24bec…9384`，302现场及冻结工具保持；媒体新增0、全Goal保守占额¥15/¥30，文字报告22449 tokens，结束套餐99%/周97%，实际账单UNKNOWN。未重启或切换线上模型。

精确A正文重建SHA与journal一致，正文明确禁止重复Voice，实际Schema也排除Voice；未发现已保存Skill记录给出相反指令。SQLite副本审计：原会话唯一工具为submit_semantic_plan，技能目录无Hypit及Voice/MaterialNeed专门指令；系统prompt只保存长度20165及hash、无全文，因此不能宣称完全排除系统上下文冲突。混排分镜及通用bootstrap存在复制诱因/噪音，但其因果效果未证实。

Astra STOP当前真实试错路线：两个套餐候选与现有单次A合同组合均未取得合格证据，目前无具名可复现的最小生产补丁。不是费用授权不足，不再要求追加同模式模型批次；若继续研发，应先重审A的任务粒度及程序/模型分工，形成架构方案和离线证据，不能暗中扩repair、删需求或放宽Material准入。当前稳定自主出片目标未完成。以下“已启动”为之前时点。

## M2.7 新固定批已授权并启动（2026-10-08）

用户“额度按照推荐的授权，无需再次确认”已绑定`7b9b15b6…36088`、40实际文字HTTP/2700秒、三主题各两次、仅原套餐、首FAIL/UNKNOWN封批；无需重复申请该项授权。启动实时预检PASS：406份Creation记录、11旧Owner、unknown/pending/submitting及活动0，Gateway active/lost/audit0，固定source/Runtime/工具/302保护文件一致，套餐窗口99%/周97%。开始第0例完整Planning，尚无真实结果；Supply/媒体/Build均禁止，旧M3批FAIL保持。以下待授权为此前时点。

## M2.7 套餐内候选离线核验通过；新真实批待授权（2026-10-08）

同一执行器@2候选已完成：M2.7原生A/B/共享repair/重审4本地HTTP通过；六例冷进程Owner→Planning→Truth→正式持久化→Supply前切点6/6 PASS，24本地HTTP/299.32秒，完成后重入0新发；旧M3 @1六例兼容6/6 PASS，24本地HTTP/297.58秒。5项保护PASS、compileall及本次范围diff PASS；全树两处无关旧文档EOF空行仍保留。首次测试命令传错无probes的清单造成零调用setup FAIL，原JUnit保留，正确清单回归通过。[具名准备证据](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-m27-qualification-prepared.json)。

新独立清单`7b9b15b61939883300e74ad3f73149ee9be8d85eb04b3ac915c67322a6336088`已冻结六个隔离载体及工具原件。仅M2.7文本Planning、65536/adaptive、40实际HTTP/2700秒；首FAIL/UNKNOWN封批。Astra最终CONTINUE，尚未获得该新批授权，实际模型调用0；不使用旧ec14剩余额度。生产source`d24bec…9384`、302保护文件保持，未切生产模型/重启服务/采购/Build。真实语义未验证，正式视频仍0/3、Goal未完成。

## 独立 Planning 批真实 FAIL；仅继续套餐内替代接入的离线核验（2026-10-08）

清单`ec14e915…de99`第0例已永久FAIL/closed：84.333秒、1次实际HTTP，M3实际收到131072/adaptive，HTTP200、finish=tool_calls、原run ok/released；完整2229字节工具结果有10个额外顶层字段，只表达首个视觉需求，其余五个场景及正式BGM Need缺失。正式合同拒绝，不能通过删字段、搬动item或补写需求放行。B/repair/Truth/Supply/生成/Build均0，后五例未执行；不是本次已证实的输出截断。原始模型XML及在线parser不可见，不能进一步断言是哪一方造成字段错位。[具名失败记录](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-qualification-real-failure.json)。

原件已永久加入fixture，原负例与独立合法parser对照1PASS；生产source仍`d24bec…9384`，302保护文件保持，未加载服务。正式视频0/3、媒体新增0、全Goal保守占额¥15/¥30，文字实际账单UNKNOWN。Astra STOP当前配置真实重试；无证据支持再改生产合同或扩大repair。

只读官方套餐/API及模型元数据核查：M2.7在套餐支持列表且元数据200；M3.1 Flash Preview所查接口404。M2.7仅为候选，未实际生成、未证明任务成功。继续原Task内隔离Gateway/Proxy离线回放，先验证纯文本Planning的A/B/repair/Truth、参数与请求身份；Material/Quality视觉配置保持。旧批不重开，新真实候选批尚未授权。以下“已启动/尚无终态”为此前过程，不能覆盖本段最终结果。

## 修正版独立 Planning 批已授权并启动（2026-10-08）

用户“授权并且执行目标”已绑定清单`ec14e915…de99`，40实际文字HTTP/2700秒、仅已购套餐、首FAIL/UNKNOWN封批。实时预检PASS：400份Creation记录、11旧Owner无unknown/pending/submitting或活动，Gateway active/lost/audit0，源码/工具/Runtime/302保护文件一致；套餐99%/周97%。第0例完整A/B/Truth已启动，尚无终态结论，不进入Supply或媒体/Build，正式视频0/3。下方待授权描述为历史准备时点。

## 冷启动评测器修复完成，新固定批次待授权（2026-10-08）

已将原生资格集成改为冻结及每个运行分别新Python解释器，未修版精确复现0HTTP误拒；修复版六例PASS（304.78秒/24本地HTTP），保护5PASS（16.94秒），禁止生成调用不放宽。修复仅测试评测器，生产source仍`d24bec…9384`、302保护文件保持；compileall/diff及Astra最终CONTINUE。[前后证据](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-qualification-cold-start-software.json)。

新清单`ec14e915…de99`（qualification-cold-v2）已零调用冻结六载体；仍为三主题各两次、131072/adaptive、40HTTP/2700秒、首FAIL或UNKNOWN封批。旧`843fe2b4…`保留0HTTP/FAIL/closed；新固定批尚待明确授权。实际模型未评测、生产作品/Supply/媒体/Build均0，正式视频0/3。当前Goal不具备完成证据。

## 独立批第0例零提交 FAIL：评测器冷启动缺口已复现（2026-10-08）

已获用户授权的清单`843fe2b4…8992e4`在第0例0.607秒停止，实际模型HTTP0、无agent run；trace把`easel.integrations.material_generation:<module>`首次加载误判为下游生成。批次永久FAIL/closed，后五例未执行，不将其算作模型能力失败。生产作品/Supply/媒体/Build0、正式视频0/3；生产source和302保护文件未变。[失败记录](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-qualification-cold-start-failure.json)。

根因是已有原生集成在同一Python进程内冻结并执行，预加载模块掩盖真实CLI的分进程启动差异。将同一测试改为冻结及每例各新Python进程后，未修代码精确复现同一错误（7.68秒、0HTTP）。最小修复仅评测器在trace前加载两个已允许的纯授权读取函数，禁止调用判定不变；生产/Prompt/Schema/额度未改。该段为验证开始时点；最终冷进程六例及保护结果见顶部。

## 独立 Planning 六例已授权并启动（2026-10-08）

用户已批准清单`843fe2b4…8992e4`对应的新固定批次，40实际文字HTTP/2700秒、仅套餐、首FAIL永久关闭。启动对账PASS：394份Creation记录无unknown/pending/submitting，11旧Owner无活动，Gateway active/lost/audit均0；冻结source、执行器、Runtime及302保护文件一致，官方套餐窗口99%/周97%。临时预检曾因脱敏函数遮盖SHA指纹零提交拒绝；内存核对证实凭证未变，错误原件保留，按既有受保护指纹写入后PASS。

现第0例完整A/B/Truth启动，未取得终态或语义结论；不推进Supply/素材/Build。历史失败保留，正式自主视频仍0/3。下方“待授权”为本次明确授权前状态。

## 下一独立 Planning 批已准备：尚未启动真实调用（2026-10-08）

沿用唯一Task和执行器，新增三个冻结开发主题各两次的完整A/B/Truth qualification模式；候选仅隔离MiniMax-M3的131072/adaptive，线上配置保持。实际原生Gateway＋本地Provider六例PASS（24本地HTTP、305.82秒），候选repair和旧contrast原生2PASS，参数/停止保护5PASS；compileall/diff、Astra冻结复核CONTINUE。没有新增生产源码改动，source仍`d24bec…9384`；302历史文件保持，旧真实四格FAIL/closed不变。

清单SHA`843fe2b4…8992e4`已冻结六个隔离载体；新批上限40实际文字HTTP/2700秒，首个合同/独立语义/运行保护失败永久关闭。当前实际调用0、生产新作品0、媒体费用新增0、正式视频0/3，尚缺这一独立新批的具名授权与实时启动对账。软件替身结果不代表模型或真实Preparation能力；样本一份真实冻结Preparation、两份明确人工派生对照。[实施细节](tasks/creator-autonomous-first-cut-2026-09-30.md)、[脱敏准备记录](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-qualification-prepared.json)。

## 最新软件批：B 所选原文绑定 @7 已实现，真实目标未完成（2026-10-08）

生产候选source `d24bec047798d3b1f9a80abc05235f1c02f99504fb864a0a820931faf2fb9384`；新B题明确绑定选中原文/位置/SHA，global引用同批完整evidence，旧@6及更早按持久版本保留原问题与恢复。未改A/Material合同，不机械决定语义。run-051为269PASS，最终常规1019PASS/5既有skip，115技能/compileall/范围diff通过，302保护文件和135fixture保持。AstraCONTINUE；未提交、未加载服务、无新真实调用。详细实施及局部修正见[原Task](tasks/creator-autonomous-first-cut-2026-09-30.md)。

真实四格仍3HTTP后FAIL/STOP，第四格未执行，正式自主视频0/3。源码修复不能冒认Planning恢复或MATERIAL_READY；下一次真实能力验证须使用独立冻结批次，旧账本不重开。下方较早状态保留为过程记录。


## 最新：四格真实诊断 FAIL/STOP，已定位容量与目录表达问题（2026-10-08）

按[唯一Task整体方案](tasks/creator-autonomous-first-cut-2026-09-30.md)先文档、执行器验证与Astra复核，再执行固定四格。current/disabled完整结果合同拒绝；union/disabled wire合法但正式unresolved与语义失败；current/adaptive Provider length、completion8192、工具参数0，原run失败并释放；第四格按约定未执行。共3真实HTTP/340.518秒/Provider报告78646tokens，账本永久关闭，不能补格或恢复计分。生产作品/Supply/媒体/Build0，正式视频0/3；新增媒体费用0、文字仅套餐、实际账单UNKNOWN。

原日志只记录旧max_tokens，不能推断没有输出上限。同版本原生离线回放确认max_completion_tokens8192；诊断工具已补两字段的类型/存在性/值与冲突保护，5PASS及原生runner1PASS（新真实调用0）。另确认目录把27非空行复制为三类编号，模型按六分镜选scope导致错绑；下一步仅离线明确输出配置和来源目录版本化最小方案，不默认union或扩大repair。生产source仍b04cc840…57353，302现场文件保持，服务未加载新版本，所有历史FAIL保留。[具名脱敏结果](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-four-cell-diagnostic.json)。下方“尚未调用/准备启动”为较早过程记录。


## 当前 Goal：三个全新主题自主视频交付（2026-10-08，进行中）

**本次执行已获授权，先文档后执行。** 用户明确确认4组/4HTTP/15分钟诊断，并要求先整体方案、确定细节、写文档再执行；已在[原Task统一执行入口](tasks/creator-autonomous-first-cut-2026-09-30.md#本次整体方案与实施细节用户确认后连续执行2026-10-08)落盘P0–P5顺序与具体保护。原稳定自主出片Goal已继续设定；当前P1测试执行器修改收尾，本轮真实HTTP0、生产新作品0、无服务加载。以下“待授权”为此次明确授权前的历史状态。

**最新追加调查：根因报告与离线模态 union 实验完成，未选入生产；真实接入能力仍阻断。** 本次对照官方 MiniMax/Pydantic AI/SGLang 资料，区分“模型输出合同违约”与尚未证实的 Schema 复杂度、推理开关影响。最终实验保留原 Condition/repair，135 项表示、混合列表、默认值和拒绝保护检查 PASS；完整 Schema 反而增大，不能认领模型质量收益。Astra 要求暂缓生产接入，Main 采纳。生产 source `b04cc840…857353`、302 正式文件/133 原fixture/193开发记录保持；本次实际模型 HTTP 0、费用0，无生产代码、Prompt、服务变更。建议一次新授权的4组 Schema×thinking 固定诊断实验，最多4 HTTP/15分钟，仅套餐，无生产作品或材料副作用；未授权、未执行，不重开旧批。[根因、已执行证据与具体后续方案](tasks/creator-autonomous-first-cut-2026-09-30.md#当前根因与可执行收敛方案先判定-planning-接入能力2026-10-08)。

**最新收敛执行：软件交付完成；单次真实文字批首项 A FAIL / 永久 STOP，稳定自主出片 Goal 未完成，正式仍0/3。** 用户授权的完整范围为两件离线成果→4探针及6例Planning（共享最多40实际HTTP/45分钟）→最多1件追加开发→同固定版3件正式视频；媒体累计¥30（历史占额¥15，新增开发¥3，正式各¥4），文字仅套餐，无付费回退，不发布。历史3件开发FAIL不恢复。当前新增开发、完整视频E2E均NOT_EXECUTED；本批其余3探针和6评测未执行，不借剩余调用额开启第二批。

软件成果：最后HTTP出口计数覆盖A/B/repair、普通Truth、框架续轮及报告修复，UNKNOWN不释放，阶段结束核验deadline，任何FAIL永久关闭；冻结Preparation原字节回放，仅新Creation/Attempt测试身份，真实评测停Supply前。run-049为269PASS/0FAIL/0GAP/0未执行，常规1013PASS/5既有skip，HTTP/Authoring22PASS、原生Gateway9PASS；115技能、compileall及范围diff通过，Astra冻结前CONTINUE。新版proposal@3/vNext@6经真实内部Owner/Material/Authoring到Hypit0.2.7免费本地Build及输出绑定Quality的隔离软件链实际产出15秒1080×1920 H264/AAC MP4；外部模型、TTS/ASR/视觉判断是固定fixture，required Voice+optional visual、不含BGM，不能冒认真实自主交付或全面素材能力。[软件证据](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-convergence-software.json)。

真实固定source `b04cc840189874cdd5d9e29b103af24cd1737948bc53de287866fee76b857353`，HEAD `df0d3a30…`未含工作树修改，隔离候选Runtime `0759643a…4d7e6`；生产服务未加载本候选。第一次零提交Gateway预检因Node --import空格路径退出；原冻结稿/空账本关闭保留。仅测试工具改file URI，带空格路径原生Gateway离线PASS后新冻结v2，语义输入、期望、生产source/Runtime未变。此后授权的首个真实A采用开发3原proposal和四冻结输入，以新隔离身份运行163.506秒、1次实际HTTP、0重发、工程介入0；HTTP200/provider tool_calls，native toolUse、原run ok/released，完整参数13987字节/SHA `3cb39372…46463`无损读回。Provider报告prompt19928/completion6355/total26283 tokens，实际请求max_tokens缺席（不能将配置8192冒认实际发送上限）；没有观察到本次截断或终态拒绝，也不能倒算Dev3旧UNKNOWN根因。

本次已确认是完整A合同违约：6个被禁止的模型Voice Need（已存在program-owned Voice）、82处meaning=allowed违反enum、6个voice source_seconds和BGM sound_character混用。工具调用成功不代表参数被Provider强制Schema；无证据支持通过nullable/数组兼容删除这些义务。Astra STOP。公开XML模板/parser在3个独立合法控制上未复现本次具体异常；optional null省略按既有Schema默认值恢复等价，online parser及原XML仍未知。原A与完整合同永久fixture原字节保留，离线结构合同3PASS保护真实负例、拒绝超出已有repair容量及合法对照；早期测试工具两份失败JUnit也保留。当前没有被证实的最小生产补丁，不能再堆Prompt、扩repair或继续真实试错。后续接入/语义任务拆分须先取得具体合同影响及离线可行证据，再按单批授权边界启动新真实批。

媒体新增费用¥0、保守累计占额仍¥15/¥30；文字实际套餐账单不可得，前97%/周97%、结束窗口重置100%/周97%，不从百分比推算或退款费用。Supply/生成/Build均0、正常生产新作品0。302正式现场、133原fixture、193开发原件全部SHA保持；另新增2份永久业务负例fixture。首原请求已终态并释放，批次已封存。[具名真实失败与固定信息](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-convergence-real-batch.json)。

以下“停止、未授权、未实施”是本轮新授权前的历史时点，不覆盖以上最新状态。

**最新：完整开发3/3 FAIL；开发名额已用尽，正式验收0/3，无可播放MP4。** 第三个正常新作品 `cr_645dc02aa63a49b785753916e9d028c4` / `fa_fcda420330b2c182c5c360b51b6b257c` 在固定source `e2451702…85da52`、Runtime `12b0d561…6c19c5`上运行，确认至Delivery失败385.548秒，Preparation209.610秒成功，Planning A162.291秒后原生保护层报`STRUCTURED_TERMINAL_REJECTED`。一次A Provider提交后3次框架尝试及3次本地重入未重复提交；原run已error/released，B/repair/Truth/Supply/媒体/Authoring/Build/Quality均0，工程介入0。Preparation为16个assistant响应、22个工具调用；HTTP提交数与实际token/套餐账单未知，不能把1个RPC或零usage当作1次模型调用或零费用。原A返回及provider finish reason在保护层拒绝前未留存，持久轨迹只保留首个分类，后续尝试将最终会话错误覆盖成`STRUCTURED_EXECUTION_FAILED`；具体模型/transport根因未确认，不能猜测并放宽终态合同。现场/固定版本/旧FAIL和fixture已对账封存，Gateway active/lost/audit及unknown/pending/submitting均0。累计媒体保守占额¥15/¥30、已知实际媒体费用0。停止新作品真实重试，不以正式验收名额继续开发；Goal未完成，后续只能离线补齐拒绝诊断证据链。[开发3失败证据](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-full-development3-failure.json)。

已形成[同一Task内的收敛方案](tasks/creator-autonomous-first-cut-2026-09-30.md#收敛方案真实接入能力先闭合再回到完整自主视频2026-10-08待实施)。首轮Astra认可方案约束后，用户要求核实实际可行性；源码复核确认旧Eval按RPC而非HTTP计数、实际创建隔离Creation并执行Preparation、旧三主题回放使用旧Planning和Hypit替身。第二轮Astra为MODIFY，方案已据此修订为先交付两个离线成果：冻结Preparation回放/共同HTTP守卫/早期诊断，以及proposal@3/vNext@6到真实免费Hypit构建和输出Quality的连续场景。完成后才考虑4个文字探针与6例Planning评测；首探针用开发3语义输入及实际Schema以新身份定位当前blocker。上述新能力未实施，真实文字批次和新增开发名额均未授权；本轮仅调查和文档修订，Goal保持BLOCKED，无生产代码、服务或真实运行变化。

以下联合软件与加载叙述为开发3之前的基线；“尚未启动”和两个FAIL是历史时点，不能覆盖上述最终结果。

开发3后的诊断软件已离线收尾，Astra前后CONTINUE：首个完整候选拒绝的封闭元数据原子发布并保留，后错/并发/写失败不改原拒绝或RESERVED，接受谓词与repair不变。相关pytest58PASS、原生transport11PASS、隔离Gateway3PASS及A/B/repair→persist/verify连续集成PASS；115skills、compileall、Node语法和范围diff通过，未新认领全量通过。候选source `ba3426f0…79f6a2` / Runtime `0759643a…4d7e6`只在隔离安装验证，生产Runtime未升级、服务未重启、没有新增真实作品或模型调用。补丁不能补回开发3原响应；具体真实根因仍UNKNOWN，3/3开发上限及正式0/3保持。[诊断软件证据](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-rejection-diagnostics-software.json)。

**联合软件验收通过并已加载，第3个开发作品尚未启动。** 原子画幅、确认预置身份/程序Voice/独立Truth/正式记录与Gate保护、Truth有效拒绝锁定及既有checkpoint合法继承已完成。run-048完整矩阵269PASS/0FAIL/0GAP/0未执行，常规1012PASS/5既有skip，原生Gateway→Harness→persist/verify全部7PASS；115技能/compileall/本Goal范围diff通过，前端未变沿用原lint/build。287现场/132fixture与两件失败额外34文件保持，旧run-046和常规失败JUnit均保留。全仓diff另有两处历史文档EOF空行，不能写成全仓PASS。Astra最终CONTINUE，冻结工作树source `e2451702c3d5fdb112e93bae8d03280cd8dcb9ae2cf2ad4281f47dc55985da52`；HEAD `df0d3a30…`不含未提交修改，Runtime `12b0d561…6c19c5`保持。Web21631/Gateway21609于11:43:30加载，HTTP200、依赖及进程身份核验通过；357作品/10旧Owner无unknown/pending/submitting/活动任务，实际raw-stream停服后138728字节精确备份SHA293a5523…ac42d。套餐98%/周97%，媒体保守占额¥10/¥30。真实成绩仍两个开发FAIL、正式0/3、MP4零。[联合软件证据](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-joint-software.json)。

**最新结果：完整开发第2/3作品 FAIL，真实重试停止，Goal 继续离线修复。** 新作品 `cr_a4e881bdb3cd437baeb53c8a929e8c38` / `fa_92fa1595e794621cb276dca79188bf11` 从正常确认至终态678.473秒；Preparation与A各1原RPC、均ok/released。A完整8545字节（SHA `dccd1b54…88788`），数组与布尔传输正常，但6个image同时选择match_output与native_ratio=9:16，正式合同拒绝；两个声音资源unresolved保留。B/repair/Truth/Supply/媒体/Build/Quality均0、工程介入0、无MP4。Preparation原会话14个assistant响应/17个工具调用，不能把1个RPC冒认1次模型调用，HTTP提交数未知。旧现场、固定source与Runtime、开发1失败原件保持；本作品完整失败现场和原A已封存为永久fixture。[失败证据](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-full-development2-failure.json)。

累计两个完整开发FAIL、正式视频0/3；媒体保守占额¥10/¥30、已确认实际媒体费用0，文字走套餐而实际账单未知。Astra结论STOP仅限制真实重试：先统一离线核对画幅原子选择、声音语义身份与执行资源责任。只读证据确认BGM具体曲目可在Material供给后绑定；当前配置预置音色为male-qn-qingse，但开发2已确认女声要求，现有链没有正式语义身份→preset resolver，不能删除unresolved或任意使用配置音色放行。以下加载与开始描述保留为历史过程，最新状态以本段为准。

**最新统一授权与真实执行：** 用户明确解除旧两轮阶段审批限制；新开发作品最多3个，打通后同固定版另起3主题正式视频验收，累计¥30图片/预置旁白、文字仅套餐、Hypit仅免费本地构建，不发布。之前单次Planning-only追加修改已归档撤回，原两轮FAIL与5请求账本不动。source `4d1a5510…356c68`/Runtime `12b0d561…6c19c5` 已安全加载，Web53245/Gateway53243及HTTP200、实际进程与指纹对账；实际原始流1,729,380字节精确归档，SHA206bc116…5d28022，355旧作品无unknown/pending/submitting、Gateway空闲，套餐窗口100%/周97%。[加载证据](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-full-service-loaded.json)。

开发第1/3作品 `cr_37a22ea5ef6b4845ba0f1d99a26c78b7` / `fa_12ed8b2fffe0fadfc96ad44660710c0a` 已正式 **FAIL**：正常确认前修订通过，Preparation成功，A完整22137字节原工具结果包含conditions/queries的item包装，正式结构拒绝；147.578秒、Preparation/A各1原RPC、3次本地重入未重发A，B/repair/Truth/Supply/媒体/Build均0，工程介入0，媒体占额¥5/已确认费用0。原件、Preparation会话、失败与累计账本已私有封存；旧257现场仅正常新会话绑定追加，排除该一条后旧绑定精确同SHA，其余旧文件均未变。正式自主视频仍0/3，不恢复计分。

离线原始官方M3 XML模板与公开SGLang parser复现同机制：带$ref的合法混合Schema解析为item包装/数值及布尔字符串，展开引用及明确可空表示可无损恢复。**在线服务使用同parser未证实**，真实A另有素材/后期和未决语义错误，不能由结构修复宣称全部解决。Planning wire投影@5已实施（canonical合同不变），原@4/@3/@2按旧合同恢复；run-043矩阵230PASS、全量973PASS/5既有skip、原生Gateway→Harness五场景5PASS，115技能/compileall/范围diff通过，272正式现场/130fixture保持。Astra发现并闭合enum/not排除null的投影反例；run-042的fixture保护FAIL保留（新增公开.py原件的compileall缓存），改为原字节.py.txt后对账通过。source6f28fbd7…50c5a、Runtime12b0d561…6c19c5不变，工作树未提交，pyproject依赖另行固定。已获Astra最终CONTINUE并安全加载：Web8440/Gateway8438、HTTP200、source/Runtime/依赖一致；加载前356作品/9Owner无活动或unknown/pending/submitting，套餐窗口99%/周97%。实际raw-stream194581字节按原路径精确备份，272正式文件/17个失败Attempt文件/130fixture保持。正常开发第2个新作品已开始方案请求；[软件验收](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-wire-software.json)。

用户已授权必要修复与真实新作品验证，图片/预置旁白全 Goal 累计 ¥30，文字仅已购套餐。沿用[唯一自主首版 Task 新授权章节](tasks/creator-autonomous-first-cut-2026-09-30.md#连续自主出片-goal2026-10-08-用户追加授权进行中)，完成条件为同一固定版本三个全新正常主题连续 `first_cut_ready`、正式素材覆盖100%、实际MP4/Quality绑定、工程介入0；不发布。原 Material-only / A-only 批次的 FAIL 和停止结论均保留。

只读核查已确认 `serve_delivery` / `_execute_creation_delivery` 是已有唯一主链，默认完整 Creation 可从 Material 继续到 Authoring/Build/Quality；`endpoint=MATERIAL_READY` 是显式旧范围终点。当前尚无三个新作品真实成功证据。Astra前置MODIFY四项已纳入Task，开始隔离实现：新增动态机械Schema（冻结目录/既有模态互斥），保留正式消费者校验；新增Runtime兼容支持组件的安全JSON捕获与原子提交占额。修前7项对照为1PASS/6FAIL；新增Schema对照通过，完整semantic测试197PASS；原生支持组件的8MiB/转义与敏感键/并发抢占/恢复拒绝测试1PASS。

Runtime连接与恢复边界已在**隔离安装副本**实施：受限agent RPC→原client-tools→实际managed SDK/fetch→完整工具终态→原生transcript→Easel只读捕获；本机Provider fetch替身，未调用真实模型。原生10个transport场景PASS，实际隔离Gateway完整8MiB恢复PASS，原tool-call ID/字节SHA/Schema一致；每请求重试不增加Provider fetch。增加原session协议绑定，丢失恢复参数或更换run不能退回普通执行。Planning/guard相关202PASS，Preparation/Web相关77PASS；具名证据在[carrier-audit目录](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-gateway-capture.json)。

只读恢复首次创建SQLite SHM与空WAL，数据库与既有WAL字节不变，已保存全目录严格比较失败及具体修正依据，不能宣称整个目录未变。新协议`planning-result-v3`已接入调用/结果适配，正常新Planning默认已接入@3 journal/frozen checkpoint，schema/Runtime身份进入请求与正式Plan identity；旧@2 pending继续v2且不刷新额度。22入口集成、run-035矩阵201PASS及943全量/5既有skip通过，257现场/117fixture保持。冻结前Astra发现HTTP重定向和debug capture保护缺口，已隔离修复并验证一次POST及敏感候选不落盘；转义8MiB暴露原SSE16MiB缓冲不足，隔离修复为新协议64MiB wire（arguments仍8MiB）后完整原tool ID/SHA恢复PASS。最终run-036为201PASS、全量943PASS/5既有skip，115技能/compileall通过，Astra CONTINUE。固定source `761d28ae…dc6d34d`，HEAD `df0d3a30`仍为历史提交，当前测试变更尚未提交；以完整工作树文件清单另行固定，不冒认已在HEAD中。正式服务已安全加载：Web39895/Gateway39893，HTTP200；8旧Owner无有效操作、343旧作品扫描无pending/submitting/unknown，Gateway active/lost0。原raw-stream2,456,422字节按实际路径停服后归档并核SHA，历史现场/fixture保持。窗口套餐99%/周97%；Development round1首项已完成并FAIL，详见下节；Supply/媒体/Build0。正式安装/服务现已加载固定补丁，首轮真实Planning Development已FAIL封存；本Goal尚未取得真实Material或完整视频，媒体新增费用0，Goal保持进行中。

### 当前真实结果：Development round1 FAIL（保留）

d01首项63.909秒，3个原RPC（Preparation/A/B）全部终态并释放；A v3工具成功1548字节，B v2文本3256字节漏题7，正式拒绝，无unknown题号。Supply/媒体/Build0、工程介入0。Scout独立核对又确认B的源/成片授权归因及原文出处有误，因此不能补ID就算通过。真实原件已保存为tests/fixtures/planning-vnext-development-2026-10-08/autonomous-round1-*，具名[失败摘要](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-development-round1-failure.json)。

B/repair固定槽位与冻结支持资格已完成离线修复：新@4合同，原文quote/来源角色校验；合法引用仍不保证完整语义。旧@2/@3保持原合同与修复额度，升级Runtime后旧身份禁止首次提交，仅恢复已有原run。run-038矩阵221PASS、全量959PASS/5既有skip，115技能/compileall/范围diff通过；257历史现场/122fixture及测试工具指纹不变。隔离Gateway的B与repair各一次外部替身请求、原tool ID/SHA无损恢复，Astra CONTINUE。固定工作树source `73e63a66…544ea6`，HEAD仍`df0d3a30`，未提交。安全加载预检349作品、8旧Owner无活动，unknown/pending/submitting及Gateway活动0，套餐98%/周97%；服务已核验Web42755/Gateway42753及HTTP200，完整source/Runtime一致；实际raw-stream87,200字节停服后精确归档。Development round2六个新隔离确认样本已冻结，开始首项真实验证；同一累计账本保持round1三次请求及FAIL。正式自主视频仍0/3。

### 最新真实结果：Development round2 FAIL，两轮真实提交停止

首项70.847秒：Preparation成功，A完整工具参数2600字节但conditions/queries类型错误；原生client-tool业务Schema验证生成工具错误并尝试续轮，原请求提交保护阻止额外Provider提交，最终A原run ERROR。不得从较早候选倒算成功。B/repair/Truth未进入，Supply/媒体/Build0、工程介入0；两个原RPC均已释放。保留[失败证据](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-development-round2-failure.json)，两轮总5个RPC、媒体累计¥0，套餐98%/周97%，实际账单未知。Gateway active/lost/audit0；固定代码、257现场及既有fixture未变，新增真实A反例；完整原始流1,729,380字节已归档。

已获Astra CONTINUE的下一步仅离线：将唯一structured carrier的本地执行合同改为安全JSON对象，实际Provider仍完整精确业务Schema；完整终态后由Harness正式校验/拒绝/共享一次repair。补真实Gateway Schema非法候选生命周期回放及普通工具保护，不放宽业务合同。两轮Development额度耗尽，不新增真实提交、不重置账本；完成软件修订后再报告下一次真实验证所需范围。此前round2进行中描述为历史过程，最终三作品仍0/3。

### 候选接收职责修正：软件通过，尚未加载 / 不启动第三轮

仅唯一structured clientTool使用安全对象执行参数，实际Provider完整业务Schema/hash不变；业务校验回归Harness。真实round2原件在原生Gateway修前复现error、修后一次POST成功运输原2600字节，Harness仍正式REJECT。现有Harness与原生Gateway连续3场景PASS（原件拒绝、可定位repair成功、repair非法停止）；普通工具原生参数验证保持。

run-039矩阵224PASS、全量962PASS/5既有skip、115技能/compileall/范围diffPASS，Astra CONTINUE；257现场/123fixture及源码/测试工具指纹保持。新source `bbf3e615…9c9c0a2`仅离线，当前服务仍为`73e63a66…544ea6`。两轮真实FAIL不改，未加载新Runtime、未启动第三轮；自主首版0/3、媒体累计¥0。软件记录见[候选接收验收](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-admission-software.json)。

### ¥30 图片/预置旁白授权保护：软件通过，未加载

现有方案确认支持明确模态子集，新 grant 版本与子集进入请求指纹；选择、核价前及最终执行均核对实际 Need。BGM/SFX 不借用 voice 授权，重放不能扩大范围，旧授权和旧请求指纹保持。Astra CONTINUE；既有生成集成扩展16PASS、run-040矩阵224PASS、全量967PASS/5既有skip、115技能/compileall/范围diff及前端lint/build通过（既有hooks/chunk警告保留）。257现场/123fixture保持。

固定工作树source `4d1a55101b61259b125a11f3cd9f18dbdcb9dbd9c00ff98ed20a568fd1356c68`，HEAD仍`df0d3a30`，未提交/未加载；服务仍为此前`73e63a66…544ea6`。本Goal媒体账本已记录用户¥30授权，累计分配/实际媒体花费均¥0；后续逐作品确认前保守占用整个子预算，总和不得超过¥30，失败/未知/未用不回收。两轮Development FAIL不变、第三次真实测试等待追加一次有界授权，无新增真实调用；自主视频仍0/3。[软件证据](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-budget-software.json)。

本地出片依赖追加核验：当前 `faster-whisper-large-v3-turbo` 已实际以CPU/int8、local_files_only加载成功，OpenCC转换通过，FFmpeg/FFprobe存在；Hypit 0.2.7的Easel指定profile仅含media.local/hyperframes.local，限定这两个端点的doctor通过，当前Chrome Headless Shell可用。已对照安装源码的local pricing与Easel免费Build判定。未执行识别、Plan/Build、生成、TTS或真实模型，源码/257现场/123fixture不变；本地依赖PASS不能替代真实声音准确率与成片证据。[脱敏前置检查](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-local-readiness.json)。

round2参数来源追加核对：原tool参数2600字节/SHA与已解析对象完全一致，错误容器在原参数中已存在；实际安装SDK的modern tool路径透传delta并拼接arguments，不观察到客户端数组→对象转换。错误定位为Provider返回结果不符合Schema；缺少服务端内部证据，不能进一步断定模型本体或Provider服务端格式转换。当前carrier发送完整Schema与指定tool choice，但没有function.strict字段，不声称服务端强制Schema已成立。原件按现有局部repair合同仍REJECT；不得把运输成功算Planning成功。此轮只读调查未新增外部调用或修改生产源码。[来源核对证据](acceptance/fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/autonomous-argument-origin-audit.json)。

## Planning A structured carrier：能力审计 BLOCKED，Astra STOP（2026-10-08）

用户授权四项修订后的同一vNext后续Goal，已设定并执行能力审计。固定生产SHA仍`ffac01cc…51c74d`/软件基线`aa0ab42a`，HEAD`df0d3a30`为后续证据文档。当前OpenClaw2026.9.4普通agent RPC拒绝动态tools/toolChoice；底层builder虽能表达指定function，direct/managed工具参数共用256000字节上限，现有结构合法A紧凑1331979字节在原生离线reducer实际拒绝。不是4096 preview问题，不把此容量反例当历史d01根因或真实语义不可表达；MiniMax服务端能力仍UNKNOWN。

Astra前置复核STOP，未发现本范围内保持完整合同的可行接入，已按停止分支结束。生产修改、模型/RPC/Supply/服务操作0，新增费用0；未commit/push。257现场/117fixture/十批1550文件原指纹保持。新协议实现、软件矩阵/全量回归及Development均NOT_EXECUTED，`READY_FOR_FORMAL_R4=NO`；旧软件PASS和真实FAIL不改写。受限于固定Runtime和当前接入，下一阶段需另定Runtime容量/工具接入范围，不继续Prompt或真实d01探索。[能力审计及脱敏执行证据](acceptance/planning-a-structured-carrier-capability-2026-10-08.md)。

## Planning Semantic Boundary vNext：S5 软件验收通过（2026-10-08）

连续Goal进行中，S1已通过；S2完整transport实现及容量Gate通过。4096 terminalReply仅展示摘要，旧Material3000协议保持；新planning-result-v2从原session/run的active最终assistant只读捕获，可信终态、stopReason与完整UTF8/SHA同时核对。安装OpenClaw2026.9.4隔离回放合法A/B及8MiB envelope无损，新进程读前后SQLite/WAL未变；Runtime/profile/phase实现钉SHA。Astra先MODIFY指出argv及转义Secret缺口，最小修复后CONTINUE。

S5软件run-032矩阵196 PASS、针对31 PASS、全量934 passed/5既有skip；AstraCONTINUE。固定`aa0ab42a`/source`ffac01cc…51c74d`后真实Development首轮第0项失败并停止：Preparation通过，A原结果7,849字节无损，但fenced JSON且条件/身份/源时长/未决语义多项不合规；132秒、2个RPC，B/Truth/Supply0。无安全充分的局部修复，第二轮不执行，`PLANNING_VNEXT_IMPLEMENTATION=FAIL（软件PASS、真实Development FAIL）; READY_FOR_FORMAL_R4=NO`。真实固定轮次内工程介入0，历史十批1550及257/117指纹保持，原请求已终态/清理，Gateway active/lost/audit0。套餐窗口100→99%、周97→97%，现金账单/token UNKNOWN。不push、不重启、不启动正式R4/Smoke/E2E。详见[最终验收与停止判断](acceptance/planning-semantic-boundary-vnext-development-2026-10-08.md)。下方R4记录保留历史。

## R4 batch10：@7固定版本已加载，真实评测进行中（2026-10-07）

固定commit`3be0ff946c29c8871a8f34de015c8b3944316ac7` / production203文件SHA`bf527ce1b565409817a5c21e0dc8029e6ca3ad73681bd619493fc4bd17be9caf`，23个选定源码/测试/fixture/Task文件凭证检查0命中，未push，其他工作树保留。run042135PASS/873全量PASS/5既有skip、115技能/compileall/diff、AstraCONTINUE。15:00:18 Web10168/Gateway10166安全加载，HTTP200/Gateway空闲；实际raw-stream停服后精确备份1,178,673字节、SHAbf6d88c5c98eeffb58971c3bc2ceb0dbf379d105c1dd847f3eab2d6d8dd0f0bf。无进程内SHA端点，版本证据为新PID/时间/执行文件/cwd与固定源核对。

实时8旧Owner有效操作0、各批unknown/pending/submitting/release待办0、Gatewayactive/lost/audit0，257旧正式现场/117fixture和九旧批原件保持。仅已购文字套餐额度89%/周98%，禁止余额/现金/超额/回退，实际账单UNKNOWN。原16主题与独立oracle不变，32新正常Creation隔离冻结，第0项开始真实Prep/A/B/Truth，尚无评分。正式合同与独立语义双PASS才下一项；实际Supply/Provider/生成/TTS/Build禁止，历史FAIL不恢复不倒算，Smoke=NO。[加载记录](acceptance/fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch10-release-loaded.json)。

## 硬条件来源治理：@7软件验收通过，等待固定及加载（2026-10-07）

同一Task§13.27已接入真实冻结来源、A/B依据及control运输、共享repair、身份/checkpoint与正式persist/load；工作树新产品默认@7，旧@1–6按原合同回放。Astra冻结前修订已闭合，最终run042为135PASS/0FAIL/0GAP/0未执行，全量873PASS/5既有skip，115技能/compileall/diff通过，257旧正式现场/117fixture保持，Astra最终CONTINUE。生产203文件SHA为`bf527ce1b565409817a5c21e0dc8029e6ca3ad73681bd619493fc4bd17be9caf`，尚非已加载版本。[具名软件验收](acceptance/fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch09-authority-software/software-summary.json)。

未commit/push/restart或启动新真实R4，服务仍89bc旧固定版；最新真实成绩仍batch09 FAIL/STOP。新真实模型/Supply/Provider/生成/TTS/Build调用0，Smoke=NO。下一步最终矩阵/全量回归与复核闭合后固定、加载，再另起原16主题的全新32项真实Eval。

## 硬条件来源治理：组件已实施，产品链尚未接入（2026-10-07）

同一Task§13.25.1经Astra前置CONTINUE后，新增Planning应用层来源目录/实际默认记录/控制值与basis资格校验。batch09真实14原件及独立预期保存17fixture，不改历史FAIL。完整修前run036为116PASS/2新增保护FAIL；组件run038为6PASS/2产品未接入FAIL，257旧正式现场/117fixture保持。组件只验证来源、已知强度及控制保护，不能证明B语义蕴含正确。

新目录/controls尚未接入A/B、共享repair、身份、checkpoint及正式persist/load，软件验收未完成。下一步完成@7同一产品链集成与完整回归，再固定版本和新真实Eval；不另建流程、不放宽Material V1.3。工作树已有未提交组件，服务/产品默认仍89bc旧版；未commit/push/restart，新真实调用0，Smoke=NO。最新真实成绩仍下方batch09 FAIL/STOP。

## R4 batch09：正式合同PASS，无来源屏幕/手部hard语义FAIL / STOP（2026-10-07）

固定89bc154d228f443e784632cd74386c54d2558ab9/sourceaff2ed40dd85dbec74f9a8a894b1688626116e6b2de5b145d8e0443597f7ea53首项Prep/A/B/Truth及一次Truth report repair五原runok/released，正式合同/Truth/Persist/Load/Supply前切点PASS。Planning无repair；15秒保持图像/function用途正确postproduction，原两纸/image/silent/9:16/SCRIPT及Mode soft保持。但required禁止任何屏幕无冻结硬来源且同Need soft no screens被硬化；手部禁令亦未找到硬依据。Main/Astra语义FAIL/STOP，不能以A自己写入description自证授权，不打包定罪有争议的印字/品牌范围。

1项FAIL/31未执行、held-out0/16；A/B初始1/1无Planning repair，含Truth初始0/1无报告repair，最终正式合同1/1但独立语义0/1。原required语义1/1保留，无遗漏/降级；无来源hard至少2。281.806秒、Planning含Truth219.945秒；5实际提交/30assistant/29工具/23原请求观察/4缓存重入，无重复提交。Truth repair1/1，按唯一会话窗口避免两个同session run重复计数。仅文字套餐90→89%/周98%，实际账单未知。

Supply全部下游/状态越界/工程介入0；固定源/工具/样本/SCRIPT、257旧现场/100fixture/八旧批及正式原件SHA保持，五run已释放、无pending/submitting/release/Gateway活动。历史FAIL永久保留、不恢复/重计，Smoke=NO。下一步Task§13.23/13.24先调查硬条款来源权威与程序投影方案，不能继续仅加提示后直接新真实测试。来源目录候选已获Astra MODIFY：不能把冻结Preparation自动当新增授权，也不能以逐字原句限制全部合法Director创意Need；须先明确出处、约束资格和全部消费者入口，尚未修改生产或启动batch10。[完整记录](acceptance/fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch09-actual-run-summary.json)。

## R4 成片使用与源条件软件已验收，等待新版本加载（2026-10-07）

同一Task§13.21/13.22完成compiler@6/target@3，units@8保持。新审核对象反事实不按可编辑性降级源条件；@5完整Schema、@1–5原映射/digest/身份/旧pending保持。run033115PASS/全量853PASS/5既有skip、115技能/compileall/diff与AstraCONTINUE；生产SHAaff2ed40dd85dbec74f9a8a894b1688626116e6b2de5b145d8e0443597f7ea53，257旧正式现场/100fixture保持。

最新真实batch08 FAIL/STOP不改，正确替身不证明模型改善。下一步按已有授权固定新commit、安全加载/套餐检查后原16主题全新32项batch09；全部Supply下游禁止，Smoke=NO。

## R4 batch08：完整Schema生效，首项unresolved正式FAIL / STOP（2026-10-07）

固定4614db7142ab6e189dde49fefd7356eafbb2cf74/sourceb64681a0c8b650d509824e4cb376fc6dfb05d0c0fc6a5d3a8850a812f1f4e548首项Prep/A/B/唯一repair四原runok/released；初B与repair均完整Schema合法，但整段成片使用/表达/后期function持续unresolved、结果无变化，正式消费者拒绝，Truth未执行。Main/Astra STOP本批；独立整段postproduction是合理可表达对照，不能声称function粒度不足为已证实根因。@5输出合同本次正常，语义判断尚未可靠。

1项FAIL/31未执行、held-out0/16；初始wire合法1/1，可用初始/最终正式合同0/1，repair0/1，正式语义/required覆盖未验证。218.823秒、Planning136.344秒；4原提交/25assistant/41工具/18原观察/3缓存重入，无重复提交。仅文字套餐91→90%/周98%，实际账单未知。Supply全部下游/状态越界/工程介入0，257旧现场/90fixture/七旧批及源码工具样本保持，原run全部释放、无pending/submitting/release/Gateway活动。

本批及历史FAIL永久保留、不恢复/重计，Smoke=NO。下一步同一Task§13.21先补独立语义正反对照、前置复核审核对象任务，未经证据不拆function或放宽unresolved。[完整记录](acceptance/fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch08-actual-run-summary.json)。

## R4 B输出合同软件已验收，等待新版本加载（2026-10-07）

同一Task§13.18/13.19完成@5完整B/repair输出Schema及精确诊断；Material V1.3、语义任务target@2、一次修复额度保持，旧@1–4版本/身份保护通过。最终run031110PASS/全量848PASS/5既有skip、115技能/compileall/diff及Astra CONTINUE，生产SHAb64681a0c8b650d509824e4cb376fc6dfb05d0c0fc6a5d3a8850a812f1f4e548。257旧正式现场/90fixture保持，正确替身不证明真实模型改善。

最新真实成绩仍batch07 FAIL/STOP，所有历史FAIL保留。下一步按已有授权固定新commit、安全加载/套餐检查后另起原16主题全新32项batch08；Supply及全部下游禁止，Smoke=NO。

## R4 batch07：前2项双PASS，第3项结构合同FAIL / STOP（2026-10-07）

固定7685953c72925b195aa7e882996aca076a2151bb/source71e5ecbbafdfd7104b835a5b6b2a3071a2132e291d31d5134dab9281547e99e4的新批已3/32，前两项无repair且正式+独立语义PASS；连续倒水/Voice主题初B返回非法kind narrative_or_postproduction，程序误报原文引用问题；唯一repair回传输入式wrapper并保留非法kind，正式拒绝，Truth未执行。Main及Astra STOP；后29未执行、held-out0/16，初始/最终合同2/3，repair0/1，失败项正式语义覆盖未验证。严格拒绝正确，但完整B/repair输出Schema和分层诊断存在软件缺口，下一步同一Task§13.18先实际事故回放/最小合同方案及设计复核。

累计616.810秒、Planning401.139秒；12原提交/77assistant/104工具/51原请求观察/9缓存重入，无重复提交。Supply下游/状态越界/工程介入0。套餐94→91%/周98→98%，实际账单未知。257旧现场/77fixture/六旧批原件及固定源/工具/样本/SCRIPT保持；12原run全部释放，各批pending/submitting/release0，Gateway空闲。正式原件不改，不继续/恢复本批，不认领Smoke；所有历史FAIL及第1项冗余scope风险保留。[完整成绩](acceptance/fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch07-actual-run-summary.json)。

## R4 属性与用途关系软件验收完成（2026-10-07）

Task§13.15/13.16新@4/target@2说明与显式旧@3映射已通过run027 103PASS/841全量PASS/5既有skip、115技能/compileall/diff及AstraCONTINUE。生产SHA71e5ecbbafdfd7104b835a5b6b2a3071a2132e291d31d5134dab9281547e99e4，257旧现场/原59fixture保持，新增18后77fixture稳定。只证明任务定义/版本/身份及正式合同可表达，不保证模型kind正确；旧及新wrong-kind独立FAIL反例保持。下一步窄提交、安全加载/套餐检查后另起32项真实R4。当前最新真实成绩仍batch06 FAIL/STOP，Smoke=NO。

## R4 batch06：正式合同PASS、属性与用途混合语义FAIL / STOP（2026-10-07）

固定0b176a2a/sourcef01fe331的新32项首项正常Preparation/A/一次query repair/B0/Truth，共5原提交、全ok/released。正式合同/Truth/持久重载通过，但源图“负空间构图以便后期叠字”被整句postproduction；源属性不能因用途变成编辑操作。已有显式负空间preference保留，无required遗漏/升级，但错误kind仍构成独立语义FAIL。Main核定FAIL、Astra STOP；本批停止，31未执行、held-out0/16，不追加修复或重计成功。

初始无需repair合同0/1、最终正式合同1/1执行项、独立语义0/1。211.901秒、Planning/Truth150.381秒；5原提交/36assistant/34工具/17原请求观察/4缓存重入，无重复实际提交。实际Supply及下游/状态越界/工程介入0。套餐95→94%/周98→98%，实际账单未知。257旧现场/59fixture/5旧批原件及固定源/工具/样本/SCRIPT保持，无pending/submitting/release，Gateway空闲。完整现场保存并核对；详见同一Task§13.14和唯一验收。当前Smoke=NO，下一步只做独立软件根因治理；下方加载和旧成绩为历史记录。

## R4 batch06：新版本加载，真实评测进行中（2026-10-07）

审核对象说明固定 `0b176a2a8fa30b01c652aa044f176feb93c2639e` / source `f01fe3317b4aa223caddea08ee0ee86cf5d3347944dc9698fd997c7a00e66005`；同矩阵run-023 96 PASS、全量834 PASS/5既有skip、115技能/compileall/diff及Astra CONTINUE。@3/units@8加入program-owned审核对象说明，新A/B及共享repair同用；旧@2完整canonical/batches/身份和@1保持，错误kind仍结构PASS/独立语义FAIL对照保留，软件不是模型语义成绩。

12:19:50 Web/Gateway新PID96725/96723安全加载，HTTP200/Gateway空闲，8旧Owner有效操作0，unknown/pending/submitting/release待办0；实际raw停服后2,328,086字节精确备份并SHA核验。257旧正式现场/59fixture/全部5旧批原件保持。仅已购文字套餐95%/98%、无付费回退，实际账单未知。

原16主题/oracle未改，新32独立正常Creation隔离；第0项真实Preparation/A/B/Truth进行中，尚未评分。每项正式+独立语义双PASS才继续，实际Supply及下游禁止，旧FAIL不恢复不倒算，Smoke=NO。详见同一Task§13.12/13.13与唯一验收。下方batch05及旧批FAIL为保留真实结果。

## R4 batch05：正式合同PASS、叙事义务语义FAIL / STOP（2026-10-07）

固定59bd7d857c6d955761a0d7fc217c713477b02762/source0657a8c27e3cf6ef2ace05ed8a8c00c15cb7604ff28dcd1d3ac28863e7fcfa48，软件88矩阵PASS/826全量PASS及安全加载后，新32正常Creation首项真实Prep/A/B/Truth四run全部ok/released，无repair，正式合同与持久重载通过。引用完整/正文后期职责正确，但asset required“不要替读者补完两张纸的来由。”约束作者叙事而非图片属性：相同素材不变，仅叙事改变即可违反。Main独立语义FAIL及Astra STOP；有真实创作来源也不能交错误审核对象。两张白纸required/静态image/silent/正文不变不能抵消该FAIL。

1项语义FAIL、31未执行、held-out0/16；正式合同1/1执行项、语义0/1。耗时277.094秒、Planning/Truth193.519秒；4原提交/33assistant/41工具/23原请求观察，3缓存原请求重入，无重复提交。NORMALIZE/repair/下游/状态越界/工程介入0。仅已购文字套餐96→95%/周98→98%，实际账单未知。

收尾Gateway空闲，无pending/submitting/release待办；257旧现场/43fixture/所有4旧批原件及源码/工具/样本/SCRIPT保持。正式产物不改，完整受保护现场与脱敏证据保存。下一步按同一Task§13.11建立“素材可观察条件 vs 作者叙事/事实义务”实际关系对照，先离线证据及统一设计复核，再另固定版本、新批32项；本批停止且历史FAIL保留，Smoke=NO。[本批记录](acceptance/fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch05-actual-run-summary.json)。下方进行中和软件PASS为历史记录，不覆盖本次FAIL。

## R4 batch05 已固定加载，真实评测进行中（2026-10-07）

引用关系软件固定 `59bd7d857c6d955761a0d7fc217c713477b02762` / source `0657a8c27e3cf6ef2ace05ed8a8c00c15cb7604ff28dcd1d3ac28863e7fcfa48`，run-019 88 PASS/全量826 PASS及Astra CONTINUE。Web/Gateway11:59:15新PID94376/94374、HTTP200、Gateway空闲；实际raw-stream停服后1,092,870字节完整备份并核验。8旧Owner有效操作0，各批无unknown/pending/submitting/release待办。仅已购套餐96%/98%且无fallback，实际账单未知。

原16主题/oracle冻结，32全新正常Creation隔离；正在第0项真实Prep/A/B/Truth评测，尚未评分，不认领PASS。257旧正式现场/43fixture及全部旧批原件保持；旧FAIL永久保留。停在Supply之前，Smoke/E2E未启动。详见唯一验收加载记录。

## R4 引用关系软件验收完成（2026-10-07，尚未新真实运行）

Task§13.9/13.10的@2/@8已完成：引用完整、实际确认三文件进入B及批次身份、旧@1/@7显式恢复、旧pending不重发，Material V1.3及修复额度未变。最终run-019 88 PASS/0 FAIL/0 GAP/0未执行，全量826 PASS/5既有skip、115技能/compileall/diff及Astra CONTINUE。run-018副本回归FAIL原样保留，已按实际待写入/已保存三文件修正。生产SHA `0657a8c27e3cf6ef2ace05ed8a8c00c15cb7604ff28dcd1d3ac28863e7fcfa48`。257旧现场/原29fixture不变，新增14后43 fixture保持。

软件仅证明语法/来源/身份及合法路径；新错误kind仍能结构通过，独立语义FAIL反例保留，不认领真实改善。下一步固定提交、安全加载并另起32项R4。最新真实成绩仍是下方batch04 FAIL；不得恢复本批或启动Smoke。

## R4 batch04：结构合同通过、独立语义FAIL / STOP（2026-10-07）

固定commit `b819d2877c65d2c10836d076415a0cc47690377b` / production SHA `79e580c163c77cafc47d4056c910e1aaf5bcc49419be31e78497d08588a54825`。第0项 `cr_84d61116682f460aac89817994c5f7ed` / `fa_1bbb0bd32f282011db2ef4cb7bf03047` 正常Preparation、A、B0、Truth各1原run，全部ok/released；无repair，真实首次正式合同通过、持久重载一致，在原生Supply import前停止。Native Owner仍preparing/next=prepare，评测器仅记录下一子阶段Supply入口，不人工造状态或MATERIAL_READY。

独立语义FAIL：冻结SCENES的“在后期叠加正文”被B编入视觉required；“由后期叠加。”以及引用正文的碎片不是背景图的素材硬条件。两张白纸required/静态图片/静音/正文均保留（明确required语义1/1），但不能因此通过整个语义验收。Astra STOP确认。primary_visual的postproduction分类合法，无人脸/人物有本次Prep来源；不将所有导演构图细节判作凭空新增。自然光等在preferred字段及description hard clauses双重表达另列强度风险，失败不依赖争议项。

本批1项语义FAIL、31未执行、held-out0/16；结构合同1/1执行项（1/32计划），语义总体0/1。墙钟257.450秒、Planning/Truth至切点173.171秒；4真实提交、36assistant响应/32工具、21原请求观察检查点，7应用callback含3原请求缓存重入，重复实际提交0。修复/补证/报告repair0、Supply/Provider/生成/TTS/Build0、state violations0、ENGINEERING_INTERVENTION0。文字套餐5小时97→96%、周98→98%，共享账号比例不是单次费用，实际账单未知。

收尾Gateway active/lost/audit0，无pending/submitting/release待办；257旧正式现场、29fixture、batch02的134原文件与batch03的136原文件、固定代码/工具/样本/SCRIPT不变；语义审核只写独立评分，不改正式Plan/Requirements/Truth。完整脱敏会话、原输入输出/请求身份/计时/原日志/独立评分保存受保护batch04目录；[结构化结果](acceptance/fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch04-actual-run-summary.json)。Smoke=NO。

下一步仅按[同一Task §13.8](tasks/planning-material-boundary-matrix-2026-10-06.md#138-batch04结构通过独立语义fail2026-10-07stop)建立该真实语义事故fixture/独立反向保护，统一设计“来源与强度/完整语义单元/后期职责”修正，先设计复核和离线集成，再另固定新版本。当前不改生产、不恢复失败批、不继续真实模型或Smoke。下方准备/软件PASS均为历史前置证据，不覆盖本次FAIL。

## R4 batch04 固定版本真实评测准备完成（2026-10-07）

A输入边界对齐固定为 `b819d2877c65d2c10836d076415a0cc47690377b`，202文件 production SHA `79e580c163c77cafc47d4056c910e1aaf5bcc49419be31e78497d08588a54825`。最终同一矩阵run-013 80 PASS/0 FAIL/0 GAP/0未执行，全量818 PASS/5既有skip（62.31秒）、115技能/compileall/diff通过，Astra CONTINUE；未推送，用户其余工作树保留。

Web/Gateway在11:20:21以新PID86940/86938加载；健康200、Gateway active/lost/audit0；8旧Owner有效操作0、持久unknown/pending/submitting/release pending0。实际raw-stream停服后52235字节精确备份，SHA核验，初次Gateway健康检查早于就绪，随后正常，无再次重启。源码/257旧正式现场/29fixture/batch02与03原件保持；个别hash被通用脱敏器隐藏的预提交记录另以总指纹与授权文件逐字节比对核验，原记录不改。

用户已购文字套餐/direct-use授权保持；同Key官方只读余量97%/98%，无fallback，实际账单未知。batch04已冻结32个全新正常确认Creation，原16主题/独立oracle未变；真实评测尚无成绩。正式A/B/Truth与独立语义审核每项均通过才推进下一项；真正Supply/Provider/生成/TTS/Build禁止。旧批FAIL不覆盖，Smoke=NO。

## R4 batch03 真实Planning FAIL / STOP（2026-10-07）

独立路径修复软件固定`63da1b009bf349d82315acc180c9d33dc4d8b86b`/生产SHA`61b6a75e65b214e61d0fa6da693cb97ed4dd722c667fe3becd9f760945ff807b`，run-008矩阵72 PASS、全量810 PASS/5既有skip及Astra CONTINUE；Web/Gateway新PID80112/80110于10:48:53加载。无活动旧任务/未知执行，实际raw-stream386041字节已精确备份。32个新Creation沿用冻结16主题/oracle。

实际第0项FAIL并停止：Preparation、A、单次repair各1且ok/released；repair已正确写入Attempt绝对路径。初始policy类型错误挡住后续检查；修复policy后，constraints.must_contain列表不能作为scalar retrieval filter、continuity_ref不在冻结catalog，共享一次repair耗尽。A Schema比Compiler接受范围宽；Astra STOP，不能再增加修复额度或删required救场。后期overlay被列为required image仅作风险诊断，未到B/Truth/正式语义评分。31项未执行、held-out0/16，最终合同0/1执行项，Smoke=NO。

墙钟205.748秒、Planning约156.954秒；3真实run、24模型响应/25工具、17原请求观察，无重复实际提交；Supply/Provider/生成/TTS/Build0，state violations0、工程介入0。文字套餐5小时98→97%、周99→98%，实际账单未知。257旧现场/25fixture/batch02原件/source/tool/HEAD/SCRIPT未变；完整脱敏会话、原A/repair、原日志与故障现场已归档。后续先按[唯一Task §13.5](tasks/planning-material-boundary-matrix-2026-10-06.md#135-batch03路径修复有效但acompiler合同仍失败2026-10-07stop)统一对齐A输入与完整编译边界及真实离线fixture，此处仅规划，不修改本失败批或启动Smoke。

## R4 batch02真实Planning失败（2026-10-07，FAIL / STOP）

固定a7f7ccfe/source327842新版本及独立32Creation的第0项已实际执行：Preparation→A→唯一repair三个原run均ok/released，完整202.975秒。但A的5个policy bool不符合dict[str,str]；repair请求没有Attempt绝对目标，独立会话写到Gateway默认workspace，正式消费者仍读取错误A而拒绝。B/Truth未执行，1FAIL/31未执行、held-out0/16。Astra确认MODEL_OUTPUT+STRUCTURAL_CONTRACT并STOP；fixture从闭包/Creation补路径掩盖了目标合同缺口。

STATE_VIOLATIONS=1（repair产物越出Attempt），workflow越级0，正式Supply/Provider/生成/TTS/Build0，工程介入0；未搬入误写文件、未修改固定生产/工具救场，未恢复旧作品。19模型assistant响应/29工具/17原请求观察，无重复付费提交；5小时套餐99→98%、周99→99%，账单未知。三个原run无pending/submitting/release，Gatewayactive/lost/audit0；257旧正式现场、25fixture和冻结正文/源码/工具不变。误写路径之前是否存在未知，不宣称全Gateway workspace无损。完整脱敏会话/原稿/错写文件/SHA保存于受保护batch02目录。

本批停止，Smoke=NO。[原Task §13.3](tasks/planning-material-boundary-matrix-2026-10-06.md#133-新版本真实第0项失败repair目标合同缺口2026-10-07stop)已给最小后续路径绑定与无隐含root的集成回归方案，尚未实施；[结构化结果](acceptance/fixtures/planning-material-matrix-2026-10-06/r4-preflight/batch02-actual-run-summary.json)。旧99b3 FAIL、异步前置FAIL及历史事故例外保持；下文RUNNING为本批开始时历史。


## R4 新固定版本独立批次（2026-10-07，RUNNING）

旧99b3/source0907批次STOP/FAIL和后续异步前置FAIL保留。独立软件修复仅A/B/repair三处稳定JSON键序，原身份/hash/scope/route/冻结正文/repair额度保护保持；不迁移旧请求、不恢复旧作品。同一矩阵run-006 **70 PASS**，全量 **805 PASS/5既有skip**，29项针对性/115技能/compileall/diff通过，Astra CONTINUE。

已固定commit **a7f7ccfea07fb7ebb64534267e22959fe948ef72**，202文件production SHA **327842e4e249481f75ffc934c973c1621807e7cc7e3073ab01b1b82b7053a636**，仅8个获批文件commit，无push，用户其他工作树保留。Web PID77120、Gateway PID77118在10:28:16加载；健康200、8旧Owner有效操作0、pending/submitting/release pending0、Gateway active/lost/audit0，257旧现场/25fixture不变。停Gateway后实际raw-stream路径229259字节完整归档、SHA核验后才重启；首个bootstrap瞬态失败，确认服务未加载后对同plist重试成功，无新日志丢失。

套餐只读同Key查询5小时/周余量99%/99%，M3无fallback，仍只授权已购文字套餐。原16主题和独立语义oracle未改，新目录`~/Library/Application Support/Easel/acceptance/planning-eval-r4-2026-10-07-batch02`冻结32个全新Creation和工具/样本/源码/历史基线；正在执行第0项Preparation，尚未认领任何Planning成绩。真正Supply/Provider/生成/TTS/Build禁止；软件通过不替代新批真实结果。每项原生合同与独立语义审核通过后才下一个，生产问题或语义失败即停。本批不认领Smoke/E2E；下文旧版停止状态属于历史。


## R4 异步前置回归（2026-10-07，生产恢复缺陷 / STOP）

仅修评测工具并补原生Owner→Gateway异步回归后，在新真实批次开始前发现生产缺陷：首次Preparation交付未排序内存bundle，恢复读已排序冻结快照；A消息包含同值但不同键序的voice.context，重建请求字节/hash变化，被原身份检查拒绝。原A已成功且释放，仍不能进入B/Truth。Astra只读复核STOP；不是模型语义失败，也不能用排序fixture或放宽hash保护规避。

同一矩阵run-004 **66 PASS/4 FAIL/0 GAP/0未执行**；run-005保存完整请求SHA/解析相等/键序差异，6项2PASS/4同根因FAIL。全量 **801 PASS/4 FAIL/5既有skip**，115技能/compileall/diff通过。commit99b3/source0907、257旧现场、25fixture均不变。新真实批次/模型/供应/生成/TTS/Build/费用=0；旧真实批次FAIL及raw-stream例外原样保留。评测工具修正已落工作树，生产修复未实施，未commit/push/重启服务。R4停止，Smoke=NO；下一步按[同一Task §13.1](tasks/planning-material-boundary-matrix-2026-10-06.md#131-异步前置回归发现生产缺陷2026-10-07stop)做稳定请求构造软件修复及回归，再固定新版本/检查加载/新独立Eval。[唯一验收](acceptance/planning-material-boundary-matrix-2026-10-06.md#r4-异步前置验证失败2026-10-07固定版本stop)及[结构化证据](acceptance/fixtures/planning-material-matrix-2026-10-06/r4-preflight/async-preflight-summary.json)。下文旧PASS均不覆盖本次新增异步路径。

## R4 真实 Planning Eval（2026-10-07，评测工具FAIL / 本批停止）

用户授权后，R0–R3 固定为 commit `99b3ca836f7c50f5ecfbea46661f91d4c40c808b`，production SHA `0907c35cf4ee98254ac0a598f924d7b757b4aaf29cc24d1ac1d3f234d5e65217` 与软件验收一致；仅提交获批软件范围，其他文档工作树保留，无 push。Web PID71192、Gateway PID71182（2026.9.4）已加载；8个旧Owner无有效下一步，持久pending/submitting/runtime_release pending=0，Gateway active/queued/running/lost及taskAudit=0；257份旧正式现场和历史fixture未变。

**新增现场保护FAIL保留：** 重启前误备份了 `/tmp` 路径，实际 Gateway raw-stream 在 wrapper 启动时被清空，原长度及损失范围未知；未恢复或冒充重建。五个相关历史会话395条事件仅作补充。用户已明确接受本次新的保留例外，历史四轮 FAIL和原事故不改；已保存事故后实际路径的新基线。不能将本次加载认领为全现场无损。

R4样本16个（8开发/8留出）、32个独立正常确认Creation在隔离根冻结，尚未认领任何成绩。评测专用停止边界复用正式Owner/Preparation/A/B/Truth/persist/load，停在原生Supply import之前；不伪造Material Gate。评测器/实际HEAD/生产SHA/样本/批次现场基线固定，未知或不足额度不提交，跳过前序语义审核拒绝，收尾变化强制整批FAIL。同一矩阵run-002 **64 PASS**，R4针对性 **12 PASS**（含真实只读validator子进程），完整回归具名 **793 PASS/5既有skip**；Astra修订后CONTINUE仅允许R4。

用户仅授权已购文字套餐额度，禁止现金/API余额/超额和付费回退，并明确沿用当前配置。实际同Key官方订阅只读查询成功，5小时剩余100%、周99%，当前MiniMax-M3、fallbacks为空；每阶段提交前保守检查余量。此检查不是原子账号扣额控制，实际账单未知。第一条《桌上的两张纸》提交了1个Preparation原请求，原生Owner先为execution_uncertain，观察后为observing_execution；冻结评测器遗漏后者，错误记FAIL。本批原FAIL保留并停止，未修改冻结工具救场。原请求随后自然正常结束/runtime released，四份准备文件原生只读校验PASS，Attempt=0、A/B/Truth=0。不能把工具失败当作Planning合同失败，也不能认领32次Eval成功。实际模型16个assistant响应、32工具调用（20exec/1次最终validate），无Provider/生成/TTS/Build；Preparation约123.4秒，5小时套餐100→99%、周99→99%，provider用量/成本均报0但不是实际账单。原run已完整脱敏归档，Gatewayactive/queued/running/lost/audit=0，257旧现场/生产/冻结工具仍不变。Smoke=NO；下一步仅修评测器异步观察和检查点循环、补原生agent.wait回归，再以新工具指纹另起独立批次，当前批次不得继续计分。

R4完整本机现场受保护保存于 `~/Library/Application Support/Easel/acceptance/planning-eval-r4-2026-10-07`；脱敏结果沿用[唯一验收](acceptance/planning-material-boundary-matrix-2026-10-06.md)。下方R0–R3的未提交/未加载描述是当时软件阶段历史。


## Planning单一语义源软件验收（2026-10-07，R0–R3 PASS / 真实评测未启动）

用户授权[同一Task R批](tasks/planning-material-boundary-matrix-2026-10-06.md)实施后，产品v3已实现：模型一次语义草稿→程序绑定ID/模态/默认值/Voice摘要及来源→模型仅分类程序unit→程序生成正式Plan/sidecar/cache/manifest。复用现有bind/validate、Truth、持久账本和Gate；整次Planning最多一次repair，未知只恢复原身份，纯声音B=0，旧确认/v1/v2按原合同且有旧执行/产物时不升级。独立语义答案与真实失败回放加入同一矩阵，四方职责和Material V1.3未改变。

最终run-017 **53 PASS/0 FAIL/0 GAP/0未执行**（原25组保留、36风险组含参数化）；全量 **787 passed/5既有bun skip**，115技能/compileall/diff通过。Astra实际实现两轮MODIFY已落实，最终CONTINUE。真实内部确认→Owner→Preparation→A/B→Truth→persist/load→Supply/首轮Observation，外部fixture替身；搜索/接收/观察各1，prepare重入搜索/接收保持1→1。原件篡改/坏快照/共享额度/嵌套子字段保护、Gateway原run超时及release恢复、v3副本绑定均已实际回归。软件通过不证明模型对Creator意图的泛化保真或真实素材准入。

HEAD仍55af28fb；新202文件source SHA **0907c35cf4ee98254ac0a598f924d7b757b4aaf29cc24d1ac1d3f234d5e65217**，未提交工作树与确切diff/文件清单形成软件指纹，未commit/push或主动重启/加载服务，运行版本未重核。R0至最终257现场文件、原19历史fixture未变（新增后24fixture也前后不变）。历史现场保护FAIL例外和四轮真实失败永久保留。最新第四轮 cr_bbe0db97318f45aea09dc839f3d9c916 先repair Voice schema，最终sidecar仍引用不存在的constraints/subtitle_overlay_only，未进入Supply；不恢复/Retry、不倒算成功。

详见[唯一验收](acceptance/planning-material-boundary-matrix-2026-10-06.md#r0r3-单一语义源软件验收2026-10-07)。本轮新增真实模型/Provider/采购/生成调用与付费费用0、新真实Creation 0；R4 Eval/R5 Smoke/R6 E2E未启动。下一步另行固定提交与检查服务加载，冻结16主题/32次独立Planning Eval语义预期和预算；Eval通过后才Smoke，再完整Material E2E到MATERIAL_READY。

## 统一治理固定版本已加载（2026-10-06，加载前置PASS）

用户另行授权后固定代码commit `55af28fb62bf4bd0d194b372101a55b05a48a051`，production SHA `cd314b19e591a302657c4762508ac42b0df422139d8ebe44a89b86991c45aecc`与run-015一致，源码干净、无push，其他既有文档工作树保留。事故以保留例外关闭，不恢复/Retry/复用旧作品，历史现场保护FAIL和三轮E2E FAIL不变。既有LaunchAgent加载Web PID61558、Gateway PID61470（2026.9.4）；健康与空闲检查PASS，Owner无旧操作/状态改写、pending/submitting/runtime_release pending=0，223份现场与19fixture加载前后不变。未启动真实模型评测/Smoke/E2E，下一步单独固定评测样本、预算与停止条件。见[加载验收](acceptance/planning-material-boundary-matrix-2026-10-06.md#固定版本与服务加载2026-10-06用户另行授权)。下方未提交/未加载状态保留为软件阶段历史。


Last audited: 2026-10-06. This is the single summary of current implementation and verification status. Source and tests establish behavior; dated Acceptance documents provide evidence for named runs. `SOFTWARE_ACCEPTED` never implies `REAL_WORLD_VERIFIED`.

## 模型输出可靠性统一治理（2026-10-06，软件合同PASS / 现场保护FAIL）

用户确认统一[实施Task](tasks/planning-material-boundary-matrix-2026-10-06.md)并授权A–D，F1正文容器、G1查询提示角色、G2产品Planning v2已实现。新正文精确保留且确认重验；旧未确认稿正常修订、已确认旧稿按旧版读取。查询解释共用，旧字段不进入硬filters或视觉required，保持候选/排序和既有cache身份。新产品登记v2并绑定sidecar/manifest/最终Need，原pending先按原route核对；旧有效v1恢复，异常版本/身份/cache/报告复用拒绝。Material V1.3、Rights/Match/Readiness与预算授权未放宽。

最终run-015 **25 PASS/0 FAIL/0 GAP/0未执行**，全量 **738 passed/5既有bun缺失skip（49.41秒）**，115技能、compileall/diff通过，Astra最终CONTINUE仅认可软件合同冻结。真实内部确认→Owner→Preparation→Planning→Truth→Supply→Observation连续集成，外部模型/Provider为隔离fixture；主场景搜索/接收/观察各1，重入不新增搜索/接收；CRLF、旧合同、查询cache、报告早返、副本身份与中断保护均有回归。

**现场保护FAIL，不认领A–D无例外整体通过。** 首轮全量测试中当时未限制产品范围的v2登记分支，因历史fixture使用真实ID误写前两轮Creation的版本、登记历史及更新时间（3/15登记事件）。未回写恢复；内存反事实重建与A基线SHA完全一致，确认变化限于四类元数据路径。221/223受保护文件和全部19历史fixture不变；两份Creation仍failed，三轮真实FAIL不变。修正产品范围并新增Python写入保护后，最终全量及矩阵前后现场无进一步变化；保护器不是完整系统沙箱。完整事故和软件证据见[唯一验收](acceptance/planning-material-boundary-matrix-2026-10-06.md#统一治理ad软件交付2026-10-06)。

当前仍为easel-studio未提交工作树，HEAD36ead76；包含新增源码的集合SHA`cd314b19e591a302657c4762508ac42b0df422139d8ebe44a89b86991c45aecc`。未提交/推送、重启/加载服务、执行付费模型/Provider或真实E批。软件合同PASS不认领素材层独立自主验收；原失败记录保持，现场元数据处置与真实评测/Smoke/E2E另行启动。

## Planning → Material 合同与集成矩阵（2026-10-06，修复前历史调查）

按用户对齐方案固定36ead76beaeed02ce53d1580dc4f0fb56ddcd88e及生产SHA5f6e21a2fb301358c906291bbf4a811fa44ac986ace214a1c7ef687c10b0aede，独立矩阵25风险行：**22 PASS / 1 FAIL / 2 CONTRACT_GAP**；pytest24 passed/1 failed。唯一明确FAIL为第三轮正常确认入口接受含说明/TTS预测/编排的script；缺失同轮sidecar的新旧政策、旧三标量query被留在filters单列合同缺口。历史wrapper、模态污染、原文/身份/cache/持久重入保护通过；不把结构绑定当作模型语义能力证明。

真实Owner/Preparation/Planning/Truth/persist/Supply/Observation的离线交接执行成功，外部语义为确定性fixture；搜索/接收/观察各1，重入服务2次但搜索/接收仍1，Rights UNKNOWN、观察unknown、Gate MATERIAL_NOT_READY。三轮原FAIL保留、223运行文件SHA与集合不变；生产代码/服务不改，无真实模型、Provider、采购、生成或视频执行。矩阵独立入口，默认collection736项不受失败案例影响；compileall/diff/脱敏检查通过，原装配失败日志保留。结果、完整Expected/Actual及聚类见[唯一矩阵验收](acceptance/planning-material-boundary-matrix-2026-10-06.md)，范围见[Task](tasks/planning-material-boundary-matrix-2026-10-06.md)。本节保留修复前调查；后续软件结果与现场异常见顶部统一治理节，真实Smoke/E2E后置，第三轮预算不转授。

## 第三次独立 Material E2E（2026-10-06，FAIL / Truth Gate）

固定`36ead76beaeed02ce53d1580dc4f0fb56ddcd88e`与生产SHA`5f6e21a2fb301358c906291bbf4a811fa44ac986ace214a1c7ef687c10b0aede`，经加载/无活动旧任务核验及Astra CONTINUE，从正常新对话建立《给一天留一点空白》`cr_7e2e84a687d9493095ff371425d7e930` / `fa_f0ff6daa752e339819a677b2d893a6fc`。独立¥10图片/预置旁白预算，确认前正式绑定MATERIAL_READY。Preparation通过，本次真实9个required Need（6视觉、Voice、BGM、SFX）完整保留；Domain/模态/全部视觉要求合同正常通过，无结构修复。正式PLANNING_READY未建立、Material Supply未进入。

确认稿文案段含6句正文及方案元说明，整体进入SCRIPT。Truth将正文6句判creative_expression、2项说明判rewrite_required、TTS时长预测判unresolved；冻结确认稿不能自动改写，后台同错3次后failed停止，无额外模型重派。`MATERIAL_E2E=FAIL / AUTONOMOUS_EXECUTION=YES / AUTONOMOUS_DELIVERY=NO / ENGINEERING_INTERVENTION=0`；供给0/9、无Readiness Gate，确认至终态5分46秒、Planning至终态3分55秒。Agent5、供应/生成/声音验证0，占额¥0，模型真实费用UNKNOWN。没有Authoring/Build/Quality/发布；15个旧作品及生产源码SHA不变，前两轮FAIL保留。只读诊断与完整脱敏现场见[第三轮唯一验收](acceptance/material-independent-e2e-3-2026-10-06.md)。本轮不修复、不恢复，也不认领Material Layer真实自主交付成功。

## 第三次独立 Material E2E 前固定版本与加载（2026-10-06）

用户授权提交已验证改动并重启服务。修复源码、测试、真实回归fixture及必要Task/第二轮验收记录已提交至`easel-studio`：`36ead76beaeed02ce53d1580dc4f0fb56ddcd88e`。生产源码/测试无未提交改动；既有无关文档整理继续保留，未混入此提交。沿用上节731 passed/5 skipped、115合同、compileall/diff及Astra CONTINUE，提交时未改测试过的代码。

北京时间21:04:30通过现有launchd重启Easel Web/Gateway；Web PID45709、cwd为本仓库，Gateway PID45701，实际runtimeVersion=2026.9.4。重启后Web `/api/status`、Gateway健康/状态通过，active=0、queued=0、683任务全部终态、taskAudit warnings/errors=0；Gateway原已安装模块SHA未变。加载前后15个Creation JSON及第二轮workspace18文件SHA不变，两轮FAIL均保留。生产文件集合SHA为`5f6e21a2fb301358c906291bbf4a811fa44ac986ace214a1c7ef687c10b0aede`，本节算法为全部Git跟踪easel/web/scripts文件路径→SHA排序JSON再SHA，不与旧次验收不同清单算法混比。

脱敏预检与加载记录：`/Users/xgx/Library/Application Support/Easel/acceptance/planning-modality-release-2026-10-06`。未启动第三次Creation/E2E、未调用模型/素材生成或视频流程；新作品预算仍须绑定新Creation，前两轮预算不转授。以下“未提交/未加载”为软件修复阶段的历史状态，当前加载版本以本节为准。

## Planning 模态与单次修复边界（2026-10-06，软件前置通过）

第二轮真实失败的更早根因是初始Planning将`voice_delivery`复制到全部10个Need；合法Voice对象原本已受支持，非Voice对象与笼统scalar修复提示冲突，继而被摊成3个非正式别名。共享application校验现于检索、视觉sources、Planning默认合并前及生成入口拒绝错位对象/别名；producer与repair共用对象例外。合法Voice canonical结构、取值范围、visual sidecar及required/optional不变，不自动删移参数或修写真实失败产物。

原“单次结构修复”另被异步重入放大至7次；现持久保存Attempt/冻结refs/确认方案对应的原请求，未知/超时只恢复原身份，complete只验产物、failed不再派发，普通Retry及错误变化不刷新额度。这是明确的恢复行为收紧，未重构Owner。全量**731 passed、5 skipped**，115技能合同、compileall/diff通过，Astra最终CONTINUE。原18份workspace文件、14个旧Creation均未变，两轮FAIL保留；服务未重载、真实模型/Provider调用0。代码仍在工作区未提交，后续新真实E2E须先提交固定并核验加载。详见[目标、根因与方案](tasks/planning-modality-contract-2026-10-06.md)。

## 第二次独立 Material E2E（2026-10-06，FAIL / 新 Planning 边界问题）

固定修复提交 `c9cb4b9c`、生产源码 SHA `de23d0567944e543015f17bd7c425886bb0ed1d0f864ca9efb1fb1aebd4cfdfa`，安全加载 Web/Gateway 并经 Astra 前置 CONTINUE 后，从正常新对话创建 `cr_223021d92de643f0a35faea2907de7ed` / `fa_d5e99b227faa224b82f5347174850a1b`，独立预算¥10、正式终点MATERIAL_READY。Preparation真实通过；真实要求文件已正确以全部7视觉ID作键、没有audio ID混入，但系统声音检索修复把标量voice参数写入全部视觉Need，最终每项漏引`constraints/voice_tone=neutral`，严格原文覆盖校验拒绝。Owner同操作3次失败后于20:30:02自动停止，未进入Material Supply/Rights/Match/Readiness。

**MATERIAL_E2E=FAIL，AUTONOMOUS_EXECUTION=YES，AUTONOMOUS_DELIVERY=NO。** 正式覆盖未建立，草稿9required/1optional、准入0/9仅供参考。Creation入口至停止20分15秒，确认后16分05秒；方案Agent3、Delivery Agent9（Preparation1/Planning1/既有修复7），素材Provider/生成0，占额¥0/¥10，模型及总账单未知。运行中工程干预0，未开发、人工补证/Retry/放行或进入Authoring/Build/Quality。固定源码、11项handoff/4项snapshot/3份确认规划文本与14个旧Creation均不变，原两轮FAIL全部保留；请求终态released、网关active0/queued0。详见[第二次独立验收记录](acceptance/material-independent-e2e-2-2026-10-06.md)。下方软件回归通过不扩大为本轮自主验收成功。

## Planning → Material 合同断口修复（2026-10-06，软件前置通过）

以 cr_94b5d27f5fb140de85981cecba009a9d / fa_2368857a95b3c017098064d189ce84e4 的原始两份 Planning JSON 字节作确定性 fixture。canonical 仍为全部视觉 Need ID → {clauses,queries}：Planning producer 包装数组/音频混入是直接偏离；程序侧另有查询 metadata 误入视觉原文和同轮缓存键不一致。初始与 repair 共用正式 schema；入口严格转换本次具名结构、已知路径/空引用及单向等长引号漂移，绑定冻结原文，只补完整缺失的显式软偏好；必要条款缺失/改词/部分覆盖及偏好升级仍拒绝。producer/consumer 共用缓存键，旧键重验复用，坏新键不得绕过。

**7 visual、8 required / 3 optional、4 audio 全部保留，无额外 Planning/repair/分类调用完成本次结构处理。** 248 项相关回归、115 技能合同、compileall/diff check 通过，Astra 前置及最终 CONTINUE。Material V1.3 语义与 canonical 输出未变，新增严格具名输入适配；READY_FOR_NEW_MATERIAL_E2E=YES 仅指软件前置通过。原失败文件字节、Need/importance/创作语义及 failed 终态保持，未重载服务、恢复 E2E、调用 Provider/生成或进入视频。证据见[原运行记录的后续软件修复节](acceptance/material-independent-e2e-2026-10-06.md#后续-planning--material-合同软件修复2026-10-06)。

## 当前独立 Material E2E（2026-10-06，FAIL / Planning 自动停止）

用户另行启动一次当前版本的新Creation独立素材验收：主工作区easel-studio HEAD5919a9de，生产源码集合SHA d1ed4ec4c2944b4f488cbeecc07208696ece0a176405393fe5c97f1a296ba016；新作品cr_94b5d27f5fb140de85981cecba009a9d / Attempt fa_2368857a95b3c017098064d189ce84e4。在新Creation创建前核对无活动/未知执行并加载现有Web及网关；正常对话与第3版画布确认，独立预算¥10，正式终点MATERIAL_READY。Preparation真实通过；Planning草稿schema经系统结构修复有效，但要求文件使用包装对象/visual_requirements数组，而正式根对象须以全部视觉Need ID作键，连续3次失败后原Owner自动停止。

**MATERIAL_E2E=FAIL，未进入Material Supply、未达到MATERIAL_READY。** 草稿8required（6视觉+旁白+BGM）、3optional，正式Plan/覆盖报告未成立，不将草稿0/8伪装成正式Readiness。正常方案派发3、Delivery Agent4、素材Provider/生成0，占额¥0/¥10，模型实际账单未知。入口至停止12分55秒，确认后10分15秒。正式确认后工程干预0；AUTONOMOUS=YES仅指全程系统执行，不表示自主达到终点。冻结输入/源码/旧作品记录不变；Agent全部终态released、无未知采购；Authoring/Build/Quality未派发。保留失败现场，不修复、不人工Retry，不自动第二次验收。详见[本次独立运行记录](acceptance/material-independent-e2e-2026-10-06.md)。下方原作品工程恢复的9/9历史不被倒算成本次结果。

## BGM 放宽后的原作品素材齐备（2026-10-06，MATERIAL_READY / 9 of 9）

按用户“放宽审核标准，不然一直推进不下去”的授权，固定现有AST与bgm-practical@4（Music0.5、19类声乐上限0.02；低音乐/静音/实际时间覆盖及身份合同仍检查）。原Owner重评既有报告后，经普通Rights/Match/Readiness达到 **9/9 required、MATERIAL_READY**；Delivery为material_ready，blocking为空，恢复journal/projection均COMPLETE。只认领该原作品一次受限恢复，不宣称通用声音能力合格。

v3/v4预登记独立留出均器乐3/6，广泛能力验收FAILED保留。v4已观察校准10/12、正常负例0/36，新来源留出正常0/10；0.5秒混入校准漏检6/16。当前10秒AST窗口不构成5秒过渡定位能力。全量709 passed、5 skipped（43.18秒，独立worktree合成画像）、115合同/compileall/diff及Astra CONTINUE；主工作区8个恢复场景复验通过。正常FirstCut链插队曾在全量发现，已修正并复跑通过。

原作品 `cr_77175a2271bf4e408a359884efc438e6` / Attempt `fa_22f91d9f97ab6e7c355d46ba87bb478b`，Plan revision不变，Bundle更新为 `cfb5d6fb92094c95208a4fa2106764c22cebbde1e803312ceaf8e6a1dad7dcb8`。BGM SHA/原50窗报告/CC BY4.0署名条件保留，19类最大声乐0.001360、Music最低0.526289。R17动作0.592420秒，仅本地复用报告；18冻结输入、46份素材字节/Rights、生成记录/预算、原失败及历史保留，Prepare7/24、Material148/1840、生成占额0.1798/10不变。零新搜索/下载/推理/Provider/生成调用。无分离模型安装或使用。

Web已加载主工作区commit43d2eb56；未派发Authoring/Build，execution=NOT_SUBMITTED，outputs为空，网关/Hypit未重启。**AUTONOMOUS=NO**，工程恢复不等于首版视频交付或端到端提速。下一顺序为视频流程软件整合与另行启动窄路线视频阶段。详见[原恢复记录R17](acceptance/creation-latency-v05-material-resume-2026-10-05.md#r17-用户放宽-bgm-审核后的原作品受限恢复material_ready--9-of-9)及[策略/失败/最终对账](acceptance/fixtures/bgm-practical-recovery-2026-10-06.json)。以下旧分段均保留当时状态，不覆盖本节。

## 已确认创作方案的规划恢复修复（2026-10-05，软件验证）

Planning 模型曾将已确认声音段从 TREATMENT 移到 SCENES；原确认校验准确，但四文件写入提示与只读要求冲突，且 write-if-missing 不能恢复错误草稿。现在确认三文件由程序单一 canonical 映射原样提供，未提交差异先以内容 hash 原子归档再原子恢复；首次输出、一次 repair 和中断重入共用恢复。初始/repair 只要求素材 JSON，不让模型重写确认文案。冻结规划差异、异常文件类型/目录 symlink 及历史字节不符仍拒绝，文件系统错误不触发新模型修复。

已有 Planning 集成场景扩展覆盖两轮移动声音、错误草稿归档/重复去重、有效 Plan 重入零模型调用、冻结拒绝、文件/模型返回后目录 symlink 拒绝；原无确认作品仍正常四文件交付。Astra 最终 CONTINUE。未改实际作品文件、未重启服务、未调用真实模型或恢复制作。最终验证及现场根因见[具名记录](acceptance/confirmed-planning-recovery-2026-10-05.md)。

## 双窗口执行入口（2026-10-05，任务拆分，不是新增验收）

用户要求分别设置两个独立目标，实施入口已拆为 [BGM 验证与素材齐备](tasks/creation-bgm-readiness-2026-10-05.md) 和 [视频流程软件优化](tasks/creation-video-flow-software-2026-10-05.md)；[原方案](tasks/creation-latency-2026-10-02.md)保留总顺序、共同约束和汇合条件。两个目标使用独立 worktree，共同文件在分支整合时合并，主工作区状态统一更新。BGM 目标负责原作品/服务/运行记录；视频目标仅交付软件改动与确定性证据，真实制作仍后置。本次只拆文档，未创建窗口、设置新目标或启动第二执行器；此前声音能力失败和原作品 8/9 保持。

## v0.6 BGM 首轮能力验收（2026-10-05，CALIBRATION_FAILED）

按[后续 Task](tasks/creation-latency-2026-10-02.md)执行 G0，本机模型三个摘要和 527 标签核对一致；建立 32 个来源/标注/许可固定的基础样本与 32 个短语音混音，校准与留出按来源隔离。只观察校准 32 项，原作品音乐未用于调参，留出 32 项保持未观察。

旧规则及仅补标签 A 均为器乐 1/6 合格、负例误放行 5/26；B 可到器乐 5/6，但仍误放行 5/26。文档允许的一项辅助比较复用已安装 faster-whisper 的 Silero VAD：零误放行时最多 4/6 器乐，通过至少 5/6 器乐时误放行至少 4/26。没有可选生产规则，已触发停止条件，G1/G2 未启动。另复现生产报告 NaN 时长未被拒绝，列入后续局部验证范围，当前未改生产模块。

新增单一离线校准/媒体重建工具；64 个媒体重建 SHA 全部一致，两轮数值回放逐项一致，8 项隔离技术反例拒绝、现有声音供给回归 4 passed、脚本 compileall 与 diff check 通过。原作品仍 **8/9 / MATERIAL_NOT_READY**、唯一缺口 bgm_subordinate；Owner 仍 material_supply_exhausted。没有安装模型、恢复服务/作品、修改运行产物/账本、调用付费 Provider 或进入 Authoring/Build。详情与有限样本的适用边界见[唯一能力验收](acceptance/creation-latency-v06-bgm-calibration-2026-10-05.md)。下一步需重新确定声音能力/证据路径，不能仅降低阈值接续。

## v0.6 方案修订与新增风险（2026-10-05，研究/方案，未实施）

本节保留此前方案阶段的记录；当前执行结果以顶部 G0 能力验收为准。

用户要求对照 OpenMontage 并搜索 GitHub 后完善方案，允许合理移植代码；固定提交源码、采用/排除理由及已完成研究现保存在[历史归档](tasks/creation-latency-completed-2026-10-05.md)；[后续 Task](tasks/creation-latency-2026-10-02.md)仅保留 BGM 校准样本与留出门、最小代码落点、规则版本/缓存迁移和 G0–G4 验收顺序。保留现主链，先能力验证再自动化，不新增运行时依赖或并行 Task。

本次源码核对发现当前 `VOCAL_LABELS` 漏掉模型已有的 Choir、A capella、Yodeling、Mantra。隔离合同反例 Music=.95 / Choir=.99 / 现有 vocal=.001 被判 instrumental_music；这是标签覆盖缺口，**不是当前 BGM 有声乐的实测结论**。原始报告与派生准入还须分别绑定模型/输入和 policy revision，避免同报告 digest 阻止新规则重评。以上尚未修复或真实校准，不能直接降低 Music 阈值。

当前作品仍为下述 R16 **8/9 / MATERIAL_NOT_READY**；701/5 为此前验证。本轮仅改方案/状态路由，未改运行代码、装模型、恢复作品、花费预算或启动 Authoring/Build。后续先执行 G0 的标签、预处理、固定正反样本与独立留出验证，再决定 G1 的最小规则调整。


## v0.5 当前素材恢复（2026-10-05，PARTIAL / 8 of 9 / 音频验证未确认）

七项视觉及旁白均已普通准入，唯一缺口BGM；尚未MATERIAL_READY，原Owner无可继续策略后停止。R14揭示Top3获取HTTP403；补真实User-Agent后R15取得1音频/20候选，其余获取失败，不认领DNS或UA为全部失败唯一根因。R16修复Openverse单曲许可/署名事实丢失及Commons查询身份脱敏；同asset/SHA刷新元数据，不重搜/下载、不写人工reviewed_at，普通CC BY条件保留。

R16原Owner观察动作24.773932秒；新增仅元数据1+本地音乐观察1。50窗音乐最低0.526289、均值0.75490602，34窗低于当前每窗0.8；人声最大0.001171。普通报告unknown/PARTIAL，**音频验证未确认**，不是报告/搜索/权利失败。没有凭标题或低人声放行，也没有把unknown当不适合盲重试。当前material_supply_exhausted指无已获批新策略，不等于模型已确认素材不适合。下一缺口是音乐性验证与其证据校准，不能仅为齐备放宽准入；已批准旁白有限放宽不转授BGM。

全量701 passed、5 skipped（47.75秒），compileall、115合同、diff check及Astra CONTINUE；成功事实落盘前持久观察PENDING，保证中断后音乐/Gate接续且不重取metadata。MATERIAL_READY终点禁止普通重评提前prepare Authoring。最终Prepare7/24、Material148/1840、五项生成complete、占额0.1798/10保持，实际总账单unknown；18项冻结输入不变、请求已终态释放、Owner空闲、网关active0/queued0。仅Web加载修复，网关/Hypit未重启，没有Authoring/Build/视频结果。整个诊断AUTONOMOUS=NO，8/9不算验收成功，不承诺提速比例。[唯一恢复记录](acceptance/creation-latency-v05-material-resume-2026-10-05.md)保留R1–R16失败与实际效果；以下旧分段为历史。

## v0.5 报告合同根因修复（2026-10-05，R11 FAILED / 6 of 9）

R3的三次“视觉派发”实际停在要求编译，未看图：MiniMax-M3 OpenAI原生thinking默认开启，通用off未映射原生参数，输出额度被占而length无正文。官方合同、安装wire模拟及两项计量能力验证核实，M3专用幂等配置脚本修复原生thinking.disabled并热加载，网关未重启。随后R4旧会话NO_REPLY，增加失败会话策略身份及原一次报告修复，有效缓存不丢弃。

R5完整JSON仍因模型计数偏移错误及围栏拒绝；改为逐段引用、程序绑定真实位置。R6又暴露编译输入重复完整Need和sources、编号未显式：模型重复列段及从1编号，完整覆盖校验拒绝。现最小修复只传带0基编号的单份原文，完整冻结身份仍绑定；原分类、偏好、Rights/Match/Readiness不放宽。报告故障不得当缺素材转生图。R7编号及引用已正确，提示的裸kind形状示例又导致null/非法JSON；已改合法JSON对象示例，不猜无效分类。

R8已真实看图但模型把偏好列入checks及partly_met，R9把重复主体的显式偏好升级/误判歧义。现观察名单显式、偏好无检查编号；显式preferred由程序原文登记，模型只解释混合intent，完整校验保持。叙事/剪辑职责不编造源动态，真实动作与证据仍必要。

R10 C普通准入通过；最新真实Gate为6/9，D/F+BGM未覆盖，Material128/1840、Prepare7/24；5项生成complete及占额0.1798/10保留，18冻结输入不变。R4–R9报告失败、R10部分成功、R11报告失败均保留，没有Authoring/Build；整个诊断不能认领自主完成或提速比例。多补位排队的进度/Owner旧投影曾漏接续，已统一真实待准入判断，旧stock账本不增加。D逐字复制仍不可靠，最终改为程序无损切分/固定id，模型只分类及短query，全文/必要边界严格校验。用户已授权修复后继续，下一段在确定性验证及原请求/账本对账后正式恢复同作品R12，终点MATERIAL_READY。[唯一恢复记录](acceptance/creation-latency-v05-material-resume-2026-10-05.md)保存各段失败及根因，旧记录不改写。

## v0.5 调度修复与素材恢复（2026-10-05，软件通过 / R3 FAILED / 5 of 9）

用户批准空观察循环和旁白误入BGM修复并恢复原作品。已共用重评集合、跳过已覆盖及当前版本完成重评，既有关联重评不占新候选额度，不能执行明确失败；已知旁白从音乐候选排除。R2暴露绑定新生成准入仍被旧图库额度阻挡，保留C/D/F三张完成图及原在途补料请求后监护停止，补齐原Need绑定generated_intakes，不增/清零图库associations，普通准入与累计授权边界保持。全量682 passed、5 skipped（41.29秒），compileall/115合同/diff check通过。

R3于08:22:20恢复，08:27:04达到3次真实视觉失败上限自动停止，墙钟约4分44秒，仍5/9 / MATERIAL_NOT_READY。C补位图已进入普通观察，但MiniMax-M3三次均stopReason=length、payloads=0，没有有效新报告；D/F未完成观察，BGM无正式合格。新增来源适配8+视觉3，Material107/1840，Prepare7/24；视觉运行总251.432秒含模型/网关等待。没有新增生图、ASR/TTS或音乐观察，旁白误派已消除。占额仍¥0.1798，余额¥9.8202，实际账单unknown。不是搜索不到视觉或生图失败；报告交付是当前主阻塞。

源码SHA `1d5b2af35441892ab9671542b59d37f837efcf3b1ac07d56505dd223c2ef4443`、18冻结输入保持；仅Web加载修复，网关/Hypit未重启，最终网关active0/queued0、请求已终态释放，Owner保存exhausted_operation。R3无现场工程救场且自主有界停止，但未自主完成；整个R1–R3诊断不认领AUTONOMOUS或提速成功。没有Authoring/Build；原Task §12.11及[统一恢复记录](acceptance/creation-latency-v05-material-resume-2026-10-05.md)保留各段证据。下一范围为真实报告输出容量/截断与交付合同定位及有限能力验证，当前不扩大修改或继续retry。

## v0.5 素材正式恢复（2026-10-05，FAILED / 5 of 9 / 已监护停止）

用户授权沿真实Planning和原Delivery Owner继续独立素材验收，终点仅MATERIAL_READY。本次使用提交964104fe，确认无活动/未知提交后仅Web加载已提交版本；网关/Hypit未重启。同Creation/Attempt及冻结Plan保留，07:57:18恢复，08:00:10因无进展循环请求监护停止，08:00:15确认stopped。详见[恢复验收记录](acceptance/creation-latency-v05-material-resume-2026-10-05.md)。

旁白复用原识别/字幕完成普通准入，required从4/9到5/9；C/D/F及BGM仍缺，Gate MATERIAL_NOT_READY。Owner新增55次observe（累计31.983872秒，主要空观察）和1次声音恢复（0.214511秒）；新增计量只有本地音乐观察1次，Material89/1840，Prepare7/24。新搜索/云端视觉/ASR/TTS/生图提交均0，占额仍¥0.1048，余额¥9.8952，实际账单unknown。

根因已定位：待重评优先调度不校验可执行性，并包含已覆盖Need旧负面报告；执行器又让重评受耗尽的历史新候选关联额度约束，空批返回COMPLETE而pending不变，故无限重派且阻挡补料/生成。另有已知旁白误入BGM观察的用途过滤缺口。监护只设置停止控制位，无运行中代码救场或改审核，但AUTONOMOUS=NO；2分52秒停止不是齐备或提速，报告/搜索/生图真实效果未验证。18项冻结文件及源码SHA不变，没有Authoring/Build。下一步最小修复及回归范围已记原Task §12.11，当前未实施，不自动恢复。

## v0.5 实测根因修复（2026-10-05，软件通过 / 真实能力未验收）

用户要求设定目标并按收敛方案修复，已实施[原 Task §12.10.9](tasks/creation-latency-completed-2026-10-05.md#12109-2026-10-05-获批软件修复验证与剩余能力门)。历史 84 分 38 秒中，51 次视觉请求累计约 66 分 09 秒，来源适配自身累计约 17 秒；主要是无关联候选跨 Need 提名、批后切换迟滞、偏好误拒、partial 阻止合法补位及报告交付故障，不能只归因模型慢。真实结果仍为 4/9 / PARTIAL / 已停止，不能认领素材齐备或提速。

软件已改：要求合同完整绑定冻结输入，明确必要项/偏好/后期职责；沿原 agent.wait(runId) 接收最多 3000 UTF-16 单位紧凑结果，系统组装保存普通观察，原结果中断可恢复，截断/错 run 不扩搜索或生成。来源/实际 query/排名及字节去重关联持久保存，每次最多两张不同素材后返回原 Owner 重算；仅有依据才跨 Need 提名，一次全计划无语义探索，跨池关联不清零。同 Need/query 的来源收益不污染其他 Need；优先已编译变体，旁白不再搜索图库朗读指令。

硬缺失 partial 可支持合法图片补位，unknown/Rights/报告故障本身不能；绑定生成先服务其原 Need，不重开全池。预留全部剩余允许生图 Need 的工作容量，沿原调用/费用账本不重置。MiniMax 官方字幕合同已核对，增加整段精确、唯一的原文/去换行索引映射并保留原字幕；同条件 ASR 正负缓存复用。用户之后取消备用模型并允许当前模型有限放宽，具体规则见下段；未通过现规则时仍明确 `needs_audio_verification`，保留音频、不重购或重复全文识别。BGM 未明权利不做昂贵声音观察，作者/单曲来源/完整署名仍须正式事实入口核实，没有修改当前记录。

确定性全量 **672 passed、5 skipped（38.75 秒）**；compileall、115 项合同、前端投影、lint/build、diff check 通过，仅既有依赖/hook/包体提示。回放中的模型/Provider/renderer 均为 fake，不是实际素材或成片验收。原 Task/顺序已同步；没有新建平行 Task、接新图库、重启服务、恢复作品、调用真实模型/Provider、使用 10 元授权或执行 E2E/Build；历史 Acceptance 不改写，运行中服务不认领加载新代码。

最新声音规则（用户已批准，[原 Task §12.10.10](tasks/creation-latency-completed-2026-10-05.md#121010-当前声音模型的有限放宽用户已批准2026-10-05)）：不下载/切换模型，不再等待备用资源决定。保留全部词≥0.5原路径；全文逐字一致、无增删且实际时间完整有效时，允许最低词≥0.25、低于0.5的字符≤全文5%且最多3字、按字符加权均值≥0.85的有限路径。普通内容/时序/生成Rights/Match共用规则，保留原概率；失败身份包含新规则，原primary识别缓存仍复用，旧失败不删除，当前Owner不派发备用模型。只读当前保存报告（含脚本/Need/音频SHA核对）95字一致、低置信1字、最低约0.282、加权均值约0.988，满足新规则；只在内存判断，未正式登记或更新Gate，历史4/9不改。BGM许可及音乐/人声规则不放宽。

本次声音增量全量 **682 passed、5 skipped（42.52秒）**，保护低分/比例/绝对量/均值边界、错字/漏字/增字/时间及旧拒绝+中断恢复零新ASR/TTS；compileall、115项合同及diff check通过，无前端代码修改。没有下载、真实推理、费用、重启、恢复、E2E/Build。不能以保存报告的只读新规则通过认领旁白已正式准入或BGM合格。下一顺序为有限真实报告和声音能力验证 → 另行允许加载及复核 → 同 Attempt 至9/9 MATERIAL_READY；完整视频后置，无同条件提速比例。

## Planning 工具消失根因修复（2026-10-04，未重启）

用户授权修复根因但明确不重启。本次只读具名 Planning 会话与 OpenClaw 2026.9.4 源码，确认首个 `length` 在四次 `write` 失败之前；对应网关日志明确记录同 run 的 `running isolated finalization` 及 `reported capability activity`。`resolveSettledToolTerminalContinuationInstruction` 回溯前一批已结束工具，未排除当前 assistant 已截断，错误进入 `runPreparedSettledTurnFinalization(disableTools=true)`，导致后续写文件工具不可用。不是文件系统写权限或全局 write 禁用；单纯建议换 exec 也无法在该无工具阶段解决问题。

已增加版本限定、幂等且保留原文件备份的离线修复脚本 `scripts/patch_openclaw_finalization.py`，并应用到本机安装版 OpenClaw 2026.9.4 的 `builtin-openclaw-B-H-7lKk.mjs`：当前 attempt 的 assistant 为 `stopReason=length` 时拒绝无工具最终回复阶段，交回原终态/有界恢复处理；正常 stop/toolUse 的收尾不变。不开放额外工具，不重复执行原工具，不修改正式 Planning 文件、Gate、授权或累计额度。

已安装文件 SHA 从 `0a8c813e535c92d03f69bc58381518ba0e6ac6e46f3adda54138c5f668340ea8` 变为 `654bb2d9753e0a354320a70bdb96a120e9d5c0780e3d76f0e69bf08f4e2dd6d6`；同目录 `.easel-finalization-original` 保存原文件。源码仓库保存可复现脚本及上游判断函数回归夹具，不将整套安装包纳入 Git。依赖升级后需重新核对，不自动对未知版本打补丁。

离线回归 **2 passed**：重现原错误分支、修复后截断拒绝、正常收尾保持、幂等/备份/版本拒绝；既有 Planning/Gateway 局部 **14 passed, 50 deselected**；安装包 `node --check` 与 diff check 通过。无真实模型/Provider/Build 调用。**补丁仅落盘，未重启 Web、网关或 Hypit，未恢复作品；运行中服务是否加载新模块不作成功声明，真实效果待后续允许加载后的验收。** 输出长度不足本身仍可能发生，不宣称 Planning 已稳定完成；历史失败保留。

## v0.5 正常对话 → 真实规划 → 素材齐备验收（2026-10-04，PARTIAL，已停止）

唯一新作品 `cr_77175a2271bf4e408a359884efc438e6` 来自正常对话方案第2版，21:27:53正式确认；Attempt `fa_22f91d9f97ab6e7c355d46ba87bb478b`。Preparation/Planning/Script Truth 已真实通过，Plan `plan-6e7c355d46ba87bb478b` revision `5e83f86c1486cfe88030ef5be47d35683a43e1faad3037e416ebe30b98593846`：7required视觉、required旁白及BGM，共9项。本次新预算10元独立绑定，旧授权不转授。终点在确认前正式持久设置并原子继承 `MATERIAL_READY`，未派发Authoring/Build/Quality。

独立运行在Planning失败，随后发生D1规划最小落盘提示修复、D2共享报告身份具名/持久单次修复、D3新生成结果先准入不重开旧池、D4补料证据摘要压缩/先保存最小报告；全部原失败保留，本轮只能认领诊断结果，AUTONOMOUS=NO。素材入口21:43:21；最终4/9覆盖（A/B复用一张Pexels、E/G共用一张MiniMax生成图片），余C/D/F、旁白、BGM仍缺。图片1次+预置旁白1次，正式占额¥0.1048/¥10，剩余额度¥9.8952，实际账单未知。恢复不清零调用或费用，不手改输入/审核/数据库。

最近加载Easel源码集合SHA `00e19009a32b084c0a16cba4172557171bdc0bd0502a452ceb63519293694c78`。必要全量646passed、5skipped（42.53s），局部身份恢复8passed、生成准入/停止12passed、补料恢复10passed，技能合同/compileall/frontend lint/build/diffcheck通过。素材入口21:43:21→23:07:59停止，共84分38秒，均属D1工程介入后的诊断素材阶段。最终阻塞为旁白本机ASR第6个有效字符置信度0.282<0.500；3次本地恢复后Owner正式停止，原27.18秒音频保留、未重购，内容/时序与Rights尚未准入。当前仅一套本机ASR模型，没有已安装替代能力；不降阈值、手改结论或用人工认读救场。BGM仍缺音乐适用/可核实署名条件，C/D/F未覆盖。累计Prepare7/24、Material88/1840（来源适配26、视觉请求51、补料建议3、报价/提交各2、本机音乐1、旁白3），117个逐Need有效视觉判断。无未知请求、无视频制作派发；真实未齐备、未宣称提速或自主通过。唯一事实记录：[v0.5 Material E2E](acceptance/creation-latency-v05-material-e2e-2026-10-04.md)，原Task §12.8。

## 本次 v0.4 独立验收与诊断（2026-10-04，已停止）

唯一新作品 `cr_8499196003b141e8bf326c35e3b28c44` 的固定基线独立 E2E **FAILED**；09:27:55 确认后停在素材审核，未 Build。D1/D2/D3 仅改观察提示的报告保存、偏好/后期效果职责及 related 合同含义；Gate、validator 与正式产物未改，现有 12 项局部回归通过。两次正式画布恢复、三次 Web 安全重载后仍未交付，不能记自主通过或稳定修复。当前源码 SHA `5b1c7947d18a9be8da2e5cca8072ea4d6ede0a70e70228dda5a5a7a06edb2f9d`，Web PID37110。

10:49:50 最终停止，素材累计 83/1636，prepare 5/24；43 次制作网关派发包含 37 次视觉观察，44 次 Provider 适配器检索计数不等于实际 HTTP 次数。86 条已保存判断中 67 unsuitable、19 partial，0 正式合格覆盖，8 项 required Need 仍缺。无未知提交/待释放调用；有效成果保留，临时防休眠已结束。10 元预算有效，无生成提交/核价占用；模型账单未知，不能称总费用为零。

剩余阻塞：报告结论与逐帧字段矛盾仍无法稳定修复；偏好/后期效果仍可能被误设为门槛；预算已授权但冻结 Brief 与画面 Need 不允许生成，权限意图传递待核实，不自行解禁。无首版，Voice/Production/Quality 效果未验收，不再盲重试，不自动第二作品。仅更新原 Task 和 [唯一运行记录](acceptance/creation-latency-v04-e2e-2026-10-03.md)，没有同条件基线或提速比例。

方案衔接（2026-10-04）：用户已批准唯一 [Task §1/§6.1/§12](tasks/creation-latency-completed-2026-10-05.md#12-v05-素材层可靠供给与耗时优化方案) 的 v0.5 软件实施与确定性验证；不重启旧任务，不恢复作品，不进行真实模型、素材采购、Material E2E 或 Build。原作品 10 元授权绑定不变，本轮未使用。以下软件结果不改写上述 FAILED。

## v0.5 素材可靠供给与耗时优化（2026-10-04，软件收口）

原 Task §12.7 记录 S1/S2/S3 三项实施及依赖，未新增平行方案：

- **A1/A2：** 逐帧主体相关性与完整适用性分离，硬条件冲突的相关图片可正常保存负面报告；unknown 与报告合同故障继续区分。旧 @2 报告兼容，有效正面与明确硬冲突/内容错配不重做。Owner 自动识别可追溯的旧偏好或静帧后期镜头误拒，只重新观察受影响关联，历史报告保留；无法识别的旧负面证据不自动推翻。静帧无需完成镜头运动，必要主体、表达及硬要求不放宽。
- **A3：** Preparation/Planning 明确补位内容许可与费用授权不同，默认格式示例不能吞掉用户明确许可；冻结 Brief hash 与 Need 许可冲突直接拒绝，缺冻结文件不能从草稿重造授权。图片补位只针对当前允许静态表达的真实缺口，逐 Need 负面报告及字节、成功供料/查询、已完成观察均须有效。真实证据/身份、源动态要求、禁令、未观察或缺证、Rights 待解决、未知提交和空间不足不自动购买。继续使用原图片 Adapter、核价/占额/请求身份及技术 intake→观察→Rights→Match→Readiness。
- **B1/B2：** 中文原意和硬约束保留，Planning 提供 provider-neutral 英文主体短语，Compiler 英文优先且不截断语义；沿现有 Pexels/Pixabay/Openverse Audio 获取路径，每批一个外部来源并按已拒批次切换。查询结果按来源/输入缓存，成功空结果也复用；恢复不重复已得素材/有效观察，不清总账。跨来源按字节去重，新增有效 Rights 证据保留。现有小批提名上限与有效拒绝可作为低收益依据，不能要求全池交叉审核或穷尽全部来源才生成；仍有更有依据候选时先看小批。为生图及验证保守预留 5 次调用，不提高额度。记录 query/来源/调用耗时、缓存、重复字节、覆盖、缺口和费用预占；估计时间及实际账单未核实为 unknown。
- **独立素材终点：** 正式 Operator API `POST /api/creations/{id}/delivery/material-endpoint` 在制作/未知执行开始前持久设置原 Delivery Owner 的 `MATERIAL_READY` 终点。必要观察及当前 Gate 验证完成后自动停止，保存真实素材验收结果；不派发 Authoring、Runtime/Build 或 Quality。`film_delivery_complete=false`，页面显示“素材已就绪 · 本轮已停止”，视频制作及成片阶段仍等待，Creation 不记整片 ready。默认整片委托行为保留。

**确定性验证：** 搜索满足后零生成且停止；一次假生图经完整普通准入达到 READY 后停止；禁止/动态/真实身份/缺授权/报告故障/输入变化/验证空间不足不提交；有效负面保存、中断/费用/未知提交、累计额度、跨内容旧链及受影响重评/历史保留均有 Fixture 或局部 Replay。前端状态投影确认素材完成而成片未完成。最终全量 **644 passed, 5 skipped（43.81s）**，compileall、115 项 skill/publisher 合同、diff check、Creator 状态投影和 frontend lint/build 通过；仅既有两项 Python 依赖提示、Hook 与构建体积提示。未调用真实模型、Provider 采购或视频 Build。

`SOFTWARE=PASS / SOFTWARE_ACCEPTED`。`READY_FOR_MATERIAL_E2E=YES` 仅表示软件入口和停止边界已验证；真实验收尚未执行。下一步须单独核对正式 Planning 输入、Creation/Attempt/许可/预算绑定、剩余额度及未知执行后由用户启动。10 元不能转授新作品，不预先承诺提速比例；真实足量召回、模型判断可靠性、生成适用性及实际耗时仍待验证。软件完成后停止。

## Snapshot

| Area | Current status |
|---|---|
| Product | Official `ai-film` Web path is connected through Material Gate, Hypit authoring/execution, and Easel output review. 唯一自主首版 Task 的本轮软件范围已完成；整体 V1 的真实自主交付与跨内容效果仍为 **PARTIAL / REAL_WORLD_NOT_VERIFIED**。 |
| Material Layer | P0/INT/P1 supply contracts are software accepted. MiniMax Image/Video/preset-voice TTS and ordinary Gate are software connected; isolated outputs passed technical inspection. 新委托预置旁白及文字生成图片/视频在用途声明、已审核条款、请求身份与实际观察证据齐全时，可按本作品内部用途自动准入；缺证仍为 UNKNOWN，旧文字声明不扩权。完整真实 Creation/Production 使用未验收。 |
| Local visual Product E2E | **REAL_WORLD_VERIFIED** for one named Creation through human-approved Selected Output; it does not establish full V1 or multi-Content consistency. |
| External Material Product E2E | **REAL_WORLD_VERIFIED** for one standard-chat Creation through Pexels Search/Acquisition, MaterialReadiness `READY`, Production Authoring, Hypit Build, Export, Review and Selected Output. The [named Acceptance](acceptance/external-material-product-e2e-2026-09-29.md) records the initial MaterialReadiness stop; the same Creation was subsequently completed. |
| Runtime profiles | `generation` is **READY** (configuration only). `v1-release` is **NOT_READY**: model auth/endpoint and `audio.production` require live verification. 本机旁白识别与配乐观察的离线依赖/模型预检已通过，不能据此代替真实声音效果验收。 Hypit 0.2.7 doctor, Runtime Worker and both local Programs are ready. |
| P3 | **NOT_STARTED**. |
| Test suite | Latest complete deterministic run: **644 passed, 5 skipped** on 2026-10-04（v0.5 软件实施，43.81s）. compileall、115 项 skill/publisher 合同、diff check、Creator 状态投影及 frontend lint/build 通过。包含隔离跨内容回放、两种素材终点与生图边界；未运行真实 E2E、付费生成或视频 Build。既有 dependency/Hook/chunk-size 提示保留。 |


## 创作临时网关环境释放修复（2026-10-03）

- 用户要求删除本次失败创作数据并修复未释放的根因，范围见 [修复 Task](tasks/creation-runtime-release-2026-10-03.md)。真实日志确认网关 MCP 活跃环境达到 256 上限；安装版 OpenClaw **2026.9.4** 按会话保留环境，空闲回收默认 0，本机该配置此前未设置。Easel 持久保存视觉核验终态后未释放临时环境，独立核验会话累积。
- Delivery Agent 提交前保存作品专属会话/agent 身份。只有带结束时间且非 yield 的 `ok/error` 终态才调用正式 `sessions.abort(key, agentId, clearQueued=true)` 等待 MCP retirement，保留历史与成功产物；未知执行继续观察同一 run。先持久保存待清理，网关确认无活跃运行后标已释放；响应丢失或无效时，原 `observe_agent` 接续清理后才继续。停止、修改方案或交付后仍核对原有未知执行并接续终态清理，不派发新工作；已结束运行不因清理失败重新提交。
- 环境上限错误保存白名单中文分类，不保存原始响应或凭证。未改变 Material V1.3、素材适用、Truth/Rights、费用或 Build 准入，也未实施待审阅的三步耗时方案。
- 本机隔离 easel profile 已设置 `mcp.sessionIdleTtlMs=300000`，网关日志确认热加载；该值是本机空闲回收兜底，不代表其他安装已配置。确认其他作品无活跃执行后，Web 服务已平滑重启加载修复，`/api/status` 返回 200；没有重启网关、调用模型或启动制作。
- 本次失败作品数据已按授权删除：**93 个专属网关会话及其 SQLite transcript 归档、101 条终态任务及 delivery state、571 条对应 audit 记录**，以及 Creation、Attempt workspace、聊天绑定、独立快照/任务事件和相关原始流/日志。检查专属路径、网关列表、绑定和数据库引用；保留其他作品、共享素材库和配置。仅保留本条不含作品内容/身份的故障与修复摘要，不保留素材或提示正文。
- 全量确定性 **617 passed, 5 skipped（38.19s）**；Preparation/隔离 Authoring **80 passed**；yield Fixture 补强后网关局部 **6 passed**。覆盖终态释放、停止后仍核对原执行、未知/yield 不释放、清理中断接续、错误网关拒绝、缓存成功不重跑、失败分类脱敏及隔离产物提升。compileall、115 项 skill/publisher 合同和 diff check 通过，仅既有两项 Python 依赖提示。本批无前端代码修改，未重复前端构建；为 **SOFTWARE_ACCEPTED**，未通过真实模型调用验收新作品交付或素材匹配效果。

## 创作耗时优化：首批（2026-10-02）

- **2026-10-03 v0.4 软件完成：** 用户批准唯一 [历史 Task](tasks/creation-latency-completed-2026-10-05.md) 的软件实施；当前为 **APPROVED / SOFTWARE_ACCEPTED / REAL_WORLD_NOT_VERIFIED**。按 §4.1 分段完成累计派发额度与请求历史、查询/Provider 限制、明确混杂旁白的确认拦截、已观察取片整数边界、初次编排必要表达承担项、已核实识别词边界字幕分组，以及有界 Quality 新时点补证与局部报告恢复。R1/R2 只核实和回归，不重复开发；Material V1.3、Truth/Rights、费用及 Quality 文字/时序/依赖权限未改变。3A/3B 等仍延期。
- **本批确定性结果：** 全量 **632 passed、5 skipped（39.08s）**，局部六文件 **214 passed**，最后五个关键回归 **5 passed**，最终 Provider 选词记录清理后的局部 **108 passed（8.49s）**；compileall、115 项 skill/publisher 合同及 diff check 通过，既有两项依赖弃用提示。当前安装 Hypit 原生文字 Area 与实测字幕组合的实际静态 check 成功；无 Build/Runtime/真实模型。确认稿/Truth、候选接续、共享观察中断、合格后停止、正式选择/越界、未知提交对账及返修受保护输入继续回归。重复同证据补看、已保存报告重审、错误重派覆盖原 run 历史等具体风险已由局部证据保护，不代表真实误判率或端到端耗时通过。
- **1A 生效边界：** 原 Creation Delivery 持久阶段额度在派发前预占；网关初次/补证/报告修复/明确故障重派、Provider 适配检索、本地声音新观察及生成报价/新提交累计，轮询/清理/有效结果读取不计。子流程、修复副本与显式 Retry 不清零；额度耗尽保留结果并停止新工作，未知提交先对账，不认领成功。上限及推导见 Task §10.1；适配器记录可能命中既有缓存，不冒充实际 HTTP 数或账单。
- **实证与未验收：** 只读对应 OpenClaw SQLite 会话确认最终两次 assistant `stopReason=length`，最后文本约 2.87 万字符却未保存报告；本批先校验文件、有限局部修复、要求先实际写入后简短回复。Quality 每组只判断采样所覆盖表达，具体缺证补不同实际时点，保留有效观察/检查和中断 checkpoint；无新采样/容量不足/持续 unknown 保留缺口。真实报告稳定性、召回、语义误拒/误通过、完整动态表达、实际音画与导演语言仍未验证。
- **审查修正执行：R1/R2 软件完成，R3 本轮实测未通过，整体仍 PARTIAL。** 用户要求设定目标后执行，[Task §9](tasks/creation-latency-completed-2026-10-05.md#9-实施后审查任务清单2026-10-03) 保持唯一任务清单。`related-first-v4` 将同池名单拆为派发前冻结的轮次，每 Need / 计划及素材池最多提名 9 项；先接续未观察关联，再沿原有限补料处理缺口。保存提名数、未观察列表及覆盖/候选耗尽/预算耗尽原因。有效报告结果摘要及时持久保存，恢复不丢掉已覆盖 Need 的判断记录。正式准入、Rights、费用和未知执行对账保持原边界。
- **本次执行终点：软件及确定性验证后停止。** 没有重启服务、继续旧 Creation、调用真实模型或执行 Build/完整 E2E；运行中服务未加载本批修改。没有已知确定性回归阻塞，具备独立真实验收准备条件；实际启动须另行确认新委托、费用及执行范围并完成版本/环境预检，不自动转授旧 10 元授权，不代用户接受成片。旧 R3 保持失败及工程介入记录。
- **R3 已核实进展与 2B 修正：** 六视觉 Need 及已生成旁白完成正式覆盖（旁白预算预估上限 0.075600 元，非最终账单），经配乐定向补料及实际公开源页核实，19:09:44 前已 MATERIAL_READY 并自动进入编排，20:17:11 首个真实无 Provider 费用 Build 已提交并完成，45 秒 / 1080×1920 / 24fps MP4 技术 QC pass；实际首屏字幕对比和必要画面关系存在不足，20:47:49 首轮四组 Quality 已为 REPAIR_REQUIRED，关键画面/剪辑表达失败及四处声音遮盖告警；报告另有字幕底色/素材朝向误判。20:53:57 后续复查因报告未落盘而重试耗尽，Delivery failed，所有请求已终态，无第二 Attempt 或新购买；不能宣称可看首版或风格通过。实际补料查询被复杂声音偏好覆盖，当前首个分页查询不变；最小修正保留明确补料词首位、偏好次位，默认初次检索及正式合同不变。全量 627/5 跳过、compileall/115 项合同/diff check 通过。确认无未知运行后重载 Web，正常 BGM-only 恢复不重购旁白；新配乐已通过既有声音证据及真实公开源页权利复核，Production/export 仍必须落实 CC BY 署名，不能据候选返回或文件存在宣称成片通过。19:15:10–19:34:50 发生合盖休眠；恢复后原编排请求明确失败，下一隔离轮自动补齐后仍缺主 SVML，原三次有界编排耗尽后，最小修正补齐指令的样式依赖冲突及缺失文件失败分类，627/5 回归通过；无未知运行时重载 Web 并经原 Delivery 重试入口接续，另已完成仅补充取片失败定位/精确帧界的诊断修正，627/5 回归通过，已核对隔离接续合同及既有测试，平滑加载诊断增强并保留同一 run/stage，未重派或取消；已有真实 MP4，详细阶段与人工救场限制见具名 R3 验收。
- **R3 真实首个问题：** 17:59:14 正式确认后首次规划因文案字段混入非朗读说明，规划删去说明而被冻结一致性检查阻止；两次合同修正仍失败，尚无生成或 Build。18:14:21 经正常方案编辑整理，18:16:44 同内容同规格、10 元生成额度重新正式确认并接续。此人工恢复意味着初始无需救场自主性未通过；继续运行验证真实素材/制作，不倒算初始自主成功，详见 [本次验收](acceptance/creation-latency-r3-2026-10-03.md)。
- **本次验证：** 第 5 项合格及描述缺失的第 9 项合格可在无新增素材下从报告保存后中断沿正常 Delivery 恢复至 `MATERIAL_READY` / 下一步 Authoring；首批已齐不继续，全失败最多 9 项且第 10 项保留为未观察，重入不新增调用。共享组分发中断复用已保存结果，后续组跳过已覆盖 Need。附件不可见保留 uncertain，否定与逐帧字段矛盾有界修复，持续坏报告不无限调用，未知结果不当内容拒绝；上述软件动作不证明真实语义误判率改善。局部 **135 passed（9.82s）**；全量 **623 passed、5 skipped（37.88s）**，compileall、115 项 skill/publisher 合同及 diff check 通过，仅既有两项依赖提示。未改前端、重启服务、调用真实模型或执行真实 Build/E2E。真实速度、五项风格及无工程救场首版仍 **NOT_VERIFIED**；具体新委托草案与费用缺口见同一 Task，未创建或启动作品。
- **R3 已获真实启动授权：** 用户采用草案、素材/旁白生成总预算上限 10 元，仅生成真实缺口，并允许问题中说明的正常模型、服务加载与真实 Build/E2E，不发布。核对无其他自主委托与 Web 执行子进程后平滑重启 Web，未重启网关；临时防休眠。正常 `/api/chat` 已新建 Creation `cr_9d6b90b9df6249fea31eee265301efbd`，完成一轮完整提案及一轮修改，通过原 `confirm_production` 绑定 45 秒 / 9:16 / 旁白与音乐 / 简体中文、当前 Mode 与预算。提案自加手部精确动作已在确认前改为日常 B-roll + 工程文字承担核心关系，保留必要表达；未手写制作 Plan、Asset 或工程。阶段与成片结果见 [本次验收记录](acceptance/creation-latency-r3-2026-10-03.md)，本轮真实验收未通过，后续事项已收敛在原 Task 的 R3 终态节。上条“未重启/未真实调用”仅指软件验证阶段，不覆盖本次获授权的 R3。

- **此前软件增量（审查修正前）：** 正式 Web 入口已接共享视觉审核；此前每 Need 同类型候选仍最多九项。新提名 `related-first-v3` 每批最多四项相关 + 一项未知文字关联探索，全无文字关联则最多探索四项，但没有同池后续批次；本次 v4 已补齐接续。描述只决定提名，不证明适用。各共享子报告独立验证后及时登记，新组跳过正式覆盖，保存中断的组仍按原身份恢复。无变化重算保留原 SupplyRun/Bundle，必要匹配/Readiness 仍执行。保存当前 Need/字节绑定的 verdict/reason/可用性供有限补料调整策略；报告自身的逐帧证据与否定结论矛盾进入已有一次结构修复，unknown 不等于内容错配，技术故障仍走原执行对账。
- **规划与风格：** 对话/Planning/Authoring 明确区分要求来源、必要表达、Mode 稳定表达和软偏好，在获准能力内提出可制作镜头，并要求五项音画表达实际落实、沿已有 Quality 检查。新增现有 Delivery 内部 Preparation/Planning/结构修正/Truth/事实文稿修正计时。调用计时包含 checkpoint 读取与等待，不等于模型提交；内部时间属于大阶段，不能叠加算端到端。确认稿、有效 Truth、实际抽帧、费用与准入继续复用既有边界，不建设通用缓存/事实/观测层，不新增裁切消硬冲突准入。
- **此前软件证据与限制：** 全量 **618 passed、5 skipped（37.04s）**，局部 **130 passed（8.77s）**；compileall、115 项 skill/publisher 合同及 diff check 通过，仅既有两项依赖提示，本轮未改前端或重复前端构建。固定三场景/九素材的送审关联 **27 → 12**，两次共享调用达到 MATERIAL_READY，保留未知描述探索且不复审已覆盖场景；全失败首批 **9 → 4** 仍明确 NOT_READY，不能单凭此宣称交付改善。报告一致性检查只能发现自身矛盾，不能自动证明画面语义误判；没有新增补看能力。真实成片风格、自主交付、服务加载和整片提速仍 **NOT_VERIFIED**。本轮未重启服务、调用模型、运行真实 Build/E2E。

- 以下为 2026-10-02 首批独立证据，不能当作本轮真实链路验收。用户新增优先项为缩短创作时间；[历史 Task](tasks/creation-latency-completed-2026-10-05.md) 已记录方案确认、Preparation/Planning/Truth、素材/声音、编排、Build、审片全链瓶颈与后续顺序。真实整片时延仍未测量，不能将局部减少计算等同整体提速比例。
- 原 Delivery Owner 每三秒扫描一次，成功步骤也等待下轮。现在成功且操作/Attempt 已变化时立即接续，每轮最多 32 步；同操作仍等待轮询，失败/不确定执行返回原机制，未改变执行锁、费用批准、对账和停止条件。回放的同一 18 次操作由 18 次调度减少为 6 个连续批次；真实节省取决于原各步骤完成时与轮询时钟的关系，并非固定每步三秒。
- 同素材视觉预览在单次观察内按版本、字节、媒体类型与时长有限复用，最多缓存九项。每次仍校验实际文件 SHA/大小，并生成独立 Need 输入与判断；不持久化缓存，重启重建。真实短视频的四个 Need 回放从 20 次 ffmpeg 抽帧减少为 5 次，采样时间与帧摘要保持，字节改变拒绝复用。
- 原 delivery 增加 `operation_timings`，按 Attempt/操作保存次数、累计/最近执行秒数、首次/最近起止时间及最近结果。该执行时间包含单次调用的等待，不包含两次调用之间的远端运行、调度或人工等待；不可直接求和当作端到端时间。网关运行仍使用已有持久身份和时间记录。
- 确定性全量 **615 passed, 5 skipped（37.99s）**；Preparation/Material 局部 **127 passed**；compileall、115 项 skill/publisher 合同和 diff check 通过，仅既有两项依赖提示。复用原场景验证立即接续、同操作不忙轮询、失败与未知提交不重提、停止、计时累积、逐 Need 独立证据及实际抽帧复用。本批没有前端改动，未重复前端检查。
- 本批为 **SOFTWARE_ACCEPTED / REAL_WORLD_LATENCY_NOT_VERIFIED**。未调用付费 AI、真实 Build/E2E、推进已有作品或重载服务；运行中服务需加载新代码后生效。后续按唯一 v0.3 最小范围处理素材候选/重复工作并验证单主题链路；有限并发等延期，不减少必要审片。

## 作品画布状态误报修复（2026-10-02）

- 本机读取确认：当前作品 Creation/Attempt 接口正常，Delivery 正等待 Planning；尚无持久规划证据时，页面提前请求 script-truth 返回 400，被误报为“状态更新失败”。重连仅重读相同接口，无法消除该误报。
- 画布与旧路径轮询现在仅在 material_planning 为 PLANNING_READY 后读取事实审核数据；完成规划后的证据读取错误仍正常显示。重新连接会重新建立同源 Operator 会话并刷新状态，不重新提交制作。
- 扩展已有 workspace-browser Fixture 验证规划未完成零审核请求、已完成规划后读取失败及重连恢复、会话重新建立；页面场景全部通过，lint/build 与 diff check 通过，既有 Hook/打包体积提示保留。前端已重新构建并确认当前服务返回新版资源；未重启制作服务、修改既有作品或提交真实 Build。真实作品能否完成仍需后台执行结果。

## 本轮收尾与真人验收边界（2026-10-02）

- [唯一 Task](tasks/creator-autonomous-first-cut-2026-09-30.md) 的 A/C/B/D/E 最小范围已实现并完成确定性软件验证；不再保留并行实施队列。仍沿用 Creation/Preparation/Planning/Material/Hypit/Review/Selected Output，未新建 Director、Workflow 或 Production Domain。正式 Material V1.3 的 Truth、Rights、Match、Readiness、身份与费用约束保留。
- 已有 Delivery Owner、委托授权、Director/Mode、声音时序、原生编排、系统 Quality、有界恢复继续复用。新增镜头软偏好与替代决定、共享观察、例外组合接受、选择保持及画布状态收尾，原 Task 的两项目标未缩减为单纯串联阶段。
- 正常路径后台自主推进；组合接受是自动选材未满足期望时的可选取舍。一次查看所选画面/旁白/BGM，写一段整体判断，只补缺失条件。已有单项核对入口收拢到高级路径或缺少完整组合时的回退，不新增正常制作审批。
- 组合选择绑定方案、每个 Need 和素材字节；同一素材用于多个场景有独立证据。分组先完整预检，保存中断接续同一决定，已完成提交可幂等重放。共享/单项观察及机器审片原报告保留，人审取舍不伪装系统 PASS。
- 供应 READY 只表示存在合格候选，不能代表用户所选素材已准入。所选组合的 blocking_needs 在原接受记录中保存，页面单独展示其待办；未通过正式条件不进入编排。补齐使用权后本地重算并自动继续，不重新搜料或要求发送“继续”。候选排序不能挤掉已接受的合格素材。
- 普通 checkpoint 重试保留选择；明确视觉修改释放相关画面选择、保留声音。规划修正只为完整 Need 未变化的项重绑定，变化后不认领旧判断。提交结果不确定仍先对账，不以组合恢复覆盖已开始的执行。
- 早期无 Attempt 失败现在明确阶段/原因和阶段 Retry；修改方案按钮遵守已有准备/规划边界。内容与素材信息读取失败保留当前作品的最后可信证据，切换 Attempt 清除旧缓存；断连显示“上次状态”，不误报生产失败或丢弃脚本。
- 隔离页面检查采用临时 Fixture 服务（127.0.0.1:8641），全部 API 返回固定数据：耗尽时可选择并一次接受三项，换候选清空旧取舍、缺失标识证据阻止提交，提交后转入编排；制作中无组合确认；无 Attempt 失败可阶段 Retry；供应 READY/所选素材缺权利仍显示 1 项正式待办；断连保留证据。390px 窄屏无横向溢出。Fixture 音视频仅证明加载与交互，不代表真实听感或成片质量。

### 完成证据与范围核对

| 要求 | 当前代码与确定性证据 |
|---|---|
| 委托后唯一后台交付、预算与未知提交 | creation_delivery / material_generation；Creation Preparation 中 delivery replay、commission bound、gateway timeout 与 build/quality recovery 场景；旧 Creation 不自动认领授权 |
| Director 判断贯穿实际执行 | Planning/Compiler → material_recovery 决定 → material-selection → 原生 Voice/Production → Quality；三内容回放增加软偏好与真实补料报告决定，断点恢复后核对编排及 Quality 输入仍消费同一决定 |
| Material/Voice 可用且少打扰 | scoped visual/music/voice evidence、shared observation、实际语音时序；Material Integration 保护独立 Need、未知 Rights、不重复供应/生成和坏报告有界修复 |
| Hypit 原生 Production 与可看性 | 本机 Hypit 0.2.7 静态 check 的三内容回放；原生字幕/ducking/取片合同；Hypit Integration 检出近黑、旁白截断、BGM 遮盖/缺失，未看/陈旧帧不能 PASS；修改只触及允许层 |
| 组合接受与恢复 | 原 combination review 场景覆盖单 Need/同素材双 Need、陈旧/缺失/重复选择零写入、API 认证、日志落盘到标记之间中断、幂等、未知提交优先对账、前三项之外选材保持、供应 READY 但所选 Rights 仍阻断以及补权利自动继续、所选字节变化仍阻断；原失败 Build checkpoint 场景保护继承/视觉修改释放/规划重绑定 |
| 人审成片与入库边界 | Hypit lifecycle/selection/hash tests：最终接受绑定当前输出与 SHA，输出 A 的审阅不能选 B，仅内部用途仍单独保留限制；不自动发布 |

- 本轮最终全量：**614 passed, 5 skipped**；收尾边界相关四组 **167 passed**；末次加强所选素材字节核验后组合/重试相关 **3 passed**；本机 Hypit 静态契约三内容回放 **1 passed**。Frontend lint/build、compileall、115 项 skill/publisher 合同与 diff check 通过。保留两项 Python 依赖提示、一项原 Hook 提示及原打包体积提示，不扩展本轮重构。
- **READY_FOR_HUMAN_E2E = YES（软件及离线预检范围）**。真正的素材命中率、Creative Mode 取舍质量、旁白/BGM 听感、实际首版可看性、跨内容风格一致性和时延仍需 Creator 验收；局部渲染边界使用替代输出，不能证明真实 Hypit 成片感知效果。
- 本轮未修改、继续或重建现有 Creation，未调用付费 AI、提交真实 Build、运行完整 E2E或重载产品服务。真人验收前需加载本轮新代码并新建作品；服务重载及真实制作由用户后续启动。本轮不宣称整体 V1 已通过真实产品验收。

## 提案可执行性与确认入口修复（2026-10-02）

- 用户本次 E2E 的最新草案已保存完整文案/分镜，但总时长、画幅、音轨均为待确认，仍被标记 READY_FOR_CONFIRMATION，制作按钮无可操作补齐路径。根因为提案提示禁止导演推荐制作规格，状态保存只检查内容章节，前端又使用本地聊天 phase 限制确认。
- 修复在原提案主链内：尊重明确要求，由 Director 对缺少的普通制作设置提出一个明确推荐及依据；推荐不是用户已确认，点击制作才冻结。保存推荐说明并纳入方案摘要，只从制作规格章节提取设置，不从分镜或格式示例猜值。只有完整方案及全部必需规格可确认，旧 READY/缺规格记录也不能直接绕过服务端确认。
- 画布显示制作设置与推荐说明；旧草案可请 Easel 补齐推荐，或一次选择缺项并通过原聊天更新整份方案。读取失败可重试，完整方案依服务端可确认状态启用入口；后端版本更新自动刷新预览，不再依赖本地 phase 的重复门禁。预算/输入使用范围/权利及最终确认保持。
- 验证：确定性全量 **614 passed, 5 skipped**；提案/聊天合同 **77 passed**；隔离页面核对完整推荐方案、缺规格一键补齐/选项、旧本地 phase、读取失败重试及原桌面/窄屏制作状态通过。Frontend lint/build、compileall、diff check 通过，仅保留既有 Hook/打包体积及 Python 依赖提示。未修改或推进当前 Creation，未调用付费 AI、Build/E2E或重载产品服务；现有草案须由 Creator 使用补齐入口更新，不能据局部测试宣称真实方案效果已验收。

## 成片入库后的素材清理（2026-10-02）

- 用户追加要求已实现：Creator 最终确认且成片成功入库后，删除该 Creation 各 Attempt 的素材媒体副本，包括成功、失败和未选用候选，以及素材/参考目录内音画预览；JSON 证据、方案、工程、已导出与入库成片保留。共享素材库和用户原始文件不删除。
- 入库与选择先持久保存，清理与制作共用执行锁；链接路径拒绝清理。失败保存 PENDING，重复最终确认幂等接续，成功为 COMPLETE。未确认或入库失败不清理，旧作品不自动扫描删除。清理后旧片修改不能直接复用被删除素材，须重新获取并遵守费用边界。
- 确定性全量回归 **614 passed, 5 skipped**；扩展既有生命周期场景核对多 Attempt、入库失败零删除、外部链接保护、清理接续与成片/证据保留。无真实制作或删除既有作品，服务尚未重载。

## D：例外组合接受增量记录（已由上方收尾核对，2026-10-02）

- 后端新增一次组合接受入口，先核对当前方案/素材版本、完整必需 Need 集合与逐素材字节，再保存逐 Need 的人工观察证据；不覆盖系统原观察或正式 Rights。保存中断由既有 Delivery Owner 接续同一份记录，完整提交可幂等重放；相关人工素材写入共用 Creation 执行锁。
- 根因修复：原单项复核只使素材可能合格，没有约束 Production 实际使用。现将保存的组合决定提供给编排，并在正式选材校验中要求包含所接受素材；每项仍重新验证正式匹配与权利准入。同时修复导演取舍输入被旧选材字段校验拒绝的问题，服务端决定不得由 Authoring 改写。
- 本批局部验证：Material integration、Hypit integration、三内容 Replay **107 passed**；新增一个组合事务场景覆盖过期字节零写入、写入后中断恢复、完整提交幂等、UNKNOWN Rights 拒绝。compileall/diff check 通过；两项既有依赖提示保留。
- 页面已接入可选组合入口：逐场景选择与实际画面/音频预览，一段整体取舍说明，一次明确接受；仅缺失的无标识/无文字证据要求补充，已有证据预填。旁白候选必须绑定当前脚本生成，输入身份变化重置表单。正常自动制作不展示新增必经确认。
- 接续修复：组合接受后不因原观察版本变化重跑视觉判断或自动换料；旁白时序仍先核验，当前实际 Rights/Match 仍检查。合格的所选候选不会因三项 shortlist 排序被丢弃。普通制作 checkpoint 重试继承原选择；明确视觉修改可释放视觉选择，保留声音选择。后者已进入代码，仍需带组合记录的专项回放证明。
- 新一批 Material/Hypit/三内容回放 **107 passed**；组合场景增加实际 next_operation 断言：直接 author，Rights 变为 UNKNOWN 后 needs_evidence。前端 lint/build、compileall、diff check 通过；保留既有 Hook 和打包体积提示。
- 上述当时待收尾项已完成，当前证据和真人边界以上方完成核对为准；不将此增量记录作为剩余任务。

## B：共享视觉观察（2026-10-02）

- 根因：每个 Need 单独发出同一素材的预览，四个场景共享候选时重复传图与模型等待。后台现在对同一素材一次输入最多四个 Need，逐 Need 返回独立报告；不复制适用结论，不改 Rights 或正式观察证据格式。已有有效单场景报告继续复用，独立 executor 仍用于已有局部调用。
- 派发前固定分组与完整输入；组身份绑定观察版本、实际素材/帧摘要与每项 Need。共同报告整体校验并持久保存，再分发原单场景报告；分发中断后读取同一组，不重新调用模型。逐 Need 对当前素材重新应用报告，正式 Matcher/Readiness 仍独立核验。需求/预览变化不能认领原分组；未知或不适配不能因其他场景合格而准入。
- 共享观察沿用原持久网关、报告修复上限和素材观察操作，不新建 Workflow；同时保留有效旧报告，不因升级重跑已完成观察。每组仍通过实际解码预览判断，未改成只看标题或复制基础描述。
- 验证：Material integration、Preparation、三内容 Replay **119 passed**；加强组身份与恢复输入核对后相关 **6 passed**。扩展原逐 Need 观察场景，两个不同场景一次模型调用，分别 suitable/unsuitable；拒绝缺场景及错用另一场景身份；模拟组报告落盘后分发中断，恢复仍只有一次模型调用。跨内容回放改为替换共享模型边界，正式 Owner 走新入口。compileall / diff check 通过；未操作现有作品、调用付费模型、重启服务或启动 Build/E2E。真实提速比例与语义准确性尚未验证。

## 制作效率与低打扰优化：第一批（2026-10-02）

- A 第一批完成记录；后续状态以本页顶部当前任务清单为准。
- 根因：视觉观察 Prompt 同时要求“审美偏好不否决”和“部分符合的细节整体 partial”，导致可替代细节容易被当作硬门槛。现去除冲突，Planning 将核心表达/明确硬要求留在 intent.description，可替代细节放入现有 constraints 的可选文字键 preferred_visual_details。Compiler 不将其传为供应硬过滤；实际图片/视频生成请求作为可取舍偏好传递，观察按同一 Need 判断并记录偏差。旧 Need 不自动降级要求，无该字段的旧生成请求文字与身份不变。尚不能仅凭这些合同断言真实模型一定正确取舍。
- 新提名视觉批次保留原 Rights 优先级，在此基础上先按内容相关性、再综合风格/质量排序；排除已知 RESTRICTED 及技术未通过的候选。UNKNOWN Rights 保留观察机会但不自动准入。已保存批次和有效报告继续复用，不因升级重排或重复请求。
- 验证：Material integration、Preparation、跨 Content Replay、Matching、MiniMax image/speech 共 **151 passed**；强化候选排序回放并保留 Rights 优先级后相关 **8 passed**。场景覆盖同素材逐 Need 独立结论、未知 Rights 不放行、报告修复上限、实际生成请求和身份、旧加权排序优先风格候选而新排序先检查内容候选、报告落盘后中断不重调。compileall / diff check 通过。只增加一个有独立排序风险的参数场景，未调用付费 AI、重建作品、重启服务或启动完整 E2E；未修改前端，本批不重复前端构建。

## 历史增量与具名证据

以下按当时记录保留；“当前”“仍待”“Goal active/暂停”等均是记录时状态。已被后续记录取代的内容不作为当前缺口清单；现行范围只取本页顶部与当前剩余事项及顺序；旧 Task 章节及历史任务状态通过 Git 追溯。

### 当前作品已按用户要求清理（2026-10-02）

- 用户在第二轮选材仍未满足后明确要求删除本次未完成制作。已停止该作品交付，删除 `cr_b31cd80a62cc4da7927006c0692a9446` 的 Creation 目录（含方案/准备快照/阶段记录）、对应 Hypit 制作工作区（含素材、旁白、观察报告及临时误写的同作品子目录）、聊天到该作品的绑定以及本次本地 ASR 调试临时文件。其余 8 个 Creation 保留；此作品未提交 Build、未产生 Selected Output，Material Library 中没有其推广资产或使用记录。共享服务、其他作品、模型和项目代码保留。
- 下方具名运行记录均为清理前历史证据，不再表示这个作品仍在运行，也不再将已删除媒体视为后续 Replay 可用数据。当前不继续或重建该 Creation；本条不把真实自主交付记为完成。
- 用户新增的“一次接受当前所选画面/BGM/旁白并继续”及“核心表达/硬要求与可替代镜头表达分开，由 Director 先作替代取舍”的要求，已加入[唯一实施 Task](tasks/creator-autonomous-first-cut-2026-09-30.md)末尾优化记录。仅记录，未实施统一通过功能或修改素材核对标准；事实与权利要求保留。

### 视觉补料耗尽误报人工事项（2026-10-02）

- 本次作品旁白恢复后，仅 `need-img-charging-scene` 未满足。生成图片的已绑定观察结论为 partial：画面过暗，墙边设备/地面线缆无法明确判断。该图片仍为 UNKNOWN Rights，不能凭生成成功或 Creator 点击确认就认领合格。此时没有需要 Creator 提供的事实或新费用决定；根因是 Owner 在一次补充检索、一次委托生成之后，将所有剩余缺口落为 `needs_evidence`，前端又把缺口直接计为人工待办。
- 最小改动：复用现有补料操作，为此类纯视觉缺口增加一轮有界检索（总计至多两轮补充检索）；优先完成原来的生成对账、预算和观察，再判断是否还可补料。已适配场景但缺少 Rights 的候选仍走原权利事项，不混为选材失败。只改检索词，保留脚本、Need、素材、授权、原生成结果及每轮请求；不得重开不确定的 Provider 请求或重复购买。
- 补料规划此前将素材数组前九项作为证据，可能漏掉排在后面的最新生成失败图；现优先取当前 Need 的最新已绑定观察，并传入历史检索词，重复短语拒绝。新轮次有独立固定请求身份与缓存，中断恢复复用原检索建议和补料结果。原费用、Rights、Match、Readiness 与首版审阅门禁保持。
- 上限用尽仍缺纯视觉素材时使用 `material_supply_exhausted`，作品区展示“自动选材暂未完成”、具体缺口和已保留结果，停止状态不伪装运行，不计入 Creator 审核待办，不展开放行不合格素材的表单。提供已有的“讨论这个场景”入口，真正的事实/权利/费用任务仍保留正式操作。该有限补救不保证任何严苛场景一定可找到素材，也不替代暂缓的整体选材效率优化。
- 验证：Material integration、Preparation、跨 Content Replay **116 passed**，新增一个跨模块恢复场景保护第二轮的固定身份、重复查询拒绝、补料落盘后中断不重复供应、原方案不变，以及用尽后的正确责任状态。三种确定性作品投影（自动补料、系统选材耗尽、真实待处理）检查通过；frontend lint/build、compileall、diff check 通过，保留既有依赖/Hook/chunk 提示。
- 真实恢复：服务重载后当前作品从 `needs_evidence` 自动进入第二轮补料，只处理充电场景；已保存四条不同的新检索词，第二轮补料完成，Owner 随后继续观察候选。未重新生成旁白、未请求新的付费素材生成；视觉缺口尚待观察结果，不把搜索完成视为素材 READY 或成片完成。

### 旁白识别低置信恢复（2026-10-02）

- 当前作品 `cr_b31cd80a62cc4da7927006c0692a9446` 已完成一条 39.312 秒旁白；失败发生于独立本地识别/时序恢复，不是 TTS 生成失败。原音频 SHA 为 `ea6ea62cbc9d6cf1f8e8925e56bf1bcb225f0fd8782c57947826896a3d32425c`。离线重放现有 small 模型复现：首词“最近”置信度约 0.313，并出现“比→筆”“劲头→鏡頭”等实际识别差异。同输入、同模型的重复 Retry 不会修复模型能力问题，不能据此断言原音频多读或重新购买。
- 原错误合并低置信、非法置信度和多余内容，且被拒绝的识别报告未落盘；现分开提示，文字不符时指出实际字符位置及识别/脚本差异，拒绝报告按摘要保存为诊断证据，不能作为成功检查点复用。完整脚本、标准简繁等价、最低置信度 0.5、实际时序及音频/脚本/Need 身份检查均保持。原成功检查点仍复用，换模型后失败报告不阻止重新识别。
- 局部验证：Material integration、MiniMax image/speech、Preparation **130 passed**；扩展既有恢复场景，验证错误类别、被拒报告保存、不能认领为成功检查点，以及恢复不重购/不改原音频。compileall、diff check 通过；保留两项既有依赖提示。本次不新增测试用例，仅扩展既有风险场景。
- **真实局部重放：** 本机配置切换至 `mobiuslabsgmbh/faster-whisper-large-v3-turbo`，模型文件 1,617,884,929 字节，SHA-256 `e76620f83d5f5b69efd3d87e3dc180c1bd21df9fbebacfd4335e5e1efcc018da`。启用 VAD 时“声”置信度约 0.259；关闭 VAD 后同音频所有词均达到既有 0.5 门槛。生成旁白核对现使用完整音频，不先拼接静音裁切后的语音片段，保持无目标脚本提示及实际时间。增大 beam 至 10/20 未修复文字差异；启用前文条件反而幻觉出“对”，不采用这些参数。
- **试听证据与根因闭环：** 较强模型仍将“劲”识别为“镜”（第 87 个有效字符、原文索引 108）。Creator 明确试听确认“读的是劲头，旁白正确”。现有恢复此前只能消费 ASR 全字匹配，无法消费这项正式人工证据。最小补修复用现有素材匹配复核接口：确认只绑定当前音频、冻结脚本、Need 和原识别报告摘要的指定字符；其他文字、置信度、完整覆盖和实际时序仍严格校验，不进行通用同音替换。原识别报告不改写，成功恢复引用同一原报告与独立复核证据，不重跑识别或 TTS。普通试听摘要、缺失/错配报告身份、不完整字符确认、低置信、漏字、多余内容、错配 Need 和 Unknown Rights 均不能绕过对应检查。
- **真实恢复结果（2026-10-02 11:28 北京时间）：** 经正式素材复核保存索引 108 的“劲”字结论，并调用原阶段 Retry；旁白时序已为 `READY/local_asr`，14 句实际边界，原识别“镜”字仍保留。原音频字节 SHA 核对不变，只有一条指定字符复核证据。Owner 清除失败并进入 `observing_material`，未重购旁白；后续素材/制作与最终成片仍未完成。本次修复不是所有中文 ASR 错误已经消除的证明，也没有新增 Director、Workflow、Production Domain 或改变 Material Layer 冻结模型。
- 补修仍为 **130 passed**，复用既有恢复场景覆盖真实 HTTP 合同、确认后检查点复用、不改原报告、其他未确认字符继续阻断、旧音频/脚本/Need/报告身份失效、低置信继续拒绝和 Rights 不被批准。compileall、diff check 通过；未新增测试数量或运行完整 E2E。


### 素材观察报告恢复校验（2026-10-02）

- **逐帧类型错误补修：** 后续报告完整包含 frame 0，但将 `frames[0].related` 写为字符串 `partial`；原校验把帧数、编号、类型和说明错误统称为“必须逐张记录”，修复提示只有示例、没有明确区分顶层 verdict 枚举与逐帧布尔/未知值。现分别报告具体字段错误，补齐 prompt 的明确类型合同，保留 partial/uncertain 的真实含义，不通过强制布尔转换批准素材。已有报告先校验，坏稿直接进入一次固定身份修复，不因 prompt 更新重跑初次观察。对应局部场景复现本次错误，验证修正后仍为 partial、逐帧不确定保留 null、Material 仍不放行；原语法、旧身份、Rights 和修复次数边界继续验证。
- 本次补修的四组局部回归 **133 passed**，compileall/diff check 通过。经用户授权重载服务并正式 Retry，09:13 发起同一报告的修复，模型将逐帧 related 修正为布尔值 true、顶层 verdict 保留 partial；原报告已通过读取校验，09:13:47 Owner 派发下一候选观察。没有手动修改报告或将 partial 素材强制准入；恢复已取得真实进展，首版尚未完成。

- 本次真实作品第四份图片观察报告包含未转义双引号，导致 JSON 解析失败。恢复入口此前按“文件存在”直接解析并复用，绕过 Web 执行器已有的有界报告修复；Owner 连续读取同一坏文件三次后停止。前三份有效观察报告、规划和已供应素材均保留。
- 新报告与恢复读取共用同一报告读取/身份/内容校验。恢复发现语法或合同无效时进入原执行器；已完成初次调用沿用网关记录，再发起一次固定身份的报告修复。解析错误变化不会产生新的修复请求，重复阶段恢复不能无限追加同输入的格式修复。坏报告按字节摘要保留诊断副本；未知、错配、Rights 缺失仍不能作为合格素材通过。
- 局部验证：Material integration、Preparation、跨 Content Replay、隔离 Authoring **132 passed**；扩展既有场景覆盖模型写坏 JSON 后中断、旧输入身份、有效报告复用、修复仍坏时反复恢复不新增调用，以及独立 Need/Rights 证据继续成立。compileall/diff check 通过，保留两项既有依赖提示。未扩展暂缓的选材优化。
- 经用户授权重载服务，并通过正式阶段 Retry 恢复同一 Creation/Attempt。10 月 2 日 08:59:33 发起当前坏报告的修复，09:00 已写出可解析且绑定原输入身份的报告，保留原 unsuitable 结论；坏字节诊断副本已保存。已有三份报告及供应素材继续复用，未手改报告、未重新供应素材。此时网关尚待返回终态，不把文件写出等同整个阶段或成片完成。

### 素材观察模型能力与提交拒绝恢复（2026-10-01）

- **后续优化暂缓：** 用户要求当前优先跑通制作；视觉候选初筛、重复观察与整片选材协调问题已记入唯一实施 Task 的当时后续评估（旧章节通过 Git 历史追溯）。本次仅记录，不启动优化，不改变当前制作链路。
- 10 月 2 日补充本次 09:44 耗时与命中率快照，记录“场景初筛 → 观察复用 → 自适应候选 → 受控并发 → 简短结构化输出”的建议顺序；最小实施范围先为初筛和复用，以隔离回放比较效率及误配，再评估并发。这是当时待评估的建议，旧 Task 第 10 节通过 Git 历史追溯；后续已完成初筛与观察复用，当前范围见本页顶部，不将受控并发等建议自动列为新任务。

- 当前真实作品在 21:34 完成 Planning 和素材搜索；首项图片观察于 21:34:49 被网关以 `INVALID_REQUEST / active model does not accept image inputs` 拒绝。旧适配器把明确拒绝归为提交不确定，再把查询 timeout 持续记为 pending，形成没有实际观察进展的长期等待。
- 已核对 [MiniMax 官方 OpenAI 兼容合同](https://platform.minimaxi.com/docs/api-reference/text-openai-api.md)：MiniMax-M3 支持图片输入。本机模型条目误配为仅 text，已通过配置命令修正为 text/image，网关模型目录确认生效；保留原模型与账号。该本机配置不纳入 Git。
- 新视觉提交先通过网关 `models.list(includeDetails=true)` 核对当前 Agent 默认模型的图片能力与可用性，并记录模型身份；沿用原会话路由，由网关继续校验实际有效模型，不使用当前 CLI 调用者无权使用的 provider/model override。已登记/已完成调用先复用原身份，不因能力查询重新提交。明确的结构化请求拒绝记 error/rejected_before_start；真实传输中断仍保持同一 run 对账，不能仅凭 timeout 认定失败并重提。
- 局部验证：Preparation、Material integration、跨内容 Replay、隔离 Authoring **131 passed**；覆盖纯文本配置提交前阻止、明确拒绝可恢复、传输中断仍等待原 run，以及图片附件与完成结果复用。后续取消单次模型 override 后，相关 4 项再次通过。compileall/diff check 通过；无新完整 E2E。
- 用户明确要求恢复本次制作：依据原拒绝日志核对原 run 的提交时间，持有原 Delivery 锁修正等待记录，保存日志条目摘要与恢复历史；没有把报告伪造为通过。重载服务后使用正式 Retry，22:26:45 已真实发出图片观察模型请求，22:26:48 收到 HTTP 200；仍为原 Creation/Attempt，复用现有素材。22:27 已生成首份真实图片观察报告，识别夜间停车场与通勤场景不符并记 unsuitable，后续继续核对候选；证明图片输入和观察文件写入已恢复，尚不证明首版交付完成。

### 创作规划失败恢复（2026-10-01）

- 真实失败根因：脚本共 14 项，其中 1 项已确定性标记为假设表达，模型额外审阅该项使原先“恰好等于待审集合”的校验拒绝整份报告。现允许当前脚本内、与已有判断一致的额外审阅，不覆盖既有证据；真正遗漏、重复、未知编号、过期身份、来源错误及相互冲突仍拒绝，错误明确指出差异。
- 对只确认方向的旧委托，格式合格但含 unresolved 的报告增加一次有界责任复核：区分委托必须补充的信息与系统自行引入、可在原方向内删除/改写的无依据表达。后者沿用原脚本修正与重新审阅链路；不自动把事实判 PASS，不改写新委托已确认的逐字文案。
- 新增同一作品“修改方案后继续”接口与页面入口，受原 delivery 执行锁保护。最小范围为内容准备/创作规划失败且未完成素材规划、未开始供应/生产、无未核实网关执行。保存原委托/方案/准备历史，暂停自动推进，沿用原对话修改完整方案；重新确认同规格版本后保留原 Preparation/Attempt 与已完成网关记录，原未提交规划文件归档后使用新确认稿。已冻结规格变化、Material/Production 已开始及执行不确定时明确拒绝覆盖；不是全阶段通用重编入口。
- 验证：Script Truth、Preparation、跨 Content Replay、Hypit、隔离 Authoring **139 passed**；额外审阅保留原证据，遗漏/重复/未知/冲突拒绝，修改中的 Owner 停止、历史保存、同规格重新确认/检查点复用及生产阶段拒绝覆盖均有局部证据。前端状态场景、lint/build、compileall 与 diff check 通过，保留既有依赖/Hook/包体积提示。未跑浏览器 fixture 或新作品完整 E2E。
- 对本次真实 `cr_b31cd80a62cc4da7927006c0692a9446` 原报告只读回放，结构校验已通过，仍保留“电车和油车又吵成一团”的内容依据问题。经用户授权，21:27 左右重启服务并调用正式阶段 Retry；原 Attempt 数量仍为 1，Owner 为 observing_execution，正在执行责任复核。未手改当前脚本、伪造审阅或创建新作品；此次记录只证明恢复已启动，不证明首版交付成功。

### 对话内视频方案（2026-10-01）

- 用户确认前在聊天中讨论完整创作表达、逐字文案、分镜节奏、声音设计与规格；提案阶段注入真实 Director 表达文件，替换仅给方向和规格的提示。完整回复由服务端解析并保存到 Creation 的 `chat_workflow.video_plan`，同一方案修改递增版本；画布不再使用最后一条助手回复充当方案。
- 新讨论轮次使旧方案暂不可确认；迟到回复不能覆盖当前轮次。画布展示持久方案，预览规格与确认共用该版本，确认请求绑定方案摘要；确认后的 `delivery.video_plan` 与 Handoff 保留该方案。已有已确认作品不迁移、不重新入队。
- Planning 原样供应确认的 SCRIPT/SCENES/TREATMENT（含声音设计），只细化 MaterialPlan；合同检查拒绝静默重写。需要改变已确认文案的事实/质量问题保留结果并报告，不能以自动改写绕过用户确认；本轮没有新增确认后在线修改作品的生产入口。
- 局部验证：Preparation、跨 Content Replay、隔离 Authoring、Hypit **120 passed**；覆盖方向不足、版本修改/持久恢复、过期确认、迟到回复、确认冻结、下游复用与重写拒绝。前端状态场景、lint/build、compileall、115 项技能合同及 diff check 通过，保留既有依赖/Hook/包体积提示。页面 fixture 增补具体文案/分镜与确认摘要断言；本轮未运行浏览器 fixture 或真实模型/E2E。
- 部署边界：未重启当前服务，未修改或推进正在制作的 Creation；后端新行为需下次服务重启后生效。

### Creator 作品工作区（2026-09-30 软件验收）

- Conversation 与 Work Canvas 分栏；窄屏“对话 / 作品”切换、待处理数量、稳定输入框和独立滚动面。作品从 Proposal 出现；作品状态从现有 Creation / Attempt 恢复，不依赖聊天中另发“继续”。七阶段进度由统一只读投影提供，默认收进“查看制作进度”。
- Proposal 卡与显式确认共用服务端字面规格解析；时长、明确画幅比例、音轨和语言缺失时留空。示例、问题、上限和歧义不补猜；未知规格要求通过对话补足。确认后保存同一组规格与原有对话哈希，Preparation 冻结前校验相同值，规格漂移阻断。旧 Creation 的已冻结输入未被迁移或修改。
- 无 Attempt 的准备失败直接显示失败原因、已保留结果和阶段 Retry。后续状态优先于旧 Preparation 失败；各类读取分别保留连接错误，失去连接显示最后可信状态。状态读取不会重新派发 Planning / Authoring / Provider。
- 事实、按场景的素材 Match、素材 Rights 与当前费用各有任务卡，继续使用原有正式门禁。观察按 Need 与 Asset SHA 隔离，切换后清空；已有来源、许可与证据预填。Match / Rights 使 Gate READY 后直接进入正式 Authoring API，不生成额外“继续”聊天回合。
- 成片播放器、当前技术检查、一次人工审片与 Selected Output / 内容库链保留。一般反馈和时间点反馈绑定当前输出与 SHA，时间点不得越过实际时长；不自动发布。
- 最小可执行修改为**构图与转场**：复用已验证的 Planning / Truth / Material checkpoint，以输出身份、反馈和 fingerprint 建立幂等新 Attempt，重新 Authoring、Plan / Pricing / 费用批准与最终审片。不重新供应素材，不复制旧费用批准，不自动提交 Build。脚本、规格、声音、字幕和素材替换明确提示需重新确认方案，不提供伪执行按钮。
- 高级信息默认折叠；移除聊天输入框中的重复制作确认及高级区重复审片播放器/批准入口。
- 验证：后端定向覆盖 110 项（109 passed / 1 deselected 的组合运行，显式确认 API 单独通过；后续 11 项关联回归通过），前端状态投影场景、隔离 Chromium 桌面/390px 窄屏场景通过。页面检查覆盖 Proposal、无 Attempt 失败、编排失败、素材任务、费用、可播放的确定性测试视频、输出绑定的时间点反馈及修改派发、运行状态与断连；全部接口拦截，未调用真实 Provider / Authoring / Build。lint/build、compileall、skill 合同与 diff check 通过。保留 AccountsPage 既有 Hook 警告及构建体积提示。
- **验证边界：** 未修改或继续当前 Creation，未执行付费 AI、真实 Build 或完整 E2E。真实 Creator 审片、修改结果与外部制作验收由 Creator 随后操作；软件测试不代表真实视频效果已验证。

### Creator E2E 前修复（上一轮修复基线）

本轮只修改代码、任务书、UI 和确定性验证；未继续当前 Creation，也未启动新的完整 E2E。当前人工 Creation 仍由 Creator 后续操作，Build 尚未提交。

- Material Match 对视觉 Need 要求当前素材的实际画面观察或按 Need 与 SHA 绑定的 Creator 核对。技术、Rights、语义与 hard constraint 每项都要成立；Readiness 重新核验 Match，不能把没有证据的重复素材当作覆盖。未核验素材保持 NOT_READY。
- 已完成 Material Gate 的 Preparation 恢复直接复用当前 checkpoint；生成素材 Rights 核对与视觉匹配核对只在本地重算，不再次进入 Provider Supply。
- Hypit 0.2.7 Task Book、Prompt 和 Retry 已按本机 Surface 收敛；Easel Run JSON 身份校验通过后才生成 native Run。隔离 Authoring 产物提升前执行本机 `hypit check`，失败产物不覆盖可信文件。静态图片与音轨各有一份本机 0.2.7 最小工程通过 `hypit check`；这不证明当前 Creation 的 Authoring 已完成。
- 已确认视频时长上限短于全部可用旁白时在 Authoring 前阻断；Authoring 产物在当前选定 Voice 与固定 Timeline 时长不符时阻断。图片 Item 的 Extent 按实际检查宽高核对，Canvas 仅表示画布。
- Creator 页面展示七阶段 Timeline、失败阶段与原因。Authoring/Plan 的 Retry 保留已完成的 Planning/Material checkpoint；已确认失败且可从 Hypit 核实的 Build 可新建同 Creation 的恢复 Attempt，重新绑定已验证的 Planning、Material、Script Truth 和 Authoring，新的 Plan/Pricing/费用批准仍是必要步骤。提交不确定时继续先对账，不允许重发 Build。技术 QC 继续自动校验文件、SHA、音视频流与完整解码；事实/风格 PASS 必须有当前成片的人审依据。
- Preparation 格式示例已移除 2.5 秒占位 beat；Agent 交付前可执行与冻结相同的只读四文件合同校验，重试携带原始脱敏诊断，聊天显示实际失败原因。当前 Creation 草稿未被修改或重试。
- 提案阶段继续使用现有新版 Proposal，已去除冲突的制作通用提醒；当前阶段不会自动填造 Creator 身份、规格或内部流程说明。
- **待真实验证：** Build 失败后的 checkpoint 恢复只有确定性软件回归，尚无真实失败 Build 试验；安全 AI 视觉预审没有已配置的分析器，异常视觉匹配目前由 Creator 按 Need 核对。上述能力不能以自动 PASS 或再次 Provider 请求代替。

### 本次 Creator 真实 E2E（2026-09-30，PARTIAL）

用户已明确启动一次普通 UI E2E，范围见 [具名验收记录](acceptance/creator-workspace-e2e-2026-09-30.md)。同一 Creation 完成 Proposal/冻结内容/规划/逐 Need 素材核对，Gate READY 后自动进入 Authoring。过程中暴露并修复了 Planning schema/检索合同、无 Profile 图库隔离、轮询重置确认、阶段误标、制作聊天泄漏和隔离 Authoring 契约缺漏。正式安装版 vocabulary 已接入隔离助手的只读合同输入，从同一失败阶段恢复后完成一个零第三方计费 Build、自动技术检查、一般时间点反馈、最终确认及内容库入库。成片为 12 秒、1080×1920、彻底静音；刷新/返回与选中输出 SHA 绑定验证通过。FUNCTIONAL/CORRECT/RECOVERABLE/CONTENT_LIBRARY=PASS，CREATOR_E2E=PARTIAL、CREATOR_VISIBLE/AUTONOMOUS=FAIL：本次曾泄漏内部制作回复，并依赖产品代码修复及服务重启，不能将修复后的结果当作完全自主验收。未手改真实产物/数据库/状态，未绕过审核或费用门禁。

### 本次 Creator 自主性与音画质量 E2E（2026-09-30，已入库；自主性 FAIL）

用户另行授权一个 36 秒、5 场景、真实旁白与 BGM 的 Creation，详见 [具名验收记录](acceptance/creator-audio-quality-e2e-2026-09-30.md)。一次 TTS 保留（31.932 秒），Creator 已确认旁白与 At Rest 配乐听感；实际 TTS 账单未核实。Material READY 后首次本地 Build 导出 36 秒、1080×1920、有音轨成片，技术 QC pass，CC BY credit 到达导出记录；第四场景开头近黑，未批准入库。局部修订先遇模型网关 502/400，再因错误帧率的截取越界使 Build 确定失败。安全诊断、合同索引、声音/字幕不变校验、基于准入原片/Normalize Clock 的截取范围检查已接入；失败 Build 恢复保留内容/素材，不合格编排停在 AUTHORING_REPAIR_REQUIRED，全检查通过才 READY，费用与审片仍重过。原生 Run 的隔离校验副本同时复制绑定身份记录，错配/缺失仍拒绝。83 项定向回归、lint/build/compileall/diff check 通过；实际普通恢复在提交前拦住越界，正常修复后完成 Build `bld_20260930T103231067Z_BF556E2071`。同一 Creation 三个阶段/修订 Attempt；最终修订版 36 秒、1080×1920、有音轨，SHA `2beb5b487123ee5fe2541190eaf3d995b91f6b212ad3731981485f066feb862f`。Creator 完整审阅后明确“成片可用，确认并保存内容库”，普通确认已绑定当前输出与 SHA；内容库文件字节核对一致，CC BY credit 保留，未发布。FUNCTIONAL/CORRECT/RECOVERABLE/CONTENT_LIBRARY 及基本内容/音画/节奏质量 PASS；风格一致性 PARTIAL（偏暗、字幕对比不足、未呈现前景虚化）。AUTONOMOUS/CREATOR_VISIBLE=FAIL，按本轮无工程救场标准 CREATOR_E2E=FAIL。用户已要求暂停；只补齐收尾记录，不启动另一轮 E2E。

当前旁白具有受保护的试听入口。Creator 已确认五句完整清晰、语速合适，并明确允许本次直接使用；通过普通素材复核保存使用声明及绑定当前脚本/音频的试听结论，Rights 为 KNOWN（限定本次作品），不代表第三方合同保证或公开发布批准。该旁白已不再阻断 Gate，生成记录仍只有一次。

[素材缺口恢复任务](tasks/creator-material-recovery-2026-09-30.md) 软件与同一 Creation 的阶段恢复已完成：来源修订只扩展明确选择的 BGM 来源，保留脚本/场景/旁白 Need 与冻结 Handoff；正式旧/新 Plan revision、父 SupplyRun、Bundle checkpoint 和请求身份记录，补充缺失素材。中断后对账完成的 Supply，重复请求复用结果。早期恢复保留原 7 个 Asset，集合增至 38 个；后续仅补缺失窗景，再经逐 Need 核对与独立配乐 Rights/署名复核，Material Gate READY，进入上述真实制作与最终入库。配乐试听、缺失署名事实和旁白试听结论都在普通作品区处理，未知许可不被 UI 合并放行。前一组合 127 passed；最终增量 Material/Compiler/Rights/敏感接口 52 passed（28 deselected），lint/build、compileall、技能合同和 diff check 通过。最终成片基本质量已由 Creator 审阅接受，但自主 E2E 因工程介入失败；完整运行与限制见同一份 [Acceptance](acceptance/creator-audio-quality-e2e-2026-09-30.md)。

### 当前 Goal：自主首版与 Director 全链执行

- **工作区 UI 信息层级优化（2026-10-01）：** 当前状态/成果与待办置于作品画布首要位置，预算与默认折叠的执行记录下移；状态只保留一处主标题，更新时刻改为紧凑本地时间。统一状态标识、卡片留白、画布底色、标题层级与窄屏间距；日志改为时间/事件两列，长方案说明提供摘要与完整展开入口。准备完成标签只显示投影中确已完成的内容/素材阶段，避免固定文案误报。前端状态场景、lint/build、diff check 通过，Safari 实际制作页面已检查状态卡和日志展开/收起；未修改生产逻辑、重启后端、重试或额外调用模型，当前任务继续原运行。保留既有 Hook 与包体积提示；本次未重新跑真实制作或完整 E2E。

- **制作执行记录可见性（2026-10-01）：** 用户实际委托在 20:37:16 发起内容准备，20:41:41 返回终态，随后 20:41:45 进入创作规划；只读执行证据显示多轮画像/目录查找、一次截短路径纠正、读取与四文件编写/校验，不将总耗时直接归因为校验或渲染。作品画布新增可展开“执行记录 · 自动更新”，复用现有 5 秒状态轮询与持久 agent_calls/history，显示任务登记、终态、耗时、等待时间与最近核对时间；明确轮询不是新成果，不展示原始提示词/模型思考/输出或凭证。已冻结内容后的等待文案改为“正在创作规划”，不再只说泛化等待。无新后端日志系统或 Provider 请求，未重启/重试/推进当前制作。前端状态场景、lint/build 和 diff check 通过；实际 Safari 页面已展开核对任务 1 的 4 分 25 秒耗时及任务 2 等待记录，后台继续原任务。该入口提供任务级记录，不冒充逐工具实时日志，也未在本批优化执行速度。

- **方案确认按钮误禁用修复（2026-10-01）：** 实际 Safari 对话已选择“旁白 + 一小段低饱和背景乐”和此前明确列为 9:16 的“竖屏”，但固定音轨正则不识别修饰语/空格，方向简称不能绑定已提供比例，助手错排的“音- 画幅：轨：…”还会清空画幅，导致按钮因缺规格被禁用。现共享 Proposal parser 支持明确旁白加配乐表达，只从先前明确比例选项解析用户的方向选择，并限制正式规格标签位置，防止正文/错排标签清空设置；不为单独“竖屏”猜比例，示例、问题、否定与不确定项继续不准入。Preparation/跨内容回放 **55 passed**；真实页面刷新后显示 30 秒、9:16、旁白与音乐、简体中文，制作按钮恢复 enabled。保留用户原填 1 元预算，未点击确认、未启动制作、未修改作品持久状态。服务已重启并通过页面/Gateway 检查；预览与正式确认继续调用同一解析器。

- **中文旁白简繁误判修复（2026-10-01）：** 独立中文样本的真实 ASR 报告已复现：识别文本使用繁体，冻结脚本为简体，旧逻辑误拒。现仅在本地识别核对中使用固定 OpenCC `t2s` 标准简繁转换进行等价比较；不做同音容错、地区词汇替换或脚本改写。匹配后字幕文字/字符位置仍取冻结脚本，时间仍取真实识别，原识别报告及其身份保留；Provider alignment 的原严格合同不变。转换库纳入安装依赖及付费 TTS 前运行预检，避免模型文件存在但缺库时先购买旁白。扩展原恢复场景，验证双向简繁、错字/同音错字/多余内容/漏字/低置信/时间重叠、缓存恢复与不重购。关联 Material/Voice/Cross-Content/Runtime **88 passed**；同一真实中文报告重新绑定得到 READY，保留原文与实测两句区间 0～1.5 秒、1.88～3.88 秒。下方“未修复阻断”为发现时记录，本段为当前修复状态；不代表所有中文识别错误均已解决或真实自主 E2E 已验收。

- **真人试跑前本机准备（2026-10-01，用户授权配置模型并重启服务）：** 两项本地模型已安装到代码默认目录 `~/.cache/easel-models/`，无需修改业务代码或凭证。AST 配乐模型复用此前下载文件，重新核对代码固定的三个 SHA；faster-whisper-small 使用 Systran 上游固定 revision `536b0662742c02347bc0e980a01041f333bce120`，四个模型/配置/词表文件按上游 LFS SHA 或 Git blob identity 校验。两项 readiness 均由 MISSING_CONFIG 转为 CONFIG_READY。实际生产读取函数对独立 10 秒公开配乐样本完成本地推理（Music 0.884159）；对本机系统声音生成的独立中文样本完成识别和词级时序输出，不使用当前作品或云端 TTS。
- **实际中文识别暴露的未修复阻断：** 样本原文“今天阳光很好。我们一起去公园散步。”实际识别为“今天陽光很好,我們一起去公園散步。”；将真实识别报告送入 `timing_from_recognition` 被现有严格原文比对拒绝。当前 `_spoken` 仅消除空白/标点，没有处理简繁形式等价。模型可运行不等于简体旁白准入可用；这是已复现的软件问题，本次配置/重启范围没有修改该逻辑，不能声称中文自主首版已经就绪。
- **重启与准备边界：** 重启前只读确认没有登记自主 Delivery 的 Creation；现有 `com.easel.web` launchd 守护服务使用项目虚拟环境重新启动，首页与 `/api/status` 返回 HTTP 200，Gateway 可达，Hypit doctor 通过。未新建/推进作品、未调用付费 AI 或启动 Build/E2E。整体 v1-release readiness 仍为 NOT_READY：模型认证/endpoint 与实际音画输出仍为 NOT_VERIFIED，本地 Rights-backed 视觉库存为 CONTENT_EMPTY（不代表外部检索或生成不可用）；真实外部制作留给用户发起。本段取代下方历史记录中的“正式音频模型未配置”状态；精细声音评分等仍后移。

- **集中软件回归收尾（2026-10-01）：** 默认 `pytest -q` 首次暴露两套 `tests` 包的收集冲突：内置微信技能的空 `tests/__init__.py` 抢占项目测试包，使跨内容回放无法导入共享夹具；移除该空包标记，保留并执行其全部测试。随后定位并补齐系统审片 JSON 读取的 UTF-8，更新两项已过期的 Mode 1.0 断言为当前正式 1.3。复跑全量 **600 passed / 5 skipped**；前端 lint/build、compileall、115 项技能/发布合同检查及 diff check 通过。两项 Python 依赖提示、AccountsPage 既有 Hook 提示及前端包体积提示保留，未顺手扩项修复。此证据覆盖当前软件组合，不证明真实模型或跨内容成片效果；正式音频模型配置仍未就绪，真人 E2E 仍由用户启动。

- **集中收尾后的必要依赖核实（2026-10-01）：** 只读核对正式配置：ffmpeg/ffprobe 与 faster-whisper/torch/transformers 均存在；`audio.voice-timing-recovery`、`audio.music-observation` 均为 `MISSING_CONFIG`，正式路径下的模型尚未就绪。此前临时 AST 样本推理不等于生产配置就绪。发现语音识别仅列入 full-system，遗漏 v1-release/audio，但正常委托 TTS 实际依赖它；现补齐两个 Profile 的同一依赖，回归先复现漏报，再以 Runtime 定向 **18 passed** 验证；compileall、diff check 通过。未下载模型、改变本机模型路径、启动服务或触碰 Creation。真人验收前的明确准备项是配置这两项本地模型并执行现有 readiness 检查；精细音色情绪评分、扩大音乐校准集和高级场景修订后移，不作为本轮继续扩项理由。

- **本轮集中收尾：内容缺陷返回 Planning（2026-10-01）：** 根因是质量修复只有保护原脚本的剪辑补丁，`repair_target=planning` 没有执行责任。现在复用同一后台 Owner、输出绑定反馈和恢复 Attempt，调用既有 Planning/Truth，再用保留素材重新执行 Match/Readiness。有效改写先存恢复记录；Planning 保存后、Gate 写入前中断会续接同一结果，不再次派发改写或采购。原成片、素材与历史费用保留，新制作不继承原选材、时间线或费用批准；脚本改变会重绑 Voice 文本身份，旧旁白不能凭旧内容证据继续通过，缺料/新旁白回到原有补料、核价、预算和生成路径。素材缺口耗尽后停在实际缺口，不退回首个 Preparation 重跑。
- **明确最小范围：** 自动修正脚本表达、现有场景的叙事顺序和视觉 Need.intent；冻结委托、Creator/Mode、事实与规格不变，Need 集合/类型/用途/scope/重要性/时长/来源约束、声音身份及参数不变。新增或删除 Need、改变上述约束不在本次自动修正范围。沿用每作品最多两轮质量恢复；未知责任不获得改写权限，真实事实缺口仍保留正式 Truth 状态。内容核验完成前不能开始编排；完成后回归原 Authoring/核价/Build/审片，没有第二条主链。
- **本轮验证与限制：** Hypit/Cross-Content/Preparation/Material integration **154 passed**；新增断言复用原高价值场景，覆盖 Planning 路由、禁止直接编排、禁止策略扩权、中断恢复只执行一次、素材字节保留及旧输出/批准不继承。Planning executor 增量场景另 **1 passed**；compileall、diff check 通过。原旁白合同仍覆盖脚本身份改变导致旧语音证据失效。三内容回放继续通过，但本次内容修正只验证到重新规划、素材重核与恢复后续派发；没有声称真实模型改写效果、变更后付费 TTS 或真实再合成已验收。按用户要求本轮集中收尾，不扩展旁白表达或审美增强。剩余旁白表达评估、本地语音依赖及最终集中验收准备仍为 PARTIAL / NOT_READY；未操作现有 Creation、付费 AI、真实 Build 或完整 E2E。

- **内容表达缺陷的责任定位（2026-10-01）：** 原 `repair_request` 将 creator / truth_expression / narrative 的全部失败都当作需改 Planning，画面误导也直接停在质量待处理。现系统审片 `@5` 在这三类失败中定位 `repair_target`：明确为画面表现或原 Need 内素材替换的，进入已有局部修订/观察/补料/Authoring/重新核价/审片路径；真正的脚本、场景要求或叙事顺序问题仍为 planning，不能借画面范围改写。仅定位未知时复用原最多三轮审片观察，只重看尚未定位批次；不会将未知自动改为通过。已完成批次的检查点、原脚本/字幕文字/旁白/时序与身份保护保持。没有新阶段、工作流或 Creator 确认。
- **本批定位与恢复验证：** Hypit/Cross-Content/Preparation/Material integration **154 passed**，compileall、diff check 通过，保留两项既有依赖提示。三内容回放分别覆盖事实表达画面误导、Creator 画面表达及叙事画面问题；首个场景先未知定位、再有界复查定位后修复。原有池内替换、补料中断对账、观察检查点、声音/文字保护、费用重核与当前输出 Quality READY 的断言继续通过。直接合同反例验证 planning/unknown 不授予局部修改、缺少/非法定位不被认作可执行修改，人工审片与旧输出仍保留。模型与渲染仍为 Fixture；这证明责任路由与保护边界，不证明实际审片模型定位准确。该批尚未覆盖脚本/场景内容恢复；其最新实现与限制以上方集中收尾记录为准。旁白表达质量及更广泛声音验证仍未完成；Goal active / NOT_READY，未操作真实 Creation、付费 AI、真实 Build 或完整 E2E。

- **声学观察独立样本证据（2026-10-01）：** 实际本地 AST 对四个公开、来源/许可/字节可追溯的 librosa 示例片段执行分类：vibeace 进入 instrumental_music，fishin 与 libri1 检出人声，短 trumpet 因 Music 分数不足保留 unknown。以相同公开配乐和朗读构造相对 RMS 0 / −12 / −24 dB 的三份混音，均检出人声，未作为无歌词配乐放行。没有为单一样本降低阈值，模型没有接收曲名或期望结论。完整来源、输入 SHA、窗口分数及限制见[具名局部验收](acceptance/local-acoustic-observation-2026-10-01.md)。这补足了真实模型音乐正例与人声混入的有限证据，但不是标注盲测、总体准确率或真实作品听感证明；旁白表达质量、内容缺陷恢复与真实音乐覆盖仍开放，Goal active / NOT_READY。仅文档更新，无生产代码改动；未操作真实 Creation、付费 AI、真实 Build 或完整 E2E。

- **BGM 实际声音观察接入（2026-10-01）：** 原默认分析只支持视觉，配乐匹配可凭标题/语义标签进入制作，三内容回放还需直接补写 BGM caption。现复用后台素材观察、Attempt observations 与普通 Match/Readiness，在本地对配乐候选解码并运行固定版本 AST AudioSet 分类；逐窗口覆盖 1～300 秒资产及尾部，音乐、人声与乐器/曲风标签来自波形，不将 Need 或目标听感喂给模型。报告绑定模型与音频 SHA，按每个 Need 单独应用；无足够音乐证据、弱/不确定人声结论及缺失观察不由标题替代。乐器/曲风排序优先实际分类标签，元数据不能将已观察的摇滚吉他包装成钢琴氛围音乐；其他软偏好仍不升级为硬门禁。原有明确 Creator 核对入口保留，但正常新委托走后台观察。
- 成功的声学报告先落盘，中断后复用再登记 Asset/Bundle；重跑不制造新时间戳。已有可用配乐时不再观察所有候选；单 Need 最多九个候选，超出模型支持时长的候选不进入推理。运行依赖已登记 `audio.music-observation`；需配乐的新委托在新的付费素材请求前预检该依赖，保留已有结果/已提交任务。安装、模型固定摘要与阈值限制见[运行依赖](configuration/v1-runtime-and-external-dependencies.md)。
- **本批声音验证：** Cross-Content/Material integration/Matching/Audio supply/Readiness/Hypit/Preparation/Runtime **199 passed**；compileall、diff check、pip check 通过。三内容回放已删除直接写入 BGM 语义，只替换本地分类器响应；每个作品只分类一次，并注入“报告已保存、Asset 登记中断”，恢复不重复分类/生成。沿用已有音频场景覆盖元数据误导、尾部缺失、音频身份错配、逐 Need 隔离、明显人声、弱分数、非音乐及软风格排序。模型/ASR/TTS/渲染回放仍为 Fixture，不作为真实听感验收。
- **独立本地模型检查与未完成项：** 已在项目虚拟环境安装可选 `torch 2.14.1 / transformers 4.57.6`，公开下载的模型文件在 `/tmp/easel-ast-validation-model` 校验官方固定 SHA，未加入 Git、未设置生产模型路径。实际 AST 对独立 12 秒本地合成正弦音执行两窗口分类，Sine wave 分数 0.881241，配乐结论为 unknown；约 54.56 秒包含首次加载。官方特征提取器有一项零 mel filter 提示。该负例证明实际加载/预处理/分类路径可执行且未把纯音自动当配乐，不证明真实歌曲的人声漏检率、情绪/音色/节奏判断或跨内容风格可靠性。真实音频校准、旁白音色/表达质量、Truth/叙事缺陷恢复仍开放；Goal active / NOT_READY。没有读取或操作现有 Creation，没有付费 AI、真实 Build 或完整 E2E。

- **文字生成视觉素材的内部使用闭环（2026-10-01）：** 原委托声明没有图片/视频生成用途，准入映射也只处理预置旁白，生成视觉素材即使已有观察仍等待人工权利复核。现新确认使用 `easel-input-use@2`，在同一方案确认中明确文字生成图片/视频用途；旧页面摘要拒绝作为新版确认，已存在 @1 声明继续支持原语音范围但不能放行视觉生成。沿用原准入映射、生成锁和 RightsService；完成的生成回执、委托额度记录、模型与输入摘要、异步视频 task 身份、实际资产字节身份、请求时已审核协议及逐 Need 视觉观察齐全时，记录 `internal_production_only/current_creation_only`。新增视觉观察后立即重新判断并走普通 Matcher/Readiness；没有观察、未知协议、旧声明或已有 RESTRICTED 均不自动放行，不复制发布权。
- **条款依据：** 只读重新核对 [MiniMax 开放平台用户协议](https://platform.minimax.cn/protocol/user-agreement)，正文 SHA 仍为 `90d05ccc1dbf8404cbc40cfb096698ceec2bc894440ac507cd048ecb9a896ae0`。6.2 规定输入内容合法授权责任，6.3 不保证输出知识产权，9.5 允许遵守法律与协议条件下选择输出使用场景；1.7 的标识/水印与对外传播条件继续适用。该映射只认领本作品内部用途，不宣称取得全部第三方权利、独占权或发布许可，未评估协议版本仍不自动准入。
- **本批准入验证：** Material integration/Cross-Content/Preparation/Image-Speech generation/Hypit/Library-first **174 passed**；补充验证自动进入 Authoring 后生成委托回归 **9 passed**，compileall、diff check 通过，保留两项既有依赖提示。沿用既有生成、确认与跨内容场景，使用实际本地 PNG/确定性 MP4 解码、Fixture 模型观察及替身 Provider 回执，验证未观察/非 Owner 不准入、旧声明不扩视觉用途、旧语音范围保留、错误模型/输入拒绝、RESTRICTED 不覆盖、重新读取不再生成，以及正式 READY 后直接进入 Authoring。未调用付费 AI、真实 Build 或完整 E2E，未操作现有 Creation。真实声音语义、Truth/叙事缺陷恢复及真实跨内容感知效果仍开放，Goal active / NOT_READY。

- **系统审片分批恢复（2026-10-01）：** 旧审片只在全部画面批次完成后保存报告，后续批次失败会丢失本轮已验证批次的恢复依据。既有确定性审片回放先复现中断后没有检查点。现沿用 Attempt 的 Review 存储，每个已通过合同校验的批次独立保存 `system_pending`，绑定当前完整输入身份、输出 SHA、批次与观察轮次；重试复用本轮已完成批次，包括其尚为 unknown 的结论，从中断批次继续。完成整轮才更新正式系统报告、清理检查点并计入复查轮次。部分结果不冒充审片通过，不覆盖最后可信报告或人工审片；输入变化不复用旧检查点，落盘仍核验输出字节及编排身份。
- **本批审片恢复验证：** Hypit/Cross-Content/Preparation **101 passed**，compileall、diff check 通过，保留两项既有依赖提示。沿用原音画缺陷测试扩展“前两批已完成、第三批中断”、原请求身份续跑、unknown 有界复查、旧输入检查点失效和人工审片保留；没有新增平行审片流程或测试文件。音视频为本地确定性合成素材、视觉判断为 Fixture，未调用真实模型或 Build。整体仍 PARTIAL / NOT_READY：真实声音语义、生成图片/视频权利、Truth/叙事缺陷恢复及真实跨内容效果未闭环，Goal active，未操作真实 Creation。

- **画面错配后的有界视觉补料（2026-10-01）：** 原素材仍准入时 Gate 保持 READY，而旧补料入口只接受 NOT_READY、Supply 又因已有匹配跳过 Need，导致池内没有备选时无法改善成片。现复用既有 `recover_material` 与供应恢复记录：唯一 Delivery Owner 先完成池内备选观察，再仅为缺少替代项的视觉 Need 执行一次原来源权限内的补充检索。系统审片报告、原输出执行身份及未改变的 Need 绑定该请求；声音、脚本、原素材和正式 Gate 语义保留。内容库按字节 SHA 排除原素材，避免不同 Library ID 冒充新候选；检索输入身份包含保留素材集合。新候选仍经原观察、Rights、Match/Readiness 与 Authoring 路径，未新增付费生成或工作流。
- **本批补料验证与限制：** Cross-Content/Library-first/Material integration/Preparation/Hypit **158 passed**；最后输入身份与文案调整后 Cross-Content/Library-first/Material integration **58 passed**，compileall、diff check 通过，保留两项既有依赖提示。既有三内容回放第二个场景覆盖：画面错配 → 池内无备选 → 视觉补料 → 供应结果已保存但 Gate 登记中断 → 对账复用 → 新候选观察/编排 → 重新核价与模拟制作 → 当前输出 Quality READY。查询规划只执行一次，中断恢复没有重复已完成来源检索，原 Bundle、TTS/ASR 与生成额度保持不变；非 Owner 调用在模型执行前拒绝。补料采用隔离本地许可图片，模型、ASR/TTS 与 Hypit 渲染仍为替身，不证明远端素材可得性、真实渲染或感知质量。实际声音语义、生成图片/视频的权利处理、Truth/叙事缺陷恢复及真实跨内容效果仍未闭环；Goal active / NOT_READY。未操作真实 Creation、付费 AI、真实 Build 或完整 E2E。

- **画面错配后的池内备选观察（2026-10-01）：** 原 fork 复制“素材观察已完成”后直接进入 Authoring，而原观察在找到首个可用素材时已停止，其余已接收候选往往没有观察证据。局部回放先复现：有另一张候选图，但修复编排连续三次找不到可用替代项。现唯一 Delivery Owner 在 `visual_material` 修复前复用 `observe_material`；以该次输出质量报告绑定补查目的，排除原选用及受保护的声音/字幕来源，按未改变的 Need 对已有候选执行原有有界观察。原素材和报告保留，新增证据经普通 Matcher/Readiness 后进入上一批替换路径；没有新 Supply、付费请求或第二工作流。原候选已可用不再被误当成“备选也已查完”。
- **本批局部验证：** Cross-Content/Preparation/Material integration/Hypit **154 passed**，compileall、diff check 通过，保留两项既有依赖提示。三内容回放的首个场景现在覆盖：系统报告画面错配 → 新修复 Attempt → 补查已有另一素材 → 普通选材/编排 → 重新核价与模拟制作 → 当前输出 Quality READY；只增加一次模型观察，原素材供应、ASR/TTS、生成额度和源 Bundle 不变。额外注入“观察与新素材 checkpoint 已落盘，但完成状态尚未写入”的中断，下一轮复用证据继续，不重复观察。其余内容的音轨修复及复制中断仍通过。实际模型与渲染仍是确定性替身，BGM 语义仍为 Fixture；不证明真实听感/风格效果。成片缺陷后的外部补料、Truth/叙事调整和实际声音感知仍开放，Goal active / NOT_READY；未操作真实 Creation、付费 AI、真实 Build 或完整 E2E。

- **系统画面错配可使用已准入备选（2026-10-01）：** 原 Quality 将 `visual_match` 失败归为构图修正，但修复合同强制保留全部素材身份，已有备选也无法使用。现仅该类系统缺陷开放 `visual_material`，通过原 fork/Authoring/核价/审片路径，在未改变的 Need 下替换同类型、独立匹配证据齐全的现有视觉素材；共享素材的每个原 Need 均须继续被覆盖。代码和 Prompt 共用当前备选表；保留组件身份、脚本、时序、声音及其他受保护部分，图片尺寸只能改为替代资产的实际检查尺寸。核对本机 Hypit 0.2.7 `media-track` 源码后，明确排除被声音/字幕引用、`source-audio` 或内嵌 Sound 使用的视觉来源，防止换画面时暗中换掉原声。普通 Creator 构图修改范围未扩大；不重新检索、购买素材或复制旧费用批准。
- **Production 选材根因一并修复：** 回归先证明“整体 Material READY + 某候选持久 qualified=true”仍会将没有实际语义证据的备选列入可用集合。READY 仅证明每个必要 Need 至少存在一个可用选项。现 Production 实际候选/选中入口对每个 Need–Asset 重新调用既有 Matcher，复用原 Rights、技术、语义与逐 Need 观察要求；缺证候选被排除，保留有效候选。没有新增准入语义或人工确认。
- **本批验证与边界：** Cross-Content/Preparation/Material integration/Hypit/Readiness/Matching **177 passed**，compileall、diff check 通过，保留两项既有依赖提示。沿用既有测试扩展同 Need 备选进入真实 checkpoint fork 与 Authoring 完成、旧选择不变/新费用未批准、无观察候选拒绝，以及图片尺寸、未授权来源、旁白、时序和原声保护。全部渲染/模型仍为 Fixture；未运行真实 Build 或完整 E2E。该修复覆盖池内已有合格备选，尚未接通成片缺陷后的新增观察/补料、Truth/叙事调整和实际声音感知；Goal active / NOT_READY，未修改真实 Creation。

- **系统音频修复回放闭环（2026-10-01）：** 原三内容回放在实际 MP4 检出缺配乐/旁白末句缺失后，只断言 Owner 选择 `repair_quality`，不能证明正常路径修复后可交付。现沿真实 Web 后台执行到 checkpoint 复用、新 Attempt 编排、重新核价、委托内零费用批准、模拟提交/导出及新输出 Quality READY。三个内容均保留原脚本、Creator/Mode、素材、旁白、时序与有限用途 Rights；原失败输出及其审片记录保留，新的审片绑定修复输出，未自动接受/入库。第二个内容在真实素材复制落盘后注入一次中断，恢复仍为同一 Attempt、同一次修复额度，不重做 Planning/素材观察/ASR/TTS，也不继承旧费用批准；每个 Attempt 仅一次模拟提交，完成后再次推进不执行工作。本批未发现需修改的生产逻辑，只补齐原有恢复链的验证缺口。
- **本批验证与边界：** 跨内容/Preparation/Material integration **108 passed**，compileall、diff check 通过，保留两项既有依赖提示。真实本地解码/音频缺陷检查、持久 Owner/服务/检查点参与回放；模型、ASR/TTS、Hypit CLI 均为替身，渲染器返回确定性合成媒体，不证明真实渲染或感知质量。BGM 语义仍由 Fixture 提供；本次只覆盖使用已准入素材的音轨修复，Truth/叙事变更与素材替换恢复仍未完成。Goal active / NOT_READY；未操作真实 Creation、付费 AI、真实 Build 或完整 E2E。

- **配乐偏好进入检索与排序（2026-10-01）：** 原 `BgmNeedSpec` 只取第一个乐器组成检索词，Planning 提供四条搜索提示时又会将它挤出；匹配排序完全不读情绪、曲风、乐器、能量与速度要求。现为完整声音偏好保留一条实际 Provider 检索请求，继续保留宽泛后备查询；明确允许人声时不再强加 instrumental。现有匹配器读取这些偏好与素材元数据计算 Director 软排序，缺少或不符的偏好不新增门禁，理由明确标为 metadata overlap。普通 caption、关键词与检索排除词仍不能证明实际无歌词、乐器或听感；本批没有新增音频模型，也未声称完成声音感知。实际声音观察及 `vocals_allowed=False` 的有效核验仍未接通，三内容回放的 BGM 语义 Fixture 保留，整体 Goal 继续 active / NOT_READY。
- **本批局部验证：** Compiler/Audio Supply/Matching/Readiness/Material integration/三内容回放 **87 passed**，保留两项既有 Python 依赖提示。扩展既有场景先复现偏好被挤掉，再验证实际 Openverse Fixture HTTP 查询、同一候选池随 Director 配乐决定改变排序、软偏好缺失不阻断、原 Rights/技术准入及跨内容主链兼容。compileall、diff check 通过。未修改真实 Creation，未调用付费 AI、真实 Build 或完整 E2E。

- **预置旁白有限用途自动准入（2026-10-01）：** 原正常路径即使已有输入授权、系统音色和声音内容证据，仍停在 Rights UNKNOWN。现复用后台素材观察操作，对当前委托、请求、费用范围、已确认文字声明、冻结脚本、实际资产、预置音色与独立语音识别证据逐项绑定；满足已评估国内协议版本时，记录 KNOWN 的有限用途依据。政策依据为 6.2/6.3/9.5 的输入责任与有条件输出使用，1.7 的传播要求通过仅限内部制作的范围隔离；不宣称所有权、商业发布许可或单靠付费取得权利。不同协议摘要不自动认领旧政策，已有人工核验/限制不被替换。
- 限定 `internal_production_only` 与 `current_creation_only`：成片可成为待审首版并最终保存，发布入口继续执行上一批范围检查；素材库登记需绑定源 Plan 的作品与 Attempt，复用时不能转给另一作品。旧 Creation、手动生成和证据缺失场景不获得新授权；没有新增 Creator 确认或第二生产路径。
- 三内容回放已移除生成旁白的手工 Rights 放行，实际 Owner/Web 素材观察自动完成此判断并进入原生制作服务与系统审片。协议审核版本在测试中使用明确的合成 Fixture，模型/ASR/渲染仍是替身；增加缺少输入声明、未评估条款、非委托音色、错误作品、识别内容错配及已有 RESTRICTED 的反例，并核对跨作品素材库复用被拒。BGM 听感仍有 Fixture 证据注入；生成图片/视频、真实声音语义、剩余质量恢复和完整真实自主交付仍未完成，Goal active。
- **本批验证：** Cross-Content/Material/Library/Rights/MiniMax/Preparation/Hypit **209 passed**；compileall、115 项技能合同、diff check 通过，保留两项既有依赖提示。还复现 Rights 脱敏删除 URL 片段中的协议摘要，现改为 URL 外独立摘要并在资产使用依据中保留，三内容回放验证判断后与导出后证据仍在。没有改真实作品、调用付费 AI、启动真实 Build、完整 E2E 或发布。

- **成片入库与发布权限解耦（2026-10-01）：** 发现 Creation ready 投影和内容库登记都要求 `READY_FOR_MANUAL_PUBLISH`，而导出仅携带署名，其他素材使用范围丢失。现 Production selection 记录实际所选素材的使用限制，导出前核对当前 Asset 身份/范围，并随输出、最终 Review、Selected Output 和内容库清单保存。审片后改变使用范围不能复用原批准；导出接续同样保留范围绑定。成片已被接受即可显示完成和入库，发布权限不再是这两个动作的前提。
- 已有明确 `internal_production_only` 条件的作品可确认并入库，其发布状态保留 Rights 待核对；Web 发布入口同时核对原导出文件/内容库副本的 SHA、原记录、最终审片及此条件，清单中删掉限制不能放行。没有新增制作确认，也没有给所有生成素材自动附加该限制；本批建立的是可执行的范围保留，不是生成许可自动判断。未调用任何发布程序或外部发布服务。
- **本批验证：** MiniMax/Rights/Cross-Content/Preparation/Material/Hypit/发布防护组合 **193 passed**，最终审片入口与导出期间范围复核增量后 Hypit **46 passed**；compileall、115 项技能合同、diff check 通过，保留两项既有依赖提示。扩展原生命周期与选材场景，覆盖普通与内部用途成片的入库、读取恢复、重复登记、使用范围变化和发布接口拒绝；无真实 Creation、付费 AI、真实 Build 或完整 E2E。生成 Rights 自动准入、声音语义和其余恢复仍开放，Goal active。

- **生成素材请求前的协议证据（2026-10-01）：** 查明当前委托生成只保留费用来源，没有保存适用服务协议；后续 Rights 因而无法核对生成时的依据。现委托内首次核价同时读取国内 MiniMax 官方协议正文，保存原文、URL、时间与 SHA；执行前将报价、已确认的文字使用声明和账号范围摘要一并写入原生成记录。图片/视频/旁白的资产 sidecar 带协议摘要和逐资产生成来源引用，绑定真实接收字节。协议正文是外部证据，不是指令、用户接受声明或系统许可结论；UNKNOWN 不会因此变为 KNOWN。
- 本次只读核对官方 [用户协议](https://platform.minimax.cn/protocol/user-agreement)：1.7 涉及输出传播标识与原标识保留，6.2 涉及输入权利，6.3 不承诺所有生成输出权利归用户，9.5 要求核对真实性/合规性/适用范围。实际正文解析为 17757 字符，SHA `90d05ccc1dbf8404cbc40cfb096698ceec2bc894440ac507cd048ecb9a896ae0`（2026-10-01）；不把该摘要当作永久许可白名单。缺少适用输出依据与可执行条件的自动准入映射仍未完成，不能据本批宣称已免除 Rights 人工处理。
- **本批局部证据：** MiniMax Image/Speech/Video、Rights、Cross-Content、Preparation、Material integration、Hypit **190 passed**；compileall、115 项技能合同、diff check 通过，保留两项既有依赖提示。沿用既有三内容与委托生成场景验证协议/输入声明到资产的关联，以及查询重试、本地接收恢复不重新抓取或覆盖请求时证据。新增一个等价参数场景：协议读取首次失败时，没有费用占额、生成记录或 Provider 提交，后台重试后仅生成一次。缺失/错误页面不作为协议正文保存；旧记录与手动生成不回填新协议。仍需实现生成权利条件的自动判断/落实、声音语义与其余恢复；Goal active，未操作真实作品、调用付费 AI、执行真实 Build 或完整 E2E。

- **未配置 Runtime 时的补料根因修复（2026-10-01）：** 实际素材恢复把 `BLOCKED` 一律当作视频制作已开始；尚未配置 Runtime 的准备阶段因此无法执行免费补料。旧恢复场景提前写入 `NOT_SUBMITTED`，掩盖了这个正常路径阻塞。现首次补料和中断恢复均接受未开始制作的 `BLOCKED`，仍保留费用已批准、编排已开始和已有输出等保护，不改制作状态或放宽准入。既有自动补料场景保留真实初始状态，先复现失败，再验证补料完成、状态写入中断后复用已完成供应、原脚本/旁白/Need 不变，以及开始 Build 后新请求仍拒绝。
- **三内容回放接通委托旁白生成：** 同 Creator/Mode 的三个内容现在由真实 Owner/Web 分派按确认时的 CNY 1 测试预算核价、占额和执行 TTS；仅官方报价文本与语音适配器返回确定性 Fixture。验证 Director 朗读参数进入实际生成调用、每部只读取一次价格/音色依据、生成一次、预算记录完成，并继续后台独立声音内容核对。回放不再直接调用生成服务或手动登记生成结果。
- **本批验证与边界：** Cross-Content/Preparation/Material integration/Hypit **152 passed**；compileall、115 项技能合同、diff check 通过，保留两项既有依赖提示。生成后 Rights 仍为 UNKNOWN；回放明确补入自有合成音的 Fixture 证据，BGM 语义仍是固定证据，本地 ASR 模型预检以替身代替。因此本批不证明生成权利自动处理、真实声音感知或完整自主交付；模型与 Hypit CLI 仍为替身，未进行真实渲染。生成 Rights、声音语义和剩余恢复继续开放，Goal active；未改真实 Creation、调用付费 AI、启动真实 Build 或完整 E2E。

- **跨内容回放从委托进入准备与供应（2026-10-01）：** 原跨内容场景直接建立 Handoff/Attempt、持久化 Planning、调用 Supply/Gate，未证明确认后的后台接线。现从含 30 秒/9:16/普通话/混音规格的结构化委托出发，由真实 `advance_creation → web._execute_creation_delivery` 领取准备、冻结四份文件、建立 Handoff/Attempt、调用正式 Planning Prompt 与系统 Truth 审阅，并执行 Local 检索/接收/普通 Gate；仅在模型调用边界写入确定性回答。三个不同内容不再由测试直接建立这些阶段状态。
- 回放同时补齐真实隔离 Profile 文件，验证其源摘要与三份 Handoff 一致；此前只有 Profile 名称的 Fixture 无法通过真实准备校验。本地图片和配乐改为逐文件 SHA 绑定的 Rights sidecar，经过原权利读取器，不再由宽泛回调给所有素材赋权。三份 Content 摘要不同、Profile/Creator/Mode 一致，准备/Planning/Truth 每部仅执行一次，后续仍经过上一批真实后台检查和制作服务到系统审片；已有断连恢复与音轨缺失负例保留。
- **本批验证：** Cross-Content/Preparation/Material integration/Hypit **152 passed**；compileall、115 项技能合同、diff check 通过，保留两项既有依赖提示。仅修改既有回放与本状态记录，未新增产品逻辑或测试文件。仍不能称全阶段自主首版：旁白生成和生成资产的 Fixture 自有权利、BGM 语义证据还在回放中显式补入；模型/ASR/渲染为替身，未验证真实感知与审美。生成 Rights、声音语义和剩余恢复仍开放，Goal active；未改真实 Creation、调用付费 AI、真实 Build 或完整 E2E。

- **真实后台分派入口修复与跨内容回放扩展（2026-10-01）：** 将原回放的旁白核对、素材观察改为经 `advance_creation → web._execute_creation_delivery` 调用后，复现 `MaterialProductOrchestrator` 未导入造成的 `NameError`；后台三次后停住，而直接调用领域服务的旧测试未覆盖这个入口。现补齐入口导入，素材观察、旁白核对和已接收素材恢复均经过真实 Web 后台分派验证，未增加第二推进路径。
- 三内容回放不再直接写入 `BUILD_COMPLETE` 和正向输出记录；改由实际 Authoring/Runtime/Plan/Pricing/委托零费用批准/提交/状态/导出服务建立正式身份和检查点，再进入系统 Quality。只替换隔离 Authoring 模型调用、Hypit CLI 与感知边界，CLI 固定返回确定性本地 MP4，实际导出仍检查字节、画幅、时长、音轨与输出身份。每个阶段重建事件循环，第二个内容模拟状态断连，后台保留最后可信状态后恢复，同一内容只派发一次编排、一次模拟提交、一次导出；完成后再次推进不调用模型或 CLI。原缺失配乐/旁白末句的实际音频缺陷仍进入已有局部修复判断，人工审片与 Selected Output 保持未确认。
- **本批验证：** Cross-Content/Preparation/Material integration/Hypit **152 passed**；委托生成接收恢复也改走同一 Web 分派入口，验证本地接续不读取凭证。compileall、115 项技能合同、diff check 通过，保留两项既有依赖提示。这是跨模块接线证据，仍不是完整 E2E：准备/Planning/首轮供应与生成前半段仍由局部 API 建立，Rights 为 Fixture 自有事实，模型/ASR/BGM 语义与 Hypit CLI 为替身，MP4 不是原生工程实际渲染。生成 Rights、真实听感及全部阶段由 Owner 自主推进仍未完成；Goal 保持 active，未触碰真实作品、调用付费 AI 或执行真实 Build。

- **Director 风格进入视觉生成请求（2026-10-01）：** 已复现 Mode 风格虽进入 `Need.constraints.preferred_style` 和检索，图片生成却仅取 `ImageNeedSpec.visual_style`，视频生成仅发送场景描述。现两条生成路径共用有效视觉描述，将原内容描述与当前 Need 风格传入实际 Image prompt / Video text 请求；执行摘要绑定完整请求文字，恢复不静默更换风格。Planning 将镜头级 `preferred_style` 作为有效选择，缺省先取已有 Image `visual_style`，再取冻结 Mode，保持检索/匹配/生成的风格来源一致；仍允许 Director 为具体镜头明确覆盖，不固定主题、镜头数量或素材内容。
- 核对官方 [Image 文生图](https://platform.minimaxi.com/docs/api-reference/image-generation-t2i) 与 [Video V2 创建](https://platform.minimaxi.com/docs/api-reference/video-generation-v2-create) 契约：当前 image-01 的视觉要求通过 prompt 传入，独立 style 参数仅适用 image-01-live；Video 使用 text。合并描述后按现有 1500/7000 字符限制在提交前校验，不截断导演要求、不添加未支持的 Provider 参数。仅补全现有执行输入，不新增风格 DSL/Director 实体或准入门禁。
- **本批验证：** Material integration/Image-Speech/Video/Preparation/三内容局部回放 **135 passed**。既有图片/视频用例先复现风格丢失，再修复；冻结 Mode 集成用实际 HTTP Adapter 与 Fixture Transport 验证默认风格、镜头覆盖及旧 Image 字段回退均进入请求，且修改工作区 Mode 不影响已冻结输入、恢复不再次购买、风格变化不能认领旧请求。技术接收继续使用真实图片字节，Rights UNKNOWN 不自动准入。compileall、115 项技能合同、diff check 通过，保留两项既有依赖提示；无付费调用、真实 Build 或完整 E2E，未修改真实 Creation。该证据证明风格进入生成执行请求，不等于真实输出必然符合风格；实际画面与可看性仍需后续观察，整体 Goal 保持 active。

- **视频素材成功后的接收与恢复（2026-10-01）：** 官方 Video V2 查询示例已返回 `cdn.hailuoai.com`，原 Adapter、下载策略、DNS fallback 三份独立域名规则都未覆盖。现三处复用同一 Provider 主机判断，只补入该精确 CDN 主机；不放开整个 hailuoai.com 或任意云存储桶。现有 HTTPS、公网 IP 固定、逐次跳转校验、下载上限和签名脱敏继续执行。契约来源为同一官方 [Video V2 查询文档](https://platform.minimaxi.com/docs/api-reference/video-generation-v2-query)，未下载其中任何真实媒体。
- 原视频下载后直接检查，检查中断仍存 `RESULT_FAILED`，接续会再次查询/下载。现先将接收回执绑定素材字节与任务身份，再执行本地检查；失败进入已有 `RESULT_INTAKE_FAILED`，Owner 复用现有 `finish_material_generation`，无需再请求 Provider 或读取凭证。共用恢复代码同时修正视频的 Provider task ID 与本地 generation ID 混用，保留已登记素材及其证据；当前字节与回执不符时拒绝认领，Rights UNKNOWN 不自动变为 KNOWN。
- **本批验证：** Video/Image-Speech/Acquisition/Material integration/Preparation **157 passed**；现有场景扩展覆盖官方 CDN 返回及跳转、精确主机与仿冒主机拒绝、DNS fallback、本地检查中断后一次提交/一次查询/一次下载、无凭证接续、同一资产/预算保留、字节变更拒绝及图片/旁白共用恢复回归。compileall、115 项技能合同、diff check 通过，保留两项既有 Python 依赖提示。Provider/下载/检查故障均为隔离 Fixture；不代表真实成片质量或生成 Rights 已验证。未修改真实 Creation，未调用付费 AI、真实 Build 或完整 E2E，Goal 仍 active。

- **异步视频素材观察恢复（2026-10-01）：** 已保存服务商任务 ID 后，旧实现把正常排队超时和临时查询断连都存成 `RESULT_FAILED`，并消耗 Delivery Owner 的三次生成重试额度；连续四次未读到结果的隔离回放先复现后台永久停住。现 Adapter 区分尚无终态的观察与明确失败，Material 保留同一 `RUNNING` 任务及最后可信 queued/running 状态；委托执行器将正常等待/临时断连交给现有 Owner 持续观察，不消耗制作失败重试、不重新提交、不重新核价或占额。断连显示既有 `observation_failed` 状态，恢复读取后自动继续。
- 核对官方 [Video V2 查询契约](https://platform.minimaxi.com/docs/api-reference/video-generation-v2-query)：queued/running 为非终态，failed/cancelled 为明确终态。网络异常、429/5xx、无效任务身份不能被当作任务已结束；身份不符不认领结果。明确鉴权/参数拒绝、终态失败及本地接收错误仍保留原有有界错误处理，不自动购买替代任务。官方查询仅覆盖最近七天，超过窗口不能凭缺失记录推断未提交；本批未新增历史任务补单能力。
- **本批验证：** Video Adapter/Material integration/Preparation **116 passed**；原有委托回放扩展为四轮排队/断连后成功，真实 Adapter 查询逻辑、持久 Generation/预算记录和 Delivery Owner 串接，验证执行器重建后同一任务接收、一次提交/占额、无额外授权、未知 Rights 仍阻断。明确终态失败三次后停止；限流/服务错误与鉴权拒绝、取消/错误任务身份有合同覆盖，既有接收检查失败恢复继续通过。前端状态投影、compileall、115 项技能合同、diff check 通过；保留两项既有 Python 依赖提示。全部 Provider 响应为 Fixture，仅只读访问公开契约；未触碰真实作品、付费 AI、真实 Build 或完整 E2E，Goal 仍 active。

- **委托输入使用声明（2026-10-01，Rights 证据链仍 PARTIAL）：** 当前委托只有费用许可，不能作为 Creator 对所提供文字的使用声明；因此生成许可后续判断缺少可复用的输入事实。现有方案预览提供明确声明，在“按这个方案制作”按钮前直接展示，并由同一次结构化确认传回摘要；没有增加弹窗、阶段确认或逐素材重复声明。后端把声明原文、版本、文字使用范围、操作范围、作品/方案身份和原确认来源原子保存在 `delivery.authorization.input_use`，与 `material_generation` 费用权限分开；摘要同时绑定可见文字及版本化范围。
- 普通聊天不能写入该声明，旧页面摘要不能确认已变化范围，同一确认重放保留原时间/来源，旧作品与未声明的既有委托不能通过重放补写授权。没有声明的 API 调用继续保留未声明状态，不从预算或自然语言推断。该记录只覆盖当前作品所提供文字的授权声明，不能推导素材许可、肖像/声音权利、服务商条款适用或发布许可；生成素材仍保持原 Rights 状态，尚未自动准入，也未代用户接受 Provider 协议。
- **本批验证：** Preparation/Material integration/Rights/Image-Speech **128 passed**；扩展既有确认 API、旧委托与委托生成回放，覆盖摘要失效、普通聊天拒绝、作品/方案绑定、幂等重放、旧确认不扩权，以及已有文字声明和预算仍不能把生成资产 UNKNOWN 变为 KNOWN。前端状态投影、lint/build、隔离 1280px/390px Proposal 页面检查通过，声明可见且按钮传回同一摘要、费用参数独立、无横向溢出。页面检查拦截全部 API，只运行临时前端 Fixture；未操作真实作品。compileall、115 项技能合同与 diff check 通过；保留既有 Hook、构建体积及两项 Python 依赖提示。

- **连续旁白下的配乐核对（2026-10-01）：** 上一批只寻找旁白外区间，30 秒作品包含 28 秒正常旁白时会直接落入 `music_unverifiable`，即使实际配乐完整。现优先保留独立区间比较，缺少区间时使用当前已准入旁白的实际音频与播放偏移进行两源线性比较；从成片与配乐参考中扣除可由旁白解释的分量，再比较配乐信号。两条声音共同确定 ±40ms 范围内的编码偏移，避免只追逐配乐相关性而把错位旁白残差当依据。没有重新合成音频、生成新素材或放宽已有通过阈值。
- 同一回放先复现正常长旁白被阻断，再验证真实 AAC MP4 完成检查且进入 `first_cut_ready`；该片配乐被移除后仍检出 `music_missing`，而原旁白测量无缺陷。随机旁白与低增益扫频配乐覆盖有编码偏移的混音、仅有旁白、两源不可区分和无效采样；两源过于相似或缺少有效参考仍保留未知，不伪造声音分离结果。报告升级为 `easel-output-quality@4`，旧 @3 机器结论重新检查，Creator 已接受输出仍不自动重跑。
- **本批验证：** Cross-Content/Hypit/Material/Preparation **150 passed**，包含三份本机 Hypit 静态 check；compileall、115 项技能合同、diff check 通过。只扩展既有风险场景，无新增测试文件；保留两项既有 Python 依赖提示。该证据覆盖受支持原生播放下的采样信号测量，不等于真实语音/配乐听感、完整音乐语义或跨内容审美验收；Goal 仍 active，未调用付费 AI、真实 Build 或完整 E2E，未改动真实 Creation。

- **成片配乐信号漏检修复（2026-10-01）：** 原系统检查只比较准入旁白与实际成片；BGM 即使完全消失，只要旁白正常仍可能得到 READY。现从当前合格 BGM Match、实际源音频和原生编排恢复播放关系，在旁白之外抽取最多三个一秒窗口比较成片与已选配乐的信号，保留 Need/Asset/SHA、时间、相关性和估计增益。源音频过静或比较区间不足记 `music_unverifiable`，不自动通过、不授权重购；检出预期配乐信号缺失记 `music_missing`，由原有有界音频局部修复处理。身份继续复用原执行 fingerprint、输出 SHA 与保存前复核，不增加第二份交付状态。
- 已核对本机 **Hypit 0.2.7** `audio-track` 的实际 `surface.ts`、`program.ts` 和 manifest：支持单段 once/loop 的起点及末端对齐、源截取和淡入淡出；音频淡变按采样时长处理，合法的 600ms 不要求是整数视频帧。避开整段旁白、两秒压低释放余量及淡变区间，比较允许 ±40ms 编码偏移。多段/拉伸等未覆盖形式保留证据缺口。报告升级为 `easel-output-quality@3`，自主流程不再认领旧 @2 的机器检查；既有 Creator 接受与未入队作品不被自动重跑。
- **本批验证：** Cross-Content/Hypit/Material/Preparation **150 passed**；最后增加截取回放后单场景再验，并执行三个原生工程的本机静态 check。三种不同扫频音频分别覆盖起点循环、末端循环、末端一次播放和毫秒淡变；实际 MP4 中去掉 BGM 时，旧旁白测量仍无缺陷，新检查检出并派发音频修复。旁白末句丢失、缓存复用、源字节变化拒绝、缺少旁白参考或拉伸不能假通过均覆盖。compileall、115 项技能合同与 diff check 通过，保留两项既有 Python 依赖提示；未调用付费 AI、真实 Build 或完整 E2E，未触碰真实 Creation。
- **能力边界：** 本批是输出信号核对，不是配乐歌词/乐器/情绪或完整听感识别，也不能证明每一时刻都有正确配乐。当前已安装 OpenClaw `agent` 入口对附件使用 `acceptNonImage: false`，不能直接把音频送入现有图片观察接口冒充听取。正常音频语义观察、生成 Rights 及其余开放项仍需完成，Goal 保持 active；已有跨内容 Fixture 中的配乐语义替身继续明确标注。

- **跨内容串接回放（2026-10-01）：** `test_same_creator_mode_three_contents_reach_reviewable_first_cut` 复用既有隔离环境与原生编排 Fixture。相同冻结 Creator 和完整 clear_memo_video 1.3 包下，通勤等待、学习工具、工作间歇分别使用 2/3/4 句不同脚本、1/2/3 个不同视觉 Need 和不同配乐音频。串接显式委托、正式系统 Truth 审阅、Planning、真实 Local 检索/接收/技术检查、固定 TTS 返回的实际 MP3、逐 Need 画面观察、独立旁白内容观察、原 Gate、Production 选择、实测字幕/配乐压低编译及原生 Run 身份校验。核对 Mode 参数进入检索与 TTS 调用、上一作品旁白不能匹配下一作品、各 Need 选到不同 Fixture 画面、恢复不重复识别/观察/生成；三个工程的字幕、镜头结构和音频字节不同。
- 在渲染结果边界注入三份确定性 MP4，使用真实 Handoff/编排 fingerprint、输出路径与 SHA 校验，实际解码画面和音频，再由现有 Delivery Owner 调用系统审片并保存 `first_cut_ready`。恢复复用当前报告，不自动接受、入库或发布。另将第三份 MP4 的末句声音移除，实际测量得到 `REPAIR_REQUIRED`，Owner 转入原音频局部修复；旧正面报告不认领新输出，不重复素材/旁白请求。该场景只验证修复派发判断，不执行修复后的真实 Build。
- **验证与边界：** 跨内容/Material/Hypit/Preparation **150 passed**；本机 **Hypit 0.2.7** 对三份含配乐压低组件的 Run 均返回 `ok=true`、`targets=[final.video]`，显式静态检查回放 **1 passed**。命令：`EASEL_TEST_HYPIT_CHECK=1 .venv/bin/python -m pytest -q tests/test_creator_content_replay.py`；只执行 check，不运行 Plan/Pricing/Build。默认测试不要求安装 Hypit。编译与 diff check 通过，保留两项既有 Python 依赖提示；无产品代码或前端修改。
- **⑥仍 PARTIAL，Goal 保持 active：** 模型、ASR、配乐语义为明确的 Fixture，Rights 为测试素材自有证据；MP4 用本地 ffmpeg 构造，不是上述原生工程的实际渲染。这里证明后半链的边界衔接与缺陷路由，不证明系统已能独立判断配乐听感、生成素材权利或真实跨内容风格。前半链仍按局部 API 串接，并未完整通过 Delivery Owner 调度所有阶段。真实感知效果、生成 Rights、正常 BGM/Voice 听感和其余开放项未闭环；未继续真实 Creation、调用付费 AI 或执行完整 E2E。
- **正常旁白内容检查（2026-10-01）：** 原本仅缺少 Provider 时序才识别，时间戳齐全的音频没有独立内容核对，普通文字标签仍可能让 Voice Match 成立。新委托复用同一离线识别执行器，正常生成旁白也核对完整冻结脚本；正式 Match 接受按 Need/脚本/音频绑定的系统内容证据或真实 Creator 核对，标题与生成成功不能代替实际内容。有效 Provider 时序保留，缺失时才补 ASR 时序；识别检查点先保存，重新计算原 Bundle/Gate，不重新生成、不改 Rights。未知许可仍阻断，音色/情绪与配乐听感尚未被该检查证明。
- 本轮另核对多模态、高级匹配、音频供应与图库复用 **18 passed**。本机 `faster_whisper` 依赖已安装，但默认模型目录缺少完整文件；未下载模型或修改生产配置。因此目前只有离线识别接口与确定性合同证据，真实识别准确性、误拒率和正常声音效果仍待验证，不能据此宣称无人工首版已经可用。
- 新委托 TTS 在核价、预算占额和真实提交前检查本地识别依赖，避免已知无法核对仍购买音频；已有音频保留。扩展既有 Fixture 覆盖有效/缺失 Provider 时序、实际识别文本不符、跨 Need/脚本/音频证据失效、识别后中断接续及未知 Rights 继续阻断；Provider 时序正常时也要观察，且不覆盖原时间值。相关 Voice/Material/Readiness/Preparation/Hypit/Runtime **205 passed**；前端投影、lint/build、compileall、115 项技能合同与 diff check 通过，保留既有 Hook、体积及两项 Python 依赖提示。测试识别器为确定性替身，未证明真实 ASR 准确性或听感；未调用付费 AI/真实 Build/完整 E2E，未修改旧 Creation。
- **审片未知结论恢复（2026-10-01）：** 原 `INCOMPLETE` 被永久缓存，Delivery Owner 直接停住；有确定缺陷但同时存在未知结论也无法进入已有局部修复。现在同一输入最多三轮观察（含首轮），仅重新请求含未知结论的画面批次并附未确定问题，复用其余批次；每轮身份与次数绑定当前输出和冻结上下文。检查中断不消耗已完成轮次，恢复使用相同请求身份，沿用网关对账；不重做视频或购买素材。未知消除后进入原质量判断/局部修复，达到上限仍保留未知，绝不转成自动 PASS。复查改善暂时判断不足，不保证相同采样能解决一切证据缺口；更丰富观察、正常 Voice/BGM 听感和跨内容交付仍未完成。
- **本批局部验证：** Hypit、Preparation、隔离 Authoring、Material integration、Compiler **171 passed**；另一次含 Image/Speech、Library-first、Audio supply 的组合 **77 passed**（覆盖有重叠，不相加）。多批次固定预览验证只重查未知批次、重启沿用身份、三轮上限、上下文变化失效、解决未知后允许已有近黑修复及人审保持 pending；音画测量继续解码确定性本地 MP4。compileall、115 项技能合同与 diff check 通过，两项既有 Python 依赖提示。无前端源码修改；未调用模型/Provider/Build，未改当前 Creation，未执行完整 E2E。
- **旁白供应接线修复（2026-10-01）：** 把已有冻结 Mode 场景继续送入真实 `ProductMaterialSupply`，复现 `voice_delivery` 对象被 `NeedCompiler` 当作标量检索条件拒绝，进而伪装成 Local 来源失败。现在仅对 Voice Need 的已知执行参数验证后从检索 filters 排除；原 Need、生成参数、Match/Rights/Readiness 不变，未知复杂条件仍拒绝。扩展既有集成与编译器回归，先失败再修复；Compiler、Material integration、Image/Speech、Library-first、Audio supply **77 passed**。这证明旁白供应可以走到实际检索，不证明正常声音观察、生成 Rights 或跨内容首版交付已经闭环。

原始产品目标对齐、流程重审与 Director 实际执行链只读核对已完成。已确认两组根因：缺少持续自主交付首版的责任与执行闭环；Mode 在 Planning 中有体现，但 Material 风格参数未接全、Voice 朗读要求未进入实际请求、Production 未完整落实文稿、Quality 仍依赖人审。用户已批准将合并方案写入文档并设 Goal 实施，[同一任务](tasks/creator-autonomous-first-cut-2026-09-30.md) 已替换为唯一实施方案。

当前：Goal 保持 active，①～⑤ **PARTIAL**。已接通委托推进、素材风格与观察、Truth 系统审阅、Voice 参数/时序、原生字幕/旁白/配乐压低及导出后的系统审片。已接通有证据的构图/字幕/混音两轮局部修复；已有候选替换与一次原许可范围内补料也已接入；逐 Need 视频观察区间已绑定原生取片；委托内付费执行、声音内容观察、其余质量缺口恢复及⑥跨内容回放仍未闭环，不能据此宣称“持续自主交付可看首版”或风格一致已实现。

- 新的结构化确认把方案原文、摘要与授权来源原子保存到同一 Creation；后端生命周期扫描仅接管带新委托记录的作品。旧 Creation 不迁移、不入队，旧确认重放也不会被接管。
- 后端从现有 Preparation/Attempt 状态推导下一项操作，复用准备、编排、Runtime、Plan、Pricing、提交、对账、状态查询和导出服务。页面对新委托只读轮询，不再用 useEffect 推进上述操作；处理正式 Truth/Material 决定后由后端观察证据继续。
- 独立 OS 执行锁覆盖同一作品的一次操作；并发调用不派发第二份任务，协程取消要等实际执行结束才释放锁。已知失败最多自动重试三次，持久计数不因重建执行器消失。Build 提交不确定只对账；状态查询失败与制作失败分开，继续保留最后可信结果。
- 按本机 Hypit 0.2.7 `packages/cli/src/output.ts` 的正式核价合同，全部请求确认为 resolved/local 才记录 0 美元。新委托自动批准仅此类无 Provider 费用的 Build，并保留当前 Plan/Pricing/fingerprint 与委托来源；未知/有费用结果仍需明确批准。删去前端 1 美元占位，未承诺 Provider 消费硬上限。
- **恢复增量（2026-10-01）：** 新委托的准备、Planning 与隔离 Authoring 调用在派发前保存请求摘要及网关运行身份，使用本机 OpenClaw 的 `gateway call agent` / `agent.wait` 正式接口；提交超时、查询超时和等待执行不触发第二次派发。对账要求同一网关 Profile、同一 runId，以及带结束时间且没有 yield 的终态。Creation 调用记录只保存身份/摘要/状态，不保存原始提示或模型回复。合同来源为本机安装包 `agent-via-gateway`、`gateway-cli`、`principal` 与 `chat-abort-ops` 源码：idempotencyKey 即 runId；不存在的运行也可能返回 timeout，因此 timeout 不能解释为执行不存在。
- 原隔离 Authoring 在调用退出时无条件删除临时 Agent/工作区，会破坏网关仍在进行的写文件。新委托在待核实时保留受限 Agent 和隔离输入/产物，对账结束后继续校验与提升；外层 Authoring checkpoint 提交后才清理。原派发指令保存在受限隔离区并按摘要校验，恢复优先接回最后一个未清理的编排回合，避免因阶段提示变化重新派发。完成文件可跨执行器重建恢复，无需再请求模型。旧普通调用继续使用原有清理行为。
- 导出先保存绑定当前 Build、输出名、署名、已通过技术检查的元数据与 SHA 的凭据，再发布和登记文件；Attempt 级导出锁串行化 API/后台请求。发布前、发布后、登记时中断都复用同一已验证字节，不再次执行 Hypit get；不同输出或文件 SHA 改变拒绝认领，最终人工审片保持 pending。
- **未闭环：** 老的未记录网关身份的调用、网关重启后查不到终态，以及“身份已保存但尚未提交”窗口仍保守停留在待核实，不凭猜测重发；这不等于所有外部故障已自动恢复。失败 Build 的有界自动恢复已接入下述现有服务；真实失败恢复效果仍待后续验收。最初导出后停在 `awaiting_quality`，现已接入下述系统审片；局部质量修复已接入下述现有修订服务，不能覆盖所有质量缺口。委托内付费素材执行及②～⑥其余缺口继续按同一 Task 推进。
- **局部验证：** `test_creation_preparation`、`test_hypit_integration`、`test_chat_capability`、`test_openclaw_authoring_boundary`、`test_material_integration`、`test_runtime_config` 共 168 passed；覆盖浏览器请求结束后由后端恢复、跨进程锁/并发/取消、逐检查点重建执行器、不确定提交先对账、查询断连、重试上限、旧作品排除、零费用核价和批准失效后禁止 Build。状态投影检查及隔离 Chromium 桌面/窄屏检查通过，新增后台核价/导出/查询断连场景中页面没有生产写请求。lint/build、compileall、115 项技能合同与 diff check 通过，保留既有 Hook/体积提示。
- **有界 Build 恢复（2026-10-01）：** 后端复用 `retry_failed_film_build`，仍核对 Hypit 的确定失败、原提交 fingerprint、Planning/Truth/Material checkpoint；派发前保存来源 Attempt，目标复制中断后接续同一幂等副本，不把半成品交给普通 Preparation。每个委托最多自动恢复两次；已知复制失败沿用三次重试上限。新 Attempt 重过 Plan/Pricing，旧批准不继承；只有正式核价确认零 Provider 费用才可使用已有委托授权。UI 在后台恢复期间不再误报需要 Creator 重试，耗尽后保留明确阶段恢复入口。
- **Director 执行接线（2026-10-01）：** `clear_memo_video` 升至 1.1，增加一个对应现有软偏好语义的 `visual_material_style`，不设固定题材/故事/场景数。Planning 从当前 Attempt 的已验证 Handoff 读取并绑定到视觉 Need 的 `preferred_style`，具体镜头显式偏好优先；声音 Need 不套视觉规则，旧冻结快照不回填。素材供应改为使用 Planning 已登记的正式 Plan，修复继续消费绑定前模型草稿的问题（该问题也影响 Voice 脚本身份绑定）。同一偏好进入已有 Compiler 首条实际 Provider 查询和 Library AdvancedMatcher，四条检索提示不会再挤掉风格词；匹配仍依赖实际观察，风格偏好本身不提供语义或 Rights 证据。该批次尚未实现自动视觉观察；后续接线见下述素材观察增量，Voice/剪辑风格与成片质量检查仍未闭环。
- **Truth 系统审阅（2026-10-01）：** 新委托的 Planning 不再把全部非逐字表达默认交给 Creator。现有网关执行系统审阅，逐项区分有冻结来源的事实改写、非事实创作表达、系统自行引入且应修正的表述，以及委托真正必需的信息缺口。报告绑定当前 SCRIPT/Truth SHA，覆盖所有待判断句；事实改写必须引用可用冻结原文，缺失/不匹配/不可公开来源不能通过合同校验。外部 URL 本身与 model_inference 不作为证据正文。
- 系统审阅记为 `SYSTEM_REVIEWED`，与 `TRUTH_SUPPORTED`、`DELEGATE_REVIEWED`、`HUMAN_REVIEWED` 分开；现有账本、正式 Truth 状态及 Material Gate 消费该证据。机器语义判断不是确定性事实证明，也不代表 Creator 接受。引用合同验证只证明来源/身份/覆盖，语义是否正确仍取决于真实模型审阅，当前只有固定响应的局部回放，尚未验证真实判断质量。
- 系统新增的无依据表达先回到同一 Planning 修正，最多一个自动修正轮次；修正输入身份在派发前持久化，调用方中断后复用已写结果，不重新消耗一轮。再次失败记为准备失败，不显示为等待 Creator 给虚构事实背书；显式阶段 Retry 才打开新轮次。真正必需且无依据的表述保留具体缺口说明。UI 显示该说明，高级记录分开统计系统审阅，并保留判定原因/引用。顺带修复人工审核时间错误地取第一条自动分类记录的问题。
- **素材观察增量（2026-10-01）：** 新委托在编排前，按已登记的 Need/Mode 偏好对已有候选执行视觉观察；不再等待每个候选都由 Creator 核对。复用现有网关、SemanticInference、Matcher、Bundle 和 Material Gate，没有增加生产主链。图片从原字节解码；视频提取最多五张实际预览，保留采样位置与预览 SHA。图片附件正式进入网关请求，合同已核对本机 OpenClaw 2026.9.4 的 AgentParamsSchema、attachment-normalize 和 chat-attachments 源码；未执行真实模型调用。
- 最初每个 Need 固定分析前三个候选；现改为下述有限候选替换，仍在派发前原子保存候选批次；来源标题只用于提名，不能替代观察。同一素材的每个 Need 独立保存报告，绑定完整 Need、素材 SHA 和预览输入身份；错配、未知、Need/风格变更或字节变更不能借另一场景的描述放行。报告保留实际风格与偏差，沿用现有软风格评分，不把所有审美差异升级为硬门禁。Provider 事实和 Rights 不被机器观察覆盖，系统结论与 Creator 核对分开。
- Pending/超时继续观察同一网关身份，不重发；中断后复用已完成报告，不重新请求素材 Provider。现有本地重算负责更新 Match/Readiness，满足时进入原 Authoring；已失败 Build 的 checkpoint 复制保留观察文件和对应身份，不重新分析相同素材。页面在后台观察期间显示具体状态，不把尚在处理的素材计为 Creator 待办；观察失败显示为素材阶段问题。
- **明确限制：** 这是样本观察接线，不是已验证的真实视觉理解能力。Fixture 固定语义响应，仅验证附件字节、证据合同、状态推进与边界，真实模型是否支持图像、是否判断准确尚待验收。视频采样位置不是逐帧语义边界；主体只在部分样本出现记录 partial，并按下述增量只使用连续相关采样点之间的范围。少量样本未发现标志/文字不证明全片不存在，带此类硬约束的视频仍可能未就绪。区间与取片、替换/补料、Voice 时序及成片检查的增量见下文；剩余声音观察、授权与恢复缺口、跨内容回放继续按同一 Task 实施；不得据此宣称正常路径已完全无人介入。
- **候选替换与自主补料增量（2026-10-01）：** 固定只看前三个候选会漏掉池中已有可用素材，找到可用素材后还会继续消耗分析。现在每个 Need 从已取得、字节有效的候选中冻结最多九项，优先尚未否定且 Rights 可准入的项；逐项观察，找到正式 Matcher 可用的选择即停止，其他 Need 保持独立证据。报告已保存但 Asset 记录尚未更新时中断可直接复用报告。新候选池不会被已否定项挤满，不因候选替换再次请求 Provider。
- 观察后仍有缺口时，新的 Delivery Owner 自动调用原 `recover_materials`，每个 Attempt 只发起一次补充检索；已有持久请求未完成则接续。现有网关根据当前缺失 Need、风格与对应观察提出检索短语，报告绑定请求并限定键/数量/长度。系统只改查询用词，不改变 SCRIPT、SCENES、Need、Mode、Rights 或来源限制，`allow_licensed_bgm` 固定 false；Voice 不进入该检索或生成，已有旁白保留。该增量没有授权付费生成或来源扩张。
- 补料完成后 Bundle 变化触发同一视觉观察与正式 Match/Readiness，具备条件继续 Authoring，无需 Creator 再说“继续”。空的待选择 Authoring 框架不再被误认为已经制作；实际选择、编排开始、费用批准或提交后的素材规划仍不能被覆盖。页面补料期间显示系统正在工作，不把尚在处理的素材算作 Creator 待办。
- 新委托和明确补料请求按来源保存已完成结果，绑定正式 Plan、检索词、Mode 风格输入及素材身份；总 Bundle 登记前中断可复用成功来源，不重复检索/下载。已有候选的 Provider/来源身份在预排序前排除，避免再次下载同一素材、让新候选有机会进入。临时来源失败不缓存为成功；若已有新候选，先保留并进入观察，不因另一来源失败阻断有效进展；无新增候选且来源失败时走原阶段有界重试，成功来源保持复用。单个来源尚未保存完成凭据前的下载中断可能重新执行该只读来源请求，不声称该窗口已具备逐文件恢复。
- **本批素材恢复验证：** Material integration、Preparation、隔离 P0 Fixture、Acquisition、Matching、Hypit、隔离 Authoring **203 passed**；最终 Material/Preparation/隔离 P0 回归 **99 passed**，后续实际补料提示路径、部分来源失败和恢复合同 **6 passed**。覆盖前三项不适合但第四项可用、找到后停止、九项上限、逐 Need 证据、报告登记中断、来源失败后恢复、来源完成后 Bundle 写入中断、同一候选不重复取得、自动补料不扩大 stock 限制、不重购 Voice、未知 Rights 保留，以及补料→重新观察→编排的后端回放。前端投影、lint/build、compileall、115 项技能合同与 diff check 通过；保留既有 Hook、包体积和 Python 依赖提示。使用临时图片、本地 Provider 与固定模型响应，未调用外部 Provider、付费 AI、真实 Build 或完整 E2E，未改当前 Creation。
- **仍有边界：** 检索词符合真实表达、观察效果及来源实际可得性需要真人验收；一次补料无法保证所有素材存在。区间与原生取片绑定见下述增量；BGM/声音内容的系统观察、委托内付费生成及未知质量证据恢复仍待完成，不将这批通过等同完整自主交付。

- **视频观察区间 → 实际取片增量（2026-10-01）：** 根因是匹配只回答整文件是否相关，而原生剪辑没有逐 Need 的源区间约束。现在视频 partial 观察只提取至少两个连续相关采样点之间最长的一段，不跨过不相关/未知样本，不把单个相关帧扩成区间；全部样本适用时仍保留原有全片采样推断。证据绑定 Need、原字节 SHA 与观察输入，缓存版本更新；Matcher 以可用区间时长核对最短时长及软适配度。Rights、标志/文字未知及原有 Readiness 语义不变。
- Authoring 的既有素材清单提供对应场景、区间与稳定原生镜头 ID 前缀；同一素材用于多个 Need 各自独立。隔离编排提交、正式选择和执行输入复核实际 Film 引用的 Item/Member/Layer，按 Normalize 的 Clock 核对原生 trim；起点向上、终点向下取整，全片终点沿用 Hypit 标准化的半入取整。必要场景必须实际进入 Film，不能只声明素材、借别的 Need 身份或经未核对的中间变换绕过。不能解释源区间的编排回到现有 Authoring 修复，不增加 Creator 确认。SVS 属性读取同时修复了嵌套值/字符串使旧正则提前截断的根因，防止漏查或误拒受保护样式。
- **本批验证：** 复用并扩展现有测试，Material intelligence/matching/integration、Hypit、隔离 Authoring、Preparation **183 passed**。临时 2 秒红/蓝视频实际解码采样，分别证明 0～0.95 秒与 1.425～1.9 秒的独立证据、范围长度约束、10 fps 下 0～9 / 15～19 帧原生取片；越界、丢失 Film 引用、借用场景、额外间接取片和受保护嵌套样式改动均被拦截。本机 Hypit **0.2.7 静态 check：ok=true**，单一 final.video 目标；compileall、115 项技能合同与 diff check 通过。没有提交 Build，没有声称生成过本次最终视频。
- **区间证据边界：** 五帧采样不能证明整段每一帧的语义、连续主体或禁止元素不存在；相关区间是有明确采样依据的推断，最终实际画面仍由输出 Quality 核对。固定模型响应只验证系统合同，真实感知与跨内容风格一致仍需后续验收。本批没有调用 Provider/付费 AI，没有修改或继续既有 Creation。
- **Voice 执行与时序增量（2026-10-01）：** `clear_memo_video` 升至 1.2，以现有 Need.constraints.voice_delivery 承载 provider-neutral 的语速倍率、音高半音和情绪选择。Planning 读取冻结 Mode，具体内容的显式选择覆盖对应默认值；旧快照不回填，不把 Provider 音色 ID 写入 Need。`delivery_description` 仍表达完整意图，Planning 必须把可支持部分转为执行参数；生成入口不再静默接受只有描述而没有执行参数的新请求。复杂口音、耳语或表演不被这些有限参数冒充支持。
- MiniMax adapter 将执行要求映射到真实 speed/pitch/emotion 参数，音量保持标准输出，由 Production 后续混音处理。请求身份在付费派发前加入运行配置的预置音色与执行参数；同一 request_id 遇到音色/参数变化拒绝认领，已完成同一输入复用原音频，不重复请求。现有付费批准与 Rights 语义保留，本批没有让未知价格/未批准生成自动提交。
- 按 [MiniMax 官方 T2A 合同](https://platform.minimaxi.com/docs/api-reference/speech-t2a-http.md)（2026-10-01 只读核对）开启句级字幕，使用 stream + exclude_aggregated_audio=false，同时取得完整音频与内联时序，避免额外下载带签名字幕 URL。仅取终态完整音频，不重复拼接前面的分块；没有终态视为结果不确定，不自动重发。Provider 字幕字段在 adapter 内转换成中立的秒/字符区间，未泄漏进 Material Domain。
- 生成记录保存音频 SHA、冻结脚本 SHA、实际检查时长与句级时间；校验完整文本覆盖、顺序、区间与时长。时序缺失/不合法时，成功音频仍保留，标记 UNAVAILABLE/INVALID，不触发重新购买。只有当前 Need、脚本和准入音频一致的 READY 时序才投影为 `productions/easel-authoring/VOICE_TIMING.json`，随既有隔离输入进入 Authoring。Provider alignment 不等于实际听感、ASR 或声音风格验收；原生使用接线见下述增量，最终质量约束仍未完成。
- **原生旁白编排增量（2026-10-01）：** 隔离 Authoring 结束后、静态检查和局部修订保护之前，由现有 Production 集成从当前正式 Plan/Bundle/生成记录重新取得可信时序，填入原生 SVML。`hypit/narration.py` 仅处理时间到帧、冻结原文、完整旁白播放和保留的句级字幕轨；字幕 Style/Frame、旁白起点与增益、画面和配乐仍由原有编排负责。Provider 省略的标点从冻结脚本恢复，每个原文字符只进入一处字幕，不使用 Provider 文案改写内容，不推算逐字时间。Timeline 放不下完整音频、循环/拉伸/截取旁白等进入现有 Authoring 修正，不截断声音或另购旁白。
- 使用 Hypit 0.2.7 的 AudioTrack/Item 和 Typography/Area 明确时间窗，属于整句字幕，未声称具备 Caption 逐词对齐。编译结果可重复执行；正式选择验证检查当前源码与可信输入是否一致，隔离区 JSON 副本不能覆盖原始证据。既有无时序素材不伪造对齐；缺失时序如何自动取得、精确取片、实际输出 Quality 和局部修复仍未闭环。BGM ducking 接线见下述增量，没有把“静态工程合法”当成“成片可看”。
- **配乐执行增量（2026-10-01）：** `clear_memo_video` 1.3 将原 Audio Bible 的旁白期间压低配乐落实为冻结的增益倍率、进入与恢复时间。现有 Production 编译阶段据当前可信句级时序和实际旁白偏移生成 48 kHz program-clock 包络；短呼吸停顿合并，长停顿恢复作者选择的基础音量。原配乐的素材、播放位置、截取、循环相位、增益与淡入淡出保持不变，不能同时将原音轨和处理后音轨叠入 Film。
- 本机 AudioTrack 的 Markup 只有固定增益，底层 AudioClip 已有 gainEnvelope。采用一个仓库提供的 Hypit 原生组件 `@easel/audio-mix@1` 将包络附到现有音轨，沿用原渲染器；没有新 Director、Workflow 或 Production Domain。组件在 Agent 退出后由代码放入隔离检查区，在正式选择验证中放入目标工程，不提升模型生成的可执行代码。组件字节校验、原子写入和已有 Authoring/费用执行指纹覆盖这些文件；未知改动不能被覆盖认领。旧冻结 Mode 不回填策略，不触发 TTS 或改动已有 Creation。
- **本批配乐验证：** Voice/Material/Preparation/Hypit/隔离 Authoring **162 passed**；后续边界修正再跑 Material/Hypit **80 passed**。新增一个跨层场景覆盖整句压低、短停顿合并、长停顿恢复、原音轨连续性、重复 Film 引用拒绝、正式准入与代码指纹。Hypit **0.2.7** 的原生工程 `check` 返回 `ok=true`。另在临时目录执行组件 Producer 与本机 media-execution.audioPresentationFilter，对 5 秒、48 kHz、双声道的确定性 550 Hz 正弦音频验证，旁白/短停顿 RMS 为 2317.08，长停顿为 9268.18，幅度比 **0.25**；没有启动 Hypit Build。compileall、115 项技能合同与 diff check 通过；无前端源码修改，保留两项既有 Python 依赖提示。
- **配乐限制：** 这是实际增益执行证据，不能证明真实选曲适配、源响度平衡或旁白可懂度。基础音量仍由编排选择，实际输出的响度/遮盖、内容和风格 Quality 及有界修复尚待完成；未把固定比例当成自动质量 PASS。
- **已付费结果的本地恢复增量（2026-10-01）：** 核价/自动授权之前先修复成功结果丢失的责任断点。Image/Voice 原先在 Provider 返回后立即做本地检查，失败统一落为不可接续记录；技术检查返回 FAILED 还可能被记成 COMPLETE。现在合法媒体字节、源身份与旁白中立句级时序在检查前提交持久回执；技术检查未通过保留结果并进入本地恢复，已完成的技术检查与既有素材证据不退回 PENDING。同一图片/旁白请求跨进程互斥，活跃请求不能因重入而再次调用 Provider。
- 新委托的 Delivery Owner 从当前 Plan/Need 与 Bundle 查找对应已收到结果，只执行本地检查、时序绑定和正式 Bundle/Readiness 登记；不加载凭证、不调用 Provider、不新增费用确认。首次生成须明确付费批准；新委托内的预算授权见下述增量。已登记结果复用原字节，素材或脚本身份变化拒绝认领；无已提交回执的 GENERATING/SUBMISSION_UNCERTAIN 不进入本地恢复、不自动重发。进程在媒体落盘与回执提交之间退出，仍按结果不确定处理，不声称同步 TTS 已具备 Provider 端对账能力。
- Bundle 登记复用原装配路径，并在既有生成记录保存前后 revision 与 SupplyRun；Bundle 写完、作品 Gate 尚未更新时中断可核对同一登记并补完状态，不重新搜索、生成或重复技术检查。所有重试沿用现有有界次数与阶段 Retry；Rights 仍为原证据状态，恢复成功不自动授予 Rights/Match。页面区分“检查已保存生成素材”与“补充缺失素材”，失败定位素材阶段。
- **本批恢复验证：** Generated Image/Voice/Video、Material integration/store、Preparation **125 passed**；扩展既有用例覆盖同请求重入拒绝、技术检查后登记中断、检查 FAILED 后仅重试本地步骤、冻结旁白时序恢复、脚本/声音/字节变化拒绝、同步结果不确定不重发、Bundle 已写而 Gate 未写时续接，以及未知 Rights 继续阻断。前端状态投影、lint/build、compileall、115 项技能合同、diff check 通过；仅既有 Hook、包体积和 Python 依赖提示。全部临时 Fixture，未调用付费 AI/真实 Provider，未启动 Build 或完整 E2E，未修改既有 Creation。
- **委托预算内生成增量（2026-10-01）：** 新方案确认可同时填写人民币素材总预算，绑定当时的服务、模型、预置音色与账户配置摘要；默认留空，确认重放不能扩大授权。已有免费供给优先，当前必需缺口且方案允许生成时，由同一个 Delivery Owner 调用原 Material 生成服务。每次新提交先按当前官方国内合同核价、将请求身份与费用上界持久占用到 Creation，再验证执行输入并提交；额度跨 Attempt 保留。未知价格、非系统音色、超额或配置变化均不自动购买。已知视频任务查询失败只续查原任务；同步提交不确定保留额度、不重复购买；已有结果仍走本地恢复。人工生成入口和后台共用作品互斥锁。
- 公开核价依据为 [MiniMax 国内按量价](https://platform.minimaxi.com/docs/guides/pricing-paygo.md) 与 [系统音色表](https://platform.minimaxi.com/docs/faq/system-voice-id.md)，2026-10-01 只读核实原地址及官方 minimax.cn 重定向：image-01 为 0.025 元/张，speech-2.8/2.6 HD 为 3.50 元/万计费字符、Turbo 为 2.00 元，汉字计 2 字符；H3-Max 480P 为 0.33 元/秒。语音按全部字符各计 2 的保守上界占额，排除可能另收首用费用的未核实音色。记录价格文档摘要与核价时间，不存凭证；本地额度不是 Provider 扣款硬上限或已核实账单，不进行美元换算。
- **本批预算验证：** Generated Image/Voice/Video、Material integration/store、Preparation、Hypit **177 passed**；最后扩展既有跨层回放为 **5 passed**，覆盖提交前中断后重新核价、0.03 元不能购买两张 0.025 元图片、响应不确定不重买、模型/音色或账户变化拒绝、已知视频任务查询失败后续查且仅提交一次。报价合同、确认 API 非法预算/重放、预算来源记录、未知 Rights 保留均覆盖；前端状态投影、lint/build、隔离桌面/窄屏页面、compileall、115 项技能合同、diff check 通过，仅既有依赖/Hook/包体积提示。公开文档 GET 不是生成调用，未运行付费 Provider/Build/完整 E2E，未触碰真实 Creation。
- **仍有边界：** 当前自动授权只覆盖每个 Need/草案的首次图片、视频或冻结脚本旁白生成；额外付费重做、未知提交的 Provider 对账和预算变更尚未闭环。生成成功不提供 Rights 或听感证据，UNKNOWN 仍阻断正式准入；BGM/Voice 听感观察、其余质量缺口恢复及跨内容风格回放仍需完成；缺失旁白时序的本地恢复见下述增量，真实识别效果未验证。不能据本批费用接线宣称自主首版目标完成。
- **旁白时序恢复增量（2026-10-01）：** 原先只有 Provider 字幕可进入编排，成功音频缺时序时没有恢复路径。现有 Delivery Owner 现在识别当前 Need/脚本绑定的已保存旁白，用已有 faster-whisper 依赖在本地恢复；不下载模型、不请求 TTS、不另收费用确认。识别不注入目标脚本，文本必须完整匹配冻结原文，时间与音频时长一致；错字、漏字、低置信、重叠拒绝。以原文标点合并实际识别词为整句，起止取词的实测时间，不均分时间或重写文稿。
- 成功识别先写本地检查点，再在原生成记录登记 `local_asr` 时序及证据摘要，保留原 Provider 结果；登记中断复用同一识别结果。Production 从正式记录重新核验音频、Need、脚本和识别内容后投影，工作区副本无权覆盖。Rights/Match/Bundle 不因恢复字幕被改成通过。复用既有有界重试和素材阶段 Retry，页面说明只识别已保存旁白；`EASEL_ASR_MODEL` 与默认本地模型目录见[运行配置](configuration/v1-runtime-and-external-dependencies.md)。该恢复依赖不阻断已有有效时序。
- **本批时序验证：** Material/Voice/Preparation/Hypit **162 passed**，隔离 Authoring **18 passed**；模型配置与恢复定向检查 **21 passed**。覆盖无提示词、离线加载、保留真实词时间、模型缺失不启动下载、输入身份错配/缺词/错词/低置信/重叠拒绝、登记中断后识别仅一次、无 TTS 重购及真实 Production 投影。前端状态投影、lint/build、compileall、115 项技能合同与 diff check 通过，仅既有依赖/Hook/体积提示；本批仅文案投影变化，未重复浏览器矩阵。本机默认 ASR 模型目录未就绪，没有运行真实识别或下载模型；Fixture 不证明识别准确性、音色/情绪、BGM 听感或整个自主交付已完成。未运行付费 AI/Build/E2E，未修改真实 Creation。


- **跨内容审片上下文修复（2026-10-01）：** 追踪发现原系统审片只携带 Script、Mode 和 Truth，未提供冻结 Creator Context、Content Core 及当前 Treatment/Scenes，无法按同一 Creator 的身份/语气/受众与各自表达意图审片。现从已验证的 Handoff 和 Planning 读取这些输入，随每批实际导出画面进入原审片执行器；明确同一 Creator/Mode 下允许主题、场景数、叙事结构变化，不套固定模板。报告升级为 `easel-output-quality@2`，增加 Creator 适配检查并把完整上下文纳入缓存身份；旧机器报告重新检查，Creator 已接受输出不被自动重跑。
- **本批审片验证：** Hypit/Preparation/Material **147 passed**，最后系统审片定向回归通过；扩展已有确定性 MP4 用例，以同 Creator/Mode 的职业、通勤、学习三个 Content 上下文验证各自进入审片、缓存互不认领，Creator 公共边界变化也不复用旧报告。身份/语气问题不能借局部视觉修复改写。compileall、115 项技能合同与 diff check 通过；无前端源码改动。本批只证明跨内容的审片输入和缓存合同，不是三支不同内容从委托到成片的完整局部 Replay；该步骤仍未完成，真实模型审片效果未验证。未调用付费 AI、Build 或真实 Creation。
- **生成 Rights 官方证据核对（2026-10-01）：** 已只读查看 [MiniMax 开放平台用户协议](https://platform.minimax.cn/protocol/user-agreement)：§9.5 允许用户自行决定输出物的使用场景，同时 §3.18 要求输入及输出的权利条件成立，§1.7 保留合成标识与水印要求。该公开条款不能单独替代逐素材来源、适用条件与第三方权利证据。本批未接受协议、未操作账户、未把付费回执转换为 Rights KNOWN；自动生成素材准入仍待补齐真实证据链，不能以增加重复人审来宣称已闭环。

- **系统审片增量（2026-10-01）：** 现有 Delivery Owner 在导出后调用实际输出检查，复用原 Review，将机器结果记录为 `review.system`，与 technical/truth/style/human 接受分开。检查要求当前编排与实际提交 fingerprint 一致，报告绑定输出名、SHA、冻结 Mode/脚本、旁白时序及编排内容；保存前再次验证。可信完成报告可复用，检查期间不重新生成素材、下载或 Build；Creator 最终审片保留该机器证据，不把人审接受改写为自动检查通过。
- 确定性检查解码实际视频，以 2 Hz 小图检测连续近黑片段；解码 16 kHz 音频，测量静音与持续削波，并将每句旁白按半秒窗口与准入原声音频比较，核对信号保留、末尾截断与明显遮盖。比较容许 ±40 ms 编码对齐，使用相关性/残差信号比作基线；这不是 ASR、发音/音色听感或精确 LUFS 验收，近黑采样也不保证检出所有短闪帧或解释创作意图。
- 视觉审片通过现有持久网关发送**实际导出帧**，包含旁白句中位置与早期预览，携带冻结脚本、Truth、Mode 和视觉/剪辑/QC 文档。按传输容量分批保留可读预览，不丢弃后半段；每批逐帧记录所见，判断画面匹配、字幕可读、明显风格偏离、事实表达和叙事。无画面/无引用不能 PASS，缺陷也必须引用已观察画面；看不清或证据不足记 unknown。实际测量有缺陷或视觉 fail 时为 `REPAIR_REQUIRED`，无已知缺陷但有 unknown 为 `INCOMPLETE`，其余为 `READY`；仅后者进入首版待审，不自动接受、入库或发布。
- UI 在系统检查时不计作 Creator 待处理任务，显示检查中、证据不足或待修正原因；现有视频保留可看。局部质量修复见下述增量；不支持的修正、修复次数耗尽及证据缺口分别保留真实未完成状态，不冒充已交付。视觉判断使用 Fixture 响应验证合同，未调用真实模型，不能据此证明真实视觉审片效果或多 Content 风格一致。
- **系统局部修复增量（2026-10-01）：** 原修订入口以 Creator 退回为前提。现有 Delivery Owner 将绑定实际输出的系统缺陷映射为独立 `system_quality` 来源，复用同一个 checkpoint 复制及 Authoring/Plan/Pricing/Build/Review 主链，不伪造人工退回、不增加第二条制作链。确定性近黑/声音缺陷和有实际帧证据的可读性/构图问题可发起修正；批次帧索引转换为原视频时间点，修正请求绑定原输出 SHA 与审片报告摘要。
- 同一委托最多两轮自动质量修正；启动前保存来源和轮次，复制中断接续同一幂等副本，重启不重置次数。已成功 Planning/Truth/Material/Voice 和观察复用；新候选不继承费用批准、Build 或输出，仍走正式核价，现有委托只自动批准已证明无 Provider 费用的合成。系统审片网关超时也先核对原运行，不按已知失败重复派发。
- 修正前后比较原生编排依赖：只开放缺陷涉及的画面构图/取片/明暗/平移缩放、字幕样式/安全区或音轨增益/淡入淡出；脚本文字、素材身份、播放时序、轨道引用及未授权部分保持不变。保护实际引用的本地样式内容，不能通过间接引用绕过。新候选导出后重新审片，不因修改文件或 Build 成功直接判 READY。页面显示系统修正中，不增加 Creator 确认。
- **本批修复验证：** Preparation/Hypit/Material/隔离 Authoring **155 passed**，后续扩展质量合同 **3 passed**；验证真实近黑输出产生局部修正请求、帧到时间点映射、叙事缺陷/过期输出拒绝局部修改、复制中断接续、两轮上限、不复制批准、不伪造人审，以及跨层改动被拦截。Creator 状态投影、lint/build、compileall、115 项技能合同、diff check 通过，仅既有依赖/Hook/包体积提示。没有调用真实模型、Provider 或 Build，也没有验证真实模型能否修好；事实/叙事、换素材、缺少语音时序及 unknown 证据的恢复仍待完成，不能据此宣称所有缺陷已自动闭环。
- **本批质量验证：** Voice/Material/Preparation/Hypit/隔离 Authoring **164 passed**，最终相关边界再跑 Preparation/Hypit **97 passed**。确定性音频检出静音、削波、旁白末尾缺失及高配乐遮盖；本地四秒 MP4 实际解码检出前两秒近黑，AAC 旁白仍可比较。系统报告绑定、缓存复用、输出字节变化拒绝、未知帧拒绝 PASS、机器记录不冒充人审、导出自动进入审片及旧报告不认领新输出均有局部证据。前端状态投影、lint/build、compileall、115 项技能合同、diff check 通过；保留既有 Hook、包体积及 Python 依赖提示。补齐原生配乐组件的 Python package-data，临时源码副本构建 wheel 并确认组件和质量模块均包含；未修改本机运行依赖。没有调用付费 AI、Hypit Build 或完整 E2E，没有改动当前 Creation。
- **本批原生编排验证：** 同一组 Voice/Material/Preparation/Hypit/隔离 Authoring 回归 **161 passed**；另扩展现有音频集成场景，验证可信输入编译、篡改投影无效及缩短旁白拒绝。临时目录内用确定性 WAV、原生 SVML/SVS/SVRun 在本机 Hypit **0.2.7** 执行 `check`，返回 `ok=true`、1 个 `output.video` target；未调用 Build。覆盖非均匀句长、旁白偏移、原文转义、保留导演样式/配乐、幂等编译和过短 Timeline。compileall、115 项技能合同与 diff check 通过；两项既有 Python 依赖提示，无前端源改动。没有调用付费 AI、修改当前 Creation 或启动 E2E。
- **本批 Voice 验证：** MiniMax Image/Speech、Material integration、Preparation、隔离 Authoring、Hypit 共 **155 passed**，compileall、115 项技能合同和 diff check 通过；覆盖冻结 Mode 默认与内容特定覆盖、真实请求参数、流式音频去重、句级单位转换、截断/重叠/错误文本拒绝、过期脚本/音频排除、时序缺失保留音频、音色变化拒绝复用及成功请求不重发。测试使用假 HTTP/Provider；没有调用 TTS、真实 Build 或真人 E2E。无前端源改动，未重复执行前端构建；既有前端证据保持独立。
- **本批素材验证：** Material Intelligence、基础/高级 Matching、Material integration、Preparation、Hypit、隔离 Authoring 共 **171 passed**；包含真实本地图片/两秒确定性视频解码、标题相符但判断不符、共享素材独立 Need、未知 Rights 保留、主体晚出现、漏帧/过期报告拒绝、图片附件请求身份、执行中断恢复和 Build checkpoint 复用。Creator 状态投影、frontend lint/build 通过；保留既有 Hook/体积及两项 Python 依赖提示。未调用付费 AI、真实 Build 或完整 E2E，未修改当前 Creation。
- **本批 Truth 验证：** `test_script_truth`、Preparation、Hypit、隔离 Authoring、完整 Material integration 共 **158 passed**；覆盖有依据改写、非事实表达、必需信息缺口、私密/错配/缺失来源拒绝、漏项/过期拒绝、修正后无需人工 Truth 确认进入素材阶段、修正中断恢复、有界失败及显式 Retry。Material Fixture 也隔离本机配置和外部 Provider，回放无网络或真实凭证依赖。状态投影、frontend lint/build、compileall、115 项技能合同、diff check 通过；保留既有依赖/Hook/体积提示，未跑全量测试或真实 E2E。
- **前一风格/恢复批次验证：** Preparation、Hypit、Compiler、基础/高级 Matching、隔离 Authoring，以及定向 Material 冻结风格与失败 Build 恢复共 **133 passed**。验证包含不同来源不可认领、旧/新 Mode 快照隔离、具体镜头偏好保留、正式检索/Library 输入、有界恢复、复制中断继续、重新核价与授权外阻断。Creator 状态投影、lint/build、compileall、115 项技能合同与 diff check 通过；只有既有 Hook/体积和测试依赖提示。未跑全量测试或真人 E2E。
- **2026-10-01 前一恢复批次验证：** Preparation、隔离 Authoring、Hypit 共 **103 passed**，包含一次派发后的超时/对账/身份错配、执行期间保留隔离工作区、完成后复用产物及三个导出中断点与哈希变更拒绝。frontend lint/build、compileall、115 项技能合同与 diff check 通过；只有既有 Hook/体积提示和两项测试依赖弃用提示。本次没有重跑页面 E2E 或全量测试。最初一轮 Preparation 测试暴露了继承本机配置后尝试外部检索的隔离缺口，已中止；Fixture 现固定临时配置、素材库和仅本地 Provider Registry，最终回归不依赖网络或真实凭证。
- 本轮没有修改或继续真实 Creation，没有调用付费 AI、真实 Build 或完整 E2E，没有重启生产服务。最终执行回放使用隔离数据和假执行器；未核实真实交付质量。`READY_FOR_HUMAN_E2E=NO`，旧具名运行及其失败结论保持不变。

## 当前实现能力与具名证据

以下为现行能力汇总；前面的历史增量不构成当前开发队列。

### Official Product Path

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

### Capability Status

| Capability | Status and evidence boundary |
|---|---|
| Creation / lifecycle | Software path is implemented; Creation read-time lifecycle projection, Attempt transitions and selection gates have deterministic regression coverage. A stale Preparation `MATERIAL_NOT_READY` no longer overrides a later selected, reviewed output in the read-time projection. |
| Planning / Truth | Planning freezes proposal, Content, Creator Context and Creative Mode. The explicitly confirmed chat transcript is now SHA-bound into a validated Production Brief and Planning context. The hash-bound claim ledger auto-classifies deterministic scene directions. New commissions execute source-bound semantic assessment and one bounded Planning rewrite before escalating genuine information gaps; `SYSTEM_REVIEWED` is distinct from verbatim source support, `DELEGATE_REVIEWED` and `HUMAN_REVIEWED`. Software contracts are verified; live semantic-review quality is not yet verified. Same-origin loopback review has no manually entered Operator Token. |
| Material sources | Library-first, Local, eligible external routing, Rights/inspection, matching, Bundle and Readiness are software connected. Pexels/Pixabay acquisitions carry mapped official license terms, material-page evidence and listed restrictions; where asset-specific third-party evidence is unknown, corresponding gates still block or request focused review. Generic SHA-bound review remains for unusual/generated/unknown Rights. One Local visual route and one Pexels external-acquisition route through MaterialReadiness are real-world verified. Positive Library reuse remains unverified. |
| AI Material Generation | **IMAGE / VIDEO / PRESET-VOICE TTS SOFTWARE CONNECTED; ALL THREE HAVE LIMITED ISOLATED LIVE EVIDENCE.** MiniMax adapters enter ordinary Material intake/Gate. 新委托可在已批准预算与服务范围内逐次核价并执行；未知价格或授权外费用停止。旧作品不自动认领新授权。 Completed generation is restored only for the current Attempt/Plan revision. The Operator UI now accepts hash-bound, operator-submitted Rights facts for current generated assets and recomputes the same Gate; it does not infer licenses. Unknown Rights blocks admission. 生成旁白已有工程介入的具名制作与入库证据；图片/视频完整真实制作及当前版本自主生成交付仍未验收。 See [AI Material Workstream](workstreams/generated-material.md), [T09A](tasks/v1c-t09-minimax-video.md), and [Image/Voice smoke evidence](acceptance/minimax-image-speech-smoke-2026-09-28.md). |
| Continuity | Provider-neutral references and lineage are software connected; cross-Content adherence is unverified. |
| Rights / attribution | Hash-bound local Rights evidence gates required Needs. Pexels/Pixabay ordinary published licenses no longer default to UNKNOWN after valid acquisition; explicit commercial trademark conditions and other unverified identity restrictions are not auto-cleared. Attribution facts have a software propagation path; 2026-09-30 音画修订版的具名运行已验证 CC BY credit 随导出与入库保留，其他素材及路线不据此推定通过。 |
| Production / Hypit | Selection qualification, current revisions, bytes and SVML/SVRun references are software gated. Non-paid Authoring starts automatically once the confirmed Production Brief and Material Gate are ready. The Creator-facing production card now shows Chinese progress and one primary action; Runtime/check/plan/pricing/export use their existing formal APIs in the background, while engineering controls stay collapsed. The named External Material Creation completed one real Hypit Build; broader V1 lifecycle evidence remains separate. |
| Audio | BGM and accepted audio material can be authored into Hypit tracks in software. Material Layer connects preset-voice TTS using the frozen, truth-reviewed Script; one isolated real TTS output passed technical intake. It is not voice cloning. 2026-09-30 具名音画运行已由 Creator 试听并确认成片入库，CC BY credit 保留；该运行有工程介入，不证明当前版本自主音画交付、跨内容混音质量或风格一致性。 SFX is not a V1 Release gate. |
| Export / Review | Named Local visual and Pexels External Material runs completed export, review and Selected Output. Broader modality and release evidence remains pending. |
| Content Asset / Material Promotion | Formal approved Selected Output is copied into a Creator-visible Content Library project and linked back to Creation / Attempt / Build / output / SHA; four existing approved selections were reconciled idempotently. Attempt Material promotion is explicit and scope-bound; UNKNOWN / RESTRICTED Rights fail closed, while Rights, acquisition provenance, generation lineage and source Creation / Attempt are retained. Deterministic promotion → later Library reuse is verified; the current real Pexels Attempt asset is eligible but remains unpromoted until a Creator/Operator chooses it. See [acceptance](acceptance/content-asset-material-promotion-2026-09-29.md). |

### Named Evidence

- Local visual Web run: Creation `cr_0283a7adf4094e80bc0c59b58a68dc99`, Build `bld_20260924T135801492Z_4696AF96FC`; its Acceptance records the 15-second final video and human-approved Selected Output.
- External Material Web run: Creation `cr_fc46c0fd949a4beca0043be745b9458d`, Attempt `fa_c1e6b95191ce6b69be351d8a39cb1e81`; Pexels MaterialReadiness `READY`, Hypit Build `bld_20260928T162455494Z_A032509CF4`, 10-second 540×960 MP4, SHA-256 `59ad3d0d7ab60673ce7cc728283add9b0de892d2d5996ca4d4d1a7e4f0eb44b3`, Review approved and `final.video` selected. The stale Preparation snapshot remains as history; read-time Creation status now projects `ready` from the selected Attempt.
- Pexels, Pixabay, Coverr, Unsplash and Openverse have dated minimal search/normalization evidence. Discovery does not mean acquisition or Rights admission; Coverr, Unsplash and Openverse remain `DISCOVERY_ONLY`.
- Hypit v0.2.7 remains the locally invoked editing/rendering engine. The old `hypihub.default` endpoint and Hypit Image/Video/Voice generation bindings remain removed. MiniMax Image/Video/T2A are separate remote Material providers; API-key presence does not establish authentication or generated output.
- Latest six-profile readiness and dependency facts: [`configuration/v1-runtime-and-external-dependencies.md`](configuration/v1-runtime-and-external-dependencies.md).

## 当前剩余事项与顺序

- v0.5 软件范围已完成确定性验证；最新正常对话新作品真实验收 **PARTIAL / 4 of 9 / AUTONOMOUS=NO**，已因旁白 ASR 证据不足停止。正式输入、工程干预、调用与费用见顶部摘要及[唯一运行记录](acceptance/creation-latency-v05-material-e2e-2026-10-04.md)。不能继续沿用“尚未启动素材验收”或“没有当前失败作品”的旧阶段描述。
- 未覆盖三项视觉 Need、旁白及 BGM；后续若获授权，从同一有效 Planning 检查点处理。现有能力的无变化重试已耗尽相应停止边界，不降低阈值、不人工改证据、不重复购买。当前新作品预算10元独立绑定，占额0.1048元，剩余9.8952元；实际 Provider 账单未核实，恢复前重新核对累计总账与未知提交。
- OpenClaw Planning 收尾补丁仅离线落盘，未重启加载或真实验证；不把源码修复当成服务已生效。任何后续加载先核对其他活动作品。
- 唯一自主首版 Task 的 A/C/B/D/E 软件范围已完成；完整视频自主交付与跨内容真实感知验收后置，需用户另行启动。不在素材终点派发 Authoring / Build / Quality。
- Library 正向真实复用等专项证据缺口单独保留；P3 尚未启动。具名音画作品曾经人审入库但有工程介入，不据此推定当前版本自主通过。

## Status Rules

- `SOFTWARE_ACCEPTED`: scoped code and deterministic acceptance passed; no live Product proof implied.
- `REAL_WORLD_VERIFIED`: only the named run, artifact, modality and scope were exercised.
- `NOT_VERIFIED`: evidence is missing; do not infer failure or readiness.
- `BLOCKED`: a concrete external/user prerequisite prevents the scoped run.
- Current status belongs here. Workstream/Task/Acceptance docs provide scope and evidence; older audits are historical snapshots.
- The latest test-suite count and duration are a dated measurement, not a target; see [`AGENTS.md`](../AGENTS.md) for risk-based test growth rules.
- The 2026-09-28 portfolio consolidation removed 12 low-value/redundant collected cases, combined BGM/SFX coverage under their shared audio-supply boundary, and collapsed common Markdown renderer smoke cases into one representative contract. It retained the distinct modality, Rights, lifecycle, security, and execution-gate risks. Test-file count changed from 57 to 56; most remaining cases protect distinct behavior.
