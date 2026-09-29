# Easel AI 开发入口

本文件只定义稳定规则和最小上下文入口。项目当前状态、架构细节和历史证据由 `docs/DOCUMENT_INDEX.md` 路由。

## 每个 Goal 的默认上下文

先读：

1. `docs/DOCUMENT_INDEX.md` — 判断该任务需要哪些材料。
2. `docs/00_PROJECT.md` — 产品目标与长期边界。
3. `docs/02_CURRENT_STATE.md` — 当前代码与验证状态；代码/测试是行为证据。
4. `docs/03_ROADMAP.md` — 当前 Workstream 和后续顺序。
5. 当前 Workstream 简报；若 Goal 指向已有 Task，再读该 Task。

不要默认读取全部 Architecture、ADR、Task、Acceptance、Audit 或历史文件。只有 Index 路由到它们、任务触及冻结边界，或需要核实某条历史证据时才读取。

## 权威与冲突

- 源码和测试说明当前行为；它们不能自行改变已接受的架构边界。
- 已接受 ADR 和标为 CURRENT 的架构文档说明设计约束。若代码与冻结设计冲突，先报告，不擅自重构。
- `docs/02_CURRENT_STATE.md` 是当前状态唯一汇总；`docs/03_ROADMAP.md` 只负责阶段和顺序。
- Task 限定实施范围；Acceptance 记录具体验证证据，不取代当前状态。
- 旧版/历史文档不构成兼容约束，除非 Goal 明确要求调查历史。

## 开发规则

- 不扩大 Goal，不顺手重构，不创建第二条视频生产主链，不改变 Material Layer V1.3 冻结语义。
- 大型跨模块能力先建立单一 Workstream/Task、依赖和验收条件，再分阶段实施；一次只做已授权范围。
- Provider 任务核对官方契约；Hypit 任务核对当前安装版本和真实源码。不要把 Provider/Hypit schema 泄漏进 Material Domain。
- 测试必须确定，不调用付费 AI、不依赖实时凭证；真实外部验收单独记录。
- 所有面向用户的说明使用中文。Secret 只放本机受保护配置或其所有者的认证存储；不得进入 Git、文档、日志、数据库、Attempt 产物或聊天。

## 常用检查

- `.venv/bin/python -m pytest -q`
- `.venv/bin/python scripts/validate_skills.py`
- `.venv/bin/python -m compileall -q easel web scripts tests`
- `cd web/frontend && npm run lint && npm run build`
- `git diff --check`

## 测试策略

- 测试按风险新增，不按 Task 数量配额新增；测试数量不是质量指标，风险覆盖才是。
- 优先顺序：Domain invariant → contract → integration boundary → high-risk regression → 必要的 unit test。
- 新测试必须保护新的风险、边界、contract 或历史回归点；优先扩展已有高价值测试，必要时参数化等价案例。
- 新 Task 和新 Capability 默认不增加测试；不要求“一 Task 一测试”或“一模块一文件”。完成替代性更高的场景后，可删除已无独立风险价值的旧测试，不机械补回等价 case。
- 不重复覆盖已由更高价值测试有效保护的行为；不测试 getter、薄包装、字段透传或内部实现细节。
- 定期按 Domain invariant、contract boundary、integration scenario、high-risk regression 复核组合；优先保留能防止跨模块失效的证据，不以文件数或单次耗时设硬目标。
- Bug 修复只有在回归测试能证明风险且不与现有覆盖重复时才新增测试。
- Capability 可以在测试数量不增加的情况下完成；若一次改动新增多项测试，先检查冗余与层级重复。
- 保持核心 Domain、Material/Rights/Gate、revision/hash/identity、Production selection、Approval/fingerprint/idempotency/reconciliation、Lifecycle、Generated Material contracts 及关键 integration 边界的有效保护。
