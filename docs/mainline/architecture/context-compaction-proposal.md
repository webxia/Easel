# CTX-01 · Easel复用官方会话压缩方案

状态：**首批已授权实施 / PARTIAL**。2026-10-23用户批准Easel侧去重、官方压缩接入及离线测试；代码已在easel-v2-rebuild实现，实际证据见父任务。未部署、未调用真实压缩、不付费、不恢复视频制作；不升级、不修改OpenClaw。

父任务：[CTX-01](../project/tasks/CTX-01_context-compaction.md)。本页只维护当前方案；旧升级核查与历史授权留在父任务。原视频停止断点不变。

## 1. 目标与明确边界

目标仍是长对话需要压缩时先整理历史，再继续原会话，保留用户意图及真实业务身份。不调大上下文或输出额度，不换模型、不新增审核，也不维护OpenClaw补丁。

**已批准首批实现两件事：自动注入去重 + 发送前复用官方sessions.compact。** Easel决定何时准备一次待发回合；官方运行时负责生成摘要、保存压缩结果及历史管理。复用现有turn、segment、交付状态和RPC连接，不新建摘要Agent、调度器或记忆系统。

能力边界必须区分：当前官方接口可读的是**上一轮**预算诊断，尚未核实有可对“历史+当前待发消息+最终系统提示及工具”执行无推理预算预检的公开接口。因此首批可以解决“已有有效超预算证据，下一次仍原样发送”和重复注入放大问题，不能声称覆盖第一次突然变大的输入、回合内部工具结果增长，或所有供应商length。

这属于原目标的**已批准首批切片**，不是把原“所有超预算输入均发送前压缩”目标偷偷改为已满足。若仍要求完整实时前置保证，当前限制下保留为未闭合能力，需另行评审官方可支持的接口；不通过增加字符阈值、复制token算法或每轮强制压缩来伪装完成。

## 2. 已核对的依据

### 2.1 已有问题

[原Web记录](../project/tasks/runs/2026-10-23-web-e2e-02.md)：estimatedPromptTokens=281483，promptBudgetBeforeReserve=236000，route=compact_only，但compactionCount=0，随后length。预算估算不是供应商实际用量，缺少完整最终请求及原始结束块，不能证明唯一因果。

官方2026.9.4及2026.10.6都把普通启发式压力当作诊断，不据此直接阻止发送；新版不是本问题的已验证修复。该调查和本机补丁清单见父任务，不作为继续改网关或升级的任务。

### 2.2 当前2026.9.4已有官方入口

基于已核验官方发布包及本机同版本源码只读核对，未调用生产RPC：

| 能力 | 实际合同与用途 |
|---|---|
| sessions.describe | 参数key、可选agentId；返回session行或null。行中包含sessionId、模型及contextTokens，并可投影contextBudgetStatus、压缩检查点信息。读取指定会话，关闭非必要标题/末条正文选项。 |
| contextBudgetStatus | source=pre-prompt-estimate，带updatedAt、sessionId、provider/model、shouldCompact、route、预算和估算。官方投影校验生产该状态的会话/模型/窗口，切模型等情况下可能不返回。是上一轮证据，缺失不能当0。 |
| sessions.compact | 参数只有key、可选agentId、可选maxLines；**不传maxLines**走原生模型摘要，传maxLines会转为历史行截断，不采用。没有预检当前prompt、预算目标、客户端幂等键或expectedSessionId参数，不虚构这些能力。 |
| 并发与结果 | 官方内部对会话生命周期加互斥，并拒绝active run/queued work及身份变化。返回ok、compacted、reason、result；ok=true并不等于完成压缩。成功后更新官方摘要/用量，清除旧contextBudgetStatus。 |

可追溯源码：官方tag v2026.9.4的src/gateway/server-methods/sessions-compact.ts、sessions-compaction-runner.ts、sessions-read.ts、src/config/sessions/context-token-provenance.ts；发布包对应sessions-compact-dMze6FvX.mjs、sessions-read-CmsoQhMB.mjs、context-token-provenance-BxxO1HAd.mjs、session-utils-list-RGkE30m3.mjs。接口一般说明见[官方会话CLI](https://docs.openclaw.ai/cli/sessions)与[压缩说明](https://docs.openclaw.ai/concepts/compaction)；在线文档可能已更新，实施合同以当前具名版本验证为准。

### 2.3 实施前接线与重复来源（问题依据）

- web/conversation_api.py的VideoChat._deliver汇合用户回合、handoff及自动结果回传；当前先设dispatching再POST。应把上下文准备放在此共同路径、实际POST之前，而非另造Web入口。
- PersistentWorkToolBridge.reserve已保存turn_id、session_key、native_session_id、prompt_hash，且有现成的同会话占用控制；业务授权仍由claim/prepare/dispatch及持久提案验证。
- easel/gateway_questions.py已有设备签名WS客户端，但当前绑定默认profile、超时处理不完整，且将所有INVALID_REQUEST视为“不支持方法”。复用握手和RPC基础时必须支持与VideoChat相同的目标Gateway，区分忙碌/身份变化/真正不支持；不能原样调用私有_rpc后误判错误。不要把新能力挂在question版本门槛下。
- ConversationService.context构造最多40条sources正文；turn_context保留该数组；reserve又在末尾附本轮原话。所以此前正文会反复写入原生历史，当前原话也可能重复出现。该结构性重复有源码证据；对281483估算的具体占比尚未测，不编造收益。
- ConversationResults另有一次性的结果事件和result_prompt，不能把必须交付的脚本、产物或故障详情一并删掉。

## 3. 当前方案

### 3.1 先让每轮输入只携带必要增量

继续使用turn_context这个自动投影，不改权威记录，也不新增LLM摘要调用。

- 本轮用户原话只在明确标记的新消息位置完整出现一次，保留本轮来源ID与附件身份。
- 自动注入的历史sources改为来源引用，正文通过既有easel_work_context按需读取；不再每轮复制历史原话。source_refs的校验仍从原记录取值，不信任摘要。
- 保留当前Profile/Director选择、brief及未解决事项、当前Work/Plan版本、有效待确认提案、权限/费用和UNKNOWN摘要。完整计划与历史检查结果按既有pending/context读取；这些字段本轮不凭“看起来大”继续删减。
- 提案确认需要的版本、hash和本轮真实回答保持可达；压缩摘要不能代替确认来源。
- 自动结果回传保留实际结果事件与展示所需内容。本期只消除可证明的重复，不把结构化交付拆成新检索系统，也不按字符数截断内容。

### 3.2 一个共同的发送前准备动作

已在Easel增加conversation_compaction.ContextPreparation薄适配层，由VideoChat._deliver调用；职责只有描述会话、必要时请求官方压缩及记录结果。

流程：

1. 沿用现有reserve取得当前待发turn的独占位置；本轮尚未POST、尚无原生run_id。不要在数据库事务内等待RPC。
2. 用该turn绑定的session_key和agentId=main调用sessions.describe。验证非空session的身份与Easel原绑定一致；不允许客户端自由指定另一会话。首次无原生历史不调用压缩。
3. 有效官方contextBudgetStatus明确shouldCompact=true时，调用一次sessions.compact({key,agentId})，不传maxLines。沿用官方判断，不增加70%/80%等新阈值，不按轮数或length触发。没有压力证据时维持普通发送，不把缺失元数据升级为所有会话的阻断。
4. 确认返回已完成且会话仍属原绑定后，重读当前业务状态并生成待发prompt，原子更新prompt_hash，再进入既有dispatching→POST→claim流程。压缩期间的新用户取消/segment撤销优先；宿主事件仍不是用户授权。
5. 同一共同入口覆盖用户消息、handoff和task_result。正常准备/压缩成功后自动继续原待发消息，无需用户输入“继续”。不能自动重发之前发生length的旧消息，更不能重发业务UNKNOWN。

不在before_prompt_build/before_agent_run/工具调用中同步compact：这时原生回合已进入运行，官方active-run互斥可能拒绝或形成等待。也不把“/compact”伪装成用户消息送入创作对话；它会干扰当前用户意图、来源和prompt_hash。

### 3.3 结果、失败与恢复沿用原回合

在现有conversation_turns.payload_json中保存小型context_preparation记录即可：官方证据身份、准备状态、压缩前后检查点/可用token元数据、是否已提交聊天请求及失败类别。不新建生产Task、业务Operation或一套独立审核台账。

| 结果 | Easel处理 |
|---|---|
| 无压力、无历史 | 不做模型压缩，走现有发送。 |
| ok=true且compacted=true | 视为官方压缩完成；重读同会话再发送。token变化仅为观察证据，缺失不填0。成功不等于待发请求已经通过实时预算复检。 |
| compacted=false、ok=false、无进展明确证据 | 如仍有已知压力，不继续照发；保留原待发消息和原因，走现有失败展示。no-op不可统一当成功，不循环调用压缩。 |
| active/queued/session changed | 不取消别的运行、不重建会话；官方明确拒绝时保留未发送回合及失败原因，不自动重复压缩。可用现有停止回答释放这条未发送消息；身份变更需核对，不能另起轮询调度器。 |
| 超时、断连或结果pending | 结果未定，复用现有结果回传tick读回；必须同身份/模型/窗口、新检查点、旧压力清除且无活动运行，才继续原待发回合。检查点时间本身不能替代完成证据，不盲重调compact。请求未必幂等，WS断连也不代表后台已取消。证据不足就保持可核实断点。 |
| 压缩中取消 | 不发送原消息；压缩可能已写入原生摘要，保留事实，不声称取消成功回滚。 |

RPC调用前后要区分“尚未提交chat”和“chat结果未知”，不能把未发送的消息误标成已执行，也不能用压缩成功释放原业务UNKNOWN。现有payload去重保障重连/重放不会重复付费压缩；进程崩溃后的未决compact通过读回处理，不在恢复时重跑同一请求。

官方compact没有对调用方的expectedSessionId原子约束。Easel发送前后身份核对加官方生命周期锁能覆盖自身顺序，但不承诺防住外部客户端恰在调用前重建同key的全部竞争；验收需覆盖变更拒绝。不得为弥补这个边界改OpenClaw或替换业务身份。

### 3.4 压缩效果与费用

压缩针对既有历史，不会缩短当前新消息；输入去重负责避免压缩后又注入同一批历史。现有官方接口没有当前最终请求的无推理预检，因此本期不实现“反复压缩直到估算fits”的新循环，也不伪造一个确定的压缩后总预算。

原生摘要本身可能调用模型并付费，使用官方会话当前模型/认证，不借视频生成授权扩大范围。正式上线时应纳入已有对话模型调用授权范围；范围不足再说明具体调用对象，不把每次自动压缩都做成新的用户审核步骤。本轮不调用compact，也不调用模型。

最小诊断只保存证据来源、会话版本关联、触发原因、compact结果、原生检查点及发送计数，不采集原文/凭证，不扩展为供应商抓包平台。

## 4. 范围、难度与取舍

| 部分 | 改动位置 | 难度/边界 |
|---|---|---|
| 自动投影去重 | conversation_pipeline.turn_context、bridge.reserve；必要的来源提示 | 低至中；确认来源及首次进入上下文不能丢。 |
| 官方RPC适配 | 复用gateway_questions中的连接能力，薄会话适配 | 中；必须按实际Gateway连接，区分业务拒绝和方法缺失，设置真实socket超时。 |
| 发送接线及恢复 | VideoChat._deliver、bridge与结果回传的既有payload | 中；避免并发/重复发送，不能绕开已有占用和UNKNOWN。 |
| 回归 | 现有conversation、execution_wait、results、插件原生测试 | 中；fake足以验证控制流，官方真实摘要效果需要单独授权调用。 |

先做小型离线接口契约验证，再实现公共入口及去重，不引入新数据库表、Agent、Gate、队列、tokenizer或后台守护。若实际安装没有预期describe压力/compact结果，或当前RPC权限不可用，记录明确缺口并停在原Task；不临时读写OpenClaw私有数据库或导入带hash的内部dist来补产品接口。

不做每轮压缩、不调大额度、不丢弃旧历史、不reset/new会话、不重规划或重生成素材。第一次输入暴增及回合内增长留作原目标未覆盖项，不为了这项已知故障展开通用上下文管理重构。

## 5. 实施任务与状态

| 子项 | 交付 | 依赖与停止边界 |
|---|---|---|
| CTX-01.1 官方合同离线验证 | 当前版本describe/compact响应、普通/忙碌/no-op/未知结果、同Gateway连接；验证历史摘要不会变更业务身份 | 首先确认公开接口可用；全用合成会话/假模型，生产不接入。 |
| CTX-01.2 输入投影去重 | 当前原话一次、旧sources引用化、原工具按需读、确认来源完整 | .1；先加能复现重复的测试，不顺带删其他业务字段。 |
| CTX-01.3 公共发送前准备 | 现有回合内describe→必要compact→重组→发送，复用取消/去重/读回 | .1；用户、handoff、task_result统一接线，既有原生工具权限不变。 |
| CTX-01.4 关联离线验收 | §6正反例与现有确认/结果回传/UNKNOWN回归；文档收口 | .2/.3；代码及软件通过不等于真实效果。 |
| CTX-01.5 授权后的定向验证 | 当前官方版本，隔离无生产工具的长会话，真实压缩与下一次发送证据 | .4及明确部署/调用授权；不恢复原片。 |

这些是同一父任务的实施顺序，不新建任务体系。用户已明确授权.1～.4，首批代码及离线验证已完成；.5未授权、NOT_TESTED。具体检查及既有回归失败见父任务，不将离线模拟写成真实Gateway或模型验收。

## 6. 验收与未覆盖项

1. 新会话、短会话或无压力证据时不新增摘要调用；仅length但无上下文证据不触发重试。
2. 同模型/会话有效shouldCompact压力：原生compact先完成，待发chat后发送且仅一次；不发送旧失败消息。错误模型/会话及过时证据不驱动错误压缩。
3. 不传maxLines、不reset、不直接操作原生数据库；历史正文不随每轮自动投影重新展开，本轮原话保留一次且source_refs仍可验证。
4. 压缩失败、明确无进展、并发、断连/pending、进程恢复、取消：无盲重调、无重复chat、无业务副作用重派；完成读回后可合法继续原待发回合。
5. 真实提案id/hash、用户确认引用、Plan版本、费用授权及UNKNOWN沿原持久记录生效；正常交接与自动结果回传不要求用户重复同意。
6. 真实定向验证须有官方摘要完成和随后请求的证据，不拿检查点增加冒充最终请求fits；效果未验证保留NOT_TESTED。

**验收分层**：首批代码与离线用例已交付；首批软件和定向压缩能力分别验收。原“当前最终请求实时预算复检”无公开接口证据，首批不宣称完整CTX-01闭环。父任务保持PARTIAL；其他length根因仍未确认。若用户要求完整目标，本首批不能被当成替代交付。
