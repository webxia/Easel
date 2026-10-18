# S6-04 · 本机worker与LangGraph持久编排

状态：**IMPLEMENTED**；本卡保存本机持久恢复与基础跨平台软件证据。后续真实生产/恢复结果见[S6-14](S6-14_integration-release.md)及[S6-14A](S6-14A_conversation-integration.md)，不再将最早的待授权状态作为当前阻断。

- **依赖**：S6-01、S6-03。
- **需求主/协作覆盖**：V2-EXP-006, V2-EXP-024, V2-EXP-025, V2-EXP-029, V2-EXP-033。
- **目标与合同**：[可执行设计](../15_IMPLEMENTATION_DESIGN.md)；[任务包共同约定](S6_IMPLEMENTATION_PLAN.md#2-每张卡开始与完成的共同约定)。
- **预计落点**：easel/production/worker.py、graph.py；easel/cli.py；pyproject.toml；.github/workflows/ci.yml；tests/production/test_worker.py、test_graph_resume.py。
- **执行分支建议**：`codex/s6-04-worker-graph`。

## 实施步骤

1. 选取与Python3.10/3.12兼容的受测LangGraph/checkpointer约束；核实传递依赖及主要桌面平台wheel，锁约束不直接追最新。不开云tracing。
2. 新增easel production worker/status和受管理生命周期；持久领取/续租/owner_epoch、取消和有限并发。关浏览器不终止制作；服务退出与用户取消分开。
3. 区分planning/production/revision run；规划结束保留待确认方案，production只读冻结方案继续。图状态仅放业务引用，恢复先核对领域记录/在途operation，按输入指纹复用完成任务。离线确定性fake节点验证故障窗口，实际业务handler由runtime接入；离线结果不冒充真实模型制作。
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

**验证：本地软件检查通过。** 在 `codex/s6-production` 的 S6 实施工作区，隔离环境 `/tmp/easel-s6-worker-venv`（macOS arm64 / Python 3.12）运行上述四组用例：128 passed，其中 worker/graph 18 项。真实临时 SQLite 与 LangGraph 检查点覆盖子进程硬退出后接管、未知操作仅查询原任务、双执行者争领、旧 epoch、取消/停服务、失租不终止整个调度循环、领域提交与检查点提交窗口、规划产物保存、生产不重新规划、持久重试上限、只读 CLI 状态与禁云追踪。

受测直接版本：LangGraph 1.2.15、SQLite saver 3.1.2、checkpoint 4.3.0、ormsgpack 1.12.0；保持 Python >=3.10。安装元数据确认这些包及 core/prebuilt/sdk/langsmith 传递层支持 3.10；ormsgpack 固定 1.12，避免 1.13 的 Python 3.11 下限。依赖放入可选 `production` extra，普通聊天不导入图依赖。依据：[LangGraph 发布元数据](https://pypi.org/project/langgraph/1.2.15/)、[SQLite saver 发布元数据](https://pypi.org/project/langgraph-checkpoint-sqlite/3.1.2/)、[持久化文档](https://docs.langchain.com/oss/python/langgraph/persistence)。

CI 已增加 Ubuntu/macOS/Windows × Python 3.10/3.12 的无外部服务持久冒烟入口；本地没有运行远端 CI，不能记作各平台已通过。未调用真实模型/生成服务；业务 handler 的完整制作闭环由后续集成验收。

### 整批集成补充

`97199284` 的 [CI run](https://github.com/webxia/Easel/actions/runs/38936316306) 已实际通过 Ubuntu/Windows 全库 pytest，以及 Ubuntu/macOS/Windows × Python 3.10/3.12 的持久层66项。该结果只绑定此基础提交；新增业务、迁移2、删除及取消渲染的最终证据以 [S6-14](S6-14_integration-release.md) 为准。上述早期未覆盖描述是当时状态，不代表最终未检查。
