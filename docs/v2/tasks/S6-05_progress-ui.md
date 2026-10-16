# S6-05 · 作品导航与可观察制作工作台

状态：**NOT_STARTED**；代码/测试目标尚待实现或接入。

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

**验证：NOT_TESTED。** 实施时记录受测提交、实际命令/结果及未覆盖项。
