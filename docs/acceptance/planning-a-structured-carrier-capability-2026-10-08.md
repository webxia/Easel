# Planning A Harness-owned carrier：当前固定 Runtime 能力审计

状态：能力门 `BLOCKED`，Astra 前置复核 `STOP`；按授权停止分支结束，生产修改和真实 Development 未启动。

本记录承接[同一 Task 新授权章节](../tasks/planning-semantic-boundary-vnext-2026-10-07.md#a-carrier-后续-goalharness-owned-结构化提交协议2026-10-08已授权)。四项评审修订已落实：正常 B CHALLENGE 使用原共享修复；真实底层调用与阶段 RPC 分账；第二轮须针对性修复及重新固定；只有独立必要语义证据才能认定合同不可表达。没有建立第二条执行链。

## 固定事实与证据范围

- 软件基线 `aa0ab42ac86305d818613bc4a078469eb2042918`，生产 SHA `ffac01cc608caf72790d2a71d5bdf813657bc7ade24be09f31c4347ea651c74d`。审计开始 HEAD `df0d3a302ef59c6a5751f44be034fcc82a592f18` 包含后续失败文档，生产源码另行对账。
- 安装 OpenClaw `2026.9.4`，Node `24.21.0`。源码根 `/Users/xgx/.local/node-v24.21.0-darwin-arm64/lib/node_modules/openclaw`，以下 Runtime 路径均相对此根；正式证据记录相关文件 SHA。
- 当前 easel 配置只读白名单：`minimax/MiniMax-M3`、API `openai-completions`、fallback 空、defaults thinking off；Easel 阶段请求显式 thinking high。没有输出任何凭证或完整配置。内置 MiniMax 默认 Anthropic 的行为**不能当作当前实际 route**。
- 当前已有 `/v1/responses`、`/v1/chat/completions` 均未启用。本轮没有启用端点、加载插件、改配置、重启服务、提交模型或读写生产数据库。
- 实际执行安装模块的离线审计：[执行器](fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/native-audit.mjs)、[原生结果](fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/native-result.json)。只在外部 Provider stream 使用合成 async iterable，内部使用原生协议 validator、request builder、stream reducer；进程在临时工作区和隔离 state/config 路径运行。它是确定性边界证据，不是实时 Provider 验收或完整产品集成验收。

## 三层能力审计

| 层 / 候选 | Expected | Actual | 判定 |
|---|---|---|---|
| 普通 `agent` RPC | 每请求接收动态工具定义与指定工具选择 | 原生 validator 接受现有请求；拒绝 clientTools/tools/tool_choice/toolChoice，additionalProperties 禁止 | FAIL |
| 底层 direct / managed request builder | 可以表达指定 function | 两个 builder 都实际输出指定 function，并保留 scope enum；本离线模型行 strict flag=false | PASS（构造能力） |
| Schema 强制合法 | 不将工具出现冒认参数合法 | reducer 接受 JSON 合法但 scope=unknown、conditions=[] 的对象；没有在此层校验语义 carrier schema | 应由 Harness 校验，非服务端能力 PASS |
| 原生工具参数容量 | 承载现有结构合法 A 完整集合 | direct/managed 都接受256000 bytes，256001拒绝；现有合法 A 容量样本1331979同样拒绝 | FAIL |
| 原工具参数保真 | 原始 arguments 能与原 run 完整捕获 | delta可无损拼回原始文本；终态只剩解析对象，删除partialArgs；当前Easel reader明确排除toolCall | 接入未具备；恢复原文仍有缺口 |
| Gateway HTTP client-tools | 可使用既有已加载、可恢复的提交入口 | 实现有客户端工具投影、结果检查；实际端点关闭，服务端创建随机response/run id，不能套原RPC预存run协议 | 当前不可接入；不擅自启用 |
| Swarm `structured_output` | 普通A可接入且不增加隐式修复/依赖 | 仅host-registered collector/subagent lane/enabled可用；首次非法自动提示retry once，schema放描述里、实际工具只暴露宽result | 不满足本Goal合同 |
| MiniMax服务端 | 当前模型真实接受并落实pin/完整schema | 未向服务端提交探测，真实schema子集、strict及并行工具约束未知 | UNKNOWN，不归罪Provider |

### 原生证据定位

1. `dist/src-7tzZ8j12.mjs:2306` 的 AgentParamsSchema 是closed object；`dist/closed-object-DGvQfpTV.mjs:5` 禁止额外属性。`dist/agent-CX9n8ax-.mjs:28` 在派发前执行该validator。离线实测拒绝相关参数，不是仅搜索没找到。
2. 当前正常embedded链：`dist/builtin-openclaw-B-H-7lKk.mjs:9097` → `dist/attempt.model-diagnostic-events-CeJy4Pvm.mjs:99` → `node_modules/@openclaw/ai/dist/transports.mjs:673` → `openai-completions-stream-Da2vvl-S.mjs:979` 的managed builder；reducer入口见transports:695。底层指定工具能力存在，不代表RPC暴露它。
3. `openai-completions-stream-Da2vvl-S.mjs:249,323` 的256000 UTF8字节上限由所有mode共用。1425/1708无条件使用同一normalizer。超限抛 `Exceeded tool-call argument buffer limit`；外层managed transport见 `transports.mjs:709` 会将异常变为terminal error并清除工具。本审计reducer抛异常后的scratch stopReason/content不能冒认成功结果。
4. 现有 `tests/test_semantic_planning.py:1894` 的 `vnext_capacity_payload('A')` 实际通过 SemanticProposal校验，1331979字节。它证明**结构合法载荷容量**，不冒充某个真实Creation的独立语义通过；真实d01仅7849字节，此容量限制不倒算成上次d01失败根因。原助手文本8MiB承载PASS也不能转授工具通道。
5. `openai-completions-stream-Da2vvl-S.mjs:1775` 提供原delta，416解析完整对象，424删除原partialArgs。direct要求finish_reason（1795）；managed缺失终态标记行为另记在原生结果中，不能仅凭parse成功放行。length即使JSON完整也保持length；malformed arguments输出error。Gateway最终pendingToolCalls由已解析对象重新JSON序列化，例如`dist/embedded-agent-CE9KzQvy.mjs:6725`，不能复原原始JSON。
6. `dist/principal-CweFVZNq.mjs:300` 校验collector授权，327要求enabled、host-registered、subagent lane及内部handoff。`dist/subagent-registry-DuhjTUku.mjs:1784` 的structured_output把真实schema放description，parameters为宽result；1815–1844管理内部invalidAttempts和retry。这不是普通Planning A专用提交口。
7. 现有HTTP兼容层 `dist/openai-tool-choice-dfAW2byV.mjs:148` 缩小client tool集合、添加指令并在结果层检查是否出现目标工具，不保证参数合法。`dist/openresponses-http-ByVzbZRo.mjs:680` 创建随机response/run，响应中call_id由endpoint重新生成（747）；继续/丢响应时要独立设计恢复，不能直接套用原RPC身份。该路线仍共享256000参数硬限制。

## 最小生命周期设计（未实施、未冻结）

唯一正式工具候选名按运行能力决定，不新增第二结果通道。程序在派发前持久绑定Creation/Attempt/request/revision/carrier schema+SHA/frozen fingerprint/profile/model/runtime和原run；模型不重复填写这些可推导身份。接收原run active分支的全部目标工具事件，按tool_call_id累计原始UTF8 arguments及hash，完整事件和最终运行终态分别核验；不能把预览对象或中间toolcall当accepted。发现wrong/多个目标工具、缺片、截断、身份不一致或后续run异常明确分类并拒绝，不选某次正确调用。

存储安全检查必须在保存原候选前执行，拒绝敏感键、重复JSON键、非有限数等；有效完整capture持久后才结构/合同校验，写正式A checkpoint后才eligible B。落盘失败只恢复已捕获本地结果。终态证据未保存且Runtime恢复后不可核实时保持UNKNOWN，不重派或补造成功。新版本进入全部身份，旧原件/pending继续原版本对账，共享repair与真实账本不刷新。

Astra细化：同一工具事件的传输重放与模型实际发起多次目标调用分别识别；按原run/调用身份/可验证事件顺序幂等恢复，不重复拼接delta、不把重放误判重复模型调用，不能证明事件连续性则UNKNOWN。只有完整目标工具结束证据和整个run允许的成功终态同时成立才可准入；length/error/aborted、缺终态或scratch/preview均拒绝。

这是协议要求与待审设计，**不是已有工具生命周期已PASS**。当前缺少普通RPC动态工具入口，工具完整载荷又超原生硬上限，故不能冻结实现。拆成多个Need工具、工具提交文件/普通assistant文本的指针、截断条件、缩小既有合法集合、复用collector的隐式repair，均不属于本Goal获准的等价接入。

## 停止判断与未验证范围

`CAPABILITY_AUDIT=BLOCKED` 指当前固定Runtime、现有接入和不变carrier合同的组合不足；**不代表MiniMax服务端不支持function calling**。不设置 `CURRENT_PROVIDER_RUNTIME_STRUCTURED_OUTPUT=BLOCKED` 的供应商归因；服务端仍UNKNOWN。能力门失败后不实施、不用新Prompt或真实d01探索，后续阶段 NOT_EXECUTED。

已完成Astra只读复核和现场对账并保存本Goal停止结论。修复Runtime容量或增加新的工具接入需要新的范围决策，不能在这里自动升级、打安装包补丁或启用公开HTTP端点。

本轮暂无新协议软件验收，因此matrix/full pytest/Development/R4均NOT_EXECUTED，不复用旧196PASS/934PASS冒称本协议成功。原生16个stream案例及6个RPC校验、2个payload构造是已执行审计；验证器符合当前实现的断言通过，不等于所需产品能力通过。审计工具一次漏传compat、一次错误假定managed不透传toolChoice，均已纠正并留记录，属于测试设置/期望修正；没有改变生产代码或隐藏产品FAIL。

生产SHA与基线完全一致，生产代码无变化；257受保护文件、117历史fixture、十批1550文件全部原SHA一致。[现场对账](fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/reconciliation.json)、[实际Runtime指纹与配置白名单](fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/runtime-facts.json)、[Astra STOP](fixtures/planning-material-matrix-2026-10-06/vnext/carrier-audit/astra-review.md)均保存。相关安装文件只读，没有升级或打补丁。

真实模型/Provider网络/Supply/生成/TTS/Build/服务操作均0，新增外部费用0；不改变历史FAIL，不认领READY_FOR_FORMAL_R4或MATERIAL_READY。未commit/push。Astra所需两项文档/元数据修订已落实，未改生产。

```ini
BASELINE = aa0ab42ac86305d818613bc4a078469eb2042918
FINAL_VERSION = 无新软件发布；HEAD=df0d3a302ef59c6a5751f44be034fcc82a592f18
PRODUCTION_SOURCE_SHA = ffac01cc608caf72790d2a71d5bdf813657bc7ade24be09f31c4347ea651c74d
CAPABILITY_AUDIT = BLOCKED
ASTRA_PRE_IMPLEMENTATION = STOP
STRUCTURED_CARRIER = NOT_IMPLEMENTED
TOOL_LIFECYCLE = DESIGN_ONLY
CARRIER_VERSION = UNCHANGED
DOWNSTREAM_COMPATIBILITY = NOT_EXECUTED
SOFTWARE_MATRIX = NOT_EXECUTED（新协议）
FULL_TESTS = NOT_EXECUTED（生产未改，未通过能力门）
EXISTING_SKIPS = 本轮无pytest；旧记录不转授
HISTORICAL_FAILS_PRESERVED = YES
ASTRA_FINAL = NOT_EXECUTED（无生产diff）
DEV_EVAL = NOT_EXECUTED
RUNS = 0/6
FINAL_SUCCESS = N/A
CARRIER_FAILURES = N/A（未提交真实模型）
SEMANTIC_FAILURES = N/A
CONTRACT_FAILURES = N/A
A_CALLS = 0
B_CALLS = 0
TRUTH_CALLS = 0
REPAIR_CALLS = 0
TOTAL_MODEL_SUBMISSIONS = 0
RPC_CALLS = 0
MODEL_TRUNCATIONS = N/A（离线length反例不是模型实际截断）
TRANSPORT_UNKNOWNS = N/A（未新建外部请求）
STATE_VIOLATIONS = 0
SUPPLY_CALLS = 0
ELAPSED_TIME = 约23分钟（Goal设定至最终对账）；精确1370.613秒见final-report.json
QUOTA_BEFORE = NOT_QUERIED
QUOTA_AFTER = NOT_QUERIED
COST = 本轮新增外部费用0（未外部调用）；历史实际账单UNKNOWN保持
ENGINEERING_INTERVENTION = 0（真实执行未启动）；生产修改0
NEW_BLOCKER_STAGE = A carrier capability audit
ROOT_CAUSE = 普通RPC动态工具入口未暴露 + installed工具参数容量不足
CURRENT_PROVIDER_RUNTIME_STRUCTURED_OUTPUT = UNKNOWN（服务端能力未验，禁止供应商归因）
READY_FOR_FORMAL_R4 = NO
BLOCKERS = 本固定Runtime/接入无法无损承载现有合法carrier集合
```
