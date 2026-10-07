# Planning → Material 独立边界矩阵

执行：

```bash
.venv/bin/python tests/planning_material_matrix/run.py
```

初始25风险案例结果22 PASS / 1 FAIL / 2 CONTRACT_GAP保留。A–D为run-015的25 PASS；R0–R3沿用同一执行器扩展36风险组/53参数化场景，run-017为53 PASS/0 FAIL/0 GAP/0未执行；已知失败不 xfail、不跳过。默认pytest不收集cases.py。局部诊断可用 `--case test_21`，仅局部结果不能认领完整矩阵。

`--output` 可指定独立记录根目录。每次创建 run-NNN，保存生产与真实现场完整性摘要、fixture摘要、Expected/Actual、异常栈、pytest/JUnit及对账。最终测试源码快照以 .py.txt 保存，避免历史 conftest 自动进入默认pytest；源字节/SHA保持。

case文件复用已有高价值合同断言，新增模态组合、真实persist、确认稿/Truth回放和真实Owner调度交接。内部生产模块不换成返回成功的替身；仅Gateway/模型/观察响应是确定性测试输入，Local检索/接收/技术检查实际执行。集成保持Rights UNKNOWN、Observation unknown、Gate MATERIAL_NOT_READY，不派发Authoring或视频阶段。

conftest隔离临时Creation/workspace/library/config，阻断外网、真实runtime/config文件、未替换Gateway、外部进程与Hypit CLI。历史fixture原件不变，派生变体只在内存或临时目录中。无真实凭证、采购、生成或E2E。

明确合同违规记FAIL，正确拒绝负例记PASS。未定义/冲突规则通过 `trace.gap` 独立报告CONTRACT_GAP，不计为PASS，不通过修改生产规则完成测试。本轮唯一正式结果、装配日志与根因建议见 `docs/acceptance/planning-material-boundary-matrix-2026-10-06.md`。
