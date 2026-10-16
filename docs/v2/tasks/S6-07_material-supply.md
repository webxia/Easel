# S6-07 · 外部供应、权益与生成适配

状态：**NOT_STARTED**；代码/测试目标尚待实现或接入。

- **依赖**：S6-03、S6-06。
- **需求主/协作覆盖**：V2-EXP-012, V2-EXP-013, V2-EXP-021, V2-EXP-025, V2-EXP-031, V2-EXP-033。
- **目标与合同**：[可执行设计](../15_IMPLEMENTATION_DESIGN.md)；[任务包共同约定](S6_IMPLEMENTATION_PLAN.md#2-每张卡开始与完成的共同约定)。
- **预计落点**：easel/materials/application、providers迁入子集；easel/production/providers/；tests/production/test_material_supply.py、test_generation_adapter.py。
- **执行分支建议**：`codex/s6-07-material-supply`。

## 实施步骤

1. 迁入M03/04，库内候选优先、有限外部回退、下载/重定向/大小限制、技术资格、权益和署名证据。
2. 供应不足返回gap/generation_route，由导演决定适配；检索循环不发收费生成。
3. M05接OperationService，不搬confirmed_paid布尔/旧报价/阶段budget；IMAGE与VIDEO各有具名服务adapter、配置/模式能力及fake回执合同，可以同厂商或不同厂商。真实服务默认不调用；只实现生图不能将本卡整体标完成。
4. VOICE接入归S6-10，不假设旧MiniMax全局Voice可用于句级旁白。缺配置/能力明确capability_unavailable且列未完成模态；S6-14只做真实验收，不承担隐含补开发。

## 通过标准与负例

库内命中无外部调用；公共URL不自动有rights；私网重定向/损坏超大文件拒绝；署名进入产物依赖；同operation查询下载不再提交；回执无法核实保留unknown；有限失败停止。

## 验证入口（本卡实现相应文件后执行）

```bash
python -m pytest -q tests/production/test_material_supply.py tests/production/test_generation_adapter.py tests/production/test_operations.py
```

**交付要求**：新素材API能供应合格候选或明确gap，生成通过唯一准入；真实Provider未试部分明确NOT_TESTED。

## 执行记录

**验证：NOT_TESTED。** 实施时记录受测提交、实际命令/结果及未覆盖项。
