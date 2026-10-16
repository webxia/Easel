# S6-02 · 作品命令、输入登记与旧入口保护

状态：**NOT_STARTED**；代码/测试目标尚待实现或接入。

- **依赖**：S6-01。
- **需求主/协作覆盖**：V2-EXP-002, V2-EXP-003, V2-EXP-005, V2-EXP-011, V2-EXP-020, V2-EXP-027, V2-EXP-028, V2-EXP-029, V2-EXP-034。
- **目标与合同**：[可执行设计](../15_IMPLEMENTATION_DESIGN.md)；[任务包共同约定](S6_IMPLEMENTATION_PLAN.md#2-每张卡开始与完成的共同约定)。
- **预计落点**：easel/production/service.py；web/production_api.py；web/app.py；tests/production/test_work_api.py、test_reference_guard.py；现有outputs/persona/upload测试。
- **执行分支建议**：`codex/s6-02-work-api`。

## 实施步骤

1. 按设计 §4 接入创建/分页列表/查询、输入、方案确认、取消/追加/接受和删除影响合同。POST plans生成持久planning run；确认只创建一个production run并从冻结方案继续，不重做规划。列表包含未出片及无画像作品。
2. 复用opaque附件ref且检查来源会话/范围，登记稳定input_id、摘要、必用/参考/可用用途与原声区间；支持混合输入。
3. 基础频道/导演/默认记录的服务层及归属命令，确认时解析设置与画像依据；未接受导演只可显式作为本片试片。
4. 新资产开放前，旧GET output/media、下载/打包/枚举入口拒绝_production私有根（含数据库/WAL/检查点和符号链接别名），artifact入口仅放行登记的可展示产物；旧DELETE output/persona检查引用。只隐藏目录不够。删除聊天不自动取消独立作品。
5. router沿用local_write_guard，不改现有聊天/发布行为；API错误清晰返回对应版本和需处理问题。

## 通过标准与负例

重复确认只产生一个production run且不重新规划；过期确认409；外会话附件拒绝；三类组合可登记；任意路径拒绝；私有DB/内部证据直接URL、编码路径、符号链接和打包读取均拒绝；新旧删除入口保护引用，删除影响合同允许S6-12实现合法删除；删画像对频道引用明确处理；删除聊天后仍从GET works找回未出片作品；无画像不读取旁人profile。

## 验证入口（本卡实现相应文件后执行）

```bash
python -m pytest -q tests/production/test_work_api.py tests/production/test_reference_guard.py tests/test_persona_security.py tests/test_local_write_guard.py tests/test_output_delete_protect.py tests/test_output_paths.py
```

**交付要求**：真实FastAPI路由可在TestClient使用；引用保护覆盖旧入口；确认只持久派发，不虚报成片。

## 执行记录

**验证：NOT_TESTED。** 实施时记录受测提交、实际命令/结果及未覆盖项。
