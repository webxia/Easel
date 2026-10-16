# S6-06 · V1素材核心迁入与作用域适配

状态：**IMPLEMENTED_OFFLINE_VERIFIED**；素材核心已真实迁入并接入生产供应，真实跨平台/模型服务与生产质量仍按下述范围验收。

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

实施工作树：`codex/s6-production`，本次验证时 HEAD `e923332a1492b37242855632958daf6bb79ba073` 加当前未提交实现。固定 V1 来源、许可证、逐文件保留/删除边界见 [源码迁入记录](../../../easel/materials/MIGRATION.md)。未读取或迁移旧素材/运行数据。

已实现 `easel/materials/`、`production/materials.py` 与实际 `supply_tasks.py` 适配：入库、资格重验、显式跨作品提升、元数据/语义索引降级、哈希/路径验证、引用保护及明确删除后的安全回收。same-work 恢复允许复用；画像为空不会借用其他人资产。主线以不可混淆的 artifact ID 继续剪辑，必用素材缺证据时返回具体阻塞，不替换成图库。

实际执行（2026-10-17，macOS arm64，Python 3.12）：

```bash
python -m pytest -q tests/production/test_materials_core.py tests/production/test_materials_reference_guard.py tests/production/test_materials_dedup.py tests/production/test_materials_rights.py tests/production/test_material_supply.py tests/production/test_generation_adapter.py tests/production/test_operations.py tests/production/test_supply_tasks.py tests/production/test_public_facts.py
```

结果 **122 passed（1.35 秒）**；此命令含 S6-07、S6-08 公共事实检索与操作服务集成。素材负例覆盖越界/symlink/篡改、同内容不同权限记录、同片与同画像授权复用、无画像、参考用途、授权变化、索引缺失、并发入库、共享对象引用及安全回收。

真实 embedding 服务、真实用户库/历史数据迁移、Ubuntu/Windows 和完整生产质量 **NOT_TESTED**。库引用和生产域是两个数据库，先保留引用以防在用文件被删；删除作品后由合法删除流程明确释放对应引用，不自动扫旧数据。
