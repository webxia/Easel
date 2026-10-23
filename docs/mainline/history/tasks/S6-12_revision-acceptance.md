# S6-12 · 自然语言修订、版本接受与内容库

> **HISTORICAL — 原阶段记录/研究，保留当时结论，不表示当前部署、授权或待办。** 当前入口见[主线导航](../../INDEX.md)。
> **调度状态：CLOSED · 2026-10-19**。用户决定关闭本卡独立研发排程：既有实现和软件验收结果保持原样，仅作为历史交付与回归依据；不再从旧实施步骤重新派发任务。后续确有实证缺陷时，仅纳入[当前三项主线](../../project/status.md#唯一研发下一动作)做局部修复。CLOSED 不代表全部真实模型、音画质量、完整规格或 Creator 接受已通过。

状态：**IMPLEMENTED / OFFLINE_INTEGRATION_VERIFIED**。自然语言局部修订、扩大影响确认、版本接受/比较、内容库和基于具体旧版新作已接通。

- **依赖**：S6-02、S6-05、S6-11。
- **需求主/协作覆盖**：V2-EXP-007, V2-EXP-008, V2-EXP-017, V2-EXP-026, V2-EXP-027, V2-EXP-034。
- **目标与合同**：[可执行设计](../../architecture/contracts.md)；[任务包共同约定](../../project/tasks/S6_IMPLEMENTATION_PLAN.md#2-每张卡开始与完成的共同约定)。
- **预计落点**：easel/production/revisions.py；service/artifact索引；OutputsPage/作品审阅组件；tests/production/test_revision_acceptance.py；tests/frontend/productionReview.test.mjs。
- **执行分支建议**：`codex/s6-12-revision-acceptance`。

## 实施步骤

1. 自然语言反馈绑定具体output版本生成ChangeSet，比较直接依赖和语义影响；普通局部无新费用直接执行，扩大影响/新增生成按既定说明确认。
2. 保护声音/文字/不变场景，复用未改成果；工程新版本、输出版本和检查绑定hash，保留旧版。
3. 明确接受具体reviewable输出，保存内容库并可比较/导出；作品接受与导演接受分开，不自动发布。
4. fork旧作品建新授权，assignment归属变更不重做/不扩大素材范围；全入口引用删除保护复核，删除聊天不删媒体。
5. 接通删除影响预览→用户明确删除作品/历史版→服务事务解除该范围保留引用→只清理无其他引用文件。删除已接受版本明确移除接受选择，不自动换版；共享资产、用户inbox原件与在途结果保留，过期预览拒绝。

## 通过标准与负例

只改字号不生图/配音；只换画面保留指定声音文案；新增生成先说明；未确认扩大影响不执行；接受不是最新文件猜测；旧版可选；fork不复制额度；归属变更不换人设快照；旧DELETE不能绕过，明确授权删除版本/作品可成功且不伤共享资产；在途结果先收存再对账清理。

## 验证入口（本卡实现相应文件后执行）

```bash
python -m pytest -q tests/production/test_revision_acceptance.py tests/production/test_reference_guard.py tests/test_artifact_archive.py
node --test tests/frontend/productionReview.test.mjs tests/frontend/artifacts.test.mjs
npm --prefix web/frontend run lint
npm --prefix web/frontend run build
```

**交付要求**：审阅→局部新版→明确接受→内容库形成真实可用链；保留所有未完成真实验收项。

## 执行记录

**删除子项：本地软件检查通过。** `codex/s6-production` 工作区新增 `deletion.py` 与 schema 2（作品/产物 tombstone、持久清理队列）；隔离 Python 3.12 执行 `python -m pytest -q tests/production/test_deletion.py`：15 passed。验证过期影响预览、命令重放、已接受选择移除、共享依赖/原件/导演证据保留、在途回执晚到、符号链接/变更文件保护、v1 schema 前向迁移、API 在清理前拒绝已删成果，以及独立素材库引用释放失败和文件暂时锁定后的持久重试。维护循环将用户取消传给独立渲染器，完成竞争时保存非可审阅回执；服务退出不当成用户取消。没有操作用户现有生产文件。

另运行真实本地 FFmpeg 的 `tests/production/test_render_local.py::test_cancel_is_observed_and_restart_recovers_interrupted_local_job`：1 passed；未调用付费服务。

该记录只覆盖删除服务；自然语言修订、审阅 UI、完整内容库及真实创作验收由本卡其他子项与 S6-14 集成记录补齐。后台清理按队列复核引用，执行命令成功不等于文件清理完成。

### 本轮集成记录（2026-10-17）

test_revision_pipeline真实本地首版→接受→自然语言视觉调整→再渲染/QC→明确接受新版通过；旧文件和接受记录保持到用户切换。test_revision_acceptance覆盖扩大影响新planning run及精确旧版fork：复制为新作参考，不继承旧授权、接受状态或素材使用权。Creator真实接受仍未测。
