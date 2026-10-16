# S6-06 · V1素材核心迁入与作用域适配

状态：**NOT_STARTED**；代码/测试目标尚待实现或接入。

- **依赖**：S6-01、S6-02。
- **需求主/协作覆盖**：V2-EXP-011, V2-EXP-012, V2-EXP-021, V2-EXP-031, V2-EXP-034。
- **目标与合同**：[可执行设计](../15_IMPLEMENTATION_DESIGN.md)；[任务包共同约定](S6_IMPLEMENTATION_PLAN.md#2-每张卡开始与完成的共同约定)。
- **预计落点**：easel/materials/：V1 domain/library/store/reuse/dedup/semantic_index；easel/production/materials.py；tests/production/test_materials_core.py。
- **执行分支建议**：`codex/s6-06-materials-core`。

## 实施步骤

1. 从固定V1 SHA按能力迁入M01/M02，保留来源和license归属；不复制用户库/历史Attempt。
2. LibraryVisibility管理本机拥有者/画像的库内可见范围，UseContext携带work_id及本次用途；不要把work_id并入所有库资产的隔离主键。同画像已授权资产可跨作品复用，current_creation_only绑定源work；无画像默认本作品范围，不能伪造Creator。
3. ingest_input/promotion/candidates/select形成稳定asset_ref与digest；参考与可剪入分开，接受成片不自动授权全参考库复用。
4. 适配旧already_used逻辑：本片恢复和局部修订可复用原选择。语义索引不可用须明示metadata结果而非伪称语义检索。

## 通过标准与负例

内容篡改/路径逃逸/symlink/越权跨画像拒绝；重复入库幂等；current_creation_only遵守；同片恢复及同画像不同作品可按许可复用；无画像不见他人资产，后续归类不自动扩大素材权限；索引缺失不假成功；旧测试意图在新fixture重跑。

## 验证入口（本卡实现相应文件后执行）

```bash
python -m pytest -q tests/production/test_materials_core.py tests/production/test_reference_guard.py
```

**交付要求**：新V2测试库能真实入库/检索/选用并保护引用；无历史数据迁移。

## 执行记录

**验证：NOT_TESTED。** 实施时记录受测提交、实际命令/结果及未覆盖项。
