# S6-05 · 作品导航与可观察制作工作台
> **调度状态：CLOSED · 2026-10-19**。用户决定关闭本卡独立研发排程：既有实现和软件验收结果保持原样，仅作为历史交付与回归依据；不再从旧实施步骤重新派发任务。后续确有实证缺陷时，仅纳入[当前三项主线](../04_CURRENT_STATE.md#唯一研发下一动作)做局部修复。CLOSED 不代表全部真实模型、音画质量、完整规格或 Creator 接受已通过。

状态：**IMPLEMENTED / OFFLINE_INTEGRATION_VERIFIED**。作品列表、制作工作台、SSE 重连、方案编辑、授权与版本审阅已接通。

- **依赖**：S6-02、S6-04。
- **需求主/协作覆盖**：V2-EXP-024, V2-EXP-028, V2-EXP-029。
- **目标与合同**：[可执行设计](../15_IMPLEMENTATION_DESIGN.md)；[任务包共同约定](S6_IMPLEMENTATION_PLAN.md#2-每张卡开始与完成的共同约定)。
- **预计落点**：web/production_api.py；web/frontend/src/lib/productionApi.ts；ProductionPage.tsx；App.tsx、ChatPage.tsx、OutputsPage.tsx；tests/frontend/productionProgress.test.mjs；tests/production/test_progress_api.py。
- **执行分支建议**：`codex/s6-05-progress-ui`。

## 实施步骤

1. GET快照与after_seq SSE从领域事务事件读取，snapshot附cursor；过期游标可重取，重复/迟到消息不覆盖新run。
2. 新作品导航从持久GET works列表读取，可从聊天和内容库进入，含无画像/未出片及历史作品；显示阶段/动作、并行步骤、输入输出、简短决策摘要、成果、次数、等待/未知/失败/需决定与更新时间。
3. 渲染真实测试产物预览，未生成不造预览；内部日志/思维/凭证不进入用户payload。
4. 观察不触发执行；用户取消走命令服务。已有chat的stop与作品cancel分离，关闭/删聊天后仍能从作品继续查看。

## 通过标准与负例

真实原型事件与展示逐项一致；并行不覆盖；断流显示状态更新中断；刷新/重连不重复调用；删聊天后可从列表找回未出片作品；旧版本事件不覆盖新版；不存在产物不标完成；无伪百分比；现有聊天回放不回归。

## 验证入口（本卡实现相应文件后执行）

```bash
python -m pytest -q tests/production/test_progress_api.py tests/test_chat_question_replay.py
node --test tests/frontend/productionProgress.test.mjs tests/frontend/chatQuestionReplay.test.mjs tests/frontend/sessionHistory.test.mjs
npm --prefix web/frontend run lint
npm --prefix web/frontend run build
```

**交付要求**：用户能在无付费原型运行中实际观察进度/成果/恢复；不是静态设计稿。

## 执行记录

**软件及本地媒体验证：已执行。真实模型/服务、真实自主生产及 Creator 接受不据离线结果宣称通过。** 整批受测代码与回归结果见 [S6-14](S6-14_integration-release.md)。

### 本轮集成记录（2026-10-17）

Node 进度用例、TypeScript 构建及浏览器本地验证已执行。隔离数据根中创建作品、启动缺配置规划、重启 Web 后作品/任务/原因/恢复入口仍存在，次数保持0；渲染步骤与实际视频审查段数来自持久事件，不展示伪百分比。
