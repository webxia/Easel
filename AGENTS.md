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
- Git 分支与远端冲突按下方「Git Fork 与分支工作流」执行：`main` 跟踪官方 upstream，`easel-studio` 承载长期二开；该规则优先于旧文档或旧记录中的相反约定。

## 开发规则

- 不扩大 Goal，不顺手重构，不创建第二条视频生产主链，不改变 Material Layer V1.3 冻结语义。
- 大型跨模块能力先建立单一 Workstream/Task、依赖和验收条件，再分阶段实施；一次只做已授权范围。
- Provider 任务核对官方契约；Hypit 任务核对当前安装版本和真实源码。不要把 Provider/Hypit schema 泄漏进 Material Domain。
- 测试必须确定，不调用付费 AI、不依赖实时凭证；真实外部验收单独记录。
- 所有面向用户的说明使用中文。Secret 只放本机受保护配置或其所有者的认证存储；不得进入 Git、文档、日志、数据库、Attempt 产物或聊天。

## Git Fork 与分支工作流

本项目是 `ZJU-REAL/Easel` 的长期二开 Fork，固定远端为：

```ini
origin   = https://github.com/webxia/Easel.git
upstream = https://github.com/ZJU-REAL/Easel.git
```

### 分支职责

- `main` 只跟踪官方 Easel 上游；不在其上开发或提交产品功能、实验代码和本地定制。`origin/main` 应尽量与 `upstream/main` 一致。
- `easel-studio` 是长期二开主分支。Creator / Creation、Planning、Material Layer、AI Generated Material、External Material、Hypit Production integration、Creator UX、Content Library、Compound / Creator Memory，以及相关文档、测试和架构修改，默认在该分支或其短期 feature branch 上进行，不直接提交到 `main`。
- 上游同步优先 fast-forward 到本地 `main`，再将更新合并进 `easel-studio`。长期二开分支默认使用 merge，避免频繁 rebase 和重写已推送历史。

标准同步流程：

```bash
git fetch upstream
git switch main
git merge --ff-only upstream/main
git push origin main

git switch easel-studio
git merge main
# 解决冲突并完成必要验证后
git push origin easel-studio
```

除非明确批准，不得 force push、重写共享历史、reset `easel-studio`、修改 `upstream`、向 `upstream` push，或自动删除远端分支。若 `main` 出现本地独有提交，先查明来源；不得直接 reset 或 force push。

### Commit / Push 安全

- commit / push 前排除 `.env`、`.env.*`（保留只含空值、placeholder 或环境变量说明的 `.env.example`）、真实凭证、Provider / Hypit 本地 auth、SQLite / runtime state、Creation / Attempt 临时 workspace、生成媒体、日志、cache 和 scratch。
- 文件名含 `secret`、`token` 或 `auth` 不代表应忽略；正常凭证加载或脱敏源码应继续纳入版本控制。
- 执行 merge、rebase、reset、force push、覆盖分支或重写历史前，先确认当前 branch、worktree 状态、修改是否已 commit / push、origin / upstream 指向，以及二开成果是否已安全存在于 `origin/easel-studio`。优先保护用户二开成果，再同步上游。

### Canonical Branch Layout

```text
ZJU-REAL/Easel
└── upstream/main
      ↓
webxia/Easel
├── origin/main          # 官方 Easel 同步分支
└── origin/easel-studio  # Easel 长期二开主分支
```

默认开发目标是 `easel-studio`，不是 `main`。

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
