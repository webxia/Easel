# S6-01 · 领域合同、事务存储与迁移
> **调度状态：CLOSED · 2026-10-19**。用户决定关闭本卡独立研发排程：既有实现和软件验收结果保持原样，仅作为历史交付与回归依据；不再从旧实施步骤重新派发任务。后续确有实证缺陷时，仅纳入[当前三项主线](../04_CURRENT_STATE.md#唯一研发下一动作)做局部修复。CLOSED 不代表全部真实模型、音画质量、完整规格或 Creator 接受已通过。

状态：**IMPLEMENTED — 本地软件检查通过**；基础跨平台 CI 已核验；整链及真实证据见 S6-14。

- **依赖**：无。
- **需求主/协作覆盖**：V2-EXP-002, V2-EXP-003, V2-EXP-005, V2-EXP-008, V2-EXP-013, V2-EXP-020, V2-EXP-027, V2-EXP-034。
- **目标与合同**：[可执行设计](../15_IMPLEMENTATION_DESIGN.md)；[任务包共同约定](S6_IMPLEMENTATION_PLAN.md#2-每张卡开始与完成的共同约定)。
- **预计落点**：easel/production/contracts.py、errors.py、store.py、migrations/；tests/production/test_contracts.py、test_store.py（均新建）。
- **执行分支建议**：`codex/s6-01-domain-store`。

## 实施步骤

1. 按设计 §3 固定物理 schema 和类型，建立work/plan/grant/run/task/operation/artifact/event/receipt及频道导演基础关系；不建立第二套人设。
2. 临时数据库迁移、事务和修订条件更新，确认后不可变；媒体索引、依赖、接受独立记录。
3. 原子命令回执与事件游标，定义所有状态/错误码；储存模块不调用网络或web。
4. 只初始化指定新V2数据根，不读取或迁入旧运行库；已有profiles继续原文件。

## 通过标准与负例

重复/并发command只登记一次；相同key不同payload拒绝；事务失败状态与事件一起回滚；旧revision写入拒绝；无画像可建作品；不可变方案不能原地修改；migration失败保留旧数据库。测试必须用tmp_path，不能初始化真实outputs。

## 验证入口（本卡实现相应文件后执行）

```bash
python -m pytest -q tests/production/test_contracts.py tests/production/test_store.py
```

**交付要求**：领域接口可由下游导入、临时库读写迁移有真实测试；没有成功空壳方法。向S6-02/03/04交付最终schema与函数签名。

## 执行记录

受测工作树：`codex/s6-production`，基于 `4525b09da8bfc30ba556dba2198872a23b35a0ae` 加本任务未提交改动。新增严格合同、20 个物理表族与数据库约束、显式迁移、短事务、幂等命令回执、事件/快照、不可变方案和在线备份；没有读取或迁移用户运行库。

本地 Python 3.12 执行本卡命令，**32 passed**。覆盖并发重复命令、旧修订、事务整体回滚、迁移失败回滚、跨作品/画像引用、未确认方案生产拒绝、接受版本引用保护和 WAL 在线备份。

未覆盖：其他平台/Python 版本 CI、下游服务集成及真实模型/媒体生产。调用方仍负责用户确认、任务状态转换和外部服务准入，存储层不把软件检查冒充真实生产通过。

### 整批集成补充

`97199284` 的 [CI run](https://github.com/webxia/Easel/actions/runs/38936316306) 已实际通过 Ubuntu/Windows 全库 pytest，以及 Ubuntu/macOS/Windows × Python 3.10/3.12 的持久层66项。该结果只绑定此基础提交；新增业务、迁移2、删除及取消渲染的最终证据以 [S6-14](S6-14_integration-release.md) 为准。上述早期未覆盖描述是当时状态，不代表最终未检查。
