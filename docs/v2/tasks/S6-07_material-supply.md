# S6-07 · 外部供应、权益与生成适配

状态：**NOT_STARTED — 实施内容已定义，依赖满足后可执行；代码/测试目标尚未创建或未接入。**

- **依赖**：S6-03、S6-06。依赖条件按实际产物满足，不只看文档状态；未满足可准备只读定位，不假报完成。
- **需求主/协作覆盖**：V2-EXP-012, V2-EXP-013, V2-EXP-021, V2-EXP-025, V2-EXP-031, V2-EXP-033。
- **目标与合同**：[可执行设计](../15_IMPLEMENTATION_DESIGN.md)；[任务包共同约定](S6_IMPLEMENTATION_PLAN.md#2-每张卡开始与完成的共同约定)。本卡路径均为仓库相对路径，标明新建处是待实现目标。
- **预计落点**：easel/materials/application、providers迁入子集；easel/production/providers/；tests/production/test_material_supply.py、test_generation_adapter.py。
- **执行分支建议**：`codex/s6-07-material-supply`，从具备依赖成果的受审查版本创建；不自动合并保护主线。

## 实施步骤

1. 迁入M03/04，库内候选优先、有限外部回退、下载/重定向/大小限制、技术资格、权益和署名证据。
2. 供应不足返回gap/generation_route，由导演决定适配；检索循环不发收费生成。
3. M05接OperationService，不搬confirmed_paid布尔/旧报价/阶段budget；IMAGE与VIDEO各有具名服务adapter、配置/模式能力及fake回执合同，可以同厂商或不同厂商。真实服务默认不调用；只实现生图不能将本卡整体标完成。
4. VOICE接入归S6-10，不假设旧MiniMax全局Voice可用于句级旁白。缺配置/能力明确capability_unavailable且列未完成模态；S6-14只做真实验收，不承担隐含补开发。

## 通过标准与负例

库内命中无外部调用；公共URL不自动有rights；私网重定向/损坏超大文件拒绝；署名进入产物依赖；同operation查询下载不再提交；回执无法核实保留unknown；有限失败停止。

## 验证入口（本卡实现相应文件后执行）

以下命令从仓库根、受测虚拟环境执行；新test文件由本卡创建，当前不存在不代表可跳过。现有pytest发现范围和前端命令沿用项目实际入口，无付费服务默认以测试替身替代。

```bash
python -m pytest -q tests/production/test_material_supply.py tests/production/test_generation_adapter.py tests/production/test_operations.py
```

新素材API能供应合格候选或明确gap，生成通过唯一准入；真实Provider未试部分明确NOT_TESTED。

## 范围、回退与交接

仅修改本卡及必要依赖接口；若合同需变化先更新统一设计和受影响任务，不另创同义接口。新增能力启用前不得写用户真实运行库；本轮未授权真实模型或媒体服务调用、旧数据迁移、生产服务重启或自动发布。后续具体任务已有授权继续有效；许可本地媒体的解码、渲染、检查与离线协议测试按共同约定执行。

失败保留可用产物与证据，只回退本任务代码/测试数据，不删除用户outputs/画像；不能用修改需求换PASS。完成记录实际HEAD、命令/输出、未测平台/服务、变更范围和下一依赖任务；更新当前状态。**运行结果：NOT_TESTED。**
