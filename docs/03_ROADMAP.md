# Easel Roadmap

> **当前有效进度（2026-10-14）：**已批准 New-Only U0–U6 唯一标准；**U2_CANDIDATE_READY（2026-10-12 原指纹）/ U3-S=PASS / U4=BLOCKED / U3-L 尚未正式取得 900 秒资格 / U5-U6 未执行 / RELEASE_NOT_AUTHORIZED**。当前 Git 已在 `990feb43` 本地提交，受测 U2 候选仍须重新核对加载指纹；这不是新的 U4/U5 验收或授权。
>
> **唯一业务下一动作：**在单独授权和安全条件满足后继续 **U4 无副作用 Web 页面、Runtime 同版、Rights/预算/UNKNOWN 准入**；成功后才能启动 U5 单条真实 Web Creation 短片 Debug。Planning 随 U5 Web Delivery 执行，独立十样本稳定性批次不构成 U5 额外前置。U3-L 可与合规短片 Debug 并行，U6 必须等待同版 U3-L PASS。实际阶段事实见[Current State](02_CURRENT_STATE.md)，原运行证据见[E2E 账本](acceptance/easel-v1-web-real-e2e-2026-10-10.md)。

## 当前已批准的唯一实施顺序（U2 候选不等于 Release）

依次执行：U0 → U1 → U2 → U3-S 与 U4 → U5（可并行 U3-L）→ U3-L 同版 PASS 后 U6。准入、授权及 STOP 条件只按[唯一 New-Only 主方案](architecture/web-backend-new-only-cutover-plan-2026-10-11.md)第 8 章，不在本页自设第二套标准。
## 2026-10-11 历史阶段安排（以下是旧阶段语境，不再独立调度）

此前 ADR-005、OpenClaw O1、P0-A/P0-B、P1/P2/P3 的阶段叙述现统一映射到[唯一 New-Only 第 8 章](architecture/web-backend-new-only-cutover-plan-2026-10-11.md) U0–U6。历史实施事实不改写，旧报错和原媒体仍在[E2E 账本](acceptance/easel-v1-web-real-e2e-2026-10-10.md)及整理前完整文档备份中；不要从旧阶段清单再启动 Planning 压力测试、重试原 Attempt 或恢复旧生产入口。U3-S 已通过软件阶段，U4 是尚未通过的真实 Web 前置，U3-L 为 U6 长片资格。
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

**状态：`U7_BACKLOG / NOT_STARTED / NO_CODE_CHANGE`。** U7 是**后续优化任务标签，不是现在已批准的第七个 Gate**；不改变正式 U0–U6、U4→U5、U3-L→U6 的实施/授权次序，不宣称已验证，也不授权真实模型、Provider、Build、部署或新代码改造。本轮仅记录并本地 Git 提交，未来另行启动。## 稳定架构

- [正式 Creation + Hypit](decisions/ADR-001-creation-hypit-mainline.md)
- [Material Layer V1.3](architecture/material-layer-v1.3.md) 和 [ADR-004](decisions/ADR-004-material-layer-v1.3-baseline.md)
- [Agent 结果处理 ADR-005](decisions/ADR-005-agent-result-processing.md)
