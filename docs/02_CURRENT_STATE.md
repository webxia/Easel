# Easel Current State

> **更新：2026-10-10｜唯一当前状态入口。** 本文只写仍然有效的实现、证据和下一步。原 1,403 行阶段流水与全部历史判断已保留在已推送的 Git 提交 `a6ed065d72b66e5dcdf886a90eb5b36fac971acf` 的 `docs/02_CURRENT_STATE.md`；需追溯时执行 `git show a6ed065d:docs/02_CURRENT_STATE.md`。历史 FAIL/UNKNOWN、真实 Attempt、预算、媒体和验收文件均不因本文精简而改变。

## 1. 正式产品边界

- **V1 只聚焦视频。** 主链：Creator/Director + Creative Mode → Creation 明确确认 → Preparation/Handoff → Planning/Truth → Material/Rights/Readiness → OpenClaw Native Authoring → Hypit 本地 Check/Build → Quality/Review → 人工选片/Content Library；不自动发布，不启用第二条旧视频生产链。
- 冻结 Material Layer V1.3；Material Layer 消费而不决定 Director 风格。关键合同仍是 `MaterialRequirement → ResolutionResult → BindingResult → MATERIAL_READY`；Rights、原始文件 SHA、失败证据、操作幂等、费用授权不得绕过。
- 新 Attempt 仅使用五项新版 pin：`truth-source-ref@1`、`material-observation-delta@1`、`easel-script-claim-ledger@3`、`quality-review-delta@1`、`easel-hypit-source@1`。历史 Attempt 的旧版本只读解释；旧 Writer/过渡执行不能重新入链。

## 2. 已交付的软件基线（ADR-005）

- 唯一正式分支 `easel-studio`，已非强推并核对 `origin/easel-studio` SHA：`a6ed065d72b66e5dcdf886a90eb5b36fac971acf`；ADR-005 CUT0～CUT6 已完成（Goal `wc_goal_yYpFxgMopd9MlccK`，Revision 23，Completed）。
- 当前新旧有效用例合并回归：**450 PASS / 0 FAIL**（20 个套件，Job `wc_job_qM8Yz2eOpg4F7phv`）；发布提交后另有定向 **74 PASS / 0 FAIL**。旧 Hypit 过渡测试 20 函数/25 个参数化场景精确退役，原文件通过 Git 追溯，保留有效旧检查 24 PASS。
- 前端 lint/build、115 项 Skills/Publisher 合同、Python 编译与 Git 差异检查通过。**不是**真实模型稳定性、付费 Hypit Build 或完整新作品视频 E2E 的通过证据。用户明确豁免 CUT5 独立 Reviewer：**未实际执行 Astra 独立复核**。
- 参见 [ADR-005](decisions/ADR-005-agent-result-processing.md)、[CUT 验收及交付记录](tasks/adr005-new-only-cutover-2026-10-10.md)、[旧测试迁移映射](acceptance/adr005-hypit-native-legacy-test-retirement-2026-10-10.md)。不要让较早文档的“待删除旧执行路径”覆盖此已发布状态。

## 3. Planning / Structured Result 可靠性：代码已提交、运行已加载

- **源码已固定**：可靠性工作包 8 个文件提交为 `4d8110589a27fa5621d633fafdbc1292f8a08d49`，包括 SDK 异常分类、版本固定的 OpenClaw 2026.9.4 补丁、隔离 Planning 评测代理的阶段感知 HTTP 恢复与测试。只有确定业务 POST 尚未发送的临时连接故障才允许有限重试；提交/结果未知保留 `UNKNOWN`。**评测代理恢复不等于生产 Gateway 已支持通用自动重试**。
- **离线证据**：Structured Result 27 PASS（Gateway 升级后复跑 Job `wc_job_JyIErVLNUgHDhcEd`）；以已核 SHA 的隔离 Runtime 运行 Native 工程 12 PASS、8 个未选择（`wc_job_SNzuGfyoaXIpzr8C`）；从已知上一版补丁到新版的离线升级演练成功，11 个运行组件全部匹配。
- **已受控加载**：正式安装 OpenClaw 2026.9.4 在升级前确认为已知旧补丁；备份 9 个代码组件到 Mac 私有路径 `~/Library/Application Support/Easel/backups/openclaw-structured-20261010T134205Z-85911` 后执行 8 目标补丁；安装目录 11/11 SHA PASS。Gateway `ai.openclaw.easel` 与 Easel Web `com.easel.web` 经原有 `launchd` 受控重启，二者 HTTP 200、Gateway Profile Health PASS、Node helper 加载 PASS；没有真实模型/Provider/付费媒体调用。正式资格批与新作品 E2E **仍需另行验收**。
## 4. 真实作品与预算状态

- 历史原作品的 Material 恢复曾达到 **R17 / 9 of 9 / MATERIAL_READY**；这是一个历史素材终点，不是工程视频完成、全类 BGM 能力通过或新 Creation 的真实 E2E。旧失败、UNKNOWN 和真实调用账单保持原值。
- 历史 Planning 资格/开发批次多次因语义、网关、上游响应等停止；旧批失败原件保留，不能以软件 450 PASS 重写成真实资格 PASS。
- **O1 可靠性软件/Runtime 加载已完成**；下一阶段是在独立模型与费用授权下沿唯一 Creation→Hypit 主链制作并验收一条**全新工程视频**，逐作品核对 Planning/Truth、Material/Rights、Build、Quality 和人工 Review；之后再做独立 6/6 资格及同一版本 3 个新主题稳定性证明。真实模型稳定性和线上通用自动重试不能由 O1 的离线测试推导为 PASS。
## 5. 本地工作区与证据保护

- 正常主仓库 `/Users/xgx/Projects/Easel`；ADR-005 已推送，可靠性代码单独提交。文档治理属于独立清理变更，具体 Git 提交/远端状态以实际 SHA 对账；约 1,192 个未跟踪的 `docs/acceptance/fixtures/` 历史验收原件继续保留，不为清洁 Git 而删除。- 原历史 Task 的内容保留于 Git（包括 `creator-e2e-repair-2026-09-30.md` 和 `v1c-t19-low-friction-creation.md`）；当前唯一授权入口为 Creator 自主首版 Task。不要对已删除文档恢复平行实施入口。
- 状态入口只更新本文，顺序只更新 [Roadmap](03_ROADMAP.md)，决策与冻结领域合同以 ADR/Architecture 为准；一次运行的细节留在原 Acceptance，不再为每个失败批次在本文新增倒序日志。

## 6. 下一动作及明确非目标

1. 核对可靠性代码与本轮文档整理的精确 Git 提交、远程 SHA，以及正式 Gateway/Web 运行版本；原件、费用与 `UNKNOWN` 一律不清零。
2. 后续用户单独授权后再开始一条全新工程视频的真实 Planning→Hypit E2E；禁止把本轮软件与 Runtime 加载证明当作真实模型稳定性、付费 Build 或视频验收通过。
3. 文档维护继续遵守唯一 Current State/Roadmap/Task 入口，历史从 Git 与 Acceptance 追溯，不恢复旧 Writer 或第二生产链。