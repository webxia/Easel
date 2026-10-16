# S6-01 · 领域合同、事务存储与迁移

状态：**NOT_STARTED**；代码/测试目标尚待实现或接入。

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

**验证：NOT_TESTED。** 实施时记录受测提交、实际命令/结果及未覆盖项。
