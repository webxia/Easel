# Easel · 主线开发 Agent 入口

> 作用域：仓库研发、代码审查、测试和架构/产品文档维护。**这不是 Easel 产品内创作 Agent 的人格或媒体生产指令。**
> 产品内创作 Agent 的规则源为 [创作 Agent 指令](agents/workspace/AGENTS.md)；产品运行时可能使用项目根作为 cwd，实际指令加载边界必须单独核验，不能仅凭文件分开放置宣称隔离完成。
> 当任务是面向用户的内容创作而非仓库研发时，不将本文的开发任务、Git/PR 和研发阶段规定作为内容生成约束；按产品运行时实际加载的创作指令与用户要求执行。

## 1. 唯一产品目标

当前主线聚焦视频：一个 Creator / Profile + 一个 Director / Creative Mode + 不同 Content → 稳定风格、具有创作自由度的可审阅视频。Creator 确认后，系统尽可能自主完成首版，必要时局部修订。先实现真实生产闭环，不因局部工具或协议问题改变产品目标。

- 正式业务需求见 [需求](docs/mainline/product/requirements.md)；目标职责见 [架构](docs/mainline/architecture/domain.md)。
- 当前二开主线建立在官方 Easel 上；`easel-studio` 只作为只读参考，不是兼容目标或下一步任务清单。
- 架构图、候选接口和路线图都不等于已实现能力；验收必须使用相应版本的实际证据。

## 2. 新任务的上下文入口

1. 先确认 Git 分支/HEAD、工作区状态、用户当前授权及任务目标，不覆盖已有改动。
2. 读 [主线文档导航](docs/mainline/INDEX.md) 和 [当前状态](docs/mainline/project/status.md)，核对活动工作树和基线，找到当前唯一工作事项。
3. 实施时读[任务衔接规范](docs/mainline/development/task-handoff.md)与当前卡，再按任务选择必要的需求、合同、[统一开发规范](docs/mainline/development/engineering.md)、源码和测试；**新功能和 Bug 修复共用同一开发流程**，不要默认全文读取历史或全部文档。
4. 如果任务与已确认需求/职责冲突，报告并走变更决策；不能用现有代码或一次失败偷偷重写需求。
5. 工作完成要给出结果、验证证据、未覆盖风险和下一动作；更新受影响的权威文件，不新增重复“最新状态”。

### 2.1 需求进入与交付闭环

- 用户用自然语言提出研发需求即可，无需特定口令。按意图和持续有效授权分流：现状询问/讨论先回答或调查；“先出方案、暂不改代码”只做方案；明确实现/修复请求在范围内持续开发和验证。普通“继续”不自动解除先前的方案/代码/部署限制。真正影响目标或权限的歧义才澄清，已明确的普通实施不逐步重复请示。
- 跨会话/跨模块需求建立或复用一张父Task，串联需求→设计→开发与离线测试→受测版本→授权部署/E2E→修复回归→交付收口；小改动沿PR、普通Bug沿原Task，不为每条消息新建卡。方案待审、开发已做、软件通过、真实通过分别记录；建Task或认可方案不自动授权开发，阶段转换按ENGINEERING §2.4核对并记录。
- 完整规则唯一维护在[ENGINEERING §2.4～§2.5](docs/mainline/development/engineering.md#24-自然语言需求进入与授权判断)，交接按[任务衔接规范](docs/mainline/development/task-handoff.md)。修复后继续父任务余下验收；Git及发布按原授权，视频发帖与软件部署分别判断。待评审任务不覆盖当前生产断点。

## 3. 阶段门槛与任务分流（研发 Agent 强制执行）

> 当前阶段、唯一活动事项与授权，以 [CURRENT_STATE](docs/mainline/project/status.md) 及本次任务为准；历史 S6/S7 决定只在原 Task/运行记录中保留，不再写成常驻 Agent 指令。

- **指令偏差先沟通**：比较用户最新指令/操作、活动 Task、已确认需求、冻结合同及授权。若实质不一致，先说明差异、来源证据、影响、可选方案与推荐，并向用户提出明确决策问题；暂停受影响写入，不能自行改写用户目标。轻微措辞歧义且不影响边界则按已批准目标执行，不反复请示。决议更新原权威文档。
- **阶段目标优先**：按 CURRENT_STATE、当前 Task 确认目标、具体受阻证据、授权、范围与收口条件；历史故障和优化不是自动待办，不为“顺手改进”增加新 Agent、Gate 或架构。
- **故障分流**：`SAFETY` 首先止损（费用、Rights、UNKNOWN、数据、权限）；`CURRENT_BLOCKER` 要有本次真实证据才修；`LATER` 归并登记到[候选池](docs/mainline/project/backlog.md)，未证实标记待验证；`RESEARCH` 不进入实施。不另建平行 Backlog。
- **有证据地持续修复**：调试按[E2E 规范](docs/mainline/development/testing.md)先定位首次失败；确证需修改代码的 Bug，**在活动 Task 内按[统一开发规范](docs/mainline/development/engineering.md)分析、设计、修复、回归**，合法时回原场景并继续父 Task 剩余验收。必要时可跨模块，不以补丁行数限缩正确性；不得放宽合同/安全保护、顺带做后续优化。失败无新证据时先补证据，不盲目修改。
- **完成即收口**：按**活动 Task 原目标和当次授权**判断完成；局部修复、工具结束或软件 PASS 不自动关闭父 Task，合法范围内由 Codex 连续完成剩余复验。报告受测源码/Dirty/部署版本、验证和未测范围；区分 `SOFTWARE_PASS`、`REAL_PRODUCTION_PASS`、`CREATOR_ACCEPTED`，不把未测写成 PASS。通用流程见[ENGINEERING](docs/mainline/development/engineering.md)，真实场景见[E2E 规范](docs/mainline/development/testing.md)。

## 4. 工程职责与安全

- **生成优先，审核兜底**：新增模块、限制或审核前，先核对已确认需求或具体失败证据，以及能否改进前期生成解决；未知效果、一般审美建议和观察局限不自动升级为硬门槛。无具体缺陷的审核标签不触发重做；技术正确性、事实、Rights、授权、费用与UNKNOWN保护不因此放宽。

- 需求定义可观察的产品行为；架构定义职责和不变量；源码/测试/运行证据定义当前行为；Task 约束本次实施范围；状态文档只汇总事实。
- Agent 负责创作或语义判断，程序负责可确定的身份、状态、权限、预算、引用和恢复；不要为了提高 PASS 数量放宽用户事实、Rights 或成本边界。
- 实际需要时可结构性重构，不坚持无意义的最小补丁；**但必须先满足第3章的阶段归类与当前验收准入**，每个新模块、Gate、Agent 或长流程必须对应已确认的当期必要需求或已证实的安全风险；后续阶段的需求不能作为当期重构理由。
- 开发 Agent 不应向产品内创作 Agent 注入研发任务、分支/提交规则或历史调试清单。
- 禁止把密钥、原始凭证和个人运行数据写入 Git、文档或日志；保护现有 `outputs/`、Profile、历史 Attempt 和未跟踪文件。
- 不擅自启动付费模型、媒体生成、自动发布、数据迁移或对生产运行造成副作用的操作；按当前用户授权范围执行。Git 例外：**已获授权的研发任务通过适用验收后，可自动 Commit 并 Push 到自己的非保护开发分支**，无需每次重复确认；必须事先核对变更范围、排除凭证/历史素材/无关未跟踪文件，并且不允许自动合并或推送受保护主线。详细边界见 [ENGINEERING §6](docs/mainline/development/engineering.md)。
- 同一问题先利用既有检查和证据；不能用纯 Prompt 声明替代能自动执行的安全检查、测试或权限控制。

## 5. 验收、交接与上游

- 工程命令与可运行检查见 [ENGINEERING](docs/mainline/development/engineering.md)，必要时阅读官方 [CONTRIBUTING](CONTRIBUTING.md)。
- 区分 **软件检查通过 / 真实生产通过 / Creator 接受**；不拿其一冒充其二，也不把未运行记为通过。
- 小修复记录在 PR 即可；跨会话/跨模块工作使用轻量 [Task 模板](docs/mainline/development/templates/TASK.md)；重大长期设计决定使用 [ADR 模板](docs/mainline/development/templates/ADR.md)。
- 本地 `main` 跟踪官方 `upstream/main`；`easel-v2-rebuild` 是长期二开主线；`easel-studio` 只作封存参考。**每周一次、每个新阶段开始前**检查官方更新，先 Fetch/Diff/报告；**官方更新合入 V2 必须先报告并获得用户明确确认**，不能因风险低自行合并。禁止静默换基线、自动 force-push 或破坏历史。
- 当前阶段与下一任务以 [当前状态](docs/mainline/project/status.md) 为准；已确认需求与职责、选型建议、实施合同和运行验收必须区分。历史 Task 的范围不限制后续已授权任务，设计文档不冒充业务实现。
