# S6-12 · 自然语言修订、版本接受与内容库

状态：**NOT_STARTED — 实施内容已定义，依赖满足后可执行；代码/测试目标尚未创建或未接入。**

- **依赖**：S6-02、S6-05、S6-11。依赖条件按实际产物满足，不只看文档状态；未满足可准备只读定位，不假报完成。
- **需求主/协作覆盖**：V2-EXP-007, V2-EXP-008, V2-EXP-017, V2-EXP-026, V2-EXP-027, V2-EXP-034。
- **目标与合同**：[可执行设计](../15_IMPLEMENTATION_DESIGN.md)；[任务包共同约定](S6_IMPLEMENTATION_PLAN.md#2-每张卡开始与完成的共同约定)。本卡路径均为仓库相对路径，标明新建处是待实现目标。
- **预计落点**：easel/production/revisions.py；service/artifact索引；OutputsPage/作品审阅组件；tests/production/test_revision_acceptance.py；tests/frontend/productionReview.test.mjs。
- **执行分支建议**：`codex/s6-12-revision-acceptance`，从具备依赖成果的受审查版本创建；不自动合并保护主线。

## 实施步骤

1. 自然语言反馈绑定具体output版本生成ChangeSet，比较直接依赖和语义影响；普通局部无新费用直接执行，扩大影响/新增生成按既定说明确认。
2. 保护声音/文字/不变场景，复用未改成果；工程新版本、输出版本和检查绑定hash，保留旧版。
3. 明确接受具体reviewable输出，保存内容库并可比较/导出；作品接受与导演接受分开，不自动发布。
4. fork旧作品建新授权，assignment归属变更不重做/不扩大素材范围；全入口引用删除保护复核，删除聊天不删媒体。
5. 接通删除影响预览→用户明确删除作品/历史版→服务事务解除该范围保留引用→只清理无其他引用文件。删除已接受版本明确移除接受选择，不自动换版；共享资产、用户inbox原件与在途结果保留，过期预览拒绝。

## 通过标准与负例

只改字号不生图/配音；只换画面保留指定声音文案；新增生成先说明；未确认扩大影响不执行；接受不是最新文件猜测；旧版可选；fork不复制额度；归属变更不换人设快照；旧DELETE不能绕过，明确授权删除版本/作品可成功且不伤共享资产；在途结果先收存再对账清理。

## 验证入口（本卡实现相应文件后执行）

以下命令从仓库根、受测虚拟环境执行；新test文件由本卡创建，当前不存在不代表可跳过。现有pytest发现范围和前端命令沿用项目实际入口，无付费服务默认以测试替身替代。

```bash
python -m pytest -q tests/production/test_revision_acceptance.py tests/production/test_reference_guard.py tests/test_artifact_archive.py
node --test tests/frontend/productionReview.test.mjs tests/frontend/artifacts.test.mjs
npm --prefix web/frontend run lint
npm --prefix web/frontend run build
```

审阅→局部新版→明确接受→内容库形成真实可用链；保留所有未完成真实验收项。

## 范围、回退与交接

仅修改本卡及必要依赖接口；若合同需变化先更新统一设计和受影响任务，不另创同义接口。新增能力启用前不得写用户真实运行库；本轮未授权真实模型或媒体服务调用、旧数据迁移、生产服务重启或自动发布。后续具体任务已有授权继续有效；许可本地媒体的解码、渲染、检查与离线协议测试按共同约定执行。

失败保留可用产物与证据，只回退本任务代码/测试数据，不删除用户outputs/画像；不能用修改需求换PASS。完成记录实际HEAD、命令/输出、未测平台/服务、变更范围和下一依赖任务；更新当前状态。**运行结果：NOT_TESTED。**
