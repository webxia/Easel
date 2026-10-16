# S6-06 · V1素材核心迁入与作用域适配

状态：**NOT_STARTED — 实施内容已定义，依赖满足后可执行；代码/测试目标尚未创建或未接入。**

- **依赖**：S6-01、S6-02。依赖条件按实际产物满足，不只看文档状态；未满足可准备只读定位，不假报完成。
- **需求主/协作覆盖**：V2-EXP-011, V2-EXP-012, V2-EXP-021, V2-EXP-031, V2-EXP-034。
- **目标与合同**：[可执行设计](../15_IMPLEMENTATION_DESIGN.md)；[任务包共同约定](S6_IMPLEMENTATION_PLAN.md#2-每张卡开始与完成的共同约定)。本卡路径均为仓库相对路径，标明新建处是待实现目标。
- **预计落点**：easel/materials/：V1 domain/library/store/reuse/dedup/semantic_index；easel/production/materials.py；tests/production/test_materials_core.py。
- **执行分支建议**：`codex/s6-06-materials-core`，从具备依赖成果的受审查版本创建；不自动合并保护主线。

## 实施步骤

1. 从固定V1 SHA按能力迁入M01/M02，保留来源和license归属；不复制用户库/历史Attempt。
2. LibraryVisibility管理本机拥有者/画像的库内可见范围，UseContext携带work_id及本次用途；不要把work_id并入所有库资产的隔离主键。同画像已授权资产可跨作品复用，current_creation_only绑定源work；无画像默认本作品范围，不能伪造Creator。
3. ingest_input/promotion/candidates/select形成稳定asset_ref与digest；参考与可剪入分开，接受成片不自动授权全参考库复用。
4. 适配旧already_used逻辑：本片恢复和局部修订可复用原选择。语义索引不可用须明示metadata结果而非伪称语义检索。

## 通过标准与负例

内容篡改/路径逃逸/symlink/越权跨画像拒绝；重复入库幂等；current_creation_only遵守；同片恢复及同画像不同作品可按许可复用；无画像不见他人资产，后续归类不自动扩大素材权限；索引缺失不假成功；旧测试意图在新fixture重跑。

## 验证入口（本卡实现相应文件后执行）

以下命令从仓库根、受测虚拟环境执行；新test文件由本卡创建，当前不存在不代表可跳过。现有pytest发现范围和前端命令沿用项目实际入口，无付费服务默认以测试替身替代。

```bash
python -m pytest -q tests/production/test_materials_core.py tests/production/test_reference_guard.py
```

新V2测试库能真实入库/检索/选用并保护引用；无历史数据迁移。

## 范围、回退与交接

仅修改本卡及必要依赖接口；若合同需变化先更新统一设计和受影响任务，不另创同义接口。新增能力启用前不得写用户真实运行库；本轮未授权真实模型或媒体服务调用、旧数据迁移、生产服务重启或自动发布。后续具体任务已有授权继续有效；许可本地媒体的解码、渲染、检查与离线协议测试按共同约定执行。

失败保留可用产物与证据，只回退本任务代码/测试数据，不删除用户outputs/画像；不能用修改需求换PASS。完成记录实际HEAD、命令/输出、未测平台/服务、变更范围和下一依赖任务；更新当前状态。**运行结果：NOT_TESTED。**
