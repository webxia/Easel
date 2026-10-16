# S1-B｜Easel V2 前后端工程质量审计与现有规范盘点

> **报告状态：审计已完成，工程质量风险尚未处置。** 审计日期：2026-10-16。
> **业务源码唯一基线：`easel-v2-rebuild@8eeafb6b9bf62b26e2077057cbebe45721f5d464`**。最初承接 S1-A 的文档分支 HEAD `78ed77edfb7b1d25015b0245bc0dcf77cbde52c3`，其中业务源码与本报告基线相同；本报告分支从业务基线独立分出。
> **S1-A 已完成但未合入**：[能力审计 PR #1](https://github.com/webxia/Easel/pull/1)，报告原文见 [S1-A 能力审计文件](https://github.com/webxia/Easel/blob/docs/s1-capability-audit/docs/v2/06_CAPABILITY_AUDIT.md)。不得把 PR #1 的文档提交或尚未获准的 V2 需求并入本次源码质量评价。
> **取证层级**：已复现（无副作用临时夹具）／静态代码确认／潜在风险／待验证。安全风险等级与实际网络可达性、文件可信来源相关；下文不声称已发生用户数据泄露或实际攻击。

## 1. 执行摘要

本轮与 S1-A 的“有什么能力”不同，只回答**当前源码工程质量、执行边界、可维护性、测试能力与工程约束的真实状况**。检查覆盖 FastAPI Web、CLI / Profile、Agent Harness、Skills / 媒体共享层、React / TypeScript、SSE / 会话、跨模块安全、依赖与 GitHub CI；没有执行产品需求差距映射、V1 历史复盘、业务修复、真实模型、真实素材生成或自动发布。

**综合判断：基础工程和多平台 CI 已具备，不能称为质量失控；但“本地优先、无独立鉴权”的部署假设、可直接访问产物目录的同源 HTTP 接口、长链路运行态与缺少浏览器级回归构成高优先级工程风险。** 不是因为 `web/app.py` 有 5,479 行就判定失败，而是此文件同时承载鉴权边界、配置、模型路由、聊天执行、媒体操作、账号与发布，存在实际跨职责修改半径和验证成本。

问题去重后共 **15 项：P0 0、P1 3、P2 10、P3 2**。其中 P1 受部署边界和不可信资源是否可访问等条件约束；不代表已经确认外部入侵。暂不建议全面重写、引入新 Agent 或先选定状态管理框架，应先保留风险证据供后续正式决策。

| 领域 | 现有有效机制 | 主要风险 |
|---|---|---|
| API / 安全 | CORS、TrustedHost、本地写入守卫、路径 resolve 校验、配置 allowlist、Key 脱敏 | 无独立访问鉴权；同源 HTML / 系统输出目录读接口可绕开预期用途隔离 |
| Agent Harness | Adapter 协议、原生 Session ID 绑定、权限确认、跨进程锁、持久化快照 | 原生 Agent 是否自动读取仓库根 `AGENTS.md` 尚未实机核验；持久化失败和 SSE 事件重放存在可观测性/效率缺口 |
| Profile / Skills / Media | 统一画像助手、Skill 契约、共享脚本、manifest 原子替换 | 文件接口和调用执行仍集中于 Web 入口；上传总量与用户级配额未约束 |
| React / TypeScript | API 封装、DOMPurify、组件化页面、SSE 续接、Node 回归测试 | 完整会话快照存 localStorage；跨标签写竞争；类型严格性与真实浏览器 E2E 不足 |
| CI / 测试 | Python 跨平台 pytest、Harness portability、安装脚本检查、前端 lint/构建/Node 回归 | 特定测试依赖宿主 HOME 和 DNS，完整 pytest 本地非全绿；未测真实浏览器端到端及夜间真实安装 |

## 2. 范围、基线与方法

### 2.1 Git 与上游事实

- `origin` 为 `https://github.com/webxia/Easel.git`；`upstream` 为 `https://github.com/ZJU-REAL/Easel.git`。
- 当前业务基线 `8eeafb6b9bf62b26e2077057cbebe45721f5d464`；`git fetch upstream` 已执行，仅比较未合并。比较 `easel-v2-rebuild...upstream/main` 当时为 **3 / 22**，上游 HEAD 为 `4696dfafd4f60d7426c3a898d4e146a212283770`。这 22 个提交**未纳入**本报告代码事实和测试结果。
- S1-A PR #1 仍 OPEN，所检查 CI 的必跑项通过，真实安装任务 SKIPPED；“CI PASS”只属于该 PR 的对应输入版本。
- 原始工作区有四处未跟踪文件/目录；本轮不读取其中个人素材内容，不删除、不暂存、不纳入提交。
- 管理型独立 worktree 的创建被本机运行器目录范围阻止；本报告采用从 V2 业务基线创建的独立 **docs/s1-engineering-quality-audit** 分支，不复用 S1-A 的六个文档差异，不合并 PR #1。

### 2.2 两轮方法

**第一轮：** 清点 Git 追踪的源文件与测试，浏览模块职责、入口和 CI；核对已存在的安全、类型、配置与验证能力。此轮盘点到 **1,085 个 tracked 文件**，其中 **207 个非选定 vendor 的 Python 文件**、**37 个前端 TS/TSX 文件**；测试入口为 63 个 Python 测试模块和 13 个前端 Node `*.test.mjs` 文件。目录统计只用于确定覆盖范围，不等于所有文件都逐行查阅。

**第二轮：** 聚焦 `web/app.py` 的输出文件边界、Origin 写入守卫、上传、会话恢复、模型配置；`App.tsx`、`store.ts`、`api.ts`、`OutputsPage.tsx`、`ArtifactGallery.tsx` 等前端代码；`easel/harnesses/{base,codex,acp,permissions,store,workspace}.py`、`easel/persona.py`、`skills/shared/scripts/manifest.py` 与配套测试。仅使用**临时 synthetic 文件及不存在的接口路由**验证安全边界，不读取用户真实 `outputs/` 或 Key，不发真实模型请求。

### 2.3 判定口径

P0：已证实、可造成严重破坏且无需额外合理条件的工程阻断；P1：在明确可达条件下的重大安全/数据风险；P2：关键功能可靠性、恢复、维护与测试质量风险；P3：低风险规范和局部可维护性问题。以下每项均写明证据与复核方法。没有复现的情境不冠以“已利用/已发生”。

## 3. 高优先级发现

### S1B-Q01｜P1｜同源 HTML 产物可从沙箱预览之外直接打开

- **证据级别：已复现 HTTP 返回行为；浏览器利用链未实机执行。**
- **定位：** `web/app.py:4014–4022`、`web/frontend/src/components/OutputsPage.tsx:182–190`、`web/frontend/src/lib/linkifyOutputs.ts:132–138`。
- **现象：** `/api/media/{path}` 将输出目录内 `.html` 原样以 `text/html` 内联提供，未附加 CSP 或 attachment 隔离。内容库的 iframe 虽然设置 `sandbox="allow-scripts"` 且不给 `allow-same-origin`，其相邻“在新标签打开”链接和自动处理的媒体链接却指向**同源原始地址**。不可信 HTML 若直接作为顶层页面打开，其脚本不再受 iframe sandbox 约束，并可调用同源本地 API。
- **取证：** 临时生成 `example/test.html` 的 TestClient 请求返回 **HTTP 200**、`Content-Type: text/html; charset=utf-8`，`Content-Security-Policy` 与 `Content-Disposition` 均缺失。未使用任何真实用户产物，也未执行攻击脚本。
- **触发条件：** 工作台允许打开含主动脚本且来源不可信的 HTML 文件。
- **处理方向：** 将原始不可信 HTML 的下载/隔离域名/服务端 CSP sandbox 与可信预览显式区分；确保所有直开路径而不仅是 iframe 都受到相同策略。明确需要保留的剪贴板/预览能力。
- **验收：** 测试不可信 HTML 预览、直开、媒体链接与下载，确保它不能获取工作台同源权限，同时合法预览仍可用。

### S1B-Q02｜P1｜本地写入守卫不是网络鉴权，可信 Origin 可被非浏览器伪造

- **证据级别：已复现守卫放行判定；没有进行真实远程攻击。**
- **定位：** `web/app.py:489–538`，`tests/test_local_write_guard.py:51–59`，服务监听 `0.0.0.0` 的运行配置。
- **现象：** POST 等写入操作带 `Origin` 时，仅判断其是否属于允许列表；有 `Origin` 则不再检查真实客户端是否为 loopback。源代码注释已准确承认手写 HTTP 客户端可以伪造 `Origin/Host`。当端口对不可信局域网或公网可达时，无法把该守卫当作写接口身份鉴权。
- **取证：** 临时模拟对端 `192.168.12.22`，POST 到不存在的 `/api/__s1b_guard_probe__`：不带 Origin 返回 **403**，伪造合法本机 Origin 返回 **404**（到达路由层）。此探针没有调用任何会修改配置的 API。
- **触发条件：** Easel HTTP 端口对不可信网络主体可达；对可信本机单用户部署，不必推导为已被攻击。
- **处理方向：** 明确支持的监听/反代方式；不能只用浏览器 Origin 当身份认证；按部署场景考虑默认 loopback、访问令牌或可信反代身份。保留明确受限的扩展剪藏能力。
- **验收：** 受信任浏览器与 CLI 仍可用；非受信任网络源即使伪造 Host/Origin 也不能读写受保护状态。

### S1B-Q03｜P1｜“系统受保护目录”只限制删除，通用读取 API 未分域

- **证据级别：已复现 synthetic 文件可读；未读取真实系统文件。**
- **定位：** `web/app.py:1132–1140`、`4001–4022`、`4025–4075`。
- **现象：** `_safe_output_path` 仅判断目标位于 `outputs/` 且存在；`/api/output/{path}` 和 `/api/media/{path}` 直接复用。用于删除的 `_is_protected` 明确拦截顶层 `_login`、`_harness` 等系统目录，但读取没有同等分类。实际登录态、会话、调试及 Harness 配置是否含敏感字段须逐项核查，不能一概断言“已泄露密钥”。
- **取证：** 在临时 `OUTPUTS_DIR` 下构造仅含无敏感标记的 `_login/review_private.txt`、`_harness/review_private.txt`，两个目录经 `/api/output/` 与 `/api/media/` 均返回 **200**。
- **触发条件：** 客户端知道/获得系统文件路径且能够访问本机 Web；与 Q02 的网络暴露条件叠加时影响放大。
- **处理方向：** 建立可公开预览的作品资源与内部状态/凭证/二维码读取的单独路径政策；内部合法二维码应通过明确白名单接口提供，不能把删除保护误作读取授权。
- **验收：** synthetic 内部文件经通用输出 API 不能读取；内容库合法项目和明确开放的登录图仍正常显示。

## 4. 可靠性、前后端与测试问题

### S1B-Q04｜P2｜上传的总量/内存/磁盘预算未统一约束

- **证据级别：静态代码确认。**
- **定位：** `web/app.py:4094–4119`、`4128–4156`；`web/frontend/src/components/ChatPage.tsx:58–86`。
- **现象：** 常规上传先 `await f.read()` 整体读入内存、事后才判断单文件 50 MB；超限“本地复制”通道虽改为 1 MB 分块，却明确**没有总大小上限**，也未看到本路径上的单次文件数/批次/磁盘配额与失败后清理策略。前端将大文件转该通道。
- **影响：** 大文件/多文件输入可能造成 RAM 峰值、磁盘增长或残留；实际流量与宿主限额尚未压测。
- **建议/验收：** 先定义单次、并发、磁盘与回收预算，再通过临时存储模拟上限、失败、重复名和中断；无需预设新上传架构。

### S1B-Q05｜P2｜SSE 事件重放反复全文件读取

- **证据级别：静态代码确认；未做长事件日志性能压测。**
- **定位：** `web/app.py:2820–2838`、`3123–3162`，`3213–3231`。
- **现象：** 每次 `_read_job_events(turn_id, cursor)` 用 `read_text().splitlines()` 解析当前任务**全部** JSONL 后过滤 `id > after`，重放尾随循环每 0.25s 检查一次。长任务累计事件多时，重复 I/O / JSON 解码压力持续扩大。写端异常也允许静默继续。
- **建议/验收：** 仅消费游标之后的事件或记录读取位置，制定事件保留/清理与持久化失败的观测要求；构造大体量日志、截断行和多连接恢复回归。

### S1B-Q06｜P2｜结果快照及事件日志落盘失败可能静默变为“完成”

- **证据级别：静态代码确认。**
- **定位：** `web/app.py:2866–2881`、`3209–3231`、`3718–3728`。
- **现象：** `_save_turn` 将任意写入异常吞掉；SSE 日志创建/追加失败也直接 `pass`。客户端断线后依赖这些文件恢复，但写入失败不形成可区分状态，原路径仍可发送完成事件。
- **影响：** 存储满、权限改变或磁盘故障时，用户可能看到任务完成却无法恢复结果；未做故障注入，不声称正常路径经常失败。
- **建议/验收：** 对恢复必要的持久化失败保留结构化错误与诊断日志；隔离目录故障注入验证真实完成与可恢复状态不混淆。

### S1B-Q07｜P2｜浏览器整量会话快照写入没有配额失败兜底

- **证据级别：静态代码确认。**
- **定位：** `web/frontend/src/lib/store.ts:91–133`、`web/frontend/src/App.tsx:249–258`、`491–524`。
- **现象：** `saveSessions` 每次序列化全部会话及历史消息，调用 `localStorage.setItem` 没有 `try/catch`；会话虽限制最多 100 条，但单条长文本/思考/活动内容没有总字节预算。相反发布草稿存储已有本地异常捕获。
- **影响：** 超过浏览器 quota 后，会话保存可抛错影响调用链，浏览器态可能与实际 Agent Session 偏离。
- **建议/验收：** 给持久化失败显式处理及可见反馈，测试 quota、损坏快照、长消息；数据存储方案在后续设计阶段决定。

### S1B-Q08｜P2｜跨标签并发编辑整份会话列表有覆盖风险

- **证据级别：潜在风险；未进行双浏览器标签动态复现。**
- **定位：** `web/frontend/src/App.tsx:82–153`、`249–257`、`491–524`，`web/frontend/src/lib/store.ts:91–133`。
- **现象：** `BroadcastChannel` 用于初次判断另一个标签是否占有候选活动会话；没有观察到多标签对 `easel_sessions` 的**增量同步、写入版本比较或冲突合并**。不同标签持有各自完整快照并写同一 localStorage key 时可能相互覆盖。
- **建议/验收：** 真实双标签交替写入不同会话，验证刷新、恢复、重试与删除；先确认冲突语义，再确定修复策略。

### S1B-Q09｜P2｜async 路由中的非受限文件 I/O

- **证据级别：静态代码确认。**
- **定位：** `web/app.py:4001–4010`、`4094–4116`，对照 `3954–3959`。
- **现象：** `async def api_output` 在协程里同步 `full.read_text`，输入可为未知大小文本；`api_upload` 在 async handler 中执行文件写入。相比之下 `api_outputs` 特意使用同步 `def` 交给 FastAPI 线程池，说明已有明确的事件循环隔离意识，但未统一落实。
- **建议/验收：** 对输入大小、同步文件 I/O 与事件循环延迟进行隔离验证；针对大文本/上传和并行状态请求评估改进，不盲目全部改成异步。

### S1B-Q10｜P2｜模型配置测试仍受宿主配置/DNS 影响，完整 pytest 未全绿

- **证据级别：真实离线测试已复现失败（详见第 6 节）。**
- **定位：** `tests/test_web_anthropic_slot.py:130–182`、`tests/test_web_model_config_parity.py:83–97`；`web/app.py:818–833`、`2479–2553`、`1623–1652`。
- **现象：** 两条“协议 Header / URL”测试只 mock `urllib.request.build_opener`，没有隔离前置 `_ssrf_safe` 的 DNS 解析；在当前环境 `_ssrf_safe("https://api.anthropic.com")` 与 OpenAI 公共目标都返回 False，因此 fake opener 不被调用。默认真实 HOME 还导致占位 Key 用例读到另一个已配置的自定义 Provider；隔离 HOME 后该失败消失。
- **影响：** 测试结果依赖开发机器配置/网络，可能误导故障定位。**当前不证明真实 Anthropic 模型调用失败，也不能把两条失败抹成 PASS。**
- **建议/验收：** 将外部目标判定与 DNS 提取成可模拟的纯边界，测试同时断言可允许的公共 IP 与必须拒绝的私网/重绑定场景；所有非真实网络测试使用独立 HOME / runtime / 配置源，跑完整 suite 全绿。

### S1B-Q11｜P2｜产品与研发 Agent 指令的实际隔离尚无底座级证据

- **证据级别：待验证（不同原生底座指令发现行为不同）。**
- **定位：** `easel/harnesses/workspace.py:10–42`、`web/app.py:2979–2986`、`easel/harnesses/codex.py:81–111`、`easel/harnesses/acp.py:90–95`；根 `AGENTS.md` 和 `agents/workspace/AGENTS.md`。
- **现象：** 程序明确将产品共享指令注入 native adapters，但原生进程工作目录依旧是项目根。某些 Agent 可能独立发现根开发 `AGENTS.md`；仅凭两个文件分开放置不能证明运行时隔离。本轮按禁令没有调用付费 Agent 来验证。
- **建议/验收：** 后续经授权采用可观测的无媒体任务核验每个底座真实指令集与 cwd；这属于**工程边界待验**，不能被解释为当前已实际串扰。

### S1B-Q12｜P2｜前端类型和真实交互回归覆盖存在边界

- **证据级别：静态代码确认，Node 回归测试实际通过。**
- **定位：** `web/frontend/tsconfig.app.json:1–25`、`web/frontend/package.json:6–11`、`.github/workflows/ci.yml:151–170`、`tests/frontend/chatQuestionReplay.test.mjs:1–61`。
- **现象：** TypeScript 设定 noUnused/不允许 switch fallthrough 等检查，但未启用 `strict`（也未观察到 `strictNullChecks`、`noImplicitAny` 等等效组合）；API 接口当前多为客户端 TypeScript 接口声明，缺少运行时响应解析约束。Node 回归提取局部 TS AST 函数并执行，能验证 SSE 解析等纯逻辑，但不等同于浏览器里的真实 React 生命周期、DOM、安全浏览器机制和跨标签重启 E2E。
- **建议/验收：** 后续根据风险渐进收紧类型规则和 API 契约测试，对 SSE 恢复、浏览器上传、HTML 预览、跨标签竞态增加少量真实浏览器回归；不要求本轮引入新框架。

### S1B-Q13｜P2｜核心 Web 与前端编排职责集中，跨模块变更半径较大

- **证据级别：静态代码确认。**
- **定位：** `web/app.py`（约 5,479 行）、`web/frontend/src/App.tsx`（约 862 行）、`web/frontend/src/lib/api.ts`（约 937 行）、`web/frontend/src/components/SettingsPanel.tsx`（约 913 行）。
- **现象：** `web/app.py` 同时处理模型设置/探测、代理通信、登录发布、文件存取和 Session 执行；`api_chat_stream` 含多运行底座、多层本地闭包、锁与 SSE 事件恢复。前端 `App.tsx` 同时管理流式通信、打字效果、会话存储/恢复、跨标签检测与页面切换。不是单纯“文件大”的问题：多种不同生命周期与副作用在少数文件/函数中交织，测试和回归必须跨多领域验证。
- **建议/验收：** 在阶段三以变更影响、调用路径和现有回归制定合理职责边界，再决定拆分；当前不触碰业务源码，不预设微服务或新增 Agent。

### S1B-Q14｜P3｜Python 统一静态规范尚无强制质量工具入口

- **证据级别：静态代码确认。**
- **定位：** `pyproject.toml:1–35`、`.github/workflows/ci.yml:17–71`、`CONTRIBUTING.md:10–17`。
- **现象：** Python 侧已经有 pytest、Skills 文档契约、安装脚本检查；但没有看到全仓 Ruff/Black/mypy 或等效 Python lint/type check 在本项目配置和 CI 中执行。此为**规范覆盖缺口**而非当前代码错误。
- **建议/验收：** 阶段三比较现有工具与实测问题后决定是否引入、采用什么范围与渐进基线，勿先做大规模格式化。

### S1B-Q15｜P3｜当前前端 lint 有一条非阻断警告

- **证据级别：已复现。**
- **定位：** `web/frontend/src/lib/linkifyOutputs.ts:27`。
- **现象：** `npm run lint` 报 `eslint(no-useless-escape)` 一条，**0 errors**，不妨碍构建或本轮审计。
- **建议/验收：** 后续代码维护时顺手调整并继续使用现有 lint，不因单条警告建立新治理流程。

## 5. 现有工程规范覆盖矩阵

“已落实”指静态机制及对应已有测试/CI 入口存在，并非所有生产场景已验证；单次审计不视为最终规范冻结。

| 主题 | 当前状态 | 证据与待办 |
|---|---|---|
| 模块与目录 | 已有但执行不充分 | `easel/`、`web/`、`agents/`、`skills/` 分工可见，Web 主入口集中（Q13） |
| Python 代码规范 | 尚需后续决策 | `pyproject.toml` 定义 Python ≥3.10，pytest 存在；未见统一 lint/type CI（Q14） |
| React / TypeScript | 已有但执行不充分 | Vite / oxlint / tsc，构建和 lint 入 CI；严格类型检查未启（Q12、Q15） |
| API / 类型契约 | 已有但执行不充分 | Pydantic 请求模型与前端 TS 类型；异常响应跨业务有多种形态、无统一运行时契约验证 |
| 会话与错误恢复 | 已有但执行不充分 | Session 绑定、锁、SSE snapshot、前端重连有效基础；持久化异常/规模化测试缺口（Q05–Q10） |
| 安全 / 凭证隔离 | 已有但执行不充分 | 配置 allowlist、CORS/TrustedHost、路径校验与 DOMPurify；HTML/读取策略与监听边界需复核（Q01–Q04） |
| 测试 / CI | 已存在且落实（范围受限） | Python 多 OS、前端 Node 回归/构建、Skills 校验；测试环境仍非全绿且浏览器 E2E 缺少（Q10、Q12） |
| Git / PR / 官方同步 | 已存在且落实 | 根 `AGENTS.md` 与 `docs/v2/05_ENGINEERING.md`；上游仅 Fetch/Diff，主线需要用户授权，PR 分支检查 |
| AI Coding / Agent | 已有但运行边界待验证 | 开发与创作指令分文件、Adapter 权限自动审批保守；原生 cwd 指令发现未验（Q11） |
| 需求 / 文档 / 交接 | 已有但状态待合流 | INDEX、CURRENT_STATE、Task/ADR 模板；当前 S1-A/S1-B 两个未合并独立文档 PR，不能把需求草案当已批准 |

已有良好工程基础不得丢失：

- `easel/harnesses/store.py:15–38,68–89`：对损坏状态显式报错、记录用哈希路径并原子写入；不是全部持久化都不可靠。
- `easel/harnesses/permissions.py:22–64`：拒绝多数默认命令/额外权限；Codex 原生 `approvalPolicy` 不被自动扩大。
- `web/app.py:1309–1319`：Profile 写入路径经解析约束；`1132–1140` 输出路径有防穿越校验，问题是**资源分类/读取授权**而非简单 `../` 穿越。
- `web/frontend/src/lib/sanitize.ts:1–10`：Markdown 渲染先经过 DOMPurify；`OutputsPage` 与 `ArtifactGallery` 的内嵌 HTML 使用 opaque-origin sandbox。Q01 只指出**原始 HTML 顶层直接打开**的例外。
- `skills/shared/scripts/manifest.py`（90–117 行）：单项目产物有元信息记录和临时文件替换，不能等同于全系统任务的持久化账本。
- `.github/workflows/ci.yml`：前端 lint、Node 用例与 build 都运行，安装则按事件分组。不要误写为“没有前端测试”或“所有真实安装 CI 都已跑”。

## 6. 实际验证与未通过事项

本节区分**文档审计完成**、**软件测试通过**、**真实制作成功**；不能相互替代。

| 验证项 | 命令/方法 | 结果 |
|---|---|---|
| Git 基线 | `git status`、`git fetch upstream`、`git rev-list --left-right --count easel-v2-rebuild...upstream/main`、`gh pr view 1` | 基线确认；上游 3/22；PR #1 开放、相关必跑 CI 成功 |
| Python 全量，普通开发 HOME | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider` | **1260 PASS / 3 FAIL / 11 SKIP / 3 warning**，约 63.34s |
| Python 全量，隔离 HOME + 指定 OpenClaw 运行时 | 临时 HOME，`EASEL_AGENT_RUNTIME=openclaw`，同一 pytest 命令 | **1261 PASS / 2 FAIL / 11 SKIP / 3 warning**，约 52.95s；仍非全绿 |
| 定向配置隔离验证 | `tests/test_web_anthropic_slot.py`、`tests/test_web_model_config_parity.py` | 临时 HOME + 指定 OpenClaw：**20 PASS / 2 FAIL**；两项为自测 HTTP 观测断言 |
| 前端 Node 回归 | 在 `web/frontend` 执行 `node --test ../../tests/frontend/*.test.mjs` | **71 PASS / 0 FAIL** |
| 前端 lint/type | `npm run lint`、`npx tsc --noEmit --project tsconfig.app.json` | lint **0 error / 1 warning**；TS 检查退出码 0 |
| 同源 HTML 响应 | 临时目录 + TestClient `GET /api/media/example/test.html` | **200**，inline `text/html`，没有 CSP / disposition |
| 本地写入守卫 | 远端模拟 peer + 不存在的 `POST` 路由 | 无 Origin **403**；伪造允许 Origin **404**（守卫放行） |
| 系统输出读隔离 | 临时 synthetic `_login`、`_harness` 文件 + TestClient | 两种通用读取 API 都返回 **200** |
| 真实 Codex/OpenClaw/ACP 模型调用、媒体、浏览器 E2E、生产部署 | 未获授权、或不属于本次审计 | **未运行**，不能声明通过 |

**两个持续失败的单测：**

1. `tests/test_web_anthropic_slot.py::test_selftest_uses_anthropic_headers_and_path`
2. `tests/test_web_anthropic_slot.py::test_selftest_keeps_openai_shape`

测试目标需要先通过 `_model_target_allowed` → `_ssrf_safe` 的 DNS 判断，而其 mock 只截获请求发起时的 opener。当前设备两个公共目标的 `_ssrf_safe` 均为 False，导致 `seen=[]`。因此**不能据此判定实际 Anthropic/OpenAI 协议代码错误**，仍必须记录本地软件测试不通过。

普通开发 HOME 下另外失败的 `test_placeholder_key_reports_missing` 在临时 HOME 中恢复 PASS：原因是函数从当前 OpenClaw 配置读取**额外自定义 Provider**，但测试仅替换 `ENV_FILE`，存在 fixture 不完全隔离，非本轮更改导致。

失败日志中可能包含实际 Provider 元数据或被掩码的局部 Key；本报告**不复制任何真实凭证、掩码值或用户配置内容**。本轮不为使测试通过去删除、覆盖或重配用户真实模型账号。

**工具环境事实：** Shell `python` 命令在当前 PATH 不存在，`python3` 为 3.14.4 但缺 pytest，项目 `.venv/bin/python` 是 Python 3.12.13 且有 pytest 9.1.1；因此完整验证改用项目 venv。前端本地没有执行会写入当前 Web dist 的生产构建；PR #1 远端此前已实际执行对应版本的前端构建。

## 7. 分模块结论与技术债处理顺序

- **后端 Web / API：** 核心功能代码入口明确，保护措施不少；优先按现有 HTTP 访问边界检查 Q01–Q04，随后处理持久化 / SSE 质量 Q05–Q06 与事件循环 Q09，而不是全面拆服务。
- **Agent Harness：** Base/Adapter/权限/持久化具备统一协议的雏形，Codex 和 ACP 在权限、会话续接上有显式错误；本轮无模型实测，Q11 标为待验证，**不将 Harness 原生 Session 当成媒体 Build 账本**。
- **Profile / Skills / 媒体：** 画像助手与元信息模块有单一入口和路径检查。Skill 存在内容与工具契约的区分，不能仅据 `SKILL.md` 宣称所有 Provider 已真实可用。V1 的 Hypit / Planning 方案不是本次评价标准。
- **前端：** 主链页面组件化且 Node 用例覆盖多种回归；但复合状态、localStorage 整量持久化及跨标签恢复真实行为需要专门浏览器验证，避免把 AST 单测当 E2E。
- **依赖与 CI：** `pyproject.toml` 规定 Python ≥3.10、依赖范围偏宽，前端有 package-lock 与 Node 24 CI；缺少跨平台真实运行时完整媒体验证是客观范围，不据此臆测每个依赖已知安全漏洞。第三方依赖最新漏洞数据库未扫描，记为后续独立待验。

**优先次序仅为决策输入，不是本轮修复任务：** Q01/Q02/Q03 的实际部署可达性与内容可信度确认 → Q10 的测试隔离恢复全量回归可信度 → Q04/Q05/Q06 的资源与恢复验证 → Q07/Q08/Q09/Q12 的前后端交互回归 → Q13/Q14/Q15 的渐进工程治理。最终是否重构取决于阶段三明确规范及阶段四已确认需求。

## 8. 进入阶段二的输入（不执行 V1 复盘）

当用户另行授权阶段二时，只需把本轮证据作为**对照问题**而非预设结论：

1. 对比 V1 的运行态丢失/重复执行经验是否与当前 `SSE + 会话快照` 风险属于同一个可复现工程问题；保留失败证据，不迁入旧协议。
2. 对比 V1 的配置、权限、Provider 失败原因时区分“真实业务调用失败”和“测试桩/网络环境失败”，以 Q10 为当前正例。
3. 审查历史图片、视频、音频等素材数据权限处理方式是否提供可复用经验，但不得因历史设计优劣修改 Q01–Q04 的当前源码事实。
4. 检查历史需求和 Agent 指令串扰、并发/恢复的踩坑记录，辅助决定后续规范测试矩阵，不启动历史媒体任务。
5. 记录历史使用过的有效验证与交接方式，只有可证实跨任务复用的规则才建议进入阶段三工程规范。

**下一阶段不是自动“修复所有 P1”或直接设计 V2 制作架构。** 先由用户审阅报告，决定是否安排安全修复或开始封存 V1 复盘。任何 PR #1 或上游合并需另行授权；未合并的 S1-A/S1-B 文档在将来集成时需对 `INDEX` 与 `CURRENT_STATE` 做语义合流，不能机械覆盖。

## 9. 本轮交接与保护结果

- **任务完成口径：** S1-B 工程质量**审计成果 COMPLETE**，但**软件全量回归 NOT PASS**（上文 2 条隔离后失败）；任何真实媒体生产验收均 **NOT RUN**。
- **唯一审计源码 SHA：** `8eeafb6b9bf62b26e2077057cbebe45721f5d464`。
- **交付：** 本报告；少量文档导航更新。文档提交 SHA / CI / PR 状态以实际完成后的 Git 回执为准，不在报告中虚填。
- **保护：** 未修改业务源码、用户配置、真实 Profile / `outputs/`、历史 Attempt 或已有未跟踪目录；未调用模型/媒体/发布，也未清理与强推。
- **停止点：** 报告完成并提交供评审后停止，不自动开展 V1 复盘、规范冻结、实现修复或 V2 设计。
