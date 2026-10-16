**当前有效Closure（2026-10-16，覆盖此前进行中/暂停NEXT）：**`RESULT=STOPPED / DRIFT=NO_DRIFT / TRANSITION=HOLD（预算耗尽）`。恢复授权44/44HTTP已用完（R14–R19），新额度总60/60关闭；全部HTTP完整、原生released，无Pending/HTTP UNKNOWN。R14真实Repair正文171450字节已派发并回传，容量修复得到真实验证；完整Planning仍NOT_PASS，Truth/D2 Proof/Cold/PLANNING_ACCEPTED未达。期间仅澄清现行资产许可待供应与Creator授权缺失的提示区别，75项离线回归PASS，@21，合同不放宽。最新R19 A全通过、3批B捕获，下一B调用在总额度guard前被拒绝，无第61次远端HTTP。NEXT=停止真实调用；可另行离线调查5次stop零工具结果，任何后续实调需新预算授权。原件/消耗见唯一E2E账本与Planning§8.38。

**当前有效停点（2026-10-16，覆盖历史NEXT）：**输出合同原件离线排查完成；29批225题中51个局部目标，38个原始结构错误、13个领域引用错误，转换前后答案相同。已消除提示题型字段歧义并补音频header排除说明，实际Schema/领域合同未变；52项集成+3项容量回归PASS，Journal/Checkpoint@20。真实调用仍暂停，新增HTTP=0，新额度仍16/60、余44。NEXT=等待用户明确恢复真实调用，完整Planning仍NOT_PASS；详见Planning实施方案§8.36。

# Easel Roadmap

**当前调度（2026-10-15续接）：**已获新增60HTTP／仅现有套餐持续Planning调试授权；Repair输入完整可逆去重54PASS，@18新Attempt R12真实复验中，旧停止NEXT已覆盖。首次完整Planning与冷验证成功即停，仍不进入U4/素材/Build/Web/部署/Git。见[Planning §8.34](tasks/planning-creative-authority-implementation-plan-2026-10-15.md)与[唯一E2E账本](acceptance/easel-v1-web-real-e2e-2026-10-10.md)。

**2026-10-15 最新停点：**Planning真实调试29/30 HTTP后停止，余1次不足新完整Attempt。R09定义冲突已修且52PASS；R11受控恢复及全B回执取得，但Repair请求超过1MiB，完整Planning仍NOT_PASS；无Pending/HTTP UNKNOWN。当前只待用户补充累计预算，再在原Task修复Repair上下文无损表示、离线回放及全新Attempt复验。`RESULT=BLOCKED / TRANSITION=ESCALATE`；旧NEXT失效，U4及素材/Build/部署/Git未获准入。详见[Current State](02_CURRENT_STATE.md)、[Planning §8.33](tasks/planning-creative-authority-implementation-plan-2026-10-15.md)与[唯一E2E账本](acceptance/easel-v1-web-real-e2e-2026-10-10.md)。


> **当前有效进度（2026-10-14）：**已批准 New-Only U0–U6 唯一标准；**U2_CANDIDATE_READY（2026-10-12 原指纹）/ U3-S=PASS / U4=BLOCKED / U3-L 尚未正式取得 900 秒资格 / U5-U6 未执行 / RELEASE_NOT_AUTHORIZED**。当前 Git 已在 `990feb43` 本地提交，受测 U2 候选仍须重新核对加载指纹；这不是新的 U4/U5 验收或授权。
>
> **当前 U4 业务动作（Planning D0–D4 已全部冻结）：**在治理收口及原有授权/安全条件满足后继续 **U4 无副作用 Web 页面、Runtime 同版、Rights/预算/UNKNOWN 准入**；成功后才能启动 U5 单条真实 Web Creation 短片 Debug。Planning 随 U5 Web Delivery 执行，独立十样本稳定性批次不构成 U5 额外前置。U3-L 可与合规短片 Debug 并行，U6 必须等待同版 U3-L PASS。实际阶段事实见[Current State](02_CURRENT_STATE.md)，原运行证据见[E2E 账本](acceptance/easel-v1-web-real-e2e-2026-10-10.md)。

## 当前工作顺序：U4 阶段 Planning 阻塞治理（2026-10-15）

**Planning Controlled Loop V1软件Closure完成：**53PASS/0FAIL、原R05 native终态只读核验PASS、新`@16`协议，12文件SHA快照manifest `1bd11137372204ee202ce84adb12aa228e6170dfd00426ef284cf0c740a1378c`（见[Planning §8.30](tasks/planning-creative-authority-implementation-plan-2026-10-15.md)）。不等同真实MiniMax/P0-D或Web视频验收。**新授权已允许下一步：全新独立Attempt、持久预算下真实MiniMax A→B→Truth→Proof，区分模型语义、受控Loop和生产缺陷，按证据最小修复和新Attempt复验，不重派R01–R06**；达到真实PASS后再评估U4 Runtime/Rights/费用Gate，再到U5/U3-L/U6。当前U4 BLOCKED，素材/Build/发布/部署未授权。

唯一 Creator Task 的 P0-A/B/C **23文件冻结/47 PASS软件基线有效**，但本轮获批P0-D真实 MiniMax M3.1 R05已出现**首个非可恢复 Tool Result 阻断**：HTTP 3/3成功结束并不等于结构化工具参数3/3，A-selection与A-details-000 PASS，A-details-001 `provider_finish=stop`、`argument_delta_bytes=0`、未生成指定 `submit_semantic_plan` Tool Call；原 Run已错误终结且释放，预算 `ENTRY_CAPTURE_UNAVAILABLE` 关闭、Repair未使用（0/3）、B/Truth/Proof未进入。**唯一NEXT：只读审计R05保存的Gateway/Proxy/SSE/模型输出合同终止原因，先评审合法恢复设计；另获授权才可创建独立R06真实测试，绝不重派R05**。后续仍为P0-D真实全链PASS→必要噪音清理→正式U4 Web/Runtime/Rights/费用 Gate→U5短视频/同版U3-L→U6。本轮R05后停止，`TRANSITION=HOLD`，U4=BLOCKED，不自动实施素材/Build。
## 不可改变的边界

- 正式 V1 目标流：Creator/Director/Creative Mode → New-Only Proposal @4 正式确认 → Preparation/Handoff → Planning/Truth → Material V1.3 的 `MaterialPlan → Material Supply → MaterialBundle → MaterialReadiness → MATERIAL_READY` → Native Authoring/Check → Hypit Build/Export → Technical QC/System Quality READY → 人工 Review/Selection/Content Library；新生产不恢复旧 V0.1 执行合同，Creator/Director/Creative Mode、Rights、费用/UNKNOWN 边界不变，且不自动发布。**这是已批准目标，不是当前源码已经实现的声明。**
- 历史 R17 的 **9/9 `MATERIAL_READY`** 仅是旧作品素材恢复，不等于视频交付；广泛 BGM 能力留出/旧 R4 等 FAIL、UNKNOWN 和预算不重新计数。
- 原始规划路线、两窗口软件/BGM任务与连续出片的历史实施细节保存在 [唯一自主出片 Task](tasks/creator-autonomous-first-cut-2026-09-30.md)、[Planning 治理 Task](tasks/planning-material-boundary-matrix-2026-10-06.md)、[耗时/BGM总入口](tasks/creation-latency-2026-10-02.md)及各自 Acceptance；只按需读取。


## U7｜Easel 创作全链路优化（后续 Task Backlog，非 U0–U6 Gate）

**目标：**待 U0–U6 当前交付主线取得真实 Web 出片与验收证据后，对整个 Creator 中心的视频创作链路进行一次端到端的**效率、质量、成本、自动化程度及恢复性**梳理。对象不是只针对 Planning，也不是另建视频生产主链；保持“一套 Creator 人设 + 一个 Director/Creative Mode + 不同内容 → 稳定风格的可审阅视频”。

**范围与待验证问题（先测量、后改造）：**
1. **Web Creation / Creator / Director / Proposal：**主题讨论到确认的交互轮次、上下文冻结与传递、重复确认、无效中断、Creator 人工负担与不同主题的风格一致性。
2. **Preparation / Planning / Truth：**跨阶段上下文重复加载、A-selection/A-details/B Review/Repair/Truth 的响应耗时、Token、结构化结果合法性、语义忠实度、模型路由和推理强度，及 Truth/来源的真实拒绝与恢复。
3. **Material V1.3 / Voice / BGM / Rights：**多 Need 素材复用、观察/匹配/供应重复调用、资源来源与许可、长 BGM 原件、真实语音/ASR/时间轴、缓存失效与 MATERIAL_READY 准入。
4. **Native Authoring / Hypit Check/Plan/Pricing/Build/Export：**素材与导演取舍传递、原生编排质量、构建耗时和峰值资源、重复 Build、防 UNKNOWN 重派、媒体可播放性、SHA 和费用可解释性。
5. **Technical QC / System Quality / Creator Review / Selection / Content Library：**音画、字幕、事实与风格核验，缺陷定位与有界局部修改，人工反馈次数、最终选片及授权范围，作品恢复与复用。
6. **跨阶段：**各阶段 p50/p95 与总端到端耗时、输入/输出/推理 Token、Provider 次数、实际费用与占额、失败率/重试率、恢复成功率、状态/证据可观测性及用户干预次数；找出瓶颈而非平均用力重构。

**第一项已发现的优化假设：Planning 推理强度与输入重复。** 目前实际实现由 OpenClaw 模型路由统一提供推理强度，不支持 A-selection、A-details、B Review、Repair、Truth 分阶段配置；A-details 与 B 多批次保留完整冻结证据并存在上下文重复传递，叠加 `reasoning_effort=max` 可能放大延迟，但尚未证明这是 UNKNOWN 或失败的根因。候选档位：A-selection=`medium`、A-details=`low/medium`、B Review=`medium`、Repair=`low`、Truth=`medium`，**仅为待实验假设**。

**验证路线：**优先在同一冻结版本、输入、Schema 和相同输出上限下，用新身份真实对照整条 Planning `max` 与 `medium`；把推理等级与输出 Token 上限分开控制并记录阶段级响应、Token、合法性及最终完成率。后续再结合真实 Web E2E 的全链遥测，按影响度选择**一类最值得优化的瓶颈**，提出最小改造与回归；任何无损上下文优化均不可删减 Creator/Director/原文/来源/Rights 语义。旧 `PENDING/UNKNOWN` 只对账不重派，切换参数不得变更原 operation 身份或恢复旧请求。

**产出与完成标准（后续启动时再确定规模）：**一份有实际调用链和阶段计时的全链诊断、瓶颈排序、各优化候选的收益/风险/前置依赖、按优先级排序的最小实施计划和对应可复现验收指标；区分“已实测”“假设”“尚未实现”。原则上复用现有 Creator Task、Current State、E2E 账本和架构文档，不新增平行工作流、独立生产标准或海量过程文档。

**状态：`U7_BACKLOG / NOT_STARTED / NO_CODE_CHANGE`。** U7 是**后续优化任务标签，不是现在已批准的第七个 Gate**；不改变正式 U0–U6、U4→U5、U3-L→U6 的实施/授权次序，不宣称已验证，也不授权真实模型、Provider、Build、部署或新代码改造。本轮仅记录并本地 Git 提交，未来另行启动。

## 稳定架构

- [正式 Creation + Hypit](decisions/ADR-001-creation-hypit-mainline.md)
- [Material Layer V1.3](architecture/material-layer-v1.3.md) 和 [ADR-004](decisions/ADR-004-material-layer-v1.3-baseline.md)
- [Agent 结果处理 ADR-005](decisions/ADR-005-agent-result-processing.md)
