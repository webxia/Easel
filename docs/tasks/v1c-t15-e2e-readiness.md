# V1C-T15：E2E 准备与正式产品验证

历史基线 / 具名验收记录（2026-10-02 归档标识）：下文状态、当前作品、恢复授权与 READY 判断只适用于当时范围，不是当前执行指令。当前唯一范围见 [自主首版 Task](creator-autonomous-first-cut-2026-09-30.md)，实际状态见 [Current State](../02_CURRENT_STATE.md)。

状态：**E2E IN PROGRESS**。标准对话正式恢复流程已通过 Preparation 并进入 Script Truth 人工审核门；尚未进入 Material Supply，三条完整 Creation E2E 均未完成。

## 目标链路

```text
Web 明确确认 → 冻结 Content / Context / Creative Mode
→ OpenClaw Planning / MaterialPlan
→ Material 来源或经确认的生成 → Inspect / Rights / Match / Bundle / Gate
→ Production Authoring 明确选材 → Hypit check / plan / pricing / approval / Build
→ Export / 技术检查 / 人工审片 / Selected Output
```

## 本阶段准备范围

- 纠正实现链路断点：供给重算恢复仅与当前 Attempt、Plan revision、Need 匹配且技术检查通过的已完成生成素材；Rights 未知继续阻断。
- 通用 Rights review 只能选取当前 Plan/Gate Bundle 中技术检查通过、字节 SHA 一致的资产；Rights 信息及证据必须绑定资产 SHA，Gate 只按已记录条款和范围重新计算。自 T19 起，Gate READY 后由此前的“开始制作”确认授权非付费 Authoring 自动启动；Preparation 或审核 API 本身不得单独制造用户授权。
- Script Truth 的审阅者身份必须如实持久化；经用户明确委托的调试 Agent 可留下独立的 `DELEGATE_REVIEWED` 记录，不得冒记为本地人工审核或来源支持事实。
- Creation 读取和列表投影生命周期状态，不修改磁盘记录或伪造历史迁移事件。
- 确认 Web → API → Material → Hypit → Export/Review/Selection 使用同一正式链；旧 Hypit Generation 文档标明历史范围。
- 运行确定性回归、全量测试、编译、前端 lint/build、技能检查及 diff 检查；确认没有测试触发真实 Provider 或 Build。
- 准备并记录非破坏性 runtime preflight、Hypit 版本/CLI/本地 runtime/program 状态和各依赖 blocker；不以配置存在冒充认证或 E2E 通过。
- Current-Bundle Rights review 闭环有确定性集成与 API 鉴权回归；正式 E2E 仍需操作员按真实条款/资产证据审核。不得把测试 Fixture 许可用于真实素材，也不得由 Easel 推断 Provider 条款。
- 最新确定性验证：`.venv/bin/python -m pytest -q` → 463 passed, 5 skipped；compileall、技能验证、前端 lint/build 与 `git diff --check` 均执行。lint 仅报告既有 `AccountsPage.tsx` Hook dependency warning。

## 正式 E2E 开始门槛

开始真实 E2E 前逐项确认：

1. 本机 OpenClaw 模型认证及 endpoint 能完成一次授权的 Planning/Authoring 请求。
2. Hypit 当前版本、runtime doctor、所需本地 programs 与 Worker 就绪；Build 使用既有用户审批门禁。
3. 目标 Required Need 有可访问、技术检查通过且资产级 Rights 已审阅的素材。若要测 AI 生成，必须另行确认具体计费调用；不能把未知 Rights 变为可用。
4. 若目标包含旁白/音乐，Script hash、预置音色或音频素材准入通过，Build 输出有音轨并通过实际聆听/审片；SFX 非本次默认 Release 门槛。
5. 本机同源浏览器会话可以建立；测试使用的 Creation、Profile、素材、预算/审批与输出范围明确。

## 既有无费用预检（2026-09-28）

- Hypit 0.2.7：doctor `ok`；Runtime Worker `running`、active work `0`；本地 Programs `2/2 READY`。
- `v1-release`：`NOT_READY`，仅模型认证/endpoint 与 `audio.production` 尚未验证。Gateway health 可达；读取 OpenClaw 配置不等于实际模型认证。
- Runtime 发现 4 个结构有效 Rights sidecar、3 个逐 Asset Rights 视觉样本和 1 个 BGM 样本；每个素材仍需针对具体 Need 重新 admission。
- 本机有 11 个 Creation 记录；只有具名 Acceptance 的结果可作为已验证证据。T15 的多 Content 验收仍需新鲜运行，不用历史选定结果替代。
- 本次预检没有调用 OpenClaw 模型、MiniMax 生成或 Hypit Build。

## 当前正式运行

- 2026-09-28，标准 Web 对话从 Creation `cr_c995c3cbb8104389a4bf568023531e8b` 恢复已有 Handoff `ho_42843e2cea71ac9f9dbe8d4d9325c0ca` 与 Attempt `fa_42843e2cea71ac9f9dbe8d4d9325c0ca`；没有新建 Creation。
- 重启加载当前代码后，原 `AcquisitionInfo` 导入异常未复现。Planning 已产生 Script Truth ledger，Preparation 状态为 `SCRIPT_TRUTH_REVIEW_REQUIRED`；Material Supply 因人工审阅门正常停止，尚无外部素材检索、MiniMax 生成或 Hypit Build。
- Operator API 使用本机回环地址上的同源浏览器会话，无需手动输入凭证；付费生成和 Hypit Build 的明确门仍保留。调试期间如用户明确委托 Codex 执行审核，必须在证据中区分 `DELEGATE_REVIEWED`；通过后才进入素材检索与 Rights Gate。T19 已将必要的低风险审核归类自动化；不可确定的事实与权利问题仍按 Gate 处理。

## 正式 E2E 验收

- 至少 3 个独立 Content/Creation 按冻结内容、Creator Context、Creative Mode 完成官方 Web 主链；当前代码状态、Attempt、Gate 与实际产物一致。
- 无人工改写中间文件或绕过 Gate；Production 只使用已准入且显式选择的素材；Hypit 只执行制作，不承担 AI 生成。
- 每个 Required Need 在 Build 前有可追溯 Match、Bundle、Rights 与 Readiness 证据；失败用例不得进入 Build。
- 导出媒体通过时长、画幅、音视频流检查；需要旁白/音乐时具备可听音轨并完成人工审片。
- Review 绑定最终输出 SHA；只有审核通过的输出能被选为 Selected Output，Creation 概要读取为 `ready`，发布仍为人工操作。
- 保存不含 Secret 的 Acceptance 证据，分别标记 `SOFTWARE_ACCEPTED`、`REAL_WORLD_VERIFIED`、`NOT_VERIFIED`；一条成功样例不代表跨 Content 一致性已证明。

完整 V1 标准另受 [视频架构验收标准](../architecture/easel-video-architecture-v1.md) 约束。T15 不自动启动其他 Acquisition、Library、Attribution、Continuity 分支；需要时单独授权和记录。
