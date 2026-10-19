# S6-02 · 作品命令、输入登记与旧入口保护
> **调度状态：CLOSED · 2026-10-19**。用户决定关闭本卡独立研发排程：既有实现和软件验收结果保持原样，仅作为历史交付与回归依据；不再从旧实施步骤重新派发任务。后续确有实证缺陷时，仅纳入[当前三项主线](../04_CURRENT_STATE.md#唯一研发下一动作)做局部修复。CLOSED 不代表全部真实模型、音画质量、完整规格或 Creator 接受已通过。

状态：**IMPLEMENTED / OFFLINE_INTEGRATION_VERIFIED**。作品命令、输入登记、事件查询与旧入口保护已接通；删除采用影响预览、精确版本确认和延后文件清理。

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

**软件及本地媒体验证：已执行。真实模型/服务、真实自主生产及 Creator 接受不据离线结果宣称通过。** 整批受测代码与回归结果见 [S6-14](S6-14_integration-release.md)。

### 本轮集成记录（2026-10-17）

作品/附件/画像/删除/路径回归见 test_work_api、test_reference_guard、test_deletion 及既有安全用例。删除画像后同名重建产生新身份，不继承旧默认；旧作品快照保留。
