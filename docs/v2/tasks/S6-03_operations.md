# S6-03 · 外部操作准入、生成次数与未知结果

状态：**IMPLEMENTED**；本地软件检查通过，真实服务验收另列。

- **依赖**：S6-01。
- **需求主/协作覆盖**：V2-EXP-006, V2-EXP-013, V2-EXP-024, V2-EXP-025, V2-EXP-026, V2-EXP-033。
- **目标与合同**：[可执行设计](../15_IMPLEMENTATION_DESIGN.md)；[任务包共同约定](S6_IMPLEMENTATION_PLAN.md#2-每张卡开始与完成的共同约定)。
- **预计落点**：easel/production/operations.py、providers/base.py；tests/production/test_operations.py、fake_provider.py。
- **执行分支建议**：`codex/s6-03-operations`。

## 实施步骤

1. 实现submit/observe/receive及reserved/sending/submitted/unknown/terminal转换；reserved→sending同一条件更新核验run/task修订、owner_epoch、取消、provider+model/mode允许清单与额度。过期worker不能新建或发送；原回执可按既有operation_id核实接收。
2. 操作ID由业务请求创建并固定服务/模式及配置版本；重放同ID复用，相同prompt的明确新生成用新ID。IMAGE/VIDEO计次，VOICE/MODEL留回执但不占额度；确认前planning/preview只引用本用途服务授权，不取得生产生成权限。
3. 假Provider在本地持久记录接收次数，支持可查询/不可查询两种模式；每个发送窗口提供故障注入。
4. 有task_id/请求键时观察原任务，未知不能自动重发；结果接收与技术核验独立重试，服务凭证只在adapter取得。

## 通过标准与负例

争最后额度至多一条发送；A预留后暂停、B接管、A恢复时A不能发送，B不重发已sending/unknown操作；有剩余额度但同服务未授权模式仍拒绝；发送前可证明失败释放；对端已接受但回执丢失不重发；不可核实保持unknown；重启/新运行不清零；查询/下载/复用不计；取消后不创建新sending；在途结果仍收存。

## 验证入口（本卡实现相应文件后执行）

```bash
python -m pytest -q tests/production/test_operations.py
```

**交付要求**：操作协议及假服务故障矩阵须通过；未调用的真实Provider须标未测。失败按具体窗口修，不增加全流程重试。

## 执行记录

**验证：本地软件检查通过；真实 Provider 未调用。** 在 `codex/s6-production` 的 S6 实施工作区，运行 `python -m pytest -q tests/production/test_operations.py`：17 passed。接收计数器使用临时 SQLite，覆盖额度竞争、固定提交身份、旧 epoch、取消、明确未发送与未知状态、查询未找到、模式授权、MODEL/VOICE 不占生成次数，以及实际 adapter 与授权服务身份不一致。

未覆盖：真实服务响应/计费规则、平台网络故障；不得将协议测试解释为真实制作通过。
