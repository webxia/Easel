# Workstream：低打扰 Creation 审核

## 目标

让用户只处理机器无法可靠代替的决定。已确认的创作方案必须完整进入冻结输入；确定性技术检查和有证据的自动判定由 Easel 完成；不确定的事实、权利、费用或最终创作取舍才暂停等待人。

## 不变量

- 不弱化 Creation 确认、Material Readiness、Attempt/Plan/SHA 身份、Hypit fingerprint/idempotency/reconciliation、Rights UNKNOWN、付费生成、付费 Build、最终输出审片及不发布边界。
- 不把模型推断记成来源事实；自动审核与人工审核、用户委托 Agent 审核分别留痕。
- 不要求用户逐行确认脚本元数据或重复确认同一生产动作。
- 未知 Rights、不可核费用、无输出或失败的技术检查继续阻断。

## 验收方向

- Creation 的显式确认快照包含聊天最终确认的结构化制作约束，并进入 Handoff/Planning 的哈希链。
- Script review 只为可验证事实主张创建人工待审项；纯场景指示、格式和制作约束由确定性分类处理。
- 有可靠、可追溯授权证据时自动 Rights admission；证据不足只呈现实际阻断资产与最少所需决定。
- Authoring 和技术 QC 不再重复询问已由“开始制作”覆盖的非付费步骤。
- Build 当前价格、授权记录和提交在一个明确操作中完成；UNKNOWN 价格不能以默认值批准。该批准不是服务商硬消费上限。
- 最终成片只要求一次创作取舍；技术、Truth/素材证据检查自动运行。通过后可自动设为 Selected Output，但永不自动发布。

## 顺序

依次处理 Proposal 快照/规划一致性、审核分类与 Rights 证据、低打扰操作台、回归与当前 T15 E2E 复测。一次只推进已具备确定证据的部分。
