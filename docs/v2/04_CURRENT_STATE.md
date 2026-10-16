# Easel V2 · 当前状态

> **阶段：S2 V1 历史、需求演进与因果复盘的文档研究已完成，待用户审核；S3/S4/S5 尚未启动。** 核查日：2026-10-16。
>
> 本文件是阶段事实快照；源码/报告各自固定 Git SHA、PR 与证据范围，**未合并的文档分支不等于 V2 主线已经吸收成果**。详细历史归因与完整审计证据见关联报告，而不是在本状态页重复流水账。

## 当前基线与保护

- V2 **业务源码审计基线**：`easel-v2-rebuild@8eeafb6b9bf62b26e2077057cbebe45721f5d464`；它不包括官方后来新增但**尚未获准合入**的上游提交。S0 AI Coding 骨架已进入 V2 主线。
- V1 **历史封存基线**：`easel-studio@57c8e2ade21af9fb6abccdab3f7ba8e50132314f`；独立旧工作树和 `/Users/xgx/Projects/Easel-V1-History` 私有原件保持只读。旧协议、运行结果、Attempt、预算与媒体没有复制到 V2 仓库。
- 四处原有未跟踪二维码/草稿/中文创作目录为用户私有现场，禁止清理、纳入提交或修改；本次 S2 只使用具名历史文档和私有审计原件，不执行旧生产。
- **本次 V2 需求尚未正式录入/批准。** 基于较早讨论的 `01_REQUIREMENTS.md` 在 V2 旧主线仍有“CURRENT”过期标签；S1-A [PR #1](https://github.com/webxia/Easel/pull/1) 已将其更正为 DRAFT。未合并前以最新用户明确决定为准，不把旧候选或旧 V1 已确认行为自动认作新需求。

## 阶段事实与单一下一动作

| 阶段 | 实际状态与成果 |
|---|---|
| S0 · 工程骨架 | COMPLETE；已推送到 `easel-v2-rebuild`，远端具名 CI 曾成功（真实安装按触发规则跳过） |
| S1-A · 当前能力审计 | **报告 COMPLETE / 待合并**：[PR #1 当前源码能力报告](https://github.com/webxia/Easel/pull/1)；静态事实不作为本次新需求 |
| S1-B · 工程质量与现有规范审计 | **报告 COMPLETE / 待合并**：[PR #2 工程质量报告](https://github.com/webxia/Easel/pull/2)；15 项风险需后续决策，隔离本地全量 pytest 曾为 1261 PASS / 2 FAIL / 11 SKIP，不能记全绿 |
| S2-A/B/C/D · V1 历史、需求与归因 | **有界历史研究 COMPLETE / 待用户审核和文档合并**：[历史与因果报告](09_V1_HISTORY_CAUSAL_AUDIT.md)。覆盖 71 份 V1 Markdown、130 个第一父提交的历史路径与 22 项旧问题，代表性成功/失败运行原件，并重新验证 7 份 final-audit SHA；不能误写成全部 8.36 GiB 字节或所有因果机制均已验证 |
| S3 · 历史经验与需求认识提炼 | NOT_STARTED；不能自动升级为本次需求或工程标准 |
| S4 · 本次需求与事实输入正式确认 | NOT_STARTED；需要用户新确认，旧 900 秒/四音轨属于历史需求而非新需求的自动批准 |
| S5 · V2 方案比较与设计冻结 | NOT_STARTED；`ModelGateway`、`Production Kernel` 等仅为候选 |
| S6/S7 · 实施与真实作品/范围验收 | NOT_STARTED；没有发生本次 V2 的真实付费模型、Build、发布或 Creator 接受验收 |

流程与阶段准入的详则保存在独立 [S2–S5 流程文档 PR #3](https://github.com/webxia/Easel/pull/3)。S2 报告在本分支产生独立 PR，**不包含、合并或覆盖 PR #1/#2/#3 的尚未验收提交**；未来需要对 `INDEX`、`ROADMAP`、`CURRENT_STATE` 和需求状态做语义合流。

**NEXT_SINGLE_ACTION**：用户审核 [S2 历史事实、需求演进与深度归因报告](09_V1_HISTORY_CAUSAL_AUDIT.md) 的有证据结论与待证边界；确认接收后才开始 **S3：从历史事实提炼适用经验与历史需求认识**。不自动修改 V2 正式需求或架构、不修复 V1、不申请新的真实模型/素材/Build/费用权限。

## 本次文档验收口径

报告既保留 Creator 审片成功、真实 Material/Native 媒体子能力，也保留三次独立 Material E2E FAIL、10/08 开发真实失败及 R09–R19 完整 Planning 0 PASS，区分 `DESIGNED`、`SOFTWARE_PASS`、`REAL_RUN`、`CREATOR_ACCEPTED`。安全的正确拒绝不会为了“完成率”被归入必须删除的错误。真实执行、账单或权益仍按原件，不靠总结反向改写历史。
