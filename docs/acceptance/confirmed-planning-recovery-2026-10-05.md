# 已确认创作方案：Planning 恢复修复

日期：2026-10-05。状态：软件验证通过，真实恢复未执行。

## 现场证据

作品 `cr_0f01f75915334b108f73f3c68f0eae0e`、Attempt `fa_64ef5e96b8fdce0e6ad7d9074ef61bf2` 的规划阶段失败。对照当前确认方案：SCRIPT 完全相同；SCENES 从873字符增至1063字符，追加声音设计；TREATMENT 从336字符缩至145字符，声音段被移走。原确认校验正确拒绝，非素材供应或 Build 失败。

根因：初始与局部修复提示同时要求写四份规划文件及保持确认三文件只读；确认文件仅不存在时写入，模型已经写坏的草稿不能由程序恢复。

## 最小修复

- 单一 canonical 映射复用已确认 script/scenes/treatment + sound，不重新解析或生成用户原文。
- 未提交差异先校验并按原字节 SHA 归档，再原子恢复；重复中断复用同内容归档。已有历史字节不符拒绝覆盖。
- 初始、一次局部修复及中断恢复进入验证前均走同一恢复逻辑；模型仅交付 MATERIAL_PLAN / MATERIAL_REQUIREMENTS JSON。
- 已冻结规划差异或缺失、异常文件类型、文件/目录 symlink 保持拒绝；错误路径不再触发另一模型修复。
- 原 Plan 身份/context_refs、Need 编译、requirements 及 Truth 校验保留。无确认方案仍沿原四文件创作交付。

## 验证

扩展既有 Planning 集成测试，无新平行测试文件：初始及 repair 两次移动声音段、归档去重、有效 Plan 重入零模型调用、冻结拒绝、文件 symlink，以及模型返回后将 planning 目录替换为 symlink；外部目录未写入，未继续派发修复模型。

最终全量 **701 passed、5 skipped（43.11秒）**；compileall、115技能与执行合同、git diff check通过。Astra 前置及最终复核 CONTINUE。

未修改真实 Attempt/确认方案/审核结果，未执行真实模型、Provider、E2E、恢复制作或服务重启，未消耗作品授权。实际作品仍处于原失败状态，当前证据仅证明软件修复。
