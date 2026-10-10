# Easel ADR-005 新版协议单线化任务

- Goal：wc_goal_yYpFxgMopd9MlccK；用户于 2026-10-10 明确要求删除旧版和过渡生产路径。
- 唯一正式 Git 主线：easel-studio → origin/easel-studio；原 Git 分支的未提交历史实验和原始 Attempt 原件不能覆盖或清理。
- 当前正式开发位置：/Users/xgx/Projects/Easel，分支 easel-studio，基线 origin/easel-studio bb01aede668462dce706eeecd8a7737033c25854；原隔离工作树 /Users/xgx/Projects/Easel/.tmp/easel-newonly-bb01aede 仅为历史来源。用户明确授权源工作区直接覆盖主仓库对应路径，覆盖前备份在 /tmp/easel-main-before-cut5-overlay-j0ogqu8o。
- 最新状态：CUT0–CUT5 已完成（CUT5 独立 Reviewer 为用户明确豁免，并非独立评审通过）；CUT6 等待精确 Git 变更归属、提交和非强推。**当前未提交或推送这轮删除。**

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

## 2026-10-10 CUT4 原任务现场恢复与回归证据

Runner 重新发现同一 detached worktree，已恢复至 `/Users/xgx/Projects/Easel/.tmp/easel-newonly-bb01aede`（HEAD `bb01aede`，主仓库 dirty 工作区未触碰）。前次 `wc_job_y6b-38PItarqzcsD` 575 秒超时，`wc_job_4M01XGP4ScySfBbh` 定位父链指纹、Planning 和 Voice checkpoint 的重复验证。

- 当前原件使用单次只读指纹复用与排除历史目录预裁剪；等价性、拒绝 symlink、缓存不跨操作、循环拒绝 **6 PASS**，原 Markdown Source-Ref 双 Fork 本轮 **1 PASS / 301.58 秒**（`wc_job_qf_ZkUGaanMwKp38`）。不跳过父指纹/Rights/Readiness，也不宣称五分钟耗时已适合高频回归。
- 当前完整新协议合同/Material Retry **127 PASS / 73.43 秒**（`wc_job_1b3RWWUANB5fthv9`）；Planning Source-Ref **8 PASS / 34.06 秒**（`wc_job_L3lZILvcF-1Ej63Y`）；Material **111 PASS / 96.55 秒**（`wc_job_gM6-5wbtG34Y1PFf`）；原生 Authoring **41 PASS / 122.64 秒**（`wc_job_rIYiheX66QCu9kyh`）；R4 Planning **30 PASS / 49.32 秒**（`wc_job_M2qcVjor6BjNjjda`）。均为无付费调用的确定性内部测试，存在重叠，不累加独立功能数。
- Python compileall、`git diff --check` PASS；Planning 其余参数化扩展仍需结案，CUT5/CUT6 未开始正式验收或提交推送，旧 Attempt/费用/UNKNOWN/失败证据保持。


## 单一路径与版本约束

仅允许五个结果协议：truth-source-ref@1、material-observation-delta@1、easel-script-claim-ledger@3、quality-review-delta@1、easel-hypit-source@1。
新 Attempt 创建前校验完整版本集合；重试继承原始固定版本，不允许空 pin、部分 pin、hypit_run_promotion@1、旧 Script @2 或两个竞争的 Authoring Writer。
旧 Attempt / 证据不会被修改或删除；get_film_attempt 等只读访问仍允许，任何旧运行/变更必须在发起模型/Provider/Build 前拒绝并提示创建新 Attempt。

## 本轮隔离工作树中的具体变更

- CUT2：result_protocols.validate/inherited/current/selected 只接受完整五项新版；service.create_film_attempt 在创建 workspace 前拒绝旧协议；existing preparation_key/idempotency、所有经 service._save_attempt 的变更拒绝历史版本；Web Authoring 开始前核版本。扩充 tests/test_result_protocol_defaults 的真实新 Attempt、旧版拒绝和无 Hypit Check 负例。
- CUT3：service.complete_film_authoring 仅原生 authoring_publication.complete；Web staged Authoring 仅 AST/typed source 只读校验；material_layer Production 只接受原生 Document 和正式 Need/Match/Rights，删除旧 SVRun 字符串解析/旧音频正则回退、双文件过渡 Writer easel/integrations/hypit/publication.py 及只覆盖旧版的测试文件。保留本地 Hypit check、费用门槛、原件/Intent/文件发表及 CAS。
- CUT4：Script 只产生和校验 Markdown ledger@3；Truth/voice 只消费 source-ref；Planning 持久化与加载强制绑定当前协议和 Truth origin；Material 只调用 facts/delta 和可追踪原始 receipt，旧 compact 直接 JSON 修复与 per-frame full report 模型路径移除；Quality 只调用 quality_results.review，不再重发完整旧审查；Hypit Quality/局部修复统一使用 native revision。
- 旧版 hypit/revision.py 及其他不再可达的测试辅助模块仍暂存，后续必须先替换既有高价值合同断言再删除；不能因文件名旧就删除冻结领域/共享工具。

## CUT2—CUT4 最新实现补充（未经功能验收）

- result_protocols 的不可变 _REQUIRED_PROFILES 是新协议授权依据；DEFAULT_PROFILES 即使被误改成空也不能重新启用旧路径。五项必须全同，否则 old/partial/transition pin 均报只读错误。
- service 的新 Attempt 创建及幂等检索、Attempt mutate、Authoring Owner/validate/plan/fingerprint/quality revision 均改为原生协议。
- Web Authoring Dispatch/stage、Truth 独立/联合、Material compact 的 receipt-only 分类调用、Material delta、Quality delta，以及 Production 所选择的 SVML/AudioTrack/Timeline，均不再执行旧版模型结果/过渡 Writer。
- 原生依赖的共享工具仍保留；老 Hypit revision.py 作为测试兼容/历史只读模块暂存，生产代码已无导入。几个大套件中尚有针对旧模式的断言需要迁移，例如 test_material_integration.py 对已删除的 _hypit_run_markup、tests/test_semantic_planning.py 用空 profile 的历史输入；不删除具有 Material/Rights/Need 防护价值的用例来掩盖缺口。
- 已更新 tests/test_script_markdown.py 的默认 ledger@3/拒绝@2、tests/test_creation_preparation.py 的 source-ref/ledger@3 冷恢复输入，移除单个只验证过渡 SVRun Writer 的旧 test。
- 仅做了 AST 静态扫描：200 个 Python 文件语法可解析，生产 easel/web 范围没有 hypit_run_promotion、ledger@2、_hypit_run_markup 旧分支文字引用；模块导入以及 Python compileall 与 git diff --check 全通过。以上均不是替代真实软件集成。
- **已有真实通过的测试证据**：五项新协议、Material、Native Authoring、SourceRef、Quality、Retry 的多组离线回归已执行；CUT4 的 Planning 巨型两代 Fork 在校验性能上仍超时。当前不提交不推送，不能认定 CUT5 完成。

## 证据与阻塞

- **变更之前的基线**：bb01aede 上 Material tests/test_material_integration.py 111 PASS/0 FAIL（Job wc_job_CrISgnwulCKRSzmI），它不是本次新代码的回归证明。
- **本次变更后的静态检查**：Python compileall 及运行模块导入通过，git diff --check 通过；未发现仍可使用 hypit_run_promotion、Script @2、旧 web Material/Quality 派发器的正式调用路径。
- **本次功能测试已有实际 PASS**：完整 Material 111 PASS、Native Authoring 41 PASS、多个 Truth/Quality/Retry 定向组合全绿。完整 Planning 和巨型两代 Fork 未通过性能验收。不得把编译/导入等同于运行正确。
- 当前不执行真实 Agent/Provider/Hypit Build/媒体成片，不提交、不推送尚未完整验收的删除工作，不清除历史预算/FAIL/UNKNOWN/旧 Attempt。

## 后续收口标准

完成真实内部 Creation/Handoff → Planning/Truth → Material/Readiness → native Hypit Authoring/check → Quality → Review，覆盖新 Attempt 默认、Retry/CAS、Intent 冷恢复、原件不重发、历史失败明确拒绝和 Rights Gate。
在同一 SHA 下目标测试集合与相关冻结合同全部通过后，按 AGENTS.md 复核/更新 CURRENT 状态，精确 Git 提交并仅对 origin/easel-studio 做非强推，不引入 ADR005 长期开发分支。

## CUT5 回归实测进度（2026-10-10，全部为离线测试）

实际运行测试需与 bb01aede **之上的新代码改动**区分，禁止借用旧版 111 PASS：

| 组合 | 结果 | 重要内容 |
|---|---|---|
| tests/test_result_protocol_defaults.py + tests/test_script_markdown.py | 19 PASS | 五项严格 pin、新建 Attempt、历史只读/拒绝、Markdown @3 |
| 原生 Authoring 五套（native_authoring_publication、owner_recovery、hypit_native_source、native_cli_boundary、native_hypit_static） | 41 PASS（Job wc_job_ZQBqUwgfDdpmz3Vv） | 真实解析、隔离候选、Check、发表、冷恢复 |
| test_script_truth + test_material_result_delta + test_quality_result_delta + test_material_control_contracts | 94 PASS | Truth/Need/Rights/Material facts-delta/Quality delta、回执篡改 |
| test_creation_preparation 源引用冷恢复 + test_native_quality_owner + 默认 pin | 14 PASS（Job wc_job_eEOHb8Rr77D-9HkY） | 原始 Source-Ref 与新 Quality Owner |
| test_material_result_fork | 1 PASS（Job wc_job_o7Za7_uQXHRSJslu） | 真实原生 Authoring + 模拟失败 Build + Material proof 两代 Fork |
| 新增 tests/test_newonly_authoring_boundaries.py | 7 PASS（Job wc_job_mie1f1_v98bagS6_） | 伪造 src/Need/SHA/Run/额外字段以及旧 Attempt 明确拒绝 |
| 完整 tests/test_material_integration.py | **111 PASS / 0 FAIL**（Job wc_job_el-5CYcjaxmOWFbq） | 剩余旧 Authoring、旧完整观察/分组、预算/素材准入测试仍依赖旧版模拟输入；不能忽略 |

这些组合有重叠，不能直接求和为独立测试总数。针对 40 项失败，用户要求的是**迁移高价值 Material/Rights/Readiness 负例到原生协议**，不能通过统一标记 skip/xfail、删除整组失败测试或放宽事实/证据要求来获取表面 PASS。已经新增 7 项真实 Native Authoring 负例以及迁移 Material fork 冷恢复。完整 Material 集成与旧 Planning 参数化套件尚未完成迁移，CUT5/CUT6 **未完成**，当前**不提交、不推送**。



## CUT5 追加：新协议入口安全与合并回归

- 现有核心服务对旧 Attempt 的防护从“仅保存时拒绝”加强到在外部 Hypit/Provider/Build/定价/重试操作前拒绝。覆盖 Authoring、Validate、Pricing、Budget、Build/取消、Runtime 绑定、Retry、Quality repair/Revision 等入口；旧 Attempt 仍可只读取证，用户主仓库历史数据没有修改。
- tests/test_result_protocol_defaults.py 的旧 Attempt 负例扩展为 11 个关键入口不会触发外部 CLI/Provider，重新执行 9 PASS。
- 新版离线组合 test_material_result_fork、test_result_protocol_defaults、test_newonly_authoring_boundaries、test_script_markdown、test_script_truth、test_material_result_delta、test_quality_result_delta、test_material_control_contracts 在同一运行取得 **121 PASS、0 FAIL**（Job wc_job_Qz5lGQmD5w4iPOY9，47.77 秒）。这是新防护实施后的证据，不是旧版111测试记录。
- 旧完整 Material 集成套件已迁移并取得 **111 PASS、0 FAIL**，旧结构测试需要逐个对应新 AST、Material facts/delta、Rights/Need/Readiness 语义迁移；不跳过/清除失败获取假绿。
- Markdown Source-Ref→双 Fork 长链尝试从旧 partial pin 改为完整五profile和严格 native Check，先后遇到旧recipes.svs提前缺失、旧 CLI Check shape 的真实测试夹具问题；夹具已改为先注册recipes、校验typed Run、返回完整Check合同。最后一次作业 wc_job_YIwELA71LQZHCHRb **220秒超时**，尚无PASS；需要定位是否模型无关 Owner 产生等待/锁或测试设计已失效。
- 静态扫描覆盖 200 个 Python 源/测试文件，AST 无语法错误；生产代码旧 hypit_run_promotion、ledger@2、_hypit_run_markup 无引用。主仓库未提交文件继续保留；尚未commit/push本轮清理。



## 2026-10-10 本轮阶段验收

- **CUT2（本地验收完成，未发布）**：五个不可变完整 pin、创建/幂等、旧历史只读以及 11 个执行入口先校验版本后发生任何外部效应；new-only protocol defaults 9 PASS，且被包含于下述 121 PASS。
- **CUT3（本地验收完成，未发布）**：SVRun-only 过渡 Writer 与旧 Authoring service/Web/Material 路线删除，原生 AST Check/Publisher 独占所有权；新增 7 个原生负例 PASS。添加版本执行前置拒绝后重新运行 5 个 native 专用套件：**41 PASS / 124.65秒**（Job wc_job_1ifqGjRt4uYL9rYi）。
- **CUT4（执行路径已清理，剩余旧 Material/Planning 测试迁移中）**：Truth@3/Source-Ref、Material facts/delta/receipts 和 Quality delta 均已定向验收，8 个当前协议/Truth/Material/Quality 合同与 fork 套件**同次 121 PASS / 47.77秒**（Job wc_job_Qz5lGQmD5w4iPOY9）。旧完整 Material 套件已 111 PASS/0 FAIL；Markdown Source-Ref 双 Fork 长链 220 秒超时。不能标记 CUT4/CUT5 全部完成。
- **CUT6（未执行）**：本轮没有 Git commit 或 push，原 /Users/xgx/Projects/Easel 主工作区未触碰，origin/easel-studio 仍 bb01aede。等合同测试迁移完成并同源码通过后才能正常非强推交付。


## 2026-10-10 持续验证（本轮）

- 正式开发目标仍是 origin/easel-studio；本轮仅用现有隔离工作树修改与验证。主仓库及其他窗口未提交修改未覆盖、未新建 Git 分支。
- 新版完整 tests/test_material_integration.py：111 PASS / 0 FAIL（Job wc_job_tIhGrTLN4pb-gITj，103.52 秒）。
- Planning R4 SourceRef、首次素材观察、Quota Preflight 等组合最新 15 PASS / 0 FAIL（Job wc_job_IVSpV_CVMJvjQC9y）；此前 P3 候选纠错 15 PASS、vNext bounded review 36 PASS（不同执行）。
- 新版核心合同组合 51 PASS / 0 FAIL（Job wc_job_h99uO4eLKjsfS42G），含五项严格协议/历史只读、Truth、Material delta、Fork 冷恢复、Quality 增量、Native Authoring 负例、指纹。
- 全量 Planning tests/test_semantic_planning.py 的旧模拟响应迁移仍不完整，长链双 Fork 及大套件多次超时，不能宣称完整通过。不能用已通过的子集替代 CUT5。
- 原生 Hypit Authoring 修改后曾有 41 PASS；没有真实 Provider/媒体/Build。代码编译与 git diff --check 已通过。
- CUT4 需收口 Planning 全链，CUT5 需同一工作树综合无红项，CUT6 才提交且仅非强推 origin/easel-studio。本次未提交/推送。

## 2026-10-10：双 Fork 性能定位与覆盖分离

真实长链表现：tests/test_semantic_planning.py::test_markdown_source_ref_persist_and_two_forks_preserve_full_coverage 离线运行时，49.4 秒完成第一轮模拟失败 Build，但 575 秒总上限内仍未完成第一次 Retry（Job wc_job_y6b-38PItarqzcsD，TIMEOUT，不能认 PASS）。另一简单 SourceRef material_fork 运行在 220 秒后完成第一 Retry，却未完成第二 Build。没有真实 Model/Provider/Hypit Build。

定量性能证据：临时函数级剖析 wc_job_4M01XGP4ScySfBbh 在前约 142 秒内记录到 PlanningIntegration.load 175 次（含嵌套约 164 秒累计），MaterialGateIntegration.assert_ready 110 次，CPU 高负载；堆栈显示 Planning.load → voice_identity.validate_checkpoint → service._execution_fingerprint(source) → authoring_publication._domain → Planning.load / MaterialGate.assert_ready。这是真实重复验证/递归依赖风险，不能以增大 pytest timeout 冒充性能修复。剖析保留在 /tmp/easel-newonly-fork-profile.log，临时文件和测试计时 print 已从跟踪测试代码清除。

同等关键恢复合同替代证据：既有 tests/test_material_result_fork.py 新增第二代 Build_FAILED → Retry，使用真实新协议 Need、Material delta 原件、native AST/Check、Fingerprint、Rights、Cost，只有 Build 状态/价格是严格离线替身。已取得 1 PASS / 0 FAIL，75.46 秒（Job wc_job_aDfKRjN-NpJ4KTGy）。验证两代 Attempt 的 Material Ready、回执资格、费用批准重置、不重复模型/Provider/生成、两代同一 Handoff + 五项 pins、相同失败结果幂等、父记录篡改拒绝。配套 tests/test_script_markdown.py、tests/test_creation_preparation.py 的 Markdown ledger@3/SourceRef 原件与冷恢复另有通过证据。不能宣称单个巨型测试已通过；下一步应在不降低单元覆盖情况下收敛其过度重复的 Planning/Voice 回溯校验，并以可维护的分层测试替代过长的单例。

当前阻塞：CUT4 的 Planning 全套和 Voice checkpoint 递归验证性能仍有缺口，CUT5 不能盖章，CUT6 不执行。主仓库及 origin/easel-studio 仍在 bb01aede，新协议清理草案在既有 /tmp/easel-newonly-bb01aede，无新分支、无新增worktree、无提交/推送。
