
# Easel Current State

> **唯一当前状态 · 2026-10-14 文档治理收口。** 本文件只保留已核验状态、有效阻塞和下一动作。历史批次不再按日期堆叠；原 300 行/123,518 字节全文已按 SHA 保存在 Mac 私有工作区归档。本次只整理工作区/文档，不是新 Gate 验收。权威规则见[唯一 New-Only U0–U6 主方案](architecture/web-backend-new-only-cutover-plan-2026-10-11.md)，原始产品运行证据见[唯一 E2E 账本](acceptance/easel-v1-web-real-e2e-2026-10-10.md)。

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

## 当前 Production 与 Planning 事实（不是当前调度入口）

- 原 Web Creation `cr_c59c0f598fa0412593f31cbeda934dfb`：Proposal @4 已确认；Delivery `failed`（Planning v3 合同错误），现存 7 个 Attempt。原件和已计额度保留，不自动重试，不把既有 Web 调试作品冒充独立 E1。
- 2026-10-14 隔离真实 MiniMax Planning 批次 `r02`：原 Job `wc_job_M7dcEmbRkeJlJ0tf` 终止，业务 `FAIL`；HTTP 3/3 完成，A-details-002 原 Agent pending、无完整 B/Truth/Plan；259 冻结文件仅 258 匹配，一个测试文件运行中发生变化。**既不证明 B 聚合成功/失败，也不是 U4/U5 的额外准入条件。**保全原 run/session/占额，绝不重派或清零；按用户最新要求不把单独修 r02 等待问题设为主任务。
- 已发生的完整 Planning 诊断/局部 PASS、模型 reported tokens 和历史 UNKNOWN 仅属原运行证据；不以独立“十例至少八例成功”替代 U5 的真实 Web 作品验收。真实 Web 首个阻塞才触发定点合同修复。

## 当前 Git / 文档保全状态

- Mac 工作区 `/Users/xgx/Projects/Easel`，分支 `easel-studio`，HEAD `ce6fa81739b812ff6bed8115cabd78bdf548e389`。整理前 219 dirty = 93 修改、121 删除、5 未跟踪；旧 Skill/Web 退役的删除不可因清洁 Git 而回滚，新 Planning 源码和四份测试夹具不可盲删。
- **整理前原件完整快照（本机私有）**：`/Users/xgx/.local/share/easel/creator-task-evidence/2026-10-14-workspace-docs-consolidation-r01/`；包括 `manifest-before.json`、`worktree-triage.json`、`working-files-before.tar.gz`、`git-worktree-before.patch.gz`、`before-docs/`。原 Task 和 State 全文、98 项实际文件字节及 121 项待删 Git HEAD blob 身份均已留存，SHA 见[唯一 Creator Task](tasks/creator-autonomous-first-cut-2026-09-30.md)。
- 当前操作仅对 `DOCUMENT_INDEX.md`、`02_CURRENT_STATE.md`、`03_ROADMAP.md` 和唯一 Creator Task 做文档整理，不修改已运行的 Creation/Attempt、源码/测试、服务、Secret、Rights/账单或素材原件。历史正文从私有归档及具名 Acceptance 查询，旧日期的 `NEXT_SINGLE_ACTION` 不具有调度权。

## NEXT_SINGLE_ACTION（后续业务，需另行授权）

**先完成 U4 无副作用 Web / Runtime / 权利 / 额度准入。**保留之前已保存的本地地址浏览器权限拒绝，不通过换通道绕过。需要有证据区分同版受控加载、真实 UI 可用性和下一请求费用/权益后，才能申请 U5 的正式 Web Creation/confirm_production 短片 Debug。Planning 在该 Web 生产链中继续；U3-L 可以与合法的 U5 短片工作并行，但 U6 必须等待 U3-L 同版资格通过。

**本轮停止条件：**用户只授权工作区快照、索引/状态/路线图对齐和唯一 Task 精简 1–3 项，完成即停。不因此自动开始 U4/U5、真实模型/Provider、Hypit Build、服务重启、Git commit/push 或 Release。
