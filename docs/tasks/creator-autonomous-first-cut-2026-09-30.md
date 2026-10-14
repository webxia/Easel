
# Easel V1 自主首版与 Director 全链执行：唯一实施 Task

> **CURRENT / 2026-10-14 唯一短调度入口。** 本 Task 仍是唯一 Owner/授权入口，不是新 Goal。旧 Task **3006 行、666,099 字节**的未提交全文（原 r02 Closure、全部 81 处 NEXT、设计/实现授权历史）已于本次压缩前完整快照，原文 SHA 可核。归档段落保留事实和决策发生时的历史状态，但**旧 NEXT/“最新停点”不再调度当前任务**。

## 目标及唯一合同

Easel V1 要让一个 Creator/Profile + 一个 Director/Creative Mode，在不同 Content 下通过 **真实 Easel Web Creation → Proposal @4 明确确认 → Preparation → Planning/Truth → Material V1.3 / Rights / MATERIAL_READY → Native Authoring → Hypit Check/Pricing/Build/Export → Technical QC / System Quality READY → 人工 Review/Selection/Content Library**，生成可播放、可审阅的首版视频，不自动发布。

**唯一已批准生产标准**：[New-Only → Web E2E R1–R6 / U0–U6 第 8 章](../architecture/web-backend-new-only-cutover-plan-2026-10-11.md)。首条正式 U5 Debug 选择一个现有 Creator + Creative Mode，通过 Web 新 Creation 做 **45–60 秒 / 9:16 / 中文 Voice+BGM** 视频；不恢复旧视频 Producer/Writer、旧 Skill/Chat/CLI 制作旁路、旧 Attempt 的主动恢复，不能以 API/CLI/数据库伪造 Web。Material V1.3 / ADR-004 冻结；Material 只消费导演语义，不决定导演风格；新生产五 pin 与所有硬 Need/源文件 SHA/权利/费用/UNKNOWN 边界必须守住。

## 现行阶段、下一动作

| 关口 | 已证实阶段事实 |
|---|---|
| U1 | 2026-10-11 标准批准 PASS |
| U2 | New-Only 唯一候选于 2026-10-12 达到 CANDIDATE_READY/受控加载；后续源码变化需重新对齐同版指纹，旧 PASS 不是生产发布 |
| U3-S | **PASS**：合法固定外部回执 + 真实内部 Owner/Material/Hypit 生成 50 秒 MP4 并通过软件 Quality/冷恢复；非真实 Web E1 |
| U3-L | 尚无正式长片资格 PASS；真实 301–900 秒 BGM 原件、Voice/ASR/最长 MP4 和资源/四模式的联合证据是 U6 硬前置，可与合法 U5 短片 Debug 并行 |
| **U4** | **BLOCKED**：保存的浏览器权限拒绝，费用/权利/未决操作准入没有达到正式 Web Gate；它是当前主线停点 |
| U5 / U6 | 尚未正式放行/执行；不能把 Planning 隔离评测算成真实 Web Debug，也不能用旧作品阶段结果拼成 U6 |

**NEXT_SINGLE_ACTION（未来业务）：**待用户另行授权后，先继续 **U4 无副作用 Web 准入**：确认实际 Easel 页面、New-Only 候选 Web/Backend/Skill/Gateway/Hypit 加载指纹、当前 Creation 的只读进度/错误与原操作状态，以及对应 Rights/额度/现金上界。以前保存的浏览器访问拒绝不能换通道绕过。**满足 U4、U2 同版、U3-S 和逐次真实调用授权后才能进入 U5 新 Web Creation 的单条短片 Debug。**

**Planning 继续作为 U5 Web Delivery 必经步骤**，但独立 `10 个完整样本至少 8 个成功` 的稳定性批次不作为 U5 额外 Gate；按真实 Web 作品的首个明确失败关口定点修复。不独立扩散 Schema/token/batch 实验，不把 r02 单次原生等待症状作为普遍整改任务。

## 安全与执行权限

- 现存生产 Web Creation `cr_c59c0f598fa0412593f31cbeda934dfb` 已确认 Proposal @4，但 Delivery 在 Planning v3 合同阶段 failed，原 7 个 Attempt 按身份保护，不自动续跑/重派。历史原 Creator/Attempt/响应/资产/媒体、Rights、费用及 ¥10 历史共享额度的适用边界不因新 Creation 自动刷新。
- 隔离 `r02` 原 Job `wc_job_M7dcEmbRkeJlJ0tf` 已终止但业务 FAIL：3/3 HTTP 完整；A-details-002 仍持有原 `run_id/session_id` 的 pending 证据，B/Truth/Plan 未到达，259 冻结文件中测试文件发生中途变化。保全所有请求/UNKNOWN/模型费用证据；不重派、不把此结果声明成模型语义故障或 B 聚合失败。按本轮用户要求，不为该等待现场另开独立专项。
- 合法 `PENDING/SUBMITTING/UNKNOWN` 只能按**原 operation** 被动观察，绝不重派/删账/清零；真实 Provider/TTS/有价 Hypit Build、正式 Web 制作、服务重启/部署与 Release 必须按阶段 Gate 获得单独授权，不能借历史模型套餐说明、报价或已有 Credential 假设零现金。
- MaterialPlan → Supply → Bundle → Readiness → MATERIAL_READY；Creator 冻结意图、版权与真实素材、Script/Truth、Native Authoring/Cost、同一视频 Output SHA、Technical/System Quality 与人工 Review 不能靠自动字段补齐或降低必需标准。未经 U3-L 验证的长片有价执行 fail-closed；不自动发布。
- 本轮用户**只授权工作区/文档整理第 1–3 项**，完成后立即暂停：禁止触发真实模型、Provider、Web `confirm_production`、Hypit Build、生产运行状态变更、Git stage/commit/push、修改源代码/测试或清理历史素材。

## 当前代码与记录入口

- 正式标准：[唯一 New-Only 主方案](../architecture/web-backend-new-only-cutover-plan-2026-10-11.md)；最新状态：[Current State](../02_CURRENT_STATE.md)；阶段顺序：[Roadmap](../03_ROADMAP.md)；**所有真实 E2E/软件/费用/失败原始运行证据只归**[唯一 E2E 账本](../acceptance/easel-v1-web-real-e2e-2026-10-10.md)和其具名原件。
- 当前 Web/Delivery 相关实现：`web/app.py`、`web/frontend/src/App.tsx`、`web/frontend/src/components/FilmOperatorPage.tsx`、`easel/creation_delivery.py`；Material/Planning、Hypit/Quality 按实际第一失败关口再读，不默认加载整套 3000 行历史。
- 工作区 `/Users/xgx/Projects/Easel`，分支 `easel-studio`、HEAD `ce6fa81739b812ff6bed8115cabd78bdf548e389`。整理前 219 项 dirty = 93 修改 / 121 删除 / 5 未跟踪；旧视频生产代码退役删除不可随便回滚，新 Planning 文件/四份测试夹具不可盲删。

## 旧全文备份与可恢复性

**独立 Mac 私有只读证据位置**：`/Users/xgx/.local/share/easel/creator-task-evidence/2026-10-14-workspace-docs-consolidation-r01/`。

- `before-docs/creator-autonomous-first-cut-2026-09-30.md`：旧 Task 全文 SHA256 **`b8acdf315c95cda3db000c2ecd3e523f148325233ee3120c5b9985f1254b7254`**。
- `before-docs/02_CURRENT_STATE.md`：旧 State 全文 SHA256 **`6622e59ddacc8f4bcedb6c2978b58bc64479a6841030113325b389969bd6592c`**。
- `working-files-before.tar.gz`：包括 98 项未提交修改/未跟踪实际文件的完整字节；`git-worktree-before.patch.gz`：全部 tracked 差异；`manifest-before.json`：219 个条目、121 个删除的 Git HEAD blob SHA；`worktree-triage.json`：保守保留/待审分类清单。无权据此清理忽略目录、原 Creation、历史 Attempt、素材或 Secret。
- 本次精简**不改变原历史 RUN/PASS/FAIL、授权变更及原始 SHA**。查询旧决定请在归档按日期和实际任务原文回查，不能恢复其中过时的调度命令或创建第二个 Task。

## 文档整理 Closure（只对本轮 1–3 项）

`RESULT = COMPLETE`（仅工作区备份、状态/路由对齐、当前 Task 压缩；**Easel 产品仍 U4 BLOCKED，U3-L 未通过，U5/U6 未执行**）。

`DRIFT = NO_PRODUCT_CHANGE`（只调整 4 份活跃 Markdown；219 项 Git 状态集合、原生产代码/测试、历史运行文件与 Secret 不变；全量工作区原字节另有 SHA 归档）。

`EVIDENCE = 219 项 Git 分类 + 98 份修改/未跟踪文件字节备份 + 121 个 Git 原删除身份 + 历史 Task/State SHA + U2/U3/U4 具名验收证据`。

`LESSON = 保留历史证据但不能让旧 Closure/NEXT 持续抢当前 Web 主线的执行权；Planning 局部验收与正式 U5 Web E2E 必须区分。`

`NEXT_SINGLE_ACTION = 本轮整理完成即停，继续由用户审阅。随后根据另行许可，先处理 U4 无副作用 Web 预检，而不是从旧 Planning 稳定性批次恢复调度。`

`TRANSITION = HOLD`（文档整理闭合，不自动放行 U4/U5/U6 的浏览器/真实模型/付费/部署/Release）。
