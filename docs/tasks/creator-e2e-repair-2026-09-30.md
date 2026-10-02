# Creator E2E 前修复任务

历史基线 / 具名验收记录（2026-10-02 归档标识）：下文状态、当前作品、恢复授权与 READY 判断只适用于当时范围，不是当前执行指令。当前唯一范围见 [自主首版 Task](creator-autonomous-first-cut-2026-09-30.md)，实际状态见 [Current State](../02_CURRENT_STATE.md)。

状态：SOFTWARE_ACCEPTED / 待人工 E2E。范围来自本次 Goal；人工 Creator E2E 由 Creator 自行启动，本任务只做确定性验证。

| 顺序 | Task | 根因与最小修复 | 定向验收 |
|---|---|---|---|
| 1 | Hypit 0.2.7 Authoring Contract | 任务书、Prompt、Retry 与本机 Surface 不一致；以安装包 READMEs/Surface 与 `hypit check` 收敛语法，保持 Easel Run JSON 的身份约束。 | 一份有效的静态工程通过本机 `hypit check`；非法 Run 身份阻断。 |
| 2 | Artifact Validation | 文件存在/UTF-8 不证明 Hypit 可执行；隔离工作区内静态 check 通过后才提升，失败时保留诊断并定向修复。 | 无效 SVML/SVS/Run 不覆盖上次可信产物。 |
| 3 | Material Match / Readiness | 无语义证据的软分仍被标为 qualified，Readiness 信任旧 Match；逐 Need 重新核验语义、技术、Rights 和 hard constraint。 | 无证据不覆盖；logo 冲突拒绝；同一 Asset 对不同 Need 分别判断。 |
| 4 | Narration / Timeline 与图片尺寸 | 独立旁白可能长于已确认时长；Canvas 被误用为图片 Extent；在 Authoring 前和产物校验时核对时长，在选图后核对原始宽高。 | 71.136 秒旁白不准入 45 秒 Timeline；错误 Extent 阻断。 |
| 5 | Creation Progress + Retry | 长流程状态和失败节点缺少产品投影；失败阶段从最近可信 checkpoint 重试。 | 已成功 Planning/Material 不重新供应；确定失败 Build 新建幂等恢复 Attempt 并重做费用批准；提交不确定 Build 先对账。 |
| 6 | Review Automation | 技术 QC 已自动执行，但创作 PASS 可被空依据写入；保留技术自动校验，要求事实/风格 PASS 有 Creator 判断或可追溯预审依据。 | 空依据 PASS 被拒绝，最终选择绑定同一 SHA。 |
| 7 | Proposal 已确认 Bug | 提案语境混入制作通用指令、模型猜测与用户事实；限于提案 Prompt 和入口边界修复。 | 不编造身份、规格或经历；不暴露内部名词；最多一个方向性问题。 |
| 8 | Creator Timeline UX | 对话和制作状态混排，四格进度隐藏失败；七阶段状态投影，工程细节默认折叠。 | waiting/running/action required/failed/completed 均可区分；显示阶段、原因与动作。 |

依赖：1 → 2；3 → 4 → 5；6、7 可在相应服务边界独立验证；8 消费 5 的真实状态。所有任务保留既有 Creation → Material → Hypit → Review 主链，不重新设计 Material Layer V1.3。

定向验证：Material/Hypit/Authoring 106 项、Preparation 41 项通过；确定失败 Build 的 checkpoint 迁移、重复点击幂等、未批准禁止提交、提交状态不确定禁止重试，以及本地 Rights/Gate 恢复有定向回归。本机 Hypit 0.2.7 静态图片和音轨最小工程各通过 `hypit check`；前端 lint/build、Python compileall、skill 合同校验和 `git diff --check` 通过。未继续当前 Creation，未执行完整 Creator E2E。

当前验证边界：没有已配置的图像语义分析器时，缺乏有效画面证据的素材会保持 NOT_READY。确定失败的 Build 已可迁移 checkpoint 到新的 Attempt；新 Attempt 的 Plan/Pricing/费用批准及真实 Build 仍待 Creator 操作，提交不确定状态禁止迁移。不得用自动 PASS 或重复 Provider 请求绕过。

## Preparation 占位节拍回归修复

2026-09-30 Creator 报告内容准备失败。只读诊断发现 Production Brief 总时长 15 秒，但 Agent 复制了格式示例中的单个 2.5 秒占位 beat；真实后端校验正确拒绝，聊天却隐藏了原因。

最小修复：格式示例改为空 beats，未确认节拍不得编排；新增只读草稿校验入口，与冻结提升共享四文件业务校验，要求 Agent 交付前执行并修正错误。失败原因进入同 Creation 的准备重试上下文；聊天显示脱敏后的具体诊断和重试动作。未修改当前 Creation 草稿或快照，未执行其重试或完整 E2E。

定向回归覆盖：错误占位 beat 被拒绝且不创建快照；重试复用 operation key 并携带后端诊断；空 beats 和合计正确的已确认节拍通过同一校验。

验证结果：Preparation 定向套件 42 passed（89.81 秒），Python compileall 与 git diff --check 通过；只读 CLI 对当前失败草稿返回准确的 2.5 / 15 秒诊断，退出码 1。未启动制作。
