# 二开文档整理与审核记录 · 2026-10-23

范围：只整理本次开始时docs/v2、已批准的开发调试整合研究及根AGENTS。官方文档/产品创作指令、代码、测试、脚本、用户材料及独立导演预研未修改。未改分支/HEAD，未提交、推送、重载、迁库或运行真实制作。

## 分类与唯一权威

[主线导航](../INDEX.md)按产品、架构、配置、开发规范、项目执行、历史分类。V2/S6/S7保留为需求/任务/历史标识，主线不等于官方Git main。旧路径仅跳转，原图片保留兼容；历史快照有明确标记，不继续维护当前状态。正式运行日志保留原轮次和判定。

## 经验覆盖核对

| 经验/约束 | 原来源 | 当前维护位置 | 核对 |
|---|---|---|---|
| 功能/Bug统一分析设计实施回归；风险决定分析深度 | 工程§2.1，研究D1 | [工程§2](../development/engineering.md) | 原规则完整迁入 |
| 同一授权持续推进、无统一工程修复次数；无新证据不盲修 | 工程§2.3，研究D5 | [工程](../development/engineering.md) | 保留产品次数/费用边界 |
| 实质指令差异先给出处、影响、方案和明确决策 | 根AGENTS，研究D6 | 根AGENTS＋[工程](../development/engineering.md) | 同范围可逆工作不反复请示 |
| DEBUG与固定版本ACCEPTANCE、G0～G6、首次失败保留 | E2E README，研究D2/D7 | [调试规范](../development/testing.md) | 全部判据保留 |
| 原Task承接Bug、修复后返回父任务；旧结案不重开 | 工程§2.2，研究D3/H5 | [工程](../development/engineering.md)＋[任务衔接](../development/task-handoff.md) | 原目标与剩余验收保留 |
| HEAD/Dirty/构建/进程/授权/最后副作用/UNKNOWN/合法恢复/唯一下步 | E2E§六、Task模板 | [E2E](../development/testing.md)＋[Task模板](../development/templates/TASK.md) | 跨窗口检查点字段保留 |
| HTTP或模型成功≠合法Plan；口头同意≠正式确认 | 研究H2/H3、G2/G3 | [E2E](../development/testing.md)及原轮次 | 首次失败和原判定保留 |
| 素材发现/下载/Rights/用途/绑定分开；可选音效降级由用户决定 | 研究H3/H4 | [素材职责](../architecture/materials.md)、[合同](../architecture/contracts.md)及原轮次 | 不把候选当合格资产 |
| 短SFX适配、补料持久引用、FFmpeg首因与局部恢复 | 研究H2/H4 | [历史案例§7](research/development-debugging-task-integration-2026-10-23.md#七历史经验把实际踩过的坑转成规范约束)及原轮次 | 完整案例保留，不升格通用容差 |
| HTTP500/大请求/length不明因果；UNKNOWN不重发 | 研究H3，E2E§四/五 | [调试规范](../development/testing.md)及原回执来源 | 事实与假设分开 |
| 浏览器/工具中断≠业务未执行，合法恢复原Work | 研究H2，E2E§五 | [调试规范](../development/testing.md) | 禁SQL造状态、复制凭证、API冒充Web |
| 软件/部署/技术/语义/生产/自主/Creator分别取证 | 工程§5，研究D7/H1～H5 | [工程](../development/engineering.md)＋[E2E](../development/testing.md) | 不拼零散PASS宣称全链路 |
| Codex原生执行，Task≠产品Work，不新增外部控制器 | 研究D4及反例 | [工程](../development/engineering.md)＋[E2E](../development/testing.md) | 实验脚本不改、不作为依赖 |
| 真实依赖、Python/平台矩阵、隔离fixture、零收集不算PASS、CI精确SHA | 任务包原§2 | [任务衔接](../development/task-handoff.md) | 每条共同约定迁入，任务包改引用 |
| 回退保留成果/失败、代码与数据分开、schema备份和向前修复 | 任务包原§2 | [任务衔接](../development/task-handoff.md) | 原有保护保留 |
| Git保护、上游每周/新阶段检查、合入需明确确认、仅自有非保护分支提交 | 根AGENTS、工程§6 | 根AGENTS＋[工程](../development/engineering.md) | S0一次性授权留历史不变常驻授权 |
| 生成优先、审核兜底；阶段分流SAFETY/CURRENT_BLOCKER/LATER/RESEARCH | 根AGENTS | 根AGENTS＋[候选池](../project/backlog.md) | 不新增平行Backlog |
| 完整1～900秒/四声音/输入/画幅/中文/无画像等验收范围 | 需求、任务包§3/8 | [需求](../product/requirements.md)＋[原任务包](../project/tasks/S6_IMPLEMENTATION_PLAN.md) | 原矩阵保留，不拿样片缩范围 |

研究全文和全部具名运行记录保留。以上是迁移核对表，不是第二套执行规则；后续经验在对应权威规范或原Task维护。

## 重复与冲突处理

- 开发流程归工程规范，E2E只维护特殊规则；共同交接从阶段任务包提取，任务包改为链接。
- 当前状态与候选池分开；原状态页尾部观察保留并明确合并评审，历史部署流水归档，不作为当前下一步。
- 配置指南剔除旧双Agent安装步骤，以源码的main / main-pipeline-v1 / protocol2为当前装配；旧方案保留历史。
- 当前原生session namespace核对为agent:main:easel-pipeline，不能沿用旧easel-video标识。
- 领域设计的旧SHA标为历史取证，实际源码以实现导读的HEAD＋Dirty及当前状态为准。合同中的历史部署结论显式标记，不代替当前验收。
- 旧阶段路线不再要求重跑S0～S5。历史Task编号、需求ID、失败判定、费用与UNKNOWN保护不重写。
- 修正三处历史路径标记问题：文件列表分开、外部日志子目录按文字描述、旧HTTP构建资源标为历史名称；未改变运行事实。

## 文件去向

- docs/v2/03_ROADMAP.md → [project/roadmap.md](../project/roadmap.md)
- docs/v2/18_MATERIAL_LAYER_ARCHITECTURE.md → [architecture/materials.md](../architecture/materials.md)
- docs/v2/19_MATERIAL_LAYER_G4_ACCEPTANCE.md → [history/v2/19_MATERIAL_LAYER_G4_ACCEPTANCE.md](v2/19_MATERIAL_LAYER_G4_ACCEPTANCE.md)
- docs/v2/05_ENGINEERING.md → [development/engineering.md](../development/engineering.md)
- docs/v2/15_IMPLEMENTATION_DESIGN.md → [architecture/contracts.md](../architecture/contracts.md)
- docs/v2/01_REQUIREMENTS.md → [product/requirements.md](../product/requirements.md)
- docs/v2/21_SYSTEM_ARCHITECTURE.md → [architecture/overview.md](../architecture/overview.md)
- docs/v2/02_ARCHITECTURE.md → [architecture/domain.md](../architecture/domain.md)
- docs/v2/20_CONVERSATIONAL_INTERACTION.md → [history/v2/20_CONVERSATIONAL_INTERACTION.md](v2/20_CONVERSATIONAL_INTERACTION.md)
- docs/v2/INDEX.md → [INDEX.md](../INDEX.md)
- docs/v2/13_PRODUCTION_WALKTHROUGH.md → [history/v2/13_PRODUCTION_WALKTHROUGH.md](v2/13_PRODUCTION_WALKTHROUGH.md)
- docs/v2/16_RUNTIME_SETUP.md → [history/v2/16_RUNTIME_SETUP.md](v2/16_RUNTIME_SETUP.md)
- docs/v2/00_VISION.md → [product/overview.md](../product/overview.md)
- docs/v2/11_REQUIREMENT_GAP_MAP.md → [history/v2/11_REQUIREMENT_GAP_MAP.md](v2/11_REQUIREMENT_GAP_MAP.md)
- docs/v2/12_PRODUCTION_FLOW_RESEARCH.md → [history/v2/12_PRODUCTION_FLOW_RESEARCH.md](v2/12_PRODUCTION_FLOW_RESEARCH.md)
- docs/v2/04_CURRENT_STATE.md → [project/status.md](../project/status.md)
- docs/v2/14_TECHNOLOGY_SELECTION.md → [history/v2/14_TECHNOLOGY_SELECTION.md](v2/14_TECHNOLOGY_SELECTION.md)
- docs/v2/17_MATERIAL_LAYER_AUDIT.md → [history/v2/17_MATERIAL_LAYER_AUDIT.md](v2/17_MATERIAL_LAYER_AUDIT.md)
- docs/v2/tasks/S6-13_channels-directors.md → [history/tasks/S6-13_channels-directors.md](tasks/S6-13_channels-directors.md)
- docs/v2/tasks/S6-01_domain-store.md → [history/tasks/S6-01_domain-store.md](tasks/S6-01_domain-store.md)
- docs/v2/tasks/S6-08_model-tasks.md → [history/tasks/S6-08_model-tasks.md](tasks/S6-08_model-tasks.md)
- docs/v2/tasks/S6_IMPLEMENTATION_PLAN.md → [project/tasks/S6_IMPLEMENTATION_PLAN.md](../project/tasks/S6_IMPLEMENTATION_PLAN.md)
- docs/v2/tasks/S6-05_progress-ui.md → [history/tasks/S6-05_progress-ui.md](tasks/S6-05_progress-ui.md)
- docs/v2/tasks/S6-07_material-supply.md → [history/tasks/S6-07_material-supply.md](tasks/S6-07_material-supply.md)
- docs/v2/tasks/S6-15_material-layer-hardening.md → [history/tasks/S6-15_material-layer-hardening.md](tasks/S6-15_material-layer-hardening.md)
- docs/v2/tasks/S6-06_materials-core.md → [history/tasks/S6-06_materials-core.md](tasks/S6-06_materials-core.md)
- docs/v2/tasks/S6-14A_conversation-integration.md → [project/tasks/S6-14A_conversation-integration.md](../project/tasks/S6-14A_conversation-integration.md)
- docs/v2/tasks/S6-10_voice-subtitles.md → [history/tasks/S6-10_voice-subtitles.md](tasks/S6-10_voice-subtitles.md)
- docs/v2/tasks/S6-09_editor-adapter.md → [history/tasks/S6-09_editor-adapter.md](tasks/S6-09_editor-adapter.md)
- docs/v2/tasks/S6-02_work-api.md → [history/tasks/S6-02_work-api.md](tasks/S6-02_work-api.md)
- docs/v2/tasks/S5_VALIDATION_PLAN.md → [history/tasks/S5_VALIDATION_PLAN.md](tasks/S5_VALIDATION_PLAN.md)
- docs/v2/tasks/S6-04_worker-graph.md → [history/tasks/S6-04_worker-graph.md](tasks/S6-04_worker-graph.md)
- docs/v2/tasks/S6-03_operations.md → [history/tasks/S6-03_operations.md](tasks/S6-03_operations.md)
- docs/v2/tasks/S6-12_revision-acceptance.md → [history/tasks/S6-12_revision-acceptance.md](tasks/S6-12_revision-acceptance.md)
- docs/v2/tasks/S6-14_integration-release.md → [project/tasks/S6-14_integration-release.md](../project/tasks/S6-14_integration-release.md)
- docs/v2/tasks/S5_ARCHITECTURE.md → [history/tasks/S5_ARCHITECTURE.md](tasks/S5_ARCHITECTURE.md)
- docs/v2/tasks/S6-11_creation-first-cut.md → [history/tasks/S6-11_creation-first-cut.md](tasks/S6-11_creation-first-cut.md)
- docs/v2/evidence/S6-14A_A7_validation.json → [history/v2/evidence/S6-14A_A7_validation.json](v2/evidence/S6-14A_A7_validation.json)
- docs/v2/evidence/S6-14A_A8_validation.json → [history/v2/evidence/S6-14A_A8_validation.json](v2/evidence/S6-14A_A8_validation.json)
- docs/v2/evidence/S6-14A_A3_channel-browser.png → [history/v2/evidence/S6-14A_A3_channel-browser.png](v2/evidence/S6-14A_A3_channel-browser.png)
- docs/v2/evidence/S6-14A_A1_openclaw_probe.json → [history/v2/evidence/S6-14A_A1_openclaw_probe.json](v2/evidence/S6-14A_A1_openclaw_probe.json)
- docs/v2/evidence/S6-14A_A2-A4_validation.json → [history/v2/evidence/S6-14A_A2-A4_validation.json](v2/evidence/S6-14A_A2-A4_validation.json)
- docs/v2/evidence/S6-14A_A5_review-browser.png → [history/v2/evidence/S6-14A_A5_review-browser.png](v2/evidence/S6-14A_A5_review-browser.png)
- docs/v2/evidence/S6-14A_A5_library-browser.png → [history/v2/evidence/S6-14A_A5_library-browser.png](v2/evidence/S6-14A_A5_library-browser.png)
- docs/v2/evidence/S6-14A_A6_chat-pipelines.png → [history/v2/evidence/S6-14A_A6_chat-pipelines.png](v2/evidence/S6-14A_A6_chat-pipelines.png)
- docs/v2/evidence/S6-14A_A6_pending-browser.png → [history/v2/evidence/S6-14A_A6_pending-browser.png](v2/evidence/S6-14A_A6_pending-browser.png)
- docs/v2/evidence/S6-14A_A5_validation.json → [history/v2/evidence/S6-14A_A5_validation.json](v2/evidence/S6-14A_A5_validation.json)
- docs/v2/evidence/S6-14A_A5_learning-browser.png → [history/v2/evidence/S6-14A_A5_learning-browser.png](v2/evidence/S6-14A_A5_learning-browser.png)
- docs/v2/evidence/S6-14A_A6_chat-entry.json → [history/v2/evidence/S6-14A_A6_chat-entry.json](v2/evidence/S6-14A_A6_chat-entry.json)
- docs/v2/diagrams/s6-14a-completion-loop.png → [history/v2/diagrams/s6-14a-completion-loop.png](v2/diagrams/s6-14a-completion-loop.png)
- docs/v2/diagrams/s6-14a-completion-loop.svg → [history/v2/diagrams/s6-14a-completion-loop.svg](v2/diagrams/s6-14a-completion-loop.svg)
- docs/v2/diagrams/s6-14a-creation-flows.png → [history/v2/diagrams/s6-14a-creation-flows.png](v2/diagrams/s6-14a-creation-flows.png)
- docs/v2/diagrams/s6-14a-entry-loop.png → [history/v2/diagrams/s6-14a-entry-loop.png](v2/diagrams/s6-14a-entry-loop.png)
- docs/v2/diagrams/s6-14a-interaction-storyboard.svg → [history/v2/diagrams/s6-14a-interaction-storyboard.svg](v2/diagrams/s6-14a-interaction-storyboard.svg)
- docs/v2/diagrams/s6-14a-conversation-flow.svg → [history/v2/diagrams/s6-14a-conversation-flow.svg](v2/diagrams/s6-14a-conversation-flow.svg)
- docs/v2/diagrams/s6-14a-conversation-flow.png → [history/v2/diagrams/s6-14a-conversation-flow.png](v2/diagrams/s6-14a-conversation-flow.png)
- docs/v2/diagrams/s6-14a-interaction-storyboard.png → [history/v2/diagrams/s6-14a-interaction-storyboard.png](v2/diagrams/s6-14a-interaction-storyboard.png)
- docs/v2/diagrams/s6-14a-entry-loop.svg → [history/v2/diagrams/s6-14a-entry-loop.svg](v2/diagrams/s6-14a-entry-loop.svg)
- docs/v2/diagrams/s6-14a-creation-flows.svg → [history/v2/diagrams/s6-14a-creation-flows.svg](v2/diagrams/s6-14a-creation-flows.svg)
- docs/v2/decisions/ADR-S6-009-local-editor.md → [architecture/decisions/ADR-S6-009-local-editor.md](../architecture/decisions/ADR-S6-009-local-editor.md)
- docs/v2/decisions/ADR-S5-001-work-production-boundary.md → [architecture/decisions/ADR-S5-001-work-production-boundary.md](../architecture/decisions/ADR-S5-001-work-production-boundary.md)
- docs/v2/templates/TASK.md → [development/templates/TASK.md](../development/templates/TASK.md)
- docs/v2/templates/ADR.md → [development/templates/ADR.md](../development/templates/ADR.md)
- docs/v2/tasks/e2e-runs/2026-10-23-backend-api-01.md → [project/tasks/runs/2026-10-23-backend-api-01.md](../project/tasks/runs/2026-10-23-backend-api-01.md)
- docs/v2/tasks/e2e-runs/2026-10-20-web-e2e-05.md → [project/tasks/runs/2026-10-20-web-e2e-05.md](../project/tasks/runs/2026-10-20-web-e2e-05.md)
- docs/v2/tasks/e2e-runs/2026-10-21-web-e2e-06.md → [project/tasks/runs/2026-10-21-web-e2e-06.md](../project/tasks/runs/2026-10-21-web-e2e-06.md)
- docs/v2/tasks/e2e-runs/2026-10-20-web-e2e-01.md → [project/tasks/runs/2026-10-20-web-e2e-01.md](../project/tasks/runs/2026-10-20-web-e2e-01.md)
- docs/v2/tasks/e2e-runs/2026-10-21-web-e2e-02.md → [project/tasks/runs/2026-10-21-web-e2e-02.md](../project/tasks/runs/2026-10-21-web-e2e-02.md)
- docs/v2/tasks/e2e-runs/2026-10-22-web-e2e-03.md → [project/tasks/runs/2026-10-22-web-e2e-03.md](../project/tasks/runs/2026-10-22-web-e2e-03.md)
- docs/v2/tasks/e2e-runs/2026-10-23-web-e2e-01.md → [project/tasks/runs/2026-10-23-web-e2e-01.md](../project/tasks/runs/2026-10-23-web-e2e-01.md)
- docs/v2/tasks/e2e-runs/2026-10-21-web-e2e-03.md → [project/tasks/runs/2026-10-21-web-e2e-03.md](../project/tasks/runs/2026-10-21-web-e2e-03.md)
- docs/v2/tasks/e2e-runs/2026-10-22-web-e2e-02.md → [project/tasks/runs/2026-10-22-web-e2e-02.md](../project/tasks/runs/2026-10-22-web-e2e-02.md)
- docs/v2/tasks/e2e-runs/2026-10-20-web-e2e-04.md → [project/tasks/runs/2026-10-20-web-e2e-04.md](../project/tasks/runs/2026-10-20-web-e2e-04.md)
- docs/v2/tasks/e2e-runs/README.md → [development/testing.md](../development/testing.md)
- docs/v2/tasks/e2e-runs/2026-10-23-web-e2e-02.md → [project/tasks/runs/2026-10-23-web-e2e-02.md](../project/tasks/runs/2026-10-23-web-e2e-02.md)
- docs/v2/tasks/e2e-runs/2026-10-20-web-e2e-03.md → [project/tasks/runs/2026-10-20-web-e2e-03.md](../project/tasks/runs/2026-10-20-web-e2e-03.md)
- docs/v2/tasks/e2e-runs/2026-10-22-web-e2e-01.md → [project/tasks/runs/2026-10-22-web-e2e-01.md](../project/tasks/runs/2026-10-22-web-e2e-01.md)
- docs/v2/tasks/e2e-runs/2026-10-22-web-e2e-05.md → [project/tasks/runs/2026-10-22-web-e2e-05.md](../project/tasks/runs/2026-10-22-web-e2e-05.md)
- docs/v2/tasks/e2e-runs/2026-10-21-web-e2e-04.md → [project/tasks/runs/2026-10-21-web-e2e-04.md](../project/tasks/runs/2026-10-21-web-e2e-04.md)
- docs/v2/tasks/e2e-runs/2026-10-22-web-e2e-04.md → [project/tasks/runs/2026-10-22-web-e2e-04.md](../project/tasks/runs/2026-10-22-web-e2e-04.md)
- docs/v2/tasks/e2e-runs/2026-10-21-web-e2e-05.md → [project/tasks/runs/2026-10-21-web-e2e-05.md](../project/tasks/runs/2026-10-21-web-e2e-05.md)
- docs/v2/tasks/e2e-runs/2026-10-20-web-e2e-02.md → [project/tasks/runs/2026-10-20-web-e2e-02.md](../project/tasks/runs/2026-10-20-web-e2e-02.md)
- docs/v2/tasks/e2e-runs/2026-10-21-web-e2e-01.md → [project/tasks/runs/2026-10-21-web-e2e-01.md](../project/tasks/runs/2026-10-21-web-e2e-01.md)
- docs/research/development-debugging-task-integration-2026-10-23.md → [history/research/development-debugging-task-integration-2026-10-23.md](research/development-debugging-task-integration-2026-10-23.md)

## 最终检查结果

- 迁移范围路径检查：137 份文档、1905 处引用，0错误；章节锚点专项核对0错误。
- E2E特殊规则逐文对照（仅标题、链接与记录目录调整），完整一致；已批准整合研究逐行内容覆盖通过，H1～H5及反例全部保留。
- 官方资料及范围外代码/测试/脚本/独立预研等1279个文件哈希对照，无变化。原HEAD与分支未改。
- 全库路径检查仍有4处原有错误，均在未修改的独立导演预研：缺少docx及三个旧路径。未伪造目标文件，也未把全库检查报告为通过。
- 本轮只验证文档结构、引用、保留范围与一致性；未运行产品测试、付费制作或部署验收，不新增SOFTWARE_PASS/REAL_PRODUCTION_PASS结论。

## 第二轮整体审核（同日，用户追加要求）

首轮检查说明内容和链接被保留，但不能单靠路径通过证明规范没有语义冲突。本轮复查根入口、产品/架构/配置、开发规范、活动任务及原经验来源，直接修正以下问题：

| 发现 | 修正与当前维护位置 |
|---|---|
| 工程、交接、模板重复定义开发流程、Bug归属和授权 | [工程规范](../development/engineering.md)保留流程；[任务衔接](../development/task-handoff.md)只保留检查清单、证据与回退；模板引用规则并补父任务剩余验收字段 |
| S6专用测试目录和旧Python矩阵被写成全仓常驻要求 | 测试随负责模块现有布局，版本/平台按当前项目声明与CI核对；不丢隔离fixture、零收集/全skip、缺服务明确不可用等经验 |
| 历史经验保存了，但日常调试入口缺具体诊断提示 | [E2E§七](../development/testing.md#七历史经验的诊断落点)补H1～H5对应的投影、Plan确认、素材资格、短SFX/持久引用、HTTP500因果和样本边界；仅作诊断提示，不加Gate或重试额度 |
| 长等待回传成功容易被当成出片成功 | 关联复验02，区分等待退场、业务结果回传和可播放成片，不把具名耗时变成永久测试期限 |
| CREATOR_ACCEPTED定义包含“审阅/反馈”；G0/G4无条件要求画像/配音 | 明确必须接受具体输出版本；提出修改不算接受。E2E按合法输入/声音模式检查适用项，不改变产品授权与质量要求 |
| 活动卡顶部旧“停止/暂停”及旧工作分支仍像当前指令 | 标注轮次阅读边界，原事实不改；当前以状态与本次用户指令为准，旧一次性提交许可不扩大 |
| 自然表达合同夹带旧测试数量、暂停制作和禁止演绎/编码扩展的阶段范围 | 实施/探针结果回链原Task与归档；保留规则快照、角色装配、投影、缓存及UNKNOWN合同，后续演绎/编码遵守已批准的末节合同 |
| 素材设计仍列“待实施”、旧不可修改文件清单；需求页旧授权像全局禁令 | 区分职责、历史备选、具名验收；文件范围和只设计授权仅属原Task，不限制后续已授权工作 |
| 状态页保留“本次修正3张卡”的旧操作叙述 | 删除该过时整理进展，原来源仍在历史快照，不修改实际生产断点 |

原经验H1～H5与反例的完整历史原文、运行判定、任务编号未删改。短SFX/FFmpeg案例不升级为全局容差；不拼不同版本PASS、不复活旧任务、固定版本独立验收、同范围持续修复、UNKNOWN不盲重发、合法原场景恢复、父任务余下验收等均保留。历史归档和旧路径别名属于追溯副本，不是平行规范。

验证：范围内路径和章节锚点检查无错误，git diff --check通过；1266个范围外已跟踪文件哈希无变化，包含官方文档与现有代码。全库仍仅有独立导演预研中的4处既有失效引用。未改官方文档、代码或部署，未执行产品/真实制作验收，未提交或推送。本轮检查结论仅针对可读取文档与现有经验来源，不宣称重新验证私有原始回执或全部产品行为。

## 独立预研4处引用收口（同日，用户追加授权）

原4项已核对：Word文件在研究目录及仓库docs中未找到，改为明确的资料缺失说明，不补造文件；另3项是Hypit和OpenMontage外部仓库路径，固定提交页面及正文可读取，改为明确外部来源并保留原链接，不创建本地替代文件。研究结论与历史验收不变。全库路径检查现为568份文档/指令、2933处引用通过，git diff --check通过；此前两轮所述4项为当时检查结果，已由本次修正收口。官方文档及产品源码未修改。
