# S6-07 · 外部供应、权益与生成适配

状态：**IMPLEMENTED_OFFLINE_VERIFIED**；外部供应、IMAGE/VIDEO 实际 HTTP 适配和主线衔接已实现；真实供应商调用仍 NOT_TESTED。

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

实施工作树：`codex/s6-production`，验证时 HEAD `e923332a1492b37242855632958daf6bb79ba073` 加当前未提交实现。固定 V1 M03/M04/M05 子集来源、官方协议、许可边界及配置说明见 [源码迁入记录](../../../easel/materials/MIGRATION.md)。未安装依赖或调用真实服务。

迁入实际下载/权益/有限供应代码，新增 Pexels 和显式公共来源、MiniMax image-01 与 H3/H3-Max HTTP 适配；生成只经 OperationService 的具名服务/模型/模式准入。图片先落私有回执，视频提交/查询/下载分开；unknown 不重发，查询/下载不计新调用。公开 URL 无权利证据不能剪入，DNS 固定连接和每跳重定向验证阻止私网/越界来源，真实媒体检查拒绝损坏内容。

`SupplyTasks.supply` 已读取已确认方案、必用/参考输入并产出作品素材 IDs；合格素材/已提交 operation 恢复不重取或重发。外部不足时由已授权创作模型提出语义补料请求，程序掌握服务身份/次数/权益；决策在发送前持久化。缺配置、权限、额度或素材资格均返回明确 needs_decision。`configured_supply` 与 `supply_capabilities` 由 runtime 使用，默认不把生成服务有 key 当作素材许可。

2026-10-17 与 S6-06 联合执行其记录中的 9 文件命令，结果 **122 passed（1.35 秒）**。其中实际 Store + OperationService + HTTP MockTransport 的 supply 主链包含必用资格/无授权零发送/unknown 不重发、模型选择补料、IMAGE 只提交一次、VIDEO 提交→单次查询→下载→真实 ffprobe 入库→edit，以及重复执行复用资产；取消/所有权变化后不发下一次检索或下载，缺外部配置不降级为自动生成。VIDEO 测试使用新造本地四秒视频，不调用生成服务。

真实 Pexels/MiniMax HTTP、真实生成质量/自然度、素材语义适配、Ubuntu/Windows 均 **NOT_TESTED**；VOICE 属 S6-10。署名 metadata 保留并交给产物依赖，最终 credits 文件/下载入口由制作主线集成验收，不拿单独保存字段冒充已完成用户导出。
