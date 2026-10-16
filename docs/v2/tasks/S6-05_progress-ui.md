# S6-05 · 作品导航与可观察制作工作台

状态：**NOT_STARTED — 实施内容已定义，依赖满足后可执行；代码/测试目标尚未创建或未接入。**

- **依赖**：S6-02、S6-04。依赖条件按实际产物满足，不只看文档状态；未满足可准备只读定位，不假报完成。
- **需求主/协作覆盖**：V2-EXP-024, V2-EXP-028, V2-EXP-029。
- **目标与合同**：[可执行设计](../15_IMPLEMENTATION_DESIGN.md)；[任务包共同约定](S6_IMPLEMENTATION_PLAN.md#2-每张卡开始与完成的共同约定)。本卡路径均为仓库相对路径，标明新建处是待实现目标。
- **预计落点**：web/production_api.py；web/frontend/src/lib/productionApi.ts；ProductionPage.tsx；App.tsx、ChatPage.tsx、OutputsPage.tsx；tests/frontend/productionProgress.test.mjs；tests/production/test_progress_api.py。
- **执行分支建议**：`codex/s6-05-progress-ui`，从具备依赖成果的受审查版本创建；不自动合并保护主线。

## 实施步骤

1. GET快照与after_seq SSE从领域事务事件读取，snapshot附cursor；过期游标可重取，重复/迟到消息不覆盖新run。
2. 新作品导航从持久GET works列表读取，可从聊天和内容库进入，含无画像/未出片及历史作品；显示阶段/动作、并行步骤、输入输出、简短决策摘要、成果、次数、等待/未知/失败/需决定与更新时间。
3. 渲染真实测试产物预览，未生成不造预览；内部日志/思维/凭证不进入用户payload。
4. 观察不触发执行；用户取消走命令服务。已有chat的stop与作品cancel分离，关闭/删聊天后仍能从作品继续查看。

## 通过标准与负例

真实原型事件与展示逐项一致；并行不覆盖；断流显示状态更新中断；刷新/重连不重复调用；删聊天后可从列表找回未出片作品；旧版本事件不覆盖新版；不存在产物不标完成；无伪百分比；现有聊天回放不回归。

## 验证入口（本卡实现相应文件后执行）

以下命令从仓库根、受测虚拟环境执行；新test文件由本卡创建，当前不存在不代表可跳过。现有pytest发现范围和前端命令沿用项目实际入口，无付费服务默认以测试替身替代。

```bash
python -m pytest -q tests/production/test_progress_api.py tests/test_chat_question_replay.py
node --test tests/frontend/productionProgress.test.mjs tests/frontend/chatQuestionReplay.test.mjs tests/frontend/sessionHistory.test.mjs
npm --prefix web/frontend run lint
npm --prefix web/frontend run build
```

用户能在无付费原型运行中实际观察进度/成果/恢复；不是静态设计稿。

## 范围、回退与交接

仅修改本卡及必要依赖接口；若合同需变化先更新统一设计和受影响任务，不另创同义接口。新增能力启用前不得写用户真实运行库；本轮未授权真实模型或媒体服务调用、旧数据迁移、生产服务重启或自动发布。后续具体任务已有授权继续有效；许可本地媒体的解码、渲染、检查与离线协议测试按共同约定执行。

失败保留可用产物与证据，只回退本任务代码/测试数据，不删除用户outputs/画像；不能用修改需求换PASS。完成记录实际HEAD、命令/输出、未测平台/服务、变更范围和下一依赖任务；更新当前状态。**运行结果：NOT_TESTED。**
