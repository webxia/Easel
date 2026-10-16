**2026-10-16 本轮预算定位补记：**共享60次HTTP的实际跨Attempt预算Owner位于私有封存历史 `2026-10-15-planning-repair-context-dedup-r02/control.py`，使用原有 `task-http.lock` 和共享 UNKNOWN 预约；仓库的 `EvalHttpBudget.completion_preflight` 为只读诊断，历史Owner没有接入该方法，修改预检本身无法修复 R19 的启动决策或共享占额竞态。本轮不改封存控制器/账本、不创建平行预算Gate。当前回归 `tests/test_openclaw_structured_result.py` 38 PASS / 2 FAIL，失败均为§8.40已记录的旧指令替换实验和Proposal@3 fixture；预算预检专项单测PASS。生产未加载、真实Planning仍NOT_PASS。详细定位见Planning §8.40后续。

**当前离线续接（2026-10-16，Planning §8.40）：**专用原始输入隔离与已定位恢复协议缺陷已修复并离线验证：structured@2/context-only/Journal@22、最终HTTP输入SHA校验、v1历史只读、新拒绝记录读取及assistant-failure隐式重派拦截。78项定向回归、本组30项闭合，原R18 Schema/输入/回执SDK重放与当前Owner A/B/Repair/B-recheck/Proof/冷恢复通过；真实安装未加载、新增真实HTTP=0，原60/60及29/30账本SHA不变，完整真实Planning仍NOT_PASS。预算目前只有只读预检，跨Attempt最终原子准入及B恢复扩展未落地，RESULT=PARTIAL/DRIFT=NO_DRIFT/TRANSITION=HOLD。NEXT=仅离线完成现有共享预算Owner最终占额处的冻结工作量准入设计与接线；不真实调用、不放宽业务合同。合同可简化项及3项旧fixture失败见[实施方案§8.40](tasks/planning-creative-authority-implementation-plan-2026-10-15.md)。

**当前有效Closure（2026-10-16，覆盖此前进行中/暂停NEXT）：**`RESULT=STOPPED / DRIFT=NO_DRIFT / TRANSITION=HOLD（预算耗尽）`。恢复授权44/44HTTP已用完（R14–R19），新额度总60/60关闭；全部HTTP完整、原生released，无Pending/HTTP UNKNOWN。R14真实Repair正文171450字节已派发并回传，容量修复得到真实验证；完整Planning仍NOT_PASS，Truth/D2 Proof/Cold/PLANNING_ACCEPTED未达。期间仅澄清现行资产许可待供应与Creator授权缺失的提示区别，75项离线回归PASS，@21，合同不放宽。最新R19 A全通过、3批B捕获，下一B调用在总额度guard前被拒绝，无第61次远端HTTP。NEXT=停止真实调用；可另行离线调查5次stop零工具结果，任何后续实调需新预算授权。原件/消耗见唯一E2E账本与Planning§8.38。

**当前有效停点（2026-10-16，覆盖历史NEXT）：**输出合同原件离线排查完成；29批225题中51个局部目标，38个原始结构错误、13个领域引用错误，转换前后答案相同。已消除提示题型字段歧义并补音频header排除说明，实际Schema/领域合同未变；52项集成+3项容量回归PASS，Journal/Checkpoint@20。真实调用仍暂停，新增HTTP=0，新额度仍16/60、余44。NEXT=等待用户明确恢复真实调用，完整Planning仍NOT_PASS；详见Planning实施方案§8.36。



**2026-10-15 最终Closure（覆盖下方历史NEXT）：**本轮整体 `RESULT=BLOCKED / DRIFT=NO_DRIFT / TRANSITION=ESCALATE`，首次真实完整Planning尚未通过。已完成R07/R08原件对账、设施受控恢复验证、R09跨批Repair定义冲突修复及当前52PASS；R10因BGM越界Header拒绝。R11真实no-tool由新Operation合法恢复，A全部批次通过、75题B原回执齐全，但13目标Repair正文1,136,224字节超过1MiB，在派发前拒绝，B正式未通过，Truth/D2 Proof/正式冷加载/PLANNING_ACCEPTED未到达。累计新增29/30 HTTP、1,948,000 tokens；原生全部released，无Pending/HTTP UNKNOWN，现金结算UNKNOWN，仅现有M Plan套餐/no现金fallback。各Attempt及共享账本已关闭，余1次不足新完整Attempt，未浪费调用。完整原件、身份和消耗只见[唯一E2E账本](acceptance/easel-v1-web-real-e2e-2026-10-10.md)。**NEXT_SINGLE_ACTION=用户补充足以完成新合法Attempt的累计预算边界；随后在现有Task做Repair上下文可逆去重与原件离线回放，再新Attempt真实复验。**不重开旧Budget，不进入素材/Build/Web/U4/部署/Git或新Agent；本轮停止。



# Easel Current State

**最新授权续接（2026-10-15）：**用户新增60HTTP，仅现有M Plan套餐，直到首次完整Planning PASS或额度用完；旧已用29/旧余1均封存，新账本绑定历史不清零。R11 Repair上下文过大已做严格可逆去重，1136224→892500字节、完整还原相等、Tool Schema与1MiB上限不变，54PASS；新输入表示@2/Journal与Checkpoint@18，当前全新R12真实复验中。历史停止NEXT不再调度本轮；流水与消耗只归[唯一E2E账本](acceptance/easel-v1-web-real-e2e-2026-10-10.md)。不进入素材/Build/Web/U4/部署/Git/新Agent。

> **唯一当前状态 · 2026-10-14 文档治理收口。** 本文件只保留已核验状态、有效阻塞和下一动作。历史批次不再按日期堆叠；原 300 行/123,518 字节全文已按 SHA 保存在 Mac 私有工作区归档。文档治理已完成，之后的 Git 提交及轻量审计也不构成新的 Gate 验收。权威规则见[唯一 New-Only U0–U6 主方案](architecture/web-backend-new-only-cutover-plan-2026-10-11.md)，原始产品运行证据见[唯一 E2E 账本](acceptance/easel-v1-web-real-e2e-2026-10-10.md)。

## 当前正式主线

**Easel Web Creation / Proposal @4/Creator 确认 → Preparation → Planning/Truth → Material V1.3 / Rights / MATERIAL_READY → Native Hypit Authoring → Check/Pricing/Build/Export → Technical QC / System Quality → 人工 Review/Selection/Content Library。**

一个 Creator/Profile + 一个 Director/Creative Mode + 不同 Content，冻结导演表达但不固定选题；不自动发布，不回退旧视频 Producer/Writer，也不把 Material Layer 变成第二个导演。Material V1.3 / ADR-004、现行五 pin、源文件与输出 SHA、Rights、费用/UNKNOWN 保持不变。Planning 是真实 Web 生产链中的必经环节，而不是独立的 Gate。

## U0–U6 当前有证据的状态

| Gate | 实际证据 | 当前判定 |
|---|---|---|
| U0/U1 | 唯一标准 2026-10-11 获批准；运行/历史文件保护持续执行 | U1 PASS；U0 是持续保护义务 |
| U2 | 2026-10-12 New-Only 唯一受控候选、React/Skill/Web 当时版本加载和旧入口退役有正式记录 | **CANDIDATE_READY（2026-10-12 原指纹）**；之后工作区源码有变更，旧证据不自动放行新同版 |
| U3-S | 已用合法固定外部回执，通过现行五 pin/内部 Owner/Material/Hypit 的真实本地 50 秒 MP4、Quality、拒绝与冷恢复 | **SOFTWARE_INTEGRATION_PASS**；非真实付费 Provider / Web E1 |
| U3-L | 长 BGM 原素材、完整 Voice/ASR、900 秒长 MP4、首中尾质量、峰值资源、四模式和 >900 秒边界 | **正式资格尚未通过**；局部 900 秒源码和 fixture 不等于 U3-L PASS |
| U4 | 候选已受控加载，但真实浏览器访问遇保存的权限拒绝；下一次真实请求的现金/Rights/额度上界未得到充分证明 | **BLOCKED**；静态 GET/HTTP 200 不能替代真人 Web |
| U5 | 需要 U2 同版候选、U3-S、U4 PASS 和逐次有价/真实模型授权 | **未正式进入**；隔离 Planning 实验不是 Web 短片 Debug |
| U6 | 全 Gate 与同版 U3-L 后，从独立新 Web Creation 做真实 MP4、审片/入库 | **未执行，Release 未授权** |

**U3-S 原件证据：**2026-10-12 的 `final.mp4` 经 FFprobe 为 50.000 秒 H.264 1080×1920 + AAC；SHA256 `07024bb66cb601fb144179598f482b4c06d1c1c2d7330f14e9148043c9c2d070`。它验证了内部真实媒体软件链路，但 Planning/Truth/外部素材和人工 Review 在这一 CI 中有合法替身，不得写成真实 Web E1。

## 当前执行焦点（2026-10-15）

**当前 Planning 最终软件基线及新授权（2026-10-15）：**Controlled Loop V1在唯一Owner内软件完成：A-details confirmed-terminal无tool/非法来源受控整批恢复、全Attempt三次Repair/单批二次Regenerate、UNKNOWN不重派、原Capture+新回执和D1/B/D2冷恢复。最终 **53 PASS/0 FAIL**、旧R05原生终态只读核验 PASS，12文件源码/快照SHA12/12一致，manifest `1bd11137372204ee202ce84adb12aa228e6170dfd00426ef284cf0c740a1378c`（`~/.local/share/easel/creator-task-evidence/2026-10-15-planning-controlled-loop-v1-software-r01/`），`@16`为当前新Attempt合同，旧`@15`原件只读。这不是已通过真实MiniMax全链。**用户新增授权执行独立持久化有界MiniMax A→B→Truth→Proof真实调试，区分语义/Loop/代码问题；不重发R05/R06，不运行素材/Build/Web，不部署/提交。**在新的E2E账本顶部记录逐次真实结果、UNKNOWN/预算与终态；U4仍BLOCKED。本段覆盖下方R06旧NEXT。

**最新隔离验证停点（2026-10-15 R06授权续接）：**隔离证据格式已修正且原Secret检查保留，无外网同脚本/原Gateway/Proxy/Budget/原Schema正反预检PASS。唯一新真实Operation `r06-4d6424f95aeb467dbf117dac94e1ff86` 已HTTP200/SSE DONE、原生ok/无Pending，返回1条工具调用和8,299字节原参数；但严格Schema在slot_004两条Claim的creative_goal_ref拒绝非法enum，**BLOCKED_OR_UNKNOWN（确认终结，非HTTP UNKNOWN），A-details-001未合法恢复**。第二次仅允许stop+0tool_calls，故本例真实1/2后停止，Token26,897、隔离恢复1/3，原R05Repair仍0/3、现金UNKNOWN。原R05全部2,802文件及23/23冻结文件SHA一致，生产Owner无Loop且未改。唯一后续是只读评审该非法来源原文与恢复边界；不继续模型调用、不进入U4。实际证据/条件性架构建议见[唯一E2E账本R06](acceptance/easel-v1-web-real-e2e-2026-10-10.md)与[Creator Task](tasks/creator-autonomous-first-cut-2026-09-30.md)。下方R05是此前运行事实，其旧NEXT已由本段覆盖。

**Planning 当前状态（2026-10-15，真实P0-D R05首错停止）：**此前 P0-A/B/C 的唯一Owner受控结构化输出、最多3次共享Repair、双回执/冷恢复软件冻结仍**23/23 SHA与47 PASS/0 FAIL有效**（manifest `4ea6df0db39df39e0fe5579602ce833024f02900d728e64ebb0e1a52575d237e`）；本轮已获用户授权实际执行 P0-D 真实 MiniMax M3.1，在旧成功 R02持久化EvalGateway/Proxy 的独立R05永久环境、封顶16HTTP/0重试内发生 **3次HTTP 200/SSE结束**：A-selection、A-details-000 的工具参数完整且PASS，第三次A-details-001虽HTTP成功，但 `provider_finish=stop`、无 `submit_semantic_plan` 工具参数（`argument_delta_bytes=0`），原代理 `argument_stream_state=INCOMPLETE`、Easel Capture `TRANSPORT_FAILED`；预算已因 `ENTRY_CAPTURE_UNAVAILABLE` 关闭，没有Pending或自动重派，首错停。**共享Repair实际0/3，B/Truth/Plan/D2 Proof均未达到，不能宣称真实全链已过。**当前源码仍23/23冻结一致、R05运行Pin286/286一致，旧R01–R04失败原件不动。唯一下一动作是只读调查已保存R05第三次模型 Tool Choice→SSE工具终态的缺参数原因，提出安全修复；任何R06付费验收另获授权，U4仍BLOCKED/U5-U6未准入。事实详见 [Planning §8.28](tasks/planning-creative-authority-implementation-plan-2026-10-15.md) 及 [唯一E2E账本](acceptance/easel-v1-web-real-e2e-2026-10-10.md)。
## 当前 Production 与 Planning 事实（不是当前调度入口）

- 原 Web Creation `cr_c59c0f598fa0412593f31cbeda934dfb`：Proposal @4 已确认；Delivery `failed`（Planning v3 合同错误），现存 7 个 Attempt。原件和已计额度保留，不自动重试，不把既有 Web 调试作品冒充独立 E1。
- 2026-10-14 隔离真实 MiniMax Planning 批次 `r02`：原 Job `wc_job_M7dcEmbRkeJlJ0tf` 终止，业务 `FAIL`；HTTP 3/3 完成，A-details-002 原 Agent pending、无完整 B/Truth/Plan；259 冻结文件仅 258 匹配，一个测试文件运行中发生变化。**既不证明 B 聚合成功/失败，也不是 U4/U5 的额外准入条件。**保全原 run/session/占额，绝不重派或清零；按用户最新要求不把单独修 r02 等待问题设为主任务。
- 已发生的完整 Planning 诊断/局部 PASS、模型 reported tokens 和历史 UNKNOWN 仅属原运行证据；不以独立“十例至少八例成功”替代 U5 的真实 Web 作品验收。真实 Web 首个阻塞才触发定点合同修复。

## 当前 Git / 文档保全状态

- Mac 工作区 `/Users/xgx/Projects/Easel`，分支 `easel-studio`，已提交基线 `990feb439bc7af58d7c7b85c6ec12780f5920d53`。当前提交前的 219 项（93 修改、121 删除、5 未跟踪）已并入该本地 Git 提交；旧 Skill/Web 退役的删除不可因清洁 Git 而回滚，新 Planning 源码和四份测试夹具不可盲删。
- **整理前原件完整快照（本机私有）**：`/Users/xgx/.local/share/easel/creator-task-evidence/2026-10-14-workspace-docs-consolidation-r01/`；包括 `manifest-before.json`、`worktree-triage.json`、`working-files-before.tar.gz`、`git-worktree-before.patch.gz`、`before-docs/`。原 Task 和 State 全文、98 项实际文件字节及 121 项待删 Git HEAD blob 身份均已留存，SHA 见[唯一 Creator Task](tasks/creator-autonomous-first-cut-2026-09-30.md)。
- 此前整理仅修改四份文档；本次轻量治理仅清理过期入口并记录测试债，不修改 Creation/Attempt、生产代码、服务、Secret、Rights/账单或素材原件。历史正文从私有归档及具名 Acceptance 查询，旧日期的 `NEXT_SINGLE_ACTION` 不具有调度权。

## NEXT_SINGLE_ACTION（后续业务，需另行授权）

**Planning D0–D4 软件专项已经冻结，当前恢复 U4 无副作用 Web / Runtime / Rights / 权利 / 额度准入。**保留之前已保存的本地地址浏览器权限拒绝，不通过换通道绕过。需要有证据区分同版受控加载、真实 UI 可用性和下一请求费用/权益后，才能申请 U5 的正式 Web Creation/confirm_production 短片 Debug。Planning 在该 Web 生产链中继续；U3-L 可以与合法的 U5 短片工作并行，但 U6 必须等待 U3-L 同版资格通过。

**提交前验证遗留：**New-Only Web/Native/MiniMax 核心专项 88 PASS；扩展 Structured Result 123 PASS / 4 FAIL。四项属于安装 OpenClaw Runtime 指纹/本地 SDK 差异（2 项）、历史 source-scope 提示词实验漂移（1 项）、旧 Proposal 夹具与当前验证冲突（1 项）。保持 FAIL 原样，尚未证实属于当前产品缺陷；不能记为全绿，也不因此阻断无关文档治理。

**后续权限：**U4/U5/付费、部署和 Release 仍受主方案与另行授权约束；工作区整理完成不产生任何新的生产许可。


### 2026-10-16 用户暂停停点（覆盖此前 NEXT）

用户明确要求“先暂停”，已停止离线测试，不再派发 HTTP/新 Attempt。新增授权已用 16/60 HTTP（R12=1、R13=15），全部 RESPONSE_COMPLETE，无 Pending/UNKNOWN；剩余44次保留，须用户恢复后才执行。旧29/30账本保持关闭。

R13 `fa_91f768503236ec8cc8260239f0ce2323`：A-selection/A-details通过（原 Owner Repair 1/3），10批B原件已收齐；汇总 Repair 请求1,172,075字节，超过未变的1 MiB上限，在派发前严格拒绝。Truth、D2 Proof、Cold Verify及PLANNING_ACCEPTED未通过。

当前未完成修改：request_view @3 将重复 evidence_choices_by_target 完整表纳入原有无损上下文引用，journal @19；R13真实原件离线回放847,290字节、R11回放697,779字节，恢复原文严格相等，Tool Schema未变。最新回归因用户暂停中断，36 PASS/1 FAIL；FAIL为测试期望4个目录项、实际3个（待核实测试数据是否达到512字符去重阈值），不得记为验证完成，不得将当前版本用于真实派发。此前@2版本54 PASS不代表@3验证完成。未修改合同或容量，不新建Agent，无Git/制作/部署动作。

RESULT=PARTIAL；DRIFT=NO_DRIFT；EVIDENCE=真实调用16次全部终态、Repair容量离线回放通过但最新回归未完成；LESSON=相同目标证据选项表也是大请求重复来源；NEXT_SINGLE_ACTION=用户恢复后先核实并修复定向回归，再完成离线验证，之后才允许新Attempt；TRANSITION=HOLD（解除条件：用户明确恢复且当前修改离线回归通过）。
