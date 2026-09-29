# V1C-T09：AI 素材真实产品验证

状态：**SUPERSEDED / NEXT-STAGE PLANNED**。

本文件是原始假设的历史记录；其中“选择本地服务”已过期。当前 Image-01、Video V2、预置音色 T2A 的 Material Adapter 和隔离真实输出见 [T09A](v1c-t09-minimax-video.md) 与 [Generated Material Workstream](../workstreams/generated-material.md)。后续缺口转入 [T15 E2E 准备与产品验证](v1c-t15-e2e-readiness.md)。

原任务按 Hypit Generation Gateway 设计，现已退出正式产品链。用户明确的边界是 Material Layer 负责 AI 素材生成和准入，Hypit 只负责后续剪辑生产。旧 Task 的 Hypit endpoint、binding、auth、generation Build 前置条件不再适用。

下一阶段在选定本地 Image/Video/Voice 服务后，为 Material Layer 建立具体实现 Task 和逐模态验收。真实产品证据须覆盖：Need 与冻结输入 → 生成意图 → 本地 Adapter → 输出字节/来源/模型事实 → Inspect/Rights/Match/Bundle/Readiness → Production 选材 → Hypit 剪辑。没有真实输出时保持 `NOT_VERIFIED`；Rights 未知时保持 `MATERIAL_NOT_READY`。本文件不授权生成调用或付费执行。
