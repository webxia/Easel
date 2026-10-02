# Creator 作品工作区体验优化

历史基线 / 具名验收记录（2026-10-02 归档标识）：下文状态、当前作品、恢复授权与 READY 判断只适用于当时范围，不是当前执行指令。当前唯一范围见 [自主首版 Task](creator-autonomous-first-cut-2026-09-30.md)，实际状态见 [Current State](../02_CURRENT_STATE.md)。

状态：SOFTWARE_ACCEPTED；范围内实现与确定性验证完成，真实 Creator E2E 待人工操作。范围：用户本次 Goal，保留当前未提交修复与冻结主链，不操作当前 Creation。

顺序与依赖：统一只读状态投影 → Conversation + Work Canvas / Proposal → 制作、无 Attempt、失败与断连恢复 → 分别保留事实、Match、Rights、费用门禁的任务卡 → 成片审阅与反馈 → 清理重复入口。

验收：确定性状态场景、前端 lint/build 与页面检查；不调用付费 AI、不执行真实 Build、不启动完整 E2E。刷新状态不得触发生产恢复；恢复与费用行为分别保留正式 API 和显式操作。

风险：早期状态不能依赖 Attempt；过期/断连不得显示正在实时运行；素材证据按 Need 和素材身份隔离；反馈不得伪装成已经执行的修改。

## 实施与验证

根因与最小修复：Proposal 无作品入口、对话和长制作表单互相挤占 → 独立 Conversation / Work Canvas；早期失败依赖 Attempt → Creation 状态投影；轮询错误被其他成功响应清掉 → 分别保留连接状态；观察串用与 Rights 表单藏在高级区 → 按场景的 Match 与独立 Rights 任务卡；修改意见只有聊天说明 → 输出绑定反馈和复用 checkpoint 的构图/转场修改入口。

规格卡与服务端确认共用字面解析，不提取示例/歧义；Preparation 验证相同规格，未知不补猜。正式阶段恢复、费用与最终审片门禁保留。通用内容、规格、声音、字幕与素材替换不自动执行，UI 明确提示重新确认方案。

验证入口：`node web/frontend/tests/creatorWorkspace.test.mjs`；在隔离 Vite 服务上执行 `web/frontend/tests/workspace-browser.mjs`（Playwright、ffmpeg；接口全部拦截，测试媒体仅在临时目录）；后端 Preparation / Material integration / Hypit integration / scoped Authoring 组合覆盖 110 项。最新相关子集 11 passed，前端 lint/build 与 compileall / skill 合同 / diff check 通过。证据和当前验证边界统一记录于 `02_CURRENT_STATE.md`，不声称真实 E2E 或新全量 pytest 已完成。

READY_FOR_HUMAN_E2E = YES。人工 Creator 自行启动真实验收；本轮未操作当前 Creation、未调用付费 AI、未执行真实 Build。
