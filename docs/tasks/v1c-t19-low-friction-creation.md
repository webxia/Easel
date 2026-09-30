# V1C-T19：低打扰 Creation 审核与制作

状态：**已并入后续唯一实施 Task**。本文件保留历史根因和验证，不再作为并列执行方案；当前范围和完成条件以 [自主首版与 Director 全链执行](creator-autonomous-first-cut-2026-09-30.md) 为准，实际状态见 [Current State](../02_CURRENT_STATE.md)。

2026-09-30 授权策略修订：新委托明确包含无 Provider 费用合成的自动执行。后端在每次 Build 前核验正式 Pricing、Plan 和 fingerprint，并保存 0 美元批准及委托来源；不再要求零费用 Build 单独点击。未知或付费请求没有被该授权覆盖。下文“Build 一次明确操作”为旧基线；正式身份、权益、费用核验和最终审片语义继续保留。

## 已核实问题

- 聊天方案和确认内容只存在于前端对话；服务端 Preparation/Planning 只读取 Content Core、Truth Packet、Creator Context 和 Creative Mode。确认时的时长、节拍、静音、屏幕文字/人脸限制没有进入 Planning，因此当前 SCRIPT/MaterialPlan 与用户确认的 6-beat 方案漂移成 3 个 beat。
- Script claim ledger 把 Markdown 标题、段落分隔、镜头指示和制作备注都拆成待审文本；当前 27 个待审单元中并非 27 条需要用户判断的事实主张。
- Operator UI 为 Rights 录入暴露多字段并逐资产操作；Authoring 在已确认制作后仍有独立确认；Build 分“持久批准”和“提交”两个操作并分别弹窗；Final Review 把 Truth、Style、人工审片和 Selected Output 拆成多次操作。
- Preparation/API 之前在 Gate READY 后需要额外确认 Authoring，与“用户开始制作即授权非付费 Authoring”的低打扰策略冲突。当前改为首次确认后自动串行运行非付费 Authoring；Rights Gate 未 READY 时仍停止。

## 范围

- 显式确认时传递并哈希绑定对话中最终确认的结构化 Production Brief；禁止 Planning 从未冻结的隐含上下文自行猜测。
- 让 Truth gate 只为需要事实核实的具体主张创建人工待审项；创作意图、镜头动作、Markdown 元数据走确定性自动审查并留下可区分记录。
- Rights 仅依据当前具体素材可追溯的授权证据自动通过；未验证、证据冲突或身份/肖像限制仍阻断。聚合呈现真正需要人判断的异常，不要求重复填写系统已有元数据。
- Proposal 确认覆盖的非付费 Planning/Authoring/QC 自动串行执行；保留每次付费素材生成的明确操作。
- 将当前 Hypit Plan fingerprint、Pricing、批准与 Build submission 收敛到单一显式 UI 操作，后端继续执行完整 fingerprint、幂等、重复提交阻断及不确定结果对账。
- 将技术审查自动化；最终由用户对成片作一次通过/返工决定。通过后自动绑定当前 SHA 并选择 Selected Output；不发布。

## 非目标

- 不绕过权益证据、Hypit Runtime/Plan/Pricing/Approval、技术校验和资产 SHA 身份。
- 不猜测服务商许可或用户预算，不新增预算上限承诺。
- 不扩大到发布/社交平台操作，不更改 Material Layer V1.3 核心语义，不新建第二条制作主链。
- 不在确定的测试中调用付费 Provider；真实生成、Build 和发布仍分开记录。

## 验收条件

1. 方案确认、冻结 Handoff、Creative Planning 与最终 Production 内容一致；更改/过期的 brief 使旧 planning/selection/approval 失效。
2. 无事实性旁白/字幕的纯镜头脚本不产生逐行人工待审；出现无来源事实主张时只定位具体主张并送审/阻断。
3. Rights 自动 admission 必须有资产级、可追溯证据和适用范围；UNKNOWN/冲突/限制不会被自动改写为可用。
4. Proposal 确认后非付费 Authoring 与技术 QC 不再重复要求用户确认；门禁失败明确停止。
5. Build 只需一次明确用户操作；服务端复核当前 Plan/Pricing/fingerprint 后审批并至多提交一次；未知价格或提交不确定时不可重复 Build。
6. 最终视频技术/事实检查自动运行，用户只做一次创作通过/返工决定；通过后 Selected Output 绑定同一输出 SHA，不发布。
7. 新增确定性回归保护以上边界，并执行 T15 的测试、构建和验收。

## 已有进度

- 标准对话确认会传入最近对话并哈希绑定 `ProductionBrief`；Preparation、Handoff 和 Planning context 核验同一 brief。未知字段不由模型补猜，publication 仍必须为 false。
- Truth ledger 将确定性识别的镜头/制作指令记为 `AUTO_REVIEWED`，保留来源支持事实审查；审阅者证据可区分 `DELEGATE_REVIEWED` 和 `HUMAN_REVIEWED`。
- 已按官方许可页映射 Pexels License 与 Pixabay Content License，并在获取时持久化具体素材页面、许可条款 URL 与明示限制；未知许可继续阻断。商用 Pixabay 素材缺少品牌视觉证据时只将该项送入复核，不当作自动通过。官方依据：[Pexels License](https://www.pexels.com/license/) 与 [Pixabay Content License](https://pixabay.com/service/terms/)（2026-09-28 查阅）。
- Authoring 在用户明确开始后自动串行运行；Build 收敛为一次确认操作；最终审片通过后一次操作同时记录审片并设定当前 SHA 为 Selected Output。付费素材生成、Build 和发布仍有独立保护，自动化不代表自动发布。
- 当前 Creation 的 frozen Handoff 早于 `ProductionBrief` 契约，不能原地补写或伪造一致性。软件回归完成后已沿标准对话启动当前 Attempt；Preparation、Script/Truth Gate、Material Gate 均通过，非付费 Authoring 已因 Hypit markup root contract 失败，Build 尚未启动。
- 调试运行中，审阅面板默认折叠完整 SCRIPT 与逐句账本，只显示分类计数；运行状态每 5 秒自动跟踪，不要求用户停留盯进度。当前记录为待处理事实 0、人工复核 0、Codex 委托复核 22；委托复核与来源事实支持仍明确区分。
- Hypit 集成边界已增加确定性兼容：重试忽略纯 JSON 排版变化、Gate 可推导的 `qualified_need_ids` 缺失、经冻结身份核实的冗余 `identity`/`revision` 字段及素材清单重排；未知字段、身份不符、素材集合/SHA/来源/Need Match 改变仍阻断。Hypit Markup 文件头与旧式 Run manifest 的纠偏已自动化；失败时刷新 Easel 生成的任务书。真实 `hypit check` 曾发现 Author Source 根属性不属于 Hypit v0.2.7 契约；本次又证实 `time:Timeline.clock` 必须用 `{clock}` typed reference，不能用字符串。该格式现已加入首轮/修复指令、生成任务书和契约测试；修正后的 Attempt 正等待校验，当前 E2E 仍未通过。
- `AUTHORING_RUNNING` 在应用重启后可能没有对应的进程内任务。Operator 增加“恢复当前非付费 Authoring”操作；现有后端任务表使重复触发保持幂等：活任务继续复用，进程重启后的孤立状态才会重新派发。已为此补充回归测试。当前 T15 Attempt 已从该孤立状态恢复，等待 Authoring 和 Hypit 静态校验结果。

## 验证

- `tests/test_pexels_provider.py tests/test_pixabay_provider.py tests/test_material_acquisition.py tests/test_material_rights.py`：44 passed。
- 全量 `.venv/bin/python -m pytest -q`：482 passed, 5 skipped（2026-09-28）。
- `compileall`、`scripts/validate_skills.py`、`git diff --check`、前端 lint/build 通过；lint 保留一条 `AccountsPage.tsx` 既有 Hook 依赖警告。
- 这些是软件验证，不代表三种来源的正式 E2E 已完成；该 E2E 仍由 T15 跟踪。
