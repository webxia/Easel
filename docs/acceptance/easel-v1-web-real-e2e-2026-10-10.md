**2026-10-16 离线修复补记（非真实验收）：**Planning专用原RPC输入隔离、结构化协议@2/Journal@22及已定位拒绝版本/隐式重派修复完成离线验证，78定向回归及本组30项闭合；原R18实际Schema/输入/回执SDK重放、原v1只读、当前Owner A/B/Repair/B-recheck/Proof/冷恢复通过。预算只读预检不等于最终共享准入，整体PARTIAL；真实安装未加载，真实Planning仍NOT_PASS，新增真实HTTP=0、共享60/60与旧29/30封存账本SHA不变。设计、合同简化评估和未闭合项见[Planning§8.40](../tasks/planning-creative-authority-implementation-plan-2026-10-15.md)。

**当前有效Closure（2026-10-16，覆盖此前进行中/暂停NEXT）：**`RESULT=STOPPED / DRIFT=NO_DRIFT / TRANSITION=HOLD（预算耗尽）`。恢复授权44/44HTTP已用完（R14–R19），新额度总60/60关闭；全部HTTP完整、原生released，无Pending/HTTP UNKNOWN。R14真实Repair正文171450字节已派发并回传，容量修复得到真实验证；完整Planning仍NOT_PASS，Truth/D2 Proof/Cold/PLANNING_ACCEPTED未达。期间仅澄清现行资产许可待供应与Creator授权缺失的提示区别，75项离线回归PASS，@21，合同不放宽。最新R19 A全通过、3批B捕获，下一B调用在总额度guard前被拒绝，无第61次远端HTTP。NEXT=停止真实调用；可另行离线调查5次stop零工具结果，任何后续实调需新预算授权。原件/消耗见唯一E2E账本与Planning§8.38。

**当前有效停点（2026-10-16，覆盖历史NEXT）：**输出合同原件离线排查完成；29批225题中51个局部目标，38个原始结构错误、13个领域引用错误，转换前后答案相同。已消除提示题型字段歧义并补音频header排除说明，实际Schema/领域合同未变；52项集成+3项容量回归PASS，Journal/Checkpoint@20。真实调用仍暂停，新增HTTP=0，新额度仍16/60、余44。NEXT=等待用户明确恢复真实调用，完整Planning仍NOT_PASS；详见Planning实施方案§8.36。


# Easel V1 Web 真实 E2E：方案、操作手册与执行记录（2026-10-10）

> **文档职责（2026-10-11 主方案正式批准）：本文件是唯一 E2E 历史及未来运行证据账本，不再拥有独立生产执行标准。** 新生产的 R1–R6、U0–U6 唯一标准已由用户批准，见 [`New-Only → Web E2E 统一主方案`](../architecture/web-backend-new-only-cutover-plan-2026-10-11.md) §8（`APPROVED_SINGLE_EXECUTION_STANDARD`）；具体 U2/U5/U6 执行、模型/Provider/Build、服务与费用仍待单独授权。本文件下方旧 Proposal @3、410、旧 Material 链路、E0–E3 手册均为当时的历史事实与证据，**不再作为未来可执行命令**；7 次失败 Attempt、24/24 次调用、15 份原始捕获、现金/UNKNOWN、SHA 保持原样。以后每轮新增真实执行信息**只在本文件顶部**登记，不在 Creator Task 重复写运行流水，不另建平行账本。**

## 2026-10-15授权／10-16续行｜R12非法来源拒绝；同受测版本R13执行中

R12独立原件`~/.local/share/easel/creator-task-evidence/2026-10-15-planning-m31-controlled-loop-live-r12/`，真实HTTP1/1完成，Token 23539，现金结算UNKNOWN，Pending=false、原Budget已closed。A-selection原raw SHA `dfcae482a2c006e645b0a75899c4f3b5aad782b1b5207b271922c6fec7350253` 的BGM Need scope=`src_37`不在冻结来源enum，原严格Schema拒绝；没有自动补全/替换来源、放宽Schema、改提示词或重派R12。Repair0/3，未到A-details/B/Truth/Proof。这是模型来源身份错误，不是Repair容量修复失败。

同一已验收@18软件以全新R13复验，独立目录`2026-10-15-planning-m31-controlled-loop-live-r13/`、source `dce88741ec533388132ef58bdb56490d5b85507d56a3954d7b5392a95580c85c`。A-selection及A-details-000已通过，后续执行中；使用同一新增60HTTP账本，不跨日重置、不产生媒体/Web/部署/Git授权。最终结果及额度另在顶部收口。

## 2026-10-15｜新增60 HTTP续接：Repair上下文可逆去重54PASS，R12真实复验中

用户明确“再加60次HTTP，还是只用现有套餐”，持续授权修复Repair过大、离线验证后新Attempt调试至首次完整PASS或额度用完，不放宽合同。新共享账本`~/.local/share/easel/creator-task-evidence/2026-10-15-planning-repair-context-dedup-r02/task-http.json`仅启用新增60次，绑定旧账本SHA与已消耗29次；旧30次账本中的未用1次不重开，当前累计消费上界89次。仍无充值/现金fallback，单Attempt24HTTP/2400秒、HTTP300秒、Repair3/单批Regenerate2；历史R07–R11不重派，UNKNOWN只对账。

原件离线重放通过：R11十批75题、13目标，原请求1136224→新892500 bytes，完整原payload可逆恢复严格相等、输出Tool Schema不变、1MiB不放宽。新表示`planning-input-context-dedup@2`、Journal/Checkpoint@18，软件54PASS/0FAIL（46.96秒），60封顶/UNKNOWN预检PASS，源文件快照和派生实验SHA归同目录。正式实现与版本说明见[Planning §8.34](../tasks/planning-creative-authority-implementation-plan-2026-10-15.md)。

全新R12已启动，独立证据`~/.local/share/easel/creator-task-evidence/2026-10-15-planning-m31-controlled-loop-live-r12/`，source `ec9c93cb60522973e0c3d82124a4876c29a9fadff7be9395ce2230cb50101559`；当前真实结果待收齐，尚不能宣称Planning全链PASS。本段替代下方旧停止NEXT的调度，保留全部历史失败和消耗。

## 2026-10-15｜最终Closure：R11真实受控恢复成功，全B回执齐；Repair请求容量阻断，累计29/30后预算不足停点

**整体 `RESULT=BLOCKED; DRIFT=NO_DRIFT; REAL_PLANNING=NOT_PASS; TRANSITION=ESCALATE（下一真实完整Attempt需新增累计预算决定）`。** 本轮不因普通错误停止：已完成R07/R08对账、隔离设施原生回放、R09真实失败根因修复及52PASS、R10/R11新独立真实复验。当前停止同时存在两个事实：R11的软件请求容量阻断未修；原Attempt Budget已closed，而本轮30累计额度只余1次，不足以开始一个可完成的全新完整Attempt。没有将余1次用于无完成可能的单阶段调用，没有重新打开任何原Budget。本轮整体未完成，绝不把软件修复或全B回执记为完整Planning PASS。

**R11原件：**`~/.local/share/easel/creator-task-evidence/2026-10-15-planning-m31-controlled-loop-live-r11/`；Creation `cr_aacb9ac985d34ce98bb6ca6304294255`，Attempt `fa_1c32923105e0cfd2fb23f1e35dc19044`；新source `2295814d932766e50aeeee0fcec19a676bef0d1f2b8e0a558e1b559c0c633a4b`，当前全部冻结文件SHA复核匹配。15/15真实HTTP均RESPONSE_COMPLETE，983756输入+51062输出=1034818 tokens；原生15项Run/Session/Schema/Terminal与Provider参数SHA全部只读复核，所有Run released、无Pending/HTTP UNKNOWN。旧失败记录和原始Capture不改，Budget已closed，within_bounds=true，Supply0/禁止阶段0。

**真实恢复事实：**A-selection PASS；A-details-000原操作发生stop+0tool，正式native拒绝SHA `cc20f3a292a1187fd9db843b67557bc971d3eb610de3e1bf5cbb8009da9bd322`，确认error/terminal/released后由唯一Owner使用新repair-000恢复。有效回执SHA `6cf112b3b75de8217a4a93578830080abf144ee526011388443b6dedaa8463f0`，原失败保留且未重派，stage有效身份固定；后续A-details-001/002 PASS。共享Repair实际1/3、该批Regenerate1/2；A-selection及已通过批次未重新生成。此只证明该真实恢复路径生效，不等同原/新回执已完成全链冷验证。

**B及首个最终阻断：**10批共75题（0000–0074）原始回执齐全；B-005有related_needs类型错误，B-007有related_needs/required_kinds类型错误，另有字面quote局部错误；模型ACCEPT不代表严格合同有效。现有跨批目标编译识别13个局部修复目标，已通过修复后的局部定义合并，但在新Repair占额/派发前，正式`review.checked_message`拒绝 **1,136,224 bytes > 1,048,576 bytes**（超87,648），错误`Complete semantic context exceeds request capacity; no clipping`。无新增修复HTTP，没有自动截断或扩大请求上限，B正式NOT_PASS；Truth/D2正式Proof/SEMANTIC_CHECKPOINT/正式冷加载/PLANNING_ACCEPTED均未到达。

**精确离线诊断：**`2026-10-15-planning-takeover-audit-r01/audit_final.py`先逆还原现行Question共享候选引用，再逐批重建与实际发送完全一致的10批Tool Schema、绑定原生回执SHA，沿真实Decoder/目标聚合/patch_schema/RepairEvidenceProjection/repair_message重放容量错误，保留原guard。未派发请求的离线重建SHA `eef20b1b34f13f3fe840c2e121d7de5b219046ffb672f1a380a6061dddca8fce`。review_context=866441字节、evidence_choices_by_target=212811字节；四个冻结批上下文分别重复同一candidate_bindings（17830字节）、evidence（20984）、source_catalog（43059），每类唯一值均1/4。仅这些重复副本就有245619字节可研究无损去重空间；**尚未修改/验收该Request View候选，不以删除依赖或缩短Token宣称解决。** 必须保留完整原文、目标身份和可逆还原/指纹/冷恢复，不改变业务合同。

|本轮新增运行|真实HTTP|输入Token|输出Token|合计Token|共享Repair|最终结果|
|---|---:|---:|---:|---:|---:|---|
|R09|13|839668|49811|889479|0/3|跨批Schema定义冲突；已离线修复|
|R10|1|21420|2283|23703|0/3|BGM越界视觉Header，严格拒绝|
|R11|15|983756|51062|1034818|1/3|Repair正文超过1MiB，未派发|
|**累计**|**29/30**|**1844844**|**103156**|**1948000**|按Attempt独立保留|**真实完整Planning NOT_PASS**|

R07/R08既有12HTTP/472226 tokens另列，不重新计入本轮新增30授权；两部分合计41HTTP/2420226 tokens。R01–R06既有历史预算不恢复也不并入新额度。全部费用按现有M Plan订阅权益执行，无充值/现金fallback；实际现金结算UNKNOWN，未记零。共享`task-http.json`以INSUFFICIENT_REMAINING_FOR_NEW_FULL_ATTEMPT关闭，保留29条不可退款占额和未用1次，不通过新Attempt重置。

**软件与未完成项：**当前已验证Loop/B身份/共享Repair/D2Owner/RepairEvidence 52PASS/0FAIL（46.71秒），R09真实9批16目标合同等价回放通过，R11真实no-tool新Operation恢复通过；源码只新增必要的跨批定义冲突修复和一项专门边界测试，没有改模型提示词、Material/声音/业务Schema、职责或架构。未宣称模型稳定、正式Web E2E/U4/Release资格。原生/HTTP/费用对账见`audit.json`、`final-audit.json`、`software-verification.json`、原各Attempt结果与Budget；本轮无素材/Build/Web/服务部署/commit/push/新Agent。

**NEXT_SINGLE_ACTION=用户明确补充足以完成新合法Attempt的累计HTTP/既有套餐额度边界；之后沿现有Task先修复Repair输入的可逆重复上下文表示并做真实原件离线等价回放，再以全新Attempt实调。不得重开R07–R11 Budget、沿原Operation重派、提高1MiB上限或删除语义义务。**

## 2026-10-15｜R10模型越界Header拒绝；同软件新R11复验中

R10独立证据目录 `~/.local/share/easel/creator-task-evidence/2026-10-15-planning-m31-controlled-loop-live-r10/`，Creation `cr_f1138c6e91c34c9f9351ab7171335718`，Manifest SHA `1eb505ab29dcb5e405aff77c6dd2f7526f02393ad62f9ac1bae68eecc81bf4f9`。真实HTTP **1/1 RESPONSE_COMPLETE**，21,420输入+2,283输出=23,703 tokens；Pending=false、within_bounds=true、Budget已closed，现金UNKNOWN。A-selection原raw SHA `2360d07307e8f4db31241509070a0105b423f4418f8fbc2b99020eebbdc7acd1`在needs[7]失败anyOf：该Need是BGM，却包含仅image/video允许的header_claim；实际严格Schema的bgm分支additionalProperties=false准确拒绝。不是Repair定义冲突复发，不修改提示词/代码、不删除模型Claim或扩大声音职责，Repair0/3，后续A-details/B/Truth/Proof未到达，REAL_PLANNING=NOT_PASS。

原操作确证结束，模型错误属于当前A-selection不可恢复范围，按最新持续授权使用全新R11独立Attempt复验（软件与R10完全相同）。当前累计14/30 HTTP、913182 tokens，剩16；R11目录 `~/.local/share/easel/creator-task-evidence/2026-10-15-planning-m31-controlled-loop-live-r11/`，source `2295814d932766e50aeeee0fcec19a676bef0d1f2b8e0a558e1b559c0c633a4b`。共享额度不重置，仍仅现有套餐/no现金fallback，等待R11完整结果。

## 2026-10-15｜R09真实全B到达：跨批局部Repair定义冲突；定点修复后R10复验中

R09证据：`~/.local/share/easel/creator-task-evidence/2026-10-15-planning-m31-controlled-loop-live-r09/`，Creation `cr_788996efb1c14f9b8a8c3b238ff88ec5`，Manifest SHA `b3ddebb2126bc030206a4ceb3fdecf9ad21232f2367ca593579f42f43b846d5e`，source `53a0a630030c83e7032a4812153271d6595e3db7688adcc7d396f5cd99f1c6fe`。真实HTTP **13/13 RESPONSE_COMPLETE**，839,668输入 +49,811输出 = **889,479 tokens**，原Run均已结束释放、Pending=false、within_bounds=true，原Budget已closed BATCH_FAILED；现金UNKNOWN。A-selection及3个A-details全部通过，9批初始B回执（question-0000–0070）全量取得；共享Repair **0/3**，在派发Repair前编译失败 `Conflicting patch definitions`，Truth/D2正式Proof/Cold未到达，**REAL_PLANNING=NOT_PASS**。

**多因果环节：**B-002有额外字段，B-005及其他题有quote/来源局部问题；B-003 question-0030对A额外“实拍/禁止跳切”给出合法director_replan_needed挑战。全部失败原文保留，未强制ACCEPT。Owner合并16个合法局部Repair目标时，独立B批的同名`Support/Support_001`定义不同，原全局合并代码错误拒绝，因此当前阻断为确定性软件缺陷，不能归因token长度或模型遗漏。

**原件离线复现与修复：**`2026-10-15-planning-takeover-audit-r01/replay_r09.py`从实际9批HTTP请求重建Schema，逐批与原发送工具Schema一致，并校验native raw SHA，沿真实Decoder→局部错误目标→冻结跨批目标→patch_schema复现冲突（16目标）。仅修改`planning_candidate_review.patch_schema`：只在局部定义名称冲突时重命名当前目标的完整局部定义与引用闭包，保留不冲突旧Schema；不改答案、来源/角色/quote准入或Repair额度。修后16目标逐一与独立编译合同完全等价，RepairEvidenceProjection成功构造；新增一项跨目标正反合同测试，定向Loop/B身份/共享Repair/D2Owner/RepairEvidence **52PASS/0FAIL（46.71秒）**，git diff --check PASS。开发中新增的额外集成fixture只有单B批且断言无效，已撤回该冗余测试/辅助扩展；失败及原因保留在software-verification.json，未有第二次生产修复。当前原生Owner/模型提示词不变，无架构改动。

**授权连续执行：**本轮新Attempt已用13/30、剩17，原R07/R08另列12不重计。R10使用全新Creation/Attempt/Run与独立目录 `~/.local/share/easel/creator-task-evidence/2026-10-15-planning-m31-controlled-loop-live-r10/`，新source `784808a21904dab774142f29c5d1bb1b463c4d63fb0e69f406023b866523b8e3`，单Attempt24和共享总预算剩17双上限（实际取较小者）、HTTP300秒、Attempt2400秒、Repair3/单批Regenerate2，仅现有M Plan套餐、不充值/无现金fallback。沿相同已离线验收的隔离Adapter、原Gateway/Proxy和唯一Owner执行，不恢复R09、不另建Planning主链；R10结果尚待收齐，不能提前报PASS。

## 2026-10-15｜Planning 接管对账与持续调试授权（R07/R08 原件已核验，后续执行中）

本轮唯一目标为一个全新 Attempt 首次真实完成 A-selection→全部 A-details→B→Truth→D2 Proof→正式冷验证与 PLANNING_ACCEPTED。用户最新指令覆盖历史“首错即停／下一轮另行授权”的调度限制，禁止新建 Agent、第二执行器、素材/Build/Web/部署/Git 操作。用户随后明确批准 **本轮新增 Attempt 跨轮累计30 HTTP**，仅使用现有 MiniMax M Plan 套餐，不充值、不转现金，套餐不足即停；单 Attempt 沿用24 HTTP/2400秒、单HTTP300秒、共享Repair3/单批Regenerate2。共享持久账本 `~/.local/share/easel/creator-task-evidence/2026-10-15-planning-takeover-audit-r01/task-http.json`；历史R07/R08的12次单列，不重开旧Budget，后续不以新Attempt重置累计额度。

**只读对账证据**：同目录 `audit.py/audit.json`；逐次实际请求文件SHA、Provider-entry参数SHA、OpenClaw native Capture/Terminal Receipt及Run/Session逐一核实。R07/R08原Job均completed（原Exit0不代表业务PASS），所有12次HTTP均RESPONSE_COMPLETE、原Run已released、无HTTP UNKNOWN/Pending，Budget均closed；没有发现更晚真实运行，另一接管指令审查聊天idle，无并行Owner的执行证据。

|运行|Attempt|实际HTTP|Token（输入/输出/合计）|共享Repair|业务终态|
|---|---|---|---|---|---|
|R07|`fa_8e362c48c16f099059c7383288a0e905`|8/8|338999/24626/363625|0/3|FAIL，A三批完成，B-003嵌套表示拒绝，Truth/Proof未到达|
|R08|`fa_25f88f156910904ce2dd0a9afe2f656a`|4/4|94340/14261/108601|1/3|FAIL，A-details-001来源enum拒绝→repair-000无工具终态；Truth/Proof未到达|

两轮总472226 Token；实际现金结算UNKNOWN，不能记零。R07所有四个B批次冻结问题集合、实际发送集合、原始答案ID集合逐一一致（0000–0031），**不存在已证实的缺题或聚合遗漏**：B-003原始`answers[0].answers.item`及support.item额外包装导致长度判定失败；只移除包装后原严格Schema合法，B-001/002另有独立局部字段错误，均保留。R07后已有lossless规范化与冷恢复修正，当前B身份@2、Journal/Checkpoint@17；R08 Manifest的全部冻结文件与接管源码一致。旧Loop V1 12文件manifest仍有9文件匹配，semantic_boundary_run/test_creation_preparation/test_planning_stage_loop三文件变化归上述规范化接线与测试；planning_wire不在旧12文件内但相对R07也变化，不继承旧53PASS资格。

R08原生no-tool只读正式读取为CONFIRMED_TERMINAL_NO_TOOL，原件SHA `d1d29f08fe84bb844de474db4fa589e0c51395510b1a22beb7b3443d28b1e452`。原隔离HTTP设施在SSE stop无参数时关闭Budget，旧drain在native error released时直接FAIL，未给现有Owner恢复机会；这属于设施与Loop调度不匹配，非HTTP UNKNOWN。原失败不修改、不恢复；新Attempt先验证隔离设施只在确证native终态与Owner共享占额后可继续。当前源码定向离线51PASS/0FAIL（47.35秒），涵盖Loop/B身份/共享Repair/D2 Owner/RepairEvidence；真实全链仍NOT_PASS。后续结果追加于本节之前，不把本接管段落当作最终Closure。

## 2026-10-15｜Planning Controlled Loop V1 软件 Closure（非真实MiniMax新调试）

§8.29–8.30实施于唯一Planning Owner：确认原生terminal no-tool或已完整工具回复仅非法creative_goal_ref时允许新Operation的 A-details整批重生；所有FIELD/B/SEMANTIC/REGENERATE共3次、单批至多2次；原R05/R06失败和旧@15不迁移，UNKNOWN禁止重派，原/新回复、D1/B/D2冷恢复严验。最终离线job `wc_job_hZycbaWZ6t7qBxRC` **53 PASS/0 FAIL**；R05历史原生拒绝观察只读PASS（stop、0 toolcall、原Run/Session绑定、拒绝SHA `0dfd228fe8150a9440121fbbb7d0ff2715028ca7eac0d5b56146016bacbf6c2a`）；12源码测试当前/快照12/12 SHA核对，manifest `1bd11137372204ee202ce84adb12aa228e6170dfd00426ef284cf0c740a1378c`，快照 `~/.local/share/easel/creator-task-evidence/2026-10-15-planning-controlled-loop-v1-software-r01/`，版本 `@16`、HEAD `d82bb60b`。旧历史原件/真实HTTP Budget不变，**没有新真实MiniMax、Git commit、服务部署**。软件`RESULT=COMPLETE`，尚未真实跑通Planning/Truth/Proof。用户随后明确授权新独立模型调试，未来运行单独追加证据，绝不把历史R05/R06失败改写为PASS。


## 2026-10-15｜R06 授权续接：无外网预检 PASS；新 Operation 返回真实 Tool Arguments，但来源枚举错误，1次后停止

**最终分类 `BLOCKED_OR_UNKNOWN`；具体为确认终结后的严格 Schema 拒绝，`HTTP_UNKNOWN=false`。** 本次用户明确授权修正同一 R06 隔离脚本证据序列化，保留现有安全检查，先无网络预检，再沿原授权最多2次新真实MiniMax操作，成功即停；可修复脚本问题不重复索权。修正仅在 `~/.local/share/easel/creator-task-evidence/planning-loop-recovery-eval-r06/` 内；旧预检脚本另存 `run.preflight-initial.py`，原 `start/result/r05-audit` 等故障原件保留，当前证据归 `offline-preflight/`、`execution/` 和根级 `final-receipt.json`，不是 R07/R08、第二 Owner 或生产 Attempt 恢复。修正后的 `run.py` SHA256 `61e873aabaf40ecbf5851582cefcff038acf4d537a834a33f16e919990b5024a`，原Gateway/Proxy/Budget未改。

**无外网预检：PASS。** 证据指纹改用 `{path,sha256}` 列表，继续调用原 `SecretRedactor.contains_secret`，不移除或放宽规则；按原规则验证敏感键拒绝和公开路径列表可安全保存。Python socket 与隔离 Node 网络规则限制 loopback，未加载真实模型Key；通过**同一脚本、原 EvalGateway/Proxy/HTTP Budget、当前安装OpenClaw、原 A-details-001严格 Schema**，合成外部边界先返回 `stop + 0 tool_calls` 并确认原生error/已终结，再以不同新Operation取得合成Tool Arguments、严格Schema PASS；同时验证缺失 `unresolved` 与多余 Slot 拒绝。合成数据只证明验收设施与格式可用，真实MiniMax请求/Token均0，不冒充业务语义/E2E。预检和live绑定同一脚本SHA。每次原HTTP Budget上限1，R06共享预占账本上限2操作、总Repair最多3；无参终态关闭原子Budget后仅可能进入另一个预分配的新操作，不重开closed Budget。

**R05 终态再次核实：**原第三次HTTP200/SSE DONE、`stop + 0 tool_calls`、`STRUCTURED_TERMINAL_REJECTED`、error/released/timestamped terminal receipt、无Pending，明确不是HTTP UNKNOWN。原 frozen A-details-001 message SHA `04dc7a5a3470296ee3db399d6a143f0e042af2492f4492200b0ff5d501c3d17c`、Schema SHA `29f3474b5fa76e45bc6832904029a1bf39e01ed6ca7fd81b0fef2177ffb3232c` 精确保持。已成功 A-selection、A-details-000 不重做、不改写；保留原 SourceSelection/Creator/Director/Creative Mode、Attempt引用和完整冻结输入。R05正式Repair仍0/3，原Attempt和已关闭Budget未恢复。

| 本次真实操作 | 实际结果 |
|---|---|
| Operation / Run ID | `r06-4d6424f95aeb467dbf117dac94e1ff86`，全新且与R05不同 |
| Session ID | `r06-34b30ee97b8f41e8a1ac89038a9859e6` |
| 模型与认证 | `MiniMax-M3.1-Flash-Preview` / adaptive / medium / 原M Plan订阅认证来源，未改生产配置 |
| HTTP / SSE / 原生终态 | 200 / SSE DONE / provider `tool_calls`；原生 `status=ok`、有startedAt/endedAt和匹配terminalReceipt；Pending=false |
| 实际 Tool Arguments | 1条 `submit_semantic_plan`，8,299字节；原文 `execution/operation-001/tool-arguments.raw.json` |
| Raw SHA256 | `33235da4b009da19355de44a79c858e634c7decae0a012d608471268ecb83a06`；Provider-entry、Native capture和落盘字节一致 |
| 字段完整性 | `slots`恰为 `slot_004/005/006`，根级 `unresolved`实际存在；未由程序补造 |
| 严格 Schema | **FAIL，2个enum错误**：`slots.slot_004.conditions[0/1].claim.creative_goal_ref` 都为非法 `src_7fa913d7de0bf1af55e`，不在原冻结允许集合 |
| Token用量 | prompt **23,479** + completion **3,418** = **26,897** |
| 预算 | 真实HTTP **1/2**，同Operation重试0；隔离恢复预占 **1/3**，原R05正式Repair仍0/3；真实现金结算 **UNKNOWN** |
| 第二次操作 | **未创建、未派发**：首次已返回Tool Arguments，不符合仅 `stop + 0 tool_calls` 才能派发第二次的条件 |

**判定与边界：**新独立模型操作确实将原无工具调用阻塞推进为一份有完整工具参数的结果，但其来源引用不合法，故**不是 `LOOP_RECOVERY_CONFIRMED`**。也未执行“两次合法独立操作均失败”，不能写 `LOOP_RECOVERY_FAILED`；按允许分类记 `BLOCKED_OR_UNKNOWN`，精确原因 `CONFIRMED_TERMINAL_STRICT_SCHEMA_REJECTED_SECOND_CALL_NOT_AUTHORIZED`，不得误报HTTP UNKNOWN。没有替模型选择正确来源、改原reply、补字段、放宽enum、进入FIELD_REPAIR或启动第二次模型调用。原生ok只证明工具候选安全终结，不代表Easel严格合同/语义验收通过。代理在候选已完整读取后的loopback连接关闭出现一次 `ConnectionResetError` 日志；最终HTTP完整观测、Native原文和SHA均齐全，因此不据此重派或抹成UNKNOWN。

**架构评估更新（只建议、不实施）：**下方首次R06记录的7项既有Owner内STAGE_REGENERATE设计仍适用，但真实证据目前只支持“新Operation可重新取得工具参数”，**不支持整阶段恢复一定合法或生产Loop已具备**。保留受控STAGE_REGENERATE作为候选；它必须与FIELD_REPAIR/SEMANTIC_REPAIR共享同Attempt最多3次，确认终结无候选与HTTP_UNKNOWN严格分离，绑定原Schema/SourceSelection/Director/Attempt及批次，留旧失败引用/新Run/Repair Ledger/Checkpoint/Cold Verify，保留成功批次，按新候选身份使不适用B ACCEPT/DecisionProof失效。正式改造仍只考虑既有 `semantic_boundary_run`、`planning_capture`、`openclaw_delivery`、`output_admission`、`planning_repair_evidence`、`planning_candidate_review` 与 `planning_d2_typed_review` 的相关边界和已有集成测试；安装OpenClaw及Tool Schema不因本例修改。非法来源必须拒绝，不增加程序猜测或修复权限。

**冷证据验证：PASS。** 独立只读 `verify_receipt.py` 从落盘raw重跑原Schema，精确复现上述2个错误；重算request/schema/runner/raw与三方SHA，核对Run/Session/预算/终态，确认第二操作不存在。真实运行前后 **R05全部2,802文件SHA一致、P0-A/B/C 23/23冻结一致**。这只是失败证据的冷核验，不是生产Owner的Cold Verify/完整Planning PASS。没有生产代码变更、凭证更换、素材/TTS/Hypit/Web制作、部署或Git commit/push。根级 `final-evidence-manifest.json` 保存本轮具名证据SHA；原故障与真实失败均保留。

`RESULT=BLOCKED（隔离恢复验收未达合法结果，执行已按限制结束）; EXPERIMENT=BLOCKED_OR_UNKNOWN; HTTP_UNKNOWN=false; DRIFT=NO_DRIFT; EVIDENCE=无外网预检PASS、1次真实HTTP终结/实际Tool Arguments、原严格Schema两处来源枚举拒绝、冷证据核验PASS; LESSON=新Operation能取得Tool Arguments与合法阶段恢复必须分别验收；安全证据索引用path/sha列表并保留原检查; NEXT_SINGLE_ACTION=只读评审R06非法creative_goal_ref原文与现有Owner恢复边界，形成最小建议；本轮立即停止，不再调用、不改生产Owner、不进入U4; TRANSITION=HOLD`。

## 2026-10-15｜R06 MiniMax Agent Loop 恢复验证：预检记录格式阻断，0 次真实请求

**`BLOCKED_OR_UNKNOWN`，未取得恢复实验结果。** 用户明确授权本轮仅在永久隔离 R06 中，以最多 2 次新 HTTP / 同 Operation 0 重试 / 全局最多 3 次共享 Repair，重生成 R05 失败的 `A-details-001`，成功即停；不得恢复 R05、改生产 Owner、启动 R07/R08 或 U4。本轮创建 `~/.local/share/easel/creator-task-evidence/planning-loop-recovery-eval-r06/`，保留 `run.py`、`start.json`、`frozen-input.json`、`r05-audit.json`、`result.json`、`evidence-manifest.json` 及纯本地收尾脚本。**执行在模型派发前停止，没有新 Operation ID、Gateway/Proxy 启动或新 HTTP Budget 占额。** 这是验收脚本预检失败，不能解释为 MiniMax Loop 失败或成功。

**第一阶段只读结论：**已审计 `semantic_boundary_run.py`、`planning_capture.py`、`planning_candidate_review.py`、`output_admission.py`、`openclaw_delivery.py`、已安装 `dist/easel-structured-result.mjs` 和 R05 原 `EvalGateway/EvalProviderProxy/EvalHttpBudget`。R05 第三次 `HTTP 200 / RESPONSE_COMPLETE / SSE_DONE / provider_finish=stop / argument_delta_bytes=0 / diagnostic_unknown=false`；原生拒绝记录 `STRUCTURED_TERMINAL_REJECTED / toolCallCount=0`，原 Run `easel-916228bb28184cc2b5a15bfac0b0d8c8` 的 `status=error / runtime_release=released / terminal_receipt` 身份一致，`pending_original_run=false`。**属于确认终结的无工具调用错误，不是 HTTP UNKNOWN。** 原原生 reservation 文件仍是 `RESERVED` 身份留存，不能单看该字段推断运行仍活跃；终态须结合拒绝记录、timestamped terminal、释放记录与 HTTP/SSE。原预算 `closed / ENTRY_CAPTURE_UNAVAILABLE` 保持，原真实 Repair 为 0/3。

现有 `capture → admitted_details` 需要先取得真实候选；白名单补答仅允许其余 Slot/Claim 严格合法而根级缺 `unresolved`，后续候选/B/语义 Repair 也不覆盖无候选终态；`openclaw_delivery` 的 Planning 强制 `retry_failed=False`。所以**当前生产 Owner 尚无这类 STAGE_REGENERATE Loop**。独立实验在新操作、新预算、冻结输入与严格 Schema 下原则上可行，但本轮没有真实执行来证明恢复。R05 原始 user message 已从保存请求去除 Runtime 包装后精确还原，SHA `04dc7a5a3470296ee3db399d6a143f0e042af2492f4492200b0ff5d501c3d17c`，与 Journal 完全一致；Schema SHA `29f3474b5fa76e45bc6832904029a1bf39e01ed6ca7fd81b0fef2177ffb3232c`，固定 `slot_004/005/006` 与根级 `unresolved`，SourceSelection/Director/Creative Mode 上下文保留。已成功 A-selection/A-details-000 的 reply SHA 重算匹配，23/23 冻结源码匹配；没有重判或恢复旧 Attempt。

**实际阻断与止损：**新验收脚本的证据保存函数调用现有 `SecretRedactor.contains_secret`。第一次启动元数据使用 `authorization` 键触发安全规则，改为 `permission` 后预检前进；随后把 R05 全文件路径作为 `originals` 字典键，公共 OpenClaw UI 缓存中含 `secrets-page` 的 12 个文件名触发 parent-key 规则，`r05-audit` 写入前 `AssertionError`。这是 Main 编写的验收记录格式错误，不是已安装 Runtime 或 MiniMax 故障，未发现 Secret 泄露。按用户“环境障碍/无法保存回执立即停止”停止后续执行；未禁用安全规则、未重跑主脚本。收尾仅将公开路径/SHA 使用列表行记录，经相同安全检查保存审计和故障事实，**不据此恢复调用**。未生成模型回执，不能把本地安全校验失败冒充模型输出失败。全树起始指纹未成功落盘，故不宣称全树前后 SHA 验收；关键 R05 请求、成功回复与冻结身份已单独核验。

| 验收项 | 实际结果 |
|---|---|
| 新真实 MiniMax HTTP | **0 / 2**，同 Operation 重试 0 |
| 新 Operation 与终态 | **无新 Operation**；仅本地 preflight `AssertionError` |
| Tool Arguments / 严格 Schema | 未取得 / 未执行 |
| 本轮 Token / 新请求预算 | prompt 0、completion 0、total 0；HTTP 0/2；共享恢复 0/3 |
| 现金 | 无新请求；历史 R05 结算 UNKNOWN 保持，不清零 |
| A-details-001 恢复 | **未证明**；R05 原失败保留 |
| 生产 Easel Loop | **未支持、未修改、未验证** |

**条件性架构建议（未获真实成功证据，不实施）：**建议保留 `STAGE_REGENERATE` 为现有唯一 Planning Owner 的候选恢复动作，正式批准前先取得真实隔离证据并按现行规则作必要架构复核。

1. **共享预算**：复用 `semantic_boundary_run.reserve_repair_slot`，在外部提交前预占同 Attempt `repair-000..002`；`FIELD_REPAIR / SEMANTIC_REPAIR / STAGE_REGENERATE` 合计最多 3，不另开阶段额度。新 regeneration 必须包含原失败 Operation 和序号，避免现有同 stage 去重逻辑将两次新操作混为一次；UNKNOWN 已占额度不退还。
2. **终态分类**：`openclaw_delivery`、`planning_capture` 保存明确传输/原生证据；`HTTP_UNKNOWN`、缺 timestamped terminal/receipt、Pending、429、截断或 Schema 身份异常均停止只对账。仅 HTTP/SSE 确认终结、原生终结且 released、精确 `stop + 0 tool_calls` 可成为 `STRUCTURED_NO_TOOL_CALL` 候选。`output_admission` 继续只验证取得的候选，不以空对象补造候选。
3. **新身份与失败引用**：原 Call/Capture/HTTP Budget 永不重开；新 Operation/Run/Session、0 自动重试，在现有 ledger 中引用旧拒绝、HTTP观测、终态 SHA 及 Attempt/stage。原 Budget 实现遇无工具参数会关闭；将来需明确同一预算治理如何管理新操作的预分配份额，不能通过重开 closed Budget 或无限新预算扩额。
4. **批次与冻结依赖**：仅重做失败 `A-details-001`；A-selection 与 A-details-000 的 ACCEPT/raw SHA 不变。绑定 Attempt、SourceSelection、原 message/Schema/codec、Director/Creator/Creative Mode、Canonical 和批次精确 slots；任一指纹变化拒绝恢复，不重新选择 Need 或改其他批次。
5. **证据与冷恢复**：扩展现有 `planning_capture`、Owner Journal/Checkpoint/`verify`、`planning_repair_evidence`，保留原失败与新 raw/tool SHA、预占/派发/终态/准入链。Cold Verify 从两份原件重建分类、额度及严格 Schema/Claim/身份校验，不能仅信 PASS 标志；旧无结果记录不变 ACCEPT。
6. **B/Proof 依赖**：`planning_candidate_review` 与 `planning_d2_typed_review` 只接受新 A candidate/Claim SHA 对应的 Review/DecisionProof。任何旧 B ACCEPT、聚合结果、D2 Proof 不适用于新 candidate 时必须失效并重审；不从前一 lineage 继承准入。受影响下游仅通过既有消费者重新验证。
7. **正式实施模块与验证**：以上既有 Owner、capture/delivery、admission、repair evidence、candidate review、D2 typed review/checkpoint 冷验证及现有高价值 integration 测试；`planning_structured` 只需绑定原严格请求身份，不改变 Tool Schema；安装 OpenClaw 已正确拒绝，不据本次证据修改它。不新增 Owner/生产主链，软件实现须独立授权并覆盖 UNKNOWN 禁重派、额度共享、成功批次保持、Proof 失效和冷恢复。

`RESULT=BLOCKED; EXPERIMENT=BLOCKED_OR_UNKNOWN; DRIFT=NO_DRIFT; EVIDENCE=R05确认终结/原输入与Schema身份匹配/23文件冻结匹配，R06真实调用0，恢复与共享Repair实际效果未验证; LESSON=证据索引不要把含敏感词的公开路径直接作为安全扫描对象键，应使用经相同规则检查的path/sha列表; TRANSITION=HOLD`。

**NEXT_SINGLE_ACTION=审阅本次预检故障，另行明确允许修正 R06 隔离验收脚本并完成无网络预检后，再决定是否执行剩余至多2次的真实调用；本轮立即停止，不自动重启 R06，不建 R07/R08，不修改生产 Owner，不进入 U4。**

## 2026-10-15｜P0-D 真实 MiniMax M3.1 首次验收 R05：A-selection / A-details-000 PASS，A-details-001 无结构化工具参数，按首错停止

**本轮新独立真实调用已经完成，P0-D FULL REAL PLANNING NOT_PASS。** 用户本轮明确授权 P0-D 在 P0-A/B/C **23文件软件冻结**之上实际请求 MiniMax。执行前确认软件 manifest SHA256 `4ea6df0db39df39e0fe5579602ce833024f02900d728e64ebb0e1a52575d237e`，冻结源 **23/23** 字节一致；历史 R01–R04 全部已终结、其旧预算关闭、没有重新派发。沿用历史实际成功的 R02 `run.py`、原 `gateway_harness.py`、`PlanningEvalBoundary/isolated_process/drain_checkpoints`、持久化 `EvalGateway + EvalProviderProxy`，创建**唯一新的隔离证据目录** `~/.local/share/easel/creator-task-evidence/2026-10-15-planning-m31-actual-owner-eval-r05/`，Manifest SHA256 `ddbb91ac1c22713cf85a1f9200bd5ac65bb9e37ad5ac9fa3e136aa1939e82586`；286/286 源码/Runner指纹完成时仍一致、OpenClaw Runtime 指纹通过。MiniMax `MiniMax-M3.1-Flash-Preview`，adaptive/medium，使用已配置 M Plan 订阅凭证类别，**单样本、HTTP硬上限16、共享Repair硬上限3、自动重试0、最大2400秒**；离线原 Gateway Preflight 通过（不发生付费请求）。本次只调用文本Planning，不调用素材、TTS、Hypit、Web/Build/部署。

**真实 R05 结果：**代理 HTTP **3 RESERVED / 3 RESPONSE_COMPLETE / HTTP 200**，但必须严格区分**HTTP 流完整结束**与**工具参数完整有效**。第一次 A-selection：provider `finish=tool_calls`、argument_stream `COMPLETE`，原模型回复 SHA256 `daa18f51c080510a7000a49ab1de0a98bfee90044628325625a1b2c556369206`，模型来源/D1选择身份 PASS。第二次 A-details-000：`finish=tool_calls`、argument_stream `COMPLETE`，原回复 SHA256 `f0ff796c17b1183b72486b9de201c8f95655f600fa52369f990f027f7d62448a`，4 个视觉 Slot、合法 Claim 及显式 `unresolved` 均通过原 Strict Wire/Admission，未消耗 Repair。第三次 A-details-001：请求已明确指定 `submit_semantic_plan` 工具（`tool_choice: {"type":"function","function":{"name":"submit_semantic_plan"}}`），MiniMax HTTP 200/SSE DONE，但原代理观测 `provider_finish=stop`、`argument_delta_bytes=0`、`reasoning_delta_bytes=4919`、`argument_stream_state=INCOMPLETE`、`observation_reasons=[ARGUMENT_STREAM_MISSING,TOOL_FINISH_OTHER]`，**没有任何 tool_calls 或可用于 Schema 校验的工具参数**。原 native Call 显示 status=error、runtime_release=released、terminal_receipt存在；本地 Capture `A-details-001` 为 `TRANSPORT_FAILED`、无 `reply_sha256`，不能伪造原回复/Schema错误、不能申请 `unresolved` 局部补答。**严格在第一不可恢复结构化输出错误处停止**；未触发 B Review、Truth、Plan、D2 Proof 或 Cold Verify 的真实 MiniMax 整链。

**本次账本与保全：**总 Token 为 `prompt=70,167`、`completion=10,030`、`total=80,197`；实际现金结算金额 UNKNOWN，不根据套餐用量推算。代理预算最终 **closed=true / close_reason=ENTRY_CAPTURE_UNAVAILABLE**，`within_bounds=false`、`pending_original_run=false`、无自动重试或新 R06；共享 `repair_count=0 / 3`，所以此运行**未验证真实 Repair 生效**。第一/第二次原始 reply SHA 与保存 Journal 字节匹配；第三次只有原 Proxy SSE 观测及 Native 终态证据，无虚构语义回复。R05 Manifest 286/286 一致，P0-A/B/C 23/23一致，源/历史R04原件无漂移；`production_modified=false`、无生产Git commit/push/部署。绝不将第三次的 `RESPONSE_COMPLETE` 解释为 `STRUCTURED_COMPLETE` 或把软件47PASS冒充真实全链PASS。

`RESULT=PARTIAL（已执行P0-D真实MiniMax并停在首个问题）; REAL_HTTP=3/3_STREAM_COMPLETED; A_SELECTION=PASS; A_DETAILS_000=PASS; A_DETAILS_001=BLOCKED_NO_TOOL_ARGS; SHARED_REPAIR=0_OF_3_NOT_EXERCISED; FULL_PLANNING=NOT_PASS; DRIFT=NO_DRIFT; TRANSITION=HOLD`。

**NEXT_SINGLE_ACTION=针对第三次请求在明确 tool_choice=function 时 provider_finish=stop 且缺失 tool_calls 的真实原始代理观测/Native 终态，做严格只读根因分析（模型真实输出与 M3.1 Gateway 工具调用/推理流兼容、无参回退策略），区分 Provider 与 Runtime；先讨论方案，不重开R05、不在本轮直接修复/扩容/另发M3.1。后续真实R06须另行授权并新建独立持久化身份。** U4继续BLOCKED，U5/U6未准入。


## 2026-10-15｜P0-A/B/C 软件受控恢复正式冻结（非真实 MiniMax 运行）

**只归档软件验收，不改变下方真实 R01–R04 失败事实。**原唯一 Planning Owner 新版本内完成严格 A-details 根字段准入、明确模型补答与全 Attempt 最多3次共享Repair；原回执、修复回执、Ledger、Journal/Checkpoint、D1/D2 Proof/Cold Verify 同版验收。最终定向Job `wc_job_NB1RcIUV85nITqQG` **47 PASS / 0 FAIL（81.82秒）**，AST与 `git diff --check` PASS；R04 保存的两个原回复 SHA 仍匹配且 HTTP Budget `closed/BATCH_FAILED`，没有新的模型 HTTP。指定23源码与测试文件只读快照目录 `~/.local/share/easel/creator-task-evidence/2026-10-15-planning-abc-software-freeze-r01/`，manifest SHA256 `4ea6df0db39df39e0fe5579602ce833024f02900d728e64ebb0e1a52575d237e`。当前 Git HEAD `d82bb60b`、其余 dirty 文件不在本冻结承诺范围，未提交/部署。**P0-D独立真实 MiniMax 尚未执行；R04 原失败不能当成模型已恢复。**唯一后续获得新授权后才可运行 P0-D，具体见[Planning §8.27](../tasks/planning-creative-authority-implementation-plan-2026-10-15.md)。

`RESULT=COMPLETE（仅软件P0-A/B/C）; DRIFT=NO_DRIFT; REAL_MINIMAX_P0_D=NOT_EXECUTED; TRANSITION=HOLD`


## 2026-10-15｜R04 真实 MiniMax M3.1：模态分批已实施，模型漏掉必填 `unresolved`，按用户指令首错停止

**用户授权和执行边界：**用户明确批准现有唯一 Owner 采取「按模态隔离 A-details 批次」，并要求修正后真实 MiniMax 验收、出现第一个错误即停止。原失败 R03 的 HTTPS 3/3、原 raw/SHA、Closed Budget 未修改或重派。当前 `StagedProposal.detail_batches(selection, modality_family=True)` 仅 New-Only D1 按保留原 ordinal 的视觉(image/video)和音频(BGM/SFX)家族切分，最大4槽/批，使用独立 Policy `planning-modality-family-detail-batches@1`；原 legacy 固定4槽批次仍支持但不会覆盖新身份。`BatchedVisualClaimCarrier` 仍沿原 SourceSelection src_→canonical、Claim SHA 与 D2 Proof/冷恢复，`BATCH_CLAIM_POLICY` 从 @3 到 @4。原 R03 真实 A-selection 原件只读验证分为 `[slot_000..003]视觉`、`[slot_004..006]视觉`、`[slot_007..010]音频`，总批次数仍3，源 Need 身份和固定顺序不变；模型 Prompt 按当前批次显式限制 audio Condition 不能带视觉 Claim。定向原 D1/D2/D4/冷恢复测试 **20 PASS/0 FAIL**，未重复运行全部历史191项目。

**唯一真实 R04：**采用历史已验证真实 MiniMax 的原 R02 `run.py/gateway_harness.py`、`PlanningEvalBoundary + drain_checkpoints`、持久化 EvalGateway+HTTPS Provider Proxy，不开临时一次性假环境。独立证据目录 `~/.local/share/easel/creator-task-evidence/2026-10-15-planning-m31-actual-owner-eval-r04`；本轮冻结 **277** 项源码/Runner指纹，Minimax `MiniMax-M3.1-Flash-Preview`、adaptive/medium、M Plan 订阅 Key 类型已核对，最大8 HTTP、0自动重试；离线原 Gateway预检 PASS（0 MiniMax）。真实执行 **2 HTTP RESERVED/2 RESPONSE_COMPLETE、0 pending、0重派**。A-selection 原始回复SHA256=`b255694ebe622a92e53812a8b25e157b5e9a4b880ed1839aaa951345a85a1367`，SourceSelection/D1头部通过；A-details-000 原始SHA256=`f71667a925366a9247d31c88227d6c27a54ca4cbfd512792f360066965db1dc6`，模型填写4个合法视觉槽，各条件有必要的visual Claim，但原回复 **根对象只有 `slots`，漏掉 Schema 的必填 `unresolved`**。实际 Provider Tool request `submit_semantic_plan` 参数根级 `required=['slots','unresolved']` 且 `additionalProperties=false`，原 Owner `wire_diagnostics` 唯一问题 `{'keyword':'required','path':[]}`，严格抛 `Planning v3合同无效：Complete Planning wire schema rejected`，用户要求下立即停，未发第三次请求、未进入后续音频 A-details/B/Truth/Plan/Proof，不能声称混合模态问题已由**真实音频回复**验证消失。

**证据与占额保护：**原始两个 reply 和本轮 HTTP/Agent/Journal 完整保存，SHA重算可核；当前 R04 Budget `closed=true`, `close_reason=BATCH_FAILED`, `pending_original_run=false`，禁止恢复失败 R04 或人工添加 `unresolved:[]`/删字段伪造合格回执。模型报告 prompt 46,473 + completion 9,416 = 55,889 tokens；真实现金结算仍 UNKNOWN，不能从 M Plan 余额推断。没有启动素材/配音/Hypit Build/Web制作，没有修改旧原件、提交、推送或部署；Git `easel-studio` HEAD `d82bb60b...` 原工作区dirty，不放行 U4/U5。

`RESULT=PARTIAL; MODALITY_FAMILY_SOFTWARE=PASS; R04_REAL_HTTP=PASS; A_SELECTION=PASS; A_DETAILS_000=FAIL_MISSING_REQUIRED_UNRESOLVED; FULL_PLANNING_REAL=NOT_PASS; DRIFT=NO_DRIFT; TRANSITION=HOLD`。
**NEXT_SINGLE_ACTION=只对这次模型 A-details 根对象漏 `unresolved` 作根因判断（模型给出的Tool Schema/完整性指令、输出容量/截断、生产请求转换或本地 strict handling），比较旧 R03 同类原件；不得直接写 `unresolved=[]` 默认、放宽闭合 Schema 或复用旧失败预算。提出安全修正并由用户另行批准新一轮真实运行；本次按「出现问题立即停止」不继续实现或派发。**

## 2026-10-15｜R03 原 R02 真实 MiniMax Env：A-details src_* Codec 验证 PASS；混合批次 BGM 非法 Claim 阻断

**本轮唯一 Owner、真实环境：**按用户授权，在 `easel-studio` 上将 A-details 视觉 Claim 的模型 Wire 统一为冻结 SourceSelection `src_*`，`BatchedVisualClaimCarrier` 使用同一个 Codec 的 `allowed_scopes` 对每条 visual Claim 限模态枚举，原 raw/tool SHA 不改，译成 canonical `event-*/global` 后继续原 D1 Header/Condition/B Proof；SourceBridge identity、Source mapping SHA、batch schema SHA 均进入新 `BATCH_CLAIM_POLICY=planning-d1-batched-claim-boundary@3` 身份，由原唯一 Owner `run/verify` 调用同一 carrier，不新增状态机/模型 Agent/改 Material V1.3。此修正对上一 R02 真实保存的 A-details-000 **18/18 个 src_* ref 原值**完成校验/无损反向编码，并验证非法 src_* 拒绝、原 Journal 字节未变化；小范围定向回归 **20 PASS（33.16s）**，没有启动大规模重复软件矩阵。

**真实 R03：**复用旧 2026-10-14 R02 正式成功的 `run.py/gateway_harness.py`、`EvalGateway/EvalProviderProxy`、`PlanningEvalBoundary + drain_checkpoints` 及原生等候/对账，在新持久隔离证据目录 `~/.local/share/easel/creator-task-evidence/2026-10-15-planning-m31-actual-owner-eval-r03`，冻结当前代码/配置 **274** 文件指纹与 Runtime 11/11 身份，M3.1-Flash-Preview / adaptive / medium，M Plan 订阅凭证类型确认，最多8个 HTTP / **0 重试**。离线 Gateway preflight PASS（不调用真 MiniMax），随后唯一 `live`。**3 HTTP RESERVED / 3 RESPONSE_COMPLETE，全部保留原始回复，`pending_original_run=false`、`boundary_reached=false`、总 token = 71,358 prompt + 13,251 completion = 84,609；最终预算 closed=BATCH_FAILED、0 重派。** 原 A-selection 回复 SHA256=`4958370cad2bec547827cd865800fc06332bc0d87522c58432647587141ac0ae`；A-details-000 SHA256=`349d032129eadd5a344cd260b67f8e1edc78285c0c6f93444c62db1081eb5ea2`；A-details-001 SHA256=`d9959568066c09fccd49c75d44e701d4ab079bd483efc363bd39f830b77030fe`。全部原文 SHA 重算 MATCH，原 R01/R02 不修改。

**已证实：** A-selection **PASS**；A-details-000 **PASS，完整证明此前 18 个来源枚举错误的模型侧 Codec 已解除**。`A-details-001` 的 `slot_004`～`slot_006`（视觉）合法，但 `slot_007` 是 BGM：7 个 BGM Condition 都被真实模型输出了**非视觉的 `claim` 对象**。实际 miniMax Tool Schema 中该 BGM Condition 只有 `text/strength/responsibility/meaning`，明确 `additionalProperties=false`，并不含 `claim`；原 owner `wire_diagnostics` 对这 7 条报告 `additionalProperties`，fail-closed `Complete Planning wire schema rejected`。仅在内存临时移除这 7 处未知字段后原工具 Schema 错误数为 0，这只是归因验证，**绝不当成成功输出、不要静默删除/清洗原模型证据**。此新问题属于同一次四 Slot batch 混合视觉和音频，模型将视觉专属 Claim 写到 BGM 的**模态字段串扰**；不能据此宣称完整 Planning 模型端可靠，也不是 `src_*` 映射回归。

**权益与止点：**此轮使用后 `mmx quota` 5h 余量约99%、周约93%，只证明订阅窗口百分比，不推断现金明细；金额仍 UNKNOWN。未进入 B/Repair/Truth/Plan/DecisionProof/D3，未运行任何 Material Provider、TTS、Hypit Build、Web E2E，未 commit/push/部署。此轮代码 AST、`git diff --check` PASS；HEAD `d82bb60b07240a3dd0d776ec00a33c68f71cab50`、39 dirty/untracked 保留；关键当前源码 `planning_creative_authority.py` SHA256 `2de2d55db0a07526de9bb434b83f715e07f01f710e5fe09ad1f0dd7c5252c725`，`semantic_boundary_run.py` SHA256 `59287bfdf539ae48c6924319c5eacf28aff361fe786987677f00c809c8f41ffb`。

`RESULT=PARTIAL; REAL_HTTP=PASS; A_SELECTION=PASS; A_DETAILS_000=PASS; A_DETAILS_001=FAIL_NONVISUAL_EXTRA_CLAIM; FULL_REAL_PLANNING=NOT_PASS; DRIFT=NO_DRIFT; TRANSITION=HOLD`。
**NEXT_SINGLE_ACTION：在同一原 Owner 下确认音频/视觉混合 batch 的模型 Wire/Schema 隔离与非法音频 Claim 安全处理责任，提出可证明 fail-closed 的设计；离线用保存 R03 原始回执验证输入字段、不篡改它。下一次新 R04 真实模型预算需要用户另行授权；严禁重派已封存 R03、隐藏 extra field、将其当成已获 Director 授权。**

## 2026-10-15｜修订后 MiniMax M3.1 真实 Planning 复验 R02：A-selection PASS，A-details Wire FAIL

**EVALUATION=COMPLETE / REAL_MODEL_HTTP=PASS / FULL_REAL_PLANNING=FAIL_A_DETAILS_000 / RESULT=PARTIAL / TRANSITION=HOLD / U4=BLOCKED。** 继续用户已授权的原 R02/R08 成功运行环境，不用临时 pytest。前一新跑 R01 `~/.local/share/easel/creator-task-evidence/2026-10-15-planning-m31-actual-owner-eval-r01` 已终结业务 FAIL，原 Budget `BATCH_FAILED` 并关闭、无 Pending，绝不恢复/重派。以原 `2026-10-14-real-minimax-p0-medium-s5-r02` 的同版 `run.py`/`gateway_harness.py`、`PlanningEvalBoundary`/`isolated_process()`/`drain_checkpoints()`、`EvalGateway`/`EvalProviderProxy`/原 HTTP 预算在 **全新持久化** `~/.local/share/easel/creator-task-evidence/2026-10-15-planning-m31-actual-owner-eval-r02` 单独冻结当前根因修订后的源代码、270 项本轮 source/harness 文件 SHA、11/11 验证通过的 Runtime、M3.1-Flash-Preview/adaptive/medium、订阅 `sk-cp` 类型认证。限 8 次真实 HTTPS、0 自动重试，隔离本机目录；`offline-corrected` 本地预检 PASS，远端模型 0。随后唯一一次 `live`，没有触发 Provider 素材/TTS/Build/Web/部署/commit/push。

**真实运行账本：** 2 次 HTTP RESERVED / **2 次 RESPONSE_COMPLETE**、参数流 COMPLETE、pending_original_run=false、within_bounds=true；原 HTTP Budget 最终 `closed=true / close_reason=BATCH_FAILED`，不可恢复失败身份。A-selection 成功通过原 `SourceSelection`/D1 选择身份，原回复 SHA256 `608dd45278ab300ed95760740e2e4fbaf7e4533171078d8a90d139a2272d2d2d`，进入 `A-details-000`。A-details 原回复 SHA256 `29869dd5a01c0ebca2ab4b20fe9a83c31d80567008df8a9a7d7666167c945e3c`，模型输出合法 JSON、含 4 slots 共 18 条 Condition Claim，但原 `planning_candidate_review`/`planning_capture` 的 `wire_diagnostics` 对 **18/18 条 `conditions[].claim.creative_goal_ref` 报 enum**，原 Owner 报 `Planning v3合同无效：Complete Planning wire schema rejected`，无 B/Repair/Truth/Plan/DecisionProof/D3。原始 reply bytes/SHA、native run IDs、session IDs、HTTP 请求/响应、模型参数、checkpoint/journal 都保存在本轮独立目录，未变更旧 R01 原件，未把局部 PASS 当整条 Planning PASS。

**现已验证的具体技术根因：**原 A-selection 使用 SourceSelection `src_*` opaque handle；A-details 给模型的 `candidate_slots` 仍只显示 `src_*`，且真实模型在 18 条 Condition Claim 中均使用合法 `src_*`（每条指向对应 event 或合法 global 创作依据）。但当前 `BatchedVisualClaimCarrier` 继承 `VisualClaimCarrier` 的 canonical `event-* / global` 枚举 Schema，既没有在发出 A-details 之前经已有 `SourceSelection` 投影为 `src_*` 枚举，也没有在收到原 Wire 后做身份验证的可逆 decode；因此当前阶段出现 **Producer Input View / A-details Output Schema 编码层不一致**。这是上一轮 Header 修订后残留的真实 Codec 合同问题，不能用提示词让模型猜内部 `event-*` 或把所有 Claim 偷偷改写成 Need.scope，也不能直接删除枚举或 auto-accept。原 18 条 `src_*` 引用在本次冻结 `source_mapping` 可证存在，归属合法与主张合理仍须由独立 B 判定。

**费用和软件状态：**模型报告本轮总 tokens：prompt=45,222、completion=7,223、total=52,445，调用后 `mmx quota` 返回 5 小时余量约99%、周余量约93%；套餐凭证为订阅 Key，现金实际结算仍 UNKNOWN。`production_modified=false`、受测 Git `easel-studio` HEAD `d82bb60b07240a3dd0d776ec00a33c68f71cab50`、无新生产代码修改、`git diff --check` PASS。前一 191 PASS 的确定性软件基线不能代表本次真实 A-details 成功。

**NEXT_SINGLE_ACTION=先在当前唯一 Planning Owner 中修复 A-details 的 SourceSelection `src_*` ⇄ canonical `event-* / global` Claim Basis 双向可逆投影，冻结 Schema/Codec identity，保留 `need_source_ref` 与 `creative_goal_ref` 各自来源、严格枚举及原 B Review；用原 A-details 回执离线审计（不改真实原件）、负例与 D0–D4 回归验证；完成后另获授权才可建立 R03 全新独立真实 M3.1 Eval 验收。** 不恢复 R02 FAIL、不新增第二请求绕过关闭的预算；Planning 整链 REAL PASS 尚缺，噪音清理与 U4 主线仍待后续。

## 2026-10-15｜复用历史真实 MiniMax Eval 环境：当前 D1+D2 Planning 原生 A-selection 首次真实验收

**EVALUATION=COMPLETE；REAL_PLANNING_SMOKE=FAIL（已取得真实 MiniMax 原始回复，D1 Claim 身份校验拒绝）；TRANSITION=HOLD；U4=BLOCKED。** 用户明确要求不再用新建临时 pytest 或一次性 Python Gateway 测试，而是调用原先 R02/R08 **实际成功出真实 HTTP 的 Eval 环境**。已只读证实原 R02 14/14 HTTP 完成及 R08（`s5e-once-r08local20261015`）1 条 `RESPONSE_COMPLETE/WIRE_PASS_DOMAIN_NOT_YET_VERIFIED`。同时只读从 OpenClaw `task_runs` 找回前次临时 pending Run `easel-ada23ca229a14d7d88a708a146742330`，其状态 `failed`、有已完成 `ended_at`；未对它重新派发。

**重用的原环境/执行器：**从 `~/.local/share/easel/creator-task-evidence/2026-10-14-real-minimax-p0-medium-s5-r02` 复制原 `run.py`、原 `gateway_harness.py`、原 `sample.json` 到新的永久隔离证据目录 `~/.local/share/easel/creator-task-evidence/2026-10-15-planning-m31-actual-owner-eval-r01`，保留历史目录与样本和原件不变。使用**同一已有** `PlanningEvalBoundary`、`isolated_process()`、`drain_checkpoints()`、`EvalGateway`、`EvalProviderProxy`、原始 RPC 终态轮询与持久化 HTTP Budget；不是另外设计一套模型调用方式。对本轮新副本仅换成当前已验签的 11/11 OpenClaw Runtime、当前 D0–D4 源码 266 个文件指纹和本次授权/订阅配置，原有无界上限收紧为 **最多 8 次真实 HTTP、0 次重试**；保留 0700 目录、原 HTTP request/result/Token 使用情况和独立 Creation/Attempt。原 `offline-corrected` 校验 PASS（1 次本地假响应、0 远端模型调用，证明持久化 Gateway/Proxy/StopBoundary 可用）后才执行唯一 `live`。

**真实运行结果：**当前真实 `MiniMax-M3.1-Flash-Preview`，adaptive/medium/8192 token，`LIVE` 首个 A-selection 使用实际 Provider HTTPS；HTTP Budget **1 RESERVED / 1 RESPONSE_COMPLETE，SDK 参数流 COMPLETE，0 pending、0 retry，原始回复 SHA256=`237817c9d3e1a746fb105513d6a04c1f9f3e38cef2ccf45ceb920a55c5da3951`**；原 native run=`easel-dc965a095e6b4425bcbf3963a4dbe9c5`，请求/回复/Journal/HTTP budget 均持久化于本轮永久目录。已证实当前 D1 Policy=`planning-creative-owner@1`、D2 Policy=`planning-d2-typed-b@1` 真正参与 A-selection。返回 11 个 Need，7 个视觉 Need 的 `header_claim.creative_goal_ref` 都引用 `SCENES.md/whole_document` 对应的同一个冻结 `src_*`，与各视觉 Need 自身的 `need.scope` 不相等（7/7 错配）；`planning_creative_authority.py:795–806` 原合同在本地 fail-closed：`Claim did not reference its actual opaque source handle`。**这是一次真实 A Wire/Claim 跨字段语义合同拒绝**，不是 Gateway 网络调用失败，不可静默覆盖原回复或标为 ACCEPT；B/Repair/Truth/Plan/DecisionProof/D3 没有进入。完整错误在 `live/result.json`；原回执/未决现场不改写。

**额度与边界：**代理仅允许原 M3.1 文本服务，没有 Material Provider/TTS/Hypit Build/Web E2E。真实模型报告用量 `prompt_tokens=21374, completion_tokens=2959, total_tokens=24333`；用后 `mmx quota` 5小时余量约99%、周余量约93%，实际现金结算仍 UNKNOWN，不从订阅用量倒推收费金额。原 HTTP Budget 已 `closed=BATCH_FAILED`，不重放。Git HEAD `d82bb60b`、`easel-studio`，生产代码未修改、无部署/commit/push；这次 Eval 仅额外写了独立证据和本文档。

**结果与唯一下一动作：**`RESULT=PARTIAL（单次真实 Eval 执行完毕且失败）; REAL_MODEL_HTTP=PASS; ORIGINAL_REPLY=CAPTURED; PLANNING_A_CLAIM=FAIL; PLANNING_D0_D4_SOFTWARE=PASS; DRIFT=NO_DRIFT; TRANSITION=HOLD`。先在受控离线审查中核对 D1 `OpaqueHeaderBridge` 是否让模型输入的 `creative_goal_ref` 与 `need.scope` 关系表达模糊（Schema 枚举允许多 handle、跨字段运行时却要求同值），仅针对这一实际复现的根因提出最小合法合同/Prompt 调整并通过固定原回复负例；任何后续第二次真实 MiniMax 调用需重新以**新独立**授权和新持久 Attempt 执行，不自动开新的 R02 批次，不重开泛化 D1–D4 或执行有价媒体。

## 2026-10-15｜按最新 OpenClaw Runtime 重试真实 MiniMax Planning：原 A-selection 仍 PENDING

**RUN_MODE=CONTROLLED_REAL_MODEL_SMOKE / RESULT=PARTIAL / REAL_PLANNING_SMOKE=NOT_PASS / TRANSITION=HOLD / U4=BLOCKED。** 按用户本轮新授权采用当前安装版为准，确认 `dist/easel-structured-result.mjs` 真实 SHA `03c8406e5c5e1b8fa7828c4358e466ce8de3c84cf300fa8df5eec6f4c2f797c2`，Node JS 静态语法 PASS、结构化输出必要入口字段存在；在项目 `easel/integrations/planning_structured.py` 更新仅该 Runtime Pin，不删除 verify_guard。原先 11 个文件中 10/11 一致，调整后由真实 `verify_runtime()` 验证 **11/11 PASS**，OpenClaw 模型配置 `minimax/MiniMax-M3.1-Flash-Preview`、adaptive/medium、8192 tokens，有效 MiniMax auth 为订阅前缀 `sk-cp`。结构化结果相关测试 **37 PASS / 2 FAIL**（旧实验 guidance 与当前视频 Proposal fixture 两项未通过，并非 Runtime Pin），单独保留证据；不以此冒称全项目全绿。

**单次实调结果：**隔离合法新 Creation `cr_f4aee3141d2d434e9f4e69b666292510`，Attempt `fa_d30b1dd5edf0bd0282dc2d38e9ebdf29`；同一真实正式 Owner 软件 A-selection，设置本轮最多 8 个模型 dispatch 上限。实际派发入口计数 **1**，原 `request_sha256` 前 24 字符 `4ef1ffc70c58a3588595acaf`、`session_sha256` 前 16 字符 `6a31540918da6701`；`run_delivery_agent()` 返回 **`DeliveryAgentPending`（已提交，等待同一 operation 终态）**。此次已经通过旧 Runtime 阻断，不能再写作原地 fail-closed。**没有得到 MODEL_COMPLETED、raw reply SHA、B/Repair/Truth/Plan/DecisionProof/消费合同证据；真实 MiniMax 是否实际扣减、是否最终完成尚 UNKNOWN。** 单独只读 `mmx quota` 后再次显示 5 小时 100%、周 93%，这不是结算证据。

**保护与局限：**该次授权的隔离 Python 临时工作目录在进程返回后已经删除，原 Attempt/agent_calls ledger 不能作为可恢复的持久身份继续原流程；不能通过重新创建 Creation/Attempt、不同 session、复制原 request 或人工修改状态伪造幂等恢复。没有进一步模型 dispatch，未启动 Provider/Hypit Build/Web E2E、部署、commit/push。真实适配性依旧 NOT_PASS，`PLANNING_SOFTWARE_COMPLETE=PASS` 原离线结论不受影响。

**NEXT_SINGLE_ACTION=先只读核实该唯一 OpenClaw Gateway operation 的最终状态与原始回执/真实权益扣减（若能从受保护 Gateway ledger 恢复原 run_id，绝不重派）；若无法确认，按 UNKNOWN 保留，不创建第二次真实调用。然后明确采用持久可追溯的新合法沙箱/Attempt 执行下一次有界 MiniMax Smoke 的权限与消费准入。** 此项是实调续接与证据保全，不是重新打开 D1–D4 或绕过 Runtime。

## 2026-10-15｜MiniMax M3.1 真实 Planning 最小验收尝试：本地 Runtime 阻断（无真实服务端模型结果）

**RUN_MODE=CONTROLLED_REAL_MODEL_SMOKE_ATTEMPT；RESULT=BLOCKED / REAL_PLANNING_SMOKE=NOT_EXECUTED；DRIFT=NO_DRIFT；TRANSITION=HOLD；正式 U4 仍 BLOCKED。** 用户本轮明确授权一次 MiniMax 真实 Planning，小规模且只到 A/B/Repair/Truth/Plan，不授权媒体供应/Build/Web E2E。隔离合法新 Attempt：`Creation=cr_136db0d9e4f345a4a9fffc069fb2b5e2`，`Attempt=fa_454a19cbdf5f22ba039978fb71e54416`。本次工具使用临时隔离 workspace，退出即清理；其 ID 和原调用入口审计保留在本记录，不能将临时目录当作持久化 Journal/Checkpoint 或当作可以恢复的原 operation。模型路由本地只读配置为 `MiniMax-M3.1-Flash-Preview` / adaptive / medium / maxTokens=8192；Easel 专用 OpenClaw profile 默认同一模型，认证元数据显示 MiniMax 使用 `sk-cp-…` 订阅类型而非按量 Key。`mmx quota` 只读查询成功，当时 5 小时窗口剩余 100%，周窗口剩余 93%；没有输出完整密钥。

**REAL_FRONTIER=A-selection 入口，未到 Provider 服务端。** 两次本地新沙箱预检在 `planning_authority.load_inputs` 之前因未恢复确认三文件和缺少 Planning 目录被拒绝，各自外部模型调用数 0；第三次只读预检先从合法 Handoff 调用 `_restore_confirmed_planning`，证明确认原文/Mode/Context 可用，然后使用正式 `web._semantic_material_planning_executor` 进入 A-selection。最多 8 次真实请求的本地硬限制下，仅触发 **1 次 A-selection dispatch callback 入口**，记录 `session_sha256` 前 16 字符 `276ee69230cd9530`、`request_sha256` 前 24 字符 `4ef1ffc70c58a3588595acaf`；随后 `planning_structured.verify_runtime()` 在 RPC 正式提交前 fail-closed：`Structured Planning Runtime patch identity is not verified`。这不是 MiniMax A 语义失败、不是成功响应，更不是已发生一次模型账单；现场没有有效回复 SHA，也没有 B/Repair/Truth/Plan/Proof。

**准确根因：** `easel/integrations/planning_structured.py` 固定了 OpenClaw Runtime 11 个结构化输出文件 SHA，当前安装版 10/11 MATCH；唯一不匹配 `dist/easel-structured-result.mjs`：EXPECTED=`73a5029aa9d6e0276b938f3900a516b31132d4c3b00ae56ff117e5502e030cdd`，ACTUAL=`03c8406e5c5e1b8fa7828c4358e466ce8de3c84cf300fa8df5eec6f4c2f797c2`。`planning_transcript.runtime_location()` 已验证 Runtime 版本与结果选择器基线，故是当前结构化补丁这一文件身份漂移，不可修改代码期望 SHA、绕过验签或改用其他通道重派。没有更改 Runtime/服务/源代码、清理原失败/UNKNOWN 或触发 Provider/Build；本次真实 MiniMax 适配性仍 UNVERIFIED。

**NEXT_SINGLE_ACTION=单独核对并受控恢复已审核的 OpenClaw `dist/easel-structured-result.mjs` 正确安装版本，验证全部 11/11 Runtime Pin 且 Gateway 进程实际加载身份一致，再对同一已授权目标新建独立合法受控 Attempt 做一次 MiniMax 实测；如存在非终态真实请求先按原 Operation 对账，绝不重派。** 任何安装文件覆盖/服务重启需独立明确权限；原 Planning D0–D4 `PLANNING_SOFTWARE_COMPLETE=PASS` 不变，真实模型未获 PASS，U4/U5/U6 仍按原 Gate。

## 2026-10-12 同一 U2 候选受控加载与 U4 复检

**CONTROLLED_LOAD=COMPLETE；RESULT=BLOCKED（U4）；DRIFT=NO_DRIFT；TRANSITION=HOLD；U2_CANDIDATE_READY / U3-S=PASS / U3-L=NOT_STARTED / RELEASE_NOT_AUTHORIZED。** 本轮用户明确授权候选前端/安装 Skill 同步、前后端重启和本地页面读取；没有授权生产确认、模型/Provider、有价调用、真实 E2E 或 U5–U6。承接前次加载差异，不重启历史迁移。

### 同一候选加载与只读验证

- 加载前逐项核验 U2 manifest SHA `846bb445d7df5fdfd98332b68e4f989f6e07e64d24e14bb1e226c072b5cd6ddc`，1,233 项 Source/Test/Skill、8 项非敏感配置及 5 项隔离 React 产物无漂移。原服务 dist 移至本轮非公开临时备份目录；直接安装已验收的 5 项 React 产物，未重新构建或改变候选指纹。
- 同步安装文件 11 份：7 个 Skill 的 `SKILL.md`（ai-video-gen、beat-sync-video、hypit-authoring、multi-voice-dubbing、paper-explainer、slideshow-video、video-intro-outro）、multi-voice-dubbing/paper-explainer 的两份 EASEL-META、paper-explainer 的 storyboard reference 和一份 skill-wechat-publisher 安装包附带测试文件。旧文件均完整备份；**仓库源码/测试文件没有修改**。核验安装 112 个 Skill 集合、598 个存在文件及 118 个候选删除身份全部匹配，没有额外或遗漏的 Skill。
- 项目前端由 FastAPI 提供，没有独立 5173 前端开发进程。本轮重启原 `com.easel.web` LaunchAgent，旧 PID `35281` → 新 PID **`98148` / 2026-10-12 23:37:31 +08:00**；仍只监听 `127.0.0.1:7860`。当前 OpenAPI SHA `efa13175291909b748e0a5d546db06d6e5609ea9c9401bdb03aecbbdebd8be3c`，规范化后 **80 个实际路径注册 = 80 个当前源码路径，无增减/方法差异**；原 15 个旧注册已消失。没有调用旧生产端点进行试探。
- 浏览器访问前只读 GET `/` / `/api/status` / `/openapi.json` 为 200；Gateway health 为 true。服务 index SHA **`22e1fa4efad2ed8516ca5b300f79c746662f864771d1f7d64109999c6ea9ecd8`** 与候选一致，其引用的候选 JS `index-BcwhSvxF.js` 在服务 dist 的 SHA 为 `e303bf1766b7941c15b504f2674c1f523182c8a65aa6dff0a3fb592f6a12e3ba`；5 项磁盘产物全部匹配。`/onepage` 及三条旧 static HTML 入口均 404。
- Gateway 原 PID `86014` 和启动时间保持，OpenClaw 2026.9.4 的 11 个磁盘补丁 pin 全部匹配；本轮没有重启 Gateway、执行会话修复或新 Agent Job。Hypit 0.2.7、本地 Runtime profile SHA `1e4099d70ed19b6ebed1451ad430cf0f9c3bbd464d9218712874af1744d18a51` 保持，没有任何 Hypit CLI/Check/Plan/Pricing/Build。安装磁盘身份不能证明 Gateway 进程内全部字节或原会话的缓存 Prompt；不为获取这种证据派发模型请求。

### U4 缺证与现场保护

虽然本轮用户明确授权页面读取，浏览器安全审批仍返回 **“A saved user permission setting blocks this action”**，阻止访问 `http://127.0.0.1:7860`。没有成功创建页面、读取按钮或执行确认；未改用其他浏览器、原始控制或间接页面渲染绕过。**ACTUAL_UI=NOT_VERIFIED_SAVED_PERMISSION_BLOCK**，区别于产品 UI 故障。拒绝后仅完成独立本地文件与保全检查，没有再通过 HTTP 达成被拒绝的页面读取。

重启前后核对实际 Delivery 资格：`cr_ca48a2d63ade46b6bd88664aa436e9ad` 无下一操作、等待证据；`cr_3ac59f99a8fa4d79a588423f8d688dc8` 的 prepare 原失败次数为 3 且原 exhausted_operation 匹配，现行 Owner 门禁阻止执行。两条记录均保持原字节；没有手改失败状态、点击 retry、释放原占额或自动开始 Preparation。其余历史 Creation 不进入现行生产 Worker。

29 个现有 Creation / 25 个引用 Attempt 的既有 Rights、费用/UNKNOWN 观察与上一记录相同，**不重放、不重新解释或清账**。10 份原生成结果的 billing UNKNOWN（8 个不同原文 SHA）保持，Gateway 46 份原请求记录 SHA 保持。当前套餐余量、未结算占用及下一请求最高现金风险仍 **BUDGET_NOT_PROVEN**；本轮新增模型/Provider/生产确认/有价服务/Hypit 请求均为 0。没有把免费 CI 报价或凭证存在当成真实请求的现金保证。

本轮证据和完整旧安装备份在 `/private/var/folders/s8/sh775m3d14s259bbqfs3w5b40000gn/T/easel-u4-load-eiudtbqm/`：`start.json`、`sync-result.json`、`served-dist-before-load/`、`installed-skill-backup/`、`loaded-web-audit.json`、`loaded-openapi.json`、`skill-sync-verification.json`、`runtime-identity.json`、`delivery-no-dispatch-check.json`、费用观察及最终指纹检查。旧安装备份不在公开服务根目录，不构成第二条执行主线。

**EVIDENCE=受控加载同版已验证，112 Skills 合同通过；实际页面与现金上限未验证，U4 不放行。LESSON=保存的浏览器访问策略须独立解除，聊天授权不会自动更改工具设置。NEXT_SINGLE_ACTION=暂停，待用户解除浏览器保存的本地地址禁用设置并具备可靠现金上限证据后，再继续同一候选的 U4 只读预检。** 不自动进入 U5–U6，不再重启或新增生产请求；无真实 Web E2E / DEBUG PROGRESS / RELEASE PASS 新结论。最终保全与文档检查结果如下方收尾。

**收尾：**HEAD `ce6fa81739b812ff6bed8115cabd78bdf548e389` / `easel-studio`、74 M / 121 D、0 staged / 0 untracked 保持；仓库相对起点只有本 Task、Current State、本账本变化，未改生产/测试/配置。候选 1,233/8/5 项身份和实际服务 5 项 React 产物均匹配；3,255 个既有运行 JSON/JSONL、46 个 Gateway 请求 SHA 无变化，现有 29 个 Creation ID 集合不变，没有新增 Creation/Attempt 或业务请求。112 Skills 合同、本轮 4 个新增引用/锚点与 git diff --check 通过。受控重启的 Web 进程保持健康启动身份，旧安装备份保留；最终报告在 `final-fingerprint-check.json`。**本轮已暂停，U4 仍 BLOCKED。**

## 2026-10-12 U4 无付费只读预检运行证据

**RESULT=BLOCKED（U4）；DRIFT=NO_DRIFT；TRANSITION=HOLD；U2_CANDIDATE_READY / U3-S=PASS / U3-L=NOT_STARTED / RELEASE_NOT_AUTHORIZED。** 本轮仅授权现场只读预检，未点击生产确认、派发请求、查询 Provider 或调用 Hypit。此结果不推翻 U2/U3-S 软件证据，但不得进入 U5–U6。

### Web 与实际加载身份

- 后端 PID `35281`，启动时间 **2026-10-11 13:11:49 +08:00**，工作目录本项目，监听 `127.0.0.1:7860`。访问浏览器前只读 GET `/` 和 `/openapi.json` 均 200；OpenAPI 原文 SHA `5d2457db2b0e5cab3519a03a47a162e35e5d16b93c5313b30b1c7ee52320f019`。路径转换器规范化后，当前源码注册 80 个路径，实际加载注册 95 个；多出的 15 个包括 `/onepage`、Creation stage/handoff、旧 Attempt author/build/export/reconcile 及直接素材生成等。完整差异列在 `loaded-version-audit.json`；**没有调用这些主动接口，不能用路由注册推断其会执行、拒绝或付费**。`/static/index.html`、`main.html`、`onepage.html` 返回 404，只证明此次请求结果。
- 页面 index SHA `19e606decf4f8df676d63917aa4956d05235e5258e0bf51c19673b0ce867e70f`；它引用磁盘 `index-WHRnRRmi.js`，SHA `b5667e8b4ef61cdbacf32f88e1a0f34c63331755790369140b96f4953c85ee7a`，mtime **2026-10-12 19:34:23 +08:00**。U2 隔离候选 index SHA `22e1fa4efad2ed8516ca5b300f79c746662f864771d1f7d64109999c6ea9ecd8`，JS `index-BcwhSvxF.js` SHA `e303bf1766b7941c15b504f2674c1f523182c8a65aa6dff0a3fb592f6a12e3ba`，后者不在服务 dist 中；另 CSS/图标三项一致。**React 加载产物不同，不只是后端需要加载当前版本。**
- 浏览器创建本地页面时安全审批拒绝，原因为 **user declined permission / 用户未授予访问许可**。没有创建页面或点击任何按钮；此后未通过其他浏览器、HTTP/UI 转换或间接方式绕过访问拒绝。实际 Creator 页面、Proposal @4 投影、按钮及拒绝行为为 **NOT_VERIFIED_BROWSER_PERMISSION_DENIED**。上述访问前的接口结果和磁盘检查不冒充实际页面验收。

### Gateway / Skill / Hypit

- Gateway PID `86014`，启动于 **2026-10-10 21:43:42 +08:00**，loopback `18789`；安装 OpenClaw **2026.9.4**。候选 pin 的 **11 个结构化结果运行文件磁盘 SHA 全部一致**，最新文件 mtime 早于该进程启动；这仍不是进程内全部加载字节的直接证明。未启动 Job、`agent.wait`、会话修复或 Gateway patch。
- 已安装 112 个 Skill 的 `SKILL.md` 中 **105 一致 / 7 不同**：`paper-explainer`、`video-intro-outro`、`multi-voice-dubbing`、`beat-sync-video`、`hypit-authoring`、`slideshow-video`、`ai-video-gen`。部分安装文本仍引用旧 auto-short-video 组装路径，hypit-authoring 尚缺候选的 Material 准入限制；这里只证明安装合同未同步，不推断执行结果。逐文件 SHA 和差异在 `openclaw-skill-audit.json` / `skill-*.diff`，未修改任何安装文件。
- Hypit 安装 **0.2.7**；只读当前进程环境下解析的 Runtime profile `/Users/xgx/.easel/hypit-v1-runtime/hypit.runtime.json`，SHA `1e4099d70ed19b6ebed1451ad430cf0f9c3bbd464d9218712874af1744d18a51`，local media/hyperframes、空 bindings/credentials。该磁盘配置不证明后端继承环境或下一请求报价；本轮没有执行 Hypit CLI、Check/Plan/Pricing/Build。Gateway 主模型配置 MiniMax-M3/无 fallback、凭证仅记录存在性；未输出 Secret，也未验证真实套餐额度。

### 只读 Rights / 费用 / UNKNOWN 观察

- 29 个已存 Creation，引用 25 个 Attempt；保存的 Agent 状态为 225 ok / 12 error，Build 状态为 20 NOT_SUBMITTED / 4 BUILD_COMPLETE / 1 BUILD_FAILED，未见保存的待执行 Agent 或非终态 Build。Gateway 的原结构化请求保留 22 个 RESERVED 和 24 个无 state 记录；RESERVED 是原派发身份留存，不能据此认定仍运行或已经结算，未进行实时查询。两个 @4 Creation 分别为 needs_evidence / failed，均无 Build；未把既有检查点恢复为生产。
- 引用 Attempt 中 **10 份 COMPLETE 生成结果的 billing 均为 UNKNOWN**，其中同一原生成记录在三个 Attempt 中完整复用，按原文只有 **8 个不同 SHA**。这些数量不是费用总额或收费次数；不重新解释旧业务结果、不合并改写记录、不清零 UNKNOWN、不补 request 身份或重派。原首片 @3 Creation 的 7 Attempt、24/24 Preparation 计数保持，不回放。
- 被引用工作区中 368 个 asset 快照的保存 Rights 为 344 KNOWN / 23 ATTRIBUTION_REQUIRED / 1 PUBLIC_DOMAIN。295 个当前可读原件 SHA 与保存值一致；73 个原快照的引用文件在观察位置不可读，保持现场、不恢复或删除。以上只读快照统计**不证明新生产的 Need/Bundle/Rights 准入**。当前两个 @4 Creation 没有生成结果，也没有据此补出 MATERIAL_READY。
- **当前套餐剩余额度、已有 UNKNOWN 占用金额及下一请求最高现金风险未得到可靠证明：BUDGET_NOT_PROVEN。** 历史 ¥10 上限、凭证存在、模型 maxTokens 或 U3-S 的 0 元隔离 CI 报价均不能替代当前权益/现金证据。无新增费用请求，未将 UNKNOWN 当零；本轮未新增生产授权。

### 保全与交接

证据目录 `/private/var/folders/s8/sh775m3d14s259bbqfs3w5b40000gn/T/easel-u4-readonly-pgdqiqu1/`：`u4-preflight.json`、`start.json`、原 GET 响应、`loaded-version-audit.json`、dist 比较、安装身份/Skill pin、脱敏 Runtime 配置、Creation/Rights/费用原件索引、Gateway 观察与最终保全检查。没有创建第二套方案或正式审计文档。

**NEXT_SINGLE_ACTION=暂停，等待明确授权受控加载同一 U2 候选；具备页面读取许可及当前费用上限证据后重做 U4。** 本轮不部署/重启、不进入 U5–U6。U2 软件候选与 U3-S PASS 保持，U4 不放行，真实 Web E2E / DEBUG PROGRESS / RELEASE PASS 均无新结果。最终候选、历史原件和文档范围核验结果附于本节收尾。

**收尾核验：**HEAD `ce6fa81739b812ff6bed8115cabd78bdf548e389` / `easel-studio` 未变；相对本轮起点仅 Task、Current State、本账本三份文件变化，保留 **74 M / 121 D、0 staged / 0 untracked**。U2 manifest SHA `846bb445d7df5fdfd98332b68e4f989f6e07e64d24e14bb1e226c072b5cd6ddc` 及 1,233 项源码/测试/Skill、8 项非敏感配置、5 项隔离 React 文件逐项无漂移；起始 **3,255 个运行 JSON/JSONL SHA 全部未变**。Web/Gateway 的 PID 和启动时间未变。`git diff --check` 通过，本轮新增文档链接可解析；检查同时发现历史 Task 段落已有 30 个本地 fixture 引用不可解析，未恢复或改写这些历史入口，不宣称全篇历史链接通过。实际页面缺证与本地加载差异仍保留 BLOCKED；没有通过新增测试或历史回放替代 U4。最终核验原件见 `final-fingerprint-check.json`。

## 2026-10-12 U3-S 无付费本地连续集成运行证据

**U3-S = PASS / SOFTWARE_INTEGRATION_PASS；U3-L = NOT_STARTED；RELEASE_NOT_AUTHORIZED。** 本轮用户仅授权当前候选的 45～60 秒中文 mixed 本地集成、关键拒绝和冷恢复；不重放历史失败，完成即停。以下是真实本地渲染的软件证据，**不是实时 Provider、真实 Web E2E 或 Release PASS**。主方案 §8.3 允许外部固定回执；内部 Owner、Rights/Readiness、Hypit Build、媒体解码与最终准入均实际执行，没有直接写入 MATERIAL_READY/Quality READY。

### L2 连续链与实际媒体

- 候选：HEAD `ce6fa81739b812ff6bed8115cabd78bdf548e389` / `easel-studio`；U2 manifest SHA `846bb445d7df5fdfd98332b68e4f989f6e07e64d24e14bb1e226c072b5cd6ddc`。源码/测试/Skill 1,233 项、非敏感配置 8 项、隔离 React 产物 5 项保持原指纹；安装 Hypit 0.2.7，使用独立临时 Runtime，仅本地 media/hyperframes、空凭证，不加载/重启生产服务。
- 新的隔离 CI Creation `cr_03b8bc9f10f24975a21625e24eb2e86a` / Attempt `fa_cfc537ec88deaccee172502d48d8c033`；Build `bld_20261012T145221177Z_BFC9CDFB37`，operation `op_1f217db2e2c647b2a82d2b298f9df068`。原五 pin 为 `truth-source-ref@1 / material-observation-delta@1 / easel-script-claim-ledger@3 / quality-review-delta@1 / easel-hypit-source@1`，Planning 保持当前 @7/@9/v3。Proposal @4、Consent @3、完整 SCRIPT、预置 Voice 身份和 frozen Creator/Director/Creative Mode 经现行 Owner 消费。
- 外部确定性边界：Planning/Truth/VLM 固定合法回执；MiniMax Speech 外部回执返回本机 Tingting 实际中文音频，**仅验证身份绑定及现行合同消费，不证明真实 MiniMax 声线或 Provider 授权**；BGM 与视觉本地自建。实际 Whisper 对完整 SCRIPT 转录/计时，实际 AST 对音乐源观察；Audio/Visual SHA、Material Match、Bundle、Readiness 和冻结 Rights 均由现有模块处理。普通人工 Rights 不能替代生成旁白来源的拒绝原件保留。公开 MiniMax 协议页只读取得，原文提取 SHA `90d05ccc1dbf8404cbc40cfb096698ceec2bc894440ac507cd048ecb9a896ae0` 与已批准条款 pin 相同，未修改合同常量或给历史 Attempt 补资格。
- 真实 Hypit Check/Plan/Pricing：7 个请求 / 7 个 no-charge / `groups=[]` / USD 0。成本批准前 submit 实际拒绝，未创建 Build operation。真实付费 AI/Provider/TTS/Build 请求为 0；离线模拟的生成记录、预留和 UNKNOWN 仍保留原身份，不冒充真实结算。
- 成功 Attempt 的真实 Build 只提交一次，成功导出唯一目标 `final.video`。文件：[本地 MP4](/private/var/folders/s8/sh775m3d14s259bbqfs3w5b40000gn/T/easel-u3s-fficf06b/ci/outputs/_creations/cr_03b8bc9f10f24975a21625e24eb2e86a/attempts/fa_cfc537ec88deaccee172502d48d8c033/final.mp4)；**SHA256 `07024bb66cb601fb144179598f482b4c06d1c1c2d7330f14e9148043c9c2d070`，1,033,271 bytes；50.000 秒 H.264 1080×1920 + 50.000 秒 AAC 48kHz 双声道**。实际 Export 由当前 `web._execute_creation_delivery` 查唯一目标，未绕过当前委托资格。
- Quality 实际采样 100 帧，旁白 87 窗最小相关度 0.997；无 clipping/声音遮蔽缺陷，BGM 末段 45/47/48 秒相关度均 1.0；技术 `defects=[]`。System Quality READY、Final Admission 通过。VLM/人工 Review 是明确 CI 外部回执，APPROVED 只属于内部软件测试，不是人类试听、完整播放或发布批准；Rights 的 `internal_production_only/current_creation_only` 限制保留。Main 实际查看 1/25/49 秒画面，中文字幕/视觉在其适用区间可见，末段实际 BGM 信号保持。

### 关键拒绝与原操作冷恢复

`rejections-cold.log` **14 PASS / 20 deselected，228.05s**：Native 成本、runtime bytes/Plan 漂移、UNKNOWN、三切点导出凭据、委托撤销及 Authoring checkpoint 恢复。`material-rejections.log` **3 PASS / 214 deselected，19.57s**：Voice 授权撤销、原音频 SHA 和 Rights UNKNOWN。`protocol-rejections.log` **11 PASS，44.00s**：当前 New-Only 旧主动入口、未准入素材/运行身份及合法停止后的取消边界。没有推断整套 Material 新结果，也没有迁移或删除旧失败测试。

真实 Build 回执在外部边界注入丢失后，Attempt 为 SUBMISSION_UNCERTAIN，重复 submit 返回原 operation 的 idempotent replay、未再 Build。独立新 Python 进程按相同工作区/operation/运行证据认领原 Build；结果入库前保持 unresolved、`retry_allowed=false`。导出后另一个新进程禁止质量 executor，重读保存 Quality、五 pin 和同一实际媒体 SHA，再次通过 Final Admission。`run-18.log` 连续链检查点接续 **1 PASS，16.39s**，不是首次整条运行耗时；`cold-final.log` 独立最终重读 PASS。

本轮失败原件未删除：第一份独立 CI Build `bld_20261012T144915414Z_4249EC6352` 为沙箱 `listen EPERM/pgrep denied`，原 operation 终态失败、无 MP4；获本地隔离渲染权限后另建本轮 CI Attempt，未恢复历史生产。成功 Build 曾被临时脚本错误请求 Output `final`，真实目标为 `final.video`；只修临时验收脚本，沿原成功 operation 完成实际 Export，不修改 Authoring 或重发 Build。所有临时失败日志保留，不能把失败 Build 算通过。

### L1 原件只读分类与当前边界对应

原作品仍为 Proposal @3；**7 个历史 journal / 15 份原始 reply 的 SHA 逐一核验，未重放、未重新解释旧业务结果或恢复旧生产**。原生产不具备当前 @4 准入，标 `HISTORICAL_READ_ONLY / NON_REPLAYABLE_AS_CURRENT_PRODUCTION`；丢失 B 不伪造回复。完整原件路径、request/reply SHA 和 journal SHA 在本轮 `l1-readonly-classification.json`，分类仅作原件审计。对应当前风险验证如下：

| 原 Attempt / 风险 | 当前应有判定与实测证据 |
|---|---|
| `fa_d31a3e20ab22070d99842241a868f44d` / 动作由静图承接 | REJECT；当前 `test_vnext_tool_schema_matches_frozen_choices_and_existing_modality_rules` 拒绝 image 的 required dynamic_action，不靠静图抹掉来源义务。 |
| `fa_559421cca275b16c490249a4571a509b` / role 超长 | 合法短 role ACCEPT，超长 REJECT，不截断；本轮 `current-contract-probe.json` 当前 Schema/consumer 判定一致。 |
| `fa_da27c309a6428657cbac964b3cff9784` / B 丢失 | 缺结果/终态不释放结果或重派；`test_vnext_full_capture[missing/lost_terminal]`；既有当前 R6 B-000 冷恢复证据见 U2 Task。本轮真实 Build UNKNOWN 同 operation 恢复另证。 |
| `fa_07e8c628b4508ea1815930502943a9ea` / framing | 合法组合保持语义，非法 mode/ratio REJECT；`test_vnext_review_contract_protection[atomic_frame]`。 |
| `fa_8d848d7c2b6dba5dd61b508a9abacc5b` / B 引用对象 | 可证等价 codec 往返；非法字段/引用 REJECT，不猜测改写；`test_vnext_review_contract_protection[xml_codec]`。 |
| `fa_ca09eac4f3afcb40b94a903943565d9d` / A-details 游离字段 | 顶层/Need 未注册字段 REJECT，不移到别处；本轮 `current-contract-probe.json` 正反对照。 |
| `fa_eb89de3f9300c1851378db0455157d40` / tempo 对象包装 | 合法 `[60,90]` ACCEPT，`{item:[60,90]}` REJECT，不擅自规范化；本轮 `current-contract-probe.json` 当前 Schema/consumer 一致。 |

以上具名当前 Planning 集合 `l1-current-boundary.log` **5 PASS，0.87s**，另六项合同探针 PASS。只证明当前风险边界，不把原七次真实 FAIL 改成 PASS；按用户要求没有历史失败执行回放。

### 指纹、证据保全与停点

证据目录 `/private/var/folders/s8/sh775m3d14s259bbqfs3w5b40000gn/T/easel-u3s-fficf06b/` 保留：`test_u3s.py`、各轮日志、`u3s-result.json`、实际 Build/Export/Quality/冷进程回执、`mp4-probe.json`、首中尾 PNG、生成/Voice/音乐观察与公开条款原件、L1 原件映射和 `final-fingerprint-check.json`。编译、Skills 合同、git diff --check PASS。独立只读 Reviewer **CONTINUE**，核验了实际 MP4 SHA、连续链/冷恢复和替身边界；Main 签字 U3-S 软件资格。

既有 3,255 个运行 JSON/JSONL SHA 全部未变，起始 dirty 全部保留；本轮仅修改 Task/Current State/本账本，最终 74 M / 121 D、0 staged / 0 untracked（本账本从本轮起点的 clean 变为 modified）。两份本轮临时 Worker 已关闭；无生产服务部署重启、实时模型/付费 Provider、真实 Web E2E、Git commit/push/reset/clean。**RESULT=COMPLETE（仅 U3-S）；DRIFT=NO_DRIFT；TRANSITION=HOLD。NEXT_SINGLE_ACTION=暂停，等待用户单独授权 U4 无付费只读预检；本轮不进入 U3-L/U4–U6，不自动发布。**

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


### 2026-10-16 用户暂停停点（覆盖此前 NEXT）

用户明确要求“先暂停”，已停止离线测试，不再派发 HTTP/新 Attempt。新增授权已用 16/60 HTTP（R12=1、R13=15），全部 RESPONSE_COMPLETE，无 Pending/UNKNOWN；剩余44次保留，须用户恢复后才执行。旧29/30账本保持关闭。

R13 `fa_91f768503236ec8cc8260239f0ce2323`：A-selection/A-details通过（原 Owner Repair 1/3），10批B原件已收齐；汇总 Repair 请求1,172,075字节，超过未变的1 MiB上限，在派发前严格拒绝。Truth、D2 Proof、Cold Verify及PLANNING_ACCEPTED未通过。

当前未完成修改：request_view @3 将重复 evidence_choices_by_target 完整表纳入原有无损上下文引用，journal @19；R13真实原件离线回放847,290字节、R11回放697,779字节，恢复原文严格相等，Tool Schema未变。最新回归因用户暂停中断，36 PASS/1 FAIL；FAIL为测试期望4个目录项、实际3个（待核实测试数据是否达到512字符去重阈值），不得记为验证完成，不得将当前版本用于真实派发。此前@2版本54 PASS不代表@3验证完成。未修改合同或容量，不新建Agent，无Git/制作/部署动作。

RESULT=PARTIAL；DRIFT=NO_DRIFT；EVIDENCE=真实调用16次全部终态、Repair容量离线回放通过但最新回归未完成；LESSON=相同目标证据选项表也是大请求重复来源；NEXT_SINGLE_ACTION=用户恢复后先核实并修复定向回归，再完成离线验证，之后才允许新Attempt；TRANSITION=HOLD（解除条件：用户明确恢复且当前修改离线回归通过）。


**2026-10-16 离线验收补录：**本轮新增HTTP=0。R11/R13完整原件重建Repair分别209218/325946字节，完整恢复/Tool Schema等价；55项相关回归及最终3项容量派发保护通过。真实执行保持暂停；详见[实施方案§8.35](../tasks/planning-creative-authority-implementation-plan-2026-10-15.md)。


**2026-10-16 R14真实失败留证：**新Attempt `fa_8c691526c999185477ed4b55f2cd7dfc`，14/14 HTTP完整、原生全部released、无Pending/UNKNOWN，Repair1/3修复5个局部答案，真实Repair正文171450字节已实际派发并返回，容量问题未复现。随后D2按模型source_or_truth_violation拒绝：两份报告仅描述资产许可待核验。原结果保留FAIL，Truth/Proof/Cold未达。累计新账本30/60、剩30；本次tokens 925943，仅现有套餐，现金结算UNKNOWN。按已接受方案§2.2（资产许可待供应不等于Creator用途授权缺失）只澄清提示，未改变Schema/领域/授权判定；离线验证后新Attempt继续，不改原件。原件及audit见2026-10-16-planning-m31-controlled-loop-live-r14。


**2026-10-16 R15–R17真实失败留证：**R15 `fa_b8ec714ca5f28c158c46db6e3d0fd87c` 1HTTP，A-selection编造src_75；R16 `fa_90884d5795937301328d825527f20c38` 2HTTP，A-details同时错误来源与缺unresolved，不符合单纯来源错误恢复条件；R17 `fa_a5ff6f28b38fddb8b08f74728d25dda6` 13HTTP，A通过、B-000至007捕获，B-008完整SSE stop零工具，无安全候选，Repair0/3。三次均原生全部released、无Pending/HTTP UNKNOWN、旧Attempt不续派，原错误不补字段不换来源。各次audit与tokens见同名私有证据目录。累计新账本46/60，R18以剩余14次新身份启动，同@21版本，无新业务合同/输出Schema修改。


**2026-10-16 R14–R19最终对账：****账本与费用：**恢复44次全部RESPONSE_COMPLETE/SSE_DONE，5次stop零工具保留为真实失败（不冒充安全模型结果）；全部原生操作released，无Pending/HTTP UNKNOWN。恢复期tokens=2442667（prompt2299198/completion143469）；新增60次tokens=3542834（prompt3340809/completion202025）。与前闭合29次合计89HTTP，若另计R07/R08原12则101HTTP。只用现有M Plan、不充值/无现金fallback；现金结算UNKNOWN，不能记0元。私有证据`2026-10-15-planning-repair-context-dedup-r02/final-resumed-audit.json`及R14–R19各final-audit，已关闭共享task-http账本；最新指纹`a9de5296ec905348712902b64ba1664b8bc7269a8fd392315f5b95d65597a205`。


逐Attempt完整结果见[实施方案§8.38](../tasks/planning-creative-authority-implementation-plan-2026-10-15.md)。R19因额度耗尽停止，完整Planning NOT_PASS，用户44次恢复授权已耗尽。
