# S6-11 · 创作主线、首版与自检接通

状态：**NOT_STARTED**；代码/测试目标尚待实现或接入。

- **依赖**：S6-04、S6-05、S6-07、S6-08、S6-09、S6-10。
- **需求主/协作覆盖**：V2-EXP-001, V2-EXP-004, V2-EXP-005, V2-EXP-006, V2-EXP-014, V2-EXP-015, V2-EXP-016, V2-EXP-032, V2-EXP-033。
- **目标与合同**：[可执行设计](../15_IMPLEMENTATION_DESIGN.md)；[任务包共同约定](S6_IMPLEMENTATION_PLAN.md#2-每张卡开始与完成的共同约定)。
- **预计落点**：easel/production/graph.py、planning.py、quality.py；ProductionPage/Chat作品路由；tests/production/test_creation_flow.py、test_quality.py。
- **执行分支建议**：`codex/s6-11-creation-first-cut`。

## 实施步骤

1. 接通输入依据→方向→planning run产生完整方案摘要/展开→一次确认→production run读取冻结方案→真实选材→原生编辑→渲染→技术与视听检查。确认前规划恢复和确认后制作分别持久化，假工具集成与真实能力边界分别标记。
2. 方案固定事实/核心观点/必用原声，导演镜头可适配；实际素材到来后更新制作计划，不重问整片要求。
3. 无必要的正常阶段不问用户；实质变更/额度/服务缺口保存NeedDecision，resume只解决该决定及受影响任务。
4. 技术检测与实际视听模型审查分开，finding有位置/证据；候选、自检失败预览、可审阅首版严格区分；无模态覆盖不报全片通过。
5. 无新证据/技术上限后停止该循环，保留产物与诊断；所有步骤接入工作台，chat不得再并行用旧Skill生成另一片。

## 通过标准与负例

同一确认一个运行；必用/观点不丢；镜头范围内适配不新增审批；故障回受影响节点；候选未检不标首版；黑场/静音有意留白不机械删；技术PASS不能自动Creator接受；fake整链仅软件证据。

## 验证入口（本卡实现相应文件后执行）

```bash
python -m pytest -q tests/production/test_creation_flow.py tests/production/test_quality.py
node --test tests/frontend/productionProgress.test.mjs
npm --prefix web/frontend run build
```

**交付要求**：主线从真实API连到编辑器和检查，至少无付费测试素材整链可跑；真实模型自主首版由S6-14经授权确认。

## 执行记录

**验证：NOT_TESTED。** 实施时记录受测提交、实际命令/结果及未覆盖项。
