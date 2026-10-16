# S6-08 · 任务化模型与受控工具执行

状态：**NOT_STARTED**；代码/测试目标尚待实现或接入。

- **依赖**：S6-02、S6-03、S6-06。
- **需求主/协作覆盖**：V2-EXP-001, V2-EXP-004, V2-EXP-005, V2-EXP-014, V2-EXP-032, V2-EXP-034。
- **目标与合同**：[可执行设计](../15_IMPLEMENTATION_DESIGN.md)；[任务包共同约定](S6_IMPLEMENTATION_PLAN.md#2-每张卡开始与完成的共同约定)。
- **预计落点**：easel/production/context.py、model_tasks.py、tools.py；easel/direct_api.py仅必要抽取公共传输；tests/production/test_model_tasks.py。
- **执行分支建议**：`codex/s6-08-model-tasks`。

## 实施步骤

1. 新TaskContext/TypedResult能力合同，复用配置而非整段普通聊天，显式组装画像必要依据、导演版本、事实/适配许可、场景和真实媒体。
2. 接收结构化结果及工具调用，用Python白名单按句柄执行；不给任意shell/file系统或直接媒体凭证。禁止加载TURN_REMINDER及根研发AGENTS作为产品执行指令。
3. 支持只读检索公共事实的来源/日期登记，个人经历只能来自用户或当前画像；不同任务只需相应模态。
4. HTTP成功/finish/空tool结果不等于有效业务结果。格式纠正与工具循环有有限技术上限，错误分类与原回执脱敏保存；不回抄授权字段。
5. 旧直接聊天仍拒绝未支持工具；新任务路径独立，不改原会话绑定。真实模型调用另明确授权。

## 通过标准与负例

伪造授权/owner/完成/外画像句柄拒绝；fake模型不能写状态；缺必要模态返回不可用；个人事实不被公共检索替换；格式失败停止有诊断；原direct_api和Harness行为无回归。

## 验证入口（本卡实现相应文件后执行）

```bash
python -m pytest -q tests/production/test_model_tasks.py tests/test_direct_api.py tests/test_harness_workspace.py tests/test_persona_security.py
```

**交付要求**：实际工具派发边界和fake协议测试须通过；能力真实性仍由后续授权样片检查，不假称模型质量已通过。

## 执行记录

**验证：NOT_TESTED。** 实施时记录受测提交、实际命令/结果及未覆盖项。
