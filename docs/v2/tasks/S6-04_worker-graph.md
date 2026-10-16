# S6-04 · 本机worker与LangGraph持久编排

状态：**NOT_STARTED**；代码/测试目标尚待实现或接入。

- **依赖**：S6-01、S6-03。
- **需求主/协作覆盖**：V2-EXP-006, V2-EXP-024, V2-EXP-025, V2-EXP-029, V2-EXP-033。
- **目标与合同**：[可执行设计](../15_IMPLEMENTATION_DESIGN.md)；[任务包共同约定](S6_IMPLEMENTATION_PLAN.md#2-每张卡开始与完成的共同约定)。
- **预计落点**：easel/production/worker.py、graph.py；easel/cli.py；pyproject.toml；.github/workflows/ci.yml；tests/production/test_worker.py、test_graph_resume.py。
- **执行分支建议**：`codex/s6-04-worker-graph`。

## 实施步骤

1. 选取与Python3.10/3.12兼容的受测LangGraph/checkpointer约束；核实传递依赖及主要桌面平台wheel，锁约束不直接追最新。不开云tracing。
2. 新增easel production worker/status和受管理生命周期；持久领取/续租/owner_epoch、取消和有限并发。关浏览器不终止制作；服务退出与用户取消分开。
3. 区分planning/production/revision run；规划结束保留待确认方案，production只读冻结方案继续。图状态仅放业务引用，恢复先核对领域记录/在途operation，按输入指纹复用完成任务。暂用确定性fake节点走合同，不冒充模型制作。
4. graph_version不兼容时明确暂停；旧worker结果不能覆盖当前版本，但原操作真实成果可幂等收存。
5. 按现有harness-portability矩阵补无模型图持久化冒烟；缺依赖只限制V2，不破坏原聊天。

## 通过标准与负例

杀worker后新进程恢复；规划中崩溃仍能恢复待确认方案；确认后不重新生成方案；旧epoch晚到拒绝；重复进程启动不双提交；检查点与领域记录双向中断不跳过授权；取消/等待恢复；3.10/3.12兼容性有实际CI证据，未运行平台不得标通过。

## 验证入口（本卡实现相应文件后执行）

```bash
python -m pytest -q tests/production/test_worker.py tests/production/test_graph_resume.py tests/test_agent_harnesses.py tests/test_runtime_env.py
```

**交付要求**：worker可运行并从真实临时持久库恢复；fake节点只验证编排。业务状态仍由S6-01/03负责。

## 执行记录

**验证：NOT_TESTED。** 实施时记录受测提交、实际命令/结果及未覆盖项。
