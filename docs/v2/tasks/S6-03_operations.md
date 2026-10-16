# S6-03 · 外部操作准入、生成次数与未知结果

状态：**NOT_STARTED — 实施内容已定义，依赖满足后可执行；代码/测试目标尚未创建或未接入。**

- **依赖**：S6-01。依赖条件按实际产物满足，不只看文档状态；未满足可准备只读定位，不假报完成。
- **需求主/协作覆盖**：V2-EXP-006, V2-EXP-013, V2-EXP-024, V2-EXP-025, V2-EXP-026, V2-EXP-033。
- **目标与合同**：[可执行设计](../15_IMPLEMENTATION_DESIGN.md)；[任务包共同约定](S6_IMPLEMENTATION_PLAN.md#2-每张卡开始与完成的共同约定)。本卡路径均为仓库相对路径，标明新建处是待实现目标。
- **预计落点**：easel/production/operations.py、providers/base.py；tests/production/test_operations.py、fake_provider.py。
- **执行分支建议**：`codex/s6-03-operations`，从具备依赖成果的受审查版本创建；不自动合并保护主线。

## 实施步骤

1. 实现submit/observe/receive及reserved/sending/submitted/unknown/terminal转换；reserved→sending同一条件更新核验run/task修订、owner_epoch、取消、provider+model/mode允许清单与额度。过期worker不能新建或发送；原回执可按既有operation_id核实接收。
2. 操作ID由业务请求创建并固定服务/模式及配置版本；重放同ID复用，相同prompt的明确新生成用新ID。IMAGE/VIDEO计次，VOICE/MODEL留回执但不占额度；确认前planning/preview只引用本用途服务授权，不取得生产生成权限。
3. 假Provider在本地持久记录接收次数，支持可查询/不可查询两种模式；每个发送窗口提供故障注入。
4. 有task_id/请求键时观察原任务，未知不能自动重发；结果接收与技术核验独立重试，服务凭证只在adapter取得。

## 通过标准与负例

争最后额度至多一条发送；A预留后暂停、B接管、A恢复时A不能发送，B不重发已sending/unknown操作；有剩余额度但同服务未授权模式仍拒绝；发送前可证明失败释放；对端已接受但回执丢失不重发；不可核实保持unknown；重启/新运行不清零；查询/下载/复用不计；取消后不创建新sending；在途结果仍收存。

## 验证入口（本卡实现相应文件后执行）

以下命令从仓库根、受测虚拟环境执行；新test文件由本卡创建，当前不存在不代表可跳过。现有pytest发现范围和前端命令沿用项目实际入口，无付费服务默认以测试替身替代。

```bash
python -m pytest -q tests/production/test_operations.py
```

操作协议及假服务故障矩阵通过；未调用真实Provider。失败按具体窗口修，不增加全流程重试。

## 范围、回退与交接

仅修改本卡及必要依赖接口；若合同需变化先更新统一设计和受影响任务，不另创同义接口。新增能力启用前不得写用户真实运行库；本轮未授权真实模型或媒体服务调用、旧数据迁移、生产服务重启或自动发布。后续具体任务已有授权继续有效；许可本地媒体的解码、渲染、检查与离线协议测试按共同约定执行。

失败保留可用产物与证据，只回退本任务代码/测试数据，不删除用户outputs/画像；不能用修改需求换PASS。完成记录实际HEAD、命令/输出、未测平台/服务、变更范围和下一依赖任务；更新当前状态。**运行结果：NOT_TESTED。**
